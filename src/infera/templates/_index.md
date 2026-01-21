# Template Selection Guide

Use this guide to select the appropriate infrastructure template based on codebase analysis, provider selection, and architecture requirements.

## Template Repository Overview

**Total Templates: 83**

| Category | Count | Directory |
|----------|-------|-----------|
| GCP-Specific | 15 | `gcp/` |
| AWS-Specific | 15 | `aws/` |
| Cloudflare-Specific | 10 | `cloudflare/` |
| Framework-Specific | 15 | `frameworks/` |
| Database Patterns | 8 | `databases/` |
| Specialized Architectures | 10 | `specialized/` |
| Cost Optimization | 5 | `cost/` |
| DevOps & CI/CD | 5 | `devops/` |

---

## Quick Selection Matrix

### By Provider

| Provider | Primary Templates | Best For |
|----------|-------------------|----------|
| **GCP** | `gcp/*.md` | Full-featured cloud, Cloud Run, GKE, Cloud SQL |
| **AWS** | `aws/*.md` | Lambda, ECS, EKS, enterprise workloads |
| **Cloudflare** | `cloudflare/*.md` | Edge computing, static sites, global distribution |

### By Architecture Type

| Architecture | GCP Template | AWS Template | Cloudflare Template |
|--------------|--------------|--------------|---------------------|
| Static Site | `gcp/static_site_cdn.md` | `aws/s3_cloudfront.md` | `cloudflare/pages_static.md` |
| API Service | `gcp/cloud_run_api.md` | `aws/lambda_api.md` | `cloudflare/workers_api.md` |
| Full-Stack App | `gcp/cloud_run_fullstack.md` | `aws/ecs_fargate_fullstack.md` | `cloudflare/full_stack.md` |
| Containerized | `gcp/cloud_run_api.md` | `aws/ecs_fargate_api.md` | N/A (use GCP/AWS) |
| Microservices | `gcp/gke_microservices.md` | `aws/eks_microservices.md` | N/A |
| ML/AI | `gcp/gke_ml_serving.md` | `aws/eks_ml_serving.md` | `cloudflare/workers_ai.md` |

---

## Decision Tree

### Step 1: Provider Selection

```
What cloud provider?
├── GCP → Go to GCP Decision Tree
├── AWS → Go to AWS Decision Tree
├── Cloudflare → Go to Cloudflare Decision Tree
└── Multi-cloud → Select primary, reference others
```

### Step 2: Framework Detection

Check for framework-specific templates first:

| Framework | Detection | Recommended Template |
|-----------|-----------|---------------------|
| Next.js | `next.config.js`, `"next":` in package.json | `frameworks/nextjs_selfhosted.md` or `frameworks/nextjs_vercel.md` |
| Nuxt | `nuxt.config.ts`, `"nuxt":` | `frameworks/nuxt_cloudflare.md` |
| Remix | `remix.config.js` | `frameworks/remix_cloudflare.md` |
| SvelteKit | `svelte.config.js` | `frameworks/sveltekit_vercel.md` |
| Astro | `astro.config.mjs` | `frameworks/astro_static.md` |
| FastAPI | `fastapi` in requirements.txt | `frameworks/fastapi_serverless.md` |
| Django | `django` in requirements.txt, `manage.py` | `frameworks/django_containers.md` |
| Rails | `Gemfile` with `rails` | `frameworks/rails_containers.md` |
| Express | `"express":` in package.json | `frameworks/express_serverless.md` |
| NestJS | `"@nestjs/core":` | `frameworks/nestjs_containers.md` |
| Spring Boot | `pom.xml` or `build.gradle` with Spring | `frameworks/spring_boot.md` |
| Go | `go.mod` | `frameworks/golang_api.md` |
| Rust | `Cargo.toml` with Axum/Actix | `frameworks/rust_api.md` |
| Phoenix/Elixir | `mix.exs` with Phoenix | `frameworks/phoenix_elixir.md` |

---

## GCP Decision Tree

```
Is there a Dockerfile?
├── Yes → Container workload
│   ├── HTTP service? → gcp/cloud_run_api.md or gcp/cloud_run_fullstack.md
│   ├── gRPC service? → gcp/cloud_run_grpc.md
│   ├── Microservices (multiple)? → gcp/gke_microservices.md
│   └── ML model serving? → gcp/gke_ml_serving.md
│
└── No → Serverless/Managed
    ├── Static site? → gcp/static_site_cdn.md
    ├── Firebase project? → gcp/firebase_fullstack.md
    ├── Event-driven? → gcp/cloud_functions_event.md
    ├── Simple API? → gcp/cloud_functions_api.md
    ├── Message queue workers? → gcp/pubsub_workers.md
    ├── Scheduled jobs? → gcp/cloud_tasks_jobs.md
    ├── Data pipeline? → gcp/dataflow_pipeline.md
    ├── Multi-region HA? → gcp/multi_region.md
    └── Full-stack app? → gcp/app_engine_standard.md
```

