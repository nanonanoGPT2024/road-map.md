# Silabus Kurikulum: Software Design & Architecture

> **Panduan Kurikulum Arsitektur Perangkat Lunak Tingkat Lanjut (Enterprise Grade)**  
> Disusun berdasarkan pemetaan kompetensi industri global dan standar referensi resmi *roadmap.sh: Software Design Architecture*.

---

## 1. Course Overview & Mindset

Menjadi seorang *Software Architect* bukan sekadar memahami sintaks bahasa pemrograman atau menguasai satu *framework* tertentu. Peran arsitek menuntut transisi cara berpikir dari **eksekusi kode tingkat rendah (*tactical coding*)** menuju **rekayasa sistem holistik (*systemic thinking*)**, pengambilan keputusan berbasis *trade-off*, serta perancangan struktur sistem yang mampu bertahan terhadap skala, waktu, dan dinamika organisasi.

### Prinsip Fondasi Kurikulum:
1. **Trade-off Over Dogma:** Tidak ada arsitektur yang "terbaik"; yang ada hanyalah kombinasi atribut kualitas (*quality attributes*) dengan kompromi paling optimal bagi konteks bisnis tertentu.
2. **Kopling & Kohesi sebagai Kompas:** Seluruh pola arsitektur—mulai dari fungsi sederhana hingga *microservices* terdistribusi—bermuara pada pengelolaan batas (*boundary management*), pemisahan kepentingan (*separation of concerns*), dan pengurangan derajat ketergantungan.
3. **Konvergensi Bisnis dan Teknis (DDD):** Arsitektur perangkat lunak yang sukses adalah representasi langsung dari model domain bisnis, bukan sekadar abstraksi teknis yang terisolasi.
4. **Resilience by Design:** Dalam sistem modern berskala besar, kegagalan (*failure*) adalah keniscayaan, bukan anomali. Sistem harus dirancang untuk menoleransi gangguan, mampu pulih mandiri (*self-healing*), dan mempertahankan ketersediaan data secara konsisten.
5. **Conway's Law & Evolusi:** Struktur arsitektur mencerminkan struktur komunikasi organisasi. Kurikulum ini mengajarkan arsitektur yang modular dan evolusioner (*evolutionary architecture*), siap bertransformasi seiring pertumbuhan skala organisasi.

---

## 2. Learning Roadmap

Berikut adalah peta jalan pembelajaran komprehensif 10 Bab yang terstruktur secara berkesinambungan:

```text
Software Design & Architecture Roadmap
│
├── [Bab 01] Fondasi Arsitektur Perangkat Lunak & Paradigma Desain
│   ├── Modul 01: Prinsip Rekayasa Sistem, Atribut Kualitas (NFR), & Trade-offs
│   ├── Modul 02: Paradigma Pemrograman (OOP, FP, Data-Oriented) dalam Desain Sistem
│   └── Modul 03: Arsitektur vs Desain: Scope, Batasan, dan Peran Software Architect
│
├── [Bab 02] Prinsip Desain Tingkat Kode: Object-Oriented, SOLID, & GRASP
│   ├── Modul 01: Analisis Kopling (Coupling) dan Kohesi (Cohesion) secara Formal
│   ├── Modul 02: Penerapan Mendalam Prinsip SOLID pada Sistem Modern
│   └── Modul 03: Desain Pola Tanggung Jawab dengan GRASP & Refaktorisasi Code Smells
│
├── [Bab 03] Pola Desain Klasik (GoF Patterns) & Idiom Arsitektur Modern
│   ├── Modul 01: Pola Kreasi (Creational) & Dekopling Instansiasi Kompleks
│   ├── Modul 02: Pola Struktural (Structural) & Pengelolaan Komposisi Objek
│   └── Modul 03: Pola Perilaku (Behavioral) & Koordinasi Alur Kerja Antar-Objek
│
├── [Bab 04] Arsitektur Moduler & Layered: Monolith Modern hingga Hexagonal
│   ├── Modul 01: Traditional N-Tier vs Modular Monolith: Boundary Enforcement
│   ├── Modul 02: Clean Architecture & Onion Architecture: The Dependency Inversion Principle
│   └── Modul 03: Hexagonal Architecture (Ports and Adapters) Implementatif
│
├── [Bab 05] Domain-Driven Design (DDD): Strategic & Tactical Modeling
│   ├── Modul 01: Strategic DDD: Ubiquitous Language, Bounded Context, & Context Mapping
│   ├── Modul 02: Tactical DDD: Entities, Value Objects, Aggregates, & Domain Services
│   └── Modul 03: Integrasi Event: Domain Events, Integration Events, & Repository Pattern
│
├── [Bab 06] Pola Arsitektur Sistem Terdistribusi & Microservices
│   ├── Modul 01: Dekomposisi Sistem: Monolith-to-Microservices Decomposition Strategies
│   ├── Modul 02: Protokol Komunikasi Inter-Service: Synchronous (REST/gRPC) vs Asynchronous
│   └── Modul 03: Pola Transaksi Terdistribusi: 2PC vs Saga Pattern vs Transactional Outbox
│
├── [Bab 07] Event-Driven Architecture (EDA) & Pola Konsistensi Data
│   ├── Modul 01: Prinsip Inti EDA: Event Brokers, Topologi Broker vs Mediator
│   ├── Modul 02: Event Sourcing & CQRS (Command Query Responsibility Segregation)
│   └── Modul 03: Konsistensi Data: Eventual Consistency, Idempotency, & Dead Letter Queue
│
├── [Bab 08] Skalabilitas, Partisi Data, & Strategi Caching
│   ├── Modul 01: Horizontal vs Vertical Scaling, Load Balancing Topologies, & Statelessness
│   ├── Modul 02: Pemartisian Basis Data: Sharding, Replikasi, Read/Write Replica, & CAP/PACELC
│   └── Modul 03: Strategi Caching Terdistribusi: Cache Patterns, Eviction, & Invalidation
│
├── [Bab 09] Ketahanan Sistem (Resilience), Keandalan, & Observabilitas
│   ├── Modul 01: Pola Ketahanan: Circuit Breaker, Bulkhead, Retry, Backoff, & Rate Limiting
│   ├── Modul 02: Observabilitas Terdistribusi: Distributed Tracing, Structured Logging, & Metrik
│   └── Modul 03: Rekayasa Kegagalan: Chaos Engineering, Graceful Degradation, & Disaster Recovery
│
└── [Bab 10] Dokumentasi Arsitektur, Tata Kelola (Governance), & Evolusi
    ├── Modul 01: Visualisasi Arsitektur: Standar C4 Model & Diagram Komponen Tingkat Lanjut
    ├── Modul 02: Architectural Decision Records (ADR) & Manajemen Technical Debt
    └── Modul 03: Evolutionary Architecture: Fitness Functions, Tata Kelola, & Conway's Law
```

---

## 3. Navigasi Kurikulum Detail

