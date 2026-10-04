# Modul 01: Modern Data Warehousing & Dimensional Data Modeling

**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Track:** Data Analyst  
**Bab 04:** Modern Data Warehousing & Dimensional Data Modeling  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Menentukan Grain:** Menentukan derajat granulasi (*grain*) data transaksi secara formal sebelum merancang skema analitis untuk mencegah anomali agregasi (*double counting*).
- **Merancang Skema Dimensional Modern:** Mengembangkan model *Star Schema* dan *Snowflake Schema* yang optimal untuk *columnar execution engine* (Snowflake, BigQuery, ClickHouse, DuckDB).
- **Mengimplementasikan SCD Type 2:** Membangun mekanisme *Slowly Changing Dimensions* Tipe 2 menggunakan teknik *deterministic hashing* (SHA-256) untuk isolasi histori mutasi data secara idempoten.
- **Mengintegrasikan Dimensional Layer ke AI Pipeline:** Menghubungkan model dimensional ke Semantic Layer dan *Feature Store* guna menyuplai konteks terstruktur berlatensi rendah untuk *Autonomous Agents* dan LLM.
- **Mengevaluasi Kinerja Query:** Mengidentifikasi dan memitigasi *join explosion* serta *data skewness* pada *distributed data warehouse*.

---

## 2. Concept Overview

Model mental analitik modern membedakan dua beban kerja komputasi utama: **OLTP (Online Transaction Processing)** yang berorientasi pada integritas transaksi atomik tingkat baris (3NF / Third Normal Form), dan **OLAP (Online Analytical Processing)** yang dioptimalkan untuk pembacaan kolumnar dengan volume data masif.

```
OLTP (Normalisasi 3NF)                   OLAP (Pemodelan Dimensional)
+-----------------------+                +-----------------------+
|  Write-Heavy (ACID)   |   ELT Batch    |   Read-Heavy (OLAP)   |
| Normalisasi Tinggi    | -------------> | Denormalisasi Terukur |
| Eliminasi Redundansi  |  / Streaming   | Star / Snowflake      |
| Akses Baris (Row-Store)|               | Akses Kolom (Columnar)|
+-----------------------+                +-----------------------+
```

### Konsep Inti Pemodelan Dimensional (Kimball Architecture)
1. **Fact Tables:** Tabel inti berisikan metrik kuantitatif terukur (*measurements*) yang dihasilkan dari peristiwa bisnis (*business events*). Karakteristik utamanya adalah numerik dan bersifat aditif (*fully additive*, *semi-additive*, atau *non-additive*).
2. **Dimension Tables:** Tabel referensi kontekstual yang menyediakan filter, pengelompokan (*grouping*), dan pelabelan deskriptif (kata tanya: *who, what, where, when, why*).
3. **Surrogate Keys vs. Natural Keys:** Pemisahan mutlak antara kunci operasional (*natural key* dari sistem sumber) dengan *surrogate key* (kunci sintetis warehouse bertipe integer atau hash) untuk mengisolasi siklus hidup data warehouse dari dependensi sistem upstream.
4. **The Grain:** Kontrak formal yang mendefinisikan secara tepat representasi satu baris data tunggal dalam Fact Table. *Grain* yang ambigu adalah akar kegagalan pelaporan analitik.

---

## 3. Why It Matters

Dalam lanskap komputasi modern dan ekosistem *Autonomous Agents*:
- **Biaya Komputasi Cloud (Cost Governance):** Menjalankan kueri agregasi analitis pada skema ternormalisasi (3NF) memaksa database melakukan puluhan operasi `JOIN`. Pada sistem penagihan berbasis komputasi (Snowflake Credits, BigQuery Slot-time), inefisiensi ini meningkatkan biaya infrastruktur secara eksponensial.
- **Konsistensi Metrik (*Single Source of Truth*):** Tanpa model dimensional standar (*Conformed Dimensions*), divisi yang berbeda (misalnya: *Sales* vs *Finance*) akan mendefinisikan metrik fundamental seperti *Active Customer* atau *Gross Revenue* dengan kalkulasi yang saling bertentangan.
- **Pondasi Grounding untuk LLM & AI Agents:** AI Agent yang bertugas melakukan *Text-to-SQL* atau inferensi keputusan otomatis membutuhkan skema database yang intuitif. Star schema meminimalisir jalur join (*join paths*), sehingga mengurangi halusinasi LLM dalam merumuskan kueri analitik kompleks.

