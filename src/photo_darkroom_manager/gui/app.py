"""GUI entry point -- NiceGUI native app."""

from nicegui import ui

from photo_darkroom_manager.gui.config import GuiSettings, load_settings, save_settings
from photo_darkroom_manager.gui.layout import build_ui
from photo_darkroom_manager.gui.model import App


def _build_setup_page() -> None:
    """First-run setup: prompt for darkroom/showroom/archive paths."""

    async def do_save():
        try:
            settings = GuiSettings(
                darkroom=darkroom_input.value,
                showroom=showroom_input.value,
                archive=archive_input.value,
            )
        except Exception as e:
            ui.notify(str(e), type="negative", timeout=5000)
            return
        save_settings(settings)
        ui.notify("Configuration saved!", type="positive")
        ui.navigate.to("/")

    ui.dark_mode(True)
    with ui.column().classes("w-full max-w-lg mx-auto p-8 gap-4"):
        ui.label("Photo Darkroom Manager — Setup").classes("text-2xl font-bold")
        ui.label("Configure your directory paths to get started.").classes(
            "text-grey-5"
        )
        darkroom_input = ui.input("Darkroom directory").classes("w-full")
        showroom_input = ui.input("Showroom directory").classes("w-full")
        archive_input = ui.input("Archive directory").classes("w-full")
        ui.button("Save & Start", icon="check", on_click=do_save).classes("mt-4")


def main() -> None:
    @ui.page("/")
    def index():
        settings = load_settings()
        if settings is None:
            _build_setup_page()
        else:
            build_ui(App(settings))

    ui.run(
        title="Photo Darkroom Manager",
        native=True,
        reload=False,
        window_size=(1200, 800),
    )


if __name__ == "__main__":
    main()
