# Proposal

## Why

The darkroom tree is the core's main read model, but today it is a mutable
`DarkroomNode` graph handed to clients as shared state. Clients address nodes
by object identity, must resolve "which node to rescan" themselves, and
derive which actions a node offers from rules that lived in the parked GUI.
The read model also imports its untidy check from the actions module. This
is the second Phase 1 step of the `dev-core-split` roadmap: the core must
own the tree index, with a stable, ergonomic interface for the CLI now and
the rebuilt GUI later.

## What Changes

- New `library` package for the library domain: layout rules, file kinds
  and the untidy check, the tree model and the scan functions. It holds no
  shared state; the engine holds the tree instance.
- Nodes are addressed by a stable id: the node's path relative to the
  darkroom. Clients never receive the index's internal objects.
- Reading a node returns a frozen, nested view of its subtree: kind, own
  and total file counts, own and rolled-up issues, and an **actions
  manifest**: the actions that apply to a node of that kind. The manifest
  ignores configuration; whether to show an action is the client's call.
- Engine API with domain prefixes:
  - `library_scanning`, `library_scanned`, `library_scan()`,
    `library_refresh(id)` (returns the id actually rescanned, the nearest
    indexed ancestor when needed), `library_node(id)`,
    `library_devices()`.
  - `action_*` factories and `action_execute(action, plan)`. After an
    action runs, the engine refreshes the part of the tree it affected and
    reports the refreshed id in the result.
  - `config_get`, `config_set`, `config_issues`, `config_save`. The
    user configuration service becomes private to the engine.
- A busy engine (scanning or running an action) refuses configuration
  edits and further work with a typed `EngineBusyError`.
- Changing the darkroom root drops the scanned tree; clients scan again.
- **BREAKING** (internal API): `engine.tree`, `engine.scanning`,
  `rescan()`, `rescan_subtree(node)`, `list_devices()`, the
  `*_action` factories and public `engine.user_config` are replaced.
  `scan.py`, `models.py`, `media.py` and `library.py` move into the
  `library` package.

Non-goals: change notifications to clients (open roadmap question), jobs and
progress, a database index or a storage interface for it, a core action
for opening a folder in the file manager (the manifest lists `open`, the
client opens it), action availability that depends on configuration or on
target folders, and adapting the parked GUI.

## Capabilities

### New Capabilities

- `engine/library-index`: how clients address, read and scan the library
  tree, what a node view contains, and when the tree is dropped.
- `app/node-actions`: which actions each kind of darkroom node offers.

### Modified Capabilities

- `engine/scanning`: a scoped rescan is requested by node id, falls back to
  the nearest indexed ancestor, and follows every executed action.
- `engine/engine-status`: configuration changes go through the engine, and
  a busy engine refuses configuration edits and further work.
- `app/darkroom-tree`: the publish folder of a batch is its own node kind.

## Impact

- Code: new `src/photo_darkroom_manager/library/` package (from
  `library.py`, `models.py`, `media.py`, `scan.py`, and the untidy check
  from `actions.py`); `engine.py` (library state and API, `action_execute`,
  config API, busy guard); `actions.py` (imports from `library`; the
  tidy collection moves out).
- Tests: new contract tests for the library index and node actions;
  `test_scan.py`, `test_manager.py`, `test_engine.py`, `test_models.py`,
  `test_media.py`, the action tests and `conftest.py` move to the new API.
  The library's tests move to `tests/library/`, one file per submodule.
- No new dependencies; configuration file and on-disk layout unchanged.
