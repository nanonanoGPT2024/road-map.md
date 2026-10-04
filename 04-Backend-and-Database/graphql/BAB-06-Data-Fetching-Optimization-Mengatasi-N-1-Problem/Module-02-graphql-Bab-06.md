# Bab 06: Data Fetching Optimization: Mengatasi N+1 Problem
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** mekanisme internal GraphQL execution engine dan DataLoader pada level Node.js Event Loop (Microtask Queue) untuk mendiagnosis bottlenecks I/O.
- **Mengimplementasikan** arsitektur Data Fetching lapis lanjut menggunakan TypeScript, mencakup *compound keys*, *projection pushdown*, dan *request-scoped caching pattern*.
- **Merancang** strategi batching untuk lingkungan terdistribusi (*Federated GraphQL Architecture / Subgraphs*) dengan protokol gRPC dan HTTP/2.
- **Mengevaluasi** perbandingan performa (*trade-off analysis*) antara SQL JOINs, DataLoader Batching (`IN` queries), dan subquery execution terhadap utilisasi database connection pool.
- **Mengintegrasikan** OpenTelemetry metrics guna mengukur *batch efficiency factor* dan *cache hit-ratio* secara *real-time* di lingkungan produksi.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- **Node.js Internals:** Memahami Event Loop phases (terutama *Microtask Queue* vs *Macrotask/Poll Phase*), `process.nextTick()`, dan *Promise resolution scheduling*.
- **GraphQL Fundamentals:** Memahami AST (Abstract Syntax Tree), Resolver Execution Tree (Breadth-First vs Depth-First traversal), dan `GraphQLResolveInfo`.
- **Database Indexing & Query Plans:** Memahami B-Tree search, cost-based optimizer, dampak clause `WHERE id IN (...)` berskala besar terhadap memory buffer pool PostgreSQL/MySQL.
- **TypeScript:** Penguasaan Generics, Conditional Types, dan Record types tingkat lanjut.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 GraphQL Execution Mechanics & N+1 Root Cause
GraphQL engine mengeksekusi resolver secara rekursif berbasis pemetaan skema. Secara spesifikasi, eksekusi field pada level yang sama bersifat konkuren melalui `Promise.all()`, tetapi eksekusi antar *parent-to-child* bersifat sekuensial hierarkis.

Ketika sebuah query meminta list entitas (misal 100 `Order`), engine memicu 1 query untuk mengambil daftar order. Kemudian, ketika resolver berpindah ke sub-field (misal `customer`), resolver `Order.customer` dipanggil secara independen sebanyak 100 kali. Tanpa mekanisme koordinasi, runtime akan menginstansiasi 100 koneksi/query independen ke database (`SELECT * FROM customers WHERE id = ?`). Inilah titik awal N+1 Problem.

#### 3.2 DataLoader Internal Mechanism: The Microtask Queue Loop
DataLoader memecahkan N+1 problem bukan melalui *background worker* terpisah, melainkan memanfaatkan penjadwalan antrean Microtask (`Promise.resolve()`) pada JavaScript Event Loop.

```
[ Call Stack Execution ]
  │
  ├─ Resolver 1: loader.load(1) ────► Append Key to Batch Queue [1]
  │                                   Return Unresolved Promise A
  ├─ Resolver 2: loader.load(2) ────► Append Key to Batch Queue [1, 2]
  │                                   Return Unresolved Promise B
  ├─ Resolver 3: loader.load(3) ────► Append Key to Batch Queue [1, 2, 3]
  │                                   Return Unresolved Promise C
  │
[ Call Stack Kosong ] ──────────────► Engine memicu Microtask Queue
                                      │
                                      ▼
                        [ DataLoader Batch Dispatch ]
                        batchFunction([1, 2, 3])
                        Executes: SELECT * FROM table WHERE id IN (1, 2, 3)
                                      │
                                      ▼
                        Resolve Promise A with data[1]
                        Resolve Promise B with data[2]
                        Resolve Promise C with data[3]
```

Langkah-langkah internal DataLoader:
1. Pemanggilan `.load(key)` memeriksa *memoization cache* lokal DataLoader.
2. Jika *cache miss*, DataLoader membuat satu Promise baru, menyimpan `{ key, resolve, reject }` ke dalam array internal `_queue`.
3. DataLoader memicu fungsi penjadwalan internal: jika antrean baru saja diinisiasi, ia memanggil `enqueuePostPromiseJob()` yang mendaftarkan fungsi dispatch ke Microtask queue via `Promise.resolve().then()`.
4. JavaScript call stack terus menyelesaikan resolver sinkronis lainnya di tick yang sama.
5. Saat call stack kosong, engine beralih ke Microtask queue. Fungsi batch DataLoader dieksekusi dengan seluruh keys yang terkumpul dalam array `_queue`.
6. Batch function mengembalikan array dengan **panjang dan indeks yang sama persis** dengan array keys masukan. DataLoader kemudian me-resolve masing-masing Promise individual.

