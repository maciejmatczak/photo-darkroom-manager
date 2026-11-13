# Tasks

The new modules are built next to the old `core/actions/_actions.py`
(groups 1–5). The new engine calls take the names of today's
`action_<name>` factories, so the engine and the CLI switch over together
in group 6; group 7 removes the old module.

## 1. The foundation (`core/actions/_base.py`)

- [x] 1.1 Add `ActionResult` (outcome `ok` | `failed` | `cancelled`,
      message), `Question`, `Answers`, `ActionPlan` (questions,
      fingerprint, abstract `nothing_to_do`), `ActionRefusedError` and the
      `fingerprint(*parts)` helper (design 2); verify with tests in
      `tests/core/actions/test_base.py` that equal parts give equal
      fingerprints and any changed part a different one
- [x] 1.2 Add `require_unchanged_plan(plan, fresh_plan)`, raising
      `ActionRefusedError` naming both fingerprints when they differ
      (design 2; spec engine/planned-actions "Executing a plan"); verify in
      `test_base.py` for a changed and an unchanged plan
- [x] 1.3 Add `check_answers(questions, answers)`: known question, offered
      choice, default when unanswered, `ActionRefusedError` naming the
      question otherwise (design 2; spec engine/planned-actions "Answers
      are checked before running"); verify each rule in `test_base.py`

## 2. The shared move helper (`core/actions/_moves.py`)

- [x] 2.1 Move the planned-move runner out of `_actions.py` into
      `_moves.py`, taking the user's answer (skip or replace) instead of a
      policy and returning a `MoveReport` (moved, replaced, failed with
      reasons, skipped, left by a cancel; archive adds what remains in its
      own result) (design 3; spec app/file-moves "Moves are reported");
      verify with tests in `tests/core/actions/test_moves.py` for a full
      run, a failed file, a skipped file, a replaced file and a cancel
      between files
- [x] 2.2 Moves are plain `FileMove` data from `_moves.py`, not steps; the
      old step types (`Move`, `MakeDir`, `Rename`, `OpenFolder`, `Launch`)
      go with `_actions.py` in group 7; verify then that
      `grep -rnwE "Move|MakeDir|OpenFolder|Launch" src` finds only the
      verb in docstrings

## 3. Planned actions, one module each

Each module has its plan and result types and its `prepare` and `run`
functions, called as `archive.prepare` and `archive.run` (design 3). Its
plan carries the inputs to prepare it again and the work its run does.
It raises `ActionRefusedError` where it refused before, and returns a
plan that says so where it returned `noop` before. Library checks two or
more actions share live in `_library.py`; `test_roots.py` covers each
action refusing a missing root.

- [x] 3.1 Tidy in `core/actions/tidy.py`: `TidyPlan` (folder, files to
      move with their targets, conflicts), `TidyResult` (`MoveReport`) and
      a question for conflicts (spec app/action-tidy); verify
      `tests/core/actions/test_tidy.py`, rewritten for the new functions,
      covers loose files, the sibling folder, nothing to tidy, conflicts
      refused without an answer and skipped with one
- [x] 3.2 Archive in `core/actions/archive.py`: `ArchivePlan` (source,
      target, roots, moves, conflicts), `ArchiveResult` (`MoveReport`,
      what remains, whether the source was removed, why a folder was
      kept) and its question for files already archived (spec
      app/action-archive); verify `tests/core/actions/test_archive.py`
      covers the mapped location, files added after the preview, skip, a
      cancel, a whole batch removed and a folder held open
- [x] 3.3 Publish in `core/actions/publish.py`: `PublishPlan` (source,
      showroom folder, files, files to replace), `PublishResult`
      (`MoveReport`), its replace-or-skip question and the refusals for a
      missing or nested `PUBLISH/` (spec app/action-publish); verify
      `tests/core/actions/test_publish.py` covers replace, skip, no
      answer, empty and missing `PUBLISH/`
- [x] 3.4 Rename in `core/actions/rename.py`: `RenamePlan` (old folder,
      the inputs, new folder) and `RenameResult` (new folder); it asks no
      questions, ignores cancel and reports no progress (spec
      app/action-rename-batch); verify `tests/core/actions/test_rename.py`
      covers kept parts, a taken name, an invalid month and a name taken
      after the check
- [x] 3.5 New batch in `core/actions/new_batch.py`: `NewBatchPlan` (the
      inputs, folders to create) and `NewBatchResult` (created batch), the
      same way (spec app/action-new-batch); verify
      `tests/core/actions/test_new_batch.py` covers a taken name, an
      invalid month, a new device, a file in the way and a symlink
      escape
- [x] 3.6 Verify for each planned action that preparing twice with no
      disk change gives the same fingerprint and adding a file changes it
      (spec engine/planned-actions "Plans carry a fingerprint"), with one
      test per module

## 4. Direct actions (`core/actions/apps.py`)

- [x] 4.1 Add `OpenFolderResult`, `ExternalAppResult`, `open_folder` and
      `open_external_app`: an `ok` result when opened or started, a
      `failed` one when the app cannot start or exits at once with an
      error, `ActionRefusedError` for a bad command, an unknown
      placeholder or no first image; the command resolution (`{folder}`,
      `{first_image_in_folder}`) stays private (design 4; specs
      app/action-open-folder, app/action-open-ext-app); verify with
      `tests/core/actions/test_apps.py`, merging `test_open.py` and
      `test_open_external.py`, for opening, both placeholders, no image,
      bad quoting and an app exiting with an error

## 5. CLI renderers (`cli/_render.py`)

- [x] 5.1 Add a text and a JSON renderer per plan type and per result
      type, found by type, with the JSON shapes of design 9; verify with
      tests in `tests/cli/test_render.py` on built values, including one
      that every plan and result type exported by `core.actions` has both
      renderers

## 6. Switch the engine and the CLI (`core/engine.py`, `cli/_app.py`)

- [x] 6.1 Add `action_prepare_rename`, `action_prepare_new_batch`,
      `action_prepare_tidy`, `action_prepare_archive` and
      `action_prepare_publish`, each running the node-kind guard and
      returning its action's plan type (design 1; spec engine/actions);
      verify with tests in `tests/core/test_engine_actions.py` (renamed
      from `test_action_requests.py`) for an id without a scan, a missing
      folder, a year refused for archive and a new device
- [x] 6.2 Add the private `_execute_planned_action` (the two checks,
      start the job, run the action, then its callback, whose return is the
      job's result, and the log lines), `NodeActionResult`, one
      `_after_<name>_run` callback per planned action and
      `_node_id_for_folder`, and rename `_target` to
      `_resolve_action_target` (design 5, 6)
- [x] 6.3 Replace the `action_<name>` factories, `action_apply` and
      `action_start` with the direct calls (`action_open`, `action_cull`,
      `action_edit`) and the execute calls (`action_rename`,
      `action_new_batch`, `action_tidy`, `action_archive`,
      `action_publish`), and move the CLI's runner to them: its command
      table maps each command to its calls, the preview goes through the
      prepare call, flags map to answers, a plan with nothing to do is not
      executed and prints no `--confirm` command, and `ActionRefusedError`
      exits 3 (design 1, 4, 5, 9); verify with tests in
      `test_engine_actions.py` that a stale plan and a bad answer are
      refused with no job started and no file moved, a rename names the
      new node, an archive that removed the batch names none, the action's
      result is what its run returned, a missing cull command is refused
      naming the key; and that the existing `tests/cli/test_app.py` tests
      for apply, confirm, a stale confirm, skip, replace, a republish
      without a choice, Ctrl+C and the exit codes pass, with new ones for
      nothing to tidy exiting 0 and a taken rename name exiting 3
- [x] 6.4 Remove `JobSlot.hold`, `_held` and `exclusive` (design 7);
      verify with tests in `tests/core/test_engine_jobs.py` that a rename
      runs as a job with a job log, a rename during an archive is refused
      naming the archive, a scan during a rename is refused, and opening
      during an archive works and starts no job

## 7. Remove the old actions module

- [x] 7.1 Delete `core/actions/_actions.py` and `tests/core/actions/
      test_plans.py`, export the foundation and each action's types and
      functions from `core/actions/__init__.py`, drop the generic
      `execute` helper from `tests/conftest.py` and the "predates these
      rules" note from `core/actions/README.md`; verify `uv run pytest`
      passes and `grep -rnE` over `src tests` for `ExecutionResult`,
      `ConflictPolicy`, `RunHooks`, `rescan_node_path`, `noop`,
      `action_apply` and `action_start` finds nothing

## 8. Docs

- [x] 8.1 Update the JSON section of `DEV.md` to the design 9 shapes,
      checked against a `--json archive ... --apply` run in a temp
      darkroom inside the scratchpad with logs kept there
- [x] 8.2 Update the jobs section of `DEV.md`: rename and new batch run as
      jobs, show progress and write a job log; verify the text against a
      `rename ... --apply` run in the same temp darkroom
- [x] 8.3 Point Phase 4 of `docs/core-split/ROADMAP.md` at
      `core-actions-as-forms` and the new specs (`engine/actions`,
      `engine/planned-actions`); verify no doc mentions `action_apply`,
      `action_start` or `engine/action-requests` (`grep -rn` over
      `docs DEV.md src`)

## 9. Integration

- [x] 9.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format
      --check .`, `uv run ty check`, `uv run lint-imports` and
      `openspec validate core-actions-as-forms --strict`; all pass

## Workflow follow-up

- Archive the change with spec sync once the work is reviewed; the
  archive retires `engine/action-requests`, `app/action-create-batch`
  and `app/action-open`.
