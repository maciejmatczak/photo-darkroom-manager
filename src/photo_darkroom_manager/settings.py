"""Config discovery and persistence (platformdirs YAML)."""

import os
from pathlib import Path

import yaml
from platformdirs import user_config_path
from pydantic import BaseModel, field_validator

APP_NAME = "photo-darkroom-manager"
CONFIG_FILENAME = "config.yaml"
CONFIG_PATH_ENV = "PHOTO_DARKROOM_MANAGER_CONFIG_PATH"

# Well-known folder names used throughout the darkroom workflow.
PUBLISH_FOLDER = "PUBLISH"
PHOTOS_FOLDER = "PHOTOS"
VIDEOS_FOLDER = "VIDEOS"


def get_config_dir() -> Path:
    return user_config_path(APP_NAME, ensure_exists=True)


def get_config_path() -> Path:
    """Path to the YAML config file.

    If ``PHOTO_DARKROOM_MANAGER_CONFIG_PATH`` is set to a non-empty string,
    that path is used (expanded user, resolved). Otherwise the default
    platformdirs location is used.
    """
    override = os.environ.get(CONFIG_PATH_ENV)
    if override is not None and override.strip():
        return Path(override).expanduser().resolve()
    return get_config_dir() / CONFIG_FILENAME


class Settings(BaseModel):
    darkroom: Path
    showroom: Path
    archive: Path
    cull_command: str | None = None
    edit_command: str | None = None

    @field_validator("darkroom", "showroom", "archive")
    @classmethod
    def validate_existing_directory(cls, v: Path) -> Path:
        v = Path(v).resolve()
        if not v.exists():
            raise ValueError(f"path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"path is not a directory: {v}")
        return v


def load_settings() -> Settings | None:
    """Load settings from the config file. Returns None if missing."""
    config_path = get_config_path()
    if not config_path.exists():
        return None
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Settings(**data)


def save_settings(settings: Settings) -> Path:
    """Persist settings to the config file (platformdirs or env override)."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    return config_path
