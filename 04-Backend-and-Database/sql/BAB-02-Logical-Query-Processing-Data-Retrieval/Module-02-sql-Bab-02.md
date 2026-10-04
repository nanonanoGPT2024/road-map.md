# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Logical Query Processing & Advanced Data Retrieval**
**Kategori: 04-Backend-and-Database | Topik: SQL**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Memetakan Alur *Logical Query Processing* (LQP):** Mentransformasi query deklaratif SQL ke dalam urutan eksekusi logis 10 fase standar ANSI SQL untuk mengeliminasi bug semantik seperti *alias shadowing* dan kebocoran predikat agregasi.
2. **Membedah Arsitektur *Physical Query Execution Engine*:** Mengidentifikasi interaksi antara Parser, Analyzer/Binder, Cost-Based Optimizer (CBO), dan Runtime Executor (Volcano Iterator Model vs. Vectorized Engine) pada PostgreSQL dan MySQL 8.0.
3. **Mengoptimalkan Algoritma Pengambilan Data Kompleks:** Mengimplementasikan pola penarikan data tingkat lanjut menggunakan *Window Functions* dengan spesifikasi frame eksplisit (`ROWS` vs `RANGE`), *Lateral Joins* (`CROSS APPLY`), dan *Recursive Common Table Expressions* (CTE) dengan kontrol materialisasi.
4. **Mendiagnosis dan Mengeliminasi *Performance Bottlenecks*:** Mengidentifikasi alokasi memori berlebih (`work_mem`), tumpahan ke disk (*disk spills*), degradasi kompleksitas waktu, dan hilangnya *SARGability* melalui analisis eksekusi visual dan tekstual (`EXPLAIN (ANALYZE, BUFFERS)`).
5. **Merancang Pola Kueri Berskala Enterprise:** Membangun kueri analitik dan transaksional yang tahan terhadap konkurensi tinggi, meminimalkan *buffer cache evictions*, dan menekan degradasi latensi p99 di lingkungan produksi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:

*   **Sintaks Dasar ANSI SQL:** Eksekusi lancar untuk DDL, DML, klausa `JOIN` (INNER, LEFT, RIGHT, FULL), dan agregasi dasar (`GROUP BY`, `HAVING`).
*   **Model Relasional & Aljabar Relasional:** Pemahaman tentang seleksi ($\sigma$), proyeksi ($\pi$), *Cartesian product* ($\times$), dan *Join* ($\bowtie$).
*   **Struktur Data & Algoritma Internal Database:** Pengetahuan mendalam tentang B-Tree/B+Tree indexing, Hash Tables, dan konsep memori buffer cache (SGA/Buffer Pool).
*   **Lingkungan Eksekusi:** Terpasang PostgreSQL 15+ atau MySQL 8.0+ dengan akses terminal untuk menjalankan CLI `psql` atau MySQL Client.

---

## 3. Concept & Internal Architecture

Dalam SQL, kode yang ditulis bersifat **deklaratif**, bukan imperatif. Pengembang mendeskripsikan *apa* data yang diinginkan, bukan *bagaimana* mengambilnya. Untuk mengeksekusi deklarasi ini, *Relational Database Management System* (RDBMS) membagi prosesnya ke dalam dua ranah: **Logical Query Processing** (urutan semantik teoritis) dan **Physical Query Execution** (langkah komputasi riil mesin database).

### 3.1. Logical Query Processing Phases

Secara leksikal, SQL ditulis mulai dari `SELECT`, namun secara logis, `SELECT` diproses hampir di akhir rantai. Pemrosesan logis beroperasi pada tabel virtual ($VT$), di mana keluaran dari satu fase menjadi masukan bagi fase berikutnya.

```
+-----------------------------------------------------------------------------------+
|                           LEXICAL ORDER (Cara Ditulis)                            |
| SELECT -> FROM -> JOIN -> WHERE -> GROUP BY -> HAVING -> WINDOW -> ORDER BY ->    |
| LIMIT/OFFSET                                                                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        LOGICAL PROCESSING ORDER (Cara Dievaluasi)                 |
|                                                                                   |
|  [1. FROM]           -> Evaluasi Cartesian Product (Cross Join)                   |
|         |                                                                         |
|         v                                                                         |
|  [2. ON]             -> Filter predikat Join (VT1)                                |
|         |                                                                         |
|         v                                                                         |
|  [3. JOIN]           -> Tambahkan Outer Rows untuk Outer Join (VT2)               |
|         |                                                                         |
|         v                                                                         |
|  [4. WHERE]          -> Evaluasi filter predikat baris atomik (VT3)               |
|         |                                                                         |
|         v                                                                         |
|  [5. GROUP BY]       -> Partisi baris ke dalam grup agregasi (VT4)                |
|         |                                                                         |
|         v                                                                         |
|  [6. HAVING]         -> Evaluasi filter predikat grup agregasi (VT5)              |
|         |                                                                         |
|         v                                                                         |
|  [7. WINDOW]         -> Kalkulasi Window Function over Partitions (VT6)           |
|         |                                                                         |
|         v                                                                         |
|  [8. SELECT]         -> Evaluasi ekspresi proyeksi, Scalar & Alias (VT7)          |
|         |                                                                         |
|         v                                                                         |
|  [9. DISTINCT]       -> Deduplikasi baris identik (VT8)                           |
|         |                                                                         |
|         v                                                                         |
|  [10. ORDER BY]      -> Pengurutan tampilan data (VT9)                            |
|         |                                                                         |
|         v                                                                         |
|  [11. LIMIT/OFFSET]  -> Pemangkasan baris kursor hasil (VT10)                     |
+-----------------------------------------------------------------------------------+
```

#### Rincian Fase Evaluasi Logis:
1. **Fase 1 (`FROM`):** Mengidentifikasi tabel sumber data. Jika terdapat pemisahan koma (ANSI-89) atau `CROSS JOIN`, kalkulasi dimulai dengan perkalian Kartesian ($R \times S$).
2. **Fase 2 (`ON`):** Menerapkan predikat pencocokan terhadap hasil perkalian Kartesian. Hanya baris yang bernilai `TRUE` yang lolos ke tabel virtual berikutnya.
3. **Fase 3 (`JOIN`):** Jika didefinisikan sebagai `OUTER JOIN` (LEFT, RIGHT, FULL), baris yang tidak cocok (*unmatched rows*) dari tabel yang dipertahankan (*preserved table*) dimasukkan kembali ke aliran data dengan kolom pasangan diisi `NULL`.
4. **Fase 4 (`WHERE`):** Memfilter baris tunggal secara diskrit. Baris yang bernilai `FALSE` atau `UNKNOWN` (karena evaluasi `NULL`) langsung dibuang. **Catatan:** Agregat tidak dapat dievaluasi di sini karena grup belum dibentuk.
5. **Fase 5 (`GROUP BY`):** Mengelompokkan baris berdasarkan kesamaan nilai dari kunci pengelompokan yang ditentukan. Menghasilkan satu baris representatif per grup.
6. **Fase 6 (`HAVING`):** Menerapkan filter predikat terhadap grup yang dihasilkan oleh `GROUP BY`. Hanya ekspresi skalar per grup atau fungsi agregat yang diizinkan di sini.
7. **Fase 7 (`WINDOW`):** Mengevaluasi fungsi analitik seperti `ROW_NUMBER()`, `RANK()`, `LEAD()`, atau `SUM(...) OVER(...)`. Fase ini berjalan di atas partisi grup yang ada tanpa mengubah jumlah baris dasar.
8. **Fase 8 (`SELECT`):** Mengekspansi ekspresi, mengevaluasi subquery skalar pada proyeksi, dan menetapkan alias kolom. Ini adalah alasan mengapa alias yang didefinisikan di `SELECT` tidak valid di `WHERE` atau `HAVING`.
9. **Fase 9 (`DISTINCT`):** Mengeliminasi baris duplikat dari tabel virtual melalui algoritma Hash Aggregate atau Unique Sort.
10. **Fase 10 (`ORDER BY`):** Mengurutkan baris secara fisik untuk pengiriman kursor. Pada fase ini, alias kolom dari fase `SELECT` sudah dapat diakses.
11. **Fase 11 (`LIMIT` / `OFFSET` / `FETCH FIRST`):** Memangkas baris dari offset tertentu hingga batas jumlah baris yang diminta sebelum dikembalikan ke aplikasi pemanggil.

