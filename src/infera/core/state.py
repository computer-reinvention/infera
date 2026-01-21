"""State management for Infera projects."""

from pathlib import Path

import yaml

from infera.core.config import InferaConfig
from infera.core.exceptions import ConfigurationError


INFERA_DIR = ".infera"
CONFIG_FILE = "config.yaml"
TERRAFORM_DIR = "terraform"


class StateManager:
    """Manages .infera/ directory."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.infera_dir = project_root / INFERA_DIR
        self.terraform_dir = self.infera_dir / TERRAFORM_DIR

    def ensure_initialized(self) -> None:
        """Ensure .infera/ directory exists."""
        self.infera_dir.mkdir(exist_ok=True)
        self.terraform_dir.mkdir(exist_ok=True)

        gitignore_path = self.infera_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(
                "# Terraform state (contains sensitive data)\n"
                "terraform/terraform.tfstate\n"
                "terraform/terraform.tfstate.backup\n"
                "terraform/.terraform/\n"
                "terraform/tfplan\n"
            )

    def is_initialized(self) -> bool:
        """Check if project is initialized."""
        return (self.infera_dir / CONFIG_FILE).exists()

    def load_config(self) -> InferaConfig | None:
        """Load project configuration."""
        config_path = self.infera_dir / CONFIG_FILE
        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return InferaConfig.model_validate(data)
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}") from e

    def save_config(self, config: InferaConfig) -> None:
        """Save project configuration."""
        self.ensure_initialized()
        config_path = self.infera_dir / CONFIG_FILE

        config.updated_at = __import__("datetime").datetime.now()

        with open(config_path, "w") as f:
            yaml.dump(
                config.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self.infera_dir / CONFIG_FILE
