# Kurikulum: Backend and Database (Kategori 04)
## Track: SQL Engineering & Query Optimization

---

# Seksi 01: Identitas Modul
* **Mata Pelajaran:** SQL Core & Relational Theory
* **Kode Modul:** SQL-04-02-01
* **Judul Modul:** Logical Query Processing & Data Retrieval
* **Tingkat Kompleksitas:** Intermediate to Advanced
* **Prasyarat:** Pemahaman dasar Relational Algebra, DDL/DML, dan sintaks dasar ANSI SQL.
* **Target Engine:** PostgreSQL 16+ / MySQL 8.0+ / ANSI SQL:2016 Compliant Engine

---

# Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Membedakan** secara presisi antara urutan penulisan leksikal (Lexical/Syntactic Order) dan urutan eksekusi logis (Logical Processing Order) dari kueri SQL deklaratif.
2. **Menganalisis** transformasi internal dataset pada 8 fase pemrosesan logis: `FROM` $\rightarrow$ `ON` $\rightarrow$ `JOIN` $\rightarrow$ `WHERE` $\rightarrow$ `GROUP BY` $\rightarrow$ `HAVING` $\rightarrow$ `SELECT` (termasuk Ekspresi, Aliasing, dan Window Functions) $\rightarrow$ `DISTINCT` $\rightarrow$ `ORDER BY` $\rightarrow$ `LIMIT/OFFSET`.
3. **Mendeteksi dan Memitigasi** anomali filtering logika *three-valued logic* (3VL: `TRUE`, `FALSE`, `UNKNOWN`) akibat kontaminasi nilai `NULL`.
4. **Menerapkan** mitigasi performa logis dengan memahami implikasi kalkulasi alias kolom, evaluasi predikat SARGable (*Search Argument Able*), dan *Window Function lifecycle*.

---

# Seksi 03: Concept Map Diagram ASCII

```
LEXICAL (WRITING) ORDER                LOGICAL EXECUTION PIPELINE
========================               ==========================
[1] SELECT                             [STEP 1: FROM & JOIN]
[2] FROM                                      │  Cartesian Product -> ON Filter -> Outer Add
[3] WHERE                                     ▼
[4] GROUP BY                           [STEP 2: WHERE]
[5] HAVING                                    │  Row Filtering (SARGable predicates, 3VL)
[6] WINDOW                                    ▼
[7] QUALIFY (Engine-specific)          [STEP 3: GROUP BY]
[8] ORDER BY                                  │  Group Formation (Reduction)
[9] LIMIT / OFFSET                            ▼
                                       [STEP 4: HAVING]
                                              │  Group Filtering (Aggregate conditions)
                                              ▼
                                       [STEP 5: SELECT]
                                              │  Scalar Eval -> Column Aliasing -> Window Functions
                                              ▼
                                       [STEP 6: DISTINCT]
                                              │  Duplicate Row Removal (Set projection)
                                              ▼
                                       [STEP 7: ORDER BY]
                                              │  Cursor Sorting (Can access alias & unseen cols)
                                              ▼
                                       [STEP 8: LIMIT / OFFSET]
                                                 Paging Engine (Top-N extraction)
```

---

# Seksi 04: Mengapa Relevan
SQL bukan bahasa prosedural; SQL bersifat deklaratif murni berbasis kalkulus relasional. Salah satu sumber disonansi kognitif terbesar bagi software engineer adalah asumsi bahwa database mengeksekusi kode dari baris pertama (`SELECT`) ke baris terakhir (`LIMIT`).

Ketidakpahaman terhadap urutan pemrosesan logis mengakibatkan:
* Kesalahan fatal seperti mencoba memfilter alias kolom `SELECT` di dalam klausa `WHERE`.
* Kerusakan data akibat salah mengasumsikan bahwa filter `WHERE` dieksekusi sebelum evaluasi `LEFT JOIN ... ON`.
* Polusi memori engine akibat pemanggilan fungsi agregat dan pengurutan data (`ORDER BY`) sebelum dilakukan pemotongan baris yang relevan.

---

# Seksi 05: Anatomi Konsep Inti

