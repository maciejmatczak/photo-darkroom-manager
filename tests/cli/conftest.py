"""Fixtures for driving the CLI in-process against temporary roots."""

import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import Roots, write_config

from photo_darkroom_manager.cli import run

BATCH = "Camera/2026/2026-10 Walk"


@dataclass(frozen=True)
class Run:
    code: int
    out: str
    err: str

    def json(self) -> dict:
        return json.loads(self.out)


@dataclass(frozen=True)
class Cli:
    """Runs ``darkroom --config CONFIG ARGV...`` in *cwd* (default: home)."""

    roots: Roots
    config: Path
    home: Path

    def __call__(self, *argv: str, cwd: Path | None = None) -> Run:
        out, err = io.StringIO(), io.StringIO()
        code = run(
            ["--config", str(self.config), *argv],
            cwd=cwd or self.home,
            stdout=out,
            stderr=err,
        )
        return Run(code, out.getvalue(), err.getvalue())

    def batch(self, *files: str, node_id: str = BATCH) -> Path:
        path = self.roots.darkroom / node_id
        path.mkdir(parents=True, exist_ok=True)
        for name in files:
            (path / name).parent.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(name.encode())
        return path


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "home"
    path.mkdir()
    return path


@pytest.fixture
def cli(roots: Roots, tmp_path: Path, home: Path) -> Cli:
    return Cli(roots, write_config(tmp_path / "config.yaml", roots), home)
