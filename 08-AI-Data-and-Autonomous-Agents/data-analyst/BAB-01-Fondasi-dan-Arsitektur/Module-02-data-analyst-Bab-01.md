# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Merekayasa Arsitektur Data Analitik Modern**: Memahami secara mendalam perbedaan mekanis antara *Row-oriented* vs *Column-oriented storage*, eksekusi tervektorisasi (*vectorized execution engine*), dan konsep *storage-compute decoupling*.
- **Membangun Pipeline Pemodelan Data Skala Enterprise**: Menerapkan metodologi dimensional modeling tingkat lanjut (Star Schema, Snowflake Schema, Factless Fact Tables, dan Slowly Changing Dimension/SCD Type 2) menggunakan SQL teroptimasi dan dbt/DuckDB.
- **Mengoptimalkan Kinerja Mesin OLAP**: Mengonfigurasi dan memanfaatkan *predicate pushdown*, *projection pushdown*, *partition pruning*, *dictionary encoding*, serta mengeliminasi bottleneck memori (*fanout joins* dan *spill-to-disk*).
- **Mengimplementasikan Semantic Layer & Data Contracts**: Merancang abstraksi metrik yang konsisten untuk konsumsi multi-platform (BI Dashboard dan LLM/Autonomous Agents) yang tahan terhadap perubahan skema hulu (*upstream breaking changes*).
- **Menerapkan Standar Observabilitas & Pengujian Produksi**: Mengintegrasikan framework validasi data otomatis (*data contracts* dan *anomaly detection assertions*) dalam siklus CI/CD analytics engineering.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Konsep Fondasi Modul 01**: Dasar-dasar siklus data analitik, pengenalan OLTP vs OLAP, dan query SQL tingkat menengah (*grouping*, agregasi dasar, *basic joins*).
- **Lingkungan Komputasi**:
  - Python 3.10+ (dengan virtual environment aktif).
  - DuckDB CLI / library `duckdb` (v0.10+).
  - Polars (`polars>=0.20.0`) & PyArrow (`pyarrow>=14.0.0`).
- **Mental Model**:
  - Paham struktur data tabular dan aljabar relasional dasar.
  - Memahami dasar sistem operasi: perbedaan operasi I/O disk (sequential vs random read), CPU cache hierarchy (L1/L2/L3), dan alokasi RAM.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Komputasi OLAP: Mengapa Row-Oriented Gagal pada Skala Analitik

Dalam OLTP tradisional (misalnya PostgreSQL, MySQL), basis data menggunakan penyimpanan berbasis baris (*row-oriented storage* atau NSM - *N-ary Storage Model*). Seluruh atribut dalam sebuah baris disimpan berurutan secara fisik di disk.

```
NSM (Row-Oriented):
[Row 1: ID, Timestamp, User_ID, Amount, Status] [Row 2: ID, Timestamp, User_ID, Amount, Status]
```

Ketika analitik menjalankan query agregasi:
```sql
SELECT SUM(amount) FROM transactions WHERE status = 'COMPLETED';
```
Mesin baris terpaksa memuat *seluruh tuple* ke dalam memori dari disk/page cache, termasuk atribut yang sama sekali tidak relevan (`Timestamp`, `User_ID`). Hal ini memboroskan *bandwidth* bus memori dan mengotori CPU cache.

Sebaliknya, arsitektur OLAP modern menggunakan model DSM (*Decomposed Storage Model*) atau *column-oriented storage* (seperti Apache Parquet, Apache Arrow, ClickHouse, DuckDB).

```
DSM (Column-Oriented):
Column ID:        [1, 2, 3, ...]
Column Timestamp: [T1, T2, T3, ...]
Column User_ID:   [U1, U2, U3, ...]
Column Amount:    [10.5, 99.0, 50.2, ...]
Column Status:    ['C', 'C', 'F', ...]
```

#### Vectorized Execution vs Volcano Iterator Model
Sistem basis data klasik menggunakan *Volcano iterator model* (evaluasi tuple per tuple melalui metode `next()`). Model ini menghasilkan jutaan panggilan fungsi virtual (*virtual function dispatching*), yang menyebabkan kegagalan prediksi percabangan CPU (*branch misprediction*) dan utilitas cache instruksi yang buruk.

Arsitektur analitik modern (DuckDB, Snowflake, ClickHouse) menerapkan **Vectorized Execution (Bataille/MonetDB/X100 Model)**:
1. Data diproses dalam blok vektor berukuran tetap (misal: 1024 atau 2048 nilai per vektor kolom).
2. Operasi data dilakukan melalui *tight loops* primitif yang memungkinkan kompiler melakukan *loop unrolling* dan vektorisasi otomatis menggunakan instruksi CPU modern (**SIMD - Single Instruction, Multiple Data**: SSE, AVX2, AVX-512, NEON).
3. Data tetap berada di dalam L1/L2 data cache selama transformasi skalar berlangsung, mereduksi latensi akses memori secara signifikan (dari ~100ns RAM ke ~1-4ns L1 cache).

### 3.2. Apache Arrow: Standar Interoperabilitas In-Memory Zero-Copy

Apache Arrow mendefinisikan spesifikasi format memori kolumnar standar yang seragam di lintas bahasa pemrogram (C++, Python, Rust, Go, R, Java).

```
Struktur Array Apache Arrow (Representasi Logis & Fisik):
Length: 4, Null Count: 1
Validity Bitmap: [1, 1, 0, 1]  (Bit 0=Active, Bit 2=Null)
Offsets:         [0, 3, 7, 7, 12] (Untuk tipe variabel seperti String/Binary)
Data Buffer:     ['a','l','i','c','e','b','o','b','d','a','v','e']
```

