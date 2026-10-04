# Kurikulum Enterprise BI Analyst: BAB-03 Data Modeling & Dimensional Warehousing
**Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan mengimplementasikan** pola dimensional tingkat lanjut: *Accumulating Snapshot Fact Tables*, *Factless Fact Tables*, *Periodic Snapshot Fact Tables*, serta penanganan relasi many-to-many melalui *Bridge Tables*.
- **Mengeksekusi strategi penanganan perubahan dimensi tingkat lanjut**: *Slowly Changing Dimension* (SCD) Tipe 4 (Mini-Dimensions) dan Tipe 6 (Hybrid 1+2+3) pada engine analitik modern (*cloud columnar data warehouse*).
- **Menyelesaikan permasalahan anomali data operasional riil**: *Late-Arriving Facts* dan *Late-Arriving Dimensions* dengan pipeline rekonsiliasi berbasis *idempotent SQL* dan *dbt* (*data build tool*).
- **Mengoptimalkan kinerja kueri enterprise**: Menganalisis *execution plan*, mengeliminasi *fan-out traps* / *cartesian product*, dan mendesain strategi *clustering/partitioning* pada dimensional model skala multi-terabyte/petabyte.
- **Mengintegrasikan model dimensional ke Semantic Layer**: Menyusun metrik bisnis yang konsisten, performan, dan bebas bias kalkulasi agregasi (*double counting*).

---

## 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
- **Foundational Dimensional Modeling**: Pemahaman rigid mengenai konsep *Grain*, Fakta (*Additive*, *Semi-Additive*, *Non-Additive*), dan *Conformed Dimensions*.
- **SCD Tipe 1 dan 2**: Mekanisme overwrite vs historisasi berbasis baris (`valid_from`, `valid_to`, `is_current`).
- **Advanced SQL**: Window Functions (`ROW_NUMBER`, `LEAD`, `LAG`), CTE tingkat lanjut, Subquery Correlations, dan sintaks analitik ANSI-SQL.
- **Data Engineering Basics**: Pemahaman fundamental tentang *columnar storage* (Parquet/ORC), kompresi data (*dictionary encoding*, *run-length*), dan konsep *micro-partitioning*.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Advanced Dimensional Patterns & Grain Integrity
Model dimensi klasik (Star Schema sederhana) sering kali gagal saat dihadapkan pada skenario alur kerja bisnis multi-tahap, relasi data multi-cabang (*multivalued attributes*), atau pemantauan status non-transaksional.

```
+----------------------------------------------------------------------------------------------------+
|                                    KIMBALL ADVANCED TOPOLOGY                                       |
+----------------------------------------------------------------------------------------------------+

  [Periodic Snapshot]           [Accumulating Snapshot]                 [Bridge / M:N]
   Grain: 1 Bulan/Akun           Grain: 1 Lifecycle Entitas             Grain: Hubungan Entitas
  +--------------------+        +---------------------------+        +--------------------------+
  | fct_monthly_bal    |        | fct_order_fulfillment     |        | brg_order_promo          |
  |--------------------|        |---------------------------|        |--------------------------|
  | account_key (FK)   |        | order_key (Degenerate)    |   +--->| order_key (FK)           |
  | month_key (FK)     |        | customer_key (FK)         |   |    | promo_key (FK)           |
  | ending_balance     |        | order_placed_date_key     |   |    | allocation_factor (0.50) |
  | total_deposit_amt  |        | order_paid_date_key       |   |    +--------------------------+
  +--------------------+        | order_shipped_date_key    |   |                 ^
                                | order_delivered_date_key  |   |                 |
                                | lag_days_place_to_ship    |---+                 |
                                +---------------------------+                     |
                                                                     +--------------------------+
                                                                     | dim_promotions           |
                                                                     +--------------------------+
```

#### A. Accumulating Snapshot Fact Tables
Berbeda dengan *Transaction Fact* yang mencatat satu titik waktu secara statis (append-only), *Accumulating Snapshot Fact Table* merepresentasikan seluruh siklus hidup proses bisnis yang memiliki tahapan pasti dari awal hingga akhir (misal: siklus *order-to-cash*, klaim asuransi, atau aplikasi kredit).
- **Karakteristik**: Memiliki beberapa *foreign key* tanggal yang merepresentasikan setiap *milestone*.
- **Pembaruan Data**: Baris fakta di-*update* setiap kali sebuah entitas bisnis berpindah dari satu tahap ke tahap berikutnya.
- **Metrik Lag**: Menyimpan durasi waktu antar-*milestone* (misal: `days_from_placed_to_shipped`) yang dihitung langsung pada level baris untuk menghindari komputasi `DATEDIFF` berulang di level kueri analitik.

#### B. Factless Fact Tables
Tabel fakta yang tidak memiliki *numeric metric* eksplisit (seperti *amount* atau *quantity*). Terdapat dua varian utama:
1. **Event Tracking**: Mencatat keterjadian suatu peristiwa asosiasi. Contoh: Absensi mahasiswa di kelas (`student_key`, `course_key`, `date_key`, `attendance_flag`).
2. **Coverage Table**: Mencatat kondisi apa yang seharusnya terjadi atau ketersediaan promosi (*what did not happen*). Digunakan untuk mendeteksi *negative space analysis* (produk mana yang sedang dipromosikan tetapi tidak terjual satu unit pun).

#### C. Bridge Tables (Multivalued Dimensions)
Ketika satu baris fakta berelasi dengan lebih dari satu nilai pada dimensi terkait (misal: satu transaksi medis ditangani oleh 3 dokter spesialis, atau satu polis asuransi dimiliki oleh 2 pemegang polis dengan persentase kepemilikan berbeda).
- **Mekanisme**: Memisahkan hubungan *Many-to-Many* melalui *Bridge Table* yang berisi *Surrogate Key Group*, *Individual Keys*, dan **Allocation Factor** (bobot bobot persentase).
- **Kompensasi Double-Counting**: Total penjumlahan metrik numerik harus dikalikan dengan `allocation_factor` jika dianalisis per atribut dimensi individual, atau dievaluasi secara utuh jika dianalisis pada level transaksi.

