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
    ActionRequest,
    ArchiveAction,
    CullAction,
    EditAction,
    ExecutionResult,
    NewBatchAction,
    OpenFolderAction,
    ParamValue,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.core.library import (
    LibraryTree,
    NodeAction,
    NodeId,
    NodeKind,
    NodeView,
    PathOutsideDarkroomError,
    canonical_id,
    is_well_formed_id,
    node_actions,
    node_kind,
    parent_id,
    resolve_path,
    scan_chain,
    scan_subtree,
)
from photo_darkroom_manager.core.logging_config import configure_logging
from photo_darkroom_manager.core.paths import Area, translate_path
from photo_darkroom_manager.core.user_config import (
    CONFIG_KEYS,
    ConfigIssue,
    ConfigValueError,
    LogLevel,
    UserConfig,
    validate_value,
)

__all__ = [
    "ActionNotAllowedError",
    "Engine",
    "EngineBusyError",
    "EngineNotReadyError",
    "LibraryNotScannedError",
    "NodeNotFoundError",
    "PathOutsideDarkroomError",
]

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
    """An id names no library node, no folder, or no node of the scanned tree."""

    def __init__(self, node_id: NodeId) -> None:
        super().__init__(f"node not in the library: {node_id!r}")
        self.node_id = node_id


class ActionNotAllowedError(ValueError):
    """An action was requested on a node whose kind does not list it."""

    def __init__(self, node_id: NodeId, action: NodeAction, kind: NodeKind) -> None:
        super().__init__(f"{action} is not allowed for a {kind}: {node_id!r}")
        self.node_id = node_id
        self.action = action
        self.kind = kind


