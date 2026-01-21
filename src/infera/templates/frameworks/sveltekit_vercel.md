# SvelteKit on Vercel / Cloudflare

## Overview

Deploy SvelteKit applications on Vercel or Cloudflare for optimal edge performance. SvelteKit's adapter system allows seamless deployment to multiple platforms with the same codebase. Ideal for high-performance web applications with excellent DX and minimal runtime overhead.

## Detection Signals

Use this template when:
- `svelte.config.js` exists
- `package.json` contains `@sveltejs/kit` dependency
- `src/routes/` directory structure
- `.svelte` files present
- User wants edge deployment
- Performance-critical application
- Minimal JavaScript bundle desired

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Vercel / Cloudflare Edge                      │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    Edge Network                          │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │    Edge     │ │    Edge     │ │    Edge     │        │   │
                    │   │  │   Region    │ │   Region    │ │   Region    │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                 SvelteKit App                      │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌───────────┐ ┌───────────┐ ┌───────────────────┐│  │   │
                    │   │  │  │  Static   │ │   SSR     │ │   API Routes      ││  │   │
                    │   │  │  │  Assets   │ │  Pages    │ │   (+server.ts)    ││  │   │
                    │   │  │  │  (CDN)    │ │           │ │                   ││  │   │
                    │   │  │  └───────────┘ └───────────┘ └───────────────────┘│  │   │
                    │   │  │                                                   │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                          │                               │   │
                    │   │          ┌───────────────┼───────────────┐              │   │
                    │   │          ▼               ▼               ▼              │   │
                    │   │   ┌───────────┐   ┌───────────┐   ┌───────────┐        │   │
                    │   │   │  Database │   │   Auth    │   │    KV     │        │   │
                    │   │   │(PlanetScale│   │  (Clerk) │   │ (Vercel/  │        │   │
                    │   │   │  Supabase)│   │           │   │Cloudflare)│        │   │
                    │   │   └───────────┘   └───────────┘   └───────────┘        │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Minimal JS • Edge SSR • Prerendering • <50ms TTFB            │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Vercel
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Edge Network | Global CDN | Automatic |
| Serverless | SSR, API routes | Auto-scaled |
| Edge Functions | Fast SSR | Optional |
| KV | Key-value store | Add-on |
| Postgres | Database | Add-on |
| Blob | Object storage | Add-on |

### Cloudflare
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Pages | Static + SSR | Auto-configured |
| Workers | Server functions | Integrated |
| D1 | SQL database | SQLite |
| KV | Key-value store | Global |
| R2 | Object storage | S3-compatible |

## Configuration

### svelte.config.js (Vercel)
```javascript
import adapter from '@sveltejs/adapter-vercel';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      // Edge deployment for low latency
      runtime: 'edge',

      // Or use Node.js for more compatibility
      // runtime: 'nodejs20.x',

      // Regions for edge functions
      regions: ['iad1', 'sfo1', 'cdg1'],

      // Split routes between edge and serverless
      split: false,
    }),

    // Prerender static pages
    prerender: {
      entries: ['*'],
      handleMissingId: 'warn',
    },

    // CSP headers
    csp: {
      mode: 'auto',
      directives: {
        'script-src': ['self'],
      },
    },

    // Alias imports
    alias: {
      $components: 'src/components',
      $lib: 'src/lib',
    },
  },
};

export default config;
```

### svelte.config.js (Cloudflare)
```javascript
import adapter from '@sveltejs/adapter-cloudflare';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      // Cloudflare Pages configuration
      routes: {
        include: ['/*'],
        exclude: ['<all>'],
      },
    }),

    prerender: {
      entries: ['*'],
    },

    alias: {
      $components: 'src/components',
      $lib: 'src/lib',
    },
  },
};

export default config;
```

