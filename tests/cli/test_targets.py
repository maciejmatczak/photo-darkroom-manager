"""Contract: app/command-line targets (ids, darkroom paths, bare targets)."""

from pathlib import Path

import pytest

from cli.conftest import BATCH, Cli
from photo_darkroom_manager.cli._targets import AmbiguousTargetError, resolve
from photo_darkroom_manager.core.engine import Engine


def _target(cli: Cli, *argv: str, cwd: Path | None = None) -> str:
    """Node id a command addressed, from its JSON output."""
    out = cli("--json", *argv, cwd=cwd)
    assert out.code == 0, out
    result = out.json()["result"]
    return result["request"]["node_id"] if result["kind"] == "plan" else result["id"]


def test_inside_a_batch_folder(cli: Cli) -> None:
    batch = cli.batch("a.jpg")
    assert _target(cli, "archive", ".", cwd=batch) == BATCH


def test_id_from_anywhere(cli: Cli) -> None:
    cli.batch()
    assert _target(cli, "inspect", "id:Camera/2026") == "Camera/2026"


def test_tab_completed_folder_name(cli: Cli) -> None:
    batch = cli.batch()
    assert _target(cli, "inspect", "2026-10 Walk", cwd=batch.parent) == BATCH


def test_ambiguous_target(cli: Cli) -> None:
    cli.batch()
    other = cli.batch("Camera/x.jpg", node_id="Phone/2026/2026-10 x")
    out = cli("--json", "inspect", "Camera", cwd=other)
    assert out.code == 3
    error = out.json()["error"]
    assert error["kind"] == "ambiguous"
    assert "id:Camera" in error["fix"]
    assert "./Camera" in error["fix"]


def test_showroom_path(cli: Cli) -> None:
    showroom = cli.roots.showroom / "2026"
    showroom.mkdir()
    out = cli("--json", "inspect", str(showroom))
    assert out.code == 5
    error = out.json()["error"]
    assert error["kind"] == "outside_darkroom"
    assert str(showroom) in error["message"]
    assert str(cli.roots.darkroom) in error["message"]


def test_empty_id_is_the_root(cli: Cli) -> None:
    cli.batch()
    assert _target(cli, "inspect", "id:") == ""


@pytest.mark.internal
def test_path_reading_follows_on_disk_names(cli: Cli) -> None:
    batch = cli.batch()
    assert _target(cli, "inspect", "./2026-10 walk", cwd=batch.parent) == BATCH


@pytest.mark.internal
def test_bare_name_that_is_only_an_id(cli: Cli) -> None:
    cli.batch()
    assert _target(cli, "inspect", "camera/2026") == "Camera/2026"


@pytest.mark.internal
def test_bare_name_that_is_neither_stays_an_id(cli: Cli, engine: Engine) -> None:
    assert resolve("Drone", cli.home, engine) == "Drone"


@pytest.mark.internal
def test_same_node_both_ways_is_not_ambiguous(cli: Cli, engine: Engine) -> None:
    cli.batch()
    assert resolve("Camera", cli.roots.darkroom, engine) == "Camera"


@pytest.mark.internal
def test_ambiguity_names_both_readings(cli: Cli, engine: Engine) -> None:
    cli.batch()
    other = cli.batch("Camera/x.jpg", node_id="Phone/2026/2026-10 x")
    with pytest.raises(AmbiguousTargetError) as exc:
        resolve("Camera", other, engine)
    assert exc.value.as_id == "Camera"
    assert exc.value.as_path == "Phone/2026/2026-10 x/Camera"
