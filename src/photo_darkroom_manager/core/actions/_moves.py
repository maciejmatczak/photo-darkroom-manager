"""Moving planned files, for the actions that move them (tidy, archive, publish).

An action plans its moves and the conflicts it found; :func:`run_moves`
re-checks every target, follows the user's answer for conflicts, reports
progress and each move to the job, stops between files on a cancel and
returns a :class:`MoveReport`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from photo_darkroom_manager.core.file_utils import MoveOutcome, move_files
from photo_darkroom_manager.core.jobs import Job

from ._base import Outcome

ConflictAnswer = Literal["skip", "replace"]
"""What the user chose for files whose target is taken."""

CONFLICT_EXISTS = "target already exists"
CONFLICT_SAME_TARGET = "same target as another file"


@dataclass(frozen=True)
class FileMove:
    """One file and where it goes; *reason* says why it failed or was skipped.

    Args:
        source: The file to move.
        target: Where it goes.
        reason: Why a move failed or was skipped, or why a planned move
            conflicts; ``None`` for a move that is free or was done.
    """

    source: Path
    target: Path
    reason: str | None = None


@dataclass(frozen=True)
class MoveReport:
    """What moving the planned files did.

    Args:
        moved: Files moved to a free target.
        replaced: Files moved in place of an existing file, by the user's
            answer.
        failed: Files that could not be moved, with the reason; each stays
            where it was.
        skipped: Files left where they are because their target is taken.
        left: Files a cancel left undone.
    """

    moved: tuple[FileMove, ...] = ()
    replaced: tuple[FileMove, ...] = ()
    failed: tuple[FileMove, ...] = ()
    skipped: tuple[FileMove, ...] = ()
    left: tuple[FileMove, ...] = ()

    @property
    def cancelled(self) -> bool:
        """True when a cancel stopped the moves before the last file."""
        return bool(self.left)

    @property
    def outcome(self) -> Outcome:
        if self.cancelled:
            return "cancelled"
        return "failed" if self.failed else "ok"

    @property
    def done(self) -> int:
        """Files moved, replacements included."""
        return len(self.moved) + len(self.replaced)


def target_taken(source: Path, target: Path) -> bool:
    """True if *target* holds a file other than *source* itself."""
    if not (target.exists() or target.is_symlink()):
        return False
    try:
        return not target.samefile(source)
    except OSError:
        return True


def _log_move(job: Job, move: FileMove, status: str) -> None:
    """Write one finished, skipped or failed move to *job*'s log."""
    fields = {"source": str(move.source), "target": str(move.target)}
    if status == "done":
        job.log.info("step_done", **fields)
    elif status == "skipped":
        job.log.info("step_skipped", reason=move.reason, **fields)
    else:
        job.log.warning("step_failed", reason=move.reason, **fields)


def run_moves(
    moves: Sequence[FileMove],
    conflicts: Sequence[FileMove],
    *,
    on_conflict: ConflictAnswer | None,
    job: Job,
) -> MoveReport:
    """Move the planned files; follow *on_conflict* for taken targets.

    Every free move's target is checked again first: one taken since the
    plan is a conflict like the planned ones. With ``replace``, files whose
    target exists replace it (two files for one target are still skipped);
    otherwise conflicting files are skipped. A target taken while moving is
    skipped the same way. *job* hears each move and how far the run got; a
    cancel stops the run between files.

    Args:
        moves: Planned moves to a free target.
        conflicts: Planned moves whose target was taken, with the reason.
        on_conflict: The user's answer for conflicts; ``None`` when the plan
            asked nothing, which skips any found while running.
        job: The job the moves belong to.
    """
    free: list[FileMove] = []
    found: list[FileMove] = list(conflicts)
    for move in moves:
        if target_taken(move.source, move.target):
            found.append(FileMove(move.source, move.target, CONFLICT_EXISTS))
        else:
            free.append(move)

    def replaces(conflict: FileMove) -> bool:
        return on_conflict == "replace" and conflict.reason == CONFLICT_EXISTS

    replacing = [FileMove(c.source, c.target) for c in found if replaces(c)]
    skipped = [c for c in found if not replaces(c)]
    for conflict in skipped:
        _log_move(job, conflict, "skipped")

    moved: list[FileMove] = []
    replaced: list[FileMove] = []
    failed: list[FileMove] = []
    left: list[FileMove] = []
    total = len(free) + len(replacing)
    finished = 0

    def on_move(outcome: MoveOutcome) -> None:
        nonlocal finished
        finished += 1
        move = FileMove(outcome.source, outcome.target, outcome.reason)
        _log_move(job, move, outcome.status)
        job.progress(finished, total, outcome.source.name)

    job.progress(0, total, None)
    for batch, replace_existing, done in (
        (free, False, moved),
        (replacing, True, replaced),
    ):
        if not batch:
            continue
        if left:
            left.extend(batch)
            continue
        report = move_files(
            ((m.source, m.target) for m in batch),
            replace=replace_existing,
            stop=lambda: job.cancelled,
            on_move=on_move,
        )
        done.extend(FileMove(src, dst) for src, dst in report.done)
        failed.extend(FileMove(src, dst, reason) for src, dst, reason in report.failed)
        skipped.extend(
            FileMove(src, dst, CONFLICT_EXISTS) for src, dst in report.skipped
        )
        left.extend(FileMove(src, dst) for src, dst in report.left)
    return MoveReport(
        moved=tuple(moved),
        replaced=tuple(replaced),
        failed=tuple(failed),
        skipped=tuple(skipped),
        left=tuple(left),
    )


def moves_message(verb: str, report: MoveReport, planned: int) -> str:
    """One line for a move run, e.g. ``Archived 90 of 100 file(s); 10 skipped``."""
    message = f"{verb} {report.done} of {planned} file(s)"
    if report.skipped:
        message += f"; {len(report.skipped)} skipped as conflicts"
    if report.cancelled:
        message += f"; cancelled with {len(report.left)} not moved"
    return message
