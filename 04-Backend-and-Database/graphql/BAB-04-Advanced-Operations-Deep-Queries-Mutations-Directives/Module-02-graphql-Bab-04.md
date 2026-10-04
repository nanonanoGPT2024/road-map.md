# BAB-04: Advanced Operations: Deep Queries, Mutations, & Directives
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah** siklus hidup eksekusi GraphQL runtime engine (*AST Parse*, *Validation*, *Field Execution Cycle*, hingga *Value Completion*).
- **Merancang dan Mengimplementasikan** *Custom Directives* tingkat lanjut (Schema Directives via Schema Transformation & Executable Directives) untuk keperluan RBAC, masking data, dan audit logging.
- **Mengarsitekturi** mutasi transaksional enterprise yang aman, terisolasi, dan *idempotent* menggunakan *Distributed Idempotency Keys* dan mitigasi race condition.
- **Mengoptimalkan** *deeply nested queries* dan transmisi data asinkron menggunakan spesifikasi Incremental Delivery (`@defer` dan `@stream`).
- **Membangun** sistem pertahanan GraphQL engine terhadap *Query Resource Exhaustion* melalui *AST-level Static Cost Analysis* dan batasan rekursi runtime.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memahami:
- Arsitektur dasar GraphQL (Schema Definition Language/SDL, Resolvers, Type System).
- Pemahaman mendalam terkait abstraksi Abstract Syntax Tree (AST) dan *Visitor Pattern*.
- Transaksi database ACID, isolasi level (Read Committed, Repeatable Read, Serializable), dan *Pessimistic/Optimistic Concurrency Control*.
- Ekosistem TypeScript/Node.js backend modern (Apollo Server 4 atau GraphQL Yoga v5) dan layer data persistence (e.g., Prisma, Kysely, atau Knex).

---

### 3. Concept & Internal Architecture

Eksekusi GraphQL bukan sekadar pemetaan fungsi router seperti REST. Di balik sebuah request GraphQL terdapat pipeline eksekusi berbasis AST yang ketat.

```
Incoming Request (HTTP POST)
          │
          ▼
┌──────────────────┐
│   Lexer & Parser │ ──> Menghasilkan DocumentNode (AST)
└──────────────────┘
          │
          ▼
┌──────────────────┐
│ Validation Phase │ ──> Aturan Validasi (KnownTypeNames, MaxDepth, AST Cost)
└──────────────────┘
          │
          ▼
┌──────────────────┐
│ Execution Engine │
└──────────────────┘
          │
          ├─► Query: Eksekusi Root Fields secara PARALEL (Promise.all)
          │
          └─► Mutation: Eksekusi Root Fields secara SERIAL (Urut runtut)
                    │
                    ▼
          ┌──────────────────┐
          │   Sub-Resolvers  │ ──> Eksekusi Child Fields PARALEL
          └──────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │ CompleteValue()  │ ──> Type coercion, Nullability boundary check
          └──────────────────┘
```

#### A. Field Execution Cycle & Value Completion
Pada runtime GraphQL, setiap *field* dieksekusi melalui algoritma `ExecuteField`:
1. **ResolveFieldValue**: Runtime memanggil resolver fungsi target `resolve(source, args, context, info)`.
2. **CompleteValue**: Runtime mengevaluasi return value.
   - Jika field mengembalikan scalar (e.g., `String`), nilai di-*coerce* sesuai spesifikasi tipe.
   - Jika field bernilai `null` dan tipe adalah non-nullable (`String!`), *error bubble-up* dipicu hingga mencapai field nullable terdekat.
   - Jika tipe adalah `Object`, eksekusi berlanjut secara rekursif (`ExecuteFields`).

#### B. Perbedaan Semantik Eksekusi: Query vs Mutation
- **Root Fields pada Query**: Dieksekusi secara **paralel**. Resolver untuk `user`, `order`, dan `notifications` pada satu root query berjalan bersamaan via asynchronous event loop.
- **Root Fields pada Mutation**: Berdasarkan spesifikasi GraphQL Bagian 6.3.1, field tingkat root pada mutasi **wajib dieksekusi secara serial**. Field mutasi kedua tidak akan dieksekusi sebelum resolver mutasi pertama menyelesaikan Promise-nya. Namun, **child fields** dari suatu mutasi (misalnya payload kembalian yang bersarang) dieksekusi kembali secara **paralel**.

#### C. Custom Directives: Schema Transformation vs Field Execution
Directives dapat diklasifikasikan menjadi dua domain implementasi:
1. **Executable Directives**: Dipanggil oleh client di dalam dokumen kueri (e.g., `@skip`, `@include`, `@defer`).
2. **Type System (Schema) Directives**: Diterapkan di server pada SDL (e.g., `@auth`, `@mask`, `@rateLimit`). Directives ini diterapkan saat proses *schema bootstrapping* melalui pemindaian AST dan pembungkusan resolver (*resolver wrapping*) menggunakan pola Schema Transformer.

