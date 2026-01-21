"""Infera CLI commands - agent handles everything."""

import asyncio
from pathlib import Path

import typer

from infera.cli import output
from infera.core.state import StateManager
from infera.core.exceptions import InferaError
from infera.core.auth import ensure_api_key


def _require_api_key() -> None:
    """Ensure API key is available, exit if not."""
    if not ensure_api_key():
        raise typer.Exit(1)


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
        help="Cloud provider (gcp, aws, azure, cloudflare).",
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
    _require_api_key()
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
        # Extract framework names from dicts
        framework_names = [
            str(f.get("name", f)) if isinstance(f, dict) else str(f)
            for f in config.detected_frameworks
        ]
        output.detected("Frameworks", framework_names)
    if config.has_dockerfile:
        output.detected("Docker", ["Dockerfile found"])
    output.detected("Architecture", [config.architecture_type or "unknown"])

    output.display_config_summary(config.model_dump())

    state = StateManager(path.resolve())
    state.save_config(config)

    output.success_box("Ready!", "Configuration saved to .infera/config.yaml")
    output.next_steps(
        [
            "Review config: [cyan]cat .infera/config.yaml[/cyan]",
            "Generate Terraform & plan: [cyan]infera plan[/cyan]",
            "Deploy: [cyan]infera apply[/cyan]",
        ]
    )


def plan_cmd(
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output."
    ),
) -> None:
    """Generate Terraform files and run terraform plan."""
    output.set_verbose(verbose)
    _require_api_key()
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
    with output.spinner("AI is generating and planning infrastructure"):
        await agent.generate_terraform_and_plan()
    # Agent handles success/error messaging and suggests fixes for any issues


def apply_cmd(
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Skip confirmation."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without applying (runs terraform plan).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output."
    ),
) -> None:
    """Run terraform apply to provision infrastructure."""
    output.set_verbose(verbose)
    _require_api_key()
    try:
        asyncio.run(_apply_async(auto_approve, dry_run))
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _apply_async(auto_approve: bool, dry_run: bool = False) -> None:
    from infera.agent import InferaAgent

    output.banner()

    state = StateManager(Path.cwd())
    config = state.load_config()

    if config is None:
        output.error("No config found. Run [cyan]infera init[/cyan] first.")
        raise typer.Exit(1)

    tf_dir = state.infera_dir / "terraform"
    # For Cloudflare, check for wrangler.toml instead of main.tf
    if config.provider == "cloudflare":
        if not (Path.cwd() / "wrangler.toml").exists():
            output.error("No wrangler.toml. Run [cyan]infera plan[/cyan] first.")
            raise typer.Exit(1)
    else:
        if not (tf_dir / "main.tf").exists():
            output.error("No Terraform files. Run [cyan]infera plan[/cyan] first.")
            raise typer.Exit(1)

    if dry_run:
        output.step_start(f"Dry run for [cyan]{config.project_name}[/cyan]")
    else:
        output.step_start(f"Applying [cyan]{config.project_name}[/cyan]")
    output.info(f"Resources: {len(config.resources)}")

    if not dry_run and not auto_approve:
        if not output.confirm("Apply infrastructure changes?", default=False):
            output.warn("Cancelled")
            raise typer.Exit(0)

    agent = InferaAgent(project_root=Path.cwd(), provider=config.provider)

    if dry_run:
        with output.spinner("Running terraform plan (dry run)"):
            await agent.apply_terraform(dry_run=True)
        # Agent handles success/error messaging and suggests fixes
    else:
        with output.spinner("Running terraform apply"):
            await agent.apply_terraform()
        # Agent handles success/error messaging and suggests fixes


def destroy_cmd(
    auto_approve: bool = typer.Option(
        False, "--auto-approve", "-y", help="Skip confirmation."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output."
    ),
) -> None:
    """Run terraform destroy to remove infrastructure."""
    output.set_verbose(verbose)
    _require_api_key()
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
    # Agent handles success/error messaging and suggests fixes for any issues


def status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output JSON."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output."
    ),
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

        output.next_steps(
            [
                "Generate plan: [cyan]infera plan[/cyan]",
                "Apply: [cyan]infera apply[/cyan]",
            ]
        )


