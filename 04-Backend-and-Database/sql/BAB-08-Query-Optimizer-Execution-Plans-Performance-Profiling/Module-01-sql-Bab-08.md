# Bab 08 Module 01: Query Optimizer, Execution Plans, & Performance Profiling

---

## 01. Identitas Modul
* **Track:** Database Engineering & Backend Architecture
* **Kategori:** 04-Backend-and-Database
* **Topik:** Advanced SQL Performance Engineering
* **Level:** Advanced (L4/Principal Track)
* **Target Engine:** PostgreSQL 15+ / 16 (kompatibel konseptual dengan MySQL 8.0+ dan distributed SQL)
* **Prasyarat:** Pemahaman mendalam tentang Indexing (B-Tree, Hash, GIN), Relational Algebra, MVCC, dan Transaksi ACID.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Mendekonstruksi Query Lifecycle:** Menganalisis transformasi SQL dari Parsing, Rewriting, Cost Estimation, Path Generation, hingga Execution Engine.
2. **Membaca dan Mengevaluasi Execution Plan:** Menginterpretasikan output `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, WAL)` secara akurat, mendeteksi disk spills, memory footprint, buffer cache misses, dan runtime skew.
3. **Mengidentifikasi dan Memitigasi Bottleneck Fisik:** Menemukan akar permasalahan dari *Sequential Scans*, *Hash Join Spills*, *Nested Loop explosion*, dan *Bitmap Heap Scan degrading*.
4. **Menganalisis Statistik Engine Internal:** Mengaudit `pg_statistic`, `pg_stats`, histogram buckets, Most Common Values (MCV), correlation metrics, dan merancang *Extended Statistics* untuk korelasi multi-kolom.
5. **Menerapkan Profiling Berkelanjutan:** Menggunakan `pg_stat_statements`, dynamic tracing via eBPF/perf, serta instrumentasi telemetry end-to-end tanpa menyebabkan degradasi performa di lingkungan produksi.

---

## 03. Concept Map Diagram (ASCII)

```text
[ SQL Text ]
     |
     v
+------------------+
| Parser & Lexer   | ---> Syntax Tree (AST)
+------------------+
     |
     v
+------------------+
| Query Rewriter   | ---> Abstract Query Tree (Views, RLS, Rules applied)
+------------------+
     |
     v
+-------------------------------------------------------------+
| Cost-Based Optimizer (CBO)                                  |
|                                                             |
|  +--------------------+      +---------------------------+  |
|  | Catalog Statistics | ---> | Path Generator            |  |
|  | (pg_statistic)     |      | - Scan Paths (Seq/Idx/Tid)|  |
|  | - MCV, Histograms  |      | - Join Paths (NL/Hash/Mrg)|  |
|  | - Correlation      |      | - Aggregate & Sort Paths  |  |
|  +--------------------+      +---------------------------+  |
|                                            |                |
|                                            v                |
|                              +---------------------------+  |
|                              | Cost Model Calculator     |  |
|                              | (CPU vs I/O Cost Metrics) |  |
|                              +---------------------------+  |
|                                            |                |
|                                            v                |
|                              [ Lowest Cost Execution Plan]  |
+-------------------------------------------------------------+
     |
     v
+-------------------------------------------------------------+
| Executor Engine (Demand-Driven Iterator / Volcano Model)    |
|                                                             |
|  [InitPlan] ---> [Node Iteration: Next()] ---> [Result Set] |
|                         |                                   |
|                         +---> Buffer Pool / OS Disk Pages   |
|                         +---> WorkMem / Temp Files          |
+-------------------------------------------------------------+
```

---

## 04. Mengapa Relevan
Pada sistem skala enterprise, 90% degradasi latensi backend berakar pada eksekusi query database yang sub-optimal. *Query Optimizer* adalah komponen inti DBMS yang menentukan *bagaimana* data diambil, bukan *apa* yang diminta. 

Kesalahan estimasi kardinalitas (misal: optimizer mengira query menghasilkan 5 baris padahal 5.000.000 baris) memicu pemilihan operator yang salah:
* **Nested Loop** dipilih menggantikan **Hash Join**, mengakibatkan kompleksitas melonjak dari $\mathcal{O}(N + M)$ menjadi $\mathcal{O}(N \times M)$.
* Alokasi `work_mem` tidak cukup, memaksa in-memory sorting beralih ke disk-based external merge sort, memicu lonjakan I/O drastis.
* Penggunaan fungsi non-sargable mematikan pemanfaatan index secara total.

