# Spec Delta

## MODIFIED Requirements

### Requirement: Engine exposes the values it works with
The engine SHALL expose the library roots and external app commands it
works with as read-only values. They SHALL always equal the user's current
configuration; changing them SHALL go through the engine's configuration
interface, which is the only way clients read, change and save the user's
configuration.

#### Scenario: Configuration change is visible at once
- **WHEN** a client sets a new valid archive root through the engine
- **THEN** the engine's archive root SHALL be the new value without any
  further step

#### Scenario: Missing value
- **WHEN** the configuration has no valid archive root
- **THEN** the engine's archive root SHALL be empty

## ADDED Requirements

### Requirement: Busy engine refuses edits and further work
While a scan or an action is running, the engine SHALL reject changing a
configuration value, starting a scan or rescan, and executing an action,
with a typed busy error. Reading values, status, problems and nodes SHALL
stay possible.

#### Scenario: Edit during a scan
- **WHEN** a full scan is running and a client sets the archive root
- **THEN** the request SHALL be rejected as busy
- **AND** the archive root SHALL be unchanged

#### Scenario: Second scan
- **WHEN** a full scan is running and a client starts another scan
- **THEN** the request SHALL be rejected as busy

#### Scenario: Reading while busy
- **WHEN** a full scan is running
- **THEN** a client SHALL still read the engine status and configuration
  values
