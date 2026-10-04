# Production-Grade SQL Engineering: Architecture, Internals, and Scalability

Selamat datang di kurikulum teknis komprehensif **Production-Grade SQL Engineering**. Kurikulum ini dirancang untuk menjembatani kesenjangan antara penulisan query tingkat pemula dengan perancangan arsitektur basis data relasional berperforma tinggi untuk sistem enterprise bersekala besar.

---

## 1. Course Overview & Engineering Mindset

SQL bukan sekadar bahasa query deklaratif; SQL adalah antarmuka komputasi formal berbasis aljabar relasional yang berinteraksi langsung dengan sistem operasi, subsistem I/O, memori (buffer pool), dan struktur disk. Menguasai SQL di tingkat industri menuntut pemahaman mendalam tentang:

*   **Logical Query Processing Order**: Bagaimana database engine memecah, memvalidasi, dan mengeksekusi instruksi secara matematis, bukan berdasarkan urutan penulisan sintaks.
*   **Storage Engine & Indexing Internals**: Struktur fisik halaman data (*pages/blocks*), alur kerja B-Tree, LSM-Tree, heap, serta bagaimana pointer dan clustered index mengatur overhead I/O.
*   **Execution Plan & Cost-Based Optimizer (CBO)**: Membaca operator fisik (*Nested Loop, Hash Join, Merge Join, Index Scan vs. Index Seek*) dan mengeliminasi *table bloat* serta disk spill.
*   **Concurrency Control & Transaction Isolation**: Mengendalikan ACID, write-ahead logging (WAL), multi-version concurrency control (MVCC), anomali data tingkat lanjut (*write skew, phantom reads*), dan resolusi deadlock.
*   **Modern Data Modeling & Scale**: Menangani semi-structured data (JSONB), window analytical functions, recursive graph queries, serta horizontal partitioning pada skala terabita.

---

## 2. Learning Roadmap

Berikut adalah visualisasi alur pembelajaran dari level dasar (fondasi relasional) hingga tingkat lanjut (skalabilitas dan engine tuning):

```text
========================================================================================
                     PRODUCTION-GRADE SQL ENGINEERING ROADMAP
========================================================================================
[Bab 01: Relational Foundations, Architecture & DDL]
  │
  ├──► [Bab 02: Logical Query Processing & Data Retrieval (DML Part 1)]
  │      │
  │      └──► [Bab 03: Relational Joins, Set Operations, & Subqueries]
  │             │
  │             └──► [Bab 04: Aggregations, Grouping, & Dimensional Analysis]
  │                    │
  │                    └──► [Bab 05: Advanced Window Functions & Analytical SQL]
  │
  ┌─────────────────────────────────────────────────────────────────────────────────────┘
  ▼
[Bab 06: Data Mutations, Upserts, & Recursive CTEs (DML Part 2)]
  │
  ├──► [Bab 07: Storage Engines, Physical Layout, & Indexing Architecture]
  │      │
  │      └──► [Bab 08: Query Optimizer, Execution Plans, & Performance Profiling]
  │             │
  │             └──► [Bab 09: Transactions, Concurrency, Locking, & MVCC]
  │                    │
  │                    └──► [Bab 10: Partitioning, Advanced Schema Design, & Programmability]
  │
  └─────────────────────────────────────────────────────────────────────────────────────┐
                                                                                        ▼
                                                                           [ENTERPRISE CAPSTONE]
========================================================================================
```

---

## 3. Detail Navigasi Modul (Bab 01 s/d Bab 10)

