"""Engine -- user configuration, status, library tree, and action dispatch."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

import structlog
from platformdirs import user_config_path, user_log_dir

from photo_darkroom_manager.core.actions import (
    Action,
    ActionPlan,
    ArchiveAction,
    ExecutionResult,
    NewBatchAction,
    OpenExternalAppAction,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.core.library import (
    LibraryTree,
    NodeId,
    NodeView,
    parent_id,
    scan_subtree,
)
from photo_darkroom_manager.core.logging_config import configure_logging
from photo_darkroom_manager.core.paths import Area, translate_path
from photo_darkroom_manager.core.user_config import (
    ConfigIssue,
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


def _scan_stats(node: NodeView) -> tuple[int, int]:
    """Return (batch_count, nodes_with_issues_count) for a node's subtree."""
    batches = 1 if node.kind == "batch" else 0
    issues = 1 if node.issues else 0
    for child in node.children:
        child_batches, child_issues = _scan_stats(child)
        batches += child_batches
        issues += child_issues
    return batches, issues


def _node_id(darkroom: Path, path: Path) -> NodeId:
    """Id of a darkroom *path*; the root for a path outside the darkroom."""
    try:
        relative = path.relative_to(darkroom).as_posix()
    except ValueError:
        return ""
    return "" if relative == "." else relative


def _require_one(*args: Path | None) -> None:
    if sum(1 for a in args if a is not None) != 1:
        raise ValueError("Provide exactly one non-None path argument")


EngineStatus = Literal["unconfigured", "invalid", "ready"]
EngineBusy = Literal["scan", "action", "config"]
ROOT_KEYS = ("darkroom", "showroom", "archive")


class EngineNotReadyError(RuntimeError):
    """Work was requested while the engine status is not ``ready``."""

    def __init__(self, status: EngineStatus, detail: str | None) -> None:
        super().__init__(f"engine is {status}: {detail}")
        self.status = status
        self.detail = detail


class EngineBusyError(RuntimeError):
    """Work or a configuration edit was requested while another one runs."""

    def __init__(self, busy: EngineBusy) -> None:
        super().__init__(f"engine is busy: {busy}")
        self.busy = busy


class LibraryNotScannedError(RuntimeError):
    """A node was read before the library was scanned."""

    def __init__(self) -> None:
        super().__init__("library is not scanned")


class NodeNotFoundError(LookupError):
    """A node id is not in the scanned library tree."""

    def __init__(self, node_id: NodeId) -> None:
        super().__init__(f"node not in the library: {node_id!r}")
        self.node_id = node_id


