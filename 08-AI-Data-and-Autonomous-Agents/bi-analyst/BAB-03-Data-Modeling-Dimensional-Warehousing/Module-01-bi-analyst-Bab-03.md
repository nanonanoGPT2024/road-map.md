# Bab 03: Data Modeling & Dimensional Warehousing
## Module 01: Core Dimensional Modeling, Kimball Methodology & Modern Star Schema Engineering

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
* **Merancang (Design)** arsitektur dimensional enterprise-grade menggunakan metodologi 4-Step Kimball Design Process dengan tingkat dekomposisi grain yang konsisten.
* **Mengimplementasikan (Implement)** skema *Star Schema* dan *Snowflake Schema* menggunakan ANSI/Modern SQL yang dilengkapi *surrogate key* berbasis deterministic hashing, *degenerate dimension*, serta penanganan *late-arriving facts/dimensions*.
* **Mengembangkan (Engineer)** pipeline transformasi *Slowly Changing Dimensions* (SCD) Tipe 1, Tipe 2, dan Tipe 3 secara idempoten menggunakan Python dan SQL.
* **Mendiagnosis & Mengeliminasi (Mitigate)** anomali relasional analitik seperti *Fan Trap*, *Chasm Trap*, dan *Granularity Mismatch* pada multi-fact queries.
* **Mengevaluasi (Evaluate)** trade-off komputasi dan penyimpanan antara pemodelan dimensional klasik (*Star Schema*) versus *One Big Table* (OBT) pada arsitektur Columnar Data Warehouse (Snowflake, BigQuery, ClickHouse).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Dimensional modeling adalah teknik perancangan basis data analitik yang dioptimalkan untuk performa kueri agregasi, pemahaman bisnis yang intuitif, dan ketahanan terhadap evolusi skema. Berbeda dari Third Normal Form (3NF) karya Inmon yang berorientasi pada integritas data transaksional (OLTP) dan eliminasi redundansi melalui isolasi relasi, Kimball Dimensional Modeling mengelompokkan data menjadi dua entitas inti: **Fact** dan **Dimension**.

```
Mental Model: 
"Events happening in space and time" -> FACT (Kata Kerja: Sales, Clicks, Logins)
"Context surrounding those events"  -> DIMENSION (Kata Benda: Who, Where, What, Why, When)
```

#### Komponen Utama Model Dimensional
1. **Fact Table**: Berisi metrik kuantitatif (fakta terukur) yang dihasilkan dari proses bisnis operasional.
   * *Additive*: Metrik dapat dijumlahkan di semua dimensi (contoh: `total_revenue`, `quantity_sold`).
   * *Semi-Additive*: Metrik hanya dapat dijumlahkan di sebagian dimensi, biasanya gagal di dimensi waktu (contoh: `account_balance`, `inventory_snapshot`).
   * *Non-Additive*: Metrik tidak dapat dijumlahkan secara langsung menggunakan operasi penjumlahan dasar, melainkan harus dihitung ulang pada level grain yang diminta (contoh: rasio margin, unit cost, persentase diskon).
   * *Factless Fact Table*: Tabel fakta yang tidak memiliki nilai numerik pengukur, hanya berupa kumpulan *foreign keys* untuk mencatat kejadian (contoh: presensi siswa, registrasi promosi).

2. **Dimension Table**: Berisi atribut deskriptif yang berfungsi sebagai parameter filtering, grouping, dan slicing pada laporan analitik.
   * *Surrogate Key*: Primary key buatan (integer sequence atau deterministic cryptographic hash), independen dari sistem sumber, digunakan untuk mengisolasi DW dari mutasi OLTP serta mendukung *historisasi*.
   * *Natural Key / Business Key*: Identifier asli dari sistem OLTP operasional.
   * *Degenerate Dimension*: Dimensi yang tersimpan langsung di dalam fact table tanpa tabel dimensi tersendiri karena tidak memiliki atribut konteks tambahan (contoh: `invoice_number`, `tracking_code`).
   * *Conformed Dimension*: Dimensi konsisten yang digunakan bersama oleh lebih dari satu fact table (contoh: `dim_customer` yang dipakai oleh `fact_sales` dan `fact_support_ticket`), menjadi dasar dari arsitektur *Enterprise Data Bus*.

