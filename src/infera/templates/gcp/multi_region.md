# GCP Multi-Region High Availability

## Overview

Deploy applications across multiple GCP regions for maximum availability, disaster recovery, and low-latency global access. Ideal for mission-critical applications requiring 99.99%+ uptime SLA.

## Detection Signals

Use this template when:
- Global user base requiring low latency
- Mission-critical availability requirements
- Disaster recovery requirements
- Compliance requirements for data residency
- RPO/RTO requirements under 1 hour

## Architecture

```
                              ┌─────────────────────────────────┐
                              │      Global Load Balancer       │
                              │      (Anycast IP)               │
                              └───────────────┬─────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
          ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
          │  us-central1    │       │  europe-west1   │       │  asia-east1     │
          │                 │       │                 │       │                 │
          │ ┌─────────────┐ │       │ ┌─────────────┐ │       │ ┌─────────────┐ │
          │ │ Cloud Run   │ │       │ │ Cloud Run   │ │       │ │ Cloud Run   │ │
          │ │ (Primary)   │ │       │ │ (Replica)   │ │       │ │ (Replica)   │ │
          │ └──────┬──────┘ │       │ └──────┬──────┘ │       │ └──────┬──────┘ │
          │        │        │       │        │        │       │        │        │
          │ ┌──────┴──────┐ │       │ ┌──────┴──────┐ │       │ ┌──────┴──────┐ │
          │ │ Cloud SQL   │◄┼───────┼─┤ Cloud SQL   │─┼───────┼─┤ Cloud SQL   │ │
          │ │ (Primary)   │ │ Repl  │ │ (Read)      │ │ Repl  │ │ (Read)      │ │
          │ └─────────────┘ │       │ └─────────────┘ │       │ └─────────────┘ │
          └─────────────────┘       └─────────────────┘       └─────────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Global Load Balancer | Traffic distribution | `google_compute_global_forwarding_rule` |
| Cloud Run (multi-region) | Application hosting | `google_cloud_run_v2_service` |
| Cloud SQL (regional HA) | Database | `google_sql_database_instance` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud CDN | Static content caching | Enabled on backend |
| Cloud Armor | DDoS protection | `google_compute_security_policy` |
| Memorystore Global | Distributed cache | `google_redis_cluster` |
| Cloud DNS | DNS management | `google_dns_managed_zone` |

## Configuration

### Terraform Variables
```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "service_name" {
  description = "Service name"
  type        = string
}

variable "regions" {
  description = "Deployment regions"
  type        = list(string)
  default     = ["us-central1", "europe-west1", "asia-east1"]
}

variable "primary_region" {
  description = "Primary region for database writes"
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "Custom domain"
  type        = string
}
```

### Terraform Resources
```hcl
# Artifact Registry (single region, replicated images)
resource "google_artifact_registry_repository" "repo" {
  location      = var.primary_region
  repository_id = "${var.service_name}-repo"
  format        = "DOCKER"
}

# Cloud Run services in each region
resource "google_cloud_run_v2_service" "app" {
  for_each = toset(var.regions)

  name     = "${var.service_name}-${each.value}"
  location = each.value

  template {
    containers {
      image = "${var.primary_region}-docker.pkg.dev/${var.project_id}/${var.service_name}-repo/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "REGION"
        value = each.value
      }

      env {
        name  = "PRIMARY_REGION"
        value = var.primary_region
      }

      env {
        name  = "DATABASE_URL"
        value = each.value == var.primary_region ? local.primary_db_url : local.replica_db_urls[each.value]
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 20
    }
  }
}

# Network Endpoint Groups for each region
resource "google_compute_region_network_endpoint_group" "neg" {
  for_each = toset(var.regions)

  name                  = "${var.service_name}-neg-${each.value}"
  network_endpoint_type = "SERVERLESS"
  region                = each.value

  cloud_run {
    service = google_cloud_run_v2_service.app[each.value].name
  }
}

