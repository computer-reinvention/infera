# Cloudflare Workers + KV Storage

## Overview

Deploy serverless APIs with KV (Key-Value) storage for fast, globally distributed data access. KV provides eventually consistent reads with low latency from any edge location. Ideal for caching, sessions, configuration, and read-heavy workloads.

## Detection Signals

Use this template when:
- Session storage requirements
- Caching layer needed
- Configuration/feature flags storage
- Read-heavy workloads (>90% reads)
- Simple key-value data model
- Need for global data distribution

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
                    │   ┌─────────────────────────────────────────┐   │
                    │   │              Worker                      │   │
                    │   │                                         │   │
    Internet ──────►│   │  ┌─────────┐       ┌─────────────────┐  │   │
                    │   │  │  API    │◄─────►│   KV Namespace  │  │   │
                    │   │  │ Logic   │       │                 │  │   │
                    │   │  └─────────┘       │  ┌───────────┐  │  │   │
                    │   │                    │  │ Edge Cache │  │  │   │
                    │   │                    │  └───────────┘  │  │   │
                    │   │                    │       ▲         │  │   │
                    │   │                    │       │ Replicate│  │   │
                    │   │                    │  ┌────┴──────┐  │  │   │
                    │   │                    │  │  Central  │  │  │   │
                    │   │                    │  │  Storage  │  │  │   │
                    │   │                    │  └───────────┘  │  │   │
                    │   │                    └─────────────────┘  │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   Eventually consistent • Read at edge          │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | API hosting | wrangler.toml |
| KV Namespace | Data storage | Binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| D1 Database | Complex queries | Binding |
| Custom Domain | Production URL | Routes |

## Configuration

### wrangler.toml
```toml
name = "my-kv-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

# KV Namespaces
[[kv_namespaces]]
binding = "SESSIONS"
id = "xxxxxxxxxxxxxxxxxxxxx"

[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"

[[kv_namespaces]]
binding = "CONFIG"
id = "xxxxxxxxxxxxxxxxxxxxx"

# Preview namespaces (for wrangler dev)
[[kv_namespaces]]
binding = "SESSIONS"
id = "xxxxxxxxxxxxxxxxxxxxx"
preview_id = "yyyyyyyyyyyyyyyyyyyyy"

# Environment-specific
[env.production.kv_namespaces]
binding = "SESSIONS"
id = "prod-xxxxxxxxxxxxxxxxxxxxx"
```

## Implementation

### Session Management
```typescript
// src/sessions.ts
import { Hono } from 'hono';
import { nanoid } from 'nanoid';

type Bindings = {
  SESSIONS: KVNamespace;
};

type Session = {
  userId: string;
  email: string;
  roles: string[];
  createdAt: string;
  expiresAt: string;
};

const SESSION_TTL = 60 * 60 * 24; // 24 hours

export const sessions = new Hono<{ Bindings: Bindings }>();

// Create session
sessions.post('/sessions', async (c) => {
  const { userId, email, roles } = await c.req.json();

  const sessionId = nanoid(32);
  const now = new Date();
  const expiresAt = new Date(now.getTime() + SESSION_TTL * 1000);

  const session: Session = {
    userId,
    email,
    roles: roles || [],
    createdAt: now.toISOString(),
    expiresAt: expiresAt.toISOString(),
  };

  await c.env.SESSIONS.put(
    `session:${sessionId}`,
    JSON.stringify(session),
    { expirationTtl: SESSION_TTL }
  );

  return c.json({
    sessionId,
    expiresAt: session.expiresAt
  }, 201);
});

// Get session
sessions.get('/sessions/:id', async (c) => {
  const sessionId = c.req.param('id');

  const data = await c.env.SESSIONS.get(`session:${sessionId}`);

  if (!data) {
    return c.json({ error: 'Session not found' }, 404);
  }

  const session: Session = JSON.parse(data);
  return c.json(session);
});

// Delete session (logout)
sessions.delete('/sessions/:id', async (c) => {
  const sessionId = c.req.param('id');
  await c.env.SESSIONS.delete(`session:${sessionId}`);
  return c.body(null, 204);
});

// Middleware to validate session
export async function validateSession(
  sessionId: string | null,
  kv: KVNamespace
): Promise<Session | null> {
  if (!sessionId) return null;

  const data = await kv.get(`session:${sessionId}`);
  if (!data) return null;

  const session: Session = JSON.parse(data);

  // Check expiration
  if (new Date(session.expiresAt) < new Date()) {
    await kv.delete(`session:${sessionId}`);
    return null;
  }

  return session;
}
```

