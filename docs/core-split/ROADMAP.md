# Roadmap: `dev-core-split`

The direction for this branch: a strong, self-contained core that owns all
darkroom logic and state, with every frontend (CLI first, GUI later) as a thin
client over it. When working on the core, you should not have to think about
the UI; when working on the UI, you should not be able to break the core.

This is a direction, not a design. Near phases are concrete; later phases
only state intent and get detailed when we reach them. A drastic change in one
phase should not need a rewrite of the others. Each phase can become an
OpenSpec change, and the design lives there, not here.

## Vision

- One core that knows the darkroom
  - Settings, the indexed folder tree with stats, issues and available
    actions, and running jobs, all in one place
  - In memory now, with a storage seam for a database index later
  - Jobs: formalized representation of triggered actions
- Thin clients over it
  - CLI first: experimental access to the core, possibly for agents
  - GUI later: the same look, rendering core state and sending intents
- Trustworthy asset operations, as in a DAM
  - The user's photos and videos are the assets; the folder layout is
    their lifecycle (darkroom → showroom → archive)
  - Every operation previews its impact on assets, runs as an observable
    job, and leaves an audit trail of what moved where
  - No asset is ever lost: conflicts block, failures are reported exactly

## Guiding principles

- The core is the single source of truth: settings, the folder tree, what
  each node allows, and the state of running work.
- Frontends hold no business rules; they render core state and send intents.
- User files are critical: every file operation shows its impact first, runs
  safely, and leaves a clear report.
- Long or risky operations are jobs: observable, never freezing the client.
- The GUI keeps its current look; only its wiring changes.

## Phase 0: Understand and protect what exists

- [x] Map what the frontend expects from the core today
      ([frontend-coupling.md](frontend-coupling.md))
  - [x] Settings and startup, tree read model, refresh, action protocol
  - [x] Business rules living in `gui/` (per-node action availability,
        path targets, form validation, opening folders)
  - [x] Core assumptions about the GUI (in-place node identity on rescan)
  - [x] Hint: write it as a short note next to the specs; it is the input
        for Phase 1
- [x] Classify the existing test suite (`pytest -m contract` / `-m internal`)
  - [x] `contract`: user-visible outcomes we keep (files moved, conflicts
        refused, stats and issues reported, settings validated)
  - [x] `internal`: tests of private helpers or behaviour we plan to change
        (see `IMPROVE_ARCHITECTURE.md`)
  - [x] Hint: pytest markers first, since files mix both; folders only if
        the split stays clean
- [x] Fill contract gaps only where cheap
  - [x] Hint: assert outcomes on disk and result kinds, not preview strings
        or object identity; do not freeze behaviour we know is wrong
  - [x] Action tests use public `prepare()` / `execute()`; file-safety
        tests in `tests/test_file_safety.py`

## Phase 1: Core boundary and state

- [x] Settings owned by the core (`core-user-config`)
  - Load never crashes the app: each setting has a value and a validity
    state the frontend can show and fix
  - Update in memory, save to file explicitly
- [ ] Tree index owned by the core
  - In-memory graph of devices, years, batches, folders, files and stats
  - Each node carries its manifest: issues and available actions
  - Refresh any node and its subtree on demand, not only from the root
  - Behind a storage seam, so a database index can replace it later
- [ ] How clients learn that state changed (open question, decide later)
- [ ] Package layout where the core never imports a frontend, enforced
      by a check

## Phase 2: CLI as the only interface

- [x] Park the GUI: moved unchanged to `legacy-gui/` as reference, not
      kept working
- [ ] Reshape the existing manager, scan and action functions into the core
- [ ] Experimental CLI over the core API, also a candidate tool surface
      for agents

## Phase 3: Jobs and safe file operations

- Every action runs as a job: progress, result, report, no frozen client
- Rethink "plan, then apply": research how DAM tools preview and confirm
  bulk file operations before settling the UX
- File safety: know what was done when a job fails; rollback if feasible

## Phase 4: Bring the GUI back

- GUI as a client of core state and jobs, same look as today
- How it stays in sync with the core tree is decided here

## Phase 5: Land it

- Sync `dev`, full test and smoke run, update docs and specs
- Merge into `dev` as a major release, delete the branch

## Later, not on this branch

- Persistent index (database) so startup does not rescan everything

## Open questions

- Change notification: events, polling, or snapshots with versions?
- One process for core and clients, or a local core service?
- Do jobs survive an app restart?
- Package split: one package with extras, or several?

## Next actionable step

Phase 0: the expectations map and the test classification. Both are cheap,
and together they define what Phase 1 must preserve and what it may change.