# Backend Service with multiple NEGs
resource "google_compute_backend_service" "app" {
  name                  = "${var.service_name}-backend"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  dynamic "backend" {
    for_each = google_compute_region_network_endpoint_group.neg
    content {
      group = backend.value.id
    }
  }

  # Health check
  health_checks = [google_compute_health_check.app.id]

  # CDN
  enable_cdn = true
  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    negative_caching  = true
  }

  # Logging
  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# Health Check
resource "google_compute_health_check" "app" {
  name = "${var.service_name}-health"

  https_health_check {
    port         = "443"
    request_path = "/health"
  }

  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3
}

# URL Map
resource "google_compute_url_map" "app" {
  name            = "${var.service_name}-url-map"
  default_service = google_compute_backend_service.app.id
}

# HTTPS Proxy
resource "google_compute_target_https_proxy" "app" {
  name             = "${var.service_name}-https-proxy"
  url_map          = google_compute_url_map.app.id
  ssl_certificates = [google_compute_managed_ssl_certificate.app.id]
}

# Global IP
resource "google_compute_global_address" "app" {
  name = "${var.service_name}-ip"
}

# Forwarding Rule
resource "google_compute_global_forwarding_rule" "app" {
  name                  = "${var.service_name}-forwarding"
  target                = google_compute_target_https_proxy.app.id
  port_range            = "443"
  ip_address            = google_compute_global_address.app.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# SSL Certificate
resource "google_compute_managed_ssl_certificate" "app" {
  name = "${var.service_name}-cert"

  managed {
    domains = [var.domain]
  }
}

# Cloud SQL Primary (with regional HA)
resource "google_sql_database_instance" "primary" {
  name             = "${var.service_name}-db-primary"
  database_version = "POSTGRES_15"
  region           = var.primary_region

  settings {
    tier              = "db-custom-4-8192"
    availability_type = "REGIONAL"  # Automatic failover within region

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }
  }

  deletion_protection = true
}

# Cross-region read replicas
resource "google_sql_database_instance" "replica" {
  for_each = toset([for r in var.regions : r if r != var.primary_region])

  name                 = "${var.service_name}-db-replica-${each.value}"
  database_version     = "POSTGRES_15"
  region               = each.value
  master_instance_name = google_sql_database_instance.primary.name

  replica_configuration {
    failover_target = false
  }

  settings {
    tier = "db-custom-2-4096"
  }
}

# Cloud Armor for DDoS protection
resource "google_compute_security_policy" "app" {
  name = "${var.service_name}-security"

  # Default rule
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow"
  }

  # Rate limiting
  rule {
    action   = "rate_based_ban"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 1000
        interval_sec = 60
      }
    }
    description = "Rate limit"
  }

  # Adaptive protection
  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable = true
    }
  }
}
```

## Application Code Patterns

### Read/Write Routing
```python
# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REGION = os.environ['REGION']
PRIMARY_REGION = os.environ['PRIMARY_REGION']
PRIMARY_DB_URL = os.environ['PRIMARY_DATABASE_URL']
REPLICA_DB_URL = os.environ.get('REPLICA_DATABASE_URL', PRIMARY_DB_URL)

# Write to primary
write_engine = create_engine(PRIMARY_DB_URL, pool_size=5)
WriteSession = sessionmaker(bind=write_engine)

# Read from local replica (or primary if in primary region)
read_engine = create_engine(REPLICA_DB_URL, pool_size=10)
ReadSession = sessionmaker(bind=read_engine)

def get_write_session():
    return WriteSession()

def get_read_session():
    return ReadSession()
```

### Health Check Endpoint
```python
# health.py
from flask import Blueprint, jsonify
import os

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health():
    """Health check for load balancer."""
    return jsonify({
        'status': 'healthy',
        'region': os.environ.get('REGION'),
        'version': os.environ.get('VERSION', 'unknown')
    })

@health_bp.route('/ready')
def ready():
    """Readiness check including dependencies."""
    # Check database connectivity
    try:
        db.session.execute('SELECT 1')
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'

    return jsonify({
        'status': 'ready' if db_status == 'connected' else 'not_ready',
        'database': db_status,
        'region': os.environ.get('REGION')
    })
