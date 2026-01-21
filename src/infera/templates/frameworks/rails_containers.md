# Rails Containers (Cloud Run / Fly.io)

## Overview

Deploy Ruby on Rails applications on container platforms for production-grade deployments. Rails' convention-over-configuration approach combined with modern containerization provides a robust foundation for web applications. Supports Cloud Run, ECS, and Fly.io deployments.

## Detection Signals

Use this template when:
- `Gemfile` with `rails` gem
- `config/application.rb` exists
- `config/routes.rb` present
- `app/controllers/` directory structure
- Full-featured web application
- ActiveRecord ORM
- Asset pipeline or Webpacker/Propshaft
- ActionCable for WebSockets (optional)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Container Platform                            │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Load Balancer / Edge                    │   │
                    │   │              (Cloud LB / Fly Edge / ALB)                  │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Container Service                           │   │
                    │   │       (Cloud Run / Fly Machines / ECS Fargate)           │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │   Rails   │ │   Rails   │ │  Sidekiq  │             │   │
                    │   │  │    Web    │ │    Web    │ │  Worker   │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │   Puma    │ │   Puma    │ │  Async    │             │   │
                    │   │  │ +Threads  │ │ +Threads  │ │   Jobs    │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 2-10 instances based on requests         │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │ PostgreSQL│     │   Redis   │     │  Storage  │            │
                    │   │ (Managed) │     │  (Cache + │     │ (GCS/S3)  │            │
                    │   │           │     │   Jobs)   │     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Convention over configuration • Full-stack • Background jobs │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run (web) | Rails application | 2 vCPU, 2GB RAM |
| Cloud Run (worker) | Sidekiq jobs | 1 vCPU, 1GB RAM |
| Cloud SQL | PostgreSQL | db-custom-1-3840 |
| Memorystore | Redis | 1GB |
| Cloud Storage | ActiveStorage | Regional |
| Secret Manager | Credentials | Auto-mount |

### Fly.io
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Fly Machines (web) | Rails application | shared-cpu-2x |
| Fly Machines (worker) | Sidekiq | shared-cpu-1x |
| Fly Postgres | Database | 1GB RAM |
| Upstash Redis | Cache + jobs | 100MB |
| Tigris | Object storage | S3-compatible |

## Configuration

### Gemfile (Production)
```ruby
source 'https://rubygems.org'

ruby '3.3.0'

gem 'rails', '~> 7.1.0'

# Database
gem 'pg', '~> 1.5'

# Server
gem 'puma', '~> 6.0'

# Assets
gem 'propshaft'
gem 'importmap-rails'
gem 'turbo-rails'
gem 'stimulus-rails'
gem 'tailwindcss-rails'

# Background jobs
gem 'sidekiq', '~> 7.0'

# Storage
gem 'aws-sdk-s3', require: false
gem 'google-cloud-storage', require: false

# Cache
gem 'redis', '~> 5.0'
gem 'hiredis'

# Performance
gem 'bootsnap', require: false
gem 'oj'

# Security
gem 'bcrypt', '~> 3.1'
gem 'rack-attack'

# Monitoring
gem 'lograge'

group :production do
  gem 'rails_12factor'
end
```

