# GCP Cloud SQL High Availability

## Overview

Deploy highly available PostgreSQL or MySQL databases on Cloud SQL with automatic failover, read replicas, and point-in-time recovery. Ideal for production workloads requiring 99.95% availability SLA.

## Detection Signals

Use this template when:
- Production database requirements
- High availability needs
- Read-heavy workloads (need replicas)
- Compliance requirements for data durability
- Multi-region disaster recovery needs

## Architecture

```
                        ┌───────────────────────────────────────────────┐
                        │              Regional HA Configuration         │
                        │                                               │
    Cloud Run ─────────►│   ┌─────────────┐      ┌─────────────┐       │
    (Primary)          │   │   Primary   │◄────►│  Standby    │       │
         │             │   │   (Zone A)  │ Sync │  (Zone B)   │       │
         │             │   │   Write     │ Repl │  Failover   │       │
         │             │   └──────┬──────┘      └─────────────┘       │
         │             │          │                                    │
    Read Queries       │   ┌──────┼──────┐                            │
         │             │   │      │      │                            │
         ▼             │   ▼      ▼      ▼                            │
    ┌────────┐         │ ┌────┐ ┌────┐ ┌────┐                         │
    │ Read   │         │ │Rep1│ │Rep2│ │Rep3│  Async Read Replicas   │
    │ Pool   │◄────────┤ └────┘ └────┘ └────┘                         │
    └────────┘         │                                               │
                        └───────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud SQL Instance | Primary database | `google_sql_database_instance` |
| Database | Application database | `google_sql_database` |
| User | Database credentials | `google_sql_user` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Read Replica | Read scaling | `google_sql_database_instance` |
| Private IP | Secure networking | `google_compute_global_address` |
| Secret Manager | Credential storage | `google_secret_manager_secret` |
| Backup | Point-in-time recovery | Enabled on instance |

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

variable "instance_name" {
  description = "Cloud SQL instance name"
  type        = string
}

variable "database_version" {
  description = "Database version"
  type        = string
  default     = "POSTGRES_15"  # or MYSQL_8_0
}

variable "tier" {
  description = "Machine tier"
  type        = string
  default     = "db-custom-2-4096"  # 2 vCPU, 4GB RAM
}

variable "availability_type" {
  description = "HA type: ZONAL or REGIONAL"
  type        = string
  default     = "REGIONAL"
}

variable "read_replica_count" {
  description = "Number of read replicas"
  type        = number
  default     = 0
}
```

### Terraform Resources
```hcl
# VPC for private connectivity
resource "google_compute_network" "vpc" {
  name                    = "${var.instance_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.instance_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# Private IP allocation
resource "google_compute_global_address" "private_ip" {
  name          = "${var.instance_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

# Service networking connection
resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# Primary Cloud SQL Instance
resource "google_sql_database_instance" "primary" {
  name             = var.instance_name
  database_version = var.database_version
  region           = var.region

  deletion_protection = true

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_type         = "PD_SSD"
    disk_size         = 100
    disk_autoresize   = true

    # High availability configuration
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 30
        retention_unit   = "COUNT"
      }
    }

    # Private IP configuration
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
      require_ssl     = true

      authorized_networks {
        name  = "internal"
        value = "10.0.0.0/8"
      }
    }

    # Maintenance window
    maintenance_window {
      day          = 7  # Sunday
      hour         = 3  # 3 AM
      update_track = "stable"
    }

    # Database flags
    database_flags {
      name  = "max_connections"
      value = "200"
    }

    database_flags {
      name  = "log_min_duration_statement"
      value = "1000"  # Log queries > 1 second
    }

    # Insights
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
  }

  depends_on = [google_service_networking_connection.private_vpc]
}

# Read Replicas
resource "google_sql_database_instance" "replica" {
  count                = var.read_replica_count
  name                 = "${var.instance_name}-replica-${count.index + 1}"
  database_version     = var.database_version
  region               = var.region
  master_instance_name = google_sql_database_instance.primary.name

  replica_configuration {
    failover_target = false
  }

  settings {
    tier            = var.tier
    disk_type       = "PD_SSD"
    disk_autoresize = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
      require_ssl     = true
    }
  }

  depends_on = [google_sql_database_instance.primary]
}

# Database
resource "google_sql_database" "database" {
  name     = var.database_name
  instance = google_sql_database_instance.primary.name
}

# Database User
resource "google_sql_user" "user" {
  name     = var.database_user
  instance = google_sql_database_instance.primary.name
  password = random_password.db_password.result
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.instance_name}-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Outputs
output "connection_name" {
  value = google_sql_database_instance.primary.connection_name
}

output "private_ip" {
  value = google_sql_database_instance.primary.private_ip_address
}

output "replica_ips" {
  value = google_sql_database_instance.replica[*].private_ip_address
}
```

## Connection Patterns

