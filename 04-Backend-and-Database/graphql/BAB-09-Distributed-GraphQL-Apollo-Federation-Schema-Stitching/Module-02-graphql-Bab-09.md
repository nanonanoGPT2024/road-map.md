# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 04-Backend-and-Database
### Topik: GraphQL
### BAB-09: Distributed GraphQL (Apollo Federation & Schema Stitching)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membangun** arsitektur Apollo Federation v2 skala enterprise menggunakan Apollo Router (Rust-based engine) dan multi-subgraph berbasis TypeScript/Node.js.
- **Mengimplementasikan** direktif tingkat lanjut Federation v2 (`@key`, `@shareable`, `@provides`, `@requires`, `@override`, `@inaccessible`, `@tag`) secara presisi untuk memodelkan entitas terdistribusi lintas domain bounded context.
- **Mengoptimalkan** resolusi entitas (`_entities` query) dengan DataLoader guna mengeliminasi masalah distributed $N+1$ problem pada network boundary.
- **Merancang** sistem propagasi metadata, otentikasi/otorisasi terpusat di Router, dan distributed tracing end-to-end menggunakan OpenTelemetry (W3C TraceContext).
- **Mengeksekusi** strategi CI/CD Schema Checks dan Contract Composition menggunakan Rover CLI untuk menjamin zero-downtime deployment pada federated graph.
- **Mengevaluasi dan Melakukan Migrasi** dari arsitektur warisan (Monolithic GraphQL atau Legacy Schema Stitching) menuju Apollo Federation v2 secara bertahap tanpa breaking changes.

---

## 2. Prerequisite

