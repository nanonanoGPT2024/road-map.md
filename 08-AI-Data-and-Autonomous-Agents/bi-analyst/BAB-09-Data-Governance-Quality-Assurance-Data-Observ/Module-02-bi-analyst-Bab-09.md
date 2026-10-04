# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Data Governance, QA, & Observability)

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
- **Merancang & Mengimplementasikan Automated Data Quality Frameworks**: Mengintegrasikan framework pengujian data deklaratif (seperti Soda Core / Great Expectations / dbt tests) ke dalam orkestrasi pipeline data dan CI/CD pipeline analitik.
- **Membangun Arsitektur Data Observability Multi-Layer**: Menerapkan 5 pilar observability (Freshness, Volume, Schema, Quality, Lineage) secara terprogram menggunakan metadata engine berbasis open-standard (OpenLineage, OpenTelemetry).
- **Menegakkan Data Contracts & Circuit Breakers**: Membangun mekanisme pencegahan (prevention) pada batas ingestion dan semantic layer guna mengisolasi silent data corruption sebelum menjangkau metrik eksekutif di dashboard BI.
- **Mengonfigurasi Enterprise Data Governance & Lineage**: Mengimplementasikan fine-grained access control (RBAC/ABAC), dynamic PII masking, dan audit trail end-to-end dari raw ingestion hingga BI Semantic Layer.
- **Menganalisis Trade-off Arsitektural**: Menyeimbangkan latensi deteksi anomali, beban komputasi warehouse (cost), ketersediaan data, dan kompleksitas operasional pada skala data enterprise terdistribusi.

---

## 2. Prerequisites
Peserta diwajibkan memiliki fondasi operasional dan konseptual berikut:
- **Data Warehousing & SQL**: Penguasaan mendalam atas SQL analitik (Window functions, CTE, Information Schema metadata query) pada platform Modern Data Stack (Snowflake, BigQuery, atau Databricks/Trino).
- **Data Modeling & Transformation**: Pengalaman produksi dengan dbt (data build tool), termasuk pemahaman model dimensional (Kimball), generic/singular tests, dan macros.
- **Orchestration & DevOps**: Pemahaman dasar mengenai orkestrasi data (Apache Airflow / Dagster) serta CI/CD pipelines (GitHub Actions / GitLab CI).
- **Python**: Kemampuan menulis skrip Python modular (Python 3.10+) berorientasi testing dan integrasi REST API.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 The 5 Pillars of Modern Data Observability
Dalam sistem BI enterprise, sekadar memeriksa status job `SUCCESS` pada scheduler tidak menjamin data di dashboard akurat. Data observability mengekstraksi dan mengevaluasi status kesehatan pipeline melalui lima dimensi:
1. **Freshness**: Mengetahui kapan tabel terakhir diperbarui dan apakah frekuensi pembaruan selaras dengan SLA downstream BI.
2. **Volume**: Memverifikasi kelengkapan baris data (*row count verification*), mendeteksi anomali *under-ingestion* (akibat API drop) atau *over-ingestion* (duplikasi payload).
3. **Schema**: Melacak mutasi struktural (*column drops*, *data type widening/narrowing*, *renaming*) yang berpotensi memutus query BI semantic model.
4. **Quality**: Memvalidasi kepatuhan nilai data terhadap aturan bisnis deklaratif (contoh: persentase `null`, keunikan, *accepted values*, validitas referensial/foreign key).
5. **Lineage**: Memetakan dependency graph secara terarah (DAG) dari sistem sumber (OLTP CDC), staging warehouse, transformasional mart, semantic layer, hingga downstream dashboard (Tableau/PowerBI/Looker).

### 3.2 Dynamic Ingestion Circuit Breaker Architecture
Untuk mencegah polusi data (*data pollution*) masuk ke reporting layer, arsitektur produksi menerapkan pola **Data Circuit Breaker**:

```
[OLTP / Ingestion Source]
          │
          ▼
   [Landing / Raw]
          │
          ▼
   [Staging Layer] ──> [Data Contract Verification Engine]
                              │
                    ┌─────────┴─────────┐
                 [PASSED]            [FAILED]
                    │                   │
                    ▼                   ▼
            [Production Mart]    [Dead-Letter Quarantine]
                    │                   │
                    ▼                   ▼
           [BI Semantic Layer]   [PagerDuty / Slack Alert]
                                 [Execution Halted]
```

- **Runtime Schema Validation**: Schema dievaluasi terhadap spesifikasi JSON Schema atau Avro/Protobuf contract.
- **Statistical Profiling Engine**: Engine menghitung ringkasan statistik (mean, variance, null rate) dan membandingkannya dengan sliding window data historis (misal 14 hari terakhir) menggunakan Z-Score atau interquartile range (IQR) untuk mendeteksi outlier sebelum mempromosikan tabel staging ke target production.
- **Zero-Copy Cloning / Blue-Green Table Swap**: Pada engine seperti Snowflake, QA dijalankan pada cloned table. Swap hanya terjadi jika seluruh kontrak data berstatus passed.

### 3.3 Unified Metadata Collection Mechanism (OpenLineage & Semantic Layer)
Lineage end-to-end tidak dibangun secara manual, melainkan melalui **event emission**:
- Saat dbt run atau query SQL dieksekusi, parser mengekstrak Abstract Syntax Tree (AST).
- Input datasets, output datasets, dan column-level transformations dikonversi menjadi metadata event berbasis standar **OpenLineage**.
- Event dikirim secara asinkronus via HTTP/Kafka menuju central metadata backend (seperti Marquez, Apache DataHub, atau OpenMetadata).
- Semantic layer (misal: dbt Semantic Layer, Cube.js, atau Looker LookML) mengikat metadata tersebut ke logical dimension/metrics yang diekspos ke BI analyst, sehingga impact analysis terhadap suatu metrik bisnis dapat dilacak balik langsung ke tingkat source database column.

