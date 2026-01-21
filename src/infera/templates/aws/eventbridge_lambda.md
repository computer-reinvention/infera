# AWS EventBridge + Lambda Event-Driven

## Overview

Build event-driven architectures using Amazon EventBridge for event routing and Lambda for processing. This pattern enables loose coupling, scalability, and seamless integration with AWS services and SaaS applications.

## Detection Signals

Use this template when:
- Event-driven architecture needed
- Loose coupling between services
- Scheduled tasks (cron jobs)
- Third-party integrations (SaaS events)
- Cross-account event routing
- Complex event filtering

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                   Event Sources                          │   │
                    │   │                                                         │   │
                    │   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
                    │   │  │ AWS     │ │ Custom  │ │ SaaS    │ │Schedule │       │   │
                    │   │  │Services │ │  Apps   │ │Partners │ │ (Cron)  │       │   │
                    │   │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │   │
                    │   └───────┼───────────┼──────────┼───────────┼────────────┘   │
                    │           │           │          │           │                 │
                    │           ▼           ▼          ▼           ▼                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    EventBridge                           │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                   Event Bus                        │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌─────────────┐  ┌─────────────┐                 │  │   │
                    │   │  │  │   Rules     │  │   Filters   │                 │  │   │
                    │   │  │  │ source=X    │  │ detail.type │                 │  │   │
                    │   │  │  │ detail-type │  │ detail.id   │                 │  │   │
                    │   │  │  └─────────────┘  └─────────────┘                 │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └────────────────────────┬────────────────────────────────┘   │
                    │                            │                                    │
                    │           ┌────────────────┼────────────────┐                  │
                    │           │                │                │                  │
                    │           ▼                ▼                ▼                  │
                    │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
                    │   │   Lambda     │ │    SQS       │ │  Step        │          │
                    │   │  Function    │ │   Queue      │ │  Functions   │          │
                    │   └──────────────┘ └──────────────┘ └──────────────┘          │
                    │                                                                 │
                    │   Serverless • 2,400+ event sources • Complex filtering         │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| EventBridge Bus | Event routing | Default or custom |
| EventBridge Rule | Event filtering | Pattern matching |
| Lambda Function | Event processing | Handler |
| IAM Role | Permissions | Lambda execution |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Dead Letter Queue | Failed events | SQS queue |
| CloudWatch | Monitoring | Metrics, logs |
| Event Archive | Replay events | Archive |
| API Destination | HTTP webhooks | Connection |

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
  region = var.region
}

variable "region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "event-driven"
}

# Custom Event Bus
resource "aws_cloudwatch_event_bus" "main" {
  name = "${var.project_name}-bus"

  tags = {
    Environment = "production"
  }
}

# Event Archive (for replay)
resource "aws_cloudwatch_event_archive" "main" {
  name             = "${var.project_name}-archive"
  event_source_arn = aws_cloudwatch_event_bus.main.arn
  retention_days   = 30

  event_pattern = jsonencode({
    source = [{ prefix = "" }]
  })
}

# Lambda Function for Order Processing
resource "aws_lambda_function" "order_processor" {
  filename         = "order_processor.zip"
  function_name    = "${var.project_name}-order-processor"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.orders.name
    }
  }
}

# Lambda Function for Notifications
resource "aws_lambda_function" "notifier" {
  filename         = "notifier.zip"
  function_name    = "${var.project_name}-notifier"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  memory_size      = 128
  timeout          = 30

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.notifications.arn
    }
  }
}

# Lambda Function for Analytics
resource "aws_lambda_function" "analytics" {
  filename         = "analytics.zip"
  function_name    = "${var.project_name}-analytics"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  memory_size      = 256
  timeout          = 60

  environment {
    variables = {
      FIREHOSE_STREAM = aws_kinesis_firehose_delivery_stream.analytics.name
    }
  }
}

# EventBridge Rule - Order Created
resource "aws_cloudwatch_event_rule" "order_created" {
  name           = "${var.project_name}-order-created"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["app.orders"]
    detail-type = ["OrderCreated"]
  })

  tags = {
    Environment = "production"
  }
}

resource "aws_cloudwatch_event_target" "order_processor" {
  rule           = aws_cloudwatch_event_rule.order_created.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id      = "OrderProcessor"
  arn            = aws_lambda_function.order_processor.arn

  # Retry policy
  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }

  # Dead letter queue
  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

