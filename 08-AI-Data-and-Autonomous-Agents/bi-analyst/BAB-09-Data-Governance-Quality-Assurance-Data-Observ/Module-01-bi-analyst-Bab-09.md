# Bab 09: Data Governance, Quality Assurance & Data Observability
## Modul 01: Enterprise Data Quality Frameworks, Observability Pipelines, dan Automated Semantic Governance

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendesain Arsitektur Data Observability Multi-Layer**: Mengimplementasikan lima pilar data observability (*Freshness, Volume, Schema, Distribution, Lineage*) ke dalam *data pipeline* analitik dan *autonomous agent context engine*.
2. **Mengonstruksi Data Contract Machine-Readable**: Merancang spesifikasi *Data Contract* menggunakan JSON Schema/YAML untuk menegakkan SLA (*Service Level Agreement*) dan SLO (*Service Level Objective*) antara tim produsen data (*upstream*) dan konsumen data (*BI/AI agents downstream*).
3. **Membangun Circuit Breaker & Data Quality Gateways**: Mengembangkan *automated data quality circuit breaker* berbasis Python yang mampu menghentikan propagasi data korup ke *Semantic Layer* secara *fail-closed* sebelum dikonsumsi oleh *dashboard* eksekutif atau *Large Language Model* (LLM).
4. **Melacak Column-Level Data Lineage End-to-End**: Mengintegrasikan ekstraksi metadata dan *column-level lineage* menggunakan standar OpenLineage untuk mendiagnosis analisis dampak (*impact analysis*) dan akar masalah (*root cause analysis*) kegagalan data pipeline.
5. **Menerapkan Dynamic Anomaly Detection pada Distribusi Metrik**: Mengimplementasikan algoritma statistik (*Z-score*, *Interquartile Range*, dan *Modified Z-Score*) untuk mendeteksi *silent data corruption* dan anomali distribusi data tanpa *hardcoded threshold*.

---

### 2. Concept Overview

Dalam era modern di mana analitik bisnis tidak hanya dikonsumsi oleh manusia melalui visualisasi BI, tetapi juga dijadikan *ground truth context* bagi *autonomous AI agents* (RAG, Text-to-SQL, Agentic Workflows), kegagalan integritas data membawa risiko eksponensial. *Garbage in, garbage out* bertransformasi menjadi *garbage in, autonomous disaster out*.

```
+-----------------------------------------------------------------------------------+
|                                  MENTAL MODEL                                     |
|                                                                                   |
|   Traditional BI:                                                                 |
|   Raw Data  --->  ETL  --->  Data Warehouse  --->  Dashboard  --->  Human Catches |
|                                                                     Error (Hours) |
|                                                                                   |
|   Autonomous AI & Modern BI Platform:                                            |
|   +---------------+     Data Contract Enforcement                                 |
|   | Data Producer | ---------------------------------+                            |
|   +---------------+                                  |                            |
|           |                                          v                            |
|           v          +--------------------------------------------------------+   |
|     [ Ingestion ] -> | Quality Gate / Circuit Breaker (Fail-Fast Validation) |   |
|                      +--------------------------------------------------------+   |
|                                     |                     |                       |
|                          (Passes)   v          (Fails)    v                       |
|                      +--------------------+     +-------------------+             |
|                      |  Validated Storage |     | Dead Letter Queue |             |
|                      +--------------------+     | & Alert Manager   |             |
|                                |                +-------------------+             |
|                                v                                                  |
|                      +--------------------+                                       |
|                      |   Semantic Layer   | <--- OpenLineage Observability        |
|                      +--------------------+                                       |
|                             /        \                                            |
|                            v          v                                           |
|                   BI Dashboard     Autonomous AI Agent (Zero-Hallucination Data)  |
+-----------------------------------------------------------------------------------+
```

#### The 5 Pillars of Data Observability

