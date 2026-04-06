from __future__ import annotations

from pathlib import Path


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _touch_empty(path: Path) -> None:
    _mkdir(path.parent)
    path.write_bytes(b"")


def main() -> None:
    data = Path(__file__).resolve().parent

    # Roots
    _mkdir(data / "darkroom")
    _mkdir(data / "showroom")
    _mkdir(data / "archive")

    darkroom_2026 = data / "darkroom" / "2026"

    # 2026-03 publish basic success
    _touch_empty(
        darkroom_2026 / "2026-03 publish basic success" / "PUBLISH" / "export_0001.jpg"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 publish basic success" / "PUBLISH" / "export_0001.xmp"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 publish basic success" / "PUBLISH" / "export_0002.jpg"
    )

    # 2026-03 publish will overwrite conflicts
    _touch_empty(
        darkroom_2026
        / "2026-03 publish will overwrite conflicts"
        / "PUBLISH"
        / "same_name_0001.jpg"
    )
    _touch_empty(
        data
        / "showroom"
        / "2026"
        / "2026-03 publish will overwrite conflicts"
        / "same_name_0001.jpg"
    )

    # 2026-03 publish will fail missing publish dir (no PUBLISH/)
    _touch_empty(
        darkroom_2026 / "2026-03 publish will fail missing publish dir" / ".gitkeep"
    )

    # 2026-03 publish will fail empty publish dir (album root in git; PUBLISH empty)
    _touch_empty(
        darkroom_2026 / "2026-03 publish will fail empty publish dir" / ".gitkeep"
    )
    _mkdir(darkroom_2026 / "2026-03 publish will fail empty publish dir" / "PUBLISH")

    # 2026-03 publish will fail publish has subdir (PUBLISH contains nested/)
    _touch_empty(
        darkroom_2026
        / "2026-03 publish will fail publish has subdir"
        / "PUBLISH"
        / "nested"
        / ".gitkeep"
    )
    _touch_empty(
        darkroom_2026
        / "2026-03 publish will fail publish has subdir"
        / "PUBLISH"
        / "export_ignored.jpg"
    )

    # 2026-03 tidy basic moves jpg and xmp (untidy at album root)
    _touch_empty(
        darkroom_2026 / "2026-03 tidy basic moves jpg and xmp" / "IMG_0001.jpg"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 tidy basic moves jpg and xmp" / "IMG_0001.xmp"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 tidy basic moves jpg and xmp" / "IMG_0002.jpg"
    )

    # 2026-03 archive basic success
    _touch_empty(
        darkroom_2026 / "2026-03 archive basic success" / "PHOTOS" / "keep_0001.jpg"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 archive basic success" / "VIDEOS" / "clip_0001.mp4"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 archive basic success" / "iPhone" / "IMG_1001.jpg"
    )
    _touch_empty(
        darkroom_2026 / "2026-03 archive basic success" / "iPhone" / "IMG_1001.xmp"
    )

    # 2026-03 archive will fail on conflict
    _touch_empty(
        darkroom_2026
        / "2026-03 archive will fail on conflict"
        / "PHOTOS"
        / "conflict_0001.jpg"
    )
    _touch_empty(
        data
        / "archive"
        / "2026"
        / "2026-03 archive will fail on conflict"
        / "PHOTOS"
        / "conflict_0001.jpg"
    )


if __name__ == "__main__":
    main()
