# Design Spec: External Applications Support

## Purpose
Add the ability to open external applications (e.g., for culling and editing) directly from the Photo Darkroom Manager. This allows users to integrate their preferred tools into the darkroom workflow.

## Requirements
- Support configurable "cull" and "edit" commands in the settings.
- Support placeholders:
  - `{folder}`: The absolute path to the selected album's folder.
  - `{first_image}`: The absolute path to the first image file in the album folder (sorted alphabetically).
- GUI integration:
  - Add "Cull" and "Edit" buttons to the album cockpit view.
  - Buttons are hidden if the corresponding command is not configured.
  - If a command fails, show a detailed error message including `stdout` and `stderr`.

## Architecture & Components

### 1. Settings (`src/photo_darkroom_manager/settings.py`)
- Add `cull_command: str | None = None` and `edit_command: str | None = None` to the `Settings` class.
- These will be persisted in the user's `config.yaml`.

### 2. Actions (`src/photo_darkroom_manager/actions.py`)
- Create a new action class (e.g., `OpenExternalAppAction`) that handles:
  - Placeholder resolution.
  - Finding the "first image" in a directory (supporting common photo formats like `.jpg`, `.arw`, `.cr2`, `.nef`, etc.).
  - Executing the command using `subprocess.Popen` (non-blocking).
  - Capturing output if the process fails to start or exits immediately with an error.

### 3. GUI (`src/photo_darkroom_manager/gui/gui_app.py`)
- Update the Cockpit view to include the new buttons.
- Use conditional rendering (or `visible` property) based on the presence of the commands in settings.
- Implement error handling to display a dialog with `stdout`/`stderr` if the command execution fails.

## Data Flow
1. User selects an album in the GUI.
2. GUI checks `Settings` for `cull_command` and `edit_command`.
3. User clicks "Cull" or "Edit".
4. Manager resolves placeholders (`{folder}`, `{first_image}`).
5. Manager launches the external process.
6. If the process fails to launch, the GUI displays an error dialog.

## Error Handling
- If `{first_image}` is used but no image files are found, show a clear error message.
- If the command executable is not found, capture the `FileNotFoundError` and show it.
- Capture and display `stdout` and `stderr` for immediate execution failures.

## Testing
- Unit tests for placeholder resolution logic.
- Unit tests for "first image" discovery in various folder structures.
- Mocked subprocess calls to verify correct command string generation.
