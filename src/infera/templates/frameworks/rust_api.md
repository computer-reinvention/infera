# Rust API (Cloud Run / Lambda)

## Overview

Deploy Rust applications on serverless or container platforms for ultra-high-performance, memory-safe APIs. Rust's zero-cost abstractions, tiny binaries, and sub-millisecond cold starts make it ideal for latency-critical serverless applications. Supports Cloud Run, Lambda, and Cloudflare Workers.

## Detection Signals

Use this template when:
- `Cargo.toml` file exists
- `src/main.rs` with `actix-web`, `axum`, or `rocket`
- `*.rs` files present
- Ultra-high performance required
- Memory safety critical
- Minimal cold starts needed
- Low memory footprint required

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Serverless / Container Platform               │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Load Balancer / Gateway                 │   │
                    │   │              (Cloud LB / API Gateway)                    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Compute (Cloud Run / Lambda)                │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │   Rust    │ │   Rust    │ │   Rust    │             │   │
                    │   │  │  Binary   │ │  Binary   │ │  Binary   │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │  ~5MB     │ │  ~5MB     │ │  ~5MB     │             │   │
                    │   │  │  <10ms    │ │  <10ms    │ │  <10ms    │             │   │
                    │   │  │  startup  │ │  startup  │ │  startup  │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 0-1000+ concurrent instances             │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │ PostgreSQL│     │   Redis   │     │  Storage  │            │
                    │   │ (Managed) │     │  (Cache)  │     │ (GCS/S3)  │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   ~5MB binary • <10ms cold start • Memory-safe • Blazing fast  │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 1 vCPU, 256MB RAM |
| Cloud SQL | PostgreSQL | db-f1-micro |
| Memorystore | Redis | Optional |
| Secret Manager | Credentials | Auto-mount |

### AWS (Lambda)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Lambda | Function compute | 256MB, provided.al2023 |
| API Gateway | HTTP routing | HTTP API |
| RDS Aurora | PostgreSQL | Serverless v2 |
| S3 | File storage | Standard |

## Configuration

### Project Structure
```
my-rust-api/
├── src/
│   ├── main.rs               # Entry point
│   ├── config.rs             # Configuration
│   ├── routes/
│   │   ├── mod.rs
│   │   ├── health.rs
│   │   └── users.rs
│   ├── handlers/
│   │   ├── mod.rs
│   │   └── user.rs
│   ├── models/
│   │   ├── mod.rs
│   │   └── user.rs
│   ├── db/
│   │   ├── mod.rs
│   │   └── user.rs
│   └── error.rs
├── migrations/
│   └── 001_init.sql
├── Cargo.toml
├── Cargo.lock
├── Dockerfile
└── .env.example
```

### Cargo.toml
```toml
[package]
name = "my-api"
version = "0.1.0"
edition = "2021"

[dependencies]
# Web framework
axum = { version = "0.7", features = ["macros"] }
tokio = { version = "1", features = ["full"] }
tower = "0.4"
tower-http = { version = "0.5", features = ["cors", "compression-gzip", "trace"] }

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# Database
sqlx = { version = "0.7", features = ["runtime-tokio", "postgres", "uuid", "chrono"] }

# Validation
validator = { version = "0.16", features = ["derive"] }

# Error handling
thiserror = "1"
anyhow = "1"

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }

# Utils
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
dotenvy = "0.15"

# Password hashing
argon2 = "0.5"

[profile.release]
lto = true
codegen-units = 1
panic = "abort"
strip = true
```

### Main Entry Point
```rust
// src/main.rs
use std::net::SocketAddr;
use std::sync::Arc;

use axum::Router;
use sqlx::postgres::PgPoolOptions;
use tower_http::cors::{Any, CorsLayer};
use tower_http::compression::CompressionLayer;
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod error;
mod handlers;
mod models;
mod routes;
mod db;

use config::Config;

#[derive(Clone)]
pub struct AppState {
    pub db: sqlx::PgPool,
    pub config: Arc<Config>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    // Load config
    dotenvy::dotenv().ok();
    let config = Config::from_env()?;
    let config = Arc::new(config);

    // Database pool
    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(&config.database_url)
        .await?;

    // Run migrations
    sqlx::migrate!("./migrations").run(&pool).await?;

    let state = AppState {
        db: pool,
        config: config.clone(),
    };

    // Build router
    let app = Router::new()
        .merge(routes::health::router())
        .merge(routes::users::router())
        .layer(CompressionLayer::new())
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_methods(Any)
                .allow_headers(Any),
        )
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    // Start server
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    tracing::info!("listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    Ok(())
}

async fn shutdown_signal() {
    tokio::signal::ctrl_c()
        .await
        .expect("failed to install CTRL+C signal handler");
    tracing::info!("shutdown signal received");
}
```

