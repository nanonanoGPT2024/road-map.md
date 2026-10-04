# Kurikulum Enterprise: Relational Databases & Production-Grade SQL Engine
**Track:** 08-AI-Data-and-Autonomous-Agents  
**Topik:** Data Analyst / Analytics Engineer  
**Bab 03:** Relational Databases & Production-Grade SQL Engineering  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level enterprise diharapkan mampu:
1. **Menganalisis Internal Storage Engine**: Membedah struktur halaman disk (PostgreSQL 8KB Page/Slotted-page architecture), mekanisme Write-Ahead Logging (WAL), dan Multi-Version Concurrency Control (MVCC) untuk memitigasi table bloat dan read/write contention.
2. **Menguasai Advanced Analytical SQL Pattern**: Mengimplementasikan algoritma windowing tingkat lanjut (frame clause sliding windows), Recursive Common Table Expressions (CTE) untuk data graf/hierarki, serta pola *Gaps and Islands* untuk analisis sesi pengguna.
3. **Mendekomposisi dan Mengoptimalkan Query Plan**: Menafsirkan output `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` secara presisi, mengidentifikasi perbedaan komputasi antara *Nested Loop*, *Hash Join*, dan *Merge Join*, serta mengeliminasi bottleneck *Buffer Spill to Disk* (`work_mem`).
4. **Mendesain Arsitektur Database Analitik Skala Produksi**: Mengonfigurasi strategi *Declarative Partitioning*, *Partial/Covering Indexes* ($B\text{-Tree}$ dan BRIN), serta integrasi *Read Replicas* dan *Connection Pooling* (PgBouncer) untuk beban kerja analitik *read-heavy*.

---

## 2. Prerequisite

Sebelum menempuh modul ini, peserta wajib menguasai:
- **Foundational SQL**: `SELECT`, `JOIN` (INNER, LEFT, FULL, CROSS), agregasi standar (`GROUP BY`, `HAVING`), dan subquery.
- **Konsep Relasional Inti**: ACID properties, Entity-Relationship Diagram (ERD), skema normalisasi (3NF) vs denormalisasi (Star/Snowflake Schema).
- **Sistem Operasi & Storage Dasar**: Mekanisme I/O disk, latency tier (L1/L2 Cache vs RAM vs NVMe vs Network Attached Storage), dan konsep dasar pagination memori.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi PostgreSQL Page Layout & MVCC
Database relasional enterprise seperti PostgreSQL tidak membaca atau menulis baris (*tuples*) secara individual ke storage engine, melainkan dalam satuan blok memori yang disebut **Page** (standar: 8 KB).

```
+-----------------------------------------------------------------------+
| PageHeaderData (24 bytes: LSN, checksum, flags, pd_lower, pd_upper)   |
+------------------------------------+----------------------------------+
| ItemIdData [1] (offset, flags, len)| ItemIdData [2] (offset, flags...) |
+------------------------------------+----------------------------------+
|               <--- Free Space Allocator (pd_lower)                    |
|                                                                       |
|               (pd_upper) --->                                         |
+-----------------------------------------------------------------------+
| Tuple 2 (HeapTupleHeaderData: t_xmin, t_xmax, t_ctid | User Data...)   |
+-----------------------------------------------------------------------+
| Tuple 1 (HeapTupleHeaderData: t_xmin, t_xmax, t_ctid | User Data...)   |
+-----------------------------------------------------------------------+
```

- **HeapTupleHeaderData**: Memuat metadata MVCC:
  - `t_xmin`: ID transaksi (`txid`) yang menyisipkan (*insert*) tuple tersebut.
  - `t_xmax`: ID transaksi yang menghapus (*delete*) atau memperbarui (*update*) tuple tersebut (update direpresentasikan secara internal sebagai soft-delete + insert baris baru).
  - `t_ctid`: Pointer fisik `(block_number, offset)` yang menunjuk ke versi tuple saat ini atau versi terbarunya.
- **MVCC & Table Bloat**: Ketika operasi `UPDATE` intensif terjadi, tuple lama dipertahankan (*dead tuples*) hingga transaksi tertua yang aktif selesai membacanya. Kegagalan proses `VACUUM` memicu pembengkakan tabel (*bloat*), meningkatkan sequential scan I/O dan mendegradasi shared buffer pool.

### 3.2 Query Lifecycle & The Cost-Based Optimizer (CBO)
Ketika analytical query dikirim ke database engine:

```
[SQL String]
     │
     ▼
[Parser] ─────────► Abstract Syntax Tree (AST)
     │
     ▼
[Analyzer/Rewriter] ──► Query Tree (Resolve Views, RLS, Type Coercion)
     │
     ▼
[Cost-Based Optimizer (CBO)]
     ├─ Read Statistics (pg_statistic, ANALYZE: n_distinct, mcv, histogram)
     ├─ Generate Execution Paths (Scan: Seq, Index, Bitmap; Join: NL, Hash, Merge)
     └─ Select Lowest Total Cost: (Disk I/O Cost + CPU Operation Cost)
     │
     ▼
[Execution Plan Engine]
     ├─ Read via Shared Buffers (Hit: RAM / Miss: OS Page Cache / Disk)
     └─ Emit Tuple Stream to Client
```

