# BAB 09 / MODULE 01: Distributed GraphQL: Apollo Federation & Schema Stitching

---

## 01: Identitas Modul

* **Track:** Backend and Database Engineering
* **Course:** Distributed GraphQL Architecture
* **Module Identifier:** `04-BED-GQL-09-01`
* **Prerequisites:** 
  * Advanced GraphQL Schema Definition Language (SDL) & Execution Engine Mechanics
  * Microservices Pattern (API Gateway, Event-Driven Architecture, gRPC)
  * TypeScript 5.x & Node.js Runtime Internals
  * Concurrency & Async Processing Models
* **Estimated Completion Time:** 180 Menit (Intensive Technical Deep-Dive & Lab)

---

## 02: Learning Objectives

1. **Menganalisis Arsitektur GraphQL Terdistribusi:** Membedakan fondasi matematis dan mekanisme eksekusi antara declarative entity composition (Apollo Federation v2) dan programmatic schema manipulation (Schema Stitching).
2. **Merancang Komposisi Schema Terfederasi:** Mengimplementasikan direktif Apollo Federation (`@key`, `@shareable`, `@external`, `@provides`, `@requires`, `@override`) untuk dekomposisi monolit GraphQL ke dalam arsitektur decoupled subgraphs.
3. **Membangun Resilient Federation Router:** Mengonfigurasi engine kompilasi *Query Plan*, caching token metadata, serta distributed context propagation untuk mencegah security leak dan degradasi performa (N+1 cross-network latency).
4. **Mengimplementasikan Advanced Schema Stitching:** Mengembangkan gateway stitching dinamis menggunakan batching executor, remote schema transform, type merging, dan custom delegation resolvers.
5. **Menjamin Keandalan & Keamanan Produksi:** Menerapkan schema governance, distributed tracing context injection, continuous schema composition pipelines (CI/CD check), depth/complexity limiting, serta circuit breaking.

---

## 03: Concept Map Diagram (ASCII)

```
========================================================================================
                      DISTRIBUTED GRAPHQL ARCHITECTURE TAXONOMY
========================================================================================

                                  [ GraphQL Client ]
                                          │
                                          │ (Single Unified Query)
                                          ▼
                      ┌─────────────────────────────────────────┐
                      │      API GATEWAY / FEDERATION ROUTER    │
                      │  (Schema Engine, Planner, Auth, Cache)  │
                      └────────────────────┬────────────────────┘
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         │ Query Planning Pipeline:                                          │
         │ 1. Parse & Validate -> 2. Query Split -> 3. Parallel/Seq Fetch    │
         └─────────────────────────────────┬─────────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
  ┌───────────────────────────────────┐         ┌───────────────────────────────────┐
  │   APOLLO FEDERATION v2 (ROUTER)   │         │     SCHEMA STITCHING GATEWAY      │
  ├───────────────────────────────────┤         ├───────────────────────────────────┤
  │ Model: Declarative Subgraphs      │         │ Model: Programmatic Delegation    │
  │ Resolusi: Entity Reference Batch  │         │ Resolusi: Remote Schema Delegate  │
  │ Contract: Federated Directives    │         │ Contract: Merged Type Resolvers   │
  │ Engine: Supergraph Composition    │         │ Engine: Dynamic Schema Merging    │
  └─────────────────┬─────────────────┘         └─────────────────┬─────────────────┘
                    │                                             │
      ┌─────────────┴─────────────┐                 ┌─────────────┴─────────────┐
      ▼                           ▼                 ▼                           ▼
┌───────────────┐           ┌───────────────┐ ┌───────────────┐           ┌───────────────┐
│ Subgraph A:   │           │ Subgraph B:   │ │ Microservice  │           │ Microservice  │
│ Users Engine  │           │ Products & Rev│ │ REST / GQL A  │           │ REST / GQL B  │
│ Entity: User  │           │ Extends User  │ │ Transform GQL │           │ Delegate Call │
│ Key: id       │           │ Entity: Prod  │ │ Type Merging  │           │ Raw Fetcher   │
└───────────────┘           └───────────────┘ └───────────────┘           └───────────────┘
========================================================================================
```

---

## 04: Mengapa Relevan

Dalam arsitektur monolit GraphQL, satu schema tunggal yang dikelola oleh puluhan tim akan memunculkan *bottleneck* koordinasi: *merge conflict* skema yang konstan, runtime error deployment tunggal yang merusak keseluruhan API surface, dan boundary domain (Bounded Contexts) yang kabur. 

