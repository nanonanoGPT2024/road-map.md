# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Advanced SQL Analytics & Query Optimization**  
**Topik: BI Analyst | Kategori: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
- Mengonstruksi kueri analitik kompleks menggunakan *advanced window functions*, *multi-level aggregations*, dan *recursive common table expressions* (rCTEs) untuk menyelesaikan use-case pelaporan hierarkis dan *time-series cohort*.
- Menganalisis *physical query execution plan* (`EXPLAIN ANALYZE`, query graph, operator costs) untuk mendeteksi *performance bottleneck*, *data skew*, *spill to disk*, dan kegagalan *cardinality estimation*.
- Mendesain strategi pengindeksan, partisi data (*partitioning*), dan *clustering/bucketing* pada data warehouse modern (PostgreSQL, Snowflake, BigQuery) guna meminimalkan I/O *throughput* dan *compute credit consumption*.
- Mengimplementasikan pola pemodelan data analitik inkremental yang bersifat *idempotent* dan *deterministic* untuk integrasi Business Intelligence tingkat enterprise.
- Memitigasi anti-pola SQL seperti *accidental cross-joins*, *high-cardinality group-by explosions*, dan kalkulasi subkueri redundan.

---

## 2. Prerequisite
Untuk memahami materi ini secara komprehensif, peserta diwajibkan telah menguasai:
- **Foundational SQL**: Standar sintaks ANSI SQL-92/99 (`SELECT`, `JOIN`, `GROUP BY`, `HAVING`, aggregasi dasar).
- **Basic Data Modeling**: Pemahaman arsitektur skema Relational (3NF) versus Dimensional (Star Schema, Snowflake Schema: Fact vs. Dimension tables).
- **Sistem Operasi & Database Internals**: Pengetahuan konseptual tentang penyimpanan disk berbasis blok/halaman, struktur memori database (*buffer cache*, *shared buffers*, `work_mem`), dan konsep latensi jaringan/disk I/O.
- **Tooling**: Terbiasa menjalankan kueri analitik pada CLI (misalnya `psql`) atau IDE database (DBeaver, DataGrip) dan membaca output log tekstual.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Pemrosesan Kueri: Dari SQL String ke Physical Execution
Ketika analitik SQL dieksekusi, database engine tidak langsung menjalankan string tersebut. Query parser dan optimizer melalui serangkaian tahapan internal:

```
[SQL Query String]
       │
       ▼
┌──────────────┐
│ Query Parser │ ──> Syntax Check, Lexical Analysis, Parsing Tree
└──────────────┘
       │
       ▼
┌──────────────┐
│ Query Rewriter│ ──> View expansion, Constant folding, Semantic check
└──────────────┘
       │
       ▼
┌──────────────┐
│  Cost-Based  │ <── Statistics Catalog (Histograms, MCVs, Null Frac, Page Count)
│  Optimizer   │ ──> Enumerate Logical Plans ──> Generate Physical Plans
└──────────────┘
       │
       ▼
┌──────────────┐
│ Query Engine │ ──> Volcano Iterator Model (Open, Next, Close) / Vectorized Engine
└──────────────┘
       │
       ▼
 [Result Tuples]
```

1. **Parser & Analyzer**: Memvalidasi sintaks dan memetakan objek database (tabel, kolom) terhadap *System Catalog*. Menghasilkan *Abstract Syntax Tree* (AST).
2. **Rewriter (Rule Engine)**: Menerapkan aturan logis independen dari biaya (cost). Contoh: memecah view menjadi tabel dasarnya, menyederhanakan predikat tautologis (misal: `WHERE 1=1 AND status = 'A'`).
3. **Cost-Based Optimizer (CBO)**: Menghitung estimasi biaya komputasi (CPU cost + I/O cost) untuk ratusan kombinasi eksekusi:
   - Akses data: *Sequential Scan*, *Index Scan*, *Bitmap Index Scan*, *Index-Only Scan*.
   - Urutan Join (*Join Order Permutations* via Dynamic Programming atau Genetic Algorithms).
   - Algoritma Join: *Nested Loop Join*, *Hash Join*, *Sort-Merge Join*.
   - Basis estimasi: *Statistics Catalog* (berisi ukuran tabel, *Most Common Values* [MCV], kuantil histogram distribusi data, dan korelasi fisik data).
4. **Execution Engine**:
   - **Volcano Iterator Model**: Pendekatan tradisional berbasis baris per baris (*tuple-at-a-time* via interface `open()`, `next()`, `close()`). Overhead CPU tinggi pada OLAP karena *virtual function calls*.
   - **Vectorized Execution Model** (e.g., Snowflake, ClickHouse, DuckDB, modern PostgreSQL extensions): Memproses sekumpulan nilai (*vectors* atau *arrays* dari ratusan hingga ribuan baris sekaligus) dalam cache CPU (L1/L2/L3), memanfaatkan instruksi SIMD (*Single Instruction, Multiple Data*).

