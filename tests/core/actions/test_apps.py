"""Contract: app/action-open-folder and app/action-open-ext-app (direct actions)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from photo_darkroom_manager.core.actions import ActionRefusedError, apps


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Folders passed to the system file manager (patched)."""
    seen: list[Path] = []
    monkeypatch.setattr(apps, "_open_in_file_manager", seen.append)
    return seen


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Argument lists started as external apps (patched; they run on)."""
    seen: list[tuple[str, ...]] = []

    def fake_popen(argv: tuple[str, ...], **kw: object) -> Mock:
        assert kw["stdout"] is subprocess.DEVNULL
        assert kw["stderr"] is subprocess.DEVNULL
        seen.append(argv)
        return Mock(wait=Mock(side_effect=subprocess.TimeoutExpired("x", 0.5)))

    monkeypatch.setattr(apps.subprocess, "Popen", fake_popen)
    return seen


def _snapshot(root: Path) -> list[Path]:
    return sorted(root.rglob("*"))


# ---------------------------------------------------------------------------
# app/action-open-folder
# ---------------------------------------------------------------------------


def test_open_a_year(tmp_path: Path, opened: list[Path]) -> None:
    year = tmp_path / "Camera" / "2026"
    (year / "2026-10 Walk").mkdir(parents=True)
    before = _snapshot(tmp_path)
    result = apps.open_folder(year)
    assert result.outcome == "ok"
    assert result.folder == year
    assert opened == [year]
    assert _snapshot(tmp_path) == before


def test_a_removed_folder_is_refused_naming_it(
    tmp_path: Path, opened: list[Path]
) -> None:
    gone = tmp_path / "Camera" / "2026" / "2026-10 Walk"
    with pytest.raises(ActionRefusedError, match="2026-10 Walk"):
        apps.open_folder(gone)
    assert opened == []


@pytest.mark.internal
def test_a_file_manager_failure_is_a_failed_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: Path) -> None:
        raise OSError("no file manager")

    monkeypatch.setattr(apps, "_open_in_file_manager", broken)
    result = apps.open_folder(tmp_path)
    assert result.outcome == "failed"
    assert "no file manager" in result.message


# ---------------------------------------------------------------------------
# app/action-open-ext-app
# ---------------------------------------------------------------------------


def test_edit_a_batch(tmp_path: Path, started: list[tuple[str, ...]]) -> None:
    result = apps.open_external_app('editor "{folder}"', tmp_path)
    assert result.outcome == "ok"
    assert started == [("editor", str(tmp_path.resolve()))]
    assert result.command == started[0]
    assert result.exit_code is None


def test_the_first_image_by_name(
    tmp_path: Path, started: list[tuple[str, ...]]
) -> None:
    (tmp_path / "b.jpg").write_bytes(b"")
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    apps.open_external_app("view {first_image_in_folder}", tmp_path)
    assert started == [("view", str((tmp_path / "a.jpg").resolve()))]


def test_no_image_directly_in_the_folder_is_refused(
    tmp_path: Path, started: list[tuple[str, ...]]
) -> None:
    (tmp_path / "PHOTOS").mkdir()
    (tmp_path / "PHOTOS" / "a.jpg").write_bytes(b"")
    with pytest.raises(ActionRefusedError, match="No image found"):
        apps.open_external_app("view {first_image_in_folder}", tmp_path)
    assert started == []


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("   ", "empty"),
        ("{not_a_real_key}", "placeholder"),
        ('echo "unclosed', "quoting"),
    ],
)
def test_a_bad_command_is_refused(
    tmp_path: Path, started: list[tuple[str, ...]], command: str, message: str
) -> None:
    with pytest.raises(ActionRefusedError, match=message):
        apps.open_external_app(command, tmp_path)
    assert started == []


@pytest.mark.internal
def test_windows_style_quotes_are_not_passed_on(
    tmp_path: Path, started: list[tuple[str, ...]]
) -> None:
    exe = r"C:\Program Files\FastRawViewer.exe"
    apps.open_external_app(f'"{exe}" "{{folder}}"', tmp_path)
    assert started == [(exe, str(tmp_path.resolve()))]


def test_an_app_exiting_with_an_error_is_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        apps.subprocess, "Popen", lambda *_a, **_k: Mock(wait=Mock(return_value=7))
    )
    result = apps.open_external_app('editor "{folder}"', tmp_path)
    assert result.outcome == "failed"
    assert result.exit_code == 7
    assert "7" in result.message


def test_an_app_that_cannot_start_is_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(*_a: object, **_k: object) -> None:
        raise FileNotFoundError("no such program")

    monkeypatch.setattr(apps.subprocess, "Popen", missing)
    result = apps.open_external_app('nothere "{folder}"', tmp_path)
    assert result.outcome == "failed"
    assert "nothere" in result.message
