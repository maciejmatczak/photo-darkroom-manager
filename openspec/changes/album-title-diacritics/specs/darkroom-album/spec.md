## ADDED Requirements

### Requirement: Album Folder Name Format
An album folder name SHALL conform to the pattern
`YYYY-MM[-DD][ title]`, where the date portion is mandatory and
the title is optional. A name that does not match this pattern
SHALL be rejected with a descriptive error.

#### Scenario: Date-only name is valid
- **WHEN** an album folder name contains only a date (`YYYY-MM`)
- **THEN** it SHALL be accepted as a valid album folder name

#### Scenario: Date with optional day is valid
- **WHEN** an album folder name contains a full date (`YYYY-MM-DD`)
- **THEN** it SHALL be accepted as a valid album folder name

#### Scenario: Date with title is valid
- **WHEN** an album folder name contains a date followed by a
  space and a non-empty title string
- **THEN** it SHALL be accepted as a valid album folder name

#### Scenario: Name not matching pattern is invalid
- **WHEN** an album folder name does not start with `YYYY-MM`
- **THEN** it SHALL be rejected with a validation error describing
  the expected pattern

### Requirement: Album Title Character Set
The optional title segment of an album folder name SHALL allow
Unicode word characters (letters from any script, digits,
underscore), as well as hyphens and spaces. All other characters
SHALL be rejected. The Python standard library `re` module with
default `str` pattern semantics (Unicode-aware `\w`) SHALL be
used; no third-party regex library is required.

#### Scenario: ASCII title is valid
- **WHEN** the title contains only ASCII letters, digits,
  underscores, hyphens, and spaces
- **THEN** it SHALL be accepted

#### Scenario: Latin diacritic title is valid
- **WHEN** the title contains characters with diacritics
  (e.g., `été`, `Wiosna ą`, `München`, `Niño`)
- **THEN** it SHALL be accepted

#### Scenario: Non-Latin script title is valid
- **WHEN** the title contains letters from a non-Latin Unicode
  script (e.g., Cyrillic, CJK)
- **THEN** it SHALL be accepted

#### Scenario: Title with punctuation or special chars is invalid
- **WHEN** the title contains characters that are not Unicode
  word characters, hyphens, or spaces (e.g., `:`, `*`, `?`, `!`)
- **THEN** it SHALL be rejected with a validation error

### Requirement: Single Source of Truth for Album Folder Validity
A public predicate function `is_valid_album_folder_name(name)`
SHALL be the sole entry point for checking whether a folder name
is a valid album folder name. All modules (including the
filesystem scanner) SHALL use this function rather than
maintaining their own pattern or logic.

#### Scenario: Scanner uses the shared predicate
- **WHEN** the scanner enumerates folders under a year directory
- **THEN** it SHALL include a folder if and only if
  `is_valid_album_folder_name` returns `True` for that folder's
  name

#### Scenario: Folder with valid diacritic title is discovered
- **WHEN** a year directory contains a folder named
  `2026-03 été`
- **THEN** the scanner SHALL include it in the darkroom tree

#### Scenario: Folder with invalid title is excluded from tree
- **WHEN** a year directory contains a folder whose title segment
  contains characters outside the allowed set (e.g.,
  `2026-03 bad:name`)
- **THEN** the scanner SHALL exclude it from the darkroom tree
