"""Pure path mapping between working and destination folder layouts."""

from pathlib import Path
from typing import Literal

Layout = Literal["device-first", "batch-first"]


def translate_path(
    path: Path,
    *,
    from_root: Path,
    to_root: Path,
    from_layout: Layout,
    to_layout: Layout,
) -> Path:
    """Reorder the device/year/batch prefix and preserve the selected tail.

    Paths need not exist. Organizational paths above a device's batch have
    no unique counterpart in the other layout and are rejected.
    """
    parts = path.relative_to(from_root).parts
    if len(parts) < 3 or ".." in parts:
        raise ValueError("Expected a device/year/batch path without traversal")
    if from_layout == to_layout:
        return to_root.joinpath(*parts)
    if from_layout == "device-first":
        device, year, batch, *tail = parts
        return to_root.joinpath(year, batch, device, *tail)
    year, batch, device, *tail = parts
    return to_root.joinpath(device, year, batch, *tail)
