# AWS Batch Processing

## Overview

Run large-scale batch computing workloads using AWS Batch with automatic resource provisioning. This architecture handles job queuing, scheduling, and execution without managing infrastructure. Ideal for data processing, scientific computing, and batch transformations.

## Detection Signals

Use this template when:
- Large-scale batch processing
- Compute-intensive workloads
- Variable batch sizes
- Cost optimization needed (Spot)
- Data transformations
- Scientific/HPC computing

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    Job Submission                        │   │
                    │   │                                                         │   │
                    │   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
                    │   │  │ Lambda  │ │  CLI    │ │  API    │ │EventBrg │       │   │
                    │   │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │   │
                    │   └───────┼───────────┼──────────┼───────────┼────────────┘   │
                    │           │           │          │           │                 │
                    │           └───────────┴──────────┴───────────┘                 │
                    │                              │                                  │
                    │                              ▼                                  │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                     AWS Batch                            │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                  Job Queue                         │  │   │
                    │   │  │   ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐         │  │   │
                    │   │  │   │Job 1│ │Job 2│ │Job 3│ │Job 4│ │Job 5│ ────►   │  │   │
                    │   │  │   └─────┘ └─────┘ └─────┘ └─────┘ └─────┘         │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                         │                               │   │
                    │   │                         ▼                               │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Compute Environment                   │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌─────────────────────────────────────────────┐  │  │   │
                    │   │  │  │           EC2 / Fargate / Spot              │  │  │   │
                    │   │  │  │                                             │  │  │   │
                    │   │  │  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐   │  │  │   │
                    │   │  │  │  │ Job 1 │ │ Job 2 │ │ Job 3 │ │ Job 4 │   │  │  │   │
                    │   │  │  │  │Container│ │Container│ │Container│ │Container│   │  │  │   │
                    │   │  │  │  └───────┘ └───────┘ └───────┘ └───────┘   │  │  │   │
                    │   │  │  │                                             │  │  │   │
                    │   │  │  │  Auto-scales 0 → hundreds of instances     │  │  │   │
                    │   │  │  └─────────────────────────────────────────────┘  │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                         │                                       │
                    │                         ▼                                       │
                    │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
                    │   │     S3       │  │  DynamoDB    │  │  CloudWatch  │         │
                    │   │  (Input/Out) │  │  (Status)    │  │   (Logs)     │         │
                    │   └──────────────┘  └──────────────┘  └──────────────┘         │
                    │                                                                 │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Job Definition | Container config | Image, resources |
| Job Queue | Job scheduling | Priority |
| Compute Environment | Resources | EC2/Fargate/Spot |
| IAM Roles | Permissions | Batch execution |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| S3 | Input/output data | Buckets |
| DynamoDB | Job tracking | Table |
| Step Functions | Orchestration | State machine |
| EventBridge | Scheduling | Rules |

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
  default = "batch-processor"
}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

