# SYSTEM DESIGN MASTERY: ROADMAP TO ARCHITECT
**Panduan Komprehensif Arsitektur Sistem Terdistribusi Berskala Besar**  
*Berdasarkan kurikulum resmi [roadmap.sh/system-design](https://roadmap.sh/system-design)*

---

## 📌 Course Overview
Kursus ini dirancang untuk membawa Anda dari pemahaman dasar arsitektur web hingga mampu merancang, menganalisis trade-off, dan mengoperasikan sistem terdistribusi berskala tinggi (*large-scale distributed systems*).

Di dunia nyata, tidak ada arsitektur yang "sempurna" — setiap keputusan arsitektur adalah kompromi (*trade-off*) antara performa, konsistensi, kompleksitas, ketersediaan, dan biaya. Di sini Anda tidak hanya mempelajari komponen sistem (Load Balancer, Caching, Database Sharding, Message Queue), tetapi juga memahami **kapan harus menggunakannya, kapan tidak boleh menggunakannya, dan bagaimana mendiagnosis bottleneck**.

---

## 🗺️ Learning Roadmap & Struktur Bab

```text
COURSE: SYSTEM DESIGN MASTERY
│
├── BAB 01 — Fondasi Skalabilitas & Metrik Sistem
│   ├── Module 01: Skalabilitas Vertikal vs Horizontal & Bottleneck Sistem
│   ├── Module 02: Latency, Throughput, dan Trade-off Kinerja
│   ├── Module 03: Ketersediaan Tinggi (High Availability), SLA, SLO, & SLI
│   └── Module 04: Teori Terdistribusi: CAP Theorem & PACELC Theorem
│
├── BAB 02 — Edge Computing, DNS, & Jaringan Distribusi
│   ├── Module 01: DNS & Global Traffic Management (Anycast, GeoDNS, TTL)
│   └── Module 02: Content Delivery Network (CDN): Push vs Pull & Edge Invalidation
│
├── BAB 03 — Traffic Management, Load Balancing, & Gateway
│   ├── Module 01: Reverse Proxy vs Forward Proxy
│   ├── Module 02: Load Balancer (Layer 4 vs Layer 7, Algoritma & Consistent Hashing)
│   └── Module 03: API Gateway & Service Mesh
│
├── BAB 04 — Caching Terdistribusi & Strategi Optimasi Data
│   ├── Module 01: Caching Layer & Pola Akses (Cache-Aside, Write-Through, Write-Behind)
│   ├── Module 02: Eviction Policies (LRU/LFU), Cache Stampede, Penetration, & Breakdown
│   └── Module 03: Distributed In-Memory Datastores (Redis & Memcached)
│
├── BAB 05 — Arsitektur Basis Data & Skalabilitas Data
│   ├── Module 01: RDBMS Scaling — B-Tree Indexing, Query Optimization, & ACID
│   ├── Module 02: Database Replication, Read Replicas, & Failover Management
│   ├── Module 03: Database Partitioning & Sharding Strategies
│   └── Module 04: NoSQL Databases (Document, Key-Value, Columnar, Graph) & BASE
│
├── BAB 06 — Protokol Komunikasi & Antar Layanan
│   ├── Module 01: REST vs GraphQL vs gRPC (Protobuf, HTTP/2)
│   └── Module 02: Real-time Communication (WebSockets, SSE, Long Polling, Webhooks)
│
├── BAB 07 — Asynchronous Processing, Message Brokers, & Streaming
│   ├── Module 01: Message Queues vs Event Streaming (RabbitMQ vs Apache Kafka)
│   ├── Module 02: Delivery Guarantees, Idempotency, & Dead Letter Queue (DLQ)
│   └── Module 03: Event-Driven Architecture, CQRS, & Event Sourcing
│
├── BAB 08 — Resiliensi Sistem, Keamanan, & Rate Limiting
│   ├── Module 01: Rate Limiting & Traffic Shaping (Token Bucket, Leaky Bucket, Sliding Window)
│   ├── Module 02: Fault Tolerance: Circuit Breaker, Retry with Jitter, & Bulkhead
│   └── Module 03: Defensive Security: DDoS Mitigation, Authentication, & Zero Trust
│
├── BAB 09 — Observabilitas, Monitoring, & Estimasi Kapasitas
│   ├── Module 01: Back-of-the-Envelope Estimation & Capacity Planning
│   └── Module 02: Distributed Tracing, Structured Logging, & Metrik (OpenTelemetry, Prometheus)
│
├── BAB 10 — Studi Kasus Nyata & Desain Arsitektur End-to-End
│   ├── Module 01: Desain Distributed Rate Limiter
│   ├── Module 02: Desain URL Shortener Skala Global (TinyURL)
│   ├── Module 03: Desain Chat System Real-time (WhatsApp / Discord)
│   └── Module 04: Desain Social Media Feed & Fan-out Engine (Twitter / Instagram)
│
└── CAPSTONE PROJECT: End-to-End Scalable E-Commerce / Streaming Platform Architecture
```

---

## 🎯 Navigasi Materi

- [BAB 01 — Fondasi Skalabilitas & Metrik Sistem](./BAB-01-Fondasi-Skalabilitas/)
  - [Module 01: Skalabilitas Vertikal vs Horizontal](./BAB-01-Fondasi-Skalabilitas/Module-01-Skalabilitas-Vertikal-vs-Horizontal.md)
  - [Module 02: Latency, Throughput, & Trade-off Kinerja](./BAB-01-Fondasi-Skalabilitas/Module-02-Latency-Throughput-Tradeoff.md)
  - [Module 03: High Availability, SLA, SLO, & SLI](./BAB-01-Fondasi-Skalabilitas/Module-03-High-Availability-SLA-SLO-SLI.md)
  - [Module 04: Teori Terdistribusi: CAP Theorem & PACELC](./BAB-01-Fondasi-Skalabilitas/Module-04-CAP-PACELC-Theorem.md)
  - [Evaluasi & Quiz BAB 01](./BAB-01-Fondasi-Skalabilitas/BAB-01-Quiz-dan-Challenge.md)
- [BAB 02 — Edge Computing, DNS, & Jaringan Distribusi](./BAB-02-Edge-DNS-CDN/)
  - [Module 01: DNS & Global Traffic Management](./BAB-02-Edge-DNS-CDN/Module-01-DNS-dan-Global-Traffic-Management.md)
  - [Module 02: Content Delivery Network (CDN)](./BAB-02-Edge-DNS-CDN/Module-02-Content-Delivery-Network-CDN.md)
  - [Evaluasi & Quiz BAB 02](./BAB-02-Edge-DNS-CDN/BAB-02-Quiz-dan-Challenge.md)
- [BAB 03 — Traffic Management, Load Balancing, & Gateway](./BAB-03-Traffic-Management-Load-Balancing/)
  - [Module 01: Reverse Proxy vs Forward Proxy](./BAB-03-Traffic-Management-Load-Balancing/Module-01-Reverse-Proxy-vs-Forward-Proxy.md)
  - [Module 02: Load Balancer L4 vs L7 & Algoritma](./BAB-03-Traffic-Management-Load-Balancing/Module-02-Load-Balancer-L4-L7-dan-Algorithms.md)
  - [Module 03: API Gateway & Service Mesh](./BAB-03-Traffic-Management-Load-Balancing/Module-03-API-Gateway-dan-Service-Mesh.md)
  - [Evaluasi & Quiz BAB 03](./BAB-03-Traffic-Management-Load-Balancing/BAB-03-Quiz-dan-Challenge.md)
- [BAB 04 — Caching Terdistribusi & Strategi Optimasi Data](./BAB-04-Caching-Terdistribusi/)
  - [Module 01: Caching Layers & Pola Akses](./BAB-04-Caching-Terdistribusi/Module-01-Caching-Layers-dan-Pola-Akses.md)
  - [Module 02: Eviction Policies & Mitigasi Anomali](./BAB-04-Caching-Terdistribusi/Module-02-Eviction-Policies-dan-Mitigasi-Anomali.md)
  - [Module 03: In-Memory Datastores (Redis & Cluster)](./BAB-04-Caching-Terdistribusi/Module-03-Redis-dan-Memcached-Deep-Dive.md)
  - [Evaluasi & Quiz BAB 04](./BAB-04-Caching-Terdistribusi/BAB-04-Quiz-dan-Challenge.md)
- [BAB 05 — Arsitektur Basis Data & Skalabilitas Data](./BAB-05-Arsitektur-Basis-Data/)
  - [Module 01: RDBMS Scaling, Indexing, & ACID](./BAB-05-Arsitektur-Basis-Data/Module-01-RDBMS-Scaling-Indexing-dan-ACID.md)
  - [Module 02: Database Replication & Failover](./BAB-05-Arsitektur-Basis-Data/Module-02-Database-Replication-dan-Failover.md)
  - [Module 03: Database Partitioning & Sharding](./BAB-05-Arsitektur-Basis-Data/Module-03-Database-Partitioning-dan-Sharding.md)
  - [Module 04: NoSQL Databases & BASE](./BAB-05-Arsitektur-Basis-Data/Module-04-NoSQL-Databases-dan-BASE.md)
  - [Evaluasi & Quiz BAB 05](./BAB-05-Arsitektur-Basis-Data/BAB-05-Quiz-dan-Challenge.md)
- [BAB 06 — Protokol Komunikasi & Antar Layanan](./BAB-06-Protokol-Komunikasi/)
  - [Module 01: REST vs GraphQL vs gRPC](./BAB-06-Protokol-Komunikasi/Module-01-REST-GraphQL-dan-gRPC.md)
  - [Module 02: Real-time Communication (WebSockets, SSE, Polling)](./BAB-06-Protokol-Komunikasi/Module-02-Realtime-WebSockets-SSE-Polling.md)
  - [Evaluasi & Quiz BAB 06](./BAB-06-Protokol-Komunikasi/BAB-06-Quiz-dan-Challenge.md)
- [BAB 07 — Asynchronous Processing, Message Brokers, & Streaming](./BAB-07-Asynchronous-Processing/)
  - [Module 01: Message Queues vs Event Streaming (RabbitMQ vs Kafka)](./BAB-07-Asynchronous-Processing/Module-01-Message-Queues-vs-Event-Streaming.md)
  - [Module 02: Delivery Guarantees, Idempotency, & DLQ](./BAB-07-Asynchronous-Processing/Module-02-Delivery-Guarantees-Idempotency-dan-DLQ.md)
  - [Module 03: Event-Driven Architecture, CQRS, & Event Sourcing](./BAB-07-Asynchronous-Processing/Module-03-Event-Driven-Architecture-CQRS-dan-Event-Sourcing.md)
  - [Evaluasi & Quiz BAB 07](./BAB-07-Asynchronous-Processing/BAB-07-Quiz-dan-Challenge.md)
- [BAB 08 — Resiliensi Sistem, Keamanan, & Rate Limiting](./BAB-08-Resiliensi-Sistem-Keamanan/)
  - [Module 01: Rate Limiting & Traffic Shaping](./BAB-08-Resiliensi-Sistem-Keamanan/Module-01-Rate-Limiting-dan-Traffic-Shaping.md)
  - [Module 02: Fault Tolerance: Circuit Breaker, Retry with Jitter, & Bulkhead](./BAB-08-Resiliensi-Sistem-Keamanan/Module-02-Fault-Tolerance-Circuit-Breaker-dan-Bulkhead.md)
  - [Module 03: Defensive Security: Authentication, Authorization, & Zero Trust](./BAB-08-Resiliensi-Sistem-Keamanan/Module-03-Defensive-Security-Authentication-dan-Zero-Trust.md)
  - [Evaluasi & Quiz BAB 08](./BAB-08-Resiliensi-Sistem-Keamanan/BAB-08-Quiz-dan-Challenge.md)
- [BAB 09 — Observabilitas, Monitoring, & Estimasi Kapasitas](./BAB-09-Observabilitas-Monitoring-Estimasi/)
  - [Module 01: Back-of-the-Envelope Estimation & Capacity Planning](./BAB-09-Observabilitas-Monitoring-Estimasi/Module-01-Back-of-the-Envelope-Estimation-dan-Capacity-Planning.md)
  - [Module 02: Distributed Tracing, Structured Logging, & Metrik](./BAB-09-Observabilitas-Monitoring-Estimasi/Module-02-Distributed-Tracing-Structured-Logging-dan-Metrik.md)
  - [Evaluasi & Quiz BAB 09](./BAB-09-Observabilitas-Monitoring-Estimasi/BAB-09-Quiz-dan-Challenge.md)
- [BAB 10 — Studi Kasus Nyata & Desain Arsitektur End-to-End](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/)
  - [Module 01: Desain Distributed Rate Limiter](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/Module-01-Desain-Distributed-Rate-Limiter.md)
  - [Module 02: Desain URL Shortener Skala Global (TinyURL)](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/Module-02-Desain-URL-Shortener-Global-TinyURL.md)
  - [Module 03: Desain Chat System Real-Time (WhatsApp / Discord)](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/Module-03-Desain-Chat-System-Real-Time-WhatsApp-Discord.md)
  - [Module 04: Desain Social Media Feed & Fan-Out Engine (Twitter / Instagram)](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/Module-04-Desain-Social-Media-Feed-dan-Fan-Out-Engine.md)
  - [Evaluasi & Quiz BAB 10](./BAB-10-Studi-Kasus-Arsitektur-End-to-End/BAB-10-Quiz-dan-Challenge.md)
- [🏆 CAPSTONE PROJECT: End-to-End Scalable Platform Architecture ("NusantaraStream")](./CAPSTONE-PROJECT-Scalable-Architecture.md)

---

## 🎓 Status Kurikulum: 100% SELESAI (COMPLETE)
Seluruh 10 Bab kurikulum, modul pembelajaran, script laboratorium hands-on yang dapat langsung dieksekusi, evaluasi kuis, serta Capstone Project telah selesai disusun dan disimpan ke dalam direktori lokal workspace.

