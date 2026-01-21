# GCP Dataflow Pipeline

## Overview

Deploy Apache Beam data pipelines on Dataflow for batch and streaming data processing. Ideal for ETL workloads, real-time analytics, data transformation, and large-scale data processing jobs.

## Detection Signals

Use this template when:
- Apache Beam code detected
- Large-scale data transformation needs
- Real-time streaming requirements
- ETL/ELT pipeline patterns
- BigQuery data loading
- Log processing at scale

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Dataflow                              │
                    │                                                         │
  ┌──────────┐      │   ┌─────────────────────────────────────────────────┐   │
  │  Pub/Sub │─────►│   │              Apache Beam Pipeline              │   │
  │  (Stream)│      │   │                                                 │   │
  └──────────┘      │   │  ┌─────┐    ┌──────────┐    ┌─────────────┐    │   │
                    │   │  │Read │───►│Transform │───►│   Write     │    │   │
  ┌──────────┐      │   │  │     │    │ (PTransform)│    │(BigQuery)  │    │   │
  │  Cloud   │─────►│   │  └─────┘    └──────────┘    └─────────────┘    │   │
  │ Storage  │      │   │                                                 │   │
  │  (Batch) │      │   │  Auto-scaling Worker Pool (n workers)          │   │
  └──────────┘      │   └─────────────────────────────────────────────────┘   │
                    │                                                         │
                    └─────────────────────────────────────────────────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                        BigQuery       Cloud Storage    Pub/Sub
                        (Analytics)    (Output files)   (Output events)
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Dataflow Job | Pipeline execution | `google_dataflow_job` |
| Service Account | Worker permissions | `google_service_account` |
| Cloud Storage | Temp/staging files | `google_storage_bucket` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| BigQuery Dataset | Output destination | `google_bigquery_dataset` |
| Pub/Sub Topic | Streaming source/sink | `google_pubsub_topic` |
| VPC Network | Private networking | `google_compute_network` |

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

variable "job_name" {
  description = "Dataflow job name"
  type        = string
}

variable "template_path" {
  description = "Path to Dataflow template"
  type        = string
}

variable "max_workers" {
  description = "Maximum number of workers"
  type        = number
  default     = 10
}

variable "machine_type" {
  description = "Worker machine type"
  type        = string
  default     = "n1-standard-4"
}
```

### Terraform Resources
```hcl
# Service Account for Dataflow
resource "google_service_account" "dataflow_sa" {
  account_id   = "${var.job_name}-dataflow"
  display_name = "Dataflow Service Account"
}

# IAM Roles
resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

