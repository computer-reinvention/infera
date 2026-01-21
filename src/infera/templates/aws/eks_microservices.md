# AWS EKS Microservices

## Overview

Deploy production-grade Kubernetes microservices using Amazon EKS with ALB Ingress Controller, service mesh, and managed add-ons. Ideal for complex applications requiring orchestration, service discovery, and fine-grained scaling.

## Detection Signals

Use this template when:
- Multiple services needing orchestration
- Kubernetes expertise available
- Complex networking requirements
- Service mesh needed
- Multi-team development
- Hybrid cloud deployments

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────────┐
                    │                             AWS Cloud                                │
                    │                                                                     │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────────┐   │
                    │   │            Application Load Balancer (ALB)                   │   │
                    │   │                  (via ALB Ingress Controller)                │   │
                    │   └─────────────────────────────┬───────────────────────────────┘   │
                    │                                 │                                   │
                    │   ┌─────────────────────────────┼───────────────────────────────┐   │
                    │   │                        EKS Cluster                           │   │
                    │   │                                                             │   │
                    │   │   ┌─────────────────────────────────────────────────────┐   │   │
                    │   │   │                 Kubernetes Namespaces                │   │   │
                    │   │   │                                                     │   │   │
                    │   │   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │   │
                    │   │   │  │   api-ns    │  │  users-ns   │  │  orders-ns  │  │   │   │
                    │   │   │  │             │  │             │  │             │  │   │   │
                    │   │   │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │  │   │   │
                    │   │   │  │ │API GW   │ │  │ │User Svc │ │  │ │Order Svc│ │  │   │   │
                    │   │   │  │ │Replicas │ │  │ │Replicas │ │  │ │Replicas │ │  │   │   │
                    │   │   │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │  │   │   │
                    │   │   │  │             │  │             │  │             │  │   │   │
                    │   │   │  │ HPA: 2-10   │  │ HPA: 3-20   │  │ HPA: 2-15   │  │   │   │
                    │   │   │  └─────────────┘  └─────────────┘  └─────────────┘  │   │   │
                    │   │   │                                                     │   │   │
                    │   │   │  ┌─────────────────────────────────────────────┐    │   │   │
                    │   │   │  │              Service Mesh (optional)         │    │   │   │
                    │   │   │  │         Istio / AWS App Mesh / Linkerd       │    │   │   │
                    │   │   │  └─────────────────────────────────────────────┘    │   │   │
                    │   │   └─────────────────────────────────────────────────────┘   │   │
                    │   │                                                             │   │
                    │   │   Node Groups: Managed / Fargate                            │   │
                    │   └─────────────────────────────────────────────────────────────┘   │
                    │                                                                     │
                    │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
                    │   │  RDS Aurora  │  │ ElastiCache  │  │    S3        │             │
                    │   └──────────────┘  └──────────────┘  └──────────────┘             │
                    │                                                                     │
                    └─────────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| EKS Cluster | Kubernetes control plane | Managed |
| Node Group | Worker nodes | Managed/Fargate |
| VPC | Networking | Private subnets |
| ALB Controller | Ingress | Helm addon |
| ECR | Container registry | Repositories |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| RDS | SQL database | Aurora/PostgreSQL |
| ElastiCache | Caching | Redis |
| Service Mesh | Observability | Istio/App Mesh |
| Secrets Manager | Secrets | CSI Driver |
| Prometheus | Monitoring | Managed Prometheus |

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
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
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
  default = "microservices"
}

