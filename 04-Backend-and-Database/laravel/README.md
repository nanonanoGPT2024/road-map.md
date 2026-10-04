# Kurikulum Arsitektur Enterprise: Laravel Framework Engineering

Selamat datang di repositori kurikulum resmi **Laravel Engineering**. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi *software engineer* menjadi *lead backend architect* yang menguasai ekosistem Laravel secara komprehensif, mulai dari pembedahan internal *framework*, optimasi konkurensi tinggi (*high-throughput*), implementasi *clean architecture*, hingga *zero-downtime deployment* berskala *enterprise*.

---

## 1. Course Overview & Mindset

### Mindset Arsitektural
Laravel sering kali disalahpahami hanya sebagai *framework* "Rapid Application Development (RAD)" untuk proyek skala kecil hingga menengah. Kurikulum ini mematahkan paradigma tersebut dengan mendalami Laravel dari perspektif rekayasa perangkat lunak tingkat lanjut:
* **Framework as an Implementation Detail:** Memisahkan *business logic* inti dari *framework delivery mechanism* melalui *Domain-Driven Design (DDD)*, *Hexagonal Architecture*, dan *SOLID principles*.
* **Under-the-Hood Mastery:** Membedah bagaimana `Service Container`, `HTTP Kernel`, dan `Pipeline pattern` bekerja secara mekanis pada runtime PHP, menghindari penggunaan *magic methods* tanpa pemahaman alokasi memori dan siklus eksekusi.
* **Scalability & Resiliency First:** Merancang aplikasi yang toleran terhadap kegagalan (*fault-tolerant*), menguasai teknik pemrosesan asinkron (*distributed queues*), strategi *caching multi-layer*, dan konkurensi tingkat tinggi dengan runtime modern (*FrankenPHP / Laravel Octane*).

### Prasyarat (Prerequisites)
* Pemahaman mendalam mengenai **PHP 8.2+** (Typed Properties, Attributes, Enums, Match Expressions, Fibers).
* Pemahaman kuat mengenai prinsip **Object-Oriented Programming (OOP)**, **Design Patterns**, dan arsitektur basis data relasional.
* Pengalaman dasar menggunakan Git, Composer, dan antarmuka *Command-Line Interface (CLI)*.

---

## 2. Learning Roadmap

```text
====================================================================================================
                        LARAVEL ENTERPRISE ARCHITECTURE ROADMAP
====================================================================================================
[Bab 01: Core Architecture, Request Lifecycle & Service Container]
   |
   +---> [Bab 02: Routing Engine, Middleware Pipeline & HTTP Layer]
            |
            +---> [Bab 03: Deep Dive Eloquent ORM & Advanced Data Modeling]
                     |
                     +---> [Bab 04: Database Architecture, Migrations & Query Optimization]
                              |
                              +---> [Bab 05: Authentication, Authorization & Security Hardening]
                                       |
                                       +---> [Bab 06: Asynchronous Processing, Queues & Distributed Tasks]
                                                |
                                                +---> [Bab 07: Caching Strategy, Real-Time & Event-Driven Architecture]
                                                         |
                                                         +---> [Bab 08: API Engineering, Modern Monolith & Inertia.js]
                                                                  |
                                                                  +---> [Bab 09: Enterprise Testing Strategy & Quality Assurance]
                                                                           |
                                                                           v
                                                       [Bab 10: High Availability, Observability, CI/CD & Deployment]
                                                                           |
                                                                           v
                                                       [ENTERPRISE CAPSTONE PROJECT: OMNIPAY ENGINE]
====================================================================================================
```

---

## 3. Navigasi Detail Modul Kursus

