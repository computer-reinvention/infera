# Template Selection Guide

Use this guide to select the appropriate infrastructure template based on codebase analysis.

## Decision Tree

### Step 1: Check for Containerization

**Is there a Dockerfile?**
- Yes → Check if it's a web service or background worker
  - Web service (exposes HTTP port via EXPOSE) → Use `containerized.md`
  - Background worker (no HTTP) → Use `containerized.md` with worker modifications
- No → Continue to Step 2

### Step 2: Identify Frontend Type

**What frontend framework is detected?**
- Static site generator (React, Vue, Angular, Svelte with static build) → Use `static_site.md`
- Server-rendered (Next.js with SSR, Nuxt with SSR) → Use `fullstack_app.md`
- No frontend detected → Continue to Step 3

### Step 3: Identify Backend Type

**What backend framework is detected?**
- REST/GraphQL API (FastAPI, Flask, Express, Django REST) → Use `api_service.md`
- Full web framework (Django with templates, Rails) → Use `fullstack_app.md`
- Background processing only → Use `containerized.md`
- No backend → Default to `static_site.md`

### Step 4: Database Requirements

**Does the codebase need a database?**

Detection signals:
- `psycopg2`, `asyncpg`, `sqlalchemy` → PostgreSQL needed
- `pymysql`, `mysql-connector` → MySQL needed
- `pymongo`, `motor` → MongoDB needed
- `redis`, `aioredis` → Redis needed

If database is needed, add database resources from the appropriate template.

## Template Combinations

| Codebase Type | Primary Template | Additional Resources |
|---------------|------------------|---------------------|
| React/Vue SPA | `static_site.md` | None |
| Next.js static export | `static_site.md` | None |
| FastAPI + React | `fullstack_app.md` | Cloud SQL if DB detected |
| Express API | `api_service.md` | Cloud SQL if DB detected |
| Docker + PostgreSQL | `containerized.md` | Cloud SQL |
| Simple HTML/CSS/JS | `static_site.md` | None |

## Detection Signals Reference

### Frontend Frameworks

| Framework | Detection Files | Key Patterns |
|-----------|----------------|--------------|
| React | package.json | `"react":`, `"react-dom":` |
| Vue | package.json, vue.config.js | `"vue":` |
| Angular | package.json, angular.json | `"@angular/core":` |
| Next.js | next.config.js | `"next":` |
| Svelte | svelte.config.js | `"svelte":` |

### Backend Frameworks

| Framework | Detection Files | Key Patterns |
|-----------|----------------|--------------|
| FastAPI | requirements.txt, pyproject.toml | `fastapi` |
| Flask | requirements.txt | `flask`, `Flask(` |
| Django | requirements.txt, manage.py | `django` |
| Express | package.json | `"express":` |
| NestJS | package.json | `"@nestjs/core":` |

### Containerization

| Signal | Files | Patterns |
|--------|-------|----------|
| Docker | Dockerfile | `FROM ` |
| Docker Compose | docker-compose.yml | `services:` |
| Kubernetes | k8s/, *.yaml | `kind: Deployment` |

## Cost Optimization Tips

1. **Static sites**: Use Cloud Storage + CDN instead of compute instances
2. **APIs with low traffic**: Use Cloud Run with scale-to-zero
3. **Databases**: Start with smallest tier, scale up based on usage
4. **Development**: Use preemptible/spot instances where possible
