# Bab 06 Module 01: Data Fetching Optimization: Mengatasi N+1 Problem

---

## Seksi 01: Identitas Modul

*   **Track:** Backend and Database Engineering
*   **Domain:** GraphQL Engine & Performance Engineering
*   **Kategori:** 04-Backend-and-Database
*   **Kode Modul:** GQL-04-06-01
*   **Tingkat Kesulitan:** Advanced / Enterprise-Grade
*   **Prasyarat Konseptual:** 
    *   Arsitektur Eksekusi GraphQL AST (*Abstract Syntax Tree*)
    *   Mekanisme Resolusi Field-Level (*Breadth-First* vs *Depth-First Execution*)
    *   Event Loop Node.js (Microtask vs Macrotask Queues, `process.nextTick()`)
    *   SQL Query Execution Plan & Database Indexing (PostgreSQL B-Tree & Composite Keys)
*   **Stack Rekomendasi:** Node.js v20+ LTS, TypeScript 5.x, Apollo Server v4, DataLoader v2.2+, Kysely / Prisma / pg-promise, PostgreSQL 16+.

---

## Seksi 02: Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendiagnosis dan Mengisolasi** akar permasalahan *N+1 Query Problem* pada GraphQL runtime engine melalui analisis Graph Execution Path dan database I/O trace.
2.  **Membangun Engine Batching & Caching** kustom berbasis *Event Loop Tick* menggunakan library `DataLoader` maupun implementasi berbasis native `Promise` scheduling.
3.  **Mengintegrasikan Dataloader Scoping** yang aman (*Request-scoped Context*) untuk mencegah kebocoran data (*cross-request data contamination/memory leak*) pada aplikasi multi-tenant/high-concurrency.
4.  **Mendesain Strategi SQL Projection** dan multi-column batching (composite key loading) guna mengatasi masalah over-fetching pada level relational database.
5.  **Menerapkan Observabilitas Lanjutan** untuk memantau *cache hit ratio*, *batch dispatch metrics*, dan *database round-trip latency* secara real-time menggunakan OpenTelemetry & Prometheus.
6.  **Mengotomatisasi Pengujian Regresi I/O** menggunakan integrasi testing yang memverifikasi jumlah query SQL yang dieksekusi per operasi GraphQL query.

---

## Seksi 03: Concept Map Diagram

```
+-----------------------------------------------------------------------------------+
|                        GRAPHQL RUNTIME EXECUTION PIPELINE                         |
+-----------------------------------------------------------------------------------+
                                          |
                                   [ Incoming Query ]
                                          |
                             +------------v------------+
                             | AST Parsing & Validation |
                             +------------+------------+
                                          |
                        +-----------------v-----------------+
                        |  Field Resolver Execution Graph   |
                        +-----------------+-----------------+
                                          |
         +--------------------------------+--------------------------------+
         |                                                                 |
         v (Naive Resolution)                                              v (Optimized Resolution)
+---------------------------------+                               +---------------------------------+
|  Individual Database Fetching   |                               |  DataLoader Batch Aggregation   |
|   (Resolvers invoke I/O directly)|                               |   (Keys queued during microtick)|
+---------------------------------+                               +---------------------------------+
         |                                                                 |
         | Iterates N times                                                | Collects array of [Key_1..N]
         v                                                                 v
+---------------------------------+                               +---------------------------------+
|   DATABASE EXHAUSTION (N+1)     |                               |   SINGLE BATCH QUERY DISPATCH   |
|   SELECT * FROM x WHERE id = 1  |                               |   SELECT * FROM x WHERE id IN   |
|   SELECT * FROM x WHERE id = 2  |                               |   ($1, $2, $3, ... $N)          |
|   ...                           |                               +---------------------------------+
|   SELECT * FROM x WHERE id = N  |                                        |
+---------------------------------+                                        | Maps results preserving
                                                                           | initial array index order
                                                                           v
                                                          +---------------------------------+
                                                          | Resolvers Consume Batched Value |
                                                          +---------------------------------+
```

