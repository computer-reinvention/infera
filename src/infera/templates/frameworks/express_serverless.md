# Express.js Serverless (Lambda / Workers)

## Overview

Deploy Express.js applications on serverless platforms for automatic scaling, cost efficiency, and minimal operational overhead. Express.js's minimal footprint and extensive middleware ecosystem make it ideal for serverless APIs. Supports AWS Lambda, Cloudflare Workers, and GCP Cloud Run.

## Detection Signals

Use this template when:
- `package.json` contains `express` dependency
- `app.js` or `server.js` with Express setup
- REST API application
- Middleware-heavy architecture
- Serverless deployment preferred
- Cost optimization priority
- Simple to moderate complexity

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Serverless Platform                           │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  API Gateway / Edge                      │   │
                    │   │           (API Gateway / Cloudflare Edge)                │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Serverless Compute                          │   │
                    │   │        (Lambda / Workers / Cloud Run)                    │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │  Express  │ │  Express  │ │  Express  │             │   │
                    │   │  │ Instance  │ │ Instance  │ │ Instance  │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │Middleware │ │Middleware │ │Middleware │             │   │
                    │   │  │  Stack    │ │  Stack    │ │  Stack    │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 0-1000+ concurrent executions            │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │  Database │     │   Cache   │     │  Storage  │            │
                    │   │(DynamoDB/ │     │  (Redis/  │     │  (S3/R2)  │            │
                    │   │PlanetScale│     │    KV)    │     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Scale to zero • <100ms cold start • Pay per request          │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### AWS Lambda
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Lambda | Function compute | 1GB RAM, Node.js 20 |
| API Gateway | HTTP routing | HTTP API |
| DynamoDB | Database | On-demand |
| ElastiCache | Redis cache | Optional |
| S3 | File storage | Standard |
| Secrets Manager | Credentials | Lambda integration |

### Cloudflare Workers
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Workers | Edge compute | Bundled |
| D1 | SQL database | SQLite |
| KV | Key-value store | Global |
| R2 | Object storage | S3-compatible |
| Queues | Async processing | Optional |

### GCP Cloud Run
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container | 1 vCPU, 512MB |
| Cloud SQL | PostgreSQL | db-f1-micro |
| Memorystore | Redis | Optional |
| Cloud Storage | Files | Regional |

## Configuration

### Project Structure
```
my-express-app/
├── src/
│   ├── app.ts              # Express app
│   ├── routes/
│   │   ├── index.ts
│   │   ├── users.ts
│   │   └── items.ts
│   ├── middleware/
│   │   ├── auth.ts
│   │   ├── errorHandler.ts
│   │   └── validation.ts
│   ├── services/
│   │   └── userService.ts
│   ├── models/
│   │   └── user.ts
│   └── utils/
│       └── logger.ts
├── tests/
├── package.json
├── tsconfig.json
├── serverless.yml          # AWS Lambda
├── wrangler.toml           # Cloudflare Workers
└── Dockerfile              # Cloud Run
```

### Express Application
```typescript
// src/app.ts
import express, { Express, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { pinoHttp } from 'pino-http';

import userRoutes from './routes/users';
import itemRoutes from './routes/items';
import { errorHandler } from './middleware/errorHandler';
import { notFoundHandler } from './middleware/notFoundHandler';

const app: Express = express();

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.CORS_ORIGINS?.split(',') || '*',
  credentials: true,
}));

// Request parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Compression
app.use(compression());

// Logging
app.use(pinoHttp({
  level: process.env.LOG_LEVEL || 'info',
  redact: ['req.headers.authorization'],
}));

// Health check
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.VERSION || '1.0.0',
  });
});

// API routes
app.use('/api/v1/users', userRoutes);
app.use('/api/v1/items', itemRoutes);

// Error handling
app.use(notFoundHandler);
app.use(errorHandler);

export { app };
```

### Routes
```typescript
// src/routes/users.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { validate } from '../middleware/validation';
import { UserService } from '../services/userService';

const router = Router();
const userService = new UserService();

// Validation schemas
const createUserSchema = z.object({
  body: z.object({
    email: z.string().email(),
    name: z.string().min(2).max(100),
    password: z.string().min(8),
  }),
});

const querySchema = z.object({
  query: z.object({
    page: z.coerce.number().int().positive().default(1),
    limit: z.coerce.number().int().positive().max(100).default(20),
    search: z.string().optional(),
  }),
});

// List users
router.get('/', validate(querySchema), async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { page, limit, search } = req.query as any;
    const result = await userService.list({ page, limit, search });
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// Create user
router.post('/', validate(createUserSchema), async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.create(req.body);
    res.status(201).json(user);
  } catch (error) {
    next(error);
  }
});

// Get user by ID
router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.getById(req.params.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (error) {
    next(error);
  }
});

// Update user
router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.update(req.params.id, req.body);
    res.json(user);
  } catch (error) {
    next(error);
  }
});

// Delete user
router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
  try {
    await userService.delete(req.params.id);
    res.status(204).send();
  } catch (error) {
    next(error);
  }
});

export default router;
```

### Error Handler Middleware
```typescript
// src/middleware/errorHandler.ts
import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';

interface AppError extends Error {
  statusCode?: number;
  code?: string;
}

export function errorHandler(
  error: AppError,
  req: Request,
  res: Response,
  next: NextFunction
) {
  req.log?.error(error);

  // Zod validation error
  if (error instanceof ZodError) {
    return res.status(400).json({
      error: 'Validation Error',
      details: error.errors.map(e => ({
        path: e.path.join('.'),
        message: e.message,
      })),
    });
  }

  // Custom app error
  if (error.statusCode) {
    return res.status(error.statusCode).json({
      error: error.message,
      code: error.code,
    });
  }

  // Default server error
  res.status(500).json({
    error: process.env.NODE_ENV === 'production'
      ? 'Internal Server Error'
      : error.message,
  });
}

export function notFoundHandler(req: Request, res: Response) {
  res.status(404).json({
    error: 'Not Found',
    path: req.path,
  });
}
```

### AWS Lambda Handler
```typescript
// src/lambda.ts
import serverless from 'serverless-http';
import { app } from './app';

// Wrap Express app for Lambda
export const handler = serverless(app, {
  request: (request: any, event: any, context: any) => {
    // Add Lambda context to request
    request.lambdaEvent = event;
    request.lambdaContext = context;
  },
});
```

### Serverless Framework Config
```yaml
# serverless.yml
service: my-express-api

provider:
  name: aws
  runtime: nodejs20.x
  region: ${opt:region, 'us-east-1'}
  stage: ${opt:stage, 'dev'}
  memorySize: 1024
  timeout: 30

  environment:
    NODE_ENV: production
    DATABASE_URL: ${ssm:/my-app/database-url}
    JWT_SECRET: ${ssm:/my-app/jwt-secret}

  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - dynamodb:*
          Resource:
            - !GetAtt UsersTable.Arn
        - Effect: Allow
          Action:
            - s3:*
          Resource:
            - !Sub arn:aws:s3:::${self:service}-${self:provider.stage}-uploads/*

functions:
  api:
    handler: dist/lambda.handler
    events:
      - httpApi:
          method: '*'
          path: '*'
    vpc:
      securityGroupIds:
        - !Ref LambdaSecurityGroup
      subnetIds:
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2

resources:
  Resources:
    UsersTable:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:service}-${self:provider.stage}-users
        BillingMode: PAY_PER_REQUEST
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
          - AttributeName: email
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH
        GlobalSecondaryIndexes:
          - IndexName: email-index
            KeySchema:
              - AttributeName: email
                KeyType: HASH
            Projection:
              ProjectionType: ALL

plugins:
  - serverless-esbuild
  - serverless-offline

custom:
  esbuild:
    bundle: true
    minify: true
    target: node20
    platform: node
    sourcemap: true
```

### Cloudflare Workers Adapter
```typescript
// src/worker.ts
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';

// Note: For Cloudflare Workers, use Hono instead of Express
// Express doesn't run natively on Workers runtime

const app = new Hono<{ Bindings: Env }>();

interface Env {
  DB: D1Database;
  KV: KVNamespace;
  BUCKET: R2Bucket;
}

// Middleware
app.use('*', logger());
app.use('*', cors());

// Health check
app.get('/health', (c) => {
  return c.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
  });
});

// Users API
app.get('/api/v1/users', async (c) => {
  const db = c.env.DB;
  const { results } = await db
    .prepare('SELECT id, email, name FROM users LIMIT 100')
    .all();
  return c.json({ users: results });
});

app.post('/api/v1/users', async (c) => {
  const db = c.env.DB;
  const body = await c.req.json();

  const { success } = await db
    .prepare('INSERT INTO users (id, email, name) VALUES (?, ?, ?)')
    .bind(crypto.randomUUID(), body.email, body.name)
    .run();

  if (!success) {
    return c.json({ error: 'Failed to create user' }, 500);
  }

  return c.json({ success: true }, 201);
});

app.get('/api/v1/users/:id', async (c) => {
  const db = c.env.DB;
  const id = c.req.param('id');

  const user = await db
    .prepare('SELECT * FROM users WHERE id = ?')
    .bind(id)
    .first();

  if (!user) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.json(user);
});

export default app;
```

### Wrangler Configuration
```toml
# wrangler.toml
name = "my-express-api"
main = "src/worker.ts"
compatibility_date = "2024-01-01"
compatibility_flags = ["nodejs_compat"]

# D1 Database
[[d1_databases]]
binding = "DB"
database_name = "express-api-db"
database_id = "your-database-id"

# KV Namespace
[[kv_namespaces]]
binding = "KV"
id = "your-kv-id"

# R2 Bucket
[[r2_buckets]]
binding = "BUCKET"
bucket_name = "express-api-uploads"

[vars]
ENVIRONMENT = "production"
```

### Dockerfile (Cloud Run)
```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 nodejs && adduser -S -u 1001 nodejs

# Copy dependencies
COPY --from=builder /app/node_modules ./node_modules
COPY --chown=nodejs:nodejs . .

USER nodejs

EXPOSE 8080
ENV PORT=8080

CMD ["node", "dist/server.js"]
```

### Server Entry Point
```typescript
// src/server.ts
import { app } from './app';

const port = process.env.PORT || 8080;

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
```

### package.json
```json
{
  "name": "my-express-api",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js",
    "deploy:lambda": "serverless deploy",
    "deploy:workers": "wrangler deploy",
    "deploy:cloudrun": "gcloud run deploy"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "helmet": "^7.1.0",
    "compression": "^1.7.4",
    "pino-http": "^9.0.0",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.10.0",
    "typescript": "^5.3.0",
    "tsx": "^4.6.0",
    "serverless": "^3.38.0",
    "serverless-http": "^3.2.0",
    "serverless-esbuild": "^1.50.0",
    "wrangler": "^3.22.0"
  }
}
```

## Deployment Commands

### AWS Lambda
```bash
# Install Serverless
npm install -g serverless

# Deploy
npm run build
serverless deploy

# Deploy single function
serverless deploy function -f api

# View logs
serverless logs -f api -t

# Invoke locally
serverless invoke local -f api --path event.json

# Remove
serverless remove
```

### Cloudflare Workers
```bash
# Deploy
wrangler deploy

# Create D1 database
wrangler d1 create express-api-db

# Run migrations
wrangler d1 execute express-api-db --file=./migrations/schema.sql

# Tail logs
wrangler tail

# Local development
wrangler dev
```

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT_ID}/express-api

