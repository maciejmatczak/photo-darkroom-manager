# Spec Delta

## ADDED Requirements

### Requirement: Overwrites are shown before publishing
The publish preview SHALL list every file that will replace a file
already in the showroom, by name.

#### Scenario: Republishing a batch
- **WHEN** `PUBLISH/` holds `a.jpg` and `b.jpg` and the showroom device
  folder already holds `a.jpg`
- **THEN** the preview SHALL list `a.jpg` as overwritten and `b.jpg` as
  new
