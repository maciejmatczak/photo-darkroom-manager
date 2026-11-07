# Spec Delta

## ADDED Requirements

### Requirement: Archive moves the previewed files
Archiving SHALL move exactly the files its preview listed. Files that
appear in the folder after the preview SHALL stay in the darkroom, and the
result SHALL report them.

#### Scenario: Photo added after the preview
- **WHEN** a batch with two files is previewed for archive, a third file
  is added, and the archive is run
- **THEN** the two previewed files SHALL be in the archive
- **AND** the third file SHALL still be in the darkroom and be reported
