# MySQL Managed Database

## Overview
Managed MySQL is a reliable choice for applications with existing MySQL dependencies, legacy systems, or when using MySQL-specific features. Cloud providers handle backups, replication, and maintenance.

**Use when:**
- Migrating existing MySQL applications
- Using MySQL-specific features (FULLTEXT, spatial)
- Team expertise is MySQL-focused
- Need MySQL protocol compatibility

**Don't use when:**
- Starting fresh (PostgreSQL often better)
- Need advanced JSON support
- Need advanced concurrency (MVCC differences)

## Detection Signals

```
Files:
- prisma/schema.prisma with provider = "mysql"
- config/database.yml with adapter: mysql2
- .sequelizerc
- db/migrations/*.sql (MySQL syntax)

Dependencies:
- mysql2, mysql, pymysql, mysqlclient
- typeorm with mysql driver
- sequelize with mysql2
- activerecord-mysql2-adapter

Code Patterns:
- mysql://, mysql2://
- TINYINT(1) for booleans
- FULLTEXT indexes
- AUTO_INCREMENT
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MySQL Managed Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │                                                           │   │
│  │  Cloud Run / ECS / Lambda / App Engine                   │   │
│  │                                                           │   │
│  └─────────────────────────┬─────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │              Connection Proxy / Pool                       │   │
│  │  • Cloud SQL Proxy (GCP)                                  │   │
│  │  • RDS Proxy (AWS)                                        │   │
│  │  • ProxySQL                                               │   │
│  └─────────────────────────┬─────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │                     PRIMARY (Write)                        │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │                    MySQL 8.0+                        │  │   │
│  │  │  • InnoDB storage engine                            │  │   │
│  │  │  • Binary logging for replication                   │  │   │
│  │  │  • Automatic backups                                │  │   │
│  │  │  • Performance Schema                               │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────┬─────────────────────────────────┘   │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                  │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐           │
│  │  Replica 1 │     │  Replica 2 │     │  Standby   │           │
│  │  (Read)    │     │  (Read)    │     │  (HA)      │           │
│  └────────────┘     └────────────┘     └────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Comparison

| Feature | Cloud SQL (GCP) | RDS (AWS) | Azure MySQL | PlanetScale |
|---------|-----------------|-----------|-------------|-------------|
| **Min Cost** | ~$7/mo | ~$12/mo | ~$12/mo | $0 (free tier) |
| **HA Option** | Regional | Multi-AZ | Zone-redundant | Built-in |
| **Max Storage** | 64 TB | 128 TB | 16 TB | Unlimited |
| **Backups** | Automatic | Automatic | Automatic | Automatic |
| **Read Replicas** | Yes | Yes | Yes | Built-in |
| **Serverless** | No | No | Flexible | Yes |
| **Branching** | No | No | No | Yes |

## GCP Cloud SQL Configuration

### Terraform Configuration

```hcl
# cloud_sql_mysql.tf

resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "mysql" {
  name             = "${var.project_name}-mysql"
  database_version = "MYSQL_8_0"
  region           = var.region

  deletion_protection = var.environment == "production"

  settings {
    tier              = var.db_tier
    availability_type = var.ha_enabled ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb
    disk_autoresize   = true

    backup_configuration {
      enabled            = true
      binary_log_enabled = true  # Required for replication and PITR
      start_time         = "03:00"

      backup_retention_settings {
        retained_backups = 30
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    maintenance_window {
      day          = 7
      hour         = 3
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
      value = "250"
    }

    database_flags {
      name  = "slow_query_log"
      value = "on"
    }

    database_flags {
      name  = "long_query_time"
      value = "1"
    }

    database_flags {
      name  = "innodb_buffer_pool_size"
      value = "134217728"  # 128 MB, adjust based on tier
    }

    database_flags {
      name  = "character_set_server"
      value = "utf8mb4"
    }

    database_flags {
      name  = "collation_server"
      value = "utf8mb4_unicode_ci"
    }
  }

  depends_on = [google_project_service.sqladmin]
}

resource "google_sql_database" "main" {
  name      = var.database_name
  instance  = google_sql_database_instance.mysql.name
  charset   = "utf8mb4"
  collation = "utf8mb4_unicode_ci"
}

resource "google_sql_user" "main" {
  name     = var.database_user
  instance = google_sql_database_instance.mysql.name
  password = random_password.db_password.result
  host     = "%"
}

# Read replica
resource "google_sql_database_instance" "read_replica" {
  count                = var.read_replica_count
  name                 = "${var.project_name}-mysql-replica-${count.index}"
  master_instance_name = google_sql_database_instance.mysql.name
  region               = var.region
  database_version     = "MYSQL_8_0"

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

output "connection_name" {
  value = google_sql_database_instance.mysql.connection_name
}

output "private_ip" {
  value = google_sql_database_instance.mysql.private_ip_address
}
```

## AWS RDS MySQL Configuration

### Terraform Configuration

```hcl
# rds_mysql.tf

resource "aws_security_group" "mysql" {
  name        = "${var.project_name}-mysql-sg"
  description = "Security group for MySQL RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 3306
    to_port         = 3306
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

resource "aws_db_subnet_group" "mysql" {
  name       = "${var.project_name}-mysql-subnet"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_parameter_group" "mysql8" {
  name   = "${var.project_name}-mysql8"
  family = "mysql8.0"

  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }

  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }

  parameter {
    name  = "slow_query_log"
    value = "1"
  }

  parameter {
    name  = "long_query_time"
    value = "1"
  }

  parameter {
    name  = "log_bin_trust_function_creators"
    value = "1"
  }
}

resource "aws_db_option_group" "mysql8" {
  name                 = "${var.project_name}-mysql8"
  engine_name          = "mysql"
  major_engine_version = "8.0"
}

resource "random_password" "mysql_password" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "mysql_password" {
  name = "${var.project_name}/mysql-password"
}

resource "aws_secretsmanager_secret_version" "mysql_password" {
  secret_id     = aws_secretsmanager_secret.mysql_password.id
  secret_string = random_password.mysql_password.result
}

resource "aws_db_instance" "mysql" {
  identifier     = "${var.project_name}-mysql"
  engine         = "mysql"
  engine_version = "8.0.35"

  instance_class        = var.db_instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.database_user
  password = random_password.mysql_password.result

  db_subnet_group_name   = aws_db_subnet_group.mysql.name
  vpc_security_group_ids = [aws_security_group.mysql.id]
  parameter_group_name   = aws_db_parameter_group.mysql8.name
  option_group_name      = aws_db_option_group.mysql8.name

  multi_az            = var.multi_az
  publicly_accessible = false

  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "Sun:04:00-Sun:05:00"

  auto_minor_version_upgrade = true
  deletion_protection        = var.environment == "production"
  skip_final_snapshot        = var.environment != "production"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  enabled_cloudwatch_logs_exports = ["error", "slowquery", "general"]

  tags = {
    Environment = var.environment
  }
}

# Read Replica
resource "aws_db_instance" "mysql_replica" {
  count = var.read_replica_count

  identifier          = "${var.project_name}-mysql-replica-${count.index}"
  replicate_source_db = aws_db_instance.mysql.identifier

  instance_class = var.replica_instance_class
  storage_type   = "gp3"

  vpc_security_group_ids = [aws_security_group.mysql.id]
  parameter_group_name   = aws_db_parameter_group.mysql8.name

  multi_az            = false
  publicly_accessible = false

  auto_minor_version_upgrade = true
  skip_final_snapshot        = true
}

output "endpoint" {
  value = aws_db_instance.mysql.endpoint
}

output "database_url" {
  value     = "mysql://${var.database_user}:${random_password.mysql_password.result}@${aws_db_instance.mysql.endpoint}/${var.database_name}"
  sensitive = true
}
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
    DATABASE_URL = f"mysql+pymysql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@/{os.environ['DB_NAME']}?unix_socket={unix_socket}&charset=utf8mb4"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

### Node.js (mysql2)

```typescript
// db.ts
import mysql from 'mysql2/promise';

const pool = mysql.createPool({
  uri: process.env.DATABASE_URL,
  waitForConnections: true,
  connectionLimit: 10,
  maxIdle: 10,
  idleTimeout: 60000,
  queueLimit: 0,
  charset: 'utf8mb4',
});

export async function query<T>(sql: string, params?: any[]): Promise<T[]> {
  const [rows] = await pool.execute(sql, params);
  return rows as T[];
}

export async function getConnection() {
  return pool.getConnection();
}

// Usage
const users = await query<User>('SELECT * FROM users WHERE id = ?', [userId]);
```

### Node.js (Prisma)

```prisma
// schema.prisma
datasource db {
  provider = "mysql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique @db.VarChar(255)
  name      String?  @db.VarChar(255)
  posts     Post[]
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  @@map("users")
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String   @db.VarChar(255)
  content   String?  @db.Text
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int      @map("author_id")
  createdAt DateTime @default(now()) @map("created_at")

  @@index([authorId])
  @@map("posts")
}
```

### Ruby (Rails)

```yaml
# config/database.yml
default: &default
  adapter: mysql2
  encoding: utf8mb4
  collation: utf8mb4_unicode_ci
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>
  timeout: 5000

development:
  <<: *default
  database: myapp_development
  username: root
  password:
  host: localhost

production:
  <<: *default
  database: <%= ENV['DB_NAME'] %>
  username: <%= ENV['DB_USER'] %>
  password: <%= ENV['DB_PASSWORD'] %>
  host: <%= ENV['DB_HOST'] %>
  socket: <%= ENV['DB_SOCKET'] %>  # For Cloud SQL proxy
```

### Go

```go
// database.go
package database

import (
    "database/sql"
    "os"
    "time"

    _ "github.com/go-sql-driver/mysql"
)

var db *sql.DB

func Init() error {
    var err error
    dsn := os.Getenv("DATABASE_URL")

    db, err = sql.Open("mysql", dsn)
    if err != nil {
        return err
    }

    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(5)
    db.SetConnMaxLifetime(time.Hour)
    db.SetConnMaxIdleTime(30 * time.Minute)

    return db.Ping()
}

func Close() {
    if db != nil {
        db.Close()
    }
}

func DB() *sql.DB {
    return db
}
```

## Migration Tools

### Flyway

```sql
-- V1__Create_users_table.sql
CREATE TABLE users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Prisma Migrate

```bash
# Create migration
npx prisma migrate dev --name add_users

# Deploy to production
npx prisma migrate deploy

# Generate client
npx prisma generate
```

### Rails Migrations

```ruby
# db/migrate/20240101000000_create_users.rb
class CreateUsers < ActiveRecord::Migration[7.1]
  def change
    create_table :users do |t|
      t.string :email, null: false, limit: 255
      t.string :name, limit: 255
      t.timestamps
    end

    add_index :users, :email, unique: true
  end
end
```

## MySQL-Specific Features

### FULLTEXT Search

```sql
-- Create FULLTEXT index
CREATE FULLTEXT INDEX idx_posts_content ON posts(title, content);

-- Search
SELECT * FROM posts
WHERE MATCH(title, content) AGAINST('search terms' IN NATURAL LANGUAGE MODE);

-- Boolean mode
SELECT * FROM posts
WHERE MATCH(title, content) AGAINST('+required -excluded' IN BOOLEAN MODE);
```

### JSON Support

```sql
-- Create table with JSON column
CREATE TABLE products (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    attributes JSON,
    INDEX idx_color ((CAST(attributes->>'$.color' AS CHAR(50))))
);

-- Insert JSON
INSERT INTO products (name, attributes) VALUES
('Widget', '{"color": "red", "size": "large", "tags": ["sale", "featured"]}');

-- Query JSON
SELECT * FROM products
WHERE JSON_EXTRACT(attributes, '$.color') = 'red';

-- Or using shorthand
SELECT * FROM products
WHERE attributes->>'$.color' = 'red';
```

### Partitioning

```sql
-- Range partitioning by date
CREATE TABLE orders (
    id BIGINT UNSIGNED AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NOT NULL,
    order_date DATE NOT NULL,
    total DECIMAL(10,2),
    PRIMARY KEY (id, order_date)
) PARTITION BY RANGE (YEAR(order_date)) (
    PARTITION p2022 VALUES LESS THAN (2023),
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);
```

## Cost Breakdown

### GCP Cloud SQL MySQL

| Configuration | vCPUs | RAM | Storage | Monthly Cost |
|--------------|-------|-----|---------|--------------|
| Development | Shared | 614 MB | 10 GB | ~$7 |
| Small Prod | 2 | 7.5 GB | 50 GB | ~$85 |
| Medium Prod | 4 | 15 GB | 100 GB | ~$170 |
| Large Prod + HA | 8 | 30 GB | 250 GB | ~$500 |

### AWS RDS MySQL

| Configuration | Instance | Storage | Monthly Cost |
|--------------|----------|---------|--------------|
| Development | db.t3.micro | 20 GB | ~$15 |
| Small Prod | db.t3.small | 50 GB | ~$30 |
| Medium Prod | db.r6g.large | 100 GB | ~$130 |
| Large Prod + Multi-AZ | db.r6g.xlarge | 250 GB | ~$420 |

## Best Practices

### Character Set Configuration

```sql
-- Always use utf8mb4 for full Unicode support
CREATE DATABASE mydb
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Check current settings
SHOW VARIABLES LIKE 'character%';
SHOW VARIABLES LIKE 'collation%';
```

### Connection Handling

```python
# GOOD - Connection pooling
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Important for MySQL wait_timeout
    pool_pre_ping=True,
)

# BAD - New connection per request
import pymysql
def query():
    conn = pymysql.connect(...)  # Don't do this
```

### Query Optimization

```sql
-- Use EXPLAIN to analyze queries
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';

-- Add indexes for common queries
CREATE INDEX idx_users_email ON users(email);

-- Use covering indexes
CREATE INDEX idx_orders_user_status ON orders(user_id, status, created_at);
```

## Common Mistakes

1. **Using utf8 instead of utf8mb4** - utf8 only supports 3-byte characters, breaks emoji
2. **Not setting pool_recycle** - Connections timeout due to wait_timeout
3. **Missing indexes on foreign keys** - MySQL doesn't auto-index FK columns
4. **Using MyISAM engine** - Use InnoDB for transactions and foreign keys
5. **Not enabling binary logging** - Required for replication and PITR
6. **Hardcoded credentials** - Use environment variables or secrets manager
7. **Not handling emoji** - Requires utf8mb4 charset
8. **Over-indexing** - Slows down writes
9. **Not using EXPLAIN** - Running slow queries in production
10. **Ignoring slow query log** - Missing optimization opportunities

## Example Configuration

```yaml
# infera.yaml
project_name: my-api
provider: gcp
region: us-central1
environment: production

database:
  type: mysql_managed
  provider: cloud_sql
  version: "8.0"

  instance:
    tier: db-custom-4-15360
    ha_enabled: true
    disk_size_gb: 100
    disk_autoresize: true

  character_set: utf8mb4
  collation: utf8mb4_unicode_ci

  backups:
    enabled: true
    binary_log_enabled: true
    retention_count: 30

  read_replicas: 1

  networking:
    private_ip: true
    vpc_connector: true

  flags:
    slow_query_log: "on"
    long_query_time: "1"

application:
  service: cloud_run
  vpc_connector: default

  env:
    DATABASE_URL:
      from_secret: mysql-connection-string
```

## Sources

- [Cloud SQL for MySQL Documentation](https://cloud.google.com/sql/docs/mysql)
- [Amazon RDS for MySQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html)
- [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/)
- [Prisma MySQL Guide](https://www.prisma.io/docs/concepts/database-connectors/mysql)
- [MySQL Performance Tuning](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
