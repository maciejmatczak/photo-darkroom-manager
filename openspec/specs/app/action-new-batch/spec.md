# app/action-new-batch Specification

## Purpose

Defines creating a new batch for a device: creating missing device and
year folders, the batch and its `PUBLISH` folder, showing them before
creating any, and refusing without writes when names are invalid or a
folder is in the way.

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
rules before any folder is created. Creating SHALL be refused, with no
folder created, when a name is invalid, when the device path resolves
outside the darkroom, when the batch already exists, or when a file
stands where a folder on its path must go. These checks SHALL hold at the
preview and again when the creation runs.

#### Scenario: Invalid device
- **WHEN** the device name is not a valid device name
- **THEN** creating SHALL be refused and no folder SHALL be created

#### Scenario: Symlink escape
- **WHEN** a device folder is a symlink resolving outside darkroom
- **THEN** creating SHALL be refused without writes

#### Scenario: Batch already exists
- **WHEN** the target batch folder exists
- **THEN** creating SHALL be refused and existing data SHALL be unchanged

#### Scenario: File in the way
- **WHEN** a file named like the year folder exists in the device folder
- **THEN** creating SHALL be refused, naming that file

### Requirement: Preview before creating
Creating a batch SHALL show the folders it will create before creating
any.

#### Scenario: New year for a device
- **WHEN** a user previews a new batch `2027-01` for device Camera and
  `Camera/2027` does not exist
- **THEN** the preview SHALL list `Camera/2027`, `Camera/2027/2027-01`
  and its `PUBLISH` folder as created

#### Scenario: Batch exists
- **WHEN** a user previews a new batch that already exists
- **THEN** the preview SHALL be refused and no folder SHALL be created
