# Enterprise Ruby on Rails: Architecture, Scalability, and Systems Design

Selamat datang di kurikulum definitif **Enterprise Ruby on Rails**. Repositori ini dirancang khusus untuk mentransformasi Software Engineer tingkat menengah menjadi **Principal Rails Architect** yang mampu merancang, membangun, mengoptimalkan, dan mengoperasikan aplikasi berskala masif (*hyper-growth*) dengan performa tinggi dan keandalan tingkat enterprise.

---

## 1. Course Overview & Mindset

### Filosofi & Doktrin Rails
Ruby on Rails dibangun di atas filosofi *The Rails Doctrine*:
- **Optimize for Programmer Happiness:** Menghilangkan friksi kognitif melalui sintaks Ruby yang ekspresif.
- **Convention over Configuration (CoC):** Mengurangi *boilerplate* dan keputusan trivial dengan konvensi baku, membebaskan fokus rekayasa untuk logika domain bernilai tinggi.
- **The Menu is Omakase:** Rails menyediakan ekosistem terpadu (*curated stack*) yang matang, namun tetap memungkinkan kustomisasi komponen tingkat lanjut.
- **The Majestic Monolith:** Menolak kompleksitas prematur dari arsitektur *microservices*. Kita membangun arsitektur modular monolitik berbasis *engines* dan *bounded contexts* sebelum memecah sistem saat batas organisasi menuntutnya.

### Paradigma Rekayasa Enterprise
Menulis kode Rails pada level enterprise bukan sekadar memanfaatkan *scaffolding*. Kurikulum ini menekankan:
1. **Zero-Magic Understanding:** Memahami secara mendalam cara kerja internal Ruby (object model, metaprogramming, GC, fiber/thread runtime) dan siklus internal Rack/Rails Engine.
2. **Database-First Mentality:** *Active Record* adalah *abstraction layer*, bukan pengganti pemahaman relasional. Optimasi query, indexing, transaction isolation, deadlocks, dan connection pooling adalah prioritas.
3. **Decoupled Architecture:** Menghindari *Fat Model, Skinny Controller* yang berantakan dengan menerapkan Service Objects, Form Objects, Query Objects, Policy Objects, dan Event-Driven Architecture.
4. **Resilience & Fault Tolerance:** Desain sistem asinkron yang *idempotent*, implementasi *circuit breaker*, *exponential backoff*, serta monitoring real-time berbasis observabilitas modern.

---

## 2. Learning Roadmap

```text
Ruby on Rails Enterprise Roadmap
│
├── [Bab 01] Fondasi Ruby Lanjutan & Anatomi Rails Engine
│   ├── 01-ruby-internals-object-model.md
│   ├── 02-rack-architecture-middleware-pipeline.md
│   └── 03-rails-boot-process-engine-internals.md
│
├── [Bab 02] Routing Lanjutan & Controller Architecture
│   ├── 01-advanced-routing-constraints.md
│   ├── 02-controllers-strong-parameters-filters.md
│   └── 03-api-mode-versioning-serialization.md
│
├── [Bab 03] Data Modeling & Active Record Mastery
│   ├── 01-migrations-arel-advanced-querying.md
│   ├── 02-associations-deep-dive-optimizations.md
│   └── 03-callbacks-validation-lifecycle-anti-patterns.md
│
├── [Bab 04] Modern View Layer, Hotwire & ViewComponents
│   ├── 01-viewcomponent-isolated-ui-architecture.md
│   ├── 02-hotwire-turbo-drive-frames-streams.md
│   └── 03-stimulus-js-reactive-state-management.md
│
├── [Bab 05] Asynchronous Processing & Background Jobs
│   ├── 01-active-job-adapter-internals.md
│   ├── 02-high-throughput-workers-sidekiq-solid-queue.md
│   └── 03-idempotency-transactional-outbox-pattern.md
│
├── [Bab 06] Real-Time Streaming & WebSocket Architecture
│   ├── 01-action-cable-internals-pub-sub.md
│   ├── 02-solid-cable-alternative-transports.md
│   └── 03-broadcast-security-performance-tuning.md
│
├── [Bab 07] Enterprise Security, Authentication & Multi-Tenancy
│   ├── 01-authentication-mechanisms-session-jwt-rodauth.md
│   ├── 02-fine-grained-authorization-pundit-action-policy.md
│   └── 03-multi-tenancy-apartment-row-level-security.md
│
├── [Bab 08] Automated Testing & Quality Engineering
│   ├── 01-rspec-best-practices-test-pyramid.md
│   ├── 02-integration-system-testing-cuprite-capybara.md
│   └── 03-benchmarking-mutation-testing-profiling.md
│
├── [Bab 09] Performance Optimization, Caching & Observability
│   ├── 01-caching-strategies-russian-doll-solid-cache.md
│   ├── 02-database-optimization-n-plus-one-sharding.md
│   └── 03-open-telemetry-apm-distributed-tracing.md
│
└── [Bab 10] Containerization, Kamal Deployment & SRE
    ├── 01-production-dockerization-asset-pipeline.md
    ├── 02-zero-downtime-deployment-kamal-traefik.md
    └── 03-high-availability-horizontal-scaling-dr.md
```

