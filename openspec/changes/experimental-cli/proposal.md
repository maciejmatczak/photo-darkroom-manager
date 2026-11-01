# Proposal

## Why

Phase 2 of the `dev-core-split` roadmap needs a client of its own: an
experimental CLI that drives the core end to end (configure, scan, inspect
a node, run an action) and that an agent can use as a tool surface. The
GUI is parked, so today nothing exercises the core API. The core also
cannot serve a one-shot, scriptable client safely yet:

- Actions are addressed by raw path and not checked against the node kind;
  tidy runs on any folder.
- Rename, new batch and the external apps prepare no plan, so a preview
  shows nothing.
- Archive moves whatever is in the folder at execute, not what was
  previewed.
- Results are prose with a boolean, and reading any node needs a full
  library scan.

## What Changes

- **New CLI** `darkroom`, with the short alias `dr`, in `cli/` (the name
  avoids the PDM package manager's `pdm`):
  - Flat top-level commands: `status`, `config list | get | set`,
    `inspect`, and one command per node action: `open`, `tidy`, `cull`,
    `edit`, `rename`, `publish`, `archive`, `new-batch`.
  - Every target is a node id or a path in the darkroom, so it works from
    a shell inside the library.
  - Commands that change files show a preview with the plan's
    fingerprint and change nothing. `--apply` runs the action as it is
    now; `--confirm FINGERPRINT` runs it only when the plan is still the
    one shown.
  - Output is readable text, or JSON with `--json`. Data goes to stdout
    and logs to stderr; the CLI never prompts. Exit codes follow the
    outcome.
- **Node-addressed, guarded action requests** in the engine. A request
  names a node id. The engine:
  - derives the node's kind from the id alone;
  - refuses actions the node's kind does not list (`ActionNotAllowedError`);
  - builds the action, with no scanned tree needed.
  - Cull and edit take their command from the configuration inside the
    engine; clients no longer pass a command.
- **Open** becomes a core action that shows a folder in the system file
  manager.
- **Every action prepares a structured plan:**
  - Its steps (file moves with overwrites marked, folders created, renames,
    launches) are data. The text preview is rendered from them.
  - A short fingerprint, derived from the plan's content and stored
    nowhere, identifies the plan. Rename and new batch validate while
    preparing.
  - Archive moves exactly the files its plan lists.
- **Outcome kinds:** `ok`, `noop`, `refused`, `failed`. They replace the
  bare success flag. "Nothing to tidy" becomes a no-op instead of a
  failure.
- **Execution results report exactly what happened:** each step done and
  each step failed, plus the node id after the action, such as a renamed
  batch's new id.
- **Engine `action_apply(action, confirm=None)`** prepares, checks a
  confirmed fingerprint when one is given, and executes in one guarded
  call.
- **Scoped library scan:** `library_scan(node_id)` loads one subtree and
  its ancestor chain. Ancestors loaded only along that chain report that
  their view is incomplete. `library_resolve(path)` turns a darkroom path
  into a node id with the folder names' on-disk case.
- **Engine `config_keys()`** lists the configuration keys, and the engine
  can keep console logging quieter than the log file.
- **BREAKING** (internal API):
  - The `action_*` factories take node ids instead of paths.
  - `action_open_external_app` is replaced by `action_cull` and
    `action_edit`.
  - `prepare()` never returns `None`.
  - `ActionResult.success` is derived from `outcome`.
  - `PrepareError` is replaced by an action result with an outcome.
- Publish keeps overwriting files that already exist in the showroom, as
  its spec requires. The plan now lists those overwrites, and the preview
  shows them.

Non-goals:

- Jobs, progress or cancel.
- Rollback.
- Change notices to the client.
- Locking across processes (one client per core stays the model).
- A long-lived session or server mode.
- Showroom or archive paths as targets.
- Changing where a renamed batch lands when its year changes.
- Adapting the parked GUI.

## Capabilities

### New Capabilities

- `engine/action-requests`: how clients request, preview and run an
  action on a node:
  - node addressing and the kind guard;
  - plans with steps and a fingerprint;
  - outcome kinds;
  - applying an action, or confirming a plan by its fingerprint;
  - what a result reports.
- `app/command-line`: what the command-line tool offers a user or an
  agent:
  - commands and targets;
  - preview then apply;
  - text and JSON output;
  - exit codes;
  - no prompts;
  - saving configuration.
- `app/action-open`: opening a node's folder in the system file manager.

### Modified Capabilities

- `engine/library-index`:
  - a scoped scan by node id;
  - views that say whether they are complete;
  - resolving a darkroom path to a node id.
- `app/action-archive`: archive moves the files that were previewed and
  leaves later arrivals in place, reported.
- `app/action-publish`: the preview lists every file that will be
  overwritten.
- `app/action-rename-batch`:
  - the preview shows the new name;
  - invalid or taken names are refused before anything is applied;
  - an omitted date or title keeps the current one.
- `app/action-create-batch`: the preview shows the folders to create, and
  invalid names are refused before anything is applied.

## Impact

- **Code:**
  - `core/actions.py`: plans, steps, outcomes, results, a new open action,
    archive and publish on plan files, rename and new batch planned.
  - `core/file_utils.py`: archive merge over a given file list, reporting
    each move.
  - `core/engine.py`: the guard, typed node-addressed factories,
    `action_apply`, `library_scan(node_id)`, `library_resolve`,
    `config_keys`, a console log level.
  - `core/library/`: kind of an id, incomplete ancestors in
    `LibraryTree`, on-disk case of ids.
  - `core/logging_config.py`: a separate console level.
  - New modules in `cli/`; a console script in `pyproject.toml`.
- **Tests:** action and engine tests move to node ids, plans and
  outcomes. New contract tests for action requests, the scoped scan and
  path resolution. New in-process CLI tests under `tests/cli/`.
- **Dependencies:** none (argparse from the standard library).
  Configuration file and on-disk layout unchanged.
- **Docs:**
  - `DEV.md` (running the CLI);
  - `docs/core-split/frontend-coupling.md` (the rules this change moves
    into the core);
  - the roadmap item.
