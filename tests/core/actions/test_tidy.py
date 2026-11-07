"""Tests for TidyAction."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    Move,
    TidyAction,
)
from photo_darkroom_manager.core.library import PHOTOS_FOLDER, VIDEOS_FOLDER

TIDY_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 tidy basic moves jpg and xmp"


def _plan(action: TidyAction) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


@pytest.mark.internal
def test_tidy_preview_text_extension_stats(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    (batch / "a.xmp").write_bytes(b"")
    (batch / "b.mp4").write_bytes(b"")
    text = _plan(TidyAction(batch)).preview_text()
    assert "Tidy 3 files" in text
    assert ".jpg: 1" in text
    assert ".xmp: 1" in text
    assert ".mp4: 1" in text
    assert "move a.jpg → PHOTOS/a.jpg" in text


@pytest.mark.internal
def test_tidy_prepare_wraps_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    act = TidyAction(Path("/tmp/will-not-use"))

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions.TidyAction._prepare",
        boom,
    )
    out = act.prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "failed"
    assert out.message == "Internal error"
    assert out.details is not None
    assert "RuntimeError" in out.details


def test_tidy_executes_on_copied_data_fixture(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(TIDY_BATCH_BASIC_REL)
    act = TidyAction(batch)
    plan = _plan(act)
    assert plan.changes_files
    ex = act.execute(plan)
    assert ex.outcome == "ok"
    assert ex.done == plan.steps
    assert (batch / PHOTOS_FOLDER).is_dir()


def test_tidy_prepare_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    out = TidyAction(f).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "refused"
    assert "Not a directory" in out.message


def test_nothing_to_tidy(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    photos = batch / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "already.jpg").write_bytes(b"")
    out = TidyAction(batch).prepare()
    assert isinstance(out, ActionResult)
    assert out.outcome == "noop"
    assert out.success
    assert out.message == "Nothing to tidy"


def test_tidy_prepare_execute_moves_to_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = _plan(act)
    assert plan.steps == (Move(batch / "a.jpg", batch / PHOTOS_FOLDER / "a.jpg"),)
    result = act.execute(plan)
    assert result.success
    assert (batch / PHOTOS_FOLDER / "a.jpg").exists()
    assert not (batch / "a.jpg").exists()


def test_tidy_recursive_from_batch_moves_to_subfolder_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    iphone = batch / "iPhone"
    iphone.mkdir(parents=True)
    (iphone / "img.jpg").write_bytes(b"")
    act = TidyAction(batch)
    result = act.execute(_plan(act))
    assert result.success
    assert (iphone / PHOTOS_FOLDER / "img.jpg").exists()
    assert not (iphone / "img.jpg").exists()
    assert not (batch / PHOTOS_FOLDER / "img.jpg").exists()


def test_tidy_sibling_bucket_video_in_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    photos = batch / "iPhone" / PHOTOS_FOLDER
    photos.mkdir(parents=True)
    (photos / "clip.mp4").write_bytes(b"")
    act = TidyAction(batch)
    result = act.execute(_plan(act))
    assert result.success
    assert (batch / "iPhone" / VIDEOS_FOLDER / "clip.mp4").exists()
    assert not (photos / "clip.mp4").exists()


def test_tidy_sibling_bucket_photo_in_videos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    videos = batch / "iPhone" / VIDEOS_FOLDER
    videos.mkdir(parents=True)
    (videos / "shot.jpg").write_bytes(b"")
    act = TidyAction(batch)
    result = act.execute(_plan(act))
    assert result.success
    assert (batch / "iPhone" / PHOTOS_FOLDER / "shot.jpg").exists()
    assert not (videos / "shot.jpg").exists()


def _same_name_in_photos(tmp_path: Path) -> Path:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"loose")
    (batch / "b.jpg").write_bytes(b"b")
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"other")
    return batch


def test_tidy_prepare_lists_conflicts(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    plan = _plan(TidyAction(batch))
    assert [s.source.name for s in plan.steps if isinstance(s, Move)] == ["b.jpg"]
    ((conflict),) = plan.conflicts
    assert conflict.move.source == batch / "a.jpg"
    assert conflict.reason == "exists"
    assert plan.summary == "Tidy 1 files, 1 conflict(s)"
    assert "conflict a.jpg → PHOTOS/a.jpg" in plan.preview_text()


def test_tidy_skip_moves_the_free_files(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    act = TidyAction(batch)
    result = act.execute(_plan(act), policy="skip")
    assert result.outcome == "ok"
    assert (batch / PHOTOS_FOLDER / "b.jpg").exists()
    assert (batch / "a.jpg").read_bytes() == b"loose"
    assert (batch / PHOTOS_FOLDER / "a.jpg").read_bytes() == b"other"
    assert [c.move.source.name for c in result.skipped] == ["a.jpg"]


def test_tidy_with_conflicts_refused_by_default(tmp_path: Path) -> None:
    batch = _same_name_in_photos(tmp_path)
    act = TidyAction(batch)
    result = act.execute(_plan(act))
    assert result.outcome == "refused"
    assert "Tidy blocked" in result.message
    assert [c.move.source.name for c in result.conflicts] == ["a.jpg"]
    assert (batch / "b.jpg").exists()


def test_tidy_two_files_for_one_target(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    (batch / PHOTOS_FOLDER).mkdir(parents=True)
    (batch / "VIDEOS").mkdir()
    (batch / "a.jpg").write_bytes(b"loose")
    (batch / "VIDEOS" / "a.jpg").write_bytes(b"misfiled")
    plan = _plan(TidyAction(batch))
    assert len(plan.steps) == 1
    ((conflict),) = plan.conflicts
    assert conflict.reason == "same_target"


def test_tidy_policies() -> None:
    assert TidyAction.policies == ("refuse", "skip")


def test_tidy_execute_aborts_on_late_conflict(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = _plan(act)
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"blocker")
    result = act.execute(plan)
    assert result.outcome == "refused"
    assert result.rescan_node_path is None
    assert "Tidy blocked" in result.message
    assert (batch / "a.jpg").exists()


def test_late_file_in_a_tidy_folder(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = _plan(act)
    (batch / "late.jpg").write_bytes(b"")
    result = act.execute(plan)
    assert result.outcome == "ok"
    assert (batch / PHOTOS_FOLDER / "a.jpg").exists()
    assert (batch / "late.jpg").exists()
    assert not (batch / PHOTOS_FOLDER / "late.jpg").exists()
