# GCP App Engine Standard

## Overview

Deploy applications on App Engine Standard environment for fully managed, auto-scaling PaaS. Ideal for web applications and APIs where you want zero infrastructure management and automatic scaling based on traffic.

## Detection Signals

Use this template when:
- `app.yaml` present in project root
- Standard runtime languages (Python, Node.js, Java, Go, PHP, Ruby)
- Simple web application without custom system dependencies
- Need for automatic scaling without configuration
- Legacy Google App Engine projects

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           App Engine Standard           │
    Internet ──────►│  ┌─────────────────────────────────┐   │
         │         │  │         Auto-scaling             │   │
    Google         │  │  ┌───────┐ ┌───────┐ ┌───────┐   │   │
    Frontend       │  │  │  Inst │ │  Inst │ │  Inst │   │   │
                    │  │  │   1   │ │   2   │ │   N   │   │   │
                    │  │  └───────┘ └───────┘ └───────┘   │   │
                    │  └─────────────────────────────────┘   │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              Cloud SQL          Memcache         Cloud Storage
              (optional)         (built-in)       (static files)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| App Engine Application | App hosting | `google_app_engine_application` |
| App Engine Service | Service version | `google_app_engine_standard_app_version` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud SQL | Relational database | `google_sql_database_instance` |
| Firestore | NoSQL database | `google_firestore_database` |
| Cloud Storage | Static files | `google_storage_bucket` |
| Cloud Tasks | Background jobs | `google_cloud_tasks_queue` |
| Cloud Scheduler | Cron jobs | `google_cloud_scheduler_job` |

## Configuration

### app.yaml (Python)
```yaml
runtime: python311

instance_class: F1

automatic_scaling:
  min_instances: 0
  max_instances: 10
  min_idle_instances: 0
  max_idle_instances: 1
  target_cpu_utilization: 0.65
  target_throughput_utilization: 0.65

env_variables:
  ENV: "production"

handlers:
  - url: /static
    static_dir: static
    secure: always

  - url: /.*
    script: auto
    secure: always

# Cloud SQL connection
beta_settings:
  cloud_sql_instances: "project:region:instance"

# VPC connector for private resources
vpc_access_connector:
  name: "projects/PROJECT_ID/locations/REGION/connectors/CONNECTOR"
```

### app.yaml (Node.js)
```yaml
runtime: nodejs20

instance_class: F2

automatic_scaling:
  min_instances: 0
  max_instances: 10

env_variables:
  NODE_ENV: "production"

handlers:
  - url: /.*
    script: auto
    secure: always
```

### Terraform Resources
```hcl
# App Engine Application (one per project)
resource "google_app_engine_application" "app" {
  project     = var.project_id
  location_id = var.region
}

# App Engine Standard Version
resource "google_app_engine_standard_app_version" "v1" {
  project    = var.project_id
  service    = "default"
  runtime    = "python311"
  version_id = "v1"

  deployment {
    zip {
      source_url = "https://storage.googleapis.com/${google_storage_bucket.source.name}/${google_storage_bucket_object.source.name}"
    }
  }

  entrypoint {
    shell = "gunicorn -b :$PORT main:app"
  }

  env_variables = {
    ENV = "production"
  }

  automatic_scaling {
    min_instances      = 0
    max_instances      = 10
    min_idle_instances = 0
    max_idle_instances = 1

    standard_scheduler_settings {
      target_cpu_utilization        = 0.65
      target_throughput_utilization = 0.65
    }
  }

  delete_service_on_destroy = false
}

# Traffic split (for gradual rollouts)
resource "google_app_engine_service_split_traffic" "split" {
  project = var.project_id
  service = google_app_engine_standard_app_version.v1.service

  migrate_traffic = true

  split {
    shard_by = "IP"
    allocations = {
      (google_app_engine_standard_app_version.v1.version_id) = 1.0
    }
  }
}
```

