# Kurikulum Software Architect Enterprise

Selamat datang di silabus kurikulum resmi **Software Architect** berbasis standar rekayasa perangkat lunak enterprise modern. Kurikulum ini dirancang untuk mentransformasikan *Senior Software Engineer* dan *Technical Lead* menjadi seorang **Enterprise Software Architect** yang mampu menyeimbangkan kapabilitas teknis tingkat tinggi, kendala bisnis, tata kelola sistem skala masif, serta manajemen *trade-off*.

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma (Mindset Shift)
Menjadi seorang Software Architect menuntut perubahan fundamental dalam cara pandang terhadap ekosistem perangkat lunak:
* **Dari "How to Code" ke "Why & What to Trade-Off"**: Arsitektur bukan tentang menemukan solusi sempurna, melainkan menemukan kumpulan *trade-off* terbaik (kinerja vs skalabilitas, konsistensi vs ketersediaan, kecepatan rilis vs stabilitas teknis).
* **Systemic & Holistic Thinking**: Mengisolasi masalah lokal ke dalam gambaran besar organisasi, mengantisipasi dampak dari Hukum Conway (*Conway’s Law*), serta memahami implikasi infrastruktur, operasional, dan finansial (*FinOps*).
* **Evolutionary over Dogmatic**: Menghindari perangkap arsitektur menara gading (*ivory tower*). Merancang sistem yang modular, dapat dievolusikan (*evolutionary architecture*), dan diverifikasi otomatis melalui *fitness functions*.

### Sasaran Kompetensi
1. Menguasai analisis kebutuhan non-fungsional (*Quality Attributes / NFRs*) dan memetakannya ke dalam rancangan sistem berkinerja tinggi.
2. Mendesain sistem terdistribusi skala enterprise menggunakan integrasi Domain-Driven Design (DDD), Event-Driven Architecture (EDA), dan CQRS/Event Sourcing.
3. Menavigasi data terdistribusi dan menjamin konsistensi lintas *bounded context* menggunakan Saga Pattern dan model konsistensi modular.
4. Menerapkan tata kelola arsitektur berbasis kode (*Architecture as Code*), pembuatan ADR (*Architecture Decision Record*), model dokumentasi C4, dan pengujian kebugaran arsitektural (*Architectural Fitness Functions*).

---

## 2. Learning Roadmap

```plaintext
SOFTWARE ARCHITECT ROADMAP
│
├── [BAB 01] Foundations of Software Architecture & Architectural Thinking
│   ├── Mindset, Peran, & Batasan Arsitek
│   ├── Systemic Thinking & Analisis Trade-off
│   └── Dokumentasi Arsitektur (C4 Model & ADR)
│
├── [BAB 02] Software Quality Attributes & Fitness Functions
│   ├── Rekayasa NFRs, SLA, SLO, & SLI
│   ├── Automated Architectural Fitness Functions
│   └── Metode Evaluasi Arsitektur (ATAM)
│
├── [BAB 03] Architectural Styles & Paradigms
│   ├── Monolith, Modular Monolith, vs Microservices
│   ├── Event-Driven Architecture (EDA)
│   └── Space-Based & Serverless Architecture
│
├── [BAB 04] Domain-Driven Design (DDD) & Strategic Modeling
│   ├── Ubiquitous Language & Bounded Contexts
│   ├── Tactical DDD: Aggregates, Entities, Value Objects
│   └── Dekomposisi Domain & Context Mapping
│
├── [BAB 05] Distributed Data Architecture & Storage Strategies
│   ├── Polyglot Persistence & CAP/PACELC Theorem Deep-Dive
│   ├── CQRS & Event Sourcing
│   └── Distributed Transactions & Saga Pattern
│
├── [BAB 06] Integration Patterns & Communication Protocols
│   ├── Sync vs Async Communication (REST, gRPC, GraphQL)
│   ├── Enterprise Integration Patterns (EIP) & Event Streaming
│   └── API Gateway, BFF, & Service Mesh Routing
│
├── [BAB 07] Scalability, Resilience & High Availability
│   ├── Caching Topologies, Partitioning, & Sharding
│   ├── Resilience Patterns (Circuit Breaker, Bulkhead, Outbox)
│   └── Disaster Recovery (DR) & Chaos Engineering
│
├── [BAB 08] Security Architecture & Zero Trust
│   ├── Zero Trust Model & Threat Modeling (STRIDE)
│   ├── Enterprise Identity: OAuth2, OIDC, & Mutual TLS (mTLS)
│   └── Data Protection, Encryption, & Regulatory Compliance
│
├── [BAB 09] Cloud-Native Infrastructure & Observability
│   ├── Cloud-Native Foundations & Multi-Region Topology
│   ├── Telemetry Terdistribusi (OpenTelemetry, Tracing, Metrics)
│   └── Cloud FinOps & Cost-Aware Architecture
│
└── [BAB 10] Architectural Governance, Evolution & Leadership
    ├── Conway's Law, Inverse Conway, & Team Topologies
    ├── Tata Kelola RFC, Tech Radar, & Architecture Review Board
    └── Legacy Modernization & Manajemen Technical Debt
```

