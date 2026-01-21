# Remix on Cloudflare

## Overview

Deploy Remix applications on Cloudflare's edge network using Cloudflare Pages or Workers. Provides global edge rendering with Remix's progressive enhancement philosophy, zero cold starts, and access to Cloudflare's data services. Optimal for Remix applications requiring edge performance with strong DX.

## Detection Signals

Use this template when:
- `remix.config.js` or `vite.config.ts` with Remix plugin exists
- `package.json` contains `@remix-run/cloudflare` or `@remix-run/cloudflare-pages`
- `app/` directory with `root.tsx` and `routes/` folder
- User wants edge deployment
- Progressive enhancement important
- Cloudflare ecosystem integration needed

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Cloudflare Edge Network                       │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    Edge Locations                        │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │    Edge     │ │    Edge     │ │    Edge     │        │   │
                    │   │  │   (300+     │ │   (300+     │ │   (300+     │        │   │
                    │   │  │  locations) │ │  locations) │ │  locations) │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Remix on Cloudflare Pages             │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌───────────┐ ┌───────────┐ ┌───────────────────┐│  │   │
                    │   │  │  │  Static   │ │   SSR     │ │   API Routes      ││  │   │
                    │   │  │  │  Assets   │ │ (Workers) │ │   (loader/action) ││  │   │
                    │   │  │  │  (CDN)    │ │           │ │                   ││  │   │
                    │   │  │  └───────────┘ └───────────┘ └───────────────────┘│  │   │
                    │   │  │                                                   │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │                          │                               │   │
                    │   │          ┌───────────────┼───────────────┐              │   │
                    │   │          ▼               ▼               ▼              │   │
                    │   │   ┌───────────┐   ┌───────────┐   ┌───────────┐        │   │
                    │   │   │    D1     │   │    KV     │   │    R2     │        │   │
                    │   │   │ Database  │   │  Session  │   │  Storage  │        │   │
                    │   │   └───────────┘   └───────────┘   └───────────┘        │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Edge SSR • Progressive enhancement • <50ms TTFB              │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Cloudflare Services
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Pages | Static + SSR hosting | Auto-configured |
| Workers | Server-side rendering | Edge runtime |
| D1 | SQL database | SQLite-compatible |
| KV | Session storage | Global, <50ms |
| R2 | File storage | S3-compatible |
| Durable Objects | WebSocket, realtime | Stateful edge |

### External Services
| Service | Purpose | Options |
|---------|---------|---------|
| Auth | Authentication | Clerk, Auth0, Lucia |
| Email | Transactional | Resend, Mailgun |
| Monitoring | Observability | Sentry, LogRocket |

## Configuration

### vite.config.ts (Remix v2 + Vite)
```typescript
import { vitePlugin as remix } from "@remix-run/dev";
import { defineConfig } from "vite";
import { cloudflareDevProxyVitePlugin as cloudflare } from "@remix-run/dev/cloudflare";

export default defineConfig({
  plugins: [
    cloudflare(),
    remix({
      future: {
        v3_fetcherPersist: true,
        v3_relativeSplatPath: true,
        v3_throwAbortReason: true,
      },
    }),
  ],
  ssr: {
    resolve: {
      conditions: ["workerd", "worker", "browser"],
    },
  },
  resolve: {
    mainFields: ["browser", "module", "main"],
  },
  build: {
    minify: true,
  },
});
```

### wrangler.toml
```toml
name = "my-remix-app"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

# Required for Remix
main = "./build/server/index.js"
assets = { directory = "./build/client" }

# D1 Database
[[d1_databases]]
binding = "DB"
database_name = "remix-app-db"
database_id = "your-database-id"

# KV Namespace (sessions)
[[kv_namespaces]]
binding = "SESSION_KV"
id = "your-kv-id"

# R2 Bucket (uploads)
[[r2_buckets]]
binding = "UPLOADS"
bucket_name = "remix-app-uploads"

# Environment variables
[vars]
ENVIRONMENT = "production"
```