### 3.2 Advanced Slowly Changing Dimensions

#### SCD Tipe 4 (Mini-Dimensions)
Digunakan saat dimensi memiliki volume baris masif (puluhan juta pengguna) dengan subset atribut profil yang berubah sangat sering (*rapidly changing attributes*, misal: rentang umur, kelompok pengeluaran bulanan, *risk band*, *credit score*).
- Jika menggunakan SCD Tipe 2 murni, ukuran tabel dimensi akan meledak (*row explosion*) karena perubahan sering terjadi pada atribut minor.
- **Solusi Tipe 4**: Atribut statis tetap berada di `dim_customer`, sedangkan atribut yang sering berubah diekstraksi ke dalam `dim_customer_profile_band` (*Mini-Dimension*). Tabel fakta kemudian mereferensikan dua foreign key sekaligus: `customer_key` dan `customer_profile_band_key`.

#### SCD Tipe 6 (Hybrid 1 + 2 + 3)
Kombinasi struktural dari Tipe 1, 2, dan 3 dalam satu tabel (`1 + 2 + 3 = 6`):
- **Tipe 2**: Menyimpan riwayat perubahan baris baru (`valid_from`, `valid_to`, `is_current`).
- **Tipe 3**: Menyimpan nilai masa lalu langsung di baris saat ini (`historic_territory`).
- **Tipe 1**: Menyimpan nilai terkini di seluruh baris historis (`current_territory`).
- **Kegunaan**: Memungkinkan analis melakukan pelaporan metrik historis berdasarkan struktur organisasi masa lalu (*as-was*) ATAU memetakan ulang seluruh transaksi masa lalu ke struktur organisasi terkini (*as-is*) tanpa komputasi join window yang kompleks.

### 3.3 Storage Internals: Columnar Warehouses & Micro-Partitioning
Pada sistem seperti Snowflake, Google BigQuery, atau AWS Redshift, data dimensional tidak disimpan dalam format blok baris tradisional (OLTP B-Tree).
- **Micro-Partitioning & Pruning**: Data dipartisi secara horizontal menjadi blok-blok terkompresi (50MB - 500MB). Setiap micro-partition memuat metadata nilai minimum dan maksimum (*min/max range*) untuk setiap kolom.
- **Efek Join Star Schema**: Join antara Fact besar dan Dimensi kecil dieksekusi melalui **Broadcast Join** (dimensi disalin ke seluruh node komputasi). Jika dimensi membengkak akibat SCD Tipe 2 yang tidak terkendali, query engine beralih ke **Hash/Shuffle Join**, yang mendistribusikan data transaksi melalui jaringan dan menyebabkan penurunan performa secara drastis (*network spill-to-disk*).

---

## 4. Why & What

| Dimensi Masalah | Solusi Konvensional (Anti-Pattern) | Solusi Enterprise (Pola Lanjutan) | Dampak Bisnis / Teknis |
| :--- | :--- | :--- | :--- |
| **Siklus Transaksi Panjang** | Mengandalkan kueri join berkali-kali ke log mutasi status operasional. | **Accumulating Snapshot Fact Table**. | Mengurangi runtime kueri dashboard SLA dari menit menjadi sub-detik; metrik durasi antar-tahap terhitung *out-of-the-box*. |
| **Relasi Atribut M:N** | Melakukan string-aggregation (misal: JSON/CSV array di kolom fakta) atau denormalisasi baris fakta. | **Bridge Table dengan Allocation Factor**. | Menghilangkan duplikasi nominal transaksi (*double-counting*); memungkinkan audit pembagian margin/insentif yang presisi. |
| **Perubahan Data Cepat** | Menggunakan SCD Tipe 2 untuk seluruh ratusan atribut pelanggan. | **SCD Tipe 4 (Mini-Dimensions)**. | Mencegah pembengkakan kapasitas *storage* hingga 80%; membatasi frekuensi *full-table reindexing/clustering*. |
| **Urutan Event Rusak** | Menolak record transaksi jika referensi dimensi belum ada di DWH (*pipeline failure*). | **Late-Arriving Dimensions Handling (Inferred Members)**. | Nol *data loss*; integritas finansial terjaga; metrik analitik segera tersedia dan direkonsiliasi otomatis. |

---

## 5. How (Workflow Detail)

### 5.1 Siklus Implementasi Late-Arriving Data (Inferred Dimension Pattern)

```
[Streaming / Batch Source]
            |
            v
   [Cek Foreign Key]  ---- (Dimensi Belum Ada?) ----> [Generate Inferred Row]
            |                                                    |
            | (Dimensi Ditemukan)                                v
            |                                     INSERT INTO dim_account (
            |                                       account_sk, account_id,
            |                                       is_inferred, valid_from
            |                                     ) VALUES (uuid, 'ACC-99', TRUE, '1970-01-01');
            |                                                    |
            +--------------------+-------------------------------+
                                 |
                                 v
                     [INSERT INTO fact_transactions]
                                 |
                                 v  (Beberapa jam/hari kemudian...)
                 [Source Ekstraksi Dimensi Mengirim Data]
                                 |
                                 v
               [UPDATE Inferred Row dengan Data Valid]
                     - Ubah Nama, Status, Atribut Aktual
                     - Set is_inferred = FALSE
```

1. **Ingestion Evaluation**: Event transaksi tiba dengan `account_id = 'ACC-99'`. Pipeline melakukan lookup ke `dim_account`.
2. **Inferred Member Creation**: Bila key tidak ditemukan, engine analitik tidak melempar *error*, melainkan men-generate baris *placeholder* pada dimensi dengan atribut default (`Nama = 'Unknown/Inferred'`, `is_inferred = TRUE`, `valid_from = '1970-01-01 00:00:00'`).
3. **Fact Attachment**: Baris fakta tetap di-insert menggunakan *Surrogate Key* dari baris *placeholder* tersebut. Dashboard tidak terputus.
4. **Late Reconciliation**: Ketika pipeline dimensi mengekstraksi metadata master akun pada jadwal berikutnya, sistem mendeteksi keberadaan *placeholder* (`is_inferred = TRUE`), lalu menimpa atribut dengan data otentik dan mengubah penanda `is_inferred = FALSE`.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi: Kartu Rekam Medis Rumah Sakit

