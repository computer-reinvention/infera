# Redis Cache

## Overview
Redis is an in-memory data store used for caching, session management, real-time analytics, and message queues. Managed Redis services provide high availability, automatic failover, and persistence without operational overhead.

**Use when:**
- Need sub-millisecond response times
- Caching frequently accessed data
- Session storage for distributed systems
- Real-time leaderboards or counters
- Pub/Sub messaging
- Rate limiting

**Don't use when:**
- Primary data store (use with a database)
- Data larger than available memory
- Complex querying requirements
- Strong durability requirements

## Detection Signals

```
Files:
- redis.conf, redis.yaml
- .redis-commander

Dependencies:
- redis, ioredis (Node.js)
- redis, aioredis (Python)
- go-redis/redis (Go)
- redis gem (Ruby)
- jedis, lettuce (Java)

Code Patterns:
- redis://, rediss://
- REDIS_URL, REDIS_HOST
- Redis.fromEnv(), createClient()
- SET, GET, HSET, LPUSH
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Redis Cache Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Web App │  │   API   │  │ Worker  │  │  Cron   │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  │       │            │            │            │           │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          │            │            │            │                │
│          └────────────┴──────┬─────┴────────────┘                │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                   Managed Redis                            │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │               Redis Cluster / Replica Set            │  │  │
│  │  │                                                      │  │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │  │
│  │  │  │   Primary   │  │   Replica   │  │   Replica   │ │  │  │
│  │  │  │   (R/W)     │◄─┤   (Read)    │  │   (Read)    │ │  │  │
│  │  │  │             │  │             │  │             │ │  │  │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘ │  │  │
│  │  │                                                      │  │  │
│  │  │  Features:                                          │  │  │
│  │  │  • Automatic failover                               │  │  │
│  │  │  • Persistence (RDB/AOF)                           │  │  │
│  │  │  • TLS encryption                                   │  │  │
│  │  │  • VPC connectivity                                 │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Memorystore (GCP) | ElastiCache (AWS) | Upstash | Redis Cloud |
|---------|-------------------|-------------------|---------|-------------|
| **Min Cost** | ~$36/mo | ~$12/mo | $0 (free tier) | $0 (free tier) |
| **Serverless** | No | Yes (new) | Yes | Partial |
| **Max Memory** | 300 GB | 6.1 TB | 10 GB free | 500 GB |
| **HA/Failover** | Yes | Yes | Built-in | Yes |
| **Cluster Mode** | Yes | Yes | No | Yes |
| **VPC** | Yes | Yes | No | Yes |
| **Edge** | No | No | Yes | No |

## GCP Memorystore Configuration

### Terraform Configuration

```hcl
# memorystore.tf

resource "google_project_service" "redis" {
  service            = "redis.googleapis.com"
  disable_on_destroy = false
}

resource "google_redis_instance" "main" {
  name           = "${var.project_name}-redis"
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_gb
  region         = var.region

  # Redis version
  redis_version = "REDIS_7_0"

  # High availability
  replica_count     = var.redis_tier == "STANDARD_HA" ? var.replica_count : 0
  read_replicas_mode = var.redis_tier == "STANDARD_HA" ? "READ_REPLICAS_ENABLED" : "READ_REPLICAS_DISABLED"

  # Networking
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  # Persistence (Standard tier only)
  persistence_config {
    persistence_mode    = "RDB"
    rdb_snapshot_period = "ONE_HOUR"
  }

  # Maintenance
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
      }
    }
  }

  # Auth
  auth_enabled = true

  # TLS
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  labels = {
    environment = var.environment
  }

  depends_on = [
    google_project_service.redis,
    google_service_networking_connection.private_vpc_connection,
  ]
}

# Store auth string in Secret Manager
resource "google_secret_manager_secret" "redis_auth" {
  secret_id = "${var.project_name}-redis-auth"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_auth" {
  secret      = google_secret_manager_secret.redis_auth.id
  secret_data = google_redis_instance.main.auth_string
}

# Variables
variable "redis_tier" {
  description = "Redis tier: BASIC or STANDARD_HA"
  type        = string
  default     = "BASIC"  # Use STANDARD_HA for production
}

variable "redis_memory_gb" {
  description = "Redis memory in GB"
  type        = number
  default     = 1
}

variable "replica_count" {
  description = "Number of read replicas (STANDARD_HA only)"
  type        = number
  default     = 1
}

