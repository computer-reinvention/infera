# Static Site Hosting

## Overview

This template is for hosting static websites including SPAs (Single Page Applications), static site generators, and simple HTML/CSS/JS sites. It uses Cloud Storage for file hosting with optional CDN for global distribution.

## Detection Signals

Use this template when you detect:

- package.json with React, Vue, Angular, or Svelte (without SSR)
- Static HTML files in `public/` or root directory
- Build commands that produce static output (`npm run build` → `dist/` or `build/`)
- Next.js with `output: 'export'` in config
- No server-side rendering or API routes

## Resources Needed

### Required

- **Cloud Storage Bucket**: Public bucket for hosting static files
  - Enable website configuration
  - Set index document (index.html)
  - Set 404 document (404.html or index.html for SPAs)

### Optional

- **Cloud CDN**: For global distribution and caching
  - Recommended for production sites with global audience
  - Adds ~$0.02-0.08/GB egress cost
- **Cloud DNS**: For custom domain
- **SSL Certificate**: Managed certificate (free with Cloud CDN)

## Best Practices

### Storage Configuration

1. Enable uniform bucket-level access for simpler IAM
2. Set appropriate CORS headers if loading assets from different domains
3. Use object versioning for rollback capability
4. Set lifecycle rules to delete old versions after 30 days

### Caching Strategy

1. **HTML files**: Short cache (5 minutes or no-cache)
   - Ensures users get latest content
2. **Hashed assets** (main.abc123.js): Long cache (1 year)
   - Safe because filename changes when content changes
3. **Images/fonts**: Medium cache (1 week to 1 month)

### Deployment

1. Use `gsutil -m rsync` for efficient delta uploads
2. Invalidate CDN cache after deployment for HTML files
3. Consider blue-green deployments with bucket versioning

## Cost Optimization

| Resource   | Typical Cost   | Notes              |
| ---------- | -------------- | ------------------ |
| Storage    | $0.02/GB/month | Standard storage   |
| Operations | $0.004/10k ops | Class A (writes)   |
| Egress     | $0.12/GB       | Without CDN        |
| CDN Egress | $0.02-0.08/GB  | With CDN (cheaper) |

**Free Tier**: 5GB storage, 1GB egress/month

**Tips**:

- Standard storage is sufficient (not Nearline/Coldline)
- CDN reduces egress costs for high-traffic sites
- Enable compression (gzip) to reduce transfer size

## Common Mistakes

1. **Forgetting SPA routing**: Set 404 page to index.html for client-side routing
2. **Missing CORS headers**: Required for fonts and API calls
3. **No cache invalidation**: Users see stale content after deploys
4. **Over-provisioning**: Static sites don't need compute instances

## GCP-Specific Implementation

### Bucket Configuration

```yaml
resource:
  type: cloud_storage
  name: ${project}-static
  config:
    location: US # or specific region
    storage_class: STANDARD
    uniform_bucket_level_access: true
    website:
      main_page_suffix: index.html
      not_found_page: index.html # For SPA routing
    cors:
      - origin: ["*"]
        method: ["GET", "HEAD"]
        response_header: ["Content-Type"]
        max_age_seconds: 3600
```

### CDN Configuration (Optional)

```yaml
resource:
  type: cloud_cdn
  name: ${project}-cdn
  config:
    backend_bucket: ${project}-static
    cache_mode: CACHE_ALL_STATIC
    default_ttl: 3600
    max_ttl: 86400
    negative_caching: true
```

### IAM for Public Access

```yaml
iam_binding:
  bucket: ${project}-static
  role: roles/storage.objectViewer
  members:
    - allUsers
```

## Deployment Commands

```bash
# Build the site
npm run build

# Sync to bucket (efficient delta upload)
gsutil -m rsync -r -d ./dist gs://${project}-static

# Invalidate CDN cache (if using CDN)
gcloud compute url-maps invalidate-cdn-cache ${project}-cdn \
  --path "/*"
```

## Example Configuration

For a React SPA with custom domain:

```yaml
project_name: my-portfolio
provider: gcp
region: us-central1
architecture_type: static_site

resources:
  - id: static-bucket
    type: cloud_storage
    name: my-portfolio-static
    provider: gcp
    config:
      location: US
      uniform_bucket_level_access: true
      website:
        main_page_suffix: index.html
        not_found_page: index.html

  - id: cdn
    type: cloud_cdn
    name: my-portfolio-cdn
    provider: gcp
    config:
      backend_bucket: my-portfolio-static
      cache_mode: CACHE_ALL_STATIC
    depends_on:
      - static-bucket

domain:
  enabled: true
  name: portfolio.example.com
  ssl: true
```

## Estimated Costs

For a typical portfolio/blog site (1GB storage, 10GB/month traffic):

- Storage: ~$0.02/month
- CDN Egress: ~$0.80/month
- **Total: ~$1-2/month**

For a high-traffic marketing site (5GB storage, 100GB/month traffic):

- Storage: ~$0.10/month
- CDN Egress: ~$8/month
- **Total: ~$10/month**