### [Bab 01: Relational Foundations, Architecture & DDL](./01-relational-foundations-architecture-and-ddl/README.md)
Fondasi teoretis sistem relasional, arsitektur client-server database, dan konstruksi skema dengan integritas referensial ketat.
*   [01. Aljabar Relasional, Teori Himpunan, dan Prinsip ACID](./01-relational-foundations-architecture-and-ddl/01-relational-algebra-and-acid.md)
*   [02. Data Definition Language (DDL): Data Types, Constraints, dan Normalisasi (1NF-BCNF)](./01-relational-foundations-architecture-and-ddl/02-ddl-datatypes-constraints-and-normalization.md)
*   [03. Anatomi Engine: Buffer Pool, Storage Engines, Heap, dan WAL System](./01-relational-foundations-architecture-and-ddl/03-database-engine-anatomy-and-wal.md)

### [Bab 02: Logical Query Processing & Data Retrieval](./02-logical-query-processing-and-data-retrieval/README.md)
Mendalami alur kerja eksekusi deklaratif `SELECT` dan teknik pemfilteran data berpresisi tinggi.
*   [01. Siklus Hidup Eksekusi Query: Parser, Planner, Optimizer, dan Execution Lifecycle](./02-logical-query-processing-and-data-retrieval/01-query-execution-lifecycle.md)
*   [02. Predikat Filtering, Sargability, dan Three-Valued Logic (3VL) NULL Semantics](./02-logical-query-processing-and-data-retrieval/02-filtering-sargability-and-null-semantics.md)
*   [03. Pattern Matching Lanjutan (LIKE, POSIX Regex) dan Evaluasi Ekspresi Bertahap](./02-logical-query-processing-and-data-retrieval/03-pattern-matching-and-expression-evaluation.md)

### [Bab 03: Relational Joins, Set Operations, & Subqueries](./03-relational-joins-set-operations-and-subqueries/README.md)
Penggabungan data multi-relasi, aljabar himpunan fisik, dan pembedahan dependensi subquery.
*   [01. Aljabar dan Algoritma JOIN: Nested Loops, Hash Joins, dan Merge Joins](./03-relational-joins-set-operations-and-subqueries/01-join-algorithms-and-internals.md)
*   [02. Inner, Outer, Cross, Self, dan Non-Equi Joins dalam Skenario Produksi](./03-relational-joins-set-operations-and-subqueries/02-join-types-and-production-patterns.md)
*   [03. Subqueries (Scalar, Correlated, EXISTS vs IN), LATERAL Joins, dan Operasi Himpunan](./03-relational-joins-set-operations-and-subqueries/03-subqueries-lateral-joins-and-set-operations.md)

### [Bab 04: Aggregations, Grouping, & Dimensional Analysis](./04-aggregations-grouping-and-dimensional-analysis/README.md)
Transformasi data multidimensi, kalkulasi metrik agregat, dan penanganan filtering data agregat.
*   [01. Mekanisme Pemrosesan `GROUP BY` dan Algoritma Hash Aggregate vs Stream/Sort Aggregate](./04-aggregations-grouping-and-dimensional-analysis/01-group-by-processing-and-algorithms.md)
*   [02. Eliminasi Anomali Agregat: `HAVING` vs `WHERE`, Semantik Filter, dan Conditional Aggregates](./04-aggregations-grouping-and-dimensional-analysis/02-having-mechanics-and-conditional-aggregates.md)
*   [03. Pengelompokan Data Dimensi Tinggi: `ROLLUP`, `CUBE`, dan `GROUPING SETS`](./04-aggregations-grouping-and-dimensional-analysis/03-rollup-cube-and-grouping-sets.md)

### [Bab 05: Advanced Window Functions & Analytical SQL](./05-advanced-window-functions-and-analytical-sql/README.md)
Analisis analitik sekuensial enterprise, komputasi tren time-series, dan optimasi window memory.
*   [01. Anatomi Window Functions: Sintaks `OVER()`, `PARTITION BY`, dan Pemilihan Framing](./05-advanced-window-functions-and-analytical-sql/01-window-syntax-and-framing-specifications.md)
*   [02. Ranking, Lead/Lag, Running Totals, Moving Averages, dan Value Distribution](./05-advanced-window-functions-and-analytical-sql/02-ranking-offset-and-statistical-functions.md)
*   [03. Optimasi Kinerja Window Functions dan Penghindaran Disk Spilling pada Frame Besar](./05-advanced-window-functions-and-analytical-sql/03-window-memory-and-performance-optimization.md)

