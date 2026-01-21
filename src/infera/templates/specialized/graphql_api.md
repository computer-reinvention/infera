# GraphQL API

## Overview
GraphQL provides a flexible query language for APIs, allowing clients to request exactly the data they need. It's ideal for applications with complex data requirements, multiple client types, or rapidly evolving schemas.

**Use when:**
- Multiple clients need different data views
- Complex nested data relationships
- Reducing over-fetching/under-fetching
- Need introspection and strong typing
- Evolving APIs without versioning

**Don't use when:**
- Simple CRUD operations
- File uploads are primary use case
- Caching is critical (REST is simpler)
- Team unfamiliar with GraphQL

## Detection Signals

```
Files:
- schema.graphql, *.graphql
- resolvers/, typeDefs/
- codegen.yml, codegen.ts

Dependencies:
- @apollo/server, graphql-yoga, mercurius (Node.js)
- strawberry-graphql, ariadne, graphene (Python)
- gqlgen, 99designs/gqlgen (Go)
- juniper (Rust)

Code Patterns:
- type Query {, type Mutation {
- @Query, @Mutation decorators
- useQuery, useMutation hooks
- gql`query { ... }`
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GraphQL API Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                       Clients                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │   Web App   │  │  Mobile App │  │   Partner   │      │   │
│  │  │  (Apollo)   │  │  (Apollo)   │  │    API      │      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │   │
│  │         │                │                │              │   │
│  └─────────┼────────────────┼────────────────┼──────────────┘   │
│            └────────────────┼────────────────┘                   │
│                             │ POST /graphql                      │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                   GraphQL Server                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │                    Schema                            │ │   │
│  │  │  type Query {                                       │ │   │
│  │  │    user(id: ID!): User                              │ │   │
│  │  │    posts(limit: Int): [Post!]!                      │ │   │
│  │  │  }                                                  │ │   │
│  │  │  type Mutation { ... }                              │ │   │
│  │  │  type Subscription { ... }                          │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │                          │                                │   │
│  │  ┌───────────────────────▼───────────────────────────┐   │   │
│  │  │                   Resolvers                        │   │   │
│  │  │  Query.user → DataLoader → Database               │   │   │
│  │  │  Query.posts → DataLoader → Database              │   │   │
│  │  │  User.posts → DataLoader → Database (N+1 solved)  │   │   │
│  │  └───────────────────────┬───────────────────────────┘   │   │
│  └──────────────────────────┼────────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │                    Data Sources                            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │ Database │  │   REST   │  │  Redis   │  │ External │  │  │
│  │  │ (Prisma) │  │   API    │  │  Cache   │  │   API    │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Node.js Implementation

### Apollo Server

```typescript
// schema.ts
export const typeDefs = `#graphql
  type User {
    id: ID!
    email: String!
    name: String
    posts: [Post!]!
    createdAt: DateTime!
  }

  type Post {
    id: ID!
    title: String!
    content: String
    author: User!
    comments: [Comment!]!
    published: Boolean!
    createdAt: DateTime!
  }

  type Comment {
    id: ID!
    content: String!
    author: User!
    post: Post!
    createdAt: DateTime!
  }

  type Query {
    user(id: ID!): User
    users(limit: Int, offset: Int): [User!]!
    post(id: ID!): Post
    posts(limit: Int, offset: Int, published: Boolean): [Post!]!
    me: User
  }

  type Mutation {
    createUser(input: CreateUserInput!): User!
    createPost(input: CreatePostInput!): Post!
    updatePost(id: ID!, input: UpdatePostInput!): Post!
    deletePost(id: ID!): Boolean!
    publishPost(id: ID!): Post!
  }

  type Subscription {
    postCreated: Post!
    commentAdded(postId: ID!): Comment!
  }

  input CreateUserInput {
    email: String!
    name: String
  }

  input CreatePostInput {
    title: String!
    content: String
  }

  input UpdatePostInput {
    title: String
    content: String
  }

  scalar DateTime
`;

// resolvers.ts
import { PrismaClient } from '@prisma/client';
import DataLoader from 'dataloader';
import { GraphQLError } from 'graphql';
import { PubSub } from 'graphql-subscriptions';

const prisma = new PrismaClient();
const pubsub = new PubSub();

