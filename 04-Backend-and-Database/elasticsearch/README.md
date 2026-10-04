# Silabus Kurikulum Enterprise: Elasticsearch Architecture & Engineering

Selamat datang di kurikulum teknis Elasticsearch. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi rekayasawan perangkat lunak, arsitek data, dan *site reliability engineers* (SRE) menjadi spesialis sistem pencarian terdistribusi (*distributed search & analytics engineer*).

Kurikulum ini mengacu pada standar kurikulum resmi roadmap.sh/elasticsearch, diperkaya dengan best-practice arsitektur skala petabyte tingkat industri.

---

## 1. Course Overview & Mindset

### Mental Model & Filosofi Arsitektur
Elasticsearch bukan sekadar *NoSQL document store* dan bukan sekadar *search engine library*. Elasticsearch adalah **mesin komputasi analitik dan pencarian terdistribusi terkoordinasi secara konsensus** yang dibangun di atas Apache Lucene.

Untuk menguasai Elasticsearch pada level enterprise, Anda harus mengubah paradigma berpikir dari relasional/CRUD database tradisional ke mental model terdistribusi:
1. **Lucene Core Invariance**: Elasticsearch mendelegasikan indexing dan searching ke instance Apache Lucene individual. Segment Lucene bersifat *immutable* (tidak dapat diubah). Setiap operasi penulisan, pembaruan, dan penghapusan tunduk pada semantik pembuatan segmen baru, penandaan *bitset tombstone*, dan *background segment merging*.
2. **Distributed Coordination & Data Sharding**: Data dipecah menjadi unit partisi logis (*shards*), yang didistribusikan ke seluruh node cluster via algoritma hashing `hash(routing) % primary_shards`. Memahami koordinasi cluster, *master election*, *cluster state publication*, serta latensi jejaring antar-node adalah kunci mencegah *split-brain* dan *cluster-wide degradation*.
3. **Memory Tiering & Resource Isolation**: Performa Elasticsearch bergantung pada rasio ekuilibrium antara alokasi **JVM Heap Memory** (untuk query execution, aggregation buckets, circuit breakers) dan **OS Page Cache / Off-heap** (eksklusif untuk Lucene FST, inverted index, dan doc values). Salah mengonfigurasi memori akan menyebabkan *catastrophic Stop-The-World GC pauses*.
4. **Consistency vs Availability**: Memahami batas toleransi model konkurensi optimistik (*optimistic concurrency control* via `_seq_no` dan `_primary_term`), replikasi berbasis *translog sync*, dan mekanisme *quorum-based recovery*.

---

## 2. Learning Roadmap

