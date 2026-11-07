# app/file-moves Specification

## Purpose

Defines what moving or replacing a user's file guarantees on disk,
whichever action does it, so no photo or video is lost to a failed or
interrupted move.

## Requirements

### Requirement: Source removed only after a verified copy
When a file is moved to another drive, its source SHALL be removed only
after the copy exists at the target with the source's size. When the copy
fails or does not match, the source SHALL stay, the incomplete copy SHALL
be removed, and the move SHALL be reported as failed with the reason.

#### Scenario: Archive to another drive
- **WHEN** a batch on drive D is archived to drive E
- **THEN** each file SHALL be removed from D only after its copy on E has
  the same size

#### Scenario: Copy cut short
- **WHEN** copying a video to another drive stops halfway because the
  drive is full
- **THEN** the video SHALL still be in its source folder
- **AND** no partial copy SHALL be left at the target

### Requirement: Replacing keeps one whole file
Replacing a file at a target SHALL never leave the target without a whole
file: until the new file is complete, the old one SHALL stay in place.
When the replacement fails, the old file SHALL be unchanged and the new
one SHALL stay at its source.

#### Scenario: Republish fails mid-copy
- **WHEN** publishing replaces `a.jpg` in the showroom and the copy fails
- **THEN** the showroom SHALL still hold the old `a.jpg`
- **AND** the new `a.jpg` SHALL still be in `PUBLISH/`

### Requirement: Conflicting files are never overwritten
A file at a target SHALL be replaced only by an action and policy that
replace, as listed in the confirmed plan. Any other move onto an existing
file, including one that appeared after the preview, SHALL be skipped or
refused and reported, and both files SHALL stay as they were.

#### Scenario: File appears in the archive after the preview
- **WHEN** a file with the same name is put into the archive between the
  preview and the archive run
- **THEN** neither file SHALL be changed
- **AND** the result SHALL report the conflict
