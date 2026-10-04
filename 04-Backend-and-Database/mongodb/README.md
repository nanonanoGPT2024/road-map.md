# Enterprise MongoDB Architecture & Data Engineering: Zero-to-Production Mastery

Selamat datang di kurikulum teknis MongoDB tingkat enterprise. Silabus ini dirancang sebagai cetak biru komprehensif untuk mentransformasi software engineer, data engineer, dan database administrator menjadi **Distributed Systems Data Architect** yang menguasai ekosistem MongoDB dari internal mesin penyimpanan hingga operasional klaster terdistribusi berskala petabyte.

---

## 1. Course Overview & Mindset

### Filosofi Desain & Mental Model
Dalam paradigma basis data relasional (RDBMS), schema didesain berdasarkan normalisasi entitas (*data-first normalization*). MongoDB membalik pendekatan ini: **Data modeling di MongoDB berorientasi pada beban kerja (*workload-driven schema design*)**. Bentuk dokumen BSON, indeks, dan topologi klaster ditentukan oleh pola akses baca/tulis (*read/write access patterns*), bukan representasi matematis relasi tabel semata.

```
+-------------------------------------------------------------------------+
|                         PARADIGMA MENTAL MODEL                          |
+-------------------------------------------------------------------------+
| RDBMS (Relational)            | MongoDB (Document Enterprise)           |
| - Normalization (3NF)         | - Workload-Driven Design (Embed/Ref)    |
| - Joins at Query Time         | - Pre-aggregation & Atomic Updates      |
| - Rigid Schema Enforcement    | - Polymorphic & Flexible Schema         |
| - Scale-Up (Vertical)         | - Scale-Out (Horizontal Sharding)       |
| - ACID by Default (Per-Table) | - Tunable Consistency (WiredTiger/Read/ |
|                               |   Write Concerns & Multi-Doc ACID)      |
+-------------------------------------------------------------------------+
```

### Sasaran Kompetensi
Setelah menyelesaikan kurikulum ini, peserta mampu:
1. Membedah internal **WiredTiger Engine**, alokasi memori cache, checkpoint, dan struktur byte BSON.
2. Mendesain skema data tingkat lanjut (*Advanced Schema Design Patterns*) yang kebal terhadap fenomena *Unbounded Array Growth*.
3. Menguasai kompilasi query pada **Aggregation Framework** dengan optimasi tahapan pipeline dan memori.
4. Mendesain strategi pengindeksan presisi berbasis *B-Tree*, *ESR (Equality, Sort, Range)* Rule, dan analisis mendalam `explain("executionStats")`.
5. Mengorkestrasikan arsitektur **Replica Set** dengan toleransi partisi jaringan (*network partition*) dan penjaminan konsistensi terdistribusi (*tunable consistency*).
6. Mengimplementasikan **Horizontal Sharding** multi-klaster berbasis *hashed*, *ranged*, dan *zoned/tag-aware sharding* tanpa degradasi performa (*jumbo chunks prevention*).
7. Menerapkan protokol keamanan perbankan: **Client-Side Field Level Encryption (CSFLE)**, RBAC, dan audit trail compliance.
8. Melakukan troubleshooting degradasi latensi, evicting cache stall, dan tuning performa pada level OS (Linux kernel) serta engine `mongod`.

### Prasyarat Teknis
- Pemahaman solid tentang struktur data, algoritma (khususnya B-Tree), dan konsep dasar database (ACID, locking, isolation levels).
- Kemahiran dalam salah satu bahasa pemrograman backend (Node.js, Go, Java, atau Python).
- Pengalaman dasar navigasi CLI Linux/UNIX dan konsep jaringan (TCP/IP, latency, DNS resolution).

---

## 2. Learning Roadmap