---

### 3. Why It Matters (Kebutuhan Enterprise)

Pada lingkungan enterprise, kueri analitik langsung terhadap basis data operasional (OLTP ter-normalisasi 3NF) menimbulkan tiga problem mendasar:
1. **Query Join Explosion**: Analisis 3NF membutuhkan join lintas 15–30 tabel untuk menghasilkan satu laporan performa penjualan, membebani CPU database dan memperpanjang waktu respons kueri dari sub-detik menjadi beberapa menit.
2. **Loss of Historical State**: Database OLTP secara konsisten menimpa (*overwrite*) data mutakhir (misalnya alamat pelanggan yang pindah), menghancurkan akurasi kalkulasi historis (*historical lineage distortion*) seperti agregasi pendapatan regional masa lalu.
3. **Chasm Trap & Fan Trap Hazards**: BI Engine atau analis yang melakukan join multi-tabel one-to-many tanpa isolasi grain rentan menghasilkan agregasi duplikat (kartesian tersembunyi), yang berujung pada bias kalkulasi metrik finansial level eksekutif.

Dengan menerapkan dimensional modeling:
* Kueri dibatasi pada struktur 1-hop join (*Fact to Dimension*).
* Histori dipertahankan secara deterministik menggunakan skema SCD Tipe 2.
* Beban I/O pada database berkurang drastis karena *partition pruning* dan *column projection* berjalan optimal pada struktur Star Schema.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur Star Schema memosisikan Fact Table sebagai pusat (hub) yang dikelilingi oleh Dimension Tables (spokes), terhubung secara referensial via Foreign Key ke Primary Surrogate Key milik dimensi.

```
       +--------------------+              +---------------------+
       |    dim_customer    |              |     dim_product     |
       +--------------------+              +---------------------+
       | PK customer_sk     |<----+        | PK product_sk       |<----+
       |    customer_id     |     |        |    product_id       |     |
       |    full_name       |     |        |    product_name     |     |
       |    tier            |     |        |    category         |     |
       |    valid_from      |     |        |    unit_cost        |     |
       |    valid_to        |     |        +---------------------+     |
       |    is_current      |     |                                    |
       +--------------------+     |                                    |
                                  |                                    |
                     +------------+-------------+                      |
                     |        fact_sales        |                      |
                     +--------------------------+                      |
                     | PK/FK  sale_date_sk      |                      |
                     | PK/FK  customer_sk       +----------------------+
                     | PK/FK  product_sk        +----------------------+
                     | PK/FK  store_sk          |                      |
                     | DD     order_number      |                      |
                     |        quantity          |                      |
                     |        unit_price        |                      |
                     |        gross_amount      |                      |
                     |        discount_amount   |                      |
                     |        net_amount        |                      |
                     +------------+-------------+                      |
                                  |                                    |
       +--------------------+     |        +---------------------+     |
       |      dim_date      |     |        |      dim_store      |     |
       +--------------------+     |        +---------------------+     |
       | PK date_sk         |<----+        | PK store_sk         |<----+
       |    calendar_date   |              |    store_id         |
       |    day_of_week     |              |    store_name       |
       |    month           |              |    city             |
       |    quarter         |              |    region           |
       |    year            |              +---------------------+
       |    is_holiday      |
       +--------------------+
```

