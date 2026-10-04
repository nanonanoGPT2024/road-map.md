# Bab 09: Analytics Engineering dbt, Git, & Data Governance
## Modul 01: Fondasi Analytics Engineering, dbt Core, Version Control (Git), dan Data Governance

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang Arsitektur Transformasi ELT**: Mengonseptualisasikan dan mengimplementasikan arsitektur pemodelan data berlapis (*Medallion Architecture*: Staging, Intermediate, Marts) menggunakan paradigma *Analytics Engineering*.
2. **Mengonfigurasi dan Mengorkestrasi dbt Core**: Mengonfigurasi proyek `dbt-core` tingkat *enterprise*, mendefinisikan *sources*, *macros*, *seeds*, dan mengoptimalkan strategi materialisasi (*view*, *table*, *incremental*).
3. **Menerapkan Git-driven DataOps**: Membangun alur kerja *version control* menggunakan Git, mencakup strategi percabangan (*branching strategy*), *peer code review*, dan integrasi *Slim Continuous Integration* (Slim CI) untuk memvalidasi perubahan *state*.
4. **Menegakkan Data Governance & Contracts**: Mengimplementasikan *model contracts*, dokumentasi otomatis, *lineage tracing*, serta validasi data deterministik melalui kombinasi tes generik, tes singular, dan paket audit industri (`dbt-expectations`).
5. **Mengelola Penanganan Error & Schema Drift**: Mengidentifikasi serta mengompensasi kegagalan pemrosesan data inkremental, anomali keterlambatan data (*late-arriving records*), dan pergeseran skema hulu (*upstream schema drift*).

---

### 2. Concept Overview

Transformasi data modern telah bergeser secara fundamental dari paradigma **ETL (Extract, Transform, Load)** klasik menuju **ELT (Extract, Load, Transform)**. Pada paradigma ETL konvensional, transformasi data dilakukan oleh *engine compute* terpisah sebelum data ditulis ke dalam sistem penyimpanan target. Hal ini menimbulkan *bottleneck* performa, fragmentasi logika bisnis, dan ketergantungan ekstrem pada tim *Data Engineering* untuk setiap perubahan kalkulasi metrik sederhana.

```
PARADIGMA KLASIK (ETL):
[Source API/DB] ---> (Compute Engine: Spark/Talend) ---> [Data Warehouse]
                     (Transformasi di luar Storage)

PARADIGMA MODERN (ELT):
[Source API/DB] ---> (Ingestion: Fivetran/Airbyte) ---> [Cloud Data Warehouse]
                                                         (Transformasi via dbt)
```

Pada paradigma ELT, data mentah (*raw data*) diekstrak dan dimuat langsung ke dalam *Cloud Data Warehouse* (Snowflake, BigQuery, Databricks, atau engine analitik lokal seperti DuckDB). Transformasi dilakukan langsung di dalam *warehouse* menggunakan kekuatan komputasi terdistribusi asli (*native push-down SQL execution*).