### [Bab 06: Data Mutations, Upserts, & Recursive CTEs](./06-data-mutations-upserts-and-recursive-ctes/README.md)
Mutasi data atomik, manipulasi hierarki kompleks, dan manajemen state transactional data.
*   [01. Mutasi Data Presisi: Atomisitas `INSERT`, `UPDATE`, `DELETE`, dan Klausa `RETURNING`](./06-data-mutations-upserts-and-recursive-ctes/01-atomic-dml-and-returning-clauses.md)
*   [02. Strategi Idempoten: `MERGE` Statement vs `ON CONFLICT DO UPDATE/NOTHING` (Upserts)](./06-data-mutations-upserts-and-recursive-ctes/02-upsert-strategies-and-merge-mechanics.md)
*   [03. Common Table Expressions (CTEs) dan Recursive CTEs untuk Data Graf/Hierarki](./06-data-mutations-upserts-and-recursive-ctes/03-common-table-expressions-and-hierarchical-recursion.md)

### [Bab 07: Storage Engines, Physical Layout, & Indexing Architecture](./07-storage-engines-physical-layout-and-indexing/README.md)
Tata letak biner pada disk, struktur data indeks, dan optimalisasi arsitektur pencarian.
*   [01. Organisasi Halaman Fisik Data, Row Pointer, Slotted Page Architecture, dan Heap Fragmentation](./07-storage-engines-physical-layout-and-indexing/01-physical-storage-pages-and-slotted-pages.md)
*   [02. Arsitektur B-Tree dan B+Tree Index: Root, Branch, Leaf Page, Page Splits, dan Fill Factor](./07-storage-engines-physical-layout-and-indexing/02-b-tree-internals-and-page-splits.md)
*   [03. Indeks Tingkat Lanjut: Composite Indexes, Partial Indexes, Expression/Functional Indexes, dan Covering Indexes (INCLUDE)](./07-storage-engines-physical-layout-and-indexing/03-advanced-indexing-strategies-and-covering-indexes.md)

### [Bab 08: Query Optimizer, Execution Plans, & Performance Profiling](./08-query-optimizer-execution-plans-and-profiling/README.md)
Diagnostik engine mendalam, decoding execution plan, dan rekayasa ulang query berbiaya tinggi.
*   [01. Anatomi Execution Plan: Membaca `EXPLAIN (ANALYZE, BUFFERS)` dan Metrik Biaya (Cost vs Actual)](./08-query-optimizer-execution-plans-and-profiling/01-reading-and-analyzing-execution-plans.md)
*   [02. Mekanisme Cost-Based Optimizer (CBO), Histogram Statistik Data, dan Selektivitas Predikat](./08-query-optimizer-execution-plans-and-profiling/02-optimizer-statistics-and-selectivity.md)
*   [03. Anti-Patterns Kritis dan Refactoring: Mengatasi Cartesian Products, Bad Sargability, dan Implicit Conversions](./08-query-optimizer-execution-plans-and-profiling/03-anti-patterns-and-query-refactoring.md)

### [Bab 09: Transactions, Concurrency, Locking, & MVCC](./09-transactions-concurrency-locking-and-mvcc/README.md)
Manajemen konkurensi tingkat rendah, proteksi integritas transaksi, dan mitigasi bottleneck lock.
*   [01. Tingkat Isolasi Transaksi SQL (Read Uncommitted hingga Serializable) dan Fenomena Anomali](./09-transactions-concurrency-locking-and-mvcc/01-transaction-isolation-and-anomalies.md)
*   [02. Multi-Version Concurrency Control (MVCC): Snapshot Isolation, Vacuuming/Purging, dan Freeze Operations](./09-transactions-concurrency-locking-and-mvcc/02-mvcc-mechanics-and-vacuum-lifecycle.md)
*   [03. Mekanisme Locking: Shared/Exclusive Locks, Row-Level vs Table-Level, Deteksi dan Penanganan Deadlock](./09-transactions-concurrency-locking-and-mvcc/03-locking-mechanisms-and-deadlock-prevention.md)

