# BAB 08: Client-Side Integration & Normalized State Management
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengonfigurasi dan mengoptimalkan arsitektur *Normalized Client Cache* (Apollo Client 3.x / Urql Graphcache / Relay Store) pada aplikasi berskala enterprise.
- Membedah representasi internal Directed Acyclic Graph (DAG) dan record pointer (`__ref`) di dalam memori client runtime.
- Mengimplementasikan custom `keyFields`, custom `merge` dan `read` policies untuk pagination berbasis kursor (*Relay-style pagination*) tanpa menduplikasi data.
- Merancang pipeline mutasi optimistik (*Optimistic UI*) yang toleran terhadap kegagalan jaringan dan menjaga integritas state antar-tab melalui `BroadcastChannel`.
- Mengisolasi dan memitigasi memory leak pada single-page application (SPA) berumur panjang menggunakan strategi Cache Eviction, Garbage Collection (`retain`/`release`), dan dereferensi entitas yatim (*orphaned entities*).
- Mengeksekusi hidrasi dan dehidrasi state cache secara aman pada arsitektur hybrid SSR/Streaming (Next.js App Router / Remix).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **GraphQL Fundamentals**: Schema Definition Language (SDL), Selection Sets, Field Aliases, Directives (`@include`, `@skip`), Fragments, dan Operasi (Query, Mutation, Subscription).
- **Relay Cursor Connections Specification**: Struktur `edges`, `node`, `pageInfo`, `cursor`, `hasPreviousPage`, dan `hasNextPage`.
- **TypeScript Advanced**: Discriminated Unions, Generics, Template Literal Types, Utility Types (`Partial`, `Omit`, `Extract`).
- **Browser Runtime & Storage Engine**: Event Loop, Microtask execution, Memory Heap Snapshots, Structured Clone Algorithm, LocalStorage, IndexedDB, dan Web Workers API.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Document Cache vs. Normalized Cache
Mayoritas HTTP cache (seperti React Query standar, SWR, atau browser HTTP cache) beroperasi menggunakan **Document Cache**. Respons disimpan menggunakan pasangan *cache-key* berupa string query dan variabel:

$$\text{Cache Key} = \text{Hash}(\text{QueryString} + \text{Variables})$$

Jika Query A mengambil `{ user(id: "1") { name status } }` dan Query B mengambil `{ user(id: "1") { status role } }`, pembaruan pada `status` di Query B tidak akan mengotomatisasi pembaruan data pada Query A. Hal ini menyebabkan inkonsistensi antarmuka (*split-brain state*).

Sebaliknya, **Normalized Cache** (Apollo Client, Relay, Urql Graphcache) mendekonstruksi payload hierarkis (pohon respons) menjadi struktur datar (*flat map*) berbasis entitas relasional:

$$\text{Record Key} = \text{TypeName} + \text{":"} + \text{Identifier (ID)}$$

```
Raw Response:
{
  "data": {
    "organization": {
      "__typename": "Organization",
      "id": "org_42",
      "name": "Acme Corp",
      "members": [
        { "__typename": "User", "id": "usr_99", "name": "Alice" }
      ]
    }
  }
}

Normalized Store (In-Memory Hash Map):
ROOT_QUERY: {
  "organization({\"id\":\"org_42\"})": { "__ref": "Organization:org_42" }
}
Organization:org_42: {
  "__typename": "Organization",
  "id": "org_42",
  "name": "Acme Corp",
  "members": [
    { "__ref": "User:usr_99" }
  ]
}
User:usr_99: {
  "__typename": "User",
  "id": "usr_99",
  "name": "Alice"
}
```

#### B. Internal Graph Representation & The Pointer Subsystem (`__ref`)
Normalized cache memelihara Directed Acyclic Graph (DAG) di mana setiap entitas independen didefinisikan sebagai *Record*, dan relasi didefinisikan sebagai *Reference Object* berformat `{ __ref: string }`.
1. **Normalization Pass**: Traverser rekursif menelusuri payload respons GraphQL. Setiap objek dengan metadata `__typename` dan field identitas (default: `id` atau `_id`) dipotong dari pohon JSON asli, dikonversi menjadi entitas datar, dan digantikan oleh simpul pointer (`__ref`).
2. **Denormalization Pass (Query Reading)**: Ketika komponen UI meminta data dengan query tertentu, engine cache menelusuri tree dari root (`ROOT_QUERY`), membaca field, mengikuti referensi pointer `__ref`, merekonstruksi nested object asli, dan mengirimkan immutable snapshot ke subscriber.
3. **Dependency Graph & Reactive Tracking**: Cache engine mendaftarkan dependensi reaktif. Setiap komponen merekam daftar record ID yang membentuk pohon datanya. Jika record `User:usr_99` diperbarui melalui mutasi apa pun, hanya komponen yang menaruh listener pada referensi `User:usr_99` yang akan dipicu untuk re-render.

