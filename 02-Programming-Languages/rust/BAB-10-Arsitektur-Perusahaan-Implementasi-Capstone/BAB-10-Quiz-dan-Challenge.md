# BAB 10: Quiz, Challenge, & Knowledge Check
**Arsitektur Perusahaan & Implementasi Capstone**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Abstraksi Domain & Inversi Ketergantungan (Clean/Hexagonal Architecture)**  
   Jelaskan bagaimana Rust mengimplementasikan prinsip *Dependency Inversion* tanpa keberadaan konsep *interface inheritance* seperti pada Java/C#. Bandingkan implikasi teknis penggunaan *Static Dispatch* (`impl Trait` / Generics dengan *monomorphization*) versus *Dynamic Dispatch* (`Box<dyn Trait>` / Trait Objects) dalam arsitektur aplikasi skala enterprise, ditinjau dari ukuran binary, *compilation time*, *cache locality*, dan fleksibilitas *dependency injection* saat *unit testing*.

2. **Type-Driven Domain Modeling & Invariant Enforcement**  
   Dalam Domain-Driven Design (DDD), aturan domain (*invariants*) harus dijaga agar selalu valid. Bagaimana idiom Rust seperti *Newtype Pattern*, *Typestate Pattern*, dan representasi *Algebraic Data Types* (ADT melalui `enum`) digunakan untuk membuat status domain yang ilegal menjadi tidak dapat dikompilasi (*make illegal states unrepresentable*)? Berikan contoh konseptual siklus hidup entitas order dari `Draft` $\to$ `Paid` $\to$ `Shipped`.

3. **Strategi Error Handling Berlapis Enterprise**  
   Mengapa mencampurkan `anyhow` dan `thiserror` dalam satu crate domain dianggap sebagai *architectural anti-pattern*? Definisikan batas arsitektural (*architectural boundary*) yang jelas di mana `thiserror` wajib digunakan (misal: core domain, adapters, client SDKs) versus di mana penanganan error berbasis kontekstual dinamis seperti `anyhow` atau `eyre` diperbolehkan (misal: binary entry point, CLI, top-level consumers).

4. **Multi-Crate Workspace Topology & Boundary Encapsulation**  
   Pada arsitektur *Cargo Workspace* skala besar, bagaimana Anda menyusun topologi modularitas untuk mencegah *circular dependencies* antar-crate? Jelaskan fungsi kontrol visibilitas Rust (`pub(crate)`, `pub(super)`, dan *re-exporting* via facade) dalam memproteksi *internal implementation details* dari adapter infrastruktur agar tidak bocor ke domain layer.

5. **Observabilitas Berstandar Produksi tanpa Domain Pollution**  
   Bagaimana cara mengintegrasikan telemetri terdistribusi (*distributed tracing*, *metrics*, dan *structured logging*) menggunakan crate `tracing` dan `opentelemetry` ke dalam sistem enterprise Rust tanpa mengotori *pure business logic* di layer domain dengan dependensi infrastruktur eksternal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Async Runtime Starvation & Thread-Pool Hygiene**  
   Sebuah *service* berbasis Tokio mengalami lonjakan drastis pada *tail latency* (P99) secara acak, padahal utilisasi CPU tercatat hanya 35%. Setelah diinspeksi, ditemukan pemanggilan fungsi komputasi berat dan fungsi blocking kriptografi legacy di dalam blok `async fn`. Jelaskan secara mendalam bagaimana mekanisme *work-stealing scheduler* Tokio beroperasi, mengapa eksekusi blocking merusak kooperatif *scheduling*, dan bagaimana teknik isolasi yang benar menggunakan `tokio::task::spawn_blocking` atau *dedicated OS thread pool*.

2. **Memory Leakage & Resource Starvation via Cyclic References**  
   Meskipun Rust memiliki sistem *ownership* tanpa *Garbage Collector*, memory leak tetap dapat terjadi di tingkat aplikasi enterprise (misal: pada sistem *in-memory cache* atau *event listener registry* yang menggunakan `Arc<RwLock<T>>`). Jelaskan bagaimana *reference cycle* terbentuk dalam Rust, bagaimana cara mendiagnosisnya menggunakan tools analisis memori (seperti Valgrind massif atau heaptrack), dan bagaimana mengatasinya menggunakan `std::sync::Weak`.