### Production Configuration
```ruby
# config/environments/production.rb
Rails.application.configure do
  config.cache_classes = true
  config.eager_load = true
  config.consider_all_requests_local = false
  config.action_controller.perform_caching = true

  # Force SSL
  config.force_ssl = true
  config.ssl_options = { redirect: { exclude: ->(request) { request.path == '/health' } } }

  # Serve static files
  config.public_file_server.enabled = ENV['RAILS_SERVE_STATIC_FILES'].present? || true
  config.public_file_server.headers = {
    'Cache-Control' => 'public, max-age=31536000'
  }

  # Assets
  config.assets.compile = false
  config.assets.digest = true

  # Active Storage
  config.active_storage.service = ENV.fetch('STORAGE_SERVICE', 'local').to_sym

  # Cache
  config.cache_store = :redis_cache_store, {
    url: ENV['REDIS_URL'],
    pool_size: ENV.fetch('RAILS_MAX_THREADS', 5).to_i,
    pool_timeout: 5
  }

  # Session
  config.session_store :cookie_store,
    key: '_app_session',
    secure: true,
    same_site: :lax

  # Action Cable
  config.action_cable.mount_path = '/cable'
  config.action_cable.url = ENV['ACTION_CABLE_URL']
  config.action_cable.allowed_request_origins = [ENV['APP_URL']]

  # Active Job
  config.active_job.queue_adapter = :sidekiq

  # Logging
  config.log_level = :info
  config.log_tags = [:request_id]
  config.lograge.enabled = true
  config.lograge.formatter = Lograge::Formatters::Json.new

  # Mailer
  config.action_mailer.delivery_method = :smtp
  config.action_mailer.smtp_settings = {
    address: ENV['SMTP_ADDRESS'],
    port: ENV.fetch('SMTP_PORT', 587).to_i,
    user_name: ENV['SMTP_USERNAME'],
    password: ENV['SMTP_PASSWORD'],
    authentication: :plain,
    enable_starttls_auto: true
  }
  config.action_mailer.default_url_options = { host: ENV['APP_URL'] }

  # Performance
  config.i18n.fallbacks = true
  config.active_support.deprecation = :notify
  config.active_record.dump_schema_after_migration = false
end
```

### Database Configuration
```yaml
# config/database.yml
default: &default
  adapter: postgresql
  encoding: unicode
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>

development:
  <<: *default
  database: app_development

test:
  <<: *default
  database: app_test

production:
  <<: *default
  url: <%= ENV['DATABASE_URL'] %>
  # Cloud SQL socket connection
  <% if ENV['CLOUD_SQL_CONNECTION_NAME'] %>
  host: /cloudsql/<%= ENV['CLOUD_SQL_CONNECTION_NAME'] %>
  <% end %>
```

### Storage Configuration
```yaml
# config/storage.yml
local:
  service: Disk
  root: <%= Rails.root.join("storage") %>

google:
  service: GCS
  project: <%= ENV['GCP_PROJECT_ID'] %>
  credentials: <%= ENV['GCP_CREDENTIALS'] %>
  bucket: <%= ENV['GCS_BUCKET'] %>

amazon:
  service: S3
  access_key_id: <%= ENV['AWS_ACCESS_KEY_ID'] %>
  secret_access_key: <%= ENV['AWS_SECRET_ACCESS_KEY'] %>
  region: <%= ENV['AWS_REGION'] %>
  bucket: <%= ENV['S3_BUCKET'] %>
```

### Sidekiq Configuration
```ruby
# config/sidekiq.yml
:concurrency: <%= ENV.fetch('SIDEKIQ_CONCURRENCY', 5) %>
:queues:
  - [critical, 3]
  - [default, 2]
  - [low, 1]

# config/initializers/sidekiq.rb
Sidekiq.configure_server do |config|
  config.redis = { url: ENV['REDIS_URL'], network_timeout: 5 }
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV['REDIS_URL'], network_timeout: 5 }
end
```

### Health Check
```ruby
# app/controllers/health_controller.rb
class HealthController < ApplicationController
  skip_before_action :authenticate_user!, if: -> { defined?(authenticate_user!) }

  def show
    checks = {
      database: database_healthy?,
      redis: redis_healthy?,
      sidekiq: sidekiq_healthy?
    }

    status = checks.values.all? ? :ok : :service_unavailable

    render json: {
      status: status == :ok ? 'healthy' : 'unhealthy',
      checks: checks,
      version: ENV.fetch('GIT_SHA', 'unknown')
    }, status: status
  end

  private

  def database_healthy?
    ActiveRecord::Base.connection.execute('SELECT 1')
    true
  rescue StandardError
    false
  end

  def redis_healthy?
    Redis.new(url: ENV['REDIS_URL']).ping == 'PONG'
  rescue StandardError
    false
  end

  def sidekiq_healthy?
    Sidekiq::ProcessSet.new.size > 0
  rescue StandardError
    true # Don't fail if Sidekiq not needed
  end
end

# config/routes.rb
Rails.application.routes.draw do
  get '/health', to: 'health#show'
end
```

