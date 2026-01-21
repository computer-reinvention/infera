# WebSocket Real-time Applications

## Overview
WebSocket enables bidirectional, real-time communication between clients and servers. Essential for chat applications, live notifications, collaborative editing, gaming, and real-time dashboards.

**Use when:**
- Building chat or messaging features
- Real-time collaboration (documents, whiteboards)
- Live notifications and updates
- Gaming or interactive applications
- Real-time dashboards and monitoring

**Don't use when:**
- Simple request/response patterns suffice
- Updates can be polled at intervals
- Mobile apps with intermittent connectivity (consider SSE)

## Detection Signals

```
Files:
- socket.io.*, ws.*, websocket.*
- channels.py (Django Channels)
- cable.yml (Rails Action Cable)

Dependencies:
- socket.io, ws, @fastify/websocket (Node.js)
- channels, websockets (Python)
- gorilla/websocket (Go)
- Phoenix.Socket (Elixir)

Code Patterns:
- ws://, wss://
- io.connect(), socket.emit(), socket.on()
- WebSocket, onmessage, onopen
- @SubscribeMessage (NestJS)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   WebSocket Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Clients                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Browser │  │ Mobile  │  │   IoT   │  │ Desktop │     │   │
│  │  │   App   │  │   App   │  │ Device  │  │   App   │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  │       │ wss://     │            │            │           │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          └────────────┴──────┬─────┴────────────┘                │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    Load Balancer                           │  │
│  │           (Sticky sessions / Connection affinity)          │  │
│  └───────────────────────────┬───────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                  WebSocket Servers                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │  Instance 1 │  │  Instance 2 │  │  Instance N │       │  │
│  │  │             │  │             │  │             │       │  │
│  │  │ Connections │  │ Connections │  │ Connections │       │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │  │
│  │         │                │                │               │  │
│  └─────────┼────────────────┼────────────────┼───────────────┘  │
│            └────────────────┼────────────────┘                   │
│                             │                                    │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │                    Pub/Sub Layer                           │  │
│  │           (Redis / Kafka / Cloud Pub/Sub)                 │  │
│  │    Cross-instance message broadcasting                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Options

| Feature | Cloud Run | AWS ECS/ALB | Cloudflare Durable Objects | Fly.io |
|---------|-----------|-------------|---------------------------|--------|
| **WebSocket Support** | Yes (streaming) | Yes | Yes (native) | Yes |
| **Connection Limit** | Depends on instance | ALB: 60s idle | No limit | No limit |
| **Sticky Sessions** | Not native | Yes | Built-in | Yes |
| **Pub/Sub** | External (Redis) | ElastiCache | Built-in | External |
| **Auto-scaling** | Yes | Yes | Yes | Yes |
| **Cold Start** | ~1-2s | ~10-30s | Sub-ms | ~300ms |

## Node.js Implementation

### Socket.IO (Recommended)

```typescript
// server.ts
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { createClient } from 'redis';

const app = express();
const httpServer = createServer(app);

const io = new Server(httpServer, {
  cors: {
    origin: process.env.ALLOWED_ORIGINS?.split(',') || '*',
    methods: ['GET', 'POST'],
  },
  pingTimeout: 60000,
  pingInterval: 25000,
});

// Redis adapter for multi-instance scaling
if (process.env.REDIS_URL) {
  const pubClient = createClient({ url: process.env.REDIS_URL });
  const subClient = pubClient.duplicate();

  Promise.all([pubClient.connect(), subClient.connect()]).then(() => {
    io.adapter(createAdapter(pubClient, subClient));
    console.log('Redis adapter connected');
  });
}

// Authentication middleware
io.use((socket, next) => {
  const token = socket.handshake.auth.token;
  if (!token) {
    return next(new Error('Authentication required'));
  }

  try {
    const user = verifyToken(token);
    socket.data.user = user;
    next();
  } catch (err) {
    next(new Error('Invalid token'));
  }
});

// Connection handling
io.on('connection', (socket) => {
  const user = socket.data.user;
  console.log(`User ${user.id} connected`);

  // Join user's personal room
  socket.join(`user:${user.id}`);

  // Join chat rooms
  socket.on('join-room', (roomId: string) => {
    socket.join(`room:${roomId}`);
    socket.to(`room:${roomId}`).emit('user-joined', {
      userId: user.id,
      username: user.name,
    });
  });

  // Handle chat messages
  socket.on('message', async (data: { roomId: string; content: string }) => {
    const message = {
      id: crypto.randomUUID(),
      userId: user.id,
      username: user.name,
      content: data.content,
      timestamp: new Date().toISOString(),
    };

    // Save to database
    await saveMessage(data.roomId, message);

    // Broadcast to room
    io.to(`room:${data.roomId}`).emit('message', message);
  });

  // Typing indicators
  socket.on('typing', (roomId: string) => {
    socket.to(`room:${roomId}`).emit('user-typing', {
      userId: user.id,
      username: user.name,
    });
  });

  // Handle disconnection
  socket.on('disconnect', () => {
    console.log(`User ${user.id} disconnected`);
  });
});

