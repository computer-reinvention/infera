# Terraform Module Patterns

## Overview

Terraform modules enable reusable, composable infrastructure as code. This guide covers battle-tested patterns for structuring Terraform projects, creating reusable modules, and managing state across environments.

### When to Use Modules
- Repeated infrastructure patterns across projects
- Multi-environment deployments (dev/staging/prod)
- Team standardization on cloud resources
- Encapsulating complex resource relationships
- Enforcing organizational policies

### When NOT to Use Modules
- One-off infrastructure
- Very simple deployments (overhead > benefit)
- Rapidly prototyping (modules slow iteration)

## Project Structure

### Standard Module Layout

```
terraform/
├── modules/                    # Reusable modules
│   ├── cloud-run/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── versions.tf
│   │   └── README.md
│   ├── cloud-sql/
│   │   └── ...
│   └── vpc/
│       └── ...
│
├── environments/               # Environment configurations
│   ├── dev/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   │   └── ...
│   └── production/
│       └── ...
│
├── shared/                     # Shared configuration
│   ├── providers.tf
│   └── versions.tf
│
└── README.md
```

### Module Structure

```hcl
# modules/cloud-run/main.tf
resource "google_cloud_run_v2_service" "default" {
  name     = var.service_name
  location = var.region

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      dynamic "env" {
        for_each = var.environment_variables
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_environment_variables
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }
    }

    vpc_access {
      connector = var.vpc_connector
      egress    = var.vpc_egress
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,  # Managed by CI/CD
    ]
  }
}

resource "google_cloud_run_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.default.location
  service  = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

```hcl
# modules/cloud-run/variables.tf
variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,48}[a-z0-9]$", var.service_name))
    error_message = "Service name must be lowercase, start with letter, max 50 chars."
  }
}

variable "region" {
  description = "GCP region for the service"
  type        = string
  default     = "us-central1"
}

variable "image" {
  description = "Container image to deploy"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu" {
  description = "CPU allocation"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocation"
  type        = string
  default     = "512Mi"
}

variable "environment_variables" {
  description = "Environment variables"
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "Secret environment variables from Secret Manager"
  type = map(object({
    secret  = string
    version = string
  }))
  default = {}
}

variable "vpc_connector" {
  description = "VPC connector for private networking"
  type        = string
  default     = null
}

variable "vpc_egress" {
  description = "VPC egress setting"
  type        = string
  default     = "PRIVATE_RANGES_ONLY"
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access"
  type        = bool
  default     = false
}
```

```hcl
# modules/cloud-run/outputs.tf
output "service_name" {
  description = "The name of the Cloud Run service"
  value       = google_cloud_run_v2_service.default.name
}

output "service_url" {
  description = "The URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.default.uri
}

output "service_id" {
  description = "The ID of the Cloud Run service"
  value       = google_cloud_run_v2_service.default.id
}

output "latest_revision" {
  description = "The latest revision of the service"
  value       = google_cloud_run_v2_service.default.latest_ready_revision
}
```

```hcl
# modules/cloud-run/versions.tf
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
  }
}
```

## Common Module Patterns

### Pattern 1: Cloud SQL Module

```hcl
# modules/cloud-sql/main.tf
resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  name                = var.instance_name
  database_version    = var.database_version
  region              = var.region
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    availability_type = var.high_availability ? "REGIONAL" : "ZONAL"
    disk_size         = var.disk_size
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = var.point_in_time_recovery
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = var.backup_retention_days
      }
    }

    ip_configuration {
      ipv4_enabled    = var.public_ip
      private_network = var.private_network
      require_ssl     = true
    }

    maintenance_window {
      day          = 7  # Sunday
      hour         = 3
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
      record_client_address   = true
    }

    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }

    database_flags {
      name  = "log_connections"
      value = "on"
    }

    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "default" {
  name     = var.database_name
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "default" {
  name     = var.database_user
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.instance_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}
```

### Pattern 2: VPC Module

```hcl
# modules/vpc/main.tf
resource "google_compute_network" "vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "private" {
  name                     = "${var.network_name}-private"
  ip_cidr_range            = var.private_subnet_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

# Cloud NAT for outbound internet
resource "google_compute_router" "router" {
  name    = "${var.network_name}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.network_name}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Serverless VPC connector
resource "google_vpc_access_connector" "connector" {
  count         = var.create_serverless_connector ? 1 : 0
  name          = "${var.network_name}-connector"
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.connector_cidr
  min_instances = 2
  max_instances = 10
}

# Private service connection (for Cloud SQL, etc.)
resource "google_compute_global_address" "private_ip" {
  name          = "${var.network_name}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}
```

### Pattern 3: GKE Cluster Module

```hcl
# modules/gke/main.tf
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.regional ? var.region : var.zone

  # Remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = var.network
  subnetwork = var.subnetwork

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_cidr
  }

  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.master_authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = var.release_channel
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
    network_policy_config {
      disabled = false
    }
  }

  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  maintenance_policy {
    recurring_window {
      start_time = "2024-01-01T03:00:00Z"
      end_time   = "2024-01-01T07:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SA,SU"
    }
  }
}

# Node pools
resource "google_container_node_pool" "primary" {
  name       = "primary"
  location   = var.regional ? var.region : var.zone
  cluster    = google_container_cluster.primary.name
  node_count = var.node_count

  autoscaling {
    min_node_count = var.min_nodes
    max_node_count = var.max_nodes
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.machine_type
    disk_size_gb = var.disk_size
    disk_type    = "pd-ssd"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = var.node_labels
    tags   = var.node_tags
  }
}
```

## Environment Configuration

### Using Workspaces

```hcl
# environments/main.tf
terraform {
  backend "gcs" {
    bucket = "my-terraform-state"
    prefix = "terraform/state"
  }
}

