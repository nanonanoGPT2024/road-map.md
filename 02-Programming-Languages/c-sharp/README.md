# Kurikulum Komprehensif Rekayasa Perangkat Lunak: C# & .NET Runtime Modern

---

## 1. Course Overview & Mindset

### Gambaran Umum
C# bukan sekadar bahasa pemrograman berbasis objek biasa; ia adalah bahasa berkinerja tinggi (*high-performance*), memiliki *type system* ekspresif dan ketat, serta berjalan di atas ekosistem runtime yang matang: Common Language Runtime (CLR) dan .NET modern (versi 8+). Kurikulum ini dirancang untuk melatih para pengembang perangkat lunak menjadi **Enterprise-Grade C# & .NET Systems Engineers**. 

Fokus kurikulum ini mencakup seluruh spektrum: mulai dari manipulasi memori tingkat rendah (*low-level memory layout*, alokasi nol dengan `Span<T>`, manipulasi pointer terkontrol), internal asinkron (*state machine execution*), pemrograman fungsional mutakhir, *source generators*, arsitektur terdistribusi *cloud-native*, hingga orkestrasi transaksi *high-throughput*.

### Rekayasa Pola Pikir (Mindset Engineering)
1. **Mechanical Sympathy:** Pahami bagaimana Common Intermediate Language (CIL/IL) diterjemahkan oleh RyuJIT menjadi instruksi mesin, bagaimana cache CPU berinteraksi dengan layout struct, dan kapan Garbage Collector (GC) generasi 0, 1, atau 2 terpicu.
2. **Performance by Default (Zero-Allocation Paradigm):** Mengabaikan alokasi memori berlebih adalah hutang teknis fatal dalam sistem skala besar. Manfaatkan *value types*, pooling memori, dan semantik referensi secara terukur.
3. **Domain-Driven & Type Safety:** Manfaatkan *rich type system* C# (records, pattern matching, discriminated unions pattern, strict immutability) untuk memvalidasi domain rule di waktu kompilasi (*compile-time correctness*), bukan di waktu runtime.
4. **Resilience & Production Readiness:** Arsitektur backend enterprise dibangun dengan asumsi jaringan akan gagal, konkurensi akan mengalami *race conditions*, dan beban traffic akan melonjak sewaktu-waktu. Observabilitas, fault tolerance, dan isolasi kegagalan adalah syarat wajib implementasi.

---

## 2. Learning Roadmap

