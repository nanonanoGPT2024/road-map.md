# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (BI Analyst & BI Engineering)

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Semantic Layer Enterprise**: Mengimplementasikan *Single Source of Truth* (SSOT) terpusat menggunakan dbt Semantic Layer / MetricFlow dan semantic engine modern untuk menjembatani *data warehouse* dengan layer konsumsi (BI, AI Agents, Reverse ETL).
- **Mengeksekusi Pemodelan Data Skala Besar**: Memilih dan mengimplementasikan secara tepat antara *Kimball Dimensional Modeling* (Star/Snowflake Schema, SCD Type 2) versus *One Big Table* (OBT) berbasis columnar storage untuk mengoptimalkan performa kueri analitik.
- **Mengoptimalkan Query Engine & Data Virtualization**: Menganalisis *execution plan*, mengelola *partitioning*, *clustering*, dan strategi *pre-aggregation/caching* (MOLAP vs. ROLAP modern) pada cloud data platform (Snowflake, BigQuery, ClickHouse).
- **Membangun Pipeline BI-Ready & AI-Ready**: Mengintegrasikan *Data Contracts*, *Data Quality Framework* (Great Expectations, dbt tests), serta antarmuka metadata terstandarisasi untuk konsumsi *Autonomous Agentic Text-to-SQL*.
- **Menerapkan FinOps & Production Observability**: Mengaudit *compute cost*, *data freshness SLA*, dan *query latency* untuk menjaga throughput sistem BI pada skala multi-terabyte tanpa pembengkakan biaya infrastruktur.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Advanced SQL**: Window functions (`LEAD`, `LAG`, `ROW_NUMBER`, `DENSE_RANK`), CTE rekursif, optimasi operator `JOIN`, dan agregasi analitik (`GROUPING SETS`, `CUBE`, `ROLLUP`).
- **Data Warehousing Fundamentals**: Pemahaman OLTP vs. OLAP, *fact tables*, *dimension tables*, *surrogate keys*, serta siklus hidup ELT/ETL.
- **Foundational dbt (data build tool)**: Konsep dasar `models`, `sources`, `seeds`, dan Jinja templating.
- **Command Line & Git**: Navigasi terminal Linux, Git workflow (*branching*, *pull requests*, CI/CD pipelines).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Evolusi Arsitektur BI: Dari Silo Monolitik ke Semantic Decoupling
Arsitektur Business Intelligence generasi awal mengikat layer semantik (definisi metrik, hierarki, kalkulasi laba/rugi) langsung di dalam alat visualisasi proprietary (misalnya: calculated fields di Tableau Desktop, DAX di Power BI). Hal ini menyebabkan masalah kritis:
1. **Metric Drift**: Metrik `Gross Revenue` di finance dashboard menghasilkan angka berbeda dengan `Gross Revenue` di marketing report karena logika filter berbeda di masing-masing UI BI tool.
2. **AI Agent Incompatibility**: Autonomous LLM Agents tidak dapat membaca logic yang terenkapsulasi di dalam file proprietary `.pbix` atau `.twbx`.

Solusi modern mengadopsi **Decoupled Semantic Architecture**:

```
+---------------------------------------------------------------------------------+
|                              CONSUMPTION LAYER                                  |
|   +--------------------+   +---------------------+   +----------------------+   |
|   | Dashboard (BI Tool)|   | AI Agents (LLM/SQL) |   | Reverse ETL (Hubspot)|   |
|   +---------+----------+   +----------+----------+   +----------+-----------+   |
+-------------|-------------------------|-------------------------|---------------+
              |                         |                         |
              +-------------------------v-------------------------+
                                        | (SQL / REST / GraphQL)
+---------------------------------------v-----------------------------------------+
|                    ENTERPRISE SEMANTIC LAYER (MetricFlow / Cube)                |
|  - Shared Metric Definitions (MRR, Churn, LTV)                                 |
|  - Join Graphs & Dimensional Hierarchies                                        |
|  - Role-Based Access Control (RBAC) & Dynamic Data Masking                      |
|  - Query Acceleration / Materialization Routing (Pre-aggregations)              |
+---------------------------------------+-----------------------------------------+
                                        | (Optimized SQL Pushdown)
+---------------------------------------v-----------------------------------------+
|                  CLOUD DATA PLATFORM (Gold Layer / Marts)                       |
|   - Fact Tables (Transaction, Snapshots)                                        |
|   - Dimension Tables (SCD Type 1 & 2, Degenerate, Conformed)                    |
|   - Storage Engine: Parquet/ORC via Snowflake, BigQuery, ClickHouse             |
+---------------------------------------------------------------------------------+
```

### 3.2 Deep Dive: Kimball vs. One Big Table (OBT) pada Columnar Storage
Dalam sistem RDBMS berbasis baris (*row-oriented* seperti PostgreSQL/MySQL klasik), Kimball Dimensional Modeling (bintang/kepingan salju) adalah standar mutlak untuk meminimalkan redundansi data melalui normalisasi dimensi.

