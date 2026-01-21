# Nuxt 3 on Cloudflare

## Overview

Deploy Nuxt 3 applications on Cloudflare's edge network using Cloudflare Pages with Workers integration. Provides global edge rendering, zero cold starts, and seamless integration with Cloudflare's ecosystem (D1, KV, R2). Optimal for Nuxt applications requiring edge performance and global reach.

## Detection Signals

Use this template when:
- `nuxt.config.ts` or `nuxt.config.js` exists
- `package.json` contains `nuxt` (v3+) dependency
- `.nuxt/` or `server/` directory present
- User wants edge deployment
- Global low-latency required
- Cloudflare ecosystem integration needed
- Cost-effective serverless preferred

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Cloudflare Edge Network                       │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    Edge Locations                        │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │    Edge     │ │    Edge     │ │    Edge     │        │   │
                    │   │  │  Americas   │ │   Europe    │ │    Asia     │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                 Cloudflare Pages                   │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌─────────────────┐  ┌─────────────────────────┐ │  │   │
                    │   │  │  │  Static Assets  │  │    Workers Functions    │ │  │   │
                    │   │  │  │   (Pre-built)   │  │     (SSR/API/ISR)       │ │  │   │
                    │   │  │  └─────────────────┘  └─────────────────────────┘ │  │   │
                    │   │  │                                                   │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │     D1      │ │     KV      │ │     R2      │        │   │
                    │   │  │  Database   │ │   Storage   │ │   Object    │        │   │
                    │   │  │   (SQL)     │ │  (Key-Val)  │ │   Store     │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Global edge • Zero cold starts • <50ms response time          │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Cloudflare Services
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Pages | Static + SSR hosting | Auto-configured |
| Workers | Server-side rendering | Integrated |
| D1 | SQL database | SQLite-compatible |
| KV | Key-value storage | Global, <50ms |
| R2 | Object storage | S3-compatible |
| Durable Objects | Stateful edge | Websockets, sessions |

### Optional Integrations
| Service | Purpose | Configuration |
|---------|---------|---------------|
| Turnstile | CAPTCHA | Widget + validation |
| Email Workers | Email handling | Routing rules |
| Analytics | Web analytics | Auto-enabled |
| Zero Trust | Access control | Identity-aware |

## Configuration

### nuxt.config.ts
```typescript
export default defineNuxtConfig({
  // Cloudflare Pages preset
  nitro: {
    preset: 'cloudflare-pages',

    // Cloudflare bindings
    cloudflare: {
      pages: {
        routes: {
          exclude: ['/images/*', '/fonts/*']
        }
      }
    }
  },

  // Modules
  modules: [
    '@nuxtjs/tailwindcss',
    '@pinia/nuxt',
    '@vueuse/nuxt',
  ],

  // Runtime config
  runtimeConfig: {
    // Private keys (server-only)
    apiSecret: '',

    // Public keys (client + server)
    public: {
      apiBase: '/api',
    }
  },

  // App configuration
  app: {
    head: {
      title: 'My Nuxt App',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' }
      ],
    }
  },

  // Experimental features
  experimental: {
    payloadExtraction: false, // Required for Workers
  },

  // Build optimizations
  vite: {
    build: {
      target: 'esnext',
    },
  },

  // Development
  devtools: { enabled: true },
});
```

### wrangler.toml (for local development)
```toml
name = "my-nuxt-app"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

# D1 Database
[[d1_databases]]
binding = "DB"
database_name = "my-app-db"
database_id = "your-database-id"

# KV Namespace
[[kv_namespaces]]
binding = "KV"
id = "your-kv-id"

# R2 Bucket
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "my-app-bucket"

# Environment variables
[vars]
ENVIRONMENT = "production"

# Secrets (set via wrangler secret put)
# API_SECRET = "..."
```

### Server API with D1
```typescript
// server/api/users/index.get.ts
export default defineEventHandler(async (event) => {
  const { DB } = event.context.cloudflare.env;

  const { results } = await DB.prepare(
    'SELECT id, name, email FROM users LIMIT 100'
  ).all();

  return results;
});

// server/api/users/index.post.ts
export default defineEventHandler(async (event) => {
  const { DB } = event.context.cloudflare.env;
  const body = await readBody(event);

  const { success } = await DB.prepare(
    'INSERT INTO users (name, email) VALUES (?, ?)'
  ).bind(body.name, body.email).run();

  if (!success) {
    throw createError({ statusCode: 500, message: 'Failed to create user' });
  }

  return { success: true };
});
```

