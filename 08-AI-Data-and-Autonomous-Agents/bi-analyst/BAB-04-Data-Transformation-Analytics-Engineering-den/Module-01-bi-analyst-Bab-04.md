# Bab 04: Data Transformation & Analytics Engineering dengan dbt
## Module 01: Fondasi Analytics Engineering, Arsitektur dbt, & Pemodelan Data Dimensional

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Mengonfigurasi dan Memvalidasi** arsitektur *analytics engineering* berbasis dbt Core menggunakan adapter data warehouse modern (PostgreSQL/DuckDB/Snowflake/BigQuery) secara modular dan *reproducible*.
*   **Merancang DAG (Directed Acyclic Graph)** transformasi data end-to-end dengan pemisahan dependensi layer: *Staging* (Source Conformance), *Intermediate* (Business Logic), dan *Marts* (Kimball Dimensional Modeling).
*   **Mengimplementasikan Metaprogramming Jinja** untuk abstraksi SQL yang DRY (*Don't Repeat Yourself*), pembuatan *reusable macros*, serta dynamic conditional compilation.
*   **Membangun Data Quality Assurance Otomatis** melalui kombinasi *schema generic tests* (`unique`, `not_null`, `relationships`, `accepted_values`), *singular data tests*, dan *source freshness assertions*.
*   **Mengoptimalkan Strategi Materialisasi** (*view*, *table*, *incremental*, *ephemeral*) berdasarkan volume data, frekuensi ingest, SLA latensi analitik, serta implikasi *compute cost*.

---

### 2. Concept Overview

Secara historis, alur data analitik didominasi oleh paradigma **ETL (Extract, Transform, Load)** di mana logika transformasi dieksekusi di *compute engine* terpisah (seperti Informatica, SSIS, atau Spark kustom) sebelum data masuk ke *reporting database*. Paradigma ini memicu *black box transformation*, *vendor lock-in*, serta fragmentasi definisi metrik bisnis antara *data engineer* dan *data analyst*.

Perkembangan *cloud data warehouse* (CDW) dengan arsitektur pemisahan *storage* dan *compute* (misal: BigQuery, Snowflake, Databricks, Redshift) menggeser paradigma tersebut menjadi **ELT (Extract, Load, Transform)**. 

```
[Legacy ETL]
Raw Sources -> [Extract & Transform Engine] -> Clean Warehouse Data -> BI Dashboard

[Modern ELT + Analytics Engineering]
Raw Sources -> [Extract & Load (Fivetran/Airbyte)] -> Raw Storage (ELT Base)
                                                            |
                                                     [dbt Core Engine]
                                               (Transform in-warehouse via SQL)
                                                            v
                                               Modeled Marts (Kimball)
                                                            |
                                      +---------------------+---------------------+
                                      v                                           v
                             BI / Semantic Layer                         AI Agents / LLM Tools
```

**Analytics Engineering** adalah jembatan antara *software engineering practices* dan dunia analitik. Inti dari disiplin ini adalah menerapkan metodologi rekayasa perangkat lunak modern ke dalam pipeline transformasi data:
1.  **Version Control (Git)**: Semua logika transformasi berbentuk *code* (declarative SQL).
2.  **Modularity & DRY**: Logika transformasi dipecah menjadi unit-unit atomik yang dapat dirangkai kembali tanpa duplikasi query.
3.  **Automated Testing & CI/CD**: Setiap transformasi diverifikasi integritas referensial dan validitas datanya sebelum disajikan ke downstream consumer.
4.  **Self-documenting Lineage**: Relasi antar tabel dipetakan secara otomatis dalam bentuk Directed Acyclic Graph (DAG) melalui referensi semantik (`ref()`).

Mental model utama dbt (*data build tool*) berpusat pada pernyataan deklaratif: **"Tulis query `SELECT` murni; dbt yang akan menangani boilerplate DDL/DML, dependensi eksekusi, serta orkestrasi materialisasi tabel atau view."**

---

### 3. Why It Matters

Di lingkungan enterprise kontemporer, BI Analyst sering kali menghadapi fenomena **"Spaghetti SQL"**:
*   Dashboard BI (Tableau, Power BI, Looker) berisi ratusan baris query *custom SQL* yang di-*embed* langsung di file laporan.
*   Ketika logika atribusi konversi atau kalkulasi *Gross Merchandise Value* (GMV) berubah, tim harus memodifikasi puluhan dashboard secara manual.
*   Tidak adanya visibilitas terhadap *upstream schema drift* yang menyebabkan dashboard rusak tanpa ada *alerting* dini (*silent failure*).
*   Munculnya inisiatif **AI Agents & Autonomous Analytics** (seperti LLM Text-to-SQL) menuntut adanya repositori data terstruktur dengan integritas metadata tinggi. AI Agent yang mengakses *raw data* yang belum dibersihkan akan menghasilkan halusinasi kalkulasi bisnis.

dbt memecahkan persoalan ini dengan memusatkan seluruh *business logic* ke dalam repositori kode tunggal (*Single Source of Truth*). Data disiapkan secara terstruktur, terdokumentasi, teruji, dan siap dikonsumsi baik oleh *human analyst* melalui BI Dashboard maupun oleh *autonomous agents* melalui Semantic Layer.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan dbt di dalam modern data stack:

```
+---------------------------------------------------------------------------------------------------+
| RAW DATA LAYER (EL Load Target)                                                                   |
|   raw.ecom_customers   |   raw.ecom_orders   |   raw.ecom_payments   |   raw.ecom_products        |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | [dbt source freshness & staging DAG]
                                                  v
+---------------------------------------------------------------------------------------------------+
| DBT TRANSFORMATION LAYERS                                                                         |
|                                                                                                   |
|  [Layer 1: Staging (View / Ephemeral)]                                                           |
|  - Rename kolom, cast data types, null hygiene, 1:1 mapping ke source                              |
|  - stg_customers.sql           stg_orders.sql           stg_payments.sql                          |
|                     \                |               /                                            |
|                      \               |              /                                             |
|  [Layer 2: Intermediate (Ephemeral / Table)]       /                                              |
|  - Business join kompleks, agregasi intermediate, deduplikasi                                    |
|  - int_order_items_pivoted.sql     int_customer_orders_joined.sql                                 |
|                                      |                                                            |
|                                      v                                                            |
|  [Layer 3: Marts / Dimensional Model (Table / Incremental)]                                       |
|  - Star Schema / Kimball (fct_*, dim_*)                                                           |
|       +---------------------------------------------+                                             |
|       |              fct_orders.sql                 |                                             |
|       |  (Grain: 1 baris per order yang selesai)    |                                             |
|       +---------------------------------------------+                                             |
|              |                              |                                                     |
|              v                              v                                                     |
|       +-----------------------+     +-----------------------+                                     |
|       |   dim_customers.sql   |     |   dim_products.sql    |                                     |
|       +-----------------------+     +-----------------------+                                     |
+---------------------------------------------------------------------------------------------------+
                                      |
                                      | [Exposures, Semantic Layer, Reverse ETL]
                                      v
+---------------------------------------------------------------------------------------------------+
| CONSUMPTION LAYER                                                                                 |
|   - BI Semantic Models (Power BI DirectLake, Tableau Hyper, Cube)                                 |
|   - Autonomous AI Agents (Text-to-SQL Tools, LangChain/LlamaIndex Context Engines)                |
+---------------------------------------------------------------------------------------------------+
```

#### Alur Kompilasi dbt Engine

```
[Jinja SQL Source Code] + [YAML Metadata]
             |
             v
   [dbt Compiler Engine]
             |
             +---> Memvalidasi dependensi ref() & source()
             +---> Membangun Directed Acyclic Graph (DAG) di Memory
             +---> Menginjeksikan DDL/DML Wrappers (CREATE TABLE AS / MERGE)
             |
             v
      [Compiled SQL] (Disimpan di /target/compiled)
             |
             v
 [Data Warehouse Target] (Eksekusi paralel sesuai thread setting)
             |
             v
    [manifest.json] (State artifact untuk Slim CI & Docs)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. The Directed Acyclic Graph (DAG) & Dependency Resolution
dbt tidak mengeksekusi model berdasarkan urutan nama file atau alfabetis. dbt menggunakan parser AST (Abstract Syntax Tree) internal untuk memindai fungsi `ref('<model_name>')` dan `source('<source_name>', '<table_name>')`.

*   **Topological Sorting**: dbt membangun representasi graf node-edge. Jika model $B$ memanggil `ref('A')`, dbt menetapkan edge $A \rightarrow B$. dbt memastikan tidak ada *cycle* (lingkaran setan dependensi $A \rightarrow B \rightarrow A$ yang menyebabkan kegagalan graf).
*   **Threaded Execution**: Jika node $B$ dan node $C$ sama-sama hanya bergantung pada node $A$, dbt akan mengeksekusi model $B$ dan $C$ secara konkuren/paralel menggunakan thread pool yang ditentukan pada profil koneksi (`threads: 4` atau lebih).

#### B. Mekanisme Kompilasi Jinja & Resolusi Lingkungan
Jinja memungkinkan eksekusi kode *procedural* sebelum kueri dikirimkan ke database engine. Variabel konteks utama:
*   `target.name`: Mengubah kueri berdasarkan target runtime (`dev`, `staging`, `prod`).
*   `is_incremental()`: Menghasilkan DML kondisional untuk pemrosesan berbasis delta.
*   `adapter.dispatch()`: Mengizinkan macro yang kompatibel lintas dialek SQL yang berbeda (misalnya sintaks hash pada BigQuery vs Snowflake).

#### C. Taksonomi Materialisasi (Materialization Strategies)
| Tipe Materialisasi | Mekanisme DDL / DML | Kasus Penggunaan Ideal | Trade-offs |
| :--- | :--- | :--- | :--- |
| **`view`** | `CREATE OR REPLACE VIEW target AS SELECT ...` | Layer *Staging*, layer *Intermediate* ringan | Tanpa biaya penyimpanan tambahan; performa kueri lambat jika data source masif. |
| **`table`** | `CREATE TABLE target AS SELECT ...` (atau teknik *blue-green atomic swap*) | Layer *Marts*, tabel reporting yang sering diakses BI | Kueri hilir sangat cepat; waktu build/transformasi lama seiring pertumbuhan volume data. |
| **`incremental`** | `MERGE INTO target USING (SELECT ...) ON key` | Data log, audit events, clickstream jutaan baris harian | Waktu build stabil dan cepat; membutuhkan state management & penanganan edge cases schema drift. |
| **`ephemeral`** | Tidak ada DDL/DML; diinjeksikan sebagai CTE (`WITH table AS (...)`) ke downstream | Kalkulasi matematika/string parsing yang sangat modular | Memperumit proses debugging SQL hasil kompilasi; tidak bisa diuji integritasnya langsung. |

#### D. Teori Pemodelan Dimensional (Kimball Architecture) dalam dbt
1.  **Staging (`stg_`)**: Model 1:1 terhadap tabel sumber raw. Bertugas merapikan nama kolom (snake_case), casting data types (string parsing to timestamp), dan isolasi *source engine quirks*.
2.  **Intermediate (`int_`)**: Bersifat opsional, bertugas melakukan denormalisasi awal, agregasi intermediate, dan resolusi relasi N-to-N yang kompleks sebelum masuk ke Mart final.
3.  **Fact Tables (`fct_`)**: Menyimpan representasi numerik dan pengukuran (*metrics/measures*) dari suatu proses bisnis pada granularitas (*grain*) yang didefinisikan secara eksplisit.
4.  **Dimension Tables (`dim_`)**: Menyimpan atribut kontekstual (*context/filters*) yang mendeskripsikan "siapa, apa, di mana, kapan, dan mengapa" dari peristiwa yang tercatat dalam fact table.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end analytics engineering menggunakan dbt Core untuk skenario platform E-Commerce.

#### Struktur Proyek
```text
analytics_dbt/
├── dbt_project.yml
├── packages.yml
├── macros/
│   └── generate_surrogate_key.sql
└── models/
    ├── staging/
    │   ├── sources.yml
    │   ├── stg_ecommerce__customers.sql
    │   └── stg_ecommerce__orders.sql
    └── marts/
        ├── core/
        │   ├── core.yml
        │   ├── dim_customers.sql
        │   └── fct_orders.sql
```

#### 1. `dbt_project.yml`
```yaml
name: 'ecom_analytics'
version: '1.0.0'
config-version: 2

profile: 'ecom_profile'

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]
target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  ecom_analytics:
    staging:
      +materialized: view
      +schema: staging
    marts:
      +materialized: table
      +schema: marts
      core:
        fct_orders:
          +materialized: incremental
          +unique_key: order_id
          +on_schema_change: fail
