# Cost Estimation Instructions

This document describes how to estimate infrastructure costs.

## Overview

Cost estimation should provide users with a reasonable monthly cost estimate for their infrastructure. Use the cloud provider's pricing information to calculate estimates.

## GCP Pricing Reference

### Compute

#### Cloud Run

Pricing model: Pay per use (CPU, memory, requests)

| Component | Price | Unit |
|-----------|-------|------|
| CPU | $0.00002400 | per vCPU-second |
| Memory | $0.00000250 | per GiB-second |
| Requests | $0.40 | per million requests |

**Monthly estimate calculation:**

For always-on instances (min_instances > 0):
```
CPU cost = vCPUs × seconds_per_month × $0.00002400
Memory cost = GiB × seconds_per_month × $0.00000250
seconds_per_month = 730 hours × 3600 = 2,628,000
```

For scale-to-zero (min_instances = 0):
- Estimate based on expected traffic
- Minimum ~$0/month if no traffic
- Base estimate: $10-20/month for light usage

#### Compute Engine

| Machine Type | vCPUs | Memory | Monthly (us-central1) |
|--------------|-------|--------|----------------------|
| e2-micro | 0.25 | 1 GB | ~$7.50 |
| e2-small | 0.5 | 2 GB | ~$15 |
| e2-medium | 1 | 4 GB | ~$30 |
| n1-standard-1 | 1 | 3.75 GB | ~$35 |
| n1-standard-2 | 2 | 7.5 GB | ~$70 |

### Databases

#### Cloud SQL

| Tier | vCPUs | Memory | Monthly |
|------|-------|--------|---------|
| db-f1-micro | shared | 0.6 GB | ~$10 |
| db-g1-small | shared | 1.7 GB | ~$30 |
| db-n1-standard-1 | 1 | 3.75 GB | ~$50 |
| db-n1-standard-2 | 2 | 7.5 GB | ~$100 |

Storage: $0.17/GB/month (SSD)
Backups: $0.08/GB/month

#### Cloud Memorystore (Redis)

| Tier | Capacity | Monthly |
|------|----------|---------|
| Basic | 1 GB | ~$35 |
| Basic | 5 GB | ~$175 |
| Standard | 1 GB | ~$70 |

### Storage

#### Cloud Storage

| Storage Class | Price per GB/month |
|---------------|-------------------|
| Standard | $0.020 |
| Nearline | $0.010 |
| Coldline | $0.004 |
| Archive | $0.0012 |

Operations:
- Class A (write): $0.05 per 10,000
- Class B (read): $0.004 per 10,000

Egress: $0.12/GB (after 1 GB free)

#### Artifact Registry

Storage: $0.10/GB/month
No network egress charges within same region

### Networking

#### VPC Access Connector

~$7/month (minimum 2 instances at e2-micro)

#### Cloud NAT

~$1/hour + $0.045/GB processed

#### Load Balancer

- Forwarding rules: $0.025/hour (~$18/month)
- Data processed: $0.008-0.012/GB

#### Cloud CDN

- Cache egress: $0.02-0.08/GB (varies by region)
- Cache fill: $0.04/GB

### Other Services

#### Secret Manager

- Secrets: $0.06/secret version/month
- Access: $0.03/10,000 access operations
- Effectively free for small usage

#### Cloud DNS

- Managed zone: $0.20/month
- Queries: $0.40/million

## AWS Pricing Reference

### Compute

#### Lambda
- Requests: $0.20/million
- Duration: $0.0000166667/GB-second

#### ECS/Fargate
- vCPU: $0.04048/hour
- Memory: $0.004445/GB/hour

#### EC2 (On-Demand, us-east-1)
| Instance | vCPUs | Memory | Monthly |
|----------|-------|--------|---------|
| t3.micro | 2 | 1 GB | ~$8 |
| t3.small | 2 | 2 GB | ~$16 |
| t3.medium | 2 | 4 GB | ~$32 |

### Databases

#### RDS PostgreSQL
| Instance | vCPUs | Memory | Monthly |
|----------|-------|--------|---------|
| db.t3.micro | 2 | 1 GB | ~$15 |
| db.t3.small | 2 | 2 GB | ~$30 |
| db.t3.medium | 2 | 4 GB | ~$60 |

Storage: $0.115/GB/month (gp2)

### Storage

#### S3
- Standard: $0.023/GB/month
- Intelligent-Tiering: $0.023-0.0125/GB/month

## Cost Estimation Process

### Step 1: List Resources

From the Terraform configuration, identify all billable resources:

```yaml
resources:
  - type: cloud_run
    config:
      cpu: 1
      memory: 512Mi
      min_instances: 0
  - type: cloud_sql
    config:
      tier: db-f1-micro
      storage_size: 10
  - type: cloud_storage
    config:
      estimated_size_gb: 5
```

### Step 2: Calculate Per-Resource Costs

For each resource, apply the pricing formulas:

#### Cloud Run Example
```
min_instances = 0 → scale-to-zero
Estimated monthly: $15 (light usage baseline)
```

#### Cloud SQL Example
```
tier = db-f1-micro → $10/month
storage = 10 GB × $0.17 = $1.70/month
Total: $11.70/month
```

#### Cloud Storage Example
```
storage = 5 GB × $0.02 = $0.10/month
Operations estimate: ~$0.50/month
Total: $0.60/month
```

### Step 3: Add Infrastructure Overhead

Include costs that apply to most deployments:

| Component | Estimated Cost |
|-----------|---------------|
| VPC Connector (if private DB) | $7/month |
| Secret Manager | ~$0 (minimal) |
| Cloud DNS (if custom domain) | $0.50/month |
| Egress (light usage) | ~$1-5/month |

### Step 4: Present Estimate

Format the cost estimate clearly:

```
COST ESTIMATE (Monthly)
────────────────────────────────────────────────────────

  Cloud Run (api-service)
    CPU/Memory (scale-to-zero): $15.00
    Subtotal: $15.00/mo

  Cloud SQL (database)
    Instance (db-f1-micro): $10.00
    Storage (10 GB): $1.70
    Subtotal: $11.70/mo

  Cloud Storage (static-assets)
    Storage (5 GB): $0.10
    Operations: $0.50
    Subtotal: $0.60/mo

  VPC Connector
    Subtotal: $7.00/mo

────────────────────────────────────────────────────────
  TOTAL: $34.30/month
============================================================

Assumptions:
  - Cloud Run assumes light traffic (< 1M requests/month)
  - Egress costs not included (depends on traffic)
  - Prices are for us-central1 region

Confidence: Medium
```

## Cost Optimization Suggestions

Based on the configuration, suggest optimizations:

1. **Scale-to-zero**: If traffic is intermittent, use min_instances=0
2. **Smaller tiers**: Start with smallest DB tier, scale up as needed
3. **Preemptible instances**: For non-critical workloads
4. **Committed use discounts**: For predictable workloads (1-3 year)
5. **Storage classes**: Use Nearline/Coldline for infrequently accessed data
6. **Regional vs Multi-regional**: Single region is cheaper

## Notes

- Prices change frequently; these are estimates
- Actual costs depend on usage patterns
- Free tier credits may reduce costs for new accounts
- Always recommend users verify with the cloud provider's pricing calculator
