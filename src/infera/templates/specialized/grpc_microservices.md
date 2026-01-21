# gRPC Microservices

## Overview
gRPC is a high-performance RPC framework using Protocol Buffers for serialization. Ideal for internal microservice communication where performance, type safety, and streaming are important.

**Use when:**
- Internal service-to-service communication
- High-performance, low-latency requirements
- Need bidirectional streaming
- Polyglot microservices (code generation)
- Strong typing and schema enforcement

**Don't use when:**
- Browser clients (use REST/GraphQL gateway)
- Simple CRUD APIs
- Third-party integrations
- Team unfamiliar with Protocol Buffers

## Detection Signals

```
Files:
- *.proto, proto/
- buf.yaml, buf.gen.yaml
- grpc-*.config

Dependencies:
- @grpc/grpc-js, @grpc/proto-loader (Node.js)
- grpcio, grpcio-tools (Python)
- google.golang.org/grpc (Go)
- tonic (Rust)

Code Patterns:
- service *Service {, rpc *
- message Request {, message Response {
- grpc.Server, grpc.Client
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   gRPC Microservices Architecture                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    External Clients                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Web App   │  │  Mobile App │  │   Partner   │      │   │
│  │  │   (REST)    │  │   (REST)    │  │   (REST)    │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  │         │                │                │              │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            └────────────────┼────────────────┘                   │
│                             │ REST/HTTP                          │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                    API Gateway                            │   │
│  │            (REST → gRPC transcoding)                     │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │ gRPC                               │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                  Internal Services (gRPC)                 │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │    Users    │  │   Orders    │  │  Products   │      │   │
│  │  │   Service   │──│   Service   │──│   Service   │      │   │
│  │  │   (gRPC)    │  │   (gRPC)    │  │   (gRPC)    │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  │         │                │                │              │   │
│  │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │   │
│  │  │  Users DB   │  │ Orders DB   │  │ Products DB │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Protocol Buffer Definitions

### Service Definition

```protobuf
// proto/user/v1/user.proto
syntax = "proto3";

package user.v1;

option go_package = "github.com/myorg/api/gen/user/v1;userv1";

import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";

// User service definition
service UserService {
  // Unary RPC
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
  rpc UpdateUser(UpdateUserRequest) returns (UpdateUserResponse);
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty);

  // Server streaming - list with pagination
  rpc ListUsers(ListUsersRequest) returns (stream User);

  // Client streaming - batch create
  rpc BatchCreateUsers(stream CreateUserRequest) returns (BatchCreateUsersResponse);

  // Bidirectional streaming
  rpc SyncUsers(stream SyncUsersRequest) returns (stream SyncUsersResponse);
}

// Messages
message User {
  string id = 1;
  string email = 2;
  string name = 3;
  UserRole role = 4;
  google.protobuf.Timestamp created_at = 5;
  google.protobuf.Timestamp updated_at = 6;
}

enum UserRole {
  USER_ROLE_UNSPECIFIED = 0;
  USER_ROLE_ADMIN = 1;
  USER_ROLE_MEMBER = 2;
}

message GetUserRequest {
  string id = 1;
}

message GetUserResponse {
  User user = 1;
}

message CreateUserRequest {
  string email = 1;
  string name = 2;
  UserRole role = 3;
}

message CreateUserResponse {
  User user = 1;
}

message UpdateUserRequest {
  string id = 1;
  optional string email = 2;
  optional string name = 3;
  optional UserRole role = 4;
}

message UpdateUserResponse {
  User user = 1;
}

message DeleteUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
}

message BatchCreateUsersResponse {
  repeated User users = 1;
  int32 created_count = 2;
}

message SyncUsersRequest {
  User user = 1;
}

message SyncUsersResponse {
  User user = 1;
  SyncStatus status = 2;
}

enum SyncStatus {
  SYNC_STATUS_UNSPECIFIED = 0;
  SYNC_STATUS_CREATED = 1;
  SYNC_STATUS_UPDATED = 2;
  SYNC_STATUS_UNCHANGED = 3;
}
```

### Buf Configuration

```yaml
# buf.yaml
version: v1
name: buf.build/myorg/api
deps:
  - buf.build/googleapis/googleapis