---

## Seksi 04: Mengapa Relevan

Dalam arsitektur GraphQL, engine pemrosesan mengeksekusi *field resolver* secara diskrit, terisolasi, dan rekursif. Setiap *resolver* hanya mengetahui domain datanya sendiri tanpa konteks hierarki global secara otomatis. Desain ini memberikan fleksibilitas skema yang luar biasa, namun menciptakan celah performa kritis: **The N+1 Query Problem**.

### Kasus Nyata Kegagalan Sistem
Bayangkan sebuah platform e-commerce yang menampilkan query daftar 100 pesanan (`orders`), di mana setiap pesanan memiliki satu pembeli (`customer`). 
*   **GraphQL Naive:** 1 query dieksekusi untuk mengambil 100 pesanan, diikuti oleh 100 query terpisah ke tabel pengguna untuk mengambil data setiap pembeli. Total: **101 Database Round-trips**.
*   **Dampak Skalabilitas:** Jika database latency adalah 5ms, total waktu eksekusi jaringan murni adalah `1 * 5ms + 100 * 5ms = 505ms`. Bila throughput traffic mencapai 500 RPS, database akan menerima 50.500 QPS—menyebabkan *connection pool exhaustion*, *CPU starvation*, lonjakan *p99 latency*, dan berujung pada *Cascading Failure* pada downstream microservices.

Optimasi *Data Fetching* dengan Batching dan Request-scoped In-memory Caching mengonsolidasikan 101 query tersebut menjadi **2 query database terisolasi**, mereduksi I/O cost hingga 98% dan menjaga stabilitas resource database.

---

## Seksi 05: Anatomi Konsep Inti

### 1. The Microtask Queue Scheduler & Node.js Event Loop
Inti dari pattern batching (`DataLoader`) di JavaScript/Node.js bersandar pada pemanfaatan microtask queue (`Promise.resolve()`) atau `process.nextTick()`. Ketika sebuah field resolver memanggil `.load(id)`, DataLoader tidak langsung mengirim query ke database. Sebaliknya:
1.  DataLoader memasukkan `id` ke dalam internal array/queue.
2.  Mengembalikan `Promise` baru yang berstatus *pending*.
3.  Menjadwalkan fungsi batch runner dieksekusi pada *tick/microtask* berikutnya menggunakan scheduler loop.
4.  Setelah semua resolver sinkron pada level kedalaman GraphQL AST yang sama selesai dijalankan, microtask queue dieksekusi.
5.  Batch function berjalan *sekali* membawa seluruh akumulasi array `id`, mengeksekusi satu query SQL (`WHERE id IN (...)`), dan memecahkan (*resolve*) masing-masing `Promise` yang sesuai dengan urutan index aslinya.

```
       [ Call resolver A: loader.load(1) ] -> Enqueue 1 -> Returns Promise A (Pending)
       [ Call resolver B: loader.load(2) ] -> Enqueue 2 -> Returns Promise B (Pending)
                                      |
                      === JS Call Stack Empty ===
                                      |
                      === Event Loop Microtask Tick ===
                                      |
       [ Batch Function Triggered with Keys: [1, 2] ]
                                      |
       [ SQL: SELECT * FROM tbl WHERE id IN (1, 2) ]
                                      |
       [ Resolve Promise A with Row 1, Resolve Promise B with Row 2 ]
```

### 2. The Golden Rules of DataLoader Batch Functions
Fungsi batch DataLoader memiliki dua kontrak absolut yang tidak boleh dilanggar:
*   **Array Length Invariance:** Panjang array hasil yang dikembalikan oleh batch function harus **persis sama** dengan panjang array keys yang dimasukkan.
*   **Index Ordering Invariance:** Posisi indeks data pada array return harus **persis memetakan** posisi indeks pada array keys. Jika `keys = [4, 2, 9]`, maka return harus `[DataFor4, DataFor2, DataFor9]`. Jika key `2` tidak ditemukan di DB, posisi indeks ke-1 harus bernilai `null` atau instance `Error`.

