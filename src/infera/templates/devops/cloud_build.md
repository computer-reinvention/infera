# Google Cloud Build Patterns

## Overview

Cloud Build is GCP's native CI/CD service that builds containers, runs tests, and deploys to Google Cloud services. It integrates deeply with GCP services and supports Terraform, Cloud Run, GKE, and Cloud Functions deployments.

### When to Use
- GCP-native infrastructure
- Tight integration with Cloud Run, GKE, Cloud Functions
- Need for private networking during builds
- Projects using Google Cloud Source Repositories
- Regulatory requirements for builds in specific regions

### When NOT to Use
- Multi-cloud deployments (prefer GitHub Actions)
- GitHub-native workflows
- Need for macOS or Windows builds
- Complex matrix testing requirements

## Build Configuration

```yaml
# cloudbuild.yaml
steps:
  - id: 'build'
    name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA', '.']

  - id: 'push'
    name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA']

  - id: 'deploy'
    name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'my-app'
      - '--image=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: 'E2_HIGHCPU_8'

timeout: '1200s'

substitutions:
  _REGION: 'us-central1'
```

## Common Patterns

### Pattern 1: Node.js Build and Test

```yaml
# cloudbuild.yaml
steps:
  # Install dependencies
  - id: 'install'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['ci']

  # Run linting
  - id: 'lint'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['run', 'lint']
    waitFor: ['install']

  # Run tests
  - id: 'test'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['run', 'test', '--', '--coverage']
    waitFor: ['install']
    env:
      - 'CI=true'

  # Build application
  - id: 'build'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['run', 'build']
    waitFor: ['lint', 'test']

  # Build Docker image
  - id: 'docker-build'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/my-app:latest'
      - '.'
    waitFor: ['build']

  # Push to Container Registry
  - id: 'docker-push'
    name: 'gcr.io/cloud-builders/docker'
    args: ['push', '--all-tags', 'gcr.io/$PROJECT_ID/my-app']
    waitFor: ['docker-build']

options:
  machineType: 'E2_HIGHCPU_8'

# Artifacts for caching
artifacts:
  objects:
    location: 'gs://${PROJECT_ID}-build-artifacts/'
    paths:
      - 'coverage/**'
```

### Pattern 2: Multi-Stage Docker Build

```yaml
# cloudbuild.yaml
steps:
  # Build with Kaniko for caching
  - id: 'build-with-cache'
    name: 'gcr.io/kaniko-project/executor:latest'
    args:
      - '--dockerfile=Dockerfile'
      - '--destination=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '--destination=gcr.io/$PROJECT_ID/my-app:$BRANCH_NAME'
      - '--cache=true'
      - '--cache-repo=gcr.io/$PROJECT_ID/my-app/cache'
      - '--cache-ttl=168h'  # 1 week

  # Run container tests
  - id: 'test-container'
    name: 'gcr.io/gcp-runtimes/container-structure-test:latest'
    args:
      - 'test'
      - '--image=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '--config=container-structure-test.yaml'
    waitFor: ['build-with-cache']

  # Scan for vulnerabilities
  - id: 'scan'
    name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        gcloud artifacts docker images scan gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA \
          --format='value(response.scan)' > /workspace/scan_id.txt
        gcloud artifacts docker images list-vulnerabilities \
          $(cat /workspace/scan_id.txt) \
          --format='table(vulnerability.effectiveSeverity,vulnerability.cvssScore,vulnerability.packageIssue[0].affectedPackage,vulnerability.packageIssue[0].affectedVersion.name)'
    waitFor: ['build-with-cache']

images:
  - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
  - 'gcr.io/$PROJECT_ID/my-app:$BRANCH_NAME'
```

### Pattern 3: Deploy to Cloud Run

```yaml
# cloudbuild.yaml
steps:
  # Build
  - id: 'build'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/${_SERVICE}:$COMMIT_SHA'
      - '.'

  # Push to Artifact Registry
  - id: 'push'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/${_SERVICE}:$COMMIT_SHA'

  # Deploy to Cloud Run
  - id: 'deploy'
    name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'deploy'
      - '${_SERVICE}'
      - '--image=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPOSITORY}/${_SERVICE}:$COMMIT_SHA'
      - '--region=${_REGION}'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--memory=512Mi'
      - '--cpu=1'
      - '--min-instances=0'
      - '--max-instances=10'
      - '--set-env-vars=COMMIT_SHA=$COMMIT_SHA'

  # Verify deployment
  - id: 'verify'
    name: 'gcr.io/cloud-builders/curl'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        URL=$(gcloud run services describe ${_SERVICE} --region=${_REGION} --format='value(status.url)')
        curl -f "$URL/health" || exit 1
        echo "Deployment verified at $URL"
    waitFor: ['deploy']

substitutions:
  _REGION: 'us-central1'
  _REPOSITORY: 'my-repo'
  _SERVICE: 'my-service'

options:
  logging: CLOUD_LOGGING_ONLY
```