breaking:
  use:
    - FILE
lint:
  use:
    - DEFAULT
```

```yaml
# buf.gen.yaml
version: v1
managed:
  enabled: true
  go_package_prefix:
    default: github.com/myorg/api/gen
plugins:
  # Go
  - plugin: buf.build/protocolbuffers/go
    out: gen
    opt: paths=source_relative
  - plugin: buf.build/grpc/go
    out: gen
    opt: paths=source_relative

  # TypeScript
  - plugin: buf.build/community/timostamm-protobuf-ts
    out: gen/ts
    opt:
      - long_type_string
      - generate_dependencies

  # Python
  - plugin: buf.build/grpc/python
    out: gen/python
  - plugin: buf.build/protocolbuffers/python
    out: gen/python
```

```bash
# Generate code
buf generate
```

## Go Implementation

### Server

```go
// cmd/server/main.go
package main

import (
    "context"
    "log"
    "net"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/health"
    "google.golang.org/grpc/health/grpc_health_v1"
    "google.golang.org/grpc/reflection"
    "google.golang.org/grpc/status"

    userv1 "github.com/myorg/api/gen/user/v1"
)

type userServer struct {
    userv1.UnimplementedUserServiceServer
    repo UserRepository
}

func (s *userServer) GetUser(ctx context.Context, req *userv1.GetUserRequest) (*userv1.GetUserResponse, error) {
    user, err := s.repo.GetByID(ctx, req.Id)
    if err != nil {
        return nil, status.Errorf(codes.NotFound, "user not found: %v", err)
    }

    return &userv1.GetUserResponse{
        User: toProtoUser(user),
    }, nil
}

func (s *userServer) CreateUser(ctx context.Context, req *userv1.CreateUserRequest) (*userv1.CreateUserResponse, error) {
    user, err := s.repo.Create(ctx, &User{
        Email: req.Email,
        Name:  req.Name,
        Role:  toModelRole(req.Role),
    })
    if err != nil {
        return nil, status.Errorf(codes.Internal, "failed to create user: %v", err)
    }

    return &userv1.CreateUserResponse{
        User: toProtoUser(user),
    }, nil
}

// Server streaming
func (s *userServer) ListUsers(req *userv1.ListUsersRequest, stream userv1.UserService_ListUsersServer) error {
    users, err := s.repo.List(stream.Context(), req.PageSize, req.PageToken)
    if err != nil {
        return status.Errorf(codes.Internal, "failed to list users: %v", err)
    }

    for _, user := range users {
        if err := stream.Send(toProtoUser(user)); err != nil {
            return err
        }
    }

    return nil
}

// Client streaming
func (s *userServer) BatchCreateUsers(stream userv1.UserService_BatchCreateUsersServer) error {
    var users []*userv1.User

    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return stream.SendAndClose(&userv1.BatchCreateUsersResponse{
                Users:        users,
                CreatedCount: int32(len(users)),
            })
        }
        if err != nil {
            return err
        }

        user, err := s.repo.Create(stream.Context(), &User{
            Email: req.Email,
            Name:  req.Name,
        })
        if err != nil {
            return status.Errorf(codes.Internal, "failed to create user: %v", err)
        }

        users = append(users, toProtoUser(user))
    }
}

func main() {
    lis, err := net.Listen("tcp", ":50051")
    if err != nil {
        log.Fatalf("failed to listen: %v", err)
    }

    // Create server with interceptors
    server := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            loggingInterceptor,
            authInterceptor,
            recoveryInterceptor,
        ),
        grpc.ChainStreamInterceptor(
            streamLoggingInterceptor,
            streamAuthInterceptor,
        ),
    )

    // Register services
    userv1.RegisterUserServiceServer(server, &userServer{repo: NewUserRepository()})

    // Health check
    healthServer := health.NewServer()
    healthServer.SetServingStatus("user.v1.UserService", grpc_health_v1.HealthCheckResponse_SERVING)
    grpc_health_v1.RegisterHealthServer(server, healthServer)

    // Reflection for debugging
    reflection.Register(server)

    log.Println("Starting gRPC server on :50051")
    if err := server.Serve(lis); err != nil {
        log.Fatalf("failed to serve: %v", err)
    }
}
```

### Client

```go
// client.go
package client