---

### 3.2. Physical Query Execution Architecture

Ketika kueri tiba di RDBMS, mesin fisik database memprosesnya melalui subsistem internal berikut:

```
[SQL Query String]
       |
       v
+------------------+
| 1. Parser        | ---> Cek Sintaksis (Grammar) & Tokenisasi
+------------------+
       | (Parse Tree)
       v
+------------------+
| 2. Analyzer /    | ---> Cek Semantik (Katalog Sistem: Tabel, Kolom, Tipe Data, Izin)
|    Binder        |
+------------------+
       | (Query Tree / Logical Plan)
       v
+------------------+
| 3. Query         | ---> Ekivalensi Aljabar, Predicate Pushdown, Join Reordering,
|    Rewriter      |      View Expansion
+------------------+
       | (Rewritten Logical Plan)
       v
+------------------+
| 4. Cost-Based    | ---> Generate Candidate Physical Plans, Evaluasi Statistik
|    Optimizer     |      (Histogram, MCV), Hitung Cost (CPU + I/O).
+------------------+
       | (Optimal Physical Execution Plan)
       v
+------------------+
| 5. Executor      | ---> Eksekusi Operator Fisik: Seq Scan, Index Scan, Hash Join,
|                  |      Nested Loop, Materialize via Volcano Iterator Model.
+------------------+
       |
       v
  [Result Set]
```

#### Arsitektur Mesin Eksekusi: Volcano Iterator Model
Sebagian besar engine relasional modern (PostgreSQL, MySQL, SQLite, SQL Server) mengimplementasikan model eksekusi berbasis *Volcano Iterator* (dikenal juga sebagai *Pipeline Model*). 

Setiap operator relasional dalam *physical execution plan* direpresentasikan sebagai node iterator dengan antarmuka seragam:
*   `open()`: Menginisialisasi status internal operator dan mengalokasikan struktur memori.
*   `next()`: Menghasilkan tepat **satu tuple** berikutnya dalam aliran data, atau mengembalikan penanda `EOF` (End of Stream).
*   `close()`: Membersihkan status internal, membebaskan memori (`work_mem`), dan menutup handle file jika terjadi *spill*.

```
Contoh Evaluasi Aliran Volcano Model:

  [Client/Output]
         ^
         | next()  (Mengambil satu tuple)
  [Limit Operator]
         ^
         | next()
  [Nested Loop Join]
    /          \
   / next()     \ next()
[Index Scan]  [Seq Scan]
```

*Keuntungan:* Penggunaan memori minimal karena data ditarik secara malas (*demand-driven / lazy evaluation*), memungkinkan streaming baris langsung ke klien tanpa harus memuat seluruh kumpulan data ke RAM, kecuali jika bertemu dengan *blocking operator*.

#### Blocking vs. Non-Blocking Operators
*   **Non-Blocking (Pipelined) Operators:** Dapat memancarkan baris ke operator induk segera setelah menerima baris dari operator anak. Contoh: `Index Scan`, `Nested Loop Join`, `Filter` (`WHERE`).
*   **Blocking (Stop-the-World) Operators:** Harus mengonsumsi **seluruh kumpulan data** dari operator anak sebelum dapat menghasilkan baris pertama ke operator induk. Contoh: `SORT` (`ORDER BY` tanpa indeks penutup), `Hash Join` (pada fase *Build* tabel hash), `Aggregate` (`GROUP BY` berbasis hash atau sort tanpa indeks streaming).

---

## 4. Why & What

### Mengapa Memahami Pemisahan Leksikal vs. Logis itu Mutlak?
Banyak kegagalan performa dan cacat logika aplikasi tingkat enterprise berakar pada miskonsepsi bahwa database mengeksekusi instruksi sesuai urutan penulisan kode. 

Ketika pengembang menulis:
```sql
SELECT customer_id, COUNT(*) as total_orders
FROM orders
WHERE total_orders > 5 -- ERROR: column "total_orders" does not exist
GROUP BY customer_id;
```
Kesalahan kompilasi ini terjadi karena fase `WHERE` dievaluasi pada Langkah 4, sedangkan alias `total_orders` baru dialokasikan pada Langkah 8 (`SELECT`). Tanpa pemahaman ini, pengembang kerap melakukan *workaround* yang keliru seperti membungkusnya dalam *subquery* yang tidak efisien atau memindahkan pemrosesan ke memori aplikasi.

### Apa Implikasinya pada Skalabilitas dan Stabilitas Database?
1. **Pencegahan Disk Spill:** Mengetahui cara kerja agregasi dan pengurutan memungkinkan rekayasawan menyetel batas alokasi memori runtime (seperti `work_mem` di Postgres) secara akurat, mencegah operator blocking beralih ke operasi I/O disk lambat via `tempdb` atau *temporary files*.
2. **Kesesuaian SARGability (Search Argumentable):** Database hanya dapat memanfaatkan indeks saat predikat di fase `ON` dan `WHERE` bersifat deterministik dan tidak dibungkus oleh fungsi transformasional skalar.
3. **Optimasi Penggunaan Sumber Daya CPU:** Mengarahkan komputasi berat (seperti ekstraksi JSON, enkripsi skalar, regex) agar dievaluasi seselesai mungkin setelah fase reduksi baris (`WHERE` dan `HAVING`) tuntas dieksekusi.

---

## 5. How (Workflow Detail)

Mari kita telaah aliran transformasi data query berikut dari fase input hingga emisi hasil.

```sql
SELECT 
    d.department_name,
    AVG(e.salary) AS avg_salary,
    RANK() OVER (ORDER BY AVG(e.salary) DESC) as salary_rank
FROM departments d
JOIN employees e ON d.department_id = e.department_id
WHERE e.is_active = TRUE
GROUP BY d.department_name
HAVING COUNT(e.employee_id) >= 5
ORDER BY salary_rank ASC
LIMIT 3;
```

### Trace Eksekusi Langkah-demi-Langkah:

```
[ departments ] (10 rows)       [ employees ] (1000 rows)
       \                               /
        \                             /
         v                           v
   +---------------------------------------+
   | FASE 1: FROM                          |
   | Cartesian Product (Cross Join)        | -> Ukuran VT1: 10 x 1000 = 10,000 baris
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 2: ON (d.dept_id = e.dept_id)    |
   | Predicate Match                       | -> Ukuran VT2: 1000 baris (Asumsi data valid)
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 3: JOIN Expansion                |
   | (Inner Join: Tidak ada outer rows)    | -> Ukuran VT3: 1000 baris
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 4: WHERE (e.is_active = TRUE)    |
   | Baris non-aktif dipangkas             | -> Ukuran VT4: 850 baris
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 5: GROUP BY (d.department_name)  |
   | Hash Table Grouping                   | -> Ukuran VT5: 8 grup departemen unik
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 6: HAVING (COUNT(e.emp_id) >= 5) |
   | Grup kecil dieleminasi                | -> Ukuran VT6: 5 grup departemen
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 7: WINDOW (RANK() OVER ...)      |
   | Kalkulasi analitik per grup           | -> Ukuran VT7: 5 baris dengan nilai Rank
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 8: SELECT Projections            |
   | Evaluasi ekspresi skalar & alias      | -> Ukuran VT8: 5 baris, 3 kolom
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 9: ORDER BY (salary_rank ASC)    |
   | Topological Sort                      | -> Ukuran VT9: 5 baris terurut
   +---------------------------------------+
                       |
                       v
   +---------------------------------------+
   | FASE 10: LIMIT 3                      |
   | Kursor dipotong pada tuple ke-3       | -> Ukuran VT10: 3 baris
   +---------------------------------------+
                       |
                       v
                 [ Output Klien ]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Pengolahan Gandum
Bayangkan pemrosesan query seperti jalur perakitan pengolahan gandum modern:

1. **`FROM` & `JOIN`:** Truk-truk membawa bahan mentah dari berbagai ladang (`tabel`) dan menuangkannya ke bak penerimaan bersama.
2. **`WHERE`:** Mesin penyaring membuang batu, kotoran, dan butir gandum busuk (`is_active = FALSE`). Langkah ini dilakukan **sebelum** penggilingan agar mesin tidak aus memproses sampah.
3. **`GROUP BY`:** Gandum yang bersih dimasukkan ke dalam karung-karung berdasarkan varietasnya (`department_name`).
4. **`HAVING`:** Karung-karung yang beratnya kurang dari 5 kg disisihkan dari jalur distribusi utama (`COUNT >= 5`).
5. **`SELECT` & `WINDOW`:** Petugas menempelkan label nutrisi rata-rata (`AVG(salary)`) dan mencap ranking mutu pada karung (`RANK()`).
6. **`ORDER BY`:** Karung disusun rapi di atas palet berdasarkan ranking mutunya.
7. **`LIMIT`:** Operator forklift hanya mengambil 3 karung teratas untuk dimuat ke mobil pickup pelanggan.

```
Pipa Pemrosesan Data (Volcano Pipeline vs Blocking Point):

[Tabel A] \
           ==> (Join: Pipelined) ==> [Filter: WHERE] ==> (Aggregation: BLOCKING)
[Tabel B] /                                                        |
                                                                   v
                                                        Semua baris ditahan di sini
                                                        hingga kalkulasi grup tuntas!
                                                                   |
                                                                   v
[Hasil Klien] <== (Limit: Pipelined) <== (Sort: BLOCKING) <========+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Anatomi Pelanggaran Tahapan Logis

Kueri di bawah ini mendemonstrasikan kegagalan pemahaman LQP versus perbaikan standarnya:

```sql
-- KASUS KELIRU: Menggunakan alias SELECT di dalam WHERE
SELECT 
    user_id, 
    first_name || ' ' || last_name AS full_name
FROM users
WHERE full_name = 'Ada Lovelace';
-- Output Database:
-- ERROR: column "full_name" does not exist
-- Penjelasan: WHERE (Fase 4) dievaluasi sebelum SELECT (Fase 8).

-- SOLUSI 1: Mengulang ekspresi pada WHERE (Idul untuk SARGability jika ada indeks ekspresi)
SELECT 
    user_id, 
    first_name || ' ' || last_name AS full_name
FROM users
WHERE first_name || ' ' || last_name = 'Ada Lovelace';

-- SOLUSI 2: Menggunakan Common Table Expression (CTE) untuk memisahkan scope evaluasi
WITH resolved_users AS (
    SELECT 
        user_id, 
        first_name || ' ' || last_name AS full_name
    FROM users
)
SELECT user_id, full_name
FROM resolved_users
WHERE full_name = 'Ada Lovelace';
```

---

### 7.2. Practical Example: Pemrosesan Analitik Transaksi Finansial

Skenario: Sebuah platform pembayaran enterprise perlu menghitung **Running Balance** per akun per hari dan mengambil **3 transaksi terbesar** untuk setiap akun menggunakan teknik retrieval mutakhir tanpa memicu *table scan* berulang.

```sql
-- Setup Skema & Data Uji
CREATE TABLE accounts (
    account_id BIGINT PRIMARY KEY,
    holder_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(10) CHECK (transaction_type IN ('CREDIT', 'DEBIT')),
    transaction_time TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_transactions_acc_time_amount 
ON transactions(account_id, transaction_time DESC) 
INCLUDE (amount, transaction_type);

-- Query Analitik Kompleks: Running Balance & Top 3 Transaksi menggunakan LATERAL JOIN
WITH ranked_daily_movements AS (
    SELECT 
        t.account_id,
        t.transaction_time,
        t.amount,
        t.transaction_type,
        -- Window Function dengan spesifikasi frame eksplisit ROWS (Bukan RANGE!)
        SUM(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE -t.amount END) 
            OVER (
                PARTITION BY t.account_id 
                ORDER BY t.transaction_time ASC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_balance
    FROM transactions t
    WHERE t.transaction_time >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT 
    a.account_id,
    a.holder_name,
    rdm.transaction_time,
    rdm.amount,
    rdm.transaction_type,
    rdm.running_balance,
    top_tx.top_amount
FROM accounts a
-- Join lateral berfungsi mirip korelasi perulangan teroptimasi (nested-loop pushdown)
CROSS JOIN LATERAL (
    SELECT 
        rdm_inner.transaction_time,
        rdm_inner.amount,
        rdm_inner.transaction_type,
        rdm_inner.running_balance
    FROM ranked_daily_movements rdm_inner
    WHERE rdm_inner.account_id = a.account_id
    ORDER BY rdm_inner.transaction_time DESC
    LIMIT 1
) rdm
CROSS JOIN LATERAL (
    SELECT ARRAY_AGG(sub.amount ORDER BY sub.amount DESC) AS top_amount
    FROM (
        SELECT tx.amount
        FROM transactions tx
        WHERE tx.account_id = a.account_id
        ORDER BY tx.amount DESC
        LIMIT 3
    ) sub
) top_tx
WHERE a.account_id IN (101, 102, 103);
```

