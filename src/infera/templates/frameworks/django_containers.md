# Django Containers (Cloud Run / ECS)

## Overview

Deploy Django applications on container platforms for production-grade deployments with full control over the runtime environment. Django's "batteries included" philosophy combined with containerization provides a robust foundation for complex web applications with ORM, admin, authentication, and more.

## Detection Signals

Use this template when:
- `manage.py` exists
- `settings.py` with Django imports
- `requirements.txt` or `pyproject.toml` contains `django`
- `wsgi.py` or `asgi.py` present
- Full-featured web application
- Admin interface needed
- Complex ORM queries
- Session management required

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Container Platform                            │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Load Balancer + CDN                     │   │
                    │   │           (Cloud Load Balancer / CloudFront + ALB)       │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Container Service                           │   │
                    │   │           (Cloud Run / ECS Fargate)                      │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │  Django   │ │  Django   │ │  Django   │             │   │
                    │   │  │ Container │ │ Container │ │ Container │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │ Gunicorn  │ │ Gunicorn  │ │ Gunicorn  │             │   │
                    │   │  │ +Workers  │ │ +Workers  │ │ +Workers  │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 2-20 instances based on CPU/requests    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │  Database │     │   Cache   │     │  Storage  │            │
                    │   │(Cloud SQL/│     │  (Redis)  │     │ (GCS/S3)  │            │
                    │   │   RDS)    │     │           │     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Production-ready • Admin interface • Full ORM support        │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 2 vCPU, 2GB RAM |
| Cloud SQL | PostgreSQL | db-custom-1-3840 |
| Memorystore | Redis cache | 1GB |
| Cloud Storage | Static/media files | Regional |
| Secret Manager | Django secrets | Auto-mount |
| Cloud CDN | Static file caching | Global |

### AWS (ECS Fargate)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Fargate | Container hosting | 1 vCPU, 2GB |
| RDS PostgreSQL | Database | db.t3.small |
| ElastiCache | Redis cache | cache.t3.micro |
| S3 | Static/media files | Standard |
| Secrets Manager | Django secrets | ECS integration |
| CloudFront | CDN | Global |

## Configuration

### Project Structure
```
my-django-app/
├── config/                   # Project configuration
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py          # Common settings
│   │   ├── development.py   # Dev settings
│   │   └── production.py    # Prod settings
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/                     # Django apps
│   ├── users/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── serializers.py
│   └── core/
│       └── ...
├── templates/
├── static/
├── media/
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── Dockerfile
├── docker-compose.yml
└── terraform/
    └── main.tf
```

### Base Settings
```python
# config/settings/base.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Apps
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_filters',
    'storages',
    'health_check',
    'health_check.db',
    'health_check.cache',
]

LOCAL_APPS = [
    'apps.users',
    'apps.core',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Auth
AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# i18n
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}
```

