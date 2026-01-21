# AWS S3 + CloudFront Static Site

## Overview

Deploy static websites and single-page applications using S3 for storage and CloudFront for global content delivery. This architecture provides low latency, high availability, and automatic HTTPS with minimal cost for static content.

## Detection Signals

Use this template when:
- Static site (HTML/CSS/JS only)
- Single-page application (React, Vue, Angular)
- Documentation sites
- Marketing landing pages
- No server-side rendering needed
- Global audience

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                             │
                    │                                                             │
                    │   ┌─────────────────────────────────────────────────────┐   │
    Internet ──────►│   │              CloudFront Distribution                 │   │
                    │   │              (Global Edge Locations)                 │   │
                    │   │                                                     │   │
                    │   │  ┌──────────────────────────────────────────────┐   │   │
                    │   │  │              Edge Locations                   │   │   │
                    │   │  │  🌍 US  🌍 EU  🌍 Asia  🌍 SA  🌍 AU         │   │   │
                    │   │  └──────────────────────────────────────────────┘   │   │
                    │   │                        │                            │   │
                    │   │                        │ Origin Request             │   │
                    │   │                        ▼                            │   │
                    │   │  ┌──────────────────────────────────────────────┐   │   │
                    │   │  │                S3 Bucket                      │   │   │
                    │   │  │             (Origin Access)                   │   │   │
                    │   │  │                                              │   │   │
                    │   │  │  ┌────────────────────────────────────────┐  │   │   │
                    │   │  │  │  index.html  │  assets/  │  js/  │ css/ │  │   │   │
                    │   │  │  └────────────────────────────────────────┘  │   │   │
                    │   │  │                                              │   │   │
                    │   │  │  Private bucket + OAC                        │   │   │
                    │   │  └──────────────────────────────────────────────┘   │   │
                    │   └─────────────────────────────────────────────────────┘   │
                    │                                                             │
                    │   ┌─────────────────────────────────────────────────────┐   │
                    │   │              Route 53 (optional)                     │   │
                    │   │        example.com → CloudFront                      │   │
                    │   └─────────────────────────────────────────────────────┘   │
                    │                                                             │
                    │   Global CDN • HTTPS • < 50ms latency • 99.9% availability │
                    └─────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| S3 Bucket | File storage | Static hosting |
| CloudFront | CDN | Distribution |
| ACM Certificate | HTTPS | DNS validation |
| Origin Access Control | Security | S3 access |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Route 53 | Custom domain | Hosted zone |
| Lambda@Edge | Dynamic content | Function association |
| WAF | Security | Web ACL |
| CloudFront Functions | URL rewrites | Viewer request |

## Configuration

### Terraform
```hcl
# main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"  # Required for ACM + CloudFront
}

variable "domain_name" {
  default = "example.com"
}

variable "project_name" {
  default = "static-site"
}

# S3 Bucket
resource "aws_s3_bucket" "main" {
  bucket = "${var.project_name}-${random_id.bucket.hex}"
}

resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Block all public access - CloudFront will access via OAC
resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket policy for CloudFront OAC
resource "aws_s3_bucket_policy" "main" {
  bucket = aws_s3_bucket.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.main.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${var.project_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ACM Certificate
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.domain_name, "www.${var.domain_name}"]
  price_class         = "PriceClass_100"  # US, Canada, Europe
  http_version        = "http2and3"

  origin {
    domain_name              = aws_s3_bucket.main.bucket_regional_domain_name
    origin_id                = "S3Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3Origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600      # 1 hour
    max_ttl                = 86400     # 24 hours
    compress               = true

    # Optional: CloudFront Function for URL rewrites
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.url_rewrite.arn
    }
  }

  # Cache behavior for static assets (longer TTL)
  ordered_cache_behavior {
    path_pattern     = "/assets/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3Origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400      # 1 day
    default_ttl            = 604800     # 7 days
    max_ttl                = 31536000   # 1 year
    compress               = true
  }

  # SPA: Return index.html for 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Environment = "production"
  }
}

# CloudFront Function for URL rewrites (SPA support)
resource "aws_cloudfront_function" "url_rewrite" {
  name    = "${var.project_name}-url-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      // Rewrite requests to root for SPA
      if (!uri.includes('.') && !uri.endsWith('/')) {
        request.uri = '/index.html';
      }

      // Add index.html for directory requests
      if (uri.endsWith('/')) {
        request.uri += 'index.html';
      }

      return request;
    }
  EOF
}

# Route 53 Records (if using Route 53)
resource "aws_route53_zone" "main" {
  name = var.domain_name
}

resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# ACM Certificate Validation
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "s3_bucket" {
  value = aws_s3_bucket.main.bucket
}

output "website_url" {
  value = "https://${var.domain_name}"
}
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Build static site (example for React)
npm run build

# Sync to S3
aws s3 sync ./build s3://static-site-xxxxx/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E1XXXXXXXXX \
  --paths "/*"

# Quick deploy script
#!/bin/bash
npm run build
aws s3 sync ./build s3://static-site-xxxxx/ --delete \
  --cache-control "max-age=31536000" \
  --exclude "index.html" \
  --exclude "*.json"
aws s3 cp ./build/index.html s3://static-site-xxxxx/index.html \
  --cache-control "no-cache, no-store, must-revalidate"
aws cloudfront create-invalidation \
  --distribution-id E1XXXXXXXXX \
  --paths "/index.html"
```

## Best Practices

### Caching
1. Long TTL for static assets (versioned)
2. Short/no cache for index.html
3. Use cache-control headers
4. Version assets with hashes
5. Invalidate on deploy

### Performance
1. Enable compression
2. Use HTTP/2 and HTTP/3
3. Optimize images (WebP)
4. Minimize bundle size
5. Use preload/prefetch

### Security
1. Use HTTPS only
2. Enable Origin Access Control
3. Set security headers
4. Enable WAF for protection
5. Use Content Security Policy

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| S3 Storage | 5GB | $0.023/GB |
| S3 Requests | 20k GET | $0.0004/1k GET |
| CloudFront | 1TB/mo | $0.085/GB |
| CloudFront Requests | 10M/mo | $0.0075-0.01/10k |
| Route 53 | - | $0.50/zone/mo |

### Example Costs
| Scale | Storage | Bandwidth | Requests | Total |
|-------|---------|-----------|----------|-------|
| Small | 1GB | 10GB | 100k | ~$1 |
| Medium | 5GB | 100GB | 1M | ~$10 |
| Large | 20GB | 1TB | 10M | ~$95 |

## Common Mistakes

1. **Public S3 bucket**: Use OAC instead
2. **No cache invalidation**: Old content served
3. **Wrong index.html caching**: SPA routing breaks
4. **Missing custom error pages**: 404 for SPA routes
5. **No compression**: Larger downloads
6. **HTTP allowed**: Security vulnerability

## Example Configuration

```yaml
project_name: my-static-site
provider: aws
architecture_type: s3_cloudfront

resources:
  - id: static-bucket
    type: aws_s3_bucket
    name: static-site
    provider: aws
    config:
      versioning: true
      public_access: blocked

  - id: cdn
    type: aws_cloudfront
    name: static-site-cdn
    provider: aws
    config:
      price_class: PriceClass_100
      http_version: http2and3
      default_ttl: 3600
      compress: true

  - id: certificate
    type: aws_acm_certificate
    name: static-site-cert
    provider: aws
    config:
      domain: example.com
      validation: DNS
```

## Sources

- [CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/)
- [S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [CloudFront Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/best-practices.html)
