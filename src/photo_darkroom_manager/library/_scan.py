"""Read node facts of a darkroom subtree from disk."""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.library.layout import NodeKind, child_kind
from photo_darkroom_manager.library.media import (
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    is_untidy,
)
from photo_darkroom_manager.library.tree import (
    FileCounts,
    NodeFacts,
    NodeId,
    NodeIssue,
    child_id,
)

_TIDY_KINDS: frozenset[NodeKind] = frozenset({"batch", "subfolder"})


def _count_files(directory: Path) -> FileCounts:
    """Count image, video, and other files directly in a directory."""
    images = 0
    videos = 0
    others = 0
    try:
        for item in directory.iterdir():
            if not item.is_file():
                continue
            ext = item.suffix.lstrip(".").lower()
            if ext in PHOTO_EXTENSIONS:
                images += 1
            elif ext in VIDEO_EXTENSIONS:
                videos += 1
            else:
                others += 1
    except OSError:
        pass
    return FileCounts(images, videos, others)


def _subfolders(directory: Path) -> list[Path]:
    try:
        return sorted(p for p in directory.iterdir() if p.is_dir())
    except OSError:
        return []


def scan_subtree(
    root: Path, node_id: NodeId, kind: NodeKind
) -> dict[NodeId, NodeFacts]:
    """Facts of the folder *node_id* (of *kind*) under *root* and below it."""
    facts: dict[NodeId, NodeFacts] = {}
    _scan(root / node_id if node_id else root, node_id, kind, facts)
    return facts


def _scan(
    path: Path, node_id: NodeId, kind: NodeKind, out: dict[NodeId, NodeFacts]
) -> None:
    issues: set[NodeIssue] = set()
    if kind in _TIDY_KINDS and is_untidy(path):
        issues.add("untidy")
    children: list[NodeId] = []
    for sub in _subfolders(path):
        sub_kind = child_kind(kind, sub.name)
        if sub_kind is None:
            continue
        sub_id = child_id(node_id, sub.name)
        _scan(sub, sub_id, sub_kind, out)
        children.append(sub_id)
    out[node_id] = NodeFacts(
        kind=kind,
        stats=_count_files(path),
        own_issues=frozenset(issues),
        children=tuple(children),
    )
