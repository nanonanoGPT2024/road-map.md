# BAB 10: Quiz, Challenge, & Knowledge Check
**Enterprise Architecture & Cloud-Native Deployment**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Clean Architecture & Dependency Inversion Principle (DIP)**  
   Jelaskan secara struktural mengapa *Domain Layer* dan *Application Layer* (Core) di dalam Clean Architecture sama sekali tidak boleh memiliki dependensi terhadap *Infrastructure Layer* (seperti Entity Framework Core atau SDK Third-Party). Bagaimana mekanisme *Dependency Inversion Principle* (DIP) dan *Interface Segregation* di ASP.NET Core memungkinkan domain logic tetap murni (*agnostic*) namun tetap dapat mengeksekusi persistensi database dan pemanggilan API eksternal?

2. **Kubernetes Pod Lifecycle & ASP.NET Core Graceful Shutdown**  
   Ketika Kubernetes mengirimkan sinyal `SIGTERM` ke pod ASP.NET Core Anda saat proses *rolling update*, uraikan siklus hidup shutdown internal runtime .NET (`IHostApplicationLifetime`). Mengapa konfigurasi `preStop hook` (sleep) di Kubernetes sering kali mutlak diperlukan sebelum Kestrel berhenti menerima traffic baru, dan apa konsekuensinya jika aplikasi langsung mematikan socket listener tanpa jeda tersebut?

3. **Triage Kubernetes Probes: Liveness, Readiness, dan Startup**  
   Bedakan tujuan arsitektural dan implikasi kegagalan dari *Startup Probe*, *Liveness Probe*, dan *Readiness Probe* pada pod ASP.NET Core. Mengapa mengekspos pemeriksaan konektivitas database SQL Server downstream secara langsung di dalam endpoint *Liveness Probe* merupakan *anti-pattern* fatal yang dapat memicu *cascading failure* di seluruh cluster?

4. **12-Factor App & Dynamic Configuration Architecture**  
   Dalam paradigma cloud-native (12-Factor App: Config), mengapa menyimpan file konfigurasi spesifik-environment (seperti `appsettings.Production.json`) di dalam image container dianggap sebagai pelanggaran prinsip *immutability*? Bagaimana sistem konfigurasi bertingkat (*hierarchical configuration provider*) di ASP.NET Core mengeksekusi resolusi nilai dari Environment Variables, Kubernetes ConfigMap/Secrets, dan Secret Management eksternal (misal: Azure Key Vault / HashiCorp Vault)?

5. **Observability Triad: OpenTelemetry Integration**  
   Jelaskan peran masing-masing pilar observabilitas: **Distributed Tracing** (`ActivitySource` / W3C `traceparent`), **Metrics** (`System.Diagnostics.Metrics.Meter`), dan **Structured Logging** (Semantic Logging). Bagaimana ASP.NET Core memanfaatkan standarisasi OpenTelemetry (OTel) untuk mengkorelasikan log internal Kestrel, query EF Core, dan HTTP call downstream ke dalam satu trace ID yang identik secara end-to-end?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Thread Pool Starvation vs. Connection Pool Exhaustion under Microservice Load**  
   Sebuah microservice ASP.NET Core mengalami lonjakan p99 latency dari 50ms menjadi 15 detik saat traffic naik, disertai pelepasan status pod menjadi *unready*. Setelah dianalisis menggunakan `dotnet-dump` dan `dotnet-counters`, metrik menunjukkan `ThreadPool.ThreadCount` melonjak tajam mendekati batas starvation, sementara utilisasi CPU hanya 25%.  
   *Pertanyaan:* Analisis akar penyebab internal runtime ini. Mengapa pemanggilan downstream API menggunakan synchronous blocking (misal: `.Result` atau `.Wait()`) atau kesalahan registrasi siklus hidup `HttpClient` via `IHttpClientFactory` dapat melumpuhkan *ThreadPool worker threads*, dan bagaimana runtime .NET mengalokasikan thread baru (skema 1 thread per ~500ms)?

2. **Dual-Write Hazard & The Transactional Outbox Pattern**  
   Diberikan skenario bisnis: sebuah handler *Command* di Application Layer harus mengupdate saldo akun di PostgreSQL via EF Core dan mempublikasikan event `OrderPlacedIntegrationEvent` ke RabbitMQ/Apache Kafka.  
   *Pertanyaan:* Mengapa eksekusi `await dbContext.SaveChangesAsync()` yang diikuti langsung oleh `await messageBus.PublishAsync()` rentan terhadap kegagalan konsistensi data (*partial failure*) tanpa Two-Phase Commit (2PC)? Rancang alur internal dari **Transactional Outbox Pattern** menggunakan EF Core transaction boundary, interceptor, dan background worker polling/CDC (Change Data Capture) untuk menjamin garansi *at-least-once delivery*.

