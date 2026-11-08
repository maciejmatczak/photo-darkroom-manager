# Design

## Context

What the code looks like after `core-jobs-framework` (see proposal.md, Why,
for the problem):

- `core/actions/_actions.py` holds every action in one module. `Action`
  has `prepare()` and `execute(plan)`; `JobAction` adds
  `execute(plan, *, policy, job)` and `policies`. Rename and new batch
  carry an `exclusive` flag.
- `ActionPlan` is one shared type for every action: typed steps (`Move`,
  `MakeDir`, `Rename`, `OpenFolder`, `Launch`), conflicts and a conflict
  label; the fingerprint is computed from them. `ExecutionResult` mixes the
  user's report with instructions for the engine (`rescan_node_path`,
  `node_path`).
- `core/engine.py` builds actions with eight `action_<name>` methods and
  runs them all through one generic path: `action_apply`, `action_start`
  or inline under `JobSlot.hold`.
- The CLI previews by calling `action.prepare()` itself and maps
  `--on-conflict` to a policy.

The requirements are in this change's specs; this document covers how.

## Goals / Non-Goals

**Goals:**

- `core/actions` is a collection of actions on a shared foundation: types
  and helpers any action may use, with no word of files, steps, conflicts,
  policies, nodes or rescans in it.
- Actions are unique: each has its own types and its own path of
  execution, like one form class per URL on the web. There is no common
  interface to execute them.
- Engine concepts (node ids, rescans, the job slot) stay in the engine.
- One busy rule (a job is running), owned by the executor's one-job limit.

**Non-Goals:**

- No change to how files are moved (`file_utils`), to scans, to the job
  slot's mechanics beyond removing `hold`, or to the CLI's commands, flags
  and exit codes.
- No GUI work; the GUI (Phase 6) will use the same calls and types.

## Decisions

### 1. The engine's surface

One call per direct action, and one pair of calls per planned action, all
with the `action_` prefix:

```python
# core/engine.py — direct: run at once, return the action's result
engine.action_open(node_id) -> OpenFolderResult
engine.action_cull(node_id) -> ExternalAppResult
engine.action_edit(node_id) -> ExternalAppResult

# core/engine.py — planned: prepare gives that action's plan,
# executing hands the plan back to that action's own call
engine.action_prepare_rename(node_id, date=None, title=None,
                             clear_title=False) -> RenamePlan
engine.action_rename(plan: RenamePlan, answers={}) -> Job

engine.action_prepare_new_batch(device_id, date="2026-10",
                                title=None) -> NewBatchPlan
engine.action_new_batch(plan: NewBatchPlan, answers={}) -> Job

engine.action_prepare_tidy(node_id) -> TidyPlan
engine.action_tidy(plan: TidyPlan, answers={}) -> Job

engine.action_prepare_archive(node_id) -> ArchivePlan
engine.action_archive(plan: ArchivePlan, answers={}) -> Job

engine.action_prepare_publish(node_id) -> PublishPlan
engine.action_publish(plan: PublishPlan, answers={"existing": "replace"}) -> Job
```

