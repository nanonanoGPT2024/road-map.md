# BAB 03: Resolvers Architecture & Execution Engine Internals
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Algoritma Eksekusi GraphQL Spec**: Memahami secara presisi bagaimana GraphQL engine memproses dokumen kueri dari AST (*Abstract Syntax Tree*), melewati fase validasi, *field collection*, hingga fase eksekusi bertingkat (*breadth-first concurrent promise resolution*).
2. **Menguasai Lifecycle Field Resolution & Microtask Scheduling**: Mengidentifikasi bagaimana JavaScript/Node.js Event Loop berinteraksi dengan resolver asynchronous, manipulasi microtask queue, dan mekanisme penjadwalan `DataLoader`.
3. **Mendesain Enterprise-Grade Resolver Middleware Pipeline**: Mengimplementasikan arsitektur resolver berbasis komposisi modular (*higher-order resolvers*, schema directives, atau plugins) untuk *cross-cutting concerns* seperti RBAC/ABAC, tracing, validasi payload, dan context propagation.
4. **Menerapkan Mitigasi Risiko Runtime Produksi**: Mengontrol konkurensi resolver, mencegah kehabisan memori (*heap out-of-memory*) akibat eksploitasi kueri deeply nested, dan mengisolasi kegagalan parsial (*partial failure handling*) sesuai spesifikasi resmi RFC GraphQL.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental AST GraphQL: Memahami bagaimana kueri diurai menjadi representasi pohon objek (*Parsing*, *Validation*, *AST Nodes*).
* Model Konkurensi Node.js: Event Loop, Call Stack, Task (Macrotask) Queue, dan Microtask Queue (`Promise.then`, `queueMicrotask`, `process.nextTick`).
* Pemrograman TypeScript Lanjutan: Generics, Mapped Types, Higher-Order Functions, dan Async Iterators.
* Pengalaman mengimplementasikan schema GraphQL dasar menggunakan `graphql-js`, `@graphql-tools`, atau framework setara (Apollo Server, Yoga, NestJS GraphQL).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 GraphQL Spec Execution Algorithm
Berdasarkan spesifikasi resmi GraphQL (Section: *Execution*), engine eksekusi beroperasi menggunakan serangkaian fungsi internal deterministik. Alur pemrosesan GraphQL tidak bekerja layaknya MVC tradisional, melainkan melalui pipeline berbasis evaluasi pohon:

```
Document AST
     │
     ▼
[Validate] ──(Invalida)──> Return GraphQLError[]
     │
     ▼ (Valid)
[ExecuteRequest()]
     │
     ├─► Build ExecutionContext (Schema, VariableValues, Errors, Context)
     │
     └─► [ExecuteQuery() / ExecuteMutation()]
              │
              └─► [ExecuteSelectionSet()]
                       │
                       ├─► [CollectFields()] (Menggabungkan inline & named fragments)
                       │
                       └─► Loop setiap Field:
                             │
                             └─► [ExecuteField()]
                                      │
                                      ├─► ResolveField() -> Panggil Resolver User
                                      │
                                      └─► [CompleteValue()]
                                               │
                                               ├─► Scalar/Enum: Koersi data
                                               ├─► List: Resolve concurrently via Promise.all()
                                               └─► Object: Rekursif ke [ExecuteSelectionSet()]
```

#### 3.2 Field Collection & Name Collisions
Engine tidak langsung mengeksekusi field satu per satu saat membaca AST. Tahap pertama dari evaluasi selection set adalah `CollectFields()`.
* **Grouping**: Semua field dengan nama respons yang sama (*response key*, baik berupa nama asli field maupun *alias*) dikelompokkan menjadi satu set eksekusi.
* **Directives Evaluation**: Engine mengevaluasi direktif bawaan `@include(if: ...)` dan `@skip(if: ...)`. Jika kondisi bernilai false untuk `@include` atau true untuk `@skip`, AST node tersebut dipangkas dari execution list sebelum resolver dipanggil.
* **Fragment Merging**: Inline fragment (`... on User`) dan Fragment Spread (`...UserFields`) yang target tipenya kompatibel dengan objek runtime saat ini akan diekspansi dan digabungkan ke dalam grup field yang relevan.

#### 3.3 CompleteValue: Scalar vs Complex Type & Coercion
Setelah fungsi resolver resolver pengguna mengembalikan nilai mentah (*raw value*), engine memanggil fungsi internal `CompleteValue()`:
* **Leaf Node (Scalar / Enum)**: Nilai melalui tahap *Result Coercion* via metode `serialize()` dari scalar type terkait. Jika melempar error atau mengembalikan nilai non-serializable, error dibungkus menjadi `GraphQLError` dan disisipkan ke array `errors`.
* **List (Array)**: Setiap elemen di dalam array diselesaikan secara independen. Jika resolver mengembalikan `Promise<Array>`, engine menunggu array selesai di-resolve, kemudian menjalankan `CompleteValue()` pada masing-masing item secara paralel:
  $$\text{Completion}(\text{List}) = \text{Promise.all}(\text{items.map}(i \implies \text{CompleteValue}(i)))$$
* **Object / Interface / Union**: Engine menentukan tipe konkrit objek runtime melalui mekanisme `__resolveType` (jika bertipe Interface/Union), lalu memanggil `ExecuteSelectionSet()` secara rekursif dengan objek baru tersebut sebagai argumen `source` (atau `parent`/`rootValue`) untuk resolver level anak.

#### 3.4 Non-Null Propagation
Salah satu karakteristik arsitektur GraphQL yang paling destruktif terhadap payload respons adalah propagasi non-null (`Non-Null Type Modifiers` bernilai `!`).
* Jika sebuah field didefinisikan sebagai non-null (`String!`, `User!`) dan resolver mengembalikan `null` atau melemparkan error yang tidak ditangani:
  1. Engine mendeteksi pelanggaran kontrak tipe non-null pada field tersebut.
  2. Nilai field tidak dapat diisi `null`.
  3. Engine menaikkan (*bubble up*) error tersebut ke parent object.
  4. Parent object tersebut dipaksa bernilai `null`.
  5. Jika parent object tersebut juga didefinisikan sebagai non-null di level kakeknya, pembatalan terus merambat ke atas hingga menemukan field yang nullable.
  6. Skenario terburuk: Jika seluruh jalur hingga root field bertipe non-null, field `data` di respons HTTP akan bernilai `null` secara keseluruhan: `{"data": null, "errors": [...]}`.

