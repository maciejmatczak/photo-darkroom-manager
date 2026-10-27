"""Tests for tidy collection and TidyAction."""

from pathlib import Path

import pytest

from photo_darkroom_manager.actions import (
    PrepareError,
    TidyAction,
    TidyPlan,
    _collect_files_to_tidy,
    collect_files_to_tidy,
)
from photo_darkroom_manager.settings import PHOTOS_FOLDER, PUBLISH_FOLDER, VIDEOS_FOLDER

TIDY_BATCH_BASIC_REL = Path("Camera") / "2026" / "2026-03 tidy basic moves jpg and xmp"


def test_collect_misplaced_photos_and_sidecar(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "shot.jpg").write_bytes(b"")
    (batch / "shot.xmp").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(batch)
    assert videos == []
    assert set(photos) == {batch / "shot.jpg", batch / "shot.xmp"}


def test_collect_misplaced_video(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "clip.mp4").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(batch)
    assert photos == []
    assert videos == [batch / "clip.mp4"]


def test_collect_skips_when_already_in_photos_folder(tmp_path: Path) -> None:
    photos_dir = tmp_path / PHOTOS_FOLDER
    photos_dir.mkdir()
    (photos_dir / "ok.jpg").write_bytes(b"")
    p, v = _collect_files_to_tidy(photos_dir)
    assert p == []
    assert v == []


def test_collect_skips_when_already_in_videos_folder(tmp_path: Path) -> None:
    videos_dir = tmp_path / VIDEOS_FOLDER
    videos_dir.mkdir()
    (videos_dir / "ok.mp4").write_bytes(b"")
    p, v = _collect_files_to_tidy(videos_dir)
    assert p == []
    assert v == []


def test_collect_multi_dot_filename_not_recognized_as_photo(tmp_path: Path) -> None:
    """Multi-dot name: stem is 'IMG'; suffix becomes '0001.jpg', not 'jpg'."""
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "IMG.0001.jpg").write_bytes(b"")
    (batch / "IMG.0001.xmp").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(batch)
    assert photos == []
    assert videos == []


def test_collect_files_to_tidy_publish_path_returns_empty(tmp_path: Path) -> None:
    pub = tmp_path / "batch" / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "a.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(pub, recursive=True)
    assert p == []
    assert v == []


def test_collect_files_to_tidy_recursive_subdir(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    sub = batch / "nested"
    sub.mkdir(parents=True)
    (sub / "deep.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(batch, recursive=True)
    assert sub / "deep.jpg" in p
    assert v == []


def test_collect_files_to_tidy_skips_publish_subdir_when_recursive(
    tmp_path: Path,
) -> None:
    batch = tmp_path / "batch"
    pub = batch / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "ignore.jpg").write_bytes(b"")
    (batch / "keep.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(batch, recursive=True)
    assert pub / "ignore.jpg" not in p
    assert batch / "keep.jpg" in p


def test_tidy_prepare_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    act = TidyAction(f)
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert "Not a directory" in out.message


def test_tidy_prepare_nothing_to_tidy(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    photos = batch / PHOTOS_FOLDER
    photos.mkdir()
    (photos / "already.jpg").write_bytes(b"")
    act = TidyAction(batch)
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "Nothing to tidy"


def test_tidy_prepare_execute_moves_to_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    result = act._execute(plan)
    assert result.success
    assert (batch / PHOTOS_FOLDER / "a.jpg").exists()
    assert not (batch / "a.jpg").exists()


def test_tidy_recursive_from_batch_moves_to_subfolder_photos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    iphone = batch / "iPhone"
    iphone.mkdir(parents=True)
    (iphone / "img.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    result = act._execute(plan)
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
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    result = act._execute(plan)
    assert result.success
    assert (batch / "iPhone" / VIDEOS_FOLDER / "clip.mp4").exists()
    assert not (photos / "clip.mp4").exists()


def test_tidy_sibling_bucket_photo_in_videos(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    videos = batch / "iPhone" / VIDEOS_FOLDER
    videos.mkdir(parents=True)
    (videos / "shot.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    result = act._execute(plan)
    assert result.success
    assert (batch / "iPhone" / PHOTOS_FOLDER / "shot.jpg").exists()
    assert not (videos / "shot.jpg").exists()


def test_tidy_prepare_blocks_when_destination_exists(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"other")
    act = TidyAction(batch)
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert "Tidy blocked" in out.message
    assert out.details is not None
    assert "→" in out.details
    assert (batch / "a.jpg").exists()


def test_tidy_execute_aborts_on_late_conflict(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    (batch / PHOTOS_FOLDER).mkdir()
    (batch / PHOTOS_FOLDER / "a.jpg").write_bytes(b"blocker")
    result = act._execute(plan)
    assert not result.success
    assert result.rescan_node_path is None
    assert "Tidy blocked" in result.message
    assert (batch / "a.jpg").exists()


def test_tidy_preview_text_extension_stats(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "a.jpg").write_bytes(b"")
    (batch / "a.xmp").write_bytes(b"")
    (batch / "b.mp4").write_bytes(b"")
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    text = plan.preview_text()
    assert ".jpg: 1" in text
    assert ".xmp: 1" in text
    assert ".mp4: 1" in text
    assert "a.jpg" not in text
    assert "b.mp4" not in text


def test_tidy_prepare_wraps_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = Path("/tmp/will-not-use")
    act = TidyAction(batch)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "photo_darkroom_manager.actions.TidyAction._prepare",
        boom,
    )
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "Internal error"
    assert out.details is not None
    assert "RuntimeError" in out.details


def test_tidy_executes_on_copied_data_fixture(photo_setup) -> None:
    batch = photo_setup.darkroom_has_dir(TIDY_BATCH_BASIC_REL)
    act = TidyAction(batch)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    assert len(plan.moves) >= 1
    ex = act._execute(plan)
    assert ex.success
    assert (batch / PHOTOS_FOLDER).is_dir()