### [Bab 01: Core Architecture, Request Lifecycle & Service Container](./bab-01-arsitektur-dan-lifecycle/README.md)
Mendalami fondasi internal Laravel, memahami urutan bootstrap sistem dari entry-point hingga resolusi dependensi otomatis.
* [Modul 01: Request Lifecycle, Bootstrap Sequence & HTTP Kernel](./bab-01-arsitektur-dan-lifecycle/01-request-lifecycle-kernel.md) — Alur eksekusi dari `public/index.php`, inisialisasi SPI, bootstrapping Providers, hingga pengembalian Response.
* [Modul 02: Deep Dive Service Container & Dependency Injection](./bab-01-arsitektur-dan-lifecycle/02-service-container-dependency-injection.md) — Reflection API, auto-wiring, contextual binding, contextual attributes, dan singleton lifecycle management.
* [Modul 03: Service Providers, Facades Internals & Macroable Pattern](./bab-01-arsitektur-dan-lifecycle/03-service-providers-facades-macros.md) — Perbedaan deferred vs eager loading provider, static proxy facades, dan ekstensi runtime menggunakan `Macroable`.

### [Bab 02: Routing Engine, Middleware Pipeline & HTTP Layer](./bab-02-routing-dan-http-layer/README.md)
Membangun pintu masuk aplikasi yang modular, terlindungi, dan terstruktur dengan memanfaatkan sistem routing mutakhir.
* [Modul 01: Advanced Routing Architecture & Model Binding](./bab-02-routing-dan-http-layer/01-advanced-routing-model-binding.md) — Routing compilation via Symfony Route, regex constraints, implicit/explicit model binding, dan fallback handling.
* [Modul 02: Pipeline Pattern, Terminable Middleware & Context](./bab-02-routing-dan-http-layer/02-pipeline-pattern-terminable-middleware.md) — Desain *onion-layer*, transformasi request/response, middleware terminasi, dan injeksi *scoped context*.
* [Modul 03: Request Validation, Custom Rules & Sanitasi Skema](./bab-02-routing-dan-http-layer/03-request-validation-custom-rules.md) — Form Request lifecycle, validasi kondisional/kompleks, invokable custom rules, dan sanitasi payload.

### [Bab 03: Deep Dive Eloquent ORM & Advanced Data Modeling](./bab-03-deep-dive-eloquent-orm/README.md)
Menguasai Active Record pattern Laravel tanpa mengorbankan performa query dan integritas model domain.
* [Modul 01: Eloquent Internals, Query Builder & Polymorphic Relations](./bab-03-deep-dive-eloquent-orm/01-eloquent-internals-polymorphism.md) — Dekonstruksi Query Builder vs Eloquent Builder, serta relasi polimorfik tingkat lanjut (1-to-many, many-to-many).
* [Modul 02: Hydration Lifecycle, Eager Loading & N+1 Mitigation](./bab-03-deep-dive-eloquent-orm/02-hydration-eager-loading-n-plus-one.md) — Mekanisme model hydration, dynamic eager loading, lazy loading prevention (`preventLazyLoading`), dan subquery selects.
* [Modul 03: Custom Casts, Mutators, Observers & Model Events](./bab-03-deep-dive-eloquent-orm/03-custom-casts-observers-events.md) — Value Objects via Attribute Casts, pemisahan side-effects menggunakan Observers, serta model pruning.

### [Bab 04: Database Architecture, Migrations & Query Optimization](./bab-04-database-architecture-dan-optimization/README.md)
Strategi pengelolaan basis data berskala korporat dengan fokus pada persistensi data, integritas transaksi, dan kecepatan baca/tulis.
* [Modul 01: Zero-Downtime Migrations & Schema Management](./bab-04-database-architecture-dan-optimization/01-zero-downtime-migrations.md) — Strategi migrasi tabel besar (*expand & contract pattern*), *column renaming safety*, dan pemisahan arsitektur migration.
* [Modul 02: Advanced SQL, Window Functions & Index Tuning](./bab-04-database-architecture-dan-optimization/02-advanced-sql-window-functions-indexes.md) — Pemanfaatan CTE, Window Functions via Eloquent, analisis `EXPLAIN`, composite indexes, dan partial indexes.
* [Modul 03: Transaction Isolation, Locking & Read/Write Splitting](./bab-04-database-architecture-dan-optimization/03-transactions-locking-replication.md) — Pessimistic (`sharedLock`/`lockForUpdate`) vs Optimistic locking, penanganan deadlocks, dan konfigurasi master-slave replication.

