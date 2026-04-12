"""Tests for external app launch (resolve, first image, OpenExternalAppAction)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from photo_darkroom_manager.actions import (
    OpenExternalAppAction,
    PrepareError,
    _find_first_image,
    _resolve_command,
)


def test_resolve_command_empty_template(tmp_path: Path) -> None:
    r = _resolve_command("   ", tmp_path)
    assert isinstance(r, PrepareError)
    assert "empty" in r.message.lower()


def test_resolve_command_folder_placeholder(tmp_path: Path) -> None:
    out = _resolve_command('echo "{folder}"', tmp_path)
    assert isinstance(out, list)
    joined = " ".join(str(p) for p in out)
    assert str(tmp_path.resolve()) in joined


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


def test_resolve_command_unknown_placeholder(tmp_path: Path) -> None:
    r = _resolve_command("{not_a_real_key}", tmp_path)
    assert isinstance(r, PrepareError)
    assert "placeholder" in r.message.lower()


def test_resolve_command_no_first_image(tmp_path: Path) -> None:
    r = _resolve_command("{first_image_in_folder}", tmp_path)
    assert isinstance(r, PrepareError)
    assert "image" in r.message.lower()


def test_resolve_command_first_image_pick_min_name(tmp_path: Path) -> None:
    (tmp_path / "z.jpg").write_bytes(b"")
    (tmp_path / "a.jpg").write_bytes(b"")
    out = _resolve_command("{first_image_in_folder}", tmp_path)
    assert isinstance(out, list)
    joined = " ".join(str(p) for p in out)
    assert "a.jpg" in joined


def test_resolve_command_shlex_bad_quotes(tmp_path: Path) -> None:
    r = _resolve_command('echo "unclosed', tmp_path)
    assert isinstance(r, PrepareError)


def test_find_first_image_none_when_empty(tmp_path: Path) -> None:
    assert _find_first_image(tmp_path) is None


def test_find_first_image_returns_min_by_name(tmp_path: Path) -> None:
    (tmp_path / "m.raw").write_bytes(b"")
    (tmp_path / "a.jpg").write_bytes(b"")
    first = _find_first_image(tmp_path)
    assert first is not None
    assert first.name == "a.jpg"


def test_open_external_prepare_ok_without_first_image_key(tmp_path: Path) -> None:
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    prep = act._prepare()
    assert prep is None


def test_open_external_prepare_error_propagates(tmp_path: Path) -> None:
    act = OpenExternalAppAction("{first_image_in_folder}", tmp_path)
    prep = act._prepare()
    assert isinstance(prep, PrepareError)


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
        "photo_darkroom_manager.actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act._execute(None)
    assert result.success
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
        "photo_darkroom_manager.actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act._execute(None)
    assert result.success


def test_open_external_execute_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_popen(*_a: object, **_kw: object) -> Mock:
        proc = Mock()
        proc.wait = Mock(return_value=7)
        return proc

    monkeypatch.setattr(
        "photo_darkroom_manager.actions.subprocess.Popen",
        fake_popen,
    )
    act = OpenExternalAppAction(f'echo "{tmp_path}"', tmp_path)
    result = act._execute(None)
    assert not result.success
    assert "7" in result.message
    assert result.details is None
