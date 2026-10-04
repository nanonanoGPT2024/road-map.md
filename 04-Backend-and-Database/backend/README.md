# 🌐 Kurikulum Lengkap: Backend Developer Mastery

> **Tujuan Kurikulum**: Mengubah pembelajar dari pemahaman dasar pemrograman menjadi **Senior Backend Engineer / Backend System Architect** yang menguasai protokol jaringan, runtime eksekusi, desain API enterprise (REST, GraphQL, gRPC), basis data relasional & NoSQL, caching terdistribusi, message brokers, keamanan (OWASP API Top 10), pengujian otomatis, serta pola arsitektur mikroservis tingkat lanjut (Saga, Event Sourcing, CQRS).

---

## 🗺️ Peta Jalan Pembelajaran (Learning Roadmap)

```
[ INTERNET & PROTOKOL ] ──> [ RUNTIME & CONCURRENCY ] ──> [ DESAIN API (REST/gRPC/GraphQL) ]
                                                                       │
                                                                       v
[ BASIN DATA NoSQL & CACHING ] <── [ RDBMS, SQL, & INDEXING ] <────────┘
         │
         v
[ MESSAGE BROKERS & ASYNC ] ──> [ SECURITY & OWASP API TOP 10 ] ──> [ TESTING & CI/CD ]
                                                                           │
                                                                           v
[ 🏆 CAPSTONE PROJECT: CORE BANKING ] <── [ ARSITEKTUR MIKROSERVIS & SAGA PATTERN ]
```

---

## 📚 Daftar Bab & Modul Pembelajaran

### [BAB 01: Fondasi Internet, HTTP/HTTPS, WebSockets, & DNS](./BAB-01-Fondasi-Internet-dan-Protokol/)
- [Module 01: Bagaimana Internet Bekerja, IP, DNS, TCP/UDP, & TLS 1.3 Handshake](./BAB-01-Fondasi-Internet-dan-Protokol/Module-01-Bagaimana-Internet-Bekerja-IP-DNS-TCP-UDP-TLS.md)
- [Module 02: Evolusi Protokol: HTTP/1.1 vs HTTP/2 vs HTTP/3, WebSockets, & SSE](./BAB-01-Fondasi-Internet-dan-Protokol/Module-02-Evolusi-HTTP-WebSockets-dan-Server-Sent-Events.md)
- [Praktikum Hands-on: Simulator Raw TCP vs HTTP & TLS Handshake](./BAB-01-Fondasi-Internet-dan-Protokol/hands-on/m01/tcp_http_tls_handshake_sim.js)
- [Praktikum Hands-on: Simulator WebSocket & SSE Duplex Streaming](./BAB-01-Fondasi-Internet-dan-Protokol/hands-on/m02/websocket_sse_duplex_sim.js)
- [BAB 01 Quiz & Chapter Challenge](./BAB-01-Fondasi-Internet-dan-Protokol/BAB-01-Quiz-dan-Challenge.md)

### [BAB 02: Bahasa Pemrograman Backend & Runtime Execution](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/)
- [Module 01: Manajemen Memori (Stack vs Heap), Concurrency Models (Event Loop vs Threads vs Goroutines)](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/Module-01-Manajemen-Memori-dan-Concurrency-Models.md)
- [Module 02: Kompilasi, Bytecode, JIT, Garbage Collection Algorithms, & CPU Profiling](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/Module-02-Kompilasi-JIT-Garbage-Collection-dan-Profiling.md)
- [Praktikum Hands-on: Simulator Event Loop vs Multi-Threading Concurrency](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/hands-on/m01/concurrency_models_sim.js)
- [Praktikum Hands-on: Simulator Mark-and-Sweep Garbage Collector & Memory Leaks](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/hands-on/m02/garbage_collector_leak_sim.js)
- [BAB 02 Quiz & Chapter Challenge](./BAB-02-Bahasa-Pemrograman-dan-Runtime-Execution/BAB-02-Quiz-dan-Challenge.md)

