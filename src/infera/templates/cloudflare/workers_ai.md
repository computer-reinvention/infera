# Cloudflare Workers AI

## Overview

Deploy AI-powered applications using Workers AI for serverless machine learning inference at the edge. Access LLMs, image models, embeddings, and more without managing infrastructure.

## Detection Signals

Use this template when:
- AI/ML inference requirements
- LLM-powered features (chatbots, content generation)
- Image generation or analysis
- Text embeddings for search
- Speech-to-text conversion
- Translation services

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────┐   │
                    │   │              Worker                      │   │
                    │   │                                         │   │
                    │   │  ┌─────────┐       ┌─────────────────┐  │   │
                    │   │  │  API    │──────►│   Workers AI    │  │   │
                    │   │  │ Logic   │       │                 │  │   │
                    │   │  └─────────┘       │  ┌───────────┐  │  │   │
                    │   │                    │  │  Models   │  │  │   │
                    │   │                    │  │ - LLMs    │  │  │   │
                    │   │                    │  │ - Images  │  │  │   │
                    │   │                    │  │ - Audio   │  │  │   │
                    │   │                    │  │ - Embed   │  │  │   │
                    │   │                    │  └───────────┘  │  │   │
                    │   │                    └─────────────────┘  │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   GPU inference at edge • Pay per request       │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | API hosting | wrangler.toml |
| AI Binding | Model access | Binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Vectorize | Vector storage | Binding |
| D1 Database | Conversation history | Binding |
| KV Namespace | Response caching | Binding |

## Configuration

### wrangler.toml
```toml
name = "ai-app"
main = "src/index.ts"
compatibility_date = "2024-01-01"

# AI binding
[ai]
binding = "AI"

# Optional: Vectorize for embeddings
[[vectorize]]
binding = "VECTORIZE"
index_name = "my-embeddings"

# Optional: D1 for conversation history
[[d1_databases]]
binding = "DB"
database_name = "conversations"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

# Optional: KV for caching
[[kv_namespaces]]
binding = "CACHE"
id = "xxxxxxxxxxxxxxxxxxxxx"
```

## Available Models

### Text Generation (LLMs)
| Model | Description | Best For |
|-------|-------------|----------|
| `@cf/meta/llama-3.1-8b-instruct` | Llama 3.1 8B | General chat, fast |
| `@cf/meta/llama-3.1-70b-instruct` | Llama 3.1 70B | Complex tasks |
| `@cf/mistral/mistral-7b-instruct-v0.2` | Mistral 7B | Balanced |
| `@cf/qwen/qwen1.5-14b-chat-awq` | Qwen 14B | Multilingual |

### Image Generation
| Model | Description |
|-------|-------------|
| `@cf/stabilityai/stable-diffusion-xl-base-1.0` | SDXL |
| `@cf/bytedance/stable-diffusion-xl-lightning` | Fast SDXL |
| `@cf/lykon/dreamshaper-8-lcm` | Dreamshaper |

### Embeddings
| Model | Description |
|-------|-------------|
| `@cf/baai/bge-base-en-v1.5` | English embeddings |
| `@cf/baai/bge-large-en-v1.5` | Large embeddings |

### Other
| Model | Type |
|-------|------|
| `@cf/openai/whisper` | Speech-to-text |
| `@cf/meta/m2m100-1.2b` | Translation |
| `@cf/microsoft/resnet-50` | Image classification |

## Implementation