#### D. Incremental Delivery (`@defer` & `@stream`)
Mengizinkan GraphQL server untuk mengirim respons secara inkremental melalui protokol HTTP Multipart (`multipart/mixed; boundary="-"`). Server memproses data kritis terlebih dahulu (*initial response*), lalu menangguhkan (*deferred*) eksekusi cabang AST yang memiliki beban tinggi untuk dikirimkan sebagai potongan respons berikutnya melalui koneksi HTTP yang sama tanpa memblokir first-byte latency.

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (Why) | Apa yang Diterapkan (What) |
| :--- | :--- | :--- |
| **Field-Level Security** | Logika autorisasi terpusat di schema level, bukan diduplikasi di puluhan controller. | Custom Directive `@auth(requires: Role)` yang menginspeksi token konteks sebelum resolver dipanggil. |
| **Deep Query Protection** | Mencegah penyerang mengirimkan query nested ribuan lapis (Denial of Service). | AST Validation Rules (*Query Depth Limiter* & *Static Cost Analysis Engine*). |
| **Data Integrity** | Menghindari *double-spending* atau duplikasi record akibat retries jaringan HTTP. | *Transactional Mutations* dipadu dengan *Distributed Idempotency Layer* (Redis + PostgreSQL Advisory Locks). |
| **Latency Optimization** | Mencegah field dengan IO lambat memperlambat seluruh representasi payload. | *Executable Directive* `@defer` yang memecah payload GraphQL menjadi *chunked streaming frames*. |

---

### 5. How (Workflow Detail)

Alur kerja mutasi transaksional dan validasi direktif terproteksi:

```
Client               GraphQL Engine              Idempotency Cache        PostgreSQL (DB)
  │                         │                           │                        │
  │─── POST Mutation ──────>│                           │                        │
  │    (x-idempotency-key)  │                           │                        │
  │                         │── Check Key Status ──────>│                        │
  │                         │<── Key "ACQUIRED/PENDING"─│                        │
  │                         │                           │                        │
  │                         │── Check AST Directives    │                        │
  │                         │   (e.g., @auth, @validate)│                        │
  │                         │                           │                        │
  │                         │── BEGIN TRANSACTION ──────────────────────────────>│
  │                         │── Execute Root Mutation ──────────────────────────>│
  │                         │── Commit Payload ─────────────────────────────────>│
  │                         │                                                    │
  │                         │── Set Result Cached ─────>│                        │
  │                         │                           │                        │
  │<── Payload Output ──────│                           │                        │
```

1. **Client Request**: Mengirimkan mutasi dengan `Idempotency-Key` pada header HTTP.
2. **Pipeline Middleware**: Menginspeksi idempotency key di memory/Redis menggunakan operasi atomic `SET NX PX`. Jika key sudah ada dan berstatus `COMPLETED`, server mengembalikan respons cached secara langsung tanpa menjalankan GraphQL AST execution pipeline.
3. **AST Schema Visitor Execution**: Direktif `@auth` membaca security context. Jika authorization gagal, parsing dihentikan langsung pada tingkat field tersebut dan dilempar ke field error tanpa mengeksekusi child resolvers.
4. **Transaction Boundary**: Resolver mutasi membungkus operasi database dalam scope transaksi (Unit of Work). Jika salah satu operasi database gagal, seluruh mutasi di-rollback.
5. **Finalization**: Nilai respons disimpan ke layer Idempotency Cache, dan payload serial dikirim kembali ke client.

---

### 6. Analogy & Diagram ASCII

Bayangkan GraphQL engine sebagai **Jalur Inspeksi Pabrik Modern**:

```
[Bahan Mentah: Raw Query String]
               │
               ▼
[Mesin Pemindai Blue-Print: AST Parser]
               │
   ┌───────────┴───────────┐
   │ Layak secara Arsitektur?│ ──(TIDAK)──> [EJECT: GraphQLError (Syntax/Validation)]
   └───────────┬───────────┘
               │ (YA)
               ▼
[Pintu Gerbang Direktif: AST Visitor Transformer]
   ├── Cek Kartu Akses (@auth)
   ├── Cek Berat Muatan (Query Cost Analysis)
   └── Format Identitas (@mask, @trim)
               │
               ▼
[Konveyor Eksekusi Resolver]
   ├── MUTASI: Melewati lajur TUNGGAL (Serial Step-by-Step)
   │     Step 1: Deduksi Saldo ──> Step 2: Buat Pesanan
   │
   └── KUERI: Melewati lajur CABANG PARALEL (Multithread/Event-Loop)
         ├── Ambil Data Profil
         ├── Ambil Riwayat Transaksi
         └── Ambil Rekomendasi Produk
               │
               ▼
[Pengepakan Nilai: CompleteValue Engine] ──> Menjamin tidak ada data non-null bocor
               │
               ▼
[Pengiriman: JSON Payload / HTTP Multipart Stream]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Custom Executable Schema Directive (`@upper`)
Mengubah output string menjadi huruf kapital secara otomatis melalui modifikasi fungsi resolver.

```typescript
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { GraphQLSchema, defaultFieldResolver } from 'graphql';

export function upperDirectiveTransformer(schema: GraphQLSchema, directiveName: string) {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const upperDirective = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (upperDirective) {
        const { resolve = defaultFieldResolver } = fieldConfig;
        fieldConfig.resolve = async function (source, args, context, info) {
          const result = await resolve(source, args, context, info);
          if (typeof result === 'string') {
            return result.toUpperCase();
          }
          return result;
        };
        return fieldConfig;
      }
    },
  });
}
```

#### B. Practical Enterprise Example: Field-Level Authorization Directive & Idempotent Mutation Architecture

Berikut adalah implementasi skala industri menggabungkan:
1. **Schema Directive `@auth`**: Autorisasi field-level berbasis RBAC.
2. **Transactional Mutation**: Eksekusi mutasi dengan *Database Transaction Isolation* dan *Idempotency Guarantee*.

```typescript
// dependencies: @apollo/server, @graphql-tools/schema, @graphql-tools/utils, graphql
import { ApolloServer } from '@apollo/server';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { GraphQLSchema, defaultFieldResolver, GraphQLError } from 'graphql';

