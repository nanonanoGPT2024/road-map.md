# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Bab 04:** Modern Data Warehousing & Dimensional Data Modeling  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi arsitektur dimensional modeling tingkat lanjut (*Accumulating Snapshot Fact Tables*, *Factless Fact Tables*, serta *Slowly Changing Dimensions* Tipe 2, 3, 4, dan 6) pada skala multi-terabyte hingga petabyte.
- Menganalisis dan mengoptimalkan performa mesin *columnar storage* modern (seperti Snowflake, Google BigQuery, dan Databricks Photon) melalui pemahaman mendalam tentang *micro-partitioning*, *data pruning*, *clustering keys*, dan *vectorized query execution*.
- Memitigasi anomali data integritas tingkat enterprise, termasuk penanganan *late-arriving facts/dimensions*, deduplikasi streaming terdistribusi, dan rekonsiliasi data point-in-time menggunakan teknik *bitemporal modeling*.
- Merancang dan mengeksekusi pipeline analitik *production-grade* berbasis SQL, dbt (data build tool), dan PySpark dengan mematuhi prinsip idempotensi, efisiensi komputasi, dan kontrol biaya FinOps.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Foundational Dimensional Modeling:** Pemahaman kuat tentang Star Schema, Snowflake Schema, Fact Tables dasar (Transactional & Periodic Snapshot), serta SCD Tipe 1.
- **Advanced SQL:** Window functions (`ROW_NUMBER()`, `LEAD()`, `LAG()`, `DENSE_RANK()`), Common Table Expressions (CTE), dan analitik agregasi multi-dimensi (`GROUPING SETS`, `CUBE`, `ROLLUP`).
- **Distributed Computing Fundamentals:** Pemahaman partisi data (*horizontal partitioning*, *sharding*), konsep *immutability*, dan model konsistensi data (ACID vs. Eventual Consistency).
- **Tooling Environment:** Pemahaman dasar CLI, Git, serta dasar eksekusi pipeline dbt Core atau Apache Spark (PySpark).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Internal Engine Modern Cloud Data Warehouse (CDW)

Data warehouse modern (Snowflake, BigQuery, Amazon Redshift RA3, Databricks SQL) beralih dari model *Shared-Nothing MPP* tradisional berbasis block-storage lokal ke arsitektur **Decoupled Compute and Storage**.

```
+-------------------------------------------------------------------------+
|                        CLOUD STORAGE LAYER                              |
|   (AWS S3 / GCS / Azure Data Lake Storage Gen2 - Object Immutability)   |
|   - Parquet / Proprietary Columnar Formats (e.g., Snowflake FDN)        |
|   - Immutable Micro-partitions (50MB - 500MB uncompressed)              |
+-------------------------------------------------------------------------+
                                    ^
                                    | Network I/O (Stateless Ephemeral Reads)
                                    v
+-------------------------------------------------------------------------+
|                        COMPUTE WORKER LAYER                             |
|   (Virtual Warehouses / BigQuery Slots / Databricks Clusters)          |
|   - Local SSD Caching (Eviction via LRU)                                |
|   - In-Memory Vectorized SIMD Query Processing (AVX-512)                |
|   - Dynamic File Pruning based on Metadata Header (Min/Max/Null-count)  |
+-------------------------------------------------------------------------+
                                    ^
                                    | Compilation & Plan Distribution
                                    v
+-------------------------------------------------------------------------+
|                     CLOUD SERVICES / METADATA LAYER                     |
|   (Global FoundationDB / Spanner Metadata Catalogs)                     |
|   - Transaction Management & MVCC (Acid Serialization)                  |
|   - Global Directory: Logical Tables -> Physical File URI Mapping       |
|   - Query Parser, Optimizer (CBO - Cost-Based Optimizer), & Auth        |
+-------------------------------------------------------------------------+
```

#### Micro-partitioning & Columnar Pruning
Penyimpanan logis dipartisi secara fisik menjadi unit *immutable micro-partitions*. Setiap partisi berisi metadata terstruktur pada header:
- Nilai minimum dan maksimum (`min_val`, `max_val`) per kolom.
- Jumlah nilai unik (*distinct count / HyperLogLog*).
- Jumlah *null values*.

Ketika kueri mengeksekusi ekspresi filter:
$$\sigma_{\text{transaction\_date} \ge '2024-01-01' \land \text{transaction\_date} \le '2024-01-31'}$$
Optimizer memanfaatkan *metadata pruning* untuk memangkas pembacaan file fisik. Jika rentang `[min_val, max_val]` suatu partisi berada di luar predikat, partisi tersebut diabaikan total tanpa melakukan Network I/O.

#### Vectorized Execution
Eksekusi kueri modern tidak lagi memproses baris per baris (*Volcano iterator model*). Mesin eksekusi vectorized mengoperasikan array data kolom sekaligus dalam register CPU memanfaatkan instruksi SIMD (*Single Instruction, Multiple Data*). Hal ini meminimalkan *instruction cache misses* dan memaksimalkan *throughput* prosesor modern.

### 3.2. Advanced Dimensional Modeling Mechanics

#### Slowly Changing Dimensions (SCD) Types 2, 4, dan 6
- **SCD Type 2 (Historical Row Preservation):** Mempertahankan riwayat penuh dengan menambahkan baris baru per perubahan atribut. Membutuhkan *surrogate key* baru per versi, `valid_from`, `valid_to`, dan flag `is_current`.
- **SCD Type 4 (History Table):** Memecah tabel menjadi dua: tabel dimensi utama yang selalu di-update secara *in-place* (hanya menyimpan status terkini) dan tabel *history log* terpisah yang mencatat setiap delta perubahan. Desain ini menjaga ukuran tabel dimensi utama tetap ramping dan mempercepat performa *join*.
- **SCD Type 6 (Hybrid 1 + 2 + 3):** Memadukan atribut riwayat (Type 2), penimpaan langsung (Type 1), dan nilai masa lalu pada kolom terpisah (Type 3). Tabel mempertahankan baris versi masa lalu, namun kolom `current_attribute` pada semua baris versi lampau diperbarui secara global untuk merefleksikan nilai mutakhir tanpa menghilangkan garis historis.