### Chat API
```typescript
// src/index.ts
import { Hono } from 'hono';

type Bindings = {
  AI: Ai;
  DB: D1Database;
};

const app = new Hono<{ Bindings: Bindings }>();

// Simple chat completion
app.post('/api/chat', async (c) => {
  const { message, conversationId } = await c.req.json();

  // Get conversation history
  let messages: { role: string; content: string }[] = [];

  if (conversationId) {
    const history = await c.env.DB.prepare(`
      SELECT role, content FROM messages
      WHERE conversation_id = ?
      ORDER BY created_at ASC
      LIMIT 20
    `).bind(conversationId).all();

    messages = history.results as any[];
  }

  // Add user message
  messages.push({ role: 'user', content: message });

  // Generate response
  const response = await c.env.AI.run(
    '@cf/meta/llama-3.1-8b-instruct',
    {
      messages: [
        {
          role: 'system',
          content: 'You are a helpful assistant. Be concise and accurate.',
        },
        ...messages,
      ],
      max_tokens: 1024,
      temperature: 0.7,
    }
  );

  const assistantMessage = response.response;

  // Save to history
  if (conversationId) {
    await c.env.DB.batch([
      c.env.DB.prepare(`
        INSERT INTO messages (conversation_id, role, content, created_at)
        VALUES (?, 'user', ?, datetime('now'))
      `).bind(conversationId, message),
      c.env.DB.prepare(`
        INSERT INTO messages (conversation_id, role, content, created_at)
        VALUES (?, 'assistant', ?, datetime('now'))
      `).bind(conversationId, assistantMessage),
    ]);
  }

  return c.json({
    message: assistantMessage,
    conversationId,
  });
});

// Streaming chat
app.post('/api/chat/stream', async (c) => {
  const { message } = await c.req.json();

  const stream = await c.env.AI.run(
    '@cf/meta/llama-3.1-8b-instruct',
    {
      messages: [
        { role: 'system', content: 'You are a helpful assistant.' },
        { role: 'user', content: message },
      ],
      stream: true,
    }
  );

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
  });
});

export default app;
```

### Image Generation
```typescript
// src/images.ts
import { Hono } from 'hono';

type Bindings = {
  AI: Ai;
  STORAGE: R2Bucket;
};

const app = new Hono<{ Bindings: Bindings }>();

app.post('/api/generate-image', async (c) => {
  const { prompt, negativePrompt, steps = 20 } = await c.req.json();

  // Generate image
  const image = await c.env.AI.run(
    '@cf/stabilityai/stable-diffusion-xl-base-1.0',
    {
      prompt,
      negative_prompt: negativePrompt,
      num_steps: steps,
    }
  );

  // Save to R2
  const key = `generated/${Date.now()}.png`;
  await c.env.STORAGE.put(key, image, {
    httpMetadata: { contentType: 'image/png' },
  });

  return c.json({
    url: `/api/images/${key}`,
    prompt,
  });
});

// Fast image generation
app.post('/api/generate-image/fast', async (c) => {
  const { prompt } = await c.req.json();

  const image = await c.env.AI.run(
    '@cf/bytedance/stable-diffusion-xl-lightning',
    {
      prompt,
      num_steps: 4, // Lightning model is fast
    }
  );

  return new Response(image, {
    headers: { 'Content-Type': 'image/png' },
  });
});

export default app;
```

### Embeddings and Vector Search
```typescript
// src/embeddings.ts
import { Hono } from 'hono';

type Bindings = {
  AI: Ai;
  VECTORIZE: VectorizeIndex;
  DB: D1Database;
};

const app = new Hono<{ Bindings: Bindings }>();

// Index a document
app.post('/api/documents', async (c) => {
  const { id, title, content } = await c.req.json();

  // Generate embeddings
  const embeddings = await c.env.AI.run(
    '@cf/baai/bge-base-en-v1.5',
    { text: [content] }
  );

  // Store in Vectorize
  await c.env.VECTORIZE.upsert([{
    id,
    values: embeddings.data[0],
    metadata: { title },
  }]);

  // Store full content in D1
  await c.env.DB.prepare(`
    INSERT OR REPLACE INTO documents (id, title, content)
    VALUES (?, ?, ?)
  `).bind(id, title, content).run();

  return c.json({ id, indexed: true });
});

// Semantic search
app.get('/api/search', async (c) => {
  const query = c.req.query('q');
  if (!query) {
    return c.json({ error: 'Query required' }, 400);
  }

  // Generate query embedding
  const queryEmbedding = await c.env.AI.run(
    '@cf/baai/bge-base-en-v1.5',
    { text: [query] }
  );

  // Search Vectorize
  const results = await c.env.VECTORIZE.query(
    queryEmbedding.data[0],
    { topK: 10 }
  );

  // Fetch full documents
  const ids = results.matches.map(m => m.id);
  const { results: documents } = await c.env.DB.prepare(`
    SELECT * FROM documents WHERE id IN (${ids.map(() => '?').join(',')})
  `).bind(...ids).all();

  return c.json({
    results: results.matches.map(match => ({
      ...match,
      document: documents.find(d => d.id === match.id),
    })),
  });
});

// RAG (Retrieval-Augmented Generation)
app.post('/api/ask', async (c) => {
  const { question } = await c.req.json();

  // 1. Embed the question
  const questionEmbedding = await c.env.AI.run(
    '@cf/baai/bge-base-en-v1.5',
    { text: [question] }
  );

  // 2. Find relevant documents
  const searchResults = await c.env.VECTORIZE.query(
    questionEmbedding.data[0],
    { topK: 3 }
  );

  const ids = searchResults.matches.map(m => m.id);
  const { results: documents } = await c.env.DB.prepare(`
    SELECT content FROM documents WHERE id IN (${ids.map(() => '?').join(',')})
  `).bind(...ids).all();

  const context = documents.map(d => d.content).join('\n\n');

  // 3. Generate answer with context
  const response = await c.env.AI.run(
    '@cf/meta/llama-3.1-8b-instruct',
    {
      messages: [
        {
          role: 'system',
          content: `Answer questions based on the provided context. If the context doesn't contain relevant information, say so.

