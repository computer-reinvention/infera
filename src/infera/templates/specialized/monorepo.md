# Monorepo Architecture

## Overview
Monorepos contain multiple projects (apps, packages, services) in a single repository. Modern tooling enables efficient builds, shared code, and coordinated deployments while maintaining clear boundaries between components.

**Use when:**
- Multiple related applications share code
- Microservices with shared libraries
- Need atomic cross-project changes
- Want unified tooling and CI/CD
- Team collaboration across projects

**Don't use when:**
- Single, simple application
- Projects are completely independent
- Different teams with separate release cycles
- Very different tech stacks

## Detection Signals

```
Files:
- pnpm-workspace.yaml, turbo.json
- nx.json, workspace.json
- lerna.json
- packages/, apps/

Dependencies:
- turborepo, nx, lerna
- @changesets/cli
- syncpack

Code Patterns:
- "workspaces" in package.json
- @myorg/* internal packages
- shared/, common/ directories
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monorepo Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  my-monorepo/                                                   │
│  │                                                              │
│  ├── apps/                      # Deployable applications       │
│  │   ├── web/                   # Next.js frontend             │
│  │   ├── api/                   # Express API                  │
│  │   ├── admin/                 # Admin dashboard              │
│  │   └── mobile/                # React Native app             │
│  │                                                              │
│  ├── packages/                  # Shared packages              │
│  │   ├── ui/                    # Component library            │
│  │   ├── database/              # Prisma schema + client       │
│  │   ├── config/                # Shared configs (tsconfig)    │
│  │   ├── utils/                 # Shared utilities             │
│  │   └── types/                 # Shared TypeScript types      │
│  │                                                              │
│  ├── services/                  # Backend microservices        │
│  │   ├── users/                 # User service                 │
│  │   ├── orders/                # Order service                │
│  │   └── notifications/         # Notification service         │
│  │                                                              │
│  ├── turbo.json                 # Turborepo config             │
│  ├── pnpm-workspace.yaml        # Workspace config             │
│  └── package.json               # Root package.json            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Turborepo Setup

### Root Configuration

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
  - "services/*"
```

```json
// package.json (root)
{
  "name": "my-monorepo",
  "private": true,
  "scripts": {
    "build": "turbo build",
    "dev": "turbo dev",
    "lint": "turbo lint",
    "test": "turbo test",
    "typecheck": "turbo typecheck",
    "clean": "turbo clean && rm -rf node_modules",
    "format": "prettier --write \"**/*.{ts,tsx,md}\""
  },
  "devDependencies": {
    "prettier": "^3.0.0",
    "turbo": "^2.0.0",
    "typescript": "^5.0.0"
  },
  "packageManager": "pnpm@8.15.0"
}
```

```json
// turbo.json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**", "!.next/cache/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["^build"],
      "outputs": ["coverage/**"]
    },
    "typecheck": {
      "dependsOn": ["^build"]
    },
    "clean": {
      "cache": false
    },
    "deploy": {
      "dependsOn": ["build", "test", "lint"]
    }
  }
}
```

### Shared Package: UI Components

```json
// packages/ui/package.json
{
  "name": "@myorg/ui",
  "version": "0.0.0",
  "private": true,
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.js"
    },
    "./button": {
      "types": "./dist/button.d.ts",
      "import": "./dist/button.mjs",
      "require": "./dist/button.js"
    }
  },
  "scripts": {
    "build": "tsup",
    "dev": "tsup --watch",
    "lint": "eslint src/",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "@myorg/config": "workspace:*",
    "react": "^18.2.0",
    "tsup": "^8.0.0",
    "typescript": "^5.0.0"
  },
  "peerDependencies": {
    "react": "^18.2.0"
  }
}
```

```typescript
// packages/ui/src/button.tsx
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from './utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'rounded-md font-medium transition-colors',
          {
            'bg-blue-600 text-white hover:bg-blue-700': variant === 'primary',
            'bg-gray-200 text-gray-900 hover:bg-gray-300': variant === 'secondary',
            'border border-gray-300 hover:bg-gray-50': variant === 'outline',
          },
          {
            'px-3 py-1.5 text-sm': size === 'sm',
            'px-4 py-2 text-base': size === 'md',
            'px-6 py-3 text-lg': size === 'lg',
          },
          className
        )}
        {...props}
      />
    );
  }
);

// packages/ui/src/index.ts
export * from './button';
export * from './input';
export * from './card';
```