# EventBridge Rule - Order Status Changed (with filtering)
resource "aws_cloudwatch_event_rule" "order_status_changed" {
  name           = "${var.project_name}-order-status-changed"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source      = ["app.orders"]
    detail-type = ["OrderStatusChanged"]
    detail = {
      status = ["SHIPPED", "DELIVERED", "CANCELLED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "notifier" {
  rule           = aws_cloudwatch_event_rule.order_status_changed.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id      = "Notifier"
  arn            = aws_lambda_function.notifier.arn

  # Transform input
  input_transformer {
    input_paths = {
      orderId = "$.detail.orderId"
      status  = "$.detail.status"
      email   = "$.detail.customerEmail"
    }
    input_template = <<EOF
{
  "orderId": <orderId>,
  "status": <status>,
  "email": <email>,
  "message": "Your order <orderId> has been <status>"
}
EOF
  }
}

# EventBridge Rule - All Events to Analytics
resource "aws_cloudwatch_event_rule" "all_events" {
  name           = "${var.project_name}-all-events"
  event_bus_name = aws_cloudwatch_event_bus.main.name

  event_pattern = jsonencode({
    source = [{ prefix = "app." }]
  })
}

resource "aws_cloudwatch_event_target" "analytics" {
  rule           = aws_cloudwatch_event_rule.all_events.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id      = "Analytics"
  arn            = aws_lambda_function.analytics.arn
}

# EventBridge Rule - Scheduled Task (Cron)
resource "aws_cloudwatch_event_rule" "daily_report" {
  name                = "${var.project_name}-daily-report"
  schedule_expression = "cron(0 9 * * ? *)"  # 9 AM UTC daily

  tags = {
    Environment = "production"
  }
}

resource "aws_cloudwatch_event_target" "daily_report" {
  rule      = aws_cloudwatch_event_rule.daily_report.name
  target_id = "DailyReport"
  arn       = aws_lambda_function.analytics.arn

  input = jsonencode({
    type = "daily_report"
    date = "today"
  })
}

# Lambda Permissions for EventBridge
resource "aws_lambda_permission" "order_processor" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.order_processor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.order_created.arn
}

resource "aws_lambda_permission" "notifier" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.order_status_changed.arn
}

resource "aws_lambda_permission" "analytics" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytics.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.all_events.arn
}

resource "aws_lambda_permission" "daily_report" {
  statement_id  = "AllowEventBridgeSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytics.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_report.arn
}

# Dead Letter Queue
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = 1209600  # 14 days
}

# DynamoDB Table
resource "aws_dynamodb_table" "orders" {
  name         = "${var.project_name}-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"

  attribute {
    name = "orderId"
    type = "S"
  }
}

# SNS Topic for Notifications
resource "aws_sns_topic" "notifications" {
  name = "${var.project_name}-notifications"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_services" {
  name = "services-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = aws_cloudwatch_event_bus.main.arn
      }
    ]
  })
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "order_processor" {
  name              = "/aws/lambda/${aws_lambda_function.order_processor.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "notifier" {
  name              = "/aws/lambda/${aws_lambda_function.notifier.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "analytics" {
  name              = "/aws/lambda/${aws_lambda_function.analytics.function_name}"
  retention_in_days = 14
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.main.name
}

output "event_bus_arn" {
  value = aws_cloudwatch_event_bus.main.arn
}
```

## Implementation

### Event Publisher
```javascript
// publisher.js
const { EventBridgeClient, PutEventsCommand } = require('@aws-sdk/client-eventbridge');

const eventbridge = new EventBridgeClient({});
const EVENT_BUS_NAME = process.env.EVENT_BUS_NAME || 'default';

async function publishEvent(source, detailType, detail) {
  const command = new PutEventsCommand({
    Entries: [{
      EventBusName: EVENT_BUS_NAME,
      Source: source,
      DetailType: detailType,
      Detail: JSON.stringify(detail),
      Time: new Date()
    }]
  });

  const response = await eventbridge.send(command);

  if (response.FailedEntryCount > 0) {
    throw new Error(`Failed to publish event: ${JSON.stringify(response.Entries)}`);
  }

  return response;
}

// Example usage
async function createOrder(orderData) {
  // Save order to database
  const order = await saveOrder(orderData);

  // Publish event
  await publishEvent('app.orders', 'OrderCreated', {
    orderId: order.id,
    customerId: order.customerId,
    customerEmail: order.email,
    items: order.items,
    total: order.total,
    createdAt: order.createdAt
  });

  return order;
}

