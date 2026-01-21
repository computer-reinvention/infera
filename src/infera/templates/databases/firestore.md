# Google Cloud Firestore

## Overview
Firestore is a flexible, scalable NoSQL document database with real-time synchronization and offline support. It's the default database for Firebase applications and integrates seamlessly with Google Cloud services.

**Use when:**
- Building mobile/web apps with real-time requirements
- Need offline-first capabilities
- Using Firebase ecosystem (Auth, Hosting, Functions)
- Simple document-based data model
- Need automatic scaling without ops

**Don't use when:**
- Complex relational queries needed
- High write throughput (>10K writes/sec per document)
- Need full SQL capabilities
- Data model is highly relational

## Detection Signals

```
Files:
- firebase.json, .firebaserc
- firestore.rules, firestore.indexes.json
- firebase-adminsdk-*.json

Dependencies:
- firebase, firebase-admin (Node.js)
- firebase-admin, google-cloud-firestore (Python)
- cloud.google.com/go/firestore (Go)

Code Patterns:
- initializeApp(), getFirestore()
- collection(), doc(), setDoc(), getDoc()
- onSnapshot() (real-time listeners)
- where(), orderBy(), limit()
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Firestore Architecture                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Client Applications                    │   │
│  │                                                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Web App │  │ iOS App │  │ Android │  │ Server  │     │   │
│  │  │ (JS)    │  │ (Swift) │  │ (Kotlin)│  │ (Admin) │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  │       │            │            │            │           │   │
│  │       │     Real-time sync      │            │           │   │
│  │       └────────────┴──────┬─────┴────────────┘           │   │
│  │                           │                              │   │
│  └───────────────────────────┼──────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    Firestore                               │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │                  Collection                          │  │  │
│  │  │                                                      │  │  │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │  │
│  │  │  │ Document 1 │  │ Document 2 │  │ Document N │    │  │  │
│  │  │  │            │  │            │  │            │    │  │  │
│  │  │  │ { fields } │  │ { fields } │  │ { fields } │    │  │  │
│  │  │  │            │  │            │  │            │    │  │  │
│  │  │  │ Subcol-    │  │ Subcol-    │  │            │    │  │  │
│  │  │  │ lections   │  │ lections   │  │            │    │  │  │
│  │  │  └────────────┘  └────────────┘  └────────────┘    │  │  │
│  │  │                                                      │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                                                            │  │
│  │  Features:                                                 │  │
│  │  • Real-time listeners                                    │  │
│  │  • Offline persistence                                    │  │
│  │  • Automatic multi-region replication                     │  │
│  │  • Security rules                                         │  │
│  │  • Composite indexes                                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Firebase Project Setup

### CLI Setup

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Initialize project
firebase init firestore

# This creates:
# - firebase.json
# - firestore.rules
# - firestore.indexes.json
```

### firebase.json

```json
{
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  },
  "emulators": {
    "firestore": {
      "port": 8080
    },
    "ui": {
      "enabled": true
    }
  }
}
```

### Security Rules

```javascript
// firestore.rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Users can only access their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;

      // User's private subcollections
      match /orders/{orderId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }
    }

    // Public read, authenticated write
    match /products/{productId} {
      allow read: if true;
      allow write: if request.auth != null && request.auth.token.admin == true;
    }

    // Posts with validation
    match /posts/{postId} {
      allow read: if true;
      allow create: if request.auth != null
        && request.resource.data.authorId == request.auth.uid
        && request.resource.data.title.size() <= 100
        && request.resource.data.content.size() <= 10000;
      allow update, delete: if request.auth != null
        && resource.data.authorId == request.auth.uid;
    }

    // Admin-only collection
    match /admin/{document=**} {
      allow read, write: if request.auth != null
        && request.auth.token.admin == true;
    }
  }
}
```

### Indexes

```json
// firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "posts",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "authorId", "order": "ASCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "orders",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

## Terraform Configuration

```hcl
# firestore.tf

resource "google_project_service" "firestore" {
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  # Point-in-time recovery (7-day window)
  point_in_time_recovery_enablement = var.environment == "production" ? "POINT_IN_TIME_RECOVERY_ENABLED" : "POINT_IN_TIME_RECOVERY_DISABLED"

  # Deletion protection
  delete_protection_state = var.environment == "production" ? "DELETE_PROTECTION_ENABLED" : "DELETE_PROTECTION_DISABLED"

  depends_on = [google_project_service.firestore]
}

