# Design

## Context

What the code looks like after `core-jobs-framework` (see proposal.md, Why,
for the problem):

- `core/actions/_actions.py` holds every action in one module. `Action`
  has `prepare()` and `execute(plan)`; `JobAction` adds
  `execute(plan, *, policy, job)` and `policies`. Rename and new batch
  carry an `exclusive` flag.
- `ActionPlan` lists typed steps (`Move`, `MakeDir`, `Rename`,
  `OpenFolder`, `Launch`), conflicts and a conflict label; the fingerprint
  is computed from them. `ExecutionResult` mixes the user's report with
  instructions for the engine (`rescan_node_path`, `node_path`).
- `core/engine.py` builds actions with eight `action_<name>` methods and
  runs them through `action_apply`, `action_start` or inline under
  `JobSlot.hold`.
- The CLI previews by calling `action.prepare()` itself and maps
  `--on-conflict` to a policy.

The requirements are in this change's specs; this document covers how.

## Goals / Non-Goals

**Goals:**

- The shared part of planned actions is only a form flow and a job: no
  word of files, steps, conflicts or policies in it.
- Each action is readable on its own: its inputs, its preview, its
  questions, its run.
- One busy rule (a job is running), owned by the executor's one-job limit.

**Non-Goals:**

- No change to how files are moved (`file_utils`), to scans, to the job
  slot's mechanics beyond removing `hold`, or to the CLI's commands, flags
  and exit codes.
- No GUI work; the GUI (Phase 6) will use the same two calls.

## Decisions

### 1. The engine's surface

Three groups of calls, all with the `action_` prefix:

```python
# direct: run at once, return the result
engine.action_open(node_id)
engine.action_cull(node_id)
engine.action_edit(node_id)

# planned, step 1: one call per action, its own typed inputs
engine.action_prepare_rename(node_id, date=None, title=None, clear_title=False)
engine.action_prepare_new_batch(device_id, date="2026-10", title=None)
engine.action_prepare_tidy(node_id)
engine.action_prepare_archive(node_id)
engine.action_prepare_publish(node_id)

# planned, step 2: one call for every plan; returns the job at once
engine.action_execute(plan, answers={"existing": "replace"})
```

`action_apply`, `action_start` and the `action_<name>` factories go away.
The node-kind guard (`_target`) runs in every call above, as today.

*Alternative:* one generic `action_prepare(name, node_id, **inputs)`.
Rejected: typed inputs per action are clearer, and the caller knows which
action it calls anyway.

### 2. The plan is a form

```python
@dataclass(frozen=True)
class Question:                      # one form field with choices
    text: str                        # "3 files already in the showroom"
    choices: tuple[str, ...]         # ("replace", "skip")
    default: str | None = None       # None: the user must answer

@dataclass(frozen=True)
class ActionPlan:                    # the form
    action: str                      # "publish"
    node_id: NodeId
    inputs: Mapping[str, object]     # what prepare got, to prepare again
    preview: str                     # plain text
    questions: Mapping[str, Question]
    fingerprint: str
```

A question is a generic choice field, as in any web form; what a
question and its choices mean is the action's business. A plan without
questions needs only a confirmation.

*Alternative:* questions fully opaque (`Mapping[str, object]`). Rejected:
the CLI preview and the answer check need at least text and choices, and
a choice field is as generic as a form gets.

### 3. A planned action keeps its work private

```python
class PlannedAction(ABC):            # core/actions/_base.py
    name: ClassVar[str]

    def prepare(self) -> ActionPlan | ActionResult: ...   # looks at the disk
    def run(self, answers: Mapping[str, str], job: Job) -> Ran: ...
```

`prepare` works out what to do, keeps it on the instance (for a move
action: its list of moves; for rename: the new path) and returns the
public plan. `run` uses that private work. Nothing outside the action
sees it, so `Move`, `MakeDir` and friends become private helpers of the
actions that use them.

The fingerprint is computed by the action from its inputs, its private
work and its questions, through one helper in `_base.py`
(`fingerprint(*parts)`), so every action hashes the same way.

### 4. Executing a plan

`action_execute(plan, answers)` in the engine:

1. Build a fresh action from `plan.action`, `plan.node_id` and
   `plan.inputs` (a private table: name → builder, the same builders the
   `action_prepare_<name>` calls use).
2. Prepare it; if the outcome is not a plan, or its fingerprint differs,
   return a refusal naming both fingerprints. Nothing starts.
3. Start the job: `action.run(answers, job)`, then the rescan, the log
   lines and the node id, as `_apply` does today.

Answers are checked at the start of `run`, by a base helper that applies
the generic form rules (known question, a choice it offers, the default
when unanswered). A bad answer ends the job `done` with a `refused`
result, as the specs require.

*Alternative:* check answers in the engine before starting the job.
Rejected: the specs make the check the action's, and the action may add
its own rules on top of the generic ones.

### 5. What a run returns

```python
@dataclass(frozen=True)
class Ran:                           # action → engine, never shown
    result: ActionResult             # what the user sees
    rescan: Path | None              # what changed on disk
    node: Path | None                # where the node is afterwards
```

`ActionResult` stays the user's report: `outcome`, `message`, `details`,
plus `node_id` and `library_refreshed` set by the engine. Actions that
move files add a `MoveReport` (moved, failed with reasons, skipped, left
by a cancel, remaining) from the shared move helper, the one place spec
`app/file-moves` "Moves are reported" lives. `ExecutionResult` with its
step lists goes away.

### 6. Every planned action is a job; one busy rule

Rename and new batch run as jobs like the others; their `run` ignores
cancel and reports no progress, since they are one step. `JobSlot.hold`,
`_held` and the `exclusive` flag are removed. The busy rule is the slot's
own: `start` and `require_idle` refuse while a job is active. Direct
actions never touch the slot.

### 7. Package layout

```
core/actions/
  __init__.py      public names
  README.md        design rules
  _base.py         ActionPlan, Question, PlannedAction, Ran, fingerprint
  _moves.py        shared move helper and MoveReport (tidy, archive, publish)
  tidy.py  archive.py  publish.py  batch.py (rename, new batch)
  apps.py          open, cull, edit: plain functions
```

Tests mirror it under `tests/core/actions/`, one file per module.

### 8. The CLI

- **Preview:** `cli/_app.py` calls `action_prepare_<name>` and prints
  `plan.preview`, each question with its choices, the fingerprint and the
  `--confirm` command.
- **Run:** `--apply` prepares and executes at once; `--confirm FP`
  prepares, compares with `FP` and executes. Each command maps its flags
  to its action's answers, e.g. `publish --on-conflict replace` →
  `{"existing": "replace"}`.
- **JSON:** a plan is `{action, node_id, inputs, preview, questions,
  fingerprint}`; a result is `{outcome, message, details, node_id,
  library_refreshed, report}`.

## Risks / Trade-offs

- [Every action and most tests are rewritten] → Do it one action at a
  time; each keeps its behaviour tests (`tests/core/actions/`) green
  before the next.
- [The CLI's JSON changes shape] → Marked experimental; `DEV.md` updated.
- [Questions are matched to CLI flags by hand in each command] →
  Accepted: a handful of commands, and the GUI will render questions
  generically from `Question`.
- [Rename and new batch write a job log for one step] → Accepted by
  decision; it is cheap and keeps one way to run planned actions.
- [Answers checked inside the job mean a bad answer starts a job that
  refuses at once] → Accepted; the refusal is immediate and logged.

## Migration Plan

One change on `dev-core-split`; no data or settings migrate. Rollback is
reverting the change.
