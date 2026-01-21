# AWS Elastic Beanstalk

## Overview

Deploy web applications using AWS Elastic Beanstalk, a fully managed PaaS that handles infrastructure provisioning, load balancing, scaling, and monitoring. Ideal for developers who want to focus on code without managing infrastructure.

## Detection Signals

Use this template when:
- Quick deployment needed
- Minimal DevOps expertise
- Standard web application stack
- Auto-scaling required
- Managed updates desired
- Multiple environment support (dev/staging/prod)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Elastic Beanstalk Environment               │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Application Load Balancer             │  │   │
                    │   │  │              (Auto-provisioned)                    │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                         │                               │   │
                    │   │                         ▼                               │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Auto Scaling Group                    │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐       │  │   │
                    │   │  │  │   EC2     │ │   EC2     │ │   EC2     │       │  │   │
                    │   │  │  │ Instance  │ │ Instance  │ │ Instance  │       │  │   │
                    │   │  │  │           │ │           │ │           │       │  │   │
                    │   │  │  │  ┌─────┐  │ │  ┌─────┐  │ │  ┌─────┐  │       │  │   │
                    │   │  │  │  │ App │  │ │  │ App │  │ │  │ App │  │       │  │   │
                    │   │  │  │  └─────┘  │ │  └─────┘  │ │  └─────┘  │       │  │   │
                    │   │  │  └───────────┘ └───────────┘ └───────────┘       │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  Min: 2 • Max: 10 • Auto-scales on CPU/requests  │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                         │                               │   │
                    │   │                         ▼                               │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                  RDS Database                      │  │   │
                    │   │  │               (Auto-provisioned)                   │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Managed platform • Rolling updates • Built-in monitoring      │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| EB Application | Application container | Name, description |
| EB Environment | Running instance | Platform, scaling |
| S3 Bucket | Application versions | Auto-created |
| IAM Roles | Permissions | Instance profile |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| RDS | Database | EB-managed or external |
| ElastiCache | Session/caching | Redis/Memcached |
| S3 | File storage | Bucket |
| CloudFront | CDN | Distribution |
| Route 53 | Custom domain | Alias record |

## Supported Platforms

| Platform | Languages/Runtimes |
|----------|-------------------|
| Node.js | 18, 20 |
| Python | 3.9, 3.10, 3.11 |
| Ruby | 3.1, 3.2 |
| Java | 8, 11, 17 (Corretto) |
| Go | 1.20, 1.21 |
| PHP | 8.1, 8.2 |
| .NET | 6, 7 |
| Docker | Custom images |
| Multi-container | Docker Compose |

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
  default = "my-app"
}

variable "platform" {
  default = "64bit Amazon Linux 2023 v6.0.0 running Node.js 20"
}

# Elastic Beanstalk Application
resource "aws_elastic_beanstalk_application" "main" {
  name        = var.project_name
  description = "My web application"

  appversion_lifecycle {
    service_role          = aws_iam_role.beanstalk_service.arn
    max_count             = 10
    delete_source_from_s3 = true
  }
}

# Elastic Beanstalk Environment
resource "aws_elastic_beanstalk_environment" "main" {
  name                = "${var.project_name}-prod"
  application         = aws_elastic_beanstalk_application.main.name
  solution_stack_name = var.platform
  tier                = "WebServer"

  # Instance settings
  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "InstanceType"
    value     = "t3.small"
  }

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = aws_iam_instance_profile.beanstalk_ec2.name
  }

  # Auto Scaling
  setting {
    namespace = "aws:autoscaling:asg"
    name      = "MinSize"
    value     = "2"
  }

  setting {
    namespace = "aws:autoscaling:asg"
    name      = "MaxSize"
    value     = "10"
  }

  # Scaling triggers
  setting {
    namespace = "aws:autoscaling:trigger"
    name      = "MeasureName"
    value     = "CPUUtilization"
  }

  setting {
    namespace = "aws:autoscaling:trigger"
    name      = "Unit"
    value     = "Percent"
  }

  setting {
    namespace = "aws:autoscaling:trigger"
    name      = "UpperThreshold"
    value     = "70"
  }

  setting {
    namespace = "aws:autoscaling:trigger"
    name      = "LowerThreshold"
    value     = "30"
  }

  # Load Balancer
  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "EnvironmentType"
    value     = "LoadBalanced"
  }

  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "LoadBalancerType"
    value     = "application"
  }

  setting {
    namespace = "aws:elbv2:listener:443"
    name      = "Protocol"
    value     = "HTTPS"
  }

  setting {
    namespace = "aws:elbv2:listener:443"
    name      = "SSLCertificateArns"
    value     = aws_acm_certificate.main.arn
  }

  # VPC settings
  setting {
    namespace = "aws:ec2:vpc"
    name      = "VPCId"
    value     = module.vpc.vpc_id
  }

  setting {
    namespace = "aws:ec2:vpc"
    name      = "Subnets"
    value     = join(",", module.vpc.private_subnets)
  }

  setting {
    namespace = "aws:ec2:vpc"
    name      = "ELBSubnets"
    value     = join(",", module.vpc.public_subnets)
  }

  # Health check
  setting {
    namespace = "aws:elasticbeanstalk:environment:process:default"
    name      = "HealthCheckPath"
    value     = "/health"
  }

  # Rolling updates
  setting {
    namespace = "aws:elasticbeanstalk:command"
    name      = "DeploymentPolicy"
    value     = "RollingWithAdditionalBatch"
  }

  setting {
    namespace = "aws:elasticbeanstalk:command"
    name      = "BatchSizeType"
    value     = "Percentage"
  }

  setting {
    namespace = "aws:elasticbeanstalk:command"
    name      = "BatchSize"
    value     = "30"
  }

  # Enhanced health reporting
  setting {
    namespace = "aws:elasticbeanstalk:healthreporting:system"
    name      = "SystemType"
    value     = "enhanced"
  }

  # CloudWatch logs
  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs"
    name      = "StreamLogs"
    value     = "true"
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs"
    name      = "RetentionInDays"
    value     = "14"
  }

  # Environment variables
  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "NODE_ENV"
    value     = "production"
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "DATABASE_URL"
    value     = "postgresql://${aws_rds_cluster.main.master_username}:${random_password.db.result}@${aws_rds_cluster.main.endpoint}:5432/app"
  }

  tags = {
    Environment = "production"
  }
}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs              = ["${var.region}a", "${var.region}b"]
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24"]
  database_subnets = ["10.0.201.0/24", "10.0.202.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = true
  create_database_subnet_group = true
}