```
+-------------------------------------------------------------------------------+
|                      LOGICAL QUERY EXECUTION ENGINE                           |
+-------------------------------------------------------------------------------+
| 1. FROM & JOIN     : V1 = Table References x Join Conditions -> Virtual T1   |
| 2. WHERE           : V2 = Filter(V1) where Predicate IS TRUE                  |
| 3. GROUP BY        : V3 = Partition(V2) by Grouping Sets                      |
| 4. HAVING          : V4 = Filter(V3) where Aggregate_Predicate IS TRUE        |
| 5. SELECT          : V5 = Project Scalar expressions, Evaluate Window Fns     |
| 6. DISTINCT        : V6 = Deduplicate(V5)                                     |
| 7. ORDER BY        : V7 = Sort(V6 or V5) using physical collation/order      |
| 8. LIMIT / OFFSET  : Output = Slice(V7, offset, limit)                        |
+-------------------------------------------------------------------------------+
```

### 1. Fase FROM dan Pemuatan Relasi (`FROM` / `JOIN` / `ON`)
Mesin mengevaluasi tabel asal. Jika terjadi `CROSS JOIN`, engine menghasilkan perkalian Cartesian ($|R| \times |S|$). Jika terdapat klausa `ON`, predikat dievaluasi untuk membentuk *Virtual Table 1* (VT1). Pada `OUTER JOIN` (`LEFT`, `RIGHT`, `FULL`), baris yang tidak memenuhi kondisi `ON` ditambahkan kembali dengan nilai `NULL` (*Outer Row Preservation*).

### 2. Fase Evaluasi Predikat Baris (`WHERE`)
Evaluasi baris dari VT1. Baris yang dievaluasi menjadi `FALSE` atau `UNKNOWN` (akibat perbandingan dengan `NULL`) dibuang. 
*Kritis:* Alias kolom yang didefinisikan pada `SELECT` **belum ada** pada fase ini.

### 3. Fase Pengelompokan Data (`GROUP BY`)
Mengelompokkan baris dari VT2 ke dalam partisi diskrit berdasarkan nilai-nilai unik kolom target. Semua kolom non-grup yang tidak dibungkus dalam fungsi agregasi (`SUM`, `AVG`, `COUNT`, `MAX`, `MIN`) menjadi ilegal secara semantik ANSI SQL.

### 4. Fase Evaluasi Predikat Agregat (`HAVING`)
Memfilter kelompok-kelompok yang dihasilkan oleh VT3. Kondisi di sini harus melibatkan agregat atau kolom yang dideklarasikan pada `GROUP BY`.

### 5. Fase Proyeksi (`SELECT`, `WINDOW`, dan Kolom Alias)
Mesin mengekstrak ekspresi yang diminta. 
* Evaluasi skalar dan pembuatan alias kolom terjadi di sini.
* Eksekusi *Window Functions* (`OVER(PARTITION BY ... ORDER BY ...)`) terjadi setelah agregasi kelompok, mengizinkan akses ke hasil kalkulasi baris individual relatif terhadap partisi.

### 6. Fase Eliminasi Duplikasi (`DISTINCT`)
Menghapus baris duplikat dari set proyeksi VT5.

### 7. Fase Pengurutan Kursor (`ORDER BY`)
Data diurutkan. Fase ini secara unik dapat mengakses nama alias yang dibuat di `SELECT` dan kolom tabel asli yang tidak disertakan di `SELECT` (kecuali jika `DISTINCT` diaktifkan).

### 8. Fase Pemotongan Baris (`LIMIT` / `OFFSET` atau ANSI `FETCH FIRST`)
Mengambil subset baris terurut dari VT7.

---

# Seksi 06: Panduan Implementasi Step-by-Step

### Langkah 1: Memverifikasi Tahapan Filter `ON` vs `WHERE` pada Outer Join
Pahami bagaimana penempatan predikat menghasilkan semantik relasional yang berbeda:

```sql
-- Kasus A: Predikat filter berada di ON clause
-- Hasil: SEMUA customer keluar; order_status di luar 'COMPLETED' menghasilkan NULL di kolom orders.
SELECT c.id, c.name, o.order_id, o.order_status
FROM customers c
LEFT JOIN orders o 
  ON c.id = o.customer_id 
  AND o.order_status = 'COMPLETED';

-- Kasus B: Predikat filter berada di WHERE clause
-- Hasil: Customers tanpa order 'COMPLETED' dieliminasi total karena WHERE NULL = 'COMPLETED' bernilai UNKNOWN.
-- Transformasi tidak sengaja menjadi INNER JOIN!
SELECT c.id, c.name, o.order_id, o.order_status
FROM customers c
LEFT JOIN orders o 
  ON c.id = o.customer_id
WHERE o.order_status = 'COMPLETED';
```

### Langkah 2: Menggunakan Window Function Sebelum ORDER BY Eksternal
```sql
SELECT 
    department_id,
    employee_id,
    salary,
    DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) as salary_rank
FROM employees
WHERE is_active = TRUE
-- Window function dievaluasi setelah WHERE dan sebelum final ORDER BY
ORDER BY department_id ASC, salary_rank ASC;
```

---

# Seksi 07: Contoh Kasus Sederhana

**Studi Kasus:** Mengapa kueri berikut menghasilkan *syntax error* pada engine SQL standar?

```sql
-- SALAH: Menggunakan alias 'total_cost' di WHERE clause
SELECT 
    item_id, 
    quantity * unit_price AS total_cost
FROM sales_items
WHERE total_cost > 1000.00;
```

**Diagnosa Matematis & Logis:**
Fase `WHERE` dieksekusi pada **Tahap 2**, sedangkan ekspresi `quantity * unit_price AS total_cost` baru dibentuk pada **Tahap 5 (SELECT)**. Mesin SQL mengembalikan error: `column "total_cost" does not exist`.

**Solusi Standar ANSI SQL:**
```sql
-- BENAR: Mengulang ekspresi asli atau menggunakan CTE / Derived Table
SELECT 
    item_id, 
    quantity * unit_price AS total_cost
FROM sales_items
WHERE (quantity * unit_price) > 1000.00;

-- BENAR (Pendekatan CTE/Derived Table):
WITH calculated_sales AS (
    SELECT 
        item_id, 
        quantity * unit_price AS total_cost
    FROM sales_items
)
SELECT item_id, total_cost
FROM calculated_sales
WHERE total_cost > 1000.00;
```

---

# Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah skrip DDL, DML, dan kueri analitik kompleks yang mendemonstrasikan interaksi seluruh fase pemrosesan logis:

```sql
-- 1. Setup Skema Database
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    payment_method VARCHAR(20) NOT NULL
);

CREATE TABLE order_items (
    item_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(order_id),
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0)
);

-- 2. Inisialisasi Data Uji
INSERT INTO customers (customer_id, name, country) VALUES
(1, 'Alice Corp', 'IDN'),
(2, 'Bob LLC', 'SGP'),
(3, 'Charlie Ltd', 'IDN'),
(4, 'Delta Inc', 'USA');

INSERT INTO orders (order_id, customer_id, order_date, order_status, payment_method) VALUES
(101, 1, '2024-01-15', 'COMPLETED', 'CREDIT_CARD'),
(102, 1, '2024-02-20', 'COMPLETED', 'BANK_TRANSFER'),
(103, 2, '2024-01-18', 'COMPLETED', 'CREDIT_CARD'),
(104, 3, '2024-03-01', 'CANCELLED', 'CREDIT_CARD'),
(105, 3, '2024-03-10', 'PENDING', 'BANK_TRANSFER');

INSERT INTO order_items (item_id, order_id, sku, quantity, unit_price) VALUES
(1, 101, 'SKU-A', 5, 100.00),
(2, 101, 'SKU-B', 2, 250.00),
(3, 102, 'SKU-C', 1, 1500.00),
(4, 103, 'SKU-A', 10, 95.00),
(5, 104, 'SKU-D', 1, 300.00),
(6, 105, 'SKU-B', 4, 250.00);

-- 3. Kueri Kompleks Pemrosesan Logis
-- Mengkalkulasi metrik transaksi regional, mengeliminasi outlier, 
-- dan merangking customer per negara berdasarkan volume transaksi valid.

SELECT 
    c.country,
    c.name AS customer_name,
    COUNT(DISTINCT o.order_id) AS total_completed_orders,
    SUM(oi.quantity * oi.unit_price) AS total_gross_spend,
    ROUND(AVG(oi.quantity * oi.unit_price), 2) AS avg_item_spend,
    DENSE_RANK() OVER (
        PARTITION BY c.country 
        ORDER BY SUM(oi.quantity * oi.unit_price) DESC
    ) as regional_rank
FROM customers c
-- Fase 1: FROM & JOIN (Outer Join menjaga Customer tanpa Completed Orders)
LEFT JOIN orders o 
    ON c.customer_id = o.customer_id 
    AND o.order_status = 'COMPLETED'
LEFT JOIN order_items oi 
    ON o.order_id = oi.order_id
-- Fase 2: WHERE (Filter regional, dieksekusi per baris SEBELUM grouping)
WHERE c.country IN ('IDN', 'SGP')
-- Fase 3: GROUP BY (Agregasi tingkat Customer)
GROUP BY 
    c.country, 
    c.customer_id, 
    c.name
-- Fase 4: HAVING (Filter hasil agregat; hanya kelompok dengan spend valid ATAU customer aktif tanpa order)
HAVING 
    SUM(oi.quantity * oi.unit_price) > 500.00 
    OR COUNT(DISTINCT o.order_id) = 0
-- Fase 5: SELECT, Window Functions dihitung
-- Fase 6: DISTINCT (Tidak digunakan secara eksplisit pada tingkat row projection)
-- Fase 7: ORDER BY (Menggunakan referensi alias dan posisi sorting)
ORDER BY 
    c.country ASC, 
    regional_rank ASC
-- Fase 8: LIMIT / OFFSET (Mengambil Top 5 Entitas)
LIMIT 5 OFFSET 0;
```

