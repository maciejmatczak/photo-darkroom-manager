# Spec Delta

## MODIFIED Requirements

### Requirement: Applying an action
A client SHALL be able to apply an action in one request that prepares
and executes it, without confirming a plan first, and with a conflict
policy. A heavy action (tidy, archive, publish) SHALL be applied as a
job; rename and new batch SHALL be applied at once and return their
result.

#### Scenario: Apply at once
- **WHEN** a client applies tidy of an untidy batch
- **THEN** the misplaced files SHALL be moved

#### Scenario: Apply starts a job
- **WHEN** a client starts applying archive of a batch
- **THEN** the engine's job SHALL be that archive until it finishes

#### Scenario: Rename returns its result
- **WHEN** a client applies a rename of a batch
- **THEN** the call SHALL return the rename's result once the folder is
  renamed
