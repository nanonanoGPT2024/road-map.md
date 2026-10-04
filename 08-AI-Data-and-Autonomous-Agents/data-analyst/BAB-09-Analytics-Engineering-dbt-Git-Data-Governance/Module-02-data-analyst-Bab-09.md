# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Topik:** Data Analyst / Analytics Engineering  
**Bab 09:** Analytics Engineering: dbt, Git, & Data Governance

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Pemodelan Data Lanjutan:** Mengonfigurasi materialisasi inkremental tingkat lanjut (*merge*, *delete+insert*, *microbatch*), strategi snapshot SCD (*Slowly Changing Dimension*) Tipe 2, dan *custom materialization* pada data warehouse modern (Snowflake/BigQuery/Databricks).
2. **Menerapkan Tata Kelola Data (*Data Governance*) Berbasis Kode:** Membangun *Data Contracts*, kontrol akses granular (*Role-Based Access Control* / RBAC), serta penyembunyian data sensitif (*Dynamic Data Masking*) langsung dari lapisan dbt.
3. **Membangun Pipeline CI/CD Data Otomatis (*Slim CI*):** Merancang alur kerja Git enterprise dengan orkestrator CI/CD untuk mengeksekusi pengujian otomatis, validasi kontrak skema, dan komparasi *state* (`state:modified+`) guna meminimalkan biaya komputasi warehouse.
4. **Mengintegrasikan Semantic Layer & Lineage Metadata:** Mempublikasikan metrik enterprise terstandarisasi menggunakan dbt Semantic Layer (MetricFlow) dan mengekstraksi DAG (*Directed Acyclic Graph*) untuk integrasi katalog data enterprise (OpenLineage/DataHub).
5. **Mengoptimalkan Performa & Efisiensi Biaya Warehouse:** Menganalisis *execution plan*, mengeliminasi *table scan* redundan via partisi/klasterisasi, serta menangani anomali *late-arriving facts*.

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
* **SQL Tingkat Lanjut:** Penguasaan mendalam *Window Functions*, CTE (*Common Table Expressions*), UDF (*User Defined Functions*), serta pemahaman logika *Query Execution Plan*.
* **Dasar dbt & Data Warehousing:** Memahami struktur proyek dbt standar (`dbt_project.yml`, *sources*, *staging*, *marts*), materialisasi *view* vs *table*, dan arsitektur *columnar storage* (BigQuery/Snowflake).
* **Git & Version Control:** Memahami alur kerja *feature branching*, *pull request review*, *merge conflicts resolution*, dan integrasi Git hooks.
* **Perangkat Lunak Terpasang:**
  * dbt Core `>= 1.7.0` (atau dbt Cloud CLI)
  * Adapter warehouse terkait (`dbt-snowflake`, `dbt-bigquery`, atau `dbt-databricks`)
  * Python `>= 3.10`
  * Git `>= 2.40`
  * Docker Engine `>= 24.0` (opsional untuk orkestrator lokal)

---

## 3. Concept & Internal Architecture

### 3.1. Arsitektur Kompilasi dan Eksekusi dbt Core
dbt bukan sebuah *execution engine* komputasi data independen. dbt berfungsi sebagai *compiler* dan *orchestration engine* metadata yang mengubah kode modular Jinja-SQL menjadi DDL/DML dialek SQL target, lalu mendorong komputasi tersebut secara *in-warehouse pushdown*.

```
   [ Jinja-SQL Models ] + [ YAML Metadata & Contracts ]
                           │
                           ▼
              ┌─────────────────────────┐
              │     dbt Compiler        │
              │  - Jinja Parsing        │
              │  - DAG Topology Sort    │
              │  - Contract Validation  │
              └────────────┬────────────┘
                           │
                           ▼
                  [ manifest.json ] (Target DAG Representation)
                           │
                           ▼
              ┌─────────────────────────┐
              │    Execution Engine     │
              │  - Thread Pool Manager  │
              │  - Connection Profiler  │
              └────────────┬────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Thread 1         Thread 2         Thread 3
    [ Worker ]       [ Worker ]       [ Worker ]
          │                │                │
          └────────────────┼────────────────┘
                           │ (Pushdown DDL/DML via JDBC/REST)
                           ▼
         ┌────────────────────────────────────┐
         │ Enterprise Cloud Data Warehouse   │
         │   (Snowflake / BigQuery / Spark)   │
         └────────────────────────────────────┘
```

#### Alur Kompilasi Internal:
1. **Parsing Phase:** dbt membaca seluruh file `.sql` dan `.yml`. dbt memetakan dependensi melalui fungsi `ref()` dan `source()`, kemudian membangun graf asiklik terarah (*Directed Acyclic Graph* / DAG) menggunakan algoritma Topological Sort.
2. **Contract & Schema Validation:** Sebelum DDL dikirim, dbt memvalidasi deklarasi tipe data kolom dalam kontrak model terhadap metadata *manifest*. Pelanggaran tipe data atau *missing columns* akan membatalkan kompilasi secara instan (*fail-fast*).
3. **Jinja Rendering:** dbt merender variabel lingkungan, makro kustom, dan logika kondisional menjadi SQL murni dialek target.
4. **Execution Phase:** dbt mendistribusikan node-node SQL yang independen ke dalam *thread pool worker* sesuai konfigurasi `threads` di `profiles.yml`.
5. **Artifact Generation:** Selesai eksekusi, dbt menghasilkan artefak mesin:
   * `manifest.json`: Representasi lengkap DAG, konfigurasi, dan kontrak.
   * `run_results.json`: Status eksekusi run-time, latensi eksekusi tiap node, dan output error warehouse.
   * `catalog.json`: Informasi skema fisik, ukuran tabel, dan jumlah partisi yang ditarik dari *information schema* data warehouse.

---

### 3.2. Mekanisme Internal Materialisasi Inkremental
Model inkremental dbt mengeliminasi kebutuhan memproses ulang (*full scan*) miliaran baris data historis. Terdapat 3 strategi utama pada level enterprise:

#### 1. Merge Strategy (Default pada Snowflake, BigQuery, Databricks)
Menggunakan klausa ANSI SQL `MERGE INTO`. dbt membentuk tabel sementara (*staging/temporary table*) berisi *delta dataset*, kemudian mengeksekusi operasi atomik:
* Jika nilai *unique key* cocok: Lakukan `UPDATE` pada kolom yang berubah.
* Jika nilai *unique key* tidak ditemukan: Lakukan `INSERT` baris baru.

#### 2. Delete + Insert Strategy
Digunakan ketika operasi `MERGE` terlalu mahal secara komputasi atau saat beroperasi pada arsitektur tertentu yang tidak mendukung atomic merge secara efisien. dbt menghapus partisi target yang terindikasi memiliki data baru berdasarkan klausa `unique_key`, kemudian menyisipkan rekaman baru.

#### 3. Microbatch Strategy (Fitur Lanjutan)
Membagi eksekusi inkremental menjadi sub-bagian waktu (*time-bucketed intervals*). Alih-alih mengeksekusi *delta* sebagai satu transaksi raksasa, dbt memecah eksekusi per jam atau per hari secara otomatis. Jika satu *microbatch* gagal, proses dapat diulang (*retry*) hanya untuk interval tersebut tanpa perlu *rollback* seluruh dataset.

---

### 3.3. Arsitektur Data Contracts & Penegakan Governance
Data Contract pada dbt mendefinisikan batas eksplisit (*hard boundary*) antara produsen data (*upstream engineers*) dan konsumen (*downstream analysts*).

```
                      DATA CONTRACT SPECIFICATION (YAML)
 ┌────────────────────────────────────────────────────────────────────────┐
 │ columns:                                                               │
 │   - name: transaction_id                                              │
 │     data_type: string                                                  │
 │     constraints:                                                       │
 │       - type: not_null                                                 │
 │       - type: primary_key                                              │
 │   - name: amount                                                       │
 │     data_type: numeric(18, 4)                                          │
 │ contract:                                                              │
 │   enforced: true                                                       │
 └────────────────────────────────────────────────────────────────────────┘
                                    │
                         dbt build Validation
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
      Schema Drift Detected                             Schema Valid
 (Koleksi tipe data mismatch                          (Model dikompilasi
   atau kolom hilang)                                 menjadi DDL warehouse)
           │                                                 │
           ▼                                                 ▼
     PIPELINE HALT                                    DDL Execution:
 (Build gagal, notifikasi CI,                       CREATE TABLE WITH
  mencegah rusaknya mart)                           CONSTRAINTS / ASSERTS
```

* **Build Phase Enforcement:** dbt memeriksa kecocokan skema SQL yang dihasilkan terhadap kontrak YAML. Ketidakcocokan memutus proses sebelum tabel target tersentuh.
* **Warehouse Native Constraint:** Pada warehouse yang mendukung (seperti Snowflake dan PostgreSQL), dbt secara otomatis menghasilkan *native constraints* (`NOT NULL`, `PRIMARY KEY`, `FOREIGN KEY`) ke dalam metadata catalog warehouse.

---

## 4. Why & What

| Dimensi | Pendekatan Legacy (Manual ELT / Stored Procedures) | Pendekatan Modern Analytics Engineering (dbt Enterprise) |
| :--- | :--- | :--- |
| **Paradigms** | Prosedural, skrip monolitik tidak berorientasi objek, *side-effect heavy*. | Deklaratif, berbasis DAG, modular, idempotent. |
| **State Management** | Diatur manual via tracking table custom; rentan *race conditions*. | Diatur otomatis via manifest state (`state:modified`), atomic merge. |
| **Testing & Quality** | Pengujian post-load manual atau skrip bash/cron ad-hoc. | Automated pre/post-load assertion, schema contracts, unit tests berbasis mock data. |
| **Lineage & Metadata** | Dokumentasi manual di spreadsheet, cepat usang (*obsolete*). | Auto-generated system DAG, integrasi runtime catalog, OpenLineage standar. |
| **Security & Privacy** | Script masking terpisah di luar alur pipeline; berisiko bocor saat staging. | Policy-as-Code: Masking logic dan RBAC terintegrasi dalam makro dbt. |
| **CI/CD Lifecycle** | Deploy langsung ke warehouse produksi (*cowboy engineering*). | Slim CI: Pengujian hanya pada model yang terisolasi dan terdampak oleh pull request. |

---

## 5. How (Workflow Detail)

Alur kerja enterprise produksi berpusat pada siklus hidup rilis perangkat lunak ketat (*GitOps for Data*):

```
1. Feature Branching (Local Dev)
   └─ Developer membuat branch: feat/add-fraud-metrics
   └─ Mengembangkan model inkremental & definisi contracts
   └─ Eksekusi dbt test & dbt run secara terisolasi di schema sandbox pribadi (dbt_jdoe)

2. Pull Request Submission
   └─ Developer mengajukan Pull Request ke branch `main`
   └─ Git Hook memicu CI Pipeline (GitHub Actions / GitLab CI)

3. Slim CI Automation
   └─ CI mengunduh manifest.json produksi terkini dari Object Storage (S3/GCS)
   └─ Menjalankan identifikasi node: dbt build --select state:modified+ --defer --state ./prod-manifest
   └─ CI menguji kontrak data, integrasi, dan eksekusi hanya untuk model yang berubah di schema PR sementara (pr_1234)

4. Merge & Production Deployment
   └─ PR di-merge ke `main` setelah seluruh checks passed dan minimal 1 Peer Approval
   └─ Orchestrator (Airflow / Dagster / dbt Cloud) mendeteksi commit baru
   └─ Orchestrator mengeksekusi model secara incremental di schema produksi
   └─ Manifest produksi baru diunggah ke Object Storage untuk siklus CI berikutnya
```

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Manufaktur Otomotif Modern
Bayangkan data mentah sebagai bijih logam dan Analytics Engineering sebagai lini perakitan pabrik mobil modular:
* **Staging Layer (Pembersihan Logam):** Bijih mentah dibersihkan dari kotoran dan distandarisasi ukurannya (casting).
* **Intermediate Layer (Perakitan Sub-Sistem):** Transmisi dan mesin dirakit secara terpisah. Suku cadang diverifikasi dengan *Data Contracts* (ukuran lubang baut harus presisi 10mm).
* **Marts Layer (Mobil Siap Pakai):** Komponen disatukan menjadi mobil utuh (SUV, Sedan) yang siap dikendarai konsumen (*Business Dashboard*).
* **Slim CI (Inspeksi Laser Lini Produksi):** Jika desain transmisi diubah, pabrik hanya menguji mesin dan sistem penggerak roda yang terhubung dengan transmisi tersebut, bukan merombak dan menguji ulang seluruh bodi dan interior mobil.