Untuk menyerap materi secara optimal, peserta harus menguasai:
- **GraphQL Fundamentals**: AST, Schema Definition Language (SDL), Resolvers, Field Execution Lifecycle, Directive Execution.
- **Backend Architecture**: Microservices, Domain-Driven Design (Bounded Contexts), REST/gRPC inter-service communication.
- **Node.js & TypeScript Advanced**: Asynchronous runtime, Generics, Decorators/Typing engine, Event Loop behavior.
- **Networking & Infra Basics**: HTTP/2, Reverse Proxy, Containerization (Docker), W3C HTTP Headers, OpenTelemetry metrics/spans.
- **Tools**: Telah menginstal Node.js >= 20.x, Docker Compose, dan Rover CLI (`curl -sSL https://rover.apollo.dev/nix/latest | sh`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Apollo Federation v2 Engine: Query Planner & Execution Core
Apollo Federation v2 menggeser arsitektur gateway dari runtime JavaScript (Node.js Gateway) ke runtime native berperforma tinggi bernama **Apollo Router** (ditulis dalam bahasa Rust). Router tidak mengeksekusi resolver aplikasi secara langsung; tugas utamanya adalah mengorkestrasikan *Query Planning* dan *Distributed Execution*.

```
Client Query
    │
    ▼
┌────────────────────────────────────────────────────────┐
│ Apollo Router (Rust Native Core)                       │
│  ├─ 1. Lexing, Parsing & Validation (AST)              │
│  ├─ 2. Query Planner (DAG Computation)                 │
│  │     └─ Menentukan fetch dependency antar-subgraph   │
│  ├─ 3. Query Plan Execution Engine                     │
│  │     ├─ Fetch A (Parallel / Root)                    │
│  │     ├─ Transformasi Response -> Entities Injection  │
│  │     └─ Fetch B (Dependent / Flattened)              │
│  └─ 4. Response Synthesis & JSON Serialization         │
└──────────────────┬─────────────────┬───────────────────┘
                   │                 │
       HTTP POST   │                 │   HTTP POST
       Entity Batch│                 │   Entity Batch
                   ▼                 ▼
         ┌────────────────┐   ┌────────────────┐
         │ Subgraph: User │   │ Subgraph: Order│
         └────────────────┘   └────────────────┘
```

#### Komponen Internal Query Planner
1. **Federated Schema Representation (Supergraph SDL)**: Gabungan dari schema semua subgraph yang dikompilasi oleh schema composer engine. Menghasilkan schema terpadu yang memetakan field ke owner subgraph masing-masing.
2. **Directed Acyclic Graph (DAG) Generator**: Saat incoming query divalidasi terhadap Supergraph SDL, Query Planner membentuk pohon eksekusi (Query Plan DAG). Node pada DAG merepresentasikan `FetchNode`, `SequenceNode`, `ParallelNode`, dan `FlattenNode`.
3. **Entity Fetch Batching Engine**: Query Planner menganalisis field dependency. Jika query meminta field pada Subgraph B yang bergantung pada entitas di Subgraph A, Router akan:
   - Mengeksekusi query dasar ke Subgraph A untuk mengambil `@key` fields.
   - Mengambil array representation dari key tersebut.
   - Mengirim request batch ke Subgraph B memanfaatkan query internal `_entities(representations: [_Any!]!)`.

### 3.2 Aljabar Direktif Federation v2
Federation v2 memodifikasi model kepemilikan schema secara fundamental melalui direktif-direktif formal:

*   **`@key(fields: FieldSet!, resolvable: Boolean = true)`**: Mendefinisikan entitas dan mekanisme identifikasi uniknya. Jika `resolvable: false`, subgraph tersebut hanya mereferensikan tipe tersebut tanpa harus menyediakan resolver `__resolveReference`.
*   **`@shareable`**: Menghilangkan batasan ketat v1 di mana satu type/field hanya boleh dimiliki oleh tepat satu subgraph. `@shareable` mengizinkan field didefinisikan dan di-resolve oleh lebih dari satu subgraph secara independen.
*   **`@requires(fields: FieldSet!)`**: Menginstruksikan Query Planner bahwa untuk me-resolve suatu field tertentu pada subgraph komputasi, field lain (yang didefinisikan dalam `@requires`) harus di-fetch terlebih dahulu dari subgraph pemilik data asalnya dan dikirimkan lewat argument `representations`.
*   **`@provides(fields: FieldSet!)`**: Optimasi query plan. Menandakan bahwa subgraph ini mampu menyediakan field dari entitas eksternal yang di-return, sehingga Router tidak perlu melakukan hop network tambahan ke subgraph asal field tersebut.
*   **`@override(from: String!)`**: Digunakan untuk migrasi inkremental. Mengambil alih kepemilikan suatu field dari subgraph lama ke subgraph baru tanpa memicu downtime atau kompilasi error.
*   **`@inaccessible`**: Menyembunyikan field dari supergraph publik namun tetap valid dalam internal composition lintas subgraph.
*   **`@tag(name: String!)`**: Memberikan metadata untuk filtering schema (misalnya membuat contract schema untuk publik vs internal partner).

---

## 4. Why & What

### Mengapa Monolithic GraphQL Gagal di Skala Enterprise?
1. **Conway's Law Violation**: Monolith schema memaksa puluhan engineer lintas domain (Auth, Payment, Logistics, Catalog) melakukan commit ke satu repository schema yang sama, memicu *merge conflicts*, *deployment bottlenecks*, dan *shared blast radius*.
2. **Coupled Runtime Scalability**: Layanan katalog baca (read-heavy, misal 200.000 RPS) memerlukan auto-scaling yang masif, sementara order mutation (write-heavy, transaksional, 1.000 RPS) membutuhkan isolasi resource memori dan koneksi database database pooling yang ketat. Menyatukannya dalam satu runtime merusak cost-efficiency infrastruktur.

### Mengapa Bukan Schema Stitching Tradisional?
Schema Stitching v1 mengandalkan delegasi berbasis gateway yang membutuhkan konfigurasi deklaratif manual (`delegateToSchema`), rawan loop dependensi runtime, rapuh terhadap type collision, dan memiliki performa buruk karena berjalan di atas engine Node.js yang membebani V8 Garbage Collector saat parsing AST berskala masif.

### Apa Keunggulan Apollo Federation v2?
Federation v2 memisahkan fase **Composition Time** dan **Runtime Execution**:
- **Composition Time**: Validasi kompatibilitas tipe dilakukan sebelum deployment melalui Rover CLI/Apollo Studio. Jika ada skema yang tidak valid, proses CI/CD dibatalkan.
- **Runtime Execution**: Apollo Router (Rust) memproses jutaan request dengan *zero-copy memory parsing*, latensi sub-millisecond, memory footprint yang sangat kecil (30-50MB vs Node.js Gateway 500MB-1GB), dan optimasi paralelisasi HTTP/2 native.

---

## 5. How (Workflow Detail)

### Alur Eksekusi Query Plan Terdistribusi
Berikut adalah trace langkah-demi-langkah ketika Apollo Router menerima query yang membutuhkan data dari 3 Subgraph (`Users`, `Orders`, `Products`):

```graphql
query GetUserDashboard($userId: ID!) {
  user(id: $userId) {
    name
    orders {
      id
      shippingCost # Dihitung di Subgraph Orders, butuh berat barang dari Products
      items {
        title
        price
      }
    }
  }
}
```

```
[Client]
   │ (1) POST /graphql
   ▼
[Apollo Router]
   │
   ├─► (2) Parse & Validate against Supergraph Schema
   ├─► (3) Generate Execution Plan:
   │       Plan:
   │       Sequence {
   │         Fetch(service: "users") { user(id) { name } }
   │         Fetch(service: "orders") { ... on User { orders { id items { id } } } }
   │         Parallel {
   │           Fetch(service: "products") { ... on Product { title price weight } }
   │         }
   │         Fetch(service: "orders") { ... on OrderItem { shippingCost } using { weight } }
   │       }
   │
   ├─► (4) Send HTTP to Subgraph 'Users' -> Subgraph returns { user: { name: "Alice" } }
   │
   ├─► (5) Send Batch HTTP to Subgraph 'Orders' -> inject { __typename: "User", id: "1" }
   │       Subgraph 'Orders' returns order data, but leaves shippingCost pending
   │
   ├─► (6) Extract Product IDs -> Send Batch _entities query to Subgraph 'Products'
   │       Subgraph 'Products' returns { title, price, weight }
   │
   ├─► (7) Fulfill @requires -> Send Batch _entities to 'Orders' with injected { weight }
   │       Orders menghitung shippingCost
   │
   └─► (8) Merge all JSON fragments -> Stream JSON response to Client
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Perakitan Otomotif
Bayangkan Supergraph sebagai **Pabrik Perakitan Mobil**:
- **Klien**: Konsumen yang memesan mobil dengan spesifikasi warna bodi, jenis transmisi, dan asuransi kecelakaan.
- **Apollo Router**: Manajer Produksi di lini tengah yang memegang buku panduan blueprint (Supergraph Schema). Ia tidak membuat suku cadang sendiri.
- **Subgraph Engine (Users, Products, Orders)**: Bengkel-bengkel spesialis terpisah:
  - Bengkel Mesin (`Products`) memproduksi mesin dan mengukur bobotnya.
  - Bengkel Sasis (`Orders`) merakit sasis, tetapi untuk menghitung pegas peredam kejut (`shippingCost`), mereka meminta data berat mesin (`weight`) dari Bengkel Mesin.
- **Entity Resolution (`_entities`)**: Kontainer forklift standar industri yang membawa nomor serial rangka (`@key(fields: "id")`) antar bengkel untuk dipasangi komponen spesifik masing-masing.

### Diagram: Topologi Apollo Federation v2 Enterprise

```
                       ┌─────────────────────────┐
                       │   WAF / Edge CDN        │
                       └────────────┬────────────┘
                                    │ TLS Termination
                                    ▼
                       ┌─────────────────────────┐
                       │      APOLLO ROUTER      │
                       │   (Rust Runtime / K8s)  │
                       │                         │
                       │  - Auth Context Inject  │
                       │  - Deduplication        │
                       │  - Distributed Tracing  │
                       └────────────┬────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       │ HTTP/2 Internal VPC        │ HTTP/2 Internal VPC        │ HTTP/2 Internal VPC
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│  Users &     │             │  Catalog &   │             │  Checkout &  │
│  Auth Domain│             │  Inventory   │             │  Billing     │
│  Subgraph    │             │  Subgraph    │             │  Subgraph    │
├──────────────┤             ├──────────────┤             ├──────────────┤
│ Node.js/TS   │             │ Go / TS      │             │ Kotlin / TS  │
│ DataLoader   │             │ DataLoader   │             │ DataLoader   │
└──────┬───────┘             └──────┬───────┘             └──────┬───────┘
       │                            │                            │
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│ PostgreSQL   │             │ Redis/Scalla │             │ Aurora MySQL │
└──────────────┘             └──────────────┘             └──────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Basic Entities Sharing
Dua subgraph sederhana yang mereferensikan satu entitas `Product`.

#### Subgraph Products (`products-schema.graphql`)
```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.3", import: ["@key", "@shareable"])

type Query {
  product(id: ID!): Product
}

type Product @key(fields: "id") {
  id: ID!
  name: String!
  price: Float! @shareable
}
```

#### Subgraph Reviews (`reviews-schema.graphql`)
```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.3", import: ["@key"])

type Product @key(fields: "id") {
  id: ID!
  reviews: [Review!]!
}

type Review {
  id: ID!
  rating: Int!
  comment: String!
}
```

---

### 7.2 Practical Enterprise Example: Microservices Federation
Implementasi sistem Order Management yang memisahkan **Inventory Subgraph** dan **Orders Subgraph** menggunakan `@requires` dan entity resolution batched dengan DataLoader.

#### Struktur Proyek
```text
enterprise-federation/
├── router/
│   └── router.yaml
├── inventory-subgraph/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       └── index.ts
└── orders-subgraph/
    ├── package.json
    ├── tsconfig.json
    └── src/
        └── index.ts
```

#### Inventory Subgraph (`inventory-subgraph/src/index.ts`)
```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';
import DataLoader from 'dataloader';

// Schema Definition
const typeDefs = gql`
  extend schema
    @link(
      url: "https://specs.apollo.dev/federation/v2.5"
      import: ["@key", "@shareable"]
    )

  type Product @key(fields: "id") {
    id: ID!
    sku: String!
    weightInGrams: Int! @shareable
    inStock: Boolean!
  }

  type Query {
    products: [Product!]!
  }
`;

interface ProductEntity {
  id: string;
  sku: string;
  weightInGrams: number;
  inStock: boolean;
}

// Simulasi Database
const PRODUCT_DB: Record<string, ProductEntity> = {
  "prod-101": { id: "prod-101", sku: "MKB-PRO", weightInGrams: 1200, inStock: true },
  "prod-102": { id: "prod-102", sku: "MOU-MSE", weightInGrams: 150, inStock: false },
};

// Batch Loader untuk optimasi resolusi reference
const productReferenceLoader = new DataLoader<string, ProductEntity | null>(
  async (ids: readonly string[]) => {
    return ids.map((id) => PRODUCT_DB[id] || null);
  }
);

const resolvers = {
  Product: {
    __resolveReference: async (reference: { id: string }) => {
      if (!reference.id) return null;
      return await productReferenceLoader.load(reference.id);
    },
  },
  Query: {
    products: () => Object.values(PRODUCT_DB),
  },
};

async function main() {
  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });

  const { url } = await startStandaloneServer(server, {
    listen: { port: 4001 },
  });

  console.log(`🚀 Inventory Subgraph siap di: ${url}`);
}

main().catch(console.error);
```

#### Orders Subgraph (`orders-subgraph/src/index.ts`)
Menggunakan `@requires` untuk menghitung ongkir secara dinamis dari berat barang milik Subgraph Inventory.

```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';
import DataLoader from 'dataloader';

const typeDefs = gql`
  extend schema
    @link(
      url: "https://specs.apollo.dev/federation/v2.5"
      import: ["@key", "@requires", "@external"]
    )

  # Menghubungkan entitas eksternal
  type Product @key(fields: "id") {
    id: ID!
    # Field external ini di-fetch dari Subgraph Inventory oleh Router
    weightInGrams: Int! @external
    # Field lokal yang butuh data weightInGrams dari remote subgraph
    calculatedShippingFee(destinationZip: String!): Float! @requires(fields: "weightInGrams")
  }

  type OrderItem {
    orderId: ID!
    product: Product!
    quantity: Int!
  }

  type Query {
    orderItems(orderId: ID!): [OrderItem!]!
  }
`;

interface OrderItemData {
  orderId: string;
  productId: string;
  quantity: Int;
}

const ORDER_DB: OrderItemData[] = [
  { orderId: "ord-9001", productId: "prod-101", quantity: 2 },
  { orderId: "ord-9001", productId: "prod-102", quantity: 1 },
];

const resolvers = {
  Product: {
    // Router memanggil resolver ini dengan menyuntikkan payload @requires secara otomatis
    calculatedShippingFee: (
      productReference: { id: string; weightInGrams?: number },
      args: { destinationZip: string }
    ) => {
      const weight = productReference.weightInGrams;
      if (typeof weight === 'undefined') {
        throw new Error("Invariant Violation: 'weightInGrams' tidak disediakan oleh Query Planner");
      }

      const ratePerKg = args.destinationZip.startsWith("1") ? 10000 : 25000;
      return (weight / 1000) * ratePerKg;
    },
    // Handler referensi saat Product di-query langsung sebagai root entity di Order Context
    __resolveReference: (reference: { id: string }) => {
      return { id: reference.id };
    }
  },
  OrderItem: {
    product: (orderItem: OrderItemData) => {
      // Mengembalikan pointer representasi GraphQL Entity
      return { __typename: 'Product', id: orderItem.productId };
    },
  },
  Query: {
    orderItems: (_: unknown, { orderId }: { orderId: string }) => {
      return ORDER_DB.filter((item) => item.orderId === orderId);
    },
  },
};

async function main() {
  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });

  const { url } = await startStandaloneServer(server, {
    listen: { port: 4002 },
  });

  console.log(`🚀 Orders Subgraph siap di: ${url}`);
}

main().catch(console.error);
```

#### Apollo Router Production Configuration (`router/router.yaml`)
```yaml
supergraph:
  listen: 0.0.0.0:4000

cors:
  allow_any_origin: false
  allow_origins:
    - https://internal-corp.enterprise.com
  allow_headers:
    - content-type
    - authorization
    - x-trace-id

telemetry:
  tracing:
    trace_propagator: tracecontext
    open_telemetry:
      endpoint: "http://otel-collector:4317"
      protocol: grpc

headers:
  all:
    request:
      - propagate:
          named: "authorization"
      - propagate:
          named: "x-request-id"
      - insert:
          name: "x-forwarded-by"
          value: "apollo-router-core"

limits:
  max_request_bytes: 2097152 # 2MB
  parser:
    max_tokens: 15000
    max_depth: 15
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: FinTech Global (Payment & Core Banking Disruption)
*   **Kondisi Awal**: Sistem Core Banking menggunakan Monolithic Node.js GraphQL Gateway dengan 180 resolvers terpusat, melayani 120.000 Request Per Detik (RPS) pada peak hours. Tim Identity, Wallet, Payment Gateway, dan Fraud Detection bekerja pada codebase yang sama.
*   **Masalah**:
    1. Kegagalan fungsi pada sub-sistem Fraud Detection memakan CPU Event Loop Node.js (Crypto check sync) sehingga seluruh gateway freeze, menyebabkan cascading failure total pada pembayaran.
    2. Deploy freeze mingguan diberlakukan karena tingginya risiko regression schema.
*   **Solusi Desain**:
    - **Pemisahan Bounded Context**: Memecah monolith menjadi 4 subgraph independen: Identity Subgraph, Ledger Subgraph, Payment Rail Subgraph, dan Risk Scoring Subgraph.
    - **Pergantian Gateway ke Apollo Router (Rust)**: Deployment router di AWS EKS multi-AZ dengan horizontal pod autoscaler (HPA) berdasarkan CPU Utilization (target 60%).
    - **Propagasi Token Aman**: Router memverifikasi JWT pada Edge, mengekstrak scope, dan menginjeksikan header `x-authenticated-user-id` dan `x-tenant-id` ke internal VPC subgraphs.
    - **Optimasi Dynamic Query**: Penggunaan `@inaccessible` untuk schema experimental dan `@override` untuk memigrasikan field saldo user dari Monolith ke Microservice Ledger baru secara paralel dengan shadow traffic.
*   **Hasil Metrik Produksi**:
    - Latensi Gateway P99 turun dari **480ms** ke **12ms**.
    - Memori infrastruktur orkestrasi terpangkas dari **64 GB RAM (cluster gateway Node.js)** menjadi **1.8 GB RAM (cluster Apollo Router)**.
    - Deployment frequency meningkat dari 1 kali per minggu menjadi rata-rata 18 kali per hari antar tim tanpa ketergantungan deployment koordinatif.

---

## 9. Trade-offs: Analisis Kritis Arsitektural

| Dimensi Arsitektur | Apollo Federation v2 | Legacy Schema Stitching | Monolithic GraphQL |
| :--- | :--- | :--- | :--- |
| **Performance (Latency P99)** | **Sangat Baik**: Router (Rust) mengompilasi plan ke native bytecode, parsing concurrent zero-copy. | **Sedang-Buruk**: Orkestrasi Node.js menambah overhead serialization internal schema delegation. | **Tinggi (Lokal)**: Tidak ada network hop antar services jika DB pooling lokal optimal. |
| **Network Overhead** | **Tinggi**: Subgraph hops via HTTP/gRPC. Distributed N+1 mengancam jika DataLoader diabaikan. | **Sangat Tinggi**: Rentan multiple-hop waterfall jika delegates tidak ter-batch. | **Nol / Sangat Rendah**: Komunikasi in-memory via function calls/process boundary. |
| **Scalability (Tim)** | **Sangat Tinggi**: Autonomous teams, schema checks otomatis, isolated CI/CD pipelines. | **Sedang**: Koordinasi manual file stitching schema masih sering dibutuhkan. | **Sangat Rendah**: Merge conflict konstan, blast radius tunggal jika satu resolver throw OOM. |
| **Cost & Complexity** | **Kompleks**: Membutuhkan Apollo Router, Supergraph Composition Pipeline, Registry / Apollo Studio. | **Sedang**: Cukup library Node.js, tapi kompleksitas maintenance runtime tinggi. | **Murah**: Satu stack deployment, infrastruktur server minimal. |
| **Contract / Safe Deploy** | **Otomatis**: Composition Engine menolak compile jika skema lintas domain inkonsisten. | **Manual**: Runtime error sering baru muncul saat edge traffic memicu query delegasi. | **Tinggi**: Type-check compiler (e.g. TypeScript) langsung memvalidasi code saat compile. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Distributed N+1 Network Cascade
*   **Problem**: Resolver `__resolveReference` pada subgraph meng-query database per record:
    ```typescript
    // ANTI-PATTERN: Menembak database per entitas yang dikirim Router
    __resolveReference: async (ref) => {
      return await db.query('SELECT * FROM products WHERE id = ?', [ref.id]);
    }
    ```
*   **Gejala**: Latensi P99 membengkak ke satuan detik ketika query meminta 100 entitas, Router membanjiri subgraph dengan ratusan query SQL terpisah.
*   **Solusi**: Bungkus referensi selalu menggunakan instance DataLoader bertingkat per request context:
    ```typescript
    __resolveReference: async (ref, context) => {
      return await context.dataLoaders.productLoader.load(ref.id);
    }
    ```

### 2. Mismatched Type Directives Composition Failure
*   **Problem**: Subgraph A mendefinisikan field sebagai non-nullable, Subgraph B mengekstensi dengan nullable:
    ```graphql
    # Subgraph A
    type Account @key(fields: "id") { id: ID! email: String! }
    
    # Subgraph B
    extend type Account @key(fields: "id") { id: ID! email: String } # Composition ERROR!
    ```
*   **Gejala**: Kompilasi Rover CLI melempar error: `[Federation - Composition] Field "Account.email" must have consistent nullability across subgraphs.`
*   **Solusi**: Pastikan `@shareable` digunakan secara konsisten atau definisikan field non-primary hanya pada subgraph otoritatifnya.

### 3. Header Context Stripping
*   **Problem**: Frontend mengirimkan header `Authorization: Bearer <token>`, tetapi subgraph menerima payload kosong/unauthorized.
*   **Akar Masalah**: Apollo Router secara default **memblokir semua headers** demi alasan keamanan (zero-trust perimeter).
*   **Solusi**: Deklarasikan propagasi header secara eksplisit pada `router.yaml` di seksi `headers.all.request`.

---

## 11. Best Practices (Production Checklist)

- [ ] **Gunakan Apollo Router (Rust)** daripada `@apollo/gateway` (Node.js) untuk lingkungan staging dan production.
- [ ] **Gunakan Rover CLI di CI/CD Pipeline**: Jalankan `rover subgraph check` sebelum pull request di-merge ke branch utama untuk mencegah runtime break.
- [ ] **Terapkan Automated Schema Registry**: Simpan Supergraph SDL terkompilasi di object store (e.g., S3/GCS) atau Apollo Studio managed federation.
- [ ] **Strict Timeout Budgeting**: Konfigurasikan client timeout di Apollo Router untuk tiap subgraph (misal: read-service 200ms, write-service 1500ms).
- [ ] **Distributed Tracing Header Injection**: Pastikan Router menginjeksi header `traceparent` (W3C standard) ke setiap request downstream Subgraph.
- [ ] **Isolasi DataLoader Scope**: Instansiasi DataLoader baru pada setiap request context, hindari deklarasi global singleton DataLoader untuk mencegah kebocoran data antar-user (cache bleeding).
- [ ] **Disable Introspection di Production**: Lindungi supergraph publik dari reverse-engineering skema internal.
- [ ] **Terapkan Query Complexity Limit**: Gunakan Router coprocessor atau plugin untuk membatasi query depth (maksimal level 10-15) dan token size.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun Supergraph lokal yang terdiri dari Apollo Router, User Subgraph, dan Order Subgraph.

### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02/{router,subgraph-users,subgraph-orders}
cd hands-on/m02
```

### Langkah 2: Setup User Subgraph
Inisialisasi direktori `subgraph-users`:
```bash
cd subgraph-users
npm init -y
npm install @apollo/server @apollo/subgraph graphql graphql-tag
npm install -D typescript @types/node tsx
npx tsc --init
```

Buat file `subgraph-users/index.ts`:
```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';

const typeDefs = gql`
  extend schema
    @link(url: "https://specs.apollo.dev/federation/v2.3", import: ["@key"])

  type User @key(fields: "id") {
    id: ID!
    username: String!
    tier: String!
  }

  type Query {
    users: [User!]!
    user(id: ID!): User
  }
`;

const USERS = [
  { id: "usr-1", username: "alexandra_core", tier: "GOLD" },
  { id: "usr-2", username: "budi_enterprise", tier: "PLATINUM" },
];

const resolvers = {
  Query: {
    users: () => USERS,
    user: (_: unknown, { id }: { id: string }) => USERS.find((u) => u.id === id),
  },
  User: {
    __resolveReference: (reference: { id: string }) => {
      return USERS.find((u) => u.id === reference.id);
    },
  },
};

async function start() {
  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });
  const { url } = await startStandaloneServer(server, { listen: { port: 4001 } });
  console.log(`User Subgraph running at ${url}`);
}
start();
```

### Langkah 3: Setup Order Subgraph
Inisialisasi direktori `subgraph-orders`:
```bash
cd ../subgraph-orders
npm init -y
npm install @apollo/server @apollo/subgraph graphql graphql-tag
npm install -D typescript @types/node tsx
npx tsc --init
```

Buat file `subgraph-orders/index.ts`:
```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { buildSubgraphSchema } from '@apollo/subgraph';
import gql from 'graphql-tag';

const typeDefs = gql`
  extend schema
    @link(url: "https://specs.apollo.dev/federation/v2.3", import: ["@key"])

  type User @key(fields: "id") {
    id: ID!
    orders: [Order!]!
  }

  type Order {
    id: ID!
    totalAmount: Float!
  }
`;

const ORDERS = [
  { id: "ord-101", userId: "usr-1", totalAmount: 450000 },
  { id: "ord-102", userId: "usr-1", totalAmount: 1200000 },
  { id: "ord-103", userId: "usr-2", totalAmount: 3500000 },
];

const resolvers = {
  User: {
    orders: (user: { id: string }) => {
      return ORDERS.filter((order) => order.userId === user.id);
    },
  },
};

async function start() {
  const server = new ApolloServer({
    schema: buildSubgraphSchema({ typeDefs, resolvers }),
  });
  const { url } = await startStandaloneServer(server, { listen: { port: 4002 } });
  console.log(`Order Subgraph running at ${url}`);
}
start();
```

### Langkah 4: Komposisi Supergraph Menggunakan Rover CLI
Pastikan kedua subgraph menyala di terminal terpisah:
```bash
# Terminal 1
cd hands-on/m02/subgraph-users && npx tsx index.ts
# Terminal 2
cd hands-on/m02/subgraph-orders && npx tsx index.ts
```

Buat file konfigurasi komposisi `hands-on/m02/router/supergraph.yaml`:
```yaml
federation_version: =2.3.0
subgraphs:
  users:
    routing_url: http://localhost:4001/
    schema:
      subgraph_url: http://localhost:4001/
  orders:
    routing_url: http://localhost:4002/
    schema:
      subgraph_url: http://localhost:4002/
```

Jalankan kompilasi Supergraph:
```bash
cd hands-on/m02/router
rover supergraph compose --config ./supergraph.yaml > supergraph-schema.graphql
```

### Langkah 5: Menjalankan Apollo Router
Unduh binary Apollo Router dan jalankan:
```bash
# Download binary apollo-router jika belum ada
curl -sSL https://rover.apollo.dev/nix/latest | sh
curl -sSL https://install.apollographql.com/router/download/nix/latest | sh

# Jalankan Router menggunakan supergraph schema yang baru dibuat
./router --supergraph supergraph-schema.graphql --config router.yaml
```

Buka browser di `http://localhost:4000/` dan jalankan federated query:
```graphql
query TestDistributedFetch {
  users {
    id
    username
    tier
    orders {
      id
      totalAmount
    }
  }
}
```

---

## 13. Exercise

### Level Easy
Modifikasi `subgraph-users` untuk menambahkan field `isActive: Boolean!` yang bersifat `@shareable`. Tambahkan field tersebut ke `subgraph-orders` juga tanpa memicu composition failure. Lakukan re-komposisi dengan Rover dan verifikasi bahwa query planner dapat me-resolve field tersebut dari kedua service.

### Level Medium
Tambahkan direktif `@inaccessible` pada field `tier` di `subgraph-users`. Re-komposisi supergraph dan buktikan melalui GraphQL Playground/Sandbox bahwa client tidak dapat lagi melakukan query terhadap field `tier`, namun subgraph lain tetap dapat mengaksesnya jika diperlukan sebagai `@requires`.

### Level Hard
Implementasikan skenario `@override` migrasi bertahap.
1. Buat Subgraph baru: `subgraph-discounts`.
2. Ambil alih field `tierDiscount` yang awalnya dihitung di `subgraph-users` menggunakan direktif `@override(from: "users")`.
3. Demonstrasikan supergraph composition berhasil dan pastikan query execution diarahkan ke resolver `subgraph-discounts` tanpa merusak downstream client logic.

---

## 14. Challenge

**Skenario Kasus**: Anda memimpin migrasi enterprise core banking dengan persyaratan **zero-downtime SLA 99.999%**.
Terdapat tipe inti `Account` yang memiliki field:
```graphql
type Account @key(fields: "id") {
  id: ID!
  balance: MonetaryAmount!
  owner: User!
  transactions(limit: Int!): [Transaction!]!
}
```
Field `balance` saat ini dimiliki oleh Monolith Core Subgraph (`core-monolith`). Anda diwajibkan memindahkan field `balance` ke Microservice Ledger Subgraph baru (`ledger-subgraph`) yang memiliki struktur database completely isolated (NewSQL).

**Tantangan Arsitektur**:
1. Buat skema dan resolver deklaratif menggunakan teknik `@override` dan parallel execution.
2. Tangani skenario di mana Router harus melakukan fallback jika `ledger-subgraph` mengalami crash saat eksekusi tanpa menggagalkan root entity `Account`.
3. Tuliskan analisis formal: bagaimana penanganan distributed transactions dan cache invalidation jika client melakukan mutasi `transferFunds` yang memperbarui saldo di `ledger-subgraph` sementara audit log berada di `core-monolith`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)
1. Apa fungsi utama Apollo Router dalam arsitektur Federation v2 dibandingkan dengan Apollo Gateway v1?
   - *Jawaban*: Apollo Router ditulis dalam native Rust dengan kinerja mutlak jauh lebih cepat, penggunaan memori minimal, dan query planning DAG zero-copy tanpa latency Event Loop Node.js.
