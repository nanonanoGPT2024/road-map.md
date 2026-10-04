# Enterprise Java Engineering: From JVM Internals to High-Throughput Distributed Systems

Selamat datang di kurikulum enterprise **Java Engineering**. Kurikulum ini dirancang untuk mentransformasi seorang pengembang perangkat lunak menjadi **Principal Java Engineer** yang memahami ekosistem Java dari tingkat paling fundamental (*JVM bytecodes, memory barrier, non-blocking I/O*) hingga arsitektur terdistribusi skala tinggi (*event-driven microservices, reactive streams, GraalVM AOT native compilation*).

---

## 1. Course Overview & Mindset

### Engineering Mindset
Java bukan sekadar bahasa pemrograman berorientasi objek; Java adalah platform komputasi enterprise dengan ekosistem runtime (JVM) paling teruji di dunia. Menguasai Java pada level *senior-to-principal* menuntut pergeseran paradigma:
1. **Mechanical Sympathy**: Menulis kode Java tanpa memahami bagaimana JVM mengeksekusi instruksi pada CPU fisik adalah resep kegagalan sistem berskala besar. Anda harus memahami *memory layout*, interaksi *cache line*, mekanisme *Garbage Collector (GC)*, serta bagaimana JIT Compiler (*C1/C2*) mengoptimasi bytecode menjadi instruksi mesin native.
2. **Deterministic Reliability vs Premature Optimization**: Menghasilkan sistem enterprise yang stabil, minim regresi, *fault-tolerant*, dan mudah dipelihara menggunakan pola modular, typing ketat, serta abstraction boundary yang jelas.
3. **Modern Idiomatic Java**: Menolak pola pikir warisan Java 1.4/5/8 kuno. Pendekatan kurikulum ini mengadopsi standar modern (**Java 17 LTS hingga Java 21 LTS**), memanfaatkan *Virtual Threads (Project Loom)*, *Pattern Matching*, *Records*, *Sealed Interfaces*, dan paradigma fungsional modern.
4. **Cloud-Native & Distributed by Design**: Memahami trade-off latensi jaringan, konsistensi data (*ACID vs BASE*), *backpressure*, *distributed transactions*, dan *observability-first development*.

---

## 2. Learning Roadmap

