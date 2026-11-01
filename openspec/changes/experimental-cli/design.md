# Design

## Context

- `Engine` factories take paths:
  - `action_tidy(path)`, `action_archive(path)`, `action_publish(path)`,
    `action_rename(path, year, month, day, name)`,
    `action_new_batch(device, year, month, day, name)`;
  - `action_open_external_app(template, path)`, where the client passes
    the command template.
  - Only the configuration roots are checked. Tidy runs on any folder, and
    nothing checks the node kind.
- `Action.prepare()` returns a per-action plan class, a `PrepareError`, or
  `None`:
  - rename, new batch and the external app return `None` and validate
    only at execute;
  - plans expose only `preview_text()`;
  - results are `success: bool`, `message` and `details`, plus
    `rescan_node_path` and `library_refreshed`.
- Archive's plan keeps `leaf_count`. `merge_tree_into_archive` lists the
  folder again at execute and moves what it finds there. Its result holds
  a count and issues.
- Library reads:
  - `library_node` and `library_refresh` need a full `library_scan()`;
  - `LibraryTree` requires the root's facts and recomputes ancestors from
    stored facts;
  - `scan_subtree(root, id, kind)` already scans any subtree;
  - `child_kind` derives a folder's kind from its parent's kind and its
    name, comparing `PUBLISH` case-sensitively.
- Logging goes to a file and to stderr at the engine's single level.
- Opening a folder in the file manager exists only in the parked GUI
  (`docs/core-split/legacy-gui/gui/widgets.py`).
- The CLI design was chosen after reviewing five alternatives: an
  id-first resource CLI with flat commands. Its rubric and the agreed
  requirements are summarised in proposal.md.

## Goals / Non-Goals

**Goals:**

- The usage this change makes possible:

  ```python
  engine.library_resolve(Path.cwd())          # -> "Camera/2026/2026-10 Walk"
  engine.library_scan("Camera/2026/2026-10 Walk")   # scoped; "" = full
  view = engine.library_node("Camera/2026/2026-10 Walk")
  view.complete, view.actions, view.total

  action = engine.action_archive("Camera/2026/2026-10 Walk")
  plan = action.prepare()                     # ActionPlan | ActionResult
  plan.steps, plan.changes_files, plan.fingerprint, plan.preview_text()
  result = engine.action_apply(action, confirm=plan.fingerprint)
  result = engine.action_apply(action)        # apply without confirming
  result.outcome, result.done, result.failed, result.left, result.node_id

  engine.action_rename("Camera/2026/2026-10 Walk", title="Hike")
  engine.action_new_batch("Drone", date="2027-01")
  engine.action_cull(node_id); engine.action_open(node_id)
  engine.config_keys()
  ```

  ```
  darkroom [--json] [--config PATH] [-v] COMMAND ...
    status
    config list | get KEY | set KEY VALUE
    inspect [TARGET] [--depth N]
    open | cull | edit TARGET
    tidy | publish | archive TARGET [--apply | --confirm FINGERPRINT]
    rename TARGET [--date YYYY-MM[-DD]] [--title T | --no-title] [RUN]
    new-batch TARGET --date YYYY-MM[-DD] [--title T] [RUN]
                                  RUN = --apply | --confirm FINGERPRINT
  ```

- No CLI module decides a domain rule. The CLI parses input, calls the
  engine and renders the result.
- A one-shot command reads only what it needs: actions need no scan, and
  `inspect` reads one subtree.

**Non-Goals:**

- Making `prepare()` busy-guarded. Preparing only reads, as before.
- Trimming views by depth in the engine. Depth is a rendering choice of
  the CLI, and totals always cover the whole subtree.
- A configuration-file path in `status`; the not-ready detail already
  names it.

## Decisions

### The CLI is named `darkroom`, aliased `dr`, and uses argparse

Two console scripts in `[project.scripts]` point at the same entry:
`darkroom = "photo_darkroom_manager.cli:main"` and
`dr = "photo_darkroom_manager.cli:main"`. The parser sets
`prog="darkroom"`, so help and error messages name the tool the same way
whichever script started it. `python -m photo_darkroom_manager.cli` works
too.

`darkroom` says what the tool manages in the project's own word; `dr` is
short to type and no common command uses it.

*Alternatives:*
- `pdm`, the name used during the brainstorm. It clashes with the PDM
  Python package manager on the same machines.
- `dkr` as the alias. Harder to type than `dr`.
- `pdr` alone. Short, but cryptic.
- `darkroom-manager` with `drm`. `drm` reads as digital rights
  management or Linux's Direct Rendering Manager.
- `lab`. Too generic, and it clashes with the GitLab `lab` CLI.
- Shortcut aliases for subcommands (`i` for `inspect`). Left out: the
  action names are short already, and one-letter aliases are easy to
  run by accident on commands that move files.
