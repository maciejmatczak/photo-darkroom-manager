"""Shared pytest fixtures."""

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from photo_darkroom_manager.core.engine import CONFIG_PATH_ENV, LOG_LEVEL_ENV, Engine
from photo_darkroom_manager.core.logging_config import reset_logging_state_for_tests

MakeEngine = Callable[..., Engine]


@dataclass(frozen=True, slots=True)
class Roots:
    """Temp library roots a test engine is configured with."""

    darkroom: Path
    showroom: Path
    archive: Path


def write_config(path: Path, roots: Roots | None = None, **values: object) -> Path:
    """Write a YAML config with *roots* and extra *values*; return *path*."""
    data: dict[str, object] = {}
    if roots is not None:
        data |= {
            "darkroom": str(roots.darkroom),
            "showroom": str(roots.showroom),
            "archive": str(roots.archive),
        }
    data |= values
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def engine_for(roots: Roots, **values: object) -> Engine:
    """Engine over a config next to the darkroom root, naming *roots*."""
    config = roots.darkroom.parent / "config.yaml"
    return Engine(write_config(config, roots, **values))


@pytest.fixture(autouse=True)
def _isolate_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Keep tests away from the user's config, logs and env overrides."""
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    monkeypatch.delenv(LOG_LEVEL_ENV, raising=False)
    monkeypatch.setattr(
        "photo_darkroom_manager.core.engine.default_logs_dir",
        lambda: tmp_path / "logs",
    )
    yield
    reset_logging_state_for_tests()


def _remove_gitkeep_files(root: Path) -> None:
    """Strip placeholder files used only so empty dirs stay in git."""
    for path in root.glob("**/.gitkeep"):
        path.unlink()


@dataclass(frozen=True, slots=True)
class PhotoSetup:
    """Writable three-root layout (darkroom / showroom / archive) plus helpers."""

    roots: Roots
    engine: Engine

    def darkroom_has_dir(self, relative: Path) -> Path:
        """Resolve ``relative`` under darkroom; assert it exists as a directory."""
        path = self.roots.darkroom / relative
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
    _remove_gitkeep_files(root)
    (
        root
        / "darkroom/Camera/2026/2026-03 publish will fail empty publish dir/PUBLISH"
    ).mkdir(exist_ok=True)
    roots = Roots(
        darkroom=(root / "darkroom").resolve(),
        showroom=(root / "showroom").resolve(),
        archive=(root / "archive").resolve(),
    )
    return PhotoSetup(roots=roots, engine=engine_for(roots))


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
def roots(darkroom_root: Path, showroom_root: Path, archive_root: Path) -> Roots:
    return Roots(
        darkroom=darkroom_root.resolve(),
        showroom=showroom_root.resolve(),
        archive=archive_root.resolve(),
    )


@pytest.fixture
def engine(roots: Roots) -> Engine:
    """Ready engine over the temp ``roots``."""
    return engine_for(roots)


@pytest.fixture
def make_engine() -> MakeEngine:
    """Factory: ``make_engine(roots, **values)`` -> ready engine."""
    return engine_for


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test ``contract`` unless it is explicitly ``internal``.

    ``contract`` tests pin user-visible behaviour the core redesign must keep;
    ``internal`` tests cover private helpers or behaviour planned to change
    (see docs/core-split/ROADMAP.md, Phase 0). Select with ``-m contract``.
    """
    for item in items:
        if item.get_closest_marker("internal") is None:
            item.add_marker(pytest.mark.contract)
