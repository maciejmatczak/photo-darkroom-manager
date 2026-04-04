---
name: Add GUI test data folders
overview: Create a `tests/data/` fixture tree containing example darkroom/showroom/archive directories with empty media files (.jpg/.mp4) and some .xmp sidecars, covering publish/archive/tidy happy paths plus intentional failure/edge-case albums (missing/empty PUBLISH, PUBLISH with subdir, untidy media placement, and archive path conflicts).
todos:
  - id: add-data-tree
    content: Create `tests/data/{darkroom,showroom,archive}` with the albums and seeded conflicts described above (0-byte .jpg/.mp4 plus some .xmp).
    status: completed
  - id: add-fixture-readme
    content: Add `tests/data/README.md` documenting each album scenario and which GUI action(s) it targets.
    status: completed
isProject: false
---

# Create fixture filesystem under tests/data

## What we’re modeling (from current code)

- **Album discovery**: scanner only treats `<darkroom>/<YYYY>/<ALBUM>/` where `YYYY` is 4 digits and `ALBUM` matches `^YYYY-MM`.
  - See `ALBUM_PATTERN` in [src/photo_darkroom_manager/gui/scanner.py](src/photo_darkroom_manager/gui/scanner.py).
- **Publish**:
  - Requires `<album>/PUBLISH/` to exist, contain **only files**, and be **non-empty**.
  - Targets `<showroom>/<YYYY>/<ALBUM>/` and reports **conflicts** when a file already exists there.
  - See `prepare_publish()` in [src/photo_darkroom_manager/gui/actions.py](src/photo_darkroom_manager/gui/actions.py).
- **Archive**:
  - Can run on an album folder or any subfolder under an album; target is `<archive>/<relative_subpath_from_darkroom>/`.
  - **Blocks** if any destination leaf path already exists in archive.
  - See `prepare_archive()` in [src/photo_darkroom_manager/gui/actions.py](src/photo_darkroom_manager/gui/actions.py) and `preview_merge_into_archive()` in [src/photo_darkroom_manager/file_utils.py](src/photo_darkroom_manager/file_utils.py).
- **Tidy / untidy**:
  - A folder is **untidy** if media files sit directly in it (except when the folder is `PHOTOS`, `VIDEOS`, or `PUBLISH`).
  - `tidy` moves *related sets* of files that share the same basename (e.g. `IMG_0001.jpg` + `IMG_0001.xmp`) into `PHOTOS/` or `VIDEOS/`.
  - See `_detect_untidy()` and `_collect_tidy_photo_video_paths()` in [src/photo_darkroom_manager/gui/scanner.py](src/photo_darkroom_manager/gui/scanner.py) and [src/photo_darkroom_manager/gui/actions.py](src/photo_darkroom_manager/gui/actions.py).

## Directory layout to add

Add a new fixture root:

- `tests/data/`
  - `darkroom/` (input tree the GUI scans)
  - `showroom/` (publish destination)
  - `archive/` (archive destination)

All “images/videos” are **0-byte files** with correct extensions, plus a few `.xmp` sidecars.

## Concrete fixture tree (proposed)

### Darkroom fixtures

Under `tests/data/darkroom/2026/` create these albums (descriptive names, all start with `2026-03`):

- `**2026-03 publish basic success`**
  - `PUBLISH/` contains:
    - `export_0001.jpg`, `export_0001.xmp`
    - `export_0002.jpg`
  - Purpose: `prepare_publish` succeeds with 0 conflicts when showroom target is empty.
- `**2026-03 publish will overwrite conflicts**`
  - `PUBLISH/` contains:
    - `same_name_0001.jpg`
  - Purpose: `prepare_publish` succeeds but reports conflicts when `tests/data/showroom/...` already has `same_name_0001.jpg`.
- `**2026-03 publish will fail missing publish dir**`
  - No `PUBLISH/` folder.
  - Purpose: `prepare_publish` fails: “PUBLISH directory does not exist”.
- `**2026-03 publish will fail empty publish dir**`
  - `PUBLISH/` exists but is empty.
  - Purpose: `prepare_publish` fails: “PUBLISH directory is empty”.
- `**2026-03 publish will fail publish has subdir**`
  - `PUBLISH/` contains a directory `nested/` (can be empty).
  - Purpose: `prepare_publish` fails: “PUBLISH directory contains subdirectories”.
- `**2026-03 tidy basic moves jpg and xmp**`
  - Album root contains (directly in album root):
    - `IMG_0001.jpg`, `IMG_0001.xmp`
    - `IMG_0002.jpg`
  - Purpose: album is flagged **untidy**; `prepare_tidy` finds photo-related groups and `execute_tidy` would move them into `PHOTOS/`.
- `**2026-03 archive basic success`**
  - Example nested content:
    - `PHOTOS/keep_0001.jpg`
    - `iPhone/IMG_1001.jpg`, `iPhone/IMG_1001.xmp`
    - `VIDEOS/clip_0001.mp4` (0-byte)
  - Purpose: `prepare_archive` succeeds when archive destination is empty; also supports archiving a subfolder like `iPhone/`.
- `**2026-03 archive will fail on conflict**`
  - Contains a leaf file path that will conflict with pre-seeded archive, e.g.:
    - `PHOTOS/conflict_0001.jpg`
  - Purpose: `prepare_archive` fails with “Archive blocked: 1 path conflict(s) already in archive”.

### Archive fixtures (pre-seeded)

Under `tests/data/archive/2026/` create:

- `2026-03 archive will fail on conflict/PHOTOS/conflict_0001.jpg`
  - Purpose: blocks archiving the corresponding darkroom album due to duplicate destination leaf.

### Showroom fixtures (pre-seeded)

Under `tests/data/showroom/2026/` create:

- `2026-03 publish will overwrite conflicts/same_name_0001.jpg`
  - Purpose: makes `prepare_publish` report a conflict pair; `execute_publish` would overwrite.

## Notes / constraints

- Keep the fixture names stable and explicit; tests can reference them by string.
- Use only `.jpg` and `.mp4` (per your preference) plus some `.xmp` sidecars.
- Ensure all empty media files are actual files (0 bytes), not placeholders in git ignored patterns.

## Verification steps (after implementation)

- Add a lightweight README inside `tests/data/` describing what each album is meant to exercise.
- (Optional manual check) point GUI config at `tests/data/darkroom`, `tests/data/archive`, `tests/data/showroom` and verify:
  - publish prepare errors for the three failing publish albums
  - publish conflict preview for the overwrite album
  - archive conflict prepare error for the conflict album
  - untidy badges for the tidy album
