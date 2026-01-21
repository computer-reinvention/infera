# Scheduled Tasks / Cron Jobs

## Overview
Scheduled tasks (cron jobs) execute code at specified intervals or times. Cloud platforms provide serverless options that eliminate the need to maintain dedicated servers for periodic workloads.

**Use when:**
- Periodic data processing or cleanup
- Sending scheduled notifications/emails
- Generating reports
- Syncing data between systems
- Cache warming or invalidation
- Health checks and monitoring

**Don't use when:**
- Real-time processing needed (use queues)
- Tasks need to run more frequently than 1/minute
- Long-running tasks > 15 minutes (consider queues)

## Detection Signals

```
Files:
- crontab, cron.yaml
- serverless.yml with schedule events
- Cloud Scheduler configs

Dependencies:
- node-cron, cron (Node.js)
- APScheduler, celery[beat] (Python)
- robfig/cron (Go)

Code Patterns:
- schedule.every(), cron.schedule()
- @scheduled_job decorator
- schedule: rate(1 hour)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cron Job Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Scheduler Service                      │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  Cloud Scheduler / EventBridge / Cron Triggers      │ │   │
│  │  │                                                      │ │   │
│  │  │  Job 1: "0 * * * *"   → Every hour                 │ │   │
│  │  │  Job 2: "0 0 * * *"   → Every day at midnight      │ │   │
│  │  │  Job 3: "0 9 * * 1"   → Every Monday at 9 AM       │ │   │
│  │  │  Job 4: "*/5 * * * *" → Every 5 minutes            │ │   │
│  │  └──────────────────────────┬──────────────────────────┘ │   │
│  └─────────────────────────────┼────────────────────────────┘   │
│                                │ HTTP / Pub/Sub / Event         │
│                                │                                 │
│  ┌─────────────────────────────▼────────────────────────────┐   │
│  │                    Job Executors                          │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │ Cloud Run   │  │   Lambda    │  │ Cloud       │      │   │
│  │  │ Job         │  │ Function    │  │ Functions   │      │   │
│  │  │             │  │             │  │             │      │   │
│  │  │ Long tasks  │  │ Quick tasks │  │ Event-based │      │   │
│  │  │ (up to 24h) │  │ (up to 15m) │  │ (up to 9m)  │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  │         │                │                │              │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            │                │                │                   │
│  ┌─────────▼────────────────▼────────────────▼──────────────┐   │
│  │                    Data Layer                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ Database │  │ Storage  │  │ External │  │ Message  │ │   │
│  │  │          │  │ Bucket   │  │   APIs   │  │ Queues   │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │   │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Cloud Scheduler + Run | EventBridge + Lambda | Vercel Cron | Cloudflare Cron |
|---------|----------------------|---------------------|-------------|-----------------|
| **Min Interval** | 1 minute | 1 minute | 1 minute | 1 minute |
| **Max Timeout** | 24 hours (Jobs) | 15 minutes | 10 seconds | 30 seconds |
| **Retry** | Configurable | Configurable | No | No |
| **Cost** | ~$0.10/job/mo | ~$1/million | Free (Hobby) | Free |
| **Timezone** | Yes | Yes | Yes | Yes |
| **Dashboard** | Yes | Yes | Yes | Yes |

## GCP Cloud Scheduler + Cloud Run Jobs

### Terraform Configuration

```hcl
# cloud_run_jobs.tf

# Enable required APIs
resource "google_project_service" "scheduler" {
  service = "cloudscheduler.googleapis.com"
}

resource "google_project_service" "run" {
  service = "run.googleapis.com"
}

