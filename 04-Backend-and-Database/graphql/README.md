Berikut adalah rancangan silabus komprehensif kurikulum 10 Bab GraphQL dalam format `README.md` standar enterprise.

```markdown
# Kurikulum Arsitektur GraphQL Enterprise: Zero to Production Engine

Selamat datang di kurikulum teknis mendalam GraphQL. Dokumen ini dirancang sebagai peta jalan (*learning roadmap*) produksi komprehensif bagi Software Engineer, Backend Architect, dan Tech Lead yang ingin menguasai ekosistem GraphQL dari tingkat primitif internal (*parsing*, AST, *execution engine*) hingga arsitektur terdistribusi berskala besar (*Apollo Federation v2*, *Schema Stitching*, dan mitigasi performa kritis).

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma: RPC/REST ke Graph-First Architecture
GraphQL bukan sekadar alternatif dari REST API atau sekadar *transport layer* baru, melainkan sebuah **spesifikasi runtime eksekusi berbasis kontrak skema formal (Schema-Driven Development)**. Mengadopsi GraphQL membutuhkan pergeseran mental model:

1. **Client-Driven Data Fetching:** Klien menentukan secara presisi struktur data yang dibutuhkan (*no over-fetching, no under-fetching*), mengeliminasi *waterfall request* di sisi jaringan perangkat bergerak (*mobile*).
2. **Schema as a Single Source of Truth:** Skema (*Schema Definition Language* / SDL) berperan sebagai kontrak tipe ketat (*strictly-typed contract*) antara frontend dan backend, memfasilitasi otomatisasi validasi, *mocking*, dan *type generation*.
3. **Execution Tree Graph Traversal:** Eksekusi GraphQL memproses query sebagai representasi pohon AST (*Abstract Syntax Tree*). Setiap field diselesaikan (*resolve*) melalui *resolution pipeline* independen yang memerlukan optimasi konkurensi khusus untuk menghindari degradasi I/O.

### Prasyarat (Prerequisites)
- Pemahaman mendalam tentang arsitektur HTTP/1.1, HTTP/2, dan RESTful APIs.
- Penguasaan bahasa pemrograman berbasis I/O asynchronous (TypeScript/Node.js, Go, Java, atau Python).
- Pemahaman dasar tentang Relational Database (SQL/PostgreSQL) dan caching layer (Redis).
- Familiaritas dengan arsitektur microservices dan API Gateway.

---

## 2. Learning Roadmap

```text
[GRAPHQL ENTERPRISE ROADMAP]
├── Bab 01: Fondasi Arsitektur & Komparasi Paradigma
│   ├── REST vs GraphQL vs gRPC
│   ├── GraphQL Runtime & AST Execution Model
│   └── GraphQL Specification & Lifecycle
│
├── Bab 02: Schema Definition Language (SDL) & Strict Type System
│   ├── Primitives, Scalars, & Enums
│   ├── Object Types, Interfaces, & Unions
│   └── Input Objects, Arguments, & Schema Directives
│
├── Bab 03: Resolvers Architecture & Execution Engine Internals
│   ├── Anatomie Resolver: Parent, Args, Context, Info
│   ├── AST Parsing, Lexing, & Field Collection Algorithm
│   └── Execution Pipeline & Asynchronous Resolution
│
├── Bab 04: Advanced Operations: Deep Queries, Mutations, & Directives
│   ├── Complex Nested Queries & Inline Fragments
│   ├── Transactional Mutations & Payload Patterns
│   └── Custom Executable & Type System Directives
│
├── Bab 05: Real-time Architecture: Subscriptions & Streaming
│   ├── WebSocket Transport vs Server-Sent Events (SSE)
│   ├── Pub/Sub Engines & Redis Scaling
│   └── Connection Lifecycle, Heartbeats, & Error Handling
│
├── Bab 06: Data Fetching Optimization: Mengatasi N+1 Problem
│   ├── Anatomi N+1 Query Problem di Graph Engine
│   ├── DataLoader Pattern: Batching, Caching, & Isolation
│   └── Lookahead Analysis & Query Projection Optimization
│
├── Bab 07: Security Engineering & Hardening
│   ├── Query Depth Limiting & Cost/Complexity Analysis
│   ├── Rate Limiting Berbasis Komputasi Field
│   └── Hardening: Introspection, Batch Attacks, & OWASP GraphQL
│
├── Bab 08: Client-Side Integration & Normalized State Management
│   ├── Client Architecture: Apollo Client, URQL, & Relay
│   ├── Normalized Caching, Cache Normalization Keys, & Garbage Collection
│   └── Automated Type Generation dengan GraphQL Code Generator
│
├── Bab 09: Distributed GraphQL: Apollo Federation & Schema Stitching
│   ├── Monolith vs Distributed Graph Architecture
│   ├── Apollo Federation v2: Subgraphs, Entities, & Key Directives
│   └── Federation Router (Rust-based) vs Schema Stitching
│
└── Bab 10: Production Observability, Resiliency, & CI/CD Pipeline
    ├── Tracing, Field-Level Metrics, & OpenTelemetry
    ├── Persisted Queries, APQ, & Edge CDN Caching
    └── Schema Registry, Breaking Change Detection, & CI/CD
