# Free Tier Maximization

## Overview

Strategic use of cloud provider free tiers to run production workloads at zero cost. This pattern combines multiple providers' generous free tiers to build complete applications without any infrastructure costs.

### When to Use
- MVPs and early-stage startups
- Side projects and personal tools
- Development and staging environments
- Low-traffic production applications (<100k requests/day)
- Learning and experimentation

### When NOT to Use
- High-traffic production workloads
- Business-critical systems requiring SLAs
- Applications requiring guaranteed performance
- When team time cost exceeds infrastructure savings

## Free Tier Comparison by Provider

### Compute Free Tiers

| Provider | Service | Free Allowance | Limits |
|----------|---------|----------------|--------|
| **GCP** | Cloud Run | 2M requests/month, 180k vCPU-seconds | 1 vCPU, 512MB max |
| **GCP** | Cloud Functions | 2M invocations/month | 400k GB-seconds |
| **AWS** | Lambda | 1M requests/month | 400k GB-seconds |
| **Cloudflare** | Workers | 100k requests/day | 10ms CPU time |
| **Vercel** | Serverless | 100k executions/month | 100GB bandwidth |
| **Netlify** | Functions | 125k executions/month | 100 hours |
| **Fly.io** | VMs | 3 shared VMs | 256MB RAM each |
| **Railway** | Containers | $5 credit/month | ~500 hours |
| **Render** | Web Service | 750 hours/month | 512MB RAM |

### Database Free Tiers

| Provider | Service | Free Allowance | Limits |
|----------|---------|----------------|--------|
| **Supabase** | PostgreSQL | 500MB storage | 2 projects |
| **PlanetScale** | MySQL | 5GB storage | 1B row reads/month |
| **Neon** | PostgreSQL | 512MB storage | 100 hours compute |
| **MongoDB Atlas** | MongoDB | 512MB storage | M0 cluster |
| **Upstash** | Redis | 10k commands/day | 256MB storage |
| **Turso** | SQLite | 8GB storage | 1B rows read/month |
| **Cloudflare** | D1 | 5M rows read/day | 100k writes/day |
| **Firebase** | Firestore | 1GB storage | 50k reads/day |

### Storage Free Tiers

| Provider | Service | Free Allowance | Limits |
|----------|---------|----------------|--------|
| **Cloudflare** | R2 | 10GB storage | 1M Class A ops |
| **AWS** | S3 | 5GB (12 months) | 20k GET, 2k PUT |
| **GCP** | Cloud Storage | 5GB (US regions) | Standard class only |
| **Vercel** | Blob | 250MB | Hobby plan |
| **Backblaze** | B2 | 10GB | 1GB egress/day |

### CDN/Edge Free Tiers

| Provider | Service | Free Allowance |
|----------|---------|----------------|
| **Cloudflare** | CDN | Unlimited |
| **Vercel** | Edge Network | 100GB bandwidth |
| **Netlify** | CDN | 100GB bandwidth |
| **Fastly** | CDN | $50 credit |

## Architecture Patterns

### Pattern 1: Full-Stack on Cloudflare (Recommended)

```
┌─────────────────────────────────────────────────────────┐
│                    Cloudflare Free                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  Pages   │    │ Workers  │    │    D1    │          │
│  │ (Static) │───▶│  (API)   │───▶│  (SQL)   │          │
│  └──────────┘    └──────────┘    └──────────┘          │
│                        │                                 │
│                        ▼                                 │
│                  ┌──────────┐                           │
│                  │    KV    │                           │
│                  │ (Cache)  │                           │
│                  └──────────┘                           │
│                                                          │
│  Cost: $0/month for 100k requests/day                   │
└─────────────────────────────────────────────────────────┘
```

**Cloudflare Pages + Workers + D1:**
```typescript
// worker.ts - API on Workers
import { Hono } from 'hono';

type Bindings = {
  DB: D1Database;
  CACHE: KVNamespace;
};

const app = new Hono<{ Bindings: Bindings }>();

app.get('/api/users', async (c) => {
  // Try cache first
  const cached = await c.env.CACHE.get('users');
  if (cached) {
    return c.json(JSON.parse(cached));
  }

  // Query D1
  const { results } = await c.env.DB.prepare(
    'SELECT * FROM users LIMIT 100'
  ).all();

  // Cache for 5 minutes
  await c.env.CACHE.put('users', JSON.stringify(results), {
    expirationTtl: 300,
  });

  return c.json(results);
});

export default app;
```

```toml
# wrangler.toml
name = "my-api"
main = "src/worker.ts"
compatibility_date = "2024-01-01"

[[d1_databases]]
binding = "DB"
database_name = "myapp"
database_id = "xxx"

[[kv_namespaces]]
binding = "CACHE"
id = "xxx"
```

### Pattern 2: Multi-Provider Stack

