# PostgreSQL Managed Database

## Overview
Managed PostgreSQL is the default choice for most applications requiring a relational database. Cloud providers handle backups, patching, replication, and failover while you focus on your application.

**Use when:**
- You need ACID compliance and complex queries
- Your data model is relational
- You need mature tooling and ecosystem
- You want managed backups and HA

**Don't use when:**
- You need sub-millisecond latency (use Redis)
- Your data is highly unstructured (consider MongoDB)
- You need global distribution (consider CockroachDB/Spanner)

## Detection Signals

```
Files:
- prisma/schema.prisma with provider = "postgresql"
- alembic.ini, alembic/
- db/migrate/*.rb (Rails)
- src/main/resources/db/migration/*.sql (Flyway)
- knexfile.js with client: 'pg'

Dependencies:
- psycopg2, asyncpg, sqlalchemy (Python)
- pg, prisma, typeorm, knex (Node.js)
- activerecord-postgresql-adapter (Ruby)
- pgjdbc, r2dbc-postgresql (Java)

Code Patterns:
- postgres://, postgresql://
- @Column, @Entity annotations
- CREATE TABLE, SELECT, JOIN
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │  Cloud Run   │     │  ECS/Fargate │     │   Lambda    │ │
│  │  (GCP)       │     │  (AWS)       │     │   (AWS)     │ │
│  └──────┬───────┘     └──────┬───────┘     └──────┬──────┘ │
│         │                    │                    │         │
│         └────────────────────┼────────────────────┘         │
│                              │                              │
│                    ┌─────────▼─────────┐                    │
│                    │  Connection Pool  │                    │
│                    │  (PgBouncer/RDS   │                    │
│                    │   Proxy)          │                    │
│                    └─────────┬─────────┘                    │
│                              │                              │
├──────────────────────────────┼──────────────────────────────┤
│                              │                              │
│  ┌───────────────────────────▼───────────────────────────┐ │
│  │                   PRIMARY INSTANCE                     │ │
│  │  ┌─────────────────────────────────────────────────┐  │ │
│  │  │              PostgreSQL 15+                      │  │ │
│  │  │  • Automatic backups                            │  │ │
│  │  │  • Point-in-time recovery                       │  │ │
│  │  │  • Automatic patching                           │  │ │
│  │  │  • Monitoring & alerting                        │  │ │
│  │  └─────────────────────────────────────────────────┘  │ │
│  └───────────────────────────┬───────────────────────────┘ │
│                              │                              │
│              ┌───────────────┼───────────────┐              │
│              │               │               │              │
│              ▼               ▼               ▼              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │  Read Replica │  │  Read Replica │  │    Standby    │   │
│  │  (Optional)   │  │  (Optional)   │  │  (HA config)  │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Cloud SQL (GCP) | RDS (AWS) | Supabase | Neon |
|---------|-----------------|-----------|----------|------|
| **Min Cost** | $7/mo | $12/mo | Free tier | Free tier |
| **HA Option** | Regional | Multi-AZ | Enterprise | N/A |
| **Max Storage** | 64 TB | 128 TB | 8 GB free | 10 GB free |
| **Backups** | Automatic | Automatic | Automatic | Automatic |
| **Read Replicas** | Yes | Yes | Enterprise | Branching |
| **Private Connect** | VPC | VPC | N/A | N/A |
| **Connection Pooling** | Manual | RDS Proxy | Built-in | Built-in |
| **Serverless Option** | AlloyDB | Aurora | N/A | Yes |

## GCP Cloud SQL Configuration

### Terraform Configuration

```hcl
# cloud_sql.tf

# Enable required APIs
resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

# Generate random password
resource "random_password" "db_password" {
  length  = 32
  special = false
}

