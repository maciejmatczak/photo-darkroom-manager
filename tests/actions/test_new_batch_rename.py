"""Tests for NewBatchAction and RenameAction execute paths."""

from pathlib import Path
from typing import cast

import pytest

from photo_darkroom_manager.actions import ActionPlan, NewBatchAction, RenameAction
from photo_darkroom_manager.settings import PUBLISH_FOLDER


def test_new_batch_execute_creates_year_batch_and_publish(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewBatchAction(darkroom, "Camera", "2026", "04", "15", "Spring Outing")
    result = act.execute(None)
    assert result.success
    batch_dir = darkroom / "Camera" / "2026" / "2026-04-15 Spring Outing"
    assert batch_dir.is_dir()
    assert (batch_dir / PUBLISH_FOLDER).is_dir()
    assert "2026-04-15 Spring Outing" in result.message


def test_new_batch_execute_without_day(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewBatchAction(darkroom, "Camera", "2026", "05", None, "No Day")
    result = act.execute(None)
    assert result.success
    batch_dir = darkroom / "Camera" / "2026" / "2026-05 No Day"
    assert (batch_dir / PUBLISH_FOLDER).is_dir()


@pytest.mark.parametrize("no_title", [None, ""])
def test_new_batch_execute_without_name_uses_date_only(
    tmp_path: Path, no_title: str | None
) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewBatchAction(darkroom, "Camera", "2026", "06", None, no_title)
    result = act.execute(None)
    assert result.success
    batch_dir = darkroom / "Camera" / "2026" / "2026-06"
    assert (batch_dir / PUBLISH_FOLDER).is_dir()


def test_new_batch_execute_fails_when_folder_already_exists(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    existing = darkroom / "Camera" / "2026" / "2026-07 Exists"
    existing.mkdir(parents=True)
    act = NewBatchAction(darkroom, "Camera", "2026", "07", None, "Exists")
    result = act.execute(None)
    assert not result.success
    assert result.rescan_node_path is None
    assert "already exists" in result.message


@pytest.mark.internal
def test_new_batch_execute_rejects_non_none_plan(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewBatchAction(darkroom, "Camera", "2026", "08", None, "X")
    result = act.execute(cast(ActionPlan, object()))
    assert not result.success
    assert "new batch expects no plan" in result.message


def test_new_batch_execute_fails_on_invalid_month(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewBatchAction(darkroom, "Camera", "2026", "13", None, "X")
    result = act.execute(None)
    assert not result.success
    assert result.rescan_node_path is None


def test_rename_execute_renames_batch_folder(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    old = darkroom / "Camera" / "2026" / "2026-03 rename me"
    old.mkdir(parents=True)
    act = RenameAction(old, darkroom, "2026", "03", None, "renamed batch")
    result = act.execute(None)
    assert result.success
    assert result.rescan_node_path == darkroom / "Camera" / "2026"
    new_path = darkroom / "Camera" / "2026" / "2026-03 renamed batch"
    assert new_path.is_dir()
    assert not old.exists()


def test_rename_execute_fails_on_invalid_month(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    batch = darkroom / "Camera" / "2026" / "2026-03 a"
    batch.mkdir(parents=True)
    act = RenameAction(batch, darkroom, "2026", "99", None, None)
    result = act.execute(None)
    assert not result.success


def test_rename_execute_fails_when_target_name_exists(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    year = darkroom / "Camera" / "2026"
    year.mkdir(parents=True)
    (year / "2026-03 source").mkdir()
    (year / "2026-03 taken").mkdir()
    act = RenameAction(year / "2026-03 source", darkroom, "2026", "03", None, "taken")
    result = act.execute(None)
    assert not result.success
    assert result.rescan_node_path is None
    assert "already exists" in result.message


def test_rename_execute_fails_when_batch_not_recognized(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    year_only = darkroom / "Camera" / "2026"
    year_only.mkdir(parents=True)
    act = RenameAction(year_only, darkroom, "2026", "03", None, "new")
    result = act.execute(None)
    assert not result.success
    assert result.message == "Could not recognize batch"


@pytest.mark.internal
def test_rename_execute_rejects_non_none_plan(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    batch = darkroom / "Camera" / "2026" / "2026-03 x"
    batch.mkdir(parents=True)
    act = RenameAction(batch, darkroom, "2026", "03", None, "y")
    result = act.execute(cast(ActionPlan, object()))
    assert not result.success
    assert "rename expects no plan" in result.message


def test_rename_execute_noop_when_unchanged(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    batch = darkroom / "Camera" / "2026" / "2026-03 same"
    batch.mkdir(parents=True)
    act = RenameAction(batch, darkroom, "2026", "03", None, "same")
    result = act.execute(None)
    assert result.success
    assert result.rescan_node_path is None
    assert batch.is_dir()
