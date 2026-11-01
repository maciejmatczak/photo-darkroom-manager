# engine/scanning Specification

## Purpose
Defines the engine's guarantees when rescanning the darkroom tree: which parts of the tree a rescan refreshes and which it leaves untouched.

## Requirements

### Requirement: Scoped rescan
Rescanning a node SHALL refresh that subtree and update its ancestors
without rescanning siblings.

#### Scenario: New year under a device
- **WHEN** a batch is created under a new year of an existing device and
  the device is rescanned
- **THEN** the new year and batch SHALL appear

### Requirement: Rescan by id with fallback
A client SHALL request a scoped rescan by node id. When the id is not in
the tree or its folder no longer exists, the engine SHALL rescan the
nearest ancestor that is in the tree and still exists. The engine SHALL
return the id it actually rescanned.

#### Scenario: Folder not yet in the tree
- **WHEN** a client rescans `Camera/2027` and only `Camera` is in the tree
- **THEN** the engine SHALL rescan `Camera` and return `Camera`

#### Scenario: Folder gone from disk
- **WHEN** a client rescans a batch whose folder was removed
- **THEN** the engine SHALL rescan its year and return the year's id
- **AND** the batch SHALL no longer be in the tree

### Requirement: Rescan after an action
After the engine executes an action that changes the darkroom, it SHALL
rescan the part of the tree the action affected before returning, and
the result SHALL carry the id it rescanned. When no tree is scanned, it
SHALL rescan nothing and the result SHALL carry no id.

#### Scenario: Tidy updates the tree
- **WHEN** a client executes tidy on an untidy batch
- **THEN** reading that batch afterwards SHALL report no untidy issue
- **AND** the result SHALL carry the id that was rescanned

#### Scenario: Opening an external app
- **WHEN** a client executes an action that opens an external app
- **THEN** the result SHALL carry no rescanned id
