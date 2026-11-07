"""Tests for photo_darkroom_manager.core.logging_config."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from photo_darkroom_manager.core.logging_config import (
    LOG_FILE_PATTERN,
    RETENTION_DAYS,
    build_log_file_path,
    cleanup_old_logs,
    configure_logging,
    reset_logging_state_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    yield
    reset_logging_state_for_tests()


def test_build_log_file_path_pattern(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    path = build_log_file_path(logs_dir)
    assert path.parent == logs_dir
    assert LOG_FILE_PATTERN.match(path.name)


def test_cleanup_old_logs_removes_stale_files(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    old = logs_dir / "old.log"
    old.write_text("stale", encoding="utf-8")
    recent = logs_dir / "recent.log"
    recent.write_text("fresh", encoding="utf-8")

    now = time.time()
    old_time = now - (RETENTION_DAYS + 1) * 86400
    os.utime(old, (old_time, old_time))

    cleanup_old_logs(logs_dir, now=now)
    assert not old.exists()
    assert recent.exists()


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:

    first = configure_logging(logs_dir=tmp_path / "logs")
    assert first is not None
    handler_count = len(logging.getLogger().handlers)

    second = configure_logging(logs_dir=tmp_path / "other")
    assert second == first
    assert len(logging.getLogger().handlers) == handler_count


def test_console_level_keeps_stderr_quiet_while_the_file_logs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_file = configure_logging(
        "INFO", logs_dir=tmp_path / "logs", console_level="WARNING"
    )
    assert log_file is not None
    logger = logging.getLogger("photo_darkroom_manager.test")
    capsys.readouterr()

    logger.info("quiet_record")
    logger.warning("loud_record")
    for handler in logging.getLogger().handlers:
        handler.flush()

    err = capsys.readouterr().err
    assert "quiet_record" not in err
    assert "loud_record" in err
    text = log_file.read_text(encoding="utf-8")
    assert "quiet_record" in text
    assert "loud_record" in text


def test_console_level_can_be_more_verbose_than_the_file(tmp_path: Path) -> None:
    configure_logging("WARNING", logs_dir=tmp_path / "logs", console_level="DEBUG")
    assert logging.getLogger("photo_darkroom_manager").isEnabledFor(logging.DEBUG)


def test_cleanup_keeps_logs_in_subfolders(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    old_job = logs_dir / "jobs" / "2020-01-01_000000_tidy.log"
    old_job.parent.mkdir(parents=True)
    old_job.write_text("audit", encoding="utf-8")
    now = time.time()
    old_time = now - (RETENTION_DAYS + 5) * 86400
    os.utime(old_job, (old_time, old_time))
    cleanup_old_logs(logs_dir, now=now)
    assert old_job.exists()
