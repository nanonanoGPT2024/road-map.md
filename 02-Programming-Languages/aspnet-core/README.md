# Enterprise ASP.NET Core: From Internals to Cloud-Native Systems

Selamat datang di silabus kurikulum komprehensif **ASP.NET Core**. Kurikulum ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi Software Engineer menjadi Technical/Solutions Architect yang menguasai ekosistem modern .NET (fokus pada .NET 8/9 LTS). 

Silabus ini tidak hanya mengajarkan sintaksis dan penggunaan API tingkat permukaan, melainkan membongkar arsitektur internal runtime, mekanika pipeline I/O berkinerja tinggi, model memori *zero-allocation*, integrasi sistem terdistribusi, hingga orkestrasi skala *enterprise*.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
ASP.NET Core adalah salah satu framework *web* modern tercepat di dunia. Namun, kecepatan dan skalabilitas tersebut hanya dapat dicapai apabila *engineer* memahami apa yang terjadi di bawah lapisan abstraksi (*under the hood*). Kurikulum ini dibangun atas prinsip:
- **No Magic**: Memahami *Common Language Runtime* (CLR), alokasi tumpukan memori (*Heap* vs *Stack*), siklus hidup *thread pool*, dan struktur soket I/O Kestrel.
- **Performance by Default**: Menerapkan paradigma alokasi memori mendekati nol (*zero-allocation*) menggunakan `Span<T>`, `Memory<T>`, dan `System.IO.Pipelines`.
- **Architectural Rigor**: Menolak arsitektur spaghetti dengan menerapkan *Clean Architecture*, *CQRS*, *Vertical Slice Architecture*, dan *Domain-Driven Design* (DDD).
- **Production-Ready Standards**: Mengintegrasikan observabilitas tingkat *enterprise* (OpenTelemetry), keamanan berlapis (*Zero Trust*), dan ketahanan sistem (*fault tolerance*) sejak hari pertama.

### Mental Model & Mindset
1. **Request Lifecycle as a Pure Pipeline**: Setiap HTTP *request* adalah aliran data biner yang ditransformasikan melalui rantai *middleware* terbalik yang terisolasi.
2. **Resource-Conscious Development**: Garbage Collector (GC) bukan alasan untuk menulis kode boros memori. Penggunaan `async/await` yang salah dapat memicu *Thread Pool Starvation* dan melumpuhkan sistem terdistribusi.
3. **Pragmatic Technology Choices**: Memilih antara *Minimal APIs* vs *Controllers*, atau *Entity Framework Core* vs *Dapper* bukan masalah preferensi personal, melainkan analisis kompromi (*trade-off analysis*) atas beban kerja (*workload*), *throughput*, dan kompleksitas domain.

### Target Audiens & Prasyarat
- **Target**: Backend Engineers, .NET Developers (Mid-to-Senior), Technical Leads, dan Cloud Architects.
- **Prasyarat**:
  - Pemahaman mendalam tentang C# modern (C# 10/11/12/13), termasuk generics, delegates, tasks, dan record types.
  - Pemahaman dasar mengenai arsitektur jaringan (TCP/IP, HTTP/1.1, HTTP/2, HTTP/3, WebSockets, TLS).
  - Pengalaman bekerja dengan basis data relasional (SQL) dan tools kontainerisasi (Docker).

---

## 2. Learning Roadmap