#### Keuntungan Zero-Copy Sharing:
Tanpa Arrow, pertukaran data dari database analitik ke modul Python (seperti Pandas) memerlukan proses *serialization* dan *deserialization* (mengonversi byte C++ ke objek Python `PyObject*`, menghabiskan 80% siklus komputasi analitik). Dengan Arrow IPC, buffer memori dapat langsung dipetakan (*memory-mapped*) tanpa alokasi ulang dan tanpa copy byte, menghasilkan transmisi data berkecepatan *line-rate*.

### 3.3. Metadata-Driven Execution: Predicate Pushdown & Parquet Footers

File Parquet membagi data ke dalam *Row Groups* (umumnya 128MB hingga 512MB per row group). Di dalam setiap *Row Group*, data dipecah lagi ke dalam *Column Chunks* dan *Pages*.

```
+-----------------------------------------------------------+
|                      Parquet File                         |
| +-------------------------------------------------------+ |
| | Row Group 0 (e.g. 1,000,000 baris)                    | |
| |  [Column Chunk: transaction_id]                       | |
| |  [Column Chunk: amount]                               | |
| |  [Column Chunk: created_at]                           | |
| +-------------------------------------------------------+ |
| +-------------------------------------------------------+ |
| | Row Group 1 (e.g. 1,000,000 baris)                    | |
| |  ...                                                  | |
| +-------------------------------------------------------+ |
| Footer: File Metadata, Schema, Stats (Min/Max/Null per  | |
|         column chunk & row group)                       | |
+-----------------------------------------------------------+
```

Ketika query analitik menyertakan filter `WHERE created_at >= '2026-03-01'`:
1. Query engine membaca **Footer** file terlebih dahulu (beberapa kilobyte terakhir dari file).
2. Engine membaca statistik `Min` dan `Max` untuk `created_at` pada masing-masing Row Group.
3. **Predicate Pushdown**: Jika `Max(created_at)` di Row Group 0 bernilai `'2026-02-28'`, maka seluruh Row Group 0 diabaikan (*skipped*) secara utuh tanpa membaca bytes data kolomnya sama sekali.

---

## 4. Why & What

| Dimensi | Paradigma Klasik (Tradisional) | Paradigma Modern (Production-Ready) |
| :--- | :--- | :--- |
| **Pipeline Data** | **ETL**: Data ditransformasikan di luar target storage menggunakan server middleware tersendiri sebelum dimuat. | **ELT**: Muat data mentah ke target storage performa tinggi, transformasi dieksekusi secara terdistribusi/vektorisasi di dalam engine. |
| **Pola Penyimpanan** | Normalisasi Database (3NF/BCNF) untuk menghemat ruang disk dan mencegah anomali tulis. | Dimensional Modeling (Kimball Star Schema / OBT - *One Big Table*) teroptimasi untuk query analitik berkecepatan tinggi. |
| **Format File** | CSV, JSON (berbasis teks, lambat di-parse, tidak ada metadata tipe data dan statistik). | Parquet, Iceberg, Arrow (biner, kolumnar, kompresi ZSTD/Snappy, *self-describing*). |
| **Konsumsi Metrik** | Logika perhitungan metrik di-hardcode langsung di dalam masing-masing dashboard visualisasi (Tableau/PowerBI/Metabase). | **Semantic Layer**: Definisi metrik tersentralisasi sebagai kode (*metrics-as-code*), disajikan seragam untuk BI dan Autonomous Agents. |
| **Kontrak Data** | Skema rapuh (*brittle*), aplikasi hulu dapat mengubah nama kolom atau tipe data sewaktu-waktu dan merusak analitik hilir. | **Data Contracts**: Validasi skema dan semantik divalidasi langsung di batas producer-consumer menggunakan CI dan assertions. |

---

## 5. How (Workflow Detail)

Alur kerja arsitektur analitik enterprise modern mencakup lima tahap berurutan:

```
[Upstream OLTP / Events]
           │
           ▼ (Ingestion Raw Data)
[Raw Ingestion / Landing Zone] (Parquet/Object Store)
           │
           ▼ (Schema Enforcement & Cleaning)
[Staging Layer] (dbt / DuckDB / SQL Models)
           │
           ▼ (Dimensional Modeling: Dim, Fact, SCD2)
[Intermediate / Core Layer] (Kimball Dimensional Modeling)
           │
           ▼ (Business Aggregation & Optimization)
[Marts Layer / Analytical Serving]
           │
           ▼ (Metrics as Code & Protocol Enforcement)
[Semantic Layer (Cube / MetricFlow / DuckDB Semantic Engine)]
           │
     ┌─────┴──────────────┐
     ▼                    ▼
[BI Dashboards]   [Autonomous AI Agents]
```

1. **Ingestion & Raw Landing**: Data diekstraksi dari database relasional atau event streaming tanpa transformasi destruktif, disimpan dalam format immutable Parquet berpartisi (`date=YYYY-MM-DD`).
2. **Staging (`stg_`)**: Membersihkan tipe data (*casting*), standarisasi penamaan kolom (misal: camelCase diubah menjadi snake_case), menangani duplikasi level teknis, dan mengisolasi logika sumber data.
3. **Core / Dimensional Modeling (`int_`, `dim_`, `fct_`)**:
   - Membangun *Conformed Dimensions* (misal: `dim_customers`, `dim_products`).
   - Menerapkan *SCD Type 2* untuk merekam histori perubahan entitas sepanjang waktu.
   - Membangun *Fact Tables* terperinci (*Atomic Grain*) dan *Aggregated Facts*.
