# Kurikulum Arsitektur Desain API Enterprise (API Design)

Selamat datang di kurikulum spesialisasi **Enterprise API Design**. Kurikulum ini dirancang untuk mencetak *Staff Software Engineer*, *API Architect*, dan *Principal Systems Engineer* yang mampu merancang, memvalidasi, mengamankan, dan mengoperasikan antarmuka komputasi terdistribusi pada skala jutaan *requests per second* (RPS) dengan garansi integritas data, ketersediaan tinggi (*high availability*), dan latensi deterministik.

---

## 1. Course Overview & Mindset

### Filosofi Desain: API sebagai Kontrak Abadi
Dalam sistem terdistribusi skala *hyper-growth*, API bukan sekadar jalur eksposur basis data melalui antarmuka HTTP. API adalah **kontrak publik legal formal** antara penyedia layanan (*producer*) dan konsumen (*consumer*). Kegagalan merancang API dengan benar di awal akan mengakibatkan akumulasi utang teknis (*technical debt*), migrasi *breaking-changes* yang mahal, celah keamanan kritis, hingga kebocoran logika domain internal (*domain leakage*).

Prinsip inti yang ditanamkan dalam kurikulum ini:
1. **Contract-First over Code-First**: Desain kontrak formal (OpenAPI, Protobuf, AsyncAPI) mendahului implementasi satu baris kode pun.
2. **Protocol Pragmatism**: Menguasai pemetaan beban kerja spesifik ke protokol yang optimal (REST/HTTP-3 untuk publik/DX, gRPC/Protobuf untuk *internal east-west*, WebSocket/SSE untuk *real-time push*, dan AsyncAPI untuk integrasi *event-driven*).
3. **Resilience & Idempotency by Default**: Setiap mutasi jaringan terdistribusi diasumsikan dapat gagal, terputus di tengah jalan, atau terulang ganda (*at-least-once delivery*). Desain harus tahan banting melalui strategi *idempotency-key* dan kontrol konkurensi optimistik.
4. **Zero-Trust Security**: Mengintegrasikan protokol keamanan *identity federation* (OAuth 2.1, OIDC, FAPI, mTLS) langsung pada lapisan arsitektur API.
5. **Zero-Downtime Evolutive Architecture**: Menjamin siklus hidup evolusi API bebas dari *breaking changes* melalui aturan kompatibilitas mundur (*backward compatibility*) berbasis skema kanonikal.

---

## 2. Learning Roadmap

Berikut adalah topologi kurikulum 10 Bab yang membentuk jalur penguasaan rekayasa API komprehensif:

```text
API DESIGN ENTERPRISE ROADMAP
│
├── [Bab 01] Fondasi & Paradigma Komunikasi Terdistribusi
│   ├── Modul 01: Taksonomi Protokol (REST, gRPC, GraphQL, Event-Driven)
│   ├── Modul 02: Arsitektur Jaringan HTTP/2, HTTP/3 (QUIC), & TCP Socket
│   └── Modul 03: Pemilihan Gaya Interaksi Sinkron vs Asinkron
│
├── [Bab 02] Resource Modeling & Pragmatic REST Architecture
│   ├── Modul 01: Dekomposisi Domain Berbasis DDD ke URI & REST Resources
│   ├── Modul 02: Hierarki Endpoint, Naming Semantics & HTTP Method Safe/Idempotent
│   └── Modul 03: Relational Modeling: HATEOAS, Sub-Resources, & Bulk Actions
│
├── [Bab 03] Contract-First Design & Formal Specifications
│   ├── Modul 01: OpenAPI Specification (OAS 3.1) Lanjutan & Skema JSON 2020-12
│   ├── Modul 02: Protocol Buffers v3 & Schema Evolution Rules
│   └── Modul 03: AsyncAPI untuk Event-Driven & Streaming Topologies
│
├── [Bab 04] Data Serialization, Filtering, & Content Negotiation
│   ├── Modul 01: Content Negotiation (MIME Types, Profiling, Custom Formats)
│   ├── Modul 02: Partial Responses (Sparse Fieldsets), Pagination (Cursor/Offset)
│   └── Modul 03: Serialisasi Kinerja Tinggi (Protobuf vs Avro vs FlatBuffers vs JSON)
│
├── [Bab 05] Distributed Mutability, Concurrency, & Idempotency
│   ├── Modul 01: Idempotency Keys Pattern & Distributed Mutex
│   ├── Modul 02: Optimistic Locking, ETag, & Conditional HTTP Headers
│   └── Modul 03: Pola Kompensasi Mutasi Terdistribusi (Saga Orchestration vs Choreography)
│
├── [Bab 06] Enterprise API Security, Identity, & Governance
│   ├── Modul 01: OAuth 2.1, OIDC, & Financial-grade API (FAPI)
│   ├── Modul 02: Mutually Authenticated TLS (mTLS) & Token Binding
│   └── Modul 03: Authorization Policy Enforcement: ABAC, RBAC, & OPA (Open Policy Agent)
│
├── [Bab 07] Traffic Shaping, Rate Limiting, & Resiliency
│   ├── Modul 01: Algoritma Rate Limiting Terdistribusi (Token/Leaky Bucket, Sliding Window)
│   ├── Modul 02: Resiliency Engineering: Circuit Breaking, Adaptive Retries, & Jitter
│   └── Modul 03: Backpressure & Flow Control Patterns
│
├── [Bab 08] Lifecycle, Versioning, & Evolution Strategy
│   ├── Modul 01: Strategi Versioning (URI, Header, Media Type) & Dampak DX
│   ├── Modul 02: Schema Deprecation, Sunsetting, & Sunset HTTP Headers
│   └── Modul 03: Automated Backward-Compatibility Breaking Detection di CI/CD
│
├── [Bab 09] Developer Experience (DX), SDKs, & Observability
│   ├── Modul 01: RFC 7807/9457 Problem Details Error Abstraction
│   ├── Modul 02: Automated SDK Generation & API Contract Testing (Pact/Prism)
│   └── Modul 03: Distributed Tracing W3C TraceContext & Telemetri API
│
└── [Bab 10] API Gateway Topologies & Edge Architectures
    ├── Modul 01: API Gateway vs Service Mesh vs Ingress Controller
    ├── Modul 02: Caching Strategy: Edge Caching, Cache-Control, & Invalidation
    └── Modul 03: Envoy Proxy, GraphQL Federation, & Gateway Aggregation
```

---

## 3. Navigasi Detail Bab & Modul

### Bab 01: Fondasi & Paradigma Komunikasi Terdistribusi
Fokus pada pemilihan fondasi protokol komunikasi berdasarkan trade-off latensi, throughput, dan karakteristik muatan (*payload*).
* [01-fondasi-paradigma-distribusi/01-taksonomi-protokol.md](01-fondasi-paradigma-distribusi/01-taksonomi-protokol.md): Analisis perbandingan REST, gRPC, GraphQL, dan EDA untuk arsitektur modern.
* [01-fondasi-paradigma-distribusi/02-arsitektur-jaringan-http2-http3.md](01-fondasi-paradigma-distribusi/02-arsitektur-jaringan-http2-http3.md): Multiplexing, Head-of-Line Blocking, binary framing, dan terminasi koneksi QUIC/UDP.
* [01-fondasi-paradigma-distribusi/03-sinkron-vs-asinkron.md](01-fondasi-paradigma-distribusi/03-sinkron-vs-asinkron.md): Trade-off RPC blocking vs decoupled asynchronous messaging di batas (*boundary*) domain.

### Bab 02: Resource Modeling & Pragmatic REST Architecture
Transformasi model bisnis Domain-Driven Design (DDD) menjadi representasi resource RESTful yang pragmatis dan konsisten.
* [02-resource-modeling-rest/01-dekomposisi-domain-ddd.md](02-resource-modeling-rest/01-dekomposisi-domain-ddd.md): Mengidentifikasi Entity, Value Object, dan Aggregate Root menjadi REST collection/singleton.
* [02-resource-modeling-rest/02-hierarki-uri-dan-semantik-http.md](02-resource-modeling-rest/02-hierarki-uri-dan-semantik-http.md): Struktur URI, korelasi aksi HTTP (GET, POST, PUT, PATCH, DELETE) dengan semantik safe & idempotent.
* [02-resource-modeling-rest/03-relasi-hateoas-dan-bulk-actions.md](02-resource-modeling-rest/03-relasi-hateoas-dan-bulk-actions.md): Hypermedia as the Engine of Application State, link relations (RFC 8288), dan pola eksekusi *batch/bulk*.

