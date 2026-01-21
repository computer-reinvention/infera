# AWS Step Functions Workflow Orchestration

## Overview

Build complex workflow orchestration using AWS Step Functions with Lambda. This architecture provides visual workflow design, automatic error handling, state management, and seamless integration with AWS services. Ideal for multi-step processes, long-running workflows, and business process automation.

## Detection Signals

Use this template when:
- Multi-step workflows needed
- Complex business logic orchestration
- Long-running processes (up to 1 year)
- Parallel processing required
- Human approval workflows
- Saga pattern implementation

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Cloud                                 │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Step Functions                          │   │
                    │   │               (State Machine)                            │   │
                    │   │                                                         │   │
                    │   │  ┌─────────────────────────────────────────────────┐    │   │
                    │   │  │              Order Processing Workflow           │    │   │
                    │   │  │                                                 │    │   │
                    │   │  │  ┌──────────┐                                   │    │   │
                    │   │  │  │  Start   │                                   │    │   │
                    │   │  │  └────┬─────┘                                   │    │   │
                    │   │  │       │                                         │    │   │
                    │   │  │       ▼                                         │    │   │
                    │   │  │  ┌──────────┐                                   │    │   │
                    │   │  │  │ Validate │──► Lambda                         │    │   │
                    │   │  │  │  Order   │                                   │    │   │
                    │   │  │  └────┬─────┘                                   │    │   │
                    │   │  │       │                                         │    │   │
                    │   │  │       ▼                                         │    │   │
                    │   │  │  ┌──────────────────────────────┐               │    │   │
                    │   │  │  │        Parallel              │               │    │   │
                    │   │  │  │  ┌────────┐  ┌────────────┐  │               │    │   │
                    │   │  │  │  │ Reserve│  │  Process   │  │               │    │   │
                    │   │  │  │  │ Stock  │  │  Payment   │  │               │    │   │
                    │   │  │  │  └────────┘  └────────────┘  │               │    │   │
                    │   │  │  └──────────────────────────────┘               │    │   │
                    │   │  │       │                                         │    │   │
                    │   │  │       ▼                                         │    │   │
                    │   │  │  ┌──────────┐                                   │    │   │
                    │   │  │  │ Ship     │──► Lambda                         │    │   │
                    │   │  │  │ Order    │                                   │    │   │
                    │   │  │  └────┬─────┘                                   │    │   │
                    │   │  │       │                                         │    │   │
                    │   │  │       ▼                                         │    │   │
                    │   │  │  ┌──────────┐                                   │    │   │
                    │   │  │  │   End    │                                   │    │   │
                    │   │  │  └──────────┘                                   │    │   │
                    │   │  └─────────────────────────────────────────────────┘    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Visual workflow • Automatic retries • State management        │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| State Machine | Workflow definition | ASL (Amazon States Language) |
| Lambda Functions | Task execution | One per step |
| IAM Role | Permissions | Step Functions execution |
| CloudWatch Logs | Logging | Log group |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| SNS | Notifications | Task tokens |
| SQS | Message queuing | Integration |
| DynamoDB | State storage | Tables |
| EventBridge | Triggers | Rules |
| X-Ray | Tracing | Enabled |

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
  default = "order-workflow"
}