#### C. Optimistic Layering Topology
Client state engine tingkat lanjut mengimplementasikan *layered commit log*. Apollo Client menggunakan arsitektur dual-layer:
- **Base Layer (Root Store)**: Menyimpan state terkonfirmasi dari respon server.
- **Optimistic Layer**: Array bertingkat dari patch virtual yang diaplikasikan di atas Base Layer. Ketika mutasi dipicu dengan respons optimistik, patch virtual di-push ke layer optimistik. Denormalizer membaca evaluasi:

$$\text{State}_{\text{visible}} = \text{Fold}(\text{BaseStore}, \text{OptimisticLayers})$$

Ketika server merespons sukses, layer optimistik dibuang (*popped*), dan respons faktual ditulis langsung ke Base Layer. Jika server mengembalikan respons *error* (HTTP 5xx, GraphQL errors), layer optimistik dibuang, dan UI langsung kembali ke base state tanpa memicu dirty reads.

---

### 4. Why & What

| Fitur | Document Cache (SWR/React Query standar) | Normalized Cache (Apollo / Relay / Urql) |
| :--- | :--- | :--- |
| **Penyimpanan State** | Berdasarkan Key Request (Query + Variables). | Flat Entity Hash-Map berbasis Graph Identity. |
| **Duplikasi Data** | Tinggi. Objek sama yang di-fetch multi-query diduplikasi. | Nol. Satu objek entitas hanya tersimpan satu kali. |
| **Konsistensi Data** | Memerlukan invalidasi manual / refetch massal. | Otomatis. Perubahan satu entitas merefleksikan seluruh UI. |
| **Konsumsi Memori** | Rendah saat query sedikit, memburuk saat skala membesar. | Efisien terhadap duplikasi; overhead pada metadata pointer. |
| **Kompleksitas Setup** | Sangat Rendah (Out of the box). | Menengah hingga Tinggi (Butuh TypePolicies & tuning kursor). |
| **Pagination Handling** | Array concat manual per cache key. | Graph normalization via Custom Merge Functions. |

#### Problem yang Dipecahkan:
1. **Data Inconsistency Syndrome**: Profil pengguna di Header menampilkan nama lama, sedangkan di Halaman Pengaturan menampilkan nama baru.
2. **Over-fetching via Network Refetching**: Kebutuhan me-refetch 5 query berbeda hanya karena satu status toggle berhasil diubah di database.
3. **Ghost Writes & Race Conditions**: Respon mutasi yang lambat menimpa mutasi yang lebih baru karena tidak adanya transaction layering.

---

### 5. How (Workflow Detail)

Alur normalisasi end-to-end dari fase eksekusi query hingga konsumsi UI:

```
[UI Component] 
      │ 
      ▼ (1) executeQuery(GetOrgDocument, { id: "org_42" })
[Client Core] 
      │
      ├─────► [Cache Read Phase]
      │             │
      │             ├───► Hit? ───► [Denormalize Graph] ───► [Emit to Component]
      │             │
      │             └───► Miss? ──┐
      │                           ▼
      │                 [Network Layer / Link Chain]
      │                           │
      │                           ▼ (2) HTTP POST GraphQL Payload
      │                 [Backend GraphQL API]
      │                           │
      │                           ▼ (3) JSON Response Packet
      │                 [Network Layer / Link Chain]
      ▼                           │
[Cache Normalization Engine] ◄────┘
      │
      ├───► (4) Extract Entity Identity via TypePolicies (keyFields)
      │         Generated Key = "Organization:org_42"
      │
      ├───► (5) Recursive Flattening
      │         Root Object: Replace nested members with [{ __ref: "User:usr_99" }]
      │
      ├───► (6) Write to Layered Table (Base Store)
      │         Update Record: "User:usr_99"
      │         Update Record: "Organization:org_42"
      │         Update Pointer: ROOT_QUERY -> organization({"id":"org_42"})
      │
      ├───► (7) Notify Watchers / Reactive Graph Observers
      │
      ▼
[UI Component Render Cycle]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Konvensional vs. Relational Registry
- **Document Cache (Perpustakaan Konvensional)**: Setiap kali siswa meminta bundel ringkasan tentang "Buku Sejarah & Profil Penulis", pustakawan memfotokopi seluruh buku beserta profil penulis ke dalam satu map. Jika penulis berganti nomor telepon, pustakawan harus memeriksa ribuan map hasil fotokopi untuk mencoret nomor lama satu per satu.
- **Normalized Cache (Relational Registry)**: Pustakawan hanya menyimpan satu kartu indeks per penulis di lemari utama. Semua map ringkasan hanya memuat kartu referensi: `Lihat Penulis: #007`. Ketika nomor telepon penulis berganti, pustakawan hanya mengedit kartu `#007`. Seketika, ribuan map yang merujuk ke `#007` otomatis menampilkan informasi yang valid.

