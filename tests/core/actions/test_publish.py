"""Tests for PublishAction prepare and execute."""

from pathlib import Path

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    Move,
    PublishAction,
)
from photo_darkroom_manager.core.library import PUBLISH_FOLDER

PUBLISH_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 publish basic success"
PUBLISH_BATCH_OVERWRITE_REL = (
    Path("Camera") / "2026" / "2026-03 publish will overwrite conflicts"
)
PUBLISH_BATCH_FAIL_MISSING_REL = (
    Path("Camera") / "2026" / "2026-03 publish will fail missing publish dir"
)
PUBLISH_BATCH_FAIL_EMPTY_REL = (
    Path("Camera") / "2026" / "2026-03 publish will fail empty publish dir"
)
PUBLISH_BATCH_FAIL_SUBDIR_REL = (
    Path("Camera") / "2026" / "2026-03 publish will fail publish has subdir"
)


PUBLISH_BATCH_BASIC_DEST = Path("2026") / "2026-03 publish basic success" / "Camera"
PUBLISH_BATCH_OVERWRITE_DEST = (
    Path("2026") / "2026-03 publish will overwrite conflicts" / "Camera"
)


def _file_names_in_publish(publish_dir: Path) -> frozenset[str]:
    return frozenset(p.name for p in publish_dir.iterdir() if p.is_file())


def _publish(photo_setup, batch: Path) -> PublishAction:
    return PublishAction(
        batch,
        darkroom=photo_setup.roots.darkroom,
        showroom=photo_setup.roots.showroom,
    )


def _plan(action: PublishAction) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


def _moves(plan: ActionPlan) -> list[Move]:
    moves = [s for s in plan.steps if isinstance(s, Move)]
    assert len(moves) == len(plan.steps)
    return moves


def test_publish_prepare_happy_empty_conflicts(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_BASIC_REL)
    expected_names = _file_names_in_publish(batch / PUBLISH_FOLDER)
    moves = _moves(_plan(_publish(photo_setup, batch)))
    assert not any(m.overwrite for m in moves)
    assert frozenset(m.source.name for m in moves) == expected_names
    expected_target = (photo_setup.roots.showroom / PUBLISH_BATCH_BASIC_DEST).resolve()
    assert {m.target.parent for m in moves} == {expected_target}


def test_publish_prepare_marks_overwrites(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_OVERWRITE_REL)
    (step,) = _moves(_plan(_publish(photo_setup, batch)))
    assert step.overwrite
    assert step.source.name == step.target.name == "same_name_0001.jpg"
    assert step.target.is_file()


def test_republishing_a_batch(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_OVERWRITE_REL)
    (batch / PUBLISH_FOLDER / "same_name_0001.jpg").unlink()
    (batch / PUBLISH_FOLDER / "a.jpg").write_bytes(b"new a")
    (batch / PUBLISH_FOLDER / "b.jpg").write_bytes(b"new b")
    showroom = photo_setup.roots.showroom / PUBLISH_BATCH_OVERWRITE_DEST
    (showroom / "a.jpg").write_bytes(b"old a")

    plan = _plan(_publish(photo_setup, batch))

    assert {m.source.name: m.overwrite for m in _moves(plan)} == {
        "a.jpg": True,
        "b.jpg": False,
    }
    lines = plan.preview_text().splitlines()
    assert "  overwrite a.jpg → a.jpg" in lines
    assert "  move b.jpg → b.jpg" in lines
    assert "New: 1, overwritten: 1" in lines


def test_publish_prepare_fails_when_publish_dir_missing(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_MISSING_REL)
    assert not (batch / PUBLISH_FOLDER).exists()
    out = _publish(photo_setup, batch).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert out.message == "PUBLISH directory does not exist"


def test_publish_prepare_empty_publish_dir_is_a_noop(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_EMPTY_REL)
    publish_dir = batch / PUBLISH_FOLDER
    assert publish_dir.is_dir()
    assert _file_names_in_publish(publish_dir) == frozenset()
    out = _publish(photo_setup, batch).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "noop"
    assert out.message == "PUBLISH directory is empty"


def test_publish_prepare_fails_when_publish_has_subdir(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_SUBDIR_REL)
    assert [p for p in (batch / PUBLISH_FOLDER).iterdir() if p.is_dir()]
    out = _publish(photo_setup, batch).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert out.message == "PUBLISH directory contains subdirectories"


def test_publish_execute_moves_files_to_showroom(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_BASIC_REL)
    publish_dir = batch / PUBLISH_FOLDER
    names = _file_names_in_publish(publish_dir)
    act = _publish(photo_setup, batch)
    plan = _plan(act)
    result = act.execute(plan)
    assert result.outcome == "ok"
    assert result.done == plan.steps
    assert f"{len(names)} file" in result.message

    showroom_batch = photo_setup.roots.showroom / PUBLISH_BATCH_BASIC_DEST
    for name in names:
        assert (showroom_batch / name).is_file()
        assert not (publish_dir / name).exists()


def test_publish_execute_replaces_existing_file(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_OVERWRITE_REL)
    publish_dir = batch / PUBLISH_FOLDER
    (publish_dir / "same_name_0001.jpg").write_bytes(b"new")
    act = _publish(photo_setup, batch)
    result = act.execute(_plan(act))
    assert result.outcome == "ok"

    dest = (
        photo_setup.roots.showroom / PUBLISH_BATCH_OVERWRITE_DEST / "same_name_0001.jpg"
    )
    assert dest.read_bytes() == b"new"
    assert not (publish_dir / "same_name_0001.jpg").exists()