### Diagram Arsitektur Produksi End-to-End

```
+-------------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE DATA ARCHITECTURE                                       |
+-------------------------------------------------------------------------------------------------------+
                                                                                                         
  [ Ingestion Sources ]                                                                                  
  (Fivetran/Airbyte/Kafka)                                                                               
            │                                                                                            
            ▼                                                                                            
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ Data Warehouse: Raw Storage Layer (Append-Only)                                                  │  
  │   - raw_pos_transactions                                                                         │  
  │   - raw_customer_profiles                                                                        │  
  └──────────────────────────────────────────────────┬───────────────────────────────────────────────┘  
                                                     │                                                   
                                                     │ (dbt Pushdown Execution)                          
                                                     ▼                                                   
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ Staging Layer (View / Ephemeral)                                                                 │  
  │   - stg_pos__transactions.sql  --> Type casting, basic cleaning, deduping                        │  
  │   - stg_crm__customers.sql     --> Sanitasi email, standarisasi nomor telepon                    │  
  └──────────────────────────────────────────────────┬───────────────────────────────────────────────┘  
                                                     │                                                   
                                                     │ (ref)                                             
                                                     ▼                                                   
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ Intermediate Layer (Table / Incremental)                                                         │  
  │   - int_transactions_enriched.sql --> Join logs + profile, windowing, late-arriving handling    │  
  └──────────────────────────────────────────────────┬───────────────────────────────────────────────┘  
                                                     │                                                   
                                                     │ (ref)                                             
                                                     ▼                                                   
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐  
  │ Marts Layer (Incremental SCD-2 / Strict Contracts Enforced)                                      │  
  │   - fct_daily_customer_revenue.sql [MERGE Incremental + Cluster by Date]                         │  
  │   - dim_customers.sql             [SCD Type 2 Snapshot]                                          │  
  └──────────────────────────┬───────────────────────────────────────────────┬───────────────────────┘  
                             │                                               │                          
                             ▼                                               ▼                          
  ┌───────────────────────────────────────────────┐ ┌────────────────────────────────────────────────┐  
  │ Semantic Layer (MetricFlow)                   │ │ Governance & Security Policy                   │  
  │   - metric: gross_revenue                     │ │   - Macro Dynamic Data Masking (PII: NIK/Email)│  
  │   - dimension: customer_segment               │ │   - OpenLineage Event Producer                 │  
  └──────────────────────────┬────────────────────┘ └────────────────────────────────────────────────┘  
                             │                                                                          
                             ▼                                                                          
                 [ Consumption Interfaces ]                                                             
     (Tableau, Looker, Hex, Reverse-ETL / Census)                                                       
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Model Inkremental Dasar
Model berikut menggunakan strategi *append/merge* sederhana untuk menyaring data yang baru masuk berdasarkan kolom modifikasi waktu.

```sql
-- models/staging/stg_sales__orders.sql
{{
    config(
        materialized='incremental',
        unique_key='order_id'
    )
}}

SELECT
    order_id,
    customer_id,
    order_status,
    order_amount,
    updated_at
FROM {{ source('raw_store', 'orders') }}

