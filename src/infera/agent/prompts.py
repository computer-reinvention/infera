"""Prompt loading and building utilities.

Prompts are stored as markdown files in the `prompts/` directory with a modular structure:

    prompts/
    ├── _shared/           # Shared components (error handling, etc.)
    │   └── error_loop.md
    ├── system.md          # Main system prompt
    ├── analyze.md         # Codebase analysis (same for all providers)
    ├── plan/
    │   ├── _base.md       # Common plan structure
    │   ├── terraform.md   # GCP/AWS/Azure specifics
    │   └── cloudflare.md  # Cloudflare specifics
    ├── apply/
    │   ├── _base.md
    │   ├── terraform.md
    │   ├── terraform_dry_run.md
    │   └── cloudflare.md
    └── destroy/
        ├── _base.md
        ├── terraform.md
        └── cloudflare.md

To add a new provider, create new files in each command directory (e.g., plan/vercel.md).
"""

from pathlib import Path
from typing import Any
import re

# Directory containing prompt markdown files
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Map providers to their deployment backend
PROVIDER_BACKEND = {
    "gcp": "terraform",
    "aws": "terraform",
    "azure": "terraform",
    "cloudflare": "cloudflare",
    # Add new providers here, e.g.:
    # "vercel": "vercel",
    # "fly": "fly",
}


def _resolve_includes(content: str, base_dir: Path, variables: dict[str, str]) -> str:
    """Resolve {include:path/to/file.md} directives in content."""
    pattern = r"\{include:([^}]+)\}"

    def replace_include(match: re.Match) -> str:
        include_path = match.group(1)
        include_file = base_dir / include_path
        if include_file.exists():
            included = include_file.read_text()
            # Recursively resolve includes and apply variables
            included = _resolve_includes(included, base_dir, variables)
            try:
                return included.format(**variables)
            except KeyError:
                return included
        return f"<!-- Include not found: {include_path} -->"

    return re.sub(pattern, replace_include, content)


def _load_raw(path: Path) -> str:
    """Load a file without variable substitution."""
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text()


def load(name: str, **kwargs: Any) -> str:
    """Load a prompt template and substitute variables.

    Args:
        name: Prompt file name (without .md extension) or path (e.g., "plan/terraform")
        **kwargs: Variables to substitute (e.g., tf_dir, project_root)

    Returns:
        Formatted prompt string
    """
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")

    template = prompt_file.read_text()
    str_kwargs = {k: str(v) for k, v in kwargs.items()}

    # Resolve includes first
    template = _resolve_includes(template, PROMPTS_DIR, str_kwargs)

    # Then apply variable substitution
    return template.format(**str_kwargs)


def load_composite(
    command: str,
    provider: str,
    variant: str | None = None,
    **kwargs: Any,
) -> str:
    """Load and compose a command prompt from base + provider-specific templates.

    Args:
        command: Command name (plan, apply, destroy)
        provider: Cloud provider (gcp, aws, azure, cloudflare)
        variant: Optional variant (e.g., "dry_run" for apply/terraform_dry_run.md)
        **kwargs: Variables to substitute

    Returns:
        Composed prompt string
    """
    # Include provider in kwargs for template substitution
    str_kwargs = {k: str(v) for k, v in kwargs.items()}
    str_kwargs["provider"] = provider

    # Determine the backend for this provider
    backend = PROVIDER_BACKEND.get(provider, "terraform")

    # Add variant suffix if provided (e.g., terraform_dry_run)
    if variant:
        backend = f"{backend}_{variant}"

    # Load base template if it exists
    base_path = PROMPTS_DIR / command / "_base.md"
    provider_path = PROMPTS_DIR / command / f"{backend}.md"

    parts = []

    # Load base template
    if base_path.exists():
        base_content = _load_raw(base_path)
        base_content = _resolve_includes(base_content, PROMPTS_DIR, str_kwargs)
        parts.append(base_content)

    # Load provider-specific template
    if provider_path.exists():
        provider_content = _load_raw(provider_path)
        provider_content = _resolve_includes(provider_content, PROMPTS_DIR, str_kwargs)
        parts.append(provider_content)
    elif not base_path.exists():
        raise FileNotFoundError(f"No prompt found for {command}/{backend}")

    # Combine and format
    combined = "\n\n---\n\n".join(parts)
    try:
        return combined.format(**str_kwargs)
    except KeyError:
        # Return unformatted if some variables are missing (they might be placeholders)
        return combined


def build_full_prompt(
    task_name: str,
    templates_dir: Path,
    project_root: Path,
    provider: str,
    variant: str | None = None,
    **task_kwargs: Any,
) -> str:
    """Build a complete prompt with system context + task instructions.

    Args:
        task_name: Name of the task prompt (e.g., "plan", "apply", "destroy")
        templates_dir: Path to templates directory
        project_root: Path to project being analyzed
        provider: Cloud provider (gcp, aws, azure, cloudflare)
        variant: Optional variant (e.g., "dry_run" for apply with --dry-run)
        **task_kwargs: Additional variables for the task prompt

    Returns:
        Combined system + task prompt
    """
    # Common variables available to all prompts
    common_vars = {
        "templates_dir": templates_dir,
        "project_root": project_root,
        "provider": provider,
    }
    all_vars = {**common_vars, **task_kwargs}

    # Load system prompt
    system_prompt = load("system", **common_vars)

    # Check if task is a composite command (has subdirectory)
    command_dir = PROMPTS_DIR / task_name
    if command_dir.is_dir():
        # Use composite loading for modular prompts
        # Pass all_vars for template substitution, but provider is also used for backend selection
        composite_vars = {**all_vars}
        composite_vars.pop("provider", None)  # Remove to avoid duplicate argument
        task_prompt = load_composite(
            command=task_name,
            provider=provider,
            variant=variant,
            **composite_vars,
        )
    else:
        # Fall back to flat file for simple prompts (analyze.md, etc.)
        task_prompt = load(task_name, **all_vars)

    return f"{system_prompt}\n\n---\n\n{task_prompt}"


def get_backend_for_provider(provider: str) -> str:
    """Get the deployment backend for a provider."""
    return PROVIDER_BACKEND.get(provider, "terraform")


def list_prompts() -> list[str]:
    """List all available prompt names."""
    prompts = []
    for item in PROMPTS_DIR.iterdir():
        if item.is_file() and item.suffix == ".md":
            prompts.append(item.stem)
        elif item.is_dir() and not item.name.startswith("_"):
            prompts.append(item.name)
    return prompts
