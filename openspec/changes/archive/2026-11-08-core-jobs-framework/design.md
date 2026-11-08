# Design

## Context

Today (see proposal.md, Why):

- `core/jobs.py` has a `JobSlot` that runs a work function on a worker
  thread and hands it a `JobContext`; work outside a job gets `NO_JOB`.
  `start(work, *, name, description, state_of)` maps the work's return
  value to a final state through `state_of`.
- `core/actions.py` has one `Action` base for all eight actions, with a
  `runs_as_job` flag and `policies`. `execute(plan, *, policy, progress,
  stop, on_step)` packs the three callables into `RunHooks`. Tidy, archive
  and publish run their moves through `_run_planned_moves`, which calls
  `file_utils.move_files(stop=, on_move=)`.
- `core/engine.py` builds the hooks from the `JobContext` (`_run`), logs
  each step (`_log_step`), maps results to states (`_action_state`), and
  decides inline or job by `runs_as_job`.
- `Action.prepare` and `Action.execute` turn any exception into an
  "Internal error" result; the slot also catches exceptions; the CLI
  builds a third "Internal error" result from a failed job's view.
- The policy is checked by the CLI, by `action_start` and by `execute`.
- Archive returns `left` as the files still on disk after cleanup, while
  its message and outcome use the moves a cancel left undone.

The specs of this change state the required behaviour; this document
covers how.

## Goals / Non-Goals

**Goals:**

- Heavy actions are written against a `Job` they receive; nothing
  translates between the job and the action.
- `jobs.py` stays standalone: no word of actions, the library or the
  darkroom.
- Each concern lives in one place: the policy check, the request and
  result log lines, the internal-error handling.

**Non-Goals:**

- No shared step runner and no shared base for the move actions' loops;
  each action keeps its own logic. Shared code stays plain helpers an
  action chooses to call (`move_file`, `move_files`, conflict helpers).
- No change to the engine's blocking scan and refresh calls, the change
  notice, the job log format or the CLI's commands and exit codes.

## Decisions

### 1. `Job` replaces `JobContext` and `NO_JOB`

`Job(name, description="", *, log_path=None)` is a plain object with
`progress(done, total=None, current=None)`, `cancelled`, `cancel()` and
`log`. With a `log_path` its logger writes the job's log file; without
one it writes only to the module logger. The slot creates the `Job`,
runs the work with it and reads its progress for snapshots. Tests create
`Job("tidy")` directly and call `job.cancel()` to test stopping.

*Alternative:* keep `JobContext` as the protocol and `NO_JOB` as the null
object. Rejected: a heavy action always runs with a real job, so a null
object only hides a missing argument.

### 2. Two action types; `exclusive` as a property

- `Action` (base): `prepare()`, `execute(plan)`. `exclusive:
  ClassVar[bool] = False`. Open, cull and edit keep the default; rename
  and new batch set it to true.
- `JobAction(Action)`: `execute(plan, *, policy, job)` with a required
  `Job`; `policies` lives here, since only heavy actions take a policy.
  `exclusive` is always true.

The engine dispatches on `isinstance(action, JobAction)`: a `JobAction`
goes through the slot, any other action runs inline. `runs_as_job`,
`RunHooks`, `NO_HOOKS` and the `progress`, `stop` and `on_step`
arguments go away.

*Alternative:* a third type for rename and new batch. Rejected: whether
an action runs alone is a property, not a kind of action.

### 3. One lock in the slot, held by a job or by an exclusive call

`JobSlot` gets `hold(name, description)`, a context manager that marks
the slot busy for the duration of a call without starting a thread or
replacing the slot's job. `start`, `require_idle` and `hold` all refuse
while a job is active or a hold is taken. The engine wraps an exclusive
inline action in `hold`; scans and config edits keep using `start` and
`require_idle`, so they see the hold too.

`JobBusyError` carries a label of what is running (`str(view)` for a job,
`name description` for a hold) instead of a `JobView`, so a hold can
name itself without becoming a job.

*Alternative:* a separate engine lock next to the slot. Rejected: two
locks would have to be checked together everywhere the busy rule
applies.

### 4. Cancelling: the action decides, `JobCancelled` carries the result

A heavy action checks `job.cancelled` in its own loop, where it can stop
safely; for moves it passes `stop=lambda: job.cancelled` to `move_files`,
which checks between files. When it stops for a cancel it raises
`JobCancelled(result)` with its partial result (done and left). The slot
ends the job `cancelled` and keeps that result. Scans already raise
`JobCancelled` with no result.

The final state follows from how the work ended: an exception is
`failed`, `JobCancelled` is `cancelled`, a return is `done`. `state_of`,
`_default_state` and `_action_state` go away.

*Alternative:* `cancelled` whenever a cancel was asked and the work
returned. Rejected: a cancel asked after the last file would mark a
complete run `cancelled`.

### 5. The action logs its steps through `job.log`

Tidy, archive and publish write `step_done`, `step_skipped` and
`step_failed` themselves, from `move_files`' `on_move` callback. The
engine logs the request (`action_request`) and the result
(`action_result`) once, in `_apply`: to `job.log` for a job, to the
module logger for an inline action, so rename and new batch land in the
application log. `Action.prepare` and `Action.execute` no longer log
`action_prepare` and `action_execute`.

### 6. Internal errors: the slot for jobs, the caller for inline calls

`Action.prepare` and `Action.execute` stop catching exceptions. In a job
an exception reaches the slot, which ends the job `failed` with the
error text; the CLI keeps its one translation of a failed job into an
"Internal error" result. An inline action's exception reaches the
caller, which the CLI already handles at its top level.

### 7. The policy is checked once per path

`check_policy` stays on the action. The engine calls it when applying
(`action_start`); `execute` trusts its caller. The CLI calls it only for
a preview, which never reaches the engine's apply, so a bad
`--on-conflict` is a usage error before a `--confirm` command is printed.

### 8. Archive: `left` and `remaining`

`left` is only the files a cancel left undone. The files still in the
batch folder after cleanup go to a new `remaining` field, which keeps the
"N file(s) left in the darkroom" message and the CLI's output. The
rendering in `cli/_render.py` reads `remaining` for that line.

### 9. Removing the parked doc

`docs/core-split/jobs-framework.md` is deleted once the specs and code
of this change are in; the roadmap's Phase 4 points at the specs
(`engine/jobs`, `engine/engine-status`, `engine/action-requests`).

## Risks / Trade-offs

- [Each heavy action repeats a little wiring (progress, stop, step log)]
  → Accepted by decision; three actions, each readable on its own. A
  helper for the `on_move` log line is fine if it stays a plain function.
- [Internal errors in inline actions now raise instead of returning a
  result] → The CLI already maps unexpected exceptions at its top level;
  the GUI (Phase 6) has to do the same.
- [`JobCancelled` now carries a value] → The slot treats a missing
  result as `None`; scans keep raising it bare.
- [JSON results change: an archive with a failed file reports the job
  `done`, archive results gain `remaining`] → The CLI's JSON is
  experimental; `DEV.md` is updated.

## Migration Plan

One change on `dev-core-split`; no data or settings migrate. Job logs
already on disk stay readable. Rollback is reverting the change.
