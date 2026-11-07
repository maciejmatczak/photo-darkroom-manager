# Design idea: jobs as a framework for actions

Status: parked, not a design. Nothing here is decided until it becomes an
OpenSpec change. It follows the `core-jobs` change and would replace parts
of it.

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
  - `Action`: one shot, changes no files (open, cull, edit). Its
    `execute(plan)` never sees a job and takes no conflict policy. It runs
    at once, also while a job runs.
  - `JobAction`: changes files (tidy, archive, publish, rename, new batch).
    Its `execute(plan, *, policy, job)` takes a required `Job`. The engine
    runs it through the job slot. The `runs_as_job` flag goes away.
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

## What would change in behaviour

- The `engine/jobs` scenario "an archive that fails on a file ends the job
  `failed`" would become "ends `done`, with a `failed` result".

## Open questions

- Do rename and new batch need anything from the job beyond logging their
  steps, or are they jobs only to stay in the audit trail?
- Should scans be written on the same framework (folders as steps without
  a known total), or stay engine work run by the slot?
