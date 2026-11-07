# Spec Delta

## MODIFIED Requirements

### Requirement: Archive to the mapped location
Archiving SHALL move the selected batch or subfolder to its archive path
as resolved by the library path mapping, preserving the nested tail and
merging into existing folders. A file already in the archive at a target
SHALL never be overwritten, including one that appears after preparation.

#### Scenario: Nested subfolder
- **WHEN** `Camera/2026/2026-10 Walk/PHOTOS/raw` is archived
- **THEN** it SHALL land at `ARCHIVE/2026/2026-10 Walk/Camera/PHOTOS/raw`

#### Scenario: Devices stay separate
- **WHEN** Camera and Phone both archive `2026/2026-10 Walk`
- **THEN** their content SHALL land in separate device folders

## ADDED Requirements

### Requirement: Archive around conflicts
The archive preview SHALL count and list the files that already exist in
the archive. Archiving with conflicts SHALL be refused unless the user
chooses to skip them; skipped files SHALL stay in the darkroom, the batch
folder SHALL be kept for them, and the result SHALL report them.

#### Scenario: Ten files already archived
- **WHEN** a batch of 100 files is archived, 10 of them already exist in
  the archive, and the user chooses to skip conflicts
- **THEN** 90 files SHALL be in the archive
- **AND** the 10 SHALL still be in the batch folder in the darkroom, and
  be reported

#### Scenario: Refused by default
- **WHEN** the user archives that batch without choosing to skip
- **THEN** the archive SHALL be refused, listing the 10 conflicts
- **AND** no file SHALL move