#### 3.3 Memory Management & Request Scoping
DataLoader menyertakan *in-memory cache* bawaan. Pada arsitektur backend enterprise, **DataLoader dilarang keras dibuat sebagai Singleton / Global Object**. Jika dijadikan singleton:
- **Cache Poisoning / Cross-Request Leaks:** Data sensitif milik *User A* dapat terakses oleh *User B* jika caching key bertabrakan.
- **Out of Memory (OOM):** Objek yang di-load akan tertahan di V8 Old Generation Heap secara permanen, mencegah Garbage Collector mereklamasi memori.

**Standar Produksi:** DataLoader harus selalu diinstansiasi secara unik per-HTTP Request melalui penyusunan *Context Factory*.

---

### 4. Why & What

| Dimensi | Pendekatan Naive (Direct DB Call) | DataLoader (Request-Scoped) | Database SQL JOIN |
| :--- | :--- | :--- | :--- |
| **Pola Eksekusi I/O** | $N + 1$ queries independen | $1 + 1$ batch query via `IN` clause | $1$ monolitik single query |
| **Koneksi DB Pool** | Exhaustion tinggi, rentan timeout | Stabil, terduplikasi rendah | Sangat efisien dalam jumlah query |
| **Overfetching Data** | Rendah per entity | Rendah per entity | Tinggi (kartesian duplikasi data) |
| **Kompatibilitas GraphQL**| Alami, mengikuti pohon AST | Sangat cocok dengan AST traversal | Sulit dipecah pada schema dynamic |
| **Federated Subgraphs** | Mematikan network downstream | Sangat optimal untuk REST/gRPC batch | Tidak bisa langsung JOIN lintas DB |

#### Kapan Menggunakan DataLoader vs SQL JOIN?
- **Gunakan DataLoader ketika:** Arsitektur sistem melibatkan GraphQL Federation (lintas sub-layanan), query data relasional hierarki dinamis yang tidak dapat diprediksi kedalamannya, atau ketika database downstream menggunakan NoSQL/Microservice API.
- **Gunakan SQL JOIN (via Lookahead/AST inspection) ketika:** Relasi 1-to-1 bersifat ketat, skema data berada dalam database ACID relasional monolitik yang sama, dan GraphQL field selection secara eksplisit meminta data yang sudah terindeks rapat secara clustering.

---

### 5. How (Workflow Detail)

Alur kerja data fetching teroptimasi dari client hingga database:

```
GraphQL Client
      │ (1) POST /graphql { users { id, profile { avatar } } }
      ▼
API Gateway / Router
      │ (2) Context Initialization (Instantiate Scoped Loaders)
      ▼
GraphQL Server Execution Engine
      │ (3) Resolve Root Query: "users"
      ├────────► DB: SELECT id FROM users LIMIT 20;
      │ (4) Return 20 Users. Engine triggers "User.profile" for each.
      ▼
Resolver Layer (Iterative Calls)
      │ (5) Loop i=1..20: context.loaders.profileLoader.load(user[i].id)
      │      --> All 20 items registered in Microtask Queue
      ▼
Event Loop Transition (Call Stack Exhausted -> Run Microtask)
      │ (6) DataLoader flushes batch: [id1, id2, ..., id20]
      ▼
Batch Function Execution
      │ (7) DB: SELECT * FROM profiles WHERE user_id IN (id1, id2, ..., id20);
      │ (8) Map DB results strictly to input keys order.
      ▼
Promise Resolution
      │ (9) Return profiles[i] back to each User.profile resolver
      ▼
Response Formatting Engine
      │ (10) JSON serialization & response dispatch
      ▼
GraphQL Client
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kurir Restoran (Pemesanan Makanan Kolektif)
Bayangkan sebuah kantor dengan 50 karyawan (Resolver). Setiap karyawan ingin memesan makan siang dari restoran yang sama.
- **Naive Approach (N+1):** Setiap karyawan menelpon restoran secara terpisah, memesan 1 porsi, dan 50 kurir berbeda datang menggunakan 50 motor. Jalanan macet (Network Latency), pintu resepsionis sesak (Connection Pool Exhaustion).
- **DataLoader Approach:** Resepsionis meletakkan papan pesanan di lobi. Karyawan menuliskan pesanan mereka di papan tersebut. Tepat pukul 11:30 (Microtask Tick), resepsionis menelepon restoran **satu kali** dengan daftar lengkap 50 pesanan. Restoran mengirim 1 mobil van berisi 50 kotak makanan. Resepsionis membagikan masing-masing kotak ke pemilik yang sesuai.

```
NAIVE APPROACH (Without DataLoader):
[Resolver 1] ───(Query 1)───► [Database]
[Resolver 2] ───(Query 2)───► [Database]   High Connection Saturation!
[Resolver 3] ───(Query 3)───► [Database]   Pool Exhaustion!
[Resolver N] ───(Query N)───► [Database]

