"""Tests for photo_darkroom_manager.models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from photo_darkroom_manager.models import DarkroomYearAlbum, recognize_darkroom_album
from photo_darkroom_manager.settings import PUBLISH_FOLDER


def test_darkroom_year_album_valid() -> None:
    p = Path("/dr/2024/2024-01 Album")
    a = DarkroomYearAlbum(
        year="2024",
        album="2024-01 Album",
        album_path=p,
        relative_subpath=Path("2024/2024-01 Album"),
    )
    assert a.year == "2024"
    assert a.publish_dir == p / PUBLISH_FOLDER


@pytest.mark.parametrize(
    "year",
    ["abcd", "24", "20245"],
)
def test_darkroom_year_album_invalid_year(year: str) -> None:
    album = "2024-01 x"
    with pytest.raises(ValidationError, match="year"):
        DarkroomYearAlbum(
            year=year,
            album=album,
            album_path=Path("/dr") / year / album,
            relative_subpath=Path(year) / album,
        )


@pytest.mark.parametrize(
    "album",
    ["01 Album", "foo", "2024-1 x"],
)
def test_darkroom_year_album_invalid_album_format(album: str) -> None:
    year = "2024"
    with pytest.raises(ValidationError, match="album"):
        DarkroomYearAlbum(
            year=year,
            album=album,
            album_path=Path("/dr") / year / album,
            relative_subpath=Path(year) / album,
        )


def test_darkroom_year_album_rejects_non_calendar_month() -> None:
    """Invalid month (not 01–12) is rejected."""
    p = Path("/dr/2024/2024-13 Album")
    with pytest.raises(ValidationError, match="album"):
        DarkroomYearAlbum(
            year="2024",
            album="2024-13 Album",
            album_path=p,
            relative_subpath=Path("2024/2024-13 Album"),
        )


def test_darkroom_year_album_rejects_glued_suffix_after_month() -> None:
    """Characters glued after YYYY-MM without a space are rejected."""
    p = Path("/dr/2024/2024-01foo")
    with pytest.raises(ValidationError, match="album"):
        DarkroomYearAlbum(
            year="2024",
            album="2024-01foo",
            album_path=p,
            relative_subpath=Path("2024/2024-01foo"),
        )


def test_recognize_darkroom_album_happy_path() -> None:
    dr = Path("/dr")
    path = dr / "2024" / "2024-01 Test"
    album = recognize_darkroom_album(dr, path)
    assert album is not None
    assert album.year == "2024"
    assert album.album == "2024-01 Test"
    assert album.album_path == path
    assert album.relative_subpath == Path("2024/2024-01 Test")


def test_recognize_darkroom_album_deeper_subpath() -> None:
    dr = Path("/dr")
    path = dr / "2024" / "2024-01 A" / "PHOTOS" / "nested"
    album = recognize_darkroom_album(dr, path)
    assert album is not None
    assert album.relative_subpath == Path("2024/2024-01 A/PHOTOS/nested")
    assert album.album_path == dr / "2024" / "2024-01 A"


def test_recognize_darkroom_album_too_shallow_returns_none(tmp_path: Path) -> None:
    dr = tmp_path / "dr"
    dr.mkdir()
    (dr / "2024").mkdir()
    assert recognize_darkroom_album(dr, dr / "2024") is None


def test_recognize_darkroom_album_not_under_darkroom_raises(tmp_path: Path) -> None:
    dr = tmp_path / "dr"
    other = tmp_path / "other"
    dr.mkdir()
    other.mkdir()
    with pytest.raises(ValueError, match="not a subpath"):
        recognize_darkroom_album(dr, other)
