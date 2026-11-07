# Design

## Context

See proposal.md for why. The engine today runs every operation in the
caller's thread under one private busy guard (`Engine._begin`, kinds
`scan`, `action`, `config`), returning when the work is done. Actions are
already split into `prepare()` (a typed `ActionPlan` with a fingerprint)
and `execute(plan)` (an `ExecutionResult` with `done`, `failed`, `left`),
and the engine rescans the affected subtree after an action. File moves
go through `file_utils.move_files`, which falls back to `copy2` plus
`unlink` across drives without checking the copy, and publish deletes an
existing showroom file before moving the new one in. Logging is structlog
over stdlib handlers (`core/logging_config.py`): one key=value file per
process in the logs folder, 30-day cleanup. The only client is the CLI,
which runs once per command; the GUI is parked.

## Goals / Non-Goals

**Goals:**
- One place that says what the engine is doing, readable by any client at
  any time, the same for scans and file actions.
- A job runs off the caller's thread, can be cancelled between steps, and
  leaves a complete audit log.
- The executor has a narrow seam (progress, cancel, one move at a time) so
  another mover (for example rclone) can replace the Python one later.
- No asyncio: the API stays plain synchronous Python.

**Non-Goals:**
- Several jobs at once, a queue, or a job history in memory.
- Resuming or replaying a job after a restart; the job log is a record,
  not a journal to resume from.
- Checksum verification and byte-level progress (sizes only, files as
  units).
- Changing how previews are rendered beyond showing conflicts.

## Decisions

### 1. One job slot on the engine, run by a `JobSlot` component

The engine owns a private `JobSlot` (new module `core/jobs.py`) that holds
the current or last job, its worker thread, a lock, a cancel flag and the
job's log handler. The engine's public job API delegates to it:

- `engine.job -> JobView | None`: frozen snapshot of the slot.
- `engine.job_wait(timeout=None) -> JobView | None`: join the worker.
- `engine.job_cancel() -> None`: set the cancel flag; no-op when idle.
- Starters, domain-prefixed like the rest of the API:
  `library_scan_start(node_id="")`, `library_refresh_start(node_id)`,
  `action_start(action, *, confirm=None, policy="refuse")`, each returning
  the new `JobView` (state `new`) or raising `EngineBusyError(job)`.
- The blocking calls `library_scan`, `library_refresh` and
  `action_apply(action, confirm=None, policy="refuse")` become
  start-then-wait and keep their return types, so the CLI's `inspect`
  and the tests stay simple. `action_execute(action, plan)` is removed:
  executing a held plan is `action_start(action, confirm=plan.fingerprint)`.

`JobView` carries `id`, `kind` (`scan`, `refresh` or the `NodeAction`),
`node_id`, `state`, `progress: Progress(done, total | None, current |
None)`, `started_at`, `finished_at`, `log_path` and `result`
(`ExecutionResult` for actions, `ScanResult(node_id)` for scans and
refreshes). The slot keeps a mutable private record under its lock and
copies it into a new `JobView` on every read, so a snapshot never changes.

Alternatives considered:
- **Job table / registry with ids.** Rejected: one job at a time makes a
  table pure bookkeeping, and old entries would grow for the life of the
  process. The job log is the history.
- **A handle object returned to the caller.** Rejected: the engine is the
  one object every layer already has, so the slot is the handle; a second
  handle type would just mirror it.
- **Methods directly on `Engine` with no component.** Possible, but the
  thread, lock, cancel flag and log handler form one deep unit with its own
  invariants (one job, state transitions, snapshot copies); keeping them in
  `JobSlot` keeps `engine.py` about domain rules and lets the slot be
  tested without a darkroom.

### 2. One worker thread per job, no asyncio

Each job runs on a new non-daemon `threading.Thread`. A starter checks and
fills the slot under its lock (state `new`), starts the thread, and
returns; the thread sets `running`, runs the work, then sets the final
state. Non-daemon means the interpreter does not kill a job mid-file on
exit; the CLI waits anyway.

Alternatives considered:
- **asyncio API** (`await engine.action_start(...)`). Rejected with the
  user: file I/O blocks, so an async core would still run threads
  underneath, and every client including the CLI would need an event
  loop. Mixing sync and async in Python is the pain we avoid.
- **Thread pool / executor.** Rejected: one job at a time needs one
  thread; a pool adds lifecycle without benefit.
- **Client-owned threads with blocking calls.** Rejected: the core would
  not know what runs, and "jobs on their own plane" would be the client's
  job.

### 3. Progress and cancel through a `JobContext`

