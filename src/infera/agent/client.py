"""Infera Agent - Main orchestrator.

This is the main entry point for the Infera agent. It coordinates:
    - Codebase analysis (infera init)
    - Terraform generation (infera plan)
    - Infrastructure deployment (infera apply)
    - Infrastructure teardown (infera destroy)

To modify agent behavior, edit the prompts in `prompts/` directory.
To modify MCP tools, edit `mcp.py`.
"""

from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

from infera.core.config import InferaConfig
from infera.agent.hooks import security_hook, logging_hook, verbose_pre_tool_hook
from infera.agent.interactions import handle_tool_permission, keep_stream_open_hook
from infera.agent import prompts
from infera.agent import mcp
from infera.cli import output as cli_output


class InferaAgent:
    """Main agent for infrastructure provisioning.

    The agent uses Claude to:
        1. Analyze codebases and detect frameworks
        2. Generate Terraform configurations
        3. Execute infrastructure changes

    Behavior is controlled by markdown prompts in `prompts/` directory.
    """

    def __init__(self, project_root: Path, provider: str = "gcp"):
        """Initialize the agent.

        Args:
            project_root: Path to the project to analyze/deploy
            provider: Cloud provider (gcp, aws, azure)
        """
        self.project_root = project_root
        self.provider = provider
        self.templates_dir = Path(__file__).parent.parent / "templates"

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def analyze_and_configure(
        self, non_interactive: bool = False
    ) -> InferaConfig:
        """Analyze codebase and generate infrastructure configuration.

        Prompt: prompts/analyze.md
        """
        prompt = self._build_analyze_prompt(non_interactive)
        config_data = await self._run_agent_extract_yaml(prompt)

        if config_data is None:
            raise RuntimeError("Agent did not produce a configuration")

        return InferaConfig.model_validate(config_data)

    async def generate_terraform_and_plan(self) -> None:
        """Generate infrastructure config and run plan.

        Uses modular prompts: prompts/plan/_base.md + prompts/plan/{backend}.md
        """
        tf_dir = self.project_root / ".infera" / "terraform"
        tf_dir.mkdir(parents=True, exist_ok=True)

        prompt = prompts.build_full_prompt(
            task_name="plan",
            templates_dir=self.templates_dir,
            project_root=self.project_root,
            provider=self.provider,
            tf_dir=tf_dir,
        )
        await self._run_agent(prompt)

    async def apply_terraform(self, dry_run: bool = False) -> None:
        """Run infrastructure deployment.

        Uses modular prompts: prompts/apply/_base.md + prompts/apply/{backend}.md
        For dry_run, uses prompts/apply/{backend}_dry_run.md
        """
        tf_dir = self.project_root / ".infera" / "terraform"

        prompt = prompts.build_full_prompt(
            task_name="apply",
            templates_dir=self.templates_dir,
            project_root=self.project_root,
            provider=self.provider,
            variant="dry_run" if dry_run else None,
            tf_dir=tf_dir,
        )
        await self._run_agent(prompt)

    async def destroy_terraform(self) -> None:
        """Destroy infrastructure.

        Uses modular prompts: prompts/destroy/_base.md + prompts/destroy/{backend}.md
        """
        tf_dir = self.project_root / ".infera" / "terraform"

        prompt = prompts.build_full_prompt(
            task_name="destroy",
            templates_dir=self.templates_dir,
            project_root=self.project_root,
            provider=self.provider,
            tf_dir=tf_dir,
        )
        await self._run_agent(prompt)

    async def deploy_full_workflow(
        self,
        non_interactive: bool = False,
        auto_approve: bool = False,
        skip_preflight: bool = False,
        resume_from: str | None = None,
    ) -> None:
        """Run the full deployment workflow: analyze, plan, and apply.

        Uses prompts/deploy/_base.md for the complete workflow.

        Args:
            non_interactive: Skip user prompts, use defaults
            auto_approve: Skip apply confirmation
            skip_preflight: Skip preflight checks (already done by CLI)
            resume_from: Phase to resume from (if resuming failed deployment)
        """
        tf_dir = self.project_root / ".infera" / "terraform"
        tf_dir.mkdir(parents=True, exist_ok=True)

        mode = "non-interactive" if non_interactive else "interactive"

        prompt = prompts.build_full_prompt(
            task_name="deploy",
            templates_dir=self.templates_dir,
            project_root=self.project_root,
            provider=self.provider,
            tf_dir=tf_dir,
            mode=mode,
            skip_preflight="true" if skip_preflight else "false",
            auto_approve="true" if auto_approve else "false",
            resume_from=resume_from or "none",
        )
        await self._run_agent(prompt)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _run_agent(self, prompt: str) -> None:
        """Run the agent with a prompt and wait for completion."""
        options = self._create_options()

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    self._log_message(message)

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

    async def _run_agent_extract_yaml(self, prompt: str) -> dict | None:
        """Run the agent and extract YAML config from response."""
        options = self._create_options()
        config_data: dict | None = None

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    self._log_message(message)
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            extracted = self._extract_yaml(block.text)
                            if extracted:
                                config_data = extracted

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

        return config_data

    def _create_options(self) -> ClaudeAgentOptions:
        """Create Claude SDK options with MCP servers and tools."""
        mcp_servers: dict = {"infera": mcp.create_infera_mcp_server()}

        # Add Terraform MCP if available
        terraform_config = mcp.get_terraform_mcp_config()
        if terraform_config:
            mcp_servers["terraform"] = terraform_config

        # Collect allowed tools
        allowed_tools = mcp.BUILTIN_TOOLS + mcp.INFERA_TOOLS
        if terraform_config:
            allowed_tools = allowed_tools + mcp.TERRAFORM_TOOLS

        return ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
            cwd=str(self.project_root),
            can_use_tool=handle_tool_permission,
            hooks={
                # keep_stream_open_hook is required for can_use_tool to work
                "PreToolUse": [
                    HookMatcher(
                        hooks=[
                            keep_stream_open_hook,
                            verbose_pre_tool_hook,
                            security_hook,
                        ]
                    )
                ],
                "PostToolUse": [HookMatcher(hooks=[logging_hook])],
            },
        )

    def _build_analyze_prompt(self, non_interactive: bool) -> str:
        """Build the analysis prompt with mode-specific instructions."""
        mode = "non-interactive" if non_interactive else "interactive"
        interaction_instruction = (
            "Use sensible defaults for all decisions - do not ask questions"
            if non_interactive
            else "Ask clarifying questions if needed using AskUserQuestion"
        )

        return prompts.build_full_prompt(
            task_name="analyze",
            templates_dir=self.templates_dir,
            project_root=self.project_root,
            provider=self.provider,
            mode=mode,
            interaction_instruction=interaction_instruction,
        )

    @staticmethod
    def _extract_yaml(text: str) -> dict | None:
        """Extract YAML configuration from text."""
        import yaml

        if "```yaml" not in text:
            return None

        start = text.find("```yaml") + 7
        end = text.find("```", start)
        if end <= start:
            return None

        try:
            return yaml.safe_load(text[start:end].strip())
        except yaml.YAMLError:
            return None

    @staticmethod
    def _log_message(message: AssistantMessage) -> None:
        """Log assistant message to the user."""
        for block in message.content:
            if isinstance(block, TextBlock) and block.text.strip():
                text = block.text.strip()
                # Always show full agent messages - they contain important info like error fixes
                cli_output.console.print(f"\n{text}")