### Caching Layer
```typescript
// src/cache.ts
import { Hono } from 'hono';

type Bindings = {
  CACHE: KVNamespace;
};

type CacheOptions = {
  ttl?: number;
  metadata?: Record<string, string>;
};

export class CacheService {
  constructor(private kv: KVNamespace) {}

  async get<T>(key: string): Promise<T | null> {
    const data = await this.kv.get(key);
    if (!data) return null;
    return JSON.parse(data) as T;
  }

  async set<T>(key: string, value: T, options: CacheOptions = {}): Promise<void> {
    const { ttl = 3600, metadata } = options;
    await this.kv.put(key, JSON.stringify(value), {
      expirationTtl: ttl,
      metadata,
    });
  }

  async delete(key: string): Promise<void> {
    await this.kv.delete(key);
  }

  async getOrSet<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: CacheOptions = {}
  ): Promise<T> {
    const cached = await this.get<T>(key);
    if (cached !== null) {
      return cached;
    }

    const value = await fetcher();
    await this.set(key, value, options);
    return value;
  }

  // List keys with prefix
  async list(prefix: string, limit: number = 1000): Promise<string[]> {
    const { keys } = await this.kv.list({ prefix, limit });
    return keys.map(k => k.name);
  }

  // Delete all keys with prefix
  async deletePrefix(prefix: string): Promise<number> {
    const keys = await this.list(prefix);
    await Promise.all(keys.map(k => this.delete(k)));
    return keys.length;
  }
}

// Usage in API
export const cache = new Hono<{ Bindings: Bindings }>();

cache.get('/api/products/:id', async (c) => {
  const cacheService = new CacheService(c.env.CACHE);
  const productId = c.req.param('id');

  const product = await cacheService.getOrSet(
    `product:${productId}`,
    async () => {
      // Fetch from origin (database, external API, etc.)
      const response = await fetch(`https://api.example.com/products/${productId}`);
      return response.json();
    },
    { ttl: 300 } // 5 minutes
  );

  return c.json(product);
});

// Cache invalidation
cache.delete('/api/products/:id/cache', async (c) => {
  const cacheService = new CacheService(c.env.CACHE);
  const productId = c.req.param('id');
  await cacheService.delete(`product:${productId}`);
  return c.json({ invalidated: true });
});
```

### Feature Flags
```typescript
// src/features.ts
import { Hono } from 'hono';

type Bindings = {
  CONFIG: KVNamespace;
};

type FeatureFlag = {
  enabled: boolean;
  percentage?: number; // For gradual rollout
  allowedUsers?: string[];
  metadata?: Record<string, any>;
};

export class FeatureFlags {
  constructor(private kv: KVNamespace) {}

  async isEnabled(
    flagName: string,
    userId?: string
  ): Promise<boolean> {
    const data = await this.kv.get(`flag:${flagName}`);
    if (!data) return false;

    const flag: FeatureFlag = JSON.parse(data);

    // Check if globally disabled
    if (!flag.enabled) return false;

    // Check allowed users
    if (flag.allowedUsers && userId) {
      if (flag.allowedUsers.includes(userId)) return true;
    }

    // Check percentage rollout
    if (flag.percentage !== undefined && userId) {
      const hash = this.hashUserId(userId, flagName);
      return hash < flag.percentage;
    }

    return flag.enabled;
  }

