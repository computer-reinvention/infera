# Multi-Tenant SaaS Architecture

## Overview
Multi-tenant architecture serves multiple customers (tenants) from a single application instance while keeping their data isolated. Essential for SaaS products that need to scale efficiently while maintaining security and customization per tenant.

**Use when:**
- Building SaaS products with multiple customers
- Need efficient resource utilization
- Customers require data isolation
- Want centralized management and updates
- Need per-tenant customization

**Don't use when:**
- Single customer deployments
- Strict compliance requiring physical isolation
- Very different feature sets per customer

## Detection Signals

```
Files:
- middleware/tenant.*, tenant.middleware.*
- models/tenant.*, organizations/
- database/migrations/*tenant*

Dependencies:
- django-tenants (Python)
- @prisma/client with multi-schema

Code Patterns:
- tenant_id, organization_id
- X-Tenant-ID header
- subdomain extraction
- Row-level security (RLS)
```

## Tenancy Models

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Tenancy Strategies                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     1. SHARED DATABASE + SHARED SCHEMA (Column-based)    │   │
│  │                                                           │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │                 users table                          │ │   │
│  │  │  id | tenant_id | email           | name            │ │   │
│  │  │  1  | acme      | john@acme.com   | John            │ │   │
│  │  │  2  | globex    | jane@globex.com | Jane            │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │  + Simple, efficient, easy migrations                    │   │
│  │  - Requires careful query filtering                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     2. SHARED DATABASE + SEPARATE SCHEMAS                │   │
│  │                                                           │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐│   │
│  │  │ schema: acme  │  │ schema: globex│  │ schema: public││   │
│  │  │               │  │               │  │ (shared)      ││   │
│  │  │ users         │  │ users         │  │ plans         ││   │
│  │  │ orders        │  │ orders        │  │ features      ││   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘│   │
│  │  + Strong isolation, simpler queries                     │   │
│  │  - Complex migrations, schema per tenant overhead        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     3. SEPARATE DATABASES                                │   │
│  │                                                           │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐            │   │
│  │  │ DB: acme  │  │ DB: globex│  │ DB: initec│            │   │
│  │  │           │  │           │  │           │            │   │
│  │  │ All tables│  │ All tables│  │ All tables│            │   │
│  │  └───────────┘  └───────────┘  └───────────┘            │   │
│  │  + Maximum isolation, compliance friendly                │   │
│  │  - Highest cost, complex connection management           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Column-Based Multi-Tenancy (Most Common)

### Database Schema

```sql
-- Core tenant table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(63) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users belong to tenants
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- RLS policy - users can only see their tenant's data
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- All tenant tables follow this pattern
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON projects
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Index on tenant_id for all tenant tables
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_projects_tenant ON projects(tenant_id);
```

### Prisma Schema

```prisma
// schema.prisma
model Tenant {
  id        String   @id @default(uuid())
  slug      String   @unique
  name      String
  plan      String   @default("free")
  settings  Json     @default("{}")
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  users     User[]
  projects  Project[]

  @@map("tenants")
}

model User {
  id        String   @id @default(uuid())
  tenantId  String   @map("tenant_id")
  email     String
  name      String?
  role      String   @default("member")
  createdAt DateTime @default(now()) @map("created_at")

  tenant    Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  projects  Project[]

  @@unique([tenantId, email])
  @@index([tenantId])
  @@map("users")
}

model Project {
  id        String   @id @default(uuid())
  tenantId  String   @map("tenant_id")
  name      String
  ownerId   String   @map("owner_id")
  createdAt DateTime @default(now()) @map("created_at")

  tenant    Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  owner     User     @relation(fields: [ownerId], references: [id])

  @@index([tenantId])
  @@map("projects")
}
```

### Tenant Middleware (Node.js/Express)

```typescript
// middleware/tenant.ts
import { Request, Response, NextFunction } from 'express';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Extend Express Request
declare global {
  namespace Express {
    interface Request {
      tenant?: {
        id: string;
        slug: string;
        name: string;
        plan: string;
        settings: any;
      };
    }
  }
}

export async function tenantMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Extract tenant from subdomain
  const host = req.get('host') || '';
  const subdomain = host.split('.')[0];

  // Or from header
  const tenantSlug = req.headers['x-tenant-id'] as string || subdomain;

  if (!tenantSlug || tenantSlug === 'www' || tenantSlug === 'api') {
    return res.status(400).json({ error: 'Tenant not specified' });
  }

  try {
    const tenant = await prisma.tenant.findUnique({
      where: { slug: tenantSlug },
    });

    if (!tenant) {
      return res.status(404).json({ error: 'Tenant not found' });
    }

    req.tenant = tenant;
    next();
  } catch (error) {
    console.error('Tenant lookup error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}

// Usage
app.use('/api', tenantMiddleware);
```