### [Bab 10: Partitioning, Advanced Schema Design, & Programmability](./10-partitioning-advanced-schema-design-and-programmability/README.md)
Skalabilitas tabel multiterabita, pemrosesan semi-terstruktur, dan logika terprogram di lapisan basis data.
*   [01. Partisi Tabel Horizontal: Range, List, Hash Partitioning, Partition Pruning, dan Maintenance](./10-partitioning-advanced-schema-design-and-programmability/01-table-partitioning-and-partition-pruning.md)
*   [02. Data Semi-Terstruktur: Penyimpanan, Querying, dan Indexing Dokumen JSON/JSONB](./10-partitioning-advanced-schema-design-and-programmability/02-semi-structured-data-jsonb-and-gin-indexes.md)
*   [03. Database Programmability: Stored Procedures, UDFs, Triggers, Views, dan Materialized Views](./10-partitioning-advanced-schema-design-and-programmability/03-programmability-procedures-triggers-views.md)

---

## 4. Enterprise Capstone Project

### Real-Time Financial Core-Banking Ledger & Settlement Engine

Pada akhir kursus, peserta akan merancang, mengimplementasikan, dan mengoptimalkan sistem basis data relasional enterprise skala penuh: **Global Multi-Currency Double-Entry Ledger & High-Throughput Clearing Engine**.

#### Spesifikasi Fungsional & Teknis:
1.  **Strict Double-Entry Bookkeeping Model**:
    *   Setiap pergerakan dana dicatat sebagai pasangan debit dan kredit dalam tabel ledger yang tidak dapat diubah (*immutable append-only*).
    *   Kendali integritas matematis: Total debit harus sama persis dengan total kredit pada tingkat transaksi melalui *deferred constraint checks*.
2.  **Concurrency & Isolation Control**:
    *   Mencegah *race conditions* pada penarikan saldo simultan menggunakan pesimistik locking berbasis `SELECT ... FOR UPDATE` dan optimistik locking teruji.
    *   Isolasi transaksi terisolasi tanpa deadlock pada throughput tinggi (target: > 3.000 TPS transaksi campuran).
3.  **Horizontal Table Partitioning**:
    *   Tabel audit log dan transaksi buku besar dipartisi menggunakan metode *Declarative Range Partitioning* berbasis rentang tanggal bulanan.
    *   Implementasi retensi data otomatis dan validasi mekanisme *partition pruning* pada execution plan query audit.
4.  **Advanced Window Aggregations**:
    *   Pembuatan modul settlement analitik akhir hari (*End-of-Day Balancing*) menggunakan window functions (`SUM() OVER (PARTITION BY account_id ORDER BY created_at ROWS UNBOUNDED PRECEDING)`).
    *   Perhitungan moving variance 30 hari untuk deteksi anomali fraud secara real-time.
5.  **Index Optimization & Performance Tuning**:
    *   Penggunaan *partial indexes* untuk transaksi dengan status `PENDING_CLEARING`.
    *   Pembuatan *covering index* (`INCLUDE`) untuk pelaporan mutasi harian, memastikan status **Index Only Scan** tercapai 100% tanpa disk read pada tabel utama.
    *   Penyusunan benchmark `EXPLAIN (ANALYZE, BUFFERS)` sebelum dan sesudah refactoring untuk membuktikan reduksi shared buffer hit dan eksekusi sub-milidetik.

Proyek ini menjadi bukti kemampuan arsitektural database peserta bahwa solusi yang dibangun siap menghadapi beban produksi skala tier-1 dengan integritas nol-kompromi.