```plaintext
ASP.NET Core Mastery Roadmap
│
├── [Bab 01] .NET Runtime, Hosting, & Request Pipeline Architecture
│   ├── CLR & Generic Host Initialization
│   ├── Kestrel Internals, Libuv, & Socket Transports
│   └── Middleware Pipeline Mechanics & HttpContext Lifecycle
│
├── [Bab 02] Dependency Injection & Configuration Deep Dive
│   ├── Service Lifetimes & IoC Container Internals
│   ├── Advanced Configuration Providers & Custom Sources
│   └── Options Pattern, Hot-Reload, & Validation
│
├── [Bab 03] Modern Web API & Routing: Minimal API vs Controllers
│   ├── MVC Controller Action Lifecycles & Formatters
│   ├── Minimal APIs, Route Endpoints, & Source Generators
│   └── Native AOT Compilation & High-Throughput Endpoints
│
├── [Bab 04] Data Access with Entity Framework Core & Dapper
│   ├── EF Core Change Tracker, Compiled Queries, & Interceptors
│   ├── Migrations Strategy, Concurrency, & Split Queries
│   └── High-Performance Hybrid Persistence with Dapper
│
├── [Bab 05] Authentication, Authorization, & Identity Security
│   ├── Cryptographic Token Engines, JWT, & OAuth2/OIDC
│   ├── Policy-Based, Role-Based, & Resource-Based Authorization
│   └── ASP.NET Core Identity & Data Protection System
│
├── [Bab 06] Validation, Error Handling, & Fault Tolerance
│   ├── Validation Pipelines & FluentValidation Integration
│   ├── Exception Handling Middleware & Problem Details (RFC 7807)
│   └── Resilience Engineering with Polly v8 (Circuit Breaker & Retries)
│
├── [Bab 07] Asynchronous Messaging & Real-Time Communication
│   ├── Real-Time Bi-Directional Engine with SignalR
│   ├── Background Processing, IHostedService, & Channels
│   └── Distributed Event-Driven Architecture with MassTransit & RabbitMQ
│
├── [Bab 08] High Performance, Caching, & Memory Optimization
│   ├── In-Memory, Distributed (Redis), & Hybrid Caching
│   ├── Zero-Allocation Programming with Span<T> & Pipelines
│   └── Response Caching, Output Caching, & Compression
│
├── [Bab 09] Observability, Logging, & Production Diagnostics
│   ├── Structured Logging with Serilog & Semantic Conventions
│   ├── OpenTelemetry Tracing, Metrics, & Distributed Correlation
│   └── Health Checks, DiagnosticSource, & Memory Dump Analysis
│
└── [Bab 10] Enterprise Architecture & Cloud-Native Deployment
    ├── Clean Architecture, Vertical Slice, & CQRS Patterns
    ├── Containerization with Docker & Distroless/Chiseled Images
    └── Kubernetes Orchestration, Zero-Downtime, & Mesh Integration
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: .NET Runtime, Hosting, & Request Pipeline Architecture](./01-dotnet-runtime-hosting-internals/README.md)
Membedah arsitektur internal proses inisialisasi .NET dan alur siklus hidup penanganan koneksi masuk dari sistem operasi ke dalam kode aplikasi.
* [01-clr-and-generic-host.md](./01-dotnet-runtime-hosting-internals/01-clr-and-generic-host.md): Eksekusi CLR, konfigurasi `IHostBuilder`, `IHostApplicationLifetime`, dan siklus hidup aplikasi.
* [02-kestrel-reverse-proxy-and-sockets.md](./01-dotnet-runtime-hosting-internals/02-kestrel-reverse-proxy-and-sockets.md): Arsitektur Kestrel, multiplexing soket, integrasi Reverse Proxy (YARP, NGINX), dan TLS Termination.
* [03-middleware-pipeline-internals.md](./01-dotnet-runtime-hosting-internals/03-middleware-pipeline-internals.md): Struktur `RequestDelegate`, rantai eksekusi ganda middleware, thread safety `HttpContext`, dan pooling context.

### [Bab 02: Dependency Injection & Configuration Deep Dive](./02-dependency-injection-and-configuration/README.md)
Mendalami implementasi container Inversion of Control bawaan runtime dan sistem hierarki konfigurasi enterprise.
* [01-service-lifetimes-and-di-container.md](./02-dependency-injection-and-configuration/01-service-lifetimes-and-di-container.md): Manajemen memori dan resolusi dependency `Transient`, `Scoped`, `Singleton`, serta pencegahan *Captive Dependencies*.
* [02-configuration-providers-and-options-pattern.md](./02-dependency-injection-and-configuration/02-configuration-providers-and-options-pattern.md): Hierarki konfigurasi JSON, Environment Variables, Azure Key Vault, serta implementasi `IOptions`, `IOptionsSnapshot`, dan `IOptionsMonitor`.
* [03-custom-di-scopes-and-validation.md](./02-dependency-injection-and-configuration/03-custom-di-scopes-and-validation.md): Pembuatan scope DI manual untuk worker thread, root provider validation, dan konfigurasi auto-startup validation.

### [Bab 03: Modern Web API & Routing: Minimal API vs Controllers](./03-web-api-and-routing/README.md)
Analisis mendalam mengenai evolusi model pemrograman web pada ASP.NET Core: Controller-based vs Minimal APIs dan dampaknya terhadap throughput.
* [01-controller-lifecycle-and-action-results.md](./03-web-api-and-routing/01-controller-lifecycle-and-action-results.md): Model binding, Action Filters, Result Filters, dan eksekusi serialisasi berbasis `System.Text.Json`.
* [02-minimal-apis-source-generators-aot.md](./03-web-api-and-routing/02-minimal-apis-source-generators-aot.md): Anatomi Minimal APIs, `RouteHandlerBuilder`, Source Generators, dan optimasi pemangkasan (*trimming*) untuk Native AOT.
* [03-endpoint-routing-and-content-negotiation.md](./03-web-api-and-routing/03-endpoint-routing-and-content-negotiation.md): Pohon perutean (*Endpoint Routing Tree*), evaluasi constraint regex, negosiasi konten kustom, dan pembuatan OpenAPI/Swagger otomatis.

### [Bab 04: Data Access with Entity Framework Core & Dapper](./04-data-access-efcore-dapper/README.md)
Strategi orkestrasi persistensi data enterprise yang menyeimbangkan kemudahan developer dengan performa transaksional ekstrem.
* [01-ef-core-change-tracker-and-query-execution.md](./04-data-access-efcore-dapper/01-ef-core-change-tracker-and-query-execution.md): Mekanisme internal `ChangeTracker`, status mutasi entitas, `AsNoTrackingWithIdentityResolution`, dan translasi ekspresi IQueryable ke SQL.
* [02-migrations-concurrency-and-performance.md](./04-data-access-efcore-dapper/02-migrations-concurrency-and-performance.md): CI/CD Migration bundle, handling konflik konkurensi optimistik (`RowVersion`), split queries, dan pooling DbContext.
* [03-hybrid-data-access-dapper-and-raw-sql.md](./04-data-access-efcore-dapper/03-hybrid-data-access-dapper-and-raw-sql.md): Implementasi pola hybrid: Command via EF Core untuk integritas domain, Query via Dapper untuk throughput baca maksimal.

### [Bab 05: Authentication, Authorization, & Identity Security](./05-auth-and-identity-security/README.md)
Membangun fondasi keamanan zero-trust menggunakan standar protokol industri mutakhir.
* [01-jwt-cookie-and-oauth2-oidc-flows.md](./05-auth-and-identity-security/01-jwt-cookie-and-oauth2-oidc-flows.md): Validasi token JWT kriptografis, rotasi kunci asimetris (JWKS), penanganan refresh token aman, dan federasi OIDC.
* [02-policy-and-resource-based-authorization.md](./05-auth-and-identity-security/02-policy-and-resource-based-authorization.md): Implementasi otorisasi deklaratif, custom `IAuthorizationRequirement`, dynamic imperative authorization, dan evaluasi berbasis izin multi-tenant.
* [03-aspnet-core-identity-and-data-protection.md](./05-auth-and-identity-security/03-aspnet-core-identity-and-data-protection.md): Ekstensi ASP.NET Core Identity, two-factor authentication (2FA), dan kriptografi persistensi kunci `IDataProtectionProvider`.

### [Bab 06: Validation, Error Handling, & Fault Tolerance](./06-validation-resilience/README.md)
Standarisasi penanganan galat dan penguatan keandalan sistem terhadap degradasi jaringan atau dependensi eksternal.
* [01-fluentvalidation-and-model-binding-filters.md](./06-validation-resilience/01-fluentvalidation-and-model-binding-filters.md): Validasi stateless strongly-typed dengan FluentValidation, integrasi pipeline validator, dan validasi rekursif.
* [02-global-error-handling-and-problem-details.md](./06-validation-resilience/02-global-error-handling-and-problem-details.md): Implementasi `IExceptionHandler`, standarisasi RFC 7807 Problem Details, dan pencegahan Information Disclosure via stack trace sanitization.
* [03-resilience-with-polly-v8.md](./06-validation-resilience/03-resilience-with-polly-v8.md): Penerapan Polly v8 Resilience Pipeline: Circuit Breaker, Exponential Backoff with Jitter, Timeout, dan Bulkhead Isolation.

### [Bab 07: Asynchronous Messaging & Real-Time Communication](./07-messaging-and-realtime/README.md)
Desain komunikasi konkuren, distribusi tugas latar belakang, dan pengiriman event asinkron berlatensi rendah.
* [01-realtime-engine-with-signalr.md](./07-messaging-and-realtime/01-realtime-engine-with-signalr.md): Arsitektur SignalR Hub, negosiasi protokol (WebSockets, SSE, Long Polling), streaming data biner, dan horizontal scaling via Redis Backplane.
* [02-background-tasks-and-channels.md](./07-messaging-and-realtime/02-background-tasks-and-channels.md): Pemrosesan asynchronous dengan `BackgroundService`, `IHostedLifecycleService`, dan implementasi Producer-Consumer in-memory via `System.Threading.Channels`.
* [03-event-driven-messaging-masstransit.md](./07-messaging-and-realtime/03-event-driven-messaging-masstransit.md): Integrasi Message Broker (RabbitMQ/Azure Service Bus) menggunakan MassTransit, transactional outbox pattern, dan idempotency consumer.

### [Bab 08: High Performance, Caching, & Memory Optimization](./08-caching-and-memory-optimization/README.md)
Teknik profiling tingkat lanjut untuk menekan penggunaan garbage collector dan memangkas latency hingga ke batas minimum.
* [01-memory-distributed-and-hybrid-cache.md](./08-caching-and-memory-optimization/01-memory-distributed-and-hybrid-cache.md): Pola Cache-Aside, pencegahan Cache Stampede menggunakan `HybridCache` baru di .NET 9, dan penanganan distributed eviction.
* [02-zero-allocation-spans-and-pipelines.md](./08-caching-and-memory-optimization/02-zero-allocation-spans-and-pipelines.md): Pemanfaatan `ReadOnlySpan<T>`, manipulasi parser biner menggunakan `System.IO.Pipelines`, `ArrayPool<T>`, dan deteksi memory leaks.
* [03-output-caching-and-response-compression.md](./08-caching-and-memory-optimization/03-output-caching-and-response-compression.md): Output Caching middleware terdistribusi, tagging berbasis cache invalidation, dan strategi kompresi data Brotli/Gzip.

### [Bab 09: Observability, Logging, & Production Diagnostics](./09-observability-and-diagnostics/README.md)
Instrumentasi sistem produksi untuk pemantauan proaktif, auditabilitas, dan isolasi insiden secara real-time.
* [01-structured-logging-and-opentelemetry.md](./09-observability-and-diagnostics/01-structured-logging-and-opentelemetry.md): Structured logging performa tinggi dengan LoggerMessage source generation, integrasi Serilog, dan protokol OpenTelemetry (OTLP).
* [02-distributed-tracing-and-metrics.md](./09-observability-and-diagnostics/02-distributed-tracing-and-metrics.md): Standarisasi W3C Trace Context, `ActivitySource`, `Meter`, pembuatan instrumen metrik kustom, dan visualisasi via Prometheus & Grafana.
* [03-dotnet-diagnostics-and-dump-analysis.md](./09-observability-and-diagnostics/03-dotnet-diagnostics-and-dump-analysis.md): Analisis performa produksi menggunakan `dotnet-dump`, `dotnet-trace`, `dotnet-gcdump`, pendeteksian deadlocks, dan thread starvation.

### [Bab 10: Enterprise Architecture & Cloud-Native Deployment](./10-enterprise-architecture-cloud-native/README.md)
Penggabungan seluruh konsep ke dalam blueprint arsitektur berskala besar yang siap dioperasikan di lingkungan cloud modern.
* [01-clean-architecture-cqrs-vertical-slice.md](./10-enterprise-architecture-cloud-native/01-clean-architecture-cqrs-vertical-slice.md): Pemisahan batasan domain (*Domain Boundaries*), segregasi Command/Query via MediatR/Wolverine, dan transisi dari Clean Architecture ke Vertical Slice.
* [02-containerization-and-chiseled-images.md](./10-enterprise-architecture-cloud-native/02-containerization-and-chiseled-images.md): Docker multi-stage build berkinerja tinggi, Ubuntu Chiseled non-root images untuk .NET, dan audit keamanan CVE kontainer.
* [03-kubernetes-orchestration-and-production-readiness.md](./10-enterprise-architecture-cloud-native/03-kubernetes-orchestration-and-production-readiness.md): Manifest deployment Kubernetes, integrasi Probes (Liveness, Readiness, Startup), konfigurasi zero-downtime rolling update, dan mitigasi graceful shutdown.

---

## 4. Enterprise Capstone Project: "NexusTrade"

### Deskripsi Sistem
Sebagai syarat kelulusan akhir kurikulum, peserta wajib membangun sistem riil berskala enterprise: **NexusTrade Core Engine** — platform kliring dan pemukiman (*clearing & settlement*) transaksi finansial multi-tenant dengan volume tinggi (*high-frequency, distributed financial platform*).

Sistem ini mensimulasikan lingkungan bursa pertukaran aset terdesentralisasi/terpusat yang mengeksekusi ribuan transaksi per detik secara konsisten, aman, dan tanpa toleransi kehilangan data (*zero data-loss tolerance*).

```plaintext
                                      NEXUSTRADE ARCHITECTURE
                                     
