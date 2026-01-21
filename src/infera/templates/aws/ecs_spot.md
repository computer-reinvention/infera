# AWS ECS with Spot Instances

## Overview

Deploy cost-optimized containerized workloads using ECS with Spot Instances. Achieve up to 90% cost savings compared to On-Demand pricing by leveraging spare EC2 capacity. Ideal for fault-tolerant workloads, batch processing, and development environments.

## Detection Signals

Use this template when:
- Cost optimization is critical
- Workload is fault-tolerant
- Batch/background processing
- Development/staging environments
- Can handle interruptions
- Stateless applications

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                           AWS Cloud                              │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Application Load Balancer                   │   │
                    │   └─────────────────────────┬───────────────────────────────┘   │
                    │                             │                                   │
                    │                             ▼                                   │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                     ECS Cluster                          │   │
                    │   │                                                         │   │
                    │   │   ┌─────────────────────────────────────────────────┐   │   │
                    │   │   │         Capacity Provider Strategy               │   │   │
                    │   │   │                                                 │   │   │
                    │   │   │  ┌─────────────────┐  ┌─────────────────────┐  │   │   │
                    │   │   │  │   On-Demand     │  │     Spot            │  │   │   │
                    │   │   │  │   (Base: 20%)   │  │   (Weight: 80%)     │  │   │   │
                    │   │   │  │                 │  │                     │  │   │   │
                    │   │   │  │  ┌───────────┐  │  │  ┌───────────┐      │  │   │   │
                    │   │   │  │  │ Instance  │  │  │  │ Spot Inst │      │  │   │   │
                    │   │   │  │  │ m5.large  │  │  │  │ m5.large  │      │  │   │   │
                    │   │   │  │  └───────────┘  │  │  │ m5.xlarge │      │  │   │   │
                    │   │   │  │                 │  │  │ m6i.large │      │  │   │   │
                    │   │   │  │  Guaranteed     │  │  │ c5.large  │      │  │   │   │
                    │   │   │  │  availability   │  │  └───────────┘      │  │   │   │
                    │   │   │  └─────────────────┘  │  60-90% cheaper     │  │   │   │
                    │   │   │                       └─────────────────────┘  │   │   │
                    │   │   └─────────────────────────────────────────────────┘   │   │
                    │   │                                                         │   │
                    │   │   Auto Scaling Group handles Spot interruptions          │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Up to 90% savings • Multiple instance types • Auto-replace   │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Cluster | Container orchestration | Capacity providers |
| Auto Scaling Group | EC2 management | Mixed instances |
| Launch Template | Instance config | Spot options |
| ECS Service | Task management | Capacity strategy |
| ALB | Load balancing | Target groups |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| On-Demand ASG | Guaranteed capacity | Base capacity |
| CloudWatch | Monitoring | Spot metrics |
| SNS | Notifications | Interruption alerts |
| EventBridge | Automation | Spot events |

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
  default = "spot-app"
}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

# ECS Cluster with Capacity Providers
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = [
    aws_ecs_capacity_provider.spot.name,
    aws_ecs_capacity_provider.on_demand.name
  ]

  default_capacity_provider_strategy {
    base              = 1  # Minimum On-Demand tasks
    weight            = 1
    capacity_provider = aws_ecs_capacity_provider.on_demand.name
  }

  default_capacity_provider_strategy {
    base              = 0
    weight            = 4  # 80% Spot
    capacity_provider = aws_ecs_capacity_provider.spot.name
  }
}

# Spot Capacity Provider
resource "aws_ecs_capacity_provider" "spot" {
  name = "${var.project_name}-spot"

  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.spot.arn
    managed_termination_protection = "ENABLED"

    managed_scaling {
      maximum_scaling_step_size = 10
      minimum_scaling_step_size = 1
      status                    = "ENABLED"
      target_capacity           = 100
    }
  }
}

