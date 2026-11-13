# Spec Delta

## Purpose

Defines opening a node's folder in the system file manager, the one action
every node kind offers.

## ADDED Requirements

### Requirement: Open a node's folder
Opening a node SHALL show its folder in the system file manager and
SHALL change no files. When the folder does not exist, opening SHALL be
refused, naming the folder.

#### Scenario: Open a year
- **WHEN** a user opens `Camera/2026`
- **THEN** that folder SHALL be shown in the file manager
- **AND** no file SHALL change

#### Scenario: Folder removed
- **WHEN** a user opens a batch whose folder was removed
- **THEN** opening SHALL be refused, naming the folder
