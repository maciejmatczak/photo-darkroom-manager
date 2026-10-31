"""Engine -- user configuration, status, scan tree, and action dispatch."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal, cast

import structlog
from platformdirs import user_config_path, user_log_dir

from photo_darkroom_manager.actions import (
    Action,
    ArchiveAction,
    NewBatchAction,
    OpenExternalAppAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.logging_config import configure_logging
from photo_darkroom_manager.paths import Area, translate_path
from photo_darkroom_manager.scan import (
    DarkroomNode,
    reaggregate_ancestors,
    rescan_subtree,
    scan_darkroom,
)
from photo_darkroom_manager.user_config import (
    ConfigValueError,
    LogLevel,
    UserConfig,
    validate_value,
)

log = structlog.get_logger(__name__)

APP_NAME = "photo-darkroom-manager"
CONFIG_FILENAME = "config.yaml"
CONFIG_PATH_ENV = "PHOTO_DARKROOM_MANAGER_CONFIG_PATH"
LOG_LEVEL_ENV = "PHOTO_DARKROOM_MANAGER_LOG_LEVEL"


def default_config_path() -> Path:
    """Config file: ``$PHOTO_DARKROOM_MANAGER_CONFIG_PATH`` or platformdirs."""
    override = os.environ.get(CONFIG_PATH_ENV)
    if override is not None and override.strip():
        return Path(override).expanduser().resolve()
    return user_config_path(APP_NAME, ensure_exists=True) / CONFIG_FILENAME


def default_logs_dir() -> Path:
    """Directory for per-run log files (platformdirs user log dir)."""
    return Path(user_log_dir(APP_NAME, ensure_exists=True))


def _scan_stats(node: DarkroomNode) -> tuple[int, int]:
    """Return (batch_count, nodes_with_issues_count) for a scan tree."""
    batches = 1 if node.node_type == "batch" else 0
    issues = 1 if node.issues else 0
    for child in node.children:
        child_batches, child_issues = _scan_stats(child)
        batches += child_batches
        issues += child_issues
    return batches, issues


def _require_one(*args: Path | None) -> None:
    if sum(1 for a in args if a is not None) != 1:
        raise ValueError("Provide exactly one non-None path argument")


EngineStatus = Literal["unconfigured", "invalid", "ready"]
ROOT_KEYS = ("darkroom", "showroom", "archive")


class EngineNotReadyError(RuntimeError):
    """Work was requested while the engine status is not ``ready``."""

    def __init__(self, status: EngineStatus, detail: str | None) -> None:
        super().__init__(f"engine is {status}: {detail}")
        self.status = status
        self.detail = detail


class Engine:
    def __init__(
        self, config_path: Path | None = None, logs_dir: Path | None = None
    ) -> None:
        self.logs_dir = logs_dir or default_logs_dir()
        configure_logging(logs_dir=self.logs_dir)
        self.user_config = UserConfig(config_path or default_config_path())
        for issue in self.user_config.load():
            log.warning("config_issue", key=issue.key, message=issue.message)
        self.log_level: LogLevel = self._initial_log_level()
        configure_logging(self.log_level, logs_dir=self.logs_dir)
        self.tree: DarkroomNode | None = None
        self.scanning = False

    @property
    def darkroom(self) -> Path | None:
        return self.user_config.get_valid("darkroom")

    @property
    def showroom(self) -> Path | None:
        return self.user_config.get_valid("showroom")

    @property
    def archive(self) -> Path | None:
        return self.user_config.get_valid("archive")

    @property
    def cull_command(self) -> str | None:
        return self.user_config.get_valid("cull_command")

    @property
    def edit_command(self) -> str | None:
        return self.user_config.get_valid("edit_command")

    @property
    def status(self) -> EngineStatus:
        if not self.user_config.exists:
            return "unconfigured"
        return "invalid" if self._reasons() else "ready"

    @property
    def status_detail(self) -> str | None:
        if not self.user_config.exists:
            return f"no configuration file at {self.user_config.path}"
        reasons = self._reasons()
        return "; ".join(reasons) if reasons else None

    def set_log_level(self, level: str) -> None:
        """Change the running log level; the configuration is not touched."""
        valid = cast(LogLevel, validate_value("log_level", level))
        self.log_level = valid
        configure_logging(valid, logs_dir=self.logs_dir)

    def _initial_log_level(self) -> LogLevel:
        """Env override, then the configuration, then ``INFO``."""
        env = os.environ.get(LOG_LEVEL_ENV, "").strip()
        if env:
            try:
                return cast(LogLevel, validate_value("log_level", env))
            except ConfigValueError as e:
                log.warning("log_level_env_ignored", value=env, message=e.message)
        return self.user_config.get_valid("log_level") or "INFO"

    def _reasons(self) -> list[str]:
        reasons = [f"{i.key}: {i.message}" for i in self.user_config.issues]
        for key in ROOT_KEYS:
            if any(i.key == key for i in self.user_config.issues):
                continue
            path = getattr(self, key)
            if path is None:
                reasons.append(f"{key}: missing")
            elif not path.exists():
                reasons.append(f"{key}: folder does not exist: {path}")
            elif not path.is_dir():
                reasons.append(f"{key}: not a folder: {path}")
        return reasons

    def _require_ready(self) -> None:
        status = self.status
        if status != "ready":
            raise EngineNotReadyError(status, self.status_detail)

    def _root(self, area: Area) -> Path:
        """Root of *area*, defined once the engine is ``ready``."""
        self._require_ready()
        root = getattr(self, area)
        assert root is not None
        return root

    def _translate(self, path: Path, from_area: Area, to_area: Area) -> Path:
        return translate_path(
            path,
            from_area=from_area,
            from_root=self._root(from_area),
            to_area=to_area,
            to_root=self._root(to_area),
        )

    def rescan_subtree(self, node: DarkroomNode) -> DarkroomNode:
        """Rescan *node* in place and reaggregate ancestors. Returns *node*.

        Preferred over ``rescan()`` when only a single subtree has changed
        (e.g. after a tidy or publish action).  I/O is limited to the node's
        subtree; ancestor stats/issues are re-aggregated cheaply without disk
        access.
        """
        self._require_ready()
        log.info("rescan_subtree_started", path=str(node.path))
        started = time.perf_counter()
        rescan_subtree(node)
        reaggregate_ancestors(node)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "rescan_subtree_complete", path=str(node.path), duration_ms=duration_ms
        )
        return node

    def rescan(self) -> DarkroomNode:
        root = self._root("darkroom")
        log.info("rescan_started", root=str(root))
        started = time.perf_counter()
        self.scanning = True
        try:
            self.tree = scan_darkroom(root)
        finally:
            self.scanning = False
        batches, issues = _scan_stats(self.tree)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "rescan_complete",
            root=str(root),
            batches=batches,
            issues=issues,
            duration_ms=duration_ms,
        )
        return self.tree

    def tidy_action(self, folder_path: Path) -> Action:
        self._require_ready()
        return TidyAction(folder_path)

    def open_external_app_action(
        self, command_template: str, folder_path: Path
    ) -> Action:
        self._require_ready()
        return OpenExternalAppAction(command_template, folder_path)

    def archive_action(self, folder_path: Path) -> Action:
        return ArchiveAction(
            folder_path, darkroom=self._root("darkroom"), archive=self._root("archive")
        )

    def publish_action(self, batch_path: Path) -> Action:
        return PublishAction(
            batch_path,
            darkroom=self._root("darkroom"),
            showroom=self._root("showroom"),
        )

    def rename_action(
        self, batch_path: Path, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return RenameAction(batch_path, self._root("darkroom"), year, month, day, name)

    def new_batch_action(
        self, device: str, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return NewBatchAction(self._root("darkroom"), device, year, month, day, name)

    def list_devices(self) -> list[str]:
        """Discover current device directories, including empty ones."""
        return sorted(p.name for p in self._root("darkroom").iterdir() if p.is_dir())

    def darkroom_path(
        self,
        *,
        archive_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(archive_path, showroom_path)
        if archive_path is not None:
            return self._translate(archive_path, "archive", "darkroom")
        assert showroom_path is not None
        return self._translate(showroom_path, "showroom", "darkroom")

    def showroom_path(
        self,
        *,
        darkroom_path: Path | None = None,
        archive_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, archive_path)
        if darkroom_path is not None:
            return self._translate(darkroom_path, "darkroom", "showroom")
        assert archive_path is not None
        return self._translate(archive_path, "archive", "showroom")

    def archive_path(
        self,
        *,
        darkroom_path: Path | None = None,
        showroom_path: Path | None = None,
    ) -> Path:
        _require_one(darkroom_path, showroom_path)
        if darkroom_path is not None:
            return self._translate(darkroom_path, "darkroom", "archive")
        assert showroom_path is not None
        return self._translate(showroom_path, "showroom", "archive")