### Shared Package: Database

```json
// packages/database/package.json
{
  "name": "@myorg/database",
  "version": "0.0.0",
  "private": true,
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "scripts": {
    "build": "tsup",
    "db:generate": "prisma generate",
    "db:push": "prisma db push",
    "db:migrate": "prisma migrate dev",
    "db:studio": "prisma studio"
  },
  "dependencies": {
    "@prisma/client": "^5.0.0"
  },
  "devDependencies": {
    "prisma": "^5.0.0",
    "tsup": "^8.0.0"
  }
}
```

```typescript
// packages/database/src/index.ts
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma = globalForPrisma.prisma || new PrismaClient();

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;

export * from '@prisma/client';
```

### App: Web (Next.js)

```json
// apps/web/package.json
{
  "name": "@myorg/web",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "build": "next build",
    "dev": "next dev -p 3000",
    "lint": "next lint",
    "start": "next start"
  },
  "dependencies": {
    "@myorg/database": "workspace:*",
    "@myorg/ui": "workspace:*",
    "@myorg/utils": "workspace:*",
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@myorg/config": "workspace:*",
    "@types/react": "^18.2.0",
    "typescript": "^5.0.0"
  }
}
```

```typescript
// apps/web/app/page.tsx
import { Button } from '@myorg/ui';
import { prisma } from '@myorg/database';
import { formatDate } from '@myorg/utils';

export default async function HomePage() {
  const posts = await prisma.post.findMany({
    take: 10,
    orderBy: { createdAt: 'desc' },
  });

  return (
    <main>
      <h1>Latest Posts</h1>
      {posts.map((post) => (
        <article key={post.id}>
          <h2>{post.title}</h2>
          <time>{formatDate(post.createdAt)}</time>
          <Button variant="primary">Read More</Button>
        </article>
      ))}
    </main>
  );
}
```

### App: API (Express)

```json
// apps/api/package.json
{
  "name": "@myorg/api",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "build": "tsup",
    "dev": "tsx watch src/index.ts",
    "start": "node dist/index.js",
    "lint": "eslint src/"
  },
  "dependencies": {
    "@myorg/database": "workspace:*",
    "@myorg/utils": "workspace:*",
    "express": "^4.18.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "@types/express": "^4.17.0",
    "tsup": "^8.0.0",
    "tsx": "^4.0.0"
  }
}
```

```typescript
// apps/api/src/index.ts
import express from 'express';
import { prisma } from '@myorg/database';
import { validateRequest } from '@myorg/utils';

const app = express();
app.use(express.json());

app.get('/api/posts', async (req, res) => {
  const posts = await prisma.post.findMany();
  res.json(posts);
});

app.post('/api/posts', async (req, res) => {
  const validated = validateRequest(req.body, postSchema);
  const post = await prisma.post.create({ data: validated });
  res.json(post);
});

app.listen(3001, () => {
  console.log('API running on http://localhost:3001');
});
```

## Shared Configuration

```json
// packages/config/package.json
{
  "name": "@myorg/config",
  "version": "0.0.0",
  "private": true,
  "files": ["eslint", "typescript"]
}
```

```json
// packages/config/typescript/base.json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "declaration": true,
    "declarationMap": true
  }
}
```

```javascript
// packages/config/eslint/base.js
module.exports = {
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint'],
  rules: {
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
  },
};
```

## CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - uses: pnpm/action-setup@v2
        with:
          version: 8

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile

      # Use Turborepo remote caching
      - name: Build
        run: pnpm build
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ vars.TURBO_TEAM }}

      - name: Test
        run: pnpm test

      - name: Lint
        run: pnpm lint

  deploy-web:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v2
        with:
          version: 8

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - run: pnpm install --frozen-lockfile

      # Build only web and its dependencies
      - run: pnpm turbo build --filter=@myorg/web...

      - name: Deploy to Vercel
        run: vercel deploy --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

## Terraform Configuration

