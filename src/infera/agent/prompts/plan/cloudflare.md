# Cloudflare Plan (Workers, Pages)

## Prerequisites

Check wrangler authentication:

```bash
npx wrangler whoami
```

If not logged in, ask the user:
> "You need to log in to Cloudflare. I'll run `wrangler login` which opens your browser. Is that okay?"

If yes:
```bash
npx wrangler login
```

## Generate Configuration

Determine deployment type from config's `architecture_type`:
- `static_site` → Cloudflare Pages
- `worker` or `api_service` → Cloudflare Workers

### For Workers

Create `{project_root}/wrangler.toml`:

```toml
name = "<project_name from config>"
main = "src/index.js"
compatibility_date = "2024-01-01"

[vars]
ENVIRONMENT = "production"
```

### For Pages (Static Sites)

Determine the correct build output directory:
- **React/Vite/Vue**: `./dist`
- **Next.js**: `./out` (for static export)
- **Create React App**: `./build`
- **Plain HTML (no build)**: `./.infera/deploy` (copy static files here during apply)

Create `{project_root}/wrangler.toml`:

```toml
name = "<project_name from config>"
pages_build_output_dir = "<appropriate directory>"
```

**IMPORTANT for plain HTML sites**: If there's no build step, set `pages_build_output_dir = "./.infera/deploy"`. During apply, only static files will be copied there.

## Check for Existing Resources

If config includes KV, D1, or R2:

```bash
npx wrangler kv:namespace list
npx wrangler d1 list
npx wrangler r2 bucket list
```

Create resources if needed (ask user first):
```bash
npx wrangler kv:namespace create "CACHE"
npx wrangler d1 create my-database
```

## Validate Configuration

```bash
cd {project_root}

# For workers
npx wrangler deploy --dry-run 2>&1 | tee {tf_dir}/plan_output.txt

# For pages - just verify we can connect
npx wrangler pages project list
```

## Common Fixes

| Error | Fix |
|-------|-----|
| Not authenticated | `npx wrangler login` |
| Account ID missing | `npx wrangler whoami` |
| Invalid wrangler.toml | Check syntax, ensure name is valid |
| Node.js not found | Install Node.js 16+ |
