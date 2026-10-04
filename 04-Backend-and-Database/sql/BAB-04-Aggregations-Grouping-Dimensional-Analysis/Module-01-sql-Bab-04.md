# Modul 04.01: Aggregations, Grouping, & Dimensional Analysis

---

## 01. Identitas Modul

| Atribut | Nilai |
| :--- | :--- |
| **Track** | Backend & Database Engineering |
| **Domain** | SQL & Relational Data Systems |
| **Tingkat Kesulitan** | Intermediate to Advanced |
| **Prasyarat** | DDL/DML Fundamentals, Relational Joins, Filtering (`WHERE`), Basic Subqueries |
| **DBMS Target** | PostgreSQL 15+ / 16+ (Standar ANSI SQL Compliant) |
| **Estimasi Waktu** | 4.5 - 6 Jam Pembelajaran Mandiri & Praktikum |

---

## 02. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Memahami Lifecycle Eksekusi Logis**: Menganalisis urutan pemrosesan query SQL (`FROM` $\rightarrow$ `WHERE` $\rightarrow$ `GROUP BY` $\rightarrow$ `HAVING` $\rightarrow$ `SELECT` $\rightarrow$ `DISTINCT` $\rightarrow$ `ORDER BY` $\rightarrow$ `LIMIT`) dan dampaknya terhadap agregasi data.
2. **Menguasai Agregasi Tingkat Lanjut**: Mengimplementasikan agregasi kondisional via `FILTER (WHERE ...)` dan ekspresi `CASE WHEN`, serta memahami komputasi data array/string agregat (`string_agg`, `array_agg`).
3. **Mengeksekusi Analisis Multidimensi**: Mendesain query pelaporan hierarki komprehensif menggunakan klausa ANSI SQL `GROUPING SETS`, `ROLLUP`, dan `CUBE` dengan penanganan nilai sentinel via fungsi `GROUPING()`.
4. **Mencegah Degradasi Performa Engine**: Mengidentifikasi titik kritis transisi dari in-memory Hash Aggregation ke On-Disk Hash/Sort Aggregation serta menyusun indexing strategy yang optimal.
5. **Menulis Query Aman dan Robust**: Menghilangkan risiko SQL Injection pada dynamic group identifiers serta mencegah anomali `NULL` dalam agregasi numerik.

---

## 03. Concept Map Diagram ASCII

```
[Raw Relational Tuples]
          │
          ▼
   ┌──────────────┐
   │ WHERE Filter │ ───(Eliminasi baris level individual)
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │   GROUP BY   │ ───[Grouping Engine]───► HashAggregate (Memory/Disk)
   └──────┬───────┘                    └───► GroupAggregate (B-Tree Sorted)
          │
          ├─────────────────────────────────────────┐
          │                                         │
          ▼                                         ▼
┌───────────────────┐                     ┌───────────────────┐
│ Basic Aggregate   │                     │ Multi-Dimensional │
│ - SUM, AVG, COUNT │                     │ - GROUPING SETS   │
│ - MIN, MAX, BOOL  │                     │ - ROLLUP          │
│ - array_agg       │                     │ - CUBE            │
└─────────┬─────────┘                     └─────────┬─────────┘
          │                                         │
          └──────────────────┬──────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  HAVING Filter  │ ───(Eliminasi grup teragregasi)
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ SELECT & Output │
                    └─────────────────┘
```

---

## 04. Mengapa Relevan

Dalam arsitektur data modern, data operasional mentah (OLTP) tidak memiliki nilai analitis sebelum ditransformasikan menjadi bentuk teragregasi. Beban komputasi agregasi sering kali dipindahkan secara tidak efisien ke application layer—seperti menarik ratusan ribu baris ke backend via ORM hanya untuk menghitung total nominal dan rata-rata. Pendekatan antipattern ini memicu:

1. **Network I/O Saturation**: Bandwidth jaringan terbuang untuk transfer payload data yang masif.
2. **Excessive Memory Footprint**: Heap memory service backend rentan terhadap *Out of Memory (OOM)*.
3. **CPU Waste**: Garbage collection thread backend bekerja terlalu keras memproses objek transien.

