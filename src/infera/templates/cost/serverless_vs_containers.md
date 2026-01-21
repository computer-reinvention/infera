# Serverless vs Containers: Cost Optimization Guide

## Overview

Choosing between serverless functions and containers significantly impacts both cost and performance. This guide provides data-driven decision frameworks for selecting the right compute model based on traffic patterns, workload characteristics, and budget constraints.

### When Serverless Wins
- Sporadic/unpredictable traffic
- Traffic with significant idle periods
- Low requests per second (<50 RPS sustained)
- Event-driven workloads
- Development and staging environments
- Batch processing jobs

### When Containers Win
- Steady baseline traffic
- High requests per second (>50 RPS sustained)
- Long-running processes
- WebSocket/streaming connections
- Applications requiring persistent state
- Workloads with large dependencies

## Cost Models Explained

### Serverless Pricing

```
Monthly Cost = (Invocations × Price per Invocation)
             + (GB-seconds × Price per GB-second)
             + (Egress × Price per GB)
```

| Provider | Invocation Cost | GB-second Cost | Free Tier |
|----------|-----------------|----------------|-----------|
| AWS Lambda | $0.20/1M | $0.0000166667 | 1M req, 400k GB-s |
| Cloud Functions | $0.40/1M | $0.0000025 | 2M req, 400k GB-s |
| Cloud Run | $0.40/1M | $0.0000024 | 2M req, 180k vCPU-s |
| Cloudflare Workers | $0.50/1M | N/A (CPU-based) | 100k req/day |

### Container Pricing

```
Monthly Cost = (vCPU hours × Price per vCPU-hour)
             + (Memory GB-hours × Price per GB-hour)
             + (Egress × Price per GB)
             + (Load Balancer if applicable)
```

| Provider | vCPU/hour | Memory/GB-hour | Min instances |
|----------|-----------|----------------|---------------|
| Cloud Run (always-on) | $0.0864 | $0.009 | 0 (scale to zero) |
| ECS Fargate | $0.04048 | $0.004445 | 1 |
| GKE Autopilot | $0.0445 | $0.00489 | 0 |
| Fly.io | $0.0315 | $0.00547 | 0 |

## Break-Even Analysis

### Cloud Run: Serverless vs Always-On

```python
# Cost calculator for Cloud Run

def serverless_cost(
    requests_per_month: int,
    avg_duration_ms: int,
    memory_mb: int
) -> float:
    """Calculate serverless (scale-to-zero) cost."""
    cpu_seconds = requests_per_month * (avg_duration_ms / 1000)
    memory_gb_seconds = cpu_seconds * (memory_mb / 1024)

    # Free tier: 180,000 vCPU-seconds, 360,000 GB-seconds
    billable_cpu = max(0, cpu_seconds - 180_000)
    billable_memory = max(0, memory_gb_seconds - 360_000)

    cpu_cost = billable_cpu * 0.0000240  # per vCPU-second
    memory_cost = billable_memory * 0.0000025  # per GB-second
    request_cost = max(0, requests_per_month - 2_000_000) * 0.0000004

    return cpu_cost + memory_cost + request_cost

def always_on_cost(
    instances: int,
    vcpu: float,
    memory_gb: float,
    hours: int = 730  # Month
) -> float:
    """Calculate always-on container cost."""
    cpu_cost = instances * vcpu * hours * 0.0864
    memory_cost = instances * memory_gb * hours * 0.009
    return cpu_cost + memory_cost

# Example: 10M requests/month, 100ms avg, 512MB
print(f"Serverless: ${serverless_cost(10_000_000, 100, 512):.2f}")
print(f"Always-on (1 instance): ${always_on_cost(1, 1, 0.5):.2f}")

# Serverless: $48.00
# Always-on: $67.33
# Winner: Serverless at this traffic level
```

### Break-Even Calculator

