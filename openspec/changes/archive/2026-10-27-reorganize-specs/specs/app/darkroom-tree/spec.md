# Spec Delta

## Purpose

Defines what the darkroom tree contains: device, year, batch, and subfolder nodes derived only from the darkroom root, and which devices are available.

## ADDED Requirements

### Requirement: Darkroom tree
The darkroom tree SHALL consist of root, device, year, batch, and subfolder
nodes derived from the darkroom layout, with parent links. Year and batch folders
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

### Requirement: Device discovery
Available devices SHALL be the immediate subdirectories of the darkroom,
sorted by name, including empty ones and excluding files, read fresh on
each call. There SHALL be no device registry and no default device.

#### Scenario: Empty device folder listed
- **WHEN** `DARKROOM/Phone` exists with no content
- **THEN** `Phone` SHALL be listed