2. Kapan sebuah subgraph entity memerlukan resolver `__resolveReference`?
   - *Jawaban*: Saat subgraph tersebut bertindak sebagai target federasi yang menerima representasi pointer key (misal `@key(fields: "id")`) dari subgraph lain untuk diisi (resolve) field lokalnya.
3. Apa implikasi dari menyetel direktif `@key(fields: "id", resolvable: false)`?
   - *Jawaban*: Router tahu bahwa subgraph tersebut mereferensikan entitas tersebut hanya sebagai foreign reference type dan subgraph tersebut **tidak** menyediakan endpoint `__resolveReference` untuk entitas tersebut.
4. Apa yang membedakan `@shareable` pada Federation v2 dengan field sharing pada Federation v1?
   - *Jawaban*: Di Federation v1, field sharing dilarang kecuali tipe di-extend secara rumit. Di v2, `@shareable` secara eksplisit mengizinkan resolusi multi-subgraph atas field yang sama secara deterministik.
5. Bagaimana Query Planner mengatasi eksekusi GraphQL query dengan field dependency antar-subgraph?
   - *Jawaban*: Membentuk DAG (Directed Acyclic Graph) yang memecah dependency menjadi tahapan `Sequence`, `Parallel`, dan `Flatten` lalu memanggil endpoint `_entities` subgraph downstream.

