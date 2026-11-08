"""Core action logic -- prepare plans and execute them for library nodes.

Every action prepares a structured plan (typed steps, a fingerprint) or an
outcome, and executes exactly the steps of a plan it prepared.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar, Literal

import structlog
from pydantic import ValidationError

from photo_darkroom_manager.core.file_utils import (
    MoveOutcome,
    collect_leaf_paths,
    move_files,
    preview_merge_into_archive,
    prune_empty_dirs,
)
from photo_darkroom_manager.core.jobs import Job, JobCancelled
from photo_darkroom_manager.core.library import (
    ALL_IMAGE_EXTENSIONS,
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
    BatchFolderName,
    DarkroomBatch,
    NodeAction,
    NodeId,
    collect_files_to_tidy,
    format_validation_error,
    is_file_a_photo,
    is_file_a_video,
    recognize_darkroom_batch,
    validate_device_name,
)
from photo_darkroom_manager.core.paths import translate_path

_PREVIEW_STEP_LINES = 35
_FINGERPRINT_LENGTH = 12

log = structlog.get_logger(__name__)

Outcome = Literal["ok", "noop", "refused", "cancelled", "failed"]
ParamValue = str | bool | None
ConflictPolicy = Literal["refuse", "skip", "replace"]
ConflictReason = Literal["exists", "same_target"]
CONFLICT_POLICIES: tuple[ConflictPolicy, ...] = ("refuse", "skip", "replace")


# ---------------------------------------------------------------------------
# Requests, steps and plans
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionRequest:
    """What a client asked for: an action on a node, with its parameters."""

    action: NodeAction
    node_id: NodeId
    params: tuple[tuple[str, ParamValue], ...] = ()

    @classmethod
    def of(
        cls, action: NodeAction, node_id: NodeId, **params: ParamValue
    ) -> ActionRequest:
        return cls(action, node_id, tuple(sorted(params.items())))


def _posix(path: Path) -> str:
    return path.as_posix()


@dataclass(frozen=True)
class Move:
    """Move a file; *overwrite* marks a target that exists and is replaced."""

    kind: ClassVar[str] = "move"
    source: Path
    target: Path
    overwrite: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "source": _posix(self.source),
            "target": _posix(self.target),
            "overwrite": self.overwrite,
        }


@dataclass(frozen=True)
class MakeDir:
    kind: ClassVar[str] = "mkdir"
    path: Path

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "path": _posix(self.path)}


@dataclass(frozen=True)
class Rename:
    kind: ClassVar[str] = "rename"
    source: Path
    target: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "source": _posix(self.source),
            "target": _posix(self.target),
        }


@dataclass(frozen=True)
class OpenFolder:
    kind: ClassVar[str] = "open"
    path: Path

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "path": _posix(self.path)}


@dataclass(frozen=True)
class Launch:
    kind: ClassVar[str] = "launch"
    argv: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "argv": list(self.argv)}


Step = Move | MakeDir | Rename | OpenFolder | Launch
_FILE_STEPS = (Move, MakeDir, Rename)


@dataclass(frozen=True)
class StepFailure:
    step: Step
    reason: str


def _shown(path: Path, bases: Sequence[Path]) -> str:
    for base in bases:
        if path.is_relative_to(base) and path != base:
            return path.relative_to(base).as_posix()
    return str(path)


def describe_step(step: Step, bases: Sequence[Path] = ()) -> str:
    """One preview line for *step*; paths under *bases* are shown relative."""
    match step:
        case Move(source=source, target=target, overwrite=overwrite):
            verb = "replace" if overwrite else "move"
            return f"{verb} {_shown(source, bases)} → {_shown(target, bases)}"
        case MakeDir(path=path) | OpenFolder(path=path):
            return f"{step.kind} {_shown(path, bases)}"
        case Rename(source=source, target=target):
            return f"rename {source.name} → {target.name}"
        case Launch(argv=argv):
            return f"launch {shlex.join(argv)}"


@dataclass(frozen=True)
class Conflict:
    """A planned move that cannot run freely, and why.

    ``exists``: the target already holds a file. ``same_target``: another
    planned move needs the same target.
    """

    move: Move
    reason: ConflictReason

    def as_dict(self) -> dict[str, object]:
        return {**self.move.as_dict(), "reason": self.reason}


def describe_conflict(
    conflict: Conflict, bases: Sequence[Path] = (), label: str = "conflict"
) -> str:
    move = conflict.move
    text = f"{label} {_shown(move.source, bases)} → {_shown(move.target, bases)}"
    if conflict.reason == "same_target":
        text += " (same target as another file)"
    return text


@dataclass(frozen=True)
class ActionPlan:
    """What an action will do, as data; executing it performs only *steps*.

    Conflicting moves are not steps; they are listed in *conflicts* and run
    only as the conflict policy allows.
    """

    request: ActionRequest
    summary: str
    """One line, e.g. ``Archive 42 files``."""
    steps: tuple[Step, ...]
    notes: tuple[str, ...] = ()
    """Context lines for the preview (folders, counts); not fingerprinted."""
    bases: tuple[Path, ...] = ()
    """Folders the preview shows step paths relative to."""
    conflicts: tuple[Conflict, ...] = ()
    conflict_label: str = "conflict"
    """How the preview names a conflict, e.g. ``replace`` for publish."""

    @property
    def changes_files(self) -> bool:
        return any(isinstance(step, _FILE_STEPS) for step in self.steps)

    @property
    def fingerprint(self) -> str:
        """Short digest of the request and the steps; derived, never stored."""
        data = {
            "action": str(self.request.action),
            "node_id": self.request.node_id,
            "params": dict(self.request.params),
            "steps": [step.as_dict() for step in self.steps],
            "conflicts": [conflict.as_dict() for conflict in self.conflicts],
        }
        text = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]

    def preview_text(self) -> str:
        lines = [self.summary, *self.notes]
        counts = Counter(s.kind for s in self.steps)
        listed = ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items()))
        lines.append("")
        lines.append(f"Steps: {listed or 'none'}")
        shown = self.steps[:_PREVIEW_STEP_LINES]
        lines.extend(f"  {describe_step(step, self.bases)}" for step in shown)
        rest = self.steps[_PREVIEW_STEP_LINES:]
        if rest:
            lines.append(f"  … and {len(rest)} more")
        if self.conflicts:
            label = self.conflict_label
            lines.append("")
            lines.append(f"Conflicts ({label}): {len(self.conflicts)}")
            lines.extend(
                f"  {describe_conflict(c, self.bases, label)}"
                for c in self.conflicts[:_PREVIEW_STEP_LINES]
            )
            more = len(self.conflicts) - _PREVIEW_STEP_LINES
            if more > 0:
                lines.append(f"  … and {more} more")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionResult:
    outcome: Outcome
    message: str
    details: str | None = None

    @property
    def success(self) -> bool:
        return self.outcome in ("ok", "noop")


@dataclass(frozen=True)
class ExecutionResult(ActionResult):
    """Result of running an action: what was done, what failed, what is left."""

    done: tuple[Step, ...] = ()
    failed: tuple[StepFailure, ...] = ()
    left: tuple[Path, ...] = ()
    """Sources of the moves a cancel left undone."""
    remaining: tuple[Path, ...] = ()
    """Files still in the acted-on folder after an archive and its cleanup."""
    conflicts: tuple[Conflict, ...] = ()
    """Conflicts found when running: planned ones and targets taken since."""
    skipped: tuple[Conflict, ...] = ()
    """Conflicting moves left undone under the ``skip`` policy."""
    fingerprint: str | None = None
    """Fingerprint of the plan run, or of the current plan when refused."""
    rescan_node_path: Path | None = None
    """Subtree root to rescan after this action; None means no rescan needed."""
    node_path: Path | None = None
    """Folder of the acted-on node afterwards; None when it is gone."""
    library_refreshed: NodeId | None = None
    """Id the engine rescanned after the action; None when it rescanned nothing."""
    node_id: NodeId | None = None
    """Id of the acted-on node afterwards, set by the engine from *node_path*."""


def _refused(message: str, details: str | None = None) -> ExecutionResult:
    return ExecutionResult("refused", message, details)


class PolicyNotSupportedError(ValueError):
    """A conflict policy was asked of an action that does not support it."""

    def __init__(
        self, action: NodeAction, policy: str, supported: Sequence[ConflictPolicy]
    ) -> None:
        names = ", ".join(supported)
        super().__init__(
            f"{action} does not support the {policy!r} conflict policy; "
            f"it supports: {names}"
        )
        self.action = action
        self.policy = policy
        self.supported = tuple(supported)


def _failures_text(failed: Sequence[StepFailure], bases: Sequence[Path]) -> str:
    return "\n".join(f"{describe_step(f.step, bases)}: {f.reason}" for f in failed)


# ---------------------------------------------------------------------------
# Action base
# ---------------------------------------------------------------------------


class Action(ABC):
    """An action on a node: prepare a plan, then execute exactly that plan.

    Subclasses implement ``_prepare`` and ``_execute``. An action executes
    only a plan prepared for its own request. Unexpected errors reach the
    caller.
    """

    action: ClassVar[NodeAction]
    exclusive: ClassVar[bool] = False
    """True for an action that must run alone: while it runs, nothing else
    that changes the library may start."""

    def __init__(self, request: ActionRequest | None) -> None:
        self.request = request or ActionRequest(self.action, "")

    def _plan(
        self,
        summary: str,
        steps: Sequence[Step],
        notes: Sequence[str] = (),
        bases: Sequence[Path] = (),
    ) -> ActionPlan:
        return ActionPlan(
            self.request, summary, tuple(steps), tuple(notes), tuple(bases)
        )

    def prepare(self) -> ActionPlan | ActionResult:
        """The plan for the request, or why there is nothing to run."""
        return self._prepare()

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        """Run *plan* and return what it did.

        Args:
            plan: A plan this action prepared for its own request.
        """
        if plan.request != self.request:
            return _refused("Plan was prepared for another request")
        return replace(self._execute(plan), fingerprint=plan.fingerprint)

    @abstractmethod
    def _prepare(self) -> ActionPlan | ActionResult: ...

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        raise NotImplementedError


class JobAction(Action):
    """A heavy action: it moves files and runs as a job.

    Subclasses implement ``_prepare`` and ``_run``. ``_run`` reports
    progress, logs its steps and checks for a cancel through the job; when
    it stops for a cancel it raises :class:`JobCancelled` with its partial
    result.
    """

    exclusive: ClassVar[bool] = True
    policies: ClassVar[tuple[ConflictPolicy, ...]] = ("refuse",)
    """Conflict policies this action supports; ``refuse`` always."""

    def check_policy(self, policy: str) -> ConflictPolicy:
        """Return *policy* if supported, else raise ``PolicyNotSupportedError``.

        Args:
            policy: The conflict policy a client asked for.
        """
        for supported in self.policies:
            if policy == supported:
                return supported
        raise PolicyNotSupportedError(self.action, policy, self.policies)

    def execute(  # ty: ignore[invalid-method-override]
        self, plan: ActionPlan, *, policy: ConflictPolicy = "refuse", job: Job
    ) -> ExecutionResult:
        """Run *plan* under the conflict *policy* as part of *job*.

        Args:
            plan: A plan this action prepared for its own request.
            policy: What to do with conflicts; the caller has checked it
                with :meth:`check_policy`.
            job: The job the run belongs to: progress, cancel and log.

        Raises:
            JobCancelled: The run stopped for a cancel; its result is what
                was done and left.
        """
        if plan.request != self.request:
            return _refused("Plan was prepared for another request")
        try:
            result = self._run(plan, policy, job)
        except JobCancelled as stopped:
            if not isinstance(stopped.result, ExecutionResult):
                raise
            done = replace(stopped.result, fingerprint=plan.fingerprint)
            raise JobCancelled(done) from None
        return replace(result, fingerprint=plan.fingerprint)

    @abstractmethod
    def _run(
        self, plan: ActionPlan, policy: ConflictPolicy, job: Job
    ) -> ExecutionResult: ...


def _moves(plan: ActionPlan) -> list[Move]:
    return [step for step in plan.steps if isinstance(step, Move)]


def _target_taken(move: Move) -> bool:
    """True if *move*'s target holds a file other than its own source."""
    if not (move.target.exists() or move.target.is_symlink()):
        return False
    try:
        return not move.target.samefile(move.source)
    except OSError:
        return True