#### Matriks Perbandingan Tipe Dimensi SCD

| Parameter | SCD Type 1 | SCD Type 2 | SCD Type 4 | SCD Type 6 |
| :--- | :--- | :--- | :--- | :--- |
| **Penyimpanan Riwayat** | Tidak Ada (Overwrite) | Ada (Baris Baru) | Ada (Tabel Terpisah) | Ada (Hybrid Baris + Kolom) |
| **Kebutuhan Storage** | Minimal ($1\times$) | Tinggi ($N \times$ Perubahan) | Sedang (Tabel Utama Tetap Kecil) | Sangat Tinggi |
| **Kompleksitas Query Dimensi** | Rendah (`SELECT ...`) | Sedang (Perlu filter `is_current`) | Sangat Rendah pada Dimensi Utama | Tinggi (Banyak kolom atribut) |
| **Dukungan Analisis Point-in-Time** | Tidak Memungkinkan | Native via `BETWEEN valid_from AND valid_to` | Memerlukan Join Kompleks ke Log | Native via Row Historis |
| **Biaya Komputasi Update (DML)** | Rendah (`UPDATE`) | Tinggi (`INSERT` + `UPDATE`) | Sangat Rendah (`INSERT` ke Log) | Ekstrem (`INSERT` + Multi-row `UPDATE`) |

#### Fact Table Patterns
1. **Accumulating Snapshot Fact Tables:** Digunakan untuk memodelkan proses bisnis dengan siklus hidup definitif dan tahapan proses yang dapat diprediksi (contoh: *Order Fulfillment*, *Loan Application Pipeline*). Setiap baris mewakili satu instans entitas bisnis, dan kolom tanggal/timestamp dimutasi atau diisi saat entitas melewati tahapan proses yang berbeda.
2. **Factless Fact Tables:** Berisi kombinasi *foreign keys* ke dimensi terkait tanpa adanya metrik kuantitatif terukur.
   - *Event Coverage:* Mencatat kejadian tertentu (misal: kehadiran siswa dalam kelas).
   - *Negative/Constraint Events:* Mencatat promosi yang sedang aktif namun produk tidak terjual selama durasi tersebut.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal pada Skala Enterprise?
Pada volume data petabyte dengan laju ingestion ratusan ribu event/detik:
- Normalisasi penuh (3NF / Inmon) menghasilkan graf relasional yang terlalu dalam. Eksekusi kueri agregasi pelaporan membutuhkan *multi-way joins* masif yang memicu komputasi *shuffle* jaringan yang sangat mahal.
- Denormalisasi mentah (*One Big Table / OBT*) tanpa tata kelola menghasilkan duplikasi penyimpanan eksponensial, anomali update saat terjadi perubahan profil master data (customer, merchant), dan ketiadaan *single source of truth*.

### Apa Solusinya?
Penerapan **Dimensional Modeling Modern (Kimball on Modern Data Stack)**:
- Memisahkan fakta numerik aditif/semi-aditif dari atribut kontekstual deskriptif (dimensi).
- Mengintegrasikan metadata-driven clustering untuk memaksimalkan *partition pruning*.
- Mengisolasi mutasi dimensi menggunakan pola SCD2 deterministik atau SCD4 performan tinggi, sehingga riwayat metrik finansial tetap terverifikasi secara hukum (*auditable*).

---

## 5. How (Workflow Detail)

Arsitektur produksi dimensional modeling modern mengadopsi alur kerja berulang berbasis ELT yang memadukan staging data mentah hingga penyajian layer mart yang siap pakai:

```
[Raw Event/CDC Streams] 
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Raw / Bronze Ingestion (Append-Only, Parquet / Delta)     │
│    - Metadata: _ingested_at, _source_file, _payload_hash    │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Silver / Normalized Staging (Cleaning & Deduplication)   │
│    - Parsing string ke strongly typed schema                │
│    - Deduplikasi via Window ROW_NUMBER() over idempotency key│
└─────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────────────────────────┐
       ▼                                          ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐
│ 3A. Dimension Processing      │  │ 3B. Fact Ingestion            │
│  - Hashing surrogate keys     │  │  - Lookups via Natural Keys   │
│  - SCD2 Diff Generation       │  │  - Late-Arriving Fact Handling│
│  - Close old row, insert new  │  │  - Surrogate key substitution │
└───────────────────────────────┘  └───────────────────────────────┘
       │                                          │
       └───────────────────┬──────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Gold / Enterprise Data Mart (Fact-Dimension Schemas)     │
│    - Transactional, Snapshot, & Accumulating Tables         │
│    - Applied Clustering Keys & Partition Constraints        │
└─────────────────────────────────────────────────────────────┘
```

### Prosedur Penanganan Late-Arriving Dimensions & Facts
1. **Late-Arriving Facts:** Fakta tiba dengan timestamp transaksi lampau, namun kunci dimensinya belum ada dalam snapshot dimensi saat transaksi terjadi.
   - *Resolusi:* Tautkan fakta ke versi dimensi yang valid pada timestamp transaksi (`transaction_time BETWEEN dim.valid_from AND dim.valid_to`). Jika catatan dimensi belum pernah ada sama sekali, tautkan ke baris *inferred dimension* (dummy record `dimension_key = -1` dengan status *Unknown*), dan perbarui fakta tersebut melalui rekonsiliasi asinkron saat master data dimensi tiba.
2. **Late-Arriving Dimensions:** Perubahan dimensi tiba terlambat dengan *effective date* di masa lampau.
   - *Resolusi:* Sistem harus memecah interval `valid_from` dan `valid_to` dimensi target yang terdampak, menyisipkan versi baru di tengah garis waktu, dan secara retroaktif memvalidasi apakah fakta terkait perlu diarahkan ulang (*re-keying*) ke versi yang baru disisipkan.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kartu Pos Perpustakaan vs. Gudang Modern
