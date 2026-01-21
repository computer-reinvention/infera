# Cloudflare Workers + R2 Object Storage

## Overview

Deploy serverless APIs with R2, Cloudflare's S3-compatible object storage. R2 provides zero egress fees, automatic global distribution, and seamless Workers integration. Ideal for file uploads, media storage, and data lakes.

## Detection Signals

Use this template when:
- File upload/download requirements
- Image/media storage needed
- S3-compatible API needed
- Large object storage (> 25MB)
- Zero egress cost requirements
- Static asset hosting

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │           Cloudflare Global Network              │
                    │                                                 │
                    │   ┌─────────────────────────────────────────┐   │
                    │   │              Worker                      │   │
    Internet ──────►│   │                                         │   │
         │         │   │  ┌─────────┐       ┌─────────────────┐  │   │
    Upload/        │   │  │  API    │◄─────►│   R2 Bucket     │  │   │
    Download       │   │  │ Logic   │       │                 │  │   │
                    │   │  └─────────┘       │  ┌───────────┐  │  │   │
                    │   │                    │  │  Objects  │  │  │   │
                    │   │                    │  │  - Files  │  │  │   │
                    │   │                    │  │  - Images │  │  │   │
                    │   │                    │  │  - Videos │  │  │   │
                    │   │                    │  └───────────┘  │  │   │
                    │   │                    └─────────────────┘  │   │
                    │   └─────────────────────────────────────────┘   │
                    │                                                 │
                    │   S3-compatible • Zero egress fees              │
                    └─────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Worker | API hosting | wrangler.toml |
| R2 Bucket | Object storage | Binding |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Custom Domain | Public bucket access | R2 custom domain |
| D1 Database | Metadata storage | Binding |
| KV Namespace | URL signing keys | Binding |

## Configuration

### wrangler.toml
```toml
name = "my-r2-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

# R2 Bucket binding
[[r2_buckets]]
binding = "STORAGE"
bucket_name = "my-bucket"

# Preview bucket for development
[[r2_buckets]]
binding = "STORAGE"
bucket_name = "my-bucket-preview"
preview_bucket_name = "my-bucket-preview"

# Optional: D1 for metadata
[[d1_databases]]
binding = "DB"
database_name = "files-metadata"
database_id = "xxxxxxxxxxxxxxxxxxxxx"

[vars]
MAX_FILE_SIZE = "104857600"  # 100MB
ALLOWED_TYPES = "image/jpeg,image/png,image/webp,application/pdf"
```

## Implementation