---

## Seksi 06: Panduan Implementasi Step-by-Step

Berikut adalah arsitektur refactoring dari sistem naive GraphQL menuju pipeline data fetching kelas industri yang terisolasi per-request.

### Langkah 1: Isolasi Factory DataLoader (Request-Scoped)
Jangan pernah membuat instance DataLoader sebagai Global/Singleton Variable. Hal tersebut akan mengakibatkan:
*   *Memory Leak*: Cache internal tidak pernah dibersihkan.
*   *Security/Data Leakage Issue*: User B bisa membaca data User A yang tersimpan di memori cache loader.

DataLoader **harus** diinisialisasi baru pada setiap siklus request melalui context GraphQL.

```typescript
// src/context/loaders.ts
import DataLoader from 'dataloader';
import { Pool } from 'pg';

export interface IDataLoaders {
  userLoader: DataLoader<string, UserRecord | null>;
}

export function createDataLoaders(dbPool: Pool): IDataLoaders {
  return {
    userLoader: new DataLoader<string, UserRecord | null>(
      async (keys: readonly string[]) => {
        return await batchGetUsersByIds(dbPool, keys);
      },
      {
        cache: true, // In-memory deduplication during this single request
        maxBatchSize: 500 // Mencegah payload packet size limit pada DB
      }
    )
  };
}
```

### Langkah 2: Konstruksi Batch Loading Function yang Deterministik
Query database relational tidak menjamin urutan data kembali sesuai dengan klausa `IN (...)`. Kita wajib menggunakan *hash-map reordering pattern*.

```typescript
// src/loaders/userLoader.ts
import { Pool } from 'pg';

export interface UserRecord {
  id: string;
  name: string;
  email: string;
}

export async function batchGetUsersByIds(
  dbPool: Pool,
  userIds: readonly string[]
): Promise<(UserRecord | null | Error)[]> {
  // 1. Eksekusi query parametrik batch tunggal
  const query = `
    SELECT id, name, email 
    FROM users 
    WHERE id = ANY($1::uuid[])
  `;
  
  try {
    const result = await dbPool.query<UserRecord>(query, [userIds as string[]]);
    
    // 2. Petakan hasil ke Dictionary / Hash Map untuk O(1) Lookup
    const userMap = new Map<string, UserRecord>();
    for (const row of result.rows) {
      userMap.set(row.id, row);
    }
    
    // 3. Rekonstruksi array output agar sesuai urutan dan panjang array userIds
    return userIds.map((id) => userMap.get(id) ?? null);
  } catch (err) {
    // 4. Return instance Error individual jika query gagal
    return userIds.map(() => err instanceof Error ? err : new Error(String(err)));
  }
}
```

### Langkah 3: Injeksi Loader ke Apollo Context Pipeline

```typescript
// src/server.ts
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { Pool } from 'pg';
import { createDataLoaders, IDataLoaders } from './context/loaders';

export interface GraphQLContext {
  db: Pool;
  loaders: IDataLoaders;
  userId?: string;
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,
});

const server = new ApolloServer<GraphQLContext>({
  typeDefs,
  resolvers,
});

const { url } = await startStandaloneServer(server, {
  listen: { port: 4000 },
  context: async ({ req }) => {
    // DataLoader DIBUAT BARU untuk setiap request unik
    return {
      db: pool,
      loaders: createDataLoaders(pool),
      userId: req.headers['x-user-id'] as string | undefined,
    };
  },
});

console.log(`🚀 Server ready at: ${url}`);
```

---

## Seksi 07: Contoh Kasus Sederhana

Berikut adalah perbandingan kode resolusi naive vs pemanfaatan DataLoader pada relasi skema 1-to-N sederhana (`Post -> Author`).