#### Join Algorithms Comparison
1. **Nested Loop Join**: Kompleksitas $O(M \times N)$ tanpa indeks, atau $O(M \log N)$ dengan index scan pada *inner table*. Ideal untuk dataset kecil atau analytical query yang sangat terfilter.
2. **Hash Join**:
   - *Phase 1 (Build)*: Engine membaca *inner table*, menghitung hash value dari join key, dan membangun *in-memory Hash Table* pada alokasi `work_mem`.
   - *Phase 2 (Probe)*: Engine memindai *outer table*, menghitung hash key, dan memetakan langsung ke Hash Table.
   - *Spill to Disk*: Jika ukuran hash table melebihi `work_mem`, PostgreSQL memecah proses menjadi *multi-batch hash join* dengan menulis batch temporer ke disk, yang menurunkan throughput hingga 90%.
3. **Merge Join**: Kompleksitas $O(M \log M + N \log N)$ untuk sorting, dilanjutkan dengan $O(M + N)$ scan paralel terurut. Sangat efisien jika data input sudah terurut dari $B\text{-Tree}$ index atau physical ordering.

---

## 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Production-Grade Analytical Engineering |
| :--- | :--- | :--- |
| **Window Processing** | Menggunakan multiple self-join untuk agregasi berjalan (*rolling metrics*). | Menggunakan Frame Clause eksplisit (`ROWS BETWEEN ...`) untuk komputasi $O(N)$ streaming di RAM. |
| **Hierarchical Queries**| Iterasi procedural berbasis aplikasi (*N+1 query problem* via ORM). | Recursive CTE native yang diproses di internal execution engine dengan buffer terisolasi. |
| **Indexing** | Single-column B-Tree pada semua foreign key (menyebabkan storage amplification). | Covering Indexes (`INCLUDE`), Composite Indexes terurut berdasarkan *cardinality & filtering*, serta BRIN untuk append-only timestamp data. |
| **Scale Management** | Mengandalkan vertikal scaling CPU/RAM saat tabel mencapai ratusan juta baris. | Declarative Partitioning dipadukan dengan *Constraint Exclusion* & *Partition Pruning*. |

---

## 5. How (Workflow Detail)

Alur kerja audit, tuning, dan implementasi kueri analitik kelas produksi:

```
[1. Problem Identification]
     │
     ├─ Tangkap query lambat via pg_stat_statements (total_exec_time / calls)
     └─ Monitor lock contention via pg_stat_activity
     │
     ▼
[2. Execution Plan Profiling]
     │
     ├─ Jalankan: EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL) <QUERY>
     ├─ Identifikasi gap antara Cost Estimate (E-Rows) vs Actual Rows
     └─ Periksa metrik: "Buffers: shared hit, read, dirtied, written" & "Temp written"
     │
     ▼
[3. Structural Remediation]
     │
     ├─ Statistika Usang? ────► Jalankan: ANALYZE VERBOSE <target_table>
     ├─ Temp Buffers Disk? ───► Naikkan work_mem per-session: SET work_mem = '256MB'
     ├─ Seq Scan Masif? ──────► Rancang Index (B-Tree Composite / Covering Index)
     └─ Skala Data > 50M? ────► Terapkan Range Partitioning pada dimensi waktu
     │
     ▼
[4. Architectural Isolation]
     │
     ├─ Arahkan query ke Read Replica via Load Balancer / PgBouncer
     └─ Terapkan statement_timeout untuk mencegah query run-away
```

---

## 6. Analogy & Diagram ASCII

### Analogi Slotted-Page & Indexing
Bayangkan sebuah **Page 8 KB** sebagai map folder arsip tebal:
- **Heap Table**: Dokumen dilempar sembarangan ke dalam map folder tanpa urutan (*heap*). Di awal map, ada daftar indeks kecil (*ItemId*) yang menunjuk posisi lembar kertas di dalam map tersebut.
- **Index Scan vs Sequential Scan**:
  - *Sequential Scan*: Petugas memeriksa seluruh lembar map satu demi satu dari gedung arsip (Disk) ke mejanya (RAM).
  - *Index Scan*: Petugas membaca buku katalog terpisah yang tersusun rapi secara alfabetis ($B\text{-Tree}$), menemukan nomor map dan nomor lembar, lalu mengambil hanya map yang dibutuhkan.
  - *Index Only Scan*: Petugas membaca buku katalog, dan semua data yang dicari ternyata sudah tercantum di buku katalog tersebut (`INCLUDE` clause), sehingga ia tidak perlu menyentuh map tebal sama sekali.

