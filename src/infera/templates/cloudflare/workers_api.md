# Cloudflare Workers API

## Overview

Deploy serverless APIs on Cloudflare Workers running at the edge in 300+ locations worldwide. Ideal for low-latency APIs, microservices, and serverless backends with sub-millisecond cold starts.

## Detection Signals

Use this template when:
- `wrangler.toml` with worker configuration
- JavaScript/TypeScript with `export default { fetch() }`
- API-only project (no frontend)
- Need for global low-latency responses
- Existing Worker patterns in code

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────┐   │
         │         │   │    Worker (runs at nearest edge)        │   │
    User Request   │   │                                         │   │
                    │   │  ┌─────────────────────────────────┐    │   │
                    │   │  │  export default {               │    │   │
                    │   │  │    async fetch(request, env) {  │    │   │
                    │   │  │      // Your API logic          │    │   │
                    │   │  │    }                            │    │   │
                    │   │  │  }                              │    │   │
                    │   │  └─────────────────────────────────┘    │   │
                    │   │                                         │   │
                    │   │  Bindings: KV, D1, R2, Queues, etc.    │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   300+ edge locations • <50ms latency globally │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | API hosting | wrangler.toml |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Custom Domain | Production URL | Routes configuration |
| KV Namespace | Caching/sessions | Binding |
| D1 Database | SQL data | Binding |
| Secrets | API keys | wrangler secret |

## Configuration

### wrangler.toml
```toml
name = "my-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

# Custom domain routing
routes = [
  { pattern = "api.example.com/*", zone_name = "example.com" }
]

# Or use workers.dev subdomain
# workers_dev = true

# Environment variables
[vars]
ENVIRONMENT = "production"
API_VERSION = "v1"

# KV Namespace (optional)
[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"

# D1 Database (optional)
[[d1_databases]]
binding = "DB"
database_name = "my-api-db"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# Production environment overrides
[env.production]
vars = { ENVIRONMENT = "production" }

[env.staging]
vars = { ENVIRONMENT = "staging" }
```

### TypeScript Configuration
```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022"],
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "noEmit": true
  }
}
```

## Worker Implementation

### Basic API
```typescript
// src/index.ts
export interface Env {
  ENVIRONMENT: string;
  API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // CORS handling
    if (request.method === 'OPTIONS') {
      return handleCORS();
    }

    try {
      // Route handling
      const response = await handleRequest(request, env, url);
      return addCORSHeaders(response);
    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({ error: 'Internal server error' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

async function handleRequest(request: Request, env: Env, url: URL): Promise<Response> {
  const path = url.pathname;
  const method = request.method;

  // Health check
  if (path === '/health') {
    return Response.json({ status: 'healthy', env: env.ENVIRONMENT });
  }

  // API routes
  if (path === '/api/users' && method === 'GET') {
    return handleGetUsers(request, env);
  }

  if (path === '/api/users' && method === 'POST') {
    return handleCreateUser(request, env);
  }

  if (path.startsWith('/api/users/') && method === 'GET') {
    const id = path.split('/')[3];
    return handleGetUser(id, env);
  }

  return Response.json({ error: 'Not found' }, { status: 404 });
}

function handleCORS(): Response {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400',
    }
  });
}

function addCORSHeaders(response: Response): Response {
  const newResponse = new Response(response.body, response);
  newResponse.headers.set('Access-Control-Allow-Origin', '*');
  return newResponse;
}
```