Bayangkan sistem administrasi rumah sakit:
- **Transaction Fact**: Setiap kali Anda disuntik atau ditebuskan obat, keluar sebuah struk pembayaran kasir.
- **Accumulating Snapshot**: Satu map rekam medis rawat inap Anda. Dimulai dari *Waktu Pendaftaran*, diisi *Waktu Masuk Kamar Operasi*, diisi *Waktu Pindah Ruang Pemulihan*, dan ditutup pada *Waktu Keluar RS*. Satu map fisik diperbarui secara bertahap sepanjang Anda dirawat.
- **Bridge Table**: Jika dalam tindakan bedah Anda ditangani oleh Tim Anestesi, Tim Bedah Saraf, dan Tim Kardiovaskular, faktur operasi tidak memuat 3 baris salinan yang identik (yang akan melipatgandakan biaya rumah sakit secara fiktif). Faktur merujuk pada *Tim Medis ID*, dan dokumen *Bridge* merinci: Dokter A (40%), Dokter B (40%), Dokter C (20%).

```
                      +-----------------------------+
                      |      dim_patient (SCD2)     |
                      +-----------------------------+
                                     |
                                     | 1
                                     |
                                     v N
+---------------------------------------------------------------------------------+
|                         fct_hospital_encounter (Accumulating)                   |
+---------------------------------------------------------------------------------+
| encounter_sk (PK)                                                               |
| patient_sk (FK)                                                                 |
| physician_group_sk (FK) ----+                                                   |
| triage_start_time           |                                                   |
| consultation_end_time       |                                                   |
| discharge_time              |                                                   |
| wait_duration_minutes       |                                                   |
| total_claim_amount          |                                                   |
+-----------------------------+---------------------------------------------------+
                              |
                              v 1
               +------------------------------+
               |   brg_physician_group (M:N)  |
               +------------------------------+
               | physician_group_sk           |
               | physician_sk (FK)            |
               | allocation_weight (e.g. 0.5) |
               +------------------------------+
                              |
                              v N
               +------------------------------+
               |      dim_physician (SCD1)    |
               +------------------------------+
               | physician_sk                 |
               | physician_name               |
               | specialization               |
               +------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: SCD Tipe 4 (Mini-Dimension Implementation)

Pemisahan atribut statis dan atribut berfrekuensi perubahan tinggi (*Income Band* dan *Credit Rating*).

```sql
-- 1. Mini-Dimension (Tabel Dimensi Profil Finansial - Ringkas, kombinasi terbatas)
CREATE TABLE dim_financial_profile_band (
    financial_profile_sk INT IDENTITY(1,1) PRIMARY KEY,
    income_bracket VARCHAR(50) NOT NULL,
    credit_score_range VARCHAR(50) NOT NULL,
    risk_category VARCHAR(20) NOT NULL
);

INSERT INTO dim_financial_profile_band (income_bracket, credit_score_range, risk_category)
VALUES 
    ('< 10M IDR', '300-579', 'VERY HIGH'),
    ('< 10M IDR', '580-669', 'HIGH'),
    ('10M-25M IDR', '670-739', 'MEDIUM'),
    ('> 25M IDR', '740-850', 'LOW');

-- 2. Base Customer Dimension (Hanya atribut statis/jarang berubah)
CREATE TABLE dim_customer (
    customer_sk INT IDENTITY(1,1) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(10) NOT NULL
);

-- 3. Fact Table yang menggabungkan keduanya
CREATE TABLE fct_loan_application (
    application_id VARCHAR(64) PRIMARY KEY,
    application_date DATE NOT NULL,
    customer_sk INT NOT NULL REFERENCES dim_customer(customer_sk),
    financial_profile_sk INT NOT NULL REFERENCES dim_financial_profile_band(financial_profile_sk),
    loan_amount NUMERIC(18,2) NOT NULL
);
```

### 7.2 Practical Example: Production dbt Implementation for Accumulating Snapshot

Berikut adalah implementasi modern pipeline *Accumulating Snapshot* untuk order fulfillment menggunakan dbt (*incremental merge*).

```sql
-- File: models/marts/core/fct_order_fulfillment_accumulating.sql

{{
  config(
    materialized = 'incremental',
    unique_key = 'order_id',
    incremental_strategy = 'merge',
    cluster_by = ['order_status', 'placed_date_key']
  )
}}

WITH source_orders AS (
    SELECT * FROM {{ ref('stg_ecommerce__orders') }}
    {% if is_incremental() %}
      -- Mengambil order yang baru dibuat ATAU yang mengalami mutasi status dalam 30 hari terakhir
      WHERE updated_at >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    {% endif %}
),

source_shipments AS (
    SELECT * FROM {{ ref('stg_logistics__shipments') }}
),

source_deliveries AS (
    SELECT * FROM {{ ref('stg_logistics__deliveries') }}
)

SELECT
    -- Degenerate Dimension
    o.order_id,
    
    -- Surrogate Keys
    COALESCE(c.customer_sk, -1) AS customer_sk,
    
    -- Date Dimension FKs (Role Playing Dates)
    TO_CHAR(o.created_at, 'YYYYMMDD')::INT AS placed_date_key,
    TO_CHAR(o.paid_at, 'YYYYMMDD')::INT AS paid_date_key,
    TO_CHAR(s.shipped_at, 'YYYYMMDD')::INT AS shipped_date_key,
    TO_CHAR(d.delivered_at, 'YYYYMMDD')::INT AS delivered_date_key,
    
    -- Degenerate Attributes
    o.order_status,
    s.tracking_number,
    
    -- Milestone Durations (Metrics Lag dihitung di grain transaksi)
    DATEDIFF('hour', o.created_at, o.paid_at) AS hours_to_pay,
    DATEDIFF('hour', o.paid_at, s.shipped_at) AS hours_to_ship,
    DATEDIFF('hour', s.shipped_at, d.delivered_at) AS hours_to_deliver,
    DATEDIFF('day', o.created_at, d.delivered_at) AS total_fulfillment_days,
    
    -- Financial Facts (Additive)
    o.total_order_amount,
    s.shipping_cost_amount,
    
    -- System Audit Timestamps
    CURRENT_TIMESTAMP() AS dwh_updated_at