Namun, pada **Modern Columnar Storage** (Snowflake, BigQuery, ClickHouse, DuckDB):
- **Columnar Pruning**: Mesin hanya memindai (*scan*) kolom yang didefinisikan dalam klausa `SELECT` dan `WHERE`.
- **Vectorized Execution**: Operasi analitik dieksekusi menggunakan instruksi SIMD (Single Instruction, Multiple Data) langsung di CPU register cache.
- **Kompresi Tinggi**: Kolom dengan kardinalitas rendah hingga menengah terkompresi secara masif melalui Run-Length Encoding (RLE) atau Dictionary Encoding.

#### Perbandingan Struktural:
1. **Kimball Star Schema**:
   - *Kelebihan*: Sangat modular; dimensi terkonformasi (*conformed dimensions*) dapat digunakan lintas multi-fact; jejak audit historis (SCD Type 2) sangat presisi.
   - *Kekurangan*: Memerlukan *multi-table joins* berulang-ulang yang membebani *shuffle phase* pada sistem komputasi terdistribusi jika volume data mencapai miliaran baris.
2. **One Big Table (OBT)**:
   - *Kelebihan*: Zero-join queries; latensi read kueri analitik dashboard sangat rendah; ideal untuk layer presentasi BI performa tinggi.
   - *Kekurangan*: Pipeline ingestion/denormalisasi kompleks; risiko inkonsistensi atribut dimensi tinggi jika update parsial terjadi; ukuran storage disk meningkat (meskipun termitigasi oleh kompresi kolom).

**Arsitektur Standar Industri**: Terapkan Kimball di level **Silver/Gold Mart Core**, lalu transformasikan menjadi **OBT ter-materialisasi** atau manfaatkan **Semantic Layer Caching** di level **Presentation Layer**.

### 3.3 Semantic Layer Engine: Dynamic Join Graph & Fan-out Prevention
Tantangan terbesar kalkulasi metrik analitik adalah **Chasm Trap** dan **Fan-out Trap**:
- **Fan-out Trap**: Terjadi ketika tabel fakta dengan granularitas lebih tinggi di-join ke tabel fakta lain melalui tabel dimensi bersama, menghasilkan replikasi baris agregasi (misalnya: 1 Order memiliki 5 Order Items, melakukan `SUM(Order.amount)` setelah di-join dengan `order_items` akan melipatgandakan nilai amount sebesar 5x).
- **Metric Engine Resolution**: Semantic layer engine memisahkan definisi metrik dari storage fisik. Engine menghasilkan SQL dengan kueri terisolasi (*sub-queries* atau CTE) per granularitas, kemudian menggabungkan hasilnya (*Coalescing / Stitching*) pada dimensi yang diminta:

$$\text{SQL Engine Flow: } Q_{\text{metrics}} = \text{Stitch}\Big(CTE_1(\text{Orders}), CTE_2(\text{Order Items})\Big) \text{ ON Dimension}$$

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy BI) | Pendekatan Enterprise Modern (Metrics-First BI) |
| :--- | :--- | :--- |
| **Logic Storage** | Tertanam di file BI visual (.pbix, Tableau Data Source). | Didefinisikan secara deklaratif di Git (`code-first` via YAML/SQL). |
| **Konsistensi Metrik**| *High divergence*; beda departemen beda hasil formula. | *Absolute SSOT*; satu definisi digunakan dashboard, API, dan AI agents. |
| **Testing & CI/CD** | Manual check; validasi pasca-rilis dashboard. | *Shift-left*; Automated Data Quality gates via CI pada Pull Request. |
| **Interaksi AI** | Terbatas pada Natural Language generation statis. | AI Autonomous Agents dapat memanggil Semantic API via standard schema. |
| **Skalabilitas Biaya**| Menambah warehouse size tanpa optimasi query plan. | Partisi cerdas, clustering keys, dan pre-aggregation routing. |

---

## 5. How (Workflow Detail)

Alur kerja implementasi BI dari raw ingestion hingga konsumsi AI:

```
[ Ingestion Layer ] (Fivetran/Airbyte/Kafka)
       │
       ▼
[ Bronze Layer (Raw) ] (Immutable, Schema-on-write / Append-only)
       │
       ▼
[ Silver Layer (Normalized / Cleansed) ] (dbt Transform: Typecasting, Deduplication, Data Contracts)
       │
       ▼
[ Gold Layer (Kimball Dimensional Models) ] (Fact & Conformed Dimensions, SCD2 Tracking)
       │
       ▼
[ Enterprise Semantic Layer ] (YAML Specs: MetricFlow, Cube.js, dbt Semantic)
       │
       ├── Cache Hit (Pre-aggregations) ──► Sub-second Response
       └── Cache Miss ───────────────────► SQL Pushdown to Warehouse
       │
       ▼
[ Consumption: Superset / Metabase / AI Text-to-SQL Agents / Reverse ETL ]
```