OPTIMIZED APPROACH (With DataLoader):
[Resolver 1] ──┐
[Resolver 2] ──┼──► [DataLoader Queue] ──(Single Batch Query)──► [Database]
[Resolver 3] ──┤        Microtask Tick
[Resolver N] ──┘    IN (id1, id2, id3, idN)
```

---

### 7. Practical Implementation (Standar Industri)

Berikut adalah implementasi production-ready menggunakan Node.js, TypeScript, Apollo Server v4, dan DataLoader dengan penanganan validasi urutan array serta compound keys.

#### 7.1 Setup & Types Definiton
```typescript
// src/types/context.ts
import DataLoader from 'dataloader';

export interface UserEntity {
  id: string;
  tenantId: string;
  name: string;
}

export interface ProfileEntity {
  id: string;
  userId: string;
  tenantId: string;
  avatarUrl: string;
  bio: string;
}

// Compound Key Definition
export interface TenantScopedKey {
  readonly id: string;
  readonly tenantId: string;
}

export interface IDataLoaders {
  profileByUserIdLoader: DataLoader<TenantScopedKey, ProfileEntity | null, string>;
}

export interface GraphQLContext {
  userId: string;
  tenantId: string;
  loaders: IDataLoaders;
}
```

#### 7.2 DataLoader Factory Implementation
DataLoader mensyaratkan dua aturan deterministik:
1. Panjang array keluaran **harus sama** dengan panjang array masukan.
2. Posisi indeks array keluaran **harus memetakan persis** posisi indeks array masukan.

```typescript
// src/loaders/profileLoader.ts
import DataLoader from 'dataloader';
import { ProfileEntity, TenantScopedKey } from '../types/context';
import { db } from '../infrastructure/database'; // Anggap instance database driver/knex/pg

// Serializer untuk compound key caching
const serializeCompoundKey = (key: TenantScopedKey): string => `${key.tenantId}:${key.id}`;

export function createProfileLoader(): DataLoader<TenantScopedKey, ProfileEntity | null, string> {
  return new DataLoader<TenantScopedKey, ProfileEntity | null, string>(
    async (keys: readonly TenantScopedKey[]) => {
      // 1. Ekstraksi unique keys untuk database payload query
      const tenantIds = Array.from(new Set(keys.map((k) => k.tenantId)));
      const userIds = Array.from(new Set(keys.map((k) => k.id)));

      // 2. Query batch ke database menggunakan SQL IN-Clause
      const records: ProfileEntity[] = await db('profiles')
        .whereIn('tenant_id', tenantIds)
        .whereIn('user_id', userIds)
        .select('*');

      // 3. Mapping menggunakan Lookup Map untuk menjamin O(1) matching
      const recordMap = new Map<string, ProfileEntity>();
      for (const record of records) {
        const keyHash = serializeCompoundKey({ id: record.userId, tenantId: record.tenantId });
        recordMap.set(keyHash, record);
      }

      // 4. Return array dengan urutan dan panjang identik sesuai keys
      return keys.map((key) => {
        const hash = serializeCompoundKey(key);
        return recordMap.get(hash) ?? null;
      });
    },
    {
      cacheKeyFn: serializeCompoundKey, // Mengizinkan komparasi object identity by value
      maxBatchSize: 1000,               // Mengurangi memory spikes dan query limit boundaries
    }
  );
}
```

#### 7.3 Context Factory & Apollo Server Integration
```typescript
// src/server.ts
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { GraphQLContext } from './types/context';
import { createProfileLoader } from './loaders/profileLoader';

const typeDefs = `#graphql
  type Profile {
    id: ID!
    userId: ID!
    avatarUrl: String
    bio: String
  }

  type User {
    id: ID!
    name: String!
    profile: Profile
  }

  type Query {
    users(limit: Int!): [User!]!
  }
`;

const resolvers = {
  Query: {
    users: async (_parent: unknown, args: { limit: number }, context: GraphQLContext) => {
      // Mock data users retrieval
      return await db('users')
        .where({ tenant_id: context.tenantId })
        .limit(args.limit);
    },
  },
  User: {
    profile: async (parent: { id: string }, _args: unknown, context: GraphQLContext) => {
      // Memanggil request-scoped loader
      return context.loaders.profileByUserIdLoader.load({
        id: parent.id,
        tenantId: context.tenantId,
      });
    },
  },
};