```
       B-Tree Index File                           Heap Data Pages (8KB each)
   +-----------------------+                    +-------------------------------+
   |      Root Node        |                    | Page 104                      |
   +-----------+-----------+                    | +---------------------------+ |
               |                                | | ItemId 1 -> [Tuple A]     | |
         +-----+-----+                          | | ItemId 2 -> [Tuple B]     | |
         |           |                          +-------------------------------+
   +-----v---+   +---v-----+                                    ^
   | Leaf 1  |   | Leaf 2  |                                    |
   +---------+   +----+----+                                    |
                      |                                         |
                      +-- Pointer (Block 104, Offset 2) --------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Framing Clause Eksplisit vs Default
Banyak analis menggunakan `AVG(amount) OVER (PARTITION BY user_id ORDER BY transacted_at)` tanpa menyadari bahwa default framing clause adalah `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Ini memaksa database engine menduplikasi evaluasi baris dengan nilai waktu yang sama.

```sql
-- Buruk (Default RANGE: Konsumsi CPU tinggi, mengevaluasi duplikasi secara lambat)
SELECT 
    transacted_at,
    amount,
    AVG(amount) OVER (
        PARTITION BY user_id 
        ORDER BY transacted_at
    ) AS naive_rolling_avg
FROM payment_ledger;

-- Produksi (ROWS Eksplisit: Engine menggeser pointer frame secara linear O(1) di RAM)
SELECT 
    transacted_at,
    amount,
    AVG(amount) OVER (
        PARTITION BY user_id 
        ORDER BY transacted_at
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS optimized_7day_rolling_avg
FROM payment_ledger;
```

### 7.2 Practical Example: Pola Gaps and Islands untuk Sessionization Engine
Skenario analitik: Identifikasi sesi interaksi pengguna aplikasi. Sebuah sesi dianggap putus jika terdapat jeda aktivitas $> 30$ menit.

```sql
WITH user_event_lag AS (
    SELECT 
        event_id,
        user_id,
        event_timestamp,
        -- Ekstrak timestamp event sebelumnya untuk user yang sama
        LAG(event_timestamp) OVER (
            PARTITION BY user_id 
            ORDER BY event_timestamp
        ) AS prev_event_timestamp
    FROM user_clickstream_events
),
session_flags AS (
    SELECT 
        event_id,
        user_id,
        event_timestamp,
        -- Evaluasi Gap: Jika jeda > 30 menit atau ini record pertama, tandai session baru (flag = 1)
        CASE 
            WHEN prev_event_timestamp IS NULL THEN 1
            WHEN event_timestamp > prev_event_timestamp + INTERVAL '30 minutes' THEN 1
            ELSE 0 
        END AS is_new_session
    FROM user_event_lag
),
session_grouping AS (
    SELECT 
        event_id,
        user_id,
        event_timestamp,
        -- Running Sum untuk membuat unique ID 'Island' sesi
        SUM(is_new_session) OVER (
            PARTITION BY user_id 
            ORDER BY event_timestamp 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS user_session_seq
    FROM session_flags
)
SELECT 
    user_id,
    -- Deterministic Unique Session Hash
    MD5(user_id || '-' || user_session_seq::text) AS session_id,
    MIN(event_timestamp) AS session_started_at,
    MAX(event_timestamp) AS session_ended_at,
    COUNT(event_id) AS total_events_in_session,
    EXTRACT(EPOCH FROM (MAX(event_timestamp) - MIN(event_timestamp))) AS session_duration_seconds
FROM session_grouping
GROUP BY user_id, user_session_seq;
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Rekonsiliasi Settlement Multi-Tier pada Fintech Gateway
- **Volume Data**: 60 juta transaksi pembayaran per bulan.
- **Problem**: Query laporan settlement bulanan memicu *out of memory* (OOM crash) pada server analitik dan memakan waktu scan $> 45$ menit karena melakukan self-join untuk memverifikasi dependensi transaksi induk (*parent transactions*) dengan multi-split settlement (*refund*, *fee cut*, dan *merchant payout*).

### Arsitektur Solusi
1. **Partitioning**: Range partitioning bulanan berdasarkan `created_at`.
2. **Covering Index**: Memastikan rekonsiliasi dapat diselesaikan hanya dengan *Index Only Scan*.
3. **Recursive CTE**: Menelusuri seluruh chain transaksi turunan tanpa nesting join tak terbatas.

```sql
-- 1. Skema Partisi Declarative
CREATE TABLE settlement_ledger (
    ledger_id UUID NOT NULL,
    parent_ledger_id UUID,
    merchant_id INT NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    fee_amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (ledger_id, created_at)
) PARTITION BY RANGE (created_at);

-- Partisi Q1
CREATE TABLE settlement_ledger_2024_01 PARTITION OF settlement_ledger
    FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2024-02-01 00:00:00+00');

CREATE TABLE settlement_ledger_2024_02 PARTITION OF settlement_ledger
    FOR VALUES FROM ('2024-02-01 00:00:00+00') TO ('2024-03-01 00:00:00+00');