// 1. Definition SDL
const typeDefs = `#graphql
  directive @auth(requires: Role = USER) on FIELD_DEFINITION | OBJECT

  enum Role {
    ADMIN
    USER
    FINANCE
  }

  type BankAccount {
    id: ID!
    accountNumber: String!
    balance: Float! @auth(requires: FINANCE)
    ownerName: String!
  }

  type TransferResult {
    transactionId: ID!
    sourceBalance: Float!
    status: String!
  }

  type Query {
    account(id: ID!): BankAccount
  }

  type Mutation {
    transferFunds(
      sourceAccountId: ID!
      targetAccountId: ID!
      amount: Float!
    ): TransferResult!
  }
`;

// 2. Types & Context Interface
interface UserSession {
  userId: string;
  roles: string[];
}

interface GraphQLContext {
  user: UserSession | null;
  idempotencyKey?: string;
  db: DatabaseDriver; // Mock Database Interface
  cache: CacheDriver;       // Mock Redis Interface
}

interface DatabaseDriver {
  transaction: <T>(cb: (tx: any) => Promise<T>) => Promise<T>;
}

interface CacheDriver {
  get: (key: string) => Promise<string | null>;
  set: (key: string, val: string, ttlSec: number) => Promise<void>;
}

// 3. Directive Transformer: @auth
export function authDirectiveTransformer(schema: GraphQLSchema, directiveName: string = 'auth') {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const authDirective = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (authDirective) {
        const requiredRole = authDirective['requires'];
        const { resolve = defaultFieldResolver } = fieldConfig;

        fieldConfig.resolve = async function (source, args, context: GraphQLContext, info) {
          if (!context.user) {
            throw new GraphQLError('Unauthenticated: Access token invalid or missing', {
              extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } },
            });
          }

          if (!context.user.roles.includes(requiredRole)) {
            throw new GraphQLError(`Forbidden: Requires '${requiredRole}' role`, {
              extensions: { code: 'FORBIDDEN', http: { status: 403 } },
            });
          }

          return resolve(source, args, context, info);
        };
        return fieldConfig;
      }
    },
  });
}

// 4. Resolvers with Idempotency & DB Transaction
const resolvers = {
  Query: {
    account: async (_: unknown, { id }: { id: string }) => {
      return {
        id,
        accountNumber: 'ACC-9821-X',
        balance: 55000000.0,
        ownerName: 'Alexander Pierce',
      };
    },
  },
  Mutation: {
    transferFunds: async (
      _: unknown,
      { sourceAccountId, targetAccountId, amount }: { sourceAccountId: string; targetAccountId: string; amount: number },
      context: GraphQLContext
    ) => {
      const { idempotencyKey, db, cache } = context;

      if (!idempotencyKey) {
        throw new GraphQLError('Header Idempotency-Key is required for this operation', {
          extensions: { code: 'BAD_REQUEST', http: { status: 400 } },
        });
      }

      // 1. Idempotency Check
      const cacheKey = `idempotency:${idempotencyKey}`;
      const cached = await cache.get(cacheKey);
      if (cached) {
        return JSON.parse(cached); // Replay respons yang sudah pernah committed
      }

      // 2. Transaction Execution
      const result = await db.transaction(async (tx) => {
        // Mock atomic operations in DB
        // Menjaga urutan eksekusi serial, isolasi SELECT ... FOR UPDATE
        const txId = 'TXN-' + Math.random().toString(36).substring(2, 9).toUpperCase();
        
        // Asumsikan operasi balance deduction & deposit sukses
        const finalBalance = 55000000.0 - amount;
        if (finalBalance < 0) {
          throw new GraphQLError('Insufficient balance', {
            extensions: { code: 'INSUFFICIENT_FUNDS' }
          });
        }

        return {
          transactionId: txId,
          sourceBalance: finalBalance,
          status: 'SUCCESS',
        };
      });

      // 3. Simpan state mutasi untuk mencegah eksekusi ganda jika terjadi retry jaringan
      await cache.set(cacheKey, JSON.stringify(result), 86400); // TTL 24 Jam

      return result;
    },
  },
};

// 5. Schema Assembly
let schema = makeExecutableSchema({ typeDefs, resolvers });
schema = authDirectiveTransformer(schema, 'auth');
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Checkout Flash Sale (Platform E-Commerce Top-Tier)
- **Tantangan**: Saat flash sale, sistem menerima lonjakan 80.000 request per detik pada mutasi `checkoutCart`. Kueri klien sangat dalam (meminta detail `order -> items -> product -> seller -> tierDiscount -> voucher`).
- **Masalah Produksi**:
  1. *Resource Exhaustion*: Client pihak ketiga secara sengaja mengeksploitasi relasi siklik (`order -> user -> orders -> user...`) yang menyebabkan thread worker Node.js kehabisan memori (*OOM Crash*).
  2. *Race Condition Mutasi*: Pengurangan inventaris ganda (*inventory negative balance*) ketika user menekan tombol bayar berulang kali secara paralel.
  3. *Bottleneck Latensi*: Waktu tunggu kueri checkout lambat karena harus memverifikasi poin eksternal dan voucher anti-fraud secara sinkron.

