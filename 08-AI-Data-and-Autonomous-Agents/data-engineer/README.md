# Enterprise Data Engineering: Production-Grade Curriculum & Practical Blueprints

Selamat datang di repositori kurikulum resmi **Data Engineer**. Silabus ini dirancang untuk mentransformasi praktisi perangkat lunak dan analis data menjadi **Senior Data Platform/Engineers** yang mampu merancang, membangun, mengoperasikan, dan mengoptimalkan platform data berskala multi-terabyte hingga petabyte dengan standar keandalan enterprise (*high availability, zero data loss, strict idempotency, dan finops-aware*).

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Data Engineering modern bukan sekadar menulis kueri SQL atau memindahkan berkas CSV menggunakan script Python sederhana. Data Engineering adalah **penerapan disiplin Software Engineering tingkat tinggi pada siklus hidup data**. Fokus kurikulum ini bertumpu pada lima pilar fundamental:

1. **Reliability & Idempotency:** Setiap pipeline harus bersifat deterministik. Eksekusi ulang (*re-run/backfill*) untuk rentang partisi yang sama harus menghasilkan *state* data yang identik tanpa efek samping (*zero duplicate, zero ghost records*).
2. **Data-as-Code & Governance:** Transformasi data, skema, dan konfigurasi infrastruktur diperlakukan sebagai artefak perangkat lunak yang diuji (*unit/integration test*), dikontrol versinya (*git-tracked*), dan ditinjau secara ketat (*peer-reviewed*).
3. **Decoupled Architecture:** Pemisahan tegas antara lapisan penyimpanan (*object storage*), komputasi (*stateless query engine*), dan orkestrasi (*control plane*) untuk memaksimalkan skalabilitas serta efisiensi biaya (*FinOps*).
4. **Lakehouse Paradigm:** Menghapus batas artifisial antara Data Lake dan Data Warehouse dengan mengadopsi format tabel terbuka (*open table formats*) berkemampuan ACID transactional guarantees.
5. **Operational Observability:** Memperlakukan data pipeline sebagai sistem terdistribusi mission-critical melalui pemantauan metrik data (*freshness, volume, distribution*), lineage otomatis, dan tracing kegagalan sistematis.

### Core Technology Stack
- **Languages:** Python (Modern 3.11+, Typing, AsyncIO, PyPika), SQL (ANSI/PostgreSQL/Trino dialect), Scala (Spark internals overview).
- **Storage & File Formats:** Apache Parquet, Apache Avro, Apache Iceberg, MinIO/AWS S3.
- **Engines & Processing:** Apache Spark 3.5, Apache Flink, Trino.
- **Streaming & Messaging:** Apache Kafka, Confluent Schema Registry.
- **Orchestration & Transformation:** Apache Airflow 2.8+, dbt-core (Data Build Tool).
- **Storage & Warehousing:** PostgreSQL, Snowflake, ClickHouse.
- **Quality & Observability:** Great Expectations, OpenLineage, Prometheus, Grafana.
- **Infrastructure & DataOps:** Docker, Kubernetes, Helm, Terraform, GitHub Actions.

---

## 2. Learning Roadmap