| Bab | Judul Bab | Fokus Utama | Tautan Modul |
| :--- | :--- | :--- | :--- |
| **01** | **Fondasi Arsitektur Perangkat Lunak & Paradigma Desain** | Pemikiran sistemik, dekonstruksi *Non-Functional Requirements* (NFRs/Quality Attributes), kompromi arsitektural (*trade-offs*), serta pengaruh paradigma OOP, FP, dan Data-Oriented terhadap struktur aplikasi berskala besar. | • [01-fondasi-dan-paradigma/01-prinsip-rekayasa-sistem.md](01-fondasi-dan-paradigma/01-prinsip-rekayasa-sistem.md)<br>• [01-fondasi-dan-paradigma/02-paradigma-pemrograman.md](01-fondasi-dan-paradigma/02-paradigma-pemrograman.md)<br>• [01-fondasi-dan-paradigma/03-arsitektur-vs-desain.md](01-fondasi-dan-paradigma/03-arsitektur-vs-desain.md) |
| **02** | **Prinsip Desain Tingkat Kode: Object-Oriented, SOLID, & GRASP** | Analisis formal metrik kopling (*afferent/efferent coupling*) dan kohesi (*LCOM*), penerapan absolut SOLID pada domain modern, serta pemanfaatan prinsip-prinsip GRASP untuk mendistribusikan tanggung jawab objek secara elegan. | • [02-prinsip-desain-solid-grasp/01-analisis-kopling-kohesi.md](02-prinsip-desain-solid-grasp/01-analisis-kopling-kohesi.md)<br>• [02-prinsip-desain-solid-grasp/02-penerapan-mendalam-solid.md](02-prinsip-desain-solid-grasp/02-penerapan-mendalam-solid.md)<br>• [02-prinsip-desain-solid-grasp/03-grasp-dan-refactoring.md](02-prinsip-desain-solid-grasp/03-grasp-dan-refactoring.md) |
| **03** | **Pola Desain Klasik (GoF Patterns) & Idiom Arsitektur Modern** | Rekontekstualisasi 23 GoF Design Patterns dalam rekayasa perangkat lunak kontemporer: dekonstruksi *over-engineering*, idiom *dependency injection*, *pipeline*, *middleware*, dan implementasi fungsional dari pola desain klasik. | • [03-pola-desain-gof/01-pola-kreasi-lanjutan.md](03-pola-desain-gof/01-pola-kreasi-lanjutan.md)<br>• [03-pola-desain-gof/02-pola-struktural-modern.md](03-pola-desain-gof/02-pola-struktural-modern.md)<br>• [03-pola-desain-gof/03-pola-perilaku-terdistribusi.md](03-pola-desain-gof/03-pola-perilaku-terdistribusi.md) |
| **04** | **Arsitektur Moduler & Layered: Monolith Modern hingga Hexagonal** | Batasan struktural *monolith* modular, mitigasi *spaghetti architecture*, pemisahan *core business logic* dari detail infrastruktur melalui Clean Architecture, Onion Architecture, dan Hexagonal Architecture (Ports & Adapters). | • [04-arsitektur-moduler-dan-layered/01-modular-monolith.md](04-arsitektur-moduler-dan-layered/01-modular-monolith.md)<br>• [04-arsitektur-moduler-dan-layered/02-clean-dan-onion-architecture.md](04-arsitektur-moduler-dan-layered/02-clean-dan-onion-architecture.md)<br>• [04-arsitektur-moduler-dan-layered/03-hexagonal-ports-and-adapters.md](04-arsitektur-moduler-dan-layered/03-hexagonal-ports-and-adapters.md) |
| **05** | **Domain-Driven Design (DDD): Strategic & Tactical Modeling** | Metodologi *Domain-Driven Design* end-to-end: pemetaan batas domain bisnis via *Bounded Context*, *Ubiquitous Language*, orkestrasi relasi via *Context Mapping*, serta implementasi taktis agregat (*Aggregates*), entitas, dan *Value Objects*. | • [05-domain-driven-design/01-strategic-ddd-bounded-context.md](05-domain-driven-design/01-strategic-ddd-bounded-context.md)<br>• [05-domain-driven-design/02-tactical-ddd-modeling.md](05-domain-driven-design/02-tactical-ddd-modeling.md)<br>• [05-domain-driven-design/03-integrasi-domain-events.md](05-domain-driven-design/03-integrasi-domain-events.md) |
| **06** | **Pola Arsitektur Sistem Terdistribusi & Microservices** | Pemecahan sistem monolitik (*service decomposition*), integrasi antar-layanan melalui protokol sinkron (gRPC/REST) vs asinkron, serta resolusi integritas data menggunakan pola transaksi terdistribusi (*Saga Pattern*, *Transactional Outbox*). | • [06-arsitektur-terdistribusi-microservices/01-dekomposisi-microservices.md](06-arsitektur-terdistribusi-microservices/01-dekomposisi-microservices.md)<br>• [06-arsitektur-terdistribusi-microservices/02-inter-service-communication.md](06-arsitektur-terdistribusi-microservices/02-inter-service-communication.md)<br>• [06-arsitektur-terdistribusi-microservices/03-transaksi-terdistribusi-saga.md](06-arsitektur-terdistribusi-microservices/03-transaksi-terdistribusi-saga.md) |
| **07** | **Event-Driven Architecture (EDA) & Pola Konsistensi Data** | Desain sistem berbasis aliran peristiwa (*event streaming*), isolasi baca/tulis melalui CQRS, auditabilitas absolut dengan *Event Sourcing*, penanganan *eventual consistency*, semantik pengiriman (*at-least-once*, *idempotency*), serta mitigasi antrean buntu (*DLQ*). | • [07-event-driven-architecture/01-prinsip-broker-dan-mediator.md](07-event-driven-architecture/01-prinsip-broker-dan-mediator.md)<br>• [07-event-driven-architecture/02-event-sourcing-dan-cqrs.md](07-event-driven-architecture/02-event-sourcing-dan-cqrs.md)<br>• [07-event-driven-architecture/03-eventual-consistency-idempotency.md](07-event-driven-architecture/03-eventual-consistency-idempotency.md) |
| **08** | **Skalabilitas, Partisi Data, & Strategi Caching** | Pola rekayasa sistem untuk *high-throughput*: *stateless services*, *database sharding*, strategi replikasi, mitigasi kompromi teorema CAP dan PACELC, topologi *caching* berlapis (*write-through*, *write-behind*, *cache-aside*), dan mitigasi *cache stampede*. | • [08-skalabilitas-dan-caching/01-prinsip-skalabilitas-horizontal.md](08-skalabilitas-dan-caching/01-prinsip-skalabilitas-horizontal.md)<br>• [08-skalabilitas-dan-caching/02-partisi-data-sharding-cap.md](08-skalabilitas-dan-caching/02-partisi-data-sharding-cap.md)<br>• [08-skalabilitas-dan-caching/03-topologi-dan-invalidation-cache.md](08-skalabilitas-dan-caching/03-topologi-dan-invalidation-cache.md) |
| **09** | **Ketahanan Sistem (Resilience), Keandalan, & Observabilitas** | Rekayasa sistem nir-henti (*fault-tolerant*): implementasi *Circuit Breaker*, *Bulkhead*, *Rate Limiting*, korelasi jejak terdistribusi (*W3C Trace Context*), agregasi log terstruktur, metrik telemetri, serta verifikasi proaktif melalui *Chaos Engineering*. | • [09-resilience-dan-observabilitas/01-pola-ketahanan-sistem.md](09-resilience-dan-observabilitas/01-pola-ketahanan-sistem.md)<br>• [09-resilience-dan-observabilitas/02-observabilitas-telemetri.md](09-resilience-dan-observabilitas/02-observabilitas-telemetri.md)<br>• [09-resilience-dan-observabilitas/03-chaos-engineering-failover.md](09-resilience-dan-observabilitas/03-chaos-engineering-failover.md) |
| **10** | **Dokumentasi Arsitektur, Tata Kelola (Governance), & Evolusi** | Standardisasi komunikasi cetak biru arsitektur menggunakan C4 Model, formalisasi keputusan teknis melalui *Architectural Decision Records* (ADR), arsitektur evolusioner berbasis *Automated Fitness Functions*, serta mitigasi hukum Conway (*Inverse Conway Maneuver*). | • [10-dokumentasi-dan-evolusi/01-visualisasi-c4-model.md](10-dokumentasi-dan-evolusi/01-visualisasi-c4-model.md)<br>• [10-dokumentasi-dan-evolusi/02-adr-dan-technical-debt.md](10-dokumentasi-dan-evolusi/02-adr-dan-technical-debt.md)<br>• [10-dokumentasi-dan-evolusi/03-evolutionary-architecture-conway.md](10-dokumentasi-dan-evolusi/03-evolutionary-architecture-conway.md) |

