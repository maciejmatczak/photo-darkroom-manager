"""Darkroom filesystem scanner -- builds a tree of DarkroomNode objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from photo_darkroom_manager.actions import collect_files_to_tidy
from photo_darkroom_manager.media import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS

ALBUM_PATTERN = re.compile(r"^\d{4}-\d{2}")


@dataclass
class FolderStats:
    image_count: int = 0
    video_count: int = 0
    other_file_count: int = 0


@dataclass
class DarkroomNode:
    path: Path
    name: str
    node_type: Literal["root", "year", "album", "subfolder"]
    stats: FolderStats = field(default_factory=FolderStats)
    local_issues: set[str] = field(default_factory=set)
    """Issues detected directly on this folder (not propagated from children)."""
    issues: set[str] = field(default_factory=set)
    """Propagated union: local_issues ∪ union(child.issues). Used for display."""
    children: list[DarkroomNode] = field(default_factory=list)
    parent: DarkroomNode | None = field(default=None, repr=False, compare=False)


def _count_files(directory: Path) -> FolderStats:
    """Count image, video, and other files directly in a directory (non-recursive)."""
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
    except PermissionError:
        pass
    return FolderStats(images, videos, others)


def _rollup_subtree_stats(node: DarkroomNode) -> None:
    """Set ``node.stats`` to files directly in this folder plus each child's stats.

    Children are expected to already store their full subtree totals.
    """
    direct = _count_files(node.path)
    total = FolderStats(direct.image_count, direct.video_count, direct.other_file_count)
    for child in node.children:
        total.image_count += child.stats.image_count
        total.video_count += child.stats.video_count
        total.other_file_count += child.stats.other_file_count
    node.stats = total


def _detect_untidy(directory: Path) -> bool:
    """True if this folder has misplaced photos or videos (see collect_tidy_paths)."""
    try:
        photos, videos = collect_files_to_tidy(directory)
    except PermissionError:
        return False
    return bool(photos or videos)


def _aggregate_issues(node: DarkroomNode) -> None:
    """Set ``node.issues`` to local_issues ∪ union(child.issues).

    Children must already have their own ``issues`` set.
    """
    aggregated = set(node.local_issues)
    for child in node.children:
        aggregated |= child.issues
    node.issues = aggregated


def _scan_subfolder(path: Path, parent: DarkroomNode | None = None) -> DarkroomNode:
    """Scan a subfolder under an album (device folder, PHOTOS, VIDEOS, etc.)."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="subfolder",
        stats=FolderStats(),
        parent=parent,
    )

    if _detect_untidy(path):
        node.local_issues.add("untidy")

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir():
                node.children.append(_scan_subfolder(child_dir, parent=node))
    except PermissionError:
        pass

    _rollup_subtree_stats(node)
    _aggregate_issues(node)
    return node


def _scan_album(path: Path, parent: DarkroomNode | None = None) -> DarkroomNode:
    """Scan an album directory."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="album",
        stats=FolderStats(),
        parent=parent,
    )

    if _detect_untidy(path):
        node.local_issues.add("untidy")

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir():
                node.children.append(_scan_subfolder(child_dir, parent=node))
    except PermissionError:
        pass

    _rollup_subtree_stats(node)
    _aggregate_issues(node)
    return node


def _propagate_issues(node: DarkroomNode) -> set[str]:
    """Recursively propagate issues up: a parent inherits all child issues.

    Also sets ``local_issues`` = ``issues`` at leaf nodes (backwards-compat
    for callers that build nodes without going through the typed scan helpers).
    """
    all_issues: set[str] = set(node.local_issues)
    for child in node.children:
        all_issues |= _propagate_issues(child)
    node.issues = all_issues
    return all_issues


def _scan_year(path: Path, parent: DarkroomNode | None = None) -> DarkroomNode:
    """Scan a year directory."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="year",
        stats=FolderStats(),
        parent=parent,
    )

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir() and ALBUM_PATTERN.match(child_dir.name):
                album_node = _scan_album(child_dir, parent=node)
                node.children.append(album_node)
    except PermissionError:
        pass

    _rollup_subtree_stats(node)
    _aggregate_issues(node)
    return node


def scan_darkroom(darkroom_path: Path) -> DarkroomNode:
    """Scan the entire darkroom directory and return a tree of DarkroomNode."""
    root = DarkroomNode(
        path=darkroom_path,
        name=darkroom_path.name,
        node_type="root",
        stats=FolderStats(),
    )

    try:
        for child_dir in sorted(darkroom_path.iterdir()):
            if (
                child_dir.is_dir()
                and child_dir.name.isdigit()
                and len(child_dir.name) == 4
            ):
                root.children.append(_scan_year(child_dir, parent=root))
    except PermissionError:
        pass

    _rollup_subtree_stats(root)
    _aggregate_issues(root)
    return root


def rescan_subtree(node: DarkroomNode) -> None:
    """Rescan *node* in place: recompute local_issues, rebuild children, roll up stats.

    The node's identity (path, node_type, parent, bound callbacks) is preserved.
    Children are rebuilt fresh from disk; there is no deep reconciliation, so
    expansion state within the rescanned subtree is lost.
    """
    node.local_issues = set()
    if _detect_untidy(node.path):
        node.local_issues.add("untidy")

    # Rebuild children based on node_type rules.
    new_children: list[DarkroomNode] = []
    try:
        for child_dir in sorted(node.path.iterdir()):
            if not child_dir.is_dir():
                continue
            if node.node_type == "year":
                if ALBUM_PATTERN.match(child_dir.name):
                    new_children.append(_scan_album(child_dir, parent=node))
            elif node.node_type in ("album", "subfolder"):
                new_children.append(_scan_subfolder(child_dir, parent=node))
            elif (
                node.node_type == "root"
                and child_dir.name.isdigit()
                and len(child_dir.name) == 4
            ):
                new_children.append(_scan_year(child_dir, parent=node))
    except PermissionError:
        pass

    node.children = new_children
    _rollup_subtree_stats(node)
    _aggregate_issues(node)


def reaggregate_ancestors(node: DarkroomNode) -> None:
    """Walk from *node*'s parent to the root, re-aggregating stats and issues.

    Call this after ``rescan_subtree`` to propagate changed totals upward
    without re-scanning any ancestor's folder on disk.
    """
    ancestor = node.parent
    while ancestor is not None:
        _rollup_subtree_stats(ancestor)
        _aggregate_issues(ancestor)
        ancestor = ancestor.parent
