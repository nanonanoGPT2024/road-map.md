# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 04-Backend-and-Database
### Bab 01: Fondasi dan Arsitektur GraphQL
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Memahami secara mendalam fase internal siklus hidup GraphQL document execution (*Tokenization/Lexing*, *AST Parsing*, *Validation Phase*, hingga *Execution Pipeline*).
- Mengimplementasikan pola *DataLoader* yang deterministik dan *thread/tick-safe* guna mengatasi *N+1 Problem* di level resolusi dependensi downstream (database/microservices).
- Mengonstruksi arsitektur server GraphQL enterprise-grade berbasis TypeScript dengan *Context Propagation*, *Resolver Composition*, *Custom Directives*, dan *Field-level Authorization*.
- Mengamankan GraphQL endpoint produksi dari serangan DoS berbasis kueri melalui implementasi *Depth Limiting*, *Query Complexity Analysis (Cost Analysis)*, dan *Automatic Persisted Queries (APQ)*.
- Mendesain instrumentasi telemetri (*Field-level Tracing* dan *OpenTelemetry*) untuk mendeteksi bottleneck latensi mikro pada *resolver tree*.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
- **Core Node.js Runtime & Asynchronous Programming**: Memahami Node.js Event Loop (*microtask queue vs macrotask queue*), `Promise.all()`, dan *tick lifecycle*.
- **TypeScript Intermediate to Advanced**: Mampu mengoperasikan *Generics*, *Mapped Types*, *Utility Types*, dan inferensi tipe data dinamis.
- **GraphQL Fundamentals**: Paham definisi SDL (*Schema Definition Language*), tipe-tipe skalar dasar, *Query*, *Mutation*, dan konsep resolver standar (argumen `parent`, `args`, `context`, `info`).
- **Database & I/O Fundamentals**: Mengetahui masalah performa latensi I/O, koneksi pooling, dan query batching di SQL/NoSQL.

---

### 3. Concept & Internal Architecture

Eksekusi GraphQL bukan sekadar parser string JSON, melainkan sebuah kompilator dan state machine yang mengeksekusi Graph traversal secara asynchronous.

```
                    GraphQL Request Lifecycle Pipeline
 ┌────────────────┐     ┌──────────────┐     ┌──────────────┐
 │ Raw HTTP Body  │────>│ Lexer/Parser │────>│ AST Document │
 └────────────────┘     └──────────────┘     └──────────────┘
                                                    │
                                                    ▼
 ┌────────────────┐     ┌──────────────┐     ┌──────────────┐
 │ JSON Response  │<────│ Field Resolv │<────│  Validation  │
 └────────────────┘     │   Pipeline   │     │ (Type & Cost)│
                        └──────────────┘     └──────────────┘
                               │
                      DataLoader Batch Phase
                     (Event Loop Microtask)
```

#### A. Lexing, Parsing, dan Abstract Syntax Tree (AST)
Ketika payload HTTP POST diterima, runtime GraphQL (`graphql-js`) memproses dokumen melalui dua layer utama:
1. **Lexer (Tokenisasi)**: Mengubah raw string dokumen kueri menjadi aliran token individual (*Punctuator*, *Name*, *StringValue*, dll.), mengabaikan whitespace dan komentar.
2. **Parser**: Menganalisis urutan token sesuai dengan Grammar formal GraphQL dan membangun **AST (Abstract Syntax Tree)**. Representasi AST ini direpresentasikan oleh tipe data node seperti `OperationDefinitionNode`, `FieldNode`, `SelectionSetNode`, dan `ArgumentNode`.

```
Query: { user(id: "1") { name } }

AST Representation:
DocumentNode
 └── OperationDefinitionNode (operation: "query")
      └── SelectionSetNode
           └── FieldNode (name: "user")
                ├── ArgumentNode (name: "id", value: "1")
                └── SelectionSetNode
                     └── FieldNode (name: "name")
```

#### B. Validation Phase
Sebelum dieksekusi, AST divalidasi terhadap Skema (`GraphQLSchema`). Validasi ini mengevaluasi:
- **Structural Integrity**: Apakah field yang diminta benar-benar ada pada tipe terkait?
- **Type Compatibility**: Apakah argumen yang dikirim sesuai dengan skalar/input tipe yang didefinisikan?
- **Fragment Integrity**: Tidak ada cyclic fragments, dan fragment spread valid pada target type.
- **Security Rules**: Memanggil fungsi validasi khusus (*Custom AST Visitors*) untuk menghitung kedalaman (*AST Depth*) dan skor kompleksitas (*Query Cost Analysis*). Jika evaluasi melanggar batas yang ditentukan, dokumen dihentikan sebelum satupun resolver dieksekusi.

#### C. Execution Pipeline & Resolver Tree
Tahap eksekusi dijalankan oleh fungsi `execute()`. Operasi dieksekusi secara berbeda tergantung jenis operasinya:
- **Query**: Resolusi field dilakukan secara paralel (concurrent asynchronous) menggunakan `Promise.all` implisit pada tingkat percabangan yang sama.
- **Mutation**: Resolusi field pada level akar (*root fields*) dieksekusi secara serial (sekuensial) untuk mencegah *race condition*, sedangkan sub-field di bawah root field dieksekusi secara paralel.
- **Field Resolution Algorithm**: Setiap pemanggilan resolver mematuhi format signature:
  `resolve(parent, args, context, info)`
  - `parent`: Hasil yang dikembalikan oleh resolver node di atasnya (*upstream*).
  - `args`: Parameter yang dipassing secara eksplisit pada query field.
  - `context`: Shared per-request context (database connections, auth identity, data loaders).
  - `info`: Metadata AST yang memuat *field name*, *path*, *return type*, dan schema AST.

