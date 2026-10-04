# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengonstruksi** arsitektur enterprise berbasis *Hexagonal / Clean Architecture* (Ports and Adapters) menggunakan kapabilitas sistem tipe Rust (Trait, Generics, Associated Types) tanpa runtime overhead (*Zero-Cost Abstraction*).
- **Mendesain & Mengimplementasikan** *Domain Invariants* menggunakan *Type-State Pattern* untuk memvalidasi *state machine* bisnis pada saat kompilasi (*compile-time correctness*).
- **Mengoptimasi Konkurensi Skala Tinggi** dengan memahami arsitektur internal *Tokio Work-Stealing Runtime*, mitigasi *cooperative scheduling starvation*, pemilihan alokator memori produksi (*jemalloc/mimalloc*), serta eliminasi *lock contention* melalui *lock-free data structures*.
- **Menerapkan Pola Ketahanan Sistem Produksi** (*Resilience Engineering*) meliputi *Transactional Outbox Pattern*, *Idempotency Engine*, *Backpressure Handling*, dan *Distributed Tracing* terstruktur.
- **Mengevaluasi & Mendiagnosis** anomali performa mikro seperti *cache-line bouncing*, *allocation churn*, *async cancellation hazards*, dan *blocking calls* di dalam async executor.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Rust Core & Memory Semantics**: Ownership, Borrowing, Lifetimes (`'a`, static, HRTB), dan Smart Pointers (`Box`, `Rc`, `Arc`, `RefCell`).
- **Asynchronous Rust**: Pemahaman runtime `tokio`, *Pinning* (`Pin<&mut T>`), `Future` contract (`poll`, `Context`, `Waker`).
- **Trait Mechanics**: *Static Dispatch* (`impl Trait`, monomorphization) vs *Dynamic Dispatch* (`dyn Trait`, vtable pointer overhead).
- **Tooling**: Kemampuan menggunakan `cargo`, `cargo-clippy`, `cargo-flamegraph`, dan `gdb`/`lldb`.

---

## 3. Concept & Internal Architecture

### 3.1 Hexagonal Architecture Menggunakan Zero-Cost Static Dispatch
Mayoritas framework pada bahasa dinamis mengandalkan *Dependency Injection (DI) Container* berbasis runtime reflection. Di Rust, pendekatan idiomatik enterprise mengandalkan **Static Dispatch via Traits dan Associated Types**, atau **Dynamic Dispatch via Vtables** jika polimorfisme heterogen mutlak dibutuhkan.

```
       +-----------------------------------------------------------+
       |                      DRIVING ADAPTER                      |
       |  (REST API / gRPC Engine / Kafka Consumer / CLI CLI Tool) |
       +-----------------------------+-----------------------------+
                                     |
                                     v  [Invokes]
                       +-------------+-------------+
                       |        DRIVING PORT       |
                       | (Application Service Trait|
                       +-------------+-------------+
                                     |
                                     v  [Implemented by]
        +----------------------------+----------------------------+
        |                     CORE APPLICATION                    |
        |  +---------------------------------------------------+  |
        |  |                   DOMAIN LAYER                    |  |
        |  | (Entities, Value Objects, Type-State State Machine)|  |
        |  +---------------------------------------------------+  |
        +----------------------------+----------------------------+
                                     |
                                     v  [Depends on Trait]
                       +-------------+-------------+
                       |        DRIVEN PORT        |
                       |  (Persistence/Queue Trait)|
                       +-------------+-------------+
                                     |
                                     v  [Implemented by]
       +-----------------------------+-----------------------------+
       |                       DRIVEN ADAPTER                      |
       | (PostgreSQL / Redis Cache / AWS S3 / Distributed Outbox)  |
       +-----------------------------------------------------------+
```

Dengan memanfaatkan Static Dispatch:
- Port didefinisikan sebagai Trait: `pub trait PaymentRepository: Send + Sync + 'static`.
- Service diikat via Generics: `pub struct PaymentService<R: PaymentRepository> { repo: R }`.
- Kompilator melakukan **monomorphization**: memproduksi kode mesin spesifik tanpa overhead alokasi pointer pointer ganda (vtable lookup) dan memungkinkan *aggressive function inlining*.