```hcl
# main.tf - Deploy multiple services from monorepo

# Web app (Next.js on Vercel)
# Deployed via Vercel CLI or integration

# API service (Cloud Run)
resource "google_cloud_run_v2_service" "api" {
  name     = "${var.project_name}-api"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/api:${var.api_version}"

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
  }
}

# User service (Cloud Run)
resource "google_cloud_run_v2_service" "users" {
  name     = "${var.project_name}-users"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/users:${var.users_version}"
    }
  }
}

# Orders service (Cloud Run)
resource "google_cloud_run_v2_service" "orders" {
  name     = "${var.project_name}-orders"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/orders:${var.orders_version}"
    }
  }
}
```

## Docker Build (Multi-stage)

```dockerfile
# Dockerfile (for apps/api)
FROM node:20-alpine AS base
RUN corepack enable

FROM base AS builder
WORKDIR /app
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm turbo build --filter=@myorg/api...

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy only necessary files
COPY --from=builder /app/apps/api/dist ./dist
COPY --from=builder /app/apps/api/package.json ./
COPY --from=builder /app/node_modules ./node_modules

# Prune dev dependencies
RUN pnpm prune --prod

USER node
EXPOSE 3001
CMD ["node", "dist/index.js"]
```

## Versioning with Changesets

```json
// .changeset/config.json
{
  "$schema": "https://unpkg.com/@changesets/config@2.3.1/schema.json",
  "changelog": "@changesets/cli/changelog",
  "commit": false,
  "fixed": [],
  "linked": [],
  "access": "restricted",
  "baseBranch": "main",
  "updateInternalDependencies": "patch",
  "ignore": []
}
```

```bash
# Create changeset
pnpm changeset

# Version packages
pnpm changeset version

# Publish (if public)
pnpm changeset publish
```

## Cost Breakdown

| Service | Platform | ~Cost/mo |
|---------|----------|----------|
| **Web** | Vercel | $20 (Pro) |
| **API** | Cloud Run | ~$20 |
| **Services** | Cloud Run x3 | ~$60 |
| **Database** | Cloud SQL | ~$50 |
| **CI/CD** | GitHub Actions | Free |
| **Total** | | ~$150/mo |

## Best Practices

### Dependency Management

```bash
# Add dependency to specific package
pnpm add lodash --filter @myorg/utils

# Add dev dependency to root
pnpm add -D prettier -w

# Update all packages
pnpm update -r
```

### Filtering Builds

```bash
# Build specific app
pnpm turbo build --filter=@myorg/web

# Build app and dependencies
pnpm turbo build --filter=@myorg/web...

# Build only changed packages
pnpm turbo build --filter=[HEAD^1]

# Build dependents of changed packages
pnpm turbo build --filter=...[@myorg/ui]
```

## Common Mistakes

1. **Circular dependencies** - Package A imports B, B imports A
2. **No workspace protocol** - Using versions instead of `workspace:*`
3. **Building everything** - Not using filters for deployments
4. **Shared state** - Singletons across packages
5. **No caching** - Missing Turborepo remote cache
6. **Large Docker images** - Not pruning properly
7. **Version drift** - Inconsistent dependency versions
8. **Missing peer deps** - UI components without React peer dep
9. **No changesets** - Manual version management
10. **Tight coupling** - Hard boundaries not enforced

## Example Configuration

```yaml
# infera.yaml
project_name: my-saas
provider: gcp
region: us-central1

monorepo:
  tool: turborepo
  package_manager: pnpm

  apps:
    web:
      type: nextjs
      deploy: vercel

    api:
      type: express
      deploy: cloud_run
      dockerfile: apps/api/Dockerfile

  services:
    users:
      deploy: cloud_run
      dockerfile: services/users/Dockerfile

    orders:
      deploy: cloud_run
      dockerfile: services/orders/Dockerfile

  packages:
    - ui
    - database
    - utils
    - config

ci:
  cache:
    turbo_remote: true

  triggers:
    - path: "apps/web/**"
      deploy: web
    - path: "apps/api/**"
      deploy: api
    - path: "services/users/**"
      deploy: users
    - path: "packages/**"
      deploy: all
```

## Sources

- [Turborepo Documentation](https://turbo.build/repo/docs)
- [pnpm Workspaces](https://pnpm.io/workspaces)
- [Nx Documentation](https://nx.dev/getting-started/intro)
- [Changesets](https://github.com/changesets/changesets)
- [Monorepo Tools Comparison](https://monorepo.tools/)