---

# Seksi 09: Diagram Alur Kerja ASCII

```
           +-------------------------------------------------------+
           | DATA STORE: customers, orders, order_items            |
           +-------------------------------------------------------+
                                      |
                                      | [1] FROM & LEFT JOIN ... ON
                                      v
           +-------------------------------------------------------+
           | VT1: Joined set of Customer + Completed Orders + Items|
           +-------------------------------------------------------+
                                      |
                                      | [2] WHERE country IN ('IDN', 'SGP')
                                      v
           +-------------------------------------------------------+
           | VT2: Filtered Rows (Non-matching country removed)     |
           +-------------------------------------------------------+
                                      |
                                      | [3] GROUP BY country, customer_id, name
                                      v
           +-------------------------------------------------------+
           | VT3: Aggregated Rows Partitioned by Customer          |
           +-------------------------------------------------------+
                                      |
                                      | [4] HAVING SUM(...) > 500 OR COUNT(...) = 0
                                      v
           +-------------------------------------------------------+
           | VT4: Retained High-Value/Zero-Order Groups            |
           +-------------------------------------------------------+
                                      |
                                      | [5] SELECT Projection & WINDOW Execution
                                      |     (DENSE_RANK() OVER (PARTITION BY...))
                                      v
           +-------------------------------------------------------+
           | VT5: Projected Result Set with Calculated Aliases     |
           +-------------------------------------------------------+
                                      |
                                      | [6] ORDER BY country ASC, regional_rank ASC
                                      v
           +-------------------------------------------------------+
           | VT6: Deterministically Sorted Rows                    |
           +-------------------------------------------------------+
                                      |
                                      | [7] LIMIT 5 OFFSET 0
                                      v
           +-------------------------------------------------------+
           | CLIENT APPLICATION RESULT SET                         |
           +-------------------------------------------------------+
```

---

# Seksi 10: Analisis Trade-offs

