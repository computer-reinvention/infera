# GitHub Actions CI/CD Patterns

## Overview

GitHub Actions provides native CI/CD integrated with GitHub repositories. This guide covers battle-tested patterns for building, testing, and deploying applications to various cloud providers.

### When to Use
- Projects hosted on GitHub
- Teams already using GitHub ecosystem
- Need for matrix testing across platforms
- Open source projects (free unlimited minutes)
- Integration with GitHub features (releases, packages, deployments)

### When NOT to Use
- Projects requiring air-gapped environments
- Complex multi-repo pipelines (consider GitLab or Jenkins)
- Need for on-premise runners with strict compliance
- Budget constraints for private repos with heavy CI usage

## Workflow Structure

```yaml
# .github/workflows/ci.yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:  # Manual trigger

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancel previous runs on same branch

env:
  NODE_VERSION: '20'
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Job definitions follow...
```

## Common Patterns

### Pattern 1: Node.js CI Pipeline

```yaml
# .github/workflows/node-ci.yaml
name: Node.js CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        node-version: [18, 20, 22]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm test -- --coverage

      - name: Upload coverage
        if: matrix.node-version == '20'
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: build
          path: dist/
          retention-days: 7
```

### Pattern 2: Docker Build & Push

```yaml
# .github/workflows/docker.yaml
name: Docker Build

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

### Pattern 3: Deploy to GCP Cloud Run

```yaml
# .github/workflows/deploy-cloudrun.yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

env:
  PROJECT_ID: my-project
  REGION: us-central1
  SERVICE: my-service
  REGISTRY: gcr.io

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # Required for Workload Identity

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'github-actions@my-project.iam.gserviceaccount.com'

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker
        run: gcloud auth configure-docker ${{ env.REGISTRY }}

      - name: Build and push image
        run: |
          docker build -t ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE }}:${{ github.sha }} .
          docker push ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE }}:${{ github.sha }}

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE }}
          region: ${{ env.REGION }}
          image: ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE }}:${{ github.sha }}
          flags: '--allow-unauthenticated'

      - name: Show URL
        run: |
          echo "Service deployed to:"
          gcloud run services describe ${{ env.SERVICE }} --region ${{ env.REGION }} --format 'value(status.url)'
```

### Pattern 4: Deploy to AWS ECS

```yaml
# .github/workflows/deploy-ecs.yaml
name: Deploy to ECS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: my-app
  ECS_SERVICE: my-app-service
  ECS_CLUSTER: production
  CONTAINER_NAME: my-app

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Download task definition
        run: |
          aws ecs describe-task-definition --task-definition ${{ env.ECS_SERVICE }} \
            --query taskDefinition > task-definition.json

      - name: Update task definition
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: ${{ env.CONTAINER_NAME }}
          image: ${{ steps.build-image.outputs.image }}

      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
```

### Pattern 5: Deploy to Cloudflare Workers

```yaml
# .github/workflows/deploy-workers.yaml
name: Deploy to Cloudflare Workers

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Deploy to Cloudflare Workers
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: deploy --env ${{ github.ref == 'refs/heads/main' && 'production' || 'preview' }}
```

### Pattern 6: Terraform Infrastructure

```yaml
# .github/workflows/terraform.yaml
name: Terraform

on:
  push:
    branches: [main]
    paths:
      - 'terraform/**'
  pull_request:
    branches: [main]
    paths:
      - 'terraform/**'

env:
  TF_VERSION: '1.6.0'
  WORKING_DIR: terraform

jobs:
  plan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write

    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'terraform@my-project.iam.gserviceaccount.com'

      - name: Terraform Init
        run: terraform init

      - name: Terraform Format Check
        run: terraform fmt -check

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        id: plan
        run: terraform plan -no-color -out=tfplan
        continue-on-error: true

      - name: Comment PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const output = `#### Terraform Plan 📖
            \`\`\`
            ${{ steps.plan.outputs.stdout }}
            \`\`\`
            `;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

      - name: Terraform Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve tfplan
```

### Pattern 7: Release with Changesets

```yaml
# .github/workflows/release.yaml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          registry-url: 'https://registry.npmjs.org'

      - name: Install dependencies
        run: npm ci

      - name: Create Release PR or Publish
        uses: changesets/action@v1
        with:
          publish: npm run release
          version: npm run version
          commit: 'chore: release'
          title: 'chore: release'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

## Security Best Practices

### Workload Identity Federation (No Secrets)

```yaml
# GCP Workload Identity setup
# First, set up in GCP:
# gcloud iam workload-identity-pools create "github" --location="global"
# gcloud iam workload-identity-pools providers create-oidc "my-repo" \
#   --location="global" \
#   --workload-identity-pool="github" \
#   --issuer-uri="https://token.actions.githubusercontent.com" \
#   --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository"

jobs:
  deploy:
    permissions:
      contents: read
      id-token: write  # Required!

    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'github-actions@PROJECT_ID.iam.gserviceaccount.com'
```

### Environment Protection Rules

```yaml
# Use environments for production deployments
jobs:
  deploy-staging:
    environment: staging
    # No approval required

  deploy-production:
    environment: production
    # Requires approval from designated reviewers
    needs: deploy-staging
```

### Secret Scanning

```yaml
# .github/workflows/security.yaml
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Caching Strategies

```yaml
# Efficient caching for faster builds
jobs:
  build:
    steps:
      # Node.js with npm
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      # Python with pip
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      # Go modules
      - uses: actions/setup-go@v5
        with:
          go-version: '1.21'
          cache: true

      # Docker layer caching
      - uses: docker/build-push-action@v5
        with:
          cache-from: type=gha
          cache-to: type=gha,mode=max

      # Custom cache
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cache/custom
            .build-cache
          key: ${{ runner.os }}-custom-${{ hashFiles('**/lockfile') }}
          restore-keys: |
            ${{ runner.os }}-custom-
```

## Reusable Workflows

```yaml
# .github/workflows/reusable-deploy.yaml
name: Reusable Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      service:
        required: true
        type: string
    secrets:
      GCP_CREDENTIALS:
        required: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4
      # Deploy steps...
```

```yaml
# .github/workflows/deploy.yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    uses: ./.github/workflows/reusable-deploy.yaml
    with:
      environment: staging
      service: my-service
    secrets:
      GCP_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS_STAGING }}

  deploy-production:
    needs: deploy-staging
    uses: ./.github/workflows/reusable-deploy.yaml
    with:
      environment: production
      service: my-service
    secrets:
      GCP_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS_PRODUCTION }}
```

## Cost Optimization

```yaml
# Use self-hosted runners for cost savings
jobs:
  build:
    runs-on: [self-hosted, linux, x64]
    # Or use larger runners for faster builds
    # runs-on: ubuntu-latest-4-cores

  # Cancel redundant runs
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

  # Skip CI for documentation
on:
  push:
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

## Example Configuration

```yaml
# infera.yaml - GitHub Actions configuration
name: my-app
provider: gcp

ci:
  provider: github_actions

  workflows:
    - name: ci
      triggers:
        - push:main
        - pull_request:main
      jobs:
        - lint
        - test
        - build

    - name: deploy
      triggers:
        - push:main
      jobs:
        - deploy:staging
        - deploy:production
      environment_protection: true

  caching:
    enabled: true
    strategy: npm

  security:
    trivy: true
    gitleaks: true
    codeql: true
```

## Sources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions Marketplace](https://github.com/marketplace?type=actions)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