---

## 4. Why & What

| Dimensi | Pendekatan Reaktif Tradisional | Modern Production Observability & Governance |
| :--- | :--- | :--- |
| **Pendeteksian Masalah** | Pengguna bisnis komplain dashboard salah/kosong di Senin pagi. | Incident alert terpicu secara otomatis dalam hitungan menit saat staging data terindikasi anomali. |
| **Batas Validasi (Boundary)** | Tidak ada data contract; schema database transactional bebas berubah tanpa notifikasi ke tim BI. | Data Contract ditegakkan di batas produsen data (CI/CD pipeline produsen memblokir breaking migration). |
| **Data Lineage** | Diagram statis di Confluence/Draw.io yang kedaluwarsa setelah 2 minggu. | Lineage terotomatisasi secara dinamis pada level kolom (Column-Level Lineage) berbasis parsing AST query engine. |
| **Quality Control** | Query ad-hoc `SELECT COUNT(*)` manual yang dijalankan analis secara berkala. | Pengujian terotomatisasi (Automated assertions) yang terintegrasi pada orchestrator DAG dan CI/CD deployment. |
| **Pemisahan Akses (Access Control)** | Seluruh analis memiliki akses baca langsung ke raw tables; PII diakses tanpa logging terpusat. | Centralized Governance via RBAC/ABAC; hashing/masking dinamis terhadap PII; audit log query dianalisis secara berkala. |

---

## 5. How (Workflow Detail)

Alur kerja implementasi QA, Observability, dan Governance kelas produksi mencakup tahapan berikut:

```
[1. Contract Definition] 
   └── Produsen data & Analis BI menyepakati schema & SLA (YAML spec)
[2. CI/CD Pre-merge Testing]
   └── PR ditrigger: dbt dry-run, Soda Core static tests, backward-compatibility check
[3. Ingestion & Dynamic Quarantine]
   └── Data masuk ke staging -> Jalankan inline assertion test
   ├── If Fail: Routing ke Quarantine Schema, kirim webhook ke Incident Manager
   └── If Pass: Eksekusi Transformasi Dimensional
[4. Post-Transformation Observability]
   └── Run Freshness & Volume Anomaly Detection (OpenLineage emitted)
[5. Semantic Layer Enforcement & Dynamic Masking]
   └── Access Policy dievaluasi: User Group A -> Plaintext; User Group B -> Masked PII
[6. Monitoring Dashboard & Feedback Loop]
   └── Track SLA, Downstream Impact, dan MTTR incident
```

1. **Definisi Kontrak**: Schema dan threshold kualitas didefinisikan secara deklaratif di repository bersama (git-tracked).
2. **Validasi CI/CD**: Setiap perubahan model dbt atau DDL database diuji menggunakan CI runner pada isolated environment (contoh: ephemeral schema).
3. **Runtime Ingestion & Circuit Breaking**: ETL/ELT mengeksekusi assertion. Jika ambang batas pelanggaran kritis terlampaui, pipeline halted untuk mencegah data kotor mencemari dashboard.
4. **Metrik & Anomaly Detection**: Observability tools mengumpulkan run-metrics, memperbarui profil statistik run-time, dan mengidentifikasi anomali volumetrik atau distribusi data.
5. **Enforcement PII & Security**: Database policies secara dinamis menyamarkan kolom sensitif (email, NIK, nomor kartu) berdasarkan role pengguna BI.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pemurnian Air Kota
Bayangkan pipeline data seperti sistem penyediaan air minum perkotaan:
- **Raw Data Ingestion** adalah pengambilan air dari sungai (bisa mengandung pasir, lumpur, atau polutan tak terduga).
- **Data Contracts** adalah regulasi industri yang melarang pabrik di hulu membuang limbah langsung ke aliran sungai tanpa spesifikasi tertentu.
- **Circuit Breaker & QA Testing** adalah katup filter sensorik otomatis. Jika kandungan zat berbahaya melampaui ambang batas, sensor menutup pipa utama dan mengalihkan air kotor ke tangki isolasi (Quarantine).
- **Data Observability** adalah rangkaian instrumen monitoring real-time (sensor tekanan air, debit aliran, indikator kejernihan) yang memberi peringatan dini sebelum air keruh keluar dari keran warga.
- **BI Layer** adalah air bersih yang mengalir langsung ke rumah penduduk; pengguna langsung mengonsumsinya tanpa harus memfilternya sendiri.

### Diagram Arsitektur Produksi