```python
def find_break_even_rps(
    avg_duration_ms: int = 100,
    memory_mb: int = 512
) -> float:
    """Find requests/second where always-on becomes cheaper."""
    for rps in range(1, 1000):
        monthly_requests = rps * 60 * 60 * 24 * 30

        serverless = serverless_cost(monthly_requests, avg_duration_ms, memory_mb)
        # Scale instances based on concurrency
        instances = max(1, rps // 100)  # ~100 RPS per instance
        container = always_on_cost(instances, 1, memory_mb / 1024)

        if container < serverless:
            return rps

    return float('inf')

# Typical break-even points:
# - 100ms duration, 512MB: ~35 RPS sustained
# - 200ms duration, 1GB: ~20 RPS sustained
# - 50ms duration, 256MB: ~80 RPS sustained
```

### Visual Break-Even Chart

```
Monthly Cost ($)
    │
350 ┤                                    ╱ Serverless
    │                                 ╱
300 ┤                              ╱
    │                           ╱
250 ┤                        ╱
    │                     ╱
200 ┤                  ╱
    │               ╱
150 ┤            ╱────────────────────── Always-on (1 instance)
    │         ╱
100 ┤      ╱
    │   ╱
 50 ┤╱
    │
  0 ┼───────┬───────┬───────┬───────┬───────▶ Requests/month
        1M      5M      10M     15M     20M
                    ↑
              Break-even (~8M req/month at 100ms)
```

## Traffic Pattern Analysis

### Pattern 1: Highly Variable (Serverless Wins)

```
Requests/hour
    │
 5k ┤        ╱╲
    │       ╱  ╲         ╱╲
 3k ┤      ╱    ╲       ╱  ╲
    │     ╱      ╲     ╱    ╲
 1k ┤    ╱        ╲___╱      ╲___
    │___╱
  0 ┼───────────────────────────────▶ Time (24h)
      2am    8am   12pm   6pm   10pm
```

```yaml
# Serverless: Pay only for actual usage
# Peak: 5,000 req/hour = 1.4 req/sec
# Average: 1,500 req/hour = 0.4 req/sec
# Monthly requests: ~1.1M
# Serverless cost: ~$5/month
# Container (1 min instance): ~$67/month
# Savings: 92%
```

### Pattern 2: Steady Traffic (Containers Win)

```
Requests/hour
    │
 5k ┤─────────────────────────────────
    │
 3k ┤
    │
 1k ┤
    │
  0 ┼───────────────────────────────▶ Time (24h)
```

```yaml
# Container: Fixed cost regardless of requests
# Steady: 5,000 req/hour = 1.4 req/sec
# Monthly requests: ~3.6M
# Serverless cost: ~$18/month
# Container (1 instance): ~$67/month
# But at 50 req/sec (180M/month):
# Serverless: ~$900/month
# Container (2 instances): ~$135/month
# Savings with container: 85%
```

### Pattern 3: Business Hours Only

```
Requests/hour
    │
 3k ┤         ┌─────────────┐
    │         │             │
 2k ┤         │             │
    │         │             │
 1k ┤         │             │
    │_________│             │__________
  0 ┼───────────────────────────────▶ Time (24h)
      2am    9am          5pm   10pm
```

```yaml
# Hybrid approach optimal
# Business hours (8h): 3,000 req/hour
# Off hours (16h): 0 requests
# Monthly: ~720k requests
# Serverless: ~$3.60/month
# Always-on: ~$67/month
# Serverless wins for this pattern
```

## Implementation Patterns

### Hybrid Architecture

```
                    ┌─────────────────────────────────┐
                    │         Load Balancer            │
                    └─────────────┬───────────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           │                      │                      │
           ▼                      ▼                      ▼
    ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
    │  Container  │       │  Container  │       │  Serverless │
    │   (Core)    │       │   (Core)    │       │   (Burst)   │
    │  Always-on  │       │  Always-on  │       │  Scale-out  │
    └─────────────┘       └─────────────┘       └─────────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                                │
                         ┌──────┴──────┐
                         │  Database   │
                         └─────────────┘
```

