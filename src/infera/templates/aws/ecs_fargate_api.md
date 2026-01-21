# AWS ECS Fargate API

## Overview

Deploy containerized APIs using ECS Fargate with Application Load Balancer. This architecture provides managed container orchestration without managing servers, automatic scaling, and seamless integration with AWS services. Ideal for APIs requiring custom runtimes, longer execution times, or consistent performance.

## Detection Signals

Use this template when:
- Containerized application (Dockerfile present)
- Need consistent performance (no cold starts)
- Request duration > 15 minutes
- Custom runtime requirements
- Memory > 10GB required
- WebSocket support needed

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                             │
                    │                                                             │
                    │   ┌─────────────────────────────────────────────────────┐   │
    Internet ──────►│   │       Application Load Balancer (ALB)               │   │
                    │   │                                                     │   │
                    │   │  ┌───────────┐    ┌───────────┐    ┌───────────┐   │   │
                    │   │  │ Target    │    │ Target    │    │ Target    │   │   │
                    │   │  │ Group     │    │ Group     │    │ Group     │   │   │
                    │   │  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘   │   │
                    │   └────────┼────────────────┼────────────────┼─────────┘   │
                    │            │                │                │             │
                    │            ▼                ▼                ▼             │
                    │   ┌─────────────────────────────────────────────────────┐   │
                    │   │                   ECS Cluster                        │   │
                    │   │                                                     │   │
                    │   │   ┌─────────────────────────────────────────────┐   │   │
                    │   │   │            ECS Service (Fargate)             │   │   │
                    │   │   │                                             │   │   │
                    │   │   │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │   │
                    │   │   │  │  Task   │  │  Task   │  │  Task   │     │   │   │
                    │   │   │  │Container│  │Container│  │Container│     │   │   │
                    │   │   │  └─────────┘  └─────────┘  └─────────┘     │   │   │
                    │   │   │                                             │   │   │
                    │   │   │  Auto-scaling: 2-10 tasks                   │   │   │
                    │   │   └─────────────────────────────────────────────┘   │   │
                    │   └─────────────────────────────────────────────────────┘   │
                    │                                                             │
                    │   Serverless containers • No EC2 management • Auto-scaling  │
                    └─────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Cluster | Container orchestration | Fargate capacity |
| ECS Service | Task management | Desired count, scaling |
| Task Definition | Container config | Image, CPU, memory |
| ALB | Load balancing | Target groups |
| ECR | Container registry | Repository |
| VPC | Networking | Subnets, security groups |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| RDS | SQL database | Aurora/PostgreSQL |
| ElastiCache | Caching | Redis/Memcached |
| S3 | File storage | Bucket |
| Secrets Manager | Secrets | Secret values |
| CloudWatch | Monitoring | Dashboards, alarms |
| WAF | Security | Web ACL |

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
  default = "my-api"
}

variable "container_port" {
  default = 8080
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

  tags = {
    Environment = "production"
  }
}

# ECR Repository
resource "aws_ecr_repository" "main" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "main" {
  family                   = var.project_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = var.project_name
      image = "${aws_ecr_repository.main.repository_url}:latest"

      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "PORT"
          value = tostring(var.container_port)
        },
        {
          name  = "NODE_ENV"
          value = "production"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.db_url.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.main.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "main" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = var.project_name
    container_port   = var.container_port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "main" {
  name        = "${var.project_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 10
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
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

# Security Groups
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "ALB security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
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

resource "aws_security_group" "ecs" {
  name        = "${var.project_name}-ecs-sg"
  description = "ECS tasks security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
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

# Auto Scaling
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.project_name}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# IAM Roles
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

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.db_url.arn
      ]
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

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

# Secrets Manager
resource "aws_secretsmanager_secret" "db_url" {
  name = "${var.project_name}/database-url"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}

# ACM Certificate (requires DNS validation)
resource "aws_acm_certificate" "main" {
  domain_name       = "api.example.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

output "alb_dns" {
  value = aws_lb.main.dns_name
}

output "ecr_repository" {
  value = aws_ecr_repository.main.repository_url
}
```

## Implementation

### Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./

USER nodejs

ENV NODE_ENV=production
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

CMD ["node", "dist/index.js"]
```

### Application Code
```javascript
// src/index.js
const express = require('express');
const helmet = require('helmet');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 8080;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

// API routes
app.get('/api/items', async (req, res) => {
  try {
    // Your business logic
    res.json({ items: [] });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/items', async (req, res) => {
  try {
    const data = req.body;
    // Your business logic
    res.status(201).json({ id: 'new-id', ...data });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});

const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
```

## Deployment Commands

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure credentials
aws configure

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build and push image
docker build -t my-api .
docker tag my-api:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/my-api:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/my-api:latest

# Deploy infrastructure
terraform init
terraform plan
terraform apply

# Force new deployment
aws ecs update-service \
  --cluster my-api-cluster \
  --service my-api \
  --force-new-deployment

# View logs
aws logs tail /ecs/my-api --follow

# Scale service
aws ecs update-service \
  --cluster my-api-cluster \
  --service my-api \
  --desired-count 5
```

## Best Practices

### Container
1. Use multi-stage builds
2. Run as non-root user
3. Include health checks
4. Keep images small (< 500MB)
5. Use specific image tags

### Networking
1. Run tasks in private subnets
2. Use ALB for internet access
3. Enable VPC Flow Logs
4. Use security groups properly
5. Consider VPC endpoints for AWS services

### Scaling
1. Set appropriate min/max capacity
2. Use target tracking scaling
3. Configure proper cooldowns
4. Monitor scaling events
5. Test scaling behavior

## Cost Breakdown

| Component | Pricing |
|-----------|---------|
| Fargate vCPU | $0.04048/vCPU/hour |
| Fargate Memory | $0.004445/GB/hour |
| ALB | $0.0225/hour + $0.008/LCU |
| NAT Gateway | $0.045/hour + $0.045/GB |
| Data Transfer | $0.09/GB (outbound) |

### Example Costs (2 tasks, 0.25 vCPU, 0.5 GB)
| Component | Monthly Cost |
|-----------|--------------|
| Fargate | ~$15 |
| ALB | ~$20 |
| NAT Gateway | ~$35 |
| **Total** | **~$70** |

### vs Lambda
| Aspect | ECS Fargate | Lambda |
|--------|-------------|--------|
| Cold starts | None | Yes |
| Max duration | Unlimited | 15 min |
| Scaling | Slower | Instant |
| Cost (low traffic) | Higher | Lower |
| Cost (high traffic) | Lower | Higher |

## Common Mistakes

1. **Public IP on tasks**: Use ALB instead
2. **No health checks**: Tasks never become healthy
3. **Wrong security groups**: Tasks can't reach DB
4. **Missing IAM permissions**: Secrets/ECR access fails
5. **No graceful shutdown**: Requests lost during deploys
6. **Single AZ**: No high availability
7. **No auto-scaling**: Manual scaling required

## Example Configuration

```yaml
project_name: my-ecs-api
provider: aws
architecture_type: ecs_fargate_api

resources:
  - id: api-cluster
    type: aws_ecs_cluster
    name: my-api-cluster
    provider: aws
    config:
      container_insights: true

  - id: api-service
    type: aws_ecs_service
    name: my-api
    provider: aws
    config:
      launch_type: FARGATE
      cpu: 256
      memory: 512
      desired_count: 2
      min_capacity: 2
      max_capacity: 10

  - id: api-alb
    type: aws_alb
    name: my-api-alb
    provider: aws
    config:
      internal: false
      ssl_certificate: true
```

## Sources

- [ECS Fargate Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [ALB Documentation](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)