```
Elasticsearch Engineering Curriculum
│
├── Bab 01: Arsitektur Fundamental & Distributed Cluster
├── Bab 02: Inverted Index, Text Analysis & Mapping Engine
├── Bab 03: Data Ingestion & Pipeline Architecture
├── Bab 04: Deep Dive Query DSL & Relevance Scoring
├── Bab 05: Complex Aggregations & Analytics Engine
├── Bab 06: Vector Search, Semantic Search & Machine Learning
├── Bab 07: Sharding, Scaling & Routing Strategies
├── Bab 08: Data Tiering, Index Lifecycle Management (ILM) & Storage Optimization
├── Bab 09: Performance Tuning, JVM & Cluster Diagnostics
└── Bab 10: Enterprise Security, Resiliency & Disaster Recovery
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Arsitektur Fundamental & Distributed Cluster](./01-arsitektur-fundamental-distributed-cluster/README.md)
Membedah arsitektur internal Elasticsearch, orkestrasi node, dan mekanisme konsensus terdistribusi.
* [Modul 01: Node Roles, Topology, dan Discovery](./01-arsitektur-fundamental-distributed-cluster/01-node-roles-topology-discovery.md) – Eksplorasi peran node (master-eligible, data, coordinating, ingest), pemilihan master via Zen Discovery / 7.x+ voting configuration, dan distribusi cluster state.
* [Modul 02: Anatomi Shard & Lucene Engine Internals](./01-arsitektur-fundamental-distributed-cluster/02-anatomi-shard-lucene-engine.md) – Dekonstruksi shard fisik vs logis, Lucene segments, immutability, flush, refresh, dan peran translog dalam durabilitas data.
* [Modul 03: Cluster State Execution & Two-Phase Commit](./01-arsitektur-fundamental-distributed-cluster/03-cluster-state-execution.md) – Mekanisme replikasi cluster state secara atomik dan penanganan kegagalan node (*fault detection* & *heartbeats*).

### [Bab 02: Inverted Index, Text Analysis & Mapping Engine](./02-inverted-index-text-analysis-mapping-engine/README.md)
Memahami cara mesin pencarian membedah data tidak terstruktur menjadi representasi terindeks berkecepatan tinggi.
* [Modul 01: Rekayasa Inverted Index & Data Structures](./02-inverted-index-text-analysis-mapping-engine/01-inverted-index-data-structures.md) – Struktur internal posting list, term dictionary, Term Frequency-Inverse Document Frequency footprint, dan Finite State Transducers (FST).
* [Modul 02: Deep Dive Analysis Pipeline: Character Filters, Tokenizers, Token Filters](./02-inverted-index-text-analysis-mapping-engine/02-analysis-pipeline-internals.md) – Anatomi pipeline analisa teks, normalisasi karakter, edge-ngram, shingle, dan perancangan custom analyzer multibahasa.
* [Modul 03: Dynamic vs Explicit Mapping & Core Data Types](./02-inverted-index-text-analysis-mapping-engine/03-mapping-and-field-types.md) – Strategi pencegahan *mapping explosion*, konfigurasi tipe data `text` vs `keyword`, `nested`, `flattened`, dan metadata fields (`_source`, `_doc_count`).

### [Bab 03: Data Ingestion & Pipeline Architecture](./03-data-ingestion-pipeline-architecture/README.md)
Arsitektur penyerapan data throughput tinggi dengan integritas terjamin.
* [Modul 01: Bulk API Internals & High-Throughput Ingestion](./03-data-ingestion-pipeline-architecture/01-bulk-api-and-concurrency.md) – Optimasi batching, konkurensi thread pools (write), backpressure, dan penanganan HTTP 429 (`EsRejectedExecutionException`).
* [Modul 02: Ingest Nodes, Pipeline Processors & Painless Scripting](./03-data-ingestion-pipeline-architecture/02-ingest-pipeline-painless.md) – Transformasi data in-flight menggunakan ingest node, dissect, grok, set, drop processor, dan scripting aman menggunakan Painless.
* [Modul 03: Document Routing & Idempotent Indexing](./03-data-ingestion-pipeline-architecture/03-document-routing-idempotency.md) – Mekanisme partisi berbasis custom `routing` key, versioning deterministik, dan optimasi *create-only* vs *upsert*.

### [Bab 04: Deep Dive Query DSL & Relevance Scoring](./04-deep-dive-query-dsl-relevance-scoring/README.md)
Penguasaan bahasa kueri Elasticsearch dan matematis penentuan relevansi hasil pencarian.
* [Modul 01: Precision Search vs Full-Text Search](./04-deep-dive-query-dsl-relevance-scoring/01-precision-vs-full-text-query.md) – Analisis komparatif eksekusi Term-level queries vs Match, Multi-match (best/most/cross fields), dan Query String dalam query execution context.
* [Modul 02: Boolean Model & Compound Queries Execution](./04-deep-dive-query-dsl-relevance-scoring/02-boolean-compound-queries.md) – Evaluasi klausa `must`, `should`, `filter`, dan `must_not` serta pemanfaatan Bitset Filter Caching untuk optimasi performa.
* [Modul 03: The Mathematics of Scoring: Okapi BM25 & Function Score](./04-deep-dive-query-dsl-relevance-scoring/03-scoring-bm25-function-score.md) – Bedah algoritma Okapi BM25 ($k_1$, $b$, term saturation), debugging bobot relevansi via `_explain`, dan manipulasi skor dinamis via `function_score` dan `script_score`.

### [Bab 05: Complex Aggregations & Analytics Engine](./05-complex-aggregations-analytics-engine/README.md)
Mengeksekusi analitik OLAP berskala masif secara real-time langsung di atas cluster pencarian.
* [Modul 01: Metric & Bucket Aggregations Architecture](./05-complex-aggregations-analytics-engine/01-metric-and-bucket-aggregations.md) – Implementasi Terms, Date Histogram, Range, Composite Aggregation, dan pemanfaatan `doc_values` serta `global_ordinals`.
* [Modul 02: Pipeline Aggregations & Analytical Computations](./05-complex-aggregations-analytics-engine/02-pipeline-aggregations.md) – Transformasi multi-pass: Parent vs Sibling aggregations (`derivative`, `moving_avg`, `bucket_script`, `cumulative_sum`).
* [Modul 03: Probabilistic Data Structures & Cardinality Estimation](./05-complex-aggregations-analytics-engine/03-probabilistic-data-structures.md) – HyperLogLog++ dalam kalkulasi `cardinality`, trade-off presisi memori (`precision_threshold`), dan kalkulasi persentil dengan T-Digest.

### [Bab 06: Vector Search, Semantic Search & Machine Learning](./06-vector-search-semantic-search-ml/README.md)
Mengintegrasikan kapabilitas modern Artificial Intelligence, dense vectors, dan semantic retrieval.
* [Modul 01: Dense Vectors & Approximate k-NN Search](./06-vector-search-semantic-search-ml/01-dense-vectors-knn-hnsw.md) – Representasi embedding vektor dengan `dense_vector`, algoritma graf HNSW (Hierarchical Navigable Small World), similarity metrics (cosine, dot_product, l2_norm).
* [Modul 02: Hybrid Retrieval & Reciprocal Rank Fusion (RRF)](./06-vector-search-semantic-search-ml/02-hybrid-search-rrf.md) – Menggabungkan skor leksikal BM25 tradisional dengan semantic vector retrieval via algoritma normalisasi ranking RRF.
* [Modul 03: In-Cluster Inference & Elastic Learned Sparse Encoder (ELSER)](./06-vector-search-semantic-search-ml/03-in-cluster-inference-elser.md) – Deployment model NLP sparse/dense vector langsung di Elasticsearch ML Node dan inferensi pipeline teks secara transparan.

### [Bab 07: Sharding, Scaling & Routing Strategies](./07-sharding-scaling-routing-strategies/README.md)
Menata topologi penyimpanan cluster guna menghindari fragmentasi data dan pemborosan komputasi.
* [Modul 01: Shard Sizing, Oversharding Hazards & Allocation Deciders](./07-sharding-scaling-routing-strategies/01-shard-sizing-and-allocation.md) – Matriks rasio shard optimal (20GB-50GB rule), overhead memori per-shard, dan algoritma *shard allocation filtering* & *awareness*.
* [Modul 02: Custom Routing Architecture & Search Colocation](./07-sharding-scaling-routing-strategies/02-custom-routing-colocation.md) – Menghilangkan *scatter-gather overhead* dengan custom routing, implikasi terhadap shard hotspotting, dan teknik mitigasi unbalance.
* [Modul 03: Shard Shrinking, Splitting & Index Rollover Protocols](./07-sharding-scaling-routing-strategies/03-shrink-split-rollover.md) – Operasi struktural: API Shrink, Split, dan otomatisasi *Rollover API* berdasar batas kapasitas ukuran dan jumlah dokumen.

### [Bab 08: Data Tiering, Index Lifecycle Management (ILM) & Storage Optimization](./08-data-tiering-ilm-storage-optimization/README.md)
Otomatisasi siklus hidup data untuk efisiensi biaya penyimpanan tanpa mengorbankan kecepatan akses.
* [Modul 01: Arsitektur Multi-Tier (Hot, Warm, Cold, Frozen)](./08-data-tiering-ilm-storage-optimization/01-multi-tier-architecture.md) – Alokasi perangkat keras komparatif (NVMe vs SSD vs Object Store) sesuai SLA kebutuhan akses data *time-series*.
* [Modul 02: Automation via Index Lifecycle Policies (ILM)](./08-data-tiering-ilm-storage-optimization/02-ilm-policies-automation.md) – Perancangan phase transitions, penyesuaian replica counts, force merge, read-only switching, dan purge rules.
* [Modul 03: Searchable Snapshots & Object Storage Offloading](./08-data-tiering-ilm-storage-optimization/03-searchable-snapshots.md) – Implementasi arsitektur Frozen tier yang membaca snapshot langsung dari AWS S3 / GCS secara streaming dengan *local cache eviction*.

### [Bab 09: Performance Tuning, JVM & Cluster Diagnostics](./09-performance-tuning-jvm-diagnostics/README.md)
Diagnostik level kernel, alokasi memori sistem, dan resolusi bottleneck latensi ekstrem.
* [Modul 01: JVM Heap, Garbage Collection (G1/ZGC) & Off-Heap Mechanics](./09-performance-tuning-jvm-diagnostics/01-jvm-gc-pagecache.md) – Rekayasa rasio 50% RAM rule (max 31GB heap untuk Zero-Based Compressed OOPs), konfigurasi Garbage First (G1GC), dan isolasi Lucene page cache.
* [Modul 02: Thread Pools, Circuit Breakers & Backpressure Diagnostics](./09-performance-tuning-jvm-diagnostics/02-thread-pools-circuit-breakers.md) – Analisis kapasitas thread pool (`search`, `write`, `management`), inspeksi *circuit breaker exceptions* (`parent`, `fielddata`), dan pencegahan OOM fatal.
* [Modul 03: Profiling & Tuning Slow Queries (Profile API, Slow Logs)](./09-performance-tuning-jvm-diagnostics/03-query-profiling-and-tuning.md) – Bedah performa menggunakan Profile API, pelacakan bottlenecks segment collection, index sorting optimization, dan konfigurasi Index Slow Logs.

### [Bab 10: Enterprise Security, Resiliency & Disaster Recovery](./10-enterprise-security-resiliency-disaster-recovery/README.md)
Mengunci keamanan data, enkripsi in-flight/at-rest, kepatuhan audit, dan mitigasi downtime total.
* [Modul 01: TLS/mTLS, Native Cryptography & RBAC/ABAC Systems](./10-enterprise-security-resiliency-disaster-recovery/01-tls-encryption-rbac-abac.md) – Pengamanan komunikasi inter-node dan client via mutual TLS, otentikasi PKI, Active Directory/LDAP integration, serta Document-Level and Field-Level Security (DLS/FLS).
* [Modul 02: Cross-Cluster Search (CCS) & Cross-Cluster Replication (CCR)](./10-enterprise-security-resiliency-disaster-recovery/02-cross-cluster-search-replication.md) – Desain topologi multi-region/multi-datacenter, replikasi aktif-pasif lintas cluster (*uni-directional*), dan federasi kueri terdistribusi (CCS).
* [Modul 03: Disaster Recovery: Distributed Snapshot, Restore & Chaos Engineering](./10-enterprise-security-resiliency-disaster-recovery/03-disaster-recovery-chaos.md) – Backup terdistribusi berkesinambungan ke Cloud Object Storage, pengujian integritas restorasi otomatis, dan simulasi cluster network partition (*chaos testing*).

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**Unified Multi-Tenant Telemetry & Hybrid E-Commerce Search Platform**

### Skala & Arsitektur Sistem:
Sebagai bukti kompetensi akhir, peserta wajib membangun dan mendemonstrasikan sistem Elasticsearch produksi skala enterprise dengan kriteria sebagai berikut:

```
[ Ingestion Layer (Kafka / Logstash / Direct App) ]
                     │
                     ▼
          [ Elasticsearch Cluster ]
   ┌────────────────────────────────────────┐
   │ 3 Dedicated Master Nodes               │
   │ 2 Ingest / ML Nodes (ELSER Model)      │
   │ 2 Data Hot Nodes (Fast NVMe)           │
   │ 2 Data Warm Nodes (SSD)                │
   │ 2 Data Cold / Frozen Nodes (S3-backed) │
   └────────────────────────────────────────┘
                     │
         [ Cross-Cluster Bridge ]
                     ▼
   [ Secondary Disaster Recovery Cluster ]
