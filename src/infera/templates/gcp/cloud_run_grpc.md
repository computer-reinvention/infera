# GCP Cloud Run gRPC Service

## Overview

Deploy high-performance gRPC microservices on Cloud Run with HTTP/2 support, automatic scaling, and built-in load balancing. Ideal for internal service-to-service communication, mobile backends, and high-throughput APIs.

## Detection Signals

Use this template when:
- `.proto` files in the project
- `grpcio`, `grpc` dependencies detected
- `@grpc/grpc-js` in package.json
- gRPC server implementation patterns
- Service mesh or microservice architecture

## Architecture

```
                                    ┌─────────────────┐
    External ──────► Load Balancer ─┤  Cloud Run      │
    (gRPC-Web)         (HTTP/2)    │  gRPC Service   │
                                    └────────┬────────┘
                                             │ gRPC
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
              Cloud Run              Cloud Run               Cloud SQL
              Service A              Service B               (shared DB)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Run Service | gRPC hosting | `google_cloud_run_v2_service` |
| Artifact Registry | Docker images | `google_artifact_registry_repository` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Load Balancer | External gRPC | `google_compute_global_address` |
| Cloud Endpoints | API management | `google_endpoints_service` |
| Cloud Armor | DDoS protection | `google_compute_security_policy` |
| VPC Connector | Internal network | `google_vpc_access_connector` |

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

variable "service_name" {
  description = "gRPC service name"
  type        = string
}

variable "grpc_port" {
  description = "gRPC server port"
  type        = number
  default     = 50051
}
```

### Terraform Resources
```hcl
# Cloud Run gRPC Service
resource "google_cloud_run_v2_service" "grpc" {
  name     = var.service_name
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}-repo/${var.service_name}:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      ports {
        container_port = var.grpc_port
        name           = "h2c"  # HTTP/2 cleartext for gRPC
      }

      env {
        name  = "GRPC_PORT"
        value = tostring(var.grpc_port)
      }
    }

    scaling {
      min_instance_count = 1  # Recommended for gRPC
      max_instance_count = 20
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# For external gRPC access, add Load Balancer
resource "google_compute_global_address" "grpc_ip" {
  count = var.enable_external_access ? 1 : 0
  name  = "${var.service_name}-ip"
}

resource "google_compute_global_forwarding_rule" "grpc" {
  count                 = var.enable_external_access ? 1 : 0
  name                  = "${var.service_name}-forwarding"
  target                = google_compute_target_https_proxy.grpc[0].id
  port_range            = "443"
  ip_address            = google_compute_global_address.grpc_ip[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
```

## gRPC Service Implementation

### Python (grpcio)
```python
# server.py
import grpc
from concurrent import futures
import os

def serve():
    port = os.environ.get('GRPC_PORT', '50051')
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ]
    )
    # Add your service
    # my_service_pb2_grpc.add_MyServiceServicer_to_server(MyService(), server)

    server.add_insecure_port(f'[::]:{port}')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
```

### Node.js (@grpc/grpc-js)
```javascript
// server.js
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const PORT = process.env.GRPC_PORT || 50051;

const server = new grpc.Server();
// Add your service implementation

server.bindAsync(
  `0.0.0.0:${PORT}`,
  grpc.ServerCredentials.createInsecure(),
  (err, port) => {
    if (err) throw err;
    console.log(`gRPC server running on port ${port}`);
  }
);
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate protobuf code
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. *.proto

ENV GRPC_PORT=50051
EXPOSE 50051

CMD ["python", "server.py"]
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# Build and push
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest

# Deploy with HTTP/2
gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}-repo/${SERVICE_NAME}:latest \
  --region ${REGION} \
  --port 50051 \
  --use-http2 \
  --min-instances 1 \
  --max-instances 20 \
  --memory 1Gi \
  --cpu 2
```

## Best Practices

### gRPC Configuration
1. Use `h2c` port name for HTTP/2 cleartext
2. Configure appropriate message size limits
3. Implement health checking with gRPC health protocol
4. Use deadlines/timeouts for all RPC calls

### Performance
1. Set `min_instances: 1` to avoid cold start latency
2. Use streaming for large data transfers
3. Implement connection pooling in clients
4. Enable gRPC keepalive for long-lived connections

### Security
1. Use Cloud Run authentication for internal services
2. Implement gRPC interceptors for authentication
3. Use Cloud Endpoints for external API management
4. Enable mTLS for service-to-service communication

## Cost Breakdown

| Traffic Level | Requests/Day | Monthly Cost |
|--------------|--------------|--------------|
| Low | 100k | $15-30 |
| Medium | 1M | $50-100 |
| High | 10M | $200-400 |

### Cost Factors
- gRPC maintains persistent connections (higher memory)
- HTTP/2 multiplexing reduces connection overhead
- Minimum instances recommended (higher baseline cost)

## Common Mistakes

1. **Not using h2c port**: Cloud Run defaults to HTTP/1.1
2. **Cold start latency**: gRPC connections are slow to establish
3. **Missing health checks**: Use gRPC health checking protocol
4. **Large messages**: Not configuring max message size
5. **No deadlines**: Requests hanging indefinitely
6. **Ignoring backpressure**: Not handling slow consumers

## Example Configuration

```yaml
project_name: my-grpc-service
provider: gcp
region: us-central1
architecture_type: grpc_service

resources:
  - id: registry
    type: artifact_registry
    name: my-grpc-service-repo
    provider: gcp
    config:
      format: DOCKER
      location: us-central1

  - id: grpc-service
    type: cloud_run
    name: my-grpc-service
    provider: gcp
    config:
      port: 50051
      http2: true
      memory: 1Gi
      cpu: "2"
      min_instances: 1
      max_instances: 20
      concurrency: 100
      allow_unauthenticated: false
      env_vars:
        GRPC_PORT: "50051"
    depends_on:
      - registry
```

## Sources

- [Cloud Run gRPC](https://cloud.google.com/run/docs/triggering/grpc)
- [gRPC Best Practices](https://grpc.io/docs/guides/performance/)
- [HTTP/2 on Cloud Run](https://cloud.google.com/run/docs/configuring/http2)
