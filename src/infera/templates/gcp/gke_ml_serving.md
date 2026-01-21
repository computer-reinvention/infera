# GCP GKE ML Serving

## Overview

Deploy machine learning models for inference on GKE with GPU support, auto-scaling, and model versioning. Ideal for production ML workloads requiring low-latency predictions, batch inference, or multiple model deployment.

## Detection Signals

Use this template when:
- ML model files detected (.pkl, .pt, .h5, .onnx, SavedModel/)
- ML serving frameworks (TensorFlow Serving, TorchServe, Triton)
- GPU requirements in code or config
- Model inference endpoints
- MLflow, BentoML, or similar patterns
- Large model file requirements

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │              GKE Cluster                 │
                        │  ┌────────────────────────────────────┐ │
    Internet ──────────►│  │      GPU Node Pool                  │ │
         │             │  │  ┌──────────┐    ┌──────────┐       │ │
    Cloud Load         │  │  │  Model   │    │  Model   │       │ │
    Balancer           │  │  │ Server A │    │ Server B │       │ │
                        │  │  │  (GPU)   │    │  (GPU)   │       │ │
                        │  │  └──────────┘    └──────────┘       │ │
                        │  └────────────────────────────────────┘ │
                        │  ┌────────────────────────────────────┐ │
                        │  │      CPU Node Pool                  │ │
                        │  │  ┌──────────┐    ┌──────────┐       │ │
                        │  │  │Preprocess│    │  Queue   │       │ │
                        │  │  │ Service  │    │  Worker  │       │ │
                        │  │  └──────────┘    └──────────┘       │ │
                        │  └────────────────────────────────────┘ │
                        └─────────────────────────────────────────┘
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                      Cloud Storage            Model Registry
                      (Model Artifacts)        (Vertex AI)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| GKE Cluster | Container orchestration | `google_container_cluster` |
| GPU Node Pool | Model inference | `google_container_node_pool` |
| Cloud Storage | Model artifacts | `google_storage_bucket` |
| Artifact Registry | Container images | `google_artifact_registry_repository` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Vertex AI Model Registry | Model versioning | `google_vertex_ai_model` |
| Cloud Pub/Sub | Async inference | `google_pubsub_topic` |
| BigQuery | Prediction logging | `google_bigquery_dataset` |
| Cloud Monitoring | Custom metrics | Managed service |

## Configuration

### Terraform Variables
```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
}

variable "gpu_type" {
  description = "GPU accelerator type"
  type        = string
  default     = "nvidia-tesla-t4"  # or nvidia-l4, nvidia-a100-40gb
}

variable "gpu_count" {
  description = "GPUs per node"
  type        = number
  default     = 1
}

variable "gpu_node_count" {
  description = "Number of GPU nodes"
  type        = number
  default     = 1
}
```

### Terraform Resources
```hcl
# GKE Cluster
resource "google_container_cluster" "ml_cluster" {
  name     = var.cluster_name
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
  }
}

# CPU Node Pool (for preprocessing, queue workers)
resource "google_container_node_pool" "cpu_nodes" {
  name       = "cpu-pool"
  location   = var.region
  cluster    = google_container_cluster.ml_cluster.name
  node_count = 2

  autoscaling {
    min_node_count = 1
    max_node_count = 10
  }

  node_config {
    machine_type = "e2-standard-4"

    service_account = google_service_account.gke_sa.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

# GPU Node Pool (for model inference)
resource "google_container_node_pool" "gpu_nodes" {
  name       = "gpu-pool"
  location   = var.region
  cluster    = google_container_cluster.ml_cluster.name
  node_count = var.gpu_node_count

  autoscaling {
    min_node_count = 0
    max_node_count = 5
  }

  node_config {
    machine_type = "n1-standard-4"  # Required for GPU

    guest_accelerator {
      type  = var.gpu_type
      count = var.gpu_count
    }

    service_account = google_service_account.gke_sa.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Taint for GPU-only workloads
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }
}

# Model Storage Bucket
resource "google_storage_bucket" "models" {
  name     = "${var.project_id}-ml-models"
  location = var.region

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}
```

## Model Serving Implementations

### TensorFlow Serving Deployment
```yaml
# tf-serving-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tf-serving
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
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-t4
      tolerations:
        - key: nvidia.com/gpu
          operator: Equal
          value: present
          effect: NoSchedule
      containers:
        - name: tf-serving
          image: tensorflow/serving:latest-gpu
          ports:
            - containerPort: 8501  # REST
            - containerPort: 8500  # gRPC
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: "8Gi"
              cpu: "4"
            requests:
              nvidia.com/gpu: 1
              memory: "4Gi"
              cpu: "2"
          args:
            - "--model_name=my_model"
            - "--model_base_path=gs://${BUCKET}/models/my_model"
            - "--enable_batching=true"
            - "--batching_parameters_file=/config/batching.config"
          volumeMounts:
            - name: config
              mountPath: /config
      volumes:
        - name: config
          configMap:
            name: tf-serving-config
```

