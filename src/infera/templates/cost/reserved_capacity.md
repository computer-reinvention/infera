# Reserved Capacity & Committed Use Discounts

## Overview

Reserved capacity (AWS) and committed use discounts (GCP) provide 30-70% savings in exchange for 1-3 year commitments. This guide covers strategies for optimizing cloud spend through long-term commitments while maintaining flexibility.

### When to Use
- Stable, predictable baseline workloads
- Production databases
- Always-on infrastructure components
- Core Kubernetes node pools
- 24/7 services with consistent resource usage
- Workloads running >70% of the time

### When NOT to Use
- Variable or seasonal workloads
- Development/staging environments
- New projects without usage history
- Workloads that may be migrated or deprecated
- Rapidly scaling startups (uncertain future needs)

## Commitment Types Comparison

### GCP Committed Use Discounts (CUDs)

| Commitment | Discount | Flexibility |
|------------|----------|-------------|
| 1-year CUD | 37% | Low - specific machine type |
| 3-year CUD | 55% | Low - specific machine type |
| Flexible CUDs | 28-46% | High - any machine type in family |
| Spend-based CUDs | Up to 28% | High - any GCP service |

### AWS Savings Plans & Reserved Instances

| Type | Discount | Flexibility |
|------|----------|-------------|
| Compute Savings Plan (1yr) | Up to 66% | High - any instance |
| Compute Savings Plan (3yr) | Up to 72% | High - any instance |
| EC2 Instance Savings Plan (1yr) | Up to 72% | Medium - instance family |
| EC2 Instance Savings Plan (3yr) | Up to 75% | Medium - instance family |
| Standard Reserved Instances | Up to 75% | Low - specific instance |
| Convertible Reserved Instances | Up to 66% | Medium - can convert |

### Azure Reserved Instances

| Commitment | Discount | Flexibility |
|------------|----------|-------------|
| 1-year RI | Up to 40% | Medium |
| 3-year RI | Up to 65% | Medium |
| Azure Savings Plan | Up to 65% | High |

## Analysis Framework

### Step 1: Identify Stable Workloads

```python
# analyze_usage.py - Find commitment candidates
import boto3
from datetime import datetime, timedelta

def analyze_ec2_utilization(days: int = 90) -> dict:
    """Analyze EC2 usage to identify commitment candidates."""
    ce = boto3.client('ce')

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
            'End': datetime.now().strftime('%Y-%m-%d'),
        },
        Granularity='DAILY',
        Metrics=['UsageQuantity', 'UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'},
        ],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': ['Amazon Elastic Compute Cloud - Compute'],
            },
        },
    )

    usage_by_type = {}
    for result in response['ResultsByTime']:
        for group in result['Groups']:
            instance_type = group['Keys'][0]
            hours = float(group['Metrics']['UsageQuantity']['Amount'])

            if instance_type not in usage_by_type:
                usage_by_type[instance_type] = []
            usage_by_type[instance_type].append(hours)

    # Calculate statistics
    recommendations = {}
    for instance_type, daily_hours in usage_by_type.items():
        avg_hours = sum(daily_hours) / len(daily_hours)
        min_hours = min(daily_hours)
        max_hours = max(daily_hours)

        # Recommend commitment for stable baseline
        # (minimum usage that occurs consistently)
        stable_baseline = min_hours * 0.9  # 90% of minimum

        if stable_baseline >= 168:  # ~7 instances always running
            recommendations[instance_type] = {
                'avg_daily_hours': avg_hours,
                'min_daily_hours': min_hours,
                'max_daily_hours': max_hours,
                'recommended_commitment_hours': stable_baseline,
                'coverage_percentage': (stable_baseline / avg_hours) * 100,
            }

    return recommendations

# Usage
recommendations = analyze_ec2_utilization(90)
for instance_type, data in recommendations.items():
    print(f"{instance_type}:")
    print(f"  Stable baseline: {data['recommended_commitment_hours']:.0f} hours/day")
    print(f"  Coverage: {data['coverage_percentage']:.1f}%")
```

