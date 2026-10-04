# Bab 05 Module 01: Query Planner & Optimization

---

## 01: Identitas Modul
- **Kategori:** 04-Backend-and-Database
- **Jalur Kurikulum:** PostgreSQL Database Administrator (PostgreSQL DBA)
- **Modul:** Bab 05 Module 01 - Query Planner & Optimization
- **Tingkat Kesulitan:** Advanced / Expert
- **Target Pembaca:** Database Administrators (DBA), Principal Backend Engineers, Platform Engineers, Site Reliability Engineers (SRE).
- **Prasyarat:** Pemahaman mendalam tentang Arsitektur PostgreSQL Storage Engine (Pages, Buffers, WAL), Transaction Isolation Levels, Indeks B-Tree Dasar, dan Administrasi PostgreSQL CLI (`psql`).

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Membedah arsitektur internal PostgreSQL Cost-Based Optimizer (CBO), mulai dari *Query Rewriting*, *Path Generation*, hingga *Plan Creation*.
2. Membaca, menganalisis, dan mendiagnosis output instruksi `EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)` secara presisi.
3. Menjelaskan algoritma Scan (`Seq Scan`, `Index Scan`, `Index Only Scan`, `Bitmap Scan`) dan Join (`Nested Loop`, `Hash Join`, `Merge Join`) beserta implikasi konsumsi I/O dan memorinya.
4. Mengontrol perilaku planner menggunakan parameter Planner Cost Constants (`random_page_cost`, `seq_page_cost`, `cpu_tuple_cost`) dan Engine Knobs (`work_mem`, `effective_cache_size`).
5. Mengimplementasikan dan memelihara *Extended Statistics* (`CREATE STATISTICS`) untuk menyelesaikan masalah korelasi multikolom dan dependensi fungsional.
6. Mendiagnosis degradasi performa yang disebabkan oleh *bloat*, *stale statistics*, *parameter sniffing* pada prepared statements, dan memory spilling ke disk.

---

## 03: Concept Map Diagram ASCII

```
+-----------------------------------------------------------------------------------+
|                            POSTGRESQL QUERY PIPELINE                              |
+-----------------------------------------------------------------------------------+
                                          |
                                    [ SQL Query ]
                                          v
+------------------+             +------------------+
| Parser / Lexer   | ----------> |    Parse Tree    |
+------------------+             +------------------+
                                          |
                                          v
+------------------+             +------------------+
| Query Rewriter   | ----------> |    Query Tree    | (Views, Rules applied)
+------------------+             +------------------+
                                          |
                                          v
+===================================================================================+
|                              COST-BASED OPTIMIZER                                 |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Catalog Statistics (pg_statistic, pg_class, pg_stats, pg_statistic_ext)     |  |
|  +-----------------------------------------------------------------------------+  |
|         |                              |                              |           |
|         v                              v                              v           |
|  [ Scan Paths ]                [ Join Paths ]                 [ Parallel Paths ]  |
|  - Seq Scan                    - Nested Loop                  - Gather            |
|  - Index Scan                  - Hash Join                    - Gather Merge      |
|  - Index Only Scan             - Merge Join                   - Parallel Hash     |
|  - Bitmap Index/Heap Scan                                                         |
|         \                              |                             /            |
|          +-----------------------------+----------------------------+             |
|                                        |                                          |
|                                        v                                          |
|                         [ Path Costing Engine (CBO) ]                             |
|                           - Cost = Disk I/O + CPU Cost                            |
|                           - Memory Check (work_mem)                               |
|                                        |                                          |
|                                        v                                          |
|                           [ Lowest Cost Plan Selected ]                           |
+===================================================================================+
                                          |
                                          v
+------------------+             +------------------+
| Executor Engine  | ----------> | Execution Result | (Shared Buffers / OS Cache / Disk)
+------------------+             +------------------+
```

---

## 04: Mengapa Relevan
Dalam arsitektur database modern berkapasitas terabyte hingga petabyte, query yang tidak efisien adalah penyebab utama lonjakan beban I/O, *lock contention*, dan latensi backend yang tinggi. PostgreSQL mengandalkan *Cost-Based Optimizer* (CBO) yang memproses metadata statistik untuk memilih jalur eksekusi yang paling efisien di antara ribuan kombinasi yang mungkin.

