# Spec Delta

## MODIFIED Requirements

### Requirement: Darkroom tree
The darkroom tree SHALL consist of root, device, year, batch, publish
folder, and subfolder nodes derived from the darkroom layout, each nested
under its parent. The publish folder is the `PUBLISH` folder directly in
a batch; every other folder under a batch is a subfolder. Year and batch
folders SHALL keep the existing date-prefix filtering.

#### Scenario: Node kinds
- **WHEN** the darkroom contains `Camera/2026/2026-10 Walk/PHOTOS`
- **THEN** the tree SHALL contain root, device, year, batch, and
  subfolder nodes in that order

#### Scenario: Empty darkroom
- **WHEN** the darkroom has no device folders
- **THEN** the tree SHALL be a root with no children

#### Scenario: Publish folder kind
- **WHEN** a batch contains `PUBLISH` and `PUBLISH/extra`
- **THEN** `PUBLISH` SHALL be a publish folder node
- **AND** `PUBLISH/extra` SHALL be a subfolder node