---

## 3. Navigasi Detail Modul Silabus

### [BAB 01: Foundations of Software Architecture & Architectural Thinking](./01-architectural-foundations-and-thinking/)
Membangun dasar berpikir arsitektur, pemisahan tanggung jawab antara arsitektur dan rekayasa detail, serta standardisasi dokumentasi keputusan teknis.
* [Modul 01: Peran, Mindset, dan Batasan Software Architect](./01-architectural-foundations-and-thinking/01-peran-mindset-software-architect.md)
* [Modul 02: Analisis Trade-off dan Systemic Thinking](./01-architectural-foundations-and-thinking/02-analisis-trade-off-dan-systemic-thinking.md)
* [Modul 03: Dokumentasi Arsitektur Berstandar: C4 Model dan ADR](./01-architectural-foundations-and-thinking/03-dokumentasi-arsitektur-c4-model-dan-adr.md)

### [BAB 02: Software Quality Attributes & Fitness Functions](./02-quality-attributes-and-fitness-functions/)
Mendefinisikan, mengukur, dan mengamankan atribut kualitas perangkat lunak (*ilities*) menggunakan pengujian arsitektur otomatis.
* [Modul 01: Rekayasa Kebutuhan NFR, Karakteristik Sistem, dan SLO/SLA/SLI](./02-quality-attributes-and-fitness-functions/01-rekayasa-kebutuhan-nfr-dan-slo-sla-sli.md)
* [Modul 02: Architectural Fitness Functions dan Guardrails Otomatis](./02-quality-attributes-and-fitness-functions/02-architectural-fitness-functions-dan-guardrails.md)
* [Modul 03: Evaluasi Arsitektur Menggunakan ATAM (Architecture Tradeoff Analysis Method)](./02-quality-attributes-and-fitness-functions/03-evaluasi-arsitektur-menggunakan-atam.md)

### [BAB 03: Architectural Styles & Paradigms](./03-architectural-styles-and-patterns/)
Komparasi kritis struktur arsitektur makro: menganalisis kapan harus memelihara monolit, kapan beralih ke microservices, dan implementasi event-driven.
* [Modul 01: Monolith, Modular Monolith, dan Microservices](./03-architectural-styles-and-patterns/01-monolith-modular-monolith-dan-microservices.md)
* [Modul 02: Event-Driven Architecture (EDA) & Reactive Systems](./03-architectural-styles-and-patterns/02-event-driven-architecture-eda.md)
* [Modul 03: Serverless, Space-Based, dan Plug-in Architecture](./03-architectural-styles-and-patterns/03-serverless-dan-space-based-architecture.md)

### [BAB 04: Domain-Driven Design (DDD) & Strategic Modeling](./04-domain-driven-design-dan-bounded-contexts/)
Menggunakan teknik Domain-Driven Design untuk memecah masalah bisnis kompleks menjadi batas-batas konteks teknis yang kohesif dan terisolasi.
* [Modul 01: Strategic DDD: Core Domain, Ubiquitous Language, dan Context Mapping](./04-domain-driven-design-dan-bounded-contexts/01-strategic-ddd-bounded-context-dan-context-mapping.md)
* [Modul 02: Tactical DDD: Entities, Value Objects, Aggregates, dan Domain Events](./04-domain-driven-design-dan-bounded-contexts/02-tactical-ddd-entities-aggregates-domain-events.md)
* [Modul 03: Strategi Dekomposisi Sistem Menuju Microservices Berbasis Boundary](./04-domain-driven-design-dan-bounded-contexts/03-dekomposisi-domain-ke-microservices.md)