---

## 4. Spesifikasi Capstone Project Enterprise

Sebagai syarat kelulusan kurikulum ini, siswa wajib merancang dan mengimplementasikan cetak biru arsitektur untuk sistem skala *enterprise*.

```text
               +--------------------------------------------------------+
               |             GLOBAL API GATEWAY / EDGE PROXY            |
               |       (Rate Limiter, Auth Validation, TLS Offload)     |
               +---------------------------+----------------------------+
                                           |
                    +----------------------+---------------------+
                    |                                            |
         [SYNC: gRPC / HTTP2]                        [ASYNC: EVENT STREAM]
                    |                                            |
                    v                                            v
     +------------------------------+             +------------------------------+
     |   CORE TRANSACTION SERVICE   |             |   CLEARING & SETTLEMENT      |
     |   (Hexagonal + Tactical DDD) |             |   (Event-Driven Consumer)    |
     +--------------+---------------+             +--------------+---------------+
                    |                                            |
         +----------+----------+                                 |
         |                     |                                 |
         v                     v                                 v
+-----------------+   +-----------------+             +--------------------+
| Transactional   |   | Event Store /   |             | Ledger Read-Model  |
| DB (PostgreSQL) |   | Outbox Table    |             | (Distributed NoSQL)|
+-----------------+   +--------+--------+             +--------------------+
                               |
                               v
                  +---------------------------+
                  |   KAFKA MESSAGE CLUSTER   |
                  |  (Partitioned by Account) |
                  +---------------------------+
```

