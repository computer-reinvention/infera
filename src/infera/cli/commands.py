"""Infera CLI commands - agent handles everything."""

import asyncio
from pathlib import Path

import typer

from infera.cli import output
from infera.core.state import StateManager
from infera.core.exceptions import InferaError


def init_cmd(
    path: Path = typer.Argument(
        Path("."),
        help="Project path to analyze.",
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    provider: str = typer.Option(
        "gcp",
        "--provider",
        "-p",
        help="Cloud provider (gcp, aws, azure).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-y",
        help="Skip prompts, use defaults.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output.",
    ),
) -> None:
    """Analyze codebase and create infrastructure config."""
    output.set_verbose(verbose)
    try:
        asyncio.run(_init_async(path, provider, non_interactive))
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _init_async(path: Path, provider: str, non_interactive: bool) -> None:
    from infera.agent import InferaAgent

    output.banner()
    output.step_start("Analyzing your codebase...")

    agent = InferaAgent(project_root=path.resolve(), provider=provider)

    with output.spinner("AI is analyzing your project"):
        config = await agent.analyze_and_configure(non_interactive=non_interactive)

    output.step_done("Analysis complete")

    if config.detected_frameworks:
        output.detected("Frameworks", config.detected_frameworks)
    if config.has_dockerfile:
        output.detected("Docker", ["Dockerfile found"])
    output.detected("Architecture", [config.architecture_type or "unknown"])

    output.display_config_summary(config.model_dump())

    state = StateManager(path.resolve())
    state.save_config(config)

    output.success_box("Ready!", "Configuration saved to .infera/config.yaml")
    output.next_steps([
        "Review config: [cyan]cat .infera/config.yaml[/cyan]",
        "Generate Terraform & plan: [cyan]infera plan[/cyan]",
        "Deploy: [cyan]infera apply[/cyan]",
    ])


def plan_cmd(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
) -> None:
    """Generate Terraform files and run terraform plan."""
    output.set_verbose(verbose)
    try:
        asyncio.run(_plan_async(quiet))
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _plan_async(quiet: bool) -> None:
    from infera.agent import InferaAgent

    output.banner()

    state = StateManager(Path.cwd())
    config = state.load_config()

    if config is None:
        output.error("No config found. Run [cyan]infera init[/cyan] first.")
        raise typer.Exit(1)

    output.step_start(f"Planning [cyan]{config.project_name}[/cyan]")
    output.info(f"Provider: {config.provider} | Region: {config.region}")

    agent = InferaAgent(project_root=Path.cwd(), provider=config.provider)

    output.step_start("Generating Terraform configuration...")
    with output.spinner("AI is writing Terraform files"):
        await agent.generate_terraform_and_plan()

    output.step_done("Terraform generated")

    # Show terraform plan output if exists
    plan_output_file = state.infera_dir / "terraform" / "plan_output.txt"
    if plan_output_file.exists() and not quiet:
        output.console.print("\n[bold]Terraform Plan:[/bold]")
        output.console.print(f"[dim]{plan_output_file.read_text()[:2000]}[/dim]")

    output.success_box("Plan Ready", "Run 'infera apply' to deploy")
    output.next_steps([
        "Review Terraform: [cyan]cat .infera/terraform/main.tf[/cyan]",
        "Apply changes: [cyan]infera apply[/cyan]",
    ])


def apply_cmd(
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Skip confirmation."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
) -> None:
    """Run terraform apply to provision infrastructure."""
    output.set_verbose(verbose)
    try:
        asyncio.run(_apply_async(auto_approve))
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _apply_async(auto_approve: bool) -> None:
    from infera.agent import InferaAgent

    output.banner()

    state = StateManager(Path.cwd())
    config = state.load_config()

    if config is None:
        output.error("No config found. Run [cyan]infera init[/cyan] first.")
        raise typer.Exit(1)

    tf_dir = state.infera_dir / "terraform"
    if not (tf_dir / "main.tf").exists():
        output.error("No Terraform files. Run [cyan]infera plan[/cyan] first.")
        raise typer.Exit(1)

    output.step_start(f"Applying [cyan]{config.project_name}[/cyan]")
    output.info(f"Resources: {len(config.resources)}")

    if not auto_approve:
        if not output.confirm("Apply infrastructure changes?", default=False):
            output.warn("Cancelled")
            raise typer.Exit(0)

    agent = InferaAgent(project_root=Path.cwd(), provider=config.provider)

    with output.spinner("Running terraform apply"):
        await agent.apply_terraform()

    output.step_done("Apply complete")
    output.success_box("Deployed!", "Infrastructure is live")
    output.next_steps([
        "Check outputs: [cyan]terraform -chdir=.infera/terraform output[/cyan]",
        "Destroy: [cyan]infera destroy[/cyan]",
    ])


def destroy_cmd(
    auto_approve: bool = typer.Option(False, "--auto-approve", "-y", help="Skip confirmation."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
) -> None:
    """Run terraform destroy to remove infrastructure."""
    output.set_verbose(verbose)
    try:
        asyncio.run(_destroy_async(auto_approve))
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _destroy_async(auto_approve: bool) -> None:
    from infera.agent import InferaAgent

    output.banner()

    state = StateManager(Path.cwd())
    config = state.load_config()

    if config is None:
        output.error("No config found. Nothing to destroy.")
        raise typer.Exit(1)

    output.step_start("Resources to destroy:")
    for r in config.resources:
        output.console.print(f"  [red]- {r.type}[/red]: {r.name}")

    output.warn("This cannot be undone!")

    if not auto_approve:
        if not output.confirm("Destroy all resources?", default=False):
            output.warn("Cancelled")
            raise typer.Exit(0)

    agent = InferaAgent(project_root=Path.cwd(), provider=config.provider)

    with output.spinner("Running terraform destroy"):
        await agent.destroy_terraform()

    output.step_done("Destroy complete")
    output.success_box("Destroyed", "All resources removed")


def status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output."),
) -> None:
    """Show current project state."""
    output.set_verbose(verbose)
    state = StateManager(Path.cwd())
    config = state.load_config()

    if config is None:
        output.error("No Infera project found.")
        output.next_steps(["Initialize: [cyan]infera init[/cyan]"])
        raise typer.Exit(1)

    if json_output:
        output.console.print(config.model_dump_json(indent=2))
    else:
        output.banner()
        output.display_config_summary(config.model_dump())

        tf_dir = state.infera_dir / "terraform"
        if (tf_dir / "main.tf").exists():
            output.step_done("Terraform files exist")
        else:
            output.info("No Terraform files yet")

        output.next_steps([
            "Generate plan: [cyan]infera plan[/cyan]",
            "Apply: [cyan]infera apply[/cyan]",
        ])