FROM source_orders o
LEFT JOIN {{ ref('dim_customer') }} c 
    ON o.customer_id = c.customer_id 
    AND c.is_current = TRUE
LEFT JOIN source_shipments s 
    ON o.order_id = s.order_id
LEFT JOIN source_deliveries d 
    ON s.shipment_id = d.shipment_id
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: FinTech Peer-to-Peer Lending (Investasi & Penyaluran Pinjaman Multi-Partner)

**Skala Masalah**:
- Platform memproses 20.000 pengajuan pinjaman per hari dengan siklus pendanaan yang kompleks: *Submitted* -> *Risk Verified* -> *Marketplace Published* -> *Partially Funded* -> *Fully Funded* -> *Disbursed* -> *Defaulted / Fully Repaid*.
- **Problem 1 (M:N Attribution)**: Satu pinjaman dapat didanai oleh hingga 50 *investor individual* dan *institutional lenders* dengan persentase porsi modal yang unik. Tim analitik bisnis melakukan *double counting* sebesar 340% pada nominal pinjaman saat menganalisis volume lending berdasarkan geografi investor.
- **Problem 2 (Late Arrival Data)**: Data pengesahan tanda tangan elektronik dari vendor pihak ketiga sering masuk H+3 hari kerja setelah pencairan, merusak urutan kueri analitik berbasis timestamp.

**Solusi Arsitektur**:
1. **Accumulating Fact Table**: `fct_loan_lifecycle` dibangun dengan seluruh *checkpoint timestamp* dan *lag duration* antar-tahap (waktu verifikasi kredit, waktu listing marketplace, hingga pelunasan).
2. **Bridge Table dengan Normalisasi Alokasi**: 
   - Dibuat `brg_loan_funding_syndicate` yang menyimpan pasangan `loan_id`, `investor_sk`, dan `funding_share_pct` (jumlah total per pinjaman terverifikasi bernilai tepat `1.000000`).
   - Query BI analitik difasilitasi dengan metrik terbobot (*Weighted Funded Amount*):
     $$\text{Weighted Amount} = \text{Original Loan Amount} \times \text{funding\_share\_pct}$$
3. **Late-Arriving Handler di Pipeline Orchestration**:
   - Jika signature masuk terlambat, baris akumulasi diperbarui menggunakan model *merge-upsert* berdasar `loan_id` tanpa mengubah histori record pencairan (*disbursement*) yang telah dikunci secara finansial.

---

## 9. Trade-offs

```
                  ACCUMULATING SNAPSHOT vs TRANSACTION GRAIN
                  
 [Transaction Fact]                           [Accumulating Snapshot]
 - Append Only                                - High In-place Updates (I/O Cost)
 - Sederhana di ELT/ETL                       - Logika Pipeline Kompleks (Merge)
 - Analisis siklus hidup butuh kueri          - Kueri Analisis SLA secepat kilat
   kompleks (Multiple Self-Joins)             - Boros jika lifecycle tidak pasti
```

| Pendekatan | Keuntungan Utama | Kompensasi / Kerugian | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Bridge Table (M:N)** | Mempertahankan granularitas asli tanpa denormalisasi struktural yang memicu anomali. | BI tools tanpa dukungan kalkulasi otomatis rentan melakukan *aggregate double-counting*. Performa join melambat. | Relasi M:N yang memiliki bobot/proporsi eksplisit (contoh: komisi penjualan tim, multi-diagnosis). |
| **Denormalisasi Flat (Array/Repeated Columns)** | Performa kueri sangat cepat di BigQuery/Snowflake modern (minim join). | Mengunci portabilitas data; kueri membutuhkan operator khusus (*UNNEST/FLATTEN*) yang tidak ramah SQL standar. | Skema internal analitik non-SQL-standard atau arsitektur Document-First. |
| **SCD Tipe 6** | Kemampuan fleksibel untuk analisis *as-was* dan *as-is* dalam satu representasi dimensi. | Kompleksitas tinggi saat memelihara pipeline ETL; risiko data drift jika logic update Tipe 1 gagal sinkron. | Organisasi enterprise dengan restrukturisasi hierarki divisi/regional yang sering terjadi. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Fan-Out Trap pada Kueri Bridge Table
*Gejala*: Total nilai penjualan di dashboard melonjak berkali-kali lipat dari target aktual perusahaan setelah menambahkan dimensi baru.

*Penyebab Root-Cause*: Analis melakukan join langsung dari Fact ke Dimensi melalui Bridge Table tanpa mengalikan metrik numerik dengan `allocation_factor`.

*Debug & Solusi*:
```sql
-- KESALAHAN (FATAL: Memicu Double Counting):
SELECT 
    d.doctor_specialization,
    SUM(f.consultation_fee) AS total_revenue -- Total melonjak jika 1 konsultasi ditangani >1 dokter!
FROM fct_medical_consultation f
JOIN brg_consultation_doctor b ON f.consultation_id = b.consultation_id
JOIN dim_doctor d ON b.doctor_sk = d.doctor_sk
GROUP BY 1;

-- SOLUSI PERBAIKAN:
SELECT 
    d.doctor_specialization,
    SUM(f.consultation_fee * b.allocation_factor) AS total_revenue_allocated
FROM fct_medical_consultation f
JOIN brg_consultation_doctor b ON f.consultation_id = b.consultation_id
JOIN dim_doctor d ON b.doctor_sk = d.doctor_sk
GROUP BY 1;
```

### 10.2 SCD Tipe 2 Timestamp Overlap
*Gejala*: Kueri analitik berbasis *Point-in-Time* (`BETWEEN valid_from AND valid_to`) mengembalikan 2 record untuk satu entitas pada detik yang sama.