#### 3.5 Interaksi Concurrency & Microtask Queue
Node.js engine mengeksekusi resolver bertingkat tanpa thread worker tambahan, sepenuhnya bergantung pada libuv dan V8 Microtask Queue.

Ketika sebuah resolver menghasilkan `Promise`, eksekusi percabangan tersebut ditunda. Engine mendaftarkan callback kelanjutan ke Microtask Queue. Ini berarti:
1. Seluruh resolver sinkronus pada level yang sama dieksekusi terlebih dahulu dalam Call Stack.
2. Ketika Call Stack kosong, V8 menguras (*drains*) Microtask Queue.
3. Semua Promise yang *settled* akan melanjutkan eksekusinya ke level resolver anak berikutnya secara simultan.

```
[Call Stack]
  │ executeSelectionSet(Root)
  │  ├── resolver A (Async) ────┐ (Didaftarkan ke Microtask)
  │  └── resolver B (Async) ────┤
  │                             ▼
[Microtask Queue] ──────> [Resolver A Done] ──► executeSelectionSet(Child A)
                  ──────> [Resolver B Done] ──► executeSelectionSet(Child B)
```

Di sinilah `DataLoader` bekerja: `DataLoader` memanfaatkan `process.nextTick()` atau microtask execution tick untuk menahan (*batching*) request individual yang dipanggil secara sinkronus pada tick yang sama sebelum mengeksekusi batch query tunggal ke database.

---

### 4. Why & What

| Dimensi | Mengapa Arsitektur Resolver Penting? | Apa Dampak di Tingkat Produksi? |
| :--- | :--- | :--- |
| **I/O Optimization** | Resolver anak dieksekusi tanpa mengetahui kueri resolver saudara (*sibling*), menyebabkan ledakan request N+1 secara natural. | Tanpa batching di execution layer, 1 kueri GraphQL dapat memicu ratusan kueri I/O ke database/downstream service dalam hitungan milidetik. |
| **Resilience & Fault Isolation** | GraphQL mendukung *Partial Success* (data parsial dikembalikan bersamaan dengan array error). | Konfigurasi nullability yang salah dapat menghancurkan seluruh pohon respons (Null Bubbling) hanya karena kegagalan field non-kritis. |
| **Resource Consumption** | GraphQL engine secara dinamis membuat representasi memori untuk setiap node yang dikunjungi dalam pohon AST. | Kueri kompleks bersarang dalam volume tinggi memicu fragmentasi heap V8, garbage collection pauses (stop-the-world), dan latensi CPU spike. |
| **Security & Governance** | Otorisasi berbasis endpoint (REST) tidak berlaku karena GraphQL hanya memiliki single endpoint `/graphql`. | Resolver harus menjadi security boundary mandiri melalui pipeline composable middleware untuk menegakkan RBAC/ABAC di level field. |

---

### 5. How (Workflow Detail)

Berikut adalah siklus hidup rinci dari satu kueri GraphQL tingkat lanjut dari saat payload HTTP diterima hingga respons dipancarkan kembali ke client:

```
Client Request
      │ (POST /graphql { query, variables })
      ▼
1. HTTP Body Parsing & De-serialization
      │
      ▼
2. Lexing & Parsing (Source Text ──► Document AST)
      │
      ▼
3. AST Validation (Against Compiled GraphQLSchema)
      ├─ Rules: KnownTypeNames, MaxDepth, ComplexityValidator
      └─ Check: Syntax valid? Selection sets compatible?
      │
      ▼ (Valid)
4. Execution Context Initialization
      ├─ schema: Skema GraphQL terkompilasi
      ├─ fragments: Map dari AST FragmentDefinitions
      ├─ rootValue: Nilai awal (bisa null/empty)
      ├─ contextValue: Request scope state (Auth, DB Connections, DataLoaders)
      ├─ variableValues: Nilai variabel yang telah dikoersi
      └─ errors: Array penampung GraphQLError runtime
      │
      ▼
5. ExecuteOperation (Query / Mutation / Subscription)
      │
      ▼
6. Recursive Field Execution Engine
      │
      ├─► Step A: `CollectFields()` untuk tipe target
      │
      ├─► Step B: Iterasi paralel setiap `ResponseKey`:
      │     │
      │     ├─ 1. Eksekusi Resolver Pipeline:
      │     │    [AuditLog] ──► [AuthGuard] ──► [InputValidation] ──► [User Resolver]
      │     │
      │     ├─ 2. User Resolver mengembalikan Promise (e.g., DataLoader load)
      │     │
      │     ├─ 3. Microtask queue me-resolve Promise
      │     │
      │     ├─ 4. Eksekusi `CompleteValue()`:
      │     │    ├─ Cek Nullability Violation
      │     │    ├─ Format / Koersi Type Scalar
      │     │    └─ Jika Object/List: Kembali rekursif ke Step A untuk child fields
      │     │
      │     └─ 5. Sisipkan data ter-resolve ke Result Map
      │
      ▼
7. Sanitasi & Filtering
      ├─ Filter null bubbling
      ├─ Format error extensions (strip stack trace jika environment = production)
      └─ Hitung metrik tracing (OpenTelemetry span end)
      │
      ▼
8. JSON Serialization & HTTP Response Transmission
      └─ Payload: { "data": { ... }, "errors": [ ... ] }
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengantaran Pesanan Restoran Multi-Departemen
Bayangkan GraphQL Execution Engine sebagai tim pelayan di restoran fine-dining:
* **AST Kueri**: Lembar pesanan pelanggan berjenjang (*Order Form*): "Saya minta Meja 4, hidangkan Steak, dan untuk setiap Steak tolong bawakan Saus Khusus dan daftar Bahan Pembuat Saus tersebut."
* **CollectFields**: Kepala Pelayan (*Head Waiter*) mengelompokkan pesanan. Jika ada dua catatan terpisah yang meminta "Saus Khusus", mereka digabung agar koki tidak memasak dua kali untuk pesanan yang identik.
* **Resolver**: Pelayan individual pergi ke stasiun kerja berbeda (Dapur Utama, Bar Minuman, Gudang Bahan). Mereka bergerak serentak (*asynchronous concurrency*).
* **DataLoader**: Pelayan tidak pergi ke gudang setiap kali ada 1 pesanan saus. Mereka menunggu sejenak (microtask tick) hingga semua pelayan meja lain selesai mendata pesanan, lalu satu kurir pergi ke gudang mengambil semua botol saus sekaligus (*batching*).
* **Null Bubble**: Jika pelanggan memesan paket "Steak Premium Wajib Lengkap" (*Non-Null*), namun bahan saus ternyata busuk (*resolver failure*), kepala pelayan tidak bisa menyajikan paket steak tersebut sebagian. Seluruh paket steak dibatalkan dan ditarik dari meja (*bubbled up to null*).

#### Diagram Eksekusi Konkuren AST & DataLoader

```
                       [Query: organization(id: "org-1")]
                                       │
                                       ▼
                   ┌───────────────────────────────────────┐
                   │ Resolver: Query.organization          │
                   │ (Fetch DB: SELECT * FROM orgs...)     │
                   └──────────────────┬────────────────────┘
                                      │ (Returns Org Object)
                                      ▼
                   ┌───────────────────────────────────────┐
                   │ Resolver: Organization.departments    │
                   │ (Fetch DB: SELECT * FROM depts...)    │
                   └──────────────────┬────────────────────┘
                                      │ (Returns 3 Departments)
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   [Department 1]               [Department 2]               [Department 3]
         │                            │                            │
   Field: members               Field: members               Field: members
         │                            │                            │
  userLoader.load(101)         userLoader.load(102)         userLoader.load(103)
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      │
                         (EVENT LOOP: Microtask Drain)
                                      │
                                      ▼
                   ┌───────────────────────────────────────┐
                   │ DataLoader Batch Function Executed    │
                   │ SELECT * FROM users WHERE id IN       │
                   │ (101, 102, 103)                       │
                   └──────────────────┬────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   (Resolves 101)               (Resolves 102)               (Resolves 103)
   dept1.members                dept2.members                dept3.members
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Low-Level Engine Execution Manual
Contoh ini mendemonstrasikan bagaimana kueri dieksekusi langsung menggunakan core function `graphql-js` tanpa server abstraction (Express/Apollo), memperlihatkan kontrol context dan execution root.

