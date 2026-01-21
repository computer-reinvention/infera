# Docker Best Practices

## Overview

Optimized Docker images reduce build times, deployment latency, security vulnerabilities, and cloud costs. This guide covers battle-tested patterns for building production-ready container images.

### Key Metrics
- **Image size**: Smaller = faster pulls, lower storage costs
- **Build time**: Faster = better CI/CD, faster deployments
- **Security**: Fewer packages = smaller attack surface
- **Layer caching**: Better caching = faster rebuilds

## Image Size Optimization

### Base Image Selection

| Base Image | Size | Use Case |
|------------|------|----------|
| `scratch` | 0 MB | Static Go/Rust binaries |
| `alpine` | 7 MB | Minimal Linux, musl libc |
| `distroless` | 20-50 MB | No shell, production apps |
| `debian-slim` | 80 MB | When glibc required |
| `ubuntu` | 78 MB | Full compatibility |
| `node:alpine` | 175 MB | Node.js production |
| `node:slim` | 250 MB | Node.js with glibc |
| `python:slim` | 150 MB | Python production |

### Multi-Stage Builds

```dockerfile
# ==========================================
# Node.js Multi-Stage Build
# ==========================================

# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 3: Production
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only necessary files
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

USER nextjs

EXPOSE 3000

CMD ["node", "dist/server.js"]

# Result: ~150MB instead of ~1GB
```

```dockerfile
# ==========================================
# Python Multi-Stage Build
# ==========================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim AS runner

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy installed packages
COPY --from=builder /root/.local /home/app/.local
ENV PATH=/home/app/.local/bin:$PATH

# Copy application
COPY --chown=app:app . .

USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Result: ~200MB instead of ~1.2GB
```

```dockerfile
# ==========================================
# Go Static Binary Build
# ==========================================

# Stage 1: Builder
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build static binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server

# Stage 2: Minimal runtime
FROM scratch

# Copy SSL certificates for HTTPS
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copy binary
COPY --from=builder /app/server /server

EXPOSE 8080

ENTRYPOINT ["/server"]

# Result: ~10MB instead of ~800MB
```

### Distroless Images

```dockerfile
# ==========================================
# Node.js with Distroless
# ==========================================

FROM node:20 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM gcr.io/distroless/nodejs20-debian12
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
CMD ["dist/server.js"]

# No shell, no package manager, no attack surface
```

```dockerfile
# ==========================================
# Python with Distroless
# ==========================================

FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --target=/app/deps -r requirements.txt
COPY . .

FROM gcr.io/distroless/python3-debian12
WORKDIR /app
COPY --from=builder /app/deps /app/deps
COPY --from=builder /app/*.py ./
ENV PYTHONPATH=/app/deps
CMD ["main.py"]
```

## Layer Caching Optimization

### Order Dependencies First

```dockerfile
# BAD: Cache invalidated on any code change
COPY . .
RUN npm ci

# GOOD: Dependencies cached separately
COPY package*.json ./
RUN npm ci
COPY . .
```

### Use .dockerignore

```dockerignore
# .dockerignore
node_modules
npm-debug.log
.git
.gitignore
.env
.env.*
*.md
!README.md
Dockerfile
docker-compose*.yml
.dockerignore
coverage
.nyc_output
.pytest_cache
__pycache__
*.pyc
.venv
venv
.idea
.vscode
*.log
tmp
```

### BuildKit Cache Mounts

```dockerfile
# syntax=docker/dockerfile:1.4

FROM node:20-alpine

WORKDIR /app

# Cache npm packages between builds
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .
RUN npm run build
```

```dockerfile
# Python with pip cache
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .
```

```dockerfile
# Go with module cache
FROM golang:1.21

WORKDIR /app

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build \
    go build -o /app/server
```

## Security Best Practices

### Non-Root User

```dockerfile
# Create and use non-root user
FROM node:20-alpine

# Create user with specific UID/GID
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

WORKDIR /app

# Change ownership
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

CMD ["node", "server.js"]
```

### Read-Only Filesystem

```dockerfile
# Application with read-only filesystem
FROM node:20-alpine

WORKDIR /app
COPY --chown=node:node . .

# Create writable directories for required paths
RUN mkdir -p /tmp/app && chown node:node /tmp/app

USER node

ENV TMPDIR=/tmp/app

# Run with --read-only flag
CMD ["node", "server.js"]
```

```yaml
# docker-compose.yml
services:
  app:
    image: my-app
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
```

