# Tasks

## 1. Verify the relocation

- [x] 1.1 Check that every requirement in the eight current main specs appears exactly once among the new `app/` and `engine/` deltas (verbatim, except the two restated `app/user-interface` requirements and the reworded opening of `app/darkroom-tree` "Darkroom tree"); verify by comparing requirement titles from `openspec show <id> --type spec --json` against the change's deltas
- [x] 1.2 Run `openspec validate reorganize-specs --strict` and verify it reports the change as valid

## 2. Project references

- [x] 2.1 Update references to old capability ids in `TODO.md`, `DEV.md`, `BIG_PICTURE.md` and `.cursor/rules/` to the new `app/` and `engine/` ids; verify with a search for the old ids that finds no stale references outside `openspec/changes/archive/`

## Workflow follow-up

- Archive the change, then delete any `openspec/specs/<old-id>/` folder left without requirements and verify `openspec list --specs` shows only `app/` and `engine/` ids.
- Rebase `album-title-diacritics` so its delta targets `app/library-layout`.