# On-Demand Capacity Provider (for base capacity)
resource "aws_ecs_capacity_provider" "on_demand" {
  name = "${var.project_name}-on-demand"

  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.on_demand.arn
    managed_termination_protection = "ENABLED"

    managed_scaling {
      maximum_scaling_step_size = 5
      minimum_scaling_step_size = 1
      status                    = "ENABLED"
      target_capacity           = 100
    }
  }
}

# Launch Template for Spot Instances
resource "aws_launch_template" "spot" {
  name_prefix   = "${var.project_name}-spot-"
  image_id      = data.aws_ami.ecs_optimized.id

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs.name
  }

  vpc_security_group_ids = [aws_security_group.ecs_instances.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${aws_ecs_cluster.main.name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_SPOT_INSTANCE_DRAINING=true" >> /etc/ecs/ecs.config
    echo "ECS_CONTAINER_STOP_TIMEOUT=90s" >> /etc/ecs/ecs.config
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-spot"
    }
  }

  # Spot instances request
  instance_market_options {
    market_type = "spot"
    spot_options {
      spot_instance_type             = "one-time"
      instance_interruption_behavior = "terminate"
    }
  }
}

# Launch Template for On-Demand Instances
resource "aws_launch_template" "on_demand" {
  name_prefix   = "${var.project_name}-on-demand-"
  image_id      = data.aws_ami.ecs_optimized.id
  instance_type = "m5.large"

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs.name
  }

  vpc_security_group_ids = [aws_security_group.ecs_instances.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${aws_ecs_cluster.main.name}" >> /etc/ecs/ecs.config
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-on-demand"
    }
  }
}

# Spot Auto Scaling Group with Mixed Instances
resource "aws_autoscaling_group" "spot" {
  name                = "${var.project_name}-spot-asg"
  vpc_zone_identifier = module.vpc.private_subnets
  min_size            = 0
  max_size            = 20
  desired_capacity    = 0

  protect_from_scale_in = true

  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "price-capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.spot.id
        version            = "$Latest"
      }

      # Multiple instance types for better Spot availability
      override {
        instance_type     = "m5.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "m5.xlarge"
        weighted_capacity = "2"
      }
      override {
        instance_type     = "m6i.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "c5.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "c5.xlarge"
        weighted_capacity = "2"
      }
      override {
        instance_type     = "r5.large"
        weighted_capacity = "1"
      }
    }
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = true
    propagate_at_launch = true
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

# On-Demand Auto Scaling Group
resource "aws_autoscaling_group" "on_demand" {
  name                = "${var.project_name}-on-demand-asg"
  vpc_zone_identifier = module.vpc.private_subnets
  min_size            = 0
  max_size            = 5
  desired_capacity    = 0

  protect_from_scale_in = true

  launch_template {
    id      = aws_launch_template.on_demand.id
    version = "$Latest"
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = true
    propagate_at_launch = true
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "main" {
  family                   = var.project_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["EC2"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name  = var.project_name
      image = "${aws_ecr_repository.main.repository_url}:latest"

      portMappings = [{
        containerPort = 8080
        hostPort      = 8080
        protocol      = "tcp"
      }]

      environment = [
        { name = "NODE_ENV", value = "production" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.main.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # Graceful shutdown for Spot interruptions
      stopTimeout = 90
    }
  ])
}

# ECS Service with Capacity Provider Strategy
resource "aws_ecs_service" "main" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = 4

  # Use capacity providers instead of launch_type
  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.on_demand.name
    base              = 1  # At least 1 On-Demand task
    weight            = 1
  }

  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.spot.name
    base              = 0
    weight            = 4  # 80% Spot
  }

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
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

  # Handle Spot interruptions gracefully
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.http]
}

# ALB
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "main" {
  name        = "${var.project_name}-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10  # Fast health checks for Spot
    matcher             = "200"
  }

  # Faster deregistration for Spot
  deregistration_delay = 30
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_instances" {
  name        = "${var.project_name}-instances-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-tasks-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM
resource "aws_iam_role" "ecs_instance" {
  name = "${var.project_name}-ecs-instance"

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

resource "aws_iam_role_policy_attachment" "ecs_instance" {
  role       = aws_iam_role.ecs_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ecs" {
  name = "${var.project_name}-ecs-profile"
  role = aws_iam_role.ecs_instance.name
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"

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

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECR
resource "aws_ecr_repository" "main" {
  name = var.project_name
}

# CloudWatch
resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7
}

# ECS AMI
data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }
}

