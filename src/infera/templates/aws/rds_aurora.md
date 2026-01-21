# AWS RDS Aurora Serverless

## Overview

Deploy auto-scaling PostgreSQL or MySQL databases using Aurora Serverless v2. This architecture provides automatic capacity scaling, high availability, and pay-per-use pricing without managing database instances.

## Detection Signals

Use this template when:
- Variable database workloads
- Unpredictable traffic patterns
- Development/staging environments
- Cost optimization needed
- Auto-scaling databases required
- High availability essential

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Application Layer                       │   │
                    │   │           (Lambda / ECS / EC2 / EKS)                     │   │
                    │   └─────────────────────────┬───────────────────────────────┘   │
                    │                             │                                   │
                    │                             ▼                                   │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Aurora Serverless v2                    │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Cluster Endpoint                      │  │   │
                    │   │  │         (Write + Read routing)                     │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                         │                               │   │
                    │   │            ┌────────────┼────────────┐                  │   │
                    │   │            │            │            │                  │   │
                    │   │            ▼            ▼            ▼                  │   │
                    │   │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │   │
                    │   │  │   Writer     │ │   Reader     │ │   Reader     │    │   │
                    │   │  │  Instance    │ │  Instance    │ │  Instance    │    │   │
                    │   │  │  (Primary)   │ │  (Replica)   │ │  (Replica)   │    │   │
                    │   │  │             │ │             │ │             │    │   │
                    │   │  │  AZ-a       │ │  AZ-b       │ │  AZ-c       │    │   │
                    │   │  └──────────────┘ └──────────────┘ └──────────────┘    │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │           Shared Storage (Auto-growing)            │  │   │
                    │   │  │             6-way replicated across AZs            │  │   │
                    │   │  │                  10GB - 128TB                      │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 0.5 - 128 ACUs • < 1 second scaling     │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
                    │   │  Secrets Mgr │  │  CloudWatch  │  │  RDS Proxy   │         │
                    │   │  (Credentials)│  │  (Metrics)   │  │  (optional)  │         │
                    │   └──────────────┘  └──────────────┘  └──────────────┘         │
                    │                                                                 │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Aurora Cluster | Database cluster | Serverless v2 |
| DB Instances | Compute | Writer + readers |
| Subnet Group | Networking | Private subnets |
| Security Group | Access control | Application SG |
| Secrets Manager | Credentials | Auto-rotation |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| RDS Proxy | Connection pooling | Lambda workloads |
| Read Replicas | Read scaling | Additional instances |
| Global Database | Multi-region | Cross-region replication |
| Performance Insights | Monitoring | Query analysis |

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

provider "aws" {
  region = var.region
}

variable "region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "aurora-db"
}

variable "engine" {
  default = "aurora-postgresql"  # or aurora-mysql
}

variable "engine_version" {
  default = "15.4"
}

variable "min_capacity" {
  default = 0.5  # Minimum ACUs
}

variable "max_capacity" {
  default = 16   # Maximum ACUs
}

# VPC (assuming exists or create)
data "aws_vpc" "main" {
  default = true
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
}

# Or create VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs              = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  database_subnets = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]

  create_database_subnet_group = true

  enable_nat_gateway = false  # Database doesn't need internet
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-subnet-group"
  subnet_ids = module.vpc.database_subnets

  tags = {
    Name = "${var.project_name}-subnet-group"
  }
}

# Security Group
resource "aws_security_group" "aurora" {
  name        = "${var.project_name}-aurora-sg"
  description = "Aurora database security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "PostgreSQL from VPC"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-aurora-sg"
  }
}

# Random password
resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Aurora Cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier = "${var.project_name}-cluster"

  engine         = var.engine
  engine_mode    = "provisioned"
  engine_version = var.engine_version

  database_name   = "app"
  master_username = "admin"
  master_password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  # Serverless v2 scaling configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  # Storage configuration
  storage_encrypted = true
  storage_type      = "aurora"  # or aurora-iopt1 for I/O optimized

  # Backup configuration
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  # Maintenance
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  apply_immediately            = false

  # Protection
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.project_name}-final-snapshot"

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]  # or ["audit", "error", "general", "slowquery"] for MySQL

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Environment = "production"
  }
}

# Writer Instance (Serverless v2)
resource "aws_rds_cluster_instance" "writer" {
  identifier          = "${var.project_name}-writer"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version
  publicly_accessible = false

  # Performance Insights
  performance_insights_enabled = true

  tags = {
    Name = "${var.project_name}-writer"
  }
}

# Reader Instance (Serverless v2) - Optional for read scaling
resource "aws_rds_cluster_instance" "reader" {
  count = 1  # Increase for more read capacity

  identifier          = "${var.project_name}-reader-${count.index}"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version
  publicly_accessible = false

  performance_insights_enabled = true

  tags = {
    Name = "${var.project_name}-reader-${count.index}"
  }
}

