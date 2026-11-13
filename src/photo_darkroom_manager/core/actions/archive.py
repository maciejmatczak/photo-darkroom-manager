"""Archive: move a batch or subfolder to its mapped place in the archive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from photo_darkroom_manager.core.file_utils import (
    collect_leaf_paths,
    preview_merge_into_archive,
    prune_empty_dirs,
)
from photo_darkroom_manager.core.jobs import Job, JobCancelled
from photo_darkroom_manager.core.paths import translate_path

from ._base import ActionPlan, ActionRefusedError, ActionResult, Answers, Question
from ._library import recognize_batch, require_available_roots
from ._moves import CONFLICT_EXISTS, FileMove, MoveReport, moves_message, run_moves

EXISTING_QUESTION = "existing"
"""The question an archive with files already archived asks; one choice:
``skip``. A file already in the archive is never overwritten."""


@dataclass(frozen=True)
class ArchivePlan(ActionPlan):
    """What archiving a folder will move, and where.

    Args:
        source: The batch or subfolder archived; also the input to prepare
            it again.
        target: Its mapped folder in the archive.
        darkroom_root: The darkroom root the source is under.
        archive_root: The archive root the target is under.
        moves: Files whose target in the archive is free.
        conflicts: Files already in the archive; they stay in the darkroom.
    """

    source: Path
    target: Path
    darkroom_root: Path
    archive_root: Path
    moves: tuple[FileMove, ...]
    conflicts: tuple[FileMove, ...] = ()

    @property
    def nothing_to_do(self) -> bool:
        return not self.moves and not self.conflicts


@dataclass(frozen=True, kw_only=True)
class ArchiveResult(ActionResult):
    """What archiving moved and what is left in the darkroom.

    Args:
        source: The folder archived.
        moves: What happened to each planned file.
        remaining: Files still in the source folder afterwards.
        source_removed: True when the source folder was emptied and removed.
        cleanup_problem: Why emptied folders were not all removed (e.g. one
            is held open); ``None`` when they were.
    """

    source: Path
    moves: MoveReport
    remaining: tuple[Path, ...] = ()
    source_removed: bool = False
    cleanup_problem: str | None = None


def prepare(source: Path, darkroom_root: Path, archive_root: Path) -> ArchivePlan:
    """Plan archiving *source*, a batch or a folder in one; change nothing.

    The source lands at its mapped archive path, keeping its nested tail and
    merging into folders already there.

    Raises:
        ActionRefusedError: A root is unavailable, *source* is not in a
            batch, or it is not a folder.
    """
    require_available_roots(darkroom=darkroom_root, archive=archive_root)
    if recognize_batch(darkroom_root, source) is None:
        raise ActionRefusedError("Could not recognize batch for this path")
    target = translate_path(
        source,
        from_area="darkroom",
        from_root=darkroom_root,
        to_area="archive",
        to_root=archive_root,
    )
    try:
        leaves, duplicates = preview_merge_into_archive(source, target)
    except ValueError as error:
        raise ActionRefusedError(str(error)) from None
    resolved_source, resolved_target = source.resolve(), target.resolve()
    taken = {src for src, _ in duplicates}
    moves = tuple(
        FileMove(leaf, resolved_target / leaf.relative_to(resolved_source))
        for leaf in leaves
        if leaf not in taken
    )
    conflicts = tuple(FileMove(src, dst, CONFLICT_EXISTS) for src, dst in duplicates)
    questions = {}
    if conflicts:
        questions[EXISTING_QUESTION] = Question(
            f"{len(conflicts)} file(s) already in the archive stay in the darkroom",
            ("skip",),
        )
    return ArchivePlan(
        source,
        resolved_target,
        darkroom_root,
        archive_root,
        moves,
        conflicts,
        questions=questions,
    )


def run(plan: ArchivePlan, answers: Answers, job: Job) -> ArchiveResult:
    """Move the planned files, then remove the folders left empty.

    Files already in the archive, planned or found while running, are
    skipped and stay in the darkroom; none is overwritten.

    Raises:
        JobCancelled: A cancel stopped the moves; its result is what was done.
    """
    report = run_moves(plan.moves, plan.conflicts, on_conflict="skip", job=job)
    source = plan.source
    try:
        prune_empty_dirs(source)
    except OSError as error:
        cleanup_problem: str | None = f"Emptied folders not removed: {error}"
    else:
        cleanup_problem = None
    remaining = tuple(collect_leaf_paths(source)) if source.is_dir() else ()
    planned = len(plan.moves) + len(plan.conflicts)
    message = moves_message("Archived", report, planned)
    if remaining:
        message += f"; {len(remaining)} file(s) left in the darkroom"
    result = ArchiveResult(
        outcome=report.outcome,
        message=message,
        source=source,
        moves=report,
        remaining=remaining,
        source_removed=not source.is_dir(),
        cleanup_problem=cleanup_problem,
    )
    if report.cancelled:
        raise JobCancelled(result)
    return result
