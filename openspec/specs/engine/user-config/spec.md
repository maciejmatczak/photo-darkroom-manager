# engine/user-config Specification

## Purpose
Defines how clients load, read, update and save the user's configuration, and
how configuration problems are reported so the user can fix them.

## Requirements

### Requirement: Tolerant load
Loading the configuration SHALL NOT fail because of the file's content or
because the file cannot be read. Every valid field SHALL be available after
loading. Loading SHALL return the problems it found, each naming the key it
concerns and a readable message; an empty result means a clean load.

#### Scenario: One invalid field
- **WHEN** the file has valid darkroom and showroom roots and an unknown
  log level
- **THEN** the darkroom and showroom values SHALL be available
- **AND** loading SHALL return exactly one problem, naming the log level key

#### Scenario: Missing required key
- **WHEN** the file has no archive key
- **THEN** loading SHALL return a problem naming the archive key as missing

#### Scenario: Unparsable or unreadable file
- **WHEN** the file is not valid YAML, or cannot be read
- **THEN** loading SHALL succeed with no values and one problem describing
  the cause

#### Scenario: No file yet
- **WHEN** no configuration file exists
- **THEN** loading SHALL return no problems and no values SHALL be set

### Requirement: Problems stay until fixed
The problems of the last load SHALL remain readable until fixed. A new load
SHALL replace them, and storing a valid value for a key SHALL remove that
key's problems.

#### Scenario: Fixing a loaded problem
- **WHEN** the file had an invalid log level and a client sets a valid one
- **THEN** no problem SHALL remain for the log level key

### Requirement: Invalid values are kept after load
A value from the file that fails validation SHALL be kept as read, so a
client can show it to the user for correction.

#### Scenario: Show what is in the file
- **WHEN** the log level in the file is invalid
- **THEN** reading the log level key SHALL return the value from the file

### Requirement: Validated update of one value
Setting one value SHALL either store it or be rejected with an error naming
the key and the reason. A rejected value SHALL leave the configuration
unchanged. A stored value SHALL be in effect immediately, without a further
step.

#### Scenario: Invalid value rejected
- **WHEN** a client sets the log level to an unknown level
- **THEN** the request SHALL be rejected with an error naming the log level
  key
- **AND** the previous value SHALL remain

#### Scenario: Unknown key
- **WHEN** a client sets or reads a key the configuration does not define
- **THEN** the request SHALL be rejected with an error naming that key

### Requirement: Configuration does not check the environment
Configuration validation SHALL check only the form of values, not whether a
configured folder currently exists on disk.

#### Scenario: Unplugged drive
- **WHEN** the archive root points to a folder that does not exist
- **THEN** loading SHALL return no problem for the archive key

### Requirement: Explicit save
The configuration SHALL be written to its file only when a client asks to
save. Saving SHALL be allowed while problems remain, and a later load SHALL
return the saved values.

#### Scenario: Round trip
- **WHEN** a client sets valid values, saves and loads again
- **THEN** the loaded values SHALL equal the saved ones

#### Scenario: Save while fixing
- **WHEN** a client fixes one of two invalid keys and saves
- **THEN** the file SHALL be written
- **AND** a later load SHALL return a problem only for the other key