### Triton Inference Server Deployment
```yaml
# triton-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triton-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: triton-server
  template:
    metadata:
      labels:
        app: triton-server
    spec:
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-t4
      tolerations:
        - key: nvidia.com/gpu
          operator: Equal
          value: present
          effect: NoSchedule
      containers:
        - name: triton
          image: nvcr.io/nvidia/tritonserver:23.10-py3
          ports:
            - containerPort: 8000  # HTTP
            - containerPort: 8001  # gRPC
            - containerPort: 8002  # Metrics
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: "16Gi"
              cpu: "8"
          args:
            - "tritonserver"
            - "--model-repository=gs://${BUCKET}/triton-models"
            - "--strict-model-config=false"
          livenessProbe:
            httpGet:
              path: /v2/health/live
              port: 8000
          readinessProbe:
            httpGet:
              path: /v2/health/ready
              port: 8000
```

### TorchServe Deployment
```yaml
# torchserve-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: torchserve
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
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-t4
      tolerations:
        - key: nvidia.com/gpu
          operator: Equal
          value: present
          effect: NoSchedule
      initContainers:
        - name: download-model
          image: google/cloud-sdk:slim
          command: ["gsutil", "cp", "-r", "gs://${BUCKET}/models/*", "/models/"]
          volumeMounts:
            - name: model-store
              mountPath: /models
      containers:
        - name: torchserve
          image: pytorch/torchserve:latest-gpu
          ports:
            - containerPort: 8080  # Inference
            - containerPort: 8081  # Management
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: "8Gi"
          command: ["torchserve"]
          args:
            - "--start"
            - "--model-store=/models"
            - "--models=all"
          volumeMounts:
            - name: model-store
              mountPath: /models
      volumes:
        - name: model-store
          emptyDir: {}
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable container.googleapis.com storage.googleapis.com

# Get cluster credentials
gcloud container clusters get-credentials ${CLUSTER_NAME} --region ${REGION}

# Install NVIDIA GPU driver daemonset
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml

# Upload model to GCS
gsutil cp -r ./model gs://${BUCKET}/models/

# Deploy serving infrastructure
kubectl apply -f k8s/

# Check GPU availability
kubectl get nodes -l cloud.google.com/gke-accelerator=nvidia-tesla-t4
```

## Best Practices

### Model Optimization
1. Use ONNX for cross-framework compatibility
2. Apply TensorRT optimization for NVIDIA GPUs
3. Enable dynamic batching for throughput
4. Use quantization (INT8/FP16) where appropriate

### Scaling
1. Use HPA based on custom metrics (inference latency, queue length)
2. Configure GPU autoscaling with appropriate cooldown
3. Pre-warm models to avoid cold start latency
4. Use node auto-provisioning for GPU nodes

### Cost Optimization
1. Use Spot VMs for non-critical inference (70% savings)
2. Scale GPU nodes to zero during off-hours
3. Right-size GPU type for your model
4. Share GPUs with NVIDIA MPS for smaller models

## Cost Breakdown

| GPU Type | On-Demand/hour | Spot/hour | Monthly (24/7) |
|----------|----------------|-----------|----------------|
| T4 | $0.35 | $0.11 | ~$250 |
| L4 | $0.54 | $0.16 | ~$390 |
| A100 40GB | $3.67 | $1.10 | ~$2,640 |
| A100 80GB | $4.82 | $1.45 | ~$3,470 |

### Total Example (T4 cluster)
| Component | Cost |
|-----------|------|
| 2x T4 GPU nodes (Spot) | ~$160/month |
| 2x CPU nodes | ~$100/month |
| GKE management | $73/month |
| Storage (100GB) | ~$2/month |
| **Total** | **~$335/month** |

## Common Mistakes

1. **Not installing GPU drivers**: GPU pods pending indefinitely
2. **Missing tolerations**: Pods not scheduled on GPU nodes
3. **No batching**: Wasting GPU capacity on single requests
4. **Over-provisioning GPUs**: Not right-sizing for model size
5. **No model versioning**: Difficult to rollback bad models
6. **Ignoring cold starts**: First request very slow

## Example Configuration

```yaml
project_name: ml-serving-platform
provider: gcp
region: us-central1
architecture_type: gke_ml_serving

resources:
  - id: cluster
    type: gke_cluster
    name: ml-cluster
    provider: gcp
    config:
      enable_workload_identity: true

  - id: cpu-pool
    type: gke_node_pool
    name: cpu-pool
    provider: gcp
    config:
      cluster: ml-cluster
      machine_type: e2-standard-4
      min_nodes: 1
      max_nodes: 10
    depends_on:
      - cluster

  - id: gpu-pool
    type: gke_node_pool
    name: gpu-pool
    provider: gcp
    config:
      cluster: ml-cluster
      machine_type: n1-standard-4
      gpu_type: nvidia-tesla-t4
      gpu_count: 1
      min_nodes: 0
      max_nodes: 5
      spot: true
    depends_on:
      - cluster

  - id: model-storage
    type: cloud_storage
    name: ml-models
    provider: gcp
    config:
      location: us-central1
      versioning: true
```

## Sources

- [GKE GPU Documentation](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [TensorFlow Serving](https://www.tensorflow.org/tfx/serving/serving_kubernetes)
- [NVIDIA Triton Inference Server](https://github.com/triton-inference-server/server)
- [Vertex AI Prediction](https://cloud.google.com/vertex-ai/docs/predictions/overview)