### Schema Definition
```graphql
type User {
  id: ID!
  username: String!
}

type Post {
  id: ID!
  title: String!
  authorId: ID!
  author: User!
}

type Query {
  posts(limit: Int!): [Post!]!
}
```

### Naive Resolvers (N+1 Anti-Pattern)
```typescript
// ❌ SANGAT TIDAK DIREKOMENDASIKAN
export const naiveResolvers = {
  Query: {
    posts: async (_, { limit }, context: GraphQLContext) => {
      // Menghasilkan 1 Query
      const res = await context.db.query('SELECT * FROM posts LIMIT $1', [limit]);
      return res.rows;
    },
  },
  Post: {
    author: async (parentPost, _, context: GraphQLContext) => {
      // Menghasilkan N Query tambahan untuk setiap Post!
      const res = await context.db.query('SELECT * FROM users WHERE id = $1', [parentPost.authorId]);
      return res.rows[0];
    },
  },
};
```

### DataLoader Resolvers (Optimized Batching)
```typescript
// ✅ IMPLEMENTASI BENAR & OPTIMAL
export const optimizedResolvers = {
  Query: {
    posts: async (_, { limit }, context: GraphQLContext) => {
      // 1 Query ke posts
      const res = await context.db.query('SELECT * FROM posts LIMIT $1', [limit]);
      return res.rows;
    },
  },
  Post: {
    author: async (parentPost, _, context: GraphQLContext) => {
      // Batch dikonsolidasi via Microtask Queue -> 1 Query ke users
      return await context.loaders.userLoader.load(parentPost.authorId);
    },
  },
};
```

---

## Seksi 08: Implementasi Production-Grade

Berikut adalah arsitektur multi-relasi enterprise-grade (One-to-Many Batching dengan SQL Aggregation & Composite Keys) menggunakan TypeScript, Apollo Server v4, dan Node-Postgres Driver murni.

```typescript
// src/types/schema.ts
export interface Author {
  id: string;
  name: string;
  email: string;
}

export interface Book {
  id: string;
  title: string;
  authorId: string;
  publishedYear: number;
}

export interface Review {
  id: string;
  bookId: string;
  rating: number;
  comment: string;
}
```

```typescript
// src/loaders/ProductionDataLoaders.ts
import DataLoader from 'dataloader';
import { Pool } from 'pg';
import { Author, Book, Review } from '../types/schema';

export class AppDataLoaders {
  private db: Pool;

  constructor(db: Pool) {
    this.db = db;
  }

  // 1-to-1 / Many-to-1 Loader: Memetakan Book ID ke Author
  public readonly authorLoader = new DataLoader<string, Author | null>(
    async (authorIds: readonly string[]) => {
      const query = `
        SELECT id, name, email 
        FROM authors 
        WHERE id = ANY($1::uuid[])
      `;
      const result = await this.db.query<Author>(query, [authorIds as string[]]);
      const authorMap = new Map<string, Author>();
      
      result.rows.forEach((row) => authorMap.set(row.id, row));
      return authorIds.map((id) => authorMap.get(id) ?? null);
    },
    { cache: true }
  );

  // 1-to-Many Loader: Memetakan 1 Book ID ke Array Review (One-to-Many Grouping)
  public readonly reviewsByBookIdLoader = new DataLoader<string, Review[]>(
    async (bookIds: readonly string[]) => {
      const query = `
        SELECT id, book_id as "bookId", rating, comment
        FROM reviews 
        WHERE book_id = ANY($1::uuid[])
        ORDER BY id ASC
      `;
      const result = await this.db.query<Review>(query, [bookIds as string[]]);
      
      // Kelompokkan reviews ke dalam array berdasarkan bookId
      const reviewsGroupedMap = new Map<string, Review[]>();
      bookIds.forEach((id) => reviewsGroupedMap.set(id, []));
      
      result.rows.forEach((review) => {
        const group = reviewsGroupedMap.get(review.bookId);
        if (group) {
          group.push(review);
        }
      });

      return bookIds.map((id) => reviewsGroupedMap.get(id) ?? []);
    },
    { cache: true }
  );

  // Composite Key Pattern: Memetakan (AuthorId + Year) -> Total Published Books Count
  public readonly authorBookCountByYearLoader = new DataLoader<
    { authorId: string; year: number },
    number,
    string
  >(
    async (keys) => {
      // Ekstraksi array tuple untuk optimasi composite query PostgreSQL
      const authorIds = keys.map((k) => k.authorId);
      const years = keys.map((k) => k.year);

      const query = `
        SELECT author_id as "authorId", published_year as "year", count(*)::int as "total"
        FROM books
        WHERE (author_id, published_year) IN (
          SELECT unnest($1::uuid[]), unnest($2::int[])
        )
        GROUP BY author_id, published_year
      `;
      
      const result = await this.db.query<{ authorId: string; year: number; total: number }>(
        query,
        [authorIds, years]
      );

      const countMap = new Map<string, number>();
      result.rows.forEach((row) => {
        countMap.set(`${row.authorId}:${row.year}`, row.total);
      });

      return keys.map((k) => countMap.get(`${k.authorId}:${k.year}`) ?? 0);
    },
    {
      // Serialisasi key object menjadi string unik untuk cache key hashing
      cacheKeyFn: (key) => `${key.authorId}:${key.year}`,
    }
  );
}
```