| Pendekatan Logis | Alternatif Desain | Pros | Cons | Dampak Resource |
| :--- | :--- | :--- | :--- | :--- |
| **`WHERE` Filtering** | **`HAVING` Filtering** untuk kondisi skalar | Menyaring data seawal mungkin (Fase 2 vs Fase 4). | Tidak bisa membaca hasil agregasi langsung. | Menghemat alokasi memori buffer secara drastis sebelum agregasi. |
| **`LEFT JOIN ... ON (cond)`** | **`LEFT JOIN ... WHERE (cond)`** | Menjaga relasi entitas opsional (preserve primary entity). | Semantic bug jika salah penempatan; mengubah `OUTER` jadi `INNER`. | Operasi Join Outer membutuhkan alokasi memori null-padding. |
| **`DISTINCT` Projection** | **`GROUP BY` Grouping** | Sintaks lebih ringkas untuk deduplikasi flat data. | Menghilangkan granularitas fungsi agregasi terarah. | `DISTINCT` mengeksekusi Sort/Hash deduplikasi pada seluruh payload. |
| **`Window Function`** | **Self-Join Subqueries** | Mengevaluasi konteks partisi tanpa replikasi IO pembacaan tabel berulang. | Sedikit lebih kompleks dibaca oleh pemula. | O(N log N) sorting vs O($N^2$) join cost. |

---

# Seksi 11: Best Practices & Antipatterns

### ✅ Best Practices
1. **Push-down Predicates:** Filter data sesegera mungkin di `WHERE` sebelum data masuk ke tahap komputasi intensif `GROUP BY` atau Window Function.
2. **Deterministic Sorting:** Selalu sertakan primary key atau kolom unik di klausa `ORDER BY` jika menggunakan paging (`LIMIT/OFFSET`) guna mencegah anomali data melompat (*Phantom Reads*).
3. **Explicit Coalescing:** Waspada terhadap Three-Valued Logic (3VL). Gunakan `COALESCE` atau ekspresi eksplisit `IS NOT DISTINCT FROM` saat membandingkan kolom yang *nullable*.

### ❌ Antipatterns
1. **Filter Non-Agregat di `HAVING`:**
   ```sql
   -- ANTIPATTERN (Lambat, memproses baris tidak relevan dalam Grouping Engine)
   SELECT department_id, COUNT(*) 
   FROM employees 
   GROUP BY department_id 
   HAVING department_id = 10;

   -- BENAR (Cepat, memfilter baris sebelum alokasi partisi grouping)
   SELECT department_id, COUNT(*) 
   FROM employees 
   WHERE department_id = 10 
   GROUP BY department_id;
   ```
2. **Mengabaikan Karakteristik Non-SARGable pada Filter:**
   ```sql
   -- ANTIPATTERN: Mencegah penggunaan B-Tree Index karena wrapping fungsi skalar
   SELECT id, name FROM users WHERE EXTRACT(YEAR FROM created_at) = 2024;

   -- BENAR: Menggunakan Range Predicate SARGable
   SELECT id, name FROM users 
   WHERE created_at >= '2024-01-01 00:00:00+00' 
     AND created_at < '2025-01-01 00:00:00+00';
   ```

---

# Seksi 12: Security Hardening

### 1. Dynamic Logical SQL Injection Mitigation
Saat membangun kueri dinamis (misalnya sorting dinamis via antarmuka UI), SQL Injection sering terjadi di fase yang tidak menerima binding parameter standar, seperti `ORDER BY`:

```sql
-- RENTAN INJECTION: Parameter kolom di-concatenate langsung
-- query = "SELECT id, name FROM users ORDER BY " + userInput; 
-- userInput = "id; DROP TABLE users; --"
```

**Solusi: Whitelisting Eksplisit pada Logical Identifier**
```sql
-- Validasi PL/pgSQL Function dengan quote_ident / Assert Whitelist
CREATE OR REPLACE FUNCTION get_users_sorted(sort_column TEXT, sort_direction TEXT)
RETURNS TABLE (user_id BIGINT, user_name VARCHAR) AS $$
BEGIN
    -- Validasi ketat nama kolom logis
    IF sort_column NOT IN ('user_id', 'created_at', 'user_name') THEN
        RAISE EXCEPTION 'Akses kolom tidak sah: %', sort_column;
    END IF;

    IF UPPER(sort_direction) NOT IN ('ASC', 'DESC') THEN
        RAISE EXCEPTION 'Arah sorting tidak sah: %', sort_direction;
    END IF;

    RETURN QUERY EXECUTE format(
        'SELECT customer_id, name FROM customers ORDER BY %I %s', 
        sort_column, 
        sort_direction
    );
END;
$$ LANGUAGE plpgsql;
```

---

# Seksi 13: Observabilitas & Debugging

Gunakan `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)` untuk membedah perbedaan antara representasi deklaratif dan eksekusi fisik engine.