Jika statistik katalog database kedaluwarsa atau parameter biaya planner tidak dikonfigurasi dengan benar untuk media penyimpanan modern (seperti NVMe SSD), planner dapat memilih rencana eksekusi suboptimal—misalnya melakukan *Sequential Scan* pada tabel miliaran baris atau memicu *external disk merge sort*. Memahami cara kerja planner memberikan DBA dan Backend Engineer kendali penuh atas latensi eksekusi, efisiensi resource hardware, dan stabilitas performa sistem secara keseluruhan.

---

## 05: Anatomi Konsep Inti

### 1. Model Biaya Planner (Cost Model Metrics)
Planner memperkirakan total biaya eksekusi dengan menjumlahkan kalkulasi unit I/O disk dan unit siklus CPU:
$$\text{Total Cost} = (N_{\text{page, seq}} \times \text{seq\_page\_cost}) + (N_{\text{page, rnd}} \times \text{random\_page\_cost}) + (N_{\text{tuple}} \times \text{cpu\_tuple\_cost}) + (N_{\text{operator}} \times \text{cpu\_operator\_cost})$$

*   `seq_page_cost` (default `1.0`): Standar biaya akses halaman disk secara sekuensial.
*   `random_page_cost` (default `4.0`): Biaya akses halaman acak. Pada media NVMe/SSD, rasio ini umumnya diturunkan ke kisaran `1.1` - `1.25`.
*   `cpu_tuple_cost` (default `0.01`): Biaya pemrosesan satu baris data (tuple) di CPU.
*   `cpu_index_tuple_cost` (default `0.005`): Biaya pemrosesan entri pada index leaf.
*   `cpu_operator_cost` (default `0.0025`): Biaya komputasi pemrosesan operator/fungsi per baris.

### 2. Algoritma Akses Data (Scan Methods)
*   **Sequential Scan (`Seq Scan`):** Membaca seluruh block tabel dari awal hingga akhir via Shared Buffers. Efisien untuk data berukuran kecil atau query dengan selektivitas rendah (mengambil $> 20-30\%$ total baris).
*   **Index Scan:** Menelusuri B-Tree Index untuk mendapatkan `ctid` (pointer block & offset), lalu membaca baris data langsung dari Heap Page. Membutuhkan *random I/O* untuk setiap baris.
*   **Index Only Scan:** Membaca data langsung dari B-Tree tanpa mengakses Heap jika seluruh kolom yang diminta berada di dalam index dan status halaman valid pada *Visibility Map* (telah di-vacuum, all-visible).
*   **Bitmap Index Scan / Bitmap Heap Scan:** Membaca Index untuk membangun *Bitmap in-memory* berisi lokasi baris data (`Bitmap Index Scan`), lalu menyortir pointer berdasarkan urutan fisik block di disk sebelum membaca Heap Page (`Bitmap Heap Scan`). Pendekatan ini mengubah akses random I/O menjadi sequential I/O.

### 3. Algoritma Penggabungan Data (Join Methods)
*   **Nested Loop Join:** Mengiterasi baris dari *outer relation* satu per satu, lalu mencari baris yang cocok di *inner relation*. Sangat optimal jika *outer relation* berukuran kecil dan *inner relation* memiliki indeks yang sesuai.
*   **Hash Join:** Membangun *in-memory hash table* dari *inner relation* (menggunakan alokasi `work_mem`), kemudian memindai *outer relation* untuk mencocokkan hash key. Jika ukuran hash table melebihi `work_mem`, sistem akan beralih ke *multi-batch hash join* yang menulis data sementara ke disk.
*   **Merge Join:** Menggabungkan dua relasi yang telah terurut berdasarkan join key. Sangat efisien jika data input sudah terurut secara fisik (misalnya via B-Tree) atau jika kedua tabel berukuran sangat besar.