### Bagian 2: Intermediate (Arsitektur & Konfigurasi)
6. Mengapa penggunaan DataLoader wajib di dalam `__resolveReference` entity resolver?
   - *Jawaban*: Karena query planner router mengirimkan array representasi `_entities` dalam satu HTTP POST batch. Tanpa DataLoader, iterasi array tersebut akan mengeksekusi query database tunggal per elemen (Distributed N+1 database hit).
7. Jelaskan bagaimana direktif `@requires(fields: "...")` bekerja di balik layar!
   - *Jawaban*: Direktif ini memerintahkan Query Planner untuk mengambil field eksternal yang dibutuhkan terlebih dahulu dari subgraph asalnya, lalu menyuntikkannya ke dalam parameter `representation` subgraph yang memiliki anotasi `@requires`.
8. Apa fungsi utama dari `@provides`?
   - *Jawaban*: `@provides` memberi tahu Query Planner bahwa subgraph lokal sudah memiliki cache/data dari field milik subgraph target, sehingga Router tidak perlu membuat network hop tambahan ke subgraph pemilik field tersebut.
9. Mengapa Apollo Router default-nya memblokir propagasi HTTP Headers downstream?
   - *Jawaban*: Untuk mengimplementasikan model keamanan zero-trust dan mencegah kebocoran headers sensitif browser/client (misal cookies, internal headers) ke subgraph pihak ketiga atau internal services yang tidak membutuhkan.