-- 2. Covering Composite Index untuk Eliminasi Heap Access
CREATE INDEX idx_settlement_reconcile_covering ON settlement_ledger (merchant_id, created_at)
INCLUDE (amount, fee_amount, status, parent_ledger_id);

-- 3. Production Query Menggunakan Recursive CTE & Partition Pruning
EXPLAIN (ANALYZE, BUFFERS)
WITH RECURSIVE transaction_lineage AS (
    -- Anchor Member: Ambil transaksi root level merchant tertentu pada rentang partisi
    SELECT 
        ledger_id,
        parent_ledger_id,
        merchant_id,
        amount,
        fee_amount,
        status,
        created_at,
        1 AS depth
    FROM settlement_ledger
    WHERE merchant_id = 94812
      AND created_at >= '2024-01-01 00:00:00+00' 
      AND created_at < '2024-01-31 23:59:59+00'
      AND parent_ledger_id IS NULL

    UNION ALL

    -- Recursive Member: Telusuri seluruh transaksi turunan (misal: dispute, fee adjustment)
    SELECT 
        c.ledger_id,
        c.parent_ledger_id,
        c.merchant_id,
        c.amount,
        c.fee_amount,
        c.status,
        c.created_at,
        p.depth + 1
    FROM settlement_ledger c
    INNER JOIN transaction_lineage p 
        ON c.parent_ledger_id = p.ledger_id
    WHERE c.created_at >= '2024-01-01 00:00:00+00' 
      AND c.created_at < '2024-02-28 23:59:59+00' -- Mengizinkan cross-partition resolution ke bulan berjalan
)
SELECT 
    merchant_id,
    COUNT(ledger_id) AS total_settled_records,
    SUM(amount) AS gross_transaction_value,
    SUM(fee_amount) AS total_platform_cut,
    MAX(depth) AS max_lineage_depth
FROM transaction_lineage
WHERE status = 'SUCCESS'
GROUP BY merchant_id;
```
*Hasil di Produksi*: Waktu komputasi turun dari 45 menit menjadi 1.2 detik. Buffer reads turun sebesar 98.4% karena *Partition Pruning* mematikan scanning ke partisi bulan lain, dan *Covering Index* melayani query 100% via shared buffer memory tanpa menyentuh disk heap.

---

## 9. Trade-offs

```
                           [Arsitektur Query & Skema]
                                        ▲
                                       / \
                                      /   \
                 (Write Latency)     /     \     (Storage Footprint)
                 Write Amplification/       \ Covering Indexes
                                   /         \
                                  ▼───────────▼
                           (Read Performance & Latency)
```

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Mitigasi Enterprise |
| :--- | :--- | :--- | :--- |
| **Covering Index (`INCLUDE`)** | Mengizinkan *Index Only Scan*, mengeliminasi read I/O ke heap data page. | Menambah ukuran file index secara signifikan; memperlambat operasi `INSERT`/`UPDATE` (*write amplification*). | Terapkan hanya pada tabel berkarakteristik *low-update* atau analytical dimensions. |
| **Declarative Partitioning** | *Partition Pruning* membatasi I/O scan hanya pada blok target; `DROP TABLE` instan untuk purge data lama. | Query yang tidak menyertakan *partition key* akan melakukan parallel scan ke seluruh partisi (*scatter-gather*), meningkatkan latensi. | Terapkan guardrail skema aplikasi: wajib menyertakan partisi waktu pada `WHERE` clause. |
| **Meningkatkan `work_mem`** | Mencegah Hash Join dan Order Sort tumpah ke disk (*temp file spill*), menaikkan kecepatan query analitik. | `work_mem` dialokasikan **per operasi per koneksi**. 100 concurrent connection dengan 4 join dapat memicu alokasi RAM $100 \times 4 \times 64\text{MB} = 25.6\text{ GB}$, berisiko OOM. | Konfigurasi `work_mem` secara dinamis di level session/role analitik saja, bukan global di `postgresql.conf`. |
| **BRIN Index (Block Range Index)** | Ukuran index sangat kecil (beberapa KB vs ratusan MB B-Tree). Sangat cepat untuk append-only timestamp log. | Kurang berguna jika data tidak terurut secara fisik di disk (*out-of-order writes*). | Jalankan periodik `VACUUM` dan pastikan data di-ingest secara strictly sequential. |

---

## 10. Common Mistakes & Troubleshooting

### Skenario 1: Pelanggaran SARGability (*Search Argumentable*)
- **Gejala**: Indeks pada kolom `created_at` diabaikan; query melakukan `Seq Scan` lambat.
- **Akar Masalah**: Membungkus kolom dengan fungsi SQL, membuat index lookup engine tidak dapat melintasi B-Tree.
```sql
-- ANTI-PATTERN (Non-SARGable):
SELECT * FROM orders WHERE DATE(created_at) = '2024-03-01';

