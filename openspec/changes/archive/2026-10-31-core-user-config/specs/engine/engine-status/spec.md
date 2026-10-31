# Spec Delta

## Purpose

Defines the state the engine exposes to clients: the configuration-backed
values it works with, whether it can work at all and why not, and runtime
state that is separate from the user's configuration.

## ADDED Requirements

### Requirement: Engine exposes the values it works with
The engine SHALL expose the library roots and external app commands it
works with as read-only values. They SHALL always equal the user's current
configuration; changing them SHALL go through the configuration.

#### Scenario: Configuration change is visible at once
- **WHEN** a client sets a new valid archive root in the configuration
- **THEN** the engine's archive root SHALL be the new value without any
  further step

#### Scenario: Missing value
- **WHEN** the configuration has no valid archive root
- **THEN** the engine's archive root SHALL be empty

### Requirement: Engine status
The engine SHALL report one status, always reflecting the current
configuration and disk: `unconfigured` when no configuration file exists,
`invalid` when the configuration has problems or a library root does not
exist or is not a folder, and `ready` otherwise.

#### Scenario: Fresh install
- **WHEN** no configuration file exists
- **THEN** the status SHALL be `unconfigured`

#### Scenario: Valid configuration
- **WHEN** the configuration has no problems and all roots exist as folders
- **THEN** the status SHALL be `ready`

#### Scenario: Unplugged drive
- **WHEN** the configuration is valid but the archive folder does not exist
- **THEN** the status SHALL be `invalid`

#### Scenario: Status follows fixes
- **WHEN** the status is `invalid` because of one configuration problem
  and a client sets a valid value for that key
- **THEN** the status SHALL be `ready` without any further step

### Requirement: Status detail
When the status is not `ready`, the engine SHALL give a readable detail
naming every reason, each with the key to fix. When `ready`, there SHALL be
no detail.

#### Scenario: Several problems at once
- **WHEN** the log level is invalid and the showroom root is a file
- **THEN** the detail SHALL name both the log level and the showroom keys

### Requirement: Work requires ready
Scans and file actions SHALL be rejected while the status is not `ready`,
with the status and its detail as the reason.

#### Scenario: Not ready rejects work
- **WHEN** the status is `invalid` and a client requests a scan or action
- **THEN** the request SHALL be rejected, carrying the status and detail

#### Scenario: Root lost after the engine check
- **WHEN** an action was created while `ready` and a library root it uses
  is no longer a folder when the action is prepared or executed
- **THEN** the action SHALL refuse, naming that root, and change no files

### Requirement: Runtime log level
The engine SHALL hold its log level as runtime state, starting from the
configuration's log level when the engine starts, unless an environment
override is set. Changing the engine's log level SHALL NOT change the
configuration or its file, and later configuration changes SHALL NOT change
the running engine's log level.

#### Scenario: Temporary debug logging
- **WHEN** the configuration sets INFO and a client sets the engine log
  level to DEBUG
- **THEN** the engine log level SHALL be DEBUG
- **AND** the configuration's log level SHALL still be INFO

#### Scenario: Configuration edit at runtime
- **WHEN** the engine runs with INFO and a client sets the configuration's
  log level to ERROR
- **THEN** the engine log level SHALL still be INFO