# State Machine
resource "aws_sfn_state_machine" "order_processing" {
  name     = "${var.project_name}-state-machine"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Order Processing Workflow"
    StartAt = "ValidateOrder"
    States = {
      ValidateOrder = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.validate_order.arn
          Payload = {
            "orderId.$" = "$.orderId"
            "items.$"   = "$.items"
          }
        }
        ResultPath = "$.validation"
        Next       = "CheckValidation"
        Retry = [{
          ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException"]
          IntervalSeconds = 2
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "OrderFailed"
          ResultPath  = "$.error"
        }]
      }

      CheckValidation = {
        Type = "Choice"
        Choices = [{
          Variable      = "$.validation.isValid"
          BooleanEquals = true
          Next          = "ProcessOrderParallel"
        }]
        Default = "OrderInvalid"
      }

      ProcessOrderParallel = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "ReserveInventory"
            States = {
              ReserveInventory = {
                Type     = "Task"
                Resource = "arn:aws:states:::lambda:invoke"
                Parameters = {
                  FunctionName = aws_lambda_function.reserve_inventory.arn
                  Payload = {
                    "orderId.$" = "$.orderId"
                    "items.$"   = "$.items"
                  }
                }
                End = true
                Retry = [{
                  ErrorEquals     = ["States.ALL"]
                  IntervalSeconds = 1
                  MaxAttempts     = 3
                  BackoffRate     = 2
                }]
              }
            }
          },
          {
            StartAt = "ProcessPayment"
            States = {
              ProcessPayment = {
                Type     = "Task"
                Resource = "arn:aws:states:::lambda:invoke"
                Parameters = {
                  FunctionName = aws_lambda_function.process_payment.arn
                  Payload = {
                    "orderId.$"  = "$.orderId"
                    "amount.$"   = "$.total"
                    "paymentMethod.$" = "$.paymentMethod"
                  }
                }
                End = true
                Retry = [{
                  ErrorEquals     = ["PaymentRetryable"]
                  IntervalSeconds = 5
                  MaxAttempts     = 2
                  BackoffRate     = 2
                }]
              }
            }
          }
        ]
        ResultPath = "$.parallelResults"
        Next       = "ShipOrder"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "CompensateOrder"
          ResultPath  = "$.error"
        }]
      }

      ShipOrder = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.ship_order.arn
          Payload = {
            "orderId.$" = "$.orderId"
          }
        }
        ResultPath = "$.shipping"
        Next       = "NotifyCustomer"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "ShippingFailed"
          ResultPath  = "$.error"
        }]
      }

      NotifyCustomer = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.notifications.arn
          Message = {
            "orderId.$" = "$.orderId"
            "status"    = "shipped"
            "tracking.$" = "$.shipping.trackingNumber"
          }
        }
        Next = "OrderComplete"
      }

      # Wait for approval example
      WaitForApproval = {
        Type    = "Task"
        Resource = "arn:aws:states:::lambda:invoke.waitForTaskToken"
        Parameters = {
          FunctionName = aws_lambda_function.request_approval.arn
          Payload = {
            "orderId.$"   = "$.orderId"
            "taskToken.$" = "$$.Task.Token"
          }
        }
        TimeoutSeconds = 86400  # 24 hours
        Next           = "ProcessApproval"
      }

      OrderComplete = {
        Type = "Succeed"
      }

      OrderInvalid = {
        Type  = "Fail"
        Error = "OrderValidationError"
        Cause = "Order validation failed"
      }

      OrderFailed = {
        Type  = "Fail"
        Error = "OrderProcessingError"
        Cause = "Order processing failed"
      }

      CompensateOrder = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.compensate_order.arn
          Payload = {
            "orderId.$" = "$.orderId"
            "error.$"   = "$.error"
          }
        }
        Next = "OrderFailed"
      }

      ShippingFailed = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.handle_shipping_failure.arn
          Payload = {
            "orderId.$" = "$.orderId"
            "error.$"   = "$.error"
          }
        }
        Next = "OrderFailed"
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tracing_configuration {
    enabled = true
  }

  tags = {
    Environment = "production"
  }
}

# Lambda Functions
resource "aws_lambda_function" "validate_order" {
  filename         = "validate_order.zip"
  function_name    = "${var.project_name}-validate-order"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30
}

resource "aws_lambda_function" "reserve_inventory" {
  filename         = "reserve_inventory.zip"
  function_name    = "${var.project_name}-reserve-inventory"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30
}

resource "aws_lambda_function" "process_payment" {
  filename         = "process_payment.zip"
  function_name    = "${var.project_name}-process-payment"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 60
}

resource "aws_lambda_function" "ship_order" {
  filename         = "ship_order.zip"
  function_name    = "${var.project_name}-ship-order"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30
}

resource "aws_lambda_function" "compensate_order" {
  filename         = "compensate_order.zip"
  function_name    = "${var.project_name}-compensate-order"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 60
}

