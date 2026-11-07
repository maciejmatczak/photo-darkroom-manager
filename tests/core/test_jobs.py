"""Tests for the job slot, with plain callables and no darkroom."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import pytest

from photo_darkroom_manager.core.jobs import (
    NO_JOB,
    JobBusyError,
    JobCancelled,
    JobContext,
    JobSlot,
    JobState,
    Progress,
    job_log_path,
)

pytestmark = pytest.mark.internal


class Gate:
    """Lets a test hold a job's work at a known point."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def hold(self, job: JobContext) -> str:
        self.entered.set()
        assert self.release.wait(5)
        return "held"


def _started(slot: JobSlot, gate: Gate, kind: str = "scan"):
    view = slot.start(gate.hold, name=kind, description="Camera")
    assert gate.entered.wait(5)
    return view


def test_no_job_before_the_first() -> None:
    slot = JobSlot()
    assert slot.view is None
    assert slot.busy is None
    assert slot.wait() is None
    slot.cancel()


def test_start_returns_at_once_as_new() -> None:
    slot = JobSlot()
    gate = Gate()
    view = slot.start(gate.hold, name="archive", description="Camera/2026/2026-10 Walk")
    assert view.state == "new"
    assert view.name == "archive"
    assert view.description == "Camera/2026/2026-10 Walk"
    assert view.progress == Progress()
    assert view.finished_at is None
    assert gate.entered.wait(5)
    assert slot.view is not None and slot.view.state == "running"
    gate.release.set()
    final = slot.wait(5)
    assert final is not None
    assert final.state == "done"
    assert final.result == "held"
    assert final.finished_at is not None


def test_one_job_at_a_time_names_the_running_job() -> None:
    slot = JobSlot()
    gate = Gate()
    running = _started(slot, gate, "scan")
    with pytest.raises(JobBusyError) as err:
        slot.start(lambda job: None, name="tidy", description="Camera")
    assert err.value.job.id == running.id
    assert err.value.job.name == "scan"
    with pytest.raises(JobBusyError):
        slot.require_idle()
    gate.release.set()
    slot.wait(5)
    slot.require_idle()


def test_next_job_replaces_the_finished_one() -> None:
    slot = JobSlot()
    first = slot.start(lambda job: 1, name="tidy", description="a")
    slot.wait(5)
    second = slot.start(lambda job: 2, name="archive", description="b")
    slot.wait(5)
    view = slot.view
    assert view is not None
    assert view.id == second.id != first.id
    assert view.name == "archive"
    assert view.result == 2


def test_snapshot_does_not_change() -> None:
    slot = JobSlot()
    gate = Gate()
    _started(slot, gate)
    kept = slot.view
    gate.release.set()
    slot.wait(5)
    assert kept is not None and kept.state == "running"
    assert slot.view is not None and slot.view.state == "done"


def test_progress_is_reported() -> None:
    slot = JobSlot()
    gate = Gate()

    def work(job: JobContext) -> None:
        job.progress(10, 40, "a.jpg")
        gate.hold(job)

    slot.start(work, name="archive", description="x")
    assert gate.entered.wait(5)
    assert slot.view is not None
    assert slot.view.progress == Progress(10, 40, "a.jpg")
    gate.release.set()
    slot.wait(5)


def test_wait_with_a_limit_returns_while_running() -> None:
    slot = JobSlot()
    gate = Gate()
    _started(slot, gate)
    view = slot.wait(0.05)
    assert view is not None and view.state == "running"
    gate.release.set()
    final = slot.wait()
    assert final is not None and final.state == "done"


def test_cancel_before_the_work_runs() -> None:
    slot = JobSlot()
    seen: list[bool] = []
    hold = threading.Event()

    def work(job: JobContext) -> None:
        assert hold.wait(5)
        seen.append(job.cancelled)
        raise JobCancelled

    slot.start(work, name="scan", description="")
    slot.cancel()
    assert slot.view is not None and slot.view.state == "cancelling"
    hold.set()
    final = slot.wait(5)
    assert seen == [True]
    assert final is not None and final.state == "cancelled"


def test_cancel_during_a_run_stops_between_steps() -> None:
    slot = JobSlot()
    step = threading.Event()
    steps: list[int] = []

    def work(job: JobContext) -> list[int]:
        for i in range(100):
            if job.cancelled:
                raise JobCancelled
            steps.append(i)
            if i == 3:
                step.set()
                while not job.cancelled:
                    pass
        return steps

    slot.start(work, name="scan", description="")
    assert step.wait(5)
    slot.cancel()
    final = slot.wait(5)
    assert final is not None and final.state == "cancelled"
    assert steps == [0, 1, 2, 3]


def test_cancel_after_the_end_keeps_the_state() -> None:
    slot = JobSlot()
    slot.start(lambda job: None, name="tidy", description="")
    slot.wait(5)
    slot.cancel()
    assert slot.view is not None and slot.view.state == "done"


