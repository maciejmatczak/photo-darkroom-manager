"""New batch: create a batch, and its device and year when missing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from photo_darkroom_manager.core.jobs import Job
from photo_darkroom_manager.core.library import (
    PUBLISH_FOLDER,
    BatchFolderName,
    format_validation_error,
    validate_device_name,
)

from ._base import ActionPlan, ActionRefusedError, ActionResult, Answers
from ._library import require_available_roots


@dataclass(frozen=True)
class NewBatchPlan(ActionPlan):
    """What creating a batch will create; it asks no questions.

    Args:
        darkroom_root: The darkroom root; with the inputs below, what
            prepares it again.
        device: The device name given.
        date: The batch date given, ``YYYY-MM[-DD]``.
        title: The batch title given, or ``None``.
        batch_folder: The batch folder to create.
        folders_to_create: Every missing folder, parents first: device,
            year, the batch and its ``PUBLISH/``.
    """

    darkroom_root: Path
    device: str
    date: str
    title: str | None
    batch_folder: Path
    folders_to_create: tuple[Path, ...]

    @property
    def nothing_to_do(self) -> bool:
        return False


@dataclass(frozen=True, kw_only=True)
class NewBatchResult(ActionResult):
    """What creating a batch did.

    Args:
        batch_folder: The batch folder, created or not.
        created: The folders created, parents first.
    """

    batch_folder: Path
    created: tuple[Path, ...] = ()


def prepare(
    darkroom_root: Path, device: str, *, date: str, title: str | None = None
) -> NewBatchPlan:
    """Plan creating a batch dated *date* for *device*; change nothing.

    Raises:
        ActionRefusedError: The darkroom is unavailable, a name is invalid,
            a file stands where a folder must go, the batch would land
            outside the darkroom, or it exists.
    """
    require_available_roots(darkroom=darkroom_root)
    try:
        device_name = validate_device_name(device)
        name = BatchFolderName.from_date(date, title)
    except ValidationError as error:
        raise ActionRefusedError(format_validation_error(error)) from None
    except ValueError as error:
        raise ActionRefusedError(str(error)) from None
    device_folder = darkroom_root / device_name
    year_folder = device_folder / name.year
    batch_folder = year_folder / name.folder_name
    for folder in (device_folder, year_folder):
        if folder.exists() and not folder.is_dir():
            raise ActionRefusedError(f"Not a folder: {folder}")
    if not batch_folder.resolve().is_relative_to(darkroom_root.resolve()):
        raise ActionRefusedError("Batch path must remain inside darkroom")
    if batch_folder.exists():
        raise ActionRefusedError(f"Batch folder already exists: {batch_folder}")
    folders = (device_folder, year_folder, batch_folder, batch_folder / PUBLISH_FOLDER)
    return NewBatchPlan(
        darkroom_root,
        device,
        date,
        title,
        batch_folder,
        tuple(f for f in folders if not f.exists()),
    )


def run(plan: NewBatchPlan, answers: Answers, job: Job) -> NewBatchResult:
    """Create the folders; one step, so no progress and no cancel.

    A batch folder that appeared since the plan was checked is left as it
    is, reported as failed.
    """
    created: list[Path] = []
    for folder in plan.folders_to_create:
        try:
            folder.mkdir(exist_ok=folder != plan.batch_folder)
        except OSError as error:
            return NewBatchResult(
                outcome="failed",
                message=f"Could not create folder: {folder}: {error}",
                batch_folder=plan.batch_folder,
                created=tuple(created),
            )
        created.append(folder)
        job.log.info("step_done", folder=str(folder))
    return NewBatchResult(
        outcome="ok",
        message=f"Created batch: {plan.batch_folder.name}",
        batch_folder=plan.batch_folder,
        created=tuple(created),
    )