### 3.2 Dynamic Memory Allocation: Work Memory & Spill to Disk
Pada engine berbasis baris seperti PostgreSQL, parameter `work_mem` menentukan batas memori internal yang dialokasikan untuk operasi penyortiran (*sorting*, *order by*, *window functions*) dan *hash tables* (*hash join*, *hash aggregation*). 
- Jika volume data melebihi alokasi memori kerja, database melakukan transisi dari **In-Memory Sorting (QuickSort)** ke **External Sort (Merge Sort on Disk)**, atau dari **In-Memory Hash Join** ke **Hybrid Hash Join with Temp File Spills**.
- Pada arsitektur cloud data warehouse (Snowflake, BigQuery), kondisi ini dikenal dengan terminologi **Local Disk Spilling** (memori virtual warehouse habis, menulis ke SSD lokal) dan **Remote Disk Spilling** (SSD lokal habis, menulis ke remote cloud storage seperti AWS S3/Google Cloud Storage), yang menyebabkan penurunan performa kueri secara drastis (*orders of magnitude*).

### 3.3 Anatomi Advanced Window Functions & Frame Specifications
Operasi analitik window functions memisahkan konsep agregasi dari reduksi baris. Anatomi deklarasi window:

$$\text{FUNCTION}()\ \mathbf{OVER}\ (\mathbf{PARTITION\ BY}\ p_1, p_2\ \mathbf{ORDER\ BY}\ o_1\ [\mathbf{ASC}|\mathbf{DESC}]\ \mathbf{FRAME\_SPECIFICATION})$$

Frame specification mendefinisikan batas subset baris dinamis relatif terhadap baris saat ini (*current row*):
- `ROWS BETWEEN <start> AND <end>`: Membatasi fisik baris secara absolut. Efisien karena tidak memerlukan pemeriksaan duplikasi nilai sorting.
- `RANGE BETWEEN <start> AND <end>`: Membatasi nilai logis berdasarkan kolom pada klausa `ORDER BY`. Engine harus memindai seluruh peers (nilai duplikat) yang nilainya identik dengan *current row*. 
  > *Peringatan Produksi:* Standar ANSI SQL mendefinisikan default frame saat `ORDER BY` dideklarasikan tanpa klausa frame sebagai:  
  > `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`  
  > Default ini secara signifikan lebih lambat daripada `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` pada dataset bervolume tinggi, karena engine dipaksa melakukan kalkulasi deteksi peers logis.

---

## 4. Why & What

### Mengapa BI Analyst Harus Menguasai Database Internals?
Laporan BI yang lambat (dashboard *freezing*, query timeout setelah 300 detik) hampir selalu bersumber dari penulisan SQL analitik yang buruk, bukan kegagalan visualisasi UI. Seorang BI Analyst enterprise tidak hanya bertanggung jawab mengekstrak data (`WHAT`), tetapi juga memastikan kueri beroperasi secara efisien dalam arsitektur komputasi terdistribusi (`HOW`).

| Pendekatan Konvensional | Pendekatan Enterprise BI Engineer |
| :--- | :--- |
| Mengandalkan agregasi di layer visualisasi (BI Tool). | Melakukan agregasi selektif di storage engine via SQL teroptimasi. |
| Menggunakan subquery bertingkat tanpa analisis rencana eksekusi. | Menganalisis *Predicate Pushdown* dan pruning partisi via `EXPLAIN`. |
| Menarik seluruh dataset mentah ke BI memori (e.g., Tableau Extract). | Menerapkan materialisasi bertingkat (*Incremental Models / ELT*). |
| Menyelesaikan masalah lambat dengan menaikkan *warehouse size* ($$$). | Mengurangi I/O footprint dan eliminasi *cross-join explosion* (ROI tinggi). |

### Apa yang Dioptimasi?
1. **I/O Footprint**: Jumlah *data blocks/partitions* yang dibaca dari disk. Mengurangi *Full Table Scan* menjadi *Partition Pruning* atau *Index Scan*.
2. **Network/Inter-Node Shuffle**: Pada warehouse terdistribusi (MPP Architecture), join antar tabel yang tidak di-*co-locate* menyebabkan perpindahan data via jaringan (*data redistribution / broadcasting*).
3. **Memory Pressure**: Menjaga agregasi dan sorting tetap berada pada *fast memory cache* tanpa mengalami *disk spilling*.

---

## 5. How (Workflow Detail)

Untuk mengidentifikasi, merekayasa ulang, dan mengoptimalkan kueri analitik BI skala enterprise, terapkan alur kerja 6-langkah berikut:

```
[1. Baseline Profiling] ──> Capture Execution Time, Scanned Bytes, Memory/Spill
           │
           ▼
[2. Execution Plan]     ──> Run EXPLAIN (ANALYZE, BUFFERS) / Profiler Graph
           │
           ▼
[3. Bottleneck Triage]  ──> Deteksi Node Biaya Tertinggi (Seq Scan, Hash Join, Sort)
           │
           ▼
[4. Query Refactoring]  ──> Terapkan Frame Optimization, CTE Flattening, Filtering
           │
           ▼
[5. Physical Tuning]    ──> Partisi, Clustering Keys, Summary Tables, Statistics
           │
           ▼
[6. Benchmark & Verify] ──> Konfirmasi Reduksi Cost & Determinisme Output Data
```

### Langkah 1: Baseline Profiling
Identifikasi baseline metrik: durasi kueri (*wall clock time*), jumlah baris yang dihasilkan, volume data yang dibaca (*bytes scanned*), dan jumlah komputasi/kredit yang digunakan.