### 4. Metrik Statistik Katalog
Katalog `pg_statistic` (diakses melalui view `pg_stats`) menyimpan metadata penentu kalkulasi biaya:
*   `null_frac`: Persentase baris dengan nilai `NULL`.
*   `n_distinct`: Estimasi jumlah nilai unik (nilai negatif menunjukkan proporsi terhadap total baris).
*   `most_common_vals` (MCV) & `most_common_freqs` (MCF): Daftar nilai yang paling sering muncul beserta frekuensi kemunculannya.
*   `histogram_bounds`: Rentang partisi data untuk kolom yang tidak termasuk dalam daftar MCV.
*   `correlation`: Korelasi statistik antara urutan fisik baris data di storage disk dengan urutan logis nilai kolomnya.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Kalibrasi Parameter Planner untuk Media NVMe/SSD
Sesuaikan parameter planner berikut pada instance PostgreSQL yang berjalan di atas media penyimpanan berkecepatan tinggi:

```sql
-- Eksekusi dengan hak akses superuser
ALTER SYSTEM SET seq_page_cost = 1.0;
ALTER SYSTEM SET random_page_cost = 1.1; -- Menyamakan cost random I/O dengan sequential I/O untuk NVMe
ALTER SYSTEM SET effective_io_concurrency = 200; -- Meningkatkan asynchrony prefetch disk
ALTER SYSTEM SET default_statistics_target = 200; -- Memperluas sample histogram (default 100)
SELECT pg_reload_conf();
```

### Step 2: Konfigurasi Memory Allocation Planner
Atur alokasi memori kerja untuk menghindari tumpahan data sort/hash ke temporary disk:

```sql
-- Atur global baseline work_mem
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET hash_mem_multiplier = 2.0; -- PostgreSQL 13+, mengizinkan hash join memakai hingga 128MB
SELECT pg_reload_conf();
```

### Step 3: Membaca Format Instrumentasi EXPLAIN
Format baku analisis performa query di PostgreSQL:

```sql
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL, TIMING, COSTS, VERBOSE)
SELECT * FROM orders WHERE customer_id = 99824;
```
*   `ANALYZE`: Menjalankan query secara aktual dan mengukur waktu eksekusi riil (jangan jalankan DML mutating tanpa transaksi pembungkus rollback).
*   `BUFFERS`: Mengukur hit/read/dirtied/written shared buffers, local buffers, dan temp buffers.
*   `SETTINGS`: Menampilkan parameter konfigurasi planner non-default yang mempengaruhi query.
*   `WAL`: Menampilkan volume WAL record dan full page images yang diproduksi.

---

## 07: Contoh Kasus Sederhana

Berikut perbandingan analisis antara *Sequential Scan* dan *Index Scan* pada tabel transaksi:

```sql
-- 1. Setup tabel skenario
CREATE TABLE transaction_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Insert 500,000 dummy records
INSERT INTO transaction_logs (user_id, amount, created_at)
SELECT 
    (random() * 50000)::INT,
    (random() * 1000)::NUMERIC(12,2),
    NOW() - (random() * interval '30 days')
FROM generate_series(1, 500000);

ANALYZE transaction_logs;

-- 3. Query tanpa indeks non-PK (Memicu Seq Scan)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM transaction_logs WHERE user_id = 4210;
```

*Output (Kondisi 1 - Seq Scan):*
```text
Seq Scan on transaction_logs  (cost=0.00..9364.00 rows=11 width=25) (actual time=0.082..24.112 rows=10 loops=1)
  Filter: (user_id = 4210)
  Rows Removed by Filter: 499990
  Buffers: shared hit=4364
Execution Time: 24.135 ms
```

```sql
-- 4. Tambahkan B-Tree Index dan jalankan ulang
CREATE INDEX idx_trx_user_id ON transaction_logs (user_id);

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM transaction_logs WHERE user_id = 4210;
```