### Environment Types
```typescript
// env.d.ts
/// <reference types="@remix-run/cloudflare" />
/// <reference types="vite/client" />

interface Env {
  DB: D1Database;
  SESSION_KV: KVNamespace;
  UPLOADS: R2Bucket;
  ENVIRONMENT: string;
  SESSION_SECRET: string;
}

declare module "@remix-run/cloudflare" {
  interface AppLoadContext {
    cloudflare: {
      env: Env;
      ctx: ExecutionContext;
      cf: IncomingRequestCfProperties;
    };
  }
}
```

### Root Component
```typescript
// app/root.tsx
import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLoaderData,
} from "@remix-run/react";
import type { LinksFunction, LoaderFunctionArgs } from "@remix-run/cloudflare";

export const links: LinksFunction = () => [
  { rel: "stylesheet", href: "/styles/app.css" },
];

export async function loader({ context }: LoaderFunctionArgs) {
  const env = context.cloudflare.env.ENVIRONMENT;
  return { env };
}

export default function App() {
  const { env } = useLoaderData<typeof loader>();

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <Outlet />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
```

### Session Management with KV
```typescript
// app/services/session.server.ts
import { createCookieSessionStorage } from "@remix-run/cloudflare";
import type { AppLoadContext } from "@remix-run/cloudflare";

export function createSessionStorage(context: AppLoadContext) {
  const { SESSION_KV } = context.cloudflare.env;
  const sessionSecret = context.cloudflare.env.SESSION_SECRET;

  return createCookieSessionStorage({
    cookie: {
      name: "__session",
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      secrets: [sessionSecret],
      secure: true,
    },
  });
}

// For KV-backed sessions (larger storage)
export function createKVSessionStorage(context: AppLoadContext) {
  const { SESSION_KV } = context.cloudflare.env;
  const sessionSecret = context.cloudflare.env.SESSION_SECRET;

  return {
    async getSession(cookieHeader: string | null) {
      const cookie = cookieHeader ? cookieHeader.split("=")[1] : null;
      if (!cookie) return {};

      const session = await SESSION_KV.get(`session:${cookie}`, { type: "json" });
      return session || {};
    },

    async commitSession(session: Record<string, any>) {
      const id = crypto.randomUUID();
      await SESSION_KV.put(`session:${id}`, JSON.stringify(session), {
        expirationTtl: 60 * 60 * 24 * 7, // 7 days
      });
      return `__session=${id}; Path=/; HttpOnly; Secure; SameSite=Lax`;
    },

    async destroySession(cookieHeader: string | null) {
      const cookie = cookieHeader ? cookieHeader.split("=")[1] : null;
      if (cookie) {
        await SESSION_KV.delete(`session:${cookie}`);
      }
      return "__session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT";
    },
  };
}
```

### Database Service with D1
```typescript
// app/services/db.server.ts
import type { AppLoadContext } from "@remix-run/cloudflare";

export interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
}

export interface Post {
  id: number;
  user_id: number;
  title: string;
  content: string;
  published: boolean;
  created_at: string;
}

export function createDbService(context: AppLoadContext) {
  const db = context.cloudflare.env.DB;

  return {
    // Users
    async getUsers(): Promise<User[]> {
      const { results } = await db
        .prepare("SELECT * FROM users ORDER BY created_at DESC")
        .all<User>();
      return results;
    },

    async getUserById(id: number): Promise<User | null> {
      return db
        .prepare("SELECT * FROM users WHERE id = ?")
        .bind(id)
        .first<User>();
    },

    async getUserByEmail(email: string): Promise<User | null> {
      return db
        .prepare("SELECT * FROM users WHERE email = ?")
        .bind(email)
        .first<User>();
    },

    async createUser(data: { email: string; name: string }): Promise<User> {
      const result = await db
        .prepare("INSERT INTO users (email, name) VALUES (?, ?) RETURNING *")
        .bind(data.email, data.name)
        .first<User>();
      return result!;
    },

    // Posts
    async getPosts(userId?: number): Promise<Post[]> {
      if (userId) {
        const { results } = await db
          .prepare("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC")
          .bind(userId)
          .all<Post>();
        return results;
      }
      const { results } = await db
        .prepare("SELECT * FROM posts WHERE published = 1 ORDER BY created_at DESC")
        .all<Post>();
      return results;
    },

    async getPostBySlug(slug: string): Promise<Post | null> {
      return db
        .prepare("SELECT * FROM posts WHERE slug = ?")
        .bind(slug)
        .first<Post>();
    },

    async createPost(data: {
      user_id: number;
      title: string;
      content: string;
    }): Promise<Post> {
      const slug = data.title.toLowerCase().replace(/\s+/g, "-");
      const result = await db
        .prepare(
          "INSERT INTO posts (user_id, title, slug, content) VALUES (?, ?, ?, ?) RETURNING *"
        )
        .bind(data.user_id, data.title, slug, data.content)
        .first<Post>();
      return result!;
    },
  };
}
```

