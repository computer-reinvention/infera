# GitLab CI/CD Patterns

## Overview

GitLab CI/CD provides integrated DevOps pipelines with powerful features including Auto DevOps, built-in container registry, and comprehensive security scanning. This guide covers battle-tested patterns for building and deploying applications.

### When to Use
- Organizations using GitLab for source control
- Need for built-in security scanning (SAST, DAST, dependency scanning)
- Complex multi-project pipelines
- Self-hosted or air-gapped environments
- Compliance requirements (SOC2, HIPAA)
- Need for comprehensive DevSecOps features

### When NOT to Use
- Small teams not already on GitLab
- Budget constraints (advanced features require paid tiers)
- Simple projects that don't need advanced features

## Pipeline Structure

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - security
  - deploy

# Global defaults
default:
  image: node:20-alpine
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - node_modules/
      - .npm/

# Variables
variables:
  DOCKER_HOST: tcp://docker:2376
  DOCKER_TLS_CERTDIR: "/certs"
  DOCKER_TLS_VERIFY: 1
  DOCKER_CERT_PATH: "$DOCKER_TLS_CERTDIR/client"

# Include templates
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
```

## Common Patterns

### Pattern 1: Node.js CI Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - install
  - lint
  - test
  - build
  - deploy

variables:
  npm_config_cache: "$CI_PROJECT_DIR/.npm"

# Cache configuration
.node_cache: &node_cache
  cache:
    key:
      files:
        - package-lock.json
    paths:
      - node_modules/
      - .npm/
    policy: pull

install:
  stage: install
  <<: *node_cache
  cache:
    policy: pull-push  # Update cache
  script:
    - npm ci --cache .npm --prefer-offline
  artifacts:
    paths:
      - node_modules/
    expire_in: 1 hour

lint:
  stage: lint
  <<: *node_cache
  needs: [install]
  script:
    - npm run lint
    - npm run format:check

test:
  stage: test
  <<: *node_cache
  needs: [install]
  script:
    - npm run test -- --coverage
  coverage: '/All files[^|]*\|[^|]*\s+([\d\.]+)/'
  artifacts:
    when: always
    reports:
      junit: junit.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml
    paths:
      - coverage/

build:
  stage: build
  <<: *node_cache
  needs: [lint, test]
  script:
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 week
  only:
    - main
    - tags
```

### Pattern 2: Docker Build with Kaniko

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

variables:
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  IMAGE_LATEST: $CI_REGISTRY_IMAGE:latest

build:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.19.0-debug
    entrypoint: [""]
  script:
    - /kaniko/executor
      --context "${CI_PROJECT_DIR}"
      --dockerfile "${CI_PROJECT_DIR}/Dockerfile"
      --destination "${IMAGE_TAG}"
      --destination "${IMAGE_LATEST}"
      --cache=true
      --cache-repo="${CI_REGISTRY_IMAGE}/cache"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG

# Alternative: Docker-in-Docker
build_dind:
  stage: build
  image: docker:24.0.7
  services:
    - docker:24.0.7-dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $IMAGE_TAG .
    - docker push $IMAGE_TAG
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Pattern 3: Deploy to GCP Cloud Run

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

variables:
  GCP_PROJECT: my-project
  GCP_REGION: us-central1
  SERVICE_NAME: my-service

.gcp_auth: &gcp_auth
  before_script:
    - echo "$GCP_SA_KEY" | base64 -d > /tmp/key.json
    - gcloud auth activate-service-account --key-file=/tmp/key.json
    - gcloud config set project $GCP_PROJECT

build:
  stage: build
  image: gcr.io/cloud-builders/docker
  <<: *gcp_auth
  script:
    - gcloud auth configure-docker gcr.io
    - docker build -t gcr.io/$GCP_PROJECT/$SERVICE_NAME:$CI_COMMIT_SHA .
    - docker push gcr.io/$GCP_PROJECT/$SERVICE_NAME:$CI_COMMIT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy_staging:
  stage: deploy
  image: google/cloud-sdk:latest
  <<: *gcp_auth
  script:
    - gcloud run deploy $SERVICE_NAME-staging
      --image gcr.io/$GCP_PROJECT/$SERVICE_NAME:$CI_COMMIT_SHA
      --region $GCP_REGION
      --platform managed
      --allow-unauthenticated
  environment:
    name: staging
    url: https://$SERVICE_NAME-staging-$GCP_PROJECT.run.app
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy_production:
  stage: deploy
  image: google/cloud-sdk:latest
  <<: *gcp_auth
  script:
    - gcloud run deploy $SERVICE_NAME
      --image gcr.io/$GCP_PROJECT/$SERVICE_NAME:$CI_COMMIT_SHA
      --region $GCP_REGION
      --platform managed
      --allow-unauthenticated
  environment:
    name: production
    url: https://$SERVICE_NAME-$GCP_PROJECT.run.app
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual
  needs: [deploy_staging]
