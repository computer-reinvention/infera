# PlanetScale

## Overview
PlanetScale is a serverless MySQL-compatible database platform built on Vitess. It offers branching workflows similar to Git, non-blocking schema changes, and horizontal scaling without the operational complexity of managing a database cluster.

**Use when:**
- Need MySQL compatibility with modern DevOps workflows
- Want Git-like branching for database schema changes
- Need horizontal scaling (sharding) without complexity
- Require non-blocking schema migrations
- Building applications that may need to scale significantly

**Don't use when:**
- Need foreign key constraints (not supported)
- Require PostgreSQL features
- Have very low traffic (may be overkill)
- Need on-premise deployment

## Detection Signals

```
Files:
- .pscale.yml
- pscale/

Dependencies:
- @planetscale/database (Node.js serverless driver)
- mysql2 (Node.js)
- mysqlclient, pymysql (Python)

Code Patterns:
- DATABASE_URL with aws.connect.psdb.cloud
- pscale CLI commands
- Vitess-specific syntax
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PlanetScale Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Vercel  │  │Cloudflare│  │ Lambda  │  │ Server  │     │   │
│  │  │ Edge    │  │ Worker   │  │         │  │         │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  │       │            │            │            │           │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          │            │            │            │                │
│          │  HTTP/TLS  │            │   MySQL    │                │
│          │  (Serverless)           │  Protocol  │                │
│          └────────────┴──────┬─────┴────────────┘                │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    PlanetScale                             │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │                 Vitess Cluster                       │  │  │
│  │  │                                                      │  │  │
│  │  │  ┌───────────┐  ┌───────────┐  ┌───────────┐       │  │  │
│  │  │  │  VTGate   │  │  VTGate   │  │  VTGate   │       │  │  │
│  │  │  │ (Router)  │  │ (Router)  │  │ (Router)  │       │  │  │
│  │  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘       │  │  │
│  │  │        │              │              │              │  │  │
│  │  │        └──────────────┼──────────────┘              │  │  │
│  │  │                       │                             │  │  │
│  │  │  ┌────────────────────▼────────────────────────┐   │  │  │
│  │  │  │              VTTablet (Shards)               │   │  │  │
│  │  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │  │  │
│  │  │  │  │ Shard 1 │  │ Shard 2 │  │ Shard N │     │   │  │  │
│  │  │  │  │ Primary │  │ Primary │  │ Primary │     │   │  │  │
│  │  │  │  │ Replica │  │ Replica │  │ Replica │     │   │  │  │
│  │  │  │  └─────────┘  └─────────┘  └─────────┘     │   │  │  │
│  │  │  └─────────────────────────────────────────────┘   │  │  │
│  │  │                                                      │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  Features:                                                 │  │
│  │  • Database branching (like Git)                          │  │
│  │  • Non-blocking schema changes                            │  │
│  │  • Automatic horizontal scaling                           │  │
│  │  • Built-in connection pooling                            │  │
│  │  • Serverless driver for edge                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## PlanetScale CLI Setup

```bash
# Install CLI
brew install planetscale/tap/pscale

# Or with npm
npm install -g pscale

# Authenticate
pscale auth login

# Create database
pscale database create my-app --region us-east

# Create branch
pscale branch create my-app development

# Connect to branch (creates secure tunnel)
pscale connect my-app development --port 3306

# Create deploy request (like PR for schema changes)
pscale deploy-request create my-app development

# Deploy to production
pscale deploy-request deploy my-app <deploy-request-number>

# Get connection string
pscale password create my-app main my-app-password
```

## Branch Workflow

```bash
# Development workflow similar to Git

# 1. Create feature branch from main
pscale branch create my-app add-users-table --from main

# 2. Connect and make schema changes
pscale connect my-app add-users-table --port 3306
mysql -h 127.0.0.1 -P 3306 -u root

# 3. Apply migrations
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY idx_users_email (email)
);

# 4. Create deploy request
pscale deploy-request create my-app add-users-table

# 5. Review schema diff in PlanetScale dashboard