```
========================================================================================================
                                     DATA OBSERVABILITY & GOVERNANCE ARCHITECTURE
========================================================================================================

  +-----------------------+     +------------------------+
  | Application Database  |     | Third-Party Ingestion  |
  |     (PostgreSQL)      |     |      (REST APIs)       |
  +-----------+-----------+     +-----------+------------+
              |                             |
              | Change Data Capture         | Batch Extraction
              v                             v
  +------------------------------------------------------+
  |                  RAW / LANDING ZONE                  |
  |             (Snowflake RAW_DB / S3 Bucket)           |
  +---------------------------+--------------------------+
                              |
                              v
  +------------------------------------------------------+
  |              STAGING LAYER & CIRCUIT BREAKER          |
  |  +------------------------------------------------+  |
  |  | Soda Core / GE Data Contract Validation Engine |  |
  |  +-----------------------+------------------------+  |
  +--------------------------|---------------------------+
                             |
             [Passes Contract Verification?]
              /                             \
        YES  /                               \  NO
            v                                 v
  +------------------------+      +-------------------------------+
  |   TRANSFORMATION LAYER |      | QUARANTINE / DEAD-LETTER ZONE |
  | (dbt Core / OpenLineage|      |  (Alert to Data Platform via  |
  |   Metadata Emission)   |      |   PagerDuty / Slack Webhook)  |
  +-----------+------------+      +-------------------------------+
              |
              v
  +------------------------------------------------------+
  |                    ANALYTICS MART                    |
  |        (Dimensional Kimball Models - Star Schema)    |
  +---------------------------+--------------------------+
                              |
                              v
  +------------------------------------------------------+
  |             GOVERNANCE & ACCESS CONTROL              |
  |  - Dynamic Column-Level Masking (PII / Sensitive)    |
  |  - Row-Level Security (RLS by Tenant / Region)       |
  |  - Audit Log Tracking (Access Logging Engine)        |
  +---------------------------+--------------------------+
                              |
                              v
  +------------------------------------------------------+
  |                  BI SEMANTIC LAYER                   |
  |        (dbt Semantic Layer / Cube.js / LookML)       |
  +---------------------------+--------------------------+
                              |
                              v
  +------------------------------------------------------+
  |              DOWNSTREAM CONSUMPTION (BI)             |
  |      [Tableau]       [PowerBI]       [Apache Superset]
  +------------------------------------------------------+
========================================================================================================
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: dbt Generic & Custom Data Tests
Implementasi pengujian deklaratif pada layer transformasi analitik.

```yaml
# models/staging/stg_ecommerce__orders.yml
version: 2

models:
  - name: stg_ecommerce__orders
    description: "Tabel transaksi staging hasil pembersihan raw orders"
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: status
        tests:
          - accepted_values:
              values: ['placed', 'shipped', 'delivered', 'cancelled', 'returned']
      - name: order_total_amount
        tests:
          - not_null
          - assert_positive_value # Singular/Custom generic test

      - name: customer_id
        tests:
          - relationships:
              to: ref('stg_ecommerce__customers')
              field: customer_id
```

```sql
-- tests/generic/assert_positive_value.sql
-- Custom macro assertion test: Return baris data yang melanggar kondisi
{% test assert_positive_value(model, column_name) %}
SELECT
    {{ column_name }} AS failing_value,
    COUNT(*) AS occurrence_count
FROM {{ model }}
WHERE {{ column_name }} < 0
GROUP BY {{ column_name }}
HAVING COUNT(*) > 0
{% endtest %}
```

---

### 7.2 Practical Example: Enterprise Data Contract Enforcement Engine
Skrip produksi Python berbasis Soda Core SDK yang berfungsi sebagai *circuit breaker* pada pipeline ingestion. Jika pengujian kontrak gagal, data tidak dimuat ke tabel produksi analitik, dan event peringatan berstruktur JSON di-dispatch.

```python
#!/usr/bin/env python3
"""
File: run_data_contract_pipeline.py
Deskripsi: Memvalidasi Staging Data menggunakan Soda Core Contract Engine
sebelum data dipromosikan ke Analytics Production Mart.
"""

import sys
import json
import logging
from typing import Dict, Any
from soda.scan import Scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DataQualityGate")

# Definisi file konfigurasi dan contract checks
SODA_CONFIGURATION_PATH = "soda/configuration.yml"
SODA_CONTRACT_CHECKS_PATH = "soda/contracts/orders_ingestion_checks.yml"

def execute_data_quality_gate() -> None:
    logger.info("Menginisialisasi Soda Core Scanning Engine...")
    scan = Scan()
    scan.set_scan_definition_name("Daily_Orders_Ingestion_Gate")
    scan.set_data_source_name("snowflake_warehouse")

    # Load koneksi database
    try:
        scan.add_configuration_yaml_file(SODA_CONFIGURATION_PATH)
    except Exception as exc:
        logger.error(f"Gagal memuat konfigurasi koneksi: {exc}")
        sys.exit(2)

    # Load file contract assertion
    try:
        scan.add_sodacl_yaml_file(SODA_CONTRACT_CHECKS_PATH)
    except Exception as exc:
        logger.error(f"Gagal memuat check assertions: {exc}")
        sys.exit(2)

    logger.info("Mengeksekusi Scan Data Quality assertions...")
    scan.execute()

    # Ekstraksi hasil scan
    scan_results = scan.get_scan_results()
    has_failures = scan.has_check_fails()
    has_errors = scan.has_scan_errors()

    summary: Dict[str, Any] = {
        "metrics_evaluated": len(scan_results.get("checks", [])),
        "failures": has_failures,
        "errors": has_errors,
    }
    logger.info(f"Scan Selesai: {json.dumps(summary)}")

    # Parsing log individual error
    for check in scan_results.get("checks", []):
        outcome = check.get("outcome")
        check_name = check.get("name")
        if outcome in ["fail", "error"]:
            logger.error(f"Test Rule Violation: [{check_name}] => Outcome: {outcome.upper()}")
            for diagnostic in check.get("diagnostics", {}).get("blocks", []):
                logger.error(f"Detail Diagnostik: {diagnostic}")

    # Circuit Breaker Logic
    if has_failures or has_errors:
        logger.critical(
            "CIRCUIT BREAKER TRIGGERED: Kualitas data melanggar Data Contract! "
            "Pipeline dihentikan. Memblokir promosi data ke layer Analytics Mart."
        )
        # Di environment produksi, emit alert ke PagerDuty / Webhook / Dead Letter Queue
        sys.exit(1)

    logger.info("SELURUH DATA CONTRACT VALID: Data staging dipromosikan ke Analytics Mart.")
    sys.exit(0)

