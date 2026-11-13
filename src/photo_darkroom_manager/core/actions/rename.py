"""Rename: give a batch a new date or title; omitted parts are kept."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from photo_darkroom_manager.core.jobs import Job
from photo_darkroom_manager.core.library import BatchFolderName, format_validation_error

from ._base import ActionPlan, ActionRefusedError, ActionResult, Answers
from ._library import is_batch_folder, require_available_roots


@dataclass(frozen=True)
class RenamePlan(ActionPlan):
    """What renaming a batch will change; it asks no questions.

    Args:
        folder: The batch folder renamed; with the inputs below, what
            prepares it again.
        darkroom_root: The darkroom root the batch is under.
        date: The new date given, or ``None`` to keep the current one.
        title: The new title given, or ``None`` to keep the current one.
        clear_title: True to drop the title.
        new_folder: The folder's path after the rename.
    """

    folder: Path
    darkroom_root: Path
    date: str | None
    title: str | None
    clear_title: bool
    new_folder: Path

    @property
    def nothing_to_do(self) -> bool:
        return self.new_folder.name == self.folder.name


@dataclass(frozen=True, kw_only=True)
class RenameResult(ActionResult):
    """What renaming did.

    Args:
        folder: Where the batch is now: the new folder, or the old one when
            the rename failed.
    """

    folder: Path


def _same_folder(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def _new_name(
    old_name: str, date: str | None, title: str | None, clear_title: bool
) -> str:
    try:
        current: BatchFolderName | None = BatchFolderName.from_str(old_name)
    except ValidationError:
        current = None
    if date is None and current is None:
        raise ActionRefusedError(
            f"Cannot read the date of '{old_name}'; give a new date"
        )
    if clear_title:
        new_title = None
    elif title is not None:
        new_title = title
    else:
        new_title = current.name if current is not None else None
    try:
        if date is not None:
            new = BatchFolderName.from_date(date, new_title)
        else:
            assert current is not None
            new = BatchFolderName(
                year=current.year,
                month=current.month,
                day=current.day,
                name=new_title,
            )
    except ValidationError as error:
        raise ActionRefusedError(format_validation_error(error)) from None
    return new.folder_name


def prepare(
    folder: Path,
    darkroom_root: Path,
    *,
    date: str | None = None,
    title: str | None = None,
    clear_title: bool = False,
) -> RenamePlan:
    """Plan renaming the batch *folder*; change nothing.

    Args:
        folder: The batch folder.
        darkroom_root: The darkroom root.
        date: New date, ``YYYY-MM[-DD]``; ``None`` keeps the current one.
        title: New title; ``None`` keeps the current one.
        clear_title: Drop the title.

    Raises:
        ActionRefusedError: The darkroom is unavailable, *folder* is not a
            batch, the new name is invalid or another folder has it.
    """
    require_available_roots(darkroom=darkroom_root)
    if not is_batch_folder(darkroom_root, folder):
        raise ActionRefusedError("Could not recognize batch")
    if not folder.is_dir():
        raise ActionRefusedError(f"Batch folder does not exist: {folder}")
    new_folder = folder.parent / _new_name(folder.name, date, title, clear_title)
    if new_folder.exists() and not _same_folder(folder, new_folder):
        raise ActionRefusedError(f"A folder named '{new_folder.name}' already exists")
    return RenamePlan(folder, darkroom_root, date, title, clear_title, new_folder)


def run(plan: RenamePlan, answers: Answers, job: Job) -> RenameResult:
    """Rename the folder; one step, so no progress and no cancel.

    A folder that took the new name since the plan was checked leaves the
    batch as it is, reported as failed.
    """
    folder, new_folder = plan.folder, plan.new_folder
    if new_folder.exists() and not _same_folder(folder, new_folder):
        return RenameResult(
            outcome="failed",
            message=f"A folder named '{new_folder.name}' already exists",
            folder=folder,
        )
    try:
        folder.rename(new_folder)
    except OSError as error:
        return RenameResult(
            outcome="failed",
            message=f"Could not rename {folder.name}: {error}",
            folder=folder,
        )
    job.log.info("step_done", source=str(folder), target=str(new_folder))
    return RenameResult(
        outcome="ok", message=f"Renamed to {new_folder.name}", folder=new_folder
    )
