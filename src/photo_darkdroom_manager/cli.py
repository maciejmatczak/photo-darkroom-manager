"""Photo Darkroom Manager - A modern CLI for managing your photo darkroom workflow."""

from pathlib import Path
from typing import Optional

from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from photo_darkdroom_manager.config import Settings
from photo_darkdroom_manager.darkroom import DarkroomYearAlbum, recognize_darkroom_album


app = typer.Typer(
    name="photo-darkroom-manager",
    help="A modern CLI tool for managing your photo darkroom workflow",
    add_completion=False,
)
console = Console()


def cli_print_pydantic_error(e: ValidationError):
    console.print("\n[bold red]❌ Configuration Validation Error[/bold red]\n")

    # Create a table for displaying errors
    error_table = Table(
        show_header=True,
        header_style="bold red",
        box=None,
        padding=(0, 1),
    )
    error_table.add_column("Field", style="cyan", no_wrap=True)
    error_table.add_column("Error", style="yellow")

    # Process each validation error
    for error in e.errors():
        # Format field location (convert tuple to dot-separated string)
        field_path = " → ".join(str(loc) for loc in error.get("loc", []))
        if not field_path:
            field_path = "[root]"

        # Get error message
        error_msg = error.get("msg", "Unknown error")

        error_table.add_row(field_path, error_msg)

    # Display the error table in a panel
    console.print(
        Panel(
            error_table,
            title="[bold red]Validation Errors[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )
    console.print(
        "\n[dim]Please check your configuration file and fix the errors above.[/dim]\n"
    )


def cli_load_settings():
    try:
        settings = Settings()
    except ValidationError as e:
        cli_print_pydantic_error(e)
        raise typer.Exit(1)

    return settings


def cli_recognize_darkroom_album(darkroom_path: Path, path: Path) -> DarkroomYearAlbum:
    try:
        album = recognize_darkroom_album(darkroom_path, path)
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)
    return album


def version_callback(value: bool):
    """Display version information."""
    if value:
        console.print("[bold cyan]Photo Darkroom Manager[/bold cyan] [dim]v0.1.0[/dim]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        help="Show version and exit",
    ),
):
    """
    Photo Darkroom Manager - Manage your photo darkroom workflow with style.
    """
    pass


@app.command()
def status():
    """Show the current status of your darkroom."""
    settings = cli_load_settings()

    console.print("\n[bold cyan]📸 Darkroom Status[/bold cyan]\n")
    cwd = Path.cwd()

    console.print(f"[blue]Darkroom:[/blue] {settings.darkroom}")
    console.print(f"[blue]Current directory:[/blue] {cwd}")

    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    console.print("[blue]Recognized album[/blue]")
    console.print(f"  Year: {album.year}")
    console.print(f"  Album: {album.album}")
    console.print(f"  Device: {album.device}")


@app.command()
def archive():
    """Show the current status of your darkroom."""
    console.print("\n[bold cyan]📸 Archiving album[/bold cyan]\n")

    settings = cli_load_settings()
    cwd = Path.cwd()
    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    if album.device is None:
        console.print(f"Moving whole album?: {album.path}")
    else:
        console.print(f"Moving album to device: {album.device}")


@app.command()
def publish():
    """Publish the album to the internet."""
    console.print("\n[bold cyan]📸 Publishing album[/bold cyan]\n")

    settings = cli_load_settings()
    cwd = Path.cwd()
    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    publish_dir = settings.darkroom / album.year / album.album / "PUBLISH"

    if not publish_dir.exists():
        console.print(f"[red]Publish directory does not exist: {publish_dir}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
