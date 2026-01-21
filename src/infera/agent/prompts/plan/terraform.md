# Terraform Plan (GCP, AWS, Azure)

## Prerequisites

Check that required CLI tools are available:

```bash
terraform version
```

If not installed, inform the user they need to install Terraform.

For GCP, also check:
```bash
gcloud auth list
```

## Generate Configuration

1. Read `{templates_dir}/instructions/terraform_generation.md`
2. Query Terraform MCP for each resource's current schema
3. Generate Terraform files in `{tf_dir}/`:
   - `main.tf` - Provider and resources
   - `variables.tf` - Variable definitions
   - `outputs.tf` - Output values

### Variable Discovery

After generating Terraform:
1. Identify required variables from the generated code
2. Read `{templates_dir}/instructions/value_discovery.md`
3. Check environment variables and project files for values
4. **Confirm discovered values with the user**
5. If user says a value is wrong, help find the correct one (e.g., `gcloud projects list`)
6. Generate `terraform.tfvars` with all values

## Validate Configuration

```bash
cd {tf_dir}
terraform init 2>&1 | tee {tf_dir}/init_output.txt
terraform plan -out=tfplan 2>&1 | tee {tf_dir}/plan_output.txt
```

Check the output files for errors.

## Common Fixes

| Error | Fix |
|-------|-----|
| Provider not found | `terraform init` |
| Invalid credentials | `gcloud auth application-default login` |
| API not enabled | `gcloud services enable <api>` |
| Quota exceeded | Request quota increase or use different region |
| Invalid project | `gcloud config set project <project-id>` |
