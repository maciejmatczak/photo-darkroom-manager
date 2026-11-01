# Design

## Context

- `scan.py` builds a mutable `DarkroomNode` graph (path, `node_type`,
  stats holding subtree totals only, `local_issues`, `issues`, children,
  parent). `engine.tree` holds it; `engine.scanning` is set during
  `rescan()`.
- `rescan_subtree(node)` rebuilds a node's children in place, keeping the
  object so a GUI widget bound to it stays valid. `reaggregate_ancestors`
  re-reads each ancestor's folder from disk, because nodes do not store
  their direct counts.
- The rule "which child folder is which kind" is written twice: in the
  `_scan_*` functions and again in `rescan_subtree`.
- `scan.py` imports `collect_files_to_tidy` from `actions.py`.
- Actions return `ExecutionResult.rescan_node_path`; clients call
  `prepare()` and `execute()` on the action directly, so the engine never
  sees an action finish.
- Clients use `engine.user_config` directly, so a darkroom change reaches
  nothing else.
- The parked GUI's `_action_buttons` is the reference for which actions a
  row offers (see `docs/core-split/frontend-coupling.md` section 5).

## Goals / Non-Goals

**Goals:**

- The usage this change makes possible:

  ```python
  engine.library_scan()                    # full scan, busy while running
  engine.library_scanning                  # bool, any scan or rescan
  engine.library_scanned                   # bool, a tree is available
  view = engine.library_node("")           # NodeView, nested subtree
  view.kind, view.stats, view.total, view.issues, view.actions
  engine.library_refresh("Camera/2027")    # -> "Camera" (rescanned id)
  engine.library_devices()                 # list[str], fresh from disk

  action = engine.action_tidy(path)
  plan = action.prepare()
  result = engine.action_execute(action, plan)
  result.library_refreshed                 # NodeId | None

  engine.config_get("archive"); engine.config_issues
  engine.config_set("darkroom", p)         # busy -> EngineBusyError;
                                           # new root drops the tree
  engine.config_save()                     # -> Path
  ```

- The library domain is one package with a small public surface; nothing
  in it imports the engine or actions.
- Ancestors are updated after a rescan without disk access.

**Non-Goals:**

- A storage interface (`Protocol`) for a future database. The private map
  of node facts is the seam; the interface is written when a second
  implementation exists.
- Renaming the path helpers (`darkroom_path`, `showroom_path`,
  `archive_path`); they belong to the area-translation question in
  `IMPROVE_ARCHITECTURE.md` #2.
- Making action preparation busy-guarded; preparing reads only.

## Decisions

### The `library` package holds models and functions, not state

```
library/
  __init__.py   public names only
  layout.py     folder constants, child_kind(parent_kind, name),
                BatchFolderName, validate_device_name, DarkroomBatch,
                recognize_darkroom_batch (from library.py, models.py)
  media.py      file kinds, collect_files_to_tidy, is_untidy (from
                media.py and actions.py)
  tree.py       NodeId, NodeKind, NodeIssue, NodeAction, FileCounts,
                NodeView, node_actions(kind), LibraryTree
  _scan.py      scan_subtree(root, node_id, kind) -> node facts
```

`LibraryTree` is a model: the darkroom root plus a private
`dict[NodeId, _Node]`, where `_Node` stores kind, direct counts, own
issues, child ids, and cached totals. Its methods work on its own data:
`view(id)`, `contains(id)`, `nearest(id)` and `replace_subtree(id,
facts)`, which swaps a subtree's entries and recomputes totals and
rolled-up issues up the parent chain from stored facts. The engine creates
it, holds it as `_library`, and owns `scanning` and busy state.

*Alternative:* a `LibraryIndex` service object owning the tree, scanning
flag and refresh. Rejected: shared state belongs on the engine, and a
second stateful object would make the engine a proxy of it.

### Ids are darkroom-relative POSIX strings

`NodeId = str`: `""` for the root, `"Camera/2026/2026-10 Walk"` below it.
Strings serialise as is for the CLI and agents, compare by value, and
survive any rebuild. A node's parent id is its id without the last part,
so `nearest(id)` walks up the string until an id is in the tree.