```plaintext
C# Modern & .NET Runtime Architecture
├── [BAB 01] Fondasi Arsitektur .NET & CLR Internals
│   ├── Eksekusi CIL, JIT Compilation, & Assembly Loading
│   └── Memory Layout: Stack, Heap, Value Types vs Reference Types
├── [BAB 02] Modern Type System & OOP Kontemporer
│   ├── Semantik Immutability: Records & ReadOnly Structs
│   ├── Pattern Matching & Exhaustiveness Checking
│   └── Advanced Generics, Variance (Co/Contravariance) & Type Constraints
├── [BAB 03] Functional C#, Delegasi & LINQ Internals
│   ├── Delegates, Anonymous Methods, Closures & Memory Leaks
│   ├── LINQ Execution Pipeline: Deferred Execution & Custom Iterators
│   └── Expression Trees & Dynamic Query Compilation
├── [BAB 04] Manajemen Memori, GC & High-Performance C#
│   ├── Garbage Collector Internals: Segments, Generations & LOH/POH
│   ├── Zero-Allocation: Span<T>, Memory<T>, ReadOnlySpan<T> & ref struct
│   └── Memory Pooling, ArrayPool<T>, Unsafe Code & Interop P/Invoke
├── [BAB 05] Asynchronous, Concurrency & Multithreading Internals
│   ├── Deep-Dive async/await: Roslyn State Machine & SynchronizationContext
│   ├── Task Parallel Library (TPL), PLINQ, & Lock-Free Primitives
│   └── System.Threading.Channels & Reactive Producer-Consumer Pipelines
├── [BAB 06] Metaprogramming, Reflection & Roslyn Source Generators
│   ├── Reflection Internals, Performance Cost, & System.Reflection.Emit
│   └── Compile-Time Metaprogramming menggunakan Roslyn Source Generators
├── [BAB 07] Arsitektur Enterprise & Clean Architecture
│   ├── Clean Architecture, Domain-Driven Design (DDD) & CQRS Pattern
│   ├── Dependency Injection Internals: Service Lifetimes & Scopes
│   └── Configuration System, Options Validation, & Custom Middlewares
├── [BAB 08] Data Access & High-Performance Persistence
│   ├── EF Core Internals: Change Tracker, Query Pipeline & Interceptors
│   ├── Micro-ORM Dapper, Raw SQL, & High-Speed Batch Operations
│   └── Distributed Transactions, Unit of Work, & Concurrency Control
├── [BAB 09] Resiliency, Observability & Enterprise Security
│   ├── Resilience Engineering: Polly (Retry, Circuit Breaker, Bulkhead)
│   ├── Observability Terpadu: OpenTelemetry, Metrics, Logs, & Tracing
│   └── Enkripsi, Data Protection API, & Zero-Trust Auth (OAuth2/OIDC)
└── [BAB 10] Cloud-Native, High-Throughput & Distributed Systems
    ├── gRPC Services, Protobuf, & HTTP/3 High-Performance RPC
    ├── Event-Driven Microservices via MassTransit & Kafka/RabbitMQ
    └── Native AOT Compilation, Trim Safety & Minimal Containerization
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Arsitektur .NET & CLR Internals](./01-fondasi-arsitektur-dotnet-clr/README.md)
*Memahami arsitektur eksekusi kode C# dari teks sumber hingga instruksi CPU native, serta model memori mendasar.*
- [Modul 01: Eksekusi CIL, RyuJIT, dan Mekanisme Assembly Loading](./01-fondasi-arsitektur-dotnet-clr/01-eksekusi-cil-dan-ryujit.md)
- [Modul 02: Layout Memori: Stack, Managed Heap, Value Types, dan Reference Types](./01-fondasi-arsitektur-dotnet-clr/02-layout-memori-stack-heap.md)
- [Modul 03: Type Safety, Boxing/Unboxing, dan Metrik Biaya Komputasi](./01-fondasi-arsitektur-dotnet-clr/03-boxing-unboxing-performance.md)

### [Bab 02: Modern Type System & OOP Kontemporer](./02-modern-type-system-oop/README.md)
*Menguasai sistem tipe C# modern untuk merancang arsitektur kode yang tangguh, aman, dan deklaratif.*
- [Modul 01: Rekayasa Tipe Data: Class, Struct, Records, dan Primary Constructors](./02-modern-type-system-oop/01-records-dan-immutability.md)
- [Modul 02: Advanced Pattern Matching, Switch Expressions, dan Exhaustiveness](./02-modern-type-system-oop/02-advanced-pattern-matching.md)
- [Modul 03: Generic Type Constraints, Covariance (`out`), dan Contravariance (`in`)](./02-modern-type-system-oop/03-generics-dan-variance.md)

### [Bab 03: Functional C#, Delegasi & LINQ Internals](./03-functional-linq-internals/README.md)
*Membongkar cara kerja LINQ, delegasi, penangkapan closure, dan manipulasi AST (Abstract Syntax Tree).*
- [Modul 01: Delegasi, Func/Action, Lambdas, dan Bahaya Memory Leak pada Closures](./03-functional-linq-internals/01-delegates-lambdas-closures.md)
- [Modul 02: Arsitektur Eksekusi LINQ: Deferred Execution, Yield Return, dan Pipeline Iterators](./03-functional-linq-internals/02-linq-deferred-execution.md)
- [Modul 03: Expression Trees: Parsing, Kompilasi Dinamis, dan Implementasi Custom LINQ Provider](./03-functional-linq-internals/03-expression-trees.md)

### [Bab 04: Manajemen Memori, GC & High-Performance C#](./04-manajemen-memori-gc-performance/README.md)
*Teknik optimasi performa tinggi, pemanfaatan memori berorientasi hardware, dan eliminasi GC pause time.*
- [Modul 01: Siklus Hidup Garbage Collector: Ephemeral Generations, LOH, POH, dan GC Tuning](./04-manajemen-memori-gc-performance/01-garbage-collector-internals.md)
- [Modul 02: Zero-Allocation Programming: `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, dan `ref struct`](./04-manajemen-memori-gc-performance/02-span-memory-ref-struct.md)
- [Modul 03: Memory Pooling (`ArrayPool<T>`), Unsafe Pointers, NativeMemory, dan Interop P/Invoke](./04-manajemen-memori-gc-performance/03-memory-pooling-dan-unsafe.md)

