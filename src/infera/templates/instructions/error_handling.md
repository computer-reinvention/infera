# Error Handling Instructions

## CRITICAL RULE

**NEVER just report an error. ALWAYS provide a fix.**

Every single error response MUST include:
1. What went wrong (plain language)
2. Why it happened (brief)
3. **A specific fix** (CLI command or action)
4. **"Would you like me to help fix this?"**

If you don't know the fix, research it using CLI commands (e.g., `gcloud` help, checking docs).

## Error Handling Process

1. **Read the full error output** - understand what went wrong
2. **Identify the root cause** - categorize the error type
3. **Suggest a clear fix** - explain in plain language what needs to be done
4. **Offer to run CLI commands** - if the fix can be automated, offer to do it
5. **Ask the user** - confirm before making changes

## Common GCP Errors and Fixes

### Billing Account Disabled/Missing

**Error patterns:**
- `The billing account for the owning project is disabled`
- `accountDisabled`
- `Billing must be enabled`

**Fix:**
```bash
# List available billing accounts
gcloud billing accounts list

# Link billing account to project
gcloud billing projects link PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

**What to tell the user:**
> "Your Google Cloud project doesn't have billing enabled. This is required to create resources. Would you like me to help you link a billing account?"

Then:
1. Run `gcloud billing accounts list` to show available accounts
2. Ask which one to use
3. Offer to run the link command

### API Not Enabled

**Error patterns:**
- `API has not been used in project`
- `it is disabled`
- `Enable it by visiting`
- `googleapi: Error 403: .* API has not been enabled`

**Fix:**
```bash
# Enable the required API
gcloud services enable SERVICENAME.googleapis.com --project=PROJECT_ID
```

**What to tell the user:**
> "The [SERVICE] API isn't enabled on your project. I can enable it for you - this is safe and just allows your project to use this Google service."

### Permission Denied

**Error patterns:**
- `Permission denied`
- `does not have permission`
- `403`
- `Caller does not have permission`

**Diagnosis:**
```bash
# Check current authenticated account
gcloud auth list

# Check current project
gcloud config get-value project

# Check IAM roles for the account
gcloud projects get-iam-policy PROJECT_ID --filter="bindings.members:ACCOUNT_EMAIL"
```

**What to tell the user:**
> "Your Google Cloud account doesn't have permission to do this. Let me check what account you're using and what permissions you have."

### Project Not Found

**Error patterns:**
- `Project not found`
- `project/PROJECT_ID was not found`

**Diagnosis:**
```bash
# List projects you have access to
gcloud projects list
```

**What to tell the user:**
> "The project `PROJECT_ID` wasn't found. This could mean it doesn't exist or you don't have access. Let me show you the projects you have access to."

### Quota Exceeded

**Error patterns:**
- `Quota exceeded`
- `QUOTA_EXCEEDED`
- `Resource exhausted`

**What to tell the user:**
> "You've hit a usage limit on your Google Cloud account. This often happens with new accounts that have lower quotas. You can request a quota increase in the Google Cloud Console, or try a different region that might have more capacity."

### Region/Zone Not Available

**Error patterns:**
- `does not have enough resources available`
- `ZONE_RESOURCE_POOL_EXHAUSTED`

**Fix:**
```bash
# List available regions
gcloud compute regions list --filter="status=UP"
```

**What to tell the user:**
> "The region you selected doesn't have capacity right now. Let me show you available regions so you can pick a different one."

### Authentication Issues

**Error patterns:**
- `Could not load the default credentials`
- `UNAUTHENTICATED`
- `Authentication required`

**Fix:**
```bash
# Re-authenticate
gcloud auth application-default login
```

**What to tell the user:**
> "Your Google Cloud authentication has expired or isn't set up. I can help you log in again."

## Common Cloudflare Errors and Fixes

### Not Authenticated

**Error patterns:**
- `You are not logged in`
- `Authentication required`
- `wrangler login`

**Fix:**
```bash
# Login to Cloudflare (opens browser)
npx wrangler login

