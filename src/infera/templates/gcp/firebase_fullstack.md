# GCP Firebase Full-Stack

## Overview

Deploy full-stack applications using the Firebase ecosystem with Hosting for frontend, Cloud Functions for backend, and Firestore for database. Ideal for real-time applications, mobile backends, and projects wanting a unified development experience.

## Detection Signals

Use this template when:
- `firebase.json` configuration file present
- Firebase SDK imports in code
- `firestore.rules` or `firestore.indexes.json`
- Cloud Functions in `functions/` directory
- Real-time data requirements
- Authentication needs

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │           Firebase Platform              │
    Internet ──────────►│  ┌─────────────────────────────────────┐ │
         │             │  │       Firebase Hosting               │ │
    Global CDN         │  │       (Static + SSR)                 │ │
                        │  └───────────────┬─────────────────────┘ │
                        │                  │                       │
                        │  ┌───────────────┼───────────────────┐   │
                        │  │               ▼                   │   │
                        │  │    Cloud Functions (2nd gen)      │   │
                        │  │    - API endpoints                │   │
                        │  │    - Background triggers          │   │
                        │  │    - Authentication triggers      │   │
                        │  └───────────────┬───────────────────┘   │
                        │                  │                       │
                        │  ┌───────────────┼───────────────────┐   │
                        │  ▼               ▼                   ▼   │
                        │ Firestore    Cloud Storage    Authentication│
                        │ (Database)   (Files)          (Users)    │
                        └─────────────────────────────────────────┘
```

## Resources

### Required
| Resource | Purpose | Service |
|----------|---------|---------|
| Firebase Hosting | Frontend hosting | Firebase Hosting |
| Cloud Functions | Backend logic | Cloud Functions (2nd gen) |
| Firestore | Database | Firestore |

### Optional
| Resource | When to Add | Service |
|----------|-------------|---------|
| Firebase Auth | User authentication | Firebase Authentication |
| Cloud Storage | File uploads | Cloud Storage for Firebase |
| Realtime Database | Real-time sync | Firebase Realtime Database |
| Firebase Extensions | Pre-built features | Various |

## Configuration

### firebase.json
```json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "/api/**",
        "function": "api"
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(js|css)",
        "headers": [
          {
            "key": "Cache-Control",
            "value": "public, max-age=31536000, immutable"
          }
        ]
      }
    ]
  },
  "functions": {
    "source": "functions",
    "runtime": "nodejs20",
    "predeploy": ["npm --prefix functions run build"]
  },
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  },
  "storage": {
    "rules": "storage.rules"
  }
}
```

### firestore.rules
```
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {
    // Users can read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }

    // Public read, authenticated write
    match /posts/{postId} {
      allow read: if true;
      allow create: if request.auth != null;
      allow update, delete: if request.auth != null &&
        request.auth.uid == resource.data.authorId;
    }

    // Admin-only access
    match /admin/{document=**} {
      allow read, write: if request.auth.token.admin == true;
    }
  }
}
```

### Terraform Resources
```hcl
# Firebase Project
resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id
}

# Firestore Database
resource "google_firestore_database" "default" {
  provider    = google-beta
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_firebase_project.default]
}

# Firebase Hosting Site
resource "google_firebase_hosting_site" "default" {
  provider = google-beta
  project  = var.project_id
  site_id  = var.project_id
}

# Cloud Storage Bucket
resource "google_storage_bucket" "firebase_storage" {
  name     = "${var.project_id}.appspot.com"
  location = "US"

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "POST", "PUT", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Cloud Functions (2nd gen)
resource "google_cloudfunctions2_function" "api" {
  name     = "api"
  location = var.region

  build_config {
    runtime     = "nodejs20"
    entry_point = "api"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    max_instance_count = 100
    available_memory   = "512M"
    timeout_seconds    = 60

    environment_variables = {
      PROJECT_ID = var.project_id
    }
  }
}
```

## Cloud Functions Implementation

### API Function (TypeScript)
```typescript
// functions/src/index.ts
import * as functions from 'firebase-functions/v2';
import * as admin from 'firebase-admin';
import express from 'express';
import cors from 'cors';

admin.initializeApp();
const db = admin.firestore();

const app = express();
app.use(cors({ origin: true }));
app.use(express.json());

// Middleware to verify auth
const authenticate = async (req: any, res: any, next: any) => {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  try {
    const token = authHeader.split('Bearer ')[1];
    const decodedToken = await admin.auth().verifyIdToken(token);
    req.user = decodedToken;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Invalid token' });
  }
};

// Public endpoint
app.get('/api/posts', async (req, res) => {
  const snapshot = await db.collection('posts')
    .orderBy('createdAt', 'desc')
    .limit(20)
    .get();

  const posts = snapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data()
  }));

  res.json(posts);
});