### File Upload API
```typescript
// src/index.ts
import { Hono } from 'hono';
import { nanoid } from 'nanoid';

type Bindings = {
  STORAGE: R2Bucket;
  DB: D1Database;
  MAX_FILE_SIZE: string;
  ALLOWED_TYPES: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Upload file
app.post('/api/upload', async (c) => {
  const formData = await c.req.formData();
  const file = formData.get('file') as File | null;

  if (!file) {
    return c.json({ error: 'No file provided' }, 400);
  }

  // Validate file size
  const maxSize = parseInt(c.env.MAX_FILE_SIZE);
  if (file.size > maxSize) {
    return c.json({
      error: `File too large. Max size: ${maxSize / 1024 / 1024}MB`
    }, 400);
  }

  // Validate file type
  const allowedTypes = c.env.ALLOWED_TYPES.split(',');
  if (!allowedTypes.includes(file.type)) {
    return c.json({
      error: `Invalid file type. Allowed: ${allowedTypes.join(', ')}`
    }, 400);
  }

  // Generate unique key
  const ext = file.name.split('.').pop();
  const key = `uploads/${nanoid()}${ext ? `.${ext}` : ''}`;

  // Upload to R2
  await c.env.STORAGE.put(key, file.stream(), {
    httpMetadata: {
      contentType: file.type,
    },
    customMetadata: {
      originalName: file.name,
      uploadedAt: new Date().toISOString(),
    },
  });

  // Store metadata in D1
  await c.env.DB.prepare(`
    INSERT INTO files (key, original_name, content_type, size, created_at)
    VALUES (?, ?, ?, ?, ?)
  `).bind(key, file.name, file.type, file.size, new Date().toISOString()).run();

  return c.json({
    key,
    url: `/api/files/${key}`,
    size: file.size,
    contentType: file.type,
  }, 201);
});

// Get file
app.get('/api/files/:key{.+}', async (c) => {
  const key = c.req.param('key');

  const object = await c.env.STORAGE.get(key);

  if (!object) {
    return c.json({ error: 'File not found' }, 404);
  }

  const headers = new Headers();
  headers.set('Content-Type', object.httpMetadata?.contentType || 'application/octet-stream');
  headers.set('Content-Length', object.size.toString());
  headers.set('ETag', object.etag);

  // Cache for 1 hour
  headers.set('Cache-Control', 'public, max-age=3600');

  return new Response(object.body, { headers });
});

// Delete file
app.delete('/api/files/:key{.+}', async (c) => {
  const key = c.req.param('key');

  await c.env.STORAGE.delete(key);
  await c.env.DB.prepare('DELETE FROM files WHERE key = ?').bind(key).run();

  return c.body(null, 204);
});

// List files
app.get('/api/files', async (c) => {
  const prefix = c.req.query('prefix') || '';
  const cursor = c.req.query('cursor');
  const limit = parseInt(c.req.query('limit') || '100');

  const listed = await c.env.STORAGE.list({
    prefix,
    cursor,
    limit,
  });

  return c.json({
    objects: listed.objects.map(obj => ({
      key: obj.key,
      size: obj.size,
      etag: obj.etag,
      uploaded: obj.uploaded,
    })),
    truncated: listed.truncated,
    cursor: listed.cursor,
  });
});

export default app;
```

### Presigned URLs (for direct uploads)
```typescript
// src/presigned.ts
import { Hono } from 'hono';
import { nanoid } from 'nanoid';

type Bindings = {
  STORAGE: R2Bucket;
  SIGNING_SECRET: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Generate presigned URL for upload
app.post('/api/presign/upload', async (c) => {
  const { filename, contentType } = await c.req.json();

  const ext = filename.split('.').pop();
  const key = `uploads/${nanoid()}${ext ? `.${ext}` : ''}`;
  const expiresIn = 3600; // 1 hour

  // Create a signed URL token
  const expires = Math.floor(Date.now() / 1000) + expiresIn;
  const signature = await signUrl(key, expires, c.env.SIGNING_SECRET);

  return c.json({
    uploadUrl: `/api/direct-upload/${key}?expires=${expires}&signature=${signature}`,
    key,
    expiresIn,
  });
});

// Direct upload endpoint (validates signature)
app.put('/api/direct-upload/:key{.+}', async (c) => {
  const key = c.req.param('key');
  const expires = parseInt(c.req.query('expires') || '0');
  const signature = c.req.query('signature') || '';

  // Validate signature
  const expectedSig = await signUrl(key, expires, c.env.SIGNING_SECRET);
  if (signature !== expectedSig) {
    return c.json({ error: 'Invalid signature' }, 403);
  }

  // Check expiration
  if (Date.now() / 1000 > expires) {
    return c.json({ error: 'URL expired' }, 403);
  }

  // Upload
  const body = await c.req.arrayBuffer();
  const contentType = c.req.header('Content-Type') || 'application/octet-stream';

  await c.env.STORAGE.put(key, body, {
    httpMetadata: { contentType },
  });

  return c.json({ key, size: body.byteLength });
});

async function signUrl(key: string, expires: number, secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(`${key}:${expires}`);
  const keyData = encoder.encode(secret);

  const cryptoKey = await crypto.subtle.importKey(
    'raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', cryptoKey, data);
  return btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export default app;
```