```
├── [BAB 01] FONDASI DATA ENGINEERING & ADVANCED PYTHON
│   ├── 01.1 Sistem Operasi, Linux Kernel & Network I/O
│   ├── 01.2 Advanced Python Internals & Concurrency
│   └── 01.3 Packaging, Modular Code & Data Quality Typing
│
├── [BAB 02] DATA MODELING, RELATIONAL INTERNALS & SQL MASTERY
│   ├── 02.1 PostgreSQL Architecture & Storage Internals
│   ├── 02.2 Advanced Analytical SQL & Window Processing
│   └── 02.3 Data Modeling Tradisional (OLTP vs OLAP)
│
├── [BAB 03] DATA LAKE, DISTRIBUTED STORAGE & FORMAT INTERNALS
│   ├── 03.1 Object Storage Architecture & Distributed I/O
│   ├── 03.2 Deep Dive Format File: Parquet, ORC, Avro
│   └── 03.3 NoSQL Engine Primitives (Key-Value, Document, Wide-Column)
│
├── [BAB 04] BATCH PROCESSING ENGINE: APACHE SPARK
│   ├── 04.1 Spark Architecture & Execution Plan Deep Dive
│   ├── 04.2 DataFrame API, Data Manipulation & Catalyst Optimizer
│   └── 04.3 Memory Management, Skew Mitigation & Tuning
│
├── [BAB 05] EVENT STREAMING & REAL-TIME ARCHITECTURES
│   ├── 05.1 Apache Kafka Internals & Distributed Log Architecture
│   ├── 05.2 Schema Governance & Serialization Protocols
│   └── 05.3 Structured Streaming & State Management (Spark/Flink)
│
├── [BAB 06] DATA ORCHESTRATION & WORKFLOW ENGINES
│   ├── 06.1 Prinsip Orkestrasi Modern & Directed Acyclic Graphs (DAG)
│   ├── 06.2 Apache Airflow Production Patterns & TaskFlow API
│   └── 06.3 Dynamic Workflows, Backfilling & Failure Recovery
│
├── [BAB 07] DATA WAREHOUSING, ANALYTICS ENGINES & DBT
│   ├── 07.1 Modern Cloud Data Warehousing Internals
│   ├── 07.2 Analytics Engineering dengan dbt (Data Build Tool)
│   └── 07.3 Dimensional Modeling: Kimball vs Data Vault 2.0
│
├── [BAB 08] MODERN LAKEHOUSE ARCHITECTURE
│   ├── 08.1 Open Table Formats: Apache Iceberg Internals
│   ├── 08.2 ACID Transactions, Time Travel & Compaction pada Data Lake
│   └── 08.3 Trino/Presto: High Performance Distributed SQL Engines
│
├── [BAB 09] DATA QUALITY, GOVERNANCE & OBSERVABILITY
│   ├── 09.1 Shift-Left Data Quality Testing & Contract Enforcement
│   ├── 09.2 Metadata Management, Lineage & OpenLineage
│   └── 09.3 Data Observability: Metrics, Freshness & Anomaly Detection
│
└── [BAB 10] DATAOPS, INFRASTRUCTURE AS CODE & FINOPS
    ├── 10.1 Containerization & Orchestration untuk Data Platform
    ├── 10.2 Infrastructure as Code (IaC) dengan Terraform
    └── 10.3 CI/CD Automation, Data Lifecycle & FinOps Engineering
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Data Engineering & Advanced Python](bab-01-fondasi-python/README.md)
Fondasi rekayasa sistem data menuntut pemahaman mendalam tentang I/O sistem operasi, manipulasi memori, serta penulisan kode sumber yang efisien dan deterministik.

*   [Modul 01.1: Sistem Operasi, Linux Kernel & Network I/O](bab-01-fondasi-python/modul-01-linux-kernel-io.md)
    *Eksplorasi POSIX, file descriptors, zero-copy architecture (`sendfile`), buffered vs unbuffered I/O, IPC, signal handling, serta CLI scripting diagnostik (`vmstat`, `iostat`, `strace`).*
*   [Modul 01.2: Advanced Python Internals & Concurrency](bab-01-fondasi-python/modul-02-python-concurrency.md)
    *GIL internals, memory management (CPython garbage collection, reference counting), multithreading vs multiprocessing vs `asyncio`, generators untuk memory-safe lazy batch streaming.*
*   [Modul 01.3: Packaging, Modular Code & Data Quality Typing](bab-01-fondasi-python/modul-03-packaging-typing.md)
    *Pydantic V2 untuk schema validation saat ingestion, Type Hinting ketat (`typing.Protocol`, `Generic`), modularisasi menggunakan Poetry, serta integrasi Ruff/Mypy pada pre-commit workflows.*

---

### [Bab 02: Data Modeling, Relational Internals & SQL Mastery](bab-02-relational-sql/README.md)
Sistem relasional adalah basis dari konsistensi transaksional data. Bab ini membongkar mesin kueri relasional dari level disk page hingga pemodelan analitis tingkat lanjut.

*   [Modul 02.1: PostgreSQL Architecture & Storage Internals](bab-02-relational-sql/modul-01-postgres-internals.md)
    *Page layout (8KB pages), heap tuples, WAL (Write-Ahead Logging), MVCC mechanisms, VACUUM lifecycle, pengindeksan tingkat lanjut (B-Tree, BRIN, GIN) dan analisis kueri via `EXPLAIN (ANALYZE, BUFFERS)`.*
*   [Modul 02.2: Advanced Analytical SQL & Window Processing](bab-02-relational-sql/modul-02-advanced-sql.md)
    *Window functions (`LEAD`, `LAG`, `DENSE_RANK`, framing specification `ROWS BETWEEN`), recursive CTEs, declarative table partitioning (range, list, hash), dan optimasi analytical join algorithms.*
*   [Modul 02.3: Data Modeling Tradisional (OLTP vs OLAP)](bab-02-relational-sql/modul-03-data-modeling-core.md)
    *Third Normal Form (3NF) untuk transactional systems, de-normalization patterns, penanganan write-amplification, dan perbandingan pola pemrosesan row-oriented vs columnar-oriented systems.*

---

### [Bab 03: Data Lake, Distributed Storage & Format Internals](bab-03-datalake-storage/README.md)
Data lake modern dibangun di atas distributed storage yang menuntut pemilihan format berkas serialisasi yang optimal untuk menekan latensi pembacaan dan pemotongan data (*data skipping*).

*   [Modul 03.1: Object Storage Architecture & Distributed I/O](bab-03-datalake-storage/modul-01-object-storage.md)
    *Desain MinIO dan AWS S3, eventual consistency vs strong consistency, multipart upload optimization, request rate limits, partition hashing, dan interaksi via S3 SDK/boto3.*
*   [Modul 03.2: Deep Dive Format File: Parquet, ORC, Avro](bab-03-datalake-storage/modul-02-file-formats.md)
    *Dremel record shredding algorithm pada Apache Parquet, footers metadata, column chunks, row groups, dictionary encoding, run-length encoding (RLE), Snappy vs ZSTD compression, dan Avro schema evolution.*
*   [Modul 03.3: NoSQL Engine Primitives (Key-Value, Document, Wide-Column)](bab-03-datalake-storage/modul-03-nosql-primitives.md)
    *Pola distribusi CAP/PACELC, Log-Structured Merge-trees (LSM Trees) vs B-Trees, data access patterns untuk Cassandra/ScylloDB dan MongoDB, serta integrasi source CDC (Change Data Capture).*

---

### [Bab 04: Batch Processing Engine: Apache Spark](bab-04-apache-spark/README.md)
Distributed batch computation engine merupakan tulang punggung pemrosesan data volume tinggi. Bab ini berfokus pada eksekusi terdistribusi, optimasi logis, dan physical compute plans.

*   [Modul 04.1: Spark Architecture & Execution Plan Deep Dive](bab-04-apache-spark/modul-01-spark-internals.md)
    *Driver, Cluster Manager, Executors, Stage boundaries, Narrow vs Wide dependencies, Directed Acyclic Graph (DAG) construction, dan dekonstruksi Parsed, Analyzed, Optimized Logical Plan serta Physical Plan.*
*   [Modul 04.2: DataFrame API, Data Manipulation & Catalyst Optimizer](bab-04-apache-spark/modul-02-dataframe-catalyst.md)
    *PySpark idiomatic patterns, Catalyst rule engine, whole-stage code generation, pushdown predicates, column projection, dan broadcast variable efficiency.*
*   [Modul 04.3: Memory Management, Skew Mitigation & Tuning](bab-04-apache-spark/modul-03-tuning-skew.md)
    *Alokasi Unified Memory (Storage vs Execution), GC tuning (G1GC), penanganan data skew dengan Salting keys, Adaptive Query Execution (AQE), dynamic partition coalesce, dan bucket joins.*

---

### [Bab 05: Event Streaming & Real-Time Architectures](bab-05-event-streaming/README.md)
Pemrosesan data real-time menuntut integrasi event broker throughput-tinggi dengan streaming compute engines yang memiliki garansi semantik *exactly-once*.

*   [Modul 05.1: Apache Kafka Internals & Distributed Log Architecture](bab-05-event-streaming/modul-01-kafka-internals.md)
    *Commit log immutable, consumer groups, partition rebalancing protocols, zero-copy reads, OS page cache utilization, ISR (In-Sync Replicas), acks configurations, dan controller quorum (KRaft).*
*   [Modul 05.2: Schema Governance & Serialization Protocols](bab-05-event-streaming/modul-02-schema-registry.md)
    *Confluent Schema Registry, evolusi skema (Backward, Forward, Full), serialisasi data efisien dengan Protocol Buffers dan Avro, serta pencegahan payload drift.*
*   [Modul 05.3: Structured Streaming & State Management](bab-05-event-streaming/modul-03-structured-streaming.md)
    *Micro-batch vs Continuous Processing, Event-Time vs Processing-Time, Watermarking untuk data terlambat (*late arriving data*), Stateful streaming joins, checkpointing, dan write-ahead log idempotency.*

---

### [Bab 06: Data Orchestration & Workflow Engines](bab-06-data-orchestration/README.md)
Orkestrasi data memastikan dependensi antartugas tereksekusi tanpa cela, deterministik, dan dapat dipulihkan secara instan saat terjadi degradasi infrastruktur.

*   [Modul 06.1: Prinsip Orkestrasi Modern & Directed Acyclic Graphs (DAG)](bab-06-data-orchestration/modul-01-orchestration-principles.md)
    *Prinsip Idempotensi mutlak, data backfilling tanpa side-effects, penanganan parameter dinamis (`execution_date`/`logical_date`), determinisme pipeline, dan isolasi lingkungan.*
*   [Modul 06.2: Apache Airflow Production Patterns & TaskFlow API](bab-06-data-orchestration/modul-02-airflow-production.md)
    *Airflow 2.8+ core architecture, Celery/Kubernetes Executor, custom operators, dynamic task mapping, TaskFlow API (`@task`), XComs over Object Storage (S3/GCS backend).*
*   [Modul 06.3: Dynamic Workflows, Backfilling & Failure Recovery](bab-06-data-orchestration/modul-03-resilience-backfill.md)
    *Circuit breakers, exponential backoff retries, SLA misses monitoring, automated rerun strategies, DAG generation scripts, dan state reconciliation post-incident.*

---

### [Bab 07: Data Warehousing, Analytics Engines & dbt](bab-07-dwh-dbt/README.md)
Transformasi analitis modern bergeser ke arah pemodelan berbasis SQL deklaratif yang diuji secara otomatis dan terintegrasi langsung dengan Modern Data Stack.

*   [Modul 07.1: Modern Cloud Data Warehousing Internals](bab-07-dwh-dbt/modul-01-cloud-dwh.md)
    *Arsitektur Snowflake / ClickHouse / BigQuery: decoupled compute & storage, micro-partitioning, metadata caching, columnar storage vectorization, zero-copy cloning, dan dynamic auto-scaling.*
*   [Modul 07.2: Analytics Engineering dengan dbt (Data Build Tool)](bab-07-dwh-dbt/modul-02-dbt-engineering.md)
    *Struktur modular dbt, materializations (view, table, incremental via merge/delete-insert), Jinja templating, custom macros, unit testing, schema generic tests, dan automated documentation generation.*
*   [Modul 07.3: Dimensional Modeling: Kimball vs Data Vault 2.0](bab-07-dwh-dbt/modul-03-dimensional-modeling.md)
    *Star Schema vs Snowflake Schema, Kimball dimensions (SCD Type 1, 2, 3, 6), Fact tables (transactional, periodic snapshot, accumulating snapshot), dan dasar arsitektur Data Vault (Hubs, Links, Satellites).*

---

### [Bab 08: Modern Lakehouse Architecture](bab-08-lakehouse-iceberg/README.md)
Format tabel terbuka membawa kapabilitas transaksional setara database engine tradisional ke atas storage tak terstruktur dengan performa kueri petabyte-scale.

*   [Modul 08.1: Open Table Formats: Apache Iceberg Internals](bab-08-lakehouse-iceberg/modul-01-iceberg-internals.md)
    *Spesifikasi arsitektur Iceberg: Catalog layer, Metadata file (`.json`), Manifest lists (`.avro`), Manifest files, dan snapshot management yang mengisolasi pembacaan dari mutasi data.*
*   [Modul 08.2: ACID Transactions, Time Travel & Compaction](bab-08-lakehouse-iceberg/modul-02-acid-compaction.md)
    *Serializability isolation via optimistic concurrency control (OCC), rollback, time-travel queries, hidden partitioning, partition evolution, rewrite data files (compaction), dan snapshot expiration.*
*   [Modul 08.3: Trino/Presto: High Performance Distributed SQL Engines](bab-08-lakehouse-iceberg/modul-03-trino-query-engine.md)
    *Koordinator dan Worker architecture, memory management, connector architecture (Iceberg, Hive, PostgreSQL federations), Cost-Based Optimizer (CBO), dan tuning latency kueri sub-second.*

---

### [Bab 09: Data Quality, Governance & Observability](bab-09-quality-observability/README.md)
Ekosistem data skala enterprise menuntut sistem imun yang mendeteksi anomali skema, drift volume, dan ketidaksesuaian logis sebelum sampai ke lapisan analitik bisnis.

*   [Modul 09.1: Shift-Left Data Quality Testing & Contract Enforcement](bab-09-quality-observability/modul-01-data-quality.md)
    *Implementasi Great Expectations dan Soda Core, pembuatan deklaratif Data Contracts antara produsen dan konsumen data, circuit breaker pipeline saat terjadi contract breach.*
*   [Modul 09.2: Metadata Management, Lineage & OpenLineage](bab-09-quality-observability/modul-02-metadata-lineage.md)
    *Pengumpulan metadata aktif, standar OpenLineage, pelacakan dataset lineage end-to-end dari sumber operasional hingga visualisasi BI menggunakan Marquez atau DataHub.*
*   [Modul 09.3: Data Observability: Metrics, Freshness & Anomaly Detection](bab-09-quality-observability/modul-03-data-observability.md)
    *Pilar Data Observability (Freshness, Volume, Schema, Quality, Lineage), agregasi metrik ke Prometheus/Grafana, implementasi anomaly detection berbasis statistical Z-score pada aliran data batch/streaming.*

---

### [Bab 10: DataOps, Infrastructure as Code & FinOps](bab-10-dataops-finops/README.md)
Platform data modern harus berjalan di atas infrastruktur yang dapat direproduksi secara deterministik (*reproducible*), terotomatisasi secara end-to-end, dan sadar biaya.

*   [Modul 10.1: Containerization & Orchestration untuk Data Platform](bab-10-dataops-finops/modul-01-k8s-containers.md)
    *Multi-stage Docker builds untuk dependencies data, deployment cluster Spark dan Airflow di atas Kubernetes (K8s) menggunakan Helm Charts, konfigurasi Resource Quotas, Taints, Tolerations, dan Node Affinity.*
*   [Modul 10.2: Infrastructure as Code (IaC) dengan Terraform](bab-10-dataops-finops/modul-02-terraform-iac.md)
    *Penyediaan modular storage (S3/Cloud Storage), IAM policies granular dengan Least Privilege Principle, provision cluster managed database, dan state backend locking via Terraform.*
*   [Modul 10.3: CI/CD Automation, Data Lifecycle & FinOps Engineering](bab-10-dataops-finops/modul-03-cicd-finops.md)
    *GitHub Actions pipelines untuk testing Spark/dbt (unit, integration, linting), dynamic staging environments, cold data tiering, compute auto-termination, dan analisis unit economics biaya pemrosesan per GB/TB.*

---

## 4. Enterprise Capstone Project

### Real-Time Financial Fraud Detection & Transaction Settlement Lakehouse Platform

Capstone Project ini adalah proyek integratif berskala enterprise yang merefleksikan arsitektur data multi-region perbankan/fintech global. Peserta diwajibkan membangun platform data terintegrasi yang menangani **ingesti streaming jutaan transaksi per detik**, mendeteksi transaksi anomali (*fraud*) secara real-time, sekaligus melakukan pembersihan, konsolidasi, dan pemodelan transaksional di dalam Lakehouse untuk analitik bisnis dan audit keuangan.

```
                           [ Transaksi FinTech Ingest ]
                                        │
                                        ▼
                           [ Apache Kafka + Schema Reg ]
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
     [ Spark Streaming / Flink ]                     [ MinIO / Bronze Lake ]
     • Stateful Anomaly Detection                    • Raw Ingestion (Idempotent)
     • Z-Score & Rule Engines                                  │
                 │                                             ▼
                 ▼                                   [ Spark Batch Orchestrated ]
     [ ClickHouse Low Latency ]                      • Medallion Silver (Deduplication)
     • Fraud Alerts Dashboard                        • Medallion Gold (Aggregations)
                                                               │
                                                               ▼
                                                    [ Apache Iceberg Tables ]
                                                    • ACID Transactions
                                                    • Data Contracts via dbt
                                                               │
                                                               ▼
                                                    [ Trino Query Federated ]
                                                    • Financial Audit & Risk BI