Pemisahan microservices independen membutuhkan teknik *aggregation layer*. Schema Stitching dan Apollo Federation hadir menyelesaikan problem ini:

* **Sistem Skala Enterprise:** Organisasi seperti Netflix, Wayfair, dan Expedia mengorkestrasi ribuan resolver melalui puluhan subgraph terisolasi yang di-deploy independen tanpa sinkronisasi rilis global.
* **Performa & Zero-Downtime:** Federation mengompilasi representasi supergraph secara *static/offline*, menghasilkan *Query Plan Deterministic* yang mengurangi beban komputasi gateway dibanding dynamic runtime introspection stitching tradisional.
* **Evolusi Arsitektur Bertahap:** Memungkinkan migrasi bertahap (*strangler fig pattern*) dari REST/Monolith GraphQL menuju microservices modular dengan schema federation contracts.

---

## 05: Anatomi Konsep Inti

### 1. Apollo Federation v2 Core Directives

* `@key(fields: "id [otherField]")`: Menandai tipe objek sebagai **Federated Entity**. Menentukan boundary identitas entitas agar dapat di-resolve atau diperluas oleh subgraph lain melalui batched query `_entities(representations: [...])`.
* `@shareable`: Menginstruksikan router bahwa sebuah field dapat di-resolve secara valid oleh lebih dari satu subgraph tanpa menimbulkan skema overlap conflict.
* `@external`: Digunakan pada subgraph yang memperluas entitas untuk mereferensikan field yang dimiliki dan di-resolve oleh subgraph asal (originating subgraph).
* `@requires(fields: "fieldA fieldB")`: Menandai field komputasi lokal yang membutuhkan router untuk mengambil dependencies field `@external` terlebih dahulu dari subgraph lain.
* `@provides(fields: "fieldA")`: Mengoptimalkan query plan dengan memberi sinyal bahwa resolver lokal mampu menyuplai field milik subgraph lain pada nesting tertentu tanpa perlu hop jaringan tambahan.
* `@override(from: "subgraphName")`: Mekanisme migrasi zero-downtime untuk memindahkan kepemilikan resolver field dari subgraph lama ke subgraph baru.

### 2. Schema Stitching Fundamentals

* **Remote Schema Delegation:** Mekanisme forward sub-query dari gateway ke downstream service menggunakan resolver delegation function (`delegateToSchema`).
* **Type Merging:** Menggabungkan tipe dengan nama identik dari dua skema terpisah menggunakan konfigurasi key selector dan field query merger.
* **Schema Transforms:** Manipulasi AST skema runtime (misal: `RenameTypes`, `FilterRootFields`, `TransformQuery`) untuk membungkus internal microservice API menjadi interface public yang terstandarisasi.

### 3. Query Plan Execution Engine

Query Plan adalah *Directed Acyclic Graph* (DAG) yang dihasilkan router/gateway saat client query masuk. Engine menganalisis dependensi field dan membagi eksekusi menjadi tiga fase:
1. **Parallel Initial Fetch:** Mengambil primary data dari subgraph root (Query root level).
2. **Entity Batch Resolution (Cross-service Hop):** Router mengekstrak *entity keys* dari respon fase 1, lalu mengirim query `_entities` dengan payload array ID (Batched Representations) ke subgraph ekstensi.
3. **Response Stitching & Shaping:** Menggabungkan subtree JSON dari berbagai network call menjadi satu struktur JSON utuh sesuai format query klien asli.

---

## 06: Panduan Implementasi Step-by-Step

Implementasi sistem federasi modern membutuhkan orkestrasi multi-service:

```
[Step 1: Setup Workspace & Shared Contracts]
       │
[Step 2: Implement Base Subgraph (Users Subgraph)]
       │
[Step 3: Implement Dependent Subgraph (Reviews/Products)]
       │
[Step 4: Compose Supergraph via Rover CLI / Apollo Composition Engine]
       │
[Step 5: Configure Production-Grade Gateway Router]
       │
[Step 6: Setup Schema Stitching Fallback (Hybrid Edge Routing)]
```

### Langkah 1: Setup Workspace Node.js

```bash
mkdir distributed-graphql && cd distributed-graphql
npm init -y
npm install @apollo/server @apollo/subgraph @apollo/gateway @graphql-tools/schema @graphql-tools/stitch @graphql-tools/batch-delegate graphql express dotenv
npm install -D typescript @types/node @types/express ts-node
npx tsc --init
```

