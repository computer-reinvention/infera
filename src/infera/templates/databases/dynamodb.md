# Amazon DynamoDB

## Overview
DynamoDB is a fully managed, serverless NoSQL database with single-digit millisecond performance at any scale. It's the default choice for serverless applications on AWS, providing automatic scaling, built-in security, and global tables for multi-region deployments.

**Use when:**
- Building serverless applications on AWS
- Need predictable, single-digit millisecond latency
- Workload has simple access patterns (key-value, query by partition key)
- Need automatic scaling without capacity planning
- Building multi-region applications

**Don't use when:**
- Complex queries with multiple JOINs
- Ad-hoc querying requirements
- Workload is highly relational
- Need strong SQL compatibility

## Detection Signals

```
Files:
- serverless.yml with dynamodb
- cdk.json, cdk.ts (AWS CDK)
- sam.yaml (AWS SAM)
- terraform/*.tf with aws_dynamodb_table

Dependencies:
- @aws-sdk/client-dynamodb (Node.js v3)
- aws-sdk (Node.js v2)
- boto3, aioboto3 (Python)
- aws-sdk-go-v2/service/dynamodb (Go)

Code Patterns:
- DynamoDBClient, DocumentClient
- PutItem, GetItem, Query, Scan
- KeyConditionExpression
- dynamodb.Table()
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DynamoDB Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Application Layer                      │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Lambda  │  │   ECS   │  │  EC2    │  │  API GW │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  │       │            │            │            │           │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          │            │            │            │                │
│          └────────────┴──────┬─────┴────────────┘                │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    DynamoDB                                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │                    Table                             │  │  │
│  │  │                                                      │  │  │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │  │
│  │  │  │ Partition 1│  │ Partition 2│  │ Partition N│    │  │  │
│  │  │  │            │  │            │  │            │    │  │  │
│  │  │  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │    │  │  │
│  │  │  │ │  Item  │ │  │ │  Item  │ │  │ │  Item  │ │    │  │  │
│  │  │  │ ├────────┤ │  │ ├────────┤ │  │ ├────────┤ │    │  │  │
│  │  │  │ │  Item  │ │  │ │  Item  │ │  │ │  Item  │ │    │  │  │
│  │  │  │ └────────┘ │  │ └────────┘ │  │ └────────┘ │    │  │  │
│  │  │  └────────────┘  └────────────┘  └────────────┘    │  │  │
│  │  │                                                      │  │  │
│  │  │  GSI: Global Secondary Index (async replication)    │  │  │
│  │  │  LSI: Local Secondary Index (same partition)        │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  Features:                                                 │  │
│  │  • Auto-scaling / On-demand capacity                      │  │
│  │  • DynamoDB Streams (change data capture)                 │  │
│  │  • Global Tables (multi-region)                           │  │
│  │  • Point-in-time recovery                                 │  │
│  │  • TTL (automatic item deletion)                          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Terraform Configuration

```hcl
# dynamodb.tf

resource "aws_dynamodb_table" "main" {
  name         = "${var.project_name}-${var.table_name}"
  billing_mode = var.billing_mode  # PAY_PER_REQUEST or PROVISIONED

  # Key schema
  hash_key  = "PK"   # Partition key
  range_key = "SK"   # Sort key (optional)

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # GSI attributes (must define if used in GSI)
  attribute {
    name = "GSI1PK"
    type = "S"
  }

  attribute {
    name = "GSI1SK"
    type = "S"
  }

  # Global Secondary Index
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing
    dynamic "read_capacity" {
      for_each = var.billing_mode == "PROVISIONED" ? [1] : []
      content {
        value = var.gsi_read_capacity
      }
    }
    dynamic "write_capacity" {
      for_each = var.billing_mode == "PROVISIONED" ? [1] : []
      content {
        value = var.gsi_write_capacity
      }
    }
  }

  # Provisioned capacity (only if PROVISIONED mode)
  dynamic "provisioned_throughput" {
    for_each = var.billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.read_capacity
      write_capacity = var.write_capacity
    }
  }

  # Auto-scaling for provisioned mode
  lifecycle {
    ignore_changes = [read_capacity, write_capacity]
  }

  # TTL
  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = var.environment == "production"
  }

  # Server-side encryption
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn  # Optional, uses AWS managed key if not set
  }

  # Streams (for triggers/replication)
  stream_enabled   = var.enable_streams
  stream_view_type = var.enable_streams ? "NEW_AND_OLD_IMAGES" : null

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Auto-scaling for provisioned mode
resource "aws_appautoscaling_target" "read" {
  count = var.billing_mode == "PROVISIONED" ? 1 : 0

  max_capacity       = var.max_read_capacity
  min_capacity       = var.read_capacity
  resource_id        = "table/${aws_dynamodb_table.main.name}"
  scalable_dimension = "dynamodb:table:ReadCapacityUnits"
  service_namespace  = "dynamodb"
}

