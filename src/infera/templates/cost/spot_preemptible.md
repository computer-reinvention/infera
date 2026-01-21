# Spot & Preemptible Instances: Cost Optimization Guide

## Overview

Spot instances (AWS) and preemptible VMs (GCP) offer 60-90% discounts compared to on-demand pricing in exchange for the possibility of interruption. This guide covers strategies to reliably use these instances for production workloads.

### When to Use
- Stateless workloads (containers, serverless backends)
- Batch processing and data pipelines
- CI/CD build runners
- Development and testing environments
- Machine learning training jobs
- Any fault-tolerant, checkpointable workload

### When NOT to Use
- Single-instance stateful applications
- Databases (use reserved instances instead)
- Workloads without graceful shutdown handling
- Real-time systems requiring 100% availability
- Legacy applications that can't handle restarts

## Pricing Comparison

### GCP Preemptible/Spot VMs

| Machine Type | On-Demand | Spot | Savings |
|--------------|-----------|------|---------|
| e2-micro | $6.11/mo | $1.83/mo | 70% |
| e2-medium | $24.46/mo | $7.34/mo | 70% |
| e2-standard-4 | $97.83/mo | $29.35/mo | 70% |
| n2-standard-8 | $311.90/mo | $74.86/mo | 76% |
| n2-highmem-16 | $831.72/mo | $199.61/mo | 76% |
| c2-standard-60 | $2,522.88/mo | $680.23/mo | 73% |

### AWS Spot Instances

| Instance Type | On-Demand | Spot (avg) | Savings |
|---------------|-----------|------------|---------|
| t3.micro | $7.59/mo | $2.28/mo | 70% |
| t3.medium | $30.37/mo | $9.11/mo | 70% |
| m5.xlarge | $140.16/mo | $42.05/mo | 70% |
| c5.2xlarge | $248.20/mo | $59.57/mo | 76% |
| r5.4xlarge | $732.48/mo | $153.82/mo | 79% |
| p3.2xlarge | $2,203.20/mo | $661.00/mo | 70% |

## Architecture Patterns

### Pattern 1: Kubernetes Spot Node Pools

```
┌─────────────────────────────────────────────────────────┐
│                    GKE/EKS Cluster                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  On-Demand Pool (System)    Spot Pool (Workloads)       │
│  ┌──────────────────┐       ┌──────────────────┐        │
│  │ ┌──────┐ ┌──────┐│       │ ┌──────┐ ┌──────┐│        │
│  │ │ Node │ │ Node ││       │ │ Node │ │ Node ││        │
│  │ │  1   │ │  2   ││       │ │  S1  │ │  S2  ││        │
│  │ └──────┘ └──────┘│       │ └──────┘ └──────┘│        │
│  │   System Pods    │       │  Application Pods │        │
│  │   (CoreDNS, etc) │       │  (tolerations)    │        │
│  └──────────────────┘       └──────────────────┘        │
│                                                          │
│  Cost: $200/mo              Cost: $60/mo (70% off)      │
└─────────────────────────────────────────────────────────┘
```

**GKE with Spot Node Pools:**
```hcl
# Terraform for GKE Spot nodes
resource "google_container_cluster" "primary" {
  name     = "production-cluster"
  location = "us-central1"

  # Small on-demand node pool for system components
  node_pool {
    name       = "system"
    node_count = 2

    node_config {
      machine_type = "e2-medium"

      # Taint to prevent workloads
      taint {
        key    = "CriticalAddonsOnly"
        value  = "true"
        effect = "PREFER_NO_SCHEDULE"
      }
    }
  }
}

# Spot node pool for workloads
resource "google_container_node_pool" "spot" {
  name       = "spot-pool"
  cluster    = google_container_cluster.primary.name
  location   = "us-central1"

  autoscaling {
    min_node_count = 0
    max_node_count = 20
  }

  node_config {
    machine_type = "e2-standard-4"
    spot         = true  # Enable Spot VMs

    # Label for pod scheduling
    labels = {
      "cloud.google.com/gke-spot" = "true"
    }

    # Taint so pods must explicitly tolerate
    taint {
      key    = "cloud.google.com/gke-spot"
      value  = "true"
      effect = "NO_SCHEDULE"
    }
  }
}
```