### Scoped Prisma Client

```typescript
// lib/prisma.ts
import { PrismaClient } from '@prisma/client';

// Create tenant-scoped client
export function createTenantPrisma(tenantId: string) {
  const prisma = new PrismaClient();

  return prisma.$extends({
    query: {
      $allModels: {
        async findMany({ model, args, query }) {
          // Skip tenant filtering for Tenant model
          if (model === 'Tenant') return query(args);

          args.where = { ...args.where, tenantId };
          return query(args);
        },
        async findFirst({ model, args, query }) {
          if (model === 'Tenant') return query(args);

          args.where = { ...args.where, tenantId };
          return query(args);
        },
        async findUnique({ model, args, query }) {
          if (model === 'Tenant') return query(args);

          // For findUnique, we need to verify tenant after fetch
          const result = await query(args);
          if (result && result.tenantId !== tenantId) {
            return null;
          }
          return result;
        },
        async create({ model, args, query }) {
          if (model === 'Tenant') return query(args);

          args.data = { ...args.data, tenantId };
          return query(args);
        },
        async update({ model, args, query }) {
          if (model === 'Tenant') return query(args);

          args.where = { ...args.where, tenantId };
          return query(args);
        },
        async delete({ model, args, query }) {
          if (model === 'Tenant') return query(args);

          args.where = { ...args.where, tenantId };
          return query(args);
        },
      },
    },
  });
}

// Usage in request handler
app.get('/api/projects', async (req, res) => {
  const prisma = createTenantPrisma(req.tenant!.id);

  // Automatically filtered by tenant
  const projects = await prisma.project.findMany();

  res.json(projects);
});
```

### Next.js Implementation

```typescript
// lib/tenant.ts
import { headers } from 'next/headers';
import { cache } from 'react';
import { prisma } from './prisma';

export const getTenant = cache(async () => {
  const headersList = headers();
  const host = headersList.get('host') || '';
  const subdomain = host.split('.')[0];

  if (!subdomain || subdomain === 'www' || subdomain === 'app') {
    return null;
  }

  return prisma.tenant.findUnique({
    where: { slug: subdomain },
  });
});

// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const host = request.headers.get('host') || '';
  const subdomain = host.split('.')[0];

  // Redirect www to main domain
  if (subdomain === 'www') {
    const url = request.nextUrl.clone();
    url.host = host.replace('www.', '');
    return NextResponse.redirect(url);
  }

  // Add tenant header for API routes
  const response = NextResponse.next();
  response.headers.set('x-tenant-slug', subdomain);

  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

## Schema-Based Multi-Tenancy (PostgreSQL)

### Django Tenants

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'mydb',
        'USER': 'user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    # ... other middleware
]

SHARED_APPS = [
    'django_tenants',
    'tenants',  # Your tenant model app
    'django.contrib.auth',
    'django.contrib.contenttypes',
]

TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'myapp',
]

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = 'tenants.Tenant'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

# models.py
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    plan = models.CharField(max_length=50, default='free')
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

class Domain(DomainMixin):
    pass

# Tenant-specific model (automatically in tenant schema)
class Project(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

# views.py
from django.http import JsonResponse
from .models import Project

def list_projects(request):
    # Automatically queries current tenant's schema
    projects = Project.objects.all()
    return JsonResponse({'projects': list(projects.values())})
```

## Authentication & Authorization

```typescript
// auth/tenant-auth.ts
import { verify } from 'jsonwebtoken';

interface TenantToken {
  userId: string;
  tenantId: string;
  role: 'owner' | 'admin' | 'member';
  permissions: string[];
}

export function verifyTenantToken(token: string): TenantToken {
  return verify(token, process.env.JWT_SECRET!) as TenantToken;
}

// Middleware
export function requirePermission(permission: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const decoded = verifyTenantToken(token);

    // Verify token tenant matches request tenant
    if (decoded.tenantId !== req.tenant?.id) {
      return res.status(403).json({ error: 'Tenant mismatch' });
    }

    // Check permission
    if (!decoded.permissions.includes(permission) && decoded.role !== 'owner') {
      return res.status(403).json({ error: 'Permission denied' });
    }

    req.user = decoded;
    next();
  };
}

// Usage
app.delete('/api/projects/:id', requirePermission('projects:delete'), async (req, res) => {
  // ...
});
```

## Feature Flags & Plan Limits

