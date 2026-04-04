"""Shared pytest fixtures."""

from pathlib import Path

import pytest

from photo_darkroom_manager.settings import Settings


@pytest.fixture
def data_dir() -> Path:
    """Path to the committed tests/data tree (read-only source)."""
    return Path(__file__).resolve().parent / "data"


@pytest.fixture
def darkroom_root(tmp_path: Path) -> Path:
    d = tmp_path / "darkroom"
    d.mkdir()
    return d


@pytest.fixture
def showroom_root(tmp_path: Path) -> Path:
    s = tmp_path / "showroom"
    s.mkdir()
    return s


@pytest.fixture
def archive_root(tmp_path: Path) -> Path:
    a = tmp_path / "archive"
    a.mkdir()
    return a


@pytest.fixture
def settings(darkroom_root: Path, showroom_root: Path, archive_root: Path) -> Settings:
    return Settings(
        darkroom=darkroom_root, showroom=showroom_root, archive=archive_root
    )
