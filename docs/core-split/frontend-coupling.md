# Frontend–core coupling map (Phase 0)

What the GUI (`src/photo_darkroom_manager/gui/`) expects from the core today,
as of commit `e8cae90` on `dev-core-split`. This is a snapshot used as input
for Phase 1 of [ROADMAP.md](ROADMAP.md), not a spec. Each finding ends
with a direction tag:

- **keep**: a contract worth preserving in the new core
- **move**: logic that belongs in the core, not the GUI
- **change**: behaviour we intend to redesign

## Import surface

The GUI imports these core names:

| GUI module | Core imports |
| --- | --- |
| `gui_app.py` | `DarkroomManager`, `Settings`, `load_settings`, `save_settings`, `configure_logging` |
| `layout.py` | `Action`, `ActionPlan`, `ActionResult`, `ExecutionResult`, `PrepareError`, `DarkroomManager`, `validate_device_name`, `DarkroomNode` |
| `node.py` | `BatchFolderName`, `format_validation_error`, `DarkroomNode`, `PUBLISH_FOLDER` |
| `widgets.py` | `DarkroomNode` |

The dependency is one way: `actions.py`, `manager.py`, `scan.py` and the
other core modules import nothing from `gui/` and nothing from NiceGUI.

## 1. Settings and startup

- `gui_app._try_load_settings` wraps `load_settings()` in
  `except Exception: return None`. A missing file, broken YAML and one invalid
  field all look the same: the "not configured" page. **change**
- `Settings` is all-or-nothing pydantic validation: one bad path (e.g. an
  unplugged drive) rejects the whole config, and the reason is discarded.
  **change**
- The settings page then starts empty (`_try_load_settings()` returns
  `None`), so the user retypes every value instead of fixing the bad one.
  **change**
- The GUI builds `Settings(...)` itself from form fields, calls
  `save_settings` and `configure_logging` directly. Validation errors are
  shown as `str(e)`. **move**
- `DarkroomManager(settings)` is constructed per page load; any exception
  during the first build becomes a generic "configuration error" page.
  **change**

Wanted instead: the core loads settings without crashing, reports validity
per setting, accepts updates in memory and saves them explicitly.

Done in `core-user-config`: settings and startup are core-owned.
`Engine()` loads `engine.user_config` tolerantly (problems per key), exposes
config-backed properties and a derived `status` / `status_detail`, and owns
the runtime log level. The GUI code above is parked in `legacy-gui/`.

## 2. Tree read model

- The GUI renders `DarkroomNode` directly and reads `path`, `name`,
  `node_type`, `stats.{image,video,other_file}_count`, `issues` and
  `children`. **keep** (as data; the type will change)
- It reads mutable `manager.tree` as shared state. **change**
- Issues are plain strings; the GUI only knows `"untidy"` (Tidy button
  turns red). **keep**, as a typed part of the node manifest
- `node.path.is_dir()` and `showroom_target.is_dir()` /
  `archive_target.is_dir()` are filesystem checks done in the GUI while
  rendering buttons. **move**

## 3. Refresh

- Full: `manager.rescan()` on a worker thread, then the GUI clears its
  registry and rebuilds the whole tree.
- Scoped: an action result carries `rescan_node_path`. The GUI looks it up
  in its registry `{path: DarkroomNodeUI}`, walks up parents until it finds
  a registered node (e.g. a new year folder has none), and falls back to a
  full rescan. Then it calls `manager.rescan_subtree(node)`. **move** (the
  nearest-ancestor resolution belongs to the core tree)
- `scan.rescan_subtree` mutates the node in place so the GUI widget bound to
  it stays valid ("node identity preserved"). The core thus depends on GUI
  object identity. **change**
- Expansion state inside a rescanned subtree is lost (children rebuilt).
  Note for Phase 4.

## 4. Action protocol

- The manager is an action factory: `tidy_action`, `archive_action`,
  `publish_action`, `rename_action`, `new_batch_action`,
  `open_external_app_action`. **keep** (as the initial API list)
- `layout.run_action` drives a two-step protocol, each step on a worker
  thread (`run.io_bound`):
  - `prepare()` returns `PrepareError` (show message and details),
    `None` (execute at once), or an `ActionPlan` (show
    `plan.preview_text()`, wait for Confirm)
  - `execute(plan)` returns `ExecutionResult` with `success`, `message`,
    `details`, `rescan_node_path`
- Impact preview before touching files: **keep** the intent; the
  mechanism is open (see ROADMAP Phase 3).
- The preview is a preformatted string, so a client cannot render counts or
  moves its own way. **change**
- `None` as "no confirmation needed" is overloaded (see
  `IMPROVE_ARCHITECTURE.md` #3). **change**
- Execution blocks the action flow until done; there is no progress,
  cancel or job history. **change** (jobs)

## 5. Business rules living in the GUI

All in `gui/node.py` `_action_buttons` unless noted. **move** for all.

- Action availability per node type:
  - device: Open, New Batch
  - year: Open only
  - batch: Rename, Tidy, Cull, Edit, Publish, Archive
  - subfolder: Tidy, Cull, Edit, Archive
  - the `PUBLISH_FOLDER` subfolder: Open only
- Cull / Edit exist only when `settings.cull_command` /
  `settings.edit_command` is set.
- Showroom and archive targets via `mgr.showroom_path(darkroom_path=...)`
  and `mgr.archive_path(darkroom_path=...)` (the fake sum type,
  `IMPROVE_ARCHITECTURE.md` #2).
- New batch form (`layout.show_new_batch_dialog`): `validate_device_name`,
  "year and month required", device list from `manager.list_devices()`.
- Rename form (`node._show_rename_dialog`): parses defaults with
  `BatchFolderName.from_str`, takes the default year from
  `node.path.parent.name`, validates with `BatchFolderName`, and skips the
  action when the name is unchanged.
- Opening a folder in the file manager (`widgets.open_directory`:
  `os.startfile` / `open` / `xdg-open`) lives in the GUI, while opening an
  external app is a core action. Two paths for the same kind of thing.

## 6. What the core does not need from the GUI

No callbacks, notifications or UI state flow into the core. Apart from
in-place node identity (section 3), the core is already UI-free, so Phase 1
is mostly about moving rules and state in, not cutting dependencies out.

## Summary for Phase 1

- Settings: per-setting validity, no crash on load, explicit save
- Tree: core-owned, immutable or versioned snapshots, node manifest with
  issues, available actions and target paths
- Refresh: core resolves "what changed", for any node
- Actions: structured previews, clear "needs confirmation" flag, jobs