1. **Freshness (Kebaruan Data)**: Memastikan data diperbarui sesuai jadwal frekuensi yang disepakati (SLA). Mengukur selisih waktu antara *event timestamp*, *processing timestamp*, dan ketersediaan data di target analitik.
2. **Volume (Kelengkapan Kuantitas)**: Mendeteksi anomali pada jumlah record yang masuk. Volume drop mengindikasikan adanya upstream pipeline crash, sedangkan volume spike yang tidak wajar dapat menandakan duplikasi atau infinite retry loop.
3. **Schema (Struktur & Tipe Data)**: Memantau stabilitas skema data. Mencegah silent schema drift seperti perubahan tipe data (`INTEGER` ke `STRING`), penghapusan kolom esensial, atau penambahan atribut yang melanggar kontrak data.
4. **Distribution (Integritas Nilai)**: Memvalidasi rentang nilai data (*statistical ranges*), persentase *nullability*, rasio kardinalitas unik, dan deviasi distribusi nilai numerik atau kategorikal.
5. **Lineage (Jejak Kausalitas Data)**: Memetakan relasi asal-usul data dari titik entri, transformasi perantara, hingga ke metrik dashboard dan *agent context retrieval*.

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan tata kelola dan observabilitas data mengakibatkan dampak finansial dan operasional yang signifikan:

* **Silent Data Corruption**: Pipeline ETL/ELT tidak melempar error (exit code 0), namun kolom `transaction_amount` bernilai `0` atau `NULL` karena perubahan skema API upstream. Eksekutif membuat keputusan alokasi modal berdasarkan metrik revenue yang salah hitung.
* **Autonomous Agent Hallucination Trigger**: Ketika Text-to-SQL atau Semantic Search agent mengakses semantic layer yang terkontaminasi anomali distribusi nilai, agent akan menghasilkan penalaran salah yang dijalankan secara otomatis (misal: memicu otomatisasi suspend akun pelanggan bernilai tinggi).
* **Compliance & Audit Liability**: Regulasi perbankan, HIPAA, dan GDPR mewajibkan ketertelusuran (*lineage*) data historis serta pembatasan akses data PII (*Personally Identifiable Information*). Ketiadaan tata kelola semantik dapat mengakibatkan sanksi penalti jutaan dolar.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur arsitektur Observabilitas Data dan Validasi Kualitas yang beroperasi di antara lapisan produsen dan lapisan konsumsi (*Semantic Layer*):