### Application Connection
```python
# Python with SQLAlchemy
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Primary (read-write)
primary_url = f"postgresql://{user}:{password}@{primary_ip}:5432/{database}"
primary_engine = create_engine(
    primary_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# Read replica pool (read-only)
replica_urls = [
    f"postgresql://{user}:{password}@{ip}:5432/{database}"
    for ip in replica_ips
]
```

### Cloud SQL Proxy
```bash
# Download proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# Connect to primary
./cloud-sql-proxy --private-ip ${PROJECT}:${REGION}:${INSTANCE}

# Connect to replica
./cloud-sql-proxy --private-ip ${PROJECT}:${REGION}:${INSTANCE}-replica-1
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable sqladmin.googleapis.com servicenetworking.googleapis.com secretmanager.googleapis.com

# Create instance (CLI alternative)
gcloud sql instances create ${INSTANCE_NAME} \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-4096 \
  --region=${REGION} \
  --availability-type=REGIONAL \
  --storage-type=SSD \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --enable-point-in-time-recovery \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=3

# Create read replica
gcloud sql instances create ${INSTANCE_NAME}-replica-1 \
  --master-instance-name=${INSTANCE_NAME} \
  --region=${REGION}

# Create database
gcloud sql databases create ${DATABASE_NAME} --instance=${INSTANCE_NAME}

# Set password
gcloud sql users set-password postgres --instance=${INSTANCE_NAME} --prompt-for-password
```

## Best Practices

### High Availability
1. Use REGIONAL availability for production
2. Enable automatic failover
3. Configure maintenance windows during low traffic
4. Test failover regularly

### Performance
1. Right-size instance for workload
2. Use connection pooling (PgBouncer or app-level)
3. Enable Query Insights for optimization
4. Index based on query patterns

### Security
1. Use private IP only (no public IP)
2. Require SSL connections
3. Use IAM database authentication
4. Store credentials in Secret Manager

### Backup & Recovery
1. Enable point-in-time recovery
2. Keep 30+ days of backups
3. Test restore procedures
4. Consider cross-region backups

## Cost Breakdown

| Tier | vCPU | RAM | Monthly Cost |
|------|------|-----|--------------|
| db-f1-micro | shared | 0.6 GB | $10 |
| db-g1-small | shared | 1.7 GB | $30 |
| db-custom-1-3840 | 1 | 3.75 GB | $60 |
| db-custom-2-4096 | 2 | 4 GB | $100 |
| db-custom-4-8192 | 4 | 8 GB | $200 |
| db-custom-8-16384 | 8 | 16 GB | $400 |

### Additional Costs
| Component | Cost |
|-----------|------|
| HA (Regional) | +100% of instance cost |
| Read Replica | Same as primary tier |
| Storage (SSD) | $0.17/GB/month |
| Backups | $0.08/GB/month |

### Example: Production HA Setup
| Component | Cost |
|-----------|------|
| Primary (db-custom-2-4096, HA) | $200/month |
| 2x Read Replicas | $200/month |
| 100GB SSD Storage | $17/month |
| Backups (200GB) | $16/month |
| **Total** | **~$433/month** |

## Common Mistakes

1. **No HA for production**: Single zone = downtime during maintenance
2. **Public IP**: Security risk, use private IP
3. **No connection pooling**: Exhausting connections
4. **Over-provisioned**: Starting too large, scale up instead
5. **No monitoring**: Missing slow query alerts
6. **Skipping backups**: No PITR for data recovery

## Example Configuration

```yaml
project_name: production-api
provider: gcp
region: us-central1
architecture_type: cloud_sql_ha

resources:
  - id: vpc
    type: vpc_network
    name: db-vpc
    provider: gcp
    config:
      auto_create_subnetworks: false

  - id: primary-db
    type: cloud_sql
    name: production-db
    provider: gcp
    config:
      database_version: POSTGRES_15
      tier: db-custom-2-4096
      availability_type: REGIONAL
      disk_type: PD_SSD
      disk_size: 100
      backup_enabled: true
      pitr_enabled: true
      private_network: db-vpc
      require_ssl: true
      query_insights: true
    depends_on:
      - vpc

  - id: replica-1
    type: cloud_sql_replica
    name: production-db-replica-1
    provider: gcp
    config:
      master_instance: production-db
      tier: db-custom-2-4096
    depends_on:
      - primary-db

  - id: replica-2
    type: cloud_sql_replica
    name: production-db-replica-2
    provider: gcp
    config:
      master_instance: production-db
      tier: db-custom-2-4096
    depends_on:
      - primary-db
```

## Sources

- [Cloud SQL High Availability](https://cloud.google.com/sql/docs/postgres/high-availability)
- [Cloud SQL Best Practices](https://cloud.google.com/sql/docs/postgres/best-practices)
- [Cloud SQL Pricing](https://cloud.google.com/sql/pricing)