### Langkah Tahapan Eksekusi:
1. **Contract Enforcement**: Terapkan *Data Contract* pada Silver staging model untuk menjamin tipe data dan batasan *nullability*.
2. **Kimball Engineering**: Bangun dimensional model di Gold Layer menggunakan dbt. Gunakan surrogate keys deterministik berbasis hash (misalnya `MD5` atau `SHA256`).
3. **Semantic Modeling**: Tulis definisi semantik deklaratif (Entities, Dimensions, Measures, Metrics) dalam format YAML.
4. **Acceleration Configuration**: Konfigurasi partisi data mart berdasarkan timestamp (misal: `order_date`) dan clustering berdasarkan dimensi yang sering difilter (misal: `tenant_id`, `country_code`).
5. **Interface Activation**: Sambungkan UI BI dan endpoint AI Agent ke Semantic Engine via antarmuka SQL/GraphQL terpadu.

---

## 6. Analogy & Diagram ASCII

### Analogi: Semantic Layer sebagai "Kepala Pelayan Restoran Bintang Lima"
- **Dapur (Data Warehouse)**: Memiliki ratusan bahan mentah, bumbu, panci, dan pisau (raw tables, complex joins, nested arrays).
- **Tamu (End User / BI User / AI Agent)**: Ingin hidangan jadi: "Bawakan saya Profit Q3 per Region". Tamu tidak perlu tahu cara memotong bawang atau suhu penggorengan.
- **Pelayan (Semantic Layer)**: Menerima pesanan, menerjemahkannya ke resep baku dapur (*standardized metric code*), mengecek apakah menu sudah siap saji di *warming tray* (*pre-aggregation cache*), dan memastikan tamu tidak salah makan racun (*fan-out prevention / data masking*).

```
+-------------------------------------------------------------------------------+
|                           FAN-OUT TRAP PREVENTION                             |
+-------------------------------------------------------------------------------+

  [SALES FACT]                  [TARGET FACT]
  Date: 2024-01-01              Date: 2024-01-01
  Sales_ID: 101                 Target_Amount: $5,000
  Amount: $1,000
  ----------------
  Sales_ID: 102
  Amount: $2,000

               NAIVE JOIN (SALES <-> TARGET ON Date)
  +------------+----------+--------------+------------------+
  | Date       | Sales_ID | Sales_Amount | Target_Amount    |
  +------------+----------+--------------+------------------+
  | 2024-01-01 | 101      | $1,000       | $5,000           |
  | 2024-01-01 | 102      | $2,000       | $5,000 (DUPLIKAT)|
  +------------+----------+--------------+------------------+
  SUM(Sales_Amount)  = $3,000 (BENAR)
  SUM(Target_Amount) = $10,000 (SALAH BESAR! Terjadi Penggandaan)

               SEMANTIC LAYER RESOLUTION (Stitched Query)
  +--------------------------------+   +----------------------------------+
  | CTE 1: Aggregate Sales         |   | CTE 2: Aggregate Target          |
  | Date: 2024-01-01               |   | Date: 2024-01-01                 |
  | Total_Sales = $3,000           |   | Total_Target = $5,000            |
  +---------------+----------------+   +----------------+-----------------+
                  \                                    /
                   \                                  /
                    FULL OUTER JOIN ON Date: 2024-01-01
                                    │
                                    ▼
       Total_Sales = $3,000 | Total_Target = $5,000 (BENAR & PRESISI)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: SCD Type 2 Implementation di SQL (Gold Layer Dimension)
Contoh query analitik untuk mempertahankan riwayat status keanggotaan pelanggan tanpa menimpa (*overwrite*) data lama:

```sql
-- DDL & Sample Query: Customer Dimension Snapshot (SCD Type 2)
CREATE TABLE dim_customers_scd2 (
    customer_sk VARCHAR(64) PRIMARY KEY, -- Hash(customer_id + valid_from)
    customer_id INT NOT NULL,
    customer_tier VARCHAR(20) NOT NULL,
    country VARCHAR(50) NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NULL,
    is_current BOOLEAN NOT NULL
);

-- Kueri analitik BI: Mengambil profil customer pada tanggal spesifik transaksi
SELECT 
    f.order_id,
    f.order_timestamp,
    f.amount,
    d.customer_tier,
    d.country
FROM fact_orders f
INNER JOIN dim_customers_scd2 d 
    ON f.customer_id = d.customer_id
    AND f.order_timestamp >= d.valid_from 
    AND (f.order_timestamp < d.valid_to OR d.valid_to IS NULL);
```

### 7.2 Practical Example: Enterprise Semantic Layer Spec (dbt MetricFlow)
File: `models/semantic/metricflow_sales.yml`

```yaml
version: 2

semantic_models:
  - name: semantic_orders
    model: ref('fct_orders')
    description: "Tabel fakta transaksi penjualan terverifikasi di level transaksi order."
    
    entities:
      - name: order_id
        type: primary
      - name: customer_id
        type: foreign
        
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
      - name: order_status
        type: categorical
      - name: is_cancelled
        type: categorical
        expr: "CASE WHEN order_status = 'CANCELLED' THEN TRUE ELSE FALSE END"

    measures:
      - name: gross_amount
        description: "Total nilai transaksi sebelum diskon dan pajak."
        agg: sum
        expr: order_amount_usd
      - name: order_count
        description: "Jumlah unit order unik."
        agg: count_distinct
        expr: order_id
      - name: average_transaction_value
        description: "Rata-rata gross order value."
        agg: average
        expr: order_amount_usd

