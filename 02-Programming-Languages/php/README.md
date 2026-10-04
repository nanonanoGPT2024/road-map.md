# Silabus Kurikulum Enterprise: Modern PHP Engineering

Selamat datang di kurikulum rekayasa perangkat lunak enterprise berbasis **PHP 8.3+**. Kurikulum ini dirancang untuk mentransformasi paradigma pengembangan PHP dari pendekatan prosedural/skrip tradisional menuju rekayasa sistem terdistribusi, *strongly-typed*, berperforma tinggi, dan mengadopsi standar arsitektur industri modern.

---

## 1. Course Overview & Mindset

PHP telah bertransformasi secara fundamental sejak rilis PHP 7.0 hingga PHP 8.3+. Bahasa ini bukan lagi sekadar alat pembuat situs web dinamis sederhana, melainkan platform komputasi tangguh yang menggerakkan sistem berskala masif di berbagai organisasi global. Kurikulum ini berfokus penuh pada **Enterprise Modern PHP**, menuntut standar rekayasa tertinggi:

*   **Strict Typing & Static Analysis**: Tidak ada kompromi untuk `mixed` yang tidak terkontrol. Seluruh kode menerapkan deklarasi tipe ketat (`declare(strict_types=1);`), analisis statis tingkat tinggi (PHPStan/Psalm Level 8+), serta memanfaatkan Union/Intersection types, Readonly classes, dan First-class callables.
*   **Standards Compliant (PHP-FIG)**: Implementasi penuh terhadap rekomendasi PSR (PSR-3, PSR-4, PSR-7, PSR-11, PSR-12, PSR-15, PSR-18) untuk memastikan interoperabilitas komponen tanpa keterikatan mutlak pada satu vendor atau kerangka kerja (*framework-agnostic*).
*   **High Performance Execution Models**: Melampaui batasan model eksekusi *shared-nothing* tradisional (PHP-FPM) dengan mendalami sistem *runtime modern* berbasis *event-loop* dan *in-memory application servers* seperti FrankenPHP, RoadRunner, dan Swoole.
*   **Domain-Driven Design & Clean Architecture**: Pemisahan tegas antara logika domain murni (*pure enterprise rules*) dengan infrastruktur komputasi eksternal (framework, database, protokol transmisi) menggunakan arsitektur Heksagonal (*Ports & Adapters*).
*   **Defensive Engineering & Zero-Trust**: Pemanfaatan kriptografi modern berbasis libsodium, mitigasi eksploitasi memori, penanganan race conditions pada konkurensi data, dan strategi mitigasi kerentanan keamanan level aplikasi (OWASP Top 10).

---

## 2. Learning Roadmap

```plaintext
Modern PHP Engineering Master Plan
│
├── [Bab 01] Fondasi Modern PHP 8.x & Execution Model
│   ├── CLI, SAPI, Zend Engine, JIT & OPcache Internals
│   ├── Advanced Type System & Declarative Typing
│   └── Modern Language Primitives (Enums, Attributes, Match)
│
├── [Bab 02] Advanced Object-Oriented PHP & Meta-programming
│   ├── Immutability, Readonly Classes & Value Objects
│   ├── Meta-programming via Reflection API & Attributes
│   └── Type Variance, Generics Simulation & First-Class Callables
│
├── [Bab 03] Standarisasi Ekosistem & Modular Package Architecture
│   ├── Composer Deep Dive & Class-loading Optimization
│   ├── PHP-FIG Ecosystem & Core PSR Compliance
│   └── Building Framework-Agnostic Modular Packages
│
├── [Bab 04] Functional Programming, Concurrency & Memory Management
│   ├── Pure Functions, High-Order Functions & Generators
│   ├── Memory Allocation, Reference Counting & Garbage Collection
│   └── PHP Fibers & Concurrency Primitives
│
├── [Bab 05] Enterprise Database Persistence & Concurrency
│   ├── Low-Level PDO Architecture & Resilient Connection Pooling
│   ├── Transaction Isolation, Deadlocks & Optimistic Locking
│   └── CQRS Pattern Implementation: Raw High-Speed SQL vs ORM
│
├── [Bab 06] Defensive Security Engineering
│   ├── Advanced Cryptography with Libsodium Engine
│   ├── Hardening Against Injection, Deserialization & Timing Attacks
│   └── Stateless Authentication, Mutual TLS & Security Middleware
│
├── [Bab 07] Testing Rigor, Static Analysis & Mutation Testing
│   ├── Unit & Integration Testing via PHPUnit & Pest
│   ├── Advanced Static Analysis via PHPStan & Psalm
│   └── Mutation Testing with Infection & Quality Assurance
│
├── [Bab 08] Arsitektur Perangkat Lunak: Hexagonal & Clean Architecture
│   ├── Domain-Driven Design (DDD) Aggregates & Repositories
│   ├── Hexagonal Architecture: Ports & Adapters Implementation
│   └── Event-Driven Systems: Domain Events & In-Memory Event Buses
│
├── [Bab 09] High-Performance Runtimes & Asynchronous Processing
│   ├── Breaking the Shared-Nothing Model: FrankenPHP & RoadRunner
│   ├── Event-Loop Runtimes: Revolt & Swoole Deep Dive
│   └── Distributed In-Memory Caching & Real-Time Blackfire Profiling
│
└── [Bab 10] Enterprise SRE, Observability & Cloud-Native Deployment
    ├── Containerization Optimization & Multi-Stage Production Builds
    ├── OpenTelemetry, Tracing, Metrics & Structured JSON Logging
    └── Production Deployment, Health Probes & Zero-Downtime Releases
```