```typescript
// src/graphql/resolvers.ts
import { GraphQLContext } from '../server';

export const enterpriseResolvers = {
  Query: {
    books: async (_: unknown, args: { limit: number; offset: number }, ctx: GraphQLContext) => {
      const query = `
        SELECT id, title, author_id as "authorId", published_year as "publishedYear"
        FROM books
        ORDER BY id DESC
        LIMIT $1 OFFSET $2
      `;
      const res = await ctx.db.query(query, [args.limit, args.offset]);
      return res.rows;
    },
  },
  Book: {
    author: async (parent: { authorId: string }, _: unknown, ctx: GraphQLContext) => {
      return ctx.loaders.authorLoader.load(parent.authorId);
    },
    reviews: async (parent: { id: string }, _: unknown, ctx: GraphQLContext) => {
      return ctx.loaders.reviewsByBookIdLoader.load(parent.id);
    },
  },
  Author: {
    booksPublishedInYear: async (
      parent: { id: string },
      args: { year: number },
      ctx: GraphQLContext
    ) => {
      return ctx.loaders.authorBookCountByYearLoader.load({
        authorId: parent.id,
        year: args.year,
      });
    },
  },
};
```

---

## Seksi 09: Diagram Alur Kerja

```
GraphQL Engine (Execution Phase)
   |
   |-- 1. Parse Query & Traverse AST
   |-- 2. Execute Query.books (Returns 50 Book records)
   |
   +---> Loop 50x Resolvers for Book.author
   |        |
   |        |-- Call loaders.authorLoader.load(author_1) -> Enqueue "author_1", returns Promise
   |        |-- Call loaders.authorLoader.load(author_2) -> Enqueue "author_2", returns Promise
   |        |-- ...
   |        +-- Call loaders.authorLoader.load(author_50) -> Enqueue "author_50", returns Promise
   |
   | === STACK HARUS KOSONG (MICROTASK QUEUE DRAIN) ===
   |
   +---> DataLoader Schedulers Awaken (process.nextTick / Microtask)
            |
            |-- De-duplicate unique keys: [author_1, author_2, ... unique keys]
            |-- Execute DB Query:
            |   "SELECT * FROM authors WHERE id = ANY($1)"
            |
   +<------- Result: [{id: author_1, ...}, {id: author_2, ...}]
   |
   |-- Re-order and match array index strictly
   |-- Resolve 50 Pending Promises concurrently
   v
Send JSON Response to Client
```

---

## Seksi 10: Analisis Trade-offs