```typescript
// lib/features.ts
interface PlanFeatures {
  maxUsers: number;
  maxProjects: number;
  features: string[];
}

const PLANS: Record<string, PlanFeatures> = {
  free: {
    maxUsers: 3,
    maxProjects: 5,
    features: ['basic_reports'],
  },
  pro: {
    maxUsers: 20,
    maxProjects: 50,
    features: ['basic_reports', 'advanced_reports', 'api_access'],
  },
  enterprise: {
    maxUsers: -1, // Unlimited
    maxProjects: -1,
    features: ['basic_reports', 'advanced_reports', 'api_access', 'sso', 'audit_logs'],
  },
};

export function getTenantFeatures(plan: string): PlanFeatures {
  return PLANS[plan] || PLANS.free;
}

export function hasFeature(tenant: { plan: string }, feature: string): boolean {
  const features = getTenantFeatures(tenant.plan);
  return features.features.includes(feature);
}

export function checkLimit(
  tenant: { plan: string },
  resource: 'users' | 'projects',
  currentCount: number
): boolean {
  const features = getTenantFeatures(tenant.plan);
  const limit = resource === 'users' ? features.maxUsers : features.maxProjects;
  return limit === -1 || currentCount < limit;
}

// Middleware
export function requireFeature(feature: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!hasFeature(req.tenant!, feature)) {
      return res.status(403).json({
        error: 'Feature not available',
        upgrade_url: '/settings/billing',
      });
    }
    next();
  };
}

// Usage
app.post('/api/projects', requireFeature('projects'), async (req, res) => {
  const projectCount = await prisma.project.count({
    where: { tenantId: req.tenant!.id },
  });

  if (!checkLimit(req.tenant!, 'projects', projectCount)) {
    return res.status(403).json({
      error: 'Project limit reached',
      current: projectCount,
      limit: getTenantFeatures(req.tenant!.plan).maxProjects,
    });
  }

  // Create project...
});
```

## Terraform Configuration

```hcl
# multi_tenant.tf

# Shared infrastructure
resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-custom-4-15360"

    database_flags {
      name  = "max_connections"
      value = "500"  # Support many tenants
    }
  }
}

# Cloud Run service
resource "google_cloud_run_v2_service" "api" {
  name     = "${var.project_name}-api"
  location = var.region

  template {
    containers {
      image = var.container_image

      env {
        name  = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }
    }

    scaling {
      min_instance_count = 2
      max_instance_count = 100
    }
  }
}

# Custom domains per tenant (optional)
resource "google_cloud_run_domain_mapping" "tenant_domains" {
  for_each = var.tenant_domains

  location = var.region
  name     = each.value

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.api.name
  }
}
```

## Cost Breakdown

| Strategy | Infra Cost | Complexity | Isolation |
|----------|------------|------------|-----------|
| **Shared DB + Column** | Lowest | Low | Soft |
| **Shared DB + Schema** | Low | Medium | Medium |
| **Separate Databases** | Highest | High | Strong |

## Best Practices

### Always Filter by Tenant

```typescript
// BAD - Forgot tenant filter
const users = await prisma.user.findMany();

// GOOD - Explicit tenant filter
const users = await prisma.user.findMany({
  where: { tenantId: req.tenant.id },
});

// BETTER - Use scoped client (can't forget)
const prisma = createTenantPrisma(req.tenant.id);
const users = await prisma.user.findMany();
```

### Audit Logging

```typescript
// Log all tenant data access
async function auditLog(
  tenantId: string,
  userId: string,
  action: string,
  resource: string,
  resourceId: string
) {
  await prisma.auditLog.create({
    data: {
      tenantId,
      userId,
      action,
      resource,
      resourceId,
      timestamp: new Date(),
    },
  });
}
```

## Common Mistakes

1. **Forgetting tenant filter** - Data leaks between tenants
2. **No RLS as backup** - Single point of failure
3. **Shared sequences** - IDs reveal tenant count
4. **Cross-tenant joins** - Performance and security issues
5. **No tenant in URLs** - Hard to debug/audit
6. **Missing tenant indexes** - Slow queries
7. **Tenant in JWT only** - Easy to forge
8. **No rate limiting per tenant** - Noisy neighbor
9. **Shared cache keys** - Cache poisoning
10. **No data export** - Compliance issues

## Example Configuration

```yaml
# infera.yaml
project_name: my-saas
provider: gcp
region: us-central1

multi_tenant:
  strategy: column_based
  tenant_identifier: subdomain  # or header, path

  database:
    type: postgres_managed
    enable_rls: true

  features:
    custom_domains: true
    white_labeling: false

  plans:
    free:
      max_users: 3
      max_projects: 5
    pro:
      max_users: 20
      max_projects: 50
    enterprise:
      max_users: unlimited
      max_projects: unlimited
      features: [sso, audit_logs, api]

services:
  api:
    runtime: cloud_run
    min_instances: 2
```

## Sources

- [Multi-tenant SaaS Patterns](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/)
- [PostgreSQL Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Django Tenants](https://django-tenants.readthedocs.io/)
- [Prisma Multi-tenancy](https://www.prisma.io/docs/guides/other/multi-tenancy)
