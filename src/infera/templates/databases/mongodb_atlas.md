# MongoDB Atlas

## Overview
MongoDB Atlas is a fully managed document database service that provides flexible schema, horizontal scaling, and powerful querying capabilities. Ideal for applications with evolving data models and complex nested data structures.

**Use when:**
- Data model is document-oriented or semi-structured
- Schema evolves frequently
- Need embedded documents and arrays
- Hierarchical or nested data relationships
- Full-text search is important

**Don't use when:**
- Strong consistency and ACID transactions are critical
- Complex JOINs are common
- Data is highly relational
- Need SQL compatibility

## Detection Signals

```
Files:
- mongodb.config.js, mongodb.yaml
- .mongorc.js
- mongod.conf

Dependencies:
- mongodb, mongoose (Node.js)
- pymongo, motor (Python)
- mongo-go-driver (Go)
- mongodb gem (Ruby)

Code Patterns:
- mongodb://, mongodb+srv://
- MongoClient, mongoose.connect
- db.collection.find()
- ObjectId, BSON
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MongoDB Atlas Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │                                                           │   │
│  │  Cloud Run / Lambda / ECS / Vercel / Cloudflare          │   │
│  │                                                           │   │
│  └─────────────────────────┬─────────────────────────────────┘   │
│                            │                                     │
│                            │ mongodb+srv://                      │
│                            │                                     │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │                   Atlas Cluster                            │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │                 Replica Set                          │  │   │
│  │  │  ┌─────────┐   ┌─────────┐   ┌─────────┐           │  │   │
│  │  │  │ Primary │   │Secondary│   │Secondary│           │  │   │
│  │  │  │  (R/W)  │   │  (Read) │   │  (Read) │           │  │   │
│  │  │  └────┬────┘   └────┬────┘   └────┬────┘           │  │   │
│  │  │       │             │             │                 │  │   │
│  │  │       └─────────────┼─────────────┘                 │  │   │
│  │  │                     │                               │  │   │
│  │  │            ┌────────▼────────┐                      │  │   │
│  │  │            │   Oplog Sync    │                      │  │   │
│  │  │            └─────────────────┘                      │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  │                                                            │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │              Atlas Features                          │  │   │
│  │  │  • Atlas Search (Full-text)                         │  │   │
│  │  │  • Atlas Data Lake                                  │  │   │
│  │  │  • Charts (Visualization)                           │  │   │
│  │  │  • Triggers (Change Streams)                        │  │   │
│  │  │  • App Services (Functions/Sync)                    │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Atlas Cluster Configuration

### MongoDB Atlas UI/CLI Setup

```bash
# Install Atlas CLI
brew install mongodb-atlas

# Login
atlas auth login

# Create cluster
atlas clusters create my-cluster \
  --provider AWS \
  --region US_EAST_1 \
  --tier M10 \
  --members 3

# Get connection string
atlas clusters connectionStrings describe my-cluster

# Create database user
atlas dbusers create atlasAdmin \
  --username myuser \
  --password mypassword \
  --role readWriteAnyDatabase

# Whitelist IP (or use 0.0.0.0/0 for serverless)
atlas accessLists create --currentIp
```

### Terraform Configuration

```hcl
# atlas.tf

terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.14"
    }
  }
}

provider "mongodbatlas" {
  public_key  = var.mongodb_atlas_public_key
  private_key = var.mongodb_atlas_private_key
}

# Project
resource "mongodbatlas_project" "main" {
  name   = var.project_name
  org_id = var.mongodb_atlas_org_id
}

# Cluster
resource "mongodbatlas_cluster" "main" {
  project_id = mongodbatlas_project.main.id
  name       = "${var.project_name}-cluster"

  # Provider settings
  provider_name               = "AWS"
  provider_region_name        = "US_EAST_1"
  provider_instance_size_name = var.cluster_tier

  # Cluster configuration
  cluster_type = "REPLICASET"
  num_shards   = 1

  # Replication
  replication_specs {
    num_shards = 1
    regions_config {
      region_name     = "US_EAST_1"
      electable_nodes = 3
      priority        = 7
      read_only_nodes = 0
    }
  }

  # Advanced configuration
  advanced_configuration {
    javascript_enabled           = true
    minimum_enabled_tls_protocol = "TLS1_2"
  }

  # Backup
  cloud_backup = true

  # Auto-scaling (M10+)
  auto_scaling_disk_gb_enabled = var.cluster_tier != "M0"

  lifecycle {
    prevent_destroy = var.environment == "production"
  }
}

# Database User
resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "mongodbatlas_database_user" "main" {
  project_id         = mongodbatlas_project.main.id
  username           = var.database_user
  password           = random_password.db_password.result
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = var.database_name
  }

  scopes {
    name = mongodbatlas_cluster.main.name
    type = "CLUSTER"
  }
}

