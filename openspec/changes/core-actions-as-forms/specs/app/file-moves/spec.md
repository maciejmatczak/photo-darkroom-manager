# Spec Delta

## ADDED Requirements

### Requirement: Moves are reported
An action that moves files SHALL report the files it moved, the files
that failed with the reason, the files it left alone because of the
user's answer, and the files a cancel left undone.

#### Scenario: Partial archive
- **WHEN** archiving three files moves two and fails on the third
- **THEN** the result SHALL report the two files moved and the failed
  file with its reason
- **AND** its outcome SHALL be `failed`

## MODIFIED Requirements

### Requirement: Conflicting files are never overwritten
A file at a target SHALL be replaced only when the user chose to replace
it for that run. Any other move onto an existing file, including one
that appeared after the preview, SHALL be skipped or refused and
reported, and both files SHALL stay as they were.

#### Scenario: File appears in the archive after the preview
- **WHEN** a file with the same name is put into the archive between the
  preview and the archive run
- **THEN** neither file SHALL be changed
- **AND** the result SHALL report the conflict
