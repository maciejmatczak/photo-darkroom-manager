"""Tests for photo_darkroom_manager.settings."""

from pathlib import Path

import pytest
import yaml
from platformdirs import user_log_dir
from pydantic import ValidationError

from photo_darkroom_manager.settings import (
    APP_NAME,
    CONFIG_FILENAME,
    CONFIG_PATH_ENV,
    Settings,
    get_config_dir,
    get_config_path,
    get_logs_dir,
    load_settings,
    save_settings,
)


def test_get_logs_dir_uses_platformdirs_user_log_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    assert get_logs_dir() == Path(user_log_dir(APP_NAME))


def test_get_config_path_without_env_uses_platformdirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    path = get_config_path()
    assert path == get_config_dir() / CONFIG_FILENAME


def test_get_config_path_with_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "myconfig.yaml"
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    assert get_config_path() == cfg.resolve()


def test_get_config_path_empty_env_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, "   ")
    path = get_config_path()
    assert path == get_config_dir() / CONFIG_FILENAME


def test_settings_accepts_existing_directories(
    darkroom_root: Path, showroom_root: Path, archive_root: Path
) -> None:
    s = Settings(darkroom=darkroom_root, showroom=showroom_root, archive=archive_root)
    assert s.darkroom == darkroom_root.resolve()
    assert s.showroom == showroom_root.resolve()
    assert s.archive == archive_root.resolve()


def test_settings_rejects_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    existing = tmp_path / "ok"
    existing.mkdir()
    with pytest.raises(ValidationError, match="path does not exist"):
        Settings(darkroom=missing, showroom=existing, archive=existing)


def test_settings_rejects_file_not_directory(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    d = tmp_path / "dir"
    d.mkdir()
    with pytest.raises(ValidationError, match="not a directory"):
        Settings(darkroom=f, showroom=d, archive=d)


def test_settings_log_level_defaults_to_info(
    darkroom_root: Path, showroom_root: Path, archive_root: Path
) -> None:
    s = Settings(darkroom=darkroom_root, showroom=showroom_root, archive=archive_root)
    assert s.log_level == "INFO"


def test_settings_log_level_rejects_invalid(
    darkroom_root: Path, showroom_root: Path, archive_root: Path
) -> None:
    with pytest.raises(ValidationError, match="log_level"):
        Settings(
            darkroom=darkroom_root,
            showroom=showroom_root,
            archive=archive_root,
            log_level="VERBOSE",  # ty: ignore[invalid-argument-type]
        )


def test_save_and_load_settings_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg.yaml"
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    dr = tmp_path / "dr"
    sr = tmp_path / "sr"
    ar = tmp_path / "ar"
    dr.mkdir()
    sr.mkdir()
    ar.mkdir()
    original = Settings(darkroom=dr, showroom=sr, archive=ar, log_level="DEBUG")
    save_settings(original)
    loaded = load_settings()
    assert loaded is not None
    assert loaded.darkroom == original.darkroom
    assert loaded.showroom == original.showroom
    assert loaded.archive == original.archive
    assert loaded.log_level == "DEBUG"


def test_load_settings_defaults_log_level_when_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg.yaml"
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    dr = tmp_path / "dr"
    sr = tmp_path / "sr"
    ar = tmp_path / "ar"
    dr.mkdir()
    sr.mkdir()
    ar.mkdir()
    cfg.write_text(
        f"darkroom: {dr}\nshowroom: {sr}\narchive: {ar}\n",
        encoding="utf-8",
    )
    loaded = load_settings()
    assert loaded is not None
    assert loaded.log_level == "INFO"


def test_load_settings_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "missing.yaml"))
    assert load_settings() is None


def test_load_settings_invalid_yaml_syntax_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("{ not: valid: yaml: ", encoding="utf-8")
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    with pytest.raises(yaml.YAMLError):
        load_settings()


def test_load_settings_valid_yaml_invalid_settings_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "partial.yaml"
    cfg.write_text("darkroom: /nope\n", encoding="utf-8")
    monkeypatch.setenv(CONFIG_PATH_ENV, str(cfg))
    with pytest.raises(ValidationError):
        load_settings()
