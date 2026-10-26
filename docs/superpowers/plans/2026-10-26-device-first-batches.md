# Device-first Batches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox syntax for
> tracking. Execution method is to be chosen by the user.

**Goal:** Replace albums with batches, organize darkroom by device, and
preserve existing actions and UI behavior with reordered destination paths.

**Architecture:** Keep the filesystem-backed darkroom tree and existing
prepare/execute actions. Centralize reversible path mapping in a small
pure module shared by actions and manager destination helpers. Apply the
model, scanner, and UI changes together as one integrated refactor.

**Tech Stack:** Python 3.13, NiceGUI 3.9, Pydantic 2, pathlib, pytest,
Ruff, and ty. No new dependencies.

**Spec:** `../specs/2026-10-26-device-first-batches-design.md`

## Global constraints

- Darkroom: `DEVICE/YEAR/BATCH`; archive/showroom: `YEAR/BATCH/DEVICE`.
- Keep `YYYY-MM[-DD][ title]` and its current validation/defaults.
- UI discovery remains darkroom-only; no Unarchive or combined catalog.
- Device/year nodes are organizational; batch actions match album actions.
- No real photo files, live configuration, or migration tooling are touched.
- Keep settings, external-tool commands, and action conflict policies.
- Keep rename local to darkroom, even when it breaks destination matching.
- No persistent IDs, workflow metadata, device registry, or new dependencies.
- Wrap all generated markdown files at 80 columns.

## Review focus

1. Two devices with the same batch name must never share a device target.
2. Nested paths and reverse mapping must retain every trailing component.
3. A custom device name must not escape darkroom or trigger media-folder
   special handling; validation must happen before directory creation.
4. New devices/years and empty darkroom must refresh without missing rows.
5. Archived-only batches must stay absent, and destination links must agree
   with the actual publish/archive targets.

Tasks below pin each of these conditions with tests or a named GUI check.

## File responsibilities

Paths below are repository-relative; `src` means
`src/photo_darkroom_manager` in this section only.

| Files | Responsibility |
| --- | --- |
| `src/paths.py` (new) | Pure conversion between the two layouts |
| `src/models.py` | Batch names, device input, darkroom recognition |
| `src/scan.py` | Device/year/batch tree and scoped scans |
| `src/actions.py` | Batch creation, mapped destinations, terminology |
| `src/manager.py` | Device discovery, action factories, path helpers |
| `src/gui/layout.py` | New Batch form, tree rendering, refresh |
| `src/gui/node.py` | Organizational rows and batch actions/links |
| `src/gui/gui_app.py` | Command-placeholder help terminology |
| `tests/test_paths.py` (new) | Conversion contract |
| Existing model/scan/manager/action tests | Updated behavior contracts |
| `tests/data/` and its generator | Both layouts in synthetic fixtures |
| README and BIG_PICTURE | Current user-facing convention |

Do not restructure unrelated modules. Historical architecture notes and
the pending diacritics proposal are not deliverables of this change.

## Task 1: Define and verify reversible path mapping

**Files:** Create `src/photo_darkroom_manager/paths.py` and
`tests/test_paths.py`.

**Interfaces:** Produce this pure function and layout type:

```python
Layout = Literal["device-first", "batch-first"]

def translate_path(
    path: Path,
    *,
    from_root: Path,
    to_root: Path,
    from_layout: Layout,
    to_layout: Layout,
) -> Path: ...
```

Consume no settings or filesystem state. Reorder only the first three
relative components; preserve the remaining tail. Same-layout conversion
only changes the root. Require at least three components for all calls.
Reject paths outside the source root and relative traversal components
with `ValueError`. Do not require either source or destination to exist.
Date/title validation remains the model's responsibility.

- [ ] Add `test_translate_path_reorders_and_round_trips` with these exact
  input/output assertions, parameterized for no tail and `PHOTOS/x.raw`:

  ```python
  source = Path("/dr/Camera/2026/2026-10 Walk/PHOTOS/x.raw")
  expected = Path("/ar/2026/2026-10 Walk/Camera/PHOTOS/x.raw")
  actual = translate_path(
      source, from_root=Path("/dr"), to_root=Path("/ar"),
      from_layout="device-first", to_layout="batch-first",
  )
  assert actual == expected
  assert translate_path(
      actual, from_root=Path("/ar"), to_root=Path("/dr"),
      from_layout="batch-first", to_layout="device-first",
  ) == source
  ```

