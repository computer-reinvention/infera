# JAMstack Architecture

## Overview
JAMstack (JavaScript, APIs, Markup) is a modern web architecture that pre-renders pages at build time and enhances them with JavaScript and APIs. Delivers fast, secure, and scalable websites with excellent developer experience.

**Use when:**
- Content-heavy sites (blogs, docs, marketing)
- E-commerce with mostly static catalog
- Need excellent performance (Core Web Vitals)
- Want simple deployment and scaling
- Using headless CMS

**Don't use when:**
- Highly dynamic, personalized content
- Real-time data requirements
- Very frequent content updates (>100/day)
- Complex server-side logic needed

## Detection Signals

```
Files:
- gatsby-config.js, next.config.js (with export)
- astro.config.mjs, nuxt.config.ts
- _config.yml (Jekyll), hugo.toml

Dependencies:
- gatsby, next, astro, nuxt
- @contentful/rich-text-*, @sanity/client
- contentlayer, mdx

Code Patterns:
- getStaticProps, getStaticPaths
- generateStaticParams
- Astro.glob, Content Collections
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    JAMstack Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     Build Time                              │ │
│  │                                                             │ │
│  │  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐  │ │
│  │  │  Headless   │    │    Build     │    │   Static     │  │ │
│  │  │    CMS      │───▶│   Process    │───▶│   Assets     │  │ │
│  │  │ (Sanity,    │    │  (Next.js,   │    │  (HTML, CSS, │  │ │
│  │  │  Contentful)│    │   Astro)     │    │   JS, JSON)  │  │ │
│  │  └─────────────┘    └──────────────┘    └──────┬───────┘  │ │
│  │                                                 │          │ │
│  └─────────────────────────────────────────────────┼──────────┘ │
│                                                    │ Deploy     │
│  ┌─────────────────────────────────────────────────▼──────────┐ │
│  │                      CDN / Edge                             │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  Cloudflare Pages / Vercel / Netlify / S3+CloudFront│   │ │
│  │  │                                                      │   │ │
│  │  │  • Global edge caching                              │   │ │
│  │  │  • Instant cache invalidation                       │   │ │
│  │  │  • Edge functions for dynamic                       │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────┬───────────────────────────────┘ │
│                               │                                  │
│  ┌────────────────────────────▼───────────────────────────────┐ │
│  │                    Runtime (APIs)                           │ │
│  │                                                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │ │
│  │  │ Serverless│  │ Commerce │  │   Auth   │  │  Search  │  │ │
│  │  │ Functions │  │   API    │  │  (Auth0) │  │ (Algolia)│  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Next.js Static Export

### Configuration

```typescript
// next.config.ts
import type { NextConfig } from 'next';

const config: NextConfig = {
  output: 'export',  // Static export
  trailingSlash: true,
  images: {
    unoptimized: true,  // Or use external loader
  },
};

export default config;
```

### Static Generation

```typescript
// app/blog/[slug]/page.tsx
import { getPostBySlug, getAllPosts } from '@/lib/posts';
import { notFound } from 'next/navigation';

interface Props {
  params: { slug: string };
}

// Generate static paths at build time
export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((post) => ({
    slug: post.slug,
  }));
}

// Generate metadata
export async function generateMetadata({ params }: Props) {
  const post = await getPostBySlug(params.slug);
  if (!post) return {};

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [post.coverImage],
    },
  };
}

// Page component
export default async function BlogPost({ params }: Props) {
  const post = await getPostBySlug(params.slug);

  if (!post) {
    notFound();
  }

  return (
    <article>
      <h1>{post.title}</h1>
      <time>{post.date}</time>
      <div dangerouslySetInnerHTML={{ __html: post.content }} />
    </article>
  );
}
```

### Content from CMS (Sanity)

```typescript
// lib/sanity.ts
import { createClient } from '@sanity/client';
import imageUrlBuilder from '@sanity/image-url';

export const client = createClient({
  projectId: process.env.SANITY_PROJECT_ID!,
  dataset: 'production',
  apiVersion: '2024-01-01',
  useCdn: true,
});

const builder = imageUrlBuilder(client);
export const urlFor = (source: any) => builder.image(source);

// lib/posts.ts
import { client } from './sanity';

