"""Deployment phases and state tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class DeploymentPhase(Enum):
    """Phases of the deployment workflow."""

    PREFLIGHT = "preflight"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    COST_PREVIEW = "cost_preview"
    APPLY = "apply"
    VERIFICATION = "verification"
    COMPLETE = "complete"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value

    @property
    def display_name(self) -> str:
        """Human-readable name for the phase."""
        names = {
            "preflight": "Preflight Checks",
            "analysis": "Codebase Analysis",
            "planning": "Infrastructure Planning",
            "cost_preview": "Cost Preview",
            "apply": "Deployment",
            "verification": "Verification",
            "complete": "Complete",
            "failed": "Failed",
        }
        return names.get(self.value, self.value.title())


@dataclass
class PhaseResult:
    """Result of a deployment phase."""

    phase: DeploymentPhase
    status: str  # "success", "failed", "skipped"
    message: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def complete(self, status: str = "success", message: str = "", error: str | None = None) -> None:
        """Mark phase as complete."""
        self.status = status
        self.message = message
        self.completed_at = datetime.now()
        self.error = error

    @property
    def duration_seconds(self) -> float | None:
        """Get duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class DeploymentState:
    """Tracks the state of a deployment workflow."""

    project_name: str
    provider: str
    current_phase: DeploymentPhase = DeploymentPhase.PREFLIGHT
    phases: list[PhaseResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    last_error: str | None = None
    retry_count: int = 0
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def start_phase(self, phase: DeploymentPhase) -> PhaseResult:
        """Start a new phase."""
        self.current_phase = phase
        result = PhaseResult(phase=phase, status="in_progress")
        self.phases.append(result)
        return result

    def complete_phase(self, status: str = "success", message: str = "", error: str | None = None) -> None:
        """Complete the current phase."""
        if self.phases:
            self.phases[-1].complete(status, message, error)
            if error:
                self.last_error = error

    def fail(self, error: str) -> None:
        """Mark deployment as failed."""
        self.current_phase = DeploymentPhase.FAILED
        self.last_error = error
        self.complete_phase("failed", error=error)

    def complete(self) -> None:
        """Mark deployment as complete."""
        self.current_phase = DeploymentPhase.COMPLETE
        self.completed_at = datetime.now()

    @property
    def is_complete(self) -> bool:
        """Check if deployment is complete."""
        return self.current_phase == DeploymentPhase.COMPLETE

    @property
    def is_failed(self) -> bool:
        """Check if deployment failed."""
        return self.current_phase == DeploymentPhase.FAILED

    @property
    def completed_phases(self) -> list[DeploymentPhase]:
        """Get list of completed phases."""
        return [p.phase for p in self.phases if p.status == "success"]

    def can_resume_from(self, phase: DeploymentPhase) -> bool:
        """Check if we can resume from a specific phase."""
        # Can resume from any phase after preflight
        phase_order = [
            DeploymentPhase.PREFLIGHT,
            DeploymentPhase.ANALYSIS,
            DeploymentPhase.PLANNING,
            DeploymentPhase.COST_PREVIEW,
            DeploymentPhase.APPLY,
            DeploymentPhase.VERIFICATION,
        ]

        if phase not in phase_order:
            return False

        # Check if previous phases completed successfully
        target_idx = phase_order.index(phase)
        for p in phase_order[:target_idx]:
            if p not in self.completed_phases:
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project_name": self.project_name,
            "provider": self.provider,
            "current_phase": self.current_phase.value,
            "phases": [
                {
                    "phase": p.phase.value,
                    "status": p.status,
                    "message": p.message,
                    "started_at": p.started_at.isoformat(),
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "error": p.error,
                }
                for p in self.phases
            ],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_error": self.last_error,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeploymentState":
        """Create from dictionary."""
        state = cls(
            project_name=data["project_name"],
            provider=data["provider"],
            current_phase=DeploymentPhase(data["current_phase"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            last_error=data.get("last_error"),
            retry_count=data.get("retry_count", 0),
        )

        for p in data.get("phases", []):
            result = PhaseResult(
                phase=DeploymentPhase(p["phase"]),
                status=p["status"],
                message=p.get("message", ""),
                started_at=datetime.fromisoformat(p["started_at"]),
                completed_at=datetime.fromisoformat(p["completed_at"]) if p.get("completed_at") else None,
                error=p.get("error"),
            )
            state.phases.append(result)

        return state


class DeploymentStateManager:
    """Manages deployment state persistence."""

    STATE_FILE = "deploy.state"

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.infera_dir = project_root / ".infera"
        self.state_file = self.infera_dir / self.STATE_FILE

    def save(self, state: DeploymentState) -> None:
        """Save deployment state."""
        self.infera_dir.mkdir(exist_ok=True)
        with open(self.state_file, "w") as f:
            yaml.dump(state.to_dict(), f, default_flow_style=False)

    def load(self) -> DeploymentState | None:
        """Load deployment state if exists."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file) as f:
                data = yaml.safe_load(f)
            return DeploymentState.from_dict(data)
        except Exception:
            return None

    def clear(self) -> None:
        """Clear deployment state."""
        if self.state_file.exists():
            self.state_file.unlink()

    def has_state(self) -> bool:
        """Check if state file exists."""
        return self.state_file.exists()


# Recovery strategies for common errors
RECOVERY_STRATEGIES: dict[str, list[str]] = {
    "gcloud not authenticated": [
        "Run: gcloud auth login",
        "Then: gcloud config set project YOUR_PROJECT_ID",
    ],
    "gcloud not found": [
        "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
        "After install, run: gcloud init",
    ],
    "billing not enabled": [
        "Visit: https://console.cloud.google.com/billing",
        "Link a billing account to your project",
    ],
    "terraform init failed": [
        "Check your internet connection",
        "Verify provider credentials",
        "Run: terraform init -reconfigure",
    ],
    "terraform plan failed": [
        "Review the error message above",
        "Check resource quotas in your cloud account",
        "Verify IAM permissions",
    ],
    "terraform apply failed": [
        "Check the specific resource error above",
        "Some resources may have been created - check your cloud console",
        "Run: infera apply --resume to retry",
    ],
    "docker not running": [
        "Start Docker Desktop or the docker daemon",
        "Verify with: docker ps",
    ],
    "permission denied": [
        "Check IAM permissions for your service account",
        "For GCP: ensure roles/editor or specific resource roles",
        "For AWS: check IAM policies attached to your user/role",
    ],
    "quota exceeded": [
        "Request quota increase in cloud console",
        "Or reduce resource requests in configuration",
    ],
    "wrangler not authenticated": [
        "Run: npx wrangler login",
        "Or set CLOUDFLARE_API_TOKEN environment variable",
    ],
}


def get_recovery_suggestions(error_message: str) -> list[str]:
    """Get recovery suggestions for an error message."""
    error_lower = error_message.lower()

    for pattern, suggestions in RECOVERY_STRATEGIES.items():
        if pattern.lower() in error_lower:
            return suggestions

    # Generic suggestions
    return [
        "Review the error message above",
        "Check your cloud provider console for more details",
        "Run: infera deploy --resume to retry from the failed phase",
    ]