```typescript
// execution-engine-raw.ts
import { 
  parse, 
  validate, 
  execute, 
  GraphQLSchema, 
  GraphQLObjectType, 
  GraphQLString, 
  GraphQLNonNull 
} from 'graphql';

// 1. Skema Tingkat Rendah
const UserType = new GraphQLObjectType({
  name: 'User',
  fields: {
    id: { type: new GraphQLNonNull(GraphQLString) },
    name: { type: GraphQLString },
  },
});

const QueryType = new GraphQLObjectType({
  name: 'Query',
  fields: {
    me: {
      type: UserType,
      resolve: (_source, _args, context) => {
        // Resolver menerima context yang diinjeksi runtime
        if (!context.authUserId) {
          throw new Error('UNAUTHENTICATED');
        }
        return { id: context.authUserId, name: 'Octocat Core' };
      },
    },
  },
});

const schema = new GraphQLSchema({ query: QueryType });

// 2. Kueri String
const sourceQuery = `
  query GetMe {
    me {
      id
      name
    }
  }
`;

// 3. Execution Pipeline Manual
async function run() {
  const documentAST = parse(sourceQuery);
  const validationErrors = validate(schema, documentAST);

  if (validationErrors.length > 0) {
    console.error('Validation Errors:', validationErrors);
    return;
  }

  const executionResult = await execute({
    schema,
    document: documentAST,
    contextValue: { authUserId: 'usr_enterprise_9988' }, // Injection Context
  });

  console.log('Result Data:', JSON.stringify(executionResult, null, 2));
}

run().catch(console.error);
```

#### 7.2 Practical Example: Enterprise-Grade Resolver Architecture
Arsitektur produksi berikut menggunakan middleware pattern (*Higher-Order Resolvers*), isolasi DataLoader per request via context factory, serta *structured error handling* berbasis RFC spec.

