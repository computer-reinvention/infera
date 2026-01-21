# Codebase Analysis Instructions

This document describes how to analyze a codebase to understand its infrastructure requirements.

## Overview

You have access to file system tools (Glob, Grep, Read) to analyze the codebase. Do NOT rely on hardcoded detection logic - inspect the actual files.

## Step 1: Identify Project Type

### Check for Configuration Files

Use Glob to find configuration files:

```
Glob: package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, Gemfile, pom.xml, build.gradle
```

Read whichever files exist to understand the project:
- `package.json` → Node.js/JavaScript project
- `requirements.txt` or `pyproject.toml` → Python project
- `go.mod` → Go project
- `Cargo.toml` → Rust project
- `Gemfile` → Ruby project
- `pom.xml` or `build.gradle` → Java project

## Step 2: Detect Frameworks

### For JavaScript/TypeScript Projects

Read `package.json` and check `dependencies` and `devDependencies`:

| Dependency | Framework | Type |
|------------|-----------|------|
| `react`, `react-dom` | React | Frontend |
| `vue` | Vue | Frontend |
| `@angular/core` | Angular | Frontend |
| `svelte` | Svelte | Frontend |
| `next` | Next.js | Fullstack |
| `nuxt` | Nuxt | Fullstack |
| `express` | Express | Backend |
| `@nestjs/core` | NestJS | Backend |
| `fastify` | Fastify | Backend |
| `hono` | Hono | Backend |

### For Python Projects

Read `requirements.txt` or `pyproject.toml` dependencies:

| Dependency | Framework | Type |
|------------|-----------|------|
| `fastapi` | FastAPI | Backend |
| `flask` | Flask | Backend |
| `django` | Django | Fullstack |
| `starlette` | Starlette | Backend |
| `streamlit` | Streamlit | Frontend |
| `gradio` | Gradio | Frontend |

### For Go Projects

Read `go.mod` for module imports:

| Import | Framework | Type |
|--------|-----------|------|
| `github.com/gin-gonic/gin` | Gin | Backend |
| `github.com/labstack/echo` | Echo | Backend |
| `github.com/gofiber/fiber` | Fiber | Backend |

## Step 3: Detect Database Requirements

Search for database drivers in dependency files:

### PostgreSQL
- Python: `psycopg2`, `psycopg`, `asyncpg`, `sqlalchemy` (with postgres)
- Node.js: `pg`, `postgres`, `@prisma/client` (check schema for postgres)
- Go: `github.com/lib/pq`, `github.com/jackc/pgx`

### MySQL
- Python: `pymysql`, `mysql-connector-python`, `aiomysql`
- Node.js: `mysql`, `mysql2`
- Go: `github.com/go-sql-driver/mysql`

### MongoDB
- Python: `pymongo`, `motor`, `mongoengine`
- Node.js: `mongodb`, `mongoose`
- Go: `go.mongodb.org/mongo-driver`

### Redis
- Python: `redis`, `aioredis`
- Node.js: `redis`, `ioredis`
- Go: `github.com/go-redis/redis`

## Step 4: Check for Containerization

### Dockerfile

```
Glob: Dockerfile, Dockerfile.*, *.dockerfile
```

If Dockerfile exists, read it to understand:
- Base image (indicates runtime)
- Exposed ports (`EXPOSE` directive)
- Entry point/command
- Multi-stage builds

### Docker Compose

```
Glob: docker-compose.yml, docker-compose.yaml, compose.yml, compose.yaml
```

If exists, read to understand:
- Services defined
- Volumes needed
- Networks
- Environment variables
- Dependencies between services

## Step 5: Find Entry Points

Look for common entry point files:

### Python
```
Glob: main.py, app.py, server.py, wsgi.py, asgi.py, manage.py
```

Read the file to find:
- Framework initialization (e.g., `app = FastAPI()`, `app = Flask(__name__)`)
- Port configuration
- Application factory patterns

### JavaScript/TypeScript
```
Glob: index.js, index.ts, server.js, server.ts, app.js, app.ts, main.js, main.ts
```

Also check `package.json` for:
- `main` field
- `scripts.start` command
- `scripts.dev` command

### Go
```
Glob: main.go, cmd/*/main.go
```

## Step 6: Identify Static Assets

```
Glob: public/**, static/**, dist/**, build/**, assets/**
```

Check if there's a build process:
- `package.json` scripts: `build`, `export`
- Output directories: `dist/`, `build/`, `.next/`, `out/`

## Step 7: Check for API Routes

### REST API Patterns
```
Grep: @app.route, @router, app.get(, app.post(, router.get(, router.post(
```

### GraphQL
```
Grep: graphql, @Query, @Mutation, type Query, type Mutation
```

## Step 8: Environment Variables

Look for environment configuration:
```
Glob: .env.example, .env.sample, .env.template
```

Read these files to understand what configuration is needed (never read actual `.env` files).

Also search code for environment variable usage:
```
Grep: process.env, os.environ, os.getenv, env::var
```

## Output Format

After analysis, summarize findings as:

```yaml
project_type: [static_site|api_service|fullstack|containerized|worker]
languages:
  - name: Python
    percentage: 60
  - name: JavaScript
    percentage: 40
frameworks:
  - name: FastAPI
    type: backend
    version: 0.100.0
  - name: React
    type: frontend
    version: 18.2.0
database_requirements:
  - type: postgresql
    detected_from: psycopg2 in requirements.txt
containerization:
  has_dockerfile: true
  has_compose: false
  base_image: python:3.11-slim
  exposed_ports: [8000]
entry_point: main.py
static_assets: null
environment_variables:
  - DATABASE_URL
  - API_KEY
  - DEBUG
```

Use this analysis to select the appropriate template from `_index.md`.
