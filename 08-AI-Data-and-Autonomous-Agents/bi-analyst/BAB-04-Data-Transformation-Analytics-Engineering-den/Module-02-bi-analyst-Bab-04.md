# BAB 04: Data Transformation & Analytics Engineering
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur data transformation multi-layer (Staging, Intermediate, Marts) berskala enterprise menggunakan **dbt (data build tool)**.
- Menguasai strategi materialisasi lanjutan: *incremental models* berbasis micro-batch, dynamic partition pruning, dan merge predicates kustom untuk efisiensi komputasi cloud data warehouse (Snowflake / BigQuery / Databricks).
- Membangun pipeline tracking histori dimensi kompleks (**Slowly Changing Dimension Type 2 & Type 4**) secara deterministik dengan dbt snapshots dan custom window functions.
- Mengonfigurasi automated CI/CD pipeline analytics engineering dengan memanfaatkan **Slim CI (`dbt state:modified`)** untuk menekan biaya komputasi testing hingga 80%.
- Mengintegrasikan **dbt Semantic Layer & MetricFlow** untuk menstandarisasi metriks bisnis lintas platform Business Intelligence (BI) tanpa disparitas definisi (single source of truth).
- Menganalisis trade-offs arsitektural antara latensi data, idempotensi pemrosesan, fragmentasi storage, dan biaya komputasi warehouse.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib memiliki pemahaman mendalam pada:
- **Advanced SQL**: Window functions (`ROW_NUMBER`, `DENSE_RANK`, `LEAD`, `LAG`), Common Table Expressions (CTEs), recursive queries, JSON parsing, dan query execution plan analysis.
- **Dimensional Modeling**: Skema Kimball (Fact tables, Dimension tables, Conformed dimensions, Degenerate dimensions, Bridge tables).
- **Fundamental dbt**: Struktur project dbt dasar, konfigurasi `dbt_project.yml`, ref/source macros, dan materialisasi dasar (`view`, `table`).
- **Modern Cloud Data Warehouses**: Konsep micro-partitioning (Snowflake), clustering/partitioning (BigQuery), atau Delta Lake layout (Databricks).
- **Git & Software Engineering Workflows**: Branching strategy, pull request workflows, dan konsep automasi CI/CD pipelines (GitHub Actions/GitLab CI).

---

### 3. Concept & Internal Architecture

#### 3.1. Internal State Engine & The Directed Acyclic Graph (DAG)
dbt mengompilasi kode Jinja-SQL modular menjadi target DDL/DML dialek SQL native data warehouse Anda. Dalam fase kompilasi:
1. **Parsing & AST Construction**: dbt membaca seluruh file `.sql` dan `.yml`, mengurai ketergantungan model melalui referensi `{{ ref('...') }}` dan `{{ source('...') }}`.
2. **DAG Compilation**: Membangun topologi ketergantungan non-siklus (DAG). Node mewakili model, snapshot, semantic node, test, dan seed. Edge mewakili garis keturunan (lineage).
3. **Artifact Generation (`manifest.json`)**: Kompilasi menghasilkan file state biner/JSON bernama `manifest.json`. File ini memuat representasi lengkap dari metadata proyek, model signatures, SQL terkompilasi, hash konfigurasi, dan test metadata.
4. **State-Aware Execution**: Pada lingkungan CI/CD, dbt membandingkan `manifest.json` cabang aktif terhadap branch utama (`production`). Operator selector seperti `state:modified+` memanfaatkan dynamic graph traversal untuk mengisolasi hanya node yang berubah dan dependensi hilirnya (*downstream consumers*).

```
[ Git Feature Branch ] ──> Compile ──> Local manifest.json
                                             │
                                    (State Comparison) <── Prod manifest.json
                                             │
                                    Isolate Modified Models
                                             │
                                             ▼
                                   Run: state:modified+
```

#### 3.2. Advanced Incremental Engine & State Idempotency
Transformasi full-refresh (`CREATE OR REPLACE TABLE AS SELECT`) tidak dapat bertahan saat dataset mencapai miliaran baris. Model inkremental menyelesaikan ini dengan memproses subset data baru/termodifikasi:

- **The `is_incremental()` Macro**: Menghasilkan DDL sementara (staging table/view) dari batch baru, lalu mengeksekusi atomic upsert/merge ke target table.
- **Merge Strategies**:
  - `merge` (ANSI standard): Menjalankan conditional match berdasarkan `unique_key`. Rentan terhadap performa buruk jika tabel target tidak terpartisi dengan benar karena warehouse harus memindai seluruh micro-partitions untuk mendeteksi kesamaan kunci.
  - `insert_overwrite`: Menghapus seluruh partisi target dan menggantinya dengan data baru dari partisi bersangkutan. Menghindari pemindaian baris-per-baris, menjadikannya strategi paling hemat biaya untuk dataset berorientasi waktu (*event stream* / *immutable logs*).
  - `microbatch` (dbt v1.9+): Menghindari scanning lookup window secara manual dengan membatasi eksekusi per granularity waktu diskrit (misal: per jam/hari) secara independen.
- **Predicates Pushdown**: Menginjeksi filter eksplisit (`incremental_predicates`) ke dalam join clause merge internal DML. Tujuannya adalah membatasi *partition pruning* pada tabel target hanya pada rentang waktu data staging, memangkas scanning dari TBs menjadi GBs.