### Route with Loader and Action
```typescript
// app/routes/posts._index.tsx
import type {
  ActionFunctionArgs,
  LoaderFunctionArgs,
  MetaFunction,
} from "@remix-run/cloudflare";
import { json } from "@remix-run/cloudflare";
import { Form, useLoaderData, useNavigation } from "@remix-run/react";
import { createDbService } from "~/services/db.server";

export const meta: MetaFunction = () => {
  return [
    { title: "Posts" },
    { name: "description", content: "View all posts" },
  ];
};

export async function loader({ context }: LoaderFunctionArgs) {
  const db = createDbService(context);
  const posts = await db.getPosts();

  return json({ posts }, {
    headers: {
      "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
    },
  });
}

export async function action({ request, context }: ActionFunctionArgs) {
  const formData = await request.formData();
  const title = formData.get("title") as string;
  const content = formData.get("content") as string;

  if (!title || !content) {
    return json({ error: "Title and content are required" }, { status: 400 });
  }

  const db = createDbService(context);

  // In real app, get user from session
  const post = await db.createPost({
    user_id: 1,
    title,
    content,
  });

  return json({ post });
}

export default function Posts() {
  const { posts } = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const isSubmitting = navigation.state === "submitting";

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">Posts</h1>

      {/* Create post form */}
      <Form method="post" className="mb-8 space-y-4">
        <div>
          <label htmlFor="title" className="block font-medium">
            Title
          </label>
          <input
            type="text"
            name="title"
            id="title"
            required
            className="w-full border rounded p-2"
          />
        </div>
        <div>
          <label htmlFor="content" className="block font-medium">
            Content
          </label>
          <textarea
            name="content"
            id="content"
            required
            rows={4}
            className="w-full border rounded p-2"
          />
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className="bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {isSubmitting ? "Creating..." : "Create Post"}
        </button>
      </Form>

      {/* Posts list */}
      <ul className="space-y-4">
        {posts.map((post) => (
          <li key={post.id} className="border rounded p-4">
            <h2 className="text-xl font-semibold">{post.title}</h2>
            <p className="text-gray-600 mt-2">{post.content}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### File Upload with R2
```typescript
// app/routes/api.upload.tsx
import type { ActionFunctionArgs } from "@remix-run/cloudflare";
import { json } from "@remix-run/cloudflare";
import {
  unstable_parseMultipartFormData,
  unstable_createMemoryUploadHandler,
} from "@remix-run/cloudflare";

export async function action({ request, context }: ActionFunctionArgs) {
  const { UPLOADS } = context.cloudflare.env;

  const uploadHandler = unstable_createMemoryUploadHandler({
    maxPartSize: 10_000_000, // 10MB
  });

  const formData = await unstable_parseMultipartFormData(request, uploadHandler);
  const file = formData.get("file") as File | null;

  if (!file) {
    return json({ error: "No file provided" }, { status: 400 });
  }

  const key = `uploads/${Date.now()}-${file.name}`;
  const arrayBuffer = await file.arrayBuffer();

  await UPLOADS.put(key, arrayBuffer, {
    httpMetadata: {
      contentType: file.type,
    },
  });

  return json({
    success: true,
    key,
    url: `/api/files/${key}`,
  });
}
```

### Error Boundary
```typescript
// app/routes/posts.$slug.tsx
import { useRouteError, isRouteErrorResponse, Link } from "@remix-run/react";

