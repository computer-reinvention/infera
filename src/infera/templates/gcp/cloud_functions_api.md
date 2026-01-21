# GCP Cloud Functions API

## Overview

Deploy lightweight serverless APIs using Cloud Functions (2nd gen). Ideal for simple REST endpoints, webhooks, and microservices that don't need full container flexibility. Offers simpler deployment than Cloud Run with automatic scaling.

## Detection Signals

Use this template when:
- Simple API with few endpoints
- Single-file or small codebase
- Event-driven patterns (webhooks, callbacks)
- No Dockerfile (prefer code-first deployment)
- Firebase integration patterns
- functions/ directory structure

## Architecture

```
                    ┌─────────────────────┐
    Internet ──────►│  Cloud Functions    │
                    │  (2nd gen)          │
                    │  HTTP Trigger       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         Firestore       Secret Manager    Cloud Storage
         (NoSQL)         (API keys)        (files)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Function | Serverless compute | `google_cloudfunctions2_function` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Firestore | NoSQL database | `google_firestore_database` |
| Cloud Storage | File storage | `google_storage_bucket` |
| Secret Manager | Sensitive config | `google_secret_manager_secret` |
| Cloud Tasks | Async processing | `google_cloud_tasks_queue` |

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

variable "function_name" {
  description = "Cloud Function name"
  type        = string
}

variable "runtime" {
  description = "Function runtime"
  type        = string
  default     = "python311"  # or nodejs20, go121
}

variable "entry_point" {
  description = "Function entry point"
  type        = string
  default     = "main"
}

variable "memory" {
  description = "Memory allocation (MB)"
  type        = string
  default     = "256M"
}
```

### Terraform Resources
```hcl
# Source code bucket
resource "google_storage_bucket" "function_source" {
  name     = "${var.project_id}-${var.function_name}-source"
  location = var.region

  uniform_bucket_level_access = true
}

# Upload source code
resource "google_storage_bucket_object" "function_zip" {
  name   = "${var.function_name}-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.source.output_path
}

# Cloud Function (2nd gen)
resource "google_cloudfunctions2_function" "api" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = var.runtime
    entry_point = var.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 100
    min_instance_count    = 0
    available_memory      = var.memory
    timeout_seconds       = 60

    environment_variables = {
      ENV = "production"
    }

    # Optional: Secret Manager integration
    secret_environment_variables {
      key        = "API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.api_key.secret_id
      version    = "latest"
    }
  }
}

# IAM for public access
resource "google_cloud_run_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloudfunctions2_function.api.location
  service  = google_cloudfunctions2_function.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "function_url" {
  value = google_cloudfunctions2_function.api.service_config[0].uri
}
```

## Function Implementation

### Python
```python
# main.py
import functions_framework
from flask import jsonify

@functions_framework.http
def main(request):
    """HTTP Cloud Function entry point."""

    # Handle CORS
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # Route handling
    path = request.path

    if path == '/api/hello':
        return jsonify({'message': 'Hello from Cloud Functions!'}), 200, headers

    if path == '/api/users' and request.method == 'POST':
        data = request.get_json()
        # Process data...
        return jsonify({'created': True}), 201, headers

    return jsonify({'error': 'Not found'}), 404, headers
```

### Node.js
```javascript
// index.js
const functions = require('@google-cloud/functions-framework');

functions.http('main', (req, res) => {
  // Handle CORS
  res.set('Access-Control-Allow-Origin', '*');

  if (req.method === 'OPTIONS') {
    res.set('Access-Control-Allow-Methods', 'GET, POST');
    res.set('Access-Control-Allow-Headers', 'Content-Type');
    res.status(204).send('');
    return;
  }

  // Route handling
  const path = req.path;

  if (path === '/api/hello') {
    res.json({ message: 'Hello from Cloud Functions!' });
    return;
  }

  res.status(404).json({ error: 'Not found' });
});
```

### requirements.txt (Python)
```
functions-framework==3.*
flask==3.*
google-cloud-firestore==2.*
```

### package.json (Node.js)
```json
{
  "name": "my-function",
  "version": "1.0.0",
  "main": "index.js",
  "dependencies": {
    "@google-cloud/functions-framework": "^3.0.0",
    "@google-cloud/firestore": "^7.0.0"
  }
}
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable cloudfunctions.googleapis.com cloudbuild.googleapis.com

# Deploy function
gcloud functions deploy ${FUNCTION_NAME} \
  --gen2 \
  --runtime python311 \
  --region ${REGION} \
  --source . \
  --entry-point main \
  --trigger-http \
  --allow-unauthenticated \
  --memory 256MB \
  --max-instances 100

# View logs
gcloud functions logs read ${FUNCTION_NAME} --region ${REGION}

# Test locally
functions-framework --target=main --debug
```

## Best Practices

### Function Design
1. Keep functions small and focused
2. Use a router library for multiple endpoints (Flask, Express)
3. Implement proper error handling
4. Return appropriate HTTP status codes

### Performance
1. Minimize cold starts with min_instances
2. Use global variables for connection pooling
3. Lazy-load heavy dependencies
4. Set appropriate memory for your workload

### Security
1. Validate all input data
2. Use Secret Manager for API keys
3. Implement rate limiting
4. Enable Cloud Run authentication for internal APIs

## Cost Breakdown

| Tier | Invocations | Memory | Price |
|------|-------------|--------|-------|
| Free | 2M/month | 400K GB-sec | $0 |
| Compute | $0.40/million | $0.0000025/GB-sec | Variable |
| Networking | - | - | $0.12/GB egress |

### Example Costs
| Traffic | Monthly Cost |
|---------|--------------|
| 1M requests/mo, 256MB | ~$0 (free tier) |
| 10M requests/mo, 256MB | ~$10 |
| 100M requests/mo, 512MB | ~$80 |

## Common Mistakes

1. **Not handling CORS**: Browser requests fail without proper headers
2. **Timeout too short**: Default 60s may not be enough
3. **Cold start impact**: Not warming functions for latency-sensitive APIs
4. **Missing error handling**: Unhandled exceptions return 500
5. **Large dependencies**: Slow cold starts from heavy packages
6. **No logging**: Debugging without structured logs

## Example Configuration

```yaml
project_name: my-api-functions
provider: gcp
region: us-central1
architecture_type: cloud_functions

resources:
  - id: api-function
    type: cloud_function
    name: my-api
    provider: gcp
    config:
      runtime: python311
      entry_point: main
      memory: 256M
      timeout: 60
      max_instances: 100
      min_instances: 0
      allow_unauthenticated: true
      env_vars:
        ENV: production

  - id: firestore
    type: firestore
    name: my-api-db
    provider: gcp
    config:
      location: us-central1
      type: FIRESTORE_NATIVE
```

## Sources

- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Cloud Functions 2nd Gen](https://cloud.google.com/functions/docs/concepts/version-comparison)
- [Functions Framework](https://cloud.google.com/functions/docs/functions-framework)
