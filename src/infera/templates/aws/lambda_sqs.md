# AWS Lambda + SQS Queue Processor

## Overview

Deploy event-driven queue processing using Lambda with SQS. This architecture provides reliable message processing with automatic retries, dead-letter queues, and seamless scaling. Ideal for background jobs, async processing, and decoupled architectures.

## Detection Signals

Use this template when:
- Background job processing needed
- Async task execution required
- Message queue patterns (producer/consumer)
- Webhook processing
- Email/notification sending
- Order processing pipelines

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                             │
                    │                                                             │
                    │   ┌─────────────────────────────────────────────────────┐   │
    Producer ──────►│   │                  SQS Queue                           │   │
    (API/Service)   │   │                                                     │   │
                    │   │  ┌─────────────────────────────────────────────┐    │   │
                    │   │  │              Messages                        │    │   │
                    │   │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │    │   │
                    │   │  │  │ Msg │ │ Msg │ │ Msg │ │ Msg │ │ Msg │   │    │   │
                    │   │  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │    │   │
                    │   │  └─────────────────────────────────────────────┘    │   │
                    │   └─────────────────────────┬───────────────────────────┘   │
                    │                             │ Event Source Mapping          │
                    │                             ▼                               │
                    │   ┌─────────────────────────────────────────────────────┐   │
                    │   │              Lambda Consumer                         │   │
                    │   │                                                     │   │
                    │   │  ┌───────────────────────────────────────────────┐  │   │
                    │   │  │  async handler(event) {                       │  │   │
                    │   │  │    for (record of event.Records) {            │  │   │
                    │   │  │      await processMessage(record.body);       │  │   │
                    │   │  │    }                                          │  │   │
                    │   │  │  }                                            │  │   │
                    │   │  └───────────────────────────────────────────────┘  │   │
                    │   └─────────────────────────┬───────────────────────────┘   │
                    │                             │ On failure                    │
                    │                             ▼                               │
                    │   ┌─────────────────────────────────────────────────────┐   │
                    │   │           Dead Letter Queue (DLQ)                    │   │
                    │   │         Failed messages for investigation            │   │
                    │   └─────────────────────────────────────────────────────┘   │
                    │                                                             │
                    │   Auto-scaling • At-least-once delivery • Automatic retries │
                    └─────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| SQS Queue | Message storage | Standard or FIFO |
| Lambda Function | Message processing | Event source mapping |
| IAM Role | Permissions | SQS + CloudWatch |
| Dead Letter Queue | Failed messages | Separate SQS queue |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| SNS Topic | Fan-out pattern | Subscriptions |
| DynamoDB | State storage | Table |
| S3 | Large payloads | Bucket |
| CloudWatch Alarms | Monitoring | DLQ depth alerts |
| X-Ray | Tracing | Sampling rules |

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
  default = "queue-processor"
}

# Main SQS Queue
resource "aws_sqs_queue" "main" {
  name                       = "${var.project_name}-queue"
  visibility_timeout_seconds = 300  # 6x Lambda timeout
  message_retention_seconds  = 1209600  # 14 days
  receive_wait_time_seconds  = 20  # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3  # Retry 3 times before DLQ
  })

  tags = {
    Environment = "production"
  }
}

# Dead Letter Queue
resource "aws_sqs_queue" "dlq" {
  name                       = "${var.project_name}-dlq"
  message_retention_seconds  = 1209600  # 14 days

  tags = {
    Environment = "production"
  }
}

# Lambda Function
resource "aws_lambda_function" "processor" {
  filename         = "lambda.zip"
  function_name    = "${var.project_name}-processor"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  memory_size      = 256
  timeout          = 50  # Less than visibility_timeout / 6

  environment {
    variables = {
      QUEUE_URL = aws_sqs_queue.main.url
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }
}

# Event Source Mapping (SQS -> Lambda)
resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn                   = aws_sqs_queue.main.arn
  function_name                      = aws_lambda_function.processor.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5

  # Partial batch failure reporting
  function_response_types = ["ReportBatchItemFailures"]
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

resource "aws_iam_role_policy" "sqs" {
  name = "sqs-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.dlq.arn
      }
    ]
  })
}

# CloudWatch Alarm for DLQ depth
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.project_name}-dlq-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "DLQ has messages that need attention"

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  alarm_actions = []  # Add SNS topic ARN for notifications
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-processor"
  retention_in_days = 14
}

