# Streaming Data / Real-Time Analytics

## Overview
Streaming data architectures process data continuously as it arrives, enabling real-time analytics, dashboards, and event-driven systems. Essential for applications requiring immediate insights from high-volume data.

**Use when:**
- Real-time dashboards and monitoring
- Event-driven architectures
- Log aggregation and analysis
- IoT data processing
- Fraud detection
- Live metrics and alerts

**Don't use when:**
- Batch processing is sufficient
- Data volume is low
- Latency of hours is acceptable
- Simple analytics with periodic reports

## Detection Signals

```
Files:
- kafka.*, kinesis.*, pubsub.*
- flink-conf.yaml, beam/
- streaming/, pipeline/

Dependencies:
- kafkajs, @google-cloud/pubsub
- apache-beam, flink
- spark-streaming

Code Patterns:
- consumer.subscribe(), stream.pipe()
- KafkaConsumer, KinesisClient
- window(), aggregate()
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Streaming Data Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Data Sources                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │  Apps   │  │   IoT   │  │  Logs   │  │ Events  │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          └────────────┴──────┬─────┴────────────┘                │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                  Message Broker / Stream                   │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │      Kafka / Pub/Sub / Kinesis / EventHub           │  │  │
│  │  │                                                      │  │  │
│  │  │  Topic: events    Topic: logs    Topic: metrics     │  │  │
│  │  │  [═══════════]    [═══════════]  [═══════════]      │  │  │
│  │  └──────────────────────┬──────────────────────────────┘  │  │
│  └─────────────────────────┼─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐  │
│  │                  Stream Processing                         │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │       Flink / Spark Streaming / Dataflow            │  │  │
│  │  │                                                      │  │  │
│  │  │  • Filter & Transform                               │  │  │
│  │  │  • Window Aggregations (tumbling, sliding)          │  │  │
│  │  │  • Join Streams                                     │  │  │
│  │  │  • Pattern Detection                                │  │  │
│  │  └──────────────────────┬──────────────────────────────┘  │  │
│  └─────────────────────────┼─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐  │
│  │                    Data Sinks                              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │ BigQuery │  │  Redis   │  │  Alerts  │  │Real-time │  │  │
│  │  │ /Redshift│  │  (cache) │  │(PagerDuty)│ │Dashboard │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Kafka (MSK/Confluent) | Pub/Sub | Kinesis | EventHub |
|---------|----------------------|---------|---------|----------|
| **Managed** | Yes | Yes | Yes | Yes |
| **Latency** | ~10ms | ~100ms | ~200ms | ~200ms |
| **Retention** | Unlimited | 31 days | 7 days | 90 days |
| **Throughput** | Very High | High | High | High |
| **Ordering** | Per partition | Optional | Per shard | Per partition |
| **Cost** | $$$$ | $$ | $$$ | $$$ |

## Google Cloud Pub/Sub + Dataflow

### Terraform Configuration

```hcl
# pubsub_dataflow.tf

# Pub/Sub Topic
resource "google_pubsub_topic" "events" {
  name = "${var.project_name}-events"

  message_retention_duration = "604800s"  # 7 days
}

# Dead letter topic
resource "google_pubsub_topic" "events_dlq" {
  name = "${var.project_name}-events-dlq"
}

# Subscription with dead letter
resource "google_pubsub_subscription" "events_sub" {
  name  = "${var.project_name}-events-sub"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Enable exactly-once delivery
  enable_exactly_once_delivery = true
}

# BigQuery dataset for analytics
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "${replace(var.project_name, "-", "_")}_analytics"
  location   = var.region
}

# BigQuery table for events
resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "events"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["event_type", "user_id"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "REQUIRED" },
    { name = "user_id", type = "STRING", mode = "NULLABLE" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "properties", type = "JSON", mode = "NULLABLE" },
  ])
}

# Dataflow job for stream processing
resource "google_dataflow_flex_template_job" "events_pipeline" {
  name                    = "${var.project_name}-events-pipeline"
  region                  = var.region
  container_spec_gcs_path = "gs://${google_storage_bucket.dataflow.name}/templates/events-pipeline.json"

  parameters = {
    inputSubscription = google_pubsub_subscription.events_sub.id
    outputTable       = "${var.project_id}:${google_bigquery_dataset.analytics.dataset_id}.${google_bigquery_table.events.table_id}"
  }

  on_delete = "drain"
}
```

### Dataflow Pipeline (Python/Apache Beam)

```python
# pipeline.py
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.io.gcp.pubsub import ReadFromPubSub
from apache_beam.io.gcp.bigquery import WriteToBigQuery
import json
from datetime import datetime

