# Kurikulum Komprehensif Arsitektur & Rekayasa Sistem Ruby Core

Selamat datang di repositori kurikulum resmi penguasaan **Ruby Modern**. Silabus ini dirancang secara sistematis untuk mentransformasi rekayasawan perangkat lunak dari tingkat pemahaman sintaksis dasar menuju kaliber *Principal/Staff Engineer*. Materi berfokus secara mendalam pada arsitektur runtime MRI (CRuby), YARV bytecode execution, model memori, konkurensi tingkat rendah, metaprogramming tingkat lanjut, desain modular enterprise, hingga kompilasi Just-In-Time (YJIT).

---

## 1. Course Overview & Mindset

### Filosofi Inti: "Design for Programmer Happiness, Architect for Mechanical Sympathy"
Ruby didesain oleh Yukihiro Matsumoto (Matz) dengan premis utama: *memaksimalkan produktivitas dan kebahagiaan rekayasawan melalui abstraksi objek yang elegan*. Namun, pada skala enterprise dan sistem terdistribusi throughput tinggi, paradigma ini wajib diseimbangkan dengan *mechanical sympathy*—pemahaman presisi atas bagaimana interpreter MRI mengeksekusi instruksi di atas kernel, sistem berkas, dan memori fisik.

### Tiga Pilar Kompetensi Inti
1. **Runtime & Metamorphic Mastery**: Memahami bagaimana YARV (Yet Another Ruby VM) merepresentasikan objek (`RBasic`, `RObject`), bagaimana method dispatching bekerja melalui *ancestor chains* dan *inline caching*, serta bagaimana memanfaatkan metaprogramming tanpa mengorbankan performa eksekusi.
2. **True Concurrency & Resource Efficiency**: Menguasai batasan GVL (Global VM Lock), pemanfaatan Ractor untuk konkurensi paralel bebas *race-condition*, Async Fiber Scheduler untuk non-blocking I/O masif, serta manajemen memori berbasis Generational/Incremental Garbage Collector.
3. **Enterprise Architecture & Rigor**: Menerapkan Domain-Driven Design (DDD) dan Clean Architecture menggunakan ekosistem Ruby modern (seperti `dry-rb`, Sequel, dan ROM), static typing dengan Sorbet/RBS, serta profiling sistem menggunakan YJIT, Vernier, dan Stackprof.

---

## 2. Learning Roadmap

```text
Ruby Core & Systems Engineering
│
├── [BAB 01] Fondasi Runtime & Arsitektur Ruby Core (MRI/YARV)
│   ├── Modul 01: Anatomi YARV & Eksekusi Bytecode
│   ├── Modul 02: Sistem Tipe Dinamis & Mutabilitas Objek
│   └── Modul 03: Ruby Garbage Collection & Manajemen Memori
│
├── [BAB 02] Deep-Dive Object-Oriented Design & Metaprogramming
│   ├── Modul 01: Ruby Object Model & Ancestor Chain
│   ├── Modul 02: Metaprogramming & Runtime Introspection
│   └── Modul 03: Evaluasi Kode Dinamis & Binding
│
├── [BAB 03] Functional Paradigm & Collection Processing
│   ├── Modul 01: Closures: Blocks, Procs, & Lambdas
│   ├── Modul 02: Enumerable, Enumerator, & Lazy Evaluation
│   └── Modul 03: Pattern Matching & Destructuring Modern Ruby
│
├── [BAB 04] Resource Management & Low-Level I/O
│   ├── Modul 01: I/O Streams, Buffering, & File Descriptors
│   ├── Modul 02: Optimasi Alokasi Objek & Leak Detection
│   └── Modul 03: Fiber Scheduler & Coroutine Architecture
│
├── [BAB 05] Concurrency, Parallelism, & Multi-Threading
│   ├── Modul 01: GVL, Native Threads, & Synchronization
│   ├── Modul 02: Ractor Parallelism & Shareable Objects
│   └── Modul 03: Event-Driven I/O & Async Runtime
│
├── [BAB 06] Gem Development, Native Extensions, & Typing
│   ├── Modul 01: Gem Packaging & Bundler Internals
│   ├── Modul 02: C Native Extensions & FFI Integration
│   └── Modul 03: Static Typing dengan Sorbet & RBS
│
├── [BAB 07] Testing Rigor & Static Analysis
│   ├── Modul 01: RSpec Deep-Dive & Custom Matchers
│   ├── Modul 02: Mocking, Stubbing, & Contract Testing
│   └── Modul 03: RuboCop AST Analysis & Custom Cops
│
├── [BAB 08] Network Programming & Rack Architecture
│   ├── Modul 01: Low-Level TCP/UDP Socket Programming
│   ├── Modul 02: Rack Interface & Middleware Pipeline
│   └── Modul 03: Membangun Rack Web Server Berperforma Tinggi
│
├── [BAB 09] Enterprise Web Architecture
│   ├── Modul 01: Clean Architecture & Domain-Driven Design (DDD)
│   ├── Modul 02: Decoupled Data Persistence: ROM & Sequel
│   └── Modul 03: dry-rb Ecosystem, Monads, & Railway Programming
│
└── [BAB 10] Performance Tuning & Production Engineering
    ├── Modul 01: Code Profiling, Benchmarking, & Allocation Tracking
    ├── Modul 02: YJIT Internals & JIT Compilation Heuristics
    └── Modul 03: Production Observability, Tracing, & Core Dumps
```