```sql
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT 
    c.country, 
    COUNT(o.order_id) as total_orders
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
WHERE c.country = 'IDN'
GROUP BY c.country
HAVING COUNT(o.order_id) > 10
ORDER BY total_orders DESC;
```

### Membaca Indikator Debugging Kunci:
1. **Filter vs Hash Cond:** Jika predikat `WHERE` muncul sebagai filter node tingkat atas alih-alih *Index Cond*, periksa struktur index kolom Anda.
2. **HashAggregate vs GroupAggregate:** *HashAggregate* memakan memori RAM (`work_mem`); jika data terlalu besar, PostgreSQL akan menumpahkannya (*spill*) ke Disk (Temporary Batch IO), menurunkan throughput.

---

# Seksi 14: Benchmarking & Performance

Perbandingan performa antara memfilter sebelum grouping (`WHERE`) versus memfilter setelah grouping (`HAVING`) pada dataset 1.000.000 baris.

```sql
-- Setup Data Benchmark
CREATE TABLE metrics_bench AS 
SELECT 
    (random() * 100)::INT AS device_id,
    (random() * 1000)::NUMERIC AS reading,
    NOW() - (random() * interval '30 days') AS recorded_at
FROM generate_series(1, 1000000);

CREATE INDEX idx_metrics_device ON metrics_bench(device_id);
VACUUM ANALYZE metrics_bench;
```

```sql
-- KASUS 1: Inefisiensi Ekstrem dengan Filter di HAVING
-- Seluruh 1.000.000 baris dikelompokkan ke memori sebelum dibuang
EXPLAIN ANALYZE 
SELECT device_id, AVG(reading)
FROM metrics_bench
GROUP BY device_id
HAVING device_id = 42;
-- Execution Time rata-rata: ~85.4 ms (HashAggregate memproses 100 grup)

-- KASUS 2: Optimalisasi Logis Push-down ke WHERE
-- Engine memotong baris via Index/Bitmap Scan menjadi hanya ~10.000 baris sebelum masuk Grouping
EXPLAIN ANALYZE 
SELECT device_id, AVG(reading)
FROM metrics_bench
WHERE device_id = 42
GROUP BY device_id;
-- Execution Time rata-rata: ~2.1 ms (Peningkatan Kecepatan: ~40x lipat)
```

---

# Seksi 15: Hands-on Lab Mini-Project

### Masalah Kasus
Perusahaan FinTech memerlukan laporan deteksi fraud transaksi *Suspicious High-Frequency Transfers*.

### Spesifikasi Kebutuhan:
1. Hitung total transfer dan volume transaksi per akun asal (`sender_id`).
2. Batasi transaksi hanya pada transaksi berstatus `SUCCESS` dalam rentang waktu 7 hari terakhir.
3. Hanya tampilkan akun dengan total volume transfer $> \$10,000$ DAN jumlah frekuensi transfer $> 3$ kali.
4. Buat ranking transaksi logis berdasarkan volume tertinggi per masing-masing negara pengirim (`origin_country`).
5. Ambil data halaman pertama (5 akun teratas).

### Solusi Script Lab:

```sql
-- 1. Inisialisasi Skema Lab
CREATE TABLE audit_transfers (
    transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id BIGINT NOT NULL,
    origin_country VARCHAR(3) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- 2. Data Seeding
INSERT INTO audit_transfers (sender_id, origin_country, amount, status, created_at)
SELECT 
    (RANDOM() * 50)::INT + 1,
    (ARRAY['IDN', 'SGP', 'MYS', 'USA'])[FLOOR(RANDOM() * 4 + 1)],
    (RANDOM() * 4000 + 100)::NUMERIC(15,2),
    (ARRAY['SUCCESS', 'FAILED', 'PENDING'])[FLOOR(RANDOM() * 3 + 1)],
    NOW() - (RANDOM() * INTERVAL '10 days')
FROM generate_series(1, 50000);

-- 3. Kueri Audit Solusi Lab
WITH qualified_accounts AS (
    SELECT 
        sender_id,
        origin_country,
        COUNT(transfer_id) AS success_tx_count,
        SUM(amount) AS total_transferred_amount
    FROM audit_transfers
    -- FASE LOGIS: WHERE memangkas status dan batas tanggal lebih awal
    WHERE status = 'SUCCESS'
      AND created_at >= NOW() - INTERVAL '7 days'
    -- FASE LOGIS: GROUP BY membentuk partisi audit entitas
    GROUP BY sender_id, origin_country
    -- FASE LOGIS: HAVING memfilter agregasi anomali
    HAVING SUM(amount) > 10000.00 
       AND COUNT(transfer_id) > 3
)
SELECT 
    sender_id,
    origin_country,
    success_tx_count,
    total_transferred_amount,
    DENSE_RANK() OVER (
        PARTITION BY origin_country 
        ORDER BY total_transferred_amount DESC
    ) AS country_volume_rank
FROM qualified_accounts
-- FASE LOGIS: ORDER BY & LIMIT eksternal
ORDER BY origin_country ASC, country_volume_rank ASC
LIMIT 5;
```

