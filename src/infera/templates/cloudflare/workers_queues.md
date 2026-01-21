# Cloudflare Workers + Queues

## Overview

Deploy message-driven architectures using Cloudflare Queues for reliable, scalable async processing. Queues provide at-least-once delivery, automatic retries, and seamless Workers integration for background job processing.

## Detection Signals

Use this template when:
- Background job processing needed
- Message queue patterns (producer/consumer)
- Async task execution
- Webhook delivery
- Email sending queues
- Data pipeline processing

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
                    │   ┌─────────────────────────────────────────┐   │
    HTTP Request ──►│   │         Producer Worker                 │   │
                    │   │                                         │   │
                    │   │  ┌─────────┐       ┌─────────────────┐  │   │
                    │   │  │  API    │──────►│     Queue       │  │   │
                    │   │  └─────────┘       │                 │  │   │
                    │   │                    │  ┌───────────┐  │  │   │
                    │   │                    │  │ Messages  │  │  │   │
                    │   │                    │  └───────────┘  │  │   │
                    │   │                    └────────┬────────┘  │   │
                    │   └────────────────────────────┼────────────┘   │
                    │                                │                │
                    │                                │ Batch Delivery │
                    │                                ▼                │
                    │   ┌─────────────────────────────────────────┐   │
                    │   │         Consumer Worker                 │   │
                    │   │                                         │   │
                    │   │  ┌─────────────────────────────────┐    │   │
                    │   │  │  async queue(batch, env) {      │    │   │
                    │   │  │    for (const message of batch) │    │   │
                    │   │  │      // Process message         │    │   │
                    │   │  │  }                              │    │   │
                    │   │  └─────────────────────────────────┘    │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   At-least-once delivery • Automatic retries    │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Producer Worker | Queue messages | wrangler.toml |
| Consumer Worker | Process messages | wrangler.toml |
| Queue | Message storage | Binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Dead Letter Queue | Failed messages | Separate queue |
| D1 Database | State tracking | Binding |
| KV Namespace | Deduplication | Binding |

## Configuration

### wrangler.toml (Producer)
```toml
name = "queue-producer"
main = "src/producer.ts"
compatibility_date = "2024-01-01"

# Queue producer binding
[[queues.producers]]
queue = "my-queue"
binding = "MY_QUEUE"

# Optional: Dead letter queue
[[queues.producers]]
queue = "my-queue-dlq"
binding = "DLQ"
```

### wrangler.toml (Consumer)
```toml
name = "queue-consumer"
main = "src/consumer.ts"
compatibility_date = "2024-01-01"

# Queue consumer binding
[[queues.consumers]]
queue = "my-queue"
max_batch_size = 10
max_batch_timeout = 30
max_retries = 3
dead_letter_queue = "my-queue-dlq"

# Database for tracking
[[d1_databases]]
binding = "DB"
database_name = "job-tracking"
database_id = "xxxxxxxxxxxxxxxxxxxxx"
```

## Implementation

### Producer Worker
```typescript
// src/producer.ts
import { Hono } from 'hono';

type Bindings = {
  MY_QUEUE: Queue;
};

type EmailJob = {
  type: 'send_email';
  to: string;
  subject: string;
  body: string;
  templateId?: string;
};

type WebhookJob = {
  type: 'deliver_webhook';
  url: string;
  payload: Record<string, any>;
  headers?: Record<string, string>;
};

type Job = EmailJob | WebhookJob;

const app = new Hono<{ Bindings: Bindings }>();

// Queue a single job
app.post('/api/jobs', async (c) => {
  const job = await c.req.json<Job>();

  await c.env.MY_QUEUE.send(job);

  return c.json({ queued: true, job });
});

// Queue multiple jobs (batch)
app.post('/api/jobs/batch', async (c) => {
  const { jobs } = await c.req.json<{ jobs: Job[] }>();

  // Batch send (max 100 messages per batch)
  const batches = chunk(jobs, 100);

  for (const batch of batches) {
    await c.env.MY_QUEUE.sendBatch(
      batch.map(job => ({ body: job }))
    );
  }

  return c.json({ queued: jobs.length });
});

// Queue with delay
app.post('/api/jobs/delayed', async (c) => {
  const { job, delaySeconds } = await c.req.json<{
    job: Job;
    delaySeconds: number;
  }>();

  await c.env.MY_QUEUE.send(job, {
    delaySeconds: Math.min(delaySeconds, 43200), // Max 12 hours
  });

  return c.json({ queued: true, delaySeconds });
});

function chunk<T>(array: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

export default app;
```

