# AWS Amplify Full-Stack

## Overview

Deploy full-stack web applications using AWS Amplify with AppSync for GraphQL, DynamoDB for data, Cognito for authentication, and automatic CI/CD. Ideal for rapid development with minimal infrastructure management.

## Detection Signals

Use this template when:
- Rapid full-stack development needed
- GraphQL API preferred
- Built-in authentication required
- Git-based CI/CD wanted
- Real-time subscriptions needed
- Minimal infrastructure management

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                        AWS Amplify                               │
                    │                                                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
    Internet ──────►│   │              Amplify Hosting                             │   │
                    │   │         (Global CDN + Auto HTTPS)                        │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │              Frontend (React/Next/Vue)             │  │   │
                    │   │  │           Built & deployed automatically           │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                             │                                   │
                    │                             ▼                                   │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    AWS AppSync                           │   │
                    │   │                  (GraphQL API)                           │   │
                    │   │                                                         │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │  Queries │ Mutations │ Subscriptions (Real-time)  │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └────────────────────────┬────────────────────────────────┘   │
                    │                            │                                    │
                    │              ┌─────────────┼─────────────┐                     │
                    │              │             │             │                     │
                    │              ▼             ▼             ▼                     │
                    │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
                    │   │   Cognito    │ │   DynamoDB   │ │   Lambda     │          │
                    │   │  (Auth)      │ │   (Data)     │ │  (Custom)    │          │
                    │   └──────────────┘ └──────────────┘ └──────────────┘          │
                    │                                                                 │
                    │   ┌──────────────┐ ┌──────────────┐                            │
                    │   │     S3       │ │  CloudWatch  │                            │
                    │   │  (Storage)   │ │   (Logs)     │                            │
                    │   └──────────────┘ └──────────────┘                            │
                    │                                                                 │
                    │   Git push → Auto build → Auto deploy • Real-time GraphQL      │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Amplify App | Hosting + CI/CD | Git connected |
| AppSync | GraphQL API | Schema + resolvers |
| DynamoDB | Data storage | Tables |
| Cognito | Authentication | User pool |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| S3 | File uploads | Storage bucket |
| Lambda | Custom logic | Functions |
| CloudWatch | Monitoring | Logs, alarms |
| Pinpoint | Analytics | Events |

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
  default = "amplify-app"
}

variable "github_repo" {
  description = "GitHub repository URL"
}

variable "github_token" {
  description = "GitHub personal access token"
  sensitive   = true
}

# Amplify App
resource "aws_amplify_app" "main" {
  name       = var.project_name
  repository = var.github_repo

  access_token = var.github_token

  # Build settings
  build_spec = <<-EOT
    version: 1
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: build
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
  EOT

  # Environment variables
  environment_variables = {
    REACT_APP_API_URL       = aws_appsync_graphql_api.main.uris["GRAPHQL"]
    REACT_APP_REGION        = var.region
    REACT_APP_USER_POOL_ID  = aws_cognito_user_pool.main.id
    REACT_APP_CLIENT_ID     = aws_cognito_user_pool_client.main.id
  }

  # Auto branch creation
  enable_auto_branch_creation = true
  auto_branch_creation_patterns = [
    "feature/*",
    "dev"
  ]

  auto_branch_creation_config {
    enable_auto_build = true
  }

  # Custom rules for SPA
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }
}

# Branch
resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.main.id
  branch_name = "main"

  framework = "React"
  stage     = "PRODUCTION"

  enable_auto_build = true
}

# Domain
resource "aws_amplify_domain_association" "main" {
  app_id      = aws_amplify_app.main.id
  domain_name = "example.com"

  sub_domain {
    branch_name = aws_amplify_branch.main.branch_name
    prefix      = ""
  }

  sub_domain {
    branch_name = aws_amplify_branch.main.branch_name
    prefix      = "www"
  }
}

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your verification code"
    email_message        = "Your verification code is {####}"
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
  }

  schema {
    name                = "name"
    attribute_data_type = "String"
    mutable             = true
    required            = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "${var.project_name}-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret     = false
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  supported_identity_providers = ["COGNITO"]

  callback_urls = [
    "http://localhost:3000/",
    "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.main.default_domain}/"
  ]

  logout_urls = [
    "http://localhost:3000/",
    "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.main.default_domain}/"
  ]
}