Bayangkan sebuah perpustakaan nasional.
- **Relational 3NF:** Setiap buku dipecah menjadi lembaran terpisah: judul di satu laci, penulis di laci lain, sampul di laci ketiga. Membaca satu buku utuh menuntut pustakawan bolak-balik mengambil dan menyusun lembaran dari 20 laci berbeda (*high join latency*).
- **One Big Table (OBT):** Menyalin seluruh teks buku beserta riwayat hidup lengkap penulisnya ke setiap lembar halaman. Ruang perpustakaan membengkak drastis (*storage inefficiency*), dan jika penulis mengganti nomor telepon, jutaan halaman buku harus dicetak ulang (*update anomaly*).
- **Modern Dimensional:** Buku tetap utuh di rak (Tabel Fakta Transaksi), namun informasi penulis dirangkum dalam katalog referensi terstandarisasi yang diperbarui versinya hanya jika ada perubahan signifikan (Tabel Dimensi SCD2). Pustakawan langsung menuju rak spesifik berdasarkan lorong bertanggal (Partitioning/Clustering) tanpa mencari dari pintu depan.

### Diagram: Mekanisme SCD Tipe 2 dengan Timeline Integrity

```
Waktu:       T0           T1                    T2                     T3
             |------------|---------------------|----------------------|--->
Peristiwa:   User Created  Alamat: Jakarta -> Bali  Alamat: Bali -> SG   Query di T1.5

Record Dimensi (dim_user_scd2):
+---------+---------+-----------+---------------------+---------------------+------------+
| user_sk | user_id | address   | valid_from          | valid_to            | is_current |
+---------+---------+-----------+---------------------+---------------------+------------+
| 10001   | U-882   | Jakarta   | 2024-01-01 00:00:00 | 2024-03-15 10:00:00 | FALSE      |
| 10002   | U-882   | Bali      | 2024-03-15 10:00:01 | 2024-06-20 18:30:00 | FALSE      |
| 10003   | U-882   | Singapore | 2024-06-20 18:30:01 | 9999-12-31 23:59:59 | TRUE       |
+---------+---------+-----------+---------------------+---------------------+------------+

Fact Record: Transaksi terjadi pada T1.5 (2024-04-10):
Query Join: fact.user_id = dim.user_id AND fact.txn_time BETWEEN dim.valid_from AND dim.valid_to
-> Terpetakan secara presisi ke user_sk: 10002 (Alamat saat itu: Bali).
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Factless Fact Table (Event Tracking Attendance)
Kasus: Melacak kehadiran pengguna dalam program pelatihan korporat untuk mengidentifikasi siapa yang *tidak* hadir melalui teknik *difference join*.

```sql
-- DDL Factless Fact Table
CREATE TABLE fact_employee_attendance (
    date_key INT NOT NULL,
    employee_key INT NOT NULL,
    course_key INT NOT NULL,
    attendance_recorded_at TIMESTAMP NOT NULL,
    CONSTRAINT pk_attendance PRIMARY KEY (date_key, employee_key, course_key)
);

-- Kueri: Identifikasi karyawan yang terdaftar di kursus X namun TIDAK hadir pada tanggal tertentu
SELECT 
    reg.employee_key,
    reg.course_key
FROM dim_course_registration reg
LEFT JOIN fact_employee_attendance att
    ON reg.employee_key = att.employee_key
    AND reg.course_key = att.course_key
    AND att.date_key = 20241025
WHERE reg.is_active = TRUE 
  AND att.employee_key IS NULL;
```

---

### 7.2. Practical Example: Production-Grade Accumulating Snapshot Fact Table

Implementasi dbt model untuk *E-commerce Order Fulfillment Pipeline* menggunakan SQL dialect Snowflake/Databricks.

```sql
-- models/marts/core/fct_order_fulfillment_accumulating.sql
{{
    config(
        materialized = 'incremental',
        unique_key = 'order_pk',
        cluster_by = ['order_status', 'order_placed_date'],
        on_schema_change = 'fail'
    )
}}

WITH source_events AS (
    SELECT 
        order_id,
        customer_id,
        merchant_id,
        event_name,
        event_timestamp,
        payload_amount_cents
    FROM {{ ref('stg_order_lifecycle_events') }}
    {% if is_incremental() %}
        -- Ambil event baru atau event yang memperbarui lifecycle order yang belum tuntas
        WHERE event_timestamp >= (SELECT DATEADD('day', -3, MAX(order_placed_date)) FROM {{ this }})
    {% endif %}
),

pivoted_stages AS (
    SELECT
        order_id,
        customer_id,
        merchant_id,
        -- Deterministic Surrogate Key via MD5 hashing
        MD5(CONCAT_WS('||', order_id)) AS order_pk,
        MAX(CASE WHEN event_name = 'ORDER_PLACED' THEN event_timestamp END) AS order_placed_at,
        MAX(CASE WHEN event_name = 'PAYMENT_CLEARED' THEN event_timestamp END) AS payment_cleared_at,
        MAX(CASE WHEN event_name = 'ITEM_DISPATCHED' THEN event_timestamp END) AS item_dispatched_at,
        MAX(CASE WHEN event_name = 'DELIVERY_COMPLETED' THEN event_timestamp END) AS delivery_completed_at,
        MAX(CASE WHEN event_name = 'ORDER_CANCELLED' THEN event_timestamp END) AS order_cancelled_at,
        MAX(payload_amount_cents) AS gross_revenue_cents
    FROM source_events
    GROUP BY 1, 2, 3, 4
),