// Protected endpoint
app.post('/api/posts', authenticate, async (req, res) => {
  const { title, content } = req.body;

  const post = await db.collection('posts').add({
    title,
    content,
    authorId: req.user.uid,
    createdAt: admin.firestore.FieldValue.serverTimestamp()
  });

  res.status(201).json({ id: post.id });
});

// Export as Firebase Function
export const api = functions.https.onRequest(app);

// Firestore trigger
export const onUserCreate = functions.firestore
  .onDocumentCreated('users/{userId}', async (event) => {
    const userData = event.data?.data();
    const userId = event.params.userId;

    // Send welcome email, create default data, etc.
    await db.collection('userProfiles').doc(userId).set({
      displayName: userData?.displayName || 'New User',
      createdAt: admin.firestore.FieldValue.serverTimestamp()
    });
  });
```

### Frontend Integration (React)
```typescript
// src/firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: `${import.meta.env.VITE_PROJECT_ID}.firebaseapp.com`,
  projectId: import.meta.env.VITE_PROJECT_ID,
  storageBucket: `${import.meta.env.VITE_PROJECT_ID}.appspot.com`,
  messagingSenderId: import.meta.env.VITE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_APP_ID
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
```

## Deployment Commands

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login
firebase login

# Initialize project
firebase init

# Build frontend
npm run build

# Deploy everything
firebase deploy

# Deploy specific services
firebase deploy --only hosting
firebase deploy --only functions
firebase deploy --only firestore:rules

# Emulate locally
firebase emulators:start

# View logs
firebase functions:log
```

## Best Practices

### Firestore
1. Design documents for query patterns
2. Use composite indexes for complex queries
3. Implement pagination with cursors
4. Denormalize data for read performance

### Cloud Functions
1. Keep functions small and focused
2. Use 2nd gen functions for better performance
3. Initialize Firebase Admin outside handlers
4. Handle errors gracefully

### Security
1. Write comprehensive security rules
2. Validate data on both client and server
3. Use Firebase App Check
4. Never expose API keys in client code

## Cost Breakdown

| Component | Free Tier | Paid |
|-----------|-----------|------|
| Hosting | 10 GB storage, 360 MB/day transfer | $0.026/GB |
| Functions | 2M invocations | $0.40/million |
| Firestore reads | 50k/day | $0.06/100k |
| Firestore writes | 20k/day | $0.18/100k |
| Storage | 5 GB | $0.026/GB |
| Auth | 10k/month | $0.0055/user |

### Example Monthly Costs
| Scale | Cost |
|-------|------|
| Small (under free tier) | $0 |
| Medium (100k users) | $50-100 |
| Large (1M users) | $500-1000 |

## Common Mistakes

1. **Not indexing Firestore**: Queries fail without proper indexes
2. **Fetching too much data**: Not using pagination
3. **Weak security rules**: Open database access
4. **Cold starts**: Not handling function initialization
5. **No offline support**: Not enabling Firestore persistence
6. **Blocking reads**: Not using real-time listeners when appropriate

## Example Configuration

```yaml
project_name: my-firebase-app
provider: gcp
region: us-central1
architecture_type: firebase_fullstack

resources:
  - id: firestore
    type: firestore
    name: default
    provider: gcp
    config:
      location: us-central1
      type: FIRESTORE_NATIVE

  - id: hosting
    type: firebase_hosting
    name: my-firebase-app
    provider: gcp
    config:
      public: dist
      rewrites:
        - source: "/api/**"
          function: api
        - source: "**"
          destination: "/index.html"

  - id: api-function
    type: cloud_function
    name: api
    provider: gcp
    config:
      runtime: nodejs20
      entry_point: api
      memory: 512M
      max_instances: 100
    depends_on:
      - firestore

  - id: storage
    type: firebase_storage
    name: default
    provider: gcp
    config:
      location: US
```

## Sources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
- [Firebase Pricing](https://firebase.google.com/pricing)
