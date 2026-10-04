# TRACK: Business Intelligence Analyst (BI Analyst)
## BAB 01: Fondasi Arsitektur Enterprise BI & Ekosistem Data Modern
### MODULE 01: Modern Business Intelligence Ecosystem, Analytics Value Chain, dan Data Flow Architecture

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (C4)** perbedaan struktural, mekanika pemrosesan, dan pola akses antara sistem Online Transaction Processing (OLTP) dan Online Analytical Processing (OLAP) dalam skala enterprise.
- **Mengevaluasi (C5)** pergeseran arsitektur analitik dari Traditional ETL (Extract-Transform-Load) menuju Modern ELT (Extract-Load-Transform) berbasis Cloud Data Warehouse/Lakehouse.
- **Merancang (C6)** alur *end-to-end data value chain* mulai dari *raw ingestion*, *semantic modeling*, hingga konsumsi analitik (*executive dashboards* & *ad-hoc reporting*).
- **Mendiagnosis (C4)** anomali data, *schema drift*, dan fragmentasi metrik pada layer presentasi analitik dengan menerapkan prinsip *Single Source of Truth* (SSOT).

---

### 2. Conceptual Foundation
Business Intelligence (BI) modern bukan sekadar pembuatan visualisasi data (*chart visualizer*), melainkan rekayasa sistem pengambilan keputusan terdistribusi (*distributed decision engineering system*). BI modern menjembatani kesenjangan antara sistem operasional mentah yang terdistribusi dan kebutuhan analitik non-teknis melalui standarisasi semantik.

Fondasi BI bertumpu pada **Analytics Value Chain** (rantai nilai analitik):
1. **Descriptive Analytics**: Apa yang terjadi? (*Historical aggregation* via OLAP).
2. **Diagnostic Analytics**: Mengapa hal tersebut terjadi? (*Drill-down*, *slicing & dicing*, korelasi metrik).
3. **Predictive Analytics**: Apa yang kemungkinan besar akan terjadi? (*Statistical trend*, forecasting pipeline).
4. **Prescriptive Analytics**: Tindakan apa yang harus dieksekusi? (*Automated alerting*, reverse ETL ke sistem operasional).

Seorang BI Analyst beroperasi terutama pada lapisan *Descriptive* dan *Diagnostic* dengan ekspansi bertahap menuju *Predictive/Prescriptive*, bertindak sebagai kustodian dari *Semantic Layer*—abstraksi logika bisnis di atas data mentah.

---

### 3. Business & Technical Rationale (Why)
- **Business Rationale**: Tanpa standardisasi BI terpusat, timbul fenomena *Metric Discrepancy Chaos*. Sebagai contoh, Departemen Finansial mendefinisikan *Revenue* berbasis *invoices generated*, sedangkan Departemen Penjualan mendefinisikannya berbasis *cash received*. Perbedaan ini menghasilkan laporan eksekutif yang bertentangan dan degradasi kepercayaan terhadap data (*data distrust*).
- **Technical Rationale**: Memaksa sistem OLTP (PostgreSQL, MySQL, Oracle) melayani kueri agregasi analitik (`GROUP BY`, `SUM`, multi-table joins ratusan juta baris) akan memicu *table locking*, kehabisan I/O *buffer pool*, dan menurunkan performa aplikasi transaksional inti. OLAP memisahkan beban kerja transaksional (berorientasi baris/row-oriented) dari beban analitik (berorientasi kolom/columnar).

---

### 4. Core Architecture / Mechanisms (What)
Arsitektur ekosistem BI kontemporer terdiri dari lima layer inti:

```
[Operational Sources (OLTP/SaaS/Logs)]
                  │
                  ▼ (Ingestion Engine: Batch / Change Data Capture)
[Raw Storage Layer (Data Lake / Cloud Storage)]
                  │
                  ▼ (Transformation & Data Modeling: dbt / Spark)
[Enterprise Data Warehouse (OLAP Engine: Columnar, Massively Parallel)]
                  │
                  ▼ (Semantic / Metric Layer: LookML, Power BI Dataset, MetricFlow)
[Consumption / Delivery (Dashboards, Embedded Analytics, Ad-hoc, Reverse ETL)]
```