---

## 07: Contoh Kasus Sederhana (Mental Model)

Bayangkan sistem E-Commerce: Service **Accounts** mengelola data otentikasi `User`, sedangkan Service **Inventory** mengelola stok `Product` dan riwayat order `User`.

```graphql
# --- Accounts Subgraph ---
type User @key(fields: "id") {
  id: ID!
  email: String!
  name: String!
}

# --- Inventory Subgraph ---
type User @key(fields: "id") {
  id: ID!
  orderCount: Int! # Field ditambahkan ke tipe User tanpa menyentuh Accounts Subgraph
}
```

Router menerima:
```graphql
query GetUserProfile {
  user(id: "usr_101") {
    name       # Resolved oleh Accounts
    orderCount # Resolved oleh Inventory
  }
}
```

Router otomatis menjalankan:
1. `Accounts.user(id: "usr_101") -> { id: "usr_101", name: "Alice" }`
2. Ekstrak `id: "usr_101"`, kirim batch entity query ke `Inventory._entities(representations: [{ __typename: "User", id: "usr_101" }]) -> { orderCount: 42 }`
3. Gateway menggabungkan payload: `{ data: { user: { name: "Alice", orderCount: 42 } } }`.

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut implementasi lengkap 3 modul: **Sub-graph Users**, **Sub-graph Reviews (Federation v2)**, dan **Apollo Supergraph Gateway**.

### File Structure
```
├── supergraph.ts
├── subgraphs/
│   ├── users.ts
│   └── reviews.ts
└── tsconfig.json
```

### 1. Subgraph Users (`subgraphs/users.ts`)
```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';
import express from 'express';
import http from 'http';

const typeDefs = gql`
  extend schema
    @link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key", "@shareable"])

  type Query {
    users: [User!]!
    user(id: ID!): User
  }

  type User @key(fields: "id") {
    id: ID!
    username: String!
    email: String!
  }
`;

interface UserDb {
  id: string;
  username: string;
  email: string;
}

const USERS_DB: UserDb[] = [
  { id: 'u1', username: 'johndoe', email: 'john@enterprise.com' },
  { id: 'u2', username: 'janedoe', email: 'jane@enterprise.com' },
];

const resolvers = {
  Query: {
    users: (): UserDb[] => USERS_DB,
    user: (_: unknown, args: { id: string }): UserDb | undefined =>
      USERS_DB.find((u) => u.id === args.id),
  },
  User: {
    __resolveReference(userRef: { id: string }): UserDb | undefined {
      // Entity Reference Resolver invoked by the Router during Query Planning
      return USERS_DB.find((u) => u.id === userRef.id);
    },
  },
};

export async function startUsersSubgraph(port: number = 4001): Promise<void> {
  const app = express();
  const httpServer = http.createServer(app);

  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });

  await server.start();
  app.use(express.json());
  app.use('/graphql', expressMiddleware(server));

  await new Promise<void>((resolve) => httpServer.listen({ port }, resolve));
  console.log(`🚀 [Subgraph Users] ready at http://localhost:${port}/graphql`);
}

if (require.main === module) {
  startUsersSubgraph();
}
```

### 2. Subgraph Reviews (`subgraphs/reviews.ts`)
```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';
import express from 'express';
import http from 'http';

const typeDefs = gql`
  extend schema
    @link(
      url: "https://specs.apollo.dev/federation/v2.0"
      import: ["@key", "@shareable", "@external", "@requires", "@provides"]
    )

  type Review {
    id: ID!
    body: String!
    rating: Int!
    author: User!
  }

  type User @key(fields: "id") {
    id: ID!
    reviews: [Review!]!
    totalReviewsCount: Int!
  }

  type Query {
    reviews: [Review!]!
  }
`;

interface ReviewDb {
  id: string;
  authorId: string;
  body: string;
  rating: number;
}

const REVIEWS_DB: ReviewDb[] = [
  { id: 'rev-101', authorId: 'u1', body: 'Layanan handal!', rating: 5 },
  { id: 'rev-102', authorId: 'u1', body: 'Deployment cepat.', rating: 4 },
  { id: 'rev-103', authorId: 'u2', body: 'Arsitektur solid.', rating: 5 },
];

