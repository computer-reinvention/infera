# AWS EKS ML Serving

## Overview

Deploy machine learning model inference using Amazon EKS with GPU support, autoscaling, and integration with SageMaker. This architecture provides high-performance ML inference at scale with Kubernetes orchestration.

## Detection Signals

Use this template when:
- ML model serving required
- GPU acceleration needed
- High-throughput inference
- Multiple model versions
- Kubernetes orchestration preferred
- Custom serving frameworks (TensorFlow Serving, TorchServe)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │            Application Load Balancer                     │   │
                    │   └─────────────────────────┬───────────────────────────────┘   │
                    │                             │                                   │
                    │   ┌─────────────────────────┼───────────────────────────────┐   │
                    │   │                     EKS Cluster                          │   │
                    │   │                                                         │   │
                    │   │  ┌─────────────────────────────────────────────────┐    │   │
                    │   │  │              GPU Node Group                      │    │   │
                    │   │  │         (p3.2xlarge / g4dn.xlarge)              │    │   │
                    │   │  │                                                 │    │   │
                    │   │  │  ┌───────────────┐  ┌───────────────┐          │    │   │
                    │   │  │  │ Inference Pod │  │ Inference Pod │          │    │   │
                    │   │  │  │               │  │               │          │    │   │
                    │   │  │  │ ┌───────────┐ │  │ ┌───────────┐ │          │    │   │
                    │   │  │  │ │ TF Serving│ │  │ │TorchServe │ │          │    │   │
                    │   │  │  │ │ + GPU     │ │  │ │ + GPU     │ │          │    │   │
                    │   │  │  │ └───────────┘ │  │ └───────────┘ │          │    │   │
                    │   │  │  │  NVIDIA T4   │  │  NVIDIA T4   │          │    │   │
                    │   │  │  └───────────────┘  └───────────────┘          │    │   │
                    │   │  │                                                 │    │   │
                    │   │  │  HPA: Scale on GPU utilization / requests      │    │   │
                    │   │  └─────────────────────────────────────────────────┘    │   │
                    │   │                                                         │   │
                    │   │  ┌─────────────────────────────────────────────────┐    │   │
                    │   │  │              CPU Node Group                      │    │   │
                    │   │  │           (for preprocessing)                    │    │   │
                    │   │  └─────────────────────────────────────────────────┘    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
                    │   │     S3       │  │    ECR       │  │  SageMaker   │         │
                    │   │   (Models)   │  │  (Images)    │  │  (Training)  │         │
                    │   └──────────────┘  └──────────────┘  └──────────────┘         │
                    │                                                                 │
                    │   GPU inference • Auto-scaling • A/B testing • Model versioning │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| EKS Cluster | Kubernetes control plane | GPU add-ons |