# Security Group
resource "aws_security_group" "batch" {
  name        = "${var.project_name}-batch-sg"
  description = "Security group for Batch compute environment"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECR Repository
resource "aws_ecr_repository" "batch" {
  name                 = "${var.project_name}-job"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# S3 Buckets
resource "aws_s3_bucket" "input" {
  bucket = "${var.project_name}-input-${random_id.bucket.hex}"
}

resource "aws_s3_bucket" "output" {
  bucket = "${var.project_name}-output-${random_id.bucket.hex}"
}

resource "random_id" "bucket" {
  byte_length = 4
}

# Compute Environment - Spot (cost-optimized)
resource "aws_batch_compute_environment" "spot" {
  compute_environment_name = "${var.project_name}-spot"
  type                     = "MANAGED"

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_PRICE_CAPACITY_OPTIMIZED"
    bid_percentage      = 100

    min_vcpus     = 0
    max_vcpus     = 256
    desired_vcpus = 0

    instance_type = [
      "c5.large",
      "c5.xlarge",
      "c5.2xlarge",
      "m5.large",
      "m5.xlarge",
      "m5.2xlarge",
      "r5.large",
      "r5.xlarge"
    ]

    subnets            = module.vpc.private_subnets
    security_group_ids = [aws_security_group.batch.id]

    instance_role = aws_iam_instance_profile.batch.arn
    spot_iam_fleet_role = aws_iam_role.spot_fleet.arn

    tags = {
      Name = "${var.project_name}-spot"
    }
  }

  service_role = aws_iam_role.batch_service.arn

  lifecycle {
    create_before_destroy = true
  }
}

# Compute Environment - On-Demand (reliable)
resource "aws_batch_compute_environment" "on_demand" {
  compute_environment_name = "${var.project_name}-on-demand"
  type                     = "MANAGED"

  compute_resources {
    type = "EC2"

    min_vcpus     = 0
    max_vcpus     = 64
    desired_vcpus = 0

    instance_type = [
      "c5.large",
      "c5.xlarge",
      "m5.large"
    ]

    subnets            = module.vpc.private_subnets
    security_group_ids = [aws_security_group.batch.id]

    instance_role = aws_iam_instance_profile.batch.arn
  }

  service_role = aws_iam_role.batch_service.arn

  lifecycle {
    create_before_destroy = true
  }
}

# Compute Environment - Fargate (serverless)
resource "aws_batch_compute_environment" "fargate" {
  compute_environment_name = "${var.project_name}-fargate"
  type                     = "MANAGED"

  compute_resources {
    type      = "FARGATE_SPOT"
    max_vcpus = 64

    subnets            = module.vpc.private_subnets
    security_group_ids = [aws_security_group.batch.id]
  }

  service_role = aws_iam_role.batch_service.arn

  lifecycle {
    create_before_destroy = true
  }
}

# Job Queue - High Priority
resource "aws_batch_job_queue" "high_priority" {
  name     = "${var.project_name}-high-priority"
  state    = "ENABLED"
  priority = 10

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.on_demand.arn
  }

  compute_environment_order {
    order               = 2
    compute_environment = aws_batch_compute_environment.spot.arn
  }
}

# Job Queue - Low Priority (Spot only)
resource "aws_batch_job_queue" "low_priority" {
  name     = "${var.project_name}-low-priority"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.spot.arn
  }
}

# Job Queue - Fargate
resource "aws_batch_job_queue" "fargate" {
  name     = "${var.project_name}-fargate"
  state    = "ENABLED"
  priority = 5

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.fargate.arn
  }
}

# Job Definition - EC2
resource "aws_batch_job_definition" "main" {
  name = "${var.project_name}-job"
  type = "container"

  platform_capabilities = ["EC2"]

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch.repository_url}:latest"

    resourceRequirements = [
      { type = "VCPU", value = "2" },
      { type = "MEMORY", value = "4096" }
    ]

    jobRoleArn       = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_execution.arn

    environment = [
      { name = "INPUT_BUCKET", value = aws_s3_bucket.input.bucket },
      { name = "OUTPUT_BUCKET", value = aws_s3_bucket.output.bucket },
      { name = "AWS_REGION", value = var.region }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "batch"
      }
    }

    mountPoints = [{
      containerPath = "/data"
      sourceVolume  = "data"
      readOnly      = false
    }]

    volumes = [{
      name = "data"
      host = {
        sourcePath = "/tmp/data"
      }
    }]
  })

  retry_strategy {
    attempts = 3
    evaluate_on_exit {
      on_status_reason = "Host EC2*"
      action           = "RETRY"
    }
    evaluate_on_exit {
      on_reason = "*"
      action    = "EXIT"
    }
  }

  timeout {
    attempt_duration_seconds = 3600
  }
}