```typescript
// enterprise-resolvers.ts
import DataLoader from 'dataloader';
import { GraphQLResolveInfo, GraphQLError } from 'graphql';

// -------------------------------------------------------------
// Type Definitions & Context Contract
// -------------------------------------------------------------
export interface CurrentUser {
  id: string;
  tenantId: string;
  roles: string[];
}

export interface GraphQLContext {
  currentUser: CurrentUser | null;
  requestId: string;
  loaders: {
    userLoader: DataLoader<string, UserEntity>;
  };
}

export interface UserEntity {
  id: string;
  tenantId: string;
  name: string;
  email: string;
}

export type GraphQLFieldResolver<TSource, TArgs, TResult> = (
  source: TSource,
  args: TArgs,
  context: GraphQLContext,
  info: GraphQLResolveInfo
) => Promise<TResult> | TResult;

// -------------------------------------------------------------
// Higher-Order Resolver Middlewares (Composition Pipeline)
// -------------------------------------------------------------

// Middleware 1: Enforce Authentication & ABAC
export function requireAuth<TSource, TArgs, TResult>(
  next: GraphQLFieldResolver<TSource, TArgs, TResult>
): GraphQLFieldResolver<TSource, TArgs, TResult> {
  return (source, args, context, info) => {
    if (!context.currentUser) {
      throw new GraphQLError('Akses ditolak: Autentikasi diperlukan.', {
        extensions: {
          code: 'UNAUTHENTICATED',
          http: { status: 401 },
          requestId: context.requestId,
        },
      });
    }
    return next(source, args, context, info);
  };
}

// Middleware 2: Guard Role (RBAC)
export function requireRoles<TSource, TArgs, TResult>(
  roles: string[],
  next: GraphQLFieldResolver<TSource, TArgs, TResult>
): GraphQLFieldResolver<TSource, TArgs, TResult> {
  return (source, args, context, info) => {
    const user = context.currentUser;
    if (!user || !roles.some((r) => user.roles.includes(r))) {
      throw new GraphQLError('Akses ditolak: Hak akses tidak mencukupi.', {
        extensions: {
          code: 'FORBIDDEN',
          http: { status: 403 },
          requiredRoles: roles,
          requestId: context.requestId,
        },
      });
    }
    return next(source, args, context, info);
  };
}

// -------------------------------------------------------------
// DataLoader Factory (Scoped per HTTP Request untuk mencegah cross-tenant leak)
// -------------------------------------------------------------
export function createUserDataLoaders(tenantId: string) {
  return {
    userLoader: new DataLoader<string, UserEntity>(
      async (userIds: readonly string[]): Promise<(UserEntity | Error)[]> => {
        // Simulasi query batching SQL: SELECT * FROM users WHERE tenant_id = ? AND id IN (...)
        const users = await mockDatabaseBatchFetch(tenantId, userIds);
        
        // PENTING: DataLoader mewajibkan mengembalikan array dengan urutan dan panjang identik
        const userMap = new Map(users.map((u) => [u.id, u]));
        return userIds.map((id) => 
          userMap.get(id) || new Error(`User [${id}] tidak ditemukan`)
        );
      },
      {
        cache: true, // Memory cache hanya hidup selama siklus HTTP request ini
      }
    ),
  };
}

// Mock Database Fetcher
async function mockDatabaseBatchFetch(tenantId: string, ids: readonly string[]): Promise<UserEntity[]> {
  return ids.map((id) => ({
    id,
    tenantId,
    name: `User ${id}`,
    email: `${id}@enterprise.internal`,
  }));
}

// -------------------------------------------------------------
// Production-Ready Resolvers Implementation
// -------------------------------------------------------------
export const resolvers = {
  Query: {
    userProfile: requireAuth(
      async (_source: unknown, args: { id: string }, context: GraphQLContext) => {
        try {
          return await context.loaders.userLoader.load(args.id);
        } catch (error: any) {
          throw new GraphQLError('Gagal mengambil data user', {
            originalError: error,
            extensions: {
              code: 'DATA_RETRIEVAL_ERROR',
              targetId: args.id,
            },
          });
        }
      }
    ),
    tenantAuditReport: requireAuth(
      requireRoles(['ADMIN', 'AUDITOR'], async (_source: unknown, _args: unknown, context: GraphQLContext) => {
        return {
          generatedAt: new Date().toISOString(),
          status: 'SUCCESS',
          tenantId: context.currentUser!.tenantId,
        };
      })
    ),
  },
  User: {
    // Resolver field-level: Mengatasi komputasi berat secara on-demand
    sensitiveAuditHash: requireRoles(['ADMIN'], (parent: UserEntity) => {
      // Hanya dieksekusi jika field diminta dalam kueri
      return `HASH_${parent.id}_${parent.tenantId}`;
    }),
  },
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Gateway B2B E-Commerce Global (Scale: 60,000 RPS)
* **Latar Belakang**: Sebuah platform multi-tenant enterprise memproses transaksi dari marketplace partner. Satu halaman dasbor memuat katalog produk, status inventory, histori pesanan, dan verifikasi harga secara dinamis melalui kueri GraphQL federasi bersarang setinggi 7 tingkat.
* **Insiden (Outage)**: Saat flash sale, latency p99 melonjak dari 120ms ke 12,800ms. Node.js heap memory membengkak secara drastis, memicu *V8 Mark-Sweep Garbage Collection pauses* selama 4 hingga 7 detik, yang berujung pada HTTP 504 Gateway Timeouts dan *cascading crash* di 40 pod server.

#### Analisis Akar Masalah (Root Cause Analysis - RCA)
1. **Unbounded List Resolution Tanpa Pagination Cursor Guard**: Kueri kustom klien meminta `orders { items { warehouse { inventoryLogs { ... } } } }`. Satu akun memiliki 40,000 histori item. GraphQL engine mengalokasikan 40,000 resolver anak secara simultan melalui `Promise.all()`.
2. **DataLoader Cross-Batching Deadlock**: DataLoader dibuat secara global sebagai singleton (bukan per request). Data antar-tenant saling bocor (*security vulnerability*), dan memory cache DataLoader tidak pernah terhapus (*memory leak*).
3. **Partial Failure Explosion**: Resolving field pihak ketiga (misalnya kalkulator pajak eksternal) berstatus non-null (`TaxCalculation!`). Ketika API perpajakan downstream timeout, error me-nullify seluruh root `Order`, menghilangkan semua data order yang sebenarnya berhasil di-fetch.

#### Solusi Arsitektur
1. **Strict Cost & Depth Limiting Engine**:
   Diimplementasikan AST validation rule sebelum engine mencapai tahap `ExecuteRequest()`:
   * Batas kedalaman kueri (Max Depth): Dibatasi maksimal 5 level.
   * Analisis Kompleksitas Kueri (*Query Complexity Analysis*): Field skalar diberi bobot 1, list tanpa batas ditolak, list terpaginasi diberi bobot `first * child_cost`. Jika total kompleksitas > 1000 poin, kueri di-reject pada fase validasi (0ms execution time).
2. **Context-Scoped DataLoader Pipeline**:
   Setiap HTTP request menginstansiasi instance `DataLoader` baru via context factory. Instance dibuang secara otomatis bersama siklus hidup garbage collection request.
3. **Resilience Pattern via RFC Nullability Contract**:
   Field integrasi downstream diubah menjadi nullable (`TaxCalculation`). Ditambahkan fallback resolver: jika microservice pajak gagal, resolver mengembalikan `null` dan mencatat error ke array `errors` dengan kode `DOWNSTREAM_SERVICE_UNAVAILABLE`. Frontend tetap menerima 95% data transaksi lainnya.
4. **Hasil**:
   * P99 latency turun kembali ke 85ms.
   * Memory usage pod stabil pada 350MB (tanpa GC spike).
   * Nilai Availability SLA naik menjadi 99.99%.

---

### 9. Trade-offs (Arsitektur & Eksekusi)

| Pendekatan / Keputusan | Keuntungan | Biaya / Konsekuensi Negatif | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **DataLoader Per-Request vs Singleton** | Menghilangkan risiko memory leak; isolasi data multi-tenant terjamin 100%. | Overhead alokasi memori untuk instansiasi map DataLoader baru di setiap request. | **Wajib di Production.** Tidak ada kompromi demi keamanan data tenant. |
| **Non-Null Type (`!`) vs Nullable** | Kontrak schema kuat; client UI tidak perlu melakukan pengecekan `null` berulang pada setiap field. | Rentan *Null Bubbling Cascade*; satu field mati dapat merusak seluruh payload respons. | Gunakan `!` hanya pada field atomik yang pasti ada di database utama (e.g., `id`, `createdAt`). Hindari pada downstream/microservice calls. |
| **Query Complexity Validation vs Execution Timeout** | Memutus kueri berbahaya secara statis (AST parsing time) sebelum database disentuh; nol resource database terbuang. | Membutuhkan pemeliharaan bobot (cost mapping) yang presisi; menolak kueri sah jika batas kalkulasi terlalu ketat. | Wajib untuk Public/Partner API. |
| **Schema Directives vs Middleware Pipeline** | Deklaratif; konfigurasi keamanan langsung terlihat di file schema `.graphql`. | Sulit didebug secara statis menggunakan standard TypeScript typing; tight-coupling ke parsing tools skema. | Pipeline fungsi komposisi TypeScript lebih dipilih untuk arsitektur enterprise modern berbasis code-first. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Anti-Pattern: Melakukan `await` di dalam Loop Resolving Manual
* **Kode Buruk**:
  ```typescript
  // Buruk: Mengubah eksekusi paralel menjadi sekuensial!
  const resolvers = {
    Author: {
      books: async (parent) => {
        const bookIds = await getBookIdsForAuthor(parent.id);
        const books = [];
        for (const id of bookIds) {
          // Blocking Event Loop: Menunggu I/O satu per satu
          const book = await fetchBookById(id);
          books.push(book);
        }
        return books;
      }
    }
  };
  ```
* **Solusi**: Manfaatkan `Promise.all()` atau delegasikan ke `DataLoader` untuk menjamin proses berjalan konkuren:
  ```typescript
  // Benar: Resolving konkuren via Microtask Queue
  const resolvers = {
    Author: {
      books: (parent, _args, context) => {
        return context.loaders.booksByAuthorLoader.load(parent.id);
      }
    }
  };
  ```

#### 2. Anti-Pattern: Menggunakan Mutasi Objek Global pada `context`
* **Gejala**: Data otentikasi user A terbaca oleh user B di bawah beban traffic tinggi (*Race Condition*).
* **Penyebab**: Context GraphQL dioper sebagai referensi objek singleton atau di-cache secara global.
* **Solusi**: Context factory harus selalu mengembalikan objek literal baru pada setiap penanganan request HTTP:
  ```typescript
  // Framework Context Factory
  const buildContext = async ({ req }): Promise<GraphQLContext> => ({
    currentUser: await authenticateToken(req.headers.authorization),
    requestId: req.headers['x-request-id'] || crypto.randomUUID(),
    loaders: initializeDataLoaders(), // Factory baru per request
  });
  ```

#### 3. Error Masking: Menelan Original Error
* **Gejala**: Log produksi hanya mencetak `Internal Server Error`, sementara *root-cause* (SQL deadlock, downstream timeout) hilang tanpa jejak.
* **Solusi**: Gunakan properti `originalError` pada `GraphQLError` dan pastikan format error handler memisahkan log audit internal dengan pesan error sanitasi untuk client:
  ```typescript
  import { GraphQLError } from 'graphql';

  export function createSecureGraphQLError(internalError: Error, publicMessage: string): GraphQLError {
    // Log error asli lengkap dengan stack trace ke APM (Datadog/Elastic)
    logger.error('Resolver Internal Failure', { error: internalError });

    return new GraphQLError(publicMessage, {
      extensions: {
        code: 'INTERNAL_SERVER_ERROR',
        // JANGAN pernah kirim internalError.stack ke client publik
      },
    });
  }
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Isolasi DataLoader**: Pastikan seluruh instance `DataLoader` diinisialisasi di dalam *Context Builder Function* pada scope per-request.
2. [ ] **Disable In-Memory Cache pada Long-Running Execution**: Jika menggunakan resolver streaming atau GraphQL Subscriptions, bersihkan DataLoader cache secara periodik agar tidak memicu memory leak.
3. [ ] **Validasi Depth & Complexity**: Integrasikan rule seperti `graphql-depth-limit` dan `graphql-validation-complexity` ke dalam pipeline validasi AST.
4. [ ] **Nullable Defense Strategy**: Pasang field bertipe nullable (`Type` bukan `Type!`) pada semua resolver yang bergantung pada dependensi jaringan eksternal (Microservice HTTP, Redis Cache, Database Replica).
5. [ ] **Tracing & OpenTelemetry Spans**: Bungkus eksekusi resolver kritis menggunakan distributed tracing spans. Sematkan metadata: `graphql.field`, `graphql.parentType`, `graphql.returnType`.
6. [ ] **Sanitasi Error Sanitization**: Gunakan `formatError` hook untuk menghapus atribut sensitif (database query string, IP internal, stack trace) saat environment bernilai `production`.
7. [ ] **Field Resolver Cost Guarding**: Hindari melakukan operasi DB/I/O di dalam leaf-level scalar resolver kecuali field tersebut memang eksplisit didefinisikan sebagai *computed dynamic field*.
8. [ ] **Hindari N+1 di Root Field**: Jika root query mengembalikan array, pertimbangkan batch resolve sejak level root alih-alih mengeksekusinya di resolver anak.
9. [ ] **Immutability Context**: Tetapkan `Readonly<GraphQLContext>` pada generic signature TypeScript untuk mencegah manipulasi context secara tidak sengaja di resolver tingkat dalam.
10. [ ] **Type Coercion Precision**: Selalu implementasikan Custom Scalar (misalnya `DateTimeISO`, `BigInt`) untuk tipe data yang rentan mengalami kehilangan presisi akibat parsing JSON standar.