metrics:
  - name: total_gross_revenue
    description: "Gross revenue resmi perusahaan di luar transaksi yang dibatalkan."
    type: simple
    type_params:
      measure: gross_amount
    filter: |
      {{ Dimension('order_id__is_cancelled') }} = FALSE

  - name: average_order_value
    description: "Rata-rata gross revenue per transaksi sukses."
    type: ratio
    type_params:
      numerator: total_gross_revenue
      denominator: valid_order_count

  - name: valid_order_count
    description: "Jumlah order non-cancelled."
    type: simple
    type_params:
      measure: order_count
    filter: |
      {{ Dimension('order_id__is_cancelled') }} = FALSE
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: Global FinTech Platform "PaySphere"
- **Skala Data**: 80 juta transaksi per hari (~150 GB data baru/hari).
- **Platform**: Data Warehouse Snowflake (Multi-Cluster Warehouse) + dbt Core + Semantic Layer Engine.
- **Masalah Utama**:
  1. *Dashboard Latency*: Pimpinan cabang mengeluhkan loading dashboard P&L memakan waktu 45-90 detik.
  2. *High Compute Bill*: Biaya Snowflake meningkat drastis menjadi $65,000/bulan akibat full scan berulang pada tabel 5 miliar baris.
  3. *Inconsistent Definitions*: Divisi Risk menyatakan Fraud Rate sebesar 0.42%, sementara Operation menyatakan 0.65% karena perbedaan penanganan transaksi *chargeback*.

### Solusi Rekayasa & Arsitektur:
1. **Partisi & Search Optimization Service**:
   - Menata ulang tabel fakta `fact_transactions` dengan clustering keys: `CLUSTER BY (DATE_TRUNC('MONTH', transaction_time), tenant_id)`.
2. **Implementasi Semantic Pre-Aggregation Routing**:
   - Membangun *Dynamic Aggregates* di semantic layer. Kueri dengan granularitas harian atau bulanan secara otomatis dialihkan ke agregasi pre-kalkulasi (*rollup tables*), melewati raw fact 5 miliar baris.
3. **Data Contract & Central Metric Standardization**:
   - Mendefinisikan metrik `fraud_rate` secara formal di Semantic Layer:
     $$\text{Fraud Rate} = \frac{\text{Count of Confirmed Fraudulent Transactions}}{\text{Total Valid Cleared Transactions}}$$
   - Menerapkan automated continuous integration (CI) test: setiap pull request yang memodifikasi formula metrik wajib lulus uji komparasi data regresi historis.

### Hasil (Benchmarking Pasca-Implementasi):
- **Dashboard Response Time**: P95 turun dari **68 detik** ke **1.8 detik** (97.3% percepatan).
- **FinOps Optimization**: Konsumsi Snowflake credits turun 54%, menghasilkan penghematan bulanan sebesar **$35,100**.
- **Metric Consistency**: 100% keselarasan data fraud rate antara tim Risk, Tim Operation, dan AI Fraud Investigator Agent.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
             [ PRE-AGGREGATION / CUBE ]
                    ▲
                   / \
                  /   \  Cost Efficiency vs. Freshness
                 /     \
                /       \
  [ REAL-TIME OBT ] <───> [ KIMBALL STAR SCHEMA ]
    (High Storage Cost,      (High Compute Shuffle,
     Low Query Latency)       Modular, Lower Storage)
