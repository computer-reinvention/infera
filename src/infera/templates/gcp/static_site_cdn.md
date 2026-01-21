# GCP Static Site with CDN

## Overview

Deploy static websites and SPAs on Cloud Storage with Cloud CDN for global distribution. Ideal for React, Vue, Angular, or any static site generator output requiring fast global delivery and minimal cost.

## Detection Signals

Use this template when:
- Static build output (dist/, build/, out/, public/)
- No server-side rendering required
- React, Vue, Angular, Svelte (static mode)
- Static site generators (Hugo, Gatsby, Astro, 11ty)
- Simple HTML/CSS/JS websites

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │          Cloud CDN                   │
    Internet ──────────►│  ┌─────────────────────────────────┐ │
         │             │  │    Global Edge Locations         │ │
    Global Load        │  │    (Cached Content)              │ │
    Balancer           │  └───────────────┬─────────────────┘ │
                        └──────────────────┼───────────────────┘
                                          │ Cache Miss
                                          ▼
                        ┌─────────────────────────────────────┐
                        │         Cloud Storage               │
                        │         (Origin)                    │
                        │   ┌───────────────────────────┐     │
                        │   │  index.html               │     │
                        │   │  static/js/*.js           │     │
                        │   │  static/css/*.css         │     │
                        │   │  assets/images/*          │     │
                        │   └───────────────────────────┘     │
                        └─────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Terraform Resource |
|----------|---------|-------------------|
| Cloud Storage Bucket | File hosting | `google_storage_bucket` |
| Backend Bucket | CDN origin | `google_compute_backend_bucket` |
| URL Map | Routing | `google_compute_url_map` |

### Optional
| Resource | When to Add | Terraform Resource |
|----------|-------------|-------------------|
| Cloud CDN | Global caching | Enabled on backend bucket |
| Global Load Balancer | HTTPS/custom domain | `google_compute_global_address` |
| SSL Certificate | HTTPS | `google_compute_managed_ssl_certificate` |
| Cloud DNS | Domain management | `google_dns_managed_zone` |

## Configuration

### Terraform Variables
```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Cloud Storage bucket name"
  type        = string
}

variable "domain" {
  description = "Custom domain (optional)"
  type        = string
  default     = ""
}
```

### Terraform Resources
```hcl
# Cloud Storage Bucket
resource "google_storage_bucket" "website" {
  name          = var.bucket_name
  location      = "US"  # Multi-region for best availability
  force_destroy = true

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"  # SPA fallback
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Make bucket public
resource "google_storage_bucket_iam_member" "public" {
  bucket = google_storage_bucket.website.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Backend bucket with CDN
resource "google_compute_backend_bucket" "cdn" {
  name        = "${var.bucket_name}-backend"
  bucket_name = google_storage_bucket.website.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching  = true

    cache_key_policy {
      include_host         = true
      include_protocol     = true
      include_query_string = false
    }
  }
}

# URL Map
resource "google_compute_url_map" "website" {
  name            = "${var.bucket_name}-url-map"
  default_service = google_compute_backend_bucket.cdn.id
}

# HTTPS Proxy
resource "google_compute_target_https_proxy" "website" {
  name             = "${var.bucket_name}-https-proxy"
  url_map          = google_compute_url_map.website.id
  ssl_certificates = [google_compute_managed_ssl_certificate.website.id]
}

# HTTP Proxy (redirect to HTTPS)
resource "google_compute_target_http_proxy" "redirect" {
  name    = "${var.bucket_name}-http-proxy"
  url_map = google_compute_url_map.redirect.id
}

resource "google_compute_url_map" "redirect" {
  name = "${var.bucket_name}-redirect"

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }
}

# Global IP Address
resource "google_compute_global_address" "website" {
  name = "${var.bucket_name}-ip"
}

# Forwarding Rules
resource "google_compute_global_forwarding_rule" "https" {
  name       = "${var.bucket_name}-https"
  target     = google_compute_target_https_proxy.website.id
  port_range = "443"
  ip_address = google_compute_global_address.website.address
}

resource "google_compute_global_forwarding_rule" "http" {
  name       = "${var.bucket_name}-http"
  target     = google_compute_target_http_proxy.redirect.id
  port_range = "80"
  ip_address = google_compute_global_address.website.address
}

# Managed SSL Certificate
resource "google_compute_managed_ssl_certificate" "website" {
  name = "${var.bucket_name}-cert"

  managed {
    domains = [var.domain]
  }
}

output "load_balancer_ip" {
  value = google_compute_global_address.website.address
}

output "bucket_url" {
  value = "https://storage.googleapis.com/${google_storage_bucket.website.name}"
}
```

## Deployment Commands

```bash
# Create bucket (if not using Terraform)
gsutil mb -l US gs://${BUCKET_NAME}

# Enable website hosting
gsutil web set -m index.html -e index.html gs://${BUCKET_NAME}

# Make public
gsutil iam ch allUsers:objectViewer gs://${BUCKET_NAME}

# Build your site
npm run build

# Upload files
gsutil -m rsync -r -d ./dist gs://${BUCKET_NAME}

# Set cache headers
gsutil -m setmeta -h "Cache-Control:public, max-age=31536000" \
  gs://${BUCKET_NAME}/static/**

gsutil setmeta -h "Cache-Control:no-cache" \
  gs://${BUCKET_NAME}/index.html

# Invalidate CDN cache (after updates)
gcloud compute url-maps invalidate-cdn-cache ${URL_MAP_NAME} \
  --path "/*" --async
```

## Best Practices

### Caching Strategy
1. Set long cache TTL for hashed assets (JS, CSS, images)
2. Set short/no-cache for index.html
3. Use content-based hashing in build tool
4. Invalidate CDN cache after deployments

### Performance
1. Enable gzip compression (automatic with CDN)
2. Optimize images before upload
3. Use preload for critical resources
4. Enable HTTP/2 (automatic with load balancer)

### SPA Configuration
1. Set 404 page to index.html for client-side routing
2. Configure proper CORS headers
3. Use relative paths in your app
4. Handle deep links correctly

## Cost Breakdown

| Component | Price |
|-----------|-------|
| Cloud Storage | $0.02/GB/month |
| Network Egress (CDN) | $0.08/GB (first 10TB) |
| CDN Cache Egress | $0.02/GB |
| Load Balancer | $0.025/hour (~$18/month) |
| SSL Certificate | Free |

### Example Monthly Costs
| Traffic | Storage | Egress | LB | Total |
|---------|---------|--------|-------|-------|
| Low (1GB, 10GB) | $0.02 | $0.80 | $18 | ~$19 |
| Medium (5GB, 100GB) | $0.10 | $8 | $18 | ~$26 |
| High (20GB, 1TB) | $0.40 | $80 | $18 | ~$98 |

### Without Custom Domain
If using bucket URL directly (no load balancer):
- Low traffic: ~$1/month
- Medium traffic: ~$8/month
- High traffic: ~$80/month

## Common Mistakes

1. **Not setting cache headers**: Slow repeated visits
2. **Missing index.html fallback**: SPA routing breaks
3. **Forgetting CDN invalidation**: Old content served
4. **Wrong bucket region**: Higher latency without CDN
5. **Public bucket without CDN**: Direct storage egress expensive
6. **Not compressing assets**: Larger file transfers

## Example Configuration

```yaml
project_name: my-react-app
provider: gcp
region: us-central1
architecture_type: static_site_cdn

resources:
  - id: website-bucket
    type: cloud_storage
    name: my-react-app-website
    provider: gcp
    config:
      location: US
      website:
        main_page: index.html
        not_found_page: index.html
      cors:
        - origin: ["*"]
          method: ["GET", "HEAD"]

  - id: cdn-backend
    type: backend_bucket
    name: my-react-app-cdn
    provider: gcp
    config:
      bucket: my-react-app-website
      enable_cdn: true
      cache_mode: CACHE_ALL_STATIC
      default_ttl: 3600
    depends_on:
      - website-bucket

domain:
  enabled: true
  name: www.example.com
  ssl: true
```

## Sources

- [Cloud Storage Static Website](https://cloud.google.com/storage/docs/hosting-static-website)
- [Cloud CDN Documentation](https://cloud.google.com/cdn/docs)
- [Cloud CDN Pricing](https://cloud.google.com/cdn/pricing)