---

## 3. Navigasi Detail Silabus

### [Bab 01: Fondasi Ruby Lanjutan & Anatomi Rails Engine](./01-fondasi-ruby-lanjutan-dan-anatomi-rails-engine/)
Mempelajari arsitektur internal Ruby, alokasi memori, runtime, serta bagaimana Rails mengabstraksi dan mengeksekusi request melalui antarmuka Rack.
- **[Modul 1: Ruby Internals & Object Model](./01-fondasi-ruby-lanjutan-dan-anatomi-rails-engine/01-ruby-internals-object-model.md)** – Singleton classes, Metaprogramming yang aman, Garbage Collection profiling, dan implementasi Fiber Scheduler.
- **[Modul 2: Rack Architecture & Middleware Pipeline](./01-fondasi-ruby-lanjutan-dan-anatomi-rails-engine/02-rack-architecture-middleware-pipeline.md)** – Spesifikasi Rack, modifikasi middleware pipeline, pembuatan kustom middleware performa tinggi.
- **[Modul 3: Rails Boot Process & Engine Internals](./01-fondasi-ruby-lanjutan-dan-anatomi-rails-engine/03-rails-boot-process-engine-internals.md)** – `config.ru`, Railties, Zeitwerk autoloading system, dan arsitektur `Rails::Engine` modular.

### [Bab 02: Routing Lanjutan & Controller Architecture](./02-routing-lanjutan-dan-controller-architecture/)
Membangun kontroler stateless yang efisien dan mendesain RESTful API maupun Hybrid Web Applications yang tangguh.
- **[Modul 1: Advanced Routing & Dynamic Constraints](./02-routing-lanjutan-dan-controller-architecture/01-advanced-routing-constraints.md)** – Custom constraint classes, sub-domain routing, route scoping, dan optimasi compilation tree router.
- **[Modul 2: Controllers, Strong Parameters & Action Lifecycle](./02-routing-lanjutan-dan-controller-architecture/02-controllers-strong-parameters-filters.md)** – Exception handling terpusat, idempotency keys handling, parameter sanitization mendalam, dan response responders.
- **[Modul 3: API-Only Architecture & High-Speed Serialization](./02-routing-lanjutan-dan-controller-architecture/03-api-mode-versioning-serialization.md)** – Versioning patterns, Alba/Blueprinter serialisasi cepat vs ActiveModel::Serializers, rate limiting dengan Rack::Attack.