import (
    "context"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"

    userv1 "github.com/myorg/api/gen/user/v1"
)

type UserClient struct {
    client userv1.UserServiceClient
    conn   *grpc.ClientConn
}

func NewUserClient(address string) (*UserClient, error) {
    conn, err := grpc.Dial(
        address,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithBlock(),
        grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
    )
    if err != nil {
        return nil, err
    }

    return &UserClient{
        client: userv1.NewUserServiceClient(conn),
        conn:   conn,
    }, nil
}

func (c *UserClient) GetUser(ctx context.Context, id string) (*userv1.User, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    resp, err := c.client.GetUser(ctx, &userv1.GetUserRequest{Id: id})
    if err != nil {
        return nil, err
    }

    return resp.User, nil
}

func (c *UserClient) ListUsers(ctx context.Context, pageSize int32) ([]*userv1.User, error) {
    stream, err := c.client.ListUsers(ctx, &userv1.ListUsersRequest{
        PageSize: pageSize,
    })
    if err != nil {
        return nil, err
    }

    var users []*userv1.User
    for {
        user, err := stream.Recv()
        if err == io.EOF {
            break
        }
        if err != nil {
            return nil, err
        }
        users = append(users, user)
    }

    return users, nil
}

func (c *UserClient) Close() error {
    return c.conn.Close()
}
```

## Node.js Implementation

### Server

```typescript
// server.ts
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';