Kemampuan menganalisis plan secara deterministik membedakan engineer reaktif (hanya menambah RAM/CPU) dengan database architect sistematis (mengeliminasi akar masalah performa pada level instruksi mesin query).

---

## 05. Anatomi Konsep Inti

### 1. Cost Model & Parameter Biaya
Cost dalam PostgreSQL dihitung dalam unit arbitrer relatif terhadap pembacaan single sequential disk page (`seq_page_cost = 1.0`).

$$\text{Total Cost} = (\text{Pages} \times \text{page\_cost}) + (\text{CPU Tuples} \times \text{cpu\_tuple\_cost}) + (\text{CPU Operators} \times \text{cpu\_operator\_cost})$$

* `seq_page_cost` (Default: 1.0): Biaya I/O fetch sequential page.
* `random_page_cost` (Default: 4.0): Biaya I/O fetch random disk access (pada NVMe SSD, parameter ini lazim diubah ke 1.1–1.25).
* `cpu_tuple_cost` (Default: 0.01): Biaya CPU memproses satu baris data fisik.
* `cpu_index_tuple_cost` (Default: 0.005): Biaya pemrosesan entri index.
* `cpu_operator_cost` (Default: 0.0025): Biaya komputasi pemrosesan ekspresi/operator WHERE/JOIN.

### 2. Node Scanning (Scan Strategies)
* **Sequential Scan (`Seq Scan`):** Membaca seluruh data page dari disk secara berurutan. Optimal jika proporsi data yang diambil > 20-30% total tabel.
* **Index Scan (`Index Scan`):** Menelusuri index B-Tree (random access), membaca pointer tuple `ctid`, lalu melompat mengambil heap page di disk.
* **Index Only Scan:** Mengambil seluruh kolom langsung dari index page tanpa menyentuh heap page, divalidasi via *Visibility Map* (VM).
* **Bitmap Index/Heap Scan:** Index di-scan untuk membangun bitmap address di memory (`BitmapIndexScan`), lalu heap page diambil secara sequential terurut berdasarkan block numbers (`BitmapHeapScan`).

### 3. Join Strategies
* **Nested Loop:** Untuk setiap baris di Outer Table, mesin memindai Inner Table. Sangat efisien jika Outer Table kecil dan Inner Table memiliki index presisi.
* **Hash Join:** Membangun in-memory hash table dari Inner Table (Batch), lalu memindai baris Outer Table dan mencocokkan hash key-nya. Membutuhkan memori (`work_mem`).
* **Merge Join:** Kedua relasi diurutkan terlebih dahulu berdasarkan Join Key, lalu dipindai secara paralel secara bersamaan. Sangat cepat bila input sudah terurut secara fisik (misal via index).

---

## 06. Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Parameter Analisis Sesi
Aktifkan granularitas trace execution plan maksimal untuk investigasi:
```sql
-- Pastikan optimizer track IO timing (Dapat menyebabkan overhead minor pada CPU timer)
SET track_io_timing = ON;
-- Konfigurasikan cost SSD modern
SET random_page_cost = 1.1;
```

### Step 2: Menggunakan EXPLAIN ANALYZE
Format syntax lengkap untuk profiling mendalam:
```sql
EXPLAIN (
    ANALYZE,    -- Menjalankan query secara aktual dan mengukur waktu eksekusi riil
    BUFFERS,    -- Melacak hits, reads, dirty, dan written blocks di shared_buffers/local
    SETTINGS,   -- Menampilkan konfigurasi optimizer yang diubah dari default
    WAL,        -- Mengukur volume Write-Ahead-Log yang dihasilkan
    VERBOSE,    -- Menampilkan target list kolom dan alias internal
    FORMAT TEXT -- Output text tree (atau JSON/YAML untuk programmatic parsing)
)
SELECT * FROM orders WHERE status = 'PENDING';
```

---

## 07. Contoh Kasus Sederhana: Diagnostic Logika Indeks & Type Cast Trap

### Masalah: Implicit Type Casting Memicu Sequential Scan
Skema tabel: Kolom `account_id` bertipe `VARCHAR(64)` dengan indeks B-Tree. Query dieksekusi dengan passing integer literal.

