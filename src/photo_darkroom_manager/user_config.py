"""User configuration service: tolerant load, validated set, explicit save."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import structlog
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from pydantic.fields import FieldInfo

log = structlog.get_logger(__name__)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Key of a problem that concerns the whole file (unreadable, not YAML).
FILE_KEY = "*"


class ConfigValues(BaseModel):
    """Shape of the configuration: fields, types and defaults.

    Only the form of a value is checked; whether a folder exists is the
    engine's concern (see ``Engine.status``).
    """

    model_config = ConfigDict(validate_assignment=True)

    darkroom: Path
    showroom: Path
    archive: Path
    cull_command: str | None = None
    edit_command: str | None = None
    log_level: LogLevel = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v

    @field_validator("darkroom", "showroom", "archive")
    @classmethod
    def resolve_path(cls, v: Path) -> Path:
        return v.expanduser().resolve()


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    """One problem found in the configuration, naming the key to fix."""

    key: str
    message: str
    source: Literal["file", "value"] = "value"


class ConfigValueError(ValueError):
    """A value was rejected by ``UserConfig.set``."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key
        self.message = message


class UnknownConfigKeyError(KeyError):
    """The configuration does not define this key."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key

    def __str__(self) -> str:
        return f"unknown configuration key: {self.key}"


_FIELDS: dict[str, FieldInfo] = ConfigValues.model_fields


def validate_value(key: str, value: object) -> object:
    """Validate one field on its own; raise ``ConfigValueError``."""
    values = ConfigValues.model_construct()
    try:
        setattr(values, key, value)
    except ValidationError as e:
        message = "; ".join(err["msg"] for err in e.errors())
        raise ConfigValueError(key, message) from None
    return getattr(values, key)


def _to_yaml(key: str, value: object) -> object:
    adapter: TypeAdapter[Any] = TypeAdapter(_FIELDS[key].annotation)
    return adapter.dump_python(value, mode="json")


class UserConfig:
    """The user's configuration, the single source of configured values."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.exists = False
        self._raw: dict[str, object] = {}
        self._valid: dict[str, object] = {}
        self._issues: dict[str, list[ConfigIssue]] = {}

    @property
    def issues(self) -> list[ConfigIssue]:
        """Problems of the last load not yet fixed by ``set``."""
        return [issue for issues in self._issues.values() for issue in issues]

    def load(self) -> list[ConfigIssue]:
        """Read the file, keeping valid fields; return the problems found."""
        self._raw = {}
        self._valid = {}
        self._issues = {}
        self.exists = self.path.exists()
        if not self.exists:
            return []
        try:
            text = self.path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            self._add(ConfigIssue(FILE_KEY, f"cannot read {self.path}: {e}", "file"))
            return self.issues
        if data is None:
            data = {}
        if not isinstance(data, dict):
            self._add(
                ConfigIssue(FILE_KEY, "file must contain a mapping of keys", "file")
            )
            return self.issues

        for key, value in data.items():
            key = str(key)
            if key not in _FIELDS:
                self._add(ConfigIssue(key, "unknown key", "file"))
                continue
            self._raw[key] = value
            try:
                self._valid[key] = validate_value(key, value)
            except ConfigValueError as e:
                self._add(ConfigIssue(key, e.message))
        for key, field in _FIELDS.items():
            if key not in data and field.is_required():
                self._add(ConfigIssue(key, "missing", "file"))
        log.info(
            "user_config_loaded", config_path=str(self.path), issues=len(self.issues)
        )
        return self.issues

    def get(self, key: str) -> object:
        """Stored value of *key*, as read if invalid; default if unset."""
        self._check_key(key)
        if key in self._raw:
            return self._raw[key]
        field = _FIELDS[key]
        return None if field.is_required() else field.default

    def get_valid(self, key: str) -> Any:
        """Validated value of *key*, or ``None`` when missing or invalid."""
        self._check_key(key)
        if self._issues.get(key):
            return None
        if key in self._valid:
            return self._valid[key]
        field = _FIELDS[key]
        return None if field.is_required() else field.default

    def set(self, key: str, value: object) -> None:
        """Validate and store *value*; it is in effect at once."""
        self._check_key(key)
        valid = validate_value(key, value)
        self._raw[key] = valid
        self._valid[key] = valid
        self._issues.pop(key, None)

    def save(self) -> Path:
        """Write the stored values (also invalid ones) to the file."""
        data: dict[str, object] = {}
        for key, value in self._raw.items():
            if key in self._valid and not self._issues.get(key):
                value = _to_yaml(key, value)
            data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False)
        self.exists = True
        log.info("user_config_saved", config_path=str(self.path))
        return self.path

    def _add(self, issue: ConfigIssue) -> None:
        self._issues.setdefault(issue.key, []).append(issue)

    @staticmethod
    def _check_key(key: str) -> None:
        if key not in _FIELDS:
            raise UnknownConfigKeyError(key)
