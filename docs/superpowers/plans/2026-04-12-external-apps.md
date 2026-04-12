# External Applications Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the ability to open external applications (culling/editing) from the GUI with configurable commands and placeholders.

**Architecture:** Update `Settings` to include command templates, implement placeholder resolution in a new action, and update the GUI to show buttons and handle errors.

**Tech Stack:** Python, Pydantic, Subprocess, Custom GUI framework (PySide/Tkinter based on existing code).

---

### Task 1: Update Settings Model

**Files:**
- Modify: `src/photo_darkroom_manager/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test for new settings fields**

```python
def test_settings_with_external_commands():
    from photo_darkroom_manager.settings import Settings
    data = {
        "darkroom": ".",
        "showroom": ".",
        "archive": ".",
        "cull_command": "cull-app {folder}",
        "edit_command": "edit-app {first_image}"
    }
    settings = Settings(**data)
    assert settings.cull_command == "cull-app {folder}"
    assert settings.edit_command == "edit-app {first_image}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL with "extra fields not permitted" or similar.

- [ ] **Step 3: Update `Settings` class**

```python
class Settings(BaseModel):
    darkroom: Path
    showroom: Path
    archive: Path
    cull_command: str | None = None
    edit_command: str | None = None
    # ... existing validators ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photo_darkroom_manager/settings.py tests/test_settings.py
git commit -m "feat: add external command fields to settings"
```

### Task 2: Implement Placeholder Resolution Logic

**Files:**
- Create: `src/photo_darkroom_manager/external_apps.py`
- Test: `tests/test_external_apps.py`

- [ ] **Step 1: Write tests for placeholder resolution**

```python
def test_resolve_placeholders(tmp_path):
    from photo_darkroom_manager.external_apps import resolve_placeholders
    album_dir = tmp_path / "2026-04-12-test"
    album_dir.mkdir()
    img1 = album_dir / "A.jpg"
    img1.touch()
    img2 = album_dir / "B.jpg"
    img2.touch()

    template = "app --folder {folder} --image {first_image}"
    resolved = resolve_placeholders(template, album_dir)
    assert str(album_dir) in resolved
    assert str(img1) in resolved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_external_apps.py -v`
Expected: FAIL with "module not found".

- [ ] **Step 3: Implement `resolve_placeholders` and helper to find first image**

```python
import os
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".arw", ".cr2", ".nef", ".dng", ".tiff"}

def find_first_image(directory: Path) -> Path | None:
    files = sorted(directory.iterdir())
    for f in files:
        if f.suffix.lower() in IMAGE_EXTENSIONS:
            return f
    return None

def resolve_placeholders(template: str, album_path: Path) -> str:
    folder = str(album_path.resolve())
    first_image_path = find_first_image(album_path)
    first_image = str(first_image_path.resolve()) if first_image_path else ""

    return template.format(folder=folder, first_image=first_image)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_external_apps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photo_darkroom_manager/external_apps.py tests/test_external_apps.py
git commit -m "feat: implement placeholder resolution for external apps"
```

### Task 3: Implement Command Execution with Error Handling

**Files:**
- Modify: `src/photo_darkroom_manager/external_apps.py`
- Test: `tests/test_external_apps.py`

- [ ] **Step 1: Write tests for command execution**

```python
def test_run_external_app_success():
    from photo_darkroom_manager.external_apps import run_external_app
    # Mocking subprocess is better here, but for simplicity:
    result = run_external_app("echo hello", Path("."))
    assert result.success is True

def test_run_external_app_failure():
    from photo_darkroom_manager.external_apps import run_external_app
    result = run_external_app("nonexistent-app-12345", Path("."))
    assert result.success is False
    assert "not found" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_external_apps.py -v`
Expected: FAIL with "function not defined".

- [ ] **Step 3: Implement `run_external_app` using `subprocess.Popen`**

```python
import subprocess
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    success: bool
    error: str | None = None
    stdout: str | None = None
    stderr: str | None = None

def run_external_app(template: str, album_path: Path) -> ExecutionResult:
    try:
        command = resolve_placeholders(template, album_path)
        # Use shell=True to allow complex commands, but be careful with paths
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # We don't wait for it to finish if it's a GUI app,
        # but we check if it failed to start immediately.
        try:
            stdout, stderr = process.communicate(timeout=1)
            if process.returncode != 0:
                return ExecutionResult(False, f"Exit code {process.returncode}", stdout, stderr)
        except subprocess.TimeoutExpired:
            # It's running, which is usually good for a GUI app
            return ExecutionResult(True)

        return ExecutionResult(True, stdout=stdout, stderr=stderr)
    except Exception as e:
        return ExecutionResult(False, str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_external_apps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photo_darkroom_manager/external_apps.py tests/test_external_apps.py
git commit -m "feat: implement external app execution with error capture"
```

### Task 4: Update GUI (Cockpit)

**Files:**
- Modify: `src/photo_darkroom_manager/gui/gui_app.py`
- Modify: `src/photo_darkroom_manager/gui/layout.py` (if buttons are defined there)

- [ ] **Step 1: Add Cull and Edit buttons to the layout**

In `src/photo_darkroom_manager/gui/gui_app.py` (or wherever the cockpit is defined), add the buttons and set their visibility based on `settings`.

```python
# Pseudo-code for GUI update
self.cull_btn = Button("Cull", on_click=self.on_cull)
self.edit_btn = Button("Edit", on_click=self.on_edit)

def update_button_visibility(self):
    self.cull_btn.visible = bool(self.settings.cull_command)
    self.edit_btn.visible = bool(self.settings.edit_command)
```

- [ ] **Step 2: Implement button click handlers**

```python
def on_cull(self):
    album = self.selected_album
    result = run_external_app(self.settings.cull_command, album.path)
    if not result.success:
        self.show_error_dialog(result)

def on_edit(self):
    album = self.selected_album
    result = run_external_app(self.settings.edit_command, album.path)
    if not result.success:
        self.show_error_dialog(result)
```

- [ ] **Step 3: Implement `show_error_dialog`**

Show a dialog with `result.error`, `result.stdout`, and `result.stderr`.

- [ ] **Step 4: Manual verification**

1. Start the GUI: `uv run python -m photo_darkroom_manager.gui.gui_app`
2. Configure a dummy command in `config.yaml` (e.g., `cull_command: "echo {folder}"`).
3. Verify the button appears and clicking it shows no error (or shows the echo output if handled).
4. Configure a failing command and verify the error dialog shows stdout/stderr.

- [ ] **Step 5: Commit**

```bash
git add src/photo_darkroom_manager/gui/gui_app.py
git commit -m "feat: add Cull and Edit buttons to GUI cockpit"
```