const server = new ApolloServer<GraphQLContext>({
  typeDefs,
  resolvers,
});

async function bootstrap() {
  const { url } = await startStandaloneServer(server, {
    listen: { port: 4000 },
    context: async ({ req }): Promise<GraphQLContext> => {
      const tenantId = (req.headers['x-tenant-id'] as string) || 'tenant-default';
      const userId = (req.headers['x-user-id'] as string) || 'anonymous';

      return {
        tenantId,
        userId,
        // DIBUAT BARU PER REQUEST (STRICT REQUIREMENT)
        loaders: {
          profileByUserIdLoader: createProfileLoader(),
        },
      };
    },
  });

  console.log(`🚀 GraphQL Production Server ready at ${url}`);
}

bootstrap();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Marketplace FinTech (High-Throughput)
- **Kondisi:** Sistem memproses 20.000 RPS pada query agregasi `GetOrderSummary`.
- **Topologi:** Apollo Federation (Gateway + 3 Subgraphs: Order Subgraph, Identity Subgraph, Ledger Subgraph).
- **Insiden:** Terjadi connection timeout cascade pada PostgreSQL Identity Subgraph ketika flash sale berlangsung. Connection pool (500 connections) habis seketika, latency melonjak dari 45ms ke 12.000ms.

#### Akar Masalah
Resolver Subgraph Entity `_entities` pada Identity Subgraph dipanggil oleh Apollo Gateway tanpa optimasi batching downstream:
```graphql
query($representations: [_Any!]!) {
  _entities(representations: $representations) {
    ... on User {
      kycStatus
    }
  }
}
```
Gateway mengirim batch 100 representations, tetapi subgraph mengeksekusi fetch KYC status via HTTP microservice API client internal satu persatu (`Promise.all(ids.map(fetchKyc))`). Terjadi network socket starvation pada OS level layer.

#### Solusi Arsitektur
1. **Penerapan Subgraph-Level DataLoader:** Mengalihkan HTTP Microservice Client ke batching gRPC call (`GetKycStatusBatch([ids])`).
2. **Chunking Query Boundary:** Menyetel `maxBatchSize: 250` pada DataLoader untuk mencegah ukuran packet melebihi batas MTU router internal dan payload limit database driver (misal: batasan parameter bind PostgreSQL 65.535).
3. **Hasil:**
   - Database Connection Utilization turun sebesar **88%**.
   - Latency p99 terpangkas dari **12.000ms** menjadi **38ms**.
   - Throughput query naik dari 1.200 RPS menjadi **22.500 RPS** tanpa horizontal scale instance tambahan.

---

### 9. Trade-offs (Analisis Komparatif Rekayasa)

```
              Latency (p99)
                  ▲
                  │        Direct REST/DB Calls (N+1)
                  │         ●
                  │
                  │
                  │                     DataLoader Batching
                  │                      ●
                  │
                  │    SQL JOINs
                  │     ●
                  └──────────────────────────────────► Throughput (Concurrency)
```

1. **DataLoader vs Database Latency (Batch Overhead):**
   - *Trade-off:* DataLoader sengaja mengorbankan latency resolver awal (beberapa microsecond) untuk menunggu mikro-antrean selesai dikumpulkan. 
   - *Dampak:* Pada volume request tunggal (1 request, 1 record), DataLoader lebih lambat ~5-10% daripada query langsung karena alokasi closure memori dan queue tick. Namun pada konkurensi tinggi, performanya mendominasi secara eksponensial.

2. **Dampak Clause `IN (...)` Skala Masif:**
   - *Trade-off:* Mengirimkan 5.000 ID dalam satu query `WHERE id IN (...)` memaksa query planner DB melakukan index scan parsing yang besar, memicu *high memory sort work area*.
   - *Mitigasi:* Konfigurasi `maxBatchSize` DataLoader di angka optimal (misal 500 - 1000).

3. **Memory Footprint:**
   - *Trade-off:* Menyimpan cache di context DataLoader per HTTP request menaikkan alokasi heap memori Node.js sementara selama lifecycle request berjalan.
   - *Mitigasi:* Lifecycle loader harus dipastikan selesai dan dibuang saat response ditutup (*garbage-collected* secara natural).

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Ketidaksesuaian Panjang Array dan Urutan Output (Silent Data Corruption)
**Kode Bermasalah:**
```typescript
// SALAH: Jika DB tidak mengembalikan data untuk ID tertentu, urutan indeks rusak!
new DataLoader(async (keys) => {
  const users = await db('users').whereIn('id', keys);
  return users; // PANJANG DAN URUTAN TIDAK COCOK!
});
```
**Troubleshooting & Solusi:**
Jika `keys = [1, 2, 3]` dan data ID 2 hilang, database mengembalikan `[user1, user3]`. DataLoader akan secara keliru mengembalikan `user3` ke pemanggil ID 2, dan throw error undefined ke ID 3. Selalu petakan ulang hasil database menggunakan `keys.map(k => map.get(k) || null)`.