#### Pipeline Data Flow: Dari OLTP ke Semantic Presentation
```
 [OLTP Log / CDC] 
        |
        v
 [Raw Ingestion Layer] (Bronze / Staging)
        |
        +---> [Transformation Engine] (dbt / Python Polars / DuckDB)
                     |
                     +--> 1. Generate Deterministic Surrogate Keys
                     +--> 2. Evaluate SCD2 Delta Checks
                     +--> 3. Lookup Dimensions against Fact Grain
                     |
        +------------+------------+
        |                         |
        v                         v
 [dim_* Tables]            [fact_* Tables]  (Silver / Dimensional Model)
        \                         /
         \                       /
          v                     v
   [Semantic Layer / BI Aggregation Views]  (Gold / Consumption Layer)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Surrogate Key Generation: Identity Sequence vs. Deterministic Hashing
Dalam platform data warehouse modern terdistribusi (seperti BigQuery, Snowflake, Databricks), autoincrement sequence global menimbulkan overhead sinkronisasi lintas *worker nodes*. Standar industri modern beralih menggunakan deterministic cryptographic hashing (misalnya MD5 atau SHA-256) terhadap Natural Key dan Metadata:

$$\text{Customer\_SK} = \text{MD5}(\text{COALESCE}(\text{TRIM}(\text{customer\_id}), \text{'-1'}) \,\|\, \text{valid\_from\_timestamp})$$

Keunggulan metode ini:
1. **Idempotency**: Dihasilkan secara independen tanpa dependensi baca pada state database target saat ini.
2. **Parallel Safe**: Worker node dapat memproses partisi tanpa risiko tabrakan ID urut (*lock-free pipeline*).

#### B. Mekanisme Slowly Changing Dimension (SCD)
Perubahan atribut kontekstual pada sistem sumber ditangani berdasarkan klasifikasi Kimball:

* **SCD Type 0 (Fixed / Passive)**: Nilai asli dipertahankan selamanya. Atribut historis diabaikan (contoh: `original_credit_score`).
* **SCD Type 1 (Overwrite)**: Data lama ditimpa dengan nilai baru. Tidak ada riwayat yang disimpan. Agregasi historis otomatis mengikuti atribut terbaru.
* **SCD Type 2 (Add New Row)**: Menambahkan baris baru dengan *surrogate key* baru, menandai baris lama sebagai non-aktif via `valid_to` dan flag `is_current = FALSE`.
* **SCD Type 3 (Add New Attribute)**: Menambahkan kolom baru untuk nilai lama (`previous_tier`) dan nilai saat ini (`current_tier`). Ruang lingkup histori terbatas hanya pada 1 mutasi sebelumnya.
* **SCD Type 4 (History Table)**: Tabel dimensi utama hanya menyimpan nilai mutakhir (Type 1), sedangkan setiap perubahan diarsipkan ke dalam tabel histori terpisah.

#### State Machine Transisi Baris SCD Tipe 2
```
Initial State:
[SK: 0x1A] [ID: C101] [Tier: Gold]   [Valid_From: 2023-01-01] [Valid_To: 9999-12-31] [Is_Current: TRUE]

Event: Customer C101 downgrade to 'Silver' on 2023-06-01

Step 1: Expire Old Record
[SK: 0x1A] [ID: C101] [Tier: Gold]   [Valid_From: 2023-01-01] [Valid_To: 2023-06-01] [Is_Current: FALSE]

Step 2: Insert New Record
[SK: 0x9F] [ID: C101] [Tier: Silver] [Valid_From: 2023-06-01] [Valid_To: 9999-12-31] [Is_Current: TRUE]
```

#### C. Chasm Trap vs. Fan Trap
* **Fan Trap**: Terjadi ketika sebuah tabel master di-join dengan dua tabel detail yang tidak sejajar relasinya melalui hierarki berantai $A \to B \to C$, di mana $B$ dan $C$ sama-sama memiliki relasi 1-to-many. Kueri agregasi pada tingkat $B$ akan berlipat ganda (*inflated*) karena Cartesian product dari $C$.
* **Chasm Trap**: Terjadi ketika sebuah fact table dihubungkan ke dua tabel dimensi berbeda, namun analis mencoba mengagregasi data di antara dua tabel detail yang berbeda grain melalui fact table perantara tanpa normalisasi grain, menyebabkan metrik dari kedua cabang berlipat ganda (*cross-product explosion*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end pemodelan dimensional menggunakan **Python 3.11** dengan modul **DuckDB** untuk mensimulasikan Modern Data Warehouse engine yang memproses SCD Type 2 Dimension dan Fact ingestion.

```python
"""
Dimensional Modeling Pipeline Implementation.
Includes DDL generation, SCD Type 2 processing, and Fact table aggregation.
Engine: DuckDB (ANSI SQL compliant, vectorized analytics execution).
"""