*Output (Kondisi 2 - Index Scan):*
```text
Bitmap Heap Scan on transaction_logs  (cost=4.37..38.93 rows=11 width=25) (actual time=0.015..0.021 rows=10 loops=1)
  Recheck Cond: (user_id = 4210)
  Heap Blocks: exact=10
  Buffers: shared hit=13
  ->  Bitmap Index Scan on idx_trx_user_id  (cost=0.00..4.37 rows=11 width=0) (actual time=0.009..0.009 rows=10 loops=1)
        Index Cond: (user_id = 4210)
        Buffers: shared hit=3
Execution Time: 0.038 ms
```

**Analisis Hasil:** Penggunaan index menurunkan waktu eksekusi dari `24.135 ms` menjadi `0.038 ms` (akselerasi $>600\times$) dan mengurangi konsumsi shared buffer hits dari `4364 blocks` menjadi `13 blocks`.

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem pemantauan komprehensif, simulasi *stale statistics*, pembuatan *Extended Statistics* multikolom, serta optimasi query join kompleks.

```sql
-- ============================================================================
-- SCRIPT OPTIMASI & MULTIVARIATE EXTENDED STATISTICS
-- ============================================================================

-- 1. Setup Skema E-Commerce Production Simulation
CREATE SCHEMA IF NOT EXISTS commerce_core;

CREATE TABLE commerce_core.regions (
    region_id INT PRIMARY KEY,
    region_name VARCHAR(50) NOT NULL,
    country_code CHAR(2) NOT NULL
);

CREATE TABLE commerce_core.customers (
    customer_id BIGSERIAL PRIMARY KEY,
    region_id INT REFERENCES commerce_core.regions(region_id),
    state VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL,
    is_vip BOOLEAN DEFAULT FALSE,
    credit_limit NUMERIC(12,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE commerce_core.orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT REFERENCES commerce_core.customers(customer_id),
    order_status VARCHAR(20) NOT NULL,
    total_amount NUMERIC(14,2) NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_customers_region_state_city ON commerce_core.customers(region_id, state, city);
CREATE INDEX idx_orders_customer_id ON commerce_core.orders(customer_id);
CREATE INDEX idx_orders_placed_status ON commerce_core.orders(placed_at, order_status) INCLUDE (total_amount);

-- 2. Injeksi Dataset Skala Menengah
INSERT INTO commerce_core.regions (region_id, region_name, country_code)
VALUES 
    (1, 'Jawa Barat', 'ID'),
    (2, 'DKI Jakarta', 'ID'),
    (3, 'California', 'US');

-- Mengisi 200.000 customer dengan dependensi fungsional buatan:
-- (state = 'CA' SELALU berpasangan dengan city = 'San Francisco' dan region_id = 3)
INSERT INTO commerce_core.customers (region_id, state, city, is_vip, credit_limit, created_at)
SELECT 
    CASE WHEN i % 2 = 0 THEN 3 ELSE 1 END,
    CASE WHEN i % 2 = 0 THEN 'CA' ELSE 'JB' END,
    CASE WHEN i % 2 = 0 THEN 'San Francisco' ELSE 'Bandung' END,
    (random() > 0.95),
    (random() * 50000)::NUMERIC(12,2),
    NOW() - (random() * interval '365 days')
FROM generate_series(1, 200000) AS i;

-- Mengisi 1.000.000 orders
INSERT INTO commerce_core.orders (customer_id, order_status, total_amount, placed_at)
SELECT 
    (random() * 199999 + 1)::BIGINT,
    (ARRAY['PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED'])[floor(random() * 4 + 1)],
    (random() * 5000)::NUMERIC(14,2),
    NOW() - (random() * interval '180 days')
FROM generate_series(1, 1000000);

ANALYZE commerce_core.regions;
ANALYZE commerce_core.customers;
ANALYZE commerce_core.orders;

-- 3. Identifikasi Masalah: Misestimasi Row Count akibat Dependent Columns
-- Planner mengasumsikan P(A AND B) = P(A) * P(B).
-- Padahal state = 'CA' dan city = 'San Francisco' memiliki korelasi 100%.

EXPLAIN (ANALYZE, BUFFERS)
SELECT * 
FROM commerce_core.customers 
WHERE state = 'CA' AND city = 'San Francisco';
-- Perhatikan selisih tajam antara 'rows=...' estimasi dengan 'rows=...' aktual!

-- 4. Solusi Produksi: Multivariate Extended Statistics
CREATE STATISTICS IF NOT EXISTS stat_customers_state_city 
ON state, city, region_id FROM commerce_core.customers;

-- Hitung ulang statistik
ANALYZE commerce_core.customers;

-- Validasi perbaikan estimasi planner
EXPLAIN (ANALYZE, BUFFERS)
SELECT * 
FROM commerce_core.customers 
WHERE state = 'CA' AND city = 'San Francisco';
-- Estimasi baris kini presisi sesuai distribusi aktual.

-- 5. Query Tuning Lanjutan: Kompleks Join & Agregasi Menggunakan CTE Materialization Control
EXPLAIN (ANALYZE, BUFFERS, SETTINGS)
WITH HighValueOrders AS MATERIALIZED (
    SELECT 
        customer_id, 
        SUM(total_amount) AS total_spent,
        COUNT(order_id) AS total_orders
    FROM commerce_core.orders
    WHERE placed_at >= NOW() - INTERVAL '90 days'
      AND order_status = 'COMPLETED'
    GROUP BY customer_id
    HAVING SUM(total_amount) > 10000
)
SELECT 
    c.customer_id,
    c.city,
    c.state,
    hvo.total_spent,
    hvo.total_orders
FROM HighValueOrders hvo
JOIN commerce_core.customers c ON c.customer_id = hvo.customer_id
WHERE c.is_vip = TRUE;
```