#### Solusi Arsitektural:
```
                             [Client Request]
                                    │
                                    ▼
                     [Cloudflare / API Gateway]
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │               GraphQL Engine Gateway                   │
       │                                                        │
       │  1. AST Depth & Complexity Limit (Max Depth: 6)       │
       │  2. Redis Distributed Lock on Idempotency Key          │
       │  3. Execute Core Mutation (ACID Transaction)           │
       │  4. @defer Response Stream:                            │
       └────────────────────────────┬───────────────────────────┘
                                    │
               ┌────────────────────┴───────────────────┐
               │                                        │
               ▼ (Immediate Chunk)                      ▼ (Deferred Chunk via @defer)
    { id, status: "PENDING" }               { loyaltyPointsEarned, dynamicVouchers }
```

1. **AST Cost Analysis Filter**: Diterapkan middleware validasi sebelum query diparsing ke resolver. Setiap field memiliki bobot (e.g., scalar = 1, relasi = 5). Request dengan total cost > 150 ditolak di tepi sistem (*Fast-Reject*).
2. **Pessimistic Concurrency dengan Idempotency**: Setiap checkout dikaitkan dengan UUID `Idempotency-Key` yang di-*lock* di Redis menggunakan `SET key value NX PX 5000`. Jika mutasi sedang berjalan, request parallel identik mendapatkan kode HTTP `409 Conflict`.
3. **Penerapan `@defer`**: Resolver cart dibagi dua: Core Settlement (`id`, `orderNumber`, `paymentUrl`) dikirim segera dalam waktu 45ms, sementara field analisis diskon afiliasi yang memanggil external microservice dibungkus dalam fragment `@defer` dan di-stream 200ms kemudian.

---

### 9. Trade-offs

| Pendekatan / Teknik | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Schema Directives vs. Resolver Middleware** | Directives menyatu langsung di SDL, terdokumentasi secara eksplisit di schema, dan reusable lintas type. | Menambah kompleksitas schema compilation, debugging resolver chains menjadi lebih rumit (*abstract visitor call-stack*). |
| **Serial Execution on Mutations** | Mencegah inkonsistensi mutasi data antar field pada tingkat root dalam satu payload kueri. | Throughput rendah jika klien mengirim banyak mutasi independen dalam satu request; durasi latency bersifat kumulatif. |
| **Streaming & Incremental Delivery (`@defer`)** | Time-To-First-Byte (TTFB) sangat cepat, UX aplikasi front-end terasa sangat responsif. | Membutuhkan HTTP/2 atau HTTP/1.1 chunked transfer encoding, load balancer harus mendukung connection streaming, memori server bertahan lebih lama. |
| **Query Complexity / Depth Limiter** | Mencegah serangan Denial of Service (DoS) berbasis malicious nested queries. | Mengonsumsi siklus CPU saat fase parsing AST pada setiap request; memerlukan tuning bobot score yang akurat untuk setiap domain model. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Asumsi Bahwa Seluruh Child Field Mutasi Berjalan Serial
- **Problem**: Pengembang mengira jika mutasi bersifat serial, maka mutasi sub-field bersarang juga berjalan serial.
- **Dampak**: Race conditions pada child fields.
- **Solusi**: Hanya **root fields** dari tipe `Mutation` yang dijamin dieksekusi secara serial oleh GraphQL runtime engine. Jika ada resolver di dalam sub-object return type mutasi, field-field tersebut dieksekusi secara **paralel** (`Promise.all`). Jangan meletakkan logika mutasi state database pada child resolver.

#### 2. Kesalahan: Directives Memodifikasi Source Data Secara In-Place (Mutation Leakage)
- **Problem**: Memodifikasi object `source` langsung di dalam resolver directive wrapper.
- **Dampak**: Efek samping tak terduga (*side effects*) pada resolver saudara (*sibling fields*) yang membaca source yang sama.
- **Solusi**: Terapkan *immutable transformation*. Selalu buat salinan shallow/deep copy dari data sebelum memanipulasi nilainya.

#### 3. Kesalahan: Nullability Bubbling yang Menghancurkan Seluruh Payload
- **Problem**: Mendefinisikan semua field sebagai non-nullable (`!`) pada query bersarang dalam, lalu melemparkan unhandled error pada directive auth.
- **Dampak**: Sesuai spec GraphQL, nullability akan merambat naik ke atas (*bubble-up*). Satu field error pada kedalaman leaf node dapat membuat keseluruhan root object bernilai `null` (`"data": null`).
- **Solusi**: Terapkan aturan desain schema *Defensive Nullability Boundary*: Buat tipe leaf yang rentan terhadap failure (seperti integrasi pihak ketiga atau protected fields) bernilai nullable.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Schema Transformers Standar**: Gunakan `@graphql-tools/utils` (`mapSchema`) alih-alih memanipulasi prototipe `GraphQLSchema` secara langsung.
- [ ] **Pasang Static Query Cost Analyzer**: Terapkan library validasi seperti `graphql-cost-analysis` atau custom AST validation rules untuk menolak kueri kompleks sebelum memasuki siklus eksekusi resolver.
- [ ] **Isolasi Mutasi Database**: Setiap resolver mutasi root yang memodifikasi lebih dari satu tabel wajib berjalan di dalam transaksi unit database dengan tingkat isolasi yang ditentukan secara eksplisit.
- [ ] **Implementasikan Dynamic Timeout**: Batalkan eksekusi resolver downstream jika koneksi HTTP client terputus menggunakan `AbortController` yang dipetakan dari Node.js request `close` event ke context GraphQL.
- [ ] **Gunakan Distributed Tracing di Directives**: Pastikan setiap eksekusi directive menyuntikkan span (misal: OpenTelemetry span) untuk melacak penalti performa dari resolver wrappers.