```

### Pattern 4: Deploy to AWS ECS

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

variables:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: my-app
  ECS_CLUSTER: production
  ECS_SERVICE: my-app-service

.aws_auth: &aws_auth
  before_script:
    - apt-get update && apt-get install -y awscli jq
    - aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
    - aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY
    - aws configure set region $AWS_REGION

build:
  stage: build
  image: docker:24.0.7
  services:
    - docker:24.0.7-dind
  <<: *aws_auth
  script:
    - aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    - docker build -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$CI_COMMIT_SHA .
    - docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$CI_COMMIT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy:
  stage: deploy
  image: amazon/aws-cli:latest
  <<: *aws_auth
  script:
    # Get current task definition
    - TASK_DEF=$(aws ecs describe-task-definition --task-definition $ECS_SERVICE --query 'taskDefinition' --output json)

    # Update image in task definition
    - NEW_TASK_DEF=$(echo $TASK_DEF | jq --arg IMAGE "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$CI_COMMIT_SHA" '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')

    # Register new task definition
    - NEW_TASK_ARN=$(aws ecs register-task-definition --cli-input-json "$NEW_TASK_DEF" --query 'taskDefinition.taskDefinitionArn' --output text)

    # Update service
    - aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE --task-definition $NEW_TASK_ARN

    # Wait for deployment
    - aws ecs wait services-stable --cluster $ECS_CLUSTER --services $ECS_SERVICE
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Pattern 5: Deploy to Kubernetes

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

variables:
  KUBE_NAMESPACE: production

.kube_context: &kube_context
  before_script:
    - kubectl config set-cluster k8s --server="$KUBE_URL" --certificate-authority="$KUBE_CA_PEM_FILE"
    - kubectl config set-credentials gitlab --token="$KUBE_TOKEN"
    - kubectl config set-context default --cluster=k8s --user=gitlab --namespace=$KUBE_NAMESPACE
    - kubectl config use-context default

build:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.19.0-debug
    entrypoint: [""]
  script:
    - /kaniko/executor
      --context "${CI_PROJECT_DIR}"
      --dockerfile "${CI_PROJECT_DIR}/Dockerfile"
      --destination "${CI_REGISTRY_IMAGE}:${CI_COMMIT_SHA}"
      --destination "${CI_REGISTRY_IMAGE}:latest"
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  <<: *kube_context
  script:
    # Update image in deployment
    - kubectl set image deployment/my-app my-app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

    # Wait for rollout
    - kubectl rollout status deployment/my-app --timeout=300s
  environment:
    name: production
    kubernetes:
      namespace: $KUBE_NAMESPACE
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Pattern 6: Terraform with GitLab

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - plan
  - apply

variables:
  TF_ROOT: terraform
  TF_STATE_NAME: default

.terraform_base:
  image: hashicorp/terraform:1.6
  before_script:
    - cd ${TF_ROOT}
    - terraform init
      -backend-config="address=${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/terraform/state/${TF_STATE_NAME}"
      -backend-config="lock_address=${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/terraform/state/${TF_STATE_NAME}/lock"
      -backend-config="unlock_address=${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/terraform/state/${TF_STATE_NAME}/lock"
      -backend-config="username=gitlab-ci-token"
      -backend-config="password=${CI_JOB_TOKEN}"
      -backend-config="lock_method=POST"
      -backend-config="unlock_method=DELETE"
      -backend-config="retry_wait_min=5"

validate:
  extends: .terraform_base
  stage: validate
  script:
    - terraform validate
    - terraform fmt -check

plan:
  extends: .terraform_base
  stage: plan
  script:
    - terraform plan -out=plan.tfplan
  artifacts:
    paths:
      - ${TF_ROOT}/plan.tfplan
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"

apply:
  extends: .terraform_base
  stage: apply
  script:
    - terraform apply -auto-approve plan.tfplan
  dependencies:
    - plan
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual
  environment:
    name: production
```

### Pattern 7: Security Scanning