- Typer or click. They bring nicer help, but a new dependency for an
  experimental tool that argparse covers.

### CLI modules: parse, resolve targets, render

```
cli/
  __init__.py   main(argv=None) -> int
  __main__.py   raise SystemExit(main())
  _app.py       parser, command dispatch, error -> exit code mapping
  _targets.py   TARGET string -> node id (id:, paths, bare targets)
  _render.py    text and JSON renderers for status, config, views,
                plans and results
```

`main(argv)` builds the engine and calls
`run(argv, *, cwd, stdout, stderr, engine) -> int`, so tests drive the CLI
in-process with a temporary darkroom, a config file and string buffers.
Every renderer takes plain core values (`NodeView`, `ActionPlan`,
`ExecutionResult`, `ConfigIssue`) and has a text and a JSON form.

### Requests are node-addressed and guarded in the engine

Every factory takes a node id and resolves it through one private guard:

```python
def _target(
    self, node_id, action: NodeAction, *, creates=False
) -> tuple[NodeId, Path]
```

1. Require `ready`.
2. Canonicalise the id to on-disk names (next decision). A malformed id
   (`..`, `.`, empty parts, backslashes, absolute) raises
   `NodeNotFoundError`.
3. Derive the kind with `layout.node_kind(node_id)`, a pure walk of
   `child_kind` over the id's parts. `None` raises `NodeNotFoundError`.
4. If `action not in node_actions(kind)`, raise
   `ActionNotAllowedError(node_id, action, kind)`.
5. If the folder does not exist and the action does not create it, raise
   `NodeNotFoundError`. Only `new_batch` creates its device folder.

The factories:
- `action_open`, `action_tidy`, `action_cull`, `action_edit`,
  `action_publish` and `action_archive` each take `(node_id)`.
- `action_rename(node_id, *, date=None, title=None, clear_title=False)`.
- `action_new_batch(device_id, *, date, title=None)`.

`date` is `YYYY-MM[-DD]`, parsed by the layout's `BatchFolderName` rules,
so clients pass the string the user typed.

Each factory hands the action an `ActionRequest(action, node_id, params)`:
a frozen record of what was asked, which plans carry and fingerprint.
Actions
stay standalone and path-based. The request is data about them, not a
link to the engine.

*Alternatives:*
- A guard in the CLI. That puts a domain rule in a frontend, and the GUI
  would copy it.
- One generic `action_request(node_id, action, **params)`. It was rejected
  in the brainstorm in favour of typed calls.
- Using the scanned tree's kind when one is loaded. That gives the same
  answer from the same table, but adds a second code path.

### Ids and paths resolve to on-disk names

New `library/_resolve.py`:
- `canonical_id(root, node_id) -> NodeId`: for each part, keep an exact
  match on disk. Otherwise take the single case-insensitive match from
  the parent's listing. Otherwise keep the part as typed, for folders
  that do not exist yet.
- `resolve_path(root, path) -> NodeId`: normalise the absolute path,
  compare it with the root using `os.path.normcase`, raise
  `PathOutsideDarkroomError(path, root)` when outside, then call
  `canonical_id`.

Symlinks are not followed, so ids stay what the user sees. The engine
exposes `library_resolve(path)` and applies `canonical_id` in `_target`
and `library_scan`.

*Alternative:* `Path.resolve()`. It follows symlinks, so a device linked
from another drive would leave the darkroom.

### One plan type with typed steps

```python
Step = Move | MakeDir | Rename | OpenFolder | Launch
Move(source, target, overwrite=False); MakeDir(path); Rename(source, target)
OpenFolder(path); Launch(argv)

@dataclass(frozen=True)
class ActionPlan:
    request: ActionRequest
    summary: str                 # one line, e.g. "Archive 42 files"
    steps: tuple[Step, ...]
    changes_files: bool          # any Move, MakeDir or Rename
    fingerprint: str             # 12 hex chars, derived, never stored
    def preview_text(self) -> str
```

The per-action plan classes go away. An action's `_execute(plan)` checks
`plan.request == self.request` and runs the plan's steps through shared
helpers, adding its own policy:

| Action | Policy at execute |
|---|---|
| Tidy | Refuse if a conflict appeared; create target folders. |
| Archive | Refuse if any target exists; move, prune, report leftovers. |
| Publish | Overwrite as today. |
| Rename, new batch | Refuse if the target exists. |

So "execution follows the plan" holds by construction.

- **Fingerprint:** SHA-256 over a canonical JSON of the action, node id,
  sorted params and the steps (POSIX paths and flags), cut to 12 hex
  characters. It is a property computed from the plan; neither the
  engine nor the disk keeps it, so any process that prepares the same
  plan gets the same value. Absolute paths are part of it, so a root
  change also changes the fingerprint. "Fingerprint" rather than "id":
  an id suggests a stored plan to look up, and there is none.
