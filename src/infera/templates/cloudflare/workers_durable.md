# Cloudflare Workers + Durable Objects

## Overview

Deploy stateful serverless applications using Durable Objects for strongly consistent, single-threaded state management. Ideal for real-time collaboration, WebSocket connections, game state, and coordination across requests.

## Detection Signals

Use this template when:
- WebSocket connections needed
- Real-time collaboration features
- Strongly consistent state required
- Rate limiting per user
- Distributed coordination
- Live counters or leaderboards

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                 Cloudflare Network                       │
                    │                                                         │
    Client ────────►│   ┌───────────────────────────────────────────────┐     │
    (WebSocket)    │   │              Worker                            │     │
                    │   │                                               │     │
                    │   │  ┌─────────┐     ┌──────────────────────────┐ │     │
                    │   │  │  Route  │────►│  Durable Object Stub     │ │     │
                    │   │  └─────────┘     │  (ID-based routing)      │ │     │
                    │   │                  └───────────┬──────────────┘ │     │
                    │   └────────────────────────────┼─────────────────┘     │
                    │                                │                       │
                    │   ┌────────────────────────────┼───────────────────┐   │
                    │   │                            ▼                   │   │
                    │   │    Durable Object Instance (single-threaded)   │   │
                    │   │    ┌──────────────────────────────────────┐    │   │
                    │   │    │  - In-memory state                   │    │   │
                    │   │    │  - WebSocket connections             │    │   │
                    │   │    │  - Transactional storage             │    │   │
                    │   │    │  - Alarms (scheduled callbacks)      │    │   │
                    │   │    └──────────────────────────────────────┘    │   │
                    │   │                                                │   │
                    │   │    Colocated with state • Strong consistency   │   │
                    │   └────────────────────────────────────────────────┘   │
                    │                                                         │
                    └─────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | Request routing | wrangler.toml |
| Durable Object | State management | Class binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| D1 Database | Persistent queries | Binding |
| KV Namespace | Caching | Binding |
| Analytics Engine | Metrics | Binding |

## Configuration

### wrangler.toml
```toml
name = "durable-app"
main = "src/index.ts"
compatibility_date = "2024-01-01"

# Durable Object bindings
[durable_objects]
bindings = [
  { name = "CHAT_ROOM", class_name = "ChatRoom" },
  { name = "RATE_LIMITER", class_name = "RateLimiter" },
  { name = "COUNTER", class_name = "Counter" }
]

# Migrations (for DO class changes)
[[migrations]]
tag = "v1"
new_classes = ["ChatRoom", "RateLimiter", "Counter"]

# Optional: KV for caching
[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"
```

## Implementation

### Chat Room with WebSockets
```typescript
// src/chat-room.ts
export class ChatRoom {
  private state: DurableObjectState;
  private sessions: Map<WebSocket, { name: string }>;
  private lastTimestamp: number;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.sessions = new Map();
    this.lastTimestamp = 0;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    // Handle WebSocket upgrade
    if (request.headers.get('Upgrade') === 'websocket') {
      return this.handleWebSocket(request);
    }

    // HTTP API for chat history
    if (url.pathname === '/history') {
      const messages = await this.state.storage.list<Message>({
        prefix: 'message:',
        reverse: true,
        limit: 100,
      });
      return Response.json([...messages.values()]);
    }

    return new Response('Expected WebSocket', { status: 400 });
  }

  private async handleWebSocket(request: Request): Promise<Response> {
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    // Get user name from query
    const url = new URL(request.url);
    const name = url.searchParams.get('name') || 'Anonymous';

    // Accept WebSocket
    server.accept();
    this.sessions.set(server, { name });

    // Send chat history
    const history = await this.state.storage.list<Message>({
      prefix: 'message:',
      reverse: true,
      limit: 50,
    });
    server.send(JSON.stringify({
      type: 'history',
      messages: [...history.values()].reverse(),
    }));

    // Announce join
    this.broadcast({ type: 'join', name, timestamp: Date.now() });

    // Handle messages
    server.addEventListener('message', async (event) => {
      const data = JSON.parse(event.data as string);

      if (data.type === 'message') {
        const message: Message = {
          id: `message:${this.nextTimestamp()}`,
          name,
          text: data.text,
          timestamp: Date.now(),
        };

        // Store message
        await this.state.storage.put(message.id, message);

        // Broadcast to all
        this.broadcast({ type: 'message', ...message });
      }
    });

    // Handle disconnect
    server.addEventListener('close', () => {
      this.sessions.delete(server);
      this.broadcast({ type: 'leave', name, timestamp: Date.now() });
    });

    return new Response(null, { status: 101, webSocket: client });
  }

  private broadcast(message: any): void {
    const json = JSON.stringify(message);
    for (const [ws] of this.sessions) {
      try {
        ws.send(json);
      } catch (e) {
        // Remove dead connections
        this.sessions.delete(ws);
      }
    }
  }

  private nextTimestamp(): number {
    const now = Date.now();
    this.lastTimestamp = Math.max(now, this.lastTimestamp + 1);
    return this.lastTimestamp;
  }
}

type Message = {
  id: string;
  name: string;
  text: string;
  timestamp: number;
};
```