---

## 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur aliran data *end-to-end* dari *source systems* hingga ke *consumption layer* berbasis *Kimball Dimensional Bus Architecture*:

```
+-----------------------------------------------------------------------------------+
| RAW / EXTRACTION LAYER                                                            |
| [Postgres App DB]      [Stripe API Engine]      [Kafka Clickstream Topic]         |
+-----------------------------------------------------------------------------------+
                                       |
                                       v  (Raw Ingestion via ELT)
+-----------------------------------------------------------------------------------+
| MEDALLION: BRONZE (RAW STORAGE / LAKEHOUSE ENGINE)                                |
| Parquet Files / Delta Tables (Append-Only, Immutable Source Copies)               |
+-----------------------------------------------------------------------------------+
                                       |
                                       v  (Data Cleansing, Typing & Dedup)
+-----------------------------------------------------------------------------------+
| MEDALLION: SILVER (NORMALIZED / ATOMIC STAGING)                                   |
| Stg_Customer, Stg_Orders, Stg_Transactions (Ephemeral / Incremental Tables)       |
+-----------------------------------------------------------------------------------+
                                       |
                                       v  (Dimensional Modeling & SCD Transformation)|
+-----------------------------------------------------------------------------------+
| MEDALLION: GOLD (STAR SCHEMA DIMENSIONAL MARTS)                                   |
|                                                                                   |
|  +-------------------+       +-----------------------+      +-------------------+ |
|  |   dim_date        |<------|  fact_order_items     |----->|   dim_customer    | |
|  |-------------------|       |-----------------------|      |-------------------| |
|  | PK date_key       |       | PK order_item_sk      |      | PK customer_sk    | |
|  |    full_date      |       | FK date_key           |      |    natural_id     | |
|  |    fiscal_quarter |       | FK customer_sk        |      |    valid_from     | |
|  +-------------------+       | FK product_sk         |      |    valid_to       | |
|                              |    quantity           |      |    is_current     | |
|  +-------------------+       |    net_amount         |      |    tier_level     | |
|  |   dim_product     |<------|    tax_amount         |      +-------------------+ |
|  |-------------------|       +-----------------------+                            |
|  | PK product_sk     |                                                            |
|  |    sku            |                                                            |
|  |    category_name  |                                                            |
|  +-------------------+                                                            |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| CONSUMPTION & SERVING LAYER                                                       |
| [Semantic Layer / Metric Stores]  <-->  [AI Agent / RAG Feature Retrieval]        |
| [Executive BI / Tableau Dashboards]                                               |
+-----------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Kimball Bus Matrix
Kimball Bus Matrix adalah representasi ortogonal antara proses bisnis (*Facts*) dengan entitas bisnis bersama (*Conformed Dimensions*).

| Business Process (Fact) | dim_date | dim_customer | dim_product | dim_organization | dim_store |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Orders** | **X** | **X** | **X** | **X** | **X** |
| **Inventory Snapshot** | **X** | | **X** | | **X** |
| **Customer Support Ticket**| **X** | **X** | | **X** | |
| **Billing & Payments** | **X** | **X** | | **X** | |

*Conformed dimensions* menjamin bahwa analisis lintas departemen (misal: membandingkan volume pemesanan terhadap rasio tiket komplain pelanggan) dapat dilakukan menggunakan operasi `JOIN` langsung tanpa konversi tipe data atau manipulasi teks.

### 5.2 Slowly Changing Dimensions (SCD)
Karakteristik dimensi yang atributnya berubah sepanjang waktu diatur menggunakan taksonomi SCD:

- **SCD Type 0 (Retain Original):** Atribut statis (e.g., `date_of_birth`). Tidak pernah diperbarui.
- **SCD Type 1 (Overwrite):** Nilai baru menimpa nilai lama. Tidak mempertahankan histori data masa lalu. Metrik historis otomatis terhitung menggunakan atribut terbaru (*destructive update*).
- **SCD Type 2 (Add New Row):** Menambahkan baris baru dengan *surrogate key* baru setiap kali terjadi mutasi. Mekanisme ini menggunakan kolom kontrol:
  - `valid_from` (TIMESTAMP)
  - `valid_to` (TIMESTAMP atau NULL/`9999-12-31`)
  - `is_current` (BOOLEAN)
  - `row_hash` (CHAR/VARCHAR: Hash dari seluruh atribut yang diawasi)
- **SCD Type 3 (Add New Attribute):** Menambahkan kolom baru untuk nilai sebelumnya (e.g., `current_tier`, `previous_tier`). Histori terbatas pada level kolom.

### 5.3 Deterministic Hashing untuk SCD2
Penggunaan *auto-incrementing integers* untuk surrogate keys pada lingkungan komputasi paralel terdistribusi (*distributed DWH*) menimbulkan *locking contention* dan *synchronization bottlenecks*. Standar industri modern beralih ke deterministik hashing (misal: SHA-256):

$$\text{surrogate\_key} = \text{SHA256}(\text{natural\_key} \parallel \text{CAST}(\text{valid\_from} \text{ AS TEXT}))$$
$$\text{row\_hash} = \text{SHA256}(\text{col}_1 \parallel \text{"|"} \parallel \text{col}_2 \parallel \text{"|"} \dots \parallel \text{col}_n)$$

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi *end-to-end* pemrosesan data dimensional dengan Python (menggunakan DuckDB sebagai *in-process OLAP engine*) untuk skenario *SCD Type 2 Customer Dimension* dan *Order Fact Loading*.

### 6.1 Data Structures & DDL Script

```sql
-- DDL Staging Layer (Idempotent DDL)
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS staging.stg_customers (
    customer_id VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    subscription_tier VARCHAR NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.stg_orders (
    order_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(18, 4) NOT NULL,
    tax_amount DECIMAL(18, 4) NOT NULL
);

-- DDL Warehouse Layer (Dimensional Models)
CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_sk VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    subscription_tier VARCHAR NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    row_hash VARCHAR(64) NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    is_current BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.fact_orders (
    order_sk VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR NOT NULL,
    customer_sk VARCHAR(64) NOT NULL REFERENCES warehouse.dim_customer(customer_sk),
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(18, 4) NOT NULL,
    tax_amount DECIMAL(18, 4) NOT NULL,
    net_amount DECIMAL(18, 4) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

### 6.2 SCD Type 2 ETL Processing Engine (Python)

```python
"""
Dimensional Modeling SCD Type 2 Engine
Implementasi Pipeline Idempoten dengan Hashing dan Point-in-Time Fact Loading
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Final

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DB_PATH: Final[str] = "analytics_dw.duckdb"


class DimensionalPipeline:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.conn = duckdb.connect(database=db_path, read_only=False)

    def close(self) -> None:
        self.conn.close()

    def execute_query(self, query: str, parameters: list | None = None) -> None:
        try:
            if parameters:
                self.conn.execute(query, parameters)
            else:
                self.conn.execute(query)
        except Exception as e:
            logger.critical(f"Database execution failed: {str(e)}")
            raise

    def process_scd2_customers(self) -> None:
        """
        Memproses mutasi dimensi Customer menggunakan SCD Type 2.
        Algoritma:
        1. Menghitung Hash atribut fungsional pada data staging.
        2. Mengidentifikasi record yang berubah dengan mencocokkan ke record aktif (is_current = True).
        3. Menutup record lama yang mengalami perubahan (valid_to = staging.updated_at, is_current = False).
        4. Menginsert record baru dan record yang termutasi.
        """
        logger.info("Memulai pemrosesan SCD Type 2 untuk warehouse.dim_customer...")

        scd2_transaction = """
        BEGIN TRANSACTION;

        -- 1. Buat temporary view dengan komputasi hash
        CREATE OR REPLACE TEMP VIEW v_stg_customers_hashed AS
        SELECT 
            customer_id,
            full_name,
            email,
            subscription_tier,
            country_code,
            updated_at,
            SHA256(CONCAT(full_name, '|', email, '|', subscription_tier, '|', country_code)) AS row_hash
        FROM staging.stg_customers;

        -- 2. Identifikasi record yang dimutasi dan record baru
        CREATE OR REPLACE TEMP VIEW v_records_to_process AS
        SELECT 
            stg.customer_id,
            stg.full_name,
            stg.email,
            stg.subscription_tier,
            stg.country_code,
            stg.updated_at,
            stg.row_hash,
            dim.customer_sk AS active_dim_sk,
            CASE 
                WHEN dim.customer_sk IS NULL THEN 'INSERT'
                WHEN dim.row_hash != stg.row_hash THEN 'UPDATE'
                ELSE 'NO_CHANGE'
            END AS action_type
        FROM v_stg_customers_hashed stg
        LEFT JOIN warehouse.dim_customer dim 
            ON stg.customer_id = dim.customer_id 
            AND dim.is_current = TRUE;

        -- 3. Invalidate record lama yang mengalami perubahan
        UPDATE warehouse.dim_customer
        SET 
            valid_to = rtp.updated_at,
            is_current = FALSE
        FROM v_records_to_process rtp
        WHERE warehouse.dim_customer.customer_sk = rtp.active_dim_sk
          AND rtp.action_type = 'UPDATE';

        -- 4. Masukkan record baru dan record perubahan (SCD Type 2 New Rows)
        INSERT INTO warehouse.dim_customer (
            customer_sk,
            customer_id,
            full_name,
            email,
            subscription_tier,
            country_code,
            row_hash,
            valid_from,
            valid_to,
            is_current
        )
        SELECT 
            SHA256(CONCAT(rtp.customer_id, '|', STRFTIME(rtp.updated_at, '%Y-%m-%d %H:%M:%S'))),
            rtp.customer_id,
            rtp.full_name,
            rtp.email,
            rtp.subscription_tier,
            rtp.country_code,
            rtp.row_hash,
            rtp.updated_at,
            NULL,
            TRUE
        FROM v_records_to_process rtp
        WHERE rtp.action_type IN ('INSERT', 'UPDATE');

        COMMIT;
        """
        self.conn.execute(scd2_transaction)
        logger.info("Sinkronisasi SCD Type 2 Customer selesai secara aman.")

    def load_fact_orders(self) -> None:
        """
        Memuat data Fact Orders dengan teknik Point-in-Time Join terhadap Dim Customer
        berdasarkan rentang validitas (valid_from <= order_date < valid_to).
        """
        logger.info("Memuat data fact_orders dengan Point-in-Time Dimension Resolution...")

        fact_pipeline_query = """
        INSERT INTO warehouse.fact_orders (
            order_sk,
            order_id,
            customer_sk,
            order_date,
            total_amount,
            tax_amount,
            net_amount,
            created_at
        )
        SELECT 
            SHA256(CONCAT(o.order_id, '|', STRFTIME(o.order_date, '%Y-%m-%d %H:%M:%S'))) AS order_sk,
            o.order_id,
            COALESCE(c.customer_sk, 'UNKNOWN_CUSTOMER_SK') AS customer_sk,
            o.order_date,
            o.total_amount,
            o.tax_amount,
            (o.total_amount - o.tax_amount) AS net_amount,
            CURRENT_TIMESTAMP AS created_at
        FROM staging.stg_orders o
        LEFT JOIN warehouse.dim_customer c 
            ON o.customer_id = c.customer_id
            AND o.order_date >= c.valid_from
            AND (o.order_date < c.valid_to OR c.valid_to IS NULL)
        WHERE NOT EXISTS (
            SELECT 1 FROM warehouse.fact_orders f WHERE f.order_id = o.order_id
        );
        """
        self.conn.execute(fact_pipeline_query)
        logger.info("Pemuatan fact_orders berhasil diselesaikan.")


if __name__ == "__main__":
    pipeline = DimensionalPipeline()
    try:
        # Inisialisasi skema
        with open("schema.sql", "r") as f:
            pipeline.execute_query(f.read())
        pipeline.process_scd2_customers()
        pipeline.load_fact_orders()
    except FileNotFoundError:
        logger.warning("File schema.sql tidak ditemukan lokal, lewati inisialisasi eksternal.")
    finally:
        pipeline.close()
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Late-Arriving Data (LAD)
- **Skenario:** Transaksi `Fact` terjadi pada `2024-01-01 10:00:00`, tetapi rekaman dimensi `Customer` yang sesuai baru terkirim ke warehouse melalui proses ELT pada `2024-01-02`.
- **Mitigasi Teknis:** 
  1. *Early-Arriving Fact Handling:* Buat *placeholder record* pada tabel dimensi dengan `customer_id` yang diketahui, `is_current = TRUE`, dan tandai atribut kontekstual sebagai `status = 'UNKNOWN'`.
  2. Ketika data dimensi yang valid akhirnya tiba, lakukan *update* pada atribut placeholder tersebut tanpa mengubah `customer_sk` yang sudah dirujuk oleh `fact_orders`.

### 7.2 Out-of-Order Updates (Temporal Chaos)
- **Skenario:** *Change Data Capture (CDC)* mengirimkan mutasi log `v2` (pukul 12:00) mendahului log `v1` (pukul 11:00) karena masalah paralelisme pada message broker.
- **Mitigasi Teknis:** Jangan mengandalkan urutan kedatangan *network stream*. Gunakan teknik *window function* pada data staging:
  ```sql
  QUALIFY ROW_NUMBER() OVER(
      PARTITION BY customer_id 
      ORDER BY updated_at DESC
  ) = 1
  ```
  Ini memastikan hanya *state* paling terverifikasi yang dievaluasi untuk proses SCD Type 2.

### 7.3 Hash Collision Risk
- **Skenario:** Terjadi tabrakan nilai hash saat menggunakan fungsi hashing yang ringkas (misal: MD5 atau CRC32) pada entitas berjumlah miliaran baris.
- **Mitigasi Teknis:** Standarkan seluruh kebutuhan *surrogate key* analitik ke **SHA-256** dan sertakan *delimiter* unik (misal: `|` atau `\x1f`) di antara kolom yang digabungkan untuk menghindari ambiguitas enkapsulasi string (contoh: string `A` + `BC` vs `AB` + `C`).

---

## 8. Trade-offs & Alternatif Solusi

| Kriteria | Kimball Star Schema | 3NF (Inmon Enterprise DWH) | One Big Table (OBT / Denormalized) |
| :--- | :--- | :--- | :--- |
| **Penyimpanan (Storage)** | Moderat (Redundansi terkontrol pada dimensi) | Sangat Efisien (Menghindari redundansi) | Boros (Duplikasi string & metadata pada tiap baris) |
| **Kecepatan Kueri Analitik** | Tinggi (Optimasi star-join pada columnar engine) | Buruk (Join traversal kompleks, lambat pada scale TB/PB) | Maksimal (Nol join, sekuensial linear columnar scanning) |
| **Integritas Konseptual** | Tinggi (*Conformed dimensions* menyatukan metrik) | Sangat Tinggi (Strict Entity Relationship Rules) | Rendah (Rentan desinkronisasi histori) |
| **Kesesuaian LLM & AI Agents** | **Optimal** (Struktur mudah dinavigasi agen SQL) | Buruk (Struktur relasi membingungkan model bahasa) | Baik (Data pipih, namun context window rawan overflow) |
| **Beban Pemeliharaan Pipeline**| Moderat (Manajemen SCD & Fact ETL) | Tinggi (Pipeline dependensi berantai yang ketat) | Rendah (Langsung append dari streaming/raw flattened) |

---

## 9. Best Practices & Standar Industri

### 9.1 Standar Konvensi Medallion & dbt (Data Build Tool)
1. **Layer Staging (`stg_`):** 
   - Konversi tipe data kanonikal.
   - Penamaan kolom seragam (*snake_case*).
   - Penguraian data semi-terstruktur (JSON/Variants).
   - *Tanpa* operasi `JOIN` ke tabel bisnis lain.
2. **Layer Intermediate (`int_`):**
   - Menggabungkan data modular sebelum disajikan.
   - Eksekusi logika *business rule* yang sering dipakai berulang.
3. **Layer Marts (`dim_`, `fact_`):**
   - Menghasilkan model dimensional akhir (Star Schema).
   - Proteksi surrogate key dengan constraints eksplisit atau *dbt unique tests*.

### 9.2 Audit Columns Mandatori
Setiap tabel dimensi dan fakta produksi **wajib** menyertakan atribut audit berikut:
- `dw_inserted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`: Waktu persistensi ke warehouse.
- `dw_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`: Waktu terakhir baris mengalami pembaruan logika.
- `dw_batch_id VARCHAR`: Identifier unik yang mengikat baris data ke ID eksekusi orkestrator (misal: Apache Airflow run ID).

---

## 10. Hands-on Lab Exercise

### Skenario
Sebuah perusahaan logistik global ingin menganalisis metrik retensi dan pesanan armada pengiriman. Anda ditugaskan mengonversi data transaksional mentah menjadi model analitis Star Schema yang mampu melacak perubahan status paket pengiriman secara temporal.

### Langkah 1: Persiapan Environment
Pastikan dependensi Python terpasang:
```bash
pip install duckdb==0.10.0 pandas
```

### Langkah 2: Eksekusi File Lab (`lab_dimensional_modeling.py`)
Jalankan script berikut untuk membuat database DuckDB lokal dan memvalidasi point-in-time state data:

```python
import duckdb

conn = duckdb.connect("logistics_dw.duckdb")

# Setup Data Staging Awal
conn.execute("""
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE TABLE staging.raw_drivers (
    driver_id INT,
    driver_name VARCHAR,
    zone VARCHAR,
    updated_at TIMESTAMP
);

CREATE OR REPLACE TABLE staging.raw_deliveries (
    delivery_id VARCHAR,
    driver_id INT,
    delivery_timestamp TIMESTAMP,
    shipping_fee DECIMAL(10,2)
);

-- Masukkan Rekaman Batch 1 (Baseline)
INSERT INTO staging.raw_drivers VALUES 
(101, 'Budi Santoso', 'Jakarta-Selatan', '2024-01-01 08:00:00'),
(102, 'Siti Aminah', 'Jakarta-Pusat', '2024-01-01 08:00:00');

-- Inisialisasi Dimensi Driver SCD Type 2
CREATE OR REPLACE TABLE marts.dim_driver (
    driver_sk VARCHAR(64) PRIMARY KEY,
    driver_id INT,
    driver_name VARCHAR,
    zone VARCHAR,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
);

INSERT INTO marts.dim_driver VALUES
(SHA256('101|2024-01-01 08:00:00'), 101, 'Budi Santoso', 'Jakarta-Selatan', '2024-01-01 08:00:00', NULL, TRUE),
(SHA256('102|2024-01-01 08:00:00'), 102, 'Siti Aminah', 'Jakarta-Pusat', '2024-01-01 08:00:00', NULL, TRUE);
""")

# Batch 2: Driver 101 Pindah Zona (Mutasi Operasional SCD2)
conn.execute("""
-- Perubahan zona Budi Santoso ke Jakarta-Barat pada tanggal 15 Januari 2024
UPDATE marts.dim_driver 
SET valid_to = '2024-01-15 09:00:00', is_current = FALSE
WHERE driver_id = 101 AND is_current = TRUE;

INSERT INTO marts.dim_driver VALUES
(SHA256('101|2024-01-15 09:00:00'), 101, 'Budi Santoso', 'Jakarta-Barat', '2024-01-15 09:00:00', NULL, TRUE);
""")

# Batch 3: Terjadi Dua Pengiriman pada Zona Waktu Berbeda
conn.execute("""
INSERT INTO staging.raw_deliveries VALUES
('DEL-001', 101, '2024-01-05 14:00:00', 25000.00), -- Terjadi saat Budi masih di Jakarta-Selatan
('DEL-002', 101, '2024-01-20 11:00:00', 30000.00); -- Terjadi saat Budi sudah di Jakarta-Barat

-- Pemuatan Fact Deliveries Menggunakan Point-In-Time Dimension Resolution
CREATE OR REPLACE TABLE marts.fact_deliveries AS
SELECT 
    d.delivery_id,
    drv.driver_sk,
    drv.zone AS historical_zone_at_delivery,
    d.delivery_timestamp,
    d.shipping_fee
FROM staging.raw_deliveries d
JOIN marts.dim_driver drv
  ON d.driver_id = drv.driver_id
 AND d.delivery_timestamp >= drv.valid_from
 AND (d.delivery_timestamp < drv.valid_to OR drv.valid_to IS NULL);
""")

# Langkah 3: Verifikasi Hasil Evaluasi Point-in-Time
result_df = conn.execute("""
SELECT 
    delivery_id, 
    historical_zone_at_delivery, 
    delivery_timestamp, 
    shipping_fee 
FROM marts.fact_deliveries 
ORDER BY delivery_timestamp ASC;
""").fetchdf()

print("HASIL VALIDASI POINT-IN-TIME RESOLUTION:")
print(result_df.to_string(index=False))

conn.close()
```

### Checklist Verifikasi
Pastikan output konsol menampilkan hasil berikut secara presisi:
- [x] Record `DEL-001` (5 Jan 2024) terasosiasi dengan zona `Jakarta-Selatan`.
- [x] Record `DEL-002` (20 Jan 2024) terasosiasi dengan zona baru `Jakarta-Barat`.
- [x] Integritas referensi `driver_sk` menunjuk hash unik dari masing-masing *temporal snapshot* dimensi. Data historis tidak tertimpa. Modul dimensional berfungsi secara analitis.