### Step 2: Calculate Savings

```python
# savings_calculator.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class CommitmentCalculation:
    instance_type: str
    quantity: int
    term: Literal['1-year', '3-year']
    on_demand_hourly: float
    committed_hourly: float
    monthly_on_demand: float
    monthly_committed: float
    monthly_savings: float
    annual_savings: float
    total_savings: float
    break_even_months: float

def calculate_aws_savings(
    instance_type: str,
    quantity: int,
    term: Literal['1-year', '3-year'] = '1-year',
) -> CommitmentCalculation:
    """Calculate savings for AWS Savings Plans."""

    # Pricing data (example - fetch from AWS Pricing API)
    pricing = {
        'm5.xlarge': {
            'on_demand': 0.192,
            '1-year': 0.121,  # 37% discount
            '3-year': 0.076,  # 60% discount
        },
        'm5.2xlarge': {
            'on_demand': 0.384,
            '1-year': 0.242,
            '3-year': 0.152,
        },
        'r5.xlarge': {
            'on_demand': 0.252,
            '1-year': 0.159,
            '3-year': 0.100,
        },
    }

    rates = pricing.get(instance_type, pricing['m5.xlarge'])
    hours_per_month = 730

    on_demand_hourly = rates['on_demand']
    committed_hourly = rates[term]

    monthly_on_demand = on_demand_hourly * hours_per_month * quantity
    monthly_committed = committed_hourly * hours_per_month * quantity
    monthly_savings = monthly_on_demand - monthly_committed

    term_months = 12 if term == '1-year' else 36
    total_savings = monthly_savings * term_months

    # Break-even: when savings exceed any upfront cost (none for no-upfront)
    break_even_months = 0  # Immediate for no-upfront

    return CommitmentCalculation(
        instance_type=instance_type,
        quantity=quantity,
        term=term,
        on_demand_hourly=on_demand_hourly,
        committed_hourly=committed_hourly,
        monthly_on_demand=monthly_on_demand,
        monthly_committed=monthly_committed,
        monthly_savings=monthly_savings,
        annual_savings=monthly_savings * 12,
        total_savings=total_savings,
        break_even_months=break_even_months,
    )

# Example calculation
result = calculate_aws_savings('m5.xlarge', 10, '1-year')
print(f"Monthly On-Demand: ${result.monthly_on_demand:.2f}")
print(f"Monthly Committed: ${result.monthly_committed:.2f}")
print(f"Monthly Savings: ${result.monthly_savings:.2f}")
print(f"Annual Savings: ${result.annual_savings:.2f}")
```

## Implementation Patterns

### Pattern 1: GCP Committed Use Discounts

```hcl
# GCP CUD Terraform configuration
resource "google_compute_commitment" "cpu_commitment" {
  name   = "cpu-1year-commitment"
  region = "us-central1"
  type   = "GENERAL_PURPOSE_E2"
  plan   = "TWELVE_MONTH"  # or THIRTY_SIX_MONTH

  resources {
    type   = "VCPU"
    amount = "100"  # 100 vCPUs committed
  }

  resources {
    type   = "MEMORY"
    amount = "400"  # 400 GB RAM committed
  }
}

# Flexible CUD (any machine type in family)
resource "google_compute_commitment" "flexible" {
  name   = "flexible-commitment"
  region = "us-central1"
  type   = "GENERAL_PURPOSE"  # Flexible across N1, N2, E2
  plan   = "TWELVE_MONTH"

  resources {
    type   = "VCPU"
    amount = "50"
  }

  resources {
    type   = "MEMORY"
    amount = "200"
  }
}
```

**GCP Spend-based CUD:**
```bash
# Purchase spend-based commitment via gcloud
gcloud compute commitments create spend-commitment \
    --region=us-central1 \
    --plan=12-month \
    --type=compute-optimized-c2 \
    --resources=vcpu=100,memory=400GB

# List existing commitments
gcloud compute commitments list --region=us-central1
```