final_accumulating AS (
    SELECT
        p.order_pk,
        p.order_id,
        -- Foreign Keys ke Dimensi
        COALESCE(c.customer_sk, -1) AS customer_sk,
        COALESCE(m.merchant_sk, -1) AS merchant_sk,
        
        -- Date Foreign Keys (YYYYMMDD)
        TO_NUMBER(TO_CHAR(p.order_placed_at, 'YYYYMMDD')) AS order_placed_date_key,
        TO_NUMBER(TO_CHAR(p.payment_cleared_at, 'YYYYMMDD')) AS payment_cleared_date_key,
        TO_NUMBER(TO_CHAR(p.item_dispatched_at, 'YYYYMMDD')) AS item_dispatched_date_key,
        TO_NUMBER(TO_CHAR(p.delivery_completed_at, 'YYYYMMDD')) AS delivery_completed_date_key,
        
        -- Timestamps Asli untuk Analisis Lag Presisi
        p.order_placed_at,
        p.payment_cleared_at,
        p.item_dispatched_at,
        p.delivery_completed_at,
        p.order_cancelled_at,
        
        -- Business Process Durations (Durasi SLA dalam Detik)
        DATEDIFF('second', p.order_placed_at, p.payment_cleared_at) AS order_to_payment_seconds,
        DATEDIFF('second', p.payment_cleared_at, p.item_dispatched_at) AS payment_to_dispatch_seconds,
        DATEDIFF('second', p.item_dispatched_at, p.delivery_completed_at) AS dispatch_to_delivery_seconds,
        DATEDIFF('second', p.order_placed_at, p.delivery_completed_at) AS total_fulfillment_seconds,
        
        -- Metric Flags & Amounts
        p.gross_revenue_cents / 100.0 AS gross_revenue_usd,
        CASE
            WHEN p.order_cancelled_at IS NOT NULL THEN 'CANCELLED'
            WHEN p.delivery_completed_at IS NOT NULL THEN 'DELIVERED'
            WHEN p.item_dispatched_at IS NOT NULL THEN 'IN_TRANSIT'
            WHEN p.payment_cleared_at IS NOT NULL THEN 'PROCESSING'
            ELSE 'PLACED'
        END AS order_status,
        
        -- Audit column
        CURRENT_TIMESTAMP() AS dwh_updated_at,
        DATE(p.order_placed_at) AS order_placed_date

    FROM pivoted_stages p
    LEFT JOIN {{ ref('dim_customers') }} c 
        ON p.customer_id = c.customer_id 
        AND p.order_placed_at >= c.valid_from 
        AND p.order_placed_at < COALESCE(c.valid_to, '9999-12-31'::TIMESTAMP)
    LEFT JOIN {{ ref('dim_merchants') }} m 
        ON p.merchant_id = m.merchant_id 
        AND m.is_current = TRUE
)

SELECT * FROM final_accumulating;
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Arsitektur Data Warehouse FinTech PayLater (Buy-Now-Pay-Later)
- **Skala:** 45 juta pengguna aktif, 2,5 miliar baris mutasi kredit/tahun, volume ingest harian 12 TB.
- **Kondisi Kritis:** Audit finansial mensyaratkan rekonsiliasi data historis kredit point-in-time dengan garansi nol pergeseran nilai nominal (*zero financial drift*). Dimensi profil risiko pengguna (*Credit Score Band*) berubah secara berkala dan sering tiba terlambat dari model ML batch pihak ketiga (*late-arriving risk classification*).

### Arsitektur Implementasi

```
           +-----------------------------------------------+
           | Apache Kafka (Financial Transactions, 10k/sec)|
           +-----------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| Databricks Auto Loader (Ingestion -> Bronze Raw Delta Lake)       |
| - Format: Delta Lake (Parquet + ACID Transaction Log)             |
| - Mode: Append Only, Zero schema mutations                        |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| Silver Layer: Dynamic Bitemporal Transformation Engine            |
| 1. dim_customer_credit_profile (SCD Tipe 2):                      |
|    - System Valid Time vs Business Application Time               |
|    - Surrogate Key = SHA256(user_id || valid_from)               |
| 2. fct_credit_drawdown (Transactional Fact):                      |
|    - Cluster Key: Z-ORDER BY (drawdown_date, merchant_id)         |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| Gold Layer: Consolidated Risk Mart                                |
| - Query Engine: Databricks Photon / Snowflake Analytical Engine   |
| - Sub-second Point-in-Time Join using Dynamic Bloom Filter Pruning|
+-------------------------------------------------------------------+
```

### PySpark Production Job: Dynamic Bitemporal Dimension Merge

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, sha2, concat_ws, coalesce, current_timestamp
from delta.tables import DeltaTable

def process_scd2_credit_profile(spark: SparkSession, delta_table_path: str, updates_view_name: str):
    """
    Eksekusi SCD Tipe 2 dengan kontrol bitemporal pada tabel master risiko kredit.
    Menghindari degradasi full-table scan menggunakan micro-merge condition.
    """
    target_table = DeltaTable.forPath(spark, delta_table_path)
    
    # Raw Delta Data dari Microbatch Staging
    updates_df = spark.sql(f"""
        SELECT 
            user_id,
            credit_score_band,
            max_limit_amount,
            effective_start_date AS business_valid_from
        FROM {updates_view_name}
    """)
    
    # Bentuk Surrogate Key berbasis Hash
    staged_updates = updates_df.withColumn(
        "profile_sk", 
        sha2(concat_ws("||", col("user_id"), col("business_valid_from")), 256)
    ).withColumn("system_ingested_at", current_timestamp())
    
    staged_updates.createOrReplaceTempView("staged_credit_updates")
    
    # Pola Merge-Insert SCD2 Atomic
    merge_query = """
    MERGE INTO delta.`{path}` AS target
    USING (
        -- Records yang ada dan perlu ditutup (UPDATE valid_to)
        SELECT 
            staged.user_id AS merge_key, 
            staged.* 
        FROM staged_credit_updates staged
        UNION ALL
        -- Baris baru yang akan diinsert secara eksplisit
        SELECT 
            NULL AS merge_key, 
            staged.* 
        FROM staged_credit_updates staged
    ) AS source
    ON target.user_id = source.merge_key 
       AND target.is_current = TRUE 
       AND target.credit_score_band <> source.credit_score_band
    
    -- Tutup record lama
    WHEN MATCHED THEN
        UPDATE SET 
            target.is_current = FALSE,
            target.valid_to = source.business_valid_from,
            target.updated_at = source.system_ingested_at
            
    -- Masukkan record baru
    WHEN NOT MATCHED AND source.merge_key IS NULL THEN
        INSERT (
            profile_sk,
            user_id,
            credit_score_band,
            max_limit_amount,
            valid_from,
            valid_to,
            is_current,
            created_at,
            updated_at
        ) VALUES (
            source.profile_sk,
            source.user_id,
            source.credit_score_band,
            source.max_limit_amount,
            source.business_valid_from,
            TIMESTAMP('9999-12-31 23:59:59'),
            TRUE,
            source.system_ingested_at,
            source.system_ingested_at
        )
    """.format(path=delta_table_path)
    
    spark.sql(merge_query)