# IP Access List (for serverless, use 0.0.0.0/0 with auth)
resource "mongodbatlas_project_ip_access_list" "all" {
  project_id = mongodbatlas_project.main.id
  cidr_block = "0.0.0.0/0"
  comment    = "Allow all (authenticated access only)"
}

# For VPC Peering (production)
resource "mongodbatlas_network_peering" "aws" {
  count = var.enable_vpc_peering ? 1 : 0

  project_id             = mongodbatlas_project.main.id
  container_id           = mongodbatlas_cluster.main.container_id
  accepter_region_name   = "us-east-1"
  provider_name          = "AWS"
  route_table_cidr_block = var.vpc_cidr
  vpc_id                 = var.vpc_id
  aws_account_id         = var.aws_account_id
}

# Atlas Search Index
resource "mongodbatlas_search_index" "main" {
  project_id   = mongodbatlas_project.main.id
  cluster_name = mongodbatlas_cluster.main.name
  database     = var.database_name
  collection   = "products"
  name         = "products_search"
  type         = "search"

  search_analyzer = "lucene.standard"

  mappings_dynamic = true

  # Or define specific mappings
  # mappings_fields = jsonencode({
  #   name = {
  #     type = "string"
  #     analyzer = "lucene.standard"
  #   }
  #   description = {
  #     type = "string"
  #     analyzer = "lucene.standard"
  #   }
  # })
}

# Outputs
output "connection_string" {
  value     = mongodbatlas_cluster.main.connection_strings[0].standard_srv
  sensitive = true
}

output "database_url" {
  value     = "mongodb+srv://${var.database_user}:${random_password.db_password.result}@${replace(mongodbatlas_cluster.main.connection_strings[0].standard_srv, "mongodb+srv://", "")}/${var.database_name}?retryWrites=true&w=majority"
  sensitive = true
}

# Variables
variable "cluster_tier" {
  description = "Atlas cluster tier"
  type        = string
  default     = "M10"  # M0 for free tier
}

variable "enable_vpc_peering" {
  description = "Enable VPC peering"
  type        = bool
  default     = false
}
```

## Application Integration

### Node.js (Native Driver)

```typescript
// db.ts
import { MongoClient, Db, Collection, ObjectId } from 'mongodb';

const uri = process.env.MONGODB_URI!;

let client: MongoClient;
let db: Db;

export async function connectDB(): Promise<Db> {
  if (db) return db;

  client = new MongoClient(uri, {
    maxPoolSize: 10,
    minPoolSize: 2,
    maxIdleTimeMS: 30000,
    connectTimeoutMS: 10000,
    serverSelectionTimeoutMS: 10000,
  });

  await client.connect();
  db = client.db(process.env.DB_NAME);

  // Verify connection
  await db.command({ ping: 1 });
  console.log('Connected to MongoDB');

  return db;
}

export async function closeDB(): Promise<void> {
  if (client) {
    await client.close();
  }
}

// For serverless (connection caching)
let cachedClient: MongoClient | null = null;

export async function getClient(): Promise<MongoClient> {
  if (cachedClient) {
    return cachedClient;
  }

  cachedClient = await MongoClient.connect(uri);
  return cachedClient;
}

// Usage
export interface User {
  _id?: ObjectId;
  email: string;
  name: string;
  createdAt: Date;
}

export async function createUser(user: Omit<User, '_id'>): Promise<User> {
  const db = await connectDB();
  const result = await db.collection<User>('users').insertOne({
    ...user,
    createdAt: new Date(),
  });
  return { _id: result.insertedId, ...user, createdAt: new Date() };
}

export async function findUserByEmail(email: string): Promise<User | null> {
  const db = await connectDB();
  return db.collection<User>('users').findOne({ email });
}
```

### Node.js (Mongoose)

```typescript
// models/User.ts
import mongoose, { Schema, Document } from 'mongoose';

export interface IUser extends Document {
  email: string;
  name: string;
  profile: {
    bio?: string;
    avatar?: string;
    social?: {
      twitter?: string;
      github?: string;
    };
  };
  posts: mongoose.Types.ObjectId[];
  createdAt: Date;
  updatedAt: Date;
}

const userSchema = new Schema<IUser>(
  {
    email: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
    },
    name: {
      type: String,
      required: true,
      trim: true,
    },
    profile: {
      bio: String,
      avatar: String,
      social: {
        twitter: String,
        github: String,
      },
    },
    posts: [{ type: Schema.Types.ObjectId, ref: 'Post' }],
  },
  {
    timestamps: true,
  }
);

// Indexes
userSchema.index({ email: 1 });
userSchema.index({ 'profile.social.twitter': 1 }, { sparse: true });

// Virtual
userSchema.virtual('postCount').get(function () {
  return this.posts.length;
});