from __future__ import annotations
import hashlib
from datetime import datetime, date
from typing import List, Dict, Any
import duckdb


class DimensionalDataWarehouse:
    def __init__(self, db_path: str = ":memory:") -> None:
        """Inisialisasi koneksi OLAP engine."""
        self.con = duckdb.connect(db_path)
        self.initialize_schema()

    def initialize_schema(self) -> None:
        """Membuat struktur tabel Star Schema produksi."""
        self.con.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_dim_customer;

        -- Dimension: dim_customer (SCD Type 2)
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_sk VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL,
            full_name VARCHAR NOT NULL,
            email VARCHAR NOT NULL,
            tier VARCHAR NOT NULL,
            valid_from TIMESTAMP NOT NULL,
            valid_to TIMESTAMP NOT NULL,
            is_current BOOLEAN NOT NULL
        );

        -- Dimension: dim_product (SCD Type 1)
        CREATE TABLE IF NOT EXISTS dim_product (
            product_sk VARCHAR PRIMARY KEY,
            product_id VARCHAR NOT NULL,
            product_name VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            unit_cost DECIMAL(12, 2) NOT NULL
        );

        -- Dimension: dim_date (Conformed Dimension)
        CREATE TABLE IF NOT EXISTS dim_date (
            date_sk INTEGER PRIMARY KEY,
            full_date DATE NOT NULL,
            day_name VARCHAR NOT NULL,
            month_name VARCHAR NOT NULL,
            calendar_quarter INTEGER NOT NULL,
            calendar_year INTEGER NOT NULL
        );

        -- Fact Table: fact_sales (Transactional Grain)
        CREATE TABLE IF NOT EXISTS fact_sales (
            sale_id VARCHAR PRIMARY KEY,
            date_sk INTEGER NOT NULL,
            customer_sk VARCHAR NOT NULL,
            product_sk VARCHAR NOT NULL,
            order_number VARCHAR NOT NULL, -- Degenerate Dimension
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(12, 2) NOT NULL,
            gross_amount DECIMAL(12, 2) NOT NULL,
            discount_amount DECIMAL(12, 2) NOT NULL,
            net_amount DECIMAL(12, 2) NOT NULL,
            FOREIGN KEY (customer_sk) REFERENCES dim_customer(customer_sk),
            FOREIGN KEY (product_sk) REFERENCES dim_product(product_sk),
            FOREIGN KEY (date_sk) REFERENCES dim_date(date_sk)
        );
        """)

    @staticmethod
    def generate_surrogate_key(*args: Any) -> str:
        """Menghasilkan deterministic MD5 hash key untuk mengeliminasi dependensi sequence lock."""
        payload = "_".join(str(val).strip().upper() for val in args if val is not None)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def populate_date_dimension(self, start_date: date, end_date: date) -> None:
        """Populate Date Dimension secara programatis."""
        self.con.execute("""
        INSERT INTO dim_date
        SELECT 
            CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_sk,
            CAST(d AS DATE) AS full_date,
            dayname(d) AS day_name,
            monthname(d) AS month_name,
            quarter(d) AS calendar_quarter,
            year(d) AS calendar_year
        FROM generate_series(
            TIMESTAMP ?, 
            TIMESTAMP ?, 
            INTERVAL 1 DAY
        ) AS t(d)
        ON CONFLICT DO NOTHING;
        """, [start_date, end_date])

    def upsert_scd2_customer(self, incoming_records: List[Dict[str, Any]], effective_timestamp: datetime) -> None:
        """
        Memproses mutasi Customer Dimensi dengan pendekatan SCD Type 2 secara idempoten.
        """
        for record in incoming_records:
            cid = record["customer_id"]
            name = record["full_name"]
            email = record["email"]
            tier = record["tier"]

            # 1. Cek record aktif saat ini
            current = self.con.execute("""
                SELECT customer_sk, tier 
                FROM dim_customer 
                WHERE customer_id = ? AND is_current = TRUE
            """, [cid]).fetchone()

            if current is None:
                # Insert baru pertama kali
                new_sk = self.generate_surrogate_key(cid, effective_timestamp.isoformat())
                self.con.execute("""
                    INSERT INTO dim_customer VALUES (?, ?, ?, ?, ?, ?, '9999-12-31 00:00:00', TRUE)
                """, [new_sk, cid, name, email, tier, effective_timestamp])
            else:
                current_sk, current_tier = current
                if current_tier != tier:
                    # Terjadi perubahan atribut penting (SCD2 trigger)
                    # A: Expire baris lama
                    self.con.execute("""
                        UPDATE dim_customer 
                        SET valid_to = ?, is_current = FALSE
                        WHERE customer_sk = ?
                    """, [effective_timestamp, current_sk])

                    # B: Insert baris baru
                    new_sk = self.generate_surrogate_key(cid, effective_timestamp.isoformat())
                    self.con.execute("""
                        INSERT INTO dim_customer VALUES (?, ?, ?, ?, ?, ?, '9999-12-31 00:00:00', TRUE)
                    """, [new_sk, cid, name, email, tier, effective_timestamp])

    def ingest_fact_sales(self, transactions: List[Dict[str, Any]]) -> None:
        """
        Memproses transaksi OLTP ke Fact Table dengan integrasi valid SK lookup.
        """
        for tx in transactions:
            tx_time: datetime = tx["timestamp"]
            date_sk = int(tx_time.strftime("%Y%m%d"))

            # Resolve SCD Type 2 Dimension Customer pada point-in-time transaksi
            customer_match = self.con.execute("""
                SELECT customer_sk 
                FROM dim_customer 
                WHERE customer_id = ? 
                  AND valid_from <= ? 
                  AND valid_to > ?
            """, [tx["customer_id"], tx_time, tx_time]).fetchone()

            if not customer_match:
                # Handle late arriving dimension: assign ke ghost/dummy default dimension
                customer_sk = "-1"
            else:
                customer_sk = customer_match[0]

            gross = tx["quantity"] * tx["unit_price"]
            net = gross - tx["discount_amount"]
            sale_id = self.generate_surrogate_key(tx["order_number"], tx["product_id"])

            self.con.execute("""
                INSERT INTO fact_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (sale_id) DO NOTHING
            """, [
                sale_id,
                date_sk,
                customer_sk,
                tx["product_sk"],
                tx["order_number"],
                tx["quantity"],
                tx["unit_price"],
                gross,
                tx["discount_amount"],
                net
            ])


# =====================================================================
# Unit Validation & Execution Demo
# =====================================================================
if __name__ == "__main__":
    dw = DimensionalDataWarehouse()

    # 1. Inisialisasi Conformed Dimensions
    dw.populate_date_dimension(date(2023, 1, 1), date(2023, 1, 10))
    
    prod_sk = dw.generate_surrogate_key("P100")
    dw.con.execute("""
        INSERT INTO dim_product VALUES (?, 'P100', 'Enterprise Analytics Engine', 'Software', 1500.00)
    """, [prod_sk])

    # 2. Registrasi Customer Baru (T0: 2023-01-01)
    t0 = datetime(2023, 1, 1, 10, 0, 0)
    dw.upsert_scd2_customer([{
        "customer_id": "C01",
        "full_name": "Budi Santoso",
        "email": "budi@megacorp.id",
        "tier": "Standard"
    }], effective_timestamp=t0)

    # 3. Transaksi Pertama (Terjadi pada 2023-01-02 saat status masih 'Standard')
    dw.ingest_fact_sales([{
        "order_number": "INV-001",
        "product_id": "P100",
        "product_sk": prod_sk,
        "customer_id": "C01",
        "timestamp": datetime(2023, 1, 2, 14, 30, 0),
        "quantity": 2,
        "unit_price": 1500.00,
        "discount_amount": 0.00
    }])

    # 4. Mutasi Profil SCD2 (T1: 2023-01-05 Budi upgrade ke 'VIP')
    t1 = datetime(2023, 1, 5, 9, 0, 0)
    dw.upsert_scd2_customer([{
        "customer_id": "C01",
        "full_name": "Budi Santoso",
        "email": "budi@megacorp.id",
        "tier": "VIP"
    }], effective_timestamp=t1)

    # 5. Transaksi Kedua (Terjadi pada 2023-01-06 saat status sudah 'VIP')
    dw.ingest_fact_sales([{
        "order_number": "INV-002",
        "product_id": "P100",
        "product_sk": prod_sk,
        "customer_id": "C01",
        "timestamp": datetime(2023, 1, 6, 11, 0, 0),
        "quantity": 1,
        "unit_price": 1500.00,
        "discount_amount": 300.00 # Diskon VIP
    }])

    # 6. Evaluasi Pelaporan Analitik Point-in-Time
    print("=== Laporan Historis Penjualan Berdasarkan Tier Pelanggan Saat Transaksi ===")
    result = dw.con.execute("""
        SELECT 
            c.tier AS customer_tier_at_transaction,
            COUNT(f.sale_id) AS total_orders,
            SUM(f.gross_amount) AS total_gross,
            SUM(f.discount_amount) AS total_discount,
            SUM(f.net_amount) AS total_net
        FROM fact_sales f
        JOIN dim_customer c ON f.customer_sk = c.customer_sk
        JOIN dim_date d ON f.date_sk = d.date_sk
        GROUP BY c.tier
    """).fetchall()

    for row in result:
        print(f"Tier: {row[0]} | Orders: {row[1]} | Gross: ${row[2]:,.2f} | Discount: ${row[3]:,.2f} | Net: ${row[4]:,.2f}")
```

---

### 7. Edge Cases & Failure Modes

#### 1. Late-Arriving Facts and Late-Arriving Dimensions
* *Mekanisme Kegagalan*: Fact table menerima baris transaksi dengan timestamp historis, namun record dimensi yang relevan belum pernah termuat ke DW (*Dimension not found*), atau record SCD Tipe 2 telah mengalami pergeseran window validity.
* *Solusi Produksi*:
  * Pasang **Default Ghost Record** (`customer_sk = '-1'`, `full_name = 'UNKNOWN / UNRESOLVED'`) untuk mencegah pelanggaran Foreign Key Constraint.
  * Masukkan transaksi ke tabel penampungan *Late Ingestion Buffer*.
  * Ketika record dimensi historis akhirnya masuk, picu *backfill process* untuk meregenerasi point-in-time surrogate key pada fact table.

#### 2. Hash Collision pada Deterministic Surrogate Keys
* *Mekanisme Kegagalan*: Algoritma hash yang terlalu sederhana (seperti CRC32) dapat menghasilkan nilai key identik untuk dua natural key berbeda bila volume baris mencapai puluhan juta.
* *Solusi Produksi*: Gunakan format standar minimal **MD5** (128-bit) atau **SHA-256** (256-bit). Selalu tambahkan pembatas pemisah (*delimiter*) unik antar atribut: `MD5(colA || '|#|' || colB)` guna menghindari kolisi karena pergeseran karakter string (contoh: 'AB' + 'C' vs 'A' + 'BC').

#### 3. SCD Type 2 Microsecond Overlap Anomaly
* *Mekanisme Kegagalan*: Ketika record lama ditutup pada `valid_to = 2023-01-01 10:00:00` dan record baru dibuka pada `valid_from = 2023-01-01 10:00:00`, kueri yang menggunakan kondisi inkusif `BETWEEN valid_from AND valid_to` akan menghasilkan **2 baris kembar** (menggandakan hasil agregasi metrik).
* *Solusi Produksi*:
  * Standarisasi predikat analitik menggunakan open-interval kanan: `event_time >= valid_from AND event_time < valid_to`.
  * Atau simpan `valid_to` record lama dengan offset microsecond: `valid_to = record_baru.valid_from - INTERVAL '1 MICROSECOND'`.

---

### 8. Trade-offs & Alternatif Solusi

| Kriteria Analisis | Kimball Star Schema | Snowflake Schema | One Big Table (OBT) / De-normalized |
| :--- | :--- | :--- | :--- |
| **Arsitektur Join** | 1-Hop Join (Fact ke Dimensi) | Multi-Hop Join (Normalisasi Dimensi lanjutan) | 0-Hop Join (Semua kolom digabung ke satu tabel datar) |
| **Query Performance** | **Tinggi**: Sangat cepat pada engine konvensional dan columnar. | **Sedang**: Latensi tinggi akibat *cost of joins* berantai. | **Sangat Tinggi**: Scan berurutan sangat cepat pada Cloud DWH modern. |
| **Penyimpanan Storage** | **Efisien**: Atribut teks terisolasi di tabel dimensi. | **Paling Efisien**: Redundansi diminimalkan (mirip 3NF). | **Boros**: Redundansi teks berulang di miliaran baris fact. |
| **Kompleksitas ETL** | **Sedang**: Mengelola SCD dan lookup surrogate key. | **Tinggi**: Dependensi antar child-parent dimension cascade. | **Rendah**: ELT flattening tanpa pemeliharaan relasi referensial. |
| **Skenario Rekomendasi**| Core Enterprise Data Model, Metrik BI Kompleks, Multiple Business Processes. | Domain data dengan hierarki mendalam yang jarang berubah. | Real-time analytics, ClickHouse/BigQuery log ingestion, Single-dashboard views. |

---

### 9. Best Practices & Standard Industri

1. **Aturan Deklarasi Grain yang Baku**: Selalu dokumentasikan grain fisik fact table dalam bentuk deklarasi deklaratif sebelum menulis kode:
   > *"Satu baris pada `fact_sales` merepresentasikan satu unit baris item transaksi barang pada satu struk checkout kasir."*
2. **Enterprise Bus Matrix Architecture**: Jangan membangun mart terisolasi (*data silos*). Gunakan *Conformed Dimensions* (dim_date, dim_customer, dim_geography) yang dipetakan pada *Enterprise Data Bus Architecture* sehingga kueri lintas proses bisnis (seperti Sales vs. Inventory) dapat dilakukan secara valid.
3. **Surrogate Key Sanitization**:
   * Jangan gunakan tipe data string bebas tanpa panjang tetap jika sistem database membedakan performa indexing.
   * Pada modern cloud DWH (Snowflake/BigQuery), gunakan `MD5_BINARY()` atau simpan dalam format hexadecimal fixed string.
4. **Isolasi Logika Semantic Layer**: Jangan pernah menaruh *business calculations* (seperti `Gross Margin % = (Revenue - COGS) / Revenue`) langsung ter-hardcode di dashboard BI. Letakkan pada semantic definition layer (dbt MetricFlow, LookML, atau Cube) yang bersandar di atas Fact Table.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Senior Analytics Engineer di platform retail *OmniStore*. Anda diminta merancang data mart untuk melacak performa promosi diskon produk dan mendeteksi anomali pada margin keuntungan secara point-in-time.

#### Langkah Pengerjaan

##### Langkah 1: Siapkan Schema DDL (Jalankan pada Environment DuckDB atau PostgreSQL)
```sql
CREATE TABLE raw_transactions (
    txn_id VARCHAR,
    customer_id VARCHAR,
    product_id VARCHAR,
    txn_date TIMESTAMP,
    qty INTEGER,
    price DECIMAL(10,2),
    discount DECIMAL(10,2)
);

INSERT INTO raw_transactions VALUES
('TX101', 'CUST_A', 'PROD_X', '2023-11-01 08:30:00', 3, 100.0, 10.0),
('TX102', 'CUST_B', 'PROD_Y', '2023-11-01 09:15:00', 1, 250.0, 0.0),
('TX103', 'CUST_A', 'PROD_X', '2023-11-02 14:00:00', 2, 100.0, 20.0);
```

##### Langkah 2: Bangun Dimension SCD Tipe 2 untuk Profil Diskon Pelanggan
```sql
CREATE TABLE dim_customer_segment (
    segment_sk VARCHAR PRIMARY KEY,
    customer_id VARCHAR,
    segment_tier VARCHAR,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN
);

-- Inisialisasi State Historis
INSERT INTO dim_customer_segment VALUES
(md5('CUST_A_2023-01-01'), 'CUST_A', 'REGULAR', '2023-01-01 00:00:00', '2023-11-02 00:00:00', FALSE),
(md5('CUST_A_2023-11-02'), 'CUST_A', 'PREMIUM', '2023-11-02 00:00:00', '9999-12-31 00:00:00', TRUE),
(md5('CUST_B_2023-01-01'), 'CUST_B', 'REGULAR', '2023-01-01 00:00:00', '9999-12-31 00:00:00', TRUE);
```

##### Langkah 3: Eksekusi Point-in-Time Fact Ingestion
Susun kueri ELT untuk memuat data dari `raw_transactions` ke `fact_orders` dengan surrogate key matching yang akurat terhadap dimensi SCD Tipe 2.

```sql
CREATE TABLE fact_orders AS
SELECT 
    t.txn_id AS order_id,
    CAST(strftime(t.txn_date, '%Y%m%d') AS INTEGER) AS date_sk,
    c.segment_sk,
    t.product_id,
    t.qty,
    t.price,
    t.discount,
    (t.qty * t.price) - t.discount AS net_revenue
FROM raw_transactions t
JOIN dim_customer_segment c 
    ON t.customer_id = c.customer_id
    AND t.txn_date >= c.valid_from 
    AND t.txn_date < c.valid_to;
```

##### Langkah 4: Validasi Integritas Hasil (Verification Queries)
Pastikan bahwa pesanan `TX101` dari `CUST_A` terikat pada tier `REGULAR`, sementara pesanan `TX103` terikat pada tier `PREMIUM`.

```sql
SELECT 
    f.order_id,
    c.customer_id,
    c.segment_tier,
    f.net_revenue
FROM fact_orders f
JOIN dim_customer_segment c ON f.segment_sk = c.segment_sk
ORDER BY f.order_id;
```

*Output yang Diharapkan:*
```text
┌──────────┬─────────────┬──────────────┬─────────────┐
│ order_id │ customer_id │ segment_tier │ net_revenue │
├──────────┼─────────────┼──────────────┼─────────────┤
│ TX101    │ CUST_A      │ REGULAR      │ 290.00      │
│ TX102    │ CUST_B      │ REGULAR      │ 250.00      │
│ TX103    │ CUST_A      │ PREMIUM      │ 180.00      │
└──────────┴─────────────┴──────────────┴─────────────┘
```
Jika `TX101` dan `TX103` menghasilkan tier yang berbeda secara akurat sesuai urutan tanggal transaksinya, maka pemodelan dimensional SCD Tipe 2 point-in-time pipeline Anda dinyatakan valid dan memenuhi standar produksi.