```

---

## 9. Trade-offs: Architectural Decision Records (ADR)

### Trade-off 1: Pre-computed Fact Aggregations vs. On-The-Fly Vectorized Compute
* **Konteks:** Tim Business Intelligence membutuhkan metrik performa sales harian per toko dan regional.
* **Pilihan 1 (Pre-aggregation):** Menggunakan tabel agregasi berkala (*Summary Tables*) yang diperbarui setiap malam.
  - *Kelebihan:* Latensi kueri instan (<100ms) untuk dashboard. Biaya query run BI rendah.
  - *Kekurangan:* Redundansi storage; kehilangan granularitas tingkat transaksi untuk analisis *drill-down*; pipeline rapuh terhadap perubahan definisi metrik bisnis lampau.
* **Pilihan 2 (Dynamic Aggregation on Granular Data):** Kueri langsung ke *Atomic Fact Table* dengan clustering keys.
  - *Kelebihan:* Fleksibilitas total untuk eksplorasi tanpa batas; data lineage transparan; tidak ada rekonsiliasi data antara atomic layer dan summary layer.
  - *Kekurangan:* Konsumsi compute slots/warehouse credits tinggi bila kueri dieksekusi ratusan analis secara simultan.
* **Keputusan Enterprise:** Gunakan *Atomic Fact Table* yang dilengkapi **Materialized Views with Automated Rewrite Engine**. Jika definisi kueri dashboard cocok dengan proyeksi MV, database otomatis mengarahkan kueri ke MV tanpa mengubah kode SQL BI layer.

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Non-Deterministic Hashing untuk Surrogate Keys
* **Anti-Pattern:** Menggunakan auto-increment sequence engine terdistribusi (`AUTO_INCREMENT`, `IDENTITY`) di lingkungan parallel cluster, atau menggunakan fungsi hash yang rentan *null-handling bugs*.
  ```sql
  -- BURUK: Jika salah satu field NULL, hasil CONCAT menghasilkan NULL di database tertentu
  SELECT MD5(user_id || customer_region) FROM users;
  ```
* **Koreksi:** Wajib menggunakan *delimiter separation* dan penanganan nilai null yang deterministik.
  ```sql
  -- BENAR: Menggunakan separator eksplisit dan COALESCE/CONCAT_WS
  SELECT MD5(CONCAT_WS('^^', COALESCE(user_id, '__NULL__'), COALESCE(customer_region, '__NULL__'))) 
  FROM users;
  ```

### 10.2. Troubleshooting: Data Clustering Degradation (Snowflake/BigQuery)
* **Gejala:** Kueri analitik berbasis filter tanggal yang biasanya selesai dalam 3 detik mendadak mengalami regresi menjadi 45 detik. *Bytes scanned* melonjak 10x lipat.
* **Akar Masalah:**
  1. File micro-partition terfragmentasi akibat seringnya operasi DML *single-row INSERT/MERGE* (micro-batching interval terlalu kecil, misal tiap 10 detik).
  2. *Clustering depth* tabel memburuk drastis karena urutan data baru yang di-insert tidak lagi sejalan dengan *clustering key*.
* **Langkah Investigasi & Remediasi:**
  ```sql
  -- Evaluasi rasio fragmentasi partisi di Snowflake
  SELECT SYSTEM$CLUSTERING_INFORMATION('fct_order_fulfillment', '(order_placed_date)');
  
  -- Solusi: Jalankan Automatic Clustering atau eksekusi Re-cluster Manual
  ALTER TABLE fct_order_fulfillment RECLUSTER;
  ```

---

## 11. Best Practices (Production Checklist)

Berikut panduan checklist arsitektur produksi:

- [ ] **Gunakan Surrogate Key Alfanumerik Konsisten:** Hindari ketergantungan sequence numerik stateful lintas data lakehouse. Standarkan hashing surrogate key menggunakan MD5 atau SHA-256.
- [ ] **Simpan Waktu dalam UTC:** Seluruh timestamp di layer fakta dan dimensi wajib bertipe data `TIMESTAMPTZ` atau dikonversi ke UTC absolut sebelum ingestion. Sediakan dimensi `dim_timezone` untuk mapping lokal pengguna.
- [ ] **Isolasi Null Value pada Foreign Key:** Jangan biarkan kolom Foreign Key pada fact table bernilai `NULL`. Mapping seluruh nilai absen/tidak dikenal ke surrogate key bernilai minus konvensional:
  - `-1`: Unknown / Unmapped
  - `-2`: Not Applicable
  - `-3`: Inferred / Pending Late Arriving Processing
- [ ] **Pemberian Nama Kolom yang Jelas (Naming Conventions):**
  - Tabel Fakta: Prefiks `fct_` (transaksi), `snp_` (periodic snapshot), `acc_` (accumulating snapshot).
  - Tabel Dimensi: Prefiks `dim_`.
  - Primary Key Dimensi: Suffix `_sk` (Surrogate Key).
  - Foreign Key Fakta: Suffix `_fk` atau `_sk` yang merujuk langsung ke entitas dimensi.
- [ ] **Terapkan Idempotensi Pipeline Penuh:** Seluruh skrip loading (dbt run, Airflow DAG, Spark Job) harus bersifat *re-runnable* tanpa memicu duplikasi data atau modifikasi histori yang keliru. Wajib menggunakan pola transactional write seperti atomic partition swap atau Delta Lake/Iceberg ACID dynamic overwrites.

---

## 12. Hands-on Practice: Membangun Production Dimensional Pipeline

Simpan latihan ini ke dalam direktori lokal: `hands-on/m02/`

### Struktur Direktori:
```text
hands-on/m02/
├── ddl/
│   └── 01_schema_init.sql
├── data/
│   └── raw_sales_stream.csv
└── pipeline/
    └── scd2_dimension_builder.sql
