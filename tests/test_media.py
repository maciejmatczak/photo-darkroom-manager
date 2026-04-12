"""Tests for photo_darkroom_manager.media."""

import pytest

from photo_darkroom_manager.media import (
    ALL_IMAGE_EXTENSIONS,
    PHOTO_EXTENSIONS,
    RAW_IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
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
