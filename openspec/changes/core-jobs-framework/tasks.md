# Tasks

## 1. Job object and slot (`core/jobs.py`)

- [x] 1.1 Replace `JobContext` and `NO_JOB` with a standalone
      `Job(name, description="", *, log_path=None)` holding progress, the
      cancel flag and its logger (design 1); verify with tests in
      `tests/core/test_jobs.py` that create `Job("tidy")` directly,
      cancel it and read its progress
- [x] 1.2 Make the slot create and run a `Job`, and derive the final
      state from how the work ended: return is `done`, `JobCancelled` is
      `cancelled`, an exception is `failed`; remove `state_of` and
      `_default_state` (design 4); verify with tests for each ending
- [x] 1.3 Let `JobCancelled` carry an optional result that the slot keeps
      as the job's result; verify a cancelled job's snapshot holds the
      partial result and a bare `JobCancelled` leaves it `None`
- [x] 1.4 Add `JobSlot.hold(name, description)` and make `start`,
      `require_idle` and `hold` refuse while a job is active or a hold is
      taken; give `JobBusyError` a label instead of a `JobView` (design
      3); verify a hold blocks a start and a second hold, leaves the
      slot's job unchanged, and is released after an exception
- [x] 1.5 Verify `jobs.py` still imports nothing from the project
      (`uv run lint-imports` and a grep for project imports)

## 2. Action types and heavy actions (`core/actions.py`)

- [x] 2.1 Split the base into `Action` with `execute(plan)` and
      `exclusive = False`, and `JobAction(Action)` with
      `execute(plan, *, policy, job)`, `policies` and `exclusive` always
      true; remove `runs_as_job`, `RunHooks`, `NO_HOOKS` and the hook
      arguments (design 2); verify with `uv run ty check`
- [x] 2.2 Set `exclusive = True` on rename and new batch and keep them as
      plain `Action`s; verify `tests/core/actions/test_new_batch_rename.py`
      passes with `execute(plan)`
- [x] 2.3 Make tidy, archive and publish `JobAction`s that report
      progress, pass `stop=lambda: job.cancelled` to `move_files`, log
      `step_done` / `step_skipped` / `step_failed` through `job.log`, and
      raise `JobCancelled(result)` when they stop for a cancel (design 4,
      5); verify with tests in `tests/core/actions/` that run each action
      with a `Job`, cancel it mid-run, and check the step lines in the
      job's log
- [x] 2.4 Remove the `action_prepare` / `action_execute` log lines and the
      "Internal error" wrappers from `Action.prepare` and `execute`
      (design 5, 6); verify an action whose prepare raises lets the error
      through
- [x] 2.5 Stop `execute` from checking the policy; the action only offers
      `check_policy` (design 7); verify `tests/core/actions/test_plans.py`
      covers `check_policy` for supported and unsupported policies
- [x] 2.6 Give archive results a `remaining` field for the files still in
      the batch folder after cleanup and keep `left` for files a cancel
      left undone (design 8); verify with tests in
      `tests/core/actions/test_archive.py` for a cancelled archive and an
      archive that leaves a file behind

## 3. Engine (`core/engine.py`)

- [x] 3.1 Dispatch on type: run a `JobAction` through the slot and any
      other action inline, wrapping an exclusive one in `hold`; remove
      `_run`'s hook lambdas, `_log_step`, `_action_state` and the
      `runs_as_job` checks; verify with `tests/core/test_engine_jobs.py`
      that rename starts no job and keeps the previous job readable
      (spec engine/jobs "Rename is not a job")
- [x] 3.2 Check the policy once, in `action_start`; verify an unsupported
      policy raises `PolicyNotSupportedError` before any job starts
- [x] 3.3 Log `action_request` and `action_result` once in `_apply`, to
      `job.log` for a job and to the module logger for an inline action;
      verify a rename's request and result reach the application log and
      a tidy's reach its job log exactly once
- [x] 3.4 Run the post-action rescan with the job's logger inside the job,
      and inside the hold for an exclusive inline action; verify the
      rescan's log lines appear in the archive's job log
- [x] 3.5 Verify the busy rules from spec engine/engine-status with tests
      in `tests/core/test_engine_jobs.py`: rename during an archive is
      refused naming the archive, a scan during a rename is refused, a
      folder opens during a rename
- [x] 3.6 Verify the job-state scenarios with tests in
      `tests/core/test_engine_jobs.py`: an archive failing on one file
      ends the job `done` with a `failed` result, a refused tidy ends
      `done` with `refused`, a scan raising an error ends `failed`

## 4. CLI (`cli/_app.py`, `cli/_render.py`)

- [x] 4.1 Remove the `runs_as_job` branch and dispatch through the engine
      for every apply; call `check_policy` only for a preview; verify
      `tests/cli/test_app.py` still gives exit 2 for
      `archive --on-conflict replace` at preview and at apply
- [x] 4.2 Render archive's `remaining` in text and JSON next to `left`;
      verify with tests in `tests/cli/test_app.py` for both outputs
- [x] 4.3 Verify `rename` and `new-batch` print no progress and leave no
      job log, and that a busy engine refuses them with exit 3
- [x] 4.4 Update the jobs section of `DEV.md`: rename and new batch run at
      once and log to the application log; a job with a failed file ends
      `done`; archive results include `remaining`; verify the text against
      a manual `uv run darkroom --json archive ... --apply` run in a temp
      darkroom inside the scratchpad

## 5. Docs

- [x] 5.1 Delete `docs/core-split/jobs-framework.md` and point Phase 4 of
      `docs/core-split/ROADMAP.md` at the specs (`engine/jobs`,
      `engine/engine-status`, `engine/action-requests`); verify no file
      links to the deleted doc (`grep -rn jobs-framework docs openspec`)

## 6. Integration

- [x] 6.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format
      --check .`, `uv run ty check`, `uv run lint-imports` and
      `openspec validate core-jobs-framework --strict`; all pass

## Workflow follow-up

- Archive the change with spec sync once the work is reviewed.