---

## 3. Navigasi Detail Modul Silabus

### Bab 01: Fondasi Modern PHP 8.x & Execution Model
Mempelajari siklus hidup eksekusi runtime PHP, kompilasi bytecode, optimalisasi JIT/OPcache, serta penguasaan sistem pengetikan modern.
*   [Modul 01.1: Zend Engine, OPcache, JIT Compiler & Lifecycle SAPI](bab-01-fondasi-modern-php/zend-engine-opcache-jit.md)
*   [Modul 01.2: Strict Typing, Scalar, Union, Intersection & DNF Types](bab-01-fondasi-modern-php/strict-typing-and-type-systems.md)
*   [Modul 01.3: Konstruksi Bahasa Modern: Attributes, Enums, & Match Expressions](bab-01-fondasi-modern-php/modern-language-constructs.md)

### Bab 02: Advanced Object-Oriented PHP & Meta-programming
Mendalami perancangan sistem berbasis objek tingkat lanjut, enkapsulasi mutlak dengan *immutability*, dan meta-programming runtime.
*   [Modul 02.1: Immutability Paradigm: Readonly Classes, Properties & Value Objects](bab-02-advanced-oop-metaprogramming/immutability-and-value-objects.md)
*   [Modul 02.2: Advanced Reflection API, Metaprogramming & Runtime Inspection](bab-02-advanced-oop-metaprogramming/reflection-and-metaprogramming.md)
*   [Modul 02.3: Covariance, Contravariance, Generics Mocking via PHPDoc & Closures](bab-02-advanced-oop-metaprogramming/type-variance-and-generics.md)

### Bab 03: Standarisasi Ekosistem & Modular Package Architecture
Membangun fondasi rekayasa perangkat lunak berskala besar yang modular, patuh pada konsorsium standar terbuka (PHP-FIG), dan interoperabel.
*   [Modul 03.1: Composer Internals, Classmap Optimization & Private Repository Strategies](bab-03-standarisasi-ekosistem/composer-internals-and-autoloading.md)
*   [Modul 03.2: PSR Deep Dive: PSR-7/15/17 (HTTP Pipeline), PSR-11 (Container), & PSR-3](bab-03-standarisasi-ekosistem/psr-standards-implementation.md)
*   [Modul 03.3: Arsitektur Package Agnostik: Membangun Library Reusable Berstandar Industri](bab-03-standarisasi-ekosistem/building-framework-agnostic-packages.md)

### Bab 04: Functional Programming, Concurrency & Memory Management
Menguasai manajemen alokasi memori heap/stack, pencegahan *memory leak*, teknik fungsional, dan eksekusi konkurensi tingkat dasar menggunakan Fibers.
*   [Modul 04.1: Functional PHP: Pure Functions, High-Order Callables, Currying & Generators](bab-04-functional-memory-concurrency/functional-programming-and-generators.md)
*   [Modul 04.2: Memory Management: Garbage Collector, Reference Counting & Cycle Collection](bab-04-functional-memory-concurrency/memory-management-and-gc.md)
*   [Modul 04.3: Concurrency Primitives: Coroutine, Fibers, and Cooperative Multitasking](bab-04-functional-memory-concurrency/fibers-and-concurrency.md)