# Cloud Run Job (for longer tasks)
resource "google_cloud_run_v2_job" "cleanup" {
  name     = "${var.project_name}-cleanup"
  location = var.region

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/jobs:latest"

        env {
          name  = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_url.secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      timeout     = "3600s"  # 1 hour max
      max_retries = 3

      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }

    task_count = 1
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# Service account for scheduler
resource "google_service_account" "scheduler" {
  account_id   = "${var.project_name}-scheduler"
  display_name = "Cloud Scheduler Service Account"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_job.cleanup.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Cloud Scheduler Jobs
resource "google_cloud_scheduler_job" "cleanup_daily" {
  name        = "${var.project_name}-cleanup-daily"
  description = "Daily cleanup of old data"
  schedule    = "0 3 * * *"  # 3 AM daily
  time_zone   = "America/New_York"
  region      = var.region

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.cleanup.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.scheduler]
}

# Hourly report generation
resource "google_cloud_scheduler_job" "hourly_report" {
  name        = "${var.project_name}-hourly-report"
  description = "Generate hourly reports"
  schedule    = "0 * * * *"  # Every hour
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/cron/report"

    headers = {
      "X-Cron-Secret" = var.cron_secret
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}

# Weekly summary email
resource "google_cloud_scheduler_job" "weekly_summary" {
  name        = "${var.project_name}-weekly-summary"
  description = "Send weekly summary emails"
  schedule    = "0 9 * * 1"  # Monday 9 AM
  time_zone   = "America/New_York"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/cron/weekly-summary"

    headers = {
      "X-Cron-Secret" = var.cron_secret
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}
```

### Cloud Run Job Handler

```typescript
// jobs/cleanup.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function cleanup() {
  console.log('Starting cleanup job...');

  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  // Delete old logs
  const deletedLogs = await prisma.log.deleteMany({
    where: {
      createdAt: { lt: thirtyDaysAgo },
    },
  });
  console.log(`Deleted ${deletedLogs.count} old logs`);

  // Delete expired sessions
  const deletedSessions = await prisma.session.deleteMany({
    where: {
      expiresAt: { lt: new Date() },
    },
  });
  console.log(`Deleted ${deletedSessions.count} expired sessions`);

  // Archive old orders
  const oldOrders = await prisma.order.findMany({
    where: {
      status: 'completed',
      completedAt: { lt: thirtyDaysAgo },
      archived: false,
    },
  });

  for (const order of oldOrders) {
    await prisma.archivedOrder.create({
      data: {
        originalId: order.id,
        data: order,
        archivedAt: new Date(),
      },
    });
    await prisma.order.update({
      where: { id: order.id },
      data: { archived: true },
    });
  }
  console.log(`Archived ${oldOrders.length} orders`);

  console.log('Cleanup completed');
}

cleanup()
  .catch((error) => {
    console.error('Cleanup failed:', error);
    process.exit(1);
  })
  .finally(() => {
    prisma.$disconnect();
  });
```

## AWS EventBridge + Lambda

### Terraform Configuration

```hcl
# eventbridge_lambda.tf

# Lambda function for cron jobs
resource "aws_lambda_function" "cron_cleanup" {
  filename         = data.archive_file.lambda.output_path
  function_name    = "${var.project_name}-cleanup"
  role             = aws_iam_role.lambda.arn
  handler          = "cleanup.handler"
  runtime          = "nodejs18.x"
  timeout          = 900  # 15 minutes max
  memory_size      = 512

  environment {
    variables = {
      DATABASE_URL = aws_secretsmanager_secret_version.db_url.secret_string
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
}

# EventBridge rule for daily cleanup
resource "aws_cloudwatch_event_rule" "daily_cleanup" {
  name                = "${var.project_name}-daily-cleanup"
  description         = "Trigger daily cleanup"
  schedule_expression = "cron(0 3 * * ? *)"  # 3 AM UTC daily
}

resource "aws_cloudwatch_event_target" "cleanup_lambda" {
  rule      = aws_cloudwatch_event_rule.daily_cleanup.name
  target_id = "CleanupLambda"
  arn       = aws_lambda_function.cron_cleanup.arn

  input = jsonencode({
    action = "cleanup"
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cron_cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_cleanup.arn
}

# Rate-based schedule (every 5 minutes)
resource "aws_cloudwatch_event_rule" "health_check" {
  name                = "${var.project_name}-health-check"
  description         = "Run health checks every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

# Multiple Lambda targets
resource "aws_lambda_function" "cron_report" {
  function_name = "${var.project_name}-report"
  # ... other config
}

resource "aws_cloudwatch_event_rule" "hourly_report" {
  name                = "${var.project_name}-hourly-report"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "report_lambda" {
  rule      = aws_cloudwatch_event_rule.hourly_report.name
  target_id = "ReportLambda"
  arn       = aws_lambda_function.cron_report.arn
}
```

### Lambda Handler

```typescript
// cleanup.ts
import { Handler, ScheduledEvent } from 'aws-lambda';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export const handler: Handler<ScheduledEvent> = async (event) => {
  console.log('Cron job triggered:', JSON.stringify(event));

  try {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    // Cleanup old records
    const deleted = await prisma.log.deleteMany({
      where: { createdAt: { lt: thirtyDaysAgo } },
    });

    console.log(`Deleted ${deleted.count} old logs`);

    return {
      statusCode: 200,
      body: JSON.stringify({ deleted: deleted.count }),
    };
  } catch (error) {
    console.error('Cleanup failed:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
};
```

## Vercel Cron Jobs

### vercel.json Configuration

```json
{
  "crons": [
    {
      "path": "/api/cron/cleanup",
      "schedule": "0 3 * * *"
    },
    {
      "path": "/api/cron/send-emails",
      "schedule": "0 9 * * 1"
    },
    {
      "path": "/api/cron/sync-data",
      "schedule": "*/15 * * * *"
    }
  ]
}
```

### API Route Handler

```typescript
// app/api/cron/cleanup/route.ts
import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const maxDuration = 10; // Hobby: 10s, Pro: 60s

export async function GET(request: Request) {
  // Verify cron secret
  const authHeader = request.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const deleted = await prisma.log.deleteMany({
      where: { createdAt: { lt: thirtyDaysAgo } },
    });

    return NextResponse.json({
      success: true,
      deleted: deleted.count,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Cleanup failed:', error);
    return NextResponse.json(
      { error: 'Cleanup failed' },
      { status: 500 }
    );
  }
}
```

## Cloudflare Cron Triggers

### wrangler.toml

```toml
name = "cron-worker"
main = "src/index.ts"

[triggers]
crons = [
  "0 3 * * *",      # Daily at 3 AM UTC
  "0 * * * *",      # Every hour
  "*/15 * * * *",   # Every 15 minutes
]
```

### Worker Handler

```typescript
// src/index.ts
export interface Env {
  DB: D1Database;
  CRON_SECRET: string;
}

export default {
  async scheduled(
    controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext
  ): Promise<void> {
    const cron = controller.cron;
    console.log(`Cron triggered: ${cron}`);

    switch (cron) {
      case '0 3 * * *':
        await dailyCleanup(env);
        break;
      case '0 * * * *':
        await hourlyReport(env);
        break;
      case '*/15 * * * *':
        await healthCheck(env);
        break;
    }
  },
};

async function dailyCleanup(env: Env) {
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  await env.DB.prepare(
    'DELETE FROM logs WHERE created_at < ?'
  ).bind(thirtyDaysAgo.toISOString()).run();

  console.log('Daily cleanup completed');
}

async function hourlyReport(env: Env) {
  const stats = await env.DB.prepare(
    'SELECT COUNT(*) as count FROM orders WHERE created_at > datetime("now", "-1 hour")'
  ).first();

  console.log('Hourly stats:', stats);
}

async function healthCheck(env: Env) {
  // Ping database
  await env.DB.prepare('SELECT 1').first();
  console.log('Health check passed');
}
```

## Best Practices

### Idempotency

```typescript
// Make jobs idempotent - safe to run multiple times
async function processOrders() {
  // Use markers to track processed items
  const unprocessed = await prisma.order.findMany({
    where: {
      processedAt: null,
      createdAt: { lt: new Date(Date.now() - 5 * 60 * 1000) }, // 5 min old
    },
    take: 100,
  });

  for (const order of unprocessed) {
    await processOrder(order);
    // Mark as processed
    await prisma.order.update({
      where: { id: order.id },
      data: { processedAt: new Date() },
    });
  }
}
```

### Distributed Locking

```typescript
// Prevent concurrent execution
import { Redis } from '@upstash/redis';

const redis = new Redis({ url: process.env.REDIS_URL });

async function withLock<T>(
  lockKey: string,
  ttlSeconds: number,
  fn: () => Promise<T>
): Promise<T | null> {
  const lockValue = crypto.randomUUID();

  // Try to acquire lock
  const acquired = await redis.set(lockKey, lockValue, {
    nx: true,
    ex: ttlSeconds,
  });

  if (!acquired) {
    console.log('Lock already held, skipping');
    return null;
  }

  try {
    return await fn();
  } finally {
    // Release lock if we still hold it
    const currentValue = await redis.get(lockKey);
    if (currentValue === lockValue) {
      await redis.del(lockKey);
    }
  }
}

// Usage
export async function handler() {
  return withLock('cleanup-job', 3600, async () => {
    // Job logic here
    await performCleanup();
  });
}
```

### Error Handling and Retries

```typescript
// With exponential backoff
async function runWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3
): Promise<T> {
  let lastError: Error;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      console.error(`Attempt ${attempt + 1} failed:`, error);

      if (attempt < maxRetries - 1) {
        const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError!;
}
```

## Cost Breakdown

| Provider | Scheduler | Execution | ~100 jobs/day |
|----------|-----------|-----------|---------------|
| **GCP** | $0.10/job/month | Cloud Run pricing | ~$5/mo |
| **AWS** | Free (first 1M) | Lambda pricing | ~$3/mo |
| **Vercel** | Free (Hobby) | Included | $0 |
| **Cloudflare** | Free | Worker pricing | ~$1/mo |

## Common Mistakes

1. **Not handling concurrent execution** - Same job runs twice
2. **Missing idempotency** - Duplicate processing on retry
3. **Long-running without checkpoints** - Timeout loses progress
4. **No monitoring/alerting** - Silent failures
5. **Hardcoded schedules** - Can't adjust without deploy
6. **Missing timezone** - Jobs run at wrong time
7. **No dead letter queue** - Failed jobs lost
8. **Blocking operations** - Timeouts on slow external APIs
9. **Missing authentication** - Cron endpoints publicly accessible
10. **No logging** - Can't debug failures

## Example Configuration

```yaml
# infera.yaml
project_name: my-app
provider: gcp
region: us-central1

cron_jobs:
  - name: daily-cleanup
    schedule: "0 3 * * *"
    timezone: America/New_York
    handler: cloud_run_job
    image: jobs:cleanup
    timeout: 3600
    retries: 3

  - name: hourly-report
    schedule: "0 * * * *"
    handler: http
    url: /api/cron/report
    timeout: 60

  - name: weekly-summary
    schedule: "0 9 * * 1"
    timezone: America/New_York
    handler: http
    url: /api/cron/weekly-summary
    timeout: 300

services:
  api:
    runtime: cloud_run

  jobs:
    runtime: cloud_run_jobs
    image: gcr.io/my-project/jobs
```

## Sources

- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Amazon EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/)
- [Vercel Cron Jobs](https://vercel.com/docs/cron-jobs)
- [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cron Expression Generator](https://crontab.guru/)