-- PRODUCTION-GRADE (SARGable):
SELECT * FROM orders 
WHERE created_at >= '2024-03-01 00:00:00+00' 
  AND created_at < '2024-03-02 00:00:00+00';
```

### Skenario 2: Implicit Type Coercion
- **Gejala**: Indeks B-Tree pada kolom `varchar` di-bypass.
- **Akar Masalah**: Mengirim integer literal ke kolom teks:
```sql
-- ANTI-PATTERN:
SELECT * FROM accounts WHERE phone_number = 628112345678; -- PostgreSQL cast phone_number::int

-- PRODUCTION-GRADE:
SELECT * FROM accounts WHERE phone_number = '628112345678';
```

### Skenario 3: External Disk Sort Spills
- **Diagnosa via EXPLAIN**:
  ```text
  Sort Method: external merge  Disk: 13424kB
  ```
- **Troubleshooting Step**:
  ```sql
  -- Evaluasi penggunaan memori per session analitik
  SHOW work_mem; -- Standar default 4MB
  SET work_mem = '128MB';
  -- Jalankan kembali query. Metrik akan berubah menjadi:
  -- Sort Method: quicksort  Memory: 9812kB
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **EXPLAIN Engine Diagnostics**: Selalu jalankan `EXPLAIN (ANALYZE, BUFFERS)` sebelum melepaskan query ke production report. Pastikan tidak ada kata `external merge Disk` atau `spill to disk`.
- [ ] **SARGable Query Design**: Pastikan kolom pada `WHERE` dan `ON` tidak dibungkus oleh fungsi bawaan (`DATE()`, `LOWER()`, `SUBSTRING()`), kecuali mengimplementasikan *Expression/Functional Indexes*.
- [ ] **Index Pruning**: Hapus indeks duplikat/tidak terpakai via pemeriksaan metrik `pg_stat_user_indexes`.
- [ ] **Explicit Window Framing**: Selalu definisikan `ROWS BETWEEN ...` secara eksplisit saat memakai aggregation over ordering untuk meminimalkan alokasi frame memory.
- [ ] **Database Connection Pooling**: Query analitik yang intensif komputasi wajib terisolasi menggunakan dedicated pool (misal: PgBouncer pada pool mode *transaction* dengan instance read-replica terpisah).
- [ ] **Statement Timeout**: Terapkan limitasi query analitik runaway:
  ```sql
  SET statement_timeout = '60000'; -- Batasi eksekusi maksimal 60 detik
  ```
- [ ] **Statistik Planner Akurat**: Jalankan `ANALYZE` secara eksplisit setelah data ingestion batch skala besar untuk memperbarui tabel distribusi `pg_statistic`.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/01_setup_benchmark_env.sql`
Menyiapkan schema dan data tiruan sebesar 1.000.000 records untuk benchmark analitik.

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DROP TABLE IF EXISTS financial_transactions CASCADE;

CREATE TABLE financial_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id INT NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    is_fraud BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

-- Generate 1,000,000 baris data sintetis
INSERT INTO financial_transactions (customer_id, transaction_type, amount, is_fraud, created_at)
SELECT 
    (random() * 10000)::INT AS customer_id,
    (ARRAY['DEBIT', 'CREDIT', 'TRANSFER', 'WITHDRAWAL'])[floor(random() * 4 + 1)] AS transaction_type,
    (random() * 5000 + 10)::NUMERIC(15, 2) AS amount,
    (random() < 0.01) AS is_fraud, -- 1% data fraud
    NOW() - (random() * 365 * 24 * 60 * 60 * INTERVAL '1 second') AS created_at
FROM generate_series(1, 1000000);

-- Update statistika engine
ANALYZE financial_transactions;
```

### File: `hands-on/m02/02_diagnostics_and_index_tuning.sql`
Melakukan profiling query sebelum dan sesudah penerapan *Covering Index*.

```sql
-- LANGKAH 1: Jalankan Query Tanpa Covering Index
-- Analisis metrik Buffers: Shared Read (Disk I/O)
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT 
    customer_id,
    SUM(amount) AS total_spent
FROM financial_transactions
WHERE created_at >= '2023-06-01' AND created_at < '2023-07-01'
GROUP BY customer_id;

-- LANGKAH 2: Buat Indeks Biasa vs Covering Index
CREATE INDEX idx_transactions_created_at ON financial_transactions (created_at);

-- Bandingkan performa
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT 
    customer_id,
    SUM(amount) AS total_spent
FROM financial_transactions
WHERE created_at >= '2023-06-01' AND created_at < '2023-07-01'
GROUP BY customer_id;

-- LANGKAH 3: Terapkan Covering Index (Index Only Scan)
DROP INDEX idx_transactions_created_at;

CREATE INDEX idx_transactions_covering 
ON financial_transactions (created_at) 
INCLUDE (customer_id, amount);

-- Eksekusi lagi: Amati perubahan node dari 'Index Scan' ke 'Index Only Scan'
-- dan perhatikan metrik 'Buffers: shared hit' vs 'shared read'
EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT 
    customer_id,
    SUM(amount) AS total_spent
FROM financial_transactions
WHERE created_at >= '2023-06-01' AND created_at < '2023-07-01'
GROUP BY customer_id;
```