resource "aws_appautoscaling_policy" "read" {
  count = var.billing_mode == "PROVISIONED" ? 1 : 0

  name               = "${var.project_name}-read-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.read[0].resource_id
  scalable_dimension = aws_appautoscaling_target.read[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.read[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "DynamoDBReadCapacityUtilization"
    }
    target_value = 70.0
  }
}

resource "aws_appautoscaling_target" "write" {
  count = var.billing_mode == "PROVISIONED" ? 1 : 0

  max_capacity       = var.max_write_capacity
  min_capacity       = var.write_capacity
  resource_id        = "table/${aws_dynamodb_table.main.name}"
  scalable_dimension = "dynamodb:table:WriteCapacityUnits"
  service_namespace  = "dynamodb"
}

resource "aws_appautoscaling_policy" "write" {
  count = var.billing_mode == "PROVISIONED" ? 1 : 0

  name               = "${var.project_name}-write-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.write[0].resource_id
  scalable_dimension = aws_appautoscaling_target.write[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.write[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "DynamoDBWriteCapacityUtilization"
    }
    target_value = 70.0
  }
}

# Variables
variable "billing_mode" {
  description = "Billing mode: PAY_PER_REQUEST (on-demand) or PROVISIONED"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "enable_streams" {
  description = "Enable DynamoDB Streams"
  type        = bool
  default     = false
}

# Outputs
output "table_name" {
  value = aws_dynamodb_table.main.name
}

output "table_arn" {
  value = aws_dynamodb_table.main.arn
}

output "stream_arn" {
  value = var.enable_streams ? aws_dynamodb_table.main.stream_arn : null
}
```

## Single-Table Design Pattern

```typescript
// Single-table design example
// Table: MyApp

// Key structure:
// PK (Partition Key) | SK (Sort Key) | Entity | Attributes...
// USER#123           | PROFILE       | User   | name, email, ...
// USER#123           | ORDER#456     | Order  | total, status, ...
// USER#123           | ORDER#789     | Order  | total, status, ...
// ORDER#456          | ORDER#456     | Order  | (for GSI access by order ID)

interface BaseItem {
  PK: string;
  SK: string;
  GSI1PK?: string;
  GSI1SK?: string;
  entityType: string;
  createdAt: string;
  updatedAt: string;
}

interface User extends BaseItem {
  entityType: 'USER';
  userId: string;
  email: string;
  name: string;
}

interface Order extends BaseItem {
  entityType: 'ORDER';
  orderId: string;
  userId: string;
  total: number;
  status: 'pending' | 'completed' | 'cancelled';
}

// Key factory functions
const keys = {
  user: (userId: string) => ({
    PK: `USER#${userId}`,
    SK: 'PROFILE',
  }),
  userOrders: (userId: string) => ({
    PK: `USER#${userId}`,
    SK: 'ORDER#',  // Prefix for begins_with queries
  }),
  order: (orderId: string, userId: string) => ({
    PK: `USER#${userId}`,
    SK: `ORDER#${orderId}`,
    GSI1PK: `ORDER#${orderId}`,
    GSI1SK: `ORDER#${orderId}`,
  }),
};
```

## Application Integration

### Node.js (AWS SDK v3)

```typescript
// dynamodb.ts
import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  QueryCommand,
  UpdateItemCommand,
  DeleteItemCommand,
} from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand as DocQueryCommand } from '@aws-sdk/lib-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'us-east-1',
});

// Document client for easier JSON handling
const docClient = DynamoDBDocumentClient.from(client, {
  marshallOptions: {
    removeUndefinedValues: true,
    convertEmptyValues: false,
  },
});

const TABLE_NAME = process.env.DYNAMODB_TABLE!;