*Penyebab Root-Cause*: Operator pembaruan dimensi menggunakan `valid_to = CURRENT_TIMESTAMP()` pada record lama dan `valid_from = CURRENT_TIMESTAMP()` pada record baru tanpa resolusi sub-detik atau inkonsistensi interval tertutup/terbuka.

*Solusi Standar Industri*: Terapkan konvensi interval **setengah terbuka** (*half-open interval*): `valid_from <= event_timestamp AND event_timestamp < valid_to`. Gunakan `valid_to` berstatus tak terhingga (misal: `'9999-12-31 23:59:59'`) untuk membedakan baris aktif saat ini.

---

## 11. Best Practices (Production Checklist)

- [ ] **Definisi Grain Tertulis**: Grain dari setiap tabel fakta harus terdokumentasi eksplisit di metadata data catalog (misal: *"Satu baris merepresentasikan status terkini dari satu aplikasi pinjaman"*).
- [ ] **Standardisasi Unknown / Inferred Key**: Gunakan Surrogate Key `-1` untuk merepresentasikan atribut yang *belum diketahui / terlambat tiba*, hindari membiarkan kolom FK bernilai `NULL`.
- [ ] **Konsistensi Bridge Allocation**: Pastikan terdapat constraint atau data-test (dbt assertion) bahwa $\sum (\text{allocation\_factor}) = 1.000000$ untuk setiap entitas dalam Bridge Table.
- [ ] **Degenerate Dimension Isolation**: Jangan membuat tabel dimensi mandiri untuk atribut pengenal yang berdiri sendiri (seperti *Invoice Number*, *Order ID*); tempatkan langsung sebagai *Degenerate Dimension* di tabel fakta.
- [ ] **Partisi dan Clustering Sesuai Pola Kueri**: Tabel fakta snapshot terakumulasi wajib di-*cluster* berdasarkan `status` dan `primary milestone date`, bukan pada surrogate key inkremental.
- [ ] **Idempotensi Pipeline**: Skrip ETL/ELT pembaruan fakta snapshot terakumulasi harus aman dieksekusi berulang kali (*idempotent*) tanpa menghasilkan duplikasi baris (*Upsert / Merge logic*).

---

## 12. Hands-on Practice

Buat seluruh file latihan berikut di dalam repositori proyek lokal pada path: `hands-on/m02/`.

### Langkah 1: Setup DDL Skema Advanced
Simpan kode berikut sebagai `hands-on/m02/01_schema_setup.sql`.

```sql
-- hands-on/m02/01_schema_setup.sql
CREATE SCHEMA IF NOT EXISTS advanced_dwh;

-- 1. Dimensi Pasien (SCD Tipe 2)
CREATE TABLE advanced_dwh.dim_patient (
    patient_sk INT IDENTITY(1,1) PRIMARY KEY,
    patient_id VARCHAR(32) NOT NULL,
    patient_name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    is_current BOOLEAN NOT NULL
);

-- 2. Dimensi Dokter (SCD Tipe 1)
CREATE TABLE advanced_dwh.dim_doctor (
    doctor_sk INT IDENTITY(1,1) PRIMARY KEY,
    doctor_id VARCHAR(32) NOT NULL UNIQUE,
    doctor_name VARCHAR(100) NOT NULL,
    specialty VARCHAR(50) NOT NULL
);

-- 3. Bridge Table Dokter (Many-to-Many Handling)
CREATE TABLE advanced_dwh.brg_treatment_doctor (
    treatment_group_id VARCHAR(32) NOT NULL,
    doctor_sk INT NOT NULL REFERENCES advanced_dwh.dim_doctor(doctor_sk),
    allocation_factor NUMERIC(5,4) NOT NULL,
    PRIMARY KEY (treatment_group_id, doctor_sk)
);

-- 4. Accumulating Snapshot Fact Table (Perjalanan Pasien Rawat Inap)
CREATE TABLE advanced_dwh.fct_inpatient_lifecycle (
    encounter_id VARCHAR(32) PRIMARY KEY,
    patient_sk INT NOT NULL REFERENCES advanced_dwh.dim_patient(patient_sk),
    treatment_group_id VARCHAR(32) NOT NULL,
    
    -- Milestone Timestamps
    admitted_at TIMESTAMP NOT NULL,
    diagnosed_at TIMESTAMP,
    surgery_started_at TIMESTAMP,
    discharged_at TIMESTAMP,
    
    -- Calculated Lags (Hours)
    lag_admission_to_diagnosis_hrs NUMERIC(8,2),
    lag_diagnosis_to_surgery_hrs NUMERIC(8,2),
    total_stay_duration_days NUMERIC(8,2),
    
    -- Metrics
    total_treatment_cost NUMERIC(14,2) NOT NULL,
    encounter_status VARCHAR(20) NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### Langkah 2: Simulasi Data & Injeksi Anomali M:N
Simpan kode berikut sebagai `hands-on/m02/02_seed_data.sql`.

```sql
-- hands-on/m02/02_seed_data.sql

-- Isi Dimensi Pasien
INSERT INTO advanced_dwh.dim_patient (patient_id, patient_name, city, valid_from, valid_to, is_current)
VALUES 
    ('P-001', 'Budi Santoso', 'Jakarta', '2023-01-01 00:00:00', '9999-12-31 23:59:59', TRUE),
    ('P-002', 'Siti Aminah', 'Surabaya', '2023-01-01 00:00:00', '9999-12-31 23:59:59', TRUE);

-- Isi Dimensi Dokter
INSERT INTO advanced_dwh.dim_doctor (doctor_id, doctor_name, specialty)
VALUES 
    ('DOC-A', 'dr. Hartono, Sp.B', 'Bedah Umum'),
    ('DOC-B', 'dr. Linda, Sp.An', 'Anestesiologi'),
    ('DOC-C', 'dr. Kevin, Sp.JP', 'Jantung');

-- Hubungan M:N Tim Medis Operasi (Group: GRP-SURG-101)
-- Operasi kolaboratif: dr. Hartono (60%), dr. Linda (40%)
INSERT INTO advanced_dwh.brg_treatment_doctor (treatment_group_id, doctor_sk, allocation_factor)
VALUES 
    ('GRP-SURG-101', 1, 0.6000),
    ('GRP-SURG-101', 2, 0.4000);