# Cloud SQL Instance
resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  deletion_protection = var.environment == "production"

  settings {
    tier              = var.db_tier
    availability_type = var.ha_enabled ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 30
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id

      # For Cloud Run without VPC connector
      dynamic "authorized_networks" {
        for_each = var.allow_public ? [1] : []
        content {
          name  = "public"
          value = "0.0.0.0/0"
        }
      }
    }

    maintenance_window {
      day          = 7  # Sunday
      hour         = 3  # 3 AM
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }

    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }

    database_flags {
      name  = "log_connections"
      value = "on"
    }

    database_flags {
      name  = "log_disconnections"
      value = "on"
    }

    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
  }

  depends_on = [google_project_service.sqladmin]
}

# Database
resource "google_sql_database" "main" {
  name     = var.database_name
  instance = google_sql_database_instance.main.name
}

# User
resource "google_sql_user" "main" {
  name     = var.database_user
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# Store password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.project_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Read replica (optional)
resource "google_sql_database_instance" "read_replica" {
  count                = var.read_replica_count
  name                 = "${var.project_name}-db-replica-${count.index}"
  master_instance_name = google_sql_database_instance.main.name
  region               = var.region
  database_version     = "POSTGRES_15"

  replica_configuration {
    failover_target = false
  }

  settings {
    tier            = var.replica_tier
    disk_type       = "PD_SSD"
    disk_autoresize = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }
}

# Variables
variable "db_tier" {
  description = "Database machine tier"
  type        = string
  default     = "db-f1-micro"  # For dev, use db-custom-2-7680 for prod
}

variable "disk_size_gb" {
  description = "Initial disk size in GB"
  type        = number
  default     = 10
}

variable "ha_enabled" {
  description = "Enable high availability"
  type        = bool
  default     = false
}

variable "read_replica_count" {
  description = "Number of read replicas"
  type        = number
  default     = 0
}

# Outputs
output "connection_name" {
  value = google_sql_database_instance.main.connection_name
}

output "private_ip" {
  value = google_sql_database_instance.main.private_ip_address
}

output "database_url" {
  value     = "postgresql://${var.database_user}:${random_password.db_password.result}@${google_sql_database_instance.main.private_ip_address}:5432/${var.database_name}"
  sensitive = true
}
```

### VPC and Private Connectivity

```hcl
# vpc.tf

resource "google_compute_network" "vpc" {
  name                    = "${var.project_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "${var.project_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# Private Service Connection for Cloud SQL
resource "google_compute_global_address" "private_ip_range" {
  name          = "private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# VPC Connector for Cloud Run
resource "google_vpc_access_connector" "connector" {
  name          = "${var.project_name}-connector"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc.name

  min_instances = 2
  max_instances = 3
}
```

## AWS RDS Configuration

### Terraform Configuration

```hcl
# rds.tf

# Security Group
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
}

# Parameter Group
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg15"
  family = "postgres15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }
}

# Generate random password
resource "random_password" "db_password" {
  length  = 32
  special = false
}

# Store in Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.project_name}/db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "15.4"

  instance_class        = var.db_instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.database_user
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az               = var.multi_az
  publicly_accessible    = false

  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "Sun:04:00-Sun:05:00"

  auto_minor_version_upgrade = true
  deletion_protection        = var.environment == "production"
  skip_final_snapshot        = var.environment != "production"
  final_snapshot_identifier  = var.environment == "production" ? "${var.project_name}-final-snapshot" : null

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Environment = var.environment
  }
}

# Read Replica (optional)
resource "aws_db_instance" "read_replica" {
  count = var.read_replica_count

  identifier          = "${var.project_name}-db-replica-${count.index}"
  replicate_source_db = aws_db_instance.main.identifier

  instance_class = var.replica_instance_class
  storage_type   = "gp3"

  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az            = false
  publicly_accessible = false

  auto_minor_version_upgrade = true
  skip_final_snapshot        = true
}

# RDS Proxy (optional, for Lambda/serverless)
resource "aws_db_proxy" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  name                   = "${var.project_name}-proxy"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  vpc_security_group_ids = [aws_security_group.rds.id]
  vpc_subnet_ids         = aws_subnet.private[*].id

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db_credentials.arn
  }
}

resource "aws_db_proxy_default_target_group" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name = aws_db_proxy.main[0].name

  connection_pool_config {
    max_connections_percent      = 100
    max_idle_connections_percent = 50
  }
}

