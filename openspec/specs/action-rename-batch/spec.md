# action-rename-batch Specification

## Purpose

Defines renaming a batch, which changes only its darkroom folder and leaves
archive and showroom folders untouched.

## Requirements

### Requirement: Darkroom-local rename
Renaming a batch SHALL change only its darkroom folder. Archive and
showroom folders SHALL NOT be renamed, even when this breaks the match
between them.

#### Scenario: Rename after publish
- **WHEN** a published batch is renamed
- **THEN** its showroom folder SHALL keep the old name