if __name__ == "__main__":
    execute_data_quality_gate()
```

```yaml
# soda/contracts/orders_ingestion_checks.yml
# Aturan deklaratif SodaCL yang dieksekusi oleh Python Engine
checks for STG_ORDERS_RAW:
  # Schema Enforcement
  - schema:
      name: Ensure required schema strictly matches contract
      fail:
        when wrong column type:
          ORDER_ID: varchar
          CUSTOMER_ID: varchar
          TOTAL_AMOUNT: numeric(18, 4)
          TRANSACTION_TIMESTAMP: timestamp_ntz
        when forbidden column present:
          - SSN
          - CREDIT_CARD_RAW
          - INTERNAL_TEST_FLAG

  # Volume Validation
  - row_count between 1000 and 500000:
      name: Ingestion volume is within nominal operational range

  # Quality Assertions
  - missing_count(ORDER_ID) = 0:
      name: ORDER_ID primary key must never be null
  - duplicate_count(ORDER_ID) = 0:
      name: ORDER_ID must be globally unique
  - invalid_percent(TOTAL_AMOUNT) < 0.01:
      valid min: 0.00
      name: Negative monetary amounts must be under 0.01% (anomalies)

  # Freshness Checks
  - freshness(TRANSACTION_TIMESTAMP) < 4h:
      name: Data must not be older than 4 hours
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: FinTech Global (Payment & Digital Lending Platform)
- **Kondisi Awal**: Menangani 40 juta transaksi harian di 4 negara Asia Tenggara.
- **Masalah**:
  1. Tim Product Engineering merilis update pada microservice payment gateway: field `currency_code` (awalnya ISO string `IDR`, `SGD`) diperbarui tanpa koordinasi menjadi format integer ID (`360`, `702`).
  2. Transformasi downstream dbt gagal parsing silently, mengubah nilai aggregate volume transaksi menjadi `NULL` pada reporting mart.
  3. Dashboard Tableau C-Level menyajikan penurunan revenue 80% secara mendadak, memicu eskalasi darurat tingkat direksi.
  4. Analisis investigasi manual memakan waktu 16 jam untuk menemukan akar masalah (*root cause*) karena tidak ada lineage metadata otomatis.
- **Solusi yang Diterapkan**:
  1. **Schema Migration Gatekeeper**: Dipasang GitHub Actions CI yang terintegrasi dengan tool data contract. Script memverifikasi staging queries terhadap JSON Schema schema registry per payment event.
  2. **dbt Semantic Layer & Elementary Observability**: Dipasang metadata hook yang memantau anomali volume dan missing values pada setiap incremental run dbt.
  3. **Data Circuit Breaker via Ephemeral Staging**: Data raw disaring melalui landing table ephemeral. Apabila terjadi schema mismatch atau lonjakan rasio null > 0.01%, load data ke `dim_merchants` dan `fct_transactions` otomatis dibatalkan, mempertahankan state data terakhir yang valid.
  4. **Dynamic Column Masking via Snowflake**: Menegakkan kepatuhan PCI-DSS dan data protection setempat (UU PDP) dengan dynamic data masking untuk atribut PII pelanggan (`phone`, `customer_name`, `email`) yang diikat pada IAM groups BI Analyst.
- **Hasil Terukur**:
  - Waktu deteksi insiden (*Mean Time to Detect* / MTTD) turun dari 9 jam menjadi < 5 menit.
  - Waktu penyelesaian insiden (*Mean Time to Resolve* / MTTR) dipangkas dari 16 jam menjadi 40 menit berkat column-level lineage OpenLineage.
  - Zero-incident reporting corruption selama 4 kuartal berturut-turut.

---

## 9. Trade-offs (Arsitektur & Operasional)

```
           [COMPUTATION COST]
                 ▲
                / \
               /   \
              /     \
             /       \
  [QUALITY DEPTH] ──── [LATENCY & THROUGHPUT]
```