```

---

## 3. Navigasi Detail Modul

### Bab 01: Fondasi Arsitektur & Komparasi Paradigma
Membedah GraphQL dari perspektif runtime execution engine dan perbandingannya secara teknis dengan paradigma API modern lainnya.
- [01.1 Mental Model: REST vs GraphQL vs gRPC](./bab-01-fondasi-dan-arsitektur/01-mental-model-rest-vs-graphql-vs-grpc.md)
- [01.2 GraphQL Runtime, AST, dan Siklus Request-Response](./bab-01-fondasi-dan-arsitektur/02-graphql-runtime-dan-ast-execution.md)
- [01.3 Dekonstruksi Spesifikasi GraphQL Resmi](./bab-01-fondasi-dan-arsitektur/03-dekonstruksi-spesifikasi-graphql.md)

### Bab 02: Schema Definition Language (SDL) & Strict Type System
Membangun fondasi domain yang tangguh melalui pemodelan tipe data SDL yang aman, ekspresif, dan berstandar industri.
- [02.1 Scalar Types, Custom Scalars, dan Enumerations](./bab-02-sdl-dan-type-system/01-scalars-custom-scalars-enums.md)
- [02.2 Polymorphism: Interfaces dan Union Types](./bab-02-sdl-dan-type-system/02-interfaces-dan-unions.md)
- [02.3 Input Objects, Validation Rules, dan Schema Directives](./bab-02-sdl-dan-type-system/03-input-types-dan-schema-directives.md)

### Bab 03: Resolvers Architecture & Execution Engine Internals
Mengupas bagaimana GraphQL engine membedah query menjadi struktur pohon dan mengeksekusi *resolver tree* secara concurrent.
- [03.1 Anatomi Resolver Pipeline: `root`, `args`, `context`, dan `info`](./bab-03-resolvers-dan-execution/01-anatomi-resolver-pipeline.md)
- [03.2 Bedah AST: Lexing, Parsing, Field Collection, dan Path Resolution](./bab-03-resolvers-dan-execution/02-bedah-ast-dan-execution-algorithm.md)
- [03.3 Asynchronous Execution, Error Bubbling, dan Partial Responses](./bab-03-resolvers-dan-execution/03-async-execution-dan-error-bubbling.md)

### Bab 04: Advanced Operations: Deep Queries, Mutations, & Directives
Pola perancangan operasi GraphQL tingkat lanjut untuk kebutuhan data transaksional dan manipulasi alur eksekusi runtime.
- [04.1 Desain Nested Queries, Fragments, dan Aliases](./bab-04-operasi-lanjutan/01-nested-queries-fragments-aliases.md)
- [04.2 Mutation Patterns: Idempotency, Payloads, dan Error Union Return](./bab-04-operasi-lanjutan/02-mutation-patterns-dan-payloads.md)
- [04.3 Mengimplementasikan Custom Executable Directives Runtime](./bab-04-operasi-lanjutan/03-custom-executable-directives.md)

### Bab 05: Real-time Architecture: Subscriptions & Streaming
Membangun komunikasi event-driven real-time memanfaatkan GraphQL Subscriptions melalui transport modern.
- [05.1 Transport Layer: WebSocket Protocol (`graphql-transport-ws`) vs SSE](./bab-05-realtime-subscriptions/01-transport-layer-ws-vs-sse.md)
- [05.2 Scaling Subscriptions dengan Distributed Redis Pub/Sub](./bab-05-realtime-subscriptions/02-distributed-pubsub-redis.md)
- [05.3 State Management Koneksi, Auth Lifecycle, dan Backpressure](./bab-05-realtime-subscriptions/03-lifecycle-auth-dan-backpressure.md)

### Bab 06: Data Fetching Optimization: Mengatasi N+1 Problem
Teknik optimasi kritis layer I/O untuk mencegah lonjakan latensi dan beban berlebih pada downstream persistence layer.
- [06.1 Mengapa N+1 Terjadi pada Execution Tree GraphQL](./bab-06-optimasi-data-fetching/01-mekanisme-n-plus-one-problem.md)
- [06.2 DataLoader: Batching, Per-Request In-Memory Cache, dan Prune Cache](./bab-06-optimasi-data-fetching/02-dataloader-batching-caching.md)
- [06.3 Lookahead Analysis Menggunakan `GraphQLResolveInfo` & Database Projection](./bab-06-optimasi-data-fetching/03-lookahead-analysis-projections.md)

### Bab 07: Security Engineering & Hardening
Strategi komprehensif mengamankan endpoint GraphQL dari eksekusi query berbahaya dan kerentanan spesifik graph.
- [07.1 Query Depth Limiting dan Static Analysis](./bab-07-keamanan-graphql/01-depth-limiting-dan-ast-validation.md)
- [07.2 Query Cost Calculation & Complexity-Based Rate Limiting](./bab-07-keamanan-graphql/02-query-complexity-rate-limiting.md)
- [07.3 Hardening Introspection, Batched Attacks, dan OWASP GraphQL Top 10](./bab-07-keamanan-graphql/03-hardening-dan-owasp-top-10.md)

### Bab 08: Client-Side Integration & Normalized State Management
Integrasi aplikasi frontend kelas enterprise dengan fokus pada optimasi local cache dan dynamic code generation.
- [08.1 Client Engines: Apollo Client vs URQL vs Relay Core Philosophy](./bab-08-client-side-integration/01-perbandingan-apollo-urql-relay.md)
- [08.2 Normalized Caching, Cache Eviction, dan Optimistic UI Updates](./bab-08-client-side-integration/02-normalized-cache-dan-optimistic-ui.md)
- [08.3 Enterprise Typings: End-to-End Type Safety dengan GraphQL Code Generator](./bab-08-client-side-integration/03-graphql-codegen-type-safety.md)

### Bab 09: Distributed GraphQL: Apollo Federation & Schema Stitching
Transformasi GraphQL monolitik menjadi platform data terdistribusi terpadu (*Enterprise Supergraph*).
- [09.1 Monolith Graph vs Distributed Micro-Graphs Architecture](./bab-09-distributed-graphql/01-arsitektur-monolith-vs-supergraph.md)
- [09.2 Apollo Federation v2 Core Directives: `@key`, `@shareable`, `@external`, `@requires`](./bab-09-distributed-graphql/02-apollo-federation-v2-directives.md)
- [09.3 Mengoperasikan Federation Router, Subgraph Stitching, dan Query Planning](./bab-09-distributed-graphql/03-federation-router-dan-query-planner.md)

### Bab 10: Production Observability, Resiliency, & CI/CD Pipeline
Operasionalisasi GraphQL pada infrastruktur cloud-native berskala tinggi dengan visibilitas penuh dan deployment aman.
- [09.1 Distributed Tracing, Field-Level Execution Metrics, dan OpenTelemetry](./bab-10-observability-dan-produksi/01-opentelemetry-dan-field-metrics.md)
- [10.2 Edge Caching: Automatic Persisted Queries (APQ) dan HTTP Cache Headers](./bab-10-observability-dan-produksi/02-persisted-queries-dan-edge-caching.md)
- [10.3 Schema Governance: Registry, Breaking Change Detection, dan CI/CD Deployment](./bab-10-observability-dan-produksi/03-schema-checks-dan-cicd-pipeline.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**Enterprise Omnichannel Supply Chain & Marketplace Supergraph**

### Deskripsi Proyek
Proyek akhir ini mengharuskan peserta membangun arsitektur GraphQL tingkat enterprise berskala produksi (*Supergraph*) yang mengintegrasikan ekosistem multi-subgraph untuk platform supply chain global, inventori real-time, dan marketplace B2B.

```text
[Client Layer] ── (Mobile / Web Clients)
       │
       ▼