### Bab 03: Contract-First Design & Formal Specifications
Standarisasi kontrak antarmuka sebagai sumber kebenaran tunggal (*single source of truth*) dalam rekayasa perangkat lunak.
* [03-contract-first-design/01-openapi-3-1-dan-json-schema.md](03-contract-first-design/01-openapi-3-1-dan-json-schema.md): Pemodelan spesifikasi OAS 3.1 komprehensif, diskriminator polimorfisme, dan Schema Validation 2020-12.
* [03-contract-first-design/02-protobuf-dan-schema-evolution.md](03-contract-first-design/02-protobuf-dan-schema-evolution.md): Desain file `.proto`, field tags, *reserved fields*, dan aturan evolusi skema biner bebas konfrontasi.
* [03-contract-first-design/03-asyncapi-streaming-topologies.md](03-contract-first-design/03-asyncapi-streaming-topologies.md): Pemodelan kontrak event/message streams berbasis Kafka, RabbitMQ, dan WebSocket dengan AsyncAPI.

### Bab 04: Data Serialization, Filtering, & Content Negotiation
Optimalisasi efisiensi transfer data pada tingkat byte dan mekanisme query data skala besar.
* [04-serialization-negotiation/01-content-negotiation-deep-dive.md](04-serialization-negotiation/01-content-negotiation-deep-dive.md): Pemanfaatan header `Accept`, `Content-Type`, vendor MIME types, dan schema profiles.
* [04-serialization-negotiation/02-filtering-sorting-pagination.md](04-serialization-negotiation/02-filtering-sorting-pagination.md): Implementasi Cursor-based vs Keyset vs Offset pagination, nested field expansion, dan sparse fieldsets.
* [04-serialization-negotiation/03-benchmarking-serialisasi-biner.md](04-serialization-negotiation/03-benchmarking-serialisasi-biner.md): Evaluasi rasio kompresi, throughput CPU, dan alokasi memori antara JSON, Protocol Buffers, dan Apache Avro.

### Bab 05: Distributed Mutability, Concurrency, & Idempotency
Menjamin integritas data dari duplikasi eksekusi dan tabrakan data mutasi konkuren (*race conditions*).
* [05-mutabilitas-konkurensi-idempotensi/01-idempotency-keys-pattern.md](05-mutabilitas-konkurensi-idempotensi/01-idempotency-keys-pattern.md): Arsitektur penyimpanan state idempotensi, deteksi in-flight request, dan *replaying payload cached*.
* [05-mutabilitas-konkurensi-idempotensi/02-optimistic-locking-etag.md](05-mutabilitas-konkurensi-idempotensi/02-optimistic-locking-etag.md): Implementasi header `ETag`, `If-Match`, `If-None-Match` untuk pencegahan anomali *lost update*.
* [05-mutabilitas-konkurensi-idempotensi/03-pola-kompensasi-saga.md](05-mutabilitas-konkurensi-idempotensi/03-pola-kompensasi-saga.md): Perancangan API endpoints untuk Saga Orchestration, verifikasi status dua arah, dan *action rollbacks*.

### Bab 06: Enterprise API Security, Identity, & Governance
Lapisan proteksi akses berbasis identitas kriptografis tingkat industri untuk sistem multi-tenant.
* [06-security-identity-governance/01-oauth21-oidc-fapi.md](06-security-identity-governance/01-oauth21-oidc-fapi.md): Arsitektur OAuth 2.1: Authorization Code + PKCE, Client Credentials, Token Exchange, dan FAPI compliance.
* [06-security-identity-governance/02-mtls-dan-token-binding.md](06-security-identity-governance/02-mtls-dan-token-binding.md): Penerapan Mutual TLS tingkat transport, X.509 certificate validation, dan DPoP (RFC 9449).
* [06-security-identity-governance/03-authorization-opa-abac.md](06-security-identity-governance/03-authorization-opa-abac.md): Integrasi Open Policy Agent (OPA) / Rego untuk Attribute-Based Access Control pada lapisan perantara API.

