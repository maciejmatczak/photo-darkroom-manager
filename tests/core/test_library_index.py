"""Contract: engine/library-index, engine/scanning and busy-engine scenarios."""

import shutil
import threading
from pathlib import Path

import pytest
from conftest import Roots, run_planned

from photo_darkroom_manager.core import engine as engine_module
from photo_darkroom_manager.core.engine import (
    Engine,
    EngineBusyError,
    LibraryNotScannedError,
    NodeNotFoundError,
    PathOutsideDarkroomError,
)
from photo_darkroom_manager.core.library import PHOTOS_FOLDER
from photo_darkroom_manager.core.library import _scan as scan_module

BATCH = "Camera/2026/2026-10 Walk"


def _batch(roots: Roots) -> Path:
    path = roots.darkroom / BATCH
    path.mkdir(parents=True)
    return path


# ---------------------------------------------------------------------------
# engine/library-index
# ---------------------------------------------------------------------------


def test_batch_id(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    batch = engine.library_node(BATCH)
    assert batch.id == BATCH
    assert batch.kind == "batch"


def test_id_survives_a_rescan(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    before = engine.library_node(BATCH)
    assert engine.library_refresh("Camera") == "Camera"
    assert engine.library_node(BATCH) == before


def test_not_scanned_yet(engine: Engine) -> None:
    assert not engine.library_scanned
    with pytest.raises(LibraryNotScannedError):
        engine.library_node("")


def test_unknown_id(engine: Engine) -> None:
    engine.library_scan()
    with pytest.raises(NodeNotFoundError) as exc:
        engine.library_node("Camera/1999")
    assert exc.value.node_id == "Camera/1999"
    assert "Camera/1999" in str(exc.value)


def test_after_a_scan(engine: Engine) -> None:
    engine.library_scan()
    assert not engine.library_scanning
    assert engine.library_scanned


def test_darkroom_moved_in_settings(engine: Engine, tmp_path: Path) -> None:
    engine.library_scan()
    other = tmp_path / "other-darkroom"
    other.mkdir()
    engine.config_set("darkroom", other)
    assert not engine.library_scanned
    with pytest.raises(LibraryNotScannedError):
        engine.library_node("")


@pytest.mark.internal
def test_same_darkroom_keeps_the_tree(roots: Roots, engine: Engine) -> None:
    engine.library_scan()
    engine.config_set("darkroom", roots.darkroom)
    engine.config_set("archive", roots.archive)
    assert engine.library_scanned


# ---------------------------------------------------------------------------
# engine/scanning
# ---------------------------------------------------------------------------


def test_new_year_under_a_device(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    (roots.darkroom / "Camera/2027").mkdir()
    assert engine.library_refresh("Camera") == "Camera"
    years = [c.name for c in engine.library_node("Camera").children]
    assert years == ["2026", "2027"]


def test_folder_not_yet_in_the_tree(roots: Roots, engine: Engine) -> None:
    (roots.darkroom / "Camera").mkdir()
    engine.library_scan()
    (roots.darkroom / "Camera/2027").mkdir()
    assert engine.library_refresh("Camera/2027") == "Camera"
    assert engine.library_node("Camera/2027").kind == "year"


def test_folder_gone_from_disk(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots)
    engine.library_scan()
    shutil.rmtree(batch)
    assert engine.library_refresh(BATCH) == "Camera/2026"
    with pytest.raises(NodeNotFoundError):
        engine.library_node(BATCH)


def test_tidy_updates_the_tree(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots)
    (batch / "loose.jpg").write_bytes(b"image")
    engine.library_scan()
    assert "untidy" in engine.library_node(BATCH).issues

    done = run_planned(engine, "tidy", BATCH)

    assert done.result.outcome == "ok"
    assert done.library_refreshed == BATCH
    view = engine.library_node(BATCH)
    assert "untidy" not in view.issues
    assert [c.name for c in view.children] == [PHOTOS_FOLDER]
    assert "untidy" not in engine.library_node("").issues


def test_opening_an_external_app_changes_nothing(roots: Roots, make_engine) -> None:
    _batch(roots)
    engine = make_engine(roots, edit_command="echo {folder}")
    engine.library_scan()
    revision = engine.library_revision
    engine.action_edit(BATCH)
    assert engine.library_revision == revision


@pytest.mark.internal
def test_action_without_a_scan_refreshes_nothing(roots: Roots, engine: Engine) -> None:
    done = run_planned(engine, "new_batch", "Camera", date="2026-10")
    assert done.result.outcome == "ok"
    assert done.library_refreshed is None
    assert not engine.library_scanned


# ---------------------------------------------------------------------------
# engine/library-index "Scan state is shared" + busy engine
# ---------------------------------------------------------------------------


def test_during_a_scan(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """While a scan runs, state is visible and edits and work are refused."""
    seen: dict[str, object] = {}
    real_scan = engine_module.scan_subtree

    def scan_and_probe(root, node_id, kind, **kwargs):
        seen["scanning"] = engine.library_scanning
        seen["status"] = engine.status
        seen["archive"] = engine.archive
        with pytest.raises(EngineBusyError) as edit:
            engine.config_set("archive", tmp_path / "elsewhere")
        seen["edit_busy"] = edit.value.label
        with pytest.raises(EngineBusyError):
            engine.library_scan()
        plan = engine.action_prepare_new_batch("Camera", date="2026-10")
        with pytest.raises(EngineBusyError):
            engine.action_new_batch(plan)
        return real_scan(root, node_id, kind, **kwargs)

    monkeypatch.setattr(engine_module, "scan_subtree", scan_and_probe)
    engine.library_scan()

    assert seen == {
        "scanning": True,
        "status": "ready",
        "archive": roots.archive,
        "edit_busy": "scan darkroom root",
    }
    assert engine.archive == roots.archive
    assert not (roots.darkroom / "Camera").exists()
    assert not engine.library_scanning


@pytest.mark.internal
def test_busy_flag_cleared_after_a_failed_scan(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(root, node_id, kind, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(engine_module, "scan_subtree", boom)
    with pytest.raises(RuntimeError):
        engine.library_scan()
    assert not engine.library_scanning
    monkeypatch.undo()
    engine.library_scan()
    assert engine.library_scanned


# ---------------------------------------------------------------------------
# engine/library-index: scoped scan, incomplete ancestors, resolving paths
# ---------------------------------------------------------------------------


@pytest.fixture
def two_devices(roots: Roots) -> Roots:
    _batch(roots)
    (roots.darkroom / BATCH / "a.jpg").write_bytes(b"")
    (roots.darkroom / "Camera/2026/2026-09 Other").mkdir()
    (roots.darkroom / "Phone/2026/2026-10 x").mkdir(parents=True)
    (roots.darkroom / "Phone/2026/2026-10 x/b.jpg").write_bytes(b"")
    return roots


def test_one_batch_nothing_scanned_before(
    two_devices: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    read: list[Path] = []
    real_count = scan_module._count_files
    real_subfolders = scan_module._subfolders

    def count(directory: Path):
        read.append(directory)
        return real_count(directory)

    def subfolders(directory: Path):
        read.append(directory)
        return real_subfolders(directory)

    monkeypatch.setattr(scan_module, "_count_files", count)
    monkeypatch.setattr(scan_module, "_subfolders", subfolders)

    assert engine.library_scan(BATCH) == BATCH

    batch = engine.library_node(BATCH)
    assert batch.total.image_count == 1
    assert batch.complete
    phone = two_devices.darkroom / "Phone"
    assert read
    assert not any(p == phone or phone in p.parents for p in read)
    assert two_devices.darkroom / "Camera/2026/2026-09 Other" not in read


def test_missing_folder(engine: Engine) -> None:
    with pytest.raises(NodeNotFoundError) as exc:
        engine.library_scan("Camera/1999")
    assert exc.value.node_id == "Camera/1999"


def test_root_after_scanning_one_batch(two_devices: Roots, engine: Engine) -> None:
    engine.library_scan(BATCH)
    root = engine.library_node("")
    assert not root.complete
    assert [c.id for c in root.children] == ["Camera"]
    assert [c.id for c in root.children[0].children] == ["Camera/2026"]
    assert [c.id for c in root.children[0].children[0].children] == [BATCH]


def test_full_scan_completes_the_tree(two_devices: Roots, engine: Engine) -> None:
    engine.library_scan(BATCH)
    engine.library_scan()
    root = engine.library_node("")
    assert root.complete
    assert [c.id for c in root.children] == ["Camera", "Phone"]


@pytest.mark.internal
def test_scoped_scan_keeps_the_rest_of_the_tree(
    two_devices: Roots, engine: Engine
) -> None:
    engine.library_scan()
    (two_devices.darkroom / BATCH / "new.jpg").write_bytes(b"")
    engine.library_scan(BATCH)
    root = engine.library_node("")
    assert root.complete
    assert root.total.image_count == 3
    assert [c.id for c in root.children] == ["Camera", "Phone"]


@pytest.mark.internal
def test_scoped_scan_returns_the_on_disk_id(two_devices: Roots, engine: Engine) -> None:
    assert engine.library_scan(BATCH.lower()) == BATCH


def test_batch_path(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    assert engine.library_resolve(roots.darkroom / BATCH) == BATCH


def test_archive_path(roots: Roots, engine: Engine) -> None:
    with pytest.raises(PathOutsideDarkroomError):
        engine.library_resolve(roots.archive / "2026")


# ---------------------------------------------------------------------------
# Cancelled scans and reading while a scan runs
# ---------------------------------------------------------------------------


class _HeldScan:
    """Holds a scan when it reaches *at* until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, at: str) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        real = engine_module.scan_subtree

        def scan(root, node_id, kind, *, visit=None):
            def held(folder_id: str) -> None:
                if folder_id == at:
                    self.reached.set()
                    assert self.release.wait(5)
                if visit is not None:
                    visit(folder_id)

            return real(root, node_id, kind, visit=held)

        monkeypatch.setattr(engine_module, "scan_subtree", scan)


def test_cancel_a_full_rescan(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)
    engine.library_scan()
    before = engine.library_node("")
    revision = engine.library_revision
    (roots.darkroom / "Camera/2026/2026-11 New").mkdir()
    held = _HeldScan(monkeypatch, "Camera/2026")
    engine.library_scan_start()
    try:
        assert held.reached.wait(5)
        engine.job_cancel()
    finally:
        held.release.set()
    job = engine.job_wait(5)

    assert job is not None and job.state == "cancelled"
    assert engine.library_node("") == before
    assert engine.library_revision == revision
    with pytest.raises(NodeNotFoundError):
        engine.library_node("Camera/2026/2026-11 New")


def test_cancel_a_refresh_keeps_the_tree(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)
    engine.library_scan()
    before = engine.library_node("Camera")
    (roots.darkroom / "Camera/2026/2026-11 New").mkdir()
    held = _HeldScan(monkeypatch, "Camera/2026")
    engine.library_refresh_start("Camera")
    try:
        assert held.reached.wait(5)
        engine.job_cancel()
    finally:
        held.release.set()
    job = engine.job_wait(5)
    assert job is not None and job.state == "cancelled"
    assert engine.library_node("Camera") == before


def test_reading_nodes_while_a_scan_runs(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)
    engine.library_scan()
    before = engine.library_node(BATCH)
    held = _HeldScan(monkeypatch, "Camera/2026")
    engine.library_scan_start()
    try:
        assert held.reached.wait(5)
        assert engine.library_scanning
        assert engine.library_node(BATCH) == before
        assert engine.status == "ready"
    finally:
        held.release.set()
    engine.job_wait(5)
    assert not engine.library_scanning


# ---------------------------------------------------------------------------
# engine/library-index: revision and changes
# ---------------------------------------------------------------------------


def test_tidy_changes_the_revision(roots: Roots, engine: Engine) -> None:
    (_batch(roots) / "loose.jpg").write_bytes(b"image")
    engine.library_scan()
    revision = engine.library_revision
    run_planned(engine, "tidy", BATCH)
    assert engine.library_revision > revision
    assert engine.library_changes(revision) == (BATCH,)


def test_reading_keeps_the_revision(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    revision = engine.library_revision
    engine.library_node("")
    engine.library_node(BATCH)
    assert engine.library_revision == revision
    assert engine.library_changes(revision) == ()


def test_archive_of_one_batch_changes_its_year(roots: Roots, engine: Engine) -> None:
    (_batch(roots) / "a.jpg").write_bytes(b"image")
    engine.library_scan()
    revision = engine.library_revision
    run_planned(engine, "archive", BATCH)
    assert engine.library_changes(revision) == ("Camera/2026",)


def test_changes_inside_another_change_are_left_out(
    roots: Roots, engine: Engine
) -> None:
    _batch(roots)
    engine.library_scan()
    revision = engine.library_revision
    engine.library_refresh(BATCH)
    engine.library_refresh("Camera")
    assert engine.library_changes(revision) == ("Camera",)


def test_darkroom_root_change_is_the_root(
    roots: Roots, engine: Engine, tmp_path: Path
) -> None:
    _batch(roots)
    engine.library_scan()
    revision = engine.library_revision
    other = tmp_path / "other-darkroom"
    other.mkdir()
    engine.config_set("darkroom", other)
    assert engine.library_changes(revision) == ("",)


def test_too_old_a_revision_is_the_root(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    revision = engine.library_revision
    for _ in range(70):
        engine.library_refresh(BATCH)
    assert engine.library_changes(revision) == ("",)
    assert engine.library_changes(engine.library_revision - 1) == (BATCH,)