| Dimensi Keputusan | Opsi A | Opsi B | Analisis Trade-off Enterprise |
| :--- | :--- | :--- | :--- |
| **Pola Eksekusi QA** | **Inline / Synchronous Blocking Test** (Fail the pipeline on anomaly). | **Asynchronous Monitoring** (Alert via Slack, data tetap masuk mart). | Opsi A menjamin integritas laporan BI 100% bebas data kotor, tetapi berisiko melanggar SLA freshness jika terjadi false-positive. Opsi B menjaga freshness data, tetapi membuka risiko konsumsi metrik salah oleh eksekutif. |
| **Granularitas Validasi** | **Full Table Profiling** (Scan 100% rows pada setiap run). | **Statistical Sampling / Sliding Window Partition Scan** (Scan $N$ hari terakhir). | Opsi A memberikan jaminan matematis absolut, namun biaya compute data warehouse (Snowflake credits / BigQuery bytes scanned) melonjak eksponensial pada tabel berukuran terabyte/petabyte. Opsi B jauh lebih efisien secara biaya, namun berisiko melewatkan anomali pada partisi data lama. |
| **Schema Governance** | **Strict Pre-Commit Schema Contracts** (Produsen tidak bisa deploy jika melanggar). | **Permissive Schema Evolution** (JSON payload variadic, diekstrak di downstream dbt). | Opsi A membebankan beban komunikasi ke produsen hulu dan memperlambat delivery software, tetapi menjamin stabilitas pipeline BI. Opsi B mempercepat rilis aplikasi hulu, tetapi memindahkan kompleksitas parsing dan risiko failure ke tim analitik. |
| **Lineage Tracking** | **Column-Level Lineage Parser Runtime**. | **Table-Level Asset Dependency**. | Column-level lineage memberikan analisis dampak perubahan (impact analysis) yang presisi, namun menghasilkan volume metadata yang sangat masif dan memerlukan overhead CPU untuk AST parsing query logs. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Alert Fatigue Akibat Static Thresholds yang Terlalu Ketat
- **Gejala**: Channel Slack `#alerts-data-quality` dibanjiri ratusan pesan per hari. Tim analitik mulai mengabaikan notifikasi (*alert blindness*).
- **Akar Masalah**: Threshold volume ditetapkan secara statis (contoh: `row_count > 10000`). Saat akhir pekan, transaksi bisnis secara alami turun ke 8.000, memicu alert palsu (*false positive*).
- **Solusi**: Terapkan pengujian berbasis moving average historis dengan deviasi standar yang memperhitungkan efek musiman (*day-of-week seasonality*), atau manfaatkan fitur anomaly detection bawaan (seperti `anomaly detection` di dbt-expectations atau Soda Core).

### 10.2 Silent Data Corruption Akibat Type Casting Implisit
- **Gejala**: Jumlah revenue harian turun drastis tanpa error satupun pada scheduler log.
- **Akar Masalah**: SQL query transformasi menggunakan `TRY_CAST(column AS NUMERIC)`. Ketika format string berubah dari aplikasi sumber (misal `1,250.00` dengan tanda koma ribuan), fungsi parsing mengembalikan `NULL` tanpa melempar runtime exception.
- **Troubleshooting**:
  1. Periksa model mart dengan query `SELECT COUNT(*) FROM table WHERE revenue IS NULL`.
  2. Ganti syntax `TRY_CAST` dengan explicit contract validation di layer staging.
  3. Tambahkan assertions: `not_null` pada kolom-kolom kalkulasi metrik vital.

### 10.3 Column Masking Memutus Query Agregasi Dashboard
- **Gejala**: Dashboard visualisasi BI menampilkan pesan error: `SQL compilation error: Expression type does not match column type in masking policy`.
- **Akar Masalah**: Dynamic masking policy mengganti nilai string asli menjadi string konstan `'***MASKED***'`, namun dashboard visualisasi mencoba melakukan operasi `GROUP BY` atau filtering berbasis logic yang mengharapkan domain nilai tertentu.
- **Solusi**: Implementasikan *conditional masking* berbasis role IAM warehouse:
  ```sql
  CREATE OR REPLACE MASKING POLICY mask_pii_string AS (val string) 
  RETURNS string ->
    CASE 
      WHEN CURRENT_ROLE() IN ('BI_ADMIN', 'DATA_ENGINEER') THEN val
      WHEN CURRENT_ROLE() IN ('BI_ANALYST') THEN SHA2(val, 256) -- Pseudonymization memungkinkan GROUP BY
      ELSE '***REDACTED***'
    END;
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis model analitik baru ke production warehouse:

- [ ] **Data Contract Verification**: Schema, column names, nullability, dan data types telah terkunci dan diverifikasi terhadap event ingestion spec.
- [ ] **Primary Key Uniqueness Assertion**: Setiap tabel dimensional dan fakta memiliki uji keunikan kunci primer (`unique` dan `not_null`).
- [ ] **Referential Integrity Validation**: Foreign key relasional antar tabel dimensi dan fakta diuji menggunakan test `relationships`.
- [ ] **Time-Travel / Zero-Copy Swap Implementation**: Pipeline transformasi menulis ke transient/shadow table terlebih dahulu, menjalankan QA checks, lalu melakukan `SWAP WITH` ke production target.
- [ ] **SLA & Freshness Thresholds**: Aturan freshness didefinisikan dengan window waktu spesifik yang memicu alert sebelum pengguna bisnis memulai jam kerja operasional.
- [ ] **Column-Level Lineage Emitted**: Runtime scheduler (Airflow/Dagster/dbt) memancarkan metadata OpenLineage ke lineage engine terpusat.
- [ ] **PII Protection & Security Tagging**: Semua atribut PII di-tagging pada database catalog (`security_level: confidential`) dan dilindungi masking policy.
- [ ] **Granular Alert Routing**: Alert error kritis (Severity 1) dikirim ke On-Call PagerDuty; anomali non-kritis (Severity 3) dikirim ke kanal Slack harian.

---

## 12. Hands-on Practice: Membangun Data Quality Gate & Observability Runner

Praktik ini mensimulasikan penerapan Data Quality Gate tingkat enterprise yang memvalidasi data analitik e-commerce, menghentikan deployment saat terjadi anomali, dan menghasilkan output metadata lineage.

### Struktur Direktori (`hands-on/m02/`)
```
hands-on/m02/
├── config/
│   └── database_connection.yml
├── contracts/
│   └── fct_sales_contract.yml
├── datasets/
│   ├── raw_sales_clean.csv
│   └── raw_sales_corrupted.csv
├── scripts/
│   └── run_quality_gate.py
└── requirements.txt
```

### Langkah 1: Persiapan Environment
Buat file `requirements.txt`:
```txt
soda-core==3.0.45
soda-core-duckdb==3.0.45
duckdb==0.9.2
pyyaml==6.0.1
```
Instalasi dependencies:
```bash
pip install -r requirements.txt
```

### Langkah 2: Setup Database & Dummy Dataset
Buat dua file CSV di direktori `hands-on/m02/datasets/`.

File `datasets/raw_sales_clean.csv`:
```csv
order_id,customer_id,transaction_date,amount,status
ORD1001,CUST001,2023-10-01 10:15:00,150.50,COMPLETED
ORD1002,CUST002,2023-10-01 11:20:00,75.00,COMPLETED
ORD1003,CUST003,2023-10-01 12:00:00,200.00,PENDING
ORD1004,CUST004,2023-10-01 13:45:00,50.25,COMPLETED
```

File `datasets/raw_sales_corrupted.csv` (Mensimulasikan anomali: Negative amount, duplicate PK, invalid status):
```csv
order_id,customer_id,transaction_date,amount,status
ORD1001,CUST001,2023-10-01 10:15:00,150.50,COMPLETED
ORD1001,CUST001,2023-10-01 10:15:00,150.50,COMPLETED
ORD1005,CUST005,2023-10-01 14:10:00,-9999.00,UNKNOWN_STATUS
ORD1006,CUST006,2023-10-01 15:30:00,,COMPLETED
```

### Langkah 3: Konfigurasi Engine & Data Contracts
File `config/database_connection.yml`:
```yaml
data_source duckdb_prod:
  type: duckdb
  path: warehouse.duckdb