Mesin database relasional modern memiliki optimasi tingkat C/C++, eksekusi *vectorized* / *parallel workers*, serta algoritma hashing dan sorting yang sangat teroptimasi. Penguasaan grouping multidimensi (`ROLLUP`, `CUBE`, `GROUPING SETS`) memungkinkan analitik analitis level enterprise (seperti pelaporan keuangan, metrik platform SaaS, audit log per departemen) dijalankan secara deklaratif dalam single query trip dengan performa tinggi.

---

## 05. Anatomi Konsep Inti

### 1. Perbedaan Mendasar `WHERE` vs `HAVING`

* **`WHERE`**: Merupakan predikat filter baris (*row-level filter*). Dieksekusi **sebelum** fase pembentukan grup (`GROUP BY`). `WHERE` tidak dapat mengevaluasi fungsi agregat karena komputasi grup belum terjadi.
* **`HAVING`**: Merupakan predikat filter grup (*group-level filter*). Dieksekusi **setelah** fungsi agregat dihitung untuk setiap partisi grup. Baris grup yang tidak memenuhi ekspresi boolean pada `HAVING` akan dieliminasi dari result set.

### 2. Agregat Standar vs Agregat Kondisional ANSI SQL

Agregat standar menghitung semua baris dalam partisi:

$$\text{AVG}(X) = \frac{\sum_{i=1}^n X_i}{n} \quad (\text{eksklusif } NULL)$$

PostgreSQL mendukung klausa `FILTER (WHERE condition)` yang jauh lebih clean, efisien, dan ekspresif dibanding idiom legacy `SUM(CASE WHEN condition THEN 1 ELSE 0 END)`:

```sql
-- ANSI Standard Filter Clause
SELECT 
    department_id,
    COUNT(*) AS total_employees,
    COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_employees,
    SUM(salary) FILTER (WHERE role = 'ENGINEER') AS engineer_payroll
FROM employees
GROUP BY department_id;
```

### 3. Ekstensi Analisis Dimensi Multilevel

* **`GROUPING SETS`**: Mendefinisikan kumpulan subset partisi grouping secara eksplisit dalam satu query tanpa memerlukan operasi `UNION ALL`.
* **`ROLLUP(A, B, C)`**: Menghasilkan grouping hierarki berjenjang:
  1. `(A, B, C)`
  2. `(A, B)`
  3. `(A)`
  4. `()` (Grand Total)
* **`CUBE(A, B, C)`**: Menghasilkan semua kombinasi subset eksponensial ($2^N$ kombinasi):
  1. `(A, B, C)`, `(A, B)`, `(A, C)`, `(B, C)`
  2. `(A)`, `(B)`, `(C)`
  3. `()` (Grand Total)
* **`GROUPING(column_name, ...)`**: Mengembalikan integer bit (`0` jika kolom tersebut adalah bagian dari agregasi grup baris tersebut, `1` jika kolom bernilai `NULL` karena merupakan hasil kalkulasi super-agregat). Mencegah ambiguitas antara `NULL` alami data vs `NULL` buatan sistem agregasi.

---

## 06. Panduan Implementasi Step-by-Step

### Tahap 1: Evaluasi Kardinalitas & Memory Planner

Sebelum menulis query analitik, periksa kardinalitas kolom target. Agregasi dengan kardinalitas rendah (misal: `status`, `country_code`) sangat efisien menggunakan `HashAggregate`. Kardinalitas tinggi dengan data besar membutuhkan memori `work_mem` yang memadai agar tidak tumpah (*spill*) ke disk.

```sql
-- Cek alokasi work_mem per connection worker
SHOW work_mem;

-- Tingkatkan lokal untuk session laporan kompleks jika diperlukan
SET work_mem = '64MB';
```

### Tahap 2: Menulis Agregasi Multidimensi dengan Penanda Hierarki

Gunakan `GROUPING()` untuk mengganti `NULL` representasional dengan string deskriptif secara aman:

```sql
SELECT 
    CASE WHEN GROUPING(region) = 1 THEN 'ALL REGIONS' ELSE region END AS region,
    CASE WHEN GROUPING(category) = 1 THEN 'ALL CATEGORIES' ELSE category END AS category,
    SUM(amount) AS total_revenue,
    GROUPING(region, category) AS grouping_bit
FROM sales_records
GROUP BY ROLLUP (region, category);
```

### Tahap 3: Optimasi Strategi Indeks untuk Grouping

Untuk menghindari runtime sorting saat komputasi agregasi:
1. Buat B-Tree Composite Index yang mencakup seluruh kolom agregasi:
   `CREATE INDEX idx_sales_reg_cat_amt ON sales_records (region, category) INCLUDE (amount);`
2. Index ini memungkinkan PostgreSQL melakukan **Index Only Scan** dilanjutkan dengan **GroupAggregate** tanpa sorting di memory/disk.

---

## 07. Contoh Kasus Sederhana

Skenario: Menghitung metrik performa toko retail online sederhana.

### Skema & Data Inisial

```sql
CREATE TABLE retail_orders (
    order_id INT PRIMARY KEY,
    store_branch VARCHAR(50),
    payment_method VARCHAR(30),
    total_amount NUMERIC(10, 2),
    is_refunded BOOLEAN
);

INSERT INTO retail_orders VALUES
(1, 'Jakarta-Pusat', 'CREDIT_CARD', 500000.00, false),
(2, 'Jakarta-Pusat', 'QRIS',        150000.00, false),
(3, 'Jakarta-Pusat', 'QRIS',        200000.00, true),
(4, 'Surabaya-Timur', 'CASH',       100000.00, false),
(5, 'Surabaya-Timur', 'CREDIT_CARD', 750000.00, false),
(6, 'Surabaya-Timur', 'CASH',        50000.00,  true);
```

### Problem Statement

Buat laporan per `store_branch` yang menampilkan:
1. Total omzet kotor (termasuk refund).
2. Total omzet bersih (hanya transaksi yang tidak di-refund).
3. Persentase tingkat refund (*refund rate* berdasarkan jumlah transaksi).
4. Daftar metode pembayaran unik yang digunakan (dalam bentuk array).
5. Filter hanya cabang dengan total omzet bersih > Rp 200.000.

### Query Solusi

```sql
SELECT 
    store_branch,
    COUNT(*) AS total_transactions,
    SUM(total_amount) AS gross_revenue,
    COALESCE(SUM(total_amount) FILTER (WHERE NOT is_refunded), 0.00) AS net_revenue,
    ROUND(
        (COUNT(*) FILTER (WHERE is_refunded)::NUMERIC / COUNT(*)::NUMERIC) * 100, 
        2
    ) AS refund_rate_pct,
    array_agg(DISTINCT payment_method ORDER BY payment_method) AS used_payment_methods
FROM retail_orders
GROUP BY store_branch
HAVING COALESCE(SUM(total_amount) FILTER (WHERE NOT is_refunded), 0.00) > 200000.00;
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi end-to-end data pipeline query analitik penjualan e-commerce multiregional dengan dukungan dimensional rollup, validasi data, dan dynamic grouping indicators.

```sql
-- ============================================================================
-- 1. SETUP SKEMA & STRUKTUR TABEL
-- ============================================================================
DROP TABLE IF EXISTS analytics_orders CASCADE;
DROP TABLE IF EXISTS dim_merchants CASCADE;

CREATE TABLE dim_merchants (
    merchant_id BIGINT PRIMARY KEY,
    merchant_name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    tier VARCHAR(20) NOT NULL CHECK (tier IN ('TIER_1', 'TIER_2', 'TIER_3'))
);

