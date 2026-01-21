# GCP Pub/Sub Workers

## Overview

Deploy message-driven worker services using Pub/Sub for reliable, scalable event processing. Ideal for asynchronous task processing, event sourcing, microservice communication, and decoupled architectures.

## Detection Signals

Use this template when:
- Message queue patterns detected
- Async processing requirements
- Event-driven architecture
- Microservice communication needs
- Background job processing
- High-throughput data ingestion

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │              Pub/Sub Message Bus                 │
                    │                                                 │
    Publishers ────►│   ┌─────────────────────────────────────────┐   │
    (API, Events)  │   │            Topic: events                 │   │
                    │   └──────────────────┬──────────────────────┘   │
                    │                      │                          │
                    │   ┌──────────────────┼──────────────────────┐   │
                    │   │                  │                      │   │
                    │   ▼                  ▼                      ▼   │
                    │ ┌────────┐      ┌────────┐            ┌────────┐│
                    │ │Sub: A  │      │Sub: B  │            │Sub: DLQ││
                    │ │(push)  │      │(pull)  │            │(errors)││
                    │ └────┬───┘      └────┬───┘            └────────┘│
                    └──────┼───────────────┼──────────────────────────┘
                           │               │
                           ▼               ▼
                    ┌────────────┐  ┌────────────┐
                    │ Cloud Run  │  │ Cloud Run  │
                    │  Worker A  │  │  Worker B  │
                    │  (HTTP)    │  │  (Pull)    │
                    └────────────┘  └────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Pub/Sub Topic | Message channel | `google_pubsub_topic` |
| Pub/Sub Subscription | Message delivery | `google_pubsub_subscription` |
| Cloud Run Service | Worker processing | `google_cloud_run_v2_service` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Dead Letter Topic | Failed messages | `google_pubsub_topic` |
| Cloud Monitoring | Alerting | Managed service |
| BigQuery | Message logging | `google_bigquery_dataset` |
| Cloud Storage | Large payloads | `google_storage_bucket` |

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

variable "topic_name" {
  description = "Pub/Sub topic name"
  type        = string
}

variable "worker_name" {
  description = "Worker service name"
  type        = string
}

variable "delivery_type" {
  description = "push or pull"
  type        = string
  default     = "push"
}
```

### Terraform Resources
```hcl
# Main Topic
resource "google_pubsub_topic" "main" {
  name = var.topic_name

  message_retention_duration = "86400s"  # 24 hours

  # Schema validation (optional)
  schema_settings {
    schema   = google_pubsub_schema.events.id
    encoding = "JSON"
  }
}

# Dead Letter Topic
resource "google_pubsub_topic" "dlq" {
  name = "${var.topic_name}-dlq"

  message_retention_duration = "604800s"  # 7 days
}

# Push Subscription (to Cloud Run)
resource "google_pubsub_subscription" "push" {
  count = var.delivery_type == "push" ? 1 : 0
  name  = "${var.topic_name}-push-sub"
  topic = google_pubsub_topic.main.name

  ack_deadline_seconds = 600  # 10 minutes

  push_config {
    push_endpoint = google_cloud_run_v2_service.worker.uri
    oidc_token {
      service_account_email = google_service_account.pubsub_sa.email
    }
    attributes = {
      x-goog-version = "v1"
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Message ordering (optional)
  enable_message_ordering = false
}

# Pull Subscription (for pull-based workers)
resource "google_pubsub_subscription" "pull" {
  count = var.delivery_type == "pull" ? 1 : 0
  name  = "${var.topic_name}-pull-sub"
  topic = google_pubsub_topic.main.name

  ack_deadline_seconds       = 600
  message_retention_duration = "604800s"

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""  # Never expire
  }
}

# Cloud Run Worker Service
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
        name  = "SUBSCRIPTION_NAME"
        value = var.delivery_type == "pull" ? google_pubsub_subscription.pull[0].name : ""
      }
    }

    scaling {
      min_instance_count = var.delivery_type == "pull" ? 1 : 0
      max_instance_count = 20
    }

    # For push subscriptions
    timeout = "600s"
  }
}

# Service Account for Pub/Sub
resource "google_service_account" "pubsub_sa" {
  account_id   = "${var.worker_name}-pubsub"
  display_name = "Pub/Sub Push Service Account"
}

# IAM: Allow Pub/Sub to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "pubsub_invoker" {
  count    = var.delivery_type == "push" ? 1 : 0
  location = google_cloud_run_v2_service.worker.location
  service  = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_sa.email}"
}

# Schema for message validation
resource "google_pubsub_schema" "events" {
  name       = "${var.topic_name}-schema"
  type       = "AVRO"
  definition = <<EOF
{
  "type": "record",
  "name": "Event",
  "fields": [
    {"name": "event_type", "type": "string"},
    {"name": "timestamp", "type": "string"},
    {"name": "data", "type": {"type": "map", "values": "string"}}
  ]
}
EOF
}
```

## Worker Implementation

### Push Worker (HTTP endpoint)
```python
# main.py
import base64
import json
from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['POST'])
def handle_message():
    """Handle Pub/Sub push message."""
    envelope = request.get_json()

    if not envelope:
        return ('Bad Request: no Pub/Sub message received', 400)

    if 'message' not in envelope:
        return ('Bad Request: invalid Pub/Sub message format', 400)

    pubsub_message = envelope['message']

    # Decode message data
    if 'data' in pubsub_message:
        data = base64.b64decode(pubsub_message['data']).decode('utf-8')
        message = json.loads(data)
    else:
        message = {}

    # Get message attributes
    attributes = pubsub_message.get('attributes', {})
    message_id = pubsub_message.get('messageId')

    print(f"Processing message {message_id}: {message}")

    try:
        # Process the message
        result = process_event(message, attributes)
        return ('OK', 200)
    except Exception as e:
        print(f"Error processing message: {e}")
        # Return error to trigger retry
        return (str(e), 500)