#### Analisis Optimasi Kueri di Atas:
1. **`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`:** Menghindari *in-memory peer-group spooling* bawaan dari `RANGE`. `RANGE` secara default harus mencari baris dengan nilai duplikat pada order criteria, memaksa alokasi memori buffer disk ganda, sedangkan `ROWS` membaca stream fisik baris per baris.
2. **`LATERAL JOIN`:** Memungkinkan inner query merujuk kolom dari outer query (`a.account_id`), bertindak sebagai iterator yang didorong ke indeks (*Index-driven evaluation*), alih-alih melakukan *FULL SCAN* pada tabel transaksi secara menyeluruh.

---

## 8. Real World Case Study (Enterprise Scale)

### Masalah Produksi: Degradasi Latensi P99 pada Sistem Flash-Sale E-Commerce
*   **Lingkungan:** PostgreSQL 14 pada AWS Aurora (16 vCPU, 64 GB RAM).
*   **Beban Sistem:** 15.000 Transaksi per Detik (TPS).
*   **Gejala:** Kueri dashboard analitik *real-time* pedagang menyebabkan latensi p99 database melonjak dari 15ms ke 12.000ms. CPU melonjak hingga 100%, memicu *connection pool starvation*.

#### Kueri Masalah Awal (Karya Pengembang):
```sql
-- DITULIS OLEH TIM APLIKASI
SELECT 
    o.merchant_id,
    o.status,
    COUNT(DISTINCT o.order_id) as unique_orders,
    SUM(o.total_amount) as gross_revenue,
    AVG(p.processing_fee) as avg_fee
FROM orders o
LEFT JOIN payments p ON o.order_id = p.order_id
WHERE o.created_at >= NOW() - INTERVAL '2 hours'
GROUP BY o.merchant_id, o.status
ORDER BY gross_revenue DESC;
```

#### Investigasi Mendalam Masalah:
1. **Cartesian Product Amplification:** Satu `order` memiliki rata-rata 3 record `payments` (karena percobaan gagal dan *split payments*). Hubungan 1:N ini melipatgandakan data di Tahap 1-3 (`FROM` & `JOIN`).
2. **Double Evaluation & Invalidation:** Operasi `SUM(o.total_amount)` menghasilkan angka yang salah (terduplikasi 3x karena perkalian baris hasil *join*). Tim aplikasi mencoba memperbaiki ini dengan melakukan kompensasi manual di aplikasi, memboroskan komputasi.
3. **`COUNT(DISTINCT)` Memory Spilling:** Melakukan evaluasi `COUNT(DISTINCT)` pada jutaan baris hasil join memaksa Postgres membuat Hash Table besar per grup di memori. Karena melampaui `work_mem` (64MB), mesin beralih ke *Disk Spill* (menulis ke tabel sementara di disk), terlihat dari metrik *External Sort/Hash Spill*.

```
EXPLAIN ANALYZE OUTPUT (Problematic Query):
->  Sort (cost=125430.22..125432.10 rows=752) (actual time=4852.122..4855.431 rows=450)
      Sort Key: (sum(o.total_amount)) DESC
      Sort Method: external merge  Disk: 48920kB   <-- DISK SPILL KRITIS!
      ->  HashAggregate (cost=85000.00..85120.00)
            Group Key: o.merchant_id, o.status
            Planned Partitions: 16  Batches: 16  Disk Usage: 104520kB <-- SPILL!
            ->  Hash Join (cost=4500.00..62000.00 rows=1500000)
                  Hash Cond: (p.order_id = o.order_id)
                  ->  Seq Scan on payments p (actual rows=4500000)
                  ...
Execution Time: 5214.882 ms
```

#### Solusi Rekayasa: Architectural Query Refactoring

Pendekatan optimasi dilakukan dengan memisahkan fase agregasi independen sebelum melakukan penggabungan data (*Aggregating Before Joining*).

```sql
-- KUERI REFAKTOR PRODUKSI
WITH target_orders AS MATERIALIZED (
    -- Isolasi filter waktu dan reduksi baris seawal mungkin
    SELECT 
        o.order_id,
        o.merchant_id,
        o.status,
        o.total_amount
    FROM orders o
    WHERE o.created_at >= NOW() - INTERVAL '2 hours'
),
aggregated_orders AS (
    -- Agregasi level order: 1 baris per grup unik tanpa Cartesian product
    SELECT 
        merchant_id,
        status,
        COUNT(order_id) AS unique_orders,
        SUM(total_amount) AS gross_revenue,
        ARRAY_AGG(order_id) AS order_ids
    FROM target_orders
    GROUP BY merchant_id, status
),
aggregated_payments AS (
    -- Pre-aggregate payments independen berdasarkan order_id yang valid
    SELECT 
        p.order_id,
        AVG(p.processing_fee) AS avg_fee
    FROM payments p
    WHERE EXISTS (
        SELECT 1 FROM target_orders tor 
        WHERE tor.order_id = p.order_id
    )
    GROUP BY p.order_id
)
SELECT 
    ao.merchant_id,
    ao.status,
    ao.unique_orders,
    ao.gross_revenue,
    AVG(ap.avg_fee) AS avg_fee
FROM aggregated_orders ao
CROSS JOIN LATERAL UNNEST(ao.order_ids) AS tid(order_id)
LEFT JOIN aggregated_payments ap ON ap.order_id = tid.order_id
GROUP BY ao.merchant_id, ao.status, ao.unique_orders, ao.gross_revenue
ORDER BY ao.gross_revenue DESC;
```

#### Hasil Metrik Produksi:
*   **Waktu Eksekusi Kueri:** Menurun dari **5.214 ms** menjadi **38 ms** (Peningkatan performa ~137x).
*   **I/O Disk Spills:** Turun drastis dari **153 MB** ke **0 Bytes** (100% In-Memory Execution).
*   **Penggunaan CPU Aurora Database:** Turun dari 100% ke 18% stabil saat *peak traffic*.

---

## 9. Trade-offs

Dalam merancang kueri pengambilan data tingkat enterprise, setiap keputusan arsitektural memiliki konsekuensi langsung terhadap alokasi sumber daya.

| Pendekatan Rekayasa | Sisi Positif (Pros) | Sisi Negatif / Konsekuensi (Cons) | Metrik Terdampak | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **Materialized CTE (`AS MATERIALIZED`)** | Mengkalkulasi subquery tepat sekali; bertindak sebagai *optimization fence* mencegah komputasi berulang. | Mengorbankan alokasi memori/disk; menghentikan *predicate pushdown* dari outer query. | Memory, Disk I/O, Query Latency | Subquery analitik berat yang dirujuk $\ge 2$ kali pada query yang sama. |
| **Inline CTE / Subquery** | Optimizer dapat menggabungkan kueri (*flattening*) dan mendorong predikat `WHERE` ke tingkat tabel terdalam. | Kueri yang sama dapat dievaluasi berulang kali jika perencana (*planner*) mendeteksi biaya alternatif. | CPU Cycles, Cache Churn | Transformasi logika sederhana dan modularisasi alur baca kode. |
| **Pipelined Window Function (`ROWS`)** | Konsumsi memori konstan $O(1)$; streaming instan tanpa buffer baris tambahan. | Logika tidak menangani relasi baris dengan nilai urutan sama (*peer groups*) secara implisit. | Latency p99, RAM | Analitik deret waktu, running totals, komputasi FIFO/LIFO. |
| **ANSI Default Window Function (`RANGE`)** | Menghitung relasi *ties/peers* secara matematis presisi sesuai standar ANSI. | Konsumsi memori $O(N)$ terhadap partisi; membaca maju-mundur di spool buffer (*high cache overhead*). | Memory, Temporary File I/O | Pemeringkatan peringkat murni di mana duplikasi nilai harus menghasilkan kalkulasi identik. |
| **Hash Join vs Nested Loop (Join Algorithms)** | Hash Join sangat cepat untuk memproses dataset besar tanpa indeks pada Join Key. | Membutuhkan fase *Build* pemblokir (*blocking memory phase*); butuh RAM besar. | Memory (`work_mem`), Startup Cost | Operasi batch berskala besar atau pelaporan *offline*. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Kegagalan *SARGability* Karena Evaluasi Fungsi Skalar
*   **Kode Rusak:**
    ```sql
    SELECT transaction_id, amount 
    FROM transactions 
    WHERE DATE(transaction_time) = '2023-10-01';
    ```