class Engine:
    def __init__(
        self, config_path: Path | None = None, logs_dir: Path | None = None
    ) -> None:
        self.logs_dir = logs_dir or default_logs_dir()
        configure_logging(logs_dir=self.logs_dir)
        self._user_config = UserConfig(config_path or default_config_path())
        for issue in self._user_config.load():
            log.warning("config_issue", key=issue.key, message=issue.message)
        self.log_level: LogLevel = self._initial_log_level()
        configure_logging(self.log_level, logs_dir=self.logs_dir)
        self._busy_lock = threading.Lock()
        self._busy: EngineBusy | None = None
        self._library: LibraryTree | None = None

    @property
    def darkroom(self) -> Path | None:
        return self._user_config.get_valid("darkroom")

    @property
    def showroom(self) -> Path | None:
        return self._user_config.get_valid("showroom")

    @property
    def archive(self) -> Path | None:
        return self._user_config.get_valid("archive")

    @property
    def cull_command(self) -> str | None:
        return self._user_config.get_valid("cull_command")

    @property
    def edit_command(self) -> str | None:
        return self._user_config.get_valid("edit_command")

    @property
    def status(self) -> EngineStatus:
        if not self._user_config.exists:
            return "unconfigured"
        return "invalid" if self._reasons() else "ready"

    @property
    def status_detail(self) -> str | None:
        if not self._user_config.exists:
            return f"no configuration file at {self._user_config.path}"
        reasons = self._reasons()
        return "; ".join(reasons) if reasons else None

    @property
    def config_issues(self) -> list[ConfigIssue]:
        """Problems of the configuration file not yet fixed by ``config_set``."""
        return self._user_config.issues

    def config_get(self, key: str) -> object:
        """Stored value of *key*, as read if invalid; default if unset."""
        return self._user_config.get(key)

    def config_set(self, key: str, value: object) -> None:
        """Validate and store *value*, in effect at once; refused while busy.

        A different darkroom drops the scanned library tree.
        """
        with self._begin("config"):
            darkroom = self.darkroom
            self._user_config.set(key, value)
            if self._library is not None and self.darkroom != darkroom:
                self._library = None
                log.info("library_dropped", reason="darkroom_changed")

    def config_save(self) -> Path:
        """Write the configuration file; return its path."""
        return self._user_config.save()

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
        return self._user_config.get_valid("log_level") or "INFO"

    def _reasons(self) -> list[str]:
        reasons = [f"{i.key}: {i.message}" for i in self._user_config.issues]
        for key in ROOT_KEYS:
            if any(i.key == key for i in self._user_config.issues):
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

    @contextmanager
    def _begin(self, busy: EngineBusy) -> Iterator[None]:
        """Mark the engine busy for one operation; refuse if another runs."""
        with self._busy_lock:
            if self._busy is not None:
                raise EngineBusyError(self._busy)
            self._busy = busy
        try:
            yield
        finally:
            with self._busy_lock:
                self._busy = None

    @property
    def library_scanning(self) -> bool:
        """True while a full scan or a rescan runs."""
        return self._busy == "scan"

    @property
    def library_scanned(self) -> bool:
        """True when a scanned library tree is available."""
        return self._library is not None

    def library_scan(self) -> None:
        """Scan the whole darkroom into a new library tree."""
        root = self._root("darkroom")
        with self._begin("scan"):
            log.info("library_scan_started", root=str(root))
            started = time.perf_counter()
            self._library = LibraryTree(root, scan_subtree(root, "", "root"))
            batches, issues = _scan_stats(self._library.view(""))
            duration_ms = int((time.perf_counter() - started) * 1000)
            log.info(
                "library_scan_complete",
                root=str(root),
                batches=batches,
                issues=issues,
                duration_ms=duration_ms,
            )

    def library_refresh(self, node_id: NodeId) -> NodeId:
        """Rescan *node_id*, or its nearest existing ancestor; return that id.

        Only that subtree is read from disk; ancestors are updated from the
        stored facts.
        """
        self._require_ready()
        self._require_library()
        with self._begin("scan"):
            return self._refresh(node_id)

    def library_node(self, node_id: NodeId) -> NodeView:
        """Frozen view of *node_id* and its whole subtree."""
        library = self._require_library()
        try:
            return library.view(node_id)
        except KeyError:
            raise NodeNotFoundError(node_id) from None

    def library_devices(self) -> list[str]:
        """Device folders on disk now, including empty ones."""
        return sorted(p.name for p in self._root("darkroom").iterdir() if p.is_dir())

    def _require_library(self) -> LibraryTree:
        if self._library is None:
            raise LibraryNotScannedError()
        return self._library

    def _refresh(self, node_id: NodeId) -> NodeId:
        """Rescan without entering the busy guard; the caller holds it."""
        library = self._require_library()
        target = library.nearest(node_id)
        while target and not library.path(target).is_dir():
            target = library.nearest(parent_id(target))
        log.info("library_refresh_started", node_id=node_id, target=target)
        started = time.perf_counter()
        facts = scan_subtree(library.root, target, library.kind(target))
        library.replace_subtree(target, facts)
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info("library_refresh_complete", target=target, duration_ms=duration_ms)
        return target

    def action_execute(
        self, action: Action, plan: ActionPlan | None
    ) -> ExecutionResult:
        """Run *action* with its *plan*, then rescan the part it affected."""
        with self._begin("action"):
            result = action.execute(plan)
            library = self._library
            if result.rescan_node_path is None or library is None:
                return result
            node_id = _node_id(library.root, result.rescan_node_path)
            return replace(result, library_refreshed=self._refresh(node_id))

    def action_tidy(self, folder_path: Path) -> Action:
        self._require_ready()
        return TidyAction(folder_path)

    def action_open_external_app(
        self, command_template: str, folder_path: Path
    ) -> Action:
        self._require_ready()
        return OpenExternalAppAction(command_template, folder_path)

    def action_archive(self, folder_path: Path) -> Action:
        return ArchiveAction(
            folder_path, darkroom=self._root("darkroom"), archive=self._root("archive")
        )

    def action_publish(self, batch_path: Path) -> Action:
        return PublishAction(
            batch_path,
            darkroom=self._root("darkroom"),
            showroom=self._root("showroom"),
        )

    def action_rename(
        self, batch_path: Path, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return RenameAction(batch_path, self._root("darkroom"), year, month, day, name)

    def action_new_batch(
        self, device: str, year: str, month: str, day: str | None, name: str | None
    ) -> Action:
        return NewBatchAction(self._root("darkroom"), device, year, month, day, name)

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
