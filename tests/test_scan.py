"""Tests for darkroom scan helpers and scan_darkroom."""

from pathlib import Path

from photo_darkroom_manager.scan import (
    DarkroomNode,
    FolderStats,
    _count_files,
    _detect_untidy,
    _propagate_issues,
    _rollup_subtree_stats,
    scan_darkroom,
)
from photo_darkroom_manager.settings import PHOTOS_FOLDER, PUBLISH_FOLDER


def test_count_files_photo_video_other_including_xmp_as_other(tmp_path: Path) -> None:
    d = tmp_path / "count"
    d.mkdir()
    (d / "a.jpg").write_bytes(b"")
    (d / "b.mp4").write_bytes(b"")
    (d / "c.xmp").write_bytes(b"")
    (d / "d.txt").write_bytes(b"")
    st = _count_files(d)
    assert st.image_count == 1
    assert st.video_count == 1
    assert st.other_file_count == 2


def test_rollup_subtree_stats_bottom_up_matches_full_tree(tmp_path: Path) -> None:
    """Roll up deepest-first so each parent sees already-totaled children."""
    p = tmp_path / "p"
    c = p / "c"
    g = c / "g"
    g.mkdir(parents=True)
    (p / "a.jpg").write_bytes(b"")
    (p / "root.txt").write_bytes(b"")
    (c / "b.jpg").write_bytes(b"")
    (c / "c2.jpg").write_bytes(b"")
    (c / "v.mp4").write_bytes(b"")
    (g / "x.xmp").write_bytes(b"")
    (g / "y.xmp").write_bytes(b"")
    (g / "deep.txt").write_bytes(b"")

    parent = DarkroomNode(path=p, name="p", node_type="album", stats=FolderStats())
    child = DarkroomNode(path=c, name="c", node_type="subfolder", stats=FolderStats())
    grand = DarkroomNode(path=g, name="g", node_type="subfolder", stats=FolderStats())
    child.children.append(grand)
    parent.children.append(child)

    _rollup_subtree_stats(grand)
    _rollup_subtree_stats(child)
    _rollup_subtree_stats(parent)

    assert parent.stats.image_count == 3
    assert parent.stats.video_count == 1
    assert parent.stats.other_file_count == 4


def test_rollup_subtree_stats_sums_one_level_only(tmp_path: Path) -> None:
    """Rolled-up child stats must not be fed back through a full recursive sum."""
    p = tmp_path / "p"
    c = p / "c"
    c.mkdir(parents=True)
    parent = DarkroomNode(
        path=p,
        name="p",
        node_type="subfolder",
        stats=FolderStats(),
    )
    child = DarkroomNode(
        path=c,
        name="c",
        node_type="subfolder",
        stats=FolderStats(2, 0, 0),
    )
    parent.children.append(child)
    _rollup_subtree_stats(parent)
    assert parent.stats.image_count == 2


def test_detect_untidy_true_when_misplaced_photo_at_album_root(tmp_path: Path) -> None:
    album = tmp_path / "2026-01 album"
    album.mkdir(parents=True)
    (album / "loose.jpg").write_bytes(b"")
    assert _detect_untidy(album) is True


def test_detect_untidy_false_when_photos_only_in_photos_folder(tmp_path: Path) -> None:
    photos = tmp_path / "2026-01 tidy" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "ok.jpg").write_bytes(b"")
    assert _detect_untidy(photos) is False


def test_propagate_issues_untidy_bubbles_to_ancestors() -> None:
    root = DarkroomNode(
        path=Path("root"), name="darkroom", node_type="root", stats=FolderStats()
    )
    year = DarkroomNode(
        path=Path("y"), name="2026", node_type="year", stats=FolderStats()
    )
    album = DarkroomNode(
        path=Path("a"), name="2026-01 x", node_type="album", stats=FolderStats()
    )
    sub = DarkroomNode(
        path=Path("s"),
        name="nested",
        node_type="subfolder",
        stats=FolderStats(),
        issues={"untidy"},
    )
    album.children.append(sub)
    year.children.append(album)
    root.children.append(year)

    _propagate_issues(root)
    assert root.issues == {"untidy"}
    assert year.issues == {"untidy"}
    assert album.issues == {"untidy"}
    assert sub.issues == {"untidy"}


def test_scan_darkroom_only_four_digit_year_dirs(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    dr.mkdir()
    (dr / "2026").mkdir()
    (dr / "abcd").mkdir()
    (dr / "202").mkdir()
    (dr / "20260").mkdir()

    tree = scan_darkroom(dr)
    assert tree.node_type == "root"
    assert [c.name for c in tree.children] == ["2026"]


def test_scan_darkroom_skips_non_album_named_folders_under_year(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    y = dr / "2026"
    y.mkdir(parents=True)
    (y / "not-an-album-name").mkdir()
    (y / "2026-03 ok album").mkdir()

    tree = scan_darkroom(dr)
    year = tree.children[0]
    assert [c.name for c in year.children] == ["2026-03 ok album"]


def test_scan_darkroom_node_types_and_aggregated_stats(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    album = dr / "2026" / "2026-04 stats"
    photos = album / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "a.jpg").write_bytes(b"")
    (photos / "b.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    assert tree.node_type == "root"
    year = tree.children[0]
    assert year.node_type == "year"
    assert year.name == "2026"
    al = year.children[0]
    assert al.node_type == "album"
    assert al.stats.image_count == 2
    photos_node = next(c for c in al.children if c.name == PHOTOS_FOLDER)
    assert photos_node.stats.image_count == 2


def test_scan_nested_subfolder_shows_accumulated_stats(tmp_path: Path) -> None:
    """Intermediate folder with no direct files still shows descendant counts."""
    dr = tmp_path / "darkroom"
    nested = dr / "2026" / "2026-07 nested" / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "x.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    al = tree.children[0].children[0]
    outer = next(c for c in al.children if c.name == "outer")
    inner = next(c for c in outer.children if c.name == "inner")
    assert outer.stats.image_count == 1
    assert inner.stats.image_count == 1
    assert al.stats.image_count == 1


def test_scan_publish_files_count_toward_stats_but_do_not_mark_album_untidy(
    tmp_path: Path,
) -> None:
    """Misplaced media under PUBLISH/ is ignored by tidy detection (short-circuit)."""
    dr = tmp_path / "darkroom"
    album = dr / "2026" / "2026-05 publish only"
    pub = album / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "export.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    al = tree.children[0].children[0]
    assert al.stats.image_count == 1
    assert "untidy" not in al.issues

    publish_node = next(c for c in al.children if c.name == PUBLISH_FOLDER)
    assert publish_node.stats.image_count == 1
    assert "untidy" not in publish_node.issues


def test_scan_untidy_album_propagates_to_root(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    album = dr / "2026" / "2026-06 messy"
    album.mkdir(parents=True)
    (album / "loose.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    assert "untidy" in tree.issues
