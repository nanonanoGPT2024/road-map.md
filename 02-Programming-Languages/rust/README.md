# Kurikulum Rekayasa Sistem Rust (Rust Systems Engineering)

Selamat datang di repositori resmi kurikulum **Mastery Rekayasa Sistem Rust**. Dokumen ini dirancang sebagai silabus komprehensif, berbasis industri, dan berorientasi pada pembangunan sistem performa tinggi (*low-latency, zero-cost abstractions, memory-safe*).

---

## 1. Course Overview & Mindset

Rust bukan sekadar bahasa pemrograman alternatif; Rust adalah pergeseran paradigma dalam rekayasa perangkat lunak sistem. Berbeda dengan bahasa yang mengandalkan *Garbage Collector* (Go, Java) atau manajemen memori manual penuh risiko (C, C++), Rust memaksakan jaminan keamanan memori dan bebas dari *data race* langsung pada tahap kompilasi (*compile-time*) melalui sistem **Ownership, Borrowing, dan Lifetimes**.

### Mindset Rekayasa yang Ditanamkan:
* **Zero-Cost Abstractions**: Abstraksi tingkat tinggi tidak boleh menimbulkan *overhead* performa saat *runtime*. Kode yang Anda tulis harus dikompilasi menjadi instruksi mesin yang seefisien kode C murni.
* **Mechanical Sympathy**: Memahami bagaimana perangkat keras (cache line, layout memori, stack vs heap, SIMD) berinteraksi langsung dengan kode Rust Anda.
* **Fearless Concurrency**: Mengubah konkurensi dari mimpi buruk *runtime debugging* menjadi kepastian matematis via sistem tipe *compile-time* (`Send` dan `Sync`).
* **Pragmatic Correctness**: Menghilangkan seluruh kelas bug memori (*use-after-free*, *double-free*, *null pointer dereference*) tanpa mengorbankan kendali langsung atas alokasi sumber daya.

---

## 2. Learning Roadmap

Berikut adalah jalur instruksional 10 Bab yang terstruktur secara berurutan:

```text
rust-systems-curriculum/
├── Bab 01: Fondasi Bahasa & Sistem Kepemilikan (Ownership & Memory Model)
│   ├── Modul 01: Toolchain, Cargo, & Memory Primitives
│   └── Modul 02: Ownership, Borrowing, & Reference Semantics
├── Bab 02: Tipe Data Maju, Polimorfisme, & Abstraksi Nol-Biaya
│   ├── Modul 01: Structs, Enums, & Pattern Matching Aljabar
│   ├── Modul 02: Traits, Generics, & Static Dispatch
│   └── Modul 03: Trait Objects & Dynamic Dispatch (vtable)
├── Bab 03: Lifetimes Lanjut & Smart Pointers
│   ├── Modul 01: Lifetime Elision, Subtyping, & HRTB
│   ├── Modul 02: Smart Pointers Eksplisit (Box, Rc, Arc)
│   └── Modul 03: Interior Mutability Pattern (Cell, RefCell, Mutex)
├── Bab 04: Penanganan Galat & Sistem I/O Idiomatik
│   ├── Modul 01: Error Handling Produksi (Result, Option, thiserror, anyhow)
│   └── Modul 02: Zero-Copy I/O, Buffer, & Filesystem Streaming
├── Bab 05: Konkurensi Tanpa Rasa Takut (Fearless Concurrency)
│   ├── Modul 01: Thread Spawning, Move Closures, Send & Sync
│   ├── Modul 02: Message Passing Concurrency (MPSC & Crossbeam)
│   └── Modul 03: Shared State, Atomics, & Lock-Free Primitives
├── Bab 06: Asynchronous Programming & Tokio Runtime
│   ├── Modul 01: Under the Hood: Futures, Wakers, & State Machine
│   ├── Modul 02: Runtime Tokio, Async I/O, & Task Scheduling
│   └── Modul 03: Pinning Semantics (Pin<&mut T>) & Async Streams
├── Bab 07: Metaprogramming & Macro System
│   ├── Modul 01: Declarative Macros (macro_rules!)
│   └── Modul 02: Procedural Macros (Custom Derive, Attribute, Function-like)
├── Bab 08: Unsafe Rust & Foreign Function Interface (FFI)
│   ├── Modul 01: Invariant Unsafe: Raw Pointers, Dereferencing, & UB
│   └── Modul 02: C-ABI Integration, Bindgen, & Memory Layout ABI
├── Bab 09: Pengujian Komprehensif, Profiling, & Optimasi
│   ├── Modul 01: Unit, Integration, Benchmark (Criterion), & Fuzzing
│   └── Modul 02: Memory Profiling, CPU Flamegraphs, & Custom Allocators
└── Bab 10: Arsitektur Perusahaan & Implementasi Capstone
    ├── Modul 01: Cargo Workspaces, Lints Deny/Forbid, & CI/CD Pipeline
    └── Modul 02: Produksi Observability: Tracing, Metrics, & Production Packaging
```

