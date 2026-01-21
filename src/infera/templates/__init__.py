"""Infrastructure templates for different architecture types."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent

AVAILABLE_TEMPLATES = [
    "static_site",
    "api_service",
    "fullstack_app",
    "containerized",
]


def get_template(name: str) -> str:
    """Get template content by name."""
    template_file = TEMPLATES_DIR / f"{name}.md"
    if template_file.exists():
        return template_file.read_text()
    raise ValueError(f"Unknown template: {name}")


def get_template_index() -> str:
    """Get template selection index."""
    index_file = TEMPLATES_DIR / "_index.md"
    return index_file.read_text()


def list_templates() -> list[str]:
    """List available templates."""
    return AVAILABLE_TEMPLATES.copy()