@dataclass(frozen=True)
class _MoveRun:
    """What running a plan's moves under a policy did."""

    done: tuple[Step, ...] = ()
    failed: tuple[StepFailure, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    skipped: tuple[Conflict, ...] = ()
    left: tuple[Path, ...] = ()
    refused: bool = False

    @property
    def cancelled(self) -> bool:
        return bool(self.left)

    @property
    def outcome(self) -> Outcome:
        if self.refused:
            return "refused"
        if self.cancelled:
            return "cancelled"
        return "failed" if self.failed else "ok"


def _skipped(conflict: Conflict, reason: str) -> MoveOutcome:
    move = conflict.move
    return MoveOutcome(move.source, move.target, "skipped", reason)


def _log_move(job: Job, outcome: MoveOutcome) -> None:
    """Write one finished, skipped or failed move to *job*'s log."""
    fields = {"source": str(outcome.source), "target": str(outcome.target)}
    if outcome.status == "done":
        job.log.info("step_done", **fields)
    elif outcome.status == "skipped":
        job.log.info("step_skipped", reason=outcome.reason, **fields)
    else:
        job.log.warning("step_failed", reason=outcome.reason, **fields)


def _run_planned_moves(plan: ActionPlan, policy: ConflictPolicy, job: Job) -> _MoveRun:
    """Run the plan's moves under *policy*, re-checking every target first.

    ``refuse``: any conflict, planned or new, refuses before a file moves.
    ``skip``: conflicting moves stay undone and are reported; a target taken
    during the run is skipped the same way. ``replace``: moves onto an
    existing file replace it (same-target conflicts are still skipped).
    *job* hears each move and how far the run got; a cancel stops the run
    between files.
    """
    free: list[Move] = []
    late: list[Conflict] = []
    for move in _moves(plan):
        if _target_taken(move):
            late.append(Conflict(move, "exists"))
        else:
            free.append(move)
    conflicts: list[Conflict] = [*plan.conflicts, *late]
    if conflicts and policy == "refuse":
        for conflict in conflicts:
            _log_move(job, _skipped(conflict, f"conflict ({conflict.reason}); refused"))
        return _MoveRun(conflicts=tuple(conflicts), refused=True)

    def replaces(conflict: Conflict) -> bool:
        return policy == "replace" and conflict.reason == "exists"

    replacing = [replace(c.move, overwrite=True) for c in conflicts if replaces(c)]
    skipped = [c for c in conflicts if not replaces(c)]
    for conflict in skipped:
        _log_move(job, _skipped(conflict, f"conflict ({conflict.reason})"))
    total = len(free) + len(replacing)
    by_pair = {(m.source, m.target): m for m in (*free, *replacing)}
    done: list[Step] = []
    failed: list[StepFailure] = []
    left: list[Path] = []
    finished = 0

    def on_move(outcome: MoveOutcome) -> None:
        nonlocal finished
        finished += 1
        _log_move(job, outcome)
        job.progress(finished, total, outcome.source.name)

    job.progress(0, total, None)
    for moves, replace_existing in ((free, False), (replacing, True)):
        if not moves:
            continue
        if left:
            left.extend(m.source for m in moves)
            continue
        report = move_files(
            ((m.source, m.target) for m in moves),
            replace=replace_existing,
            stop=lambda: job.cancelled,
            on_move=on_move,
        )
        done.extend(by_pair[pair] for pair in report.done)
        failed.extend(
            StepFailure(by_pair[(src, dst)], reason)
            for src, dst, reason in report.failed
        )
        taken = [Conflict(by_pair[pair], "exists") for pair in report.skipped]
        skipped.extend(taken)
        conflicts.extend(taken)
        left.extend(src for src, _ in report.left)
    return _MoveRun(
        done=tuple(done),
        failed=tuple(failed),
        conflicts=tuple(conflicts),
        skipped=tuple(skipped),
        left=tuple(left),
    )


def _conflicts_text(
    conflicts: Sequence[Conflict], bases: Sequence[Path], label: str = "conflict"
) -> str:
    return "\n".join(describe_conflict(c, bases, label) for c in conflicts)


def _refused_for_conflicts(
    plan: ActionPlan, run: _MoveRun, what: str
) -> ExecutionResult:
    choice = "skip or replace them" if "replace" in plan.conflict_label else "skip them"
    return ExecutionResult(
        "refused",
        f"{what} blocked: {len(run.conflicts)} file conflict(s); choose to {choice}",
        _conflicts_text(run.conflicts, plan.bases, plan.conflict_label),
        conflicts=run.conflicts,
    )


def _run_message(verb: str, run: _MoveRun, planned: int) -> str:
    message = f"{verb} {len(run.done)} of {planned} file(s)"
    if run.skipped:
        message += f"; {len(run.skipped)} skipped as conflicts"
    if run.cancelled:
        message += f"; cancelled with {len(run.left)} not moved"
    return message


def _run_details(plan: ActionPlan, run: _MoveRun, *extra: str | None) -> str | None:
    parts = []
    if run.failed:
        parts.append(_failures_text(run.failed, plan.bases))
    if run.skipped:
        parts.append(_conflicts_text(run.skipped, plan.bases, "skipped"))
    parts.extend(e for e in extra if e)
    return "\n".join(parts) or None


def _recognize_batch(darkroom: Path, path: Path) -> DarkroomBatch | None:
    """The batch *path* is in, or ``None`` when it is not in a valid batch."""
    try:
        return recognize_darkroom_batch(darkroom, path)
    except ValueError:
        return None


def _is_batch_folder(darkroom: Path, path: Path) -> bool:
    """True if *path* sits where a batch does: ``DEVICE/YEAR/BATCH``."""
    try:
        return len(path.relative_to(darkroom).parts) == 3
    except ValueError:
        return False


def _unavailable_root(**roots: Path) -> str | None:
    """Message for the first library root that is not a folder, if any.

    Actions check their roots themselves at prepare and execute: a root
    validated earlier may be gone by now (e.g. an unplugged drive).
    """
    for name, root in roots.items():
        if not root.is_dir():
            return f"{name.capitalize()} folder is not available: {root}"
    return None


# ---------------------------------------------------------------------------
# Tidy
# ---------------------------------------------------------------------------


def _file_extension(path: Path) -> str:
    return path.suffix.lstrip(".").lower()


def _tidy_destination(src: Path) -> Path:
    """Resolve target path for a misplaced media file."""
    parent = src.parent
    ext = _file_extension(src)

    if parent.name == PHOTOS_FOLDER and is_file_a_video([ext]):
        return parent.parent / VIDEOS_FOLDER / src.name
    if parent.name == VIDEOS_FOLDER and is_file_a_photo([ext]):
        return parent.parent / PHOTOS_FOLDER / src.name
    if is_file_a_video([ext]):
        return parent / VIDEOS_FOLDER / src.name
    return parent / PHOTOS_FOLDER / src.name


def _build_tidy_moves(folder_path: Path) -> list[tuple[Path, Path]]:
    """Collect misplaced files recursively and pair each with its tidy target.

    Targets are per source folder (e.g. iPhone/IMG.jpg → iPhone/PHOTOS/), not
    flattened to the action root.
    """
    photo_paths, video_paths = collect_files_to_tidy(folder_path, recursive=True)
    sources = photo_paths + video_paths
    return [(src, _tidy_destination(src)) for src in sources]


def _split_tidy_moves(
    moves: Sequence[tuple[Path, Path]],
) -> tuple[list[Move], list[Conflict]]:
    """Split tidy moves into free moves and conflicts.

    A move conflicts when its target holds another file, or when an earlier
    move already needs the same target.
    """
    free: list[Move] = []
    conflicts: list[Conflict] = []
    seen_dst: set[Path] = set()
    for src, dst in moves:
        move = Move(src, dst)
        if dst in seen_dst:
            conflicts.append(Conflict(move, "same_target"))
        elif _target_taken(move):
            conflicts.append(Conflict(move, "exists"))
        else:
            free.append(move)
        seen_dst.add(dst)
    return free, conflicts


def _format_extension_stats(paths: Sequence[Path]) -> list[str]:
    counts = Counter(f".{_file_extension(p)}" for p in paths)
    return [f"  {ext}: {n}" for ext, n in sorted(counts.items())]


class TidyAction(JobAction):
    action = NodeAction.TIDY
    policies = ("refuse", "skip")

    def __init__(self, folder_path: Path, *, request: ActionRequest | None = None):
        super().__init__(request)
        self._folder_path = folder_path

    def _prepare(self) -> ActionPlan | ActionResult:
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return ActionResult("refused", f"Not a directory: {folder_path}")

        moves = _build_tidy_moves(folder_path)
        if not moves:
            return ActionResult("noop", "Nothing to tidy", f"Folder: {folder_path}")

        free, conflicts = _split_tidy_moves(moves)
        photos = [m.source for m in free if m.target.parent.name == PHOTOS_FOLDER]
        videos = [m.source for m in free if m.target.parent.name == VIDEOS_FOLDER]
        notes = [f"Folder: {folder_path}", f"Photos to move: {len(photos)}"]
        notes += _format_extension_stats(photos)
        notes.append(f"Videos to move: {len(videos)}")
        notes += _format_extension_stats(videos)
        summary = f"Tidy {len(free)} files"
        if conflicts:
            summary += f", {len(conflicts)} conflict(s)"
        return replace(
            self._plan(summary, free, notes, [folder_path]),
            conflicts=tuple(conflicts),
        )

    def _run(
        self, plan: ActionPlan, policy: ConflictPolicy, job: Job
    ) -> ExecutionResult:
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return _refused(f"Not a directory: {folder_path}")

        run = _run_planned_moves(plan, policy, job)
        if run.refused:
            return _refused_for_conflicts(plan, run, "Tidy")
        planned = len(_moves(plan)) + len(plan.conflicts)
        result = ExecutionResult(
            run.outcome,
            _run_message("Tidied", run, planned),
            _run_details(plan, run),
            done=run.done,
            failed=run.failed,
            left=run.left,
            conflicts=run.conflicts,
            skipped=run.skipped,
            rescan_node_path=folder_path,
            node_path=folder_path,
        )
        if run.cancelled:
            raise JobCancelled(result)
        return result


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


class ArchiveAction(JobAction):
    action = NodeAction.ARCHIVE
    policies = ("refuse", "skip")

    def __init__(
        self,
        folder_path: Path,
        *,
        darkroom: Path,
        archive: Path,
        request: ActionRequest | None = None,
    ) -> None:
        super().__init__(request)
        self._folder_path = folder_path
        self._darkroom_path = darkroom
        self._archive_path = archive

    def _unavailable_root(self) -> str | None:
        return _unavailable_root(
            darkroom=self._darkroom_path, archive=self._archive_path
        )

    def _prepare(self) -> ActionPlan | ActionResult:
        if problem := self._unavailable_root():
            return ActionResult("refused", problem)
        folder_path = self._folder_path
        batch = _recognize_batch(self._darkroom_path, folder_path)
        if batch is None:
            return ActionResult("refused", "Could not recognize batch for this path")

        target_dir = translate_path(
            folder_path,
            from_area="darkroom",
            from_root=self._darkroom_path,
            to_area="archive",
            to_root=self._archive_path,
        )

        try:
            leaves, duplicates = preview_merge_into_archive(folder_path, target_dir)
        except ValueError as e:
            return ActionResult("refused", str(e))

        if not leaves:
            return ActionResult("noop", "Nothing to archive", f"Folder: {folder_path}")

        source = folder_path.resolve()
        target = target_dir.resolve()
        taken = {src for src, _ in duplicates}
        steps = [
            Move(leaf, target / leaf.relative_to(source))
            for leaf in leaves
            if leaf not in taken
        ]
        conflicts = tuple(Conflict(Move(src, dst), "exists") for src, dst in duplicates)
        summary = f"Archive {len(steps)} files"
        if conflicts:
            summary += f", {len(conflicts)} already in the archive"
        return replace(
            self._plan(
                summary,
                steps,
                [f"From: {source}", f"To:   {target}"],
                [source, target],
            ),
            conflicts=conflicts,
        )

    def _run(
        self, plan: ActionPlan, policy: ConflictPolicy, job: Job
    ) -> ExecutionResult:
        if problem := self._unavailable_root():
            return _refused(problem)
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return _refused(f"Folder does not exist: {folder_path}")

        run = _run_planned_moves(plan, policy, job)
        if run.refused:
            return _refused_for_conflicts(plan, run, "Archive")
        planned = len(_moves(plan)) + len(plan.conflicts)
        # Removing emptied folders is cleanup, not a planned step: a folder
        # held open (e.g. a shell's current folder on Windows) stays.
        try:
            prune_empty_dirs(folder_path)
        except OSError as e:
            kept = f"Emptied folders not removed: {e}"
        else:
            kept = None
        remaining = (
            tuple(collect_leaf_paths(folder_path)) if folder_path.is_dir() else ()
        )
        message = _run_message("Archived", run, planned)
        if remaining:
            message += f"; {len(remaining)} file(s) left in the darkroom"
        result = ExecutionResult(
            run.outcome,
            message,
            _run_details(plan, run, kept),
            done=run.done,
            failed=run.failed,
            left=run.left,
            remaining=remaining,
            conflicts=run.conflicts,
            skipped=run.skipped,
            rescan_node_path=folder_path.parent,
            node_path=folder_path if folder_path.is_dir() else None,
        )
        if run.cancelled:
            raise JobCancelled(result)
        return result


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


class PublishAction(JobAction):
    action = NodeAction.PUBLISH
    policies = ("refuse", "skip", "replace")

    def __init__(
        self,
        batch_path: Path,
        *,
        darkroom: Path,
        showroom: Path,
        request: ActionRequest | None = None,
    ) -> None:
        super().__init__(request)
        self._batch_path = batch_path
        self._showroom_path = showroom
        self._darkroom_path = darkroom

    def _unavailable_root(self) -> str | None:
        return _unavailable_root(
            darkroom=self._darkroom_path, showroom=self._showroom_path
        )

    def _prepare(self) -> ActionPlan | ActionResult:
        if problem := self._unavailable_root():
            return ActionResult("refused", problem)
        batch_path = self._batch_path
        batch = _recognize_batch(self._darkroom_path, batch_path)
        if batch is None:
            return ActionResult("refused", "Could not recognize batch")

        publish_dir = batch_path / PUBLISH_FOLDER
        if not publish_dir.exists():
            return ActionResult("refused", "PUBLISH directory does not exist")
        entries = sorted(publish_dir.iterdir())
        if any(f.is_dir() for f in entries):
            return ActionResult("refused", "PUBLISH directory contains subdirectories")
        files = [f for f in entries if f.is_file()]
        if not files:
            return ActionResult("noop", "PUBLISH directory is empty")

        target_dir = translate_path(
            batch.batch_path,
            from_area="darkroom",
            from_root=self._darkroom_path,
            to_area="showroom",
            to_root=self._showroom_path,
        )
        steps: list[Move] = []
        conflicts: list[Conflict] = []
        for f in files:
            move = Move(f, target_dir / f.name)
            if _target_taken(move):
                conflicts.append(Conflict(move, "exists"))
            else:
                steps.append(move)
        notes = [
            f"From: {publish_dir}",
            f"To:   {target_dir}",
            f"New: {len(steps)}, already in the showroom: {len(conflicts)}",
        ]
        summary = f"Publish {len(files)} files"
        if conflicts:
            summary += f", {len(conflicts)} would be replaced"
        return replace(
            self._plan(summary, steps, notes, [publish_dir, target_dir]),
            conflicts=tuple(conflicts),
            conflict_label="replace",
        )

    def _run(
        self, plan: ActionPlan, policy: ConflictPolicy, job: Job
    ) -> ExecutionResult:
        if problem := self._unavailable_root():
            return _refused(problem)
        run = _run_planned_moves(plan, policy, job)
        if run.refused:
            return _refused_for_conflicts(plan, run, "Publish")
        planned = len(_moves(plan)) + len(plan.conflicts)
        result = ExecutionResult(
            run.outcome,
            _run_message("Published", run, planned),
            _run_details(plan, run),
            done=run.done,
            failed=run.failed,
            left=run.left,
            conflicts=run.conflicts,
            skipped=run.skipped,
            rescan_node_path=self._batch_path,
            node_path=self._batch_path,
        )
        if run.cancelled:
            raise JobCancelled(result)
        return result


# ---------------------------------------------------------------------------
# New batch
# ---------------------------------------------------------------------------


class NewBatchAction(Action):
    action = NodeAction.NEW_BATCH
    exclusive = True

    def __init__(
        self,
        darkroom_path: Path,
        device: str,
        *,
        date: str,
        title: str | None = None,
        request: ActionRequest | None = None,
    ) -> None:
        super().__init__(request)
        self._darkroom_path = darkroom_path
        self._device = device
        self._date = date
        self._title = title

    def _folders(self) -> list[Path] | ActionResult:
        """Device, year, batch and publish folders, or why they are refused.

        Checked at prepare and again at execute.
        """
        darkroom_path = self._darkroom_path
        if problem := _unavailable_root(darkroom=darkroom_path):
            return ActionResult("refused", problem)
        try:
            device = validate_device_name(self._device)
            name = BatchFolderName.from_date(self._date, self._title)
        except ValidationError as e:
            return ActionResult("refused", format_validation_error(e))
        except ValueError as e:
            return ActionResult("refused", str(e))

        device_dir = darkroom_path / device
        year_dir = device_dir / name.year
        batch_dir = year_dir / name.folder_name
        for folder in (device_dir, year_dir):
            if folder.exists() and not folder.is_dir():
                return ActionResult("refused", f"Not a folder: {folder}")
        if not batch_dir.resolve().is_relative_to(darkroom_path.resolve()):
            return ActionResult("refused", "Batch path must remain inside darkroom")
        if batch_dir.exists():
            return ActionResult("refused", f"Batch folder already exists: {batch_dir}")
        return [device_dir, year_dir, batch_dir, batch_dir / PUBLISH_FOLDER]

    def _prepare(self) -> ActionPlan | ActionResult:
        folders = self._folders()
        if isinstance(folders, ActionResult):
            return folders
        steps = [MakeDir(f) for f in folders if not f.exists()]
        batch_dir = folders[2]
        return self._plan(
            f"Create batch {batch_dir.relative_to(self._darkroom_path).as_posix()}",
            steps,
            [f"Darkroom: {self._darkroom_path}"],
            [self._darkroom_path],
        )

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        folders = self._folders()
        if isinstance(folders, ActionResult):
            return _refused(folders.message, folders.details)
        year_dir, batch_dir = folders[1], folders[2]
        done: list[Step] = []
        for step in plan.steps:
            assert isinstance(step, MakeDir)
            try:
                step.path.mkdir(exist_ok=step.path != batch_dir)
            except OSError as e:
                return ExecutionResult(
                    "failed",
                    f"Could not create folder: {step.path}",
                    str(e),
                    done=tuple(done),
                    failed=(StepFailure(step, str(e)),),
                    rescan_node_path=year_dir,
                    node_path=batch_dir if batch_dir.is_dir() else None,
                )
            done.append(step)
        return ExecutionResult(
            "ok",
            f"Created batch: {batch_dir.name}",
            done=tuple(done),
            rescan_node_path=year_dir,
            node_path=batch_dir,
        )


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


def _same_folder(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


class RenameAction(Action):
    action = NodeAction.RENAME
    exclusive = True

    def __init__(
        self,
        batch_path: Path,
        darkroom_path: Path,
        *,
        date: str | None = None,
        title: str | None = None,
        clear_title: bool = False,
        request: ActionRequest | None = None,
    ) -> None:
        super().__init__(request)
        self._batch_path = batch_path
        self._darkroom_path = darkroom_path
        self._date = date
        self._title = title
        self._clear_title = clear_title

    def _check(self) -> ActionResult | None:
        if problem := _unavailable_root(darkroom=self._darkroom_path):
            return ActionResult("refused", problem)
        if not _is_batch_folder(self._darkroom_path, self._batch_path):
            return ActionResult("refused", "Could not recognize batch")
        if not self._batch_path.is_dir():
            return ActionResult(
                "refused", f"Batch folder does not exist: {self._batch_path}"
            )
        return None

    def _new_name(self) -> str | ActionResult:
        old_name = self._batch_path.name
        try:
            current: BatchFolderName | None = BatchFolderName.from_str(old_name)
        except ValidationError:
            current = None
        if self._date is None and current is None:
            return ActionResult(
                "refused", f"Cannot read the date of '{old_name}'; give a new date"
            )
        if self._clear_title:
            title = None
        elif self._title is not None:
            title = self._title
        else:
            title = current.name if current is not None else None
        try:
            if self._date is not None:
                new = BatchFolderName.from_date(self._date, title)
            else:
                assert current is not None
                new = BatchFolderName(
                    year=current.year, month=current.month, day=current.day, name=title
                )
        except ValidationError as e:
            return ActionResult("refused", format_validation_error(e))
        return new.folder_name

    def _prepare(self) -> ActionPlan | ActionResult:
        if refusal := self._check():
            return refusal
        new_name = self._new_name()
        if isinstance(new_name, ActionResult):
            return new_name
        batch_path = self._batch_path
        if new_name == batch_path.name:
            return ActionResult("noop", f"No change: {new_name}")
        new_path = batch_path.parent / new_name
        if new_path.exists() and not _same_folder(batch_path, new_path):
            return ActionResult(
                "refused", f"A folder named '{new_name}' already exists"
            )
        return self._plan(
            f"Rename {batch_path.name} to {new_name}",
            [Rename(batch_path, new_path)],
            [f"Folder: {batch_path.parent}"],
        )

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        if refusal := self._check():
            return _refused(refusal.message, refusal.details)
        (step,) = plan.steps
        assert isinstance(step, Rename)
        if step.target.exists() and not _same_folder(step.source, step.target):
            return _refused(f"A folder named '{step.target.name}' already exists")
        step.source.rename(step.target)
        return ExecutionResult(
            "ok",
            f"Renamed to {step.target.name}",
            done=(step,),
            rescan_node_path=step.source.parent,
            node_path=step.target,
        )


# ---------------------------------------------------------------------------
# External apps and opening a folder
# ---------------------------------------------------------------------------


def _find_first_image(folder: Path) -> Path | None:
    try:
        files = [
            f
            for f in folder.iterdir()
            if f.is_file() and f.suffix.lower().lstrip(".") in ALL_IMAGE_EXTENSIONS
        ]
    except PermissionError:
        return None
    if not files:
        return None
    return min(files, key=lambda p: p.name)


class _NoImageFound(Exception):
    pass


class _CommandMapping(dict[str, str]):
    def __init__(self, folder: Path) -> None:
        super().__init__()
        self._folder = folder.resolve()

    def __missing__(self, key: str) -> str:
        if key == "folder":
            return str(self._folder)
        if key == "first_image_in_folder":
            first = _find_first_image(self._folder)
            if first is None:
                raise _NoImageFound
            return str(first.resolve())
        raise KeyError(key)


def _strip_outer_shell_quotes(part: str) -> str:
    """Drop one pair of outer quotes from a shlex token.

    ``shlex.split(..., posix=False)`` (used so Windows paths keep ``\\``) leaves
    surrounding ``"`` or ``'`` inside the token; ``subprocess`` argv must not
    include those characters.
    """
    if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
        return part[1:-1]
    return part


def _resolve_command(template: str, folder: Path) -> list[str] | ActionResult:
    if not template.strip():
        return ActionResult("refused", "Command is empty")
    mapping = _CommandMapping(folder)
    try:
        resolved = template.format_map(mapping)
    except _NoImageFound:
        return ActionResult(
            "refused",
            "No image found in folder",
            "{first_image_in_folder} requires an image file as a direct child of "
            "the folder (not inside subfolders such as PHOTOS/).",
        )
    except KeyError as e:
        return ActionResult("refused", "Unknown placeholder in command", str(e))
    except ValueError as e:
        return ActionResult("refused", "Invalid command template", str(e))

    try:
        parts = shlex.split(resolved, posix=False)
    except ValueError as e:
        return ActionResult("refused", "Invalid command (quoting)", str(e))

    if not parts:
        return ActionResult("refused", "Command resolves to empty")

    return [_strip_outer_shell_quotes(p) for p in parts]


class OpenExternalAppAction(Action):
    """Launch a configured command for a folder (see cull and edit)."""

    action = NodeAction.EDIT
    config_key: ClassVar[str] = "edit_command"

    def __init__(
        self,
        command_template: str | None,
        folder_path: Path,
        *,
        request: ActionRequest | None = None,
    ) -> None:
        super().__init__(request)
        self._command_template = command_template
        self._folder_path = folder_path

    def _prepare(self) -> ActionPlan | ActionResult:
        if self._command_template is None:
            return ActionResult("refused", f"{self.config_key} is not configured")
        if not self._folder_path.is_dir():
            return ActionResult(
                "refused", f"Folder does not exist: {self._folder_path}"
            )
        argv = _resolve_command(self._command_template, self._folder_path)
        if isinstance(argv, ActionResult):
            return argv
        return self._plan(f"Launch {Path(argv[0]).name}", [Launch(tuple(argv))])

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        (step,) = plan.steps
        assert isinstance(step, Launch)
        try:
            proc = subprocess.Popen(
                step.argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            return ExecutionResult(
                "failed",
                f"Could not start command: {list(step.argv)}",
                str(e),
                failed=(StepFailure(step, str(e)),),
            )

        try:
            code = proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            code = 0
        if code == 0:
            return ExecutionResult(
                "ok",
                "Started external application",
                done=(step,),
                node_path=self._folder_path,
            )
        reason = f"Command exited with code {code}"
        return ExecutionResult("failed", reason, failed=(StepFailure(step, reason),))


class CullAction(OpenExternalAppAction):
    action = NodeAction.CULL
    config_key = "cull_command"


class EditAction(OpenExternalAppAction):
    action = NodeAction.EDIT
    config_key = "edit_command"


def _open_folder(path: Path) -> None:
    """Show *path* in the system file manager."""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class OpenFolderAction(Action):
    """Show a node's folder in the system file manager; changes no files."""

    action = NodeAction.OPEN

    def __init__(self, folder_path: Path, *, request: ActionRequest | None = None):
        super().__init__(request)
        self._folder_path = folder_path

    def _prepare(self) -> ActionPlan | ActionResult:
        if not self._folder_path.is_dir():
            return ActionResult(
                "refused", f"Folder does not exist: {self._folder_path}"
            )
        return self._plan(f"Open {self._folder_path}", [OpenFolder(self._folder_path)])

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        (step,) = plan.steps
        assert isinstance(step, OpenFolder)
        if not step.path.is_dir():
            return _refused(f"Folder does not exist: {step.path}")
        try:
            _open_folder(step.path)
        except OSError as e:
            return ExecutionResult(
                "failed",
                f"Could not open folder: {step.path}",
                str(e),
                failed=(StepFailure(step, str(e)),),
            )
        return ExecutionResult(
            "ok", f"Opened {step.path}", done=(step,), node_path=step.path
        )
