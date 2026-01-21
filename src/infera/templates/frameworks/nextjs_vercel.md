# Next.js on Vercel

## Overview

Deploy Next.js applications on Vercel, the platform built by the creators of Next.js. Provides zero-configuration deployment with edge functions, ISR, image optimization, and automatic CI/CD. The optimal choice for Next.js projects seeking the best developer experience and performance.

## Detection Signals

Use this template when:
- `next.config.js` or `next.config.mjs` exists
- `package.json` contains `next` dependency
- `pages/` or `app/` directory structure
- User wants managed deployment
- Edge functions or middleware needed
- Image optimization required
- ISR (Incremental Static Regeneration) needed

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                         Vercel Edge Network                      │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                     Edge Network                         │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │    Edge     │ │    Edge     │ │    Edge     │        │   │
                    │   │  │   (Global)  │ │   (Global)  │ │   (Global)  │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │               Edge Middleware                      │  │   │
                    │   │  │        (Auth, Redirects, A/B Testing)              │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │   Static    │ │   Server    │ │    API      │        │   │
                    │   │  │   Assets    │ │ Components  │ │   Routes    │        │   │
                    │   │  │   (CDN)     │ │  (Lambda)   │ │  (Lambda)   │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                │                                 │
                    │                                ▼                                 │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                   External Services                      │   │
                    │   │   ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
                    │   │   │ Database │  │   CMS    │  │  Auth    │              │   │
                    │   │   │ (Planet- │  │(Sanity/  │  │(Clerk/   │              │   │
                    │   │   │  Scale)  │  │Contentful│  │Auth0)    │              │   │
                    │   │   └──────────┘  └──────────┘  └──────────┘              │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                                                                 │
                    │   Zero-config • Edge Functions • ISR • Image Optimization       │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Included (Vercel Platform)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Edge Network | Global CDN | Automatic |
| Serverless Functions | API routes, SSR | Auto-scaled |
| Edge Functions | Middleware | Global, <1ms cold start |
| Image Optimization | next/image | Automatic |
| Analytics | Web Vitals | Optional add-on |
| KV Storage | Edge data store | Optional add-on |

### External Services (Recommended)
| Service | Purpose | Options |
|---------|---------|---------|
| Database | Data persistence | PlanetScale, Supabase, Neon |
| Auth | Authentication | Clerk, Auth0, NextAuth |
| CMS | Content management | Sanity, Contentful, Strapi |
| Email | Transactional email | Resend, SendGrid |

## Configuration

### vercel.json
```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next",
  "installCommand": "npm install",
  "regions": ["iad1", "sfo1", "cdg1"],
  "functions": {
    "app/api/**/*.ts": {
      "memory": 1024,
      "maxDuration": 30
    }
  },
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "no-store, max-age=0"
        }
      ]
    },
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/old-path",
      "destination": "/new-path"
    }
  ],
  "redirects": [
    {
      "source": "/blog/:slug",
      "destination": "/posts/:slug",
      "permanent": true
    }
  ],
  "crons": [
    {
      "path": "/api/cron/daily",
      "schedule": "0 0 * * *"
    }
  ]
}
```

### next.config.mjs
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.example.com',
      },
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // Experimental features
  experimental: {
    // Enable PPR (Partial Prerendering)
    ppr: true,
    // Server Actions
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },

  // Headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
        ],
      },
    ];
  },

  // Redirects
  async redirects() {
    return [
      {
        source: '/old',
        destination: '/new',
        permanent: true,
      },
    ];
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_APP_URL: process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : 'http://localhost:3000',
  },

  // Logging
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
```

### Edge Middleware (middleware.ts)
```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Geolocation-based routing
  const country = request.geo?.country || 'US';

  // A/B testing
  const bucket = request.cookies.get('ab-bucket')?.value ||
    (Math.random() < 0.5 ? 'a' : 'b');

  const response = NextResponse.next();

  // Set A/B test cookie
  if (!request.cookies.has('ab-bucket')) {
    response.cookies.set('ab-bucket', bucket, { maxAge: 60 * 60 * 24 * 7 });
  }

  // Add custom headers
  response.headers.set('x-country', country);
  response.headers.set('x-ab-bucket', bucket);

  // Redirect based on country
  if (country === 'DE' && !request.nextUrl.pathname.startsWith('/de')) {
    return NextResponse.redirect(new URL('/de' + request.nextUrl.pathname, request.url));
  }

  return response;
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};
```

### API Route with Edge Runtime
```typescript
// app/api/hello/route.ts
import { NextResponse } from 'next/server';