| GPU Node Group | Inference compute | g4dn/p3 instances |
| ECR | Container images | Model images |
| S3 | Model storage | Model artifacts |
| ALB | Load balancing | Ingress controller |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| SageMaker | Training | Training jobs |
| Spot Instances | Cost optimization | GPU spot |
| Prometheus | Monitoring | Custom metrics |
| Karpenter | Autoscaling | Node provisioning |
| Triton | Multi-model | Inference server |

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
  default = "ml-inference"
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

  azs             = ["${var.region}a", "${var.region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

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

  # GPU Node Group
  eks_managed_node_groups = {
    # GPU nodes for inference
    gpu = {
      name           = "gpu-inference"
      instance_types = ["g4dn.xlarge"]  # 1x T4 GPU, 4 vCPU, 16GB RAM
      ami_type       = "AL2_x86_64_GPU"

      min_size     = 0
      max_size     = 10
      desired_size = 2

      labels = {
        "nvidia.com/gpu" = "true"
        "node-type"      = "gpu"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      # Pre-install NVIDIA drivers
      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        # Enable NVIDIA persistence daemon
        nvidia-smi -pm ENABLED
      EOT
    }

    # CPU nodes for preprocessing
    cpu = {
      name           = "cpu-preprocessing"
      instance_types = ["m5.large"]

      min_size     = 1
      max_size     = 5
      desired_size = 2

      labels = {
        "node-type" = "cpu"
      }
    }

    # GPU Spot for cost optimization
    gpu_spot = {
      name           = "gpu-spot"
      instance_types = ["g4dn.xlarge", "g4dn.2xlarge"]
      capacity_type  = "SPOT"
      ami_type       = "AL2_x86_64_GPU"

      min_size     = 0
      max_size     = 10
      desired_size = 0

      labels = {
        "nvidia.com/gpu" = "true"
        "node-type"      = "gpu-spot"
      }

      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        },
        {
          key    = "spot"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }

  enable_irsa = true

  # Install NVIDIA device plugin
  cluster_addons = {
    coredns = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni = { most_recent = true }
  }
}

# Configure providers
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

# NVIDIA Device Plugin
resource "helm_release" "nvidia_device_plugin" {
  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  namespace  = "kube-system"
  version    = "0.14.3"

  set {
    name  = "tolerations[0].key"
    value = "nvidia.com/gpu"
  }

  set {
    name  = "tolerations[0].operator"
    value = "Exists"
  }

  set {
    name  = "tolerations[0].effect"
    value = "NoSchedule"
  }

  depends_on = [module.eks]
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
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.lb_controller_irsa.iam_role_arn
  }

  depends_on = [module.eks]
}

# S3 Bucket for Models
resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models-${random_id.bucket.hex}"
}

resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ECR Repository
resource "aws_ecr_repository" "inference" {
  name                 = "${var.project_name}/inference"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# IRSA for model access
module "inference_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${var.project_name}-inference"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["inference:inference-sa"]
    }
  }
}

resource "aws_iam_role_policy" "inference_s3" {
  name = "s3-model-access"
  role = module.inference_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.models.arn,
        "${aws_s3_bucket.models.arn}/*"
      ]
    }]
  })
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "models_bucket" {
  value = aws_s3_bucket.models.bucket
}

output "ecr_repository" {
  value = aws_ecr_repository.inference.repository_url
}
```

### Kubernetes Manifests

#### TensorFlow Serving Deployment
```yaml
# k8s/tensorflow-serving.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: inference
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: inference-sa
  namespace: inference
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/ml-inference-inference
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tf-serving
  namespace: inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tf-serving
  template:
    metadata:
      labels:
        app: tf-serving
    spec:
      serviceAccountName: inference-sa
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      nodeSelector:
        node-type: gpu
      containers:
        - name: tf-serving
          image: tensorflow/serving:2.14.0-gpu
          ports:
            - containerPort: 8500
              name: grpc
            - containerPort: 8501
              name: rest
          env:
            - name: MODEL_BASE_PATH
              value: "s3://ml-inference-models/models"
            - name: MODEL_NAME
              value: "my_model"
            - name: AWS_REGION
              value: "us-east-1"
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "4"
              memory: "8Gi"
              nvidia.com/gpu: "1"
          livenessProbe:
            httpGet:
              path: /v1/models/my_model
              port: 8501
            initialDelaySeconds: 60
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /v1/models/my_model
              port: 8501
            initialDelaySeconds: 30
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: tf-serving
  namespace: inference
spec:
  selector:
    app: tf-serving
  ports:
    - port: 8500
      targetPort: 8500
      name: grpc
    - port: 8501
      targetPort: 8501
      name: rest
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tf-serving-hpa
  namespace: inference
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tf-serving
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # Custom GPU metrics (requires DCGM exporter)
    - type: Pods
      pods:
        metric:
          name: DCGM_FI_DEV_GPU_UTIL
        target:
          type: AverageValue
          averageValue: "70"
