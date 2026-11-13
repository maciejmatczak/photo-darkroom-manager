"""Contract: engine/jobs and the engine-status busy rule, through the engine."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import MakeEngine, Roots, run_planned

from photo_darkroom_manager.core import engine as engine_module
from photo_darkroom_manager.core import file_utils
from photo_darkroom_manager.core.actions import apps as apps_module
from photo_darkroom_manager.core.actions import rename as rename_module
from photo_darkroom_manager.core.engine import (
    ActionRefusedError,
    Engine,
    EngineBusyError,
    JobView,
    NodeActionResult,
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


def _start_archive(engine: Engine, node_id: str = BATCH) -> JobView:
    return engine.action_archive(engine.action_prepare_archive(node_id))


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
    view = _start_archive(engine)
    assert view.name == "archive"
    assert view.description == BATCH
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"
    assert isinstance(final.result, NodeActionResult)
    assert final.result.result.outcome == "ok"


def test_opening_a_folder_is_not_a_job(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)
    opened: list[Path] = []
    monkeypatch.setattr(apps_module, "_open_in_file_manager", opened.append)
    result = engine.action_open(BATCH)
    assert result.outcome == "ok"
    assert opened == [roots.darkroom / BATCH]
    assert engine.job is None


def test_rename_is_a_job_with_a_job_log(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    plan = engine.action_prepare_rename(BATCH, title="Hike")
    view = engine.action_rename(plan)
    assert view.name == "rename"
    assert view.description == BATCH
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"
    assert (roots.darkroom / "Camera/2026/2026-10 Hike").is_dir()
    assert final.log_path is not None and final.log_path.is_file()


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

    view = _start_archive(engine)
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
        engine.action_tidy(engine.action_prepare_tidy(BATCH))
    assert err.value.label == "scan darkroom root"
    with pytest.raises(EngineBusyError):
        engine.library_scan_start()
    gate.release.set()
    engine.job_wait(5)


def test_next_job_replaces_the_finished_one(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    run_planned(engine, "tidy", BATCH)
    tidy = engine.job
    _start_archive(engine)
    engine.job_wait(5)
    job = engine.job
    assert tidy is not None and job is not None
    assert job.name == "archive"
    assert job.id != tidy.id


def test_finished_job_keeps_its_result(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    done = run_planned(engine, "tidy", BATCH)
    job = engine.job
    assert job is not None
    assert job.state == "done"
    assert job.result == done
    assert job.log_path is not None and job.log_path.is_file()


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


def test_action_that_fails_on_a_file_ends_done(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    real = file_utils.move_file

    def locked(src: Path, dst: Path, *, replace: bool = False) -> None:
        if src.name == "b.jpg":
            raise PermissionError("locked")
        real(src, dst, replace=replace)

    monkeypatch.setattr(file_utils, "move_file", locked)
    result = run_planned(engine, "archive", BATCH).result
    assert result.outcome == "failed"
    assert [m.source.name for m in result.moves.failed] == ["b.jpg"]
    job = engine.job
    assert job is not None and job.state == "done"


def test_a_scan_that_raises_ends_failed(
    roots: Roots, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _batch(roots)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(engine_module, "scan_subtree", boom)
    engine.library_scan_start()
    final = engine.job_wait(5)
    assert final is not None and final.state == "failed"
    assert final.error == "RuntimeError: disk on fire"


def test_nothing_to_tidy_ends_done_with_ok(roots: Roots, engine: Engine) -> None:
    _batch(roots)
    result = run_planned(engine, "tidy", BATCH).result
    assert result.outcome == "ok"
    assert result.moves.done == 0
    job = engine.job
    assert job is not None and job.state == "done"


def test_a_file_in_the_way_at_run_time_is_skipped(roots: Roots, engine: Engine) -> None:
    batch = _batch(roots, "a.jpg", "b.jpg")
    plan = engine.action_prepare_tidy(BATCH)
    (batch / "PHOTOS").mkdir()
    engine.action_tidy(plan)
    final = engine.job_wait(5)
    assert final is not None and final.state == "done"
    result = final.result.result
    assert result.outcome == "ok"


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
    _start_archive(engine)
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
    _start_archive(engine)
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
    _start_archive(engine)
    gate.wait()

    engine.job_cancel()
    cancelling = engine.job
    assert cancelling is not None and cancelling.state == "cancelling"
    gate.release.set()
    final = engine.job_wait(5)

    assert final is not None and final.state == "cancelled"
    result = final.result
    assert isinstance(result, NodeActionResult)
    assert result.result.outcome == "cancelled"
    assert len(result.result.moves.moved) == 11
    assert len(result.result.moves.left) == 29
    assert result.library_refreshed is not None
    assert engine.library_node(BATCH).stats.image_count == 29


def test_cancel_after_the_end(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    run_planned(engine, "tidy", BATCH)
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
    _start_archive(engine)
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

    monkeypatch.setattr(apps_module, "_open_in_file_manager", opened.append)
    monkeypatch.setattr(apps_module.subprocess, "Popen", popen)
    gate = MoveGate(monkeypatch, after=1)
    released.append(gate.release)
    _start_archive(engine)
    gate.wait()

    assert engine.action_open(OTHER).outcome == "ok"
    assert engine.action_edit(OTHER).outcome == "ok"
    assert opened == [roots.darkroom / OTHER]
    assert launched and launched[0][0] == "editor"
    job = engine.job
    assert job is not None and job.name == "archive" and job.active
    gate.release.set()
    engine.job_wait(5)


def test_rename_during_an_archive_is_refused_naming_it(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(3))
    _batch(roots, "x.jpg", node=OTHER)
    gate = MoveGate(monkeypatch, after=1)
    released.append(gate.release)
    _start_archive(engine)
    gate.wait()

    plan = engine.action_prepare_rename(OTHER, title="Walk 2")
    with pytest.raises(EngineBusyError) as err:
        engine.action_rename(plan)

    assert err.value.label == f"archive {BATCH}"
    assert (roots.darkroom / OTHER).is_dir()
    assert not (roots.darkroom / "Camera/2026/2026-11 Walk 2").exists()
    gate.release.set()
    engine.job_wait(5)


class RenameGate:
    """Holds every rename inside its run until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        real = rename_module.run

        def run(plan, answers, job):
            self.reached.set()
            assert self.release.wait(5)
            return real(plan, answers, job)

        monkeypatch.setattr(rename_module, "run", run)


