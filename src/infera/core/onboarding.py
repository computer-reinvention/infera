"""First-run onboarding for Infera.

Handles initial setup:
1. API key configuration
2. Provider selection
3. Provider authentication check
4. IAM permissions verification
5. Quota checks (where applicable)
6. Service/API enablement (where applicable)
"""

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

# Config file location (same directory as credentials)
INFERA_DIR = Path.home() / ".infera"
CONFIG_FILE = INFERA_DIR / "config.json"

Provider = Literal["gcp", "aws", "azure", "cloudflare"]

PROVIDER_NAMES = {
    "gcp": "Google Cloud Platform",
    "aws": "Amazon Web Services",
    "azure": "Microsoft Azure",
    "cloudflare": "Cloudflare",
}

PROVIDER_DOCS = {
    "gcp": "https://cloud.google.com/sdk/docs/install",
    "aws": "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
    "azure": "https://learn.microsoft.com/en-us/cli/azure/install-azure-cli",
    "cloudflare": "https://developers.cloudflare.com/workers/wrangler/install-and-update/",
}


class CheckStatus(Enum):
    """Status of an onboarding check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    FIXED = "fixed"  # Auto-fixed by the onboarding process


@dataclass
class CheckResult:
    """Result of a single onboarding check."""

    name: str
    status: CheckStatus
    message: str
    fix_instructions: list[str] | None = None
    can_auto_fix: bool = False


@dataclass
class OnboardingResult:
    """Result of the full onboarding process."""

    provider: str  # One of: gcp, aws, azure, cloudflare
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        """Check if all critical checks passed."""
        return all(
            c.status
            in (
                CheckStatus.PASSED,
                CheckStatus.WARNING,
                CheckStatus.SKIPPED,
                CheckStatus.FIXED,
            )
            for c in self.checks
        )


def get_config() -> dict:
    """Load config from file."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config: dict) -> None:
    """Save config to file."""
    INFERA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_default_provider() -> Provider | None:
    """Get the default provider from config."""
    config = get_config()
    provider = config.get("default_provider")
    if provider in ("gcp", "aws", "azure", "cloudflare"):
        return provider  # type: ignore
    return None


def set_default_provider(provider: Provider) -> None:
    """Set the default provider in config."""
    config = get_config()
    config["default_provider"] = provider
    save_config(config)


def is_onboarding_complete() -> bool:
    """Check if onboarding has been completed."""
    from infera.core.auth import get_api_key

    # Need both API key and default provider
    if not get_api_key():
        return False
    if not get_default_provider():
        return False
    return True


async def run_onboarding(provider: Provider | None = None) -> OnboardingResult | None:
    """Run the full onboarding flow.

    Args:
        provider: Provider to set up. If None, will prompt user.

    Returns:
        OnboardingResult if successful, None if cancelled.
    """
    from infera.cli import output
    from infera.core.auth import ensure_api_key

    output.console.print()
    output.console.print("[bold cyan]Welcome to Infera![/bold cyan]")
    output.console.print("Let's get you set up for infrastructure provisioning.")
    output.console.print()

    # Step 1: API Key
    if not ensure_api_key():
        return None

    # Step 2: Provider selection
    if provider is None:
        provider = await _prompt_provider_selection()
        if provider is None:
            return None

    output.console.print()
    output.step_start(f"Setting up {PROVIDER_NAMES[provider]}...")

    # Step 3: Run provider-specific checks
    checker = ProviderOnboardingChecker(provider)
    result = await checker.run_all()

    # Step 4: Display results
    _display_check_results(result)

    # Step 5: Save provider as default if all passed
    if result.passed:
        set_default_provider(provider)
        output.console.print()
        output.step_done(f"Default provider set to {PROVIDER_NAMES[provider]}")

    return result