```
MongoDB Enterprise Mastery Architecture
│
├── [BAB 01] Core Architecture, Document Model & BSON Internals
│   ├── Modul 01: BSON Binary Anatomy & WiredTiger Storage Engine
│   └── Modul 02: Memory Lifecycle, Checkpoints & Journaling
│
├── [BAB 02] High-Performance CRUD Operations & Bulk Execution
│   ├── Modul 01: Atomic Mutations & Write Concern Semantics
│   ├── Modul 02: Read Concern, Read Preferences & Cursor Internals
│   └── Modul 03: Bulk Operations API & Pipeline Mutation Processing
│
├── [BAB 03] Advanced Data Modeling & Schema Design Patterns
│   ├── Modul 01: Embedding vs. Referencing Decision Matrix
│   ├── Modul 02: High-Performance Schema Patterns (Bucket, Polymorphic, Attribute)
│   └── Modul 03: Anti-Patterns Mitigation & Schema Versioning Lifecycle
│
├── [BAB 04] The Aggregation Framework: Deep-Dive Execution
│   ├── Modul 01: Core Aggregation Pipeline & Memory Optimization ($lookup, $unwind)
│   ├── Modul 02: Window Functions, Bucketing & Faceted Search
│   └── Modul 03: Custom Accumulators & Query Execution Optimization
│
├── [BAB 05] Indexing Strategies, B-Tree Internals & Query Tuning
│   ├── Modul 01: B-Tree Mechanics, Compound Indexes & ESR Rule
│   ├── Modul 02: Specialized Indexes: Multikey, TTL, Partial, Text & 2dsphere
│   └── Modul 03: Query Planner Execution Analysis via explain()
│
├── [BAB 06] Concurrency Control, Lock Semantics & Transactions
│   ├── Modul 01: WiredTiger Concurrency & Lock Hierarchy (IS, IX, S, X)
│   ├── Modul 02: Distributed Multi-Document ACID Transactions
│   └── Modul 03: Optimistic Concurrency Control (OCC) Patterns
│
├── [BAB 07] High Availability & Replica Set Architecture
│   ├── Modul 01: Oplog Architecture, Mechanics & Sizing
│   ├── Modul 02: Raft-like Consensus, Heartbeats & Split-Brain Mitigation
│   └── Modul 03: Replica Set Maintenance, Reconfiguration & Resync
│
├── [BAB 08] Scalability via Horizontal Sharding Architecture
│   ├── Modul 01: Sharded Cluster Architecture (Mongos, Config Servers, Shards)
│   ├── Modul 02: Shard Key Strategy: Hashed, Ranged & Compound Anti-Hotspotting
│   └── Modul 03: Chunk Balancing, Split Mechanics & Zoned Sharding
│
├── [BAB 09] Enterprise Security, Governance & CSFLE
│   ├── Modul 01: Authentication (SCRAM, x.509, LDAP) & Granular RBAC
│   ├── Modul 02: Encryption-at-Rest & Client-Side Field Level Encryption (CSFLE)
│   └── Modul 03: Auditing Protocols, Network Isolation & Compliance
│
└── [BAB 10] Site Reliability Engineering, Diagnostics & Tuning
    ├── Modul 01: Linux OS Kernel Tuning & WiredTiger Cache Sizing
    ├── Modul 02: Diagnostics via FTDC, Profiler & Metrics Interpretation
    └── Modul 03: Zero-Downtime Backup, Point-in-Time Recovery & Chaos Engineering
```

---

## 3. Navigasi Detail Modul Silabus

### [Bab 01: Core Architecture, Document Model & BSON Internals](./bab-01-core-architecture/README.md)
Membedah anatomi internal MongoDB: bagaimana dokumen direpresentasikan dalam memori dan disk, alokasi memori WiredTiger, dan alur penulisan data dari koneksi TCP hingga blok media penyimpanan.
* **[Modul 01: BSON Binary Anatomy & WiredTiger Storage Engine](./bab-01-core-architecture/modul-01-bson-wiredtiger.md)**: Format BSON, overhead tipe data, layout disk WiredTiger, mekanisme kompresi (Snappy, Zlib, Zstandard).
* **[Modul 02: Memory Lifecycle, Checkpoints & Journaling](./bab-01-core-architecture/modul-02-memory-journaling.md)**: Siklus memori dirty/clean cache, checkpointing interval (60 detik), mekanisme Write-Ahead Log (WAL/Journal), dan recovery setelah crash mendadak.

