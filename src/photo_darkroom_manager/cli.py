"""Photo Darkroom Manager - A modern CLI for managing your photo darkroom workflow."""

import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Optional

from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
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
            padding=(1, 4),
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
    items = [
        ("Path", str(album.album_path)),
        ("Year", album.year),
        ("Album", album.album),
    ]

    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_column(style="cyan", no_wrap=True)
    info_table.add_column()
    for item in items:
        info_table.add_row(item[0], item[1])

    console.print(
        Panel(
            info_table,
            title=f"[blue]Album '{escape(album.album)}'[/blue]",
            border_style="blue",
            expand=False,
        )
    )
    console.print("")


def cli_print_header(text: str):
    """Print a formatted header panel."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{text}[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )
    )
    console.print()


def info_table(items: list[tuple[str, str]]) -> Table:
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
    )
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    for item in items:
        table.add_row(item[0], item[1])
    return table


def cli_print_info_table(
    items: list[tuple[str, str]], title: str = "Info", in_panel=False
):
    if in_panel:
        console.print(
            Panel(info_table(items), title=title, border_style="cyan", expand=False)
        )
    else:
        console.print(info_table(items))


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

    cli_print_header("📸 Darkroom Status")
    cwd = Path.cwd()

    cli_print_info_table(
        [
            ("Darkroom:", str(settings.darkroom)),
            ("Current directory:", str(cwd)),
        ],
        title="Darkroom Status",
        in_panel=True,
    )

    album = cli_recognize_darkroom_album(settings.darkroom, cwd)
    if album:
        console.print("")
        cli_print_album(album)


def remove_readonly(func, path, _):
    "Clear the readonly bit and reattempt the removal"
    os.chmod(path, stat.S_IWRITE)
    func(path)


def move_dir(src, dst, copy_function=shutil.copy2, onexc=None):
    """Recursively move a file or directory to another location. This is
    similar to the Unix "mv" command. Return the file or directory's
    destination.

    If dst is an existing directory or a symlink to a directory, then src is
    moved inside that directory. The destination path in that directory must
    not already exist.

    If dst already exists but is not a directory, it may be overwritten
    depending on os.rename() semantics.

    If the destination is on our current filesystem, then rename() is used.
    Otherwise, src is copied to the destination and then removed. Symlinks are
    recreated under the new name if os.rename() fails because of cross
    filesystem renames.

    The optional `copy_function` argument is a callable that will be used
    to copy the source or it will be delegated to `copytree`.
    By default, copy2() is used, but any function that supports the same
    signature (like copy()) can be used.

    A lot more could be done here...  A look at a mv.c shows a lot of
    the issues this implementation glosses over.

    """
    real_dst = dst
    if os.path.isdir(dst):
        if shutil._samefile(src, dst) and not os.path.islink(src):
            # We might be on a case insensitive filesystem,
            # perform the rename anyway.
            os.rename(src, dst)
            return

        # Using _basename instead of os.path.basename is important, as we must
        # ignore any trailing slash to avoid the basename returning ''
        real_dst = os.path.join(dst, shutil._basename(src))

        if os.path.exists(real_dst):
            raise shutil.Error("Destination path '%s' already exists" % real_dst)
    try:
        os.rename(src, real_dst)
    except OSError:
        if os.path.islink(src):
            linkto = os.readlink(src)
            os.symlink(linkto, real_dst)
            os.unlink(src)
        elif os.path.isdir(src):
            if shutil._destinsrc(src, dst):
                raise shutil.Error(
                    "Cannot move a directory '%s' into itself '%s'." % (src, dst)
                )
            if shutil._is_immutable(src) or (
                not os.access(src, os.W_OK)
                and os.listdir(src)
                and sys.platform == "darwin"
            ):
                raise PermissionError(
                    "Cannot move the non-empty directory "
                    "'%s': Lacking write permission to '%s'." % (src, src)
                )
            shutil.copytree(src, real_dst, copy_function=copy_function, symlinks=True)
            shutil.rmtree(src, onexc=onexc)
        else:
            copy_function(src, real_dst)
            os.unlink(src)
    return real_dst


def move_dir_safely(source_dir: Path, target_dir: Path):
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Source directory is not a directory: {source_dir}")
    if target_dir.exists():
        raise ValueError(f"Target directory already exists: {target_dir}")
    move_dir(source_dir, target_dir, onexc=remove_readonly)


@app.command()
def archive(path: Path | None = None):
    """Show the current status of your darkroom."""

    cli_print_header("📸 Archiving")

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

    console.print(f"Archiving album: [white]{album.album_path}[/white]")
    source_dir = cwd
    target_dir = settings.archive / album.relative_subpath

    console.print("")

    console.print(f"Source directory: [green]{escape(str(source_dir))}[/green]")
    console.print(f"Target directory: {cli_render_path(target_dir)}")
    console.print("")

    if not typer.confirm("Ready to move directory?", default=False):
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


def move_file_under_dir(file_path: Path, target_dir: Path, overwrite: bool = False):
    if not target_dir.exists():
        raise ValueError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise ValueError(f"Target directory is not a directory: {target_dir}")

    target_file = target_dir / file_path.name

    if target_file.exists():
        if not target_file.is_file():
            raise ValueError(f"Cannot overwrite non-file: {target_file}")

    # if target_file.exists():
    #     raise ValueError(f"Target file already exists: {target_file}")

    shutil.move(file_path, target_file)


@app.command()
def publish():
    """Publish the album to the showroom."""
    cli_print_header("📸 Publishing album")

    settings = cli_load_settings()
    cwd = Path.cwd().resolve()
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

    # we now have the files to publish

    # we need to double check target directory before copying
    target_dir = settings.showroom / album.year / album.album

    cli_print_info_table(
        [
            ("Files in publish directory:", str(len(files_in_publish_dir))),
            ("Target directory:", cli_render_path(target_dir)),
        ],
    )
    console.print("")

    if not target_dir.exists():
        console.print(f"  [yellow]Target directory does not exist[/yellow]")
        console.print("")
        if not typer.confirm("  Create target directory?", default=False):
            console.print("  [dim]Aborted.[/dim]")
            raise typer.Exit(0)
        target_dir.mkdir(parents=True, exist_ok=True)
        console.print(
            f"  [green]Created target directory[/green]: {cli_render_path(target_dir)}"
        )

    # first, find potential conflicts

    conflicts = []
    for file in files_in_publish_dir:
        target_file = target_dir / file.name
        if target_file.exists():
            conflicts.append((file, target_file))

    if conflicts:
        console.print("[bold yellow]🔥 Conflicts detected![/bold yellow]")
        console.print("")
        console.print("The following files already exist in the target directory:")
        console.print("")

        conflict_table = Table(
            show_header=True,
            header_style="bold yellow",
            box=None,
            padding=(0, 1),
        )
        conflict_table.add_column("File", style="yellow", no_wrap=True)
        conflict_table.add_column("Source/Target", style="dim")

        for source_file, target_file in conflicts:
            conflict_table.add_row(
                escape(source_file.name),
                escape(str(source_file)) + "\n" + escape(str(target_file)),
            )

        console.print(conflict_table)
        console.print("")
        console.print(f"  Total files to publish: {len(files_in_publish_dir)}")
        console.print(f"  Total conflicts: {len(conflicts)}")
        console.print("")

        if not typer.confirm(
            "Ready to continue (and *overwrite* existing files)?",
            default=False,
        ):
            console.print("  [dim]Aborted.[/dim]")
            raise typer.Exit(0)

    else:
        if not typer.confirm(
            f"Ready to move {len(files_in_publish_dir)} files?", default=False
        ):
            console.print("  [dim]Aborted.[/dim]")
            raise typer.Exit(0)

    # we are ready to move files to the target directory
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

    console.print("[green]Done![/green]")


@app.command()
def organize():
    """Organize the files: seperate photos and videos into separate directories."""
    cli_print_header("📸 Organizing files")

    settings = cli_load_settings()
    cwd = Path.cwd().resolve()
    album = cli_recognize_darkroom_album(settings.darkroom, cwd)

    if album is None:
        console.print(f"[red]Album not recognized for path: {cwd}[/red]")
        raise typer.Exit(0)

    cli_print_album(album)

    files_data = {}
    for item in cwd.iterdir():
        if item.is_dir():
            continue

        # Get filename without any suffixes (e.g., "IMG_1234.jpg.xmp" -> "IMG_1234")
        file_id = item.name.split(".")[0]

        if file_id in files_data:
            continue
        else:
            files_data[file_id] = {
                "paths": [],
                "suffixes": [],
                "is_photo": False,
                "is_video": False,
            }

        all_related_files = list(cwd.glob(f"{file_id}.*", case_sensitive=False))
        files_data[file_id]["paths"] = all_related_files
        files_data[file_id]["suffixes"] = [
            f.name.split(".", 1)[-1] for f in all_related_files
        ]

        files_data[file_id]["is_photo"] = is_file_a_photo(
            files_data[file_id]["suffixes"]
        )
        files_data[file_id]["is_video"] = is_file_a_video(
            files_data[file_id]["suffixes"]
        )

    photo_paths = []
    video_paths = []

    for file_id, d in files_data.items():
        is_photo = d["is_photo"]
        is_video = d["is_video"]

        if is_photo and is_video:
            console.print(
                f"[yellow]File {file_id} is both a photo and a video, skipping...[/yellow]"
            )
            console.print(f"  Suffixes: {d['suffixes']}")
        if not (is_photo or is_video):
            console.print(
                f"[yellow]File {file_id} is not a photo or a video, skipping...[/yellow]"
            )
            console.print(f"  Suffixes: {d['suffixes']}")
        if is_photo:
            photo_paths.extend(d["paths"])
        if is_video:
            video_paths.extend(d["paths"])

    cli_print_info_table(
        [
            ("Photos:", str(len(photo_paths))),
            ("Videos:", str(len(video_paths))),
        ]
    )
    console.print("")

    if not typer.confirm("Ready to move files?", default=False):
        console.print("  [dim]Aborted.[/dim]")
        raise typer.Exit(0)

    video_dir = cwd / "VIDEOS"
    if video_paths:
        video_dir.mkdir(parents=True, exist_ok=True)

    photos_dir = cwd / "PHOTOS"
    if photo_paths:
        photos_dir.mkdir(parents=True, exist_ok=True)

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
            "[cyan]Moving files...", total=len(photo_paths) + len(video_paths)
        )
        for path in photo_paths:
            move_file_under_dir(path, photos_dir)
            progress.update(task, advance=1)
        for path in video_paths:
            move_file_under_dir(path, video_dir)
            progress.update(task, advance=1)

    console.print("[green]Done![/green]")


def is_file_a_photo(suffixes: list[str]) -> bool:
    return any(
        suffix.lower() in {"jpg", "jpeg", "png", "heic", "heif"} for suffix in suffixes
    )


def is_file_a_video(suffixes: list[str]) -> bool:
    return any(
        suffix.lower() in {"mp4", "mov", "avi", "mkv", "webm"} for suffix in suffixes
    )


if __name__ == "__main__":
    app()
