# Cloudflare Apply (Workers, Pages)

## Prerequisites

Check authentication:
```bash
npx wrangler whoami
```

If not authenticated:
```bash
npx wrangler login
```

## Deploy Commands

### For Workers

```bash
cd {project_root}
npx wrangler deploy 2>&1 | tee {tf_dir}/apply_output.txt
```

### For Pages (Static Sites)

**IMPORTANT: Never deploy the entire project root. Only deploy actual static files.**

**For sites with a build step:**
```bash
cd {project_root}
npm run build  # or appropriate build command
npx wrangler pages deploy ./dist --project-name=<project_name> 2>&1 | tee {tf_dir}/apply_output.txt
```

**For plain HTML sites (no build step):**
```bash
cd {project_root}

# Create clean deploy directory with only static files
mkdir -p .infera/deploy
find . -maxdepth 1 -type f \( -name "*.html" -o -name "*.css" -o -name "*.js" -o -name "*.ico" -o -name "*.png" -o -name "*.jpg" -o -name "*.svg" \) -exec cp {{}} .infera/deploy/ \;

# Copy asset directories if they exist
[ -d "assets" ] && cp -r assets .infera/deploy/
[ -d "images" ] && cp -r images .infera/deploy/
[ -d "css" ] && cp -r css .infera/deploy/
[ -d "js" ] && cp -r js .infera/deploy/

# Deploy from clean directory
npx wrangler pages deploy .infera/deploy --project-name=<project_name> 2>&1 | tee {tf_dir}/apply_output.txt
```

**If project doesn't exist yet:**
```bash
npx wrangler pages project create <project_name> --production-branch=main
```

## Common Fixes

| Error | Fix |
|-------|-----|
| Not authenticated | `npx wrangler login` |
| Project not found | `npx wrangler pages project create <name>` |
| Script too large | Suggest code splitting or dependency cleanup |
| KV not found | `npx wrangler kv:namespace create NAME` |
| D1 not found | `npx wrangler d1 create NAME` |
| Account ID missing | `npx wrangler whoami` |
| Email not verified | Verify email in Cloudflare dashboard |

## Post-Deploy

After successful deploy:
1. Report the live URL (e.g., `https://project.pages.dev`)
2. Suggest viewing logs: `npx wrangler tail` (for workers)
3. Mention custom domain setup if configured
