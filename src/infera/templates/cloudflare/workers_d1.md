# Cloudflare Workers + D1 Database

## Overview

Deploy serverless APIs with D1, Cloudflare's serverless SQLite database. D1 provides a familiar SQL interface with automatic replication, zero cold starts, and pay-per-query pricing.

## Detection Signals

Use this template when:
- SQL database requirements
- Relational data model needed
- CRUD API patterns
- Need for transactions
- SQLite-compatible queries
- Prisma/Drizzle ORM usage

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────┐   │
                    │   │              Worker                      │   │
                    │   │                                         │   │
                    │   │  ┌─────────┐       ┌─────────────────┐  │   │
                    │   │  │  API    │◄─────►│  D1 Database    │  │   │
                    │   │  │ Logic   │       │  (SQLite)       │  │   │
                    │   │  └─────────┘       │                 │  │   │
                    │   │                    │  - Primary      │  │   │
                    │   │                    │  - Read Replicas│  │   │
                    │   │                    └─────────────────┘  │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   Global replication • Automatic failover       │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | API hosting | wrangler.toml |
| D1 Database | Data storage | Binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| KV Namespace | Caching | Binding |
| Custom Domain | Production URL | Routes |

## Configuration

### wrangler.toml
```toml
name = "my-d1-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# Local D1 for development
[env.dev]
[[env.dev.d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "local"

# Production
[env.production]
[[env.production.d1_databases]]
binding = "DB"
database_name = "my-database"
database_id = "xxxxxxxxxxxxxxxxxxxxx"
```

### Database Schema
```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT,
  published BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_published ON posts(published);

-- Trigger to update updated_at
CREATE TRIGGER users_updated_at
  AFTER UPDATE ON users
  BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;
```

## Implementation

### Raw D1 Queries
```typescript
// src/index.ts
import { Hono } from 'hono';

type Bindings = {
  DB: D1Database;
};

type User = {
  id: number;
  email: string;
  name: string;
  created_at: string;
};

type Post = {
  id: number;
  user_id: number;
  title: string;
  content: string | null;
  published: boolean;
};

const app = new Hono<{ Bindings: Bindings }>();

// Users CRUD
app.get('/api/users', async (c) => {
  const { results } = await c.env.DB.prepare(
    'SELECT * FROM users ORDER BY created_at DESC LIMIT 100'
  ).all<User>();

  return c.json(results);
});

app.get('/api/users/:id', async (c) => {
  const id = c.req.param('id');

  const user = await c.env.DB.prepare(
    'SELECT * FROM users WHERE id = ?'
  ).bind(id).first<User>();

  if (!user) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.json(user);
});

app.post('/api/users', async (c) => {
  const { email, name } = await c.req.json();

  try {
    const result = await c.env.DB.prepare(
      'INSERT INTO users (email, name) VALUES (?, ?) RETURNING *'
    ).bind(email, name).first<User>();

    return c.json(result, 201);
  } catch (error: any) {
    if (error.message.includes('UNIQUE constraint failed')) {
      return c.json({ error: 'Email already exists' }, 409);
    }
    throw error;
  }
});

app.put('/api/users/:id', async (c) => {
  const id = c.req.param('id');
  const { email, name } = await c.req.json();

  const result = await c.env.DB.prepare(
    'UPDATE users SET email = ?, name = ? WHERE id = ? RETURNING *'
  ).bind(email, name, id).first<User>();

  if (!result) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.json(result);
});

app.delete('/api/users/:id', async (c) => {
  const id = c.req.param('id');

  const { meta } = await c.env.DB.prepare(
    'DELETE FROM users WHERE id = ?'
  ).bind(id).run();

  if (meta.changes === 0) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.body(null, 204);
});

// Posts with user join
app.get('/api/posts', async (c) => {
  const published = c.req.query('published');

  let query = `
    SELECT p.*, u.name as author_name, u.email as author_email
    FROM posts p
    JOIN users u ON p.user_id = u.id
  `;

  if (published === 'true') {
    query += ' WHERE p.published = TRUE';
  }

  query += ' ORDER BY p.created_at DESC LIMIT 50';

  const { results } = await c.env.DB.prepare(query).all();
  return c.json(results);
});

// Batch insert with transaction
app.post('/api/users/batch', async (c) => {
  const { users } = await c.req.json();

  const statements = users.map((user: { email: string; name: string }) =>
    c.env.DB.prepare(
      'INSERT INTO users (email, name) VALUES (?, ?)'
    ).bind(user.email, user.name)
  );

  const results = await c.env.DB.batch(statements);
  return c.json({ inserted: results.length });
});

export default app;
```