resource "google_project_iam_member" "bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# Temp/Staging Bucket
resource "google_storage_bucket" "dataflow_temp" {
  name     = "${var.project_id}-dataflow-temp"
  location = var.region

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

# Batch Dataflow Job
resource "google_dataflow_job" "batch" {
  name              = var.job_name
  template_gcs_path = var.template_path
  temp_gcs_location = "gs://${google_storage_bucket.dataflow_temp.name}/temp"

  parameters = {
    inputFile  = "gs://${var.input_bucket}/*.json"
    outputTable = "${var.project_id}:${var.dataset}.${var.table}"
  }

  max_workers       = var.max_workers
  machine_type      = var.machine_type
  service_account_email = google_service_account.dataflow_sa.email

  on_delete = "cancel"
}

# Streaming Dataflow Job (Flex Template)
resource "google_dataflow_flex_template_job" "streaming" {
  provider                = google-beta
  name                    = "${var.job_name}-streaming"
  container_spec_gcs_path = "gs://${var.template_bucket}/templates/${var.job_name}.json"
  region                  = var.region

  parameters = {
    input_subscription = google_pubsub_subscription.input.id
    output_table       = "${var.project_id}:${var.dataset}.${var.table}"
    temp_location      = "gs://${google_storage_bucket.dataflow_temp.name}/temp"
  }

  service_account_email = google_service_account.dataflow_sa.email

  # Streaming-specific options
  additional_experiments = [
    "enable_streaming_engine"
  ]
}

# BigQuery Dataset
resource "google_bigquery_dataset" "output" {
  dataset_id = var.dataset
  location   = var.region
}

# BigQuery Table
resource "google_bigquery_table" "output" {
  dataset_id = google_bigquery_dataset.output.dataset_id
  table_id   = var.table

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = <<EOF
[
  {"name": "id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "data", "type": "JSON", "mode": "NULLABLE"}
]
EOF
}
```

## Pipeline Implementation

### Batch Pipeline (Python)
```python
# batch_pipeline.py
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions
import json

class ParseJson(beam.DoFn):
    def process(self, element):
        try:
            record = json.loads(element)
            yield {
                'id': record['id'],
                'timestamp': record['timestamp'],
                'value': record.get('value', 0),
                'category': record.get('category', 'unknown')
            }
        except Exception as e:
            # Log bad records
            yield beam.pvalue.TaggedOutput('errors', element)

class TransformData(beam.DoFn):
    def process(self, element):
        # Apply business logic
        element['value_normalized'] = element['value'] / 100
        element['processed_at'] = datetime.utcnow().isoformat()
        yield element

def run(argv=None):
    options = PipelineOptions(argv)
    google_options = options.view_as(GoogleCloudOptions)

    with beam.Pipeline(options=options) as p:
        # Read from GCS
        lines = p | 'ReadFromGCS' >> beam.io.ReadFromText(
            options.input_pattern
        )

        # Parse and transform
        parsed = (
            lines
            | 'ParseJSON' >> beam.ParDo(ParseJson()).with_outputs('errors', main='records')
        )

        transformed = (
            parsed.records
            | 'Transform' >> beam.ParDo(TransformData())
        )

        # Write to BigQuery
        transformed | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
            table=options.output_table,
            schema='id:STRING,timestamp:TIMESTAMP,value:FLOAT,category:STRING,value_normalized:FLOAT,processed_at:TIMESTAMP',
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
        )

        # Write errors for debugging
        parsed.errors | 'WriteErrors' >> beam.io.WriteToText(
            options.error_output
        )

if __name__ == '__main__':
    run()
```

### Streaming Pipeline (Python)
```python
# streaming_pipeline.py
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms.window import FixedWindows
from apache_beam.transforms.trigger import AfterWatermark, AfterCount, Repeatedly
import json

class ParseEvent(beam.DoFn):
    def process(self, element):
        message = json.loads(element.decode('utf-8'))
        yield message

class EnrichEvent(beam.DoFn):
    def process(self, element, timestamp=beam.DoFn.TimestampParam):
        element['processing_timestamp'] = timestamp.to_utc_datetime().isoformat()
        yield element

def run(argv=None):
    options = PipelineOptions(argv)
    options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=options) as p:
        # Read from Pub/Sub
        events = (
            p
            | 'ReadFromPubSub' >> beam.io.ReadFromPubSub(
                subscription=options.input_subscription
            )
            | 'ParseEvents' >> beam.ParDo(ParseEvent())
        )

        # Window and aggregate
        windowed = (
            events
            | 'Window' >> beam.WindowInto(
                FixedWindows(60),  # 1-minute windows
                trigger=Repeatedly(AfterWatermark(early=AfterCount(100))),
                accumulation_mode=beam.transforms.trigger.AccumulationMode.DISCARDING
            )
        )

        # Aggregate by category
        aggregated = (
            windowed
            | 'KeyByCategory' >> beam.Map(lambda x: (x['category'], x['value']))
            | 'SumByCategory' >> beam.CombinePerKey(sum)
            | 'FormatOutput' >> beam.Map(lambda x: {
                'category': x[0],
                'total_value': x[1],
                'window_end': beam.DoFn.WindowParam
            })
        )

        # Write to BigQuery (streaming inserts)
        aggregated | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
            table=options.output_table,
            schema='category:STRING,total_value:FLOAT,window_end:TIMESTAMP',
            method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS
        )

if __name__ == '__main__':
    run()
```

## Deployment Commands

```bash
# Enable APIs
gcloud services enable dataflow.googleapis.com bigquery.googleapis.com

# Run batch job
python batch_pipeline.py \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --runner=DataflowRunner \
  --temp_location=gs://${BUCKET}/temp \
  --input_pattern=gs://${INPUT_BUCKET}/*.json \
  --output_table=${PROJECT_ID}:${DATASET}.${TABLE}

