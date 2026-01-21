# AWS Lambda API

## Overview

Deploy serverless REST APIs using AWS Lambda with API Gateway. This architecture provides automatic scaling, pay-per-request pricing, and zero server management. Ideal for APIs with variable traffic patterns.

## Detection Signals

Use this template when:
- Serverless API requirements
- Variable or unpredictable traffic
- Pay-per-request pricing preference
- Minimal operational overhead needed
- Sub-second cold starts acceptable
- Request duration < 15 minutes

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                     AWS Cloud                            │
                    │                                                         │
    Internet ──────►│   ┌─────────────────────────────────────────────────┐   │
                    │   │              API Gateway                         │   │
                    │   │                                                 │   │
                    │   │  ┌─────────┐       ┌─────────────────────────┐  │   │
                    │   │  │  REST   │──────►│    Lambda Functions     │  │   │
                    │   │  │  API    │       │                         │  │   │
                    │   │  └─────────┘       │  ┌───────────────────┐  │  │   │
                    │   │                    │  │  - GET /items     │  │  │   │
                    │   │                    │  │  - POST /items    │  │  │   │
                    │   │                    │  │  - GET /items/:id │  │  │   │
                    │   │                    │  │  - PUT /items/:id │  │  │   │
                    │   │                    │  │  - DELETE /:id    │  │  │   │
                    │   │                    │  └───────────────────┘  │  │   │
                    │   │                    └─────────────────────────┘  │   │
                    │   └─────────────────────────────────────────────────┘   │
                    │                           │                             │
                    │                           ▼                             │
                    │   ┌─────────────────────────────────────────────────┐   │
                    │   │                  DynamoDB                        │   │
                    │   │              (or RDS/Aurora)                     │   │
                    │   └─────────────────────────────────────────────────┘   │
                    │                                                         │
                    │   Auto-scaling • Pay per request • Zero servers         │
                    └─────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Lambda Function | API logic | Runtime, memory, timeout |
| API Gateway | HTTP routing | REST or HTTP API |
| IAM Role | Permissions | Lambda execution role |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| DynamoDB | NoSQL storage | Table, indexes |
| RDS/Aurora | SQL storage | Instance, VPC |
| S3 | File storage | Bucket |
| Cognito | Authentication | User pool |
| CloudWatch | Monitoring | Alarms, dashboards |
| X-Ray | Tracing | Sampling rules |
| WAF | Security | Web ACL |

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

variable "function_name" {
  default = "my-api"
}

# Lambda Function
resource "aws_lambda_function" "api" {
  filename         = "lambda.zip"
  function_name    = var.function_name
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.main.name
    }
  }
}

# API Gateway HTTP API (cheaper than REST API)
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.function_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
  }
}

resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${var.function_name}-role"

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

resource "aws_iam_role_policy" "dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      Resource = [
        aws_dynamodb_table.main.arn,
        "${aws_dynamodb_table.main.arn}/index/*"
      ]
    }]
  })
}

# DynamoDB Table
resource "aws_dynamodb_table" "main" {
  name         = "${var.function_name}-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  tags = {
    Environment = "production"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${var.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 14
}

output "api_url" {
  value = aws_apigatewayv2_stage.api.invoke_url
}
```

## Implementation

### Lambda Handler (Node.js)
```javascript
// index.js
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand, DeleteCommand } = require('@aws-sdk/lib-dynamodb');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);
const TABLE_NAME = process.env.TABLE_NAME;

exports.handler = async (event) => {
  const { routeKey, pathParameters, body } = event;
  const method = event.requestContext?.http?.method || 'GET';
  const path = event.rawPath || '/';

  try {
    // Route handling
    if (method === 'GET' && path === '/items') {
      return await listItems();
    }

    if (method === 'GET' && path.startsWith('/items/')) {
      const id = pathParameters?.id;
      return await getItem(id);
    }

    if (method === 'POST' && path === '/items') {
      const data = JSON.parse(body);
      return await createItem(data);
    }

    if (method === 'PUT' && path.startsWith('/items/')) {
      const id = pathParameters?.id;
      const data = JSON.parse(body);
      return await updateItem(id, data);
    }

    if (method === 'DELETE' && path.startsWith('/items/')) {
      const id = pathParameters?.id;
      return await deleteItem(id);
    }

    return response(404, { error: 'Not found' });
  } catch (error) {
    console.error('Error:', error);
    return response(500, { error: 'Internal server error' });
  }
};

async function listItems() {
  const result = await docClient.send(new QueryCommand({
    TableName: TABLE_NAME,
    KeyConditionExpression: 'pk = :pk',
    ExpressionAttributeValues: {
      ':pk': 'ITEM'
    }
  }));

  return response(200, { items: result.Items });
}

async function getItem(id) {
  const result = await docClient.send(new GetCommand({
    TableName: TABLE_NAME,
    Key: { pk: 'ITEM', sk: id }
  }));

  if (!result.Item) {
    return response(404, { error: 'Item not found' });
  }

  return response(200, result.Item);
}

async function createItem(data) {
  const id = `item_${Date.now()}`;
  const item = {
    pk: 'ITEM',
    sk: id,
    ...data,
    createdAt: new Date().toISOString()
  };

  await docClient.send(new PutCommand({
    TableName: TABLE_NAME,
    Item: item
  }));

  return response(201, item);
}