```text
===================================================================================
                       ENTERPRISE JAVA CURRICULUM ROADMAP
===================================================================================

[BAB 01: JVM Deep Dive & Fondasi Java Modern]
   │
   ├── 01. Arsitektur JVM, ClassLoader & Memory Model (Stack, Heap, Metaspace)
   ├── 02. Modern Java Idiom: Records, Pattern Matching, Sealed Types
   └── 03. JIT Compilation (C1/C2), GC Ergonomics (G1, ZGC) & Bytecode Analysis
   │
[BAB 02: Object-Oriented Engineering & Functional Core]
   │
   ├── 01. SOLID & Enterprise Domain Modeling
   ├── 02. Functional Programming: Lambdas, Streams & Monadic Design
   └── 03. Generics Ekstrem, Type Erasure, PECS & Reflection
   │
[BAB 03: Java Concurrency & Multithreading Mendalam]
   │
   ├── 01. Java Memory Model (JMM), Atomics & Lock-Free Programming
   ├── 02. ForkJoinPool, CompletableFuture & Structured Concurrency
   └── 03. Virtual Threads (Project Loom) & High-Throughput Concurrency
   │
[BAB 04: I/O, Networking & Low-Latency Data Processing]
   │
   ├── 01. Classic I/O vs Java NIO (Channels, Buffers, Selectors)
   ├── 02. HTTP/2, gRPC & Binary Serialization (Protobuf, Kryo, Jackson)
   └── 03. Off-Heap Memory Management & Foreign Function & Memory API (Panama)
   │
[BAB 05: Data Persistence, ORM & Database Performance Tuning]
   │
   ├── 01. JDBC Internals, HikariCP & Batch Execution
   ├── 02. JPA & Hibernate Internals: Entity Lifecycle, Caching & Dirty Checking
   └── 03. Query Optimization, N+1 Prevention, Distributed Locking & Isolation
   │
[BAB 06: Framework Architecture: Spring Boot 3 Deep Dive]
   │
   ├── 01. IoC Container & Bean Lifecycle Under the Hood
   ├── 02. Spring Boot Auto-Configuration & Custom Starters
   └── 03. Spring AOP, Dynamic Proxies & Annotation Processing
   │
[BAB 07: Enterprise Microservices & Distributed Systems]
   │
   ├── 01. Contract-First API, Domain-Driven Design (DDD) & Hexagonal Architecture
   ├── 02. Event-Driven Architecture dengan Apache Kafka (Transactional Outbox)
   └── 03. Resilience Engineering: Circuit Breaking, Rate Limiting & Retry (Resilience4j)
   │
[BAB 08: Reactive Java & Event-Loop Systems]
   │
   ├── 01. Reactive Streams Specification & Project Reactor (Flux/Mono)
   ├── 02. Spring WebFlux: Event Loop Architecture & Backpressure Management
   └── 03. Non-Blocking Persistence: R2DBC & Reactive Data Pipelines
   │
[BAB 09: Enterprise Security & Identity Governance]
   │
   ├── 01. JCA/JCE Cryptography, TLS/mTLS & Secure Coding Standards
   ├── 02. Spring Security 6 Internals: Filter Chains & SecurityContext
   └── 03. Zero-Trust Identity: OAuth2, OIDC, JWT Verification & RBAC/ABAC
   │
[BAB 10: Observability, Cloud-Native Deployment & GraalVM Native Image]
   │
   ├── 01. Production Observability: OpenTelemetry, Micrometer & Distributed Tracing
   ├── 02. Containerization, Linux cgroups v2 Awareness & JVM Container Tuning
   └── 03. Ahead-Of-Time (AOT) Compilation, GraalVM Native Image & Substrate VM
   │
===================================================================================
                       CAPSTONE: HIGH-SCALE CORE PAYMENT ENGINE
===================================================================================
```

---

## 3. Detail Navigasi Kurikulum

### [Bab 01: JVM Deep Dive & Fondasi Java Modern](./01-jvm-deep-dive-and-modern-syntax/)
*Membongkar cara kerja runtime JVM, model alokasi memori, optimalisasi runtime, dan pemanfaatan sintaksis modern Java LTS.*
* [Modul 01: Arsitektur JVM, ClassLoader & Memory Model](./01-jvm-deep-dive-and-modern-syntax/01-jvm-architecture-classloader-and-memory-model.md)
  * JVM Subsystems, ClassLoader hierarchy (Bootstrap, Platform, App), Heap (Eden, Survivor, Tenured), Metaspace, Stack Frame, and JIT compilation paths.
* [Modul 02: Sintaksis Modern Java: Records, Pattern Matching & Sealed Types](./01-jvm-deep-dive-and-modern-syntax/02-modern-java-records-pattern-matching-and-sealed-types.md)
  * Immutability dengan Records, Enhanced Switch Expressions, Type Pattern Matching, Record Patterns, dan Algebraic Data Types via Sealed Interfaces.
* [Modul 03: JIT Compilation, Garbage Collection (G1, ZGC) & Bytecode Internals](./01-jvm-deep-dive-and-modern-syntax/03-jit-compilation-gc-ergonomics-and-bytecode-analysis.md)
  * C1/C2 Compiler, Tiered Compilation, OSR, Deoptimization, GC mechanisms (Serial, Parallel, G1, ZGC low-latency), and analyzing bytecode using `javap`.

---