-- Kasus Individual: dr. Kevin menangani penuh (100%)
INSERT INTO advanced_dwh.brg_treatment_doctor (treatment_group_id, doctor_sk, allocation_factor)
VALUES 
    ('GRP-CARD-202', 3, 1.0000);
```

### Langkah 3: Pipeline Idempotent Upsert (Accumulating Snapshot Logic)
Simpan skrip berikut sebagai `hands-on/m02/03_accumulating_pipeline.sql`. Skrip ini mensimulasikan pembaruan bertahap (In-place merge logic).

```sql
-- hands-on/m02/03_accumulating_pipeline.sql

-- TAHAP 1: Pasien baru masuk (Admission)
MERGE INTO advanced_dwh.fct_inpatient_lifecycle AS target
USING (
    SELECT 
        'ENC-88901' AS encounter_id,
        1 AS patient_sk,
        'GRP-SURG-101' AS treatment_group_id,
        TIMESTAMP '2024-03-01 08:00:00' AS admitted_at,
        CAST(NULL AS TIMESTAMP) AS diagnosed_at,
        CAST(NULL AS TIMESTAMP) AS surgery_started_at,
        CAST(NULL AS TIMESTAMP) AS discharged_at,
        2500000.00 AS total_treatment_cost,
        'ADMITTED' AS encounter_status
) AS source
ON target.encounter_id = source.encounter_id
WHEN MATCHED THEN 
    UPDATE SET 
        diagnosed_at = source.diagnosed_at,
        surgery_started_at = source.surgery_started_at,
        discharged_at = source.discharged_at,
        encounter_status = source.encounter_status,
        updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN 
    INSERT (encounter_id, patient_sk, treatment_group_id, admitted_at, total_treatment_cost, encounter_status, updated_at)
    VALUES (source.encounter_id, source.patient_sk, source.treatment_group_id, source.admitted_at, source.total_treatment_cost, source.encounter_status, CURRENT_TIMESTAMP);

-- TAHAP 2: Pasien telah didiagnosa dan dioperasi (Mutasi In-place)
MERGE INTO advanced_dwh.fct_inpatient_lifecycle AS target
USING (
    SELECT 
        'ENC-88901' AS encounter_id,
        TIMESTAMP '2024-03-01 11:30:00' AS diagnosed_at,
        TIMESTAMP '2024-03-01 14:00:00' AS surgery_started_at,
        TIMESTAMP '2024-03-03 10:00:00' AS discharged_at,
        18500000.00 AS final_cost,
        'DISCHARGED' AS encounter_status
) AS source
ON target.encounter_id = source.encounter_id
WHEN MATCHED THEN 
    UPDATE SET 
        diagnosed_at = source.diagnosed_at,
        surgery_started_at = source.surgery_started_at,
        discharged_at = source.discharged_at,
        lag_admission_to_diagnosis_hrs = DATEDIFF('minute', target.admitted_at, source.diagnosed_at) / 60.0,
        lag_diagnosis_to_surgery_hrs = DATEDIFF('minute', source.diagnosed_at, source.surgery_started_at) / 60.0,
        total_stay_duration_days = DATEDIFF('hour', target.admitted_at, source.discharged_at) / 24.0,
        total_treatment_cost = source.final_cost,
        encounter_status = source.encounter_status,
        updated_at = CURRENT_TIMESTAMP;
