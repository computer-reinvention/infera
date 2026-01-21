# Cloudflare Full-Stack Application

## Overview

Deploy complete full-stack applications using the Cloudflare Developer Platform: Pages for frontend, Workers for API, D1 for database, R2 for storage, and KV for caching. A unified platform with global distribution and zero cold starts.

## Detection Signals

Use this template when:
- Full-stack application with frontend and backend
- Need for database, storage, and caching
- Global distribution requirements
- Serverless architecture preferred
- Cost-sensitive deployment

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │              Cloudflare Developer Platform               │
                    │                                                         │
    Internet ──────►│   ┌─────────────────────────────────────────────────┐   │
                    │   │              Pages (Frontend)                    │   │
                    │   │   React/Vue/Svelte + Functions                  │   │
                    │   └──────────────────────┬──────────────────────────┘   │
                    │                          │ /api/*                       │
                    │   ┌──────────────────────┼──────────────────────────┐   │
                    │   │                      ▼                          │   │
                    │   │         Pages Functions / Workers               │   │
                    │   │                                                 │   │
                    │   │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │   │
                    │   │  │   D1    │  │   R2    │  │       KV        │ │   │
                    │   │  │   SQL   │  │ Storage │  │     Cache       │ │   │
                    │   │  └─────────┘  └─────────┘  └─────────────────┘ │   │
                    │   │                                                 │   │
                    │   │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │   │
                    │   │  │ Queues  │  │  AI     │  │   Vectorize     │ │   │
                    │   │  │  Jobs   │  │ Models  │  │   Embeddings    │ │   │
                    │   │  └─────────┘  └─────────┘  └─────────────────┘ │   │
                    │   └─────────────────────────────────────────────────┘   │
                    │                                                         │
                    │   Global CDN • Zero cold starts • Pay-per-use           │
                    └─────────────────────────────────────────────────────────┘
```

## Resources

### Core Stack
| Resource | Purpose | Use Case |
|----------|---------|----------|
| Pages | Frontend hosting | React/Vue/Svelte SPA |
| Pages Functions | API endpoints | REST/GraphQL API |
| D1 | SQL database | User data, content |
| R2 | Object storage | Files, images |
| KV | Key-value store | Sessions, cache |

### Optional Services
| Resource | Purpose | Use Case |
|----------|---------|----------|
| Queues | Background jobs | Emails, webhooks |
| Workers AI | ML inference | Chat, embeddings |
| Vectorize | Vector search | Semantic search |
| Durable Objects | Real-time state | WebSockets |

## Configuration

### Project Structure
```
my-fullstack-app/
├── package.json
├── wrangler.toml
├── tsconfig.json
├── vite.config.ts
├── src/                        # Frontend
│   ├── App.tsx
│   ├── main.tsx
│   ├── pages/
│   ├── components/
│   └── lib/
├── functions/                  # API (Pages Functions)
│   ├── api/
│   │   ├── auth/
│   │   │   ├── login.ts
│   │   │   ├── register.ts
│   │   │   └── logout.ts
│   │   ├── users/
│   │   │   ├── index.ts
│   │   │   └── [id].ts
│   │   ├── posts/
│   │   │   ├── index.ts
│   │   │   └── [id].ts
│   │   └── upload.ts
│   └── _middleware.ts
├── db/
│   ├── schema.sql
│   └── migrations/
└── public/
```

### wrangler.toml
```toml
name = "my-fullstack-app"
pages_build_output_dir = "dist"
compatibility_date = "2024-01-01"

# D1 Database
[[d1_databases]]
binding = "DB"
database_name = "my-app-db"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# R2 Storage
[[r2_buckets]]
binding = "STORAGE"
bucket_name = "my-app-storage"

# KV Cache
[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"

# KV Sessions
[[kv_namespaces]]
binding = "SESSIONS"
id = "yyyyyyyyyyyyyyyyyyyyy"

# Queues
[[queues.producers]]
queue = "jobs"
binding = "JOBS"

# Workers AI
[ai]
binding = "AI"

# Environment variables
[vars]
ENVIRONMENT = "production"
APP_URL = "https://my-app.pages.dev"
```

### Database Schema
```sql
-- db/schema.sql

-- Users
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar_url TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- Posts
CREATE TABLE posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT,
  slug TEXT UNIQUE NOT NULL,
  published BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_slug ON posts(slug);
CREATE INDEX idx_posts_published ON posts(published);

-- Sessions
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Files
CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  key TEXT UNIQUE NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT,
  size INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## Implementation

### API Types
```typescript
// functions/types.ts
export interface Env {
  DB: D1Database;
  STORAGE: R2Bucket;
  CACHE: KVNamespace;
  SESSIONS: KVNamespace;
  JOBS: Queue;
  AI: Ai;
  APP_URL: string;
}

export interface User {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
}

export interface Session {
  userId: number;
  user: User;
}
```

### Authentication Middleware
```typescript
// functions/_middleware.ts
import { nanoid } from 'nanoid';
import type { Env, Session, User } from './types';

const PUBLIC_PATHS = [
  '/api/auth/login',
  '/api/auth/register',
  '/api/health',
];

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);

  // Skip auth for public paths
  if (PUBLIC_PATHS.some(p => url.pathname.startsWith(p))) {
    return context.next();
  }

  // Skip auth for non-API routes
  if (!url.pathname.startsWith('/api')) {
    return context.next();
  }

  // Get session token
  const token = context.request.headers.get('Authorization')?.replace('Bearer ', '');

  if (!token) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Validate session
  const sessionData = await context.env.SESSIONS.get(`session:${token}`);
  if (!sessionData) {
    return Response.json({ error: 'Invalid session' }, { status: 401 });
  }

  const session: Session = JSON.parse(sessionData);

  // Check expiration
  const sessionMeta = await context.env.DB.prepare(
    'SELECT expires_at FROM sessions WHERE id = ?'
  ).bind(token).first<{ expires_at: string }>();

  if (!sessionMeta || new Date(sessionMeta.expires_at) < new Date()) {
    await context.env.SESSIONS.delete(`session:${token}`);
    return Response.json({ error: 'Session expired' }, { status: 401 });
  }

  // Add session to context
  context.data.session = session;

  return context.next();
};
```

### Auth API
```typescript
// functions/api/auth/register.ts
import { nanoid } from 'nanoid';
import type { Env } from '../../types';

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { email, password, name } = await context.request.json();

  // Hash password (use bcrypt in production)
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const passwordHash = btoa(String.fromCharCode(...new Uint8Array(hashBuffer)));

  try {
    // Create user
    const user = await context.env.DB.prepare(`
      INSERT INTO users (email, password_hash, name)
      VALUES (?, ?, ?)
      RETURNING id, email, name, avatar_url
    `).bind(email, passwordHash, name).first();

    // Create session
    const sessionId = nanoid(32);
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7 days

    await context.env.DB.prepare(`
      INSERT INTO sessions (id, user_id, expires_at)
      VALUES (?, ?, ?)
    `).bind(sessionId, user.id, expiresAt.toISOString()).run();

    await context.env.SESSIONS.put(
      `session:${sessionId}`,
      JSON.stringify({ userId: user.id, user }),
      { expirationTtl: 7 * 24 * 60 * 60 }
    );

    return Response.json({
      user,
      token: sessionId,
      expiresAt: expiresAt.toISOString(),
    }, { status: 201 });

  } catch (error: any) {
    if (error.message?.includes('UNIQUE constraint failed')) {
      return Response.json({ error: 'Email already exists' }, { status: 409 });
    }
    throw error;
  }
};
```

### Posts API
```typescript
// functions/api/posts/index.ts
import type { Env, Session } from '../../types';
import { nanoid } from 'nanoid';

// List posts
export const onRequestGet: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = parseInt(url.searchParams.get('limit') || '20');
  const offset = (page - 1) * limit;

  // Check cache
  const cacheKey = `posts:page:${page}:limit:${limit}`;
  const cached = await context.env.CACHE.get(cacheKey);
  if (cached) {
    return Response.json(JSON.parse(cached));
  }

  const { results } = await context.env.DB.prepare(`
    SELECT p.*, u.name as author_name, u.avatar_url as author_avatar
    FROM posts p
    JOIN users u ON p.user_id = u.id
    WHERE p.published = TRUE
    ORDER BY p.created_at DESC
    LIMIT ? OFFSET ?
  `).bind(limit, offset).all();

  const { count } = await context.env.DB.prepare(`
    SELECT COUNT(*) as count FROM posts WHERE published = TRUE
  `).first<{ count: number }>();

  const response = {
    posts: results,
    pagination: {
      page,
      limit,
      total: count,
      pages: Math.ceil(count / limit),
    },
  };

  // Cache for 5 minutes
  await context.env.CACHE.put(cacheKey, JSON.stringify(response), {
    expirationTtl: 300,
  });

  return Response.json(response);
};

// Create post
export const onRequestPost: PagesFunction<Env> = async (context) => {
  const session = context.data.session as Session;
  const { title, content, published } = await context.request.json();

  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') + '-' + nanoid(6);

  const post = await context.env.DB.prepare(`
    INSERT INTO posts (user_id, title, content, slug, published)
    VALUES (?, ?, ?, ?, ?)
    RETURNING *
  `).bind(session.userId, title, content, slug, published || false).first();

  // Invalidate cache
  const keys = await context.env.CACHE.list({ prefix: 'posts:' });
  await Promise.all(keys.keys.map(k => context.env.CACHE.delete(k.name)));

  return Response.json(post, { status: 201 });
};
```

### File Upload
```typescript
// functions/api/upload.ts
import type { Env, Session } from '../types';
import { nanoid } from 'nanoid';

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const session = context.data.session as Session;
  const formData = await context.request.formData();
  const file = formData.get('file') as File;

  if (!file) {
    return Response.json({ error: 'No file provided' }, { status: 400 });
  }

  // Validate
  const maxSize = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSize) {
    return Response.json({ error: 'File too large' }, { status: 400 });
  }

  // Generate key
  const ext = file.name.split('.').pop();
  const key = `uploads/${session.userId}/${nanoid()}${ext ? `.${ext}` : ''}`;

  // Upload to R2
  await context.env.STORAGE.put(key, file.stream(), {
    httpMetadata: { contentType: file.type },
    customMetadata: { originalName: file.name },
  });

  // Save metadata
  await context.env.DB.prepare(`
    INSERT INTO files (user_id, key, filename, content_type, size)
    VALUES (?, ?, ?, ?, ?)
  `).bind(session.userId, key, file.name, file.type, file.size).run();

  return Response.json({
    key,
    url: `/api/files/${key}`,
    filename: file.name,
    size: file.size,
  }, { status: 201 });
};
```

### Frontend Client
```typescript
// src/lib/api.ts
const API_URL = '/api';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }

  constructor() {
    this.token = localStorage.getItem('token');
  }

  private async fetch<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers as Record<string, string>,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Request failed');
    }

    return response.json();
  }

  // Auth
  async register(data: { email: string; password: string; name: string }) {
    const result = await this.fetch<{ user: User; token: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(result.token);
    return result;
  }

  async login(data: { email: string; password: string }) {
    const result = await this.fetch<{ user: User; token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(result.token);
    return result;
  }

  logout() {
    this.setToken(null);
  }

  // Posts
  async getPosts(page = 1, limit = 20) {
    return this.fetch<{ posts: Post[]; pagination: Pagination }>(
      `/posts?page=${page}&limit=${limit}`
    );
  }

  async createPost(data: { title: string; content: string; published?: boolean }) {
    return this.fetch<Post>('/posts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Upload
  async uploadFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : {},
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    return response.json();
  }
}

export const api = new ApiClient();
```

## Deployment Commands

```bash
# Install dependencies
npm install

# Create D1 database
npx wrangler d1 create my-app-db
npx wrangler d1 execute my-app-db --file=./db/schema.sql

# Create R2 bucket
npx wrangler r2 bucket create my-app-storage

# Create KV namespaces
npx wrangler kv:namespace create CACHE
npx wrangler kv:namespace create SESSIONS

# Create queue
npx wrangler queues create jobs

# Build and deploy
npm run build
npx wrangler pages deploy dist

# Set secrets
npx wrangler secret put JWT_SECRET
```

## Cost Breakdown

| Service | Free Tier | Typical Cost |
|---------|-----------|--------------|
| Pages | Unlimited | $0 |
| Workers/Functions | 100k/day | $0.50/million |
| D1 reads | 5M/day | $0.001/million |
| D1 writes | 100k/day | $1/million |
| D1 storage | 5GB | $0.75/GB |
| R2 storage | 10GB | $0.015/GB |
| R2 egress | **FREE** | **FREE** |
| KV reads | 100k/day | $0.50/million |
| KV writes | 1k/day | $5/million |

### Example Monthly Cost
| Scale | Users | Cost |
|-------|-------|------|
| Small (<1k MAU) | 1k | ~$0 (free tier) |
| Medium (10k MAU) | 10k | ~$10-20 |
| Large (100k MAU) | 100k | ~$50-100 |

## Example Configuration

```yaml
project_name: my-fullstack-app
provider: cloudflare
architecture_type: full_stack

resources:
  - id: pages
    type: cloudflare_pages
    name: my-fullstack-app
    provider: cloudflare
    config:
      build_command: npm run build
      output_directory: dist
      functions_directory: functions

  - id: database
    type: cloudflare_d1
    name: my-app-db
    provider: cloudflare
    config:
      binding: DB

  - id: storage
    type: cloudflare_r2
    name: my-app-storage
    provider: cloudflare
    config:
      binding: STORAGE

  - id: cache
    type: cloudflare_kv
    name: cache
    provider: cloudflare
    config:
      binding: CACHE

  - id: sessions
    type: cloudflare_kv
    name: sessions
    provider: cloudflare
    config:
      binding: SESSIONS

  - id: jobs-queue
    type: cloudflare_queue
    name: jobs
    provider: cloudflare
    config:
      binding: JOBS
```

## Sources

- [Cloudflare Developer Platform](https://developers.cloudflare.com/)
- [Pages Documentation](https://developers.cloudflare.com/pages)
- [D1 Documentation](https://developers.cloudflare.com/d1)
- [R2 Documentation](https://developers.cloudflare.com/r2)
