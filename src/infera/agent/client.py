"""Infera Agent - Claude SDK integration.

The agent uses:
- Built-in tools (Read, Write, Glob, Grep) for codebase analysis
- Terraform MCP server for live provider documentation (optional)
- Markdown instruction files for guidance on tasks
- Minimal custom tools (only verify_auth for authentication checks)
"""

import os
import shutil
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    HookMatcher,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

from infera.core.config import InferaConfig
from infera.agent.hooks import security_hook, logging_hook, verbose_pre_tool_hook
from infera.agent.tools import verify_auth
from infera.cli import output as cli_output


def _verbose_log_message(message: AssistantMessage) -> None:
    """Log assistant message content in verbose mode."""
    if not cli_output.is_verbose():
        return

    for block in message.content:
        if isinstance(block, TextBlock):
            # Truncate long text for readability
            text = block.text.strip()
            if text:
                # Show first 200 chars of agent thinking
                if len(text) > 200:
                    text = text[:197] + "..."
                cli_output.agent_thinking(text)


def _get_terraform_mcp_config() -> dict | None:
    """Get Terraform MCP server configuration.

    Tries in order:
    1. Local Go binary (terraform-mcp-server)
    2. Docker (hashicorp/terraform-mcp-server)
    3. None (agent works without it using instruction files)
    """
    # Check for local binary first
    terraform_mcp_binary = shutil.which("terraform-mcp-server")
    if terraform_mcp_binary:
        return {
            "command": terraform_mcp_binary,
            "args": [],
        }

    # Check if Docker is available
    docker_path = shutil.which("docker")
    if docker_path:
        # Check if Docker daemon is running (quick check)
        docker_sock = Path(os.environ.get("DOCKER_HOST", "").replace("unix://", ""))
        if not docker_sock.exists():
            docker_sock = Path("/var/run/docker.sock")
        if not docker_sock.exists():
            docker_sock = Path.home() / ".docker/run/docker.sock"

        if docker_sock.exists():
            return {
                "command": "docker",
                "args": ["run", "-i", "--rm", "hashicorp/terraform-mcp-server:latest"],
            }

    # Terraform MCP not available - agent will use instruction files only
    return None


def _build_system_prompt(templates_dir: Path, project_root: Path, provider: str) -> str:
    """Build the system prompt with instruction file references."""
    return f"""You are Infera, an infrastructure provisioning agent.

## Your Capabilities

You have access to:
1. **File tools**: Read, Write, Glob, Grep for analyzing codebases and writing files
2. **Terraform MCP**: Query live Terraform Registry documentation for accurate resource schemas
3. **Instruction files**: Detailed guides on how to perform specific tasks
4. **AskUserQuestion**: Clarify ambiguities with the user

## Instruction Files

IMPORTANT: Before performing any task, read the relevant instruction file:

- **Codebase Analysis**: `{templates_dir}/instructions/codebase_analysis.md`
  How to analyze a codebase to detect frameworks, databases, and requirements

- **Terraform Generation**: `{templates_dir}/instructions/terraform_generation.md`
  How to use the Terraform MCP and generate correct Terraform configurations

- **Cost Estimation**: `{templates_dir}/instructions/cost_estimation.md`
  How to estimate monthly costs for infrastructure resources

## Infrastructure Templates

After analyzing the codebase, select the appropriate template:

- **Template Index**: `{templates_dir}/_index.md`
  Decision tree for selecting the right template

- **Static Site**: `{templates_dir}/static_site.md`
- **API Service**: `{templates_dir}/api_service.md`
- **Fullstack App**: `{templates_dir}/fullstack_app.md`
- **Containerized**: `{templates_dir}/containerized.md`

## Terraform MCP Tools

Use these tools to get accurate, up-to-date Terraform documentation:

- `mcp__terraform__search_providers`: Search for providers
- `mcp__terraform__get_provider_details`: Get provider info and resource list
- `mcp__terraform__get_resource_details`: Get full resource schema and examples
- `mcp__terraform__search_modules`: Find reusable modules

ALWAYS query the Terraform MCP for resource schemas before generating Terraform code.
Do NOT rely on memorized configurations - schemas change between provider versions.

## Workflow

### For `infera init`:
1. Read `{templates_dir}/instructions/codebase_analysis.md`
2. Analyze the codebase at `{project_root}` using Glob, Grep, Read
3. Read `{templates_dir}/_index.md` to select the right template
4. Read the selected template for best practices
5. Use AskUserQuestion to clarify any ambiguities
6. Generate the infrastructure configuration as YAML

### For `infera plan`:
1. Read the configuration from `.infera/config.yaml`
2. Read `{templates_dir}/instructions/terraform_generation.md`
3. Query Terraform MCP for each resource's current schema
4. Generate Terraform files in `.infera/terraform/`
5. Read `{templates_dir}/instructions/cost_estimation.md`
6. Calculate and present the cost estimate

### For `infera apply`:
1. Verify authentication using `mcp__infera__verify_auth`
2. Execute Terraform via the Executor (handled by CLI)

## Rules

- ALWAYS read instruction files before performing tasks
- ALWAYS query Terraform MCP for resource schemas
- ASK the user before making non-standard choices
- NEVER prompt for secrets - expect user to configure externally
- PRIORITIZE cost optimization for simple projects
- OUTPUT configurations as YAML code blocks (```yaml)

## Current Context

- Project root: `{project_root}`
- Provider: `{provider}`
- Templates directory: `{templates_dir}`
"""