### Server API with KV
```typescript
// server/api/cache/[key].get.ts
export default defineEventHandler(async (event) => {
  const key = getRouterParam(event, 'key');
  const { KV } = event.context.cloudflare.env;

  const value = await KV.get(key, { type: 'json' });

  if (!value) {
    throw createError({ statusCode: 404, message: 'Not found' });
  }

  return value;
});

// server/api/cache/[key].put.ts
export default defineEventHandler(async (event) => {
  const key = getRouterParam(event, 'key');
  const body = await readBody(event);
  const { KV } = event.context.cloudflare.env;

  await KV.put(key, JSON.stringify(body), {
    expirationTtl: 3600, // 1 hour
    metadata: { updatedAt: new Date().toISOString() }
  });

  return { success: true };
});
```

### Server API with R2
```typescript
// server/api/files/upload.post.ts
export default defineEventHandler(async (event) => {
  const { BUCKET } = event.context.cloudflare.env;
  const formData = await readMultipartFormData(event);

  if (!formData || !formData[0]) {
    throw createError({ statusCode: 400, message: 'No file provided' });
  }

  const file = formData[0];
  const key = `uploads/${Date.now()}-${file.filename}`;

  await BUCKET.put(key, file.data, {
    httpMetadata: {
      contentType: file.type,
    },
    customMetadata: {
      originalName: file.filename || 'unknown',
    },
  });

  return {
    key,
    url: `/api/files/${key}`
  };
});

// server/api/files/[...path].get.ts
export default defineEventHandler(async (event) => {
  const path = getRouterParam(event, 'path');
  const { BUCKET } = event.context.cloudflare.env;

  const object = await BUCKET.get(path);

  if (!object) {
    throw createError({ statusCode: 404, message: 'File not found' });
  }

  setHeader(event, 'Content-Type', object.httpMetadata?.contentType || 'application/octet-stream');
  setHeader(event, 'Cache-Control', 'public, max-age=31536000');

  return object.body;
});
```

### Server Middleware (Auth)
```typescript
// server/middleware/auth.ts
export default defineEventHandler(async (event) => {
  const protectedRoutes = ['/api/admin', '/api/user'];
  const path = getRequestPath(event);

  if (protectedRoutes.some(route => path.startsWith(route))) {
    const authorization = getHeader(event, 'authorization');

    if (!authorization) {
      throw createError({ statusCode: 401, message: 'Unauthorized' });
    }

    // Validate token with KV
    const { KV } = event.context.cloudflare.env;
    const token = authorization.replace('Bearer ', '');
    const session = await KV.get(`session:${token}`, { type: 'json' });

    if (!session) {
      throw createError({ statusCode: 401, message: 'Invalid session' });
    }

    event.context.user = session;
  }
});
```

### Database Schema (D1)
```sql
-- migrations/0001_initial.sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT,
  published BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_published ON posts(published);
```

### Composables
```typescript
// composables/useCloudflare.ts
export const useD1 = () => {
  return useRequestEvent()?.context.cloudflare.env.DB;
};

export const useKV = () => {
  return useRequestEvent()?.context.cloudflare.env.KV;
};

export const useR2 = () => {
  return useRequestEvent()?.context.cloudflare.env.BUCKET;
};

// composables/useApi.ts
export const useApi = () => {
  const config = useRuntimeConfig();

  return $fetch.create({
    baseURL: config.public.apiBase,
    onRequest({ options }) {
      const token = useCookie('auth-token');
      if (token.value) {
        options.headers = {
          ...options.headers,
          Authorization: `Bearer ${token.value}`,
        };
      }
    },
  });
};
```