```

| Pendekatan | Latensi Kueri | Biaya Komputasi Kueri | Biaya Storage & Build | Kompleksitas Maintenance | Best Used For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kimball Star Schema (Pure ROLAP)** | Sedang - Tinggi (5s - 60s) | Tinggi (Scan + Shuffling join berulang) | Rendah (Ternormalisasi) | Sedang | *Ad-hoc slice & dice analysis*, eksplorasi data mendalam |
| **One Big Table (OBT Ter-denormalisasi)** | Sangat Rendah (< 3s) | Rendah (Zero join, sequential scan) | Tinggi (Duplikasi data string/dimensi) | Rendah | Dashboard eksekutif spesifik, feeding langsung ke ML engine |
| **Semantic Layer Pre-Aggregation (MOLAP Virtual)** | Ultra Rendah (< 500ms) | Terkendali (Query hit cache/rollup) | Sedang (Biaya pre-build rollup tables) | Tinggi (Manajemen invalidasi cache) | High-concurrency BI user base, public-facing embedded analytics |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Fan-out Trap / Duplikasi Akibat 1-to-Many Join
- **Gejala**: Angka metrik pendapatan (*revenue*) melonjak drastis setelah menambahkan dimensi baru seperti `payment_method` atau `shipping_item`.
- **Root Cause**: Kardinalitas 1 order memiliki multi payment method atau multi delivery attempt. Join menyebabkan baris order berlipat ganda.
- **Troubleshooting & Fix**:
  1. Identifikasi *primary grain* dari setiap model.
  2. Jangan join tabel transaksi langsung ke dimension yang memiliki relasi many-to-many tanpa jembatan (*bridge table*) atau tanpa pra-agregasi.
  3. Lakukan kalkulasi metrik via `COUNT(DISTINCT ...)` atau manfaatkan sub-query/CTE sebelum melakukan operasi join.

### 10.2 Cache Invalidation Storm
- **Gejala**: Dashboard mendadak timeout setiap pukul 08:00 pagi bersamaan dengan data warehouse spike 100% CPU.
- **Root Cause**: Semua tabel pre-aggregation di-invalidate secara serempak saat cron data ingestion selesai, menyebabkan ratusan user dashboard secara bersamaan memicu kalkulasi ulang ke tabel dasar (*cache stampede*).
- **Troubleshooting & Fix**:
  - Terapkan strategi **Warm-up Cache Warming** terprogram: Jalankan bot kueri otomatis pasca-pipeline dbt selesai untuk membangun cache *sebelum* jam kantor dimulai.
  - Implementasikan *Stale-While-Revalidate* cache control.

### 10.3 Dynamic Partition Pruning Failure
- **Gejala**: Kueri analitik dengan filter rentang tanggal tetap memindai 100% isi tabel (Terabyte scanned).
- **Root Cause**: Menerapkan fungsi deterministik atau transformasi kolom pada klausa filter, misalnya: `WHERE TO_CHAR(order_date, 'YYYY-MM-DD') = '2024-01-01'`. Mesin database tidak dapat menggunakan partisi mikro karena kolom terbungkus fungsi.
- **Troubleshooting & Fix**:
  - Pertahankan integritas kolom partisi asli: `WHERE order_date >= '2024-01-01' AND order_date < '2024-01-02'`.

---

## 11. Best Practices (Production Checklist)

### Data Modeling & SQL
- [ ] Setiap tabel dimensi memiliki Surrogate Key (SK) non-bisnis berbasis Hash (`MD5`/`SHA256`).
- [ ] Tidak ada penggunaan `SELECT *` dalam produksi data mart.
- [ ] Semua kolom desimal finansial menggunakan tipe data `DECIMAL/NUMERIC`, bukan `FLOAT/DOUBLE`.
- [ ] Fact tables memiliki *clustering* atau *partitioning* berdasarkan kolom waktu/tanggal utama.

### Semantic Layer & BI Governance
- [ ] Definisi metrik tersimpan dalam kontrol versi Git (dbt semantic layer, Cube YAML).
- [ ] Singularitas metrik: Tidak ada duplikasi nama metrik dengan formula berbeda di platform manapun.
- [ ] Konfigurasi default *query timeout* pada layer presentasi (misal: batasi maksimal 30 detik untuk dashboard interaktif).

### FinOps & Reliability
- [ ] Pemasangan *Daily Warehouse Auto-suspend* (maksimal 60-120 detik idle time).
- [ ] Penerapan *Resource Monitor* dengan hard-cap budget alert pada cloud warehouse.
- [ ] Data Quality checks (Null checks, Uniqueness, Referential Integrity) berjalan sebagai *blocking step* di CI/CD pipeline staging sebelum dipromosikan ke Gold layer.

---

## 12. Hands-on Practice: Membangun Production-Grade Data Mart & Metric Engine

Praktikum ini menggunakan **DuckDB** (mesin analytical in-process SQL berstandar columnar storage modern) dan Python untuk mendemonstrasikan pembentukan model dimensional, penanganan Fan-Out Trap, dan semantic aggregation.

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/setup_environment.py`
```python
import duckdb
import os

os.makedirs("data", exist_ok=True)
con = duckdb.connect("data/enterprise_bi.duckdb")

# Setup Skema & Raw Data
con.execute("""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS gold;

-- Raw Orders (Fakta Transaksi)
CREATE OR REPLACE TABLE raw.orders AS SELECT * FROM (VALUES
    (1, 101, TIMESTAMP '2024-03-01 10:00:00', 500.0, 'COMPLETED'),
    (2, 102, TIMESTAMP '2024-03-01 11:30:00', 1200.0, 'COMPLETED'),
    (3, 101, TIMESTAMP '2024-03-02 09:15:00', 300.0, 'CANCELLED'),
    (4, 103, TIMESTAMP '2024-03-02 14:00:00', 1500.0, 'COMPLETED')
) AS t(order_id, customer_id, order_time, amount, status);

-- Raw Order Items (Granularitas Lebih Rendah -> Potensi Fan-out)
CREATE OR REPLACE TABLE raw.order_items AS SELECT * FROM (VALUES
    (1, 1, 501, 250.0),
    (2, 1, 502, 250.0),
    (3, 2, 503, 1200.0),
    (4, 3, 504, 300.0),
    (5, 4, 505, 500.0),
    (6, 4, 506, 500.0),
    (7, 4, 507, 500.0)
) AS t(item_id, order_id, product_id, item_amount);

-- Raw Target Sales (Fakta Target Per Tanggal)
CREATE OR REPLACE TABLE raw.sales_targets AS SELECT * FROM (VALUES
    (DATE '2024-03-01', 1500.0),
    (DATE '2024-03-02', 2000.0)
) AS t(target_date, target_amount);
""")

print("[SUCCESS] Environment DuckDB berhasil disiapkan di 'data/enterprise_bi.duckdb'.")
con.close()
```

