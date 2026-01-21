# Cloudflare Pages with Functions

## Overview

Deploy full-stack applications using Pages for static frontend and Pages Functions for serverless API endpoints. Functions run on the same global network as your static assets, providing low-latency responses worldwide.

## Detection Signals

Use this template when:
- `functions/` directory in project root
- Static site with API requirements
- Full-stack framework with API routes
- Form handling or dynamic content needs
- BFF (Backend for Frontend) pattern

## Architecture

```
    Git Repository
         │
         ├── /src (Frontend)
         └── /functions (API)
         │
         ▼ (push)
    ┌─────────────────────────────────────────┐
    │         Cloudflare Pages                 │
    │                                         │
    │   ┌─────────────┐   ┌─────────────┐     │
    │   │   Static    │   │  Functions  │     │
    │   │   Assets    │   │  (Workers)  │     │
    │   │  (Frontend) │   │   (API)     │     │
    │   └──────┬──────┘   └──────┬──────┘     │
    │          │                 │            │
    │          └────────┬────────┘            │
    │                   │                     │
    │      ┌────────────┴────────────┐        │
    │      │    Global Edge Network   │        │
    │      │    (300+ locations)     │        │
    │      └─────────────────────────┘        │
    └─────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Pages Project | Site + Functions | Connected to Git repo |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| KV Namespace | Key-value storage | Binding in wrangler.toml |
| D1 Database | SQL database | Binding in wrangler.toml |
| R2 Bucket | Object storage | Binding in wrangler.toml |
| Custom Domain | Production domain | DNS records |

## Configuration

### Project Structure
```
my-fullstack-app/
├── package.json
├── wrangler.toml
├── src/                    # Frontend source
│   ├── App.jsx
│   └── index.html
├── dist/                   # Build output (gitignored)
├── functions/              # Pages Functions
│   ├── api/
│   │   ├── users.ts       # /api/users endpoint
│   │   ├── posts/
│   │   │   ├── index.ts   # /api/posts
│   │   │   └── [id].ts    # /api/posts/:id
│   │   └── [[path]].ts    # Catch-all /api/*
│   └── _middleware.ts      # Global middleware
└── public/                 # Static assets
```

### wrangler.toml
```toml
name = "my-fullstack-app"
pages_build_output_dir = "dist"
compatibility_date = "2024-01-01"