**Kubernetes Deployment with Spot Tolerations:**
```yaml
# deployment.yaml - Schedule on Spot nodes
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      # Tolerate Spot node taint
      tolerations:
        - key: "cloud.google.com/gke-spot"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"

      # Prefer Spot nodes
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              preference:
                matchExpressions:
                  - key: cloud.google.com/gke-spot
                    operator: In
                    values:
                      - "true"

      # Spread across nodes for availability
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: api-server

      # Graceful termination
      terminationGracePeriodSeconds: 30

      containers:
        - name: api
          image: gcr.io/project/api:latest
          ports:
            - containerPort: 8080

          # Handle SIGTERM for graceful shutdown
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 5"]

          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
```

### Pattern 2: AWS ECS with Spot Capacity Providers

```hcl
# ECS Cluster with Spot capacity
resource "aws_ecs_cluster" "main" {
  name = "production"

  capacity_providers = [
    aws_ecs_capacity_provider.spot.name,
    aws_ecs_capacity_provider.on_demand.name,
  ]

  default_capacity_provider_strategy {
    # Prefer Spot (70% of tasks)
    capacity_provider = aws_ecs_capacity_provider.spot.name
    weight            = 70
    base              = 0
  }

  default_capacity_provider_strategy {
    # Fallback to on-demand (30%)
    capacity_provider = aws_ecs_capacity_provider.on_demand.name
    weight            = 30
    base              = 2  # Minimum 2 on-demand
  }
}

# Spot capacity provider
resource "aws_ecs_capacity_provider" "spot" {
  name = "spot"

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

# Spot Auto Scaling Group
resource "aws_autoscaling_group" "spot" {
  name                = "ecs-spot"
  vpc_zone_identifier = var.private_subnet_ids
  min_size            = 0
  max_size            = 20
  desired_capacity    = 2

  # Mixed instances for better availability
  mixed_instances_policy {
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.ecs.id
        version            = "$Latest"
      }

      # Multiple instance types for better Spot availability
      override {
        instance_type = "m5.large"
      }
      override {
        instance_type = "m5a.large"
      }
      override {
        instance_type = "m4.large"
      }
      override {
        instance_type = "t3.large"
      }
    }

    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0  # 100% Spot
      spot_allocation_strategy                 = "capacity-optimized"
    }
  }

  # Capacity rebalancing for Spot interruptions
  capacity_rebalance = true

  tag {
    key                 = "AmazonECSManaged"
    value               = true
    propagate_at_launch = true
  }
}
```

### Pattern 3: Batch Processing on Spot