// Send to specific user (from any instance)
export function sendToUser(userId: string, event: string, data: any) {
  io.to(`user:${userId}`).emit(event, data);
}

// Broadcast to room (from any instance)
export function broadcastToRoom(roomId: string, event: string, data: any) {
  io.to(`room:${roomId}`).emit(event, data);
}

const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

### Client Implementation

```typescript
// client.ts
import { io, Socket } from 'socket.io-client';

class ChatClient {
  private socket: Socket;
  private listeners: Map<string, Set<Function>> = new Map();

  constructor(serverUrl: string, token: string) {
    this.socket = io(serverUrl, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    this.socket.on('connect', () => {
      console.log('Connected to server');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('Disconnected:', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('Connection error:', error.message);
    });

    this.socket.on('message', (message) => {
      this.emit('message', message);
    });

    this.socket.on('user-typing', (data) => {
      this.emit('typing', data);
    });
  }

  joinRoom(roomId: string) {
    this.socket.emit('join-room', roomId);
  }

  sendMessage(roomId: string, content: string) {
    this.socket.emit('message', { roomId, content });
  }

  sendTyping(roomId: string) {
    this.socket.emit('typing', roomId);
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach((callback) => callback(data));
  }

  disconnect() {
    this.socket.disconnect();
  }
}

// Usage
const chat = new ChatClient('wss://api.example.com', authToken);
chat.joinRoom('room-123');
chat.on('message', (message) => {
  console.log('New message:', message);
});
chat.sendMessage('room-123', 'Hello everyone!');
```

## Cloudflare Durable Objects

```typescript
// src/chatRoom.ts - Durable Object for WebSocket handling
export class ChatRoom {
  private sessions: Map<WebSocket, { userId: string; username: string }> = new Map();
  private state: DurableObjectState;

  constructor(state: DurableObjectState) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/websocket') {
      if (request.headers.get('Upgrade') !== 'websocket') {
        return new Response('Expected WebSocket', { status: 426 });
      }

      const { 0: client, 1: server } = new WebSocketPair();

      // Get user info from query params
      const userId = url.searchParams.get('userId')!;
      const username = url.searchParams.get('username')!;

      await this.handleSession(server, { userId, username });

      return new Response(null, {
        status: 101,
        webSocket: client,
      });
    }

    return new Response('Not found', { status: 404 });
  }

  async handleSession(webSocket: WebSocket, user: { userId: string; username: string }) {
    webSocket.accept();
    this.sessions.set(webSocket, user);

    // Notify others
    this.broadcast({
      type: 'user-joined',
      userId: user.userId,
      username: user.username,
    }, webSocket);

    webSocket.addEventListener('message', async (event) => {
      const data = JSON.parse(event.data as string);

      switch (data.type) {
        case 'message':
          const message = {
            type: 'message',
            id: crypto.randomUUID(),
            userId: user.userId,
            username: user.username,
            content: data.content,
            timestamp: new Date().toISOString(),
          };

          // Store message
          await this.state.storage.put(`message:${message.id}`, message);

          // Broadcast to all
          this.broadcast(message);
          break;

        case 'typing':
          this.broadcast({
            type: 'user-typing',
            userId: user.userId,
            username: user.username,
          }, webSocket);
          break;
      }
    });

    webSocket.addEventListener('close', () => {
      this.sessions.delete(webSocket);
      this.broadcast({
        type: 'user-left',
        userId: user.userId,
        username: user.username,
      });
    });
  }

  broadcast(message: any, exclude?: WebSocket) {
    const json = JSON.stringify(message);
    for (const [ws] of this.sessions) {
      if (ws !== exclude) {
        ws.send(json);
      }
    }
  }
}

// src/index.ts - Worker entry point
export interface Env {
  CHAT_ROOMS: DurableObjectNamespace;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Route to chat room Durable Object
    if (url.pathname.startsWith('/room/')) {
      const roomId = url.pathname.split('/')[2];
      const id = env.CHAT_ROOMS.idFromName(roomId);
      const room = env.CHAT_ROOMS.get(id);

      const newUrl = new URL(request.url);
      newUrl.pathname = '/websocket';

      return room.fetch(new Request(newUrl, request));
    }

    return new Response('Not found', { status: 404 });
  },
};

export { ChatRoom };
```

### wrangler.toml

```toml
name = "chat-app"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[durable_objects]
bindings = [
  { name = "CHAT_ROOMS", class_name = "ChatRoom" }
]

[[migrations]]
tag = "v1"
new_classes = ["ChatRoom"]
```

## GCP Cloud Run Configuration

### Terraform

