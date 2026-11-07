"""Run one job at a time on a worker thread, with progress, cancel and a log.

A :class:`JobSlot` holds the current or last job and runs its work on a new
thread. Clients read the job as frozen :class:`JobView` snapshots, wait for
it or cancel it. The work gets a :class:`JobContext` to report progress, see
a cancel request and write to the job's own log file; it stops between
steps on its own.

Lifecycle of a job:

1. ``start`` (caller's thread): refuse while a job is active, create the
   job's id and log file, store it as ``new``, start the worker thread.
2. Run (worker thread): open the job's logger, write ``job_started``, set
   ``running`` and call the work with a context.
3. Finish (worker thread): map the result, or an exception, to ``done``,
   ``failed`` or ``cancelled``, write ``job_finished``, close the logger and
   store the final snapshot.

The module depends only on the standard library and structlog.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from structlog.stdlib import BoundLogger, ProcessorFormatter

__all__ = [
    "NO_JOB",
    "JobBusyError",
    "JobCancelled",
    "JobContext",
    "JobSlot",
    "JobState",
    "JobView",
    "Progress",
    "job_log_path",
]

JobState = Literal["new", "running", "cancelling", "done", "failed", "cancelled"]
ACTIVE_STATES: frozenset[JobState] = frozenset({"new", "running", "cancelling"})
FINAL_STATES: frozenset[JobState] = frozenset({"done", "failed", "cancelled"})

_LOGGER_NAME = __name__
_SLUG_LENGTH = 60
_UNSAFE_IN_NAME = re.compile(r'[\s<>:"/\\|?*\x00-\x1f~]+')


@dataclass(frozen=True)
class Progress:
    """How far a job got.

    Args:
        done: Finished units so far.
        total: All units, or ``None`` when the job cannot count them.
        current: The item being worked on, if the job has one.
    """

    done: int = 0
    total: int | None = None
    current: str | None = None


@dataclass(frozen=True)
class JobView:
    """Read-only snapshot of a job; it never changes once taken.

    Args:
        id: Unique id of the job, made when it starts.
        name: Short name the caller gave, e.g. ``archive``.
        description: Free-form text the caller gave, e.g. what it works on.
        state: Where the job is in its lifecycle.
        progress: The last progress the work reported.
        started_at: When the job was accepted.
        finished_at: When it ended; ``None`` while active.
        log_path: The job's own log file; ``None`` when the slot has no
            log folder.
        result: What the work returned, once it ended without an error.
        error: Type and message of the exception that ended it ``failed``.
    """

    id: str
    name: str
    description: str
    state: JobState
    progress: Progress
    started_at: datetime
    finished_at: datetime | None = None
    log_path: Path | None = None
    result: Any = None
    error: str | None = None

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def finished(self) -> bool:
        return self.state in FINAL_STATES

    def __str__(self) -> str:
        return f"{self.name} {self.description}".strip()


class JobBusyError(RuntimeError):
    """A job was started while another one is new, running or cancelling.

    Args:
        job: Snapshot of the job that is running.
    """

    def __init__(self, job: JobView) -> None:
        super().__init__(f"a job is running: {job}")
        self.job = job


class JobCancelled(Exception):
    """Raised by work that stops on a cancel request with nothing to return."""


def _wrap(logger: logging.Logger) -> BoundLogger:
    """A structlog logger over *logger*, independent of global configuration."""
    return structlog.wrap_logger(
        logger,
        wrapper_class=BoundLogger,
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.format_exc_info,
            ProcessorFormatter.wrap_for_formatter,
        ],
    )


_module_log = _wrap(logging.getLogger(_LOGGER_NAME))


class JobContext:
    """What running work sees of its job; this base does nothing.

    Work that runs outside a job (tests, inline calls) gets :data:`NO_JOB`,
    whose log is this module's logger.
    """

    def progress(
        self, done: int, total: int | None = None, current: str | None = None
    ) -> None:
        """Report how far the work got.

        Args:
            done: Finished units so far.
            total: All units, or ``None`` when unknown.
            current: The item being worked on, if any.
        """

    @property
    def cancelled(self) -> bool:
        """True once a client asked the job to stop."""
        return False

    @property
    def log(self) -> BoundLogger:
        """Logger writing to the job's log file (and on to the app's logs)."""
        return _module_log


NO_JOB = JobContext()


@dataclass
class _Record:
    view: JobView
    cancel: threading.Event = field(default_factory=threading.Event)
    exception: Exception | None = None


class _SlotContext(JobContext):
    def __init__(self, slot: JobSlot, record: _Record, log: BoundLogger) -> None:
        self._slot = slot
        self._record = record
        self._log = log

    def progress(
        self, done: int, total: int | None = None, current: str | None = None
    ) -> None:
        self._slot._update(self._record, progress=Progress(done, total, current))

    @property
    def cancelled(self) -> bool:
        return self._record.cancel.is_set()

    @property
    def log(self) -> BoundLogger:
        return self._log


def _slug(text: str) -> str:
    """*text* for a file name: unsafe characters and spaces become ``-``."""
    slug = _UNSAFE_IN_NAME.sub("-", text).strip("-.")
    return slug[:_SLUG_LENGTH].rstrip("-.")


def job_log_path(
    jobs_dir: Path, started: datetime, name: str, description: str
) -> Path:
    """A free path ``{YYYY-MM-DD}_{HHMMSS}_{name}_{description}.log``.

    Args:
        jobs_dir: Folder of the job logs.
        started: When the job started; sorting names sorts by start time.
        name: The job's short name.
        description: The job's description, shortened and made safe.

    A name already taken gets ``_2``, ``_3``, ... so two jobs never share a
    file.
    """
    parts = [f"{started:%Y-%m-%d}_{started:%H%M%S}", _slug(name), _slug(description)]
    stem = "_".join(part for part in parts if part)
    path = jobs_dir / f"{stem}.log"
    suffix = 2
    while path.exists():
        path = jobs_dir / f"{stem}_{suffix}.log"
        suffix += 1
    return path


@contextmanager
def _job_logger(job_id: str, path: Path | None) -> Iterator[BoundLogger]:
    """A logger for one job: its file (if any), then on to this module's log.

    The stdlib logger is not registered with :mod:`logging`, so nothing is
    left behind once the job ends.
    """
    logger = logging.Logger(f"{_LOGGER_NAME}.{job_id}", logging.INFO)
    logger.parent = logging.getLogger(_LOGGER_NAME)
    handler: logging.Handler | None = None
    if path is not None:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(
            ProcessorFormatter(processor=structlog.processors.KeyValueRenderer())
        )
        logger.addHandler(handler)
    try:
        yield _wrap(logger).bind(job_id=job_id)
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()


def _default_state(result: object) -> JobState:
    return "done"


class JobSlot:
    """Holds at most one job and runs it on a new non-daemon thread.

    A finished job stays readable until the next one replaces it; there is
    no list of past jobs.

    Args:
        jobs_dir: Folder for one log file per job; ``None`` writes job logs
            only to this module's logger.
    """

    def __init__(self, jobs_dir: Path | None = None) -> None:
        self._jobs_dir = jobs_dir
        self._lock = threading.Lock()
        self._record: _Record | None = None
        self._thread: threading.Thread | None = None

    @property
    def view(self) -> JobView | None:
        """Snapshot of the current or last job; ``None`` before the first."""
        with self._lock:
            return self._record.view if self._record else None

    @property
    def busy(self) -> JobView | None:
        """The job when it is new, running or cancelling; else ``None``."""
        with self._lock:
            if self._record is not None and self._record.view.active:
                return self._record.view
            return None

    @property
    def exception(self) -> Exception | None:
        """The unexpected error that ended the last job ``failed``, if any."""
        with self._lock:
            return self._record.exception if self._record else None

    def require_idle(self) -> None:
        """Raise :class:`JobBusyError` while a job is active."""
        if (job := self.busy) is not None:
            raise JobBusyError(job)

    def start[R](
        self,
        work: Callable[[JobContext], R],
        *,
        name: str,
        description: str = "",
        state_of: Callable[[R], JobState] = _default_state,
    ) -> JobView:
        """Accept *work* as the new job and start it; return it as ``new``.

        Args:
            work: Runs on the worker thread with the job's context; its
                return value becomes the job's result.
            name: Short name of the job, e.g. ``archive``; used in the log
                file name and in messages.
            description: Free-form text, e.g. what the job works on; also
                used, shortened, in the log file name.
            state_of: Final state for the work's result; by default every
                result is ``done``. An exception always ends the job
                ``failed`` and :class:`JobCancelled` ends it ``cancelled``.

        Raises:
            JobBusyError: Another job is new, running or cancelling.
        """
        started = datetime.now()
        with self._lock:
            if self._record is not None and self._record.view.active:
                raise JobBusyError(self._record.view)
            log_path = None
            if self._jobs_dir is not None:
                self._jobs_dir.mkdir(parents=True, exist_ok=True)
                log_path = job_log_path(self._jobs_dir, started, name, description)
                log_path.touch()
            record = _Record(
                JobView(
                    id=uuid.uuid4().hex[:12],
                    name=name,
                    description=description,
                    state="new",
                    progress=Progress(),
                    started_at=started,
                    log_path=log_path,
                )
            )
            self._record = record
            thread = threading.Thread(
                target=self._run, args=(record, work, state_of), name=f"job-{name}"
            )
            self._thread = thread
            view = record.view
        thread.start()
        return view

    def wait(self, timeout: float | None = None) -> JobView | None:
        """Wait for the job to end and return its snapshot.

        Args:
            timeout: Seconds to wait at most; ``None`` waits until it ends.
        """
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.view

    def cancel(self) -> None:
        """Ask the active job to stop at its next step; no-op when idle."""
        with self._lock:
            record = self._record
            if record is None or not record.view.active:
                return
            record.cancel.set()
            if record.view.state in ("new", "running"):
                record.view = replace(record.view, state="cancelling")

    def _update(self, record: _Record, **changes: Any) -> None:
        with self._lock:
            if record.view.finished:
                return
            if changes.get("state") == "running" and record.view.state != "new":
                changes.pop("state")
            record.view = replace(record.view, **changes)

    def _run[R](
        self,
        record: _Record,
        work: Callable[[JobContext], R],
        state_of: Callable[[R], JobState],
    ) -> None:
        view = record.view
        started = time.perf_counter()
        with _job_logger(view.id, view.log_path) as job_log:
            job_log.info("job_started", name=view.name, description=view.description)
            self._update(record, state="running")
            result: object = None
            error: str | None = None
            try:
                result = work(_SlotContext(self, record, job_log))
            except JobCancelled:
                state: JobState = "cancelled"
            except Exception as e:
                job_log.exception("job_error")
                state = "failed"
                error = f"{type(e).__name__}: {e}"
                record.exception = e
            else:
                state = state_of(result)  # type: ignore[arg-type]
            job_log.info(
                "job_finished",
                state=state,
                error=error,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        with self._lock:
            record.view = replace(
                record.view,
                state=state,
                finished_at=datetime.now(),
                result=result,
                error=error,
            )
