"""Library checks several actions share: roots, batches."""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.core.library import DarkroomBatch, recognize_darkroom_batch

from ._base import ActionRefusedError


def require_available_roots(**roots: Path) -> None:
    """Refuse when a library root is not a folder, e.g. an unplugged drive.

    Actions check their roots when they prepare: a root validated earlier may
    be gone by now.

    Args:
        roots: The roots the action needs, by name (``darkroom=...``).

    Raises:
        ActionRefusedError: The first root that is not a folder, named.
    """
    for name, root in roots.items():
        if not root.is_dir():
            raise ActionRefusedError(
                f"{name.capitalize()} folder is not available: {root}"
            )


def recognize_batch(darkroom_root: Path, path: Path) -> DarkroomBatch | None:
    """The batch *path* is in, or ``None`` when it is not in a valid batch."""
    try:
        return recognize_darkroom_batch(darkroom_root, path)
    except ValueError:
        return None


def is_batch_folder(darkroom_root: Path, path: Path) -> bool:
    """True if *path* sits where a batch does: ``DEVICE/YEAR/BATCH``."""
    try:
        return len(path.relative_to(darkroom_root).parts) == 3
    except ValueError:
        return False
