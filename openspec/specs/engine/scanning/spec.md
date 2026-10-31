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
