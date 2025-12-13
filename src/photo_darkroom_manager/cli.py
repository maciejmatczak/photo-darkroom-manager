"""Photo Darkroom Manager - A modern CLI for managing your photo darkroom workflow."""

import os
from pathlib import Path
import shutil
from typing import Optional

from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.table import Table
import typer

from photo_darkroom_manager.config import Settings
from photo_darkroom_manager.darkroom import DarkroomYearAlbum, recognize_darkroom_album


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


def cli_recognize_darkroom_album(
    darkroom_path: Path, path: Path
) -> DarkroomYearAlbum | None:
    try:
        album = recognize_darkroom_album(darkroom_path, path)
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)
    return album


def cli_print_album(album: DarkroomYearAlbum):
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()

    table.add_row("Path", str(album.album_path))
    table.add_row("Year", album.year)
    table.add_row("Album", album.album)
    table.add_row("Device", str(album.device) if album.device else "[dim]None[/dim]")

    console.print(
        Panel(
            table,
            title=f"[blue]Album '{escape(album.album)}'[/blue]",
            border_style="blue",
            expand=False,
        )
    )
    console.print("")


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
    if album:
        cli_print_album(album)


def move_dir_safely(source_dir: Path, target_dir: Path):
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Source directory is not a directory: {source_dir}")
    if target_dir.exists():
        raise ValueError(f"Target directory already exists: {target_dir}")
    shutil.move(source_dir, target_dir)


@app.command()
def archive(path: Path | None = None):
    """Show the current status of your darkroom."""

    console.print("\n[bold cyan]📸 Archiving[/bold cyan]\n")

    settings = cli_load_settings()
    if path is None:
        cwd = Path.cwd()
    else:
        cwd = path.resolve()

    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    if album is None:
        console.print(f"[red]Album not recognized for path: {cwd}[/red]")
        raise typer.Exit(1)

    cli_print_album(album)

    source_dir: Path
    if album.device is None:
        console.print(f"Archiving *whole* album: [white]{album.album_path}[/white]")
        source_dir = album.album_path
        target_dir = settings.archive / album.year / album.album
    else:
        console.print(
            f"Archiving album's *device folder*: [white]{album.device}[/white]"
        )
        source_dir = album.album_path / album.device
        target_dir = settings.archive / album.year / album.album / album.device

    console.print("")

    console.print(f"Source directory: {escape(str(source_dir))}")
    console.print(f"Target directory: {cli_render_path(target_dir)}")
    console.print("")

    if not typer.confirm("Ready to move directory?", default=True):
        console.print("  [dim]Aborted.[/dim]")
        raise typer.Exit(0)

    console.print("")
    console.print(f"[green]Moving directory...[/green]")

    move_dir_safely(source_dir, target_dir)

    console.print(f"[green]Done![/green]")


def cli_render_path(path: Path) -> str:
    parts = path.parts

    existing_part: Path = Path(parts[0])
    not_existing_parts = Path("")

    exists = True
    for part in parts[1:]:
        p = existing_part / part
        if not p.exists():
            exists = False

        if exists:
            existing_part = p
        else:
            not_existing_parts = not_existing_parts / part

    existing_part_str = escape(str(existing_part))
    not_existing_parts_str = escape(str(not_existing_parts))

    return f"[green]{existing_part_str}{escape(os.path.sep)}[/green][white dim]{not_existing_parts_str}[/white dim]"


def move_file_under_dir(file_path: Path, target_dir: Path):
    if not target_dir.exists():
        raise ValueError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise ValueError(f"Target directory is not a directory: {target_dir}")

    target_file = target_dir / file_path.name

    if target_file.exists():
        raise ValueError(f"Target file already exists: {target_file}")

    shutil.move(file_path, target_file)


@app.command()
def publish():
    """Publish the album to the internet."""
    console.print("\n[bold cyan]📸 Publishing album[/bold cyan]\n")

    settings = cli_load_settings()
    cwd = Path.cwd()
    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    if album is None:
        console.print(f"[red]Album not recognized for path: {cwd}[/red]")
        raise typer.Exit(0)

    cli_print_album(album)

    publish_dir = album.publish_dir

    # PUBLISH directory must exist, if it doesn't, we exit

    if not publish_dir.exists():
        console.print(f"[red]Publish directory does not exist: {publish_dir}[/red]")
        raise typer.Exit(1)

    items_in_publish_dir = list(publish_dir.glob("*"))

    # directories in PUBLISH directory are unexpected, as we only publish files

    dirs_in_publish_dir = [f for f in items_in_publish_dir if f.is_dir()]
    if dirs_in_publish_dir:
        console.print("[red]Publish directory contains directories[/red]")
        console.print("[dim]Files in publish directory:[/dim]")
        for d in dirs_in_publish_dir:
            console.print(f"[dim]  - {d.name}[/dim]")
        raise typer.Exit(1)

    # files in PUBLISH directory are expected, as we only publish files
    # if there are no files, we exit

    files_in_publish_dir = [f for f in items_in_publish_dir if f.is_file()]
    if len(files_in_publish_dir) == 0:
        console.print("[yellow]Publish directory is empty[/yellow]")
        raise typer.Exit(1)

    console.print(
        f"  [dim]Files in publish directory:[/dim] {len(files_in_publish_dir)}\n"
    )

    # we now have the files to publish

    # we need to double check target directory before copying
    target_dir = settings.showroom / album.year / album.album

    console.print(f"Target directory: {cli_render_path(target_dir)}")
    if not target_dir.exists():
        console.print(f"  [yellow]Target directory does not exist[/yellow]")
        if not typer.confirm("  Create target directory?", default=True):
            console.print("  [dim]Aborted.[/dim]")
            raise typer.Exit(0)
        target_dir.mkdir(parents=True, exist_ok=True)
        console.print(
            f"  [green]Created target directory[/green]: {cli_render_path(target_dir)}"
        )

    # we are ready to move files to the target directory

    console.print("")
    if not typer.confirm(
        f"Ready to move {len(files_in_publish_dir)} files?", default=True
    ):
        console.print("  [dim]Aborted.[/dim]")
        raise typer.Exit(0)

    console.print("")
    console.print(f"[green]Moving files...[/green]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Moving files...", total=len(files_in_publish_dir)
        )
        for file in files_in_publish_dir:
            move_file_under_dir(file, target_dir)
            progress.update(task, advance=1)

    console.print(f"[green]Done![/green]")


if __name__ == "__main__":
    app()
