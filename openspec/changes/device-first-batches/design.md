## Context

The app derives its UI tree from the darkroom folder only and runs
prepare/execute actions (tidy, publish, archive, rename, new album,
open external). Destinations were found by substituting the root, which
only works when all roots share one layout.

## Goals / Non-Goals

**Goals:**

- Group active work by device: `DARKROOM/DEVICE/YEAR/BATCH/`.
- Group stored results by year and batch:
  `ARCHIVE|SHOWROOM/YEAR/BATCH/DEVICE/`.
- Keep every existing batch action and its behavior.

**Non-Goals:**

- Migration tooling or touching real photo data.
- A combined catalog across roots; archived-only batches stay hidden.
- Unarchive, device profiles, progress tracking, photo preview.

## Layout

```text
DARKROOM/DEVICE/YEAR/BATCH/
  PUBLISH/
  loose files and optional subfolders
  PHOTOS/    (created by Tidy when needed)
  VIDEOS/    (created by Tidy when needed)

ARCHIVE/YEAR/BATCH/DEVICE/
  archived files and subfolders

SHOWROOM/YEAR/BATCH/DEVICE/
  published files
```

Two devices with identical year/batch names share a destination batch
parent but keep separate device folders.

## Decisions

### Path translation between areas

Darkroom and destination roots no longer share a layout, so a root swap
cannot find the matching folder: Camera's darkroom batch would land in
the wrong place and devices could collide. Translation must also work
back from archive or showroom to darkroom, so it has to be reversible and
keep the trailing part of the path.

Callers translate between named areas (darkroom, archive, showroom), not
between layouts. Which layout an area uses is fixed by the library layout
and known only to the path module; callers never name a layout. This
removes a class of mismatched calls and keeps layout knowledge in one
place.

Translation is pure: it receives the three roots as a value, never reads
settings, and never touches the filesystem, so destinations that do not
exist yet can be resolved and the mapping is cheap to test exhaustively.
Paths outside the source root, too shallow to identify a batch, or
containing `..` are rejected.

*Alternative:* the device-first layout in all roots, keeping a plain root
swap. Rejected: stored results should be grouped by year and batch.

*Alternative:* callers pass source and target layouts explicitly.
Rejected: the layout is a fixed property of each area, so restating it at
every call adds nothing and allows mismatches.

### Darkroom-only UI

The tree remains derived exclusively from darkroom. A combined catalog was
discussed and explicitly declined. Reverse path helpers remain supported.

### Device rows start new batches

Device and year nodes have no batch actions or destination links: they
group batches, they are not batches. A device row additionally offers New
Batch with that device preselected, because the device is the natural
place to start intake for it. The toolbar New Batch stays for a first or
new device. Year rows keep only Open in Explorer, counts, issues, and
expand/collapse.

### Device choice without a registry

Device choices are the immediate directories of darkroom, refreshed when
the form opens, sorted by name, including empty directories, with no
automatic default. A custom name must be a safe single directory
component on Windows.

### Rename stays local

Rename changes only the darkroom folder. Names remain path-based anchors;
no coordinated rename or persistent identity is added.

## Interfaces

```python
# models.py
class DarkroomBatch(BaseModel):
    device: str
    year: str
    batch: str
    batch_path: Path
    relative_subpath: Path  # full selected path relative to darkroom

    @property
    def publish_dir(self) -> Path: ...

def recognize_darkroom_batch(
    darkroom_path: Path, path: Path,
) -> DarkroomBatch | None: ...

def validate_device_name(value: str) -> str: ...

# manager.py: DarkroomManager
def list_devices(self) -> list[str]: ...
def new_batch_action(
    self, device: str, year: str, month: str,
    day: str | None, name: str | None,
) -> Action: ...

# actions.py
class NewBatchAction(Action):
    def __init__(
        self, darkroom_path: Path, device: str, year: str, month: str,
        day: str | None, name: str | None,
    ) -> None: ...
```

Manager `darkroom_path`, `archive_path`, and `showroom_path` keep their
keyword interfaces and exactly-one-source checks, delegating to area
translation.

## Risks / Trade-offs

- Two devices with the same batch name must never share a device target
  → covered by mapper and publish/archive tests.
- Nested paths must keep every trailing component → round-trip tests.
- A custom device name could escape darkroom or collide with media-folder
  handling → validate before any directory creation; reject symlinks
  resolving outside darkroom.
- New devices/years or an empty darkroom could leave rows missing after
  refresh → refresh nearest existing ancestor, full refresh fallback.
- Rename breaks destination matching for existing archive/showroom
  folders → accepted; documented.

## Migration Plan

Code, docs, and synthetic fixtures only. The user moves real folders
manually. No legacy layout support remains after the change.