# RDS (External - recommended for production)
resource "aws_rds_cluster" "main" {
  cluster_identifier     = "${var.project_name}-db"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.4"
  database_name          = "app"
  master_username        = "admin"
  master_password        = random_password.db.result
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 4.0
  }

  skip_final_snapshot = true
}

resource "aws_rds_cluster_instance" "main" {
  identifier          = "${var.project_name}-db-instance"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version
}

resource "random_password" "db" {
  length  = 32
  special = false
}

# Security Groups
resource "aws_security_group" "db" {
  name        = "${var.project_name}-db-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
}

# IAM Roles
resource "aws_iam_role" "beanstalk_service" {
  name = "${var.project_name}-beanstalk-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "elasticbeanstalk.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "beanstalk_service" {
  role       = aws_iam_role.beanstalk_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth"
}

resource "aws_iam_role_policy_attachment" "beanstalk_service_managed" {
  role       = aws_iam_role.beanstalk_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkService"
}

resource "aws_iam_role" "beanstalk_ec2" {
  name = "${var.project_name}-beanstalk-ec2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "beanstalk_ec2_web" {
  role       = aws_iam_role.beanstalk_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier"
}

resource "aws_iam_role_policy_attachment" "beanstalk_ec2_worker" {
  role       = aws_iam_role.beanstalk_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier"
}

resource "aws_iam_instance_profile" "beanstalk_ec2" {
  name = "${var.project_name}-beanstalk-ec2"
  role = aws_iam_role.beanstalk_ec2.name
}

# ACM Certificate
resource "aws_acm_certificate" "main" {
  domain_name       = "app.example.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

output "environment_url" {
  value = aws_elastic_beanstalk_environment.main.endpoint_url
}

output "cname" {
  value = aws_elastic_beanstalk_environment.main.cname
}
```

### Application Configuration (.ebextensions)
```yaml
# .ebextensions/01_packages.config
packages:
  yum:
    git: []

# .ebextensions/02_nodecommand.config
option_settings:
  aws:elasticbeanstalk:container:nodejs:
    NodeCommand: "npm start"
    ProxyServer: nginx

# .ebextensions/03_environment.config
option_settings:
  aws:elasticbeanstalk:application:environment:
    NODE_OPTIONS: "--max-old-space-size=512"

# .ebextensions/04_autoscaling.config
option_settings:
  aws:autoscaling:asg:
    MinSize: 2
    MaxSize: 10
  aws:autoscaling:trigger:
    MeasureName: CPUUtilization
    Unit: Percent
    UpperThreshold: 70
    LowerThreshold: 30
```

### Platform Hooks
```bash
# .platform/hooks/predeploy/01_install.sh
#!/bin/bash
npm ci --production
npm run build
```

## Deployment Commands

```bash
# Install EB CLI
pip install awsebcli

# Initialize application
eb init -p node.js my-app --region us-east-1

# Create environment
eb create my-app-prod --instance-type t3.small --scale 2

# Deploy
eb deploy

# Open in browser
eb open

# View logs
eb logs

# SSH to instance
eb ssh

# View status
eb status

# Scale
eb scale 5

# Terminate
eb terminate my-app-prod
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| EC2 (2x t3.small) | ~$30 |
| ALB | ~$20 |
| RDS Aurora | ~$50 |
| NAT Gateway | ~$35 |
| **Total** | **~$135** |

## Best Practices

1. **Use external RDS** - Don't use EB-managed database for production
2. **Enable enhanced health** - Better monitoring
3. **Use rolling updates** - Zero-downtime deployments
4. **Configure proper health checks** - Accurate health status
5. **Use .ebextensions** - Infrastructure as code

## Common Mistakes

1. **EB-managed database**: Data loss on environment termination
2. **No health check path**: Instances marked unhealthy
3. **Wrong deployment policy**: Downtime during updates
4. **Missing IAM permissions**: Deployment failures
5. **Single instance environment**: No high availability

## Sources

- [Elastic Beanstalk Documentation](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/)
- [EB CLI Reference](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3.html)
- [Platform Versions](https://docs.aws.amazon.com/elasticbeanstalk/latest/platforms/platforms-supported.html)
