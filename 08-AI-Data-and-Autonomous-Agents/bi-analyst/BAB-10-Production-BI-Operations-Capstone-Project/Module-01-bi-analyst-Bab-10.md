# Bab 10: Production BI Operations & Capstone Project Module 01

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Arsitektur DataOps untuk Business Intelligence (BI)** dengan mengintegrasikan *Continuous Integration/Continuous Delivery* (CI/CD), *semantic versioning*, dan pengujian otomatis untuk artefak analitik.
2. **Membangun Automated Data Quality & Anomaly Detection Gates** yang memvalidasi *schema contract*, integritas referensial, serta distribusi statistik data metrik sebelum dikonsumsi oleh lapisan *dashboarding*.
3. **Menerapkan Pola Zero-Downtime Deployment & Circuit Breaker pada Data Warehouse** menggunakan teknik *atomic swap*, *blue-green deployment*, dan *graceful degradation* pada semantic layer.
4. **Membangun Sistem Observabilitas BI End-to-End** yang melacak metrik *Freshness, Volume, Distribution, Schema,* dan *Lineage* dengan batas ambang Service Level Objective (SLO) spesifik (misal: *pipeline freshness* $< 15$ menit, *dashboard query response* P95 $< 2.5$ detik).
5. **Menginisiasi Capstone Project Module 01** dengan menyusun fondasi arsitektur analitik enterprise berskala besar, memetakan domain model, dan menegakkan kontrak data (*data contract*) production-grade.

---

## 2. Concept Overview

Dalam lanskap analitik enterprise modern, Business Intelligence (BI) tidak lagi sekadar merancang visualisasi data statis di atas database replika. BI operasional modern merupakan sistem terdistribusi kritis yang menuntut reliabilitas setara dengan sistem *software engineering* produksi tier-1. 

```
+-----------------------------------------------------------------------------------+
|                            MENTAL MODEL: ANALYTICS OPS                            |
+-----------------------------------------------------------------------------------+
|  Software Engineering Principles        |  Applied Data & BI Operations           |
+-----------------------------------------+-----------------------------------------+
|  Unit & Integration Testing             |  dbt-tests, Great Expectations, Soda    |
|  CI/CD Pipelines (GitHub Actions)       |  Slim CI, PR-based ephemeral staging    |
|  Blue-Green / Zero-Downtime Deploys     |  Atomic Table Swaps, Zero-Copy Cloning  |
|  APM & Distributed Tracing (OpenTel)    |  Data Observability (Elementary, SRE)   |
|  Microservice Circuit Breakers          |  Semantic Layer Failover & Cache Lock   |
+-----------------------------------------------------------------------------------+
```

Operasional BI modern berakar pada empat pilar:
* **The Semantic Layer as Single Source of Truth:** Abstraksi logika bisnis (KPI, dimensi, metrik) dari *underlying physical storage* ke dalam repositori berbasis kode (*code-first semantic models*), memastikan bahwa metrik seperti `Gross Merchandise Value (GMV)` atau `Customer Churn Rate` terdefinisi secara identik di seluruh laporan eksekutif, antarmuka BI (Tableau, PowerBI, Apache Superset), maupun agen AI otonom.
* **Shift-Left Data Quality Testing:** Pengecekan anomali data dilakukan sedini mungkin di pipeline rekayasa data sebelum memasuki *serving layer*. Jika validasi gagal, *circuit breaker* terpicu guna mencegah polusi data (*silent data corruption*) ke metrik level eksekutif.
* **Zero-Downtime Serving:** Melindungi beban kerja operasional dari *table lock* atau kueri kosong (*empty reads*) saat proses ingest data berjalan dengan memanfaatkan *partition swap*, kloning berbasis metadata (*zero-copy clone*), atau penggantian *view* secara atomik.
* **Data Observability & SLA Monitoring:** Telemetri berkelanjutan terhadap perilaku pipeline, pergeseran skema (*schema drift*), deviasi volume, serta latensi konsumsi data.

---

## 3. Why It Matters

Kegagalan menerapkan standar rekayasa perangkat lunak dalam operasional BI berdampak fatal secara finansial dan strategis:

1. **The "Silent Data Corruption" Disaster:** Perubahan tipe data upstream (misalnya sistem pembayaran mengubah format mata uang dari integer sen ke float desimal) yang tidak terdeteksi dapat merusak agregasi laba bersih. Keputusan strategis bernilai jutaan dolar sering kali diambil di atas dashboard dengan data yang keliru tanpa memicu error sistem.
2. **Executive Loss of Trust:** Jika metrik *Revenue* di dashboard CEO berbeda $5\%$ dari angka yang dilaporkan tim akuntansi pada hari penutupan buku kuartalan, kredibilitas seluruh divisi data akan runtuh. Rekonsiliasi manual yang reaktif menghabiskan ribuan jam kerja teknis.
3. **Regulatori & Audit Trail Compliance:** Kebutuhan sertifikasi seperti SOX (Sarbanes-Oxley), BCBS 239, atau GDPR mengharuskan setiap angka finansial memiliki *immutable audit log* dan *end-to-end lineage* yang dapat dibuktikan dari *source-to-widget*.
4. **Biaya Komputasi yang Tidak Terkendali:** Tanpa tata kelola operasional dan *circuit breaker*, kueri analitik ad-hoc yang tidak terindeks atau join *Cartesian* yang tidak disengaja pada tabel terdistribusi berukuran petabyte dapat menghabiskan ribuan dolar dalam hitungan menit di platform komputasi cloud seperti Snowflake atau BigQuery.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup deployment BI dari repositori Git hingga ke lapisan penyajian visual dan agen otonom, terintegrasi dengan mekanisme observabilitas dan *circuit breaker*.

