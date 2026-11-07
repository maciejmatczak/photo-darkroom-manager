"""Contract: engine/jobs and the engine-status busy rule, through the engine."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import MakeEngine, Roots

from photo_darkroom_manager.core import actions as actions_module
from photo_darkroom_manager.core import engine as engine_module
from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions import ExecutionResult, Move
from photo_darkroom_manager.core.engine import (
    Engine,
    EngineBusyError,
    PolicyNotSupportedError,
    ScanResult,
)
from photo_darkroom_manager.core.jobs import Progress

BATCH = "Camera/2026/2026-10 Walk"
OTHER = "Camera/2026/2026-11 Hike"


def _batch(roots: Roots, *files: str, node: str = BATCH) -> Path:
    path = roots.darkroom / node
    path.mkdir(parents=True, exist_ok=True)
    for name in files:
        (path / name).write_bytes(name.encode())
    return path


def _files(n: int) -> list[str]:
    return [f"{i:03}.jpg" for i in range(n)]


class MoveGate:
    """Holds the mover after *after* files until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, after: int) -> None:
        self.after = after
        self.moved = 0
        self.reached = threading.Event()
        self.release = threading.Event()
        real = file_utils.move_file

        def move(src: Path, dst: Path, *, replace: bool = False) -> None:
            if self.moved == self.after:
                self.reached.set()
                assert self.release.wait(5)
            real(src, dst, replace=replace)
            self.moved += 1

        monkeypatch.setattr(file_utils, "move_file", move)

    def wait(self) -> None:
        assert self.reached.wait(5)


