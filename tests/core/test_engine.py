"""Contract: engine/engine-status spec scenarios."""

from pathlib import Path

import pytest
from conftest import Roots, write_config
from platformdirs import user_config_path, user_log_dir

from photo_darkroom_manager.core.engine import (
    APP_NAME,
    CONFIG_FILENAME,
    CONFIG_PATH_ENV,
    LOG_LEVEL_ENV,
    Engine,
    EngineNotReadyError,
    default_config_path,
    default_logs_dir,
)


def _engine(tmp_path: Path, roots: Roots | None, **values: object) -> Engine:
    return Engine(write_config(tmp_path / "c.yaml", roots, **values))


def test_configuration_change_is_visible_at_once(
    engine: Engine, tmp_path: Path
) -> None:
    new = tmp_path / "new-archive"
    engine.config_set("archive", new)
    assert engine.archive == new.resolve()


def test_missing_value(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, None, darkroom=str(roots.darkroom))
    assert engine.archive is None
    assert engine.darkroom == roots.darkroom


def test_fresh_install(tmp_path: Path) -> None:
    engine = Engine(tmp_path / "missing.yaml")
    assert engine.status == "unconfigured"
    assert engine.status_detail is not None


def test_valid_configuration(engine: Engine) -> None:
    assert engine.status == "ready"
    assert engine.status_detail is None


def test_unplugged_drive(tmp_path: Path, roots: Roots) -> None:
    gone = Roots(roots.darkroom, roots.showroom, tmp_path / "unplugged")
    engine = _engine(tmp_path, gone)
    assert engine.status == "invalid"
    assert engine.status_detail is not None
    assert "archive" in engine.status_detail


def test_status_follows_fixes(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, roots, log_level="VERBOSE")
    assert engine.status == "invalid"
    engine.config_set("log_level", "INFO")
    assert engine.status == "ready"


def test_status_follows_disk(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, roots)
    roots.archive.rmdir()
    assert engine.status == "invalid"
    roots.archive.mkdir()
    assert engine.status == "ready"


def test_several_problems_at_once(tmp_path: Path, roots: Roots) -> None:
    showroom_file = tmp_path / "showroom.txt"
    showroom_file.write_text("x")
    bad = Roots(roots.darkroom, showroom_file, roots.archive)
    engine = _engine(tmp_path, bad, log_level="VERBOSE")
    detail = engine.status_detail
    assert detail is not None
    assert "log_level" in detail
    assert "showroom" in detail


def test_not_ready_rejects_work(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, roots, log_level="VERBOSE")
    batch = roots.darkroom / "Camera/2026/2026-10"
    work = [
        engine.library_scan,
        lambda: engine.action_tidy(batch),
        lambda: engine.action_archive(batch),
        lambda: engine.action_publish(batch),
        lambda: engine.action_rename(batch, "2026", "10", None, "x"),
        lambda: engine.action_new_batch("Camera", "2026", "10", None, None),
        lambda: engine.action_open_external_app("edit {folder}", batch),
    ]
    for request in work:
        with pytest.raises(EngineNotReadyError) as exc:
            request()
        assert exc.value.status == "invalid"
        assert exc.value.detail == engine.status_detail


def test_temporary_debug_logging(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, roots, log_level="INFO")
    engine.set_log_level("debug")
    assert engine.log_level == "DEBUG"
    assert engine.config_get("log_level") == "INFO"
    assert "INFO" in (tmp_path / "c.yaml").read_text()


def test_configuration_edit_at_runtime(tmp_path: Path, roots: Roots) -> None:
    engine = _engine(tmp_path, roots, log_level="INFO")
    engine.config_set("log_level", "ERROR")
    assert engine.log_level == "INFO"


def test_log_level_seeded_from_configuration(tmp_path: Path, roots: Roots) -> None:
    assert _engine(tmp_path, roots, log_level="WARNING").log_level == "WARNING"


def test_env_override_wins_at_start(
    tmp_path: Path, roots: Roots, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "ERROR")
    assert _engine(tmp_path, roots, log_level="DEBUG").log_level == "ERROR"


def test_load_problem_is_logged(tmp_path: Path, roots: Roots) -> None:
    _engine(tmp_path, roots, log_level="VERBOSE")
    logs = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "logs").iterdir())
    assert "config_issue" in logs
    assert "log_level" in logs


def test_invalid_env_log_level_falls_back_to_configuration(
    tmp_path: Path, roots: Roots, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "VERBOSE")
    assert _engine(tmp_path, roots, log_level="DEBUG").log_level == "DEBUG"


@pytest.mark.parametrize("override", [None, "   "])
def test_default_config_path_uses_platformdirs(
    monkeypatch: pytest.MonkeyPatch, override: str | None
) -> None:
    if override is not None:
        monkeypatch.setenv(CONFIG_PATH_ENV, override)
    assert default_config_path() == user_config_path(APP_NAME) / CONFIG_FILENAME


def test_config_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "myconfig.yaml"
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    assert default_config_path() == cfg.resolve()
    detail = Engine().status_detail
    assert detail is not None
    assert str(cfg.resolve()) in detail


def test_default_logs_dir_uses_platformdirs() -> None:
    # Imported before the isolation fixture patches the module attribute.
    assert default_logs_dir() == Path(user_log_dir(APP_NAME))