### wrangler.toml (Cloudflare)
```toml
name = "my-sveltekit-app"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

# D1 Database
[[d1_databases]]
binding = "DB"
database_name = "sveltekit-db"
database_id = "your-db-id"

# KV Namespace
[[kv_namespaces]]
binding = "KV"
id = "your-kv-id"

# R2 Bucket
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "sveltekit-uploads"

[vars]
PUBLIC_APP_URL = "https://myapp.com"
```

### App Types (Cloudflare)
```typescript
// src/app.d.ts
/// <reference types="@sveltejs/adapter-cloudflare" />

declare global {
  namespace App {
    interface Error {
      message: string;
      code?: string;
    }

    interface Locals {
      user: {
        id: string;
        email: string;
      } | null;
    }

    interface PageData {
      title?: string;
    }

    interface Platform {
      env: {
        DB: D1Database;
        KV: KVNamespace;
        BUCKET: R2Bucket;
      };
      context: {
        waitUntil(promise: Promise<any>): void;
      };
      caches: CacheStorage;
    }
  }
}

export {};
```

### Layout with Auth
```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  import { invalidate } from '$app/navigation';
  import type { LayoutData } from './$types';

  export let data: LayoutData;

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    invalidate('app:user');
  }
</script>

<svelte:head>
  <title>{$page.data.title ?? 'My App'}</title>
</svelte:head>

<div class="min-h-screen">
  <nav class="bg-gray-800 text-white p-4">
    <div class="container mx-auto flex justify-between items-center">
      <a href="/" class="text-xl font-bold">My App</a>

      <div class="flex items-center gap-4">
        {#if data.user}
          <span>Hello, {data.user.email}</span>
          <button
            on:click={handleLogout}
            class="bg-red-500 px-3 py-1 rounded"
          >
            Logout
          </button>
        {:else}
          <a href="/login" class="bg-blue-500 px-3 py-1 rounded">Login</a>
        {/if}
      </div>
    </div>
  </nav>

  <main class="container mx-auto p-4">
    <slot />
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, sans-serif;
  }
</style>
```

### Layout Server Load
```typescript
// src/routes/+layout.server.ts
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ cookies, locals }) => {
  return {
    user: locals.user,
  };
};
```

### Hooks for Auth
```typescript
// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  // Get session from cookie
  const sessionId = event.cookies.get('session');

  if (sessionId) {
    // Cloudflare: Access platform bindings
    const db = event.platform?.env.DB;

    if (db) {
      const session = await db
        .prepare('SELECT * FROM sessions WHERE id = ? AND expires_at > datetime("now")')
        .bind(sessionId)
        .first();

      if (session) {
        const user = await db
          .prepare('SELECT id, email FROM users WHERE id = ?')
          .bind(session.user_id)
          .first();

        event.locals.user = user;
      }
    }
  }

  event.locals.user = event.locals.user ?? null;

  const response = await resolve(event);

  return response;
};
```

### Page with Load Function
```svelte
<!-- src/routes/posts/+page.svelte -->
<script lang="ts">
  import type { PageData } from './$types';
  import { enhance } from '$app/forms';

  export let data: PageData;
</script>

<svelte:head>
  <title>Posts</title>
  <meta name="description" content="All posts" />
</svelte:head>

<h1 class="text-3xl font-bold mb-6">Posts</h1>

{#if data.user}
  <form
    method="POST"
    action="?/create"
    use:enhance
    class="mb-8 space-y-4"
  >
    <div>
      <label for="title" class="block font-medium">Title</label>
      <input
        type="text"
        name="title"
        id="title"
        required
        class="w-full border rounded p-2"
      />
    </div>
    <div>
      <label for="content" class="block font-medium">Content</label>
      <textarea
        name="content"
        id="content"
        rows="4"
        class="w-full border rounded p-2"
      ></textarea>
    </div>
    <button
      type="submit"
      class="bg-blue-500 text-white px-4 py-2 rounded"
    >
      Create Post
    </button>
  </form>
{/if}

<ul class="space-y-4">
  {#each data.posts as post}
    <li class="border rounded p-4">
      <a href="/posts/{post.slug}" class="text-xl font-semibold hover:underline">
        {post.title}
      </a>
      <p class="text-gray-600 mt-2">{post.excerpt}</p>
      <p class="text-sm text-gray-400 mt-2">
        By {post.author} • {new Date(post.created_at).toLocaleDateString()}
      </p>
    </li>
  {:else}
    <li class="text-gray-500">No posts yet.</li>
  {/each}
</ul>
```

