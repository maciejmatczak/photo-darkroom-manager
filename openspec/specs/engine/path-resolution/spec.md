# engine/path-resolution Specification

## Purpose
Defines how the engine resolves a darkroom, archive, or showroom location for a path, consistently for every action and client.

## Requirements

### Requirement: Destination resolution
The core's darkroom, archive, and showroom path helpers SHALL accept
exactly one source path and resolve it through the library path mapping.
Actions and the user interface SHALL use the same resolution.

#### Scenario: Helpers agree with actions
- **WHEN** the archive or showroom path of a batch or subfolder is asked
- **THEN** it SHALL equal the destination the archive or publish action
  uses
