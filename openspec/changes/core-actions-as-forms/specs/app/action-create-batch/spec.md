# Spec Delta

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Creation conflicts
**Reason**: It repeated "Validate before writing" and "Preview before
creating", and called a refusal a failure.
**Migration**: See "Validate before writing".
