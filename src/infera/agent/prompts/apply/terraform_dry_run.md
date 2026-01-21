# Terraform Dry Run (Plan Only)

## Prerequisites

Verify Terraform files exist:
```bash
ls {tf_dir}/main.tf
```

If not found, tell user to run `infera plan` first.

## Deploy Commands

This is a dry run - only show what would be changed:

```bash
cd {tf_dir}
terraform plan 2>&1 | tee {tf_dir}/plan_output.txt
```

Check plan_output.txt for results.

## Common Fixes

| Error | Fix |
|-------|-----|
| State lock | `terraform force-unlock <lock-id>` |
| Invalid credentials | `gcloud auth application-default login` |
| API not enabled | `gcloud services enable <api>` |

## Post-Plan

After successful plan:
1. Show summary of changes (resources to add/change/destroy)
2. Show estimated costs if available
3. Remind user to run `infera apply` (without --dry-run) to apply changes
