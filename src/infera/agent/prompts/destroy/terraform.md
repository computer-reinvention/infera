# Terraform Destroy (GCP, AWS, Azure)

## List Resources

```bash
cd {tf_dir}
terraform state list
```

## Destroy Commands

```bash
cd {tf_dir}
terraform destroy -auto-approve 2>&1 | tee {tf_dir}/destroy_output.txt
```

Check destroy_output.txt for results.

## Common Fixes

| Error | Fix |
|-------|-----|
| State lock | `terraform force-unlock <lock-id>` |
| Resource in use | Check dependencies, destroy dependent resources first |
| Permission denied | Check IAM roles |
| Resource not found | May have been deleted manually, run `terraform refresh` |

## Post-Destroy

After successful destroy:
1. Confirm all resources are gone
2. Optionally clean up local state: `rm -rf {tf_dir}/.terraform {tf_dir}/terraform.tfstate*`
