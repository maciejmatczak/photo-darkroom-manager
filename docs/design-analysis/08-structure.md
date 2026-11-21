# Phase 8: Structure

Where each piece from "Phase 7 at a glance" in
[07-interfaces.md](07-interfaces.md) lives, so the structure itself shows
the boundaries. Today's package layout, and the AGENTS.md hints that
describe it, are not inputs: they describe the current code, not this
redesign.

## 8a. The layout: roles inside a core

**Options compared (design it twice):**

| | A1. Roles at the top | A2. Roles inside `core/` | B. By feature, shared below |
|---|---|---|---|
| Folders | `cli/`, `gui/`, `compose.py`, then the roles | `cli/`, `gui/`, then `core/` holding the roles and `compose.py` | One folder per use case, `shared/` below |
| Change scenarios (Phase 5) | 1 folder each for 6 of 8 | The same | The same |
| Dependency rules | One layers contract | Two short layers contracts, one forbidden | Features independent of each other: a contract naming all eight |
| The core's interface | Not stated anywhere | `core/__init__.py`: one front door | Not stated |
| Composition root | Beside the frontends | Inside the backend it builds | Beside the frontends |
| Drawbacks | Frontends can reach any lower layer | One more level of nesting | `shared/` grows into a second `domain/`; the `archive/` feature clashes with the archive area |

A flat layout by knowledge was dropped early: with about 30 modules, its
rules would have to list modules one by one.

**Chosen: A2.**

```
photo_darkroom_manager/
  cli/                 driving adapter: commands         ─┐ independent of
  gui/                 driving adapter: the window        ─┘ each other
  core/
    __init__.py        the front door: build_core, the application
                       services, the values they pass around
    compose.py         build_core(settings): the composition root
    application/       tidying, publishing, archiving, renaming,
                       starting_batch, overview, opening, setting_up
    adapters/          driven: internal_transfer, rclone_transfer,
                       file_run_log, os_apps, settings_file
    ports/             file_transfer, run_log, external_apps,
                       settings_store
    domain/            batch, darkroom, showroom, archive, tidy_recipe,
                       folder_view, command_template, settings, move
    filesystem/        folders, safe names, the same-name rule
```

Dependency direction, read top to bottom:

```
cli | gui  >  core
core:  compose  >  application | adapters  >  ports  >  domain  >  filesystem
```

Decided:

- **Roles name the folders.** The scenario counts are equal across the
  options, because scattering was settled by the modules (Phases 5 and 7);
  so the layout is chosen by how simply it states the rules, and roles
  state them in one line.
- **A `core/` package with a narrow front door.** A layers contract lets
  a higher layer import any lower one; without a boundary, a frontend
  could import a concrete adapter. `core/__init__.py` exports what a client
  needs and nothing else, so the core's interface is written in one place:
  a deep module at the package level (Ousterhout).
- **The composition root lives inside the core.** Both clients call the
  same `build_core`, and it wires backend parts only.
- **`cli/` and `gui/` are driving adapters at the top**, not under
  `adapters/`. Driving adapters call the application; driven adapters are
  called by it (Cockburn, hexagonal architecture). They sit at different
  heights: the frontends import the core's front door, the driven adapters
  only ports and the domain. One folder would hold two layers.
- **`filesystem/` is the bottom layer, below the domain.** Phase 6 gave the
  filesystem no port: it is the medium the darkroom is made of. The
  darkroom reads folders, `Renaming` calls `folders.rename`, and
  `InternalTransfer` copies files; all three need the same OS facts (safe
  names, when two names are the same, creating and renaming folders), and
  only a layer below them all can serve them. It holds no domain
  knowledge. A port sits above the domain and points down through an
  interface; a medium sits below it and is imported directly.
- **Migration is cheaper**: `core`, `cli` and `gui` exist today, so the
  redesign moves code inside `core/` instead of also reshaping the top.

Rejected:

- **A1**, roles at the top: it has the direction (layers) but no boundary
  (a front door), and it puts the composition root next to the frontends.
  First recommended, then dropped: a `core/` wrapper was wrongly judged to
  carry no rule of its own.
- **B**, by feature: see the table.

## 8b. Naming per level

One strategy per level: **folders encode the role, files encode the
knowledge they own.**

| Folder | A file is named after | Files |
|---|---|---|
| `domain/` | The decision it owns | `batch`, `darkroom`, `showroom`, `archive`, `tidy_recipe`, `folder_view`, `command_template`, `settings`, `move` |
| `application/` | The activity: the use case's policy | `tidying`, `publishing`, `archiving`, `renaming`, `starting_batch`, `overview`, `opening`, `setting_up` |
| `ports/` | The role: the port's name | `file_transfer`, `run_log`, `external_apps`, `settings_store` |
| `adapters/` | How it works, then the port | `builtin_transfer`, `rclone_transfer`, `file_run_log`, `os_external_apps`, `toml_settings_store` |
| `filesystem/` | The OS fact | `folders` (create, rename), `names` (safe names, the same-name rule) |

Across all folders:

- **A file is the snake-case name of its main class** (`tidying.py` holds
  `Tidying`).
- **A use case's own value objects live in its file** (`TidyPreview`,
  `PublishClash`, ...).
- **A file that outgrows itself becomes a package of the same name**
  (`domain/darkroom/`), whose `__init__.py` is its interface.

Decided:

- **The tidy recipe's plan lives in the domain.** `recipe.plan(path)`
  returns a `TidyPlan` holding `TidyClash` and `LeftAlone` (7c); the recipe
  is in `domain/`, and the domain cannot import `application/`. So those
  three go in `domain/tidy_recipe.py`, as the recipe's output, and
  `Tidying` turns the plan into its preview and report. Publish and archive
  plan inside their use cases, so their plan types stay in
  `application/`. The rule: a type lives with whoever builds it.
- **Adapters are named how it works, then the port** (a contract by role,
  an implementation by technology):

  | Phase 7 name | Becomes | Why |
  |---|---|---|
  | `InternalTransfer` | `BuiltinTransfer` | "Internal" says nothing about how; it is the copy, check and swap built into the app |
  | `SettingsFile` | `TomlSettingsStore` | The technology (TOML) and the port it implements |
  | "an OS adapter" | `OsExternalApps` | It had no name yet |
  | `RcloneTransfer`, `FileRunLog` | Unchanged | Already follow the pattern |

- **The insides of `cli/` and `gui/` are not designed here.** They follow
  their frameworks (commands; windows and widgets), and this design stops
  at the core's front door. Parked for when the frontends are rebuilt on
  it.
