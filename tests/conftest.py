"""Shared pytest fixtures."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from photo_darkroom_manager.settings import Settings


@dataclass(frozen=True, slots=True)
class PhotoSetup:
    """Writable three-root layout (darkroom / showroom / archive) plus helpers."""

    settings: Settings

    def darkroom_has_dir(self, relative: Path) -> Path:
        """Resolve ``relative`` under darkroom; assert it exists as a directory."""
        path = self.settings.darkroom / relative
        assert path.is_dir(), (
            "Missing tests/data darkroom fixtures; run "
            "`uv run python tests/data/create_test_data_fixtures.py` "
            "from the repo root."
        )
        return path


@pytest.fixture
def data_dir() -> Path:
    """Path to the committed tests/data tree (read-only source)."""
    return Path(__file__).resolve().parent / "data"


@pytest.fixture
def photo_setup(tmp_path: Path, data_dir: Path) -> PhotoSetup:
    """Copy ``tests/data`` into ``tmp_path``; return a :class:`PhotoSetup` wrapper.

    Mirrors a real install: writable darkroom, showroom, and archive trees built
    from the shared fixture scaffold.
    """
    root = tmp_path / "workspace"
    shutil.copytree(data_dir, root)
    return PhotoSetup(
        settings=Settings(
            darkroom=root / "darkroom",
            showroom=root / "showroom",
            archive=root / "archive",
        )
    )


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