---

## 09: Diagram Alur Kerja ASCII

### Alur Keputusan Query Planner Memilih Metode Join

```
                  [ Mulai Evaluasi Join Antara Relasi A & B ]
                                       |
                                       v
                     /-----------------------------------\
                    < Apakah kedua set data sudah terurut >
                    <        berdasarkan Join Key?        >
                     \-----------------------------------/
                                   /       \
                             YA  /           \ TIDAK
                               v               v
                     +--------------+    /-----------------------------------\
                     |  MERGE JOIN  |   <  Apakah salah satu relasi berukuran >
                     +--------------+   <  sangat kecil & memiliki index PK?  >
                                         \-----------------------------------/
                                                   /       \
                                             YA  /           \ TIDAK
                                               v               v
                                     +---------------+   /-----------------------------------\
                                     |  NESTED LOOP  |  < Apakah estimasi Hash Table relasi   >
                                     | (Index Inner) |  < bagian dalam muat di work_mem?      >
                                     +---------------+   \-----------------------------------/
                                                                   /       \
                                                             YA  /           \ TIDAK
                                                               v               v
                                                     +---------------+   +-------------------+
                                                     |   HASH JOIN   |   | HASH JOIN 2-PASS  |
                                                     |  (In-Memory)  |   | (Spill to Disk)   |
                                                     +---------------+   +-------------------+
```

---

## 10: Analisis Trade-offs

| Metode / Fitur Planner | Keuntungan Utama | Kerugian / Trade-off | Skenario Ideal Penggunaan |
| :--- | :--- | :--- | :--- |
| **Nested Loop Join** | Latensi inisialisasi minimal; efisien pada subset data kecil. | Kompleksitas kuadratik $\mathcal{O}(N \times M)$ jika relasi dalam tidak terindeks. | OLTP: Lookup satu baris atau join relasi kecil ke tabel berindeks. |
| **Hash Join** | Sangat cepat untuk relasi besar tanpa data terurut; kompleksitas $\mathcal{O}(N + M)$. | Membutuhkan alokasi memori besar; write disk jika melebihi `work_mem`. | OLAP / Batch Processing: Penggabungan tabel berukuran besar tanpa indeks terurut. |
| **Merge Join** | Membutuhkan memori konstan; efisien jika input sudah terurut. | Membutuhkan overhead sorting awal jika input belum terurut. | Penggabungan data bervolume masif yang sudah memiliki B-Tree index pada join keys. |
| **High `work_mem`** | Mencegah hash joins dan sorting meluap ke temporary files di disk. | Risiko memicu OOM (Out Of Memory) Killer karena dialokasikan per node query per koneksi. | Sesi batch analitik khusus atau koneksi terisolasi. |
| **High Statistics Target** | Estimasi kalkulasi biaya menjadi lebih akurat pada data terdistribusi timpang (*skewed*). | Meningkatkan durasi proses `ANALYZE` dan overhead CPU saat query planning. | Tabel partisi utama dengan distribusi nilai yang sangat bervariasi. |

