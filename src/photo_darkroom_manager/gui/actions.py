"""Core action logic for the GUI -- no CLI/Rich/Typer dependencies."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from photo_darkroom_manager.constants import (
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
)
from photo_darkroom_manager.darkroom import recognize_darkroom_album
from photo_darkroom_manager.file_utils import move_dir_safely
from photo_darkroom_manager.media import is_file_a_photo, is_file_a_video


@dataclass
class ActionResult:
    success: bool
    message: str


def action_new_album(
    darkroom_path: Path,
    year: str,
    month: str,
    day: str | None,
    name: str,
) -> ActionResult:
    """Create a new album folder under the darkroom."""
    date_part = f"{year}-{month}"
    if day:
        date_part = f"{date_part}-{day}"
    album_folder_name = f"{date_part} {name.strip()}" if name.strip() else date_part

    target_dir = darkroom_path / year / album_folder_name
    if target_dir.exists():
        return ActionResult(False, f"Album folder already exists: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=False)
    publish_dir = target_dir / PUBLISH_FOLDER
    publish_dir.mkdir(parents=True, exist_ok=True)

    return ActionResult(True, f"Created album: {album_folder_name}")


def action_tidy(folder_path: Path) -> ActionResult:
    """Tidy files in the folder: separate photos and videos into subdirectories."""
    if not folder_path.is_dir():
        return ActionResult(False, f"Not a directory: {folder_path}")

    files_data: dict[str, dict] = {}
    for item in folder_path.iterdir():
        if item.is_dir():
            continue
        file_id = item.name.split(".")[0]
        if file_id in files_data:
            continue

        all_related = list(folder_path.glob(f"{file_id}.*"))
        suffixes = [f.name.split(".", 1)[-1] for f in all_related]
        files_data[file_id] = {
            "paths": all_related,
            "suffixes": suffixes,
            "is_photo": is_file_a_photo(suffixes),
            "is_video": is_file_a_video(suffixes),
        }

    photo_paths: list[Path] = []
    video_paths: list[Path] = []
    for d in files_data.values():
        if d["is_photo"] and not d["is_video"]:
            photo_paths.extend(d["paths"])
        elif d["is_video"] and not d["is_photo"]:
            video_paths.extend(d["paths"])

    moved = 0
    if photo_paths:
        photos_dir = folder_path / PHOTOS_FOLDER
        photos_dir.mkdir(exist_ok=True)
        for p in photo_paths:
            shutil.move(str(p), str(photos_dir / p.name))
            moved += 1

    if video_paths:
        videos_dir = folder_path / VIDEOS_FOLDER
        videos_dir.mkdir(exist_ok=True)
        for p in video_paths:
            shutil.move(str(p), str(videos_dir / p.name))
            moved += 1

    return ActionResult(True, f"Tidied {moved} files")


def action_archive(
    folder_path: Path,
    darkroom_path: Path,
    archive_path: Path,
) -> ActionResult:
    """Archive a folder from the darkroom to the archive directory."""
    album = recognize_darkroom_album(darkroom_path, folder_path)
    if album is None:
        return ActionResult(False, "Could not recognize album for this path")

    target_dir = archive_path / album.relative_subpath
    if target_dir.exists():
        return ActionResult(False, f"Archive target already exists: {target_dir}")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    _dest, issues = move_dir_safely(folder_path, target_dir)

    unrecovered = [i for i in issues if not i.recovered]
    if unrecovered:
        details = "; ".join(f"{i.operation} {i.path}: {i.error}" for i in unrecovered)
        return ActionResult(False, f"Archived with errors: {details}")

    return ActionResult(True, f"Archived to {target_dir}")


def action_publish(
    album_path: Path,
    showroom_path: Path,
    darkroom_path: Path,
) -> ActionResult:
    """Publish files from the album's PUBLISH/ dir to the showroom."""
    album = recognize_darkroom_album(darkroom_path, album_path)
    if album is None:
        return ActionResult(False, "Could not recognize album")

    publish_dir = album_path / PUBLISH_FOLDER
    if not publish_dir.exists():
        return ActionResult(False, "PUBLISH directory does not exist")

    files = [f for f in publish_dir.iterdir() if f.is_file()]
    if not files:
        return ActionResult(False, "PUBLISH directory is empty")

    dirs_in_publish = [f for f in publish_dir.iterdir() if f.is_dir()]
    if dirs_in_publish:
        return ActionResult(False, "PUBLISH directory contains subdirectories")

    target_dir = showroom_path / album.year / album.album
    target_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for f in files:
        shutil.move(str(f), str(target_dir / f.name))
        moved += 1

    return ActionResult(True, f"Published {moved} files to showroom")


def action_rename_album(
    album_path: Path,
    new_name: str,
    darkroom_path: Path,
) -> ActionResult:
    """Rename an album folder on disk."""
    album = recognize_darkroom_album(darkroom_path, album_path)
    if album is None:
        return ActionResult(False, "Could not recognize album")

    new_name = new_name.strip()
    if not new_name:
        return ActionResult(False, "New name cannot be empty")

    new_path = album_path.parent / new_name
    if new_path.exists():
        return ActionResult(False, f"A folder named '{new_name}' already exists")

    album_path.rename(new_path)
    return ActionResult(True, f"Renamed to {new_name}")