# Composite indexes
resource "google_firestore_index" "posts_by_author" {
  project    = var.project_id
  database   = google_firestore_database.main.name
  collection = "posts"

  fields {
    field_path = "authorId"
    order      = "ASCENDING"
  }

  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.main]
}

resource "google_firestore_index" "orders_by_status" {
  project    = var.project_id
  database   = google_firestore_database.main.name
  collection = "orders"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "createdAt"
    order      = "DESCENDING"
  }
}

# Backup schedule (production)
resource "google_firestore_backup_schedule" "daily" {
  count = var.environment == "production" ? 1 : 0

  project  = var.project_id
  database = google_firestore_database.main.name

  retention = "604800s"  # 7 days

  daily_recurrence {}
}

# Variables
variable "firestore_location" {
  description = "Firestore location"
  type        = string
  default     = "us-central"  # Multi-region: nam5, eur3
}

# Outputs
output "database_name" {
  value = google_firestore_database.main.name
}
```

## Application Integration

### Web (JavaScript/TypeScript)

```typescript
// firebase.ts
import { initializeApp } from 'firebase/app';
import {
  getFirestore,
  collection,
  doc,
  getDoc,
  getDocs,
  setDoc,
  updateDoc,
  deleteDoc,
  query,
  where,
  orderBy,
  limit,
  onSnapshot,
  serverTimestamp,
  Timestamp,
  writeBatch,
  runTransaction,
} from 'firebase/firestore';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);

// Types
interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

interface Post {
  id: string;
  title: string;
  content: string;
  authorId: string;
  published: boolean;
  createdAt: Timestamp;
}

// CRUD operations
export async function getUser(userId: string): Promise<User | null> {
  const docRef = doc(db, 'users', userId);
  const docSnap = await getDoc(docRef);
  return docSnap.exists() ? { id: docSnap.id, ...docSnap.data() } as User : null;
}

export async function createUser(userId: string, data: Omit<User, 'id' | 'createdAt' | 'updatedAt'>): Promise<void> {
  const docRef = doc(db, 'users', userId);
  await setDoc(docRef, {
    ...data,
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  });
}

export async function updateUser(userId: string, data: Partial<User>): Promise<void> {
  const docRef = doc(db, 'users', userId);
  await updateDoc(docRef, {
    ...data,
    updatedAt: serverTimestamp(),
  });
}

// Queries
export async function getUserPosts(userId: string, maxResults = 20): Promise<Post[]> {
  const q = query(
    collection(db, 'posts'),
    where('authorId', '==', userId),
    where('published', '==', true),
    orderBy('createdAt', 'desc'),
    limit(maxResults)
  );

  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as Post));
}

// Real-time listener
export function subscribeToUserPosts(
  userId: string,
  callback: (posts: Post[]) => void
): () => void {
  const q = query(
    collection(db, 'posts'),
    where('authorId', '==', userId),
    orderBy('createdAt', 'desc'),
    limit(20)
  );

  return onSnapshot(q, (snapshot) => {
    const posts = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as Post));
    callback(posts);
  });
}

// Batch writes
export async function createPostsInBatch(posts: Omit<Post, 'id' | 'createdAt'>[]): Promise<void> {
  const batch = writeBatch(db);

  posts.forEach(post => {
    const docRef = doc(collection(db, 'posts'));
    batch.set(docRef, {
      ...post,
      createdAt: serverTimestamp(),
    });
  });

  await batch.commit();
}

// Transaction
export async function likePost(postId: string, userId: string): Promise<void> {
  const postRef = doc(db, 'posts', postId);
  const likeRef = doc(db, 'posts', postId, 'likes', userId);

  await runTransaction(db, async (transaction) => {
    const postDoc = await transaction.get(postRef);
    if (!postDoc.exists()) {
      throw new Error('Post not found');
    }

    const likeDoc = await transaction.get(likeRef);
    if (likeDoc.exists()) {
      throw new Error('Already liked');
    }

    const newLikeCount = (postDoc.data().likeCount || 0) + 1;
    transaction.update(postRef, { likeCount: newLikeCount });
    transaction.set(likeRef, { createdAt: serverTimestamp() });
  });
}
```

### Node.js (Admin SDK)

```typescript
// firestore-admin.ts
import { initializeApp, cert, ServiceAccount } from 'firebase-admin/app';
import { getFirestore, FieldValue, Timestamp } from 'firebase-admin/firestore';

// Initialize with service account
const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT!);