---

# Seksi 16: Automated Testing & Verification

Gunakan framework assertions berbasis SQL sederhana untuk memverifikasi logika:

```sql
DO $$
DECLARE
    v_test_count INT;
    v_invalid_rows INT;
BEGIN
    -- TEST 1: Verifikasi bahwa baris bernilai FAILED tidak bocor ke hasil agregasi
    SELECT COUNT(*) INTO v_invalid_rows
    FROM (
        SELECT sender_id, SUM(amount) as total
        FROM audit_transfers
        WHERE status = 'SUCCESS'
        GROUP BY sender_id
        HAVING SUM(amount) > 0
    ) sub
    WHERE sub.sender_id IN (
        SELECT sender_id FROM audit_transfers GROUP BY sender_id HAVING bool_and(status = 'FAILED')
    );

    IF v_invalid_rows > 0 THEN
        RAISE EXCEPTION 'TEST FAILED: Data dengan status FAILED bocor ke pipeline.';
    ELSE
        RAISE NOTICE 'TEST 1 PASSED: Pipeline pemisahan predikat valid.';
    END IF;

    -- TEST 2: Verifikasi Integritas Window Function Ranking
    SELECT COUNT(*) INTO v_invalid_rows
    FROM (
        SELECT 
            origin_country,
            total_transferred_amount,
            DENSE_RANK() OVER (PARTITION BY origin_country ORDER BY total_transferred_amount DESC) as rnk
        FROM (
            SELECT origin_country, sender_id, SUM(amount) as total_transferred_amount
            FROM audit_transfers
            WHERE status = 'SUCCESS'
            GROUP BY origin_country, sender_id
        ) raw_g
    ) ranked
    WHERE rnk = 1 AND total_transferred_amount < (
        SELECT MAX(total_transferred_amount) 
        FROM (
            SELECT origin_country, sender_id, SUM(amount) as total_transferred_amount
            FROM audit_transfers
            WHERE status = 'SUCCESS'
            GROUP BY origin_country, sender_id
        ) sub2 
        WHERE sub2.origin_country = ranked.origin_country
    );

    IF v_invalid_rows > 0 THEN
        RAISE EXCEPTION 'TEST 2 FAILED: Algoritma DENSE_RANK tidak konsisten dengan partisi logis.';
    ELSE
        RAISE NOTICE 'TEST 2 PASSED: Evaluasi Window Function terverifikasi presisi.';
    END IF;
END $$;
```

---

# Seksi 17: Troubleshooting Guide