### [Bab 05: Authentication, Authorization & Security Hardening](./bab-05-auth-dan-security-hardening/README.md)
Mengamankan endpoint dan data sensitif menggunakan standar otentikasi industri serta mitigasi celah keamanan modern.
* [Modul 01: Token-Based vs Session Authentication (Sanctum & Passport)](./bab-05-auth-dan-security-hardening/01-sanctum-passport-token-auth.md) — Stateful SPA authentication via Sanctum, implementasi OAuth2 Server lengkap menggunakan Passport, dan token revocation.
* [Modul 02: Granular Authorization: Gates, Policies & Dynamic RBAC](./bab-05-auth-dan-security-hardening/02-gates-policies-dynamic-rbac.md) — Implementasi Role-Based & Attribute-Based Access Control (RBAC/ABAC), policy discovery, dan otorisasi resource bersarang.
* [Modul 03: Hardening Application Security: OWASP Top 10 Mitigation](./bab-05-auth-dan-security-hardening/03-owasp-mitigation-security-hardening.md) — Mass assignment protection, timing-attack safe comparisons, SQL injection edge cases, XSS mitigation, dan Content Security Policy (CSP).

### [Bab 06: Asynchronous Processing, Queues & Distributed Tasks](./bab-06-asynchronous-processing-dan-queues/README.md)
Membangun arsitektur terdistribusi berbasis antrean yang tangguh untuk menangani *heavy workloads* secara non-blocking.
* [Modul 01: Queue Architecture, Redis Drivers & Job Dispatching](./bab-06-asynchronous-processing-dan-queues/01-queue-architecture-redis-drivers.md) — Struktur data Redis untuk queues, siklus hidup dispatching job, serialized payload, dan delayed execution.
* [Modul 02: Job Batching, Chaining, Rate Limiting & Idempotency](./bab-06-asynchronous-processing-dan-queues/02-job-batching-chaining-idempotency.md) — Workflow paralel via Job Batches, dependensi sekuensial via Chains, distributed job rate-limiting, dan idempotency keys.
* [Modul 03: Laravel Horizon, Worker Scaling & Failure Handling](./bab-06-asynchronous-processing-dan-queues/03-laravel-horizon-worker-scaling.md) — Manajemen supervisor, auto-scaling worker nodes, dead-letter queue (DLQ) retry policies, dan notifikasi kegagalan real-time.

### [Bab 07: Caching Strategy, Real-Time & Event-Driven Architecture](./bab-07-caching-realtime-dan-event-driven/README.md)
Mengakselerasi performa read-intensive application serta membangun komunikasi data dua arah secara real-time.
* [Modul 01: Enterprise Caching Patterns & Distributed Locks](./bab-07-caching-realtime-dan-event-driven/01-caching-patterns-distributed-locks.md) — Cache-aside vs Write-through, Tagged Cache, invalidasi deterministik, dan Redis Atomic Locks untuk mencegah *race condition*.
* [Modul 02: Event-Driven Architecture & Asynchronous Listeners](./bab-07-caching-realtime-dan-event-driven/02-event-driven-architecture-listeners.md) — Domain Events, pemisahan concern dengan queued listeners, subscriber classes, dan event sourcing fundamentals.
* [Modul 03: Real-Time WebSockets via Laravel Reverb](./bab-07-caching-realtime-dan-event-driven/03-realtime-websockets-laravel-reverb.md) — Arsitektur first-party WebSocket server (Laravel Reverb), private & presence channels, client event broadcasting, dan scaling socket nodes.

