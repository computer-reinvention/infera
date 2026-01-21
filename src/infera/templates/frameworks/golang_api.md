# Go API (Cloud Run / Lambda)

## Overview

Deploy Go applications on serverless or container platforms for high-performance, low-latency APIs. Go's compiled binaries, minimal memory footprint, and fast startup times make it ideal for serverless and cloud-native deployments. Supports Cloud Run, Lambda, and Kubernetes.

## Detection Signals

Use this template when:
- `go.mod` file exists
- `main.go` or `cmd/` directory structure
- `*.go` files with `package main`
- High-performance API needed
- Minimal memory footprint required
- Fast cold start important
- Concurrent request handling

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
                    │   │  │    Go     │ │    Go     │ │    Go     │             │   │
                    │   │  │  Binary   │ │  Binary   │ │  Binary   │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │  ~10MB    │ │  ~10MB    │ │  ~10MB    │             │   │
                    │   │  │  <50ms    │ │  <50ms    │ │  <50ms    │             │   │
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
                    │   <10MB binary • <50ms cold start • Concurrent by default      │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 1 vCPU, 512MB RAM |
| Cloud SQL | PostgreSQL | db-f1-micro |
| Memorystore | Redis | 1GB |
| Cloud Storage | File uploads | Regional |
| Secret Manager | Credentials | Auto-mount |

### AWS (Lambda)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Lambda | Function compute | 512MB, provided.al2023 |
| API Gateway | HTTP routing | HTTP API |
| RDS Aurora | PostgreSQL | Serverless v2 |
| ElastiCache | Redis | Optional |
| S3 | File storage | Standard |

## Configuration

### Project Structure
```
my-go-api/
├── cmd/
│   └── api/
│       └── main.go           # Entry point
├── internal/
│   ├── config/
│   │   └── config.go         # Configuration
│   ├── handler/
│   │   ├── handler.go        # HTTP handlers
│   │   └── user.go
│   ├── middleware/
│   │   ├── logging.go
│   │   └── auth.go
│   ├── model/
│   │   └── user.go           # Domain models
│   ├── repository/
│   │   └── user.go           # Data access
│   ├── service/
│   │   └── user.go           # Business logic
│   └── server/
│       └── server.go         # HTTP server setup
├── pkg/
│   └── validator/
│       └── validator.go
├── migrations/
│   └── 001_init.sql
├── go.mod
├── go.sum
├── Dockerfile
├── Makefile
└── .env.example
```

### Main Entry Point
```go
// cmd/api/main.go
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"myapp/internal/config"
	"myapp/internal/server"
)

func main() {
	// Initialize logger
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		slog.Error("failed to load config", "error", err)
		os.Exit(1)
	}

	// Create server
	srv, err := server.New(cfg)
	if err != nil {
		slog.Error("failed to create server", "error", err)
		os.Exit(1)
	}

	// Start server in goroutine
	go func() {
		slog.Info("starting server", "port", cfg.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("shutting down server")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("server shutdown error", "error", err)
	}

	slog.Info("server stopped")
}
```

### Configuration
```go
// internal/config/config.go
package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	Port        string
	Environment string
	DatabaseURL string
	RedisURL    string
	JWTSecret   string
}

func Load() (*Config, error) {
	port := getEnv("PORT", "8080")
	env := getEnv("ENVIRONMENT", "development")

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}

	return &Config{
		Port:        port,
		Environment: env,
		DatabaseURL: dbURL,
		RedisURL:    getEnv("REDIS_URL", ""),
		JWTSecret:   os.Getenv("JWT_SECRET"),
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
```

### HTTP Server
```go
// internal/server/server.go
package server

import (
	"context"
	"database/sql"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"

	"myapp/internal/config"
	"myapp/internal/handler"
	"myapp/internal/repository"
	"myapp/internal/service"

	_ "github.com/lib/pq"
)

func New(cfg *config.Config) (*http.Server, error) {
	// Database connection
	db, err := sql.Open("postgres", cfg.DatabaseURL)
	if err != nil {
		return nil, err
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	if err := db.Ping(); err != nil {
		return nil, err
	}

	// Initialize layers
	userRepo := repository.NewUserRepository(db)
	userService := service.NewUserService(userRepo)
	userHandler := handler.NewUserHandler(userService)

	// Router
	r := chi.NewRouter()

	// Middleware
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))
	r.Use(middleware.Compress(5))

	// CORS
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Routes
	r.Get("/health", healthHandler)

	r.Route("/api/v1", func(r chi.Router) {
		r.Route("/users", func(r chi.Router) {
			r.Get("/", userHandler.List)
			r.Post("/", userHandler.Create)
			r.Get("/{id}", userHandler.Get)
			r.Put("/{id}", userHandler.Update)
			r.Delete("/{id}", userHandler.Delete)
		})
	})

	return &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}, nil
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"healthy"}`))
}
```

### User Model
```go
// internal/model/user.go
package model