locals {
  environment = terraform.workspace

  config = {
    dev = {
      project_id    = "my-project-dev"
      region        = "us-central1"
      min_instances = 0
      max_instances = 5
    }
    staging = {
      project_id    = "my-project-staging"
      region        = "us-central1"
      min_instances = 1
      max_instances = 10
    }
    production = {
      project_id    = "my-project-prod"
      region        = "us-central1"
      min_instances = 2
      max_instances = 100
    }
  }

  env = local.config[local.environment]
}

module "api" {
  source = "../../modules/cloud-run"

  service_name  = "api"
  region        = local.env.region
  image         = var.api_image
  min_instances = local.env.min_instances
  max_instances = local.env.max_instances

  environment_variables = {
    ENVIRONMENT = local.environment
    LOG_LEVEL   = local.environment == "production" ? "info" : "debug"
  }
}
```

### Using Separate Directories (Recommended)

```hcl
# environments/production/main.tf
terraform {
  backend "gcs" {
    bucket = "my-project-prod-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = "my-project-prod"
  region  = "us-central1"
}

module "vpc" {
  source = "../../modules/vpc"

  network_name   = "production"
  region         = "us-central1"
  private_subnet_cidr = "10.0.0.0/20"
}

module "database" {
  source = "../../modules/cloud-sql"

  instance_name       = "production-db"
  database_version    = "POSTGRES_15"
  tier                = "db-custom-4-16384"
  high_availability   = true
  deletion_protection = true

  private_network = module.vpc.network_id
}

module "api" {
  source = "../../modules/cloud-run"

  service_name  = "api"
  region        = "us-central1"
  image         = "gcr.io/my-project-prod/api:latest"
  min_instances = 2
  max_instances = 100
  cpu           = "2"
  memory        = "1Gi"

  vpc_connector = module.vpc.serverless_connector_id

  secret_environment_variables = {
    DATABASE_URL = {
      secret  = module.database.password_secret_id
      version = "latest"
    }
  }

  allow_unauthenticated = true
}
```

```hcl
# environments/production/terraform.tfvars
# Production-specific values
api_image = "gcr.io/my-project-prod/api:v1.2.3"
```

## State Management

### Remote State with Locking

```hcl
# backend.tf
terraform {
  backend "gcs" {
    bucket = "my-terraform-state"
    prefix = "terraform/state/${path.module}"
  }
}

# Or for AWS
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

### Accessing Remote State

```hcl
# Access state from another module
data "terraform_remote_state" "vpc" {
  backend = "gcs"
  config = {
    bucket = "my-terraform-state"
    prefix = "terraform/state/vpc"
  }
}

module "api" {
  source = "../../modules/cloud-run"

  vpc_connector = data.terraform_remote_state.vpc.outputs.serverless_connector_id
}
```

## Testing Modules

```hcl
# modules/cloud-run/tests/main.tftest.hcl
variables {
  service_name = "test-service"
  region       = "us-central1"
  image        = "nginx:latest"
}

run "creates_cloud_run_service" {
  command = plan

  assert {
    condition     = google_cloud_run_v2_service.default.name == "test-service"
    error_message = "Service name does not match"
  }

  assert {
    condition     = google_cloud_run_v2_service.default.location == "us-central1"
    error_message = "Region does not match"
  }
}

run "validates_service_name" {
  command = plan

  variables {
    service_name = "INVALID_NAME"
  }

  expect_failures = [
    var.service_name,
  ]
}
```

```bash
# Run tests
terraform test
```

## Best Practices

### 1. Version Pinning

```hcl
# versions.tf
terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}
```

### 2. Naming Conventions

```hcl
# locals.tf
locals {
  # Consistent naming
  name_prefix = "${var.project}-${var.environment}"

  common_labels = {
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
    team        = var.team
  }
}

resource "google_cloud_run_v2_service" "api" {
  name = "${local.name_prefix}-api"

  template {
    labels = local.common_labels
  }
}
```

### 3. Sensitive Output Handling

```hcl
# outputs.tf
output "database_password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}

output "database_url" {
  description = "Database connection URL"
  value       = "postgresql://${var.database_user}:${random_password.db_password.result}@${google_sql_database_instance.main.private_ip_address}/${var.database_name}"
  sensitive   = true
}
```

### 4. Data Source Usage

```hcl
# Use data sources for existing resources
data "google_project" "current" {}

data "google_compute_network" "existing" {
  name = "existing-vpc"
}

resource "google_cloud_run_v2_service" "api" {
  project = data.google_project.current.project_id

  template {
    vpc_access {
      network_interfaces {
        network = data.google_compute_network.existing.id
      }
    }
  }
}
```

## Example Configuration

```yaml
# infera.yaml - Terraform module usage
name: my-app
provider: gcp

infrastructure:
  tool: terraform

  modules:
    - source: ./modules/vpc
      name: vpc
      variables:
        network_name: "${name}-network"
        region: us-central1

    - source: ./modules/cloud-sql
      name: database
      variables:
        instance_name: "${name}-db"
        tier: db-f1-micro

    - source: ./modules/cloud-run
      name: api
      variables:
        service_name: "${name}-api"
        min_instances: 0
        max_instances: 10

  state:
    backend: gcs
    bucket: "${project_id}-tfstate"
```

## Sources

- [Terraform Module Documentation](https://developer.hashicorp.com/terraform/language/modules)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [Google Cloud Terraform Modules](https://registry.terraform.io/namespaces/terraform-google-modules)
- [Terraform Testing](https://developer.hashicorp.com/terraform/language/tests)
- [Terraform State Management](https://developer.hashicorp.com/terraform/language/state)
