# AWS Multi-Region High Availability

## Overview

Deploy globally distributed applications with multi-region high availability using Route 53, Global Accelerator, and cross-region replication. This architecture provides disaster recovery, low latency for global users, and 99.99%+ availability.

## Detection Signals

Use this template when:
- Global user base
- High availability requirements (99.99%+)
- Disaster recovery needed
- Low latency globally
- Regulatory data residency
- Active-active or active-passive failover

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        Global Layer                              │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
    Internet ──────►│   │                   Route 53                               │   │
                    │   │          (Latency-based / Geolocation routing)           │   │
                    │   │                                                         │   │
                    │   │  ┌──────────────────────────────────────────────────┐   │   │
                    │   │  │              Global Accelerator                   │   │   │
                    │   │  │         (Anycast IPs, TCP/UDP optimization)       │   │   │
                    │   │  └──────────────────────────────────────────────────┘   │   │
                    │   └─────────────────────────┬───────────────────────────────┘   │
                    │                             │                                   │
                    │              ┌──────────────┴──────────────┐                   │
                    │              │                             │                   │
                    │              ▼                             ▼                   │
                    │   ┌──────────────────────┐    ┌──────────────────────┐        │
                    │   │    US-EAST-1         │    │    EU-WEST-1         │        │
                    │   │    (Primary)         │    │    (Secondary)       │        │
                    │   │                      │    │                      │        │
                    │   │  ┌────────────────┐  │    │  ┌────────────────┐  │        │
                    │   │  │     ALB        │  │    │  │     ALB        │  │        │
                    │   │  └───────┬────────┘  │    │  └───────┬────────┘  │        │
                    │   │          │           │    │          │           │        │
                    │   │  ┌───────┴────────┐  │    │  ┌───────┴────────┐  │        │
                    │   │  │  ECS/EKS/EC2   │  │    │  │  ECS/EKS/EC2   │  │        │
                    │   │  └───────┬────────┘  │    │  └───────┬────────┘  │        │
                    │   │          │           │    │          │           │        │
                    │   │  ┌───────┴────────┐  │    │  ┌───────┴────────┐  │        │
                    │   │  │  Aurora Global │◄─┼────┼──│  Aurora Global │  │        │
                    │   │  │   (Writer)     │  │    │  │   (Reader)     │  │        │
                    │   │  └────────────────┘  │    │  └────────────────┘  │        │
                    │   │                      │    │                      │        │
                    │   │  ┌────────────────┐  │    │  ┌────────────────┐  │        │
                    │   │  │  S3 (Primary)  │◄─┼────┼──│  S3 (Replica)  │  │        │
                    │   │  └────────────────┘  │    │  └────────────────┘  │        │
                    │   └──────────────────────┘    └──────────────────────┘        │
                    │                                                                 │
                    │   RPO: ~1 second • RTO: ~1 minute • Global latency < 100ms     │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Route 53 | DNS routing | Health checks, failover |
| Global Accelerator | Traffic routing | Anycast IPs |
| ALB (per region) | Load balancing | Health checks |
| Compute (per region) | Application | ECS/EKS/EC2 |
| Aurora Global | Database | Cross-region replication |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| S3 Replication | Object storage | Cross-region |
| ElastiCache Global | Session/cache | Multi-region |
| DynamoDB Global | NoSQL | Global tables |
| CloudFront | CDN | Global edge |

## Configuration