resource "aws_db_proxy_target" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name          = aws_db_proxy.main[0].name
  target_group_name      = aws_db_proxy_default_target_group.main[0].name
  db_instance_identifier = aws_db_instance.main.identifier
}

# Variables
variable "db_instance_class" {
  default = "db.t3.micro"  # For dev, use db.r6g.large for prod
}

variable "allocated_storage" {
  default = 20
}

variable "max_allocated_storage" {
  default = 100
}

variable "multi_az" {
  default = false
}

variable "read_replica_count" {
  default = 0
}

variable "enable_rds_proxy" {
  default = false
}

# Outputs
output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "database_url" {
  value     = "postgresql://${var.database_user}:${random_password.db_password.result}@${aws_db_instance.main.endpoint}/${var.database_name}"
  sensitive = true
}

output "proxy_endpoint" {
  value = var.enable_rds_proxy ? aws_db_proxy.main[0].endpoint : null
}
```

## Supabase Configuration

### Project Setup

```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Link to existing project
supabase link --project-ref <project-id>

# Or create new project via dashboard
# https://supabase.com/dashboard
```

### Connection String

```typescript
// supabase.ts
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)

// Direct PostgreSQL connection (for migrations, etc.)
// postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Migrations with Supabase CLI

```bash
# Create migration
supabase migration new create_users_table

# migrations/20240101000000_create_users_table.sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

# Apply migrations
supabase db push

# Generate types
supabase gen types typescript --local > types/supabase.ts
```

## Application Integration

### Python (SQLAlchemy)

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.environ["DATABASE_URL"]

# For Cloud SQL with Unix socket
if os.environ.get("INSTANCE_CONNECTION_NAME"):
    unix_socket = f"/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
    DATABASE_URL = f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@/{os.environ['DB_NAME']}?host={unix_socket}"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,  # Enable connection health checks
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Python (asyncpg for async)

```python
# database_async.py
import asyncpg
import os
from contextlib import asynccontextmanager

DATABASE_URL = os.environ["DATABASE_URL"]

pool = None

async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20,
        max_inactive_connection_lifetime=300,
    )

async def close_pool():
    global pool
    if pool:
        await pool.close()

@asynccontextmanager
async def get_connection():
    async with pool.acquire() as conn:
        yield conn
```

### Node.js (Prisma)

```prisma
// schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String?
  posts     Post[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model Post {
  id        String   @id @default(uuid())
  title     String
  content   String?
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id])
  authorId  String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```

```typescript
// prisma.ts
import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient }

export const prisma = globalForPrisma.prisma || new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['query', 'error', 'warn'] : ['error'],
})

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
```

### Go

```go
// database.go
package database

import (
    "context"
    "os"
    "time"

    "github.com/jackc/pgx/v5/pgxpool"
)

var pool *pgxpool.Pool

func Init() error {
    config, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
    if err != nil {
        return err
    }

    config.MaxConns = 25
    config.MinConns = 5
    config.MaxConnLifetime = time.Hour
    config.MaxConnIdleTime = 30 * time.Minute
    config.HealthCheckPeriod = time.Minute

    pool, err = pgxpool.NewWithConfig(context.Background(), config)
    return err
}

func Close() {
    if pool != nil {
        pool.Close()
    }
}

func Pool() *pgxpool.Pool {
    return pool
}
```

## Migration Strategies

### Alembic (Python)

```bash
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add users table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Flyway (Java/Spring)

```properties
# application.properties
spring.flyway.enabled=true
spring.flyway.locations=classpath:db/migration
spring.flyway.baseline-on-migrate=true
```

```sql
-- V1__Create_users_table.sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

### Prisma Migrate

```bash
# Create migration
npx prisma migrate dev --name add_users

# Deploy to production
npx prisma migrate deploy

# Reset database (dev only)
npx prisma migrate reset
```

## Cost Breakdown

### GCP Cloud SQL

