# PostgreSQL Serverless

## Overview
Serverless PostgreSQL provides auto-scaling database capacity that scales to zero when idle and automatically handles connection pooling. Ideal for variable workloads, development environments, and cost-sensitive applications.

**Use when:**
- Traffic is unpredictable or bursty
- You want to minimize costs during low usage
- Development/staging environments
- Branching workflows (Neon)
- You need instant provisioning

**Don't use when:**
- Consistent high traffic (cheaper to use provisioned)
- You need guaranteed latency (cold starts exist)
- Complex HA requirements
- Very large databases (> 1 TB)

## Detection Signals

```
Files:
- .neon/config.json
- neon.json
- supabase/config.toml (with pooler mode)
- serverless.yml with aurora-serverless

Dependencies:
- @neondatabase/serverless (Node.js)
- neon-serverless (Python)

Code Patterns:
- neon.tech connection strings
- Aurora Serverless v2 configurations
- Connection pooler endpoints
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Serverless PostgreSQL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │   │
│  │  │  Vercel    │  │ Cloudflare │  │   Lambda   │         │   │
│  │  │  Function  │  │  Worker    │  │  Function  │         │   │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘         │   │
│  │        │               │               │                 │   │
│  └────────┼───────────────┼───────────────┼─────────────────┘   │
│           │               │               │                      │
│           └───────────────┼───────────────┘                      │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │              Built-in Connection Pooler                   │   │
│  │  • HTTP/WebSocket connections                            │   │
│  │  • Automatic connection management                        │   │
│  │  • Sub-10ms cold start (Neon)                            │   │
│  │  • Transaction support                                    │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │                   Compute Layer                           │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │              Auto-scaling Compute                   │  │   │
│  │  │  • Scale to zero when idle                         │  │   │
│  │  │  • Instant scale-up on demand                      │  │   │
│  │  │  • 0.25 - 8 vCPU (Neon) / 0.5 - 128 ACU (Aurora)  │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │                   Storage Layer                           │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │           Separated Storage (Neon)                  │  │   │
│  │  │  • Copy-on-write branching                         │  │   │
│  │  │  • Point-in-time restore                           │  │   │
│  │  │  • Storage-only billing when idle                  │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Neon | Aurora Serverless v2 | Supabase | PlanetScale |
|---------|------|---------------------|----------|-------------|
| **Min Cost** | $0 (free tier) | ~$43/mo minimum | $0 (free tier) | $0 (free tier) |
| **Scale to Zero** | Yes | No (0.5 ACU min) | No | Yes |
| **Cold Start** | ~500ms | N/A | N/A | ~1s |
| **Branching** | Native | No | No | Native |
| **Max Compute** | 8 vCPU | 128 ACU | Fixed | N/A (MySQL) |
| **Connection Pooling** | Built-in | Built-in | Built-in | Built-in |
| **Edge-compatible** | Yes | No | Partial | Yes |
| **PostgreSQL** | Yes | Yes | Yes | No (MySQL) |

## Neon Configuration

### Project Setup

```bash
# Install Neon CLI
npm install -g neonctl

# Authenticate
neonctl auth

# Create project
neonctl projects create --name my-project --region-id aws-us-east-1

# Create database
neonctl databases create --name mydb --project-id <project-id>

# Get connection string
neonctl connection-string --project-id <project-id> --database-name mydb
```

### Connection Strings

```bash
# Pooled connection (recommended for serverless)
# Use for Vercel, Cloudflare Workers, Lambda
postgresql://user:pass@ep-cool-name-123456.us-east-1.aws.neon.tech/mydb?sslmode=require

# Direct connection (for migrations)
postgresql://user:pass@ep-cool-name-123456.us-east-1.aws.neon.tech:5432/mydb?sslmode=require

# Pooled via pgbouncer (transaction mode)
postgresql://user:pass@ep-cool-name-123456-pooler.us-east-1.aws.neon.tech/mydb?sslmode=require
```

### Neon Serverless Driver

```typescript
// For edge runtimes (Cloudflare Workers, Vercel Edge)
import { neon, neonConfig } from '@neondatabase/serverless';

// Configure for edge
neonConfig.fetchConnectionCache = true;

const sql = neon(process.env.DATABASE_URL!);

// Simple query
const users = await sql`SELECT * FROM users WHERE id = ${userId}`;

// Transaction
import { neon, Pool } from '@neondatabase/serverless';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

const client = await pool.connect();
try {
  await client.query('BEGIN');
  await client.query('INSERT INTO users (name) VALUES ($1)', ['Alice']);
  await client.query('INSERT INTO logs (action) VALUES ($1)', ['user_created']);
  await client.query('COMMIT');
} catch (e) {
  await client.query('ROLLBACK');
  throw e;
} finally {
  client.release();
}
```

### Neon Branching

```bash
# Create branch from main
neonctl branches create --name feature-auth --parent main