output "queue_url" {
  value = aws_sqs_queue.main.url
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}
```

## Implementation

### Lambda Consumer (Node.js)
```javascript
// index.js
const { SQSClient, DeleteMessageCommand } = require('@aws-sdk/client-sqs');

const sqs = new SQSClient({});

exports.handler = async (event) => {
  console.log(`Processing ${event.Records.length} messages`);

  const batchItemFailures = [];

  for (const record of event.Records) {
    try {
      const message = JSON.parse(record.body);
      await processMessage(message, record);

      console.log(`Successfully processed message ${record.messageId}`);
    } catch (error) {
      console.error(`Error processing message ${record.messageId}:`, error);

      // Report this item as failed for retry
      batchItemFailures.push({
        itemIdentifier: record.messageId
      });
    }
  }

  // Return failed items for partial batch failure
  return {
    batchItemFailures
  };
};

async function processMessage(message, record) {
  const { type, payload } = message;

  switch (type) {
    case 'send_email':
      await sendEmail(payload);
      break;

    case 'process_order':
      await processOrder(payload);
      break;

    case 'generate_report':
      await generateReport(payload);
      break;

    case 'webhook':
      await deliverWebhook(payload);
      break;

    default:
      throw new Error(`Unknown message type: ${type}`);
  }
}

async function sendEmail({ to, subject, body, templateId }) {
  // Use SES, SendGrid, etc.
  const response = await fetch('https://api.sendgrid.com/v3/mail/send', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.SENDGRID_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      personalizations: [{ to: [{ email: to }] }],
      from: { email: 'noreply@example.com' },
      subject,
      content: [{ type: 'text/html', value: body }]
    })
  });

  if (!response.ok) {
    throw new Error(`Email failed: ${response.status}`);
  }
}

async function processOrder({ orderId, items, customerId }) {
  // Process order logic
  console.log(`Processing order ${orderId} for customer ${customerId}`);

  // Validate inventory
  // Charge payment
  // Update order status
  // Send confirmation
}

async function generateReport({ reportType, parameters, destination }) {
  // Generate report
  console.log(`Generating ${reportType} report`);

  // Query data
  // Generate report
  // Upload to S3
  // Notify user
}

async function deliverWebhook({ url, payload, headers }) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Webhook failed: ${response.status}`);
  }
}
```

### Lambda Consumer (Python)
```python
# handler.py
import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Processing {len(event['Records'])} messages")

    batch_item_failures = []

    for record in event['Records']:
        try:
            message = json.loads(record['body'])
            process_message(message, record)

            logger.info(f"Successfully processed message {record['messageId']}")
        except Exception as e:
            logger.error(f"Error processing message {record['messageId']}: {e}")

            # Report this item as failed for retry
            batch_item_failures.append({
                'itemIdentifier': record['messageId']
            })

    # Return failed items for partial batch failure
    return {
        'batchItemFailures': batch_item_failures
    }


def process_message(message, record):
    msg_type = message.get('type')
    payload = message.get('payload', {})

    handlers = {
        'send_email': send_email,
        'process_order': process_order,
        'generate_report': generate_report,
        'webhook': deliver_webhook,
    }

    handler_func = handlers.get(msg_type)
    if not handler_func:
        raise ValueError(f"Unknown message type: {msg_type}")

    handler_func(payload)


def send_email(payload):
    import requests

    response = requests.post(
        'https://api.sendgrid.com/v3/mail/send',
        headers={
            'Authorization': f"Bearer {os.environ['SENDGRID_API_KEY']}",
            'Content-Type': 'application/json'
        },
        json={
            'personalizations': [{'to': [{'email': payload['to']}]}],
            'from': {'email': 'noreply@example.com'},
            'subject': payload['subject'],
            'content': [{'type': 'text/html', 'value': payload['body']}]
        }
    )

    if not response.ok:
        raise Exception(f"Email failed: {response.status_code}")


def process_order(payload):
    logger.info(f"Processing order {payload['orderId']}")
    # Process order logic


def generate_report(payload):
    logger.info(f"Generating {payload['reportType']} report")
    # Generate report logic


def deliver_webhook(payload):
    import requests

    response = requests.post(
        payload['url'],
        headers={'Content-Type': 'application/json', **payload.get('headers', {})},
        json=payload['payload']
    )

    if not response.ok:
        raise Exception(f"Webhook failed: {response.status_code}")
```

