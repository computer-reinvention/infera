# GCP Cloud Tasks Background Jobs

## Overview

Deploy reliable background job processing using Cloud Tasks for scheduled, rate-limited, and retryable task execution. Ideal for email sending, webhook delivery, async API calls, and any work that can be deferred.

## Detection Signals

Use this template when:
- Async job processing patterns
- Rate-limited external API calls
- Scheduled task execution
- Webhook delivery requirements
- Task queue patterns (Celery, Sidekiq concepts)
- Deferred processing needs

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │              Cloud Tasks                         │
                    │                                                 │
    API Request ───►│   ┌─────────────────────────────────────────┐   │
         │         │   │            Task Queue                    │   │
    Create Task    │   │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │   │
                    │   │  │Task1│ │Task2│ │Task3│ │TaskN│        │   │
                    │   │  └─────┘ └─────┘ └─────┘ └─────┘        │   │
                    │   │                                         │   │
                    │   │  Rate: 100/sec  │  Retry: 5x           │   │
                    │   └─────────────────┼───────────────────────┘   │
                    └─────────────────────┼───────────────────────────┘
                                          │ HTTP dispatch
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │              Cloud Run Worker                    │
                    │                                                 │
                    │   ┌─────────────────────────────────────────┐   │
                    │   │  POST /tasks/send-email                 │   │
                    │   │  POST /tasks/process-webhook            │   │
                    │   │  POST /tasks/sync-data                  │   │
                    │   └─────────────────────────────────────────┘   │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Tasks Queue | Task scheduling | `google_cloud_tasks_queue` |
| Cloud Run Service | Task handler | `google_cloud_run_v2_service` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud Scheduler | Periodic tasks | `google_cloud_scheduler_job` |
| Secret Manager | API keys | `google_secret_manager_secret` |
| Cloud Monitoring | Alerting | Managed service |

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

variable "queue_name" {
  description = "Cloud Tasks queue name"
  type        = string
}

variable "worker_name" {
  description = "Worker service name"
  type        = string
}

variable "max_dispatches_per_second" {
  description = "Max task dispatch rate"
  type        = number
  default     = 100
}
```

### Terraform Resources
```hcl
# Cloud Tasks Queue
resource "google_cloud_tasks_queue" "main" {
  name     = var.queue_name
  location = var.region

  rate_limits {
    max_dispatches_per_second = var.max_dispatches_per_second
    max_concurrent_dispatches = 100
  }

  retry_config {
    max_attempts       = 5
    max_retry_duration = "3600s"
    min_backoff        = "10s"
    max_backoff        = "600s"
    max_doublings      = 4
  }

  stackdriver_logging_config {
    sampling_ratio = 1.0
  }
}

# Service Account for Cloud Tasks
resource "google_service_account" "tasks_sa" {
  account_id   = "${var.queue_name}-tasks"
  display_name = "Cloud Tasks Service Account"
}

# IAM: Allow Cloud Tasks to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "tasks_invoker" {
  location = google_cloud_run_v2_service.worker.location
  service  = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks_sa.email}"
}

# Cloud Run Worker
resource "google_cloud_run_v2_service" "worker" {
  name     = var.worker_name
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.worker_name}-repo/${var.worker_name}:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "QUEUE_NAME"
        value = google_cloud_tasks_queue.main.name
      }
    }

    scaling {
      min_instance_count = 1  # Keep warm for tasks
      max_instance_count = 20
    }

    timeout = "600s"
  }
}

# Cloud Scheduler for periodic tasks
resource "google_cloud_scheduler_job" "daily_cleanup" {
  name        = "daily-cleanup"
  description = "Run cleanup task daily"
  schedule    = "0 3 * * *"  # 3 AM daily
  time_zone   = "America/Los_Angeles"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.worker.uri}/tasks/cleanup"

    oidc_token {
      service_account_email = google_service_account.tasks_sa.email
    }
  }

  retry_config {
    retry_count = 3
  }
}