resource "aws_lambda_function" "handle_shipping_failure" {
  filename         = "handle_shipping_failure.zip"
  function_name    = "${var.project_name}-handle-shipping-failure"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30
}

resource "aws_lambda_function" "request_approval" {
  filename         = "request_approval.zip"
  function_name    = "${var.project_name}-request-approval"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30
}

# SNS Topic
resource "aws_sns_topic" "notifications" {
  name = "${var.project_name}-notifications"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/${var.project_name}"
  retention_in_days = 14
}

# IAM Role for Step Functions
resource "aws_iam_role" "step_functions" {
  name = "${var.project_name}-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "step_functions" {
  name = "step-functions-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.validate_order.arn,
          aws_lambda_function.reserve_inventory.arn,
          aws_lambda_function.process_payment.arn,
          aws_lambda_function.ship_order.arn,
          aws_lambda_function.compensate_order.arn,
          aws_lambda_function.handle_shipping_failure.arn,
          aws_lambda_function.request_approval.arn
        ]
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
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      }
    ]
  })
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

resource "aws_iam_role_policy" "lambda_step_functions" {
  name = "step-functions-callback"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "states:SendTaskSuccess",
        "states:SendTaskFailure"
      ]
      Resource = "*"
    }]
  })
}

# API Gateway to trigger workflow
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_function" "api_handler" {
  filename         = "api_handler.zip"
  function_name    = "${var.project_name}-api-handler"
  role             = aws_iam_role.api_handler.arn
  handler          = "index.handler"
  runtime          = "nodejs20.x"
  timeout          = 30

  environment {
    variables = {
      STATE_MACHINE_ARN = aws_sfn_state_machine.order_processing.arn
    }
  }
}

resource "aws_iam_role" "api_handler" {
  name = "${var.project_name}-api-handler-role"

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

resource "aws_iam_role_policy" "api_handler" {
  name = "step-functions-start"
  role = aws_iam_role.api_handler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "states:StartExecution",
        "states:DescribeExecution"
      ]
      Resource = aws_sfn_state_machine.order_processing.arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_handler_basic" {
  role       = aws_iam_role.api_handler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.order_processing.arn
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.main.api_endpoint
}
```

## Implementation

### API Handler (Start Workflow)
```javascript
// api_handler/index.js
const { SFNClient, StartExecutionCommand, DescribeExecutionCommand } = require('@aws-sdk/client-sfn');

const sfn = new SFNClient({});
const STATE_MACHINE_ARN = process.env.STATE_MACHINE_ARN;

exports.handler = async (event) => {
  const method = event.requestContext.http.method;
  const path = event.rawPath;

  if (method === 'POST' && path === '/orders') {
    return startOrderWorkflow(event);
  }

  if (method === 'GET' && path.startsWith('/orders/')) {
    const executionArn = decodeURIComponent(path.split('/')[2]);
    return getOrderStatus(executionArn);
  }

  return {
    statusCode: 404,
    body: JSON.stringify({ error: 'Not found' })
  };
};

async function startOrderWorkflow(event) {
  const body = JSON.parse(event.body);

  const orderId = `order_${Date.now()}`;

  const command = new StartExecutionCommand({
    stateMachineArn: STATE_MACHINE_ARN,
    name: orderId,
    input: JSON.stringify({
      orderId,
      items: body.items,
      total: body.total,
      paymentMethod: body.paymentMethod,
      shippingAddress: body.shippingAddress
    })
  });

  const result = await sfn.send(command);

  return {
    statusCode: 202,
    body: JSON.stringify({
      orderId,
      executionArn: result.executionArn,
      status: 'PROCESSING'
    })
  };
}