```
┌─────────────────────────────────────────────────────────┐
│                   Multi-Provider Free                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Vercel (Free)          Supabase (Free)                 │
│  ┌──────────┐           ┌──────────┐                    │
│  │ Next.js  │──────────▶│ Postgres │                    │
│  │ Frontend │           │   Auth   │                    │
│  └──────────┘           │ Realtime │                    │
│       │                 └──────────┘                    │
│       │                                                  │
│       │     Upstash (Free)    Cloudflare (Free)        │
│       │     ┌──────────┐      ┌──────────┐             │
│       └────▶│  Redis   │      │    R2    │             │
│             │ (Cache)  │      │ (Files)  │             │
│             └──────────┘      └──────────┘             │
│                                                          │
│  Cost: $0/month                                         │
└─────────────────────────────────────────────────────────┘
```

**Next.js with Supabase + Upstash:**
```typescript
// lib/db.ts
import { createClient } from '@supabase/supabase-js';
import { Redis } from '@upstash/redis';

// Supabase - Free PostgreSQL
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Upstash - Free Redis
export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_URL!,
  token: process.env.UPSTASH_REDIS_TOKEN!,
});

// Cloudflare R2 for file storage
export async function uploadToR2(file: Buffer, key: string) {
  const response = await fetch(
    `${process.env.R2_ENDPOINT}/${key}`,
    {
      method: 'PUT',
      body: file,
      headers: {
        'Authorization': `Bearer ${process.env.R2_TOKEN}`,
      },
    }
  );
  return response.ok;
}
```

### Pattern 3: GCP Free Tier Stack

```
┌─────────────────────────────────────────────────────────┐
│                    GCP Always Free                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  Cloud   │    │  Cloud   │    │Firestore │          │
│  │ Storage  │    │   Run    │───▶│ (NoSQL)  │          │
│  │ (Static) │    │  (API)   │    │ 1GB free │          │
│  └──────────┘    └──────────┘    └──────────┘          │
│       │               │                                  │
│       │               ▼                                  │
│       │         ┌──────────┐                            │
│       │         │  Secret  │                            │
│       └────────▶│ Manager  │                            │
│                 │ 6 active │                            │
│                 └──────────┘                            │
│                                                          │
│  Cost: $0/month for 2M requests                         │
└─────────────────────────────────────────────────────────┘
```

**Cloud Run with Firestore:**
```python
# main.py - FastAPI on Cloud Run
from fastapi import FastAPI
from google.cloud import firestore

app = FastAPI()
db = firestore.Client()

@app.get("/api/items")
async def get_items():
    items_ref = db.collection('items')
    docs = items_ref.limit(100).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@app.post("/api/items")
async def create_item(item: dict):
    doc_ref = db.collection('items').document()
    doc_ref.set(item)
    return {"id": doc_ref.id}
```

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# Deploy within free tier
gcloud run deploy api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --max-instances 2
```

## Optimization Strategies

### 1. Request Minimization

```typescript
// Aggressive caching to stay within free tiers
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_URL!,
  token: process.env.UPSTASH_REDIS_TOKEN!,
});

export async function cachedQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = 3600
): Promise<T> {
  // Check cache
  const cached = await redis.get<T>(key);
  if (cached) return cached;

  // Fetch and cache
  const data = await fetcher();
  await redis.setex(key, ttl, data);
  return data;
}

// Usage - reduces DB reads by 90%+
const users = await cachedQuery(
  'users:list',
  () => supabase.from('users').select('*'),
  300 // 5 minute cache
);
```

### 2. Database Read Optimization

```typescript
// PlanetScale optimization - 1B row reads/month free
import { connect } from '@planetscale/database';

const conn = connect({
  url: process.env.DATABASE_URL,
});

// BAD: Reads all columns
const bad = await conn.execute('SELECT * FROM posts');

// GOOD: Only needed columns, reduces row reads
const good = await conn.execute(
  'SELECT id, title, created_at FROM posts WHERE published = 1 LIMIT 20'
);

// BETTER: Use covering indexes
// CREATE INDEX idx_posts_list ON posts(published, created_at, id, title);
```

### 3. Edge Caching Strategy

```typescript
// Cloudflare Workers - cache API responses at edge
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const cacheKey = new Request(url.toString(), request);
    const cache = caches.default;

    // Check edge cache
    let response = await cache.match(cacheKey);
    if (response) {
      return response;
    }

    // Fetch from origin
    response = await handleRequest(request, env);

    // Cache successful responses
    if (response.status === 200) {
      const cached = new Response(response.body, response);
      cached.headers.set('Cache-Control', 'public, max-age=300');
      await cache.put(cacheKey, cached.clone());
    }

    return response;
  },
};
```

### 4. Serverless Cold Start Mitigation

```typescript
// Keep functions warm within free tier limits
// Cloudflare Workers Cron Trigger
export default {
  async scheduled(event: ScheduledEvent, env: Env) {
    // Ping every 5 minutes to keep warm
    // Uses ~8,640 requests/month (within free tier)
    await fetch('https://your-api.workers.dev/health');
  },
};
```

```toml
# wrangler.toml
[triggers]
crons = ["*/5 * * * *"]
```

## Free Tier Monitoring

### Usage Tracking Dashboard

```typescript
// Track usage to avoid overage
interface UsageMetrics {
  requests: number;
  dbReads: number;
  storage: number;
  bandwidth: number;
}