*Alternative:* public handles (objects or index-like tokens). Rejected:
handles into a mutable tree go stale after a rebuild (Qt needed
`QPersistentModelIndex` for this), need lifetime rules, and a handle with
methods would carry a link back to the engine.

*Trade-off:* a rename changes the id. The rename action already declares
the parent as its impact, so the client replaces the parent's subtree.

### Views are frozen, nested and built on read

`NodeView` is a frozen dataclass: `id`, `name`, `kind`, `stats` (direct),
`total`, `own_issues`, `issues`, `actions: frozenset[NodeAction]`,
`children: tuple[NodeView, ...]`. `library_node(id)` builds it from the
stored facts on each call. Building the whole tree is one pass over the
map; the darkroom has thousands of folders at most.

*Alternative:* snapshots with versions. Rejected: clients would need to
diff snapshots to refresh one subtree.

### The actions manifest depends on kind only

`node_actions(kind) -> frozenset[NodeAction]` is a pure table in
`tree.py`. `NodeAction` (`open`, `new_batch`, `rename`, `tidy`, `cull`,
`edit`, `publish`, `archive`) is library vocabulary: the operations the
library allows on its folders. The actions module and engine map them to
concrete actions; `library` never imports them.

*Alternatives:* a rules table in the engine that also checks
configuration and targets, or `available_for()` on each action class.
Rejected: both mix "applies to this kind" with "can run now", which
`prepare()` already decides, and the second couples the tree to actions.

### `publish` is its own node kind

`child_kind("batch", "PUBLISH")` returns `"publish"`; deeper folders are
`"subfolder"`. Without it the manifest would need the folder name, not
only its kind.

### The engine runs actions and refreshes after them

`action_execute(action, plan)` marks the engine busy, calls
`action.execute(plan)`, and, when the result has `rescan_node_path` and a
tree is scanned, refreshes that id. It returns the result with
`library_refreshed` set through `dataclasses.replace`. The factories get
the `action_` prefix (`action_tidy`, `action_archive`, `action_publish`,
`action_rename`, `action_new_batch`, `action_open_external_app`).

*Alternative:* clients keep calling `action.execute()` and then
`library_refresh`. Rejected: the action knows its impact, and only the
engine can keep the busy state honest.

### One busy guard for scans, actions and configuration edits

A `threading.Lock` protects one `_busy: Literal["scan", "action"] | None`.
`library_scan`, `library_refresh`, `action_execute` and `config_set` enter
through `_begin(reason)`, which raises `EngineBusyError(busy)` when
another operation runs. `library_scanning` is `_busy == "scan"`. Reads
take no lock.

*Alternative:* allow concurrent scans with a counter. Rejected: no client
needs it, and one operation at a time makes configuration edits safe.

### Configuration goes through the engine

`user_config` becomes `_user_config`. The engine adds `config_get`,
`config_issues`, `config_set` and `config_save`, delegating to the
service. `config_set("darkroom", value)` drops `_library` when the
validated darkroom differs from the previous one. Other domains read
`engine.darkroom` and friends, never the service.

### The untidy check moves to `library.media`

`collect_files_to_tidy` moves with its private helper; `TidyAction` and
`_scan` both import it. Resolves `IMPROVE_ARCHITECTURE.md` #1.

## Risks / Trade-offs

- [Building nested views of the whole tree on every read] → one pass over
  an in-memory map; clients read the root once after a scan and then only
  the refreshed ids.
- [`NodeAction.open` has no engine action] → the client opens the folder,
  as the parked GUI does; a core action is a later change.
- [Strict busy guard refuses a second scan request from another client]
  → the error is typed and carries the running operation, so the client
  can wait or tell the user.
- [Large rename of public engine names] → internal API only; the parked
  GUI is reference, and the CLI does not exist yet.

## Migration Plan

Internal API only. Tests move to the new names in the same change. No
on-disk or configuration format changes, so no rollback steps.
