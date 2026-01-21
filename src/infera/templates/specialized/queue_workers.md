# Message Queue Workers

## Overview
Message queues enable asynchronous processing by decoupling producers from consumers. Workers process tasks from queues, enabling reliable background job processing, event-driven architectures, and workload distribution.

**Use when:**
- Background job processing (emails, reports)
- Event-driven architectures
- Workload distribution across workers
- Handling traffic spikes (buffering)
- Reliable task execution with retries
- Long-running operations

**Don't use when:**
- Synchronous responses required
- Simple, fast operations
- Very low latency requirements

## Detection Signals

```
Files:
- workers/, jobs/, queues/
- celery.py, tasks.py
- bull.ts, bullmq.ts

Dependencies:
- bullmq, bull, bee-queue (Node.js)
- celery, rq, dramatiq (Python)
- machinery, asynq (Go)
- sidekiq (Ruby)

Code Patterns:
- queue.add(), worker.process()
- @celery.task, @job
- SQS, Pub/Sub, CloudTasks
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Queue Worker Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Producers                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Web API   │  │  Cron Job   │  │  Webhook    │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  │         │                │                │              │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            └────────────────┼────────────────┘                   │
│                             │ Enqueue                            │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                    Message Queue                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────┐  │ │   │
│  │  │  │ emails  │  │ reports │  │ uploads │  │  DLQ  │  │ │   │
│  │  │  │ queue   │  │ queue   │  │ queue   │  │       │  │ │   │
│  │  │  └────┬────┘  └────┬────┘  └────┬────┘  └───────┘  │ │   │
│  │  └───────┼────────────┼────────────┼──────────────────┘ │   │
│  └──────────┼────────────┼────────────┼─────────────────────┘   │
│             │ Dequeue    │            │                          │
│  ┌──────────▼────────────▼────────────▼─────────────────────┐   │
│  │                      Workers                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │  Worker 1   │  │  Worker 2   │  │  Worker N   │      │   │
│  │  │             │  │             │  │             │      │   │
│  │  │ Process job │  │ Process job │  │ Process job │      │   │
│  │  │ Ack/Nack    │  │ Ack/Nack    │  │ Ack/Nack    │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Cloud Pub/Sub | SQS | Cloud Tasks | BullMQ + Redis |
|---------|--------------|-----|-------------|----------------|
| **Type** | Pub/Sub | Queue | Task queue | Job queue |
| **Ordering** | Optional | FIFO optional | Guaranteed | FIFO |
| **Delay** | No | Yes (15 min) | Yes | Yes |
| **Dead Letter** | Yes | Yes | No | Yes |
| **Fan-out** | Yes | No | No | No |
| **Cost** | $0.04/100K | $0.40/million | $0.40/million | Self-hosted |

## BullMQ Implementation (Node.js)

### Queue Setup

```typescript
// queues/index.ts
import { Queue, Worker, QueueEvents } from 'bullmq';
import Redis from 'ioredis';

const connection = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: null,
});

// Define queues
export const emailQueue = new Queue('emails', { connection });
export const reportQueue = new Queue('reports', { connection });
export const processQueue = new Queue('process', { connection });

// Queue events for monitoring
const queueEvents = new QueueEvents('emails', { connection });

queueEvents.on('completed', ({ jobId }) => {
  console.log(`Job ${jobId} completed`);
});

queueEvents.on('failed', ({ jobId, failedReason }) => {
  console.error(`Job ${jobId} failed: ${failedReason}`);
});
```

### Job Definitions

```typescript
// jobs/email.ts
import { Job } from 'bullmq';
import { sendEmail } from '@/lib/email';

export interface EmailJobData {
  to: string;
  subject: string;
  template: string;
  data: Record<string, any>;
}

export async function processEmailJob(job: Job<EmailJobData>) {
  const { to, subject, template, data } = job.data;

  job.updateProgress(10);

  // Render template
  const html = await renderTemplate(template, data);

  job.updateProgress(50);

  // Send email
  await sendEmail({ to, subject, html });

  job.updateProgress(100);

  return { sent: true, to };
}
```

### Worker Implementation

```typescript
// workers/email.worker.ts
import { Worker, Job } from 'bullmq';
import { processEmailJob, EmailJobData } from '@/jobs/email';

