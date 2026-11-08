# Proposal

## Why

The job slot from `core-jobs` was added after actions already existed, so
the engine now translates a job into hooks (`progress`, `stop`,
`on_step`) for the actions and maps their result back to a job state.
That layer duplicates work (the policy is checked three times, each run is
logged twice, internal errors are wrapped in three layers) and runs
rename and new batch as jobs although they are single, short steps.
This is Phase 4 of the roadmap, before the GUI is built on top.

## What Changes

- The job module becomes a framework that heavy actions are written
  against. A standalone `Job` object owns progress, the cancel flag and
  the job's logger; tests create one directly.
- Two action types, told apart by type:
  - `Action`: one shot (open, cull, edit, rename, new batch).
    `execute(plan)` never sees a job and takes no conflict policy.
  - `JobAction`: heavy, changes files (tidy, archive, publish).
    `execute(plan, *, policy, job)` takes a required `Job`; the engine
    runs it through the job slot.
- Each action talks to its job itself: it reports progress, writes its
  audit lines through `job.log`, and decides in its own loop where to
  check for a cancel. A file being moved is never interrupted.
- Exclusive actions, as a property of the action: `exclusive`, false by
  default, set by rename and new batch, always true for a `JobAction`. An
  exclusive action runs alone: a job holds the lock for its whole run, an
  exclusive one-shot action for its call. While it is taken, exclusive
  actions, scans and config edits are refused as busy; open, cull and
  edit always run.
- **BREAKING**: rename and new batch no longer run as jobs and write no
  job log; their step is logged to the application log.
- **BREAKING**: a job's state follows from the run alone (an exception
  means `failed`, a cancel means `cancelled`, otherwise `done`). An
  archive that fails on one file ends the job `done` with a `failed`
  result.
- The conflict policy is checked once, each run is logged once, and
  internal errors are wrapped in one place.
- Archive's `left` keeps one meaning: the files a cancel left behind.
- Removed: `RunHooks`, `NO_HOOKS`, `NO_JOB`, `JobContext`, `state_of`,
  `runs_as_job`, and the engine's translation of a job into hooks.

Not in scope: a shared step runner where actions return lists of steps
for one generic runner (rejected: it guesses what actions will become and
hides the same work behind another interface), the NAS speed fixes for
scans and moves, the GUI.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engine/jobs`: what runs as a job (only tidy, archive, publish and
  scans); the job state follows from the run alone; blocking calls cover
  the heavy actions only.
- `engine/engine-status`: the busy rule covers exclusive actions: rename
  and new batch are refused while a job runs, and while one of them runs,
  jobs and config edits are refused.
- `engine/action-requests`: applying an action runs it as a job only for
  heavy actions; rename and new batch are applied at once.

## Impact

- Code: `core/jobs.py` (the `Job` object, the slot running it, no
  `state_of` or `NO_JOB`), `core/actions.py` (the two action types, the
  `exclusive` property, each heavy action using its `Job`, rename and
  new batch without hooks), `core/engine.py` (the lock, dispatch by type,
  no hook translation, one policy check), `core/file_utils.py`
  (`move_files` callables wired by the action), `cli/_app.py` (no
  `runs_as_job` branch, one policy check).
- CLI: `rename` and `new-batch` print no job progress and leave no job
  log; JSON results of an archive with a failed file report the job as
  `done`. Commands, options and exit codes stay the same.
- Tests: `tests/core/test_jobs.py`, `tests/core/test_engine_jobs.py`,
  the action tests and `tests/cli/test_app.py` move to the new types.
- Docs: `DEV.md` (jobs section). `docs/core-split/jobs-framework.md`,
  the parked idea this change grew from, is removed once the change is
  in, with the roadmap pointing at the specs instead.
