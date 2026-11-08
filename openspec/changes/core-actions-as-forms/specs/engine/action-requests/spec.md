# Spec Delta

## REMOVED Requirements

### Requirement: Requests address a node by id
**Reason**: The capability is retired; requests are no longer a concept.
**Migration**: See `engine/actions`, "Actions address a node by id".

### Requirement: Actions are guarded by node kind
**Reason**: The capability is retired.
**Migration**: See `engine/actions`, "Actions are guarded by node kind".

### Requirement: Creating a missing node
**Reason**: The capability is retired.
**Migration**: See `engine/actions`, "Creating a missing node".

### Requirement: External app commands come from configuration
**Reason**: The capability is retired.
**Migration**: See `engine/actions`, "External app commands come from
configuration".

### Requirement: Preparing yields a plan or an outcome
**Reason**: Plans no longer list their steps as data; they carry a
plain-text preview and the action's own questions.
**Migration**: See `engine/planned-actions`, "Preparing yields a plan or
an outcome".

### Requirement: Plans say whether they change files
**Reason**: Whether an action is planned or direct is fixed per action,
not stated by each plan.
**Migration**: See `engine/actions`, "Direct actions run at once", and
`engine/planned-actions`, "Planned actions".

### Requirement: Plans carry a fingerprint
**Reason**: Moved with the planned-action flow.
**Migration**: See `engine/planned-actions`, "Plans carry a fingerprint".

### Requirement: Applying an action
**Reason**: A planned action is always prepared and then executed; there
is no separate one-request apply.
**Migration**: See `engine/planned-actions`, "Executing a plan".

### Requirement: Confirming a plan
**Reason**: Executing a plan always checks its fingerprint.
**Migration**: See `engine/planned-actions`, "Executing a plan".

### Requirement: Execution follows the plan
**Reason**: Moved with the planned-action flow.
**Migration**: See `engine/planned-actions`, "Execution follows the
plan".

### Requirement: Outcome kinds
**Reason**: Its scenarios describe conflicts and conflict policies, which
are no longer shared concepts.
**Migration**: See `engine/actions`, "Result outcomes".

### Requirement: Results report each step
**Reason**: Plans and results no longer list steps; each action reports
what it did.
**Migration**: See `engine/planned-actions`, "Results report what the
action did", and `app/file-moves`, "Moves are reported".

### Requirement: Results name the node after the action
**Reason**: The capability is retired.
**Migration**: See `engine/actions`, "Results name the node after the
action".

### Requirement: Plans list conflicts
**Reason**: Conflicts are not a shared concept; an action that has them
asks about them as its own questions.
**Migration**: See `engine/planned-actions`, "Plans ask the action's own
questions", and the per-action specs.

### Requirement: Conflict policy
**Reason**: Policies are replaced by the answers to each action's own
questions.
**Migration**: See `engine/planned-actions`, "The action checks its
answers".

### Requirement: Conflicts found while running
**Reason**: Covered by the answers the user gave for the plan.
**Migration**: See `engine/planned-actions`, "Answers cover what the run
finds".
