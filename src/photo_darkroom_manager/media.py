"""Media file type detection utilities."""

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "heic", "heif"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}


def is_file_a_photo(suffixes: list[str]) -> bool:
    return any(suffix.lower() in PHOTO_EXTENSIONS for suffix in suffixes)


def is_file_a_video(suffixes: list[str]) -> bool:
    return any(suffix.lower() in VIDEO_EXTENSIONS for suffix in suffixes)