class ScanGate:
    """Holds every scan inside its first folder until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        real = engine_module.scan_subtree

        def scan(root, node_id, kind, *, visit=None):
            def held(folder_id: str) -> None:
                if visit is not None:
                    visit(folder_id)
                self.reached.set()
                assert self.release.wait(5)

            return real(root, node_id, kind, visit=held)

        monkeypatch.setattr(engine_module, "scan_subtree", scan)

    def wait(self) -> None:
        assert self.reached.wait(5)


@pytest.fixture
def released() -> Iterator[list[threading.Event]]:
    """Events set at teardown so no job thread outlives a failing test."""
    events: list[threading.Event] = []
    yield events
    for event in events:
        event.set()


# ---------------------------------------------------------------------------
# What runs as a job
# ---------------------------------------------------------------------------


def test_archive_is_a_job(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    view = engine.action_start(engine.action_archive(BATCH))
    assert view.name == "archive"
    assert view.description == BATCH
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"
    assert isinstance(final.result, ExecutionResult)
    assert final.result.outcome == "ok"


def test_opening_a_folder_is_not_a_job(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)
    opened: list[Path] = []
    monkeypatch.setattr(actions_module, "_open_folder", opened.append)
    result = engine.action_apply(engine.action_open(BATCH))
    assert result.outcome == "ok"
    assert opened == [roots.darkroom / BATCH]
    assert engine.job is None
    with pytest.raises(ValueError, match="runs at once"):
        engine.action_start(engine.action_open(BATCH))


# ---------------------------------------------------------------------------
# Starting, one at a time, reading
# ---------------------------------------------------------------------------


def test_start_returns_while_files_are_moved(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(5))
    engine.library_scan()
    gate = MoveGate(monkeypatch, after=2)
    released.append(gate.release)

    view = engine.action_start(engine.action_archive(BATCH))
    gate.wait()

    assert view.state == "new"
    running = engine.job
    assert running is not None and running.state == "running"
    assert engine.library_node(BATCH).kind == "batch"
    gate.release.set()
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"


def test_second_job_while_busy_names_the_scan(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, "a.jpg")
    gate = ScanGate(monkeypatch)
    released.append(gate.release)
    engine.library_scan_start()
    gate.wait()

    with pytest.raises(EngineBusyError) as err:
        engine.action_start(engine.action_tidy(BATCH))
    assert err.value.job.name == "scan"
    with pytest.raises(EngineBusyError):
        engine.library_scan_start()
    gate.release.set()
    engine.job_wait(5)


def test_next_job_replaces_the_finished_one(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    engine.action_apply(engine.action_tidy(BATCH))
    tidy = engine.job
    engine.action_start(engine.action_archive(BATCH))
    engine.job_wait(5)
    job = engine.job
    assert tidy is not None and job is not None
    assert job.name == "archive"
    assert job.id != tidy.id


def test_finished_job_keeps_its_result(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    result = engine.action_apply(engine.action_tidy(BATCH))
    job = engine.job
    assert job is not None
    assert job.state == "done"
    assert job.result == result
    assert job.log_path is not None and job.log_path.is_file()


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


def test_action_that_fails_on_a_file_ends_failed(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    real = file_utils.move_file

    def locked(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "b.jpg":
            raise PermissionError("locked")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", locked)
    result = engine.action_apply(engine.action_archive(BATCH))
    assert result.outcome == "failed"
    job = engine.job
    assert job is not None and job.state == "failed"


def test_nothing_to_tidy_ends_done_with_noop(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    result = engine.action_apply(engine.action_tidy(BATCH))
    assert result.outcome == "noop"
    job = engine.job
    assert job is not None and job.state == "done"


def test_refused_conflict_ends_done(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg")
    (batch / "PHOTOS").mkdir()
    (batch / "PHOTOS" / "a.jpg").write_bytes(b"other")
    result = engine.action_apply(engine.action_tidy(BATCH))
    assert result.outcome == "refused"
    assert [c.move.source.name for c in result.conflicts] == ["a.jpg"]
    job = engine.job
    assert job is not None and job.state == "done"


# ---------------------------------------------------------------------------
# Progress, waiting, cancelling
# ---------------------------------------------------------------------------


def test_archive_progress(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(40))
    gate = MoveGate(monkeypatch, after=10)
    released.append(gate.release)
    engine.action_start(engine.action_archive(BATCH))
    gate.wait()

    job = engine.job
    assert job is not None
    assert job.progress == Progress(10, 40, "009.jpg")
    gate.release.set()
    engine.job_wait(5)


def test_scan_progress_has_no_total(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots)
    gate = ScanGate(monkeypatch)
    released.append(gate.release)
    engine.library_scan_start()
    gate.wait()
    job = engine.job
    assert job is not None
    assert job.progress.total is None
    assert job.progress.done >= 1
    assert engine.library_scanning
    gate.release.set()
    engine.job_wait(5)
    assert not engine.library_scanning


def test_wait_with_a_limit(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(3))
    gate = MoveGate(monkeypatch, after=1)
    released.append(gate.release)
    engine.action_start(engine.action_archive(BATCH))
    gate.wait()
    view = engine.job_wait(0.05)
    assert view is not None and view.state == "running"
    gate.release.set()
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"


def test_cancel_an_archive(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    """Cancel after 10 of 40: cancelled, 10 moved, 30 left, tree rescanned."""
    _batch(roots, *_files(40))
    engine.library_scan()
    gate = MoveGate(monkeypatch, after=10)
    released.append(gate.release)
    engine.action_start(engine.action_archive(BATCH))
    gate.wait()

    engine.job_cancel()
    cancelling = engine.job
    assert cancelling is not None and cancelling.state == "cancelling"
    gate.release.set()
    final = engine.job_wait(5)

    assert final is not None and final.state == "cancelled"
    result = final.result
    assert isinstance(result, ExecutionResult)
    assert result.outcome == "cancelled"
    assert len([s for s in result.done if isinstance(s, Move)]) == 11
    assert len(result.left) == 29
    assert result.library_refreshed is not None
    assert engine.library_node(BATCH).stats.image_count == 29


def test_cancel_after_the_end(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    engine.action_apply(engine.action_tidy(BATCH))
    engine.job_cancel()
    job = engine.job
    assert job is not None and job.state == "done"


def test_blocking_scan_leaves_a_finished_scan(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    engine.library_scan()
    job = engine.job
    assert job is not None
    assert job.name == "scan"
    assert job.state == "done"
    assert job.result == ScanResult("")


# ---------------------------------------------------------------------------
# Busy rule: edits refused, open, cull and edit allowed
# ---------------------------------------------------------------------------


def test_config_edit_refused_during_an_archive(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
    tmp_path: Path,
) -> None:
    _batch(roots, *_files(3))
    gate = MoveGate(monkeypatch, after=1)
    released.append(gate.release)
    engine.action_start(engine.action_archive(BATCH))
    gate.wait()
    with pytest.raises(EngineBusyError):
        engine.config_set("archive", tmp_path / "elsewhere")
    assert engine.archive == roots.archive
    gate.release.set()
    engine.job_wait(5)


def test_open_and_edit_during_an_archive(
    roots: Roots,
    make_engine: MakeEngine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(3))
    _batch(roots, "x.jpg", node=OTHER)
    engine = make_engine(roots, edit_command="editor {folder}")
    opened: list[Path] = []
    launched: list[tuple[str, ...]] = []

    class FakeProc:
        def wait(self, timeout: float) -> int:
            return 0

    def popen(argv, **kwargs):
        launched.append(tuple(argv))
        return FakeProc()

    monkeypatch.setattr(actions_module, "_open_folder", opened.append)
    monkeypatch.setattr(actions_module.subprocess, "Popen", popen)
    gate = MoveGate(monkeypatch, after=1)
    released.append(gate.release)
    engine.action_start(engine.action_archive(BATCH))
    gate.wait()

    assert engine.action_apply(engine.action_open(OTHER)).outcome == "ok"
    assert engine.action_apply(engine.action_edit(OTHER)).outcome == "ok"
    assert opened == [roots.darkroom / OTHER]
    assert launched and launched[0][0] == "editor"
    job = engine.job
    assert job is not None and job.name == "archive" and job.active
    gate.release.set()
    engine.job_wait(5)


# ---------------------------------------------------------------------------
# Conflict policy
# ---------------------------------------------------------------------------


def test_replace_is_publish_only(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    with pytest.raises(PolicyNotSupportedError) as err:
        engine.action_start(engine.action_archive(BATCH), policy="replace")
    assert err.value.supported == ("refuse", "skip")
    assert engine.job is None


def test_archive_skip_through_the_engine(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    taken = roots.archive / "2026/2026-10 Walk/Camera/a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    result = engine.action_apply(engine.action_archive(BATCH), policy="skip")
    assert result.outcome == "ok"
    assert [c.move.source.name for c in result.skipped] == ["a.jpg"]
    assert taken.read_bytes() == b"old"


# ---------------------------------------------------------------------------
# app/job-log through the engine
# ---------------------------------------------------------------------------


def test_partial_archive_log_lists_every_step(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, *_files(5))
    archived = roots.archive / "2026/2026-10 Walk/Camera"
    archived.mkdir(parents=True)
    for name in ("001.jpg", "003.jpg"):
        (archived / name).write_bytes(b"old")
    real = file_utils.move_file

    def full_disk(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "004.jpg":
            raise OSError(28, "No space left on device")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", full_disk)
    engine.action_apply(engine.action_archive(BATCH), policy="skip")
    job = engine.job
    assert job is not None and job.log_path is not None
    assert job.log_path.parent == engine.logs_dir / "jobs"
    assert job.log_path.name.endswith("_archive_Camera-2026-2026-10-Walk.log")
    lines = job.log_path.read_text(encoding="utf-8").splitlines()

    def events(name: str) -> list[str]:
        return [line for line in lines if f"event='{name}'" in line]

    (started,) = events("job_started")
    assert "name='archive'" in started
    (request,) = events("action_request")
    assert "policy='skip'" in request
    assert "summary='Archive 3 files, 2 already in the archive'" in request
    done = events("step_done")
    assert len(done) == 2
    assert all("source=" in line and "target=" in line for line in done)
    skipped = events("step_skipped")
    assert len(skipped) == 2
    assert all(any(n in s for s in skipped) for n in ("001.jpg", "003.jpg"))
    (failed,) = events("step_failed")
    assert "004.jpg" in failed and "No space left" in failed
    (result,) = events("action_result")
    assert "outcome='failed'" in result
    (finished,) = events("job_finished")
    assert "state='failed'" in finished
    assert "duration_ms=" in finished
    assert lines[-1] == finished


def test_log_holds_finished_steps_while_the_job_runs(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(40))
    gate = MoveGate(monkeypatch, after=10)
    released.append(gate.release)
    view = engine.action_start(engine.action_archive(BATCH))
    gate.wait()
    assert view.log_path is not None
    text = view.log_path.read_text(encoding="utf-8")
    assert text.count("event='step_done'") == 10
    assert "job_finished" not in text
    gate.release.set()
    engine.job_wait(5)