### [Bab 02: High-Performance CRUD Operations & Bulk Execution](./bab-02-crud-operations/README.md)
Mempelajari semantik operasi mutasi dan query secara deterministik dengan latensi rendah, throughput tinggi, serta penanganan atomisitas level dokumen.
* **[Modul 01: Atomic Mutations & Write Concern Semantics](./bab-02-crud-operations/modul-01-atomic-write-concerns.md)**: Modifikator dokumen berkinerja tinggi (`$set`, `$inc`, `$push`, positional operator `$` dan `$[<identifier>]`), write concern mechanics (`w:1`, `w:majority`, `j:true`).
* **[Modul 02: Read Concern, Read Preferences & Cursor Internals](./bab-02-crud-operations/modul-02-read-concern-cursor.md)**: Analisis level isolasi `readConcern` (`local`, `available`, `majority`, `linearizable`, `snapshot`), routing query via `readPreference`, cursor pagination vs memory skip.
* **[Modul 03: Bulk Operations API & Pipeline Mutation Processing](./bab-02-crud-operations/modul-03-bulk-operations.md)**: Eksekusi massal `bulkWrite()` (ordered vs unordered), network roundtrip reduction, dan batch ingestion pipelines.

### [Bab 03: Advanced Data Modeling & Schema Design Patterns](./bab-03-data-modeling/README.md)
Membangun arsitektur skema dokumen untuk sistem terdistribusi, menghindari jebakan model relasional dan memaksimalkan efisiensi I/O disk.
* **[Modul 01: Embedding vs. Referencing Decision Matrix](./bab-03-data-modeling/modul-01-embedding-vs-referencing.md)**: Metrik 1-to-1, 1-to-Few, 1-to-Many, 1-to-Squillions, dan trade-off konsistensi vs. performa.
* **[Modul 02: High-Performance Schema Patterns](./bab-03-data-modeling/modul-02-schema-patterns.md)**: Implementasi *Bucket Pattern* (Time-Series/IoT), *Polymorphic Pattern*, *Attribute Pattern*, *Extended Reference*, dan *Outlier Pattern*.
* **[Modul 03: Anti-Patterns Mitigation & Schema Versioning Lifecycle](./bab-03-data-modeling/modul-03-antipatterns-versioning.md)**: Mitigasi *Unbounded Array Growth*, migrasi skema online dengan *Schema Versioning Pattern*, validasi JSON Schema pada level collection.

### [Bab 04: The Aggregation Framework: Deep-Dive Execution](./bab-04-aggregation-framework/README.md)
Menguasai mesin pengolahan data native MongoDB secara paralel untuk analisis data kompleks dan pelaporan enterprise tanpa dependensi sistem ETL eksternal.
* **[Modul 01: Core Aggregation Pipeline & Memory Optimization](./bab-04-aggregation-framework/modul-01-pipeline-memory.md)**: Tahapan pipeline (`$match`, `$project`, `$group`, `$lookup`, `$unwind`), optimasi batasan RAM 100MB/stage, penggunaan `allowDiskUse`.
* **[Modul 02: Window Functions, Bucketing & Faceted Search](./bab-04-aggregation-framework/modul-02-window-facets.md)**: Operasi analitik waktu-nyata `$setWindowFields`, analisis segmentasi via `$bucketAuto`, pengindeksan katalog multi-dimensi via `$facet`.
* **[Modul 03: Custom Accumulators & Query Execution Optimization](./bab-04-aggregation-framework/modul-03-custom-accumulators-tuning.md)**: Optimasi kompilasi stage coalescing, ekspresi JavaScript via `$accumulator` dan `$function`, pushdown predicates ke layer storage engine.

### [Bab 05: Indexing Strategies, B-Tree Internals & Query Tuning](./bab-05-indexing-tuning/README.md)
Mendalami implementasi B-Tree pada disk/RAM, strategi eliminasi bottleneck query, serta teknik evaluasi rencana eksekusi query planner.
* **[Modul 01: B-Tree Mechanics, Compound Indexes & ESR Rule](./bab-05-indexing-tuning/modul-01-btree-compound-esr.md)**: Struktur data B-Tree, indeks majemuk (*compound*), eliminasi *In-Memory Sort* menggunakan *Equality, Sort, Range (ESR) Rule*.
* **[Modul 02: Specialized Indexes: Multikey, TTL, Partial, Text & 2dsphere](./bab-05-indexing-tuning/modul-02-specialized-indexes.md)**: Penanganan indeks array (*Multikey*), retensi log otomatis (*TTL*), efisiensi ruang via *Partial* dan *Sparse Indexes*, query geospasial spheroidal (*2dsphere*).
* **[Modul 03: Query Planner Execution Analysis via explain()](./bab-05-indexing-tuning/modul-03-explain-execution-stats.md)**: Anatomi output `explain("executionStats")`, analisis perbandingan `totalKeysExamined`, `totalDocsExamined`, dan `nReturned`, deteksi tahap `COLLSCAN` tersembunyi.