---

## 13. Exercise

### Level Easy
Diberikan tabel `daily_metrics (metric_date DATE, metric_name VARCHAR, value NUMERIC)`. Tulis query analitik untuk menghitung moving average 7-hari menggunakan eksplisit frame specification untuk menghindari degradasi frame range default.
- *Input Kunci*: Hindari penggunaan `AVG() OVER (ORDER BY metric_date)` polos. Terapkan klausa `ROWS BETWEEN`.

### Level Medium
Menggunakan data `financial_transactions`, rancang query untuk mendeteksi anomali: Temukan daftar pelanggan yang melakukan transaksi dengan nilai lebih besar dari $3 \times$ standar deviasi pengeluaran mereka sendiri dalam 10 transaksi terakhir (`ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING`).

### Level Hard
Selesaikan kasus **Gaps and Islands** stok inventaris:
Diberikan tabel `inventory_snapshots (snapshot_date DATE, product_id INT, is_in_stock BOOLEAN)`. Buat query analitik produksi untuk menentukan rentang tanggal (`start_date`, `end_date`) kapan saja sebuah produk berada dalam status kontinu *Out of Stock* (`is_in_stock = FALSE`) minimal selama 3 hari berturut-turut. Solusi dilarang menggunakan procedural loop (PL/pgSQL) dan wajib menggunakan window aggregation deterministic chaining.

---

## 14. Challenge

### Studi Kasus: Attributed Clickstream Path-to-Conversion Analysis
Sebuah perusahaan e-commerce memiliki tabel clickstream sebesar 200 juta baris:
```sql
user_touchpoints (
    touchpoint_id UUID,
    user_id VARCHAR(64),
    utm_source VARCHAR(64),
    utm_medium VARCHAR(64),
    action_type VARCHAR(32), -- 'CLICK', 'VIEW', 'PURCHASE'
    purchase_value NUMERIC(12,2),
    timestamp TIMESTAMPTZ
)
```

**Tantangan Arsitektur**:
1. Buat query analytical reporting tanpa bantuan platform eksternal (Spark/Snowflake) murni di PostgreSQL untuk menghitung **First-Touch Attribution** dan **Last-Touch Attribution** untuk setiap transaksi purchase:
   - Ambil seluruh clickstream yang terjadi maksimal 14 hari sebelum event `PURCHASE`.
   - Abaikan seluruh interaksi yang terjadi setelah event `PURCHASE` tersebut.
2. Query harus dirancang sedemikian rupa agar CBO PostgreSQL mengeksekusi rencana tanpa memicu disk temp write (`work_mem` dibatasi hanya 64MB).
3. Anda harus menentukan strategi indexing dan skema partisi apa yang harus diterapkan pada tabel tersebut agar query selesai dalam waktu $< 5$ detik untuk rentang windowing transaksi 1 bulan penuh. Sertakan DDL Index dan DDL Partitioning yang Anda usulkan.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Level (5 Soal)
1. **Mengapa modifikasi data via query `UPDATE` pada PostgreSQL secara internal menghasilkan overhead yang mirip dengan `DELETE` dan `INSERT`?**
   - A. Karena PostgreSQL langsung menulis ulang seluruh file fisik tabel di storage.
   - B. Karena mekanisme MVCC membuat tuple baru dengan `t_xmin` baru dan menandai tuple lama dengan `t_xmax`, meninggalkan tuple lama sebagai dead tuple.
   - C. Karena relational database tidak mendukung update memory secara in-place.
   - D. Karena transaksi secara otomatis dibatalkan jika field diubah secara langsung.

2. **Apa dampak performa jika Anda menulis `WHERE EXTRACT(YEAR FROM created_at) = 2024` dibandingkan `WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'`?**
   - A. Tidak ada perbedaan karena compiler SQL modern otomatis mengubah format fungsinya.
   - B. Fungsi `EXTRACT` membuat query menjadi non-SARGable, memaksa database melakukan Sequential Scan ke seluruh baris tabel dan membatalkan penggunaan B-Tree Index biasa.
   - C. Pendekatan range comparison membutuhkan memori CPU lebih besar dibandingkan fungsi integer.
   - D. `EXTRACT` mempercepat scan karena integer indexing lebih ringan dibanding timestamp.

3. **Apa arti istilah `shared hit` pada metrik pembacaan `EXPLAIN (ANALYZE, BUFFERS)`?**
   - A. Halaman data dibaca langsung dari partisi backup.
   - B. Halaman data telah tersedia di shared buffer pool RAM PostgreSQL tanpa memerlukan pemanggilan system call disk read.
   - C. Halaman data di-share ke thread transaksi lain.
   - D. Terjadi collision pada hashing cache database.

