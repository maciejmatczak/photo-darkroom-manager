"""Tests for rename: kept parts, refusals and its run."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import ActionRefusedError, rename
from photo_darkroom_manager.core.jobs import Job


@pytest.fixture
def darkroom(tmp_path: Path) -> Path:
    path = tmp_path / "darkroom"
    path.mkdir()
    return path


def _batch(darkroom: Path, name: str) -> Path:
    path = darkroom / "Camera" / "2026" / name
    path.mkdir(parents=True)
    return path


def _new_name(folder: Path, darkroom: Path, **inputs) -> str:
    return rename.prepare(folder, darkroom, **inputs).new_folder.name


def test_the_plan_names_the_old_and_new_folder(darkroom: Path) -> None:
    old = _batch(darkroom, "2026-10 Walk")
    plan = rename.prepare(old, darkroom, date="2026-10-05")
    assert plan.folder == old
    assert plan.new_folder == old.with_name("2026-10-05 Walk")
    assert plan.questions == {}
    assert old.is_dir()


def test_running_renames_the_folder(darkroom: Path) -> None:
    old = _batch(darkroom, "2026-03 rename me")
    result = rename.run(
        rename.prepare(old, darkroom, title="renamed batch"), {}, Job("rename")
    )
    assert result.outcome == "ok"
    assert result.folder == old.with_name("2026-03 renamed batch")
    assert result.folder.is_dir()
    assert not old.exists()


def test_a_new_title_keeps_the_date(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10-05 Walk")
    assert _new_name(source, darkroom, title="Hike") == "2026-10-05 Hike"


def test_a_new_date_keeps_the_title(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    assert _new_name(source, darkroom, date="2026-11") == "2026-11 Walk"


def test_the_title_can_be_dropped(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    assert _new_name(source, darkroom, clear_title=True) == "2026-10"


def test_the_same_name_has_nothing_to_do(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    assert rename.prepare(source, darkroom, date="2026-10", title="Walk").nothing_to_do


def test_a_taken_name_is_refused(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    _batch(darkroom, "2026-10 Hike")
    with pytest.raises(ActionRefusedError, match="2026-10 Hike"):
        rename.prepare(source, darkroom, title="Hike")
    assert source.is_dir()


def test_an_invalid_month_is_refused(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    with pytest.raises(ActionRefusedError, match="month"):
        rename.prepare(source, darkroom, date="2026-13")


def test_an_unreadable_name_needs_a_date(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10Walk")
    with pytest.raises(ActionRefusedError, match="date"):
        rename.prepare(source, darkroom, title="Walk")
    assert _new_name(source, darkroom, date="2026-10") == "2026-10"


def test_a_year_is_not_a_batch(darkroom: Path) -> None:
    year = darkroom / "Camera" / "2026"
    year.mkdir(parents=True)
    with pytest.raises(ActionRefusedError, match="Could not recognize batch"):
        rename.prepare(year, darkroom, title="new")


def test_a_name_taken_after_the_check_fails_and_keeps_the_batch(
    darkroom: Path,
) -> None:
    source = _batch(darkroom, "2026-03 source")
    plan = rename.prepare(source, darkroom, title="taken")
    _batch(darkroom, "2026-03 taken")
    result = rename.run(plan, {}, Job("rename"))
    assert result.outcome == "failed"
    assert "already exists" in result.message
    assert result.folder == source
    assert source.is_dir()


def test_preparing_twice_gives_the_same_fingerprint(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    first = rename.prepare(source, darkroom, title="Hike").fingerprint
    assert rename.prepare(source, darkroom, title="Hike").fingerprint == first
    assert rename.prepare(source, darkroom, title="Trip").fingerprint != first