[Edge / CDN] ── (Cloudflare / Fastly APQ Cache)
       │
       ▼
[Router Gateway] ── (Apollo Router / Rust-based Gateway)
       │           ├── JWT Authentication & Context Propagation
       │           ├── Query Complexity Analysis & Depth Limiting
       │           └── Automated Query Planner Engine
       │
       ├─── Subgraph: Identity & Auth Service (`@key(fields: "id")`)
       ├─── Subgraph: Product Catalog & Pricing (`@key(fields: "sku")`)
       ├─── Subgraph: Inventory & Warehouse (`@key(fields: "sku")` & `@requires`)
       ├─── Subgraph: Order Management & Billing (`@key(fields: "id")`)
       └─── Real-time Subgraph: Live Tracking via SSE / WebSockets
```

### Kebutuhan Fungsional & Arsitektur
1. **Distributed Schema (Apollo Federation v2):**
   - Terdiri dari minimal 4 subgraf independen:
     - `Account/Identity Subgraph`
     - `Product Catalog Subgraph`
     - `Warehouse & Inventory Subgraph`
     - `Order Processing & Fulfillment Subgraph`
   - Implementasi federasi multi-subgraph menggunakan `@key`, `@shareable`, `@external`, `@provides`, dan `@requires`.
   - Menggunakan gateway berbasis performa tinggi (Apollo Router dengan Rust Engine).

2. **Resolusi I/O & Pencegahan Degenerasi Performa:**
   - Implementasi `DataLoader` pada setiap subgraph untuk mencegah *N+1 database queries*.
   - Lookahead dynamic projection menggunakan `GraphQLResolveInfo` untuk mengoptimalkan SELECT query SQL ke backend storage (PostgreSQL).

3. **Pertahanan & Keamanan Runtime Skema:**
   - Validasi query depth maksimal (*depth limit* = 6 level).
   - Validasi query complexity limit berbasis komputasi bobot field (*max cost threshold* per IP/User token).
   - Nonaktifkan `Introspection Query` pada *production environment* dengan mekanisme *safelist/Persisted Queries*.

4. **Real-time Pipeline:**
   - Subgraph fulfillment mengekspos *Subscriptions* untuk perubahan status pemesanan (`orderStatusUpdated`).
   - Transport memanfaatkan WebSocket berstandar `graphql-transport-ws` atau SSE (*Server-Sent Events*), terdistribusi menggunakan Redis Pub/Sub cluster.

5. **Observabilitas & Schema Registry CI/CD:**
   - Integrasi distributed tracing berbasis OpenTelemetry (OTel) dengan visualisasi Jaeger / Prometheus.
   - Pipelining GitHub Actions / GitLab CI yang mengeksekusi `schema check` untuk mendeteksi *breaking changes* sebelum artefak digabungkan (*merge*) ke branch utama.
   - Implementasi *Automatic Persisted Queries (APQ)* dengan layer penyimpanan Redis di sisi router gateway.

### Standar Penilaian
- **Kebenaran Arsitektur:** Resolusi query federasi berjalan tanpa *query plan bottlenecks*.
- **Efisiensi Sistem:** Resolusi data bebas dari masalah N+1 (dibuktikan via logging query profiler).
- **Keamanan:** Mampu menangkis serangan *denial-of-service* berbasis recursive nested query.
- **Kualitas Kode:** Strict typing, idiomatic SDL formatting, dan unit/integration tests untuk setiap resolver minimal 80% coverage.
```