### [Bab 03: Data Modeling & Active Record Mastery](./03-data-modeling-dan-active-record-mastery/)
Mendominasi Active Record untuk throughput tinggi, query kompleks, dan manipulasi data berintegritas tanpa kebocoran logika.
- **[Modul 1: Migrations, Arel & Advanced Query Construction](./03-data-modeling-dan-active-record-mastery/01-migrations-arel-advanced-querying.md)** – Zero-downtime database migrations, recursive CTEs dengan Arel, Window Functions, dan subquery optimization.
- **[Modul 2: Associations Deep Dive & Performance Patterns](./03-data-modeling-dan-active-record-mastery/02-associations-deep-dive-optimizations.md)** – Polymorphic joins, Counter Caches, Preloading vs Eager Loading vs Inlining, dan Batch processing (`find_each` vs `in_batches`).
- **[Modul 3: Callbacks Lifecycle & Domain-Driven Decoupling](./03-data-modeling-dan-active-record-mastery/03-callbacks-validation-lifecycle-anti-patterns.md)** – Callback anti-patterns, Transaction rollback handling, decoupling via Service Objects, Form Objects, dan Trailblazer/dry-rb.

### [Bab 04: Modern View Layer, Hotwire & ViewComponents](./04-modern-view-layer-hotwire-dan-viewcomponents/)
Membangun antarmuka modern yang reaktif tanpa Single Page Application (SPA) bloat, mengutamakan performa rendering server.
- **[Modul 1: Isolated UI Architecture dengan ViewComponent](./04-modern-view-layer-hotwire-dan-viewcomponents/01-viewcomponent-isolated-ui-architecture.md)** – Desain komponen modular terenkapsulasi, isolated testing, slots pattern, dan performance profiling view layer.
- **[Modul 2: Hotwire Deep Dive: Turbo Drive, Frames & Streams](./04-modern-view-layer-hotwire-dan-viewcomponents/02-hotwire-turbo-drive-frames-streams.md)** – DOM replacement over-the-wire, frame targeting, lazy loading, multi-stream morphing berbasis Rails 8/Turbo 8.
- **[Modul 3: Stimulus.js & Client-Side State Management](./04-modern-view-layer-hotwire-dan-viewcomponents/03-stimulus-js-reactive-state-management.md)** – Lifecycle callbacks, target/value controllers, integrasi dengan library browser eksternal, dan decoupled UI actions.

### [Bab 05: Asynchronous Processing & Background Jobs](./05-asynchronous-processing-dan-background-jobs/)
Menghandle beban komputasi masif dan integrasi pihak ketiga secara andal menggunakan arsitektur job terdistribusi.
- **[Modul 1: ActiveJob Internals & Queue Adapters](./05-asynchronous-processing-dan-background-jobs/01-active-job-adapter-internals.md)** – Serialization arguments, globalID mechanics, priority scheduling, dan error handling orchestration.
- **[Modul 2: High-Throughput Processing: Sidekiq Enterprise & Solid Queue](./05-asynchronous-processing-dan-background-jobs/02-high-throughput-workers-sidekiq-solid-queue.md)** – Redis lock contention, multithreading memory management (Jemalloc), database-backed queues via Solid Queue.
- **[Modul 3: Idempotency, Concurrency Control & Transactional Outbox](./05-asynchronous-processing-dan-background-jobs/03-idempotency-transactional-outbox-pattern.md)** – Mengatasi duplicated jobs, race conditions, Distributed Locks (Redlock), dan implementasi Transactional Outbox Pattern.

### [Bab 06: Real-Time Streaming & WebSocket Architecture](./06-real-time-streaming-dan-websocket-architecture/)
Membangun kapabilitas kolaboratif real-time berlatensi rendah dengan skalabilitas concurrent connection yang tinggi.
- **[Modul 1: ActionCable Engine Architecture & Pub/Sub](./06-real-time-streaming-dan-websocket-architecture/01-action-cable-internals-pub-sub.md)** – Connection lifecycle, Channels, Streams, subscription security, dan backend adapter Redis vs PostgreSQL.
- **[Modul 2: Solid Cable, AnyCable & Go/Erlang Offloading](./06-real-time-streaming-dan-websocket-architecture/02-solid-cable-alternative-transports.md)** – Mengurangi penggunaan memori Ruby menggunakan Solid Cable dan implementasi AnyCable berbasis Go/RPC untuk jutaan koneksi.
- **[Modul 3: Broadcast Security & High-Frequency Streaming Optimization](./06-real-time-streaming-dan-websocket-architecture/03-broadcast-security-performance-tuning.md)** – Data payload sanitization, debouncing/throttling updates, presence channels, dan client reconnection storms.