### Consumer Worker
```typescript
// src/consumer.ts

type Bindings = {
  DB: D1Database;
  DLQ: Queue;
};

type EmailJob = {
  type: 'send_email';
  to: string;
  subject: string;
  body: string;
};

type WebhookJob = {
  type: 'deliver_webhook';
  url: string;
  payload: Record<string, any>;
  headers?: Record<string, string>;
};

type Job = EmailJob | WebhookJob;

export default {
  async queue(
    batch: MessageBatch<Job>,
    env: Bindings
  ): Promise<void> {
    console.log(`Processing ${batch.messages.length} messages`);

    for (const message of batch.messages) {
      try {
        await processJob(message.body, env);

        // Acknowledge successful processing
        message.ack();

        // Track success
        await trackJob(env.DB, message.id, 'completed');
      } catch (error) {
        console.error(`Error processing job ${message.id}:`, error);

        // Track failure
        await trackJob(env.DB, message.id, 'failed', String(error));

        // Retry (up to max_retries)
        message.retry();
      }
    }
  },
};

async function processJob(job: Job, env: Bindings): Promise<void> {
  switch (job.type) {
    case 'send_email':
      await sendEmail(job);
      break;
    case 'deliver_webhook':
      await deliverWebhook(job);
      break;
    default:
      throw new Error(`Unknown job type: ${(job as any).type}`);
  }
}

async function sendEmail(job: EmailJob): Promise<void> {
  // Use your email service (SendGrid, Resend, etc.)
  const response = await fetch('https://api.sendgrid.com/v3/mail/send', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${SENDGRID_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      personalizations: [{ to: [{ email: job.to }] }],
      from: { email: 'noreply@example.com' },
      subject: job.subject,
      content: [{ type: 'text/plain', value: job.body }],
    }),
  });

  if (!response.ok) {
    throw new Error(`Email failed: ${response.status}`);
  }
}

async function deliverWebhook(job: WebhookJob): Promise<void> {
  const response = await fetch(job.url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...job.headers,
    },
    body: JSON.stringify(job.payload),
  });

  if (!response.ok) {
    throw new Error(`Webhook failed: ${response.status}`);
  }
}

async function trackJob(
  db: D1Database,
  messageId: string,
  status: string,
  error?: string
): Promise<void> {
  await db.prepare(`
    INSERT INTO job_history (message_id, status, error, processed_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT (message_id) DO UPDATE SET
      status = excluded.status,
      error = excluded.error,
      processed_at = excluded.processed_at
  `).bind(messageId, status, error || null, new Date().toISOString()).run();
}
```

### Dead Letter Queue Consumer
```typescript
// src/dlq-consumer.ts

type Bindings = {
  DB: D1Database;
};

export default {
  async queue(
    batch: MessageBatch<any>,
    env: Bindings
  ): Promise<void> {
    console.log(`Processing ${batch.messages.length} dead letters`);

    for (const message of batch.messages) {
      // Log failed message for investigation
      await env.DB.prepare(`
        INSERT INTO dead_letters (
          message_id, body, attempts, failed_at
        ) VALUES (?, ?, ?, ?)
      `).bind(
        message.id,
        JSON.stringify(message.body),
        message.attempts,
        new Date().toISOString()
      ).run();

      // Alert on critical failures
      if (message.body.type === 'critical') {
        await sendAlert(message);
      }

      message.ack();
    }
  },
};

async function sendAlert(message: Message<any>): Promise<void> {
  // Send to Slack, PagerDuty, etc.
}
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create queue
npx wrangler queues create my-queue
npx wrangler queues create my-queue-dlq

# List queues
npx wrangler queues list

# Deploy producer
npx wrangler deploy -c wrangler.producer.toml

# Deploy consumer
npx wrangler deploy -c wrangler.consumer.toml

# View queue stats
npx wrangler queues consumer my-queue

# Send test message
curl -X POST https://producer.example.com/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "send_email", "to": "test@example.com", "subject": "Test", "body": "Hello"}'
```

## Best Practices

### Message Design
1. Keep messages small (< 128KB)
2. Include all data needed for processing
3. Design for idempotency
4. Add correlation IDs for tracking

### Consumer Design
1. Process messages in batches for efficiency
2. Implement proper error handling
3. Use acknowledgment correctly
4. Set appropriate retry limits

### Reliability
1. Use dead letter queues
2. Track job history
3. Monitor queue depth
4. Alert on high failure rates

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Messages written | 1M/month | $0.40/million |
| Messages read | 1M/month | $0.40/million |
| Storage | - | Included |

### Example Costs
| Scale | Messages/mo | Cost |
|-------|-------------|------|
| Small | 500k | $0 |
| Medium | 10M | $8 |
| Large | 100M | $80 |

## Common Mistakes

1. **Not using batches**: Sending messages one at a time
2. **Large messages**: Exceeding 128KB limit
3. **Missing error handling**: Unhandled errors lose messages
4. **No DLQ**: Failed messages disappear
5. **Ignoring retries**: Not handling duplicate processing
6. **Wrong acknowledgment**: Acking before processing completes

## Example Configuration

```yaml
project_name: queue-system
provider: cloudflare
architecture_type: workers_queues

resources:
  - id: main-queue
    type: cloudflare_queue
    name: jobs
    provider: cloudflare
    config:
      binding: MY_QUEUE

  - id: dlq
    type: cloudflare_queue
    name: jobs-dlq
    provider: cloudflare
    config:
      binding: DLQ

  - id: producer
    type: cloudflare_worker
    name: queue-producer
    provider: cloudflare
    config:
      main: src/producer.ts
      queue_producers:
        - queue: jobs
          binding: MY_QUEUE

  - id: consumer
    type: cloudflare_worker
    name: queue-consumer
    provider: cloudflare
    config:
      main: src/consumer.ts
      queue_consumers:
        - queue: jobs
          max_batch_size: 10
          max_retries: 3
          dead_letter_queue: jobs-dlq
```

## Sources

- [Queues Documentation](https://developers.cloudflare.com/queues)
- [Queues Best Practices](https://developers.cloudflare.com/queues/best-practices)
- [Queues Pricing](https://developers.cloudflare.com/queues/platform/pricing)