# 6. Deploy to main
pscale deploy-request deploy my-app 1

# 7. Delete feature branch
pscale branch delete my-app add-users-table
```

## Connection Configuration

### Connection Strings

```bash
# Standard MySQL connection (for servers)
mysql://username:password@aws.connect.psdb.cloud/database?ssl={"rejectUnauthorized":true}

# Serverless driver (for edge/serverless)
# Uses HTTP protocol, no TCP connection needed
DATABASE_URL="mysql://username:password@aws.connect.psdb.cloud/database?sslaccept=strict"
```

### Environment Variables

```bash
# .env
DATABASE_HOST=aws.connect.psdb.cloud
DATABASE_USERNAME=your-username
DATABASE_PASSWORD=your-password
DATABASE_NAME=my-app

# Or single URL
DATABASE_URL="mysql://username:password@aws.connect.psdb.cloud/my-app?ssl={\"rejectUnauthorized\":true}"
```

## Application Integration

### Node.js (Serverless Driver - Edge Compatible)

```typescript
// db.ts - For Vercel Edge, Cloudflare Workers
import { connect } from '@planetscale/database';

const config = {
  host: process.env.DATABASE_HOST,
  username: process.env.DATABASE_USERNAME,
  password: process.env.DATABASE_PASSWORD,
};

export const conn = connect(config);

// Usage
export async function getUsers() {
  const results = await conn.execute('SELECT * FROM users LIMIT 100');
  return results.rows;
}

export async function createUser(email: string, name: string) {
  const result = await conn.execute(
    'INSERT INTO users (email, name) VALUES (?, ?)',
    [email, name]
  );
  return result.insertId;
}

export async function getUserByEmail(email: string) {
  const results = await conn.execute(
    'SELECT * FROM users WHERE email = ?',
    [email]
  );
  return results.rows[0] || null;
}

// Transaction support
export async function transferCredits(fromId: string, toId: string, amount: number) {
  const tx = conn.transaction(async (tx) => {
    await tx.execute(
      'UPDATE users SET credits = credits - ? WHERE id = ? AND credits >= ?',
      [amount, fromId, amount]
    );
    await tx.execute(
      'UPDATE users SET credits = credits + ? WHERE id = ?',
      [amount, toId]
    );
  });
  return tx;
}
```

### Node.js (mysql2 - for long-running servers)

```typescript
// db.ts - For traditional servers
import mysql from 'mysql2/promise';

const pool = mysql.createPool({
  host: process.env.DATABASE_HOST,
  user: process.env.DATABASE_USERNAME,
  password: process.env.DATABASE_PASSWORD,
  database: process.env.DATABASE_NAME,
  ssl: {
    rejectUnauthorized: true,
  },
  waitForConnections: true,
  connectionLimit: 10,
  maxIdle: 10,
  idleTimeout: 60000,
  queueLimit: 0,
});

export async function query<T>(sql: string, params?: any[]): Promise<T[]> {
  const [rows] = await pool.execute(sql, params);
  return rows as T[];
}

export async function getConnection() {
  return pool.getConnection();
}
```

### Node.js (Drizzle ORM)

```typescript
// db/schema.ts
import { mysqlTable, bigint, varchar, timestamp, uniqueIndex } from 'drizzle-orm/mysql-core';

export const users = mysqlTable('users', {
  id: bigint('id', { mode: 'number' }).primaryKey().autoincrement(),
  email: varchar('email', { length: 255 }).notNull(),
  name: varchar('name', { length: 255 }),
  createdAt: timestamp('created_at').defaultNow(),
}, (table) => ({
  emailIdx: uniqueIndex('email_idx').on(table.email),
}));

export const posts = mysqlTable('posts', {
  id: bigint('id', { mode: 'number' }).primaryKey().autoincrement(),
  title: varchar('title', { length: 255 }).notNull(),
  content: varchar('content', { length: 65535 }),
  authorId: bigint('author_id', { mode: 'number' }).notNull(),
  createdAt: timestamp('created_at').defaultNow(),
});