# AppSync GraphQL API
resource "aws_appsync_graphql_api" "main" {
  name                = "${var.project_name}-api"
  authentication_type = "AMAZON_COGNITO_USER_POOLS"

  user_pool_config {
    user_pool_id   = aws_cognito_user_pool.main.id
    default_action = "ALLOW"
    aws_region     = var.region
  }

  additional_authentication_provider {
    authentication_type = "API_KEY"
  }

  schema = <<EOF
type Todo @aws_cognito_user_pools {
  id: ID!
  title: String!
  completed: Boolean!
  owner: String!
  createdAt: AWSDateTime!
  updatedAt: AWSDateTime!
}

type Query {
  getTodo(id: ID!): Todo
  listTodos(limit: Int, nextToken: String): TodoConnection
}

type Mutation {
  createTodo(input: CreateTodoInput!): Todo
  updateTodo(input: UpdateTodoInput!): Todo
  deleteTodo(id: ID!): Todo
}

type Subscription {
  onCreateTodo: Todo @aws_subscribe(mutations: ["createTodo"])
  onUpdateTodo: Todo @aws_subscribe(mutations: ["updateTodo"])
  onDeleteTodo: Todo @aws_subscribe(mutations: ["deleteTodo"])
}

type TodoConnection {
  items: [Todo]
  nextToken: String
}

input CreateTodoInput {
  title: String!
  completed: Boolean
}

input UpdateTodoInput {
  id: ID!
  title: String
  completed: Boolean
}
EOF

  log_config {
    cloudwatch_logs_role_arn = aws_iam_role.appsync_logs.arn
    field_log_level          = "ERROR"
  }
}

# API Key for public access
resource "aws_appsync_api_key" "main" {
  api_id  = aws_appsync_graphql_api.main.id
  expires = timeadd(timestamp(), "8760h") # 1 year
}

# DynamoDB Table
resource "aws_dynamodb_table" "todos" {
  name         = "${var.project_name}-todos"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "owner"
    type = "S"
  }

  global_secondary_index {
    name            = "byOwner"
    hash_key        = "owner"
    projection_type = "ALL"
  }
}

# AppSync Data Source
resource "aws_appsync_datasource" "todos" {
  api_id           = aws_appsync_graphql_api.main.id
  name             = "TodosTable"
  type             = "AMAZON_DYNAMODB"
  service_role_arn = aws_iam_role.appsync.arn

  dynamodb_config {
    table_name = aws_dynamodb_table.todos.name
  }
}

# AppSync Resolvers
resource "aws_appsync_resolver" "get_todo" {
  api_id      = aws_appsync_graphql_api.main.id
  type        = "Query"
  field       = "getTodo"
  data_source = aws_appsync_datasource.todos.name

  request_template = <<EOF
{
  "version": "2017-02-28",
  "operation": "GetItem",
  "key": {
    "id": $util.dynamodb.toDynamoDBJson($ctx.args.id)
  }
}
EOF

  response_template = "$util.toJson($ctx.result)"
}

resource "aws_appsync_resolver" "list_todos" {
  api_id      = aws_appsync_graphql_api.main.id
  type        = "Query"
  field       = "listTodos"
  data_source = aws_appsync_datasource.todos.name

  request_template = <<EOF
{
  "version": "2017-02-28",
  "operation": "Query",
  "index": "byOwner",
  "query": {
    "expression": "#owner = :owner",
    "expressionNames": {
      "#owner": "owner"
    },
    "expressionValues": {
      ":owner": $util.dynamodb.toDynamoDBJson($ctx.identity.username)
    }
  },
  "limit": $util.defaultIfNull($ctx.args.limit, 20),
  "nextToken": $util.toJson($util.defaultIfNullOrEmpty($ctx.args.nextToken, null))
}
EOF

  response_template = <<EOF
{
  "items": $util.toJson($ctx.result.items),
  "nextToken": $util.toJson($ctx.result.nextToken)
}
EOF
}

resource "aws_appsync_resolver" "create_todo" {
  api_id      = aws_appsync_graphql_api.main.id
  type        = "Mutation"
  field       = "createTodo"
  data_source = aws_appsync_datasource.todos.name

  request_template = <<EOF
{
  "version": "2017-02-28",
  "operation": "PutItem",
  "key": {
    "id": $util.dynamodb.toDynamoDBJson($util.autoId())
  },
  "attributeValues": {
    "title": $util.dynamodb.toDynamoDBJson($ctx.args.input.title),
    "completed": $util.dynamodb.toDynamoDBJson($util.defaultIfNull($ctx.args.input.completed, false)),
    "owner": $util.dynamodb.toDynamoDBJson($ctx.identity.username),
    "createdAt": $util.dynamodb.toDynamoDBJson($util.time.nowISO8601()),
    "updatedAt": $util.dynamodb.toDynamoDBJson($util.time.nowISO8601())
  }
}
EOF

  response_template = "$util.toJson($ctx.result)"
}