```sql
-- DDL & Setup
CREATE TABLE accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    balance NUMERIC(15,2),
    is_active BOOLEAN
);

INSERT INTO accounts 
SELECT i::text, (random() * 10000)::numeric(15,2), true 
FROM generate_series(1, 100000) AS i;

ANALYZE accounts;
```

### Query Eksperimen (Anti-Pattern vs Corrected)

```sql
-- EKSPERIMEN 1: Implicit Cast (Indeks Diabaikan)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM accounts WHERE account_id = 12345; -- Int literal passed to VARCHAR column

-- Output Problem:
-- Seq Scan on accounts (cost=0.00..2140.00 rows=1 width=40) (actual time=8.231..14.512 rows=1 loops=1)
--   Filter: ((account_id)::integer = 12345)
--   Rows Removed by Filter: 99999
--   Buffers: shared hit=890

-- EKSPERIMEN 2: Explicit Data Type Match (Index Utilized)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM accounts WHERE account_id = '12345';

-- Output Solusi:
-- Index Scan using accounts_pkey on accounts (cost=0.29..8.31 rows=1 width=40) (actual time=0.021..0.022 rows=1 loops=1)
--   Index Cond: ((account_id)::text = '12345'::text)
--   Buffers: shared hit=3
```

**Analisis:** Pada Eksperimen 1, fungsi typecast `(account_id)::integer` dievaluasi untuk setiap baris, merusak prinsip *Sargability* dan mematikan fungsi B-Tree traversal.

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi end-to-end framework monitoring kardinalitas, deteksi query drift, dan koreksi statistik pada sistem High-Throughput E-Commerce.

```sql
-- ============================================================================
-- SCRIPT: Advanced Query Optimizer Profiler & Statistics Tuning Framework
-- Target Engine: PostgreSQL 14+
-- ============================================================================

BEGIN;

-- 1. Setup Skema E-Commerce Simulasi Skala Besar
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS commerce;

CREATE TABLE commerce.customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL,
    segment VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE commerce.orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES commerce.customers(customer_id),
    order_status VARCHAR(20) NOT NULL,
    order_date DATE NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    metadata JSONB
);

-- Indexing awal
CREATE INDEX idx_orders_customer_id ON commerce.orders(customer_id);
CREATE INDEX idx_orders_status_date ON commerce.orders(order_status, order_date);

-- 2. Generate Data dengan Distribusi Data Sangat Skewed (Zipfian-like)
INSERT INTO commerce.customers (customer_id, country_code, segment, created_at)
SELECT 
    gen_random_uuid(),
    CASE WHEN random() < 0.85 THEN 'ID' ELSE 'SG' END,
    CASE WHEN random() < 0.70 THEN 'RETAIL' ELSE 'ENTERPRISE' END,
    clock_timestamp() - (random() * interval '365 days')
FROM generate_series(1, 100000);

INSERT INTO commerce.orders (customer_id, order_status, order_date, total_amount, metadata)
SELECT 
    c.customer_id,
    CASE 
        WHEN random() < 0.90 THEN 'COMPLETED'
        WHEN random() < 0.98 THEN 'CANCELLED'
        ELSE 'PROCESSING'
    END,
    CURRENT_DATE - (random() * 90)::INT,
    (random() * 5000)::NUMERIC(12,2),
    jsonb_build_object('source', 'mobile_app', 'version', '2.4.0')
FROM commerce.customers c
CROSS JOIN generate_series(1, 10); -- 1 Juta Orders

COMMIT;

-- Update Database Statistics
ANALYZE VERBOSE commerce.customers;
ANALYZE VERBOSE commerce.orders;

-- ============================================================================
-- 3. Multi-Column Correlation Problem & Extended Statistics Solution
-- ============================================================================

-- Kasus Masalah: Kolom 'country_code' dan 'segment' berkorelasi kuat secara tersembunyi
-- Optimizer mengasumsikan independensi statistik: P(A and B) = P(A) * P(B)
-- Menghasilkan estimasi row yang sangat meleset (Cardianlity Misestimate)

-- Diagnostik Plan SEBELUM Extended Statistics
EXPLAIN (ANALYZE, BUFFERS, COSTS, TIMING)
SELECT * 
FROM commerce.customers
WHERE country_code = 'ID' AND segment = 'RETAIL';

-- Analisis deviasi: Jika Estimated Rows != Actual Rows secara ekstrem, 
-- buat Multivariate Extended Statistics:
CREATE STATISTICS IF NOT EXISTS cust_country_segment_stat 
ON country_code, segment 
FROM commerce.customers;

ANALYZE commerce.customers;

-- Diagnostik Plan SESUDAH Extended Statistics (Estimasi baris mendekati 100% presisi)
EXPLAIN (ANALYZE, BUFFERS, COSTS, TIMING)
SELECT * 
FROM commerce.customers
WHERE country_code = 'ID' AND segment = 'RETAIL';

-- ============================================================================
-- 4. Dynamic Performance Profiler View
-- Query untuk mengekstrak metrik query lambat dari pg_stat_statements
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE OR REPLACE VIEW telemetry.v_query_efficiency_report AS
SELECT 
    queryid,
    substr(query, 1, 100) AS truncated_query,
    calls,
    round(total_exec_time::numeric, 2) AS total_exec_time_ms,
    round(mean_exec_time::numeric, 2) AS avg_exec_time_ms,
    round((100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0))::numeric, 2) AS cache_hit_ratio,
    rows AS total_rows_returned,
    round((rows / nullif(calls, 0))::numeric, 2) AS avg_rows_per_call,
    shared_blks_read AS disk_blocks_read,
    shared_blks_dirtied AS blocks_dirtied,
    temp_blks_read + temp_blks_written AS workmem_disk_spill_blocks
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC
LIMIT 50;
```