*   **Dampak Buruk:** Database tidak dapat menggunakan B-Tree Index pada `transaction_time`. Engine terpaksa beralih ke *Full Table Scan* terhadap seluruh tabel (jutaan baris), menghitung fungsi `DATE()` untuk setiap baris.
*   **Koreksi Standar:**
    ```sql
    SELECT transaction_id, amount 
    FROM transactions 
    WHERE transaction_time >= '2023-10-01 00:00:00Z' 
      AND transaction_time < '2023-10-02 00:00:00Z';
    ```

### 2. Disk Spill pada Window Functions Akibat Default Frame
*   **Kode Rusak:**
    ```sql
    SELECT order_id, customer_id, 
           SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_time)
    FROM orders;
    ```
*   **Dampak Buruk:** Tidak mendefinisikan frame clause secara spesifik menyebabkan database menerapkan default ANSI: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Ini memicu pembentukan struktur *Spool Engine* di Postgres/SQL Server yang dapat tumpah (*spill*) ke disk saat partisi membesar.
*   **Koreksi Standar:**
    ```sql
    SELECT order_id, customer_id, 
           SUM(amount) OVER (
               PARTITION BY customer_id 
               ORDER BY order_time 
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           )
    FROM orders;
    ```

### 3. Jebakan `NOT IN` Terhadap Subquery yang Menghasilkan `NULL`
*   **Kode Rusak:**
    ```sql
    SELECT user_id FROM users 
    WHERE user_id NOT IN (SELECT supervisor_id FROM departments);
    ```
*   **Dampak Buruk:** Jika terdapat satu saja nilai `NULL` di kolom `supervisor_id`, evaluasi logis SQL menggunakan logika tiga nilai (*Three-Valued Logic*):
    `user_id NOT IN (1, 2, NULL)` dievaluasi menjadi `user_id <> 1 AND user_id <> 2 AND user_id <> NULL`.
    Karena `user_id <> NULL` menghasilkan `UNKNOWN`, seluruh ekspresi `AND` bernilai `UNKNOWN` atau `FALSE`. Kueri mengembalikan **0 baris** (*silent data loss*).
*   **Koreksi Standar (Gunakan `NOT EXISTS`):**
    ```sql
    SELECT u.user_id 
    FROM users u 
    WHERE NOT EXISTS (
        SELECT 1 FROM departments d 
        WHERE d.supervisor_id = u.user_id
    );
    ```

### 4. Pola Anti-Paginasi: Skalabilitas Runtuh pada Skala Besar Menggunakan `OFFSET`
*   **Kode Rusak:**
    ```sql
    SELECT id, payload FROM events ORDER BY created_at DESC LIMIT 20 OFFSET 500000;
    ```
*   **Dampak Buruk:** Sesuai urutan logis, database harus memindai dan memilah $500.020$ baris, mengurutkannya, lalu membuang $500.000$ baris pertama untuk mengembalikan hanya $20$ baris. Mengakibatkan I/O masif dan latensi tinggi.
*   **Koreksi Standar (Keyset Pagination / Keyset Cursor):**
    ```sql
    -- Simpan 'created_at' dan 'id' terakhir dari halaman sebelumnya
    SELECT id, payload 
    FROM events 
    WHERE (created_at, id) < ('2023-10-01 10:00:00Z', 892110)
    ORDER BY created_at DESC, id DESC 
    LIMIT 20;
    ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini saat melakukan *Code Review* dan verifikasi arsitektur kueri SQL:

- [ ] **Predikat `WHERE` Bersifat SARGable:** Kolom yang terindeks tidak dibungkus fungsi skalar, kalkulasi matematika, atau type-casting implisit.
- [ ] **Eksplisitkan Frame Window Function:** Selalu gunakan `ROWS` alih-alih membiarkan default `RANGE`, kecuali dependensi *ties* memang diwajibkan oleh spesifikasi bisnis.
- [ ] **Eliminasi Subquery Kartesian:** Pastikan tidak ada join parsial yang mengalikan baris sebelum agregasi; gunakan pre-agregasi jika diperlukan.
- [ ] **Defensif terhadap Three-Valued Logic:** Hindari operator `NOT IN (SELECT ...)`. Gunakan `NOT EXISTS` atau anti-join (`LEFT JOIN ... WHERE right.id IS NULL`).
- [ ] **Verifikasi Buffer dan Spill Kueri:** Jalankan `EXPLAIN (ANALYZE, BUFFERS)` pada *staging* dengan volume data mirip produksi. Pastikan `Disk: 0 kB` dan metrik *Sort Method* berada pada `quicksort` dalam memori.
- [ ] **Klausa `SELECT` Minimalis:** Tidak ada penggunaan `SELECT *` pada kode produksi. Hanya proyeksikan kolom yang dibutuhkan untuk memungkinkan optimizer menggunakan *Index-Only Scan*.
- [ ] **Batas Paginasi Aman:** Tidak menggunakan `OFFSET` besar di tabel transaksional. Migrasikan ke model *Keyset Pagination*.
- [ ] **Pengecekan Kardinalitas dan Selektivitas:** Pastikan statistik tabel telah diperbarui melalui rutinitas `ANALYZE` berkala agar CBO tidak salah memilih *Nested Loop Join* untuk tabel besar.

---

## 12. Hands-on Practice

Simpan seluruh skrip di bawah ini ke dalam direktori file praktikum: `hands-on/m02/logical_query_deep_dive.sql`.

### Langkah Praktikum Terpandu

#### Langkah 1: Persiapan Skema Data & Konfigurasi Engine
Buka terminal dan jalankan `psql` ke database target Anda.

```sql
-- hands-on/m02/logical_query_deep_dive.sql

DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS store_orders CASCADE;

CREATE TABLE store_orders (
    order_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    order_status VARCHAR(20) NOT NULL
);

CREATE TABLE order_items (
    item_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id INT NOT NULL REFERENCES store_orders(order_id),
    sku VARCHAR(50) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    quantity INT NOT NULL
);

-- Masukkan dataset simulasi dengan sebaran data realistis
INSERT INTO store_orders (customer_id, order_date, order_status)
SELECT 
    (random() * 1000)::INT + 1,
    CURRENT_DATE - ((random() * 60)::INT || ' days')::INTERVAL,
    (ARRAY['COMPLETED', 'PENDING', 'CANCELLED'])[floor(random() * 3 + 1)]