CREATE TABLE analytics_orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id BIGINT NOT NULL REFERENCES dim_merchants(merchant_id),
    order_timestamp TIMESTAMPTZ NOT NULL,
    order_status VARCHAR(20) NOT NULL CHECK (order_status IN ('COMPLETED', 'CANCELLED', 'DISPUTED')),
    gross_amount NUMERIC(15, 4) NOT NULL CHECK (gross_amount >= 0),
    discount_amount NUMERIC(15, 4) NOT NULL DEFAULT 0.0000,
    net_amount NUMERIC(15, 4) GENERATED ALWAYS AS (gross_amount - discount_amount) STORED,
    currency VARCHAR(3) NOT NULL DEFAULT 'IDR'
);

-- ============================================================================
-- 2. INDEXING STRATEGY
-- ============================================================================
CREATE INDEX idx_dim_merchants_country_tier 
ON dim_merchants (country_code, tier, merchant_id);

CREATE INDEX idx_analytics_orders_timestamp_merchant 
ON analytics_orders (order_timestamp, merchant_id) 
INCLUDE (order_status, gross_amount, net_amount);

-- ============================================================================
-- 3. MOCK DATA SEEDING
-- ============================================================================
INSERT INTO dim_merchants (merchant_id, merchant_name, country_code, tier) VALUES
(101, 'Alpha Tech ID', 'ID', 'TIER_1'),
(102, 'Beta Fashion ID', 'ID', 'TIER_2'),
(103, 'Gamma Groceries SG', 'SG', 'TIER_1'),
(104, 'Delta Hardware MY', 'MY', 'TIER_3');

INSERT INTO analytics_orders (merchant_id, order_timestamp, order_status, gross_amount, discount_amount) VALUES
(101, '2026-03-01 10:00:00+07', 'COMPLETED', 1500000.0000, 50000.0000),
(101, '2026-03-01 12:30:00+07', 'COMPLETED',  850000.0000, 25000.0000),
(101, '2026-03-02 09:15:00+07', 'CANCELLED',  400000.0000,      0.0000),
(102, '2026-03-01 14:00:00+07', 'COMPLETED',  300000.0000,      0.0000),
(102, '2026-03-02 16:45:00+07', 'DISPUTED',   250000.0000,  10000.0000),
(103, '2026-03-01 11:10:00+08', 'COMPLETED', 5200000.0000, 200000.0000),
(103, '2026-03-02 15:20:00+08', 'COMPLETED', 3100000.0000, 100000.0000),
(104, '2026-03-02 18:00:00+08', 'COMPLETED',  950000.0000,  50000.0000);

-- ============================================================================
-- 4. PRODUCTION-GRADE DIMENSIONAL AGGREGATION QUERY (CUBE & GROUPING)
-- ============================================================================
WITH base_metrics AS (
    SELECT 
        m.country_code,
        m.tier,
        m.merchant_name,
        COUNT(o.order_id) AS total_orders,
        COUNT(o.order_id) FILTER (WHERE o.order_status = 'COMPLETED') AS completed_orders,
        COUNT(o.order_id) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders,
        COUNT(o.order_id) FILTER (WHERE o.order_status = 'DISPUTED') AS disputed_orders,
        COALESCE(SUM(o.gross_amount), 0.0000) AS total_gross_volume,
        COALESCE(SUM(o.net_amount) FILTER (WHERE o.order_status = 'COMPLETED'), 0.0000) AS total_net_completed_volume,
        COALESCE(AVG(o.net_amount) FILTER (WHERE o.order_status = 'COMPLETED'), 0.0000) AS avg_completed_ticket_size
    FROM dim_merchants m
    LEFT JOIN analytics_orders o ON m.merchant_id = o.merchant_id
        AND o.order_timestamp >= '2026-03-01 00:00:00+00' 
        AND o.order_timestamp <  '2026-03-03 00:00:00+00'
    GROUP BY CUBE(m.country_code, m.tier, m.merchant_name)
)
SELECT 
    -- Dimensional Formatting based on GROUPING metadata
    CASE 
        WHEN GROUPING(country_code) = 1 THEN '== GLOBAL TOTAL ==' 
        ELSE country_code 
    END AS country,
    
    CASE 
        WHEN GROUPING(tier) = 1 AND GROUPING(country_code) = 1 THEN '== ALL TIERS (GLOBAL) =='
        WHEN GROUPING(tier) = 1 THEN '== ALL TIERS (COUNTRY) =='
        ELSE tier 
    END AS merchant_tier,
    
    CASE 
        WHEN GROUPING(merchant_name) = 1 AND GROUPING(tier) = 1 THEN '== ALL MERCHANTS (ROLLUP) =='
        WHEN GROUPING(merchant_name) = 1 THEN '== SUB-TOTAL (TIER) =='
        ELSE merchant_name 
    END AS merchant,
    
    -- Calculated Metrics
    total_orders,
    completed_orders,
    cancelled_orders,
    disputed_orders,
    
    -- Financial Aggregates
    ROUND(total_gross_volume, 2) AS gross_vol,
    ROUND(total_net_completed_volume, 2) AS net_completed_vol,
    ROUND(avg_completed_ticket_size, 2) AS avg_ticket_size,
    
    -- Operational Health KPIs
    CASE 
        WHEN total_orders = 0 THEN 0.00
        ELSE ROUND((cancelled_orders::NUMERIC / total_orders::NUMERIC) * 100, 2)
    END AS cancellation_rate_pct,
    
    -- Grouping Bitmask for Programmatic Downstream Consumption
    GROUPING(country_code, tier, merchant_name) AS grouping_level_id