```python
# batch_processor.py - Checkpointing for Spot interruptions
import boto3
import signal
import json
from datetime import datetime

class SpotAwareBatchProcessor:
    def __init__(self, job_id: str, checkpoint_bucket: str):
        self.job_id = job_id
        self.checkpoint_bucket = checkpoint_bucket
        self.s3 = boto3.client('s3')
        self.interrupted = False

        # Handle Spot interruption warning
        signal.signal(signal.SIGTERM, self.handle_interruption)

    def handle_interruption(self, signum, frame):
        """Called when Spot instance is being terminated."""
        print("Received termination signal, saving checkpoint...")
        self.interrupted = True
        self.save_checkpoint()

    def save_checkpoint(self):
        """Save current progress to S3."""
        checkpoint = {
            'job_id': self.job_id,
            'processed_count': self.processed_count,
            'last_item_id': self.last_item_id,
            'timestamp': datetime.utcnow().isoformat(),
        }

        self.s3.put_object(
            Bucket=self.checkpoint_bucket,
            Key=f'checkpoints/{self.job_id}.json',
            Body=json.dumps(checkpoint),
        )
        print(f"Checkpoint saved: {checkpoint}")

    def load_checkpoint(self) -> dict | None:
        """Load previous checkpoint if exists."""
        try:
            response = self.s3.get_object(
                Bucket=self.checkpoint_bucket,
                Key=f'checkpoints/{self.job_id}.json',
            )
            return json.loads(response['Body'].read())
        except self.s3.exceptions.NoSuchKey:
            return None

    def process(self, items: list):
        """Process items with checkpointing."""
        # Resume from checkpoint
        checkpoint = self.load_checkpoint()
        start_index = 0

        if checkpoint:
            start_index = checkpoint['processed_count']
            print(f"Resuming from checkpoint: {start_index} items processed")

        self.processed_count = start_index
        self.last_item_id = None

        for i, item in enumerate(items[start_index:], start=start_index):
            if self.interrupted:
                break

            # Process item
            self.process_item(item)

            self.processed_count = i + 1
            self.last_item_id = item['id']

            # Periodic checkpoint every 100 items
            if self.processed_count % 100 == 0:
                self.save_checkpoint()

        # Final checkpoint
        self.save_checkpoint()
        print(f"Completed: {self.processed_count}/{len(items)} items")
```

```yaml
# AWS Batch job definition for Spot
Resources:
  BatchJobDefinition:
    Type: AWS::Batch::JobDefinition
    Properties:
      Type: container
      JobDefinitionName: spot-batch-job
      RetryStrategy:
        Attempts: 3  # Retry on Spot interruption
      Timeout:
        AttemptDurationSeconds: 3600
      ContainerProperties:
        Image: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/batch:latest
        Vcpus: 4
        Memory: 8192
        Command:
          - python
          - batch_processor.py
          - --job-id
          - Ref::jobId
        Environment:
          - Name: CHECKPOINT_BUCKET
            Value: !Ref CheckpointBucket

  SpotComputeEnvironment:
    Type: AWS::Batch::ComputeEnvironment
    Properties:
      Type: MANAGED
      ComputeResources:
        Type: SPOT
        BidPercentage: 80  # Max 80% of on-demand price
        AllocationStrategy: SPOT_CAPACITY_OPTIMIZED
        MinvCpus: 0
        MaxvCpus: 256
        InstanceTypes:
          - optimal
        Subnets: !Ref PrivateSubnets
        SecurityGroupIds:
          - !Ref BatchSecurityGroup
        InstanceRole: !GetAtt BatchInstanceRole.Arn
        SpotIamFleetRole: !GetAtt SpotFleetRole.Arn
```

### Pattern 4: CI/CD Runners on Spot

```hcl
# GitHub Actions self-hosted runners on Spot
resource "google_compute_instance_template" "runner" {
  name_prefix  = "github-runner-"
  machine_type = "e2-standard-4"

  scheduling {
    preemptible       = true
    automatic_restart = false
  }

  disk {
    source_image = "ubuntu-os-cloud/ubuntu-2204-lts"
    disk_size_gb = 100
    disk_type    = "pd-ssd"
  }

  network_interface {
    network = var.network
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    # Install GitHub Actions runner
    mkdir -p /opt/actions-runner && cd /opt/actions-runner

    curl -o actions-runner-linux-x64.tar.gz -L \
      https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

    tar xzf actions-runner-linux-x64.tar.gz

    # Configure runner
    ./config.sh --url https://github.com/${var.org}/${var.repo} \
      --token ${var.runner_token} \
      --labels spot,linux \
      --unattended \
      --ephemeral  # Self-destruct after one job

    # Run
    ./run.sh
  EOF

  service_account {
    scopes = ["cloud-platform"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Managed instance group for auto-scaling
resource "google_compute_instance_group_manager" "runners" {
  name               = "github-runners"
  base_instance_name = "runner"
  zone               = "us-central1-a"

  version {
    instance_template = google_compute_instance_template.runner.id
  }

  target_size = 0  # Scale via autoscaler

  update_policy {
    type           = "PROACTIVE"
    minimal_action = "REPLACE"
  }
}

resource "google_compute_autoscaler" "runners" {
  name   = "github-runners-autoscaler"
  zone   = "us-central1-a"
  target = google_compute_instance_group_manager.runners.id

  autoscaling_policy {
    max_replicas = 10
    min_replicas = 0

    # Scale based on custom metric (queued jobs)
    metric {
      name   = "custom.googleapis.com/github/queued_jobs"
      target = 1
      type   = "GAUGE"
    }
  }
}
```