#### D. DataLoader & Node.js Event Loop Coordination
*DataLoader* bukan sekadar caching library, melainkan mekanisme penjadwalan I/O. DataLoader memanfaatkan mekanisme *Event Loop Queue* (khususnya `process.nextTick` di Node.js) untuk mengumpulkan (*batch*) semua kunci identitas yang di-*enqueue* selama satu siklus eksekusi sinkron sebelum mengeksekusi fungsi batch fetching:

1. Resolver A memanggil `loader.load(1)`. DataLoader menyimpan kunci `1` di internal array dan mengembalikan sebuah unresolved `Promise`.
2. Resolver B pada kedalaman cabang tree yang sama memanggil `loader.load(2)`. DataLoader menyimpan kunci `2`.
3. Seluruh eksekusi resolver pada fase sinkron selesai. Node.js event loop bergeser ke *microtask queue*.
4. Callback batching DataLoader terpanggil: `batchFunction([1, 2])`.
5. Satu query batch dieksekusi ke upstream (misal: `SELECT * FROM users WHERE id IN (1, 2)`).
6. DataLoader me-resolve promise masing-masing resolver secara tepat dengan referensi entitas yang sesuai.

---

### 4. Why & What

| Dimensi | REST Architecture | GraphQL Engine Architecture |
| :--- | :--- | :--- |
| **Model Eksekusi** | Terikat langsung pada routing tabel HTTP method & endpoint URL path. | Traversal terpadu pada Directed Acyclic Graph (DAG) melalui AST. |
| **Over/Under-fetching** | Diatasi dengan membuat endpoint baru atau query string kompleks (`?include=...`). | Diatasi secara natif; klien menentukan selection set secara deklaratif. |
| **I/O Latency Handling** | N+1 ditangani manual di tingkat query builder/ORM endpoint terkait. | N+1 ditangani secara otomatis melalui abstractions seperti DataLoader di level Resolver. |
| **API Evolution** | Versi eksplisit pada path (`/api/v1`, `/api/v2`) atau headers. | Field-level deprecation tags (`@deprecated`), skema berevolusi secara continuous (*additive changes*). |
| **Network Overhead** | Multiple round-trips untuk relasi nested data. | Single network round-trip mengorkestrasi multi-entity aggregation. |

Mengapa arsitektur internal ini penting bagi skala enterprise?
1. **Pencegahan Cascading Failures**: Jika downstream microservice lambat, execution engine dapat mengisolasi kegagalan pada field tertentu (mengembalikan partial data dengan field `null` dan array `errors`) tanpa menggagalkan root response.
2. **Deterministic Profiling**: Karena eksekusi berbasis AST, telemetry collector dapat melacak field spesifik mana yang memicu latency spike dan mendeteksi dependensi data yang tidak efisien langsung dari skema.

---

### 5. How (Workflow Detail)

Berikut adalah workflow produksi dari request masuk hingga response dikirimkan:

```
[Client]
   │ HTTP POST /graphql (Query, Variables, OperationName)
   ▼
[HTTP Transport / Express / Fastify Middleware]
   │ Ekstraksi Bearer Token & Tracing Headers (Traceparent)
   ▼
[Context Factory]
   │ Inisialisasi: Request-scoped instances (DataLoader, DB Pools, User Context)
   ▼
[Engine: Lexing & Parsing] ───(Sintaks Error?)───> [Bailout: 400 Bad Request]
   │ Sukses: Hasilkan DocumentNode (AST)
   ▼
[Engine: AST Validation]
   ├── Validation Rules Standard (Type-checking)
   ├── Complexity/Depth Visitor (Hitung bobot kueri)
   └── Is Valid? ───(Melebihi Ambang Batas?)───> [Bailout: GraphQLError (Complexity)]
   ▼
[Engine: Execution Phase]
   ├── Root Field Resolvers dieksekusi concurrently (Query)
   │     │
   │     ├── Resolver memanggil DataLoader.load(ID)
   │     └── Event-loop tick deferral
   │           │
   │           ▼
   │     DataLoader mengeksekusi Batch Fetch Function
   │     (Batch DB Query / gRPC call)
   │
   └── Child Resolvers memproses parent data (Recursion down the AST tree)
   ▼
[Response Formatting]
   ├── Format Payload: { data: { ... }, errors: [ ... ] }
   └── Sanitasi Error Stack Trace untuk Environment Produksi
   ▼
[Client Response Sent]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengantaran Logistik Paket Terpadu
Bayangkan REST sebagai armada kurir terpisah: jika 100 orang di satu kantor memesan barang dari 3 toko berbeda, 300 kurir terpisah akan datang membawa satu barang per kurir secara acak (N+1 Problem, high network overhead).

GraphQL Engine dengan DataLoader bertindak sebagai **Kantor Pos Konsolidasi**:
1. Formulir pemesanan (GraphQL Query Document) diperiksa formatnya oleh staf validasi skema.
2. Pesanan untuk gedung yang sama ditampung dalam keranjang batching (`DataLoader.load()`).
3. Tepat sebelum mobil boks berangkat (Event Loop microtask tick), sistem menggabungkan semua pesanan toko A menjadi satu pesanan skala besar (`batchFunction()`).
4. Barang tiba di kantor pos, dipecah sesuai pemesan asli, dan diantarkan ke meja masing-masing dalam satu pengantaran terpadu (*Single unified JSON response*).

```
Resolver Tree Parallel Resolution & DataLoader Consolidation:

  Root Query: orders(limit: 2)
      │
      ├── [Order 1] ──────────────────────────┐
      │     └── customerId: 101               │ (Enqueued to DataLoader)
      │           └── customer.name           ▼
      │                                 ┌───────────────┐
      └── [Order 2] ───────────────────>│  DataLoader   │──> Batch Fetch:
            └── customerId: 102         │ Accumulator   │    SELECT * FROM users
                  └── customer.name     └───────────────┘    WHERE id IN (101, 102)
                                              │
      ┌───────────────────────────────────────┘
      ▼
  Dispatching results back to:
  Order 1 -> Customer 101 Name
  Order 2 -> Customer 102 Name