class ParseEvent(beam.DoFn):
    def process(self, element):
        try:
            data = json.loads(element.decode('utf-8'))
            yield {
                'event_id': data.get('id'),
                'event_type': data.get('type'),
                'user_id': data.get('user_id'),
                'timestamp': datetime.utcnow().isoformat(),
                'properties': json.dumps(data.get('properties', {})),
            }
        except Exception as e:
            # Send to dead letter
            yield beam.pvalue.TaggedOutput('dead_letter', element)

class WindowedAggregation(beam.DoFn):
    def process(self, element, window=beam.DoFn.WindowParam):
        window_start = window.start.to_utc_datetime().isoformat()
        window_end = window.end.to_utc_datetime().isoformat()

        yield {
            'event_type': element[0],
            'count': element[1],
            'window_start': window_start,
            'window_end': window_end,
        }

def run():
    options = PipelineOptions([
        '--streaming',
        '--runner=DataflowRunner',
        '--project=my-project',
        '--region=us-central1',
        '--temp_location=gs://my-bucket/temp',
    ])

    with beam.Pipeline(options=options) as p:
        # Read from Pub/Sub
        events = (
            p
            | 'Read Events' >> ReadFromPubSub(
                subscription='projects/my-project/subscriptions/events-sub'
            )
            | 'Parse Events' >> beam.ParDo(ParseEvent()).with_outputs('dead_letter', main='events')
        )

        # Write raw events to BigQuery
        events.events | 'Write to BigQuery' >> WriteToBigQuery(
            'my-project:analytics.events',
            schema='event_id:STRING,event_type:STRING,user_id:STRING,timestamp:TIMESTAMP,properties:JSON',
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
        )

        # Windowed aggregation (1 minute windows)
        (
            events.events
            | 'Extract Type' >> beam.Map(lambda x: (x['event_type'], 1))
            | 'Window' >> beam.WindowInto(beam.window.FixedWindows(60))
            | 'Count by Type' >> beam.CombinePerKey(sum)
            | 'Format Aggregation' >> beam.ParDo(WindowedAggregation())
            | 'Write Aggregations' >> WriteToBigQuery(
                'my-project:analytics.event_counts',
                schema='event_type:STRING,count:INTEGER,window_start:TIMESTAMP,window_end:TIMESTAMP',
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            )
        )

        # Write dead letters
        events.dead_letter | 'Write Dead Letters' >> beam.io.WriteToText(
            'gs://my-bucket/dead-letters/events'
        )

if __name__ == '__main__':
    run()
```

## AWS Kinesis + Lambda

### Terraform Configuration

```hcl
# kinesis_lambda.tf

# Kinesis Data Stream
resource "aws_kinesis_stream" "events" {
  name             = "${var.project_name}-events"
  shard_count      = var.shard_count
  retention_period = 168  # 7 days

  stream_mode_details {
    stream_mode = "ON_DEMAND"  # Auto-scaling
  }

  encryption_type = "KMS"
  kms_key_id      = aws_kms_key.kinesis.id
}

# Lambda for stream processing
resource "aws_lambda_function" "stream_processor" {
  filename         = data.archive_file.processor.output_path
  function_name    = "${var.project_name}-stream-processor"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.process"
  runtime          = "nodejs18.x"
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = {
      TIMESTREAM_DATABASE = aws_timestreamwrite_database.metrics.database_name
      TIMESTREAM_TABLE    = aws_timestreamwrite_table.events.table_name
    }
  }
}

# Kinesis trigger for Lambda
resource "aws_lambda_event_source_mapping" "kinesis_trigger" {
  event_source_arn  = aws_kinesis_stream.events.arn
  function_name     = aws_lambda_function.stream_processor.arn
  starting_position = "LATEST"

  batch_size                         = 100
  maximum_batching_window_in_seconds = 5
  parallelization_factor             = 10

  # Bisect on error for better error isolation
  bisect_batch_on_function_error = true

  # Retry configuration
  maximum_retry_attempts = 3

  destination_config {
    on_failure {
      destination_arn = aws_sqs_queue.dlq.arn
    }
  }
}

