# Value Discovery Instructions

This document describes how to discover and confirm values for Terraform variables **after generating Terraform files**.

## When to Use This

Use this during `infera plan` after you have:
1. Generated `main.tf`, `variables.tf`, and `outputs.tf`
2. Identified all variables that need values (from `variables.tf`)

## Discovery Process

For each variable that needs a value:

1. **Check environment variables** - Use Bash to echo relevant env vars
2. **Search project files** - Use Grep/Read to find values in config files
3. **Confirm with user** - Always confirm discovered values before using them
4. **React dynamically** - If user says the value is wrong, help them find the right one

## IMPORTANT: Always Confirm Discovered Values

When you find a value automatically, **always ask the user to confirm it**. Use AskUserQuestion with:
- The value you found
- Where you found it (env var name, file, etc.)
- Options: "Yes, use this" / "No, let me specify"

Example:
> "I found a Google Cloud project ID from your environment: `my-project-123` (from GOOGLE_CLOUD_PROJECT). Should I use this project?"
>
> 1. Yes, use my-project-123
> 2. No, I want to use a different project

## Reacting to User Corrections

If the user says a discovered value is wrong, **help them find the correct one**:

### GCP Project ID
```bash
# List all projects the user has access to
gcloud projects list --format="table(projectId,name,projectNumber)"
```
Then show the list and ask which one to use.

### GCP Region
```bash
# List available regions
gcloud compute regions list --format="table(name,status)"
```

### AWS Region
```bash
# List available regions
aws ec2 describe-regions --query "Regions[].RegionName" --output table
```

### Azure Subscription
```bash
# List subscriptions
az account list --output table
```

## Interactive Flow Example

1. **Agent finds value**: "I found `my-old-project` in your GOOGLE_CLOUD_PROJECT env var."

2. **User says no**: "That's my old project, I want to use a different one."

3. **Agent helps**: Runs `gcloud projects list`, shows results:
   ```
   PROJECT_ID          NAME                PROJECT_NUMBER
   my-old-project      Old Project         123456789
   my-new-project      New Project         987654321
   production-app      Production          555555555
   ```

4. **Agent asks**: "Which project would you like to use?"

5. **User responds**: "my-new-project" or just "2" (for the second option)

6. **Agent confirms**: Uses `my-new-project` for the configuration

## Provider-Specific Requirements

### GCP (Google Cloud Platform)

| Field | Required | Env Vars to Check | Files to Search | Default |
|-------|----------|-------------------|-----------------|---------|
| `project_id` | **YES** | `GOOGLE_CLOUD_PROJECT`, `GCP_PROJECT`, `GCLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT` | `app.yaml`, `.firebaserc`, `terraform.tfvars`, `*.tf`, `cloudbuild.yaml` | None - must be provided |
| `region` | YES | `GOOGLE_CLOUD_REGION`, `GCP_REGION`, `CLOUDSDK_COMPUTE_REGION` | `app.yaml`, `terraform.tfvars` | `us-central1` |

**Search patterns for GCP project_id:**
- `project = "project-id"` or `project: project-id` in YAML/HCL
- `"projectId": "project-id"` in JSON files
- GCP project IDs match: lowercase letters, numbers, hyphens, 6-30 chars

### AWS (Amazon Web Services)

| Field | Required | Env Vars to Check | Files to Search | Default |
|-------|----------|-------------------|-----------------|---------|
| `region` | **YES** | `AWS_REGION`, `AWS_DEFAULT_REGION` | `terraform.tfvars`, `serverless.yml`, `samconfig.toml` | None - must be provided |
| `account_id` | Optional | `AWS_ACCOUNT_ID` | `terraform.tfvars` | Can be inferred |

### Azure

| Field | Required | Env Vars to Check | Files to Search | Default |
|-------|----------|-------------------|-----------------|---------|
| `subscription_id` | **YES** | `AZURE_SUBSCRIPTION_ID`, `ARM_SUBSCRIPTION_ID` | `terraform.tfvars`, `*.tf` | None - must be provided |
| `resource_group` | **YES** | `AZURE_RESOURCE_GROUP` | `terraform.tfvars` | None - must be provided |
| `location` | YES | `AZURE_LOCATION` | `terraform.tfvars` | `eastus` |

### Cloudflare

| Field | Required | Env Vars to Check | Files to Search | Default |
|-------|----------|-------------------|-----------------|---------|
| `account_id` | **YES** | `CLOUDFLARE_ACCOUNT_ID`, `CF_ACCOUNT_ID` | `wrangler.toml` | None - discover via wrangler |
| `worker_name` | YES | None | `wrangler.toml` (name field) | Project name |
| `compatibility_date` | YES | None | `wrangler.toml` | Current date |

**Note**: Cloudflare uses `wrangler` CLI instead of Terraform. Authentication is handled via `wrangler login`.

## Discovery Commands

Use these Bash commands to check environment variables:

```bash
# GCP
echo "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
echo "GCP_PROJECT=$GCP_PROJECT"
echo "GCLOUD_PROJECT=$GCLOUD_PROJECT"
echo "CLOUDSDK_CORE_PROJECT=$CLOUDSDK_CORE_PROJECT"

# Also try gcloud config (if available)
gcloud config get-value project 2>/dev/null || echo "gcloud not configured"

# AWS
echo "AWS_REGION=$AWS_REGION"
echo "AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"

# Azure
echo "AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID"
echo "ARM_SUBSCRIPTION_ID=$ARM_SUBSCRIPTION_ID"

# Cloudflare
echo "CLOUDFLARE_ACCOUNT_ID=$CLOUDFLARE_ACCOUNT_ID"
echo "CF_ACCOUNT_ID=$CF_ACCOUNT_ID"

# Check wrangler authentication status
npx wrangler whoami 2>/dev/null || echo "wrangler not logged in"
```

## Asking the User

When you must ask the user for a value, use AskUserQuestion with:

1. **Plain language** - No jargon
2. **Context** - Where they can find this value
3. **Why it's needed** - Brief explanation

### Example Questions

**GCP Project ID:**
> "What Google Cloud project should we deploy to? You can find your project ID in the Google Cloud Console (console.cloud.google.com) - it's shown at the top of the page or in project settings. It looks something like 'my-project-123'."

**AWS Region:**
> "Which AWS region do you want to use? This determines where your servers will be located. For US users, 'us-east-1' (Virginia) or 'us-west-2' (Oregon) are common choices. For Europe, 'eu-west-1' (Ireland) is popular."

**Azure Subscription:**
> "What's your Azure subscription ID? You can find this in the Azure Portal under 'Subscriptions'. It's a long string of letters and numbers like 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'."

**Cloudflare Account:**
> "I need to connect to your Cloudflare account. I'll run `wrangler login` which will open your browser to authenticate. Is that okay?"

## Validation

After discovery, verify:

1. **project_id** (GCP): Matches pattern `^[a-z][a-z0-9-]{4,28}[a-z0-9]$`
2. **region** (GCP): Valid GCP region like `us-central1`, `europe-west1`
3. **region** (AWS): Valid AWS region like `us-east-1`, `eu-west-1`
4. **subscription_id** (Azure): Valid UUID format

If validation fails, ask the user to provide a corrected value.
