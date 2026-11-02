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
import traceback
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar, Literal

import structlog
from pydantic import ValidationError

from photo_darkroom_manager.core.file_utils import (
    collect_leaf_paths,
    move_files,
    preview_merge_into_archive,
    prune_empty_dirs,
)
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

Outcome = Literal["ok", "noop", "refused", "failed"]
ParamValue = str | bool | None


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
            verb = "overwrite" if overwrite else "move"
            return f"{verb} {_shown(source, bases)} → {_shown(target, bases)}"
        case MakeDir(path=path) | OpenFolder(path=path):
            return f"{step.kind} {_shown(path, bases)}"
        case Rename(source=source, target=target):
            return f"rename {source.name} → {target.name}"
        case Launch(argv=argv):
            return f"launch {shlex.join(argv)}"


@dataclass(frozen=True)
class ActionPlan:
    """What an action will do, as data; executing it performs only *steps*."""

    request: ActionRequest
    summary: str
    """One line, e.g. ``Archive 42 files``."""
    steps: tuple[Step, ...]
    notes: tuple[str, ...] = ()
    """Context lines for the preview (folders, counts); not fingerprinted."""
    bases: tuple[Path, ...] = ()
    """Folders the preview shows step paths relative to."""

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
        }
        text = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]

    def preview_text(self) -> str:
        lines = [self.summary, *self.notes]
        counts = Counter(
            "overwrite" if isinstance(s, Move) and s.overwrite else s.kind
            for s in self.steps
        )
        lines.append("")
        lines.append(
            "Steps: " + ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items()))
        )
        shown = self.steps[:_PREVIEW_STEP_LINES]
        lines.extend(f"  {describe_step(step, self.bases)}" for step in shown)
        rest = self.steps[_PREVIEW_STEP_LINES:]
        if rest:
            lines.append(f"  … and {len(rest)} more")
            overwrites = [s for s in rest if isinstance(s, Move) and s.overwrite]
            if overwrites:
                lines.append("Also overwritten:")
                lines.extend(f"  {describe_step(s, self.bases)}" for s in overwrites)
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
    """Files the action found but did not touch, e.g. added after the preview."""
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


def _failures_text(failed: Sequence[StepFailure], bases: Sequence[Path]) -> str:
    return "\n".join(f"{describe_step(f.step, bases)}: {f.reason}" for f in failed)


# ---------------------------------------------------------------------------
# Action base
# ---------------------------------------------------------------------------


class Action(ABC):
    """Template method: public prepare/execute never raise.

    Subclasses implement _prepare / _execute. An action executes only a plan
    prepared for its own request.
    """

    action: ClassVar[NodeAction]

    def __init__(self, request: ActionRequest | None) -> None:
        self.request = request or ActionRequest(self.action, "")

    def log_context(self) -> dict[str, object]:
        return {"node_id": self.request.node_id}

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
        action_name = type(self).__name__
        ctx = self.log_context()
        try:
            result = self._prepare()
        except Exception:
            log.exception("action_prepare", action=action_name, **ctx)
            return ActionResult("failed", "Internal error", traceback.format_exc())

        if isinstance(result, ActionPlan):
            log.info(
                "action_prepare",
                action=action_name,
                outcome="plan",
                fingerprint=result.fingerprint,
                steps=len(result.steps),
                **ctx,
            )
        else:
            log.info(
                "action_prepare",
                action=action_name,
                outcome=result.outcome,
                message=result.message,
                **ctx,
            )
        return result

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        action_name = type(self).__name__
        ctx = self.log_context()
        if plan.request != self.request:
            result = _refused("Plan was prepared for another request")
        else:
            try:
                result = self._execute(plan)
            except Exception:
                log.exception("action_execute", action=action_name, **ctx)
                result = ExecutionResult(
                    "failed", "Internal error", traceback.format_exc()
                )
        result = replace(result, fingerprint=plan.fingerprint)
        log_method = log.info if result.success else log.warning
        log_method(
            "action_execute",
            action=action_name,
            outcome=result.outcome,
            message=result.message,
            done=len(result.done),
            failed=len(result.failed),
            **ctx,
        )
        return result

    @abstractmethod
    def _prepare(self) -> ActionPlan | ActionResult: ...

    @abstractmethod
    def _execute(self, plan: ActionPlan) -> ExecutionResult: ...