```

File `contracts/fct_sales_contract.yml`:
```yaml
checks for sales_staging:
  # Schema validation
  - schema:
      name: Validasi integritas struktur kolom
      fail:
        when wrong column type:
          order_id: varchar
          customer_id: varchar
          amount: double
          status: varchar

  # Business asserts
  - missing_count(order_id) = 0:
      name: order_id tidak boleh null
  - duplicate_count(order_id) = 0:
      name: order_id harus unik
  - missing_count(amount) = 0:
      name: amount tidak boleh bernilai null
  - min(amount) >= 0.0:
      name: amount tidak boleh bernilai negatif
  - invalid_count(status) = 0:
      valid values: ['COMPLETED', 'PENDING', 'CANCELLED']
      name: status harus sesuai domain value bisnis
```

### Langkah 4: Skrip Eksekusi Circuit Breaker
File `scripts/run_quality_gate.py`:
```python
import sys
import duckdb
from soda.scan import Scan

def bootstrap_duckdb(dataset_path: str):
    con = duckdb.connect("warehouse.duckdb")
    con.execute(f"CREATE OR REPLACE TABLE sales_staging AS SELECT * FROM read_csv_auto('{dataset_path}');")
    con.close()

def run_gate(dataset_file: str):
    print(f"\n--- MENJALANKAN DATA QUALITY GATE UNTUK: {dataset_file} ---")
    bootstrap_duckdb(dataset_file)

    scan = Scan()
    scan.set_scan_definition_name("Local_Quality_Gate")
    scan.set_data_source_name("duckdb_prod")
    scan.add_configuration_yaml_file("config/database_connection.yml")
    scan.add_sodacl_yaml_file("contracts/fct_sales_contract.yml")
    
    scan.execute()
    
    print("\n--- HASIL SCAN ---")
    for check in scan.get_scan_results().get("checks", []):
        name = check.get("name")
        outcome = check.get("outcome")
        print(f"[{outcome.upper()}] {name}")

    if scan.has_check_fails() or scan.has_scan_errors():
        print("\n[RESULT: REJECTED] Data terkontaminasi anomali! Pipeline dihentikan.")
        return False
    else:
        print("\n[RESULT: APPROVED] Data bersih. Mempromosikan data ke Production Analytics Mart.")
        return True

if __name__ == "__main__":
    # Test 1: Clean Data Run
    clean_passed = run_gate("datasets/raw_sales_clean.csv")
    assert clean_passed is True, "Pipeline gagal pada data bersih!"

    # Test 2: Corrupted Data Run
    corrupted_passed = run_gate("datasets/raw_sales_corrupted.csv")
    assert corrupted_passed is False, "Circuit breaker gagal mendeteksi data korup!"
    print("\nVerifikasi pengujian integritas selesai: Circuit breaker berfungsi 100% normal.")