### 3.2 Tokio Runtime Internals: Work-Stealing, Budgets, dan Micro-tasks
Runtime Tokio multi-thread terdiri atas:
1. **Worker Threads**: Sejumlah thread OS yang setara dengan core CPU logis (dapat dikonfigurasi via `worker_threads`).
2. **Local Run Queue**: Setiap thread memiliki antrean lokal *lock-free* berkapasitas 256 tasks (menggunakan buffer cincin / ring buffer).
3. **Global Queue**: Antrean bersama yang diakses jika antrean lokal penuh atau saat worker thread mencari task baru (dilindungi oleh mutex berkecepatan tinggi).
4. **Cooperative Scheduling (Task Budget)**: Setiap kali async task menjalankan `.await`, task decrement sebuah *cooperation budget* (default: 128 ticks). Jika habis, task secara sukarela menghasilkan giliran (*yield*) kembali ke queue untuk mencegah monopoli thread CPU.

```
[ Worker Thread 1 ]         [ Worker Thread 2 ]         [ Worker Thread 3 ]
+-----------------+         +-----------------+         +-----------------+
| Local Queue     |         | Local Queue     |         | Local Queue     |
| [T1][T2][T3]    |         | [T4][T5]        |         | (KOSONG!)       |
+--------+--------+         +--------+--------+         +--------+--------+
         |                           |                           |
         |                           |             Steals 50%    |
         |                           |             tasks dari T1 |
         |                           +-------------------------->+
         v                                                       
+-------------------------------------------------------------------------+
|                  GLOBAL INJECTION QUEUE (Shared / Fallback)             |
|                           [T6][T7][T8]                                  |
+-------------------------------------------------------------------------+
```

Jika worker 3 kehabisan task pada local queue-nya:
1. Ia memeriksa Global Queue.
2. Jika kosong, ia menjalankan algoritma **Work Stealing**: mencuri setengah (*steal half*) task dari local queue milik worker lain (misalnya Worker 1) secara atomic (`atomic CAS`).

### 3.3 Memory Layout, Alignment, dan Cache-Line Contention
Pada komputasi latensi ultra-rendah:
- **False Sharing**: Dua thread menulis ke variabel independen yang berada di dalam baris cache (*cache line*) yang sama (umumnya 64 byte pada x86_64 dan ARM64). Hal ini memicu *MESI cache coherency protocol invalidation* terus-menerus.
- Solusi di Rust: Menyisipkan padding eksplisit via `#[repr(align(64))]` atau struktur pembungkus seperti `crossbeam_utils::CachePadded<T>`.

---

## 4. Why & What

| Dimensi | Pendekatan Enterprise Konvensional (Java/Go/Node) | Pendekatan Enterprise Rust |
|---|---|---|
| **Type Safety & State** | Validasi runtime (if-else, runtime exceptions, validasi hibernate saat runtime). | **Type-State Pattern**: Transisi state ilegal gagal dikompilasi (*Unrepresentable Invalid States*). |
| **Concurrency Model** | Thread-pool besar dengan GC Pause (Java) atau Goroutines dengan runtime preemption & GC overhead (Go). | **Work-Stealing Executor Non-GC**: Zero runtime pause, deterministic allocation, memori ultra-ramping. |
| **Dependency Decoupling**| Runtime DI via Reflection (Spring `@Autowired`), memperlambat cold-start dan memicu runtime error. | **Compile-time Monomorphization**: Validasi dependensi saat kompilasi, zero overhead, inline optimization. |
| **Memory Allocation** | Default dynamic allocations pada heap, memicu GC churn. | **Stack allocation priority**, Zero-copy slice borrow (`&str`, `&[u8]`), Custom allocators (`mimalloc`). |

---

## 5. How: Workflow Detail Eksekusi Transaksi Finansial

Alur eksekusi request transaksi perbankan dengan pola transactional outbox dan type-state:

```
[Client Request]
       |
       v
1. [Inbound Adapter] -> Deserialisasi zero-copy payload via Serde
       |
       v
2. [Domain Layer]    -> Type-State Initial: Transaction<Draft>
       |             -> Validasi invariant bisnis: Signature & Limit
       v
3. [Domain Transition]-> Konsumsi Ownership `Draft` -> Transisi ke `Transaction<Authorized>`
       |             -> Tidak ada path rollback manual; state lama musnah dari stack
       v
4. [Port Outbound]   -> Atomic Execution:
       |                - Simpan Event ke Outbox Table
       |                - Update Ledger Balances
       |                - Commit RDBMS Transaction (via sqlx/deadpool)
       v
5. [Async Worker]    -> Background Task membaca Outbox via CDC / Polling
       |             -> Publikasi event ke Apache Kafka / Redpanda
       v
[Response OK 200]
```

---

## 6. Analogy & Diagram