3. **Container Resource Allocation & .NET Garbage Collector Tuning (cgroups v1 vs v2)**  
   Pada platform Kubernetes, sebuah pod .NET Core sering mengalami *OOMKilled* (Exit Code 137) meskipun alokasi memory limit pod ditetapkan sebesar 2 GiB.  
   *Pertanyaan:* Bagaimana mekanisme internal .NET Server GC berinteraksi dengan batasan memori container cgroups? Apa perbedaan mendasar antara alokasi Server GC vs. Workstation GC pada container dengan limitasi CPU kecil (< 2 core), dan bagaimana variabel environment `DOTNET_GCHeapHardLimitPercent` atau `DOTNET_TotalMemoryLimit` mencegah runtime .NET mengonsumsi memori melampaui limit cgroups sebelum GC cycle dipicu?

4. **Resilience Engineering: Polly v8 Cascading Failures & Retry Storms**  
   Anda mengonfigurasi `Polly` resilience pipeline v8 pada downstream HTTP client dengan strategi *Retry* 5 kali secara agresif tanpa *Jitter* dan tanpa *Circuit Breaker*. Ketika service target downstream mengalami penurunan kapasitas (*degraded state*), traffic ke service tersebut justru meledak 5x lipat dan menumbangkan seluruh cluster.  
   *Pertanyaan:* Jelaskan mekanisme dinamika sistem di balik fenomena **Retry Storm / Thundering Herd** ini. Bagaimana integrasi *Circuit Breaker State Machine* (Closed, Open, Half-Open) bersama *Exponential Backoff with Full Jitter* memitigasi bencana kolapsnya dependensi downstream?

5. **Diagnostic Memory Leak & Lost Context in Asynchronous Background Tasks**  
   Dalam sebuah microservice pemrosesan transaksi yang berjalan pada `BackgroundService` (`IHostedService`), terdeteksi kebocoran memori (*memory leak*) progresif dan hilangnya korelasi `CorrelationId` pada log aplikasi.  
   *Pertanyaan:* Mengapa menginjeksi dependency dengan *Scoped Lifetime* (seperti EF Core `DbContext`) secara langsung ke dalam konstruktor singleton `BackgroundService` dilarang oleh service provider ASP.NET Core, dan bagaimana mekanisme pembentukan explicit scope (`IServiceScopeFactory.CreateScope()`) menyelesaikan masalah ini? Mengapa `AsyncLocal<T>` kehilangan context trace-nya jika developer menggunakan `ThreadPool.QueueUserWorkItem` tanpa *ExecutionContext capture*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Failure Akibat Downstream Degradation Saat Event Penjualan Skala Besar
Pada saat flash sale nasional, traffic ke service *Checkout* berbasis ASP.NET Core melonjak hingga 45.000 RPS. Service *Checkout* bergantung pada *Third-party Fraud Detection Service* eksternal yang diakses via HTTPS. Tiba-tiba, p95 latency dari Fraud Detection Service melonjak dari 80ms menjadi 6.000ms.  
Dalam 30 detik:
- Kestrel threadpool habis terpakai untuk menahan request yang terhambat.
- Memory consumption melonjak karena akumulasi buffer HTTP request.
- Endpoint `/healthz/ready` ASP.NET Core tidak lagi merespons sebelum batas timeout 2 detik Kubernetes.
- Kubelet menganggap pod tidak sehat dan mencabut pod dari Endpoints routing Service.
- Seluruh sisa pod yang hidup menerima limpahan traffic sisa, menyebabkan *domino-effect collapse* di seluruh cluster.

**Pertanyaan Diagnostik:**
1. Desainlah arsitektur mitigasi menggunakan Polly v8 Resilience Pipeline yang harus diimplementasikan pada `HttpClient` service Checkout tersebut (tentukan parameter *Timeout*, *Circuit Breaker*, *Rate Limiter*, dan *Fallback*).
2. Bagaimana isolasi health check endpoint harus direfaktor agar saturasi dependency eksternal tidak membuat Kubernetes membunuh pod yang sebenarnya masih sanggup memproses fungsionalitas checkout non-fraud (atau fallback checkout)?

---

