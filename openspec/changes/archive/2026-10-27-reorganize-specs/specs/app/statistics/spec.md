# Spec Delta

## Purpose

Defines the file counts and issues reported for each node of the darkroom tree,
and how they roll up from batches through year and device nodes to the root.

## ADDED Requirements

### Requirement: Roll-up through devices
File counts and issues SHALL roll up from batches through years and
devices to the root. Device and year nodes SHALL report only aggregated
descendant statistics and issues.

#### Scenario: Untidy batch surfaces on device
- **WHEN** a batch has loose untidy files
- **THEN** its year, device, and root nodes SHALL report the issue

#### Scenario: Rescan updates ancestors
- **WHEN** files change inside one batch and it is rescanned
- **THEN** the counts of its year, device, and root SHALL be updated