### Analogi Dunia Nyata: Perakitan Mobil dengan Lintasan Rel Fisik
Arsitektur runtime Rust mirip lintasan perakitan pabrik mobil otomatis:
- Pada bahasa GC (Java/Go), lintasan diisi oleh mobil dan inspektur kebersihan berjalan melintasi lintasan secara acak. Sesekali, peluit dibunyikan (*Stop-The-World* GC) dan semua perakitan berhenti agar lantai bisa disapu.
- Pada Rust, lintasan dibuat presisi tinggi. Setiap komponen mobil diikat dengan sekrup baja berukuran pas (*Type-State*). Pintu mobil belum bisa dipasang jika sasis belum dicat karena rel mekanisnya tidak menyatu (*compile-time rejection*). Sisa limbah dibuang ke corong pembuangan seketika saat pekerja melepaskan suku cadang (*deterministic RAII dropping*), sehingga tidak memerlukan waktu pembersihan terjadwal.

---

## 7. Simple & Practical Examples

### 7.1 Simple Example: Type-State Pattern untuk Pipeline Order Transaksi
Contoh ini mendemonstrasikan bagaimana kita mengunci perpindahan state secara matematis pada tahap kompilasi. Order yang berstatus `Unverified` tidak dapat diproses checkout secara sembarangan.

```rust
use std::marker::PhantomData;

// State Marker structs
pub struct Unverified;
pub struct Verified {
    pub verification_code: String,
}
pub struct Paid {
    pub payment_receipt: String,
}

// Domain Entity dengan Type-State
pub struct Order<State> {
    pub order_id: u64,
    pub amount: u64,
    state: State,
}

// Inisialisasi awal: Hanya bisa dibuat dalam state Unverified
impl Order<Unverified> {
    pub fn new(order_id: u64, amount: u64) -> Self {
        Self {
            order_id,
            amount,
            state: Unverified,
        }
    }

    // Transisi: Mengonsumsi `self` (Ownership dipindah), mengembalikan State baru
    pub fn verify(self, verification_code: String) -> Order<Verified> {
        Order {
            order_id: self.order_id,
            amount: self.amount,
            state: Verified { verification_code },
        }
    }
}

impl Order<Verified> {
    // Hanya Order<Verified> yang memiliki method checkout!
    pub fn checkout(self, receipt: String) -> Order<Paid> {
        Order {
            order_id: self.order_id,
            amount: self.amount,
            state: Paid { payment_receipt: receipt },
        }
    }
}

fn main() {
    let order = Order::new(1001, 500_000);
    
    // COMPILE ERROR jika langsung: order.checkout("REC-123".into());
    // Method checkout tidak ada di Order<Unverified>!

    let verified_order = order.verify("AUTH-999".into());
    let paid_order = verified_order.checkout("REC-88847".into());

    println!("Order {} sukses dibayar. Receipt: {}", paid_order.order_id, paid_order.state.payment_receipt);
}
```

### 7.2 Practical Example: Hexagonal Architecture Core Engine (Production Grade)
Implementasi service pembayaran transfer antar rekening lengkap dengan Outbound Ports, Error Domain terdefinisi, zero-allocation abstractions, dan tracing.

