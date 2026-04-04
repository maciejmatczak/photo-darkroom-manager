---
name: DarkroomUI Class Refactor
overview: Refactor `layout.py` and `gui_app.py` to eliminate the `manager`/`rebuild_fn` parameter threading by encapsulating all GUI state in a `DarkroomUI` class, using `@ui.refreshable_method` for the tree.
todos:
  - id: refactor-layout
    content: "Rewrite layout.py: remove build_ui and module globals, implement DarkroomUI class with all instance methods and @ui.refreshable_method render_tree"
    status: completed
  - id: update-gui-app
    content: Update gui_app.py import and call site to use DarkroomUI(manager).build()
    status: completed
  - id: lint-format
    content: Run ruff format and ruff check, fix any issues
    status: completed
isProject: false
---

# DarkroomUI Class Refactor

Replace the current free-function layout with a `DarkroomUI` class. `manager` becomes `self.manager`, and the `rebuild_fn` closure is replaced by `self.render_tree.refresh()` (NiceGUI's `@ui.refreshable_method`).

## Current call-chain (the problem)

```mermaid
flowchart TD
    build_ui["build_ui(manager)"]
    rebuild_tree["rebuild_tree() closure"]
    render_node["_render_node(node, manager, rebuild_fn)"]
    action_btns["_action_buttons(node, manager, rebuild_fn)"]
    run_action["_run_action(action, manager, rebuild_fn, label)"]
    handle_result["_handle_execute_result(result, manager, rebuild_fn)"]
    rescan_rebuild["_rescan_and_rebuild(manager, rebuild_fn)"]

    build_ui --> rebuild_tree
    build_ui --> render_node
    render_node --> action_btns
    action_btns --> run_action
    run_action --> handle_result
    handle_result --> rescan_rebuild
    rescan_rebuild -->|"rebuild_fn()"| rebuild_tree
```

## Target structure

```mermaid
flowchart TD
    index["index() in gui_app.py"]
    DarkroomUI["DarkroomUI(manager)"]
    build["self.build()"]
    render_tree["@refreshable_method self.render_tree()"]
    render_node["self._render_node(node, depth)"]
    action_btns["self._action_buttons(node)"]
    run_action["self.run_action(action, label)"]
    rescan_refresh["self.rescan_and_refresh()"]

    index --> DarkroomUI
    DarkroomUI --> build
    build --> render_tree
    render_tree --> render_node
    render_node --> action_btns
    action_btns -->|"self.run_action(...)"| run_action
    run_action -->|"self.rescan_and_refresh()"| rescan_refresh
    rescan_refresh -->|"self.render_tree.refresh()"| render_tree
```

## Changes

### [`src/photo_darkroom_manager/gui/layout.py`](src/photo_darkroom_manager/gui/layout.py)

- Remove module-level mutable globals `_all_expansions` and `_expanded_paths`; move them to `self._all_expansions` and `self._expanded_paths` on `DarkroomUI`
- Keep pure free functions as-is: `_open_directory`, `_depth_class`, `_tree_btn`, `_present_action_details`
- Remove `build_ui(manager)` function entirely
- Create `DarkroomUI` class with:
  - `__init__(self, manager: DarkroomManager)` — stores `self.manager`, `self._all_expansions`, `self._expanded_paths`
  - `@ui.refreshable_method render_tree(self)` — replaces the `rebuild_tree` closure; clears `_all_expansions`, renders all year nodes
  - `async rescan_and_refresh(self)` — replaces `_rescan_and_rebuild`; calls `run.io_bound(self.manager.rescan)` then `self.render_tree.refresh()`
  - `async run_action(self, action, label)` — replaces `_run_action`; no `manager`/`rebuild_fn` params, calls `self.rescan_and_refresh()` internally
  - `async _handle_execute_result(self, result)` — replaces the free-function version
  - `_render_node(self, node, depth)` — replaces free function; calls `self._action_buttons(node)`
  - `_action_buttons(self, node)` — replaces free function; calls `self.run_action(...)`
  - `_show_rename_dialog(self, node)` — instance method
  - `_show_new_album_dialog(self)` — instance method
  - `build(self)` — builds header + column, calls `self.render_tree()`, then does initial `manager.rescan()` + `self.render_tree.refresh()`

### [`src/photo_darkroom_manager/gui/gui_app.py`](src/photo_darkroom_manager/gui/gui_app.py)

- Replace `from photo_darkroom_manager.gui.layout import build_ui` with `from photo_darkroom_manager.gui.layout import DarkroomUI`
- Change `build_ui(DarkroomManager(settings))` to `DarkroomUI(DarkroomManager(settings)).build()`