#### 3.3. Semantic Layer & Metric Standardization Architecture
Secara tradisional, logika metrik (seperti *Net Revenue*, *Churn Rate*, *Customer Acquisition Cost*) terduplikasi di dashboard Looker, Tableau, Metabase, dan ad-hoc query Python.
Arsitektur dbt Semantic Layer (berbasis MetricFlow) memisahkan **definisi metrik bisnis** dari **lapisan presentasi BI**:
- **Semantic Models**: Mendefinisikan entity (misal: `customer_id`), measures (agregasi dasar: `SUM(amount)`), dan dimensions (kategorikal/waktu).
- **Metric Definitions**: Menentukan kalkulasi bisnis formal (misal: rasio, kumulatif, derivatif).
- **Dynamic Query Engine**: Client (BI tools/API) meminta metrik `net_revenue` dipotong berdasarkan `customer.region`. MetricFlow secara dinamis menghasilkan query SQL yang optimal, menghindari *fan-out traps* dan *chasm traps* secara otomatis melalui entity relationships.

---

### 4. Why & What

| Dimensi | Legacy Stored Procedures / ELT Konvensional | Modern Production Analytics Engineering |
| :--- | :--- | :--- |
| **Keterbacaan & Modularitas** | Monolitik SQL scripts ribuan baris, dependency di-hardcode via procedural orchestrator. | Modular (Single Responsibility Principle), dependency terdefinisi secara deklaratif via `ref()`. |
| **Data Quality & Testing** | Pengecekan manual pasca pipeline gagal, data anomali lolos ke dashboard tanpa alert. | Automated contract testing, unit testing SQL, dan statistical assertion sebelum model dipublikasikan. |
| **Histori & State Tracking** | Custom DML scripts yang rentan terhadap race-condition saat menangani updates. | Deterministik SCD Type 2 engine via automated cryptographic hashing & validity timestamping. |
| **CI/CD & Governance** | Perubahan diuji langsung di staging/production database; blasting radius tidak terkontrol. | Automated Slim CI, ephemeral PR staging environments, schema contracts, dan model deprecation warnings. |
| **Metrik Organisasi** | Definisi KPI berbeda-beda di tiap dashboard (misal: Marketing vs Finance ARR). | Single Source of Truth via Semantic Layer; metrik didefinisikan sekali dalam kode, dikonsumsi semua platform. |

---

### 5. How (Workflow Detail)

Arsitektur produksi end-to-end mengikuti alur siklus hidup data dan siklus hidup kode secara simultan:

```
[ Raw Ingestion Layer ] (Fivetran / Airbyte / Kafka)
           │
           ▼
[ Staging Layer (stg_) ] ── Pure 1:1 view, casting tipe data, renaming kolom, deduplikasi awal
           │
           ▼
[ Intermediate Layer (int_) ] ── Heavy joins, business entities restructuring, window aggregations
           │
           ▼
[ Marts Layer (fct_, dim_) ] ── Star-schema denormalization, incremental loads, SCD snapshotting
           │
           ├──────────────────────────────┐
           ▼                              ▼
[ Semantic Layer / MetricFlow ]    [ Reverse ETL / Activation ]
           │                              │
           ▼                              ▼
[ BI Consumers (Tableau, Looker) ] [ CRM, Marketing Platforms ]
```

#### Siklus Hidup Deploy (Continuous Integration via Slim CI)
1. **Developer Branch**: Analytics Engineer membuat branch baru, memodifikasi logic pada satu model intermediate `int_order_items_discounted.sql`.
2. **Pull Request Trigger**: GitHub Actions memicu CI runner.
3. **Artifact Retrieval**: CI runner mengunduh `manifest.json` dari rilis produksi terakhir yang tersimpan di Cloud Storage (S3/GCS).
4. **Selective Build & Test (Slim CI)**:
   ```bash
   dbt build --select state:modified+ --defer --state ./prod-manifest
   ```
   *Mekanisme `--defer`*: Model upstream yang tidak berubah tidak di-build ulang di schema PR; dbt secara dinamis mengarahkan referensinya ke schema produksi tanpa menduplikasi data.
5. **Contract Enforcement**: dbt memvalidasi apakah ada breaking changes pada nama kolom atau tipe data terhadap konsumen downstream.
6. **Merge to Main**: Pipeline CD memicu running target staging/production environment secara teratur.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Manufaktur Modular
Bayangkan perakitan mobil:
- **Legacy Approach**: Satu mekanik merakit seluruh mobil dari lempengan baja mentah, kabel, dan mesin di satu ruangan tanpa cetak biru formal. Jika rem bermasalah, seluruh mobil harus dibongkar tanpa tahu komponen mana yang cacat.
- **Analytics Engineering Approach**: 
  - **Staging**: Pembersihan lempengan baja mentah dari kotoran dan inspeksi dimensi awal.
  - **Intermediate**: Pembuatan sub-komponen (blok silinder mesin, sasis, transmisi) yang independen dan dapat diuji secara terpisah di meja uji masing-masing.
  - **Marts**: Perakitan final menjadi mobil utuh (sedan, truk) siap pakai oleh pengemudi (analis bisnis).
  - **Slim CI**: Saat desain baut sasis diubah, pabrik hanya menguji sasis dan mobil yang menggunakan sasis tersebut; pabrik tidak membuang waktu menguji ulang mesin mobil lain yang tidak terpengaruh.

#### Diagram Arsitektur Incremental Predicates & Partition Pruning

```
Target Table Micro-Partitions (Snowflake / BigQuery):
┌────────────────┬────────────────┬────────────────┬────────────────┐
│ Date: 2023-10  │ Date: 2023-11  │ Date: 2023-12  │ Date: 2024-01  │
│ [PARTITION 01] │ [PARTITION 02] │ [PARTITION 03] │ [PARTITION 04] │
└────────────────┴────────────────┴────────────────┴────────────────┘
        │                │                │                │
        │ SKIP           │ SKIP           │ SCANNED        │ SCANNED
        ▼                ▼                ▼                ▼
   (Pruned away by incremental_predicates)   [   MERGE WINDOW EVALUATION  ]
                                             ▲
                                             │ Lookback Buffer (3 Days)
                                   ┌──────────────────┐
                                   │ Incoming Changes │
                                   │  (Staging Batch) │
                                   └──────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Reusable Window-Deduplication Macro
File: `macros/deduplicate.sql`
```sql
{% macro deduplicate(relation, partition_by, order_by) %}
    select *
    from (
        select
            *,
            row_number() over (
                partition by {{ partition_by }}
                order by {{ order_by }}
            ) as _dedup_rank
        from {{ relation }}
    )
    where _dedup_rank = 1
{% endmacro %}
```

Penggunaan di Model:
```sql
-- models/staging/stg_crm__users.sql
{{ config(materialized='view') }}