{% if is_incremental() %}
    -- Filter hanya dijalankan ketika tabel sudah terbentuk di warehouse
    WHERE updated_at >= (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

---

### 7.2. Practical Example (Production Grade Enterprise)

Berikut adalah implementasi model transaksi keuangan tingkat produksi dengan kriteria:
1. **Contract Enforcement:** Schema dikunci ketat; perbedaan tipe data memicu *compilation failure*.
2. **Dynamic Data Masking Macro:** Sensor otomatis pada data PII berdasarkan *warehouse role*.
3. **Optimized Incremental Strategy:** Menggunakan *merge strategy* dengan clustering dan *lookback window* untuk menangani *late-arriving events*.

#### Step 1: Makro Masking Berdasarkan Role (`macros/apply_pii_mask.sql`)
```sql
{% macro apply_pii_mask(column_name, role_allowed='FINANCE_ADMIN') %}
    CASE
        -- Snowflake context function
        WHEN CURRENT_ROLE() = '{{ role_allowed }}' THEN {{ column_name }}
        ELSE SHA2(CONCAT({{ column_name }}, 'SALT_KEY_PRODUCTION_98231'), 256)
    END
{% endmacro %}
```

#### Step 2: Deklarasi Schema & Kontrak Model (`models/marts/finance/fct_financial_transactions.yml`)
```yaml
version: 2

models:
  - name: fct_financial_transactions
    description: "Tabel fakta transaksi keuangan terenkripsi dengan penegakan data contracts ketat."
    config:
      contract:
        enforced: true
    columns:
      - name: transaction_id
        data_type: string
        description: "Primary key unik transaksi"
        constraints:
          - type: not_null
          - type: primary_key
      - name: customer_id
        data_type: string
        constraints:
          - type: not_null
      - name: customer_bank_account
        data_type: string
        description: "PII sensitif yang dimaskir dinamis via macro"
        constraints:
          - type: not_null
      - name: transaction_amount
        data_type: numeric(18, 4)
        constraints:
          - type: not_null
      - name: transaction_status
        data_type: string
        constraints:
          - type: not_null
      - name: transaction_timestamp
        data_type: timestamp_ntz
        constraints:
          - type: not_null
      - name: ingestion_timestamp
        data_type: timestamp_ntz
        constraints:
          - type: not_null
```

#### Step 3: Logika SQL Produksi (`models/marts/finance/fct_financial_transactions.sql`)
```sql
{{
    config(
        materialized='incremental',
        unique_key='transaction_id',
        incremental_strategy='merge',
        cluster_by=['transaction_timestamp::DATE', 'transaction_status'],
        on_schema_change='fail'
    )
}}

WITH source_transactions AS (
    SELECT * 
    FROM {{ ref('stg_pos__transactions') }}
),

sanitized_transactions AS (
    SELECT
        transaction_id,
        customer_id,
        {{ apply_pii_mask('customer_bank_account', role_allowed='FINANCE_ADMIN') }} AS customer_bank_account,
        CAST(transaction_amount AS NUMERIC(18, 4)) AS transaction_amount,
        UPPER(transaction_status) AS transaction_status,
        CAST(transaction_timestamp AS TIMESTAMP_NTZ) AS transaction_timestamp,
        CURRENT_TIMESTAMP() AS ingestion_timestamp
    FROM source_transactions
)

SELECT * FROM sanitized_transactions

{% if is_incremental() %}
    -- Window lookback 3 hari untuk mitigasi late-arriving events / replikasi tertunda
    WHERE transaction_timestamp >= (
        SELECT DATEADD(day, -3, MAX(transaction_timestamp)) 
        FROM {{ this }}
    )
{% endif %}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Skalabilitas Data Platform FinTech Unicorn "PayFast"
* **Konteks:** PayFast memproses 60 juta transaksi per hari di 4 negara Asia Tenggara.
* **Problem:**
  1. Pipeline dbt harian membutuhkan waktu **2 jam 45 menit** menggunakan model full refresh/view.
  2. Biaya Snowflake melonjak 300% ($45.000/bulan) akibat *full table scan* berulang.
  3. Insiden produksi: Tim backend mengubah tipe data `transaction_amount` dari `FLOAT` menjadi `STRING` (dengan format mata uang lokal), merusak 14 dashboard eksekutif dan *reverse-ETL* ke sistem anti-fraud.
* **Solusi Arsitektural:**
  1. **Migrasi ke Incremental Merge + Dynamic Partitioning:** Mengubah seluruh model *marts* menjadi tabel inkremental berpartisi dengan klausa clustering berdasarkan `country_code` dan `transaction_date`. Mengaktifkan *lookback window* 48 jam untuk rekonsiliasi data perbankan yang tertunda.
  2. **Implementasi Data Contracts (dbt 1.5+):** Mengonfigurasi `contract: {enforced: true}` pada seluruh model staging dan marts tingkat finansial. Perubahan tipe data upstream secara otomatis memutus CI branch backend sebelum memengaruhi dbt.
  3. **Slim CI Implementation:** Mengintegrasikan GitHub Actions dengan artefak S3 manifest produksi. Pipeline CI PR dbt berkurang dari 40 menit menjadi **3 menit 15 detik** karena hanya mengompilasi dan menguji model yang terdampak langsung.
* **Hasil:**
  * Waktu eksekusi pipeline dbt harian berkurang menjadi **18 menit** (penurunan waktu komputasi **89%**).
  * Penghematan biaya Snowflake mencapai **$28.000 per bulan**.
  * *Zero incident* kerusakan skema hilir (*downstream schema breakage*) selama 12 bulan berturut-turut.

---

## 9. Trade-offs

Setiap keputusan perancangan arsitektur analitik membawa konsekuensi struktural:

```
                       STRATEGI MATERIALISASI DBT
                                    ▲
                                    │
                               Performa Query
                                Konsumsi Tinggi
                                    │
                [Table]             │          [Incremental]
                   │                │                ▲
                   │                │               ╱ 
                   │                │              ╱ Biaya Compute Rendah
    Biaya Compute  │                │             ╱  Operasional Kompleks
    Tinggi         │                │            ╱   
                   ▼                │           ╱    
            ───────┼────────────────┼──────────┼──────────────►
                   │                │          Kompleksitas
                   │                │          Engineering
                   │    [View]      │          Tinggi
                   │       ▲        │
                   │       │        │
                   ▼       │        │
                     Latensi Kueri  │
                        Lambat      │
```

### 1. View vs Incremental
* **View:**
  * *Pros:* Nol biaya penyimpanan (*storage cost*), data selalu *real-time* merefleksikan sumber.
  * *Cons:* Kueri analitik berat pada ribuan pengguna akan membebani warehouse (*compute explosion*).
  * *Trade-off:* Gunakan View hanya pada Staging Layer; gunakan Incremental pada Marts.

### 2. Full Refresh vs Incremental
* **Full Refresh (`materialized='table'`):**
  * *Pros:* Deterministik absolut, tidak rentan terhadap anomali duplikasi data atau rekonsiliasi state historis.
  * *Cons:* Biaya komputasi eksponensial seiring bertambahnya volume data.
  * *Trade-off:* Full refresh cocok untuk tabel dimensi kecil (< 5 juta baris); Incremental wajib untuk tabel fakta besar.

### 3. Strict Data Contracts vs Developer Velocity
* **Strict Contracts (`enforced: true`):**
  * *Pros:* Proteksi skema mutlak bagi sistem hilir (BI/ML).
  * *Cons:* Menghambat kecepatan perombakan fitur; setiap perubahan kolom memerlukan migrasi YAML terencana dan negosiasi lintas tim.

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Penanganan *Late-Arriving Facts* yang Naif
* **Masalah:** Menggunakan filter inkremental absolut `WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})`. Jika data transaksi tanggal 10 baru masuk ke sistem pada tanggal 12, data tanggal 10 tersebut akan diabaikan selamanya karena pointer `MAX(created_at)` sudah berada di tanggal 12.
* **Troubleshooting & Fix:** Selalu implementasikan *sliding lookback window*:
  ```sql
  WHERE created_at >= (SELECT DATEADD('day', -7, MAX(created_at)) FROM {{ this }})
  ```

### Mistake 2: Non-Deterministic `unique_key` pada Incremental Merge
* **Masalah:** Operasi `MERGE` di Snowflake/BigQuery gagal dengan error runtime: `MERGE statement matched a single row from the target table with multiple rows of the source table`.
* **Troubleshooting & Fix:** Penyebabnya adalah *dataset staging* mengandung duplikasi nilai *primary key*. Sisipkan langkah deduplikasi eksplisit menggunakan `QUALIFY ROW_NUMBER() OVER (PARTITION BY unique_id ORDER BY updated_at DESC) = 1` sebelum menjalankan sintaks penggabungan akhir.

### Mistake 3: State Comparison Failure pada Slim CI
* **Masalah:** CI gagal mendeteksi perubahan model dengan error: `The state selector requires a path to a valid manifest.json`.
* **Troubleshooting & Fix:** Pastikan pipeline CI mengekstrak `manifest.json` dari branch produksi utama, bukan branch saat ini. Parameter CLI dbt harus memuat path defer:
  ```bash
  dbt build --select state:modified+ --defer --state ./path_to_prod_manifest/
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum meloloskan model dbt ke lingkungan produksi:

- [ ] **Contract Defined:** Seluruh model fakta memiliki deklarasi `contract: {enforced: true}` lengkap dengan tipe data kolom eksplisit.
- [ ] **Deterministic Primary Key:** Model mendefinisikan *primary key* tunggal atau komposit yang diuji dengan pengujian `unique` dan `not_null`.
- [ ] **Clustering/Partitioning:** Model inkremental berukuran > 10 GB mendefinisikan strategi partisi tanggal dan klasterisasi kunci filter kueri.
- [ ] **Idempotency Validated:** Eksekusi `dbt run` dua kali berturut-turut menghasilkan jumlah baris dan status data yang identik tanpa duplikasi.
- [ ] **Lookback Window Configured:** Klausa inkremental memperhitungkan *late-arriving records* dengan jendela *lookback* minimal 3-7 hari.
- [ ] **PII Masking Activated:** Kolom berisi data sensitif (*personally identifiable information*) dilindungi oleh makro *role-based dynamic masking*.
- [ ] **Zero Hardcoded Names:** Tidak ada nama database atau skema yang di-*hardcode* di dalam skrip SQL; wajib menggunakan referensi `{{ ref() }}` atau `{{ source() }}`.
- [ ] **Unit Tests Written:** Model dengan logika matematika/kondisional kompleks memiliki file unit test YAML dengan *mock inputs* dan *expected outputs*.
- [ ] **CI Slim Verified:** Skrip CI memvalidasi hanya model yang dimodifikasi (`state:modified+`) untuk efisiensi komputasi.
- [ ] **Documentation & Lineage:** Semua kolom penting memiliki dokumentasi fungsional di YAML untuk rendering katalog otomatis.

---

## 12. Hands-on Practice

Struktur direktori praktikum ini wajib diatur dalam path: `hands-on/m02/`

```
hands-on/m02/
├── .github/
│   └── workflows/
│       └── slim_ci.yml
├── analyses/
├── macros/
│   └── generate_schema_name.sql
│   └── mask_pii.sql
├── models/
│   ├── staging/
│   │   ├── src_ecommerce.yml
│   │   ├── stg_orders.sql
│   │   └── stg_orders.yml
│   └── marts/
│       ├── fct_orders_incremental.sql
│       └── fct_orders_incremental.yml
├── tests/
│   └── assert_positive_revenue.sql
├── dbt_project.yml
└── profiles.yml.example
```

### Langkah 1: Inisialisasi Konfigurasi Proyek (`dbt_project.yml`)
Simpan file ini di `hands-on/m02/dbt_project.yml`:
```yaml
name: 'enterprise_analytics_m02'
version: '1.0.0'
config-version: 2

profile: 'production_warehouse'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
macro-paths: ["macros"]

models:
  enterprise_analytics_m02:
    staging:
      +materialized: view
    marts:
      +materialized: incremental
```

### Langkah 2: Konfigurasi Source & Data Contracts
Simpan file ini di `hands-on/m02/models/staging/src_ecommerce.yml`:
```yaml
version: 2

sources:
  - name: ecommerce_raw
    database: RAW_DATA
    schema: PUBLIC
    tables:
      - name: raw_orders
        columns:
          - name: id
            data_type: string
          - name: user_id
            data_type: string
          - name: gross_amount
            data_type: numeric(18, 4)
          - name: updated_at
            data_type: timestamp_ntz
```

Simpan file model staging di `hands-on/m02/models/staging/stg_orders.sql`:
```sql
SELECT
    id AS order_id,
    user_id,
    CAST(gross_amount AS NUMERIC(18, 4)) AS gross_amount,
    CAST(updated_at AS TIMESTAMP_NTZ) AS updated_at
FROM {{ source('ecommerce_raw', 'raw_orders') }}
```

### Langkah 3: Model Inkremental Marts dengan Testing
Simpan file spesifikasi kontrak di `hands-on/m02/models/marts/fct_orders_incremental.yml`:
```yaml
version: 2

models:
  - name: fct_orders_incremental
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: string
        constraints:
          - type: not_null
          - type: primary_key
      - name: user_id
        data_type: string
        constraints:
          - type: not_null
      - name: gross_amount
        data_type: numeric(18, 4)
      - name: updated_at
        data_type: timestamp_ntz
```

