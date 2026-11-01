# Roadmap: `dev-core-split`

The direction for this branch: a strong, self-contained core that owns all
darkroom logic and state, with every frontend (CLI first, GUI later) as a thin
client over it. When working on the core, you should not have to think about
the UI; when working on the UI, you should not be able to break the core.

This is a direction, not a design. Near phases are concrete; later phases
only state intent and get detailed when we reach them. A drastic change in one
phase should not need a rewrite of the others. Each phase can become an
OpenSpec change, and the design lives there, not here.

Each item states the outcome that makes it done; a phase is done when all
its items are.

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

- [x] A written map of what the frontend expects from the core today
      ([frontend-coupling.md](frontend-coupling.md))
  - [x] Covers settings and startup, the tree read model, refresh and the
        action protocol
  - [x] Lists the business rules living in `gui/` (per-node action
        availability, path targets, form validation, opening folders)
  - [x] Lists core assumptions about the GUI (in-place node identity on
        rescan)
- [x] Every test is marked `contract` or `internal`, and each marker can run
      on its own (`pytest -m contract` / `-m internal`)
  - [x] `contract`: user-visible outcomes we keep (files moved, conflicts
        refused, stats and issues reported, settings validated)
  - [x] `internal`: tests of private helpers or behaviour we plan to change
        (see `IMPROVE_ARCHITECTURE.md`)
- [x] Cheap contract gaps are filled: tests assert outcomes on disk and
      result kinds, not preview strings or object identity, and do not
      freeze behaviour we know is wrong
  - [x] Action tests use public `prepare()` / `execute()`; file-safety
        tests live in `tests/test_file_safety.py`

## Phase 1: Core boundary and state

- [x] The core owns settings (`core-user-config`)
  - Loading never crashes the app: each setting has a value and a validity
    state the frontend can show and fix
  - Updates stay in memory until saved to file explicitly
- [x] The core owns the tree index (`core-library-index`)
  - An in-memory graph of devices, years, batches, folders, files and stats
  - Each node carries its manifest: issues and available actions
  - Any node and its subtree can be refreshed on demand, not only the root
  - A storage seam lets a database index replace it later: the private map
    of node facts in `LibraryTree`; an interface waits for a second
    implementation
- [x] Agreed how the client learns that the library changed; it is built in
      Phase 3
  - One client per core: the core is a library in the client's process,
    not a service
  - The engine tells its client which part of the library changed,
    whatever caused it; the client re-reads that part and re-renders
- [ ] The core never imports a frontend, and a check fails the build if it
      does

## Phase 2: CLI as the only interface

- [x] The GUI is parked: moved unchanged to `legacy-gui/` as reference, not
      kept working
- [x] The old manager and scan code live in the core: the `Engine` and the
      `library` package; actions are created and run through the engine
- [ ] An experimental CLI drives the core API end to end (configure, scan,
      inspect a node, run an action) and is usable by an agent as a tool
      surface

## Phase 3: Jobs and safe file operations

- [ ] Research how DAM tools preview and confirm bulk file operations, and
      write down the approach we pick
- [ ] Propose the jobs change in OpenSpec, deciding whether jobs survive an
      app restart and how the client is told what changed
- Every action runs as a job: the client sees its progress, result and
  report, and never freezes while it runs
- The client is told which part of the library changed, after its own
  calls and after background work, and re-renders only that part; the
  shape and delivery of that notice are designed here
  - Later: several processes (GUI, an agent's CLI) over one database
    index, where the engine also notices changes made by others
- "Plan, then apply" is settled, after researching how DAM tools preview
  and confirm bulk file operations
- A failed job reports exactly what was done; rollback where feasible

## Phase 4: Bring the GUI back

- [ ] Compare the parked GUI with the core API, using
      [frontend-coupling.md](frontend-coupling.md), and list what the core
      does not offer yet
- [ ] Propose the GUI change in OpenSpec, built from that list
- The GUI is a client of core state and jobs and looks as it does today
- It stays in sync with the core through the change notice from Phase 3

## Phase 5: Land it

- [ ] Decide the package split (one package with extras, or several) and
      write down why
- [ ] Write a release checklist: smoke run steps, and the docs and specs to
      update
- `dev` is merged in, the full test suite and a smoke run pass, and docs and
  specs match the code
- `dev-core-split` is merged into `dev` as a major release and deleted

## Later, not on this branch

- Persistent index (database) so startup does not rescan everything

## Open questions

- Do jobs survive an app restart?
- Package split: one package with extras, or several?

## Next actionable step

Close Phase 1 with the import check, then start the Phase 2 CLI over the
engine's API.