- **Preview:** `preview_text()` renders the summary, counts by step kind
  and the first 35 steps. Overwrites are always listed.
- **Rename and new batch** now validate in `prepare()`:
  - names via `BatchFolderName` and `validate_device_name`;
  - "already exists";
  - the device symlink escape.
  - Rename fills an omitted date or title from
    `BatchFolderName.from_str(current name)`. A current name it cannot
    parse needs `--date`. A rename to the same name is `noop`.
- **External apps:** cull, edit and open resolve their `Launch` argv or
  `OpenFolder` path in `prepare()`. Execute runs exactly that. Opening a
  folder uses one private `_open_folder(path)` (`os.startfile`, `open`,
  `xdg-open`) that tests patch.

*Alternatives:*
- **Per-action plan subclasses with structured fields.** Every client
  would need to know each class.
- **Including mtimes and sizes in the fingerprint.** Editors and indexers
  touch files, so fingerprints would change for no visible reason. Names
  and targets
  already catch added, removed and conflicting files. A file whose content
  changes but keeps its name is not detected, which is acceptable for
  moves.

### Outcomes and results

```python
Outcome = Literal["ok", "noop", "refused", "failed"]

@dataclass(frozen=True)
class ActionResult:
    outcome: Outcome; message: str; details: str | None = None
    success -> outcome in ("ok", "noop")

@dataclass(frozen=True)
class ExecutionResult(ActionResult):
    done: tuple[Step, ...] = ()
    failed: tuple[StepFailure, ...] = ()     # step + reason
    left: tuple[Path, ...] = ()              # e.g. files archive did not move
    fingerprint: str | None = None           # of the plan run or found
    rescan_node_path: Path | None = None
    node_path: Path | None = None            # acted-on folder afterwards
    library_refreshed: NodeId | None = None
    node_id: NodeId | None = None            # set by the engine
```

`prepare()` returns `ActionPlan | ActionResult`. Exceptions become
`failed` with the traceback in `details`. The mapping of today's
messages:

| Message today | Outcome |
|---|---|
| "Nothing to tidy", empty `PUBLISH/`, same rename name | `noop` |
| Conflicts, invalid input, unavailable root, plan mismatch (*) | `refused` |
| Unexpected errors, steps failing partway | `failed` |

(*) Also an unrecognised batch, a missing `PUBLISH/` and an unconfigured
command.

The engine turns `node_path` into `node_id`, as it already does for
`rescan_node_path`.

*Alternative:* keep `success` and add an error code. Two fields that can
disagree.

### `action_apply` prepares, confirms and executes in one guarded call

`action_apply(action, confirm=None) -> ExecutionResult`:
1. It enters the busy guard once and prepares.
2. A non-plan outcome is returned as an `ExecutionResult` with that
   outcome.
3. When `confirm` is given and the plan's fingerprint differs, it returns
   `refused`. The message names both fingerprints, e.g. `plan changed
   since 3f9a1c07 (now 81d0e5aa); preview again`, and the result's
   `fingerprint` is the current one.
4. Otherwise it executes and refreshes like `action_execute`.

The CLI maps `--apply` to `action_apply(action)` and `--confirm F` to
`action_apply(action, confirm=F)`. argparse puts the two in a mutually
exclusive group, so both together is a usage error.

*Alternatives for the wording:*
- `--apply --expect DIGEST`. It names the mechanism, not the intent, and
  makes one flag modify another.
- `--apply --if-plan F`, in the spirit of HTTP `If-Match`. Precise, but
  less natural to type.
- `--apply F`. One flag with an optional value is easy to misread, and
  running without a check would then need a separate `--force`.

`action_execute(action, plan)` stays for in-process clients that keep the
plan they showed.

*Alternative:* serialising plans for later execution. The plan becomes a
second, trusted source of truth outside the engine, and it settles
Phase 3's "plan, then apply" before its research.

### Archive moves a given file list

`file_utils` gains:
- `move_files(moves) -> MoveReport(done, failed)` over `cstm_shutil_move`;
- `prune_empty_dirs(top)`, public.

`merge_tree_into_archive` is replaced. `preview_merge_into_archive` keeps
listing the leaves and conflicts for `prepare()`. After moving, archive
lists what is left under the source folder and reports it as `left`.

### Scoped scan loads a subtree plus its ancestor chain

`library_scan(node_id="")`:
1. Require `ready`, canonicalise and derive the kind; a missing folder
   raises `NodeNotFoundError`.