### Pattern 4: Deploy to GKE

```yaml
# cloudbuild.yaml
steps:
  # Build image
  - id: 'build'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '.'

  # Push image
  - id: 'push'
    name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA']

  # Get GKE credentials
  - id: 'get-credentials'
    name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - 'run'
      - '--filename=k8s/'
      - '--location=${_ZONE}'
      - '--cluster=${_CLUSTER}'
      - '--image=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'

  # Or use kubectl directly
  - id: 'deploy-kubectl'
    name: 'gcr.io/cloud-builders/kubectl'
    args:
      - 'set'
      - 'image'
      - 'deployment/my-app'
      - 'my-app=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
    env:
      - 'CLOUDSDK_COMPUTE_ZONE=${_ZONE}'
      - 'CLOUDSDK_CONTAINER_CLUSTER=${_CLUSTER}'

  # Wait for rollout
  - id: 'verify-rollout'
    name: 'gcr.io/cloud-builders/kubectl'
    args:
      - 'rollout'
      - 'status'
      - 'deployment/my-app'
      - '--timeout=300s'
    env:
      - 'CLOUDSDK_COMPUTE_ZONE=${_ZONE}'
      - 'CLOUDSDK_CONTAINER_CLUSTER=${_CLUSTER}'

substitutions:
  _ZONE: 'us-central1-a'
  _CLUSTER: 'production'
```

### Pattern 5: Terraform Infrastructure

```yaml
# cloudbuild.yaml
steps:
  # Initialize Terraform
  - id: 'tf-init'
    name: 'hashicorp/terraform:1.6'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        cd terraform
        terraform init \
          -backend-config="bucket=${PROJECT_ID}-tfstate" \
          -backend-config="prefix=terraform/state"

  # Validate
  - id: 'tf-validate'
    name: 'hashicorp/terraform:1.6'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        cd terraform
        terraform validate
    waitFor: ['tf-init']

  # Plan
  - id: 'tf-plan'
    name: 'hashicorp/terraform:1.6'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        cd terraform
        terraform plan -out=tfplan -var="project_id=$PROJECT_ID"
    waitFor: ['tf-validate']

  # Apply (only on main branch)
  - id: 'tf-apply'
    name: 'hashicorp/terraform:1.6'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        if [ "$BRANCH_NAME" = "main" ]; then
          cd terraform
          terraform apply -auto-approve tfplan
        else
          echo "Skipping apply on non-main branch"
        fi
    waitFor: ['tf-plan']

timeout: '1800s'

options:
  logging: CLOUD_LOGGING_ONLY
```

### Pattern 6: Cloud Functions Deployment

```yaml
# cloudbuild.yaml
steps:
  # Install dependencies
  - id: 'install'
    name: 'python:3.11'
    entrypoint: 'pip'
    args: ['install', '-r', 'requirements.txt', '-t', '.']

  # Run tests
  - id: 'test'
    name: 'python:3.11'
    entrypoint: 'python'
    args: ['-m', 'pytest', 'tests/', '-v']
    waitFor: ['install']

  # Deploy function
  - id: 'deploy'
    name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'functions'
      - 'deploy'
      - '${_FUNCTION_NAME}'
      - '--gen2'
      - '--region=${_REGION}'
      - '--runtime=python311'
      - '--source=.'
      - '--entry-point=main'
      - '--trigger-http'
      - '--allow-unauthenticated'
      - '--memory=256Mi'
      - '--timeout=60s'
    waitFor: ['test']

substitutions:
  _REGION: 'us-central1'
  _FUNCTION_NAME: 'my-function'
```

### Pattern 7: Multi-Environment Deployment

```yaml
# cloudbuild.yaml
steps:
  # Build
  - id: 'build'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '.'

  # Push
  - id: 'push'
    name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA']

  # Deploy to staging
  - id: 'deploy-staging'
    name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'my-app-staging'
      - '--image=gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - '--region=${_REGION}'
      - '--platform=managed'
      - '--project=${_STAGING_PROJECT}'
    waitFor: ['push']

  # Run integration tests
  - id: 'integration-test'
    name: 'node:20'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        npm ci
        STAGING_URL=$(gcloud run services describe my-app-staging \
          --region=${_REGION} \
          --project=${_STAGING_PROJECT} \
          --format='value(status.url)')
        API_URL=$STAGING_URL npm run test:integration
    waitFor: ['deploy-staging']

  # Deploy to production (manual approval via separate trigger)
  - id: 'tag-for-production'
    name: 'gcr.io/cloud-builders/docker'
    args:
      - 'tag'
      - 'gcr.io/$PROJECT_ID/my-app:$COMMIT_SHA'
      - 'gcr.io/$PROJECT_ID/my-app:production-ready'
    waitFor: ['integration-test']

substitutions:
  _REGION: 'us-central1'
  _STAGING_PROJECT: 'my-project-staging'

# cloudbuild-production.yaml (separate file for production)
# Triggered manually or by approval workflow
steps:
  - id: 'deploy-production'
    name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'my-app'
      - '--image=gcr.io/$PROJECT_ID/my-app:production-ready'
      - '--region=${_REGION}'
      - '--platform=managed'
      - '--project=${_PROD_PROJECT}'
```