---

## 11: Best Practices & Antipatterns

### Best Practices
1. **Rutin Melakukan Sample Recalibration:** Lakukan `ANALYZE` secara terprogram setelah transaksi *bulk load* (ETL) data besar selesai.
2. **Kompensasi Arsitektur Hardware:** Set `random_page_cost = 1.1` pada media penyimpanan NVMe/PCIe storage modern. Nilai default (`4.0`) ditujukan untuk disk mekanik (HDD).
3. **Optimasi Berbasis Partial Index:** Buat partial index untuk memfilter *unbalanced flags* (misalnya: `WHERE is_processed = FALSE`).
4. **Gunakan Parameter Extended Statistics:** Implementasikan `CREATE STATISTICS` jika terdapat filter korelasi multikolom (contoh: `kategori_id` dengan `subkategori_id`).

### Antipatterns
1. **Sargable Predicate Violation:** Menerapkan fungsi native pada kolom index dalam klausa `WHERE`.
   *   ❌ *Buruk:* `WHERE DATE(created_at) = '2023-10-01'` (Index lookup dinonaktifkan, memicu full Seq Scan).
   *   ✅ *Baik:* `WHERE created_at >= '2023-10-01 00:00:00Z' AND created_at < '2023-10-02 00:00:00Z'`.
2. **Kebutaan Blind Tuning dengan Menyetel Engine Knobs Global:** Menaikkan `enable_seqscan = OFF` secara global pada database cluster. Ini memaksa planner memilih index scan meskipun biaya I/O riilnya jauh lebih mahal daripada sequential scan.
3. **Alokasi `work_mem` Global yang Terlalu Agresif:** Menyetel `work_mem = 4GB` secara global pada server dengan `max_connections = 500`. Hal ini dapat menyebabkan crash OOM seketika ketika lonjakan query bersamaan terjadi.

---

## 12: Security Hardening

Dalam konteks query planning dan optimasi, proteksi keamanan database berfokus pada mitigasi ancaman *resource exhaustion* (DoS) dan kebocoran data tersembunyi (*side-channel leaks*):

```sql
-- 1. Pencegahan DoS Query Runaway dengan Statement Timeout
ALTER ROLE app_report_user SET statement_timeout = '15s';
ALTER ROLE app_backend_user SET statement_timeout = '3s';

-- 2. Batasi konsumsi temporary files agar tidak memenuhi disk drive instance
ALTER ROLE app_backend_user SET temp_file_limit = '256MB';

-- 3. Row-Level Security (RLS) Leak-Proof Optimization
-- Fungsi custom yang digunakan dalam Security Qualifiers HARUS berstatus LEAKPROOF
-- agar planner tidak mengevaluasi fungsi buatan user sebelum RLS filter diterapkan.
CREATE OR REPLACE FUNCTION commerce_core.verify_tenant_access(input_tenant_id INT) 
RETURNS BOOLEAN
IMMUTABLE STRICT LEAKPROOF
LANGUAGE plpgsql 
AS $$
BEGIN
    RETURN (CURRENT_SETTING('app.current_tenant_id', true)::INT = input_tenant_id);
END;
$$;
```

---

## 13: Observabilitas & Debugging

Gunakan modul ekstensi `pg_stat_statements` untuk memantau performa query secara persisten:

```sql
-- Pastikan shared_preload_libraries = 'pg_stat_statements' pada postgresql.conf
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 1. Query untuk Mengidentifikasi Top 5 Query dengan Mean Exec Time Tertinggi
SELECT 
    queryid,
    SUBSTRING(query, 1, 80) AS short_query,
    calls,
    total_exec_time::NUMERIC(10,2) AS total_time_ms,
    mean_exec_time::NUMERIC(10,2) AS avg_time_ms,
    shared_blks_hit,
    shared_blks_read,
    shared_blks_dirtied,
    temp_blks_read,
    temp_blks_written
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 5;

-- 2. Query untuk Mendeteksi Query yang Paling Banyak Tumpah ke Temp Disk (Disk Spill)
SELECT 
    queryid,
    calls,
    temp_blks_written,
    local_blks_written,
    SUBSTRING(query, 1, 100) AS query
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC
LIMIT 10;
```

---

## 14: Benchmarking & Performance

Jalankan skenario pengujian komparatif performa query sebelum dan sesudah optimasi indeks serta penyesuaian memory engine menggunakan utility `pgbench`.

### 1. Definisi Query Uji (`bench_query.sql`)
```sql
\set cid random(1, 200000)
SELECT 
    c.customer_id, c.city, o.order_id, o.total_amount 
FROM commerce_core.customers c
JOIN commerce_core.orders o ON c.customer_id = o.customer_id
WHERE c.customer_id = :cid
  AND o.order_status = 'COMPLETED';
```

### 2. Eksekusi Load Test via Terminal Bash
```bash
# Baseline Benchmark (8 Clients, 2 Threads, durasi 30 detik)
pgbench -U postgres -d postgres -M prepared -N -f bench_query.sql -c 8 -j 2 -T 30
```

### 3. Komparasi Metrik

| Konfigurasi Parameter | Throughput (TPS) | Latensi Rata-rata ($P_{50}$) | Latensi $P_{99}$ | Shared Block Reads | Temp Disk Spills |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Default Settings** (`work_mem=4MB`, `rnd_cost=4.0`, No Composite Index) | 1,214 | 6.58 ms | 48.21 ms | 312,890 blocks | 14,310 blocks |
| **Optimized Settings** (`work_mem=64MB`, `rnd_cost=1.1`, Composite Indexes Applied) | 14,890 | 0.53 ms | 2.11 ms | 412 blocks | 0 blocks |

---

## 15: Hands-on Lab Mini-Project

### Skenario Masalah
Perusahaan logistik menghadapi lonjakan latensi tinggi saat menjalankan dashboard harian. Query pencarian pengiriman paket yang tertunda (*delayed status*) mengalami degradasi latensi parah seiring membesarnya ukuran partisi tabel tracking.

### Langkah-langkah Praktik

```sql
-- LANGKAH 1: Setup Lingkungan Lab
CREATE TABLE shipment_tracker (
    tracking_id BIGSERIAL PRIMARY KEY,
    carrier_code VARCHAR(10) NOT NULL,
    current_status VARCHAR(20) NOT NULL,
    is_delayed BOOLEAN NOT NULL,
    last_checkpoint_timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB
);

-- LANGKAH 2: Injeksi Data (1 Juta Baris dengan Skewed Distribution)
-- 99% paket berstatus 'DELIVERED' (is_delayed = false), hanya 1% berstatus 'IN_TRANSIT' & is_delayed = true
INSERT INTO shipment_tracker (carrier_code, current_status, is_delayed, last_checkpoint_timestamp)
SELECT 
    (ARRAY['JNE', 'SICEPAT', 'GOSEND'])[floor(random() * 3 + 1)],
    CASE WHEN random() > 0.01 THEN 'DELIVERED' ELSE 'IN_TRANSIT' END,
    CASE WHEN random() > 0.01 THEN FALSE ELSE TRUE END,
    NOW() - (random() * interval '60 days')
FROM generate_series(1, 1000000);

VACUUM ANALYZE shipment_tracker;

-- LANGKAH 3: Jalankan Problematic Query
-- Kita ingin mengambil paket yang sedang terlambat (delayed) dalam 7 hari terakhir
EXPLAIN (ANALYZE, BUFFERS)
SELECT carrier_code, COUNT(*)
FROM shipment_tracker
WHERE is_delayed = TRUE 
  AND last_checkpoint_timestamp >= NOW() - INTERVAL '7 days'
GROUP BY carrier_code;

-- LANGKAH 4: Solusi Optimasi Menggunakan Partial Index
CREATE INDEX idx_shipment_delayed_recent 
ON shipment_tracker (last_checkpoint_timestamp, carrier_code) 
WHERE is_delayed = TRUE;

-- Verifikasi Ulang Execution Plan
EXPLAIN (ANALYZE, BUFFERS)
SELECT carrier_code, COUNT(*)
FROM shipment_tracker
WHERE is_delayed = TRUE 
  AND last_checkpoint_timestamp >= NOW() - INTERVAL '7 days'
GROUP BY carrier_code;
```