### Production Settings
```python
# config/settings/production.py
import os
from .base import *

DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'app'),
        'USER': os.environ.get('DB_USER', 'app'),
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# For Cloud SQL with Unix socket
if os.environ.get('CLOUD_SQL_CONNECTION_NAME'):
    DATABASES['default']['HOST'] = f"/cloudsql/{os.environ['CLOUD_SQL_CONNECTION_NAME']}"

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# Session
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Static files with WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files with Cloud Storage
if os.environ.get('GCS_BUCKET_NAME'):
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = os.environ['GCS_BUCKET_NAME']
    GS_DEFAULT_ACL = 'publicRead'
    GS_QUERYSTRING_AUTH = False
elif os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION', 'us-east-1')
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### URL Configuration
```python
# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.users.urls')),
    path('health/', include('health_check.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

### Custom User Model
```python
# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email
```

### API Views
```python
# apps/users/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserCreateSerializer

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def update_me(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

### Dockerfile
```dockerfile
# Multi-stage build for smaller image
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/production.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r production.txt

# Production image
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system django && adduser --system --group django

# Install Python packages
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application
COPY --chown=django:django . .

# Collect static files
RUN python manage.py collectstatic --noinput --settings=config.settings.production

USER django

EXPOSE 8000

# Gunicorn with optimal settings
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "4", \
     "--worker-class", "gthread", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output", \
     "--enable-stdio-inheritance"]
```

### Production Requirements
```
# requirements/production.txt
-r base.txt

# Production server
gunicorn>=21.0.0

# Database
psycopg2-binary>=2.9.0

# Cache
redis>=5.0.0
django-redis>=5.4.0

# Storage
django-storages[google,boto3]>=1.14.0
google-cloud-storage>=2.14.0
boto3>=1.34.0

# Static files
whitenoise>=6.6.0

# Logging
python-json-logger>=2.0.0

# Health checks
django-health-check>=3.17.0
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
variable "project_name" { default = "django-app" }

# Cloud Run
resource "google_cloud_run_v2_service" "main" {
  name     = var.project_name
  location = var.region

  template {
    scaling {
      min_instance_count = 2
      max_instance_count = 20
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/web:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        cpu_idle = false  # Keep warm for Django
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "DJANGO_SETTINGS_MODULE"
        value = "config.settings.production"
      }

      env {
        name  = "ALLOWED_HOSTS"
        value = "${var.project_name}-${google_cloud_run_v2_service.main.location}-run.app,${var.custom_domain}"
      }

      env {
        name  = "CLOUD_SQL_CONNECTION_NAME"
        value = google_sql_database_instance.main.connection_name
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.media.name
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
      }

      env {
        name = "DJANGO_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.django_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/health/"
          port = 8000
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health/"
          port = 8000
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
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

# Cloud SQL PostgreSQL
resource "google_sql_database_instance" "main" {
  name             = "${var.project_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-custom-1-3840"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  deletion_protection = true
}

# Redis
resource "google_redis_instance" "main" {
  name           = "${var.project_name}-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = var.region

  authorized_network = google_compute_network.main.id
}

# Media bucket
resource "google_storage_bucket" "media" {
  name     = "${var.project_id}-${var.project_name}-media"
  location = var.region

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# VPC
resource "google_compute_network" "main" {
  name                    = "${var.project_name}-vpc"
  auto_create_subnetworks = true
}

resource "google_vpc_access_connector" "main" {
  name          = "${var.project_name}-connector"
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"
}

# Secrets
resource "google_secret_manager_secret" "django_secret" {
  secret_id = "${var.project_name}-django-secret"
  replication { auto {} }
}

resource "google_secret_manager_secret_version" "django_secret" {
  secret      = google_secret_manager_secret.django_secret.id
  secret_data = random_password.django_secret.result
}

resource "random_password" "django_secret" {
  length  = 64
  special = true
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.project_name}-db-password"
  replication { auto {} }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

resource "random_password" "db" {
  length  = 32
  special = false
}

output "url" {
  value = google_cloud_run_v2_service.main.uri
}
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest

# Deploy
gcloud run deploy ${APP_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 2 \
  --max-instances 20 \
  --memory 2Gi \
  --cpu 2 \
  --add-cloudsql-instances ${PROJECT_ID}:${REGION}:${DB_INSTANCE}

# Run migrations
gcloud run jobs create migrate \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest \
  --region ${REGION} \
  --execute-now \
  -- python manage.py migrate --settings=config.settings.production

# Create superuser
gcloud run jobs create createsuperuser \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest \
  --region ${REGION} \
  -- python manage.py createsuperuser --noinput \
     --username admin --email admin@example.com

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (2 instances min) | ~$50 |
| Cloud SQL (1 vCPU, 3.75GB) | ~$50 |
| Memorystore Redis (1GB) | ~$35 |
| Cloud Storage | ~$5 |
| **Total** | **~$140** |

## Best Practices

1. **Use WhiteNoise** - Serve static files efficiently
2. **Configure connection pooling** - Use CONN_MAX_AGE
3. **Use Redis for cache/sessions** - Faster than database
4. **Proper logging** - JSON format for cloud platforms
5. **Health checks** - Use django-health-check
6. **Media files in cloud storage** - Don't store locally
7. **Run migrations in jobs** - Not during deployment
8. **Use Gunicorn gthread** - Better for I/O bound workloads

## Common Mistakes

1. **DEBUG=True in production** - Security vulnerability
2. **SQLite in production** - Use PostgreSQL
3. **No static file handling** - Configure WhiteNoise
4. **Missing ALLOWED_HOSTS** - Required for security
5. **No connection pooling** - Causes connection exhaustion
6. **Running migrations in CMD** - Causes deployment delays
7. **Storing media locally** - Lost on container restart
8. **No health check** - Load balancer can't verify health

## Example Configuration

```yaml
# infera.yaml
project_name: my-django-app
provider: gcp

framework:
  name: django
  version: "5.0"

deployment:
  type: container
  runtime: python312

  resources:
    cpu: 2
    memory: 2Gi

  scaling:
    min_instances: 2
    max_instances: 20
    target_cpu: 70

  health_check:
    path: /health/
    interval: 30s

database:
  type: postgresql
  version: "15"
  tier: db-custom-1-3840

cache:
  type: redis
  size: 1gb

storage:
  type: gcs
  bucket: media

env_vars:
  DJANGO_SETTINGS_MODULE: config.settings.production
  ALLOWED_HOSTS: myapp.com

secrets:
  - DJANGO_SECRET_KEY
  - DB_PASSWORD
```

## Sources

- [Django Documentation](https://docs.djangoproject.com/)
- [Cloud Run Django Tutorial](https://cloud.google.com/python/django/run)
- [Django Production Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [WhiteNoise Documentation](http://whitenoise.evans.io/)