## Interruption Handling

### GCP Preemptible/Spot VM Handling

```go
// main.go - Handle preemption in Go application
package main

import (
    "context"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "cloud.google.com/go/compute/metadata"
)

func main() {
    ctx, cancel := context.WithCancel(context.Background())

    // Check for preemption via metadata
    go watchPreemption(ctx, cancel)

    // Handle SIGTERM
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGTERM)

    server := &http.Server{Addr: ":8080"}

    go func() {
        select {
        case <-sigChan:
            log.Println("Received SIGTERM, shutting down...")
        case <-ctx.Done():
            log.Println("Preemption detected, shutting down...")
        }

        // Graceful shutdown with timeout
        shutdownCtx, _ := context.WithTimeout(context.Background(), 25*time.Second)
        server.Shutdown(shutdownCtx)
    }()

    log.Println("Server starting...")
    server.ListenAndServe()
}

func watchPreemption(ctx context.Context, cancel context.CancelFunc) {
    // GCP provides 30 seconds warning via metadata
    client := metadata.NewClient(&http.Client{})

    for {
        select {
        case <-ctx.Done():
            return
        default:
            // Poll maintenance event (blocking with wait_for_change)
            _, err := client.Get("instance/maintenance-event?wait_for_change=true")
            if err == nil {
                log.Println("Maintenance event detected!")
                cancel()
                return
            }
        }
    }
}
```

### AWS Spot Interruption Handling

```typescript
// spot-handler.ts - EC2 Spot interruption handler
import { EC2Client, DescribeInstanceStatusCommand } from '@aws-sdk/client-ec2';
import axios from 'axios';

const METADATA_URL = 'http://169.254.169.254/latest/meta-data';

interface SpotInterruptionNotice {
  action: 'terminate' | 'stop' | 'hibernate';
  time: string;
}

export async function watchSpotInterruption(
  onInterrupt: () => Promise<void>
): Promise<void> {
  const checkInterval = 5000; // 5 seconds

  while (true) {
    try {
      // Check instance action (2-minute warning)
      const response = await axios.get<SpotInterruptionNotice>(
        `${METADATA_URL}/spot/instance-action`,
        { timeout: 1000 }
      );

      if (response.data) {
        console.log(`Spot interruption notice: ${JSON.stringify(response.data)}`);
        await onInterrupt();
        return;
      }
    } catch (error: any) {
      // 404 means no interruption scheduled
      if (error.response?.status !== 404) {
        console.error('Error checking spot status:', error.message);
      }
    }

    await new Promise(resolve => setTimeout(resolve, checkInterval));
  }
}

// Usage in application
async function main() {
  const server = createServer();

  // Start watching for interruption
  watchSpotInterruption(async () => {
    console.log('Graceful shutdown initiated...');

    // Stop accepting new requests
    server.close();

    // Drain existing connections
    await drainConnections();

    // Save state/checkpoint
    await saveState();

    // Deregister from load balancer
    await deregisterFromALB();

    process.exit(0);
  });

  server.listen(8080);
}
```

## Cost Optimization Strategies

### Multi-Zone Diversification