class InferaAgent:
    """Main agent orchestrator for Infera.

    The agent relies on:
    - Markdown instruction files for task guidance
    - Terraform MCP for live provider documentation
    - Built-in tools for file operations
    - Minimal custom tools (verify_auth only)
    """

    def __init__(self, project_root: Path, provider: str = "gcp"):
        self.project_root = project_root
        self.provider = provider
        self.templates_dir = Path(__file__).parent.parent / "templates"
        self._client: ClaudeSDKClient | None = None

    def _create_options(self) -> ClaudeAgentOptions:
        """Create Claude SDK options with MCP servers."""
        # Minimal custom tools - only verify_auth for authentication checks
        infera_server = create_sdk_mcp_server(
            name="infera",
            version="0.1.0",
            tools=[verify_auth],
        )

        # Configure MCP servers
        mcp_servers: dict = {"infera": infera_server}

        # Try to add Terraform MCP server (optional)
        terraform_mcp = _get_terraform_mcp_config()
        if terraform_mcp:
            mcp_servers["terraform"] = terraform_mcp

        # Configure allowed tools
        allowed_tools = [
            # Built-in file tools for codebase analysis
            "Read",
            "Write",
            "Glob",
            "Grep",
            # Shell for specific commands if needed
            "Bash",
            # User interaction
            "AskUserQuestion",
            # Custom tool for auth verification
            "mcp__infera__verify_auth",
        ]

        # Add Terraform MCP tools if available
        if terraform_mcp:
            allowed_tools.extend([
                "mcp__terraform__search_providers",
                "mcp__terraform__get_provider_details",
                "mcp__terraform__get_resource_details",
                "mcp__terraform__search_modules",
                "mcp__terraform__get_module_details",
            ])

        return ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
            cwd=str(self.project_root),
            hooks={
                "PreToolUse": [HookMatcher(hooks=[verbose_pre_tool_hook, security_hook])],
                "PostToolUse": [HookMatcher(hooks=[logging_hook])],
            },
        )

    async def analyze_and_configure(self, non_interactive: bool = False) -> InferaConfig:
        """Analyze codebase and generate infrastructure configuration."""
        prompt = self._build_analysis_prompt(non_interactive)

        options = self._create_options()
        config_data: dict | None = None

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    _verbose_log_message(message)
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Look for YAML config in response
                            config_data = self._extract_config_from_response(block.text)
                            if config_data:
                                break

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

        if config_data is None:
            raise RuntimeError("Agent did not produce a configuration")

        return InferaConfig.model_validate(config_data)

    async def generate_terraform_and_plan(self) -> None:
        """Generate Terraform files and run terraform plan."""
        tf_dir = self.project_root / ".infera" / "terraform"
        tf_dir.mkdir(parents=True, exist_ok=True)

        prompt = f"""{_build_system_prompt(self.templates_dir, self.project_root, self.provider)}

---

# Task: Generate Terraform and Run Plan

1. Read the config at {self.project_root}/.infera/config.yaml

2. Read the Terraform generation instructions:
   {self.templates_dir}/instructions/terraform_generation.md

3. Generate Terraform files in {tf_dir}/
   - main.tf (provider + resources)
   - variables.tf (variables with defaults)
   - outputs.tf (useful outputs)

4. Run these commands using Bash:
   ```
   cd {tf_dir}
   terraform init
   terraform plan -out=tfplan 2>&1 | tee plan_output.txt
   ```

5. Report what will be created/changed/destroyed

IMPORTANT: Write the actual .tf files using the Write tool, then run terraform commands.
"""

        options = self._create_options()

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    _verbose_log_message(message)

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

    async def apply_terraform(self) -> None:
        """Run terraform apply."""
        tf_dir = self.project_root / ".infera" / "terraform"

        prompt = f"""{_build_system_prompt(self.templates_dir, self.project_root, self.provider)}

---

# Task: Apply Terraform

Run terraform apply in {tf_dir}:

```bash
cd {tf_dir}
terraform apply -auto-approve tfplan 2>&1
terraform output -json > outputs.json
```

If tfplan doesn't exist, run:
```bash
terraform apply -auto-approve
```

Report the outputs when done.
"""

        options = self._create_options()

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    _verbose_log_message(message)

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

    async def destroy_terraform(self) -> None:
        """Run terraform destroy."""
        tf_dir = self.project_root / ".infera" / "terraform"

        prompt = f"""{_build_system_prompt(self.templates_dir, self.project_root, self.provider)}

---

# Task: Destroy Infrastructure

Run terraform destroy in {tf_dir}:

```bash
cd {tf_dir}
terraform destroy -auto-approve 2>&1
```

Confirm when all resources are destroyed.
"""

        options = self._create_options()

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    _verbose_log_message(message)

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        raise RuntimeError(f"Agent error: {message.result}")

    def _build_analysis_prompt(self, non_interactive: bool) -> str:
        """Build the initial analysis prompt with full context."""
        mode = "non-interactive" if non_interactive else "interactive"
        system_context = _build_system_prompt(self.templates_dir, self.project_root, self.provider)

        return f"""{system_context}

---

# Current Task: Analyze Codebase and Configure Infrastructure

Mode: {mode}

Follow the workflow for `infera init`:

1. First, read the codebase analysis instructions at:
   {self.templates_dir}/instructions/codebase_analysis.md

2. Analyze the codebase at {self.project_root} using Glob, Grep, Read tools

3. Read the template index and select the appropriate template:
   {self.templates_dir}/_index.md

4. Read the selected template for best practices

5. {"Use sensible defaults for all decisions - do not ask questions" if non_interactive else "Ask clarifying questions if needed using AskUserQuestion"}

6. Output the final infrastructure configuration as a YAML code block

The YAML should be parseable as an InferaConfig with this structure:
```yaml
version: '1.0'
project_name: <name>
provider: {self.provider}
region: us-central1
project_id: null  # User will set this
detected_frameworks: []
has_dockerfile: false
entry_point: null
architecture_type: <static_site|api_service|fullstack|containerized>
resources:
  - id: <unique_id>
    type: <resource_type>
    name: <resource_name>
    provider: {self.provider}
    config: {{}}
    depends_on: []
domain: null
```
"""

    def _build_terraform_prompt(self) -> str:
        """Build the Terraform generation prompt with full context."""
        system_context = _build_system_prompt(self.templates_dir, self.project_root, self.provider)

        return f"""{system_context}

---

# Current Task: Generate Terraform Configuration

Follow the workflow:

1. Read the current configuration:
   {self.project_root}/.infera/config.yaml

2. Read the Terraform generation instructions:
   {self.templates_dir}/instructions/terraform_generation.md

3. For EACH resource type in the config, query the Terraform MCP:
   - Use mcp__terraform__get_resource_details to get the current schema
   - Do NOT assume argument names - verify them

4. Generate Terraform files and write them to:
   {self.project_root}/.infera/terraform/

   Create these files:
   - main.tf (provider config and all resources)
   - variables.tf (input variables)
   - outputs.tf (output values)

5. Read the cost estimation instructions:
   {self.templates_dir}/instructions/cost_estimation.md

6. Calculate and report the estimated monthly cost
"""

    def _extract_config_from_response(self, text: str) -> dict | None:
        """Extract YAML configuration from agent response."""
        import yaml

        # Look for YAML code block
        if "```yaml" in text:
            start = text.find("```yaml") + 7
            end = text.find("```", start)
            if end > start:
                yaml_text = text[start:end].strip()
                try:
                    return yaml.safe_load(yaml_text)
                except yaml.YAMLError:
                    pass
        return None

    async def stream_execution(
        self, prompt: str
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream agent execution for real-time output.

        Yields (message_type, content) tuples.
        """
        options = self._create_options()

        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)

            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            yield ("text", block.text)

                if isinstance(message, ResultMessage):
                    if message.subtype != "success":
                        yield ("error", message.result or "Unknown error")
                    else:
                        yield ("complete", message.result or "")
                    break