2. Enter the busy guard as `scan`.
3. `""` builds a new tree from a full scan, as today.
4. Any other id reads `scan_subtree(root, id, kind)` plus
   `_scan.scan_chain(root, id)`. The chain gives facts for each ancestor:
   own counts and issues from one listing, `children=(next on the path,)`,
   `complete=False`.

`NodeFacts` and `NodeView` gain `complete: bool`. `LibraryTree`:
- **`load_subtree(id, facts, chain)`:** adds the missing ancestors as
  stubs, adds the id to an existing ancestor's children if needed, then
  replaces the subtree and re-aggregates up.
- **A tree built from a chain:** `LibraryTree(root, chain | facts)` also
  works, since the chain contains `""`.
- **`complete`:** a node's `complete` is its own facts' flag, and-ed over
  its children.
- **Refreshing a stub ancestor** scans its whole subtree and makes it
  complete.

`library_refresh` keeps its fallback semantics. `library_scan(id)`
rejects unknown ids instead of falling back, because a client asked to
look at that node.

*Alternatives:*
- **A tree rooted at the scanned node.** Ids are darkroom-relative, so the
  tree would need a second root concept.
- **`library_node` scanning when needed.** That mixes I/O into a read and
  contradicts the spec rule that reading before a scan is rejected.

### CLI targets

`_targets.resolve(text, cwd, engine) -> NodeId`:

| Input | Read as |
|---|---|
| `id:X` | the id `X` (`id:` alone is the root) |
| An absolute path, or one starting with `.` | a `cwd`-relative path |
| Bare text | both an id and a `cwd`-relative path, see below |

For bare text:
- An empty string is the root.
- Otherwise the candidate path counts when it exists on disk and resolves
  inside the darkroom. The candidate id counts when its canonical folder
  exists.
- If one counts, use it.
- If both count and differ, it is refused as ambiguous.
- If neither counts, keep the id, so `new-batch Drone` reaches the
  engine's guard.

`inspect` without a target uses `cwd` when it is inside the darkroom, and
the root otherwise. This is input syntax, not domain logic: the GUI never
parses such strings.

### CLI output, errors and exit codes

- **Text:**
  - `inspect` renders an indented tree down to `--depth` (default 1);
    children beyond the depth are shown as a count;
  - plans render as `preview_text()` plus `plan <fingerprint>` and the
    `--confirm` command that runs exactly that plan;
  - results show the outcome, the message, done and failed counts, left
    files, and the new id.
- **`--json`:** one document per command:
  `{"format": 1, "command": ..., "ok": bool, "result" | "error": ...}`.
  - A result holds the node view (children cut at `--depth`, with a
    `child_count`), or the plan with all its steps, or the execution
    result.
  - An error holds `kind`, `message` and, where known, a `fix` naming the
    CLI command, e.g. `config set darkroom PATH`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | `ok`, `noop`, or a preview printed |
| 1 | `failed` |
| 2 | Usage error (argparse) |
| 3 | `refused`, not allowed, ambiguous target, busy engine |
| 4 | `EngineNotReadyError` |
| 5 | `NodeNotFoundError`, `PathOutsideDarkroomError` |

- `ConfigValueError` and `UnknownConfigKeyError` from `config set` exit
  with 3.
- `config set` calls `config_set` and then `config_save`.
- `open`, `cull` and `edit` execute at once, because their plan's
  `changes_files` is false. The core decides that, not the CLI.

### Quieter console logging

`configure_logging(level, *, logs_dir, console_level=None)` sets the
stderr handler to `console_level` when given. The file keeps `level`.
`Engine(..., console_log_level=None)` passes it through. The CLI uses
`WARNING`, or `INFO` with `-v` and `DEBUG` with `-vv`, so a person sees
results and an agent sees clean stderr. `config_keys()` exposes the
configuration's key order, which `config list` needs.

## Risks / Trade-offs

- **Archiving thousands of files gives a large JSON plan.** The text
  preview is truncated. A `--brief` option that drops the steps can come
  when an agent needs it.
- **No lock across processes:** two `--apply` runs could overlap. One
  client per core is the agreed model, and `--confirm` catches most
  surprises.
- **Partial trees add a `complete` flag every reader must respect.**
  Contract tests cover stub ancestors, completion by a later scan and
  refresh of a stub.
- **Large internal API break** (factories, plans, results). The parked
  GUI is reference only, and the tests move in the same change.
- **The rename default depends on parsing the current name.** An
  unparseable name asks for `--date`, so it never guesses.
- **Opening a folder cannot be checked in tests.** `_open_folder` is the
  only OS call and is patched.

## Migration Plan

Internal API only. Tests move to the new API in the same change. The
configuration file and the on-disk layout are unchanged, and there are no
rollback steps. `docs/core-split/frontend-coupling.md` records that
opening a folder, the rename defaults, the forms' validation and the
structured previews have moved into the core.