## Application Structure

### Python (Flask)
```
my-app/
├── app.yaml
├── main.py
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    └── index.html
```

```python
# main.py
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return {'status': 'healthy'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

```
# requirements.txt
Flask==3.0.0
gunicorn==21.2.0
```

### Node.js (Express)
```
my-app/
├── app.yaml
├── app.js
├── package.json
└── public/
    └── index.html
```

```javascript
// app.js
const express = require('express');
const app = express();

app.use(express.static('public'));

app.get('/api/health', (req, res) => {
  res.json({ status: 'healthy' });
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

## Deployment Commands

```bash
# Initialize App Engine (first time only)
gcloud app create --region=${REGION}

# Deploy application
gcloud app deploy app.yaml --project=${PROJECT_ID}

# Deploy with traffic split
gcloud app deploy app.yaml --project=${PROJECT_ID} --no-promote
gcloud app services set-traffic default --splits=v1=0.1,v2=0.9

# View logs
gcloud app logs tail -s default

# Browse application
gcloud app browse

# List versions
gcloud app versions list

# Delete old versions
gcloud app versions delete v1 v2 --service=default
```

## Best Practices

### Performance
1. Use appropriate instance class for workload
2. Configure automatic scaling thresholds
3. Use Memcache for session storage
4. Serve static files from Cloud Storage

### Cost Optimization
1. Set min_instances to 0 for scale-to-zero
2. Use F1 instance class for light workloads
3. Delete unused versions
4. Use Cloud CDN for static content

### Security
1. Enable Identity-Aware Proxy for internal apps
2. Use Cloud SQL Auth Proxy
3. Store secrets in Secret Manager
4. Enable HTTPS-only access

## Instance Classes

| Class | CPU | Memory | Cost/Hour |
|-------|-----|--------|-----------|
| F1 | 600 MHz | 256 MB | $0.05 |
| F2 | 1.2 GHz | 512 MB | $0.10 |
| F4 | 2.4 GHz | 1 GB | $0.20 |
| F4_1G | 2.4 GHz | 2 GB | $0.30 |

## Cost Breakdown

| Traffic | Instance Hours | Monthly Cost |
|---------|----------------|--------------|
| Low (idle) | ~720 F1 | $0 (free tier) |
| Medium | ~720 F2 | $72 |
| High | ~1440 F4 | $288 |

### Free Tier
- 28 instance hours/day for F1
- 9 instance hours/day for B1
- 1 GB Cloud Storage
- 1 GB egress/day

## Common Mistakes

1. **Wrong instance class**: F1 too small for heavy workloads
2. **No warmup requests**: Cold starts affect first users
3. **Ignoring deadlines**: Requests timeout after 60 seconds
4. **Static files in app**: Should use Cloud Storage
5. **Not cleaning old versions**: Accumulating unused deployments
6. **Blocking operations**: Use Cloud Tasks for long jobs

## Example Configuration

```yaml
project_name: my-flask-app
provider: gcp
region: us-central1
architecture_type: app_engine_standard

resources:
  - id: app-engine
    type: app_engine_application
    name: my-flask-app
    provider: gcp
    config:
      location: us-central1

  - id: app-version
    type: app_engine_standard
    name: my-flask-app
    provider: gcp
    config:
      service: default
      runtime: python311
      instance_class: F2
      automatic_scaling:
        min_instances: 0
        max_instances: 10
      env_vars:
        ENV: production
    depends_on:
      - app-engine

  - id: database
    type: cloud_sql
    name: my-flask-app-db
    provider: gcp
    config:
      database_version: POSTGRES_15
      tier: db-f1-micro
```

## Sources

- [App Engine Standard Documentation](https://cloud.google.com/appengine/docs/standard)
- [App Engine Pricing](https://cloud.google.com/appengine/pricing)
- [app.yaml Reference](https://cloud.google.com/appengine/docs/standard/reference/app-yaml)