4. **Data Marts (`fct_`, `mart_`)**: Layer denormalisasi yang disesuaikan dengan domain bisnis tertentu (Finansial, Marketing, Operasional).
5. **Semantic Layer**: Mendefinisikan agregasi metrik (seperti *Customer Churn Rate*, *Gross Revenue*, *ARR*) beserta dimensinya secara terpusat. Ketika LLM Agent membutuhkan metrik data, agent tidak menulis SQL mentah dari nol, melainkan meminta data melalui Semantic Layer via API atau alat analitik terstruktur.

---

## 6. Analogy & Diagram ASCII

### Analogi Pustakawan: Row-Store vs Column-Store
Bayangkan sebuah perpustakaan berisi jutaan buku catatan sensus kependudukan. Setiap halaman berisi satu baris data warga: Nama, Umur, Pekerjaan, Pendapatan.

- **Row-Store**: Buku disusun per individu. Jika Anda diminta mencari "Berapa rata-rata pendapatan warga?", Anda harus membuka jutaan halaman satu per satu, membaca seluruh baris nama dan pekerjaan, hanya untuk mencatat nominal pendapatan di ujung baris.
- **Column-Store**: Data dipisah ke dalam buku-buku khusus. Ada satu buku khusus yang hanya memuat seluruh angka "Pendapatan". Anda hanya perlu membuka satu buku tersebut dan menghitung totalnya dalam hitungan detik tanpa terganggu oleh jutaan teks nama dan alamat.

### Diagram: Aliran Eksekusi Teroptimasi (Projection, Predicate Pushdown, SIMD)

```
Query: 
SELECT status, SUM(amount) 
FROM read_parquet('transactions_*.parquet') 
WHERE created_at >= '2026-01-01' 
GROUP BY status;

DISK / OBJECT STORAGE
┌──────────────────────────────────────────────────────────────┐
│ Parquet File                                                 │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Row Group 0: created_at Min: 2025-01-01, Max: 2025-12-31  │ │ ──> DILEWATI SECARA TOTAL!
│ └──────────────────────────────────────────────────────────┘ │      (Predicate Pushdown via Metadata)
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Row Group 1: created_at Min: 2026-01-01, Max: 2026-06-30  │ │
│ │  ┌──────────────┐ ┌──────────────┐ ┌───────────────────┐  │ │
│ │  │ Col: status  │ │ Col: amount  │ │ Col: user_metadata│  │ │ ──> user_metadata DIABAIKAN!
│ │  └──────┬───────┘ └──────┬───────┘ └─────────┬─────────┘  │ │      (Projection Pushdown)
└───────────┼────────────────┼───────────────────┼─────────────┘
            │                │                   │ (Not read)
            ▼                ▼                   X
MEMORY (Arrow Buffers - 2048 rows / batch)
┌───────────────────────────┬─────────────────────────────────┐
│ Vector Chunk (status)     │ Vector Chunk (amount)           │
│ ['SUCCESS', 'SUCCESS', ..]│ [150.00, 240.50, 12.00, ..]     │
└─────────────┬─────────────┴────────────────┬────────────────┘
              │                              │
              ▼                              ▼
CPU REGISTERS & CACHE (SIMD Vector Processing)
┌─────────────────────────────────────────────────────────────┐
│ [ AVX-512 Register: 8 x 64-bit float Additions per cycle ]  │
└─────────────────────────────┬───────────────────────────────┘
                              ▼
                        HASIL AGREGASI
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Ingest, Process, and Analyze with In-Memory Vectorization (DuckDB)

Contoh ini menunjukkan performa eksekusi vektorisasi lokal menggunakan DuckDB langsung pada file data mentah.

```python
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

# 1. Setup Data Dummy Berukuran Signifikan Secara Efisien
table = pa.table({
    "transaction_id": range(1, 100001),
    "user_id": [i % 500 for i in range(1, 100001)],
    "amount": [float((i * 17) % 500) for i in range(1, 100001)],
    "status": ["COMPLETED" if i % 4 != 0 else "FAILED" for i in range(1, 100001)],
    "created_date": ["2026-03-01" if i % 2 == 0 else "2026-03-02" for i in range(1, 100001)]
})
pq.write_table(table, "transactions.parquet")

# 2. Vectorized Analytic Query menggunakan DuckDB
con = duckdb.connect()

query = """
EXPLAIN ANALYZE
SELECT 
    status,
    COUNT(transaction_id) as total_tx,
    ROUND(SUM(amount), 2) as total_amount,
    ROUND(AVG(amount), 2) as avg_amount
FROM read_parquet('transactions.parquet')
WHERE created_date = '2026-03-01'
GROUP BY status;
"""

print(con.execute(query).fetchone()[1])
print("\nHasil Eksekusi:")
print(con.execute("""
SELECT 
    status,
    COUNT(transaction_id) as total_tx,
    ROUND(SUM(amount), 2) as total_amount,
    ROUND(AVG(amount), 2) as avg_amount
FROM read_parquet('transactions.parquet')
WHERE created_date = '2026-03-01'
GROUP BY status;
""").df())
```

### 7.2. Practical Example: Implementasi SCD Type 2 Menggunakan Pure SQL & DuckDB

Menjaga histori perubahan profil analitik (Slowly Changing Dimension Type 2) adalah salah satu tugas analitik data terpenting di industri skala produksi.

```python
import duckdb

con = duckdb.connect()

# 1. Tabel Dimensi Eksisting (Snapshot Hari Ini)
con.execute("""
CREATE OR REPLACE TABLE dim_customers_scd2 (
    customer_sk BIGINT,
    customer_id INT,
    tier VARCHAR,
    credit_limit DECIMAL(10, 2),
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
);

INSERT INTO dim_customers_scd2 VALUES
(1, 101, 'BRONZE', 1000.00, '2026-01-01 00:00:00', '2026-03-01 12:00:00', FALSE),
(2, 101, 'SILVER', 2500.00, '2026-03-01 12:00:00', '9999-12-31 23:59:59', TRUE),
(3, 102, 'GOLD', 5000.00, '2026-01-15 08:00:00', '9999-12-31 23:59:59', TRUE);
""")