### Page Server Load
```typescript
// src/routes/posts/+page.server.ts
import type { PageServerLoad, Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  const db = platform?.env.DB;

  if (!db) {
    return { posts: [] };
  }

  const { results: posts } = await db
    .prepare(`
      SELECT p.id, p.title, p.slug, p.content, p.created_at,
             u.name as author
      FROM posts p
      JOIN users u ON p.user_id = u.id
      WHERE p.published = 1
      ORDER BY p.created_at DESC
      LIMIT 20
    `)
    .all();

  // Cache for 1 minute, revalidate in background for 5 minutes
  setHeaders({
    'Cache-Control': 'public, max-age=60, stale-while-revalidate=300',
  });

  return {
    posts: posts.map(p => ({
      ...p,
      excerpt: p.content?.substring(0, 200) + '...',
    })),
  };
};

export const actions: Actions = {
  create: async ({ request, locals, platform }) => {
    if (!locals.user) {
      throw redirect(303, '/login');
    }

    const formData = await request.formData();
    const title = formData.get('title') as string;
    const content = formData.get('content') as string;

    if (!title?.trim()) {
      return fail(400, { error: 'Title is required', title, content });
    }

    const db = platform?.env.DB;
    if (!db) {
      return fail(500, { error: 'Database unavailable' });
    }

    const slug = title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

    try {
      await db
        .prepare(
          'INSERT INTO posts (user_id, title, slug, content, published) VALUES (?, ?, ?, ?, 1)'
        )
        .bind(locals.user.id, title, slug, content)
        .run();

      throw redirect(303, `/posts/${slug}`);
    } catch (e) {
      if (e instanceof Response) throw e;
      return fail(500, { error: 'Failed to create post' });
    }
  },
};
```

### API Route
```typescript
// src/routes/api/posts/+server.ts
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ platform, url }) => {
  const db = platform?.env.DB;
  const limit = parseInt(url.searchParams.get('limit') ?? '10');
  const offset = parseInt(url.searchParams.get('offset') ?? '0');

  if (!db) {
    return json({ posts: [], total: 0 });
  }

  const [{ results: posts }, { total }] = await Promise.all([
    db
      .prepare('SELECT * FROM posts WHERE published = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?')
      .bind(limit, offset)
      .all(),
    db
      .prepare('SELECT COUNT(*) as total FROM posts WHERE published = 1')
      .first() as Promise<{ total: number }>,
  ]);

  return json({
    posts,
    total,
    hasMore: offset + posts.length < total,
  });
};

export const POST: RequestHandler = async ({ request, locals, platform }) => {
  if (!locals.user) {
    return json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { title, content } = await request.json();

  if (!title) {
    return json({ error: 'Title is required' }, { status: 400 });
  }

  const db = platform?.env.DB;
  if (!db) {
    return json({ error: 'Database unavailable' }, { status: 500 });
  }

  const slug = title.toLowerCase().replace(/\s+/g, '-');

  const result = await db
    .prepare(
      'INSERT INTO posts (user_id, title, slug, content) VALUES (?, ?, ?, ?) RETURNING *'
    )
    .bind(locals.user.id, title, slug, content)
    .first();

  return json({ post: result }, { status: 201 });
};
```