const worker = new Worker<EmailJobData>(
  'emails',
  async (job) => {
    console.log(`Processing email job ${job.id}`);
    return processEmailJob(job);
  },
  {
    connection,
    concurrency: 5,
    limiter: {
      max: 100,
      duration: 1000, // 100 emails per second
    },
  }
);

worker.on('completed', (job) => {
  console.log(`Email job ${job.id} completed`);
});

worker.on('failed', (job, err) => {
  console.error(`Email job ${job?.id} failed:`, err);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  await worker.close();
});
```

### Producer (API)

```typescript
// api/send-email.ts
import { emailQueue } from '@/queues';

export async function POST(req: Request) {
  const { to, subject, template, data } = await req.json();

  const job = await emailQueue.add(
    'send-email',
    { to, subject, template, data },
    {
      attempts: 3,
      backoff: {
        type: 'exponential',
        delay: 1000,
      },
      removeOnComplete: {
        age: 24 * 3600, // Keep completed jobs for 24 hours
        count: 1000,
      },
      removeOnFail: {
        age: 7 * 24 * 3600, // Keep failed jobs for 7 days
      },
    }
  );

  return Response.json({ jobId: job.id });
}

// Delayed job
await emailQueue.add('reminder', data, {
  delay: 24 * 60 * 60 * 1000, // 24 hours
});

// Scheduled/repeated job
await emailQueue.add('daily-digest', data, {
  repeat: {
    pattern: '0 9 * * *', // Every day at 9 AM
  },
});
```

## AWS SQS + Lambda

### Terraform Configuration

```hcl
# sqs_lambda.tf

# SQS Queue
resource "aws_sqs_queue" "jobs" {
  name                       = "${var.project_name}-jobs"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600  # 14 days
  receive_wait_time_seconds  = 20       # Long polling
  visibility_timeout_seconds = 300      # 5 minutes

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })
}

# Dead Letter Queue
resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${var.project_name}-jobs-dlq"
  message_retention_seconds = 1209600
}

# Lambda Worker
resource "aws_lambda_function" "worker" {
  filename         = data.archive_file.worker.output_path
  function_name    = "${var.project_name}-worker"
  role             = aws_iam_role.lambda.arn
  handler          = "worker.handler"
  runtime          = "nodejs18.x"
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      DATABASE_URL = var.database_url
    }
  }
}

# SQS Event Source Mapping
resource "aws_lambda_event_source_mapping" "sqs_worker" {
  event_source_arn                   = aws_sqs_queue.jobs.arn
  function_name                      = aws_lambda_function.worker.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5

  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 10
  }
}

# IAM permissions
resource "aws_iam_role_policy" "lambda_sqs" {
  name = "${var.project_name}-lambda-sqs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.jobs.arn
      }
    ]
  })
}
```

### Lambda Worker

```typescript
// worker.ts
import { SQSHandler, SQSBatchResponse, SQSBatchItemFailure } from 'aws-lambda';

interface JobMessage {
  type: string;
  data: any;
}

export const handler: SQSHandler = async (event): Promise<SQSBatchResponse> => {
  const batchItemFailures: SQSBatchItemFailure[] = [];

  for (const record of event.Records) {
    try {
      const message: JobMessage = JSON.parse(record.body);
      console.log(`Processing job type: ${message.type}`);

      switch (message.type) {
        case 'send-email':
          await processEmailJob(message.data);
          break;
        case 'generate-report':
          await processReportJob(message.data);
          break;
        default:
          console.warn(`Unknown job type: ${message.type}`);
      }
    } catch (error) {
      console.error(`Failed to process message ${record.messageId}:`, error);
      batchItemFailures.push({ itemIdentifier: record.messageId });
    }
  }

  return { batchItemFailures };
};

// Producer (in API)
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';

const sqs = new SQSClient({});

export async function enqueueJob(type: string, data: any, delaySeconds = 0) {
  await sqs.send(new SendMessageCommand({
    QueueUrl: process.env.SQS_QUEUE_URL,
    MessageBody: JSON.stringify({ type, data }),
    DelaySeconds: delaySeconds,
  }));
}
```

## GCP Cloud Pub/Sub

### Terraform Configuration

```hcl
# pubsub.tf