### [Bab 08: API Engineering, Modern Monolith & Inertia.js](./bab-08-api-engineering-dan-modern-monolith/README.md)
Merancang kontrak antarmuka API enterprise yang kokoh atau menggabungkan keunggulan SPA dengan Monolith.
* [Modul 01: Enterprise RESTful APIs, Transformers & Versioning](./bab-08-api-engineering-dan-modern-monolith/01-restful-api-transformers-versioning.md) — API Resource & Resource Collections, JSON:API standard conformity, filtering/sorting via pipeline, dan skema API versioning.
* [Modul 02: Modern Monolith with Inertia.js & State Management](./bab-08-api-engineering-dan-modern-monolith/02-modern-monolith-inertiajs.md) — Paradigma hybrid SPA-Monolith, sharing data props efisien, partial reloads, deferred props, dan form handling tanpa full-page refresh.
* [Modul 03: API Documentation Automation & Contract-Driven Design](./bab-08-api-engineering-dan-modern-monolith/03-openapi-contract-driven-design.md) — Generasi OpenApi/Swagger spec otomatis melalui static analysis (Scramble/Scribe) dan pengujian berbasis skema kontrak.

### [Bab 09: Enterprise Testing Strategy & Quality Assurance](./bab-09-testing-strategy-dan-qa/README.md)
Menerapkan piramida testing lengkap untuk menjamin stabilitas fungsional, performa, dan integritas arsitektur kode.
* [Modul 01: Modern Unit & Feature Testing with Pest PHP](./bab-09-testing-strategy-dan-qa/01-pest-php-unit-feature-testing.md) — Transisi ke Pest PHP, pengujian fungsionalitas murni, mocking external dependencies menggunakan Mockery, dan test doubles.
* [Modul 02: Integration, Database & HTTP Component Testing](./bab-09-testing-strategy-dan-qa/02-integration-database-http-testing.md) — Database transactions isolation, model factories, testing state changes, dan assertions kompleks pada HTTP endpoints.
* [Modul 03: Architecture Testing, Static Analysis & Mutation Testing](./bab-09-testing-strategy-dan-qa/03-arch-testing-static-analysis-mutation.md) — Pest Architecture Rules (menegakkan batasan layer DDD), PHPStan (Level 8+ / Larastan), dan Mutation Testing menggunakan Infection PHP.

### [Bab 10: High Availability, Observability, CI/CD & Deployment](./bab-10-ha-observability-dan-deployment/README.md)
Mempersiapkan infrastruktur runtime produksi berkinerja tinggi, terpantau secara telemetrik, dan dideploy secara kontinu.
* [Modul 01: High-Performance Runtime: Laravel Octane & FrankenPHP](./bab-10-ha-observability-dan-deployment/01-laravel-octane-frankenphp.md) — Mengatasi state-leaks dalam long-running processes, integrasi FrankenPHP/Swoole, concurrent tasks via Octane, dan memory profiling.
* [Modul 02: Observability: Structured Logging, Pulse & OpenTelemetry](./bab-10-ha-observability-dan-deployment/02-observability-pulse-opentelemetry.md) — Application monitoring dengan Laravel Pulse, distributed tracing via OpenTelemetry, Contextual logging, dan error tracking via Sentry.
* [Modul 03: Production Multi-Stage Docker & Zero-Downtime CI/CD](./bab-10-ha-observability-dan-deployment/03-docker-production-zero-downtime-cicd.md) — Optimasi Dockerfile multi-stage untuk PHP-FPM/Octane, asset build caching, pipeline GitHub Actions, dan rolling deployment via Deployer/Envoyer.

---

## 4. Enterprise Capstone Project: OmniPay Engine

Sebagai syarat kelulusan kurikulum ini, peserta wajib mengimplementasikan **OmniPay Engine**, sebuah *Core Payment Gateway & Settlement Reconciliation Platform* berbasis *multi-tenant* yang mampu memproses jutaan transaksi per hari dengan konsistensi data finansial yang mutlak.

