# Tasks

## 1. Safe moves

- [x] 1.1 Rework `file_utils.move_files` to take a conflict policy, a
      progress hook and a cancel check, move one file at a time, and stop
      between files when cancelled; verify with tests in
      `tests/core/file_utils/` that a cancelled run reports done and left
      files
- [x] 1.2 Move across drives through a `.<name>.darkroom-partial` copy whose
      size is checked before it is put in place and the source removed;
      verify with tests that simulate a short copy and a failing copy
      (source kept, no partial file left, step failed with reason); copy
      data with `copyfile`, set timestamps as best effort (a refused
      `utime` logs a warning, the step succeeds), and retry the final
      rename briefly on a sharing violation; verify both with tests
- [x] 1.3 Replace with `os.replace` (same drive) or partial copy plus
      `os.replace` (across drives), never deleting the old target first;
      verify with a test where the replacing copy fails and the old target
      is unchanged
- [x] 1.4 Never overwrite a target without the replace policy: a target
      that exists at move time is reported as a conflict; verify with a
      test that creates the target between planning and moving
- [x] 1.5 Remove `cstm_shutil_move` and its directory-only helpers once
      `move_files` no longer calls it; verify nothing else imports them
      and `pytest tests/core` passes

## 2. Conflicts in plans and the conflict policy

- [x] 2.1 Add `Conflict` and `ActionPlan.conflicts`, include conflicts in
      the fingerprint and in `preview_text()` (counted, capped list,
      "replaced" wording for publish); verify with plan tests in
      `tests/core/actions/test_plans.py`
- [x] 2.2 Add `ConflictPolicy`, `Action.policies` and
      `ExecutionResult.skipped`, and the `cancelled` outcome; verify the
      policy sets per action with tests
- [x] 2.3 Tidy: plan duplicate-target and existing-target conflicts instead
      of refusing; execute under `refuse` and `skip`, re-checking targets;
      verify the `app/action-tidy` scenarios in `tests/core/actions/`
- [x] 2.4 Archive: plan existing archive files as conflicts; `skip` leaves
      them and keeps the batch folder; verify the `app/action-archive`
      scenarios, including a conflict appearing after the preview
- [x] 2.5 Publish: list existing showroom files as conflicts; `replace`
      and `skip` per `app/action-publish`, `refuse` by default; verify the
      replace, skip and no-choice scenarios
- [x] 2.6 Give `Action.execute` optional `progress`, `stop` and `on_step`
      hooks (plain callables; actions do not import `jobs`) and stop
      between steps with a `cancelled` result listing what was left;
      verify with hooks that stop after two moves
- [x] 2.7 Update the existing action, file-safety and batch-workflow tests
      that expected a `refused` prepare on conflicts, and verify the full
      `pytest tests/core` run passes

## 3. Job slot

- [x] 3.1 Create a standalone `core/jobs.py` (standard library and
      structlog only) with `JobState`, `Progress`, `JobView` (`name`,
      `description`), `JobContext` and `JobSlot` (lock, one worker thread,
      cancel flag, snapshot copies, state transitions); verify with
      `tests/core/test_jobs.py` using plain callables, no darkroom
- [x] 3.2 Test one job at a time (busy error names the running job), the
      next job replacing a finished one, snapshots not changing, `wait`
      with and without a timeout, and cancel before, during and after a
      run
- [x] 3.3 Map results to final states (`ok`/`noop`/`refused` → `done`,
      `cancelled` → `cancelled`, `failed` or an exception → `failed` with
      details); verify with tests

## 4. Engine on the job slot

- [x] 4.1 Replace `_begin` and `EngineBusy` with the slot:
      `EngineBusyError` carries the running job; `config_set` refuses while
      busy; verify the `engine/engine-status` busy scenarios in
      `tests/core/test_engine.py`
