# Spec Delta

## Purpose

Defines the `darkroom` command-line tool: the commands a person or an
agent uses to configure the library, inspect nodes and run node actions,
and how it reports results and errors.

## ADDED Requirements

### Requirement: Commands
The tool SHALL offer `status`, `config list`, `config get`,
`config set`, `inspect`, and one command per node action: `open`,
`tidy`, `cull`, `edit`, `rename`, `publish`, `archive` and `new-batch`.
Each command SHALL describe itself and its options in its help.

#### Scenario: Help lists the commands
- **WHEN** a user runs `darkroom --help`
- **THEN** every command above SHALL be listed

### Requirement: Short name
The tool SHALL also be available as `dr`, with the same commands,
options and output; help SHALL name the tool `darkroom` either way.

#### Scenario: Alias runs the same command
- **WHEN** a user runs `dr inspect .` inside a batch
- **THEN** the output SHALL be the same as for `darkroom inspect .`

### Requirement: Targets are ids or darkroom paths
A target SHALL be a node id or a filesystem path inside the darkroom. A
target starting with `id:` SHALL be read as an id; an absolute path, or
one starting with `.`, SHALL be read as a path relative to the current
folder. An empty id addresses the root.

#### Scenario: Inside a batch folder
- **WHEN** a user's shell is in `DARKROOM/Camera/2026/2026-10 Walk` and
  they run `darkroom archive .`
- **THEN** the target SHALL be `Camera/2026/2026-10 Walk`

#### Scenario: Id from anywhere
- **WHEN** a user in any folder runs
  `darkroom inspect "id:Camera/2026"`
- **THEN** the target SHALL be `Camera/2026`

### Requirement: Bare targets
A target with neither form SHALL be read both as an id and as a path
relative to the current folder. When only one of them names an existing
node, that node SHALL be the target; when both do and they differ, the
command SHALL be refused as ambiguous, suggesting `id:` or `./`.

#### Scenario: Tab-completed folder name
- **WHEN** a user's shell is in `DARKROOM/Camera/2026` and they run
  `darkroom inspect "2026-10 Walk"`
- **THEN** the target SHALL be `Camera/2026/2026-10 Walk`

#### Scenario: Ambiguous target
- **WHEN** the current folder holds a folder `Camera` that is not the
  darkroom's `Camera` and a user runs `darkroom inspect Camera`
- **THEN** the command SHALL be refused as ambiguous

### Requirement: Paths outside the darkroom
A path target outside the darkroom SHALL be refused, naming the path and
the darkroom root.

#### Scenario: Showroom path
- **WHEN** a user runs `darkroom inspect SHOWROOM/2026`
- **THEN** the command SHALL be refused as outside the darkroom

### Requirement: Inspect a node
`inspect` SHALL show a node's id, kind, files directly in it, files in
its subtree, its own and rolled-up issues, its actions and its children
down to a depth the user chooses. Without a target it SHALL inspect the
current folder when that is in the darkroom, and the root otherwise.

#### Scenario: Batch with depth one
- **WHEN** a user runs `darkroom inspect --depth 1` inside a batch
- **THEN** the output SHALL show the batch and its direct children only
- **AND** the batch's totals SHALL still count its whole subtree

### Requirement: Inspect reads only what it shows
Inspecting a node SHALL read from disk only that node's subtree and the
folders of its ancestors, never sibling subtrees.

#### Scenario: One batch in a large library
- **WHEN** a user inspects one batch of one device
- **THEN** no folder of another device SHALL be read

### Requirement: Preview by default
Without `--apply` or `--confirm`, a command for an action that changes
files SHALL print its plan, the plan's fingerprint and the command that
confirms it, and change nothing. An action that changes no files SHALL
run at once.

#### Scenario: Archive preview
- **WHEN** a user runs `darkroom archive .` inside a batch
- **THEN** the files to move, `plan` with the fingerprint, and the
  `--confirm` command SHALL be printed
- **AND** no file SHALL be moved

#### Scenario: Open runs at once
- **WHEN** a user runs `darkroom open .`
- **THEN** the folder SHALL open without `--apply` or `--confirm`

### Requirement: Apply or confirm
`--apply` SHALL run the action as it is prepared now. `--confirm
FINGERPRINT` SHALL run it only when its plan still has that fingerprint,
and otherwise refuse, showing the confirmed and the current fingerprint.
The two options SHALL NOT be combined.

#### Scenario: Confirm the plan shown
- **WHEN** a user previews archive, nothing changes, and they run the
  printed `--confirm` command
- **THEN** the previewed files SHALL be archived

#### Scenario: Confirm a stale plan
- **WHEN** a user confirms a fingerprint from before a file was added to
  the batch
- **THEN** the command SHALL be refused, showing both fingerprints
- **AND** no file SHALL be moved

#### Scenario: Both options
- **WHEN** a user passes both `--apply` and `--confirm`
- **THEN** the command SHALL fail as a usage error

### Requirement: Never prompts
No command SHALL wait for input; whatever would need a decision SHALL be
an option or a refusal.

#### Scenario: Apply without a terminal
- **WHEN** an agent runs an apply command with no terminal attached
- **THEN** the command SHALL finish without reading input

### Requirement: Text and JSON output
Output SHALL be readable text by default. With `--json`, a command SHALL
print exactly one JSON document on stdout carrying a format version, and
nothing else. Logs SHALL go to stderr only.

#### Scenario: Machine-readable inspect
- **WHEN** an agent runs `darkroom --json inspect "id:Camera"`
- **THEN** stdout SHALL parse as one JSON document holding the node and
  its children

### Requirement: Structured errors
In JSON mode, a refused or failed command SHALL print a JSON document
with the error's kind and message, and a suggested fix where the tool
knows one.

#### Scenario: Not configured
- **WHEN** an agent runs `darkroom --json inspect` and no darkroom root is
  configured
- **THEN** the error SHALL name the `darkroom` key and suggest setting it
  with `config set`

### Requirement: Exit codes
The exit code SHALL be 0 for ok, no-op and a printed preview; 1 for
failed; 2 for a usage error; 3 for refused, including not allowed and an
ambiguous target; 4 when the engine is not ready; and 5 when the target
is not found or outside the darkroom.

#### Scenario: Archive a year
- **WHEN** a user runs `darkroom archive "id:Camera/2026"`
- **THEN** the exit code SHALL be 3

#### Scenario: Unknown id
- **WHEN** a user runs `darkroom inspect "id:Camera/1999"` and no such
  folder exists
- **THEN** the exit code SHALL be 5

### Requirement: Setting configuration saves it
`config set` SHALL validate the value and, when valid, save the
configuration file in the same command. An invalid value SHALL be
refused, naming the key and the problem, and the file SHALL be unchanged.

#### Scenario: Set the archive root
- **WHEN** a user runs `darkroom config set archive D:/Archive` and the
  folder exists
- **THEN** the configuration file SHALL hold the new archive root

#### Scenario: Invalid log level
- **WHEN** a user runs `darkroom config set log_level LOUD`
- **THEN** the command SHALL be refused naming `log_level`
- **AND** the configuration file SHALL be unchanged