### GCP Templates

| Template | Use Case | Key Services |
|----------|----------|--------------|
| `gcp/cloud_run_api.md` | Serverless API | Cloud Run + Artifact Registry |
| `gcp/cloud_run_fullstack.md` | Full-stack app | Cloud Run + Cloud SQL + Storage |
| `gcp/cloud_run_grpc.md` | gRPC microservice | Cloud Run + gRPC + Load Balancer |
| `gcp/cloud_functions_api.md` | Lightweight functions | Cloud Functions + Firestore |
| `gcp/cloud_functions_event.md` | Event-driven | Cloud Functions + Pub/Sub |
| `gcp/gke_microservices.md` | Kubernetes cluster | GKE + Istio + Cloud SQL |
| `gcp/gke_ml_serving.md` | ML model serving | GKE + Vertex AI + GPUs |
| `gcp/app_engine_standard.md` | Managed PaaS | App Engine + Cloud SQL |
| `gcp/static_site_cdn.md` | Static + CDN | Cloud Storage + Cloud CDN |
| `gcp/firebase_fullstack.md` | Firebase ecosystem | Firebase Hosting + Functions + Firestore |
| `gcp/cloud_sql_ha.md` | HA database | Cloud SQL + Read Replicas + Failover |
| `gcp/pubsub_workers.md` | Message queue workers | Pub/Sub + Cloud Run |
| `gcp/cloud_tasks_jobs.md` | Background jobs | Cloud Tasks + Cloud Run |
| `gcp/dataflow_pipeline.md` | Data pipeline | Dataflow + BigQuery |
| `gcp/multi_region.md` | Multi-region HA | Global LB + Cloud Run multi-region |

---

## AWS Decision Tree

```
Is there a Dockerfile?
├── Yes → Container workload
│   ├── Simple API/web? → aws/ecs_fargate_api.md
│   ├── Full-stack? → aws/ecs_fargate_fullstack.md
│   ├── Cost-sensitive? → aws/ecs_spot.md
│   ├── Microservices? → aws/eks_microservices.md
│   └── ML serving? → aws/eks_ml_serving.md
│
└── No → Serverless
    ├── Static site? → aws/s3_cloudfront.md
    ├── Amplify project? → aws/amplify_fullstack.md
    ├── Simple API? → aws/lambda_api.md
    ├── Queue processing? → aws/lambda_sqs.md
    ├── Event-driven? → aws/eventbridge_lambda.md
    ├── Workflows? → aws/step_functions.md
    ├── Batch jobs? → aws/batch_processing.md
    ├── Multi-region? → aws/multi_region.md
    └── Traditional PaaS? → aws/elastic_beanstalk.md
```

### AWS Templates

| Template | Use Case | Key Services |
|----------|----------|--------------|
| `aws/lambda_api.md` | Serverless API | Lambda + API Gateway |
| `aws/lambda_sqs.md` | Queue processor | Lambda + SQS + DLQ |
| `aws/ecs_fargate_api.md` | Container API | ECS Fargate + ALB |
| `aws/ecs_fargate_fullstack.md` | Full-stack | ECS + RDS + S3 + CloudFront |
| `aws/ecs_spot.md` | Cost-optimized | ECS + Spot Instances |
| `aws/eks_microservices.md` | Kubernetes | EKS + ALB Ingress + RDS |
| `aws/eks_ml_serving.md` | ML inference | EKS + SageMaker + GPUs |
| `aws/elastic_beanstalk.md` | Managed PaaS | Elastic Beanstalk + RDS |
| `aws/s3_cloudfront.md` | Static site | S3 + CloudFront + ACM |
| `aws/amplify_fullstack.md` | Full-stack | Amplify + AppSync + DynamoDB |
| `aws/rds_aurora.md` | Serverless DB | Aurora Serverless v2 |
| `aws/eventbridge_lambda.md` | Event-driven | EventBridge + Lambda |
| `aws/step_functions.md` | Workflows | Step Functions + Lambda |
| `aws/batch_processing.md` | Batch jobs | AWS Batch + S3 |
| `aws/multi_region.md` | Multi-region HA | Route53 + Global Accelerator |

---

## Cloudflare Decision Tree

```
What type of application?
├── Static site
│   ├── With API routes? → cloudflare/pages_functions.md
│   └── Pure static? → cloudflare/pages_static.md
│
├── API/Backend
│   ├── Need SQL database? → cloudflare/workers_d1.md
│   ├── Need key-value storage? → cloudflare/workers_kv.md
│   ├── Need file storage? → cloudflare/workers_r2.md
│   ├── Need queues? → cloudflare/workers_queues.md
│   ├── Need stateful logic? → cloudflare/workers_durable.md
│   ├── Need AI inference? → cloudflare/workers_ai.md
│   └── Simple API? → cloudflare/workers_api.md
│
└── Full-stack edge app → cloudflare/full_stack.md
```

