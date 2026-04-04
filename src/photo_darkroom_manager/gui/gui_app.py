"""NiceGUI process entry -- native app and dev server."""

from nicegui import ui

from photo_darkroom_manager.gui.layout import DarkroomUI
from photo_darkroom_manager.manager import DarkroomManager
from photo_darkroom_manager.settings import Settings, load_settings, save_settings


def _try_load_settings() -> Settings | None:
    """Load settings; return None if missing, invalid, or unreadable."""
    try:
        return load_settings()
    except Exception:
        return None


def _build_setup_page(initial: Settings | None = None) -> None:
    """Settings: prompt for darkroom/showroom/archive paths."""

    async def do_save():
        try:
            settings = Settings(
                darkroom=darkroom_input.value,
                showroom=showroom_input.value,
                archive=archive_input.value,
            )
        except Exception as e:
            ui.notify(str(e), type="negative", timeout=5000)
            return
        save_settings(settings)
        ui.notify("Configuration saved!", type="positive")

    ui.dark_mode(True)
    with ui.column().classes("w-full max-w-lg mx-auto p-8 gap-4"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to("/"),
            ).props("dense").tooltip("Back to main")
            ui.label("Photo Darkroom Manager — Settings").classes(
                "text-2xl font-bold flex-grow"
            )
        ui.label("Configure your directory paths.").classes("text-grey-5")
        darkroom_input = ui.input(
            "Darkroom directory",
            value=str(initial.darkroom) if initial else "",
        ).classes("w-full")
        showroom_input = ui.input(
            "Showroom directory",
            value=str(initial.showroom) if initial else "",
        ).classes("w-full")
        archive_input = ui.input(
            "Archive directory",
            value=str(initial.archive) if initial else "",
        ).classes("w-full")
        ui.button("Save", icon="check", on_click=do_save).classes("mt-4")


def _build_configuration_error(message: str) -> None:
    """Main route when settings exist but the app cannot start (e.g. scan failure)."""

    ui.dark_mode(True)
    with ui.column().classes("w-full max-w-2xl mx-auto p-8 gap-4"):
        ui.label("Configuration problem").classes("text-xl font-bold")
        ui.label(message).classes("text-negative")
        ui.button(
            "Open settings",
            icon="settings",
            on_click=lambda: ui.navigate.to("/settings"),
        ).props("color=primary")


def _build_not_configured() -> None:
    """Main route when no valid settings file exists."""

    ui.dark_mode(True)
    with ui.column().classes("w-full max-w-2xl mx-auto p-8 gap-4"):
        ui.label("Not configured").classes("text-xl font-bold")
        ui.label("Set darkroom, showroom, and archive paths to use the app.").classes(
            "text-grey-5"
        )
        ui.button(
            "Open settings",
            icon="settings",
            on_click=lambda: ui.navigate.to("/settings"),
        ).props("color=primary")


def _register_pages() -> None:
    @ui.page("/")
    def index():
        settings = _try_load_settings()
        if settings is None:
            _build_not_configured()
            return
        try:
            DarkroomUI(DarkroomManager(settings)).build()
        except Exception as e:
            _build_configuration_error(str(e))

    @ui.page("/settings")
    def settings_page():
        _build_setup_page(_try_load_settings())


def main() -> None:
    _register_pages()
    ui.run(
        title="Photo Darkroom Manager",
        native=True,
        reload=False,
        window_size=(1200, 800),
    )


def dev() -> None:
    """Dev server: opens in browser with hot reload."""
    _register_pages()
    ui.run(
        title="Photo Darkroom Manager [DEV]",
        native=False,
        reload=True,
        port=8090,
    )


if __name__ in {"__main__", "__mp_main__"}:
    dev()