```

### Langkah 1: Inisialisasi Skema Database (Simpan di `ddl/01_schema_init.sql`)
Jalankan di DuckDB, PostgreSQL, atau Cloud Data Warehouse pilihan Anda:

```sql
-- DDL untuk Master Dimensi Produk (SCD Tipe 2)
CREATE TABLE dim_product (
    product_sk VARCHAR(32) PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    unit_retail_price NUMERIC(12, 2) NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    is_current BOOLEAN NOT NULL
);

-- DDL untuk Fact Sales Transaksional
CREATE TABLE fct_sales_transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    transaction_timestamp TIMESTAMP NOT NULL,
    date_key INT NOT NULL,
    product_sk VARCHAR(32) NOT NULL,
    store_id VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    gross_amount NUMERIC(12, 2) NOT NULL,
    tax_amount NUMERIC(12, 2) NOT NULL
);

-- Masukkan Rekord Awal Dimensi
INSERT INTO dim_product VALUES 
('p1_v1', 'P-101', 'Ergonomic Chair', 'Furniture', 150.00, '2023-01-01 00:00:00', '2023-06-30 23:59:59', FALSE),
('p1_v2', 'P-101', 'Ergonomic Chair Pro', 'Furniture', 180.00, '2023-07-01 00:00:00', '9999-12-31 23:59:59', TRUE);
```

### Langkah 2: Pipeline Integrasi Late-Arriving Fact (Simpan di `pipeline/scd2_dimension_builder.sql`)

Terapkan kueri ETL yang mengekstrak data transaksi mentah dan mengaitkannya secara presisi ke versi SCD Tipe 2 yang berlaku pada saat kejadian:

```sql
-- Simulasi Stream Data Transaksi Mentah yang Baru Masuk
WITH raw_incoming_sales AS (
    SELECT 'TX-9001' AS transaction_id, TIMESTAMP '2023-03-15 14:20:00' AS txn_time, 'P-101' AS product_id, 'STR-01' AS store_id, 2 AS qty, 300.00 AS total_price UNION ALL
    SELECT 'TX-9002' AS transaction_id, TIMESTAMP '2023-08-10 09:15:00' AS txn_time, 'P-101' AS product_id, 'STR-02' AS store_id, 1 AS qty, 180.00 AS total_price UNION ALL
    -- Transaksi dengan produk yang tidak terdaftar sama sekali (Missing Dimension)
    SELECT 'TX-9003' AS transaction_id, TIMESTAMP '2023-09-01 11:00:00' AS txn_time, 'P-999' AS product_id, 'STR-01' AS store_id, 5 AS qty, 50.00 AS total_price
)
SELECT
    raw.transaction_id,
    raw.txn_time AS transaction_timestamp,
    CAST(STRFTIME(raw.txn_time, '%Y%m%d') AS INT) AS date_key,
    -- Resolusi Surrogate Key: Terhubung ke Versi SCD2 yang tepat, atau -1 jika Inferred
    COALESCE(dim.product_sk, 'UNKNOWN_INFERRED') AS product_sk,
    raw.store_id,
    raw.qty AS quantity,
    raw.total_price AS gross_amount,
    ROUND(raw.total_price * 0.11, 2) AS tax_amount
FROM raw_incoming_sales raw
LEFT JOIN dim_product dim
    ON raw.product_id = dim.product_id
    AND raw.txn_time >= dim.valid_from 
    AND raw.txn_time <= dim.valid_to;
