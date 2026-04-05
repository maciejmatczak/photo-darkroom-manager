"""Tests for darkroom scan helpers and scan_darkroom."""

from pathlib import Path

from photo_darkroom_manager.scan import (
    DarkroomNode,
    FolderStats,
    _aggregate_stats,
    _count_files,
    _detect_untidy,
    _propagate_issues,
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


def test_aggregate_stats_sums_descendants() -> None:
    parent = DarkroomNode(
        path=Path("p"),
        name="p",
        node_type="album",
        stats=FolderStats(1, 0, 1),
    )
    child = DarkroomNode(
        path=Path("c"),
        name="c",
        node_type="subfolder",
        stats=FolderStats(2, 1, 0),
    )
    grand = DarkroomNode(
        path=Path("g"),
        name="g",
        node_type="subfolder",
        stats=FolderStats(0, 0, 3),
    )
    child.children.append(grand)
    parent.children.append(child)
    agg = _aggregate_stats(parent)
    assert agg.image_count == 3
    assert agg.video_count == 1
    assert agg.other_file_count == 4


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