---

### 12. Hands-on Practice

Buatlah sebuah implementasi simulasi GraphQL Engine internal berstandar enterprise yang menggabungkan custom pipeline resolver, batch loading, dan depth-limiting. Simpan file latihan ini di direktori `hands-on/m02/`.

#### Struktur Direktori
```text
hands-on/m02/
├── package.json
├── tsconfig.json
└── src/
    ├── context.ts
    ├── dataloaders.ts
    ├── schema.ts
    └── server.ts
```

#### Langkah 1: Inisialisasi Proyek & Dependencies
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install graphql dataloader
npm install -D typescript @types/node ts-node
```

Buat file `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

#### Langkah 2: Definisikan Mock Entity & DataLoader (`src/dataloaders.ts`)
```typescript
import DataLoader from 'dataloader';

export interface Customer {
  id: string;
  name: string;
}

export interface Order {
  id: string;
  customerId: string;
  totalAmount: number;
}

// Mock Database Records
const DB_CUSTOMERS: Customer[] = [
  { id: 'c1', name: 'PT Multi Artha' },
  { id: 'c2', name: 'CV Maju Jaya' },
];

const DB_ORDERS: Order[] = [
  { id: 'o101', customerId: 'c1', totalAmount: 500000 },
  { id: 'o102', customerId: 'c1', totalAmount: 750000 },
  { id: 'o103', customerId: 'c2', totalAmount: 1200000 },
];

export function createLoaders() {
  const customerLoader = new DataLoader<string, Customer | null>(
    async (customerIds: readonly string[]) => {
      console.log(`[DB QUERY] Executing batch fetch for Customers: ${customerIds.join(', ')}`);
      const results = customerIds.map((id) => DB_CUSTOMERS.find((c) => c.id === id) || null);
      return results;
    }
  );

  const ordersByCustomerLoader = new DataLoader<string, Order[]>(
    async (customerIds: readonly string[]) => {
      console.log(`[DB QUERY] Executing batch fetch for Orders of Customers: ${customerIds.join(', ')}`);
      return customerIds.map((cId) => DB_ORDERS.filter((o) => o.customerId === cId));
    }
  );

  return { customerLoader, ordersByCustomerLoader };
}

export type AppDataLoaders = ReturnType<typeof createLoaders>;
```