#### Topological Diagram: In-Memory Pointer Graph
```
============================== IN-MEMORY CACHE TOPOLOGY ==============================

                ┌───────────────────────────────────────┐
                │              ROOT_QUERY               │
                └──────────────────┬────────────────────┘
                                   │
         ┌─────────────────────────┴────────────────────────┐
         │                                                  │
         ▼                                                  ▼
"viewer": { __ref: "User:usr_101" }         "project(id:'p_1')": { __ref: "Project:p_1" }
         │                                                  │
         │                                                  ▼
         │                                      ┌───────────────────────┐
         │                                      │      Project:p_1      │
         │                                      ├───────────────────────┤
         │                                      │ id: "p_1"             │
         │                                      │ name: "Apollo Engine" │
         │                                      │ lead: {               │
         │                                      │   __ref: "User:usr_101"──┐ (Shared Reference)
         │                                      │ }                     │  │
         │                                      │ tasks: [              │  │
         │                                      │   {__ref:"Task:t_1"}, │  │
         │                                      │   {__ref:"Task:t_2"}  │  │
         │                                      │ ]                     │  │
         │                                      └───────────┬───────────┘  │
         │                                                  │              │
         ▼                                                  ▼              │
┌─────────────────────────┐                     ┌───────────────────────┐  │
│      User:usr_101       │◄────────────────────┴───────────────────────┼──┘
├─────────────────────────┤                                             │
│ __typename: "User"      │                                             │
│ id: "usr_101"           │                                             │
│ email: "lead@corp.internal"                                           │
│ status: "ONLINE"        │◄── (Single update here mutates viewer & lead)│
└─────────────────────────┘                                             │
                                                                        │
        ┌───────────────────────────────────────────────────────────────┘
        │
        ├───────────────────────────────────┐
        ▼                                   ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│        Task:t_1         │       │        Task:t_2         │
├─────────────────────────┤       ├─────────────────────────┤
│ id: "t_1"               │       │ id: "t_2"               │
│ title: "Write Parser"   │       │ title: "Ship AST"       │
│ completed: false        │       │ completed: true         │
└─────────────────────────┘       └─────────────────────────┘
======================================================================================
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: TypePolicy Dasar dan Setup Custom Keys
Konfigurasi Apollo Client 3 untuk memetakan skema dengan primary key non-standar (`uuid` bukan `id`).

```typescript
// src/lib/apollo-simple.ts
import { ApolloClient, InMemoryCache, HttpLink } from "@apollo/client";

export const simpleClient = new ApolloClient({
  link: new HttpLink({ uri: "https://api.enterprise.domain/graphql" }),
  cache: new InMemoryCache({
    typePolicies: {
      Device: {
        // Custom identifier: gabungan clusterId dan hardwareUuid
        keyFields: ["clusterId", "hardwareUuid"],
      },
      GlobalConfig: {
        // Singleton Object tanpa ID
        keyFields: false,
      },
    },
  }),
});
```

#### B. Practical Enterprise Example: Full Cache Policies, Optimistic Mutation, dan Relay Cursor Merge
Implementasi production-grade untuk sistem *Financial Ledger Task Manager*.

```typescript
// src/lib/apollo-client.ts
import {
  ApolloClient,
  InMemoryCache,
  FieldPolicy,
  Reference,
  makeVar,
  gql,
} from "@apollo/client";

// Reactive Variable untuk Client-Side Transient State
export const isOfflineSyncActiveVar = makeVar<boolean>(false);

interface RelayConnection<T> {
  edges: Array<{
    cursor: string;
    node: T;
    __typename: string;
  }>;
  pageInfo: {
    hasNextPage: boolean;
    hasPreviousPage: boolean;
    startCursor?: string;
    endCursor?: string;
  };
  totalCount?: number;
}

// Custom FieldPolicy untuk Relay Cursor-Based Pagination
const relayPaginationPolicy = (): FieldPolicy<RelayConnection<Reference>> => {
  return {
    keyArgs: ["filter", ["type", "status"]], // Partisi cache berdasarkan filter kritis
    merge(existing, incoming, { args }) {
      const mergedEdges = existing ? existing.edges.slice(0) : [];
      
      // Hitung offset jika server menyediakan kursor, atau lakukan dedup berbasis node pointer
      const existingRefKeys = new Set(
        mergedEdges.map((edge) => edge.node.__ref)
      );

      for (const edge of incoming.edges) {
        if (!existingRefKeys.has(edge.node.__ref)) {
          mergedEdges.push(edge);
          existingRefKeys.add(edge.node.__ref);
        }
      }

      return {
        ...incoming,
        edges: mergedEdges,
        pageInfo: incoming.pageInfo,
        totalCount: incoming.totalCount ?? existing?.totalCount,
      };
    },
    read(existing) {
      return existing;
    },
  };
};