FROM generate_series(1, 10000);

INSERT INTO order_items (order_id, sku, price, quantity)
SELECT 
    (random() * 9999)::INT + 1,
    'SKU-PROD-' || (random() * 500)::INT,
    ((random() * 100) + 5)::NUMERIC(10, 2),
    (random() * 5)::INT + 1
FROM generate_series(1, 50000);

CREATE INDEX idx_orders_status_date ON store_orders(order_status, order_date);
CREATE INDEX idx_items_order_id ON order_items(order_id) INCLUDE (price, quantity);

ANALYZE store_orders;
ANALYZE order_items;
```

#### Langkah 2: Eksperimen Efek Pemilihan Frame Window Function
Bandingkan profil memori antara `RANGE` dan `ROWS`.

```sql
-- Uji 1: Menggunakan Default FRAME (RANGE)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    order_id, 
    order_date,
    COUNT(*) OVER (
        PARTITION BY order_status 
        ORDER BY order_date
        -- Default: RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as running_count
FROM store_orders;

-- Uji 2: Menggunakan Eksplisit Streaming FRAME (ROWS)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    order_id, 
    order_date,
    COUNT(*) OVER (
        PARTITION BY order_status 
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as running_count
FROM store_orders;
```
*Tugas Analisis:* Periksa metrik `Buffers` pada *WindowAgg node*. Amati bagaimana penggunaan memori pada versi `ROWS` lebih rendah dan stabil dibandingkan `RANGE`.

#### Langkah 3: Mengatasi Alias Scoping & Predicate Pushdown
Jalankan query analisis tingkat keranjang belanja:

```sql
-- Analisis Keranjang: Menghitung pembeli bernilai tinggi
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH aggregated_basket AS (
    SELECT 
        so.customer_id,
        COUNT(DISTINCT so.order_id) AS total_orders,
        SUM(oi.price * oi.quantity) AS customer_spend
    FROM store_orders so
    JOIN order_items oi ON so.order_id = oi.order_id
    WHERE so.order_status = 'COMPLETED'
    GROUP BY so.customer_id
)
SELECT 
    customer_id,
    total_orders,
    customer_spend
FROM aggregated_basket
WHERE customer_spend > 500.00
ORDER BY customer_spend DESC
LIMIT 10;
```
*Tugas Analisis:* Perhatikan dalam rencana eksekusi di mana predikat `customer_spend > 500.00` diletakkan. Apakah Optimizer mengevaluasinya di dalam `HAVING` internal CTE atau melakukan filter di luar setelah seluruh agregasi selesai?

---

## 13. Exercise

### Level Easy
Tulis kueri untuk mengambil data dari tabel `store_orders` yang menampilkan `customer_id`, total transaksi per pelanggan, dan label klasifikasi volume: `'HIGH'` jika total pesanan $> 10$, dan `'REGULAR'` jika $\le 10$. Urutkan hasil dari total pesanan terbanyak ke tersedikit.
*Batasan:* Dilarang menggunakan *Subquery* atau CTE. Gunakan pemahaman fase LQP secara murni.

### Level Medium
Berdasarkan skema `store_orders` dan `order_items`, buat sebuah kueri yang menghitung **persentase kontribusi penjualan** setiap item (`oi.price * oi.quantity`) terhadap **total omset keseluruhan status 'COMPLETED'**, dikelompokkan berdasarkan bulan transaksi.
*Kriteria Teknis:*
*   Gunakan *Window Function* tanpa melakukan Join ganda ke tabel sumber.
*   Spesifikasikan frame window secara tepat untuk performa optimal.
*   Hasil harus memuat kolom: `order_id`, `bulan_transaksi`, `nilai_item`, dan `persentase_dari_total_bulan_berjalan`.

### Level Hard
Optimalkan kueri agregasi pelaporan di bawah ini yang mengalami degradasi performa drastis akibat Cartesian explosion dan subquery berulang:

```sql
-- Kueri Buruk yang Harus Dirombak
SELECT 
    so.customer_id,
    (SELECT COUNT(*) FROM store_orders so2 WHERE so2.customer_id = so.customer_id) AS all_time_orders,
    SUM(oi.price * oi.quantity) AS current_completed_spend,
    MAX(so.order_date) AS last_order_date
FROM store_orders so
JOIN order_items oi ON so.order_id = oi.order_id
WHERE so.order_status = 'COMPLETED'
GROUP BY so.customer_id
HAVING SUM(oi.price * oi.quantity) > 1000
ORDER BY current_completed_spend DESC;
```
*Kriteria Teknis:*
*   Hapus korelasi subquery skalar di proyeksi `SELECT`.
*   Cegah multiplikasi kalkulasi `all_time_orders` akibat join terhadap `order_items`.
*   Hasilkan eksekusi dengan maksimal 1 scan ke tabel `store_orders`.

---

## 14. Challenge

### Studi Kasus: Ledger Balance Reconstruction Engine

**Latar Belakang Arsitektural:**
Sebuah platform neobank menyimpan jutaan mutasi mutlak di tabel append-only bernama `general_ledger`. Karena alasan kepatuhan audit regulasi, saldo akun tidak disimpan sebagai nilai mutabel di tabel terpisah, melainkan harus dikonstruksi secara on-the-fly dari riwayat mutasi debit dan kredit.

```sql
CREATE TABLE general_ledger (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_number VARCHAR(34) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    direction VARCHAR(2) CHECK (direction IN ('CR', 'DR')),
    amount NUMERIC(18, 4) NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_ledger_acc_posted ON general_ledger(account_number, posted_at);
```

**Tantangan Rekayasa:**
Anda diminta merancang arsitektur kueri *point-in-time balance reconstruction* yang harus memenuhi spesifikasi berikut:

1. **Parameter Input:** Diberikan target waktu arbitrer, misalnya `AS OF '2023-09-15 23:59:59.999+00'`.
2. **Kebutuhan Output:** Mengambil 50 akun dengan aktivitas mutasi terbesar dalam 7 hari sebelum parameter target waktu tersebut, dan menghasilkan output:
    *   `account_number`
    *   `currency`
    *   `reconstructed_balance_as_of`: Saldo bersih total sejak awal waktu hingga target waktu yang ditentukan ($\sum CR - \sum DR$).
    *   `rolling_7d_volume`: Total volume perputaran dana mutasi ($\sum |amount|$) selama rentang window 7 hari tersebut.
    *   `largest_single_credit_tx`: Nilai kredit mutasi tunggal tertinggi yang pernah dicatat oleh akun tersebut dalam rentang window 7 hari.
3. **Batasan Keras Produksi (Constraints):**
    *   **Anti-Double Scan:** Dilarang memindai tabel `general_ledger` secara penuh berkali-kali untuk menghitung saldo historis dan saldo 7 hari.
    *   **Batas Waktu:** Query harus dieksekusi di bawah 150ms pada dataset uji yang memiliki minimal 10.000.000 baris.
    *   **Zero Intermediate Table Spill:** Seluruh operasi agregasi dan kalkulasi window harus tertampung dalam `work_mem = 32MB` tanpa menulis temporary file ke disk.

Tuliskan strategi arsitektur Anda, query SQL produksi, dan jelaskan langkah-langkah logika optimasi perencana fisik yang Anda targetkan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Pada tahap pemrosesan logis manakah sebuah alias kolom yang didefinisikan di klausa `SELECT` mulai valid dan dapat diakses oleh klausa lain?**
   * A. `WHERE`
   * B. `GROUP BY`
   * C. `HAVING`
   * D. `ORDER BY`

2. **Mengapa fungsi agregasi seperti `COUNT()` atau `SUM()` tidak dapat dievaluasi secara langsung di dalam klausa `WHERE`?**
   * A. Karena `WHERE` hanya mendukung tipe data string dan integer.
   * B. Karena `WHERE` (Fase 4) dievaluasi sebelum pembentukan partisi baris oleh `GROUP BY` (Fase 5).
   * C. Karena fungsi agregat membutuhkan pengurutan fisik dari `ORDER BY`.
   * D. Karena standar ANSI mewajibkan semua agregasi ditulis di dalam ekspresi subquery.

3. **Perilaku apa yang terjadi pada baris yang bernilai predikat `UNKNOWN` pada evaluasi klausa `WHERE`?**
   * A. Baris tetap dimasukkan ke dalam tabel virtual berikutnya.
   * B. Database melemparkan runtime exception fatal.
   * C. Baris dibuang dari tabel virtual hasil pemfilteran.
   * D. Nilai atribut otomatis dikonversi menjadi string kosong `""`.

4. **Operasi join manakah di bawah ini yang memproses Tahap 3 (Outer Row Addition) pada evaluasi logis?**
   * A. `INNER JOIN`
   * B. `CROSS JOIN`
   * C. `LEFT OUTER JOIN`
   * D. `NATURAL JOIN` (tanpa spesifikasi outer)

5. **Antarmuka method apakah yang dieksekusi secara berulang pada model eksekusi *Volcano Iterator* untuk mengalirkan tuple antar operator fisik secara demand-driven?**
   * A. `fetch()`
   * B. `next()`
   * C. `pull()`
   * D. `emit()`

---

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Apa dampak arsitektural terhadap konsumsi memori dan eksekusi ketika klausa frame window dihilangkan pada query yang menggunakan `ORDER BY`?**
   * A. Otomatis beralih ke `ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING`.
   * B. Menggunakan default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, yang memicu buffering peer-group dan mencegah pipelining baris secara efisien.
   * C. Menghentikan optimasi query dan memaksa engine melakukan restart transaksi.
   * D. Memory footprint selalu $O(1)$ terlepas dari spesifikasi klausa.

7. **Diberikan ekspresi: `WHERE col NOT IN (SELECT other_col FROM tbl)`. Jika `other_col` menghasilkan set data `{10, 20, NULL}`, maka output filter tersebut adalah:**
   * A. Mengembalikan seluruh baris kecuali yang bernilai 10 dan 20.
   * B. Selalu mengembalikan himpunan kosong (0 baris) karena perbandingan logika tiga nilai dengan `NULL`.
   * C. Otomatis mengabaikan nilai `NULL` dan melanjutkan filter pada nilai 10 dan 20.
   * D. Menghasilkan eksekusi crash dengan kode error *NullPointerException*.

8. **Manakah dari operator fisik berikut yang diklasifikasikan sebagai *Blocking Operator* (Stop-the-World)?**
   * A. `Index Scan`
   * B. `Filter`
   * C. `Sort` (tanpa ketersediaan index pemesanan)
   * D. `Nested Loop Join`

9. **Apa perbedaan mendasar antara implementasi `LATERAL JOIN` (PostgreSQL) dibandingkan subquery berkorelasi biasa di klausa `SELECT`?**
   * A. `LATERAL JOIN` hanya dapat mengembalikan satu baris dan satu kolom skalar tunggal.
   * B. `LATERAL JOIN` dapat mengembalikan banyak baris dan banyak kolom per baris terluar, serta bertindak sebagai parameter iterator langsung ke perencana join fisik.
   * C. `LATERAL JOIN` dieksekusi secara asynchronous di thread terpisah.
   * D. Subquery di `SELECT` selalu lebih hemat memori daripada `LATERAL JOIN`.

10. **Bagaimana optimizer menangani *Common Table Expression* (CTE) yang dideklarasikan dengan penanda `MATERIALIZED` pada PostgreSQL 12+?**
    * A. Menulis output CTE ke dalam tabel permanen di skema public.
    * B. Memaksa engine mengevaluasi CTE secara terpisah sebagai *temporary data buffer* sekali jalan, bertindak sebagai *optimization fence* yang menghentikan penyatuan query (*flattening*).
    * C. Mengubah CTE menjadi temporary view berbasis disk secara paksa.
    * D. Menginstruksikan CBO untuk melakukan inline query ekspansi tanpa isolasi.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1:**
Sebuah query pelaporan akuntansi berjalan lambat:
```sql
SELECT gl.branch_id, SUM(gl.amount) 
FROM general_ledger gl 
WHERE EXTRACT(YEAR FROM gl.posted_at) = 2023 
GROUP BY gl.branch_id;
```
Tabel memiliki indeks komposit B-Tree pada `(posted_at, branch_id)`. Hasil `EXPLAIN` menunjukkan bahwa perencana fisik memilih operator `Seq Scan` (Full Table Scan) yang memakan waktu 45 detik. Apa akar masalah arsitekturalnya dan bagaimana perbaikan paling optimal tanpa memodifikasi skema indeks fisik yang ada?
*   A. *Index Cardinality* terlalu rendah; solusinya ubah tabel menjadi unindexed heap.
*   B. Fungsi `EXTRACT(YEAR ...)` menghilangkan sifat *SARGability* kolom `posted_at`; solusinya ganti filter predikat menjadi rentang stempel waktu diskrit: `gl.posted_at >= '2023-01-01' AND gl.posted_at < '2024-01-01'`.
*   C. Urutan kolom indeks salah; seharusnya `branch_id` berada di posisi pertama.
*   D. Klausa `GROUP BY` membatalkan penggunaan indeks pada `WHERE`.

12. **Skenario 2:**
Pada sistem inventaris retail berskala 50 juta baris, kueri paginasi berikut di halaman 2000 mengalami timeout (>30 detik):
```sql
SELECT product_id, sku, updated_at 
FROM inventory 
ORDER BY updated_at DESC, product_id DESC 
LIMIT 25 OFFSET 50000;
```
Indeks pada `(updated_at DESC, product_id DESC)` sudah aktif. Mengapa timeout tetap terjadi meskipun indeks yang sesuai telah dibuat?
*   A. Indeks rusak (*corrupted*) dan harus dibangun ulang menggunakan `REINDEX`.
*   B. Karena `OFFSET 50000` memaksa mesin menelusuri 50.025 leaf node dari indeks B-Tree dan membaca data heap terkait, sebelum akhirnya membuang 50.000 tuple pertama.
*   C. Batas alokasi `shared_buffers` terlalu kecil untuk menampung 25 baris data.
*   D. Mesin database tidak mendukung operasi descending pada B-Tree.

13. **Skenario 3:**
Sistem analytics Anda mengalami crash Out-Of-Memory (OOM) saat kueri berikut dieksekusi secara terjadwal:
```sql
SELECT 
    user_id,
    session_id,
    event_time,
    LAST_VALUE(event_payload) OVER (
        PARTITION BY user_id 
        ORDER BY event_time
    ) as latest_payload
FROM tracking_events;
```
Dataset memiliki miliaran data event. Apa kegagalan logika dalam kueri analitik ini yang menyebabkan lonjakan alokasi memori runtime dan hasil bisnis yang salah (tidak benar-benar mengembalikan event terakhir sesi)?
*   A. Fungsi `LAST_VALUE()` memerlukan alokasi `work_mem` minimal 1GB per partisi.
*   B. Partisi berdasarkan `user_id` tidak valid untuk tipe data integer.
*   C. Kueri mengandalkan frame default ANSI (`RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`). Hal ini menyebabkan `LAST_VALUE()` hanya mengevaluasi data sampai baris saat ini (bukan baris paling akhir di partisi) dan sekaligus memicu *spill* struktur spool ke disk/memori. Frame seharusnya ditentukan sebagai `ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING` atau diubah menggunakan `FIRST_VALUE()` dengan urutan terbalik.
*   D. Tidak ada klausa `WHERE`, sehingga database memuat seluruh data ke swap space secara ilegal.

---

### Kunci Jawaban & Justifikasi

#### Bagian 1
1. **D — `ORDER BY`**. Sesuai siklus Logical Query Processing, `SELECT` berada di Langkah 8, sedangkan `ORDER BY` berada di Langkah 10. Klausa `WHERE`, `GROUP BY`, dan `HAVING` dievaluasi mendahului `SELECT`.
2. **B — `WHERE` (Fase 4) dievaluasi sebelum pembentukan partisi baris oleh `GROUP BY` (Fase 5)**. Fungsi agregat membutuhkan sekelompok tuple untuk dihitung, sementara pada fase `WHERE`, database masih berada pada tahap evaluasi baris tunggal independen.
3. **C — Baris dibuang dari tabel virtual hasil pemfilteran**. Sesuai standar ANSI logika 3 nilai, predikat `WHERE` hanya meloloskan baris yang ekspresinya secara definitif bernilai boolean `TRUE`. Nilai `FALSE` dan `UNKNOWN` dieliminasi.
4. **C — `LEFT OUTER JOIN`**. Fase 3 secara eksplisit bertugas mengembalikan kembali baris-baris dari preserved-table (*outer table*) yang tidak lolos pencocokan predikat fase 2 (`ON`) ke dalam kumpulan data dengan nilai pelengkap `NULL`.
5. **B — `next()`**. Model Volcano iterator mengandalkan pemanggilan rekursif `next()` dari consumer operator ke producer operator untuk menarik data tuple-demi-tuple.

#### Bagian 2
6. **B — Menggunakan default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`...** Default `RANGE` mengharuskan database mencari baris yang bernilai sama (*peer rows*) pada sorting key, menciptakan overhead memori dan mencegah eksekusi streaming murni yang disediakan oleh mode `ROWS`.
7. **B — Selalu mengembalikan himpunan kosong (0 baris)...** Evaluasi `x NOT IN (..., NULL)` ditransformasikan secara aljabar menjadi relasi konjungtif `(x <> ...) AND (x <> NULL)`. Nilai dari `x <> NULL` adalah `UNKNOWN`, dan kondisi konjungtif `TRUE AND UNKNOWN` mengevaluasi ke `UNKNOWN`, sehingga tidak ada baris yang lolos filter.
8. **C — `Sort` (tanpa ketersediaan index pemesanan)**. Operasi pengurutan membutuhkan konsumsi seluruh masukan baris dari anak tree sebelum baris urutan pertama dapat ditentukan secara matematis dan dipancarkan ke atas (*pipeline break*).
9. **B — `LATERAL JOIN` dapat mengembalikan banyak baris dan banyak kolom...** Berbeda dari correlated subquery biasa di proyeksi yang dibatasi satu sel skalar, lateral join bertindak sebagai inline loop yang mengekspos seluruh bentuk relasi ke perencana join database.
10. **B — Memaksa engine mengevaluasi CTE secara terpisah...** Istilah *optimization fence* merujuk pada isolasi kalkulasi di mana planner tidak diizinkan untuk menyatukan kembali (*flatten/inline*) subquery ke dalam kueri utama, mencegah predikat luar didorong masuk (*pushed-down*) ke dalam CTE.

#### Bagian 3
11. **B — Fungsi `EXTRACT(YEAR ...)` menghilangkan sifat *SARGability*...** Membungkus kolom dengan fungsi skalar memaksa evaluasi per baris dan mematikan fungsi B-Tree range traversal. Mengubahnya menjadi rentang `>=` dan `<` mengembalikan kemampuan perencana untuk menggunakan `Index Range Scan`.
12. **B — Karena `OFFSET 50000` memaksa mesin menelusuri 50.025 leaf node...** `OFFSET` tidak melompati baris secara magis pada level fisik. Mesin tetap harus memindai dan menghitung tuple satu demi satu hingga batas offset tercapai. Solusinya adalah *keyset pagination*.
13. **C — Kueri mengandalkan frame default ANSI (`RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`)...** Karena frame default berhenti pada `CURRENT ROW`, `LAST_VALUE()` secara paradoksikal hanya mengembalikan nilai baris itu sendiri. Selain cacat logika bisnis, mode `RANGE` ini memicu alokasi frame spooling yang masif di memori per partisi, berujung pada kehabisan memori (OOM).

---

## 16. Summary

1. **Pemisahan Semantik Mutlak:** SQL bersifat deklaratif; urutan penulisan kode (*lexical order*) tidak mencerminkan urutan eksekusi (*logical order*). Memahami alur `FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY` adalah fondasi eliminasi bug scoping dan desain kueri berkinerja tinggi.
2. **Volcano Iterator vs Blocking Operators:** Mesin fisik database beroperasi melalui penarikan tuple berbasis antarmuka `open()`, `next()`, `close()`. Kenali operator *non-blocking* (pipelined stream) versus *blocking* (`Sort`, `Hash Aggregate`) untuk mencegah terjadinya lonjakan memori dan latensi p99.
3. **Optimasi Frame Window Function:** Default ANSI `RANGE` membawa penalti performa laten yang berat akibat pemrosesan peer-group. Selalu definisikan klausa frame secara eksplisit menggunakan `ROWS BETWEEN ...` untuk memastikan streaming satu dimensi dengan penggunaan memori $O(1)$.
4. **Integritas SARGability:** Keberadaan indeks fisik tidak menjamin penggunaannya oleh database optimizer. Hindari pemanggilan fungsi pada kolom target di klausa predikat `WHERE` dan `ON` agar traversal B-Tree tetap optimal.
5. **Keyset Pagination vs Paging Klasik:** `OFFSET` besar tidak memiliki tempat dalam arsitektur berskala enterprise. Desainlah paginasi berbasis kursor deterministik (*Keyset Cursor*) untuk memastikan kompleksitas waktu komputasi konstan $O(1)$ terlepas dari kedalaman halaman yang diakses klien.