Simpan logika model di `hands-on/m02/models/marts/fct_orders_incremental.sql`:
```sql
{{
    config(
        materialized='incremental',
        unique_key='order_id',
        incremental_strategy='merge',
        on_schema_change='fail'
    )
}}

WITH base_orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
)

SELECT
    order_id,
    user_id,
    gross_amount,
    updated_at
FROM base_orders

{% if is_incremental() %}
    WHERE updated_at >= (
        SELECT DATEADD(day, -3, MAX(updated_at)) 
        FROM {{ this }}
    )
{% endif %}
```

### Langkah 4: Custom Singular Data Test
Simpan file ini di `hands-on/m02/tests/assert_positive_revenue.sql`:
```sql
-- Pengujian custom: Mengembalikan record yang melanggar batasan bisnis
SELECT
    order_id,
    gross_amount
FROM {{ ref('fct_orders_incremental') }}
WHERE gross_amount < 0
```

### Langkah 5: Skrip GitHub Actions Slim CI (`.github/workflows/slim_ci.yml`)
```yaml
name: dbt-slim-ci

on:
  pull_request:
    branches: [ "main" ]

jobs:
  slim-ci-run:
    runs-on: ubuntu-latest
    env:
      DBT_PROFILES_DIR: ./
      SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
      SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
      SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
      SNOWFLAKE_ROLE: ${{ secrets.SNOWFLAKE_ROLE }}
      SNOWFLAKE_WAREHOUSE: ${{ secrets.SNOWFLAKE_WAREHOUSE }}
      SNOWFLAKE_DATABASE: ${{ secrets.SNOWFLAKE_DATABASE }}
      SNOWFLAKE_SCHEMA: "PR_CI_${{ github.event.pull_request.number }}"

    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dbt
        run: pip install dbt-snowflake

      - name: Download Production Manifest Artifact
        run: |
          mkdir -p ./prod-state
          # Asumsi penarikan manifest dari AWS S3 storage
          # aws s3 cp s3://company-dbt-metadata/production/manifest.json ./prod-state/manifest.json
          # Dummy manifest copy untuk simulasi:
          touch ./prod-state/manifest.json

      - name: Execute Slim CI Build & Deferral
        run: |
          dbt deps
          dbt build \
            --select state:modified+ \
            --defer \
            --state ./prod-state \
            --target ci
```

---

## 13. Exercise

### Level Easy
Konfigurasikan model Snapshot dbt SCD Tipe 2 untuk melacak perubahan status pesanan pada tabel `stg_orders`. 
* Gunakan strategi `timestamp`.
* Tetapkan `updated_at` sebagai target validasi perubahan.
* Simpan di file `snapshots/orders_snapshot.sql`.

### Level Medium
Buat sebuah makro Jinja kustom bernama `custom_deduplicate(relation, partition_by, order_by)` yang menghasilkan subquery ANSI SQL untuk menyaring baris duplikat secara dinamis menggunakan *window function* `ROW_NUMBER()`. Terapkan makro ini ke dalam model inkremental untuk mencegah error *unique key collision*.

### Level Hard
Rancang model agregasi inkremental matriks keuangan harian `fct_customer_daily_spend` dari tabel mentah berukuran multi-gigabyte. Model harus:
1. Memiliki kontrak ketat (*data contract*).
2. Menggunakan strategi *delete+insert* pada partisi tanggal (`date_day`).
3. Menangani kasus transaksi mundur (*retroactive adjustments*) hingga 14 hari ke belakang secara otomatis tanpa *full rebuild*.

---

## 14. Challenge

### Studi Kasus: Konsolidasi Arsitektur Multi-Tenant Analytics (Zero-Trust Isolation)
Sebuah perusahaan logistik SaaS global beroperasi di bawah mandat kepatuhan GDPR dan POJK. Mereka memiliki 100 tenant perusahaan besar yang menggunakan skema database analitik bersama (*multi-tenant warehouse*).

**Tantangan Sistemik:**
1. Anda dituntut merancang arsitektur dbt yang memungkinkan setiap model marts dieksekusi secara terisolasi per tenant. Metrik tenant A **sama sekali tidak boleh** bocor ke tenant B secara runtime.
2. Tim keamanan mewajibkan bahwa data finansial tenant yang dikonsumsi oleh data scientist dienkripsi menggunakan kunci enkripsi khusus per tenant (*tenant-specific hashing salt*) yang disimpan di secure secrets vault.
3. Seluruh dependensi lineage tabel hingga level kolom (*column-level lineage*) harus diekspor secara real-time ke format metadata OpenLineage setiap kali CI/CD mengeksekusi pipeline produksi.

**Ekspektasi Output Arsitektur:**
* Rancang struktur folder dbt, strategi makro abstraksi skema dinamis (`generate_schema_name`), dan rancangan alur kerja CI/CD untuk orkestrasi 100 tenant ini secara efisien tanpa membuat proyek terfragmentasi menjadi 100 repo yang berbeda.
* Berikan dokumen arsitektur komprehensif, implementasi makro Jinja utama, konfigurasi dbt YAML, dan analisis estimasi overhead komputasi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama artefak `manifest.json` yang dihasilkan saat kompilasi dbt?
   * A. Menyimpan log koneksi driver JDBC ke warehouse.
   * B. Menyediakan representasi representasional struktural lengkap dari graf dependensi (DAG) dan konfigurasi model.
   * C. Menyimpan cache data tabel agar komputasi lokal dapat berjalan tanpa warehouse.
   * D. Menampung data pengguna yang mengakses dashboard analitik.
   * *Jawaban yang Benar:* **B** — `manifest.json` adalah cetak biru teknis dbt yang memuat representasi DAG, properti node, dan kontrak skema.