### [Bab 02: Object-Oriented Engineering & Functional Core](./02-object-oriented-engineering-and-functional-core/)
*Penerapan prinsip OOP tingkat lanjut, fungsionalitas deklaratif, dan manipulasi sistem tipe Java.*
* [Modul 01: SOLID Principles & Enterprise Domain Modeling](./02-object-oriented-engineering-and-functional-core/01-solid-principles-and-enterprise-domain-modeling.md)
  * Desain modular berbasis SOLID, domain modeling tanpa leak-abstraction, Interface Segregation, dan decoupling domain model dari infrastructure layer.
* [Modul 02: Paradigma Fungsional: Functional Interfaces & Stream API Internals](./02-object-oriented-engineering-and-functional-core/02-functional-interfaces-and-stream-api-internals.md)
  * Functional Interfaces (`Function`, `BiFunction`, `Predicate`), Monadic patterns dengan `Optional`, Stream execution pipelines, `Spliterator`, dan stateless/stateful operations.
* [Modul 03: Generics Ekstrem, Type Erasure, PECS & Reflection](./02-object-oriented-engineering-and-functional-core/03-generics-type-erasure-pecs-and-reflection.md)
  * Producer Extends Consumer Super (PECS), Generic Constraints, Type Erasure, Bridge Methods, dan aman menggunakan Java Reflection & MethodHandles.

---

### [Bab 03: Java Concurrency & Multithreading Mendalam](./03-concurrency-and-multithreading/)
*Menguasai eksekusi konkuren, memori bersama, algoritma bebas-kunci, dan revolusi Virtual Threads.*
* [Modul 01: Java Memory Model (JMM), Atomics & Lock-Free Structures](./03-concurrency-and-multithreading/01-jmm-atomics-and-lock-free-programming.md)
  * Happens-Before relationship, Memory Barriers, `volatile`, CAS (Compare-And-Swap), `AtomicInteger`, `VarHandle`, dan lock-free data structures.
* [Modul 02: Executor Framework, ForkJoinPool & CompletableFuture](./03-concurrency-and-multithreading/02-executors-forkjoinpool-and-completablefuture.md)
  * Thread pool sizing, Work-stealing algorithm pada `ForkJoinPool`, asynchronous chaining, pipelining, and error mitigation dengan `CompletableFuture`.
* [Modul 03: Project Loom: Virtual Threads & High-Throughput Systems](./03-concurrency-and-multithreading/03-virtual-threads-and-structured-concurrency.md)
  * Carrier threads vs Virtual threads, Continuation preservation, Pinning prevention (`synchronized` vs `ReentrantLock`), dan Structured Concurrency API.

---

### [Bab 04: I/O, Networking & Low-Latency Data Processing](./04-io-networking-and-low-latency-systems/)
*Pemrosesan data berkecepatan tinggi, perbandingan model blocking vs non-blocking, dan interaksi native.*
* [Modul 01: Java NIO: Non-Blocking I/O, Channels, Buffers & Selectors](./04-io-networking-and-low-latency-systems/01-java-nio-channels-buffers-and-selectors.md)
  * Buffer lifecycle (`allocate`, `flip`, `clear`, `compact`), Channel-to-Channel transfer, Zero-Copy transfer menggunakan `FileChannel.transferTo()`, dan Selector multiplexing.
* [Modul 02: Network Communication: HTTP/2 Client, gRPC & Serialisasi Performa Tinggi](./04-io-networking-and-low-latency-systems/02-network-clients-grpc-and-serialization.md)
  * Modern `java.net.http.HttpClient`, RPC menggunakan gRPC over HTTP/2, serialisasi biner via Protocol Buffers vs Jackson JSON performance tuning.
* [Modul 03: Direct Memory & Foreign Function & Memory (FFM) API](./04-io-networking-and-low-latency-systems/03-direct-memory-and-foreign-function-memory-api.md)
  * Off-heap memory allocation via `ByteBuffer.allocateDirect`, migrasi dari `sun.misc.Unsafe` ke Foreign Function & Memory (FFM) API (Java 22/21 Preview).

---

