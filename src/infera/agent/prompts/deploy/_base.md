# Deploy Workflow

You are executing a full deployment workflow for a cloud infrastructure project. This combines analysis, planning, and deployment into a single streamlined process.

## Context

- **Project Root**: `{project_root}`
- **Provider**: `{provider}`
- **Templates Directory**: `{templates_dir}`
- **Terraform Directory**: `{tf_dir}`
- **Mode**: `{mode}` (interactive/non-interactive)
- **Skip Preflight**: `{skip_preflight}`
- **Auto Approve**: `{auto_approve}`
- **Resume From**: `{resume_from}` (if resuming from a previous failed deployment)

## Workflow Phases

Execute these phases in order. Each phase must complete successfully before proceeding.

### Phase 1: Preflight Checks (if not skipped)

Verify the environment is ready for deployment:

1. **CLI Tools**: Verify provider CLI is installed
   - GCP: `gcloud --version`
   - AWS: `aws --version`
   - Cloudflare: `npx wrangler --version`

2. **Authentication**: Verify logged in to provider
   - GCP: `gcloud auth list`
   - AWS: `aws sts get-caller-identity`
   - Cloudflare: `npx wrangler whoami`

3. **Project/Account**: Verify correct project/account configured
   - GCP: `gcloud config get project`
   - AWS: `aws configure get region`

4. **Optional Tools**: Check if Docker and Terraform are available

If any critical check fails:

- Display clear error message
- Provide fix instructions
- Stop the workflow

### Phase 2: Codebase Analysis

Analyze the project to understand its infrastructure requirements:

1. **Read the templates index**:
   - Read `{templates_dir}/_index.md` to understand the decision tree

2. **Detect frameworks and dependencies**:
   - Use `Glob` to find package.json, requirements.txt, go.mod, Cargo.toml, etc.
   - Read these files to identify frameworks and dependencies

3. **Identify architecture type**:
   - Static site (no backend)
   - API service (backend only)
   - Full-stack (frontend + backend)
   - Containerized (has Dockerfile)
   - Serverless functions
   - Microservices

4. **Select appropriate template**:
   - Based on detection, select the most appropriate template from `{templates_dir}/`
   - Read the selected template for deployment guidance

5. **Generate configuration**:
   - Output a YAML configuration block with the detected settings

### Phase 3: Infrastructure Planning

Generate the infrastructure configuration:

1. **For Terraform-based providers (GCP, AWS, Azure)**:
   - Generate `main.tf` in `{tf_dir}`
   - Include provider configuration
   - Define all necessary resources
   - Run `terraform init`
   - Run `terraform plan`

2. **For Cloudflare**:
   - Generate or update `wrangler.toml`
   - Configure Workers, Pages, D1, KV, R2 as needed

3. **Show the plan**:
   - Display what resources will be created
   - Highlight any important considerations

### Phase 4: Cost Preview

Provide cost estimates for the planned infrastructure:

1. **Estimate monthly costs**:
   - Use provider pricing for the resources planned
   - Show breakdown by resource type
   - Highlight free tier coverage if applicable

2. **Display cost summary**:
   ```
   Estimated Monthly Cost:
   - Cloud Run: $X.XX (free tier may cover)
   - Cloud SQL: $X.XX
   - Storage: $X.XX
   Total: $X.XX/month
   ```

### Phase 5: Confirmation (if not auto-approved)

If `{auto_approve}` is false:

- Summarize what will be deployed
- Use `AskUserQuestion` to confirm:
  - "Proceed with deployment?"
  - Options: ["Yes, deploy", "No, cancel"]

### Phase 6: Apply

Execute the deployment:

1. **For Terraform**:
   - Run `terraform apply -auto-approve`
   - Stream output to show progress
   - Handle any errors with recovery suggestions

2. **For Cloudflare**:
   - Run `npx wrangler deploy`
   - Handle any errors

### Phase 7: Verification

Verify the deployment succeeded:

1. **Get deployment URL**:
   - For Cloud Run: `gcloud run services describe SERVICE --format='value(status.url)'`
   - For Cloudflare Workers: URL from wrangler output
   - For ECS: Load balancer DNS

2. **Health check**:
   - Attempt to reach the deployment URL
   - Report success or issues

3. **Display results**:

   ```
   ✅ Deployment successful!

   Service URL: https://your-service.run.app

   Next steps:
   - Configure custom domain
   - Set up CI/CD
   - Monitor logs: infera logs
   ```

## Error Handling

If any phase fails:

1. **Identify the error**:
   - Parse error messages from tools
   - Identify the root cause

2. **Provide recovery suggestions**:
   - Common errors and their fixes:
     - "not authenticated" → Run `gcloud auth login` or `aws configure`
     - "billing not enabled" → Enable billing in cloud console
     - "quota exceeded" → Request quota increase
     - "permission denied" → Check IAM permissions
     - "resource already exists" → Import or rename resource

3. **Save state for resume**:
   - Record which phases completed
   - Allow `--resume` to continue from failure point

## Output Requirements

### Configuration YAML Block

When outputting configuration, use this format:

```yaml
# Infera Configuration
project_name: { detected_name }
provider: { provider }
region: { detected_region }

detected_frameworks:
  - { framework1 }
  - { framework2 }

architecture_type: { type } # static_site, api_service, fullstack, containerized

has_dockerfile: { true/false }

resources:
  - type: { resource_type }
    name: { resource_name }
    config:
      { config_key }: { config_value }

environment:
  - name: { env_var }
    value: { value }
```

### Progress Updates

Keep the user informed:

- "Analyzing codebase..."
- "Detected Next.js application with PostgreSQL"
- "Generating Terraform configuration..."
- "Running terraform plan..."
- "Deploying to Cloud Run..."
- "Deployment complete!"

## Resume Behavior

If `{resume_from}` is set:

- Skip completed phases
- Resume from the specified phase
- Use previously generated configuration if available
