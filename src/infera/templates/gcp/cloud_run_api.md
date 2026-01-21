# GCP Cloud Run API

## Overview

Deploy serverless REST/GraphQL APIs on Cloud Run with automatic scaling, managed HTTPS, and pay-per-use pricing. Ideal for stateless API services that need to scale from zero to millions of requests.

## Detection Signals

Use this template when:
- FastAPI, Flask, Express, or similar API framework detected
- `requirements.txt` or `package.json` with web framework
- API route patterns (`/api/`, `routes/`, `routers/`)
- Dockerfile with HTTP port exposed (optional)
- No frontend or separate frontend deployment

## Architecture

```
                    ┌─────────────────┐
                    │  Cloud Run      │
    Internet ──────►│  (Auto-scaling) │──────► Artifact Registry
                    │  min: 0, max: N │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         Cloud SQL     Secret Manager   Cloud Storage
         (optional)    (API keys)       (file uploads)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Run Service | Container hosting | `google_cloud_run_v2_service` |
| Artifact Registry | Docker images | `google_artifact_registry_repository` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud SQL | Database detected | `google_sql_database_instance` |
| Secret Manager | Sensitive config | `google_secret_manager_secret` |
| VPC Connector | Private network | `google_vpc_access_connector` |
| Cloud Armor | DDoS protection | `google_compute_security_policy` |
| Load Balancer | Custom domain | `google_compute_global_address` |

## Configuration

### Terraform Variables
```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
}

variable "min_instances" {
  description = "Minimum instances (0 for scale to zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum instances"
  type        = number
  default     = 10
}

variable "memory" {
  description = "Memory per instance"
  type        = string
  default     = "512Mi"
}

variable "cpu" {
  description = "CPU per instance"
  type        = string
  default     = "1"
}
```

### Terraform Resources
```hcl
# Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "${var.service_name}-repo"
  format        = "DOCKER"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      ports {
        container_port = 8080
      }

      # Environment variables from Secret Manager
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }
    }

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# IAM for public access
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

## Deployment Commands

```bash
# Authenticate
gcloud auth login
gcloud config set project ${PROJECT_ID}

# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# Build and push container
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest

# Deploy (without Terraform)
gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 10
```

## Best Practices

### Container Optimization
1. Use multi-stage Docker builds to minimize image size
2. Run as non-root user for security
3. Set `PYTHONDONTWRITEBYTECODE=1` for Python apps
4. Configure health check endpoint at `/health` or `/`

### Scaling Configuration
1. Set `min_instances: 0` for cost optimization
2. Set `min_instances: 1` for latency-sensitive APIs
3. Set concurrency based on app characteristics (default: 80)
4. Use CPU allocation "always on" for background tasks

### Security
1. Enable Cloud Run authentication for internal APIs
2. Use Secret Manager for database URLs and API keys
3. Configure VPC connector for private database access
4. Add Cloud Armor for public APIs

## Cost Breakdown

| Traffic Level | Requests/Day | Monthly Cost |
|--------------|--------------|--------------|
| Low | 10k | $0-5 (free tier) |
| Medium | 100k | $15-30 |
| High | 1M | $100-300 |

### Pricing Components
- CPU: $0.000024/vCPU-second
- Memory: $0.0000025/GiB-second
- Requests: $0.40/million (first 2M free)
- Networking: $0.12/GB egress

### Free Tier (per month)
- 2 million requests
- 360,000 vCPU-seconds
- 180,000 GiB-seconds

## Common Mistakes

1. **Not configuring concurrency**: Default 80 may not suit your app
2. **Ignoring cold starts**: Use min_instances=1 for latency-sensitive APIs
3. **Missing health checks**: Cloud Run needs a responsive endpoint
4. **Hardcoded secrets**: Always use Secret Manager
5. **Over-provisioning**: Start small and scale up based on metrics
6. **Not enabling Cloud CDN**: For cacheable API responses

## Example Configuration

```yaml
project_name: my-fastapi-app
provider: gcp
region: us-central1
architecture_type: api_service

resources:
  - id: registry
    type: artifact_registry
    name: my-fastapi-app-repo
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: api
    type: cloud_run
    name: my-fastapi-app
    provider: gcp
    config:
      port: 8080
      memory: 512Mi
      cpu: "1"
      min_instances: 0
      max_instances: 10
      concurrency: 80
      allow_unauthenticated: true
      env_vars:
        ENV: production
    depends_on:
      - registry
```

## Sources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Best Practices for Cloud Run](https://cloud.google.com/run/docs/best-practices)
