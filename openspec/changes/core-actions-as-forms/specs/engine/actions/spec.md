# Spec Delta

## Purpose

Defines what every action on a library node shares as seen by a client:
how it addresses a node, which actions a node allows, how direct actions
run, and what every result reports.

## ADDED Requirements

### Requirement: Actions address a node by id
A client SHALL ask for an action by node id and the action's own inputs.
The engine SHALL derive the node's kind from the id and resolve its
folder without a scanned library tree. An id that names no library node,
or whose folder does not exist, SHALL be rejected with a typed error
naming the id.

#### Scenario: Archive without a scan
- **WHEN** a client asks for archive of `Camera/2026/2026-10 Walk` and no
  library tree is scanned
- **THEN** the engine SHALL prepare the archive of that batch

#### Scenario: Id outside the library layout
- **WHEN** a client asks for tidy of `Camera/notes` and `notes` is not a
  year folder
- **THEN** the request SHALL be rejected as not found, naming
  `Camera/notes`

#### Scenario: Folder gone
- **WHEN** a client asks for archive of a batch whose folder does not
  exist
- **THEN** the request SHALL be rejected as not found, naming the id

### Requirement: Actions are guarded by node kind
Asking for an action that the node's kind does not list SHALL be
rejected with a typed error naming the id, the action and the kind, and
no file SHALL change.

#### Scenario: Archive a year
- **WHEN** a client asks for archive of `Camera/2026`
- **THEN** the request SHALL be rejected as not allowed for a year

#### Scenario: Tidy the root
- **WHEN** a client asks for tidy of the root
- **THEN** the request SHALL be rejected as not allowed for the root

### Requirement: Creating a missing node
An action that creates the node's folder SHALL be accepted when that
folder does not exist yet, as long as the id names a node kind that lists
the action.

#### Scenario: New batch for a new device
- **WHEN** a client asks for a new batch for device `Drone` and no
  `Drone` folder exists
- **THEN** the engine SHALL prepare a plan that creates `Drone`, its year
  and the batch

### Requirement: Direct actions run at once
Open, cull and edit SHALL be direct actions: a client SHALL ask for one
on a node and get its result when the call returns, with no plan, no
confirmation and no job. Direct actions SHALL also run while a job runs.

#### Scenario: Open a folder
- **WHEN** a client opens a batch's folder
- **THEN** the folder SHALL open and the call SHALL return an `ok` result
- **AND** no job SHALL be started

### Requirement: External app commands come from configuration
Cull and edit SHALL run the command configured for them; a client SHALL
NOT supply the command. When the command is not configured, the action
SHALL be refused, naming the configuration key, and nothing SHALL be
launched.

#### Scenario: Cull without a command
- **WHEN** no cull command is configured and a client asks for cull of a
  batch
- **THEN** the action SHALL be refused, naming `cull_command`

### Requirement: Result outcomes
Every result SHALL carry exactly one outcome: `ok` when it did what was
asked, `noop` when there was nothing to do, `refused` when it could not
run as asked and changed no files, `cancelled` when it was stopped by a
client before it finished, and `failed` when something went wrong while
running.

#### Scenario: Republish without a choice
- **WHEN** a republish would replace files in the showroom and the
  client gives no answer about them
- **THEN** the result SHALL carry a `refused` outcome
- **AND** no file SHALL be published

#### Scenario: Cancelled archive
- **WHEN** a client cancels an archive while it runs
- **THEN** the result SHALL carry a `cancelled` outcome

#### Scenario: Unexpected error in a job
- **WHEN** a planned action raises an unexpected error while its job runs
- **THEN** the job SHALL end `failed` with the error

### Requirement: Results name the node after the action
A result SHALL carry the id of the acted-on node as it is after the
action, or none when the action removed it from the darkroom.

#### Scenario: Rename
- **WHEN** a client renames `Camera/2026/2026-10 Walk` to
  `2026-10-05 Walk`
- **THEN** the result SHALL carry `Camera/2026/2026-10-05 Walk`

#### Scenario: Archive empties the batch
- **WHEN** archiving moves every file of a batch and its folder is
  removed
- **THEN** the result SHALL carry no node id