async function updateItem(id, data) {
  const item = {
    pk: 'ITEM',
    sk: id,
    ...data,
    updatedAt: new Date().toISOString()
  };

  await docClient.send(new PutCommand({
    TableName: TABLE_NAME,
    Item: item
  }));

  return response(200, item);
}

async function deleteItem(id) {
  await docClient.send(new DeleteCommand({
    TableName: TABLE_NAME,
    Key: { pk: 'ITEM', sk: id }
  }));

  return response(204, null);
}

function response(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    },
    body: body ? JSON.stringify(body) : ''
  };
}
```

### Lambda Handler (Python)
```python
# handler.py
import json
import os
import boto3
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('rawPath', '/')
    path_params = event.get('pathParameters', {}) or {}

    try:
        if method == 'GET' and path == '/items':
            return list_items()

        if method == 'GET' and path.startswith('/items/'):
            return get_item(path_params.get('id'))

        if method == 'POST' and path == '/items':
            body = json.loads(event.get('body', '{}'))
            return create_item(body)

        if method == 'PUT' and path.startswith('/items/'):
            body = json.loads(event.get('body', '{}'))
            return update_item(path_params.get('id'), body)

        if method == 'DELETE' and path.startswith('/items/'):
            return delete_item(path_params.get('id'))

        return response(404, {'error': 'Not found'})

    except Exception as e:
        print(f'Error: {e}')
        return response(500, {'error': 'Internal server error'})


def list_items():
    result = table.query(
        KeyConditionExpression='pk = :pk',
        ExpressionAttributeValues={':pk': 'ITEM'}
    )
    return response(200, {'items': result.get('Items', [])})


def get_item(item_id):
    result = table.get_item(Key={'pk': 'ITEM', 'sk': item_id})
    item = result.get('Item')

    if not item:
        return response(404, {'error': 'Item not found'})

    return response(200, item)


def create_item(data):
    item_id = f"item_{int(datetime.now().timestamp() * 1000)}"
    item = {
        'pk': 'ITEM',
        'sk': item_id,
        **data,
        'createdAt': datetime.now().isoformat()
    }

    table.put_item(Item=item)
    return response(201, item)


def update_item(item_id, data):
    item = {
        'pk': 'ITEM',
        'sk': item_id,
        **data,
        'updatedAt': datetime.now().isoformat()
    }

    table.put_item(Item=item)
    return response(200, item)


def delete_item(item_id):
    table.delete_item(Key={'pk': 'ITEM', 'sk': item_id})
    return response(204, None)


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str) if body else ''
    }
```

## Deployment Commands

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure credentials
aws configure

# Package Lambda (Node.js)
cd lambda && npm install && zip -r ../lambda.zip . && cd ..

# Package Lambda (Python)
cd lambda && pip install -r requirements.txt -t . && zip -r ../lambda.zip . && cd ..

# Deploy with Terraform
terraform init
terraform plan
terraform apply

# Test API
curl https://xxx.execute-api.us-east-1.amazonaws.com/items
curl -X POST https://xxx.execute-api.us-east-1.amazonaws.com/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Item"}'

# View logs
aws logs tail /aws/lambda/my-api --follow
```

## Best Practices

### Performance
1. Keep Lambda packages small (< 50MB)
2. Use provisioned concurrency for consistent latency
3. Initialize SDK clients outside handler
4. Use connection pooling for databases
5. Enable X-Ray for tracing

### Security
1. Use least-privilege IAM policies
2. Enable API Gateway authorization
3. Validate and sanitize inputs
4. Use environment variables for secrets
5. Enable VPC for database access

### Cost Optimization
1. Right-size memory allocation
2. Use HTTP API instead of REST API (70% cheaper)
3. Set appropriate timeouts
4. Use DynamoDB on-demand for variable traffic
5. Monitor with CloudWatch

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Lambda requests | 1M/month | $0.20/million |
| Lambda duration | 400k GB-s | $0.0000166667/GB-s |
| API Gateway (HTTP) | 1M/month | $1.00/million |
| DynamoDB reads | 25 RCU | $0.25/million RRU |
| DynamoDB writes | 25 WCU | $1.25/million WRU |

### Example Costs
| Traffic | Requests/mo | Lambda | API GW | DynamoDB | Total |
|---------|-------------|--------|--------|----------|-------|
| Low | 100k | $0 | $0 | $0 | $0 |
| Medium | 1M | $0.20 | $1 | $2 | ~$3 |
| High | 10M | $2 | $10 | $20 | ~$32 |

## Common Mistakes

1. **Cold starts**: Not using provisioned concurrency for latency-sensitive APIs
2. **Timeouts**: Setting timeout too low for DB operations
3. **Package size**: Including unnecessary dependencies
4. **IAM policies**: Overly permissive permissions
5. **No error handling**: Unhandled exceptions crash Lambda
6. **Synchronous operations**: Blocking on external calls
7. **Missing CORS**: Browser requests fail

## Example Configuration

```yaml
project_name: my-lambda-api
provider: aws
architecture_type: lambda_api

resources:
  - id: api-function
    type: aws_lambda
    name: my-api
    provider: aws
    config:
      runtime: nodejs20.x
      memory: 256
      timeout: 30
      handler: index.handler

  - id: api-gateway
    type: aws_apigateway_v2
    name: my-api
    provider: aws
    config:
      protocol: HTTP
      cors: true

  - id: data-table
    type: aws_dynamodb
    name: my-api-table
    provider: aws
    config:
      billing_mode: PAY_PER_REQUEST
      hash_key: pk
      range_key: sk
```

## Sources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table/)