### Rate Limiter
```typescript
// src/rate-limiter.ts
export class RateLimiter {
  private state: DurableObjectState;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '100');
    const window = parseInt(url.searchParams.get('window') || '60000');

    // Get current count
    const now = Date.now();
    const windowStart = now - window;

    // Clean old entries
    const entries = await this.state.storage.list<number>({
      prefix: 'req:',
    });

    let count = 0;
    const toDelete: string[] = [];

    for (const [key, timestamp] of entries) {
      if (timestamp < windowStart) {
        toDelete.push(key);
      } else {
        count++;
      }
    }

    // Delete old entries
    if (toDelete.length > 0) {
      await this.state.storage.delete(toDelete);
    }

    // Check limit
    if (count >= limit) {
      return Response.json({
        allowed: false,
        remaining: 0,
        reset: windowStart + window,
      }, { status: 429 });
    }

    // Record request
    await this.state.storage.put(`req:${now}`, now);

    return Response.json({
      allowed: true,
      remaining: limit - count - 1,
      reset: windowStart + window,
    });
  }
}
```

### Distributed Counter
```typescript
// src/counter.ts
export class Counter {
  private state: DurableObjectState;
  private value: number | null = null;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    // Load value on first access
    if (this.value === null) {
      this.value = (await this.state.storage.get<number>('value')) || 0;
    }

    const url = new URL(request.url);
    const method = request.method;

    if (method === 'GET') {
      return Response.json({ value: this.value });
    }

    if (method === 'POST' && url.pathname === '/increment') {
      const amount = parseInt(url.searchParams.get('amount') || '1');
      this.value += amount;
      await this.state.storage.put('value', this.value);
      return Response.json({ value: this.value });
    }

    if (method === 'POST' && url.pathname === '/decrement') {
      const amount = parseInt(url.searchParams.get('amount') || '1');
      this.value -= amount;
      await this.state.storage.put('value', this.value);
      return Response.json({ value: this.value });
    }

    if (method === 'POST' && url.pathname === '/reset') {
      this.value = 0;
      await this.state.storage.put('value', 0);
      return Response.json({ value: 0 });
    }

    return new Response('Not found', { status: 404 });
  }
}
```