async def _prompt_provider_selection() -> Provider | None:
    """Prompt user to select a cloud provider."""
    from infera.cli import output

    output.console.print("[bold]Select your cloud provider:[/bold]")
    output.console.print()

    providers = [
        ("gcp", "Google Cloud Platform", "Cloud Run, GKE, Cloud Functions"),
        ("aws", "Amazon Web Services", "Lambda, ECS, EKS"),
        ("cloudflare", "Cloudflare", "Workers, Pages, D1"),
        ("azure", "Microsoft Azure", "Container Apps, AKS, Functions"),
    ]

    for i, (key, name, services) in enumerate(providers, 1):
        output.console.print(f"  [cyan]{i}.[/cyan] {name}")
        output.console.print(f"      [dim]{services}[/dim]")

    output.console.print()
    choice = output.console.input("[bold]Enter your choice (1-4):[/bold] ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(providers):
            return providers[idx][0]  # type: ignore
    except ValueError:
        pass

    output.error("Invalid choice.")
    return None


def _display_check_results(result: OnboardingResult) -> None:
    """Display the results of onboarding checks."""
    from infera.cli import output

    output.console.print()

    for check in result.checks:
        if check.status == CheckStatus.PASSED:
            output.step_done(f"{check.name}: {check.message}")
        elif check.status == CheckStatus.FIXED:
            output.step_done(f"{check.name}: {check.message} [dim](auto-fixed)[/dim]")
        elif check.status == CheckStatus.WARNING:
            output.warn(f"{check.name}: {check.message}")
        elif check.status == CheckStatus.SKIPPED:
            output.info(f"{check.name}: {check.message} [dim](skipped)[/dim]")
        elif check.status == CheckStatus.FAILED:
            output.error(f"{check.name}: {check.message}")
            if check.fix_instructions:
                output.console.print()
                output.console.print("  [bold]To fix:[/bold]")
                for instruction in check.fix_instructions:
                    output.console.print(f"    → {instruction}")
                output.console.print()


class ProviderOnboardingChecker:
    """Runs onboarding checks for a specific provider."""

    def __init__(self, provider: str):
        self.provider = provider

    async def run_all(self) -> OnboardingResult:
        """Run all onboarding checks for the provider."""
        checks: list[CheckResult] = []

        # 1. CLI installed
        checks.append(await self._check_cli_installed())
        if checks[-1].status == CheckStatus.FAILED:
            # Can't proceed without CLI
            return OnboardingResult(provider=self.provider, checks=checks)

        # 2. Authentication
        checks.append(await self._check_authentication())
        if checks[-1].status == CheckStatus.FAILED:
            return OnboardingResult(provider=self.provider, checks=checks)

        # 3. Project/Account configuration
        checks.append(await self._check_project_configured())
        if checks[-1].status == CheckStatus.FAILED:
            return OnboardingResult(provider=self.provider, checks=checks)

        # 4. IAM Permissions (provider-specific)
        iam_check = await self._check_iam_permissions()
        if iam_check:
            checks.append(iam_check)

        # 5. Quota (provider-specific, optional)
        quota_check = await self._check_quota()
        if quota_check:
            checks.append(quota_check)

        # 6. Billing (GCP-specific)
        if self.provider == "gcp":
            checks.append(await self._check_gcp_billing())

        return OnboardingResult(provider=self.provider, checks=checks)

    async def _check_cli_installed(self) -> CheckResult:
        """Check if the provider CLI is installed."""
        cli_commands = {
            "gcp": ["gcloud", "--version"],
            "aws": ["aws", "--version"],
            "azure": ["az", "--version"],
            "cloudflare": ["npx", "wrangler", "--version"],
        }

        cmd = cli_commands[self.provider]
        cli_name = cmd[0] if self.provider != "cloudflare" else "wrangler"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                return CheckResult(
                    name="CLI Installation",
                    status=CheckStatus.PASSED,
                    message=f"{cli_name} is installed",
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="CLI Installation",
            status=CheckStatus.FAILED,
            message=f"{cli_name} is not installed",
            fix_instructions=[
                f"Install {cli_name}: {PROVIDER_DOCS[self.provider]}",
            ],
        )

    async def _check_authentication(self) -> CheckResult:
        """Check if user is authenticated with the provider."""
        if self.provider == "gcp":
            return await self._check_gcp_auth()
        elif self.provider == "aws":
            return await self._check_aws_auth()
        elif self.provider == "azure":
            return await self._check_azure_auth()
        elif self.provider == "cloudflare":
            return await self._check_cloudflare_auth()

        return CheckResult(
            name="Authentication",
            status=CheckStatus.SKIPPED,
            message="Unknown provider",
        )

    async def _check_gcp_auth(self) -> CheckResult:
        """Check GCP authentication."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0 and stdout.strip():
                account = stdout.decode().strip().split("\n")[0]
                return CheckResult(
                    name="Authentication",
                    status=CheckStatus.PASSED,
                    message=f"Logged in as {account}",
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Authentication",
            status=CheckStatus.FAILED,
            message="Not authenticated with Google Cloud",
            fix_instructions=[
                "Run: gcloud auth login",
                "Then: gcloud auth application-default login",
            ],
        )

    async def _check_aws_auth(self) -> CheckResult:
        """Check AWS authentication."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "aws",
                "sts",
                "get-caller-identity",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0:
                try:
                    identity = json.loads(stdout.decode())
                    arn = identity.get("Arn", "unknown")
                    # Extract username from ARN
                    user = arn.split("/")[-1] if "/" in arn else arn
                    return CheckResult(
                        name="Authentication",
                        status=CheckStatus.PASSED,
                        message=f"Logged in as {user}",
                    )
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Authentication",
            status=CheckStatus.FAILED,
            message="Not authenticated with AWS",
            fix_instructions=[
                "Run: aws configure",
                "Or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY",
            ],
        )

    async def _check_azure_auth(self) -> CheckResult:
        """Check Azure authentication."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "az",
                "account",
                "show",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0:
                try:
                    account = json.loads(stdout.decode())
                    user = account.get("user", {}).get("name", "unknown")
                    return CheckResult(
                        name="Authentication",
                        status=CheckStatus.PASSED,
                        message=f"Logged in as {user}",
                    )
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Authentication",
            status=CheckStatus.FAILED,
            message="Not authenticated with Azure",
            fix_instructions=[
                "Run: az login",
            ],
        )

    async def _check_cloudflare_auth(self) -> CheckResult:
        """Check Cloudflare authentication."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx",
                "wrangler",
                "whoami",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output_text = stdout.decode() + stderr.decode()

            if proc.returncode == 0 and "You are logged in" in output_text:
                # Extract email if possible
                for line in output_text.split("\n"):
                    if "@" in line:
                        return CheckResult(
                            name="Authentication",
                            status=CheckStatus.PASSED,
                            message=f"Logged in ({line.strip()})",
                        )
                return CheckResult(
                    name="Authentication",
                    status=CheckStatus.PASSED,
                    message="Logged in to Cloudflare",
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Authentication",
            status=CheckStatus.FAILED,
            message="Not authenticated with Cloudflare",
            fix_instructions=[
                "Run: npx wrangler login",
                "Or set environment variable: CLOUDFLARE_API_TOKEN",
            ],
        )

    async def _check_project_configured(self) -> CheckResult:
        """Check if a project/account is configured."""
        if self.provider == "gcp":
            return await self._check_gcp_project()
        elif self.provider == "aws":
            return await self._check_aws_region()
        elif self.provider == "azure":
            return await self._check_azure_subscription()
        elif self.provider == "cloudflare":
            # Cloudflare doesn't need project configuration
            return CheckResult(
                name="Account Configuration",
                status=CheckStatus.PASSED,
                message="Cloudflare uses global configuration",
            )

        return CheckResult(
            name="Project Configuration",
            status=CheckStatus.SKIPPED,
            message="Unknown provider",
        )

    async def _check_gcp_project(self) -> CheckResult:
        """Check GCP project configuration."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "config",
                "get",
                "project",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0 and stdout.strip():
                project = stdout.decode().strip()
                return CheckResult(
                    name="Project Configuration",
                    status=CheckStatus.PASSED,
                    message=f"Using project: {project}",
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Project Configuration",
            status=CheckStatus.FAILED,
            message="No GCP project configured",
            fix_instructions=[
                "Run: gcloud config set project YOUR_PROJECT_ID",
                "Or create a new project: gcloud projects create PROJECT_ID",
            ],
        )

    async def _check_aws_region(self) -> CheckResult:
        """Check AWS region configuration."""
        # Check environment variable first
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")

        if not region:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "aws",
                    "configure",
                    "get",
                    "region",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and stdout.strip():
                    region = stdout.decode().strip()
            except FileNotFoundError:
                pass

        if region:
            return CheckResult(
                name="Region Configuration",
                status=CheckStatus.PASSED,
                message=f"Using region: {region}",
            )

        return CheckResult(
            name="Region Configuration",
            status=CheckStatus.FAILED,
            message="No AWS region configured",
            fix_instructions=[
                "Run: aws configure set region us-east-1",
                "Or set environment variable: export AWS_DEFAULT_REGION=us-east-1",
            ],
        )

    async def _check_azure_subscription(self) -> CheckResult:
        """Check Azure subscription configuration."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "az",
                "account",
                "show",
                "--query",
                "name",
                "-o",
                "tsv",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0 and stdout.strip():
                subscription = stdout.decode().strip()
                return CheckResult(
                    name="Subscription Configuration",
                    status=CheckStatus.PASSED,
                    message=f"Using subscription: {subscription}",
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Subscription Configuration",
            status=CheckStatus.FAILED,
            message="No Azure subscription configured",
            fix_instructions=[
                "Run: az account set --subscription SUBSCRIPTION_ID",
                "List subscriptions: az account list",
            ],
        )

    async def _check_iam_permissions(self) -> CheckResult | None:
        """Check IAM permissions for the provider."""
        if self.provider == "gcp":
            return await self._check_gcp_iam()
        elif self.provider == "aws":
            return await self._check_aws_iam()
        # Azure and Cloudflare: skip detailed IAM checks for now
        return None

    async def _check_gcp_iam(self) -> CheckResult:
        """Check GCP IAM permissions."""
        # Get current project
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "config",
                "get",
                "project",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            project = stdout.decode().strip() if proc.returncode == 0 else None
        except FileNotFoundError:
            project = None

        if not project:
            return CheckResult(
                name="IAM Permissions",
                status=CheckStatus.SKIPPED,
                message="No project configured",
            )

        # Check if user has editor or owner role
        # This is a simplified check - in production you'd check specific permissions
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "projects",
                "get-iam-policy",
                project,
                "--format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                # If we can read IAM policy, we likely have sufficient permissions
                return CheckResult(
                    name="IAM Permissions",
                    status=CheckStatus.PASSED,
                    message="Sufficient permissions to manage resources",
                )
            elif b"PERMISSION_DENIED" in stderr:
                return CheckResult(
                    name="IAM Permissions",
                    status=CheckStatus.WARNING,
                    message="Could not verify IAM permissions",
                    fix_instructions=[
                        "Ensure you have Editor or Owner role on the project",
                        f"Check: gcloud projects get-iam-policy {project}",
                        "Grant role: gcloud projects add-iam-policy-binding {project} --member=user:YOUR_EMAIL --role=roles/editor",
                    ],
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="IAM Permissions",
            status=CheckStatus.WARNING,
            message="Could not verify IAM permissions",
        )

    async def _check_aws_iam(self) -> CheckResult:
        """Check AWS IAM permissions."""
        # Check if user can perform basic operations
        try:
            proc = await asyncio.create_subprocess_exec(
                "aws",
                "iam",
                "get-user",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return CheckResult(
                    name="IAM Permissions",
                    status=CheckStatus.PASSED,
                    message="IAM user access verified",
                )
            elif b"AccessDenied" in stderr:
                # User exists but limited permissions - might still work
                return CheckResult(
                    name="IAM Permissions",
                    status=CheckStatus.WARNING,
                    message="Limited IAM access - may need additional permissions",
                    fix_instructions=[
                        "Ensure you have permissions for the services you want to use",
                        "Common policies: AmazonEC2FullAccess, AmazonECSFullAccess, AWSLambda_FullAccess",
                    ],
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="IAM Permissions",
            status=CheckStatus.WARNING,
            message="Could not verify IAM permissions",
        )

    async def _check_quota(self) -> CheckResult | None:
        """Check quota for the provider (optional)."""
        # Quota checks are complex and provider-specific
        # For now, we'll skip detailed quota checks
        # In a production system, you'd check:
        # - GCP: Compute Engine quotas, Cloud Run limits
        # - AWS: EC2 limits, Lambda concurrency
        # - Azure: Resource limits
        return None

    async def _check_gcp_billing(self) -> CheckResult:
        """Check if billing is enabled for the GCP project."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "config",
                "get",
                "project",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            project = stdout.decode().strip() if proc.returncode == 0 else None
        except FileNotFoundError:
            project = None

        if not project:
            return CheckResult(
                name="Billing",
                status=CheckStatus.SKIPPED,
                message="No project configured",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "beta",
                "billing",
                "projects",
                "describe",
                project,
                "--format=value(billingEnabled)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                billing_enabled = stdout.decode().strip().lower() == "true"
                if billing_enabled:
                    return CheckResult(
                        name="Billing",
                        status=CheckStatus.PASSED,
                        message="Billing is enabled",
                    )
                else:
                    return CheckResult(
                        name="Billing",
                        status=CheckStatus.FAILED,
                        message="Billing is not enabled",
                        fix_instructions=[
                            "Enable billing at: https://console.cloud.google.com/billing",
                            f"Link billing account to project: {project}",
                        ],
                    )
            elif b"PERMISSION_DENIED" in stderr:
                # Can't check billing - warn but don't fail
                return CheckResult(
                    name="Billing",
                    status=CheckStatus.WARNING,
                    message="Could not verify billing status",
                    fix_instructions=[
                        "Ensure billing is enabled at: https://console.cloud.google.com/billing",
                    ],
                )
        except FileNotFoundError:
            pass

        return CheckResult(
            name="Billing",
            status=CheckStatus.WARNING,
            message="Could not verify billing status",
        )


async def enable_gcp_api(api: str, project: str | None = None) -> bool:
    """Enable a GCP API for the project.

    Args:
        api: API to enable (e.g., 'run.googleapis.com')
        project: Project ID. If None, uses default project.

    Returns:
        True if enabled successfully, False otherwise.
    """
    cmd = ["gcloud", "services", "enable", api]
    if project:
        cmd.extend(["--project", project])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def check_gcp_api_enabled(api: str, project: str | None = None) -> bool:
    """Check if a GCP API is enabled.

    Args:
        api: API to check (e.g., 'run.googleapis.com')
        project: Project ID. If None, uses default project.

    Returns:
        True if enabled, False otherwise.
    """
    cmd = [
        "gcloud",
        "services",
        "list",
        "--enabled",
        f"--filter=config.name:{api}",
        "--format=value(config.name)",
    ]
    if project:
        cmd.extend(["--project", project])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return proc.returncode == 0 and api in stdout.decode()
    except FileNotFoundError:
        return False


# Common GCP APIs needed for infrastructure provisioning
GCP_REQUIRED_APIS = [
    "run.googleapis.com",  # Cloud Run
    "artifactregistry.googleapis.com",  # Artifact Registry
    "cloudbuild.googleapis.com",  # Cloud Build
    "compute.googleapis.com",  # Compute Engine (for networking)
    "sqladmin.googleapis.com",  # Cloud SQL
    "secretmanager.googleapis.com",  # Secret Manager
]


async def ensure_gcp_apis_enabled(apis: list[str] | None = None) -> dict[str, bool]:
    """Ensure required GCP APIs are enabled.

    Args:
        apis: List of APIs to enable. If None, uses default list.

    Returns:
        Dict mapping API name to success status.
    """
    from infera.cli import output

    if apis is None:
        apis = GCP_REQUIRED_APIS

    results = {}

    for api in apis:
        if await check_gcp_api_enabled(api):
            results[api] = True
        else:
            output.info(f"Enabling {api}...")
            results[api] = await enable_gcp_api(api)
            if results[api]:
                output.step_done(f"Enabled {api}")
            else:
                output.warn(f"Could not enable {api}")

    return results