### Pattern 2: AWS Savings Plans

```hcl
# AWS Savings Plans via Terraform
resource "aws_savingsplans_plan" "compute" {
  plan_type = "Compute"

  commitment       = 10.00  # $10/hour commitment
  payment_option   = "No Upfront"
  term_duration    = "ONE_YEAR"
}

# Alternative: Use AWS Console or CLI
# aws savingsplans create-savings-plan \
#   --savings-plan-type "Compute" \
#   --commitment "10.00" \
#   --term-duration-in-seconds 31536000 \
#   --payment-option "No Upfront"
```

**Reserved Instances for specific workloads:**
```python
# reserve_instances.py - Purchase RIs programmatically
import boto3

ec2 = boto3.client('ec2')

def purchase_reserved_instances(
    instance_type: str,
    instance_count: int,
    availability_zone: str,
    offering_type: str = 'No Upfront',
    term: int = 1,  # years
) -> dict:
    """Purchase Reserved Instances."""

    # Find available offerings
    offerings = ec2.describe_reserved_instances_offerings(
        InstanceType=instance_type,
        AvailabilityZone=availability_zone,
        ProductDescription='Linux/UNIX',
        OfferingType=offering_type,
        InstanceTenancy='default',
        Filters=[
            {'Name': 'duration', 'Values': [str(term * 31536000)]},
        ],
    )

    if not offerings['ReservedInstancesOfferings']:
        raise ValueError(f"No offerings found for {instance_type}")

    offering_id = offerings['ReservedInstancesOfferings'][0]['ReservedInstancesOfferingId']

    # Purchase
    result = ec2.purchase_reserved_instances_offering(
        ReservedInstancesOfferingId=offering_id,
        InstanceCount=instance_count,
    )

    return result

# Example
result = purchase_reserved_instances(
    instance_type='m5.xlarge',
    instance_count=10,
    availability_zone='us-east-1a',
    offering_type='No Upfront',
    term=1,
)
```

### Pattern 3: Kubernetes with Mixed Commitments

```yaml
# GKE cluster with committed node pools
apiVersion: container.cnrm.cloud.google.com/v1beta1
kind: ContainerCluster
metadata:
  name: production
spec:
  location: us-central1

  # On-demand system pool
  nodeConfig:
    machineType: e2-standard-4
    nodePoolAutoConfig:
      networkTags:
        tags:
          - "gke-system"

---
# Committed node pool (covered by CUD)
apiVersion: container.cnrm.cloud.google.com/v1beta1
kind: ContainerNodePool
metadata:
  name: committed-pool
spec:
  clusterRef:
    name: production
  location: us-central1

  nodeConfig:
    machineType: e2-standard-8  # Matches CUD commitment
    labels:
      commitment: "cud-covered"

  autoscaling:
    minNodeCount: 5   # Baseline covered by CUD
    maxNodeCount: 20  # Overflow on-demand

---
# Spot pool for variable workloads (no commitment)
apiVersion: container.cnrm.cloud.google.com/v1beta1
kind: ContainerNodePool
metadata:
  name: spot-pool
spec:
  clusterRef:
    name: production
  location: us-central1

  nodeConfig:
    machineType: e2-standard-4
    spot: true
    labels:
      commitment: "none"
    taints:
      - key: "spot"
        value: "true"
        effect: "NO_SCHEDULE"

  autoscaling:
    minNodeCount: 0
    maxNodeCount: 50
```

### Pattern 4: Database Reserved Instances

```hcl
# RDS Reserved Instances
resource "aws_db_instance" "production" {
  identifier           = "prod-db"
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.r5.xlarge"  # Match RI
  allocated_storage    = 100
  multi_az             = true

  tags = {
    ReservedInstance = "true"
  }
}

# Purchase RI via AWS CLI (not Terraform)
# aws rds purchase-reserved-db-instances-offering \
#   --reserved-db-instances-offering-id <offering-id> \
#   --db-instance-count 1
```