### Cloudflare Templates

| Template | Use Case | Key Services |
|----------|----------|--------------|
| `cloudflare/pages_static.md` | Static site | Pages + custom domain |
| `cloudflare/pages_functions.md` | Static + API | Pages + Functions |
| `cloudflare/workers_api.md` | Edge API | Workers + custom domain |
| `cloudflare/workers_d1.md` | Edge + SQL | Workers + D1 |
| `cloudflare/workers_kv.md` | Edge + KV store | Workers + KV |
| `cloudflare/workers_r2.md` | Edge + storage | Workers + R2 |
| `cloudflare/workers_queues.md` | Queue processing | Workers + Queues |
| `cloudflare/workers_durable.md` | Stateful edge | Workers + Durable Objects |
| `cloudflare/workers_ai.md` | Edge AI | Workers + Workers AI |
| `cloudflare/full_stack.md` | Complete stack | Workers + D1 + R2 + KV |

---

## Database Selection

```
What type of data?
├── Relational (SQL)
│   ├── Need serverless scaling? → databases/postgres_serverless.md
│   ├── MySQL required? → databases/mysql_managed.md or databases/planetscale.md
│   └── PostgreSQL (default) → databases/postgres_managed.md
│
├── Document (NoSQL)
│   ├── MongoDB ecosystem? → databases/mongodb_atlas.md
│   ├── GCP project? → databases/firestore.md
│   └── AWS project? → databases/dynamodb.md
│
└── Caching
    └── Redis → databases/redis_cache.md
```

### Database Templates

| Template | Database | Best For |
|----------|----------|----------|
| `databases/postgres_managed.md` | PostgreSQL | Default choice - Cloud SQL/RDS/Supabase |
| `databases/postgres_serverless.md` | PostgreSQL | Auto-scaling - Neon/Aurora Serverless |
| `databases/mysql_managed.md` | MySQL | Legacy apps - Cloud SQL/RDS |
| `databases/mongodb_atlas.md` | MongoDB | Document store - Atlas |
| `databases/redis_cache.md` | Redis | Caching - Memorystore/ElastiCache |
| `databases/dynamodb.md` | DynamoDB | Serverless NoSQL - AWS |
| `databases/firestore.md` | Firestore | Realtime NoSQL - GCP |
| `databases/planetscale.md` | PlanetScale | Serverless MySQL |

---

## Specialized Architectures

| Pattern | Template | Use Case |
|---------|----------|----------|
| WebSocket/Realtime | `specialized/websocket_realtime.md` | Chat, collaboration, live updates |
| GraphQL API | `specialized/graphql_api.md` | Flexible APIs, mobile backends |
| gRPC Microservices | `specialized/grpc_microservices.md` | High-performance internal communication |
| Cron Jobs | `specialized/cron_jobs.md` | Scheduled tasks, periodic processing |
| Queue Workers | `specialized/queue_workers.md` | Async processing, background jobs |
| ML Inference | `specialized/ml_inference.md` | Model deployment, AI APIs |
| Streaming Data | `specialized/streaming_data.md` | Real-time analytics, event processing |
| Multi-Tenant SaaS | `specialized/multi_tenant.md` | B2B SaaS applications |
| JAMstack | `specialized/jamstack.md` | Headless CMS + static sites |
| Monorepo | `specialized/monorepo.md` | Multiple services in one repo |

---

## Cost Optimization

| Pattern | Template | Savings |
|---------|----------|---------|
| Free Tier Strategy | `cost/free_tier_maximization.md` | $0/month for low traffic |
| Serverless vs Containers | `cost/serverless_vs_containers.md` | 30-50% based on workload |
| Spot/Preemptible Instances | `cost/spot_preemptible.md` | 60-90% on compute |
| Reserved Capacity | `cost/reserved_capacity.md` | 30-70% on committed use |
| Cold Start Optimization | `cost/cold_start_optimization.md` | Better latency + cost |

---

## DevOps & CI/CD

| Pattern | Template | Use Case |
|---------|----------|----------|
| GitHub Actions | `devops/github_actions.md` | GitHub-hosted CI/CD |
| GitLab CI | `devops/gitlab_ci.md` | GitLab-hosted CI/CD |
| Cloud Build | `devops/cloud_build.md` | GCP-native CI/CD |
| Terraform Modules | `devops/terraform_modules.md` | IaC patterns and modules |
| Docker Best Practices | `devops/docker_best_practices.md` | Container optimization |

---