const PROTO_PATH = path.resolve(__dirname, '../proto/user/v1/user.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const userProto = (protoDescriptor.user as any).v1;

// Implementation
const userService = {
  getUser: async (
    call: grpc.ServerUnaryCall<any, any>,
    callback: grpc.sendUnaryData<any>
  ) => {
    try {
      const user = await userRepository.findById(call.request.id);
      if (!user) {
        return callback({
          code: grpc.status.NOT_FOUND,
          message: 'User not found',
        });
      }
      callback(null, { user });
    } catch (error) {
      callback({
        code: grpc.status.INTERNAL,
        message: error.message,
      });
    }
  },

  createUser: async (
    call: grpc.ServerUnaryCall<any, any>,
    callback: grpc.sendUnaryData<any>
  ) => {
    try {
      const user = await userRepository.create(call.request);
      callback(null, { user });
    } catch (error) {
      callback({
        code: grpc.status.INTERNAL,
        message: error.message,
      });
    }
  },

  // Server streaming
  listUsers: async (call: grpc.ServerWritableStream<any, any>) => {
    try {
      const users = await userRepository.list(
        call.request.page_size,
        call.request.page_token
      );

      for (const user of users) {
        call.write(user);
      }
      call.end();
    } catch (error) {
      call.destroy(error);
    }
  },
};

// Start server
function main() {
  const server = new grpc.Server();

  server.addService(userProto.UserService.service, userService);

  server.bindAsync(
    '0.0.0.0:50051',
    grpc.ServerCredentials.createInsecure(),
    (error, port) => {
      if (error) {
        console.error('Failed to bind:', error);
        return;
      }
      console.log(`Server running on port ${port}`);
      server.start();
    }
  );
}

main();
```

## Terraform Configuration

```hcl
# grpc_service.tf

# Cloud Run for gRPC service
resource "google_cloud_run_v2_service" "users_grpc" {
  name     = "${var.project_name}-users-grpc"
  location = var.region

  template {
    containers {
      image = var.users_service_image

      ports {
        container_port = 50051
        name           = "h2c"  # HTTP/2 cleartext for gRPC
      }

      env {
        name  = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        grpc {
          service = "user.v1.UserService"
        }
        initial_delay_seconds = 5
      }

      liveness_probe {
        grpc {
          service = "user.v1.UserService"
        }
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Internal load balancer for gRPC
resource "google_compute_region_backend_service" "grpc_backend" {
  name                  = "${var.project_name}-grpc-backend"
  region                = var.region
  protocol              = "GRPC"
  load_balancing_scheme = "INTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.grpc_neg.id
  }

  health_checks = [google_compute_health_check.grpc_health.id]
}

resource "google_compute_health_check" "grpc_health" {
  name = "${var.project_name}-grpc-health"

  grpc_health_check {
    port         = 50051
    grpc_service_name = "user.v1.UserService"
  }
}
```

## API Gateway (gRPC-Web/REST Transcoding)

```yaml
# envoy.yaml - REST to gRPC transcoding
static_resources:
  listeners:
    - name: listener_0
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 8080
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: ingress_http
                route_config:
                  name: local_route
                  virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      routes:
                        - match:
                            prefix: "/"
                          route:
                            cluster: grpc_service
                http_filters:
                  - name: envoy.filters.http.grpc_json_transcoder
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.grpc_json_transcoder.v3.GrpcJsonTranscoder
                      proto_descriptor: "/etc/envoy/proto.pb"
                      services: ["user.v1.UserService"]
                      print_options:
                        add_whitespace: true
                        always_print_primitive_fields: true
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  clusters:
    - name: grpc_service
      connect_timeout: 5s
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      typed_extension_protocol_options:
        envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
          "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
          explicit_http_config:
            http2_protocol_options: {}
      load_assignment:
        cluster_name: grpc_service
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: users-grpc
                      port_value: 50051
```

## Cost Breakdown

| Provider | Service | ~1M requests/mo |
|----------|---------|-----------------|
| **GCP Cloud Run** | gRPC service | ~$20 |
| **AWS ECS** | gRPC service | ~$30 |
| **GKE/EKS** | Kubernetes | ~$100+ (cluster overhead) |

## Best Practices

### Interceptors

```go
// Logging interceptor
func loggingInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    start := time.Now()

    resp, err := handler(ctx, req)

    log.Printf(
        "method=%s duration=%s error=%v",
        info.FullMethod,
        time.Since(start),
        err,
    )

    return resp, err
}

// Auth interceptor
func authInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Error(codes.Unauthenticated, "missing metadata")
    }

    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Error(codes.Unauthenticated, "missing token")
    }

    // Verify token
    claims, err := verifyToken(tokens[0])
    if err != nil {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }

    // Add claims to context
    ctx = context.WithValue(ctx, "user", claims)

    return handler(ctx, req)
}
```

## Common Mistakes

1. **Exposing gRPC to browsers** - Use gRPC-Web or REST gateway
2. **No health checks** - Load balancer can't detect unhealthy instances
3. **Missing deadlines** - Requests hang forever
4. **No retry logic** - Transient failures cause errors
5. **Large messages** - gRPC has 4MB default limit
6. **Blocking streams** - Not handling backpressure
7. **No reflection** - Hard to debug with grpcurl
8. **Missing interceptors** - No logging, auth, or metrics
9. **Ignoring status codes** - Using generic errors
10. **No graceful shutdown** - Active requests interrupted

## Example Configuration

```yaml
# infera.yaml
project_name: my-microservices
provider: gcp
region: us-central1

grpc_services:
  - name: users
    proto: proto/user/v1/user.proto
    port: 50051
    health_check: true

  - name: orders
    proto: proto/order/v1/order.proto
    port: 50052
    health_check: true

gateway:
  type: envoy
  transcoding: true
  routes:
    - path: /v1/users/*
      service: users
    - path: /v1/orders/*
      service: orders

networking:
  internal_lb: true
  vpc_connector: true
```

## Sources

- [gRPC Documentation](https://grpc.io/docs/)
- [Protocol Buffers](https://protobuf.dev/)
- [Buf Documentation](https://buf.build/docs/)
- [Cloud Run gRPC](https://cloud.google.com/run/docs/triggering/grpc)
- [gRPC-Web](https://grpc.io/docs/platforms/web/)
