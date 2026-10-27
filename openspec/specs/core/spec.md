# core Specification

## Purpose

Defines the darkroom tree the application works on: device, year, batch, and
subfolder nodes derived only from the darkroom root, scoped rescans, device
discovery, and destination resolution shared by actions and the user interface.

## Requirements

### Requirement: Darkroom tree
The core SHALL build a tree of root, device, year, batch, and subfolder
nodes from the darkroom layout, with parent links. Year and batch folders
SHALL keep the existing date-prefix filtering.

#### Scenario: Node kinds
- **WHEN** the darkroom contains `Camera/2026/2026-10 Walk/PHOTOS`
- **THEN** the tree SHALL contain root, device, year, batch, and
  subfolder nodes in that order

#### Scenario: Empty darkroom
- **WHEN** the darkroom has no device folders
- **THEN** the tree SHALL be a root with no children

### Requirement: Darkroom only
The tree SHALL be derived only from the darkroom root.

#### Scenario: Fully archived batch
- **WHEN** a batch has been fully archived and the darkroom is rescanned
- **THEN** the batch SHALL NOT appear in the tree

### Requirement: Scoped rescan
Rescanning a node SHALL refresh that subtree and update its ancestors
without rescanning siblings.

#### Scenario: New year under a device
- **WHEN** a batch is created under a new year of an existing device and
  the device is rescanned
- **THEN** the new year and batch SHALL appear

### Requirement: Device discovery
Available devices SHALL be the immediate subdirectories of the darkroom,
sorted by name, including empty ones and excluding files, read fresh on
each call. There SHALL be no device registry and no default device.

#### Scenario: Empty device folder listed
- **WHEN** `DARKROOM/Phone` exists with no content
- **THEN** `Phone` SHALL be listed

### Requirement: Destination resolution
The core's darkroom, archive, and showroom path helpers SHALL accept
exactly one source path and resolve it through the library path mapping.
Actions and the user interface SHALL use the same resolution.

#### Scenario: Helpers agree with actions
- **WHEN** the archive or showroom path of a batch or subfolder is asked
- **THEN** it SHALL equal the destination the archive or publish action
  uses
