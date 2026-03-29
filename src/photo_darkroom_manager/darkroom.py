import re
from pathlib import Path

from pydantic import BaseModel, field_validator


class DarkroomYearAlbum(BaseModel):
    year: str
    album: str
    album_path: Path
    relative_subpath: Path

    @property
    def publish_dir(self) -> Path:
        return self.album_path / "PUBLISH"

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
        """Validate that the album follows the format 'YYYY-MM[ <something>]'."""
        pattern = r"^\d{4}-\d{2}.*"
        if not re.match(pattern, v):
            raise ValueError(
                "album must follow format 'YYYY-MM[ <something>]' "
                f"(e.g., '2024-01 Album Name' or '2024-01'), got: {v}"
            )
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