3. **Object Safety Violations pada Adapter Extensibility**  
   Saat merancang *pluggable storage adapter* untuk mendukung multi-cloud (AWS S3, GCP Cloud Storage), Anda mendeklarasikan trait:
   ```rust
   pub trait BlobStorage {
       async fn upload<R: std::io::Read>(&self, key: &str, reader: R) -> Result<(), StorageError>;
   }
   ```
   Kompiler menolak pembuatan `Box<dyn BlobStorage>` dengan error *object safety*. Analisis penyebab internal penolakan ini oleh compiler (terkait generic method dan trait `Sized`), lalu tunjukkan cara mendesain ulang trait tersebut agar memenuhi syarat *Object Safety* tanpa mengorbankan performa *streaming I/O*.

4. **Cancellation Safety pada Pipeline Transaksional**  
   Dalam runtime async Rust, future yang dihentikan via `tokio::select!` akan langsung di-*drop* di titik *yield* (suspension point) terdekat. Analisis bahaya *cancellation unsafety* pada operasi multi-step domain (misal: menarik dana dari akun, lalu menembak service notifikasi). Bagaimana cara mengaudit, mendesain, dan mengamankan operasi kritis agar *cancellation-safe* menggunakan idiom State Machine atau `tokio::sync::oneshot` / `tokio::task::spawn` non-cancellable wrapper?

5. **Graceful Shutdown Orchestration & In-Flight Transaction Draining**  
   Ketika aplikasi menerima sinyal `SIGTERM` dari orchestrator (seperti Kubernetes), bagaimana arsitektur graceful shutdown yang deterministik dirancang di Rust? Jelaskan koordinasi antarkomponen menggunakan `tokio_util::sync::CancellationToken`, pelacakan proses *in-flight* via `tokio::sync::mpsc` channel drop semantics / `tokio::sync::Barrier`, dan batas timeout penghentian paksa.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck & Thread Starvation pada High-Throughput Payment Ingestion Engine
Sistem payment gateway berbasis Rust (Tokio, Axum, SQLx) memproses 25.000 request per detik. Pada kondisi peak load, metrik menunjukkan latensi API melonjak dari 15ms menjadi 4.500ms, dan *health check endpoint* (`/healthz`) mulai *timeout*, menyebabkan Kubernetes me-restart container secara berulang (*crash loop* akibat *liveness probe failure*).  
Profiling awal menunjukkan:
* Database connection pool (`sqlx::Pool`) terisi penuh (100% utilized).
* Kode handler melakukan deserialisasi JSON berukuran besar dan enkripsi payload JWT secara sinkron langsung di handler request sebelum query database.
* Terdapat mutex global `std::sync::Mutex<HashMap<String, RateLimiter>>` yang diakses di setiap request.

**Pertanyaan Diagnostik:**
1. Apa akar masalah arsitektural yang menyebabkan *health check endpoint* ikut mengalami timeout padahal ia tidak mengakses database?
2. Mengapa penggunaan `std::sync::Mutex` di dalam konteks asynchronous sangat berbahaya dibandingkan `tokio::sync::Mutex`, dan kapan `std::sync::Mutex` justru lebih dianjurkan daripada versi asynchronous-nya?
3. Rancang rencana mitigasi arsitektur komprehensif untuk mengeliminasi bottleneck tersebut (restrukturisasi connection pool, isolasi CPU-bound tasks, optimasi rate-limiting state, dan segregasi health check).

---

### Skenario B: Silent Data Corruption & Race Condition pada Distributed Ledger System
Sebuah sistem *double-entry bookkeeping* finansial yang mendistribusikan mutasi akun antar-node mengalami diskrepansi audit saldo: saldo total tidak balance sebesar 0.001% pada akhir hari transaksi bervolume tinggi.  
Setelah investigasi, alur mutasi didefinisikan sebagai berikut:
1. Service membaca saldo dari database PostgreSQL menggunakan isolation level `READ COMMITTED`.
2. Model domain memvalidasi kecukupan saldo di memori Rust:
   ```rust
   if account.balance >= transfer_amount {
       account.balance -= transfer_amount;
       // ... hit external clearinghouse via HTTP ...
       // ... commit balance update to DB ...
   }
   ```
3. HTTP client dikonfigurasi dengan retry otomatis jika terjadi network glitch.