### Dockerfile
```dockerfile
# syntax=docker/dockerfile:1
ARG RUBY_VERSION=3.3.0
FROM ruby:$RUBY_VERSION-slim as base

WORKDIR /rails

# Set production environment
ENV RAILS_ENV="production" \
    BUNDLE_DEPLOYMENT="1" \
    BUNDLE_PATH="/usr/local/bundle" \
    BUNDLE_WITHOUT="development:test"

# Build stage
FROM base as build

# Install build dependencies
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    build-essential \
    git \
    libpq-dev \
    node-gyp \
    pkg-config \
    python-is-python3 && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install gems
COPY Gemfile Gemfile.lock ./
RUN bundle install && \
    rm -rf ~/.bundle/ "${BUNDLE_PATH}"/ruby/*/cache "${BUNDLE_PATH}"/ruby/*/bundler/gems/*/.git

# Install JavaScript dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application code
COPY . .

# Precompile assets
RUN SECRET_KEY_BASE_DUMMY=1 ./bin/rails assets:precompile

# Production stage
FROM base

# Install runtime dependencies
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    curl \
    libpq5 \
    postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Copy built artifacts
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --from=build /rails /rails

# Create non-root user
RUN useradd rails --create-home --shell /bin/bash && \
    chown -R rails:rails db log storage tmp
USER rails:rails

# Entrypoint
ENTRYPOINT ["/rails/bin/docker-entrypoint"]

EXPOSE 3000
CMD ["./bin/rails", "server", "-b", "0.0.0.0"]
```

### Docker Entrypoint
```bash
#!/bin/bash -e
# bin/docker-entrypoint

# Run migrations if this is the first instance
if [ "${MIGRATE_ON_BOOT:-false}" = "true" ]; then
  echo "Running database migrations..."
  ./bin/rails db:migrate
fi

# Execute the command
exec "${@}"
```

### Fly.io Configuration
```toml
# fly.toml
app = "my-rails-app"
primary_region = "iad"
console_command = "/rails/bin/rails console"

[build]

[deploy]
  release_command = "./bin/rails db:migrate"

[env]
  RAILS_ENV = "production"
  RAILS_LOG_TO_STDOUT = "true"
  RAILS_SERVE_STATIC_FILES = "true"
  STORAGE_SERVICE = "amazon"

[http_service]
  internal_port = 3000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 2
  processes = ["app"]

[[services]]
  protocol = "tcp"
  internal_port = 3000
  processes = ["app"]

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

  [[services.tcp_checks]]
    interval = "15s"
    timeout = "2s"
    grace_period = "5s"

  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    grace_period = "5s"
    method = "get"
    path = "/health"

[[statics]]
  guest_path = "/rails/public"
  url_prefix = "/"
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
variable "project_name" { default = "rails-app" }

# Cloud Run - Web
resource "google_cloud_run_v2_service" "web" {
  name     = "${var.project_name}-web"
  location = var.region

  template {
    scaling {
      min_instance_count = 2
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/web:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        cpu_idle = false
      }

      ports {
        container_port = 3000
      }

      env {
        name  = "RAILS_ENV"
        value = "production"
      }

      env {
        name  = "RAILS_LOG_TO_STDOUT"
        value = "true"
      }

      env {
        name  = "RAILS_SERVE_STATIC_FILES"
        value = "true"
      }

      env {
        name = "SECRET_KEY_BASE"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.rails_master_key.secret_id
            version = "latest"
          }
        }
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
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
      }

      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.storage.name
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        initial_delay_seconds = 10
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        period_seconds = 30
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

# Cloud Run - Worker (Sidekiq)
resource "google_cloud_run_v2_service" "worker" {
  name     = "${var.project_name}-worker"
  location = var.region

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    containers {
      image   = "${var.region}-docker.pkg.dev/${var.project_id}/${var.project_name}/web:latest"
      command = ["bundle", "exec", "sidekiq"]

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = false
      }

      # Same env vars as web...
      env {
        name  = "RAILS_ENV"
        value = "production"
      }

      # ... additional env vars
    }

    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
  }
}

# Cloud SQL
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

# Storage
resource "google_storage_bucket" "storage" {
  name     = "${var.project_id}-${var.project_name}-storage"
  location = var.region

  uniform_bucket_level_access = true
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

output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}
```