---

## 3. Navigasi Detail Bab

### [Bab 01: Fondasi Bahasa & Sistem Kepemilikan (Ownership & Memory Model)](./01-fondasi-dan-ownership)
Membedah arsitektur internal memori komputer (Stack vs. Heap), mekanisme kompilasi LLVM via `rustc`, dan aturan mutlak Ownership yang menjadi inti kompilasi Rust.
* [Modul 01: Toolchain, Cargo, & Memory Primitives](./01-fondasi-dan-ownership/01-toolchain-dan-primitif-memori.md)
* [Modul 02: Ownership, Borrowing, & Reference Semantics](./01-fondasi-dan-ownership/02-ownership-dan-borrowing.md)

### [Bab 02: Tipe Data Maju, Polimorfisme, & Abstraksi Nol-Biaya](./02-tipe-data-dan-abstraksi)
Membangun tipe data aljabar (*Algebraic Data Types*), pemanfaatan *monomorphization* untuk *zero-cost abstractions*, serta perbandingan mekanik antara *static dispatch* dan *dynamic dispatch*.
* [Modul 01: Structs, Enums, & Pattern Matching Aljabar](./02-tipe-data-dan-abstraksi/01-struct-enum-pattern-matching.md)
* [Modul 02: Traits, Generics, & Static Dispatch](./02-tipe-data-dan-abstraksi/02-traits-dan-generics.md)
* [Modul 03: Trait Objects & Dynamic Dispatch (vtable)](./02-tipe-data-dan-abstraksi/03-trait-objects-dan-vtable.md)

### [Bab 03: Lifetimes Lanjut & Smart Pointers](./03-lifetimes-dan-smart-pointers)
Menganalisis siklus hidup referensi secara formal, mengatasi konflik borrow checker kompleks, dan mengeksplorasi manajemen memori berbasis pointer pintar (*smart pointers*) serta *interior mutability*.
* [Modul 01: Lifetime Elision, Subtyping, & HRTB](./03-lifetimes-dan-smart-pointers/01-advanced-lifetimes-hrtb.md)
* [Modul 02: Smart Pointers Eksplisit (Box, Rc, Arc)](./03-lifetimes-dan-smart-pointers/02-smart-pointers.md)
* [Modul 03: Interior Mutability Pattern (Cell, RefCell, Mutex)](./03-lifetimes-dan-smart-pointers/03-interior-mutability.md)

### [Bab 04: Penanganan Galat & Sistem I/O Idiomatik](./04-error-handling-dan-io)
Menerapkan penanganan galat deterministik berbasis `Result<T, E>` tanpa pengecualian (*exceptions*), strategi pemetaan galat domain tingkat enterprise, dan streaming data berkecepatan tinggi.
* [Modul 01: Error Handling Produksi (Result, Option, thiserror, anyhow)](./04-error-handling-dan-io/01-robust-error-handling.md)
* [Modul 02: Zero-Copy I/O, Buffer, & Filesystem Streaming](./04-error-handling-dan-io/02-io-buffering-streaming.md)

### [Bab 05: Konkurensi Tanpa Rasa Takut (Fearless Concurrency)](./05-fearless-concurrency)
Mempelajari model eksekusi paralel Rust, jaminan keselamatan thread via marker trait `Send` & `Sync`, komunikasi antar thread, dan sinkronisasi tingkat rendah (*atomic instructions*).
* [Modul 01: Thread Spawning, Move Closures, Send & Sync](./05-fearless-concurrency/01-threads-dan-markers.md)
* [Modul 02: Message Passing Concurrency (MPSC & Crossbeam)](./05-fearless-concurrency/02-message-passing.md)
* [Modul 03: Shared State, Atomics, & Lock-Free Primitives](./05-fearless-concurrency/03-shared-state-dan-atomics.md)

### [Bab 06: Asynchronous Programming & Tokio Runtime](./06-async-dan-tokio)
Dekonstruksi cara kerja *cooperative multitasking*, kompilasi *state machine* dari ekspresi `async`, alokasi `Pin`, dan penerapan runtime `tokio` untuk menangani ratusan ribu koneksi simultan.
* [Modul 01: Under the Hood: Futures, Wakers, & State Machine](./06-async-dan-tokio/01-futures-dan-wakers.md)
* [Modul 02: Runtime Tokio, Async I/O, & Task Scheduling](./06-async-dan-tokio/02-tokio-runtime-internals.md)
* [Modul 03: Pinning Semantics (Pin<&mut T>) & Async Streams](./06-async-dan-tokio/03-pinning-dan-streams.md)