def auth_cmd(
    status: bool = typer.Option(
        False, "--status", "-s", help="Show current auth status."
    ),
    update: bool = typer.Option(False, "--update", "-u", help="Update API key."),
) -> None:
    """Manage Anthropic API key authentication."""
    from infera.core.auth import (
        get_api_key,
        save_api_key,
        is_valid_api_key,
        CREDENTIALS_FILE,
    )

    if status or (not status and not update):
        # Show current status
        key = get_api_key()
        if key:
            # Mask the key for display
            masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
            output.step_done(f"API key configured: {masked}")
            output.info(f"Credentials file: {CREDENTIALS_FILE}")
        else:
            output.warn("No API key configured")
            output.next_steps(
                [
                    "Set key: [cyan]infera auth --update[/cyan]",
                    "Or set environment variable: [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]",
                ]
            )
        return

    if update:
        # Update API key
        output.console.print()
        output.console.print(
            "Get your API key at: [link=https://console.anthropic.com/settings/keys]https://console.anthropic.com/settings/keys[/link]"
        )
        output.console.print()

        key = output.console.input(
            "[bold]Enter your Anthropic API key:[/bold] "
        ).strip()

        if not key:
            output.error("No API key provided.")
            raise typer.Exit(1)

        if not is_valid_api_key(key):
            output.warn(
                "This doesn't look like a valid Anthropic API key (should start with 'sk-ant-')."
            )
            if not output.confirm("Save anyway?", default=False):
                raise typer.Exit(1)

        save_api_key(key)
        output.step_done(f"API key saved to {CREDENTIALS_FILE}")


def deploy_cmd(
    path: Path = typer.Argument(
        Path("."),
        help="Project path to deploy.",
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    provider: str = typer.Option(
        "gcp",
        "--provider",
        "-p",
        help="Cloud provider (gcp, aws, azure, cloudflare).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-y",
        help="Skip prompts, use defaults.",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        help="Skip apply confirmation.",
    ),
    skip_preflight: bool = typer.Option(
        False,
        "--skip-preflight",
        help="Skip preflight checks.",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume from last checkpoint.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output.",
    ),
) -> None:
    """Full deployment workflow: analyze, plan, and deploy in one command."""
    output.set_verbose(verbose)
    _require_api_key()
    try:
        asyncio.run(
            _deploy_async(
                path,
                provider,
                non_interactive,
                auto_approve,
                skip_preflight,
                resume,
            )
        )
    except InferaError as e:
        output.error(str(e))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        output.warn("Cancelled")
        raise typer.Exit(130)


async def _deploy_async(
    path: Path,
    provider: str,
    non_interactive: bool,
    auto_approve: bool,
    skip_preflight: bool,
    resume: bool,
) -> None:
    from infera.agent import InferaAgent
    from infera.core.preflight import PreflightChecker, CheckStatus
    from infera.core.phases import (
        DeploymentStateManager,
        DeploymentState,
        DeploymentPhase,
    )

    output.banner()
    project_path = path.resolve()

    # Check for resume state
    state_manager = DeploymentStateManager(project_path)
    deploy_state: DeploymentState | None = None
    resume_from: DeploymentPhase | None = None

    if resume and state_manager.has_state():
        deploy_state = state_manager.load()
        if deploy_state and deploy_state.is_failed:
            resume_from = deploy_state.current_phase
            output.info(
                f"Resuming from: {resume_from.display_name if resume_from else 'unknown'}"
            )

    # Phase 1: Preflight checks
    if not skip_preflight and resume_from not in (
        DeploymentPhase.ANALYSIS,
        DeploymentPhase.PLANNING,
        DeploymentPhase.APPLY,
    ):
        output.step_start("Running preflight checks...")

        checker = PreflightChecker(provider)  # type: ignore
        preflight_result = await checker.run_all()

        # Display results
        for check in preflight_result.checks:
            if check.status == CheckStatus.PASSED:
                output.step_done(f"{check.name}: {check.message}")
            elif check.status == CheckStatus.WARNING:
                output.warn(f"{check.name}: {check.message}")
            elif check.status == CheckStatus.FAILED:
                output.error(f"{check.name}: {check.message}")
                if check.fix_instructions:
                    output.info("Fix:")
                    for instruction in check.fix_instructions:
                        output.console.print(f"  → {instruction}")

        if not preflight_result.passed:
            output.error("Preflight checks failed. Fix the issues above and try again.")
            raise typer.Exit(1)

        output.step_done("Preflight checks passed")

    # Initialize or resume deployment state
    if not deploy_state:
        deploy_state = DeploymentState(
            project_name=project_path.name,
            provider=provider,
        )

    # Run the full deployment workflow via agent
    output.step_start("Starting deployment workflow...")

    agent = InferaAgent(project_root=project_path, provider=provider)

    with output.spinner("AI is analyzing and deploying your project"):
        await agent.deploy_full_workflow(
            non_interactive=non_interactive,
            auto_approve=auto_approve,
            skip_preflight=skip_preflight,
            resume_from=resume_from.value if resume_from else None,
        )

    # Save final state
    if deploy_state:
        deploy_state.complete()
        state_manager.save(deploy_state)
    state_manager.clear()  # Clear on success

    output.success_box("Deployment complete!", "Your infrastructure is now live.")
    output.next_steps(
        [
            "Check status: [cyan]infera status[/cyan]",
            "View logs: [cyan]gcloud run logs read[/cyan]",
            "Destroy: [cyan]infera destroy[/cyan]",
        ]
    )