```rust
use std::sync::Arc;
use thiserror::Error;
use tracing::{info, instrument};

// ==========================================
// 1. DOMAIN LAYER
// ==========================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AccountId(pub u64);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CurrencyAmount {
    pub cents: u64,
}

impl CurrencyAmount {
    pub fn new(cents: u64) -> Result<Self, DomainError> {
        if cents == 0 {
            return Err(DomainError::InvalidAmount("Jumlah transfer harus > 0".into()));
        }
        Ok(Self { cents })
    }
}

#[derive(Debug, Error)]
pub enum DomainError {
    #[error("Saldo tidak mencukupi. Dibutuhkan: {required}, Tersedia: {available}")]
    InsufficientFunds { required: u64, available: u64 },
    #[error("Rekening tidak ditemukan: {0:?}")]
    AccountNotFound(AccountId),
    #[error("Nilai transaksi tidak valid: {0}")]
    InvalidAmount(String),
    #[error("Database error internal: {0}")]
    InfrastructureFailure(String),
}

// ==========================================
// 2. PORTS (DRIVEN / OUTBOUND)
// ==========================================

#[async_trait::async_trait]
pub trait LedgerPort: Send + Sync {
    async fn get_balance(&self, account: AccountId) -> Result<CurrencyAmount, DomainError>;
    async fn execute_transfer(
        &self,
        source: AccountId,
        destination: AccountId,
        amount: CurrencyAmount,
        outbox_event: String,
    ) -> Result<(), DomainError>;
}

// ==========================================
// 3. APPLICATION SERVICE (HEXAGON CORE)
// ==========================================

pub struct TransferService<L: LedgerPort> {
    ledger: Arc<L>,
}

impl<L: LedgerPort> TransferService<L> {
    pub fn new(ledger: Arc<L>) -> Self {
        Self { ledger }
    }

    #[instrument(skip(self), fields(source = %source.0, dest = %destination.0, amount = %amount.cents))]
    pub async fn transfer(
        &self,
        source: AccountId,
        destination: AccountId,
        amount: CurrencyAmount,
    ) -> Result<(), DomainError> {
        // Step 1: Validasi Invariant Domain
        let source_balance = self.ledger.get_balance(source).await?;
        if source_balance.cents < amount.cents {
            return Err(DomainError::InsufficientFunds {
                required: amount.cents,
                available: source_balance.cents,
            });
        }

        // Step 2: Siapkan Outbox Transactional Event Payload
        let event_json = format!(
            r#"{{"event":"FundsTransferred","from":{},"to":{},"amount":{}}}"#,
            source.0, destination.0, amount.cents
        );

        // Step 3: Eksekusi Atomic via Port
        self.ledger
            .execute_transfer(source, destination, amount, event_json)
            .await?;

        info!("Transfer berhasil dieksekusi secara atomik.");
        Ok(())
    }
}

// ==========================================
// 4. ADAPTER (DRIVEN / MOCK PERSISTENCE)
// ==========================================

pub struct InMemoryLedgerAdapter {
    // Simulasi in-memory concurrent state (di produksi: Connection Pool SQLx)
    dummy_balance: parking_lot::RwLock<u64>,
}

impl InMemoryLedgerAdapter {
    pub fn new(initial_balance: u64) -> Self {
        Self {
            dummy_balance: parking_lot::RwLock::new(initial_balance),
        }
    }
}

#[async_trait::async_trait]
impl LedgerPort for InMemoryLedgerAdapter {
    async fn get_balance(&self, _account: AccountId) -> Result<CurrencyAmount, DomainError> {
        let lock = self.dummy_balance.read();
        Ok(CurrencyAmount { cents: *lock })
    }

    async fn execute_transfer(
        &self,
        _source: AccountId,
        _destination: AccountId,
        amount: CurrencyAmount,
        outbox_event: String,
    ) -> Result<(), DomainError> {
        let mut lock = self.dummy_balance.write();
        if *lock < amount.cents {
            return Err(DomainError::InsufficientFunds {
                required: amount.cents,
                available: *lock,
            });
        }
        *lock -= amount.cents;
        info!(target: "audit_log", "Outbox record disimpan: {}", outbox_event);
        Ok(())
    }
}

// ==========================================
// 5. APPLICATION RUNNER
// ==========================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    // Wiring IoC via pure Rust composition
    let ledger_adapter = Arc::new(InMemoryLedgerAdapter::new(1_000_000));
    let service = TransferService::new(ledger_adapter.clone());

    let src = AccountId(101);
    let dst = AccountId(202);
    let amount = CurrencyAmount::new(250_000)?;

    service.transfer(src, dst, amount).await?;

    let final_balance = ledger_adapter.get_balance(src).await?;
    println!("Sisa saldo rekening sumber: {} cents", final_balance.cents);

    Ok(())
}
```

---

## 8. Real-World Case Study: FinTech Ultra-High Throughput Ledger Engine

### Konteks Kasus
Platform pembayaran multi-nasional memproses transaksi kartu debit dan transfer instan dengan beban puncak hingga **120.000 TPS** dengan SLA p99 **< 2.5 milidetik**. Pada platform berbasis Java terdahulu, terjadi degradasi performa setiap 15 menit akibat Stop-The-World GC (CMS / ZGC pause) dan contention pada dynamic reflection mapping (Jackson, Hibernate).

### Masalah Arsitektural
1. **GC Churn**: Pembuatan jutaan objek transfer sementara per detik menyebabkan thrashing CPU.
2. **Database Overload**: Transaksi ACID langsung ke RDBMS utama menyebabkan connection exhaustion dan lock table timeout.
3. **Double Spending**: Latensi distributed lock menyebabkan race condition saat verifikasi saldo.

### Solusi Arsitektur Menggunakan Rust
Arsitektur baru dibangun ulang dengan komponen berikut:
1. **Core Domain**: Mengadopsi **Hexagonal Architecture** murni dengan zero-copy serialization (`rkyv` & `serde_json`).
2. **Actor-Based In-Memory Sharding**: Akun dipartisi ke dalam 64 memory partition worker (berdasarkan `account_id % 64`). Setiap worker berjalan pada satu dedicated tokio thread (pinned CPU core via `core_affinity`) tanpa shared-lock antar worker. Worker memegang saldo akun di L3 Cache memory.
3. **LMAX Disruptor Pattern Ring-Buffer**: Digunakan `crossbeam-channel` dengan varian array bounded tanpa lock untuk komunikasi thread ultra-cepat (< 100ns per hop).
4. **Transactional Outbox Engine**: Event ditulis ke *Write-Ahead Log* (WAL) disk menggunakan `O_DIRECT` bypass page-cache OS, kemudian dipublikasikan asinkron ke Kafka.