### Main Worker (Router)
```typescript
// src/index.ts
import { Hono } from 'hono';

type Bindings = {
  CHAT_ROOM: DurableObjectNamespace;
  RATE_LIMITER: DurableObjectNamespace;
  COUNTER: DurableObjectNamespace;
};

const app = new Hono<{ Bindings: Bindings }>();

// Chat room routes
app.all('/room/:roomId/*', async (c) => {
  const roomId = c.req.param('roomId');

  // Get or create DO instance by name
  const id = c.env.CHAT_ROOM.idFromName(roomId);
  const stub = c.env.CHAT_ROOM.get(id);

  // Forward request
  const url = new URL(c.req.url);
  url.pathname = url.pathname.replace(`/room/${roomId}`, '');

  return stub.fetch(new Request(url.toString(), c.req.raw));
});

// Rate limiter
app.get('/api/*', async (c, next) => {
  const ip = c.req.header('CF-Connecting-IP') || 'unknown';

  // Get rate limiter for this IP
  const id = c.env.RATE_LIMITER.idFromName(ip);
  const limiter = c.env.RATE_LIMITER.get(id);

  const response = await limiter.fetch(
    new Request('http://limiter/?limit=100&window=60000')
  );
  const result = await response.json<{ allowed: boolean; remaining: number }>();

  if (!result.allowed) {
    return c.json({ error: 'Rate limited' }, 429);
  }

  c.header('X-RateLimit-Remaining', result.remaining.toString());
  return next();
});

// Counter routes
app.get('/counter/:name', async (c) => {
  const name = c.req.param('name');
  const id = c.env.COUNTER.idFromName(name);
  const counter = c.env.COUNTER.get(id);
  return counter.fetch(c.req.raw);
});

app.post('/counter/:name/:action', async (c) => {
  const name = c.req.param('name');
  const action = c.req.param('action');
  const id = c.env.COUNTER.idFromName(name);
  const counter = c.env.COUNTER.get(id);

  const url = new URL(c.req.url);
  url.pathname = `/${action}`;

  return counter.fetch(new Request(url.toString(), { method: 'POST' }));
});

export default app;
export { ChatRoom } from './chat-room';
export { RateLimiter } from './rate-limiter';
export { Counter } from './counter';
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Deploy (includes DO classes)
npx wrangler deploy

# Test WebSocket (using websocat)
websocat "wss://your-app.workers.dev/room/test-room?name=Alice"

# Test counter
curl https://your-app.workers.dev/counter/visits
curl -X POST https://your-app.workers.dev/counter/visits/increment
```

## Best Practices

### State Management
1. Use in-memory caching for hot data
2. Persist critical state to storage
3. Keep DO instances small and focused
4. Use alarms for scheduled tasks

### Scalability
1. Partition by natural boundaries (room, user, resource)
2. Avoid single global DO for hot paths
3. Use ID from name for predictable routing
4. Consider DO location hints

### Reliability
1. Handle WebSocket reconnection gracefully
2. Implement heartbeat/ping for connections
3. Use storage transactions for consistency
4. Plan for DO restarts

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Requests | 1M/month | $0.15/million |
| Duration | 400k GB-s | $12.50/million GB-s |
| Storage reads | 1M/month | $0.20/million |
| Storage writes | 1M/month | $1.00/million |
| Storage | 1GB | $0.20/GB |

### Example Costs
| Scale | Requests | Duration | Cost |
|-------|----------|----------|------|
| Small | 1M | 100k GB-s | ~$2 |
| Medium | 10M | 1M GB-s | ~$15 |
| Large | 100M | 10M GB-s | ~$140 |

## Common Mistakes

1. **Single global DO**: Creates bottleneck
2. **Not handling reconnects**: Lost WebSocket state
3. **Large state**: Keep DOs focused
4. **Missing error handling**: DO crashes lose connections
5. **No migrations**: Class changes break existing DOs
6. **Blocking operations**: DOs are single-threaded

## Example Configuration

```yaml
project_name: realtime-app
provider: cloudflare
architecture_type: workers_durable

resources:
  - id: main-worker
    type: cloudflare_worker
    name: realtime-app
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"
      durable_objects:
        - name: CHAT_ROOM
          class_name: ChatRoom
        - name: RATE_LIMITER
          class_name: RateLimiter
        - name: COUNTER
          class_name: Counter
```

## Sources

- [Durable Objects Documentation](https://developers.cloudflare.com/durable-objects)
- [WebSockets with DO](https://developers.cloudflare.com/durable-objects/examples/websocket-hibernation)
- [DO Best Practices](https://developers.cloudflare.com/durable-objects/best-practices)
