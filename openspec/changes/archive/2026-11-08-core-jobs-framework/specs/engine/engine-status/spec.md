# Spec Delta

## ADDED Requirements

### Requirement: Rename and new batch run alone
While a rename or a new batch is being applied, the engine SHALL reject
changing a configuration value, starting a job, and applying another
rename or new batch, with the same typed busy error. Reading and running
open, cull and edit SHALL stay possible.

#### Scenario: Scan during a rename
- **WHEN** a rename is being applied and a client starts a scan
- **THEN** the scan SHALL be rejected as busy

#### Scenario: Opening a folder during a rename
- **WHEN** a rename is being applied and a client opens another batch's
  folder
- **THEN** the folder SHALL open

## MODIFIED Requirements

### Requirement: Busy engine refuses edits and further work
While a job is `new`, `running` or `cancelling`, the engine SHALL reject
changing a configuration value, starting another job (a scan, a refresh
or a heavy action) and applying a rename or a new batch, with a typed
busy error naming the running job. Reading values, status, problems,
nodes and the job SHALL stay possible, and so SHALL running actions that
change no files: open, cull and edit.

#### Scenario: Edit during a scan
- **WHEN** a full scan is running and a client sets the archive root
- **THEN** the request SHALL be rejected as busy
- **AND** the archive root SHALL be unchanged

#### Scenario: Second scan
- **WHEN** a full scan is running and a client starts another scan
- **THEN** the request SHALL be rejected as busy

#### Scenario: Rename during an archive
- **WHEN** an archive is running and a client applies a rename of
  another batch
- **THEN** the request SHALL be rejected as busy, naming the archive
- **AND** no folder SHALL be renamed

#### Scenario: Reading while busy
- **WHEN** a full scan is running
- **THEN** a client SHALL still read the engine status and configuration
  values

#### Scenario: Opening a folder during an archive
- **WHEN** an archive is running and a client opens another batch's
  folder
- **THEN** the folder SHALL open

#### Scenario: Editing during an archive
- **WHEN** an archive is running and a client starts edit on a batch
- **THEN** the external editor SHALL be launched
