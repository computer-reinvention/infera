# FastAPI Serverless (Cloud Run / Lambda)

## Overview

Deploy FastAPI applications on serverless platforms for automatic scaling, cost efficiency, and minimal operational overhead. FastAPI's async-first design and automatic OpenAPI documentation make it ideal for modern APIs. Supports both GCP Cloud Run and AWS Lambda deployments.

## Detection Signals

Use this template when:
- `main.py` or `app.py` with FastAPI imports
- `requirements.txt` or `pyproject.toml` contains `fastapi`
- `uvicorn` or `gunicorn` in dependencies
- API-focused Python application
- OpenAPI/Swagger documentation needed
- Async operations (database, HTTP calls)
- Serverless deployment preferred

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Serverless Platform                           │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  API Gateway / Load Balancer             │   │
                    │   │              (Cloud Run URL / API Gateway)               │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Serverless Compute                          │   │
                    │   │           (Cloud Run / Lambda)                           │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │  FastAPI  │ │  FastAPI  │ │  FastAPI  │             │   │
                    │   │  │ Instance  │ │ Instance  │ │ Instance  │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │  Uvicorn  │ │  Uvicorn  │ │  Uvicorn  │             │   │
                    │   │  │  + Async  │ │  + Async  │ │  + Async  │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 0-100+ instances based on requests       │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │  Database │     │   Cache   │     │  Storage  │            │
                    │   │(Cloud SQL/│     │ (Redis/   │     │ (GCS/S3)  │            │
                    │   │   RDS)    │     │Memorystore│     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Scale to zero • Auto OpenAPI • <100ms cold start             │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 1 vCPU, 1GB RAM |
| Cloud SQL | PostgreSQL database | db-f1-micro |
| Memorystore | Redis cache | 1GB |
| Cloud Storage | File uploads | Regional |
| Secret Manager | API keys, credentials | Auto-mount |
| Artifact Registry | Container images | Docker |

### AWS (Lambda + API Gateway)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Lambda | Function compute | 1GB RAM |
| API Gateway | HTTP routing | REST or HTTP API |
| RDS Aurora | PostgreSQL Serverless | 0.5-4 ACU |
| ElastiCache | Redis cache | t3.micro |
| S3 | File storage | Standard |
| Secrets Manager | Credentials | Lambda integration |

## Configuration

### Project Structure
```
my-fastapi-app/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── database.py          # DB connection
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   └── user.py
│   ├── routers/             # API routes
│   │   ├── __init__.py
│   │   ├── users.py
│   │   └── items.py
│   ├── services/            # Business logic
│   │   └── user_service.py
│   └── middleware/          # Custom middleware
│       └── logging.py
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── terraform/
    └── main.tf
```

### FastAPI Application
```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .config import settings
from .database import engine, get_db
from .routers import users, items
from .middleware.logging import LoggingMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    yield
    # Shutdown
    print("Shutting down...")
    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="My FastAPI Application",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(LoggingMiddleware)

# Routers
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Welcome to the API", "docs": "/docs"}
```

### Configuration with Pydantic
```python
# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "My FastAPI App"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str | None = None

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Cloud Storage
    GCS_BUCKET: str | None = None
    S3_BUCKET: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### Async Database Connection
```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Convert sync URL to async
database_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Models and Schemas
```python
# app/models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# app/schemas/user.py
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserList(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    per_page: int
```

### API Router
```python
# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models.user import User
from ..schemas.user import UserCreate, UserResponse, UserList
from ..services.user_service import UserService

router = APIRouter()

@router.get("", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    # Get total count
    total = await db.scalar(select(func.count(User.id)))

    # Get paginated users
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    users = result.scalars().all()

    return UserList(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)

    # Check if user exists
    existing = await service.get_by_email(user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await service.create(user_data)
    return UserResponse.model_validate(user)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.model_validate(user)

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    deleted = await service.delete(user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
```

### Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port
EXPOSE 8080

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

### requirements.txt
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
orjson>=3.9.0
httpx>=0.26.0
redis>=5.0.0
python-multipart>=0.0.6
```

### GCP Terraform
```hcl
# terraform/main.tf
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {}
variable "region" { default = "us-central1" }
variable "project_name" { default = "fastapi-app" }

# Artifact Registry
resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = var.project_name
  format        = "DOCKER"
}