### [BAB 03: Arsitektur API: RESTful, GraphQL, & gRPC](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/)
- [Module 01: Desain RESTful API Enterprise, Richardson Maturity Model, HATEOAS, & Idempotency](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/Module-01-Desain-RESTful-API-Richardson-Maturity-Idempotency.md)
- [Module 02: Modern RPC & GraphQL: Protobuf Schema, Subscriptions, & Mitigasi N+1 Problem](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/Module-02-gRPC-Protobuf-dan-GraphQL-N-Plus-One-Problem.md)
- [Praktikum Hands-on: Simulator RESTful API Idempotency Key & HATEOAS](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/hands-on/m01/rest_idempotency_engine_sim.js)
- [Praktikum Hands-on: Simulator Protobuf Serialization vs GraphQL DataLoader](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/hands-on/m02/protobuf_graphql_dataloader_sim.js)
- [BAB 03 Quiz & Chapter Challenge](./BAB-03-Arsitektur-API-REST-GraphQL-gRPC/BAB-03-Quiz-dan-Challenge.md)

### [BAB 04: Basis Data Relasional (RDBMS) & SQL Mastery](./BAB-04-RDBMS-dan-SQL-Mastery/)
- [Module 01: Relational Modeling, Normalisasi vs Denormalisasi, ACID Guarantees, & Isolation Levels](./BAB-04-RDBMS-dan-SQL-Mastery/Module-01-Relational-Modeling-ACID-dan-Isolation-Levels.md)
- [Module 02: Indexing Internals (B-Tree, Hash, GIN), Query Planner (EXPLAIN ANALYZE), & Partitioning](./BAB-04-RDBMS-dan-SQL-Mastery/Module-02-Indexing-Internals-BTree-Query-Planner-Partitioning.md)
- [Praktikum Hands-on: Simulator Transaksi ACID & Anomali Isolasi (Dirty Read, Phantom Read)](./BAB-04-RDBMS-dan-SQL-Mastery/hands-on/m01/acid_isolation_levels_sim.js)
- [Praktikum Hands-on: Simulator B-Tree Index Search vs Full Table Scan](./BAB-04-RDBMS-dan-SQL-Mastery/hands-on/m02/btree_index_planner_sim.js)
- [BAB 04 Quiz & Chapter Challenge](./BAB-04-RDBMS-dan-SQL-Mastery/BAB-04-Quiz-dan-Challenge.md)

### [BAB 05: Basis Data Non-Relasional (NoSQL) & NewSQL](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/)
- [Module 01: Taksonomi NoSQL: Key-Value, Document, Wide-Column, Graph, & CAP Theorem](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/Module-01-Taksonomi-NoSQL-CAP-Theorem-dan-Document-Stores.md)
- [Module 02: Consistent Hashing, Sharding, Vector Databases, & AI Embeddings](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/Module-02-Consistent-Hashing-Sharding-dan-Vector-Databases.md)
- [Praktikum Hands-on: Simulator CAP Theorem Partition Tolerance & Eventual Consistency](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/hands-on/m01/cap_theorem_eventual_consistency_sim.js)
- [Praktikum Hands-on: Simulator Consistent Hashing Ring & Vnode Rebalancing](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/hands-on/m02/consistent_hashing_ring_sim.js)
- [BAB 05 Quiz & Chapter Challenge](./BAB-05-Basis-Data-NoSQL-dan-NewSQL/BAB-05-Quiz-dan-Challenge.md)

### [BAB 06: Strategi Caching & In-Memory Data Stores](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/)
- [Module 01: Pola Caching (Cache-Aside, Write-Through, Write-Behind) & Algoritma Eviksi (LRU, LFU)](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/Module-01-Pola-Caching-dan-Algoritma-Eviksi-LRU-LFU.md)
- [Module 02: Redis Internals, Distributed Locks (Redlock), & Mitigasi Cache Stampede / Penetration](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/Module-02-Redis-Internals-Distributed-Lock-dan-Cache-Stampede.md)
- [Praktikum Hands-on: Simulator Cache-Aside vs Write-Through dengan Eviksi LRU](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/hands-on/m01/caching_patterns_lru_sim.js)
- [Praktikum Hands-on: Simulator Redis Distributed Lock (Redlock) & Mutex Reentrancy](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/hands-on/m02/redis_distributed_lock_sim.js)
- [BAB 06 Quiz & Chapter Challenge](./BAB-06-Strategi-Caching-dan-In-Memory-Stores/BAB-06-Quiz-dan-Challenge.md)