#### Mistake 2: DataLoader sebagai Singleton Global
**Kode Bermasalah:**
```typescript
// SALAH BESAR: Global DataLoader
export const userLoader = new DataLoader(keys => fetchUsers(keys));
```
**Troubleshooting & Solusi:**
Leakage data antar pengguna. Jika *User A* me-load data privat miliknya, data tersebut tersimpan di memoization cache DataLoader global. Ketika *User B* melakukan query data yang sama, *User B* membaca data *User A* dari cache. Selalu instantiate DataLoader di dalam function pembuat konteks request (`context factory`).

#### Mistake 3: Unhandled Rejection di dalam Batch Function
**Dampak:**
Jika fungsi batch melempar error tak tertangani (`throw new Error("DB Error")`), semua Promise yang menunggu di batch tersebut akan di-reject secara bersamaan, mengakibatkan Partial Failure runtuh menjadi Total Failure.
**Solusi:**
Tangani error secara granular. Kembalikan instance `Error` per elemen array bila kegagalan bersifat spesifik per entitas:
```typescript
return keys.map(key => {
  return recordMap.get(key) || new Error(`Entity ${key} not found`);
});
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Request Isolation:** DataLoader di-instansiasi baru pada setiap lifecycle *incoming request* melalui Apollo Server Context function.
- [ ] **Array Invariance:** Batch function menjamin `output.length === inputKeys.length` dan pemetaan indeks data presisi 100%.
- [ ] **Max Batch Size:** Parameter `maxBatchSize` diatur secara ketat (rekomendasi: 200 - 1.000) untuk mencegah buffer overflow database parameter bind.
- [ ] **Cache Key Serialization:** Jika menggunakan non-primitive keys (object, array), selalu sediakan fungsi kustom `cacheKeyFn`.
- [ ] **Disable Cache for Mutations:** Jangan menggunakan cache dari DataLoader baca di dalam resolver mutasi untuk mencegah pembacaan data basi (*stale data*).
- [ ] **Lookahead Inspection:** Kombinasikan DataLoader dengan `graphql-info-inspector` untuk hanya melakukan SELECT pada kolom yang diminta client (*SQL projection pushdown*).
- [ ] **Telemetry Instrumentation:** Tambahkan hook tracer (OpenTelemetry) pada fungsi batch untuk mencatat metrik: `batch_size`, `cache_hit_ratio`, dan `db_wait_time`.

---

### 12. Hands-on Practice

Buka terminal Anda dan setup workspace pada direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Dependencies
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install @apollo/server graphql dataloader knex pg dotenv
npm install -D typescript @types/node tsx
npx tsc --init
```

#### Langkah 2: Database Schema & Seeder
Buat file `src/seed.ts` untuk mengisi database SQLite/PostgreSQL lokal.

```typescript
// src/seed.ts
import { knex } from 'knex';

const db = knex({
  client: 'sqlite3',
  connection: { filename: './dev.sqlite3' },
  useNullAsDefault: true,
});

async function run() {
  await db.schema.dropTableIfExists('articles');
  await db.schema.dropTableIfExists('authors');

  await db.schema.createTable('authors', (t) => {
    t.string('id').primary();
    t.string('name');
  });

  await db.schema.createTable('articles', (t) => {
    t.string('id').primary();
    t.string('author_id');
    t.string('title');
  });

  await db('authors').insert([
    { id: 'auth-1', name: 'Al-Farabi' },
    { id: 'auth-2', name: 'Ibn Sina' },
  ]);

  await db('articles').insert([
    { id: 'art-1', author_id: 'auth-1', title: 'Philosophy of Logic' },
    { id: 'art-2', author_id: 'auth-1', title: 'Political Regime' },
    { id: 'art-3', author_id: 'auth-2', title: 'The Canon of Medicine' },
  ]);

  console.log('Seeding completed successfully.');
  process.exit(0);
}

run();
```
Jalankan seed:
```bash
npx tsx src/seed.ts
```

#### Langkah 3: Implementasikan Server Terinstrumentasi DataLoader
Buat file `src/index.ts`:

```typescript
// src/index.ts
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import DataLoader from 'dataloader';
import { knex } from 'knex';

const db = knex({
  client: 'sqlite3',
  connection: { filename: './dev.sqlite3' },
  useNullAsDefault: true,
});

// Logging SQL untuk memverifikasi perbaikan N+1
db.on('query', (query) => {
  console.log(`[SQL EXEC]: ${query.sql} -- Bindings: [${query.bindings}]`);
});

interface Context {
  loaders: {
    authorLoader: DataLoader<string, any>;
  };
}

const typeDefs = `#graphql
  type Author {
    id: ID!
    name: String!
  }

  type Article {
    id: ID!
    title: String!
    author: Author
  }

  type Query {
    articles: [Article!]!
  }
`;

function createAuthorLoader() {
  return new DataLoader<string, any>(async (authorIds) => {
    console.log(`[DataLoader] Batching execution for keys:`, authorIds);
    const authors = await db('authors').whereIn('id', authorIds);
    const authorMap = new Map(authors.map((a) => [a.id, a]));
    return authorIds.map((id) => authorMap.get(id) || null);
  });
}

const resolvers = {
  Query: {
    articles: async () => {
      return await db('articles').select('*');
    },
  },
  Article: {
    author: async (parent: { author_id: string }, _args: unknown, ctx: Context) => {
      return ctx.loaders.authorLoader.load(parent.author_id);
    },
  },
};

async function main() {
  const server = new ApolloServer<Context>({ typeDefs, resolvers });

  const { url } = await startStandaloneServer(server, {
    listen: { port: 4001 },
    context: async () => ({
      loaders: {
        authorLoader: createAuthorLoader(),
      },
    }),
  });

  console.log(`Running on ${url}`);
}

main();
```

#### Langkah 4: Pengujian & Observasi
Jalankan server:
```bash
npx tsx src/index.ts
```
Kirim Query menggunakan cURL:
```bash
curl -X POST http://localhost:4001/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { articles { id title author { name } } }"}'
```

**Perhatikan Log Terminal:**
Anda akan melihat tepat **2 query SQL**, bukan 4 query (1 untuk articles, 1 batch untuk authors). Ini memverifikasi masalah N+1 terselesaikan secara deterministik.

---

### 13. Exercises

#### Level Easy
Ubah `createAuthorLoader` pada Hands-on di atas untuk menangani situasi di mana author memiliki status soft-delete (`deleted_at IS NOT NULL`). Jika author terhapus, kembalikan `null` tanpa merusak pipeline resolver.
- **Kriteria Keberhasilan:** Eksekusi query tidak throw error dan record artikel tetap mengembalikan payload dengan `author: null`.

#### Level Medium
Buat sebuah `One-to-Many DataLoader` bernama `articlesByAuthorIdLoader`. Loader ini harus menerima input satu `authorId` dan mengembalikan `Article[]` (Array artikel) milik author tersebut.
- **Kriteria Keberhasilan:** Mampu memetakan banyak entitas anak ke satu key induk menggunakan group aggregation logic di dalam batch function.

#### Level Hard
Rancang DataLoader yang mengimplementasikan **Projection Pushdown**. Loader harus memeriksa `GraphQLResolveInfo` untuk membaca AST field yang dipilih oleh client (misal: client hanya meminta field `avatar`, abaikan `bio`). 
- **Kriteria Keberhasilan:** SQL yang dihasilkan DataLoader secara dinamis mengubah `SELECT *` menjadi `SELECT id, user_id, avatar_url` sesuai permintaan client secara adaptif.

---

### 14. Enterprise Production Challenge

**Studi Kasus:** Sistem Multitenant Cloud Logging Analytics.
- **Konteks:** Anda memiliki skema multitenant di mana table logs di-sharding secara dinamis per bulan dan per tenant ID (contoh nama tabel: `logs_tenantA_2023_10`).
- **Tantangan:** 
  1. Rancang arsitektur data loader yang dapat menerima compound key `{ tenantId: string, timestamp: Date, logId: string }`.
  2. Batch function harus secara dinamis mengelompokkan keys berdasarkan shard target database table, menembakkan queries paralel ke masing-masing dynamic shard yang relevan menggunakan `Promise.allSettled()`.
  3. Kembalikan data yang teragregasi secara presisi sesuai urutan keys pemanggil pertama.
  4. Implementasikan circuit-breaker: Jika satu tenant shard lambat (>2000ms), gagalkan hanya tenant tersebut dengan mengembalikan GraphQL Partial Error, tanpa menggagalkan query dari tenant shard lain dalam request yang sama.
- **Constraint:** Tidak boleh menggunakan Object Mutation, full strict TypeScript types, dan memori garbage heap overhead harus di bawah 15MB pada 5.000 queued items.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Kapan tepatnya DataLoader mengeksekusi fungsi batch-nya di Node.js runtime?
   - A. Tepat saat method `.load()` dipanggil.
   - B. Pada fase timer Event Loop berikutnya (`setTimeout`).
   - C. Di akhir Call Stack sinkron melalui Microtask Queue (`Promise.resolve()`).
   - D. Setiap 100 millisecond secara terjadwal.