```

### Spesifikasi Teknis & Kriteria Keberhasilan

1. **High-Throughput Streaming Ingestion & Schema Governance:**
   - Simulator transaksi memproduksi payload event transaksi minimal 5.000 events/detik ke dalam **Apache Kafka**.
   - Skema divalidasi ketat menggunakan **Confluent Schema Registry** berbasis Avro format. Pipeline harus menolak transaksi invalid ke *Dead Letter Queue* (DLQ) tanpa memicu crash pada consumer group.
2. **Real-Time Stream Processing & Fraud Detection:**
   - Engine streaming (**PySpark Structured Streaming** atau **Apache Flink**) membaca log event Kafka, menerapkan sliding windows (rentang 10 menit, slide tiap 1 menit) untuk menghitung lonjakan frekuensi dan anomali nilai transaksi (*statistical outlier detection*).
   - Flagging transaksi berisiko tinggi diarahkan ke database analitik berlatensi rendah (**ClickHouse**) dengan latensi end-to-end $P_{99} < 2$ detik.
3. **Enterprise Lakehouse Storage (Medallion Architecture with Apache Iceberg):**
   - **Bronze Layer:** Raw data append-only berformat Parquet mentah di MinIO/S3 dengan partisi tanggal (`year=YYYY/month=MM/day=DD`).
   - **Silver Layer:** Apache Iceberg table format. Spark melakukan deduplikasi data idempotently menggunakan `MERGE INTO` berdasarkan `transaction_id`, data cleaning, dan masking kolom sensitif PII (Personally Identifiable Information).
   - **Gold Layer:** Pemodelan dimensional data via **dbt** (Fact Transaction Settlement, Dimension Merchant, Dimension Account) dengan skema Star Schema/Kimball.
4. **Data Orchestration & Quality Verification:**
   - Semua pipeline batch, snapshot expiration, dan data compaction diorkestrasi menggunakan **Apache Airflow 2.8+** via TaskFlow API dan Docker/Kubernetes Executor.
   - Pengecekan kualitas data otomatis di tiap fase menggunakan **Great Expectations** / **dbt tests**. Jika terjadi anomali integritas data (misal: saldo minus, referensi akun null), alert ditembakkan ke Slack/PagerDuty dan proses downstream dihentikan otomatis (*Circuit Breaker*).
5. **Infrastructure as Code, CI/CD, & Monitoring:**
   - Seluruh infrastruktur (MinIO buckets, Kafka topics, IAM policies, ClickHouse/Postgres DB) harus diprovisi secara deklaratif menggunakan **Terraform**.
   - Pipeline pengujian kode divalidasi melalui **GitHub Actions** (Mypy type checking, Pytest unit testing dengan Spark local session, dbt compile and test).
   - Metrik sistem (CPU/Memory usage Spark/Kafka, Kafka Consumer Lag, dan Data Freshness SLA) terekam di **Prometheus** dan divisualisasikan pada **Grafana Dashboard**.

---

## 5. Standar Kontribusi & Panduan Eksekusi

Setiap direktori Bab (`bab-XX-.../`) berisi modul instruksional detail, arsitektur kode, konfigurasi infrastruktur, dan latihan lab mandiri. Untuk mulai mempelajari modul:

```bash
# Clone repositori
git clone https://github.com/organization/data-engineer-curriculum.git
cd data-engineer-curriculum

# Eksplorasi direktori bab yang dituju
cd bab-01-fondasi-python
cat README.md
```

Seluruh pengiriman lab dan capstone project wajib memenuhi kriteria pemeriksaan otomatis:
- Unit test passing rate: **100%**.
- Linting standard: **Ruff strict compliant**.
- Static type checking: **Mypy compliant (zero untyped functions)**.
- Arsitektur: Mendukung sistem idempotensi penuh (dapat dieksekusi berulang kali tanpa memicu duplikasi data).