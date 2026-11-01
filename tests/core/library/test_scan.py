"""Tests for scanning the darkroom into a library tree."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.library import (
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    LibraryTree,
    NodeView,
    scan_subtree,
)


def _scan(darkroom: Path) -> NodeView:
    return LibraryTree(darkroom, scan_subtree(darkroom, "", "root")).view("")


def _child(view: NodeView, name: str) -> NodeView:
    return next(c for c in view.children if c.name == name)


# ---------------------------------------------------------------------------
# file counts
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_counts_photo_video_other_including_xmp_as_other(tmp_path: Path) -> None:
    batch = tmp_path / "Camera" / "2026" / "2026-01 count"
    batch.mkdir(parents=True)
    for name in ("a.jpg", "b.mp4", "c.xmp", "d.txt"):
        (batch / name).write_bytes(b"")

    stats = scan_subtree(tmp_path, "Camera/2026/2026-01 count", "batch")[
        "Camera/2026/2026-01 count"
    ].stats

    assert stats.image_count == 1
    assert stats.video_count == 1
    assert stats.other_file_count == 2


@pytest.mark.internal
def test_untidy_only_when_media_misplaced(tmp_path: Path) -> None:
    messy = tmp_path / "Camera" / "2026" / "2026-01 messy"
    messy.mkdir(parents=True)
    (messy / "loose.jpg").write_bytes(b"")
    tidy_photos = tmp_path / "Camera" / "2026" / "2026-02 tidy" / PHOTOS_FOLDER
    tidy_photos.mkdir(parents=True)
    (tidy_photos / "ok.jpg").write_bytes(b"")

    year = _scan(tmp_path).children[0].children[0]

    assert _child(year, "2026-01 messy").own_issues == {"untidy"}
    assert _child(year, "2026-02 tidy").issues == frozenset()


# ---------------------------------------------------------------------------
# app/darkroom-tree
# ---------------------------------------------------------------------------


def test_node_kinds(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026" / "2026-10 Walk" / PHOTOS_FOLDER).mkdir(parents=True)

    root = _scan(tmp_path)
    device = root.children[0]
    year = device.children[0]
    batch = year.children[0]
    photos = batch.children[0]

    assert [n.kind for n in (root, device, year, batch, photos)] == [
        "root",
        "device",
        "year",
        "batch",
        "subfolder",
    ]


def test_empty_darkroom(tmp_path: Path) -> None:
    root = _scan(tmp_path)
    assert root.kind == "root"
    assert root.children == ()


def test_publish_folder_kind(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026" / "2026-10 Walk" / PUBLISH_FOLDER / "extra").mkdir(
        parents=True
    )

    batch = _scan(tmp_path).children[0].children[0].children[0]
    publish = _child(batch, PUBLISH_FOLDER)

    assert publish.kind == "publish"
    assert _child(publish, "extra").kind == "subfolder"


def test_only_four_digit_year_dirs(tmp_path: Path) -> None:
    for name in ("2026", "abcd", "202", "20260"):
        (tmp_path / "Camera" / name).mkdir(parents=True)

    device = _scan(tmp_path).children[0]
    assert [c.name for c in device.children] == ["2026"]


def test_skips_non_batch_named_folders_under_year(tmp_path: Path) -> None:
    year_dir = tmp_path / "Camera" / "2026"
    (year_dir / "not-an-batch-name").mkdir(parents=True)
    (year_dir / "2026-03 ok batch").mkdir()

    year = _scan(tmp_path).children[0].children[0]
    assert [c.name for c in year.children] == ["2026-03 ok batch"]


# ---------------------------------------------------------------------------
# app/statistics
# ---------------------------------------------------------------------------


def test_aggregated_stats(tmp_path: Path) -> None:
    photos = tmp_path / "Camera" / "2026" / "2026-04 stats" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "a.jpg").write_bytes(b"")
    (photos / "b.jpg").write_bytes(b"")

    root = _scan(tmp_path)
    year = root.children[0].children[0]
    batch = year.children[0]

    assert batch.total.image_count == 2
    assert batch.stats.image_count == 0
    assert _child(batch, PHOTOS_FOLDER).total.image_count == 2
    assert root.total.image_count == 2


def test_nested_subfolder_shows_accumulated_stats(tmp_path: Path) -> None:
    """Intermediate folder with no direct files still shows descendant counts."""
    nested = tmp_path / "Camera" / "2026" / "2026-07 nested" / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "x.jpg").write_bytes(b"")

    batch = _scan(tmp_path).children[0].children[0].children[0]
    outer = _child(batch, "outer")
    inner = _child(outer, "inner")

    assert outer.total.image_count == 1
    assert inner.total.image_count == 1
    assert batch.total.image_count == 1


def test_publish_files_count_but_do_not_mark_batch_untidy(tmp_path: Path) -> None:
    pub = tmp_path / "Camera" / "2026" / "2026-05 publish only" / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "export.jpg").write_bytes(b"")

    batch = _scan(tmp_path).children[0].children[0].children[0]

    assert batch.total.image_count == 1
    assert "untidy" not in batch.issues
    publish = _child(batch, PUBLISH_FOLDER)
    assert publish.total.image_count == 1
    assert "untidy" not in publish.issues


def test_untidy_batch_propagates_to_root(tmp_path: Path) -> None:
    batch = tmp_path / "Camera" / "2026" / "2026-06 messy"
    batch.mkdir(parents=True)
    (batch / "loose.jpg").write_bytes(b"")

    root = _scan(tmp_path)
    device = root.children[0]
    year = device.children[0]

    assert "untidy" in year.issues
    assert "untidy" in device.issues
    assert "untidy" in root.issues
    assert root.own_issues == frozenset()


@pytest.mark.internal
def test_sibling_issue_kept_on_ancestor(tmp_path: Path) -> None:
    year_dir = tmp_path / "Camera" / "2026"
    (year_dir / "2026-01 clean").mkdir(parents=True)
    (year_dir / "2026-02 messy").mkdir()
    (year_dir / "2026-02 messy" / "loose.jpg").write_bytes(b"")

    year = _scan(tmp_path).children[0].children[0]

    assert "untidy" not in _child(year, "2026-01 clean").issues
    assert "untidy" in _child(year, "2026-02 messy").issues
    assert "untidy" in year.issues