### [Bab 06: Concurrency Control, Lock Semantics & Transactions](./bab-06-concurrency-transactions/README.md)
Menguasai semantik multithreading, mitigasi deadlock, serta implementasi transaksi ACID lintas dokumen dan lintas shard pada lingkungan klaster.
* **[Modul 01: WiredTiger Concurrency & Lock Hierarchy](./bab-06-concurrency-transactions/modul-01-locks-concurrency.md)**: Hirarki penguncian database (Global, Database, Collection, Document-level intent locks: IS, IX, S, X), alokasi tiket pembacaan/penulisan (*read/write tickets*).
* **[Modul 02: Distributed Multi-Document ACID Transactions](./bab-06-concurrency-transactions/modul-02-acid-transactions.md)**: Implementasi session transaksi multi-dokumen, transient transaction errors handling, performa transaksi lintas shard, batas waktu commit.
* **[Modul 03: Optimistic Concurrency Control (OCC) Patterns](./bab-06-concurrency-transactions/modul-03-optimistic-locking.md)**: Pengendalian konkurensi non-blocking tingkat aplikasi menggunakan version stamps dan conditional atomic update arrays.

### [Bab 07: High Availability & Replica Set Architecture](./bab-07-replica-sets/README.md)
Membangun infrastruktur tanpa *Single Point of Failure (SPOF)* menggunakan protokol replikasi terdistribusi, konsensus otomatis, dan mekanisme pemulihan bencana.
* **[Modul 01: Oplog Architecture, Mechanics & Sizing](./bab-07-replica-sets/modul-01-oplog-mechanics.md)**: Struktur `local.oplog.rs`, proses replikasi idempotensi, estimasi ukuran Oplog (*oplog window sizing*), replikasi chaining.
* **[Modul 02: Raft-like Consensus, Heartbeats & Split-Brain Mitigation](./bab-07-replica-sets/modul-02-consensus-elections.md)**: Mekanisme pemilihan Primary, prioritas node, node tipe Hidden dan Arbiter, pencegahan *split-brain*, penanganan rollback folder.
* **[Modul 03: Replica Set Maintenance, Reconfiguration & Resync](./bab-07-replica-sets/modul-03-maintenance-resync.md)**: Rolling updates tanpa downtime, rekonfigurasi status anggota secara aman, Initial Sync manual vs berbasis filesystem snapshot.

### [Bab 08: Scalability via Horizontal Sharding Architecture](./bab-08-horizontal-sharding/README.md)
Mendistribusikan data secara horizontal ke puluhan node menggunakan mekanisme partisi terdistribusi untuk beban kerja throughput penulisan masif.
* **[Modul 01: Sharded Cluster Architecture](./bab-08-horizontal-sharding/modul-01-cluster-topology.md)**: Peran `mongos` query router, klaster Config Server (CSRS), katalog metadata shard, dan interaksi perutean query.
* **[Modul 02: Shard Key Strategy: Hashed, Ranged & Compound Anti-Hotspotting](./bab-08-horizontal-sharding/modul-02-shard-key-selection.md)**: Pemilihan Shard Key berkardinalitas tinggi, isolasi monotonic write bottleneck via *Hashed Sharding*, pengelompokan rentang via *Compound Shard Keys*.
* **[Modul 03: Chunk Balancing, Split Mechanics & Zoned Sharding](./bab-08-horizontal-sharding/modul-03-balancing-zoned-sharding.md)**: Siklus pemecahan chunk (*chunk splits*), balancer window execution, *jumbo chunks recovery*, dan pemisahan data geografis via *Zoned/Tag-Aware Sharding*.

