"""Tests for new batch: the folders it plans, its refusals and its run."""

from pathlib import Path

import pytest
from conftest import link_dir

from photo_darkroom_manager.core.actions import ActionRefusedError, new_batch
from photo_darkroom_manager.core.jobs import Job
from photo_darkroom_manager.core.library import PUBLISH_FOLDER


@pytest.fixture
def darkroom(tmp_path: Path) -> Path:
    path = tmp_path / "darkroom"
    path.mkdir()
    return path


def _snapshot(root: Path) -> list[Path]:
    return sorted(p.relative_to(root) for p in root.rglob("*"))


def _create(
    darkroom: Path, device: str = "Camera", **inputs
) -> new_batch.NewBatchResult:
    plan = new_batch.prepare(darkroom, device, **inputs)
    return new_batch.run(plan, {}, Job("new_batch"))


def test_creates_the_year_batch_and_publish(darkroom: Path) -> None:
    result = _create(darkroom, date="2026-04-15", title="Spring Outing")
    batch = darkroom / "Camera" / "2026" / "2026-04-15 Spring Outing"
    assert result.outcome == "ok"
    assert result.batch_folder == batch
    assert (batch / PUBLISH_FOLDER).is_dir()
    assert not (batch / "PHOTOS").exists()
    assert "2026-04-15 Spring Outing" in result.message


@pytest.mark.parametrize("title", [None, ""])
def test_without_a_title_the_name_is_the_date(
    darkroom: Path, title: str | None
) -> None:
    _create(darkroom, date="2026-06", title=title)
    assert (darkroom / "Camera" / "2026" / "2026-06" / PUBLISH_FOLDER).is_dir()


def test_a_new_year_for_a_device(darkroom: Path) -> None:
    (darkroom / "Camera" / "2026").mkdir(parents=True)
    plan = new_batch.prepare(darkroom, "Camera", date="2027-01")
    assert plan.folders_to_create == (
        darkroom / "Camera" / "2027",
        darkroom / "Camera" / "2027" / "2027-01",
        darkroom / "Camera" / "2027" / "2027-01" / PUBLISH_FOLDER,
    )
    assert not plan.nothing_to_do
    assert not (darkroom / "Camera" / "2027").exists()


def test_a_new_device(darkroom: Path) -> None:
    plan = new_batch.prepare(darkroom, "Drone", date="2027-01")
    assert plan.folders_to_create[0] == darkroom / "Drone"
    assert len(plan.folders_to_create) == 4


def test_an_existing_batch_is_refused(darkroom: Path) -> None:
    (darkroom / "Camera" / "2026" / "2026-07 Exists").mkdir(parents=True)
    before = _snapshot(darkroom)
    with pytest.raises(ActionRefusedError, match="already exists"):
        new_batch.prepare(darkroom, "Camera", date="2026-07", title="Exists")
    assert _snapshot(darkroom) == before


@pytest.mark.parametrize("date", ["2026-13", "2026", "2026-10-32", "10-2026"])
def test_an_invalid_date_is_refused(darkroom: Path, date: str) -> None:
    with pytest.raises(ActionRefusedError):
        new_batch.prepare(darkroom, "Camera", date=date)
    assert list(darkroom.iterdir()) == []


def test_a_file_in_the_way_is_refused_naming_it(darkroom: Path) -> None:
    (darkroom / "Camera").mkdir()
    (darkroom / "Camera" / "2026").write_bytes(b"keep")
    with pytest.raises(ActionRefusedError, match="2026"):
        new_batch.prepare(darkroom, "Camera", date="2026-07")
    assert (darkroom / "Camera" / "2026").read_bytes() == b"keep"


def test_a_device_linked_outside_the_darkroom_is_refused(
    darkroom: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link_dir(darkroom / "Camera", outside)
    with pytest.raises(ActionRefusedError, match="inside darkroom"):
        new_batch.prepare(darkroom, "Camera", date="2027-01")
    assert list(outside.iterdir()) == []


def test_a_batch_made_after_the_check_fails_and_is_kept(darkroom: Path) -> None:
    plan = new_batch.prepare(darkroom, "Camera", date="2026-07")
    (darkroom / "Camera" / "2026" / "2026-07").mkdir(parents=True)
    (darkroom / "Camera" / "2026" / "2026-07" / "a.jpg").write_bytes(b"a")
    result = new_batch.run(plan, {}, Job("new_batch"))
    assert result.outcome == "failed"
    assert (darkroom / "Camera" / "2026" / "2026-07" / "a.jpg").is_file()


def test_preparing_twice_gives_the_same_fingerprint(darkroom: Path) -> None:
    first = new_batch.prepare(darkroom, "Camera", date="2027-01").fingerprint
    assert new_batch.prepare(darkroom, "Camera", date="2027-01").fingerprint == first
    (darkroom / "Camera").mkdir()
    assert new_batch.prepare(darkroom, "Camera", date="2027-01").fingerprint != first