### File: `hands-on/m02/build_marts.py`
```python
import duckdb

con = duckdb.connect("data/enterprise_bi.duckdb")

# 1. Transformasi Gold Fact: Fact Orders dengan Surrogate Key MD5
con.execute("""
CREATE OR REPLACE TABLE gold.fct_orders AS
SELECT
    MD5(CAST(order_id AS VARCHAR)) AS order_sk,
    order_id,
    customer_id,
    CAST(order_time AS DATE) AS order_date,
    amount,
    status,
    CASE WHEN status = 'COMPLETED' THEN amount ELSE 0.0 END AS net_completed_revenue
FROM raw.orders;
""")

# 2. Semantic Resolution Query (Menghindari Fan-out antara Orders & Target)
# Menghitung realisasi sales vs target tanpa duplikasi target
semantic_result = con.execute("""
WITH aggregated_sales AS (
    SELECT 
        order_date,
        SUM(net_completed_revenue) AS daily_actual_revenue,
        COUNT(DISTINCT order_id) AS total_orders
    FROM gold.fct_orders
    GROUP BY order_date
),
daily_performance AS (
    SELECT
        COALESCE(s.order_date, t.target_date) AS metric_date,
        COALESCE(s.daily_actual_revenue, 0.0) AS actual_revenue,
        COALESCE(t.target_amount, 0.0) AS target_amount,
        ROUND((COALESCE(s.daily_actual_revenue, 0.0) / t.target_amount) * 100, 2) AS attainment_pct
    FROM aggregated_sales s
    FULL OUTER JOIN raw.sales_targets t
        ON s.order_date = t.target_date
)
SELECT * FROM daily_performance ORDER BY metric_date ASC;
""").fetchdf()

print("\n--- HASIL METRIK SEMANTIC (ACTUAL VS TARGET) ---")
print(semantic_result)

con.close()
```

### Langkah Menjalankan Praktikum:
1. Pastikan runtime Python 3.10+ telah terinstal.
2. Jalankan perintah instalasi dependency:
   ```bash
   pip install duckdb pandas
   ```
3. Eksekusi file persiapan:
   ```bash
   python hands-on/m02/setup_environment.py
   ```
4. Eksekusi script transformasi data mart dan semantic engine:
   ```bash
   python hands-on/m02/build_marts.py
   ```

---

## 13. Exercises

### Level Easy
Diberikan tabel `fact_sales` (kolom: `sale_id`, `sale_timestamp`, `gross_amount`). Buat kueri SQL analitik untuk menghitung rata-rata harian bergulir selama 7 hari (*7-day rolling average*) dari `gross_amount` untuk setiap transaksi tanpa merusak granularitas baris!

<details>
<summary>Lihat Solusi</summary>

```sql
SELECT
    sale_id,
    sale_timestamp,
    gross_amount,
    AVG(gross_amount) OVER (
        ORDER BY sale_timestamp
        RANGE BETWEEN INTERVAL 7 DAYS PRECEDING AND CURRENT ROW
    ) AS rolling_avg_7d
FROM fact_sales;
```
</details>

---

### Level Medium
Sebuah marketplace memiliki skema bintang: `dim_merchants` (SCD Type 2) dan `fact_settlement`. Jika terjadi perubahan status merchant dari 'REGULAR' menjadi 'PREMIUM' pada tanggal `2024-06-15 00:00:00`, tuliskan kueri data modeling SQL untuk memastikan laporan transaksi tanggal 14 Juni teratribusi ke 'REGULAR', dan transaksi tanggal 15 Juni ke 'PREMIUM'.

<details>
<summary>Lihat Solusi</summary>

```sql
SELECT
    f.settlement_id,
    f.settlement_amount,
    f.settlement_timestamp,
    m.merchant_id,
    m.merchant_tier
FROM fact_settlement f
INNER JOIN dim_merchants m
    ON f.merchant_id = m.merchant_id
    AND f.settlement_timestamp >= m.valid_from
    AND (f.settlement_timestamp < m.valid_to OR m.valid_to IS NULL);
```
</details>

---

### Level Hard
Rancang struktur DDL dan kueri analitik penanganan **Chasm Trap** untuk skema enterprise berikut:
Satu tabel customer memiliki dua fakta independen: `fact_deposits` dan `fact_withdrawals`. Hitung rasio total deposit terhadap total withdrawal per customer per bulan tanpa menghasilkan Cartesian product (Cross Join Fan-Out)!

<details>
<summary>Lihat Solusi</summary>

