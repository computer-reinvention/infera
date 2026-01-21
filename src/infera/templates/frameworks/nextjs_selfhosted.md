# Next.js Self-Hosted (Cloud Run / ECS)

## Overview

Deploy Next.js applications on your own infrastructure using containers. Provides full control over the runtime environment, custom scaling policies, and integration with existing cloud infrastructure. Ideal for teams with specific compliance requirements, cost optimization needs, or existing cloud investments.

## Detection Signals

Use this template when:
- `next.config.js` or `next.config.mjs` exists
- `package.json` contains `next` dependency
- `Dockerfile` present or container deployment preferred
- User wants infrastructure control
- Existing GCP/AWS investment
- Compliance requirements (data residency)
- Cost optimization at scale (>$500/month on Vercel)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        Cloud Provider                            │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Load Balancer / CDN                     │   │
                    │   │           (Cloud CDN / CloudFront + ALB)                 │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                Container Service                         │   │
                    │   │              (Cloud Run / ECS Fargate)                   │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │ Next.js   │ │ Next.js   │ │ Next.js   │             │   │
                    │   │  │ Container │ │ Container │ │ Container │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │  SSR +    │ │  SSR +    │ │  SSR +    │             │   │
                    │   │  │  API      │ │  API      │ │  API      │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 1-20 instances based on CPU/requests    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │  Database │     │   Cache   │     │  Storage  │            │
                    │   │(Cloud SQL/│     │ (Redis/   │     │ (GCS/S3)  │            │
                    │   │   RDS)    │     │Memorystore│     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Full control • Custom scaling • VPC integration               │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 2 vCPU, 2GB RAM |
| Cloud CDN | Static asset caching | Cache control headers |
| Cloud SQL | Database | PostgreSQL 15 |
| Memorystore | Redis cache | 1GB |
| Artifact Registry | Container images | Docker |
| Cloud Storage | Static files, uploads | Regional |
| Secret Manager | Environment secrets | Auto-mounted |

### AWS (ECS Fargate)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Fargate | Container hosting | 1 vCPU, 2GB RAM |
| ALB | Load balancing | Target groups |
| CloudFront | CDN | S3 + ALB origins |
| RDS Aurora | Database | PostgreSQL Serverless v2 |
| ElastiCache | Redis cache | 1 node |
| ECR | Container images | Docker |
| S3 | Static files | Website hosting |
| Secrets Manager | Environment secrets | ECS integration |

## Configuration

### Dockerfile (Optimized)
```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application
RUN npm run build

# Stage 3: Runner
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy necessary files
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Set ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### next.config.mjs (Standalone Output)
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker
  output: 'standalone',

  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'storage.googleapis.com',
      },
      {
        protocol: 'https',
        hostname: '*.s3.amazonaws.com',
      },
    ],
    // Use external image optimization service
    loader: 'custom',
    loaderFile: './image-loader.js',
  },

  // Compress responses
  compress: true,

  // Generate build ID from git
  generateBuildId: async () => {
    return process.env.GIT_SHA || 'development';
  },

  // Caching headers for static assets
  async headers() {
    return [
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        source: '/images/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=86400, stale-while-revalidate=604800',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

### GCP Terraform
```hcl
# main.tf - GCP Cloud Run
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP Project ID"
}

variable "region" {
  default = "us-central1"
}

variable "project_name" {
  default = "nextjs-app"
}

# Artifact Registry
resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = var.project_name
  format        = "DOCKER"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "main" {
  name     = var.project_name
  location = var.region

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 20
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/app:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        cpu_idle = true  # Scale to zero
      }

      ports {
        container_port = 3000
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 3000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 3000
        }
        period_seconds    = 30
        timeout_seconds   = 3
        failure_threshold = 3
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Allow public access
resource "google_cloud_run_service_iam_member" "public" {
  location = google_cloud_run_v2_service.main.location
  service  = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# VPC Connector for database access
resource "google_vpc_access_connector" "main" {
  name          = "${var.project_name}-connector"
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"
}

# Cloud SQL PostgreSQL
resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = "projects/${var.project_id}/global/networks/default"
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "main" {
  name     = "app"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = "app"
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}

resource "random_password" "db" {
  length  = 32
  special = false
}

# Secret Manager
resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.project_name}-database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.main.name}:${random_password.db.result}@/app?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
}

# Cloud CDN with Load Balancer
resource "google_compute_global_address" "main" {
  name = "${var.project_name}-ip"
}

resource "google_compute_region_network_endpoint_group" "main" {
  name                  = "${var.project_name}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.main.name
  }
}

resource "google_compute_backend_service" "main" {
  name                  = "${var.project_name}-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"

  backend {
    group = google_compute_region_network_endpoint_group.main.id
  }

  enable_cdn = true

  cdn_policy {
    cache_mode                   = "CACHE_ALL_STATIC"
    default_ttl                  = 3600
    max_ttl                      = 86400
    client_ttl                   = 3600
    negative_caching             = true
    serve_while_stale            = 86400
    signed_url_cache_max_age_sec = 0

    cache_key_policy {
      include_host         = true
      include_protocol     = true
      include_query_string = true
    }
  }
}

resource "google_compute_url_map" "main" {
  name            = "${var.project_name}-urlmap"
  default_service = google_compute_backend_service.main.id
}

resource "google_compute_managed_ssl_certificate" "main" {
  name = "${var.project_name}-cert"

  managed {
    domains = ["app.example.com"]
  }
}