# Additional queue for high-priority tasks
resource "google_cloud_tasks_queue" "priority" {
  name     = "${var.queue_name}-priority"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 500
    max_concurrent_dispatches = 200
  }

  retry_config {
    max_attempts = 10
    min_backoff  = "5s"
    max_backoff  = "300s"
  }
}
```

## Worker Implementation

### Task Handler (Python)
```python
# main.py
from flask import Flask, request, jsonify
from google.cloud import tasks_v2
import json
import os

app = Flask(__name__)
client = tasks_v2.CloudTasksClient()

PROJECT_ID = os.environ['PROJECT_ID']
LOCATION = os.environ.get('LOCATION', 'us-central1')
QUEUE_NAME = os.environ['QUEUE_NAME']

# Task creation helper
def create_task(task_type: str, payload: dict, delay_seconds: int = 0):
    """Create a Cloud Task."""
    parent = client.queue_path(PROJECT_ID, LOCATION, QUEUE_NAME)

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{os.environ['SERVICE_URL']}/tasks/{task_type}",
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(payload).encode(),
            'oidc_token': {
                'service_account_email': os.environ['SERVICE_ACCOUNT']
            }
        }
    }

    if delay_seconds > 0:
        from datetime import datetime, timedelta
        from google.protobuf import timestamp_pb2

        d = datetime.utcnow() + timedelta(seconds=delay_seconds)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)
        task['schedule_time'] = timestamp

    response = client.create_task(parent=parent, task=task)
    return response.name