export async function getAllPosts() {
  return client.fetch(`
    *[_type == "post"] | order(publishedAt desc) {
      _id,
      title,
      slug,
      excerpt,
      publishedAt,
      "coverImage": coverImage.asset->url
    }
  `);
}

export async function getPostBySlug(slug: string) {
  return client.fetch(`
    *[_type == "post" && slug.current == $slug][0] {
      _id,
      title,
      slug,
      excerpt,
      content,
      publishedAt,
      "coverImage": coverImage.asset->url,
      "author": author->{name, image}
    }
  `, { slug });
}
```

## Astro Implementation

### Configuration

```typescript
// astro.config.mjs
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://example.com',
  integrations: [mdx(), sitemap(), tailwind()],
  output: 'static',  // Default
});
```

### Content Collections

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
});

export const collections = { blog };

// src/pages/blog/[...slug].astro
---
import { getCollection, type CollectionEntry } from 'astro:content';
import BlogLayout from '@/layouts/BlogLayout.astro';

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: { post },
  }));
}

interface Props {
  post: CollectionEntry<'blog'>;
}

const { post } = Astro.props;
const { Content } = await post.render();
---

<BlogLayout title={post.data.title}>
  <article>
    <h1>{post.data.title}</h1>
    <time datetime={post.data.pubDate.toISOString()}>
      {post.data.pubDate.toLocaleDateString()}
    </time>
    <Content />
  </article>
</BlogLayout>
```

## Headless CMS Options

### Contentful

```typescript
// lib/contentful.ts
import { createClient } from 'contentful';

const client = createClient({
  space: process.env.CONTENTFUL_SPACE_ID!,
  accessToken: process.env.CONTENTFUL_ACCESS_TOKEN!,
});

export async function getPosts() {
  const entries = await client.getEntries({
    content_type: 'blogPost',
    order: ['-sys.createdAt'],
  });

  return entries.items.map((item) => ({
    id: item.sys.id,
    title: item.fields.title,
    slug: item.fields.slug,
    content: item.fields.content,
    publishedAt: item.sys.createdAt,
  }));
}
```

### Sanity

```typescript
// sanity.config.ts
import { defineConfig } from 'sanity';
import { deskTool } from 'sanity/desk';

export default defineConfig({
  name: 'default',
  title: 'My Blog',
  projectId: 'your-project-id',
  dataset: 'production',
  plugins: [deskTool()],
  schema: {
    types: [
      {
        name: 'post',
        title: 'Post',
        type: 'document',
        fields: [
          { name: 'title', type: 'string' },
          { name: 'slug', type: 'slug', options: { source: 'title' } },
          { name: 'content', type: 'array', of: [{ type: 'block' }] },
          { name: 'coverImage', type: 'image' },
          { name: 'publishedAt', type: 'datetime' },
        ],
      },
    ],
  },
});
```

### MDX (Local Content)

```typescript
// contentlayer.config.ts
import { defineDocumentType, makeSource } from 'contentlayer/source-files';
import rehypePrettyCode from 'rehype-pretty-code';

export const Post = defineDocumentType(() => ({
  name: 'Post',
  filePathPattern: 'posts/**/*.mdx',
  contentType: 'mdx',
  fields: {
    title: { type: 'string', required: true },
    date: { type: 'date', required: true },
    description: { type: 'string', required: true },
    tags: { type: 'list', of: { type: 'string' } },
  },
  computedFields: {
    slug: {
      type: 'string',
      resolve: (post) => post._raw.flattenedPath.replace('posts/', ''),
    },
    url: {
      type: 'string',
      resolve: (post) => `/blog/${post._raw.flattenedPath.replace('posts/', '')}`,
    },
  },
}));

export default makeSource({
  contentDirPath: 'content',
  documentTypes: [Post],
  mdx: {
    rehypePlugins: [[rehypePrettyCode, { theme: 'github-dark' }]],
  },
});
```

## Incremental Static Regeneration (ISR)