```
+--------------------------------------------------------------------------------------------------+
|                           ENTERPRISE DATA OBSERVABILITY ARCHITECTURE                             |
+--------------------------------------------------------------------------------------------------+

 [ Upstream Event Streams / OLTP Databases ]
                    |
                    | Raw Data Stream / Batch Ingestion
                    v
 +-----------------------------------------------------------------------+
 | STEP 1: Ingestion & Contract Evaluation                               |
 |   - Data Contract Registry (JSON Schema / YAML Specs)                 |
 |   - Schema Conformance Validator (Structural Integrity)               |
 +-----------------------------------------------------------------------+
                    |
                    v
 +-----------------------------------------------------------------------+
 | STEP 2: In-Memory Validation Engine & Statistical Profiler            |
 |   - DuckDB High-Performance Vectorized Profiling                      |
 |   - Statistical Asserter (Null Rate, Outliers, Z-Score Drift)         |
 +-----------------------------------------------------------------------+
             /                                           \
    (PASSED DATA INTEGRITY)                     (FAILED DATA INTEGRITY)
            |                                               |
            v                                               v
 +-------------------------------------+       +------------------------------------+
 | STEP 3A: Production Semantic Store  |       | STEP 3B: Circuit Breaker Isolation |
 |   - Idempotent Merge / Append       |       |   - Quarantine (Dead Letter Queue) |
 |   - Materialized Metric Views       |       |   - Automated PagerDuty / Slack    |
 +-------------------------------------+       +------------------------------------+
            |                                               |
            |-- Emits Run Event Metadata                     |-- Emits Failure Trace
            v                                               v
 +-----------------------------------------------------------------------+
 | STEP 4: Metadata & Observability Bus (OpenLineage Standard)           |
 |   - Lineage Collector Service (Marquez / Atlan / DataHub)             |
 |   - Metric Observability Dashboard (Grafana / Prometheus)             |
 +-----------------------------------------------------------------------+
            |
            +------------------------------------+
            |                                    |
            v                                    v
 [ BI Dashboards & Semantic Layer ]    [ LLM Context & Autonomous Agents ]
   (Executive Metrics, KPIs)             (Deterministic, Validated Data)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Data Contract Paradigm
Data Contract adalah perjanjian tertulis yang bersifat *declarative* dan *executable* antara produsen (*software engineers*) dan konsumen data (*BI analysts, ML engineers*). 

Struktur Data Contract mencakup:
* **Schema Definition**: Penamaan kolom, tipe data, dan batasan nullability.
* **Semantic Constraints**: Definisi domain bisnis (contoh: `status` harus bernilai salah satu dari `['PENDING', 'SETTLED', 'REFUNDED']`).
* **SLA/SLO Expectations**: Toleransi keterlambatan data (*freshness SLA*) dan ambang batas kelengkapan volume (*completeness SLO*).

#### 5.2 Dynamic Statistical Anomaly Detection
Memvalidasi data dengan ambang batas kaku (*hardcoded thresholds*) seperti `amount < 1000000` tidak adaptif terhadap pertumbuhan bisnis alami atau tren musiman. Sistem modern menerapkan metode statistik dinamis:

* **Modified Z-Score (Median Absolute Deviation / MAD)**: Lebih robust terhadap *extreme outliers* dibandingkan standar deviasi biasa.
  $$\text{MAD} = \text{median}(|X_i - \tilde{X}|)$$
  $$M_i = \frac{0.6745 \cdot (X_i - \tilde{X})}{\text{MAD}}$$
  Di mana $\tilde{X}$ adalah median dari distribusi metrik historis. Jika $|M_i| > 3.5$, nilai tersebut diklasifikasikan sebagai anomali potensial.

#### 5.3 Automated Circuit Breaking
Jika data yang masuk melanggar *Critical Assertions*:
1. Pipeline langsung memutus eksekusi sinkronisasi ke tabel target (*fail-fast*).
2. Data yang gagal dialihkan ke tabel karantina (*dead-letter storage*) untuk audit forensik.
3. Metadata kesalahan dipancarkan ke *OpenLineage Event Collector* dan sistem notifikasi on-call (*PagerDuty/Slack*).
4. Konsumsi analitik tetap menggunakan snapshot data valid sebelumnya tanpa terjadi down-time atau distorsi agregasi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end sistem tata kelola data, validasi kualitas, dan observabilitas dengan spesifikasi:
* **Python 3.11+** dengan strict type hinting.
* **DuckDB** sebagai vectorized in-memory compute engine untuk pemrosesan berkecepatan tinggi.
* **Pydantic V2** untuk pemodelan Data Contract.
* **OpenLineage-compliant Run Event Emitter** untuk melacak lineage dan metadata eksekusi.
* **Circuit Breaker Pattern** yang menghentikan pipeline saat terjadi anomali kritis.

```python
#!/usr/bin/env python3
"""
Enterprise Data Governance, Quality Assurance & Observability Engine.
Standard: GEMINI.md Enterprise Grade Architecture.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import duckdb
from pydantic import BaseModel, Field, ValidationError

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("DataObservabilityEngine")


# ============================================================================
# DOMAIN MODELS & DATA CONTRACT SPECIFICATION
# ============================================================================
class CriticalityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    CRITICAL = "CRITICAL"


class ColumnRule(BaseModel):
    name: str
    data_type: str
    nullable: bool = False
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class DataContract(BaseModel):
    dataset_name: str
    version: str
    freshness_max_lag_minutes: int
    criticality: CriticalityLevel
    columns: List[ColumnRule]


# ============================================================================
# OBSERVABILITY & OPENLINEAGE COMPLIANT EVENT DEFINITION
# ============================================================================
@dataclass(frozen=True)
class OpenLineageEvent:
    event_type: str  # START, RUNNING, COMPLETE, FAIL
    event_time: str
    run_id: str
    job_name: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    assertions: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# ============================================================================
# STATISTICAL ANOMALY DETECTOR ENGINE
# ============================================================================
class StatisticalAnomalyDetector:
    """
    Mendeteksi anomali volume dan nilai menggunakan Modified Z-Score (MAD).
    """

    @staticmethod
    def calculate_modified_z_score(
        current_value: float, historical_values: List[float]
    ) -> float:
        if not historical_values or len(historical_values) < 3:
            return 0.0

        sorted_vals = sorted(historical_values)
        n = len(sorted_vals)
        median = (
            sorted_vals[n // 2]
            if n % 2 != 0
            else (sorted_vals[(n // 2) - 1] + sorted_vals[n // 2]) / 2.0
        )

        deviations = [abs(x - median) for x in historical_values]
        sorted_devs = sorted(deviations)
        mad = (
            sorted_devs[n // 2]
            if n % 2 != 0
            else (sorted_devs[(n // 2) - 1] + sorted_devs[n // 2]) / 2.0
        )

        if mad == 0:
            # Fallback jika median absolute deviation bernilai nol
            return 0.0

        modified_z = (0.6745 * (current_value - median)) / mad
        return float(modified_z)


# ============================================================================
# EXCEPTIONS & CIRCUIT BREAKER
# ============================================================================
class CircuitBreakerTrippedError(Exception):
    """Dilempar ketika validasi kritis gagal dan data pipeline dihentikan seketika."""
    pass


# ============================================================================
# QUALITY ASSURANCE & OBSERVABILITY PIPELINE ENGINE
# ============================================================================
class DataQualityEngine:
    def __init__(self, contract: DataContract, historical_row_counts: List[float]) -> None:
        self.contract = contract
        self.historical_row_counts = historical_row_counts
        self.con = duckdb.connect(database=":memory:")
        self.run_id = str(uuid.uuid4())

    def _emit_lineage(
        self, event_type: str, assertions: List[Dict[str, Any]], error_detail: Optional[str] = None
    ) -> None:
        event = OpenLineageEvent(
            event_type=event_type,
            event_time=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            job_name=f"job_validate_{self.contract.dataset_name}",
            inputs=[{"namespace": "s3_bronze", "name": f"raw_{self.contract.dataset_name}"}],
            outputs=[{"namespace": "snowflake_gold", "name": f"analytics_{self.contract.dataset_name}"}],
            assertions=assertions,
        )
        logger.info(f"OpenLineage Event Emitted [{event_type}]:\n{event.to_json()}")
        if error_detail:
            logger.error(f"Tracing Detail for Run {self.run_id}: {error_detail}")

    def execute_pipeline(self, raw_data_json: str, reference_timestamp: datetime) -> bool:
        """
        Mengeksekusi siklus validasi menyeluruh:
        1. Ingest Data Mentah ke DuckDB
        2. Schema Verification (Struktur & Tipe)
        3. Statistical Volume Check (Modified Z-Score)
        4. Freshness SLA Validation
        5. Column-Level Semantic Assertions
        6. Circuit Breaker Execution
        """
        logger.info(f"Starting Data Observability Engine for {self.contract.dataset_name} [Run ID: {self.run_id}]")
        self._emit_lineage(event_type="START", assertions=[])

        # Step 1: Load Data
        try:
            self.con.execute(
                f"CREATE OR REPLACE TABLE raw_stage AS SELECT * FROM read_json_auto('{raw_data_json}')"
            )
        except Exception as e:
            err_msg = f"Fatal Ingestion Error: Gagal membaca data JSON mentah: {str(e)}"
            self._emit_lineage(event_type="FAIL", assertions=[], error_detail=err_msg)
            raise CircuitBreakerTrippedError(err_msg) from e

        assertions_result: List[Dict[str, Any]] = []
        is_circuit_broken = False
        failure_reasons: List[str] = []

        # Step 2: Volume Anomaly Validation
        total_rows = self.con.execute("SELECT COUNT(*) FROM raw_stage").fetchone()[0]
        z_score_volume = StatisticalAnomalyDetector.calculate_modified_z_score(
            float(total_rows), self.historical_row_counts
        )
        volume_status = "PASSED" if abs(z_score_volume) < 3.5 else "FAILED"
        assertions_result.append({
            "assertion": "volume_anomaly_check",
            "metric_value": total_rows,
            "modified_z_score": round(z_score_volume, 3),
            "status": volume_status,
        })

        if volume_status == "FAILED" and self.contract.criticality == CriticalityLevel.CRITICAL:
            is_circuit_broken = True
            failure_reasons.append(f"Volume anomali terdeteksi: {total_rows} rows (Z-Score: {z_score_volume:.2f})")

        # Step 3: Schema Structure & Nullability Assertions
        existing_cols = {
            col[0]: col[1]
            for col in self.con.execute("DESCRIBE raw_stage").fetchall()
        }

        for rule in self.contract.columns:
            # Kolom wajib ada
            if rule.name not in existing_cols:
                assertions_result.append({
                    "assertion": f"column_existence_{rule.name}",
                    "status": "FAILED",
                    "reason": "Missing mandatory column",
                })
                is_circuit_broken = True
                failure_reasons.append(f"Kolom wajib '{rule.name}' tidak ditemukan pada skema data.")
                continue

            # Nullability Check
            if not rule.nullable:
                null_count = self.con.execute(
                    f"SELECT COUNT(*) FROM raw_stage WHERE {rule.name} IS NULL"
                ).fetchone()[0]
                status = "PASSED" if null_count == 0 else "FAILED"
                assertions_result.append({
                    "assertion": f"nullability_check_{rule.name}",
                    "metric_value": null_count,
                    "status": status,
                })
                if status == "FAILED":
                    is_circuit_broken = True
                    failure_reasons.append(f"Kolom '{rule.name}' melanggar non-nullability ({null_count} nulls ditemukan).")

            # Domain Value Whitelist Check
            if rule.allowed_values:
                allowed_str = ", ".join([f"'{val}'" for val in rule.allowed_values])
                invalid_count = self.con.execute(
                    f"SELECT COUNT(*) FROM raw_stage WHERE {rule.name} NOT IN ({allowed_str}) AND {rule.name} IS NOT NULL"
                ).fetchone()[0]
                status = "PASSED" if invalid_count == 0 else "FAILED"
                assertions_result.append({
                    "assertion": f"allowed_values_{rule.name}",
                    "invalid_count": invalid_count,
                    "status": status,
                })
                if status == "FAILED":
                    is_circuit_broken = True
                    failure_reasons.append(f"Kolom '{rule.name}' memiliki {invalid_count} baris di luar batasan domain bisnis.")

            # Value Range Boundary Checks
            if rule.min_value is not None or rule.max_value is not None:
                min_bound = rule.min_value if rule.min_value is not None else -math.inf
                max_bound = rule.max_value if rule.max_value is not None else math.inf
                out_of_bounds = self.con.execute(
                    f"SELECT COUNT(*) FROM raw_stage WHERE ({rule.name} < {min_bound} OR {rule.name} > {max_bound}) AND {rule.name} IS NOT NULL"
                ).fetchone()[0]
                status = "PASSED" if out_of_bounds == 0 else "FAILED"
                assertions_result.append({
                    "assertion": f"boundary_range_{rule.name}",
                    "out_of_bounds_count": out_of_bounds,
                    "status": status,
                })
                if status == "FAILED":
                    is_circuit_broken = True
                    failure_reasons.append(f"Kolom '{rule.name}' memiliki {out_of_bounds} baris di luar jangkauan [{min_bound}, {max_bound}].")

        # Step 4: Freshness SLA Check
        if "event_timestamp" in existing_cols:
            max_ts_str = self.con.execute("SELECT MAX(event_timestamp) FROM raw_stage").fetchone()[0]
            if max_ts_str:
                max_ts = datetime.fromisoformat(str(max_ts_str).replace("Z", "+00:00"))
                lag_minutes = (reference_timestamp - max_ts).total_seconds() / 60.0
                is_fresh = lag_minutes <= self.contract.freshness_max_lag_minutes
                status = "PASSED" if is_fresh else "FAILED"
                assertions_result.append({
                    "assertion": "freshness_sla_check",
                    "lag_minutes": round(lag_minutes, 2),
                    "sla_limit": self.contract.freshness_max_lag_minutes,
                    "status": status,
                })
                if status == "FAILED":
                    is_circuit_broken = True
                    failure_reasons.append(f"Pelanggaran Freshness SLA: Keterlambatan data {lag_minutes:.2f} menit melebihi batas {self.contract.freshness_max_lag_minutes} menit.")

        # Step 5: Evaluate Circuit Breaker Status
        if is_circuit_broken:
            full_error = " | ".join(failure_reasons)
            self._emit_lineage(event_type="FAIL", assertions=assertions_result, error_detail=full_error)
            raise CircuitBreakerTrippedError(
                f"[CIRCUIT BREAKER AKTIF] Pipeline dihentikan untuk mencegah kontaminasi: {full_error}"
            )

        # Step 6: Success Completion
        self._emit_lineage(event_type="COMPLETE", assertions=assertions_result)
        logger.info(f"Pipeline SUKSES: Semua data assertion lulus kontrak. Data dipromosikan ke Semantic Store.")
        return True


# ============================================================================
# DEMONSTRATION & VERIFICATION RUNNER
# ============================================================================
if __name__ == "__main__":
    import tempfile

    # 1. Definisikan Data Contract untuk Transaksi Keuangan
    contract_spec = DataContract(
        dataset_name="financial_transactions",
        version="1.2.0",
        freshness_max_lag_minutes=60,
        criticality=CriticalityLevel.CRITICAL,
        columns=[
            ColumnRule(name="transaction_id", data_type="VARCHAR", nullable=False),
            ColumnRule(name="user_id", data_type="VARCHAR", nullable=False),
            ColumnRule(name="amount", data_type="DOUBLE", nullable=False, min_value=0.01, max_value=500000.0),
            ColumnRule(name="status", data_type="VARCHAR", nullable=False, allowed_values=["PENDING", "SETTLED", "CANCELLED"]),
            ColumnRule(name="event_timestamp", data_type="TIMESTAMP", nullable=False),
        ],
    )

    # 2. Riwayat volume historis (sekitar 100 baris per batch)
    historical_volumes = [98.0, 102.0, 100.0, 95.0, 105.0, 99.0, 101.0]

    # Skenario A: Data Valid (Should Pass)
    valid_payload = [
        {"transaction_id": "TX1001", "user_id": "USR01", "amount": 150.50, "status": "SETTLED", "event_timestamp": "2026-03-30T10:00:00Z"},
        {"transaction_id": "TX1002", "user_id": "USR02", "amount": 2999.00, "status": "PENDING", "event_timestamp": "2026-03-30T10:15:00Z"},
        {"transaction_id": "TX1003", "user_id": "USR03", "amount": 45.00, "status": "CANCELLED", "event_timestamp": "2026-03-30T10:25:00Z"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_valid:
        json.dump(valid_payload, tmp_valid)
        tmp_valid_path = tmp_valid.name

    print("\n" + "=" * 80)
    print("RUNNING SCENARIO A: VALID DATA")
    print("=" * 80)
    engine_a = DataQualityEngine(contract=contract_spec, historical_row_counts=[3.0, 3.0, 3.0, 4.0, 3.0])
    current_time_ref = datetime.fromisoformat("2026-03-30T10:30:00+00:00")
    engine_a.execute_pipeline(raw_data_json=tmp_valid_path, reference_timestamp=current_time_ref)

    # Skenario B: Korup (Negative Amount & Domain Status Liar)
    corrupted_payload = [
        {"transaction_id": "TX2001", "user_id": "USR04", "amount": -99.00, "status": "SETTLED", "event_timestamp": "2026-03-30T10:00:00Z"},
        {"transaction_id": "TX2002", "user_id": "USR05", "amount": 500.00, "status": "HACKED_STATUS", "event_timestamp": "2026-03-30T10:05:00Z"},
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_corrupt:
        json.dump(corrupted_payload, tmp_corrupt)
        tmp_corrupt_path = tmp_corrupt.name

    print("\n" + "=" * 80)
    print("RUNNING SCENARIO B: CORRUPTED DATA TRIGGERING CIRCUIT BREAKER")
    print("=" * 80)
    engine_b = DataQualityEngine(contract=contract_spec, historical_row_counts=[2.0, 2.0, 2.0, 2.0])
    try:
        engine_b.execute_pipeline(raw_data_json=tmp_corrupt_path, reference_timestamp=current_time_ref)
    except CircuitBreakerTrippedError as cb_err:
        print(f"\n[INTERCEPTED BY ARCHITECTURE]: {cb_err}")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case | Mekanisme Kegagalan | Strategi Mitigasi Produksi |
| :--- | :--- | :--- |
| **Silent Schema Widening / Truncation** | Database OLTP mengubah kolom `DECIMAL(18, 4)` menjadi `FLOAT` atau memotong `VARCHAR(255)` menjadi `VARCHAR(50)`, mengakibatkan hilangnya presisi angka finansial tanpa memicu syntax error. | Terapkan validasi tipe data presisi tinggi menggunakan vectorized scanning sebelum operasi load/merge; tolak tipe floating-point untuk transaksi moneter. |
| **Cold-Start Problem pada Anomaly Detection** | Tabel baru atau metrik bisnis yang baru diluncurkan tidak memiliki riwayat data historis yang cukup ($N < 10$), sehingga MAD atau Z-Score menghasilkan deviasi semu (*false positive panic*). | Sediakan *heuristic warmup mode*; gunakan batasan deterministik eksplisit (*min/max threshold*) selama periode *bootstrapping* 14 hari pertama. |
| **Late-Arriving / Backfilled Data Spikes** | Pipeline re-ingestion batch historis memicu peringatan *Freshness SLA* dan lonjakan *Volume Anomaly* palsu karena timestamp event masa lalu bercampur dengan ingestion timestamp saat ini. | Pisahkan metrik `processing_timestamp` (observabilitas infrastruktur pipeline) dengan `event_business_timestamp` (observabilitas domain data). |
| **Distributed Dead-Letter Queue Flooding** | Jika ribuan batch berturut-turut gagal dan dialihkan ke DLQ (*Dead Letter Queue*), volume DLQ dapat menghabiskan storage cluster analitik (*disk saturation*). | Konfigurasikan retention period dan automated rate-limiting alarm pada DLQ bucket, didukung *dead-man switch alert* jika DLQ terisi $>10\%$ dari total volume harian. |
| **Infinite Feedback Loop pada Alerting Agent** | Autonomous Agent membaca log kegagalan OpenLineage, memicu automated re-trigger pipeline secara berulang tanpa perbaikan skema upstream (*retry loop*). | Terapkan pola *Exponential Backoff* dengan *Jitter* dan batasan *Max Retry Limit* (maksimal 3 percobaan) sebelum mengunci status job menjadi `BLOCKED_MANUAL_INTERVENTION`. |

---

### 8. Trade-offs & Alternatif Solusi

```
        ┌────────────────────────────────────────────────────────┐
        │       Data Quality & Observability Trade-off Space      │
        └────────────────────────────────────────────────────────┘
                 Fail-Closed Engine (Data Contract Guard)
                               ▲
                               │
                               │   * Great Expectations
                               │   * In-Memory Vectorized (DuckDB)
                               │
       High Latency ───────────┼─────────── Low Latency / Streaming
       / Batch Heavy           │            * Soda Core / In-Stream Checks
                               │
                               ▼
                  Fail-Open / Passive Monitoring
                       (Monte Carlo / Datadog)
```

#### Komparasi Strategi Verifikasi Data

1. **Active Pre-Ingestion Guard (Fail-Closed) vs. Passive Post-Ingestion Monitoring (Fail-Open)**:
   * *Active Guard*: Data divalidasi sebelum ditulis ke semantic warehouse. **Kelebihan**: Integritas data terjamin 100%, BI dan LLM agent tidak akan pernah membaca data rusak. **Kekurangan**: Ingestion latency meningkat; jika validasi error, aliran data terhenti (*blocker*).
   * *Passive Monitoring*: Data langsung dimasukkan ke warehouse, dan anomaly detector memindai data secara asinkron di belakang layar. **Kelebihan**: *Zero latency penalty* pada ingestion. **Kekurangan**: Terjadi jeda waktu (*monitoring gap*) di mana analitik membaca data yang rusak sebelum anomali terdeteksi.

2. **DuckDB In-Memory Assertions vs. DBT Generic Tests**:
   * *DBT Tests*: Mengeksekusi query SQL langsung pada target data warehouse (misal: Snowflake, BigQuery). Sangat baik untuk transformasi in-warehouse, namun membebani biaya komputasi warehouse pada data berskala terabyte.
   * *DuckDB Engine*: Memproses validasi sebelum data menyentuh warehouse cloud. Sangat hemat biaya (*zero warehouse warehouse credits*), namun dibatasi oleh alokasi RAM pada worker container.

---

### 9. Best Practices & Standar Industri

1. **Contract-First Development**: Jangan pernah menulis pipeline konsumsi analitik tanpa Data Contract yang disetujui produsen data. Data Contract harus disimpan dalam repositori Git (*Contract as Code*) dengan linting CI/CD otomatis.
2. **Column-Level Lineage Tracing via OpenLineage Standard**: Pastikan setiap transformasi dari ingestion bronze ke semantic gold memancarkan *Lineage Run Events* yang memetakan kolom input ke metrik agregasi downstream.
3. **Data Masking at Quality Gateway**: Kolom sensitif (*PII* seperti nomor kartu kredit, alamat surel, NIK) harus diverifikasi formatnya sekaligus dimasking (hashing/tokenisasi) di gerbang data quality sebelum diarsipkan ke data lakehouse.
4. **Idempotency & Replayability**: Setiap batch yang dikarantina oleh *Circuit Breaker* harus dapat direproses secara idempoten (*atomic re-run*) setelah perbaikan skema dilakukan tanpa meninggalkan record ganda di semantic store.
5. **Decoupled Quality Severity Levels**:
   * `CRITICAL`: Memicu pemutusan sirkuit (*circuit breaker abort*) dan membangunkan tim on-call.
   * `WARNING`: Mengirim notifikasi observabilitas tanpa menghentikan jalur pipeline analitik.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Senior BI Analyst di sebuah platform e-commerce enterprise. Tim Engineering backend secara tidak sengaja mengubah format ISO string pada `order_timestamp` dan membiarkan status pesanan bernilai string kosong `""`. Tugas Anda adalah membangun script automasi pipeline yang mendeteksi error ini, mencegah kerusakan metriks dashboard eksekutif, dan mencatat lineage event.

#### Langkah 1: Persiapan Environment
Buat environment Python dan instal dependensi yang dibutuhkan:
```bash
python3 -m venv dq_lab_env
source dq_lab_env/bin/activate
pip install duckdb pydantic
```

#### Langkah 2: Buat Skrip Verifikasi Mandiri (`lab_governance_test.py`)
Tuliskan skrip pengujian berbasis skenario riil:

```python
import json
import os
from datetime import datetime, timezone
# Import class dari modul implementasi utama di atas
from data_quality_framework import (
    DataContract,
    ColumnRule,
    CriticalityLevel,
    DataQualityEngine,
    CircuitBreakerTrippedError,
)

def run_lab():
    # 1. Definisi Kontrak Bisnis
    lab_contract = DataContract(
        dataset_name="orders_stream",
        version="2.0.0",
        freshness_max_lag_minutes=30,
        criticality=CriticalityLevel.CRITICAL,
        columns=[
            ColumnRule(name="order_id", data_type="VARCHAR", nullable=False),
            ColumnRule(name="total_amount", data_type="DOUBLE", nullable=False, min_value=1.0),
            ColumnRule(name="order_status", data_type="VARCHAR", nullable=False, allowed_values=["COMPLETED", "SHIPPED"]),
        ]
    )

    # 2. Dataset Simulasi yang Mengandung Pelanggaran Kontrak
    # Kasus: order_id ORD999 memiliki order_status bernilai kosong (melanggar allowed_values)
    # Kasus: order_id ORD1000 memiliki total_amount 0.0 (melanggar min_value 1.0)
    dirty_batch = [
        {"order_id": "ORD998", "total_amount": 150.0, "order_status": "COMPLETED"},
        {"order_id": "ORD999", "total_amount": 75.0, "order_status": ""},
        {"order_id": "ORD1000", "total_amount": 0.0, "order_status": "SHIPPED"},
    ]

    dirty_file = "lab_dirty_orders.json"
    with open(dirty_file, "w") as f:
        json.dump(dirty_batch, f)

    # 3. Eksekusi Engine dan Verifikasi Pemutusan Sirkuit
    print("\n[LAB TEST]: Memulai validasi batch order kotor...")
    engine = DataQualityEngine(contract=lab_contract, historical_row_counts=[3.0, 3.0, 3.0])
    
    try:
        engine.execute_pipeline(
            raw_data_json=dirty_file,
            reference_timestamp=datetime.now(timezone.utc)
        )
        print("[-] TEST GAGAL: Pipeline tidak boleh meloloskan data korup!")
    except CircuitBreakerTrippedError as err:
        print("[+] TEST BERHASIL: Circuit Breaker aktif dan mencegah korupsi data.")
        print(f"[DETAIL ERROR]: {err}")
    finally:
        if os.path.exists(dirty_file):
            os.remove(dirty_file)

if __name__ == "__main__":
    run_lab()
```

#### Langkah 3: Eksekusi dan Verifikasi Hasil
Jalankan tes lab di terminal:
```bash
python3 lab_governance_test.py
```

Output yang diharapkan mencakup log assertion OpenLineage terstruktur yang menunjukkan kegagalan pada `allowed_values_order_status` dan `boundary_range_total_amount`, diakhiri dengan eksepsi `CircuitBreakerTrippedError` yang menghentikan proses pemuatan data ke *semantic layer*.