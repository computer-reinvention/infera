# Infera

Agentic infrastructure provisioning from code analysis. Infera analyzes your codebase, infers the optimal cloud architecture, and provisions resources automatically.

## Features

- **Intelligent Analysis**: Detects frameworks (React, Vue, FastAPI, Django, etc.) and dependencies
- **Best Practice Templates**: Uses proven architecture patterns for different project types
- **Cost Estimation**: Shows per-resource and total monthly cost estimates
- **Hybrid Execution**: Uses cloud SDKs for simple resources, Terraform for complex setups
- **Rollback on Failure**: Atomic provisioning with automatic cleanup

## Quick Setup

### 1. Install via pipx (recommended)

```bash
pipx install infera
```

Or with pip:

```bash
pip install infera
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 3. Configure your cloud provider

```bash
# For GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 4. Run infera

```bash
cd /path/to/your/project
infera init    # Analyze codebase and create config
infera plan    # Preview infrastructure and costs
infera apply   # Provision resources
```

## Installation Options

### pipx (isolated environment)

```bash
pipx install infera
```

### pip (global)

```bash
pip install infera
```

### From source (development)

```bash
git clone https://github.com/computer-reinvention/infera.git
cd infera
uv sync
uv run infera --help
```

## Requirements

- Python 3.11+
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