**Pertanyaan Diagnostik:**
1. Di mana letak kegagalan arsitektur konkurensi dan batas transaksional pada alur di atas (*Time-of-Check to Time-of-Use* / TOCTOU, non-repeatable read, dan *distributed side-effects*)?
2. Bagaimana Anda menyusun ulang pola transaksi ini menggunakan prinsip *Pessimistic Locking* (`SELECT FOR UPDATE`) atau *Optimistic Concurrency Control* (version vector) yang divalidasi oleh sistem tipe Rust?
3. Bagaimana memastikan efek samping eksternal (HTTP clearinghouse) aman dari eksekusi ganda menggunakan *Idempotency Keys* dan pola *Transactional Outbox* di Rust?

---

### Skenario C: Arsitektur Modul Monolith Workspace vs Microservices Decomposition
Perusahaan Anda memiliki aplikasi monolitik Rust yang besar (1 workspace dengan 45 crates internal, 800.000 baris kode). Masalah yang muncul:
* Waktu kompilasi CI/CD mencapai 45 menit (clean build).
* Kebutuhan resource RAM dev machine membengkak (rust-analyzer sering OOM).
* Tim enterprise lain menuntut agar fungsionalitas *Inventory Service* dipisahkan menjadi microservice independen dengan target SLA latensi P99 < 5ms.

Manajemen mengusulkan pemecahan langsung menjadi 5 microservice yang berkomunikasi via HTTP/JSON REST.

**Pertanyaan Diagnostik:**
1. Mengapa memecah monolith Rust langsung menjadi microservice berbasis HTTP/JSON berpotensi menurunkan throughput dan justru meningkatkan kompleksitas operasional serta latensi secara signifikan?
2. Apa trade-off teknis jika mengganti HTTP/JSON dengan gRPC (Tonic / Protobuf) vs IPC berbasis shared memory / Unix Domain Sockets jika service tetap di-deploy pada node yang sama?
3. Langkah optimasi arsitektur apa yang bisa diterapkan terlebih dahulu pada Monolith Workspace Rust (misal: *compiler caching* via `sccache`, dynamic linking untuk binary dev via `cargo-mold`, arsitektur decoupled *Event-Driven* internal via Actor / MPSC, dan modular boundaries) sebelum memutuskan transisi fisik ke microservices?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Core Matching Engine & Distributed Transaction Ledger (Capstone Implementation)

#### Problem
Anda ditugaskan merancang dan mengimplementasikan modul inti (*engine*) dari sebuah sistem bursa internal (*High-Frequency Order Book & Execution Engine*) yang harus mampu memproses antrean order dengan latensi mikrodetik, menjamin konsistensi catatan mutasi saldo secara deterministik, dan menyediakan API boundary berbasis Clean Architecture yang tangguh.

#### Requirements
1. **Domain Engine Layer (Zero Dynamic Allocation Core):**
   * Implementasikan struktur data `OrderBook` dengan dua sisi: `Bids` dan `Asks` menggunakan struktur data berkinerja tinggi (misal: `BTreeMap` atau contiguous array ring-buffer).
   * Engine harus mendukung order types: `LimitOrder`, `MarketOrder`, dan `CancelOrder`.
   * Logika matching engine harus berupa fungsi deterministik murni (*pure function*) yang tidak melakukan I/O, network call, maupun alokasi memori berlebih di *hot path*.
2. **Transactional Ledger & Typestate State Machine:**
   * Siklus hidup order (`New` $\to$ `PartiallyFilled` / `Filled` / `Cancelled`) wajib direpresentasikan menggunakan **Typestate Pattern** guna menjamin secara compile-time bahwa order yang telah berstatus `Filled` atau `Cancelled` tidak dapat dimasukkan kembali ke matching engine.
   * Model mutasi saldo akun debit-kredit harus mematuhi prinsip double-entry: total debet harus sama persis dengan total kredit pada setiap *trade execution event*.
3. **Hexagonal Infrastructure Adapters:**
   * **Inbound Adapter:** Sediakan interface Axum Web API (atau Tonic gRPC) untuk menerima request transaksi.
   * **Outbound Adapter:** Sediakan abstraksi repository penyimpanan transaksi menggunakan Trait (misal: `LedgerRepository`) dengan implementasi mock in-memory dan database stub.
   * **Event Streaming Adapter:** Emisikan setiap trade match event ke asynchronous bounded channel (`tokio::sync::mpsc`) untuk pemrosesan audit log downstream.