with raw_users as (
    select * from {{ source('crm_raw', 'users') }}
)

{{ deduplicate('raw_users', 'user_id', 'updated_at desc') }}
```

---

#### 7.2. Practical Example: Enterprise-Grade Incremental Fact Model dengan Partition Pruning & Contract Testing

File: `models/marts/fct_orders.yml`
```yaml
version: 2

models:
  - name: fct_orders
    description: "Tabel fakta pesanan enterprise dengan incremental merge optimal dan strict schema contract."
    config:
      contract:
        enforced: true
    columns:
      - name: order_key
        data_type: string
        description: "Surrogate key berbasis hash MD5/SHA256"
        data_tests:
          - not_null
          - unique
      - name: order_id
        data_type: string
        data_tests:
          - not_null
      - name: customer_id
        data_type: string
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      - name: order_status
        data_type: string
        data_tests:
          - accepted_values:
              values: ['PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'REFUNDED']
      - name: order_timestamp
        data_type: timestamp
        data_tests:
          - not_null
      - name: gross_amount_usd
        data_type: numeric(18,4)
      - name: net_amount_usd
        data_type: numeric(18,4)
```

File: `models/marts/fct_orders.sql`
```sql
{{
    config(
        materialized='incremental',
        unique_key='order_key',
        incremental_strategy='merge',
        merge_update_columns=['order_status', 'net_amount_usd', 'updated_at'],
        on_schema_change='fail',
        partition_by={
            "field": "order_timestamp",
            "data_type": "timestamp",
            "granularity": "day"
        },
        cluster_by=['customer_id', 'order_status'],
        incremental_predicates=[
            "DBT_INTERNAL_DEST.order_timestamp >= timestamp_sub(current_timestamp(), interval 7 day)"
        ]
    )
}}

with source_orders as (
    select * from {{ ref('stg_ecommerce__orders') }}
    {% if is_incremental() %}
        -- Dynamic lookback window untuk mengatasi late-arriving events hingga 3 hari ke belakang
        where updated_at >= (
            select timestamp_sub(max(updated_at), interval 3 day)
            from {{ this }}
        )
    {% endif %}
),

source_payments as (
    select * from {{ ref('stg_ecommerce__payments') }}
),

aggregated_payments as (
    select
        order_id,
        sum(case when payment_status = 'SUCCESS' then amount_usd else 0 end) as total_paid_amount_usd
    from source_payments
    {% if is_incremental() %}
        where payment_timestamp >= (
            select timestamp_sub(max(order_timestamp), interval 7 day)
            from {{ this }}
        )
    {% endif %}
    group by 1
),

final as (
    select
        -- Surrogate Key deterministik menggunakan dbt_utils
        {{ dbt_utils.generate_surrogate_key(['o.order_id']) }} as order_key,
        cast(o.order_id as string) as order_id,
        cast(o.customer_id as string) as customer_id,
        cast(o.order_status as string) as order_status,
        cast(o.order_timestamp as timestamp) as order_timestamp,
        cast(o.gross_amount_usd as numeric(18,4)) as gross_amount_usd,
        cast(coalesce(p.total_paid_amount_usd, 0) as numeric(18,4)) as net_amount_usd,
        cast(o.updated_at as timestamp) as updated_at
    from source_orders o
    left join aggregated_payments p on o.order_id = p.order_id
)

select
    order_key,
    order_id,
    customer_id,
    order_status,
    order_timestamp,
    gross_amount_usd,
    net_amount_usd
from final
```

---

### 8. Real World Case Study: E-Commerce Scale Migration

#### Latar Belakang & Masalah
Perusahaan e-commerce multinasional memproses 40 juta transaksi per hari di Google BigQuery. Sebelumnya, pemrosesan analitik menggunakan *monolithic scheduled query* sepanjang 2.400 baris SQL yang dijalankan setiap 4 jam. 
**Dampak Buruk**:
- Biaya BigQuery meledak hingga $45,000/bulan akibat full-scan pemindaian tabel `orders` yang mencapai ratusan Terabyte per run.
- Sering terjadi kegagalan pipeline karena timeout pemrosesan (kuota slot compute habis).
- Tidak ada mekanisme testing otomatis; error logic pada diskon baru disadari 2 minggu kemudian saat tim Finance merekonsiliasi laba kotor.

#### Implementasi Solusi
1. **Refactoring ke Modularity**: Query 2.400 baris dipecah menjadi 12 model: 4 staging views, 5 intermediate tables (memecah pemrosesan promo codes, shipment, refund, taxes), dan 1 incremental mart (`fct_orders`).
2. **Partisi & Dynamic Incremental Strategy**: Mengubah target model menjadi incremental dengan `insert_overwrite` terpartisi harian. Menggunakan buffer window lookback 3 hari untuk mengakomodasi pembatalan dan status perubahan pesanan.
3. **Penerapan Model Contracts & Generic Tests**: Seluruh foreign key ditambahkan relasi assertion test. `contract: {enforced: true}` diaktifkan agar deployment diblokir secara otomatis jika tim source data merubah struktur skema tanpa pemberitahuan.
4. **Slim CI Implementation**: Integrasi GitHub Actions dengan dbt Cloud metadata API. Runtime pengujian PR menyusut dari 48 menit (full DAG) menjadi 3 menit (hanya model yang termodifikasi).

#### Hasil Kuantitatif
- **Penghematan Biaya Compute**: Pemindaian data harian berkurang 88%, menghemat pengeluaran BigQuery dari $45,000/bulan menjadi $7,200/bulan.
- **Pipeline Latency**: Data freshness meningkat dari 4 jam menjadi 15 menit.
- **Data Quality Incident**: Menurun drastis dari rata-rata 8 insiden data analytics per kuartal menjadi 0 insiden dalam 6 bulan pertama implementasi.

---

### 9. Trade-offs Architecture Matrix

| Strategi / Keputusan | Keuntungan | Kerugian & Konsekuensi | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **View Materialization** | Zero storage cost; selalu merefleksikan data terkini secara instan. | Beban komputasi berulang dibebankan pada query BI reader; query lambat pada aggregasi berat. | Staging models (`stg_`), filtering sederhana, transformasi ringan. | Marts tables, visualisasi dashboard interaktif bertrafik tinggi. |
| **Incremental (Merge)** | Menjaga integritas data unik (`unique_key`), fleksibel terhadap mutasi record non-deterministik. | Compute cost tinggi saat micro-partitioning warehouse terpecah; risiko scan masif tanpa `incremental_predicates`. | Data transaksional dengan status yang sering berubah (misal: pesanan e-commerce). | Append-only event streams (log clicks, sensor metrics). |
| **Incremental (Insert Overwrite)** | Sangat cepat; zero-scan pada partisi yang tidak berubah; biaya komputasi jauh lebih rendah. | Memerlukan data yang secara ketat berbasis waktu; risiko kehilangan data jika partisi staging kosong/salah hitung. | Immutable event logs, metrics snapshots, ledger immutable. | Data yang sering ter-update secara acak pada rentang tahun/bulan lampau. |
| **SCD Type 2 (Snapshots)** | Menyimpan seluruh histori perubahan atribut bisnis secara sempurna dengan audit trail. | Eksplosi storage; query join dimensional downstream menjadi lebih kompleks (`WHERE event_ts BETWEEN valid_from AND valid_to`). | Core Master Data: Customer status, Employee tier, Product catalog pricing. | High-frequency update telemetry data (IoT/Sensor data). |
| **Schema Contracts Enforced** | Mencegah silent schema breakage; downstream application terlindungi dari drift tipe data. | Developer overhead tinggi; memerlukan sinkronisasi koordinasi ketat lintas tim data & software engineers. | Production Marts yang dikonsumsi oleh Finance, External Clients, Machine Learning models. | Staging experimental sandbox models. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The "Fan-Out Trap" on Incremental Join
*Gejala*: Jumlah baris pada tabel inkremental target terus berlipat ganda setiap kali incremental job berjalan.
*Akar Masalah*: Join antara intermediate data dengan reference data non-unik (1-to-many join) menyebabkan duplikasi baris yang gagal dieliminasi oleh klausa merge dbt jika composite key tidak dikonfigurasi secara absolut.
*Solusi*: 
Gunakan macro `dbt_utils.generate_surrogate_key` yang menggabungkan seluruh komponen natural key dan dimensi pembeda, lalu validasikan dengan test `unique` di schema `.yml`.
```sql
{{ dbt_utils.generate_surrogate_key(['order_id', 'line_item_id', 'updated_at']) }} as fct_orders_surrogate_key
```

#### 2. Warehouse Full Scan pada Incremental Model
*Gejala*: Tagihan compute data warehouse melonjak tinggi meskipun hanya 100 baris data baru yang diproses.
*Akar Masalah*: Engine warehouse gagal mengevaluasi *micro-partition pruning* karena predicate merge tidak memiliki batasan eksplisit terhadap target table internal (`DBT_INTERNAL_DEST`).
*Solusi*: 
Tambahkan konfigurasi `incremental_predicates` di block config model Anda:
```sql
config(
    materialized='incremental',
    unique_key='id',
    incremental_predicates=[
        "DBT_INTERNAL_DEST.created_date >= dateadd('day', -7, current_date())"
    ]
)
```

#### 3. Late-Arriving Dimensions pada SCD Type 2
*Gejala*: Transaksi fakta masuk dengan timestamp `2024-01-05`, namun snapshot dimensi customer baru mencatat pembaruan pertama pada `2024-01-06`. Hasil join menghasilkan `dim_customer_key = NULL`.
*Solusi*:
Implementasikan *Default Inferred Dimension Record* (Ghost Dimension). Saat lookup surrogate key dimensi gagal:
```sql
coalesce(dim_customer.customer_key, '-1') as customer_key
```
Di mana key `-1` merepresentasikan "Unknown/Not Yet Available Customer Dimension", yang kemudian di-update melalui pipeline rekonsiliasi berkala.

---

### 11. Best Practices & Production Checklist

#### Architectural Guidelines
- [ ] **Layering Isolation**: Model analitik dilarang keras melompati layer. Staging tidak boleh mereferensikan model Intermediate; Marts tidak boleh langsung membaca dari Source table mentah.
- [ ] **Deterministic Surrogate Keys**: Gunakan hash function (MD5/SHA256) untuk membuat Primary Key sintetik, bukan auto-incrementing integer/identity warehouse.
- [ ] **Contract Testing**: Seluruh model di Layer Marts harus memiliki flag `enforced: true` untuk mengunci contract schema bagi konsumen data.

#### Production Deployment Checklist
- [ ] `dbt source freshness` dieksekusi sebelum transformasi berjalan untuk mendeteksi stalled pipelines upstream.
- [ ] Model inkremental memiliki parameter testing isolasi: Jalankan full-refresh berkala (misal: mingguan pada low-traffic hours) untuk mengoreksi state drifts:
  ```bash
  dbt run --select fct_orders --full-refresh
  ```
- [ ] Seluruh Jinja templating tidak mengandung *raw table names* secara manual; mutlak menggunakan syntax `{{ ref('...') }}` atau `{{ source('...', '...') }}`.
- [ ] Tagging & Cost Tracking: Terapkan query tagging di level config model untuk auditing biaya:
  ```sql
  {{ config(tags=['finance', 'daily_marts'], snowflake_warehouse='ANALYTICS_TRANSFORM_WH') }}
  ```
- [ ] Setup documentation assertion: Jalankan `dbt docs generate` secara otomatis di CI pipeline dan host dokumen arsitektur lineage di internal static storage (S3/GCS buckets).

---

### 12. Hands-on Practice

Buat struktur project dbt lokal Anda dengan direktori berikut untuk modul ini:

```
hands-on/m02/
├── dbt_project.yml
├── packages.yml
├── macros/
│   └── generate_custom_slug.sql
├── models/
│   ├── staging/
│   │   ├── _sources.yml
│   │   ├── stg_payments.sql
│   │   └── stg_subscriptions.sql
│   ├── intermediate/
│   │   └── int_subscription_payments_joined.sql
│   └── marts/
│       ├── _marts_models.yml
│       └── fct_mrr_movements.sql
└── tests/
    └── assert_positive_mrr.sql
```

#### Langkah 1: Inisialisasi Dependensi Package
File: `hands-on/m02/packages.yml`
```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.3.0
```
*Jalankan command:*
```bash
dbt deps
```

#### Langkah 2: Konfigurasi Source dan Staging
File: `hands-on/m02/models/staging/_sources.yml`
```yaml
version: 2
sources:
  - name: billing_db
    schema: raw_billing
    tables:
      - name: raw_subscriptions
      - name: raw_payments
```

File: `hands-on/m02/models/staging/stg_subscriptions.sql`
```sql
{{ config(materialized='view') }}

select
    cast(id as string) as subscription_id,
    cast(customer_id as string) as customer_id,
    cast(plan_name as string) as plan_name,
    cast(status as string) as subscription_status,
    cast(monthly_amount as numeric(10,2)) as monthly_amount,
    cast(created_at as timestamp) as started_at,
    cast(cancelled_at as timestamp) as cancelled_at,
    cast(updated_at as timestamp) as updated_at
from {{ source('billing_db', 'raw_subscriptions') }}
```

File: `hands-on/m02/models/staging/stg_payments.sql`
```sql
{{ config(materialized='view') }}

select
    cast(id as string) as payment_id,
    cast(subscription_id as string) as subscription_id,
    cast(amount as numeric(10,2)) as payment_amount,
    cast(status as string) as payment_status,
    cast(payment_date as timestamp) as payment_timestamp
from {{ source('billing_db', 'raw_payments') }}
```

#### Langkah 3: Layer Intermediate (Business Logic Windowing)
File: `hands-on/m02/models/intermediate/int_subscription_payments_joined.sql`
```sql
{{ config(materialized='table') }}

with subs as (
    select * from {{ ref('stg_subscriptions') }}
),

payments as (
    select * from {{ ref('stg_payments') }}
    where payment_status = 'SETTLED'
),

latest_payments as (
    select
        subscription_id,
        count(payment_id) as total_lifetime_payments,
        max(payment_timestamp) as last_successful_payment_at
    from payments
    group by 1
)

select
    s.subscription_id,
    s.customer_id,
    s.plan_name,
    s.subscription_status,
    s.monthly_amount,
    s.started_at,
    s.cancelled_at,
    s.updated_at,
    coalesce(lp.total_lifetime_payments, 0) as lifetime_payment_count,
    lp.last_successful_payment_at
from subs s
left join latest_payments lp on s.subscription_id = lp.subscription_id
```

#### Langkah 4: Layer Marts Incremental (MRR Movement Tracking)
File: `hands-on/m02/models/marts/fct_mrr_movements.sql`
```sql
{{
    config(
        materialized='incremental',
        unique_key='movement_key',
        incremental_strategy='merge',
        on_schema_change='fail'
    )
}}

with current_sub_state as (
    select * from {{ ref('int_subscription_payments_joined') }}
    {% if is_incremental() %}
        where updated_at >= (
            select timestamp_sub(max(recorded_at), interval 2 day)
            from {{ this }}
        )
    {% endif %}
),

calculated_movements as (
    select
        {{ dbt_utils.generate_surrogate_key(['subscription_id', 'updated_at']) }} as movement_key,
        subscription_id,
        customer_id,
        plan_name,
        subscription_status,
        monthly_amount as current_mrr,
        updated_at as recorded_at,
        current_timestamp() as dbt_updated_at
    from current_sub_state
)

select * from calculated_movements
```

File: `hands-on/m02/models/marts/_marts_models.yml`
```yaml
version: 2
models:
  - name: fct_mrr_movements
    description: "Tabel fakta pergerakan bulanan Monthly Recurring Revenue (MRR)."
    columns:
      - name: movement_key
        data_tests:
          - unique
          - not_null
      - name: current_mrr
        data_tests:
          - not_null
```

#### Langkah 5: Custom Singular Data Test
File: `hands-on/m02/tests/assert_positive_mrr.sql`
```sql
-- Singular test: MRR pergerakan tidak boleh bernilai negatif secara implisit tanpa status cancelling
select
    movement_key,
    current_mrr
from {{ ref('fct_mrr_movements') }}
where current_mrr < 0
```

#### Eksekusi Hands-on Pipeline
```bash
# 1. Jalankan compile verifikasi DAG
dbt compile

# 2. Jalankan build utuh (run dan test)
dbt build

# 3. Jalankan emulasi Slim CI build
dbt build --select state:modified --state ./target
```

---

### 13. Exercises

#### Level Easy
**Tugas**: Buat generic test dbt kustom bernama `assert_is_valid_email` yang memeriksa apakah kolom target mematuhi format email regex standar (`^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$`).
*Ekspektasi Output*: File macro dbt yang menerima argumen `model` dan `column_name` dan mengembalikan baris yang gagal mematuhi format tersebut.
<details>
<summary>Lihat Solusi Hint</summary>

```sql
-- macros/assert_is_valid_email.sql
{% test assert_is_valid_email(model, column_name) %}
select
    {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and not regexp_contains({{ column_name }}, r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
{% endtest %}
```
</details>

#### Level Medium
**Tugas**: Konfigurasikan snapshot dbt untuk melacak perubahan `tier` (Bronze, Silver, Gold, Platinum) pada tabel `dim_customers` menggunakan strategi `check` pada kolom `tier` dan `status`, dengan target schema bernama `snapshots`.
*Ekspektasi Output*: File `.sql` snapshot dbt valid dengan validasi `dbt_valid_to` dan `dbt_valid_from`.
<details>
<summary>Lihat Solusi Hint</summary>

```sql
-- snapshots/snp_customers.sql
{% snapshot snp_customers %}
{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='check',
      check_cols=['tier', 'status']
    )
}}
select customer_id, customer_email, tier, status from {{ ref('stg_crm__customers') }}
{% endsnapshot %}
```
</details>

#### Level Hard
**Tugas**: Rancang model dbt incremental bertipe `insert_overwrite` untuk partisi harian di Snowflake/BigQuery bernama `fct_daily_user_engagement`. Pipeline ini harus:
1. Menghitung rolling 7-day active usage window untuk setiap user.
2. Memiliki toleransi late arriving data maksimal 3 hari ke belakang.
3. Hanya mengganti partisi (*dynamic overwrite*) yang terdampak oleh window evaluasi tanpa melakukan pemindaian full historical partition.
*Ekspektasi Output*: Model SQL terkompilasi yang menggunakan konfigurasi `incremental_strategy='insert_overwrite'` dan dynamic partition targeting block.
<details>
<summary>Lihat Solusi Hint</summary>

```sql
{{
  config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={
      'field': 'activity_date',
      'data_type': 'date'
    },
    partitions=partition_list_macro() -- Macro komputasi daftar tanggal 3 hari kebelakang
  )
}}
with base_events as (
    select user_id, date(event_timestamp) as activity_date
    from {{ ref('stg_app__events') }}
    {% if is_incremental() %}
    where date(event_timestamp) >= date_sub(current_date(), interval 3 day)
    {% endif %}
)
select
    activity_date,
    user_id,
    count(*) as total_events