# Get branch connection string
neonctl connection-string --branch feature-auth

# Reset branch to parent state
neonctl branches reset feature-auth --parent main

# Delete branch
neonctl branches delete feature-auth
```

### Terraform Configuration (Neon)

```hcl
# neon.tf

terraform {
  required_providers {
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.2"
    }
  }
}

provider "neon" {
  api_key = var.neon_api_key
}

resource "neon_project" "main" {
  name      = var.project_name
  region_id = "aws-us-east-1"

  default_endpoint_settings {
    autoscaling_limit_min_cu = 0.25
    autoscaling_limit_max_cu = 4
    suspend_timeout_seconds  = 300  # Scale to zero after 5 min
  }

  quota {
    active_time_seconds = 360000  # 100 hours/month
    compute_time_seconds = 360000
  }
}

resource "neon_branch" "main" {
  project_id = neon_project.main.id
  name       = "main"
}

resource "neon_database" "main" {
  project_id = neon_project.main.id
  branch_id  = neon_branch.main.id
  name       = var.database_name
  owner_name = neon_role.main.name
}

resource "neon_role" "main" {
  project_id = neon_project.main.id
  branch_id  = neon_branch.main.id
  name       = var.database_user
}

resource "neon_endpoint" "main" {
  project_id = neon_project.main.id
  branch_id  = neon_branch.main.id
  type       = "read_write"

  autoscaling_limit_min_cu = 0.25
  autoscaling_limit_max_cu = 4
  suspend_timeout_seconds  = 300
}

# Development branch
resource "neon_branch" "dev" {
  project_id = neon_project.main.id
  parent_id  = neon_branch.main.id
  name       = "development"
}

resource "neon_endpoint" "dev" {
  project_id = neon_project.main.id
  branch_id  = neon_branch.dev.id
  type       = "read_write"

  autoscaling_limit_min_cu = 0.25
  autoscaling_limit_max_cu = 1
  suspend_timeout_seconds  = 60  # Aggressive scale-down for dev
}

output "connection_uri" {
  value     = neon_endpoint.main.connection_uri
  sensitive = true
}

output "dev_connection_uri" {
  value     = neon_endpoint.dev.connection_uri
  sensitive = true
}
```

## Aurora Serverless v2 Configuration

### Terraform Configuration

```hcl
# aurora_serverless.tf

resource "aws_rds_cluster" "serverless" {
  cluster_identifier     = "${var.project_name}-aurora"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.4"
  database_name          = var.database_name
  master_username        = var.database_user
  master_password        = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  storage_encrypted = true

  # Serverless v2 configuration
  serverlessv2_scaling_configuration {
    min_capacity = 0.5   # 0.5 ACU minimum
    max_capacity = 16    # Can go up to 128 ACU
  }

  backup_retention_period = 30
  preferred_backup_window = "03:00-04:00"

  skip_final_snapshot = var.environment != "production"

  enabled_cloudwatch_logs_exports = ["postgresql"]
}

resource "aws_rds_cluster_instance" "serverless" {
  count = var.instance_count

  identifier         = "${var.project_name}-aurora-${count.index}"
  cluster_identifier = aws_rds_cluster.serverless.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.serverless.engine
  engine_version     = aws_rds_cluster.serverless.engine_version

  performance_insights_enabled = true
}

# RDS Proxy for Lambda connections
resource "aws_db_proxy" "aurora" {
  name                   = "${var.project_name}-proxy"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  vpc_security_group_ids = [aws_security_group.aurora.id]
  vpc_subnet_ids         = aws_subnet.private[*].id

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db_credentials.arn
  }
}

resource "aws_db_proxy_default_target_group" "aurora" {
  db_proxy_name = aws_db_proxy.aurora.name

  connection_pool_config {
    max_connections_percent      = 100
    max_idle_connections_percent = 50
  }
}

resource "aws_db_proxy_target" "aurora" {
  db_proxy_name          = aws_db_proxy.aurora.name
  target_group_name      = aws_db_proxy_default_target_group.aurora.name
  db_cluster_identifier  = aws_rds_cluster.serverless.id
}

output "cluster_endpoint" {
  value = aws_rds_cluster.serverless.endpoint
}

output "proxy_endpoint" {
  value = aws_db_proxy.aurora.endpoint
}
```

## Application Integration

### Vercel + Neon

```typescript
// lib/db.ts
import { neon, neonConfig } from '@neondatabase/serverless';

// Enable connection caching for serverless
neonConfig.fetchConnectionCache = true;

export const sql = neon(process.env.DATABASE_URL!);

// Usage in API route
// app/api/users/route.ts
import { sql } from '@/lib/db';

