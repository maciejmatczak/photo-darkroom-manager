---
name: Settings Page Routing
overview: Split the current single `/` route into two dedicated routes (`/` for main, `/settings` for settings), add a gear button in the header to access settings, and a back-arrow on the settings page to return to main. The settings page never auto-redirects — saving validates and persists, navigation is always explicit.
todos:
  - id: setup-page-refactor
    content: "Refactor _build_setup_page() in gui_app.py: accept optional Settings for pre-fill, remove navigate.to on save, add back-arrow button"
    status: completed
  - id: register-routes
    content: "Add /settings route and fix / route in _register_pages(): redirect to /settings when unconfigured, guard DarkroomManager construction"
    status: completed
  - id: header-gear-button
    content: Add gear icon button to DarkroomUI header in layout.py linking to /settings
    status: completed
isProject: false
---

# Settings Page Routing Refactor

## New routing structure

```mermaid
flowchart TD
    Start([App start]) --> LoadSettings["load_settings()"]
    LoadSettings -->|None| RedirectSettings["/settings"]
    LoadSettings -->|valid| MainPage["/"]

    MainPage -->|settings missing| MisconfigBanner["Banner: not configured + link to /settings"]
    MainPage -->|settings valid| DarkroomUI["DarkroomUI.build()"]
    DarkroomUI -->|gear icon in header| SettingsPage["/settings"]

    SettingsPage -->|back arrow| MainPage
    SettingsPage -->|save button| Validate["Validate Settings()"]
    Validate -->|invalid| ShowError["ui.notify error, stay on /settings"]
    Validate -->|valid| SavePersist["save_settings(), ui.notify success, stay on /settings"]
```

## Changes

### [`gui_app.py`](src/photo_darkroom_manager/gui/gui_app.py)

- **`_build_setup_page()`** — remove the `ui.navigate.to("/")` call on save. Replace with `ui.notify("Saved")`. Add a back-arrow button (`ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/"))`) at the top. Accept an optional `Settings` arg to pre-fill the inputs with current values.

- **`_register_pages()`** — register two routes:
  - `@ui.page("/")`: load settings; if `None`, redirect to `/settings`; otherwise build `DarkroomUI`. Wrap `DarkroomManager` construction in try/except so stale/invalid paths show a banner instead of crashing.
  - `@ui.page("/settings")`: always build the settings page, pre-filling with `load_settings()` if available.

### [`layout.py`](src/photo_darkroom_manager/gui/layout.py)

- **`DarkroomUI.build()`** — add a gear icon button at the end of the header row:
  ```python
  ui.button(icon="settings", on_click=lambda: ui.navigate.to("/settings")).props("dense").tooltip("Settings")
  ```