def _moves(plan: ActionPlan) -> list[Move]:
    return [step for step in plan.steps if isinstance(step, Move)]


def _run_moves(
    moves: Sequence[Move], *, replace_existing: bool = False
) -> tuple[tuple[Step, ...], tuple[StepFailure, ...]]:
    report = move_files(((m.source, m.target) for m in moves), replace=replace_existing)
    by_pair = {(m.source, m.target): m for m in moves}
    done = tuple(by_pair[pair] for pair in report.done)
    failed = tuple(
        StepFailure(by_pair[(src, dst)], reason) for src, dst, reason in report.failed
    )
    return done, failed


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


def _find_tidy_conflicts(
    moves: Sequence[tuple[Path, Path]],
) -> list[tuple[Path, Path]]:
    """Return moves that would overwrite an existing file or another move's target.

    Checked at prepare and again at execute so the user sees conflicts before
    confirming and late arrivals on disk cannot silently replace files.
    """
    conflicts: list[tuple[Path, Path]] = []
    seen_dst: dict[Path, Path] = {}

    for src, dst in moves:
        if dst in seen_dst and seen_dst[dst] != src:
            conflicts.append((src, dst))
        else:
            seen_dst[dst] = src

        if (
            dst.exists()
            and dst.resolve() != src.resolve()
            and (src, dst) not in conflicts
        ):
            conflicts.append((src, dst))

    return conflicts


def _format_move_lines(
    pairs: Sequence[tuple[Path, Path]], source_root: Path, target_root: Path
) -> str:
    return "\n".join(
        f"{src.relative_to(source_root)}\n\t→ {dst.relative_to(target_root)}"
        for src, dst in pairs
    )


def _format_extension_stats(paths: Sequence[Path]) -> list[str]:
    counts = Counter(f".{_file_extension(p)}" for p in paths)
    return [f"  {ext}: {n}" for ext, n in sorted(counts.items())]


class TidyAction(Action):
    action = NodeAction.TIDY

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

        conflicts = _find_tidy_conflicts(moves)
        if conflicts:
            return ActionResult(
                "refused",
                f"Tidy blocked: {len(conflicts)} file conflict(s)",
                _format_move_lines(conflicts, folder_path, folder_path),
            )

        photos = [src for src, dst in moves if dst.parent.name == PHOTOS_FOLDER]
        videos = [src for src, dst in moves if dst.parent.name == VIDEOS_FOLDER]
        notes = [f"Folder: {folder_path}", f"Photos to move: {len(photos)}"]
        notes += _format_extension_stats(photos)
        notes.append(f"Videos to move: {len(videos)}")
        notes += _format_extension_stats(videos)
        return self._plan(
            f"Tidy {len(moves)} files",
            [Move(src, dst) for src, dst in moves],
            notes,
            [folder_path],
        )

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return _refused(f"Not a directory: {folder_path}")

        moves = _moves(plan)
        conflicts = _find_tidy_conflicts([(m.source, m.target) for m in moves])
        if conflicts:
            return _refused(
                f"Tidy blocked: {len(conflicts)} file conflict(s)",
                _format_move_lines(conflicts, folder_path, folder_path),
            )

        done, failed = _run_moves(moves)
        if failed:
            return ExecutionResult(
                "failed",
                f"Tidied {len(done)} of {len(moves)} files",
                _failures_text(failed, plan.bases),
                done=done,
                failed=failed,
                rescan_node_path=folder_path,
                node_path=folder_path,
            )
        return ExecutionResult(
            "ok",
            f"Tidied {len(done)} files",
            done=done,
            rescan_node_path=folder_path,
            node_path=folder_path,
        )


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