export async function GET() {
  const users = await sql`SELECT * FROM users LIMIT 10`;
  return Response.json(users);
}
```

### Cloudflare Workers + Neon

```typescript
// worker.ts
import { neon, neonConfig } from '@neondatabase/serverless';

export interface Env {
  DATABASE_URL: string;
}

neonConfig.fetchConnectionCache = true;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const sql = neon(env.DATABASE_URL);

    const url = new URL(request.url);

    if (url.pathname === '/users') {
      const users = await sql`SELECT * FROM users`;
      return Response.json(users);
    }

    return new Response('Not Found', { status: 404 });
  },
};
```

### Drizzle ORM with Neon

```typescript
// db/schema.ts
import { pgTable, serial, text, timestamp, uuid } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  email: text('email').notNull().unique(),
  name: text('name'),
  createdAt: timestamp('created_at').defaultNow(),
});

// db/index.ts
import { drizzle } from 'drizzle-orm/neon-http';
import { neon } from '@neondatabase/serverless';
import * as schema from './schema';

const sql = neon(process.env.DATABASE_URL!);
export const db = drizzle(sql, { schema });

// Usage
import { db } from '@/db';
import { users } from '@/db/schema';
import { eq } from 'drizzle-orm';

const allUsers = await db.select().from(users);
const user = await db.select().from(users).where(eq(users.id, userId));
```

### Prisma with Neon

```prisma
// schema.prisma
datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_URL")  // For migrations
}

generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["driverAdapters"]
}
```

```typescript
// lib/prisma.ts
import { Pool, neonConfig } from '@neondatabase/serverless';
import { PrismaNeon } from '@prisma/adapter-neon';
import { PrismaClient } from '@prisma/client';

neonConfig.fetchConnectionCache = true;

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const adapter = new PrismaNeon(pool);

export const prisma = new PrismaClient({ adapter });
```

### Lambda + Aurora Serverless

```python
# lambda_function.py
import os
import json
import psycopg2
from psycopg2 import pool

# Connection pool (reused across invocations)
connection_pool = None

def get_connection():
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.environ['RDS_PROXY_ENDPOINT'],
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            connect_timeout=5,
        )
    return connection_pool.getconn()

def return_connection(conn):
    if connection_pool:
        connection_pool.putconn(conn)

def lambda_handler(event, context):
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users LIMIT 10")
            users = cur.fetchall()
            return {
                'statusCode': 200,
                'body': json.dumps(users, default=str)
            }
    finally:
        if conn:
            return_connection(conn)
```

## Branch-Based Development Workflow

### GitHub Actions Integration

```yaml
# .github/workflows/preview.yml
name: Preview Environment

on:
  pull_request:
    types: [opened, synchronize, reopened, closed]

jobs:
  create-branch:
    if: github.event.action != 'closed'
    runs-on: ubuntu-latest
    steps:
      - uses: neondatabase/create-branch-action@v4
        id: create-branch
        with:
          project_id: ${{ secrets.NEON_PROJECT_ID }}
          branch_name: preview/pr-${{ github.event.number }}
          api_key: ${{ secrets.NEON_API_KEY }}

      - name: Run Migrations
        env:
          DATABASE_URL: ${{ steps.create-branch.outputs.db_url }}
        run: |
          npx prisma migrate deploy

      - name: Deploy Preview
        env:
          DATABASE_URL: ${{ steps.create-branch.outputs.db_url }}
        run: |
          vercel deploy --prebuilt --env DATABASE_URL=$DATABASE_URL

  delete-branch:
    if: github.event.action == 'closed'
    runs-on: ubuntu-latest
    steps:
      - uses: neondatabase/delete-branch-action@v3
        with:
          project_id: ${{ secrets.NEON_PROJECT_ID }}
          branch: preview/pr-${{ github.event.number }}
          api_key: ${{ secrets.NEON_API_KEY }}
```

### Vercel Integration

```json
// vercel.json
{
  "build": {
    "env": {
      "DATABASE_URL": "@neon_database_url",
      "DIRECT_URL": "@neon_direct_url"
    }
  }
}
```

```bash
# Install Neon Vercel integration
# Go to: https://vercel.com/integrations/neon

