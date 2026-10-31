"""Tests for darkroom scan helpers and scan_darkroom."""

from pathlib import Path

import pytest

from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.scan import (
    DarkroomNode,
    FolderStats,
    _aggregate_issues,
    _count_files,
    _detect_untidy,
    _propagate_issues,
    _rollup_subtree_stats,
    reaggregate_ancestors,
    rescan_subtree,
    scan_darkroom,
)
from photo_darkroom_manager.settings import PHOTOS_FOLDER, PUBLISH_FOLDER, Settings


@pytest.mark.internal
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


@pytest.mark.internal
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

    parent = DarkroomNode(path=p, name="p", node_type="batch", stats=FolderStats())
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


@pytest.mark.internal
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


@pytest.mark.internal
def test_detect_untidy_true_when_misplaced_photo_at_batch_root(tmp_path: Path) -> None:
    batch = tmp_path / "2026-01 batch"
    batch.mkdir(parents=True)
    (batch / "loose.jpg").write_bytes(b"")
    assert _detect_untidy(batch) is True


@pytest.mark.internal
def test_detect_untidy_false_when_photos_only_in_photos_folder(tmp_path: Path) -> None:
    photos = tmp_path / "2026-01 tidy" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "ok.jpg").write_bytes(b"")
    assert _detect_untidy(photos) is False


@pytest.mark.internal
def test_propagate_issues_untidy_bubbles_to_ancestors() -> None:
    root = DarkroomNode(
        path=Path("root"), name="darkroom", node_type="root", stats=FolderStats()
    )
    year = DarkroomNode(
        path=Path("y"), name="2026", node_type="year", stats=FolderStats()
    )
    batch = DarkroomNode(
        path=Path("a"), name="2026-01 x", node_type="batch", stats=FolderStats()
    )
    sub = DarkroomNode(
        path=Path("s"),
        name="nested",
        node_type="subfolder",
        stats=FolderStats(),
        local_issues={"untidy"},
    )
    batch.children.append(sub)
    year.children.append(batch)
    root.children.append(year)

    _propagate_issues(root)
    assert root.issues == {"untidy"}
    assert year.issues == {"untidy"}
    assert batch.issues == {"untidy"}
    assert sub.issues == {"untidy"}