Every call refuses the same way: by raising a typed error, as the engine
already does for a bad id (`NodeNotFoundError`) or kind
(`ActionNotAllowedError`); actions add `ActionRefusedError` (decision 2).
An execute call returns the job at once, or raises before any job starts.
`action_apply`, `action_start` and today's `action_<name>` factories go
away. The node-kind guard (`_resolve_action_target`, today's `_target`)
runs in every call above.

*Alternative:* one generic `action_execute(plan, answers)` for every plan.
Rejected: one call for every plan type needs a common interface every
action must fit, a plan that carries its action back to the engine, and a
table that looks up what to do by plan type; the type checker could not
catch a rename plan handed to the archive.

*Alternative:* one generic `action_prepare(name, node_id, **inputs)`.
Rejected for the same reason: typed inputs and a typed plan per action
are clearer, and the caller knows which action it calls anyway.

*Alternative:* `action_execute_<name>` for the execute calls. Rejected:
longer and says nothing more; "prepare the archive", then "archive".

### 2. The shared foundation

`core/actions/_base.py` holds what every action may build on. It knows
nothing about the engine or about any one action, and defines no
interface to execute.

```python
# core/actions/_base.py — shared types
@dataclass(frozen=True)
class ActionResult:                   # every action has a result
    outcome: Outcome                  # "ok" | "failed" | "cancelled"
    message: str

@dataclass(frozen=True)
class Question:                       # one form field with choices
    text: str                         # "3 files already in the showroom"
    choices: tuple[str, ...]          # ("replace", "skip")
    default: str | None = None        # None: the user must answer

Answers = Mapping[str, str]           # posted form data

@dataclass(frozen=True)
class ActionPlan(ABC):                # some actions have a plan
    questions: Mapping[str, Question]
    fingerprint: str

    @property
    @abstractmethod
    def nothing_to_do(self) -> bool: ...  # each plan answers from its fields

class ActionRefusedError(Exception):  # cannot plan or run as asked
    message: str
    details: str | None
```

```python
# core/actions/_base.py — shared helpers
def fingerprint(*parts: object) -> str: ...
def require_unchanged_plan(plan: ActionPlan,
                           fresh_plan: ActionPlan) -> None: ...
def check_answers(questions: Mapping[str, Question],
                  answers: Answers) -> Answers: ...
```

- **Results:** every action, direct or planned, returns its own subclass
  of `ActionResult`. Results only ever end `ok`, `failed` or `cancelled`.
- **Plans:** only planned actions have one. A plan with nothing to do is
  still a plan; its fields show it, and `nothing_to_do` lets a frontend
  skip the confirmation without knowing the plan type.
- **Refusing:** `ActionRefusedError` is the one way an action says it
  cannot plan or run as asked (a missing `PUBLISH/`, a taken name, an
  invalid month, a bad command).
- **`fingerprint`:** every action hashes the same way.
- **`require_unchanged_plan`:** raises `ActionRefusedError` naming both
  fingerprints when a fresh plan differs from the one handed back.
- **`check_answers`:** applies the web-form rules (a known question, a
  choice it offers, the default when unanswered) and returns the answers
  with defaults filled in; otherwise raises `ActionRefusedError` naming
  the question.

*Alternative:* `prepare() -> P | ActionResult`, with `noop` and `refused`
results. Rejected: it mixes two cases into one union, and a refusal would
be a value here but an error for a bad id or kind.

*Alternative:* typed answers per action. Rejected: a third type per action
for little gain; the questions already say what can be answered.

### 3. Each planned action is its own module

A planned action module defines its plan and result types and two plain
functions, `prepare` and `run`; the module name says which action, so the
engine calls them as `archive.prepare` and `archive.run`. Nothing makes
the modules alike
except the foundation they use.

```python
# core/actions/archive.py
@dataclass(frozen=True)
class ArchivePlan(ActionPlan):
    source: Path                      # also the input to prepare again
    target: Path
    files: int
    conflicts: tuple[Path, ...]
    _moves: tuple[Move, ...] = field(repr=False)   # private work

@dataclass(frozen=True)
class ArchiveResult(ActionResult):
    moves: MoveReport
    removed_folders: tuple[Path, ...]

def prepare(source: Path, darkroom_root: Path,
            archive_root: Path) -> ArchivePlan: ...
def run(plan: ArchivePlan, answers: Answers, job: Job) -> ArchiveResult: ...
```

- **The plan is the preview:** its fields say what will happen, in the
  action's own terms. There is no shared preview text.
- **Plans are plain data:** a plan carries the inputs its prepare got, so
  the engine can prepare it again from the plan alone, and the work the
  run will do in a private field. The fingerprint covers that work and
  the questions, so any change in what the action would do changes it.
  Frontends never show private fields.
- **Private helpers:** `Move`, `MakeDir` and friends belong to the actions
  that use them.

| Action | Plan says | Result says |
| --- | --- | --- |
| tidy | folder, files to move with their targets, conflicts | `MoveReport` |
| archive | source, target, files, conflicts | `MoveReport`, emptied dirs |
| publish | source, showroom folder, files, files to replace | `MoveReport` |
| rename | old folder, the inputs, new folder | new folder |
| new batch | device folder, the inputs, folders to create | created batch |

Actions that move files put a `MoveReport` (moved, failed with reasons,
skipped, left by a cancel, remaining) from the shared move helper
(`_moves.py`) in their result, the one place spec `app/file-moves`
"Moves are reported" lives.

### 4. Direct actions

Open, cull and edit live in `core/actions/apps.py`. They have no plan
and no job, but a result like every action:

```python
# core/actions/apps.py
@dataclass(frozen=True)
class OpenFolderResult(ActionResult):
    folder: Path

@dataclass(frozen=True)
class ExternalAppResult(ActionResult):  # cull and edit: one mechanism
    folder: Path
    command: tuple[str, ...]            # what was started
    exit_code: int | None               # set when it exited at once

def open_folder(folder: Path) -> OpenFolderResult: ...
def open_external_app(command: str, folder: Path) -> ExternalAppResult: ...
```

| Case | What happens | Where |
| --- | --- | --- |
| Opened or started | `ok` result | `apps.py` |
| Cannot start, or exits at once with an error | `failed` result | `apps.py` |
| Bad command, unknown placeholder, no image | refused | `apps.py` |
| No command configured | refused, naming the key | engine |
| The folder is gone | `NodeNotFoundError` | engine guard |

Refused means `ActionRefusedError`. The engine checks configuration
because it owns it; `apps.py` only gets
a command and a folder. The engine returns the result as it is: a direct
action neither moves a node nor needs a rescan, so the engine has nothing
to add.

So every action follows one rule: a refusal raises; an action that was
attempted returns its own result.

### 5. Executing a plan

Each execute call follows the same steps, through one engine-private
helper so that none can skip the checks:

```python
# core/engine.py — one execute call
from photo_darkroom_manager.core.actions import archive

def action_archive(self, plan: archive.ArchivePlan,
                   answers: Answers = {}) -> Job:
    fresh_plan = self.action_prepare_archive(
        self._node_id_for_folder(plan.source)
    )
    return self._execute_planned_action(
        plan,
        fresh_plan,
        answers,
        run_action=archive.run,
        after_run=self._after_archive_run,
    )

# core/engine.py — archive's callback, next to its call
def _after_archive_run(
    self, plan: archive.ArchivePlan, result: archive.ArchiveResult, job: Job
) -> NodeActionResult[archive.ArchiveResult]:
    refreshed = self._refresh(
        self._node_id_for_folder(plan.source.parent), job.log
    )
    node_id = (
        self._node_id_for_folder(plan.source) if plan.source.is_dir() else None
    )
    return NodeActionResult(result, node_id, refreshed)

# core/engine.py — the steps every execute call shares, private, universal
def _execute_planned_action(
    self, plan, fresh_plan, answers, run_action, after_run
) -> Job:
    require_unchanged_plan(plan, fresh_plan)        # raises: stale plan
    checked_answers = check_answers(fresh_plan.questions, answers)
    return self._jobs.start(...)    # result = run_action(fresh_plan,
                                    #   checked_answers, job); then
                                    # after_run(fresh_plan, result, job)
                                    # is the job's result; and the log
```

`_execute_planned_action` knows nothing about any one action: it gets the
action's run function and one callback for what follows it.

`check_answers` raises for a bad answer, like `require_unchanged_plan`
for a stale plan.

1. **Prepare again** through the action's own `action_prepare_<name>`
   call, from the inputs the plan carries, so the node guard runs again.
2. **Check, before any job starts:** an unchanged plan and valid answers;
   otherwise `ActionRefusedError`, and no file changes.
3. **Start the job:** the action's run function on the fresh plan, whose
   work is current. The call returns the job at once.
4. **After the run, whatever its outcome:** the call's own callback
   (decision 6), whose return is the job's result, and the log lines, as
   `_apply` does today.

The private engine methods this change adds or renames, named so that
each reads on its own on a large class:

- `_execute_planned_action`: the shared steps above
- `_after_<name>_run`: one callback per planned action, for whatever
  follows its run (decision 6)
- `_node_id_for_folder`: the node id of a darkroom folder
- `_resolve_action_target`: today's `_target`; checks the node exists
  and its kind allows the action, and returns its id and folder

`_request`, `_apply`, `_prepare_and_run` and `_after` go away with the
generic path.

What the run finds that the check could not see, such as a file put at a
target in between, is handled inside the run: by the user's answer where
a question covered it, or reported as a failed or skipped file.

### 6. What the engine does after a run

Each execute call's callback does what follows its run: today, rescan
and find the node afterwards, from its plan and result fields:

| Call | Rescan | Node afterwards |
| --- | --- | --- |
| `action_tidy` | the folder | the folder |
| `action_publish` | the batch | the batch |
| `action_archive` | the source's parent | the source, or none if removed |
| `action_rename` | the old folder's parent | `RenameResult.folder` |
| `action_new_batch` | the parent of the created batch | the created batch |

Each callback is a small private method next to its call
(`_after_archive_run`). Actions never name nodes or rescans; `ExecutionResult`,
`rescan_node_path` and `node_path` go away.

The job's result is an engine type that carries the action's result
untouched next to what the engine added:

```python
# core/engine.py — the engine's result of an executed plan
@dataclass(frozen=True)
class NodeActionResult[R: ActionResult]:
    result: R                         # the action's own result
    node_id: NodeId | None            # the node afterwards
    library_refreshed: NodeId | None  # what the engine rescanned
```

*Alternative:* the engine adds `node_id` and `library_refreshed` to the
action's result. Rejected: engine concepts would be back on the actions'
types.

### 7. Every planned action is a job; one busy rule

Rename and new batch run as jobs like the others; their run ignores
cancel and reports no progress, since they are one step. `JobSlot.hold`,
`_held` and the `exclusive` flag are removed. The busy rule is the slot's
own: `start` and `require_idle` refuse while a job is active. Direct
actions never touch the slot.

### 8. Package layout

```
core/actions/
  __init__.py      public names
  README.md        design rules
  _base.py         the foundation: ActionResult, ActionPlan, Question,
                   Answers, ActionRefusedError, fingerprint,
                   require_unchanged_plan, check_answers
  _moves.py        shared move helper and MoveReport (tidy, archive, publish)
  tidy.py  archive.py  publish.py  rename.py  new_batch.py
                   one planned action each: its plan and result types,
                   prepare and run
  apps.py          open, cull, edit: their result types and functions
```

Tests mirror it under `tests/core/actions/`, one file per module.

### 9. The frontends

Each frontend shows each plan and result type its own way, like a
template per form.

- **CLI rendering:** `cli/_render.py` has one text and one JSON renderer
  per plan type and per result type, found by type. A type without one
  is a missing feature of the CLI, caught by a test, not a fallback to
  generic text.
- **Commands:** `cli/_app.py` keeps its one runner; its command table
  maps each planned command to its pair of engine calls (prepare,
  execute) and each direct command to its one call.
- **Preview:** the runner calls the prepare call and prints the rendered
  plan, each question with its choices, the fingerprint and the
  `--confirm` command. A plan with nothing to do prints without a
  `--confirm` command and exits 0.
- **Run:** `--apply` prepares and executes at once; `--confirm FP`
  prepares, compares with `FP` and executes. A plan with nothing to do is
  not executed. Each command maps its flags to its action's answers, e.g.
  `publish --on-conflict replace` → `{"existing": "replace"}`.
- **Exit codes:** `ActionRefusedError` exits 3 (refused) with its
  message; a `failed` result exits 1, a `cancelled` one 130, as today.
- **JSON:** a plan is `{action, ...its own fields, questions,
  fingerprint}`; a result is `{action, outcome, message, ...its own
  fields}`, plus `node_id` and `library_refreshed` for an executed plan.
  `action` is the command's name.

## Risks / Trade-offs

- [Every action and most tests are rewritten] → Do it one action at a
  time; each keeps its behaviour tests (`tests/core/actions/`) green
  before the next.
- [The engine's surface grows to 13 action calls, two per new planned
  action] → Accepted: each is a few lines over
  `_execute_planned_action`, and typed.
- [Nothing forces a new action to fingerprint its work] →
  `_execute_planned_action` always runs the stale check, and each action
  module has a fingerprint test.
- [No generic "run any plan" for tests or tools] → Accepted: tests call
  each action's own functions; the CLI already dispatches per command.
- [A new action needs a renderer per type in every frontend] → Accepted:
  that is the point of typed plans; a CLI test lists every plan and
  result type and fails on a missing renderer.
- [The CLI's JSON changes shape] → Marked experimental; `DEV.md` updated.
- [Questions are matched to CLI flags by hand in each command] →
  Accepted: a handful of commands.
- [Rename and new batch write a job log for one step] → Accepted by
  decision; it is cheap and keeps one way to run planned actions.
- [The disk can change between the check and the run] → The run follows
  the user's answers where a question covers it and reports anything
  else as a failed or skipped file; it never overwrites (spec
  app/file-moves).
- [A refusal leaves no job log] → Accepted: nothing ran; the engine logs
  the refusal in the app log.

## Migration Plan

One change on `dev-core-split`; no data or settings migrate. Rollback is
reverting the change.