const resolvers = {
  Query: {
    reviews: (): ReviewDb[] => REVIEWS_DB,
  },
  User: {
    reviews(user: { id: string }): ReviewDb[] {
      return REVIEWS_DB.filter((r) => r.authorId === user.id);
    },
    totalReviewsCount(user: { id: string }): number {
      return REVIEWS_DB.filter((r) => r.authorId === user.id).length;
    },
    __resolveReference(ref: { id: string }): { id: string } {
      // Stub reference resolution
      return { id: ref.id };
    },
  },
  Review: {
    author(review: ReviewDb): { __typename: string; id: string } {
      return { __typename: 'User', id: review.authorId };
    },
  },
};

export async function startReviewsSubgraph(port: number = 4002): Promise<void> {
  const app = express();
  const httpServer = http.createServer(app);

  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });

  await server.start();
  app.use(express.json());
  app.use('/graphql', expressMiddleware(server));

  await new Promise<void>((resolve) => httpServer.listen({ port }, resolve));
  console.log(`🚀 [Subgraph Reviews] ready at http://localhost:${port}/graphql`);
}

if (require.main === module) {
  startReviewsSubgraph();
}
```

### 3. Production Gateway Engine (`supergraph.ts`)
```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { ApolloGateway, IntrospectAndCompose, RemoteGraphQLDataSource } from '@apollo/gateway';
import express, { Request } from 'express';
import http from 'http';
import { startUsersSubgraph } from './subgraphs/users';
import { startReviewsSubgraph } from './subgraphs/reviews';

interface AuthenticatedContext {
  token?: string;
  clientId?: string;
}

class AuthenticatedDataSource extends RemoteGraphQLDataSource {
  override willSendRequest({ request, context }: { request: any; context: AuthenticatedContext }) {
    if (context.token) {
      request.http.headers.set('Authorization', context.token);
    }
    if (context.clientId) {
      request.http.headers.set('X-Client-Id', context.clientId);
    }
  }
}

async function bootstrapDistributedEngine(): Promise<void> {
  // 1. Jalankan Subgraphs
  await startUsersSubgraph(4001);
  await startReviewsSubgraph(4002);

  // 2. Inisialisasi Apollo Gateway dengan Dynamic Composition
  const gateway = new ApolloGateway({
    supergraphSdl: new IntrospectAndCompose({
      subgraphs: [
        { name: 'users', url: 'http://localhost:4001/graphql' },
        { name: 'reviews', url: 'http://localhost:4002/graphql' },
      ],
      pollIntervalInMs: 10000, // Cek schema updates setiap 10 detik
    }),
    buildService({ url }) {
      return new AuthenticatedDataSource({ url });
    },
  });

  const app = express();
  const httpServer = http.createServer(app);

  const server = new ApolloServer<AuthenticatedContext>({
    gateway,
  });

  await server.start();

  app.use(express.json());
  app.use(
    '/graphql',
    expressMiddleware(server, {
      context: async ({ req }: { req: Request }): Promise<AuthenticatedContext> => {
        const authHeader = req.headers.authorization || '';
        const clientId = (req.headers['x-client-id'] as string) || 'anonymous-client';
        return {
          token: authHeader,
          clientId,
        };
      },
    })
  );

  const PORT = 4000;
  await new Promise<void>((resolve) => httpServer.listen({ port: PORT }, resolve));
  console.log(`🎯 [Federation Supergraph Router] fully operational at http://localhost:${PORT}/graphql`);
}

bootstrapDistributedEngine().catch((err) => {
  console.error('Fatal bootstrapping error:', err);
  process.exit(1);
});
```

---

## 09: Diagram Alur Kerja Eksekusi Query Plan (ASCII)

```
========================================================================================
                     QUERY EXECUTION PLAN: FEDERATED RESOLUTION
========================================================================================