```

#### 2. `packages.yml`
```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
```

#### 3. Macro: `macros/generate_surrogate_key.sql`
Macro ini menghasilkan hash deterministik SHA-256 lintas dialect database untuk pembuatan Surrogate Key tanpa dependensi sequence database.

```sql
{% macro generate_surrogate_key(fields) %}
    {#-- Validasi input: pastikan fields berupa list non-kosong --#}
    {% if not fields or fields | length == 0 %}
        {{ exceptions.raise_compiler_error("Macro generate_surrogate_key membutuhkan minimal satu field.") }}
    {% endif %}

    {#-- Gabungkan seluruh field dengan pemisah delimiter, tangani null secara konsisten --#}
    lower(
        encode(
            digest(
                concat_ws('||',
                    {% for field in fields %}
                        coalesce(cast({{ field }} as text), '__dbt_null_sentinel__')
                        {% if not loop.last %}, {% endif %}
                    {% endfor %}
                ),
                'sha256'
            ),
            'hex'
        )
    )
{% endmacro %}
```

#### 4. Source Definition & Freshness: `models/staging/sources.yml`
```yaml
version: 2

sources:
  - name: ecom_raw
    schema: raw
    database: analytics_db
    loaded_at_field: _loaded_at
    freshness:
      warn_after: {count: 12, period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: raw_customers
        description: "Data mentah pelanggan yang diimpor dari database aplikasi transactional."
        columns:
          - name: id
            tests:
              - not_null
              - unique
      - name: raw_orders
        description: "Data transaksi penjualan e-commerce mentah."
        columns:
          - name: id
            tests:
              - not_null
              - unique
          - name: customer_id
          - name: order_status
```

#### 5. Staging Model: `models/staging/stg_ecommerce__customers.sql`
```sql
with source as (
    select * from {{ source('ecom_raw', 'raw_customers') }}
),

renamed as (
    select
        -- Identifiers
        cast(id as bigint) as customer_id,
        
        -- Attributes
        trim(cast(first_name as text)) as first_name,
        trim(cast(last_name as text)) as last_name,
        lower(trim(cast(email as text))) as email_address,
        
        -- Timestamps with standard timezone UTC
        cast(created_at as timestamp with time zone) as registered_at_utc,
        cast(_loaded_at as timestamp with time zone) as ingested_at_utc

    from source
)

select * from renamed
```

#### 6. Staging Model: `models/staging/stg_ecommerce__orders.sql`
```sql
with source as (
    select * from {{ source('ecom_raw', 'raw_orders') }}
),

renamed as (
    select
        -- Identifiers
        cast(id as bigint) as order_id,
        cast(customer_id as bigint) as customer_id,
        
        -- Measures / Currency (Transformasi ke cent/satuan basis untuk hindari floating point issue)
        cast(order_amount as numeric(18, 4)) as total_order_amount,
        cast(tax_amount as numeric(18, 4)) as total_tax_amount,
        
        -- Categorical Attributes
        lower(trim(cast(order_status as text))) as order_status,
        
        -- Timestamps
        cast(ordered_at as timestamp with time zone) as ordered_at_utc,
        cast(_loaded_at as timestamp with time zone) as ingested_at_utc

    from source
)

select * from renamed
```

#### 7. Dimensional Mart: `models/marts/core/dim_customers.sql`
```sql
with customers as (
    select * from {{ ref('stg_ecommerce__customers') }}
),

orders as (
    select * from {{ ref('stg_ecommerce__orders') }}
),

customer_order_aggregates as (
    select
        customer_id,
        min(ordered_at_utc) as first_order_date,
        max(ordered_at_utc) as most_recent_order_date,
        count(distinct order_id) as total_lifetime_orders,
        sum(case when order_status = 'completed' then total_order_amount else 0 end) as total_lifetime_value
    from orders
    group by customer_id
),

final as (
    select
        -- Surrogate Key
        {{ generate_surrogate_key(['c.customer_id']) }} as customer_sk,
        
        -- Natural Keys
        c.customer_id,
        
        -- Dimension Attributes
        c.first_name,
        c.last_name,
        c.email_address,
        c.registered_at_utc,
        
        -- Behavioral Metrics (Kimball Degenerate / Sourced Facts)
        coalesce(coa.total_lifetime_orders, 0) as total_lifetime_orders,
        coalesce(coa.total_lifetime_value, 0) as total_lifetime_value,
        coa.first_order_date,
        coa.most_recent_order_date,
        
        case 
            when coa.total_lifetime_orders > 0 then true 
            else false 
        end as is_paying_customer

    from customers c
    left join customer_order_aggregates coa 
        on c.customer_id = coa.customer_id
)

select * from final
```

#### 8. Fact Mart Incremental: `models/marts/core/fct_orders.sql`
```sql
{{
    config(
        materialized='incremental',
        unique_key='order_id',
        on_schema_change='fail'
    )
}}

with orders as (
    select * from {{ ref('stg_ecommerce__orders') }}
    {% if is_incremental() %}
        -- Filter delta window: hanya proses order baru atau yang termutasi sejak eksekusi run terakhir.
        -- Gunakan margin lookback (contoh: 3 hari) untuk menampung late-arriving events.
        where ingested_at_utc >= (
            select coalesce(max(ingested_at_utc), '1970-01-01'::timestamp with time zone) - interval '3 days'
            from {{ this }}
        )
    {% endif %}
),

customers as (
    select customer_sk, customer_id from {{ ref('dim_customers') }}
),

final as (
    select
        -- Primary Surrogate Key untuk Fact Table
        {{ generate_surrogate_key(['o.order_id']) }} as order_sk,
        
        -- Foreign Key ke Dimensi
        coalesce(c.customer_sk, {{ generate_surrogate_key(["'-1'"]) }}) as customer_sk,
        
        -- Natural / Degenerate Identifiers
        o.order_id,
        o.customer_id,
        o.order_status,
        
        -- Temporal Dimensions
        o.ordered_at_utc,
        o.ingested_at_utc,
        
        -- Additive Fact Measures
        o.total_order_amount,
        o.total_tax_amount,
        (o.total_order_amount - o.total_tax_amount) as net_order_amount

    from orders o
    left join customers c
        on o.customer_id = c.customer_id
)

select * from final
```

#### 9. Schema Testing & Documentation: `models/marts/core/core.yml`
```yaml
version: 2

models:
  - name: dim_customers
    description: "Tabel dimensi sentral pelanggan berisikan riwayat registrasi dan metrik agregasi lifetime."
    columns:
      - name: customer_sk
        description: "Surrogate Key SHA-256 yang merepresentasikan entitas pelanggan."
        tests:
          - unique
          - not_null
      - name: customer_id
        description: "Natural key dari sistem transaksi sumber."
        tests:
          - unique
          - not_null
      - name: total_lifetime_orders
        description: "Total akumulasi order yang pernah dilakukan customer."
        tests:
          - not_null

  - name: fct_orders
    description: "Tabel fakta transaksional tingkat pesanan (grain: 1 order per baris)."
    columns:
      - name: order_sk
        description: "Surrogate Key SHA-256 untuk order."
        tests:
          - unique
          - not_null
      - name: customer_sk
        description: "Foreign key yang menghubungkan pesanan ke tabel dim_customers."
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_sk
      - name: order_status
        description: "Status terkini pesanan."
        tests:
          - accepted_values:
              values: ['placed', 'shipped', 'completed', 'returned', 'cancelled']
      - name: total_order_amount
        description: "Nilai kotor total transaksi pemesanan."
        tests:
          - not_null
```

---

### 7. Edge Cases & Failure Modes

*   **Late-Arriving Dimensions / Facts**: Transaksi (`fct_orders`) masuk ke pipeline sebelum entitas pelanggan (`dim_customers`) selesai diekstrak dari sumber.
    *   *Mitigasi*: Gunakan *unknown member record* dengan Surrogate Key deterministik `-1` (seperti diterapkan pada `coalesce(c.customer_sk, {{ generate_surrogate_key(["'-1'"]) }})`). Faktanya tetap tercatat tanpa melanggar *not_null constraints*.
*   **Upstream Schema Drift**: Perubahan tipe data (misal `id` dari `int` ke `varchar`) atau *renaming* kolom pada layer raw.
    *   *Mitigasi*: Konfigurasi `on_schema_change: fail` pada model inkremental untuk mencegah penulisan data korup. Tangani mutasi secara eksplisit di Staging layer sebelum diteruskan ke Marts.
*   **Timestamp Precision & Timezone Drift**: Ketidaksesuaian timezone (UTC vs local TZ) antar berbagai tabel raw yang menyebabkan kegagalan partisi atau perhitungan metrik harian salah.
    *   *Mitigasi*: Wajibkan konversi eksplisit ke `TIMESTAMP WITH TIME ZONE` (UTC) di Staging layer.
*   **Incremental Sync Drift akibat Hard Deletes**: Record dihapus di transactional database, namun model incremental dbt hanya membaca record baru/terupdate, sehingga data yang dihapus tetap tersimpan di DW.
    *   *Mitigasi*: Implementasikan *Soft Deletes* di transactional system (`is_deleted = TRUE`), atau jadwalkan berkala eksekusi full refresh (`dbt run --full-refresh --select fct_orders`) pada periode *low-traffic* mingguan.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Evaluasi | dbt Core | SQLMesh | Coalesce.io | Pure Airflow + Stored Procedures |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | ELT berbasis deklaratif SQL + Jinja compilation. | ELT berbasis Virtual Data Environments & Semantic Plan. | GUI-driven ELT berbasis metadata (Snowflake-first). | Prosedural, SQL dieksekusi via `PythonOperator` / DBA scripts. |
| **Developer Experience** | Berbasis CLI & code-centric, ekosistem package komunitas sangat luas. | CLI canggih dengan dynamic environment tagging. | Web-based visual modeling (ramah bagi low-code analyst). | Manual; minim testing framework bawaan, high mental burden. |
| **Data Testing & Lineage** | Out-of-the-box via YAML, Jinja tests, dan DAG extraction otomatis. | Built-in data unit testing, automated virtual staging tests. | Otomatis dari GUI dependency builder. | Harus dibangun kustom via script PyTest / Great Expectations terpisah. |
| **Kelemahan Utama** | *State management* multi-developer membutuhkan konfigurasi storage backend. | Komunitas masih berkembang; learning curve sintaks baru. | Proprietary vendor lock-in, biaya lisensi enterprise tinggi. | Maintenance tinggi (*spaghetti code*), tidak ada automated lineage DAG. |

---

### 9. Best Practices & Standard Industri

*   **Aturan Struktur Layering (Naming Conventions)**:
    *   `stg_[source]__[entity].sql`: Membersihkan, standardisasi nama, dan casting (hanya membaca `source()`).
    *   `int_[entity]__[transformation_logic].sql`: Intermediate joins & denormalisasi bisnis (membaca `ref('stg_...')`).
    *   `fct_[business_process].sql` / `dim_[entity].sql`: Final dimensional data marts (membaca `ref('int_...')` atau `ref('stg_...')`).
*   **Pola Desain SQL (CTE-Only Pattern)**:
    Hindari subqueries bertingkat. Gunakan CTE (Common Table Expressions) secara modular:
    1.  *Import CTEs*: Ambil seluruh dependensi `ref()` atau `source()` di awal query.
    2.  *Logical CTEs*: Jalankan transformasi dan manipulasi data per blok fungsional.
    3.  *Final CTE*: Gabungkan semua hasil transformasi.
    4.  *Final Query*: Selalu diakhiri dengan `select * from final`.
*   **Surrogate Keys vs Natural Keys**:
    Gunakan selalu Surrogate Key berbasis *deterministic cryptographic hashing* (MD5/SHA256) pada layer Dimensional Marts. Ini mengisolasi sistem analitik dari perubahan primary key pada transactional database.
*   **Automated Slim CI via State Deferral**:
    Di pipeline CI/CD GitHub Actions / GitLab CI, jangan lakukan full-build ke seluruh DAG. Bandingkan `manifest.json` dari production terhadap pull request:
    ```bash
    dbt run --select state:modified+ --defer --state path/to/prod/artifacts
    dbt test --select state:modified+ --defer --state path/to/prod/artifacts
    ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Lead Analytics Engineer di sebuah perusahaan retail online. Tim BI melaporkan bahwa data metrik revenue sering tidak akurat karena adanya record duplikat dan kegagalan casting mata uang pada raw data. Anda diminta membangun pipeline transformasi dbt lokal menggunakan DuckDB.

#### Langkah 1: Persiapan Environment
Pasang dbt-duckdb di environment python lokal Anda:
```bash
python3 -m venv dbt-env
source dbt-env/bin/activate
pip install dbt-core==1.7.0 dbt-duckdb==1.7.0
```

Inisialisasi profil dbt pada `~/.dbt/profiles.yml`:
```yaml
ecom_profile:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ./analytics.duckdb
      threads: 4
```

#### Langkah 2: Setup Seed Data Mentah
Buat file `seeds/raw_customers.csv`:
```csv
id,first_name,last_name,email,created_at
101,John,Doe,john.doe@example.com,2023-01-15 08:30:00
102,Jane,Smith,jane.smith@example.com,2023-02-10 11:15:00
103,Bob,Marley,bob.marley@example.com,2023-03-01 14:00:00
```

Buat file `seeds/raw_orders.csv`:
```csv
id,customer_id,order_amount,tax_amount,order_status,ordered_at
5001,101,150.00,15.00,completed,2023-03-05 10:00:00
5002,101,80.50,8.05,completed,2023-03-10 12:30:00
5003,102,200.00,20.00,placed,2023-03-12 09:45:00
5004,103,50.00,5.00,returned,2023-03-15 16:20:00
```

Load file CSV ke DuckDB sebagai raw table:
```bash
dbt seed
```

#### Langkah 3: Eksekusi Kompilasi & Transformasi DAG
Jalankan kompilasi untuk memastikan dependensi terpetakan dengan benar:
```bash
dbt compile
```

Eksekusi pembentukan tabel staging dan marts:
```bash
dbt run
```

*Expected output logging*:
```text
Running with dbt=1.7.0
Registered adapter: duckdb=1.7.0
Found 4 models, 2 seeds, 6 data tests

Concurrency: 4 threads (target='dev')

1 of 4 START sql view model dev.stg_ecommerce__customers ................. [RUN]
2 of 4 START sql view model dev.stg_ecommerce__orders .................... [RUN]
1 of 4 OK created sql view model dev.stg_ecommerce__customers ............ [OK in 0.08s]
2 of 4 OK created sql view model dev.stg_ecommerce__orders ............... [OK in 0.08s]
3 of 4 START sql table model dev.dim_customers ........................... [RUN]
3 of 4 OK created sql table model dev.dim_customers ...................... [OK in 0.12s]
4 of 4 START sql incremental model dev.fct_orders ........................ [RUN]
4 of 4 OK created sql incremental model dev.fct_orders ................... [OK in 0.14s]

Finished running 2 view models, 1 table model, 1 incremental model in 0.45s.
Completed successfully
```

#### Langkah 4: Menjalankan Assertion & Schema Test
Verifikasi integritas struktur database:
```bash
dbt test
```

*Expected output logging*:
```text
Concurrency: 4 threads (target='dev')

1 of 6 START test not_null_dim_customers_customer_sk ..................... [RUN]
2 of 6 START test unique_dim_customers_customer_sk ....................... [RUN]
3 of 6 START test not_null_fct_orders_order_sk ........................... [RUN]
4 of 6 START test unique_fct_orders_order_sk ............................. [RUN]
5 of 6 START test relationships_fct_orders_customer_sk__customer_sk ...... [RUN]
6 of 6 START test accepted_values_fct_orders_order_status ................ [RUN]
1 of 6 PASS not_null_dim_customers_customer_sk ........................... [PASS in 0.05s]
2 of 6 PASS unique_dim_customers_customer_sk ............................. [PASS in 0.05s]
3 of 6 PASS not_null_fct_orders_order_sk ................................. [PASS in 0.04s]
4 of 6 PASS unique_fct_orders_order_sk ................................... [PASS in 0.04s]
5 of 6 PASS relationships_fct_orders_customer_sk__customer_sk ............ [PASS in 0.06s]
6 of 6 PASS accepted_values_fct_orders_order_status ...................... [PASS in 0.05s]

Finished running 6 tests in 0.18s.
All checks passed!
```

#### Langkah 5: Inspeksi Dokumentasi Interaktif & Lineage Graph
Generate artefak metadata dan luncurkan web interface dbt docs:
```bash
dbt docs generate
dbt docs serve --port 8080
```
Buka browser pada `http://localhost:8080` dan periksa visualisasi Directed Acyclic Graph (DAG) untuk memvalidasi aliran data dari seed mentah, melewati layer staging, hingga membentuk *Star Schema* di dimensional marts. Pipeline ini sekarang sepenuhnya terisolasi, teruji, dan siap melayani downstream dashboards maupun context lookup dari LLM autonomous agents.