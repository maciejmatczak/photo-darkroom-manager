from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator
from pydantic_core import InitErrorDetails

from photo_darkroom_manager.settings import PUBLISH_FOLDER


def format_validation_error(e: ValidationError) -> str:
    """Short user-facing message from a Pydantic ``ValidationError``."""
    parts = [str(err.get("msg", "")) for err in e.errors()]
    return "; ".join(parts) if parts else str(e)


_ALBUM_FOLDER_PARSE_PATTERN = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?(?:\s+(.+))?$")

# Title segment: ASCII letters, digits, spaces, hyphen, underscore only.
_TITLE_ALLOWED = re.compile(r"^[a-zA-Z0-9_\- ]+$")


def _album_folder_shape_validation_error(raw: str) -> ValidationError:
    msg = "Album folder name does not match YYYY-MM[-DD][ title]"
    details: InitErrorDetails = {
        "type": "value_error",
        "loc": (),
        "input": raw,
        "ctx": {"error": ValueError(msg)},
    }
    return ValidationError.from_exception_data("AlbumFolderName", [details])


class AlbumFolderName(BaseModel):
    """Validated darkroom album folder name components and string form."""

    year: str
    month: str
    day: str | None = None
    name: str | None = None

    @field_validator("day", mode="before")
    @classmethod
    def coerce_empty_day(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" else s

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        s = v.strip()
        if not s.isdigit() or len(s) != 4:
            raise ValueError(f"year must be exactly 4 digits, got: {v!r}")
        return s

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        s = v.strip()
        if not s.isdigit():
            raise ValueError(f"month must be numeric, got: {v!r}")
        m = int(s)
        if not 1 <= m <= 12:
            raise ValueError(f"month must be 01–12, got: {v!r}")
        return f"{m:02d}"

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if not s.isdigit():
            raise ValueError(f"day must be numeric, got: {v!r}")
        d = int(s)
        if not 1 <= d <= 31:
            raise ValueError(f"day must be 01–31, got: {v!r}")
        return f"{d:02d}"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        if not _TITLE_ALLOWED.fullmatch(s):
            raise ValueError(
                "title may only contain ASCII letters, digits, spaces, hyphens, "
                "and underscores"
            )
        return s

    @property
    def folder_name(self) -> str:
        date_part = f"{self.year}-{self.month}"
        if self.day is not None:
            date_part = f"{date_part}-{self.day}"
        if self.name:
            return f"{date_part} {self.name}"
        return date_part

    @classmethod
    def from_str(cls, s: str) -> AlbumFolderName:
        """Build from a folder name string; raises ``ValidationError`` if invalid."""
        raw = s.strip()
        m = _ALBUM_FOLDER_PARSE_PATTERN.match(raw)
        if not m:
            raise _album_folder_shape_validation_error(raw)
        year, month, day, name = m.group(1), m.group(2), m.group(3), m.group(4)
        return cls(year=year, month=month, day=day, name=name)


class DarkroomYearAlbum(BaseModel):
    year: str
    album: str
    album_path: Path
    relative_subpath: Path

    @property
    def publish_dir(self) -> Path:
        return self.album_path / PUBLISH_FOLDER

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        """Validate that the year is a valid 4-digit year."""
        if not v.isdigit():
            raise ValueError(f"year must be numeric, got: {v}")
        if len(v) != 4:
            raise ValueError(f"year must be 4 digits, got: {v} (length {len(v)})")
        return v

    @field_validator("album")
    @classmethod
    def validate_album(cls, v: str) -> str:
        """Validate album folder name shape (same rules as ``AlbumFolderName``)."""
        try:
            AlbumFolderName.from_str(v)
        except ValidationError:
            raise ValueError(
                "album must follow format 'YYYY-MM[-DD][ title]' with month 01-12; "
                "optional day 01-31 after YYYY-MM-DD; optional space and title "
                f"(e.g. '2024-01 Album Name', '2024-01', '2024-01-15 Trip'), got: {v!r}"
            ) from None
        return v


def recognize_darkroom_album(
    darkroom_path: Path, path: Path
) -> DarkroomYearAlbum | None:
    """Recognize the darkroom album from the path."""
    try:
        relative_path = path.relative_to(darkroom_path)
    except ValueError:
        raise ValueError(
            f"Path {path} is not a subpath of darkroom path: {darkroom_path}"
        ) from None
    parts = relative_path.parts

    try:
        year = parts[0]
        album = parts[1]
    except IndexError:
        return None

    album_path = darkroom_path / year / album

    return DarkroomYearAlbum(
        year=year, album=album, album_path=album_path, relative_subpath=relative_path
    )