10. Bagaimana Rover CLI memvalidasi kompatibilitas antar schema pada tahap CI/CD?
    - *Jawaban*: Rover mengambil seluruh SDL subgraph, menjalankan aljabar composition Federation v2 untuk mengecek konflik tipe, kepemilikan field, resolvable keys, dan validitas nullability sebelum Supergraph SDL di-build.

### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Dalam eksekusi produksi, didapati endpoint Supergraph mengalami lonjakan error HTTP 500 saat traffic puncak, tetapi metrik CPU Apollo Router hanya berada di 15%. Logs menunjukkan error: `HTTP connection pool exhausted when calling Subgraph Inventory`. Apa akar masalah dan bagaimana langkah mitigasinya?
    - *Solusi Rekayasa*: Koneksi HTTP client connection pool dari Router ke Subgraph Inventory mencapai batas default (Router default pool size). Tambahkan konfigurasi `subgraphs.<name>.client.pool` pada `router.yaml` untuk memperbesar batas max idle connections dan atur keep-alive timeout sesuai kapasitas load balancer upstream subgraph.
12. **Skenario B**: Dua developer dari Tim Billing dan Tim Order mendefinisikan enum yang sama `PaymentStatus { PENDING, SUCCESS, FAILED }`. Tim Order menambahkan nilai baru `REFUNDED` di subgraph-nya, namun lupa memberi tahu Tim Billing. Mengapa supergraph composition gagal di CI/CD dan bagaimana arsitektur Federation v2 mengatasinya?
    - *Solusi Rekayasa*: Federation v2 mengharuskan semua Shared Enum memiliki set nilai (variants) yang identik di semua subgraph agar konsisten. Solusinya: sinkronkan enum di kedua subgraph, atau jadikan status pembayaran sebagai model `@key` entity/scalar contract, atau gunakan pattern semantic versioning pada schema release.
