# Terraform Apply (GCP, AWS, Azure)

## Prerequisites

Verify Terraform files exist:
```bash
ls {tf_dir}/main.tf
```

If not found, tell user to run `infera plan` first.

Check authentication:
```bash
# For GCP
gcloud auth list
```

## Deploy Commands

```bash
cd {tf_dir}
terraform apply -auto-approve 2>&1 | tee {tf_dir}/apply_output.txt
```

Check apply_output.txt for results.

## Common Fixes

| Error | Fix |
|-------|-----|
| State lock | `terraform force-unlock <lock-id>` |
| Resource exists | Import with `terraform import` or delete manually |
| Quota exceeded | Request increase or use different region |
| Permission denied | Check IAM roles, run `gcloud auth application-default login` |
| API not enabled | `gcloud services enable <api>` |
| Invalid credentials | `gcloud auth application-default login` |

## Post-Deploy

After successful apply:
1. Read terraform outputs: `terraform output`
2. Report the service URL and any relevant endpoints
3. Suggest next steps (e.g., configure DNS, set up CI/CD)
