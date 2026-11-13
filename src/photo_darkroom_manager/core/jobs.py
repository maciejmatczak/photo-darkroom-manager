"""Run one job at a time on a worker thread, with progress, cancel and a log.

A :class:`JobSlot` holds the current or last job and runs its work on a new
thread. Clients read the job as frozen :class:`JobView` snapshots, wait for
it or cancel it. The work gets a :class:`Job` to report progress, see a
cancel request and write to the job's own log file; it decides itself
where it can stop.

Lifecycle of a job:

1. ``start`` (caller's thread): refuse while the slot is busy, create the
   :class:`Job` and its log file, store it as ``new``, start the worker
   thread.
2. Run (worker thread): write ``job_started``, set ``running`` and call the
   work with the job.
3. Finish (worker thread): a return ends the job ``done``,
   :class:`JobCancelled` ends it ``cancelled`` and any other exception
   ``failed``; write ``job_finished``, close the log and store the final
   snapshot.

The module depends only on the standard library and structlog.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from structlog.stdlib import BoundLogger, ProcessorFormatter

__all__ = [
    "Job",
    "JobBusyError",
    "JobCancelled",
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
    """Work was refused while a job is active.

    Args:
        label: What is running: the job's name and description.
    """

    def __init__(self, label: str) -> None:
        super().__init__(f"busy: {label} is running")
        self.label = label


class JobCancelled(Exception):
    """Raised by work that stops for a cancel request.

    Args:
        result: What the work did before it stopped, kept as the job's
            result; ``None`` when it has nothing to report.
    """

    def __init__(self, result: object = None) -> None:
        super().__init__("cancelled")
        self.result = result


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


def _label(name: str, description: str) -> str:
    return f"{name} {description}".strip()


class Job:
    """One piece of work: its progress, its cancel flag and its log.

    The slot creates a job for each run; tests create one directly. Every
    method may be called from any thread.

    Args:
        name: Short name, e.g. ``archive``.
        description: Free-form text, e.g. what the job works on.
        log_path: File the job's log writes to, besides this module's
            logger; ``None`` writes only to this module's logger.
    """

    def __init__(
        self, name: str, description: str = "", *, log_path: Path | None = None
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.name = name
        self.description = description
        self.log_path = log_path
        self._progress = Progress()
        self._cancel = threading.Event()
        logger = logging.Logger(f"{_LOGGER_NAME}.{self.id}", logging.INFO)
        logger.parent = logging.getLogger(_LOGGER_NAME)
        self._handler: logging.Handler | None = None
        if log_path is not None:
            self._handler = logging.FileHandler(log_path, encoding="utf-8")
            self._handler.setFormatter(
                ProcessorFormatter(processor=structlog.processors.KeyValueRenderer())
            )
            logger.addHandler(self._handler)
        self._logger = logger
        self._log = _wrap(logger).bind(job_id=self.id)

    def __str__(self) -> str:
        return _label(self.name, self.description)

    def progress(
        self, done: int, total: int | None = None, current: str | None = None
    ) -> None:
        """Report how far the work got.

        Args:
            done: Finished units so far.
            total: All units, or ``None`` when unknown.
            current: The item being worked on, if any.
        """
        self._progress = Progress(done, total, current)

    @property
    def last_progress(self) -> Progress:
        """The progress reported last; nothing done before the first report."""
        return self._progress

    @property
    def cancelled(self) -> bool:
        """True once the job was asked to stop."""
        return self._cancel.is_set()

    def cancel(self) -> None:
        """Ask the work to stop at its next safe point."""
        self._cancel.set()

    @property
    def log(self) -> BoundLogger:
        """Logger writing to the job's log file and on to the app's logs."""
        return self._log

    def close(self) -> None:
        """Close the job's log file; later lines go only to the app's logs."""
        if self._handler is not None:
            self._logger.removeHandler(self._handler)
            self._handler.close()
            self._handler = None


@dataclass
class _Record:
    view: JobView
    job: Job
    exception: Exception | None = None

    def snapshot(self) -> JobView:
        if self.view.active:
            return replace(self.view, progress=self.job.last_progress)
        return self.view


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


class JobSlot:
    """Holds at most one job and runs it on a new non-daemon thread.

    A finished job stays readable until the next one replaces it; there is
    no list of past jobs. The slot is busy while its job is active.

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
            return self._record.snapshot() if self._record else None

    @property
    def busy(self) -> JobView | None:
        """The job when it is new, running or cancelling; else ``None``."""
        with self._lock:
            if self._record is not None and self._record.view.active:
                return self._record.snapshot()
            return None

    @property
    def exception(self) -> Exception | None:
        """The unexpected error that ended the last job ``failed``, if any."""
        with self._lock:
            return self._record.exception if self._record else None

    def _refuse_if_busy(self) -> None:
        """Raise :class:`JobBusyError` while busy; the lock must be held."""
        if self._record is not None and self._record.view.active:
            raise JobBusyError(str(self._record.view))

    def require_idle(self) -> None:
        """Raise :class:`JobBusyError` while a job is active."""
        with self._lock:
            self._refuse_if_busy()

    def start[R](
        self,
        work: Callable[[Job], R],
        *,
        name: str,
        description: str = "",
    ) -> JobView:
        """Accept *work* as the new job and start it; return it as ``new``.

        The job ends ``done`` when *work* returns, ``cancelled`` when it
        raises :class:`JobCancelled` (whose result becomes the job's) and
        ``failed`` when it raises anything else.

        Args:
            work: Runs on the worker thread with the job; its return value
                becomes the job's result.
            name: Short name of the job, e.g. ``archive``; used in the log
                file name and in messages.
            description: Free-form text, e.g. what the job works on; also
                used, shortened, in the log file name.

        Raises:
            JobBusyError: Another job is active.
        """
        started = datetime.now()
        with self._lock:
            self._refuse_if_busy()
            log_path = None
            if self._jobs_dir is not None:
                self._jobs_dir.mkdir(parents=True, exist_ok=True)
                log_path = job_log_path(self._jobs_dir, started, name, description)
            job = Job(name, description, log_path=log_path)
            record = _Record(
                JobView(
                    id=job.id,
                    name=name,
                    description=description,
                    state="new",
                    progress=Progress(),
                    started_at=started,
                    log_path=log_path,
                ),
                job,
            )
            self._record = record
            thread = threading.Thread(
                target=self._run, args=(record, work), name=f"job-{name}"
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
        """Ask the active job to stop at its next safe point; no-op when idle."""
        with self._lock:
            record = self._record
            if record is None or not record.view.active:
                return
            record.job.cancel()
            if record.view.state in ("new", "running"):
                record.view = replace(record.view, state="cancelling")

    def _run[R](self, record: _Record, work: Callable[[Job], R]) -> None:
        job = record.job
        started = time.perf_counter()
        job.log.info("job_started", name=job.name, description=job.description)
        with self._lock:
            if record.view.state == "new":
                record.view = replace(record.view, state="running")
        result: object = None
        error: str | None = None
        try:
            result = work(job)
        except JobCancelled as stopped:
            state: JobState = "cancelled"
            result = stopped.result
        except Exception as e:
            job.log.exception("job_error")
            state = "failed"
            error = f"{type(e).__name__}: {e}"
            record.exception = e
        else:
            state = "done"
        job.log.info(
            "job_finished",
            state=state,
            error=error,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        job.close()
        with self._lock:
            record.view = replace(
                record.view,
                state=state,
                progress=job.last_progress,
                finished_at=datetime.now(),
                result=result,
                error=error,
            )