// db/index.ts
import { drizzle } from 'drizzle-orm/planetscale-serverless';
import { connect } from '@planetscale/database';
import * as schema from './schema';

const connection = connect({
  host: process.env.DATABASE_HOST,
  username: process.env.DATABASE_USERNAME,
  password: process.env.DATABASE_PASSWORD,
});

export const db = drizzle(connection, { schema });

// Usage
import { db } from '@/db';
import { users, posts } from '@/db/schema';
import { eq } from 'drizzle-orm';

const allUsers = await db.select().from(users);
const user = await db.select().from(users).where(eq(users.email, email));
const userWithPosts = await db.query.users.findFirst({
  where: eq(users.id, userId),
  with: {
    posts: true,
  },
});
```

### Node.js (Prisma)

```prisma
// schema.prisma
datasource db {
  provider     = "mysql"
  url          = env("DATABASE_URL")
  relationMode = "prisma"  // Required for PlanetScale (no FK support)
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id        BigInt   @id @default(autoincrement())
  email     String   @unique @db.VarChar(255)
  name      String?  @db.VarChar(255)
  posts     Post[]
  createdAt DateTime @default(now()) @map("created_at")

  @@index([email])
  @@map("users")
}

model Post {
  id        BigInt   @id @default(autoincrement())
  title     String   @db.VarChar(255)
  content   String?  @db.Text
  authorId  BigInt   @map("author_id")
  author    User     @relation(fields: [authorId], references: [id])
  createdAt DateTime @default(now()) @map("created_at")

  @@index([authorId])  // Required since no FK
  @@map("posts")
}
```

```typescript
// prisma.ts
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma = globalForPrisma.prisma || new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['query'] : [],
});

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

### Python

```python
# database.py
import os
import mysql.connector
from mysql.connector import pooling

# Connection pool for traditional servers
pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=5,
    host=os.environ["DATABASE_HOST"],
    user=os.environ["DATABASE_USERNAME"],
    password=os.environ["DATABASE_PASSWORD"],
    database=os.environ["DATABASE_NAME"],
    ssl_ca="/etc/ssl/certs/ca-certificates.crt",
    ssl_verify_cert=True,
)


def get_connection():
    return pool.get_connection()


def query(sql: str, params: tuple = None) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def execute(sql: str, params: tuple = None) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


# Usage
def get_user_by_email(email: str) -> dict | None:
    results = query("SELECT * FROM users WHERE email = %s", (email,))
    return results[0] if results else None


def create_user(email: str, name: str) -> int:
    return execute(
        "INSERT INTO users (email, name) VALUES (%s, %s)",
        (email, name)
    )
```

### Go

```go
// database.go
package database

import (
    "database/sql"
    "os"

    _ "github.com/go-sql-driver/mysql"
)

var db *sql.DB

func Init() error {
    dsn := os.Getenv("DATABASE_USERNAME") + ":" +
        os.Getenv("DATABASE_PASSWORD") + "@tcp(" +
        os.Getenv("DATABASE_HOST") + ")/" +
        os.Getenv("DATABASE_NAME") + "?tls=true&parseTime=true"

    var err error
    db, err = sql.Open("mysql", dsn)
    if err != nil {
        return err
    }

    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(5)

    return db.Ping()
}

func Close() {
    if db != nil {
        db.Close()
    }
}

type User struct {
    ID        int64
    Email     string
    Name      sql.NullString
    CreatedAt time.Time
}

func GetUserByEmail(email string) (*User, error) {
    var user User
    err := db.QueryRow(
        "SELECT id, email, name, created_at FROM users WHERE email = ?",
        email,
    ).Scan(&user.ID, &user.Email, &user.Name, &user.CreatedAt)

    if err == sql.ErrNoRows {
        return nil, nil
    }
    return &user, err
}

func CreateUser(email, name string) (int64, error) {
    result, err := db.Exec(
        "INSERT INTO users (email, name) VALUES (?, ?)",
        email, name,
    )
    if err != nil {
        return 0, err
    }
    return result.LastInsertId()
}
```

## Schema Migrations

### Prisma Migrations

