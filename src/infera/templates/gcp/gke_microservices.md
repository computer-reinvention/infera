# GCP GKE Microservices

## Overview

Deploy containerized microservices on Google Kubernetes Engine (GKE) with service mesh, automatic scaling, and managed Kubernetes infrastructure. Ideal for complex applications with multiple services requiring fine-grained orchestration.

## Detection Signals

Use this template when:
- Multiple services/microservices in codebase
- Kubernetes manifests (k8s/, deployments/, charts/)
- docker-compose.yml with multiple services
- Service mesh patterns (Istio config)
- Complex networking requirements
- Need for StatefulSets or DaemonSets

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │              GKE Cluster                 │
    Internet ─────────►│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
         │             │  │Service A│  │Service B│  │Service C│  │
    Cloud Load         │  │  (API)  │  │(Worker) │  │  (DB)   │  │
    Balancer           │  └────┬────┘  └────┬────┘  └────┬────┘  │
                        │       │           │           │        │
                        │  ┌────┴───────────┴───────────┴────┐   │
                        │  │         Service Mesh (Istio)     │   │
                        │  └─────────────────────────────────┘   │
                        └─────────────────────────────────────────┘
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                        Cloud SQL              Memorystore
                        (PostgreSQL)           (Redis)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| GKE Cluster | Container orchestration | `google_container_cluster` |
| Node Pool | Compute nodes | `google_container_node_pool` |
| Artifact Registry | Container images | `google_artifact_registry_repository` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud SQL | Managed database | `google_sql_database_instance` |
| Memorystore | Redis cache | `google_redis_instance` |
| Cloud Load Balancer | External traffic | `google_compute_global_address` |
| Cloud NAT | Outbound internet | `google_compute_router_nat` |
| Cloud Armor | DDoS protection | `google_compute_security_policy` |
| Istio | Service mesh | Installed via add-on |

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

variable "node_count" {
  description = "Number of nodes per zone"
  type        = number
  default     = 1
}

variable "machine_type" {
  description = "Node machine type"
  type        = string
  default     = "e2-medium"
}

variable "enable_istio" {
  description = "Enable Istio service mesh"
  type        = bool
  default     = false
}
```

### Terraform Resources
```hcl
# VPC Network
resource "google_compute_network" "vpc" {
  name                    = "${var.cluster_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.cluster_name}-subnet"
  ip_cidr_range = "10.0.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.region

  # Use VPC-native cluster
  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  # Enable Workload Identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Addons
  addons_config {
    http_load_balancing {
      disabled = false
    }

    horizontal_pod_autoscaling {
      disabled = false
    }

    network_policy_config {
      disabled = !var.enable_istio
    }
  }

  # Maintenance window
  maintenance_policy {
    daily_maintenance_window {
      start_time = "03:00"
    }
  }
}

# Node Pool
resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.cluster_name}-node-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = var.node_count

  autoscaling {
    min_node_count = 1
    max_node_count = 10
  }

  node_config {
    machine_type = var.machine_type

    # Google recommends custom service accounts
    service_account = google_service_account.gke_sa.email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      env = "production"
    }

    tags = ["gke-node", var.cluster_name]
  }
}

# Service Account for GKE nodes
resource "google_service_account" "gke_sa" {
  account_id   = "${var.cluster_name}-gke-sa"
  display_name = "GKE Service Account"
}

# Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "${var.cluster_name}-repo"
  format        = "DOCKER"
}
```

## Kubernetes Manifests

### Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app: api-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      serviceAccountName: api-service-sa
      containers:
        - name: api
          image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: url
```

### Service
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
spec:
  selector:
    app: api-service
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
---
# Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "api-ip"
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /*
            pathType: ImplementationSpecific
            backend:
              service:
                name: api-service
                port:
                  number: 80
```

### HorizontalPodAutoscaler
```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
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

## Deployment Commands

```bash
# Enable APIs
gcloud services enable container.googleapis.com artifactregistry.googleapis.com

# Get cluster credentials
gcloud container clusters get-credentials ${CLUSTER_NAME} --region ${REGION}

# Build and push images
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest

# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods
kubectl get services
kubectl get ingress
```

## Best Practices

### Cluster Configuration
1. Use regional clusters for high availability
2. Enable Workload Identity for secure GCP access
3. Use VPC-native clusters for better networking
4. Configure node auto-provisioning for dynamic scaling

### Security
1. Use GKE Workload Identity instead of service account keys
2. Enable Binary Authorization for image verification
3. Use Network Policies to restrict pod communication
4. Regularly update cluster and node versions

### Monitoring
1. Enable GKE monitoring and logging
2. Use Cloud Operations for GKE
3. Set up alerts for resource utilization
4. Implement distributed tracing with Cloud Trace

## Cost Breakdown

| Component | e2-medium (3 nodes) | e2-standard-4 (3 nodes) |
|-----------|---------------------|-------------------------|
| GKE Management | $0 (Autopilot) / $73 (Standard) | Same |
| Compute | ~$75/month | ~$300/month |
| Load Balancer | ~$18/month | ~$18/month |
| Networking | Variable | Variable |
| **Total** | **~$93-170/month** | **~$318-400/month** |

### Cost Optimization Tips
- Use Spot VMs for non-critical workloads (70% savings)
- Right-size node pools based on actual usage
- Use cluster autoscaling to scale down during off-hours
- Consider GKE Autopilot for simplified management

## Common Mistakes

1. **Over-provisioning nodes**: Start small and scale up
2. **Missing resource limits**: Pods without limits can starve others
3. **No health checks**: Unhealthy pods receive traffic
4. **Single-zone cluster**: No high availability
5. **Default node pool**: Use custom node pools for flexibility
6. **Ignoring costs**: GKE management fees add up

## Example Configuration

```yaml
project_name: microservices-platform
provider: gcp
region: us-central1
architecture_type: gke_microservices

resources:
  - id: vpc
    type: vpc_network
    name: microservices-vpc
    provider: gcp
    config:
      auto_create_subnetworks: false

  - id: subnet
    type: vpc_subnet
    name: microservices-subnet
    provider: gcp
    config:
      ip_cidr_range: "10.0.0.0/16"
      pods_range: "10.1.0.0/16"
      services_range: "10.2.0.0/20"
    depends_on:
      - vpc

  - id: cluster
    type: gke_cluster
    name: microservices-cluster
    provider: gcp
    config:
      network: microservices-vpc
      subnetwork: microservices-subnet
      enable_workload_identity: true
      enable_http_load_balancing: true
    depends_on:
      - subnet

  - id: node-pool
    type: gke_node_pool
    name: default-pool
    provider: gcp
    config:
      cluster: microservices-cluster
      machine_type: e2-medium
      min_nodes: 1
      max_nodes: 10
    depends_on:
      - cluster

  - id: registry
    type: artifact_registry
    name: microservices-repo
    provider: gcp
    config:
      format: DOCKER
      location: us-central1
```

## Sources

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE Best Practices](https://cloud.google.com/kubernetes-engine/docs/best-practices)
- [GKE Cost Optimization](https://cloud.google.com/kubernetes-engine/docs/best-practices/cost-optimization)