### Terraform
```hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Primary region
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

# Secondary region
provider "aws" {
  alias  = "secondary"
  region = "eu-west-1"
}

variable "project_name" {
  default = "multi-region-app"
}

variable "domain_name" {
  default = "app.example.com"
}

locals {
  primary_region   = "us-east-1"
  secondary_region = "eu-west-1"
}

# =====================================
# GLOBAL RESOURCES
# =====================================

# Route 53 Hosted Zone
resource "aws_route53_zone" "main" {
  provider = aws.primary
  name     = var.domain_name
}

# Health Checks
resource "aws_route53_health_check" "primary" {
  provider          = aws.primary
  fqdn              = module.primary.alb_dns
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10

  tags = {
    Name = "${var.project_name}-primary-health"
  }
}

resource "aws_route53_health_check" "secondary" {
  provider          = aws.primary
  fqdn              = module.secondary.alb_dns
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10

  tags = {
    Name = "${var.project_name}-secondary-health"
  }
}

# Route 53 Records - Latency-based routing
resource "aws_route53_record" "primary" {
  provider = aws.primary
  zone_id  = aws_route53_zone.main.zone_id
  name     = var.domain_name
  type     = "A"

  set_identifier = "primary"
  latency_routing_policy {
    region = local.primary_region
  }

  alias {
    name                   = module.primary.alb_dns
    zone_id                = module.primary.alb_zone_id
    evaluate_target_health = true
  }

  health_check_id = aws_route53_health_check.primary.id
}

resource "aws_route53_record" "secondary" {
  provider = aws.primary
  zone_id  = aws_route53_zone.main.zone_id
  name     = var.domain_name
  type     = "A"

  set_identifier = "secondary"
  latency_routing_policy {
    region = local.secondary_region
  }

  alias {
    name                   = module.secondary.alb_dns
    zone_id                = module.secondary.alb_zone_id
    evaluate_target_health = true
  }

  health_check_id = aws_route53_health_check.secondary.id
}

# Global Accelerator
resource "aws_globalaccelerator_accelerator" "main" {
  provider        = aws.primary
  name            = var.project_name
  ip_address_type = "IPV4"
  enabled         = true

  attributes {
    flow_logs_enabled   = true
    flow_logs_s3_bucket = aws_s3_bucket.logs.bucket
    flow_logs_s3_prefix = "globalaccelerator/"
  }
}

resource "aws_globalaccelerator_listener" "main" {
  provider        = aws.primary
  accelerator_arn = aws_globalaccelerator_accelerator.main.id
  protocol        = "TCP"
  client_affinity = "SOURCE_IP"

  port_range {
    from_port = 443
    to_port   = 443
  }
}

resource "aws_globalaccelerator_endpoint_group" "primary" {
  provider                  = aws.primary
  listener_arn              = aws_globalaccelerator_listener.main.id
  endpoint_group_region     = local.primary_region
  traffic_dial_percentage   = 100
  health_check_port         = 443
  health_check_protocol     = "HTTPS"
  health_check_path         = "/health"
  health_check_interval_seconds = 10
  threshold_count           = 3

  endpoint_configuration {
    endpoint_id = module.primary.alb_arn
    weight      = 100
  }
}

resource "aws_globalaccelerator_endpoint_group" "secondary" {
  provider                  = aws.primary
  listener_arn              = aws_globalaccelerator_listener.main.id
  endpoint_group_region     = local.secondary_region
  traffic_dial_percentage   = 100
  health_check_port         = 443
  health_check_protocol     = "HTTPS"
  health_check_path         = "/health"

  endpoint_configuration {
    endpoint_id = module.secondary.alb_arn
    weight      = 100
  }
}

# =====================================
# AURORA GLOBAL DATABASE
# =====================================

resource "aws_rds_global_cluster" "main" {
  provider                  = aws.primary
  global_cluster_identifier = "${var.project_name}-global"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "app"
  storage_encrypted         = true
}

# Primary Aurora Cluster
resource "aws_rds_cluster" "primary" {
  provider                  = aws.primary
  cluster_identifier        = "${var.project_name}-primary"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  master_username           = "admin"
  master_password           = random_password.db.result
  db_subnet_group_name      = module.primary.db_subnet_group
  vpc_security_group_ids    = [module.primary.db_security_group_id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 16
  }

  skip_final_snapshot = true
}

resource "aws_rds_cluster_instance" "primary" {
  provider           = aws.primary
  count              = 2
  identifier         = "${var.project_name}-primary-${count.index}"
  cluster_identifier = aws_rds_cluster.primary.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.primary.engine
  engine_version     = aws_rds_cluster.primary.engine_version
}

# Secondary Aurora Cluster
resource "aws_rds_cluster" "secondary" {
  provider                  = aws.secondary
  cluster_identifier        = "${var.project_name}-secondary"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  global_cluster_identifier = aws_rds_global_cluster.main.id
  db_subnet_group_name      = module.secondary.db_subnet_group
  vpc_security_group_ids    = [module.secondary.db_security_group_id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 16
  }

  skip_final_snapshot = true

  depends_on = [aws_rds_cluster_instance.primary]
}

resource "aws_rds_cluster_instance" "secondary" {
  provider           = aws.secondary
  count              = 2
  identifier         = "${var.project_name}-secondary-${count.index}"
  cluster_identifier = aws_rds_cluster.secondary.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.secondary.engine
  engine_version     = aws_rds_cluster.secondary.engine_version
}

resource "random_password" "db" {
  length  = 32
  special = false
}

# =====================================
# S3 CROSS-REGION REPLICATION
# =====================================

resource "aws_s3_bucket" "primary" {
  provider = aws.primary
  bucket   = "${var.project_name}-primary-${random_id.bucket.hex}"
}

resource "aws_s3_bucket" "secondary" {
  provider = aws.secondary
  bucket   = "${var.project_name}-secondary-${random_id.bucket.hex}"
}

resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "primary" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "secondary" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.secondary.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_replication_configuration" "primary" {
  provider   = aws.primary
  depends_on = [aws_s3_bucket_versioning.primary, aws_s3_bucket_versioning.secondary]

  role   = aws_iam_role.s3_replication.arn
  bucket = aws_s3_bucket.primary.id

  rule {
    id     = "replicate-all"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.secondary.arn
      storage_class = "STANDARD"
    }
  }
}

resource "aws_iam_role" "s3_replication" {
  provider = aws.primary
  name     = "${var.project_name}-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "s3_replication" {
  provider = aws.primary
  name     = "s3-replication"
  role     = aws_iam_role.s3_replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.primary.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Resource = "${aws_s3_bucket.primary.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Resource = "${aws_s3_bucket.secondary.arn}/*"
      }
    ]
  })
}

# =====================================
# REGIONAL MODULES
# =====================================

module "primary" {
  source = "./modules/region"
  providers = {
    aws = aws.primary
  }

  project_name = var.project_name
  region       = local.primary_region
  environment  = "primary"
  is_primary   = true

  db_endpoint = aws_rds_cluster.primary.endpoint
  s3_bucket   = aws_s3_bucket.primary.bucket
}

module "secondary" {
  source = "./modules/region"
  providers = {
    aws = aws.secondary
  }

  project_name = var.project_name
  region       = local.secondary_region
  environment  = "secondary"
  is_primary   = false

  db_endpoint = aws_rds_cluster.secondary.reader_endpoint
  s3_bucket   = aws_s3_bucket.secondary.bucket
}

# Logs bucket
resource "aws_s3_bucket" "logs" {
  provider = aws.primary
  bucket   = "${var.project_name}-logs-${random_id.bucket.hex}"
}

output "global_accelerator_dns" {
  value = aws_globalaccelerator_accelerator.main.dns_name
}

output "global_accelerator_ips" {
  value = aws_globalaccelerator_accelerator.main.ip_sets[0].ip_addresses
}

output "route53_nameservers" {
  value = aws_route53_zone.main.name_servers
}

output "primary_alb" {
  value = module.primary.alb_dns
}

output "secondary_alb" {
  value = module.secondary.alb_dns
}
```