const LIMITS = {
  cloudflare: { requests: 100_000 }, // per day
  supabase: { dbReads: 50_000 },     // per day
  planetscale: { dbReads: 1_000_000_000 }, // per month
  vercel: { bandwidth: 100 * 1024 * 1024 * 1024 }, // 100GB
};

export async function checkUsage(): Promise<UsageMetrics> {
  // Cloudflare Analytics API
  const cfUsage = await fetch(
    'https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics/dashboard',
    { headers: { 'Authorization': `Bearer ${CF_TOKEN}` }}
  );

  // PlanetScale Insights API
  const psUsage = await fetch(
    'https://api.planetscale.com/v1/organizations/{org}/databases/{db}/insights',
    { headers: { 'Authorization': `${PS_TOKEN}` }}
  );

  return {
    requests: cfUsage.requests,
    dbReads: psUsage.rows_read,
    storage: 0,
    bandwidth: 0,
  };
}
```

### Alerts Before Overage

```yaml
# GitHub Actions - daily usage check
name: Free Tier Monitor
on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check usage
        run: |
          # Cloudflare Workers usage
          USAGE=$(curl -s "https://api.cloudflare.com/..." | jq '.requests')
          if [ $USAGE -gt 80000 ]; then
            echo "::warning::Approaching Cloudflare free tier limit: $USAGE/100k"
          fi

          # PlanetScale row reads
          READS=$(curl -s "https://api.planetscale.com/..." | jq '.rows_read')
          if [ $READS -gt 800000000 ]; then
            echo "::warning::Approaching PlanetScale limit: $READS/1B"
          fi
```

## Cost Comparison Table

| Stack | Monthly Cost | Limits | Best For |
|-------|--------------|--------|----------|
| Cloudflare Full Stack | $0 | 100k req/day | Edge-first apps |
| Vercel + Supabase | $0 | 100k functions | Next.js apps |
| GCP Free Tier | $0 | 2M req/month | Python/Go APIs |
| Fly.io + Turso | $0 | 3 VMs + 8GB DB | Full control |
| Railway + Neon | $5 | 500 hours + 512MB | Quick prototypes |

## Common Mistakes

### 1. Ignoring Egress Costs
```yaml
# BAD: Large response bodies
GET /api/data → Returns 5MB JSON

# GOOD: Paginated, compressed responses
GET /api/data?page=1&limit=20 → Returns 50KB JSON
```

### 2. Not Using Connection Pooling
```typescript
// BAD: New connection per request (exhausts limits)
export async function handler(req) {
  const client = new Client(DATABASE_URL);
  await client.connect();
  // ...
}

// GOOD: Reuse connections
const pool = new Pool({ connectionString: DATABASE_URL, max: 5 });
export async function handler(req) {
  const client = await pool.connect();
  // ...
  client.release();
}
```

### 3. Forgetting Region Selection
```bash
# BAD: Firestore in nam5 (not free)
gcloud firestore databases create --region=nam5

# GOOD: Free tier regions only
gcloud firestore databases create --region=us-east1
# Or: us-west1, us-central1
```

### 4. Exceeding Concurrent Execution Limits
```typescript
// BAD: Unbounded parallelism
await Promise.all(items.map(item => processItem(item)));

// GOOD: Controlled concurrency
import pLimit from 'p-limit';
const limit = pLimit(5);
await Promise.all(items.map(item => limit(() => processItem(item))));
```

## Example Configuration

```yaml
# infera.yaml - Free tier optimized
name: my-free-app
provider: cloudflare

architecture:
  type: edge_fullstack
  frontend:
    framework: next
    hosting: cloudflare_pages
  api:
    runtime: workers
    memory: 128MB
  database:
    type: d1
    backup: false
  cache:
    type: kv
    ttl: 300
  storage:
    type: r2

optimization:
  free_tier: true
  caching: aggressive
  compression: true

monitoring:
  usage_alerts: true
  thresholds:
    requests: 80000  # 80% of daily limit
    storage: 8GB     # 80% of R2 limit
```

## Migration Path

When traffic exceeds free tiers:

```
Free Tier → Pay-as-you-go → Reserved Capacity

Cloudflare Free    → Workers Paid ($5/month)   → Enterprise
Supabase Free      → Pro ($25/month)           → Team
Vercel Hobby       → Pro ($20/month)           → Enterprise
PlanetScale Free   → Scaler ($29/month)        → Business
```

## Sources

- [Cloudflare Workers Free Tier](https://developers.cloudflare.com/workers/platform/pricing/)
- [Supabase Pricing](https://supabase.com/pricing)
- [PlanetScale Pricing](https://planetscale.com/pricing)
- [GCP Free Tier](https://cloud.google.com/free)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [Vercel Pricing](https://vercel.com/pricing)
- [Fly.io Pricing](https://fly.io/docs/about/pricing/)
