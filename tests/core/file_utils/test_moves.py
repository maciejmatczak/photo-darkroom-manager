"""Tests for the safe file mover in file_utils."""

import errno
import os
import shutil
from pathlib import Path

import pytest

from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.file_utils import (
    PARTIAL_SUFFIX,
    MoveOutcome,
    TargetExistsError,
    move_file,
    move_files,
)


def _file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _partials(folder: Path) -> list[Path]:
    return [p for p in folder.rglob(f"*{PARTIAL_SUFFIX}")]


@pytest.fixture
def other_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every move of a source file look like a move to another drive.

    The rename of the partial copy into place stays a same-drive rename.
    """
    real = file_utils._rename

    def rename(source: Path, target: Path, *, replace: bool) -> None:
        if not source.name.endswith(PARTIAL_SUFFIX):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        real(source, target, replace=replace)

    monkeypatch.setattr(file_utils, "_rename", rename)


# -- same drive --------------------------------------------------------------


def test_move_creates_target_folders(tmp_path: Path) -> None:
    src = _file(tmp_path / "src" / "f.txt", "data")
    dst = tmp_path / "archive" / "p" / "q" / "f.txt"

    report = move_files([(src, dst)])

    assert report.done == ((src, dst),)
    assert report.failed == report.skipped == report.left == ()
    assert dst.read_text(encoding="utf-8") == "data"
    assert not src.exists()


def test_move_keeps_going_after_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pairs = [
        (_file(tmp_path / n, n), tmp_path / "out" / n)
        for n in ("a.txt", "b.txt", "c.txt")
    ]
    real = file_utils.move_file

    def flaky(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "b.txt":
            raise PermissionError("locked")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", flaky)
    report = move_files(pairs)

    assert report.done == (pairs[0], pairs[2])
    assert [(s, d) for s, d, _ in report.failed] == [pairs[1]]
    assert "locked" in report.failed[0][2]
    assert (tmp_path / "b.txt").exists()


def test_existing_target_is_skipped_not_overwritten(tmp_path: Path) -> None:
    src = _file(tmp_path / "new.txt", "new")
    dst = _file(tmp_path / "out" / "new.txt", "old")

    report = move_files([(src, dst)])

    assert report.skipped == ((src, dst),)
    assert report.done == ()
    assert src.read_text(encoding="utf-8") == "new"
    assert dst.read_text(encoding="utf-8") == "old"


def test_target_created_after_planning_is_never_overwritten(tmp_path: Path) -> None:
    """A target that appears between planning and moving is a conflict."""
    pairs = [(_file(tmp_path / n, n), tmp_path / "out" / n) for n in ("a.txt", "b.txt")]
    seen: list[MoveOutcome] = []

    def on_move(outcome: MoveOutcome) -> None:
        seen.append(outcome)
        _file(tmp_path / "out" / "b.txt", "late")

    report = move_files(pairs, on_move=on_move)

    assert report.done == (pairs[0],)
    assert report.skipped == (pairs[1],)
    assert (tmp_path / "out" / "b.txt").read_text(encoding="utf-8") == "late"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "b.txt"
    assert [o.status for o in seen] == ["done", "skipped"]


def test_replace_swaps_in_the_new_file(tmp_path: Path) -> None:
    src = _file(tmp_path / "new.txt", "new")
    dst = _file(tmp_path / "out" / "new.txt", "old")

    report = move_files([(src, dst)], replace=True)

    assert report.done == ((src, dst),)
    assert dst.read_text(encoding="utf-8") == "new"
    assert not src.exists()


def test_move_file_raises_on_existing_target(tmp_path: Path) -> None:
    src = _file(tmp_path / "a.txt", "a")
    dst = _file(tmp_path / "out" / "a.txt", "old")

    with pytest.raises(TargetExistsError):
        move_file(src, dst)


# -- stopping ------------------------------------------------------------------


def test_stop_reports_done_and_left(tmp_path: Path) -> None:
    pairs = [
        (_file(tmp_path / f"{i}.txt", str(i)), tmp_path / "out" / f"{i}.txt")
        for i in range(5)
    ]
    moved: list[MoveOutcome] = []

    report = move_files(pairs, stop=lambda: len(moved) == 2, on_move=moved.append)

    assert report.done == tuple(pairs[:2])
    assert report.left == tuple(pairs[2:])
    assert report.cancelled
    assert all(src.exists() for src, _ in pairs[2:])


# -- across drives -----------------------------------------------------------


@pytest.mark.usefixtures("other_drive")
def test_cross_drive_move_copies_then_removes_source(tmp_path: Path) -> None:
    src = _file(tmp_path / "d" / "clip.mov", "video")
    dst = tmp_path / "e" / "clip.mov"

    report = move_files([(src, dst)])

    assert report.done == ((src, dst),)
    assert dst.read_text(encoding="utf-8") == "video"
    assert not src.exists()
    assert _partials(tmp_path) == []


@pytest.mark.usefixtures("other_drive")
def test_short_copy_keeps_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _file(tmp_path / "d" / "clip.mov", "full video")
    dst = tmp_path / "e" / "clip.mov"

    def short_copy(source: Path, copy: Path) -> None:
        Path(copy).write_text("full", encoding="utf-8")

    monkeypatch.setattr(shutil, "copyfile", short_copy)
    report = move_files([(src, dst)])

    assert report.done == ()
    ((_, _, reason),) = report.failed
    assert "source kept" in reason
    assert src.read_text(encoding="utf-8") == "full video"
    assert not dst.exists()
    assert _partials(tmp_path) == []


@pytest.mark.usefixtures("other_drive")
def test_failing_copy_keeps_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _file(tmp_path / "d" / "clip.mov", "video")
    dst = tmp_path / "e" / "clip.mov"

    def disk_full(source: Path, copy: Path) -> None:
        Path(copy).write_text("vi", encoding="utf-8")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(shutil, "copyfile", disk_full)
    report = move_files([(src, dst)])

    ((_, _, reason),) = report.failed
    assert "No space left" in reason
    assert src.exists()
    assert not dst.exists()
    assert _partials(tmp_path) == []


@pytest.mark.usefixtures("other_drive")
def test_failing_replace_keeps_the_old_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _file(tmp_path / "publish" / "a.jpg", "new")
    dst = _file(tmp_path / "showroom" / "a.jpg", "old")

    def broken(source: Path, copy: Path) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(shutil, "copyfile", broken)
    report = move_files([(src, dst)], replace=True)

    assert len(report.failed) == 1
    assert dst.read_text(encoding="utf-8") == "old"
    assert src.read_text(encoding="utf-8") == "new"


@pytest.mark.usefixtures("other_drive")
def test_cross_drive_replace(tmp_path: Path) -> None:
    src = _file(tmp_path / "publish" / "a.jpg", "new")
    dst = _file(tmp_path / "showroom" / "a.jpg", "old")

    report = move_files([(src, dst)], replace=True)

    assert report.done == ((src, dst),)
    assert dst.read_text(encoding="utf-8") == "new"
    assert not src.exists()


@pytest.mark.usefixtures("other_drive")
def test_refused_timestamps_do_not_fail_the_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _file(tmp_path / "d" / "a.jpg", "data")
    dst = tmp_path / "e" / "a.jpg"

    def refuse(source: Path, copy: Path) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(shutil, "copystat", refuse)
    report = move_files([(src, dst)])

    assert report.done == ((src, dst),)
    assert dst.read_text(encoding="utf-8") == "data"


@pytest.mark.usefixtures("other_drive")
def test_rename_into_place_retries_while_the_copy_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _file(tmp_path / "d" / "a.jpg", "data")
    dst = tmp_path / "e" / "a.jpg"
    monkeypatch.setattr(file_utils, "_RENAME_PAUSE_S", 0)
    real_rename = os.rename
    attempts: list[str] = []

    def held_twice(source: str | Path, target: str | Path) -> None:
        if str(source).endswith(PARTIAL_SUFFIX) and len(attempts) < 2:
            attempts.append(str(source))
            raise PermissionError(errno.EACCES, "being used by another process")
        real_rename(source, target)

    monkeypatch.setattr(os, "rename", held_twice)
    report = move_files([(src, dst)])

    assert report.done == ((src, dst),)
    assert len(attempts) == 2
    assert dst.read_text(encoding="utf-8") == "data"
