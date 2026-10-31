# Roadmap: `dev-core-split`

The direction for this branch: a strong, self-contained core that owns all
darkroom logic, with every frontend (CLI first, GUI later) as a thin client
over one agreed interface. When working on the core, you should not have to
think about the UI; when working on the UI, you should not be able to break
the core.

Phases run roughly in order, but each one ends in a working, tested state.
This is direction, not tickets. Each phase can become an OpenSpec change.

## Guiding principles

- Core knows nothing about frontends: no NiceGUI imports, no UI state.
- One interface for all clients: the CLI and GUI call the same API.
- Core is testable in isolation, so the tests prove behaviour, not the UI.
- Long or risky operations are jobs: observable, cancellable, logged.
- The GUI keeps its current look; only its wiring changes.

## Phase 0: Safety net

- [ ] Lock in current behaviour before moving code
  - [ ] Behaviour tests for scan, path resolution and each action (create
        batch, rename, publish, archive) against today's code
  - [ ] Hint: test via public functions, so the tests survive the move
- [ ] Map the current coupling
  - [ ] Where `gui/` reaches into `actions.py`, `manager.py`, `scan.py`
  - [ ] Where core code assumes a UI (callbacks, notifications, state)

## Phase 1: Design the core boundary

- [ ] Agree the package layout
  - [ ] Hint: `core/` (domain + services), `cli/`, `gui/`; core never
        imports from `cli/` or `gui/`
  - [ ] Enforce the rule automatically (a test or `import-linter` contract)
- [ ] Design the frontend–backend interface
  - [ ] Commands: one entry point per operation (scan, plan, apply action)
  - [ ] Queries: read models for the tree, statistics, settings
  - [ ] Results: plain data objects (dataclasses / pydantic), no UI types
  - [ ] Errors: a small, typed exception hierarchy that clients can map
  - [ ] Hint: consider "plan, then apply" for file actions, so any client
        can preview changes (dry run) before anything touches disk
- [ ] Decide how the core reports progress and events
  - [ ] Hint: an event/callback protocol the core emits into, which the
        CLI prints and the GUI renders
- [ ] Write it down as specs (`openspec/specs/engine/`) before coding

## Phase 2: Core first, CLI as the only interface

- [ ] Park the GUI
  - [ ] Leave `gui/` in place but unsupported on this branch; it may break
  - [ ] Hint: keep it importable, or exclude it from CI, so it doesn't
        block core work
- [ ] Move and reshape the logic into `core/`
  - [ ] Split `actions.py` into one module per operation
  - [ ] Turn `DarkroomManager` into the core facade behind the interface
  - [ ] Settings, paths, scanning, models move unchanged, then get cleaned
- [ ] Build the CLI on the interface only
  - [ ] Commands mirror core operations, e.g. `dr-mng scan`,
        `dr-mng batch create`, `dr-mng publish --dry-run`
  - [ ] Hint: `typer` or `argparse`; output via a renderer that can do
        human text and `--json`
  - [ ] Phase 0 tests now run against the core API and stay green

## Phase 3: Jobs backend

- [ ] Model long-running work as jobs
  - [ ] A job has an id, state (queued, running, done, failed, cancelled),
        progress and a log
  - [ ] Actions and scans run as jobs; the CLI can run them in the
        foreground and wait
- [ ] Choose the execution model
  - [ ] Hint: start in-process (thread or asyncio worker), behind an
        interface, so it can move to a separate process later
  - [ ] Decide whether job history persists (e.g. SQLite) or stays in memory
- [ ] Safety for file operations
  - [ ] Hint: journal the planned moves so a failed job can report exactly
        what was done and, ideally, roll back

## Phase 4: Bring the GUI back

- [ ] Rewire the GUI as a client of the core interface
  - [ ] Same look and layout as today; no direct calls into core internals
  - [ ] Long actions go through jobs: progress, cancel, error display
- [ ] Decide how the GUI talks to the core
  - [ ] Hint: in-process calls first; a local HTTP/WebSocket API only if a
        separate backend process becomes worth it
- [ ] Feature parity check against `dev` (and the user-interface specs)

## Phase 5: Land it

- [ ] Final sync of `dev`, full test run, manual smoke test of CLI and GUI
- [ ] Update README, DEV.md, AGENTS.md and the specs to the new layout
- [ ] Merge `dev-core-split` into `dev`, release as a major version, delete
      the branch

## Open questions

- Should the CLI and GUI share one process model, or should the core run as
  a local service both connect to?
- How much of "plan, then apply" do we want: dry run only, or reviewable
  plans the user approves in the GUI?
- Do jobs need to survive an app restart?
- Package split: one package with extras (`[gui]`, `[cli]`) or several?

## Next actionable step

Phase 0: write the behaviour tests and the coupling map. They are cheap,
they make every later step safe, and the coupling map answers most of the
Phase 1 interface questions.