export const enterpriseCache = new InMemoryCache({
  typePolicies: {
    Query: {
      fields: {
        transactions: relayPaginationPolicy(),
      },
    },
    Transaction: {
      keyFields: ["id"],
      fields: {
        // Virtual Field Resolver
        isAuditable: {
          read(_, { readField }) {
            const amount = readField<number>("amount");
            const status = readField<string>("status");
            return (amount ?? 0) > 100000 && status === "SETTLED";
          },
        },
      },
    },
  },
});

export const apolloClient = new ApolloClient({
  uri: process.env.NEXT_PUBLIC_GRAPHQL_ENDPOINT,
  cache: enterpriseCache,
  connectToDevTools: process.env.NODE_ENV !== "production",
});
```

Contoh eksekusi Optimistic Mutation:

```typescript
// src/features/transactions/mutations/useApproveTransaction.ts
import { useMutation, gql } from "@apollo/client";

export const APPROVE_TRANSACTION = gql`
  mutation ApproveTransaction($id: ID!, $comment: String!) {
    approveTransaction(id: $id, comment: $comment) {
      id
      status
      approvedAt
      auditComments {
        id
        comment
        author
      }
      __typename
    }
  }
`;

export function useApproveTransaction() {
  const [mutate, result] = useMutation(APPROVE_TRANSACTION);

  const executeApproval = async (transactionId: string, userEmail: string) => {
    return await mutate({
      variables: {
        id: transactionId,
        comment: "Fast-path automated enterprise sign-off",
      },
      optimisticResponse: {
        approveTransaction: {
          id: transactionId,
          status: "SETTLED",
          approvedAt: new Date().toISOString(),
          auditComments: [
            {
              id: `temp_comment_${Date.now()}`,
              comment: "Fast-path automated enterprise sign-off",
              author: userEmail,
              __typename: "AuditComment",
            },
          ],
          __typename: "Transaction",
        },
      },
      update(cache, { data }) {
        if (!data?.approveTransaction) return;

        // Modifikasi langsung pada fragmen atau identitas spesifik
        cache.modify({
          id: cache.identify({ __typename: "Transaction", id: transactionId }),
          fields: {
            status() {
              return "SETTLED";
            },
          },
        });
      },
    });
  };

  return { executeApproval, ...result };
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Multi-Tenant B2B FinTech Dashboard (Juta Transaksi Harian)
Sebuah perusahaan Unicorn FinTech mengalami degradasi performa akut pada platform web konsol kasir:
1. **Insiden**: Komputer kasir mengalami Crash Out-Of-Memory (OOM) setiap 4–6 jam operasi terus-menerus.
2. **Investigasi Heap Snapshot**: Cache GraphQL client mengakumulasi lebih dari 350.000 record transaksi individual (`ROOT_QUERY.transactions.edges`) tanpa mekanisme *eviction*.
3. **Ghost Records**: Komponen tabs yang dibuka-tutup meninggalkan *detached reference nodes* yang tidak bisa disapu oleh browser V8 garbage collector karena pointer referensi `__ref` masih dipegang oleh InMemoryCache.

#### Solusi Arsitektural:
1. **Bapped-Window Cursor Pagination Policy**: Membatasi kapasitas buffer edge connection pada memory cache hingga maksimum 250 record terbaru; edge lama secara aktif dipotong dari cache.
2. **Explicit Cache Eviction Lifecycle**: Mengaitkan siklus hidup unmounting route dengan operasi `cache.evict()` dan `cache.gc()`.
3. **Cross-Tab Synchronization**: Memanfaatkan Web standard `BroadcastChannel` untuk merefleksikan mutasi antar-tab tanpa network over-fetching.

```typescript
// src/lib/cache-lifecycle.ts
import { enterpriseCache } from "./apollo-client";

export class CacheLifecycleManager {
  private static broadcast = new BroadcastChannel("graphql_cache_sync_bus");

  public static init() {
    this.broadcast.onmessage = (event) => {
      const { type, entityId } = event.data;
      if (type === "INVALIDATE_RECORD") {
        // Evict spesifik entitas yang dimutasi di tab lain
        enterpriseCache.evict({ id: entityId });
        enterpriseCache.gc();
      }
    };
  }

  public static broadcastInvalidation(entityId: string) {
    this.broadcast.postMessage({
      type: "INVALIDATE_RECORD",
      entityId,
    });
  }

  public static pruneOrphanedEntities() {
    // Jalankan Garbage Collection deterministik
    const deadIds = enterpriseCache.gc();
    if (process.env.NODE_ENV !== "production") {
      console.info(`[Apollo GC] Collected ${deadIds.length} dead records.`);
    }
  }
}
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Aggressive Normalization** | Redundansi data 0%, auto-update UI antar view berbeda, data payload hemat. | Runtime overhead CPU saat parsing respons JSON besar; kompleksitas debugging meningkat. |
| **Optimistic Updates** | Zero-latency perceived performance bagi user; respons instan pada UI. | State rollback complexity; potensi *flicker* jika respons server divergen secara struktural dari estimasi payload. |
| **Deep Relay Connections** | Standarisasi pagination, cursor tracking fleksibel, bidirectional pagination. | Struktur payload GraphQL membengkak (`edges`, `node`, `pageInfo`); merge function kompleks di client. |
| **Persistent Cache (IndexedDB)** | Waktu booting aplikasi instan (instant-on) saat offline atau reload; network resilience. | Risiko membaca data basi (*stale data attacks*); kompleksitas migrasi skema cache lokal saat rilis API versi baru. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Fragment Tanpa `id` atau `__typename`
- **Gejala**: Mutasi dieksekusi, network respons sukses, tetapi antarmuka tidak ter-update tanpa manual refresh.
- **Akar Masalah**: Selection set pada mutation query tidak mengembalikan field yang didefinisikan sebagai `keyFields` (default: `id` dan `__typename`). Cache tidak dapat mencocokkan respons dengan hash table yang ada, dan memperlakukannya sebagai objek anonim tanpa referensi.
- **Solusi**: Pastikan ESLint rules `@graphql-eslint/require-id-when-available` diaktifkan di pipeline CI.

#### Mistake 2: Cache Key Collision pada Polymorphic Types (Unions/Interfaces)
- **Gejala**: Data objek polymorphic (misal implementasi interface `PaymentMethod` berupa `CreditCard` dan `BankTransfer`) saling menimpa jika keduanya memiliki `id` numerik identik dari database terpisah.
- **Solusi**: Konfigurasi `possibleTypes` pada `InMemoryCache` agar normalizer menyadari hierarki polimorfisme, dan tambahkan `__typename` eksplisit dalam setiap fragment matching.

#### Mistake 3: Dangling Pointer Post-Eviction
- **Gejala**: Operasi `cache.evict({ id: 'Task:10' })` dipanggil, tetapi query yang me-retrieve daftar array task melempar runtime error: `Missing field 'title' while writing result`.
- **Akar Masalah**: `cache.evict()` membuang objek record dari hash map, tetapi referensi `{ __ref: "Task:10" }` masih tersimpan di dalam array parent (`Project:p_1.tasks`).
- **Solusi**: Hapus pointer referensi menggunakan modifier filter:

```typescript
cache.modify({
  id: cache.identify({ __typename: "Project", id: projectId }),
  fields: {
    tasks(existingTaskRefs: Reference[], { readField }) {
      return existingTaskRefs.filter(
        (ref) => readField("id", ref) !== targetTaskId
      );
    },
  },
});
// Jalankan GC untuk membersihkan orphan metadata
cache.gc();
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **TypePolicies Strictness**: Definisikan `keyFields` untuk setiap tipe skema yang tidak memiliki properti standar `id`.
2. [ ] **Always Request `__typename`**: Verifikasi konfigurasi build tool (seperti `graphql-tag` atau `@graphql-codegen`) menginjeksi metadata `__typename` secara otomatis pada setiap composite type.
3. [ ] **Bound Array Merges**: Pada field pagination, selalu terapkan *window bounding* (misal max 500 records) untuk mencegah unbounded memory expansion pada browser mobile.
4. [ ] **Optimistic Mutation Safety**: Pastikan setiap optimistic response memiliki ID sementara yang deterministik dan mock shape yang merefleksikan 100% kontrak skema GraphQL.
5. [ ] **Automated Cache Garbage Collection**: Jadwalkan `cache.gc()` pada saat browser berada pada state idle (`requestIdleCallback`) pasca navigasi rute utama.
6. [ ] **SSR Safe Hydration**: Jangan pernah berbagi (*share*) single instance ApolloCache antar concurrent server requests di Next.js/Node.js untuk menghindari kebocoran data antar-pengguna (*Cross-Request State Pollution*). Buat instance client baru per-request.

---

### 12. Hands-on Practice

Buat dan implementasikan file-file berikut pada direktori: `hands-on/m02/`

#### File 1: `hands-on/m02/src/schema.graphql`
```graphql
type Task {
  id: ID!
  title: String!
  isCompleted: Boolean!
  priority: Priority!
  updatedAt: String!
}

enum Priority {
  LOW
  MEDIUM
  HIGH
}

type TaskEdge {
  cursor: String!
  node: Task!
}

type PageInfo {
  hasNextPage: Boolean!
  endCursor: String
}

type TaskConnection {
  edges: [TaskEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type Query {
  taskList(first: Int, after: String, priority: Priority): TaskConnection!
}

type Mutation {
  toggleTaskStatus(id: ID!): Task!
  createTask(title: String!, priority: Priority!): Task!
  deleteTask(id: ID!): ID!
}
```

#### File 2: `hands-on/m02/src/cache-engine.ts`
Implementasi enterprise-grade cache manager dengan eviction, mutation patching, dan isolation.

```typescript
import { InMemoryCache, Reference } from "@apollo/client";

export function createProductionCache(): InMemoryCache {
  return new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          taskList: {
            keyArgs: ["priority"],
            merge(existing, incoming) {
              const existingEdges: Reference[] = existing ? existing.edges : [];
              const incomingEdges: Reference[] = incoming ? incoming.edges : [];
              
              // Dedup edges by pointer
              const existingNodePointers = new Set(
                existingEdges.map((e: any) => e.node.__ref)
              );

              const filteredIncoming = incomingEdges.filter(
                (e: any) => !existingNodePointers.has(e.node.__ref)
              );

              return {
                ...incoming,
                edges: [...existingEdges, ...filteredIncoming],
                pageInfo: incoming.pageInfo,
              };
            },
          },
        },
      },
      Task: {
        keyFields: ["id"],
        fields: {
          title(existing: string) {
            return existing;
          },
        },
      },
    },
  });
}
```

#### File 3: `hands-on/m02/src/cache-operations.test.ts`
Suite pengujian unit untuk memverifikasi referensial cache, mutasi optimistik, dan dereferensi dangling pointer.

```typescript
import { createProductionCache } from "./cache-engine";
import { gql } from "@apollo/client";

describe("Normalized Cache Structural Tests", () => {
  it("should normalize incoming task connections into disjoint records and maintain pointers", () => {
    const cache = createProductionCache();
    
    const query = gql`
      query GetTasks {
        taskList(priority: HIGH) {
          edges {
            cursor
            node {
              id
              title
              isCompleted
              priority
              updatedAt
              __typename
            }
            __typename
          }
          pageInfo {
            hasNextPage
            endCursor
            __typename
          }
          totalCount
          __typename
        }
      }
    `;

    const serverData = {
      taskList: {
        __typename: "TaskConnection",
        totalCount: 1,
        pageInfo: {
          __typename: "PageInfo",
          hasNextPage: false,
          endCursor: "c_1",
        },
        edges: [
          {
            __typename: "TaskEdge",
            cursor: "c_1",
            node: {
              __typename: "Task",
              id: "task_100",
              title: "Hardening Cluster",
              isCompleted: false,
              priority: "HIGH",
              updatedAt: "2023-10-27T00:00:00Z",
            },
          },
        ],
      },
    };

    // Tulis ke cache
    cache.writeQuery({
      query,
      data: serverData,
    });

    // Validasi Flat Record Store
    const extracted = cache.extract();
    expect(extracted["Task:task_100"]).toBeDefined();
    expect(extracted["Task:task_100"]?.title).toBe("Hardening Cluster");

    // Lakukan evict dan verifikasi dereferensi
    cache.evict({ id: "Task:task_100" });
    const collectedGarbage = cache.gc();
    
    expect(cache.extract()["Task:task_100"]).toBeUndefined();
    expect(collectedGarbage).not.toContain("Task:task_100"); // Sudah ter-evict sebelumnya
  });
});
```

---

### 13. Exercise

#### Level: Easy
Diberikan payload JSON GraphQL dari endpoint `userProfile`. Konfigurasikan instance `InMemoryCache` dengan custom `keyFields` untuk entitas `UserSetting` yang menggunakan kombinasi properti `userId` dan `sectionKey` sebagai compound primary key.

#### Level: Medium
Buat sebuah fungsi custom `FieldPolicy.merge` untuk array komentar polymorphic (`Comment` dan `AuditNote`). Merge policy harus mampu menggabungkan array baru dengan array lama, membuang duplikasi berdasarkan ID entitas, dan mempertahankan urutan waktu secara descending berdasarkan field `createdAt`.

#### Level: Hard
Implementasikan custom cache updater untuk mutasi `deleteTask(id: ID!)`. Update handler harus:
1. Menghapus task dari root cache store secara aman menggunakan `cache.evict`.
2. Menghapus referensi task yang bersangkutan dari semua *active paginated connection lists* di memori (`ROOT_QUERY.taskList(...)`) tanpa peduli variasi argumen filter-nya.
3. Menurunkan field `totalCount` sebesar 1 pada masing-masing connection metadata.
4. Mengeksekusi dereferensi dangling edge secara atomik.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Web Architect di bursa perdagangan aset digital (*Crypto Exchange*). Dashboard platform menerima update via WebSocket Subscription sebanyak 500 pembaruan harga (*OrderBook ticks*) per detik. 
- Jika setiap update langsung di-apply via `cache.modify()` atau respons subscription standar, UI thread browser mengalami *frame dropping* (terjun ke < 10 FPS) dan memori membengkak hingga browser freeze.
- **Tantangan Arsitektur**:
  1. Rancang dan tulis spesifikasi teknis arsitektur integrasi client yang mengabstraksi penulisan ke GraphQL cache menggunakan mekanisme **Batched Queue Time-Slicing** (Throttle Flush Buffer).
  2. Buffer harus menahan seluruh mutation/subscription records, melakukan *deduplikasi data* secara in-memory (hanya mengambil *latest state* per ticker pair) selama jendela interval 100ms.
  3. Flush mutasi yang diagregasi ke Normalized Cache menggunakan single transaction context (`cache.performTransaction()`) untuk membatasi UI re-render rate maksimal 10Hz, sambil mempertahankan keandalan optimistik rollback jika WebSocket koneksi terputus tiba-tiba (*network drop*).
  4. Dokumentasikan diagram lifecycle state data dari WebSocket packet hingga paint execution.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan struktural utama antara document-based caching dan normalized caching?**
   - *Jawaban*: Document cache menyimpan keseluruhan respons query berdasarkan hash string query dan variabelnya. Normalized cache memecah struktur respons hierarkis menjadi entitas-entitas data datar (flat record) yang diidentifikasi secara unik menggunakan kombinasi `__typename` dan ID dalam format DAG.
2. **Kapan Apollo Client menghasilkan field `__ref` di dalam state tree-nya?**
   - *Jawaban*: `__ref` dihasilkan saat traversal engine mendeteksi sebuah objek composite dengan metadata identitas (secara default `__typename` dan `id`/`_id`) dan mengekstraknya dari root parent, menggantikannya dengan sebuah pointer referensial.
3. **Apa kegunaan dari directive `__typename` pada operasi client-side?**
   - *Jawaban*: Untuk memberikan metadata discriminator tipe eksplisit yang dibutuhkan oleh cache engine dalam mengonstruksi Graph Identity Key (`TypeName:ID`) dan mengevaluasi fragment types pada Union atau Interface types.
4. **Apa yang terjadi secara default jika Anda mengeksekusi mutasi yang mengembalikan ID objek yang sudah ada di cache tanpa konfigurasi custom update?**
   - *Jawaban*: Normalized cache akan secara otomatis menimpa field-field lama pada record tersebut dengan nilai-nilai field baru yang diterima dari mutation response, lalu memicu re-render pada komponen UI yang me-listen record tersebut.
5. **Mengapa singleton types (tipe tanpa ID) harus diset `keyFields: false`?**
   - *Jawaban*: Untuk memberitahu cache engine agar tidak mencoba membuat key identifier unik (seperti `TypeName:undefined`), melainkan menyematkan field-fieldnya langsung ke dalam record parent tempat objek tersebut bersarang.

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara kerja Optimistic UI rollback ketika server mengembalikan error 500?**
   - *Jawaban*: Optimistic UI disimpan di layer patch terpisah di atas base store. Jika terjadi kegagalan respons, client engine cukup membuang (discard/pop) layer optimistik tersebut. Base store yang bersih langsung dirender ulang tanpa perlu adanya mutasi balik manual.
2. **Jelaskan risiko memory leak yang diasosiasikan dengan penggunaan `cache.evict()` tanpa dibarengi `cache.gc()`!**
   - *Jawaban*: `cache.evict()` menghapus objek yang ditunjuk dari entitas store, tetapi reference pointer (`__ref`) di dalam array list pada entitas lain atau `ROOT_QUERY` tetap ada (dangling reference), sehingga ukuran index referensi internal tetap bertambah dan denormalization queries berpotensi menerima partial missing data.
3. **Mengapa argumen pagination (seperti `first`, `after`) harus dikecualikan dari `keyArgs` pada Relay connections?**
   - *Jawaban*: Jika pagination cursor dijadikan bagian dari `keyArgs`, setiap page baru akan membentuk partisi field terpisah di cache (misal: `taskList({"first":10,"after":"abc"})`), sehingga mempersulit penggabungan continuous list di satu tempat dan meniadakan fungsi scrolling list yang kohesif.
4. **Apa fungsi dari `cache.identify(object)` dalam operasi pembaruan manual?**
   - *Jawaban*: Menghasilkan string Canonical Record Key (misalnya `"Task:123"`) berdasarkan TypePolicies skema dari input objek yang diberikan, memastikan manipulasi cache via `cache.modify` atau `cache.readFragment` menunjuk ke alamat record yang presisi.
5. **Mengapa kita tidak boleh membagikan instance InMemoryCache yang sama di antara request yang berbeda dalam arsitektur Server-Side Rendering (SSR)?**
   - *Jawaban*: Akan terjadi kebocoran state antar pengguna (*Cross-Request State Pollution*), di mana data privat dari Pengguna A yang tersimpan di memori cache server dapat terhidrasi dan terkirim ke dalam payload HTML milik Pengguna B.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario 1**: 
   Aplikasi e-commerce Anda memiliki list produk. Saat user melakukan scroll ke bawah (infinite scroll pagination), user menekan tombol "Wishlist" pada produk #85. Ikon berubah menjadi merah sesaat, tetapi saat scroll berlanjut dan batch data baru ter-fetch, status produk #85 kembali menjadi false. 
   - *Pertanyaan*: Analisis kemungkinan penyebab kegagalan sinkronisasi cache ini!
   - *Jawaban*: Kegagalan merge policy pada query pagination list. Saat fetch batch halaman berikutnya selesai, fungsi `merge` pagination kemungkinan secara keliru me-replace seluruh array list produk lama dengan array list baru (alih-alih melakukan append/deduplikasi), atau pagination query merespons produk #85 kembali dengan field `isWishlisted: false` dari snapshot replika database backend yang mengalami *replication lag*, menimpa base store client.

2. **Skenario 2**: 
   Sebuah aplikasi Enterprise Healthcare menggunakan polling interval setiap 3 detik untuk query `patientVitals`. Meskipun memory browser stabil, profil CPU DevTools menunjukkan *CPU spikes* reguler setiap 3 detik yang mengakibatkan interface *jank/stutter*. Data yang masuk 99% identik di setiap polling.
   - *Pertanyaan*: Langkah mitigasi arsitektur apa yang harus dilakukan di level client cache?
   - *Jawaban*: Implementasikan konfigurasi policy `canonizeResults: true` atau manfaatkan structural sharing comparison di cache. Jika data payload sama persis, cache denormalizer harus mengembalikan referensi objek memori yang identik (*referential equality*), mencegah React tree memicu siklus reconciler dan re-rendering komponen yang tidak perlu.

3. **Skenario 3**: 
   Pengguna mengeluhkan bahwa saat mereka membuka dua tab browser secara berdampingan: Tab A mengubah status sebuah task dari "PENDING" menjadi "DONE", namun Tab B tetap menampilkan status "PENDING" sampai halaman di-refresh sepenuhnya. Tim menolak menggunakan GraphQL Subscription penuh via WebSocket karena pertimbangan beban infrastruktur server.
   - *Pertanyaan*: Solusi apa yang paling efisien diimplementasikan di client-side architecture?
   - *Jawaban*: Pasang `BroadcastChannel API` atau `SharedWorker` yang diintegrasikan ke dalam link pipeline GraphQL Client. Setiap mutasi sukses di Tab A memancarkan payload ringkas `{ entityId, typename, fields }` melalui channel lokal. Tab B mendengarkan channel tersebut dan langsung mengeksekusi `cache.modify()` atau `cache.evict()` secara lokal tanpa membebani backend dengan koneksi persisten.

---

### 16. Summary

- **Normalized Caching** adalah fondasi state management client-side berskala enterprise untuk GraphQL, menggantikan fragmentasi document-based caching dengan struktur DAG yang deterministik.
- Komponen inti dari normalized cache bertumpu pada **Graph Identity** (`__typename` + `keyFields`), **Reference Pointer** (`__ref`), dan partisi **Layer Optimistik**.
- Pengelolaan relasi kompleks seperti **Relay-style Connections** memerlukan perancangan `keyArgs` dan custom `merge` functions yang presisi untuk menghindari duplikasi data dan partisi cache yang terpecah.
- Pembersihan memori via `cache.evict()` dan `cache.gc()` bersifat wajib pada aplikasi Long-Lived SPA guna mencegah kebocoran memori (OOM) dan *dangling pointers*.
- Di level enterprise, konsistensi data client diperkuat dengan kombinasi **Optimistic Updates** berlayer, sinkronisasi multi-tab via **BroadcastChannel**, dan penanganan isolasi instance cache pada arsitektur hybrid **SSR/Streaming**.