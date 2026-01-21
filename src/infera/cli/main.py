"""Infera CLI - Main entry point."""

from typing import Optional

import typer
from rich.console import Console

from infera import __version__
from infera.cli.commands import init_cmd, plan_cmd, apply_cmd, destroy_cmd, status_cmd

app = typer.Typer(
    name="infera",
    help="Agentic infrastructure provisioning from code analysis.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"infera version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Minimal output (summary only).",
    ),
) -> None:
    """Infera - Agentic infrastructure provisioning from code analysis."""
    pass


# Register commands
app.command(name="init")(init_cmd)
app.command(name="plan")(plan_cmd)
app.command(name="apply")(apply_cmd)
app.command(name="destroy")(destroy_cmd)
app.command(name="status")(status_cmd)


if __name__ == "__main__":
    app()
