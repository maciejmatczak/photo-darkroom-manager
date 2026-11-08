# Spec Delta

## MODIFIED Requirements

### Requirement: Busy engine refuses edits and further work
While a job is `new`, `running` or `cancelling`, the engine SHALL reject
changing a configuration value and starting another job (a scan, a
refresh or the execution of a planned action), with a typed busy error
naming the running job. Reading values, status, problems, nodes and the
job SHALL stay possible, and so SHALL preparing a planned action and
running a direct action: open, cull and edit.

#### Scenario: Edit during a scan
- **WHEN** a full scan is running and a client sets the archive root
- **THEN** the request SHALL be rejected as busy
- **AND** the archive root SHALL be unchanged

#### Scenario: Second scan
- **WHEN** a full scan is running and a client starts another scan
- **THEN** the request SHALL be rejected as busy

#### Scenario: Rename during an archive
- **WHEN** an archive is running and a client executes a rename plan of
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

## REMOVED Requirements

### Requirement: Rename and new batch run alone
**Reason**: Rename and new batch run as jobs, so the busy rule for jobs
covers them; there is no separate lock for them.
**Migration**: See "Busy engine refuses edits and further work".
