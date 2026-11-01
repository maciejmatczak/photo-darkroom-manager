# Spec Delta

## Purpose

Defines how a client requests an action on a library node, previews its
plan and runs it, and what the engine reports back, so every client gets
the same guards, previews and results.

## ADDED Requirements

### Requirement: Requests address a node by id
A client SHALL request an action by node id and the action's own
parameters. The engine SHALL derive the node's kind from the id and
resolve its folder without a scanned library tree. An id that names no
library node, or whose folder does not exist, SHALL be rejected with a
typed error naming the id.

#### Scenario: Archive without a scan
- **WHEN** a client requests archive of `Camera/2026/2026-10 Walk` and no
  library tree is scanned
- **THEN** the engine SHALL prepare the archive of that batch

#### Scenario: Id outside the library layout
- **WHEN** a client requests tidy of `Camera/notes` and `notes` is not a
  year folder
- **THEN** the request SHALL be rejected as not found, naming
  `Camera/notes`

#### Scenario: Folder gone
- **WHEN** a client requests archive of a batch whose folder does not
  exist
- **THEN** the request SHALL be rejected as not found, naming the id

### Requirement: Actions are guarded by node kind
A request for an action that the node's kind does not list SHALL be
rejected with a typed error naming the id, the action and the kind, and
no file SHALL change.

#### Scenario: Archive a year
- **WHEN** a client requests archive of `Camera/2026`
- **THEN** the request SHALL be rejected as not allowed for a year

#### Scenario: Tidy the root
- **WHEN** a client requests tidy of the root
- **THEN** the request SHALL be rejected as not allowed for the root

### Requirement: Creating a missing node
A request for an action that creates the node's folder SHALL be accepted
when that folder does not exist yet, as long as the id names a node kind
that lists the action.

#### Scenario: New batch for a new device
- **WHEN** a client requests a new batch for device `Drone` and no
  `Drone` folder exists
- **THEN** the engine SHALL prepare a plan that creates `Drone`, its year
  and the batch

### Requirement: External app commands come from configuration
Cull and edit SHALL run the command configured for them; a client SHALL
NOT supply the command. When the command is not configured, preparing
SHALL be refused, naming the configuration key.

#### Scenario: Cull without a command
- **WHEN** no cull command is configured and a client requests cull of a
  batch
- **THEN** preparing SHALL be refused, naming `cull_command`

### Requirement: Preparing yields a plan or an outcome
Preparing an action SHALL return either a plan or a non-`ok` outcome
with a message. A plan SHALL list its steps as data: files to move with
source, target and whether the target is overwritten; folders to create;
folders to rename; folders to open; commands to launch.

#### Scenario: Rename plan
- **WHEN** a client prepares renaming `2026-10 Walk` to `2026-10-05 Walk`
- **THEN** the plan SHALL list one rename from the old folder to the new
  one

#### Scenario: Nothing to tidy
- **WHEN** a client prepares tidy of a batch with no misplaced files
- **THEN** preparing SHALL return a `noop` outcome

### Requirement: Plans say whether they change files
Each plan SHALL state whether running it changes files, so a client can
ask for confirmation only when it does.

#### Scenario: Launching an app
- **WHEN** a client prepares edit of a batch
- **THEN** the plan SHALL state that it changes no files

#### Scenario: Archive
- **WHEN** a client prepares archive of a batch with files
- **THEN** the plan SHALL state that it changes files

### Requirement: Plans carry a fingerprint
Each plan SHALL carry a short fingerprint derived from its content: the
action, the node id, the parameters and the steps. Preparing the same
request against the same disk and configuration SHALL give the same
fingerprint, in any process; any change in the steps SHALL give a
different one. The engine SHALL NOT store plans or fingerprints.

#### Scenario: Same request twice
- **WHEN** a client prepares archive of a batch twice with no change on
  disk
- **THEN** both plans SHALL carry the same fingerprint

#### Scenario: File added in between
- **WHEN** a file is added to the batch between two preparations
- **THEN** the two fingerprints SHALL differ

### Requirement: Applying an action
A client SHALL be able to apply an action in one request that prepares
and executes it, without confirming a plan first.

#### Scenario: Apply at once
- **WHEN** a client applies tidy of an untidy batch
- **THEN** the misplaced files SHALL be moved

### Requirement: Confirming a plan
A client SHALL be able to apply an action by confirming the fingerprint
of a plan it was shown. The engine SHALL prepare the action again and
execute it only when the new plan has that fingerprint. Otherwise it
SHALL refuse, reporting the confirmed and the current fingerprint, and
no file SHALL change.

#### Scenario: Plan changed since the preview
- **WHEN** a client was shown an archive plan with fingerprint F, a file
  was then added to the batch, and the client confirms F
- **THEN** the request SHALL be refused, reporting F and the current
  fingerprint
- **AND** no file SHALL be moved

#### Scenario: Plan unchanged
- **WHEN** nothing changed since the preview and the client confirms its
  fingerprint
- **THEN** the action SHALL be executed

### Requirement: Execution follows the plan
Executing a plan SHALL perform only the plan's steps. It SHALL NOT move,
create or rename anything the plan does not list.

#### Scenario: Late file in a tidy folder
- **WHEN** a misplaced file appears in a batch after its tidy plan was
  prepared and the plan is executed
- **THEN** the new file SHALL stay where it is

### Requirement: Outcome kinds
Every prepare and execute result SHALL carry exactly one outcome: `ok`
when it did what was asked, `noop` when there was nothing to do,
`refused` when it could not run as asked and changed no files, and
`failed` when something went wrong while running or unexpectedly.

#### Scenario: Conflict at prepare
- **WHEN** archiving a batch would overwrite a file already in the
  archive
- **THEN** preparing SHALL return a `refused` outcome listing the
  conflicts

#### Scenario: Unexpected error
- **WHEN** an action raises an unexpected error
- **THEN** the result SHALL carry a `failed` outcome with the error
  details

### Requirement: Results report each step
An execution result SHALL list every step it performed and every step
that failed, with the reason for each failure.

#### Scenario: Partial archive
- **WHEN** archiving three files moves two and fails on the third
- **THEN** the result SHALL list the two moves done and the failed move
  with its reason
- **AND** its outcome SHALL be `failed`

### Requirement: Results name the node after the action
An execution result SHALL carry the id of the acted-on node as it is
after the action, or none when the action removed it from the darkroom.

#### Scenario: Rename
- **WHEN** a client renames `Camera/2026/2026-10 Walk` to
  `2026-10-05 Walk`
- **THEN** the result SHALL carry `Camera/2026/2026-10-05 Walk`

#### Scenario: Archive empties the batch
- **WHEN** archiving moves every file of a batch and its folder is
  removed
- **THEN** the result SHALL carry no node id
