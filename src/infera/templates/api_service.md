# API Service

## Overview

This template is for hosting backend API services including REST APIs, GraphQL endpoints, and microservices. It uses Cloud Run for serverless container hosting with automatic scaling.

## Detection Signals

Use this template when you detect:
- FastAPI, Flask, Django REST Framework, or Express.js
- API route definitions (routers/, routes/, api/)
- No frontend or separate frontend deployment
- Dockerfile with HTTP port exposed
- requirements.txt or package.json with web framework

## Resources Needed

### Required
- **Cloud Run Service**: Serverless container hosting
  - Auto-scaling based on traffic
  - Scale to zero when idle
  - Managed HTTPS endpoint

- **Artifact Registry**: Container image storage
  - Store Docker images
  - Integrated with Cloud Build

### Optional
- **Cloud SQL**: If database is detected
- **Secret Manager**: For API keys and credentials
- **Cloud Load Balancer**: For custom domain with SSL
- **Cloud Armor**: For WAF/DDoS protection

## Best Practices

### Container Configuration
1. Use multi-stage Docker builds for smaller images
2. Run as non-root user for security
3. Set appropriate memory and CPU limits
4. Configure health check endpoint

### Scaling Configuration
1. Set min instances to 0 for cost optimization (or 1 for low latency)
2. Set max instances based on expected traffic
3. Configure concurrency based on application characteristics
4. Use CPU-based autoscaling for compute-heavy workloads

### Security
1. Enable Cloud Run authentication if not public API
2. Use Secret Manager for sensitive configuration
3. Configure VPC connector for private database access
4. Enable Cloud Armor for public APIs

## Cost Optimization

| Resource | Typical Cost | Notes |
|----------|-------------|-------|
| CPU | $0.000024/vCPU-sec | Only when processing |
| Memory | $0.0000025/GiB-sec | Only when processing |
| Requests | $0.40/million | First 2M free |
| Networking | $0.12/GB egress | To internet |

**Free Tier**: 2 million requests, 360k vCPU-seconds, 180k GiB-seconds per month

**Tips**:
- Scale to zero eliminates idle costs
- Right-size CPU/memory for your workload
- Use regional endpoints to reduce egress

## Common Mistakes

1. **Not setting concurrency**: Default may not match your app
2. **Cold start latency**: Use min-instances=1 for latency-sensitive APIs
3. **Missing health checks**: Required for proper scaling
4. **Hardcoded secrets**: Use Secret Manager instead

## GCP-Specific Implementation

### Cloud Run Configuration
```yaml
resource:
  type: cloud_run
  name: ${project}-api
  config:
    image: gcr.io/${gcp_project}/${project}-api:latest
    port: 8080
    memory: 512Mi
    cpu: "1"
    min_instances: 0
    max_instances: 10
    concurrency: 80
    timeout: 300s
    env_vars:
      ENV: production
    secrets:
      - DATABASE_URL: ${project}-db-url:latest
```

### Artifact Registry
```yaml
resource:
  type: artifact_registry
  name: ${project}-registry
  config:
    format: DOCKER
    location: us-central1
```

### Secret Manager (for sensitive config)
```yaml
resource:
  type: secret_manager
  name: ${project}-db-url
  config:
    # Value set separately, not in config
```

### IAM for Public Access
```yaml
iam_binding:
  service: ${project}-api
  role: roles/run.invoker
  members:
    - allUsers  # For public API
```

## Deployment Commands

```bash
# Build and push container
docker build -t gcr.io/${PROJECT_ID}/${PROJECT}-api:latest .
docker push gcr.io/${PROJECT_ID}/${PROJECT}-api:latest

# Deploy to Cloud Run
gcloud run deploy ${PROJECT}-api \
  --image gcr.io/${PROJECT_ID}/${PROJECT}-api:latest \
  --region us-central1 \
  --allow-unauthenticated
```

## Example Configuration

For a FastAPI backend:

```yaml
project_name: my-api
provider: gcp
region: us-central1
architecture_type: api_service

resources:
  - id: registry
    type: artifact_registry
    name: my-api-registry
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: api
    type: cloud_run
    name: my-api
    provider: gcp
    config:
      image: us-central1-docker.pkg.dev/${project_id}/my-api-registry/my-api:latest
      port: 8080
      memory: 512Mi
      cpu: "1"
      min_instances: 0
      max_instances: 10
      concurrency: 80
      allow_unauthenticated: true
    depends_on:
      - registry
```

## With Database

If database is detected, add Cloud SQL:

```yaml
resources:
  # ... previous resources ...

  - id: database
    type: cloud_sql
    name: my-api-db
    provider: gcp
    config:
      database_version: POSTGRES_15
      tier: db-f1-micro
      storage_size: 10
      backup_enabled: true
      private_network: true
```

## Estimated Costs

For a low-traffic API (10k requests/day, light processing):
- Cloud Run: ~$0-5/month (may fit in free tier)
- **Total: ~$0-5/month**

For a medium-traffic API (100k requests/day):
- Cloud Run: ~$15-30/month
- Cloud SQL (if needed): ~$10-30/month
- **Total: ~$25-60/month**

For a high-traffic API (1M+ requests/day):
- Cloud Run: ~$100-300/month
- Cloud SQL (if needed): ~$50-200/month
- **Total: ~$150-500/month**
