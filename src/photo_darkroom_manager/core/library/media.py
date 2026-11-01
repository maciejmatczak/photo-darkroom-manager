"""Media file kinds and the untidy check."""

from __future__ import annotations

from pathlib import Path

from photo_darkroom_manager.core.library.layout import (
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
)

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "heic", "heif", "tif", "tiff"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

RAW_IMAGE_EXTENSIONS = {
    "arw",
    "cr2",
    "cr3",
    "nef",
    "orf",
    "dng",
    "raf",
    "rw2",
    "pef",
}

ALL_IMAGE_EXTENSIONS = PHOTO_EXTENSIONS | RAW_IMAGE_EXTENSIONS


def is_file_a_photo(suffixes: list[str]) -> bool:
    return any(suffix.lower() in PHOTO_EXTENSIONS for suffix in suffixes)


def is_file_a_video(suffixes: list[str]) -> bool:
    return any(suffix.lower() in VIDEO_EXTENSIONS for suffix in suffixes)


def _collect_files_to_tidy(folder: Path) -> tuple[list[Path], list[Path]]:
    """Collect misplaced photos and videos in a single directory.

    Groups files by stem so sidecars move together. Uses correct-state predicate:
    photos belong in PHOTOS/, videos in VIDEOS/.
    """
    seen_stems: set[str] = set()
    photo_paths: list[Path] = []
    video_paths: list[Path] = []

    try:
        items = folder.iterdir()
    except PermissionError:
        return [], []

    for item in items:
        if not item.is_file():
            continue
        stem = item.name.split(".")[0]
        if stem in seen_stems:
            continue
        seen_stems.add(stem)

        all_related = list(folder.glob(f"{stem}.*"))
        suffixes = [f.name.split(".", 1)[-1] for f in all_related]

        if (
            is_file_a_photo(suffixes)
            and not is_file_a_video(suffixes)
            and folder.name != PHOTOS_FOLDER
        ):
            photo_paths.extend(all_related)
        elif (
            is_file_a_video(suffixes)
            and not is_file_a_photo(suffixes)
            and folder.name != VIDEOS_FOLDER
        ):
            video_paths.extend(all_related)

    return photo_paths, video_paths


def collect_files_to_tidy(
    folder_path: Path, *, recursive: bool = False
) -> tuple[list[Path], list[Path]]:
    """Collect misplaced photos and videos under folder_path.

    Skips PUBLISH/ entirely. When recursive=True, walks all subdirectories.
    """
    if PUBLISH_FOLDER in folder_path.parts:
        return [], []

    photo_paths, video_paths = _collect_files_to_tidy(folder_path)

    if recursive:
        try:
            children = sorted(folder_path.iterdir())
        except PermissionError:
            return photo_paths, video_paths
        for child in children:
            if child.is_dir() and child.name != PUBLISH_FOLDER:
                p, v = collect_files_to_tidy(child, recursive=True)
                photo_paths.extend(p)
                video_paths.extend(v)

    return photo_paths, video_paths


def is_untidy(folder: Path) -> bool:
    """True if *folder* itself holds misplaced photos or videos."""
    try:
        photos, videos = collect_files_to_tidy(folder)
    except OSError:
        return False
    return bool(photos or videos)
