# Spec Delta

## ADDED Requirements

### Requirement: Direct actions run at once
Open, cull and edit SHALL be direct actions: a client SHALL request one
for a node and get its result when the call returns, with no plan, no
confirmation and no job. Direct actions SHALL also run while a job runs.

#### Scenario: Open a folder
- **WHEN** a client opens a batch's folder
- **THEN** the folder SHALL open and the call SHALL return an `ok` result
- **AND** no job SHALL be started

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

## MODIFIED Requirements

### Requirement: External app commands come from configuration
Cull and edit SHALL run the command configured for them; a client SHALL
NOT supply the command. When the command is not configured, the request
SHALL be refused, naming the configuration key, and nothing SHALL be
launched.

#### Scenario: Cull without a command
- **WHEN** no cull command is configured and a client requests cull of a
  batch
- **THEN** the request SHALL be refused, naming `cull_command`

## REMOVED Requirements

### Requirement: Outcome kinds
**Reason**: Its scenarios describe conflicts and conflict policies, which
are no longer shared concepts.
**Migration**: See "Result outcomes".

### Requirement: Preparing yields a plan or an outcome
**Reason**: Plans no longer list their steps as data; they carry a
plain-text preview and the action's own questions.
**Migration**: See `engine/planned-actions`, "Preparing yields a plan or
an outcome".

### Requirement: Plans say whether they change files
**Reason**: Whether an action is planned or direct is fixed per action,
not stated by each plan.
**Migration**: See "Direct actions run at once" and
`engine/planned-actions`, "Planned actions".

### Requirement: Plans carry a fingerprint
**Reason**: Moved with the planned-action flow.
**Migration**: See `engine/planned-actions`, "Plans carry a fingerprint".

### Requirement: Applying an action
**Reason**: A planned action is always prepared and then executed; there
is no separate one-request apply.
**Migration**: Prepare, then execute the plan; see
`engine/planned-actions`, "Executing a plan".

### Requirement: Confirming a plan
**Reason**: Executing a plan always checks its fingerprint.
**Migration**: See `engine/planned-actions`, "Executing a plan".

### Requirement: Execution follows the plan
**Reason**: Moved with the planned-action flow.
**Migration**: See `engine/planned-actions`, "Execution follows the
plan".

### Requirement: Results report each step
**Reason**: Plans and results no longer list steps; each action reports
what it did.
**Migration**: See `engine/planned-actions`, "Results report what the
action did".

### Requirement: Plans list conflicts
**Reason**: Conflicts are not a shared concept; an action that has them
asks about them as its own questions.
**Migration**: See `engine/planned-actions`, "Plans ask the action's own
questions", and the per-action specs (`app/action-archive`,
`app/action-publish`, `app/action-tidy`).

### Requirement: Conflict policy
**Reason**: Policies are replaced by the answers to each action's own
questions.
**Migration**: See `engine/planned-actions`, "The action checks its
answers".

### Requirement: Conflicts found while running
**Reason**: Covered by the answers the user gave for the plan.
**Migration**: See `engine/planned-actions`, "Answers cover what the run
finds".