2. Mengapa DataLoader dilarang keras dibuat sebagai singleton instance yang dipakai bersama lintas request?
   - A. Karena DataLoader tidak mendukung TypeScript generics.
   - B. Dapat menyebabkan kebocoran data antar user (Cache Poisoning) dan kebocoran memori (OOM).
   - C. Karena Apollo Server secara otomatis mematikan singleton.
   - D. Singleton memperlambat deserialisasi JSON payload.

3. Apa aturan utama yang harus dipenuhi oleh array yang dikembalikan oleh DataLoader batch function?
   - A. Harus selalu diurutkan secara ascending berdasarkan Primary Key.
   - B. Panjang array dan posisi indeks elemen harus identik dengan array keys masukan.
   - C. Harus membuang nilai `null` dan `undefined`.
   - D. Ukurannya harus selalu sama dengan `maxBatchSize`.

4. Fitur apa dari DataLoader yang memungkinkan pencarian key berbasis object reference yang berbeda namun memiliki nilai yang sama?
   - A. `batchScheduleFn`
   - B. `name`
   - C. `cacheKeyFn`
   - D. `cacheMap`

5. Berapakah jumlah query database yang dihasilkan DataLoader untuk mengambil relasi dari 50 item data flat jika seluruh child resolve pada tick yang sama?
   - A. 50 Query
   - B. 51 Query
   - C. 1 Batch Query
   - D. 0 Query

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis)
6. Jika fungsi batch DataLoader melempar exception murni (`throw new Error("Timeout")`), apa yang terjadi pada resolver individual yang memanggil `.load()`?
   - A. Hanya key pertama yang error, key lainnya mengembalikan `null`.
   - B. Semua Promise resolver yang terdaftar pada batch tersebut akan ter-reject.
   - C. DataLoader akan otomatis melakukan retry hingga 3 kali.
   - D. Database pool otomatis restart.

7. Mengapa query `WHERE id IN (...)` yang dihasilkan oleh DataLoader bisa menjadi masalah jika tidak dibatasi nilainya?
   - A. Karena PostgreSQL menolak string key lebih dari 10 karakter.
   - B. Mengakibatkan parameter limits saturation pada driver database dan lonjakan konsumsi memory parse tree pada DB engine.
   - C. Database akan otomatis mengunci table secara eksklusif (Full Table Lock).
   - D. Menghilangkan fungsionalitas Primary Key Index.

8. Bagaimana cara paling aman mengosongkan cache DataLoader setelah mutasi data terjadi pada request yang sama?
   - A. Menghapus object context GraphQL.
   - B. Memanggil method `loader.clear(key)` atau `loader.clearAll()`.
   - C. Me-restart server Node.js.
   - D. Mematikan database connection pool.

9. Manakah pernyataan yang benar mengenai integrasi DataLoader dalam arsitektur GraphQL Federation?
   - A. Subgraph tidak memerlukan DataLoader karena Gateway sudah mengeliminasi N+1.
   - B. DataLoader diimplementasikan pada Subgraph level untuk mem-batch request resolve entity representation (`_entities`).
   - C. DataLoader diletakkan di Apollo Gateway untuk mem-batch query ke semua subgraph secara serentak.
   - D. Federation melarang pemakaian DataLoader demi keamanan data.

10. Jika pemanggilan query GraphQL menghasilkan urutan hierarki 3 level: `Users -> Posts -> Comments`, berapa total database trips minimal yang terjadi bila DataLoader digunakan di setiap level?
    - A. 3 Trips
    - B. $1 + N + M$ Trips
    - C. 1 Trip
    - D. 6 Trips

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Connection Spike:**
    Sistem Anda mengalami lonjakan database connection hingga batas maksimal pool (pool size: 100) sesaat setelah migrasi ke GraphQL DataLoader, meskipun jumlah query database terpantau turun drastis. Setelah diteliti, query batch memuat ribuan ID sekaligus. Parameter konfigurasi apa pada DataLoader yang harus segera Anda pasang untuk meredam insiden ini? Jelaskan mekanismenya!

12. **Skenario Cache Consistency Bug:**
    Seorang engineer melaporkan bahwa pada endpoint mutasi `updateUserEmail(id: "1", newEmail: "a@b.com")`, resolver berhasil mengubah data di database. Namun query lanjutan `me { email }` yang berada dalam satu payload HTTP mutation yang sama masih mengembalikan email lama. Apa penyebab arsitekturalnya dan bagaimana solusi resolvernya?