### [BAB 05: Distributed Data Architecture & Storage Strategies](./05-distributed-data-architecture/)
Menjawab tantangan persistensi data dalam sistem terdistribusi, model konsistensi, transisi transaksi atomik, dan skalabilitas data masif.
* [Modul 01: Polyglot Persistence, Teorema CAP, dan Implikasi PACELC](./05-distributed-data-architecture/01-polyglot-persistence-dan-cap-theorem-deep-dive.md)
* [Modul 02: Command Query Responsibility Segregation (CQRS) & Event Sourcing](./05-distributed-data-architecture/02-cqrs-dan-event-sourcing.md)
* [Modul 03: Transaksi Terdistribusi: 2PC vs Saga Pattern (Orchestration vs Choreography)](./05-distributed-data-architecture/03-transaksi-terdistribusi-dan-saga-pattern.md)

### [BAB 06: Integration Patterns & Communication Protocols](./06-integration-patterns-dan-communication-protocols/)
Menata interkoneksi antarkomponen perangkat lunak dan protokol komunikasi sinkron/asinkron berkecepatan tinggi.
* [Modul 01: Sinkron vs Asinkron: REST, gRPC, dan GraphQL Protocol Internals](./06-integration-patterns-dan-communication-protocols/01-synchronous-vs-asynchronous-communication-grpc-rest-graphql.md)
* [Modul 02: Message Brokers & Event Streaming: Kafka vs RabbitMQ Topologies](./06-integration-patterns-dan-communication-protocols/02-event-streaming-message-brokers-kafka-rabbitmq.md)
* [Modul 03: Enterprise Integration Patterns (EIP), API Gateway, dan BFF Pattern](./06-integration-patterns-dan-communication-protocols/03-enterprise-integration-patterns-eip-dan-api-gateway.md)

### [BAB 07: Scalability, Resilience & High Availability](./07-scalability-resilience-dan-high-availability/)
Strategi mitigasi *cascading failures*, perancangan topologi redundansi, dan pembangunan sistem yang tangguh menghadapi kondisi degradasi.
* [Modul 01: Caching Topologies, Database Sharding, dan Data Partitioning](./07-scalability-resilience-dan-high-availability/01-horizontal-scaling-sharding-dan-caching-topologies.md)
* [Modul 02: Resilience Patterns: Circuit Breaker, Rate Limiting, Bulkhead, & Outbox](./07-scalability-resilience-dan-high-availability/02-resilience-patterns-circuit-breaker-retry-bulkhead.md)
* [Modul 03: Disaster Recovery Strategies, RTO/RPO, dan Chaos Engineering](./07-scalability-resilience-dan-high-availability/03-disaster-recovery-dan-chaos-engineering.md)

### [BAB 08: Security Architecture & Zero Trust](./08-security-architecture-dan-compliance/)
Mengintegrasikan postur keamanan ke dalam fondasi arsitektur, kepatuhan audit, isolasi beban kerja, dan pertahanan berlapis (*defense-in-depth*).
* [Modul 01: Zero Trust Architecture & Threat Modeling (STRIDE / DREAD)](./08-security-architecture-dan-compliance/01-zero-trust-architecture-dan-threat-modeling.md)
* [Modul 02: Enterprise Identity & Federation: OAuth2.1, OIDC, and mTLS Mesh](./08-security-architecture-dan-compliance/02-enterprise-identity-oauth2-oidc-dan-mTLS.md)
* [Modul 03: Data Protection, Cryptographic Storage, dan Audit Compliance](./08-security-architecture-dan-compliance/03-data-protection-encryption-dan-compliance-audit.md)

### [BAB 09: Cloud-Native Infrastructure & Observability](./09-cloud-native-infrastructure-dan-observability/)
Menghubungkan rancangan sistem dengan realitas runtime infrastruktur cloud, observabilitas terpusat, dan efisiensi biaya komputasi.
* [Modul 01: Cloud-Native Paradigms, Containers, Kubernetes, & Service Mesh](./09-cloud-native-infrastructure-dan-observability/01-cloud-native-foundations-kubernetes-dan-service-mesh.md)
* [Modul 02: Distributed Observability: OpenTelemetry, Distributed Tracing, & APM](./09-cloud-native-infrastructure-dan-observability/02-enterprise-observability-distributed-tracing-metrics-logs.md)
* [Modul 03: Cloud FinOps: Cost-Optimized Architectural Decision Making](./09-cloud-native-infrastructure-dan-observability/03-cloud-finops-dan-cost-aware-architecture.md)

