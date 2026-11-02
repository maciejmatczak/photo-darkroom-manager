"""Tests for the library tree model and the actions manifest."""

import dataclasses
import importlib
from pathlib import Path

import pytest

from photo_darkroom_manager.core.library import (
    PUBLISH_FOLDER,
    FileCounts,
    LibraryTree,
    NodeAction,
    NodeFacts,
    NodeKind,
    node_actions,
    scan_chain,
    scan_subtree,
)

A = NodeAction


def _scan_tree(darkroom: Path) -> LibraryTree:
    return LibraryTree(darkroom, scan_subtree(darkroom, "", "root"))


# ---------------------------------------------------------------------------
# app/node-actions
# ---------------------------------------------------------------------------


def test_batch_actions(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026" / "2026-10 Walk").mkdir(parents=True)
    batch = _scan_tree(tmp_path).view("Camera/2026/2026-10 Walk")
    assert batch.actions == {
        A.OPEN,
        A.RENAME,
        A.TIDY,
        A.CULL,
        A.EDIT,
        A.PUBLISH,
        A.ARCHIVE,
    }


def test_publish_folder_actions(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026" / "2026-10 Walk" / PUBLISH_FOLDER).mkdir(parents=True)
    publish = _scan_tree(tmp_path).view(f"Camera/2026/2026-10 Walk/{PUBLISH_FOLDER}")
    assert publish.actions == {A.OPEN}


def test_tidy_folder_still_offers_tidy(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026" / "2026-10 Walk").mkdir(parents=True)
    batch = _scan_tree(tmp_path).view("Camera/2026/2026-10 Walk")
    assert A.TIDY in batch.actions
    assert "untidy" not in batch.issues


@pytest.mark.internal
@pytest.mark.parametrize(
    ("kind", "actions"),
    [
        ("root", {A.OPEN}),
        ("year", {A.OPEN}),
        ("device", {A.OPEN, A.NEW_BATCH}),
        ("subfolder", {A.OPEN, A.TIDY, A.CULL, A.EDIT, A.ARCHIVE}),
    ],
)
def test_node_actions_by_kind(kind, actions) -> None:
    assert node_actions(kind) == actions


# ---------------------------------------------------------------------------
# engine/library-index: views
# ---------------------------------------------------------------------------


def test_batch_with_a_subfolder(tmp_path: Path) -> None:
    batch_dir = tmp_path / "Camera" / "2026" / "2026-10 Walk"
    (batch_dir / "PHOTOS").mkdir(parents=True)
    (batch_dir / "a.jpg").write_bytes(b"")
    (batch_dir / "PHOTOS" / "b.jpg").write_bytes(b"")
    (batch_dir / "PHOTOS" / "c.jpg").write_bytes(b"")

    batch = _scan_tree(tmp_path).view("Camera/2026/2026-10 Walk")

    assert batch.stats.image_count == 1
    assert batch.total.image_count == 3
    assert [c.id for c in batch.children] == ["Camera/2026/2026-10 Walk/PHOTOS"]
    assert batch.children[0].name == "PHOTOS"


def test_view_is_a_snapshot(tmp_path: Path) -> None:
    batch_dir = tmp_path / "Camera" / "2026" / "2026-10 Walk"
    batch_dir.mkdir(parents=True)
    tree = _scan_tree(tmp_path)
    kept = tree.view("Camera/2026/2026-10 Walk")

    (batch_dir / "new.jpg").write_bytes(b"")
    tree.replace_subtree(kept.id, scan_subtree(tmp_path, kept.id, kept.kind))

    assert kept.total.image_count == 0
    assert tree.view(kept.id).total.image_count == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(kept, "name", "x")  # noqa: B010


@pytest.mark.internal
def test_root_view_is_named_after_darkroom(tmp_path: Path) -> None:
    root = _scan_tree(tmp_path).view("")
    assert root.id == ""
    assert root.name == tmp_path.name
    assert root.kind == "root"


# ---------------------------------------------------------------------------
# LibraryTree internals
# ---------------------------------------------------------------------------


@pytest.mark.internal
def test_nearest_walks_up_to_indexed_ancestor(tmp_path: Path) -> None:
    (tmp_path / "Camera" / "2026").mkdir(parents=True)
    tree = _scan_tree(tmp_path)
    assert tree.nearest("Camera/2026") == "Camera/2026"
    assert tree.nearest("Camera/2027/2027-01 x") == "Camera"
    assert tree.nearest("Phone") == ""


@pytest.mark.internal
def test_replace_subtree_updates_ancestors_without_reading_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    year_dir = tmp_path / "Camera" / "2026"
    batch_dir = year_dir / "2026-01 a"
    batch_dir.mkdir(parents=True)
    (year_dir / "2026-02 b").mkdir()
    (year_dir / "2026-02 b" / "loose.jpg").write_bytes(b"")
    tree = _scan_tree(tmp_path)

    (batch_dir / "loose.jpg").write_bytes(b"")
    counted: list[Path] = []
    scan_module = importlib.import_module("photo_darkroom_manager.core.library._scan")
    original = scan_module._count_files

    def spy(directory: Path) -> FileCounts:
        counted.append(directory)
        return original(directory)

    monkeypatch.setattr(scan_module, "_count_files", spy)
    tree.replace_subtree(
        "Camera/2026/2026-01 a",
        scan_subtree(tmp_path, "Camera/2026/2026-01 a", "batch"),
    )

    assert counted == [batch_dir]
    assert tree.view("Camera/2026").total.image_count == 2
    assert tree.view("").total.image_count == 2
    assert tree.view("Camera").issues == {"untidy"}


@pytest.mark.internal
def test_replace_subtree_clears_issue_when_last_sibling_fixed() -> None:
    def facts(untidy_a: bool, untidy_b: bool) -> dict[str, NodeFacts]:
        empty = FileCounts()

        def batch(untidy: bool) -> NodeFacts:
            issues = frozenset({"untidy"} if untidy else set())
            return NodeFacts("batch", empty, issues, ())  # type: ignore[arg-type]

        return {
            "": NodeFacts("root", empty, frozenset(), ("C",)),
            "C": NodeFacts("device", empty, frozenset(), ("C/2026",)),
            "C/2026": NodeFacts(
                "year", empty, frozenset(), ("C/2026/2026-01", "C/2026/2026-02")
            ),
            "C/2026/2026-01": batch(untidy_a),
            "C/2026/2026-02": batch(untidy_b),
        }

    tree = LibraryTree(Path("dr"), facts(True, True))
    tree.replace_subtree("C/2026/2026-01", facts(False, True))
    assert tree.view("").issues == {"untidy"}
    tree.replace_subtree("C/2026/2026-02", facts(False, False))
    assert tree.view("").issues == frozenset()
    assert tree.view("C/2026").issues == frozenset()


@pytest.mark.internal
def test_replace_subtree_drops_removed_descendants(tmp_path: Path) -> None:
    batch_dir = tmp_path / "Camera" / "2026" / "2026-01 a"
    (batch_dir / "old").mkdir(parents=True)
    tree = _scan_tree(tmp_path)
    (batch_dir / "old").rmdir()

    tree.replace_subtree(
        "Camera/2026/2026-01 a",
        scan_subtree(tmp_path, "Camera/2026/2026-01 a", "batch"),
    )

    assert not tree.contains("Camera/2026/2026-01 a/old")
    assert tree.view("Camera/2026/2026-01 a").children == ()


# ---------------------------------------------------------------------------
# partial trees: scoped loads and incomplete ancestors
# ---------------------------------------------------------------------------

WALK = "Camera/2026/2026-10 Walk"


def _two_devices(darkroom: Path) -> None:
    (darkroom / WALK / "PHOTOS").mkdir(parents=True)
    (darkroom / WALK / "PHOTOS" / "a.jpg").write_bytes(b"")
    (darkroom / "Camera" / "2026" / "2026-09 Other").mkdir()
    (darkroom / "Camera" / "2026" / "2026-09 Other" / "b.jpg").write_bytes(b"")
    (darkroom / "Phone" / "2026" / "2026-10 x").mkdir(parents=True)
    (darkroom / "Phone" / "2026" / "2026-10 x" / "c.jpg").write_bytes(b"")


def _load(tree: LibraryTree, darkroom: Path, node_id: str, kind: NodeKind) -> None:
    tree.load_subtree(
        node_id,
        scan_subtree(darkroom, node_id, kind),
        scan_chain(darkroom, node_id),
    )


def _scoped_tree(darkroom: Path, node_id: str, kind: NodeKind) -> LibraryTree:
    chain = scan_chain(darkroom, node_id)
    return LibraryTree(darkroom, chain | scan_subtree(darkroom, node_id, kind))


def test_stub_ancestors_cover_only_the_scanned_branch(tmp_path: Path) -> None:
    _two_devices(tmp_path)
    tree = _scoped_tree(tmp_path, WALK, "batch")

    root = tree.view("")
    assert not root.complete
    assert [c.id for c in root.children] == ["Camera"]
    assert root.total.image_count == 1
    batch = tree.view(WALK)
    assert batch.complete
    assert [c.name for c in batch.children] == ["PHOTOS"]
    assert not tree.view("Camera/2026").complete


@pytest.mark.internal
def test_load_subtree_adds_a_branch_to_a_stub(tmp_path: Path) -> None:
    _two_devices(tmp_path)
    tree = _scoped_tree(tmp_path, WALK, "batch")
    _load(tree, tmp_path, "Phone/2026/2026-10 x", "batch")
    root = tree.view("")
    assert [c.id for c in root.children] == ["Camera", "Phone"]
    assert root.total.image_count == 2
    assert not root.complete


def test_stub_becomes_complete_after_its_own_scan(tmp_path: Path) -> None:
    _two_devices(tmp_path)
    tree = _scoped_tree(tmp_path, WALK, "batch")
    _load(tree, tmp_path, "Camera", "device")
    camera = tree.view("Camera")
    assert camera.complete
    assert camera.total.image_count == 2
    assert not tree.view("").complete

    _load(tree, tmp_path, "", "root")
    assert tree.view("").complete
    assert tree.view("").total.image_count == 3


def test_stub_becomes_complete_after_a_refresh(tmp_path: Path) -> None:
    _two_devices(tmp_path)
    tree = _scoped_tree(tmp_path, WALK, "batch")
    tree.replace_subtree("Camera/2026", scan_subtree(tmp_path, "Camera/2026", "year"))
    year = tree.view("Camera/2026")
    assert year.complete
    assert [c.name for c in year.children] == ["2026-09 Other", "2026-10 Walk"]
    assert not tree.view("Camera").complete


@pytest.mark.internal
def test_load_subtree_adds_a_new_branch_to_a_complete_tree(tmp_path: Path) -> None:
    _two_devices(tmp_path)
    tree = _scan_tree(tmp_path)
    (tmp_path / "Camera" / "2027" / "2027-01 new").mkdir(parents=True)
    _load(tree, tmp_path, "Camera/2027/2027-01 new", "batch")
    assert [c.name for c in tree.view("Camera").children] == ["2026", "2027"]
    assert tree.view("Camera/2027/2027-01 new").complete
    assert not tree.view("Camera/2027").complete
    assert tree.view("Camera/2026").complete
    assert tree.view("Phone").complete