13. **Skenario Array Length Desynchronization:**
    Perhatikan potongan kode berikut:
    ```typescript
    const userLoader = new DataLoader(async (ids) => {
      return await db('users').whereIn('id', ids).select();
    });
    ```
    Jika pemanggil mengeksekusi:
    ```typescript
    Promise.all([
      userLoader.load('A'), // Record ada di DB
      userLoader.load('B'), // Record TIDAK ada di DB
      userLoader.load('C'), // Record ada di DB
    ])
    ```
    Apa error spesifik yang akan dimunculkan oleh internal runtime DataLoader, dan bagaimana struktur data kembalian yang seharusnya?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **C** — Di akhir call stack eksekusi sinkronus, DataLoader dipicu via microtask queue callback (`Promise.resolve()`).
2. **B** — Singleton menahan cache lintas koneksi HTTP, membuka risiko data leakage antar user dan konsumsi memori tak terhingga (memory leak).
3. **B** — DataLoader memetakan resolver berdasarkan indeks array; panjang dan posisi urutan input dan output harus persis sama.
4. **C** — Default DataLoader menggunakan komparasi identitas memori (`===`). Objek membutuhkan serialization kustom melalui `cacheKeyFn`.
5. **C** — Seluruh 50 pemanggilan `.load()` masuk ke tick microtask yang sama dan dilebur menjadi 1 query batch.

#### Bagian 2: Intermediate
6. **B** — Exception level-batch me-reject seluruh promise batch execution array. Error harus dipetakan per item jika ingin partial handling.
7. **B** — Database engine memiliki batas parameter binding (misal SQL Server: 2.100, Postgres: 65.535), dan memori parser akan membengkak jika clause `IN` terlalu besar.
8. **B** — Memanggil explicit cache eviction `.clear(key)` atau `.clearAll()` pada instance loader request tersebut.
9. **B** — Pada GraphQL Federation, query `_entities` dari gateway diteruskan ke subgraph; DataLoader di subgraph mengelompokkan representation keys ini.
10. **A** — 3 trips (1 trip untuk Users, 1 trip batch untuk Posts dari users tersebut, 1 trip batch untuk Comments dari posts tersebut).

#### Bagian 3: Panduan Skenario Kasus Produksi
11. **Solusi Kasus 11:**
    Pasang opsi `maxBatchSize` (misal diset ke 250 atau 500). Mekanismenya: DataLoader akan memecah antrean yang awalnya ribuan menjadi sub-batch kecil yang dieksekusi secara terukur, mencegah query berukuran raksasa yang mengunci pool database terlalu lama dan memakan memori buffer database terlalu masif.
12. **Solusi Kasus 12:**
    Penyebab: Resolver mutasi mengeksekusi update ke database, namun `context.loaders.userLoader` telah men-cache model User lama sebelum mutasi berjalan (atau dibaca ulang via loader yang sama).
    Solusi: Di dalam resolver mutasi, setelah database update berhasil, panggil `context.loaders.userLoader.clear(id)` atau perbarui cache secara manual menggunakan `context.loaders.userLoader.clear(id).prime(id, updatedUser)`.
13. **Solusi Kasus 13:**
    Error spesifik: `The order of resolved values must match the order of keys...`. Database hanya mengembalikan array dengan panjang 2 (`[User A, User C]`), sedangkan DataLoader mengharapkan panjang 3.
    Solusi yang benar: Kembalikan array berisi `[UserA, null, UserC]` menggunakan mapping `ids.map(id => map.get(id) ?? null)`.

---

### 16. Summary

- **N+1 Problem** bukan keterbatasan dari GraphQL itu sendiri, melainkan konsekuensi logis dari arsitektur resolver terisolasi (*decoupled resolvers*) yang mengeksekusi I/O secara naif.
- **DataLoader** menyelesaikan permasalahan ini dengan menjadwalkan batch function ke dalam **Microtask Queue** Node.js runtime, mengeksploitasi siklus hidup Call Stack Event Loop secara presisi.
- Arsitektur produksi mewajibkan DataLoader bersifat **Request-Scoped (Context-bound)** untuk mencegah bahaya fatal *data leaks* dan *memory exhaustion*.
- Kontrak deterministik DataLoader mengharuskan: **Panjang Array Hasil = Panjang Array Masukan**, dengan urutan indeks yang terpetakan sempurna (1:1 mapping).
- Pada sistem berskala enterprise, batching harus dikombinasikan dengan teknik **Projection Pushdown**, pengaturan batas **Max Batch Size**, pemantauan **OpenTelemetry Metrics**, serta pengamanan transaksi mutasi melalui **Cache Eviction Strategies**.