```

## Deployment Commands

```bash
# Deploy to all regions
for REGION in us-central1 europe-west1 asia-east1; do
  gcloud run deploy ${SERVICE_NAME}-${REGION} \
    --image ${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest \
    --region ${REGION} \
    --min-instances 1 \
    --max-instances 20 \
    --set-env-vars REGION=${REGION},PRIMARY_REGION=${PRIMARY_REGION}
done

# Update load balancer
gcloud compute backend-services update ${SERVICE_NAME}-backend \
  --global \
  --enable-cdn

# Check regional health
for REGION in us-central1 europe-west1 asia-east1; do
  echo "Checking ${REGION}..."
  curl -s https://${REGION}-run.googleapis.com/.../health
done
```

## Best Practices

### Traffic Management
1. Use anycast for automatic geo-routing
2. Configure health checks with appropriate thresholds
3. Set up failover policies between regions
4. Monitor latency per region

### Database Strategy
1. Write to primary region only
2. Read from local replicas when possible
3. Handle replication lag in application
4. Plan for cross-region failover

### Cost Optimization
1. Use Cloud CDN for static content
2. Right-size instances per region based on traffic
3. Consider Committed Use Discounts
4. Monitor and optimize egress costs

## Cost Breakdown

| Component | Per Region | 3 Regions |
|-----------|------------|-----------|
| Cloud Run (min instances) | ~$50/month | ~$150/month |
| Cloud SQL (db-custom-2-4096) | ~$100/month | ~$300/month |
| Load Balancer | ~$20/month | ~$20/month (shared) |
| Cloud CDN | ~$0.08/GB | ~$0.08/GB |
| Cloud Armor | ~$5/month + $0.75/M requests | Same |
| **Total Base** | - | **~$475/month** |

### Traffic Costs
- Inter-region egress: $0.01/GB (within GCP)
- Internet egress: $0.12/GB

## Common Mistakes

1. **No read replicas**: All traffic going to primary DB
2. **Missing health checks**: Bad instances receive traffic
3. **Ignoring replication lag**: Stale reads causing issues
4. **Single region DNS**: Not using Cloud DNS global
5. **No failover testing**: Untested disaster recovery
6. **Over-provisioned**: Same capacity in all regions

## Example Configuration

```yaml
project_name: global-api
provider: gcp
architecture_type: multi_region

regions:
  - us-central1  # Primary
  - europe-west1
  - asia-east1

resources:
  - id: global-lb
    type: global_load_balancer
    name: global-api-lb
    provider: gcp
    config:
      enable_cdn: true
      cloud_armor: true

  - id: app-us
    type: cloud_run
    name: global-api-us-central1
    provider: gcp
    config:
      region: us-central1
      min_instances: 1
      max_instances: 20
    depends_on:
      - global-lb

  - id: app-eu
    type: cloud_run
    name: global-api-europe-west1
    provider: gcp
    config:
      region: europe-west1
      min_instances: 1
      max_instances: 10
    depends_on:
      - global-lb

  - id: app-asia
    type: cloud_run
    name: global-api-asia-east1
    provider: gcp
    config:
      region: asia-east1
      min_instances: 1
      max_instances: 10
    depends_on:
      - global-lb

  - id: db-primary
    type: cloud_sql
    name: global-api-db-primary
    provider: gcp
    config:
      region: us-central1
      tier: db-custom-4-8192
      availability_type: REGIONAL
      backup_enabled: true

  - id: db-replica-eu
    type: cloud_sql_replica
    name: global-api-db-eu
    provider: gcp
    config:
      region: europe-west1
      master_instance: global-api-db-primary
    depends_on:
      - db-primary

  - id: db-replica-asia
    type: cloud_sql_replica
    name: global-api-db-asia
    provider: gcp
    config:
      region: asia-east1
      master_instance: global-api-db-primary
    depends_on:
      - db-primary

domain:
  enabled: true
  name: api.example.com
  ssl: true
  dns_provider: cloud_dns
```

## Sources

- [Global Load Balancing](https://cloud.google.com/load-balancing/docs/https)
- [Cloud SQL Cross-Region Replicas](https://cloud.google.com/sql/docs/postgres/replication)
- [Multi-Region Design Patterns](https://cloud.google.com/architecture/disaster-recovery)