### [Bab 07: Metaprogramming & Macro System](./07-metaprogramming-macros)
Otomasi boilerplate dan ekspansi sintaksis melalui macro deklaratif serta pembuatan *procedural macros* berbasis *Abstract Syntax Tree* (AST) dengan `syn` dan `quote`.
* [Modul 01: Declarative Macros (macro_rules!)](./07-metaprogramming-macros/01-declarative-macros.md)
* [Modul 02: Procedural Macros (Custom Derive, Attribute, Function-like)](./07-metaprogramming-macros/02-procedural-macros.md)

### [Bab 08: Unsafe Rust & Foreign Function Interface (FFI)](./08-unsafe-dan-ffi)
Mempelajari batas-batas kontrak keselamatan Rust (*undefined behavior*, aliasing rules), manipulasi pointer mentah (*raw pointers*), serta integrasi dua arah dengan pustaka C/C++.
* [Modul 01: Invariant Unsafe: Raw Pointers, Dereferencing, & UB](./08-unsafe-dan-ffi/01-unsafe-invariants.md)
* [Modul 02: C-ABI Integration, Bindgen, & Memory Layout ABI](./08-unsafe-dan-ffi/02-ffi-dan-c-abi.md)

### [Bab 09: Pengujian Komprehensif, Profiling, & Optimasi](./09-testing-profiling-optimasi)
Standar verifikasi perangkat lunak sistem melalui unit/integration testing terisolasi, microbenchmarking statistik, *fuzz testing*, dan profiling alokasi memori serta siklus CPU.
* [Modul 01: Unit, Integration, Benchmark (Criterion), & Fuzzing](./09-testing-profiling-optimasi/01-testing-dan-fuzzing.md)
* [Modul 02: Memory Profiling, CPU Flamegraphs, & Custom Allocators](./09-testing-profiling-optimasi/02-profiling-dan-allocators.md)

### [Bab 10: Arsitektur Perusahaan & Implementasi Capstone](./10-arsitektur-dan-capstone)
Konsolidasi seluruh konsep ke dalam tata kelola multi-crate workspace produksi, audit lisensi dan kerentanan dependensi, instrumentasi telemetri (*distributed tracing*), serta spesifikasi proyek akhir.
* [Modul 01: Cargo Workspaces, Lints Deny/Forbid, & CI/CD Pipeline](./10-arsitektur-dan-capstone/01-workspaces-dan-ci.md)
* [Modul 02: Produksi Observability: Tracing, Metrics, & Production Packaging](./10-arsitektur-dan-capstone/02-observability-dan-packaging.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**"AetherKV: Distributed, High-Throughput, LSM-Tree Storage Engine with Raft Consensus & Async Network Layer"**

### Gambaran Umum
Peserta diwajibkan merancang dan membangun sistem penyimpanan persisten terdistribusi (*distributed key-value store*) dari nol, menggabungkan seluruh konsep kepemilikan memori, konkurensi tingkat lanjut, I/O asinkron, dan antarmuka C-FFI.

### Persyaratan Arsitektural & Teknis:

1. **Storage Core (Log-Structured Merge-Tree)**:
   * **MemTable**: Struktur data in-memory konkuren berbasis *SkipList* atau *Concurrent SkipList* bebas *lock* kasar (*fine-grained locking* atau CAS operations).
   * **Write-Ahead Logging (WAL)**: Mekanisme durabilitas pemulihan crash dengan *zero-copy serialization* (`rkyv` atau `bincode`).
   * **SSTable & Compaction**: Penyimpanan file immutable terurut pada disk dengan integrasi *Bloom Filter* untuk meminimalkan *read amplification*, dilengkapi *background compaction task* asinkron.

2. **Network Engine (Tokio Async Layer)**:
   * Implementasi protokol wire berbasis biner kustom menggunakan *custom frame codec*.
   * Menggunakan runtime `tokio` multi-threaded yang mampu menangani koneksi konkuren dengan throughput tinggi (> 100k QPS).

3. **Consensus & Replikasi (Raft Protocol Engine)**:
   * Menerapkan sub-modul konsensus Raft (Leader Election, Log Replication, Heartbeat) menggunakan abstraksi saluran *Actor Model* berbasis `tokio::sync::mpsc`.

4. **FFI Bridge**:
   * Menyediakan *C Dynamic/Static Library* (`cdylib` / `staticlib`) yang membungkus client AetherKV.
   * Kode C header (`aetherkv.h`) yang kompatibel dengan ABI C murni untuk konsumsi oleh runtime bahasa lain (C, Python, atau Node.js).

5. **Observability & Reliability Standards**:
   * Seluruh sistem harus diinstrumentasikan menggunakan `tracing` crate dengan integrasi format OpenTelemetry/Jaeger.
   * Nol toleransi terhadap *data race*, kebocoran alokasi tak terduga (*memory leak*), atau *undefined behavior* pada modul Unsafe (wajib lolos sanitasi `cargo miri` dan *fuzz testing* minimum 1 jam tanpa crash).
   * Minimum cakupan unit test 80% dan menyertakan laporan benchmark `criterion` performa baca/tulis terhadap ukuran payload yang bervariasi.