```typescript
// app/products/[id]/page.tsx
// For platforms that support ISR (Vercel, Netlify)

export const revalidate = 3600; // Revalidate every hour

export async function generateStaticParams() {
  // Generate top products at build time
  const products = await getTopProducts(100);
  return products.map((p) => ({ id: p.id }));
}

export default async function ProductPage({ params }: { params: { id: string } }) {
  const product = await getProduct(params.id);

  if (!product) {
    notFound();
  }

  return <ProductDetail product={product} />;
}

// On-demand revalidation
// app/api/revalidate/route.ts
import { revalidatePath, revalidateTag } from 'next/cache';

export async function POST(request: Request) {
  const { secret, path, tag } = await request.json();

  if (secret !== process.env.REVALIDATION_SECRET) {
    return Response.json({ error: 'Invalid secret' }, { status: 401 });
  }

  if (path) {
    revalidatePath(path);
  }
  if (tag) {
    revalidateTag(tag);
  }

  return Response.json({ revalidated: true });
}
```

## Deployment Configuration

### Cloudflare Pages

```toml
# wrangler.toml (for functions)
name = "my-jamstack-site"
compatibility_date = "2024-01-01"

[site]
bucket = "./dist"
```

```yaml
# GitHub Action
name: Deploy to Cloudflare Pages

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - run: npm ci
      - run: npm run build

      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: my-site
          directory: dist
```

### Vercel

```json
// vercel.json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "astro",
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        }
      ]
    }
  ],
  "redirects": [
    {
      "source": "/old-path",
      "destination": "/new-path",
      "permanent": true
    }
  ]
}
```

### S3 + CloudFront

```hcl
# s3_cloudfront.tf

resource "aws_s3_bucket" "site" {
  bucket = var.domain_name
}

resource "aws_s3_bucket_website_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "404.html"
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = [var.domain_name]

  origin {
    domain_name = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id   = "S3Origin"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.site.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3Origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  # SPA fallback
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.site.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
```

## Cost Breakdown

| Platform | Free Tier | Pro Pricing |
|----------|-----------|-------------|
| **Vercel** | 100GB bandwidth | $20/mo |
| **Netlify** | 100GB bandwidth | $19/mo |
| **Cloudflare Pages** | Unlimited bandwidth | Free |
| **S3 + CloudFront** | - | ~$5-20/mo |

## Best Practices

### Performance

```typescript
// Preload critical assets
<link rel="preload" href="/fonts/Inter.woff2" as="font" type="font/woff2" crossOrigin="" />

// Image optimization
import Image from 'next/image';
<Image src={post.image} alt="" width={800} height={400} priority />

// Code splitting
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <Skeleton />,
});
```

### SEO

```typescript
// Sitemap generation
// next-sitemap.config.js
module.exports = {
  siteUrl: 'https://example.com',
  generateRobotsTxt: true,
  sitemapSize: 5000,
  changefreq: 'daily',
  priority: 0.7,
};
```

## Common Mistakes

1. **Not pre-rendering enough** - Too much client-side fetching
2. **Missing sitemap** - Poor SEO indexing
3. **No 404 handling** - Broken user experience
4. **Large bundle sizes** - Slow initial load
5. **Missing image optimization** - Core Web Vitals issues
6. **No cache headers** - Redundant CDN fetches
7. **Build times too long** - Slow deployments
8. **No preview mode** - Hard to review content
9. **Missing redirects** - Broken links after migration
10. **No ISR for dynamic content** - Stale pages

## Example Configuration

```yaml
# infera.yaml
project_name: my-blog
provider: cloudflare

jamstack:
  framework: astro
  cms: sanity

  build:
    command: npm run build
    output: dist

  content:
    revalidation: webhook
    preview: true

deployment:
  platform: cloudflare_pages
  branch: main

  environment:
    SANITY_PROJECT_ID: abc123
    SANITY_TOKEN:
      from_secret: sanity-token

  headers:
    - pattern: "/*"
      headers:
        Cache-Control: "public, max-age=31536000, immutable"
    - pattern: "/index.html"
      headers:
        Cache-Control: "public, max-age=0, must-revalidate"
```

## Sources

- [JAMstack.org](https://jamstack.org/)
- [Next.js Static Export](https://nextjs.org/docs/app/building-your-application/deploying/static-exports)
- [Astro Documentation](https://docs.astro.build/)
- [Sanity Documentation](https://www.sanity.io/docs)
- [Contentful Documentation](https://www.contentful.com/developers/docs/)
- [Cloudflare Pages](https://developers.cloudflare.com/pages/)