### Pages with ISR
```vue
<!-- pages/blog/[slug].vue -->
<script setup lang="ts">
const route = useRoute();

// ISR with 1 hour revalidation
const { data: post } = await useFetch(`/api/posts/${route.params.slug}`, {
  key: `post-${route.params.slug}`,
  getCachedData(key) {
    const data = nuxtApp.payload.data[key] || nuxtApp.static.data[key];
    if (!data) return;
    return data;
  },
});

if (!post.value) {
  throw createError({ statusCode: 404, message: 'Post not found' });
}

// SEO
useSeoMeta({
  title: post.value.title,
  description: post.value.excerpt,
  ogImage: post.value.image,
});
</script>

<template>
  <article class="prose max-w-none">
    <h1>{{ post.title }}</h1>
    <div v-html="post.content" />
  </article>
</template>
```

## Deployment Commands

```bash
# Install dependencies
npm install

# Local development with Cloudflare bindings
npm run dev

# Or use wrangler for full Cloudflare environment
npx wrangler pages dev .output/public --compatibility-flags=nodejs_compat

# Build for production
npm run build

# Deploy to Cloudflare Pages
npx wrangler pages deploy .output/public

# Create D1 database
npx wrangler d1 create my-app-db

# Run D1 migrations
npx wrangler d1 execute my-app-db --file=./migrations/0001_initial.sql

# Create KV namespace
npx wrangler kv:namespace create KV

# Create R2 bucket
npx wrangler r2 bucket create my-app-bucket

# Set secrets
npx wrangler secret put API_SECRET

# View logs
npx wrangler pages deployment tail

# List deployments
npx wrangler pages deployment list
```

## GitHub Actions Deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloudflare Pages

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build
        env:
          NUXT_PUBLIC_API_BASE: ${{ vars.API_BASE }}

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: my-nuxt-app
          directory: .output/public
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}
          branch: ${{ github.head_ref || github.ref_name }}
```

## Cost Breakdown

| Resource | Free Tier | Paid (Pro) |
|----------|-----------|------------|
| Pages | Unlimited sites, 500 builds/mo | Unlimited builds |
| Workers | 100K requests/day | $5/10M requests |
| D1 | 5GB storage, 5M reads/day | $0.75/M reads |
| KV | 100K reads/day | $0.50/M reads |
| R2 | 10GB storage, 10M reads/mo | $0.015/GB/mo |
| **Typical App** | **$0/month** | **~$5-20/month** |

## Best Practices

1. **Use ISR for dynamic content** - Cache pages at edge with revalidation
2. **Leverage D1 for SQL** - SQLite at edge for low-latency queries
3. **Use KV for sessions** - Fast session storage globally
4. **R2 for assets** - Serve images/files from edge
5. **Minimize bundle size** - Tree shake, code split
6. **Use server-only composables** - Keep secrets server-side
7. **Enable compression** - Brotli compression by default
8. **Monitor with Analytics** - Built-in web analytics

## Common Mistakes

1. **Using Node.js APIs** - Workers runtime is not Node.js
2. **Large bundle sizes** - Exceeds 1MB limit for Workers
3. **Not using bindings correctly** - Access via `event.context.cloudflare.env`
4. **Synchronous database calls** - Always await D1/KV/R2 operations
5. **Missing nodejs_compat flag** - Required for some Node.js polyfills
6. **Hardcoding secrets** - Use wrangler secret put
7. **Ignoring cold starts** - Workers have minimal cold starts, optimize anyway
8. **Not using Pages Functions** - SSR should use integrated functions

## Example Configuration

```yaml
# infera.yaml
project_name: my-nuxt-app
provider: cloudflare

framework:
  name: nuxt
  version: "3"

deployment:
  type: pages

  bindings:
    d1:
      - name: DB
        database: my-app-db
    kv:
      - name: KV
    r2:
      - name: BUCKET
        bucket: my-app-bucket

  env_vars:
    NUXT_PUBLIC_API_BASE: /api

  secrets:
    - API_SECRET

build:
  command: npm run build
  output: .output/public
```

## Sources

- [Nuxt Cloudflare Deployment](https://nuxt.com/deploy/cloudflare)
- [Cloudflare Pages Documentation](https://developers.cloudflare.com/pages/)
- [Cloudflare D1 Documentation](https://developers.cloudflare.com/d1/)
- [Nitro Cloudflare Preset](https://nitro.unjs.io/deploy/providers/cloudflare)
