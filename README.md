# photo-darkroom-manager

Micro helper for moving photo files around.

## Installation

```bash
# First installation
uv tool install --python 3.13 git+https://github.com/maciejmatczak/photo-darkroom-manager

# Upgrade
uv tool upgrade photo-darkroom-manager
```

After installation, run **`photo-darkroom-manager`** or **`dr-mng`** to open the GUI (native window). On first launch, configure darkroom, showroom, and archive paths; settings are stored under the platform user config directory (or the path in `PHOTO_DARKROOM_MANAGER_CONFIG_PATH` if set).

## Concepts

Refer to [BIG_PICTURE.md](BIG_PICTURE.md) for the conceptual overview.

## Using the app

The GUI shows your darkroom as a tree of devices, years, and batches. A
**batch** is a dated folder (`YYYY-MM[-DD][ title]`) of work from one device;
its name can stay provisional.

- **New Batch** (toolbar, or on a device row with that device preselected)
  creates `DEVICE/YEAR/BATCH/PUBLISH/`. Choose an existing device folder or
  type a new device name.
- On a batch or subfolder: **Tidy** (move photos/videos into `PHOTOS` /
  `VIDEOS`) and **Archive** (merge into the archive tree).
- On a batch: **Publish** (move files from `PUBLISH` into the showroom) and
  **Rename**. Rename changes only the darkroom folder.

The darkroom is organized by device; archive and showroom are organized by
year and batch, with one folder per device inside:

```text
darkroom/Camera/2024/2024-01 Vacation/PUBLISH/
showroom/2024/2024-01 Vacation/Camera/
archive/2024/2024-01 Vacation/Camera/
```

**Example:** publishing the batch above moves files from its `PUBLISH/` to
`showroom/2024/2024-01 Vacation/Camera/`.

**Migrating from albums:** earlier versions used
`darkroom/YEAR/ALBUM/DEVICE/`. Move existing folders to
`darkroom/DEVICE/YEAR/BATCH/` by hand; the app does not migrate them.

## Development

Install [uv](https://docs.astral.sh/uv/), then `uv sync --group dev` and install pre-commit hooks (including `commit-msg` for conventional commits). See [DEV.md](DEV.md) for the full workflow and CI notes.