### [Bab 09: Enterprise Security, Governance & CSFLE](./bab-09-security-governance/README.md)
Menerapkan protokol pertahanan berlapis untuk melindungi data terestrial dan data transit sesuai standar kepatuhan PCI-DSS, HIPAA, dan GDPR.
* **[Modul 01: Authentication & Granular RBAC](./bab-09-security-governance/modul-01-auth-rbac.md)**: Implementasi SCRAM-SHA-256, autentikasi berbasis sertifikat mTLS/x.509, integrasi federasi Active Directory/LDAP, pembuatan Custom Roles berprinsip least-privilege.
* **[Modul 02: Encryption-at-Rest & Client-Side Field Level Encryption (CSFLE)](./bab-09-security-governance/modul-02-encryption-csfle.md)**: Konfigurasi WiredTiger Encrypted Storage Engine via KMIP/AWS KMS, implementasi CSFLE & Queryable Encryption (QE) untuk perlindungan data PII.
* **[Modul 03: Auditing Protocols, Network Isolation & Compliance](./bab-09-security-governance/modul-03-auditing-compliance.md)**: Konfigurasi log audit JSON terstruktur, proteksi network interface (`bindIp`), firewalls, IP allowlisting, dan compliance logging validation.

### [Bab 10: Site Reliability Engineering, Diagnostics & Tuning](./bab-10-sre-diagnostics/README.md)
Metodologi pemeliharaan production-grade: profiling latensi rendah, tuning kernel subsistem Linux, serta pengoperasian sistem pemulihan krisis.
* **[Modul 01: Linux OS Kernel Tuning & WiredTiger Cache Sizing](./bab-10-sre-diagnostics/modul-01-os-cache-tuning.md)**: Konfigurasi NUMA memory interleaving, Transparent Huge Pages (THP) deactivation, disk schedulers, limits (`ulimit`), dan alokasi `storage.wiredTiger.engineConfig.cacheSizeGB`.
* **[Modul 02: Diagnostics via FTDC, Profiler & Metrics Interpretation](./bab-10-sre-diagnostics/modul-02-ftdc-profiler-metrics.md)**: Ekstraksi metrik *Full-Time Diagnostic Data Capture* (FTDC), analisis *Database Profiler*, identifikasi lonjakan *queued operations* dan *page faults*.
* **[Modul 03: Zero-Downtime Backup, Point-in-Time Recovery & Chaos Engineering](./bab-10-sre-diagnostics/modul-03-backup-pitr-chaos.md)**: Prosedur backup konsisten menggunakan filesystem LVM/EBS snapshots, replikasi arsip Oplog untuk Point-In-Time Recovery (PITR), dan simulasi partisi jaringan via Chaos Testing.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**Global High-Frequency Ledger & Telemetry Logistics Engine (GHF-LTLE)**

```
                                ARSITEKTUR CAPSTONE ENTERPRISE
  
  [ Client Application / API Gateway ] (mTLS + Automatic CSFLE Engine)
                 |
                 +-----------------------+-----------------------+
                 |                       |                       |
                 v                       v                       v
          [ mongos - 01 ]         [ mongos - 02 ]         [ mongos - 03 ]
                 |                       |                       |
                 +-----------------------+-----------------------+
                                         |
                 +-----------------------+-----------------------+
                 | (Metadata Routing)                            |
                 v                                               |
      [ Config Server Replica ]                                  |
      [   (CSRS - 3 Nodes)    ]                                  |
                                                                 |
        +--------------------------------------------------------+
        |
        +-----------------------------------+-----------------------------------+
        |                                   |                                   |
        v                                   v                                   v
  [ SHARD 01 (EMEA Zone) ]            [ SHARD 02 (APAC Zone) ]            [ SHARD 03 (AMER Zone) ]
  +----------------------+            +----------------------+            +----------------------+
  | Node 1: Primary      |            | Node 1: Primary      |            | Node 1: Primary      |
  | Node 2: Secondary    |            | Node 2: Secondary    |            | Node 2: Secondary    |
  | Node 3: Secondary    |            | Node 3: Secondary    |            | Node 3: Secondary    |
  | (WiredTiger + CSFLE) |            | (WiredTiger + CSFLE) |            | (WiredTiger + CSFLE) |
  +----------------------+            +----------------------+            +----------------------+
```