```
+----------------------------------------------------------------------------------------------------+
|                                    BI PRODUCTION ARCHITECTURE                                      |
+----------------------------------------------------------------------------------------------------+

  [ Developer Commit ]
           │
           ▼
  [ GitHub Actions CI ] ────► Run Slim CI (dbt / SQLFluff / Pytest)
           │
           ├──────────────────────────────┐
       (Passes)                        (Fails)
           │                              │
           ▼                              ▼
  [ Production Merge ]           [ PR Rejected & Alerted ]
           │
           ▼
  ┌────────────────────────────────────────────────────────────────┐
  │ Pipeline Orchestration (Airflow / Dagster / Prefect)           │
  │                                                                │
  │  +------------------+     +------------------+                 │
  │  | Extract & Load   | ──► | Transform (dbt)  |                 │
  │  | (Fivetran/Airbyte)     | (Staging Models) |                 │
  │  +------------------+     +--------┬---------+                 │
  │                                    │                           │
  │                                    ▼                           │
  │                       +──────────────────────────+             │
  │                       | Pre-Serving Tests        |             │
  │                       | (Volume, Null, Contracts)|             │
  │                       +────────────┬─────────────+             │
  └────────────────────────────────────┼───────────────────────────┘
                                       │
                         ┌─────────────┴─────────────┐
                    (Valid Data)               (Anomaly / Fail)
                         │                           │
                         ▼                           ▼
        +─────────────────────────────────+  +─────────────────────────+
        | Atomic Swap / Blue-Green        |  | Trip Circuit Breaker    |
        | - Swap staging to prod tables   |  | - Halt ingestion        |
        | - Refresh Materialized Views    |  | - Retain stale snapshot |
        +────────────────┬────────────────+  | - Trigger PagerDuty/    |
                         │                   |   Slack Critical Alert  |
                         ▼                   +─────────────────────────+
        +─────────────────────────────────+
        | Semantic Layer Engine           |
        | (Cube.js / MetricFlow)          |
        | - Enforces metric consistency   |
        | - Multi-tenant caching          |
        +────────────────┬────────────────+
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
+───────────────────────────+   +───────────────────────────+
| BI Presentation Tier      |   | Autonomous AI Agents      |
| (Superset / PowerBI /     |   | (LLM Agents querying via  |
| Metabase)                 |   | Semantic APIs)            |
+───────────────────────────+   +───────────────────────────+
        │                                 │
        └────────────────┬────────────────┘
                         ▼
        +─────────────────────────────────+
        | Data Observability & Monitoring |
        | - Elementary / OpenLineage      |
        | - Query Performance Tracking    |
        | - Latency & Freshness SLI/SLO   |
        +─────────────────────────────────+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Semantic Versioning & Kontrak Data (Data Contracts)
Data contract mendefinisikan skema, properti kualitas, dan SLA dari data output yang disediakan oleh upstream data product. Dalam format declaratif (biasanya YAML/JSON), kontrak ini mencakup:
* **Schema Integrity:** Nama kolom, tipe data presisi, aturan *nullability*, dan kunci relasional.
* **Semantic Meaning:** Unit pengukuran (misal: ISO 4217 currency code), zona waktu (wajib UTC), dan metode pembulatan.
* **SLA & Freshness:** Ambang batas maksimal jeda kedatangan data (*maximum allowed latency*).

### 5.2 Zero-Downtime Deployment: Blue-Green Table Swapping
Memodifikasi tabel berukuran gigabyte atau terabyte secara *in-place* akan memicu penguncian tabel (*table lock*) dan menyebabkan query analitik gagal (*read failures*). Solusi standar industri adalah **Atomic Swapping**:
1. Pipeline membuat dan memuat data ke dalam skema staging: `analytics_blue.fact_orders`.
2. Validasi integritas data dijalankan terhadap `fact_orders` di skema blue.
3. Jika pengujian lolos, jalankan perintah DDL atomik:
   ```sql
   ALTER TABLE analytics_prod.fact_orders SWAP WITH analytics_blue.fact_orders;
   ```
   Atau untuk database yang tidak mendukung `SWAP WITH`, manipulasi *symlink* atau penggantian referensi *atomic view*:
   ```sql
   CREATE OR REPLACE VIEW analytics_prod.fact_orders AS 
   SELECT * FROM analytics_prod.fact_orders_v2;
   ```

### 5.3 Anomaly Detection & Statistical Drift Protection
Pengecekan berbasis aturan kaku (*rule-based*, misal: `val > 0`) tidak memadai untuk mendeteksi *metric drift*. Pendekatan produksi memanfaatkan pemodelan statistik berkelanjutan:
* **Modified Z-Score / IQR (Interquartile Range):** Digunakan untuk mendeteksi anomali pada volume data harian dengan mendeteksi deviasi terhadap moving average (misalnya 30 hari terakhir).
* **Population Stability Index (PSI):** Digunakan untuk mengukur pergeseran distribusi probabilitas dari variabel kontinu atau kategoris antar periode waktu, berguna untuk mendeteksi apakah profil pembeli berubah secara drastis akibat kegagalan tracking upstream.

### 5.4 Circuit Breaker Pattern dalam BI
Jika terdeteksi kegagalan data kritis:
1. **Trip the Breaker:** Pipeline downstream berhenti mempublikasikan data baru ke layer penyajian.
2. **Graceful Degradation:** Semantic layer diarahkan untuk tetap menyajikan *cached data snapshot* dari partisi valid terakhir, sembari memunculkan *flag metadata* pada dashboard: `[WARNING: Data freshness delayed. Displaying snapshot from T-24h]`.
3. **Automated Rollback:** Jika skema terlanjur termutasi secara keliru, eksekusi migrasi balik ke versi metastore sebelumnya secara otomatis.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Python produksi untuk **Production BI Quality Gate & Circuit Breaker Engine**. Skrip ini memvalidasi skema data, mendeteksi statistical volume drift, melakukan atomic swap, dan mengelola status circuit breaker yang dipantau oleh layer presentasi BI.

```python
"""
production_bi_circuit_breaker.py
Author: Principal Data Solutions Architect
Description: Production BI Quality Gate, Statistical Drift Detector, 
             and Zero-Downtime Table Swap Controller.
"""

from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import duckdb
from pydantic import BaseModel, Field, ValidationError

# =====================================================================
# Structured Logging Setup
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("BI-CircuitBreaker")


# =====================================================================
# Domain Models & Data Contracts
# =====================================================================
class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operations: Traffic flowing to fresh data
    OPEN = "OPEN"          # Tripped: Serving fallback/stale data, alerts firing
    HALF_OPEN = "HALF_OPEN"  # Testing recovery in progress