```yaml
# .gitlab-ci.yml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml
  - template: Security/DAST.gitlab-ci.yml
  - template: Security/License-Scanning.gitlab-ci.yml

stages:
  - build
  - test
  - security
  - deploy

# Override SAST settings
sast:
  stage: security
  variables:
    SAST_EXCLUDED_PATHS: "spec, test, tests, tmp"

# Container scanning
container_scanning:
  stage: security
  variables:
    CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  needs:
    - build

# DAST (Dynamic Application Security Testing)
dast:
  stage: security
  variables:
    DAST_WEBSITE: https://staging.example.com
  needs:
    - deploy_staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## Multi-Project Pipelines

```yaml
# Parent project: .gitlab-ci.yml
stages:
  - trigger

trigger_frontend:
  stage: trigger
  trigger:
    project: group/frontend
    branch: main
    strategy: depend  # Wait for downstream to complete
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - shared/**/*

trigger_backend:
  stage: trigger
  trigger:
    project: group/backend
    branch: main
    strategy: depend
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      changes:
        - shared/**/*
```

```yaml
# Child project: .gitlab-ci.yml
workflow:
  rules:
    # Run when triggered by parent
    - if: $CI_PIPELINE_SOURCE == "pipeline"
    # Or run normally
    - if: $CI_COMMIT_BRANCH

build:
  script:
    - echo "Building with triggered changes"
```

## Environment-Specific Deployments

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

.deploy_template:
  image: google/cloud-sdk:latest
  script:
    - gcloud run deploy $SERVICE_NAME
      --image gcr.io/$GCP_PROJECT/$SERVICE_NAME:$CI_COMMIT_SHA
      --region $GCP_REGION
      --set-env-vars="ENV=$CI_ENVIRONMENT_NAME"

deploy_development:
  extends: .deploy_template
  stage: deploy
  variables:
    GCP_PROJECT: my-project-dev
    SERVICE_NAME: api
    GCP_REGION: us-central1
  environment:
    name: development
    url: https://api-dev.example.com
    on_stop: stop_development
  rules:
    - if: $CI_COMMIT_BRANCH != "main"

stop_development:
  extends: .deploy_template
  stage: deploy
  script:
    - gcloud run services delete $SERVICE_NAME --region $GCP_REGION --quiet
  environment:
    name: development
    action: stop
  rules:
    - if: $CI_COMMIT_BRANCH != "main"
      when: manual

deploy_staging:
  extends: .deploy_template
  stage: deploy
  variables:
    GCP_PROJECT: my-project-staging
    SERVICE_NAME: api
    GCP_REGION: us-central1
  environment:
    name: staging
    url: https://api-staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

deploy_production:
  extends: .deploy_template
  stage: deploy
  variables:
    GCP_PROJECT: my-project-prod
    SERVICE_NAME: api
    GCP_REGION: us-central1
  environment:
    name: production
    url: https://api.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual
  needs:
    - deploy_staging
```

## Caching Strategies

```yaml
# Global cache configuration
cache:
  key:
    files:
      - package-lock.json
    prefix: ${CI_JOB_NAME}
  paths:
    - node_modules/
  policy: pull-push

# Job-specific cache
test:
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - .cache/
    policy: pull  # Read-only cache

# Distributed cache with S3
variables:
  S3_CACHE_BUCKET: my-gitlab-cache
  CACHE_S3_SERVER_SIDE_ENCRYPTION: AES256
```

## Artifacts and Dependencies

```yaml
build:
  script:
    - npm run build
  artifacts:
    paths:
      - dist/
    reports:
      dotenv: build.env  # Pass variables to downstream jobs
    expire_in: 1 week
    when: on_success

test:
  needs:
    - job: build
      artifacts: true
  script:
    - npm test

deploy:
  dependencies:
    - build  # Only download artifacts from build
  script:
    - deploy.sh
```

## Example Configuration

```yaml
# infera.yaml - GitLab CI configuration
name: my-app
provider: gcp

ci:
  provider: gitlab_ci

  stages:
    - build
    - test
    - security
    - deploy

  security:
    sast: true
    dependency_scanning: true
    container_scanning: true
    secret_detection: true

  environments:
    development:
      auto_deploy: true
      auto_stop: 24h

    staging:
      auto_deploy: true
      on_branch: main

    production:
      manual_approval: true
      protected: true

  caching:
    enabled: true
    type: s3
    bucket: my-gitlab-cache
```

## Sources

- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [GitLab CI/CD Examples](https://docs.gitlab.com/ee/ci/examples/)
- [GitLab Security Scanning](https://docs.gitlab.com/ee/user/application_security/)
- [GitLab Terraform Integration](https://docs.gitlab.com/ee/user/infrastructure/iac/)
- [GitLab Auto DevOps](https://docs.gitlab.com/ee/topics/autodevops/)
