# Tasks

## 1. Library: node kinds, ids and partial trees

- [ ] 1.1 Add `layout.node_kind(node_id) -> NodeKind | None` (a walk of
      `child_kind` over the id's parts) and export it from `library`;
      verify with internal tests for every kind, a date-less folder under
      a year, `PUBLISH/extra`, and malformed ids (`..`, empty parts,
      backslashes).
- [ ] 1.2 Add `library/_resolve.py` with `canonical_id(root, node_id)`,
      `resolve_path(root, path)` and `PathOutsideDarkroomError`; verify
      with contract tests for the `engine/library-index` scenarios
      "Lower-case path on a case-insensitive disk", "Publish folder typed
      in lower case", "Batch path" and "Archive path", plus internal
      tests that a symlinked device is not followed and that two
      case-insensitive matches keep only an exact one.
- [ ] 1.3 Add `complete` to `NodeFacts` and `NodeView`, `_scan.scan_chain`
      and `LibraryTree.load_subtree`; verify with tests that stub
      ancestors aggregate only the scanned branch, report incomplete, and
      become complete after their own scan or refresh, and that
      `uv run pytest tests/core/library` is green.

## 2. Actions: requests, plans, outcomes and results

- [ ] 2.1 Add `ActionRequest`, the step types (`Move`, `MakeDir`,
      `Rename`, `OpenFolder`, `Launch`), `ActionPlan` (summary, steps,
      `changes_files`, fingerprint, `preview_text()`), `Outcome`,
      `ActionResult` and the new `ExecutionResult` fields; make the base
      `prepare()` / `execute()` return `failed` on exceptions; verify
      with internal tests that the fingerprint is stable for equal plans and
      changes with any step, param or root.
- [ ] 2.2 Move tidy to the plan: `noop` when nothing to tidy, `refused`
      on conflicts at prepare and execute, moves only the plan's steps;
      verify by updating `tests/core/actions/test_tidy.py` and adding the
      `engine/action-requests` scenarios "Nothing to tidy" and "Late file
      in a tidy folder".
- [ ] 2.3 Replace `merge_tree_into_archive` with `move_files` and a public
      `prune_empty_dirs` in `file_utils`; archive plans list every move,
      execute moves only those, and the result reports done, failed and
      left files; verify with `tests/core/file_utils` and
      `tests/core/actions/test_archive.py`, including "Photo added after
      the preview", "Partial archive" (patched move failure) and
      "Archive empties the batch".
- [ ] 2.4 Move publish to the plan: overwrites marked on their `Move`
      steps and listed in the preview, `noop` for an empty `PUBLISH/`,
      overwrite behaviour unchanged; verify with
      `tests/core/actions/test_publish.py` and the "Republishing a batch"
      scenario.
- [ ] 2.5 Make rename prepare a `Rename` plan: validation and "already
      exists" at prepare, date and title defaults from the current name,
      clearing the title on request, `noop` for the same name, the new
      folder as `node_path`; verify with the `app/action-rename-batch`
      scenarios in `tests/core/actions/test_new_batch_rename.py`.
- [ ] 2.6 Make new batch prepare `MakeDir` steps for the missing device
      and year folders, the batch and `PUBLISH/`, with every name and
      symlink check at prepare and again at execute; verify with the
      `app/action-create-batch` scenarios, old and new, in
      `tests/core/actions/test_new_batch_rename.py`.
- [ ] 2.7 Make the external app action prepare a `Launch` step and
      execute exactly its argv, and add an open-folder action with an
      `OpenFolder` step and a patched `_open_folder`; verify with
      `tests/core/actions/test_open_external.py` and a new
      `test_open.py` covering the `app/action-open` scenarios.

## 3. Engine API

- [ ] 3.1 Add the guard `_target`, `ActionNotAllowedError`, and
      node-addressed factories `action_open`, `action_tidy`,
      `action_cull`, `action_edit`, `action_publish`, `action_archive`,
      `action_rename` and `action_new_batch`, with cull and edit commands
      from configuration, and set `node_id` on results from `node_path`;
      remove `action_open_external_app`; verify with contract tests for
      the `engine/action-requests` scenarios on addressing, guarding,
      creating a missing node, commands from configuration and "Results
      name the node after the action".
- [ ] 3.2 Add `action_apply(action, confirm=None)` under one busy
      guard; verify with the "Apply at once", "Plan changed since the
      preview" and "Plan unchanged" scenarios and a busy-engine test.
- [ ] 3.3 Add `library_scan(node_id="")` (scoped scan through
      `scan_chain` and `load_subtree`) and `library_resolve(path)`;
      verify with the `engine/library-index` scenarios "One batch,
      nothing scanned before" (patch the scan to record folders read),
      "Missing folder", "Root after scanning one batch" and "Full scan
      completes the tree".
- [ ] 3.4 Add `config_keys()`, a `console_level` in
      `configure_logging` and `console_log_level` on `Engine`; verify
      with `tests/core/test_logging_config.py` that stderr stays silent
      below its level while the file still gets the record, and with an
      engine test for `config_keys()`.
- [ ] 3.5 Move `test_engine.py`, `test_batch_workflow.py`,
      `test_file_safety.py`, `test_library_index.py`, `test_manager.py`
      and `conftest.py` to node ids, plans and outcomes; verify
      `uv run pytest` is green and `uv run lint-imports`, `uv run ty
      check` and `uv run ruff check` pass.
- [ ] 3.6 Update `docs/core-split/frontend-coupling.md`: opening a folder,
      rename defaults, form validation and structured previews now live
      in the core; verify the file names each moved rule's new home and
      is wrapped at 80 columns.

## 4. Command-line tool

- [ ] 4.1 Create `cli/__init__.py` (`main`), `cli/__main__.py`,
      `cli/_app.py` with the parser for every command and global options
      (`--json`, `--config`, `-v`), and add
      `darkroom` and `dr` scripts for `photo_darkroom_manager.cli:main` to
      `[project.scripts]` with `prog="darkroom"`; verify `uv run darkroom
      --help` and `uv run dr --help` both list every command under the
      name `darkroom`, and in-process tests cover "Help lists the
      commands" and "Alias runs the same command".
- [ ] 4.2 Implement `cli/_targets.py` (`id:`, paths, bare targets, the
      default `inspect` target); verify with tests under `tests/cli/` for
      "Inside a batch folder", "Id from anywhere", "Tab-completed folder
      name", "Ambiguous target" and "Showroom path".
- [ ] 4.3 Implement `status` and `config list | get | set` (set validates
      and saves); verify with tests for "Set the archive root", "Invalid
      log level" and a `status` run on an unconfigured engine.
- [ ] 4.4 Implement `inspect` with `--depth`, text and JSON, over
      `library_scan(id)` and `library_node(id)`; verify with "Batch with
      depth one", "Machine-readable inspect" and "One batch in a large
      library".
- [ ] 4.5 Implement the action commands: preview by default, `--apply`
      and `--confirm FINGERPRINT` as mutually exclusive options,
      immediate run when a plan changes no files, and rename and
      new-batch options; verify with "Archive preview", "Confirm the plan
      shown", "Confirm a stale plan", "Both options", "Open runs at once"
      (patched opener) and an applied new batch, tidy and rename.
- [ ] 4.6 Implement the JSON envelope, structured errors with fixes and
      the exit-code mapping; verify with a test per exit code, "Not
      configured", and "Apply without a terminal" (stdin closed).
- [ ] 4.7 Document the CLI in `DEV.md` (install, commands, targets,
      preview and apply, JSON and exit codes) and tick the Phase 2 CLI
      item in `docs/core-split/ROADMAP.md`; verify the documented
      commands run as written against a temporary darkroom and both files
      are wrapped at 80 columns.

## 5. Integration

- [ ] 5.1 Run an end-to-end CLI session against a temporary darkroom,
      showroom and archive: set the three roots, create a batch, add
      files, inspect, tidy, publish, then archive with `--confirm`; verify
      every step exits 0 with the expected files on disk, and
      `uv run pre-commit run --all-files` passes.

## Workflow follow-up

- Archive the change after review (`/opsx:archive experimental-cli`).