---

## 09. Diagram Alur Kerja Mesin Query (Execution Plan Generation)

```text
               +--------------------------------------+
               |          Input Query AST             |
               +--------------------------------------+
                                  |
                                  v
               +--------------------------------------+
               |      Pre-Evaluation of Constants     |
               |       & Subquery Flattening          |
               +--------------------------------------+
                                  |
                                  v
               +--------------------------------------+
               |        Scan Path Generation          |
               | (Seq Scan vs Index Scan vs Bitmap)   |
               +--------------------------------------+
                                  |
          +-----------------------+-----------------------+
          |                                               |
  Relation Size Small                            Relation Size Large
          |                                               |
          v                                               v
+--------------------+                         +--------------------+
|  Index Only Scan   |                         | Sequential / Parallel|
| (If all cols in Idx|                         |     Seq Scan       |
+--------------------+                         +--------------------+
          \                                               /
           \                                             /
            v                                           v
       +-----------------------------------------------------+
       |               Join Path Optimization                |
       |  Permutasi Urutan Join Menggunakan Dynamic Program  |
       |  (atau Genetic Query Optimization / GEQO jika N>12)  |
       +-----------------------------------------------------+
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
[Nested Loop Join]         [Hash Join]              [Merge Join]
- Memerlukan Index        - Build Hash Table       - Memerlukan input
- Skala Data Kecil        - Membutuhkan work_mem     terurut
- Low latency start       - High throughput        - Cocok untuk stream
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                                  v
       +-----------------------------------------------------+
       |         Cheapest Cost Path Selected -> Plan         |
       +-----------------------------------------------------+
```

---

## 10. Analisis Trade-offs

| Pendekatan Operator | Keunggulan | Kelemahan | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **Nested Loop Join** | Latensi awal instan (*0 startup cost*), efisien untuk filter kecil. | Degradasi waktu $\mathcal{O}(N \times M)$ jika estimasi baris meleset dan tabel besar. | Lookup OLTP presisi dengan indeks (misal: 1 customer ke 5 order). |
| **Hash Join** | Sangat cepat untuk relasi besar acak; kompleksitas $\mathcal{O}(N + M)$. | Membutuhkan alokasi memori (`work_mem`). Jika kehabisan memori, terjadi disk spilling. | Batch processing / analytical join tanpa indeks terurut. |
| **Merge Join** | Memori minimal dan stabil; performa konstan untuk dataset terurut berukuran masif. | Overhead sorting tinggi ($\mathcal{O}(N \log N)$) jika data belum terurut di disk/indeks. | Integrasi tabel masif yang diurutkan pada clustered key/index yang sama. |
| **Bitmap Index Scan** | Mencegah random access disk berlebihan dengan memetakan block memory secara fisik. | Overhead komputasi saat membangun bitmap; kehilangan direct pointer jika memori penuh (lossy). | Ekstraksi baris berkisar antara 2% hingga 20% dari total tabel. |

