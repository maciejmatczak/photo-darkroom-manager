# Actions

An action is something done to a node of the darkroom tree: open a batch,
rename it, archive it. That is all the word means.

## What this package is

- **A collection of actions**, each unique
  - Every action has its own types and its own path of execution
  - Like the web: one form class per URL, not every form posted to one
    URL
- **On a shared foundation** (`_base.py`)
  - Every action has a result; some have a plan; some run as a job
  - The foundation gives the types and helpers for that, and no common
    interface to execute an action

## Two kinds of action

- **Direct**: open, cull, edit (`apps.py`)
  - Run at once and return their own result
  - No plan, no confirmation, no job
- **Planned**: rename, new batch, tidy, archive, publish (one module each)
  - The user sees what will happen and decides before anything changes
  - Always run as a job

## Design rules

- **Each action has its own types**
  - Its own result, subclassing `ActionResult`; a planned action also its
    own plan, subclassing `ActionPlan`
  - No shared shape that every action must squeeze into
- **Each action has its own path**
  - A planned action module has its own `prepare` and `run`, called as
    `archive.prepare` and `archive.run`
  - The engine has its own call for each: `action_prepare_archive`, then
    `action_archive`
- **The plan is the preview**
  - Its fields say what will happen, in the action's own terms
  - There is no generic preview text; each frontend shows each plan type
    its own way, like a template per form
  - Nothing to do is still a plan, one that says so
  - A plan is plain data: the inputs to prepare it again, and the work
    the run will do in a private field
- **Refusing is raising**
  - An action that cannot plan or run as asked raises
    `ActionRefusedError`; it never returns a "refused" value
  - A stale plan or a bad answer is refused the same way, before any job
    starts
  - So a result only ever ends `ok`, `failed` or `cancelled`
- **An action owns its logic**
  - How it works, how it loops, where it can stop: all its own
  - Shared code is plain helpers an action chooses to call
- **An action does not know the engine**
  - It gets its inputs, the user's answers and its job, and nothing more
  - It never names nodes or says what to rescan
- **The engine decides how, when and what follows**
  - That a planned action runs as a job, one job at a time
  - What to rescan and where the node is afterwards, in each call
  - No flags on actions describe how the engine runs them
- **No hooks between the engine and actions**
  - An action reports to its job; the engine reads the job

## How a planned action flows

Archive as the example:

1. **Prepare**: `engine.action_prepare_archive(node_id)`
   - Calls `archive.prepare(...)`, returns an `ArchivePlan`, or raises
     `ActionRefusedError`
2. **Show**: the frontend shows the plan and asks its questions
3. **Execute**: `engine.action_archive(plan, answers)`
   - **Check**, before any job: the engine prepares again, then
     `require_unchanged_plan` and `check_answers`
   - Then it starts the job and returns it
4. **Run**, inside the job: `archive.run(plan, answers, job)` does the
   work and reports progress through the job
5. **Result**: an `ArchiveResult`; the engine adds the node afterwards and
   what it rescanned, without touching the result

## The foundation

| Name | What it is |
| --- | --- |
| `ActionResult` | `outcome` (`ok`, `failed`, `cancelled`) and `message` |
| `ActionPlan` | `questions`, `fingerprint`, `nothing_to_do` |
| `Question` | One form field: `text`, `choices`, `default` |
| `Answers` | Posted form data: question name to choice |
| `ActionRefusedError` | Cannot plan or run as asked: `message`, `details` |
| `fingerprint()` | Hash an action's work the same way everywhere |
| `require_unchanged_plan()` | Refuse a plan that differs from a fresh one |
| `check_answers()` | Apply the form rules; fill in defaults |

Everything else is on each action's own types.
