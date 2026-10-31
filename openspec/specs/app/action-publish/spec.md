# app/action-publish Specification

## Purpose
Defines publishing a batch: moving the contents of its PUBLISH folder into the
batch's device folder in the showroom.

## Requirements

### Requirement: Publish to the device showroom folder
Publishing a batch SHALL move the contents of its `PUBLISH/` directly
into the batch's showroom device folder, as resolved by the library path
mapping. Only the `PUBLISH` component SHALL be stripped. Existing
overwrite behavior SHALL be unchanged.

#### Scenario: Two devices publish the same batch
- **WHEN** Camera and Phone each publish `2026/2026-10 Walk`
- **THEN** files SHALL land in `SHOWROOM/2026/2026-10 Walk/Camera` and
  `SHOWROOM/2026/2026-10 Walk/Phone` respectively
