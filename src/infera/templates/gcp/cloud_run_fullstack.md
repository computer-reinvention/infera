# GCP Cloud Run Full-Stack Application

## Overview

Deploy full-stack applications (SSR frontend + API + database) on Cloud Run with Cloud SQL. Ideal for Next.js, Nuxt, Django with templates, Rails, or any application that combines frontend rendering with backend logic and database persistence.

## Detection Signals

Use this template when:
- Next.js, Nuxt, SvelteKit with SSR mode detected
- Django/Rails with template rendering
- Database ORM detected (SQLAlchemy, Prisma, ActiveRecord)
- `DATABASE_URL` or similar environment variable patterns
- Combined frontend and backend in single codebase

## Architecture

```
                                   ┌─────────────────┐
                    ┌─────────────►│  Cloud Storage  │
                    │              │  (static assets)│
                    │              └─────────────────┘
    Internet ───────┤
                    │              ┌─────────────────┐
                    └─────────────►│   Cloud Run     │
                                   │  (SSR + API)    │
                                   └────────┬────────┘
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                        VPC Connector  Cloud SQL    Secret Manager
                              │        (PostgreSQL)
                              └────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Run Service | App hosting | `google_cloud_run_v2_service` |
| Cloud SQL | PostgreSQL/MySQL | `google_sql_database_instance` |
| Artifact Registry | Docker images | `google_artifact_registry_repository` |
| VPC Connector | Private DB access | `google_vpc_access_connector` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud Storage | Static assets | `google_storage_bucket` |
| Cloud CDN | Global caching | `google_compute_backend_bucket` |
| Load Balancer | Custom domain | `google_compute_global_address` |
| Cloud Armor | Security | `google_compute_security_policy` |
| Redis (Memorystore) | Session/cache | `google_redis_instance` |

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
  description = "Application name"
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine type"
  type        = string
  default     = "db-f1-micro"
}

variable "db_version" {
  description = "Database version"
  type        = string
  default     = "POSTGRES_15"
}
```

### Terraform Resources
```hcl
# VPC for private connectivity
resource "google_compute_network" "vpc" {
  name                    = "${var.service_name}-vpc"
  auto_create_subnetworks = true
}

# VPC Connector for Cloud Run -> Cloud SQL
resource "google_vpc_access_connector" "connector" {
  name          = "${var.service_name}-connector"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
}

# Cloud SQL Instance
resource "google_sql_database_instance" "main" {
  name             = "${var.service_name}-db"
  database_version = var.db_version
  region           = var.region

  settings {
    tier = var.db_tier

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled            = true
      start_time         = "03:00"
      binary_log_enabled = false
    }
  }

  deletion_protection = true
}

# Database
resource "google_sql_database" "database" {
  name     = var.service_name
  instance = google_sql_database_instance.main.name
}

# Database User
resource "google_sql_user" "user" {
  name     = var.service_name
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# Store DB password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.service_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region

  template {
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}-repo/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql://${google_sql_user.user.name}:${random_password.db_password.result}@${google_sql_database_instance.main.private_ip_address}:5432/${google_sql_database.database.name}"
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
  }
}
```

## Deployment Commands

```bash
# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  vpcaccess.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

# Build and push
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest

# Run migrations (using Cloud Run jobs)
gcloud run jobs create ${SERVICE_NAME}-migrate \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest \
  --region ${REGION} \
  --vpc-connector ${SERVICE_NAME}-connector \
  --set-env-vars DATABASE_URL=${DATABASE_URL} \
  --command "npm" \
  --args "run,migrate"

gcloud run jobs execute ${SERVICE_NAME}-migrate --region ${REGION}
```

## Best Practices

### Database Configuration
1. Always use VPC Connector for private database access
2. Never expose Cloud SQL to public internet
3. Enable automated backups with point-in-time recovery
4. Use connection pooling (PgBouncer or built-in)
5. Set appropriate connection limits in Cloud Run

### Application Configuration
1. Set `min_instances: 1` to avoid cold starts with DB connections
2. Implement connection pooling in your application
3. Use health checks that verify database connectivity
4. Configure graceful shutdown for database connections

### Security
1. Store database credentials in Secret Manager
2. Use IAM authentication when possible
3. Encrypt data at rest (enabled by default)
4. Enable Cloud SQL Auth Proxy for local development

## Cost Breakdown

| Component | Low Traffic | Medium Traffic | High Traffic |
|-----------|-------------|----------------|--------------|
| Cloud Run | $10-30/mo | $50-150/mo | $200-500/mo |
| Cloud SQL (db-f1-micro) | $10/mo | - | - |
| Cloud SQL (db-g1-small) | - | $30/mo | - |
| Cloud SQL (db-custom-2-4096) | - | - | $100/mo |
| VPC Connector | $7/mo | $7/mo | $7/mo |
| **Total** | **$27-47/mo** | **$87-187/mo** | **$307-607/mo** |

### Cloud SQL Pricing
- db-f1-micro: ~$10/month (shared, 0.6GB RAM)
- db-g1-small: ~$30/month (shared, 1.7GB RAM)
- db-custom-2-4096: ~$100/month (2 vCPU, 4GB RAM)

## Common Mistakes

1. **Not using VPC Connector**: Exposing database to public internet
2. **Forgetting connection pooling**: Exhausting database connections
3. **Missing health checks**: Database connectivity not verified
4. **Skipping migrations**: Running app without schema updates
5. **Over-provisioned database**: Starting with larger tier than needed
6. **No backup strategy**: Missing point-in-time recovery setup

## Example Configuration

```yaml
project_name: my-nextjs-app
provider: gcp
region: us-central1
architecture_type: fullstack_app

resources:
  - id: vpc
    type: vpc_network
    name: my-nextjs-app-vpc
    provider: gcp
    config:
      auto_create_subnetworks: true

  - id: vpc-connector
    type: vpc_connector
    name: my-nextjs-app-connector
    provider: gcp
    config:
      region: us-central1
      ip_cidr_range: "10.8.0.0/28"
    depends_on:
      - vpc

  - id: database
    type: cloud_sql
    name: my-nextjs-app-db
    provider: gcp
    config:
      database_version: POSTGRES_15
      tier: db-f1-micro
      storage_size: 10
      backup_enabled: true
      private_network: true
    depends_on:
      - vpc

  - id: registry
    type: artifact_registry
    name: my-nextjs-app-repo
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: app
    type: cloud_run
    name: my-nextjs-app
    provider: gcp
    config:
      port: 3000
      memory: 1Gi
      cpu: "2"
      min_instances: 1
      max_instances: 10
      vpc_connector: my-nextjs-app-connector
      env_vars:
        NODE_ENV: production
    depends_on:
      - registry
      - database
      - vpc-connector
```

## Sources

- [Cloud Run + Cloud SQL](https://cloud.google.com/sql/docs/postgres/connect-run)
- [VPC Connector](https://cloud.google.com/vpc/docs/serverless-vpc-access)
- [Cloud SQL Best Practices](https://cloud.google.com/sql/docs/postgres/best-practices)