```hcl
# cloud_run_websocket.tf

resource "google_cloud_run_v2_service" "websocket" {
  name     = "${var.project_name}-websocket"
  location = var.region

  template {
    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      # Startup probe
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }
    }

    # Enable HTTP/2 for streaming
    annotations = {
      "run.googleapis.com/sessionAffinity" = "true"  # Sticky sessions
    }

    scaling {
      min_instance_count = 1  # Keep warm for WebSocket
      max_instance_count = 10
    }

    # Long timeout for WebSocket connections
    timeout = "3600s"

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Redis for cross-instance pub/sub
resource "google_redis_instance" "main" {
  name           = "${var.project_name}-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = var.region

  authorized_network = google_compute_network.vpc.id
}
```

## AWS ECS with ALB

```hcl
# ecs_websocket.tf

# Application Load Balancer
resource "aws_lb" "websocket" {
  name               = "${var.project_name}-ws-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "production"
}

resource "aws_lb_listener" "websocket" {
  load_balancer_arn = aws_lb.websocket.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.websocket.arn
  }
}

resource "aws_lb_target_group" "websocket" {
  name        = "${var.project_name}-ws-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  # Enable sticky sessions for WebSocket
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400  # 24 hours
    enabled         = true
  }

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 10
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

# ECS Service
resource "aws_ecs_service" "websocket" {
  name            = "${var.project_name}-websocket"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.websocket.arn
  desired_count   = 2  # Multiple instances

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.websocket.arn
    container_name   = "websocket"
    container_port   = 8080
  }
}

# ElastiCache Redis for pub/sub
resource "aws_elasticache_replication_group" "pubsub" {
  replication_group_id = "${var.project_name}-pubsub"
  description          = "Redis for WebSocket pub/sub"

  node_type            = "cache.t3.micro"
  num_cache_clusters   = 2
  port                 = 6379

  engine               = "redis"
  engine_version       = "7.0"

  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  automatic_failover_enabled = true
  multi_az_enabled           = true
}
```

## Cost Breakdown

| Provider | Service | ~100K Concurrent | ~1M Concurrent |
|----------|---------|-----------------|----------------|
| **GCP** | Cloud Run + Redis | ~$200/mo | ~$2,000/mo |
| **AWS** | ECS + ElastiCache | ~$300/mo | ~$2,500/mo |
| **Cloudflare** | Durable Objects | ~$50/mo | ~$500/mo |
| **Fly.io** | Machines + Upstash | ~$100/mo | ~$1,000/mo |

## Best Practices

### Connection Management

```typescript
// Heartbeat to detect dead connections
const HEARTBEAT_INTERVAL = 30000;
const HEARTBEAT_TIMEOUT = 10000;

io.on('connection', (socket) => {
  let heartbeatTimeout: NodeJS.Timeout;

  const resetHeartbeat = () => {
    clearTimeout(heartbeatTimeout);
    heartbeatTimeout = setTimeout(() => {
      socket.disconnect(true);
    }, HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT);
  };

  socket.on('pong', resetHeartbeat);
  resetHeartbeat();

  setInterval(() => {
    socket.emit('ping');
  }, HEARTBEAT_INTERVAL);
});
```

### Rate Limiting

```typescript
import { RateLimiterMemory } from 'rate-limiter-flexible';

const rateLimiter = new RateLimiterMemory({
  points: 10,  // 10 messages
  duration: 1, // per second
});

socket.on('message', async (data) => {
  try {
    await rateLimiter.consume(socket.data.user.id);
    // Process message
  } catch (err) {
    socket.emit('error', { message: 'Rate limit exceeded' });
  }
});
```

## Common Mistakes

1. **No sticky sessions** - WebSocket connections fail when routed to different instances
2. **Missing Redis adapter** - Can't broadcast across multiple instances
3. **No heartbeat** - Dead connections not detected
4. **No reconnection logic** - Clients don't recover from network issues
5. **Blocking event handlers** - Blocks all connections on instance
6. **No rate limiting** - DoS vulnerability
7. **Large payloads** - WebSocket messages should be small
8. **Missing authentication** - Unauthenticated connections accepted
9. **No graceful shutdown** - Connections dropped during deploys
10. **Polling fallback disabled** - Some networks block WebSocket

## Example Configuration

```yaml
# infera.yaml
project_name: chat-app
provider: gcp
region: us-central1

architecture:
  type: websocket_realtime

services:
  websocket:
    runtime: cloud_run
    image: gcr.io/my-project/chat-server
    port: 8080
    min_instances: 1
    max_instances: 10
    session_affinity: true
    timeout: 3600

    env:
      REDIS_URL:
        from_secret: redis-url

  redis:
    type: memorystore
    tier: STANDARD_HA
    memory_gb: 1

networking:
  vpc_connector: true
  allow_unauthenticated: false
```

## Sources

- [Socket.IO Documentation](https://socket.io/docs/v4/)
- [Cloudflare Durable Objects](https://developers.cloudflare.com/durable-objects/)
- [Cloud Run WebSocket Support](https://cloud.google.com/run/docs/triggering/websockets)
- [AWS ALB WebSocket](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-websockets.html)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