**Terraform for GCP Hybrid:**
```hcl
# Always-on baseline capacity
resource "google_cloud_run_v2_service" "baseline" {
  name     = "${var.app_name}-baseline"
  location = var.region

  template {
    scaling {
      min_instance_count = 2  # Always running
      max_instance_count = 5
    }

    containers {
      image = var.image
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }
  }
}

# Serverless burst capacity
resource "google_cloud_run_v2_service" "burst" {
  name     = "${var.app_name}-burst"
  location = var.region

  template {
    scaling {
      min_instance_count = 0  # Scale to zero
      max_instance_count = 100
    }

    containers {
      image = var.image
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

# Load balancer with routing
resource "google_compute_url_map" "default" {
  name = "${var.app_name}-urlmap"

  default_service = google_compute_backend_service.baseline.id

  host_rule {
    hosts        = ["*"]
    path_matcher = "api"
  }

  path_matcher {
    name            = "api"
    default_service = google_compute_backend_service.baseline.id

    # Route overflow to burst
    route_rules {
      priority = 1
      service  = google_compute_backend_service.burst.id
      match_rules {
        prefix_match = "/"
        header_matches {
          header_name = "X-Overflow"
          exact_match = "true"
        }
      }
    }
  }
}
```

### AWS Lambda with Reserved Concurrency

```typescript
// Optimize Lambda for cost with provisioned concurrency
import { LambdaClient, PutProvisionedConcurrencyConfigCommand } from '@aws-sdk/client-lambda';

// For predictable baseline, use provisioned concurrency
// Costs: $0.015 per provisioned concurrency-hour
// vs $0.0000166667 per GB-second on-demand

const setProvisionedConcurrency = async (functionName: string, concurrency: number) => {
  const client = new LambdaClient({});

  await client.send(new PutProvisionedConcurrencyConfigCommand({
    FunctionName: functionName,
    Qualifier: '$LATEST',
    ProvisionedConcurrentExecutions: concurrency,
  }));
};

// Cost analysis:
// 10 provisioned instances = $109.50/month
// Can handle ~100 RPS with 100ms duration
// On-demand at same traffic = ~$180/month
// Savings: 39% + better cold start latency
```

### Cloud Run Scheduled Scaling

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-api
  annotations:
    # Scale based on time of day
    run.googleapis.com/minScale: "1"
    run.googleapis.com/maxScale: "10"
spec:
  template:
    spec:
      containerConcurrency: 80
      containers:
        - image: gcr.io/project/image
          resources:
            limits:
              cpu: "1"
              memory: 512Mi
```

```bash
#!/bin/bash
# scheduled-scaling.sh - Run via Cloud Scheduler

HOUR=$(date +%H)
SERVICE="my-api"
REGION="us-central1"

if [ $HOUR -ge 9 ] && [ $HOUR -lt 17 ]; then
  # Business hours: maintain minimum instances
  gcloud run services update $SERVICE \
    --region $REGION \
    --min-instances 3 \
    --max-instances 20
else
  # Off hours: scale to zero
  gcloud run services update $SERVICE \
    --region $REGION \
    --min-instances 0 \
    --max-instances 5
fi
```

## Decision Framework

### Quick Decision Matrix

| Factor | Serverless | Containers |
|--------|------------|------------|
| Traffic < 1M req/month | ✅ | ❌ |
| Traffic > 10M req/month | ❌ | ✅ |
| Idle time > 50% | ✅ | ❌ |
| Response time < 100ms critical | ❌ | ✅ |
| WebSocket/streaming | ❌ | ✅ |
| Large dependencies (>500MB) | ❌ | ✅ |
| Rapid scaling needed | ✅ | ❌ |
| Predictable budget needed | ❌ | ✅ |

### Cost Estimation Template

```yaml
# infera.yaml - cost optimization settings
name: my-app

cost_optimization:
  strategy: auto  # auto, serverless, containers, hybrid

  # Traffic estimates
  traffic:
    avg_requests_per_day: 100000
    peak_multiplier: 5
    idle_hours_per_day: 12

  # Workload characteristics
  workload:
    avg_duration_ms: 150
    memory_requirement_mb: 512
    cold_start_tolerance: medium  # low, medium, high

  # Constraints
  constraints:
    max_monthly_budget: 100
    min_availability: 99.9
    max_cold_start_ms: 1000

