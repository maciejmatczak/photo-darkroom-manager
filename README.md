# photo-darkroom-manager

Micro helper for moving photo files around.

## Installation

```bash
uv tool install git+https://github.com/maciejmatczak/photo-darkroom-manager
```

## Concepts

Configuration is managed via a `darkroom.yaml` file that defines the paths for darkroom, showroom, and archive directories.

- **Darkroom**: Your working directory where photos are organized and edited.
  - Structure: `/.../darkroom/YYYY/YYYY-MM[ Album Name]/`
- **Showroom**: Where published photos are moved. Mirrors the darkroom structure.
  - Structure: `/.../showroom/YYYY/YYYY-MM[ Album Name]/`
- **Archive**: Where archived albums or device folders are stored. Same structure.
  - Structure: `/.../archive/YYYY/YYYY-MM[ Album Name]/`
- **Albums**: Organized by year and follow the format `YYYY-MM[ Album Name]` (e.g., `2024-01 Vacation`)
- **Device folders**: Optional subdirectories within albums (e.g., `iPhone`, `Camera`) for organizing photos by source device
  - Structure: `/.../darkroom/YYYY/YYYY-MM[ Album Name]/<Device Folder>/`
- **PUBLISH directory**: A special `PUBLISH/` subdirectory within albums containing files ready to be published to the showroom
  - Structure: `/.../darkroom/YYYY/YYYY-MM[ Album Name]/PUBLISH/`

## Commands

### `publish`

Moves files from an album's `PUBLISH` directory to the showroom.

```bash
photo-darkroom-manager publish
```

Must be run from within a recognized darkroom album directory. The `PUBLISH` subdirectory must contain files (not directories). The command will:
- Create the target directory in the showroom if it doesn't exist (with confirmation)
- Show a progress bar while moving files
- Require confirmation before moving

**Example:** From `/.../darkroom/2024/2024-01 Vacation/`, files in `PUBLISH/` are moved to `/.../showroom/2024/2024-01 Vacation/`.

---

### `archive`

Archives an album or device folder from the darkroom to the archive directory.

```bash
photo-darkroom-manager archive [PATH]
```

If `PATH` is not provided, uses the current directory. Archives the entire album or just the device folder, depending on the current location. Requires confirmation before moving.

**Examples:**
- From `/.../darkroom/2024/2024-01 Vacation/`: archives entire album to `/.../archive/2024/2024-01 Vacation/`
- From `/.../darkroom/2024/2024-01 Vacation/iPhone/`: archives only device folder to `/.../archive/2024/2024-01 Vacation/iPhone/`

## Development

Install [uv](https://docs.astral.sh/uv/), then `uv sync --group dev` and install pre-commit hooks (including `commit-msg` for conventional commits). See [DEV.md](DEV.md) for the full workflow and CI notes.