def test_scan_and_config_refused_but_open_allowed_during_a_rename(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
    tmp_path: Path,
) -> None:
    _batch(roots)
    _batch(roots, node=OTHER)
    opened: list[Path] = []
    monkeypatch.setattr(apps_module, "_open_in_file_manager", opened.append)
    gate = RenameGate(monkeypatch)
    released.append(gate.release)
    engine.action_rename(engine.action_prepare_rename(BATCH, title="Hike 2"))
    try:
        assert gate.reached.wait(5)
        with pytest.raises(EngineBusyError) as err:
            engine.library_scan_start()
        assert err.value.label == f"rename {BATCH}"
        with pytest.raises(EngineBusyError):
            engine.config_set("archive", tmp_path / "elsewhere")
        other = engine.action_prepare_rename(OTHER, title="Other")
        with pytest.raises(EngineBusyError):
            engine.action_rename(other)
        assert engine.action_open(OTHER).outcome == "ok"
        assert opened == [roots.darkroom / OTHER]
    finally:
        gate.release.set()
    final = engine.job_wait(5)
    assert final is not None and final.result.result.outcome == "ok"
    engine.library_scan()


# ---------------------------------------------------------------------------
# Conflict policy
# ---------------------------------------------------------------------------


def test_replace_is_publish_only(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg")
    taken = roots.archive / "2026/2026-10 Walk/Camera/a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    plan = engine.action_prepare_archive(BATCH)
    with pytest.raises(ActionRefusedError, match="skip"):
        engine.action_archive(plan, {"existing": "replace"})
    assert engine.job is None


def test_archive_skip_through_the_engine(roots: Roots, engine: Engine) -> None:
    _batch(roots, "a.jpg", "b.jpg")
    taken = roots.archive / "2026/2026-10 Walk/Camera/a.jpg"
    taken.parent.mkdir(parents=True)
    taken.write_bytes(b"old")
    result = run_planned(engine, "archive", BATCH, {"existing": "skip"}).result
    assert result.outcome == "ok"
    assert [m.source.name for m in result.moves.skipped] == ["a.jpg"]
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
    run_planned(engine, "archive", BATCH, {"existing": "skip"})
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
    assert "answers={'existing': 'skip'}" in request
    assert "fingerprint=" in request
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
    assert "state='done'" in finished
    assert "duration_ms=" in finished
    assert lines[-1] == finished


def _app_log(engine: Engine) -> str:
    """Text of the application log files (not the job logs)."""
    return "".join(
        p.read_text(encoding="utf-8") for p in sorted(engine.logs_dir.glob("*.log"))
    )


def test_rename_logs_its_request_and_result_in_its_job_log(
    roots: Roots, engine: Engine
) -> None:
    _batch(roots)
    run_planned(engine, "rename", BATCH, title="Hike")
    job = engine.job
    assert job is not None and job.log_path is not None
    text = job.log_path.read_text(encoding="utf-8")
    assert text.count("event='action_request'") == 1
    assert text.count("event='action_result'") == 1
    assert "Renamed to 2026-10 Hike" in text


def test_tidy_logs_its_request_and_result_once_in_its_job_log(
    roots: Roots, engine: Engine
) -> None:
    _batch(roots, "a.jpg")
    run_planned(engine, "tidy", BATCH)
    job = engine.job
    assert job is not None and job.log_path is not None
    text = job.log_path.read_text(encoding="utf-8")
    assert text.count("event='action_request'") == 1
    assert text.count("event='action_result'") == 1


def test_the_rescan_after_an_archive_logs_to_its_job_log(
    roots: Roots, engine: Engine
) -> None:
    _batch(roots, "a.jpg")
    engine.library_scan()
    run_planned(engine, "archive", BATCH)
    job = engine.job
    assert job is not None and job.log_path is not None
    lines = job.log_path.read_text(encoding="utf-8").splitlines()
    names = [line.split("event='")[1].split("'")[0] for line in lines]
    assert names.index("refresh_started") < names.index("refresh_complete")
    assert names.index("refresh_complete") < names.index("action_result")


def test_log_holds_finished_steps_while_the_job_runs(
    roots: Roots,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    released: list[threading.Event],
) -> None:
    _batch(roots, *_files(40))
    gate = MoveGate(monkeypatch, after=10)
    released.append(gate.release)
    view = _start_archive(engine)
    gate.wait()
    assert view.log_path is not None
    text = view.log_path.read_text(encoding="utf-8")
    assert text.count("event='step_done'") == 10
    assert "job_finished" not in text
    gate.release.set()
    engine.job_wait(5)