```bash
# Find RDS RI offerings
aws rds describe-reserved-db-instances-offerings \
    --db-instance-class db.r5.xlarge \
    --product-description postgresql \
    --duration 31536000 \
    --offering-type "No Upfront" \
    --query 'ReservedDBInstancesOfferings[*].[ReservedDBInstancesOfferingId,FixedPrice,RecurringCharges]'
```

## Coverage Optimization

### Optimal Coverage Strategy

```
┌─────────────────────────────────────────────────────────┐
│              Optimal Commitment Coverage                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Usage                                                   │
│    │                     Peak (On-Demand)               │
│ 50 ┤         ╱╲    ╱╲         ╱╲                        │
│    │        ╱  ╲  ╱  ╲   ╱╲  ╱  ╲                       │
│ 40 ┤       ╱    ╲╱    ╲ ╱  ╲╱    ╲                      │
│    │──────────────────────────────── Variable (Spot)   │
│ 30 ┤▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                    │
│    │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ Committed          │
│ 20 ┤▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ (CUD/RI)          │
│    │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                    │
│ 10 ┤▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                    │
│    │                                                     │
│  0 ┼──────────────────────────────────────▶ Time        │
│                                                          │
│  Target: 70-80% committed, 10-20% spot, 10% on-demand   │
└─────────────────────────────────────────────────────────┘
```

### Coverage Calculator

```python
def calculate_optimal_coverage(
    min_usage: float,
    avg_usage: float,
    max_usage: float,
    risk_tolerance: float = 0.1,  # 10% buffer
) -> dict:
    """Calculate optimal commitment levels."""

    # Commit to stable baseline (with buffer)
    committed = min_usage * (1 - risk_tolerance)

    # Variable portion (spot eligible)
    spot_eligible = avg_usage - committed

    # Peak capacity (on-demand)
    on_demand_buffer = max_usage - avg_usage

    total = committed + spot_eligible + on_demand_buffer

    return {
        'committed': {
            'amount': committed,
            'percentage': (committed / total) * 100,
            'discount': '37-60%',
        },
        'spot': {
            'amount': spot_eligible,
            'percentage': (spot_eligible / total) * 100,
            'discount': '60-90%',
        },
        'on_demand': {
            'amount': on_demand_buffer,
            'percentage': (on_demand_buffer / total) * 100,
            'discount': '0%',
        },
        'blended_savings': calculate_blended_savings(
            committed, spot_eligible, on_demand_buffer
        ),
    }

def calculate_blended_savings(committed: float, spot: float, on_demand: float) -> float:
    """Calculate overall blended discount rate."""
    total = committed + spot + on_demand
    if total == 0:
        return 0

    # Weighted average discount
    committed_discount = 0.45  # 45% average CUD/RI discount
    spot_discount = 0.70      # 70% average spot discount
    on_demand_discount = 0    # No discount

    return (
        (committed / total * committed_discount) +
        (spot / total * spot_discount) +
        (on_demand / total * on_demand_discount)
    ) * 100
```

## Monitoring & Optimization

### Commitment Utilization Dashboard

```python
# commitment_monitor.py - Track CUD/RI utilization
import boto3
from datetime import datetime, timedelta

def get_ri_utilization() -> dict:
    """Get Reserved Instance utilization metrics."""
    ce = boto3.client('ce')

    response = ce.get_reservation_utilization(
        TimePeriod={
            'Start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'End': datetime.now().strftime('%Y-%m-%d'),
        },
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SUBSCRIPTION_ID'},
        ],
    )

    utilization = []
    for item in response['UtilizationsByTime']:
        for group in item.get('Groups', []):
            utilization.append({
                'subscription_id': group['Keys'][0],
                'utilization_percentage': float(
                    group['Utilization']['UtilizationPercentage']
                ),
                'purchased_hours': float(
                    group['Utilization']['PurchasedHours']
                ),
                'used_hours': float(
                    group['Utilization']['TotalActualHours']
                ),
            })

    return utilization

def get_savings_plan_utilization() -> dict:
    """Get Savings Plan utilization."""
    ce = boto3.client('ce')

    response = ce.get_savings_plans_utilization(
        TimePeriod={
            'Start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'End': datetime.now().strftime('%Y-%m-%d'),
        },
    )

    return {
        'utilization_percentage': float(
            response['Total']['Utilization']['UtilizationPercentage']
        ),
        'used_commitment': float(
            response['Total']['Utilization']['UsedCommitment']
        ),
        'total_commitment': float(
            response['Total']['Utilization']['TotalCommitment']
        ),
    }

# Alert on low utilization
utilization = get_savings_plan_utilization()
if utilization['utilization_percentage'] < 80:
    print(f"WARNING: Savings Plan utilization at {utilization['utilization_percentage']:.1f}%")
    print("Consider reducing commitment or increasing workload coverage")
```

