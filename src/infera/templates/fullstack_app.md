# Full Stack Application

## Overview

This template is for full stack applications that combine frontend and backend, typically with a database. It handles both static assets and dynamic server-side rendering or API endpoints.

## Detection Signals

Use this template when you detect:
- Frontend framework (React, Vue) + Backend framework (FastAPI, Express)
- Next.js or Nuxt with SSR (server-side rendering)
- Django or Rails with templates
- Database dependencies (psycopg2, pymongo, etc.)
- Both `package.json` and `requirements.txt` (or monorepo structure)

## Resources Needed

### Required
- **Cloud Run**: For backend/SSR
- **Cloud Storage**: For static assets (if separate frontend)
- **Cloud SQL**: For database (PostgreSQL recommended)
- **Artifact Registry**: Container images

### Optional
- **Cloud CDN**: For static assets
- **Cloud Load Balancer**: For custom domain routing
- **Redis (Memorystore)**: For caching/sessions
- **Secret Manager**: For credentials

## Architecture Patterns

### Pattern A: Monolith (SSR Framework)
```
User → Cloud Run (Next.js/Nuxt/Django) → Cloud SQL
```
Best for: Next.js SSR, Django with templates, Rails

### Pattern B: Separated Frontend/Backend
```
User → Cloud Storage/CDN (React SPA)
         ↓
       Cloud Run (API) → Cloud SQL
```
Best for: React + FastAPI, Vue + Express

### Pattern C: Microservices
```
User → Load Balancer → Cloud Run (Frontend)
                    → Cloud Run (API)
                    → Cloud SQL
```
Best for: Complex applications, team separation

## Best Practices

### Database
1. Use private IP for Cloud SQL (VPC connector)
2. Enable automated backups
3. Use connection pooling (PgBouncer or built-in)
4. Start with smallest tier, scale based on metrics

### Caching
1. Use Redis for session storage in multi-instance setups
2. Cache database queries for read-heavy workloads
3. Use CDN for static assets

### Security
1. Never expose database to public internet
2. Use Secret Manager for database credentials
3. Enable SSL for all connections
4. Use IAM for service-to-service auth

## Cost Optimization

| Resource | Typical Cost | Notes |
|----------|-------------|-------|
| Cloud Run | $0-50/month | Depends on traffic |
| Cloud SQL (db-f1-micro) | ~$10/month | Smallest tier |
| Cloud SQL (db-g1-small) | ~$30/month | 1.7GB RAM |
| Cloud Storage | ~$1-5/month | Static assets |
| VPC Connector | ~$7/month | For private SQL |

**Tips**:
- Cloud SQL is often the largest cost
- Consider serverless Cloud SQL for dev/staging
- Use scale-to-zero for Cloud Run

## Common Mistakes

1. **Public database**: Always use private IP
2. **No connection pooling**: Exhausts database connections
3. **Missing VPC connector**: Required for private SQL access
4. **Separate regions**: Keep all resources in same region

## GCP-Specific Implementation

### Cloud SQL Configuration
```yaml
resource:
  type: cloud_sql
  name: ${project}-db
  config:
    database_version: POSTGRES_15
    tier: db-f1-micro  # Smallest, upgrade as needed
    region: us-central1
    storage_size: 10  # GB, auto-grows
    storage_type: SSD
    backup_configuration:
      enabled: true
      start_time: "03:00"
    ip_configuration:
      private_network: projects/${gcp_project}/global/networks/default
      ipv4_enabled: false  # No public IP
```

### Cloud Run with VPC Connector
```yaml
resource:
  type: cloud_run
  name: ${project}-app
  config:
    image: gcr.io/${gcp_project}/${project}:latest
    port: 8080
    memory: 1Gi
    cpu: "1"
    min_instances: 1  # Avoid cold starts
    max_instances: 10
    vpc_connector: ${project}-connector
    env_vars:
      DATABASE_URL: "postgresql://user:pass@/dbname?host=/cloudsql/${connection_name}"
```

### VPC Connector
```yaml
resource:
  type: vpc_connector
  name: ${project}-connector
  config:
    region: us-central1
    ip_cidr_range: 10.8.0.0/28
    network: default
```

## Example Configuration

For a Next.js + PostgreSQL application:

```yaml
project_name: my-app
provider: gcp
region: us-central1
architecture_type: fullstack_app

resources:
  - id: registry
    type: artifact_registry
    name: my-app-registry
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: database
    type: cloud_sql
    name: my-app-db
    provider: gcp
    config:
      database_version: POSTGRES_15
      tier: db-f1-micro
      storage_size: 10
      backup_enabled: true
      private_network: true

  - id: vpc-connector
    type: vpc_connector
    name: my-app-connector
    provider: gcp
    config:
      region: us-central1
      ip_cidr_range: 10.8.0.0/28

  - id: app
    type: cloud_run
    name: my-app
    provider: gcp
    config:
      image: us-central1-docker.pkg.dev/${project_id}/my-app-registry/my-app:latest
      port: 3000
      memory: 1Gi
      cpu: "1"
      min_instances: 1
      max_instances: 10
      vpc_connector: my-app-connector
      allow_unauthenticated: true
    depends_on:
      - registry
      - database
      - vpc-connector
```

## Estimated Costs

For a small full stack app (low traffic, minimal data):
- Cloud Run: ~$5-15/month
- Cloud SQL (db-f1-micro): ~$10/month
- VPC Connector: ~$7/month
- Storage: ~$1/month
- **Total: ~$25-35/month**

For a medium full stack app (moderate traffic):
- Cloud Run: ~$30-50/month
- Cloud SQL (db-g1-small): ~$30/month
- VPC Connector: ~$7/month
- Storage + CDN: ~$10/month
- **Total: ~$80-100/month**

For a production app (high traffic, larger database):
- Cloud Run: ~$100-200/month
- Cloud SQL (db-n1-standard-1): ~$50-100/month
- VPC Connector: ~$7/month
- Storage + CDN: ~$20-50/month
- **Total: ~$200-400/month**