def test_scan_darkroom_only_four_digit_year_dirs(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    (dr / "Camera").mkdir(parents=True)
    (dr / "Camera" / "2026").mkdir()
    (dr / "Camera" / "abcd").mkdir()
    (dr / "Camera" / "202").mkdir()
    (dr / "Camera" / "20260").mkdir()

    tree = scan_darkroom(dr)
    assert tree.node_type == "root"
    assert [c.name for c in tree.children[0].children] == ["2026"]


def test_scan_darkroom_skips_non_batch_named_folders_under_year(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    y = dr / "Camera" / "2026"
    y.mkdir(parents=True)
    (y / "not-an-batch-name").mkdir()
    (y / "2026-03 ok batch").mkdir()

    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    assert [c.name for c in year.children] == ["2026-03 ok batch"]


def test_scan_darkroom_node_types_and_aggregated_stats(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch = dr / "Camera" / "2026" / "2026-04 stats"
    photos = batch / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "a.jpg").write_bytes(b"")
    (photos / "b.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    assert tree.node_type == "root"
    year = tree.children[0].children[0]
    assert year.node_type == "year"
    assert year.name == "2026"
    al = year.children[0]
    assert al.node_type == "batch"
    assert al.stats.image_count == 2
    photos_node = next(c for c in al.children if c.name == PHOTOS_FOLDER)
    assert photos_node.stats.image_count == 2


def test_scan_nested_subfolder_shows_accumulated_stats(tmp_path: Path) -> None:
    """Intermediate folder with no direct files still shows descendant counts."""
    dr = tmp_path / "darkroom"
    nested = dr / "Camera" / "2026" / "2026-07 nested" / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "x.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    al = tree.children[0].children[0].children[0]
    outer = next(c for c in al.children if c.name == "outer")
    inner = next(c for c in outer.children if c.name == "inner")
    assert outer.stats.image_count == 1
    assert inner.stats.image_count == 1
    assert al.stats.image_count == 1


def test_scan_publish_files_count_toward_stats_but_do_not_mark_batch_untidy(
    tmp_path: Path,
) -> None:
    """Misplaced media under PUBLISH/ is ignored by tidy detection (short-circuit)."""
    dr = tmp_path / "darkroom"
    batch = dr / "Camera" / "2026" / "2026-05 publish only"
    pub = batch / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "export.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    al = tree.children[0].children[0].children[0]
    assert al.stats.image_count == 1
    assert "untidy" not in al.issues

    publish_node = next(c for c in al.children if c.name == PUBLISH_FOLDER)
    assert publish_node.stats.image_count == 1
    assert "untidy" not in publish_node.issues


def test_scan_untidy_batch_propagates_to_root(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch = dr / "Camera" / "2026" / "2026-06 messy"
    batch.mkdir(parents=True)
    (batch / "loose.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    device = tree.children[0]
    year = device.children[0]
    assert "untidy" in year.issues
    assert "untidy" in device.issues
    assert "untidy" in tree.issues


# ---------------------------------------------------------------------------
# parent back-pointer
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_scan_darkroom_sets_parent_pointers(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch = dr / "Camera" / "2026" / "2026-01 check"
    photos = batch / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "a.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    al = year.children[0]
    photos_node = al.children[0]

    assert year.parent is tree.children[0]
    assert year.parent.parent is tree
    assert al.parent is year
    assert photos_node.parent is al


@pytest.mark.internal
def test_scan_darkroom_root_has_no_parent(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    dr.mkdir()
    tree = scan_darkroom(dr)
    assert tree.parent is None


@pytest.mark.internal
def test_scan_parent_excluded_from_repr_and_eq(tmp_path: Path) -> None:
    """parent must be repr=False / compare=False to avoid infinite recursion."""
    dr = tmp_path / "darkroom"
    (dr / "Camera" / "2026" / "2026-01 eq").mkdir(parents=True)
    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    # __repr__ must not include the parent field (repr=False)
    r = repr(year)
    assert "parent=" not in r
    # two structurally-equal nodes with different parents compare equal
    import copy

    year2 = copy.copy(year)
    year2.parent = None
    assert year == year2


# ---------------------------------------------------------------------------
# local_issues vs propagated issues
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_aggregate_issues_keeps_sibling_issue_on_ancestor(tmp_path: Path) -> None:
    """Clearing one batch's untidy must not clear an ancestor that still has a
    sibling batch with the issue."""
    dr = tmp_path / "darkroom"
    year_dir = dr / "Camera" / "2026"
    batch_a = year_dir / "2026-01 clean"
    batch_b = year_dir / "2026-02 messy"
    batch_a.mkdir(parents=True)
    batch_b.mkdir(parents=True)
    (batch_b / "loose.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    al_a = next(c for c in year.children if c.name == "2026-01 clean")
    al_b = next(c for c in year.children if c.name == "2026-02 messy")

    assert "untidy" not in al_a.issues
    assert "untidy" in al_b.issues
    assert "untidy" in year.issues

    # Simulate: batch_a's local issues are still empty, year re-aggregates
    _aggregate_issues(year)
    assert "untidy" in year.issues, "Sibling still untidy; year must keep the flag"


# ---------------------------------------------------------------------------
# rescan_subtree
# ---------------------------------------------------------------------------


def test_rescan_subtree_updates_stats_after_new_file(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch_dir = dr / "Camera" / "2026" / "2026-01 stats"
    batch_dir.mkdir(parents=True)
    tree = scan_darkroom(dr)
    batch = tree.children[0].children[0].children[0]
    assert batch.stats.image_count == 0

    (batch_dir / "new.jpg").write_bytes(b"")
    rescan_subtree(batch)

    assert batch.stats.image_count == 1


def test_rescan_subtree_detects_untidy_then_clears_it(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch_dir = dr / "Camera" / "2026" / "2026-02 tidy"
    batch_dir.mkdir(parents=True)
    (batch_dir / "loose.jpg").write_bytes(b"")
    tree = scan_darkroom(dr)
    batch = tree.children[0].children[0].children[0]
    assert "untidy" in batch.local_issues

    # Tidy the batch: move file into PHOTOS/
    photos = batch_dir / PHOTOS_FOLDER
    photos.mkdir()
    (batch_dir / "loose.jpg").rename(photos / "loose.jpg")

    rescan_subtree(batch)
    assert "untidy" not in batch.local_issues
    assert "untidy" not in batch.issues


def test_rescan_subtree_creates_new_children_after_tidy(tmp_path: Path) -> None:
    """Tidy creates PHOTOS/ and VIDEOS/ subfolders; rescan_subtree picks them up."""
    dr = tmp_path / "darkroom"
    batch_dir = dr / "Camera" / "2026" / "2026-03 new-children"
    batch_dir.mkdir(parents=True)
    (batch_dir / "img.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    batch = tree.children[0].children[0].children[0]
    assert batch.children == []

    # Simulate tidy outcome: PHOTOS/ created, file moved
    photos_dir = batch_dir / PHOTOS_FOLDER
    photos_dir.mkdir()
    (batch_dir / "img.jpg").rename(photos_dir / "img.jpg")

    rescan_subtree(batch)

    child_names = [c.name for c in batch.children]
    assert PHOTOS_FOLDER in child_names
    # New children have parent set back to batch
    for child in batch.children:
        assert child.parent is batch


@pytest.mark.internal
def test_rescan_subtree_preserves_node_identity_and_parent(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch_dir = dr / "Camera" / "2026" / "2026-04 identity"
    batch_dir.mkdir(parents=True)
    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    batch = year.children[0]
    original_id = id(batch)

    rescan_subtree(batch)

    assert id(batch) == original_id
    assert batch.parent is year


# ---------------------------------------------------------------------------
# reaggregate_ancestors
# ---------------------------------------------------------------------------


def test_reaggregate_ancestors_rolls_up_stats_to_root(tmp_path: Path) -> None:
    dr = tmp_path / "darkroom"
    batch_dir = dr / "Camera" / "2026" / "2026-05 rollup"
    batch_dir.mkdir(parents=True)
    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    batch = year.children[0]

    (batch_dir / "new.jpg").write_bytes(b"")
    rescan_subtree(batch)
    reaggregate_ancestors(batch)

    assert year.stats.image_count == 1
    assert tree.stats.image_count == 1


def test_reaggregate_ancestors_clears_issue_when_last_sibling_fixed(
    tmp_path: Path,
) -> None:
    """After both batches are tidied, the year and root lose 'untidy'."""
    dr = tmp_path / "darkroom"
    year_dir = dr / "Camera" / "2026"
    batch_a_dir = year_dir / "2026-01 a"
    batch_b_dir = year_dir / "2026-02 b"
    batch_a_dir.mkdir(parents=True)
    batch_b_dir.mkdir(parents=True)
    (batch_a_dir / "loose.jpg").write_bytes(b"")
    (batch_b_dir / "loose.jpg").write_bytes(b"")

    tree = scan_darkroom(dr)
    year = tree.children[0].children[0]
    al_a = next(c for c in year.children if c.name == "2026-01 a")
    al_b = next(c for c in year.children if c.name == "2026-02 b")

    assert "untidy" in year.issues

    # Fix batch_a
    photos_a = batch_a_dir / PHOTOS_FOLDER
    photos_a.mkdir()
    (batch_a_dir / "loose.jpg").rename(photos_a / "loose.jpg")
    rescan_subtree(al_a)
    reaggregate_ancestors(al_a)
    # batch_b still untidy → year keeps flag
    assert "untidy" in year.issues

    # Fix batch_b
    photos_b = batch_b_dir / PHOTOS_FOLDER
    photos_b.mkdir()
    (batch_b_dir / "loose.jpg").rename(photos_b / "loose.jpg")
    rescan_subtree(al_b)
    reaggregate_ancestors(al_b)
    assert "untidy" not in year.issues
    assert "untidy" not in tree.issues


# ---------------------------------------------------------------------------
# Manager-level invariant: tidy uses rescan_subtree, never full rescan
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_manager_tidy_calls_rescan_subtree_not_full_rescan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executing a tidy action via the manager must use scoped rescan only."""
    darkroom = tmp_path / "darkroom"
    showroom = tmp_path / "showroom"
    archive = tmp_path / "archive"
    batch_dir = darkroom / "Camera" / "2026" / "2026-01 inv"
    batch_dir.mkdir(parents=True)
    (batch_dir / "loose.jpg").write_bytes(b"")
    for d in (showroom, archive):
        d.mkdir()

    settings = Settings(darkroom=darkroom, showroom=showroom, archive=archive)
    mgr = DarkroomManager(settings)
    mgr.rescan()
    assert mgr.tree is not None

    year = mgr.tree.children[0].children[0]
    batch = year.children[0]

    full_rescan_called = []
    original_rescan = mgr.__class__.rescan

    def spy_rescan(self: DarkroomManager) -> object:
        full_rescan_called.append(True)
        return original_rescan(self)

    monkeypatch.setattr(DarkroomManager, "rescan", spy_rescan)

    # Move file to PHOTOS/ (simulate what TidyAction does)
    photos = batch_dir / PHOTOS_FOLDER
    photos.mkdir()
    (batch_dir / "loose.jpg").rename(photos / "loose.jpg")

    mgr.rescan_subtree(batch)

    assert not full_rescan_called, "rescan_subtree must not call full rescan()"
    assert batch.stats.image_count == 1
    assert "untidy" not in batch.issues