export function ErrorBoundary() {
  const error = useRouteError();

  if (isRouteErrorResponse(error)) {
    return (
      <div className="container mx-auto p-4 text-center">
        <h1 className="text-4xl font-bold text-red-500">
          {error.status} {error.statusText}
        </h1>
        <p className="mt-4">{error.data}</p>
        <Link to="/posts" className="mt-4 text-blue-500 underline">
          Back to Posts
        </Link>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 text-center">
      <h1 className="text-4xl font-bold text-red-500">Oops!</h1>
      <p className="mt-4">Something went wrong.</p>
      <Link to="/" className="mt-4 text-blue-500 underline">
        Go Home
      </Link>
    </div>
  );
}
```

## Deployment Commands

```bash
# Install dependencies
npm install

# Local development
npm run dev

# Build for production
npm run build

# Deploy to Cloudflare Pages
npx wrangler pages deploy ./build/client

# Or deploy as Worker
npx wrangler deploy

# Create D1 database
npx wrangler d1 create remix-app-db

# Run migrations
npx wrangler d1 execute remix-app-db --file=./migrations/0001_initial.sql

# Create KV namespace
npx wrangler kv:namespace create SESSION_KV

# Create R2 bucket
npx wrangler r2 bucket create remix-app-uploads

# Set secrets
npx wrangler secret put SESSION_SECRET

# View logs
npx wrangler tail

# List deployments
npx wrangler deployments list
```

## Database Migrations

```sql
-- migrations/0001_initial.sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  content TEXT,
  published BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_slug ON posts(slug);
CREATE INDEX idx_posts_published ON posts(published);
```

## GitHub Actions Deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy

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

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: my-remix-app
          directory: build/client
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}
```

## Cost Breakdown

| Resource | Free Tier | Paid |
|----------|-----------|------|
| Pages | Unlimited sites | - |
| Workers | 100K req/day | $5/10M req |
| D1 | 5GB, 5M reads/day | $0.75/M reads |
| KV | 100K reads/day | $0.50/M reads |
| R2 | 10GB, 10M reads/mo | $0.015/GB |
| **Typical App** | **$0/month** | **~$5-15/month** |

## Best Practices

1. **Use loaders for data** - Server-side data loading at edge
2. **Progressive enhancement** - Forms work without JS
3. **Cache responses** - Set Cache-Control headers
4. **Use D1 for persistence** - SQLite at edge
5. **KV for sessions** - Fast, global session storage
6. **R2 for uploads** - Edge-accessible file storage
7. **Type everything** - Full TypeScript support
8. **Error boundaries** - Graceful error handling

## Common Mistakes

1. **Client-side data fetching** - Use loaders instead
2. **Large bundles** - Code split with route modules
3. **Missing context types** - Define Env interface properly
4. **Synchronous operations** - Always await D1/KV/R2
5. **No error boundaries** - Add per-route error handling
6. **Hardcoded secrets** - Use wrangler secrets
7. **Missing nodejs_compat** - Required for some packages
8. **Not using forms** - Remix forms provide better UX

## Example Configuration

```yaml
# infera.yaml
project_name: my-remix-app
provider: cloudflare

framework:
  name: remix
  version: "2"

deployment:
  type: pages

  bindings:
    d1:
      - name: DB
        database: remix-app-db
    kv:
      - name: SESSION_KV
    r2:
      - name: UPLOADS
        bucket: remix-app-uploads

  secrets:
    - SESSION_SECRET

build:
  command: npm run build
  output: build/client
```

## Sources

- [Remix Cloudflare Documentation](https://remix.run/docs/en/main/guides/cloudflare)
- [Cloudflare Pages Remix](https://developers.cloudflare.com/pages/framework-guides/remix/)
- [Cloudflare D1](https://developers.cloudflare.com/d1/)
- [Remix Documentation](https://remix.run/docs)