[ Web Client / Terminal ]    [ External Algorithmic Trading Bots ]
           │                                      │
           ▼                                      ▼
    [ TLS / HTTPS ]                        [ WSS / Binary ]
           │                                      │
           └──────────────────┬───────────────────┘
                              ▼
        ┌───────────────────────────────────────────────┐
        │        Reverse Proxy / Edge Ingress           │
        │             (YARP / Envoy)                    │
        └─────────────────────┬─────────────────────────┘
                              ▼
        ┌───────────────────────────────────────────────┐
        │             NexusTrade API Gateway            │
        │     - Rate Limiting (Fixed/Token Bucket)      │
        │     - JWT / OIDC Authentication Validation    │
        │     - W3C Distributed Trace Injection         │
        └─────────────────────┬─────────────────────────┘
                              │
               Internal Low-Latency Network
                              │
        ┌─────────────────────┴─────────────────────────┐
        │                                               │
        ▼                                               ▼
┌───────────────────────────────┐     ┌───────────────────────────────────┐
│     Trading Order Service     │     │      Market Data Feed Service     │
│   (Vertical Slice + CQRS)     │     │     (High-Throughput SignalR)     │
│                               │     │                                   │
│  - Zero-Allocation Parsers    │     │  - Real-Time L2 Order Book Push   │
│  - FluentValidation Pipeline  │     │  - Redis Backplane Pub/Sub        │
│  - HybridCache (L1/L2)        │     │  - Binary Protocol Serialization  │
└──────────────┬────────────────┘     └─────────────────┬─────────────────┘
               │                                        │
    Event Stream Outbox                                 │
               │                                        │
               ▼                                        │