---

## 3. Navigasi Detail Bab

### [BAB 01: Fondasi Runtime & Arsitektur Ruby Core (MRI/YARV)](./bab-01-fondasi-runtime-dan-arsitektur-ruby-core/)
Eksplorasi mendalam mengenai internal interpreter CRuby/MRI, siklus hidup kompilasi kode sumber menjadi bytecode YARV, struktur representasi data internal di level C, serta mekanisme alokasi heap dan Garbage Collection.
* [Modul 01: Anatomi YARV & Eksekusi Bytecode](./bab-01-fondasi-runtime-dan-arsitektur-ruby-core/modul-01-anatomi-yarv-dan-eksekusi-bytecode.md)
* [Modul 02: Sistem Tipe Dinamis & Mutabilitas Objek](./bab-01-fondasi-runtime-dan-arsitektur-ruby-core/modul-02-sistem-tipe-dinamis-dan-mutabilitas-objek.md)
* [Modul 03: Ruby Garbage Collection & Manajemen Memori](./bab-01-fondasi-runtime-dan-arsitektur-ruby-core/modul-03-ruby-garbage-collection-dan-memori.md)

### [BAB 02: Deep-Dive Object-Oriented Design & Metaprogramming](./bab-02-deep-dive-ood-dan-metaprogramming/)
Pembongkaran sistem objek Ruby secara fundamental: bagaimana class sebenarnya hanyalah objek, navigasi singleton class (eigenclass), dynamic method definition, dynamic dispatching, serta manipulasi scope bindings.
* [Modul 01: Ruby Object Model & Ancestor Chain](./bab-02-deep-dive-ood-dan-metaprogramming/modul-01-ruby-object-model-dan-ancestor-chain.md)
* [Modul 02: Metaprogramming & Runtime Introspection](./bab-02-deep-dive-ood-dan-metaprogramming/modul-02-metaprogramming-dan-runtime-introspection.md)
* [Modul 03: Evaluasi Kode Dinamis & Binding](./bab-02-deep-dive-ood-dan-metaprogramming/modul-03-evaluasi-kode-dinamis-dan-binding.md)

### [BAB 03: Functional Paradigm & Collection Processing](./bab-03-functional-ruby-dan-collection-processing/)
Penguasaan kapabilitas fungsional Ruby: perbedaan mendasar antar bentuk *closure*, pemrosesan koleksi data bervolume besar secara efisien via iterator dan generator, serta teknik pattern matching struktural modern.
* [Modul 01: Closures: Blocks, Procs, & Lambdas](./bab-03-functional-ruby-dan-collection-processing/modul-01-closures-blocks-procs-lambdas.md)
* [Modul 02: Enumerable, Enumerator, & Lazy Evaluation](./bab-03-functional-ruby-dan-collection-processing/modul-02-enumerable-enumerator-dan-lazy-evaluation.md)
* [Modul 03: Pattern Matching & Destructuring Modern Ruby](./bab-03-functional-ruby-dan-collection-processing/modul-03-pattern-matching-dan-destructuring.md)

