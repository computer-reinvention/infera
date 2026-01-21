# Cold Start Optimization

## Overview

Cold starts occur when serverless functions or containers must initialize before processing requests, adding latency from 100ms to several seconds. This guide covers strategies to minimize cold start impact on both user experience and cost.

### When Cold Starts Matter
- User-facing APIs with latency SLAs
- Real-time applications (chat, gaming)
- Payment processing and checkout flows
- Interactive web applications
- Mobile app backends

### When Cold Starts Are Acceptable
- Background job processing
- Scheduled tasks (cron)
- Event-driven pipelines
- Batch processing
- Internal tooling with tolerant users

## Cold Start Causes & Duration

### By Platform

| Platform | Typical Cold Start | Factors |
|----------|-------------------|---------|
| AWS Lambda (Node.js) | 100-500ms | Package size, VPC, memory |
| AWS Lambda (Python) | 200-800ms | Dependencies, layers |
| AWS Lambda (Java) | 3-10s | JVM startup, framework |
| Cloud Run | 500ms-2s | Container size, startup probes |
| Cloud Functions | 200-800ms | Similar to Lambda |
| Cloudflare Workers | ~0ms | V8 isolates, no cold start |
| Vercel Functions | 100-500ms | Similar to Lambda |

### Cold Start Timeline

```
┌─────────────────────────────────────────────────────────┐
│                  Cold Start Breakdown                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Request ──▶ [Infrastructure] ──▶ [Runtime] ──▶ [App]   │
│               │                    │              │      │
│               │                    │              │      │
│               ▼                    ▼              ▼      │
│            ~200ms              ~100ms          ~200ms    │
│         (Container           (Node.js/       (Framework │
│          download,           Python          init, DB   │
│          network)            init)           connect)   │
│                                                          │
│  Total Cold Start: ~500ms                               │
│  Warm Request: ~10ms                                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Optimization Strategies

### Strategy 1: Minimize Package Size

```dockerfile
# BAD: Large image with dev dependencies
FROM node:18
WORKDIR /app
COPY package*.json ./
RUN npm install  # Includes devDependencies
COPY . .
CMD ["node", "server.js"]
# Image size: ~1.2GB, Cold start: ~3s

# GOOD: Multi-stage build, production only
FROM node:18-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

FROM gcr.io/distroless/nodejs18-debian11
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/server.js ./
CMD ["server.js"]
# Image size: ~150MB, Cold start: ~500ms
```

**Lambda Layer Optimization:**
```bash
# Create optimized Lambda layer
mkdir -p layer/nodejs
cd layer/nodejs

# Install only production dependencies
npm init -y
npm install --production express aws-sdk

# Remove unnecessary files
find . -name "*.md" -delete
find . -name "*.ts" -delete
find . -name "test*" -type d -exec rm -rf {} +
find . -name "example*" -type d -exec rm -rf {} +

# Package layer
cd ..
zip -r ../layer.zip .

# Deploy layer
aws lambda publish-layer-version \
    --layer-name optimized-deps \
    --zip-file fileb://layer.zip \
    --compatible-runtimes nodejs18.x
```

### Strategy 2: Lazy Loading

```typescript
// BAD: Import everything at top level
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { SESClient } from '@aws-sdk/client-ses';
import OpenAI from 'openai';

// All clients initialized on cold start

// GOOD: Lazy import when needed
let s3Client: S3Client | null = null;
let dynamoClient: DynamoDBClient | null = null;

function getS3Client(): S3Client {
  if (!s3Client) {
    const { S3Client } = require('@aws-sdk/client-s3');
    s3Client = new S3Client({});
  }
  return s3Client;
}

function getDynamoClient(): DynamoDBClient {
  if (!dynamoClient) {
    const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
    dynamoClient = new DynamoDBClient({});
  }
  return dynamoClient;
}

export async function handler(event: any) {
  // Only initialize what's needed for this request
  if (event.action === 's3') {
    const client = getS3Client();
    // Use S3...
  } else if (event.action === 'dynamo') {
    const client = getDynamoClient();
    // Use DynamoDB...
  }
}
```

### Strategy 3: Connection Pooling Outside Handler

```typescript
// Lambda with persistent connections
import { Pool } from 'pg';

// Initialize OUTSIDE handler - persists across invocations
let pool: Pool | null = null;

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      host: process.env.DB_HOST,
      database: process.env.DB_NAME,
      user: process.env.DB_USER,
      password: process.env.DB_PASSWORD,
      max: 1,  // Lambda: 1 connection per instance
      idleTimeoutMillis: 120000,
      connectionTimeoutMillis: 5000,
    });
  }
  return pool;
}

export async function handler(event: any) {
  const pool = getPool();  // Reuses existing pool on warm start

  const result = await pool.query('SELECT * FROM users WHERE id = $1', [event.userId]);

  return {
    statusCode: 200,
    body: JSON.stringify(result.rows[0]),
  };
}
```

### Strategy 4: Provisioned Concurrency (AWS Lambda)

```hcl
# Terraform for provisioned concurrency
resource "aws_lambda_function" "api" {
  function_name = "api-handler"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
  memory_size   = 1024
  timeout       = 30

  # Enable SnapStart for faster cold starts (Java)
  snap_start {
    apply_on = "PublishedVersions"
  }
}

resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.api.function_name
  function_version = aws_lambda_function.api.version
}

# Provisioned concurrency - always warm
resource "aws_lambda_provisioned_concurrency_config" "api" {
  function_name                     = aws_lambda_function.api.function_name
  qualifier                         = aws_lambda_alias.live.name
  provisioned_concurrent_executions = 5

  # Cost: $0.015/hour per provisioned instance
  # 5 instances = $54.75/month
}

# Auto-scaling provisioned concurrency
resource "aws_appautoscaling_target" "lambda" {
  max_capacity       = 50
  min_capacity       = 5
  resource_id        = "function:${aws_lambda_function.api.function_name}:${aws_lambda_alias.live.name}"
  scalable_dimension = "lambda:function:ProvisionedConcurrency"
  service_namespace  = "lambda"
}

resource "aws_appautoscaling_policy" "lambda" {
  name               = "lambda-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.lambda.resource_id
  scalable_dimension = aws_appautoscaling_target.lambda.scalable_dimension
  service_namespace  = aws_appautoscaling_target.lambda.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 0.7  # 70% utilization target

    predefined_metric_specification {
      predefined_metric_type = "LambdaProvisionedConcurrencyUtilization"
    }
  }
}
```

### Strategy 5: Cloud Run Minimum Instances

```hcl
# Cloud Run with minimum instances
resource "google_cloud_run_v2_service" "api" {
  name     = "api-service"
  location = "us-central1"

  template {
    scaling {
      min_instance_count = 2  # Always keep 2 warm
      max_instance_count = 100
    }

    containers {
      image = "gcr.io/project/api:latest"

      # Startup optimization
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 1
        timeout_seconds       = 1
        failure_threshold     = 3
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = false  # CPU always allocated (faster response)
      }
    }

    # Container startup optimization
    max_instance_request_concurrency = 80
    timeout                          = "300s"
  }
}

# Cost: ~$50/month for 2 minimum instances (512Mi, 1 CPU)
```

### Strategy 6: Cloudflare Workers (Zero Cold Start)

```typescript
// Workers use V8 isolates - no cold start
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Instantly available - no initialization delay
    const url = new URL(request.url);

    if (url.pathname === '/api/users') {
      // D1 queries are fast even on first request
      const { results } = await env.DB.prepare(
        'SELECT * FROM users LIMIT 10'
      ).all();

      return Response.json(results);
    }

    return new Response('Not found', { status: 404 });
  },
};
```

### Strategy 7: Warming Functions

```typescript
// Keep functions warm with scheduled pings
// CloudWatch Events rule: rate(5 minutes)

export async function warmer(event: any) {
  // Check if this is a warming invocation
  if (event.source === 'serverless-plugin-warmup') {
    console.log('Warming invocation');
    return { statusCode: 200, body: 'Warmed' };
  }

  // Regular handler logic
  return handleRequest(event);
}
```

```yaml
# serverless.yml with warmup plugin
plugins:
  - serverless-plugin-warmup

custom:
  warmup:
    default:
      enabled: true
      events:
        - schedule: rate(5 minutes)
      concurrency: 5  # Keep 5 instances warm
      prewarm: true   # Warm on deploy

functions:
  api:
    handler: handler.main
    warmup:
      default:
        enabled: true
```

## Language-Specific Optimizations

### Node.js

```javascript
// Use esbuild for smaller bundles
// esbuild.config.js
const esbuild = require('esbuild');

esbuild.build({
  entryPoints: ['src/handler.ts'],
  bundle: true,
  minify: true,
  platform: 'node',
  target: 'node18',
  outfile: 'dist/handler.js',
  external: ['aws-sdk'],  // Already in Lambda runtime
  treeShaking: true,
});

// Result: ~100KB vs ~5MB with node_modules
```

### Python

```python
# Use slim dependencies
# requirements.txt
boto3  # Skip - already in Lambda
botocore  # Skip - already in Lambda
requests  # Use urllib3 instead (smaller)
pydantic  # Heavy - consider dataclasses

# Optimize imports
# BAD
import pandas  # 150MB+, 5s+ cold start

# GOOD - only import what you need
from pandas import DataFrame, read_csv
```

```dockerfile
# Python Lambda container optimization
FROM public.ecr.aws/lambda/python:3.11 AS builder

# Install dependencies to /opt
COPY requirements.txt .
RUN pip install -r requirements.txt -t /opt/python \
    --no-cache-dir \
    --compile \
    --only-binary :all:

# Remove unnecessary files
RUN find /opt/python -name "*.pyc" -delete
RUN find /opt/python -name "__pycache__" -type d -exec rm -rf {} +
RUN find /opt/python -name "tests" -type d -exec rm -rf {} +
RUN find /opt/python -name "*.dist-info" -type d -exec rm -rf {} +