### Configuration
```rust
// src/config.rs
use anyhow::Result;

#[derive(Clone)]
pub struct Config {
    pub port: u16,
    pub database_url: String,
    pub jwt_secret: String,
    pub environment: String,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            port: std::env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()?,
            database_url: std::env::var("DATABASE_URL")?,
            jwt_secret: std::env::var("JWT_SECRET").unwrap_or_else(|_| "secret".to_string()),
            environment: std::env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string()),
        })
    }

    pub fn is_production(&self) -> bool {
        self.environment == "production"
    }
}
```

### User Model
```rust
// src/models/user.rs
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;
use validator::Validate;

#[derive(Debug, Serialize, FromRow)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub name: String,
    #[serde(skip_serializing)]
    pub password_hash: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, Validate)]
pub struct CreateUser {
    #[validate(email(message = "Invalid email"))]
    pub email: String,
    #[validate(length(min = 2, max = 100, message = "Name must be 2-100 characters"))]
    pub name: String,
    #[validate(length(min = 8, message = "Password must be at least 8 characters"))]
    pub password: String,
}

#[derive(Debug, Deserialize, Validate)]
pub struct UpdateUser {
    #[validate(length(min = 2, max = 100))]
    pub name: Option<String>,
    #[validate(length(min = 8))]
    pub password: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UserResponse {
    pub id: Uuid,
    pub email: String,
    pub name: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
}

impl From<User> for UserResponse {
    fn from(user: User) -> Self {
        Self {
            id: user.id,
            email: user.email,
            name: user.name,
            is_active: user.is_active,
            created_at: user.created_at,
        }
    }
}
```

### Database Operations
```rust
// src/db/user.rs
use anyhow::Result;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::user::{CreateUser, User, UpdateUser};

pub async fn find_all(pool: &PgPool, limit: i64, offset: i64) -> Result<(Vec<User>, i64)> {
    let total: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM users WHERE is_active = true")
        .fetch_one(pool)
        .await?;

    let users = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, password_hash, is_active, created_at, updated_at
        FROM users
        WHERE is_active = true
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        "#,
    )
    .bind(limit)
    .bind(offset)
    .fetch_all(pool)
    .await?;

    Ok((users, total.0))
}

pub async fn find_by_id(pool: &PgPool, id: Uuid) -> Result<Option<User>> {
    let user = sqlx::query_as::<_, User>(
        "SELECT id, email, name, password_hash, is_active, created_at, updated_at FROM users WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(pool)
    .await?;

    Ok(user)
}

pub async fn create(pool: &PgPool, input: CreateUser, password_hash: String) -> Result<User> {
    let user = sqlx::query_as::<_, User>(
        r#"
        INSERT INTO users (id, email, name, password_hash, is_active)
        VALUES ($1, $2, $3, $4, true)
        RETURNING id, email, name, password_hash, is_active, created_at, updated_at
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(&input.email)
    .bind(&input.name)
    .bind(&password_hash)
    .fetch_one(pool)
    .await?;

    Ok(user)
}

pub async fn delete(pool: &PgPool, id: Uuid) -> Result<bool> {
    let result = sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await?;

    Ok(result.rows_affected() > 0)
}
```

### User Handlers
```rust
// src/handlers/user.rs
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use validator::Validate;

use crate::db::user as user_db;
use crate::error::AppError;
use crate::models::user::{CreateUser, UserResponse};
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct Pagination {
    #[serde(default = "default_page")]
    pub page: i64,
    #[serde(default = "default_limit")]
    pub limit: i64,
}

fn default_page() -> i64 { 1 }
fn default_limit() -> i64 { 20 }

#[derive(Serialize)]
pub struct PaginatedResponse<T> {
    pub data: Vec<T>,
    pub total: i64,
    pub page: i64,
    pub limit: i64,
}

pub async fn list(
    State(state): State<AppState>,
    Query(pagination): Query<Pagination>,
) -> Result<Json<PaginatedResponse<UserResponse>>, AppError> {
    let limit = pagination.limit.min(100);
    let offset = (pagination.page - 1) * limit;

    let (users, total) = user_db::find_all(&state.db, limit, offset).await?;

    Ok(Json(PaginatedResponse {
        data: users.into_iter().map(UserResponse::from).collect(),
        total,
        page: pagination.page,
        limit,
    }))
}

pub async fn get(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<UserResponse>, AppError> {
    let user = user_db::find_by_id(&state.db, id)
        .await?
        .ok_or(AppError::NotFound("User not found".to_string()))?;

    Ok(Json(UserResponse::from(user)))
}

pub async fn create(
    State(state): State<AppState>,
    Json(input): Json<CreateUser>,
) -> Result<(StatusCode, Json<UserResponse>), AppError> {
    input.validate()?;

    // Hash password
    let password_hash = argon2::hash_encoded(
        input.password.as_bytes(),
        b"randomsalt123456",
        &argon2::Config::default(),
    )?;

    let user = user_db::create(&state.db, input, password_hash).await?;

    Ok((StatusCode::CREATED, Json(UserResponse::from(user))))
}

pub async fn delete(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, AppError> {
    let deleted = user_db::delete(&state.db, id).await?;

    if deleted {
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(AppError::NotFound("User not found".to_string()))
    }
}
```

