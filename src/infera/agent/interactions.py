"""User interaction handlers for the agent.

Handles AskUserQuestion tool calls and other user interactions.
"""

from typing import Any

from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from infera.cli import output


async def handle_tool_permission(
    tool_name: str,
    input_data: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """Handle tool permission requests including AskUserQuestion.

    This callback is invoked when Claude needs user input:
    - For AskUserQuestion: displays questions and collects answers
    - For other tools: auto-approves (permission_mode handles restrictions)
    """
    if tool_name == "AskUserQuestion":
        return await _handle_ask_user_question(input_data)

    # Auto-approve other tools (permission_mode handles restrictions)
    return PermissionResultAllow(updated_input=input_data)


async def _handle_ask_user_question(
    input_data: dict[str, Any],
) -> PermissionResultAllow:
    """Display Claude's questions and collect user answers."""
    questions = input_data.get("questions", [])
    answers: dict[str, str] = {}

    # Pause the spinner to allow user input
    output.pause_spinner()

    try:
        for q in questions:
            header = q.get("header", "Question")
            question_text = q.get("question", "")
            options = q.get("options", [])
            multi_select = q.get("multiSelect", False)

            # Display the question
            output.console.print(f"\n[bold cyan]{header}:[/bold cyan] {question_text}")

            # Display options
            for i, opt in enumerate(options):
                label = opt.get("label", f"Option {i+1}")
                description = opt.get("description", "")
                output.console.print(f"  [dim]{i + 1}.[/dim] {label} - {description}")

            # Show input hint
            if multi_select:
                output.console.print("  [dim](Enter numbers separated by commas, or type your own answer)[/dim]")
            else:
                output.console.print("  [dim](Enter a number, or type your own answer)[/dim]")

            # Collect response
            response = output.console.input("[bold]Your choice:[/bold] ").strip()
            answers[question_text] = _parse_response(response, options)
    finally:
        # Resume the spinner after input is collected
        output.resume_spinner()

    return PermissionResultAllow(
        updated_input={
            "questions": questions,
            "answers": answers,
        }
    )


def _parse_response(response: str, options: list[dict[str, Any]]) -> str:
    """Parse user input as option number(s) or free text."""
    try:
        # Try to parse as comma-separated numbers
        indices = [int(s.strip()) - 1 for s in response.split(",")]
        labels = [
            options[i].get("label", "")
            for i in indices
            if 0 <= i < len(options)
        ]
        if labels:
            return ", ".join(labels)
    except ValueError:
        pass

    # Return as free text
    return response


async def keep_stream_open_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """Dummy hook that keeps the stream open for can_use_tool.

    Required workaround: In Python, can_use_tool requires streaming mode
    and a PreToolUse hook that returns {"continue_": True} to keep the
    stream open. Without this hook, the stream closes before the permission
    callback can be invoked.
    """
    return {"continue_": True}
