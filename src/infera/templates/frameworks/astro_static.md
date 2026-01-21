# Astro Static / Hybrid

## Overview

Deploy Astro applications for content-driven websites with optimal performance. Astro's islands architecture delivers minimal JavaScript by default while supporting dynamic components when needed. Perfect for blogs, documentation, marketing sites, and portfolios with optional SSR capabilities.

## Detection Signals

Use this template when:
- `astro.config.mjs` or `astro.config.ts` exists
- `package.json` contains `astro` dependency
- `src/pages/` or `src/content/` directory structure
- `.astro` files present
- Content-focused website
- Minimal JavaScript preferred
- Multiple UI frameworks in use (React, Vue, Svelte)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Static / Edge Deployment                      │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                    CDN Edge Network                      │   │
                    │   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
                    │   │  │    Edge     │ │    Edge     │ │    Edge     │        │   │
                    │   │  │   Cache     │ │   Cache     │ │   Cache     │        │   │
                    │   │  └─────────────┘ └─────────────┘ └─────────────┘        │   │
                    │   │         │               │               │                │   │
                    │   │         ▼               ▼               ▼                │   │
                    │   │  ┌───────────────────────────────────────────────────┐  │   │
                    │   │  │                  Astro Site                        │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  ┌─────────────┐  ┌─────────────────────────────┐ │  │   │
                    │   │  │  │   Static    │  │      Interactive Islands    │ │  │   │
                    │   │  │  │   HTML/CSS  │  │  ┌───────┐ ┌───────┐        │ │  │   │
                    │   │  │  │   (0 JS)    │  │  │ React │ │ Vue   │        │ │  │   │
                    │   │  │  │             │  │  │Island │ │Island │        │ │  │   │
                    │   │  │  └─────────────┘  │  └───────┘ └───────┘        │ │  │   │
                    │   │  │                   └─────────────────────────────┘ │  │   │
                    │   │  │                                                   │  │   │
                    │   │  │  [Optional SSR: Server Endpoints / Hybrid Mode]  │  │   │
                    │   │  └───────────────────────────────────────────────────┘  │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                          │                                      │
                    │          ┌───────────────┼───────────────┐                     │
                    │          ▼               ▼               ▼                     │
                    │   ┌───────────┐   ┌───────────┐   ┌───────────┐               │
                    │   │  Headless │   │   Search  │   │   Forms   │               │
                    │   │    CMS    │   │  (Algolia)│   │(Formspree)│               │
                    │   └───────────┘   └───────────┘   └───────────┘               │
                    │                                                                 │
                    │   Zero JS default • Islands architecture • Sub-second loads    │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### Deployment Options
| Platform | Best For | Configuration |
|----------|----------|---------------|
| Cloudflare Pages | Static + SSR | Free, global CDN |
| Vercel | Static + SSR | Edge runtime |
| Netlify | Static + serverless | Easy setup |
| AWS S3 + CloudFront | Static only | Cost-effective |
| GCP Cloud Storage | Static only | Simple hosting |

### Optional Services
| Service | Purpose | Examples |
|---------|---------|----------|
| CMS | Content management | Sanity, Contentful, Strapi |
| Search | Site search | Algolia, Pagefind |
| Analytics | Traffic tracking | Plausible, Fathom |
| Forms | Contact forms | Formspree, Netlify Forms |
| Comments | User comments | Giscus, Utterances |

## Configuration

### astro.config.mjs (Static)
```javascript
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import compress from 'astro-compress';

// UI framework integrations
import react from '@astrojs/react';
import vue from '@astrojs/vue';

export default defineConfig({
  site: 'https://example.com',

  integrations: [
    tailwind(),
    mdx(),
    sitemap(),
    compress(),
    react(),
    vue(),
  ],

  // Static output (default)
  output: 'static',

  // Build configuration
  build: {
    assets: '_assets',
    inlineStylesheets: 'auto',
  },

  // Markdown configuration
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
    remarkPlugins: [],
    rehypePlugins: [],
  },

  // Image optimization
  image: {
    service: {
      entrypoint: 'astro/assets/services/sharp',
    },
  },

  // Prefetch links
  prefetch: {
    prefetchAll: true,
    defaultStrategy: 'viewport',
  },

  // Redirects
  redirects: {
    '/old-path': '/new-path',
    '/blog/[...slug]': '/posts/[...slug]',
  },

  // Experimental features
  experimental: {
    contentCollectionCache: true,
  },
});
```

### astro.config.mjs (Hybrid SSR)
```javascript
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
// Or: import vercel from '@astrojs/vercel/serverless';
// Or: import node from '@astrojs/node';

export default defineConfig({
  site: 'https://example.com',

  // Hybrid mode: static by default, SSR opt-in
  output: 'hybrid',

  // Cloudflare adapter
  adapter: cloudflare({
    mode: 'directory',
    runtime: {
      mode: 'local',
      type: 'pages',
      bindings: {
        DB: {
          type: 'd1',
        },
        KV: {
          type: 'kv',
        },
      },
    },
  }),

  integrations: [
    // ... integrations
  ],
});
```