### Bab 05: Enterprise Database Persistence & Concurrency
Membangun lapisan persistensi berdaya tahan tinggi, menangani integritas transaksi data ACID, dan menyelesaikan tantangan konkurensi ekstrem.
*   [Modul 05.1: Low-Level PDO Architecture, Buffer Management & Connection Resilience](bab-05-database-and-concurrency/pdo-architecture-and-connection-pooling.md)
*   [Modul 05.2: Concurrency Controls: Pessimistic/Optimistic Locking, Isolation Levels & Deadlocks](bab-05-database-and-concurrency/locking-and-transaction-isolation.md)
*   [Modul 05.3: CQRS Read-Write Splitting: High-Performance Hydration vs Robust Unit-of-Work ORMs](bab-05-database-and-concurrency/cqrs-hydration-and-orm.md)

### Bab 06: Defensive Security Engineering
Menerapkan protokol pertahanan berlapis untuk menangkal vektor serangan modern, enkripsi data kelas perbankan, dan otentikasi ketat.
*   [Modul 06.1: Enterprise Cryptography via Libsodium: Symmetric, Asymmetric & Key Rotation](bab-06-defensive-security/libsodium-and-cryptography.md)
*   [Modul 06.2: Mitigasi OWASP Top 10: SQL Injection, Timing Attacks, Object Injection & CSRF](bab-06-defensive-security/owasp-mitigation-and-hardening.md)
*   [Modul 06.3: Stateless Authentication Engines: Mutual TLS (mTLS), Secure Tokens & Auth Middleware](bab-06-defensive-security/mtls-and-stateless-auth.md)

### Bab 07: Testing Rigor, Static Analysis & Mutation Testing
Mengotomatisasi verifikasi fungsionalitas dan kebenaran matematis sistem melalui pipeline pengujian berlapis dan jaminan kualitas kode.
*   [Modul 07.1: Comprehensive Unit & Integration Testing: Architecture Mocking via Pest & PHPUnit](bab-07-testing-and-quality/phpunit-and-pest-testing.md)
*   [Modul 07.2: Static Analysis at Scale: Custom PHPStan Rules, Baseline, and Type Inference](bab-07-testing-and-quality/phpstan-psalm-static-analysis.md)
*   [Modul 07.3: Mutation Testing: Menguji Ketahanan Test Suite Menggunakan Infection Engine](bab-07-testing-and-quality/mutation-testing-with-infection.md)

### Bab 08: Arsitektur Perangkat Lunak: Hexagonal & Clean Architecture
Merancang aplikasi enterprise decoupling total yang mengisolasi aturan bisnis utama dari dunia luar menggunakan prinsip DDD dan Ports & Adapters.
*   [Modul 08.1: Domain-Driven Design (DDD): Entities, Value Objects, Domain Events & Aggregates](bab-08-arsitektur-hexagonal-ddd/ddd-fundamentals-in-php.md)
*   [Modul 08.2: Hexagonal Architecture: Memisahkan Driver Ports dari Driven Adapters](bab-08-arsitektur-hexagonal-ddd/hexagonal-ports-and-adapters.md)
*   [Modul 08.3: Event-Driven Core: CQRS Command Handlers, Domain Events Dispatcher, & Outbox Pattern](bab-08-arsitektur-hexagonal-ddd/event-driven-cqrs-outbox.md)

### Bab 09: High-Performance Runtimes & Asynchronous Processing
Menembus batas komputasi PHP tradisional dengan server persisten, runtime asinkron, non-blocking I/O, dan instrumentasi performa.
*   [Modul 09.1: Persistent Application Servers: Menguasai FrankenPHP & RoadRunner Core Lifecycle](bab-09-high-performance-runtimes/frankenphp-and-roadrunner.md)
*   [Modul 09.2: Async Non-Blocking I/O: Event Loops, Revolt PHP, Swoole, dan Worker Pools](bab-09-high-performance-runtimes/async-revolt-and-swoole.md)
*   [Modul 09.3: Profiling & Memory Leak Detection: Advanced Diagnostics via Blackfire & Xdebug Profiler](bab-09-high-performance-runtimes/blackfire-and-performance-profiling.md)

