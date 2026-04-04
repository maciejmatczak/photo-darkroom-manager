# photo-darkroom-manager

Micro helper for moving photo files around.

## Installation

```bash
uv tool install --python 3.13 git+https://github.com/maciejmatczak/photo-darkroom-manager
```

After installation, run **`photo-darkroom-manager`** or **`dr-mng`** to open the GUI (native window). On first launch, configure darkroom, showroom, and archive paths; settings are stored under the platform user config directory (or the path in `PHOTO_DARKROOM_MANAGER_CONFIG_PATH` if set).

## Concepts

Refer to [BIG_PICTURE.md](BIG_PICTURE.md) for the conceptual overview.

## Using the app

The GUI shows your darkroom as a tree. From each album or subfolder you can **Tidy** (move photos/videos into `PHOTOS` / `VIDEOS`), **Archive** (merge into the archive tree), **Publish** (move files from `PUBLISH` into the showroom), **Rename** an album, or create a **New Album** from the toolbar.

**Example:** For an album at `/.../darkroom/2024/2024-01 Vacation/`, publishing moves files from `PUBLISH/` to `/.../showroom/2024/2024-01 Vacation/`.


## Development

Install [uv](https://docs.astral.sh/uv/), then `uv sync --group dev` and install pre-commit hooks (including `commit-msg` for conventional commits). See [DEV.md](DEV.md) for the full workflow and CI notes.