### Error Page
```svelte
<!-- src/routes/+error.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
</script>

<svelte:head>
  <title>Error {$page.status}</title>
</svelte:head>

<div class="min-h-screen flex items-center justify-center">
  <div class="text-center">
    <h1 class="text-6xl font-bold text-gray-300">{$page.status}</h1>
    <p class="text-xl text-gray-600 mt-4">{$page.error?.message || 'Something went wrong'}</p>
    <a href="/" class="mt-6 inline-block text-blue-500 hover:underline">
      Go Home
    </a>
  </div>
</div>
```

## Deployment Commands

### Vercel
```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy preview
vercel

# Deploy production
vercel --prod

# Set environment variables
vercel env add DATABASE_URL

# Pull env vars locally
vercel env pull .env.local

# View logs
vercel logs

# Promote deployment
vercel promote <url>
```

### Cloudflare
```bash
# Build
npm run build

# Deploy to Cloudflare Pages
npx wrangler pages deploy .svelte-kit/cloudflare

# Create D1 database
npx wrangler d1 create sveltekit-db

# Run migrations
npx wrangler d1 execute sveltekit-db --file=./migrations/schema.sql

# Create KV
npx wrangler kv:namespace create KV

# Create R2
npx wrangler r2 bucket create sveltekit-uploads

# Set secrets
npx wrangler secret put AUTH_SECRET

# View logs
npx wrangler pages deployment tail
```

## GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-vercel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npm run build

      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'

  # Or deploy to Cloudflare
  deploy-cloudflare:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npm run build

      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: my-sveltekit-app
          directory: .svelte-kit/cloudflare
```

## Cost Breakdown

### Vercel
| Plan | Features | Cost |
|------|----------|------|
| Hobby | Personal, 100GB | Free |
| Pro | Team, 1TB, analytics | $20/member |

### Cloudflare
| Resource | Free | Paid |
|----------|------|------|
| Pages | Unlimited | - |
| Workers | 100K req/day | $5/10M |
| D1 | 5GB, 5M reads | $0.75/M |
| KV | 100K reads/day | $0.50/M |
| **Total** | **$0** | **$5-20/mo** |

## Best Practices

1. **Prerender static pages** - Use `export const prerender = true`
2. **Use load functions** - SSR data fetching
3. **Progressive enhancement** - Forms work without JS
4. **Edge runtime for speed** - Low latency globally
5. **Type everything** - Full TypeScript support
6. **Use stores sparingly** - Prefer load functions
7. **Cache aggressively** - Set Cache-Control headers
8. **Error boundaries** - Handle errors gracefully

## Common Mistakes

1. **Client-side fetching** - Use load functions instead
2. **Large bundles** - Svelte is small, keep deps minimal
3. **Missing types** - Define App.Platform properly
4. **Forgetting prerender** - Static pages should be prerendered
5. **No error handling** - Add +error.svelte pages
6. **Blocking hooks** - Keep hooks fast
7. **Hardcoded URLs** - Use environment variables
8. **No form enhancement** - Use `use:enhance` for better UX

## Example Configuration

```yaml
# infera.yaml
project_name: my-sveltekit-app
provider: cloudflare  # or vercel

framework:
  name: sveltekit
  version: "2"

deployment:
  type: pages
  runtime: edge

  bindings:  # Cloudflare only
    d1:
      - name: DB
        database: sveltekit-db
    kv:
      - name: KV
    r2:
      - name: BUCKET
        bucket: sveltekit-uploads

  env_vars:
    PUBLIC_APP_URL: https://myapp.com

  secrets:
    - AUTH_SECRET
    - DATABASE_URL

build:
  command: npm run build
  output: .svelte-kit/cloudflare
```

## Sources

- [SvelteKit Documentation](https://kit.svelte.dev/docs)
- [SvelteKit Vercel Adapter](https://kit.svelte.dev/docs/adapter-vercel)
- [SvelteKit Cloudflare Adapter](https://kit.svelte.dev/docs/adapter-cloudflare)
- [Cloudflare Pages SvelteKit](https://developers.cloudflare.com/pages/framework-guides/sveltekit/)
