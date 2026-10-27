## `tests/data` fixtures

This directory contains a **small on-disk fixture filesystem** that mirrors how
the app operates with three roots:

- **`darkroom/`**: scanned by the GUI
- **`showroom/`**: publish destination
- **`archive/`**: archive destination

All `.jpg` / `.mp4` and `.xmp` files are intentionally **0 bytes**; only the
names and extensions matter for the current workflow logic.

### Layout

The darkroom is device-first; archive and showroom are batch-first:

```text
darkroom/DEVICE/YEAR/BATCH/
archive/YEAR/BATCH/DEVICE/
showroom/YEAR/BATCH/DEVICE/
```

All fixtures use the device `Camera`. Only directories under
`darkroom/<DEVICE>/<YYYY>/` whose names start with `YYYY-MM` are treated as
batches.

### Batches under `darkroom/Camera/2026/`

- **`2026-03 publish basic success`**
  - **Publish**: `PUBLISH/` contains a few files (`export_0001.jpg` + sidecar
    `export_0001.xmp`, and `export_0002.jpg`) so publish should prepare cleanly.

- **`2026-03 publish will overwrite conflicts`**
  - **Publish**: `PUBLISH/` contains `same_name_0001.jpg`.
  - **Conflict**:
    `showroom/2026/2026-03 publish will overwrite conflicts/Camera/` already
    contains `same_name_0001.jpg`, so publish prepare should report an
    overwrite conflict.

- **`2026-03 publish will fail missing publish dir`**
  - **Publish (fail)**: missing `PUBLISH/` directory.
  - Batch folder is held in git with a root `.gitkeep`.

- **`2026-03 publish will fail empty publish dir`**
  - **Publish (fail)**: `PUBLISH/` exists but contains **no files**.
  - The batch is tracked with a root `.gitkeep`; an empty `PUBLISH/` is not
    representable in git, so the test (and `create_test_data_fixtures.py`)
    creates that directory at runtime.

- **`2026-03 publish will fail publish has subdir`**
  - **Publish (fail)**: `PUBLISH/` contains a subdirectory (`nested/`), which
    should fail publish prepare.
  - `nested/.gitkeep` keeps the otherwise empty subdirectory in git.

- **`2026-03 tidy basic moves jpg and xmp`**
  - **Tidy**: media files sit directly in the batch root (`IMG_0001.jpg` +
    `IMG_0001.xmp`, `IMG_0002.jpg`), making it **untidy**. Tidy should move
    them under `PHOTOS/`.

- **`2026-03 archive basic success`**
  - **Archive**: contains typical subfolders (`PHOTOS/`, `VIDEOS/`, `nested/`)
    with leaf files, including an `.xmp` sidecar under `nested/`.

- **`2026-03 archive will fail on conflict`**
  - **Archive (fail)**: contains `PHOTOS/conflict_0001.jpg`.
  - **Conflict**:
    `archive/2026/2026-03 archive will fail on conflict/Camera/PHOTOS/` is
    pre-seeded with `conflict_0001.jpg`, so archive prepare should be blocked
    by a destination path conflict.
