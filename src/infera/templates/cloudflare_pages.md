# Cloudflare Pages (Static Sites)

## Overview

This template is for hosting static websites and SPAs using Cloudflare Pages. Pages provides global CDN distribution, automatic HTTPS, and seamless integration with Git.

## Detection Signals

Use this template when you detect:
- Static site generators (React, Vue, Next.js static export, Hugo, etc.)
- `package.json` with build command producing static output
- HTML/CSS/JS files without server-side logic
- No `wrangler.toml` (use Worker template if present)

## When to Choose Cloudflare vs GCP

| Use Cloudflare Pages When | Use GCP Cloud Storage When |
|--------------------------|---------------------------|
| Want automatic Git deploys | Need fine-grained control |
| Global edge CDN included | Specific region requirements |
| Free tier is sufficient | Need other GCP services |
| Simple static hosting | Complex IAM requirements |

## Resources Needed

### Required
- **Cloudflare Account**: Free tier includes unlimited sites
- **Build Configuration**: Framework preset or custom build command

### Optional
- **Custom Domain**: Connect your domain (free SSL included)
- **Pages Functions**: Serverless functions alongside static assets
- **Environment Variables**: Build-time or runtime configuration

## Project Structure

```
my-site/
├── src/                # Source files
├── public/             # Static assets
├── package.json        # Dependencies
└── (dist|build|out)/   # Build output (gitignored)
```

## Deployment Methods

### Method 1: Git Integration (Recommended)

Connect GitHub/GitLab for automatic deploys:

1. Go to Cloudflare Dashboard → Pages
2. Create project → Connect to Git
3. Select repository
4. Configure build settings:
   - Build command: `npm run build`
   - Build output: `dist` (or `build`, `out`, etc.)
5. Deploy

### Method 2: Direct Upload (CLI)

```bash
# Install wrangler
npm install -g wrangler

# Login
wrangler login

# Deploy (from build directory)
npx wrangler pages deploy ./dist --project-name=my-site
```

### Method 3: Wrangler Config

Create `wrangler.toml`:

```toml
name = "my-site"
pages_build_output_dir = "./dist"

# Optional: Environment variables
[vars]
API_URL = "https://api.example.com"
```

## Plain HTML Sites (No Build Step)

For simple HTML/CSS/JS sites without a build process:

**IMPORTANT**: Do NOT deploy the entire project directory. Internal directories like `.infera`, `.git`, `node_modules` should never be uploaded.

**Recommended approach**:
1. Copy only static files to `.infera/deploy/`
2. Deploy from that clean directory

```bash
# Copy static files only
mkdir -p .infera/deploy
cp *.html *.css *.js .infera/deploy/ 2>/dev/null || true
cp -r assets images css js .infera/deploy/ 2>/dev/null || true

# Deploy from clean directory
npx wrangler pages deploy .infera/deploy --project-name=my-site
```

**Config for plain HTML**:
```yaml
resources:
  - id: pages
    type: cloudflare_pages
    config:
      build_command: null
      build_output: .infera/deploy
      deployment_method: direct_upload
```

## Framework Presets

Cloudflare Pages auto-detects these frameworks:

| Framework | Build Command | Output Directory |
|-----------|--------------|------------------|
| React (CRA) | `npm run build` | `build` |
| React (Vite) | `npm run build` | `dist` |
| Vue | `npm run build` | `dist` |
| Next.js (static) | `npm run build` | `out` |
| Nuxt (static) | `npm run generate` | `dist` |
| Svelte | `npm run build` | `build` |
| Angular | `npm run build` | `dist/app-name` |
| Hugo | `hugo` | `public` |
| Astro | `npm run build` | `dist` |
| Plain HTML | (none) | `.infera/deploy` |

## Deployment Commands

```bash
# Install wrangler (if not installed)
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Build your site first
npm run build

# Deploy to Pages
npx wrangler pages deploy ./dist --project-name=my-site

# Deploy with specific branch (for preview)
npx wrangler pages deploy ./dist --project-name=my-site --branch=preview
```

## Pages Functions (Optional)

Add serverless functions alongside your static site:

```
my-site/
├── functions/
│   ├── api/
│   │   └── hello.js    # /api/hello endpoint
│   └── _middleware.js  # Runs on all requests
├── src/
└── package.json
```

```javascript
// functions/api/hello.js
export async function onRequest(context) {
  return new Response(JSON.stringify({ message: "Hello!" }), {
    headers: { "Content-Type": "application/json" }
  });
}
```

## Best Practices

### Build Configuration
1. Use environment variables for API URLs
2. Enable source maps for debugging
3. Optimize images before build
4. Use framework's production mode

### Caching
1. Pages automatically caches at edge
2. Use hashed filenames for long-term caching
3. Set appropriate Cache-Control headers

### Performance
1. Enable compression (automatic)
2. Minimize JavaScript bundle size
3. Use lazy loading for images
4. Implement code splitting

## Cost Optimization

| Feature | Free Tier | Pro Plan ($20/mo) |
|---------|-----------|-------------------|
| Sites | Unlimited | Unlimited |
| Bandwidth | Unlimited | Unlimited |
| Builds | 500/month | 5,000/month |
| Concurrent Builds | 1 | 5 |
| Functions Requests | 100k/day | 10M/month |
| Custom Domains | Unlimited | Unlimited |

**Tips**:
- Free tier is sufficient for most projects
- Git integration means automatic deploys
- No egress costs (unlike GCP/AWS)

## Common Mistakes

1. **Wrong output directory**: Check framework docs for correct path
2. **Missing build command**: Must specify how to build
3. **Environment variables**: Use Pages settings, not `.env` files in git
4. **SPA routing**: Configure `_redirects` or `_headers` file

## SPA Routing Configuration

For client-side routing (React Router, Vue Router, etc.), create:

**`public/_redirects`**:
```
/*    /index.html   200
```

Or **`public/_headers`**:
```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
```

## Example Configuration

For a React SPA:

```yaml
project_name: my-portfolio
provider: cloudflare
architecture_type: static_site

resources:
  - id: pages
    type: cloudflare_pages
    name: my-portfolio
    provider: cloudflare
    config:
      build_command: npm run build
      build_output: dist

domain:
  enabled: true
  name: portfolio.example.com
```

## Estimated Costs

For any static site:
- **Total: $0/month** (free tier covers most use cases)

Even high-traffic sites (millions of requests):
- **Total: $0/month** (unlimited bandwidth on free tier)

Pro plan benefits ($20/month):
- More concurrent builds
- Web Analytics
- More Functions requests