### Hasil Metrik Produksi
- **Throughput**: Stabil di 145.000 TPS.
- **Latency p99**: Turun drastis dari 85ms (Java) ke **1.1ms (Rust)**.
- **Konsumsi Memori**: Menurun dari 32 GiB (JVM Heap) menjadi **340 MiB (Rust Resident Memory)** pada beban kerja yang sama.
- **Cloud Infrastructure Cost**: Pengurangan instance AWS dari 48 instance `c5.4xlarge` menjadi 4 instance `c6i.2xlarge`.

---

## 9. Trade-Offs

Setiap keputusan rekayasa sistem perangkat lunak memiliki konsekuensi. Berikut adalah matriks trade-off yang harus dihadapi saat membangun sistem enterprise dengan Rust:

| Pilihan Teknikal | Keuntungan (+) | Kerugian / Biaya (-) | Rekomendasi Kontekstual |
|---|---|---|---|
| **Static Dispatch (`impl Trait`)** | Zero runtime cost; inlining penuh oleh LLVM; optimasi SIMD. | *Binary bloat* (monomorphization code size bertambah); waktu kompilasi (*compile-time*) lebih lama. | Gunakan secara default pada hot-path transaksi domain utama. |
| **Dynamic Dispatch (`dyn Trait`)** | Waktu kompilasi cepat; binary lebih kecil; mempermudah dynamic plugin architecture. | Memerlukan vtable pointer chasing (~2 dereferensiasi pointer); mencegah inlining; alokasi heap (`Box<dyn Trait>`). | Gunakan pada boundary adapter yang jarang dieksekusi (misal: Dynamic Plugin Loader, CLI parser). |
| **Custom Allocator (`mimalloc`/`jemalloc`)** | Mencegah fragmentasi memori pada multi-threaded allocation berat; throughput meningkat hingga 20%. | Kompatibilitas cross-compilation (terutama Windows MSVC / Musl target) bisa memerlukan konfigurasi toolchain tambahan. | Wajib diaktifkan untuk HTTP microservices dan database-intensive engines di Linux container. |
| **Bounded vs Unbounded Channel** | **Bounded**: Mencegah OOM via *Backpressure* terukur. | Jika kapasitas salah estimasi, memicu thread stall atau client rejection (HTTP 429). | **Haram memakai Unbounded di produksi**. Gunakan selalu bounded queue dengan metrics monitoring. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memanggil Operasi Blocking di Dalam Async Runtime
```rust
// FATAL BUG: Menghentikan worker thread Tokio!
async fn process_file() {
    let data = std::fs::read_to_string("heavy_ledger.csv").unwrap(); // BLOCKING IO!
    // Worker thread tokio berhenti memproses task async lain selama IO disk berjalan.
}
```
**Perbaikan:**
Gunakan asynchronous API atau delegasikan ke blocking pool:
```rust
async fn process_file_correct() {
    // Pilihan A: Gunakan tokio async io
    let data = tokio::fs::read_to_string("heavy_ledger.csv").await.unwrap();

    // Pilihan B: Operasi CPU-bound/blocking berat didelegasikan ke thread pool khusus
    let parsed = tokio::task::spawn_blocking(|| {
        heavy_cpu_computation()
    }).await.unwrap();
}
```

### Mistake 2: Memegang `tokio::sync::MutexGuard` Melintasi Titik `.await` Secara Tidak Perlu
```rust
// ANTI-PATTERN: Menahan lock terlalu lama
async fn bad_lock_handling(mutex: Arc<tokio::sync::Mutex<State>>) {
    let mut guard = mutex.lock().await;
    guard.counter += 1;
    
    // Melakukan network request sambil memegang lock memicu lock starvation!
    external_http_call().await; 
}
```
**Perbaikan:**
Perkecil cakupan lock (*lock scope*) sesegera mungkin:
```rust
async fn good_lock_handling(mutex: Arc<tokio::sync::Mutex<State>>) {
    {
        let mut guard = mutex.lock().await;
        guard.counter += 1;
    } // Guard di-drop otomatis di sini! Lock dilepas sebelum network call.

    external_http_call().await;
}
```