class Engine:
    def __init__(
        self,
        config_path: Path | None = None,
        logs_dir: Path | None = None,
        *,
        console_log_level: LogLevel | None = None,
    ) -> None:
        self.logs_dir = logs_dir or default_logs_dir()
        self.console_log_level: LogLevel | None = console_log_level
        configure_logging(logs_dir=self.logs_dir, console_level=console_log_level)
        self._user_config = UserConfig(config_path or default_config_path())
        for issue in self._user_config.load():
            log.warning("config_issue", key=issue.key, message=issue.message)
        self.log_level: LogLevel = self._initial_log_level()
        configure_logging(
            self.log_level, logs_dir=self.logs_dir, console_level=console_log_level
        )
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
    def status_issues(self) -> list[ConfigIssue]:
        """What keeps the engine from ``ready``, by configuration key."""
        if not self._user_config.exists:
            return [ConfigIssue(key, "missing", "file") for key in ROOT_KEYS]
        return self._problems()

    @property
    def config_path(self) -> Path:
        return self._user_config.path

    def config_keys(self) -> tuple[str, ...]:
        """Configuration keys, in their defined order."""
        return CONFIG_KEYS

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
        configure_logging(
            valid, logs_dir=self.logs_dir, console_level=self.console_log_level
        )

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
        return [f"{i.key}: {i.message}" for i in self._problems()]

    def _problems(self) -> list[ConfigIssue]:
        problems = list(self._user_config.issues)
        for key in ROOT_KEYS:
            if any(i.key == key for i in self._user_config.issues):
                continue
            path = getattr(self, key)
            if path is None:
                problems.append(ConfigIssue(key, "missing"))
            elif not path.exists():
                problems.append(ConfigIssue(key, f"folder does not exist: {path}"))
            elif not path.is_dir():
                problems.append(ConfigIssue(key, f"not a folder: {path}"))
        return problems

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

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    @property
    def library_scanning(self) -> bool:
        """True while a full scan or a rescan runs."""
        return self._busy == "scan"

    @property
    def library_scanned(self) -> bool:
        """True when a scanned library tree is available."""
        return self._library is not None

    def library_scan(self, node_id: NodeId = "") -> NodeId:
        """Scan *node_id*'s subtree and its ancestors' folders; return its id.

        ``""`` scans the whole darkroom into a new tree. Any other node is
        loaded into the current tree, or a new partial one, with ancestors
        not scanned before as incomplete stubs; the rest is kept as it was.
        """
        root = self._root("darkroom")
        node_id, kind = self._node(node_id)
        if not self._folder(node_id).is_dir():
            raise NodeNotFoundError(node_id)
        with self._begin("scan"):
            log.info("library_scan_started", root=str(root), node_id=node_id)
            started = time.perf_counter()
            facts = scan_subtree(root, node_id, kind)
            chain = scan_chain(root, node_id)
            if self._library is None or not node_id:
                self._library = LibraryTree(root, chain | facts)
            else:
                self._library.load_subtree(node_id, facts, chain)
            batches, issues = _scan_stats(self._library.view(node_id))
            duration_ms = int((time.perf_counter() - started) * 1000)
            log.info(
                "library_scan_complete",
                root=str(root),
                node_id=node_id,
                batches=batches,
                issues=issues,
                duration_ms=duration_ms,
            )
        return node_id

    def library_resolve(self, path: Path) -> NodeId:
        """Id of the darkroom folder at *path*, with the on-disk folder names.

        Raises ``PathOutsideDarkroomError`` for a path outside the darkroom.
        """
        return resolve_path(self._root("darkroom"), path)

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

    def _folder(self, node_id: NodeId) -> Path:
        root = self._root("darkroom")
        return root / node_id if node_id else root

    def _node(self, node_id: NodeId) -> tuple[NodeId, NodeKind]:
        """Canonical id and kind of *node_id*; ``NodeNotFoundError`` if none."""
        if not is_well_formed_id(node_id):
            raise NodeNotFoundError(node_id)
        canonical = canonical_id(self._root("darkroom"), node_id)
        kind = node_kind(canonical)
        if kind is None:
            raise NodeNotFoundError(node_id)
        return canonical, kind

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _target(
        self, node_id: NodeId, action: NodeAction, *, creates: bool = False
    ) -> tuple[NodeId, Path]:
        """Guard a request: *node_id* names a node whose kind lists *action*.

        The folder must exist unless the action creates it. Only the id's
        own folders are read; no scanned tree is needed.
        """
        self._require_ready()
        node_id, kind = self._node(node_id)
        if action not in node_actions(kind):
            raise ActionNotAllowedError(node_id, action, kind)
        path = self._folder(node_id)
        if not creates and not path.is_dir():
            raise NodeNotFoundError(node_id)
        return node_id, path

    def _request(
        self, action: NodeAction, node_id: NodeId, **params: ParamValue
    ) -> tuple[ActionRequest, Path]:
        creates = action == NodeAction.NEW_BATCH
        node_id, path = self._target(node_id, action, creates=creates)
        return ActionRequest.of(action, node_id, **params), path

    def action_execute(self, action: Action, plan: ActionPlan) -> ExecutionResult:
        """Run *action* with its *plan*, then rescan the part it affected."""
        with self._begin("action"):
            return self._run(action, plan)

    def action_apply(
        self, action: Action, confirm: str | None = None
    ) -> ExecutionResult:
        """Prepare and execute *action* in one guarded call.

        With *confirm*, execute only when the new plan has that fingerprint;
        otherwise refuse, reporting both fingerprints.
        """
        with self._begin("action"):
            prepared = action.prepare()
            if not isinstance(prepared, ActionPlan):
                return ExecutionResult(
                    prepared.outcome, prepared.message, prepared.details
                )
            current = prepared.fingerprint
            if confirm is not None and confirm != current:
                return ExecutionResult(
                    "refused",
                    f"plan changed since {confirm} (now {current}); preview again",
                    fingerprint=current,
                )
            return self._run(action, prepared)

    def _run(self, action: Action, plan: ActionPlan) -> ExecutionResult:
        """Execute and refresh without entering the busy guard."""
        result = action.execute(plan)
        darkroom = self.darkroom
        if result.node_path is not None and darkroom is not None:
            result = replace(result, node_id=_node_id(darkroom, result.node_path))
        library = self._library
        if result.rescan_node_path is None or library is None:
            return result
        node_id = _node_id(library.root, result.rescan_node_path)
        return replace(result, library_refreshed=self._refresh(node_id))

    def action_open(self, node_id: NodeId) -> Action:
        request, path = self._request(NodeAction.OPEN, node_id)
        return OpenFolderAction(path, request=request)

    def action_tidy(self, node_id: NodeId) -> Action:
        request, path = self._request(NodeAction.TIDY, node_id)
        return TidyAction(path, request=request)

    def action_cull(self, node_id: NodeId) -> Action:
        """Launch the configured ``cull_command`` for the node's folder."""
        request, path = self._request(NodeAction.CULL, node_id)
        return CullAction(self.cull_command, path, request=request)

    def action_edit(self, node_id: NodeId) -> Action:
        """Launch the configured ``edit_command`` for the node's folder."""
        request, path = self._request(NodeAction.EDIT, node_id)
        return EditAction(self.edit_command, path, request=request)

    def action_archive(self, node_id: NodeId) -> Action:
        request, path = self._request(NodeAction.ARCHIVE, node_id)
        return ArchiveAction(
            path,
            darkroom=self._root("darkroom"),
            archive=self._root("archive"),
            request=request,
        )

    def action_publish(self, node_id: NodeId) -> Action:
        request, path = self._request(NodeAction.PUBLISH, node_id)
        return PublishAction(
            path,
            darkroom=self._root("darkroom"),
            showroom=self._root("showroom"),
            request=request,
        )

    def action_rename(
        self,
        node_id: NodeId,
        *,
        date: str | None = None,
        title: str | None = None,
        clear_title: bool = False,
    ) -> Action:
        """Rename a batch; an omitted date or title keeps the current one."""
        request, path = self._request(
            NodeAction.RENAME, node_id, date=date, title=title, clear_title=clear_title
        )
        return RenameAction(
            path,
            self._root("darkroom"),
            date=date,
            title=title,
            clear_title=clear_title,
            request=request,
        )

    def action_new_batch(
        self, device_id: NodeId, *, date: str, title: str | None = None
    ) -> Action:
        """Create a batch dated *date* (``YYYY-MM[-DD]``) under a device.

        The device folder is created too when it does not exist yet.
        """
        request, _ = self._request(
            NodeAction.NEW_BATCH, device_id, date=date, title=title
        )
        return NewBatchAction(
            self._root("darkroom"),
            request.node_id,
            date=date,
            title=title,
            request=request,
        )

    # ------------------------------------------------------------------
    # Paths between areas
    # ------------------------------------------------------------------

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