### Secrets Management

```dockerfile
# BAD: Secrets in image
ENV DATABASE_PASSWORD=secret123

# GOOD: Use build secrets (BuildKit)
# syntax=docker/dockerfile:1.4
RUN --mount=type=secret,id=db_password \
    cat /run/secrets/db_password > /app/.env

# Build with: docker build --secret id=db_password,src=./password.txt .
```

```dockerfile
# GOOD: Runtime secrets via environment
FROM node:20-alpine
WORKDIR /app
COPY . .
# Password injected at runtime, not build time
CMD ["node", "server.js"]
```

### Vulnerability Scanning

```dockerfile
# Add scanning to CI/CD
# GitHub Actions example
- name: Build image
  run: docker build -t my-app .

- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'my-app'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'

- name: Upload Trivy scan results
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: 'trivy-results.sarif'
```

## Health Checks

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY . .
RUN npm ci --only=production

# Add health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node healthcheck.js || exit 1

CMD ["node", "server.js"]
```

```javascript
// healthcheck.js
const http = require('http');

const options = {
  hostname: 'localhost',
  port: process.env.PORT || 3000,
  path: '/health',
  timeout: 2000,
};

const request = http.request(options, (res) => {
  process.exit(res.statusCode === 200 ? 0 : 1);
});

request.on('error', () => process.exit(1));
request.end();
```

## Optimized Dockerfiles by Framework

### Next.js Production

```dockerfile
# Next.js optimized Dockerfile
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### FastAPI Production

```dockerfile
# FastAPI optimized Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home appuser

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Spring Boot Production

```dockerfile
# Spring Boot with layered JARs
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /app
COPY . .
RUN ./gradlew build -x test

# Extract layers
FROM eclipse-temurin:21-jdk AS extractor
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar
RUN java -Djarmode=layertools -jar app.jar extract

FROM eclipse-temurin:21-jre
WORKDIR /app

RUN useradd --create-home appuser

COPY --from=extractor /app/dependencies/ ./
COPY --from=extractor /app/spring-boot-loader/ ./
COPY --from=extractor /app/snapshot-dependencies/ ./
COPY --from=extractor /app/application/ ./

USER appuser

EXPOSE 8080

ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

## Docker Compose for Development

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: development  # Multi-stage target
    volumes:
      - .:/app
      - /app/node_modules  # Prevent overwriting
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://user:pass@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: myapp
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d myapp"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

```dockerfile
# Dockerfile with development target
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./

FROM base AS development
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]

FROM base AS production
RUN npm ci --only=production
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

## Size Comparison

```
┌─────────────────────────────────────────────────────────┐
│               Image Size Comparison                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Approach                        Size      Build Time   │
│  ───────────────────────────────────────────────────    │
│  node:20                         1.1 GB    3m 45s       │
│  node:20-slim                    250 MB    2m 30s       │
│  node:20-alpine                  175 MB    2m 15s       │
│  Multi-stage + alpine            85 MB     2m 45s       │
│  Multi-stage + distroless        50 MB     3m 00s       │
│  Go + scratch                    12 MB     1m 30s       │
│  Rust + scratch                  8 MB      2m 00s       │
│                                                          │
│  Savings: 95% reduction possible with optimization      │
└─────────────────────────────────────────────────────────┘
```

## Build Commands

```bash
# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1

# Build with cache
docker build \
  --cache-from=my-app:latest \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t my-app:latest .

# Multi-platform build
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push \
  -t my-registry/my-app:latest .

# Build with secrets
docker build \
  --secret id=npmrc,src=$HOME/.npmrc \
  -t my-app .

# Build specific stage
docker build --target development -t my-app:dev .
```

## Example Configuration

```yaml
# infera.yaml - Docker configuration
name: my-app
provider: gcp

docker:
  base_image: node:20-alpine
  multi_stage: true
  distroless: false

  optimization:
    layer_caching: true
    buildkit: true
    cache_mounts: true

  security:
    non_root_user: true
    read_only_filesystem: false
    vulnerability_scanning: true

  health_check:
    endpoint: /health
    interval: 30s
    timeout: 3s

  platforms:
    - linux/amd64
    - linux/arm64
```

## Sources

- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [BuildKit](https://docs.docker.com/build/buildkit/)
- [Distroless Images](https://github.com/GoogleContainerTools/distroless)
- [Trivy Scanner](https://aquasecurity.github.io/trivy/)
- [Docker Security](https://docs.docker.com/engine/security/)