# Outputs
output "redis_host" {
  value = google_redis_instance.main.host
}

output "redis_port" {
  value = google_redis_instance.main.port
}

output "redis_read_endpoint" {
  value = google_redis_instance.main.read_endpoint
}

output "redis_url" {
  value     = "rediss://:${google_redis_instance.main.auth_string}@${google_redis_instance.main.host}:${google_redis_instance.main.port}"
  sensitive = true
}
```

## AWS ElastiCache Configuration

### Terraform Configuration

```hcl
# elasticache.tf

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis-sg"
  description = "Security group for Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

# Replication Group (with failover)
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.project_name}-redis"
  description          = "Redis cluster for ${var.project_name}"

  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_replicas + 1
  port                 = 6379

  engine               = "redis"
  engine_version       = "7.0"
  parameter_group_name = aws_elasticache_parameter_group.redis7.name

  # Multi-AZ
  automatic_failover_enabled = var.redis_replicas > 0
  multi_az_enabled           = var.redis_replicas > 0

  # Security
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  # Auth
  auth_token                 = random_password.redis_auth.result
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  # Snapshots
  snapshot_retention_limit = 7
  snapshot_window          = "03:00-04:00"

  # Maintenance
  maintenance_window = "sun:04:00-sun:05:00"

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  tags = {
    Environment = var.environment
  }
}

resource "aws_elasticache_parameter_group" "redis7" {
  name   = "${var.project_name}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }
}

# Store auth token in Secrets Manager
resource "aws_secretsmanager_secret" "redis_auth" {
  name = "${var.project_name}/redis-auth"
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id     = aws_secretsmanager_secret.redis_auth.id
  secret_string = random_password.redis_auth.result
}

# Variables
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"  # cache.r6g.large for prod
}

variable "redis_replicas" {
  description = "Number of read replicas"
  type        = number
  default     = 0  # 1+ for HA
}

# Outputs
output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  value = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_url" {
  value     = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379"
  sensitive = true
}
```

## Upstash Configuration

### Serverless Redis (Upstash)

```bash
# Create via CLI or dashboard
# https://console.upstash.com

# Connection string format:
# rediss://default:password@endpoint.upstash.io:6379
```

### Terraform Configuration

```hcl
# upstash.tf

terraform {
  required_providers {
    upstash = {
      source  = "upstash/upstash"
      version = "~> 1.0"
    }
  }
}

provider "upstash" {
  email   = var.upstash_email
  api_key = var.upstash_api_key
}

resource "upstash_redis_database" "main" {
  database_name = var.project_name
  region        = "us-east-1"
  tls           = true
  eviction      = true  # Enable eviction when memory full
}

output "redis_endpoint" {
  value = upstash_redis_database.main.endpoint
}

output "redis_password" {
  value     = upstash_redis_database.main.password
  sensitive = true
}

output "redis_url" {
  value     = "rediss://default:${upstash_redis_database.main.password}@${upstash_redis_database.main.endpoint}:6379"
  sensitive = true
}
```

## Application Integration

### Node.js (ioredis)

```typescript
// redis.ts
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
  reconnectOnError(err) {
    const targetErrors = ['READONLY', 'ECONNRESET'];
    return targetErrors.some(e => err.message.includes(e));
  },
});

redis.on('error', (err) => console.error('Redis Error:', err));
redis.on('connect', () => console.log('Redis connected'));

export default redis;

// Cache wrapper
export async function cached<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlSeconds: number = 3600
): Promise<T> {
  const cached = await redis.get(key);
  if (cached) {
    return JSON.parse(cached);
  }

  const data = await fetcher();
  await redis.setex(key, ttlSeconds, JSON.stringify(data));
  return data;
}

// Usage
const user = await cached(
  `user:${userId}`,
  () => db.users.findUnique({ where: { id: userId } }),
  3600
);
```

### Node.js (Upstash - Edge Compatible)

```typescript
// For Cloudflare Workers, Vercel Edge, etc.
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

// Usage in Edge function
export async function GET(request: Request) {
  const cached = await redis.get<string>('my-key');
  if (cached) {
    return new Response(cached);
  }

  const data = 'fresh data';
  await redis.setex('my-key', 3600, data);
  return new Response(data);
}
```

### Python

```python
# redis_client.py
import redis
import json
import os
from functools import wraps