# 2. Data Mutasi Baru (Source Stream CDC / Sync Harian pada 2026-03-31)
con.execute("""
CREATE OR REPLACE TABLE raw_customer_updates (
    customer_id INT,
    tier VARCHAR,
    credit_limit DECIMAL(10, 2),
    updated_at TIMESTAMP
);

INSERT INTO raw_customer_updates VALUES
-- Customer 101 upgrade ke GOLD (SCD2 Change)
(101, 'GOLD', 7500.00, '2026-03-31 10:00:00'),
-- Customer 103 baru (New Record)
(103, 'BRONZE', 1500.00, '2026-03-31 10:00:00');
""")

# 3. Eksekusi Atomic Merge / Upsert Logic untuk SCD Type 2
con.execute("""
-- Langkah A: Identifikasi Record yang Berubah dan Butuh Expire
CREATE OR REPLACE TEMP TABLE scd2_records_to_expire AS
SELECT 
    target.customer_sk,
    source.updated_at AS new_valid_to
FROM dim_customers_scd2 target
JOIN raw_customer_updates source
    ON target.customer_id = source.customer_id
WHERE target.is_current = TRUE
  AND (target.tier != source.tier OR target.credit_limit != source.credit_limit);

-- Langkah B: Expire Record Lama
UPDATE dim_customers_scd2
SET 
    valid_to = scd2_records_to_expire.new_valid_to,
    is_current = FALSE
FROM scd2_records_to_expire
WHERE dim_customers_scd2.customer_sk = scd2_records_to_expire.customer_sk;

-- Langkah C: Masukkan Baris Versi Baru & Pelanggan Baru
INSERT INTO dim_customers_scd2
SELECT
    (SELECT COALESCE(MAX(customer_sk), 0) FROM dim_customers_scd2) + ROW_NUMBER() OVER () as customer_sk,
    source.customer_id,
    source.tier,
    source.credit_limit,
    source.updated_at as valid_from,
    TIMESTAMP '9999-12-31 23:59:59' as valid_to,
    TRUE as is_current
FROM raw_customer_updates source
LEFT JOIN dim_customers_scd2 target
    ON source.customer_id = target.customer_id 
    AND target.is_current = TRUE
WHERE target.customer_sk IS NULL 
   OR (target.tier != source.tier OR target.credit_limit != source.credit_limit);
""")

print("=== DIM CUSTOMERS SCD 2 SETELAH UPDATE ===")
print(con.execute("SELECT * FROM dim_customers_scd2 ORDER BY customer_id, valid_from").df())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Konteks Kasus
**Perusahaan**: *FinTech PayStream Asia*  
**Skala**: Memproses 120 juta transaksi per hari dengan nilai transaksi bruto (GTV) harian mencapai USD 45 juta.  
**Masalah**: 
1. Eksekutif dan Lead Data Analyst mengeluhkan metrik "Gross Revenue" memiliki definisi berbeda antara dashboard Tim Finance dan Dashboard Tim Risk.
2. Query analitik harian pada PostgreSQL read-replica memicu saturasi CPU 100% dan OOM (*Out-of-Memory*) crash berulang kali.
3. Autonomous Risk Agent yang mengaudit pola anomali secara berkala mengalami *timeout* saat membaca tabel transaksi yang berukuran lebih dari 10 Terabyte.

### Desain Solusi Arsitektur Produksi

```
[OLTP Postgres Source]
         │ (CDC via Debezium / Kafka)
         ▼
[S3 Object Storage (Raw Parquet - Partitioned by date=YYYY-MM-DD)]
         │
         ▼ (DuckDB In-Memory Pre-Compute / dbt Pipeline)
[Warehouse / Lakehouse Engine (Core Marts)]
   - dim_merchants (SCD Type 2)
   - dim_users (SCD Type 2)
   - fct_transactions (Clustered by status, merchant_id)
         │
         ▼
[Universal Semantic Layer] (Single Source of Truth)
   - Metric: gross_revenue = SUM(amount * fee_rate)
   - Metric: chargeback_rate = COUNT(failed_tx) / COUNT(total_tx)
         │
   ┌─────┴────────────────────────────┐
   ▼                                  ▼
[Executive BI Platform]    [Autonomous Risk AI Agent]
 (Zero Calculation Logic)   (Consumes Standard Metrics API)
```

### Implementasi Transformasi: Production-Grade Analytical Marts

```sql
-- Pipeline Script: core_fct_transactions.sql
-- Optimasi Skala Besar: Window functions untuk Sessionization & Cumulative Windowing
WITH deduplicated_source AS (
    SELECT 
        transaction_id,
        user_id,
        merchant_id,
        amount,
        fee_rate,
        status,
        event_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id 
            ORDER BY ingested_at DESC
        ) as dedupe_rank
    FROM read_parquet('s3://paystream-lake/raw/transactions/year=2026/month=03/*.parquet')
),
valid_transactions AS (
    SELECT 
        transaction_id,
        user_id,
        merchant_id,
        amount,
        fee_rate,
        status,
        event_timestamp
    FROM deduplicated_source
    WHERE dedupe_rank = 1
),
enriched_transactions AS (
    SELECT 
        t.transaction_id,
        t.user_id,
        t.merchant_id,
        t.amount,
        t.fee_rate,
        (t.amount * t.fee_rate) AS calculated_revenue,
        t.status,
        t.event_timestamp,
        -- Running aggregate menggunakan sliding frame berbasis waktu
        SUM(t.amount) OVER(
            PARTITION BY t.user_id 
            ORDER BY t.event_timestamp 
            RANGE BETWEEN INTERVAL 1 HOUR PRECEDING AND CURRENT ROW
        ) AS user_1hr_cumulative_velocity
    FROM valid_transactions t
)
SELECT 
    et.transaction_id,
    et.user_id,
    et.merchant_id,
    et.amount,
    et.calculated_revenue,
    et.status,
    et.event_timestamp,
    et.user_1hr_cumulative_velocity,
    -- Deteksi instan indikator fraud untuk Agent
    CASE 
        WHEN et.user_1hr_cumulative_velocity > 50000.00 THEN TRUE 
        ELSE FALSE 
    END AS is_velocity_alert
FROM enriched_transactions et;
```