## Triggers Configuration

```hcl
# Terraform for Cloud Build triggers
resource "google_cloudbuild_trigger" "push_to_main" {
  name        = "push-to-main"
  description = "Build and deploy on push to main"

  github {
    owner = "my-org"
    name  = "my-repo"
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  substitutions = {
    _REGION     = "us-central1"
    _SERVICE    = "my-service"
    _REPOSITORY = "my-repo"
  }

  service_account = google_service_account.cloudbuild.id
}

resource "google_cloudbuild_trigger" "pull_request" {
  name        = "pull-request"
  description = "Run tests on pull request"

  github {
    owner = "my-org"
    name  = "my-repo"
    pull_request {
      branch = "^main$"
    }
  }

  filename = "cloudbuild-pr.yaml"

  service_account = google_service_account.cloudbuild.id
}

# Manual trigger for production
resource "google_cloudbuild_trigger" "production_deploy" {
  name        = "production-deploy"
  description = "Deploy to production (manual)"

  github {
    owner = "my-org"
    name  = "my-repo"
    push {
      tag = "^v.*"  # Triggered by version tags
    }
  }

  filename = "cloudbuild-production.yaml"

  approval_config {
    approval_required = true
  }

  service_account = google_service_account.cloudbuild.id
}

# Service account for Cloud Build
resource "google_service_account" "cloudbuild" {
  account_id   = "cloudbuild-sa"
  display_name = "Cloud Build Service Account"
}

resource "google_project_iam_member" "cloudbuild_run" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}
```

## Private Pool for VPC Access

```yaml
# cloudbuild.yaml with private pool
steps:
  - id: 'access-private-db'
    name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        # Can access private VPC resources
        psql "host=10.0.0.5 dbname=mydb user=myuser" -c "SELECT 1"

options:
  pool:
    name: 'projects/$PROJECT_ID/locations/us-central1/workerPools/my-private-pool'
```

```hcl
# Terraform for private pool
resource "google_cloudbuild_worker_pool" "private" {
  name     = "my-private-pool"
  location = "us-central1"

  worker_config {
    disk_size_gb   = 100
    machine_type   = "e2-standard-4"
    no_external_ip = false
  }

  network_config {
    peered_network = google_compute_network.vpc.id
  }
}
```

## Caching and Optimization

```yaml
# cloudbuild.yaml with caching
steps:
  # Restore cache
  - id: 'restore-cache'
    name: 'gcr.io/cloud-builders/gsutil'
    args:
      - '-m'
      - 'cp'
      - '-r'
      - 'gs://${PROJECT_ID}-build-cache/node_modules'
      - '.'
    allowFailure: true

  # Install dependencies
  - id: 'install'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['ci']
    waitFor: ['restore-cache']

  # Build
  - id: 'build'
    name: 'node:20'
    entrypoint: 'npm'
    args: ['run', 'build']
    waitFor: ['install']

  # Save cache
  - id: 'save-cache'
    name: 'gcr.io/cloud-builders/gsutil'
    args:
      - '-m'
      - 'cp'
      - '-r'
      - 'node_modules'
      - 'gs://${PROJECT_ID}-build-cache/'
    waitFor: ['build']

options:
  machineType: 'E2_HIGHCPU_8'
```

## Example Configuration

```yaml
# infera.yaml - Cloud Build configuration
name: my-app
provider: gcp

ci:
  provider: cloud_build

  triggers:
    - name: push-to-main
      event: push
      branch: main
      config: cloudbuild.yaml

    - name: pull-request
      event: pull_request
      branch: main
      config: cloudbuild-pr.yaml

    - name: production
      event: tag
      pattern: "^v.*"
      approval_required: true

  options:
    machine_type: E2_HIGHCPU_8
    logging: CLOUD_LOGGING_ONLY

  private_pool:
    enabled: false  # Enable for VPC access
```

## Sources

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Cloud Build Quickstart](https://cloud.google.com/build/docs/quickstart-build)
- [Cloud Build Triggers](https://cloud.google.com/build/docs/automating-builds/create-manage-triggers)
- [Private Pools](https://cloud.google.com/build/docs/private-pools/private-pools-overview)
- [Cloud Build Pricing](https://cloud.google.com/build/pricing)