# This automatically:
# - Creates preview branches for each deployment
# - Sets DATABASE_URL environment variable
# - Deletes branches when PR is closed
```

## Cost Breakdown

### Neon

| Plan | Compute | Storage | Features | Monthly |
|------|---------|---------|----------|---------|
| Free | 191 hours | 0.5 GB | 1 project, basic | $0 |
| Launch | 300 hours | 10 GB | 10 projects | $19 |
| Scale | 750 hours | 50 GB | Unlimited projects | $69 |
| Business | Unlimited | 500 GB | SLA, support | $700+ |

**Pay-as-you-go (Scale plan):**
- Compute: $0.16/hour per CU (0.25-8 CU)
- Storage: $0.000164/GB-hour (~$0.12/GB-month)
- Written data: $0.09/GB

### Aurora Serverless v2

| Configuration | Min ACU | Max ACU | Monthly (estimated) |
|--------------|---------|---------|---------------------|
| Dev/Test | 0.5 | 2 | ~$43 + storage |
| Small Prod | 0.5 | 8 | ~$100 + storage |
| Medium Prod | 2 | 32 | ~$400 + storage |
| Large Prod | 4 | 64 | ~$800 + storage |

**Pricing:**
- Compute: $0.12/ACU-hour
- Storage: $0.10/GB-month
- I/O: $0.20 per million requests

### Cost Comparison (Example: Variable Traffic App)

| Scenario | Neon (Scale) | Aurora Serverless v2 |
|----------|--------------|---------------------|
| 10 hrs/day activity | ~$25/mo | ~$50/mo |
| Always-on low traffic | ~$45/mo | ~$43/mo |
| Spiky traffic (0-4 CU) | ~$35/mo | ~$80/mo |
| Scale to zero needed | ✅ $0 idle | ❌ ~$43 min |

## Best Practices

### Connection Handling

```typescript
// GOOD - Use HTTP driver for edge/serverless
import { neon } from '@neondatabase/serverless';
const sql = neon(process.env.DATABASE_URL);

// GOOD - Use pooled connection for server
import { Pool } from '@neondatabase/serverless';
const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// BAD - Creating new Pool per request
export async function handler() {
  const pool = new Pool({ connectionString: process.env.DATABASE_URL }); // Don't do this
  // ...
}
```

### Query Optimization for Serverless

```typescript
// GOOD - Single round-trip with batch
const sql = neon(process.env.DATABASE_URL);

const [users, posts, comments] = await sql.transaction([
  sql`SELECT * FROM users WHERE id = ${userId}`,
  sql`SELECT * FROM posts WHERE author_id = ${userId}`,
  sql`SELECT * FROM comments WHERE user_id = ${userId}`,
]);

// BAD - Multiple round-trips
const user = await sql`SELECT * FROM users WHERE id = ${userId}`;
const posts = await sql`SELECT * FROM posts WHERE author_id = ${userId}`;
const comments = await sql`SELECT * FROM comments WHERE user_id = ${userId}`;
```

### Cold Start Mitigation

```typescript
// Keep compute warm with scheduled pings
// Vercel cron job
// vercel.json
{
  "crons": [{
    "path": "/api/keep-warm",
    "schedule": "*/5 * * * *"
  }]
}

// app/api/keep-warm/route.ts
import { sql } from '@/lib/db';

export async function GET() {
  await sql`SELECT 1`;
  return new Response('OK');
}
```

## Common Mistakes

1. **Not using pooled connections** - Direct connections exhaust limits in serverless
2. **Creating pools per request** - Causes connection storms
3. **Ignoring cold starts** - Not warming database for latency-sensitive apps
4. **Using Aurora Serverless for scale-to-zero** - Minimum 0.5 ACU (~$43/mo)
5. **Not using branches for development** - Missing out on instant dev environments
6. **Large migrations on serverless** - May timeout; run from stable connection
7. **Not setting suspend timeout** - Leaving compute running when idle
8. **Over-provisioning max compute** - Setting unnecessarily high limits
9. **Using wrong connection string** - Direct vs pooled for different use cases
10. **Not testing cold start behavior** - Production surprises

## Example Configuration

```yaml
# infera.yaml
project_name: my-serverless-app
provider: neon  # or aws (aurora)
environment: production

database:
  type: postgres_serverless
  provider: neon

  project:
    name: my-app-prod
    region: aws-us-east-1

  compute:
    min_cu: 0.25
    max_cu: 4
    suspend_timeout_seconds: 300

  branches:
    main:
      protected: true
    development:
      parent: main
      auto_delete: false
    preview:
      parent: main
      auto_delete: true
      pattern: "preview/pr-*"

  integrations:
    vercel: true
    github_actions: true

application:
  runtime: vercel
  framework: nextjs

  env:
    DATABASE_URL:
      from: neon
      pooled: true
    DIRECT_URL:
      from: neon
      pooled: false
```

## Sources

- [Neon Documentation](https://neon.tech/docs)
- [Neon Serverless Driver](https://github.com/neondatabase/serverless)
- [Aurora Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Drizzle ORM + Neon](https://orm.drizzle.team/docs/get-started-postgresql#neon)
- [Prisma + Neon](https://www.prisma.io/docs/guides/database/neon)
- [Neon Branching](https://neon.tech/docs/introduction/branching)