# Timestream for time-series data
resource "aws_timestreamwrite_database" "metrics" {
  database_name = "${var.project_name}-metrics"
}

resource "aws_timestreamwrite_table" "events" {
  database_name = aws_timestreamwrite_database.metrics.database_name
  table_name    = "events"

  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 365
  }
}
```

### Lambda Handler

```typescript
// handler.ts
import { KinesisStreamHandler, KinesisStreamRecord } from 'aws-lambda';
import { TimestreamWriteClient, WriteRecordsCommand } from '@aws-sdk/client-timestream-write';

const timestream = new TimestreamWriteClient({});

interface Event {
  id: string;
  type: string;
  userId: string;
  timestamp: number;
  properties: Record<string, any>;
}

export const process: KinesisStreamHandler = async (event) => {
  const records: any[] = [];

  for (const record of event.Records) {
    try {
      const payload = Buffer.from(record.kinesis.data, 'base64').toString();
      const data: Event = JSON.parse(payload);

      records.push({
        Dimensions: [
          { Name: 'event_type', Value: data.type },
          { Name: 'user_id', Value: data.userId || 'anonymous' },
        ],
        MeasureName: 'event_count',
        MeasureValue: '1',
        MeasureValueType: 'BIGINT',
        Time: data.timestamp.toString(),
        TimeUnit: 'MILLISECONDS',
      });
    } catch (error) {
      console.error('Failed to parse record:', error);
    }
  }

  if (records.length > 0) {
    await timestream.send(new WriteRecordsCommand({
      DatabaseName: process.env.TIMESTREAM_DATABASE,
      TableName: process.env.TIMESTREAM_TABLE,
      Records: records,
    }));
  }

  return { batchItemFailures: [] };
};
```

## Kafka with Node.js

### Producer

```typescript
// producer.ts
import { Kafka, Producer, CompressionTypes } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'my-app',
  brokers: process.env.KAFKA_BROKERS!.split(','),
  ssl: true,
  sasl: {
    mechanism: 'plain',
    username: process.env.KAFKA_USERNAME!,
    password: process.env.KAFKA_PASSWORD!,
  },
});

const producer = kafka.producer();

export async function initProducer() {
  await producer.connect();
}

export async function sendEvent(event: {
  type: string;
  userId?: string;
  properties: Record<string, any>;
}) {
  await producer.send({
    topic: 'events',
    compression: CompressionTypes.GZIP,
    messages: [
      {
        key: event.userId || null,
        value: JSON.stringify({
          id: crypto.randomUUID(),
          ...event,
          timestamp: Date.now(),
        }),
        headers: {
          'content-type': 'application/json',
        },
      },
    ],
  });
}

// Batch sending
export async function sendEvents(events: any[]) {
  await producer.sendBatch({
    topicMessages: [
      {
        topic: 'events',
        messages: events.map((event) => ({
          key: event.userId || null,
          value: JSON.stringify({
            id: crypto.randomUUID(),
            ...event,
            timestamp: Date.now(),
          }),
        })),
      },
    ],
  });
}
```

### Consumer

```typescript
// consumer.ts
import { Kafka, Consumer, EachBatchPayload } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'my-app',
  brokers: process.env.KAFKA_BROKERS!.split(','),
});

const consumer = kafka.consumer({
  groupId: 'event-processors',
  maxWaitTimeInMs: 100,
  maxBytesPerPartition: 1048576, // 1MB
});

export async function startConsumer() {
  await consumer.connect();
  await consumer.subscribe({ topic: 'events', fromBeginning: false });

  await consumer.run({
    eachBatch: async ({ batch, resolveOffset, heartbeat }: EachBatchPayload) => {
      const events = [];

      for (const message of batch.messages) {
        try {
          const event = JSON.parse(message.value!.toString());
          events.push(event);
          resolveOffset(message.offset);
        } catch (error) {
          console.error('Failed to parse message:', error);
        }

        // Heartbeat to prevent rebalancing during long batches
        await heartbeat();
      }

      // Process batch
      await processBatch(events);
    },
  });
}

async function processBatch(events: any[]) {
  // Aggregate by type
  const counts = events.reduce((acc, event) => {
    acc[event.type] = (acc[event.type] || 0) + 1;
    return acc;
  }, {});

  // Write to database/cache
  await updateMetrics(counts);

  console.log(`Processed ${events.length} events`);
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  await consumer.disconnect();
});
```

## Real-time Dashboard (WebSocket)

```typescript
// dashboard-server.ts
import { Server } from 'socket.io';
import { createClient } from 'redis';