class ArchiveAction(Action):
    action = NodeAction.ARCHIVE

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

    def _conflict_details(self, pairs: Sequence[tuple[Path, Path]]) -> str:
        return _format_move_lines(pairs, self._darkroom_path, self._archive_path)

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

        if duplicates:
            return ActionResult(
                "refused",
                f"Archive blocked: {len(duplicates)} file conflict(s) "
                "already in archive",
                self._conflict_details(duplicates),
            )
        if not leaves:
            return ActionResult("noop", "Nothing to archive", f"Folder: {folder_path}")

        source = folder_path.resolve()
        target = target_dir.resolve()
        steps = [Move(leaf, target / leaf.relative_to(source)) for leaf in leaves]
        return self._plan(
            f"Archive {len(steps)} files",
            steps,
            [f"From: {source}", f"To:   {target}"],
            [source, target],
        )

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        if problem := self._unavailable_root():
            return _refused(problem)
        folder_path = self._folder_path
        if not folder_path.is_dir():
            return _refused(f"Folder does not exist: {folder_path}")

        moves = _moves(plan)
        conflicts = [
            (m.source, m.target)
            for m in moves
            if m.target.exists() or m.target.is_symlink()
        ]
        if conflicts:
            return _refused(
                f"Archive blocked: {len(conflicts)} file conflict(s) "
                "already in archive",
                self._conflict_details(conflicts),
            )

        done, failed = _run_moves(moves)
        # Removing emptied folders is cleanup, not a planned step: a folder
        # held open (e.g. a shell's current folder on Windows) stays.
        try:
            prune_empty_dirs(folder_path)
        except OSError as e:
            kept = f"Emptied folders not removed: {e}"
        else:
            kept = None
        left = tuple(collect_leaf_paths(folder_path)) if folder_path.is_dir() else ()
        message = f"Archived {len(done)} of {len(moves)} file(s)"
        if left:
            message += f"; {len(left)} file(s) left in the darkroom"
        details = [_failures_text(failed, plan.bases)] if failed else []
        if kept:
            details.append(kept)
        return ExecutionResult(
            "failed" if failed else "ok",
            message,
            "\n".join(details) or None,
            done=done,
            failed=failed,
            left=left,
            rescan_node_path=folder_path.parent,
            node_path=folder_path if folder_path.is_dir() else None,
        )


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


class PublishAction(Action):
    action = NodeAction.PUBLISH

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
        steps = [
            Move(f, target_dir / f.name, overwrite=(target_dir / f.name).exists())
            for f in files
        ]
        overwrites = sum(1 for s in steps if s.overwrite)
        notes = [
            f"From: {publish_dir}",
            f"To:   {target_dir}",
            f"New: {len(steps) - overwrites}, overwritten: {overwrites}",
        ]
        return self._plan(
            f"Publish {len(steps)} files", steps, notes, [publish_dir, target_dir]
        )

    def _execute(self, plan: ActionPlan) -> ExecutionResult:
        if problem := self._unavailable_root():
            return _refused(problem)
        moves = _moves(plan)
        done, failed = _run_moves(moves, replace_existing=True)
        if failed:
            return ExecutionResult(
                "failed",
                f"Published {len(done)} of {len(moves)} files",
                _failures_text(failed, plan.bases),
                done=done,
                failed=failed,
                rescan_node_path=self._batch_path,
                node_path=self._batch_path,
            )
        return ExecutionResult(
            "ok",
            f"Published {len(done)} files to showroom",
            done=done,
            rescan_node_path=self._batch_path,
            node_path=self._batch_path,
        )


# ---------------------------------------------------------------------------
# New batch
# ---------------------------------------------------------------------------


class NewBatchAction(Action):
    action = NodeAction.NEW_BATCH

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

    def log_context(self) -> dict[str, object]:
        return {"device": self._device, "date": self._date, "title": self._title}

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
