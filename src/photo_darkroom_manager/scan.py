"""Darkroom filesystem scanner -- builds a tree of DarkroomNode objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from photo_darkroom_manager.actions import collect_tidy_paths
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
    issues: set[str] = field(default_factory=set)
    children: list[DarkroomNode] = field(default_factory=list)


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


def _aggregate_stats(node: DarkroomNode) -> FolderStats:
    """Recursively aggregate stats from all descendants."""
    total = FolderStats(
        node.stats.image_count, node.stats.video_count, node.stats.other_file_count
    )
    for child in node.children:
        child_agg = _aggregate_stats(child)
        total.image_count += child_agg.image_count
        total.video_count += child_agg.video_count
        total.other_file_count += child_agg.other_file_count
    return total


def _detect_untidy(directory: Path) -> bool:
    """True if this folder has misplaced photos or videos (see collect_tidy_paths)."""
    try:
        photos, videos = collect_tidy_paths(directory)
    except PermissionError:
        return False
    return bool(photos or videos)


def _scan_subfolder(path: Path) -> DarkroomNode:
    """Scan a subfolder under an album (device folder, PHOTOS, VIDEOS, etc.)."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="subfolder",
        stats=_count_files(path),
    )

    if _detect_untidy(path):
        node.issues.add("untidy")

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir():
                node.children.append(_scan_subfolder(child_dir))
    except PermissionError:
        pass

    return node


def _scan_album(path: Path) -> DarkroomNode:
    """Scan an album directory."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="album",
        stats=_count_files(path),
    )

    if _detect_untidy(path):
        node.issues.add("untidy")

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir():
                node.children.append(_scan_subfolder(child_dir))
    except PermissionError:
        pass

    return node


def _propagate_issues(node: DarkroomNode) -> set[str]:
    """Recursively propagate issues up: a parent inherits all child issues."""
    all_issues = set(node.issues)
    for child in node.children:
        all_issues |= _propagate_issues(child)
    node.issues = all_issues
    return all_issues


def _scan_year(path: Path) -> DarkroomNode:
    """Scan a year directory."""
    node = DarkroomNode(
        path=path,
        name=path.name,
        node_type="year",
        stats=FolderStats(),
    )

    try:
        for child_dir in sorted(path.iterdir()):
            if child_dir.is_dir() and ALBUM_PATTERN.match(child_dir.name):
                album_node = _scan_album(child_dir)
                album_node.stats = _aggregate_stats(album_node)
                node.children.append(album_node)
    except PermissionError:
        pass

    node.stats = _aggregate_stats(node)
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
                root.children.append(_scan_year(child_dir))
    except PermissionError:
        pass

    root.stats = _aggregate_stats(root)
    _propagate_issues(root)
    return root