### Content Collections
```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: ({ image }) => z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: image().optional(),
    author: z.string().default('Anonymous'),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

const docs = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    sidebar: z.object({
      label: z.string().optional(),
      order: z.number().optional(),
    }).optional(),
  }),
});

export const collections = { blog, docs };
```

### Blog Post Template
```astro
---
// src/content/blog/hello-world.md
title: "Hello World"
description: "My first blog post"
pubDate: 2024-01-15
heroImage: "./hello-world.jpg"
tags: ["astro", "web"]
---

# Hello World

This is my first blog post using Astro!

## Code Example

```javascript
console.log('Hello, Astro!');
```
```

### Layout Component
```astro
---
// src/layouts/BaseLayout.astro
import Header from '../components/Header.astro';
import Footer from '../components/Footer.astro';
import { ViewTransitions } from 'astro:transitions';

interface Props {
  title: string;
  description?: string;
  image?: string;
}

const { title, description = 'My Astro Site', image } = Astro.props;
const canonicalURL = new URL(Astro.url.pathname, Astro.site);
---

<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="canonical" href={canonicalURL} />
    <meta name="generator" content={Astro.generator} />

    <!-- SEO -->
    <title>{title}</title>
    <meta name="description" content={description} />

    <!-- Open Graph -->
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:url" content={canonicalURL} />
    {image && <meta property="og:image" content={new URL(image, Astro.url)} />}

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image" />

    <!-- View Transitions -->
    <ViewTransitions />

    <!-- Styles -->
    <link rel="stylesheet" href="/styles/global.css" />
  </head>
  <body>
    <Header />
    <main>
      <slot />
    </main>
    <Footer />
  </body>
</html>

<style is:global>
  :root {
    --color-primary: #4f46e5;
    --color-text: #1f2937;
  }

  body {
    font-family: system-ui, sans-serif;
    color: var(--color-text);
  }
</style>
```

### Blog Index Page
```astro
---
// src/pages/blog/index.astro
import { getCollection } from 'astro:content';
import BaseLayout from '../../layouts/BaseLayout.astro';
import PostCard from '../../components/PostCard.astro';

const posts = (await getCollection('blog', ({ data }) => !data.draft))
  .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
---

<BaseLayout title="Blog" description="All blog posts">
  <section class="container mx-auto px-4 py-8">
    <h1 class="text-4xl font-bold mb-8">Blog</h1>

    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      {posts.map((post) => (
        <PostCard post={post} />
      ))}
    </div>
  </section>
</BaseLayout>
```

### Dynamic Blog Post Page
```astro
---
// src/pages/blog/[...slug].astro
import { getCollection, type CollectionEntry } from 'astro:content';
import BaseLayout from '../../layouts/BaseLayout.astro';

export async function getStaticPaths() {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: post,
  }));
}

type Props = CollectionEntry<'blog'>;

const post = Astro.props;
const { Content } = await post.render();
---

<BaseLayout
  title={post.data.title}
  description={post.data.description}
  image={post.data.heroImage?.src}
>
  <article class="container mx-auto px-4 py-8 prose lg:prose-xl">
    {post.data.heroImage && (
      <img
        src={post.data.heroImage.src}
        alt={post.data.title}
        class="w-full rounded-lg"
        transition:name={`hero-${post.slug}`}
      />
    )}

    <h1 transition:name={`title-${post.slug}`}>{post.data.title}</h1>

    <div class="text-gray-500 mb-8">
      <time datetime={post.data.pubDate.toISOString()}>
        {post.data.pubDate.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        })}
      </time>
      <span class="mx-2">·</span>
      <span>{post.data.author}</span>
    </div>

    <Content />

    <div class="mt-8 flex gap-2">
      {post.data.tags.map((tag) => (
        <a
          href={`/tags/${tag}`}
          class="px-3 py-1 bg-gray-100 rounded-full text-sm hover:bg-gray-200"
        >
          #{tag}
        </a>
      ))}
    </div>
  </article>
</BaseLayout>
```

### Interactive Island Component
```astro
---
// src/components/Counter.astro - Wrapper
import Counter from './Counter.tsx';
---

<!-- Load on visible (recommended for below-fold content) -->
<Counter client:visible />

<!-- Load on page load -->
<Counter client:load />

<!-- Load on idle -->
<Counter client:idle />

<!-- Load only on interaction -->
<Counter client:only="react" />
```