#### Langkah 3: Konteks Eksekusi (`src/context.ts`)
```typescript
import { AppDataLoaders, createLoaders } from './dataloaders';

export interface AppContext {
  requestId: string;
  loaders: AppDataLoaders;
}

export function buildContext(): AppContext {
  return {
    requestId: `req_${Math.random().toString(36).substring(2, 9)}`,
    loaders: createLoaders(),
  };
}
```

#### Langkah 4: Skema & Resolver Pipeline (`src/schema.ts`)
```typescript
import { 
  GraphQLSchema, 
  GraphQLObjectType, 
  GraphQLString, 
  GraphQLList, 
  GraphQLNonNull, 
  GraphQLFloat 
} from 'graphql';
import { AppContext } from './context';
import { Customer, Order } from './dataloaders';

const CustomerType = new GraphQLObjectType<Customer, AppContext>({
  name: 'Customer',
  fields: () => ({
    id: { type: new GraphQLNonNull(GraphQLString) },
    name: { type: new GraphQLNonNull(GraphQLString) },
    orders: {
      type: new GraphQLNonNull(new GraphQLList(new GraphQLNonNull(OrderType))),
      resolve: (parent, _args, context) => {
        // Menggunakan DataLoader: Mencegah N+1 saat me-resolve orders
        return context.loaders.ordersByCustomerLoader.load(parent.id);
      },
    },
  }),
});

const OrderType: GraphQLObjectType<Order, AppContext> = new GraphQLObjectType<Order, AppContext>({
  name: 'Order',
  fields: () => ({
    id: { type: new GraphQLNonNull(GraphQLString) },
    totalAmount: { type: new GraphQLNonNull(GraphQLFloat) },
    customer: {
      type: CustomerType,
      resolve: (parent, _args, context) => {
        // Menggunakan DataLoader: Mencegah N+1 saat me-resolve referensi customer balik
        return context.loaders.customerLoader.load(parent.customerId);
      },
    },
  }),
});

const RootQueryType = new GraphQLObjectType<unknown, AppContext>({
  name: 'Query',
  fields: {
    customers: {
      type: new GraphQLNonNull(new GraphQLList(new GraphQLNonNull(CustomerType))),
      resolve: () => {
        // Simulasi SELECT * FROM customers
        return [
          { id: 'c1', name: 'PT Multi Artha' },
          { id: 'c2', name: 'CV Maju Jaya' },
        ];
      },
    },
  },
});

export const enterpriseSchema = new GraphQLSchema({
  query: RootQueryType,
});
```

#### Langkah 5: Engine Runner & Verifikasi Trace Execution (`src/server.ts`)
```typescript
import { parse, validate, execute } from 'graphql';
import { enterpriseSchema } from './schema';
import { buildContext } from './context';

async function executeTest() {
  const query = `
    query GetEnterpriseDashboard {
      customers {
        id
        name
        orders {
          id
          totalAmount
          customer {
            name
          }
        }
      }
    }
  `;

  console.log('--- STARTING GRAPHQL EXECUTION PIPELINE ---');
  const documentAST = parse(query);
  const validationErrors = validate(enterpriseSchema, documentAST);

  if (validationErrors.length > 0) {
    console.error('Validation Failed:', validationErrors);
    process.exit(1);
  }

  // Buat context per-request
  const context = buildContext();

  console.log(`Executing request with ID: ${context.requestId}`);
  const result = await execute({
    schema: enterpriseSchema,
    document: documentAST,
    contextValue: context,
  });

  console.log('--- EXECUTION COMPLETED ---');
  console.log('Final Payload Output:');
  console.log(JSON.stringify(result, null, 2));
}

executeTest().catch(console.error);
```

#### Langkah 6: Eksekusi & Validasi Hasil
Jalankan via terminal:
```bash
npx ts-node src/server.ts
```

Output log database harus membuktikan bahwa batch fetch hanya terpanggil **tepat 1 kali** untuk orders dan **1 kali** untuk customers kembali (ter-cache), membuktikan eliminasi total dari N+1 problem:
```text
--- STARTING GRAPHQL EXECUTION PIPELINE ---
Executing request with ID: req_xxxxxxx
[DB QUERY] Executing batch fetch for Orders of Customers: c1, c2
[DB QUERY] Executing batch fetch for Customers: c1, c2
--- EXECUTION COMPLETED ---
```

---

### 13. Exercise

#### Level 1 (Easy) - AST Field Inspection Resolver
* **Tugas**: Buat sebuah resolver untuk field `SystemInfo.requestedFields: [String!]!` yang memeriksa `GraphQLResolveInfo` parameter dan mengembalikan daftar nama string seluruh field turunan langsung yang diminta oleh client dalam selection set kueri saat ini.
* **Kriteria Penerimaan**:
  * Menggunakan `info.fieldNodes` untuk membaca sub-selections.
  * Harus menangani kueri ber-alias dengan benar (mengembalikan original name atau alias sesuai yang tertulis di node).

#### Level 2 (Medium) - Custom Execution Directive Filter
* **Tugas**: Rancang schema directive `@maskSensitive(roleRequired: String!)`.
* **Kriteria Penerimaan**:
  * Jika context pengguna tidak memiliki role yang diwajibkan, ganti return string dari resolver tersebut menjadi string tersensor: `"********"`.
  * Nilai non-string harus melemparkan `GraphQLError` dengan extension code `UNAUTHORIZED_MASK_FIELD`.
  * Harus membungkus resolver asli secara transparan tanpa merusak *completeValue pipeline*.