```sql
WITH dep_monthly AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', deposit_time) AS month_date,
        SUM(deposit_amount) AS total_deposit
    FROM fact_deposits
    GROUP BY customer_id, DATE_TRUNC('month', deposit_time)
),
wdr_monthly AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', withdrawal_time) AS month_date,
        SUM(withdrawal_amount) AS total_withdrawal
    FROM fact_withdrawals
    GROUP BY customer_id, DATE_TRUNC('month', withdrawal_time)
)
SELECT
    COALESCE(d.customer_id, w.customer_id) AS customer_id,
    COALESCE(d.month_date, w.month_date) AS metric_month,
    COALESCE(d.total_deposit, 0) AS total_deposit,
    COALESCE(w.total_withdrawal, 0) AS total_withdrawal,
    CASE 
        WHEN COALESCE(w.total_withdrawal, 0) = 0 THEN NULL 
        ELSE ROUND(COALESCE(d.total_deposit, 0) / w.total_withdrawal, 4) 
    END AS deposit_to_withdrawal_ratio
FROM dep_monthly d
FULL OUTER JOIN wdr_monthly w
    ON d.customer_id = w.customer_id 
    AND d.month_date = w.month_date;
```
</details>

---

## 14. Challenge: Arsitektur Multi-Currency Marketplace dengan Delayed Attribution

### Kasus Nyata:
Anda adalah Lead BI Architect di "OmniShop Global", platform e-commerce beroperasi di 12 negara dengan ketentuan arsitektur analitik:
1. **Volatilitas Kurs**: Transaksi terjadi dalam mata uang lokal (IDR, JPY, EUR, USD), tetapi seluruh metrik eksekutif dan board report harus dapat dikonversi secara real-time ke USD menggunakan kurs penutupan transaksi harian (*Daily Exchange Rate*).
2. **Late-Arriving Facts**: 15% event log checkout terlambat masuk ke warehouse hingga H+3 karena sync offline dari edge device POS kasir toko fisik.
3. **Refund Attribution**: Retur barang/refund bisa terjadi hingga H+30 setelah transaksi dan harus dialokasikan ke metrik 'Net Adjusted Revenue' pada *bulan terjadinya transaksi original*, bukan bulan saat refund diproses.

### Tugas Desain Anda:
1. Gambarkan arsitektur data pipeline (ASCII Diagram) dari Raw Ingestion hingga Semantic Model Presentation.
2. Tuliskan skema data modeling (DDL/SQL) yang paling optimal untuk menangani kasus kurs mata uang dan late-arriving events tanpa mengharuskan full-refresh rebuild pada seluruh tabel fakta historis.
3. Tentukan bagaimana Semantic Layer mendefinisikan formula `Net Adjusted Revenue` yang secara dinamis memperhitungkan refund mundur tersebut secara deterministik.

*(Tantangan ini tidak memiliki kunci jawaban instan. Rancang arsitektur ini berdasarkan prinsip-prinsip decoupling, idempotency, dan partition immutability).*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (5 Soal)
1. **Apa perbedaan mendasar antara SCD Type 1 dan SCD Type 2?**
   - *Jawaban*: SCD Type 1 menimpa data lama (tidak ada histori), sedangkan SCD Type 2 mempertahankan riwayat perubahan dengan membuat baris baru yang dilengkapi penanda waktu (`valid_from`, `valid_to`) atau status aktif (`is_current`).
2. **Apa yang dimaksud dengan Surrogate Key pada Kimball modeling?**
   - *Jawaban*: Kunci buatan (artificial/synthetic key), sering berupa integer urut atau hash string, yang tidak memiliki makna bisnis dan digunakan sebagai primary key unik tabel dimensi untuk memisahkan warehouse dari dependensi sistem operasional.
3. **Mengapa columnar storage lebih diunggulkan dibandingkan row-oriented storage untuk query analytical (OLAP)?**
   - *Jawaban*: Karena kueri OLAP biasanya mengagregasi sejumlah kecil kolom dari miliaran baris. Columnar storage hanya membaca kolom yang dibutuhkan dari disk (pruning) dan memungkinkan rasio kompresi data yang jauh lebih tinggi.
4. **Apa fungsi utama dari Semantic Layer dalam Modern Data Stack?**
   - *Jawaban*: Sebagai layer abstraksi terpusat di atas data warehouse yang mengunci definisi bisnis, join logic, dan kalkulasi metrik secara konsisten untuk berbagai platform konsumsi data (BI tools, AI agents, sheets).
5. **Apa indikasi utama terjadinya Fan-out Trap dalam query SQL?**
   - *Jawaban*: Nilai kalkulasi agregasi metrik (seperti `SUM` atau `COUNT`) menjadi berlipat ganda dari angka aktual karena operasi `1-to-many join` yang menduplikasi baris pada tabel sisi '1'.

---

### 15.2 Pertanyaan Intermediate (5 Soal)
6. **Kapan sebuah arsitektur data sebaiknya menggunakan One Big Table (OBT) dibandingkan Kimball Star Schema?**
   - *Jawaban*: Saat use-case berorientasi pada latensi baca dashboard super cepat, skala read query sangat tinggi, kompleksitas join perlu dieliminasi untuk user BI pemula, dan kapasitas disk/storage bukan kendala utama.
