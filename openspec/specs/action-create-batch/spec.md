# action-create-batch Specification

## Purpose

Defines creating a batch for a device: creating missing device and year folders,
the batch, and its PUBLISH folder; validating names before any write; and
failing without changes on conflicts.

## Requirements

### Requirement: Create batch for a device
The action SHALL take a device, year, month, and optional day and title.
It SHALL create any missing device and year folders, the batch folder,
and `PUBLISH/`, and SHALL NOT create `PHOTOS/` or `VIDEOS/`.

#### Scenario: Create in empty darkroom
- **WHEN** a batch is created for device Camera, date 2026/10, no day or
  title, in an empty darkroom
- **THEN** `Camera/2026/2026-10/PUBLISH/` SHALL exist and the action SHALL
  succeed

#### Scenario: Create for existing device
- **WHEN** device Camera already exists
- **THEN** the batch SHALL be created beneath it

### Requirement: Validate before writing
Device and batch names SHALL be validated against the library naming
rules before any folder is created. A device path resolving outside the
darkroom SHALL be rejected before writes.

#### Scenario: Invalid device
- **WHEN** the device name is not a valid device name
- **THEN** the action SHALL fail and no files SHALL be created

#### Scenario: Symlink escape
- **WHEN** a device folder is a symlink resolving outside darkroom
- **THEN** the action SHALL fail without writes

### Requirement: Creation conflicts
The action SHALL fail without altering data when the batch exists or a
file blocks a folder on its path.

#### Scenario: Batch already exists
- **WHEN** the target batch folder exists
- **THEN** the action SHALL report failure and existing data SHALL be
  unchanged