### Bab 07: Traffic Shaping, Rate Limiting, & Resiliency
Melindungi kluster API dari lonjakan lalu lintas yang tidak terduga (*thundering herd*) dan serangan kehabisan sumber daya.
* [07-traffic-shaping-resiliency/01-algoritma-rate-limiting.md](07-traffic-shaping-resiliency/01-algoritma-rate-limiting.md): Desain Rate Limiting terdistribusi menggunakan Redis Cluster: Sliding-Window Log vs Token Bucket.
* [07-traffic-shaping-resiliency/02-resilience-circuit-breaker-retries.md](07-traffic-shaping-resiliency/02-resilience-circuit-breaker-retries.md): Perancangan header retry (`Retry-After`), Exponential Backoff dengan Full Jitter, dan State Machine Circuit Breaker.
* [07-traffic-shaping-resiliency/03-backpressure-flow-control.md](07-traffic-shaping-resiliency/03-backpressure-flow-control.md): Penanganan antrean API overload, HTTP 429 vs 503, dan mekanisme *reactive stream backpressure*.

### Bab 08: Lifecycle, Versioning, & Evolution Strategy
Prinsip evolusi arsitektur API secara transparan tanpa merusak integrasi klien lama (*zero customer disruption*).
* [08-lifecycle-versioning-evolution/01-strategi-versioning-api.md](08-lifecycle-versioning-evolution/01-strategi-versioning-api.md): Evaluasi komparatif URI Path, Custom Header, dan Media Type Versioning.
* [08-lifecycle-versioning-evolution/02-deprecations-dan-sunsetting.md](08-lifecycle-versioning-evolution/02-deprecations-dan-sunsetting.md): Penggunaan standar IETF header `Deprecation` dan `Sunset` (RFC 8594) serta audit log telemetri pemanggil.
* [08-lifecycle-versioning-evolution/03-breaking-change-detection-cicd.md](08-lifecycle-versioning-evolution/03-breaking-change-detection-cicd.md): Otomasi pengujian validasi skema linting (Buf CLI, Spectral, OpenAPI-diff) di pipeline CI/CD.

### Bab 09: Developer Experience (DX), SDKs, & Observability
Meningkatkan produktivitas integrasi partner/developer dan menyederhanakan diagnosa anomali terdistribusi.
* [09-dx-sdks-observability/01-rfc-9457-problem-details.md](09-dx-sdks-observability/01-rfc-9457-problem-details.md): Standardisasi schema error payload global menggunakan spesifikasi formal RFC 9457.
* [09-dx-sdks-observability/02-contract-testing-dan-sdk-generation.md](09-dx-sdks-observability/02-contract-testing-dan-sdk-generation.md): Penerapan Consumer-Driven Contract Testing (Pact) dan pipeline code generation SDK berbasis OpenAPI Generator.
* [09-dx-sdks-observability/03-distributed-tracing-w3c.md](09-dx-sdks-observability/03-distributed-tracing-w3c.md): Propagasi tracing context (`traceparent`, `tracestate`) lintas batas mikroservis dan korelasi log API.

### Bab 10: API Gateway Topologies & Edge Architectures
Infrastruktur orkestrasi perbatasan (*edge boundary*), keamanan jaringan luar, dan agregasi data terdistribusi.
* [10-api-gateway-edge/01-topologi-gateway-dan-service-mesh.md](10-api-gateway-edge/01-topologi-gateway-dan-service-mesh.md): Batas tanggung jawab Edge API Gateway (Kong/Envoy) versus Internal Service Mesh (Istio/Linkerd).
* [10-api-gateway-edge/02-edge-caching-dan-invalidation.md](10-api-gateway-edge/02-edge-caching-dan-invalidation.md): Strategi Cache-Control, surrogate keys, stale-while-revalidate, dan arsitektur CDN purge event-driven.
* [10-api-gateway-edge/03-graphql-federation-dan-bff.md](10-api-gateway-edge/03-graphql-federation-dan-bff.md): Pola Backend-for-Frontend (BFF) dan Apollo Federation / gRPC Gateway untuk konsolidasi antarmuka multi-klien.

---

## 4. Enterprise Capstone Project Specification

### Judul Capstone:
**"NexusPay Global Exchange": Multi-Protocol, High-Frequency Cross-Border Settlement & Core-Banking API Engine**