initializeApp({
  credential: cert(serviceAccount as ServiceAccount),
});

export const db = getFirestore();

// Server-side operations (bypasses security rules)
export async function createUserAdmin(userId: string, email: string, name: string) {
  await db.collection('users').doc(userId).set({
    email,
    name,
    createdAt: FieldValue.serverTimestamp(),
    updatedAt: FieldValue.serverTimestamp(),
  });
}

export async function getAllUsers(limitCount = 100) {
  const snapshot = await db.collection('users')
    .orderBy('createdAt', 'desc')
    .limit(limitCount)
    .get();

  return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
}

// Bulk operations with batched writes
export async function bulkUpdateUsers(updates: { id: string; data: any }[]) {
  const batches = [];
  let batch = db.batch();
  let operationCount = 0;

  for (const update of updates) {
    const ref = db.collection('users').doc(update.id);
    batch.update(ref, {
      ...update.data,
      updatedAt: FieldValue.serverTimestamp(),
    });
    operationCount++;

    // Firestore limit: 500 operations per batch
    if (operationCount === 500) {
      batches.push(batch.commit());
      batch = db.batch();
      operationCount = 0;
    }
  }

  if (operationCount > 0) {
    batches.push(batch.commit());
  }

  await Promise.all(batches);
}

// Collection group queries (query across subcollections)
export async function getAllOrdersByStatus(status: string) {
  const snapshot = await db.collectionGroup('orders')
    .where('status', '==', status)
    .orderBy('createdAt', 'desc')
    .get();

  return snapshot.docs.map(doc => ({
    id: doc.id,
    path: doc.ref.path,
    ...doc.data(),
  }));
}
```

### Python (Admin SDK)

```python
# firestore_admin.py
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter
import os

# Initialize
cred = credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
firebase_admin.initialize_app(cred)

db = firestore.client()


