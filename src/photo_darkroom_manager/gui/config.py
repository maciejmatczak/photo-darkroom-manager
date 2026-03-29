"""GUI configuration: platformdirs-based config discovery and persistence."""

from pathlib import Path

import yaml
from platformdirs import user_config_path
from pydantic import BaseModel, field_validator

APP_NAME = "photo-darkroom-manager"
CONFIG_FILENAME = "config.yaml"


def get_config_dir() -> Path:
    return user_config_path(APP_NAME, ensure_exists=True)


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILENAME


class GuiSettings(BaseModel):
    darkroom: Path
    showroom: Path
    archive: Path

    @field_validator("darkroom", "showroom", "archive")
    @classmethod
    def validate_existing_directory(cls, v: Path) -> Path:
        v = Path(v).resolve()
        if not v.exists():
            raise ValueError(f"path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"path is not a directory: {v}")
        return v


def load_settings() -> GuiSettings | None:
    """Load settings from the platformdirs config file. Returns None if missing."""
    config_path = get_config_path()
    if not config_path.exists():
        return None
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return GuiSettings(**data)


def save_settings(settings: GuiSettings) -> Path:
    """Persist settings to the platformdirs config file."""
    config_path = get_config_path()
    data = {
        "darkroom": str(settings.darkroom),
        "showroom": str(settings.showroom),
        "archive": str(settings.archive),
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    return config_path
