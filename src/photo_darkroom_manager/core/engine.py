"""Engine -- user configuration, status, library tree, jobs and actions."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

import structlog
from platformdirs import user_config_path, user_log_dir
from structlog.stdlib import BoundLogger

from photo_darkroom_manager.core.actions import (
    Action,
    ActionPlan,
    ActionRequest,
    ArchiveAction,
    ConflictPolicy,
    CullAction,
    EditAction,
    ExecutionResult,
    JobAction,
    NewBatchAction,
    OpenFolderAction,
    ParamValue,
    PolicyNotSupportedError,
    PublishAction,
    RenameAction,
    TidyAction,
)
from photo_darkroom_manager.core.jobs import (
    Job,
    JobBusyError,
    JobCancelled,
    JobSlot,
    JobView,
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
    "JobCancelled",
    "LibraryNotScannedError",
    "NodeNotFoundError",
    "PathOutsideDarkroomError",
    "PolicyNotSupportedError",
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


def _visitor(job: Job):
    """Scan hook: stop on cancel, count folders as indeterminate progress."""
    count = 0

    def visit(node_id: NodeId) -> None:
        nonlocal count
        if job.cancelled:
            raise JobCancelled
        count += 1
        job.progress(count, None, node_id or None)

    return visit


def _require_one(*args: Path | None) -> None:
    if sum(1 for a in args if a is not None) != 1:
        raise ValueError("Provide exactly one non-None path argument")


EngineStatus = Literal["unconfigured", "invalid", "ready"]
ROOT_KEYS = ("darkroom", "showroom", "archive")
SCAN_JOBS = frozenset({"scan", "refresh"})
"""Names of the jobs that read the library from disk."""
JOBS_DIR_NAME = "jobs"
"""Folder in the logs folder that holds one log file per job."""
_CHANGES_KEPT = 64

EngineBusyError = JobBusyError
"""Work that must run alone was requested while a job or an exclusive
action runs."""


class EngineNotReadyError(RuntimeError):
    """Work was requested while the engine status is not ``ready``."""

    def __init__(self, status: EngineStatus, detail: str | None) -> None:
        super().__init__(f"engine is {status}: {detail}")
        self.status = status
        self.detail = detail


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


@dataclass(frozen=True)
class ScanResult:
    """Result of a scan or refresh job.

    Args:
        node_id: The id that was scanned or rescanned.
    """

    node_id: NodeId


def _job_description(node_id: NodeId) -> str:
    """Free-form description of a job on *node_id*."""
    return node_id or "darkroom root"


def _log_result(logger: BoundLogger, result: ExecutionResult) -> None:
    """Write what an action did, as the last line of its log."""
    logger.info(
        "action_result",
        outcome=result.outcome,
        message=result.message,
        done=len(result.done),
        failed=len(result.failed),
        skipped=len(result.skipped),
        conflicts=len(result.conflicts),
        left=[str(p) for p in result.left],
        remaining=[str(p) for p in result.remaining],
        refreshed=result.library_refreshed,
    )


def _under(node_id: NodeId, other: NodeId) -> bool:
    """True if *node_id* is *other* or inside it."""
    return other == "" or node_id == other or node_id.startswith(f"{other}/")


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
        self._jobs = JobSlot(self.logs_dir / JOBS_DIR_NAME)
        self._tree_lock = threading.RLock()
        self._library: LibraryTree | None = None
        self._revision = 0
        self._changes: deque[tuple[int, NodeId]] = deque(maxlen=_CHANGES_KEPT)

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
        self._jobs.require_idle()
        with self._tree_lock:
            darkroom = self.darkroom
            self._user_config.set(key, value)
            if self._library is not None and self.darkroom != darkroom:
                self._library = None
                self._record_change("")
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

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    @property
    def job(self) -> JobView | None:
        """Snapshot of the current or last job; ``None`` before the first."""
        return self._jobs.view

    def job_wait(self, timeout: float | None = None) -> JobView | None:
        """Wait until the job ends or *timeout* seconds pass; return it."""
        return self._jobs.wait(timeout)

    def job_cancel(self) -> None:
        """Ask the running job to stop between steps; no-op when idle."""
        self._jobs.cancel()

    def _wait_finished(self) -> JobView:
        view = self._jobs.wait()
        assert view is not None and view.finished
        if view.state == "failed" and (error := self._jobs.exception) is not None:
            raise error
        return view

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    @property
    def library_scanning(self) -> bool:
        """True while a scan or refresh job runs."""
        job = self._jobs.busy
        return job is not None and job.name in SCAN_JOBS

    @property
    def library_scanned(self) -> bool:
        """True when a scanned library tree is available."""
        return self._library is not None

    @property
    def library_revision(self) -> int:
        """Grows every time any part of the tree changes."""
        with self._tree_lock:
            return self._revision

    def library_changes(self, since: int) -> tuple[NodeId, ...]:
        """Ids of the subtrees loaded or rescanned after revision *since*.

        Ids inside another returned id are left out. Returns the root when
        the changes since then are no longer kept or the tree was dropped.
        """
        with self._tree_lock:
            if since >= self._revision:
                return ()
            if not self._changes or self._changes[0][0] > since + 1:
                return ("",)
            ids = list(dict.fromkeys(n for r, n in self._changes if r > since))
        if "" in ids:
            return ("",)
        return tuple(n for n in ids if not any(o != n and _under(n, o) for o in ids))

    def _record_change(self, node_id: NodeId) -> None:
        """Bump the revision for a change of *node_id*'s subtree (lock held)."""
        self._revision += 1
        self._changes.append((self._revision, node_id))

    def library_scan_start(self, node_id: NodeId = "") -> JobView:
        """Start scanning *node_id*'s subtree and its ancestors' folders.

        ``""`` scans the whole darkroom into a new tree. Any other node is
        loaded into the current tree, or a new partial one, with ancestors
        not scanned before as incomplete stubs; the rest is kept as it was.
        The tree changes only when the scan completes.
        """
        root = self._root("darkroom")
        node_id, kind = self._node(node_id)
        if not self._folder(node_id).is_dir():
            raise NodeNotFoundError(node_id)
        return self._jobs.start(
            lambda job: self._scan(job, root, node_id, kind),
            name="scan",
            description=_job_description(node_id),
        )

    def library_scan(self, node_id: NodeId = "") -> NodeId:
        """Scan as a job and wait for it; return the scanned id."""
        self.library_scan_start(node_id)
        view = self._wait_finished()
        if view.state == "cancelled":
            raise JobCancelled
        return view.result.node_id

    def _scan(
        self, job: Job, root: Path, node_id: NodeId, kind: NodeKind
    ) -> ScanResult:
        job.log.info("scan_started", root=str(root), node_id=node_id)
        started = time.perf_counter()
        facts = scan_subtree(root, node_id, kind, visit=_visitor(job))
        chain = scan_chain(root, node_id)
        with self._tree_lock:
            if self._library is None or not node_id:
                self._library = LibraryTree(root, chain | facts)
            else:
                self._library.load_subtree(node_id, facts, chain)
            self._record_change(node_id)
            batches, issues = _scan_stats(self._library.view(node_id))
        duration_ms = int((time.perf_counter() - started) * 1000)
        job.log.info(
            "scan_result",
            root=str(root),
            node_id=node_id,
            batches=batches,
            issues=issues,
            duration_ms=duration_ms,
        )
        return ScanResult(node_id)

    def library_resolve(self, path: Path) -> NodeId:
        """Id of the darkroom folder at *path*, with the on-disk folder names.

        Raises ``PathOutsideDarkroomError`` for a path outside the darkroom.
        """
        return resolve_path(self._root("darkroom"), path)

    def library_refresh_start(self, node_id: NodeId) -> JobView:
        """Start rescanning *node_id*, or its nearest existing ancestor.

        Only that subtree is read from disk; ancestors are updated from the
        stored facts. The job's result names the id that was rescanned.
        """
        self._require_ready()
        self._require_library()

        def work(job: Job) -> ScanResult:
            refreshed = self._refresh(node_id, job.log, job)
            job.log.info("refresh_result", node_id=node_id, refreshed=refreshed)
            return ScanResult(refreshed)

        return self._jobs.start(
            work, name="refresh", description=_job_description(node_id)
        )

    def library_refresh(self, node_id: NodeId) -> NodeId:
        """Refresh as a job and wait for it; return the rescanned id."""
        self.library_refresh_start(node_id)
        view = self._wait_finished()
        if view.state == "cancelled":
            raise JobCancelled
        return view.result.node_id

    def library_node(self, node_id: NodeId) -> NodeView:
        """Frozen view of *node_id* and its whole subtree."""
        with self._tree_lock:
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

    def _refresh(
        self, node_id: NodeId, logger: BoundLogger, job: Job | None = None
    ) -> NodeId:
        """Rescan *node_id*; disk is read outside the tree lock.

        Args:
            node_id: The id to rescan, or the nearest existing ancestor.
            logger: Where the rescan's lines go.
            job: The refresh job, which may cancel the rescan and hears its
                progress; ``None`` for the rescan after an action, which is
                never cancelled.
        """
        with self._tree_lock:
            library = self._require_library()
            target = library.nearest(node_id)
            while target and not library.path(target).is_dir():
                target = library.nearest(parent_id(target))
            root, kind = library.root, library.kind(target)
        logger.info("refresh_started", node_id=node_id, target=target)
        started = time.perf_counter()
        visit = _visitor(job) if job is not None else None
        facts = scan_subtree(root, target, kind, visit=visit)
        with self._tree_lock:
            if self._library is not library:
                return target
            library.replace_subtree(target, facts)
            self._record_change(target)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info("refresh_complete", target=target, duration_ms=duration_ms)
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

    def action_start(
        self,
        action: JobAction,
        *,
        confirm: str | None = None,
        policy: str = "refuse",
    ) -> JobView:
        """Start preparing and executing a heavy *action* as a job; return it.

        Args:
            action: The heavy action to run (tidy, archive, publish).
            confirm: Execute only when the new plan has this fingerprint;
                otherwise the job ends with a refusal naming both.
            policy: What to do with conflicts.

        Raises:
            PolicyNotSupportedError: The action does not support *policy*.
            EngineBusyError: A job or an exclusive action runs.
        """
        if not isinstance(action, JobAction):
            raise ValueError(f"{action.action} runs at once; use action_apply")
        checked = action.check_policy(policy)
        return self._jobs.start(
            lambda job: self._apply(action, confirm, checked, job),
            name=str(action.action),
            description=_job_description(action.request.node_id),
        )

    def action_apply(
        self,
        action: Action,
        confirm: str | None = None,
        policy: str = "refuse",
    ) -> ExecutionResult:
        """Prepare and execute *action*, waiting for the result.

        A heavy action runs as a job. Any other runs at once; an exclusive
        one (rename, new batch) holds the engine while it runs, the others
        (open, cull, edit) also run while a job runs.

        Args:
            action: The action to run.
            confirm: Execute only when the new plan has this fingerprint.
            policy: What to do with conflicts; only heavy actions take one
                other than ``refuse``.

        Raises:
            PolicyNotSupportedError: The action does not support *policy*.
            EngineBusyError: The action must run alone and the engine is
                busy.
        """
        if isinstance(action, JobAction):
            self.action_start(action, confirm=confirm, policy=policy)
            view = self._wait_finished()
            assert isinstance(view.result, ExecutionResult)
            return view.result
        if policy != "refuse":
            raise PolicyNotSupportedError(action.action, policy, ("refuse",))
        if not action.exclusive:
            return self._apply(action, confirm, "refuse", None)
        description = _job_description(action.request.node_id)
        with self._jobs.hold(str(action.action), description):
            return self._apply(action, confirm, "refuse", None)

    def _apply(
        self,
        action: Action,
        confirm: str | None,
        policy: ConflictPolicy,
        job: Job | None,
    ) -> ExecutionResult:
        """Prepare, check *confirm*, execute and rescan; log request and result.

        Args:
            action: The action to run.
            confirm: Fingerprint the new plan must have, if given.
            policy: Conflict policy, already checked.
            job: The job of a heavy action; ``None`` for one run at once,
                which logs to the application log.
        """
        logger = job.log if job is not None else log
        try:
            result = self._prepare_and_run(action, confirm, policy, job, logger)
        except JobCancelled as stopped:
            if isinstance(stopped.result, ExecutionResult):
                _log_result(logger, stopped.result)
            raise
        _log_result(logger, result)
        return result

    def _prepare_and_run(
        self,
        action: Action,
        confirm: str | None,
        policy: ConflictPolicy,
        job: Job | None,
        logger: BoundLogger,
    ) -> ExecutionResult:
        request = action.request
        if job is not None:
            job.progress(0)
        prepared = action.prepare()
        if not isinstance(prepared, ActionPlan):
            logger.info(
                "action_request",
                action=str(request.action),
                node_id=request.node_id,
                params=dict(request.params),
                policy=policy,
                prepared=prepared.outcome,
                message=prepared.message,
            )
            return ExecutionResult(prepared.outcome, prepared.message, prepared.details)
        current = prepared.fingerprint
        logger.info(
            "action_request",
            action=str(request.action),
            node_id=request.node_id,
            params=dict(request.params),
            policy=policy,
            fingerprint=current,
            confirm=confirm,
            summary=prepared.summary,
            notes=list(prepared.notes),
            steps=len(prepared.steps),
            conflicts=len(prepared.conflicts),
        )
        if confirm is not None and confirm != current:
            return ExecutionResult(
                "refused",
                f"plan changed since {confirm} (now {current}); preview again",
                fingerprint=current,
            )
        if not isinstance(action, JobAction):
            return self._after(action.execute(prepared), logger)
        assert job is not None
        try:
            result = action.execute(prepared, policy=policy, job=job)
        except JobCancelled as stopped:
            if not isinstance(stopped.result, ExecutionResult):
                raise
            raise JobCancelled(self._after(stopped.result, logger)) from None
        return self._after(result, logger)

    def _after(self, result: ExecutionResult, logger: BoundLogger) -> ExecutionResult:
        """Name the acted-on node and rescan what changed; never cancelled."""
        darkroom = self.darkroom
        if result.node_path is not None and darkroom is not None:
            result = replace(result, node_id=_node_id(darkroom, result.node_path))
        library = self._library
        if result.rescan_node_path is None or library is None:
            return result
        node_id = _node_id(library.root, result.rescan_node_path)
        return replace(result, library_refreshed=self._refresh(node_id, logger))

    def action_open(self, node_id: NodeId) -> Action:
        request, path = self._request(NodeAction.OPEN, node_id)
        return OpenFolderAction(path, request=request)

    def action_tidy(self, node_id: NodeId) -> JobAction:
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

    def action_archive(self, node_id: NodeId) -> JobAction:
        request, path = self._request(NodeAction.ARCHIVE, node_id)
        return ArchiveAction(
            path,
            darkroom=self._root("darkroom"),
            archive=self._root("archive"),
            request=request,
        )

    def action_publish(self, node_id: NodeId) -> JobAction:
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