### [Bab 07: Enterprise Security, Authentication & Multi-Tenancy](./07-enterprise-security-authentication-dan-multi-tenancy/)
Mengamankan aplikasi Rails dari kerentanan web modern dan merancang isolasi data multitenan yang ketat.
- **[Modul 1: Authentication Architecture: Native Rails 8 vs Rodauth vs Devise](./07-enterprise-security-authentication-dan-multi-tenancy/01-authentication-mechanisms-session-jwt-rodauth.md)** – Password hashing (Argon2), MFA, Passkeys/WebAuthn, Session hijacking prevention, dan stateless API Auth.
- **[Modul 2: Fine-Grained Authorization dengan Action Policy & Pundit](./07-enterprise-security-authentication-dan-multi-tenancy/02-fine-grained-authorization-pundit-action-policy.md)** – Policy scoping, headless policies, performa tinggi pre-authorization caching, dan Role-Based/Attribute-Based Access Control.
- **[Modul 3: Multi-Tenancy Patterns: Database Schemas vs Row-Level Security](./07-enterprise-security-authentication-dan-multi-tenancy/03-multi-tenancy-apartment-row-level-security.md)** – PostgreSQL schemas isolation, PostgreSQL Row-Level Security (RLS) terintegrasi Active Record, query scoping leak prevention.

### [Bab 08: Automated Testing & Quality Engineering](./08-automated-testing-dan-quality-engineering/)
Membangun test suite yang komprehensif, paralel, deterministik, dan cepat untuk siklus rilis berkelanjutan (CI/CD).
- **[Modul 1: RSpec Mastery & The Enterprise Testing Pyramid](./08-automated-testing-dan-quality-engineering/01-rspec-best-practices-test-pyramid.md)** – Custom matchers, metadata filtering, FactoryBot optimization, avoiding database hits, mocks and stubs safely.
- **[Modul 2: System Tests & Headless Browser Automation](./08-automated-testing-dan-quality-engineering/02-integration-system-testing-cuprite-capybara.md)** – Cuprite (Chrome CDP) vs Selenium, async assertion patterns, file upload testing, snapshot/visual regression tests.
- **[Modul 3: Mutation Testing, Benchmarking & Memory Profiling](./08-automated-testing-dan-quality-engineering/03-benchmarking-mutation-testing-profiling.md)** – Mutant framework integration, `benchmark-ips`, memory leak detection dengan `derailed_benchmarks` dan `memory_profiler`.

### [Bab 09: Performance Optimization, Caching & Observability](./09-performance-optimization-caching-dan-observability/)
Memaksimalkan throughput, memangkas latensi p99, dan menerapkan instrumentasi observabilitas menyeluruh.
- **[Modul 1: Advanced Caching: Russian Doll, Key-Based & Solid Cache](./09-performance-optimization-caching-dan-observability/01-caching-strategies-russian-doll-solid-cache.md)** – Cache digests, Fragment caching, Low-level cache design, Disk-backed Solid Cache optimization, cache stampede prevention.
- **[Modul 2: Database Scalability, N+1 Detection & Sharding](./09-performance-optimization-caching-dan-observability/02-database-optimization-n-plus-one-sharding.md)** – Prosopite vs Bullet, database connection pool tuning, Read/Write replica splitting, horizontal sharding via ActiveRecord Multi-DB.
- **[Modul 3: OpenTelemetry, Distributed Tracing & APM](./09-performance-optimization-caching-dan-observability/03-open-telemetry-apm-distributed-tracing.md)** – Instrumentasi manual/otomatis Active Support notifications, integrasi OTel collector, trace propagation, structured logging.