```bash
# Create migration (local development)
npx prisma db push

# For production, use PlanetScale branches
# 1. Create branch
pscale branch create my-app add-posts-table

# 2. Push to branch
DATABASE_URL="mysql://...@add-posts-table.aws.connect.psdb.cloud/my-app" npx prisma db push

# 3. Create deploy request
pscale deploy-request create my-app add-posts-table

# 4. Deploy
pscale deploy-request deploy my-app 1
```

### Drizzle Migrations

```bash
# Generate migration
npx drizzle-kit generate:mysql

# Push to PlanetScale branch
npx drizzle-kit push:mysql
```

### Raw SQL Migrations

```sql
-- migrations/001_create_users.sql
CREATE TABLE users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- migrations/002_create_posts.sql
CREATE TABLE posts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    author_id BIGINT UNSIGNED NOT NULL,
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_posts_author (author_id),
    KEY idx_posts_published (published, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## GitHub Actions Integration

```yaml
# .github/workflows/db-migrations.yml
name: Database Migrations

on:
  pull_request:
    paths:
      - 'prisma/schema.prisma'
      - 'db/migrations/**'

jobs:
  create-branch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup pscale
        uses: planetscale/setup-pscale-action@v1
        with:
          version: latest

      - name: Create branch
        env:
          PLANETSCALE_SERVICE_TOKEN_ID: ${{ secrets.PLANETSCALE_SERVICE_TOKEN_ID }}
          PLANETSCALE_SERVICE_TOKEN: ${{ secrets.PLANETSCALE_SERVICE_TOKEN }}
        run: |
          pscale branch create my-app pr-${{ github.event.number }} --from main --wait

      - name: Get credentials
        id: creds
        env:
          PLANETSCALE_SERVICE_TOKEN_ID: ${{ secrets.PLANETSCALE_SERVICE_TOKEN_ID }}
          PLANETSCALE_SERVICE_TOKEN: ${{ secrets.PLANETSCALE_SERVICE_TOKEN }}
        run: |
          CREDS=$(pscale password create my-app pr-${{ github.event.number }} pr-password --format json)
          echo "host=$(echo $CREDS | jq -r '.host')" >> $GITHUB_OUTPUT
          echo "username=$(echo $CREDS | jq -r '.username')" >> $GITHUB_OUTPUT
          echo "password=$(echo $CREDS | jq -r '.plain_text')" >> $GITHUB_OUTPUT

      - name: Run migrations
        env:
          DATABASE_URL: "mysql://${{ steps.creds.outputs.username }}:${{ steps.creds.outputs.password }}@${{ steps.creds.outputs.host }}/my-app?sslaccept=strict"
        run: npx prisma db push

      - name: Create deploy request
        env:
          PLANETSCALE_SERVICE_TOKEN_ID: ${{ secrets.PLANETSCALE_SERVICE_TOKEN_ID }}
          PLANETSCALE_SERVICE_TOKEN: ${{ secrets.PLANETSCALE_SERVICE_TOKEN }}
        run: |
          pscale deploy-request create my-app pr-${{ github.event.number }} --format json

  cleanup:
    runs-on: ubuntu-latest
    if: github.event.action == 'closed'
    steps:
      - name: Setup pscale
        uses: planetscale/setup-pscale-action@v1

      - name: Delete branch
        env:
          PLANETSCALE_SERVICE_TOKEN_ID: ${{ secrets.PLANETSCALE_SERVICE_TOKEN_ID }}
          PLANETSCALE_SERVICE_TOKEN: ${{ secrets.PLANETSCALE_SERVICE_TOKEN }}
        run: pscale branch delete my-app pr-${{ github.event.number }} --force