---

### 12. Hands-on Practice

Berikut panduan langkah demi langkah implementasi *Production-grade Schema Directives & Idempotent Mutation Engine*.

#### Struktur Direktori:
Simpan file-file berikut di dalam direktori: `hands-on/m02/`
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── directives/
│   │   └── maskDirective.ts
│   ├── infrastructure/
│   │   ├── cache.ts
│   │   └── database.ts
│   ├── schema/
│   │   ├── typeDefs.ts
│   │   └── resolvers.ts
│   └── index.ts
```

#### Langkah 1: Inisialisasi Dependensi (`package.json`)
```json
{
  "name": "graphql-m02-advanced-operations",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "ts-node src/index.ts"
  },
  "dependencies": {
    "@apollo/server": "^4.10.0",
    "@graphql-tools/schema": "^10.0.3",
    "@graphql-tools/utils": "^10.1.2",
    "graphql": "^16.8.1"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

#### Langkah 2: Masking Directive Transformer (`src/directives/maskDirective.ts`)
```typescript
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { GraphQLSchema, defaultFieldResolver } from 'graphql';

export function maskDirectiveTransformer(schema: GraphQLSchema, directiveName: string = 'mask') {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const maskDirective = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (maskDirective) {
        const { resolve = defaultFieldResolver } = fieldConfig;
        const pattern: string = maskDirective['pattern'] || '*';

        fieldConfig.resolve = async function (source, args, context, info) {
          const result = await resolve(source, args, context, info);
          if (typeof result === 'string') {
            if (result.length <= 4) return pattern.repeat(result.length);
            // Sembunyikan karakter kecuali 4 digit terakhir
            const visiblePart = result.slice(-4);
            const maskedPart = pattern.repeat(result.length - 4);
            return `${maskedPart}${visiblePart}`;
          }
          return result;
        };
        return fieldConfig;
      }
    },
  });
}
```

#### Langkah 3: Database & Cache Abstraction (`src/infrastructure/cache.ts` & `src/infrastructure/database.ts`)
```typescript
// src/infrastructure/cache.ts
export class MemoryIdempotencyStore {
  private store = new Map<string, string>();

  async get(key: string): Promise<string | null> {
    return this.store.get(key) || null;
  }

  async set(key: string, value: string): Promise<void> {
    this.store.set(key, value);
  }
}

// src/infrastructure/database.ts
export class MockDatabase {
  private balances = new Map<string, number>([
    ['ACC_A', 1000000],
    ['ACC_B', 500000]
  ]);

  async runTransaction<T>(work: (balances: Map<string, number>) => Promise<T>): Promise<T> {
    // Simulasi rollback semantics dengan snapshot
    const snapshot = new Map(this.balances);
    try {
      const result = await work(this.balances);
      return result;
    } catch (error) {
      this.balances = snapshot; // Rollback
      throw error;
    }
  }

  getBalance(accountId: string): number {
    return this.balances.get(accountId) || 0;
  }
}
```

#### Langkah 4: Definisi Schema & Resolvers (`src/schema/typeDefs.ts` & `src/schema/resolvers.ts`)
```typescript
// src/schema/typeDefs.ts
export const typeDefs = `#graphql
  directive @mask(pattern: String) on FIELD_DEFINITION

  type Account {
    id: ID!
    panNumber: String! @mask(pattern: "#")
    balance: Float!
  }

  type Mutation {
    debitAccount(idempotencyKey: String!, accountId: ID!, amount: Float!): Account!
  }

  type Query {
    account(id: ID!): Account
  }
`;

// src/schema/resolvers.ts
import { GraphQLError } from 'graphql';
import { MemoryIdempotencyStore } from '../infrastructure/cache';
import { MockDatabase } from '../infrastructure/database';

export const createResolvers = (db: MockDatabase, cache: MemoryIdempotencyStore) => ({
  Query: {
    account: (_: unknown, { id }: { id: string }) => {
      const bal = db.getBalance(id);
      return {
        id,
        panNumber: '4532119988234411',
        balance: bal
      };
    }
  },
  Mutation: {
    debitAccount: async (
      _: unknown,
      { idempotencyKey, accountId, amount }: { idempotencyKey: string; accountId: string; amount: number }
    ) => {
      // 1. Idempotency Boundary
      const cached = await cache.get(idempotencyKey);
      if (cached) {
        return JSON.parse(cached);
      }

      // 2. Transaction Boundary
      const updatedAccount = await db.runTransaction(async (balances) => {
        const currentBal = balances.get(accountId);
        if (currentBal === undefined) {
          throw new GraphQLError('Account not found', { extensions: { code: 'NOT_FOUND' } });
        }
        if (currentBal < amount) {
          throw new GraphQLError('Insufficient balance for debit', {
            extensions: { code: 'UNPROCESSABLE_ENTITY' }
          });
        }

        const newBal = currentBal - amount;
        balances.set(accountId, newBal);

        return {
          id: accountId,
          panNumber: '4532119988234411',
          balance: newBal
        };
      });

      // 3. Cache Payload
      await cache.set(idempotencyKey, JSON.stringify(updatedAccount));
      return updatedAccount;
    }
  }
});
```

#### Langkah 5: Server Entrypoint Assembly (`src/index.ts`)
```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { typeDefs } from './schema/typeDefs';
import { createResolvers } from './schema/resolvers';
import { maskDirectiveTransformer } from './directives/maskDirective';
import { MockDatabase } from './infrastructure/database';
import { MemoryIdempotencyStore } from './infrastructure/cache';

async function bootstrap() {
  const db = new MockDatabase();
  const cache = new MemoryIdempotencyStore();

  let schema = makeExecutableSchema({
    typeDefs,
    resolvers: createResolvers(db, cache)
  });

  // Apply schema transformation
  schema = maskDirectiveTransformer(schema, 'mask');

  const server = new ApolloServer({
    schema
  });

  const { url } = await startStandaloneServer(server, {
    listen: { port: 4000 }
  });

  console.log(`🚀 Production Architecture GraphQL Server siap pada: ${url}`);
}

bootstrap();
```

---

### 13. Exercise

#### Level: Easy
1. Buat direktif skema `@trim` yang memeriksa setiap field bernilai tipe `String`. Jika string tersebut memiliki *leading* atau *trailing whitespace*, potong nilai tersebut secara otomatis sebelum dikirimkan ke client.

#### Level: Medium
2. Implementasikan query bersarang rekursif untuk sistem komentar beranak (`Comment -> replies -> Comment`). Tambahkan mekanisme *Validation Rule AST* kustom bernama `DepthLimitRule(maxDepth: number)` yang menolak kueri jika kedalaman rekursi kueri komentar melampaui 4 level.

#### Level: Hard
3. Buat custom executable directive `@rateLimit(limit: Int!, duration: Int!)`. Directive ini harus menginspeksi identitas IP client atau User ID dari GraphQL Context. Integrasikan dengan algoritma *Token Bucket* (menggunakan storage in-memory atau mock Redis) yang memblokir eksekusi field resolver bersangkutan dan melempar `GraphQLError` dengan extension code `TOO_MANY_REQUESTS` jika kuota limit terlampaui.

---

### 14. Challenge

**Skenario**: Sistem Transaksi Multi-Ledger Terdistribusi
Sebuah bank digital membutuhkan mutasi GraphQL tingkat tinggi: `executeSettlement(batchId: ID!, entries: [SettlementEntry!]!): SettlementBatchPayload!`.

**Persyaratan Tantangan**:
1. **Partial Failures & Error Mapping**: Mutasi menerima hingga 500 entry mutasi finansial sekaligus. Jika salah satu mutasi entitas reguler gagal, seluruh batch transaksi harus dibatalkan (*Atomic Rollback*). Namun, jika kegagalan disebabkan oleh entitas yang ditandai sebagai `optional: true`, entitas tersebut diabaikan dan sisanya tetap committed.
2. **Strict Serial Replay**: Jika client mengirimkan request yang sama dua kali karena network timeout, sistem harus mengembalikan representasi state data tanpa memicu mutasi ledger ulang dan tanpa menciptakan locking deadlock.
3. **AST Query Cost Defense**: Kueri kembalian mendukung graph data yang sangat lebar dan dalam (`SettlementBatchPayload -> auditLogs -> user -> securityContext -> devices`). Anda ditantang mendesain arsitektur resolver dan static validation rule yang membatasi eksekusi mutasi ini jika payload query response memiliki kompleksitas algoritmik melebihi $O(N^2)$ pada graph traversal.

*Instruksi*: Susun arsitektur SDL, transformer direktif, dan resolver pipeline untuk memecahkan arsitektur di atas tanpa bantuan framework third-party berbayar.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Bagaimana urutan eksekusi default pada GraphQL engine untuk Root Fields di tipe Mutation dibandingkan dengan tipe Query?**
   - A. Keduanya dieksekusi paralel secara default.
   - B. Query dieksekusi paralel, sedangkan Root Fields Mutation dieksekusi serial secara berurutan.
   - C. Query dieksekusi serial, Mutation paralel.
   - D. Keduanya wajib dieksekusi serial menurut spesifikasi.

2. **Apa yang terjadi ketika field bertipe non-nullable (`String!`) pada GraphQL resolver mengembalikan nilai `null` atau melempar eksepsi unhandled?**
   - A. Nilai diubah menjadi empty string `""` secara otomatis.
   - B. GraphQL mengabaikan field tersebut dan mengembalikan sisa data apa adanya.
   - C. Terjadi *nullability bubble-up*; error merambat ke parent field terdekat yang nullable, atau mengubah seluruh root object menjadi null jika tidak ada boundary nullable.
   - D. Koneksi HTTP langsung ditutup paksa (*terminated*) oleh server.

3. **Kapan sebuah Type System Directive (Schema Directive) dieksekusi di server?**
   - A. Pada setiap HTTP Request yang masuk saat parsing dokumen.
   - B. Saat server melakukan bootstrapping / kompilasi schema pembentukan `GraphQLSchema`.
   - C. Setelah response JSON selesai di-serialize.
   - D. Hanya saat client memanggil directive tersebut secara eksplisit di payload query.

4. **Operasi AST traversal pada GraphQL engine secara internal mengimplementasikan design pattern apa?**
   - A. Observer Pattern
   - B. Visitor Pattern
   - C. Singleton Pattern
   - D. Factory Method Pattern

5. **Apa fungsi utama dari direktif `@defer` pada spesifikasi GraphQL Incremental Delivery?**
   - A. Membatalkan kueri jika eksekusinya terlalu lambat.
   - B. Menunda eksekusi resolver tertentu agar tidak memblokir respon initial chunk payload data ke client.
   - C. Memindahkan eksekusi kueri ke thread worker background tanpa mengirim hasil ke client.
   - D. Melakukan caching otomatis pada layer Redis.

#### Intermediate (5 Soal)
6. **Jika Anda membungkus field resolver di dalam custom directive transformer, signature fungsi resolver internal apa yang harus Anda tangani agar tidak memutus execution chain?**
   - A. `(parent, args, context, info)`
   - B. `(req, res, next)`
   - C. `(root, payload)`
   - D. `(documentAst, variableValues)`

7. **Perhatikan skema berikut:**
   ```graphql
   type Mutation {
     updateProfile: User
     sendNotification: Boolean
   }
   ```
   **Jika eksekusi `updateProfile` membutuhkan waktu 300ms dan `sendNotification` butuh 100ms, berapa total waktu minimal eksekusi kedua root mutasi ini jika dipanggil bersamaan dalam satu dokumen mutasi?**
   - A. 100ms
   - B. 300ms
   - C. 400ms (kumulatif karena serial execution guarantee)
   - D. Berjalan non-deterministik tergantung event loop thread pool.

8. **Apa perbedaan mendasar antara eksekusi Executable Directive dan Schema Directive?**
   - A. Executable Directive didefinisikan di SDL; Schema Directive ditulis di dokumen client.
   - B. Executable Directive diterapkan pada operasi client query document; Schema Directive diterapkan pada deklarasi tipe skema di server.
   - C. Schema Directive tidak memiliki argumen; Executable Directive wajib memiliki argumen.
   - D. Tidak ada perbedaan, keduanya adalah istilah yang sama.

9. **Mengapa implementasi Idempotency Key pada layer mutasi GraphQL idealnya diverifikasi sebelum siklus eksekusi resolver berjalan?**
   - A. Agar GraphQL server tidak perlu mengalokasikan siklus parsing dokumen AST kueri.
   - B. Untuk menghindari deadlock memori Node.js.
   - C. Untuk mencegah *side-effects* operasi database dan mengembalikan cached payload secara langsung jika request merupakan duplikasi retry.
   - D. Karena format JSON GraphQL tidak mendukung header HTTP.

10. **Bagaimana cara kerja AST Validation Rule kustom dalam mencegah deep recursive queries?**
    - A. Menghitung kedalaman nesting kurung kurawal secara statis saat parsing DocumentNode sebelum resolver manapun dipanggil.
    - B. Mematikan server jika memori heap Node.js melampaui 80%.
    - C. Menghentikan runtime resolver saat kedalaman objek runtime database mencapai batasan tertentu.
    - D. Menghitung waktu CPU yang dihabiskan oleh request.

#### Kasus Skenario Produksi (3 Soal)
11. **Skenario Sistem Billing**:
    Sebuah aplikasi fintech memiliki mutasi `processPayment`. Klien melaporkan bahwa ketika koneksi internet seluler terputus sesaat setelah menekan tombol "Bayar", user menekan tombol tersebut kembali. Hasilnya, saldo user terpotong dua kali, namun mutasi hanya mengembalikan satu receipt ID. Investigasi menunjukkan root mutasi tidak menerapkan idempotency key dan database query menggunakan `balance = balance - amount` tanpa isolasi transaksi memadai.
    **Langkah arsitektural mutlak apa yang harus dipasang untuk merekayasa ulang mutasi ini menjadi aman secara enterprise?**
    - A. Mengubah tipe mutasi menjadi Query karena Query dieksekusi secara cepat.
    - B. Menerapkan header `Idempotency-Key` unik dari client, diverifikasi menggunakan Redis atomic lock (`SET NX`), dibungkus dalam Database Transaction dengan isolation level Serializable atau pessimistic lock (`SELECT FOR UPDATE`), serta menyimpan cache hasil mutasi tersebut.
    - C. Menambahkan timeout 500ms pada client agar user tidak bisa menekan tombol dua kali.
    - D. Membagi mutasi ke dalam dua sub-field GraphQL terpisah.

12. **Skenario Memory Exhaustion (OOM)**:
    Engine GraphQL Apollo Server Anda mengalami restart terus menerus (crash OOM) saat diuji beban oleh tim QA. Dokumen kueri yang dikirimkan tim QA ternyata mengeksploitasi fragment rekursif:
    ```graphql
    fragment UserLoop on User {
      friends {
        ...UserLoop
      }
    }
    ```
    Resolver tidak pernah melempar error, namun proses langsung terminated.
    **Apa mitigasi teknis paling tepat di layer GraphQL runtime engine?**
    - A. Memasang load balancer tambahan di depan server.
    - B. Menghapus tipe `friends` dari skema.
    - C. Menerapkan AST validation rule `known-fragment-names` dan memasang mekanisme validasi statis batasan kedalaman kueri (*max depth validation*) sebelum runtime mengeksekusi resolvers pipeline.
    - D. Menambah alokasi RAM server menjadi 64GB.

13. **Skenario Data Masking Leakage**:
    Anda menerapkan directive `@mask` untuk menyamarkan nomor kartu kredit pada field `CreditCard.pan`. Namun, tim audit mendapati bahwa ketika field tersebut dipanggil bersamaan dengan inline fragment bertingkat:
    ```graphql
    ... on CreditCard {
      pan
    }
    ```
    Data tampil tanpa masking pada log elasticsearch gateway, meskipun di response client termasking dengan benar. Ternyata ada logging middleware GraphQL yang membaca `info.fieldNodes` langsung dari AST mentah tanpa melewati wrapper directive transformer.
    **Di mana seharusnya posisi sanitasi data logging yang benar pada arsitektur GraphQL?**
    - A. Di client side saja sebelum render UI.
    - B. Logging data payload tidak boleh membaca raw AST atau raw DB record; logging harus dilakukan pada fase formatting response akhir (`formatResponse` hook / wrapper execution) setelah seluruh pipeline directive transformers dan resolvers selesai mengembalikan sanitized values.
    - C. Matikan semua sistem logging di server produksi.
    - D. Ubah tipe SDL `pan` menjadi `Int`.

---

#### Kunci Jawaban & Evaluasi

1. **B**: Sesuai spesifikasi resmi GraphQL, field pada tipe `Query` dieksekusi secara paralel untuk mengoptimalkan latensi I/O, sementara field pada tingkat root di tipe `Mutation` wajib dieksekusi secara serial guna menjamin konsistensi perubahan status (state mutations).
2. **C**: Prinsip dasar penanganan error GraphQL pada field non-nullable adalah *Error Bubbling*; jika field `!` menghasilkan null, maka parent container-nya dianggap tidak valid dan nilainya diubah menjadi null hingga mencapai nullable field terdekat.
3. **B**: Schema directives diterapkan saat kompilasi schema awal (bootstrapping) menggunakan teknik modifikasi resolver melalui Schema Visitor/Transformer.
4. **B**: GraphQL compiler mengurai kueri menjadi AST dan menggunakan *Visitor Pattern* (`enter` dan `leave` hooks) untuk memeriksa atau memvalidasi node dokumen.
5. **B**: `@defer` memungkinkan fragmen query yang lambat dikirim secara bertahap via multipart payload HTTP response tanpa memblokir transfer data awal.
6. **A**: Standar field resolver pada GraphQL engine menerima 4 argumen: `(source/parent, args, context, info)`.
7. **C**: Karena spesifikasi menjamin serial root mutation execution, durasi eksekusinya diakumulasi: 300ms + 100ms = 400ms.
8. **B**: Executable Directives ditulis pada dokumen operasi client (`query MyQ { field @skip }`), sedangkan Type System / Schema Directives didefinisikan dan dieksekusi di SDL backend server (`type User { email: String @auth }`).
9. **C**: Memeriksa idempotency key di awal pipeline mencegah duplikasi mutasi transaksional ke database dan menghemat resource komputasi dengan merespons balik hasil kalkulasi sebelumnya yang telah tersimpan.
10. **A**: Validasi AST berjalan statis pada representasi tree sebelum runtime memanggil siklus resolver manapun.
11. **B**: Solusi enterprise untuk mutasi finansial wajib menyatukan *Distributed Idempotency Layer* di tepi aplikasi dan *ACID Transactions / Row Locks* pada layer data persistence.
12. **C**: Validasi statis AST terhadap batas kedalaman (*max depth*) dan fragment cycle analysis secara langsung menolak dokumen kueri sebelum eksekusi dimulai, melindungi CPU dan Event Loop dari jebakan tak terhingga (*infinite loops*).
13. **B**: Logging harus mengonsumsi final sanitized/masked payload yang dihasilkan oleh *Value Completion stage* pada lifecycle GraphQL, bukan dari data sumber mentah sebelum diproses oleh directive pipeline.

---

### 16. Summary

Implementasi lanjutan GraphQL pada skala enterprise menuntut pemahaman mendalam tentang **internal pipeline eksekusi**:
1. **Perilaku Root Mutations**: Selalu dieksekusi secara serial, berbeda dengan queries yang berjalan secara paralel. Namun, resolver anak di dalam tipe kembalian mutasi tetap berjalan secara paralel.
2. **Schema Transformation**: Custom Schema Directives dieksekusi saat server bootstrapping untuk memodifikasi fungsi eksekusi resolver (*resolver decoration*), menjadikannya instrumen yang tepat untuk standarisasi *Cross-Cutting Concerns* seperti RBAC dan masking data.
3. **Resiliensi Operasi Finansial**: Membutuhkan kombinasi mutasi transaksional database yang ketat dan lapisan *Idempotency Cache* terdistribusi guna mencegah race condition dan mutasi ganda akibat *network retries*.
4. **Proteksi AST**: Mengamankan arsitektur GraphQL produksi memerlukan pertahanan statis (*Static Query Cost & Depth Analysis*) sebelum siklus eksekusi field dimulai untuk mencegah eksploitasi DoS pada relasi graf yang dalam.