# Job Definition - Fargate
resource "aws_batch_job_definition" "fargate" {
  name = "${var.project_name}-fargate-job"
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch.repository_url}:latest"

    resourceRequirements = [
      { type = "VCPU", value = "1" },
      { type = "MEMORY", value = "2048" }
    ]

    jobRoleArn       = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_execution.arn

    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }

    networkConfiguration = {
      assignPublicIp = "DISABLED"
    }

    environment = [
      { name = "INPUT_BUCKET", value = aws_s3_bucket.input.bucket },
      { name = "OUTPUT_BUCKET", value = aws_s3_bucket.output.bucket }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "fargate"
      }
    }
  })

  retry_strategy {
    attempts = 2
  }

  timeout {
    attempt_duration_seconds = 1800
  }
}

# Array Job Definition (for parallel processing)
resource "aws_batch_job_definition" "array" {
  name = "${var.project_name}-array-job"
  type = "container"

  platform_capabilities = ["EC2"]

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch.repository_url}:latest"

    resourceRequirements = [
      { type = "VCPU", value = "1" },
      { type = "MEMORY", value = "2048" }
    ]

    jobRoleArn       = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_execution.arn

    environment = [
      { name = "INPUT_BUCKET", value = aws_s3_bucket.input.bucket },
      { name = "OUTPUT_BUCKET", value = aws_s3_bucket.output.bucket }
    ]

    command = [
      "/bin/bash", "-c",
      "echo Processing array index $AWS_BATCH_JOB_ARRAY_INDEX && python process.py --index $AWS_BATCH_JOB_ARRAY_INDEX"
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "array"
      }
    }
  })
}