```

## Cost Breakdown

### PlanetScale Pricing

| Plan | Rows Read/mo | Rows Written/mo | Storage | Monthly Cost |
|------|--------------|-----------------|---------|--------------|
| Hobby (Free) | 1 billion | 10 million | 5 GB | $0 |
| Scaler | 100 billion | 50 million | 10 GB | $29 |
| Scaler Pro | 500 billion | 125 million | 25 GB | $99 |
| Team | 2 trillion | 500 million | 50 GB | $599 |
| Enterprise | Custom | Custom | Custom | Contact |

### Additional Costs

| Resource | Cost |
|----------|------|
| Extra storage | $2.50/GB |
| Extra rows read | $1/billion |
| Extra rows written | $1.50/million |
| Extra branches | $0/branch (unlimited) |

### Cost Optimization Tips

```typescript
// Use SELECT with specific columns
// BAD - reads all columns
const users = await db.select().from(users);

// GOOD - reads only needed columns
const users = await db.select({ id: users.id, name: users.name }).from(users);

// Use LIMIT for large queries
const recentPosts = await db.select().from(posts).limit(100);

// Use indexes for frequently queried columns
// This reduces rows scanned
```

## Best Practices

### Handle No Foreign Keys

```typescript
// PlanetScale doesn't support FK constraints
// Use application-level referential integrity

// Prisma - use relationMode = "prisma"
// schema.prisma
datasource db {
  relationMode = "prisma"  // Handles relations in Prisma, not DB
}

// Manual integrity checks
async function deleteUser(userId: string) {
  // Delete related records first
  await db.delete(posts).where(eq(posts.authorId, userId));
  await db.delete(users).where(eq(users.id, userId));
}
```

### Efficient Queries

```typescript
// GOOD - Use indexes
const user = await db.select().from(users).where(eq(users.email, email));
// email has unique index

// GOOD - Use composite indexes for multi-column queries
// CREATE INDEX idx_posts_author_date ON posts(author_id, created_at DESC);
const posts = await db.select()
  .from(posts)
  .where(eq(posts.authorId, authorId))
  .orderBy(desc(posts.createdAt));

// BAD - Query without index
const posts = await db.select()
  .from(posts)
  .where(like(posts.content, '%search%'));  // Full table scan
```

### Connection Handling

```typescript
// Serverless - use @planetscale/database
import { connect } from '@planetscale/database';
const conn = connect(config);  // HTTP-based, no connection pooling needed

// Long-running servers - use mysql2 with pooling
import mysql from 'mysql2/promise';
const pool = mysql.createPool({
  connectionLimit: 10,
  // ...
});
```

## Common Mistakes

1. **Using foreign keys** - Not supported; use application-level integrity
2. **Not using indexes** - Missing indexes increase row reads (cost)
3. **SELECT *** - Reads unnecessary columns, increases row reads
4. **Not using branches for schema changes** - Missing safe migration workflow
5. **Large transactions** - Keep transactions small and fast
6. **Not handling relation mode** - Prisma needs `relationMode = "prisma"`
7. **Ignoring row read counts** - Monitor to avoid surprise bills
8. **Not using serverless driver for edge** - mysql2 doesn't work on edge
9. **Missing indexes on foreign key columns** - Slow joins without FK indexes
10. **Not testing schema changes in branches** - Deploy to production without testing

## Example Configuration

```yaml
# infera.yaml
project_name: my-app
provider: planetscale
environment: production

database:
  type: planetscale
  region: us-east

  organization: my-org
  database: my-app

  branches:
    main:
      production: true
      safe_migrations: true
    development:
      from: main

  settings:
    plan: scaler  # hobby, scaler, scaler_pro, team

application:
  runtime: vercel
  framework: nextjs

  env:
    DATABASE_HOST:
      from: planetscale
      branch: main
    DATABASE_USERNAME:
      from_secret: planetscale-username
    DATABASE_PASSWORD:
      from_secret: planetscale-password
```

## Sources

- [PlanetScale Documentation](https://planetscale.com/docs)
- [PlanetScale Serverless Driver](https://github.com/planetscale/database-js)
- [Drizzle + PlanetScale](https://orm.drizzle.team/docs/get-started-mysql#planetscale)
- [Prisma + PlanetScale](https://www.prisma.io/docs/guides/database/planetscale)
- [PlanetScale CLI Reference](https://planetscale.com/docs/reference/planetscale-cli)
- [Vitess Documentation](https://vitess.io/docs/)
