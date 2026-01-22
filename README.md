# Infera

Agentic infrastructure provisioning from code analysis. Infera analyzes your codebase, infers the optimal cloud architecture, and provisions resources automatically.

## Features

- **Intelligent Analysis**: Detects frameworks (React, Vue, FastAPI, Django, etc.) and dependencies
- **Best Practice Templates**: Uses proven architecture patterns for different project types
- **Cost Estimation**: Shows per-resource and total monthly cost estimates
- **Hybrid Execution**: Uses cloud SDKs for simple resources, Terraform for complex setups
- **Rollback on Failure**: Atomic provisioning with automatic cleanup

## See It In Action

```bash
$ cd my-fastapi-project
$ infera init

🔍 Analyzing codebase...
   ├── Detected: Python 3.11 (pyproject.toml)
   ├── Detected: FastAPI framework (confidence: 94%)
   ├── Detected: PostgreSQL database (asyncpg in dependencies)
   ├── Detected: Dockerfile present
   └── Detected: Redis for caching (redis-py)

📋 Selected template: gcp/cloud_run_fullstack.md
   Based on: API framework + database + containerized

📦 Proposed Infrastructure:
   ┌─────────────────────────────────────────────────────────┐
   │  Cloud Run Service     my-fastapi-app      us-central1 │
   │  Artifact Registry     my-fastapi-repo     us-central1 │
   │  Cloud SQL (Postgres)  my-fastapi-db       us-central1 │
   │  Redis (Memorystore)   my-fastapi-cache    us-central1 │
   │  Secret Manager        DATABASE_URL, REDIS_URL         │
   └─────────────────────────────────────────────────────────┘

💰 Estimated Monthly Cost: $45-85
   ├── Cloud Run:      $5-20  (scales to zero)
   ├── Cloud SQL:      $25-40 (db-f1-micro)
   ├── Memorystore:    $15-25 (basic tier)
   └── Networking:     ~$1

✅ Configuration saved to .infera/config.yaml

$ infera apply

🚀 Provisioning infrastructure...
   ✓ Enabled Cloud Run API
   ✓ Enabled Artifact Registry API
   ✓ Created Artifact Registry: my-fastapi-repo
   ✓ Built and pushed container image
   ✓ Created Cloud SQL instance: my-fastapi-db
   ✓ Created Memorystore instance: my-fastapi-cache
   ✓ Stored secrets in Secret Manager
   ✓ Deployed Cloud Run service: my-fastapi-app

🎉 Deployment complete!

   Service URL: https://my-fastapi-app-abc123-uc.a.run.app

   Next steps:
   • Set up custom domain: infera domain add api.myapp.com
   • View logs: gcloud run logs read my-fastapi-app
   • Monitor costs: infera status --costs
```

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

## Template-Driven Intelligence

Infera's core strength lies in its **library of 83 battle-tested deployment templates** that encode years of production infrastructure knowledge. Instead of generating configurations from scratch, our AI agent references these templates to deliver consistent, proven infrastructure patterns.

### What Are Templates?

Templates are comprehensive markdown documents that define everything needed to deploy a specific architecture pattern:

- **Architecture diagrams** showing how components connect
- **Resource definitions** with Terraform configurations ready to use
- **Best practices** distilled from production deployments
- **Cost breakdowns** with real pricing data at different traffic levels
- **Common mistakes** to avoid and their solutions
- **Detection signals** that help match your codebase to the right pattern

### Template Categories

| Category | Templates | Examples |
|----------|-----------|----------|
| **GCP Deployments** | 15 | Cloud Run, GKE, Cloud Functions, App Engine |
| **AWS Deployments** | 15 | Lambda, ECS Fargate, EKS, Elastic Beanstalk |
| **Cloudflare Edge** | 10 | Workers, Pages, D1, R2, Durable Objects |
| **Framework-Specific** | 15 | Next.js, FastAPI, Django, Rails, Go, Rust |
| **Database Patterns** | 8 | PostgreSQL, MySQL, MongoDB, Redis, DynamoDB |
| **Specialized Architectures** | 10 | WebSocket, GraphQL, ML Inference, Multi-tenant |
| **Cost Optimization** | 5 | Free tier strategies, Spot instances, Serverless vs Containers |
| **DevOps & CI/CD** | 5 | GitHub Actions, GitLab CI, Docker best practices |

### How Templates Work

1. **Codebase Analysis**: Infera scans your project for framework signatures, dependencies, and patterns
2. **Template Matching**: The AI agent uses detection signals to select the most appropriate template
3. **Configuration Generation**: Resources are configured following template best practices
4. **Cost Estimation**: Pricing data from templates provides accurate monthly estimates

### Why Templates Matter

**Consistency**: Every FastAPI service you deploy follows the same proven Cloud Run configuration. No more reinventing the wheel.

**Best Practices Built-In**: Templates encode lessons learned from production incidents—proper health checks, security configurations, scaling limits, and resource sizing.

**Cost Awareness**: Each template includes detailed cost breakdowns. Know exactly what you'll pay before provisioning a single resource.

**Multi-Cloud Ready**: The same application type maps to equivalent services across providers. Deploy a Next.js app to GCP Cloud Run, AWS ECS, or Cloudflare Pages with templates optimized for each.

### Example: What a Template Provides

For a simple API deployment, the `gcp/cloud_run_api.md` template includes:

```
✓ Architecture diagram with Cloud Run, Artifact Registry, and optional databases
✓ Complete Terraform configuration with variables and outputs
✓ Scaling recommendations (min/max instances, concurrency)
✓ Security setup (IAM, Secret Manager, VPC connectors)
✓ Cost table: 10k requests/day = $0-5, 1M requests/day = $100-300
✓ Common mistakes: cold starts, missing health checks, hardcoded secrets
```

All of this knowledge flows into your `infera plan` output automatically.

## Roadmap

We're actively developing Infera to become the most intelligent infrastructure provisioning tool available. Here's what's coming:

### Infrastructure Discovery & Alignment

**Discover existing resources**: Infera will scan your cloud accounts to identify already-provisioned infrastructure—databases, load balancers, VPCs, and more.

**Align with existing patterns**: Instead of proposing a new Cloud SQL instance, Infera will recognize you already have an RDS cluster and suggest connecting to it. Your new services will follow the naming conventions, tagging strategies, and network topology already established in your environment.

**Drift detection**: Compare your codebase requirements against what's actually deployed. Get alerts when your infrastructure diverges from what your application expects.

### Deeper Provider Integrations

**One-click authentication**: Native OAuth flows for GCP, AWS, and Cloudflare. No more copying service account keys or configuring credentials manually.

**Real-time provisioning feedback**: Stream deployment logs directly into your terminal. Watch resources come online with live status updates.

**Automatic IAM configuration**: Infera will create least-privilege service accounts and roles automatically, eliminating one of the most error-prone parts of cloud setup.

**Cost optimization recommendations**: Analyze your running infrastructure and suggest reserved instances, committed use discounts, or architecture changes that could reduce your bill.

### Expanded Provider Support

- **Azure**: App Service, Azure Functions, AKS, Cosmos DB
- **Vercel/Netlify**: Native support for frontend-focused deployments
- **DigitalOcean**: App Platform, Managed Databases, Kubernetes
- **Fly.io**: Edge deployments with automatic region selection

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

[MIT](LICENSE)