### Latar Belakang Masalah:
Sebuah konsorsium perbankan global membutuhkan platform API generasi baru yang memproses penyelesaian transaksi lintas negara (*cross-border clearing*), konversi valuta asing secara *real-time*, dan rekonsiliasi akun multi-mata uang. Platform ini diakses oleh ribuan bank mitra melalui *public internet* (REST/JSON) dan terintegrasi ke *core-banking engine internal* melalui koneksi berlatensi ultra-rendah (gRPC/Protobuf).

### Persyaratan Arsitektural & Fungsional Wajib:
1. **Multi-Protocol Contract Definition**:
   * Sediakan spesifikasi formal **OpenAPI 3.1** yang mencakup seluruh endpoint publik: Onboarding Akun, Eksekusi Transfer, dan Laporan Rekening.
   * Sediakan spesifikasi **Protobuf v3** untuk jalur performa tinggi: Order Match Engine & Core Ledger Settlements.
   * Sediakan spesifikasi **AsyncAPI** untuk pub/sub status transaksi real-time melalui broker streaming.
2. **Kepatuhan Mutasi Terdistribusi & Idempotensi**:
   * Implementasikan mekanisme *Idempotency-Key* tingkat produksi pada endpoint mutasi pembayaran. Duplikasi request dengan key yang sama dalam kurun waktu 24 jam harus mengembalikan response yang identik tanpa memproses mutasi ganda.
   * Gunakan kontrol konkurensi optimistik berbasis header `If-Match` dan `ETag` untuk mencegah tabrakan saldo (*concurrent balance race condition*).
3. **Standar Keamanan Tingkat Finansial (FAPI Compliant)**:
   * Arsitektur autentikasi berbasis mTLS di edge layer dan token berbasis OAuth 2.1 dengan DPoP (Demonstrating Proof-of-Possession).
   * Engine evaluasi otorisasi berbasis fine-grained ABAC menggunakan Open Policy Agent (OPA).
4. **Resiliensi & Traffic Shaping**:
   * Rate limiting multi-tingkat (per tenant tier & per endpoint category) menggunakan Redis distributed sliding-window.
   * Implementasi circuit breaker dan adaptive retry headers (`Retry-After`) saat upstream clearinghouse bank sentral mengalami degradasi.
5. **Observabilitas & Error Standardization**:
   * Penanganan error terpadu yang mematuhi RFC 9457 Problem Details lengkap dengan *invalid-params tracking* dan *trace identifier*.
   * Injeksi W3C TraceContext di setiap lapisan siklus permintaan.

### Deliverables Capstone:
* Dokumen Arsitektur Desain API Formal (ADR - *Architectural Decision Record*).
* File Spesifikasi Kontrak Valid: `openapi.yaml` (v3.1), `settlement.proto` (v3), dan `asyncapi.yaml`.
* Repositori simulasi implementasi gateway/server (menggunakan Go, Node.js/TypeScript, atau Java/Kotlin) yang mengeksekusi logika idempotensi, rate limiting, validasi ETag, dan handling RFC 9457.
* Pipeline CI/CD yang mengintegrasikan Spectral linter, Buf CLI breaking change detector, dan suite *Consumer-Driven Contract Test* menggunakan Pact.

### Kriteria Kelulusan (Evaluation Rubrics):
| Metrik Penilaian | Bobot | Kriteria Keberhasilan |
| :--- | :--- | :--- |
| **Kematangan Kontrak (Schema Design)** | 25% | OpenAPI 3.1 & Proto3 bebas dari cacat semantik; 100% lulus Spectral strict ruleset; pemodelan resource mematuhi kaidah DDD & REST pragmatis. |
| **Idempotensi & Keamanan Finansial** | 25% | Berhasil menahan 1.000 concurrent payload ganda tanpa menghasilkan double-ledgering; kepatuhan mTLS/DPoP terverifikasi. |
| **Resiliensi & Kendali Trafik** | 20% | Rate limiter sliding-window akurat di bawah stress test; graceful degradation terbukti saat simulasi upstream failure. |
| **Penanganan Error & DX** | 15% | Format error konsisten 100% terhadap RFC 9457; keterbacaan dokumentasi interaktif memadai untuk developer eksternal. |
| **CI/CD Breaking-Change Governance** | 15% | Skrip CI otomatis menggagalkan build jika terdeteksi perubahan field tak kompatibel pada API contracts. |