export const runtime = 'edge';
export const preferredRegion = ['iad1', 'sfo1'];

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const name = searchParams.get('name') || 'World';

  return NextResponse.json({
    message: `Hello, ${name}!`,
    timestamp: new Date().toISOString(),
  });
}
```

### ISR Example
```typescript
// app/blog/[slug]/page.tsx
import { notFound } from 'next/navigation';

interface Post {
  slug: string;
  title: string;
  content: string;
}

async function getPost(slug: string): Promise<Post | null> {
  const res = await fetch(`https://api.example.com/posts/${slug}`, {
    next: { revalidate: 3600 }, // ISR: revalidate every hour
  });

  if (!res.ok) return null;
  return res.json();
}

export async function generateStaticParams() {
  const posts = await fetch('https://api.example.com/posts').then(r => r.json());
  return posts.map((post: Post) => ({ slug: post.slug }));
}

export default async function PostPage({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);

  if (!post) notFound();

  return (
    <article>
      <h1>{post.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: post.content }} />
    </article>
  );
}
```

## Deployment Commands

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy (preview)
vercel

# Deploy to production
vercel --prod

# Link to existing project
vercel link

# Set environment variables
vercel env add NEXT_PUBLIC_API_URL
vercel env add DATABASE_URL

# Pull environment variables locally
vercel env pull .env.local

# View logs
vercel logs

# List deployments
vercel ls

# Promote preview to production
vercel promote <deployment-url>

# Rollback to previous deployment
vercel rollback

# Run build locally (same as Vercel)
vercel build

# View project settings
vercel inspect <deployment-url>
```

## Environment Variables

```bash
# Vercel Dashboard or CLI
# Production
NEXT_PUBLIC_APP_URL=https://myapp.com
DATABASE_URL=postgres://...
NEXTAUTH_SECRET=...
NEXTAUTH_URL=https://myapp.com

# Preview (automatically set)
VERCEL_URL=myapp-git-branch-team.vercel.app
VERCEL_ENV=preview

# Development
# Pulled to .env.local via `vercel env pull`
```

## Cost Breakdown

| Plan | Features | Monthly Cost |
|------|----------|--------------|
| Hobby | Personal projects, 100GB bandwidth | Free |
| Pro | Team features, 1TB bandwidth, Analytics | $20/member |
| Enterprise | SLA, dedicated support, SSO | Custom |

| Add-on | Included | Extra |
|--------|----------|-------|
| Bandwidth | 100GB-1TB | $40/100GB |
| Serverless | 100GB-hrs | $0.18/GB-hr |
| Edge Functions | 1M-10M | $2/1M invocations |
| Image Optimization | 1000-5000 | $5/1000 images |
| Analytics | Basic | $10/project |
| KV Storage | - | $1/100K reads |

## Best Practices

1. **Use App Router** - Server Components by default, better performance
2. **Leverage ISR** - Incremental Static Regeneration for dynamic content
3. **Edge Middleware** - Auth, redirects, A/B testing at edge
4. **Image Optimization** - Always use `next/image` component
5. **Environment Variables** - Use NEXT_PUBLIC_ prefix for client-side
6. **Caching** - Utilize Vercel's caching with proper cache headers
7. **Preview Deployments** - Every PR gets a unique URL
8. **Monorepo Support** - Use turborepo for multi-package repos

## Common Mistakes

1. **Not using Edge Runtime for simple API routes** - Edge is faster and cheaper
2. **Exposing secrets** - Don't use NEXT_PUBLIC_ for sensitive data
3. **Large bundle sizes** - Use dynamic imports and tree shaking
4. **Missing revalidate** - Set proper cache times for data fetching
5. **Ignoring Web Vitals** - Monitor Core Web Vitals in Analytics
6. **Hardcoding URLs** - Use VERCEL_URL for preview deployments
7. **Not using Preview Deployments** - Test every PR before merge
8. **Blocking middleware** - Keep middleware fast, use edge-compatible code

## Example Configuration

```yaml
# infera.yaml
project_name: my-nextjs-app
provider: vercel

framework:
  name: nextjs
  version: "14"

deployment:
  regions:
    - iad1
    - sfo1
    - cdg1

  functions:
    memory: 1024
    max_duration: 30

  env_vars:
    NEXT_PUBLIC_APP_URL: https://myapp.com
    DATABASE_URL: ${secrets.DATABASE_URL}

  preview:
    enabled: true
    comments: true

integrations:
  database: planetscale
  auth: clerk
  analytics: true
```

## Sources

- [Vercel Next.js Documentation](https://vercel.com/docs/frameworks/nextjs)
- [Next.js Documentation](https://nextjs.org/docs)
- [Vercel Edge Functions](https://vercel.com/docs/functions/edge-functions)
- [Vercel KV](https://vercel.com/docs/storage/vercel-kv)
