"""Photo Darkroom Manager - A modern CLI for managing your photo darkroom workflow."""

import typer
from rich.console import Console
from rich.panel import Panel
from typing import Optional

app = typer.Typer(
    name="photo-darkroom-manager",
    help="A modern CLI tool for managing your photo darkroom workflow",
    add_completion=False,
)
console = Console()


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
def hello(
    name: str = typer.Argument(..., help="Your name"),
    fancy: bool = typer.Option(False, "--fancy", "-f", help="Use fancy formatting"),
):
    """Greet someone with style."""
    if fancy:
        greeting = Panel.fit(
            f"[bold cyan]Hello, {name}![/bold cyan]\n[dim]Welcome to Photo Darkroom Manager[/dim]",
            border_style="cyan",
            title="👋 Greeting",
        )
        console.print(greeting)
    else:
        console.print(f"[bold green]Hello, {name}![/bold green]")


@app.command()
def status():
    """Show the current status of your darkroom."""
    console.print("\n[bold cyan]📸 Darkroom Status[/bold cyan]\n")

    # Example status table
    from rich.table import Table

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="right")
    table.add_column("Details")

    table.add_row("Camera", "[green]✓ Ready[/green]", "Canon EOS R5")
    table.add_row("Lens", "[green]✓ Ready[/green]", "24-70mm f/2.8")
    table.add_row("Film", "[yellow]⚠ Low[/yellow]", "3 rolls remaining")
    table.add_row("Developer", "[green]✓ Ready[/green]", "Fresh stock")

    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
