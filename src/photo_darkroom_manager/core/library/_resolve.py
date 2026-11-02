"""Turn darkroom paths and typed ids into ids with the on-disk folder names."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from photo_darkroom_manager.core.library.tree import NodeId


class PathOutsideDarkroomError(ValueError):
    """A path given as a darkroom node is not inside the darkroom."""

    def __init__(self, path: Path, root: Path) -> None:
        super().__init__(f"path is outside the darkroom {root}: {path}")
        self.path = path
        self.root = root


def on_disk_name(names: Iterable[str], part: str) -> str:
    """*part* as spelled in *names*: exact, else the one case-insensitive match.

    Keeps *part* as typed when no single folder matches, so ids of folders
    that do not exist yet stay as the client wrote them.
    """
    folded = part.casefold()
    matches = []
    for name in names:
        if name == part:
            return part
        if name.casefold() == folded:
            matches.append(name)
    return matches[0] if len(matches) == 1 else part


def _folder_names(folder: Path) -> list[str]:
    try:
        return [p.name for p in folder.iterdir() if p.is_dir()]
    except OSError:
        return []


def canonical_id(root: Path, node_id: NodeId) -> NodeId:
    """*node_id* with each part spelled as the folder on disk under *root*.

    Symlinks are not followed; parts with no folder on disk stay as typed.
    """
    if not node_id:
        return ""
    folder = root
    parts: list[str] = []
    for part in node_id.split("/"):
        name = on_disk_name(_folder_names(folder), part)
        parts.append(name)
        folder = folder / name
    return "/".join(parts)


def resolve_path(root: Path, path: Path) -> NodeId:
    """Id of the darkroom folder at *path*; ``PathOutsideDarkroomError`` if outside.

    The path is made absolute and normalised (``.`` and ``..`` collapsed)
    without following symlinks, and compared with *root* ignoring case where
    the platform does.
    """
    root_parts = Path(os.path.normpath(os.path.abspath(root))).parts
    path_parts = Path(os.path.normpath(os.path.abspath(path))).parts
    head = path_parts[: len(root_parts)]
    if len(head) < len(root_parts) or [os.path.normcase(p) for p in head] != [
        os.path.normcase(p) for p in root_parts
    ]:
        raise PathOutsideDarkroomError(path, root)
    return canonical_id(root, "/".join(path_parts[len(root_parts) :]))
