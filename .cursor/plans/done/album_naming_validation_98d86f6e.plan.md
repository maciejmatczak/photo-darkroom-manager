---
name: Album naming validation
overview: Add an `AlbumFolderName` Pydantic model to `models.py` as the single source of truth for album folder naming, fix `DarkroomYearAlbum.validate_album` to delegate to it, give `RenameAction` the same structured API as `NewAlbumAction`, update `DarkroomManager`, upgrade the rename GUI dialog to match new-album, and extend the tests.
todos:
  - id: models-album-folder-name
    content: Add AlbumFolderName Pydantic model (validators, folder_name property, parse classmethod) to models.py; update DarkroomYearAlbum.validate_album to delegate; extend test_models.py
    status: completed
  - id: actions-refactor
    content: Wire NewAlbumAction._execute to AlbumFolderName; restructure RenameAction to (album_path, darkroom_path, year, month, day, name); update test_new_album_rename.py
    status: completed
  - id: manager-gui
    content: Update DarkroomManager.rename_action signature; replace rename dialog with four-field form (prefill via AlbumFolderName.parse + read-only year); update test_manager.py
    status: completed
  - id: qa
    content: Run ruff format, ruff check --fix, ty check, pytest
    status: completed
isProject: false
---

# Album Naming Validation — Full Alignment

## Current gaps

- `DarkroomYearAlbum.validate_album` regex `^\d{4}-(0[1-9]|1[0-2])( .*)?$` rejects valid `YYYY-MM-DD` names produced by `NewAlbumAction`.
- `RenameAction(album_path, new_name: str, darkroom_path)` accepts any free-form string — no month/day structure, no shared validation.
- The rename GUI dialog is a single "Album name" text field vs the four-field new-album dialog.
- `DarkroomManager.rename_action(album_path, new_name: str)` does not mirror `new_album_action(year, month, day, name)`.

## 1. `models.py` — add `AlbumFolderName` + update `DarkroomYearAlbum`

Add a new Pydantic model above `DarkroomYearAlbum`:

```python
class AlbumFolderName(BaseModel):
    year: str
    month: str
    day: str | None = None
    name: str | None = None

    @field_validator("year")   # enforce 4 digits
    @field_validator("month")  # normalize "4" → "04"; enforce 01–12
    @field_validator("day")    # normalize "5" → "05"; enforce 01–31 if present
    @field_validator("name")   # strip; None if empty; reject Windows-forbidden chars (<>:"/\|?* + controls)

    @property
    def folder_name(self) -> str:
        # YYYY-MM[-DD][ title]  — single definition of the format

    @classmethod
    def parse(cls, s: str) -> "AlbumFolderName | None":
        # regex ^(\d{4})-(\d{2})(?:-(\d{2}))?(?:\s+(.+))?$
        # returns AlbumFolderName or None for non-conforming strings
```

Key behaviours:

- Month and day validators **normalize** bare user digits (`"4"` → `"04"`) so GUI inputs don't require zero-padding.
- `name` validator strips whitespace and coerces empty string to `None`.
- `parse` is the single regex definition of a valid album folder name; it returns `None` for anything non-conforming (used by the GUI and by `validate_album`).

Update `**DarkroomYearAlbum.validate_album`** to delegate:

```python
@field_validator("album")
@classmethod
def validate_album(cls, v: str) -> str:
    if AlbumFolderName.parse(v) is None:
        raise ValueError("album must follow format 'YYYY-MM[-DD][ title]' ...")
    return v
```

This replaces the hand-rolled regex in `validate_album` with `parse`, keeping one definition of the valid shape.

## 2. `actions.py` — wire model + structured `RenameAction`

Import `AlbumFolderName` and `ValidationError` from `pydantic`.

- `**NewAlbumAction._execute**`: replace inline date assembly (lines 475–479) with:

```python
try:
    folder_name = AlbumFolderName(year=year, month=month, day=day, name=name).folder_name
except ValidationError as e:
    return ExecutionResult(False, _validation_message(e))
```

- `**RenameAction**` constructor: change signature from `(album_path, new_name: str, darkroom_path)` to `(album_path, darkroom_path, year, month, day, name)`. In `_execute`:
  - `recognize_darkroom_album` as today
  - build folder name via `AlbumFolderName(...)` in `try/except ValidationError`
  - no-op when built name equals `album_path.name`
  - collision check + rename as today

Add a module-level private helper to extract clean user-facing text from a `ValidationError`:

```python
def _validation_message(e: ValidationError) -> str:
    msgs = [
        str(err.get("ctx", {}).get("error", err["msg"]))
        for err in e.errors()
    ]
    return "; ".join(msgs)
```

## 3. `manager.py` — align `rename_action`

Change:

```python
def rename_action(self, album_path: Path, new_name: str) -> Action:
    return RenameAction(album_path, new_name, self.settings.darkroom)
```

to:

```python
def rename_action(
    self, album_path: Path, year: str, month: str, day: str | None, name: str | None
) -> Action:
    return RenameAction(album_path, self.settings.darkroom, year, month, day, name)
```

## 4. `gui/layout.py` — rename dialog matches new-album; both dialogs use numeric inputs

Use `ui.number()` for all numeric fields (year, month, day) in **both** `_show_new_album_dialog` and `_show_rename_dialog`. `.value` is `float | None`; convert with `str(int(v))` before passing to the manager. Name stays `ui.input()`.

```python
# year — read-only in rename, editable in new-album
ui.number("Year", value=..., precision=0, min=1000, max=9999)

# month
ui.number("Month", value=..., precision=0, min=1, max=12)

# day — optional; None/.value is None when blank
ui.number("Day (optional)", precision=0, min=1, max=31)

# name
ui.input("Name (optional)")
```

Rename dialog prefill:

```python
parsed = AlbumFolderName.parse(node.name)
```

- Month/Day/Name: prefilled from `parsed` if not `None`; if `parse` returns `None` (non-standard legacy name), month/day/name are blank and a hint label says "Current name could not be parsed — fill fields manually."

No-op when the built folder name equals `node.name`.

Call: `self.manager.rename_action(node.path, year, month, day or None, name or None)`.

## 5. Tests

- `**tests/test_models.py**`: parametrized `validate_album` cases with `-DD`; `AlbumFolderName` round-trips (`build` → `parse`); invalid inputs for each field validator; `parse` returning `None` for non-conforming strings.
- `**tests/actions/test_new_album_rename.py**`: update `RenameAction` instantiation to new signature; add tests for bad-month / bad-day / forbidden-char in name / year-mismatch failures; add no-op (unchanged name) case.
- `**tests/test_manager.py**`: update `test_factory_methods_return_actions_with_expected_paths` to use new `rename_action(album_path, year, month, day, name)` signature.

## Files touched

- `[src/photo_darkroom_manager/models.py](src/photo_darkroom_manager/models.py)`
- `[src/photo_darkroom_manager/actions.py](src/photo_darkroom_manager/actions.py)`
- `[src/photo_darkroom_manager/manager.py](src/photo_darkroom_manager/manager.py)`
- `[src/photo_darkroom_manager/gui/layout.py](src/photo_darkroom_manager/gui/layout.py)`
- `[tests/test_models.py](tests/test_models.py)`
- `[tests/actions/test_new_album_rename.py](tests/actions/test_new_album_rename.py)`
- `[tests/test_manager.py](tests/test_manager.py)`
