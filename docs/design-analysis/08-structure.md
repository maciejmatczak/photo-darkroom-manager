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

## 8c. Dependency rules, in plain words

| # | Rule |
|---|---|
| R1 | `cli` and `gui` import only `core`'s front door, never anything inside it, and never each other |
| R2 | Nothing in `core` imports `cli`, `gui`, or a UI or CLI library |
| R3 | `domain/` imports only `filesystem/` (and the standard library) |
| R4 | `ports/` imports only `domain/`, for the types in its signatures (`Move`, `Settings`, `DarkroomPath`) |
| R5 | `application/` imports `ports/`, `domain/` and `filesystem/`, never `adapters/` |
| R6 | `adapters/` import `ports/`, `domain/` and `filesystem/`, never `application/`, and never each other |
| R7 | Only `compose.py` imports `adapters/`; nothing inside `core` imports `compose.py` except the front door |
| R8 | Use cases never import each other: what two of them share goes down into `domain/` or `filesystem/` |

**The front door** (`core/__init__.py`) exports what clients pass in or
read back, and nothing else:

- `build_core(settings) -> Core` and `open_setup() -> SettingUp`; the
  application services are reached through `Core` (`core.tidying`, ...);
- the values: `DarkroomPath`, `BatchDate`, `NameChange`, `StopOrSkip`,
  `StopSkipOrReplace`, every preview and report, `FolderView`,
  `FolderKind`, `Counts`, `Settings`, `SetupState`, `CommandTemplate`;
- the refusals, and `RunWatch`, which the client implements.

Not exported: the domain services, the plans, the ports other than
`RunWatch`, the adapters, `filesystem/`.

On the caller side:

```python
from photo_darkroom_manager.core import build_core, open_setup  # a client

setup = open_setup()                    # builds TomlSettingsStore inside
settings = setup.current()
state = setup.check(settings) if settings else NOT_SET_UP
core = build_core(settings) if state.ready else None
```

Decided:

- **A layer may skip the ones below it.** `Renaming` calls
  `folders.rename`, past the domain. Forbidding that would force a domain
  method whose only job is to call it: a pass-through method, a red flag
  in Ousterhout's book (an interface that hides nothing). `filesystem/` is
  the medium every layer stands on.
- **The application types against ports, never adapters** (R5), type
  hints included. A port is a `typing.Protocol`, so adapters implement it
  without inheriting and the application names only the port; the
  concrete class is chosen in `compose.py` alone (dependency inversion,
  Martin). Imports under `if TYPE_CHECKING:` count too: they couple all
  the same. If the application seems to need an adapter, the port is
  missing a method or a setting; widen the port.
- **Errors are part of the port.** Each adapter translates its failures
  into what the port declares (a `Failure` in `TransferResult`,
  `AppFailed`); the application never catches an adapter's exception.
- **The composition root builds every adapter**, the settings store
  included: `open_setup()` replaces the client building
  `TomlSettingsStore` itself in 7k, which broke R1.
- **Use cases never import each other** (R8). When two need the same
  check, importing one from the other is the easy drift; pushing the
  shared part down keeps each use case changeable on its own (Phase 5).
- **The rclone client stays inside `adapters/rclone_transfer`** if rclone
  is adopted, until a second user appears. A `clients/` folder for one
  file would hold nothing real.
- R1 needs an indirect-import allowance in its contract:
  `cli -> core -> compose -> adapters` is a legitimate chain. *(Corrected
  in 8d: a `protected` contract checks direct imports only, so no
  allowance is needed.)*

## 8d. Enforcement: import-linter contracts

Option names checked against the installed import-linter 2.15 source (the
version this project pins); the readthedocs pages returned 404. These
contracts apply once the layout exists; until then, today's two contracts
stay as they are.

```toml
[tool.importlinter]
root_package = "photo_darkroom_manager"
include_external_packages = true

[[tool.importlinter.contracts]]              # R1 (part), R2
name = "Frontends sit on the core; the core knows no frontend"
type = "layers"
layers = ["cli | gui", "core"]
containers = ["photo_darkroom_manager"]

[[tool.importlinter.contracts]]              # R2
name = "The core imports no UI library"
type = "forbidden"
source_modules = ["photo_darkroom_manager.core"]
forbidden_modules = ["nicegui", "webview"]

[[tool.importlinter.contracts]]              # R1: the front door
name = "Only the core reaches inside the core"
type = "protected"
protected_modules = ["photo_darkroom_manager.core.*"]
allowed_importers = ["photo_darkroom_manager.core"]

[[tool.importlinter.contracts]]              # R3-R7
name = "Inside the core, imports point down"
type = "layers"
layers = ["compose", "application | adapters", "ports", "domain",
          "filesystem"]
containers = ["photo_darkroom_manager.core"]
exhaustive = true

[[tool.importlinter.contracts]]              # R8
name = "Use cases never import each other"
type = "independence"
modules = ["photo_darkroom_manager.core.application.*"]

[[tool.importlinter.contracts]]              # R6 (part)
name = "Adapters never import each other"
type = "independence"
modules = ["photo_darkroom_manager.core.adapters.*"]
```

| Rule | Enforced by |
|---|---|
| R1 frontends use only the front door | `protected`: only `core`, as a package with its descendants, may import `core.*`. It checks direct imports, so `cli -> core -> compose` passes with no indirect-import allowance |
| R2 no UI library, no frontend in the core | The two contracts that exist today, kept |
| R3-R7 direction; application never adapters; only `compose` sees adapters | The inner layers contract: `\|` makes `application` and `adapters` independent siblings; a higher layer may skip down to any lower one (8c) |
| R6, R8 no imports among siblings | Two `independence` contracts with wildcards (`*` matches one level) |

Decided:

- **The smell test passes**: no contract lists individual modules; each
  names a folder or a wildcard, so a new use case or adapter needs no
  config change. **`exhaustive = true`** is the other half: a new folder
  inside `core/` fails the check until it is placed in a layer.
- **`protected` for the front door**, not the `forbidden` contract with
  `allow_indirect_imports` planned in 8c: it states the rule positively
  ("only the core may reach in") and checks direct imports only, so the
  legitimate chain through `compose` needs no workaround.
- **R4 is looser in config than in words**: the layers contract lets
  `ports/` import `filesystem/`. Accepted rather than adding a contract: a
  port has no reason to touch the OS, and review catches it.
- **Type-only imports count** (8c): `exclude_type_checking_imports` is off
  by default in 2.15, and stays off.
- **No CLI library to forbid**: the CLI uses `argparse` from the standard
  library.