```text
+-------------------------------------------------------------------------------------------------------+
|                                    OMNIPAY ENGINE ARCHITECTURE                                        |
+-------------------------------------------------------------------------------------------------------+
                                                     |
                                            [ Cloudflare / WAF ]
                                                     |
                                        [ NGINX / FrankenPHP Ingress ]
                                                     |
                     +-------------------------------+-------------------------------+
                     |                                                               |
           [ Synchronous API Layer ]                                      [ Asynchronous Workers ]
         (Laravel Octane - FrankenPHP)                                   (Horizon Worker Pool / Redis)
                     |                                                               |
      +--------------+--------------+                                +---------------+---------------+
      |                             |                                |                               |
[Sanctum Auth]               [Idempotency &]                  [Webhook Ingestion]             [Reconciliation]
[Rate Limiter]               [Request Valid]                  [Double-Entry Ledger]           [Settlement Job]
      |                             |                                |                               |
      +--------------+--------------+                                +---------------+---------------+
                     |                                                               |
                     +-------------------------------+-------------------------------+
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
                [ PostgreSQL 16+ ]                                       [ Redis Cluster ]
             (Master-Replica Routing)                                  (Cache, Locks, Queues)
                         |                                                       |
         +---------------+---------------+                                       |
         |                               |                                       |
  [Tenant Data DB]              [Financial Ledger]                    [Pulse & Tracing Metrics]
   (Row-Level RLS)              (ACID Serializable)                  (OpenTelemetry Collector)
```

### Spesifikasi Teknis & Fungsional Capstone

#### 1. Arsitektur Domain Core
* **Multi-Tenancy:** Pendekatan *single-database with scoped row-level security* atau *database-per-tenant*, terisolasi secara transparan via *Global Scopes* dan *Tenant Resolution Middleware*.
* **Double-Entry Bookkeeping Ledger:** Sistem pencatatan keuangan yang immutable (tidak boleh ada update atau delete fisik pada tabel buku besar). Setiap transaksi memiliki entri debit dan kredit yang seimbang secara matematis dalam satu *atomic database transaction*.
* **Idempotent Webhook Processing:** Memproses notifikasi pembayaran pihak ketiga menggunakan *Idempotency Keys* dengan *atomic locks* di Redis, mencegah *double-crediting* akibat duplikasi pengiriman webhook.

#### 2. Kinerja & Keandalan (Non-Functional Requirements)
* **High-Throughput Runtime:** Diuji menggunakan *k6* atau *wrk* untuk mencapai minimal **1.500+ requests/sec** pada *stateless checkout endpoint* dengan latency p99 < 80ms menggunakan **Laravel Octane (FrankenPHP)**.
* **Fault Tolerance:** Mengimplementasikan *Circuit Breaker pattern* ketika melakukan panggilan API keluar ke bank/partner, didukung mekanisme antrean berbasis prioritas (*Priority Queues*) dan *Dead Letter Queue* monitoring via **Laravel Horizon**.
* **Audit Trail & Observability:** Seluruh event finansial harus memicu *Domain Event* yang tercatat secara asinkron ke storage audit log, terintegrasi dengan **Structured Contextual Logging** dan metrik **Laravel Pulse**.

#### 3. Standar Kualitas Kode (Quality Gates)
* **Coverage Testing:** Minimal **85% code coverage** menggunakan **Pest PHP** mencakup Unit, Integration, dan Feature tests (khusus modul settlement dan buku besar finansial wajib 100% test coverage).
* **Static Analysis:** Harus lolos **PHPStan level 8** (atau *Larastan max level*) tanpa mengabaikan *baseline error* (`treatPhpDocTypesAsCertain: true`).
* **Architecture Compliance:** Lolos pengujian struktur arsitektur menggunakan **Pest Arch**, memastikan domain model tidak bocor ke luar layer, dan kontroler tidak memanggil Query Builder secara langsung.

---

## 5. Standar Kontribusi & Panduan Memulai
1. Fork repositori ini dan pastikan lingkungan lokal Anda memenuhi spesifikasi: **PHP >= 8.2**, **Composer >= 2.6**, **Docker & Docker Compose**, serta **Node.js >= 20.x**.
2. Masuk ke masing-masing direktori modul (misal: `bab-01-arsitektur-dan-lifecycle/`) untuk membaca materi konseptual, diagram detail, serta menyelesaikan tugas lab teknis yang tersedia.
3. Seluruh submission tugas dan Capstone Project harus diserahkan dalam bentuk *Pull Request* yang telah melewati pemeriksaan *GitHub Actions pipeline* (Linter, PHPStan, Pest Testing).