import "time"

type User struct {
	ID        string    `json:"id" db:"id"`
	Email     string    `json:"email" db:"email"`
	Name      string    `json:"name" db:"name"`
	Password  string    `json:"-" db:"password"`
	IsActive  bool      `json:"is_active" db:"is_active"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}

type CreateUserInput struct {
	Email    string `json:"email" validate:"required,email"`
	Name     string `json:"name" validate:"required,min=2,max=100"`
	Password string `json:"password" validate:"required,min=8"`
}

type UpdateUserInput struct {
	Name     string `json:"name,omitempty" validate:"omitempty,min=2,max=100"`
	Password string `json:"password,omitempty" validate:"omitempty,min=8"`
}
```

### User Repository
```go
// internal/repository/user.go
package repository

import (
	"context"
	"database/sql"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"

	"myapp/internal/model"
)

type UserRepository struct {
	db *sql.DB
}

func NewUserRepository(db *sql.DB) *UserRepository {
	return &UserRepository{db: db}
}

func (r *UserRepository) FindAll(ctx context.Context, limit, offset int) ([]model.User, int, error) {
	var total int
	err := r.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM users WHERE is_active = true").Scan(&total)
	if err != nil {
		return nil, 0, err
	}

	rows, err := r.db.QueryContext(ctx, `
		SELECT id, email, name, is_active, created_at, updated_at
		FROM users
		WHERE is_active = true
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var users []model.User
	for rows.Next() {
		var u model.User
		if err := rows.Scan(&u.ID, &u.Email, &u.Name, &u.IsActive, &u.CreatedAt, &u.UpdatedAt); err != nil {
			return nil, 0, err
		}
		users = append(users, u)
	}

	return users, total, nil
}

func (r *UserRepository) FindByID(ctx context.Context, id string) (*model.User, error) {
	var u model.User
	err := r.db.QueryRowContext(ctx, `
		SELECT id, email, name, is_active, created_at, updated_at
		FROM users WHERE id = $1
	`, id).Scan(&u.ID, &u.Email, &u.Name, &u.IsActive, &u.CreatedAt, &u.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &u, nil
}

func (r *UserRepository) Create(ctx context.Context, input model.CreateUserInput) (*model.User, error) {
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(input.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	id := uuid.New().String()
	var u model.User
	err = r.db.QueryRowContext(ctx, `
		INSERT INTO users (id, email, name, password, is_active)
		VALUES ($1, $2, $3, $4, true)
		RETURNING id, email, name, is_active, created_at, updated_at
	`, id, input.Email, input.Name, string(hashedPassword)).Scan(
		&u.ID, &u.Email, &u.Name, &u.IsActive, &u.CreatedAt, &u.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return &u, nil
}

func (r *UserRepository) Delete(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, "DELETE FROM users WHERE id = $1", id)
	if err != nil {
		return err
	}
	rows, _ := result.RowsAffected()
	if rows == 0 {
		return sql.ErrNoRows
	}
	return nil
}
```

### User Handler
```go
// internal/handler/user.go
package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/go-playground/validator/v10"

	"myapp/internal/model"
	"myapp/internal/service"
)

type UserHandler struct {
	service  *service.UserService
	validate *validator.Validate
}

func NewUserHandler(s *service.UserService) *UserHandler {
	return &UserHandler{
		service:  s,
		validate: validator.New(),
	}
}

func (h *UserHandler) List(w http.ResponseWriter, r *http.Request) {
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 || limit > 100 {
		limit = 20
	}

	users, total, err := h.service.List(r.Context(), page, limit)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to fetch users")
		return
	}

	respond(w, http.StatusOK, map[string]interface{}{
		"data":  users,
		"total": total,
		"page":  page,
		"limit": limit,
	})
}

func (h *UserHandler) Get(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	user, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to fetch user")
		return
	}
	if user == nil {
		respondError(w, http.StatusNotFound, "User not found")
		return
	}

	respond(w, http.StatusOK, user)
}

func (h *UserHandler) Create(w http.ResponseWriter, r *http.Request) {
	var input model.CreateUserInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if err := h.validate.Struct(input); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	user, err := h.service.Create(r.Context(), input)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to create user")
		return
	}

	respond(w, http.StatusCreated, user)
}

func (h *UserHandler) Update(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	var input model.UpdateUserInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	user, err := h.service.Update(r.Context(), id, input)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to update user")
		return
	}

	respond(w, http.StatusOK, user)
}