# Secrets Manager for credentials
resource "aws_secretsmanager_secret" "db" {
  name = "${var.project_name}/database"

  tags = {
    Name = "${var.project_name}-db-secret"
  }
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = aws_rds_cluster.main.master_username
    password = random_password.master.result
    host     = aws_rds_cluster.main.endpoint
    port     = aws_rds_cluster.main.port
    database = aws_rds_cluster.main.database_name
    engine   = var.engine
    url      = "postgresql://${aws_rds_cluster.main.master_username}:${random_password.master.result}@${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}/${aws_rds_cluster.main.database_name}"
  })
}

# Secret rotation (optional)
resource "aws_secretsmanager_secret_rotation" "db" {
  secret_id           = aws_secretsmanager_secret.db.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn

  rotation_rules {
    automatically_after_days = 30
  }
}

# RDS Proxy (optional - recommended for Lambda)
resource "aws_db_proxy" "main" {
  name                   = "${var.project_name}-proxy"
  debug_logging          = false
  engine_family          = "POSTGRESQL"  # or MYSQL
  idle_client_timeout    = 1800
  require_tls            = true
  role_arn               = aws_iam_role.proxy.arn
  vpc_security_group_ids = [aws_security_group.aurora.id]
  vpc_subnet_ids         = module.vpc.database_subnets

  auth {
    auth_scheme               = "SECRETS"
    iam_auth                  = "DISABLED"
    secret_arn                = aws_secretsmanager_secret.db.arn
  }

  tags = {
    Name = "${var.project_name}-proxy"
  }
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 100
    max_idle_connections_percent = 50
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name         = aws_db_proxy.main.name
  target_group_name     = aws_db_proxy_default_target_group.main.name
  db_cluster_identifier = aws_rds_cluster.main.id
}

# IAM Role for RDS Proxy
resource "aws_iam_role" "proxy" {
  name = "${var.project_name}-proxy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "rds.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "proxy" {
  name = "secrets-access"
  role = aws_iam_role.proxy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = aws_secretsmanager_secret.db.arn
    }]
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.project_name}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Database CPU utilization is high"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  alarm_actions = []  # Add SNS topic ARN
}

resource "aws_cloudwatch_metric_alarm" "connections" {
  alarm_name          = "${var.project_name}-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 100
  alarm_description   = "Database connection count is high"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  alarm_actions = []
}

output "cluster_endpoint" {
  description = "Writer endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "proxy_endpoint" {
  description = "RDS Proxy endpoint"
  value       = aws_db_proxy.main.endpoint
}

output "secret_arn" {
  description = "Secrets Manager ARN"
  value       = aws_secretsmanager_secret.db.arn
}

output "database_name" {
  value = aws_rds_cluster.main.database_name
}
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform plan
terraform apply

# Connect to database
# Get credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id aurora-db/database \
  --query SecretString --output text | jq

# Connect via psql
psql "postgresql://admin:PASSWORD@cluster-endpoint:5432/app"

# Run migrations
DATABASE_URL="postgresql://..." npx prisma migrate deploy

# Monitor ACU usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name ServerlessDatabaseCapacity \
  --dimensions Name=DBClusterIdentifier,Value=aurora-db-cluster \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average
```

## Best Practices

### Scaling
1. Set appropriate min/max ACU limits
2. Monitor ACU utilization
3. Use read replicas for read-heavy workloads
4. Consider I/O optimized storage for high throughput

### Connections
1. Use RDS Proxy for Lambda
2. Implement connection pooling
3. Monitor connection counts
4. Set appropriate timeouts

### Security
1. Enable encryption at rest
2. Use Secrets Manager for credentials
3. Enable IAM authentication
4. Use private subnets only
5. Rotate credentials regularly

## Cost Breakdown

| Component | Pricing |
|-----------|---------|
| Aurora Serverless v2 | $0.12/ACU-hour |
| Storage | $0.10/GB-month |
| I/O | $0.20/million requests |
| Backup | $0.021/GB-month |
| RDS Proxy | $0.015/vCPU-hour |

### Example Costs
| Workload | Avg ACUs | Storage | Monthly |
|----------|----------|---------|---------|
| Dev | 0.5 | 20GB | ~$50 |
| Small | 2 | 50GB | ~$150 |
| Medium | 8 | 200GB | ~$600 |
| Large | 32 | 1TB | ~$2,500 |

## Common Mistakes

1. **Min ACU too low**: Slow cold starts
2. **No read replicas**: Writer overloaded
3. **Public access**: Security vulnerability
4. **No proxy**: Lambda connection exhaustion
5. **Wrong engine version**: Missing features

## Example Configuration

```yaml
project_name: my-aurora-db
provider: aws
architecture_type: rds_aurora

resources:
  - id: aurora-cluster
    type: aws_rds_aurora
    name: my-db-cluster
    provider: aws
    config:
      engine: aurora-postgresql
      engine_version: "15.4"
      serverless_v2:
        min_capacity: 0.5
        max_capacity: 16
      instances:
        - type: writer
        - type: reader
      encryption: true
      backup_retention: 7

  - id: db-proxy
    type: aws_db_proxy
    name: my-db-proxy
    provider: aws
    config:
      engine_family: POSTGRESQL
      require_tls: true
```

## Sources

- [Aurora Serverless v2 Guide](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [RDS Proxy Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html)
- [Aurora Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.BestPractices.html)