### [BAB 07: Asynchronous Processing & Message Brokers](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/)
- [Module 01: Message Queues vs Event Streaming (RabbitMQ AMQP vs Apache Kafka vs Redis Streams)](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/Module-01-Message-Queues-vs-Event-Streaming-Kafka-RabbitMQ.md)
- [Module 02: Idempotent Consumers, Dead Letter Queues (DLQ), Exactly-Once Semantics, & Outbox Pattern](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/Module-02-Idempotent-Consumers-DLQ-dan-Transactional-Outbox.md)
- [Praktikum Hands-on: Simulator Event Streaming Kafka Log Partitions & Consumer Groups](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/hands-on/m01/kafka_partitions_consumer_sim.js)
- [Praktikum Hands-on: Simulator Transactional Outbox Pattern & CDC Engine](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/hands-on/m02/transactional_outbox_cdc_sim.js)
- [BAB 07 Quiz & Chapter Challenge](./BAB-07-Asynchronous-Processing-dan-Message-Brokers/BAB-07-Quiz-dan-Challenge.md)

### [BAB 08: Autentikasi, Otorisasi, & Keamanan Backend (OWASP)](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/)
- [Module 01: Authentication & Authorization: Session vs JWT, OAuth 2.0, OpenID Connect (OIDC), & PKCE](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/Module-01-Auth-Session-JWT-OAuth2-OIDC-PKCE.md)
- [Module 02: OWASP API Security Top 10, SQLi, CSRF, Token Bucket Rate Limiting, & Data Encryption](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/Module-02-OWASP-API-Security-Top-10-Rate-Limiting-Enkripsi.md)
- [Praktikum Hands-on: Simulator OAuth 2.0 Authorization Code Flow with PKCE](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/hands-on/m01/oauth2_pkce_auth_flow_sim.js)
- [Praktikum Hands-on: Simulator Token Bucket & Leaky Bucket Rate Limiting Middleware](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/hands-on/m02/token_bucket_rate_limiter_sim.js)
- [BAB 08 Quiz & Chapter Challenge](./BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/BAB-08-Quiz-dan-Challenge.md)

### [BAB 09: Pengujian Backend (Testing), Kualitas Kode, & CI/CD](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/)
- [Module 01: Piramida Pengujian: Unit Testing, Integration Testing, Testcontainers, & Contract Testing](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/Module-01-Piramida-Testing-Integration-Testcontainers-Contract.md)
- [Module 02: Static Analysis, Linter, CI/CD Pipeline Automation, Smoke Tests, & Load Testing](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/Module-02-Static-Analysis-CICD-Automation-dan-Load-Testing.md)
- [Praktikum Hands-on: Simulator Unit vs Integration Test Suite dengan Database Mocks](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/hands-on/m01/backend_testing_framework_sim.js)
- [Praktikum Hands-on: Simulator High-Throughput Load Testing & Latency Percentiles Engine](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/hands-on/m02/load_testing_latency_p99_sim.js)
- [BAB 09 Quiz & Chapter Challenge](./BAB-09-Pengujian-Backend-Kualitas-Kode-dan-CICD/BAB-09-Quiz-dan-Challenge.md)

### [BAB 10: Arsitektur Backend Lanjutan & Skalabilitas Sistem](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/)
- [Module 01: Evolusi Arsitektur: Monolith vs Modular Monolith vs Microservices (Domain-Driven Design)](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/Module-01-Monolith-Modular-Microservices-dan-DDD.md)
- [Module 02: Transaksi Terdistribusi: Two-Phase Commit (2PC) vs Saga Pattern, Event Sourcing, & CQRS](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/Module-02-Transaksi-Terdistribusi-Saga-Event-Sourcing-CQRS.md)
- [Praktikum Hands-on: Simulator Domain-Driven Design (Bounded Context & Aggregates)](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/hands-on/m01/ddd_aggregate_root_sim.js)
- [Praktikum Hands-on: Simulator Saga Orchestrator dengan Automated Compensating Transactions](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/hands-on/m02/saga_orchestrator_compensating_sim.js)
- [BAB 10 Quiz & Chapter Challenge](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/BAB-10-Quiz-dan-Challenge.md)

---

## 🏆 [CAPSTONE PROJECT: Enterprise Omnichannel Payment & Core Banking Backend](./CAPSTONE-PROJECT-Enterprise-Omnichannel-Payment-Backend.md)
- [Dokumen Spesifikasi & Arsitektur Capstone](./CAPSTONE-PROJECT-Enterprise-Omnichannel-Payment-Backend.md)
- [Praktikum Hands-on: PayPulse Enterprise Payment & Ledger Engine Simulator](./hands-on/capstone/paypulse_payment_engine.js)
Arsitektur dan implementasi backend enterprise end-to-end yang memadukan REST/gRPC API, RDBMS transactions dengan isolasi ketat, event streaming Outbox pattern, caching Redis multi-layer, rate limiting, dan Saga orchestration untuk transfer dana antar bank.
