"""Contract: engine/library-index, engine/scanning and busy-engine scenarios."""

import shutil
from pathlib import Path

import pytest
from conftest import Roots

from photo_darkroom_manager.core import engine as engine_module
from photo_darkroom_manager.core.actions import PrepareError, TidyPlan
from photo_darkroom_manager.core.engine import (
    Engine,
    EngineBusyError,
    LibraryNotScannedError,
    NodeNotFoundError,
)
from photo_darkroom_manager.core.library import PHOTOS_FOLDER

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

    action = engine.action_tidy(batch)
    plan = action.prepare()
    assert isinstance(plan, TidyPlan)
    result = engine.action_execute(action, plan)

    assert result.success
    assert result.library_refreshed == BATCH
    view = engine.library_node(BATCH)
    assert "untidy" not in view.issues
    assert [c.name for c in view.children] == [PHOTOS_FOLDER]
    assert "untidy" not in engine.library_node("").issues


def test_opening_an_external_app(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots)
    engine.library_scan()
    action = engine.action_open_external_app("echo {folder}", batch)
    plan = action.prepare()
    assert not isinstance(plan, PrepareError)
    result = engine.action_execute(action, plan)
    assert result.success
    assert result.library_refreshed is None


@pytest.mark.internal
def test_action_without_a_scan_refreshes_nothing(roots: Roots, engine: Engine) -> None:
    result = engine.action_execute(
        engine.action_new_batch("Camera", "2026", "10", None, None), None
    )
    assert result.success
    assert result.rescan_node_path is not None
    assert result.library_refreshed is None
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

    def scan_and_probe(root, node_id, kind):
        seen["scanning"] = engine.library_scanning
        seen["status"] = engine.status
        seen["archive"] = engine.archive
        with pytest.raises(EngineBusyError) as edit:
            engine.config_set("archive", tmp_path / "elsewhere")
        seen["edit_busy"] = edit.value.busy
        with pytest.raises(EngineBusyError):
            engine.library_scan()
        with pytest.raises(EngineBusyError):
            engine.action_execute(
                engine.action_new_batch("Camera", "2026", "10", None, None), None
            )
        return real_scan(root, node_id, kind)

    monkeypatch.setattr(engine_module, "scan_subtree", scan_and_probe)
    engine.library_scan()

    assert seen == {
        "scanning": True,
        "status": "ready",
        "archive": roots.archive,
        "edit_busy": "scan",
    }
    assert engine.archive == roots.archive
    assert not (roots.darkroom / "Camera").exists()
    assert not engine.library_scanning


@pytest.mark.internal
def test_busy_flag_cleared_after_a_failed_scan(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(root, node_id, kind):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(engine_module, "scan_subtree", boom)
    with pytest.raises(RuntimeError):
        engine.library_scan()
    assert not engine.library_scanning
    monkeypatch.undo()
    engine.library_scan()
    assert engine.library_scanned