// Get user
export async function getUser(userId: string): Promise<User | null> {
  const response = await docClient.send(
    new GetCommand({
      TableName: TABLE_NAME,
      Key: {
        PK: `USER#${userId}`,
        SK: 'PROFILE',
      },
    })
  );
  return response.Item as User | null;
}

// Create user
export async function createUser(user: Omit<User, 'PK' | 'SK' | 'entityType' | 'createdAt' | 'updatedAt'>): Promise<User> {
  const now = new Date().toISOString();
  const item: User = {
    ...user,
    PK: `USER#${user.userId}`,
    SK: 'PROFILE',
    GSI1PK: `EMAIL#${user.email}`,
    GSI1SK: `USER#${user.userId}`,
    entityType: 'USER',
    createdAt: now,
    updatedAt: now,
  };

  await docClient.send(
    new PutCommand({
      TableName: TABLE_NAME,
      Item: item,
      ConditionExpression: 'attribute_not_exists(PK)',  // Prevent overwrite
    })
  );

  return item;
}

// Get user orders
export async function getUserOrders(userId: string, limit = 20): Promise<Order[]> {
  const response = await docClient.send(
    new DocQueryCommand({
      TableName: TABLE_NAME,
      KeyConditionExpression: 'PK = :pk AND begins_with(SK, :sk)',
      ExpressionAttributeValues: {
        ':pk': `USER#${userId}`,
        ':sk': 'ORDER#',
      },
      Limit: limit,
      ScanIndexForward: false,  // Newest first
    })
  );

  return (response.Items || []) as Order[];
}

// Update order status
export async function updateOrderStatus(orderId: string, userId: string, status: Order['status']): Promise<void> {
  await docClient.send(
    new UpdateItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({
        PK: `USER#${userId}`,
        SK: `ORDER#${orderId}`,
      }),
      UpdateExpression: 'SET #status = :status, updatedAt = :updatedAt',
      ExpressionAttributeNames: {
        '#status': 'status',
      },
      ExpressionAttributeValues: marshall({
        ':status': status,
        ':updatedAt': new Date().toISOString(),
      }),
    })
  );
}

// Transactional write
import { TransactWriteItemsCommand } from '@aws-sdk/client-dynamodb';

export async function createOrderWithInventoryUpdate(order: Order, productId: string, quantity: number): Promise<void> {
  await client.send(
    new TransactWriteItemsCommand({
      TransactItems: [
        {
          Put: {
            TableName: TABLE_NAME,
            Item: marshall(order),
          },
        },
        {
          Update: {
            TableName: TABLE_NAME,
            Key: marshall({
              PK: `PRODUCT#${productId}`,
              SK: 'INVENTORY',
            }),
            UpdateExpression: 'SET quantity = quantity - :qty',
            ConditionExpression: 'quantity >= :qty',
            ExpressionAttributeValues: marshall({
              ':qty': quantity,
            }),
          },
        },
      ],
    })
  );
}
```

### Python (boto3)

```python
# dynamodb.py
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json
from datetime import datetime
import os

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])


def get_user(user_id: str) -> dict | None:
    response = table.get_item(
        Key={
            'PK': f'USER#{user_id}',
            'SK': 'PROFILE',
        }
    )
    return response.get('Item')


def create_user(user_id: str, email: str, name: str) -> dict:
    now = datetime.utcnow().isoformat()
    item = {
        'PK': f'USER#{user_id}',
        'SK': 'PROFILE',
        'GSI1PK': f'EMAIL#{email}',
        'GSI1SK': f'USER#{user_id}',
        'entityType': 'USER',
        'userId': user_id,
        'email': email,
        'name': name,
        'createdAt': now,
        'updatedAt': now,
    }

    table.put_item(
        Item=item,
        ConditionExpression='attribute_not_exists(PK)',
    )

    return item


def get_user_orders(user_id: str, limit: int = 20) -> list:
    response = table.query(
        KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('ORDER#'),
        Limit=limit,
        ScanIndexForward=False,  # Newest first
    )
    return response.get('Items', [])


def update_order_status(user_id: str, order_id: str, status: str) -> None:
    table.update_item(
        Key={
            'PK': f'USER#{user_id}',
            'SK': f'ORDER#{order_id}',
        },
        UpdateExpression='SET #status = :status, updatedAt = :updatedAt',
        ExpressionAttributeNames={
            '#status': 'status',
        },
        ExpressionAttributeValues={
            ':status': status,
            ':updatedAt': datetime.utcnow().isoformat(),
        },
    )


