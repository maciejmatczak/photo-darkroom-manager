# Spec Delta

## MODIFIED Requirements

### Requirement: Actions do not depend on state or settings
The listed actions SHALL depend only on the node's kind: not on its
issues, its files, the configured external app commands, or whether a
target folder exists. Whether an action is shown, enabled or highlighted
is the client's decision, and whether it can run is decided when it is
requested.

#### Scenario: Tidy folder still offers tidy
- **WHEN** a batch has no untidy files
- **THEN** it SHALL still list tidy
- **AND** it SHALL report no untidy issue

#### Scenario: Cull without a configured command
- **WHEN** no cull command is configured
- **THEN** a batch SHALL still list cull