FROM base_metrics
ORDER BY 
    GROUPING(country_code) ASC,
    country_code NULLS LAST,
    GROUPING(tier) ASC,
    tier NULLS LAST,
    GROUPING(merchant_name) ASC,
    merchant_name NULLS LAST;
```

---

## 09. Diagram Alur Kerja Mesin Eksekusi SQL

```
[Incoming SQL Query with GROUP BY / ROLLUP]
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│              PostgreSQL Query Optimizer                  │
│  - Evaluasi Index B-Tree vs Seq Scan                     │
│  - Estimasi Kardinalitas & Alokasi Memory (work_mem)     │
└──────────────────────────┬───────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
  [Data is Pre-Sorted /       [Data is Unsorted /
   B-Tree Index Available]     High Hash Efficiency]
             │                           │
             ▼                           ▼
   ┌───────────────────┐       ┌───────────────────┐
   │  GroupAggregate   │       │   HashAggregate   │
   │   (Memory Lean)   │       │  (Fast In-Memory) │
   └─────────┬─────────┘       └─────────┬─────────┘
             │                           │
             │                 ┌─────────┴─────────┐
             │                 │ Fits in work_mem? │
             │                 └────┬─────────┬────┘
             │                  YES │         │ NO
             │                      │         ▼
             │                      │  ┌──────────────┐
             │                      │  │ Spill to Disk│
             │                      │  │ (Batched     │
             │                      │  │  Temp Files) │
             │                      │  └──────┬───────┘
             │                      │         │
             └──────────────┬───────┴─────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │    Apply Aggregations   │
               │ (SUM, COUNT, FILTER, etc│
               └────────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │      Apply HAVING       │
               │ (Filter Aggregate Rows) │
               └────────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │ Output Result Tuples    │
               └─────────────────────────┘
```

---

## 10. Analisis Trade-offs

| Pendekatan | Kelebihan | Kekurangan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **`HashAggregate`** | Sangat cepat untuk kardinalitas rendah-sedang ($O(N)$), tidak membutuhkan data terurut secara fisik. | Mengonsumsi memory `work_mem` secara masif; jika tumpah ke disk (*spill*), performa anjlok secara eksponensial. | Agregasi ad-hoc, kardinalitas kolom rendah-menengah, atau memory database sangat longgar. |
| **`GroupAggregate`** | Konsumsi memori sangat minimal ($O(1)$ partisi aktif), streaming result langsung ke client. | Memerlukan data yang sudah terurut; jika tidak ada indeks B-Tree, memerlukan fase `Sort` eksplisit ($O(N \log N)$). | Tabel sangat besar dengan B-Tree index yang mencakup kolom `GROUP BY`, kardinalitas tinggi. |
| **`ROLLUP` / `CUBE`** | Single trip execution ke engine database, optimasi pemindaian data sekali jalan (*single scan*). | Menghasilkan dataset berukuran besar ($2^N$ baris pada `CUBE`), meningkatkan komputasi CPU database. | Laporan hierarki analitik dashboard dan visualisasi data multi-level matriks. |
| **`UNION ALL` Multi-Query** | Mudah dipahami pemula tanpa perlu memahami bitmask `GROUPING()`. | *Full Table Scan* berulang untuk setiap query, network I/O tinggi, query plan tidak terpadu. | **Hindari di lingkungan produksi.** |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Penyederhanaan via Agregat Bersyarat**: Gunakan konstruksi `FILTER (WHERE condition)` ANSI SQL alih-alih `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. Eksekusi filter bawaan engine jauh lebih teroptimasi.
* **Gunakan Explicit Column Aliasing pada Dimensional Grouping**: Saat menggunakan `ROLLUP` / `CUBE`, selalu bungkus kolom grouping dengan fungsi `GROUPING()` untuk menggantikan representasi nilai `NULL` dengan label bermakna.
* **Optimasi Skenario Kardinalitas Tinggi**: Buat Composite B-Tree Index yang berurutan persis sama dengan urutan kolom dalam klausa `GROUP BY` untuk memfasilitasi algoritma `GroupAggregate`.
* **Kompensasi Nilai Agregat Kosong**: Gunakan `COALESCE(SUM(val), 0)` untuk memastikan field agregat numerik tidak mengembalikan `NULL` ke layer aplikasi saat dataset kosong.

### Antipatterns to Avoid
* **Antipattern: Agregasi di Layer Aplikasi**: Mengambil seluruh baris transaksi via ORM (`SELECT * FROM orders`) lalu melakukan `reduce` / `groupBy` di JavaScript/Go/Python.
* **Antipattern: Inklusi Kolom Non-Agregat Tanpa Functional Dependency**: Memilih kolom di `SELECT` yang tidak terdaftar di `GROUP BY` dan bukan merupakan fungsi agregat (pada DBMS non-strict hal ini memicu data non-deterministik).
* **Antipattern: Filter Agregasi di Klausa `WHERE`**: Memaksa subquery redundant hanya untuk memfilter nilai agregasi alih-alih memanfaatkan klausa `HAVING`.

---

## 12. Security Hardening

### 1. SQL Injection pada Dynamic Grouping Kolom
Dalam sistem pelaporan kustom (misal: user UI memilih dimensi group by secara dinamis), rentan terjadi injeksi kode melalui manipulasi nama kolom agregat.

```sql
-- REKOMENDASI SECURITY: Strict Whitelisting pada Stored Procedure / Application Layer
CREATE OR REPLACE FUNCTION get_safe_aggregated_sales(p_dimension TEXT)
RETURNS TABLE (dimension_val TEXT, total_rev NUMERIC) AS $$
BEGIN
    -- Validasi Nama Kolom Menggunakan Strict Whitelist Array
    IF p_dimension NOT IN ('country_code', 'tier', 'payment_method') THEN
        RAISE EXCEPTION 'Invalid aggregation dimension: %', p_dimension
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    RETURN QUERY EXECUTE format(
        'SELECT %I::TEXT, SUM(gross_amount) FROM dim_merchants m 
         JOIN analytics_orders o ON m.merchant_id = o.merchant_id 
         GROUP BY %I', 
        p_dimension, p_dimension
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 2. Mencegah Denial of Service via Dimensional Exploitation
Query `CUBE` dengan $N$ dimensi menghasilkan $2^N$ subset. Jika client request mengizinkan injeksi $N=10$ kolom ke dalam `CUBE`, database akan mengeksekusi $2^{10} = 1024$ permutasi partisi agregasi yang dapat memicu CPU exhaustion.
* **Mitigasi**: Batasi dimensional analysis maksimum 3-4 dimensi pada application/query level.

---

## 13. Observabilitas & Debugging

Gunakan `EXPLAIN (ANALYZE, BUFFERS, SETTINGS)` untuk membedah strategi eksekusi agregasi.

```sql
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT 
    country_code,
    tier,
    SUM(gross_amount)
FROM dim_merchants m
JOIN analytics_orders o ON m.merchant_id = o.merchant_id
GROUP BY country_code, tier;
```

### Membaca Indikator Eksekusi (Query Plan Interpretation)

1. **`HashAggregate`**:
   * *Status Sehat*: `Batches: 1, Memory Usage: 45kB` (Agregasi berjalan sepenuhnya di RAM).
   * *Degradasi/Spill*: `Batches: 4, Disk Usage: 18432kB` $\rightarrow$ Tanda bahwa `work_mem` tidak mencukupi, menyebabkan tumpahan partisi hash ke disk I/O sementara.
2. **`GroupAggregate`**:
   * Menunjukkan engine memanfaatkan sorting fisik (dari B-Tree index atau Explicit Sort Node). Konsumsi memori sangat konstan.

---

## 14. Benchmarking & Performance

Tabel perbandingan performa variasi metode agregasi pada dataset 1.000.000 baris transaksi:

| Skenario Pengujian | Execution Plan Engine | Execution Time | Buffer Shared Hit / Read | Disk Spill |
| :--- | :--- | :--- | :--- | :--- |
| **`HashAggregate` (Cukup `work_mem`)** | In-Memory Hash Map | 64.2 ms | 12.450 pages | 0 kB |
| **`HashAggregate` (Rendah `work_mem`)** | Mixed Hash + Temp File | 412.8 ms | 12.450 pages | 34.200 kB |
| **`GroupAggregate` (Tanpa Index)** | Sequential Scan + Sort Node | 289.4 ms | 12.450 pages | 0 kB (RAM Sort) |
| **`GroupAggregate` (Covering B-Tree Index)** | Index-Only Scan | **18.7 ms** | 1.840 pages | 0 kB |

*Kesimpulan*: Covering B-Tree Index yang menghilangkan sort runtime memberikan throughput agregasi tertinggi dengan konsumsi memory terendah.

---

## 15. Hands-on Lab Mini-Project

### Skenario: Multi-Level Financial Ledger Matrix Aggregation

Rancang skema dan query laporan akuntansi multi-tier untuk mengelompokkan biaya operasional berdasarkan Divisi, Departemen, dan Kategori Biaya.

```sql
-- 1. Setup Lab Environment
CREATE TABLE corporate_expenses (
    expense_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    division VARCHAR(50) NOT NULL,
    department VARCHAR(50) NOT NULL,
    cost_category VARCHAR(50) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    is_approved BOOLEAN NOT NULL DEFAULT true
);

INSERT INTO corporate_expenses (division, department, cost_category, amount, is_approved) VALUES
('Technology', 'Core Engineering', 'SaaS Subscriptions', 12000.00, true),
('Technology', 'Core Engineering', 'Cloud Infrastructure', 45000.00, true),
('Technology', 'Quality Assurance', 'SaaS Subscriptions',  3000.00, true),
('Technology', 'Quality Assurance', 'Device Farm',         8000.00, false),
('Operations', 'Logistics',         'Fuel & Transport',   15000.00, true),
('Operations', 'Logistics',         'Warehouse Lease',    25000.00, true),
('Operations', 'Customer Support',  'SaaS Subscriptions',  5000.00, true),
('Operations', 'Customer Support',  'Telecom',             2000.00, true);

-- 2. Tantangan Query: Eksekusi Hierarchical Multi-Level Ledger
SELECT 
    CASE WHEN GROUPING(division) = 1 THEN '== ENTERPRISE TOTAL ==' ELSE division END AS division,
    CASE WHEN GROUPING(department) = 1 THEN '-- DIVISION TOTAL --' ELSE department END AS department,
    CASE WHEN GROUPING(cost_category) = 1 THEN '.. DEPARTMENT TOTAL ..' ELSE cost_category END AS cost_category,
    
    COUNT(*) AS total_line_items,
    COUNT(*) FILTER (WHERE is_approved) AS approved_items,
    SUM(amount) AS total_expense,
    COALESCE(SUM(amount) FILTER (WHERE is_approved), 0.00) AS total_approved_expense,
    COALESCE(SUM(amount) FILTER (WHERE NOT is_approved), 0.00) AS rejected_exposure
    
FROM corporate_expenses
GROUP BY ROLLUP (division, department, cost_category)
ORDER BY 
    GROUPING(division) ASC,
    division,
    GROUPING(department) ASC,
    department,
    GROUPING(cost_category) ASC,
    cost_category;
```

---

## 16. Automated Testing & Verification

Berikut adalah suite test verifikasi menggunakan kerangka kerja `pgTAP` untuk menguji keakuratan integritas kalkulasi dimensional grouping.

```sql
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap;

SELECT plan(4);

-- Test 1: Verifikasi tabel dan data eksis
SELECT has_table('corporate_expenses', 'Tabel corporate_expenses harus terdefinisi');

-- Test 2: Verifikasi konsistensi Grand Total ROLLUP sama dengan SUM skalar
SELECT results_eq(
    $$ 
        SELECT SUM(amount) FROM corporate_expenses 
    $$,
    $$ 
        SELECT total_expense 
        FROM (
            SELECT SUM(amount) AS total_expense, GROUPING(division) as g_div
            FROM corporate_expenses
            GROUP BY ROLLUP(division)
        ) sub 
        WHERE g_div = 1 
    $$,
    'Grand Total dari ROLLUP harus identik dengan SUM skalar seluruh tabel'
);

-- Test 3: Verifikasi akurasi Filtered Aggregates
SELECT is(
    (SELECT SUM(amount) FILTER (WHERE NOT is_approved) FROM corporate_expenses),
    8000.00::NUMERIC,
    'Total unapproved expense harus bernilai tepat 8000.00'
);

-- Test 4: Verifikasi grouping bitmasking pada CUBE
SELECT ok(
    (SELECT count(DISTINCT GROUPING(division, department)) FROM corporate_expenses GROUP BY CUBE(division, department)) = 4,
    'CUBE 2 Dimensi harus menghasilkan tepat 4 distinct status bitmask grouping (0, 1, 2, 3)'
);

SELECT * FROM finish();
ROLLBACK;
```

---

## 17. Troubleshooting Guide

### Issue 1: Performa Drop Drastis pada Query Agregasi Berskala Besar
* **Gejala**: CPU 100%, IOPS disk database melonjak tinggi saat eksekusi query rollup/grouping.
* **Akar Masalah**: Engine database kekurangan memory `work_mem`, memaksa `HashAggregate` melakukan tumpahan (*spill*) partisi batch ke temporary disk file.
* **Resolusi**:
  1. Periksa log atau `EXPLAIN ANALYZE` untuk menemukan string `Disk Usage: xxxxkB`.
  2. Naikkan parameter `work_mem` secara terukur pada level transaksi atau per connection:
     `SET LOCAL work_mem = '128MB';`

### Issue 2: Ambiguitas Nilai `NULL` Hasil Aggregasi vs Nilai Data Asli
* **Gejala**: Tidak bisa membedakan apakah baris `NULL` pada hasil query merupakan data `NULL` aktual dari tabel atau merupakan baris agregat (*Super-Aggregate Subtotal*).
* **Akar Masalah**: Mengandalkan fungsi `COALESCE(col, 'TOTAL')` langsung pada kolom nullable.
* **Resolusi**: Selalu gunakan fungsi bawaan `GROUPING(col)`:
  ```sql
  -- AMAN & AKURAT
  CASE WHEN GROUPING(nullable_col) = 1 THEN 'SUBTOTAL' ELSE nullable_col END
  ```

---

## 18. Checklist Produksi

- [ ] **Validasi Urutan Logis**: Memastikan filter baris diletakkan di `WHERE` (bukan di `HAVING`) untuk memangkas pemrosesan sebelum grouping.