### Bab 10: Enterprise SRE, Observability & Cloud-Native Deployment
Mempersiapkan sistem untuk skala produksi masif, integrasi pipeline CI/CD tanpa henti, orkestrasi kontainer, serta telemetri terdistribusi.
*   [Modul 10.1: Container Engineering: Multi-Stage Alpine/Debian Docker Builds, Distroless & Security Scanning](bab-10-sre-observability-cloud/production-dockerization.md)
*   [Modul 10.2: Distributed Tracing & Observability: OpenTelemetry, Prometheus Metrics & Structured Logs](bab-10-sre-observability-cloud/opentelemetry-and-metrics.md)
*   [Modul 10.3: Kubernetes Native Deployment, Graceful Termination, Readiness/Liveness Probes](bab-10-sre-observability-cloud/kubernetes-native-deployment.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**Core Payment & Multi-Currency Settlement Engine (FinTech Infrastructure Platform)**

### Deskripsi Sistem
Sebuah sistem *high-throughput core banking engine* terdistribusi yang menangani pemrosesan transaksi pembayaran multi-mata uang, validasi saldo akun (*double-entry bookkeeping*), deteksi anomali penipuan transaksi secara *real-time*, integrasi pihak ketiga (*payment aggregator*), serta penyesuaian (*settlement/reconciliation*) terjadwal secara asinkron.

### Target Spesifikasi Teknis & Non-Fungsional
1.  **Arsitektur Inti**:
    *   Menerapkan arsitektur **Hexagonal / Ports & Adapters** yang terpisah mutlak dari framework HTTP.
    *   Menerapkan prinsip **Domain-Driven Design (DDD)** dengan *bounded context* yang jelas: *Payment Intake*, *Ledger Double-Entry*, *Exchange Rate Matrix*, dan *Reconciliation Core*.
2.  **Runtime & Kinerja**:
    *   Berjalan di atas **RoadRunner** atau **FrankenPHP** (worker mode, *in-memory runtime*) untuk meniadakan overhead inisialisasi framework pada setiap HTTP request.
    *   Mampu menangani beban minimal **2.500 TPS (Transactions Per Second)** dengan batas latensi $P_{99} \le 80\text{ ms}$.
3.  **Integritas Data & Konkurensi**:
    *   Setiap pergerakan saldo wajib menggunakan kalkulasi berbasis *Double-Entry Bookkeeping* (Setiap mutasi Debit harus setara dengan Kredit).
    *   Pencegahan mutlak terhadap *race-condition* dan *double-spending* menggunakan **Pessimistic Locking** (`SELECT FOR UPDATE`) pada skenario transaksi paralel, dipadukan dengan **Idempotency Keys** pada level API Gateway.
4.  **Standar Keamanan & Kriptografi**:
    *   Data sensitif (kartu/token perbankan) terenkripsi saat diam (*at-rest*) menggunakan algoritma terotentikasi **Libsodium** (`crypto_aead_xchacha20poly1305_ietf`).
    *   Integritas pesan antar-layanan divalidasi via **HMAC SHA-256** dan *signature verification*.
5.  **Kualitas Kode & Testing**:
    *   Analisis statis: **PHPStan Level 8 atau Max** (nol error, nol *baseline exception* yang diabaikan).
    *   Cakupan test: Minimal **90% Branch Coverage** menggunakan Pest/PHPUnit.
    *   Verifikasi ketahanan mutasi: **Infection MSI (Mutation Score Indicator) $\ge 80\%$**.
6.  **Observabilitas & Operasional**:
    *   Integrasi metrik ke **Prometheus** (Counter transaksi, Histogram durasi eksekusi).
    *   Distribusi jejak tracing menggunakan **OpenTelemetry SDK** ke Jaeger.
    *   Sistem ekspor log terstruktur berbasis format JSON sesuai spesifikasi Elastic Common Schema (ECS).

### Deliverables Capstone
*   **Source Code**: Repository monorepo/polyrepo terstruktur rapi dengan PHP 8.3+, `composer.json` terkonfigurasi ketat, dan static analyzer toolset.
*   **Infrastructure as Code & Docker**: `Dockerfile` multi-stage build yang memproduksi image siap produksi berukuran minimal (<150MB), aman, serta `docker-compose.yml` yang mencakup service: PHP Engine, RoadRunner/FrankenPHP, PostgreSQL 16 (dengan replication awareness), Redis Cluster, Kafka/RabbitMQ, Prometheus, dan Jaeger.
*   **Dokumentasi Desain Arsitektur (ADR)**: Minimal 3 Architecture Decision Records (ADRs) yang mendokumentasikan:
    1. Pemilihan in-memory application server vs PHP-FPM konvensional.
    2. Strategi isolasi transaksi database untuk mencegah deadlock pada transfer paralel.
    3. Implementasi Transactional Outbox Pattern untuk pengiriman event ke broker Kafka/RabbitMQ.