"""Preflight checks for deployment readiness."""

import asyncio
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from infera.core.exceptions import PreflightError  # noqa: F401


class CheckStatus(Enum):
    """Status of a preflight check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single preflight check."""

    name: str
    status: CheckStatus
    message: str
    fix_instructions: list[str] = field(default_factory=list)
    details: str | None = None


@dataclass
class PreflightResult:
    """Aggregated result of all preflight checks."""

    provider: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if all critical checks passed."""
        return all(
            c.status in (CheckStatus.PASSED, CheckStatus.WARNING, CheckStatus.SKIPPED)
            for c in self.checks
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(c.status == CheckStatus.WARNING for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        """Get list of failed checks."""
        return [c for c in self.checks if c.status == CheckStatus.FAILED]

    def summary(self) -> str:
        """Generate summary string."""
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASSED)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAILED)
        warnings = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)
        return f"Preflight: {passed} passed, {failed} failed, {warnings} warnings"


class PreflightChecker:
    """Run preflight checks before deployment."""

    # Provider-specific CLI tools
    PROVIDER_CLIS = {
        "gcp": "gcloud",
        "aws": "aws",
        "cloudflare": "wrangler",
        "azure": "az",
    }

    def __init__(self, provider: Literal["gcp", "aws", "cloudflare", "azure"]):
        self.provider = provider

    async def run_all(self) -> PreflightResult:
        """Run all preflight checks for the provider."""
        result = PreflightResult(provider=self.provider)

        # Common checks
        result.checks.append(await self.check_cli_installed())
        result.checks.append(await self.check_authentication())

        # Provider-specific checks
        if self.provider == "gcp":
            result.checks.append(await self.check_gcp_project())
            result.checks.append(await self.check_gcp_billing())
            result.checks.append(await self.check_gcp_apis())
        elif self.provider == "aws":
            result.checks.append(await self.check_aws_region())
            result.checks.append(await self.check_aws_credentials())
        elif self.provider == "cloudflare":
            result.checks.append(await self.check_cloudflare_account())

        # Optional checks
        result.checks.append(await self.check_docker_installed())
        result.checks.append(await self.check_terraform_installed())

        return result

    async def check_cli_installed(self) -> CheckResult:
        """Check if the provider CLI is installed."""
        cli = self.PROVIDER_CLIS.get(self.provider)
        if not cli:
            return CheckResult(
                name="CLI Installed",
                status=CheckStatus.SKIPPED,
                message=f"Unknown provider: {self.provider}",
            )

        if shutil.which(cli):
            # Get version
            version = await self._get_cli_version(cli)
            return CheckResult(
                name="CLI Installed",
                status=CheckStatus.PASSED,
                message=f"{cli} is installed",
                details=version,
            )
        else:
            return CheckResult(
                name="CLI Installed",
                status=CheckStatus.FAILED,
                message=f"{cli} CLI not found",
                fix_instructions=self._get_cli_install_instructions(),
            )

    async def check_authentication(self) -> CheckResult:
        """Check if authenticated with the provider."""
        if self.provider == "gcp":
            return await self._check_gcp_auth()
        elif self.provider == "aws":
            return await self._check_aws_auth()
        elif self.provider == "cloudflare":
            return await self._check_cloudflare_auth()
        elif self.provider == "azure":
            return await self._check_azure_auth()
        else:
            return CheckResult(
                name="Authentication",
                status=CheckStatus.SKIPPED,
                message=f"Unknown provider: {self.provider}",
            )

    async def check_gcp_project(self) -> CheckResult:
        """Check if GCP project is configured."""
        try:
            result = await self._run_command(
                ["gcloud", "config", "get-value", "project"]
            )
            project = result.strip()
            if project and project != "(unset)":
                return CheckResult(
                    name="GCP Project",
                    status=CheckStatus.PASSED,
                    message=f"Project: {project}",
                )
            else:
                return CheckResult(
                    name="GCP Project",
                    status=CheckStatus.FAILED,
                    message="No GCP project configured",
                    fix_instructions=[
                        "Run: gcloud config set project YOUR_PROJECT_ID",
                        "Or set GOOGLE_CLOUD_PROJECT environment variable",
                    ],
                )
        except Exception as e:
            return CheckResult(
                name="GCP Project",
                status=CheckStatus.FAILED,
                message=f"Failed to check project: {e}",
            )

    async def check_gcp_billing(self) -> CheckResult:
        """Check if GCP billing is enabled."""
        try:
            result = await self._run_command(
                ["gcloud", "config", "get-value", "project"]
            )
            project = result.strip()
            if not project or project == "(unset)":
                return CheckResult(
                    name="GCP Billing",
                    status=CheckStatus.SKIPPED,
                    message="No project configured",
                )

            # Check billing
            billing_result = await self._run_command(
                [
                    "gcloud",
                    "billing",
                    "projects",
                    "describe",
                    project,
                    "--format=value(billingEnabled)",
                ],
                check=False,
            )

            if billing_result.strip().lower() == "true":
                return CheckResult(
                    name="GCP Billing",
                    status=CheckStatus.PASSED,
                    message="Billing is enabled",
                )
            else:
                return CheckResult(
                    name="GCP Billing",
                    status=CheckStatus.WARNING,
                    message="Billing may not be enabled",
                    fix_instructions=[
                        "Visit: https://console.cloud.google.com/billing",
                        "Link a billing account to your project",
                    ],
                )
        except Exception:
            return CheckResult(
                name="GCP Billing",
                status=CheckStatus.WARNING,
                message="Could not verify billing status",
                fix_instructions=[
                    "Ensure billing is enabled at: https://console.cloud.google.com/billing",
                ],
            )

    async def check_gcp_apis(self) -> CheckResult:
        """Check if required GCP APIs are enabled."""
        required_apis = [
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "artifactregistry.googleapis.com",
        ]

        try:
            result = await self._run_command(
                [
                    "gcloud",
                    "services",
                    "list",
                    "--enabled",
                    "--format=value(config.name)",
                ]
            )
            enabled_apis = set(result.strip().split("\n"))

            missing = [api for api in required_apis if api not in enabled_apis]

            if not missing:
                return CheckResult(
                    name="GCP APIs",
                    status=CheckStatus.PASSED,
                    message="Required APIs are enabled",
                )
            else:
                return CheckResult(
                    name="GCP APIs",
                    status=CheckStatus.WARNING,
                    message=f"Some APIs may need enabling: {', '.join(missing)}",
                    fix_instructions=[
                        f"Run: gcloud services enable {' '.join(missing)}",
                    ],
                )
        except Exception:
            return CheckResult(
                name="GCP APIs",
                status=CheckStatus.WARNING,
                message="Could not verify API status",
            )

    async def check_aws_region(self) -> CheckResult:
        """Check if AWS region is configured."""
        import os

        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

        if region:
            return CheckResult(
                name="AWS Region",
                status=CheckStatus.PASSED,
                message=f"Region: {region}",
            )

        # Try to get from config
        try:
            result = await self._run_command(
                ["aws", "configure", "get", "region"], check=False
            )
            region = result.strip()
            if region:
                return CheckResult(
                    name="AWS Region",
                    status=CheckStatus.PASSED,
                    message=f"Region: {region}",
                )
        except Exception:
            pass

        return CheckResult(
            name="AWS Region",
            status=CheckStatus.FAILED,
            message="No AWS region configured",
            fix_instructions=[
                "Set AWS_REGION environment variable",
                "Or run: aws configure",
            ],
        )

    async def check_aws_credentials(self) -> CheckResult:
        """Check if AWS credentials are valid."""
        try:
            result = await self._run_command(
                ["aws", "sts", "get-caller-identity", "--output", "json"]
            )
            import json

            identity = json.loads(result)
            return CheckResult(
                name="AWS Credentials",
                status=CheckStatus.PASSED,
                message=f"Account: {identity.get('Account', 'unknown')}",
            )
        except Exception:
            return CheckResult(
                name="AWS Credentials",
                status=CheckStatus.FAILED,
                message="AWS credentials invalid or expired",
                fix_instructions=[
                    "Run: aws configure",
                    "Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
                ],
            )

    async def check_cloudflare_account(self) -> CheckResult:
        """Check Cloudflare account configuration."""
        import os

        if os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get(
            "CLOUDFLARE_ACCOUNT_ID"
        ):
            return CheckResult(
                name="Cloudflare Account",
                status=CheckStatus.PASSED,
                message="Cloudflare credentials found in environment",
            )

        return CheckResult(
            name="Cloudflare Account",
            status=CheckStatus.WARNING,
            message="Cloudflare credentials not in environment (may be in wrangler.toml)",
        )

    async def check_docker_installed(self) -> CheckResult:
        """Check if Docker is installed (optional)."""
        if shutil.which("docker"):
            try:
                result = await self._run_command(["docker", "--version"])
                return CheckResult(
                    name="Docker",
                    status=CheckStatus.PASSED,
                    message="Docker is installed",
                    details=result.strip(),
                )
            except Exception:
                return CheckResult(
                    name="Docker",
                    status=CheckStatus.WARNING,
                    message="Docker installed but not running",
                    fix_instructions=["Start Docker Desktop or docker daemon"],
                )
        else:
            return CheckResult(
                name="Docker",
                status=CheckStatus.WARNING,
                message="Docker not installed (may be needed for container builds)",
                fix_instructions=[
                    "Install Docker: https://docs.docker.com/get-docker/"
                ],
            )

    async def check_terraform_installed(self) -> CheckResult:
        """Check if Terraform is installed."""
        if shutil.which("terraform"):
            try:
                result = await self._run_command(["terraform", "--version"])
                version_line = result.strip().split("\n")[0]
                return CheckResult(
                    name="Terraform",
                    status=CheckStatus.PASSED,
                    message="Terraform is installed",
                    details=version_line,
                )
            except Exception:
                pass

        return CheckResult(
            name="Terraform",
            status=CheckStatus.WARNING,
            message="Terraform not installed",
            fix_instructions=[
                "Install: https://developer.hashicorp.com/terraform/downloads",
                "Or: brew install terraform (macOS)",
            ],
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _check_gcp_auth(self) -> CheckResult:
        """Check GCP authentication."""
        try:
            result = await self._run_command(
                ["gcloud", "auth", "list", "--format=value(account)"]
            )
            accounts = [a for a in result.strip().split("\n") if a]
            if accounts:
                return CheckResult(
                    name="Authentication",
                    status=CheckStatus.PASSED,
                    message=f"Authenticated as: {accounts[0]}",
                )
            else:
                return CheckResult(
                    name="Authentication",
                    status=CheckStatus.FAILED,
                    message="Not authenticated with GCP",
                    fix_instructions=[
                        "Run: gcloud auth login",
                        "For service accounts: gcloud auth activate-service-account --key-file=KEY_FILE",
                    ],
                )
        except Exception as e:
            return CheckResult(
                name="Authentication",
                status=CheckStatus.FAILED,
                message=f"Failed to check authentication: {e}",
            )

    async def _check_aws_auth(self) -> CheckResult:
        """Check AWS authentication."""
        try:
            await self._run_command(["aws", "sts", "get-caller-identity"])
            return CheckResult(
                name="Authentication",
                status=CheckStatus.PASSED,
                message="Authenticated with AWS",
            )
        except Exception:
            return CheckResult(
                name="Authentication",
                status=CheckStatus.FAILED,
                message="Not authenticated with AWS",
                fix_instructions=[
                    "Run: aws configure",
                    "Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                ],
            )

    async def _check_cloudflare_auth(self) -> CheckResult:
        """Check Cloudflare authentication."""
        try:
            result = await self._run_command(["npx", "wrangler", "whoami"])
            if "Not logged in" in result:
                return CheckResult(
                    name="Authentication",
                    status=CheckStatus.FAILED,
                    message="Not authenticated with Cloudflare",
                    fix_instructions=["Run: npx wrangler login"],
                )
            return CheckResult(
                name="Authentication",
                status=CheckStatus.PASSED,
                message="Authenticated with Cloudflare",
            )
        except Exception:
            return CheckResult(
                name="Authentication",
                status=CheckStatus.WARNING,
                message="Could not verify Cloudflare authentication",
                fix_instructions=["Run: npx wrangler login"],
            )

    async def _check_azure_auth(self) -> CheckResult:
        """Check Azure authentication."""
        try:
            await self._run_command(["az", "account", "show"])
            return CheckResult(
                name="Authentication",
                status=CheckStatus.PASSED,
                message="Authenticated with Azure",
            )
        except Exception:
            return CheckResult(
                name="Authentication",
                status=CheckStatus.FAILED,
                message="Not authenticated with Azure",
                fix_instructions=["Run: az login"],
            )

    async def _get_cli_version(self, cli: str) -> str:
        """Get CLI version string."""
        try:
            if cli == "gcloud":
                result = await self._run_command(["gcloud", "--version"])
                return result.strip().split("\n")[0]
            elif cli == "aws":
                result = await self._run_command(["aws", "--version"])
                return result.strip()
            elif cli == "wrangler":
                result = await self._run_command(["npx", "wrangler", "--version"])
                return result.strip()
            elif cli == "az":
                result = await self._run_command(["az", "--version"])
                return result.strip().split("\n")[0]
        except Exception:
            pass
        return "unknown version"

    def _get_cli_install_instructions(self) -> list[str]:
        """Get installation instructions for the provider CLI."""
        if self.provider == "gcp":
            return [
                "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
                "After install, run: gcloud init",
            ]
        elif self.provider == "aws":
            return [
                "Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
                "After install, run: aws configure",
            ]
        elif self.provider == "cloudflare":
            return [
                "Wrangler is installed via npm: npm install -g wrangler",
                "Or use npx: npx wrangler",
            ]
        elif self.provider == "azure":
            return [
                "Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli",
                "After install, run: az login",
            ]
        return []

    async def _run_command(self, cmd: list[str], check: bool = True) -> str:
        """Run a command and return output."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode or 1, cmd, stdout, stderr
            )

        return stdout.decode("utf-8")
