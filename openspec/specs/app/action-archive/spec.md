# app/action-archive Specification

## Purpose
Defines archiving a batch or subfolder: moving it to its mapped location under
the batch's device folder in the archive while preserving its nested structure
and conflict policies.

## Requirements

### Requirement: Archive to the mapped location
Archiving SHALL move the selected batch or subfolder to its archive path
as resolved by the library path mapping, preserving the nested tail and
merging into existing folders. Existing conflict policies SHALL be
unchanged, including conflicts that appear after preparation.

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
