# Task: Analyze Codebase and Configure Infrastructure

Mode: {mode}

Follow the workflow for `infera init`:

1. First, read the codebase analysis instructions at:
   {templates_dir}/instructions/codebase_analysis.md

2. Analyze the codebase at {project_root} using Glob, Grep, Read tools

3. Read the template index and select the appropriate template:
   {templates_dir}/_index.md

4. Read the selected template for best practices

5. {interaction_instruction}

6. Output the final infrastructure configuration as a YAML code block

## Important Notes

- This phase focuses on **codebase analysis** and **architecture selection**
- Provider-specific values (project_id, etc.) will be collected during `infera plan` when Terraform is generated
- Set provider-specific fields to `null` here - they will be filled in during plan

The YAML should be parseable as an InferaConfig with this structure:
```yaml
version: '1.0'
project_name: <name>
provider: {provider}
region: us-central1  # Required for GCP/AWS/Azure, null for Cloudflare (global edge)
project_id: null  # Will be discovered/prompted during 'infera plan'
detected_frameworks: []
has_dockerfile: false
entry_point: null
architecture_type: <static_site|api_service|fullstack|containerized|worker>
resources:
  - id: <unique_id>
    type: <resource_type>
    name: <resource_name>
    provider: {provider}
    config: {{}}
    depends_on: []
domain: null
```

**Provider-specific notes:**
- **GCP/AWS/Azure**: `region` is required (e.g., `us-central1`, `us-east-1`)
- **Cloudflare**: `region` should be `null` (Workers run on global edge network)