# Batch write (up to 25 items)
def batch_create_items(items: list) -> None:
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
```

### Go

```go
// dynamodb.go
package database

import (
    "context"
    "os"
    "time"

    "github.com/aws/aws-sdk-go-v2/aws"
    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/feature/dynamodb/attributevalue"
    "github.com/aws/aws-sdk-go-v2/service/dynamodb"
    "github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

var client *dynamodb.Client
var tableName string

func Init(ctx context.Context) error {
    cfg, err := config.LoadDefaultConfig(ctx)
    if err != nil {
        return err
    }
    client = dynamodb.NewFromConfig(cfg)
    tableName = os.Getenv("DYNAMODB_TABLE")
    return nil
}

type User struct {
    PK        string `dynamodbav:"PK"`
    SK        string `dynamodbav:"SK"`
    UserID    string `dynamodbav:"userId"`
    Email     string `dynamodbav:"email"`
    Name      string `dynamodbav:"name"`
    CreatedAt string `dynamodbav:"createdAt"`
    UpdatedAt string `dynamodbav:"updatedAt"`
}

func GetUser(ctx context.Context, userID string) (*User, error) {
    result, err := client.GetItem(ctx, &dynamodb.GetItemInput{
        TableName: &tableName,
        Key: map[string]types.AttributeValue{
            "PK": &types.AttributeValueMemberS{Value: "USER#" + userID},
            "SK": &types.AttributeValueMemberS{Value: "PROFILE"},
        },
    })
    if err != nil {
        return nil, err
    }
    if result.Item == nil {
        return nil, nil
    }

    var user User
    err = attributevalue.UnmarshalMap(result.Item, &user)
    return &user, err
}

func CreateUser(ctx context.Context, userID, email, name string) (*User, error) {
    now := time.Now().UTC().Format(time.RFC3339)
    user := User{
        PK:        "USER#" + userID,
        SK:        "PROFILE",
        UserID:    userID,
        Email:     email,
        Name:      name,
        CreatedAt: now,
        UpdatedAt: now,
    }

    item, err := attributevalue.MarshalMap(user)
    if err != nil {
        return nil, err
    }

    _, err = client.PutItem(ctx, &dynamodb.PutItemInput{
        TableName:           &tableName,
        Item:                item,
        ConditionExpression: aws.String("attribute_not_exists(PK)"),
    })
    if err != nil {
        return nil, err
    }

    return &user, nil
}
```

## DynamoDB Streams with Lambda

```typescript
// Stream handler for order processing
import { DynamoDBStreamHandler, DynamoDBRecord } from 'aws-lambda';
import { unmarshall } from '@aws-sdk/util-dynamodb';

export const handler: DynamoDBStreamHandler = async (event) => {
  for (const record of event.Records) {
    if (record.eventName === 'INSERT' && record.dynamodb?.NewImage) {
      const item = unmarshall(record.dynamodb.NewImage as any);

      if (item.entityType === 'ORDER') {
        await processNewOrder(item);
      }
    }

    if (record.eventName === 'MODIFY' && record.dynamodb?.NewImage) {
      const newItem = unmarshall(record.dynamodb.NewImage as any);
      const oldItem = record.dynamodb.OldImage
        ? unmarshall(record.dynamodb.OldImage as any)
        : null;

      if (newItem.entityType === 'ORDER' && newItem.status !== oldItem?.status) {
        await handleOrderStatusChange(newItem, oldItem?.status);
      }
    }
  }
};

async function processNewOrder(order: any) {
  // Send confirmation email, update inventory, etc.
  console.log('Processing new order:', order.orderId);
}

async function handleOrderStatusChange(order: any, oldStatus: string) {
  console.log(`Order ${order.orderId} status changed from ${oldStatus} to ${order.status}`);
}
```

## Cost Breakdown

### On-Demand (PAY_PER_REQUEST)

| Operation | Cost |
|-----------|------|
| Write Request Unit (WRU) | $1.25 per million |
| Read Request Unit (RRU) | $0.25 per million |
| Storage | $0.25 per GB-month |
| Streams | $0.02 per 100K read requests |
| Global Tables | 2x write cost |

### Provisioned Capacity

| Resource | Cost |
|----------|------|
| Write Capacity Unit (WCU) | $0.47 per WCU-month |
| Read Capacity Unit (RCU) | $0.09 per RCU-month |
| Storage | $0.25 per GB-month |
| Reserved Capacity | 53-76% discount |

### Cost Examples

| Workload | RRU/day | WRU/day | Storage | Monthly Cost |
|----------|---------|---------|---------|--------------|
| Light | 1M | 100K | 1 GB | ~$5 |
| Medium | 10M | 1M | 10 GB | ~$40 |
| Heavy | 100M | 10M | 100 GB | ~$400 |
| Enterprise | 1B | 100M | 1 TB | ~$4,000 |

## Best Practices

### Access Pattern Design

```typescript
// Define access patterns FIRST, then design keys

// Access Patterns:
// 1. Get user by ID → PK=USER#id, SK=PROFILE
// 2. Get user by email → GSI1: GSI1PK=EMAIL#email
// 3. Get user's orders → PK=USER#id, SK begins_with ORDER#
// 4. Get order by ID → GSI1: GSI1PK=ORDER#id
// 5. Get orders by status → GSI2: GSI2PK=STATUS#status, GSI2SK=createdAt
```

### Avoid Hot Partitions

```typescript
// BAD - All writes to same partition
const key = {
  PK: 'GLOBAL_COUNTER',  // Hot partition!
  SK: 'value',
};

// GOOD - Distribute writes across partitions
const shardedKey = {
  PK: `COUNTER#${Math.floor(Math.random() * 10)}`,  // Shard 0-9
  SK: 'value',
};

// Read aggregation
async function getCounter(): Promise<number> {
  const shards = await Promise.all(
    Array.from({ length: 10 }, (_, i) =>
      docClient.send(new GetCommand({
        TableName: TABLE_NAME,
        Key: { PK: `COUNTER#${i}`, SK: 'value' },
      }))
    )
  );
  return shards.reduce((sum, shard) => sum + (shard.Item?.count || 0), 0);
}
```

### Efficient Queries

```typescript
// GOOD - Query with specific key condition
const response = await docClient.send(new QueryCommand({
  TableName: TABLE_NAME,
  KeyConditionExpression: 'PK = :pk AND SK BETWEEN :start AND :end',
  ExpressionAttributeValues: {
    ':pk': `USER#${userId}`,
    ':start': 'ORDER#2024-01-01',
    ':end': 'ORDER#2024-12-31',
  },
}));

// BAD - Scan (reads entire table)
const response = await docClient.send(new ScanCommand({
  TableName: TABLE_NAME,
  FilterExpression: 'userId = :userId',  // Filter happens AFTER scan
  ExpressionAttributeValues: { ':userId': userId },
}));
```

## Common Mistakes

1. **Using Scan instead of Query** - Scans read entire table
2. **Hot partitions** - All traffic to same partition key
3. **Designing schema before access patterns** - SQL mindset
4. **Not using GSIs for alternate access patterns** - Forces scans
5. **Over-fetching with ProjectionExpression** - Return only needed attributes
6. **Not handling throttling** - Missing retry with backoff
7. **Large items** - Items > 400KB fail; use S3 for large data
8. **Missing TTL for temporary data** - Manual cleanup required
9. **Not using transactions when needed** - Data inconsistency
10. **Ignoring capacity mode choice** - On-demand vs provisioned cost difference

## Example Configuration

```yaml
# infera.yaml
project_name: my-serverless-api
provider: aws
region: us-east-1
environment: production

database:
  type: dynamodb

  table:
    name: MyApp
    billing_mode: PAY_PER_REQUEST  # or PROVISIONED

    keys:
      partition_key: { name: PK, type: S }
      sort_key: { name: SK, type: S }

    global_secondary_indexes:
      - name: GSI1
        partition_key: { name: GSI1PK, type: S }
        sort_key: { name: GSI1SK, type: S }
        projection: ALL

    ttl:
      enabled: true
      attribute: TTL

    streams:
      enabled: true
      view_type: NEW_AND_OLD_IMAGES

    point_in_time_recovery: true
    encryption: AWS_OWNED  # or CUSTOMER_MANAGED

application:
  runtime: lambda

  functions:
    - name: api
      handler: src/handler.handler

  env:
    DYNAMODB_TABLE:
      from: terraform
      output: table_name
```

## Sources

- [DynamoDB Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table/)
- [DynamoDB Book by Alex DeBrie](https://www.dynamodbbook.com/)
- [AWS SDK v3 Documentation](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/)
- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