### Judul Proyek:
**Global Real-Time Multi-Tenant Core Banking & Payment Clearing Platform**

### Latar Belakang Bisnis:
Institusi finansial global membutuhkan platform pemrosesan transaksi dan kliring instan lintas negara. Platform harus menangani volume transaksi masif tanpa risiko inkonsistensi saldo (*double-spending*), mematuhi standar regulasi finansial internasional (PCI-DSS & ISO-20022), serta memiliki ketersediaan tinggi (*zero downtime*) saat terjadi pemadaman parsial pada salah satu pusat data kawasan (*data center zone*).

### Non-Functional Requirements (NFR) Minimum:
1. **Throughput & Latency:** Mampu memproses minimal **10.000 transaksi per detik (TPS)** pada kondisi beban puncak (*peak load*) dengan latensi *99th percentile* ($P_{99}$) di bawah **80 milidetik**.
2. **Ketersediaan (Availability):** Mencapai tingkat ketersediaan **99.999% (*five nines*)**, toleran terhadap kegagalan salah satu *Availability Zone* (AZ) tanpa interupsi layanan (*automatic failover*).
3. **Integritas Data (Data Integrity):** Penolakan total terhadap inkonsistensi data transaksi finansial (*Strict Consistency* pada *Ledger Aggregates*). Saldo rekening tidak boleh mengalami desinkronisasi dalam kondisi partisi jaringan (*PACELC: PC/EC bias pada write engine*).
4. **Auditabilitas & Regulasi:** Setiap mutasi saldo akun wajib tercatat dalam model *append-only* permanen (*immutable ledger*) menggunakan prinsip *Event Sourcing*.

### Komponen Teknis yang Wajib Dihasilkan:
* **Strategic & Tactical Domain Blueprint:**
  * Context Map lengkap yang membedakan bounded context: *Account Management*, *Funds Transfer Engine*, *Fraud Detection*, *Ledger Clearing*, dan *Regulatory Reporting*.
  * Spesifikasi kode agregat (*Aggregate Root*) akun finansial dengan proteksi invarian ketat dan pola *Ports & Adapters*.
* **Distributed Concurrency & Consistency Design:**
  * Implementasi *Distributed Transaction* menggunakan **Saga Pattern (Orchestration/Choreography)** untuk kliring pembayaran multi-bank.
  * Solusi pengiriman pesan andal menggunakan **Transactional Outbox Pattern** guna menjamin konsistensi antara *state store* dan *event broker*.
* **Fault-Tolerance & Resilience Matrix:**
  * Peta integrasi *resilience patterns*: Circuit Breaker, Exponential Backoff with Jitter, Idempotent Consumer (menggunakan *Idempotency Keys*), dan *Dead Letter Queue (DLQ)*.
* **Architecture Documentation Package:**
  * Diagram C4 Model lengkap: *Level 1 (System Context)*, *Level 2 (Container)*, *Level 3 (Component)*, dan *Level 4 (Code/Deployment)*.
  * Minimal **5 dokumen Architecture Decision Record (ADR)** yang mendokumentasikan keputusan kritis (e.g., pemilihan model konsistensi, strategi partisi basis data, pemilihan broker kejadian).
  * Pengujian ketahanan arsitektur menggunakan skenario *Chaos Engineering* berbasis *Fitness Functions*.