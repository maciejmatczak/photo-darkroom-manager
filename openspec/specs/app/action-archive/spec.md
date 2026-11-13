# app/action-archive Specification

## Purpose
Defines archiving a batch or subfolder: moving it to its mapped location under
the batch's device folder in the archive while preserving its nested structure
and conflict policies.

## Requirements

### Requirement: Archive to the mapped location
Archiving SHALL move the selected batch or subfolder to its archive path
as resolved by the library path mapping, preserving the nested tail and
merging into existing folders.

#### Scenario: Nested subfolder
- **WHEN** `Camera/2026/2026-10 Walk/PHOTOS/raw` is archived
- **THEN** it SHALL land at `ARCHIVE/2026/2026-10 Walk/Camera/PHOTOS/raw`

#### Scenario: Devices stay separate
- **WHEN** Camera and Phone both archive `2026/2026-10 Walk`
- **THEN** their content SHALL land in separate device folders

### Requirement: Archive moves the previewed files
Archiving SHALL move exactly the files its preview listed. Files that
appear in the folder after the preview SHALL stay in the darkroom, and the
result SHALL report them.

#### Scenario: Photo added after the preview
- **WHEN** a batch with two files is previewed for archive, a third file
  is added, and the archive is run
- **THEN** the two previewed files SHALL be in the archive
- **AND** the third file SHALL still be in the darkroom and be reported

### Requirement: Archive around conflicts
The archive preview SHALL count and list the files that already exist in
the archive and ask whether to skip them. Without that answer, archiving
SHALL be refused. Skipped files SHALL stay in the darkroom, the batch
folder SHALL be kept for them, and the result SHALL report them. A file
already in the archive SHALL never be overwritten.

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

### Requirement: Emptied folders are removed
After archiving, the archived folder and the folders inside it that were
left empty SHALL be removed. A folder that still holds files SHALL be kept,
and one that cannot be removed, for example because it is open
elsewhere, SHALL be kept and reported.

#### Scenario: Whole batch archived
- **WHEN** every file of a batch is archived
- **THEN** the batch folder SHALL no longer be in the darkroom

#### Scenario: A file stays behind
- **WHEN** one file of a batch is skipped because it is already in the
  archive
- **THEN** the batch folder SHALL be kept with that file
