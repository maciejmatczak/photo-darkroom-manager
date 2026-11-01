# Spec Delta

## ADDED Requirements

### Requirement: Preview before creating
Creating a batch SHALL show the folders it will create before creating
any. An invalid device or batch name, or a batch that already exists,
SHALL be refused at the preview.

#### Scenario: New year for a device
- **WHEN** a user previews a new batch `2027-01` for device Camera and
  `Camera/2027` does not exist
- **THEN** the preview SHALL list `Camera/2027`, `Camera/2027/2027-01`
  and its `PUBLISH` folder as created

#### Scenario: Batch exists
- **WHEN** a user previews a new batch that already exists
- **THEN** the preview SHALL be refused and no folder SHALL be created
