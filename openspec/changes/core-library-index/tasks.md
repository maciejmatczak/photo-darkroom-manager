# Tasks

## 1. Library package

- [x] 1.1 Create `src/photo_darkroom_manager/library/` with `layout.py`
      (contents of `library.py` and `models.py`) and `media.py` (contents
      of `media.py` plus `collect_files_to_tidy` and its helper from
      `actions.py`); delete the old modules, export public names from
      `__init__.py`, and update imports in `src` and `tests`; verify
      `grep -rnE "manager\.(models|media) |actions import collect" src
      tests` returns nothing and `uv run pytest` is green.
- [x] 1.2 Add `child_kind(parent_kind, name)` to `layout.py` as the one
      rule for node kinds, including `publish` for `PUBLISH` directly in a
      batch; verify with internal tests per parent kind, including a
      date-less folder under a year and `PUBLISH/extra`.
- [x] 1.3 Make the tidy tests import `collect_files_to_tidy` publicly from
      `library`; verify `grep -rn "_collect_files_to_tidy" tests` returns
      nothing.

## 2. Tree model and scan

- [x] 2.1 Add `tree.py` with `NodeId`, `NodeKind`, `NodeIssue`,
      `NodeAction`, `FileCounts`, frozen `NodeView` and
      `node_actions(kind)`; verify with contract tests for the
      `app/node-actions` scenarios "Batch actions" and "Publish folder
      actions".
- [x] 2.2 Implement `LibraryTree` (facts map, `view`, `contains`,
      `nearest`, `replace_subtree` recomputing totals and rolled-up issues
      from stored facts) and `_scan.scan_subtree` using `child_kind` and
      `media`; verify with tests that a subtree replacement updates
      ancestor totals with no ancestor folder read (patch the file
      counter) and that "View is a snapshot" holds.
- [x] 2.3 Remove `scan.py` and move `test_scan.py` to the new model,
      keeping the `app/darkroom-tree` and `app/statistics` scenarios as
      contract tests and adding "Publish folder kind"; verify
      `uv run pytest tests/library` is green and no test imports a
      private scan name.

## 3. Engine library API

- [x] 3.1 Add the busy guard (`_begin`, `EngineBusyError`) and the
      `library_scanning`, `library_scanned`, `library_scan()`,
      `library_node(id)` and `library_devices()` members, replacing
      `tree`, `scanning`, `rescan()` and `list_devices()`; verify with the
      `engine/library-index` scenarios "Batch id", "Batch with a
      subfolder", "Not scanned yet", "Unknown id", "During a scan" and
      "After a scan", and the "Empty device folder listed" test.
- [x] 3.2 Add `library_refresh(id)` with nearest-ancestor fallback,
      replacing `rescan_subtree(node)`; verify with the `engine/scanning`
      scenarios "New year under a device", "Folder not yet in the tree",
      "Folder gone from disk" and "Id survives a rescan".
- [x] 3.3 Rename the factories to `action_*`, add `action_execute(action,
      plan)` refreshing `rescan_node_path` and setting
      `ExecutionResult.library_refreshed`; update
      `test_batch_workflow.py`, `test_file_safety.py` and the action tests
      to execute through the engine; verify with "Tidy updates the tree"
      and "Opening an external app".

## 4. Engine configuration API

- [x] 4.1 Make the service private as `_user_config` and add
      `config_get`, `config_issues`, `config_set` (busy-guarded) and
      `config_save`; move `test_engine.py` and `conftest.py` to them;
      verify with "Configuration change is visible at once", "Edit during
      a scan", "Second scan" and "Reading while busy", and
      `grep -rn "\.user_config\b" src tests` returning nothing outside
      `engine.py`.
- [x] 4.2 Drop the scanned tree when `config_set` changes the darkroom;
      verify with "Darkroom moved in settings" and a test that setting the
      same darkroom keeps the tree.

## 5. Docs and integration

- [x] 5.1 Tick "Tree index owned by the core" in
      `docs/core-split/ROADMAP.md`, add a "Done in core-library-index"
      note to sections 2, 3 and 5 of `frontend-coupling.md`, and mark
      `IMPROVE_ARCHITECTURE.md` #1 done; verify the files wrap at 80
      columns.
- [x] 5.2 Run `uv run pytest`, `uv run ruff check`, `uv run ruff format
      --check` and `uv run ty check`; verify all pass and
      `openspec validate core-library-index --strict` is clean.

## Workflow follow-up

- Archive the change with spec sync after review.
