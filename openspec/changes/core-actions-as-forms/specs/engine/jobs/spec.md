# Spec Delta

## ADDED Requirements

### Requirement: Work that runs as a job
Every planned action (rename, new batch, tidy, archive and publish) and
every library scan and refresh SHALL run as a job. Direct actions (open,
cull and edit) SHALL run at once and never as a job.

#### Scenario: Archive is a job
- **WHEN** a client executes an archive plan for a batch
- **THEN** the archive SHALL run as a job of kind archive for that batch

#### Scenario: Opening a folder is not a job
- **WHEN** a client opens a batch's folder
- **THEN** the folder SHALL open and no job SHALL be started

#### Scenario: Rename is a job
- **WHEN** a client executes a rename plan for a batch
- **THEN** the rename SHALL run as a job of kind rename for that batch

## MODIFIED Requirements

### Requirement: Blocking calls run as jobs
The engine's blocking calls for scanning and refreshing SHALL start a job
and wait for it, so they follow the same busy rule and leave the same
job, state and log as a job started directly.

#### Scenario: Blocking scan
- **WHEN** a client calls the blocking scan and it returns
- **THEN** the engine's job SHALL be a finished scan

## REMOVED Requirements

### Requirement: What runs as a job
**Reason**: Rename and new batch now run as jobs, which its scenario
"Rename is not a job" contradicts.
**Migration**: See "Work that runs as a job".