2. Pada model inkremental dbt, ekspresi blok `{% if is_incremental() %}` akan bernilai TRUE jika:
   * A. Database target adalah tipe OLAP columnar warehouse.
   * B. Perintah `dbt run --full-refresh` sedang dijalankan.
   * C. Tabel target sudah ada di warehouse dan bendera `--full-refresh` tidak digunakan.
   * D. Model tersebut memiliki dependency minimal dua model staging upstream.
   * *Jawaban yang Benar:* **C** — Makro `is_incremental()` hanya merender blok SQL jika tabel relasi fisik sudah ada di database dan proses eksekusi tidak memaksakan *full refresh*.

3. Apa efek samping dari mengonfigurasi `contract: {enforced: true}` pada model dbt jika query SQL menghasilkan kolom yang tidak didefinisikan di YAML?
   * A. Kolom tersebut diabaikan secara diam-diam dan query tetap sukses.
   * B. dbt membatalkan kompilasi secara instan (*compilation error*) sebelum menyentuh warehouse.
   * C. Warehouse akan membuat kolom baru tersebut secara otomatis dengan tipe data VARCHAR.
   * D. Model diubah materialisasinya menjadi view secara otomatis.
   * *Jawaban yang Benar:* **B** — Deklarasi kontrak yang diaktifkan (*enforced*) mengharuskan kecocokan mutlak antara kolom deklarasi YAML dan ekspresi SELECT pada model SQL.

4. Strategi materialisasi dbt mana yang paling optimal untuk dataset transaksi ratusan juta baris yang terus bertambah setiap hari?
   * A. Materialisasi `view`.
   * B. Materialisasi `ephemeral`.
   * C. Materialisasi `table`.
   * D. Materialisasi `incremental`.
   * *Jawaban yang Benar:* **D** — Materialisasi inkremental hanya memproses rekaman delta baru, meminimalkan waktu dan biaya komputasi query.

5. Manakah perintah CLI dbt yang benar untuk mengeksekusi pengujian hanya pada model yang mengalami perubahan kode dan seluruh model turunannya?
   * A. `dbt test --select modified`
   * B. `dbt build --select state:modified+ --state <path-to-manifest>`
   * C. `dbt run --models changed:*`
   * D. `dbt execute --select *`
   * *Jawaban yang Benar:* **B** — Sintaks `state:modified+` memanfaatkan pembandingan manifes terhadap status sebelumnya dan tanda `+` memastikan semua node hilir terdampak turut diproses.

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. Mengapa penggunaan filter `WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})` dapat menimbulkan data anomaly (*silent data loss*)?
   * A. Karena fungsi `MAX()` mengunci tabel warehouse secara permanen.
   * B. Karena rekaman transaksi yang terlambat masuk (*late-arriving facts*) dengan timestamp lampau akan terabaikan oleh filter batas atas.
   * C. Karena dbt tidak dapat mengevaluasi fungsi SQL agregat di dalam blok `is_incremental()`.
   * D. Karena tabel target akan terhapus otomatis akibat *deadlock*.
   * *Jawaban yang Benar:* **B** — Jika transaksi lampau tertunda masuk ke staging akibat latensi replikasi, kueri yang mengandalkan MAX() statis murni akan mengabaikan data tersebut secara permanen.

7. Apa tujuan arsitektural dari penggunaan parameter `--defer` pada alur kerja Slim CI?
   * A. Menunda eksekusi CI hingga jam sepi komputasi warehouse.
   * B. Memungkinkan model yang tidak dimodifikasi dalam PR merujuk pada tabel/skema lingkungan produksi alih-alih membangun ulang tabel tersebut di skema staging CI.
   * C. Menunda pengecekan data contract hingga model mencapai tahap deployment final.
   * D. Menginstruksikan Git untuk menahan commit sebelum review selesai.
   * *Jawaban yang Benar:* **B** — `--defer` menyelesaikan ketergantungan model upstream yang tidak dimodifikasi dengan mengarahkan kuerinya ke tabel produksi yang sudah ada, menghemat 90%+ biaya CI.

8. Dalam konfigurasi snapshot SCD Tipe 2 dbt, kolom teknis mana yang secara otomatis dibuat oleh dbt untuk mencatat histori versi rekaman?
   * A. `dbt_row_id`, `dbt_hash_diff`, `dbt_created_by`.
   * B. `dbt_scd_id`, `dbt_updated_at`, `dbt_valid_from`, `dbt_valid_to`.
   * C. `history_id`, `start_date`, `end_date`, `is_active`.
   * D. `record_id`, `system_timestamp`, `status`.
   * *Jawaban yang Benar:* **B** — dbt Core secara bawaan menginjeksikan kolom pelacak metadata waktu: `dbt_scd_id`, `dbt_updated_at`, `dbt_valid_from`, dan `dbt_valid_to`.

9. Apa perbedaan esensial antara Generic Tests dan Singular Tests pada dbt?
   * A. Generic tests ditulis dalam sintaks Python, sedangkan Singular tests ditulis dalam Bash script.
   * B. Generic tests didefinisikan dalam blok YAML berbasis makro parameter (`unique`, `not_null`), sedangkan Singular tests ditulis sebagai kueri SQL mandiri di direktori `tests/`.
   * C. Singular tests hanya dapat berjalan di schema produksi lokal.
   * D. Generic tests tidak memvalidasi data warehouse fisik.
   * *Jawaban yang Benar:* **B** — Generic tests adalah asersi reusable yang dikonfigurasi via YAML, sedangkan Singular tests adalah file `.sql` independen yang mencari pelanggaran batasan bisnis.

10. Jika tim data engineer menerapkan `on_schema_change='fail'` pada konfigurasi incremental model dbt, apa yang terjadi saat kolom baru ditambahkan pada upstream model?
    * A. dbt secara otomatis menjalankan DDL `ALTER TABLE ADD COLUMN` pada warehouse.
    * B. Kolom baru tersebut diabaikan tanpa peringatan.
    * C. Eksekusi dbt run akan langsung melempar error dan proses dihentikan sebelum manipulasi data dijalankan.
    * D. Seluruh isi tabel warehouse dihapus dan diubah menjadi *ephemeral*.
    * *Jawaban yang Benar:* **C** — Nilai `fail` memproteksi tabel target dari mutasi skema tak terduga dengan memutus eksekusi bila skema sumber dan skema target tidak identik.