// DataLoaders to solve N+1 problem
function createLoaders() {
  return {
    userLoader: new DataLoader<string, User>(async (ids) => {
      const users = await prisma.user.findMany({
        where: { id: { in: [...ids] } },
      });
      const userMap = new Map(users.map((u) => [u.id, u]));
      return ids.map((id) => userMap.get(id)!);
    }),
    postsByAuthorLoader: new DataLoader<string, Post[]>(async (authorIds) => {
      const posts = await prisma.post.findMany({
        where: { authorId: { in: [...authorIds] } },
      });
      const postMap = new Map<string, Post[]>();
      posts.forEach((post) => {
        const existing = postMap.get(post.authorId) || [];
        postMap.set(post.authorId, [...existing, post]);
      });
      return authorIds.map((id) => postMap.get(id) || []);
    }),
  };
}

export const resolvers = {
  Query: {
    user: async (_: any, { id }: { id: string }, context: Context) => {
      return context.loaders.userLoader.load(id);
    },
    users: async (_: any, { limit = 10, offset = 0 }: { limit?: number; offset?: number }) => {
      return prisma.user.findMany({ take: limit, skip: offset });
    },
    post: async (_: any, { id }: { id: string }) => {
      return prisma.post.findUnique({ where: { id } });
    },
    posts: async (_: any, args: { limit?: number; offset?: number; published?: boolean }) => {
      return prisma.post.findMany({
        take: args.limit || 10,
        skip: args.offset || 0,
        where: args.published !== undefined ? { published: args.published } : undefined,
        orderBy: { createdAt: 'desc' },
      });
    },
    me: (_: any, __: any, context: Context) => {
      if (!context.user) throw new GraphQLError('Not authenticated');
      return context.loaders.userLoader.load(context.user.id);
    },
  },

  Mutation: {
    createUser: async (_: any, { input }: { input: CreateUserInput }) => {
      return prisma.user.create({ data: input });
    },
    createPost: async (_: any, { input }: { input: CreatePostInput }, context: Context) => {
      if (!context.user) throw new GraphQLError('Not authenticated');

      const post = await prisma.post.create({
        data: {
          ...input,
          authorId: context.user.id,
        },
        include: { author: true },
      });

      pubsub.publish('POST_CREATED', { postCreated: post });
      return post;
    },
    updatePost: async (_: any, { id, input }: { id: string; input: UpdatePostInput }, context: Context) => {
      const post = await prisma.post.findUnique({ where: { id } });
      if (!post) throw new GraphQLError('Post not found');
      if (post.authorId !== context.user?.id) throw new GraphQLError('Not authorized');

      return prisma.post.update({ where: { id }, data: input });
    },
    deletePost: async (_: any, { id }: { id: string }, context: Context) => {
      const post = await prisma.post.findUnique({ where: { id } });
      if (!post) throw new GraphQLError('Post not found');
      if (post.authorId !== context.user?.id) throw new GraphQLError('Not authorized');

      await prisma.post.delete({ where: { id } });
      return true;
    },
    publishPost: async (_: any, { id }: { id: string }, context: Context) => {
      const post = await prisma.post.findUnique({ where: { id } });
      if (!post) throw new GraphQLError('Post not found');
      if (post.authorId !== context.user?.id) throw new GraphQLError('Not authorized');

      return prisma.post.update({
        where: { id },
        data: { published: true },
      });
    },
  },

  Subscription: {
    postCreated: {
      subscribe: () => pubsub.asyncIterator(['POST_CREATED']),
    },
    commentAdded: {
      subscribe: (_: any, { postId }: { postId: string }) => {
        return pubsub.asyncIterator([`COMMENT_ADDED_${postId}`]);
      },
    },
  },

  // Field resolvers
  User: {
    posts: (parent: User, _: any, context: Context) => {
      return context.loaders.postsByAuthorLoader.load(parent.id);
    },
  },

  Post: {
    author: (parent: Post, _: any, context: Context) => {
      return context.loaders.userLoader.load(parent.authorId);
    },
    comments: (parent: Post) => {
      return prisma.comment.findMany({ where: { postId: parent.id } });
    },
  },
};

// server.ts
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import express from 'express';
import cors from 'cors';
import { json } from 'body-parser';

interface Context {
  user: User | null;
  loaders: ReturnType<typeof createLoaders>;
}

const server = new ApolloServer<Context>({
  typeDefs,
  resolvers,
  plugins: [
    // Logging plugin
    {
      async requestDidStart() {
        return {
          async didEncounterErrors({ errors }) {
            errors.forEach((error) => console.error('GraphQL Error:', error));
          },
        };
      },
    },
  ],
});

await server.start();

const app = express();

