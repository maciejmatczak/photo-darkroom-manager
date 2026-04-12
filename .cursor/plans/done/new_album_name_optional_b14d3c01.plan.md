---
name: New album name Optional
overview: "Widen `NewAlbumAction` / `DarkroomManager.new_album_action` to accept `name: str | None`, normalize in `_execute` so `None` matches current `\"\"` folder naming, update the new-album dialog to pass `None` for a blank optional name, and extend tests accordingly."
todos:
  - id: actions-execute
    content: "Update NewAlbumAction: `name: str | None`, normalize in `_execute` with `(name or \"\").strip()`"
    status: completed
  - id: manager-gui
    content: Widen `DarkroomManager.new_album_action`; pass `None` for blank name in `_show_new_album_dialog`
    status: completed
  - id: tests-lint
    content: Adjust/add tests for `None`; run ruff + ty
    status: completed
isProject: false
---

# Optional album name (`str | None`) for new album

## Current behavior

- [`NewAlbumAction`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\actions.py) stores `name: str` and in `_execute` builds the folder name with:

```478:478:d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\actions.py
        album_folder_name = f"{date_part} {name.strip()}" if name.strip() else date_part
```

  Empty string yields **date-only** folder names (e.g. `2026-06`).

- [`_show_new_album_dialog`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\gui\layout.py) sets `n = name_input.value.strip()`, so a blank field becomes `""`, not `None`.

## Changes

1. **Types and constructor** — In [`actions.py`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\actions.py), change `NewAlbumAction.__init__` parameter `name` from `str` to `str | None`. Store it as today (or keep `str | None` on the private field).

2. **`_execute` normalization** — Replace direct `name.strip()` with logic equivalent to **empty / missing title**:
   - Use something like `stripped = (name or "").strip()` (or `"" if name is None else name.strip()`), then keep the same branch: `album_folder_name = f"{date_part} {stripped}" if stripped else date_part`.
   - This makes `None` and `""` (and whitespace-only) behave like today’s `""`.

3. **Factory** — In [`manager.py`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\manager.py), update `new_album_action(..., name: str | None)` to match.

4. **GUI** — In [`layout.py`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\gui\layout.py) inside `do_create`, after reading the optional name field: pass `None` when there is no non-whitespace title (e.g. `n = name_input.value.strip() or None` instead of only `.strip()`).

5. **Tests** — In [`tests/actions/test_new_album_rename.py`](d:\workspace\photo-darkroom-manager\tests\actions\test_new_album_rename.py):
   - Either add a small test that `NewAlbumAction(..., None)` produces the same path as `""` for the “no title” case, or change `test_new_album_execute_without_name_uses_date_only` to use `None` and assert the same expectations (folder `2026-06`, etc.).
   - [`tests/test_manager.py`](d:\workspace\photo-darkroom-manager\tests\manager.py) can keep passing a string for `name`; no change required unless you want an explicit `None` case there.

6. **Quality checks** — Per project rules: `uv run ruff format`, `uv run ruff check --fix`, `uv run ty check`.

## Scope / non-goals

- **RenameAction** and shared validation are listed separately in [TODO.md](d:\workspace\photo-darkroom-manager\TODO.md) line 4; this task does not touch them.

## Call sites

Grep shows no other production callers beyond `manager.new_album_action` and tests; [`layout.py`](d:\workspace\photo-darkroom-manager\src\photo_darkroom_manager\gui\layout.py) is the only GUI caller to update.
