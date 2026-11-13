"""Publish: move a batch's ``PUBLISH/`` files to its showroom device folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from photo_darkroom_manager.core.jobs import Job, JobCancelled
from photo_darkroom_manager.core.library import PUBLISH_FOLDER
from photo_darkroom_manager.core.paths import translate_path

from ._base import ActionPlan, ActionRefusedError, ActionResult, Answers, Question
from ._library import recognize_batch, require_available_roots
from ._moves import (
    CONFLICT_EXISTS,
    ConflictAnswer,
    FileMove,
    MoveReport,
    moves_message,
    run_moves,
    target_taken,
)

EXISTING_QUESTION = "existing"
"""The question a republish asks about files already in the showroom:
``replace`` or ``skip``."""


@dataclass(frozen=True)
class PublishPlan(ActionPlan):
    """What publishing a batch will move to the showroom.

    Args:
        batch: The batch published; also the input to prepare it again.
        publish_folder: Its ``PUBLISH/`` folder, whose files are published.
        target: The batch's device folder in the showroom.
        darkroom_root: The darkroom root the batch is under.
        showroom_root: The showroom root the target is under.
        moves: Files new to the showroom.
        replacements: Files already in the showroom; replaced or skipped as
            the user answers.
    """

    batch: Path
    publish_folder: Path
    target: Path
    darkroom_root: Path
    showroom_root: Path
    moves: tuple[FileMove, ...]
    replacements: tuple[FileMove, ...] = ()

    @property
    def nothing_to_do(self) -> bool:
        return not self.moves and not self.replacements


@dataclass(frozen=True, kw_only=True)
class PublishResult(ActionResult):
    """What publishing moved.

    Args:
        batch: The batch published.
        moves: What happened to each file; ``replaced`` lists the files put
            in place of old ones.
    """

    batch: Path
    moves: MoveReport


def prepare(batch: Path, darkroom_root: Path, showroom_root: Path) -> PublishPlan:
    """Plan publishing the files directly in *batch*'s ``PUBLISH/``; change nothing.

    Raises:
        ActionRefusedError: A root is unavailable, *batch* is not a batch,
            or ``PUBLISH/`` is missing or holds folders.
    """
    require_available_roots(darkroom=darkroom_root, showroom=showroom_root)
    recognized = recognize_batch(darkroom_root, batch)
    if recognized is None:
        raise ActionRefusedError("Could not recognize batch")
    publish_folder = batch / PUBLISH_FOLDER
    if not publish_folder.is_dir():
        raise ActionRefusedError("PUBLISH directory does not exist")
    entries = sorted(publish_folder.iterdir())
    if any(entry.is_dir() for entry in entries):
        raise ActionRefusedError("PUBLISH directory contains subdirectories")
    target = translate_path(
        recognized.batch_path,
        from_area="darkroom",
        from_root=darkroom_root,
        to_area="showroom",
        to_root=showroom_root,
    )
    moves: list[FileMove] = []
    replacements: list[FileMove] = []
    for file in (entry for entry in entries if entry.is_file()):
        if target_taken(file, target / file.name):
            replacements.append(FileMove(file, target / file.name, CONFLICT_EXISTS))
        else:
            moves.append(FileMove(file, target / file.name))
    questions = {}
    if replacements:
        questions[EXISTING_QUESTION] = Question(
            f"{len(replacements)} file(s) already in the showroom",
            ("replace", "skip"),
        )
    return PublishPlan(
        batch,
        publish_folder,
        target,
        darkroom_root,
        showroom_root,
        tuple(moves),
        tuple(replacements),
        questions=questions,
    )


def run(plan: PublishPlan, answers: Answers, job: Job) -> PublishResult:
    """Move the files; replace or skip the ones already there as answered.

    A replaced file is put in place only once the new one is complete.

    Raises:
        JobCancelled: A cancel stopped the moves; its result is what was done.
    """
    answer = answers.get(EXISTING_QUESTION)
    report = run_moves(
        plan.moves,
        plan.replacements,
        on_conflict=cast(ConflictAnswer, answer) if answer else None,
        job=job,
    )
    planned = len(plan.moves) + len(plan.replacements)
    result = PublishResult(
        outcome=report.outcome,
        message=moves_message("Published", report, planned),
        batch=plan.batch,
        moves=report,
    )
    if report.cancelled:
        raise JobCancelled(result)
    return result