app.use(
  '/graphql',
  cors<cors.CorsRequest>(),
  json(),
  expressMiddleware(server, {
    context: async ({ req }) => {
      const token = req.headers.authorization?.replace('Bearer ', '');
      const user = token ? await verifyToken(token) : null;
      return {
        user,
        loaders: createLoaders(),
      };
    },
  })
);

app.listen(4000, () => {
  console.log('Server running at http://localhost:4000/graphql');
});
```

### GraphQL Yoga (Lightweight)

```typescript
// server.ts
import { createYoga, createSchema } from 'graphql-yoga';
import { createServer } from 'http';

const yoga = createYoga({
  schema: createSchema({
    typeDefs,
    resolvers,
  }),
  context: async ({ request }) => {
    const token = request.headers.get('authorization')?.replace('Bearer ', '');
    const user = token ? await verifyToken(token) : null;
    return { user, loaders: createLoaders() };
  },
  maskedErrors: process.env.NODE_ENV === 'production',
  graphiql: process.env.NODE_ENV !== 'production',
});

const server = createServer(yoga);
server.listen(4000, () => {
  console.log('Server running at http://localhost:4000/graphql');
});
```

## Python Implementation

### Strawberry (Async, Type-Safe)

```python
# schema.py
import strawberry
from strawberry.types import Info
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass

@strawberry.type
class User:
    id: strawberry.ID
    email: str
    name: Optional[str]
    created_at: datetime

    @strawberry.field
    async def posts(self, info: Info) -> List["Post"]:
        return await info.context.loaders.posts_by_author.load(self.id)


@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    content: Optional[str]
    published: bool
    author_id: strawberry.Private[str]
    created_at: datetime

    @strawberry.field
    async def author(self, info: Info) -> User:
        return await info.context.loaders.user.load(self.author_id)


@strawberry.input
class CreatePostInput:
    title: str
    content: Optional[str] = None


@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID, info: Info) -> Optional[User]:
        return await info.context.loaders.user.load(id)

    @strawberry.field
    async def posts(
        self,
        limit: int = 10,
        offset: int = 0,
        published: Optional[bool] = None,
    ) -> List[Post]:
        query = select(PostModel)
        if published is not None:
            query = query.where(PostModel.published == published)
        query = query.offset(offset).limit(limit)

        async with get_session() as session:
            result = await session.execute(query)
            return [Post.from_orm(p) for p in result.scalars()]

    @strawberry.field
    async def me(self, info: Info) -> Optional[User]:
        if not info.context.user:
            return None
        return await info.context.loaders.user.load(info.context.user.id)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_post(self, input: CreatePostInput, info: Info) -> Post:
        if not info.context.user:
            raise Exception("Not authenticated")

        async with get_session() as session:
            post = PostModel(
                title=input.title,
                content=input.content,
                author_id=info.context.user.id,
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return Post.from_orm(post)


schema = strawberry.Schema(query=Query, mutation=Mutation)

# server.py
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI, Depends

app = FastAPI()

async def get_context(request: Request):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    user = await verify_token(token) if token else None
    return {
        "user": user,
        "loaders": create_loaders(),
    }

graphql_router = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_router, prefix="/graphql")
```

## Client Implementation

### Apollo Client (React)

```typescript
// apollo-client.ts
import { ApolloClient, InMemoryCache, createHttpLink, from } from '@apollo/client';
import { setContext } from '@apollo/client/link/context';
import { onError } from '@apollo/client/link/error';

const httpLink = createHttpLink({
  uri: process.env.NEXT_PUBLIC_GRAPHQL_URL,
});

const authLink = setContext((_, { headers }) => {
  const token = localStorage.getItem('token');
  return {
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
    },
  };
});

const errorLink = onError(({ graphQLErrors, networkError }) => {
  if (graphQLErrors) {
    graphQLErrors.forEach(({ message, locations, path }) =>
      console.error(`[GraphQL error]: Message: ${message}, Path: ${path}`)
    );
  }
  if (networkError) {
    console.error(`[Network error]: ${networkError}`);
  }
});

export const client = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          posts: {
            keyArgs: ['published'],
            merge(existing = [], incoming) {
              return [...existing, ...incoming];
            },
          },
        },
      },
    },
  }),
});

// hooks/usePosts.ts
import { gql, useQuery } from '@apollo/client';

const GET_POSTS = gql`
  query GetPosts($limit: Int, $offset: Int, $published: Boolean) {
    posts(limit: $limit, offset: $offset, published: $published) {
      id
      title
      content
      createdAt
      author {
        id
        name
      }
    }
  }
`;