variable "cluster_version" {
  default = "1.29"
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

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  # Required tags for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "${var.project_name}-cluster"
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  # Managed Node Groups
  eks_managed_node_groups = {
    general = {
      name           = "general"
      instance_types = ["m5.large"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3

      labels = {
        role = "general"
      }
    }

    # Spot instances for non-critical workloads
    spot = {
      name           = "spot"
      instance_types = ["m5.large", "m5.xlarge", "m6i.large"]
      capacity_type  = "SPOT"
      min_size       = 0
      max_size       = 10
      desired_size   = 2

      labels = {
        role = "spot"
      }

      taints = [{
        key    = "spot"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  # Fargate Profile for specific namespaces
  fargate_profiles = {
    serverless = {
      name = "serverless"
      selectors = [
        { namespace = "serverless" }
      ]
    }
  }

  # Enable IRSA
  enable_irsa = true

  # Cluster Add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  tags = {
    Environment = "production"
  }
}

# IRSA for EBS CSI Driver
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${var.project_name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# Configure Kubernetes Provider
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# AWS Load Balancer Controller
module "lb_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${var.project_name}-lb-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.6.2"

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.lb_controller_irsa.iam_role_arn
  }

  depends_on = [module.eks]
}

# Metrics Server
resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  namespace  = "kube-system"
  version    = "3.11.0"

  depends_on = [module.eks]
}

# RDS Aurora
resource "aws_rds_cluster" "main" {
  cluster_identifier     = "${var.project_name}-db"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.4"
  database_name          = "app"
  master_username        = "admin"
  master_password        = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 8.0
  }

  skip_final_snapshot = true
}

resource "aws_rds_cluster_instance" "main" {
  count               = 2
  identifier          = "${var.project_name}-db-${count.index}"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version
  publicly_accessible = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "db" {
  name        = "${var.project_name}-db-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "random_password" "db" {
  length  = 32
  special = false
}

# Store DB credentials in Secrets Manager
resource "aws_secretsmanager_secret" "db" {
  name = "${var.project_name}/database"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    host     = aws_rds_cluster.main.endpoint
    port     = 5432
    username = aws_rds_cluster.main.master_username
    password = random_password.db.result
    database = aws_rds_cluster.main.database_name
  })
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "db_endpoint" {
  value = aws_rds_cluster.main.endpoint
}
```

### Kubernetes Manifests

#### Namespace and Service
```yaml
# k8s/user-service.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: users
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: users
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      serviceAccountName: user-service
      containers:
        - name: user-service
          image: 123456789.dkr.ecr.us-east-1.amazonaws.com/user-service:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_HOST
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: host
            - name: DATABASE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: user-service
  namespace: users
spec:
  selector:
    app: user-service
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
  namespace: users
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

#### Ingress
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456789:certificate/xxx
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /users
            pathType: Prefix
            backend:
              service:
                name: user-service
                port:
                  number: 80
          - path: /orders
            pathType: Prefix
            backend:
              service:
                name: order-service
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 80
```

## Deployment Commands

```bash
# Update kubeconfig
aws eks update-kubeconfig --name microservices-cluster --region us-east-1

# Verify cluster access
kubectl get nodes
kubectl get pods -A

# Deploy services
kubectl apply -f k8s/

# Build and push image
aws ecr get-login-password | docker login --username AWS --password-stdin xxx.dkr.ecr.us-east-1.amazonaws.com
docker build -t user-service .
docker push xxx.dkr.ecr.us-east-1.amazonaws.com/user-service:latest

# Rollout update
kubectl rollout restart deployment/user-service -n users

# View logs
kubectl logs -f deployment/user-service -n users

# Scale deployment
kubectl scale deployment/user-service -n users --replicas=5

# Port forward for debugging
kubectl port-forward svc/user-service -n users 8080:80
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| EKS Cluster | $73 |
| Node Group (3x m5.large) | ~$200 |
| Spot Nodes (2x m5.large) | ~$60 |
| NAT Gateway (3 AZ) | ~$100 |
| ALB | ~$20 |
| RDS Aurora | ~$100 |
| **Total** | **~$553** |

## Best Practices

### Cluster Management
1. Use managed node groups
2. Enable cluster autoscaler
3. Use Fargate for burst workloads
4. Keep Kubernetes version current
5. Enable control plane logging

### Application Design
1. Implement health/readiness probes
2. Set resource requests/limits
3. Use horizontal pod autoscaling
4. Implement graceful shutdown
5. Use service accounts for IRSA

### Security
1. Enable pod security standards
2. Use network policies
3. Rotate credentials regularly
4. Scan images for vulnerabilities
5. Use Secrets Manager CSI driver

## Common Mistakes

1. **No resource limits**: Pods consume all node resources
2. **Missing probes**: Dead pods receive traffic
3. **Wrong subnet tags**: ALB creation fails
4. **No autoscaling**: Manual scaling required
5. **Single NAT Gateway**: Single point of failure

## Sources

- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