---

### Bagian 3: Skenario Kasus Produksi Enterprise (Analisis Kasus)

#### Skenario 1: Ledakan Waktu CI Pipeline
Sebuah tim analitik mengeluhkan waktu eksekusi Pull Request CI mereka melonjak dari 5 menit menjadi 58 menit setelah menambahkan 50 model analitik baru. Pemeriksaan log menunjukkan CI mengeksekusi `dbt run && dbt test` secara menyeluruh pada skema pengujian sementara untuk seluruh proyek.
* **Pertanyaan Kasus:** Jelaskan langkah konfigurasi arsitektur dbt dan CI pipeline secara terperinci untuk mereduksi waktu eksekusi kembali ke batas < 5 menit tanpa mengorbankan integritas data pengujian!
* **Analisis Solusi:**
  1. Wajib beralih menggunakan pola **Slim CI** menggunakan flag `dbt build --select state:modified+ --defer --state ./prod_artifacts/`.
  2. Langkah orkestrator CI harus mengunduh file `manifest.json` hasil build terakhir dari branch `main` (misal dari bucket S3 atau dbt Cloud Metadata API).
  3. Mengaktifkan eksekusi multi-threading dbt (`--threads 8` atau lebih) disesuaikan dengan kapasitas *virtual warehouse* CI.
  4. Menerapkan isolasi skema dinamis berbasis *PR number* (misal `ci_pr_102`) yang secara otomatis didrop setelah PR di-merge atau di-close via GitHub Action lifecyle.

#### Skenario 2: Anomali Duplikasi Baris pada Model Finansial
Tabel `fct_monthly_subscription_billing` dilaporkan oleh tim Finance memiliki kelebihan pelaporan nominal sebesar 15% pada laporan akhir bulan. Model tersebut berstatus `incremental` dengan `incremental_strategy='merge'` dan `unique_key=['subscription_id', 'billing_month']`.
* **Pertanyaan Kasus:** Mengapa duplikasi atau penggelembungan angka ini tetap dapat terjadi pada strategi `merge` dan bagaimana perbaikan permanennya?
* **Analisis Solusi:**
  1. Penyebab utama: Dataset staging upstream menghasilkan data ganda (*duplicate primary key candidates*) pada batch ingestasi yang sama akibat pengiriman ulang API (*retry events* tanpa idempotency). Warehouse engine yang mengeksekusi `MERGE` terhadap relasi sumber non-deterministik akan mengupdate baris berulang kali atau menghasilkan duplikasi tak terduga tergantung dialek warehouse.
  2. Perbaikan: Sebelum melakukan konsumsi di model inkremental, model staging harus membersihkan data dengan klausa deterministik:
     ```sql
     QUALIFY ROW_NUMBER() OVER (
         PARTITION BY subscription_id, billing_month 
         ORDER BY event_timestamp DESC
     ) = 1
     ```
  3. Menambahkan asersi pengujian generic dbt `unique` pada kunci komposit tersebut menggunakan paket `dbt-utils` (`dbt_utils.unique_combination_of_columns`).

#### Skenario 3: Pelanggaran Privasi Data (PII Leakage)
Auditor eksternal menemukan bahwa data nomor kartu debit dan NIK pelanggan tersimpan dalam bentuk *plaintext* pada tabel intermediate analitik (`int_payment_settlements`), dan dapat diakses oleh analis junior tanpa izin.
* **Pertanyaan Kasus:** Bagaimana Anda mendesain solusi *Zero-Trust Data Protection* langsung di lapisan dbt tanpa mematikan workflow analis analitik?
* **Analisis Solusi:**
  1. Menerapkan **Role-Based Dynamic Masking** di dbt via Makro Jinja. Makro ini memeriksa `CURRENT_ROLE()` database; jika bukan `SECURITY_ADMIN` atau `FINANCE_DIR`, kolom otomatis di-hash menggunakan algoritma SHA-256 dengan *production salt*.
  2. Memanfaatkan fitur *dbt Grants*: Deklarasikan hak akses `select` secara granular hanya kepada *functional roles* di tingkat YAML konfigurasi model.
  3. Mengonfigurasi audit log CI dbt yang memvalidasi bahwa tidak ada kueri SQL di staging atau marts yang meng-unmask kolom sensitif secara sengaja tanpa pemanggilan makro enkripsi resmi.

---

## 16. Summary

Modul ini telah mengupas secara mendalam implementasi lanjutan Analytics Engineering pada standar enterprise:
1. **Model Materialization Mechanics:** Memahami internal dbt compiler, thread pool allocation, dan perbedaan komputasi antara materialisasi *view*, *table*, dan *incremental* (`merge`, `delete+insert`).
2. **Quality & Governance by Code:** Penerapan *Data Contracts* tingkat lanjut mengunci integritas skema data warehouse secara mutlak, sedangkan makro dbt memungkinkan penegakan *Dynamic Data Masking* dan *Role-Based Access Control* (RBAC) langsung dari repositori kode analitik.
3. **Enterprise CI/CD via Slim CI:** Penghematan drastis waktu pengujian dan komputasi cloud warehouse dicapai melalui perbandingan state DAG menggunakan artefak `manifest.json` (`state:modified+`) dan deferral environment.
4. **Resiliency & Performance:** Mitigasi *late-arriving facts* melalui strategi *lookback windowing*, determinasi *unique key* yang ketat, dan klasterisasi partisi fisik data warehouse memastikan eksekutif dan pemangku kepentingan selalu mengonsumsi data yang akurat, tepat waktu, dan hemat biaya komputasi.