### [Bab 05: Data Persistence, ORM & Database Performance Tuning](./05-persistence-and-database-performance/)
*Optimalisasi database access layer, pencegahan query bottleneck, dan manajemen konkurensi data.*
* [Modul 01: JDBC Internals, HikariCP Tuning & Batch Processing](./05-persistence-and-database-performance/01-jdbc-internals-hikaricp-and-batching.md)
  * JDBC Driver mechanics, Statement caching, HikariCP pool sizing heuristics, dan batch inserts/updates execution strategies.
* [Modul 02: JPA/Hibernate Internals: Lifecycle, Caching & Dirty Checking](./05-persistence-and-database-performance/02-jpa-hibernate-internals-and-caching.md)
  * Entity State transitions, PersistentContext snapshots, Automatic Dirty Checking, First-Level Cache, Second-Level Cache (Ehcache/Redis), dan Query Cache.
* [Modul 03: Advanced Performance: N+1 Optimization, Locking & Transactions](./05-persistence-and-database-performance/03-query-optimization-locking-and-transactions.md)
  * Join Fetch vs Entity Graphs, N+1 mitigation, Optimistic Locking (`@Version`) vs Pessimistic Locking (`PESSIMISTIC_WRITE`), dan Transaction Isolation Levels.

---

### [Bab 06: Framework Architecture: Spring Boot 3 Deep Dive](./06-spring-boot-internals-and-architecture/)
*Membedah mekanisme internal framework de-facto enterprise Java.*
* [Modul 01: IoC Container & Bean Lifecycle Under the Hood](./06-spring-boot-internals-and-architecture/01-ioc-container-and-bean-lifecycle.md)
  * `BeanFactory` vs `ApplicationContext`, `BeanDefinition`, Instantiation, Post-processors (`BeanFactoryPostProcessor`, `BeanPostProcessor`), dan destruction lifecycle.