```

---

### 7. Practical Implementation (Standar Industri)

Implementasi GraphQL Node.js/TypeScript produksi menggunakan `@graphql-tools/schema`, `dataloader`, dan validasi keamanan.

#### A. Inisialisasi Proyek dan Tipenya
Struktur dependensi:
```json
{
  "dependencies": {
    "dataloader": "^2.2.2",
    "graphql": "^16.8.1",
    "@graphql-tools/schema": "^10.0.3",
    "express": "^4.19.2"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.11.24",
    "typescript": "^5.3.3"
  }
}
```

#### B. Skema, DataLoaders, Context, dan Resolver Produksi

```typescript
// src/types/context.ts
import DataLoader from 'dataloader';

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Order {
  id: string;
  userId: string;
  total: number;
  status: 'PENDING' | 'COMPLETED' | 'CANCELLED';
}

export interface GraphQLContext {
  userId?: string;
  loaders: {
    userLoader: DataLoader<string, User | null>;
    ordersByUserIdLoader: DataLoader<string, Order[]>;
  };
}
```

```typescript
// src/loaders/index.ts
import DataLoader from 'dataloader';
import { User, Order } from '../types/context';

// Mock Downstream Repository (e.g. Database / Microservice client)
const fakeUserDb: Record<string, User> = {
  '1': { id: '1', name: 'Alice Enterprise', email: 'alice@corp.internal' },
  '2': { id: '2', name: 'Bob Infrastructure', email: 'bob@corp.internal' },
};

const fakeOrderDb: Order[] = [
  { id: '101', userId: '1', total: 450.0, status: 'COMPLETED' },
  { id: '102', userId: '1', total: 120.5, status: 'PENDING' },
  { id: '103', userId: '2', total: 999.0, status: 'COMPLETED' },
];

export function createDataLoaders() {
  return {
    // 1-to-1 Batching (User by ID)
    userLoader: new DataLoader<string, User | null>(
      async (keys: readonly string[]) => {
        // Log untuk memverifikasi konsolidasi batching
        console.log(`[DB Query Executed] Batch loading users for IDs: ${keys.join(', ')}`);
        
        // Simulasikan Query: SELECT * FROM users WHERE id IN (...)
        const userMap = new Map<string, User>();
        keys.forEach((key) => {
          if (fakeUserDb[key]) {
            userMap.set(key, fakeUserDb[key]);
          }
        });

        // DataLoader REQUIREMENT: Panjang array hasil HARUS sama persis dengan panjang keys
        // dan berurutan sesuai index key yang diminta.
        return keys.map((key) => userMap.get(key) || null);
      },
      { cache: true } // Request-level caching
    ),

    // 1-to-Many Batching (Orders by User ID)
    ordersByUserIdLoader: new DataLoader<string, Order[]>(
      async (keys: readonly string[]) => {
        console.log(`[DB Query Executed] Batch loading orders for User IDs: ${keys.join(', ')}`);
        
        // Simulasikan Query: SELECT * FROM orders WHERE userId IN (...)
        const groupedOrders = new Map<string, Order[]>();
        keys.forEach((key) => groupedOrders.set(key, []));

        fakeOrderDb.forEach((order) => {
          if (groupedOrders.has(order.userId)) {
            groupedOrders.get(order.userId)!.push(order);
          }
        });

        return keys.map((key) => groupedOrders.get(key) || []);
      }
    ),
  };
}
```

```typescript
// src/schema/index.ts
import { makeExecutableSchema } from '@graphql-tools/schema';
import { GraphQLContext, Order, User } from '../types/context';
import { GraphQLError } from 'graphql';

const typeDefs = /* GraphQL */ `
  enum OrderStatus {
    PENDING
    COMPLETED
    CANCELLED
  }

  type User {
    id: ID!
    name: String!
    email: String!
    orders: [Order!]!
  }

  type Order {
    id: ID!
    total: Float!
    status: OrderStatus!
    customer: User!
  }

  type Query {
    me: User
    orders(limit: Int = 10): [Order!]!
  }

  input CreateOrderInput {
    total: Float!
  }

  type Mutation {
    createOrder(input: CreateOrderInput!): Order!
  }
`;

