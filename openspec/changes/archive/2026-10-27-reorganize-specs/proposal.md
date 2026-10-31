# Proposal

## Why

The main specs mix two kinds of contract: behavior the user sees and relies
on, and the internal mechanics of how the core scans and resolves paths.
`core` holds both, and `user-interface` prescribes a rescan strategy instead
of an observable result. The upcoming UI/core separation needs a clear place
for the engine's contract with its clients, kept apart from the app's
contract with its users, before new requirements are added on either side.

## What Changes

- Introduce two spec areas using nested capability paths:
  - `app/` - behavior a user can observe or rely on (screens, actions,
    on-disk results, library layout).
  - `engine/` - guarantees the core gives any client (scanning, path
    resolution); never mechanics such as classes or threads.
- Move the action, library layout, and statistics capabilities under `app/`
  with requirements unchanged.
- Split `core`: tree shape, darkroom-only derivation, and device discovery go
  to `app/darkroom-tree`; scoped rescan goes to `engine/scanning`;
  destination resolution goes to `engine/path-resolution`.
- Move `user-interface` to `app/user-interface`, restating two requirements as
  observable behavior:
  - "Refresh after creation" (which prescribed what to rescan) becomes
    "Rows appear after creation".
  - "Batch and subfolder rows" states that Open buttons target the same
    destination the actions use, instead of naming the core helpers.
- **BREAKING** (spec ids only): every existing capability id changes. No
  application behavior changes.

## Capabilities

### New Capabilities

- `app/action-archive`: archiving a batch or subfolder (moved from `action-archive`)
- `app/action-create-batch`: creating a batch for a device (moved from `action-create-batch`)
- `app/action-publish`: publishing a batch (moved from `action-publish`)
- `app/action-rename-batch`: renaming a batch (moved from `action-rename-batch`)
- `app/library-layout`: library roots, layouts, naming, recognition (moved from `library-layout`)
- `app/statistics`: per-node counts, issues, and roll-up (moved from `statistics`)
- `app/darkroom-tree`: what the darkroom tree contains and which devices exist (split from `core`)
- `app/user-interface`: rows, actions offered, New Batch form (moved from `user-interface`)
- `engine/scanning`: scoped rescans of the darkroom tree (split from `core`)
- `engine/path-resolution`: resolving a node's darkroom, archive, and showroom locations (split from `core`)

### Modified Capabilities

- `action-archive`, `action-create-batch`, `action-publish`,
  `action-rename-batch`, `library-layout`, `statistics`, `core`,
  `user-interface`: all requirements removed (relocated to the capabilities
  above).

## Impact

- `openspec/specs/` layout and every capability id. In-flight change
  `album-title-diacritics` must target `app/library-layout`.
- Requires OpenSpec with nested spec id support (1.15+).
- No code, tests, or runtime behavior change.
