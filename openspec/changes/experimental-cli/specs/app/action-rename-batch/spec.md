# Spec Delta

## ADDED Requirements

### Requirement: Rename preview
Renaming SHALL show the current and the new folder name before anything
is renamed. An invalid new name, or one already taken in the year folder,
SHALL be refused at the preview, and nothing SHALL be renamed.

#### Scenario: Name taken
- **WHEN** a user previews renaming `2026-10 Walk` to `2026-10 Hike` and
  `2026-10 Hike` exists in the same year
- **THEN** the preview SHALL be refused, naming `2026-10 Hike`

#### Scenario: Invalid month
- **WHEN** a user previews renaming a batch to month `13`
- **THEN** the preview SHALL be refused, naming the month

### Requirement: Unchanged parts are kept
A rename that gives no new date SHALL keep the batch's current date, and
one that gives no new title SHALL keep its current title; the title
SHALL be cleared only when asked for. A rename that results in the same
name SHALL do nothing.

#### Scenario: New title only
- **WHEN** a user renames `2026-10-05 Walk` giving only the title `Hike`
- **THEN** the new name SHALL be `2026-10-05 Hike`

#### Scenario: Clear the title
- **WHEN** a user renames `2026-10 Walk` asking to clear the title
- **THEN** the new name SHALL be `2026-10`

#### Scenario: Same name
- **WHEN** a user renames `2026-10 Walk` to date `2026-10` and title
  `Walk`
- **THEN** nothing SHALL be renamed and the result SHALL say there was
  nothing to do