const resolvers = {
  Query: {
    me: async (_: unknown, __: unknown, context: GraphQLContext): Promise<User | null> => {
      if (!context.userId) {
        throw new GraphQLError('Unauthenticated access', {
          extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } },
        });
      }
      return context.loaders.userLoader.load(context.userId);
    },
    orders: async (_: unknown, { limit }: { limit: number }): Promise<Order[]> => {
      // Mock data fetching root level orders
      return [
        { id: '101', userId: '1', total: 450.0, status: 'COMPLETED' },
        { id: '102', userId: '1', total: 120.5, status: 'PENDING' },
        { id: '103', userId: '2', total: 999.0, status: 'COMPLETED' },
      ].slice(0, limit);
    },
  },
  Order: {
    customer: async (parent: Order, _: unknown, context: GraphQLContext): Promise<User | null> => {
      // Menyelesaikan relasi N+1 via DataLoader
      return context.loaders.userLoader.load(parent.userId);
    },
  },
  User: {
    orders: async (parent: User, _: unknown, context: GraphQLContext): Promise<Order[]> => {
      // Menyelesaikan relasi 1 to Many via DataLoader
      return context.loaders.ordersByUserIdLoader.load(parent.id);
    },
  },
  Mutation: {
    createOrder: async (
      _: unknown,
      { input }: { input: { total: number } },
      context: GraphQLContext
    ): Promise<Order> => {
      if (!context.userId) {
        throw new GraphQLError('Unauthorized', { extensions: { code: 'FORBIDDEN' } });
      }

      const newOrder: Order = {
        id: Buffer.from(`${Date.now()}`).toString('base64'),
        userId: context.userId,
        total: input.total,
        status: 'PENDING',
      };

      // Invalidate DataLoader cache if mutating local state in long running context
      context.loaders.ordersByUserIdLoader.clear(context.userId);

      return newOrder;
    },
  },
};

export const schema = makeExecutableSchema({ typeDefs, resolvers });
```

```typescript
// src/server.ts
import express from 'express';
import { graphql, validate, parse, specifiedRules, ValidationRule } from 'graphql';
import { schema } from './schema';
import { createDataLoaders } from './loaders';
import { GraphQLContext } from './types/context';

const app = express();
app.use(express.json());

// Custom Validation Rule: Simple Max Depth Guard
const createDepthLimitRule = (maxDepth: number): ValidationRule => {
  return (context) => {
    return {
      OperationDefinition(node) {
        const calculateDepth = (selectionSet: any, currentDepth: number): number => {
          if (!selectionSet || !selectionSet.selections) return currentDepth;
          let max = currentDepth;
          for (const selection of selectionSet.selections) {
            if (selection.kind === 'Field') {
              const depth = calculateDepth(selection.selectionSet, currentDepth + 1);
              if (depth > max) max = depth;
            }
          }
          return max;
        };

        const depth = calculateDepth(node.selectionSet, 0);
        if (depth > maxDepth) {
          context.reportError(
            new Error(`Query depth of ${depth} exceeds maximum allowable depth of ${maxDepth}.`)
          );
        }
      },
    };
  };
};

app.post('/graphql', async (req, res) => {
  const { query, variables, operationName } = req.body;

  if (typeof query !== 'string') {
    return res.status(400).json({ errors: [{ message: 'Missing valid query string' }] });
  }

  try {
    // 1. AST Parsing
    const documentAST = parse(query);

    // 2. AST Validation with Custom Rules (Depth Limit: 4)
    const validationErrors = validate(schema, documentAST, [
      ...specifiedRules,
      createDepthLimitRule(4),
    ]);

    if (validationErrors.length > 0) {
      return res.status(400).json({ errors: validationErrors });
    }

    // 3. Request-Scoped Context Initialization
    // PENTING: createDataLoaders HARUS dibuat per request untuk menghindari cross-request data leaks!
    const context: GraphQLContext = {
      userId: (req.headers['x-user-id'] as string) || '1',
      loaders: createDataLoaders(),
    };

    // 4. Execution Pipeline
    const executionResult = await graphql({
      schema,
      source: query,
      rootValue: null,
      contextValue: context,
      variableValues: variables,
      operationName,
    });

    return res.json(executionResult);
  } catch (error: any) {
    return res.status(500).json({
      errors: [{ message: error.message || 'Internal Execution Error' }],
    });
  }
});