### Skenario B: Race Condition dan Double Financial Processing Akibat Jaringan Asinkron
Dalam arsitektur *Decoupled Payment Processing*, service *Payment* menerima event `ProcessPaymentCommand` dari message broker. Karena lonjakan beban dan jitter jaringan, message broker melakukan *redelivery* event yang sama selang 200ms. Dua consumer thread yang berbeda pada dua instance pod ASP.NET Core memproses command transaksi dengan `OrderId: "ORD-99881"` secara hampir bersamaan.  
Kedua instance membaca status `Orders` dari database: keduanya melihat status `PENDING`, keduanya memotong balance user via integrasi Core Banking API, dan keduanya mengupdate status database menjadi `SUCCESS`. Saldo nasabah terpotong ganda untuk pesanan yang sama.

**Pertanyaan Diagnostik:**
1. Di layer mana dan bagaimana Anda mengimplementasikan **Idempotency Key Pattern** pada Application/Infrastructure layer ASP.NET Core untuk memastikan pengiriman ganda (*at-least-once delivery*) tidak menyebabkan side-effect ganda pada sistem eksternal maupun database internal?
2. Bandingkan efektivitas penggunaan **Pessimistic Locking (`SELECT ... FOR UPDATE`)**, **Optimistic Concurrency Control (OCC via EF Core RowVersion/xmin)**, dan **Distributed Lock (e.g., Redlock via Redis)** dalam mengatasi *race condition* di atas dengan mempertimbangkan latency, scalability, dan deadlock hazards.

---

### Skenario C: Trade-off Arsitektur: Monolith Modular vs. Event-Driven Microservices
Perusahaan Anda memiliki aplikasi Monolith ASP.NET Core lawas yang melayani 3 domain inti: *Catalog*, *Billing*, dan *Inventory*. Tim Engineering terpecah: satu kubu ingin langsung memecah monolith menjadi 3 microservice independen dengan database terpisah yang berkomunikasi via gRPC dan Apache Kafka. Kubu lain menginginkan refaktor bertahap menjadi **Modular Monolith** dengan Clean Architecture dan *In-Memory Message Bus* lebih dulu.

