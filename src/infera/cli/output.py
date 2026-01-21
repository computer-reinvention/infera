"""CLI output formatting - create-react-app style."""

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Active spinner reference (for pausing during user input)
_active_spinner = None

# Brand colors
BRAND = "cyan"
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
DIM = "dim"

# Verbose mode state
_verbose_enabled = False


def set_verbose(enabled: bool) -> None:
    """Enable or disable verbose output."""
    global _verbose_enabled
    _verbose_enabled = enabled


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose_enabled


def verbose(message: str) -> None:
    """Show message only in verbose mode."""
    if _verbose_enabled:
        console.print(f"  [{DIM}][verbose][/{DIM}] {message}")


def debug(label: str, value: str) -> None:
    """Show debug info only in verbose mode."""
    if _verbose_enabled:
        console.print(f"  [{DIM}]{label}:[/{DIM}] {value}")


def banner() -> None:
    """Display welcome banner."""
    logo = """
    ╦╔╗╔╔═╗╔═╗╦═╗╔═╗
    ║║║║╠╣ ║╣ ╠╦╝╠═╣
    ╩╝╚╝╚  ╚═╝╩╚═╩ ╩
    """
    console.print(f"[{BRAND}]{logo}[/{BRAND}]")
    console.print(f"  [{DIM}]Infrastructure from code, powered by AI[/{DIM}]\n")


def step_start(message: str) -> None:
    """Show step starting."""
    console.print(f"\n[{BRAND}]→[/{BRAND}] {message}")


def step_done(message: str) -> None:
    """Show step completed."""
    console.print(f"[{SUCCESS}]✓[/{SUCCESS}] {message}")


def step_skip(message: str) -> None:
    """Show step skipped."""
    console.print(f"[{DIM}]○ {message}[/{DIM}]")


def step_fail(message: str) -> None:
    """Show step failed."""
    console.print(f"[{ERROR}]✗[/{ERROR}] {message}")


def info(message: str) -> None:
    """Show info message."""
    console.print(f"  [{DIM}]{message}[/{DIM}]")


def warn(message: str) -> None:
    """Show warning."""
    console.print(f"\n[{WARNING}]⚠[/{WARNING}]  {message}")


def error(message: str) -> None:
    """Show error."""
    console.print(f"\n[{ERROR}]✗[/{ERROR}]  {message}")


def success_box(title: str, message: str) -> None:
    """Show success in a panel."""
    console.print()
    console.print(Panel(
        f"[{SUCCESS}]{message}[/{SUCCESS}]",
        title=f"[bold {SUCCESS}]{title}[/bold {SUCCESS}]",
        border_style=SUCCESS,
    ))


def next_steps(steps: list[str]) -> None:
    """Show next steps to user."""
    console.print(f"\n[bold]Next steps:[/bold]\n")
    for i, step in enumerate(steps, 1):
        console.print(f"  [{BRAND}]{i}.[/{BRAND}] {step}")
    console.print()


@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    """Context manager for spinner during async operations."""
    global _active_spinner
    status = console.status(f"[{BRAND}]{message}[/{BRAND}]", spinner="dots")
    _active_spinner = status
    try:
        with status:
            yield
    finally:
        _active_spinner = None


def pause_spinner() -> None:
    """Pause the active spinner to allow user input."""
    global _active_spinner
    if _active_spinner is not None:
        _active_spinner.stop()


def resume_spinner() -> None:
    """Resume the paused spinner."""
    global _active_spinner
    if _active_spinner is not None:
        _active_spinner.start()


@contextmanager
def progress_steps(steps: list[str]) -> Generator[callable, None, None]:
    """Context manager for multi-step progress."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )

    current_step = [0]
    task_ids = []

    with progress:
        # Add all tasks
        for step in steps:
            task_id = progress.add_task(f"[{DIM}]○ {step}[/{DIM}]", total=1)
            task_ids.append(task_id)

        def advance(success: bool = True):
            if current_step[0] < len(steps):
                idx = current_step[0]
                if success:
                    progress.update(task_ids[idx], description=f"[{SUCCESS}]✓ {steps[idx]}[/{SUCCESS}]", completed=1)
                else:
                    progress.update(task_ids[idx], description=f"[{ERROR}]✗ {steps[idx]}[/{ERROR}]", completed=1)
                current_step[0] += 1

                # Start next step
                if current_step[0] < len(steps):
                    next_idx = current_step[0]
                    progress.update(task_ids[next_idx], description=f"[{BRAND}]→ {steps[next_idx]}[/{BRAND}]")

        # Mark first step as current
        if task_ids:
            progress.update(task_ids[0], description=f"[{BRAND}]→ {steps[0]}[/{BRAND}]")

        yield advance


def agent_thinking(message: str) -> None:
    """Show agent is thinking."""
    console.print(f"  [{DIM}]💭 {message}[/{DIM}]")


def agent_action(tool: str, detail: str = "") -> None:
    """Show agent is taking an action."""
    if detail:
        console.print(f"  [{BRAND}]⚡[/{BRAND}] {tool}: [{DIM}]{detail}[/{DIM}]")
    else:
        console.print(f"  [{BRAND}]⚡[/{BRAND}] {tool}")


def detected(label: str, values: list[str]) -> None:
    """Show detected items."""
    if values:
        items = ", ".join(f"[{BRAND}]{v}[/{BRAND}]" for v in values)
        console.print(f"  [{SUCCESS}]✓[/{SUCCESS}] {label}: {items}")


def display_config_summary(config: dict) -> None:
    """Display config summary in a nice panel."""
    lines = []
    lines.append(f"[bold]Project:[/bold] {config.get('project_name', 'unknown')}")
    lines.append(f"[bold]Provider:[/bold] {config.get('provider', 'unknown')}")
    lines.append(f"[bold]Region:[/bold] {config.get('region', 'unknown')}")
    lines.append(f"[bold]Type:[/bold] {config.get('architecture_type', 'unknown')}")

    resources = config.get('resources', [])
    if resources:
        lines.append(f"\n[bold]Resources ({len(resources)}):[/bold]")
        for r in resources:
            lines.append(f"  • {r.get('type', '?')}: {r.get('name', '?')}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold]Configuration[/bold]",
        border_style=BRAND,
    ))


def confirm(message: str, default: bool = False) -> bool:
    """Interactive confirmation prompt."""
    import typer
    return typer.confirm(f"\n{message}", default=default)


def prompt(message: str, default: str = "") -> str:
    """Interactive text prompt."""
    import typer
    return typer.prompt(f"\n{message}", default=default)


# Backwards compatibility aliases
log_step = step_start
log_success = step_done
log_error = error
log_warning = warn
