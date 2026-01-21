# GCP Cloud Functions Event-Driven

## Overview

Deploy event-driven serverless functions using Cloud Functions with Pub/Sub, Cloud Storage, or Firestore triggers. Ideal for background processing, data pipelines, and reactive architectures that respond to events.

## Detection Signals

Use this template when:
- Pub/Sub usage patterns detected
- Cloud Storage event handlers
- Firestore triggers or listeners
- Background processing requirements
- Message queue consumers
- ETL or data transformation patterns

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Pub/Sub   │────►│   Cloud     │────►│   Downstream    │
│   Topic     │     │  Functions  │     │   Services      │
└─────────────┘     └─────────────┘     └─────────────────┘
       ▲                   │
       │                   ▼
┌──────┴──────┐     ┌─────────────┐
│  Publishers │     │  Firestore  │
│  (API, etc) │     │  / Storage  │
└─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Cloud     │────►│   Cloud     │────►│   Data          │
│   Storage   │     │  Functions  │     │   Processing    │
│   Bucket    │     │  (Trigger)  │     │   (BigQuery)    │
└─────────────┘     └─────────────┘     └─────────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Function | Event processor | `google_cloudfunctions2_function` |
| Pub/Sub Topic | Message queue | `google_pubsub_topic` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Pub/Sub Subscription | Pull/Push delivery | `google_pubsub_subscription` |
| Cloud Storage | File triggers | `google_storage_bucket` |
| Firestore | Document triggers | `google_firestore_database` |
| Dead Letter Topic | Failed messages | `google_pubsub_topic` |
| BigQuery | Data warehouse | `google_bigquery_dataset` |

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

variable "trigger_type" {
  description = "Event trigger type"
  type        = string
  default     = "pubsub"  # pubsub, storage, firestore
}

variable "pubsub_topic" {
  description = "Pub/Sub topic name"
  type        = string
  default     = ""
}
```

### Pub/Sub Triggered Function
```hcl
# Pub/Sub Topic
resource "google_pubsub_topic" "main" {
  name = var.pubsub_topic

  message_retention_duration = "86600s"  # 24 hours
}

# Dead Letter Topic
resource "google_pubsub_topic" "dlq" {
  name = "${var.pubsub_topic}-dlq"
}

# Cloud Function with Pub/Sub trigger
resource "google_cloudfunctions2_function" "event_processor" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = "python311"
    entry_point = "process_message"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    max_instance_count = 100
    min_instance_count = 0
    available_memory   = "512M"
    timeout_seconds    = 540  # 9 minutes max for Pub/Sub

    environment_variables = {
      PROJECT_ID = var.project_id
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.main.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}
```

### Cloud Storage Triggered Function
```hcl
# Storage Bucket with notifications
resource "google_storage_bucket" "source" {
  name     = "${var.project_id}-${var.function_name}-source"
  location = var.region
}

# Cloud Function with Storage trigger
resource "google_cloudfunctions2_function" "storage_processor" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = "python311"
    entry_point = "process_file"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    max_instance_count = 100
    available_memory   = "1Gi"
    timeout_seconds    = 540
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.function_sa.email

    event_filters {
      attribute = "bucket"
      value     = google_storage_bucket.source.name
    }
  }
}
```

## Function Implementation

### Pub/Sub Handler (Python)
```python
# main.py
import base64
import json
import functions_framework
from google.cloud import firestore
from google.cloud import bigquery

db = firestore.Client()
bq = bigquery.Client()

@functions_framework.cloud_event
def process_message(cloud_event):
    """Process Pub/Sub message."""

    # Decode message
    message_data = base64.b64decode(cloud_event.data["message"]["data"])
    message = json.loads(message_data)

    print(f"Processing message: {message}")

    try:
        # Process the event
        result = handle_event(message)

        # Store result
        db.collection('processed_events').add({
            'message_id': cloud_event.data["message"]["messageId"],
            'result': result,
            'processed_at': firestore.SERVER_TIMESTAMP
        })

        return 'OK'

    except Exception as e:
        print(f"Error processing message: {e}")
        raise  # Retry the message

def handle_event(message):
    """Business logic for event processing."""
    event_type = message.get('type')

    if event_type == 'user_signup':
        return process_signup(message)
    elif event_type == 'order_placed':
        return process_order(message)
    else:
        return {'status': 'unknown_event'}
```

### Cloud Storage Handler (Python)
```python
# main.py
import functions_framework
from google.cloud import storage
from google.cloud import bigquery

storage_client = storage.Client()
bq_client = bigquery.Client()

