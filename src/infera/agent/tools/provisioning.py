"""Minimal tools for the agent.

The agent handles most tasks using built-in tools (Bash, Read, Write, etc.).
This module provides only a simple auth verification tool.
"""

import asyncio
import json
from typing import Any

from claude_agent_sdk import tool


@tool(
    "verify_auth",
    "Verify authentication with a cloud provider (gcp, aws, azure)",
    {"provider": str},
)
async def verify_auth(args: dict[str, Any]) -> dict[str, Any]:
    """Verify authentication with a cloud provider."""
    provider = args.get("provider", "gcp")

    if provider == "gcp":
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud",
                "auth",
                "list",
                "--format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "gcloud CLI not found or not authenticated",
                        }
                    ],
                    "is_error": True,
                }

            accounts = json.loads(stdout.decode())
            active = [a for a in accounts if a.get("status") == "ACTIVE"]

            if not active:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "No active gcloud account. Run 'gcloud auth login'",
                        }
                    ],
                    "is_error": True,
                }

            # Get project
            proc2 = await asyncio.create_subprocess_exec(
                "gcloud",
                "config",
                "get-value",
                "project",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await proc2.communicate()
            project = stdout2.decode().strip()

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Authenticated with GCP. Account: {active[0].get('account')}. Project: {project or 'not set'}",
                    }
                ]
            }
        except FileNotFoundError:
            return {
                "content": [{"type": "text", "text": "gcloud CLI not installed"}],
                "is_error": True,
            }

    elif provider == "aws":
        try:
            proc = await asyncio.create_subprocess_exec(
                "aws",
                "sts",
                "get-caller-identity",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "AWS CLI not authenticated. Run 'aws configure'",
                        }
                    ],
                    "is_error": True,
                }

            identity = json.loads(stdout.decode())
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Authenticated with AWS. Account: {identity.get('Account')}",
                    }
                ]
            }
        except FileNotFoundError:
            return {
                "content": [{"type": "text", "text": "AWS CLI not installed"}],
                "is_error": True,
            }

    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Provider '{provider}' not supported. Use: gcp, aws",
                }
            ],
            "is_error": True,
        }