| Pendekatan Optimasi | Keuntungan (Pros) | Kerugian (Cons) | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **Naive Direct Fetching** | Implementasi kode sangat cepat; tidak butuh pemahaman concurrency. | N+1 Disaster; DB CPU Spike; Latency degradasi eksponensial. | Hanya untuk skrip migrasi lokal satu-baris atau POC sederhana. |
| **DataLoader Pattern (Batching + Tick Cache)** | Mereduksi SQL round-trip ke $O(1)$ per kedalaman query; cache level request aman dari leak. | Memori heap spike sementara pada payload raksasa; kode resolver tidak decoupled murni dari batching logic. | Standar arsitektur industri utama untuk seluruh GraphQL backends. |
| **SQL Join Projection (e.g., PostGraphile / Hasura / join-monster)** | Menghasilkan single massive SQL query dengan dynamic `JOIN`; performa I/O terbaik secara teoritis. | Query plan DB raksasa berisiko lock table; query compiler kompleks; sulit mengintegrasikan multi data source / microservices. | Arsitektur Monolith SQL di mana database engine menjadi pusat logika bisnis. |
| **Global Redis Cache Lookahead** | Offload database I/O secara persisten lintas seluruh user/request. | Menambah roundtrip network Redis per field; kompleksitas *cache invalidation* masif. | Data Read-heavy statis yang jarang berubah (e.g., Master SKU Katalog). |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices (DO)
1.  **Strict Context Instantiation:** Selalu instansiasi DataLoader di dalam fungsi penghasil context request GraphQL.
2.  **Array Clamping / Batch Size Limit:** Berikan opsi `{ maxBatchSize: 1000 }` untuk mencegah query SQL melampaui limitasi parameter statement engine PostgreSQL ($65535$) atau packet data limit.
3.  **Error Propagation Handling:** Kembalikan instance `Error` per elemen array pada batch loader daripada melempar (`throw`) exception global, agar partial GraphQL failure tetap berfungsi.
4.  **Key Serialization:** Selalu berikan parameter `cacheKeyFn` jika menggunakan Object atau Composite Key sebagai loader input identifier.

### Antipatterns (DON'T)
```typescript
// ❌ 1. GLOBAL DATALOADER SINGLETON
// Mengakibatkan Memory Leak masif dan Security Leak antar User Context!
export const globalUserLoader = new DataLoader(keys => fetchUsers(keys));

// ❌ 2. BROKEN BATCH CONTRACT (Panjang array tidak sama dengan keys)
const badLoader = new DataLoader(async (ids) => {
  const users = await db.query('SELECT * FROM users WHERE id = ANY($1)', [ids]);
  return users.rows; // BUG FATAL: Jika 1 ID tidak ditemukan, seluruh mapping resolver bergeser & corrupt!
});

// ❌ 3. MUTATING INTERNAL DATALOADER CACHE ACROSS SESSIONS
app.post('/graphql', (req, res) => {
  // Menggunakan DataLoader yang sama untuk seluruh request pipeline
});
```

---

## Seksi 12: Security Hardening

Implementasi DataLoader tanpa guardrail membuka vektor serangan **Denial of Service (DoS) via Cache Exhaustion** dan **Query Depth Batch Amplification**.

### 1. Guarding Against Memory Depletion via Batch Size & Pagination Limiting
Jika seorang penyerang mengirim GraphQL Query yang mengeksploitasi nested pagination masif (contoh: 10.000 list record), DataLoader akan mencoba menyimpan 10.000 object pada heap memory.

```typescript
// Konfigurasi Security Defensif pada Loader
export function createSecureUserLoader(db: Pool) {
  return new DataLoader<string, UserRecord | null>(
    async (ids) => {
      // Sanity check hard limit
      if (ids.length > 2000) {
        throw new Error('Batch query footprint exceeded security threshold limit.');
      }
      return batchGetUsersByIds(db, ids);
    },
    {
      // Membatasi eksekusi query internal menjadi chunking 500 ID per DB statement
      maxBatchSize: 500,
    }
  );
}
```