**Dampak Solusi**:
- Latensi query agregasi harian turun dari **48 menit** menjadi **2,8 detik** berkat partisi Parquet dan eliminasi deduplikasi di level konsumsi.
- Discrepancy metric antara Risk dan Finance turun menjadi **0%** karena seluruh metrik dievaluasi melalui single canonical data model.

---

## 9. Trade-offs (Arsitektur & Rekayasa Analitik)

```
                    ┌───────────────────────────────┐
                    │ Latensi Rendah / Kecepatan    │
                    └──────────────┬────────────────┘
                                  / \
                                 /   \
                                /     \
                               /       \
                              /         \
  ┌──────────────────────────┐           ┌──────────────────────────┐
  │ Fleksibilitas Ad-Hoc /   ├───────────┤ Efisiensi Biaya Storage  │
  │ Granularitas Atomic      │           │ & Pemrosesan             │
  └──────────────────────────┘           └──────────────────────────┘
```

### Analisis Pertimbangan Desain
1. **Pre-Aggregated Data Marts (OLAP Cubes) vs Ad-Hoc On-The-Fly Querying**:
   - *Pre-aggregation*: Waktu respon query sub-detik (<200ms) untuk dashboard. Namun, kehilangan granularitas asli (tidak dapat melakukan *drill-down* ke level transaksi individu) dan memerlukan biaya komputasi tambahan saat jadwal update data dijalankan.
   - *On-The-Fly (Raw OLAP)*: Memberikan fleksibilitas eksplorasi maksimal untuk Data Analyst dan Autonomous Agent. Namun, biaya komputasi per query dapat membengkak secara linier jika metadata pruning tidak optimal.

2. **One Big Table (OBT) vs Star Schema (Kimball)**:
   - *OBT (Full Denormalization)*: Tidak ada operasi `JOIN` saat query time, pemrosesan disk-to-CPU sangat cepat pada mesin kolumnar. Kekurangan: *data duplication* masif, *write amplification*, serta risiko anomali data jika terjadi mutasi data historis.
   - *Star Schema*: Mengurangi redundansi data, struktur bersih, dan pembaruan data referensi (SCD) terisolasi rapi. Kekurangan: Memerlukan alokasi hash join memory yang besar saat mengombinasikan puluhan dimensi.

3. **Storage-Compute Decoupling vs Colocated Engine**:
   - *Decoupled (e.g., S3/GCS + DuckDB/Snowflake)*: Fleksibilitas penskalaan independen dan biaya penyimpanan sangat murah. Namun, memperkenalkan latensi jaringan (*network I/O bottleneck*) saat membaca data awal.

---

## 10. Common Mistakes & Troubleshooting

### Skenario 1: Skew Joins Menyebabkan OOM (Out of Memory)
- **Gejala**: Pipeline analitik berjalan lancar pada 95% tahapan, tetapi tiba-tiba *hang* atau crash karena kehabisan RAM pada langkah akhir `JOIN` antara tabel transaksi dan profil pengguna.
- **Root Cause**: Terjadi *data skew* ekstrem. Sebagai contoh, ada nilai default `user_id = NULL` atau `user_id = 'GUEST'` yang berjumlah puluhan juta baris. Semua data ini dialokasikan ke hash bucket/thread memori yang sama.
- **Solusi Troubleshooting**:
  ```sql
  -- Pisahkan data null/default sebelum Join, atau lakukan Skew Salting
  SELECT 
      t.transaction_id,
      COALESCE(u.user_tier, 'ANONYMOUS') AS user_tier
  FROM (
      SELECT * FROM transactions WHERE user_id IS NOT NULL
  ) t
  LEFT JOIN dim_users u ON t.user_id = u.user_id
  UNION ALL
  SELECT 
      transaction_id,
      'ANONYMOUS' AS user_tier
  FROM transactions 
  WHERE user_id IS NULL;
  ```

### Skenario 2: Fanout Join yang Menggelembungkan Agregasi Finansial
- **Gejala**: Metrik `SUM(payment_amount)` pada laporan bulanan tiba-tiba menjadi dua atau tiga kali lipat lebih besar daripada uang riil yang masuk di mutasi rekening bank.
- **Root Cause**: Terjadi relasi *One-to-Many* yang tidak terdeteksi saat menggabungkan tabel `fct_orders` dengan `fct_order_discounts` atau `fct_shipments`, sehingga baris order diduplikasi sebelum proses penjumlahan berlangsung.
- **Solusi**: Agregasikan dimensi anak secara independen ke tingkat *grain* yang sama sebelum melakukan `JOIN`:
  ```sql
  -- JANGAN: Menggabungkan tabel shipment langsung ke orders
  -- LAKUKAN: Pra-agregasi tabel anak ke tingkat Order
  WITH aggregated_shipments AS (
      SELECT 
          order_id, 
          COUNT(shipment_id) as total_shipments,
          SUM(shipping_fee) as total_shipping_fee
      FROM fct_shipments
      GROUP BY order_id
  )
  SELECT 
      o.order_id,
      o.order_amount,
      COALESCE(s.total_shipping_fee, 0) AS total_shipping_fee
  FROM fct_orders o
  LEFT JOIN aggregated_shipments s ON o.order_id = s.order_id;
  ```

