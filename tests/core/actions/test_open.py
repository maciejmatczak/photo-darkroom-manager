"""Contract: app/action-open scenarios (opening a node's folder)."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core import actions
from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    OpenFolder,
    OpenFolderAction,
)


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Folders passed to the system file manager (patched)."""
    seen: list[Path] = []
    monkeypatch.setattr(actions, "_open_folder", seen.append)
    return seen


def _snapshot(root: Path) -> list[Path]:
    return sorted(root.rglob("*"))


def test_open_a_year(tmp_path: Path, opened: list[Path]) -> None:
    year = tmp_path / "Camera" / "2026"
    (year / "2026-10 Walk").mkdir(parents=True)
    before = _snapshot(tmp_path)
    act = OpenFolderAction(year)
    plan = act.prepare()
    assert isinstance(plan, ActionPlan)
    assert plan.steps == (OpenFolder(year),)
    assert not plan.changes_files

    result = act.execute(plan)

    assert result.outcome == "ok"
    assert opened == [year]
    assert _snapshot(tmp_path) == before


def test_folder_removed(tmp_path: Path, opened: list[Path]) -> None:
    gone = tmp_path / "Camera" / "2026" / "2026-10 Walk"
    out = OpenFolderAction(gone).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert str(gone) in out.message
    assert opened == []


@pytest.mark.internal
def test_folder_removed_after_the_preview(tmp_path: Path, opened: list[Path]) -> None:
    folder = tmp_path / "batch"
    folder.mkdir()
    act = OpenFolderAction(folder)
    plan = act.prepare()
    assert isinstance(plan, ActionPlan)
    folder.rmdir()
    result = act.execute(plan)
    assert result.outcome == "refused"
    assert opened == []


@pytest.mark.internal
def test_opener_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: Path) -> None:
        raise OSError("no file manager")

    monkeypatch.setattr(actions, "_open_folder", broken)
    act = OpenFolderAction(tmp_path)
    plan = act.prepare()
    assert isinstance(plan, ActionPlan)
    result = act.execute(plan)
    assert result.outcome == "failed"
    assert "no file manager" in (result.details or "")