### Regional Module
```hcl
# modules/region/main.tf
variable "project_name" {}
variable "region" {}
variable "environment" {}
variable "is_primary" {}
variable "db_endpoint" {}
variable "s3_bucket" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-${var.environment}-vpc"
  cidr = var.is_primary ? "10.0.0.0/16" : "10.1.0.0/16"

  azs              = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets  = var.is_primary ? ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"] : ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
  public_subnets   = var.is_primary ? ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"] : ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]
  database_subnets = var.is_primary ? ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"] : ["10.1.201.0/24", "10.1.202.0/24", "10.1.203.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  create_database_subnet_group = true
}

# ALB
resource "aws_lb" "main" {
  name               = "${var.project_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "main" {
  name        = "${var.project_name}-${var.environment}-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10
    matcher             = "200"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Service (simplified)
resource "aws_ecs_service" "main" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = var.project_name
    container_port   = 8080
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

resource "aws_ecs_task_definition" "main" {
  family                   = "${var.project_name}-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = var.project_name
    image = "nginx:latest"  # Replace with your image
    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]
    environment = [
      { name = "DATABASE_URL", value = "postgresql://admin@${var.db_endpoint}:5432/app" },
      { name = "S3_BUCKET", value = var.s3_bucket },
      { name = "REGION", value = var.region },
      { name = "IS_PRIMARY", value = tostring(var.is_primary) }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${var.project_name}-${var.environment}"
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# Security Groups, IAM, ACM...
# (abbreviated for brevity)

output "alb_dns" {
  value = aws_lb.main.dns_name
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "alb_zone_id" {
  value = aws_lb.main.zone_id
}

output "db_subnet_group" {
  value = module.vpc.database_subnet_group_name
}

output "db_security_group_id" {
  value = aws_security_group.db.id
}
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Test failover
# Simulate primary region failure
aws route53 update-health-check \
  --health-check-id HC123 \
  --disabled

# Promote secondary Aurora to primary (disaster recovery)
aws rds failover-global-cluster \
  --global-cluster-identifier multi-region-app-global \
  --target-db-cluster-identifier multi-region-app-secondary

# Check Global Accelerator health
aws globalaccelerator describe-endpoint-group \
  --endpoint-group-arn arn:aws:globalaccelerator::xxx:accelerator/xxx/listener/xxx/endpoint-group/xxx
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| Global Accelerator | ~$50 |
| Route 53 (health checks) | ~$2 |
| Aurora Global (2 regions) | ~$200 |
| ECS Fargate (2 regions) | ~$150 |
| ALB (2 regions) | ~$40 |
| NAT Gateway (6 AZs) | ~$200 |
| S3 Replication | ~$10 |
| **Total** | **~$652** |

## Best Practices

1. **Use health checks at every layer**
2. **Keep RPO/RTO requirements clear**
3. **Test failover regularly**
4. **Monitor replication lag**
5. **Use infrastructure as code**

## Common Mistakes

1. **No health checks**: Routing to unhealthy endpoints
2. **Asymmetric capacity**: Secondary can't handle full load
3. **No failover testing**: Untested disaster recovery
4. **High replication lag**: Data loss during failover
5. **Missing cross-region permissions**: IAM misconfiguration

## Sources

- [Route 53 Health Checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover.html)
- [Global Accelerator](https://docs.aws.amazon.com/global-accelerator/latest/dg/)
- [Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html)
