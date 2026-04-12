"""Tests for NewAlbumAction and RenameAction execute paths."""

from pathlib import Path
from typing import cast

import pytest

from photo_darkroom_manager.actions import ActionPlan, NewAlbumAction, RenameAction
from photo_darkroom_manager.settings import PUBLISH_FOLDER


def test_new_album_execute_creates_year_album_and_publish(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewAlbumAction(darkroom, "2026", "04", "15", "Spring Outing")
    result = act._execute(None)
    assert result.success
    album_dir = darkroom / "2026" / "2026-04-15 Spring Outing"
    assert album_dir.is_dir()
    assert (album_dir / PUBLISH_FOLDER).is_dir()
    assert "2026-04-15 Spring Outing" in result.message


def test_new_album_execute_without_day(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewAlbumAction(darkroom, "2026", "05", None, "No Day")
    result = act._execute(None)
    assert result.success
    album_dir = darkroom / "2026" / "2026-05 No Day"
    assert (album_dir / PUBLISH_FOLDER).is_dir()


@pytest.mark.parametrize("no_title", [None, ""])
def test_new_album_execute_without_name_uses_date_only(
    tmp_path: Path, no_title: str | None
) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewAlbumAction(darkroom, "2026", "06", None, no_title)
    result = act._execute(None)
    assert result.success
    album_dir = darkroom / "2026" / "2026-06"
    assert (album_dir / PUBLISH_FOLDER).is_dir()


def test_new_album_execute_fails_when_folder_already_exists(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    existing = darkroom / "2026" / "2026-07 Exists"
    existing.mkdir(parents=True)
    act = NewAlbumAction(darkroom, "2026", "07", None, "Exists")
    result = act._execute(None)
    assert not result.success
    assert "already exists" in result.message


def test_new_album_execute_rejects_non_none_plan(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    act = NewAlbumAction(darkroom, "2026", "08", None, "X")
    result = act._execute(cast(ActionPlan, object()))
    assert not result.success
    assert "new album expects no plan" in result.message


def test_rename_execute_renames_album_folder(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    old = darkroom / "2026" / "2026-03 rename me"
    old.mkdir(parents=True)
    act = RenameAction(old, "2026-03 renamed album", darkroom)
    result = act._execute(None)
    assert result.success
    new_path = darkroom / "2026" / "2026-03 renamed album"
    assert new_path.is_dir()
    assert not old.exists()


def test_rename_execute_fails_on_empty_name(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    album = darkroom / "2026" / "2026-03 a"
    album.mkdir(parents=True)
    act = RenameAction(album, "   ", darkroom)
    result = act._execute(None)
    assert not result.success
    assert result.message == "New name cannot be empty"


def test_rename_execute_fails_when_target_name_exists(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    year = darkroom / "2026"
    year.mkdir(parents=True)
    (year / "2026-03 source").mkdir()
    (year / "2026-03 taken").mkdir()
    act = RenameAction(year / "2026-03 source", "2026-03 taken", darkroom)
    result = act._execute(None)
    assert not result.success
    assert "already exists" in result.message


def test_rename_execute_fails_when_album_not_recognized(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    year_only = darkroom / "2026"
    year_only.mkdir(parents=True)
    act = RenameAction(year_only, "2026-03 new", darkroom)
    result = act._execute(None)
    assert not result.success
    assert result.message == "Could not recognize album"


def test_rename_execute_rejects_non_none_plan(tmp_path: Path) -> None:
    darkroom = tmp_path / "darkroom"
    album = darkroom / "2026" / "2026-03 x"
    album.mkdir(parents=True)
    act = RenameAction(album, "2026-03 y", darkroom)
    result = act._execute(cast(ActionPlan, object()))
    assert not result.success
    assert "rename expects no plan" in result.message