7. **Bagaimana cara kerja teknik Stitching Query pada Semantic Engine untuk mencegah Chasm Trap?**
   - *Jawaban*: Engine memecah kueri menjadi beberapa sub-query/CTE independen per fact table di level agregasi yang setara, lalu menggabungkan hasilnya menggunakan `FULL OUTER JOIN` pada shared dimension keys.
8. **Apa dampak buruk dari pengabaian Clustering Key pada tabel fakta berukuran multi-terabyte di Snowflake/BigQuery?**
   - *Jawaban*: Terjadi *full partition scanning* yang memicu konsumsi komputasi tinggi, biaya query melonjak drastis, serta degradasi latensi respons dashboard.
9. **Mengapa penggunaan MD5/SHA256 hash surrogate keys mempermudah proses ELT incremental dibandingkan auto-increment sequence ID?**
   - *Jawaban*: Hash keys bersifat deterministik dan stateless; dapat dihasilkan secara independen di pipeline transformasi terdistribusi secara paralel tanpa perlu melakukan locking atau koordinasi global state ke database sequence engine.
10. **Bagaimana AI Autonomous Agent memanfaatkan Enterprise Semantic Layer untuk Text-to-SQL?**
    - *Jawaban*: AI tidak perlu menebak nama tabel fisik atau relasi join yang kompleks; AI cukup memetakan intent user ke metrik dan dimensi yang telah tervalidasi di semantic schema, mencegah kesalahan halusinasi sintaks SQL.

---

### 15.3 Skenario Kasus Produksi (3 Kasus)

#### Skenario 1: Ledakan Biaya Warehouse Akibat Dashboard BI
- **Kondisi**: Dashboard eksekutif dibuka oleh 500 branch manager setiap jam 09:00. Dashboard melakukan kueri langsung (Direct Query) ke BigQuery/Snowflake yang mengarah ke tabel fakta berukuran 2 TB. Biaya melonjak 400% dalam 1 bulan.
- **Tindakan Penanganan**:
  1. Pasang layer pre-aggregation/BI caching (misal via Cube.js atau BigQuery BI Engine) dengan TTL 2-4 jam.
  2. Alihkan kueri dashboard ke tabel agregasi ter-materialisasi (*Rollup Mart*) level harian, bukan langsung menembak raw transactional fact.
  3. Konfigurasi clustering table berdasarkan `branch_id` dan batasi akses kueri user menggunakan auto partition filtering.

#### Skenario 2: Anomali Metrik Pasca Migrasi Skema Operasional
- **Kondisi**: Tim software engineering merilis fitur baru yang memungkinkan customer membagi split-payment menjadi 2 kartu. Dashboard keuangan mendadak melaporkan jumlah pembeli (*buyer count*) naik 2x lipat dari biasanya.
- **Tindakan Penanganan**:
  1. Identifikasi bahwa kueri analitik lama menggunakan `COUNT(order_id)` pada tabel join payment yang kini memiliki kardinalitas 1 order to many payments.
  2. Implementasikan *Data Contract* antara tim SWE dan Data Platform agar setiap perubahan skema di-notifikasi sebelum rilis.
  3. Perbaiki logika semantic layer menjadi `COUNT(DISTINCT order_id)` atau isolasi granularitas payment ke fact table terpisah.

#### Skenario 3: Penanganan Data Masuk Tak Beraturan (Out-of-Order Ingestion)
- **Kondisi**: Sistem IoT logistik mengirim data status pengiriman dengan delay bervariasi (beberapa data tiba terlambat 48 jam). Dashboard SLA pengiriman selalu salah jika hanya melihat batch data hari berjalan.
- **Tindakan Penanganan**:
  1. Ubah strategi partitioning: gunakan partisi berdasarkan `event_timestamp` (waktu kejadian asli), bukan `ingestion_timestamp`.
  2. Terapkan pemrosesan dbt incremental dengan sliding look-back window (misal: memproses ulang data `CURRENT_DATE - INTERVAL 3 DAYS`).
  3. Gunakan *watermark tracking* untuk mendeteksi event yang tiba terlambat dan memicu materialisasi ulang partisi terkait secara selektif tanpa full-refresh.

---

## 16. Summary
- Modern BI bukan sekadar membangun dashboard visual, melainkan membangun **arsitektur data analitik terstruktur, berperforma tinggi, dan konsisten**.
- Pemisahan antara storage layer dan semantic logic (**Decoupled Semantic Layer**) adalah standar fundamental untuk melayani BI tradisional, Reverse ETL, dan AI Autonomous Agents secara harmonis.
- Pemilihan pemodelan data (Kimball vs. OBT) harus didasarkan pada karakteristik query engine (columnar vs. row-based), trade-off antara biaya penyimpanan vs. latensi kueri, dan kompleksitas pemeliharaan skema.
- Penerapan otomatisasi pengujian data (*shift-left data quality*), pencegahan join traps (*fan-out & chasm traps*), dan prinsip FinOps adalah pembeda antara arsitektur data amatir dengan platform data kelas enterprise.