FROM public.ecr.aws/lambda/python:3.11
COPY --from=builder /opt/python /opt/python
COPY handler.py .
CMD ["handler.lambda_handler"]
```

### Java (with SnapStart)

```java
// Enable CRaC for SnapStart
import org.crac.Context;
import org.crac.Core;
import org.crac.Resource;

public class Handler implements RequestHandler<APIGatewayProxyRequestEvent, APIGatewayProxyResponseEvent>, Resource {

    private final DatabaseConnection db;

    public Handler() {
        // Initialize on cold start
        this.db = new DatabaseConnection();
        // Register for SnapStart checkpoint
        Core.getGlobalContext().register(this);
    }

    @Override
    public void beforeCheckpoint(Context<? extends Resource> context) {
        // Called before snapshot - close connections
        db.close();
    }

    @Override
    public void afterRestore(Context<? extends Resource> context) {
        // Called after restore - reconnect
        db.reconnect();
    }

    @Override
    public APIGatewayProxyResponseEvent handleRequest(
        APIGatewayProxyRequestEvent event,
        Context context
    ) {
        // Handle request
        return new APIGatewayProxyResponseEvent()
            .withStatusCode(200)
            .withBody("OK");
    }
}
```

```xml
<!-- pom.xml - Optimize for Lambda -->
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-shade-plugin</artifactId>
            <configuration>
                <createDependencyReducedPom>false</createDependencyReducedPom>
                <minimizeJar>true</minimizeJar>
                <filters>
                    <filter>
                        <artifact>*:*</artifact>
                        <excludes>
                            <exclude>META-INF/*.SF</exclude>
                            <exclude>META-INF/*.DSA</exclude>
                            <exclude>META-INF/*.RSA</exclude>
                        </excludes>
                    </filter>
                </filters>
            </configuration>
        </plugin>
    </plugins>
</build>
```

## Cost vs Latency Trade-offs

```
┌─────────────────────────────────────────────────────────┐
│         Cold Start Mitigation Cost Comparison            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Strategy                  Cost Impact    Cold Start     │
│  ──────────────────────────────────────────────────      │
│  No mitigation             $0             500ms-5s       │
│  Code optimization         $0             200ms-1s       │
│  Provisioned (5 units)     $55/month      ~0ms           │
│  Min instances (2)         $50/month      ~0ms           │
│  Warming pings             ~$1/month      100-200ms      │
│  Cloudflare Workers        $5/month       ~0ms           │
│                                                          │
│  Recommendation by use case:                             │
│  ─────────────────────────────────────────────────────   │
│  Internal APIs: Code optimization only                   │
│  User-facing: Provisioned concurrency or min instances   │
│  Edge/global: Cloudflare Workers                        │
│  Cost-sensitive: Warming pings + optimization           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Monitoring Cold Starts

```typescript
// Track cold starts in your application
let isWarm = false;

export async function handler(event: any) {
  const isColdStart = !isWarm;
  isWarm = true;

  const start = Date.now();

  try {
    const result = await processRequest(event);

    // Log metrics
    console.log(JSON.stringify({
      metric: 'request',
      cold_start: isColdStart,
      duration_ms: Date.now() - start,
    }));

    return result;
  } catch (error) {
    console.log(JSON.stringify({
      metric: 'error',
      cold_start: isColdStart,
      error: error.message,
    }));
    throw error;
  }
}
```

```sql
-- CloudWatch Logs Insights query
fields @timestamp, @message
| filter metric = 'request'
| stats
    count(*) as total,
    sum(cold_start) as cold_starts,
    avg(duration_ms) as avg_latency,
    pct(duration_ms, 95) as p95_latency
    by bin(1h)
| sort @timestamp desc
```

## Example Configuration

```yaml
# infera.yaml - Cold start optimization
name: api-service
provider: gcp

cold_start:
  optimization_level: aggressive  # none, basic, aggressive

  strategies:
    - min_instances: 2
    - lazy_loading: true
    - connection_pooling: true

  # Platform-specific
  cloud_run:
    min_instances: 2
    cpu_idle: false  # CPU always allocated
    startup_probe:
      path: /health
      period_seconds: 1

  lambda:
    provisioned_concurrency: 5
    snap_start: true  # Java only

build:
  optimization:
    minify: true
    tree_shaking: true
    external_modules:
      - aws-sdk  # Use Lambda runtime version
```

## Sources

- [AWS Lambda Cold Starts](https://docs.aws.amazon.com/lambda/latest/operatorguide/execution-environments.html)
- [AWS Lambda SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Cloud Run Cold Starts](https://cloud.google.com/run/docs/tips/general)
- [Cloudflare Workers Isolates](https://developers.cloudflare.com/workers/learning/how-workers-works/)
- [Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
- [Serverless Cold Start Analysis](https://mikhail.io/serverless/coldstarts/aws/)