# Run streaming job
python streaming_pipeline.py \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --runner=DataflowRunner \
  --streaming \
  --temp_location=gs://${BUCKET}/temp \
  --input_subscription=projects/${PROJECT_ID}/subscriptions/${SUB} \
  --output_table=${PROJECT_ID}:${DATASET}.${TABLE}

# Create Flex Template
gcloud dataflow flex-template build gs://${BUCKET}/templates/my-pipeline.json \
  --image-gcr-path=${REGION}-docker.pkg.dev/${PROJECT_ID}/dataflow/my-pipeline:latest \
  --sdk-language=PYTHON \
  --flex-template-base-image=PYTHON3 \
  --metadata-file=metadata.json \
  --py-path=. \
  --env=FLEX_TEMPLATE_PYTHON_PY_FILE=pipeline.py

# Run from template
gcloud dataflow flex-template run my-job \
  --template-file-gcs-location=gs://${BUCKET}/templates/my-pipeline.json \
  --region=${REGION} \
  --parameters input_subscription=...,output_table=...
```

## Best Practices

### Pipeline Design
1. Use windowing for streaming aggregations
2. Handle late data with allowed lateness
3. Use side inputs for lookup data
4. Implement dead letter queues for errors

### Performance
1. Enable Streaming Engine for streaming jobs
2. Use appropriate parallelism (num_workers)
3. Optimize shuffle with Dataflow Shuffle
4. Use efficient serialization (Avro over JSON)

### Cost Optimization
1. Use Flexrs (Flexible Resource Scheduling) for batch
2. Right-size workers for your workload
3. Use preemptible VMs for fault-tolerant jobs
4. Enable autoscaling

## Cost Breakdown

| Component | Cost |
|-----------|------|
| vCPU | $0.056/vCPU-hour |
| Memory | $0.003557/GB-hour |
| Streaming Engine | $0.018/unit-hour |
| Shuffle | $0.011/GB shuffled |

### Example Costs
| Job Type | Workers | Duration | Cost |
|----------|---------|----------|------|
| Batch (n1-standard-4, 10 workers, 2 hours) | 10 | 2h | ~$15 |
| Streaming (n1-standard-2, 3 workers, 24h) | 3 | 24h | ~$25/day |

## Common Mistakes

1. **No windowing**: Unbounded PCollections never complete
2. **Large side inputs**: Should be broadcast, not streamed
3. **Hot keys**: Uneven data distribution causes bottlenecks
4. **No error handling**: Pipeline fails on bad records
5. **Over-provisioned**: Too many workers for small jobs
6. **Missing monitoring**: Not tracking job metrics

## Example Configuration

```yaml
project_name: data-pipeline
provider: gcp
region: us-central1
architecture_type: dataflow_pipeline

resources:
  - id: temp-bucket
    type: cloud_storage
    name: data-pipeline-temp
    provider: gcp
    config:
      location: us-central1
      lifecycle_delete_age: 7

  - id: bigquery-dataset
    type: bigquery_dataset
    name: analytics
    provider: gcp
    config:
      location: us-central1

  - id: events-topic
    type: pubsub_topic
    name: events
    provider: gcp
    config:
      message_retention: "86400s"

  - id: events-subscription
    type: pubsub_subscription
    name: events-dataflow
    provider: gcp
    config:
      topic: events
      ack_deadline: 600
    depends_on:
      - events-topic

  - id: streaming-pipeline
    type: dataflow_job
    name: events-processor
    provider: gcp
    config:
      streaming: true
      max_workers: 10
      machine_type: n1-standard-2
      enable_streaming_engine: true
      input_subscription: events-dataflow
      output_table: analytics.events
    depends_on:
      - temp-bucket
      - bigquery-dataset
      - events-subscription
```

## Sources

- [Dataflow Documentation](https://cloud.google.com/dataflow/docs)
- [Apache Beam Programming Guide](https://beam.apache.org/documentation/programming-guide/)
- [Dataflow Pricing](https://cloud.google.com/dataflow/pricing)
