"""structlog setup: file + stderr sinks, levels, log retention."""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import structlog
from structlog.processors import TimeStamper, format_exc_info
from structlog.stdlib import ProcessorFormatter
from structlog.types import Processor

RETENTION_DAYS = 30
APP_LOGGER_NAME = "photo_darkroom_manager"
LOG_FILE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_\d+\.log$")

THIRD_PARTY_LOGGERS = ("nicegui", "uvicorn", "uvicorn.error", "uvicorn.access")

_configured = False
_log_file_path: Path | None = None
_file_handler: logging.Handler | None = None
_stderr_handler: logging.Handler | None = None


def build_log_file_path(logs_dir: Path) -> Path:
    """Return ``{YYYY-MM-DD}_{HHMMSS}_{pid}.log`` under *logs_dir*."""
    now = datetime.now()
    filename = f"{now.strftime('%Y-%m-%d')}_{now.strftime('%H%M%S')}_{os.getpid()}.log"
    return logs_dir / filename


def cleanup_old_logs(
    logs_dir: Path, *, retention_days: int = RETENTION_DAYS, now: float | None = None
) -> None:
    """Delete log files in *logs_dir* older than *retention_days*."""
    if not logs_dir.is_dir():
        return
    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    for path in logs_dir.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


def _shared_pre_chain() -> Sequence[Processor]:
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        format_exc_info,
    ]


def _level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO)


def _apply_log_levels(level_name: str, console_name: str | None) -> None:
    level = _level(level_name)
    console = _level(console_name) if console_name else level
    if _file_handler is not None:
        _file_handler.setLevel(level)
    if _stderr_handler is not None:
        _stderr_handler.setLevel(console)
    logging.getLogger().setLevel(min(level, console))
    logging.getLogger(APP_LOGGER_NAME).setLevel(min(level, console))
    for name in THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_logging(
    log_level: str = "INFO", *, logs_dir: Path, console_level: str | None = None
) -> Path | None:
    """Configure structlog + stdlib handlers under *logs_dir*.

    The log file gets *log_level*; stderr gets *console_level* when given,
    else *log_level*. Repeat calls only re-apply the levels; handlers and the
    log file from the first call are kept.
    """
    global _configured, _log_file_path, _file_handler, _stderr_handler

    level_name = log_level.upper()

    if _configured:
        _apply_log_levels(level_name, console_level)
        return _log_file_path

    logs_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_logs(logs_dir)

    log_file = build_log_file_path(logs_dir)

    pre_chain = _shared_pre_chain()
    timestamper = TimeStamper(fmt="iso", utc=False)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            format_exc_info,
            ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.processors.KeyValueRenderer(),
            foreign_pre_chain=pre_chain,
        )
    )
    root.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=pre_chain,
        )
    )
    root.addHandler(stderr_handler)

    _file_handler = file_handler
    _stderr_handler = stderr_handler
    _apply_log_levels(level_name, console_level)

    _configured = True
    _log_file_path = log_file

    structlog.get_logger(__name__).info(
        "app_started",
        log_file=str(log_file),
        level=level_name,
        pid=os.getpid(),
    )

    return log_file


def reset_logging_state_for_tests() -> None:
    """Clear handlers and module state between tests."""
    global _configured, _log_file_path, _file_handler, _stderr_handler
    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    structlog.reset_defaults()
    _configured = False
    _log_file_path = None
    _file_handler = None
    _stderr_handler = None