### Mistake 3: Async Cancellation Hazards
Di Tokio, jika sebuah `Future` di-cancel (misalnya timeout via `tokio::time::timeout`), eksekusi future berhenti di titik `.await` terdekat, dan semua lokal variabel di-drop. Jika transaksi outbox Anda baru menulis setengah data sebelum titik `.await`, sistem Anda berada dalam status inkonsisten (*partial commit*).

---

## 11. Best Practices (Production Checklist)

- [ ] **Custom Memory Allocator**: Aktifkan `mimalloc` atau `jemallocator` di `main.rs`.
- [ ] **Linter Aggressiveness**: Aktifkan `#![deny(clippy::all, clippy::pedantic, clippy::nursery)]` pada level workspace crate.
- [ ] **Deny Panics in Production**: Gunakan `clippy::unwrap_used = "deny"` dan `clippy::expect_used = "deny"` untuk memaksa penggunaan penanganan error berbasis `Result<T, E>`.
- [ ] **Structured Observability**: Integrasikan `tracing` crate dengan OpenTelemetry layer, JSON formatter di environment produksi, serta forward `span-id` dan `trace-id`.
- [ ] **Graceful Shutdown**: Tangani `SIGINT` dan `SIGTERM` dengan `tokio::signal` dan gunakan `tokio_util::sync::CancellationToken` untuk memicu shutdown bersih pada background workers.
- [ ] **Bounded Everything**: Pastikan semua queue, HTTP connection pool, dan database pool memiliki limit tegas (*bounded capacity*).

---

## 12. Hands-on Practice

Buat dan simpan struktur modul ini pada repositori lokal Anda di folder: `hands-on/m02/`

