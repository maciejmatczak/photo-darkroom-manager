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

TIDY_ALBUM_BASIC_REL = Path("2026") / "2026-03 tidy basic moves jpg and xmp"


def test_collect_misplaced_photos_and_sidecar(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()
    (album / "shot.jpg").write_bytes(b"")
    (album / "shot.xmp").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(album)
    assert videos == []
    assert set(photos) == {album / "shot.jpg", album / "shot.xmp"}


def test_collect_misplaced_video(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()
    (album / "clip.mp4").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(album)
    assert photos == []
    assert videos == [album / "clip.mp4"]


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
    album = tmp_path / "album"
    album.mkdir()
    (album / "IMG.0001.jpg").write_bytes(b"")
    (album / "IMG.0001.xmp").write_bytes(b"")
    photos, videos = _collect_files_to_tidy(album)
    assert photos == []
    assert videos == []


def test_collect_files_to_tidy_publish_path_returns_empty(tmp_path: Path) -> None:
    pub = tmp_path / "album" / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "a.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(pub, recursive=True)
    assert p == []
    assert v == []


def test_collect_files_to_tidy_recursive_subdir(tmp_path: Path) -> None:
    album = tmp_path / "album"
    sub = album / "nested"
    sub.mkdir(parents=True)
    (sub / "deep.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(album, recursive=True)
    assert sub / "deep.jpg" in p
    assert v == []


def test_collect_files_to_tidy_skips_publish_subdir_when_recursive(
    tmp_path: Path,
) -> None:
    album = tmp_path / "album"
    pub = album / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "ignore.jpg").write_bytes(b"")
    (album / "keep.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(album, recursive=True)
    assert pub / "ignore.jpg" not in p
    assert album / "keep.jpg" in p


def test_tidy_prepare_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    act = TidyAction(f)
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert "Not a directory" in out.message


def test_tidy_prepare_nothing_to_tidy(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()
    photos = album / PHOTOS_FOLDER
    photos.mkdir()
    (photos / "already.jpg").write_bytes(b"")
    act = TidyAction(album)
    out = act.prepare()
    assert isinstance(out, PrepareError)
    assert out.message == "Nothing to tidy"


def test_tidy_prepare_execute_moves_to_photos(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()
    (album / "a.jpg").write_bytes(b"")
    act = TidyAction(album)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    result = act._execute(plan)
    assert result.success
    assert (album / PHOTOS_FOLDER / "a.jpg").exists()
    assert not (album / "a.jpg").exists()


def test_tidy_prepare_wraps_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    album = Path("/tmp/will-not-use")
    act = TidyAction(album)

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
    album = photo_setup.darkroom_has_dir(TIDY_ALBUM_BASIC_REL)
    act = TidyAction(album)
    plan = act._prepare()
    assert isinstance(plan, TidyPlan)
    assert len(plan.photo_paths) >= 1
    ex = act._execute(plan)
    assert ex.success
    assert (album / PHOTOS_FOLDER).is_dir()
