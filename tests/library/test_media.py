"""Tests for library media kinds and tidy collection."""

from pathlib import Path

import pytest

from photo_darkroom_manager.library import (
    ALL_IMAGE_EXTENSIONS,
    PHOTO_EXTENSIONS,
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    RAW_IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    VIDEOS_FOLDER,
    collect_files_to_tidy,
    is_file_a_photo,
    is_file_a_video,
)


@pytest.mark.parametrize(
    ("suffixes", "expected"),
    [
        (["jpg"], True),
        (["JPG"], True),
        (["jpeg", "xmp"], True),
        (["heic"], True),
        (["heif"], True),
        (["png"], True),
        (["tif"], True),
        (["tiff"], True),
        ([], False),
        (["txt"], False),
        (["mp4"], False),
    ],
)
def test_is_file_a_photo(suffixes: list[str], expected: bool) -> None:
    assert is_file_a_photo(suffixes) is expected


@pytest.mark.parametrize(
    ("suffixes", "expected"),
    [
        (["mp4"], True),
        (["MOV"], True),
        (["avi"], True),
        (["mkv"], True),
        (["webm"], True),
        ([], False),
        (["jpg"], False),
        (["txt"], False),
    ],
)
def test_is_file_a_video(suffixes: list[str], expected: bool) -> None:
    assert is_file_a_video(suffixes) is expected


def test_photo_extensions_cover_known_types() -> None:
    assert {"jpg", "jpeg", "png", "heic", "heif", "tif", "tiff"}.issubset(
        PHOTO_EXTENSIONS
    )


def test_video_extensions_cover_known_types() -> None:
    assert {"mp4", "mov", "avi", "mkv", "webm"}.issubset(VIDEO_EXTENSIONS)


def test_all_image_extensions_is_composed_union() -> None:
    assert ALL_IMAGE_EXTENSIONS == PHOTO_EXTENSIONS | RAW_IMAGE_EXTENSIONS


@pytest.mark.internal
def test_collect_misplaced_photos_and_sidecar(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "shot.jpg").write_bytes(b"")
    (batch / "shot.xmp").write_bytes(b"")
    photos, videos = collect_files_to_tidy(batch)
    assert videos == []
    assert set(photos) == {batch / "shot.jpg", batch / "shot.xmp"}


@pytest.mark.internal
def test_collect_misplaced_video(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "clip.mp4").write_bytes(b"")
    photos, videos = collect_files_to_tidy(batch)
    assert photos == []
    assert videos == [batch / "clip.mp4"]


@pytest.mark.internal
def test_collect_skips_when_already_in_photos_folder(tmp_path: Path) -> None:
    photos_dir = tmp_path / PHOTOS_FOLDER
    photos_dir.mkdir()
    (photos_dir / "ok.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(photos_dir)
    assert p == []
    assert v == []


@pytest.mark.internal
def test_collect_skips_when_already_in_videos_folder(tmp_path: Path) -> None:
    videos_dir = tmp_path / VIDEOS_FOLDER
    videos_dir.mkdir()
    (videos_dir / "ok.mp4").write_bytes(b"")
    p, v = collect_files_to_tidy(videos_dir)
    assert p == []
    assert v == []


@pytest.mark.internal
def test_collect_multi_dot_filename_not_recognized_as_photo(tmp_path: Path) -> None:
    """Multi-dot name: stem is 'IMG'; suffix becomes '0001.jpg', not 'jpg'."""
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "IMG.0001.jpg").write_bytes(b"")
    (batch / "IMG.0001.xmp").write_bytes(b"")
    photos, videos = collect_files_to_tidy(batch)
    assert photos == []
    assert videos == []


@pytest.mark.internal
def test_collect_publish_path_returns_empty(tmp_path: Path) -> None:
    pub = tmp_path / "batch" / PUBLISH_FOLDER
    pub.mkdir(parents=True)
    (pub / "a.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(pub, recursive=True)
    assert p == []
    assert v == []


@pytest.mark.internal
def test_collect_recursive_subdir(tmp_path: Path) -> None:
    batch = tmp_path / "batch"
    sub = batch / "nested"
    sub.mkdir(parents=True)
    (sub / "deep.jpg").write_bytes(b"")
    p, v = collect_files_to_tidy(batch, recursive=True)
    assert sub / "deep.jpg" in p
    assert v == []


@pytest.mark.internal
def test_collect_skips_publish_subdir_when_recursive(
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