# Deploy
gcloud run deploy express-api \
  --image gcr.io/${PROJECT_ID}/express-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 100

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100
```

## Cost Breakdown

### AWS Lambda
| Component | Monthly Cost |
|-----------|--------------|
| Lambda (1M requests) | ~$3 |
| API Gateway | ~$3.50 |
| DynamoDB (on-demand) | ~$5 |
| **Total** | **~$12** |

### Cloudflare Workers
| Resource | Free | Paid |
|----------|------|------|
| Workers | 100K req/day | $5/10M |
| D1 | 5GB, 5M reads | $0.75/M |
| KV | 100K reads | $0.50/M |
| **Total** | **$0** | **~$10/mo** |

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (scale to 0) | ~$0-20 |
| Cloud SQL | ~$10 |
| **Total** | **~$10-30** |

## Best Practices

1. **Use TypeScript** - Type safety catches errors early
2. **Validation with Zod** - Runtime type checking
3. **Structured logging** - JSON logs for cloud platforms
4. **Error handling middleware** - Centralized error responses
5. **Health check endpoint** - Required for all platforms
6. **Environment-based config** - No hardcoded values
7. **Compression** - Reduce response sizes
8. **Security headers** - Helmet middleware

## Common Mistakes

1. **Large Lambda package** - Use esbuild to bundle
2. **No cold start optimization** - Keep bundle small
3. **Sync file I/O** - Use async operations
4. **No connection pooling** - Use serverless-friendly DBs
5. **Missing error handling** - Unhandled promises crash
6. **Hardcoded secrets** - Use environment variables
7. **No request validation** - Use Zod schemas
8. **Large payloads** - Lambda has 6MB limit

## Example Configuration

```yaml
# infera.yaml
project_name: my-express-api
provider: aws  # or cloudflare, gcp

framework:
  name: express
  version: "4"

deployment:
  type: serverless

  # AWS Lambda
  aws:
    runtime: nodejs20.x
    memory: 1024
    timeout: 30
    vpc: true

  # Cloudflare Workers
  cloudflare:
    bindings:
      d1: DB
      kv: KV
      r2: BUCKET

  # GCP Cloud Run
  gcp:
    memory: 512Mi
    min_instances: 0
    max_instances: 100

database:
  type: dynamodb  # or d1, postgresql
  mode: on-demand

env_vars:
  NODE_ENV: production

secrets:
  - JWT_SECRET
  - DATABASE_URL
```

## Sources

- [Express.js Documentation](https://expressjs.com/)
- [Serverless Framework](https://www.serverless.com/framework/docs)
- [Cloudflare Workers](https://developers.cloudflare.com/workers/)
- [Cloud Run Node.js](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/nodejs)