async function updateOrderStatus(orderId, status) {
  // Update in database
  const order = await updateOrder(orderId, { status });

  // Publish event
  await publishEvent('app.orders', 'OrderStatusChanged', {
    orderId: order.id,
    status: status,
    previousStatus: order.previousStatus,
    customerEmail: order.email,
    updatedAt: new Date().toISOString()
  });

  return order;
}

module.exports = { publishEvent, createOrder, updateOrderStatus };
```

### Order Processor Lambda
```javascript
// order_processor/index.js
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);
const TABLE_NAME = process.env.TABLE_NAME;

exports.handler = async (event) => {
  console.log('Processing event:', JSON.stringify(event, null, 2));

  const { detail } = event;

  // Process order
  const order = {
    orderId: detail.orderId,
    customerId: detail.customerId,
    items: detail.items,
    total: detail.total,
    status: 'PENDING',
    createdAt: detail.createdAt,
    processedAt: new Date().toISOString()
  };

  // Save to DynamoDB
  await docClient.send(new PutCommand({
    TableName: TABLE_NAME,
    Item: order
  }));

  console.log('Order processed:', order.orderId);

  return {
    statusCode: 200,
    body: JSON.stringify({ orderId: order.orderId })
  };
};
```

### Notification Lambda
```javascript
// notifier/index.js
const { SNSClient, PublishCommand } = require('@aws-sdk/client-sns');

const sns = new SNSClient({});
const TOPIC_ARN = process.env.SNS_TOPIC_ARN;

exports.handler = async (event) => {
  console.log('Notification event:', JSON.stringify(event, null, 2));

  const { orderId, status, email, message } = event;

  // Send notification via SNS
  await sns.send(new PublishCommand({
    TopicArn: TOPIC_ARN,
    Subject: `Order ${orderId} - ${status}`,
    Message: JSON.stringify({
      email,
      subject: `Order Update: ${orderId}`,
      body: message,
      timestamp: new Date().toISOString()
    }),
    MessageAttributes: {
      email: {
        DataType: 'String',
        StringValue: email
      }
    }
  }));

  console.log('Notification sent for order:', orderId);

  return { statusCode: 200 };
};
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Package and deploy Lambda functions
cd order_processor && zip -r ../order_processor.zip . && cd ..
cd notifier && zip -r ../notifier.zip . && cd ..
cd analytics && zip -r ../analytics.zip . && cd ..

aws lambda update-function-code \
  --function-name event-driven-order-processor \
  --zip-file fileb://order_processor.zip

# Test by sending an event
aws events put-events \
  --entries '[{
    "EventBusName": "event-driven-bus",
    "Source": "app.orders",
    "DetailType": "OrderCreated",
    "Detail": "{\"orderId\": \"123\", \"customerId\": \"456\", \"total\": 99.99}"
  }]'

# View Lambda logs
aws logs tail /aws/lambda/event-driven-order-processor --follow

# Replay archived events
aws events start-replay \
  --replay-name test-replay \
  --event-source-arn arn:aws:events:us-east-1:123456789:event-bus/event-driven-bus \
  --destination '{"Arn": "arn:aws:events:us-east-1:123456789:event-bus/event-driven-bus"}' \
  --event-start-time 2024-01-01T00:00:00Z \
  --event-end-time 2024-01-02T00:00:00Z
```

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| EventBridge Events | - | $1.00/million |
| Lambda Requests | 1M/month | $0.20/million |
| Lambda Duration | 400k GB-s | $0.0000166667/GB-s |
| CloudWatch Logs | 5GB | $0.50/GB |

### Example Costs
| Scale | Events/mo | Lambda | Total |
|-------|-----------|--------|-------|
| Small | 1M | 1M invokes | ~$2 |
| Medium | 10M | 10M invokes | ~$15 |
| Large | 100M | 100M invokes | ~$130 |

## Best Practices

### Event Design
1. Use consistent event schema
2. Include correlation IDs
3. Version your events
4. Keep events small (< 256KB)
5. Use meaningful source/detail-type

### Error Handling
1. Configure dead-letter queues
2. Set appropriate retry policies
3. Implement idempotency
4. Log failed events
5. Monitor DLQ depth

### Patterns
1. Use event archive for replay
2. Implement event versioning
3. Use input transformers
4. Cross-account event sharing
5. Fan-out to multiple targets

## Common Mistakes

1. **No dead-letter queue**: Lost events
2. **Missing permissions**: Lambda can't process
3. **Wrong event pattern**: Events not matched
4. **No idempotency**: Duplicate processing
5. **Large events**: Exceeds 256KB limit

## Sources

- [EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/)
- [EventBridge Patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)
- [EventBridge Best Practices](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-best-practices.html)