```tsx
// src/components/Counter.tsx - React Island
import { useState } from 'react';

export default function Counter() {
  const [count, setCount] = useState(0);

  return (
    <div className="flex items-center gap-4 p-4 bg-gray-100 rounded-lg">
      <button
        onClick={() => setCount(c => c - 1)}
        className="px-4 py-2 bg-red-500 text-white rounded"
      >
        -
      </button>
      <span className="text-2xl font-bold">{count}</span>
      <button
        onClick={() => setCount(c => c + 1)}
        className="px-4 py-2 bg-green-500 text-white rounded"
      >
        +
      </button>
    </div>
  );
}
```

### API Endpoint (SSR Mode)
```typescript
// src/pages/api/posts.ts
import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const tag = url.searchParams.get('tag');

  let posts = await getCollection('blog', ({ data }) => !data.draft);

  if (tag) {
    posts = posts.filter(post => post.data.tags.includes(tag));
  }

  return new Response(JSON.stringify(posts.map(p => ({
    slug: p.slug,
    title: p.data.title,
    description: p.data.description,
    pubDate: p.data.pubDate,
    tags: p.data.tags,
  }))), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
```

### SSR Page with Prerender False
```astro
---
// src/pages/dashboard.astro
export const prerender = false; // SSR this page

import BaseLayout from '../layouts/BaseLayout.astro';

// Access Cloudflare bindings
const runtime = Astro.locals.runtime;
const db = runtime.env.DB;

const { results: stats } = await db
  .prepare('SELECT * FROM stats ORDER BY date DESC LIMIT 30')
  .all();
---

<BaseLayout title="Dashboard">
  <h1>Dashboard</h1>
  <div class="stats">
    {stats.map(stat => (
      <div class="stat-card">
        <span class="date">{stat.date}</span>
        <span class="value">{stat.visits}</span>
      </div>
    ))}
  </div>
</BaseLayout>
```

## Deployment Commands

### Cloudflare Pages
```bash
# Build
npm run build

# Deploy
npx wrangler pages deploy dist

# Local preview with D1/KV
npx wrangler pages dev dist --d1=DB --kv=KV
```

### Vercel
```bash
# Install CLI
npm i -g vercel

# Deploy
vercel

# Production deploy
vercel --prod
```

### Netlify
```bash
# Install CLI
npm i -g netlify-cli

# Deploy
netlify deploy

# Production
netlify deploy --prod
```

### AWS S3 + CloudFront
```bash
# Build
npm run build

# Sync to S3
aws s3 sync dist/ s3://my-bucket --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id DIST_ID --paths "/*"
```

## GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - run: npm ci
      - run: npm run build

      # Cloudflare Pages
      - name: Deploy to Cloudflare
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: my-astro-site
          directory: dist

      # Or Vercel
      # - uses: amondnet/vercel-action@v25
      #   with:
      #     vercel-token: ${{ secrets.VERCEL_TOKEN }}
      #     vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
      #     vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
```

## Cost Breakdown

| Platform | Free Tier | Paid |
|----------|-----------|------|
| Cloudflare Pages | Unlimited sites, 500 builds/mo | Unlimited |
| Vercel | 100GB bandwidth | $20/mo |
| Netlify | 100GB bandwidth, 300 min | $19/mo |
| AWS S3+CF | 1GB storage, 50GB out | ~$5/mo |

## Best Practices

1. **Use content collections** - Type-safe content with Zod
2. **Islands for interactivity** - Only hydrate what's needed
3. **Prerender by default** - Static pages are fastest
4. **Image optimization** - Use Astro's built-in service
5. **View Transitions** - Smooth page transitions
6. **Prefetch links** - Faster navigation
7. **Component islands** - React/Vue/Svelte where needed
8. **RSS + Sitemap** - Built-in integrations

## Common Mistakes

1. **Hydrating everything** - Only use client: when needed
2. **Missing content schema** - Define collections properly
3. **Large images** - Use Image component for optimization
4. **No sitemap** - Add @astrojs/sitemap
5. **Missing meta tags** - SEO requires proper meta
6. **Client-side routing** - Astro uses MPA by default
7. **Wrong adapter** - Match adapter to platform
8. **No RSS feed** - Content sites need RSS

## Example Configuration

```yaml
# infera.yaml
project_name: my-astro-site
provider: cloudflare

framework:
  name: astro
  version: "4"

deployment:
  type: static  # or hybrid for SSR

  build:
    command: npm run build
    output: dist

  # For hybrid mode
  adapter: cloudflare
  bindings:
    d1:
      - name: DB
        database: astro-db
    kv:
      - name: KV

  env_vars:
    SITE_URL: https://example.com

integrations:
  - tailwind
  - mdx
  - sitemap
  - compress
```

## Sources

- [Astro Documentation](https://docs.astro.build)
- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/)
- [Astro Cloudflare Adapter](https://docs.astro.build/en/guides/integrations-guide/cloudflare/)
- [Astro View Transitions](https://docs.astro.build/en/guides/view-transitions/)