4. **Klausa Frame mana yang merupakan default jika Anda hanya menulis `OVER (ORDER BY timestamp)` pada window function PostgreSQL?**
   - A. `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`
   - B. `ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING`
   - C. `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`
   - D. `ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING`

5. **Kapan tipe indeks BRIN (Block Range Index) paling tepat digunakan dibanding B-Tree?**
   - A. Pada tabel yang sering mengalami operasi acak `UPDATE` dan `DELETE`.
   - B. Pada tabel berukuran raksasa di mana data dimasukkan secara terurut alami secara fisik di disk (append-only), seperti log atau timeseries.
   - C. Pada tabel kecil dengan kardinalitas kolom sangat bervariasi.
   - D. Ketika kolom yang diindeks berupa tipe data teks dokumen panjang.

### 15.2 Intermediate Level (5 Soal)
6. **Perhatikan skenario berikut:**
   Query menggunakan `Hash Join` tumpah ke disk: `Batches: 16 Memory Usage: 4096kB`. Manakah tindakan korektif arsitektural yang paling aman dan efektif?
   - A. Mengubah join menjadi `CROSS JOIN`.
   - B. Meningkatkan alokasi `work_mem` secara global pada file konfigurasi `postgresql.conf` menjadi 10GB untuk semua user.
   - C. Menaikkan `work_mem` hanya di scope session query pelaporan tersebut berjalan, atau mengoptimalkan join condition agar dataset inner table lebih terfilter.
   - D. Menghapus index pada join key.

7. **Apa perbedaan struktural utama antara `B-Tree Composite Index (A, B)` dengan `B-Tree Index A INCLUDE (B)`?**
   - A. Composite Index menyimpan A dan B pada level internal nodes dan leaf nodes pohon B-Tree; sedangkan `INCLUDE` hanya menyimpan kolom B di leaf nodes, menghemat ruang internal node dan mendukung Index-Only Scan untuk B tanpa bisa memfilter predikat `WHERE B = ...` secara efisien.
   - B. `INCLUDE` index hanya mendukung tipe data integer.
   - C. Composite index tidak dapat digunakan untuk sorting kolom A.
   - D. Tidak ada perbedaan struktural; klausa `INCLUDE` hanyalah alias sintaksis untuk composite index.

8. **Dalam Recursive CTE, apa peran dari klausa `UNION ALL` versus `UNION` dalam hal kinerja eksekusi engine?**
   - A. `UNION` lebih cepat karena langsung menghentikan pembacaan baris ganda.
   - B. `UNION ALL` secara instan mengalirkan tuple ke buffer penampung tanpa operasi deduplikasi hashing/sorting, sedangkan `UNION` memaksakan deduplikasi mahal di setiap iterasi rekursif.
   - C. `UNION ALL` membatasi kedalaman rekursi maksimal 100 level secara otomatis.
   - D. Keduanya memiliki kompleksitas algoritma yang identik di dalam query tree rewriter.

9. **Ketika PostgreSQL mengeksekusi `Merge Join`, kondisi prasyarat apa yang harus dipenuhi oleh kedua child nodes?**
   - A. Kedua child node harus memiliki jumlah record yang sama persis.
   - B. Data stream dari kedua tabel harus sudah terurut (*ordered*) berdasarkan join key yang dievaluasi.
   - C. Salah satu tabel harus berukuran kurang dari `work_mem`.
   - D. Kedua tabel harus berada dalam skema partisi yang sama.

10. **Apa dampak utama dari fenomena *Write Amplification* akibat indexing berlebih pada pipeline data analitik?**
    - A. Ukuran RAM server database otomatis tereduksi secara permanen.
    - B. Setiap operasi `INSERT` atau `UPDATE` membutuhkan penulisan I/O tambahan ke struktur leaf node B-Tree dari masing-masing index, meningkatkan latensi penulisan dan beban I/O disk.
    - C. Optimizer akan menolak menjalankan instruksi `VACUUM`.
    - D. Database engine secara otomatis mendowngrade isolation level menjadi Read Uncommitted.

### 15.3 Production Scenario Analysis (3 Soal Kasus)
11. **Skenario Kasus A:**
    Sebuah query dashboard analitik keuangan memuat kueri berikut:
    ```sql
    SELECT merchant_id, COUNT(*) 
    FROM settlements 
    WHERE settlement_date >= '2023-01-01' 
    GROUP BY merchant_id;
    ```
    Engine PostgreSQL memilih melakukan `Seq Scan` pada tabel `settlements` (berukuran 150 GB) alih-alih menggunakan index `idx_settlements_date` yang sudah ada pada kolom `settlement_date`. Hasil `ANALYZE` menunjukkan bahwa transaksi dari rentang tanggal tersebut mencakup 85% dari total seluruh baris tabel. Mengapa optimizer menolak menggunakan index dan memilih `Seq Scan`? Apakah keputusan engine ini benar?
    - *Analisis dan Pilih Jawaban:*
      - A. Optimizer salah; ini adalah bug pada PostgreSQL CBO yang harus diatasi dengan mematikan `enable_seqscan = off`.
      - B. Optimizer benar; membaca 85% data tabel via Index Scan akan memicu random page I/O masif (bolak-balik antara index page dan heap page), yang secara signifikan jauh lebih lambat daripada sequential scan linear terhadap file fisik tabel.
      - C. Index mengalami fragmentasi, solusinya adalah menjalankan perintah `REINDEX`.
      - D. Optimizer menolak index karena kolom target tidak dibungkus dengan klausul agregasi `SUM()`.