```

#### TorchServe Deployment
```yaml
# k8s/torchserve.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: torchserve
  namespace: inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app: torchserve
  template:
    metadata:
      labels:
        app: torchserve
    spec:
      serviceAccountName: inference-sa
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      nodeSelector:
        node-type: gpu
      initContainers:
        - name: download-model
          image: amazon/aws-cli:latest
          command:
            - /bin/sh
            - -c
            - |
              aws s3 cp s3://ml-inference-models/models/model.mar /models/
          volumeMounts:
            - name: models
              mountPath: /models
      containers:
        - name: torchserve
          image: pytorch/torchserve:0.9.0-gpu
          args:
            - torchserve
            - --start
            - --model-store=/models
            - --models=all
          ports:
            - containerPort: 8080
              name: inference
            - containerPort: 8081
              name: management
            - containerPort: 8082
              name: metrics
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "4"
              memory: "8Gi"
              nvidia.com/gpu: "1"
          volumeMounts:
            - name: models
              mountPath: /models
          livenessProbe:
            httpGet:
              path: /ping
              port: 8080
            initialDelaySeconds: 60
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ping
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 5
      volumes:
        - name: models
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: torchserve
  namespace: inference
spec:
  selector:
    app: torchserve
  ports:
    - port: 8080
      targetPort: 8080
      name: inference
    - port: 8081
      targetPort: 8081
      name: management
```

#### Ingress
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: inference-ingress
  namespace: inference
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /v1/models/my_model
spec:
  rules:
    - host: inference.example.com
      http:
        paths:
          - path: /v1/models
            pathType: Prefix
            backend:
              service:
                name: tf-serving
                port:
                  number: 8501
          - path: /predictions
            pathType: Prefix
            backend:
              service:
                name: torchserve
                port:
                  number: 8080
```

## Deployment Commands

```bash
# Update kubeconfig
aws eks update-kubeconfig --name ml-inference-cluster

# Verify GPU nodes
kubectl get nodes -l nvidia.com/gpu=true
kubectl describe node <gpu-node-name> | grep nvidia.com/gpu

# Deploy inference workloads
kubectl apply -f k8s/

# Test TensorFlow Serving
curl -X POST http://inference.example.com/v1/models/my_model:predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [[1.0, 2.0, 3.0, 4.0]]}'

# Test TorchServe
curl -X POST http://inference.example.com/predictions/my_model \
  -T input.jpg

# View GPU utilization
kubectl exec -it <pod-name> -n inference -- nvidia-smi

# Scale deployment
kubectl scale deployment tf-serving -n inference --replicas=5
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| EKS Cluster | $73 |
| GPU Nodes (2x g4dn.xlarge) | ~$450 |
| CPU Nodes (2x m5.large) | ~$140 |
| NAT Gateway | ~$35 |
| ALB | ~$20 |
| **Total** | **~$718** |

### GPU Instance Pricing
| Instance | GPUs | On-Demand | Spot (~70% off) |
|----------|------|-----------|-----------------|
| g4dn.xlarge | 1x T4 | $0.526/hr | ~$0.16/hr |
| g4dn.2xlarge | 1x T4 | $0.752/hr | ~$0.23/hr |
| p3.2xlarge | 1x V100 | $3.06/hr | ~$0.92/hr |

## Best Practices

1. **Use Spot for non-critical inference**
2. **Enable GPU metrics monitoring**
3. **Implement model caching**
4. **Use batch inference when possible**
5. **Set resource requests/limits**

## Common Mistakes

1. **Missing GPU tolerations**: Pods not scheduled on GPU nodes
2. **No NVIDIA device plugin**: GPUs not detected
3. **Wrong AMI type**: Missing NVIDIA drivers
4. **Insufficient memory**: OOM errors
5. **No model versioning**: Can't rollback

## Sources

- [EKS GPU Support](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html)
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [TensorFlow Serving](https://www.tensorflow.org/tfx/guide/serving)
- [TorchServe](https://pytorch.org/serve/)
