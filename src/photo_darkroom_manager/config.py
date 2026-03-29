from pathlib import Path

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


def find_darkroom_yaml(start_path: Path | None = None) -> Path | None:
    """Find darkroom.yaml in the current directory or any parent directory."""
    if start_path is None:
        start_path = Path.cwd()

    current = Path(start_path).resolve()

    # Walk up the directory tree until we reach the root
    while True:
        yaml_file = current / "darkroom.yaml"
        if yaml_file.exists():
            return yaml_file

        # Stop if we've reached the root directory
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


class Settings(BaseSettings):
    darkroom: Path
    showroom: Path
    archive: Path

    model_config = SettingsConfigDict(yaml_file=["darkroom.yaml"])

    @field_validator("darkroom", "showroom", "archive")
    @classmethod
    def validate_existing_directory(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"path is not a directory: {v}")
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = find_darkroom_yaml()
        if yaml_file is None:
            # If no yaml file found, return empty tuple
            # This will allow other sources (env vars, etc.) to be used
            return ()
        return (
            YamlConfigSettingsSource(
                settings_cls, yaml_file=yaml_file, yaml_file_encoding="utf-8"
            ),
        )