## Detection Signals Reference

### Frontend Frameworks

| Framework | Detection Files | Key Patterns |
|-----------|----------------|--------------|
| React | package.json | `"react":`, `"react-dom":` |
| Vue | package.json, vue.config.js | `"vue":` |
| Angular | package.json, angular.json | `"@angular/core":` |
| Next.js | next.config.js | `"next":` |
| Nuxt | nuxt.config.ts | `"nuxt":` |
| SvelteKit | svelte.config.js | `"@sveltejs/kit":` |
| Astro | astro.config.mjs | `"astro":` |
| Remix | remix.config.js | `"@remix-run":` |

### Backend Frameworks

| Framework | Detection Files | Key Patterns |
|-----------|----------------|--------------|
| FastAPI | requirements.txt, pyproject.toml | `fastapi` |
| Flask | requirements.txt | `flask` |
| Django | requirements.txt, manage.py | `django` |
| Express | package.json | `"express":` |
| NestJS | package.json | `"@nestjs/core":` |
| Spring Boot | pom.xml, build.gradle | `spring-boot` |
| Go (Gin/Echo) | go.mod | `gin-gonic`, `labstack/echo` |
| Rust (Axum) | Cargo.toml | `axum`, `actix-web` |
| Rails | Gemfile | `rails` |
| Phoenix | mix.exs | `phoenix` |

### Database Signals

| Database | Detection Patterns |
|----------|-------------------|
| PostgreSQL | `psycopg2`, `asyncpg`, `pg`, `prisma` + PostgreSQL |
| MySQL | `pymysql`, `mysql2`, `mysql-connector` |
| MongoDB | `pymongo`, `mongoose`, `mongodb` |
| Redis | `redis`, `ioredis`, `aioredis` |
| SQLite | `sqlite3`, `better-sqlite3`, `libsql` |
| DynamoDB | `@aws-sdk/client-dynamodb`, `boto3` + DynamoDB |
| Firestore | `@google-cloud/firestore`, `firebase-admin` |

### Containerization Signals

| Signal | Files | Patterns |
|--------|-------|----------|
| Docker | Dockerfile | `FROM ` |
| Docker Compose | docker-compose.yml | `services:` |
| Kubernetes | k8s/, *.yaml | `kind: Deployment` |
| Helm | Chart.yaml | `apiVersion: v2` |

### Cloudflare-Specific

| Signal | Files | Patterns |
|--------|-------|----------|
| Wrangler Config | wrangler.toml | `name =`, `main =` |
| Worker Code | src/index.ts | `export default {`, `fetch(` |
| Pages Functions | functions/ | `onRequest` |
| D1 Usage | wrangler.toml | `[[d1_databases]]` |
| KV Usage | wrangler.toml | `[[kv_namespaces]]` |
| R2 Usage | wrangler.toml | `[[r2_buckets]]` |
| Durable Objects | wrangler.toml | `[[durable_objects]]` |

---

## Cost Comparison Quick Reference

| Workload | GCP (monthly) | AWS (monthly) | Cloudflare (monthly) |
|----------|---------------|---------------|----------------------|
| Static site (1M views) | $1-5 | $1-5 | $0 (free tier) |
| API (1M requests) | $5-20 | $5-25 | $0-5 |
| Full-stack (moderate) | $50-150 | $50-200 | $25-75 |
| Microservices (production) | $200-500 | $200-600 | N/A |
| Database (PostgreSQL) | $25-100 | $25-150 | N/A (use Neon) |

---

## Template Combination Examples

### 1. Next.js + PostgreSQL + Redis

```yaml
templates:
  - frameworks/nextjs_selfhosted.md  # App deployment
  - databases/postgres_managed.md    # Primary database
  - databases/redis_cache.md         # Session/cache
```

### 2. FastAPI Microservices

```yaml
templates:
  - frameworks/fastapi_serverless.md     # API services
  - specialized/grpc_microservices.md    # Internal communication
  - specialized/queue_workers.md         # Background processing
  - databases/postgres_managed.md        # Database
```

### 3. JAMstack with CMS

```yaml
templates:
  - specialized/jamstack.md              # Architecture overview
  - cloudflare/pages_static.md           # Hosting
  - cloudflare/workers_kv.md             # Edge caching
```

### 4. Multi-tenant SaaS

```yaml
templates:
  - specialized/multi_tenant.md          # Architecture
  - gcp/cloud_run_fullstack.md           # Application
  - databases/postgres_managed.md        # Per-tenant schemas
  - databases/redis_cache.md             # Rate limiting
```

### 5. ML Model Serving

```yaml
templates:
  - specialized/ml_inference.md          # Architecture
  - gcp/gke_ml_serving.md                # GPU cluster
  - specialized/queue_workers.md         # Batch inference
```