export const User = mongoose.model<IUser>('User', userSchema);
```

```typescript
// db/connection.ts
import mongoose from 'mongoose';

const MONGODB_URI = process.env.MONGODB_URI!;

// For serverless environments
let cached = (global as any).mongoose;

if (!cached) {
  cached = (global as any).mongoose = { conn: null, promise: null };
}

export async function connectDB() {
  if (cached.conn) {
    return cached.conn;
  }

  if (!cached.promise) {
    const opts = {
      bufferCommands: false,
      maxPoolSize: 10,
    };

    cached.promise = mongoose.connect(MONGODB_URI, opts);
  }

  cached.conn = await cached.promise;
  return cached.conn;
}
```

### Python (PyMongo)

```python
# database.py
from pymongo import MongoClient
from pymongo.database import Database
from contextlib import contextmanager
import os

MONGODB_URI = os.environ["MONGODB_URI"]
DB_NAME = os.environ.get("DB_NAME", "mydb")

# Connection pooling
client: MongoClient = None


def get_client() -> MongoClient:
    global client
    if client is None:
        client = MongoClient(
            MONGODB_URI,
            maxPoolSize=10,
            minPoolSize=2,
            maxIdleTimeMS=30000,
            connectTimeoutMS=10000,
            serverSelectionTimeoutMS=10000,
        )
    return client


def get_db() -> Database:
    return get_client()[DB_NAME]


def close_client():
    global client
    if client:
        client.close()
        client = None


# Usage
def create_user(email: str, name: str) -> dict:
    db = get_db()
    result = db.users.insert_one({
        "email": email,
        "name": name,
        "createdAt": datetime.utcnow(),
    })
    return {"_id": str(result.inserted_id), "email": email, "name": name}


def find_user_by_email(email: str) -> dict | None:
    db = get_db()
    return db.users.find_one({"email": email})
```

### Python (Motor - Async)

```python
# database_async.py
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URI = os.environ["MONGODB_URI"]
DB_NAME = os.environ.get("DB_NAME", "mydb")

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGODB_URI)
    # Verify connection
    await client.admin.command('ping')


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return client[DB_NAME]


# Usage with FastAPI
from fastapi import FastAPI

app = FastAPI()


@app.on_event("startup")
async def startup():
    await connect_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


@app.get("/users/{email}")
async def get_user(email: str):
    db = get_db()
    user = await db.users.find_one({"email": email})
    return user
```

### Go

```go
// database.go
package database

import (
    "context"
    "os"
    "time"

    "go.mongodb.org/mongo-driver/mongo"
    "go.mongodb.org/mongo-driver/mongo/options"
)

var client *mongo.Client
var database *mongo.Database

func Connect() error {
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    uri := os.Getenv("MONGODB_URI")
    opts := options.Client().
        ApplyURI(uri).
        SetMaxPoolSize(10).
        SetMinPoolSize(2).
        SetMaxConnIdleTime(30 * time.Second)

    var err error
    client, err = mongo.Connect(ctx, opts)
    if err != nil {
        return err
    }

    // Verify connection
    if err = client.Ping(ctx, nil); err != nil {
        return err
    }

    database = client.Database(os.Getenv("DB_NAME"))
    return nil
}

func Close() error {
    if client != nil {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()
        return client.Disconnect(ctx)
    }
    return nil
}

func DB() *mongo.Database {
    return database
}

func Collection(name string) *mongo.Collection {
    return database.Collection(name)
}
```

## Atlas Search

```typescript
// Atlas Search example
const pipeline = [
  {
    $search: {
      index: 'products_search',
      compound: {
        must: [
          {
            text: {
              query: searchTerm,
              path: ['name', 'description'],
              fuzzy: { maxEdits: 1 },
            },
          },
        ],
        filter: [
          {
            range: {
              path: 'price',
              gte: minPrice,
              lte: maxPrice,
            },
          },
        ],
      },
      highlight: {
        path: ['name', 'description'],
      },
    },
  },
  {
    $project: {
      name: 1,
      description: 1,
      price: 1,
      score: { $meta: 'searchScore' },
      highlights: { $meta: 'searchHighlights' },
    },
  },
  { $limit: 20 },
];