```

---

## 13. Exercise

### 13.1 Level Easy
Rancang query analitik pada tabel `fct_inpatient_lifecycle` yang menampilkan rata-rata `total_stay_duration_days` dan rata-rata `lag_admission_to_diagnosis_hrs` dikelompokkan berdasarkan `encounter_status`.

### 13.2 Level Medium
Tuliskan kueri pelaporan yang menampilkan **Pendapatan Bersih Rumah Sakit per Dokter** berdasarkan data pada `fct_inpatient_lifecycle`, `brg_treatment_doctor`, dan `dim_doctor`. Pastikan nominal `total_treatment_cost` teralokasi secara proporsional sesuai `allocation_factor` tanpa memicu redundansi nilai transaksi!

### 13.3 Level Hard
Sebuah transaksi baru tiba dengan `doctor_id = 'DOC-UNKNOWN-XYZ'` yang belum terdaftar di sistem master dokter (kasus *Late-Arriving Dimension*).
1. Susun prosedur/skrip SQL transaksional yang mengamankan integritas data dengan meng-generate baris *placeholder* pada `dim_doctor` (surrogate key otomatis, name = 'Placeholder Doc', specialty = 'Unassigned').
2. Hubungkan baris fakta tersebut ke bridge dan fact table.
3. Tuliskan kueri mutasi rekonsiliasi yang mengupdate baris *placeholder* ketika master profil dokter tersebut akhirnya tiba 2 hari kemudian.

---

## 14. Challenge

**Skenario Kasus Kompleks: Multi-Currency Multi-Tenant Subscription Engine**
Perusahaan SaaS FinTech beroperasi di 4 negara (Indonesia, Singapura, Filipina, Vietnam) dengan model langganan tahunan di mana tagihan dipecah menjadi beberapa *milestone pembayaran berkala* (Down Payment 30%, Delivery 40%, Maintenance 30%).

Kondisi Lapangan:
1. Pembayaran dilakukan dalam mata uang lokal masing-masing negara (IDR, SGD, PHP, VND), namun pembukuan grup konsolidasi harus dilaporkan dalam USD berdasarkan *kurs transaksi aktual* DAN *kurs penutupan akhir bulan* (Dual-reporting standard).
2. Terdapat tim konsultan yang menangani implementasi langganan klien. Tim terdiri dari 1 Lead Architect dan hingga 4 Senior Engineers. Bonus performa dibagi berdasarkan bobot kontribusi jam kerja yang dicatat dalam sistem eksternal terpisah.
3. Sebagian besar kontrak langganan mengalami perpanjangan dini (*early-renewal*) atau penghentian sepihak (*churn*) di tengah jalan, yang menyebabkan nilai *future recognized revenue* harus dihitung ulang secara historis.

**Tugas Arsitektur**:
Rancang arsitektur dimensional model lengkap:
1. Tentukan Grain, Entity-Relationship Design (Star/Snowflake/Bridge).
2. Tuliskan definisi skema DDL (Fact, Mini-Dimensions, Bridge, Date Role-Playing, Currency Exchange Snapshot).
3. Buat skenario visualisasi alur data dan strategi kalkulasi agar kueri analitik dashboard eksekutif tidak menghasilkan *Cartesian Product* saat memotong performa langganan berdasarkan *Regional Country*, *Exchange Rate Currency*, dan *Consultant Allocation*.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa perbedaan mendasar antara Transaction Fact Table dan Accumulating Snapshot Fact Table dari perspektif operasi DML (*Data Manipulation Language*)?
2. Kapan Anda harus memilih SCD Tipe 4 dibandingkan SCD Tipe 2?
3. Mengapa kolom Foreign Key pada Fact Table tidak disarankan bernilai `NULL` ketika referensi dimensi belum diketahui?
4. Apa fungsi dari kolom `allocation_factor` di dalam sebuah Bridge Table?
5. Mengapa tabel fakta periodic snapshot sangat ideal untuk analisis saldo akhir bulan rekening bank?

### 15.2 Pertanyaan Intermediate
6. Bagaimana cara mencegah terjadinya *fan-out trap* saat meng-query fact table yang dihubungkan dengan 2 bridge table berbeda secara simultan?
7. Pada kondisi modern cloud warehouse berbasis *micro-partitioning*, mengapa SCD Tipe 2 yang menghasilkan miliaran baris baru dapat memperlambat kueri agregasi secara drastis?
8. Bagaimana struktur tabel SCD Tipe 6 memungkinkan analis menjawab pertanyaan analitik "Siapa manajer penjualan saat transaksi terjadi (*as-was*)" DAN "Siapa manajer wilayah tersebut saat ini (*as-is*)"?
9. Apa perbedaan esensial antara *Factless Fact Table for Events* dan *Factless Fact Table for Coverage*?
10. Di pipeline ELT dbt, konfigurasi materialisasi dan strategi apa yang paling tepat digunakan untuk mengelola Accumulating Snapshot Fact Table secara efisien?

### 15.3 Skenario Kasus Produksi
11. **Skenario A (Finansial)**: Pipeline pelaporan keuangan Anda menampilkan total revenue global sebesar 120 Miliar IDR, namun audit internal menemukan total cash flow riil perbankan hanya 100 Miliar IDR. Setelah diusut, kueri analitik Anda menggabungkan tabel `fct_subscription` dengan `brg_partner_referral` tanpa menggunakan agregasi terbobot. Jelaskan formula perbaikan query SQL-nya!
12. **Skenario B (E-commerce Logistics)**: Dashboard pemantauan SLA pengiriman barang mengalami kegagalan kueri (Timeout 15 menit) pada cluster Snowflake. Data historis mencapai 500 juta baris transaksi per tahun. Arsitektur saat ini menggunakan *Transaction Fact* mentah yang melakukan self-join 5 kali ke tabel audit status log untuk menghitung durasi antar milestone status (*Picked*, *Packed*, *In-Transit*, *Delivered*). Rekomendasikan transformasi dimensional model untuk mereduksi latency kueri menjadi di bawah 3 detik!
13. **Skenario C (Streaming Ingestion)**: Sistem menerima event order fulfillment dari Apache Kafka secara real-time. Karena latensi jaringan antar-region cloud, event `order_delivered` tiba di DWH 5 detik LEBIH CEPAT daripada event `order_created`. Bagaimana arsitektur dimensional DWH menangani anomali *Out-of-Order Execution* ini agar data tidak hilang (*orphan record*) dan status milestone akhir tetap akurat?

---

### Jawaban Kunci & Rasionalisasi Evaluasi

#### Jawaban Pertanyaan Basic
1. **Rasionalisasi DML**: Transaction Fact Table bersifat *Append-Only* (hanya operasi `INSERT`), merekam satu peristiwa spesifik yang terjadi di masa lalu. Accumulating Snapshot Fact Table didominasi oleh operasi *Update/Merge In-Place*, di mana satu baris fisik diperbarui berulang kali sepanjang siklus hidup entitas bisnis berlangsung.
2. **Rasionalisasi SCD 4 vs 2**: SCD Tipe 4 dipilih saat dimensi memiliki entitas bervolume masif dan atribut yang berubah memiliki frekuensi sangat tinggi (*rapidly changing attributes*). Memisahkan atribut yang sering berubah ke Mini-Dimension mencegah replikasi baris masif (*row explosion*) pada dimensi utama.
3. **Rasionalisasi Not-NULL FK**: Mengizinkan nilai `NULL` pada FK merusak performa *inner join*, memicu *three-valued logic boolean (TRUE, FALSE, UNKNOWN)* yang rentan menghasilkan bug agregasi, serta menghilangkan kemampuan penelusuran data *unmapped/inferred*. Standardisasinya adalah me-map nilai `NULL` ke surrogate key default (misal `-1`).
4. **Rasionalisasi Allocation Factor**: Menghindari *double counting*. Kolom ini merepresentasikan bobot pembagian proporsional (0.0 hingga 1.0) sehingga metrik numerik dapat dialokasikan dengan akurat ketika satu transaksi diasosiasikan dengan banyak anggota dimensi.
5. **Rasionalisasi Periodic Snapshot**: Menghitung saldo akhir bulan dari seluruh mutasi debit-kredit transaksi harian (*transaction fact*) untuk jutaan nasabah membutuhkan kueri agregasi historis yang luar biasa berat. Periodic Snapshot menyediakan status saldo agregat pada *checkpoint* interval waktu berkala secara langsung.

#### Jawaban Pertanyaan Intermediate
6. **Mitigasi Fan-Out Multi-Bridge**: Jangan pernah melakukan join dua bridge table secara langsung ke satu tabel fakta dalam satu kueri datar (*flat SELECT*). Eksekusi agregasi metrik secara terpisah pada subquery CTE yang mengisolasi masing-masing bridge table, kemudian satukan hasil akhir agregasi tersebut pada level *grain* yang sama menggunakan `JOIN` sederhana.
7. **Dampak Micro-Partitioning SCD 2**: Pembengkakan baris akibat SCD Tipe 2 membuat range metadata *min-max* pada micro-partition menjadi overlap secara masif. Akibatnya, query pruning optimizer tidak dapat mengeliminasi partisi yang tidak relevan, memaksa engine melakukan *Full Table Scan* dan network data shuffling (*Hash Join* antar compute cluster).
8. **Mekanisme SCD Tipe 6**:
   - Analisis *As-Was*: Menggunakan kolom dimensi versi historis saat transaksi dicatat (mereferensikan `customer_sk` spesifik pada rentang `valid_from` - `valid_to`).
   - Analisis *As-Is*: Menggunakan kolom `current_attribute` yang disimpan langsung di baris dimensi tersebut atau di-*overwrite* via Tipe 1 di seluruh histori baris dimensi yang memiliki *business key* sama.
9. **Event vs Coverage Factless**:
   - *Event Tracking*: Menguji apakah interaksi terjadi (misal: log klik pengguna, pencatatan log kehadiran mahasiswa).
   - *Coverage Table*: Memetakan kemungkinan ruang kombinasi bisnis untuk menemukan *apa yang tidak terjadi* (misal: mencatat seluruh toko dan produk yang aktif dipromosikan pada minggu X untuk mendeteksi toko mana yang gagal menjual produk promo tersebut).
10. **dbt Accumulating Configuration**: Konfigurasi terbaik adalah `materialized = 'incremental'`, `incremental_strategy = 'merge'`, dengan parameter `unique_key = 'business_entity_id'` dan `cluster_by` pada kolom status atau tanggal pembuatan entitas. Filter inkremental harus melingkupi jendela mutasi bisnis (misal: `updated_at >= DATEADD('day', -30, CURRENT_TIMESTAMP())`).

#### Jawaban Skenario Kasus Produksi
11. **Rasionalisasi Skenario A**: Formula SQL salah karena tidak memperhitungkan faktor pembobotan partner. Kueri harus diperbaiki dengan mengalikan kolom nominal terhadap allocation factor:
   ```sql
   SELECT 
       p.partner_name,
       SUM(f.subscription_amount * b.allocation_share) AS true_attributed_revenue
   FROM fct_subscription f
   JOIN brg_partner_referral b ON f.subscription_id = b.subscription_id
   JOIN dim_partner p ON b.partner_sk = p.partner_sk
   GROUP BY 1;
   ```
12. **Rasionalisasi Skenario B**: Lakukan transformasi arsitektural dari *Transaction Log Fact* menjadi **Accumulating Snapshot Fact Table** (`fct_shipment_fulfillment`). Tabel fakta ini memuat satu baris per nomor resi (*tracking_number*), dengan kolom tanggal spesifik untuk setiap status (`picked_at`, `packed_at`, `in_transit_at`, `delivered_at`) dan kolom kalkulasi langsung durasi SLA (`hours_picked_to_packed`, `hours_packed_to_transit`, `hours_transit_to_delivered`). Dashboard analitik cukup membaca baris flat ini tanpa ada komputasi self-join runtime. Waktu respons kueri berkurang secara drastis dari menit ke sub-detik.
13. **Rasionalisasi Skenario C**: Terapkan pola **Inferred Accumulating State**:
   - Ketika event `order_delivered` tiba lebih dulu, pipeline tetap melakukan operasi `MERGE`.
   - Baris fakta baru di-insert dengan `order_id` tersebut, mengisi kolom `delivered_at`, menandai kolom `placed_at = NULL` atau *default inferred*, serta menyematkan status teknis `is_incomplete_milestone = TRUE`.
   - Ketika event `order_created` tiba terlambat, statement `MERGE` mendeteksi keberadaan baris via `order_id`, melakukan update pada kolom `placed_at`, menghitung ulang seluruh lag metrik waktu penyelesaian, dan mematikan flag `is_incomplete_milestone = FALSE`. Data tetap utuh, terisolasi, dan tidak ada paket record yang hilang.

---

## 16. Summary

1. **Struktur Model Lanjutan Mengikuti Karakter Alur Bisnis**:
   - Gunakan *Transaction Fact* untuk histori atomic append-only.
   - Gunakan *Periodic Snapshot* untuk memotret saldo/posisi inventori pada interval waktu teratur.
   - Gunakan *Accumulating Snapshot* untuk mengaudit performa alur kerja multi-milestone terikat waktu.

2. **Resolusi Hubungan Banyak-ke-Banyak Wajib Menjamin Integritas Finansial**:
   - Penerapan *Bridge Tables* wajib menyertakan atribut bobot (*Allocation Factor*).
   - Analis BI harus menjamin bahwa metrik skalar dikalikan dengan alokasi bobot sebelum dieksekusi fungsi agregasi (`SUM`) guna mengeliminasi bencana *double counting*.

3. **Optimasi Modern Columnar Warehouse Berpusat pada Efisiensi Partisi**:
   - Pemilihan pola SCD (Tipe 2 vs Tipe 4 vs Tipe 6) berdampak langsung terhadap stabilitas *micro-partition pruning* dan *join network shuffling*.
   - Pisahkan atribut dengan frekuensi pembaruan tinggi ke dalam *Mini-Dimensions* (SCD 4) untuk mempertahankan kestabilan tabel dimensi utama.

4. **Kekebalan Pipeline Analitik Terhadap Gangguan Data Operasional**:
   - Skenario *Late-Arriving Facts* dan *Late-Arriving Dimensions* diselesaikan melalui pola *Inferred Dimensions Placeholder* dan *Idempotent In-Place Merge*, memastikan dashboard analitik enterprise beroperasi 24/7 tanpa risiko terhenti akibat anomali latensi transmisi upstream data.