async function getOrderStatus(executionArn) {
  const command = new DescribeExecutionCommand({
    executionArn
  });

  const result = await sfn.send(command);

  return {
    statusCode: 200,
    body: JSON.stringify({
      status: result.status,
      startDate: result.startDate,
      stopDate: result.stopDate,
      output: result.output ? JSON.parse(result.output) : null
    })
  };
}
```

### Validate Order Lambda
```javascript
// validate_order/index.js
exports.handler = async (event) => {
  const { orderId, items } = event;

  console.log(`Validating order ${orderId}`);

  // Validate items
  if (!items || items.length === 0) {
    return {
      isValid: false,
      reason: 'No items in order'
    };
  }

  // Check inventory availability (mock)
  for (const item of items) {
    if (item.quantity > 100) {
      return {
        isValid: false,
        reason: `Item ${item.productId} exceeds maximum quantity`
      };
    }
  }

  return {
    isValid: true,
    validatedAt: new Date().toISOString()
  };
};
```

### Human Approval Pattern
```javascript
// request_approval/index.js
const { SFNClient, SendTaskSuccessCommand, SendTaskFailureCommand } = require('@aws-sdk/client-sfn');
const { SNSClient, PublishCommand } = require('@aws-sdk/client-sns');

const sfn = new SFNClient({});
const sns = new SNSClient({});

exports.handler = async (event) => {
  const { orderId, taskToken } = event;

  // Store task token for later callback
  // In production, store in DynamoDB
  console.log(`Approval requested for order ${orderId}`);
  console.log(`Task token: ${taskToken}`);

  // Send notification with approval link
  await sns.send(new PublishCommand({
    TopicArn: process.env.APPROVAL_TOPIC_ARN,
    Subject: `Approval Required: Order ${orderId}`,
    Message: JSON.stringify({
      orderId,
      approvalUrl: `https://api.example.com/approve?token=${encodeURIComponent(taskToken)}&action=approve`,
      rejectUrl: `https://api.example.com/approve?token=${encodeURIComponent(taskToken)}&action=reject`
    })
  }));

  // Don't return - workflow waits for callback
};

// Separate handler for approval callback
exports.approvalCallback = async (event) => {
  const { token, action } = event.queryStringParameters;

  if (action === 'approve') {
    await sfn.send(new SendTaskSuccessCommand({
      taskToken: token,
      output: JSON.stringify({ approved: true, approvedAt: new Date().toISOString() })
    }));
  } else {
    await sfn.send(new SendTaskFailureCommand({
      taskToken: token,
      error: 'ApprovalRejected',
      cause: 'Order was rejected by approver'
    }));
  }

  return {
    statusCode: 200,
    body: `Order ${action}d successfully`
  };
};
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Package Lambda functions
for f in validate_order reserve_inventory process_payment ship_order compensate_order; do
  cd $f && zip -r ../$f.zip . && cd ..
done

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789:stateMachine:order-workflow \
  --input '{"orderId": "123", "items": [{"productId": "ABC", "quantity": 2}], "total": 99.99}'

# View execution history
aws stepfunctions get-execution-history \
  --execution-arn arn:aws:states:us-east-1:123456789:execution:order-workflow:order_123

# List executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:123456789:stateMachine:order-workflow \
  --status-filter RUNNING
```

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| State transitions | 4,000/month | $0.025/1,000 |
| Express workflows | - | $1.00/million requests |
| Lambda | 1M requests | $0.20/million |

### Example Costs
| Scale | Executions/mo | Transitions | Total |
|-------|---------------|-------------|-------|
| Small | 10k | 100k | ~$3 |
| Medium | 100k | 1M | ~$30 |
| Large | 1M | 10M | ~$300 |

## Best Practices

1. **Use Standard for long-running, Express for high-volume**
2. **Implement proper error handling with Catch/Retry**
3. **Use task tokens for human approval workflows**
4. **Enable X-Ray tracing for debugging**
5. **Log execution data for troubleshooting**

## Common Mistakes

1. **No error handling**: Workflow fails silently
2. **Missing compensation**: No rollback on failure
3. **Large payloads**: Exceeds 256KB limit
4. **No timeouts**: Workflows run forever
5. **Wrong workflow type**: Standard vs Express

## Sources

- [Step Functions Documentation](https://docs.aws.amazon.com/step-functions/latest/dg/)
- [Amazon States Language](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-amazon-states-language.html)
- [Step Functions Best Practices](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)
