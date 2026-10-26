## 1. Widen Title Validation in models.py

- [ ] 1.1 Change `_TITLE_ALLOWED` regex from `r"^[a-zA-Z0-9_\- ]+$"`
      to `r"^[\w\- ]+$"` in `models.py`
- [ ] 1.2 Update the comment above `_TITLE_ALLOWED` to reflect Unicode
      word characters instead of ASCII
- [ ] 1.3 Update the error message in `validate_name` to remove the word
      "ASCII" (e.g., "title may only contain letters, digits, spaces,
      hyphens, and underscores")

## 2. Add Predicate Function to models.py

- [ ] 2.1 Add `is_valid_album_folder_name(name: str) -> bool` to
      `models.py`, wrapping `AlbumFolderName.from_str()` in a
      try/except `ValidationError`

## 3. Remove ALBUM_PATTERN from scan.py

- [ ] 3.1 Delete `ALBUM_PATTERN = re.compile(r"^\d{4}-\d{2}")` from
      `scan.py`
- [ ] 3.2 Remove `import re` from `scan.py`
- [ ] 3.3 Import `is_valid_album_folder_name` from `models` in `scan.py`
- [ ] 3.4 Replace `ALBUM_PATTERN.match(child_dir.name)` with
      `is_valid_album_folder_name(child_dir.name)` in `_scan_year`
- [ ] 3.5 Replace `ALBUM_PATTERN.match(child_dir.name)` with
      `is_valid_album_folder_name(child_dir.name)` in `rescan_subtree`

## 4. Tests

- [ ] 4.1 In `tests/test_models.py`, add positive cases for diacritic
      titles: `2026-03 été`, `2025-08 Wiosna ą`, `2024-12 München`
- [ ] 4.2 In `tests/test_models.py`, verify the existing rejection test
      still holds for truly invalid chars (e.g., `bad:name`)
- [ ] 4.3 In `tests/test_models.py`, add tests for
      `is_valid_album_folder_name` (returns `True` for valid,
      `False` for invalid)
- [ ] 4.4 In `tests/test_scan.py`, add a test that a year directory
      containing `2026-03 été` produces an album node for that folder

## 5. Housekeeping

- [ ] 5.1 Mark TODO.md line 10 (`album validation: support diactric
      characters`) as done