### Producer API (sends messages to queue)
```javascript
// producer.js
const { SQSClient, SendMessageCommand, SendMessageBatchCommand } = require('@aws-sdk/client-sqs');

const sqs = new SQSClient({});
const QUEUE_URL = process.env.QUEUE_URL;

// Send single message
async function sendMessage(type, payload, options = {}) {
  const command = new SendMessageCommand({
    QueueUrl: QUEUE_URL,
    MessageBody: JSON.stringify({ type, payload }),
    DelaySeconds: options.delaySeconds || 0,
    MessageAttributes: options.attributes || {}
  });

  return sqs.send(command);
}

// Send batch of messages
async function sendBatch(messages) {
  const entries = messages.map((msg, index) => ({
    Id: `msg-${index}`,
    MessageBody: JSON.stringify(msg)
  }));

  // SQS batch limit is 10 messages
  const batches = [];
  for (let i = 0; i < entries.length; i += 10) {
    batches.push(entries.slice(i, i + 10));
  }

  const results = [];
  for (const batch of batches) {
    const command = new SendMessageBatchCommand({
      QueueUrl: QUEUE_URL,
      Entries: batch
    });
    results.push(await sqs.send(command));
  }

  return results;
}

// Example usage
async function queueEmailJob(to, subject, body) {
  return sendMessage('send_email', { to, subject, body });
}

async function queueOrderProcessing(orderId, items, customerId) {
  return sendMessage('process_order', { orderId, items, customerId });
}

module.exports = { sendMessage, sendBatch, queueEmailJob, queueOrderProcessing };
```

## Deployment Commands

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure credentials
aws configure

# Package Lambda
cd lambda && npm install && zip -r ../lambda.zip . && cd ..

# Deploy with Terraform
terraform init
terraform plan
terraform apply

# Send test message
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789/queue-processor-queue \
  --message-body '{"type": "send_email", "payload": {"to": "test@example.com", "subject": "Test", "body": "Hello"}}'

# View queue metrics
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789/queue-processor-queue \
  --attribute-names ApproximateNumberOfMessages

# View DLQ
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789/queue-processor-dlq

# View Lambda logs
aws logs tail /aws/lambda/queue-processor-processor --follow
```

## Best Practices

### Message Design
1. Keep messages small (< 256KB)
2. Include all data needed for processing
3. Design for idempotency (use deduplication IDs)
4. Add correlation IDs for tracing
5. Include message version for schema evolution

### Queue Configuration
1. Set visibility timeout to 6x Lambda timeout
2. Use long polling (20 seconds)
3. Configure appropriate retention period
4. Use FIFO queues for ordering requirements
5. Set up dead-letter queues

### Error Handling
1. Use partial batch failure reporting
2. Implement exponential backoff
3. Set appropriate max receive count
4. Monitor DLQ depth
5. Create alerts for failed messages

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| SQS requests | 1M/month | $0.40/million |
| Lambda requests | 1M/month | $0.20/million |
| Lambda duration | 400k GB-s | $0.0000166667/GB-s |
| CloudWatch Logs | 5GB | $0.50/GB |

### Example Costs
| Scale | Messages/mo | SQS | Lambda | Total |
|-------|-------------|-----|--------|-------|
| Low | 100k | $0 | $0 | $0 |
| Medium | 5M | $2 | $1 | ~$3 |
| High | 50M | $20 | $10 | ~$30 |

## Common Mistakes

1. **Wrong visibility timeout**: Should be 6x Lambda timeout
2. **No partial batch failures**: All messages retry on single failure
3. **Missing DLQ**: Failed messages lost forever
4. **No idempotency**: Duplicate processing on retries
5. **Large messages**: Use S3 for payloads > 256KB
6. **Blocking calls**: Lambda times out waiting for responses
7. **No monitoring**: DLQ fills up unnoticed

## Example Configuration

```yaml
project_name: queue-processor
provider: aws
architecture_type: lambda_sqs

resources:
  - id: main-queue
    type: aws_sqs_queue
    name: jobs
    provider: aws
    config:
      visibility_timeout: 300
      message_retention: 1209600
      max_receive_count: 3

  - id: dlq
    type: aws_sqs_queue
    name: jobs-dlq
    provider: aws
    config:
      message_retention: 1209600

  - id: processor
    type: aws_lambda
    name: queue-processor
    provider: aws
    config:
      runtime: nodejs20.x
      memory: 256
      timeout: 50
      event_source: main-queue
      batch_size: 10
```

## Sources

- [AWS Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [SQS Best Practices](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html)
- [Partial Batch Failures](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting)
