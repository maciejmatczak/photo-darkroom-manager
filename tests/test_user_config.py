"""Contract: engine/user-config spec scenarios."""

from pathlib import Path

import pytest
from conftest import Roots, write_config

from photo_darkroom_manager.user_config import (
    FILE_KEY,
    ConfigValueError,
    ConfigValues,
    UnknownConfigKeyError,
    UserConfig,
)


def _loaded(path: Path) -> UserConfig:
    config = UserConfig(path)
    config.load()
    return config


def test_config_values_accept_missing_folder(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    values = ConfigValues(darkroom=missing, showroom=missing, archive=missing)
    assert values.archive == missing.resolve()


def test_one_invalid_field_keeps_the_others(tmp_path: Path, roots: Roots) -> None:
    cfg = write_config(tmp_path / "c.yaml", roots, log_level="VERBOSE")
    config = UserConfig(cfg)
    issues = config.load()
    assert [i.key for i in issues] == ["log_level"]
    assert config.get_valid("darkroom") == roots.darkroom
    assert config.get_valid("showroom") == roots.showroom


def test_missing_required_key(tmp_path: Path, roots: Roots) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"darkroom: {roots.darkroom}\nshowroom: {roots.showroom}\n")
    issues = UserConfig(cfg).load()
    assert [(i.key, i.message) for i in issues] == [("archive", "missing")]


@pytest.mark.parametrize("content", ["{ not: valid: yaml: ", "- a list\n"])
def test_unparsable_file_gives_one_problem(tmp_path: Path, content: str) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(content, encoding="utf-8")
    config = UserConfig(cfg)
    issues = config.load()
    assert [i.key for i in issues] == [FILE_KEY]
    assert config.get_valid("darkroom") is None


def test_unreadable_file_gives_one_problem(tmp_path: Path) -> None:
    # A directory at the config path cannot be read as a file.
    cfg = tmp_path / "c.yaml"
    cfg.mkdir()
    config = UserConfig(cfg)
    issues = config.load()
    assert [i.key for i in issues] == [FILE_KEY]


def test_no_file_yet(tmp_path: Path) -> None:
    config = UserConfig(tmp_path / "missing.yaml")
    assert config.load() == []
    assert config.exists is False
    assert config.get("darkroom") is None


def test_unknown_key_in_file_is_a_problem(tmp_path: Path, roots: Roots) -> None:
    cfg = write_config(tmp_path / "c.yaml", roots, colour="blue")
    assert [i.key for i in UserConfig(cfg).load()] == ["colour"]


def test_fixing_a_loaded_problem(tmp_path: Path, roots: Roots) -> None:
    config = _loaded(write_config(tmp_path / "c.yaml", roots, log_level="VERBOSE"))
    config.set("log_level", "debug")
    assert config.issues == []
    assert config.get_valid("log_level") == "DEBUG"


def test_new_load_replaces_problems(tmp_path: Path, roots: Roots) -> None:
    cfg = write_config(tmp_path / "c.yaml", roots, log_level="VERBOSE")
    config = _loaded(cfg)
    write_config(cfg, roots)
    assert config.load() == []
    assert config.issues == []


def test_invalid_value_from_file_is_kept(tmp_path: Path, roots: Roots) -> None:
    config = _loaded(write_config(tmp_path / "c.yaml", roots, log_level="VERBOSE"))
    assert config.get("log_level") == "VERBOSE"
    assert config.get_valid("log_level") is None


def test_invalid_value_rejected(tmp_path: Path, roots: Roots) -> None:
    config = _loaded(write_config(tmp_path / "c.yaml", roots, log_level="ERROR"))
    with pytest.raises(ConfigValueError) as exc:
        config.set("log_level", "VERBOSE")
    assert exc.value.key == "log_level"
    assert config.get("log_level") == "ERROR"


@pytest.mark.parametrize("op", ["get", "set"])
def test_unknown_key_rejected(tmp_path: Path, op: str) -> None:
    config = UserConfig(tmp_path / "c.yaml")
    with pytest.raises(UnknownConfigKeyError) as exc:
        if op == "get":
            config.get("colour")
        else:
            config.set("colour", "blue")
    assert exc.value.key == "colour"


def test_stored_value_in_effect_immediately(tmp_path: Path, roots: Roots) -> None:
    config = _loaded(write_config(tmp_path / "c.yaml", roots))
    new = roots.archive / "elsewhere"
    config.set("archive", new)
    assert config.get_valid("archive") == new.resolve()


def test_missing_archive_folder_is_not_a_config_problem(
    tmp_path: Path, roots: Roots
) -> None:
    gone = Roots(roots.darkroom, roots.showroom, tmp_path / "unplugged")
    assert UserConfig(write_config(tmp_path / "c.yaml", gone)).load() == []


def test_round_trip(tmp_path: Path, roots: Roots) -> None:
    cfg = tmp_path / "sub" / "c.yaml"
    config = UserConfig(cfg)
    for key in ("darkroom", "showroom", "archive"):
        config.set(key, getattr(roots, key))
    config.set("edit_command", "edit {folder}")
    config.set("log_level", "DEBUG")
    assert config.save() == cfg

    again = UserConfig(cfg)
    assert again.load() == []
    for key in ("darkroom", "showroom", "archive", "edit_command", "log_level"):
        assert again.get_valid(key) == config.get_valid(key)


def test_save_while_fixing(tmp_path: Path, roots: Roots) -> None:
    cfg = write_config(
        tmp_path / "c.yaml", roots, log_level="VERBOSE", edit_command=["not", "str"]
    )
    config = _loaded(cfg)
    assert {i.key for i in config.issues} == {"log_level", "edit_command"}
    config.set("log_level", "INFO")
    config.save()
    assert [i.key for i in UserConfig(cfg).load()] == ["edit_command"]