# Task handlers
@app.route('/tasks/send-email', methods=['POST'])
def handle_send_email():
    """Handle email sending task."""
    data = request.get_json()

    try:
        send_email(
            to=data['to'],
            subject=data['subject'],
            body=data['body']
        )
        return jsonify({'status': 'sent'}), 200
    except Exception as e:
        print(f"Email failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/process-webhook', methods=['POST'])
def handle_webhook():
    """Handle webhook delivery task."""
    data = request.get_json()

    try:
        deliver_webhook(
            url=data['url'],
            payload=data['payload'],
            headers=data.get('headers', {})
        )
        return jsonify({'status': 'delivered'}), 200
    except Exception as e:
        print(f"Webhook failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/sync-data', methods=['POST'])
def handle_sync():
    """Handle data sync task."""
    data = request.get_json()

    try:
        result = sync_external_system(data['entity_id'])
        return jsonify({'status': 'synced', 'result': result}), 200
    except Exception as e:
        print(f"Sync failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tasks/cleanup', methods=['POST'])
def handle_cleanup():
    """Handle scheduled cleanup task."""
    try:
        deleted_count = cleanup_old_records()
        return jsonify({'status': 'complete', 'deleted': deleted_count}), 200
    except Exception as e:
        print(f"Cleanup failed: {e}")
        return jsonify({'error': str(e)}), 500

# Helper functions
def send_email(to, subject, body):
    """Send email via SendGrid/SES/etc."""
    # Implementation
    pass

def deliver_webhook(url, payload, headers):
    """Deliver webhook with retry."""
    import requests
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

def sync_external_system(entity_id):
    """Sync data with external system."""
    # Implementation
    pass

def cleanup_old_records():
    """Delete old records."""
    # Implementation
    return 100

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Creating Tasks from API
```python
# api.py - In your main API service
from google.cloud import tasks_v2
import json

client = tasks_v2.CloudTasksClient()

def queue_email(to: str, subject: str, body: str):
    """Queue an email for sending."""
    parent = client.queue_path(PROJECT_ID, LOCATION, 'email-queue')

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{WORKER_URL}/tasks/send-email",
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'to': to,
                'subject': subject,
                'body': body
            }).encode(),
            'oidc_token': {
                'service_account_email': SERVICE_ACCOUNT
            }
        }
    }

    return client.create_task(parent=parent, task=task)

def queue_webhook(url: str, payload: dict, delay_seconds: int = 0):
    """Queue a webhook for delivery."""
    parent = client.queue_path(PROJECT_ID, LOCATION, 'webhook-queue')

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{WORKER_URL}/tasks/process-webhook",
            'body': json.dumps({
                'url': url,
                'payload': payload
            }).encode()
        }
    }

    if delay_seconds:
        from datetime import datetime, timedelta
        from google.protobuf import timestamp_pb2

        d = datetime.utcnow() + timedelta(seconds=delay_seconds)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)
        task['schedule_time'] = timestamp

    return client.create_task(parent=parent, task=task)
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable cloudtasks.googleapis.com run.googleapis.com cloudscheduler.googleapis.com

# Create queue
gcloud tasks queues create ${QUEUE_NAME} \
  --location=${REGION} \
  --max-dispatches-per-second=100 \
  --max-concurrent-dispatches=100 \
  --max-attempts=5 \
  --min-backoff=10s \
  --max-backoff=600s

# Create task manually
gcloud tasks create-http-task \
  --queue=${QUEUE_NAME} \
  --url=${WORKER_URL}/tasks/test \
  --method=POST \
  --body-content='{"test": true}'

# List tasks in queue
gcloud tasks list --queue=${QUEUE_NAME} --location=${REGION}

# Pause/resume queue
gcloud tasks queues pause ${QUEUE_NAME} --location=${REGION}
gcloud tasks queues resume ${QUEUE_NAME} --location=${REGION}
```

## Best Practices

### Task Design
1. Keep task payloads small (< 100KB)
2. Make handlers idempotent
3. Include request IDs for deduplication
4. Store large data in Cloud Storage, pass URLs

### Queue Configuration
1. Set appropriate rate limits for external APIs
2. Configure retry with exponential backoff
3. Use separate queues for different priorities
4. Monitor queue depth and latency

### Reliability
1. Return appropriate HTTP status codes
2. 2xx = success (task complete)
3. 4xx = permanent failure (don't retry)
4. 5xx = temporary failure (retry)

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Task operations | 1M/month | $0.40/million |
| Cloud Scheduler | 3 jobs free | $0.10/job/month |

### Example Monthly Costs
| Scale | Tasks | Cost |
|-------|-------|------|
| Low (100k tasks) | Free | $0 |
| Medium (10M tasks) | 10M | ~$4 |
| High (100M tasks) | 100M | ~$40 |

## Common Mistakes

1. **Not idempotent**: Duplicate task execution causes issues
2. **Wrong status codes**: 4xx prevents needed retries
3. **Too short timeout**: Tasks killed mid-processing
4. **No rate limiting**: Overwhelming external APIs
5. **Large payloads**: Should use Cloud Storage for data
6. **Missing monitoring**: Not tracking failed tasks

## Example Configuration

```yaml
project_name: task-processor
provider: gcp
region: us-central1
architecture_type: cloud_tasks_jobs

resources:
  - id: email-queue
    type: cloud_tasks_queue
    name: email-queue
    provider: gcp
    config:
      max_dispatches_per_second: 50
      max_concurrent_dispatches: 50
      max_attempts: 5
      min_backoff: 10s
      max_backoff: 600s

  - id: webhook-queue
    type: cloud_tasks_queue
    name: webhook-queue
    provider: gcp
    config:
      max_dispatches_per_second: 100
      max_concurrent_dispatches: 100
      max_attempts: 10
      min_backoff: 5s
      max_backoff: 300s

  - id: worker
    type: cloud_run
    name: task-worker
    provider: gcp
    config:
      port: 8080
      memory: 1Gi
      cpu: "2"
      min_instances: 1
      max_instances: 20
      timeout: 600
      allow_unauthenticated: false

  - id: daily-cleanup
    type: cloud_scheduler
    name: daily-cleanup
    provider: gcp
    config:
      schedule: "0 3 * * *"
      target_url: https://task-worker.run.app/tasks/cleanup
      time_zone: America/Los_Angeles
```

## Sources

- [Cloud Tasks Documentation](https://cloud.google.com/tasks/docs)
- [Cloud Tasks + Cloud Run](https://cloud.google.com/tasks/docs/creating-http-target-tasks)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