### [BAB 04: Resource Management & Low-Level I/O](./bab-04-resource-management-dan-low-level-io/)
Interaksi Ruby dengan kernel sistem operasi: penanganan descriptor berkas, buffering stream, optimasi memori bebas leak pada level OS, dan pemanfaatan Fiber primitif serta Fiber Scheduler.
* [Modul 01: I/O Streams, Buffering, & File Descriptors](./bab-04-resource-management-dan-low-level-io/modul-01-io-stream-buffering-dan-file-descriptors.md)
* [Modul 02: Optimasi Alokasi Objek & Leak Detection](./bab-04-resource-management-dan-low-level-io/modul-02-optimasi-alokasi-objek-dan-leak-detection.md)
* [Modul 03: Fiber Scheduler & Coroutine Architecture](./bab-04-resource-management-dan-low-level-io/modul-03-fiber-scheduler-dan-coroutine-architecture.md)

### [BAB 05: Concurrency, Parallelism, & Multi-Threading](./bab-05-concurrency-parallelism-dan-multi-threading/)
Arsitektur penanganan beban konkuren: mitigasi Global VM Lock (GVL), sinkronisasi thread primitif, konkurensi paralel tanpa memori bersama via Ractor, dan I/O event-loop asinkron berbasis async gem.
* [Modul 01: GVL, Native Threads, & Synchronization](./bab-05-concurrency-parallelism-dan-multi-threading/modul-01-gvl-native-threads-dan-synchronization.md)
* [Modul 02: Ractor Parallelism & Shareable Objects](./bab-05-concurrency-parallelism-dan-multi-threading/modul-02-ractor-parallelism-dan-shareable-objects.md)
* [Modul 03: Event-Driven I/O & Async Runtime](./bab-05-concurrency-parallelism-dan-multi-threading/modul-03-event-driven-io-dan-async-runtime.md)

### [BAB 06: Gem Development, Native Extensions, & Typing](./bab-06-gem-development-dan-tooling/)
Standar rekayasa ekosistem distribusi package: pembuatan Gem berstandar industri, integrasi library C via Ruby C API dan FFI, serta penerapan static typing dengan Sorbet dan RBS.
* [Modul 01: Gem Packaging & Bundler Internals](./bab-06-gem-development-dan-tooling/modul-01-gem-packaging-dan-bundler-internals.md)
* [Modul 02: C Native Extensions & FFI Integration](./bab-06-gem-development-dan-tooling/modul-02-c-native-extensions-dan-ffi.md)
* [Modul 03: Static Typing dengan Sorbet & RBS](./bab-06-gem-development-dan-tooling/modul-03-static-typing-sorbet-dan-rbs.md)

### [BAB 07: Testing Rigor & Static Analysis](./bab-07-testing-rigor-dan-static-analysis/)
Penerapan metodologi pengujian perangkat lunak tingkat lanjut: arsitektur internal RSpec, isolasi dependensi melalui test doubles & contract tests, serta analisis Abstract Syntax Tree (AST) untuk penegakan static rule kustom.
* [Modul 01: RSpec Deep-Dive & Custom Matchers](./bab-07-testing-rigor-dan-static-analysis/modul-01-rspec-deep-dive-dan-custom-matchers.md)
* [Modul 02: Mocking, Stubbing, & Contract Testing](./bab-07-testing-rigor-dan-static-analysis/modul-02-mocking-stubbing-dan-contract-testing.md)
* [Modul 03: RuboCop AST Analysis & Custom Cops](./bab-07-testing-rigor-dan-static-analysis/modul-03-rubocop-ast-analysis-dan-custom-cops.md)

### [BAB 08: Network Programming & Rack Architecture](./bab-08-network-programming-dan-rack-architecture/)
Pemahaman fondasi komunikasi web: socket programming dari lapisan TCP mentah, arsitektur antarmuka Rack yang mendasari ekosistem web Ruby, dan implementasi web server konkurensi tinggi dari nol.
* [Modul 01: Low-Level TCP/UDP Socket Programming](./bab-08-network-programming-dan-rack-architecture/modul-01-low-level-socket-programming.md)
* [Modul 02: Rack Interface & Middleware Pipeline](./bab-08-network-programming-dan-rack-architecture/modul-02-rack-interface-dan-middleware-architecture.md)
* [Modul 03: Membangun Rack Web Server Berperforma Tinggi](./bab-08-network-programming-dan-rack-architecture/modul-03-membangun-rack-web-server-berperforma-tinggi.md)