Client Query:
  query GetUserData {
    user(id: "u1") {
      username
      reviews {
        body
        rating
      }
    }
  }

                                  ┌──────────────┐
                                  │ Client Query │
                                  └──────┬───────┘
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    Apollo Gateway / Router Engine     │
                      │  Generates Execution DAG Query Plan   │
                      └──────────────────┬────────────────────┘
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               │ [Step 1: Fetch Primary Entity Fields]             │
               │ Target: Subgraph Users                            │
               │ Payload: { user(id: "u1") { id username } }       │
               └─────────────────────────┬─────────────────────────┘
                                         ▼
                              ┌────────────────────┐
                              │ Subgraph Users     │
                              │ Returns:           │
                              │ { id, username }   │
                              └──────────┬─────────┘
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               │ [Step 2: Batch Entity Resolution]                 │
               │ Target: Subgraph Reviews                          │
               │ Payload: _entities(representations: [{            │
               │            __typename: "User", id: "u1"           │
               │          }]) { ... on User { reviews } }          │
               └─────────────────────────┬─────────────────────────┘
                                         ▼
                              ┌────────────────────┐
                              │ Subgraph Reviews   │
                              │ Returns:           │
                              │ { reviews: [...] } │
                              └──────────┬─────────┘
                                         │
                      ┌──────────────────┴────────────────────┐
                      │ Gateway Merging Engine                │
                      │ Resolves combined response JSON       │
                      └──────────────────┬────────────────────┘
                                         ▼
                               ┌───────────────────┐
                               │ Unified Response  │
                               │ Sent to Client    │
                               └───────────────────┘
========================================================================================
```

---

## 10: Analisis Komparasi Trade-Offs

| Dimensi Arsitektural | Apollo Federation v2 | Schema Stitching (GraphQL Tools) |
| :--- | :--- | :--- |
| **Model Paradigma** | Declarative Entity Contracts via Schema Directives | Programmatic Execution & Transform Layer |
| **Composition Phase** | Build-time (Supergraph SDL Compilation via Rover) | Runtime / Dynamic Gateway In-memory Stitch |
| **Query Planning Cost** | Sangat Rendah (Kompilasi statis & optimasi Rust engine) | Sedang - Tinggi (Dynamic delegated executions) |
| **Integrasi REST/Legacy**| Memerlukan Apollo Subgraph Wrapper | Native schema wrapping & dynamic transforms |
| **Developer Autonomy** | Sangat Tinggi (Kontrak schema terisolasi per domain) | Rentan dependency lock-in jika gateway menumpuk resolver |
| **Ecosystem Tooling** | Apollo Studio, Rover CLI, Router (Rust-based) | GraphQL Tools, Envelop, Hive |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Keep Subgraph Entities Lean:** Definisikan kunci entitas (`@key`) seringkas mungkin (gunakan Immutable Primary Key seperti UUID/ULID).
* **Enforce CI/CD Schema Validation:** Validasi integritas Supergraph sebelum deployment menggunakan Rover CLI (`rover subgraph check`).
* **Implement Batching Entity Resolvers:** Gunakan caching DataLoader pada level Subgraph `__resolveReference` untuk menghindari N+1 query lokal ke database.
* **Propagate Distributed Contexts:** Teruskan trace context (`traceparent`), request ID, dan authorization token dari Gateway ke semua downstream subgraphs.

### Antipatterns
* **Circular Subgraph Dependencies:** Subgraph A membutuhkan data dari Subgraph B yang juga me-resolve field yang membutuhkan entity kembali ke Subgraph A di nesting yang sama (memicu Network Waterfalling).
* **Stitching Logic Overload pada Gateway:** Menulis *business validation* atau direct database querying di dalam Gateway layer (melanggar separation of concerns).
* **Overusing `@shareable`:** Mengabaikan batasan bounded context dengan menandai semua field sebagai `@shareable` untuk menghindari error komposisi secara instan.

---

## 12: Security Hardening

Dalam sistem GraphQL terdistribusi, celah keamanan pada satu subgraph dapat membahayakan keseluruhan Supergraph.

```typescript
// Production Hardening Hook: Complexity & Depth Limiter pada Gateway
import { ApolloServerPlugin } from '@apollo/server';
import { GraphQLError } from 'graphql';

export const SecurityPolicyPlugin: ApolloServerPlugin = {
  async requestDidStart() {
    return {
      async didResolveOperation({ request, document }) {
        // 1. Enforce Max Query Depth Check
        const maxDepth = 6;
        const depth = calculateQueryDepth(document);
        if (depth > maxDepth) {
          throw new GraphQLError(`Security Violation: Query depth limit of ${maxDepth} exceeded. Received: ${depth}`, {
            extensions: { code: 'BAD_REQUEST_DEPTH_EXCEEDED' },
          });
        }

        // 2. Block Introspection in Production
        if (process.env.NODE_ENV === 'production' && request.operationName === 'IntrospectionQuery') {
          throw new GraphQLError('GraphQL introspection is disabled in production.', {
            extensions: { code: 'FORBIDDEN_INTROSPECTION' },
          });
        }
      },
    };
  },
};