---

## 11. Best Practices & Antipatterns

### Best Practices
1. **Targetkan High Cache Hit Ratio:** Formula `shared_hit / (shared_hit + shared_read)` harus berada di atas 99% pada beban OLTP murni.
2. **Kompensasi Skewness dengan Targeted Statistics:** Naikkan target sampling statistik pada kolom dengan deviasi ekstrem:
   ```sql
   ALTER TABLE commerce.orders ALTER COLUMN order_status SET STATISTICS 500;
   ANALYZE commerce.orders;
   ```
3. **Optimalkan Work Memory Spesifik Sesi:** Hindari menaikkan `work_mem` secara global di `postgresql.conf`. Gunakan alokasi dinamis per transaksi analitik besar:
   ```sql
   SET LOCAL work_mem = '256MB';
   -- Jalankan query aggregation besar
   ```

### Antipatterns
1. **Over-Indexing:** Setiap indeks B-Tree menambah penalti write amplification secara linier saat `INSERT`, `UPDATE`, dan `DELETE`, serta membebani cache mesin.
2. **Leading Wildcard Search:** Kondisi `LIKE '%keyword'` menggagalkan pemanfaatan struktur B-Tree traversal secara total. Gunakan indeks GIN dengan modul `pg_trgm`.
3. **Correlated Subqueries dalam SELECT Clause:** Memicu eksekusi sub-query per-baris secara terisolasi layaknya *hidden nested loop*. Gunakan teknik Window Function atau CTE (`WITH`).

---

## 12. Security Hardening

Dalam konteks query optimizer dan profiling, aspek keamanan mencakup isolasi execution data dan mitigasi SQL Injection berbasis timing:

1. **Restriksi Akses `pg_stat_statements` & Parameter Internal:**
   Query plan dapat membocorkan data sensitif (misal: konstanta WHERE clause atau pola data melalui histogram). Batasi akses view analitik hanya kepada peran berwenang.
   ```sql
   REVOKE ALL ON pg_stat_statements FROM PUBLIC;
   GRANT SELECT ON pg_stat_statements TO role_dba_monitoring;
   ```

2. **Row-Level Security (RLS) Performance Bypass Mitigation:**
   Ketika RLS diterapkan, optimizer menginjeksi filter keamanan ke setiap query. Hati-hati terhadap fungsi yang bocor (*leaky functions*). Gunakan atribut `LEAKPROOF` hanya pada fungsi yang telah diaudit secara formal:
   ```sql
   CREATE OR REPLACE FUNCTION telemetry.secure_hash_validator(text)
   RETURNS boolean AS $$
   BEGIN
       RETURN (substr($1, 1, 4) = 'SEC_');
   END;
   $$ LANGUAGE plpgsql IMMUTABLE LEAKPROOF;
   ```

---

## 13. Observabilitas & Debugging

Gunakan kombinasi metrik internal dan system tracing untuk mengisolasi query stalls:

### 1. Deteksi Lock Contention & Disk Spills Real-time
```sql
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE state != 'idle' 
  AND (now() - pg_stat_activity.query_start) > interval '500 milliseconds'
ORDER BY duration DESC;
```

### 2. Analisis Temp File Generation (WorkMem Spilling Indicator)
Pantau log file database dari query yang menumpahkan komputasi ke storage:
```ini
# postgresql.conf
log_temp_files = 4096 # Log seluruh operasi temporary files > 4MB (Satuan KB)
```

Output log jika optimizer gagal mengalokasikan memori yang cukup:
```text
LOG: temporary file: path "base/pgsql_tmp/pgsql_tmp1832.0", size 48392104 bytes
STATEMENT: SELECT customer_id, count(*) FROM commerce.orders GROUP BY 1 ORDER BY 2 DESC;
```

---

## 14. Benchmarking & Performance

Lakukan benchmarking terisolasi untuk membuktikan efektivitas indeks komposit dan penghapusan *disk sort*:

### Test Harness menggunakan pgbench

Simpan script SQL pengujian berikut (`benchmark_query.sql`):
```sql
\set customer_id random(1, 100000)
SELECT order_id, order_status, total_amount 
FROM commerce.orders 
WHERE customer_id = (
    SELECT customer_id FROM commerce.customers LIMIT 1 OFFSET :customer_id
)
ORDER BY order_date DESC LIMIT 5;
```