- [ ] Add `test_same_layout_preserves_relative_path` for archive/showroom;
  `test_devices_have_distinct_targets` for Camera and Phone with the same
  date/title; and `test_translate_rejects_invalid_paths` for outside-root,
  fewer than three components, and a `..` component. Assert `ValueError`
  for invalid inputs and no filesystem writes for any conversion.
- [ ] Run `uv run pytest tests/test_paths.py -q`; expect failure because
  the mapping module is not implemented yet.
- [ ] Implement the interface above using pathlib component reordering.
- [ ] Run `uv run pytest tests/test_paths.py -q`; expect all tests passing.
- [ ] Commit this tested unit with `feat: add photo layout path mapping`.

## Task 2: Integrate device-first batches through the application

**Files:** Modify the existing models, scanner, actions, manager, three GUI
modules, their tests, and synthetic fixtures listed above. Rename
`tests/actions/test_new_album_rename.py` to `test_new_batch_rename.py`.

This is one integrated task because node types, action factories, and UI
consumers must agree. Do not leave temporary album aliases in the result.

**Interfaces:** Consume Task 1's `translate_path`. Produce:

```python
# models.py
class BatchFolderName(BaseModel): ...  # existing naming contract

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

# manager.py: methods on DarkroomManager
def list_devices(self) -> list[str]: ...

def new_batch_action(
    self, device: str, year: str, month: str,
    day: str | None, name: str | None,
) -> Action: ...

# actions.py: constructor on NewBatchAction
def __init__(
    self, darkroom_path: Path, device: str, year: str, month: str,
    day: str | None, name: str | None,
) -> None: ...
```

Retain manager `darkroom_path`, `archive_path`, and `showroom_path`
keyword interfaces and their exactly-one-source argument checks. Delegate
to Task 1's mapper with explicit layouts. Retain action factory names for
publish, archive, tidy, external launch, and rename; rename their album
parameters to batch where applicable.

- [ ] Adapt model, scanner, manager, creation, publication, and archive
  tests plus synthetic fixtures to the new layouts. Remove fixture device
  nesting that represents the old convention; retain generic nested
  folders to exercise subtree behavior. Keep fixtures synthetic and make
  the generator produce exactly the same new layout.
- [ ] Add `test_new_batch_existing_and_custom_device`, parameterized for
  an existing device and an empty darkroom. Execute the new action with
  device Camera and date 2026/10, no day/title, and assert:

  ```python
  batch = settings.darkroom / "Camera" / "2026" / "2026-10"
  assert result.success
  assert batch.is_dir()
  assert (batch / "PUBLISH").is_dir()
  assert not (batch / "PHOTOS").exists()
  assert not (batch / "VIDEOS").exists()
  ```

- [ ] Add device validation cases: blank, `.`, `..`, `../Camera`, slash,
  backslash, colon, control character, Windows reserved name `CON`, and
  `PUBLISH`/`PHOTOS`/`VIDEOS` in any case must fail without creating files.
  Accept `Camera`, `My Camera`, and `Aparat Łukasza`. Trim surrounding
  whitespace; reject trailing dots and Windows forbidden characters or
  reserved device names, including reserved names with extensions.
- [ ] Pin creation conflicts: an existing batch or file blocking a device
  path produces an unsuccessful action result and preserves existing data.
  Reject custom-device symlinks resolving outside darkroom before writes.
- [ ] Add `test_scan_device_year_batch_and_scoped_refresh`: assert node
  types root/device/year/batch/subfolder, parent links, and counts/issues
  rolled up through device. Exercise creation beneath a new year/device
  and scoped changes to an existing batch. Preserve existing year/date
  prefix filtering; do not add strict scanner validation in this refactor.
- [ ] Add `test_list_devices_includes_empty_directories`: include sorted
  immediate directories only, exclude files, and see changes on a fresh
  call. No saved registry or automatic default device.