function calculateQueryDepth(node: any, currentDepth = 0): number {
  if (!node || !node.selectionSet) return currentDepth;
  let max = currentDepth;
  for (const selection of node.selectionSet.selections) {
    if (selection.selectionSet) {
      const d = calculateQueryDepth(selection, currentDepth + 1);
      if (d > max) max = d;
    }
  }
  return max;
}
```

Downstream Subgraph harus memblokir akses langsung dari public internet:
1. **Network Layer Isolation:** Letakkan Subgraph di private VPC/Subnet; gateway berada di DMZ.
2. **Mutual TLS (mTLS) / Shared Secret:** Validasi shared HMAC token atau signed JWT pada downstream microservice untuk memastikan request hanya berasal dari Supergraph Router.

---

## 13: Observabilitas & Debugging

Gunakan OpenTelemetry (OTel) context injection untuk mendistribusikan trace IDs dari client -> Gateway -> Subgraphs.

```typescript
import { trace, context, SpanStatusCode } from '@opentelemetry/api';

// Middleware tracing pada Gateway RemoteGraphQLDataSource
class TracedGraphQLDataSource extends RemoteGraphQLDataSource {
  override willSendRequest({ request }: { request: any }) {
    const activeSpan = trace.getActiveSpan();
    if (activeSpan) {
      const traceContext = {};
      // Inject traceparent W3C header
      trace.getTracer('gateway-tracer').startActiveSpan('subgraph-fetch', (span) => {
        request.http.headers.set('traceparent', `00-${span.spanContext().traceId}-${span.spanContext().spanId}-01`);
        span.end();
      });
    }
  }

  override didReceiveResponse({ response }: { response: any }) {
    if (response.errors && response.errors.length > 0) {
      const activeSpan = trace.getActiveSpan();
      activeSpan?.setStatus({
        code: SpanStatusCode.ERROR,
        message: 'Subgraph returned GraphQL execution errors.',
      });
    }
    return response;
  }
}
```

---

## 14: Benchmarking & Performance

Optimasi performa Gateway berfokus pada latensi network waterfall dan serialization overhead.

### Benchmark Setup

Uji throughput menggunakan `k6` terhadap federated query 2-hops:

```javascript
// k6-loadtest.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 100,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<150'], // 95% request harus selesai di bawah 150ms
  },
};

const QUERY = JSON.stringify({
  query: `
    query BenchmarkTest {
      users {
        id
        username
        reviews {
          id
          rating
        }
      }
    }
  `,
});

export default function () {
  const params = {
    headers: { 'Content-Type': 'application/json' },
  };
  const res = http.post('http://localhost:4000/graphql', QUERY, params);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has no errors': (r) => !JSON.parse(r.body).errors,
  });
  sleep(0.05);
}
```

### Strategi Optimasi
* **Sub-graph DataLoader (Batching):** Pastikan resolver `__resolveReference` memanfaatkan DataLoader untuk menggabungkan N pemanggilan entitas ke database menjadi satu `SELECT * FROM tbl WHERE id IN (...)`.
* **Apollo Router (Rust Architecture):** Pada beban di atas 10.000 RPS, gantikan Node.js `@apollo/gateway` dengan binary Apollo Router (ditulis dalam Rust) untuk mengurangi latensi engine parsing hingga 80% dan mengeliminasi V8 garbage collection pause.

---

## 15: Hands-on Lab Mini-Project

### Skenario: Implementasi Subgraph Products & Cross-Service Requirement
Bangun Subgraph **Products** dan modifikasi **Reviews Subgraph** untuk menghitung rata-rata rating review per produk secara terdistribusi.

#### Requirements
1. Buat file `subgraphs/products.ts` port 4003:
   * Entity `Product` dengan key `id`. Field: `id`, `name`, `priceInCents`.
2. Update `subgraphs/reviews.ts`:
   * Tambahkan entitas ekstensi `Product` dengan `@key(fields: "id")`.
   * Berikan field `reviews: [Review!]!` dan `averageRating: Float!` pada ekstensi `Product`.
3. Daftarkan subgraph baru ke file gateway `supergraph.ts`.

#### Solusi Subgraph Products (`subgraphs/products.ts`)

```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';
import express from 'express';
import http from 'http';

const typeDefs = gql`
  extend schema
    @link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key", "@shareable"])

  type Product @key(fields: "id") {
    id: ID!
    name: String!
    priceInCents: Int!
  }

  type Query {
    products: [Product!]!
    product(id: ID!): Product
  }
`;

