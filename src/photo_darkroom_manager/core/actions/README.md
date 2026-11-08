# Actions

An action is something done to a node of the darkroom tree: open a batch,
rename it, archive it. That is all the word means.

> The code here still predates some of these rules; the OpenSpec change
> `core-actions-as-forms` brings it in line.

## Two kinds of action

- **Direct**: open, cull, edit
  - Plain engine functions on a node; they run at once and return a result
  - No plan, no confirmation, no job
- **Planned**: rename, new batch, tidy, archive, publish
  - The user sees what will happen and decides before anything changes
  - Always run as a job

## Design rules

- **An action owns its logic**
  - How it works, how it loops, where it can stop: all its own
  - Shared code is plain helpers an action chooses to call
- **An action does not know the engine**
  - It gets what it needs (its inputs, the user's answers, its job) and
    nothing more
- **Only what is truly common is shared, and it stays generic**
  - Planned actions work like a web form: get the form, post it, validate
  - Plus one thing of our own: a posted form runs as a job
  - Nothing about files, conflicts or policies belongs to the shared part
- **Custom data passes through**
  - What an action asks and what the user answers mean something only to
    that action and to the screen that shows it
  - The shared part carries them without looking inside
- **A preview is plain text**
  - It tells the user what will happen; it is not a list of steps to run
- **The engine decides how and when**
  - Which actions are direct and which are planned
  - That a planned action runs as a job, one job at a time
  - No flags on actions describe how the engine runs them
- **No hooks between the engine and actions**
  - An action reports to its job; the engine reads the job

## How a planned action flows

1. **Prepare**: the engine asks the action for a plan
   - One explicit call per action, with its own inputs:
     `action_prepare_rename(node_id, date=..., title=...)`
2. **Show**: the frontend shows the preview and asks the plan's questions
3. **Execute**: `action_execute(plan, answers)`
   - The engine prepares again; if the plan changed, it is refused
   - Otherwise it starts the job
4. **Run**: inside the job, the action checks the answers, does its work
   and reports progress and its steps through the job
5. **Result**: the job ends with what the action did

What a plan carries, the generic part only:

| Field | Meaning |
| --- | --- |
| `action`, `node_id` | Which action, on which node |
| `inputs` | What prepare was given |
| `preview` | What will happen, as text |
| `questions` | What the user must decide; the action's own format |
| `fingerprint` | Same fingerprint, same plan |