## Deployment Commands

### Fly.io
```bash
# Install flyctl
brew install flyctl

# Launch app
fly launch

# Deploy
fly deploy

# Run migrations
fly ssh console -C "/rails/bin/rails db:migrate"

# Rails console
fly ssh console -C "/rails/bin/rails console"

# View logs
fly logs

# Scale
fly scale count 3

# Create PostgreSQL
fly postgres create

# Attach database
fly postgres attach my-app-db

# Create Upstash Redis
fly redis create
```

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest

# Deploy web
gcloud run deploy ${APP_NAME}-web \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest \
  --region ${REGION} \
  --min-instances 2 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --add-cloudsql-instances ${PROJECT_ID}:${REGION}:${DB_INSTANCE}

# Deploy worker
gcloud run deploy ${APP_NAME}-worker \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${APP_NAME}/web:latest \
  --command "bundle,exec,sidekiq" \
  --region ${REGION} \
  --no-allow-unauthenticated \
  --min-instances 1

# Run migrations
gcloud run jobs execute migrate --region ${REGION}
```

## Cost Breakdown

### Fly.io
| Component | Monthly Cost |
|-----------|--------------|
| Machines (2 shared-cpu-2x) | ~$15 |
| Sidekiq (1 shared-cpu-1x) | ~$5 |
| Postgres (1GB) | ~$7 |
| Upstash Redis | ~$5 |
| **Total** | **~$32** |

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run Web (2 min) | ~$50 |
| Cloud Run Worker (1 min) | ~$25 |
| Cloud SQL | ~$50 |
| Redis | ~$35 |
| **Total** | **~$160** |

## Best Practices

1. **Use Puma with threads** - Optimal for I/O bound apps
2. **Configure connection pool** - Match RAILS_MAX_THREADS
3. **Use Sidekiq for jobs** - Reliable background processing
4. **ActiveStorage for uploads** - Cloud-native file handling
5. **Lograge for logging** - JSON structured logs
6. **Health check endpoint** - Required for load balancers
7. **Bootsnap for boot time** - Faster cold starts
8. **Rack::Attack for rate limiting** - Basic DDoS protection

## Common Mistakes

1. **Missing SECRET_KEY_BASE** - Rails won't start
2. **No connection pooling** - Database exhaustion
3. **Running migrations in CMD** - Race conditions
4. **Development gems in production** - Larger image, slower
5. **No health check** - Failed deployments
6. **Missing RAILS_SERVE_STATIC_FILES** - No assets served
7. **SQLite in production** - Use PostgreSQL
8. **No asset precompilation** - Missing CSS/JS

## Example Configuration

```yaml
# infera.yaml
project_name: my-rails-app
provider: fly  # or gcp

framework:
  name: rails
  version: "7.1"

deployment:
  type: container
  runtime: ruby-3.3

  web:
    resources:
      cpu: 2
      memory: 2Gi
    scaling:
      min_instances: 2
      max_instances: 10

  worker:
    command: "bundle exec sidekiq"
    resources:
      cpu: 1
      memory: 1Gi
    scaling:
      min_instances: 1

database:
  type: postgresql
  version: "15"
  size: 1gb

cache:
  type: redis
  size: 1gb

storage:
  type: s3  # or gcs
  bucket: my-app-storage

env_vars:
  RAILS_ENV: production
  RAILS_LOG_TO_STDOUT: "true"

secrets:
  - SECRET_KEY_BASE
  - DATABASE_URL
```

## Sources

- [Rails Guides](https://guides.rubyonrails.org/)
- [Fly.io Rails Guide](https://fly.io/docs/rails/)
- [Cloud Run Rails](https://cloud.google.com/ruby/rails/run)
- [Docker Rails Guide](https://docs.docker.com/samples/rails/)