* [Modul 02: Spring Boot Auto-Configuration & Custom Starter Engineering](./06-spring-boot-internals-and-architecture/02-autoconfiguration-and-custom-starters.md)
  * Analisis `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, Conditional annotations (`@ConditionalOnClass`, `@ConditionalOnProperty`), dan pembuatan custom starter modular.
* [Modul 03: Spring AOP, Dynamic Proxies & Custom Annotations](./06-spring-boot-internals-and-architecture/03-spring-aop-dynamic-proxies-and-annotations.md)
  * JDK Dynamic Proxy vs CGLIB proxying, Pointcuts, JoinPoints, Advices, dan rekayasa runtime interception menggunakan Custom Annotations.

---

### [Bab 07: Enterprise Microservices & Distributed Systems](./07-enterprise-microservices-and-distributed-systems/)
*Membangun layanan terdistribusi yang resilient, scalable, dan mengadopsi DDD.*
* [Modul 01: Domain-Driven Design (DDD) & Hexagonal Architecture](./07-enterprise-microservices-and-distributed-systems/01-ddd-and-hexagonal-architecture.md)
  * Aggregates, Entities, Value Objects, Domain Events, Ports and Adapters (Hexagonal Architecture) structure dalam modular package layout.
* [Modul 02: Event-Driven Architecture dengan Apache Kafka](./07-enterprise-microservices-and-distributed-systems/02-event-driven-architecture-with-kafka.md)
  * Producer idempotent configs, Consumer Group balancing, Dead Letter Queues (DLQ), dan implementasi Transactional Outbox Pattern untuk zero message loss.
* [Modul 03: Distributed Resilience & Fault Tolerance](./07-enterprise-microservices-and-distributed-systems/03-distributed-resilience-with-resilience4j.md)
  * Implementasi Circuit Breaker, Bulkhead isolation, Rate Limiter, dan Exponential Backoff Retry menggunakan library Resilience4j.

---

### [Bab 08: Reactive Java & Event-Loop Systems](./08-reactive-java-and-event-loop-systems/)
*Arsitektur non-blocking asynchronous streaming untuk throughput ekstrem dan efisiensi memori.*
* [Modul 01: Reactive Streams Specification & Project Reactor Internals](./08-reactive-java-and-event-loop-systems/01-reactive-streams-and-project-reactor.md)
  * Publisher, Subscriber, Subscription, Backpressure propagation, `Flux` vs `Mono`, dan Schedulers (`parallel()`, `boundedElastic()`).
* [Modul 02: Spring WebFlux: Non-Blocking Web Layer](./08-reactive-java-and-event-loop-systems/02-spring-webflux-and-event-loop.md)
  * Netty event loop substrate, Non-blocking Controllers vs Functional Endpoints, Request-Response pipeline, dan penanganan I/O bound tasks.
* [Modul 03: Reactive Data Persistence via R2DBC](./08-reactive-java-and-event-loop-systems/03-reactive-data-access-with-r2dbc.md)
  * Reactive Relational Database Connectivity (R2DBC), Transaction management reaktif, Connection Pooling reaktif, dan streaming data end-to-end tanpa blocking threads.

---

### [Bab 09: Enterprise Security & Identity Governance](./09-enterprise-security-and-identity-governance/)
*Keamanan aplikasi pertahanan mendalam (*defense-in-depth*), kriptografi, dan identitas terfederasi.*
* [Modul 01: Java Cryptography Architecture (JCA/JCE) & Secure Coding](./09-enterprise-security-and-identity-governance/01-jca-cryptography-and-secure-coding.md)
  * Hashing (Argon2, BCrypt), AES-GCM symmetric encryption, RSA/ECC asymmetric signatures, KeyStore management, dan pencegahan injection/memory leakage.
* [Modul 02: Spring Security 6 Architecture & Filter Chains](./09-enterprise-security-and-identity-governance/02-spring-security-internals-and-filter-chains.md)
  * `SecurityFilterChain`, `AuthenticationManager`, `SecurityContextHolder`, CSRF protection, CORS policies, dan custom reactive/servlet authentication filters.
* [Modul 03: Zero-Trust Security: OAuth2, OIDC & JWT Hardening](./09-enterprise-security-and-identity-governance/03-oauth2-oidc-and-jwt-hardening.md)
  * Implementasi Resource Server, Stateless JWT validation (JWKS endpoint parsing), Token introspection, Method-level authorization (`@PreAuthorize`), dan fine-grained RBAC/ABAC.

---

### [Bab 10: Observability, Cloud-Native Deployment & GraalVM Native Image](./10-observability-cloud-native-and-graalvm/)
*Menyiapkan aplikasi Java untuk lingkungan cloud terdistribusi, instrumentasi metrik, dan kompilasi AOT.*
* [Modul 01: Full-Stack Observability: OpenTelemetry & Micrometer](./10-observability-cloud-native-and-graalvm/01-opentelemetry-micrometer-and-tracing.md)
  * Metrics collection (Prometheus/Micrometer), W3C Trace Context propagation, Distributed Tracing dengan OpenTelemetry/Jaeger, dan structured JSON logging (MDC context).
* [Modul 02: Containerization & Linux cgroups v2 JVM Tuning](./10-observability-cloud-native-and-graalvm/02-containerization-and-cgroups-tuning.md)
  * Container ergonomics, Multi-stage Dockerfile distroless, Heap sizing di Docker (`-XX:MaxRAMPercentage`), cgroups v2 CPU quota management, dan CDS (Class Data Sharing).
* [Modul 03: GraalVM Native Image & Substrate VM Optimization](./10-observability-cloud-native-and-graalvm/03-graalvm-native-image-and-aot-compilation.md)
  * Ahead-Of-Time (AOT) compilation, Closed-world assumption, reachability metadata generation, eliminasi cold-start (<50ms startup time), dan pemantauan memori footprint minimal.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**OmniPay Core: High-Throughput Fault-Tolerant Distributed Financial Ledger & Payment Engine**

### Arsitektur Sistem:
```text
                       [API Gateway / Edge Proxy]
                                  │
                                  ▼
                  [Payment Ingestion Service (Java 21)]
                   (Virtual Threads + Non-blocking I/O)
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
     [Kafka Ingestion Topic]                 [Redis Cache Layer]
              │                                (Distributed Lock)
              ▼
   [Ledger Engine Service] ◄── Transactional Outbox Pattern
   (Double-Entry Bookkeeping)
              │
              ├── PostgreSQL 16 (Source of Truth - ACID Isolation)
              │
              ▼
   [Audit & Settlement Stream] ──► [Event Store / Long-Term Analytical S3]
