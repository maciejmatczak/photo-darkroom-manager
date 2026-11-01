# Spec Delta

## Purpose

Defines which actions apply to each kind of darkroom node, so every client
offers the same actions on the same rows.

## ADDED Requirements

### Requirement: Actions by node kind
Each node SHALL list the actions that apply to its kind:
- root and year: open
- device: open, new batch
- batch: open, rename, tidy, cull, edit, publish, archive
- subfolder: open, tidy, cull, edit, archive
- publish folder: open

#### Scenario: Batch actions
- **WHEN** a client reads a batch
- **THEN** it SHALL list open, rename, tidy, cull, edit, publish and
  archive

#### Scenario: Publish folder actions
- **WHEN** a client reads the publish folder of a batch
- **THEN** it SHALL list only open

### Requirement: Actions do not depend on state or settings
The listed actions SHALL depend only on the node's kind: not on its
issues, its files, the configured external app commands, or whether a
target folder exists. Whether an action is shown, enabled or highlighted
is the client's decision, and whether it can run is decided when it is
prepared.

#### Scenario: Tidy folder still offers tidy
- **WHEN** a batch has no untidy files
- **THEN** it SHALL still list tidy
- **AND** it SHALL report no untidy issue

#### Scenario: Cull without a configured command
- **WHEN** no cull command is configured
- **THEN** a batch SHALL still list cull