const redis = createClient({ url: process.env.REDIS_URL });
const io = new Server(3001, { cors: { origin: '*' } });

// Subscribe to Redis pub/sub for metrics updates
const subscriber = redis.duplicate();

async function startDashboard() {
  await redis.connect();
  await subscriber.connect();

  // Subscribe to metrics channel
  await subscriber.subscribe('metrics', (message) => {
    const metrics = JSON.parse(message);
    // Broadcast to all connected clients
    io.emit('metrics', metrics);
  });

  io.on('connection', (socket) => {
    console.log('Dashboard client connected');

    // Send current metrics on connect
    redis.hGetAll('current_metrics').then((metrics) => {
      socket.emit('metrics', metrics);
    });
  });
}

// Consumer updates metrics
async function updateMetrics(counts: Record<string, number>) {
  const pipeline = redis.multi();

  for (const [type, count] of Object.entries(counts)) {
    pipeline.hIncrBy('current_metrics', type, count);
  }

  await pipeline.exec();

  // Publish update
  await redis.publish('metrics', JSON.stringify(counts));
}
```

## Cost Breakdown

| Service | Provider | ~1M events/day |
|---------|----------|----------------|
| **Kafka** | Confluent Cloud | ~$200/mo |
| **Kafka** | AWS MSK | ~$300/mo |
| **Pub/Sub** | GCP | ~$40/mo |
| **Kinesis** | AWS | ~$100/mo |
| **Dataflow** | GCP | ~$100/mo |
| **BigQuery** | GCP | ~$20/mo (storage + queries) |

## Best Practices

### Idempotent Processing

```typescript
// Use event ID for deduplication
const processedIds = new Set<string>();

async function processEvent(event: Event) {
  if (processedIds.has(event.id)) {
    return; // Skip duplicate
  }

  await doProcessing(event);

  processedIds.add(event.id);

  // Clean up old IDs (use Redis with TTL in production)
  if (processedIds.size > 10000) {
    const oldest = [...processedIds].slice(0, 5000);
    oldest.forEach(id => processedIds.delete(id));
  }
}
```

### Backpressure Handling

```typescript
// Consumer with backpressure
const consumer = kafka.consumer({
  groupId: 'processors',
  maxInFlightRequests: 1,  // Process one batch at a time
});

await consumer.run({
  autoCommit: false,  // Manual commits after processing
  eachBatch: async ({ batch, commitOffsetsIfNecessary }) => {
    try {
      await processBatch(batch.messages);
      await commitOffsetsIfNecessary();
    } catch (error) {
      // Don't commit - will reprocess
      throw error;
    }
  },
});
```

## Common Mistakes

1. **No idempotency** - Duplicate processing on retry
2. **Missing dead letter queue** - Lost messages
3. **No backpressure handling** - Consumer overwhelmed
4. **Unbounded memory** - Not limiting batch sizes
5. **Missing monitoring** - Silent lag buildup
6. **No ordering guarantees** - Events processed out of order
7. **Ignoring late data** - Incorrect aggregations
8. **No watermarks** - Can't handle event-time processing
9. **Single consumer** - No parallelism
10. **No graceful shutdown** - Data loss on restart

## Example Configuration

```yaml
# infera.yaml
project_name: analytics-pipeline
provider: gcp
region: us-central1

streaming:
  broker: pubsub

  topics:
    - name: events
      retention: 7d
      dead_letter: true

    - name: metrics
      retention: 1d

  processing:
    type: dataflow
    workers: 2
    max_workers: 10

  sinks:
    - type: bigquery
      dataset: analytics
      table: events

    - type: redis
      purpose: real-time-cache

monitoring:
  alerts:
    - metric: lag
      threshold: 1000
      window: 5m
```

## Sources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Google Cloud Pub/Sub](https://cloud.google.com/pubsub/docs)
- [Apache Beam](https://beam.apache.org/documentation/)
- [AWS Kinesis](https://docs.aws.amazon.com/kinesis/)
- [Dataflow Templates](https://cloud.google.com/dataflow/docs/guides/templates)
- [Confluent Cloud](https://docs.confluent.io/cloud/current/)