### GCP CUD Utilization

```bash
# Check CUD utilization via gcloud
gcloud compute commitments describe cpu-1year-commitment \
    --region=us-central1 \
    --format="table(
        name,
        status,
        plan,
        resources[].type,
        resources[].amount,
        startTimestamp,
        endTimestamp
    )"

# Get usage vs commitment
gcloud compute resource-policies list --format=json | jq '
  .[] | select(.commitment != null) |
  {name: .name, commitment: .commitment, currentUsage: .currentUsage}
'
```

## Cost Comparison Summary

```
┌─────────────────────────────────────────────────────────────────┐
│           Annual Cost Comparison: 10 x m5.xlarge                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Strategy              Monthly    Annual     Savings            │
│  ─────────────────────────────────────────────────────          │
│  On-Demand             $1,401     $16,819    Baseline           │
│  1-Year No Upfront     $883       $10,596    37% ($6,223)       │
│  3-Year No Upfront     $555       $6,660     60% ($10,159)      │
│  3-Year All Upfront    $491       $5,892     65% ($10,927)      │
│  Spot (avg 70% off)    $420       $5,046     70% ($11,773)*     │
│                                                                  │
│  * Spot has interruption risk; suitable for fault-tolerant      │
│                                                                  │
│  Recommended: 1-Year Savings Plan for most workloads            │
│  - Immediate savings with no upfront cost                       │
│  - Flexibility to change instance types                         │
│  - Can increase commitment as usage grows                       │
└─────────────────────────────────────────────────────────────────┘
```

## Example Configuration

```yaml
# infera.yaml - Reserved capacity configuration
name: production-cluster
provider: gcp

cost_optimization:
  strategy: committed_use

  # Commitment configuration
  commitments:
    - type: cpu_memory
      plan: 1-year
      resources:
        vcpu: 100
        memory_gb: 400
      machine_family: e2

  # Coverage targets
  coverage:
    committed_percentage: 70
    spot_percentage: 20
    on_demand_percentage: 10

  # Monitoring
  alerts:
    utilization_threshold: 80  # Alert if <80% utilized
    expiration_warning_days: 90

kubernetes:
  node_pools:
    - name: committed
      machine_type: e2-standard-8
      min_nodes: 12  # Matches commitment
      max_nodes: 12
      labels:
        cost-tier: committed

    - name: spot
      machine_type: e2-standard-4
      spot: true
      min_nodes: 0
      max_nodes: 20
      labels:
        cost-tier: spot

    - name: on-demand
      machine_type: e2-standard-4
      min_nodes: 0
      max_nodes: 10
      labels:
        cost-tier: on-demand
```

## Sources

- [GCP Committed Use Discounts](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview)
- [AWS Savings Plans](https://aws.amazon.com/savingsplans/)
- [AWS Reserved Instances](https://aws.amazon.com/ec2/pricing/reserved-instances/)
- [Azure Reserved VM Instances](https://azure.microsoft.com/en-us/pricing/reserved-vm-instances/)
- [GCP Pricing Calculator](https://cloud.google.com/products/calculator)
- [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/)
