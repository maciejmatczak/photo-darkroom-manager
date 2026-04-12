---
name: Stricter album validation
overview: Tighten `DarkroomYearAlbum.validate_album` in `models.py` to enforce calendar months `01`–`12` and a clear separator after `YYYY-MM` (end of string or space + optional rest), then update the two permissive tests in `test_models.py` to expect `ValidationError`.
todos:
  - id: validate-album-regex
    content: Replace `validate_album` pattern and error text in `src/photo_darkroom_manager/models.py`
    status: completed
  - id: update-tests
    content: Rename and flip the two permissive tests in `tests/test_models.py` to `ValidationError` cases
    status: completed
  - id: lint-verify
    content: Run ruff format, ruff check --fix, ty check, and pytest
    status: completed
isProject: false
---

# Stricter `DarkroomYearAlbum` album validation

## Current behavior

In [`src/photo_darkroom_manager/models.py`](src/photo_darkroom_manager/models.py), `validate_album` uses:

```python
pattern = r"^\d{4}-\d{2}.*"
```

That accepts any two-digit “month” (e.g. `13`) and glued text (`2024-01foo`), which contradicts the docstring (`'YYYY-MM[ <something>]'`) and the items in [`TODO.md`](TODO.md).

## Target behavior

1. **Month** — Only `01`–`12` (reject `2024-13`, `2024-00`, etc.).
2. **Suffix** — After `YYYY-MM`, allow either **end of string** or **a single space** followed by an optional remainder (title). Reject glued characters immediately after the month digits (e.g. `2024-01foo`).

A single regex that encodes both rules (aligned with the existing internal plan and docstring):

`r"^\d{4}-(0[1-9]|1[0-2])( .*)?$"`

- `(0[1-9]|1[0-2])` — months `01`–`09` and `10`–`12`.
- `( .*)?$` — nothing after the month, or space + optional rest (so `2024-01 Album` and `2024-01` are valid).

**Note:** This pattern rejects forms like `2024-01-foo` (hyphen glued after month without a space first). That is consistent with the docstring’s “space before title” convention. If you later need hyphenated subtitles without a leading space, validation would need an explicit extension.

Update the `ValueError` message in the same validator so it still describes allowed shapes (e.g. mention month range and that a space separates an optional title).

## Tests

In [`tests/test_models.py`](tests/test_models.py):

| Current test | Change |
|--------------|--------|
| `test_darkroom_year_album_permissive_regex_accepts_non_calendar_month` | Rename (e.g. `test_darkroom_year_album_rejects_non_calendar_month`), use `pytest.raises(ValidationError, match="album")` with `album="2024-13 Album"` (same paths as today). Remove TODO comment that documents permissive behavior. |
| `test_darkroom_year_album_permissive_regex_accepts_tight_prefix` | Rename (e.g. `test_darkroom_year_album_rejects_glued_suffix_after_month`), assert `ValidationError` for `album="2024-01foo"`. Remove TODO. |

No change required to `recognize_darkroom_album`: it constructs `DarkroomYearAlbum` from path parts; stricter validation applies at model construction time as today.

## Verification (after implementation)

Per workspace rules, run in order:

- `uv run ruff format`
- `uv run ruff check --fix`
- `uv run ty check`
- `uv run pytest tests/test_models.py` (or full suite)

Optionally uncheck or remove the matching bullets in [`TODO.md`](TODO.md) once done (same scope as the task).