@pytest.mark.parametrize(
    ("result", "state"),
    [
        ("ok", "done"),
        ("noop", "done"),
        ("refused", "done"),
        ("cancelled", "cancelled"),
        ("failed", "failed"),
    ],
)
def test_results_map_to_final_states(result: str, state: JobState) -> None:
    mapping: dict[str, JobState] = {"cancelled": "cancelled", "failed": "failed"}
    slot = JobSlot()
    slot.start(
        lambda job: result,
        name="tidy",
        description="",
        state_of=lambda r: mapping.get(r, "done"),
    )
    final = slot.wait(5)
    assert final is not None
    assert final.state == state
    assert final.result == result


def test_an_exception_ends_the_job_failed() -> None:
    def boom(job: JobContext) -> None:
        raise RuntimeError("disk on fire")

    slot = JobSlot()
    slot.start(boom, name="archive", description="")
    final = slot.wait(5)
    assert final is not None
    assert final.state == "failed"
    assert final.error == "RuntimeError: disk on fire"
    assert final.result is None


def test_a_finished_state_never_changes() -> None:
    slot = JobSlot()
    holder: list[JobContext] = []
    slot.start(holder.append, name="tidy", description="")
    slot.wait(5)
    holder[0].progress(5, 5)
    view = slot.view
    assert view is not None and view.state == "done" and view.progress == Progress()


def test_job_log_path_is_set_when_logs_dir_given(tmp_path: Path) -> None:
    slot = JobSlot(tmp_path / "jobs")
    view = slot.start(
        lambda job: None, name="archive", description="Camera/2026/2026-10 Walk"
    )
    slot.wait(5)
    assert view.log_path is not None
    assert view.log_path.is_file()
    assert view.log_path.parent == tmp_path / "jobs"
    assert view.log_path.name.endswith("_archive_Camera-2026-2026-10-Walk.log")


# ---------------------------------------------------------------------------
# Job logs
# ---------------------------------------------------------------------------

STARTED = datetime(2026, 11, 7, 14, 30, 12)


@pytest.mark.parametrize(
    ("name", "description", "file"),
    [
        ("scan", "", "2026-11-07_143012_scan.log"),
        (
            "archive",
            "Camera/2026/2026-10 Walk",
            "2026-11-07_143012_archive_Camera-2026-2026-10-Walk.log",
        ),
        ("tidy", 'a: b"c?  d', "2026-11-07_143012_tidy_a-b-c-d.log"),
        ("tidy", "x" * 100, f"2026-11-07_143012_tidy_{'x' * 60}.log"),
    ],
)
def test_log_file_names(tmp_path: Path, name: str, description: str, file: str) -> None:
    assert job_log_path(tmp_path, STARTED, name, description) == tmp_path / file


def test_two_jobs_in_the_same_second_get_two_files(tmp_path: Path) -> None:
    job_log_path(tmp_path, STARTED, "tidy", "a").touch()
    second = job_log_path(tmp_path, STARTED, "tidy", "a")
    assert second.name == "2026-11-07_143012_tidy_a_2.log"


def test_the_work_writes_to_the_jobs_log(tmp_path: Path) -> None:
    slot = JobSlot(tmp_path)
    gate = Gate()

    def work(job: JobContext) -> None:
        job.log.info("step_done", source="a.jpg")
        gate.hold(job)

    view = slot.start(work, name="archive", description="batch")
    assert gate.entered.wait(5)
    assert view.log_path is not None
    mid_job = view.log_path.read_text(encoding="utf-8")
    gate.release.set()
    slot.wait(5)
    lines = view.log_path.read_text(encoding="utf-8").splitlines()

    assert "event='step_done'" in mid_job
    assert "job_finished" not in mid_job
    assert [line.split("event='")[1].split("'")[0] for line in lines] == [
        "job_started",
        "step_done",
        "job_finished",
    ]
    assert all(f"job_id='{view.id}'" in line for line in lines)
    assert "name='archive'" in lines[0] and "description='batch'" in lines[0]
    assert "state='done'" in lines[-1]


def test_a_failed_job_logs_its_traceback(tmp_path: Path) -> None:
    def boom(job: JobContext) -> None:
        raise RuntimeError("disk on fire")

    slot = JobSlot(tmp_path)
    view = slot.start(boom, name="archive")
    slot.wait(5)
    assert view.log_path is not None
    text = view.log_path.read_text(encoding="utf-8")
    assert "event='job_error'" in text
    assert "RuntimeError: disk on fire" in text
    assert "state='failed'" in text


def test_logs_of_two_jobs_stay_apart(tmp_path: Path) -> None:
    slot = JobSlot(tmp_path)
    first = slot.start(lambda job: job.log.info("first_step"), name="tidy")
    slot.wait(5)
    second = slot.start(lambda job: job.log.info("second_step"), name="tidy")
    slot.wait(5)
    assert first.log_path is not None and second.log_path is not None
    assert first.log_path != second.log_path
    assert "second_step" not in first.log_path.read_text(encoding="utf-8")
    assert "first_step" not in second.log_path.read_text(encoding="utf-8")


def test_without_a_folder_there_is_no_log_file() -> None:
    slot = JobSlot()
    view = slot.start(lambda job: job.log.info("step"), name="tidy")
    slot.wait(5)
    assert view.log_path is None


def test_work_outside_a_job_can_log() -> None:
    NO_JOB.log.info("not_in_a_job")