### Routes
```rust
// src/routes/users.rs
use axum::{
    routing::{get, post, delete},
    Router,
};

use crate::handlers::user;
use crate::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/api/v1/users", get(user::list).post(user::create))
        .route("/api/v1/users/:id", get(user::get).delete(user::delete))
}

// src/routes/health.rs
use axum::{routing::get, Json, Router};
use serde::Serialize;

use crate::AppState;

#[derive(Serialize)]
struct HealthResponse {
    status: String,
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "healthy".to_string(),
    })
}

pub fn router() -> Router<AppState> {
    Router::new().route("/health", get(health))
}
```

### Error Handling
```rust
// src/error.rs
use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

#[derive(Debug)]
pub enum AppError {
    NotFound(String),
    BadRequest(String),
    Internal(String),
    Validation(validator::ValidationErrors),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            AppError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
            AppError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg),
            AppError::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            AppError::Validation(errors) => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "error": "Validation failed", "details": errors })),
                )
                    .into_response()
            }
        };

        (status, Json(json!({ "error": message }))).into_response()
    }
}

impl From<anyhow::Error> for AppError {
    fn from(err: anyhow::Error) -> Self {
        tracing::error!("Internal error: {:?}", err);
        AppError::Internal("Internal server error".to_string())
    }
}

impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        tracing::error!("Database error: {:?}", err);
        AppError::Internal("Database error".to_string())
    }
}

impl From<validator::ValidationErrors> for AppError {
    fn from(errors: validator::ValidationErrors) -> Self {
        AppError::Validation(errors)
    }
}

impl From<argon2::Error> for AppError {
    fn from(err: argon2::Error) -> Self {
        tracing::error!("Argon2 error: {:?}", err);
        AppError::Internal("Password hashing error".to_string())
    }
}
```

### Dockerfile
```dockerfile
# Build stage
FROM rust:1.75-slim AS builder

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

# Create dummy project for dependency caching
RUN cargo new --bin myapp
WORKDIR /app/myapp

# Copy manifests
COPY Cargo.toml Cargo.lock ./

# Build dependencies only
RUN cargo build --release
RUN rm src/*.rs

# Copy source and build
COPY src ./src
COPY migrations ./migrations
RUN touch src/main.rs
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/myapp/target/release/my-api /usr/local/bin/

EXPOSE 8080
ENV PORT=8080

CMD ["my-api"]
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT_ID}/rust-api

# Deploy
gcloud run deploy rust-api \
  --image gcr.io/${PROJECT_ID}/rust-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 100 \
  --set-secrets "DATABASE_URL=database-url:latest"

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100
```

### AWS Lambda
```bash
# Build with cargo-lambda
cargo lambda build --release --arm64

# Deploy
cargo lambda deploy rust-api \
  --region us-east-1 \
  --memory 256

# With environment variables
cargo lambda deploy rust-api \
  --env-var DATABASE_URL=$DATABASE_URL
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (scale to 0) | ~$0-5 |
| Cloud SQL (db-f1-micro) | ~$10 |
| **Total** | **~$10-15** |

### AWS Lambda
| Component | Monthly Cost |
|-----------|--------------|
| Lambda (1M requests) | ~$2 |
| API Gateway | ~$3.50 |
| RDS Serverless | ~$25 |
| **Total** | **~$30** |

## Best Practices

1. **Use release builds** - Enable LTO and strip symbols
2. **Async all the way** - Use tokio for async runtime
3. **Connection pooling** - SQLx handles this automatically
4. **Structured errors** - Use thiserror for error types
5. **Tracing** - Use tracing crate for observability
6. **Validation** - Use validator crate for input
7. **Graceful shutdown** - Handle SIGTERM signals
8. **Minimal runtime** - Use slim base images

## Common Mistakes

1. **Debug builds in production** - Always use --release
2. **Blocking in async** - Use spawn_blocking for CPU work
3. **No error handling** - Use Result everywhere
4. **Large binaries** - Enable LTO and strip
5. **No connection limits** - Configure pool size
6. **Panicking** - Use proper error types
7. **No logging** - Add tracing from start
8. **Unbounded buffers** - Set limits on collections

## Example Configuration

```yaml
# infera.yaml
project_name: my-rust-api
provider: gcp

framework:
  name: rust
  version: "1.75"

deployment:
  type: serverless

  resources:
    memory: 256Mi
    cpu: 1

  scaling:
    min_instances: 0
    max_instances: 100
    concurrency: 80

  health_check:
    path: /health
    interval: 10s

database:
  type: postgresql
  version: "15"
  tier: serverless

env_vars:
  RUST_LOG: info
  ENVIRONMENT: production

secrets:
  - DATABASE_URL
  - JWT_SECRET
```

## Sources

- [Axum Documentation](https://docs.rs/axum/latest/axum/)
- [SQLx Documentation](https://docs.rs/sqlx/latest/sqlx/)
- [Cloud Run Rust](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/rust)
- [Cargo Lambda](https://www.cargo-lambda.info/)