resource "google_compute_target_https_proxy" "main" {
  name             = "${var.project_name}-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_forwarding_rule" "main" {
  name                  = "${var.project_name}-lb"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_https_proxy.main.id
  port_range            = "443"
  ip_address            = google_compute_global_address.main.id
}

output "url" {
  value = "https://${google_compute_global_address.main.address}"
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.main.uri
}
```

### AWS Terraform
```hcl
# main.tf - AWS ECS Fargate
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
  default = "nextjs-app"
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

  enable_nat_gateway     = true
  single_nat_gateway     = true
  enable_dns_hostnames   = true
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
  name = var.project_name

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
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "app"
      image = "${aws_ecr_repository.main.repository_url}:latest"

      portMappings = [
        {
          containerPort = 3000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "NODE_ENV"
          value = "production"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.database_url.arn
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
        command     = ["CMD-SHELL", "curl -f http://localhost:3000/api/health || exit 1"]
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
    container_name   = "app"
    container_port   = 3000
  }
}

# Auto Scaling
resource "aws_appautoscaling_target" "main" {
  max_capacity       = 20
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.project_name}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.main.resource_id
  scalable_dimension = aws_appautoscaling_target.main.scalable_dimension
  service_namespace  = aws_appautoscaling_target.main.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = var.project_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "main" {
  name        = var.project_name
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/health"
    healthy_threshold   = 2
    unhealthy_threshold = 10
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  default_root_object = ""
  aliases             = ["app.example.com"]

  origin {
    domain_name = aws_lb.main.dns_name
    origin_id   = "alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    forwarded_values {
      query_string = true
      headers      = ["Host", "Accept", "Authorization"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 86400
  }

  # Cache static assets
  ordered_cache_behavior {
    path_pattern     = "/_next/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 31536000
    default_ttl            = 31536000
    max_ttl                = 31536000
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# Security Groups
resource "aws_security_group" "alb" {
  name   = "${var.project_name}-alb"
  vpc_id = module.vpc.vpc_id

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
  name   = "${var.project_name}-ecs"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 3000
    to_port         = 3000
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
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.project_name}-database-url"
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}

# ACM Certificate
resource "aws_acm_certificate" "main" {
  domain_name       = "app.example.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

output "alb_url" {
  value = "https://${aws_lb.main.dns_name}"
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.main.domain_name}"
}
```

## Deployment Commands

### GCP
```bash
# Build and push to Artifact Registry
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/app:latest

# Deploy to Cloud Run
gcloud run deploy ${APP_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/app:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 20 \
  --memory 2Gi \
  --cpu 2

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${APP_NAME}" --limit 100
```

### AWS
```bash
# Login to ECR
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Build and push
docker build -t ${APP_NAME} .
docker tag ${APP_NAME}:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}:latest

# Force new deployment
aws ecs update-service --cluster ${APP_NAME} --service ${APP_NAME} --force-new-deployment

# View logs
aws logs tail /ecs/${APP_NAME} --follow
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (min 1 instance) | ~$30 |
| Cloud SQL (db-f1-micro) | ~$10 |
| Cloud CDN | ~$20 |
| Cloud Storage | ~$5 |
| **Total** | **~$65** |

### AWS ECS Fargate
| Component | Monthly Cost |
|-----------|--------------|
| ECS Fargate (2 tasks) | ~$60 |
| ALB | ~$20 |
| CloudFront | ~$20 |
| RDS (db.t3.micro) | ~$15 |
| **Total** | **~$115** |

## Best Practices

1. **Use standalone output** - Smaller Docker images, faster deployments
2. **Enable compression** - Gzip responses for better performance
3. **Configure CDN properly** - Cache static assets at edge
4. **Set up health checks** - Ensure proper container health monitoring
5. **Use VPC for database** - Private networking for security
6. **Implement secrets management** - Never hardcode credentials
7. **Enable container insights** - Monitor CPU, memory, network
8. **Use immutable deployments** - Tag images with git SHA

## Common Mistakes

1. **Not using standalone output** - Results in larger, slower images
2. **Missing health check endpoint** - Container may not start properly
3. **No CDN for static assets** - Poor performance, higher costs
4. **Database in public subnet** - Security vulnerability
5. **Missing VPC connector** - Can't connect to private resources
6. **No auto-scaling** - Over-provisioned or under-provisioned
7. **Ignoring cold starts** - Set minimum instances for latency-sensitive apps
8. **Not caching build layers** - Slow CI/CD pipelines

## Example Configuration

```yaml
# infera.yaml
project_name: my-nextjs-app
provider: gcp  # or aws

framework:
  name: nextjs
  version: "14"

deployment:
  type: container
  runtime: nodejs-20

  resources:
    cpu: 2
    memory: 2Gi

  scaling:
    min_instances: 1
    max_instances: 20
    target_cpu: 70

  health_check:
    path: /api/health
    interval: 30s

database:
  type: postgresql
  version: "15"
  tier: small

cache:
  type: redis
  size: 1gb

cdn:
  enabled: true
  cache_static: true

env_vars:
  NODE_ENV: production
  NEXT_TELEMETRY_DISABLED: "1"
```

## Sources

- [Next.js Docker Deployment](https://nextjs.org/docs/deployment#docker-image)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Next.js Standalone Output](https://nextjs.org/docs/advanced-features/output-file-tracing)