const PRODUCTS = [
  { id: 'prod-1', name: 'Cloud Server Pro', priceInCents: 9900 },
  { id: 'prod-2', name: 'Database Managed Instance', priceInCents: 15000 },
];

const resolvers = {
  Query: {
    products: () => PRODUCTS,
    product: (_: unknown, { id }: { id: string }) => PRODUCTS.find((p) => p.id === id),
  },
  Product: {
    __resolveReference(ref: { id: string }) {
      return PRODUCTS.find((p) => p.id === ref.id);
    },
  },
};

export async function startProductsSubgraph(port = 4003): Promise<void> {
  const app = express();
  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });
  await server.start();
  app.use(express.json());
  app.use('/graphql', expressMiddleware(server));
  await new Promise<void>((resolve) => http.createServer(app).listen({ port }, resolve));
  console.log(`🚀 [Products Subgraph] ready at http://localhost:${port}/graphql`);
}
```

---

## 16: Automated Testing & Verification

Pengujian federasi memerlukan pengujian integrasi gateway end-to-end tanpa menjalankan instance jaringan HTTP fisik melalui *Schema Composition Execution Test*.

```typescript
// gateway.spec.ts
import { ApolloServer } from '@apollo/server';
import { ApolloGateway, LocalGraphQLDataSource } from '@apollo/gateway';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';

describe('Federated Supergraph Integration Test', () => {
  let testServer: ApolloServer;

  beforeAll(async () => {
    // 1. Mock Subgraph Schemas Local in-memory
    const usersSchema = buildSubgraphSchema({
      typeDefs: gql`
        extend schema @link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key"])
        type User @key(fields: "id") {
          id: ID!
          name: String!
        }
        type Query {
          user(id: ID!): User
        }
      `,
      resolvers: {
        Query: { user: () => ({ id: 'u1', name: 'Unit Test User' }) },
        User: { __resolveReference: (ref) => ({ id: ref.id, name: 'Unit Test User' }) },
      },
    });

    const reviewsSchema = buildSubgraphSchema({
      typeDefs: gql`
        extend schema @link(url: "https://specs.apollo.dev/federation/v2.0", import: ["@key"])
        type User @key(fields: "id") {
          id: ID!
          karma: Int!
        }
      `,
      resolvers: {
        User: {
          __resolveReference: (ref) => ({ id: ref.id, karma: 999 }),
        },
      },
    });

    // 2. Mount Apollo Gateway dengan Local GraphQL Data Sources
    const gateway = new ApolloGateway({
      supergraphSdl: undefined,
      serviceList: [
        { name: 'users', url: 'local://users' },
        { name: 'reviews', url: 'local://reviews' },
      ],
      buildService({ name }) {
        if (name === 'users') return new LocalGraphQLDataSource(usersSchema);
        if (name === 'reviews') return new LocalGraphQLDataSource(reviewsSchema);
        throw new Error(`Unknown service: ${name}`);
      },
    });

    testServer = new ApolloServer({ gateway });
    await testServer.start();
  });

  afterAll(async () => {
    await testServer.stop();
  });

  it('Berhasil mengeksekusi batched cross-subgraph query plan', async () => {
    const response = await testServer.executeOperation({
      query: `
        query TestFederation {
          user(id: "u1") {
            id
            name
            karma
          }
        }
      `,
    });

    expect(response.body.kind).toBe('single');
    if (response.body.kind === 'single') {
      expect(response.body.singleResult.errors).toBeUndefined();
      expect(response.body.singleResult.data).toEqual({
        user: {
          id: 'u1',
          name: 'Unit Test User',
          karma: 999,
        },
      });
    }
  });
});
```

---

## 17: Troubleshooting Guide

### 1. Error: `GRAPHQL_VALIDATION_FAILED: Cannot query field "_entities" on type "Query"`
* **Akar Masalah:** Downstream service menggunakan Apollo Server reguler (`@apollo/server`) tanpa membungkus skema dengan `buildSubgraphSchema` dari package `@apollo/subgraph`.
* **Solusi:** Ganti `makeExecutableSchema` dengan `buildSubgraphSchema({ typeDefs, resolvers })` pada Subgraph.

### 2. Composition Error: `[CompositionError] Field "User.email" already has a resolver in Subgraph A and cannot be redefined in Subgraph B`
* **Akar Mas