# IAM Roles
resource "aws_iam_role" "appsync" {
  name = "${var.project_name}-appsync-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "appsync.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "appsync_dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.appsync.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      Resource = [
        aws_dynamodb_table.todos.arn,
        "${aws_dynamodb_table.todos.arn}/index/*"
      ]
    }]
  })
}

resource "aws_iam_role" "appsync_logs" {
  name = "${var.project_name}-appsync-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "appsync.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "appsync_logs" {
  role       = aws_iam_role.appsync_logs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppSyncPushToCloudWatchLogs"
}

# S3 for file uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-uploads-${random_id.bucket.hex}"
}

resource "random_id" "bucket" {
  byte_length = 4
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

output "amplify_url" {
  value = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.main.default_domain}"
}

output "graphql_endpoint" {
  value = aws_appsync_graphql_api.main.uris["GRAPHQL"]
}

output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "client_id" {
  value = aws_cognito_user_pool_client.main.id
}
```

## Implementation

### React App with Amplify
```javascript
// src/App.js
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import { generateClient } from 'aws-amplify/api';
import '@aws-amplify/ui-react/styles.css';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: process.env.REACT_APP_USER_POOL_ID,
      userPoolClientId: process.env.REACT_APP_CLIENT_ID,
    }
  },
  API: {
    GraphQL: {
      endpoint: process.env.REACT_APP_API_URL,
      region: process.env.REACT_APP_REGION,
      defaultAuthMode: 'userPool'
    }
  }
});

const client = generateClient();

function App() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <main>
          <h1>Hello {user.username}</h1>
          <TodoList />
          <button onClick={signOut}>Sign out</button>
        </main>
      )}
    </Authenticator>
  );
}

function TodoList() {
  const [todos, setTodos] = useState([]);

  useEffect(() => {
    fetchTodos();

    // Real-time subscription
    const subscription = client.graphql({
      query: `subscription OnCreateTodo {
        onCreateTodo { id title completed }
      }`
    }).subscribe({
      next: ({ data }) => {
        setTodos(prev => [...prev, data.onCreateTodo]);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  async function fetchTodos() {
    const result = await client.graphql({
      query: `query ListTodos {
        listTodos { items { id title completed } }
      }`
    });
    setTodos(result.data.listTodos.items);
  }

  async function createTodo(title) {
    await client.graphql({
      query: `mutation CreateTodo($input: CreateTodoInput!) {
        createTodo(input: $input) { id title completed }
      }`,
      variables: { input: { title } }
    });
  }

  return (
    <div>
      <input
        type="text"
        onKeyPress={e => e.key === 'Enter' && createTodo(e.target.value)}
      />
      <ul>
        {todos.map(todo => (
          <li key={todo.id}>{todo.title}</li>
        ))}
      </ul>
    </div>
  );
}
```

## Deployment Commands

```bash
# Deploy infrastructure
terraform init
terraform apply

# Push to deploy (automatic via Git)
git add .
git commit -m "Update app"
git push origin main

# Manual deploy
aws amplify start-job \
  --app-id dxxxxxxxxxx \
  --branch-name main \
  --job-type RELEASE

# View deployment status
aws amplify get-job \
  --app-id dxxxxxxxxxx \
  --branch-name main \
  --job-id xxxxx
```

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Amplify Hosting | 1000 build min/mo | $0.01/min |
| Amplify Hosting | 15GB/mo | $0.15/GB |
| AppSync | 250k queries/mo | $4/million |
| Cognito | 50k MAU | $0.0055/MAU |
| DynamoDB | 25GB | $0.25/GB |

### Example Costs
| Scale | Users | API Calls | Total |
|-------|-------|-----------|-------|
| Small | 1k | 100k | ~$5 |
| Medium | 10k | 1M | ~$60 |
| Large | 100k | 10M | ~$600 |

## Common Mistakes

1. **No authentication**: API exposed publicly
2. **Missing CORS**: Frontend requests fail
3. **Wrong resolver mappings**: Data not returned
4. **No indexes**: Slow queries
5. **Missing subscriptions**: No real-time updates

## Sources

- [Amplify Documentation](https://docs.amplify.aws/)
- [AppSync Developer Guide](https://docs.aws.amazon.com/appsync/latest/devguide/)
- [Cognito User Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools.html)