### Langkah 1: Setup Workspace & Dependencies
Jalankan di terminal:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
cargo init --bin enterprise-engine
```

Ubah file `Cargo.toml`:
```toml
[package]
name = "enterprise-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.38", features = ["full"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json", "env-filter"] }
thiserror = "1.0"
async-trait = "0.1"
parking_lot = "0.12"
mimalloc = "0.1"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
strip = true
```

### Langkah 2: Inisialisasi Allocator Produksi & Entry Point
Edit `src/main.rs`:
```rust
use mimalloc::MiMalloc;

#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

mod domain;
mod ports;
mod adapters;
mod service;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("info,enterprise_engine=debug")
        .json()
        .init();

    tracing::info!("Enterprise Engine started with mimalloc allocator.");
}
```

### Langkah 3: Eksekusi Profiling & Verifikasi Release
Jalankan kompilasi teroptimasi:
```bash
cargo build --release
```
Periksa ukuran binary yang dihasilkan menggunakan utilitas `size` atau `ls -lh target/release/enterprise-engine`. Binary harus berukuran ringkas, teroptimasi, dan siap untuk deployment container scratch/distroless.

---

## 13. Exercises

### Level Easy
Ubah implementasi `CurrencyAmount` pada seksi 7.2 agar mampu memvalidasi mata uang (*ISO-4217 Currency Code*, misal "USD", "IDR"). Jika format mata uang tidak tepat 3 karakter alfabet kapital, tolak pada saat instansiasi menggunakan `DomainError::InvalidAmount`.

### Level Medium
Implementasikan sebuah In-Memory Rate Limiter Port menggunakan algoritma **Token Bucket** yang thread-safe. Gunakan `parking_lot::Mutex` dan `tokio::time::Instant`. Pasang Port ini ke dalam `TransferService` untuk menolak request jika source account melakukan lebih dari 5 request per detik.

### Level Hard
Buat implementasi **Transactional Outbox Processor** menggunakan background loop Tokio task (`tokio::spawn`). Task ini harus membaca slice in-memory outbox event setiap 200ms, mengirimkannya ke mock external dispatcher, dan jika sukses, menghapus event tersebut secara thread-safe tanpa memicu dead-lock dengan transaksi service transfer utama.

---

## 14. Real-World Challenge: Resilient Matching Engine (Fault-Tolerant Orderbook)

### Skenario Bisnis
Sebuah bursa kripto tier-1 merekrut Anda untuk merancang ulang Matching Engine spot trading mereka. Sistem lama sering mengalami inkonsistensi saldo saat terjadi crash mendadak di tengah matching transaksi.

### Spesifikasi Teknis yang Harus Dipenuhi
1. **Engine Core**: Gunakan *Type-State Pattern* untuk mengunci lifecycle order: `Submitted` -> `Validated` -> `PartiallyFilled` -> `FullyFilled` (atau `Cancelled`). Order yang sudah `Cancelled` secara matematis dilarang masuk ke fungsi matching.
2. **High-Performance Priority Queue**: Orderbook harus diimplementasikan menggunakan dua Binary Heap atau BTreeMap (`bids` descending, `asks` ascending) yang diproteksi menggunakan non-blocking data exchange atau atomic single-writer partition.
3. **Audit Trail & WAL**: Setiap order match harus menghasilkan pair `ExecutionEvent`. Event ini **harus** dipersistensikan ke local append-only log sebelum status perubahan saldo dikonfirmasi ke memori port adapter.
4. **Failure Injection**: Simulasikan skenario kegagalan fatal (misalnya: panic injection via `tokio::select!` timeout). Sistem harus memiliki mekanisme pemulihan (*crash recovery*) yang membaca ulang WAL dan merekonstruksi ulang state orderbook secara identik (*deterministic state replay*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)
1. **Mengapa *Type-State Pattern* lebih unggul daripada sekadar menyimpan enum status (misal: `status: OrderStatus`) di dalam struct entity?**
   - *Jawaban Singkat*: Type-State memvalidasi ketersediaan fungsi dan transisi status pada fase kompilasi (*compile-time*), sehingga method yang tidak valid untuk status tertentu tidak eksis di binary, mengeliminasi bug runtime pengecekan kondisi `if status == ...`.

2. **Apa yang dilakukan oleh Tokio Runtime saat terjadi "Work Stealing"?**
   - *Jawaban Singkat*: Ketika sebuah worker thread mendapati antrean lokalnya kosong, ia mencuri setengah task dari antrean lokal milik worker thread lain menggunakan operasi atomic lock-free.

3. **Mengapa penulisan `std::thread::sleep` dilarang keras di dalam fungsi `async` pada Tokio?**
   - *Jawaban Singkat*: Karena memblokir OS thread yang sedang dipinjam oleh worker runtime, mencegah task async lain yang berada dalam queue thread tersebut untuk dieksekusi.

4. **Kapan kita harus memilih Static Dispatch (`impl Trait`) dibanding Dynamic Dispatch (`dyn Trait`)?**
   - *Jawaban Singkat*: Static dispatch dipilih saat performa dan inlining fungsi sangat krusial di hot-path serta tipe adapter sudah diketahui pasti saat kompilasi.

5. **Apa fungsi utama dari crate `thiserror` dalam arsitektur enterprise Rust?**
   - *Jawaban Singkat*: Untuk mendefinisikan custom error domain internal yang strongly-typed dan ramah terhadap penanganan error terstruktur tanpa overhead runtime string-formatting dinamis.

---

### Bagian 2: Intermediate (Analisis Kasus Singkat)
1. **Bagaimana cara mencegah memory leak yang disebabkan oleh circular reference saat menggunakan `Arc<T>`?**
   - *Solusi Teknis*: Gunakan `std::sync::Weak<T>` untuk memecah siklus kepemilikan. `Weak` tidak menambah *strong reference count*, sehingga saat strong reference bernilai 0, memori akan tetap di-drop.

2. **Dua worker thread membaca dan menulis ke dua field integer `u64` yang berdekatan di dalam sebuah struct pada loop ketat. Keduanya mengalami degradasi performa drastis. Masalah apa yang terjadi dan bagaimana solusinya?**
   - *Solusi Teknis*: Masalah *False Sharing*. Kedua variabel berada di cache line 64-byte yang sama. Solusinya: Pisahkan kedua field tersebut menggunakan padding cache line (`#[repr(align(64))]` atau `crossbeam_utils::CachePadded`).

3. **Apa perbedaan mendasar antara `parking_lot::Mutex` dan `tokio::sync::Mutex`? Kapan waktu yang tepat menggunakan masing-masing tipe lock tersebut?**
   - *Solusi Teknis*: `parking_lot::Mutex` adalah thread-blocking spin/parking mutex untuk synchronous context (sangat cepat, footprint kecil). `tokio::sync::Mutex` bekerja secara asinkron dengan cara mem-parking Task Tokio tanpa memblokir thread OS. Gunakan `parking_lot` untuk proteksi data in-memory cepat tanpa melintasi titik `.await`, gunakan `tokio::sync::Mutex` HANYA jika lock harus dipertahankan melintasi await point.

4. **Dalam konteks database persistence dengan Rust, mengapa SQL injection secara default hampir mustahil terjadi saat menggunakan library modern seperti `sqlx`?**
   - *Solusi Teknis*: Karena query SQL divalidasi dan di-compile secara *prepared statement* bawaan, serta macro `sqlx::query!` melakukan validasi sintaks dan skema tipe langsung ke database saat waktu kompilasi (*compile-time query verification*).