Context:
${context}`,
        },
        { role: 'user', content: question },
      ],
    }
  );

  return c.json({
    answer: response.response,
    sources: searchResults.matches.map(m => m.id),
  });
});

export default app;
```

### Speech-to-Text
```typescript
// src/audio.ts
import { Hono } from 'hono';

type Bindings = {
  AI: Ai;
};

const app = new Hono<{ Bindings: Bindings }>();

app.post('/api/transcribe', async (c) => {
  const formData = await c.req.formData();
  const audio = formData.get('audio') as File;

  if (!audio) {
    return c.json({ error: 'Audio file required' }, 400);
  }

  const arrayBuffer = await audio.arrayBuffer();

  const result = await c.env.AI.run(
    '@cf/openai/whisper',
    { audio: [...new Uint8Array(arrayBuffer)] }
  );

  return c.json({
    text: result.text,
    vtt: result.vtt, // WebVTT subtitles
  });
});

export default app;
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create Vectorize index (if using)
npx wrangler vectorize create my-embeddings --dimensions=768 --metric=cosine

# Deploy
npx wrangler deploy

# Test chat
curl -X POST https://ai-app.workers.dev/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'

# Test image generation
curl -X POST https://ai-app.workers.dev/api/generate-image/fast \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A sunset over mountains"}' \
  --output image.png
```

## Best Practices

### Performance
1. Use streaming for long responses
2. Cache common queries in KV
3. Choose appropriate model size
4. Use batch operations when possible

### Cost Optimization
1. Use smaller models when sufficient
2. Limit max_tokens appropriately
3. Cache embeddings for repeated queries
4. Use Lightning models for fast inference

### Quality
1. Write clear, specific prompts
2. Use system prompts for consistent behavior
3. Implement content moderation
4. Test across different inputs

## Cost Breakdown

| Model Type | Price |
|------------|-------|
| Text generation | $0.011/1k tokens |
| Image generation | $0.03/image |
| Embeddings | $0.00001/1k tokens |
| Speech-to-text | $0.0005/second |

### Example Costs
| Usage | Monthly Cost |
|-------|--------------|
| 100k chat messages | ~$15 |
| 10k images | ~$300 |
| 1M embedding tokens | ~$0.01 |

## Common Mistakes

1. **Ignoring rate limits**: Plan for retries
2. **No streaming**: Users wait too long
3. **Wrong model**: Using large model for simple tasks
4. **Missing moderation**: No content filtering
5. **No caching**: Regenerating same content
6. **Unbounded tokens**: No max_tokens limit

## Example Configuration

```yaml
project_name: ai-app
provider: cloudflare
architecture_type: workers_ai

resources:
  - id: ai-worker
    type: cloudflare_worker
    name: ai-app
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"
      ai_binding: AI

  - id: embeddings-index
    type: cloudflare_vectorize
    name: my-embeddings
    provider: cloudflare
    config:
      binding: VECTORIZE
      dimensions: 768
      metric: cosine

  - id: conversations-db
    type: cloudflare_d1
    name: conversations
    provider: cloudflare
    config:
      binding: DB
```

## Sources

- [Workers AI Documentation](https://developers.cloudflare.com/workers-ai)
- [Available Models](https://developers.cloudflare.com/workers-ai/models)
- [Vectorize Documentation](https://developers.cloudflare.com/vectorize)