Work functions take a `JobContext` with `progress(done, total=None,
current=None)` and `cancelled: bool`. A no-op context is the default, so
actions and scans still run directly in tests. Cancelling is cooperative:

- Action execution checks `cancelled` before each step. A stop ends the
  step loop; the steps not run go to `left` and the outcome is
  `cancelled`. The rescan after the action still runs (files did move).
- Scans check `cancelled` per folder while building facts and raise a
  private `_Cancelled`; the engine swaps facts into the tree only after a
  scan completes, so a cancelled scan leaves the tree untouched.
- Prepare inside `action_start` (needed for the `confirm` check) runs on
  the worker too, with indeterminate progress.

The final state follows the result: `done` for `ok` and `noop` (and for a
`refused` plan under the `refuse` policy, which is a valid answer, not a
crash), `cancelled` for `cancelled`, `failed` for `failed`.

### 4. Which work is a job

`Action` gains `runs_as_job: ClassVar[bool]`, false for `OpenFolderAction`
and `OpenExternalAppAction` (cull, edit). For those, `action_apply` keeps
running prepare and execute inline, without the slot, so they work while a
job runs. Everything else goes through `action_start`. Scans and
refreshes always go through the slot. `config_set` checks the slot and
raises `EngineBusyError` when it is busy; the old `_begin` guard and the
`EngineBusy` literal go away.

### 5. Conflicts in the plan and a conflict policy

`ActionPlan` gains `conflicts: tuple[Conflict, ...]`, where
`Conflict(move: Move, reason: Literal["exists", "same_target"])`. Steps
hold only free moves; conflicting moves live only in `conflicts`. The
fingerprint covers steps and conflicts. `ActionResult` refusals for
conflicts at prepare go away for tidy, archive and publish.

`ConflictPolicy = Literal["refuse", "skip", "replace"]`, default
`refuse`. `Action.policies: ClassVar[frozenset[ConflictPolicy]]`: tidy and
archive `{refuse, skip}`, publish `{refuse, skip, replace}`, others
`{refuse}`. The engine checks the policy when starting and raises a typed
`PolicyNotSupportedError(action, policy, supported)`.

Execute re-checks every planned target just before running:
- `refuse`: any conflict (planned or new) refuses before the first move.
- `skip`: conflicts are dropped into `ExecutionResult.skipped`; a target
  that becomes occupied during the run is skipped the same way.
- `replace`: conflicting moves run with replace semantics (decision 6).

Publish's existing-file check moves from `Move(overwrite=True)` in steps to
`Conflict(reason="exists")`; the preview labels publish conflicts as
"replaced" and other actions' as "conflict". `Move.overwrite` stays for
the executor (set on the replace path), so the step data keeps its shape.
Rename and new batch keep refusing an existing target name: a single
folder step has nothing to run around.

### 6. Safe moves in `file_utils`

`move_files` becomes the one mover seam, called per file with the policy,
the progress hook and the cancel check:

- **Same drive:** `os.rename` for a free target (on Windows it fails if
  the target exists, which becomes a skip or refusal); on POSIX the
  target's absence is checked right before the rename. Replace uses
  `os.replace`, which is atomic on one drive.
- **Across drives:** copy with `copy2` to a temporary name in the target
  folder (`.<name>.darkroom-partial`), compare its size with the source,
  then move the temporary file into place (`os.rename` for a free target,
  `os.replace` for replace) and only then unlink the source. Any failure
  removes the temporary file and leaves the source; the step is reported
  failed with the reason.
- Network shares (SMB, NFS): the data is copied with `copyfile` and the
  timestamps set afterwards as best effort, so a share that refuses
  `utime` (CIFS mounts owned by another user) logs a warning instead of
  failing a step whose data copied fine. The rename into place is retried
  a few times with a short pause, because an antivirus scan or a NAS
  indexer can hold the new file open for a moment on Windows.
- `cstm_shutil_move` and its directory branch (`copytree`, read-only
  `rmtree`) lose their only caller and are removed; folder renames keep
  `os.rename`.

Alternatives considered:
- **Checksum after copy.** Rejected for now: it doubles the reads of large
  videos; size plus `copy2` raising on I/O errors covers truncated copies.
  The seam allows adding a hash later.
- **Backup of replaced files** (like `rclone --backup-dir`). Rejected by
  the user: no backups; replace is an explicit choice.

### 7. Library revision and change list

