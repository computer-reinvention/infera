# Containerized Application

## Overview

This template is for applications that are already containerized with Docker. It deploys containers to Cloud Run, which provides serverless container hosting with automatic scaling.

## Detection Signals

Use this template when you detect:
- Dockerfile in project root
- docker-compose.yml (will extract main service)
- .dockerignore file
- Container-specific configuration

## Resources Needed

### Required
- **Cloud Run**: Serverless container hosting
- **Artifact Registry**: Container image storage

### Optional (based on Dockerfile analysis)
- **Cloud SQL**: If database connection detected
- **Cloud Storage**: If file storage needed
- **Secret Manager**: For environment secrets
- **Cloud Pub/Sub**: If message queue detected
- **Cloud Tasks**: If background jobs detected

## Dockerfile Analysis

When analyzing the Dockerfile, extract:

1. **Base image**: Determines runtime requirements
2. **EXPOSE ports**: HTTP port for Cloud Run
3. **ENV variables**: Required configuration
4. **CMD/ENTRYPOINT**: Start command
5. **Multi-stage**: Indicates optimized build

### Common Base Images

| Base Image | Typical Use | Cloud Run Compatible |
|------------|-------------|---------------------|
| python:3.x | Python apps | Yes |
| node:18 | Node.js apps | Yes |
| golang:1.x | Go apps | Yes |
| openjdk:17 | Java apps | Yes |
| nginx:alpine | Static sites | Yes (but prefer Storage) |

## Best Practices

### Container Optimization
1. Use multi-stage builds to reduce image size
2. Run as non-root user
3. Use specific version tags (not :latest in production)
4. Minimize layers and clean up in same layer

### Cloud Run Configuration
1. Set appropriate memory based on container needs
2. Configure concurrency based on application type
3. Use startup probes for slow-starting containers
4. Set request timeout appropriately

### Health Checks
1. Implement /health or /healthz endpoint
2. Return 200 for healthy, 5xx for unhealthy
3. Keep health check lightweight

## Cost Optimization

Same as API Service template - Cloud Run pricing:

| Resource | Typical Cost | Notes |
|----------|-------------|-------|
| CPU | $0.000024/vCPU-sec | Only when processing |
| Memory | $0.0000025/GiB-sec | Only when processing |
| Requests | $0.40/million | First 2M free |

**Tips**:
- Right-size memory based on actual usage
- Use min-instances=0 for non-critical workloads
- Consider spot/preemptible for batch jobs

## Common Mistakes

1. **Large container images**: Use multi-stage builds
2. **Running as root**: Security risk
3. **Hardcoded configuration**: Use environment variables
4. **No graceful shutdown**: Handle SIGTERM properly
5. **Missing health checks**: Required for proper scaling

## GCP-Specific Implementation

### Artifact Registry
```yaml
resource:
  type: artifact_registry
  name: ${project}-images
  config:
    format: DOCKER
    location: us-central1
    description: Container images for ${project}
```

### Cloud Run from Dockerfile
```yaml
resource:
  type: cloud_run
  name: ${project}
  config:
    # Image built from Dockerfile
    image: us-central1-docker.pkg.dev/${gcp_project}/${project}-images/${project}:latest
    port: ${detected_port}  # From EXPOSE in Dockerfile
    memory: ${detected_memory}  # Based on base image
    cpu: "1"
    min_instances: 0
    max_instances: 10
    startup_probe:
      path: /health
      initial_delay_seconds: 10
    env_vars: ${detected_env_vars}  # From ENV in Dockerfile
```

## Docker Compose Handling

If docker-compose.yml is detected:

1. **Identify main service**: Usually the one with ports exposed
2. **Extract configuration**: Environment variables, volumes
3. **Handle dependencies**: Database, Redis → Cloud services
4. **Ignore local-only services**: Adminer, Mailhog, etc.

### Mapping docker-compose to GCP

| Docker Compose | GCP Equivalent |
|----------------|----------------|
| Main service | Cloud Run |
| postgres/mysql | Cloud SQL |
| redis | Memorystore |
| volumes | Cloud Storage |
| networks | VPC |

## Example Configuration

For a containerized Python application:

```yaml
project_name: my-container-app
provider: gcp
region: us-central1
architecture_type: containerized

resources:
  - id: registry
    type: artifact_registry
    name: my-container-app-images
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: app
    type: cloud_run
    name: my-container-app
    provider: gcp
    config:
      image: us-central1-docker.pkg.dev/${project_id}/my-container-app-images/app:latest
      port: 8080
      memory: 512Mi
      cpu: "1"
      min_instances: 0
      max_instances: 10
      concurrency: 80
      startup_probe:
        path: /health
        initial_delay_seconds: 5
      allow_unauthenticated: true
    depends_on:
      - registry
```

## Build and Deploy Commands

```bash
# Build container
docker build -t us-central1-docker.pkg.dev/${PROJECT_ID}/${PROJECT}-images/app:latest .

# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Push to registry
docker push us-central1-docker.pkg.dev/${PROJECT_ID}/${PROJECT}-images/app:latest

# Deploy to Cloud Run
gcloud run deploy ${PROJECT} \
  --image us-central1-docker.pkg.dev/${PROJECT_ID}/${PROJECT}-images/app:latest \
  --region us-central1 \
  --allow-unauthenticated
```

## Estimated Costs

Similar to API Service - depends on traffic and resource usage.

For a containerized web service (moderate traffic):
- Cloud Run: ~$15-50/month
- Artifact Registry: ~$0.10/GB storage
- **Total: ~$15-50/month**

With database:
- Add Cloud SQL: ~$10-50/month
- Add VPC Connector: ~$7/month
- **Total: ~$35-110/month**
