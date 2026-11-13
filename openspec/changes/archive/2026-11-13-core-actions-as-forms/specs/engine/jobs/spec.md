# Spec Delta

## ADDED Requirements

### Requirement: How a job ends
A job's final state SHALL follow from how its work ended, never from the
content of its result: `failed` when the work raised an error,
`cancelled` when a cancel was asked and the work stopped for it, and
`done` otherwise. What the work did to each file SHALL be reported in its
result. A refused request SHALL start no job.

#### Scenario: Work raises an error
- **WHEN** a scan stops because of an unexpected error
- **THEN** the job SHALL end `failed` with the error

#### Scenario: File in the way at run time
- **WHEN** a tidy job finds a file at one of its targets that was not
  there when the plan was checked
- **THEN** the job SHALL end `done`
- **AND** its result SHALL report that file as skipped and the others as
  moved

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

### Requirement: Job states
A job's state SHALL be one of `new` (accepted, not yet running),
`running`, `cancelling` (asked to stop, not stopped yet), `done`,
`failed` and `cancelled`. A job SHALL end in exactly one of the last
three, and a finished job's state SHALL never change.

#### Scenario: Action that fails on a file
- **WHEN** an archive moves some files and fails on one
- **THEN** the job SHALL end `done`
- **AND** its result SHALL have the `failed` outcome and name the file

#### Scenario: Nothing to do
- **WHEN** a client executes a tidy plan that has nothing to do
- **THEN** the job SHALL end `done` with an `ok` result that moved
  nothing

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

### Requirement: A job's final state follows from its run
**Reason**: Refusals no longer reach a job, which its scenario "Refused
at run time" assumes.
**Migration**: See "How a job ends".