### [BAB 09: Enterprise Web Architecture](./bab-09-enterprise-web-architecture-ruby/)
Membangun aplikasi web Ruby skala besar di luar paradigma monolit tradisional: pemisahan domain murni (Domain-Driven Design), pola persistensi decoupling via Sequel dan ROM, serta arsitektur fungsional terarah menggunakan `dry-rb`.
* [Modul 01: Clean Architecture & Domain-Driven Design (DDD)](./bab-09-enterprise-web-architecture-ruby/modul-01-clean-architecture-dan-ddd.md)
* [Modul 02: Decoupled Data Persistence: ROM & Sequel](./bab-09-enterprise-web-architecture-ruby/modul-02-decoupled-data-persistence-rom-dan-sequel.md)
* [Modul 03: dry-rb Ecosystem, Monads, & Railway Programming](./bab-09-enterprise-web-architecture-ruby/modul-03-dry-rb-monads-dan-service-layers.md)

### [BAB 10: Performance Tuning & Production Engineering](./bab-10-performance-tuning-dan-production-engineering/)
Metodologi optimasi performa dan stabilitas produksi: profiling alokasi CPU dan memori, penyetelan heuristik kompilasi YJIT, instrumentasi OpenTelemetry, dan inspeksi heap dump pada crash sistem.
* [Modul 01: Code Profiling, Benchmarking, & Allocation Tracking](./bab-10-performance-tuning-dan-production-engineering/modul-01-code-profiling-dan-benchmarking.md)
* [Modul 02: YJIT Internals & JIT Compilation Heuristics](./bab-10-performance-tuning-dan-production-engineering/modul-02-yjit-internals-dan-compilation-heuristics.md)
* [Modul 03: Production Observability, Tracing, & Core Dumps](./bab-10-performance-tuning-dan-production-engineering/modul-03-observability-tracing-dan-heap-dumps.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title: "AetherStream: High-Throughput Distributed Event Log & Stream Processing Engine"

#### 1. Deskripsi Sistem
Peserta wajib merancang dan mengimplementasikan **AetherStream**, sebuah mesin pemrosesan event stream terdistribusi *in-memory* yang persisten ke disk (terinspirasi oleh Apache Kafka dan Redis Streams), dibangun secara mandiri menggunakan **Ruby 3.3+ murni** tanpa framework web *off-the-shelf* (tanpa Rails/Sinatra).

#### 2. Arsitektur Inti & Spesifikasi Teknis
* **Networking & Ingestion Layer**: 
  * Server TCP non-blocking berbasis *Async Fiber Scheduler* yang mampu menangani minimal 20.000 persistent connection secara simultan.
  * Parser protokol biner kustom menggunakan bitmasking dan unpack packing Ruby.
* **Storage & Memory Engine**:
  * Segmented Append-Only Commit Log dengan integrasi *C-Extension* via Ruby FFI untuk direct kernel I/O (`io_uring` atau zero-copy `sendfile`).
  * Indexing berbasis Sparse In-Memory Index (Memory Footprint < 100MB per 1M event).
* **Parallel Execution Layer**:
  * Pipeline transformasi event (filtering, map-reduce aggregations) dieksekusi secara paralel murni menggunakan **Ractors** tanpa terkendala GVL.
* **Domain & Type Safety**:
  * Seluruh domain logic ditulis mengikuti prinsip *Clean Architecture* dan *Railway-Oriented Programming* (`dry-monads`).
  * Strict Type checking diberlakukan 100% menggunakan **Sorbet** (`# typed: strict`) atau **RBS/Steep**.
* **Observability & Runtime Optimization**:
  * Pematangan YJIT (verifikasi rasio kompilasi instruksi via `RubyVM::YJIT.runtime_stats`).
  * Instrumentasi metrik native via OpenTelemetry SDK dan zero-allocation request tracing.

#### 3. Kriteria Penerimaan (Acceptance Criteria)
1. **Throughput Benchmark**: Menghasilkan throughput minimal 15.000 events/sec write rate pada single machine 4-core dengan latensi p99 < 5ms.
2. **Crash Resilience**: Integritas data terverifikasi 100% (zero data loss) setelah proses menerima sinyal `SIGKILL` saat penulisan intensif berlangsung.
3. **Memory Profile**: Tidak ditemukan memory leak selama soak-test 2 jam (divalidasi dengan `MemoryProfiler` dan `GC.stat`).
4. **Code Rigor**: Cakupan pengujian unit dan integrasi minimal 90% via RSpec, dengan analisis AST kustom via RuboCop cop untuk mencegah penggunaan metode yang memicu alokasi memori berlebih (`String#+`, dynamic closures pada hot paths).