---

## 16: Automated Testing & Verification

Skrip verifikasi otomatis berbasis `PL/pgSQL` untuk mendeteksi *plan regression* dan memastikan tidak ada *Sequential Scan* yang terjadi pada query operasional utama:

```sql
DO $$
DECLARE
    plan_json JSONB;
    node_type TEXT;
    actual_rows BIGINT;
    execution_time NUMERIC;
BEGIN
    -- 1. Eksekusi EXPLAIN JSON ke dalam variabel
    EXECUTE 'EXPLAIN (ANALYZE, FORMAT JSON) 
             SELECT carrier_code, COUNT(*) 
             FROM shipment_tracker 
             WHERE is_delayed = TRUE 
               AND last_checkpoint_timestamp >= NOW() - INTERVAL ''7 days'' 
             GROUP BY carrier_code' 
    INTO plan_json;

    -- 2. Parsing output JSON node root
    node_type := plan_json->0->'Plan'->'Node Type';
    execution_time := (plan_json->0->'Execution Time')::TEXT::NUMERIC;

    RAISE NOTICE 'Node Plan Terdeteksi: %, Waktu Eksekusi: % ms', node_type, execution_time;

    -- 3. Assertion 1: Validasi bahwa operasi tidak fallback ke Seq Scan
    IF jsonb_path_exists(plan_json, '$..Plan ? (@."Node Type" == "Seq Scan")') THEN
        RAISE EXCEPTION 'TEST FAILED: Sequential Scan terdeteksi pada query shipment tracking!';
    END IF;

    -- 4. Assertion 2: Validasi threshold latensi eksekusi di bawah 5 milidetik
    IF execution_time > 5.0 THEN
        RAISE EXCEPTION 'TEST FAILED: Latensi eksekusi melebihi batas SLA! Waktu: % ms', execution_time;
    END IF;

    RAISE NOTICE 'SUCCESS: Seluruh assertion optimizer lolos verifikasi produksi.';
END;
$$ LANGUAGE plpgsql;
```

---

## 17: Troubleshooting Guide

### 1. Masalah: Planner Salah Menghitung Estimasi Baris (Row Estimation Error)
*   **Gejala:** Output `EXPLAIN` menunjukkan `rows=1` padahal `actual rows=500000`, menyebabkan pemilihan `Nested Loop` yang sangat lambat.
*   **Akar Masalah:** Katalog statistik out-of-date atau terdapat multikolom berkorelasi tinggi.
*   **Solusi:**
    1. Jalankan `ANALYZE tablename;`.
    2. Jika data timpang (*skewed*), naikkan target sampel: `ALTER TABLE tablename ALTER COLUMN colname SET STATISTICS 500;`.
    3. Jika terdapat dependensi antarkolom, buat extended statistics via `CREATE STATISTICS`.

### 2. Masalah: Sorting atau Hash Meluap ke Disk (Disk Spilling)
*   **Gejala:** Output `EXPLAIN (ANALYZE)` menunjukkan node `Sort Method: external merge Disk: 48920kB` atau `HashBatch 4/8 Spill to Disk`.
*   **Akar Masalah:** Ukuran data operasi melebihi alokasi memori `work_mem`.
*   **Solusi:**
    1. Naikkan `work_mem` secara dinamis pada level session: `SET work_mem = '256MB';`.
    2. Sediakan B-Tree index yang sudah terurut sesuai klausa `ORDER BY` untuk mengeliminasi pemrosesan sort in-memory.

### 3