The engine keeps `library_revision: int` and a bounded deque of
`(revision, node_id)` entries (64 kept), appended whenever a subtree is
loaded or replaced, and `""` when the tree is dropped or rebuilt.
`library_changes(since) -> tuple[NodeId, ...]` returns the ids changed
after `since`, with ids under another returned id removed, or `("",)` when
`since` is older than the oldest kept entry. A finished job's result
already names its rescanned id (`library_refreshed` / `ScanResult`).

The tree is now read by clients while a worker writes it. The engine gets
a lock around tree reads (`library_node` building a view) and writes
(`replace_subtree`, `load_subtree`, the revision bump); scans read disk
outside the lock and only swap facts in under it.

Alternatives considered: a push callback for changes. Deferred: with the
slot, a client polls `engine.job` and `library_revision`; a callback can be
added later without changing these.

### 8. Job logs through structlog

The worker binds `job_id` with `structlog.contextvars` for its whole run
(contextvars are per thread, so this tags only that job's records), and
`merge_contextvars` is added to the structlog chain. `logging_config`
gains a context manager that attaches, for one job, a `FileHandler` to
`<logs>/jobs/<name>.log` with a filter passing only records whose
`job_id` matches, using the same key=value renderer as the main log.

Audit events go to a dedicated logger `photo_darkroom_manager.jobs` set to
INFO, so they are always written whatever the engine log level; they also
reach the main log under its own level. Events: `job_started` (kind, node,
params, policy, summary, notes, step and conflict counts), `step_done`,
`step_skipped`, `step_failed` (source, target, reason), `job_finished`
(state, outcome, message, counts, left files, refreshed id, duration). Each
is written as it happens; the handler flushes per record.

File name: `{YYYY-MM-DD}_{HHMMSS}_{kind}_{node}.log`, the node id with `/`
replaced by `~` and characters invalid on Windows replaced by `_`, `root`
for the root, and `_2`, `_3`, … appended on a clash. `cleanup_old_logs`
only touches files directly in the logs folder, so `jobs/` is kept; a test
pins that.

Alternative considered: custom JSON-lines writer. Rejected with the user:
stay on the project's structured logging.

### 9. CLI

- `--apply` / `--confirm` call `action_start(...)`, then loop on
  `job_wait(timeout=0.2)`, drawing progress on stderr only when stderr is a
  TTY (a counter with the current file, or a spinner without a total).
- `KeyboardInterrupt` during the wait calls `job_cancel()`, waits for the
  job, renders its result, and exits 130.
- `--on-conflict {skip,replace}` maps to the policy;
  `PolicyNotSupportedError` is a usage error (exit 2). A plan's `confirm`
  argv carries the option the user gave.
- A preview stays synchronous in the CLI (`action.prepare()`), and prints
  conflict counts and a capped list. A `refused` result for conflicts
  exits 3, as now.
- `inspect` uses the blocking `library_scan`; its spinner follows the same
  TTY rule.

## Risks / Trade-offs

- [The tree is shared across threads] → One engine lock around tree reads
  and writes; scans do disk I/O outside it; tests read while a scan runs.
- [POSIX `rename` overwrites silently, leaving a check-then-rename race] →
  The window is tiny and the darkroom has one writer; the result reports
  what happened. `os.link` + `unlink` is not portable (exFAT cards).
- [Size-only verification misses same-size corruption] → Accepted for
  now; `copy2` raises on I/O errors; hashing can be added in the mover.
- [Threads make tests flaky] → Tests use the blocking calls or
  `job_wait()`; the no-op `JobContext` lets action and scan tests run
  without threads; cancel tests use a context that cancels after N steps.
- [Non-daemon worker delays process exit] → Jobs are minutes at most; the
  CLI cancels on Ctrl+C. A GUI can cancel on quit.
- [Breaking engine API and publish behaviour] → No persisted state and
  only internal callers; the CLI and tests move in the same change.
  Publishing over existing files now needs `--on-conflict replace`.
- [Temporary `.darkroom-partial` files after a crash] → Named clearly,
  never counted as media; the next move of the same file replaces it.
- [NFSv3 rename reply lost, retry reports "not found"] → The step is
  reported failed although the file moved; the source is kept, so the
  worst case is a duplicate, never a loss.
- [Faked second drive in tests] → The cross-drive path is the main path
  for a NAS archive or showroom; the end-to-end check also runs against a
  real second drive or network share.

## Migration Plan

No data migration. Callers of `action_execute` move to `action_start` or
`action_apply`; callers expecting a `refused` prepare for conflicts read
`plan.conflicts`. `DEV.md` documents `--on-conflict`, progress and Ctrl+C.

## Open Questions

- Should a `.darkroom-partial` left by a crash be cleaned up by tidy or a
  scan? It can wait: it is harmless and visible.