# Pub/Sub Topic
resource "google_pubsub_topic" "jobs" {
  name = "${var.project_name}-jobs"

  message_retention_duration = "604800s"  # 7 days
}

# Dead Letter Topic
resource "google_pubsub_topic" "jobs_dlq" {
  name = "${var.project_name}-jobs-dlq"
}

# Subscription with push to Cloud Run
resource "google_pubsub_subscription" "jobs_push" {
  name  = "${var.project_name}-jobs-push"
  topic = google_pubsub_topic.jobs.name

  ack_deadline_seconds = 300

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/jobs"

    oidc_token {
      service_account_email = google_service_account.pubsub.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.jobs_dlq.id
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

# Pull subscription (alternative)
resource "google_pubsub_subscription" "jobs_pull" {
  name  = "${var.project_name}-jobs-pull"
  topic = google_pubsub_topic.jobs.name

  ack_deadline_seconds       = 300
  message_retention_duration = "604800s"
  retain_acked_messages      = false
}
```

### Cloud Run Worker

```typescript
// worker.ts
import express from 'express';

const app = express();
app.use(express.json());

interface PubSubMessage {
  message: {
    data: string;
    messageId: string;
    publishTime: string;
    attributes: Record<string, string>;
  };
  subscription: string;
}

app.post('/jobs', async (req, res) => {
  const pubsubMessage = req.body as PubSubMessage;

  try {
    const data = JSON.parse(
      Buffer.from(pubsubMessage.message.data, 'base64').toString()
    );

    console.log(`Processing job ${pubsubMessage.message.messageId}:`, data);

    await processJob(data);

    // Ack the message
    res.status(200).send('OK');
  } catch (error) {
    console.error('Job failed:', error);
    // Nack the message (will be retried)
    res.status(500).send('Failed');
  }
});

app.listen(process.env.PORT || 8080);

// Producer
import { PubSub } from '@google-cloud/pubsub';

const pubsub = new PubSub();
const topic = pubsub.topic('my-project-jobs');

export async function enqueueJob(type: string, data: any) {
  const message = JSON.stringify({ type, data });
  const messageId = await topic.publishMessage({ data: Buffer.from(message) });
  return messageId;
}
```

## GCP Cloud Tasks

### Terraform Configuration

```hcl
# cloud_tasks.tf

resource "google_cloud_tasks_queue" "jobs" {
  name     = "${var.project_name}-jobs"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 100
  }

  retry_config {
    max_attempts       = 5
    max_retry_duration = "0s"  # No limit
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 4
  }

  stackdriver_logging_config {
    sampling_ratio = 1.0
  }
}

# Service account for invoking Cloud Run
resource "google_service_account" "tasks" {
  account_id   = "${var.project_name}-tasks"
  display_name = "Cloud Tasks Service Account"
}

resource "google_cloud_run_v2_service_iam_member" "tasks_invoker" {
  name     = google_cloud_run_v2_service.worker.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks.email}"
}
```

### Cloud Tasks Producer

```typescript
// tasks.ts
import { CloudTasksClient } from '@google-cloud/tasks';

const client = new CloudTasksClient();
const parent = client.queuePath(
  process.env.GOOGLE_CLOUD_PROJECT!,
  process.env.REGION!,
  'my-project-jobs'
);

export async function enqueueTask(
  type: string,
  data: any,
  options: {
    delaySeconds?: number;
    scheduleTime?: Date;
  } = {}
) {
  const task: any = {
    httpRequest: {
      url: `${process.env.WORKER_URL}/tasks/${type}`,
      httpMethod: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: Buffer.from(JSON.stringify(data)).toString('base64'),
      oidcToken: {
        serviceAccountEmail: process.env.TASKS_SERVICE_ACCOUNT,
      },
    },
  };

  if (options.delaySeconds) {
    task.scheduleTime = {
      seconds: Date.now() / 1000 + options.delaySeconds,
    };
  } else if (options.scheduleTime) {
    task.scheduleTime = {
      seconds: options.scheduleTime.getTime() / 1000,
    };
  }

  const [response] = await client.createTask({ parent, task });
  return response.name;
}