13. **Skenario C**: Sebuah field `@requires(fields: "userTier")` bernilai `undefined` di resolver subgraph tujuan, menyebabkan error runtime: `Cannot read properties of undefined`. Padahal Subgraph User (asal data) berjalan dengan normal. Di mana letak kesalahannya?
    - *Solusi Rekayasa*: Kesalahan umum: field `userTier` pada subgraph tujuan lupa didefinisikan dengan direktif `@external`, ATAU query yang dieksekusi client tidak menyertakan path entitas yang valid sehingga Query Planner memotong cabang dependency tersebut. Pastikan field `@external` dideklarasikan persis dengan tipe asalnya di subgraph pemanggil.

---

## 16. Summary

1. **Apollo Federation v2** adalah standar industri arsitektur GraphQL terdistribusi yang memisahkan perancangan skema secara terdesentralisasi (Domain-Driven Design) dengan eksekusi query native berkecepatan tinggi melalui **Apollo Router**.
2. **Entity-First Modeling**: Fondasi federasi bertumpu pada entitas dengan identifier `@key`. Entitas dapat diperluas, di-share, atau di-override tanpa interupsi service lain.
3. **Optimasi Network**: Integrasi batch entity resolution (`_entities`) dengan pattern **DataLoader** di level Subgraph adalah mitigasi utama terhadap risiko Distributed N+1 Problem pada arsitektur microservices.
4. **Resilience & Governance**: Skalabilitas federasi enterprise dijamin melalui komposisi deterministik di pipeline CI/CD via **Rover CLI**, penegakan observability dengan **OpenTelemetry (W3C traceparent)**, dan propagasi konteks yang aman di Edge Gateway.