# KV Namespace binding
[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"

# D1 Database binding
[[d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# R2 Bucket binding
[[r2_buckets]]
binding = "STORAGE"
bucket_name = "my-bucket"

# Environment variables
[vars]
ENVIRONMENT = "production"

# Secrets (set via CLI: wrangler secret put)
# API_KEY = "set via CLI"
```

## Functions Implementation

### Basic API Endpoint
```typescript
// functions/api/hello.ts
export const onRequest: PagesFunction = async (context) => {
  return new Response(JSON.stringify({
    message: 'Hello from Pages Functions!',
    timestamp: new Date().toISOString()
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
};
```

### CRUD API with D1
```typescript
// functions/api/users/index.ts
interface Env {
  DB: D1Database;
}

export const onRequestGet: PagesFunction<Env> = async (context) => {
  const { results } = await context.env.DB.prepare(
    'SELECT * FROM users LIMIT 100'
  ).all();

  return Response.json(results);
};

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const body = await context.request.json();
  const { name, email } = body;

  const result = await context.env.DB.prepare(
    'INSERT INTO users (name, email) VALUES (?, ?) RETURNING *'
  ).bind(name, email).first();

  return Response.json(result, { status: 201 });
};

// functions/api/users/[id].ts
export const onRequestGet: PagesFunction<Env> = async (context) => {
  const { id } = context.params;

  const user = await context.env.DB.prepare(
    'SELECT * FROM users WHERE id = ?'
  ).bind(id).first();

  if (!user) {
    return Response.json({ error: 'User not found' }, { status: 404 });
  }

  return Response.json(user);
};

export const onRequestPut: PagesFunction<Env> = async (context) => {
  const { id } = context.params;
  const body = await context.request.json();
  const { name, email } = body;

  const result = await context.env.DB.prepare(
    'UPDATE users SET name = ?, email = ? WHERE id = ? RETURNING *'
  ).bind(name, email, id).first();

  return Response.json(result);
};

export const onRequestDelete: PagesFunction<Env> = async (context) => {
  const { id } = context.params;

  await context.env.DB.prepare(
    'DELETE FROM users WHERE id = ?'
  ).bind(id).run();

  return new Response(null, { status: 204 });
};
```

### Middleware
```typescript
// functions/_middleware.ts
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

export const onRequest: PagesFunction = async (context) => {
  // Handle CORS preflight
  if (context.request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // Add timing header
  const start = Date.now();

  try {
    const response = await context.next();

    // Clone response to add headers
    const newResponse = new Response(response.body, response);
    newResponse.headers.set('X-Response-Time', `${Date.now() - start}ms`);

    // Add CORS headers
    Object.entries(corsHeaders).forEach(([key, value]) => {
      newResponse.headers.set(key, value);
    });

    return newResponse;
  } catch (error) {
    return Response.json(
      { error: 'Internal server error' },
      { status: 500, headers: corsHeaders }
    );
  }
};
```

### Authentication Middleware
```typescript
// functions/api/_middleware.ts
interface Env {
  API_KEY: string;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const authHeader = context.request.headers.get('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return Response.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  const token = authHeader.slice(7);

  // Validate token (example: simple API key check)
  if (token !== context.env.API_KEY) {
    return Response.json(
      { error: 'Invalid token' },
      { status: 403 }
    );
  }

  // Continue to the handler
  return context.next();
};
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create D1 database (if needed)
npx wrangler d1 create my-database
npx wrangler d1 execute my-database --file=./schema.sql

# Create KV namespace (if needed)
npx wrangler kv:namespace create CACHE

# Set secrets
npx wrangler secret put API_KEY

# Build frontend
npm run build

# Deploy
npx wrangler pages deploy dist

# Local development
npx wrangler pages dev dist --d1=DB
```

## Best Practices

### Function Organization
1. Use file-based routing (functions/api/...)
2. Separate middleware for cross-cutting concerns
3. Keep functions small and focused
4. Use TypeScript for type safety

### Performance
1. Functions execute at edge (low latency)
2. Use KV for caching frequent reads
3. Batch database operations when possible
4. Return early for unauthorized requests

### Security
1. Validate all input data
2. Use secrets for API keys
3. Implement rate limiting
4. Add CORS headers appropriately

## Cost Breakdown

| Component | Free Tier | Paid ($5/mo) |
|-----------|-----------|--------------|
| Function requests | 100k/day | 10M/month included |
| Function CPU | 10ms/req | 50ms/req |
| KV reads | 100k/day | $0.50/million |
| KV writes | 1k/day | $5/million |
| D1 reads | 5M/day | $0.001/million |
| D1 writes | 100k/day | $1/million |
| D1 storage | 5GB | $0.75/GB |

## Common Mistakes

1. **Wrong function location**: Must be in `functions/` directory
2. **Missing bindings**: Forgetting to configure D1/KV in wrangler.toml
3. **CORS issues**: Not handling OPTIONS requests
4. **Cold starts**: Functions are instant (no cold start concern)
5. **Large responses**: Keep responses small for edge performance
6. **No error handling**: Unhandled errors crash the function

## Example Configuration

```yaml
project_name: my-fullstack-app
provider: cloudflare
architecture_type: pages_functions

resources:
  - id: pages-site
    type: cloudflare_pages
    name: my-fullstack-app
    provider: cloudflare
    config:
      production_branch: main
      build_command: npm run build
      output_directory: dist
      functions_directory: functions

  - id: database
    type: cloudflare_d1
    name: my-database
    provider: cloudflare
    config:
      binding: DB

  - id: cache
    type: cloudflare_kv
    name: my-cache
    provider: cloudflare
    config:
      binding: CACHE

domain:
  enabled: true
  name: app.example.com
  ssl: true
```

## Framework Integration

### Astro with API Routes
```typescript
// src/pages/api/hello.ts
import type { APIRoute } from 'astro';

export const GET: APIRoute = async ({ request }) => {
  return new Response(JSON.stringify({ message: 'Hello!' }), {
    headers: { 'Content-Type': 'application/json' }
  });
};
```

### SvelteKit
```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-cloudflare';

export default {
  kit: {
    adapter: adapter()
  }
};
```

### Remix
```javascript
// vite.config.ts
import { cloudflareDevProxyVitePlugin } from '@remix-run/dev';

export default {
  plugins: [cloudflareDevProxyVitePlugin()]
};
```

## Sources

- [Pages Functions Documentation](https://developers.cloudflare.com/pages/functions)
- [Functions Routing](https://developers.cloudflare.com/pages/functions/routing)
- [D1 + Pages](https://developers.cloudflare.com/d1/get-started/)
