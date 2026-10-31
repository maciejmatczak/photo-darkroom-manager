"""Pure path translation between library areas."""

from pathlib import Path
from typing import Literal

Area = Literal["darkroom", "archive", "showroom"]


# Darkroom is device-first (DEVICE/YEAR/BATCH); destinations are batch-first
# (YEAR/BATCH/DEVICE).
_DEVICE_FIRST: frozenset[Area] = frozenset({"darkroom"})


def translate_path(
    path: Path,
    *,
    from_area: Area,
    from_root: Path,
    to_area: Area,
    to_root: Path,
) -> Path:
    """Map *path* in one area to the matching path in another area.

    Reorders the device/year/batch prefix as the areas' layouts require and
    preserves the selected tail. Paths need not exist. Organizational paths
    above a device's batch have no unique counterpart and are rejected.
    """
    parts = path.relative_to(from_root).parts
    if len(parts) < 3 or ".." in parts:
        raise ValueError("Expected a device/year/batch path without traversal")
    from_device_first = from_area in _DEVICE_FIRST
    if from_device_first == (to_area in _DEVICE_FIRST):
        return to_root.joinpath(*parts)
    if from_device_first:
        device, year, batch, *tail = parts
        return to_root.joinpath(year, batch, device, *tail)
    year, batch, device, *tail = parts
    return to_root.joinpath(device, year, batch, *tail)