from base_events
group by 1, 2
```
</details>

---

### 14. Challenge

**Skenario Bisnis: Real-Time Fraud & Late-Arriving Event Reconciliation Architecture**

Sebuah unicorn fintech penyedia layanan transfer dana instan mengalami masalah inkonsistensi metrik.
- **Kondisi Sumber Data**: 
  - Data stream `transfers` masuk via pipeline CDC Debezium ke Kafka lalu ditulis ke Data Warehouse secara near real-time (mikro-batch 1 menit).
  - Status transaksi dapat berubah dari `INITIATED` -> `FRAUD_SCREENING` -> `SETTLED` atau `REJECTED` dalam rentang waktu yang bervariasi antara 2 detik hingga 14 hari (late-arriving audit bank rekanan).
  - Volume transaksi: 100 juta record baru per hari dengan sekitar 15% mutasi status yang tersebar di partisi 14 hari terakhir.
- **Batasan Sistem & Biaya**:
  - Tim Finance menuntut metrik transaksi *settled* di warehouse memiliki latensi maksimal 10 menit.
  - Tim Executive memangkas alokasi biaya komputasi warehouse sebesar 40%. Full-refresh harian dilarang keras.
  - Konsumen analitik (tim Anti-Fraud & Regulatory Reporting) membutuhkan data point-in-time state histori mutasi status transaksi untuk keperluan audit kepatuhan hukum perbankan.

**Tugas Arsitektur**:
1. Rancang arsitektur data transformation multi-tier yang mampu menangani event mutasi late-arriving hingga 14 hari tanpa melakukan table scan penuh.
2. Tentukan materialisasi dbt yang tepat pada setiap layer (Staging, Intermediate, Marts, Snapshots).
3. Deskripsikan secara spesifik bagaimana Anda mengatasi race-condition ketika record update tiba bersamaan dengan running batch dbt.
4. Buat dokumen diagram alur arsitektur teks/ASCII yang mendemonstrasikan bagaimana dbt Semantic Layer tetap membaca data valid tanpa terkena kalkulasi ganda (*double-counting*) saat status transfer bergeser dari `INITIATED` menjadi `SETTLED`.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (1 - 5)
1. **Apa perbedaan mendasar antara materialisasi `table` dan `view` pada dbt?**
   - A. View disimpan langsung di storage fisik warehouse, Table tidak.
   - B. Table dieksekusi secara instan saat dibaca client, View dikompilasi sebelumnya.
   - C. Table menyimpan data fisik terkomputasi di storage; View adalah query tersimpan yang dieksekusi on-the-fly saat diakses.
   - D. View otomatis mengimplementasikan incremental loading, Table selalu full-refresh.

2. **Perintah selector dbt manakah yang digunakan untuk mengeksekusi model `fct_orders` beserta seluruh model downstream yang bergantung padanya?**
   - A. `dbt run --select +fct_orders`
   - B. `dbt run --select fct_orders+`
   - C. `dbt run --select @fct_orders`
   - D. `dbt run --exclude fct_orders`

3. **Macro `{{ ref('model_name') }}` pada dbt memiliki fungsi utama untuk:**
   - A. Menyalin kode SQL dari model lain secara verbatim.
   - B. Menghubungkan external database via JDBC connection.
   - C. Menginterpolasi nama schema dan database secara dinamis serta membangun edge pada DAG lineage graph.
   - D. Melakukan casting tipe data secara otomatis.

4. **Kapan kondisi Jinja `{% if is_incremental() %}` mengevaluasi nilai `TRUE`?**
   - A. Setiap kali dbt run dijalankan pada mode development.
   - B. Ketika tabel target sudah ada di warehouse, materialisasi diset `incremental`, dan flag `--full-refresh` tidak digunakan.
   - C. Ketika tabel target kosong atau baru pertama kali dibuat.
   - D. Ketika dbt state memvalidasi perubahan skema di file `.yml`.

5. **Apa fungsi utama dari file `manifest.json` dalam ekosistem dbt?**
   - A. Menyimpan password dan credential database koneksi pengembang.
   - B. Menyimpan representasi lengkap topologi metadata, lineage graph, dan konfigurasi proyek hasil kompilasi.
   - C. Bertindak sebagai storage file untuk materialisasi tabel lokal.
   - D. Menggantikan file konfigurasi `dbt_project.yml`.

#### Soal Intermediate (6 - 10)
6. **Pada pemodelan Slowly Changing Dimension Type 2 (SCD2) menggunakan dbt snapshot, apa yang terjadi jika record yang dimonitor mengalami perubahan pada kolom `check_cols`?**
   - A. Record lama ditimpa (overwritten) dengan nilai baru.
   - B. Record baru ditolak dan dibuang ke log error.
   - C. Record aktif saat ini ditutup dengan mengisikan kolom `dbt_valid_to` dengan timestamp perubahan, dan baris baru di-insert dengan `dbt_valid_to = NULL`.
   - D. dbt secara otomatis menaikkan counter surrogate key berbasis sequence integer.

7. **Mengapa strategi incremental `merge` berpotensi memicu lonjakan biaya (high compute billing) pada Google BigQuery atau Snowflake jika `incremental_predicates` tidak disertakan?**
   - A. Karena warehouse harus memindai (full-scan) seluruh micro-partition tabel target untuk menemukan kecocokan `unique_key`.
   - B. Karena file manifest.json corrupt jika merge gagal.
   - C. Karena dbt membatalkan eksekusi index join pada cloud data warehouse.
   - D. Karena merge strategy secara otomatis menduplikasi baris di layer cache.

8. **Fitur Slim CI dbt memanfaatkan flag `--state` dan `state:modified`. Bagaimana mekanisme ini mengidentifikasi model yang berubah?**
   - A. Membaca commit message pada Git history.
   - B. Membandingkan hash definisi node, SQL terkompilasi, dan konfigurasi dari `manifest.json` aktif terhadap `manifest.json` referensi (produksi).
   - C. Menghitung perbedaan jumlah baris tabel fisik antara staging dan prod.
   - D. Menjalankan dry-run compilation terhadap seluruh database.

9. **Apa kegunaan dari implementasi `contract: {enforced: true}` pada model YAML dbt?**
   - A. Menjamin SLA running model selalu di bawah 5 menit.
   - B. Mengunci definisi kolom, tipe data, dan nullability; pipeline build akan gagal jika output SQL tidak sesuai dengan deklarasi skema.
   - C. Mengamankan tabel dari query delete yang dilakukan oleh unauthorized user.
   - D. Mengubah warehouse engine menjadi transactional ACID compliant secara otomatis.

10. **Apa perbedaan antara *Chasm Trap* dan *Fan-Out Trap* dalam dimensional modeling yang secara native diatasi oleh arsitektur MetricFlow pada dbt Semantic Layer?**
    - A. Chasm trap terjadi saat query membaca data binary; Fan-out trap terjadi saat storage kehabisan kapasitas partisi.
    - B. Chasm trap terjadi karena divergensi dua tabel fakta yang di-join melalui dimensi bersama; Fan-out trap terjadi karena aggregasi yang overcounting akibat join 1-to-many.
    - C. Fan-out trap hanya terjadi pada Postgres, sedangkan Chasm trap khusus BigQuery.
    - D. Keduanya adalah terminologi identik untuk mendefinisikan cyclic DAG dependencies.

#### Skenario Kasus Produksi (11 - 13)
11. **Skenario Pipeline Latency Drop**: 
Sebuah model incremental `fct_website_sessions` dijalankan setiap jam. Setelah berjalan normal selama 6 bulan, waktu pemrosesan melonjak dari 2 menit menjadi 45 menit. Model ini memiliki `unique_key='session_id'` dan difilter dengan `where session_start >= (select max(session_start) from {{ this }})`. Dari profiling database, diketahui warehouse melakukan scanning 100% partisi target. 
*Tindakan arsitektural mana yang paling tepat dan permanen untuk memperbaiki masalah ini?*
    - A. Menurunkan ukuran cluster warehouse dari 2XL ke Large untuk menghemat slot.
    - B. Mengganti `unique_key` menjadi auto-increment surrogate key dan mengubah materialisasi menjadi ephemeral.
    - C. Mengonfigurasi tabel target dengan *clustering key* berbasis `session_start` dan menyuntikkan `incremental_predicates` yang membatasi perbandingan partisi fisik target ke rentang waktu relevan.
    - D. Mengubah jadwal dbt run dari per jam menjadi sehari sekali.

12. **Skenario Silent Data Corruption**:
Pipeline dbt memproses model `dim_products` menggunakan snapshot strategy. Sumber data upstream (Postgres via Fivetran) menghapus hard-delete 50 produk yang tidak aktif lagi. Pada tabel target `dim_products` dbt snapshot, produk yang dihapus tersebut tetap berstatus `dbt_valid_to IS NULL`.
*Mengapa ini terjadi dan bagaimana konfigurasi snapshot yang tepat untuk mengatasinya?*
    - A. dbt snapshot tidak mendeteksi hard delete secara default; tambahkan konfigurasi `invalidate_hard_deletes: true` pada block snapshot config.
    - B. Fivetran gagal sinkronisasi; pipeline harus di-drop dan full-refresh.
    - C. Snapshot dbt hanya dapat digunakan untuk materialisasi table, bukan view upstream.
    - D. Ubah konfigurasi strategy dari `timestamp` menjadi `check`.

13. **Skenario CI Cost Optimization**:
Sebuah project dbt enterprise memiliki 1.800 models. Rata-rata terdapat 60 Pull Requests yang diajukan setiap hari oleh tim analis. Pipeline CI saat ini menjalankan `dbt build` secara penuh untuk setiap PR, menghabiskan biaya warehouse sebesar $300 per PR run ($18,000/hari).
*Solusi arsitektural paling efektif untuk menekan biaya minimal 75% tanpa mengurangi jaminan kualitas data adalah:*
    - A. Menonaktifkan testing pada tahap CI dan hanya menjalankan testing manual di local machine.
    - B. Mengimplementasikan Slim CI dengan command `dbt build --select state:modified+ --defer --state ./prod-artifacts` dan mengonfigurasi schema PR berbasis ephemeral/temporary schemas yang langsung di-drop pasca merge.
    - C. Membatasi pengajuan Pull Request hanya satu kali dalam seminggu untuk batch validation.
    - D. Menghapus seluruh generic test dan hanya menyisakan singular SQL tests.

---

#### Kunci Jawaban & Pembahasan Quiz

1. **C**: `table` menyimpan data fisik terhitung di persistent storage, sedangkan `view` adalah virtual query yang dihitung saat query reader dieksekusi.
2. **B**: Syntax selector trailing plus `fct_orders+` menginstruksikan dbt untuk mengeksekusi model tersebut beserta seluruh model hilir (downstream dependencies). Leading plus (`+fct_orders`) mengeksekusi upstream.
3. **C**: `ref()` mengabstraksi pemanggilan nama objek database secara dinamis sesuai environment (dev/prod) dan secara internal mendaftarkan edge dependency pada DAG lineage dbt.
4. **B**: `is_incremental()` hanya mengevaluasi `TRUE` jika tabel target sudah terbentuk di database, materialisasinya adalah `incremental`, dan flag full-refresh tidak dipicu.
5. **B**: `manifest.json` adalah core artifact dbt yang menyimpan representasi lengkap AST, lineage, konfigurasi, dan state dari seluruh node dalam proyek.
6. **C**: Mekanisme SCD2 dbt snapshot secara otomatis meng-expire record lama (`dbt_valid_to = current_timestamp`) dan memasukkan record baru dengan `dbt_valid_to IS NULL`.
7. **A**: Tanpa predicates pushdown pada tabel target internal, query planner warehouse tidak dapat melakukan micro-partition pruning sehingga harus memindai seluruh histori tabel untuk mencari match dari `unique_key`.
8. **B**: Slim CI membandingkan properti node dan compiled hash antara `manifest.json` saat ini dengan `manifest.json` dari state produksi sebelumnya untuk mengisolasi hanya node yang termodifikasi.
9. **B**: Schema Contracts memvalidasi struktur output model terhadap metadata YAML; jika terdapat tipe data atau kolom yang tidak cocok, proses kompilasi/run dbt digagalkan seketika untuk mencegah schema breaking downstream.
10. **B**: Chasm Trap timbul akibat join dua fact table melalui satu dimension table yang mendistorsi agregasi; Fan-Out Trap timbul saat agregasi dilakukan pada tabel yang terduplikasi barisnya akibat join 1-to-many.
11. **C**: Masalah warehouse full-scan pada incremental model diatasi dengan partition pruning yang dipaksa melalui `incremental_predicates` serta pengaturan clustering/partitioning key pada kolom penanda waktu target table.
12. **A**: Secara default, dbt snapshots mengabaikan record sumber yang hilang (hard-deleted). Konfigurasi `invalidate_hard_deletes: true` menginstruksikan dbt untuk mengisi `dbt_valid_to` pada record snapshot saat source primary key tidak lagi ditemukan pada source table.
13. **B**: Menggunakan Slim CI (`state:modified+`) dikombinasikan dengan mode `--defer` mengisolasi testing hanya pada node yang berubah, sementara model upstream yang tidak berubah langsung diarahkan ke schema produksi tanpa komputasi ulang.

---

### 16. Summary

- **Analytics Engineering Paradigm**: Transformasi data modern di cloud data warehouse menuntut standar disiplin software engineering: modularitas, DRY (Don't Repeat Yourself), automated testing, dan deterministic lineage via DAG.
- **Incremental Processing Mastery**: Efisiensi biaya dan latensi pipeline analitik enterprise ditentukan oleh strategi materialisasi inkremental yang tepat. Penggunaan `incremental_predicates`, lookback dynamic buffers, dan partition pruning adalah fondasi utama menekan full-table scan pada dataset skala Terabyte/Petabyte.
- **Robust Historical Lineage**: Pemanfaatan dbt snapshots (SCD Type 2) memberikan auditabilitas penuh terhadap evolusi data dimensi bisnis dari waktu ke waktu secara deklaratif dan otomatis.
- **Engineering Excellence via CI/CD**: Implementasi Slim CI berbasis state artifact comparison (`manifest.json`) memotong runtime dan biaya compute testing data hingga lebih dari 80%, mengisolasi kegagalan skema sebelum mencapai dashboard produksi.
- **Centralized Metrics Governance**: Lapisan Semantic Layer menutup celah inkonsistensi kalkulasi KPI bisnis antar platform presentasi visual, menjamin satu kebenaran definisi data (*single source of truth*) di seluruh level organisasi.