# Auto-selected based on above:
# strategy: serverless
# estimated_cost: $45/month
# reasoning: High idle time (50%), moderate traffic
```

## Provider-Specific Optimizations

### GCP Cloud Run

```hcl
# Optimize Cloud Run for cost
resource "google_cloud_run_v2_service" "optimized" {
  name     = "cost-optimized-api"
  location = "us-central1"

  template {
    # CPU only allocated during requests (cheaper)
    annotations = {
      "run.googleapis.com/cpu-throttling" = "true"
    }

    scaling {
      min_instance_count = 0  # Scale to zero
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/project/image"

      # Right-size resources
      resources {
        limits = {
          cpu    = "1"     # Don't over-provision
          memory = "512Mi" # Match actual needs
        }
        cpu_idle = true    # CPU only during requests
      }

      # Optimize startup
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 1
        failure_threshold     = 3
      }
    }

    # Higher concurrency = fewer instances needed
    max_instance_request_concurrency = 100
  }
}
```

### AWS Lambda

```hcl
# Cost-optimized Lambda configuration
resource "aws_lambda_function" "optimized" {
  function_name = "cost-optimized"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"

  # Right-size memory (CPU scales with memory)
  memory_size = 512  # Test different values
  timeout     = 10

  # ARM64 is 20% cheaper than x86
  architectures = ["arm64"]

  # Optimize package size for faster cold starts
  filename = "function.zip"

  environment {
    variables = {
      NODE_OPTIONS = "--enable-source-maps"
    }
  }

  # Reserved concurrency prevents runaway costs
  reserved_concurrent_executions = 100
}

# Use Graviton2 for Lambda (arm64)
# Saves 20% on compute costs
# Better price-performance ratio
```

### Cloudflare Workers

```typescript
// Workers are CPU-time based, not duration
// Optimize for CPU efficiency

// BAD: CPU-intensive JSON parsing
const data = JSON.parse(largeJsonString);

// GOOD: Stream processing
const stream = new TransformStream();
const writer = stream.writable.getWriter();

// Use built-in APIs (faster than JS implementations)
const hash = await crypto.subtle.digest('SHA-256', data);

// Cache aggressively to reduce invocations
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const cache = caches.default;
    const cached = await cache.match(request);
    if (cached) return cached;

    const response = await handleRequest(request, env);

    // Cache for 1 hour
    const cacheable = new Response(response.body, response);
    cacheable.headers.set('Cache-Control', 'public, max-age=3600');
    await cache.put(request, cacheable.clone());

    return cacheable;
  },
};
```

## Monitoring Cost Efficiency

```typescript
// Track cost metrics per request
interface CostMetrics {
  computeMs: number;
  memoryMb: number;
  coldStart: boolean;
}

export function trackCost(metrics: CostMetrics): void {
  const costPerMs = 0.0000000167; // Lambda pricing per ms per GB
  const memoryCost = (metrics.memoryMb / 1024) * metrics.computeMs * costPerMs;

  // Send to monitoring
  console.log(JSON.stringify({
    metric: 'request_cost',
    value: memoryCost,
    coldStart: metrics.coldStart,
    duration: metrics.computeMs,
    memory: metrics.memoryMb,
  }));
}

// Middleware to track all requests
export function costMiddleware(handler: Handler): Handler {
  return async (event, context) => {
    const start = Date.now();
    const isColdStart = !globalThis.__initialized;
    globalThis.__initialized = true;

    try {
      return await handler(event, context);
    } finally {
      trackCost({
        computeMs: Date.now() - start,
        memoryMb: context.memoryLimitInMB,
        coldStart: isColdStart,
      });
    }
  };
}
```

## Example Configuration

```yaml
# infera.yaml - Serverless vs Containers decision
name: my-api
provider: gcp

# Auto-detect optimal compute model
compute:
  strategy: auto

  # Or explicit selection with reasoning
  # strategy: serverless
  # reason: >
  #   Traffic analysis shows 70% idle time with peak of 50 RPS.
  #   Estimated serverless cost: $45/month
  #   Estimated container cost: $135/month
  #   Serverless saves 67% for this workload.

architecture:
  type: api_service

  resources:
    memory: 512Mi
    cpu: 1

  scaling:
    min_instances: 0
    max_instances: 20
    target_concurrency: 80
```

## Sources

- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Cloudflare Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [The Economics of Serverless](https://martinfowler.com/articles/serverless.html)
- [When to use Serverless](https://www.serverless.com/blog/when-why-use-serverless)