@functions_framework.cloud_event
def process_file(cloud_event):
    """Process uploaded file."""

    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"Processing file: gs://{bucket_name}/{file_name}")

    # Skip non-data files
    if not file_name.endswith('.csv'):
        print(f"Skipping non-CSV file: {file_name}")
        return 'SKIPPED'

    try:
        # Download and process file
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        content = blob.download_as_text()

        # Load to BigQuery
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
        )

        uri = f"gs://{bucket_name}/{file_name}"
        table_id = f"{PROJECT_ID}.dataset.table"

        load_job = bq_client.load_table_from_uri(
            uri, table_id, job_config=job_config
        )
        load_job.result()  # Wait for completion

        # Move to processed folder
        new_name = f"processed/{file_name}"
        bucket.rename_blob(blob, new_name)

        return 'OK'

    except Exception as e:
        print(f"Error processing file: {e}")
        raise
```

### Firestore Trigger (Node.js)
```javascript
// index.js
const functions = require('@google-cloud/functions-framework');
const { Firestore } = require('@google-cloud/firestore');

const db = new Firestore();

functions.cloudEvent('onUserCreate', async (cloudEvent) => {
  const firestoreData = cloudEvent.data;

  // Extract document path
  const resourceName = firestoreData.value?.name;
  const pathParts = resourceName.split('/documents/')[1].split('/');
  const collection = pathParts[0];
  const docId = pathParts[1];

  // Get document data
  const userData = firestoreData.value?.fields;

  console.log(`New user created: ${docId}`);

  // Send welcome email, update analytics, etc.
  await db.collection('user_events').add({
    userId: docId,
    event: 'signup',
    timestamp: new Date()
  });
});
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable \
  cloudfunctions.googleapis.com \
  pubsub.googleapis.com \
  eventarc.googleapis.com \
  cloudbuild.googleapis.com

# Create Pub/Sub topic
gcloud pubsub topics create ${TOPIC_NAME}

# Deploy Pub/Sub triggered function
gcloud functions deploy ${FUNCTION_NAME} \
  --gen2 \
  --runtime python311 \
  --region ${REGION} \
  --source . \
  --entry-point process_message \
  --trigger-topic ${TOPIC_NAME} \
  --memory 512MB \
  --max-instances 100 \
  --retry

# Deploy Storage triggered function
gcloud functions deploy ${FUNCTION_NAME} \
  --gen2 \
  --runtime python311 \
  --region ${REGION} \
  --source . \
  --entry-point process_file \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${BUCKET_NAME}" \
  --memory 1Gi \
  --max-instances 100

# Publish test message
gcloud pubsub topics publish ${TOPIC_NAME} \
  --message '{"type": "test", "data": "hello"}'
```

## Best Practices

### Message Processing
1. Make functions idempotent (handle retries)
2. Use dead letter queues for failed messages
3. Set appropriate timeout based on processing time
4. Batch process when possible for efficiency

### Error Handling
1. Implement exponential backoff for retries
2. Log all errors with context
3. Use structured logging for debugging
4. Monitor failed invocations

### Performance
1. Initialize clients outside handler (reuse connections)
2. Use async operations when possible
3. Set appropriate memory for your workload
4. Consider using batch processing for high throughput

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Cloud Functions | 2M invocations | $0.40/million |
| Pub/Sub | 10GB/month | $40/TB |
| Cloud Storage | 5GB | $0.02/GB |
| Eventarc | - | $0.50/million events |

### Example Monthly Costs
| Scale | Invocations | Cost |
|-------|-------------|------|
| Low | 1M/month | ~$0 (free tier) |
| Medium | 10M/month | ~$20 |
| High | 100M/month | ~$150 |

## Common Mistakes

1. **Not idempotent**: Processing same message multiple times
2. **Missing dead letter queue**: Lost messages on repeated failures
3. **Timeout too short**: Background jobs failing mid-process
4. **No error tracking**: Silent failures without alerts
5. **Ordering assumptions**: Pub/Sub doesn't guarantee order
6. **Memory leaks**: Not cleaning up resources in long-running functions

## Example Configuration

```yaml
project_name: event-processor
provider: gcp
region: us-central1
architecture_type: event_driven

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

  - id: event-processor
    type: cloud_function
    name: event-processor
    provider: gcp
    config:
      runtime: python311
      entry_point: process_message
      memory: 512M
      timeout: 540
      max_instances: 100
      trigger_type: pubsub
      trigger_topic: events
      retry_policy: RETRY_POLICY_RETRY
    depends_on:
      - events-topic
```

## Sources

- [Cloud Functions Triggers](https://cloud.google.com/functions/docs/calling)
- [Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Eventarc Documentation](https://cloud.google.com/eventarc/docs)