### [Bab 05: Asynchronous, Concurrency & Multithreading Internals](./05-async-concurrency-multithreading/README.md)
*Mekanika pemrosesan paralel, async state machine, penanganan race conditions, dan streaming non-blocking.*
- [Modul 01: Dekonstruksi `async`/`await`: Roslyn State Machine, SynchronizationContext, dan TaskScheduler](./05-async-concurrency-multithreading/01-async-await-state-machine.md)
- [Modul 02: Sinkronisasi Lanjutan, Lock-free Programming, dan `System.Threading.Channels`](./05-async-concurrency-multithreading/02-synchronization-channels.md)
- [Modul 03: Task Parallel Library (TPL), CancellationTokens, Dataflow, dan Parallel LINQ (PLINQ)](./05-async-concurrency-multithreading/03-tpl-cancellation-plinq.md)

### [Bab 06: Metaprogramming, Reflection & Roslyn Source Generators](./06-metaprogramming-source-generators/README.md)
*Membangun pustaka enterprise dengan manipulasi metadata runtime dan otomasi kompilasi kode modern.*
- [Modul 01: Reflection Internals, Dynamic Code Generation, dan DynamicMethod (`ILGenerator`)](./06-metaprogramming-source-generators/01-reflection-emit-il.md)
- [Modul 02: Roslyn Compiler Platform: Menulis Custom Analyzers dan Code Fixers](./06-metaprogramming-source-generators/02-roslyn-analyzers.md)
- [Modul 03: Roslyn Source Generators: Otomasi Boilerplate, Pemetaan Tipe, dan AOT-Compliant Serializer](./06-metaprogramming-source-generators/03-source-generators.md)

### [Bab 07: Arsitektur Enterprise & Clean Architecture](./07-enterprise-clean-architecture/README.md)
*Standar industri perancangan solusi perangkat lunak modular, decoupled, dan mudah diuji.*
- [Modul 01: Clean Architecture, Hexagonal Pattern, dan Domain-Driven Design (DDD) Aggregates](./07-enterprise-clean-architecture/01-clean-architecture-ddd.md)
- [Modul 02: Internal IoC/DI: ServiceProvider Lifecycle, Scoped Leaks, dan Custom Container Resolution](./07-enterprise-clean-architecture/02-ioc-di-lifecycles.md)
- [Modul 03: Configuration Engine, Strongly-Typed Options, Validasi Terdistribusi, dan Middleware Pipeline](./07-enterprise-clean-architecture/03-options-middleware-pipeline.md)

### [Bab 08: Data Access & High-Performance Persistence](./08-data-access-persistence/README.md)
*Strategi akses data enterprise, integrasi relasional, caching, dan tuning performa database.*
- [Modul 01: Entity Framework Core: Change Tracker Internals, Compiled Queries, dan Split Queries](./08-data-access-persistence/01-efcore-internals-tuning.md)
- [Modul 02: High-Performance Micro-ORM: Dapper, Multi-Mapping, dan Buffer Handling](./08-data-access-persistence/02-dapper-micro-orm.md)
- [Modul 03: Transaksi Terdistribusi, Optimistic/Pessimistic Concurrency, dan Pola Outbox](./08-data-access-persistence/03-transactions-outbox-pattern.md)