| Configuration | vCPUs | RAM | Storage | Monthly Cost |
|--------------|-------|-----|---------|--------------|
| Development | Shared | 614 MB | 10 GB | ~$7 |
| Small Prod | 2 | 7.5 GB | 50 GB | ~$85 |
| Medium Prod | 4 | 15 GB | 100 GB | ~$170 |
| Large Prod + HA | 8 | 30 GB | 250 GB | ~$500 |
| Enterprise + Replicas | 16 | 60 GB | 500 GB | ~$1,200 |

### AWS RDS

| Configuration | Instance | Storage | Monthly Cost |
|--------------|----------|---------|--------------|
| Development | db.t3.micro | 20 GB | ~$15 |
| Small Prod | db.t3.small | 50 GB | ~$30 |
| Medium Prod | db.r6g.large | 100 GB | ~$140 |
| Large Prod + Multi-AZ | db.r6g.xlarge | 250 GB | ~$450 |
| Enterprise | db.r6g.2xlarge + Replicas | 500 GB | ~$1,000 |

### Supabase

| Plan | Storage | Connections | Monthly Cost |
|------|---------|-------------|--------------|
| Free | 500 MB | 50 | $0 |
| Pro | 8 GB | 100 | $25 |
| Team | 100 GB | 200 | $599 |
| Enterprise | Custom | Custom | Contact |

## Best Practices

### Connection Management

```python
# BAD - Opening new connections for each request
def get_data():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

# GOOD - Using connection pool
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
)

def get_data():
    with engine.connect() as conn:
        return conn.execute("SELECT * FROM users").fetchall()
```

### Indexing Strategy

```sql
-- Primary lookup columns
CREATE INDEX idx_users_email ON users(email);

-- Composite indexes for common queries
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);

-- Partial indexes for filtered queries
CREATE INDEX idx_orders_pending ON orders(created_at)
WHERE status = 'pending';

-- JSONB indexes
CREATE INDEX idx_users_metadata ON users USING gin(metadata);
```

### Query Optimization

```sql
-- Use EXPLAIN ANALYZE
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';

-- Add appropriate indexes based on query plans
-- Look for Seq Scan on large tables

-- Use prepared statements
PREPARE get_user(text) AS
SELECT * FROM users WHERE email = $1;

EXECUTE get_user('test@example.com');
```

## Common Mistakes

1. **No connection pooling** - Creates new connections per request, exhausting limits
2. **Missing indexes** - Slow queries on commonly filtered columns
3. **N+1 queries** - Fetching related data in loops instead of JOINs
4. **No backups tested** - Never verifying backup restoration works
5. **Public IP without SSL** - Database exposed without encryption
6. **Hardcoded credentials** - Passwords in code instead of environment/secrets
7. **No connection timeouts** - Connections hanging indefinitely
8. **Missing health checks** - Not validating connections before use
9. **Over-provisioned instances** - Paying for unused capacity
10. **No read replicas for read-heavy workloads** - Primary overloaded

## Example Configuration

```yaml
# infera.yaml
project_name: my-api
provider: gcp
region: us-central1
environment: production

database:
  type: postgres_managed
  provider: cloud_sql
  version: "15"

  instance:
    tier: db-custom-4-15360  # 4 vCPU, 15 GB RAM
    ha_enabled: true
    disk_size_gb: 100
    disk_autoresize: true

  backups:
    enabled: true
    point_in_time_recovery: true
    retention_days: 30

  read_replicas: 2

  networking:
    private_ip: true
    vpc_connector: true

  credentials:
    secret_manager: true

application:
  service: cloud_run
  vpc_connector: default

  env:
    DATABASE_URL:
      from_secret: db-connection-string
```

## Sources

- [Cloud SQL for PostgreSQL Documentation](https://cloud.google.com/sql/docs/postgres)
- [Amazon RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [Supabase Documentation](https://supabase.com/docs)
- [PostgreSQL Performance Tips](https://www.postgresql.org/docs/current/performance-tips.html)
- [PgBouncer Documentation](https://www.pgbouncer.org/)
- [Prisma Best Practices](https://www.prisma.io/docs/guides/performance-and-optimization)