```

---

## 13. Exercises

### Level Easy
Tuliskan dbt assertion query tunggal (*singular test*) bernama `assert_valid_discount_rate.sql` yang mendeteksi anomali jika terdapat transaksi di tabel mart analitik `fct_sales` di mana nilai kolom `discount_percentage` bernilai lebih besar dari 1.0 (100%) atau bernilai negatif (< 0.0).

### Level Medium
Rancang skema tabel metadata database relational untuk melacak **Pilar Volume & Freshness** harian dari 500 tabel data mart. Skema harus mampu menyimpan:
- `table_name`
- `check_timestamp`
- `row_count`
- `expected_row_count_lower_bound`
- `expected_row_count_upper_bound`
- `latest_record_timestamp`
- `latency_minutes`
- `status_flag` (PASS/FAIL)
Tuliskan DDL SQL skema tersebut serta satu query SQL window function untuk menghitung persentase perubahan row count hari ini dibanding rata-rata 7 hari sebelumnya.

### Level Hard
Buat implementasi Python class `SemanticLayerCircuitBreaker` yang menginterogasi API semantic store (atau mengeksekusi query metadata ke information schema warehouse). Class ini harus:
1. Menerima daftar model mart yang menjadi dependency dashboard eksekutif C-Level.
2. Mengecek apakah tabel underlying sedang berada dalam lock state atau memiliki failure run pada sistem dbt/observability dalam 60 menit terakhir.
3. Mengembalikan status boolean `can_serve_traffic`: jika `False`, mematikan tile dashboard tertentu secara otomatis menggunakan API tool BI downstream (mock payload) dan menggantinya dengan status banner *"Data Maintenance in Progress"*.

---

## 14. Challenges (Tantangan Studi Kasus Nyata)

### Skenario: Rekonsiliasi Multi-Sistem Finansial Pasca-Migrasi Cloud
Anda adalah Principal BI Data Architect di bank digital tier-1. Organisasi Anda baru saja melakukan migrasi platform dari sistem on-premise Oracle ke Databricks/Snowflake.

- **Situasi**:
  Setiap tengah malam, pipeline menjalankan perhitungan saldo buku besar (*general ledger balance*). Terdapat selisih $0.001 per transaksi akibat pembulatan presisi desimal floating-point antara sistem Java Core Banking lama dengan Spark SQL engine baru. Sepintas terlihat sepele, namun pada volume 80 juta transaksi per hari, selisih akumulasi mencapai jutaan rupiah, yang menyebabkan ketidakcocokan pada laporan neraca audit keuangan OJK.
- **Tantangan Arsitektur**:
  1. Rancang arsitektur **Automated Reconciliation Framework** yang menguji konsistensi metrik keuangan secara deterministik sebelum laporan dirender di semantic layer analitik.
  2. Bagaimana Anda merancang deteksi anomali desimal tersebut tanpa menyebabkan throughput pipeline batch batch ETL malam hari terhenti lebih dari 30 menit (SLA ketat: data harus siap pukul 06.00 WIB)?
  3. Susun mitigasi teknis (data contract & casting governance) untuk menjamin kompatibilitas tipe data moneter di seluruh layer (Source DB -> Ingestion CDC -> Bronze -> Silver -> Gold Mart -> BI Metric Store).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. **Apa perbedaan mendasar antara data observability dan data quality testing konvensional?**
   - *Jawaban*: Data quality testing bersifat statis dan deterministik berbasis rules (mengecek kondisi lulus/gagal atas assertion tertentu), sedangkan data observability bersifat holistik dan terus menerus, melacak pola kesehatan data internal (anomali volume, freshness, distribusi, schema drift, dan graph lineage) di seluruh sistem secara dinamis.

2. **Mengapa penegakan data contract sebaiknya dilakukan di layer ingestion atau batas produsen data daripada di downstream BI dashboard?**
   - *Jawaban*: Pendekatan "Shift-Left". Memperbaiki kerusakan data di downstream BI memakan resource komputasi dan investigasi besar (*expensive MTTR*). Memvalidasi di layer hulu (boundaries) menghentikan propagasi data kotor (garbage-in, garbage-out) sebelum mempolusi semantic layer dan model analitik.

3. **Sebutkan minimal 3 parameter kunci yang menyusun pilar schema drift dalam observability.**
   - *Jawaban*: Perubahan tipe data kolom, penambahan/penghapusan kolom (added/dropped columns), dan perubahan batasan nullability atau primary/foreign key.

4. **Apa fungsi utama dari OpenLineage dalam arsitektur analitik modern?**
   - *Jawaban*: Menyediakan standar terbuka dan format spesifikasi metadata standar API untuk mengumpulkan data lineage end-to-end secara asinkron dari berbagai alat pemrosesan (Spark, dbt, Airflow, Great Expectations) ke metadata catalog.

5. **Apa yang dimaksud dengan Dynamic PII Masking pada platform modern data warehouse?**
   - *Jawaban*: Mekanisme keamanan di mana nilai data sensitif (misal NIK/Email) diubah atau disamarkan secara dinamis pada saat query dieksekusi berdasarkan role/hak akses pengguna, tanpa mengubah data asli yang tersimpan di disk storage.

### 15.2 Pertanyaan Intermediate
6. **Kapan tim data sebaiknya menggunakan singular test dbt daripada generic test deklaratif?**
   - *Jawaban*: Singular test digunakan ketika assertion quality memerlukan logika bisnis kompleks yang melibatkan multi-table join, subquery, aggregasi lintas entitas (business logic reconciliation), yang tidak bisa dipenuhi oleh generic schema tests seperti `unique` atau `not_null`.

7. **Bagaimana cara kerja mekanisme Circuit Breaker berbasis Table-Swap pada data warehouse seperti Snowflake?**
   - *Jawaban*: Pipeline memuat dan mentransformasikan data ke transient staging table, mengeksekusi serangkaian QA assertions. Jika seluruh tes lulus (passed), engine menjalankan perintah atomic DDL `ALTER TABLE prod_table SWAP WITH staging_table`. Jika gagal, pipeline abort dan data produksi tetap bersih tanpa downtime atau *dirty read*.

8. **Mengapa penggunaan anomaly detection berbasis moving average sederhana (Simple Moving Average) sering menghasilkan false positive pada metrik volume transaksi retail?**
   - *Jawaban*: Karena SMA tidak memperhitungkan pola musiman kalender bisnis (*business seasonality*), seperti pola lonjakan di akhir pekan (weekend spikes), tanggal gajian (*payday surge*), atau penurunan transaksi saat hari libur nasional.

9. **Apa risiko arsitektural jika column-level lineage di-generate menggunakan active query injection dibanding log-based AST parsing?**
   - *Jawaban*: Active query injection membebani sistem komputasi data warehouse dan dapat menambah latensi runtime ETL, sedangkan log-based AST parsing bersifat non-intrusif karena menganalisis riwayat execution plan dari information schema/query history secara terpisah (*out-of-band*).

10. **Bagaimana semantic layer (seperti dbt Semantic Layer atau Looker LookML) membantu penegakan data governance?**
    - *Jawaban*: Semantic layer bertindak sebagai *single source of truth* untuk definisi metrik bisnis, mengabstraksi kompleksitas SQL mentah, dan membatasi akses pengguna sehingga mereka hanya dapat mengonsumsi metrik terverifikasi yang telah diikat dengan aturan keamanan row-level dan column-level policy.

### 15.3 Skenario Kasus Produksi
11. **Skenario 1**: Tim BI Analyst melaporkan bahwa metric `Daily Active Users (DAU)` di Metabase mengalami drop 45% mendadak pada hari Selasa. Pipeline Airflow berstatus hijau (`SUCCESS`). Saat dicek, query staging upstream CDC Postgres tidak mengembalikan error. Langkah sistematis apa yang harus Anda lakukan untuk mendeteksi akar masalah?
    - *Solusi Analitis*:
      1. Cek **Volume Pillar**: Bandingkan row count source table CDC landing vs staging mart.
      2. Periksa **Schema Pillar**: Cari tahu apakah ada event type baru yang ditambahkan oleh tim aplikasi yang tidak masuk dalam klausa `WHERE event_type IN (...)` model dbt.
      3. Periksa **Freshness & Watermark**: Verifikasi apakah pipeline CDC mengalami replikasi lag/hang sehingga data yang dimuat adalah data usang (*stale*).
      4. Eksekusi query rekonsiliasi manual antara OLTP database dengan data staging warehouse.

12. **Skenario 2**: Biaya data warehouse Snowflake melonjak 250% dalam satu bulan terakhir. Setelah audit dilakukan, ditemukan bahwa framework data quality mengeksekusi test assertion `unique` dan `relationships` pada tabel transaksi `fct_events` yang berukuran 5 Miliar baris setiap 15 menit. Bagaimana Anda merancang ulang strategi testing agar cost-efficient tanpa mengorbankan integritas data?
    - *Solusi Analitis*:
      1. Ubah lingkup test dari Full-Table Scan ke **Partition-Pruned / Sliding Window Testing**: Jalankan test hanya pada partisi transaksi hari berjalan ($T$) atau $T-1$ menggunakan parameter timestamp filtering.
      2. Pindahkan deep referential integrity test ke frekuensi yang lebih rendah (misal: satu kali sehari di luar jam sibuk).
      3. Manfaatkan **Metadata-based testing**: Gunakan `row_count` dari `INFORMATION_SCHEMA.TABLE_STORAGE_METRICS` yang gratis (*zero compute cost*) untuk validasi volume dasar sebelum menjalankan SQL assertions.

13. **Skenario 3**: Sebuah institusi finansial diwajibkan mematuhi regulasi ketat di mana analis BI internal diizinkan melihat agregasi transaksi regional, tetapi dilarang keras merekonstruksi identitas individu nasabah (*re-identification risk*). Bagaimana Anda merancang kontrol akses ini pada level semantic layer dan arsitektur data mart?
    - *Solusi Analitis*:
      1. Implementasikan **Row-Level Security (RLS)** dan **Aggregation Threshold Enforcement**: Aturan di warehouse/semantic layer menolak mengeksekusi query yang menghasilkan kelompok data dengan cardinality individu di bawah $K$-Anonymity threshold (misal: kelompok kurang dari 5 nasabah).
      2. Terapkan **Dynamic Hashing/Pseudonymization dengan Pepper/Salt** tersembunyi pada `customer_id` sehingga identitas unik tidak dapat di-join silang dengan data publik.
      3. Pisahkan Semantic Layer View: Analis hanya diberikan hak query ke pre-aggregated dimensional views (`fct_regional_daily_sales`), bukan ke level atomic transaction (`fct_orders_detail`).

---

## 16. Summary

- **Integritas Data BI adalah Tanggung Jawab Hanyutan Hulu (Shift-Left)**: Kualitas data analitik tidak dapat diuji hanya di dashboard downstream; integritas harus ditegakkan di batas arsitektur sedini mungkin menggunakan Data Contracts dan Automated Circuit Breakers.
- **5 Pilar Data Observability**: Keandalan sistem analitik modern bertumpu pada transparansi Freshness, Volume, Schema, Quality, dan Lineage. Monitoring yang hanya mengandalkan status exit code task scheduler tidak memadai untuk sistem enterprise.
- **Keseimbangan Biaya dan Keandalan (Trade-offs)**: Implementasi validasi kualitas data harus mempertimbangkan dampak komputasi (*cost overhead*). Gunakan dynamic partition scans dan statistical anomaly models untuk menghindari *full-table scans* yang mahal dan alert fatigue.
- **Governance Terpadu via Semantic Layer**: Gabungan dari column-level lineage, automated audit logging, dan dynamic PII masking memastikan platform analitik enterprise tetap aman, patuh regulasi industri (GDPR/UU PDP/PCI-DSS), dan menghasilkan metrik bisnis yang konsisten serta dapat diandalkan oleh pengambil keputusan.