4. **Resilience & Observability:**
   * Integrasikan structured tracing (`tracing`) dengan spans kontekstual (menyimpan `order_id` dan `account_id`).
   * Implementasikan graceful shutdown pipeline: jika service menerima `SIGINT`/`SIGTERM`, engine berhenti menerima order baru, menuntaskan order yang sedang berada di antrean in-memory buffer (*draining*), dan menyimpan snapshot state terakhir sebelum exit.

#### Constraints
* **P99 Execution Time:** Eksekusi matching order di memori harus selesai dalam waktu $< 50\,\mu\text{s}$ per order.
* **Safety Rules:** Wajib `100% Safe Rust` (terapkan `#![forbid(unsafe_code)]` pada root crate domain).
* **Concurrency:** Tidak boleh terjadi *deadlock* pada race condition order placement simultan dari ribuan user concurrent.
* **Compiler Directives:** Error handling di layer domain wajib menggunakan `thiserror`, dilarang keras menggunakan `unwrap()` atau `expect()` di level produksi (hanya diizinkan di unit testing).

#### Expected Output
* Repositori modular Cargo Workspace terstruktur:
  * `core-domain` (Entity, Value Objects, Typestate Order, Matching Engine murni).
  * `application-service` (Use cases, orchestration, port definitions).
  * `infrastructure-adapters` (REST/gRPC handler, database repositories, tracing setup).
  * `app-bin` (Binary entry point, configuration loader, graceful shutdown orchestrator).
* Unit test suite komprehensif untuk domain invariants & edge cases matching (partial fills, price-time priority).
* Benchmark suite menggunakan `criterion` yang membuktikan performa matching engine di bawah batas latency yang disyaratkan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Cara mengimplementasikan Clean/Hexagonal Architecture secara idiomatik menggunakan sistem trait, generic constraints, dan modular workspace di Rust.
- [ ] Perbedaan fundamental, trade-off performa, dan footprint memori antara *Static Dispatch* (monomorphization) dan *Dynamic Dispatch* (`dyn Trait` / vtable).
- [ ] Aturan *Object Safety* pada Trait dan batasan-batasannya saat mendesain abstraksi layer infrastruktur.
- [ ] Cara mengekspresikan status domain kompleks secara ketat menggunakan *Typestate Pattern* dan ADT (`enum`) guna mencegah invalid runtime state.
- [ ] Perbedaan peruntukan crate `thiserror` (untuk domain & error kontrak spesifik) dan `anyhow` (untuk batas aplikasi/entry point).
- [ ] Arsitektur internal runtime Tokio (work-stealing thread pool, cooperative multitasking, task suspension, cancellation safety).
- [ ] Bahaya pemanggilan fungsi blocking / CPU-bound di dalam async thread dan strategi isolasinya.
- [ ] Pola orkestrasi *Graceful Shutdown* menggunakan `CancellationToken` dan teknik draining bounded channel.

### Saya tidak perlu menghafal:
- [ ] Seluruh signature method dari crate pihak ketiga (misal: seluruh builder API dari `axum`, `tonic`, atau `sqlx`—gunakan dokumentasi `docs.rs`).
- [ ] Representasi memori low-level bit-per-bit dari vtable pointer layout pada rustc internal ABI (cukup pahami konsep fat pointer: data pointer + vtable pointer).
- [ ] Kode implementasi mendalam dari algoritma crypto hashing atau protokol low-level transport engine.

### Saya harus bisa melakukan:
- [ ] Menyusun struktur Cargo Workspace multi-crate enterprise yang modular, terisolasi, bebas dari circular dependency, dan memiliki visibility scope yang aman.
- [ ] Mendiagnosis bottleneck latensi (P99 spikes) akibat blocking execution atau lock contention pada runtime async menggunakan tracing tools.
- [ ] Mengonversi domain model konvensional yang rentan runtime error menjadi sistem domain yang *strictly typed* (Type-Driven Development).
- [ ] Merancang kontrak trait adapter infrastruktur yang fleksibel, testable (mudah di-mock), dan aman dari runtime panic.
- [ ] Menulis benchmark performa sub-milidetik menggunakan `criterion` untuk membuktikan batas ambang SLA kode domain kritis.
- [ ] Mengimplementasikan pipeline shutdown yang deterministik dan *crash-resilient* pada sistem microservice Rust berstandar enterprise.