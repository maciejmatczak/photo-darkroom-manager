"""Read node facts of a darkroom subtree from disk."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from photo_darkroom_manager.core.library.layout import NodeKind, child_kind, node_kind
from photo_darkroom_manager.core.library.media import (
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    is_untidy,
)
from photo_darkroom_manager.core.library.tree import (
    FileCounts,
    NodeFacts,
    NodeId,
    NodeIssue,
    child_id,
    parent_id,
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


Visit = Callable[[NodeId], None]


def scan_subtree(
    root: Path, node_id: NodeId, kind: NodeKind, *, visit: Visit | None = None
) -> dict[NodeId, NodeFacts]:
    """Facts of the folder *node_id* (of *kind*) under *root* and below it.

    *visit* is called with each folder's id before the folder is read; it
    may raise to stop the scan, which then returns nothing.
    """
    facts: dict[NodeId, NodeFacts] = {}
    _scan(root / node_id if node_id else root, node_id, kind, facts, visit)
    return facts


def scan_chain(root: Path, node_id: NodeId) -> dict[NodeId, NodeFacts]:
    """Stub facts of every ancestor of *node_id*, from the root down.

    Each ancestor's own files and issues come from one listing of its
    folder; its children are only the next folder on the path, so it is
    marked incomplete. Siblings' subtrees are never read.
    """
    facts: dict[NodeId, NodeFacts] = {}
    child = node_id
    while child:
        ancestor = parent_id(child)
        kind = node_kind(ancestor)
        if kind is None:
            raise ValueError(f"not a library node: {ancestor!r}")
        path = root / ancestor if ancestor else root
        facts[ancestor] = NodeFacts(
            kind=kind,
            stats=_count_files(path),
            own_issues=_own_issues(path, kind),
            children=(child,),
            complete=False,
        )
        child = ancestor
    return facts


def _own_issues(path: Path, kind: NodeKind) -> frozenset[NodeIssue]:
    if kind in _TIDY_KINDS and is_untidy(path):
        return frozenset({"untidy"})
    return frozenset()


def _scan(
    path: Path,
    node_id: NodeId,
    kind: NodeKind,
    out: dict[NodeId, NodeFacts],
    visit: Visit | None,
) -> None:
    if visit is not None:
        visit(node_id)
    children: list[NodeId] = []
    for sub in _subfolders(path):
        sub_kind = child_kind(kind, sub.name)
        if sub_kind is None:
            continue
        sub_id = child_id(node_id, sub.name)
        _scan(sub, sub_id, sub_kind, out, visit)
        children.append(sub_id)
    out[node_id] = NodeFacts(
        kind=kind,
        stats=_count_files(path),
        own_issues=_own_issues(path, kind),
        children=tuple(children),
    )