# Verify login
npx wrangler whoami
```

**What to tell the user:**
> "You need to log in to Cloudflare. I'll open your browser for authentication - just approve the request there."

### Account ID Missing/Invalid

**Error patterns:**
- `Missing account_id`
- `Could not find account`
- `Account not found`

**Fix:**
```bash
# List accounts you have access to
npx wrangler whoami

# The account ID is shown in the output
```

**What to tell the user:**
> "I need your Cloudflare account ID. Let me check which accounts you have access to."

### Worker Name Already Exists

**Error patterns:**
- `A worker with this name already exists`
- `Script already exists`

**What to tell the user:**
> "A worker with this name already exists in your account. Would you like me to use a different name, or deploy to the existing worker (this will replace it)?"

### Script Too Large

**Error patterns:**
- `Script too large`
- `Exceeded maximum`
- `Size limit exceeded`

**What to tell the user:**
> "Your worker code is too large. Cloudflare has a 1MB limit for worker scripts. You may need to split your code or remove unused dependencies."

### KV/D1 Not Found

**Error patterns:**
- `KV namespace not found`
- `D1 database not found`
- `Binding not found`

**Fix:**
```bash
# Create KV namespace
npx wrangler kv:namespace create "MY_KV"

# Create D1 database
npx wrangler d1 create my-database

# List existing resources
npx wrangler kv:namespace list
npx wrangler d1 list
```

**What to tell the user:**
> "The storage resource doesn't exist yet. Would you like me to create it for you?"

### Rate Limited

**Error patterns:**
- `Rate limited`
- `Too many requests`

**What to tell the user:**
> "Cloudflare is rate limiting requests. This usually resolves in a few minutes. Would you like me to wait and retry?"

## Common AWS Errors and Fixes

### Credentials Not Configured

**Error patterns:**
- `NoCredentialProviders`
- `Unable to locate credentials`

**Fix:**
```bash
# Configure credentials
aws configure
```

### Access Denied

**Error patterns:**
- `AccessDenied`
- `UnauthorizedAccess`

**Diagnosis:**
```bash
# Check current identity
aws sts get-caller-identity
```

## Error Response Template

When you encounter an error, respond with:

1. **What happened** (one sentence, plain language)
2. **Why it happened** (brief explanation)
3. **How to fix it** (clear steps)
4. **Offer to help** (if you can run commands to fix it)

**Example response:**

> ## ❌ Deployment Failed: Billing Not Enabled
>
> Your Google Cloud project doesn't have an active billing account, which is required to create cloud resources.
>
> **To fix this, I can:**
> 1. Show you the billing accounts you have access to
> 2. Link one of them to your project
>
> Would you like me to help with this? (This won't charge you anything - it just enables the project to use paid services when needed.)

## Unknown Errors

If you encounter an error not listed above:

1. **Search for clues** in the error message
2. **Try diagnostic commands**:
   ```bash
   # GCP diagnostics
   gcloud auth list
   gcloud config list
   gcloud projects describe PROJECT_ID

   # Check if services are enabled
   gcloud services list --enabled --project=PROJECT_ID
   ```
3. **Research the error** - use the error code/message to find solutions
4. **Still offer a path forward** - even if it's "Let me check the GCP documentation" or "Let's verify your setup step by step"

**NEVER say "I don't know how to fix this" without offering an alternative action.**

## Important Rules

- **ALWAYS provide a fix** - this is mandatory, not optional
- **Never leave the user stuck** - always suggest a path forward
- **Offer to run commands** - don't just tell them what to do, offer to do it
- **Explain in plain language** - avoid jargon like "IAM" or "403" without explanation
- **Be reassuring** - these errors are common and fixable
- **Ask before making changes** - especially for billing or permissions
- **If unsure, diagnose** - run commands to gather more info before giving up
