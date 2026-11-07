# Proposal

## Why

Work that changes files or reads the whole library runs inside the
caller's call today: the client is blocked until it returns, nothing shows
what is running or how far it got, and nothing can stop it. A conflict
refuses the whole action even when the user would gladly move everything
else, and the only record of what moved is the general debug log. Phase 3
of the redesign makes running work a first-class part of the engine and
makes file operations trustworthy: previewed as a summary of intent, run in
the background, cancellable, and recorded completely.

## What Changes

- **Jobs.** The engine holds one job slot. Starting a job returns at once;
  the engine runs it on a worker thread it owns. Any client reads the
  slot to see the job's kind, node, state (`new`, `running`, `cancelling`,
  `done`, `failed`, `cancelled`), optional progress, result and log file,
  and can cancel it or wait for it. Only one job runs at a time; starting
  another replaces the finished one. There is no job table and no
  history in memory. The API stays synchronous Python: no asyncio.
- **What runs as a job.** Every action that changes files (tidy, archive,
  publish, rename, new batch), and every library scan and refresh. Open,
  cull and edit change no files and run at once, also while a job runs.
- **BREAKING (engine API).** `library_scan`, `library_refresh` and
  `action_apply` run their work as a job and wait for it, so they are
  refused while another job runs; `action_execute` goes away in favour of
  starting a job. The private busy kinds `scan` / `action` become the job
  slot; config edits stay refused while a job runs.
- **Cancel.** A running job stops between steps (between files, or between
  folders for a scan). A cancelled action reports what it did and what it
  left; a cancelled scan keeps the library as it was before the scan.
- **Change notice.** The library carries a revision that grows with every
  change to the tree. A client asks which nodes changed since the revision
  it last read; a finished job also names the node it rescanned.
- **Conflicts in the plan.** Preparing tidy, archive or publish no longer
  refuses on conflicts: the plan lists them next to the free steps, and
  its summary counts them. Applying takes a conflict policy: `refuse`
  (the default: refuse while any conflict is left), `skip` (move the free
  files, leave the conflicting ones and report them) and, for publish
  only, `replace`. Renaming a batch or creating one onto an existing name
  stays an error.
- **BREAKING (publish).** Publishing no longer replaces showroom files
  silently: files already there are listed as replacements, and the user
  picks `replace` or `skip`.
- **Safe moves.** A file moved to another drive is deleted from its source
  only after its copy has the source's size. Replacing a file never deletes
  the old one before the new one is in place.
- **Job log.** Every job writes its own log file under `<logs>/jobs/`,
  named by its start time, kind and node, through the project's structlog
  setup: the request, the summary of intent, the policy, every step with
  its result, the skipped and failed files and the outcome. Job logs are
  an audit trail and are not removed by the 30-day log cleanup.
- **CLI.** Commands stay stateless: an apply starts the job, prints
  progress on stderr, waits and exits. `--on-conflict skip|replace`
  chooses the policy; Ctrl+C cancels the job and still prints its report.

Out of scope: jobs surviving an app restart, undo or rollback, backup
copies, rclone or other external movers, more than one job at a time, a
job history, and the GUI.

## Capabilities

### New Capabilities
- `engine/jobs`: the job slot: starting, reading, waiting for and
  cancelling the one job the engine runs, its states and progress, and
  which work runs as a job.
- `app/job-log`: the audit log file every job leaves on disk.
- `app/file-moves`: what moving or replacing a user's file guarantees on
  disk, whatever action does it.
- `app/action-tidy`: tidying a batch or subfolder, including its conflicts.

### Modified Capabilities
- `engine/engine-status`: the busy rule now follows the job slot and lets
  open, cull and edit run during a job.
- `engine/action-requests`: plans list conflicts, applying takes a
  conflict policy and runs as a job, a cancelled outcome is added, and a
  conflict no longer refuses at prepare.
- `engine/scanning`: scans and refreshes run as jobs; a cancelled scan
  leaves the library as it was.
- `engine/library-index`: scan state comes from the job slot; the library
  revision and the changes since a revision are added.
- `app/action-archive`: conflicting files can be left in the darkroom while
  the rest is archived.
- `app/action-publish`: files already in the showroom are replaced or
  skipped by choice, never silently.
- `app/command-line`: progress, `--on-conflict`, cancelling with Ctrl+C and
  its exit code.

## Impact

- Code: `core/engine.py` (job slot, worker, guards, revision),
  a new `core/jobs.py` (job state, snapshot, progress, cancel token),
  `core/actions.py` (conflicts in plans, policies, progress and cancel
  hooks in execution), `core/file_utils.py` (verified cross-drive moves,
  safe replace), `core/library/` (cancellable scan, revision and change
  list), `core/logging_config.py` (per-job log files), `cli/_app.py` and
  `cli/_render.py` (progress, policy option, Ctrl+C).
- Tests: new `tests/core/test_jobs.py`; action, file-utils, engine, scan
  and CLI tests updated for conflicts in plans, jobs and policies.
- No new dependencies. The parked GUI is not touched.