- [ ] Add publish/archive assertions with Camera and Phone contributions:
  both target `2026/2026-10 Walk/<device>` independently. Verify archive
  preserves nested tails, publish strips only its staging `PUBLISH`, and
  manager destination links equal the action plan destinations at batch
  and archive-subfolder level. Retain overwrite and conflict regression
  tests, including conflicts appearing after preparation.
- [ ] Add regressions asserting rename changes only darkroom, a fully
  archived batch is absent on rescan, and loose RAW/JPEG/video/sidecar
  fixtures are tidied without moving `PUBLISH` contents. Retain existing
  sidecar grouping semantics rather than redesigning them.
- [ ] Run `uv run pytest -q`; expect failures from the old interfaces,
  hierarchy, and destination layout. Establish that they exercise the
  intended changes before implementation.
- [ ] Implement models and device validation. Preserve current batch
  name validators exactly, including optional title/day behavior. Return
  `None` for too-shallow recognition and retain exceptions for paths
  outside darkroom or invalid recognized components.
- [ ] Implement scanner node types and root/device/year traversal. Update
  scoped rescans, statistics, and logs. Device folders are organizational
  nodes; their issues summarize descendants. Do not scan other roots.
- [ ] Implement manager discovery and batch factory, then action changes.
  Validate creation inputs before writes. Publish maps the batch root;
  archive maps the selected path. Preserve preparation previews, execution
  errors, conflict policies, and scoped-rescan result semantics.
- [ ] Update the GUI atomically with these interfaces: New Batch toolbar
  form, searchable required device selection with custom input, unchanged
  date defaults, and no auto-selected device. Obtain choices on form open.
  For device/year nodes, return after the darkroom Open button. Keep
  existing batch/subfolder/PUBLISH action gates and destination checks.
- [ ] Update all UI terminology, command help, preview text, log fields,
  model/factory imports, and locals that denote the renamed concept.
  Refresh the nearest existing ancestor after creation, with full refresh
  fallback for a new device; keep the current path-based UI registry.
- [ ] Run `uv run pytest -q`; expect all tests passing, including existing
  media, filesystem, settings, and external-launch regression tests.
- [ ] Commit the integrated change with
  `feat: organize darkroom by device and batch`.

## Task 3: Document and verify the completed convention

**Files:** Modify `README.md`, `BIG_PICTURE.md`, and `tests/data/README.md`.
Use temporary roots for GUI checks; no live settings writes.

**Interfaces:** Consume the completed application from Task 2. No new API.

- [ ] Update folder diagrams and examples with both layouts, New Batch
  device selection, loose intake files, and PUBLISH placement. Explain
  manual migration and preserve the existing darkroom-only UI description.
- [ ] Run `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check .`, and `uv run ty check`. Expect successful
  exit status from each; address failures attributable to this change.
- [ ] Perform a GUI check using `PHOTO_DARKROOM_MANAGER_CONFIG_PATH`
  pointing to a temporary configuration and temporary three-root fixture:
  create a first custom device, then select it for another batch; create a
  second device with the same date/title; inspect action gates and new
  hierarchy visibility. Confirm blank device input prevents creation.
- [ ] On those temporary files, publish and archive with previews. Confirm
  Explorer links identify the destinations used by the actions. Confirm
  no destination links appear on device/year rows and fully archived
  batches disappear after refresh. Do not change subfolder showroom-link
  semantics or add an Unarchive button.
- [ ] Check the final diff for unintended dependencies, real-data paths,
  persistent settings changes, migration tooling, and legacy aliases.
  Confirm generated Markdown lines are no longer than 80 columns.
- [ ] Commit documentation with `docs: describe device-first batches`.

## Completion and handoff

Deliver the implementation with passing automated checks and the recorded
temporary-data GUI result. Report any check that could not run accurately.
Do not push, merge, migrate real files, or broaden behavior as part of this
plan. The branch is `device-first-order`; inspect its state before starting.

Recommended execution method: native/inline. The main refactor shares
models and signatures across actions, scanner, and UI, so sequential work
keeps those changes coherent. Choose execution after reviewing this plan.