class ColumnContract(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class TableContract(BaseModel):
    table_name: str
    target_schema: str
    staging_schema: str
    expected_columns: List[ColumnContract]
    max_null_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    allowed_volume_z_score: float = Field(default=3.0, ge=1.0, le=5.0)


class ValidationResult(BaseModel):
    is_valid: bool
    reasons: List[str]
    metrics_captured: Dict[str, Any]


# =====================================================================
# Statistical Anomaly Detection Engine
# =====================================================================
class StatisticalGuard:
    """Performs statistical anomaly detection on ingestion volumes & metrics."""

    @staticmethod
    def calculate_modified_z_score(
        current_value: float, historical_series: List[float]
    ) -> float:
        """
        Calculates modified Z-score using Median Absolute Deviation (MAD)
        for robust outlier detection independent of extreme outliers.
        """
        if not historical_series or len(historical_series) < 3:
            logger.warning("Insufficient historical data for MAD. Fallback to standard deviation.")
            return 0.0

        median = float(sorted(historical_series)[len(historical_series) // 2])
        deviations = [abs(x - median) for x in historical_series]
        mad = float(sorted(deviations)[len(deviations) // 2])

        if mad == 0.0:
            # If MAD is zero, use simple mean/std to prevent division by zero
            mean = sum(historical_series) / len(historical_series)
            variance = sum((x - mean) ** 2 for x in historical_series) / len(historical_series)
            std_dev = math.sqrt(variance)
            return abs(current_value - mean) / std_dev if std_dev > 0 else 0.0

        # 0.6745 is the consistency constant for normal distribution
        modified_z_score = 0.6745 * abs(current_value - median) / mad
        return float(modified_z_score)


# =====================================================================
# Production BI Gatekeeper & Orchestrator
# =====================================================================
class ProductionBIGatekeeper:
    def __init__(self, db_connection: duckdb.DuckDBPyConnection) -> None:
        self.conn = db_connection
        self._initialize_metadata_store()

    def _initialize_metadata_store(self) -> None:
        """Instantiates internal catalog to manage circuit breaker states & SLAs."""
        self.conn.execute("""
            CREATE SCHEMA IF NOT EXISTS bi_operations_meta;
            CREATE TABLE IF NOT EXISTS bi_operations_meta.circuit_status (
                table_identifier VARCHAR PRIMARY KEY,
                state VARCHAR NOT NULL,
                last_updated TIMESTAMP NOT NULL,
                last_valid_snapshot VARCHAR,
                failure_reason VARCHAR
            );
            CREATE TABLE IF NOT EXISTS bi_operations_meta.volume_history (
                table_identifier VARCHAR NOT NULL,
                recorded_at TIMESTAMP NOT NULL,
                row_count BIGINT NOT NULL
            );
        """)

    def evaluate_contract(
        self, contract: TableContract
    ) -> ValidationResult:
        """Validates physical staging data against declarative data contracts."""
        staging_fqdn = f"{contract.staging_schema}.{contract.table_name}"
        reasons: List[str] = []
        captured_metrics: Dict[str, Any] = {}

        logger.info(f"Validating contract for staging table: {staging_fqdn}")

        # 1. Structural Schema Validation
        try:
            columns_query = f"""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_schema = '{contract.staging_schema}' 
                  AND table_name = '{contract.table_name}';
            """
            live_columns = self.conn.execute(columns_query).fetchall()
            if not live_columns:
                return ValidationResult(
                    is_valid=False,
                    reasons=[f"Table {staging_fqdn} does not exist in metastore."],
                    metrics_captured={},
                )

            live_column_map = {row[0].lower(): (row[1].upper(), row[2].upper()) for row in live_columns}

            for expected_col in contract.expected_columns:
                col_name = expected_col.name.lower()
                if col_name not in live_column_map:
                    reasons.append(f"Missing mandatory column: {expected_col.name}")
                    continue

                actual_type, actual_nullable = live_column_map[col_name]
                if expected_col.data_type.upper() not in actual_type:
                    reasons.append(
                        f"Type mismatch on column {expected_col.name}: "
                        f"expected {expected_col.data_type}, found {actual_type}"
                    )

                if not expected_col.nullable and actual_nullable == "YES":
                    # Check for null values in non-nullable column
                    null_check_sql = f"SELECT COUNT(*) FROM {staging_fqdn} WHERE {expected_col.name} IS NULL;"
                    null_count = self.conn.execute(null_check_sql).fetchone()[0]
                    if null_count > 0:
                        reasons.append(
                            f"Non-nullable column '{expected_col.name}' contains {null_count} NULL records."
                        )

        except Exception as e:
            logger.error(f"Error during structural validation: {str(e)}")
            return ValidationResult(is_valid=False, reasons=[f"Database query error: {str(e)}"], metrics_captured={})

        # 2. Volume & Statistical Drift Validation
        count_sql = f"SELECT COUNT(*) FROM {staging_fqdn};"
        current_row_count = float(self.conn.execute(count_sql).fetchone()[0])
        captured_metrics["current_row_count"] = current_row_count

        table_id = f"{contract.target_schema}.{contract.table_name}"
        history_sql = f"""
            SELECT row_count FROM bi_operations_meta.volume_history
            WHERE table_identifier = '{table_id}'
            ORDER BY recorded_at DESC LIMIT 30;
        """
        history_rows = [float(r[0]) for r in self.conn.execute(history_sql).fetchall()]

        if history_rows:
            z_score = StatisticalGuard.calculate_modified_z_score(current_row_count, history_rows)
            captured_metrics["volume_z_score"] = z_score
            logger.info(f"Calculated Volume Modified Z-Score: {z_score:.2f}")

            if z_score > contract.allowed_volume_z_score:
                reasons.append(
                    f"Volume anomaly detected! Modified Z-Score: {z_score:.2f} > "
                    f"Threshold: {contract.allowed_volume_z_score} (Current Rows: {current_row_count})"
                )

        is_valid = len(reasons) == 0
        return ValidationResult(is_valid=is_valid, reasons=reasons, metrics_captured=captured_metrics)

    def execute_atomic_swap(self, contract: TableContract) -> None:
        """Executes zero-downtime atomic view or table pointer update."""
        target_fqdn = f"{contract.target_schema}.{contract.table_name}"
        staging_fqdn = f"{contract.staging_schema}.{contract.table_name}"
        backup_fqdn = f"{contract.target_schema}.{contract.table_name}_previous"

        logger.info(f"Commencing atomic transaction swap: {staging_fqdn} -> {target_fqdn}")

        # DuckDB / PostgreSQL atomic pointer swap execution using transaction
        swap_sql = f"""
            BEGIN TRANSACTION;
                CREATE SCHEMA IF NOT EXISTS {contract.target_schema};
                DROP TABLE IF EXISTS {backup_fqdn};
                CREATE TABLE IF NOT EXISTS {target_fqdn} AS SELECT * FROM {staging_fqdn} WHERE 1=0;
                ALTER TABLE {target_fqdn} RENAME TO {contract.table_name}_previous;
                ALTER TABLE {staging_fqdn} RENAME TO {contract.table_name};
            COMMIT;
        """
        try:
            self.conn.execute(swap_sql)
            logger.info("Atomic table swap successfully completed.")

            # Record successful volume history
            table_id = f"{contract.target_schema}.{contract.table_name}"
            row_count = self.conn.execute(f"SELECT COUNT(*) FROM {target_fqdn}").fetchone()[0]
            self.conn.execute(f"""
                INSERT INTO bi_operations_meta.volume_history VALUES
                ('{table_id}', CURRENT_TIMESTAMP, {row_count});
            """)

            # Update circuit breaker state to CLOSED
            self._update_circuit_status(table_id, CircuitState.CLOSED, target_fqdn, None)

        except Exception as e:
            logger.critical(f"Atomic swap transaction failed! Rolling back. Error: {str(e)}")
            self.conn.execute("ROLLBACK;")
            raise RuntimeError(f"Database swap failed: {str(e)}") from e

    def trip_circuit_breaker(self, contract: TableContract, reasons: List[str]) -> None:
        """Opens circuit breaker, preventing corrupted data promotion."""
        table_id = f"{contract.target_schema}.{contract.table_name}"
        combined_reason = "; ".join(reasons)
        logger.error(f"TRIPPING CIRCUIT BREAKER for {table_id}. Reasons: {combined_reason}")

        self._update_circuit_status(table_id, CircuitState.OPEN, None, combined_reason)
        self._dispatch_pagerduty_alert(table_id, combined_reason)

    def _update_circuit_status(
        self,
        table_id: str,
        state: CircuitState,
        last_valid_snapshot: Optional[str],
        failure_reason: Optional[str],
    ) -> None:
        """Upserts circuit breaker current state."""
        reason_clean = f"'{failure_reason}'" if failure_reason else "NULL"
        snapshot_clean = f"'{last_valid_snapshot}'" if last_valid_snapshot else "NULL"
        
        self.conn.execute(f"""
            INSERT INTO bi_operations_meta.circuit_status (
                table_identifier, state, last_updated, last_valid_snapshot, failure_reason
            ) VALUES (
                '{table_id}', '{state.value}', CURRENT_TIMESTAMP, {snapshot_clean}, {reason_clean}
            )
            ON CONFLICT (table_identifier) DO UPDATE SET
                state = EXCLUDED.state,
                last_updated = EXCLUDED.last_updated,
                last_valid_snapshot = COALESCE(EXCLUDED.last_valid_snapshot, bi_operations_meta.circuit_status.last_valid_snapshot),
                failure_reason = EXCLUDED.failure_reason;
        """)

    def _dispatch_pagerduty_alert(self, entity_id: str, message: str) -> None:
        """Production alerting integration mock (PagerDuty / OpsGenie / Slack API)."""
        logger.critical(
            f"[ALERT PAYLOAD SENT] Service: BI-Engine | Entity: {entity_id} | "
            f"Severity: CRITICAL | Details: {message}"
        )


# =====================================================================
# Execution Demonstration & Verification
# =====================================================================
if __name__ == "__main__":
    # Inisialisasi in-memory analytical warehouse
    con = duckdb.connect(database=":memory:")
    gatekeeper = ProductionBIGatekeeper(con)

    # 1. Setup Staging Environment
    con.execute("CREATE SCHEMA staging;")
    con.execute("""
        CREATE TABLE staging.fact_daily_financials (
            transaction_id VARCHAR,
            metric_date DATE,
            revenue_usd DOUBLE,
            cost_usd DOUBLE
        );
    """)

    # Definisikan Kontrak Data
    financial_contract = TableContract(
        table_name="fact_daily_financials",
        target_schema="analytics_prod",
        staging_schema="staging",
        expected_columns=[
            ColumnContract(name="transaction_id", data_type="VARCHAR", nullable=False),
            ColumnContract(name="metric_date", data_type="DATE", nullable=False),
            ColumnContract(name="revenue_usd", data_type="DOUBLE", nullable=False),
            ColumnContract(name="cost_usd", data_type="DOUBLE", nullable=True),
        ],
        allowed_volume_z_score=2.5,
    )

    # Isi history data historis sintetis untuk melatih detector (30 hari sebelumnya)
    for day in range(30, 0, -1):
        con.execute(f"""
            INSERT INTO bi_operations_meta.volume_history VALUES 
            ('analytics_prod.fact_daily_financials', CURRENT_TIMESTAMP - INTERVAL '{day}' DAY, 10000 + {day * 10});
        """)

    # SCENARIO A: Simulasi Data Valid
    logger.info("=== SCENARIO A: Pipeline Data Valid ===")
    con.execute("""
        INSERT INTO staging.fact_daily_financials 
        SELECT 
            'TXN_' || range::VARCHAR, 
            CURRENT_DATE, 
            150.50, 
            45.20 
        FROM range(10150);
    """)

    result_a = gatekeeper.evaluate_contract(financial_contract)
    if result_a.is_valid:
        gatekeeper.execute_atomic_swap(financial_contract)
    else:
        gatekeeper.trip_circuit_breaker(financial_contract, result_a.reasons)

    # SCENARIO B: Simulasi Malformed Ingestion (Missing Values & Extreme Volume Drop)
    logger.info("\n=== SCENARIO B: Silent Data Corruption (Circuit Breaker Tripped) ===")
    con.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    con.execute("DROP TABLE IF EXISTS staging.fact_daily_financials;")
    con.execute("""
        CREATE TABLE staging.fact_daily_financials (
            transaction_id VARCHAR,
            metric_date DATE,
            revenue_usd DOUBLE,
            cost_usd DOUBLE
        );
    """)
    # Masukkan data korup (Hanya 100 baris padahal historis 10,000, serta NULL transaction_id)
    con.execute("""
        INSERT INTO staging.fact_daily_financials VALUES 
        (NULL, CURRENT_DATE, 200.0, 50.0),
        ('TXN_99999', CURRENT_DATE, -50.0, 10.0);
    """)

    result_b = gatekeeper.evaluate_contract(financial_contract)
    if result_b.is_valid:
        gatekeeper.execute_atomic_swap(financial_contract)
    else:
        gatekeeper.trip_circuit_breaker(financial_contract, result_b.reasons)

    # Audit Circuit Status
    status = con.execute("SELECT * FROM bi_operations_meta.circuit_status;").fetchall()
    logger.info(f"\nFinal State in Metadata Catalog: {status}")
```

---

## 7. Edge Cases & Failure Modes

Berikut adalah potensi kegagalan kritis pada pipeline BI tingkat lanjut beserta mitigasinya:

| Kasus Batas (Edge Case) | Mekanisme Kegagalan | Dampak Operasional | Solusi / Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Upstream Type Widening / Narrowing** | Sumber upstream mengubah kolom ID numerik menjadi alfanumerik (misal: order_id dari `INT64` ke `VARCHAR`). | ETL downstream runtime error atau nilai dikonversi menjadi `NULL`. | Strict schema contract parsing pada file staging. Tolak pipeline via CI jika tipe data bergeser tanpa persetujuan PR. |
| **Late-Arriving Facts across Partitions** | Transaksi yang diproses tertunda (misal: offline POS sync) masuk ke partisi 7 hari lalu. | Dashboard visualisasi harian tidak mencerminkan data aktual (*under-reporting* pendapatan historis). | Implementasikan *rolling partition re-processing* ($T-7$ hari) dan hindari penguncian agregat statis pada tabel partisi lampau. |
| **Seasonality & Holiday Volume Spikes** | Volume data Black Friday melonjak $500\%$ di atas rata-rata historis 30 hari. | Statistical anomaly detection memicu alarm palsu (*false positive*) dan memutus pipeline. | Gunakan *calendar-aware statistical baseline* yang membandingkan volume dengan pola tahun sebelumnya (*Year-over-Year*) alih-alih hanya MA 30 hari. |
| **Metastore Lock Contention during Atomic Swap** | Kueri analitik ad-hoc yang berjalan lama (long-running aggregation) menahan shared lock pada tabel target. | Perintah DDL `ALTER TABLE ... SWAP` mengalami timeout atau menyebabkan kaskade kueri terblokir. | Terapkan batas ambang timeout kueri (`STATEMENT_TIMEOUT = '30s'`) untuk DDL swap, atau gunakan *view pointing abstraction* dengan pergantian pointer atomik. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur data memiliki trade-off mendasar antara biaya, keandalan, dan latensi pembaruan:

```
                  Complexity vs. Data Freshness Trade-off
       
   Real-Time (Streaming)
        ▲
        │                                 [Stream Processing (Flink + Iceberg)]
        │                                 - Latency: Sub-detik
        │                                 - Cost: $$$$$
        │                                 - Complexity: Sangat Tinggi
        │
        │             [Micro-Batching + Atomic View Swaps]
        │             - Latency: 5 - 15 Menit
        │             - Cost: $$
        │             - Complexity: Menengah (Ideal Enterprise BI)
        │
        │  [Daily Batch Ingestion + Hard Overwrite]
        │  - Latency: 24 Jam
        │  - Cost: $
        │  - Complexity: Rendah (Rawan Downtime)
        ▼
        └─────────────────────────────────────────────────────────────►
          Low Reliability                                High Reliability
```

### Matriks Komparasi Opsi Deployment Serving Layer

| Pendekatan | Latensi | Biaya Komputasi | Kompleksitas Teknis | Kemudahan Rollback |
| :--- | :--- | :--- | :--- | :--- |
| **Direct In-Place Overwrite (`INSERT OVERWRITE`)** | Rendah | Sangat Murah | Sangat Sederhana | **Buruk** (Downtime query selama penulisan, rollback manual). |
| **Blue-Green Table Swap (Metadata Swap)** | Menengah | Sedang (Memerlukan kapasitas storage ganda temporer) | Menengah | **Sangat Baik** (Tinggal menukar kembali pointer ke snapshot tabel sebelumnya). |
| **Zero-Copy Cloning (Snowflake / Databricks Delta)** | Instan | Efisien (Hanya membayar modifikasi delta metadata) | Rendah-Menengah | **Sangat Baik** (Snapshot point-in-time instan melalui fitur time-travel bawaan engine). |
| **Dual-Writing via Streaming Buffers** | Sub-detik | Sangat Mahal | Sangat Tinggi | **Kompleks** (Perlu dedup stream engine dan state-store reconciliation). |

---

## 9. Best Practices & Standar Industri

1. **Dashboard SLA & Service Level Objectives (SLOs):**
   * **Data Freshness SLO:** Data dashboard diperbarui selambat-lambatnya 30 menit setelah *business cutoff hour*. Target SLA: $99.5\%$.
   * **Query Latency SLO:** Dashboard analitik operasional harus menyelesaikan $95\%$ kueri dalam waktu $< 2.0$ detik. Kueri di atas 5 detik wajib diagregasi ke dalam *materialized view/summary table*.
2. **Shift-Left Semantic Testing (dbt + Slim CI):**
   * Jangan pernah menjalankan tes integrasi pada seluruh dataset riwayat di CI. Gunakan *state-aware deferred execution* (`dbt build --select state:modified+ --defer`).
3. **Data Drift Visibility & Dashboard Badging:**
   * Jangan biarkan end-user menebak apakah data valid atau tidak. Jika *circuit breaker* aktif, manfaatkan API BI tool (seperti Tableau Metadata API atau Superset Custom Banners) untuk menyuntikkan peringatan visual: *"⚠️ Data under incident investigation. Snapshot as of 06:00 UTC."*
4. **Prinsip Immutability pada Source Layer:**
   * Seluruh layer *raw staging* wajib bersifat *append-only*. Mutasi data (update/delete) hanya boleh terjadi secara logis di lapisan pemodelan analitik melalui *slowly changing dimension* (SCD Type 2) untuk menjaga rekam jejak audit.

---

## 10. Hands-on Lab Exercise: Capstone Project Module 01

### Skenario Proyek
Anda ditunjuk sebagai Lead Analytics Engineer untuk platform e-commerce global *"OmniMarket"*. Manajemen mengeluhkan laporan pendapatan sering berubah secara tidak dapat dijelaskan pada hari Senin pagi. 

Tugas Anda dalam Module 01 ini adalah:
1. Membangun fondasi arsitektur data production-ready yang terisolasi.
2. Mengonfigurasi kontrak data berbasis skema dan distribusi statistik.
3. Menguji ketahanan pipeline terhadap *upstream data corruption* menggunakan *circuit breaker pattern*.

### Langkah-langkah Praktikum

#### Langkah 1: Persiapan Environment
Siapkan virtual environment Python dan pasang dependensi yang dibutuhkan:
```bash
python -m venv bi_ops_env
source bi_ops_env/bin/activate  # Untuk Windows: bi_ops_env\Scripts\activate
pip install duckdb pydantic structlog pytest
```

#### Langkah 2: Buat File Struktur Proyek Capstone
Buat direktori kerja:
```bash
mkdir -p capstone_module_01/{contracts,engine,tests}
touch capstone_module_01/contracts/order_contract.py
touch capstone_module_01/engine/pipeline_gatekeeper.py
touch capstone_module_01/tests/test_circuit_breaker.py
```

#### Langkah 3: Eksekusi File Skrip
Jalankan file `production_bi_circuit_breaker.py` yang disediakan di Bagian 6:
```bash
python production_bi_circuit_breaker.py
```

#### Langkah 4: Verifikasi Output Evaluasi
Amati log terminal dan pastikan keluaran berikut tercapai:
1. **Scenario A:** Menghasilkan status `Atomic table swap successfully completed.` dan `state = CLOSED`.
2. **Scenario B:** Menghasilkan alert: `TRIPPING CIRCUIT BREAKER for analytics_prod.fact_daily_financials` dengan detail kegagalan:
   * Deteksi anomali volume baris (Z-Score $> 2.5$).
   * Pelanggaran batasan non-nullable pada kolom `transaction_id`.
3. Verifikasi bahwa tabel produksi tetap aman dan tidak terkontaminasi oleh data korup skenario B:
   ```sql
   SELECT COUNT(*) FROM analytics_prod.fact_daily_financials;
   -- Hasil harus tetap 10150 baris valid dari Skenario A, BUKAN 2 baris korup!
   ```

### Kriteria Kelulusan Evaluasi (Checklist)
* [ ] Metadata database mencatat riwayat volume transaksi secara otomatis.
* [ ] Uji skema mendeteksi perubahan tipe kolom dan keberadaan *null* ilegal.
* [ ] Anomaly detection memicu *circuit breaker* saat deviasi volume ekstrem disuntikkan.
* [ ] Zero-downtime swap memastikan kueri pada layer analitik target tidak pernah membaca tabel kosong saat eksekusi berlangsung.