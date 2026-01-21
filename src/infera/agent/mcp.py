"""MCP (Model Context Protocol) server configuration.

This module configures the MCP servers available to the agent:
    - infera: Custom tools (verify_auth)
    - terraform: HashiCorp Terraform Registry documentation (optional)

The Terraform MCP provides live documentation for resource schemas,
ensuring generated Terraform code uses correct argument names.
"""

import os
import shutil
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server

from infera.agent.tools import verify_auth


def get_terraform_mcp_config() -> dict | None:
    """Get Terraform MCP server configuration.

    Tries in order:
        1. Local binary: terraform-mcp-server
        2. Docker: hashicorp/terraform-mcp-server
        3. None (agent uses instruction files only)

    Returns:
        MCP server config dict, or None if unavailable
    """
    # Option 1: Local Go binary
    binary = shutil.which("terraform-mcp-server")
    if binary:
        return {"command": binary, "args": []}

    # Option 2: Docker
    if shutil.which("docker") and _docker_available():
        return {
            "command": "docker",
            "args": ["run", "-i", "--rm", "hashicorp/terraform-mcp-server:latest"],
        }

    return None


def _docker_available() -> bool:
    """Check if Docker daemon is running."""
    candidates = [
        Path(os.environ.get("DOCKER_HOST", "").replace("unix://", "")),
        Path("/var/run/docker.sock"),
        Path.home() / ".docker/run/docker.sock",
    ]
    return any(sock.exists() for sock in candidates if str(sock))


def create_infera_mcp_server():
    """Create the Infera MCP server with custom tools."""
    return create_sdk_mcp_server(
        name="infera",
        version="0.1.0",
        tools=[verify_auth],
    )


# Tools available from each MCP server
INFERA_TOOLS = [
    "mcp__infera__verify_auth",
]

TERRAFORM_TOOLS = [
    "mcp__terraform__search_providers",
    "mcp__terraform__get_provider_details",
    "mcp__terraform__get_resource_details",
    "mcp__terraform__search_modules",
    "mcp__terraform__get_module_details",
]

# Built-in Claude tools the agent can use
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Glob",
    "Grep",
    "Bash",
    "AskUserQuestion",
]