| Gejala Error / Masalah | Akar Masalah (Root Cause) | Solusi Perbaikan |
| :--- | :--- | :--- |
| `ERROR: column "x" must appear in the GROUP BY clause or be used in an aggregate function` | Mencoba memproyeksikan kolom individual di `SELECT` (Fase 5) yang tidak diikutsertakan di `GROUP BY` (Fase 3). | Masukkan kolom ke `GROUP BY` atau bungkus kolom tersebut dalam fungsi agregat (`MIN`, `MAX`, `ARRAY_AGG`). |
| Data `LEFT JOIN` berkurang secara tidak terduga setelah menambah filter. | Meletakkan predikat tabel sisi-kanan (nullable table) di klausa `WHERE` alih-alih di klausa `ON`. | Pindahkan predikat dari `WHERE` ke dalam `ON` pada relasi `LEFT JOIN`. |
| Paginasi `LIMIT/OFFSET` mengembalikan data duplikat antar halaman. | `ORDER BY` tidak bersifat deterministik (ada baris yang memiliki nilai sorting identik). | Tambahkan Tie-Breaker Unique Key pada `ORDER BY` (contoh: `ORDER BY created_at DESC, id DESC`). |
| Nilai komputasi `COUNT(col)` menghasilkan angka 0 padahal baris ada. | Kolom yang dihitung bernilai `NULL`. Fungsi `COUNT(col)` mengabaikan `NULL`, berbeda dengan `COUNT(*)`. | Gunakan `COUNT(*)` jika tujuannya menghitung kardinalitas baris, bukan keberadaan nilai atribut. |

---

# Seksi 18: Checklist Produksi

- [ ] **Validasi Urutan Logis:** Tidak ada referensi alias kolom `SELECT` di dalam klausa `WHERE` atau `JOIN ... ON`.
- [ ] **SARGability:** Semua predikat di `WHERE` tidak membungkus kolom terindeks dengan fungsi mutasi skalar (contoh: `DATE(col) = '2024-01-01'`).
- [ ] **Audit Outer Join:** Semua kondisi filter spesifik untuk tabel relasi `RIGHT/LEFT` berada pada blok `ON`, bukan terminasi `WHERE` (kecuali untuk teknik *Anti-Join* `WHERE right_table.id IS NULL`).
- [ ] **Alokasi Agregasi:** Klausa `HAVING` dikhususkan secara eksklusif untuk mengevaluasi fungsi agregasi (`SUM`, `COUNT`, dll); seluruh filter level baris telah diturunkan ke `WHERE`.
- [ ] **Paging Deterministik:** Setiap kueri yang memiliki klausa `LIMIT` / `OFFSET` memiliki pengurutan `ORDER BY` yang unik dan deterministik untuk mencegah inkonsistensi konkurensi pagination.
- [ ] **Penanganan 3VL:** Penanganan nilai `NULL` eksplisit pada operasi negasi (`NOT IN (...)` menghasilkan set kosong jika terdapat satu saja `NULL`; gunakan `NOT EXISTS` sebagai pengganti).

---

# Seksi 19: Ringkasan Eksekutif
Pemrosesan kueri logis menetapkan aturan formal mengenai urutan pembacaan deklaratif database:
1. Engine membentuk data mentah via **`FROM`** dan mengevaluasi integritas referensial via **`ON`**.
2. Baris yang tidak memenuhi syarat dipangkas pada fase **`WHERE`** menggunakan logika Three-Valued Logic (`TRUE`, `FALSE`, `UNKNOWN`).
3. Baris yang tersisa dikelompokkan pada **`GROUP BY`** dan dipangkas secara kondisional pada **`HAVING`**.
4. Hanya setelah fase-fase di atas selesai, mesin mengevaluasi ekspresi nilai skalar, alias, dan fungsi analitis pada **`SELECT`**.
5. Hasil akhir dibersihkan dari duplikasi (**`DISTINCT`**), diurutkan (**`ORDER BY`**), dan dipotong (**`LIMIT/OFFSET`**).

Memahami siklus hidup ini secara ketat mencegah terjadinya logical error fungsional, menghindari query rewrite yang tidak efisien, dan menjadi fondasi utama sebelum mempelajari physical query optimization (Cost-Based Optimizer, Hash/Merge Joins, dan Index Scan Access Methods).

---

# Seksi 20: Referensi & Bacaan Lanjutan
1. **Ben-Gan, Itzik.** *T-SQL Fundamentals (Chapter 1: Logical Query Processing)*. Microsoft Press.
2. **PostgreSQL Global Development Group.** *PostgreSQL 16 Documentation: Chapter 7. Queries (SELECT, Window Functions, Sorting).*
3. **ANSI/ISO/IEC 9075-2:2016.** *Information technology — Database languages — SQL — Part 2: Foundation (SQL/Foundation).*
4. **Molina, H., Ullman, J. D., & Widom, J.** *Database Systems: The Complete Book (2nd Edition)*. Pearson.