const results = await db.collection('products').aggregate(pipeline).toArray();
```

## Change Streams (Real-time)

```typescript
// Real-time updates with Change Streams
async function watchCollection() {
  const db = await connectDB();
  const changeStream = db.collection('orders').watch([
    { $match: { operationType: { $in: ['insert', 'update'] } } },
  ]);

  changeStream.on('change', (change) => {
    console.log('Change detected:', change);
    // Handle real-time updates
    if (change.operationType === 'insert') {
      notifyNewOrder(change.fullDocument);
    }
  });

  // For serverless, use resumeToken for reliability
  let resumeToken;
  changeStream.on('change', (change) => {
    resumeToken = change._id;
    // Store resumeToken for recovery
  });
}
```

## Cost Breakdown

### MongoDB Atlas Tiers

| Tier | RAM | Storage | vCPU | Monthly Cost |
|------|-----|---------|------|--------------|
| M0 (Free) | Shared | 512 MB | Shared | $0 |
| M2 | Shared | 2 GB | Shared | $9 |
| M5 | Shared | 5 GB | Shared | $25 |
| M10 | 2 GB | 10 GB | 2 | ~$57 |
| M20 | 4 GB | 20 GB | 2 | ~$140 |
| M30 | 8 GB | 40 GB | 2 | ~$280 |
| M40 | 16 GB | 80 GB | 4 | ~$450 |
| M50 | 32 GB | 160 GB | 8 | ~$850 |

### Additional Costs

| Feature | Cost |
|---------|------|
| Data Transfer (out) | $0.08-0.12/GB |
| Backup Storage | $0.023/GB/month |
| Atlas Search | $0.10/hour per replica |
| Data Lake Queries | $5.00/TB scanned |
| BI Connector | Included in M10+ |

## Best Practices

### Schema Design

```typescript
// GOOD - Embedded documents for 1:few relationships
const userSchema = {
  name: "John",
  addresses: [
    { type: "home", street: "123 Main St" },
    { type: "work", street: "456 Office Ave" },
  ],
};

// GOOD - References for 1:many or many:many
const orderSchema = {
  userId: ObjectId("..."),  // Reference to users
  items: [
    { productId: ObjectId("..."), quantity: 2 },
  ],
};

// BAD - Unbounded arrays
const badSchema = {
  comments: [], // Can grow infinitely - use separate collection
};
```

### Indexing

```typescript
// Create indexes for common queries
await db.collection('users').createIndex({ email: 1 }, { unique: true });
await db.collection('orders').createIndex({ userId: 1, createdAt: -1 });
await db.collection('products').createIndex({ category: 1, price: 1 });

// Compound index for covered queries
await db.collection('orders').createIndex(
  { userId: 1, status: 1, createdAt: -1 },
  { name: 'orders_user_status_date' }
);

// Text index for search
await db.collection('products').createIndex(
  { name: 'text', description: 'text' },
  { weights: { name: 10, description: 5 } }
);
```

### Connection Management

```typescript
// GOOD - Reuse connection in serverless
let cachedClient: MongoClient | null = null;

export async function getClient() {
  if (cachedClient) return cachedClient;
  cachedClient = await MongoClient.connect(uri);
  return cachedClient;
}

// BAD - Creating new connection per request
export async function handler() {
  const client = await MongoClient.connect(uri); // Don't do this
  // ...
  await client.close();
}
```

## Common Mistakes

1. **Creating connections per request** - Use connection pooling
2. **Missing indexes** - Query analysis with explain()
3. **Unbounded arrays** - Arrays that grow without limit
4. **Over-embedding** - Embedding data that's frequently updated independently
5. **No schema validation** - Use JSON Schema validation
6. **Ignoring read/write concerns** - Set appropriate durability levels
7. **Not using Atlas Search** - Building manual text search
8. **Wide IP whitelist without auth** - Security risk
9. **Not monitoring slow queries** - Enable profiling
10. **Missing retryable writes** - Connection string should include `retryWrites=true`

## Example Configuration

```yaml
# infera.yaml
project_name: my-app
provider: mongodb_atlas
environment: production

database:
  type: mongodb_atlas
  org_id: "your-org-id"

  cluster:
    name: my-cluster
    provider: AWS
    region: US_EAST_1
    tier: M10
    disk_auto_scaling: true

  backup:
    enabled: true
    frequency: daily

  search:
    enabled: true
    indexes:
      - name: products_search
        collection: products
        dynamic: true

  security:
    ip_whitelist:
      - 0.0.0.0/0  # For serverless
    tls: required
    encryption_at_rest: true

  users:
    - name: app_user
      roles:
        - { role: readWrite, db: mydb }

application:
  runtime: cloud_run

  env:
    MONGODB_URI:
      from_secret: mongodb-uri
    DB_NAME: mydb
```

## Sources

- [MongoDB Atlas Documentation](https://www.mongodb.com/docs/atlas/)
- [MongoDB Node.js Driver](https://www.mongodb.com/docs/drivers/node/current/)
- [Mongoose Documentation](https://mongoosejs.com/docs/)
- [MongoDB Schema Design Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
- [Atlas Search Documentation](https://www.mongodb.com/docs/atlas/atlas-search/)
- [MongoDB Performance Best Practices](https://www.mongodb.com/docs/manual/administration/analyzing-mongodb-performance/)