### Skenario 3: Partition Pruning Gagal Akibat Penggunaan Fungsi pada Kolom Filter
- **Gejala**: Query memindai seluruh direktori data mentah (misal: 5 TB data) meskipun klausul `WHERE` sudah disertakan.
- **Root Cause**: Kolom partisi dibungkus oleh fungsi sehingga *query planner* tidak dapat memetakan filter ke path folder.
  ```sql
  -- ANTI-PATTERN: Pruning GAGAL
  WHERE CAST(created_at AS VARCHAR) LIKE '2026-03%'
  
  -- PRODUCTION PATTERN: Pruning BERJALAN OPTIMAL
  WHERE created_at >= '2026-03-01 00:00:00' AND created_at < '2026-04-01 00:00:00'
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis model atau pipeline data analitik ke lingkungan *production*:

- [ ] **Deterministic Ordering**: Setiap penggunaan ekspresi window function (`ROW_NUMBER()`, `DENSE_RANK()`) selalu memiliki klausa `ORDER BY` yang unik untuk mencegah *non-deterministic output*.
- [ ] **Idempotensi Penuh**: Seluruh transformasi tabel bertipe *incremental* dapat dijalankan berulang kali untuk rentang tanggal yang sama tanpa menghasilkan data ganda (*atomic overwrite / delete-insert pattern*).
- [ ] **Static Code Analysis (SQL Quality)**: Lulus linting menggunakan `SQLFluff` sesuai konvensi format tim.
- [ ] **Type Narrowing**: Tipe data skalar dioptimalkan; jangan menggunakan `BIGINT` untuk kolom status bernilai 1-5 (gunakan `TINYINT` / `SMALLINT`), dan hindari `VARCHAR` tanpa limit jika dapat dikelompokkan sebagai enum/dictionary.
- [ ] **Audit Trail Columns**: Semua tabel analitik menyertakan kolom sistem audit wajib: `_created_at_utc`, `_updated_at_utc`, dan `_source_file_path`.
- [ ] **Data Contracts Enforcement**: Skema input dan output diverifikasi secara otomatis (cek tipe data, nilai nullability, dan batasan rentang nilai).

---

## 12. Hands-on Practice

Target pengerjaan pada direktori: `hands-on/m02/`

### Langkah 1: Setup Lingkungan & Dependensi
Buka terminal dan jalankan urutan perintah berikut:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
python -m venv venv
source venv/bin/activate  # Untuk Windows: venv\Scripts\activate
pip install duckdb polars pyarrow
```

### Langkah 2: Buat Pipeline Generator Data Mentah
Buat file `generator.py` untuk mensimulasikan data transaksi enterprise mentah dalam format Parquet:

```python
# generator.py
import pyarrow as pa
import pyarrow.parquet as pq
import random
from datetime import datetime, timedelta

def generate_enterprise_data(records=250000):
    print(f"Generating {records} records...")
    start_date = datetime(2026, 3, 1)
    
    data = {
        "tx_id": [f"TX-{1000000 + i}" for i in range(records)],
        "account_id": [f"ACC-{random.randint(100, 2500)}" for i in range(records)],
        "tx_type": [random.choice(["TRANSFER", "WITHDRAWAL", "PAYMENT", "FEE"]) for _ in range(records)],
        "amount": [round(random.uniform(5.0, 5000.0), 2) for _ in range(records)],
        "fee": [round(random.uniform(0.1, 15.0), 2) for _ in range(records)],
        "status": [random.choice(["SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "SUSPICIOUS"]) for _ in range(records)],
        "tx_time": [start_date + timedelta(seconds=random.randint(0, 86400 * 30)) for _ in range(records)]
    }
    
    table = pa.Table.from_pydict(data)
    pq.write_table(table, "raw_transactions.parquet", compression="snappy", row_group_size=50000)
    print("Selesai: 'raw_transactions.parquet' berhasil dibuat.")

if __name__ == "__main__":
    generate_enterprise_data()
```

Jalankan:
```bash
python generator.py
```

### Langkah 3: Bangun Production Analytical Pipeline Engine
Buat file `pipeline.py` yang mereplikasi pipeline transformasi analitik end-to-end:

```python
# pipeline.py
import duckdb
import time

def run_analytical_pipeline():
    con = duckdb.connect(database="analytics_prod.db")
    
    print("[1/3] Menjalankan Layer Staging & Enforce Typings...")
    con.execute("""
    CREATE OR REPLACE TABLE stg_transactions AS
    SELECT 
        CAST(tx_id AS VARCHAR) AS transaction_id,
        CAST(account_id AS VARCHAR) AS account_id,
        UPPER(TRIM(tx_type)) AS transaction_type,
        CAST(amount AS DECIMAL(12, 2)) AS amount,
        CAST(fee AS DECIMAL(10, 2)) AS fee,
        UPPER(TRIM(status)) AS status,
        CAST(tx_time AS TIMESTAMP) AS transaction_timestamp
    FROM read_parquet('raw_transactions.parquet')
    WHERE amount > 0;
    """)

    print("[2/3] Membangun Analytical Mart: Account Rolling Analytics...")
    con.execute("""
    CREATE OR REPLACE TABLE mart_account_risk_velocity AS
    WITH ranked_transactions AS (
        SELECT 
            transaction_id,
            account_id,
            transaction_type,
            amount,
            fee,
            status,
            transaction_timestamp,
            -- Window metric: 3 transaksi terakhir dari akun yang sama
            AVG(amount) OVER (
                PARTITION BY account_id 
                ORDER BY transaction_timestamp 
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
            ) AS avg_prior_3_tx_amount,
            -- Rolling total 7 hari
            SUM(amount) OVER (
                PARTITION BY account_id 
                ORDER BY transaction_timestamp 
                RANGE BETWEEN INTERVAL 7 DAYS PRECEDING AND CURRENT ROW
            ) AS rolling_7d_total_volume
        FROM stg_transactions
    )
    SELECT 
        *,
        CASE 
            WHEN avg_prior_3_tx_amount > 0 AND amount > (avg_prior_3_tx_amount * 4) THEN TRUE
            ELSE FALSE
        END AS is_spike_anomaly
    FROM ranked_transactions;
    """)

    print("[3/3] Validasi Assertions Kontrak Data...")
    audit_res = con.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN amount <= 0 THEN 1 END) as invalid_amount_records,
        COUNT(CASE WHEN transaction_id IS NULL THEN 1 END) as null_pks
    FROM mart_account_risk_velocity
    """).fetchall()

    print(f"Hasil Audit Data: {audit_res}")
    
    # Jalankan verifikasi assertion
    assert audit_res[0][1] == 0, "DATA CONTRACT BREACH: Ditemukan nilai amount invalid <= 0"
    assert audit_res[0][2] == 0, "DATA CONTRACT BREACH: Ditemukan Primary Key bernilai NULL"
    
    print("\nPipeline Berhasil Dijalankan Tanpa Pelanggaran Kontrak Data.")
    con.close()

if __name__ == "__main__":
    start = time.time()
    run_analytical_pipeline()
    print(f"Total waktu eksekusi: {time.time() - start:.2f} detik")
```

Jalankan skrip:
```bash
python pipeline.py
```

---

## 13. Exercise

### Level Easy: Analisis Agregasi Pivot Berkecepatan Tinggi
- **Instruksi**: Buat query SQL di DuckDB untuk membaca `raw_transactions.parquet` dan buat rekap matriks jumlah transaksi yang berhasil (`SUCCESS`) berdasarkan `transaction_type` secara dinamis/pivot untuk setiap minggu.
- **Kriteria Penerimaan**:
  - Kolom hasil harus berupa: `week_starting_date`, `PAYMENT`, `TRANSFER`, `WITHDRAWAL`, `FEE`.
  - Wajib menggunakan sintaks `PIVOT` DuckDB native tanpa operasi string parsing yang lambat.

### Level Medium: Deteksi Session Gap Analysis
- **Instruksi**: Buat model data SQL untuk menghitung sesi aktivitas setiap `account_id`. Sebuah sesi dianggap *berakhir* dan sesi baru dimulai apabila selisih waktu antara transaksi saat ini dan transaksi sebelumnya pada akun yang sama melebihi **48 jam**.
- **Kriteria Penerimaan**:
  - Tampilkan `session_id` sintesis (format: `{account_id}-{session_counter}`).
  - Hitung total nominal (`SUM(amount)`) dan durasi transaksi (dalam menit) untuk masing-masing sesi.

### Level Hard: Komputasi Retensi Pelanggan (Classic Cohort Retention Matrix)
- **Instruksi**: Hitung cohort bulanan retensi akun transaksi. Identifikasi bulan pertama transaksi masing-masing `account_id` (Cohort Month). Kemudian lacak persentase akun yang kembali aktif bertransaksi pada Month 1, Month 2, dan Month 3 berikutnya.
- **Kriteria Penerimaan**:
  - Output berupa matriks berformat: `cohort_month`, `cohort_size`, `m1_retention_pct`, `m2_retention_pct`, `m3_retention_pct`.
  - Dilarang keras melakukan kalkulasi di memori Python; seluruh kalkulasi *cohort logic* harus berjalan murni di dalam analytical SQL engine secara deterministik dan optimal.

---

## 14. Challenge (Tantangan Studi Kasus Nyata)

### Skenario Kasus Kompleks
Sebuah institusi pertukaran aset kripto memproses miliaran log *orderbook updates* per hari. Tim Autonomous Risk Intelligence Agent memerlukan pipeline analitik *Streaming-to-Batch Reconciliation* untuk mendeteksi indikasi *wash trading* (dua akun terafiliasi saling jual-beli aset yang sama berulang kali dalam durasi hitungan detik untuk memanipulasi volume).

### Persyaratan Tantangan:
1. **Desain Skema**: Rancang skema dimensional data analitik yang mampu menampung data trades berkecepatan tinggi sekaligus memetakan jejaring akun yang terafiliasi (relasi graf n-derajat).
2. **Optimasi Batasan Memori**: Skrip yang dibangun harus mampu memproses datasets log sebesar minimal 10 juta baris pada mesin pengembang lokal (spesifikasi terbatas: RAM 8 GB) tanpa memicu crash `MemoryError` atau sistem *swap freezing*.
3. **Logika Analitik Multi-Dimensi**:
   - Identifikasi pasangan transaksi (`seller_id`, `buyer_id`) yang saling bertukar aset identik dengan selisih waktu kurang dari 5 detik.
   - Buat algoritma perhitungan *circular volume score* di dalam query analitik.
4. **Data Contract Failure Handling**: Rancang mekanisme *circuit breaker* otomatis: jika volume data kotor/malformed pada ingestion file melebihi 0.1%, hentikan proses komputasi, kirim *alert payload* JSON ke autonomous incident handler, dan lakukan *rollback atomic* ke kondisi data stabil terakhir.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)