- [x] 4.2 Add `job`, `job_wait`, `job_cancel`, `library_scan_start`,
      `library_refresh_start` and `action_start(action, confirm=, policy=)`
      with policy checking (`PolicyNotSupportedError`); make
      `library_scan`, `library_refresh` and `action_apply` start-and-wait;
      remove `action_execute`; verify the `engine/jobs` scenarios in
      `tests/core/test_engine.py`
- [x] 4.3 Run open, cull and edit inline (`runs_as_job = False`), also
      while a job runs; verify with a test that opens a folder and
      launches edit during a running archive
- [x] 4.4 Make scans cancellable per folder and swap facts into the tree
      only after a complete scan; verify the `engine/scanning` "Cancelled
      scan keeps the library" scenario in `tests/core/library/`
- [x] 4.5 Rescan after an action inside the same job, also after a
      failed or cancelled action; verify the cancelled-archive scenario
- [x] 4.6 Guard tree reads and writes with an engine lock and do scan
      disk I/O outside it; verify with a test reading nodes while a scan
      job runs
- [x] 4.7 Update `test_action_requests.py`, `test_library_index.py` and
      the other engine tests to the new API, and verify `pytest tests/core`
      passes

## 5. Library revision and changes

- [x] 5.1 Add `library_revision` and `library_changes(since)` with a
      bounded change list, root on overflow or a dropped tree; verify the
      `engine/library-index` revision and change scenarios in
      `tests/core/test_library_index.py`

## 6. Job logs

- [x] 6.1 Give each job its own logger in the slot (a file handler on the
      job's log file, INFO whatever the app level) as `JobContext.log`,
      with `job_started`, `job_error` and `job_finished` written by the
      slot; verify in `tests/core/test_jobs.py` that a job's lines stay
      in its own file and are written as they happen
- [x] 6.2 Name job logs `{date}_{time}_{name}_{description}.log` under
      the slot's folder (`<logs>/jobs/`), with the description shortened
      and made safe and clash suffixes; verify names for the root, a
      batch, unsafe text, a long description and two jobs in one second
- [x] 6.3 Log `action_request`, `step_done`, `step_skipped`,
      `step_failed` and `action_result` from the engine through the job's
      logger, with the fields in design decision 8; verify a partial
      archive's log lists every moved and skipped file and the outcome,
      and that a log read mid-job already holds the finished steps
- [x] 6.4 Verify with a test that `cleanup_old_logs` keeps old files in
      `jobs/`

## 7. CLI

- [x] 7.1 Run `--apply` / `--confirm` through `action_start` and a wait
      loop; draw progress on stderr only when it is a TTY; verify in
      `tests/cli/test_app.py` that a JSON run writes one document and no
      progress
- [x] 7.2 Add `--on-conflict {skip,replace}` to tidy, archive and publish,
      carry it in the printed `--confirm` command, and map
      `PolicyNotSupportedError` to exit 2; verify the `app/command-line`
      conflict scenarios
- [x] 7.3 Show conflict counts and a capped list in text and JSON previews
      and results (skipped files included); verify with CLI tests
- [x] 7.4 Cancel the job on Ctrl+C, print its result and exit 130; verify
      with a test that raises `KeyboardInterrupt` during the wait
- [x] 7.5 Document jobs, `--on-conflict`, progress, Ctrl+C, exit 130 and
      the `jobs/` log folder in `DEV.md`, wrapped at 80 columns

## 8. Integration and roadmap

- [x] 8.1 Run a scripted end-to-end session with the real `darkroom`
      executable against fresh roots: archive with a conflict (refused,
      then `--on-conflict skip`), republish with `replace` and `skip`, and
      check the job logs, with the archive on a real second drive or
      network share; verify every step behaves as the specs say
- [x] 8.2 Verify `pytest`, `ruff`, `ty`, `lint-imports` and
      `pre-commit run --all-files` pass and `openspec validate core-jobs
      --strict` is clean
- [x] 8.3 Tick the Phase 3 items this change delivers in
      `docs/core-split/ROADMAP.md`, record the research summary and the
      decisions (no restart survival, no undo, one job slot, threads not
      asyncio), and update the next actionable step