export function usePosts(published?: boolean) {
  return useQuery(GET_POSTS, {
    variables: { limit: 10, offset: 0, published },
  });
}

// components/PostList.tsx
function PostList() {
  const { data, loading, error, fetchMore } = usePosts(true);

  if (loading) return <Loading />;
  if (error) return <Error message={error.message} />;

  const loadMore = () => {
    fetchMore({
      variables: { offset: data.posts.length },
    });
  };

  return (
    <div>
      {data.posts.map((post) => (
        <PostCard key={post.id} post={post} />
      ))}
      <button onClick={loadMore}>Load More</button>
    </div>
  );
}
```

### Code Generation

```yaml
# codegen.ts
import type { CodegenConfig } from '@graphql-codegen/cli';

const config: CodegenConfig = {
  schema: 'http://localhost:4000/graphql',
  documents: ['src/**/*.tsx', 'src/**/*.ts'],
  generates: {
    './src/gql/': {
      preset: 'client',
      plugins: [],
      config: {
        withHooks: true,
      },
    },
  },
};

export default config;
```

```bash
# Generate types
npx graphql-codegen
```

## Cost Breakdown

| Provider | Configuration | ~1M requests/mo | ~10M requests/mo |
|----------|--------------|-----------------|------------------|
| **GCP Cloud Run** | 1 vCPU, 512MB | ~$10 | ~$50 |
| **AWS Lambda** | 512MB, API Gateway | ~$15 | ~$80 |
| **Cloudflare Workers** | Standard | ~$5 | ~$45 |

## Best Practices

### Use DataLoader for N+1

```typescript
// BAD - N+1 queries
const resolvers = {
  User: {
    posts: async (user) => {
      return prisma.post.findMany({ where: { authorId: user.id } });
    },
  },
};

// GOOD - Batched with DataLoader
const postsLoader = new DataLoader(async (authorIds: string[]) => {
  const posts = await prisma.post.findMany({
    where: { authorId: { in: authorIds } },
  });
  return authorIds.map((id) => posts.filter((p) => p.authorId === id));
});
```

### Query Complexity Limiting

```typescript
import { createComplexityLimitRule } from 'graphql-validation-complexity';

const complexityLimitRule = createComplexityLimitRule(1000, {
  onCost: (cost) => console.log('Query cost:', cost),
});

const server = new ApolloServer({
  typeDefs,
  resolvers,
  validationRules: [complexityLimitRule],
});
```

### Persisted Queries

```typescript
// Server
import { ApolloServerPluginPersistedQueries } from '@apollo/server/plugin/persistedQueries';

const server = new ApolloServer({
  plugins: [ApolloServerPluginPersistedQueries()],
});

// Client
import { createPersistedQueryLink } from '@apollo/client/link/persisted-queries';
import { sha256 } from 'crypto-hash';

const link = createPersistedQueryLink({ sha256 });
```

## Common Mistakes

1. **N+1 queries** - Not using DataLoader
2. **No query depth limiting** - DoS via deep queries
3. **No complexity limiting** - Expensive queries allowed
4. **Exposing internal errors** - Leaking implementation details
5. **Not using fragments** - Duplicated field selections
6. **Overfetching in resolvers** - Loading more data than needed
7. **No caching strategy** - Missing cache policies
8. **Synchronous DataLoader** - Blocking event loop
9. **Missing input validation** - Trusting client input
10. **No rate limiting** - Unlimited query execution

## Example Configuration

```yaml
# infera.yaml
project_name: graphql-api
provider: gcp
region: us-central1

api:
  type: graphql
  framework: apollo

  features:
    introspection: false  # Disable in production
    playground: false
    persisted_queries: true
    complexity_limit: 1000
    depth_limit: 10

services:
  api:
    runtime: cloud_run
    min_instances: 1

database:
  type: postgres_managed
  provider: cloud_sql

  connection:
    pool_size: 10

application:
  env:
    DATABASE_URL:
      from_secret: database-url
```

## Sources

- [Apollo Server Documentation](https://www.apollographql.com/docs/apollo-server/)
- [GraphQL Best Practices](https://graphql.org/learn/best-practices/)
- [DataLoader Documentation](https://github.com/graphql/dataloader)
- [Strawberry GraphQL](https://strawberry.rocks/docs)
- [GraphQL Code Generator](https://the-guild.dev/graphql/codegen)