# IAM Roles
resource "aws_iam_role" "batch_service" {
  name = "${var.project_name}-batch-service"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "batch.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role" "batch_execution" {
  name = "${var.project_name}-batch-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_execution" {
  role       = aws_iam_role.batch_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "batch_job" {
  name = "${var.project_name}-batch-job"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "batch_job" {
  name = "s3-access"
  role = aws_iam_role.batch_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.input.arn,
        "${aws_s3_bucket.input.arn}/*",
        aws_s3_bucket.output.arn,
        "${aws_s3_bucket.output.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role" "batch_instance" {
  name = "${var.project_name}-batch-instance"

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

resource "aws_iam_role_policy_attachment" "batch_instance_ecs" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "batch" {
  name = "${var.project_name}-batch-profile"
  role = aws_iam_role.batch_instance.name
}

resource "aws_iam_role" "spot_fleet" {
  name = "${var.project_name}-spot-fleet"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "spotfleet.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  role       = aws_iam_role.spot_fleet.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/${var.project_name}"
  retention_in_days = 14
}

# EventBridge Rule for scheduled jobs
resource "aws_cloudwatch_event_rule" "nightly" {
  name                = "${var.project_name}-nightly"
  schedule_expression = "cron(0 2 * * ? *)"  # 2 AM UTC daily
}

resource "aws_cloudwatch_event_target" "batch" {
  rule     = aws_cloudwatch_event_rule.nightly.name
  arn      = aws_batch_job_queue.low_priority.arn
  role_arn = aws_iam_role.eventbridge_batch.arn

  batch_target {
    job_definition = aws_batch_job_definition.main.arn
    job_name       = "nightly-job"
  }
}

resource "aws_iam_role" "eventbridge_batch" {
  name = "${var.project_name}-eventbridge-batch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_batch" {
  name = "batch-submit"
  role = aws_iam_role.eventbridge_batch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "batch:SubmitJob"
      ]
      Resource = "*"
    }]
  })
}

output "job_queue_high" {
  value = aws_batch_job_queue.high_priority.arn
}

output "job_queue_low" {
  value = aws_batch_job_queue.low_priority.arn
}

output "job_definition" {
  value = aws_batch_job_definition.main.arn
}

output "input_bucket" {
  value = aws_s3_bucket.input.bucket
}

output "output_bucket" {
  value = aws_s3_bucket.output.bucket
}
```

## Implementation

### Docker Image
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install boto3 pandas numpy

COPY process.py .

ENTRYPOINT ["python", "process.py"]
```

### Batch Job Script
```python
# process.py
import os
import json
import boto3
import pandas as pd
from datetime import datetime

s3 = boto3.client('s3')

INPUT_BUCKET = os.environ['INPUT_BUCKET']
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
ARRAY_INDEX = os.environ.get('AWS_BATCH_JOB_ARRAY_INDEX', '0')

def main():
    print(f"Starting job processing at {datetime.now()}")
    print(f"Array index: {ARRAY_INDEX}")

    # Download input file
    input_key = f"input/data_{ARRAY_INDEX}.csv"
    local_input = f"/tmp/input_{ARRAY_INDEX}.csv"

    print(f"Downloading s3://{INPUT_BUCKET}/{input_key}")
    s3.download_file(INPUT_BUCKET, input_key, local_input)

    # Process data
    df = pd.read_csv(local_input)
    print(f"Processing {len(df)} rows")

    # Example transformation
    df['processed_at'] = datetime.now().isoformat()
    df['array_index'] = ARRAY_INDEX

    # Upload result
    output_key = f"output/result_{ARRAY_INDEX}.csv"
    local_output = f"/tmp/output_{ARRAY_INDEX}.csv"
    df.to_csv(local_output, index=False)

    print(f"Uploading to s3://{OUTPUT_BUCKET}/{output_key}")
    s3.upload_file(local_output, OUTPUT_BUCKET, output_key)

    print(f"Job completed at {datetime.now()}")

if __name__ == '__main__':
    main()
```

## Deployment Commands

```bash
# Build and push Docker image
aws ecr get-login-password | docker login --username AWS --password-stdin xxx.dkr.ecr.us-east-1.amazonaws.com
docker build -t batch-processor-job .
docker push xxx.dkr.ecr.us-east-1.amazonaws.com/batch-processor-job:latest

# Submit single job
aws batch submit-job \
  --job-name "test-job" \
  --job-queue "batch-processor-low-priority" \
  --job-definition "batch-processor-job"

# Submit array job (parallel processing)
aws batch submit-job \
  --job-name "array-job" \
  --job-queue "batch-processor-low-priority" \
  --job-definition "batch-processor-array-job" \
  --array-properties size=100

# Submit job with overrides
aws batch submit-job \
  --job-name "custom-job" \
  --job-queue "batch-processor-high-priority" \
  --job-definition "batch-processor-job" \
  --container-overrides '{
    "environment": [
      {"name": "CUSTOM_VAR", "value": "custom_value"}
    ],
    "resourceRequirements": [
      {"type": "VCPU", "value": "4"},
      {"type": "MEMORY", "value": "8192"}
    ]
  }'

# List jobs
aws batch list-jobs --job-queue batch-processor-low-priority --job-status RUNNING

# View job details
aws batch describe-jobs --jobs JOB_ID
```

## Cost Breakdown

| Component | Pricing |
|-----------|---------|
| EC2 On-Demand | $0.085/hr (m5.large) |
| EC2 Spot | ~$0.025/hr (70% off) |
| Fargate vCPU | $0.04048/hr |
| Fargate Memory | $0.004445/GB/hr |
| S3 Storage | $0.023/GB |

### Example Costs
| Workload | Compute Hours | Spot | On-Demand |
|----------|---------------|------|-----------|
| 100 jobs (1hr each) | 100 | ~$3 | ~$9 |
| 1000 jobs (1hr each) | 1000 | ~$25 | ~$85 |

## Best Practices

1. **Use Spot for cost savings** - Up to 90% cheaper
2. **Use array jobs for parallel processing**
3. **Set appropriate retry strategies**
4. **Use Fargate for small jobs**
5. **Monitor job queue depth**

## Common Mistakes

1. **No Spot interruption handling**: Jobs fail without retry
2. **Undersized compute**: Jobs timeout
3. **No job timeouts**: Jobs run forever
4. **Large container images**: Slow startup
5. **Missing IAM permissions**: Jobs can't access S3

## Sources

- [AWS Batch Documentation](https://docs.aws.amazon.com/batch/latest/userguide/)
- [AWS Batch Best Practices](https://docs.aws.amazon.com/batch/latest/userguide/best-practices.html)
- [Batch Job Definition Parameters](https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html)