  private hashUserId(userId: string, flagName: string): number {
    // Simple hash for consistent percentage allocation
    let hash = 0;
    const str = `${userId}:${flagName}`;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash = hash & hash;
    }
    return Math.abs(hash % 100);
  }

  async setFlag(flagName: string, flag: FeatureFlag): Promise<void> {
    await this.kv.put(`flag:${flagName}`, JSON.stringify(flag));
  }

  async listFlags(): Promise<{ name: string; flag: FeatureFlag }[]> {
    const { keys } = await this.kv.list({ prefix: 'flag:' });
    const flags = await Promise.all(
      keys.map(async (k) => {
        const data = await this.kv.get(k.name);
        return {
          name: k.name.replace('flag:', ''),
          flag: JSON.parse(data!) as FeatureFlag,
        };
      })
    );
    return flags;
  }
}

// API routes
export const features = new Hono<{ Bindings: Bindings }>();

features.get('/api/features', async (c) => {
  const ff = new FeatureFlags(c.env.CONFIG);
  const flags = await ff.listFlags();
  return c.json(flags);
});

features.get('/api/features/:name', async (c) => {
  const ff = new FeatureFlags(c.env.CONFIG);
  const name = c.req.param('name');
  const userId = c.req.query('userId');

  const enabled = await ff.isEnabled(name, userId);
  return c.json({ name, enabled });
});

features.put('/api/features/:name', async (c) => {
  const ff = new FeatureFlags(c.env.CONFIG);
  const name = c.req.param('name');
  const flag = await c.req.json();

  await ff.setFlag(name, flag);
  return c.json({ name, ...flag });
});
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create KV namespaces
npx wrangler kv:namespace create SESSIONS
npx wrangler kv:namespace create CACHE
npx wrangler kv:namespace create CONFIG

# Create preview namespaces
npx wrangler kv:namespace create SESSIONS --preview

# List namespaces
npx wrangler kv:namespace list

# Put a key
npx wrangler kv:key put --namespace-id=xxx "key" "value"

# Get a key
npx wrangler kv:key get --namespace-id=xxx "key"

# Delete a key
npx wrangler kv:key delete --namespace-id=xxx "key"

# Bulk upload
npx wrangler kv:bulk put --namespace-id=xxx data.json

# Deploy
npx wrangler deploy
```

## Best Practices

### Data Model
1. Use consistent key naming (prefix:id format)
2. Keep values small (< 25MB, ideally < 1KB)
3. Store JSON for complex data
4. Use TTL for expiring data

### Performance
1. KV is optimized for reads (eventually consistent)
2. Writes propagate globally in ~60 seconds
3. Use metadata for small frequently-accessed data
4. Batch operations when possible

### Consistency
1. KV is eventually consistent
2. Not suitable for counters or real-time data
3. Use D1 for strong consistency needs
4. Consider read-your-writes patterns

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Reads | 100k/day | $0.50/million |
| Writes | 1k/day | $5/million |
| Deletes | 1k/day | $5/million |
| Lists | 1k/day | $5/million |
| Storage | 1GB | $0.50/GB/month |

### Example Costs
| Scale | Reads/mo | Writes/mo | Cost |
|-------|----------|-----------|------|
| Small | 1M | 10k | ~$0.55 |
| Medium | 100M | 1M | ~$55 |
| Large | 1B | 10M | ~$550 |

## Common Mistakes

1. **Using KV for writes**: KV is read-optimized
2. **Expecting strong consistency**: Updates take ~60s to propagate
3. **Large values**: Keep values small for performance
4. **No TTL**: Forgetting to expire stale data
5. **Missing namespace**: Forgetting to create/bind namespace
6. **List limitations**: Can only list 1000 keys at a time

## Example Configuration

```yaml
project_name: my-kv-api
provider: cloudflare
architecture_type: workers_kv

resources:
  - id: api-worker
    type: cloudflare_worker
    name: my-kv-api
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"

  - id: sessions
    type: cloudflare_kv
    name: sessions
    provider: cloudflare
    config:
      binding: SESSIONS

  - id: cache
    type: cloudflare_kv
    name: cache
    provider: cloudflare
    config:
      binding: CACHE

  - id: config
    type: cloudflare_kv
    name: config
    provider: cloudflare
    config:
      binding: CONFIG
```

## Sources

- [KV Documentation](https://developers.cloudflare.com/kv)
- [KV Best Practices](https://developers.cloudflare.com/kv/learning/kv-best-practices)
- [KV Pricing](https://developers.cloudflare.com/kv/platform/pricing)