**Pertanyaan Diagnostik:**
1. Lakukan analisis trade-off teknis komprehensif (evaluasi aspek: *Network Latency*, *Consistency Model (Strong vs Eventual)*, *Operational Complexity/DevOps overhead*, dan *Blast Radius* kegagalan) antara kedua opsi tersebut.
2. Jika Modular Monolith dipilih sebagai fase transisi, bagaimana Anda mendesain boundary antar-modul di ASP.NET Core (secara struktural *C# Projects*, enkapsulasi internal assembly, dan komunikasi antar domain) agar di masa depan modul *Billing* dapat dipisahkan menjadi microservice independen tanpa menulis ulang domain logic-nya?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Cloud-Native Order Processing Service

#### Problem
Anda ditugaskan merancang dan mengimplementasikan core skeleton dari microservice transaksi enterprise (`OrderProcessingService`) menggunakan ASP.NET Core terkini (.NET 8/9 LTS). Service ini harus tahan banting (*resilient*) terhadap kegagalan jaringan, siap dideploy ke environment Kubernetes secara nir-henti (*zero-downtime*), dan memiliki visibilitas telemetri kelas satu.

#### Functional & Architectural Requirements
1. **Clean Architecture Structure**:
   - `OrderProcessing.Domain`: Model entitas `Order`, `OrderItem`, Domain Events, Value Objects (menggunakan invariant-safe DDD patterns, tanpa dependensi framework luar).
   - `OrderProcessing.Application`: Implementasikan MediatR (atau custom Mediator pattern) untuk command `CreateOrderCommand`. Gunakan FluentValidation.
   - `OrderProcessing.Infrastructure`: EF Core DbContext yang menargetkan PostgreSQL/SQL Server, implementasi Transactional Outbox Pattern via Interceptor atau Background Worker.
   - `OrderProcessing.Api`: Minimal API atau Controller murni sebagai I/O routing.
2. **Cloud-Native & Container Hardening**:
   - Sediakan `Dockerfile` multi-stage build yang memproduksi *rootless*, *distroless* (atau Alpine hardened) container image untuk meminimalkan attack surface.
   - Konfigurasikan implementasi `IHostApplicationLifetime` untuk graceful connection draining saat pod dimatikan.
3. **Resilience & Fault Tolerance**:
   - Definisikan Polly v8 Resilience Pipeline pada downstream outbound HTTP call (misal: simulasi integrasi *PaymentGateway*) yang menggabungkan:
     - *Timeout Strategy* (misal: max 2.5s)
     - *Retry with Exponential Backoff and Jitter* (max 3 retries)
     - *Circuit Breaker* (buka circuit jika failure rate > 50% dalam window 10 detik)
4. **Health Checks & Observability**:
   - Endpoint `/healthz/live` (Liveness) hanya memvalidasi internal server responsiveness.
   - Endpoint `/healthz/ready` (Readiness) memvalidasi kesiapan koneksi Database dan Message Broker via `AspNetCore.Diagnostics.HealthChecks`.
   - Setup integrasi OpenTelemetry yang mengekspor Traces (W3C standard) dan Metrics (System.Diagnostics) ke console/OTLP collector.

#### Constraints
- Zero external direct dependencies di Core Domain layer.
- Thread-safe, non-blocking asynchronous programming (`async`/`await` end-to-end tanpa `Task.Result` / `Task.Wait`).
- Tidak boleh terjadi data loss saat instance di-kill (`SIGTERM`) di tengah proses penulisan order dan event outbox.

#### Expected Output
1. Struktur direktori solusi (`src/` dan `tests/`) yang mematuhi batas arsitektural Clean Architecture.
2. Kode C# esensial:
   - Command Handler dengan Outbox pattern context.
   - Registrasi Polly v8 Resilience Pipeline via Dependency Injection.
   - Konfigurasi `Program.cs` yang mengekspos Health Checks, OpenTelemetry, dan Middleware Pipeline.
3. Production-ready `Dockerfile` (Multi-stage build, Rootless execution).
4. File konfigurasi manifest Kubernetes (`deployment.yaml`) yang mendefinisikan Pod Spec lengkap: probes (startup, liveness, readiness), resource limits/requests, preStop lifecycle hook, dan termination grace period.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan ketat aturan dependensi (*Dependency Rule*) pada Clean Architecture dan Hexagonal Architecture.
- [ ] Perbedaan fundamental antara Workstation GC dan Server GC serta perilakunya di dalam container Linux dengan cgroups v1/v2 limit.
- [ ] Mengapa Thread Pool starvation terjadi pada ASP.NET Core dan bagaimana menghindarinya melalui full-stack asynchronous I/O.
- [ ] Mekanisme kerja state machine Circuit Breaker (Closed, Open, Half-Open) dan bahaya Retry Storm tanpa Jitter.
- [ ] Lifecycle graceful termination pod di Kubernetes: interaksi antara `SIGTERM`, kubelet endpoint removal, `preStop` hook, dan connection draining Kestrel.
- [ ] Garansi *At-least-once delivery* vs *Exactly-once processing* serta implementasi Transactional Outbox Pattern dan Idempotent Consumer.
- [ ] Peran dan arsitektur spesifikasi OpenTelemetry: Tracing (`TraceId`, `SpanId`), Metrics, dan Semantic Conventions.

### Saya tidak perlu menghafal:
- [ ] Syntax baris demi baris dari Dockerfile directive atau syntax exact Kubernetes manifest YAML (cukup memahami semantiknya dan menggunakan template/dokumentasi resmi).
- [ ] Seluruh overload parameter konfigurasi Polly Resilience Pipeline (cukup memahami konsep Timeout, Circuit Breaker, dan algoritma Backoff/Jitter).
- [ ] Semua konfigurasi internal garbage collector runtime switch (cukup memahami flag utama: `ServerGarbageCollection` dan `DOTNET_GCHeapHardLimitPercent`).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan memperbaiki *cascading failures* downstream menggunakan Polly v8 resilience pipelines.
- [ ] Merancang dan mengonfigurasi endpoint Kubernetes Health Checks (`Startup`, `Liveness`, `Readiness`) secara proporsional tanpa anti-pattern.
- [ ] Menulis multi-stage `Dockerfile` untuk aplikasi ASP.NET Core yang menghasilkan image berukuran minimalis, berjalan di mode non-root user (*rootless*).
- [ ] Mengimplementasikan *Transactional Outbox Pattern* menggunakan EF Core DbContext transaction boundary untuk mencegah partial write hazard.
- [ ] Menghubungkan tracing antar-service menggunakan OpenTelemetry instrumentation library untuk ASP.NET Core, HttpClient, dan Entity Framework Core.
- [ ] Menganalisis log produksi dan heap/thread dump menggunakan tools analitis runtime (seperti `dotnet-dump`, `dotnet-trace`, atau `dotnet-counters`) saat terjadi lonjakan latency.