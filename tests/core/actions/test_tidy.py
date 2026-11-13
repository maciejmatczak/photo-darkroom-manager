"""Tests for tidy: its plan, its question for conflicts and its run."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionRefusedError,
    check_answers,
    tidy,
)
from photo_darkroom_manager.core.actions._moves import (
    CONFLICT_EXISTS,
    CONFLICT_SAME_TARGET,
    FileMove,
)
from photo_darkroom_manager.core.jobs import Job
from photo_darkroom_manager.core.library import PHOTOS_FOLDER, VIDEOS_FOLDER

TIDY_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 tidy basic moves jpg and xmp"


def _run(plan: tidy.TidyPlan, **answers: str) -> tidy.TidyResult:
    return tidy.run(plan, answers, Job("tidy"))


def test_tidy_on_copied_data_fixture(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(TIDY_BATCH_BASIC_REL)
    plan = tidy.prepare(batch)
    assert not plan.nothing_to_do
    result = _run(plan)
    assert result.outcome == "ok"
    assert result.moves.moved == plan.moves
    assert (batch / PHOTOS_FOLDER).is_dir()


def test_not_a_directory_is_refused(tmp_path: Path) -> None:
    file = tmp_path / "file"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(ActionRefusedError, match="Not a directory"):
        tidy.prepare(file)


def test_nothing_to_tidy(tmp_path: Path) -> None:
    photos = tmp_path / "batch" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "already.jpg").write_bytes(b"")
    plan = tidy.prepare(tmp_path / "batch")
    assert plan.nothing_to_do
    assert plan.questions == {}


def test_loose_photo_moves_to_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    plan = tidy.prepare(batch)
    assert plan.moves == (FileMove(batch / "a.jpg", batch / PHOTOS_FOLDER / "a.jpg"),)
    result = _run(plan)
    assert result.outcome == "ok"
    assert result.message == "Tidied 1 of 1 file(s)"
    assert (batch / PHOTOS_FOLDER / "a.jpg").exists()
    assert not (batch / "a.jpg").exists()


def test_a_subfolder_gets_its_own_photos(tmp_path: Path) -> None:
    iphone = tmp_path / "batch" / "iPhone"
    iphone.mkdir(parents=True)
    (iphone / "img.jpg").write_bytes(b"")
    _run(tidy.prepare(tmp_path / "batch"))
    assert (iphone / PHOTOS_FOLDER / "img.jpg").exists()
    assert not (tmp_path / "batch" / PHOTOS_FOLDER / "img.jpg").exists()


def test_video_in_photos_moves_to_the_sibling_videos(tmp_path: Path) -> None:
    photos = tmp_path / "batch" / "iPhone" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "clip.mp4").write_bytes(b"")
    _run(tidy.prepare(tmp_path / "batch"))
    assert (tmp_path / "batch" / "iPhone" / VIDEOS_FOLDER / "clip.mp4").exists()


def test_photo_in_videos_moves_to_the_sibling_photos(tmp_path: Path) -> None:
    videos = tmp_path / "batch" / "iPhone" / VIDEOS_FOLDER
    videos.mkdir(parents=True)
    (videos / "shot.jpg").write_bytes(b"")
    _run(tidy.prepare(tmp_path / "batch"))
    assert (tmp_path / "batch" / "iPhone" / PHOTOS_FOLDER / "shot.jpg").exists()


def _same_name_in_photos(tmp_path: Path) -> Path:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"loose")
    (batch / "b.jpg").write_bytes(b"b")
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"other")
    return batch


def test_conflicts_are_listed_and_asked_about(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    plan = tidy.prepare(batch)
    assert [m.source.name for m in plan.moves] == ["b.jpg"]
    ((conflict),) = plan.conflicts
    assert conflict.source == batch / "a.jpg"
    assert conflict.reason == CONFLICT_EXISTS
    assert plan.questions[tidy.CONFLICTS_QUESTION].choices == ("skip",)


def test_conflicts_without_an_answer_are_refused(tmp_path: Path) -> None:
    plan = tidy.prepare(_same_name_in_photos(tmp_path))
    with pytest.raises(ActionRefusedError, match=tidy.CONFLICTS_QUESTION):
        check_answers(plan.questions, {})


def test_skip_moves_the_free_files(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    result = _run(tidy.prepare(batch), conflicts="skip")
    assert result.outcome == "ok"
    assert (batch / PHOTOS_FOLDER / "b.jpg").exists()
    assert (batch / "a.jpg").read_bytes() == b"loose"
    assert (batch / PHOTOS_FOLDER / "a.jpg").read_bytes() == b"other"
    assert [m.source.name for m in result.moves.skipped] == ["a.jpg"]


def test_two_files_for_one_target(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    (batch / PHOTOS_FOLDER).mkdir(parents=True)
    (batch / VIDEOS_FOLDER).mkdir()
    (batch / "a.jpg").write_bytes(b"loose")
    (batch / VIDEOS_FOLDER / "a.jpg").write_bytes(b"misfiled")
    plan = tidy.prepare(batch)
    assert len(plan.moves) == 1
    ((conflict),) = plan.conflicts
    assert conflict.reason == CONFLICT_SAME_TARGET


def test_a_target_taken_after_the_plan_is_skipped(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    plan = tidy.prepare(batch)
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"blocker")
    result = _run(plan)
    assert result.outcome == "ok"
    assert [m.source.name for m in result.moves.skipped] == ["a.jpg"]
    assert (batch / "a.jpg").exists()
    assert (batch / PHOTOS_FOLDER / "a.jpg").read_bytes() == b"blocker"


def test_a_late_file_in_a_tidy_folder_stays(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    plan = tidy.prepare(batch)
    (batch / "late.jpg").write_bytes(b"")
    result = _run(plan)
    assert result.outcome == "ok"
    assert (batch / PHOTOS_FOLDER / "a.jpg").exists()
    assert (batch / "late.jpg").exists()


def test_preparing_twice_gives_the_same_fingerprint(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    assert tidy.prepare(batch).fingerprint == tidy.prepare(batch).fingerprint
    before = tidy.prepare(batch).fingerprint
    (batch / "c.jpg").write_bytes(b"")
    assert tidy.prepare(batch).fingerprint != before