1. Mengapa format penyimpanan kolumnar (*column-oriented*) seperti Parquet jauh lebih efisien untuk beban kerja agregasi analitik dibandingkan format baris (*row-oriented*) seperti CSV atau PostgreSQL heap page?
2. Apa yang dimaksud dengan *Predicate Pushdown*, dan komponen apa di dalam file Parquet yang memungkinkan query engine melompati pembacaan blok data yang tidak relevan?
3. Apa perbedaan fundamental antara proses deserialisasi data klasik (misal: JSON/CSV parser ke Python) dibanding *Zero-Copy Sharing* menggunakan Apache Arrow?
4. Dalam pemodelan dimensional Kimball, apa yang menjadi pembeda utama antara tabel *Fact* dan tabel *Dimension*?
5. Mengapa penggunaan indeks B-Tree standar sering kali dihindari pada sistem analitik data skala besar berbasis *column-store*?

### Bagian 2: Intermediate (Penerapan & Analisis Pola)

6. Jelaskan apa risiko matematis dari penggunaan window function `RANGE BETWEEN` jika kolom penentu urutan (`ORDER BY`) tidak memiliki nilai yang bersifat *strictly monotonic / unique*!
7. Bagaimana arsitektur *Vectorized Execution* (seperti yang digunakan DuckDB atau ClickHouse) memanfaatkan register CPU modern untuk mempercepat pemrosesan query analitik?
8. Sebuah query analitik mengalami degradasi performa drastis setelah ditambahkan operasi `LEFT JOIN` ke dimensi baru. Setelah diinspeksi, jumlah baris output membengkak secara signifikan dari tabel faktanya. Masalah struktural apa yang sedang terjadi, dan bagaimana cara memitigasinya?
9. Apa fungsi utama *Semantic Layer* dalam menjembatani kebutuhan data antara dashboard visualisasi tradisional dengan modul AI / Autonomous Agent?
10. Dalam implementasi Slowly Changing Dimension Type 2 (SCD2), jelaskan mengapa penggunaan *Surrogate Key* sintetis berbasis hash atau integer sekuensial lebih disarankan daripada hanya mengandalkan *Natural Key* dari sistem sumber!

### Bagian 3: Production Case Scenarios (Analisis & Solusi Lapangan)

11. **Skenario A (OOM Window Processing)**:  
    Pipeline agregasi Anda gagal memproses query analitik harian berikut pada mesin dengan RAM 16GB:
    ```sql
    SELECT 
        user_id,
        ARRAY_AGG(transaction_id ORDER BY event_time) OVER (PARTITION BY tenant_id) 
    FROM enterprise_events;
    ```
    Data memiliki satu `tenant_id` bernilai `'DEFAULT'` yang mencakup 80% dari total 50 juta baris data. Analisis penyebab kegagalan alokasi memori query engine ini dan tuliskan refactoring query yang menjamin eksekusi streaming/chunking yang aman!

12. **Skenario B (Data Contract Silent Poisoning)**:  
    Tim upstream microservices mengubah tipe kolom `gross_amount` dari nilai numerik (contoh: `1250.50`) menjadi string berformat mata uang lokal (contoh: `"IDR 1.250,50"`). Akibatnya, query analitik bulanan mengevaluasi nilai tersebut menjadi `NULL` tanpa memicu error crash, yang berujung pada terbitnya laporan keuangan tahunan yang salah. Rancang arsitektur pengujian assertions dan Data Contract enforcement otomatis di layer ingest untuk mencegah skenario fatal ini!

13. **Skenario C (Parquet Small Files Problem)**:  
    Sebuah sistem streaming menulis file Parquet setiap 10 detik ke data lake S3, menghasilkan 8.640 file kecil per hari dengan ukuran masing-masing ~50KB. Ketika Data Analyst membaca data selama 1 bulan menggunakan DuckDB/Athena, waktu query membutuhkan waktu hingga 20 menit meskipun total ukuran data hanya ~12GB. Jelaskan akar masalah performa dari fenomena I/O ini dan tuliskan workflow kompeksi (*compaction strategy*) yang ideal!

---

## 16. Summary

1. **Arsitektur Berbasis Kolom & Vektorisasi**: Lompatan performa analitik data modern bertumpu pada penyimpanan berorientasi kolom (Parquet), representasi data in-memory terstandarisasi (Arrow), serta mesin eksekusi CPU berbasis vektor (SIMD) yang mengeliminasi overhead instruksi konvensional.
2. **Kekuatan Metadata-Driven I/O**: Fitur seperti *Projection Pushdown* dan *Predicate Pushdown* menghemat I/O secara masif dengan cara hanya membaca kolom yang dibutuhkan dan melompati jutaan baris data yang tidak relevan secara langsung melalui metadata statistik file footer.
3. **Disiplin Pemodelan Data Relasional Modern**: Keberhasilan analitik enterprise ditentukan oleh konsistensi data modeling: pemisahan fakta dan dimensi, penanganan histori melalui Slowly Changing Dimensions (SCD2), serta pencegahan *fanout joins* melalui pra-agregasi yang ketat.
4. **Sentralisasi Logika via Semantic Layer**: Memindahkan logika bisnis dan kalkulasi metrik ke luar dari dashboard visualisasi menuju *Semantic Layer* tersentralisasi menjamin integritas metrik yang setara bagi pemangku kepentingan bisnis maupun *Autonomous AI Agents*.
5. **Defensive Engineering & Observabilitas**: Arsitektur analitik produksi yang tangguh wajib memperlakukan skema data sebagai API publik: menerapkan *Data Contracts*, mengeksekusi validasi assertions secara otomatis, dan mengidentifikasi anomali data sebelum metrik dikonsumsi oleh sistem hilir.