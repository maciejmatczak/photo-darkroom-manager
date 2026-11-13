"""Tests for the shared move helper: answers, failures, late conflicts, cancel."""

from pathlib import Path

import pytest

from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions._moves import (
    CONFLICT_EXISTS,
    CONFLICT_SAME_TARGET,
    FileMove,
    run_moves,
)
from photo_darkroom_manager.core.jobs import Job


def _files(folder: Path, *names: str, content: bytes = b"new") -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / name for name in names]
    for path in paths:
        path.write_bytes(content)
    return paths


def _moves(sources: list[Path], target: Path) -> list[FileMove]:
    return [FileMove(s, target / s.name) for s in sources]


class _CancelAfter(Job):
    """A job that asks itself to stop once *moves* files are done."""

    def __init__(self, moves: int) -> None:
        super().__init__("test")
        self._moves = moves

    def progress(
        self, done: int, total: int | None = None, current: str | None = None
    ) -> None:
        super().progress(done, total, current)
        if done >= self._moves:
            self.cancel()


def test_a_full_run_moves_every_file_and_reports_progress(tmp_path: Path) -> None:
    sources = _files(tmp_path / "src", "a.jpg", "b.jpg")
    job = Job("test")
    report = run_moves(_moves(sources, tmp_path / "dst"), (), on_conflict=None, job=job)
    assert report.outcome == "ok"
    assert [m.source.name for m in report.moved] == ["a.jpg", "b.jpg"]
    assert (tmp_path / "dst/a.jpg").is_file()
    assert job.last_progress.done == 2
    assert job.last_progress.total == 2


def test_a_failed_file_stays_and_the_others_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = _files(tmp_path / "src", "a.jpg", "b.jpg")
    real = file_utils.move_file

    def locked(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "a.jpg":
            raise PermissionError("locked")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", locked)
    report = run_moves(
        _moves(sources, tmp_path / "dst"), (), on_conflict=None, job=Job("test")
    )
    assert report.outcome == "failed"
    ((failed),) = report.failed
    assert failed.source.name == "a.jpg"
    assert "locked" in (failed.reason or "")
    assert sources[0].is_file()
    assert [m.source.name for m in report.moved] == ["b.jpg"]


def test_a_skipped_conflict_stays_where_it_is(tmp_path: Path) -> None:
    (a,) = _files(tmp_path / "src", "a.jpg")
    (taken,) = _files(tmp_path / "dst", "a.jpg", content=b"old")
    conflict = FileMove(a, taken, CONFLICT_EXISTS)
    report = run_moves((), (conflict,), on_conflict="skip", job=Job("test"))
    assert report.outcome == "ok"
    assert report.skipped == (conflict,)
    assert a.read_bytes() == b"new"
    assert taken.read_bytes() == b"old"


def test_replace_puts_the_new_file_in_place(tmp_path: Path) -> None:
    (a,) = _files(tmp_path / "src", "a.jpg")
    (taken,) = _files(tmp_path / "dst", "a.jpg", content=b"old")
    report = run_moves(
        (), (FileMove(a, taken, CONFLICT_EXISTS),), on_conflict="replace", job=Job("t")
    )
    assert [m.target for m in report.replaced] == [taken]
    assert taken.read_bytes() == b"new"
    assert not a.exists()


def test_replace_never_lets_two_files_share_a_target(tmp_path: Path) -> None:
    (a,) = _files(tmp_path / "src", "a.jpg")
    same = FileMove(a, tmp_path / "dst/a.jpg", CONFLICT_SAME_TARGET)
    report = run_moves((), (same,), on_conflict="replace", job=Job("test"))
    assert report.skipped == (same,)
    assert a.is_file()


def test_a_target_taken_since_the_plan_is_skipped(tmp_path: Path) -> None:
    sources = _files(tmp_path / "src", "a.jpg", "b.jpg")
    moves = _moves(sources, tmp_path / "dst")
    _files(tmp_path / "dst", "a.jpg", content=b"late")
    report = run_moves(moves, (), on_conflict=None, job=Job("test"))
    assert report.outcome == "ok"
    assert [m.source.name for m in report.skipped] == ["a.jpg"]
    assert [m.source.name for m in report.moved] == ["b.jpg"]
    assert (tmp_path / "dst/a.jpg").read_bytes() == b"late"


def test_a_late_target_follows_the_answer_to_replace(tmp_path: Path) -> None:
    (a,) = _files(tmp_path / "src", "a.jpg")
    moves = _moves([a], tmp_path / "dst")
    _files(tmp_path / "dst", "a.jpg", content=b"late")
    report = run_moves(moves, (), on_conflict="replace", job=Job("test"))
    assert [m.source.name for m in report.replaced] == ["a.jpg"]
    assert (tmp_path / "dst/a.jpg").read_bytes() == b"new"


def test_a_cancel_stops_between_files(tmp_path: Path) -> None:
    sources = _files(tmp_path / "src", *(f"{i}.jpg" for i in range(5)))
    report = run_moves(
        _moves(sources, tmp_path / "dst"), (), on_conflict=None, job=_CancelAfter(2)
    )
    assert report.outcome == "cancelled"
    assert report.done == 2
    assert len(report.left) == 3
    assert all(m.source.is_file() for m in report.left)