```

---

## 13. Exercise

### Level Easy
Tuliskan kueri analitik berbasis SQL pada tabel akumulasi `fct_order_fulfillment_accumulating` dari Bagian 7.2 untuk menghitung rata-rata waktu pemrosesan (*order placed to payment cleared*) dan rata-rata pengiriman (*dispatch to delivery*) dalam satuan jam, dikelompokkan berdasarkan kuartal tanggal pemesanan (`order_placed_at`).

### Level Medium
Kembangkan skrip SQL DDL dan DML untuk memodelkan **SCD Tipe 3** pada tabel `dim_merchant`. Persyaratan:
1. Kolom menyimpan: `merchant_id`, `legal_business_name`, `current_merchant_tier`, `previous_merchant_tier`, dan `tier_change_date`.
2. Tuliskan kueri `UPDATE` ketika merchant ID `M-404` naik status dari 'TIER_2' menjadi 'TIER_1'.

### Level Hard
Buat dbt macro dinamis (Jinja + SQL) yang menerima nama tabel staging dan daftar kolom pembanding delta, kemudian mengeksekusi *hashing generation* menggunakan SHA-256 untuk mendeteksi perubahan atribut secara otomatis pada implementasi SCD Tipe 2. Tangani skenario di mana seluruh nilai pada baris masukan bernilai NULL.

---

## 14. Challenge: Arsitektur Multi-Tier Global E-Commerce Core Model

**Deskripsi Masalah Kasus Riil:**  
Sebuah platform marketplace global beroperasi di 12 negara dengan sistem pencatatan transaksi terdesentralisasi. Sistem ini menghasilkan:
1. Transaksi lintas mata uang yang memerlukan konversi mata uang dinamis pada detik transaksi terjadi (*point-in-time exchange rate table*).
2. Perubahan pengelompokan kategori produk multi-level (*Taxonomy Hierarchy*) hingga 10 level kedalaman. Perubahan taksonomi ini bersifat retroaktif sebagian: divisi audit menuntut pelaporan keuangan menggunakan kategori *as-was* (saat transaksi dieksekusi), sementara divisi analitik pemasaran menuntut metrik historis dikonsolidasikan menggunakan taksonomi *as-is* (kategori mutakhir saat laporan ditarik).
3. Pengiriman barang lintas batas sering memicu pembatalan parsial (*partial refunds*) dan pergantian nomor resi logistik di tengah jalan.

**Tantangan Arsitektural:**  
Rancang dokumen arsitektur dan model dimensional yang menjawab tantangan di atas:
- Tentukan kombinasi Fact Table (Transactional vs Accumulating vs Factless) dan SCD Type yang optimal untuk memitigasi isu dual-reporting (*as-was* vs *as-is*) tanpa menggandakan Fact Table utama.
- Sajikan diagram relasi entitas dalam format ASCII yang memetakan koneksi Fact-to-Dimension secara komprehensif.
- Dokumentasikan strategi komputasi clustering untuk memastikan kueri pelaporan rentang 5 tahun tidak memindai lebih dari 10% data keseluruhan.

*(Peserta diminta menyusun dokumen solusi arsitektur ini secara mandiri sebagai portofolio level Principal Data Engineer).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. Apa karakteristik utama dari *Factless Fact Table*?  
   a. Tabel yang tidak memiliki primary key.  
   b. Tabel fakta yang hanya berisi surrogate foreign key tanpa metrik numerik pengukuran kuantitatif langsung.  
   c. Tabel dimensi yang dinormalisasi ke bentuk 3NF.  
   d. View logis yang tidak menyimpan data fisik di disk.  
   *Kunci: b*

2. Pada SCD Tipe 2, jika sebuah baris dimensi mengalami perubahan atribut, aksi apa yang dilakukan pada database?  
   a. Menimpa nilai kolom lama secara langsung di baris yang sama.  
   b. Menghapus record lama dan menyisipkan record baru.  
   c. Mengubah flag `is_current` record lama menjadi FALSE, mengupdate `valid_to`, dan menyisipkan record baru dengan `is_current = TRUE`.  
   d. Membuat tabel database baru dengan akhiran tahun berjalan.  
   *Kunci: c*

3. Manakah tipe Fact Table yang paling cocok untuk melacak alur pipeline pelamar kerja mulai dari pengajuan lamaran, jadwal wawancara, tes teknis, offering letter, hingga orientasi?  
   a. Transactional Fact Table  
   b. Periodic Snapshot Fact Table  
   c. Accumulating Snapshot Fact Table  
   d. Factless Event Coverage Table  
   *Kunci: c*

4. Mengapa penggunaan auto-incrementing integer (misal: MySQL auto-increment) dihindari sebagai Surrogate Key generator pada arsitektur Modern Data Lakehouse?  
   a. Membutuhkan sinkronisasi state terpusat yang menjadi bottleneck performa pada kluster komputasi terdistribusi.  
   b. Integer membutuhkan kapasitas penyimpanan lebih besar daripada teks MD5 string.  
   c. Tidak kompatibel dengan tipe data Apache Parquet.  
   d. Query engine berbasis GPU tidak mendukung perbandingan integer.  
   *Kunci: a*

5. Dalam mesin columnar database modern, apa yang dimaksud dengan teknik *Pruning*?  
   a. Menghapus partisi file lama secara permanen dari object storage.  
   b. Melewati pembacaan blok data fisik tertentu karena metadata min/max blok berada di luar predikat kueri.  
   c. Mengompresi string panjang menggunakan algoritma gzip.  
   d. Melakukan indexing menggunakan B-Tree pada memory RAM.  
   *Kunci: b*

---

### Bagian B: Intermediate (Pilihan Ganda)

6. SCD Tipe 6 merupakan kombinasi hibrida dari teknik SCD tipe:  
   a. Tipe 1 + Tipe 2 + Tipe 3  
   b. Tipe 2 + Tipe 4 + Tipe 0  
   c. Tipe 1 + Tipe 4 + Tipe 5  
   d. Tipe 2 + Tipe 3 + Tipe 5  
   *Kunci: a*

7. Apa konsekuensi teknis utama dari menerapkan *Clustering Key* dengan kardinalitas yang teramat tinggi (misal: timestamp dengan presisi nanodetik) pada tabel fakta berskala multi-terabyte?  
   a. Kueri akan gagal akibat memory out-of-bounds secara konsisten.  
   b. Terjadi over-fragmentasi micro-partition, menghasilkan banyak file berukuran sangat kecil yang menurunkan efisiensi I/O dan metadata pruning.  
   c. Mesin komputasi secara otomatis menolak operasi INSERT berikutnya.  
   d. File Parquet secara otomatis dikonversi menjadi file format CSV.  
   *Kunci: b*

8. Apa langkah penanganan terbaik jika sebuah fakta transaksi tiba di DWH namun data master dimensinya belum masuk ke tabel dimensi (*Late-Arriving Dimension*)?  
   a. Menolak transaksi dan melempar exception ke antrean dead-letter queue.  
   b. Membiarkan kolom foreign key bernilai `NULL`.  
   c. Membuat entitas *inferred/dummy* pada tabel dimensi dengan atribut status 'Unknown', menautkan fakta ke record tersebut, dan memperbarui dimensinya saat master data tiba.  
   d. Menunda eksekusi pipeline transaksi dan memblokir seluruh workflow ETL hingga dimensi tersedia.  
   *Kunci: c*

9. Dalam perancangan dimensional, apa yang dimaksud dengan konsep *Conformed Dimension*?  
   a. Dimensi yang hanya boleh diakses oleh satu tabel fakta spesifik.  
   b. Dimensi yang memiliki struktur, makna bisnis, dan surrogate key yang konsisten di seluruh enterprise data warehouse, memungkinkan integrasi kueri antar-fakta (*drill across*).  
   c. Tabel dimensi sementara yang dihapus setelah pipeline ELT selesai.  
   d. Dimensi yang telah dikonversi sepenuhnya menjadi tabel terdenormalisasi tunggal (OBT).  
   *Kunci: b*

10. Mengapa operasi `MERGE` berbasis SCD Tipe 2 pada tabel Delta Lake yang berukuran ratusan gigabyte lambat jika dijalankan tanpa kondisi partisi spesifik?  
    a. Delta Lake tidak mendukung indeks b-tree sehingga engine terpaksa membaca transaction log secara serial.  
    b. Engine harus melakukan *full table scan* untuk mencocokkan target row keys dan mengevaluasi status `is_current` tanpa filter direktori partisi.  
    c. Format Parquet tidak mendukung instruksi pembaruan atomik.  
    d. Spark driver memory kehabisan alokasi ruang buffer JDBC.  
    *Kunci: b*

---

### Bagian C: Skenario Kasus Produksi

11. **Skenario 1:** Sebuah fintech pinjaman online mengalami masalah laporan rekonsiliasi bulanan. Tim audit menemukan bahwa metrik total pengeluaran dana pinjaman pada laporan bulan Januari 2024 yang diakses pada Februari berbeda nilainya dengan laporan bulan Januari 2024 yang diakses pada Juni. Setelah diinvestigasi, dimensi `dim_borrower` menggunakan SCD Tipe 1, dan ada nasabah yang berganti cabang domisili pada bulan Mei.  
    *Pertanyaan:* Analisis akar masalah teknis ini dan jelaskan solusi arsitektural yang wajib diimplementasikan!  
    *Analisis/Kunci:* Akar masalah adalah penggunaan **SCD Tipe 1** yang menimpa (*overwrite*) data historis nasabah. Ketika cabang domisili nasabah berubah di bulan Mei, seluruh rekaman transaksi Januari yang di-join ke dimensi nasabah secara retrospektif dikaitkan ke cabang baru, merusak validitas audit historis. Solusinya: Implementasikan **SCD Tipe 2** dengan kolom `valid_from` dan `valid_to`. Rekonsiliasi faktur wajib melakukan point-in-time join (`txn_time BETWEEN valid_from AND valid_to`) untuk memastikan pelaporan *as-was* tetap konsisten secara permanen.

12. **Skenario 2:** Pipeline dbt incremental Anda mengolah tabel `fct_order_status` yang mencakup 500 juta baris. Perusahaan menerapkan model pemrosesan pesanan yang dinamis, di mana status pesanan bisa diperbarui dari *PLACED* menjadi *DELIVERED* dalam jangka waktu bervariasi antara 1 hingga 45 hari. Kueri dbt Anda menggunakan konfigurasi `WHERE updated_at >= (SELECT MAX(updated_at) FROM {{ this }})`. Beberapa analis melaporkan data pesanan yang mengalami pembaruan status tidak termutasi di mart pelaporan.  
    *Pertanyaan:* Mengapa terjadi *data loss* pembaruan ini dan bagaimana merancang strategi *lookback window* yang benar dan hemat biaya?  
    *Analisis/Kunci:* Masalah ini bersumber dari *clock drift*, keterlambatan streaming event CDC (*event arrival out of order*), atau batch transaction yang tertahan. Jika satu batch baru masuk dengan `updated_at` bernilai masa kini, namun ada event perubahan untuk transaksi lama yang terselip dengan nilai `updated_at` beberapa menit/jam lebih rendah, klausa incremental akan melewatkan data tersebut. Solusi: Gunakan **dynamic lookback window** (misal: mengambil data staging dengan `updated_at >= CURRENT_DATE() - INTERVAL '3 DAY'` atau '45 DAY' khusus untuk order yang belum final), dikombinasikan dengan mekanisme *MERGE/Upsert* berbasis unique primary key, bukan sekadar append data baru.

13. **Skenario 3:** Tim Data Platform mendeteksi lonjakan tagihan warehouse Snowflake hingga 300% setelah meluncurkan model fact baru. Fact table ini memiliki 10 foreign keys ke berbagai dimensi dan berukuran 10 TB. Setiap malam, dilakukan proses reload penuh (*full table refresh* via `CREATE OR REPLACE TABLE`) untuk memperbarui fakta.  
    *Pertanyaan:* Apa tindakan FinOps dan arsitektur engineering mendesak yang harus dilakukan untuk memangkas biaya hingga di bawah 80% tanpa mengurangi ketersediaan data?  
    *Analisis/Kunci:*  
    1. Hentikan pola *full table refresh*; ubah menjadi **Incremental Ingestion** menggunakan mekanisme `MERGE` atau partisi harian append-only.  
    2. Terapkan strategi **Clustering Key** yang tepat pada fact table (misal: kolom tanggal transaksi `txn_date`), hindari clustering pada kolom ber-kardinalitas unik tinggi seperti ID UUID.  
    3. Manfaatkan **Transient Tables** untuk layer staging intermediate guna menghemat biaya fail-safe storage.  
    4. Pastikan virtual warehouse menggunakan fitur *auto-suspend* agresif (misal: 60 detik) dan skala komputasi diturunkan (*downscaling*) saat proses batch selesai.

---

## 16. Summary

1. Arsitektur data warehouse modern mengandalkan pemisahan storage dan compute, memanfaatkan format columnar berbasis *immutable micro-partitions* dengan metadata file komprehensif untuk *pruning*.
2. Pemilihan skema SCD (khususnya SCD Tipe 2 vs. Tipe 4) memengaruhi tidak hanya integritas audit data historis finansial perusahaan (*point-in-time analysis*), tetapi juga performa komputasi DML MERGE pada skala petabyte.
3. Pola tabel fakta tingkat lanjut:
   - **Accumulating Snapshot:** Wajib untuk proses bisnis bertahap dengan pelacakan durasi lag SLA antar-milestone.
   - **Factless Fact:** Esensial untuk penelusuran cakupan relasi (event coverage) dan identifikasi ketiadaan kejadian (*negative queries*).
4. Penanganan anomalistis seperti *Late-Arriving Dimensions* menuntut penggunaan *surrogate keys* berbasis hashing deterministik dan penyediaan entitas referensi default/inferred untuk mencegah hilangnya data fakta.
5. Efisiensi sistem jangka panjang ditentukan oleh keseimbangan antara normalisasi dimensi, clustering dataset yang tepat sasaran, serta desain pipeline transformasional yang sepenuhnya idempoten.