def process_event(message, attributes):
    """Business logic for processing events."""
    event_type = message.get('type')

    if event_type == 'order_created':
        return process_order(message)
    elif event_type == 'user_signed_up':
        return process_signup(message)
    else:
        print(f"Unknown event type: {event_type}")
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Pull Worker (Async processing)
```python
# worker.py
import json
import os
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1

project_id = os.environ['PROJECT_ID']
subscription_name = os.environ['SUBSCRIPTION_NAME']

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(project_id, subscription_name)

def callback(message):
    """Process a single message."""
    print(f"Received message: {message.message_id}")

    try:
        data = json.loads(message.data.decode('utf-8'))
        attributes = dict(message.attributes)

        # Process message
        result = process_event(data, attributes)

        # Acknowledge successful processing
        message.ack()
        print(f"Processed message {message.message_id}")

    except Exception as e:
        print(f"Error processing message {message.message_id}: {e}")
        # Nack to retry later
        message.nack()

def process_event(data, attributes):
    """Business logic."""
    # Your processing logic here
    pass

def main():
    streaming_pull = subscriber.subscribe(
        subscription_path,
        callback=callback,
        flow_control=pubsub_v1.types.FlowControl(
            max_messages=10,  # Process 10 messages concurrently
            max_bytes=10 * 1024 * 1024  # 10MB
        )
    )

    print(f"Listening for messages on {subscription_path}")

    try:
        streaming_pull.result()
    except TimeoutError:
        streaming_pull.cancel()
        streaming_pull.result()

if __name__ == '__main__':
    main()
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable pubsub.googleapis.com run.googleapis.com

# Create topic
gcloud pubsub topics create ${TOPIC_NAME}

# Create subscription (push)
gcloud pubsub subscriptions create ${SUBSCRIPTION_NAME} \
  --topic=${TOPIC_NAME} \
  --push-endpoint=${CLOUD_RUN_URL} \
  --ack-deadline=600 \
  --dead-letter-topic=${DLQ_TOPIC} \
  --max-delivery-attempts=5

# Create subscription (pull)
gcloud pubsub subscriptions create ${SUBSCRIPTION_NAME} \
  --topic=${TOPIC_NAME} \
  --ack-deadline=600 \
  --dead-letter-topic=${DLQ_TOPIC} \
  --max-delivery-attempts=5

# Publish test message
gcloud pubsub topics publish ${TOPIC_NAME} \
  --message='{"type": "test", "data": "hello"}'

# View dead letter messages
gcloud pubsub subscriptions pull ${DLQ_SUBSCRIPTION} --auto-ack
```

## Best Practices

### Message Design
1. Keep messages small (< 10MB, ideally < 1KB)
2. Use attributes for routing metadata
3. Include idempotency keys
4. Use schema validation for data integrity

### Reliability
1. Always configure dead letter queues
2. Set appropriate ack deadlines
3. Implement idempotent message handlers
4. Use exponential backoff for retries

### Performance
1. Batch publish when possible
2. Use flow control for pull subscribers
3. Enable message ordering only when needed
4. Scale workers based on backlog

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Message ingestion | 10 GB/month | $40/TB |
| Message delivery | 10 GB/month | $40/TB |
| Egress | 10 GB/month | Standard rates |
| Seek/Snapshot | - | $0.05/GB/month |

### Example Monthly Costs
| Scale | Messages | Cost |
|-------|----------|------|
| Low (1M, 1KB each) | 1 GB | ~$0 (free tier) |
| Medium (100M, 1KB each) | 100 GB | ~$8 |
| High (1B, 1KB each) | 1 TB | ~$80 |

## Common Mistakes

1. **Not using DLQ**: Lost messages on repeated failures
2. **Short ack deadline**: Messages redelivered while processing
3. **Large messages**: Should use Cloud Storage for large payloads
4. **Ordering without need**: Reduces throughput significantly
5. **Not handling duplicates**: At-least-once delivery means duplicates
6. **Ignoring backlog**: Not monitoring subscription backlog

## Example Configuration

```yaml
project_name: event-processor
provider: gcp
region: us-central1
architecture_type: pubsub_workers

resources:
  - id: events-topic
    type: pubsub_topic
    name: events
    provider: gcp
    config:
      message_retention: "86400s"

  - id: events-dlq
    type: pubsub_topic
    name: events-dlq
    provider: gcp
    config:
      message_retention: "604800s"

  - id: events-subscription
    type: pubsub_subscription
    name: events-push
    provider: gcp
    config:
      topic: events
      delivery_type: push
      push_endpoint: https://worker.run.app
      ack_deadline: 600
      dead_letter_topic: events-dlq
      max_delivery_attempts: 5
    depends_on:
      - events-topic
      - events-dlq

  - id: worker
    type: cloud_run
    name: event-worker
    provider: gcp
    config:
      port: 8080
      memory: 1Gi
      cpu: "2"
      min_instances: 0
      max_instances: 20
      timeout: 600
```

## Sources

- [Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Pub/Sub + Cloud Run](https://cloud.google.com/run/docs/triggering/pubsub-push)
- [Pub/Sub Pricing](https://cloud.google.com/pubsub/pricing)