// Usage
await enqueueTask('send-email', { to: 'user@example.com', template: 'welcome' });

// Delayed task
await enqueueTask('send-reminder', { userId: '123' }, { delaySeconds: 3600 });
```

## Python (Celery)

```python
# celery_app.py
from celery import Celery

app = Celery(
    'tasks',
    broker=os.environ['REDIS_URL'],
    backend=os.environ['REDIS_URL'],
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
)

# tasks.py
from celery_app import app

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email(self, to: str, subject: str, template: str, data: dict):
    try:
        html = render_template(template, data)
        send_email_smtp(to, subject, html)
        return {'sent': True, 'to': to}
    except Exception as exc:
        self.retry(exc=exc)

@app.task
def generate_report(report_type: str, params: dict):
    # Long-running task
    data = fetch_report_data(report_type, params)
    pdf = generate_pdf(data)
    url = upload_to_storage(pdf)
    return {'url': url}

# Producer
from tasks import send_email, generate_report

# Async execution
send_email.delay('user@example.com', 'Welcome', 'welcome', {'name': 'John'})

# Delayed execution
send_email.apply_async(
    args=['user@example.com', 'Reminder', 'reminder', {}],
    countdown=3600  # 1 hour delay
)

# Scheduled execution
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-report': {
        'task': 'tasks.generate_report',
        'schedule': crontab(hour=9, minute=0),
        'args': ('daily', {}),
    },
}
```

## Cost Breakdown

| Provider | Service | ~1M messages/mo | Notes |
|----------|---------|-----------------|-------|
| **GCP** | Pub/Sub | ~$40 | $0.04/100K messages |
| **GCP** | Cloud Tasks | ~$40 | $0.40/million |
| **AWS** | SQS | ~$0.40 | First 1M free |
| **Self-hosted** | BullMQ + Redis | ~$30 | Redis hosting cost |

## Best Practices

### Idempotent Job Processing

```typescript
async function processJob(job: Job) {
  const idempotencyKey = `job:${job.id}:processed`;

  // Check if already processed
  const alreadyProcessed = await redis.get(idempotencyKey);
  if (alreadyProcessed) {
    console.log(`Job ${job.id} already processed`);
    return;
  }

  // Process job
  await doWork(job.data);

  // Mark as processed (with TTL)
  await redis.setex(idempotencyKey, 86400, 'true');
}
```

### Graceful Shutdown

```typescript
let isShuttingDown = false;

process.on('SIGTERM', async () => {
  console.log('Shutting down gracefully...');
  isShuttingDown = true;

  // Stop accepting new jobs
  await worker.pause();

  // Wait for current jobs to finish
  await worker.close();

  process.exit(0);
});
```

## Common Mistakes

1. **Not handling failures** - Jobs silently fail
2. **Missing dead letter queue** - Failed jobs lost forever
3. **No idempotency** - Duplicate processing on retry
4. **Long visibility timeout** - Blocks retries
5. **No monitoring** - Silent queue buildup
6. **Synchronous processing** - Blocking the API
7. **Missing backoff** - Hammering failing services
8. **No job prioritization** - Important jobs delayed
9. **Unbounded concurrency** - Overwhelming downstream services
10. **No graceful shutdown** - Jobs interrupted mid-processing

## Example Configuration

```yaml
# infera.yaml
project_name: my-app
provider: gcp
region: us-central1

queues:
  - name: emails
    type: cloud_tasks
    rate_limit: 100/s
    retry:
      max_attempts: 5
      min_backoff: 10s

  - name: reports
    type: pubsub
    dead_letter: true

workers:
  email_worker:
    runtime: cloud_run
    queue: emails
    concurrency: 5

  report_worker:
    runtime: cloud_run
    queue: reports
    concurrency: 2
    timeout: 3600
```

## Sources

- [BullMQ Documentation](https://docs.bullmq.io/)
- [AWS SQS Developer Guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/)
- [Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Cloud Tasks Documentation](https://cloud.google.com/tasks/docs)
- [Celery Documentation](https://docs.celeryq.dev/)
