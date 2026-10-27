## 1. Path translation (`library-layout`)

- [x] 1.1 Add `tests/test_paths.py`: reorder and round trip (with and
      without `PHOTOS/x.raw` tail), same-layout root swap, distinct
      device targets, invalid paths raise `ValueError`
- [x] 1.2 Implement `src/photo_darkroom_manager/paths.py`
      (`translate_path`, `Layout`)
- [x] 1.3 Replace layout arguments with area translation: callers pass
      source and target area plus the three roots; layouts become private
      to `paths.py`. Rewrite `tests/test_paths.py` against the spec
      scenarios (darkroom to archive and back, showroom to archive changes
      only the root, unsafe paths) and update all call sites

## 2. Tests and fixtures for the new layout

- [x] 2.1 Adapt model, scanner, manager, and action tests plus the
      fixture generator and `tests/data/` to the new layouts; remove old
      device nesting, keep generic nested folders
- [x] 2.2 Rename `tests/actions/test_new_album_rename.py` to
      `test_new_batch_rename.py`
- [x] 2.3 `library-layout`: device name cases (rejected and accepted
      lists) and batch recognition (path inside a batch; root, device,
      and year paths recognize no batch)
- [x] 2.4 `action-create-batch`: add
      `test_new_batch_existing_and_custom_device` (existing device and
      empty darkroom; `PUBLISH/` only), invalid device creates nothing,
      symlink escape, existing batch or blocking file preserved
- [x] 2.5 `core`: add `test_scan_device_year_batch_and_scoped_refresh`
      (node kinds, empty darkroom, new year under existing device, fully
      archived batch absent)
- [x] 2.6 `core`: add `test_list_devices_includes_empty_directories`
      (sorted, files excluded, fresh on each call)
- [x] 2.7 `statistics`: untidy batch issue and count changes roll up
      through year and device to root
- [x] 2.8 `action-publish` / `action-archive`: Camera and Phone sharing a
      batch land in separate device folders; archive keeps nested tail;
      `core` path helpers equal action destinations; keep conflict and
      overwrite regressions
- [x] 2.9 `action-rename-batch`: rename after publish leaves showroom and
      archive names unchanged
- [x] 2.10 Regression: loose files tidied without touching `PUBLISH`

## 3. Implementation

- [x] 3.1 `library-layout`: `DarkroomBatch`, `recognize_darkroom_batch`,
      `validate_device_name` in `models.py`; keep batch name validators
      exactly
- [x] 3.2 `core` / `statistics`: root/device/year/batch traversal, scoped
      rescans, roll-up, logs; darkroom only
- [x] 3.3 `core`: `list_devices`, `new_batch_action`, and
      `darkroom_path`/`archive_path`/`showroom_path` via area translation
- [x] 3.4 Actions: `NewBatchAction` with device; publish and archive
      destinations via area translation; preserved previews and conflict
      policies
- [x] 3.5 `user-interface`: toolbar New Batch (no device preselected) and
      device-row New Batch (device preselected, changeable); required
      device with custom input; year rows have no actions or links;
      batch, subfolder, and `PUBLISH` row actions and link gates kept
- [x] 3.6 `user-interface`: rename Album to Batch in UI text, help,
      previews, logs, imports, and locals; no legacy aliases
- [x] 3.7 `user-interface`: refresh nearest existing ancestor after
      creation, full refresh for a new device
- [x] 3.8 Run `uv run pytest -q`; all pass

## 4. Documentation and verification

- [x] 4.1 Update `README.md`, `BIG_PICTURE.md`, `tests/data/README.md`
      to match `library-layout` (areas, both layouts), New Batch device
      choice, and manual migration
- [x] 4.2 Run `uv run pytest -q`, `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run ty check`,
      `openspec validate device-first-batches --strict`
- [x] 4.3 GUI check on temporary roots via
      `PHOTO_DARKROOM_MANAGER_CONFIG_PATH`: toolbar New Batch with a
      custom device, device-row New Batch preselects that device, second
      device same batch, blank device blocked, year rows show no actions,
      publish/archive previews and links, archived batch disappears
- [x] 4.4 Review the changes: no new dependencies, real paths, settings changes,
      migration tooling, legacy aliases, or caller-supplied layouts;
      markdown within 80 columns