### Using Drizzle ORM
```typescript
// src/db/schema.ts
import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';

export const users = sqliteTable('users', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  email: text('email').notNull().unique(),
  name: text('name').notNull(),
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
});

export const posts = sqliteTable('posts', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  userId: integer('user_id').notNull().references(() => users.id),
  title: text('title').notNull(),
  content: text('content'),
  published: integer('published', { mode: 'boolean' }).default(false),
});

// src/index.ts
import { drizzle } from 'drizzle-orm/d1';
import { eq } from 'drizzle-orm';
import { Hono } from 'hono';
import * as schema from './db/schema';

type Bindings = { DB: D1Database };

const app = new Hono<{ Bindings: Bindings }>();

app.get('/api/users', async (c) => {
  const db = drizzle(c.env.DB, { schema });
  const allUsers = await db.select().from(schema.users).all();
  return c.json(allUsers);
});

app.get('/api/users/:id', async (c) => {
  const db = drizzle(c.env.DB, { schema });
  const id = parseInt(c.req.param('id'));

  const user = await db.select()
    .from(schema.users)
    .where(eq(schema.users.id, id))
    .get();

  if (!user) return c.json({ error: 'Not found' }, 404);
  return c.json(user);
});

app.post('/api/users', async (c) => {
  const db = drizzle(c.env.DB, { schema });
  const { email, name } = await c.req.json();

  const result = await db.insert(schema.users)
    .values({ email, name })
    .returning()
    .get();

  return c.json(result, 201);
});

export default app;
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create D1 database
npx wrangler d1 create my-database

# Apply schema
npx wrangler d1 execute my-database --file=./schema.sql

# Run migrations (production)
npx wrangler d1 execute my-database --file=./schema.sql --remote

# Query database
npx wrangler d1 execute my-database --command="SELECT * FROM users"

# Local development with D1
npx wrangler dev --local --persist

# Deploy
npx wrangler deploy

# Backup database
npx wrangler d1 backup create my-database
npx wrangler d1 backup list my-database
```

## Best Practices

### Query Optimization
1. Use indexes for frequently queried columns
2. Use LIMIT to prevent large result sets
3. Use parameterized queries (never string concatenation)
4. Batch multiple operations with `db.batch()`

### Schema Design
1. Use appropriate data types
2. Add foreign key constraints
3. Create indexes for JOIN columns
4. Use triggers for updated_at timestamps

### Error Handling
1. Handle unique constraint violations
2. Handle foreign key violations
3. Validate input before queries
4. Use transactions for multi-step operations

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Reads | 5M/day | $0.001/million |
| Writes | 100k/day | $1/million |
| Storage | 5GB | $0.75/GB/month |

### Example Monthly Costs
| Scale | Reads | Writes | Storage | Cost |
|-------|-------|--------|---------|------|
| Small | 10M | 500k | 1GB | ~$0 |
| Medium | 100M | 5M | 10GB | ~$13 |
| Large | 1B | 50M | 100GB | ~$126 |

## Common Mistakes

1. **No indexes**: Slow queries on large tables
2. **Large result sets**: Always use LIMIT
3. **String concatenation**: SQL injection risk
4. **Missing error handling**: Unique constraint crashes
5. **No migrations**: Schema changes not tracked
6. **Forgetting --remote**: Queries run locally

## Example Configuration

```yaml
project_name: my-d1-api
provider: cloudflare
architecture_type: workers_d1

resources:
  - id: api-worker
    type: cloudflare_worker
    name: my-d1-api
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"

  - id: database
    type: cloudflare_d1
    name: my-database
    provider: cloudflare
    config:
      binding: DB
```

## Sources

- [D1 Documentation](https://developers.cloudflare.com/d1)
- [D1 SQL Reference](https://developers.cloudflare.com/d1/platform/client-api)
- [Drizzle ORM + D1](https://orm.drizzle.team/docs/get-started-sqlite#cloudflare-d1)
