# Design idea: jobs as a framework for actions

Status: parked, not a design; planned as Phase 4 of the
[roadmap](ROADMAP.md). Nothing here is decided until it becomes an
OpenSpec change. It follows the `core-jobs` change and would replace parts
of it. Checked against a simplification review on 2026-11-08.

## Intent

On a given input, run an action's work and follow its progress. Today the
pieces for that grew in layers: the job slot runs "some work function", the
engine translates the job into hooks (`progress`, `stop`, `on_step`) for the
actions, `move_files` has its own loop and callbacks, and `state_of` maps an
action's result back to a job state. Designed from scratch, the job module
would be a small framework that actions that change files are written
against, with one clear contract.

## The idea

- **The job module is a framework, actions build on it.** The dependency
  points one way: actions depend on the generic job module, which knows
  nothing of actions, the library or the darkroom.
- **Two kinds of actions, told apart by type.**
  - `Action`: one shot (open, cull, edit, rename, new batch). Its
    `execute(plan)` never sees a job and takes no conflict policy. It has
    a `locks_engine` property, false by default; rename and new batch set
    it to true because they change files.
  - `JobAction`: heavy, changes files (tidy, archive, publish). Its
    `execute(plan, *, policy, job)` takes a required `Job`. The engine
    runs it through the job slot. `locks_engine` is always true. The
    `runs_as_job` flag goes away.
- **`Job` is a standalone object** that owns its state: progress, the
  cancel flag and its logger. It writes to a log file only when given a
  path. The slot creates a `Job`, runs it on the worker thread and keeps
  it; clients read snapshots of it. Tests create one directly
  (`Job(name="tidy")`), call `job.cancel()` to test stopping and read its
  progress afterwards, so no fake "no job" object is needed.
- **The action talks to its job itself:** `job.progress(done, total,
  current)`, `job.cancelled`, and `job.log` for its audit lines
  (`step_done`, `step_skipped`, `step_failed`). File helpers such as
  `move_files` keep plain callables; the action wires the job into them.
  Only the action knows its own loop, so it alone decides where to check
  `job.cancelled` (for example between files); a file being moved is never
  interrupted.
- **The engine lock.** A job holds the lock for its whole run; an action
  with `locks_engine` holds it for its call. While the lock is taken,
  locking actions, scans and config edits are refused as busy; open, cull
  and edit always run.
- **The job state follows from the run alone:** an exception means
  `failed`, a cancel asked means `cancelled`, otherwise `done`. Whether a
  file move failed is in the action's result, not in the job state.

## What would go away

- `RunHooks` and the `progress`, `stop` and `on_step` arguments of
  `Action.execute`.
- The engine's translation layer: `_log_step` and the progress and cancel
  lambdas.
- `NO_JOB`, `JobContext` and `state_of`.
- `runs_as_job`.
- The conflict policy checked in three places (CLI, engine, `execute`):
  it is checked once.
- Each run logged by both the action and the engine: it is logged once,
  through `job.log`.
- "Internal error" results built in three layers (action, job slot, CLI):
  built in one.

## What would change in behaviour

- The `engine/jobs` scenario "an archive that fails on a file ends the job
  `failed`" would become "ends `done`, with a `failed` result".
- Rename and new batch no longer run as jobs and write no job log; their
  single step goes to the application log. This changes the `engine/jobs`
  spec and Phase 3's rule that every action that changes files runs as a
  job.
- Archive's `left` has one meaning: the files a cancel left behind. Today
  it is overwritten with the files still on disk after cleanup.

## Rejected alternative

A shared step runner: actions return a list of steps (move, make folder,
rename) with a conflict decision per step, and one generic runner applies
them with progress, cancel and logging. Rejected because it guesses what
actions will become, and new actions would keep needing new step types; it
hides the same work behind a different interface. Each action keeps its
own logic, so reading the action shows what it does.

## Open questions

- Should scans be written on the same framework (folders as steps without
  a known total), or stay engine work run by the slot? Either way they
  take the engine lock.