### Using Hono Framework
```typescript
// src/index.ts
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';

type Bindings = {
  DB: D1Database;
  CACHE: KVNamespace;
  API_KEY: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Middleware
app.use('*', logger());
app.use('*', cors());

// Health check
app.get('/health', (c) => c.json({ status: 'healthy' }));

// API routes
app.get('/api/users', async (c) => {
  const { results } = await c.env.DB.prepare('SELECT * FROM users').all();
  return c.json(results);
});

app.get('/api/users/:id', async (c) => {
  const id = c.req.param('id');
  const user = await c.env.DB.prepare('SELECT * FROM users WHERE id = ?')
    .bind(id)
    .first();

  if (!user) {
    return c.json({ error: 'User not found' }, 404);
  }
  return c.json(user);
});

app.post('/api/users', async (c) => {
  const body = await c.req.json();
  const { name, email } = body;

  const result = await c.env.DB.prepare(
    'INSERT INTO users (name, email) VALUES (?, ?) RETURNING *'
  ).bind(name, email).first();

  return c.json(result, 201);
});

app.put('/api/users/:id', async (c) => {
  const id = c.req.param('id');
  const body = await c.req.json();
  const { name, email } = body;

  const result = await c.env.DB.prepare(
    'UPDATE users SET name = ?, email = ? WHERE id = ? RETURNING *'
  ).bind(name, email, id).first();

  return c.json(result);
});

app.delete('/api/users/:id', async (c) => {
  const id = c.req.param('id');
  await c.env.DB.prepare('DELETE FROM users WHERE id = ?').bind(id).run();
  return c.body(null, 204);
});

// 404 handler
app.notFound((c) => c.json({ error: 'Not found' }, 404));

// Error handler
app.onError((err, c) => {
  console.error('Error:', err);
  return c.json({ error: 'Internal server error' }, 500);
});

export default app;
```

### package.json
```json
{
  "name": "my-api",
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "test": "vitest"
  },
  "dependencies": {
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.0.0",
    "typescript": "^5.0.0",
    "wrangler": "^3.0.0",
    "vitest": "^1.0.0"
  }
}
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Local development
npx wrangler dev

# Deploy
npx wrangler deploy

# Deploy to staging
npx wrangler deploy --env staging

# Set secrets
npx wrangler secret put API_KEY
npx wrangler secret put DATABASE_URL

# View logs
npx wrangler tail

# List deployments
npx wrangler deployments list
```

## Best Practices

### Performance
1. Workers have no cold starts (instant execution)
2. Use `ctx.waitUntil()` for background tasks
3. Cache responses with Cache API
4. Keep bundle size small (< 1MB)

### Security
1. Use `wrangler secret` for sensitive data
2. Validate all input data
3. Implement rate limiting
4. Use appropriate CORS configuration

### Code Organization
1. Use a router framework (Hono, itty-router)
2. Separate concerns (routes, handlers, utils)
3. Use TypeScript for type safety
4. Write unit tests

## Cost Breakdown

| Component | Free Tier | Paid ($5/mo) |
|-----------|-----------|--------------|
| Requests | 100k/day | 10M/month included |
| CPU time | 10ms/req | 50ms/req |
| After included | - | $0.50/million |
| Script size | 1MB | 10MB |

### Example Costs
| Traffic | Monthly Cost |
|---------|--------------|
| 1M requests | $0 (free tier) |
| 50M requests | $25 |
| 100M requests | $50 |

## Common Mistakes

1. **Blocking operations**: Use async/await properly
2. **Large bundles**: Tree-shake unused code
3. **CPU limits**: 10ms free, 50ms paid per request
4. **No error handling**: Unhandled errors return 500
5. **Hardcoded secrets**: Use wrangler secret
6. **Missing CORS**: Browser requests fail

## Example Configuration

```yaml
project_name: my-api
provider: cloudflare
architecture_type: worker

resources:
  - id: api-worker
    type: cloudflare_worker
    name: my-api
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"
      routes:
        - pattern: "api.example.com/*"
          zone_name: "example.com"

  - id: database
    type: cloudflare_d1
    name: my-api-db
    provider: cloudflare
    config:
      binding: DB

  - id: cache
    type: cloudflare_kv
    name: my-api-cache
    provider: cloudflare
    config:
      binding: CACHE
```

## Sources

- [Workers Documentation](https://developers.cloudflare.com/workers)
- [Workers Runtime APIs](https://developers.cloudflare.com/workers/runtime-apis)
- [Hono Framework](https://hono.dev/)