#### Level 3 (Hard) - Concurrency Throttle Execution Plugin
* **Tugas**: Buat wrapper eksekusi kueri tingkat engine yang membatasi konkurensi resolver asynchronous maksimum yang dapat berjalan bersamaan (misalnya maksimal 5 asynchronous resolver concurrently per HTTP request) menggunakan semaphore pattern.
* **Kriteria Penerimaan**:
  * Membatasi eksekusi I/O intensif jika sebuah kueri mengekspansi list besar.
  * Tidak boleh mengubah struktur data schema `.graphql`.
  * Menolak kueri secara graceful jika execution time melebihi batas batas waktu yang ditentukan (*execution timeout cancellation token*).

---

### 14. Challenge

#### Skenario Kasus Kompleks: Real-time Distributed Federated Resolver Orchestrator
Sebuah korporasi telekomunikasi memiliki arsitektur di mana 1 root schema menggabungkan data dari 3 downstream services:
1. `Billing Core` (Legacy gRPC Service - lambat, timeout rate 5%).
2. `User Identity` (PostgreSQL Database lokal - sangat cepat, 2ms).
3. `Network Telemetry` (Apache Cassandra - throughput tinggi).

#### Tugas Rekayasa:
Bangun sebuah custom execution engine pipeline yang menangani skenario **Partial Degradation Resilience**:
1. Jika service `Billing Core` mengalami timeout (> 200ms), kueri tidak boleh gagal secara keseluruhan.
2. Resolver `Billing` harus memicu *Circuit Breaker* lokal, mengembalikan nilai fallback (misalnya status: `PENDING_CALCULATION`), dan menambahkan custom non-fatal diagnostic warning ke response `extensions.warnings`.
3. Selesaikan masalah "Thundering Herd": Jika 500 request kueri masuk secara simultan meminta tagihan user yang sama, hanya 1 request gRPC yang boleh dieksekusi ke `Billing Core`, sementara 499 request lainnya menunggu hasil resolver pertama melalui in-flight deduplication.
4. **Target Tanpa Solusi Instan**: Terapkan mekanisme ini murni menggunakan arsitektur resolver execution pattern pada runtime Node.js/TypeScript tanpa menambahkan proxy eksternal (seperti Envoy).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Konseptual & Dasar (5 Soal)
1. **Pada tahap eksekusi GraphQL, apa yang terjadi jika fungsi resolver pengguna mengembalikan nilai `undefined` untuk field skalar bertipe nullable?**
   * *Jawaban*: Engine memperlakukan `undefined` sama dengan `null`. Sesuai spesifikasi GraphQL, nilai akan diserialisasi menjadi JSON `null` di dalam output respons tanpa memicu error.
2. **Apa peran fungsi internal `CollectFields()` dalam algoritma eksekusi GraphQL?**
   * *Jawaban*: `CollectFields()` menggabungkan seluruh field yang memiliki nama respons (*response key* atau *alias*) yang identik, mengevaluasi direktif `@include` dan `@skip`, serta meratakan (*flattening*) fragment spreads dan inline fragments ke dalam satu daftar eksekusi tunggal.
3. **Mengapa pemanggilan `new DataLoader(...)` di tingkat file global (singleton) merupakan anti-pattern fatal pada backend web server multi-tenant?**
   * *Jawaban*: Karena cache internal DataLoader akan bertahan melintasi siklus hidup request. Ini mengakibatkan: (1) Kebocoran data privasi antar-user/tenant (*cross-tenant data leak*), dan (2) Memori heap server akan terus membengkak (*memory leak*) karena cache map tidak pernah di-garbage-collect.
4. **Jelaskan konsep "Null Bubbling" pada GraphQL!**
   * *Jawaban*: Null Bubbling adalah mekanisme propagasi error di mana jika sebuah field bertipe non-null (`!`) menghasilkan `null` (karena error resolver atau ketiadaan data), engine terpaksa menggelembungkan nilai `null` tersebut ke field parent di atasnya. Hal ini berulang hingga engine menemukan field nullable terdekat atau membatalkan seluruh root data menjadi `null`.
5. **Kapan tepatnya tahapan `validate` dijalankan oleh GraphQL engine relatif terhadap fungsi resolver?**
   * *Jawaban*: Validasi AST dijalankan **sebelum** fungsi resolver manapun dieksekusi. Jika dokumen kueri melanggar aturan validasi skema atau aturan struktural, eksekusi dibatalkan seketika dan array `errors` dikembalikan ke klien tanpa ada resolver yang dipanggil.

#### Bagian B: Pertanyaan Lanjutan & Analisis Arsitektur (5 Soal)
6. **Bagaimana mekanisme microtask queue pada JavaScript runtime memungkinkan batching pada `DataLoader` bekerja secara otomatis?**
   * *Jawaban*: Ketika metode `load()` dipanggil secara berurutan dalam Call Stack sinkronus, DataLoader menampung (*queues*) key tersebut ke dalam array internal dan menjadwalkan fungsi dispatch batch menggunakan `process.nextTick` atau Promise microtask. Begitu seluruh resolver sinkronus pada tick tersebut selesai dieksekusi dan Call Stack kosong, event loop mengeksekusi microtask DataLoader yang memproses semua key terkumpul dalam 1 query tunggal.
7. **Jika resolver field A dan resolver field B berada pada level hierarki kueri yang sama (siblings) dan keduanya asynchronous, bagaimana urutan penyelesaian eksekusinya menurut GraphQL spec?**
   * *Jawaban*: Spesifikasi GraphQL tidak mendikte urutan eksekusi absolut untuk kueri bertipe `Query` (sibling fields diselesaikan secara konkuren/independen). Namun untuk `Mutation`, GraphQL spec mewajibkan eksekusi field di level root dieksekusi secara ketat sekuensial berseri (*serial execution*) untuk mencegah race condition mutasi data.
8. **Diberikan skema berikut: `type Query { user: User! }` dan `type User { profile: Profile! }` dan `type Profile { bio: String! }`. Jika resolver `Profile.bio` melempar runtime exception, apa bentuk akhir representasi respons JSON GraphQL?**
   * *Jawaban*: 
     ```json
     {
       "data": null,
       "errors": [
         {
           "message": "...",
           "path": ["user", "profile", "bio"]
         }
       ]
     }
     ```
     *Penjelasan*: Karena `bio` adalah non-null (`String!`), kegagalan merambat ke `Profile!`. Karena `Profile!` juga non-null, merambat lagi ke `User!`. Karena `user` pada root Query juga `User!`, seluruh root `data` berubah menjadi `null`.
