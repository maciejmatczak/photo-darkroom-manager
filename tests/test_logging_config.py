"""Tests for photo_darkroom_manager.logging_config."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from photo_darkroom_manager.logging_config import (
    LOG_FILE_PATTERN,
    LOG_LEVEL_ENV,
    RETENTION_DAYS,
    build_log_file_path,
    cleanup_old_logs,
    configure_logging,
    reset_logging_state_for_tests,
    resolve_log_level,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    yield
    reset_logging_state_for_tests()


def test_resolve_log_level_defaults_to_info() -> None:
    assert resolve_log_level(None) == "INFO"


def test_resolve_log_level_uses_argument() -> None:
    assert resolve_log_level("DEBUG") == "DEBUG"


def test_resolve_log_level_env_overrides_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "WARNING")
    assert resolve_log_level("DEBUG") == "WARNING"


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


def test_configure_logging_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "photo_darkroom_manager.logging_config.get_logs_dir",
        lambda: tmp_path / "logs",
    )

    first = configure_logging()
    assert first is not None
    handler_count = len(logging.getLogger().handlers)

    second = configure_logging()
    assert second == first
    assert len(logging.getLogger().handlers) == handler_count