def create_user(user_id: str, email: str, name: str) -> dict:
    doc_ref = db.collection('users').document(user_id)
    data = {
        'email': email,
        'name': name,
        'createdAt': firestore.SERVER_TIMESTAMP,
        'updatedAt': firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(data)
    return {'id': user_id, **data}


def get_user(user_id: str) -> dict | None:
    doc_ref = db.collection('users').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        return {'id': doc.id, **doc.to_dict()}
    return None


def get_user_posts(user_id: str, limit_count: int = 20) -> list:
    posts_ref = db.collection('posts')
    query = posts_ref.where(
        filter=FieldFilter('authorId', '==', user_id)
    ).where(
        filter=FieldFilter('published', '==', True)
    ).order_by('createdAt', direction=firestore.Query.DESCENDING).limit(limit_count)

    return [{'id': doc.id, **doc.to_dict()} for doc in query.stream()]


# Real-time listener
def watch_collection(collection_name: str, callback):
    def on_snapshot(docs, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                callback('added', change.document.id, change.document.to_dict())
            elif change.type.name == 'MODIFIED':
                callback('modified', change.document.id, change.document.to_dict())
            elif change.type.name == 'REMOVED':
                callback('removed', change.document.id, None)

    return db.collection(collection_name).on_snapshot(on_snapshot)


# Transaction
@firestore.transactional
def transfer_credits(transaction, from_user_id: str, to_user_id: str, amount: int):
    from_ref = db.collection('users').document(from_user_id)
    to_ref = db.collection('users').document(to_user_id)

    from_doc = from_ref.get(transaction=transaction)
    to_doc = to_ref.get(transaction=transaction)

    if not from_doc.exists or not to_doc.exists:
        raise ValueError('User not found')

    from_credits = from_doc.get('credits') or 0
    if from_credits < amount:
        raise ValueError('Insufficient credits')

    transaction.update(from_ref, {'credits': from_credits - amount})
    transaction.update(to_ref, {'credits': (to_doc.get('credits') or 0) + amount})


def execute_transfer(from_user_id: str, to_user_id: str, amount: int):
    transaction = db.transaction()
    transfer_credits(transaction, from_user_id, to_user_id, amount)
```

### Go

```go
// firestore.go
package database

import (
    "context"
    "os"

    "cloud.google.com/go/firestore"
    "google.golang.org/api/iterator"
)

var client *firestore.Client

func Init(ctx context.Context) error {
    var err error
    projectID := os.Getenv("GOOGLE_CLOUD_PROJECT")
    client, err = firestore.NewClient(ctx, projectID)
    return err
}

func Close() error {
    if client != nil {
        return client.Close()
    }
    return nil
}

type User struct {
    ID        string `firestore:"-"`
    Email     string `firestore:"email"`
    Name      string `firestore:"name"`
    CreatedAt any    `firestore:"createdAt,serverTimestamp"`
    UpdatedAt any    `firestore:"updatedAt,serverTimestamp"`
}

func CreateUser(ctx context.Context, userID, email, name string) error {
    _, err := client.Collection("users").Doc(userID).Set(ctx, User{
        Email: email,
        Name:  name,
    })
    return err
}

func GetUser(ctx context.Context, userID string) (*User, error) {
    doc, err := client.Collection("users").Doc(userID).Get(ctx)
    if err != nil {
        return nil, err
    }

    var user User
    if err := doc.DataTo(&user); err != nil {
        return nil, err
    }
    user.ID = doc.Ref.ID
    return &user, nil
}

func GetUserPosts(ctx context.Context, userID string, limit int) ([]Post, error) {
    iter := client.Collection("posts").
        Where("authorId", "==", userID).
        Where("published", "==", true).
        OrderBy("createdAt", firestore.Desc).
        Limit(limit).
        Documents(ctx)

    var posts []Post
    for {
        doc, err := iter.Next()
        if err == iterator.Done {
            break
        }
        if err != nil {
            return nil, err
        }

        var post Post
        if err := doc.DataTo(&post); err != nil {
            return nil, err
        }
        post.ID = doc.Ref.ID
        posts = append(posts, post)
    }

    return posts, nil
}

// Transaction example
func LikePost(ctx context.Context, postID, userID string) error {
    return client.RunTransaction(ctx, func(ctx context.Context, tx *firestore.Transaction) error {
        postRef := client.Collection("posts").Doc(postID)
        likeRef := postRef.Collection("likes").Doc(userID)

        postDoc, err := tx.Get(postRef)
        if err != nil {
            return err
        }

        likeDoc, err := tx.Get(likeRef)
        if err == nil && likeDoc.Exists() {
            return errors.New("already liked")
        }

        likeCount, _ := postDoc.DataAt("likeCount")
        newCount := 1
        if count, ok := likeCount.(int64); ok {
            newCount = int(count) + 1
        }

        tx.Update(postRef, []firestore.Update{{Path: "likeCount", Value: newCount}})
        tx.Set(likeRef, map[string]any{"createdAt": firestore.ServerTimestamp})

        return nil
    })
}
```

## Cloud Functions Integration

```typescript
// functions/src/index.ts
import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';

admin.initializeApp();
const db = admin.firestore();

// Trigger on document create
export const onUserCreated = functions.firestore
  .document('users/{userId}')
  .onCreate(async (snap, context) => {
    const userId = context.params.userId;
    const userData = snap.data();

    // Send welcome email
    await sendWelcomeEmail(userData.email, userData.name);

    // Create default settings
    await db.collection('users').doc(userId).collection('settings').doc('preferences').set({
      notifications: true,
      theme: 'light',
    });
  });

// Trigger on document update
export const onOrderStatusChange = functions.firestore
  .document('users/{userId}/orders/{orderId}')
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after = change.after.data();

    if (before.status !== after.status) {
      // Send notification
      await sendOrderStatusNotification(
        context.params.userId,
        context.params.orderId,
        after.status
      );
    }
  });

// Scheduled function for cleanup
export const cleanupOldData = functions.pubsub
  .schedule('every 24 hours')
  .onRun(async () => {
    const thirtyDaysAgo = admin.firestore.Timestamp.fromDate(
      new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    );

    const oldDocs = await db.collection('logs')
      .where('createdAt', '<', thirtyDaysAgo)
      .limit(500)
      .get();

    const batch = db.batch();
    oldDocs.docs.forEach(doc => batch.delete(doc.ref));
    await batch.commit();
  });
```

## Data Modeling Patterns

### Subcollections vs Root Collections

```typescript
// Subcollections - for hierarchical data
// users/{userId}/orders/{orderId}
// Pros: Natural access patterns, automatic scoping
// Cons: Can't query across all users' orders easily

// Root collections with references
// users/{userId}
// orders/{orderId} with userId field
// Pros: Easier cross-user queries
// Cons: Manual relationship management
```

### Denormalization

```typescript
// Store frequently accessed data together
interface Post {
  id: string;
  title: string;
  content: string;
  authorId: string;
  // Denormalized author data
  author: {
    name: string;
    avatarUrl: string;
  };
  // Denormalized counts
  likeCount: number;
  commentCount: number;
}

