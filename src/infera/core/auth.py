"""API key management for Infera.

Handles storing and retrieving the Anthropic API key from:
1. Environment variable (ANTHROPIC_API_KEY)
2. Credentials file (~/.infera/credentials)
"""

import os
from pathlib import Path

# Credentials file location
INFERA_DIR = Path.home() / ".infera"
CREDENTIALS_FILE = INFERA_DIR / "credentials"


def get_api_key() -> str | None:
    """Get the Anthropic API key from environment or credentials file.

    Returns:
        API key string if found, None otherwise.
    """
    # First check environment variable
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # Then check credentials file
    if CREDENTIALS_FILE.exists():
        try:
            content = CREDENTIALS_FILE.read_text().strip()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    if key.startswith('"') and key.endswith('"'):
                        key = key[1:-1]
                    elif key.startswith("'") and key.endswith("'"):
                        key = key[1:-1]
                    if key:
                        # Set in environment for the current process
                        os.environ["ANTHROPIC_API_KEY"] = key
                        return key
        except Exception:
            pass

    return None


def save_api_key(key: str) -> None:
    """Save the API key to the credentials file.

    Args:
        key: The Anthropic API key to save.
    """
    # Create directory if it doesn't exist
    INFERA_DIR.mkdir(parents=True, exist_ok=True)

    # Write credentials file
    CREDENTIALS_FILE.write_text(f'ANTHROPIC_API_KEY="{key}"\n')

    # Set restrictive permissions (owner read/write only)
    CREDENTIALS_FILE.chmod(0o600)

    # Also set in environment for current process
    os.environ["ANTHROPIC_API_KEY"] = key


def is_valid_api_key(key: str) -> bool:
    """Basic validation of API key format.

    Args:
        key: The API key to validate.

    Returns:
        True if the key looks valid, False otherwise.
    """
    # Anthropic API keys start with "sk-ant-"
    if not key:
        return False
    if not key.startswith("sk-ant-"):
        return False
    if len(key) < 20:
        return False
    return True


def ensure_api_key() -> bool:
    """Ensure an API key is available, prompting if necessary.

    This function should be called at CLI startup. It:
    1. Checks for existing key (env var or credentials file)
    2. If not found, prompts the user to enter one
    3. Saves the key for future use

    Returns:
        True if a valid API key is available, False otherwise.
    """
    from infera.cli import output

    # Check if key already exists
    key = get_api_key()
    if key:
        return True

    # Prompt user for API key
    output.console.print()
    output.console.print("[bold cyan]Welcome to Infera![/bold cyan]")
    output.console.print()
    output.console.print("To use Infera, you need an Anthropic API key.")
    output.console.print(
        "Get one at: [link=https://console.anthropic.com/settings/keys]https://console.anthropic.com/settings/keys[/link]"
    )
    output.console.print()

    # Get key from user
    key = output.console.input("[bold]Enter your Anthropic API key:[/bold] ").strip()

    if not key:
        output.error("No API key provided.")
        return False

    if not is_valid_api_key(key):
        output.warn(
            "This doesn't look like a valid Anthropic API key (should start with 'sk-ant-')."
        )
        if not output.confirm("Save anyway?", default=False):
            return False

    # Save the key
    save_api_key(key)
    output.step_done(f"API key saved to {CREDENTIALS_FILE}")
    output.console.print()

    return True