### Langkah 2: Evaluasi Execution Plan
Jalankan kueri menggunakan `EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)` pada PostgreSQL atau periksa *Query Profile visual graph* di Snowflake / BigQuery.

### Langkah 3: Triase Bottleneck
- **Cost Anomalies**: Perbedaan tajam antara estimasi baris (`rows=...`) dan baris aktual (`actual rows=...`). Perbedaan order of magnitude ($10\times - 1000\times$) mengindikasikan katalog statistik usang (*stale statistics*), memicu CBO memilih algoritma join yang salah.
- **Operator Biaya Tinggi**: Identifikasi node dengan *cost percentage* > 60%. Cari operator `External Sort`, `Hash Join` bertingkat tinggi, atau `Filter` yang dieksekusi setelah pembacaan jutaan baris alih-alih memanfaatkan index scan.

### Langkah 4: Structural Query Refactoring
- Ganti subquery berkorelasi (*correlated subqueries*) dengan Window Functions atau explicit Joins.
- Perbaiki batas frame window function: eksplisit deklarasikan `ROWS BETWEEN ...` untuk mencegah overhead `RANGE`.
- Dorong filter lebih dekat ke sumber (*Predicate Pushdown* manual bila CBO gagal melakukannya).

### Langkah 5: Desain Fisik & Pengindeksan (Physical Design)
- Konfigurasikan tabel analitik menggunakan partisi waktu (`PARTITION BY DATE(order_date)`).
- Terapkan *clustering keys* pada kolom-kolom yang sering digunakan dalam klausa filter atau join berulang (e.g., `tenant_id`, `customer_id`).

### Langkah 6: Validasi Deterministik & Regresi
Pastikan hasil transformasi kueri baru menghasilkan dataset yang identik secara matematis (`EXCEPT` / `MINUS` testing bernilai 0 baris) dengan penurunan metrik latensi minimal 50%.

---

## 6. Analogy & Diagram ASCII

### Analogi Pustakawan & Gudang Buku
Bayangkan sebuah gudang arsip dengan 10.000.000 dokumen transaksi keuangan.
- **Full Table Scan**: Pustakawan berjalan ke setiap rak dari lantai 1 sampai lantai 10, membaca setiap lembar dokumen dari awal hingga akhir hanya untuk mencari 5 transaksi milik PT. ABC.
- **Index Scan (B-Tree)**: Pustakawan membuka kartu katalog alfabetis di meja depan, menemukan letak dokumen PT. ABC berada di Rak 4, Kotak 12, dan langsung mengambil 5 dokumen tersebut.
- **Partition Pruning**: Gudang dibagi menjadi ruangan khusus per tahun. Kueri mencari tahun 2024; pustakawan mengunci ruangan 2015–2023 dan hanya memeriksa ruangan 2024.
- **Spill to Disk**: Meja kerja pustakawan hanya muat 10 dokumen sekaligus. Ketika diminta mengurutkan 100.000 dokumen, meja penuh. Pustakawan terpaksa bolak-balik menaruh tumpukan sementara di kardus lantai, memperlambat proses 100 kali lipat dibanding jika mejanya cukup besar (*in-memory*).

### Arsitektur Data Shuffling dan Join Execution