app.listen(4000, () => {
  console.log('Production GraphQL Service running on http://localhost:4000/graphql');
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Arsitektur E-Commerce Global (Scale: 50,000 req/sec)
Sebuah platform checkout enterprise menghadapi degradasi latensi parah (p99 > 3800ms) saat kampanye belanja kuartalan (*Flash Sale*). Root Query dashboard klien mengambil daftar `Cart`, relasi `CartItem`, data inventaris `ProductVariant`, dan reputasi `Merchant`.

#### Masalah Utama
1. **The Recursive N+1 Explosion**: Setiap `CartItem` menembak gRPC request terpisah ke `Inventory-Service` untuk memeriksa status ketersediaan barang. Hasil: 1 keranjang dengan 20 item memicu 21 RPC downstream.
2. **Global DataLoader Leakage**: Pengembang menginstansiasi instance `DataLoader` di level *global singleton*. Akibatnya, User B menerima data User A yang tersimpan dalam memory cache DataLoader, menciptakan insiden kebocoran data GDPR tingkat tinggi.
3. **Circular Query Attack**: Pengguna mengeksploitasi relasi:
   `user { orders { customer { orders { customer { ... } } } } }`
   menyebabkan CPU starvation 100% pada Node.js Event Loop parser.

#### Arsitektur Solusi
```
                         Enterprise API Gateway
                         ┌────────────────────┐
                         │   Depth & Cost     │
                         │   Analysis Guard   │
                         └─────────┬──────────┘
                                   │
                                   ▼
                   GraphQL Orchestration Layer (Node.js)
                 ┌──────────────────────────────────────┐
                 │ Context Scoped Factory:              │
                 │ - New DataLoader per Request         │
                 │ - Traceparent Context Propagation    │
                 └─────────┬──────────────────┬─────────┘
                           │                  │
               gRPC Batch  │                  │  Redis Read-Through
               Loaders     ▼                  ▼  (Persistent Cache)
                   ┌──────────────┐     ┌──────────────┐
                   │  Inventory   │     │   Product    │
                   │ Microservice │     │   Catalog    │
                   └──────────────┘     └──────────────┘
```

1. **Context-Isolation Factory**: Instance DataLoader diikatkan secara ketat pada lifecycle `req` Express/Fastify. Ketika koneksi HTTP ditutup, heap memory didereferensikan oleh garbage collector.
2. **gRPC Batch Binding**: Dibuat adapter `DataLoader` yang memetakan puluhan request SKU menjadi single batch call `GetItemStocks(repeated string skuList)` ke Inventory Service. Latensi p99 turun drastis dari 3800ms ke 140ms.
3. **AST Query Cost Engine**: Mengimplementasikan bobot komputasi statis:
   - Root field = 1 poin.
   - List relations = perkalian parameter pagination `first / limit` x 2.
   - Maksimum kuota complexity per request dibatasi 250 poin. Permintaan melebihi kuota di-reject langsung pada fase AST Validation dengan error `MAX_COMPLEXITY_EXCEEDED`.

---

### 9. Trade-offs (Analisis Arsitektural)

| Aspek | Keputusan / Pendekatan | Keuntungan | Biaya / Kerugian |
| :--- | :--- | :--- | :--- |
| **Parsing Overhead** | Dynamic AST Parsing (Per-request) | Sangat fleksibel; klien bebas mendefinisikan field. | CPU-intensive di Node.js runtime. Rentan DoS pada kueri berukuran megabyte. |
| **Safe Parsing** | Automatic Persisted Queries (APQ) | Mengirim hash SHA256 (32 byte) alih-alih dokumen string kueri ribuan byte; AST di-cache di Redis/memory. | Memerlukan storage shared cache layer untuk registry hash; menambah dependensi infrastruktur. |
| **Data Fetching** | DataLoader In-Memory Batching | Mengurangi IO downstream secara signifikan (eliminasi N+1). | Kompleksitas kode bertambah. Memori heap per-request naik sementara selama penampungan kunci. |
| **Caching Layer** | HTTP Edge Caching vs GraphQL Cache | REST dapat menggunakan standard HTTP cache-control header di reverse proxy (Cloudflare/Fastly). | GraphQL umumnya menggunakan POST, rendering browser & HTTP cache proxies non-fungsional tanpa APQ/GET wrappers. |
| **Error Handling** | Partial Success (`data` + `errors`) | Klien tetap dapat me-render UI parsial meski ada sub-service downstream yang down. | Error parsing di client side lebih kompleks; HTTP status code hampir selalu mengembalikan `200 OK`. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Membagi DataLoader Instance Antar HTTP Request (Global State)
- **Symptom**: User A melihat nama, saldo, atau alamat User B secara berkala.
- **Root Cause**: `const loader = new DataLoader(...)` dideklarasikan di scope global file modul, bukan di dalam fungsi Context Factory. DataLoader menyimpan resolve promise cache yang shared antar-thread/request.
- **Solusi**: Instansiasi *wajib* dilakukan di dalam callback context creation:
  ```typescript
  // SALAH
  export const globalUserLoader = new DataLoader(keys => ...);

  // BENAR
  export const createContext = (req): GraphQLContext => ({
    loaders: {
      userLoader: new DataLoader(keys => batchUsers(keys)),
    }
  });
  ```

#### Kesalahan 2: Ketidakcocokan Panjang dan Urutan Array pada DataLoader Batch Function
- **Symptom**: Field mengembalikan data yang tertukar antar ID atau error runtime `The order and length of keys does not match the returned values`.
- **Root Cause**: SQL query `WHERE id IN (3, 1, 2)` mengembalikan record dengan urutan `[1, 2, 3]`. Batch function me-return array database secara mentah tanpa re-indexing.
- **Solusi**: Petakan kembali menggunakan `Map` sesuai urutan array input `keys`:
  ```typescript
  const batchFn = async (keys: readonly string[]) => {
    const rows = await db.select().whereIn('id', keys);
    const map = new Map(rows.map(r => [r.id, r]));
    return keys.map(k => map.get(k) || null); // Jamin panjang & urutan 100% presisi
  };
  ```

#### Kesalahan 3: Unhandled Rejection di Sub-Resolver yang Menghancurkan Root Data
- **Symptom**: Satu field non-nullable (`String!`) pada child melemparkan error tak tertangani; seluruh root object mengembalikan `null`.
- **Root Cause**: Aturan *Bubble-up Error* GraphQL: jika child resolver dengan skema *Non-Nullable* melempar exception, engine akan merambat naik menghapus parent-nya hingga mencapai field nullable pertama.
- **Solusi**: Definisikan field relasi sebagai *Nullable* jika downstream dependensinya memiliki kemungkinan gagal (*graceful degradation*), atau tangkap error di resolver dan kembalikan error typing spesifik (*Union error pattern*).

---

### 11. Best Practices (Production Checklist)

- [ ] **Disable Schema Introspection di Production**: Lindungi skema internal dari automated recon attacker (`introspection: process.env.NODE_ENV !== 'production'`).
- [ ] **Enforce Max Query Depth**: Batasi kedalaman AST nesting traversal (rekomendasi: kedalaman maksimal 5-7 level).
- [ ] **Terapkan Query Cost Analysis**: Assign poin pada setiap field, kalkulasi cost pada fase validation, tolak eksekusi jika cost > limit.
- [ ] **Gunakan APQ (Automatic Persisted Queries)**: Menghindari network saturasi karena upload string GraphQL besar berulang-ulang dari klien.
- [ ] **Isolasi DataLoader Scope**: DataLoaders dibuat baru pada tiap request cycle di context builder.
- [ ] **Masking Internal Error Extensions**: Pastikan `stacktrace`, database table name, dan internal endpoint disanitasi dari payload `errors` sebelum response keluar ke publik.
- [ ] **Terapkan Field-Level Metrics**: Gunakan instrumentasi OpenTelemetry pada setiap method `resolve()` untuk memantau p95/p99 latency per-resolver.
- [ ] **Timeouts per Downstream Call**: Setiap fetch di dalam resolver wajib dibungkus dengan hard timeout limit (misal: `AbortSignal.timeout(3000)`).

---

### 12. Hands-on Practice

Buatlah implementasi backend GraphQL production-grade di direktori `hands-on/m02/`.

#### Langkah 1: Setup Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install express graphql @graphql-tools/schema dataloader
npm install --save-dev typescript @types/express @types/node ts-node
npx tsc --init
```

Ubah `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  }
}
```

#### Langkah 2: Buat Source Code Terpadu
Buat file `hands-on/m02/server.ts` yang memuat resolver, batched loader, serta AST guard seperti pada seksi 7.

#### Langkah 3: Eksekusi dan Verifikasi Server
Jalankan server:
```bash
npx ts-node server.ts
```

Buka terminal lain, uji dengan payload `curl` untuk melihat batching log:
```bash
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -H "x-user-id: 1" \
  -d '{
    "query": "query GetDashboard { orders(limit: 5) { id total customer { id name email } } }"
  }'