### Gambaran Skenario
Peserta ditugaskan membangun inti platform data terdistribusi untuk perusahaan logistik multinasional yang mencakup 3 benua (EMEA, APAC, AMER). Sistem harus mencatat jutaan event telemetri armada logistik per detik secara real-time sekaligus memproses transaksi finansial multi-mata uang dengan jaminan konsistensi absolut (ACID) dan perlindungan data PII sesuai regulasi data sovereignty (GDPR di Eropa, PDPA di APAC).

### Persyaratan Arsitektural & Fungsional
1. **Topologi Klaster**:
   - Skala Sharded Cluster: 3 Shard (masing-masing berupa 3-node Replica Set).
   - Config Server Replica Set (CSRS) 3 node.
   - Minimal 2 instance `mongos` router dengan failover layer.
2. **Advanced Data Modeling**:
   - Skema Telemetri Truk: Mengimplementasikan **Bucket Pattern** (dokumen menampung data sensor per jam per kendaraan, maksimal 60 sub-dokumen metrik) untuk mencegah *document growth fragmentation*.
   - Skema Akun Ledger: Mengimplementasikan **Optimistic Concurrency Control** dengan array mutasi saldo terkompresi.
3. **Zoned / Tag-Aware Sharding**:
   - Konfigurasi zonasi berbasis benua (`regionKey: "EMEA"`, `"APAC"`, `"AMER"`).
   - Data transaksi pengguna regional dijamin disimpan secara fisik hanya pada node Shard di zona geografis bersangkutan.
4. **Keamanan & Regulasi**:
   - Implementasi **Client-Side Field Level Encryption (CSFLE)** menggunakan integrasi AWS KMS / HashiCorp Vault. Field PII seperti `tax_identification_number` dan `driver_license_number` harus terenkripsi secara deterministik/acak sebelum melewati layer transport network.
   - Konfigurasi granular Role-Based Access Control (RBAC) dengan 3 profil akses: `app-service`, `read-analytics`, dan `sre-admin`.
5. **Jaminan Transaksi & Kueri**:
   - Transaksi transfer saldo antar akun logistik menggunakan transaksi multi-dokumen dengan konfigurasi `writeConcern: { w: "majority", wtimeout: 5000 }` dan `readConcern: "snapshot"`.
   - Pipeline analitik multi-tahap agregasi untuk kalkulasi biaya operasional bulanan armada via `$setWindowFields` tanpa memicu alokasi memori berlebih (`allowDiskUse: false`).

### Kriteria Verifikasi & Kelulusan Pengujian
- **Performance Benchmark**: Mampu menangani beban uji tulis konkurensi tinggi minimal **15,000 writes/sec** dengan latensi p99 < 15ms menggunakan automated load generator (Go / k6).
- **Zero Data Loss Under Failure**: Simulasi terminasi paksa (`SIGKILL`) pada satu node Primary pada Shard 01 saat eksekusi mutasi transfer saldo massal berlangsung. Klaster wajib melakukan evaluasi konsensus failover otomatis < 10 detik tanpa ada data yang korup atau transaksi berstatus inkonsisten (*no orphan balance records*).
- **Index Optimization Audit**: Menghasilkan zero collection scans (`COLLSCAN = 0`) pada seluruh query operasional yang tercatat di profil log database (`db.system.profile`).
- **Data Sovereignty Compliance Proof**: Validasi via perintah `explain()` bahwa query berdasar rentang wilayah geografis diarahkan eksklusif ke shard yang sesuai secara deterministik tanpa scatter-gather query broadcast.

---

## 5. Standar Kontribusi & Panduan Kode

Untuk memastikan konsistensi dan kualitas tingkat enterprise pada setiap modul yang Anda tulis atau modifikasi:
- Kode skrip mongo shell harus kompatibel dengan `mongosh` versi 2.x+.
- Konfigurasi klaster harus disediakan dalam format YAML yang valid.
- Semua kueri optimasi wajib menyertakan verifikasi output blok JSON `executionStats`.
- Penggunaan perintah *deprecated* (seperti `insert()`, `update()`, atau `remove()` lama) dilarang keras; wajib menggunakan `insertOne()`, `insertMany()`, `updateOne()`, `updateMany()`, atau `bulkWrite()`.

Selamat mengeksplorasi kurikulum MongoDB Enterprise. Mulai perjalanan Anda dari **[Bab 01: Core Architecture, Document Model & BSON Internals](./bab-01-core-architecture/README.md)**.