```
Node 1 (Worker)                 Node 2 (Worker)
┌───────────────────────┐       ┌───────────────────────┐
│ Fact: 50M Rows        │       │ Fact: 50M Rows        │
│ Dim: Local Partition  │       │ Dim: Local Partition  │
└───────────────────────┘       └───────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            │
              INTER-CONNECT NETWORK FABRIC
     [Data Reshuffling / Hash Redistribution: SLOW]
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│ Hash Table: Dim A     │       │ Hash Table: Dim A     │
│ Probe: Fact Data      │       │ Probe: Fact Data      │
│ In-Memory Match OK    │       │ SPILL TO DISK WARNING │
│ (Memory: 512MB)       │       │ (Memory > work_mem)   │
└───────────────────────┘       └───────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Window Functions - Running Total & Moving Average
Contoh mendasar ini mendemonstrasikan signifikansi penulisan frame specification pada kinerja ANSI SQL.

```sql
-- SKENARIO: Menghitung Running Total omzet harian per toko
-- VARIANT A: Kueri tidak efisien (implisit RANGE, membaca peers)
SELECT 
    store_id,
    sale_date,
    revenue,
    SUM(revenue) OVER (
        PARTITION BY store_id 
        ORDER BY sale_date
        -- Implisit: RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total_slow
FROM retail_sales;

-- VARIANT B: Kueri Teroptimasi (eksplisit ROWS, eksekusi direct pointer)
SELECT 
    store_id,
    sale_date,
    revenue,
    SUM(revenue) OVER (
        PARTITION BY store_id 
        ORDER BY sale_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total_fast,
    AVG(revenue) OVER (
        PARTITION BY store_id 
        ORDER BY sale_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS moving_avg_7d
FROM retail_sales;
```

### 7.2 Practical Example: Enterprise MoM & YoY Retention Engine
Kueri analitik tingkat lanjut untuk menghitung *Month-over-Month (MoM) Growth*, *Year-over-Year (YoY) Growth*, dan segmentasi persentil performa pelanggan menggunakan ANSI/PostgreSQL yang valid:

```sql
WITH monthly_customer_metrics AS (
    SELECT 
        DATE_TRUNC('month', transaction_timestamp)::DATE AS sales_month,
        customer_id,
        SUM(amount) AS total_spend,
        COUNT(DISTINCT transaction_id) AS total_orders
    FROM enterprise_orders
    WHERE transaction_timestamp >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '24 months'
      AND order_status = 'COMPLETED'
    GROUP BY 
        DATE_TRUNC('month', transaction_timestamp)::DATE, 
        customer_id
),
customer_ranked_performance AS (
    SELECT 
        sales_month,
        customer_id,
        total_spend,
        total_orders,
        -- Mengelompokkan pelanggan ke dalam quintile spending per bulan
        NTILE(5) OVER (
            PARTITION BY sales_month 
            ORDER BY total_spend DESC
        ) AS spending_quintile,
        -- Menarik total belanja bulan sebelumnya untuk customer yang sama
        LAG(total_spend, 1) OVER (
            PARTITION BY customer_id 
            ORDER BY sales_month
        ) AS prev_month_spend,
        -- Menarik total belanja tahun sebelumnya (12 periode)
        LAG(total_spend, 12) OVER (
            PARTITION BY customer_id 
            ORDER BY sales_month
        ) AS prev_year_spend
    FROM monthly_customer_metrics
)
SELECT 
    sales_month,
    spending_quintile,
    COUNT(customer_id) AS total_active_customers,
    ROUND(SUM(total_spend), 2) AS current_tier_revenue,
    ROUND(
        (SUM(total_spend) - SUM(prev_month_spend)) 
        / NULLIF(SUM(prev_month_spend), 0) * 100, 
        2
    ) AS mom_growth_pct,
    ROUND(
        (SUM(total_spend) - SUM(prev_year_spend)) 
        / NULLIF(SUM(prev_year_spend), 0) * 100, 
        2
    ) AS yoy_growth_pct
FROM customer_ranked_performance
GROUP BY 
    sales_month, 
    spending_quintile
ORDER BY 
    sales_month DESC, 
    spending_quintile ASC;
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: E-Commerce Multi-Tenant Global FinTech
* **Platform**: Database PostgreSQL 16 pada instans AWS RDS `db.r6i.4xlarge` (16 vCPU, 128 GB RAM, Aurora Storage Engine).
* **Ukuran Dataset**: Tabel `ledger_entries` memuat 450.000.000 transaksi.
* **Problem Statement**: Dasbor Executive BI mengeksekusi kueri agregasi pergerakan saldo kas harian per *tenant*. Dasbor mengalami *statement timeout* (koneksi diputus setelah 300 detik) atau menghabiskan kapasitas IOPS storage.

### Kueri Asli (Unoptimized):
```sql
-- EXECUTION TIME: 312.435 ms (TIMEOUT pada jam sibuk)
SELECT 
    tenant_id,
    DATE(entry_timestamp) as tx_date,
    account_type,
    SUM(credit_amount - debit_amount) as net_flow,
    (SELECT SUM(l2.credit_amount - l2.debit_amount)
     FROM ledger_entries l2
     WHERE l2.tenant_id = ledger_entries.tenant_id
       AND DATE(l2.entry_timestamp) <= DATE(ledger_entries.entry_timestamp)
    ) as cumulative_balance
FROM ledger_entries
WHERE entry_timestamp >= '2023-01-01'
GROUP BY tenant_id, DATE(entry_timestamp), account_type;
```

### Analisis Execution Plan Awal (`EXPLAIN ANALYZE`):
1. **Correlated Subquery Explosion**: Subquery skalar pada `cumulative_balance` dieksekusi untuk setiap baris hasil agregasi luar ($N \times M$ complexity).
2. **Date Function Wrapping**: Predikat `DATE(entry_timestamp)` mematikan kemampuan optimizer memanfaatkan index pada `entry_timestamp` (*Non-Sargable Predicate*).
3. **Spill to Disk**: Operasi `HashAggregate` menghasilkan *hash tables* berukuran 4.2 GB, melampaui default `work_mem` (4 MB), memaksa engine menulis 3.8 GB temp files ke disk.

### Langkah Remediasi Arsitektur:
1. **Partisi Fisik**: Mengonversi tabel menjadi *Declarative Range Partitioning* berdasarkan kolom `entry_timestamp` (bulanan).
2. **Composite BRIN Index**: Menggunakan *Block Range Index* (BRIN) pada tabel partisi untuk `entry_timestamp` karena data append-only berurutan secara fisik.
3. **Refaktorisasi SQL**: Menghilangkan correlated subquery dengan menggantinya menggunakan *Cumulative Window Aggregate*.

### Kueri Setelah Refaktorisasi (Optimized):
```sql
WITH daily_flows AS (
    SELECT 
        tenant_id,
        entry_timestamp::DATE AS tx_date,
        account_type,
        SUM(credit_amount - debit_amount) AS net_flow
    FROM ledger_entries
    -- Filter sargable: Range batas jelas tanpa modifikasi fungsi pada kolom indeks
    WHERE entry_timestamp >= TIMESTAMP '2023-01-01 00:00:00'
      AND entry_timestamp <  TIMESTAMP '2024-01-01 00:00:00'
    GROUP BY 
        tenant_id, 
        entry_timestamp::DATE, 
        account_type
)
SELECT 
    tenant_id,
    tx_date,
    account_type,
    net_flow,
    -- Window function menggantikan subkueri skalar O(N^2) menjadi O(N log N)
    SUM(net_flow) OVER (
        PARTITION BY tenant_id, account_type
        ORDER BY tx_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_balance
FROM daily_flows
ORDER BY tenant_id, tx_date, account_type;
```

### Metrik Hasil Komparasi:
| Metrik | Sebelum Optimasi | Sesudah Optimasi | Efisiensi |
| :--- | :--- | :--- | :--- |
| **Execution Time** | 312,435 ms | 1,420 ms | **99.5% lebih cepat (220x)** |
| **Shared Hit Blocks**| 840,210 | 124,015 | 85.2% pengurangan I/O |
| **Temp Disk Spill**| 3,892 MB | 0 MB (Pure In-Memory) | Eliminasi Total Disk I/O |
| **CPU Utilization**| 100% (semua 16 core saturasi) | 22% (burst sesaat) | Mengurangi starvation pool |

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

Dalam arsitektur analitik enterprise, setiap keputusan desain SQL memiliki implikasi trade-off arsitektural:

```
                  PENGHEMATAN BIAYA (COST)
                            ▲
                           / \
                          /   \
                         /  ▲  \
                        / TRADE \
                       /   OFF   \
                      /     ▼     \
LATENSI RENDAH ◄─────┴───────────┴─────► TINGKAT KELENTURAN
(AGREGASI/MATERIALISASI)                  (REAL-TIME COMPUTE AD-HOC)
```

### 1. In-Line Computation vs. Pre-Aggregation (Materialized Views)
- **In-Line (Compute On-Demand)**:
  - *Kelebihan*: Data selalu up-to-date (real-time); fleksibilitas filter dimensi tidak terbatas.
  - *Kekurangan*: Beban I/O dan CPU tinggi; biaya compute pergudangan data cloud melonjak linear terhadap frekuensi refresh dasbor.
- **Pre-Aggregated (Materialized Tables / dbt incremental)**:
  - *Kelebihan*: Latensi dasbor < 1 detik; query hanya memindai $0.1\%$ volume data mentah.
  - *Kekurangan*: Membutuhkan pipeline sinkronisasi batch/streaming; latensi data (data lag); biaya storage ganda.

### 2. Indexes: Read Latency vs. Write Amplification
- **Menambahkan Composite Indexes (B-Tree/GIST)**:
  - *Kelebihan*: Akses kueri filter analitik spesifik menjadi sub-milidetik.
  - *Kekurangan*: Operasi `INSERT`/`UPDATE` batch harian melambat (*write amplification*). Setiap modifikasi baris memaksa database mengunci dan memperbarui pohon indeks di disk.

### 3. Big Warehouse vs. Query Optimization (Cloud Warehouses)
- Menggandakan ukuran compute warehouse di Snowflake (e.g., Size L ke Size 2XL) memangkas durasi kueri yang lambat hingga 50%, tetapi melipatgandakan *credit consumption* per jam ($4\times$).
- Melakukan query refactoring (membatasi partition scanning dan frame specification) mempertahankan ukuran warehouse di level Small dengan durasi setara, menghemat pengeluaran ribuan dolar per bulan.

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Anti-Pattern: Non-Sargable Predicates
Penggunaan ekspresi matematika atau fungsi manipulasi tipe data pada kolom di dalam klausa `WHERE` membuat optimizer tidak dapat menggunakan index scan (*Non-Sargable*).

*Contoh Salah:*
```sql
-- Index pada 'created_at' diabaikan secara total! Full Table Scan terjadi.
SELECT customer_id, amount 
FROM payments 
WHERE TO_CHAR(created_at, 'YYYY-MM') = '2024-03';
```

*Contoh Benar:*
```sql
-- Sargable: B-Tree index scan aktif secara penuh
SELECT customer_id, amount 
FROM payments 
WHERE created_at >= '2024-03-01 00:00:00' 
  AND created_at <  '2024-04-01 00:00:00';
```

### 10.2 Anti-Pattern: Accidental Cartesian Explosion via Multi-Valued JOINs
Melakukan `JOIN` langsung pada beberapa tabel *one-to-many* secara simultan sebelum agregasi menyebabkan perkalian silang (*fan-out*), melipatgandakan baris dan menghasilkan nilai agregasi (`SUM`, `AVG`) yang korup secara finansial.

*Contoh Terjadi Duplikasi Nilai (Bug Finansial):*
```sql
-- Pelanggan memiliki 2 alamat dan 3 pesanan: Menghasilkan 6 baris join!
-- SUM(o.total_amount) akan terhitung 2x lipat dari nilai riil.
SELECT 
    c.customer_id,
    SUM(o.total_amount) AS calculated_revenue
FROM customers c
LEFT JOIN customer_addresses a ON c.customer_id = a.customer_id
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id;
```

*Solusi Teroptimasi & Benar:*
```sql
-- Lakukan agregasi independen sebelum operasi join dilakukan
WITH customer_orders_aggregated AS (
    SELECT 
        customer_id, 
        SUM(total_amount) AS calculated_revenue
    FROM orders
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    COALESCE(coa.calculated_revenue, 0) AS calculated_revenue
FROM customers c
LEFT JOIN customer_orders_aggregated coa ON c.customer_id = coa.customer_id;
```

### 10.3 Troubleshooting Guide: Memory Spill to Disk
Apabila log eksekusi kueri mencatat `External Sort: 54124kB` atau Snowflake Profile menampilkan `Bytes spilled to remote storage`:

```
Gejala: Query lambat drastis, I/O Wait membengkak tinggi
  │
  ├─> Periksa Work Memory:
  │     SET work_mem = '256MB'; -- Naikkan secara modular pada session level
  │
  ├─> Audit Kolom SELECT:
  │     Eliminasi kolom teks masif yang tidak terpakai (e.g. payload_json, metadata_text)
  │     dari subquery sorting/agregasi.
  │
  └─> Tinjau Sorting/Window Frame:
        Ganti 'RANGE' dengan 'ROWS'.
        Pastikan klausa PARTITION BY memiliki kardinalitas yang cukup rasional.
```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist arsitektural ini sebelum merilis skrip analitik atau semantic layer model ke production data warehouse:

- [ ] **Sargability**: Tidak ada fungsi logis/string/tanggal yang membungkus kolom database terindeks pada predikat `WHERE` dan `JOIN ON`.
- [ ] **SELECT Minimalist**: Seluruh `SELECT *` telah dieliminasi; hanya kolom dimensi dan metrik yang diperlukan yang ditarik ke memory.
- [ ] **Window Frame Explicit**: Semua fungsi window berbasis urutan memiliki frame boundaries eksplisit (`ROWS BETWEEN ...`).
- [ ] **Partition Pruning Enforced**: Filter tanggal/waktu pada partitioned table dinyatakan secara pasti dan statis atau semi-statis untuk memicu *static partition elimination*.
- [ ] **CTE Materialization Awareness**: Pada PostgreSQL, CTE besar yang hanya digunakan satu kali diverifikasi apakah di-inlining oleh optimizer atau membutuhkan syntax `WITH cte_name AS MATERIALIZED (...)`.
- [ ] **DISTINCT/UNION Misuse**: Tidak menggunakan `SELECT DISTINCT` hanya untuk menutupi bug join fan-out; menggunakan `UNION ALL` alih-alih `UNION` jika data dijamin unik secara matematis.
- [ ] **Deterministic Ordering**: Kueri analitik berbasis penomoran baris (`ROW_NUMBER()`) selalu menyertakan kolom tie-breaker unik pada `ORDER BY` untuk memastikan output stabil antar eksekusi.
- [ ] **Statistics Freshness**: Tabel yang mengalami operasi batch ingestion besar telah dianalisis ulang (`ANALYZE table_name;`) sebelum menjalankan kueri analitik downstream.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan mereproduksi masalah degradasi performa pada PostgreSQL dan mengoptimalkannya menggunakan teknik indexing, memory management, dan refaktorisasi kueri. Simpan seluruh artefak praktikum ini di direktori `hands-on/m02/`.

### Tahap 1: Setup Lingkungan & Ingestion Dataset Sintetis
Buka terminal dan buat file `hands-on/m02/01_setup_benchmark.sql`:

```sql
-- hands-on/m02/01_setup_benchmark.sql
DROP TABLE IF EXISTS raw_clickstream CASCADE;

CREATE TABLE raw_clickstream (
    event_id BIGSERIAL,
    user_id INT NOT NULL,
    session_id UUID NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    url_path VARCHAR(255) NOT NULL,
    event_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    dwell_time_ms INT
);

-- Injeksi 1.000.000 baris data sintetis
INSERT INTO raw_clickstream (user_id, session_id, event_name, url_path, event_timestamp, dwell_time_ms)
SELECT 
    (random() * 50000)::INT AS user_id,
    gen_random_uuid() AS session_id,
    (ARRAY['page_view', 'add_to_cart', 'checkout_click', 'payment_failed', 'purchase_success'])[(random()*4 + 1)::INT] AS event_name,
    '/product/' || (random() * 1000)::INT AS url_path,
    TIMESTAMP '2024-01-01 00:00:00' + (random() * (INTERVAL '90 days')) AS event_timestamp,
    (random() * 120000)::INT AS dwell_time_ms
FROM generate_series(1, 1000000);

-- Refresh catalog stats
ANALYZE raw_clickstream;
```

Eksekusi via terminal:
```bash
psql -U postgres -d analytics_db -f hands-on/m02/01_setup_benchmark.sql
```

### Tahap 2: Mendiagnosis Kueri Buruk (Unoptimized Session Duration Analysis)
Buat file `hands-on/m02/02_unoptimized_query.sql`:

```sql
-- hands-on/m02/02_unoptimized_query.sql
-- Skenario: Menghitung session duration per user dan mencari user tercepat checkout
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT 
    user_id,
    session_id,
    MIN(event_timestamp) AS session_start,
    MAX(event_timestamp) AS session_end,
    EXTRACT(EPOCH FROM (MAX(event_timestamp) - MIN(event_timestamp))) AS session_duration_seconds,
    (SELECT event_name 
     FROM raw_clickstream c2 
     WHERE c2.session_id = c1.session_id 
     ORDER BY event_timestamp DESC LIMIT 1) AS last_event
FROM raw_clickstream c1
WHERE event_timestamp >= '2024-02-01' 
  AND event_timestamp <= '2024-02-28'
GROUP BY user_id, session_id;
```

Jalankan skrip ini, catat nilai Execution Time dan kemunculan operator `SubPlan` berkorelasi yang memicu pembacaan blok disk raksasa.

### Tahap 3: Optimasi Struktur & Penulisan SQL
Buat file `hands-on/m02/03_optimized_query.sql` yang mengimplementasikan Window Function dan eliminasi SubPlan:

```sql
-- hands-on/m02/03_optimized_query.sql

-- Buat indeks composite untuk mendukung seleksi data berbasis range tanggal
CREATE INDEX IF NOT EXISTS idx_clickstream_ts_covering 
ON raw_clickstream(event_timestamp) 
INCLUDE (user_id, session_id, event_name);

EXPLAIN (ANALYZE, BUFFERS, COSTS)
WITH ranked_events AS (
    SELECT 
        user_id,
        session_id,
        event_name,
        event_timestamp,
        FIRST_VALUE(event_timestamp) OVER w_session AS session_start,
        LAST_VALUE(event_timestamp) OVER w_session AS session_end,
        LAST_VALUE(event_name) OVER w_session AS last_event,
        ROW_NUMBER() OVER (
            PARTITION BY session_id 
            ORDER BY event_timestamp DESC
        ) AS reverse_seq
    FROM raw_clickstream
    WHERE event_timestamp >= TIMESTAMP '2024-02-01 00:00:00' 
      AND event_timestamp <  TIMESTAMP '2024-03-01 00:00:00'
    WINDOW w_session AS (
        PARTITION BY session_id 
        ORDER BY event_timestamp ASC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT 
    user_id,
    session_id,
    session_start,
    session_end,
    EXTRACT(EPOCH FROM (session_end - session_start)) AS session_duration_seconds,
    last_event
FROM ranked_events
WHERE reverse_seq = 1;
```

Eksekusi dan bandingkan hasilnya:
```bash
psql -U postgres -d analytics_db -f hands-on/m02/03_optimized_query.sql
```

---

## 13. Exercise

### Level Easy
Tuliskan kueri ANSI SQL untuk menghitung perbedaan selisih waktu (`time_delta`) dalam detik antara transaksi saat ini dengan transaksi persis sebelumnya untuk masing-masing `customer_id`.
* **Skema**: `transactions(transaction_id INT, customer_id INT, transaction_time TIMESTAMP, amount NUMERIC)`
* **Constraint**: Gunakan fungsi window tanpa melakukan join manual atau subquery.

### Level Medium
Diberikan tabel `user_logins(user_id INT, login_date DATE)`. Seseorang dapat login beberapa kali dalam sehari (duplikat mungkin ada).
Tuliskan kueri SQL untuk mendeteksi rekor berturut-turut login harian terpanjang (*longest consecutive login streak*) untuk setiap pelanggan menggunakan teknik pemotongan kelompok analitik (*Gaps and Islands Problem* via window functions).

### Level Hard
Optimalkan kueri analitik berikut yang mengalami kegagalan *memory exhaustion* pada PostgreSQL:
```sql
SELECT 
    d.department_name,
    e.employee_name,
    e.salary,
    (SELECT AVG(salary) FROM employees WHERE department_id = e.department_id) as dept_avg,
    (SELECT COUNT(*) FROM sales s WHERE s.sales_rep_id = e.employee_id AND s.sale_amount > 1000) as high_value_deals
FROM employees e
JOIN departments d ON e.department_id = d.department_id
WHERE e.is_active = TRUE
ORDER BY e.salary DESC;
```
*Tugas*: Refaktor total menjadi satu query block atau CTE murni dengan kompleksitas waktu agregasi optimal, tanpa correlated subqueries, menggunakan zero disk spill.

---

## 14. Challenge

### Skenario: Algoritma Fraud Detection Graph Traversal (The Circular Transaction Loop)
Sebuah bank digital mendeteksi pola transaksi pencucian uang di mana dana dikirim berputar antar rekening hingga akhirnya kembali ke akun asal dalam kurun waktu kurang dari 72 jam:  
$$\text{Akun A} \longrightarrow \text{Akun B} \longrightarrow \text{Akun C} \longrightarrow \text{Akun A}$$

Dataset:
*   Tabel `fund_transfers`:
    - `transfer_id BIGINT`
    - `source_account_id INT`
    - `target_account_id INT`
    - `transfer_timestamp TIMESTAMP`
    - `amount NUMERIC(15,2)`

### Persyaratan Tantangan:
1. Rancang kueri **Recursive Common Table Expression (rCTE)** teroptimasi yang mampu menelusuri siklus pengiriman transaksi bertingkat hingga **kedalaman traversal maksimal 5 hop (A $\rightarrow$ B $\rightarrow$ C $\rightarrow$ D $\rightarrow$ E $\rightarrow$ A)**.
2. Batasi loop hanya untuk transaksi di mana setiap rantai hop berikutnya terjadi dalam rentang waktu $0 < \Delta t \le 24\text{ jam}$ setelah transaksi hop sebelumnya diterima, dengan variasi nilai `amount` deviasi tidak lebih dari $\pm 10\%$.
3. Cegah rekursi tak berhingga (*infinite cycle trap*) secara deterministik pada database engine tanpa merusak eksekusi thread.
4. Kueri harus scalable dan dievaluasi mampu berjalan di bawah 60 detik pada tabel dengan 10.000.000 baris data tanpa memicu *stack depth error*. Sertakan konfigurasi tuning yang Anda sarankan.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa konsekuensi arsitektural penggunaan frame default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` dibandingkan `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`?
2. Mengapa klausa `WHERE EXTRACT(YEAR FROM order_date) = 2024` dianggap sebagai anti-pattern pada tabel berindeks?
3. Sebutkan perbedaan mekanis utama antara `RANK()`, `DENSE_RANK()`, dan `ROW_NUMBER()`.
4. Kapan sebuah Cost-Based Optimizer (CBO) cenderung memilih `Hash Join` dibandingkan `Nested Loop Join`?
5. Mengapa penggunaan `UNION ALL` secara umum lebih disarankan daripada `UNION` dalam pipeline analitik data warehouse jika deduplikasi baris tidak diperlukan?

### 5 Pertanyaan Intermediate
6. Jelaskan fenomena *Data Skew* pada sistem database MPP terdistribusi (misalnya Snowflake atau Amazon Redshift) dan bagaimana pengaruhnya terhadap efisiensi kueri JOIN.
7. Mengapa subquery berkorelasi (*correlated subquery*) pada klausa `SELECT` sering kali menjadi sumber utama degradasi performa dibanding penulisan menggunakan Window Functions?
8. Bagaimana pengaruh parameter `work_mem` di PostgreSQL terhadap pemilihan operator antara `HashAggregate` dan `GroupAggregate`?
9. Apa yang dimaksud dengan optimasi *Predicate Pushdown* dan dalam skenario apa CBO gagal mendorong predikat tersebut menembus sebuah CTE?
10. Dalam kasus pemrosesan analitik data besar, jelaskan perbedaan dampak penggunaan B-Tree Index konvensional dibandingkan BRIN (Block Range Index).

### 3 Skenario Kasus Produksi
11. **Skenario Disk Spill**: Kueri analitik dashboard harian mendadak melonjak durasinya dari 10 detik menjadi 18 menit. Setelah dicek via `EXPLAIN (ANALYZE, BUFFERS)`, ditemukan node:  
    `SortMethod: external merge Disk: 142058kB`.  
    Jelaskan langkah investigasi dan minimal 2 solusi teknis konkret untuk menuntaskan masalah tersebut secara permanen.
12. **Skenario Join Fan-Out Financial Error**: Dasbor metrik GMV (Gross Merchandise Value) perusahaan e-commerce menampilkan angka 300% lebih tinggi daripada nominal penagihan payment gateway. Ditemukan developer melakukan kueri menggabungkan tabel `orders`, `order_items`, dan `shipment_deliveries`. Bagaimana mekanisme validasi data yang harus diterapkan untuk membuktikan kesalahan join ini dan tuliskan pola arsitektur SQL yang benar?
13. **Skenario Cardinality Estimation Failure**: Database baru saja menerima penambahan data (*bulk insert*) 50.000.000 transaksi dari migrasi sistem lama. Kueri laporan sederhana berbasis filter `status = 'PENDING'` mengalami hanging. Kueri tersebut menggunakan *Index Scan* alih-alih *Sequential Scan*, padahal baris berstatus `'PENDING'` berjumlah 95% dari tabel. Mengapa optimizer membuat keputusan yang keliru ini dan bagaimana perintah SQL mitigasinya?

---

## 16. Summary

Optimalisasi SQL analitik tingkat enterprise menuntut pemahaman arsitektur mesin database secara holistik—bukan sekadar menghafal sintaksis. BI Analyst tingkat lanjut menjembatani kebutuhan visualisasi data analitik dan efisiensi infrastruktur data warehouse.

Tiga pilar utama arsitektur SQL analitik:
1. **Mechanical Sympathy**: Memahami bagaimana optimizer membaca katalog statistik, memilih algoritma join (`Hash`, `Merge`, `Nested Loop`), dan mengelola alokasi memori internal (`work_mem`, storage spilling).
2. **Precision Engineering**: Memanfaatkan kekuatan native *Window Functions* dengan frame specification eksplisit, teknik mitigasi *Gaps and Islands*, serta menghindari anti-pola pemrosesan *non-sargable predicates* dan subkueri skalar O($N^2$).
3. **Idempotence & Scalability**: Membangun model transformasi data yang meminimalkan *data shuffling*, memanfaatkan teknik eliminasi partisi (*partition pruning*), dan mencegah manipulasi join yang memicu ledakan baris *fan-out*.