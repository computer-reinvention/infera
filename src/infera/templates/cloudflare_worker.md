# Cloudflare Worker

## Overview

This template is for deploying serverless functions and APIs using Cloudflare Workers. Workers run on Cloudflare's edge network, providing low latency globally without managing servers.

## Detection Signals

Use this template when you detect:
- `wrangler.toml` or `wrangler.jsonc` in the project
- JavaScript/TypeScript files with Worker syntax (`export default { fetch() }`)
- `package.json` with `wrangler` as a dependency
- API routes without a traditional backend framework
- Edge-first architecture patterns

## When to Choose Cloudflare vs GCP

| Use Cloudflare Workers When | Use GCP Cloud Run When |
|----------------------------|------------------------|
| Simple API/functions | Complex containerized apps |
| Global edge latency matters | Specific region requirements |
| No container needed | Need Docker/containers |
| < 10ms CPU time per request | Long-running processes |
| KV/D1 storage is sufficient | Need Cloud SQL/Postgres |

## Resources Needed

### Required
- **Cloudflare Account**: Free tier available
- **Worker Script**: Your JavaScript/TypeScript code
- **wrangler.toml**: Configuration file

### Optional
- **KV Namespace**: Key-value storage for caching/state
- **D1 Database**: SQLite-compatible serverless database
- **R2 Bucket**: S3-compatible object storage
- **Custom Domain**: Route worker to your domain
- **Secrets**: Environment variables for API keys

## Project Structure

```
my-worker/
├── wrangler.toml       # Wrangler configuration
├── src/
│   └── index.js        # Worker entry point
├── package.json
└── package-lock.json
```

## wrangler.toml Configuration

```toml
name = "my-worker"
main = "src/index.js"
compatibility_date = "2024-01-01"

# Optional: KV Namespace
[[kv_namespaces]]
binding = "MY_KV"
id = "xxxxxxxxxxxxxxxxxxxxx"

# Optional: D1 Database
[[d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# Optional: R2 Bucket
[[r2_buckets]]
binding = "MY_BUCKET"
bucket_name = "my-bucket"

# Optional: Environment variables
[vars]
ENVIRONMENT = "production"

# Optional: Secrets (set via wrangler secret put)
# SECRET_KEY = "set via CLI"
```

## Worker Code Structure

### Basic HTTP Handler
```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/api/hello") {
      return new Response(JSON.stringify({ message: "Hello!" }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response("Not Found", { status: 404 });
  }
};
```

### With KV Storage
```javascript
export default {
  async fetch(request, env, ctx) {
    // Read from KV
    const value = await env.MY_KV.get("key");

    // Write to KV
    await env.MY_KV.put("key", "value");

    return new Response(value);
  }
};
```

## Deployment Commands

```bash
# Login to Cloudflare (first time)
npx wrangler login

# Local development
npx wrangler dev

# Deploy to production
npx wrangler deploy

# Set secrets
npx wrangler secret put SECRET_NAME

# View logs
npx wrangler tail
```

## Best Practices

### Performance
1. Workers have 10ms CPU time limit (50ms on paid plan)
2. Use `ctx.waitUntil()` for background tasks
3. Leverage KV for caching frequently accessed data
4. Use streaming responses for large payloads

### Security
1. Use `wrangler secret put` for sensitive values
2. Validate all input from requests
3. Use Cloudflare Access for authentication if needed
4. Set appropriate CORS headers

### Code Organization
1. Keep worker code small (< 1MB compressed)
2. Use ES modules for code splitting
3. Consider Hono or itty-router for routing

## Cost Optimization

| Resource | Free Tier | Paid Plan |
|----------|-----------|-----------|
| Requests | 100k/day | $0.50/million |
| CPU Time | 10ms/request | 50ms/request |
| KV Reads | 100k/day | $0.50/million |
| KV Writes | 1k/day | $5/million |
| D1 Reads | 5M/day | $0.001/million |
| D1 Writes | 100k/day | $1/million |
| R2 Storage | 10GB | $0.015/GB/month |

**Tips**:
- Free tier is generous for small projects
- KV is cheaper than D1 for simple key-value data
- Use caching to reduce origin requests

## Common Mistakes

1. **Exceeding CPU limits**: Workers timeout after 10ms (free) or 50ms (paid)
2. **Blocking operations**: Use async/await properly
3. **Large responses**: Stream large responses instead of buffering
4. **Missing error handling**: Always handle errors gracefully

## Example Configuration

For a simple API worker:

```yaml
project_name: my-api
provider: cloudflare
architecture_type: worker

resources:
  - id: worker
    type: cloudflare_worker
    name: my-api-worker
    provider: cloudflare
    config:
      main: src/index.js
      compatibility_date: "2024-01-01"

  - id: kv
    type: cloudflare_kv
    name: my-api-cache
    provider: cloudflare
    config:
      binding: CACHE
```

## Estimated Costs

For a low-traffic API (10k requests/day):
- **Total: $0/month** (within free tier)

For a medium-traffic API (1M requests/day):
- Requests: ~$15/month
- KV (if used): ~$5/month
- **Total: ~$20/month**

For a high-traffic API (10M+ requests/day):
- Requests: ~$150/month
- KV (if used): ~$50/month
- **Total: ~$200/month**
