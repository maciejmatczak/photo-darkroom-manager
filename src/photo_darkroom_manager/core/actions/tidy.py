"""Tidy: move misplaced photos and videos into their ``PHOTOS/`` or ``VIDEOS/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from photo_darkroom_manager.core.jobs import Job, JobCancelled
from photo_darkroom_manager.core.library import (
    PHOTOS_FOLDER,
    VIDEOS_FOLDER,
    collect_files_to_tidy,
    is_file_a_photo,
    is_file_a_video,
)

from ._base import ActionPlan, ActionRefusedError, ActionResult, Answers, Question
from ._moves import (
    CONFLICT_EXISTS,
    CONFLICT_SAME_TARGET,
    FileMove,
    MoveReport,
    moves_message,
    run_moves,
    target_taken,
)

CONFLICTS_QUESTION = "conflicts"
"""The question a tidy with conflicts asks; its one choice is ``skip``."""


@dataclass(frozen=True)
class TidyPlan(ActionPlan):
    """What tidying a folder will move.

    Args:
        folder: The folder tidied, with all its subfolders; also the input to
            prepare it again.
        moves: Misplaced files and the free target each one goes to.
        conflicts: Misplaced files that cannot move: their target holds
            another file, or another file needs the same target.
    """

    folder: Path
    moves: tuple[FileMove, ...]
    conflicts: tuple[FileMove, ...] = ()

    @property
    def nothing_to_do(self) -> bool:
        return not self.moves and not self.conflicts


@dataclass(frozen=True, kw_only=True)
class TidyResult(ActionResult):
    """What tidying moved.

    Args:
        folder: The folder tidied.
        moves: What happened to each planned file.
    """

    folder: Path
    moves: MoveReport


def _tidy_target(source: Path) -> Path:
    """Where a misplaced media file goes: its folder's or sibling bucket."""
    parent = source.parent
    extension = source.suffix.lstrip(".").lower()
    if parent.name == PHOTOS_FOLDER and is_file_a_video([extension]):
        return parent.parent / VIDEOS_FOLDER / source.name
    if parent.name == VIDEOS_FOLDER and is_file_a_photo([extension]):
        return parent.parent / PHOTOS_FOLDER / source.name
    if is_file_a_video([extension]):
        return parent / VIDEOS_FOLDER / source.name
    return parent / PHOTOS_FOLDER / source.name


def prepare(folder: Path) -> TidyPlan:
    """Plan tidying *folder* and its subfolders; change nothing.

    Each misplaced file goes to the ``PHOTOS/`` or ``VIDEOS/`` of its own
    folder (``iPhone/IMG.jpg`` to ``iPhone/PHOTOS/``), or to the sibling
    bucket when it sits in the wrong one.

    Raises:
        ActionRefusedError: *folder* is not a folder.
    """
    if not folder.is_dir():
        raise ActionRefusedError(f"Not a directory: {folder}")
    photos, videos = collect_files_to_tidy(folder, recursive=True)
    moves: list[FileMove] = []
    conflicts: list[FileMove] = []
    seen_targets: set[Path] = set()
    for source in photos + videos:
        target = _tidy_target(source)
        if target in seen_targets:
            conflicts.append(FileMove(source, target, CONFLICT_SAME_TARGET))
        elif target_taken(source, target):
            conflicts.append(FileMove(source, target, CONFLICT_EXISTS))
        else:
            moves.append(FileMove(source, target))
        seen_targets.add(target)
    questions = {}
    if conflicts:
        questions[CONFLICTS_QUESTION] = Question(
            f"{len(conflicts)} file(s) cannot be moved: their target is taken",
            ("skip",),
        )
    return TidyPlan(folder, tuple(moves), tuple(conflicts), questions=questions)


def run(plan: TidyPlan, answers: Answers, job: Job) -> TidyResult:
    """Move the planned files; skip conflicts as the user answered.

    Raises:
        JobCancelled: A cancel stopped the moves; its result is what was done.
    """
    report = run_moves(
        plan.moves,
        plan.conflicts,
        on_conflict="skip" if CONFLICTS_QUESTION in answers else None,
        job=job,
    )
    planned = len(plan.moves) + len(plan.conflicts)
    result = TidyResult(
        outcome=report.outcome,
        message=moves_message("Tidied", report, planned),
        folder=plan.folder,
        moves=report,
    )
    if report.cancelled:
        raise JobCancelled(result)
    return result