9. **Mengapa kita harus berhati-hati saat menggunakan `info.schema` di dalam resolver kueri dengan frekuensi trafik tinggi?**
   * *Jawaban*: Objek `GraphQLResolveInfo` dan `schema` adalah struktur data referensial pohon yang sangat masif. Mengakses atau men-clone objek ini secara ceroboh, atau mempertahankan referensinya di dalam long-lived closure dapat membebani pointer dereferencing dan menghambat pembersihan garbage collection pada V8 heap.
10. **Bagaimana cara mengisolasi kalkulasi otorisasi (RBAC) agar tidak dieksekusi berulang kali ketika sebuah field list me-resolve 1,000 item dalam satu array?**
    * *Jawaban*: Lakukan pemeriksaan otorisasi di level parent resolver (atau guard middleware pada root operation) yang mengembalikan list tersebut, bukan di dalam field-level resolver item individual. Alternatifnya, gunakan memoization/caching context token evaluation agar izin role hanya dievaluasi satu kali per request lifecycle.

#### Bagian C: Studi Kasus Produksi Nyata (3 Skenario)
11. **Skenario 1**: Metrik APM menunjukkan lonjakan tajam CPU 100% pada container gateway saat menerima kueri dengan struktur `fragment LoopA on User { friends { ...LoopB } } fragment LoopB on User { friends { ...LoopA } }`. Mengapa GraphQL engine gagal mencegah ini jika parser tidak error? Bagaimana memperbaikinya?
    * *Analisis & Solusi*: Parser berhasil memprosesnya karena secara sintaksis dokumen tersebut valid. Masalah terjadi karena kueri tersebut membentuk Fragment Cycle (lingkaran tak terbatas). GraphQL spec menyertakan aturan validasi bawaan `KnownFragmentNames` dan `NoFragmentCycles`. Insiden ini terjadi jika engine di-run dengan custom validation rules yang secara tidak sengaja menonaktifkan atau meng-override `NoFragmentCycles` rule dari `graphql-js`. Solusinya adalah memverifikasi bahwa `specifiedRules` diikutsertakan secara utuh dalam fungsi `validate(schema, documentAST, specifiedRules)`.
12. **Skenario 2**: Sebuah enterprise menggunakan field masking untuk menyembunyikan data PII. Resolver mengembalikan data terenkripsi. Namun, client melaporkan bahwa ketika mereka mengirimkan invalid sub-query di dalam field yang ditolak, response header HTTP mengembalikan 200 OK dengan error masking yang membocorkan nama kolom database internal. Bagaimana Anda mengonfigurasi Execution Error Pipeline untuk menangkal data leakage ini?
    * *Analisis & Solusi*: Masalahnya terletak pada pipeline pemformatan error bawaan (*unhandled exceptions leakage*). Solusi: Terapkan fungsi `formatError` di engine server. Pada layer ini, intercept seluruh instance `GraphQLError`. Periksa apakah error tersebut berasal dari user validation yang aman atau exception driver database/ORM. Jika terdapat exception runtime yang tidak terkelola, ganti pesannya dengan masker statis generik (`"INTERNAL_SERVER_ERROR"`), simpan detail teknis ke backend logging/APM terpisah dengan traceId, dan hapus properti `extensions.exception.stacktrace`.
13. **Skenario 3**: Dalam sistem e-commerce federasi, resolver `Cart.totalPrice` lambat (3,500ms) karena menunggu panggilan eksternal ke microservice Kurs Mata Uang, padahal user hanya meminta `query { cart { id itemCount } }`. Resolver `Cart.totalPrice` tetap terpanggil dan memblokir request. Mengapa ini bisa terjadi dan bagaimana cara mendiagnosis resolver yang "over-executing"?
    * *Analisis & Solusi*: Ini terjadi jika developer melakukan "Over-fetching di Resolver Parent": Resolver root `cart` mengambil data cart beserta kalkulasi `totalPrice` sekaligus secara eager di parent resolver, alih-alih memisahkannya ke dalam dedicated resolver milik field `Cart.totalPrice`. Solusi: Pastikan parent resolver `cart` hanya mengembalikan pointer ID mentah atau data cart lokal. Pindahkan kalkulasi kurs mata uang ke field resolver `totalPrice`. Engine GraphQL hanya akan mengeksekusi resolver `totalPrice` jika dan hanya jika field tersebut secara eksplisit terdaftar di AST selection set kueri yang dikirimkan client.

---

### 16. Summary
1. **Algoritma Eksekusi GraphQL Spec** beroperasi secara deterministik melalui tahapan: Lexing $\to$ Parsing (AST) $\to$ Validation $\to$ Execution Context Assembly $\to$ Selection Set Evaluation (`CollectFields`) $\to$ Field Completion Pipeline (`CompleteValue`).
2. **Conkurensi Resolving Berbasis Microtask**: Penyelesaian GraphQL field bertingkat mengandalkan perputaran Event Loop dan Microtask Queue. Seluruh resolver pada layer saudara (*siblings*) dieksekusi secara asinkron dan paralel, kecuali pada root mutation yang dieksekusi secara sekuensial.
3. **Pemberantasan N+1 Problem**: Merupakan kewajiban mutlak pada skala enterprise menggunakan abstraksi batching berbasis event loop tick seperti `DataLoader`. DataLoader harus di-scope per request demi mencegah kerentanan data leakage multi-tenant dan memory leak.
4. **Propagasi Non-Null (Null Bubbling)**: Penggunaan modifier tanda seru (`!`) harus diperhitungkan dengan matang. Satu kegagalan pada field non-null yang berada jauh di dalam hierarki child resolver dapat membatalkan dan mengosongkan keseluruhan payload pohon objek di atasnya.
5. **Proteksi Runtime Statis & Dinamis**: Keamanan engine GraphQL produksi bergantung pada kombinasi evaluasi statis sebelum eksekusi (AST Query Depth & Complexity Limit) dan isolasi dinamis resolver (Higher-Order Resolver Middleware untuk RBAC/ABAC serta pemformatan error terenkapsulasi).