5. **Apa implikasi menggunakan `panic = "abort"` pada release profile aplikasi Rust enterprise?**
   - *Solusi Teknis*: Menonaktifkan proses *stack unwinding* saat terjadi panic; binary langsung terminate seketika. Menghasilkan binary yang lebih kecil dan performa eksekusi lebih kencang, namun tidak memungkinkan penangkapan panic via `std::panic::catch_unwind`.

---

### Bagian 3: Production Scenarios

#### Kasus A: The Phantom Thread Starvation
**Skenario**: Layanan API order matching Anda mengalami lonjakan latency p99 dari 2ms ke 4500ms saat traffic naik. Metrik CPU menunjukkan hanya 1 core yang utilisasinya 100%, sedangkan core lainnya idle (utilisasi 3%). Worker threads tampak membeku bergantian.
- **Penyebab**: Terdapat task komputasi CPU intensif panjang (misalnya hashing cryptographic atau parsing JSON raksasa) yang berjalan langsung di thread Tokio tanpa melakukan yield, memonopoli scheduler thread dan mengabaikan task budget.
- **Langkah Remediasi**:
  1. Audit source code untuk menemukan kalkulasi CPU-bound berat.
  2. Bungkus eksekusi fungsi berat tersebut ke dalam `tokio::task::spawn_blocking(...)` agar dieksekusi di OS dedicated blocking pool.
  3. Sisipkan `tokio::task::yield_now().await` di dalam iterasi parsing loop yang besar untuk memberikan kesempatan task lain dieksekusi oleh Tokio scheduler.

#### Kasus B: The Silent Memory Bloat
**Skenario**: Container Rust Anda di Kubernetes di-kill secara berkala oleh Linux Kernel (OOMKilled - Exit Code 137). Metrik heap profiler menunjukkan bahwa alokasi object aplikasi sangat kecil (< 50MB), namun Linux `top` Resident Set Size (RSS) terus membesar hingga 2GB.
- **Penyebab**: Fragmentasi memori ekstrem yang disebabkan oleh default system allocator (`glibc malloc`) saat menghadapi throughput transaksi multi-threaded yang mengalokasikan dan mendealokasikan buffer berukuran variatif secara serempak.
- **Langkah Remediasi**:
  1. Ganti default allocator dengan `mimalloc` atau `jemalloc` yang memiliki arena multi-thread terisolasi dan sistem manajemen fragmentasi agresif.
  2. Implementasikan teknik *Buffer Reuse* menggunakan `bytes::BytesMut` untuk menghindari alokasi baru pada setiap request yang masuk.

#### Kasus C: Distributed Outbox Race Condition
**Skenario**: Sistem mencatat event transaksi outbox ganda ke Apache Kafka saat terjadi micro-network disconnection antara aplikasi dan message broker. Konsumen menerima duplikasi pesanan yang menyebabkan double dispatching barang gudang.
- **Penyebab**: Adapter Outbox Processor gagal memperbarui status event menjadi `PROCESSED` sebelum event berhasil dikirim, atau crash terjadi tepat setelah publish ke broker namun sebelum transaksi status di DB ter-commit.
- **Langkah Remediasi**:
  1. Terapkan prinsip **Idempotent Consumer** di hilir: setiap event outbox wajib menyertakan unique deterministic payload ID (UUIDv5/v7).
  2. Buat state transition pada tabel outbox: `PENDING` -> `IN_FLIGHT` (dengan lease timeout) -> `PUBLISHED`.
  3. Gunakan database update bersyarat (*optimistic locking with version check*) agar worker lain tidak mengambil event yang sama saat network timeout sedang berlangsung.

---

## 16. Summary
- **Arsitektur Enterprise Rust** menuntut pemanfaatan sistem tipe sebagai fondasi reliabilitas utama, menggantikan validasi runtime dengan pemeriksaan statis (*compile-time invariants*).
- **Hexagonal Architecture via Static Dispatch** memungkinkan decoupling total domain bisnis dari implementasi infrastruktur (DB, queue, protocol) tanpa membayar penalti performa virtual table dispatching.
- **Tokio Scheduler Performance** bergantung pada kebersihan async execution path: zero blocking calls, pembatasan ketat scope locking mutex, dan kesadaran terhadap task budget cooperativeness.
- **Ketahanan Sistem Produksi (Production Resilience)** diwujudkan melalui alokator memori generasi modern, handling eksplisit terhadap async cancellation hazards, penerapan backpressure bertingkat, dan arsitektur outbox event yang idempoten.