// Update denormalized data when source changes
export const onUserProfileUpdate = functions.firestore
  .document('users/{userId}')
  .onUpdate(async (change, context) => {
    const { name, avatarUrl } = change.after.data();
    const userId = context.params.userId;

    // Update all posts by this user
    const posts = await db.collection('posts')
      .where('authorId', '==', userId)
      .get();

    const batch = db.batch();
    posts.docs.forEach(doc => {
      batch.update(doc.ref, {
        'author.name': name,
        'author.avatarUrl': avatarUrl,
      });
    });
    await batch.commit();
  });
```

## Cost Breakdown

### Firestore Pricing

| Operation | Free Tier | Cost After Free Tier |
|-----------|-----------|---------------------|
| Document Reads | 50K/day | $0.06 per 100K |
| Document Writes | 20K/day | $0.18 per 100K |
| Document Deletes | 20K/day | $0.02 per 100K |
| Storage | 1 GB | $0.18 per GB/month |
| Network Egress | 10 GB/month | $0.12 per GB |

### Cost Examples

| Workload | Reads/day | Writes/day | Storage | Monthly Cost |
|----------|-----------|------------|---------|--------------|
| Hobby | 50K | 20K | 1 GB | ~$0 (free tier) |
| Startup | 500K | 100K | 10 GB | ~$50 |
| Growth | 5M | 1M | 100 GB | ~$500 |
| Scale | 50M | 10M | 1 TB | ~$5,000 |

## Best Practices

### Efficient Queries

```typescript
// GOOD - Query with index
const posts = await db.collection('posts')
  .where('authorId', '==', userId)
  .where('published', '==', true)
  .orderBy('createdAt', 'desc')
  .limit(20)
  .get();

// BAD - Reading all documents then filtering
const allPosts = await db.collection('posts').get();
const filteredPosts = allPosts.docs.filter(doc =>
  doc.data().authorId === userId && doc.data().published
);
```

### Pagination

```typescript
// Cursor-based pagination
let query = db.collection('posts')
  .orderBy('createdAt', 'desc')
  .limit(20);

if (lastDoc) {
  query = query.startAfter(lastDoc);
}

const snapshot = await query.get();
const lastVisible = snapshot.docs[snapshot.docs.length - 1];
// Use lastVisible as cursor for next page
```

### Offline Support

```typescript
// Enable offline persistence (web)
import { enableIndexedDbPersistence } from 'firebase/firestore';

enableIndexedDbPersistence(db).catch((err) => {
  if (err.code === 'failed-precondition') {
    // Multiple tabs open
  } else if (err.code === 'unimplemented') {
    // Browser doesn't support
  }
});
```

## Common Mistakes

1. **Not creating composite indexes** - Queries fail without proper indexes
2. **Over-reading documents** - Each read costs; use queries wisely
3. **Large documents** - Keep documents under 1MB; use subcollections
4. **Missing security rules** - Default rules may be too permissive
5. **N+1 queries** - Batch reads instead of individual fetches
6. **Not using serverTimestamp** - Inconsistent timestamps across clients
7. **Ignoring offline behavior** - Handle offline state in UI
8. **Too deep nesting** - Max 100 levels; keep hierarchy shallow
9. **Not paginating** - Loading all documents at once
10. **Missing error handling** - Network and permission errors

## Example Configuration

```yaml
# infera.yaml
project_name: my-app
provider: gcp
environment: production

database:
  type: firestore
  location: nam5  # Multi-region

  indexes:
    - collection: posts
      fields:
        - { field: authorId, order: ASCENDING }
        - { field: createdAt, order: DESCENDING }

    - collection: orders
      fields:
        - { field: status, order: ASCENDING }
        - { field: createdAt, order: DESCENDING }

  backup:
    enabled: true
    retention_days: 7

  security:
    rules_file: firestore.rules

application:
  framework: nextjs
  hosting: firebase

  env:
    NEXT_PUBLIC_FIREBASE_PROJECT_ID: my-app
    NEXT_PUBLIC_FIREBASE_API_KEY:
      from_secret: firebase-api-key
```

## Sources

- [Firestore Documentation](https://firebase.google.com/docs/firestore)
- [Firestore Data Modeling](https://firebase.google.com/docs/firestore/data-model)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Firestore Pricing](https://firebase.google.com/pricing)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
