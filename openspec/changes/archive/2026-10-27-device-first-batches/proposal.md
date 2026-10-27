## Why

Active photo work is easier to manage grouped by the device it came from.
Today the darkroom is organized `YEAR/ALBUM/DEVICE`, and the "album" name
implies a final, well-organized event. Renaming the concept to **batch**
lets its name stay provisional so intake, editing, RAW development, and
publishing can proceed without perfect album organization upfront.

Stored results (archive, showroom) should stay grouped by year and batch,
so darkroom and destination roots now use different layouts. Root
substitution no longer works; path translation becomes a first-class,
isolated concern.

## What Changes

- **BREAKING** Darkroom layout becomes `DARKROOM/DEVICE/YEAR/BATCH/`;
  archive and showroom become `ROOT/YEAR/BATCH/DEVICE/`. No legacy layout
  support; the user migrates real folders manually.
- Rename the Album concept to Batch throughout code, UI, logs, and docs.
- Introduce pure path translation between areas (darkroom, archive,
  showroom); each area's layout is known only to the path module.
- Scanner builds root/device/year/batch/subfolder trees.
- New Batch requires a device (existing folder or validated custom name).
- Publish and archive target `YEAR/BATCH/DEVICE` via the mapper.
- Device rows offer New Batch for that device; year rows only group.

## Non-goals

No migration command, device registry, persistent IDs, workflow metadata,
combined catalog, archive/showroom scanning, Unarchive action, new
dependencies, or diacritics change.

## Capabilities

Specs are organized by abstraction level rather than by module:

- **Domain:** `library-layout` defines what the darkroom, archive, and
  showroom are, how they relate, their folder layouts, and naming.
- **Actions:** one `action-<name>` spec per user operation (create batch,
  rename batch, tidy, publish, archive, open external). Each describes
  only its behavior and refers to `library-layout` for locations.
- **Supporting areas:** `core` (darkroom tree, device discovery,
  destination resolution), `statistics`, `settings`, `user-interface`.

This change touches the capabilities below. `action-tidy`,
`action-open-external`, and `settings` are unaffected.

### New Capabilities

- `library-layout`: Roles of the three roots, device-first darkroom and
  batch-first archive/showroom layouts, reversible path translation between
  them, batch and device names, and recognizing a batch from a path.
- `core`: Darkroom-only tree of device, year, batch, and subfolder nodes;
  scoped rescans; device discovery; destination resolution shared by
  actions and the UI.
- `statistics`: Counts and issues rolled up through year and device nodes.
- `action-create-batch`: Creating a batch for a device, validating before
  writes, and creation conflicts.
- `action-publish`: Publishing `PUBLISH/` contents to the showroom device
  folder.
- `action-archive`: Archiving a batch or subfolder to its mapped archive
  location.
- `action-rename-batch`: Rename changes only the darkroom folder.
- `user-interface`: Batch terminology, device and year rows (New Batch
  from a device row), batch row actions, the New Batch form, refresh
  after creation.

### Modified Capabilities

None (no specs exist yet). The pending `album-title-diacritics` change
defines `darkroom-album`; its naming rules belong to `library-layout` and
must be rebased onto it if that change is applied later.

## Impact

- `library-layout`: `paths.py` (new, done with `tests/test_paths.py`),
  `models.py`, `tests/test_models.py`.
- `core`: `scan.py`, `manager.py` (rescans, `list_devices`, path helpers).
- `statistics`: `scan.py` roll-up, `gui/widgets.py` badges.
- `action-*`: `actions.py`, `manager` factories, `tests/actions/`
  (`test_new_album_rename.py` becomes `test_new_batch_rename.py`).
- `user-interface`: `gui/layout.py`, `gui/node.py`, `gui/gui_app.py`.
- Shared: synthetic fixtures in `tests/data/` and generator; `README.md`,
  `BIG_PICTURE.md`, `tests/data/README.md`.
- Unchanged: settings format, external-tool configuration, move
  semantics, conflict policies.