```hcl
# Use multiple zones for better Spot availability
resource "aws_autoscaling_group" "spot_diverse" {
  name                = "spot-diverse"
  min_size            = 3
  max_size            = 10
  vpc_zone_identifier = var.multi_az_subnets  # Multiple AZs

  mixed_instances_policy {
    instances_distribution {
      spot_allocation_strategy = "capacity-optimized-prioritized"
      spot_instance_pools      = 0  # Use all available pools
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.app.id
      }

      # Prioritized by cost-performance
      override {
        instance_type     = "m5.xlarge"
        weighted_capacity = "4"
      }
      override {
        instance_type     = "m5a.xlarge"
        weighted_capacity = "4"
      }
      override {
        instance_type     = "m5n.xlarge"
        weighted_capacity = "4"
      }
      override {
        instance_type     = "m4.xlarge"
        weighted_capacity = "4"
      }
      override {
        instance_type     = "c5.xlarge"
        weighted_capacity = "4"
      }
    }
  }
}
```

### Savings Summary

```
┌─────────────────────────────────────────────────────────┐
│               Monthly Cost Comparison                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Workload: 10-node Kubernetes cluster                   │
│  Instance: e2-standard-4 (4 vCPU, 16GB)                │
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │ On-Demand                                  │         │
│  │ 10 × $97.83 = $978.30/month               │         │
│  └────────────────────────────────────────────┘         │
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │ 100% Spot                                  │         │
│  │ 10 × $29.35 = $293.50/month               │         │
│  │ Savings: $684.80 (70%)                    │         │
│  └────────────────────────────────────────────┘         │
│                                                          │
│  ┌────────────────────────────────────────────┐         │
│  │ Hybrid (20% On-Demand / 80% Spot)          │         │
│  │ 2 × $97.83 + 8 × $29.35 = $430.46/month   │         │
│  │ Savings: $547.84 (56%)                    │         │
│  └────────────────────────────────────────────┘         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Best Practices

### 1. Always Use Multiple Instance Types
```yaml
# BAD: Single instance type
instance_types:
  - m5.large

# GOOD: Multiple similar types
instance_types:
  - m5.large    # Intel
  - m5a.large   # AMD
  - m5n.large   # Network optimized
  - m4.large    # Previous gen
  - t3.large    # Burstable
```

### 2. Implement Health Checks
```yaml
# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3

# Prevents traffic during termination
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 10"]
```

### 3. Use Pod Disruption Budgets
```yaml
# Ensure minimum availability during interruptions
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2  # Always keep 2 pods running
  selector:
    matchLabels:
      app: api-server
```

## Example Configuration

```yaml
# infera.yaml - Spot instance configuration
name: my-app
provider: gcp

compute:
  strategy: spot_optimized

  # Spot configuration
  spot:
    enabled: true
    fallback_to_on_demand: true
    on_demand_base: 2  # Minimum on-demand instances

  # Instance diversification
  instance_types:
    - e2-standard-4
    - e2-standard-8
    - n2-standard-4

  # Interruption handling
  interruption:
    graceful_shutdown_seconds: 25
    checkpoint_enabled: true
    checkpoint_storage: gs://my-bucket/checkpoints

kubernetes:
  node_pools:
    - name: system
      spot: false
      min_nodes: 2
      max_nodes: 3

    - name: workloads
      spot: true
      min_nodes: 0
      max_nodes: 20
      taints:
        - key: cloud.google.com/gke-spot
          value: "true"
          effect: NoSchedule
```

## Sources

- [GCP Spot VMs](https://cloud.google.com/compute/docs/instances/spot)
- [AWS Spot Instances](https://aws.amazon.com/ec2/spot/)
- [GKE Spot Node Pools](https://cloud.google.com/kubernetes-engine/docs/concepts/spot-vms)
- [EKS Spot Best Practices](https://aws.github.io/aws-eks-best-practices/cost_optimization/spot/)
- [Spot Instance Advisor](https://aws.amazon.com/ec2/spot/instance-advisor/)
- [GCP Preemptible VM Best Practices](https://cloud.google.com/compute/docs/instances/preemptible)