#### Komponen Kritis:
1. **Columnar Storage & Compression**: OLAP menyimpan data per kolom, bukan per baris. Operasi seperti `SUM(sales_amount)` hanya membaca blok disk untuk kolom `sales_amount`, menghemat I/O hingga 90% melalui teknik kompresi *Run-Length Encoding* (RLE) atau *Dictionary Encoding*.
2. **Semantic Layer**: Abstraksi logis di mana dimensi, hierarki, dan ukuran (*measures*) didefinisikan satu kali (*DRY principle: Don't Repeat Yourself*) dan dikonsumsi oleh berbagai visualizer secara seragam.
3. **Massively Parallel Processing (MPP)**: Distribusi eksekusi kueri analitik ke berbagai compute node secara independen untuk mempercepat agregasi dataset skala terabyte/petabyte.

---

### 5. Implementation Blueprint / Process Flow (How)
Implementasi alur kerja analitik end-to-end mengikuti metodologi *Data-to-Decision Pipeline*:

1. **Ingestion & Staging**: Ekstraksi log transaksional melalui *Change Data Capture* (CDC) menggunakan Kafka/Debezium atau pipeline SaaS (Fivetran/Airbyte) langsung ke *landing zone* Cloud DWH tanpa memodifikasi schema asli.
2. **Cleansing & Conformity**: Sanitasi tipe data, penanganan nilai *null*, deduplikasi, dan standarisasi zona waktu (UTC sebagai standar baku).
3. **Dimensional Modeling**: Penerapan metodologi Kimball (Fact Tables & Dimension Tables) untuk menstrukturkan data ke dalam skema *Star* atau *Snowflake*.
4. **Semantic Layer Compilation**: Definisi metrik teragregasi (misalnya: *Churn Rate*, *Customer Lifetime Value*, *Gross Margin*) ke dalam kode model (*LookML*, *dbt Semantic Layer*, *Tabular Model Definition Language/TMDL*).
5. **Consumption & Alerting**: Pembangunan dasbor performa operasional/strategis dengan *caching layer* terkonfigurasi dan integrasi pelaporan otomatis berbasis ambang batas (*threshold alerts*).

---

### 6. ASCII Architecture / Flow Diagram

```
+---------------------------------------------------------------------------------------+
|                                OPERATIONAL SOURCES (OLTP)                             |
|  +--------------------+  +----------------------+  +-------------------------------+  |
|  | PostgreSQL (Orders)|  | MongoDB (User Events)|  | Salesforce (CRM Pipelines)    |  |
|  +---------+----------+  +----------+-----------+  +---------------+---------------+  |
+------------|------------------------|------------------------------|------------------+
             | CDC                    | Micro-batch                  | REST API
             v                        v                              v
+---------------------------------------------------------------------------------------+
|                          INGESTION & RAW LANDING (DATA LAKE)                          |
|  - S3 / GCS / Azure Data Lake Storage (Parquet, JSON, Avro)                           |
+--------------------------------------------+------------------------------------------+
                                             |
                                             v ELT Worker (dbt / Databricks)
+---------------------------------------------------------------------------------------+
|                         MODERN CLOUD DATA WAREHOUSE (OLAP)                            |
|                                                                                       |
|  [Medallion Architecture]                                                             |
|  +-------------------+      +---------------------+      +-------------------------+  |
|  |   BRONZE LAYER    | ---> |    SILVER LAYER     | ---> |       GOLD LAYER        |  |
|  | Raw Append-Only   |      | Cleansed, Conformed |      | Dimensional Star Schema |  |
|  +-------------------+      +---------------------+      |  - FactSales            |  |
|                                                          |  - DimCustomer          |  |
|                                                          |  - DimDate (Role-Play)  |  |
|                                                          +------------+------------+  |
+-----------------------------------------------------------------------|---------------+
                                                                        v
+---------------------------------------------------------------------------------------+
|                                    SEMANTIC LAYER                                     |
|  - Metric Definitions: Gross Margin = (Rev - COGS) / Rev                              |
|  - Row-Level Security (RLS) & Column-Level Security (CLS)                             |
|  - Caching & Aggregation Engine (Pre-aggregations / VertiPaq / BI Engine)             |
+---------------------------------------+-----------------------------------------------+
                                        |
                 +----------------------+----------------------+
                 v                                             v
+------------------------------------+       +------------------------------------+
|       BI DASHBOARDS & OLAP         |       |       OPERATIONAL ANALYTICS        |
|  - Executive Strategic KPIs        |       |  - Reverse ETL to CRM/ERP          |
|  - Exploratory Slicing/Dicing      |       |  - Automated Slack/Email Alerting  |
|  - Tabular Financial Reports       |       |  - Machine Learning Feeds          |
+------------------------------------+       +------------------------------------+
```

---

### 7. Minimal Working Example: OLTP vs. OLAP Simulation

Berikut adalah simulasi bagaimana skema transaksi normalisasi (OLTP) ditransformasikan menjadi skema analitik denormalisasi (OLAP) untuk mempermudah pemodelan data BI:

#### OLTP Normalization (3NF) - Sangat baik untuk penulisan transaksi tinggi:
```sql
-- DDL OLTP
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(100),
    region_id INT
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    order_timestamp TIMESTAMP,
    status VARCHAR(20)
);

CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT,
    product_id INT,
    quantity INT,
    unit_price DECIMAL(10, 2)
);
```

#### OLAP Dimensional Model (Star Schema) - Didesain untuk kueri BI berperforma tinggi:
```sql
-- DDL Dimensi (SCD Type 1/2)
CREATE TABLE dim_customer (
    customer_sk BIGINT PRIMARY KEY, -- Surrogate Key
    customer_id INT,                -- Natural/Business Key
    customer_name VARCHAR(100),
    customer_region VARCHAR(50),
    effective_date DATE,
    is_current BOOLEAN
);

CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,       -- Format: YYYYMMDD
    full_date DATE,
    day_of_week VARCHAR(10),
    calendar_month VARCHAR(10),
    calendar_quarter VARCHAR(2),
    calendar_year INT
);

-- DDL Fakta (Fact Table)
CREATE TABLE fct_order_sales (
    order_item_sk BIGINT PRIMARY KEY,
    date_key INT REFERENCES dim_date(date_key),
    customer_sk BIGINT REFERENCES dim_customer(customer_sk),
    product_id INT,
    order_id INT,
    quantity INT,
    unit_price DECIMAL(10, 2),
    gross_sales_amount DECIMAL(12, 2),
    created_at_utc TIMESTAMP
);
```

#### Logika Kueri BI (Analisis Performa Penjualan Kuartalan):
```sql
-- Kueri analitik cepat tanpa join kompleks multi-tabel 3NF
SELECT 
    d.calendar_year,
    d.calendar_quarter,
    c.customer_region,
    COUNT(DISTINCT f.order_id) AS total_orders,
    SUM(f.gross_sales_amount) AS total_revenue,
    AVG(f.gross_sales_amount) AS average_order_value
FROM fct_order_sales f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_customer c ON f.customer_sk = c.customer_sk
WHERE d.calendar_year = 2024
GROUP BY 1, 2, 3
ORDER BY 1, 2, total_revenue DESC;
```

---

### 8. Real-World Enterprise Scenario

**Konteks**: Platform E-commerce skala nasional memproses 500.000 pesanan per hari.
**Masalah**: Tim pemasaran dan tim finansial memiliki perbedaan pelaporan sebesar 14% pada metrik "Pendapatan Bulanan".
- Tim Finansial menarik data dari ERP (basis kas, memperhitungkan refund dan retur setelah pembayaran kliring).
- Tim Pemasaran mengagregasi data langsung dari basis data transaksional PostgreSQL melalui direct query pada Metabase (basis *gross transaction*, tanpa filter `status = 'COMPLETED'` dan mengabaikan status *refund*).
- Dampak: Beban kueri Metabase langsung ke *replica database* produksi mengakibatkan replikasi mengalami keterlambatan (*replication lag*) hingga 45 menit, mengganggu operasional inventaris gudang.

**Solusi Arsitektural**:
1. Menghentikan akses direct query visualizer ke *read-replica* operasional.
2. Membangun model ELT terpusat ke BigQuery/Snowflake menggunakan dbt.
3. Mendefinisikan kontrak semantik:
   - `Gross Merchandise Value (GMV)`: Total nilai transaksi yang di-generate pengguna (apapun status akhirnya).
   - `Net Revenue`: `GMV - Cancellations - Refunds - Merchant Payouts` (hanya untuk transaksi yang berstatus `Settled`).
4. Mendistribusikan kedua metrik tersebut melalui modul Semantic Layer terpadu.

---

### 9. Edge Cases, Failure Modes, and Defensive Strategies

| Failure Mode / Edge Case | Akar Masalah | Strategi Defensif (Defensive Mitigation) |
| :--- | :--- | :--- |
| **Schema Drift** | Perubahan tipe data/kolom baru di OLTP mendadak (misal: `order_id` berubah dari `INT` ke `UUID`). | Terapkan *Schema Evolution detection* pada ingestion engine dan bangun CI/CD pipeline yang menjalankan validasi *dry-run* skema sebelum transformasi dieksekusi. |
| **Late-Arriving Dimensions** | Transaksi penjualan tercatat di Fact Table sebelum data profil pengguna sinkron ke Dimension Table. | Gunakan teknik *Inferred Dimensions* (masukkan data dummy surrogate key `customer_sk = -1` dengan label "Unknown", update saat data profil tiba via incremental load). |
| **Duplicate Events (At-least-once Ingestion)** | Ingestion via queue (Kafka) melakukan pengiriman ganda akibat *network retry*. | Terapkan proses deduplikasi berbasis hash (misalnya: `MD5(order_id || product_id)`) menggunakan klausa `QUALIFY ROW_NUMBER() OVER(PARTITION BY hash_key ORDER BY updated_at DESC) = 1`. |
| **Timezone Inconsistency** | Server OLTP berada di GMT+7, API partner di UTC, visualisasi diakses pengguna di GMT+8. | Standardisasi seluruh layer Bronze, Silver, dan Gold secara ketat dalam **UTC**. Lakukan konversi zona waktu *hanya* pada lapisan presentasi akhir berdasarkan profil regional pengguna. |

---

### 10. Performance Considerations & Bottlenecks

1. **High Cardinality Dimension Slicing**:
   - *Bottleneck*: Menggunakan atribut dengan kardinalitas sangat tinggi (seperti `UUID`, nomor kartu, atau alamat email) sebagai filter atau *slice* pada visualisasi visual. Hal ini menghancurkan efisiensi indexing/caching columnar storage.
   - *Mitigasi*: Hindari memasukkan *high-cardinality non-analytical attributes* ke dalam memori BI tabular model; simpan atribut tersebut di layer *Cold Storage* atau hanya ambil saat kueri detail *drill-through* level transaksi individual.

2. **Fan Trap / Chasm Trap pada Skema Relasional Multi-Fact**:
   - *Bottleneck*: Melakukan kueri SQL yang menggabungkan dua tabel fakta dengan tingkat granularitas berbeda (misal: `fct_orders` dan `fct_order_line_items`) melalui dimensi umum, menghasilkan *Cartesian explosion* dan kalkulasi agregasi `SUM()` yang menggelembung.
   - *Mitigasi*: Jangan pernah menggabungkan dua tabel fakta secara langsung tanpa pra-agregasi ke tingkat granularitas yang setara (*conformed granularity*).

---

### 11. Trade-offs Analysis

| Pendekatan Arsitektur | Kelebihan | Kelemahan | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- |
| **Direct Query / Live Connection** | Data bersifat *near-real-time*; tidak memerlukan storage ganda di memory tool BI. | Kueri dashboards dibatasi performa database sumber; rawan *timeout* jika data masif; beban tinggi pada database. | Dashboard operasional teknis, audit keamanan, atau monitor log transaksi detik-ke-detik. |
| **In-Memory Caching / Import Mode** (e.g., Power BI VertiPaq, Tableau Hyper) | Performa kueri instan (<1 detik); agregasi masif dioptimalkan via memori terkompresi. | Kapasitas memori terbatas; ada latensi pembaruan data (*scheduled refresh interval*); memory footprint mahal. | Dasbor analitik eksekutif, exploratory analytics reguler, laporan performa bulanan/harian. |
| **Pre-aggregated Data Marts** | Agregasi SQL sangat cepat; menghemat biaya komputasi runtime di DWH. | Kehilangan fleksibilitas *drill-down* ke data level atomik; waktu pemrosesan batch ETL meningkat. | Sistem pelaporan finansial statutori yang metrik agregatnya bersifat statis dan baku. |

---

### 12. Architectural Evolution & Future-Proofing

```
Traditional BI (2000-2010)        Modern BI (2012-2022)             Next-Gen Composable BI (Now)
+-----------------------+         +-----------------------+         +----------------------------+
| - Monolithic On-Prem  |         | - Cloud DWH (Snowflake|         | - Lakehouse (Iceberg/Delta)|
|   (SSAS, Oracle)      |  ====>  |   / BigQuery)         |  ====>  | - Decoupled Semantic Layer |
| - Nightly Batch ETL   |         | - ELT Architecture    |         |   (MetricFlow, Cube.js)    |
| - Heavy Static Reports|         | - Self-service Data   |         | - Headless BI / GenAI BI   |
+-----------------------+         +-----------------------+         +----------------------------+
```

- **Headless BI / Standalone Semantic Layer**: Logika metrik tidak lagi terkunci (*vendor lock-in*) di dalam tool BI seperti Power BI (DAX) atau Tableau (Calculated Fields). Definisi metrik disimpan sebagai kode (*Metrics as Code*) berbasis Git menggunakan Cube.js, dbt Semantic Layer, atau LookML, sehingga dapat dikonsumsi secara serentak oleh Web App, Excel, LLM Agent, maupun Tool Visualisasi.
- **Table Formats Terbuka (Apache Iceberg / Delta Lake)**: Menggeser dominasi data warehouse berbayar tertutup menuju format berkas analitik terbuka dengan kapabilitas *ACID transactions* dan *Time Travel*.

---

### 13. Anti-Patterns to Avoid

1. **The "Spreadsheet Shadow-IT" Anti-Pattern**: Menggunakan file Excel/Google Sheets manual yang disimpan secara lokal di laptop staf analitis sebagai *lookup table* untuk melengkapi data warehouse produksi.
   - *Koreksi*: Bangun *Master Data Management* (MDM) terpusat atau simpan tabel referensi melalui model seed version-controlled (misalnya via `dbt seed`) yang masuk ke dalam audit git.
2. **Dashboard Factory Anti-Pattern**: Membangun ratusan dasbor ad-hoc untuk setiap permintaan tiket manajerial tanpa strategi konsolidasi, menyebabkan ribuan laporan terbengkalai (*abandoned dashboards*) yang mengonsumsi biaya pembaruan data (*refresh costs*).
   - *Koreksi*: Lakukan audit utilitas dasbor berkala; terapkan siklus hidup aset data (*deprecation policy*) untuk laporan yang tidak dibuka dalam jangka waktu 60 hari.
3. **Logic Duplication in Viz Layer**: Menulis logika kalkulasi margin kotor secara berbeda di 10 lembar visualisasi Power BI / Tableau alih-alih meletakkannya di layer SQL / Semantic Data Mart.
   - *Koreksi*: Dorong logika bisnis ke layer terendah yang memungkinkan (*push transformations down to the warehouse/semantic model*).

---

### 14. Security, Governance, and Compliance

- **Row-Level Security (RLS)**: Pembatasan akses baris data secara dinamis berdasarkan identitas pengguna (*User Principal Name* / peran IAM).
  ```sql
  -- Contoh Konseptual RLS Policy pada Cloud DWH
  CREATE ROW ACCESS POLICY region_filter ON dim_customer
  AS (customer_region VARCHAR) -> 
    CURRENT_USER() IN ('vp_asia@corp.com') AND customer_region = 'APAC'
    OR CURRENT_USER() IN ('global_exec@corp.com');
  ```
- **Column-Level Security (CLS) & Data Masking**: Kolom sensitif (Personally Identifiable Information - PII) seperti Nomor Induk Kependudukan (NIK), alamat, atau nomor kartu kredit harus dienkripsi atau disamarkan (*hashing/masking*) bagi peran analis umum:
  ```sql
  -- Dynamic Masking: Menampilkan hanya 4 digit terakhir kartu kredit
  MASKED WITH (FUNCTION = 'partial(0, "XXXX-XXXX-XXXX-", 4)')
  ```
- **Lineage Tracking**: Memastikan visualisasi dasbor memiliki metadata pelacakan (*data provenance*) hingga ke level source table untuk kepatuhan regulasi seperti GDPR atau UU Perlindungan Data Pribadi (UU PDP).

---

### 15. Observability, Monitoring, and Auditing

Pilar observabilitas data yang wajib dipantau oleh BI Analyst:
1. **Freshness (Kebaruan Data)**: Selang waktu antara event transaksi terjadi di OLTP dengan pembaruan terakhir di dashboard. Alerting diaktifkan jika keterlambatan (*staleness*) melebihi SLA bisnis (misalnya > 2 jam).
2. **Volume Anomaly**: Lonjakan atau penurunan drastis jumlah baris data yang dimuat ke dalam Fact table (misalnya jumlah pesanan harian tiba-tiba 0 atau 5x lipat akibat *infinite loop retry*).
3. **Distribution & Schema Invariants**: Uji konsistensi batasan logika data:
   - Persentase nilai `NULL` pada foreign key (harus 0%).
   - Nilai metrik non-negatif: `gross_sales_amount >= 0`.
4. **Execution Profiling**: Memantau waktu eksekusi dasbor; jika waktu rendering > 5 detik, aktifkan audit jejak query plan.

---

### 16. Production Readiness Checklist

| Kategori | Item Pemeriksaan | Status Verifikasi |
| :--- | :--- | :--- |
| **Data Quality** | Uji keunikan (*uniqueness*) dan non-null pada seluruh primary & surrogate keys telah lulus. | [ ] Diverifikasi |
| **Semantics** | Penamaan metrik seragam menggunakan standar industri (e.g., camelCase atau snake_case terstandarisasi). | [ ] Diverifikasi |
| **Performance** | Partisi data (*Partitioning*) dan pengelompokan (*Clustering*) di DWH telah disesuaikan dengan pola filter waktu. | [ ] Diverifikasi |
| **Governance** | RLS dan Data Masking untuk data PII telah diuji coba menggunakan berbagai profil pengguna non-admin. | [ ] Diverifikasi |
| **Auditability** | Dokumentasi kamus data (*Data Dictionary*) terisi lengkap dan terintegrasi ke Data Catalog. | [ ] Diverifikasi |
| **Cost Control** | Batasan komputasi (*Query limits / auto-suspend warehouse*) dikonfigurasi untuk mencegah runaway query. | [ ] Diverifikasi |

---

### 17. Industry Best Practices

1. **Adopt Kimball Dimensional Modeling with Modern Adaptations**: Walaupun komputasi DWH cloud sangat cepat, pemodelan star schema tetap menjadi standar emas dalam visualisasi data karena memaksimalkan efisiensi memori engine visual (seperti Power BI VertiPaq).
2. **Treat Data as a Product**: Setiap dataset atau dashboard yang diproduksi harus memiliki *product owner*, *Service Level Agreement* (SLA), target pengguna yang jelas, dan dokumentasi yang diperbarui.
3. **CI/CD for Semantic Layers**: Jangan pernah mengubah formula metrik langsung di server produksi. Gunakan version control (Git), pull request dengan code review, serta staging deployment pipeline.
4. **Decouple Storage and Compute**: Pastikan kueri analitik berat pada jam sibuk tidak berebut sumber daya komputasi dengan pipeline ELT terjadwal (pisahkan compute warehouse untuk *transformation engine* dan *reporting engine*).

---

### 18. Hands-on Lab: Enterprise Metric Normalization Challenge

#### Skenario:
Anda menerima data mentah tabel transaksi e-commerce kotor. Tugas Anda adalah membersihkan, menduplikasi, dan memodelkannya ke dalam star schema dasar, lalu menghitung indikator performa penjualan.

#### Langkah 1: Siapkan Dataset Mentah (Staging Area)
Jalankan skrip SQL berikut pada database engine Anda (PostgreSQL / SQLite / DuckDB):

```sql
CREATE TABLE stg_raw_orders (
    raw_transaction_id VARCHAR(50),
    customer_email VARCHAR(100),
    order_timestamp_str VARCHAR(50),
    product_category VARCHAR(50),
    amount_paid_raw VARCHAR(50),
    status VARCHAR(20)
);

INSERT INTO stg_raw_orders VALUES
('TRX-001', 'budi@domain.com', '2024-01-10 10:15:00', 'Electronics', '1500000', 'SUCCESS'),
('TRX-002', 'ani@domain.com', '2024-01-10 11:20:00', 'Fashion', '250000', 'SUCCESS'),
('TRX-003', 'budi@domain.com', '2024-01-11 09:05:00', 'Electronics', '500000', 'REFUNDED'),
('TRX-001', 'budi@domain.com', '2024-01-10 10:15:00', 'Electronics', '1500000', 'SUCCESS'), -- Duplikasi
('TRX-004', 'charlie@domain.com', '2024-01-12 14:00:00', 'Groceries', 'NULL', 'FAILED');
```

#### Langkah 2: Lakukan Transformasi dan Deduplikasi (Silver Modeling)
Tulis kueri transformasi untuk membuang duplikasi data, menyaring transaksi gagal, mengonversi tipe data secara defensif, dan membersihkan data:

```sql
WITH deduplicated_orders AS (
    SELECT 
        raw_transaction_id,
        customer_email,
        CAST(order_timestamp_str AS TIMESTAMP) AS order_timestamp,
        product_category,
        -- Penanganan nilai null atau string tidak valid
        CASE 
            WHEN amount_paid_raw = 'NULL' OR amount_paid_raw IS NULL THEN 0 
            ELSE CAST(amount_paid_raw AS DECIMAL(12,2)) 
        END AS amount_paid,
        status,
        ROW_NUMBER() OVER (
            PARTITION BY raw_transaction_id 
            ORDER BY order_timestamp_str DESC
        ) AS row_num
    FROM stg_raw_orders
)
SELECT 
    raw_transaction_id,
    customer_email,
    order_timestamp,
    product_category,
    amount_paid,
    status
FROM deduplicated_orders
WHERE row_num = 1 
  AND status IN ('SUCCESS', 'REFUNDED');
```

#### Langkah 3: Ekstraksi Metrik Analitik (Gold Metric Computation)
Hitung **Gross Merchandise Value (GMV)** dan **Net Realized Revenue**:
- *GMV*: Semua transaksi berstatus `SUCCESS` atau `REFUNDED`.
- *Net Revenue*: Hanya transaksi berstatus `SUCCESS` (transaksi `REFUNDED` harus dikeluarkan).

```sql
WITH clean_data AS (
    -- Gunakan logika dari Langkah 2
    SELECT 
        raw_transaction_id,
        product_category,
        CASE 
            WHEN amount_paid_raw = 'NULL' OR amount_paid_raw IS NULL THEN 0 
            ELSE CAST(amount_paid_raw AS DECIMAL(12,2)) 
        END AS amount_paid,
        status,
        ROW_NUMBER() OVER (
            PARTITION BY raw_transaction_id 
            ORDER BY order_timestamp_str DESC
        ) AS row_num
    FROM stg_raw_orders
)
SELECT 
    product_category,
    COUNT(raw_transaction_id) AS total_valid_transactions,
    SUM(amount_paid) AS gross_merchandise_value,
    SUM(CASE WHEN status = 'SUCCESS' THEN amount_paid ELSE 0 END) AS net_realized_revenue
FROM clean_data
WHERE row_num = 1 AND status != 'FAILED'
GROUP BY product_category;
```

#### Langkah 4: Verifikasi Hasil (Verification Step)
Pastikan output data Anda sesuai dengan kriteria kebenaran berikut:
- Kategori `Electronics` harus memiliki GMV = `2.000.000` (TRX-001 [1.500.000] + TRX-003 [500.000]), tetapi Net Realized Revenue = `1.500.000`.
- TRX-001 yang terduplikasi hanya boleh dihitung **satu kali**.
- Transaksi TRX-004 berkategori `Groceries` yang berstatus `FAILED` harus sepenuhnya dikeluarkan dari agregasi bisnis.

---

### 19. Key Takeaways & Summary
1. **Pemisahan OLTP dan OLAP adalah harga mati**: OLTP didesain untuk keandalan eksekusi transaksi per baris (atomisitas, konsistensi), sedangkan OLAP dioptimalkan untuk agregasi data analitik masif per kolom.
2. **Kekuatan BI Terletak pada Semantic Layer**: Dashboard visual hanyalah lapisan permukaan visual; nilai sesungguhnya dari Business Intelligence modern terletak pada standarisasi logika bisnis dan metrik yang terpusat, konsisten, dan teruji.
3. **Data Quality Shift-Left**: Memperbaiki anomali data di layer visualisasi (dashboard calculated fields) adalah tindakan reaktif yang memicu kesalahan berulang. Standardisasi, pembersihan, dan deduplikasi harus ditarik ke layer data pipeline (Silver/Gold layers) seawal mungkin.
4. **Metrik Harus Memiliki Definisi Matematis Tunggal**: BI Analyst profesional tidak sekadar membuat visualisasi, melainkan menyusun konsensus bisnis mengenai definisi operasional data demi menjaga integritas pengambilan keputusan enterprise.