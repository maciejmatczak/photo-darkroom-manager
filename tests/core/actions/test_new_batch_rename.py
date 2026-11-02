"""Tests for NewBatchAction and RenameAction."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    MakeDir,
    NewBatchAction,
    Rename,
    RenameAction,
)
from photo_darkroom_manager.core.library import PUBLISH_FOLDER


@pytest.fixture
def darkroom(tmp_path: Path) -> Path:
    path = tmp_path / "darkroom"
    path.mkdir()
    return path


def _plan(action) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


def _refused(action) -> ActionResult:
    out = action.prepare()
    assert isinstance(out, ActionResult), out
    assert out.outcome == "refused"
    return out


def _snapshot(root: Path) -> list[Path]:
    return sorted(p.relative_to(root) for p in root.rglob("*"))


# ---------------------------------------------------------------------------
# app/action-create-batch
# ---------------------------------------------------------------------------


def test_new_batch_creates_year_batch_and_publish(darkroom: Path) -> None:
    act = NewBatchAction(darkroom, "Camera", date="2026-04-15", title="Spring Outing")
    result = act.execute(_plan(act))
    assert result.outcome == "ok"
    batch_dir = darkroom / "Camera" / "2026" / "2026-04-15 Spring Outing"
    assert batch_dir.is_dir()
    assert (batch_dir / PUBLISH_FOLDER).is_dir()
    assert "2026-04-15 Spring Outing" in result.message
    assert result.node_path == batch_dir


def test_new_batch_without_day(darkroom: Path) -> None:
    act = NewBatchAction(darkroom, "Camera", date="2026-05", title="No Day")
    assert act.execute(_plan(act)).success
    assert (darkroom / "Camera" / "2026" / "2026-05 No Day" / PUBLISH_FOLDER).is_dir()


@pytest.mark.parametrize("no_title", [None, ""])
def test_new_batch_without_title_uses_date_only(
    darkroom: Path, no_title: str | None
) -> None:
    act = NewBatchAction(darkroom, "Camera", date="2026-06", title=no_title)
    assert act.execute(_plan(act)).success
    assert (darkroom / "Camera" / "2026" / "2026-06" / PUBLISH_FOLDER).is_dir()


def test_new_year_for_a_device(darkroom: Path) -> None:
    (darkroom / "Camera" / "2026").mkdir(parents=True)
    plan = _plan(NewBatchAction(darkroom, "Camera", date="2027-01"))
    assert plan.steps == (
        MakeDir(darkroom / "Camera" / "2027"),
        MakeDir(darkroom / "Camera" / "2027" / "2027-01"),
        MakeDir(darkroom / "Camera" / "2027" / "2027-01" / PUBLISH_FOLDER),
    )
    assert plan.changes_files
    assert not (darkroom / "Camera" / "2027").exists()


def test_new_batch_for_a_new_device(darkroom: Path) -> None:
    plan = _plan(NewBatchAction(darkroom, "Drone", date="2027-01"))
    assert [s.path for s in plan.steps if isinstance(s, MakeDir)] == [
        darkroom / "Drone",
        darkroom / "Drone" / "2027",
        darkroom / "Drone" / "2027" / "2027-01",
        darkroom / "Drone" / "2027" / "2027-01" / PUBLISH_FOLDER,
    ]


def test_batch_exists(darkroom: Path) -> None:
    (darkroom / "Camera" / "2026" / "2026-07 Exists").mkdir(parents=True)
    before = _snapshot(darkroom)
    out = _refused(NewBatchAction(darkroom, "Camera", date="2026-07", title="Exists"))
    assert "already exists" in out.message
    assert _snapshot(darkroom) == before


def test_new_batch_refused_when_created_after_the_preview(darkroom: Path) -> None:
    act = NewBatchAction(darkroom, "Camera", date="2026-07")
    plan = _plan(act)
    (darkroom / "Camera" / "2026" / "2026-07").mkdir(parents=True)
    result = act.execute(plan)
    assert result.outcome == "refused"
    assert result.rescan_node_path is None
    assert "already exists" in result.message


@pytest.mark.parametrize("date", ["2026-13", "2026", "2026-10-32", "10-2026"])
def test_new_batch_refuses_an_invalid_date(darkroom: Path, date: str) -> None:
    _refused(NewBatchAction(darkroom, "Camera", date=date))
    assert list(darkroom.iterdir()) == []


# ---------------------------------------------------------------------------
# app/action-rename-batch
# ---------------------------------------------------------------------------


def _batch(darkroom: Path, name: str) -> Path:
    path = darkroom / "Camera" / "2026" / name
    path.mkdir(parents=True)
    return path


def test_rename_plan(darkroom: Path) -> None:
    old = _batch(darkroom, "2026-10 Walk")
    plan = _plan(RenameAction(old, darkroom, date="2026-10-05"))
    assert plan.steps == (Rename(old, old.with_name("2026-10-05 Walk")),)
    assert plan.summary == "Rename 2026-10 Walk to 2026-10-05 Walk"
    assert old.is_dir()


def test_rename_execute_renames_batch_folder(darkroom: Path) -> None:
    old = _batch(darkroom, "2026-03 rename me")
    act = RenameAction(old, darkroom, title="renamed batch")
    result = act.execute(_plan(act))
    assert result.outcome == "ok"
    new_path = old.with_name("2026-03 renamed batch")
    assert result.rescan_node_path == old.parent
    assert result.node_path == new_path
    assert new_path.is_dir()
    assert not old.exists()


def test_name_taken(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    _batch(darkroom, "2026-10 Hike")
    out = _refused(RenameAction(source, darkroom, title="Hike"))
    assert "2026-10 Hike" in out.message
    assert source.is_dir()


def test_invalid_month(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    out = _refused(RenameAction(source, darkroom, date="2026-13"))
    assert "month" in out.message
    assert source.is_dir()


def test_new_title_only(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10-05 Walk")
    (step,) = _plan(RenameAction(source, darkroom, title="Hike")).steps
    assert isinstance(step, Rename)
    assert step.target.name == "2026-10-05 Hike"


def test_new_date_keeps_the_title(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    (step,) = _plan(RenameAction(source, darkroom, date="2026-11")).steps
    assert isinstance(step, Rename)
    assert step.target.name == "2026-11 Walk"


def test_clear_the_title(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    (step,) = _plan(RenameAction(source, darkroom, clear_title=True)).steps
    assert isinstance(step, Rename)
    assert step.target.name == "2026-10"


def test_same_name(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10 Walk")
    out = RenameAction(source, darkroom, date="2026-10", title="Walk").prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "noop"
    assert source.is_dir()


def test_unreadable_current_name_needs_a_date(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-10Walk")
    out = _refused(RenameAction(source, darkroom, title="Walk"))
    assert "date" in out.message
    (step,) = _plan(RenameAction(source, darkroom, date="2026-10")).steps
    assert isinstance(step, Rename)
    assert step.target.name == "2026-10"


def test_rename_fails_when_batch_not_recognized(darkroom: Path) -> None:
    year_only = darkroom / "Camera" / "2026"
    year_only.mkdir(parents=True)
    out = _refused(RenameAction(year_only, darkroom, title="new"))
    assert out.message == "Could not recognize batch"


def test_rename_refused_when_target_appears_after_the_preview(darkroom: Path) -> None:
    source = _batch(darkroom, "2026-03 source")
    act = RenameAction(source, darkroom, title="taken")
    plan = _plan(act)
    _batch(darkroom, "2026-03 taken")
    result = act.execute(plan)
    assert result.outcome == "refused"
    assert result.rescan_node_path is None
    assert source.is_dir()
