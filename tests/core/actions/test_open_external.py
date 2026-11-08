"""Tests for external app launch (resolve, first image, OpenExternalAppAction)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from photo_darkroom_manager.core.actions import (
    ActionPlan,
    ActionResult,
    CullAction,
    ExecutionResult,
    Launch,
    OpenExternalAppAction,
)
from photo_darkroom_manager.core.actions._actions import (
    _find_first_image,
    _resolve_command,
)


def _plan(action: OpenExternalAppAction) -> ActionPlan:
    plan = action.prepare()
    assert isinstance(plan, ActionPlan), plan
    return plan


@pytest.mark.internal
def test_execution_result_rescan_node_path_defaults_none() -> None:
    result = ExecutionResult("ok", "ok")
    assert result.rescan_node_path is None


@pytest.mark.internal
def test_resolve_command_empty_template(tmp_path: Path) -> None:
    r = _resolve_command("   ", tmp_path)
    assert isinstance(r, ActionResult)
    assert r.outcome == "refused"
    assert "empty" in r.message.lower()


@pytest.mark.internal
def test_resolve_command_folder_placeholder(tmp_path: Path) -> None:
    out = _resolve_command('echo "{folder}"', tmp_path)
    assert isinstance(out, list)
    joined = " ".join(str(p) for p in out)
    assert str(tmp_path.resolve()) in joined


@pytest.mark.internal
def test_resolve_command_strips_cmd_style_outer_quotes(tmp_path: Path) -> None:
    """posix=False keeps "" around tokens; argv must not contain those quotes."""
    exe = r"C:\Program Files\FastRawViewer.exe"
    template = f'"{exe}" "{{folder}}"'
    out = _resolve_command(template, tmp_path)
    assert isinstance(out, list)
    assert out[0] == exe
    assert out[1] == str(tmp_path.resolve())
    assert not str(out[0]).startswith('"')
    assert not str(out[1]).startswith('"')


@pytest.mark.internal
def test_resolve_command_unknown_placeholder(tmp_path: Path) -> None:
    r = _resolve_command("{not_a_real_key}", tmp_path)
    assert isinstance(r, ActionResult)
    assert r.outcome == "refused"
    assert "placeholder" in r.message.lower()


@pytest.mark.internal
def test_resolve_command_no_first_image(tmp_path: Path) -> None:
    r = _resolve_command("{first_image_in_folder}", tmp_path)
    assert isinstance(r, ActionResult)
    assert r.outcome == "refused"
    assert "image" in r.message.lower()


@pytest.mark.internal
def test_resolve_command_first_image_pick_min_name(tmp_path: Path) -> None:
    (tmp_path / "z.jpg").write_bytes(b"")
    (tmp_path / "a.jpg").write_bytes(b"")
    out = _resolve_command("{first_image_in_folder}", tmp_path)
    assert isinstance(out, list)
    joined = " ".join(str(p) for p in out)
    assert "a.jpg" in joined


@pytest.mark.internal
def test_resolve_command_shlex_bad_quotes(tmp_path: Path) -> None:
    r = _resolve_command('echo "unclosed', tmp_path)
    assert isinstance(r, ActionResult)
    assert r.outcome == "refused"


@pytest.mark.internal
def test_find_first_image_none_when_empty(tmp_path: Path) -> None:
    assert _find_first_image(tmp_path) is None


@pytest.mark.internal
def test_find_first_image_returns_min_by_name(tmp_path: Path) -> None:
    (tmp_path / "m.raw").write_bytes(b"")
    (tmp_path / "a.jpg").write_bytes(b"")
    first = _find_first_image(tmp_path)
    assert first is not None
    assert first.name == "a.jpg"


def test_open_external_prepare_plans_one_launch(tmp_path: Path) -> None:
    plan = _plan(OpenExternalAppAction('edit "{folder}"', tmp_path))
    assert plan.steps == (Launch(("edit", str(tmp_path.resolve()))),)
    assert not plan.changes_files


def test_open_external_prepare_error_propagates(tmp_path: Path) -> None:
    prep = OpenExternalAppAction("{first_image_in_folder}", tmp_path).prepare()
    assert isinstance(prep, ActionResult)
    assert prep.outcome == "refused"


def test_cull_without_a_command(tmp_path: Path) -> None:
    prep = CullAction(None, tmp_path).prepare()
    assert isinstance(prep, ActionResult)
    assert prep.outcome == "refused"
    assert "cull_command" in prep.message


def test_open_external_executes_exactly_the_planned_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    act = OpenExternalAppAction("view {first_image_in_folder}", tmp_path)
    plan = _plan(act)
    (tmp_path / "0-first.jpg").write_bytes(b"")
    seen: list[object] = []

    def fake_popen(argv, **_kw: object) -> Mock:
        seen.append(argv)
        return Mock(wait=Mock(return_value=0))

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions._actions.subprocess.Popen", fake_popen
    )
    result = act.execute(plan)
    assert result.outcome == "ok"
    assert seen == [("view", str((tmp_path / "a.jpg").resolve()))]


def test_open_external_execute_uses_devnull_and_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    procs: list[Mock] = []

    def fake_popen(*_a: object, **kw: object) -> Mock:
        captured.update(kw)
        proc = Mock()
        proc.wait = Mock(return_value=0)
        procs.append(proc)
        return proc

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions._actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act.execute(_plan(act))
    assert result.success
    assert result.rescan_node_path is None
    assert captured["stdout"] is subprocess.DEVNULL
    assert captured["stderr"] is subprocess.DEVNULL
    assert len(procs) == 1
    procs[0].wait.assert_called_once_with(timeout=0.5)


def test_open_external_execute_timeout_means_still_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_popen(*_a: object, **_kw: object) -> Mock:
        proc = Mock()
        proc.wait = Mock(
            side_effect=subprocess.TimeoutExpired(cmd="x", timeout=0.5),
        )
        return proc

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions._actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act.execute(_plan(act))
    assert result.success
    assert result.rescan_node_path is None


def test_open_external_execute_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_popen(*_a: object, **_kw: object) -> Mock:
        proc = Mock()
        proc.wait = Mock(return_value=7)
        return proc

    monkeypatch.setattr(
        "photo_darkroom_manager.core.actions._actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act.execute(_plan(act))
    assert not result.success
    assert result.rescan_node_path is None
    assert "7" in result.message
    assert result.details is None