func (h *UserHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")

	if err := h.service.Delete(r.Context(), id); err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to delete user")
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func respond(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, message string) {
	respond(w, status, map[string]string{"error": message})
}
```

### Dockerfile
```dockerfile
# Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /app

# Install dependencies
RUN apk add --no-cache git ca-certificates

# Download modules
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -o /app/server ./cmd/api

# Runtime stage
FROM scratch

# Copy CA certificates
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copy binary
COPY --from=builder /app/server /server

EXPOSE 8080

ENTRYPOINT ["/server"]
```

### AWS Lambda Handler
```go
// cmd/lambda/main.go
package main

import (
	"context"
	"log"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/awslabs/aws-lambda-go-api-proxy/chi"

	"myapp/internal/config"
	"myapp/internal/server"
)

var chiLambda *chiadapter.ChiLambda

func init() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}

	r, err := server.NewRouter(cfg)
	if err != nil {
		log.Fatal(err)
	}

	chiLambda = chiadapter.New(r)
}

func handler(ctx context.Context, req events.APIGatewayV2HTTPRequest) (events.APIGatewayV2HTTPResponse, error) {
	return chiLambda.ProxyWithContextV2(ctx, req)
}

func main() {
	lambda.Start(handler)
}
```

### go.mod
```go
module myapp

go 1.22

require (
	github.com/go-chi/chi/v5 v5.0.11
	github.com/go-chi/cors v1.2.1
	github.com/go-playground/validator/v10 v10.17.0
	github.com/google/uuid v1.6.0
	github.com/lib/pq v1.10.9
	golang.org/x/crypto v0.18.0
)
```

### Makefile
```makefile
.PHONY: build run test lint docker

build:
	CGO_ENABLED=0 go build -ldflags="-w -s" -o bin/server ./cmd/api

run:
	go run ./cmd/api

test:
	go test -v -race ./...

lint:
	golangci-lint run

docker:
	docker build -t myapp .

deploy-cloudrun:
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/myapp
	gcloud run deploy myapp \
		--image gcr.io/$(PROJECT_ID)/myapp \
		--platform managed \
		--region us-central1 \
		--allow-unauthenticated
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT_ID}/go-api

# Deploy
gcloud run deploy go-api \
  --image gcr.io/${PROJECT_ID}/go-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 100 \
  --set-secrets "DATABASE_URL=database-url:latest"

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100
```

### AWS Lambda
```bash
# Build for Lambda
GOOS=linux GOARCH=amd64 go build -o bootstrap ./cmd/lambda
zip function.zip bootstrap

# Deploy
aws lambda update-function-code \
  --function-name go-api \
  --zip-file fileb://function.zip

# Create HTTP API
aws apigatewayv2 create-api \
  --name go-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:us-east-1:123456789:function:go-api
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (scale to 0) | ~$0-10 |
| Cloud SQL (db-f1-micro) | ~$10 |
| **Total** | **~$10-20** |

### AWS Lambda
| Component | Monthly Cost |
|-----------|--------------|
| Lambda (1M requests) | ~$3 |
| API Gateway | ~$3.50 |
| RDS Serverless | ~$25 |
| **Total** | **~$32** |

## Best Practices

1. **Use context everywhere** - Propagate context for cancellation
2. **Structured logging** - Use slog for JSON logs
3. **Graceful shutdown** - Handle SIGTERM properly
4. **Connection pooling** - Configure database pool
5. **Minimal dependencies** - Keep binary small
6. **Scratch base image** - Smallest possible container
7. **Input validation** - Use validator package
8. **Error handling** - Don't expose internal errors

## Common Mistakes

1. **Ignoring context** - Use context.Context throughout
2. **Goroutine leaks** - Always handle cancellation
3. **No connection limits** - Set MaxOpenConns
4. **Panicking** - Recover in middleware
5. **Large binaries** - Use -ldflags="-w -s"
6. **No timeouts** - Set read/write timeouts
7. **Ignoring errors** - Always check error returns
8. **Global state** - Use dependency injection

## Example Configuration

```yaml
# infera.yaml
project_name: my-go-api
provider: gcp

framework:
  name: golang
  version: "1.22"

deployment:
  type: serverless

  resources:
    memory: 512Mi
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
  ENVIRONMENT: production

secrets:
  - DATABASE_URL
  - JWT_SECRET
```

## Sources

- [Go Documentation](https://go.dev/doc/)
- [Chi Router](https://go-chi.io/)
- [Cloud Run Go Quickstart](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/go)
- [AWS Lambda Go](https://docs.aws.amazon.com/lambda/latest/dg/lambda-golang.html)