### Image Processing
```typescript
// src/images.ts
import { Hono } from 'hono';

type Bindings = {
  STORAGE: R2Bucket;
};

const app = new Hono<{ Bindings: Bindings }>();

// Get image with transformations (using Cloudflare Images)
app.get('/api/images/:key{.+}', async (c) => {
  const key = c.req.param('key');
  const width = c.req.query('w');
  const height = c.req.query('h');
  const format = c.req.query('format');
  const quality = c.req.query('quality');

  const object = await c.env.STORAGE.get(key);
  if (!object) {
    return c.json({ error: 'Image not found' }, 404);
  }

  // If no transformations, return original
  if (!width && !height && !format && !quality) {
    return new Response(object.body, {
      headers: {
        'Content-Type': object.httpMetadata?.contentType || 'image/jpeg',
        'Cache-Control': 'public, max-age=31536000',
      },
    });
  }

  // Build Cloudflare Image Resizing URL
  const options: string[] = [];
  if (width) options.push(`width=${width}`);
  if (height) options.push(`height=${height}`);
  if (format) options.push(`format=${format}`);
  if (quality) options.push(`quality=${quality}`);
  options.push('fit=contain');

  // Redirect to image resizing service
  const imageUrl = `https://example.com/cdn-cgi/image/${options.join(',')}/${key}`;

  return c.redirect(imageUrl);
});

export default app;
```

## Deployment Commands

```bash
# Login
npx wrangler login

# Create R2 bucket
npx wrangler r2 bucket create my-bucket

# List buckets
npx wrangler r2 bucket list

# Upload file directly
npx wrangler r2 object put my-bucket/test.txt --file=./test.txt

# Get file info
npx wrangler r2 object get my-bucket/test.txt

# Delete file
npx wrangler r2 object delete my-bucket/test.txt

# Enable public access (custom domain)
# Configure in Cloudflare dashboard

# Deploy
npx wrangler deploy
```

## Best Practices

### File Organization
1. Use prefixes for logical grouping (uploads/, images/, documents/)
2. Include timestamps or IDs in keys for uniqueness
3. Store metadata in D1 for search/filtering
4. Use consistent naming conventions

### Performance
1. Stream large files instead of buffering
2. Use multipart uploads for files > 100MB
3. Set appropriate Cache-Control headers
4. Use presigned URLs for direct client uploads

### Security
1. Validate file types and sizes
2. Use presigned URLs with short expiration
3. Implement access control in Workers
4. Scan uploaded files for malware

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Storage | 10GB | $0.015/GB/month |
| Class A ops (writes) | 1M/month | $4.50/million |
| Class B ops (reads) | 10M/month | $0.36/million |
| Egress | **FREE** | **FREE** |

### Example Costs
| Scale | Storage | Writes | Reads | Cost |
|-------|---------|--------|-------|------|
| Small | 50GB | 100k | 1M | ~$0.79 |
| Medium | 500GB | 1M | 10M | ~$8.25 |
| Large | 5TB | 10M | 100M | ~$117 |

### R2 vs S3 Comparison
| | R2 | S3 |
|---|---|---|
| Storage | $0.015/GB | $0.023/GB |
| Egress | **FREE** | $0.09/GB |
| Write ops | $4.50/M | $5.00/M |
| Read ops | $0.36/M | $0.40/M |

## Common Mistakes

1. **Not streaming**: Loading entire file into memory
2. **Missing validation**: No file size/type checks
3. **Wrong content-type**: Not setting httpMetadata
4. **No error handling**: R2 operations can fail
5. **Missing CORS**: Direct browser uploads fail
6. **Inefficient listing**: Not using pagination

## Example Configuration

```yaml
project_name: my-r2-api
provider: cloudflare
architecture_type: workers_r2

resources:
  - id: api-worker
    type: cloudflare_worker
    name: my-r2-api
    provider: cloudflare
    config:
      main: src/index.ts
      compatibility_date: "2024-01-01"

  - id: storage
    type: cloudflare_r2
    name: my-bucket
    provider: cloudflare
    config:
      binding: STORAGE

  - id: metadata-db
    type: cloudflare_d1
    name: files-metadata
    provider: cloudflare
    config:
      binding: DB
```

## Sources

- [R2 Documentation](https://developers.cloudflare.com/r2)
- [R2 Workers API](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
- [R2 Pricing](https://developers.cloudflare.com/r2/pricing/)