### [BAB 10: Architectural Governance, Evolution & Leadership](./10-architectural-governance-and-technical-leadership/)
Menyinkronkan struktur organisasi dengan arsitektur teknis, kepemimpinan lintas tim, manajemen utang teknis, dan evolusi jangka panjang.
* [Modul 01: Conway's Law, Inverse Conway Maneuver, dan Team Topologies](./10-architectural-governance-and-technical-leadership/01-conways-law-dan-team-topologies.md)
* [Modul 02: Architectural Governance: RFC Processes, Tech Radars, & ARB](./10-architectural-governance-and-technical-leadership/02-governance-rfc-process-dan-tech-radar.md)
* [Modul 03: Manajemen Technical Debt dan Strategi Migrasi Sistem Legacy (Strangler Fig)](./10-architectural-governance-and-technical-leadership/03-manajemen-technical-debt-dan-evolusi-sistem-legacy.md)

---

## 4. Spesifikasi Capstone Project Enterprise

Sebagai syarat kelulusan kurikulum ini, peserta wajib merancang dan mempertahankan dokumen cetak biru arsitektur enterprise untuk proyek berskala produksi:

### Proyek: Global Omnichannel Core Payment & Settlement Platform ("OmniPay-X")

#### Skenario Masalah
OmniPay-X adalah platform pemrosesan pembayaran skala regional yang melayani transaksi e-commerce, terminal fisik (POS), dan dompet digital lintas negara dengan target:
* Menangani beban puncak hingga **150.000 Transaksi Per Detik (TPS)**.
* Ketersediaan tinggi tingkat **99.999% SLA (Five Nines)**.
* Latensi pemrosesan p99 di bawah **80 milidetik** untuk transaksi otorisasi.
* Kepatuhan ketat terhadap standar regulasi data finansial (*PCI-DSS Level 1* dan *GDPR / UU PDP*).

#### Deliverables yang Wajib Dikumpulkan
1. **Architectural Blueprint & C4 Model**:
   * Diagram Context (Level 1), Container (Level 2), dan Component (Level 3) menggunakan format Structurizr / PlantUML.
   * Diagram alur runtime untuk jalur kritis otorisasi pembayaran dan penyelesaian dana (*settlement*).
2. **Kompilasi Architecture Decision Records (Minimal 5 ADR Inti)**:
   * Pemilihan Database Transaksional (NewSQL vs RDBMS ter-sharding).
   * Pola Konsistensi Terdistribusi (Saga Orchestration vs Choreography untuk *Payment Capture & Settlement*).
   * Strategi Komunikasi Antar-Layanan (gRPC vs Event Streaming via Kafka).
   * Mekanisme Idempotensi Transaksi Terdistribusi.
   * Model Isolasi Data Multi-Tenant dan Enkripsi Lintas Batas Negara.
3. **Strategic Domain-Driven Design Context Map**:
   * Pemetaan *Bounded Context* (Payment Ingestion, Fraud Detection, Ledger Engine, Settlement Core, Notification).
   * Definisi kontrak batas (*Upstream/Downstream, Customer/Supplier, Anti-Corruption Layer*).
4. **Resilience & Chaos Engineering Runbook**:
   * Desain mitigasi kegagalan *cross-region failover* (RTO < 30 detik, RPO = 0 untuk transaksi tervalidasi).
   * Spesifikasi *Circuit Breaker*, *Bulkhead*, dan strategi *Dead Letter Queue (DLQ)*.
5. **Architectural Fitness Functions Suite**:
   * Script uji kebugaran arsitektur terotomasi (misal: menggunakan ArchUnit atau skrip linter arsitektur) untuk mencegah *cyclic dependencies* dan membatasi dependensi antar-layer layer secara otomatis di pipeline CI/CD.

---
*Kurikulum ini dirawat secara berkala oleh Technical Curriculum Council untuk mencerminkan dinamika dan evolusi standar industri perangkat lunak modern.*