┌───────────────────────────────┐                       │
│    RabbitMQ Event Broker      │                       │
│  - MassTransit Orchestration  │                       │
│  - High-Concurrency Queues    │                       │
│  - Poison / Dead Letter Queue │                       │
└──────────────┬────────────────┘                       │
               │                                        │
               ▼                                        │
┌───────────────────────────────┐                       │
│   Clearing & Settle Service   │                       │
│   (Event-Driven Consumer)     │                       │
│                               │                       │
│  - Idempotent Consumption     │                       │
│  - Polly Circuit Breaker v8   │                       │
│  - Distributed Lock (Redis)   │                       │
└──────────────┬────────────────┘                       │
               │                                        │
               ▼                                        │
┌───────────────────────────────────────────────┐       │
│               Data Persistence                │       │
│                                               │       │
│  - Write-Side: PostgreSQL (EF Core Relational)│       │
│  - Read-Side: PostgreSQL Views via Dapper     │       │
│  - Distributed Cache: Redis Cluster           │◄──────┘
└───────────────────────────────────────────────┘
```

### Spesifikasi Fungsional & Kebutuhan Teknis

1. **Order Ingestion Engine (Bab 01, 03, 08)**:
   - Endpoint Minimal APIs berbasis Native AOT untuk penerimaan *Limit/Market Order*.
   - Parsing payload transaksi tanpa alokasi memori heap (`ReadOnlySpan<byte>` dan `System.IO.Pipelines`).
   - Pemanfaatan *Rate Limiting Middleware* bawaan .NET dengan algoritma *Token Bucket Partitioned by Tenant/API-Key*.

2. **Core Domain & CQRS Separation (Bab 02, 04, 10)**:
   - Arsitektur berbasis *Vertical Slice* terisolasi.
   - Command Path: Modifikasi saldo akun pedagang (*ledger balances*) dieksekusi melalui Entity Framework Core dengan isolasi transaksi ketat dan *Optimistic Concurrency Control* (`RowVersion`).
   - Query Path: Pengambilan status *order book* dan riwayat mutasi rekening diproses menggunakan Dapper via query SQL yang dioptimasi dengan indeks berulang.

3. **Enterprise Security & Identity (Bab 05)**:
   - Autentikasi terpusat via OIDC/OAuth2 dengan validasi asinkron terhadap klaim sertifikat JWKS publik.
   - Sistem *Resource-Based Authorization* dinamis: Pengguna hanya dapat membatalkan atau mengubah pesanan yang terafiliasi dengan `TenantId` dan `OrganizationUnit` miliknya.
   - Enkripsi field-level sensitif (rekening bank & API Secret) menggunakan `IDataProtectionProvider` dengan kunci yang dirotasi secara otomatis.

4. **Resilience & Fault Tolerance Pipeline (Bab 06)**:
   - Seluruh integrasi eksternal (misal: Gateway Pembayaran FinTech pihak ketiga) dibungkus oleh Polly v8 Resilience Pipeline:
     - Retries: 3x dengan *Exponential Backoff* dan *Full Jitter*.
     - Circuit Breaker: Trip jika tingkat kegagalan mencapai 40% dalam durasi 15 detik; isolasi fallback transaksional.
   - Pengecualian domain dipetakan secara global menggunakan `IExceptionHandler` menjadi dokumen standar RFC 7807 Problem Details tanpa membocorkan infrastruktur internal.

5. **Asynchronous Clearing & Event-Driven Settlement (Bab 07)**:
   - Transaksi order yang terverifikasi diterbitkan (*published*) menggunakan implementasi *Transactional Outbox Pattern* guna menjamin *guaranteed delivery*.
   - MassTransit mengeksekusi konsumsi event secara paralel pada antrean RabbitMQ dengan konsumsi idempoten memanfaatkan persistensi *Message Deduplication Table*.
   - Layanan SignalR Hub menyiarkan pembaruan transaksi *Ticker* pasar secara real-time ke ratusan ribu koneksi menggunakan *Redis Backplane*.

6. **Observability, Profiling, & Cloud Deployment (Bab 09, 10)**:
   - Full instrumentation menggunakan OpenTelemetry SDK: Eksport trace terdistribusi, metric (`orders_processed_total`, `order_execution_latency_ms`), dan log ke OpenTelemetry Collector.
   - Integrasi *Health Checks* berlapis (`/health/live`, `/health/ready`) yang memantau konektivitas database, latensi broker, dan pemakaian memori internal aplikasi.
   - Kontainerisasi multi-stage Docker memanfaatkan base image `mcr.microsoft.com/dotnet/nightly/runtime-deps:chiseled`.
   - File konfigurasi Kubernetes (Deployment, HPA, Service, NetworkPolicy) yang mencakup manajemen sinyal SIGTERM untuk *graceful drain* koneksi HTTP dan WebSocket selama 30 detik.

### Deliverables Proyek
1. **Source Code**: Repositori Git monorepo terstruktur (`/src`, `/tests`, `/deploy`).
2. **Automated Test Suites**:
   - Unit Tests untuk logika matching engine domain.
   - Integration Tests menggunakan `WebApplicationFactory<TProgram>` dan `Testcontainers` (PostgreSQL, Redis, RabbitMQ terisolasi).
   - Load Testing Script (k6) yang membuktikan sistem mampu menangani minimal **5.000 RPS** dengan p99 latency < **25ms**.
3. **Architecture Decision Records (ADR)**: Dokumen penulisan rasionalisasi teknis mengapa memilih model arsitektur tertentu vs alternatif lainnya.
4. **CI/CD Pipeline Definition**: Pipeline otomatis (GitHub Actions) yang mencakup langkah build, static code analysis, pemindaian vulnerabilitas kontainer (Trivy), dan migrasi database terverifikasi.

---
*Mulai pembelajaran dari [Bab 01: .NET Runtime, Hosting, & Request Pipeline Architecture](./01-dotnet-runtime-hosting-internals/README.md).*