"""Tests for publish: its plan, its replace-or-skip question and its run."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionRefusedError,
    check_answers,
    publish,
)
from photo_darkroom_manager.core.jobs import Job
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


def _names(folder: Path) -> frozenset[str]:
    return frozenset(p.name for p in folder.iterdir() if p.is_file())


def _prepare(photo_setup, batch: Path) -> publish.PublishPlan:
    return publish.prepare(
        batch, photo_setup.roots.darkroom, photo_setup.roots.showroom
    )


def _run(plan: publish.PublishPlan, **answers: str) -> publish.PublishResult:
    return publish.run(plan, answers, Job("publish"))


def _republish(photo_setup) -> tuple[Path, Path]:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_OVERWRITE_REL)
    publish_dir = batch / PUBLISH_FOLDER
    (publish_dir / "same_name_0001.jpg").unlink()
    (publish_dir / "a.jpg").write_bytes(b"new a")
    (publish_dir / "b.jpg").write_bytes(b"new b")
    showroom = photo_setup.roots.showroom / PUBLISH_BATCH_OVERWRITE_DEST
    (showroom / "a.jpg").write_bytes(b"old a")
    return batch, showroom


def test_files_go_to_the_showroom_device_folder(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_BASIC_REL)
    plan = _prepare(photo_setup, batch)
    assert plan.replacements == ()
    assert plan.questions == {}
    assert frozenset(m.source.name for m in plan.moves) == _names(
        batch / PUBLISH_FOLDER
    )
    expected = (photo_setup.roots.showroom / PUBLISH_BATCH_BASIC_DEST).resolve()
    assert {m.target.parent.resolve() for m in plan.moves} == {expected}


def test_a_republish_lists_replacements_and_asks(photo_setup) -> None:
    batch, _ = _republish(photo_setup)
    plan = _prepare(photo_setup, batch)
    assert [m.source.name for m in plan.moves] == ["b.jpg"]
    assert [m.source.name for m in plan.replacements] == ["a.jpg"]
    question = plan.questions[publish.EXISTING_QUESTION]
    assert question.choices == ("replace", "skip")
    assert question.default is None


def test_a_republish_without_a_choice_is_refused(photo_setup) -> None:
    batch, _ = _republish(photo_setup)
    plan = _prepare(photo_setup, batch)
    with pytest.raises(ActionRefusedError, match=publish.EXISTING_QUESTION):
        check_answers(plan.questions, {})


def test_republish_with_replace(photo_setup) -> None:
    batch, showroom = _republish(photo_setup)
    result = _run(_prepare(photo_setup, batch), existing="replace")
    assert result.outcome == "ok"
    assert (showroom / "a.jpg").read_bytes() == b"new a"
    assert (showroom / "b.jpg").read_bytes() == b"new b"
    assert list((batch / PUBLISH_FOLDER).iterdir()) == []
    assert [m.source.name for m in result.moves.replaced] == ["a.jpg"]


def test_republish_with_skip(photo_setup) -> None:
    batch, showroom = _republish(photo_setup)
    result = _run(_prepare(photo_setup, batch), existing="skip")
    assert result.outcome == "ok"
    assert (showroom / "a.jpg").read_bytes() == b"old a"
    assert (showroom / "b.jpg").read_bytes() == b"new b"
    assert [p.name for p in (batch / PUBLISH_FOLDER).iterdir()] == ["a.jpg"]
    assert [m.source.name for m in result.moves.skipped] == ["a.jpg"]


def test_a_missing_publish_folder_is_refused(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_MISSING_REL)
    with pytest.raises(ActionRefusedError, match="PUBLISH directory does not exist"):
        _prepare(photo_setup, batch)


def test_a_folder_in_publish_is_refused(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_SUBDIR_REL)
    with pytest.raises(ActionRefusedError, match="contains subdirectories"):
        _prepare(photo_setup, batch)


def test_an_empty_publish_folder_has_nothing_to_do(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_FAIL_EMPTY_REL)
    assert _prepare(photo_setup, batch).nothing_to_do


def test_publishing_moves_the_files(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(PUBLISH_BATCH_BASIC_REL)
    names = _names(batch / PUBLISH_FOLDER)
    plan = _prepare(photo_setup, batch)
    result = _run(plan)
    assert result.outcome == "ok"
    assert result.moves.moved == plan.moves
    assert f"{len(names)} file" in result.message
    showroom = photo_setup.roots.showroom / PUBLISH_BATCH_BASIC_DEST
    assert all((showroom / name).is_file() for name in names)


def test_preparing_twice_gives_the_same_fingerprint(photo_setup) -> None:
    batch, _ = _republish(photo_setup)
    first = _prepare(photo_setup, batch).fingerprint
    assert _prepare(photo_setup, batch).fingerprint == first
    (batch / PUBLISH_FOLDER / "c.jpg").write_bytes(b"c")
    assert _prepare(photo_setup, batch).fingerprint != first
