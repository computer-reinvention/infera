# Infera

Agentic infrastructure provisioning from code analysis. Infera analyzes your codebase, infers the optimal cloud architecture, and provisions resources automatically.

## Features

- **Intelligent Analysis**: Detects frameworks (React, Vue, FastAPI, Django, etc.) and dependencies
- **Best Practice Templates**: Uses proven architecture patterns for different project types
- **Cost Estimation**: Shows per-resource and total monthly cost estimates
- **Hybrid Execution**: Uses cloud SDKs for simple resources, Terraform for complex setups
- **Rollback on Failure**: Atomic provisioning with automatic cleanup

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/infera.git
cd infera

# Install with uv
uv sync

# Or install globally
uv tool install .
```

## Quick Start

```bash
# Navigate to your project
cd /path/to/your/project

# Initialize - analyzes codebase and creates configuration
uv run infera init

# Review the plan and cost estimate
uv run infera plan

# Provision the infrastructure
uv run infera apply
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- [Google Cloud SDK](https://cloud.google.com/sdk) (for GCP provider)
- `ANTHROPIC_API_KEY` environment variable

## CLI Commands

| Command | Description |
|---------|-------------|
| `infera init` | Analyze codebase and create configuration |
| `infera plan` | Generate execution plan with cost estimate |
| `infera apply` | Provision infrastructure |
| `infera destroy` | Tear down all resources |
| `infera status` | Show current infrastructure state |

## Supported Architectures

- **Static Site**: React, Vue, Angular → Cloud Storage + CDN
- **API Service**: FastAPI, Flask, Express → Cloud Run
- **Full Stack**: Next.js, Django → Cloud Run + Cloud SQL
- **Containerized**: Dockerfile → Cloud Run from container

## Configuration

After `infera init`, configuration is stored in `.infera/config.yaml`:

```yaml
version: "1.0"
project_name: my-app
provider: gcp
region: us-central1

resources:
  - id: app
    type: cloud_run
    name: my-app
    config:
      image: gcr.io/my-project/my-app:latest
      memory: 512Mi
      min_instances: 0
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Type checking
uv run pyright

# Format code
uv run ruff format .
```

## License

MIT
