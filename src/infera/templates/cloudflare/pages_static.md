# Cloudflare Pages Static Site

## Overview

Deploy static websites and SPAs on Cloudflare Pages with automatic builds, global CDN distribution, and zero configuration. Ideal for React, Vue, Angular, Svelte, and static site generators.

## Detection Signals

Use this template when:
- Static build output (dist/, build/, out/, public/)
- React, Vue, Angular, Svelte, Astro detected
- Static site generators (Hugo, Gatsby, 11ty, Jekyll)
- No server-side rendering required
- Simple HTML/CSS/JS websites

## Architecture

```
    Git Repository
         │
         ▼ (push)
    ┌─────────────────┐
    │ Cloudflare      │
    │ Build System    │
    │ (npm run build) │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │              Cloudflare Global Network               │
    │                                                     │
    │   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐  │
    │   │ POP │   │ POP │   │ POP │   │ POP │   │ POP │  │
    │   │ US  │   │ EU  │   │ Asia│   │ SA  │   │ AF  │  │
    │   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘  │
    │                                                     │
    │   300+ edge locations worldwide                    │
    └─────────────────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Pages Project | Site hosting | Connected to Git repo |

### Optional
| Resource | When to Add | Configuration |
|----------|-------------|---------------|
| Custom Domain | Production domain | DNS records |
| Web Analytics | Usage tracking | Enabled in dashboard |
| Access | Authentication | Zero Trust integration |

## Configuration

### wrangler.toml
```toml
name = "my-static-site"
pages_build_output_dir = "dist"

# Optional: Environment variables for build
[vars]
API_URL = "https://api.example.com"

# Optional: Custom headers
[[headers]]
for = "/*"
[headers.values]
X-Frame-Options = "DENY"
X-Content-Type-Options = "nosniff"

[[headers]]
for = "/assets/*"
[headers.values]
Cache-Control = "public, max-age=31536000, immutable"
```

### package.json (example React)
```json
{
  "name": "my-static-site",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^5.0.0"
  }
}
```

### Build Configuration
When connecting your repository, configure:

| Framework | Build Command | Output Directory |
|-----------|---------------|------------------|
| React (Vite) | `npm run build` | `dist` |
| React (CRA) | `npm run build` | `build` |
| Vue | `npm run build` | `dist` |
| Angular | `npm run build` | `dist/project-name` |
| Svelte | `npm run build` | `build` |
| Next.js (static) | `npm run build` | `out` |
| Astro | `npm run build` | `dist` |
| Hugo | `hugo` | `public` |
| Gatsby | `gatsby build` | `public` |

## Deployment Commands

```bash
# Login to Cloudflare
npx wrangler login

# Create Pages project (connect to Git)
npx wrangler pages project create my-static-site

# Deploy manually (without Git integration)
npm run build
npx wrangler pages deploy dist

# Deploy with custom branch
npx wrangler pages deploy dist --branch production

# View deployments
npx wrangler pages deployment list my-static-site

# Add custom domain
npx wrangler pages project add-domain my-static-site example.com
```

## _headers File
```
# Cache static assets forever (use hashed filenames)
/assets/*
  Cache-Control: public, max-age=31536000, immutable

# Don't cache HTML (for SPA routing)
/*.html
  Cache-Control: no-cache

/index.html
  Cache-Control: no-cache

# Security headers
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
```

## _redirects File
```
# SPA fallback - serve index.html for all routes
/*    /index.html   200

# Redirect old URLs
/old-page    /new-page    301
/blog/*      https://blog.example.com/:splat    301

# API proxy (if using Pages Functions)
/api/*    https://api.example.com/:splat    200
```

## Best Practices

### Performance
1. Use immutable caching for hashed assets
2. Optimize images before deployment
3. Enable compression (automatic)
4. Use preload for critical resources

### SPA Configuration
1. Add `/* /index.html 200` redirect for client routing
2. Configure proper CORS if calling external APIs
3. Use environment variables for API URLs
4. Handle deep links correctly

### Security
1. Add security headers via `_headers` file
2. Use HTTPS (automatic and enforced)
3. Enable Cloudflare Access for staging environments
4. Configure CSP headers for XSS protection

## Cost Breakdown

| Component | Free Tier | Pro ($20/mo) |
|-----------|-----------|--------------|
| Requests | Unlimited | Unlimited |
| Bandwidth | Unlimited | Unlimited |
| Builds | 500/month | 5,000/month |
| Concurrent builds | 1 | 5 |
| Sites | Unlimited | Unlimited |
| Custom domains | 100 | 250 |

### Free Tier is Generous
- Unlimited bandwidth
- Unlimited requests
- 500 builds/month
- Automatic SSL
- DDoS protection

## Common Mistakes

1. **Missing SPA redirect**: Routes return 404 on refresh
2. **No cache busting**: Old assets served after deploy
3. **Large assets**: Should optimize images/videos
4. **Wrong output directory**: Build not found
5. **Hardcoded URLs**: Use environment variables
6. **Missing headers**: No security headers configured

## Example Configuration

```yaml
project_name: my-react-app
provider: cloudflare
architecture_type: pages

resources:
  - id: pages-site
    type: cloudflare_pages
    name: my-react-app
    provider: cloudflare
    config:
      production_branch: main
      build_command: npm run build
      output_directory: dist
      environment_variables:
        VITE_API_URL: https://api.example.com

domain:
  enabled: true
  name: www.example.com
  ssl: true
```

## GitHub/GitLab Integration

### Automatic Deployments
When connected to Git:
- Push to `main` → Production deployment
- Push to other branches → Preview deployment
- Pull requests → Preview with unique URL

### Environment Variables
Set in Cloudflare dashboard:
- Production variables
- Preview variables (for staging)
- Secrets (encrypted)

## Framework-Specific Notes

### Next.js Static Export
```javascript
// next.config.js
module.exports = {
  output: 'export',
  images: {
    unoptimized: true  // Required for static export
  }
}
```

### Astro
```javascript
// astro.config.mjs
export default defineConfig({
  output: 'static',
  adapter: undefined  // No adapter for static
})
```

### SvelteKit
```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-static';

export default {
  kit: {
    adapter: adapter({
      fallback: 'index.html'  // SPA mode
    })
  }
};
```

## Sources

- [Cloudflare Pages Documentation](https://developers.cloudflare.com/pages)
- [Pages Build Configuration](https://developers.cloudflare.com/pages/configuration/build-configuration)
- [Pages Pricing](https://www.cloudflare.com/plans/developer-platform/)