### 2. Tenant Context Verification pada Batch Level
Mencegah kerentanan **BOLA (Broken Object Level Authorization)** saat DataLoader melakukan resolving batch secara agregat lintas tenant.

```typescript
export function createTenantAwareLoader(db: Pool, tenantId: string) {
  return new DataLoader<string, TenantData | null>(async (ids) => {
    // Kueri SELALU dipaksa diisolasi menggunakan Tenant ID yang valid dari Auth Context
    const query = `
      SELECT * FROM tenant_records 
      WHERE tenant_id = $1 AND id = ANY($2::uuid[])
    `;
    const res = await db.query(query, [tenantId, ids as string[]]);
    const map = new Map(res.rows.map((r) => [r.id, r]));
    return ids.map((id) => map.get(id) ?? null);
  });
}
```

---

## Seksi 13: Observabilitas & Debugging

Implementasikan tracing metrics kustom untuk memantau efektivitas DataLoader menggunakan Prometheus dan OpenTelemetry spans.

```typescript
import DataLoader from 'dataloader';
import { Counter, Histogram } from 'prom-client';

const dataloaderBatchSizeHistogram = new Histogram({
  name: 'graphql_dataloader_batch_size',
  help: 'Number of keys dispatched in a single dataloader batch',
  labelNames: ['loader_name'],
  buckets: [1, 5, 10, 50, 100, 250, 500],
});

const dataloaderCacheHitsCounter = new Counter({
  name: 'graphql_dataloader_cache_hits_total',
  help: 'Total dataloader in-memory cache hits',
  labelNames: ['loader_name'],
});

export function createMonitoredLoader<K, V>(
  loaderName: string,
  batchFn: (keys: readonly K[]) => Promise<(V | Error)[]>
): DataLoader<K, V> {
  const loader = new DataLoader<K, V>(async (keys) => {
    dataloaderBatchSizeHistogram.observe({ loader_name: loaderName }, keys.length);
    return batchFn(keys);
  });

  // Proxying `.load()` untuk menghitung internal cache hits
  const originalLoad = loader.load.bind(loader);
  loader.load = function (key: K): Promise<V> {
    // @ts-expect-error - Akses internal cache dataloader untuk inspeksi metrik
    if (loader._cacheMap && loader._cacheMap.has(loader._cacheKeyFn(key))) {
      dataloaderCacheHitsCounter.inc({ loader_name: loaderName });
    }
    return originalLoad(key);
  };

  return loader;
}
```

---

## Seksi 14: Benchmarking & Performance

Tolak ukur berikut mendemonstrasikan perbandingan eksekusi GraphQL Query fetching 250 records `Orders` beserta nested `User` dan `Product` details menggunakan PostgreSQL 16 (16GB RAM, 4 vCPU, Latency DB Network = 2.5ms).

### Perbandingan Karakteristik Throughput

| Metrik Evaluasi | Naive Implementation (Tanpa Loader) | DataLoader Optimized | Selisih Efisiensi |
| :--- | :--- | :--- | :--- |
| **Total DB Queries** | 501 Query | 3 Query | **-99.4% Roundtrips** |
| **Total Database Latency** | 1,252.5 ms | 7.5 ms | **167x Lebih Cepat** |
| **P99 Response Time** | 1,480 ms | 18 ms | **98.7% Reduksi Latency** |
| **Max Concurrency RPS** | 42 RPS (Pool Exhausted) | 1,280 RPS | **30.4x Throughput Scale** |
| **DB Connection Usage** | 100% Saturation (Spike) | 8% Steady Baseline | **Aman dari DB Crash** |

---

## Seksi 15: Hands-on Lab Mini-Project

### Skenario Lab
Anda ditugaskan memigrasikan backend katalog e-commerce yang mengalami crash saat flash sale. Anda harus mengimplementasikan:
1. Skema Relasional: Categories, Products, dan Inventory.
2. GraphQL Resolver yang menyelesaikan N+1 pada query katalog produk nested.

