---
name: Path Translation Methods
overview: Add three path-translation methods to `DarkroomManager`, one per destination space. Each method takes keyword-only source arguments and validates that exactly one is provided. Update the GUI buttons to use them.
todos:
  - id: manager-methods
    content: Add _translate, _require_one helpers and the three public path-translation methods to DarkroomManager in manager.py
    status: completed
  - id: gui-buttons
    content: Update showroom and archive Open button callbacks in layout.py to use the new manager methods
    status: completed
isProject: false
---

# Path Translation via Keyword-Only Methods

## API Design

Three methods on `DarkroomManager`, each named after the **destination** space. Keyword-only args name the **source** space. Exactly one source must be provided.

```python
def darkroom_path(self, *, archive_path: Path | None = None, showroom_path: Path | None = None) -> Path: ...
def showroom_path(self, *, darkroom_path: Path | None = None, archive_path: Path | None = None) -> Path: ...
def archive_path(self,   *, darkroom_path: Path | None = None, showroom_path: Path | None = None) -> Path: ...
```

Call sites read naturally — method = where you're going, kwarg = where you're coming from:

```python
self.manager.showroom_path(darkroom_path=node.path)
self.manager.archive_path(darkroom_path=node.path)
```

## Validation

Each method validates exactly one source is non-`None`. A shared private helper handles both validation and the actual translation:

```python
def _translate(self, path: Path, from_root: Path, to_root: Path) -> Path:
    return to_root / path.relative_to(from_root)

def _require_one(self, **kwargs: Path | None) -> tuple[str, Path]:
    provided = [(k, v) for k, v in kwargs.items() if v is not None]
    if len(provided) != 1:
        names = ", ".join(kwargs)
        raise ValueError(f"Provide exactly one of: {names}")
    return provided[0]
```

## Files to change

- [`src/photo_darkroom_manager/manager.py`](src/photo_darkroom_manager/manager.py) — add `_translate`, `_require_one`, and the three public methods
- [`src/photo_darkroom_manager/gui/layout.py`](src/photo_darkroom_manager/gui/layout.py) — update the showroom and archive "Open" button `on_click` callbacks (lines 291 and 301) to use `self.manager.showroom_path(darkroom_path=_n.path)` and `self.manager.archive_path(darkroom_path=_n.path)`
