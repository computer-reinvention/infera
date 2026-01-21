# Cloudflare Destroy (Workers, Pages)

## List Resources

```bash
# For workers
npx wrangler deployments list

# For pages
npx wrangler pages project list
```

## Destroy Commands

### For Workers

```bash
cd {project_root}
npx wrangler delete 2>&1 | tee {tf_dir}/destroy_output.txt
```

### For Pages

```bash
npx wrangler pages project delete <project_name> 2>&1 | tee {tf_dir}/destroy_output.txt
```

### For KV Namespaces (if created)

```bash
npx wrangler kv:namespace delete --namespace-id=<NAMESPACE_ID>
```

### For D1 Databases (if created)

```bash
npx wrangler d1 delete <DATABASE_NAME>
```

### For R2 Buckets (if created)

```bash
npx wrangler r2 bucket delete <BUCKET_NAME>
```

## Common Fixes

| Error | Fix |
|-------|-----|
| Not authenticated | `npx wrangler login` |
| Resource not found | May already be deleted |
| Permission denied | Check Cloudflare account permissions |

## Post-Destroy

After successful destroy:
1. Confirm resources are gone
2. Optionally remove wrangler.toml: `rm {project_root}/wrangler.toml`