```

### 1. Functional Requirements:
*   **Double-Entry Bookkeeping Ledger**: Setiap transaksi finansial harus mematuhi aturan akuntansi debit/kredit seimbang (`Σ Debits == Σ Credits`). Tidak boleh ada modifikasi record mutasi (*append-only immutable ledger*).
*   **Strict Idempotency Layer**: Setiap request pembayaran wajib menyertakan `Idempotency-Key` unik. Sistem harus menjamin bahwa eksekusi transaksi yang berulang tidak akan menduplikasi debit akun finansial.
*   **Account Locking & Sequencing**: Penanganan update saldo akun secara atomik tanpa menyebabkan database deadlock pada volume tinggi melalui algoritma optimistic concurrency control (`@Version`) yang digabungkan dengan Redis Redlock distributed fallback.
*   **Transactional Outbox Pipeline**: Setiap event mutasi buku besar diterbitkan ke Apache Kafka menggunakan Polling/Debezium CDC Transactional Outbox Pattern untuk memastikan tidak ada divergensi data antara database relasional dan broker antrean.

### 2. Non-Functional & Reliability Requirements:
*   **Throughput & Latency Target**: Sistem mampu memproses minimal **10.000 Request Per Second (RPS)** pada API Ingestion dengan latensi **P99 < 15ms** pada beban kerja sustained.
*   **Virtual Threads Concurrency**: Menggunakan Java 21 Virtual Threads (`Executors.newVirtualThreadPerTaskExecutor`) pada I/O-bound pipelines untuk menjamin efisiensi thread tanpa starvation.
*   **Zero Data Loss Guarantees**: Kafka producer dengan konfigurasi `acks=all`, `min.insync.replicas=2`, `enable.idempotence=true`, dan rollback transaksi ACID database penuh jika terjadi kegagalan sistem downstream.
*   **Graceful Degradation**: Implementasi Circuit Breaker via Resilience4j pada rute payment gateway eksternal; jika circuit terbuka (*OPEN*), request dialihkan ke asynchronous retry queue dengan dead-letter handling.

### 3. Observability & Infrastructure Verification:
*   **Distributed Tracing**: Trace context disuntikkan mulai dari Ingestion API, dilanjutkan ke Kafka Headers, hingga dieksekusi oleh worker Ledger Engine, dan dapat divisualisasikan secara end-to-end pada Jaeger/Zipkin.
*   **Metrics & Health**: Expose Prometheus metrics mencakup:
    *   Laju GC pause time & heap allocation rate.
    *   Ukuran connection pool active vs pending (HikariCP).
    *   Jumlah active/carrier Virtual Threads.
    *   Laju commit Kafka offset lag.
*   **Container Delivery**: Aplikasi dikompilasi menjadi dua varian:
    1. Multi-stage Distroless JVM container image dengan optimasi Class Data Sharing (CDS).
    2. GraalVM Native Image binary dengan startup latency di bawah 80 milidetik dan memory footprint di bawah 64MB idle.

---
*Silabus ini merupakan acuan resmi rekayasa perangkat lunak enterprise berbasis Java. Setiap bab harus diselesaikan secara runtut melalui studi teoritis, inspeksi kode, dan implementasi proyek nyata.*