### [Bab 10: Containerization, Kamal Deployment & SRE](./10-containerization-kamal-deployment-dan-sre/)
Menjalankan dan mengelola aplikasi Rails di lingkungan infrastruktur modern dengan kesiapan operasional penuh.
- **[Modul 1: Enterprise Docker Packaging & Asset Pipeline Mastery](./10-containerization-kamal-deployment-dan-sre/01-production-dockerization-asset-pipeline.md)** – Multi-stage production Dockerfile, optimasi Jemalloc, Propshaft vs Sprockets, asset precompilation tanpa live database.
- **[Modul 2: Zero-Downtime Deployments dengan Kamal & Traefik](./10-containerization-kamal-deployment-dan-sre/02-zero-downtime-deployment-kamal-traefik.md)** – Kamal orchestration, Traefik edge proxying, blue-green deployment strategy, automated rolling releases, secret management.
- **[Modul 3: High Availability, Horizontal Auto-Scaling & Disaster Recovery](./10-containerization-kamal-deployment-dan-sre/03-high-availability-horizontal-scaling-dr.md)** – Puma thread/worker concurrency tuning, graceful shutdowns, automated failover, health checks, backup snapshot validations.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title: **"FinPulse Engine" — High-Throughput Real-Time FinTech Ledger & Payment Orchestration Platform**

### Ringkasan Eksekutif
FinPulse Engine adalah platform transaksi keuangan berbasis monolit modular (*modular monolith*) yang menangani ribuan transaksi per detik (*TPS*), menyediakan buku besar (*immutable double-entry ledger*), serta menyajikan pelaporan dan *reconciliation* instan melalui streaming UI secara real-time.

### Persyaratan Arsitektural & Fungsional
1. **Double-Entry General Ledger Core:**
   - Pencatatan transaksi mutlak *immutable* (tidak ada `UPDATE` atau `DELETE` pada baris ledger).
   - Penggunaan PostgreSQL Row-Level Locking (`FOR UPDATE`) dan transaction isolation level serializable untuk mencegah *double-spending*.
   - Idempotency layer menggunakan Redis Distributed Lock dan ID unik per request.
2. **Modular Rails Engines:**
   - Membagi domain ke dalam Isolated Rails Engines:
     - `LedgerCore::Engine` (Manajemen akun, debit, kredit, saldo).
     - `PaymentGateways::Engine` (Integrasi eksternal pihak ketiga dengan Circuit Breaker).
     - `AnalyticsReporting::Engine` (Agregasi metrik dan audit).
3. **High-Throughput Asynchronous Pipeline:**
   - Memproses batch payout menggunakan Solid Queue / Sidekiq Enterprise dengan mekanisme rate limiting pihak ketiga.
   - Implementasi Transactional Outbox Pattern untuk menjamin pengiriman webhook tanpa data inkonsistensi.
4. **Real-Time Hotwire & Cable Dashboard:**
   - Dashboard Admin tanpa JavaScript heavy-framework: menggunakan Turbo Streams morphing dan ViewComponent untuk merefleksikan perubahan status transaksi, volume agregat, dan anomali fraud secara live.
5. **Keamanan & Kepatuhan Finansial:**
   - Enkripsi data sensitif at-rest via `ActiveRecord::Encryption`.
   - Audit trail tak terelakkan (*tamper-proof audit logs*) yang mencatat setiap aksi administratif.
   - Fine-grained RBAC menggunakan `Action Policy` dengan kustom scoping rule.
6. **Infrastruktur & Penyebaran Produksi:**
   - Multi-container architecture (Web, Worker, Cable, Redis, Postgres Primary, Postgres Replica).
   - Orkestrasi deployment *zero-downtime* ke dedicated server menggunakan **Kamal**.
   - Tracing end-to-end terintegrasi dengan OpenTelemetry.

### Kriteria Kelulusan Teknis
- **Test Coverage:** Minimal 90% dengan RSpec (Unit, Request, System, dan Concurrency Tests).
- **Performance Threshold:** Latensi p95 API < 80ms di bawah beban 1,000 RPS.
- **Fault-Tolerance Verification:** Sistem harus lulus uji *Chaos Engineering* (mematikan instance background worker dan database primary-replica failover tanpa data loss).

---
*Mulai langkah pertama Anda menuju penguasaan Rails enterprise pada [Bab 01: Fondasi Ruby Lanjutan & Anatomi Rails Engine](./01-fondasi-ruby-lanjutan-dan-anatomi-rails-engine/).*