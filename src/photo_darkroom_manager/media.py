"""Media file type detection utilities."""

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