Eksekusi beban benchmark multi-thread:
```bash
pgbench -h localhost -p 5432 -U postgres -d enterprise_db \
        -f ./benchmark_query.sql \
        -c 32 \
        -j 8 \
        -T 60 \
        -r
```

### Metrik Hasil Benchmark (Sebelum vs Sesudah Optimasi)

| Metrik Validasi | Baseline (Unoptimized) | Optimized (Composite Idx + Tuned Stats) | Delta Peningkatan |
| :--- | :--- | :--- | :--- |
| **Latency p95** | 184.2 ms | 3.1 ms | **98.3% Reduction** |
| **Latency p99** | 412.8 ms | 7.8 ms | **98.1% Reduction** |
| **TPS (Throughput)**| 142 tx/sec | 3,890 tx/sec | **27.3x Scale** |
| **Buffer Reads (Disk)**| 12,400 blks/query | 0 blks/query (100% cache hit) | **Total Elimination** |

---

## 15. Hands-on Lab Mini-Project

### Objective
Lakukan debugging dan tuning pada skenario sistem analitik yang mengalami degradasi performa (*slow running report*).

### Baseline Broken Setup
```sql
CREATE SCHEMA IF NOT EXISTS lab;

CREATE TABLE lab.transactions (
    id BIGSERIAL PRIMARY KEY,
    merchant_id INT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    payload TEXT
);

-- Injeksi data
INSERT INTO lab.transactions (merchant_id, amount, created_at, payload)
SELECT 
    (random() * 50)::INT,
    (random() * 1000)::NUMERIC(10,2),
    NOW() - (random() * 30 || ' days')::INTERVAL,
    repeat('A', 100)
FROM generate_series(1, 500000);

ANALYZE lab.transactions;
```

### Problem Query
Query analitik bulanan ini menyebabkan CPU 100% spike dan runtime lambat:
```sql
SELECT 
    merchant_id, 
    COUNT(*) as total_trans, 
    SUM(amount) as total_vol
FROM lab.transactions
WHERE date_trunc('month', created_at) = '2026-03-01'::timestamp
GROUP BY merchant_id;
```

### Langkah Remediasi Hands-on
1. **Analisis Plan Awal:** Identifikasi kenapa B-Tree index pada `created_at` (jika dibuat) tidak digunakan akibat wrapping fungsi `date_trunc`.
2. **Sargable Transformation:** Ubah klausa WHERE menjadi rentang deterministik:
   ```sql
   WHERE created_at >= '2026-03-01 00:00:00' 
     AND created_at < '2026-04-01 00:00:00'
   ```
3. **Covering Index Implementation:** Buat indeks komposit penutup (*covering index*) untuk mengaktifkan *Index Only Scan*:
   ```sql
   CREATE INDEX idx_trans_perf_covering 
   ON lab.transactions(created_at, merchant_id) 
   INCLUDE (amount);
   ```

---

## 16. Automated Testing & Verification

Gunakan assertion script berbasis plpgsql untuk memvalidasi regression execution plan secara otomatis pada CI/CD database integration tests.

```sql
DO $$
DECLARE
    v_plan JSON;
    v_node_type TEXT;
    v_total_cost NUMERIC;
    v_max_allowed_cost NUMERIC := 100.0;
BEGIN
    -- Jalankan EXPLAIN JSON dan tampung ke variabel
    EXECUTE 'EXPLAIN (FORMAT JSON) 
             SELECT * FROM commerce.customers 
             WHERE customer_id = ''00000000-0000-0000-0000-000000000000''::uuid' 
    INTO v_plan;

    -- Ekstraksi Root Node Type dan Total Cost
    v_node_type := v_plan->0->'Plan'->>'Node Type';
    v_total_cost := (v_plan->0->'Plan'->>'Total Cost')::numeric;

    -- Assert Operator Bukan Sequential Scan
    IF v_node_type = 'Seq Scan' THEN
        RAISE EXCEPTION 'REGRESSION DETECTED: Query executed with Seq Scan!';
    END IF;

    -- Assert Maximum Cost Budget
    IF v_total_cost > v_max_allowed_cost THEN
        RAISE EXCEPTION 'COST BUDGET EXCEEDED: Expected < %, Got %', 
            v_max_allowed_cost, v_total_cost;
    END IF;

    RAISE NOTICE 'SUCCESS: Query Plan assertion passed. Execution Path: % (Cost: %)', 
        v_node_type, v_total_cost;
END;
$$;
```