```

**Verifikasi di log terminal server:**
Pastikan hanya muncul **1 kali** pencatatan query batching user, membuktikan N+1 tereliminasi:
`[DB Query Executed] Batch loading users for IDs: 1, 2` (Bukan dipanggil 5 kali per item order).

Uji Query Depth Blocker (Kueri Jahat):
```bash
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query EvilDepth { orders { customer { orders { customer { orders { id } } } } } }"
  }'
```
**Respon Harapan:** HTTP 400 dengan pesan error `Query depth of 5 exceeds maximum allowable depth of 4.`

---

### 13. Exercises

#### Level: Easy
Modifikasi implementasi DataLoader pada seksi 7 untuk menambahkan loader baru bernama `orderByIdLoader` yang menerima string ID order tunggal dan mengembalikan detail Order. Integrasikan ke dalam Query `order(id: ID!): Order`.

#### Level: Medium
Implementasikan custom GraphQL directive `@auth(role: Role)` pada level resolver. Jika user yang mengirim request tidak memiliki role yang diizinkan di dalam auth token context, lempar `GraphQLError` dengan kode `FORBIDDEN` sebelum resolver field dijalankan.

#### Level: Hard
Tulis sebuah Custom AST Validation Visitor yang menghitung **Query Complexity Score Dinamis**.
- Aturan skor:
  - Default scalar field = 1 poin.
  - Object relation = 5 poin.
  - Field yang memiliki argumen `limit` bernilai bilangan bulat `N` = bobot dikalikan dengan `N`.
- Jika total poin kueri melebihi ambang batas 100 poin, hentikan kueri pada fase validasi dan kembalikan laporan validasi error terperinci.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di sebuah fintech dengan infrastruktur multi-tenant. Terdapat endpoint GraphQL federated core yang mengeksekusi integrasi rekening bank. 

**Tantangan**:
1. Rancang arsitektur GraphQL engine yang mampu menangani *Multi-Tenancy Context Isolation*. Tenant A dan Tenant B tidak boleh saling memblokir *DataLoader queues* maupun membagi memory heap context.
2. Selesaikan masalah **DataLoader Cache Stampede**: Jika 10.000 concurrent request membaca profil vendor yang sama (`vendor_id = "V-999"`) secara serentak persis di saat cache context individual dibuat (Cold Start), downstream DB akan lumpuh karena menerima 10.000 batch requests terpisah (masing-masing request memiliki DataLoader sendiri).
3. Bangun mekanisme koordinasi *Two-Tier Caching*:
   - Tier 1: Local Context Loader (In-memory per tick per request).
   - Tier 2: Distributed Redis Cache read-through dengan mekanisme locking (Singleflight/Mutex) sebelum fallback ke PostgreSQL/gRPC.
   - Buat sketsa arsitektur dan draft implementasi komponen batch singleflight resolution tersebut tanpa membocorkan data antar tenant.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic Concepts (5 Soal)
1. **Pada siklus pemrosesan GraphQL, tahapan mana yang mengubah raw string query menjadi token terpisah?**
   - A. Parser
   - B. Lexer
   - C. Validator
   - D. Executor
   *Jawaban yang benar: B*

2. **Apa yang mendasari eksekusi paralel resolver pada root Query di engine GraphQL?**
   - A. Web Worker Threading
   - B. Thread pool native C++
   - C. Concurrency async non-blocking (Promise.all)
   - D. Mutation sequence locking
   *Jawaban yang benar: C*

3. **Mengapa field pada root Mutation dieksekusi secara serial, bukan paralel?**
   - A. Karena GraphQL tidak mendukung mutation paralel
   - B. Untuk menjamin konsistensi state dan mencegah race condition data updates
   - C. Untuk menghemat alokasi memori heap
   - D. Karena database SQL menolak multi-thread queries
   *Jawaban yang benar: B*

4. **Kapan instance DataLoader idealnya dibuat dalam siklus hidup backend service?**
   - A. Sekali saja saat server boot (Global Singleton)
   - B. Di dalam scope resolver masing-masing field
   - C. Baru setiap kali request HTTP masuk (Request-Scoped Context)
   - D. Saat query AST divalidasi
   *Jawaban yang benar: C*

5. **Apa ekstensi respon standar yang digunakan GraphQL untuk menyematkan status code atau metadata error?**
   - A. `meta`
   - B. `extensions`
   - C. `trace`
   - D. `headers`
   *Jawaban yang benar: B*

---

#### Bagian B: Intermediate Concepts (5 Soal)
1. **Bagaimana mekanisme pasti DataLoader menunda (defer) pemanggilan batch function hingga semua resolver di layer yang sama terkumpul?**
   - A. Menggunakan `setTimeout(fn, 1000)`
   - B. Mengantrekan eksekusi pada microtask queue event loop (misal: `process.nextTick` / `Promise.resolve()`)
   - C. Memblokir kernel thread sampai batas timeout tercapai
   - D. Menunggu HTTP socket close
   *Jawaban yang benar: B*

2. **Jika skema GraphQL mendefinisikan field `user: User!` (non-nullable) dan resolvernya melempar exception `null` karena database down, apa yang terjadi pada response tree?**
   - A. Field tersebut menjadi `null` dan field lainnya berjalan normal
   - B. Error diabaikan dan mengembalikan objek kosong `{}`
   - C. Error merambat naik (*bubbles up*) ke parent hingga field nullable pertama, atau seluruh payload `data` menjadi `null`
   - D. Server Express langsung crash (exit code 1)
   *Jawaban yang benar: C*

3. **Fungsi utama dari implementasi Automatic Persisted Queries (APQ) di level gateway/server adalah:**
   - A. Menyimpan hasil query database secara permanen di disk
   - B. Mereduksi bandwidth transmisi dari client ke server dengan mengirim hash 32-byte dari query, bukan string query utuh
   - C. Menghindari kebutuhan validasi skema
   - D. Mengubah GraphQL menjadi gRPC
   *Jawaban yang benar: B*

4. **Argumen ke-4 pada signature resolver `info` bertipe `GraphQLResolveInfo`. Apa kegunaan utamanya yang paling kritikal?**
   - A. Menyimpan session database client
   - B. Memberikan akses metadata AST query, tipe kembalian, dan field selection path yang diminta client
   - C. Berisi token otentikasi JWT
   - D. Berisi instance global DataLoader
   *Jawaban yang benar: B*

5. **Kapan fase Custom AST Validation Rule (seperti Depth Limit) dieksekusi oleh GraphQL Engine?**
   - A. Setelah semua resolver selesai berjalan
   - B. Bersamaan dengan pengiriman response JSON ke HTTP socket
   - C. Setelah parsing string menjadi AST, tetapi sebelum satupun fungsi `resolve()` dijalankan
   - D. Saat kompilasi file TypeScript
   *Jawaban yang benar: C*

---

#### Bagian C: Skenario Kasus Produksi (3 Soal)

1. **Skenario Kasus Memory Leak**: 
   Sebuah server GraphQL Node.js mengalami kenaikan RAM konstan hingga Crash OOM (*Out of Memory*) setelah 3 jam beroperasi di bawah beban moderat. Tim mendapati bahwa konfigurasi DataLoader dibuat seperti berikut:
   ```typescript
   // globalScope.ts
   export const userLoader = new DataLoader(keys => fetchUsers(keys));
   // resolver.ts
   resolve: (_, __, ctx) => userLoader.load(ctx.userId);
   ```
   *Analisis apa yang menyebabkan OOM dan bagaimana arsitektur yang benar?*
   - **Jawaban**: 
     Memory leak disebabkan oleh penggunaan singleton instance `userLoader` di global scope dengan konfigurasi caching aktif (default: `cache: true`). Setiap key yang pernah di-load akan tersimpan secara permanen dalam internal JavaScript `Map` di memory heap tanpa pernah dibersihkan (*no TTL, no LRU eviction*). Seiring berjalannya jutaan request unik, `Map` tersebut membesar tanpa batas hingga Node.js crash OOM. Arsitektur yang benar adalah membuat `userLoader` baru di dalam **Request Context Factory** untuk setiap request HTTP yang masuk. Dengan demikian, ketika HTTP request selesai dan lifecycle context berakhir, seluruh struktur Map DataLoader akan otomatis dibersihkan oleh Garbage Collector.

2. **Skenario Kasus Database Connection Exhaustion**:
   Sistem reporting GraphQL memiliki root query `departments { employees { hardwareAssigned { vendor } } }`. Saat reporting dieksekusi pada 50 department yang memiliki 5.000 employee, pool koneksi database PostgreSQL (max 100 pool) langsung *exhausted* (habis) dan timeout, meskipun DataLoader telah dipasang pada resolver `employees` dan `hardwareAssigned`.
   *Mengapa hal ini terjadi dan bagaimana solusinya?*
   - **Jawaban**: 
     Meskipun DataLoader melakukan batching per layer tree, jumlah entitas yang di-resolve sangat masif (5.000 employee menghasilkan satu batch fetch array ID yang sangat panjang). Jika query batch yang dihasilkan DataLoader tidak memiliki paginasi internal atau batas parameter SQL (`WHERE id IN (...)`), database engine dipaksa melakukan scanning besar yang memakan I/O connections terlalu lama. Lebih buruk lagi, jika child resolver men-trigger *sub-loaders* secara independen, ratusan microtask berbarengan meminta koneksi dari pool secara serempak. Solusinya:
     1. Terapkan paginasi wajib (*Connection specification / slicing*) pada skema (`employees(first: 20)`).
     2. Konfigurasikan *max batch size* pada DataLoader options: `new DataLoader(batchFn, { maxBatchSize: 250 })` untuk memecah query masif menjadi chunks yang aman bagi engine SQL.
     3. Terapkan queue rate limiting / concurrency limiter pada pool client database.

3. **Skenario Distributed Partial Failure**:
   Dalam arsitektur microservice, GraphQL server bertindak sebagai Backend-For-Frontend (BFF). Sebuah kueri halaman profil meminta `User` (dari User-DB), `RecentTransactions` (dari Transaction-Service via REST), dan `CreditScore` (dari Third-party Credit Agency via SOAP). Third-party Credit Agency mengalami timeout (latensi > 10 detik).
   *Bagaimana merancang resolver dan schema agar profil user dan transaksi tetap tampil di UI tanpa terblokir oleh kegagalan Credit Score?*
   - **Jawaban**:
     1. **Schema Design**: Pastikan field `creditScore` didefinisikan sebagai *Nullable*: `type UserProfile { creditScore: CreditScore }` (bukan `CreditScore!`).
     2. **Resolver Level Circuit Breaking & Timeout**: Resolver untuk `creditScore` harus membungkus panggilan network third-party dengan hard timeout (misal: 1.5 detik via `AbortController`).
     3. **Graceful Error Handling**: Ketika panggilan third-party gagal/timeout, resolver menangkap exception menggunakan `try-catch`, mencatat log telemetri/OpenTelemetry, dan mengembalikan `null` ke GraphQL Engine sambil melempar partial execution error:
        ```typescript
        resolve: async (parent, args, ctx) => {
          try {
            return await fetchCreditScoreWithTimeout(parent.id, 1500);
          } catch (err) {
            ctx.reportGraphQLError(new GraphQLError("Credit service unavailable", {
              extensions: { code: "SERVICE_UNAVAILABLE" }
            }));
            return null;
          }
        }
        ```
     Hasilnya: Engine mengembalikan payload HTTP 200 dengan data user dan transaksi yang utuh pada field `data`, sementara status kegagalan third-party diisolasi pada array `errors`.

---

### 16. Summary

- **Eksekusi GraphQL Berbasis Siklus Kompiler**: Eksekusi GraphQL bukan sekadar routing URL, melainkan pemrosesan terstruktur melalui fase **Lexing** $\to$ **AST Parsing** $\to$ **AST Validation** $\to$ **Field Resolution Tree Traversal**.
- **N+1 Problem Ditangani Melalui Loop Synchronization**: DataLoader bukan database tool, melainkan instrumen *I/O coordination* yang memanfaatkan antrean *Microtask Queue* Node.js untuk mendiferensiasi dan mengonsolidasikan panggilan downstream secara deterministik.
- **Isolasi Memori Context Mutlak Diperlukan**: DataLoader dan per-request state *wajib* diisolasi per request cycle guna mencegah kebocoran data (*data leak cross-tenant*) serta memory leaks pada runtime.
- **Keamanan AST Adalah Baris Pertahanan Utama**: Perlindungan API GraphQL produksi tidak mengandalkan rate-limiting IP biasa saja, melainkan validasi struktural dokumen: **Query Depth Limiting**, **Cost Analysis**, dan eliminasi beban parsing melalui **Automatic Persisted Queries (APQ)**.