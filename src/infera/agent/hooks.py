"""Agent hooks for security and logging."""

from typing import Any

from claude_agent_sdk import HookContext

from infera.cli import output


async def verbose_pre_tool_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Log tool invocations in verbose mode."""
    if not output.is_verbose():
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Format the tool call for display
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Truncate long commands
        if len(cmd) > 80:
            cmd = cmd[:77] + "..."
        output.agent_action("Bash", cmd)
    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        output.agent_action("Read", file_path)
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        output.agent_action("Write", file_path)
    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        output.agent_action("Glob", pattern)
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        output.agent_action("Grep", pattern)
    elif tool_name == "AskUserQuestion":
        output.agent_action("AskUserQuestion")
    elif tool_name.startswith("mcp__terraform__"):
        # Terraform MCP tools
        action = tool_name.replace("mcp__terraform__", "")
        detail = tool_input.get("provider", "") or tool_input.get("resource", "") or ""
        output.agent_action(f"terraform:{action}", detail)
    elif tool_name.startswith("mcp__infera__"):
        # Infera MCP tools
        action = tool_name.replace("mcp__infera__", "")
        output.agent_action(f"infera:{action}")
    else:
        output.agent_action(tool_name)

    return {}


async def security_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Block dangerous operations."""
    tool_name = input_data.get("tool_name", "")

    # Block destructive Terraform commands without confirmation
    if tool_name == "Bash":
        command = input_data.get("tool_input", {}).get("command", "")

        # Block terraform destroy with auto-approve
        if "terraform destroy" in command and "--auto-approve" in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Destructive operations require explicit confirmation"
                    ),
                }
            }

        # Block rm -rf on important directories
        dangerous_patterns = ["rm -rf /", "rm -rf ~", "rm -rf $HOME"]
        for pattern in dangerous_patterns:
            if pattern in command:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Blocked dangerous command: {pattern}",
                    }
                }

    return {}


async def logging_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Log all tool usage for audit trail."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # In a real implementation, this would write to .infera/audit.log
    # For now, we just return empty dict (no-op)

    # Example of what we'd log:
    # - Tool name
    # - Key parameters (redacting sensitive data)
    # - Timestamp
    # - Result status (in PostToolUse)

    return {}