# Cloud Run
resource "google_cloud_run_v2_service" "main" {
  name     = var.project_name
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/api:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 30
        timeout_seconds   = 3
        failure_threshold = 3
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Public access
resource "google_cloud_run_service_iam_member" "public" {
  location = google_cloud_run_v2_service.main.location
  service  = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# VPC Connector
resource "google_vpc_access_connector" "main" {
  name          = "${var.project_name}-connector"
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"
}

# Cloud SQL
resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = "projects/${var.project_id}/global/networks/default"
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "main" {
  name     = "app"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = "app"
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}

resource "random_password" "db" {
  length  = 32
  special = false
}

# Secrets
resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.project_name}-database-url"
  replication { auto {} }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.main.name}:${random_password.db.result}@/app?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
}

resource "google_secret_manager_secret" "secret_key" {
  secret_id = "${var.project_name}-secret-key"
  replication { auto {} }
}

resource "google_secret_manager_secret_version" "secret_key" {
  secret      = google_secret_manager_secret.secret_key.id
  secret_data = random_password.secret_key.result
}

resource "random_password" "secret_key" {
  length  = 64
  special = true
}

output "url" {
  value = google_cloud_run_v2_service.main.uri
}
```

### AWS Lambda Handler (Mangum)
```python
# app/lambda_handler.py
from mangum import Mangum
from .main import app

# Lambda handler using Mangum adapter
handler = Mangum(app, lifespan="off")
```

### AWS SAM Template
```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    MemorySize: 1024
    Runtime: python3.12
    Environment:
      Variables:
        ENVIRONMENT: production
        DATABASE_URL: !Sub '{{resolve:secretsmanager:${DatabaseSecret}:SecretString:url}}'

Resources:
  FastAPIFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: app.lambda_handler.handler
      CodeUri: .
      Events:
        Api:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /{proxy+}
            Method: ANY
        Root:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /
            Method: ANY
      VpcConfig:
        SubnetIds:
          - !Ref PrivateSubnet1
          - !Ref PrivateSubnet2
        SecurityGroupIds:
          - !Ref LambdaSecurityGroup

  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: prod
      CorsConfiguration:
        AllowOrigins:
          - "*"
        AllowMethods:
          - GET
          - POST
          - PUT
          - DELETE
          - OPTIONS

Outputs:
  ApiUrl:
    Value: !Sub "https://${HttpApi}.execute-api.${AWS::Region}.amazonaws.com/prod"
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/api:latest

# Deploy
gcloud run deploy ${APP_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/api:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 100 \
  --memory 1Gi \
  --cpu 1

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100

# Run migrations
gcloud run jobs execute migrate --region ${REGION}
```

### AWS Lambda
```bash
# Deploy with SAM
sam build
sam deploy --guided

# View logs
sam logs -n FastAPIFunction --tail

# Local testing
sam local start-api
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (scale to zero) | ~$0-50 |
| Cloud SQL (db-f1-micro) | ~$10 |
| Secrets | ~$0.50 |
| **Total** | **~$10-60** |

### AWS Lambda
| Component | Monthly Cost |
|-----------|--------------|
| Lambda (1M requests) | ~$20 |
| API Gateway | ~$3.50 |
| RDS Serverless | ~$25 |
| **Total** | **~$50** |

## Best Practices

1. **Use async throughout** - FastAPI + asyncpg for best performance
2. **Connection pooling** - Configure SQLAlchemy pool properly
3. **Pydantic validation** - Type-safe request/response
4. **Dependency injection** - Use Depends for shared resources
5. **Health checks** - Always expose /health endpoint
6. **Structured logging** - JSON logs for cloud platforms
7. **OpenAPI docs** - Auto-generated, always available
8. **Environment config** - Use pydantic-settings

## Common Mistakes

1. **Sync database calls** - Use asyncpg, not psycopg2
2. **No connection pooling** - Serverless needs proper pool config
3. **Missing lifespan** - Cleanup connections on shutdown
4. **Large cold starts** - Minimize imports, use lazy loading
5. **No health check** - Required for load balancer health
6. **Hardcoded secrets** - Use Secret Manager / Secrets Manager
7. **Missing CORS** - Configure for frontend access
8. **No request validation** - Always use Pydantic schemas

## Example Configuration

```yaml
# infera.yaml
project_name: my-fastapi-app
provider: gcp  # or aws

framework:
  name: fastapi
  version: "0.109"

deployment:
  type: serverless
  runtime: python312

  resources:
    memory: 1Gi
    cpu: 1

  scaling:
    min_instances: 0
    max_instances: 100
    concurrency: 80

  health_check:
    path: /health
    interval: 30s

database:
  type: postgresql
  version: "15"
  tier: serverless

env_vars:
  ENVIRONMENT: production
  CORS_ORIGINS: '["https://myapp.com"]'

secrets:
  - DATABASE_URL
  - SECRET_KEY
```

## Sources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloud Run Python](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/python)
- [AWS Lambda Python](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [Mangum - AWS Lambda Adapter](https://mangum.io/)