redis_client = redis.from_url(
    os.environ["REDIS_URL"],
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)


def cached(key_prefix: str, ttl: int = 3600):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"

            # Try to get from cache
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)

            # Call function and cache result
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator


# Usage
@cached("user", ttl=3600)
def get_user(user_id: str) -> dict:
    # Expensive database query
    return db.query(User).filter(User.id == user_id).first()
```

### Python (Async with aioredis)

```python
# redis_async.py
import aioredis
import os

redis_pool = None


async def init_redis():
    global redis_pool
    redis_pool = aioredis.from_url(
        os.environ["REDIS_URL"],
        encoding="utf-8",
        decode_responses=True,
        max_connections=10,
    )


async def close_redis():
    global redis_pool
    if redis_pool:
        await redis_pool.close()


async def get_redis():
    return redis_pool


# Usage with FastAPI
from fastapi import FastAPI, Depends

app = FastAPI()


@app.on_event("startup")
async def startup():
    await init_redis()


@app.on_event("shutdown")
async def shutdown():
    await close_redis()


@app.get("/cached/{key}")
async def get_cached(key: str):
    redis = await get_redis()
    value = await redis.get(f"cache:{key}")
    return {"value": value}
```

### Go

```go
// redis.go
package cache

import (
    "context"
    "encoding/json"
    "os"
    "time"

    "github.com/redis/go-redis/v9"
)

var client *redis.Client

func Init() {
    opt, err := redis.ParseURL(os.Getenv("REDIS_URL"))
    if err != nil {
        panic(err)
    }

    opt.PoolSize = 10
    opt.MinIdleConns = 2
    opt.DialTimeout = 5 * time.Second
    opt.ReadTimeout = 3 * time.Second
    opt.WriteTimeout = 3 * time.Second

    client = redis.NewClient(opt)

    // Verify connection
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    if err := client.Ping(ctx).Err(); err != nil {
        panic(err)
    }
}

func Close() {
    if client != nil {
        client.Close()
    }
}

func Client() *redis.Client {
    return client
}

// Cached fetches from cache or calls fetcher
func Cached[T any](ctx context.Context, key string, ttl time.Duration, fetcher func() (T, error)) (T, error) {
    var result T

    // Try cache first
    cached, err := client.Get(ctx, key).Result()
    if err == nil {
        if err := json.Unmarshal([]byte(cached), &result); err == nil {
            return result, nil
        }
    }

    // Fetch fresh data
    result, err = fetcher()
    if err != nil {
        return result, err
    }

    // Cache result
    data, _ := json.Marshal(result)
    client.SetEx(ctx, key, string(data), ttl)

    return result, nil
}
```

## Common Patterns

### Session Storage

```typescript
// Session middleware
import session from 'express-session';
import RedisStore from 'connect-redis';
import redis from './redis';

app.use(session({
  store: new RedisStore({ client: redis }),
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
  },
}));
```

### Rate Limiting

```typescript
// Rate limiter with sliding window
async function rateLimit(key: string, limit: number, windowMs: number): Promise<boolean> {
  const now = Date.now();
  const windowStart = now - windowMs;

  const pipeline = redis.pipeline();
  pipeline.zremrangebyscore(key, 0, windowStart);
  pipeline.zadd(key, now, `${now}`);
  pipeline.zcard(key);
  pipeline.expire(key, Math.ceil(windowMs / 1000));

  const results = await pipeline.exec();
  const count = results?.[2]?.[1] as number;

  return count <= limit;
}

// Usage
const allowed = await rateLimit(`ratelimit:${ip}`, 100, 60000); // 100 req/min
if (!allowed) {
  return res.status(429).json({ error: 'Too many requests' });
}
```

### Distributed Lock

```typescript
// Simple distributed lock using SET NX
async function acquireLock(lockKey: string, ttlMs: number): Promise<string | null> {
  const lockValue = crypto.randomUUID();
  const result = await redis.set(lockKey, lockValue, 'PX', ttlMs, 'NX');
  return result === 'OK' ? lockValue : null;
}

async function releaseLock(lockKey: string, lockValue: string): Promise<boolean> {
  // Use Lua script for atomic check-and-delete
  const script = `
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    else
      return 0
    end
  `;
  const result = await redis.eval(script, 1, lockKey, lockValue);
  return result === 1;
}