# Spot Interruption Handler (EventBridge Rule)
resource "aws_cloudwatch_event_rule" "spot_interruption" {
  name        = "${var.project_name}-spot-interruption"
  description = "Capture Spot Instance interruption warnings"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })
}

resource "aws_cloudwatch_event_target" "spot_interruption" {
  rule      = aws_cloudwatch_event_rule.spot_interruption.name
  target_id = "LogToCloudWatch"
  arn       = aws_cloudwatch_log_group.spot_events.arn
}

resource "aws_cloudwatch_log_group" "spot_events" {
  name              = "/aws/events/${var.project_name}-spot"
  retention_in_days = 7
}

output "alb_dns" {
  value = aws_lb.main.dns_name
}
```

## Implementation

### Application with Graceful Shutdown
```javascript
// index.js - Handle SIGTERM for Spot interruptions
const express = require('express');
const app = express();

let isShuttingDown = false;

app.get('/health', (req, res) => {
  if (isShuttingDown) {
    return res.status(503).json({ status: 'shutting down' });
  }
  res.json({ status: 'healthy' });
});

app.get('/api/data', (req, res) => {
  if (isShuttingDown) {
    return res.status(503).json({ error: 'Service unavailable' });
  }
  res.json({ message: 'Hello from Spot!' });
});

const server = app.listen(8080, () => {
  console.log('Server running on port 8080');
});

// Graceful shutdown on SIGTERM (Spot interruption)
process.on('SIGTERM', () => {
  console.log('SIGTERM received - starting graceful shutdown');
  isShuttingDown = true;

  // Stop accepting new requests
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });

  // Force close after 90 seconds
  setTimeout(() => {
    console.log('Forcing shutdown');
    process.exit(1);
  }, 90000);
});
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Build and push image
aws ecr get-login-password | docker login --username AWS --password-stdin xxx.dkr.ecr.us-east-1.amazonaws.com
docker build -t spot-app .
docker push xxx.dkr.ecr.us-east-1.amazonaws.com/spot-app:latest

# Update service
aws ecs update-service --cluster spot-app-cluster --service spot-app --force-new-deployment

# View Spot savings
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter '{"Dimensions":{"Key":"PURCHASE_TYPE","Values":["Spot"]}}'
```

## Cost Breakdown

| Instance Type | On-Demand | Spot (avg) | Savings |
|---------------|-----------|------------|---------|
| m5.large | $0.096/hr | $0.029/hr | 70% |
| m5.xlarge | $0.192/hr | $0.058/hr | 70% |
| c5.large | $0.085/hr | $0.026/hr | 69% |
| r5.large | $0.126/hr | $0.038/hr | 70% |

### Monthly Estimate (4 tasks average)
| Configuration | On-Demand | Spot (80%) | Savings |
|---------------|-----------|------------|---------|
| 4x m5.large | ~$280 | ~$90 | ~$190 |

## Best Practices

### Instance Diversification
1. Use multiple instance types
2. Spread across availability zones
3. Use capacity-optimized allocation
4. Monitor interruption rates

### Application Design
1. Implement graceful shutdown
2. Enable ECS Spot draining
3. Use health check endpoints
4. Store state externally

### Monitoring
1. Track Spot interruptions
2. Monitor task placement
3. Alert on capacity issues
4. Review Spot savings

## Common Mistakes

1. **Single instance type**: Higher interruption risk
2. **No On-Demand base**: No guaranteed capacity
3. **Missing graceful shutdown**: Lost requests
4. **Slow health checks**: Delayed failover
5. **Stateful containers**: Data loss on interruption

## Sources

- [EC2 Spot Best Practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
- [ECS Capacity Providers](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/cluster-capacity-providers.html)
- [Spot Instance Advisor](https://aws.amazon.com/ec2/spot/instance-advisor/)
