# CLAUDE.md - Infera Project Guide

## Project Overview

Infera is an agentic infrastructure provisioning tool that analyzes codebases, infers infrastructure requirements, and provisions cloud resources. It uses Claude Agent SDK to orchestrate the analysis and provisioning workflow.

## Tech Stack

- **Python**: 3.11+
- **Package Manager**: `uv` (not pip)
- **CLI Framework**: Typer + Rich
- **Agent**: Claude Agent SDK (`claude-agent-sdk`)
- **Cloud Provider**: GCP (primary), with AWS/Azure planned
- **IaC**: Hybrid approach - GCP SDK for simple resources, Terraform for complex setups
- **Data Models**: Pydantic v2

## Development Commands

```bash
# Install dependencies
uv sync

# Run CLI
uv run infera --help
uv run infera init
uv run infera plan
uv run infera apply

# Run tests
uv run pytest

# Type checking
uv run pyright

# Format code
uv run ruff format .
uv run ruff check --fix .
```

## Project Structure

```
src/infera/
├── cli/                 # CLI commands (Typer)
├── core/                # Config, state, exceptions
├── agent/               # Claude SDK integration
│   └── tools/           # Custom MCP tools
├── analyzers/           # Framework detection
├── architects/          # Architecture design
├── templates/           # Markdown best practice guides (agent reads these)
├── providers/           # Cloud provider implementations
├── execution/           # Plan building and execution
└── costs/               # Cost estimation
```

## Key Architectural Decisions

### Template-Driven Intelligence

The core intelligence comes from **markdown templates** in `src/infera/templates/`. The Claude agent reads these documents to understand best practices for different architecture types:

- `_index.md` - Template selection decision tree
- `static_site.md` - Cloud Storage + CDN
- `api_service.md` - Cloud Run
- `fullstack_app.md` - Cloud Run + Cloud SQL
- `containerized.md` - Docker deployments

When modifying infrastructure logic, update the relevant template markdown first.

### Hybrid Execution

- **SDK execution**: Simple resources (Cloud Run, Storage, Artifact Registry)
- **Terraform execution**: Complex resources (Load Balancers, DNS, VPC, IAM bindings)
- Decision logic in `providers/base.py:should_use_terraform()`

### State Management

State lives in `.infera/` directory:
- `config.yaml` - User-facing configuration
- `state.json` - Provisioned resource state
- `terraform/` - Hidden Terraform files (when used)

### Framework Detection

Detection uses confidence scoring in `analyzers/detector.py`:
- File presence (40% weight)
- Code patterns (40% weight)
- Directory structure indicators (20% weight)

Threshold: 50% confidence to detect a framework.

## CLI Workflow

```
infera init    → Analyze codebase → Suggest architecture → Save config
infera plan    → Generate execution plan → Show costs → Save plan
infera apply   → Confirm → Execute plan → Update state
infera destroy → Preview → Confirm → Teardown resources
infera status  → Show current state
```

## Agent System

The `InferaAgent` class in `agent/client.py` orchestrates workflows using:

1. **Built-in tools**: Read, Glob, Grep (for codebase analysis)
2. **Custom MCP tools**:
   - `analyze_codebase` - Framework detection
   - `suggest_architecture` - Template selection
   - `provision_resource` - Resource creation
   - `estimate_cost` - Cost calculation

System prompt directs agent to:
1. Read `templates/_index.md` first
2. Analyze codebase with file tools
3. Select appropriate template
4. Ask user for clarification via `AskUserQuestion`
5. Generate configuration following template best practices

## GCP Resources Supported

| Resource | Type Key | Implementation |
|----------|----------|----------------|
| Cloud Run | `cloud_run` | SDK |
| Cloud Storage | `cloud_storage` | SDK (gsutil) |
| Cloud SQL | `cloud_sql` | SDK |
| Artifact Registry | `artifact_registry` | SDK |
| VPC Connector | `vpc_connector` | SDK |
| Load Balancer | `load_balancer` | Terraform |
| Cloud DNS | `cloud_dns` | Terraform |

## Adding New Features

### New Resource Type

1. Add to `providers/gcp.py`:
   - `_provision_<resource>()` method
   - `_destroy_<resource>()` method
   - `_exists_<resource>()` method
   - `_tf_<resource>()` for Terraform generation
2. Add pricing data to `costs/pricing.py`
3. Update `get_supported_resources()` list

### New Cloud Provider

1. Create `providers/<provider>.py` implementing `BaseProvider`
2. Add pricing client in `costs/pricing.py`
3. Register in `providers/__init__.py:get_provider()`

### New Architecture Template

1. Create `templates/<name>.md` following existing format
2. Update `templates/_index.md` decision tree
3. Add to `architects/designer.py:_select_template()`

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=infera

# Run specific test file
uv run pytest tests/test_analyzers.py
```

Test fixtures in `tests/fixtures/` contain sample projects for testing detection.

## Environment Variables

- `ANTHROPIC_API_KEY` - Required for Claude Agent SDK
- `GOOGLE_APPLICATION_CREDENTIALS` - Optional, uses gcloud auth by default

## Common Issues

1. **Import errors in IDE**: Run `uv sync` to install dependencies
2. **gcloud not found**: Install Google Cloud SDK and run `gcloud auth login`
3. **Permission denied on GCP**: Ensure correct project is set with `gcloud config set project <id>`