### [Bab 09: Resiliency, Observability & Enterprise Security](./09-resiliency-observability-security/README.md)
*Menjamin ketersediaan tinggi, mitigasi kegagalan jaringan, audit jejak sistem, dan keamanan tingkat lanjut.*
- [Modul 01: Pola Resiliensi Aplikasi: Polly v8 (Circuit Breaker, Rate Limiting, Hedging, Fallback)](./09-resiliency-observability-security/01-polly-resilience.md)
- [Modul 02: Observabilitas Modern: OpenTelemetry (Distributed Tracing, Metrics, Serilog/Structured Logging)](./09-resiliency-observability-security/02-opentelemetry-logging.md)
- [Modul 03: Enkripsi Data, Proteksi Kunci (ASP.NET Data Protection), JWT/OIDC, dan Security Hardening](./09-resiliency-observability-security/03-security-cryptography.md)

### [Bab 10: Cloud-Native, High-Throughput & Distributed Systems](./10-cloud-native-distributed-systems/README.md)
*Deploy sistem ultra-cepat, komunikasi mikroservis real-time, optimasi kontainer, dan Native AOT.*
- [Modul 01: High-Throughput RPC: gRPC, Protobuf Serialization, Streaming, dan Interceptors](./10-cloud-native-distributed-systems/01-grpc-streaming-services.md)
- [Modul 02: Event-Driven Microservices: MassTransit, Event Sourcing, dan Message Brokers (Kafka/RabbitMQ)](./10-cloud-native-distributed-systems/02-event-driven-masstransit.md)
- [Modul 03: Native AOT (Ahead-of-Time), Trim Optimization, dan Produksi Kontainer Berukuran Minimal](./10-cloud-native-distributed-systems/03-native-aot-containers.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**ApexClearing: Ultra-Low Latency Order Execution & Distributed Settlement Engine**

### Deskripsi Sistem:
ApexClearing adalah platform backend bursa finansial terdistribusi yang dirancang untuk memproses, mencocokkan (*order-book matching*), dan menyelesaikan transaksi efek/aset kripto dengan beban transaksi masif (*high-frequency, ultra-low latency*). Sistem memisahkan eksekusi order kecepatan tinggi dengan proses pencatatan distributed ledger menggunakan pola CQRS dan Event Sourcing.

### Spesifikasi Teknis & Kriteria Wajib:
1. **Low-Latency In-Memory Matching Engine:**
   - Implementasi modul *Matching Engine* menggunakan alokasi mendekati nol (*zero-allocation*) memanfaatkan `Span<T>`, `Memory<T>`, `ArrayPool<T>`, dan `ref struct`.
   - Menggunakan `System.Threading.Channels` berorientasi *single-writer* tanpa mekanisme penguncian berat (*lock-free concurrent queues*).

2. **Arsitektur & Komunikasi Antar-Layanan:**
   - **Ingress Gateway:** gRPC Streaming end-point dengan validasi skema protobuf berbasis kompilasi C#.
   - **Event Store & Message Bus:** Implementasi MassTransit terintegrasi dengan Apache Kafka untuk publishing event `OrderPlaced`, `OrderMatched`, dan `SettlementFinalized`.
   - **Persistence Strategy:** Polyglot persistence; PostgreSQL via Entity Framework Core untuk manajemen akun dan state settlement, serta TimescaleDB/Dapper untuk pencatatan riwayat audit transaksi berkecepatan tinggi.

3. **Metaprogramming & Source Generation:**
   - Membuat custom **Roslyn Source Generator** untuk menghasilkan parser serialisasi data biner custom secara otomatis pada waktu kompilasi (*compile-time*) tanpa memanfaatkan runtime reflection sama sekali.

4. **Resilience & Production Observability:**
   - Integrasi **Polly v8** untuk penanganan *transient error* pada integrasi perbankan/clearing external.
   - Penuh dengan instrumentasi **OpenTelemetry** (Metrics, Distributed Tracing melalui Jaeger, dan Structured Logging via Serilog).
   - Metrik CPU GC Generation 0/1/2 collection metrics terekspos ke Prometheus endpoint.

5. **Deployment & AOT Compilation:**
   - Dikompilasi menggunakan target **.NET 8+ Native AOT**.
   - Output *executable binary* mandiri (tanpa ketergantungan runtime eksternal) dengan konsumsi memori dasar (*base memory footprint*) < 30 MB dan *cold start* < 15 milidetik.
   - Dibuat dalam format distroless Docker container berukuran minimal dengan keamanan terisolasi.