// Usage
const lockKey = `lock:order:${orderId}`;
const lockValue = await acquireLock(lockKey, 30000);
if (!lockValue) {
  throw new Error('Could not acquire lock');
}

try {
  await processOrder(orderId);
} finally {
  await releaseLock(lockKey, lockValue);
}
```

### Pub/Sub

```typescript
// Publisher
async function publishEvent(channel: string, event: object) {
  await redis.publish(channel, JSON.stringify(event));
}

// Subscriber
const subscriber = redis.duplicate();

subscriber.subscribe('orders', (err) => {
  if (err) console.error('Subscribe error:', err);
});

subscriber.on('message', (channel, message) => {
  const event = JSON.parse(message);
  console.log(`Received on ${channel}:`, event);
});
```

## Cost Breakdown

### GCP Memorystore

| Configuration | Memory | Tier | Monthly Cost |
|--------------|--------|------|--------------|
| Development | 1 GB | BASIC | ~$36 |
| Small Prod | 5 GB | STANDARD_HA | ~$250 |
| Medium Prod | 16 GB | STANDARD_HA | ~$800 |
| Large Prod | 50 GB | STANDARD_HA | ~$2,500 |

### AWS ElastiCache

| Configuration | Node Type | Nodes | Monthly Cost |
|--------------|-----------|-------|--------------|
| Development | cache.t3.micro | 1 | ~$12 |
| Small Prod | cache.t3.small | 2 | ~$50 |
| Medium Prod | cache.r6g.large | 3 | ~$450 |
| Large Prod | cache.r6g.xlarge | 3 | ~$900 |

### Upstash

| Plan | Commands/day | Max Memory | Monthly Cost |
|------|-------------|------------|--------------|
| Free | 10K | 256 MB | $0 |
| Pay-as-you-go | Unlimited | 10 GB | ~$0.20/100K commands |
| Pro | Unlimited | Configurable | $280+ |

## Best Practices

### Connection Management

```typescript
// GOOD - Single connection/pool
const redis = new Redis(process.env.REDIS_URL);
export default redis;

// BAD - Creating connections per request
export function getRedis() {
  return new Redis(process.env.REDIS_URL); // Don't do this
}
```

### Key Naming

```typescript
// GOOD - Namespaced, descriptive keys
const userKey = `user:${userId}:profile`;
const cacheKey = `cache:api:users:${userId}`;
const sessionKey = `session:${sessionId}`;

// BAD - Generic, collision-prone keys
const key = userId; // Don't do this
```

### TTL Strategy

```typescript
// Always set TTL for cache data
await redis.setex(`cache:${key}`, 3600, value);

// Use TTL for rate limiting
await redis.expire(`ratelimit:${ip}`, 60);

// Don't cache forever
// BAD: await redis.set(key, value);
```

## Common Mistakes

1. **No connection pooling** - Creating connections per request
2. **Missing TTL on cache keys** - Memory grows unbounded
3. **Storing large values** - Redis is for small, fast data
4. **Not handling connection errors** - No retry logic
5. **Using KEYS command in production** - Blocks Redis, use SCAN
6. **No TLS in production** - Data transmitted in plain text
7. **Missing auth token** - Anyone can access your Redis
8. **Not using pipelines** - Many round trips for batch operations
9. **Ignoring eviction policy** - Wrong data gets evicted
10. **No monitoring** - Missing memory/connection alerts

## Example Configuration

```yaml
# infera.yaml
project_name: my-api
provider: gcp
region: us-central1
environment: production

cache:
  type: redis
  provider: memorystore

  instance:
    memory_size_gb: 5
    tier: STANDARD_HA
    replica_count: 1

  version: "REDIS_7_0"

  security:
    auth_enabled: true
    transit_encryption: true

  persistence:
    mode: RDB
    snapshot_period: ONE_HOUR

  networking:
    vpc_connector: true

application:
  service: cloud_run
  vpc_connector: default

  env:
    REDIS_URL:
      from_secret: redis-url
```

## Sources

- [Google Cloud Memorystore](https://cloud.google.com/memorystore/docs/redis)
- [Amazon ElastiCache for Redis](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/)
- [Upstash Documentation](https://docs.upstash.com/)
- [Redis Best Practices](https://redis.io/docs/management/optimization/)
- [ioredis Documentation](https://github.com/redis/ioredis)
- [Redis Patterns](https://redis.io/docs/manual/patterns/)