**Analytics Engineering** menjembatani kesenjangan struktural antara *Data Engineering* dan *Data Analysis*:
* **Data Engineer**: Bertanggung jawab atas ketersediaan infrastruktur, saluran *ingestion* data mentah (*data ingestion pipelines*), platform keandalan, dan latensi sistem.
* **Data Analyst**: Berfokus pada konsumsi akhir, eksploitasi data, pemodelan statistik, *dashboarding*, serta penerjemahan kebutuhan bisnis menjadi wawasan analitis.
* **Analytics Engineer**: Menerapkan prinsip-prinsip rekayasa perangkat lunak (*software engineering best practices*)—seperti *version control*, integrasi berkelanjutan (*continuous integration*), pengujian otomatis (*automated testing*), modularitas (*DRY - Don't Repeat Yourself*), dan dokumentasi kode—ke dalam lapisan pemodelan transformasi data SQL.

Inti dari ekosistem ini adalah **dbt (data build tool)**. dbt bertindak sebagai orkestrator lapisan transformasi (*T* dalam ELT). dbt mengompilasi kode SQL berbasis Jinja menjadi SQL murni (*pure native dialect SQL*), menghitung *Directed Acyclic Graph* (DAG) dependensi secara otomatis, mengeksekusi model dalam urutan topologis yang benar, dan menerapkan tata kelola (*data governance*) langsung di tingkat basis data.

---

### 3. Why It Matters

Tanpa standardisasi *Analytics Engineering*, organisasi enterprise sering mengalami kegagalan operasional data sistemik:

1. **Spaghetti SQL & Tribal Knowledge**:
   Transformasi dijalankan melalui kueri SQL ribuan baris yang tersimpan di dalam alat visualisasi data (BI Tools) atau skrip *cron job* tak bertuan. Modifikasi rumus metrik seperti *Monthly Recurring Revenue* (MRR) di satu *dashboard* tidak merefleksikan angka yang sama di *dashboard* lain, merusak *single source of truth*.
2. **Kegagalan Data Tak Terdeteksi (Silent Data Corruption)**:
   Perubahan skema pada database transaksional hulu (misal: kolom `user_id` diubah namanya atau berisi `NULL`) menyebabkan metrik laporan keuangan melenceng tanpa memicu galat sintaksis (*syntax error*). Tanpa pengujian skema dan asersi otomatis di tingkat transformasi, eksekutif mengambil keputusan berbasis data yang korup.
3. **Absensinya Jejak Audit & Regulasi Kepatuhan (Auditability & Compliance)**:
   Kerangka kerja regulasi seperti GDPR, HIPAA, dan SOX menuntut organisasi membuktikan asal-usul metrik (*data provenance/lineage*). Organisasi harus mampu menunjukkan dari tabel mana data berasal, siapa yang memodifikasi logikanya, kapan model tersebut dikompilasi, dan apakah data sensitif (PII) telah dianonimkan sesuai tata kelola.

Penerapan dbt, Git, dan Data Governance menghadirkan kepastian teknik, efisiensi komputasi *warehouse*, serta transparansi operasional melalui *declarative data modeling*.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur transformasi data end-to-end yang mengintegrasikan alur GitOps, *continuous integration*, *execution DAG*, dan lapisan tata kelola data:

```
+---------------------------------------------------------------------------------------------------+
|                                      VERSION CONTROL LAYER (Git)                                   |
|                                                                                                   |
|  Feature Branch                Pull Request / Merge Review                  Main Branch           |
|  [git checkout -b feat/mrr]  ---> [GitHub PR / CI Workflow] --------------> [Production Artifact] |
+------------------------------------------|--------------------------------------------------------+
                                           | Triggers
                                           v
+---------------------------------------------------------------------------------------------------+
|                                CONTINUOUS INTEGRATION (Slim CI)                                   |
|                                                                                                   |
|  dbt compile --select state:modified+                                                             |
|  dbt test    --select state:modified+ (Running in ephemeral PR schema: pr_1042_analytics)          |
+------------------------------------------|--------------------------------------------------------+
                                           | Merged & Deployed
                                           v
+---------------------------------------------------------------------------------------------------+
|                               DBT ORCHESTRATION & COMPUTE ENGINE                                  |
|                                                                                                   |
|  [Source: Raw OLTP / Events]                                                                      |
|            |                                                                                      |
|            v                                                                                      |
|   +------------------+     Jinja / SQL Compilation     +---------------------------------------+  |
|   |  sources.yml     |  -----------------------------> | Directed Acyclic Graph (DAG) Engine   |  |
|   |  - raw_orders    |                                 +-------------------|-------------------+  |
|   |  - raw_payments  |                                                     |                      |
|   +------------------+                                                     |                      |
|                                                                            v                      |
|   +--------------------------------------------------------------------------------------------+  |
|   |                            MEDALLION TRANSFORMATION LAYERS                                 |  |
|   |                                                                                            |  |
|   |  [Layer 1: Staging (Bronze)]                                                               |  |
|   |   - stg_orders.sql (View, 1:1 raw abstraction, type casting, renaming)                     |  |
|   |   - stg_payments.sql (View)                                                                |  |
|   |            |                                                                               |  |
|   |            v                                                                               |  |
|   |  [Layer 2: Intermediate (Silver)]                                                          |  |
|   |   - int_orders_aggregated.sql (Ephemeral / Table, complex business joins, denormalization)|  |
|   |            |                                                                               |  |
|   |            v                                                                               |  |
|   |  [Layer 3: Marts (Gold)]                                                                   |  |
|   |   - fct_daily_revenue.sql (Incremental Table, partition-pruned, business-ready metrics)   |  |
|   |   - dim_customers.sql (Table, SCD Type 2 or flattened dimension)                          |  |
|   +--------------------------------------------------------------------------------------------+  |
+------------------------------------------|--------------------------------------------------------+
                                           | Produces
                                           v
+---------------------------------------------------------------------------------------------------+
|                              GOVERNANCE, AUDIT, & CONSUMPTION                                     |
|                                                                                                   |
|  +--------------------+     +-----------------------+     +------------------------------------+  |
|  | Data Lineage Graph |     | Schema Contracts      |     | Consumers                          |  |
|  | (OpenLineage API / |     | (dbt contract enforce,|     | - BI Tools (Tableau, Looker)       |  |
|  |  dbt docs)         |     |  Generic & Unit Tests)|     | - AI Agents / Feature Stores       |  |
|  +--------------------+     +-----------------------+     +------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Kompilasi Template Engine Jinja & Resolusi DAG
dbt tidak mengeksekusi SQL mentah Anda secara langsung. dbt memproses file melalui template engine Jinja. Ketika fungsi `ref('model_name')` atau `source('source_name', 'table_name')` dipanggil, terjadi dua fase eksekusi:

1. **Fase Parsing (Graph Generation)**: dbt memindai seluruh direktori proyek, mengevaluasi semua dependensi `ref` dan `source`, lalu membangun *dependency graph* (topological DAG). Apabila terdeteksi dependensi sirkular (misal model A mereferensikan B, dan B mereferensikan A), kompilasi dihentikan seketika dengan pesan `CyclicDependencyException`.
2. **Fase Kompilasi (SQL Rendering)**: String `{{ ref('stg_orders') }}` digantikan dengan identifier absolut database target yang dikonfigurasi pada profil aktif, misalnya `"production_warehouse"."analytics_staging"."stg_orders"`.

#### B. Strategi Materialisasi (*Materialization Strategies*)
Model dbt dapat dimaterialisasikan dalam bentuk fisik yang berbeda di dalam basis data:

| Materialisasi | Mekanisme Database | Keuntungan | Kerugian / Biaya | Use Case Ideal |
|---|---|---|---|---|
| **View** | Dijalankan sebagai pernyataan `CREATE VIEW AS SELECT...` | Tidak ada biaya penyimpanan fisik tambahan; selalu menyajikan data paling mutakhir dari tabel hulu. | Komputasi dijalankan ulang setiap kali kueri dipanggil; latensi tinggi pada agregasi masif. | Lapisan Staging; data dengan pembaruan dinamis berukuran kecil hingga menengah. |
| **Table** | Dijalankan sebagai `CREATE TABLE AS SELECT...` (CTAS) secara atomik menggunakan struktur tabel *swap/drop*. | Performa pembacaan kueri hilir (*downstream query*) sangat cepat; data telah terindeks dan terdistribusi. | Biaya komputasi dan penulisan tinggi saat pembaruan; mengunci sumber daya (*resource intensive*). | Dimensi (*Dimensions*), intermediate modeling kompleks, mart konsumsi BI. |
| **Incremental** | Pada run pertama: CTAS. Pada run selanjutnya: `MERGE`, `INSERT`, atau `DELETE+INSERT` berdasarkan predikat filter. | Mengurangi pemrosesan data historis secara drastis; efisiensi komputasi *warehouse* tinggi pada skala terabyte/petabyte. | Kompleksitas penanganan *schema drift*, *late-arriving records*, dan potensi duplikasi jika kunci unik (*unique_key*) salah dikonfigurasi. | Fakta transaksi volume tinggi (*Event streaming*, *Order ledgers*, *Audit logs*). |
| **Ephemeral** | Dikonversi menjadi *Common Table Expression* (CTE) langsung di dalam kueri model hilir yang mereferensikannya. | Menjaga kebersihan skema basis data (*zero database footprint*). | Tidak dapat di-query secara langsung untuk debugging manual; memperpanjang ukuran kueri hasil kompilasi. | Transformasi mikro yang sangat spesifik dan hanya digunakan oleh satu model lain. |

#### C. Mekanisme Kerja Incremental Materialization
Pada strategi inkremental, blok konfigurasi mengevaluasi makro `is_incremental()`. Makro ini mengembalikan nilai boolean `TRUE` hanya jika kondisi berikut terpenuhi secara simultan:
1. Tabel target fisik sudah eksis di dalam database.
2. dbt tidak dijalankan dengan opsi flags `--full-refresh`.

Mekanisme internal `MERGE` SQL:
```sql
MERGE INTO target_table USING staging_filtered
ON target_table.unique_key = staging_filtered.unique_key
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

#### D. Penegakan Data Governance & Data Contracts
Mulai dbt Core v1.5+, paradigma *Data Contracts* diperkenalkan untuk membalik tanggung jawab rekayasa data. Alih-alih menerima skema secara pasif, model dbt dapat mengunci kontrak skema secara deklaratif:
* `enforced: true`: Mewajibkan kompilator dbt mencocokkan tipe data hasil proyeksi SQL dengan deklarasi skema YAML.
* Jika model mengembalikan tipe data yang melanggar kontrak skema (misal deklarasi `varchar` tetapi kueri menghasilkan `integer` tanpa *explicit cast*), dbt memutus proses eksekusi pipeline (*hard failure*).

---

### 6. Production-Ready Code Implementation

Implementasi ini mengasumsikan penggunaan engine analitik modern (sintaks ANSI/PostgreSQL/DuckDB/Snowflake-compatible). Struktur proyek dbt yang dibangun memodelkan platform e-commerce enterprise.

#### Struktur Proyek:
```text
analytics_project/
├── dbt_project.yml
├── packages.yml
├── models/
│   ├── staging/
│   │   ├── src_ecommerce.yml
│   │   ├── stg_ecommerce__orders.sql
│   │   └── stg_ecommerce__orders.yml
│   ├── intermediate/
│   │   └── int_ecommerce__customer_aggregates.sql
│   └── marts/
│       ├── fct_daily_revenue.sql
│       └── fct_daily_revenue.yml
└── macros/
    └── generate_surrogate_key.sql
```

#### File 1: `dbt_project.yml`
```yaml
name: 'enterprise_analytics'
version: '1.0.0'
config-version: 2

profile: 'enterprise_dw'

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]
seed-paths: ["seeds"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  enterprise_analytics:
    staging:
      +schema: staging
      +materialized: view
    intermediate:
      +schema: intermediate
      +materialized: ephemeral
    marts:
      +schema: marts
      +materialized: table
```

#### File 2: `models/staging/src_ecommerce.yml`
```yaml
version: 2

sources:
  - name: ecommerce
    database: raw_production
    schema: public
    description: "Database transaksional Postgres mentah yang di-ingest via Fivetran."
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    loaded_at_field: _loaded_at
    tables:
      - name: raw_orders
        description: "Log pesanan transaksional mentah langsung dari sistem checkout."
        columns:
          - name: id
            tests:
              - unique
              - not_null
          - name: user_id
          - name: order_date
          - name: status
          - name: amount_cents
```

#### File 3: `macros/generate_surrogate_key.sql`
```sql
{#
    Macro untuk menghasilkan surrogate key deterministik menggunakan hashing SHA-256.
    Menjamin konsistensi hashing di lintas layer pemodelan tanpa bergantung pada auto-increment keys.
#}
{% macro generate_surrogate_key(field_list) %}
    {%- set fields = [] -%}
    {%- for field in field_list -%}
        {%- do fields.append("coalesce(cast(" ~ field ~ " as varchar), '_dbt_null_')") -%}
    {%- endfor -%}
    sha256(concat({{ fields | join(", '||', ") }}))
{% endmacro %}
```

#### File 4: `models/staging/stg_ecommerce__orders.sql`
```sql
-- Materialized as View per folder configuration
with source as (
    select * from {{ source('ecommerce', 'raw_orders') }}
),

renamed_and_casted as (
    select
        -- Identifiers
        cast(id as varchar) as order_id,
        cast(user_id as varchar) as customer_id,
        
        -- Categorical Attributes
        cast(status as varchar) as order_status,
        
        -- Numerics & Monetary
        cast(amount_cents / 100.0 as numeric(16, 2)) as amount_usd,
        
        -- Timestamps
        cast(order_date as timestamp) as ordered_at,
        cast(_loaded_at as timestamp) as ingested_at

    from source
)

select * from renamed_and_casted
```

#### File 5: `models/staging/stg_ecommerce__orders.yml` (Data Contract & Schema Test)
```yaml
version: 2

models:
  - name: stg_ecommerce__orders
    description: "Pembersihan tahap awal dan standarisasi tipe data dari tabel raw_orders."
    config:
      contract:
        enforced: true
    columns:
      - name: order_id
        data_type: varchar
        description: "Primary key untuk entitas order."
        tests:
          - unique
          - not_null

      - name: customer_id
        data_type: varchar
        description: "Foreign key yang mengarah ke sistem identitas pelanggan."
        tests:
          - not_null

      - name: order_status
        data_type: varchar
        tests:
          - accepted_values:
              values: ['completed', 'pending', 'cancelled', 'refunded']

      - name: amount_usd
        data_type: numeric(16,2)
        tests:
          - not_null

      - name: ordered_at
        data_type: timestamp
        tests:
          - not_null

      - name: ingested_at
        data_type: timestamp
```

#### File 6: `models/marts/fct_daily_revenue.sql` (Incremental Mart)
```sql
{{
    config(
        materialized='incremental',
        unique_key='daily_revenue_pk',
        incremental_strategy='merge',
        on_schema_change='append_new_columns',
        partition_by={
            "field": "revenue_date",
            "data_type": "date"
        }
    )
}}

with orders as (
    select * 
    from {{ ref('stg_ecommerce__orders') }}
    where order_status = 'completed'
    
    {% if is_incremental() %}
        -- Optimasi lookback window 3 hari untuk menangani late-arriving mutations
        and ordered_at >= (
            select dateadd(day, -3, max(revenue_date)) 
            from {{ this }}
        )
    {% endif %}
),

daily_aggregation as (
    select
        cast(ordered_at as date) as revenue_date,
        count(distinct order_id) as total_orders,
        count(distinct customer_id) as unique_paying_customers,
        sum(amount_usd) as total_gross_revenue_usd,
        avg(amount_usd) as average_order_value_usd,
        current_timestamp as dbt_updated_at
    from orders
    group by 1
),

final as (
    select
        {{ generate_surrogate_key(['revenue_date']) }} as daily_revenue_pk,
        revenue_date,
        total_orders,
        unique_paying_customers,
        total_gross_revenue_usd,
        average_order_value_usd,
        dbt_updated_at
    from daily_aggregation
)

select * from final
```

#### File 7: `models/marts/fct_daily_revenue.yml`
```yaml
version: 2

models:
  - name: fct_daily_revenue
    description: "Tabel fakta agregasi finansial harian untuk konsumsi BI dan dashboard eksekutif."
    columns:
      - name: daily_revenue_pk
        description: "SHA-256 hash dari revenue_date sebagai surrogate key utama."
        tests:
          - unique
          - not_null

      - name: revenue_date
        description: "Tanggal pembukuan metrik pendapatan."
        tests:
          - not_null

      - name: total_gross_revenue_usd
        description: "Akumulasi nilai penjualan bruto."
        tests:
          - not_null

      - name: total_orders
        description: "Jumlah pesanan berstatus completed."
        tests:
          - not_null
```

---

### 7. Edge Cases & Failure Modes

#### 1. Masalah Keterlambatan Data (*Late-Arriving Dimensions & Facts*)
* **Masalah**: Pesanan yang terjadi pada tanggal 10 baru tersinkronisasi ke dalam sistem analitik pada tanggal 14 karena keterlambatan proses *ingestion* atau proses rekonsiliasi pembayaran.
* **Gejala Kegagalan**: Jika kueri inkremental hanya menggunakan kondisi `ordered_at > (select max(revenue_date) from {{ this }})`, rekaman tertanggal 10 akan dilewati secara permanen, menyebabkan pelaporan pendapatan di bawah nilai sebenarnya (*under-reported revenue*).
* **Solusi/Mitigasi**: Gunakan *rolling lookback window* dinamis (seperti terlihat pada baris `dateadd(day, -3, max(revenue_date))` di file implementasi) dan pastikan tabel target memiliki `unique_key` yang valid agar mesin basis data menjalankan pembaruan nilai (*UPSERT/MERGE*) alih-alih menambahkan baris kembar (*duplicate rows*).

#### 2. Ketidakteraturan Skema (*Silent Schema Drift*)
* **Masalah**: Tim aplikasi hulu menambahkan kolom baru atau mengubah tipe data kolom dari `integer` ke `string` tanpa pemberitahuan.
* **Gejala Kegagalan**: Eksekusi dbt hancur saat operasi `MERGE` dijalankan karena struktur fisik skema tidak kompatibel (*mismatched datatypes*).
* **Solusi/Mitigasi**: Aktifkan konfigurasi `on_schema_change: 'append_new_columns'` atau `fail` secara ketat pada konfigurasi model dbt, dan tegakkan deklarasi skema kontraktual melalui `contract: enforced: true`.

#### 3. Kehancuran Partisi (*Partition Pruning Exhaustion*)
* **Masalah**: Penggunaan fungsi manipulasi kolom pada klausa filter inkremental, seperti `WHERE cast(ordered_at as string) = '...'`.
* **Gejala Kegagalan**: Engine database tidak dapat mengeliminasi partisi (*fails partition pruning*), sehingga seluruh tabel fakta multi-terabyte dibaca ulang secara penuh (*full table scan*). Hal ini menyebabkan ledakan biaya komputasi dan *query timeout*.
* **Solusi/Mitigasi**: Selalu gunakan filter predikat yang kompatibel dengan partisi (*SARGable predicates*), menyaring langsung pada kolom fisik indeks/partisi tanpa transformasi fungsional di klausa `WHERE`.

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan dalam arsitektur analitik membawa implikasi langsung terhadap performa, kompleksitas kode, dan biaya infrastruktur:

```
VIEW                              TABLE                          INCREMENTAL
Latency Data Rendah          Throughput Pembacaan Tinggi    Efisiensi Biaya Komputasi Tinggi
Biaya Compute Ad-hoc Tinggi  Biaya Rebuild Batch Tinggi     Kompleksitas Logika Tinggi
<--------------------------------------------------------------------------------------->
```

#### 1. Materialization View vs. Table vs. Incremental
* **View**:
  * *Kelebihan*: Tidak butuh biaya *storage*; perubahan kode logika hulu langsung terlihat seketika.
  * *Kekurangan*: Beban pemrosesan dipindahkan ke *end-user/BI*; eksekusi lambat pada data skala besar.
* **Table**:
  * *Kelebihan*: Pembacaan sangat cepat dan konsisten; mengisolasi pengguna dari fluktuasi komputasi *base table*.
  * *Kekurangan*: Siklus rebuild memerlukan waktu lama; biaya kalkulasi ulang data historis yang sebenarnya tidak berubah bersifat mubazir.
* **Incremental**:
  * *Kelebihan*: Waktu pipeline transformasi stabil di kisaran linear/konstan, hemat komputasi gudang data.
  * *Kekurangan*: Beban manajemen status (state management), penanganan rekaman yang di-update di masa lalu memerlukan strategi *lookback window* yang rumit.

#### 2. dbt Core vs. SQLMesh vs. Stored Procedures Tradisional
* **Stored Procedures Tradisional**:
  * *Trade-off*: Efisien secara komputasi lokal, tetapi rentan menjadi "kotak hitam" tanpa *lineage graph*, tanpa asersi pengujian terintegrasi, dan sulit diuji di lingkungan terisolasi (*CI/CD hostile*).
* **SQLMesh**:
  * *Trade-off*: SQLMesh menawarkan deteksi perubahan semantik tingkat lanjut (*virtual data environments*), namun ekosistem komunitas, adopsi industri, dan ketersediaan *third-party plugins* dbt Core jauh lebih matang dan dominan secara global.

---

### 9. Best Practices & Standard Industri

1. **Konvensi Penamaan Ketat (*Strict Naming Conventions*)**:
   * Lapisan Staging: Beri prefiks `stg_<source>__<entities>` (contoh: `stg_ecommerce__orders`).
   * Lapisan Intermediate: Beri prefiks `int_<entities>__<transformation_logic>` (contoh: `int_orders__customer_pivoted`).
   * Lapisan Marts: Beri prefiks `fct_<metric_domain>` untuk tabel fakta dan `dim_<entity_name>` untuk tabel dimensi.
2. **Kemandirian Lingkungan (*Slim CI Optimization*)**:
   Jangan pernah menjalankan `dbt build` terhadap seluruh proyek di dalam proses pull request continuous integration (CI). Manfaatkan *artifact comparison* dari dbt:
   ```bash
   dbt build --select state:modified+ --state path/to/production/artifacts
   ```
   Langkah ini hanya mengeksekusi model-model yang baris logikanya telah diubah secara aktual beserta model hilir (*downstream models*) yang terdampak langsung.
3. **Pemberian Kunci Non-Surrogate Alami Dilarang di Marts**:
   Selalu buat *surrogate key* komposit deterministik (berbasis algoritma hashing MD5 atau SHA-256) untuk seluruh tabel fakta dan dimensi guna menghindari dependensi terhadap urutan autoincrement ID dari sistem transaksional.
4. **Isolasi Database per Lingkungan Melalui Dynamic Schemas**:
   Pastikan lingkungan pengembangan developer menuliskan data ke skema terisolasi (contoh: `dbt_<developer_username>`), sementara lingkungan produksi menulis ke skema kanonikal (`analytics_marts`). Hal ini dikendalikan melalui kustomisasi macro `generate_schema_name`.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun pipeline dbt dari data penjualan mentah lokal hingga tabel fakta agregasi harian, memvalidasi integritas data dengan *schema tests*, dan menguji perilaku *data contract enforcement*.

#### Prasyarat
* Python 3.9+ telah terpasang.
* Akses terminal/bash.

#### Langkah 1: Inisialisasi Environment & dbt DuckDB
Buka terminal dan jalankan skrip berikut:

```bash
# 1. Buat direktori kerja dan virtual environment
mkdir -p dbt_governance_lab && cd dbt_governance_lab
python -m venv venv
source venv/bin/activate  # Untuk Windows: venv\Scripts\activate

# 2. Instal dbt-core dan adapter DuckDB (engine SQL kolumnar lokal performa tinggi)
pip install dbt-core==1.8.0 dbt-duckdb==1.8.0

# 3. Buat struktur folder proyek standar dbt
mkdir -p data models/staging models/marts macros
```

#### Langkah 2: Buat Konfigurasi Profil Database (`profiles.yml`)
Simpan file ini di direktori root atau di direktori `~/.dbt/profiles.yml`:

```yaml
# profiles.yml
lab_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: 'warehouse.duckdb'
      threads: 2
```

#### Langkah 3: Konfigurasi Proyek (`dbt_project.yml`)
Simpan file berikut di direktori root `dbt_governance_lab/dbt_project.yml`:

```yaml
name: 'lab_governance'
version: '1.0.0'
config-version: 2

profile: 'lab_profile'

model-paths: ["models"]
macro-paths: ["macros"]
seed-paths: ["data"]

models:
  lab_governance:
    staging:
      +materialized: view
    marts:
      +materialized: table
```

#### Langkah 4: Siapkan Data Mentah (*Seed Data*)
Buat file `data/raw_transactions.csv`:

```csv
transaction_id,user_id,amount,transaction_date,status
tx101,usr_1,250.00,2024-01-01 10:00:00,completed
tx102,usr_2,150.50,2024-01-01 11:30:00,completed
tx103,usr_1,99.00,2024-01-02 09:15:00,completed
tx104,usr_3,500.00,2024-01-02 14:00:00,refunded
tx105,usr_4,35.00,2024-01-03 16:45:00,completed
```

Jalankan perintah seed untuk memuat data CSV ke dalam basis data DuckDB:
```bash
dbt seed
```

#### Langkah 5: Implementasi Macro SHA-256
Buat file `macros/generate_surrogate_key.sql`:

```sql
{% macro generate_surrogate_key(field_list) %}
    {%- set fields = [] -%}
    {%- for field in field_list -%}
        {%- do fields.append("coalesce(cast(" ~ field ~ " as varchar), '_null_')") -%}
    {%- endfor -%}
    md5(concat({{ fields | join(", '||', ") }}))
{% endmacro %}
```

#### Langkah 6: Implementasi Model Staging dan Kontrak Skema
Buat file `models/staging/stg_transactions.sql`:

```sql
with source as (
    select * from {{ ref('raw_transactions') }}
),

transformed as (
    select
        cast(transaction_id as varchar) as transaction_id,
        cast(user_id as varchar) as user_id,
        cast(amount as numeric(10, 2)) as amount_usd,
        cast(transaction_date as timestamp) as transaction_timestamp,
        cast(status as varchar) as transaction_status
    from source
)

select * from transformed
```

Buat file dokumentasi dan pengujian `models/staging/stg_transactions.yml`:

```yaml
version: 2

models:
  - name: stg_transactions
    description: "Layer staging untuk data transaksi keuangan."
    config:
      contract:
        enforced: true
    columns:
      - name: transaction_id
        data_type: varchar
        tests:
          - unique
          - not_null
      - name: user_id
        data_type: varchar
        tests:
          - not_null
      - name: amount_usd
        data_type: numeric(10,2)
        tests:
          - not_null
      - name: transaction_timestamp
        data_type: timestamp
        tests:
          - not_null
      - name: transaction_status
        data_type: varchar
        tests:
          - accepted_values:
              values: ['completed', 'refunded', 'pending']
```

#### Langkah 7: Implementasi Model Marts Agregasi
Buat file `models/marts/fct_daily_sales.sql`:

```sql
with staging as (
    select * from {{ ref('stg_transactions') }}
    where transaction_status = 'completed'
),

aggregated as (
    select
        cast(transaction_timestamp as date) as sale_date,
        count(distinct transaction_id) as total_successful_transactions,
        sum(amount_usd) as total_volume_usd,
        round(avg(amount_usd), 2) as average_ticket_usd
    from staging
    group by 1
)

select
    {{ generate_surrogate_key(['sale_date']) }} as daily_sales_pk,
    sale_date,
    total_successful_transactions,
    total_volume_usd,
    average_ticket_usd
from aggregated
```

Buat file uji `models/marts/fct_daily_sales.yml`:

```yaml
version: 2

models:
  - name: fct_daily_sales
    columns:
      - name: daily_sales_pk
        tests:
          - unique
          - not_null
      - name: sale_date
        tests:
          - not_null
```

#### Langkah 8: Eksekusi, Pengujian Data, dan Validasi Tata Kelola

Jalankan model dan tes untuk memvalidasi pipeline:
```bash
# Kompilasi dan eksekusi seluruh model DAG
dbt run

# Jalankan pengujian deklaratif yang telah didefinisikan di YAML
dbt test
```

*Output yang diharapkan dari terminal:*
```text
Running with dbt=1.8.0
Found 2 models, 7 tests, 1 seed, 0 sources

Concurrency: 2 threads (target='dev')

1 of 2 START sql view model dev.stg_transactions ............................. [RUN]
1 of 2 OK created sql view model dev.stg_transactions ........................ [OK in 0.08s]
2 of 2 START sql table model dev.fct_daily_sales ............................. [RUN]
2 of 2 OK created sql table model dev.fct_daily_sales ........................ [OK in 0.12s]

Finished running 1 view model, 1 table model in 0.35s.

Running 7 tests
1 of 7 START test accepted_values_stg_transactions_transaction_status ......... [RUN]
...
7 of 7 PASS unique_fct_daily_sales_daily_sales_pk ............................. [PASS in 0.05s]

Finished running 7 tests in 0.42s.
All checks passed!
```

#### Langkah 9: Verifikasi Penegakan Kontrak Data (*Failure Simulation*)
Uji ketangguhan *contract enforcement*. Edit file `models/staging/stg_transactions.sql`, ubah proyeksi `transaction_id`:

```sql
-- Sengaja memicu error type contract
cast(transaction_id as integer) as transaction_id,
```

Jalankan perintah run:
```bash
dbt run --select stg_transactions
```

*Hasil Pengujian Tata Kelola:*
dbt akan memblokir eksekusi kompilasi secara langsung dan mengembalikan kegagalan kontraktual (*Compilation/Contract Enforcement Error*):
```text
Model 'stg_transactions' does not meet the specified contract!
  Column: transaction_id
  Declared Type: varchar
  Actual Type: integer
```
Kembalikan tipe data ke `cast(transaction_id as varchar)` untuk menormalkan kembali sistem analitik Anda.

#### Langkah 10: Generate Dokumentasi Lineage
Jalankan perintah berikut untuk mengompilasi katalog metadata dan membuka visualisasi lineage interaktif di peramban web:

```bash
# Menghasilkan manifest.json dan catalog.json
dbt docs generate

# Menjalankan server dokumentasi lokal
dbt docs serve --port 8080
```

Buka `http://localhost:8080` pada peramban Anda untuk melihat Directed Acyclic Graph (DAG) interaktif, skema data contract, dan kamus metrik yang diproduksi secara langsung dari repositori kode.