### Setup Database & Struktur
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL
);

CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  category_id UUID NOT NULL REFERENCES categories(id),
  title TEXT NOT NULL,
  price NUMERIC NOT NULL
);

-- Seed Data
INSERT INTO categories (id, name) 
VALUES ('c1111111-1111-1111-1111-111111111111', 'Electronics'),
       ('c2222222-2222-2222-2222-222222222222', 'Home & Kitchen');

INSERT INTO products (category_id, title, price)
SELECT 
  'c1111111-1111-1111-1111-111111111111',
  'Product Laptop ' || generate_series,
  1500.00
FROM generate_series(1, 100);
```

### Eksekusi Lab: Implementasi DataLoader
Lengkapi file `src/lab/catalog.ts`:

```typescript
import DataLoader from 'dataloader';
import { Pool } from 'pg';

export interface Category {
  id: string;
  name: string;
}

export interface Product {
  id: string;
  categoryId: string;
  title: string;
  price: string;
}

export class CatalogDataLoaders {
  constructor(private pool: Pool) {}

  public readonly categoryLoader = new DataLoader<string, Category | null>(
    async (categoryIds: readonly string[]) => {
      const result = await this.pool.query<Category>(
        'SELECT id, name FROM categories WHERE id = ANY($1::uuid[])',
        [categoryIds as string[]]
      );
      
      const map = new Map<string, Category>();
      result.rows.forEach((cat) => map.set(cat.id, cat));
      
      return categoryIds.map((id) => map.get(id) ?? null);
    }
  );
}

// Resolver Lab
export const catalogResolvers = {
  Query: {
    products: async (_: unknown, args: { limit: number }, ctx: { db: Pool }) => {
      const res = await ctx.db.query<Product>(
        'SELECT id, category_id as "categoryId", title, price FROM products LIMIT $1',
        [args.limit]
      );
      return res.rows;
    },
  },
  Product: {
    category: async (
      parent: Product,
      _: unknown,
      ctx: { loaders: CatalogDataLoaders }
    ) => {
      return ctx.loaders.categoryLoader.load(parent.categoryId);
    },
  },
};
```

---

## Seksi 16: Automated Testing & Verification

Automated integration test menggunakan `Jest` dan `pg-mem` / real testcontainers untuk memverifikasi secara ketat bahwa eksekusi query tidak mengalami regresi ke N+1 problem.

```typescript
// test/dataloader-regression.test.ts
import { ApolloServer } from '@apollo/server';
import { Pool } from 'pg';
import { catalogResolvers, CatalogDataLoaders } from '../src/lab/catalog';

describe('GraphQL N+1 Regression Suite', () => {
  let mockPool: Pool;
  let server: ApolloServer;
  let querySpy: jest.SpyInstance;

  beforeEach(() => {
    mockPool = new Pool();
    
    // Spy pemanggilan db pool query untuk audit I/O counter
    querySpy = jest.spyOn(mockPool, 'query');

    server = new ApolloServer({
      typeDefs: `
        type Category { id: ID!, name: String! }
        type Product { id: ID!, title: String!, category: Category }
        type Query { products(limit: Int!): [Product!]! }
      `,
      resolvers: catalogResolvers,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('harus menyelesaikan nested products dan categories hanya dalam TEPAT 2 SQL Query', async () => {
    // 1. Mock DB Result untuk Query Pertama (Products)
    querySpy.mockImplementationOnce(async () => ({
      rows: [
        { id: 'p1', categoryId: 'c1', title: 'Laptop 1' },
        { id: 'p2', categoryId: 'c1', title: 'Laptop 2' },
        { id: 'p3', categoryId: 'c2', title: 'Coffee Maker' },
        { id: 'p4', categoryId: 'c2', title: 'Blender' },
      ],
    }));

    // 2. Mock DB Result untuk Query Kedua (Batched Categories)
    querySpy.mockImplementationOnce(async () => ({
      rows: [
        { id: 'c1', name: '