12. **Skenario Kasus B:**
    Pipeline analitik Anda menjalankan query batch rekonsiliasi malam hari. Anda mengamati log engine dan menemukan error: `canceling statement due to conflict with recovery`. Apa penyebab arsitektural dari kegagalan sistem ini pada lingkungan enterprise, dan bagaimana solusi permanennya?
    - *Analisis dan Pilih Jawaban:*
      - A. Master node kehabisan disk space untuk memproses instruksi query write.
      - B. Query dijalankan pada Read Replica, dan proses replay WAL log dari master node harus menghapus tuple/buffer data di replica yang sedang dibaca oleh long-running query Anda untuk menjaga konsistensi state. Solusinya adalah menaikkan konfigurasi `max_standby_archive_delay` / `max_standby_streaming_delay` atau mengaktifkan `hot_standby_feedback = on`.
      - C. Koneksi PgBouncer terputus akibat network timeout. Solusinya mengubah pool mode menjadi session.
      - D. Server replica mengalami corrupt memory; solusinya mereplikasi ulang dari backup snapshot.

13. **Skenario Kasus C:**
    Diberikan eksekusi kueri dengan metrik berikut:
    ```text
    Bitmap Heap Scan on log_events (cost=1420.50..89201.22 rows=85000)
      Recheck Cond: (severity = 'CRITICAL')
      Rows Removed by Index Recheck: 421000
      Buffers: shared hit=4210 read=18290
      -> Bitmap Index Scan on idx_log_severity (cost=0.00..1399.25 rows=506100)
    ```
    Mengapa muncul baris `Rows Removed by Index Recheck`, dan optimasi arsitektural apa yang harus diambil untuk mempercepat eksekusi kueri ini secara signifikan?
    - *Analisis dan Pilih Jawaban:*
      - A. Indeks rusak; solusi satu-satunya adalah menghapus index dan menggunakan sequential scan.
      - B. `work_mem` tidak cukup untuk menampung bitmap pointer per baris di memory, sehingga PostgreSQL mengubah representasi bitmap menjadi lossy (berbasis page, bukan tuple ID). Mesin harus membaca seluruh page dan memfilter ulang baris secara manual. Solusinya adalah menaikkan parameter `work_mem` untuk query tersebut.
      - C. Statistik data salah total; solusinya adalah menurunkan alokasi shared memory engine.
      - D. Kolom severity memiliki kardinalitas terlalu tinggi untuk dijadikan Bitmap Scan.

---

## 16. Summary

1. **Storage Internals Drive Analytics**: Memahami PostgreSQL *Slotted-Page Architecture* (8 KB per page) dan lifecycle tuple MVCC (`t_xmin`, `t_xmax`) sangat fundamental. Performa query analitik bukan sekadar urusan sintaks SQL, melainkan bagaimana kueri meminimalkan transfer blok memori (*Shared Buffers*) dari storage ke CPU cache.
2. **Deterministic Optimizer Profiling**: Pembacaan hasil eksekusi kueri wajib berlandaskan pada metriks faktual via `EXPLAIN (ANALYZE, BUFFERS)`. Identifikasi tipe join (*Nested Loop* untuk subset sempit, *Hash Join* untuk dataset besar acak, *Merge Join* untuk dataset terurut) dan hindari terjadinya *Memory-to-Disk spills* dengan penyetelan alokasi `work_mem` secara proporsional.
3. **Pola Analitik Tingkat Lanjut**: Implementasi eksplisit *Sliding Window Frame* (`ROWS BETWEEN ...`) mengeliminasi redundansi komputasi bawaan *RANGE*. Permasalahan sekuensial kompleks (seperti atribusi, identifikasi anomali, sessionization, deteksi hierarki) dapat diselesaikan di dalam *storage engine layer* menggunakan integrasi pola *Gaps and Islands* serta *Recursive Common Table Expressions (CTE)*.
4. **Skalabilitas Arsitektural**: Pada volume data analitik skala enterprise ($> 10^7$ baris), indeks B-Tree tunggal konvensional tidak lagi memadai. Desain harus bertransisi ke kombinasi *Declarative Range/List Partitioning*, *Covering Indexes (`INCLUDE`)* untuk mencapai zero-heap-access *Index Only Scan*, serta isolasi beban kerja menggunakan dedicated *Read Replicas* yang diproteksi oleh *Connection Pooler*.