```

### Persyaratan Fungsional & Non-Fungsional Capstone:

1. **Dual Workload Support**:
   * **Workload A (Time-Series Telemetry)**: Ingestion log dan metrics mikroservis dengan volume minimal **50.000 events/detik**, didukung pipeline ingest berbasis grok/dissect/painless, ILM otomatis transisi Hot (1 hari) -> Warm (7 hari, force-merged) -> Cold (30 hari, searchable snapshots) -> Delete (90 hari).
   * **Workload B (Hybrid E-Commerce Product Catalog)**: Pencarian katalog multi-atribut (1.000.000 SKU) dengan **Hybrid Search** menggabungkan BM25 text query (title, description, tags) dengan dense vector similarity (k-NN) menggunakan model embedding semantik, diranking ulang dengan **Reciprocal Rank Fusion (RRF)**.
2. **Deterministic Multi-Tenancy**:
   * Implementasi partisi data tenant menggunakan **Custom Shard Routing** dan **Document-Level Security (DLS)** sehingga tenant A tidak dapat melihat data tenant B secara kriptografis dan logis.
3. **Resiliency & High Availability**:
   * Konfigurasi arsitektur **Cross-Cluster Replication (CCR)** aktif-pasif ke data center kedua dengan zero data loss target (RPO < 1 detik, RTO < 30 detik).
4. **Hardening & Security Constraints**:
   * Strict mTLS 1.3 inter-node dan client encryption.
   * Role-Based Access Control (RBAC) dengan 3 profil akses: `cluster_admin`, `ingest_agent`, dan `tenant_search_consumer`.
5. **Observability & Diagnostics**:
   * Dashboard pemantauan performa: JVM GC profiling, Threadpool queue inspection, Circuit breaker headroom, dan Index slow query monitoring alerting bila latensi p99 melebihi **150ms**.

### Kriteria Kelulusan:
Proyek harus diserahkan dalam bentuk repositori Git yang berisi file konfigurasi (`docker-compose.yml` multi-node / Terraform / Kubernetes Helm values), skrip automasi pengujian beban (*load-testing script* via Locust atau JMeter), definisi mapping/pipeline, dan dokumen *Architecture Decision Record* (ADR) lengkap. Evaluasi mencakup stabilitas sistem di bawah tekanan injeksi data tanpa menimbulkan `429 Too Many Requests` atau `CircuitBreakingException`.