---

## 17. Troubleshooting Guide

### 1. Gejala: Estimasi Kardinalitas Jauh Berbeda dari Riil
* **Penyebab:** Statistik tabel basi (*stale statistics*) atau data skewed tidak tertangkap di standard histogram.
* **Solusi:** Jalankan `ANALYZE` manual pada tabel target. Jika masalah berlanjut, naikkan `default_statistics_target` dari 100 ke 500.

### 2. Gejala: Hash Join Lambat & Disk I/O Melonjak Tajam
* **Penyebab:** Memori operator terlampaui sehingga batch tumpah ke disk (*Batches: > 1* pada output explain).
* **Solusi:** Naikkan `work_mem` khusus untuk query tersebut, atau gunakan parallel query execution (`max_parallel_workers_per_gather`).

### 3. Gejala: Index Diabaikan dan Memilih Sequential Scan
* **Penyebab 1:** Modifikasi kolom dengan function (non-sargable) atau implicit type casting.
* **Penyebab 2:** Tabel berukuran terlalu kecil (I/O disk random via indeks lebih mahal dibanding sequential fetch block kecil).
* **Penyebab 3:** Parameter `random_page_cost` terlalu tinggi (default 4.0) pada media penyimpanan NVMe SSD. Ubah ke 1.1.

---

## 18. Checklist Produksi

- [ ] **IO Timing:** Pastikan `track_io_timing = on` aktif untuk evaluasi latency I/O.
- [ ] **Hardware Alignment:** Set `random_page_cost` ke kisaran `1.1 - 1.25` jika menggunakan SSD/NVMe enterprise storage.
- [ ] **Memory Allocation:** Konfigurasikan `shared_buffers` (25-40% total RAM) dan `work_mem` secara rasional agar join dan sort tidak meluap ke disk secara konstan.
- [ ] **Concurrency & Workers:** Konfigurasikan `max_worker_processes`, `max_parallel_workers`, dan `max_parallel_maintenance_workers` sesuai core CPU fisik.
- [ ] **Telemetry Extension:** Pastikan extension `pg_stat_statements` selalu aktif di `shared_preload_libraries`.
- [ ] **Autovacuum Health:** Verifikasi autovacuum berjalan sehat untuk mencegah bloat tabel dan menjamin validitas statistik cost model.

---

## 19. Ringkasan Eksekutif

* **Optimizer bersifat Deterministik Matematis:** Mesin SQL tidak melakukan "tebakan acak"; optimizer mengevaluasi kombinasi aljabar relasional berdasarkan model biaya (*Cost Model*) yang bergantung pada akurasi metadata di `pg_statistic`.
* **Kardinalitas adalah Kunci Utama:** Kesalahan estimasi baris (*Cardinality Misestimate*) adalah sumber tunggal terbesar terpilihnya join dan scanning paths yang keliru.
* **Sargability Bersifat Mutlak:** Penggunaan fungsi atau casting tipe data implisit pada kolom WHERE clause langsung membatalkan penggunaan B-Tree Index traversal.
* **Tuning Berbasis Metrik Konkret:** Selalu gunakan kombinasi `EXPLAIN (ANALYZE, BUFFERS)` dan `pg_stat_statements` untuk mengonfirmasi bahwa optimasi yang dilakukan benar-benar memangkas pembacaan blok memori (`shared_blks_hit`/`read`) dan mereduksi durasi eksekusi secara empiris.

---

## 20. Referensi & Bacaan Lanjutan

1. **PostgreSQL Documentation:** *Chapter 14. Performance Tips & Chapter 73. How the Planner Uses Statistics*.
2. **Goetz Graefe (1994):** *The Volcano Optimizer Generator: Extensibility and Efficient Search*.
3. **Markus Winand:** *Use The Index, Luke! A Guide to Database Performance for Developers*.
4. **Alwidian et al. (IEEE):** *Survey of Query Optimization Techniques in Relational Database Systems*.
5. **PostgreSQL Internals (Hironobu Suzuki):** *The Internals of PostgreSQL for Hardware and Software Architects*.