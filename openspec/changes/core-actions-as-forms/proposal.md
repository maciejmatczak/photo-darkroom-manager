# Proposal

## Why

Actions were meant as plain operations on a darkroom node, but they grew
into one framework that every action must fit: shared steps, conflicts and
policies, flags that tell the engine how to run them, three ways to run a
plan, and a lock that reaches from non-job actions into the job executor.
Each new heavy feature leaked into all actions. This change separates what
is truly shared from what belongs to one action, on top of the job work of
`core-jobs-framework`.

## What Changes

- Open, cull and edit become direct engine functions on a node: they run
  at once and return their result, with no plan, confirmation or job
- Rename, new batch, tidy, archive and publish are planned actions that
  work like a web form:
  - prepare: one explicit engine call per action with its own inputs
    (`action_prepare_rename(node_id, date=..., title=...)`), returning a
    plan
  - the plan carries which action and node, the inputs, a plain-text
    preview, the action's own questions for the user and a fingerprint
  - execute: one engine call, `action_execute(plan, answers)`; the engine
    prepares again and refuses a plan whose fingerprint changed
  - the action checks the answers itself; the shared part carries
    questions and answers without looking inside
- Every planned action runs as a job, rename and new batch included, so
  they get a job log too
- The engine is busy exactly while a job runs: the one-job rule is the
  only lock; the slot's hold and the `exclusive` flag are removed
- **BREAKING**: steps (`Move`, `MakeDir`, `Rename`, `OpenFolder`,
  `Launch`), conflicts and conflict policies are no longer part of the
  shared plan or result; an action that uses them keeps them private
- **BREAKING**: a plan's JSON shows the preview text and questions instead
  of a list of steps and conflicts; results drop the per-step lists
- **BREAKING**: `action_apply`, `action_start` and the `action_<name>`
  factories are replaced by the `action_prepare_<name>` calls,
  `action_execute` and the direct functions
- The CLI's commands, flags and exit codes stay as they are; each command
  maps its flags (e.g. `--on-conflict replace`) to its action's answers
- The actions module becomes a package with a README of its design rules

## Capabilities

### New Capabilities

- `engine/planned-actions`: preparing a planned action into a plan with a
  preview, questions and a fingerprint; executing a plan with the user's
  answers as a job; refusing stale plans and invalid answers
- `engine/actions`: what every action on a node shares (addressing a node
  by id, the kind guard, creating a missing node, outcomes, the node
  afterwards) and direct actions running at once; replaces
  `engine/action-requests`
- `app/action-open-ext-app`: cull and edit open a folder in an external
  app, and when that is refused or fails
- `app/action-open-folder`: opening a node's folder; replaces
  `app/action-open`, renamed next to `app/action-open-ext-app`
- `app/action-new-batch`: creating a new batch, under the action's name;
  replaces `app/action-create-batch`, with its refusals stated once

### Retired Capabilities

- `engine/action-requests`: requests are no longer a concept; its shared
  rules move to `engine/actions`, its plan rules to
  `engine/planned-actions`, and its steps, conflicts and policies are
  dropped
- `app/action-create-batch`: renamed to `app/action-new-batch`
- `app/action-open`: renamed to `app/action-open-folder`

### Modified Capabilities

- `engine/jobs`: rename and new batch run as jobs; what runs as a job is
  every planned action plus scans and refreshes
- `engine/engine-status`: the busy rule is only "a job is running"; rename
  and new batch are refused as busy because they start a job
- `app/command-line`: a planned action's preview prints its preview text
  and questions instead of its steps and conflicts
- `app/file-moves`: reporting moved, failed, skipped and undone files
  moves here from the generic result; replacing depends on the user's
  answer, not a policy
- `app/action-archive`: the overwrite rule lives in one requirement;
  emptied folders are removed
- `app/action-publish`: the replace rule lives in one requirement; a
  missing, nested or empty `PUBLISH/` is covered
- `app/node-actions`: whether an action can run is decided when it is
  requested, since direct actions are never prepared

## Impact

- Code: `core/actions/` (package, README, generic plan, per-action
  questions and answers), `core/jobs.py` (hold removed), `core/engine.py`
  (direct functions, `action_prepare_<name>`, `action_execute`, one busy
  rule), `cli/_app.py` and `cli/_render.py` (flags to answers, preview
  text)
- Tests: action, engine and CLI tests move to the new calls and shapes
- Docs: `DEV.md` (jobs and JSON sections), `docs/core-split/ROADMAP.md`
  (Phase 4)
