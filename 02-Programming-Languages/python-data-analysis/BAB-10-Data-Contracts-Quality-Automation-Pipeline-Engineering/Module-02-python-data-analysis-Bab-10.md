# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Data Contracts, Quality Automation, & Pipeline Engineering**  
**Kategori: 02-Programming-Languages / python-data-analysis**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan Declarative Data Contracts** pada skala *enterprise* menggunakan `pandera` dan `pydantic v2` untuk mengunci skema struktural, tipe data semantik, dan batasan statistik (*statistical invariants*).
- **Membangun Automated Quality Gates & Circuit Breakers** dalam data pipeline Python yang secara deterministik mencegat dan mengisolasi rekaman anomali (*bad data*) tanpa menghentikan beban kerja kritis (*fail-safe isolation*).
- **Mengarsitekturi Pola Dead-Letter Queue (DLQ) & Rekonsiliasi Karantina** berbasis format analitik modern (Apache Parquet) dengan metadata pelacakan garis keturunan data (*data lineage*).
- **Mengintegrasikan Automated Data Quality Testing ke dalam CI/CD Engine** guna mendeteksi *schema drift* dan regresi integritas data sebelum kode dideploy ke *production lakehouse*.
- **Mengoptimalkan Overhead Validasi** melalui komputasi tervektorisasi (*vectorized checks*), meminimalkan latensi eksekusi pipeline di bawah 5% dari total durasi I/O analitik.

---

## 2. Prerequisite

Peserta wajib menguasai:
- **Python Lanjutan**: Pemahaman mendalam tentang *type hinting* (`typing`, `TypeVar`), *decorators*, *context managers*, dan metaprogramming dasar.
- **Ekosistem Analitik Python**: Operasional manipulasi data tingkat lanjut menggunakan `pandas` (vektorisasi, *indexing*, *memory layout*) atau `polars`.
- **Dasar Rekayasa Pipeline Data**: Konsep *batch ingestion*, idempotensi, arsitektur medali (*Bronze-Silver-Gold*), dan transaksi file ACID dasar.
- **Tools Prasyarat Lingkungan**:
  - Python >= 3.11
  - `pandera[io]>=0.18.0`
  - `pydantic>=2.6.0`
  - `pyarrow>=14.0.0`
  - `pytest>=8.0.0`
  - `structlog>=24.1.0`

---

## 3. Concept & Internal Architecture

Dalam arsitektur analitik modern, **Data Contract** adalah perjanjian formal (*binding agreement*) yang dapat dieksekusi secara terprogram antara penyedia data (*upstream data producer*) dan konsumen downstream (*analytics/ML engineers*). Kontrak ini mencakup:
1. **Schema Syntax**: Tipe data, keberadaan kolom (*nullability*), format struktural.
2. **Semantic Integrity**: Batasan domain bisnis (misal: `transaction_amount >= 0`, `status IN ('SUCCESS', 'FAILED')`).
3. **Statistical Invariants & Distribution**: Batasan anomali agregat (misal: *Z-score* kurtosis, batas toleransi *null rate* < 0.1%).
4. **SLA & Lineage Metadata**: Versi kontrak (*semantic versioning*), kepemilikan (*owner*), dan klasifikasi privasi (*GDPR/PII tag*).

### Internal Architecture: Pandera Validation Engine & Execution Flow

```
[Inbound Raw Data]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│             DataFrame Engine (Pandas / PyArrow)        │
└───────────────────────┬────────────────────────────────┘
                        │ In-Memory Representation
                        ▼
┌────────────────────────────────────────────────────────┐
│           Pandera SchemaModel Interceptor              │
│                                                        │
│  ┌────────────────────┐      ┌──────────────────────┐  │
│  │ Column Type Cast   │─────▶│ Vectorized Series    │  │
│  │ & Coercion Phase   │      │ Assertion Engine     │  │
│  └────────────────────┘      └──────────┬───────────┘  │
│                                         │              │
│                                         ▼              │
│                              ┌──────────────────────┐  │
│                              │ DataFrame-Wide Multi-│  │
│                              │ Column Logic Gates   │  │
│                              └──────────┬───────────┘  │
└─────────────────────────────────────────┼──────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  │ Error Evaluation (lazy=True)                  │
                  ▼                                               ▼
         [Validation Succeeded]                         [SchemaErrors Raised]
                  │                                               │
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │ Clean Data Stream      │                      │ Vectorized Mask Index  │
     │ Target: Silver Table   │                      │ Generation             │
     └────────────────────────┘                      └────────────┬───────────┘
                                                                  │
                                                ┌─────────────────┴─────────────────┐
                                                ▼                                   ▼
                                     ┌─────────────────────┐             ┌─────────────────────┐
                                     │ Valid Records Pass  │             │ Invalid Records     │
                                     │ to Processing       │             │ Quarantined to DLQ  │
                                     └─────────────────────┘             └─────────────────────┘
```

### Mekanisme Kerja Internal

1. **Parser & Coercion Stage**: Pandera membaca metadata skema dari deklarasi berbasis kelas (`SchemaModel`). Jika opsi `coerce=True` diaktifkan, Pandera mengeksekusi konversi tipe tervektorisasi pada tingkat kolom (C-level PyArrow/Numpy array) sebelum memeriksa batasan.
2. **Lazy Error Collection Engine**: Bila `lazy=True`, validator tidak memutus alur eksekusi saat kegagalan pertama ditemukan (*short-circuit*). Sebaliknya, *engine* mengeksekusi semua *checks*, membangun *bitmask boolean*, dan mengumpulkan objek `SchemaError` ke dalam repositori kesalahan tabular multidimensi (`SchemaErrors.failure_cases`).
3. **Quarantine Mask Interception**: Dengan memanfaatkan metadata indeks dari kegagalan validasi, pipeline analitik memisahkan (*splits*) dataset in-memory ke dalam dua jalur:
   - **Clean Lane**: Menampung baris valid yang segera diteruskan ke pemrosesan analitik.
   - **Dead-Letter Queue (DLQ) Lane**: Menampung rekaman anomali yang dipaketkan bersama konteks eksekusi (*payload*, *trace ID*, aturan validasi yang gagal, waktu ingest) ke penyimpanan objek dingin (*cold storage*) untuk audit.

---

## 4. Why & What

| Dimensi | Paradigma Konvensional (*Defensive Code*) | Paradigma Modern (*Data Contracts as Code*) |
| :--- | :--- | :--- |
| **Pola Validasi** | `if df['col'].isnull().any(): ...` yang tersebar secara imperatif di tengah logika transformasi data. | Deklarasi skema sentralistik (*Single Source of Truth*) menggunakan `SchemaModel` yang terpisah dari logika bisnis. |
| **Lokasi Deteksi** | Hilir (*Downstream failure*): Dashboard rusak atau metrik ML terdegradasi setelah berminggu-minggu *silent corruption*. | Hulu (*Shift-Left Verification*): Ditolak di pintu gerbang ingest (*Ingestion Boundary*) atau saat CI/CD pull request. |
| **Penanganan Error** | Pipeline melempar *crash* fatal secara acak; seluruh batch data ditolak atau dibatalkan. | Isolasi granular: Rekaman valid tetap mengalir (*graceful degradation*), rekaman rusak dialihkan ke DLQ. |
| **Evolusi Skema** | Tak terprediksi (*Schema Drift*): Kolom baru atau tipe yang berubah langsung merusak sistem. | Versi terikat (*Semantic Versioning v1.2.0*): *Deprecation warnings* eksplisit, *backward-compatibility checks*. |
| **Audit & Observabilitas**| Log stdout tanpa format baku; sulit merekonstruksi akar anomali. | *Standardized validation report* terstruktur (JSON/Arrow), dapat diekspor langsung ke Prometheus/Datadog. |

---

## 5. How (Workflow Detail)

Implementasi produksi mengikuti alur lima langkah berikut:

```
[Extract: Raw Ingestion]
        │
        ▼
[Step 1: Load Contract Definition] ──▶ (Versioned Contract Class)
        │
        ▼
[Step 2: Execute Vectorized Validation] ──▶ (pandera.validate(lazy=True))
        │
   ┌────┴───────────────────────────┐
   │ Check Result                   │
   ▼                                ▼
[Success]                      [Failure Cases Caught]
   │                                │
   │                                ▼
   │                   [Step 3: Extract Failure Indices]
   │                                │
   │                  ┌─────────────┴─────────────┐
   │                  ▼                           ▼
   │        [Partition Clean Data]     [Step 4: Package DLQ Artifacts]
   │                  │                           │
   ▼                  ▼                           ▼
[Step 5: Write to Silver Tier]         [Write DLQ to S3 / Parquet]
                                                  │
                                                  ▼
                                       [Emit Metric Alert / PagerDuty]
```

### Rincian Alur Kerja Produksi

1. **Definisi Kontrak Deklaratif**: Kontrak didefinisikan dalam modul terisolasi menggunakan `pandera.DataFrameModel`. Setiap kolom memiliki *type specification*, aturan *nullability*, *regex constraints*, dan batasan statistik.
2. **Evaluasi Validasi Vektor Terisolasi**: Data mentah dievaluasi melalui *entry point* validator. Parameter `lazy=True` diaktifkan untuk menangkap *seluruh* pelanggaran dalam satu kali *pass*.
3. **Pemisahan Data (*Bifurcation*)**: Mengambil indeks yang tercatat dalam `failure_cases` dari pengecualian `SchemaErrors`. Menggunakan operasi *boolean indexing* native untuk memotong dataset menjadi subset data bersih dan subset data karantina.
4. **Pengemasan Dead-Letter Queue (DLQ)**: Baris anomali diperkaya dengan kolom metadata: `_failed_check`, `_schema_version`, `_ingestion_timestamp`, dan `_job_run_id`. Data disimpan dalam format Parquet terkompresi Snappy di bucket karantina.
5. **Circuit Breaking & Penegakan Toleransi**: Menghitung *Error Rate* ($\text{Error Rate} = \frac{\text{Invalid Rows}}{\text{Total Rows}}$). Jika $\text{Error Rate} > \text{Threshold}$ (misal: $> 2\%$), lemparkan `CircuitBreakerOpenException` untuk menghentikan pipeline total dan mencegah kontaminasi lebih lanjut.

---

## 6. Analogy & Diagram ASCII

### Analogi: Gerbang Kargo Bandara Internasional
Bayangkan data pipeline sebagai jalur kargo logistik bandara:
- **Pipeline Konvensional**: Petugas kargo langsung menaruh semua peti ke dalam pesawat. Di tengah penerbangan, salah satu peti bocor dan merusak sistem navigasi pesawat (dashboard analitik crash atau salah saji laba perusahaan).
- **Data Contract & DLQ**: Setiap peti melewati pemindai X-Ray otomatis (*Contract Validation*).
  - Peti yang sesuai standar langsung dimuat ke kabin pesawat (*Clean Lane -> Silver/Gold Tier*).
  - Peti yang memiliki barang berbahaya, label rusak, atau kelebihan berat (*Schema Breach*) disisihkan otomatis oleh lengan robotik ke ruang karantina (*DLQ*), lalu alarm operator berbunyi jika 5% dari peti dalam satu kontainer ditolak (*Circuit Breaker*).

### Diagram Alir Arsitektur Komponen

```
                  RAW DATA INGESTION (Batch / Microbatch)
                                     │
                                     ▼
                ┌───────────────────────────────────────────┐
                │    CONTRACT ENGINE GATE (Pandera Core)     │
                │  - Semantic Type Checking (Int64, Utf8)   │
                │  - Domain Invariants (Amount >= 0)        │
                │  - Referential & Statistical Bounds       │
                └─────────────────────┬─────────────────────┘
                                      │
                   Is Schema Valid?   │
                   ┌──────────────────┴──────────────────┐
                 YES                                     NO
                   │                                     │
                   ▼                                     ▼
      ┌─────────────────────────┐           ┌─────────────────────────┐
      │   PRODUCTION CONSUMER   │           │ LAZY ERROR INTERCEPTOR  │
      │   (Silver / Gold Layer) │           └────────────┬────────────┘
      │                         │                        │
      │  Write to Production    │                        ▼
      │  Format (Delta/Parquet) │           ┌─────────────────────────┐
      └─────────────────────────┘           │  ERROR RATE EVALUATOR   │
                                            └────────────┬────────────┘
                                                         │
                                        Is Error Rate > Threshold (e.g. 5%)?
                                        ┌────────────────┴────────────────┐
                                      YES                                 NO
                                       │                                  │
                                       ▼                                  ▼
                        ┌──────────────────────────────┐    ┌──────────────────────────┐
                        │    CIRCUIT BREAKER ACTIVATED │    │ RECORD BIFURCATION SPLIT │
                        │  - Pipeline Terminated       │    └─────────────┬────────────┘
                        │  - PagerDuty Alert Triggered │                  │
                        │  - Rollback Transaction      │                  ▼
                        └──────────────────────────────┘    ┌──────────────────────────┐
                                                            │ DEAD-LETTER QUEUE (DLQ)  │
                                                            │ - Original Raw Data      │
                                                            │ - Failure Rule Violation │
                                                            │ - Execution Trace Metadata│
                                                            └──────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### Simple Example: Kontrak Data Dasar dengan Pandera

Contoh pengenalan konsep validasi berbasis skema objek Python:

```python
import pandas as pd
import pandera as pa
from pandera.typing import Series


class SimpleTransactionContract(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(
        unique=True,
        str_matches=r"^TXN-[0-9]{8}$",
        nullable=False
    )
    user_id: Series[int] = pa.Field(ge=1, nullable=False)
    amount: Series[float] = pa.Field(ge=0.01, le=1_000_000.0)
    status: Series[str] = pa.Field(isin=["PENDING", "SETTLED", "FAILED"])

    class Config:
        strict = True  # Menolak kolom yang tidak didefinisikan


# Simulasi Data Uji
raw_payload = pd.DataFrame({
    "transaction_id": ["TXN-00000001", "TXN-00000002", "INVALID_ID"],
    "user_id": [101, 102, -5],
    "amount": [250.50, -10.0, 99.0],
    "status": ["SETTLED", "REFUNDED", "PENDING"]
})

try:
    validated_df = SimpleTransactionContract.validate(raw_payload, lazy=True)
except pa.errors.SchemaErrors as err:
    print(f"Jumlah pelanggaran kontrak: {len(err.failure_cases)}")
    print(err.failure_cases[["check", "column", "failure_case"]])
```

---

### Practical Example: Enterprise Ingestion Engine dengan DLQ & Circuit Breaker

Arsitektur produksi: membaca batch transaksi, memvalidasi kontrak, memisahkan data kotor ke DLQ dengan *lineage metadata*, dan menghentikan eksekusi jika *error budget* terlampaui.

```python
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, Any
import uuid

import numpy as np
import pandas as pd
import pandera as pa
from pandera.typing import Series
import structlog

# Inisialisasi Structured Logger
logger = structlog.get_logger("pipeline.contract_gate")


# ============================================================================
# 1. DATA CONTRACT DEFINITION
# ============================================================================
class FinancialRecordContract(pa.DataFrameModel):
    """Data Contract yang mengatur transaksi finansial ingest upstream."""
    
    txn_uuid: Series[str] = pa.Field(
        unique=True,
        str_matches=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        nullable=False,
        description="UUID v4 transaksi standar."
    )
    account_id: Series[str] = pa.Field(
        str_matches=r"^ACC-[0-9]{5}$",
        nullable=False
    )
    amount_idr: Series[float] = pa.Field(
        ge=1000.0,
        le=500_000_000.0,
        nullable=False,
        description="Nominal transaksi minimum Rp1.000 dan maks Rp500 Juta per transaksi tunggal."
    )
    processing_fee: Series[float] = pa.Field(ge=0.0, nullable=False)
    channel: Series[str] = pa.Field(
        isin=["QRIS", "VIRTUAL_ACCOUNT", "CREDIT_CARD", "OVER_THE_COUNTER"]
    )
    event_timestamp: Series[pd.Timestamp] = pa.Field(
        nullable=False,
        description="Timestamp transaksi event generator."
    )

    @pa.dataframe_check
    def check_processing_fee_less_than_amount(cls, df: pd.DataFrame) -> Series[bool]:
        """Invarian Logika Bisnis: Fee tidak boleh melebihi nominal transaksi."""
        return df["processing_fee"] < df["amount_idr"]

    class Config:
        strict = True
        coerce = True


# ============================================================================
# 2. CIRCUIT BREAKER EXCEPTION
# ============================================================================
class CircuitBreakerTrippedError(Exception):
    """Dilempar ketika metrik data rusak melebihi Service Level Objective (SLO)."""
    pass


# ============================================================================
# 3. PRODUCTION CONTRACT RUNTIME ENGINE
# ============================================================================
class EnterpriseContractInterceptor:
    def __init__(
        self,
        contract: type[pa.DataFrameModel],
        max_error_threshold_pct: float = 5.0,
        dlq_base_path: str = "./data/dlq",
        output_base_path: str = "./data/silver"
    ):
        self.contract = contract
        self.max_error_threshold_pct = max_error_threshold_pct
        self.dlq_base_path = Path(dlq_base_path)
        self.output_base_path = Path(output_base_path)
        
        self.dlq_base_path.mkdir(parents=True, exist_ok=True)
        self.output_base_path.mkdir(parents=True, exist_ok=True)

    def execute(self, df_raw: pd.DataFrame, batch_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        total_rows = len(df_raw)
        if total_rows == 0:
            logger.warn("Batch kosong diterima, melewati validasi.", batch_id=batch_id)
            return pd.DataFrame(), pd.DataFrame()

        clean_df = pd.DataFrame()
        quarantined_df = pd.DataFrame()

        try:
            # Validasi Eager/Vectorized dengan pengumpulan komprehensif
            clean_df = self.contract.validate(df_raw, lazy=True)
            logger.info("Batch lolos validasi kontrak 100%.", batch_id=batch_id, count=total_rows)
            return clean_df, quarantined_df

        except pa.errors.SchemaErrors as err:
            logger.error("Pelanggaran kontrak terdeteksi.", batch_id=batch_id, violations_count=len(err.failure_cases))
            
            # Ambil indeks baris bermasalah
            failure_indices = err.failure_cases["index"].dropna().unique()
            # Handle kegagalan skema struktural non-index level
            valid_integer_indices = [int(i) for i in failure_indices if isinstance(i, (int, np.integer))]
            
            # Segmentasi Data: Clean vs Corrupted
            quarantined_mask = df_raw.index.isin(valid_integer_indices)
            quarantined_df = df_raw[quarantined_mask].copy()
            clean_df = df_raw[~quarantined_mask].copy()

            # Hitung Rasio Error & Evaluasi Circuit Breaker
            error_rate = (len(quarantined_df) / total_rows) * 100.0
            logger.info(
                "Evaluasi Error Budget",
                batch_id=batch_id,
                total_rows=total_rows,
                corrupted_rows=len(quarantined_df),
                error_rate_pct=round(error_rate, 2),
                threshold_pct=self.max_error_threshold_pct
            )

            if error_rate > self.max_error_threshold_pct:
                error_msg = (
                    f"CIRCUIT BREAKER AKTIF: Error rate {error_rate:.2f}% "
                    f"melebihi ambang batas {self.max_error_threshold_pct}%."
                )
                logger.critical("Menghentikan pipeline untuk proteksi sistem downstream.", reason=error_msg)
                raise CircuitBreakerTrippedError(error_msg)

            # Ekstraksi dan Pemaketan DLQ
            self._write_to_dlq(quarantined_df, err.failure_cases, batch_id)

            return clean_df, quarantined_df

    def _write_to_dlq(self, corrupted_df: pd.DataFrame, failure_cases: pd.DataFrame, batch_id: str) -> None:
        """Menyimpan data terkontaminasi beserta audit trace ke Parquet."""
        execution_time = datetime.now(timezone.utc)
        
        # Aggregasi failure descriptions per index baris
        failures_summary = (
            failure_cases.groupby("index")
            .apply(lambda g: g[["check", "column", "failure_case"]].to_dict(orient="records"))
            .to_dict()
        )

        # Injeksi Metadata Karantina
        corrupted_df["_dlq_batch_id"] = batch_id
        corrupted_df["_dlq_isolated_at"] = execution_time
        corrupted_df["_dlq_failure_reasons"] = corrupted_df.index.map(
            lambda idx: str(failures_summary.get(idx, [{"check": "Structural Error", "column": "SCHEMA", "failure_case": "N/A"}]))
        )

        dlq_filename = self.dlq_base_path / f"dlq_batch_{batch_id}_{execution_time.strftime('%Y%m%d%H%M%S')}.parquet"
        corrupted_df.to_parquet(dlq_filename, index=True, engine="pyarrow")
        logger.info("Data rusak berhasil diisolasi ke DLQ storage.", dlq_target=str(dlq_filename))


# ============================================================================
# 4. SIMULASI EKSEKUSI PRODUKSI
# ============================================================================
if __name__ == "__main__":
    interceptor = EnterpriseContractInterceptor(
        contract=FinancialRecordContract,
        max_error_threshold_pct=15.0,  # Toleransi 15%
        dlq_base_path="./tmp/dlq",
        output_base_path="./tmp/silver"
    )

    batch_uuid = str(uuid.uuid4())
    
    # 10 Data Rows: 8 Valid, 2 Invalid (20% Corrupted -> Melebihi 15% jika ditargetkan)
    # Kami set 1 invalid agar 10% (Lolosan validasi DLQ tanpa trip circuit breaker)
    synthetic_batch = pd.DataFrame([
        # Row 1: Valid
        {
            "txn_uuid": "e3a89047-9201-4be6-8805-728b7e287834",
            "account_id": "ACC-10023",
            "amount_idr": 150000.0,
            "processing_fee": 2500.0,
            "channel": "QRIS",
            "event_timestamp": "2024-03-24T10:00:00"
        },
        # Row 2: Valid
        {
            "txn_uuid": "14f2e5ec-62eb-4581-8178-57d42cf38a06",
            "account_id": "ACC-10024",
            "amount_idr": 2500000.0,
            "processing_fee": 5000.0,
            "channel": "VIRTUAL_ACCOUNT",
            "event_timestamp": "2024-03-24T10:01:15"
        },
        # Row 3: INVALID (Fee > Amount & Channel Ilegal)
        {
            "txn_uuid": "d8a1c6e4-4a5f-4022-b5f7-660c1d683709",
            "account_id": "ACC-99999",
            "amount_idr": 2000.0,
            "processing_fee": 5000.0,  # INVALID: Fee > Amount
            "channel": "PAYPAL_DIRECT",  # INVALID: Bukan channel legal
            "event_timestamp": "2024-03-24T10:02:30"
        }
    ] + [
        # Sisanya 7 row data valid
        {
            "txn_uuid": str(uuid.uuid4()),
            "account_id": f"ACC-{20000+i}",
            "amount_idr": float(10000 * (i + 1)),
            "processing_fee": 500.0,
            "channel": "QRIS",
            "event_timestamp": "2024-03-24T10:05:00"
        } for i in range(7)
    ])

    print("--- MENJALANKAN PIPELINE PENJAGAAN KONTRAK DATA ---")
    clean, quarantined = interceptor.execute(synthetic_batch, batch_id=batch_uuid)
    
    print(f"\n[HASIL PEMROSESAN]")
    print(f"Total Baris Diproses : {len(synthetic_batch)}")
    print(f"Data Bersih Lolos    : {len(clean)} baris")
    print(f"Data Karantina (DLQ) : {len(quarantined)} baris")
```

---

## 8. Real World Case Study: E-Commerce Payment Reconciliation Gate

### Konteks Masalah
Sebuah payment gateway memproses transaksi senilai Rp120 Miliar per hari dari 14 kanal pembayaran mitra (OVO, GoPay, BCA Virtual Account, dsb.). Masalah terjadi ketika:
1. Salah satu upstream payment partner melakukan perubahan format output JSON secara sepihak: tipe data field `settlement_timestamp` yang semula berformat Unix epoch integer (`1711274400`) diubah menjadi string ISO-8601 (`"2024-03-24T10:00:00Z"`).
2. Pipeline analitik downstream harian langsung *crash* pada pukul 02:00 pagi.
3. Tim analitik melakukan perbaikan reaktif manual selama 6 jam. Akibatnya, laporan rekonsiliasi keuangan tertunda, memicu denda keterlambatan SLA ke Bank Indonesia dan pembekuan likuiditas merchant.

### Solusi Arsitektur
Diterapkan arsitektur **Data Contract Gate & Automatic Isolation Layer**:
- **Penerapan Schema Drift Guard**: Menggunakan Pandera dengan modul `typing.Union` dan *multi-format coercion handler* pada ingestion boundary.
- **Circuit Breaker Multi-Level**:
  - Pelanggaran skema struktural < 1%: Masuk ke DLQ secara otomatis, peringatan level P3 dikirim ke Slack. Pipeline terus berjalan tanpa memblokir transaksi 99% merchant lainnya.
  - Pelanggaran > 5%: PagerDuty memicu panggilan On-Call (P1), menghentikan pipeline transaksi finansial agar saldo mutasi merchant tidak salah hitung (*zero dirty write tolerance*).
- **Automated Quarantine Replay Pipeline**: Data pada DLQ yang disebabkan oleh pembaharuan format tanggal dapat diproses ulang (*re-ingested*) secara otomatis melalui script transformasi tanpa intervensi modifikasi database utama.

### Metrik Hasil Transformasi Produksi
- **Downtime Pipeline**: Turun dari rata-rata 14 jam per insiden menjadi **0 menit** (karena anomali otomatis terisolasi ke DLQ).
- **Lead Time to Detection (MTTD)**: Dari 4 jam setelah batch selesai menjadi **real-time (< 2 detik saat validasi ingest)**.
- **Merchant Impacted**: Berkurang dari 100% merchant terdampak saat kegagalan, menjadi **hanya 0.08%** transaksi anomali yang ditahan di buffer audit.

---

## 9. Trade-offs: Analisis Arsitektural

Setiap keputusan dalam implementasi Data Contracts memiliki konsekuensi teknis:

```
                  Validation Rigor vs. Pipeline Latency
    
    [Rigor: High]
           ▲
           │                         * Lazy SchemaModel + Cross-Column Invariants
           │                           (Komprehensif, latensi bertambah 8-15%)
           │
           │            * Single-Column Coercion Only
           │              (Cepat, memori rendah, gagal tangkap multi-kolom)
           │
           │  * Raw JSON / Permissive Parquet
           │    (Latensi ~0%, resiko tinggi silent data corruption downstream)
           │
           └──────────────────────────────────────────────────────────▶
          0%                                                        20%
                                Pipeline Latency Overhead
```

| Pendekatan | Keuntungan | Biaya / Trade-off | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Eager Validation** (`lazy=False`) | Menolak data pada kegagalan baris pertama (*Fast-fail*). Konsumsi memori minimal. | Tidak menangkap seluruh profil anomali dalam satu eksekusi batch. Tidak dapat membuat DLQ yang komprehensif. | Streaming real-time latensi rendah (misal: sensor IoT dengan Kafka window < 500ms). |
| **Lazy Multi-pass Validation** (`lazy=True`) | Memetakan semua pelanggaran di seluruh baris dan kolom. Ideal untuk DLQ routing yang presisi. | Membutuhkan alokasi memori tambahan untuk memetakan error tabular; runtime bertambah 5–12%. | Financial settlements, transaksi ERP, pemrosesan batch analitik data lakehouse harian. |
| **Strict Schema vs Evolution** (`strict=True` vs `strict=False`) | Menghentikan *unauthorized data bloat* dan potensi kebocoran PII melalui kolom tak dikenal. | Setiap penambahan kolom upstream yang sah memerlukan sinkronisasi kode contract dan deployment CI/CD. | Lingkungan kepatuhan ketat (Fintech PCI-DSS, Healthcare HIPAA). |
| **Vectorized Checks vs UDF** | Mengeksekusi verifikasi pada kecepatan C/Rust via Numpy/Arrow array. Overhead minimal. | Logika bisnis yang kompleks atau dependensi I/O eksternal (misal: validasi API eksternal) sulit divektorkan. | Skala analitik data besar (> 10 juta baris per batch). |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Row-by-Row Iterator Anti-Pattern
* **Kesalahan**: Menggunakan `.apply()` dengan fungsi Python biasa di dalam custom check Pandera:
  ```python
  # BURUK: Sangat lambat, mengunci GIL, 100x lebih lambat
  @pa.check("amount")
  def validate_amount(cls, series):
      return series.apply(lambda x: custom_external_validator(x))
  ```
* **Solusi**: Gunakan operasi boolean tervektorisasi murni (NumPy ufuncs / Pandas vectorized expressions):
  ```python
  # BENAR: Berjalan penuh pada native C-arrays
  @pa.check("amount")
  def validate_amount(cls, series: Series[float]) -> Series[bool]:
      return (series > 0) & (series < 1_000_000)
  ```

### 2. The Silent Cast Trap (`coerce=True`)
* **Kesalahan**: Mengaktifkan `coerce=True` pada kolom float yang berisi string non-numerik acak. Secara *default*, parser dapat mengubah nilai rusak menjadi `NaN`, yang kemudian lolos jika kolom tersebut tidak memiliki validasi eksplisit `nullable=False`.
* **Solusi**: Pasangkan selalu `coerce=True` dengan `nullable=False` secara ketat pada data kritis:
  ```python
  balance: Series[float] = pa.Field(coerce=True, nullable=False)
  ```

### 3. Mask Alignment Index Mismatch
* **Kesalahan**: Melakukan *filtering* data bersih menggunakan boolean mask dari dataframe yang indeksnya telah direset, sementara dataframe asli masih mempertahankan indeks lama:
  ```python
  # Runtime Bug: Alignment pandas akan menghasilkan dataframe penuh NaN!
  clean_df = df_raw[~df_raw.reset_index().index.isin(failure_indices)]
  ```
* **Solusi**: Pertahankan integritas *Primary Key* atau jalankan `df.reset_index(drop=True)` secara eksplisit di awal boundary validation sebelum kontrak dieksekusi.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa ini sebelum mempromosikan pipeline kontrak data ke *Production*:

- [ ] **Declarative Isolation**: Kontrak data disimpan dalam repositori terpisah atau modul khusus domain (`contracts/financial/v1.py`), bukan bercampur di dalam pipeline script.
- [ ] **Semantic Versioning Enforcement**: Setiap kontrak memiliki metadata versi (misal: `__version__ = "2.1.0"`). Setiap perubahan skema yang *breaking* mewajibkan kenaikan versi mayor.
- [ ] **Vectorized Assertions**: 100% validasi kustom menggunakan operasi tervektorisasi native. Tidak ada pemanggilan `.apply()`, `for` loop, atau iterasi `iterrows()`.
- [ ] **Strict Nullability & Typing**: Seluruh kolom analitik vital ditandai `nullable=False` dan tipe data dipatok secara deterministik (hindari tipe `object` serbaguna; gunakan `string[pyarrow]`, `int64`, `float64`).
- [ ] **Deterministic DLQ Schema**: File Parquet pada DLQ menyimpan data payload asli bersama kolom metadata sistem audit (`_dlq_batch_id`, `_dlq_isolated_at`, `_dlq_failure_reasons`).
- [ ] **Circuit Breaker Configuration**: Nilai ambang batas pemutus sirkuit (*error budget threshold*, misal: 2%) dikonfigurasi melalui *environment variable*, bukan di-*hardcode*.
- [ ] **CI/CD Schema Regression Tests**: Menjalankan *test suite* yang memvalidasi *golden test datasets* terhadap kontrak pada pipeline integrasi (GitHub Actions / GitLab CI) sebelum deployment.

---

## 12. Hands-on Practice

Buatlah implementasi pipeline data contract di direktori `hands-on/m02/` dengan mengikuti struktur dan langkah berikut.

### Struktur Direktori
```
hands-on/m02/
├── contracts/
│   ├── __init__.py
│   └── user_activity_contract.py
├── pipeline/
│   ├── __init__.py
│   └── ingestion_engine.py
├── tests/
│   ├── __init__.py
│   └── test_contract_pipeline.py
├── data/
│   ├── raw/
│   ├── silver/
│   └── dlq/
└── requirements.txt
```

### File: `requirements.txt`
```text
pandera[io]==0.18.0
pandas==2.2.1
pyarrow==15.0.0
pytest==8.0.2
structlog==24.1.0
```

### Langkah 1: Definisikan Kontrak Data
Tulis kode berikut pada `contracts/user_activity_contract.py`:

```python
import pandera as pa
from pandera.typing import Series


class UserActivityContract(pa.DataFrameModel):
    user_id: Series[int] = pa.Field(ge=1, nullable=False)
    session_id: Series[str] = pa.Field(str_matches=r"^SES-[A-Z0-9]{8}$", nullable=False)
    page_dwell_time_sec: Series[float] = pa.Field(ge=0.0, le=86400.0, nullable=False)
    action: Series[str] = pa.Field(isin=["VIEW", "CLICK", "PURCHASE", "EXIT"], nullable=False)
    device_os: Series[str] = pa.Field(isin=["IOS", "ANDROID", "WINDOWS", "MACOS", "LINUX"])

    @pa.dataframe_check
    def check_purchase_dwell_time(cls, df: pa.typing.DataFrame) -> Series[bool]:
        """Pola logis: User tidak bisa melakukan PURCHASE secara instan (< 1 detik)."""
        is_purchase = df["action"] == "PURCHASE"
        valid_dwell = df["page_dwell_time_sec"] >= 1.0
        return ~is_purchase | valid_dwell

    class Config:
        strict = True
        coerce = True
```

### Langkah 2: Bangun Ingestion Engine dengan DLQ
Tulis kode berikut pada `pipeline/ingestion_engine.py`:

```python
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import pandas as pd
import pandera as pa

from contracts.user_activity_contract import UserActivityContract


class ActivityPipelineGate:
    def __init__(self, output_dir: Path, dlq_dir: Path):
        self.output_dir = output_dir
        self.dlq_dir = dlq_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dlq_dir.mkdir(parents=True, exist_ok=True)

    def process_batch(self, df_raw: pd.DataFrame) -> Tuple[int, int]:
        batch_id = str(uuid.uuid4())[:8]
        try:
            clean_df = UserActivityContract.validate(df_raw, lazy=True)
            self._write_parquet(clean_df, self.output_dir / f"clean_{batch_id}.parquet")
            return len(clean_df), 0
        except pa.errors.SchemaErrors as err:
            invalid_indices = err.failure_cases["index"].dropna().astype(int).unique()
            invalid_mask = df_raw.index.isin(invalid_indices)
            
            clean_df = df_raw[~invalid_mask]
            corrupt_df = df_raw[invalid_mask].copy()

            if not clean_df.empty:
                self._write_parquet(clean_df, self.output_dir / f"clean_{batch_id}.parquet")
            
            if not corrupt_df.empty:
                corrupt_df["_dlq_isolated_at"] = datetime.now(timezone.utc)
                self._write_parquet(corrupt_df, self.dlq_dir / f"dlq_{batch_id}.parquet")

            return len(clean_df), len(corrupt_df)

    def _write_parquet(self, df: pd.DataFrame, path: Path):
        df.to_parquet(path, engine="pyarrow", index=False)
```

### Langkah 3: Otomasi Testing CI/CD
Tulis kode pengujian integrasi pada `tests/test_contract_pipeline.py`:

```python
import pytest
import pandas as pd
from pipeline.ingestion_engine import ActivityPipelineGate
from contracts.user_activity_contract import UserActivityContract


@pytest.fixture
def mock_pipeline(tmp_path):
    output_dir = tmp_path / "silver"
    dlq_dir = tmp_path / "dlq"
    return ActivityPipelineGate(output_dir=output_dir, dlq_dir=dlq_dir)


def test_contract_valid_batch_routing(mock_pipeline):
    valid_data = pd.DataFrame({
        "user_id": [1, 2],
        "session_id": ["SES-ABC12345", "SES-XYZ98765"],
        "page_dwell_time_sec": [12.5, 45.0],
        "action": ["VIEW", "PURCHASE"],
        "device_os": ["IOS", "ANDROID"]
    })
    
    clean_count, dlq_count = mock_pipeline.process_batch(valid_data)
    assert clean_count == 2
    assert dlq_count == 0


def test_contract_violating_batch_isolation(mock_pipeline):
    mixed_data = pd.DataFrame({
        "user_id": [10, -99],  # user_id -99 melanggar ge=1
        "session_id": ["SES-VALID01", "INVALID_SES_NAME"],
        "page_dwell_time_sec": [0.2, 5.0],  # Baris 0 action PURCHASE + dwell 0.2 melanggar rule
        "action": ["PURCHASE", "CLICK"],
        "device_os": ["WINDOWS", "MACOS"]
    })
    
    clean_count, dlq_count = mock_pipeline.process_batch(mixed_data)
    # Kedua baris harus ditolak:
    # Baris 0 gagal check_purchase_dwell_time
    # Baris 1 gagal user_id ge=1 dan format session_id
    assert clean_count == 0
    assert dlq_count == 2
```

Jalankan pengujian via terminal:
```bash
pytest tests/test_contract_pipeline.py -v
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `UserActivityContract` pada Hands-on Practice untuk menambahkan kolom opsional `referrer_url: Series[str]`. Aturan:
- `nullable=True`.
- Jika string terisi, string harus diawali dengan `"https://"` (gunakan parameter regex `str_matches`).

### Level Medium
Kembangkan interceptor DLQ pada `ActivityPipelineGate` agar menyimpan kolom metadata baru bernama `_error_fields_violated` yang berisi string daftar kolom spesifik yang gagal (misal: `"['user_id', 'session_id']"`). Ekstrak informasi ini secara langsung dari `err.failure_cases`.

### Level Hard
Implementasikan custom decorator bernama `@enforce_contract_with_metrics(contract_cls, error_threshold_pct)` yang membungkus fungsi transformasi analitik apa pun yang menghasilkan Pandas DataFrame. Decorator harus:
1. Memvalidasi output DataFrame terhadap `contract_cls`.
2. Jika validasi gagal, secara transparan mengisolasi anomali ke disk lokal.
3. Menghitung latensi eksekusi validasi menggunakan `time.perf_counter()`.
4. Jika persentase error melebihi `error_threshold_pct`, batalkan eksekusi dengan melempar pengecualian kustom `CircuitBreakerTrippedError` dan pastikan data tidak ditulis ke downstream.

---

## 14. Challenge

**Skenario**: Anda adalah Principal Data Architect di perusahaan unicorn logistik multi-nasional. Sistem pengiriman menerima pembaruan status pelacakan paket (*Waybill Status Telemetry*) dari kurir dengan kecepatan 50.000 events/detik. Upstream IoT edge devices sering mengalami transmisi terfragmentasi yang mengakibatkan:
1. Jam sistem acak yang mundur ke masa lalu (*backward temporal drift*).
2. Kode status transit baru yang belum terdaftar di enum bisnis internal.
3. Muatan batch sering kali mengandung duplikasi ID transaksi dengan stempel waktu berbeda.

**Tantangan**:
Rancang dan bangun mesin validasi modular berbasis Pandera/PyArrow yang mampu:
- Menegakkan konsistensi monontonik temporal: Dalam satu *waybill_id*, `checkpoint_timestamp[t]` harus selalu $\ge$ `checkpoint_timestamp[t-1]`.
- Menerapkan **Dynamic Contract Versioning Engine**: Engine harus membaca versi payload dari header (`payload_version: "v1"` vs `"v2"`), lalu secara dinamis memilih skema kontrak yang relevan tanpa menggunakan kondisional `if-else` bertingkat yang monolitik.
- Menjamin *throughput processing* minimum 10.000 records/detik pada mesin 8-core CPU standar dengan overhead komputasi validasi $\le 8\%$.
- Rancang strategi rekonsiliasi DLQ: Buat rancangan mekanisme otomatis untuk merehidrasi data dari karantina kembali ke pipeline utama begitu skema upstream yang baru telah disetujui (*Contract Schema Migration Replay*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara validasi skema imperatif (menggunakan `assert df['col'].notnull()`) dan deklaratif (menggunakan `pandera.DataFrameModel`)?**
   - *Jawaban*: Validasi deklaratif memisahkan aturan bisnis secara sentralisasi dari logika transformasi pipeline, menyediakan dokumentasi mandiri (*self-documenting*), memungkinkan validasi menyeluruh (*lazy multi-violation aggregation*), dan dapat dieksekusi secara otomatis pada CI/CD serta boundary testing.
2. **Kapan parameter `lazy=True` pada Pandera wajib digunakan dalam data pipeline enterprise?**
   - *Jawaban*: Wajib digunakan saat pipeline membutuhkan ekstraksi seluruh anomali data dalam satu batch untuk diarahkan ke Dead-Letter Queue (DLQ). Jika `lazy=False`, proses validasi langsung melempar error pada pelanggaran pertama (*fail-fast*), sehingga sisa anomali lainnya tidak dapat dipetakan secara menyeluruh.
3. **Apa efek samping dari pengaktifan `coerce=True` pada kolom bertipe data numerik?**
   - *Jawaban*: Pandera akan memaksa konversi tipe data (misal string ke float/integer). Jika data string tidak dapat diubah menjadi angka valid, konversi dapat menghasilkan `NaN` atau melempar kegagalan tipe data, yang jika tidak diproteksi dengan `nullable=False` dapat menyebabkan data rusak lolos ke lapisan analitik.
4. **Apa tujuan utama implementasi Dead-Letter Queue (DLQ) dalam pipeline data analitik?**
   - *Jawaban*: Mencegah kegagalan total (*pipeline crash*) akibat anomali minoritas, mempertahankan kelancaran transmisi data yang valid ke lapisan Silver/Gold (*high availability*), serta menyimpan rekaman yang rusak untuk kebutuhan audit forensik dan pemrosesan ulang (*replayability*).
5. **Mengapa aturan pemeriksaan unik (`unique=True`) pada kolom berbasis Pandas memiliki implikasi performa yang signifikan pada dataset besar?**
   - *Jawaban*: Pengecekan keunikan memerlukan operasi hashing global atau sorting data di seluruh partisi in-memory ($O(N)$ hingga $O(N \log N)$), yang memicu konsumsi memori tinggi dan membatasi paralelisasi streaming murni.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Bagaimana cara mencegah `Pandas` mengonsumsi memori berlebih saat melakukan validasi pada DataFrame dengan ukuran puluhan juta baris?**
   - *Jawaban*: Gunakan tipe data PyArrow native (misal: `pa.String()`, `int64[pyarrow]`), jalankan validasi dalam lingkungan partisi berbasis chunking/batching, dan pastikan assertion hanya menggunakan vectorized masks tanpa membuat salinan (*copy*) DataFrame baru di memori.
7. **Jelaskan risiko arsitektur jika sebuah pipeline analitik menerapkan Circuit Breaker dengan batas ambang persentase error yang terlalu rendah (misal: 0.001%)!**
   - *Jawaban*: Sensitivitas berlebih (*false positive alerting*) yang memicu penutupan pipeline secara prematur akibat anomali insidental yang tidak signifikan, menyebabkan terganggunya SLA ketersediaan data hilir (*high operational fatigue* bagi tim On-Call).
8. **Mengapa validasi kontrak data idealnya dieksekusi pada *Ingestion Boundary* (Bronze Layer) alih-alih di Gold Tier Data Mart?**
   - *Jawaban*: Prinsip *Shift-Left*: Mencegah biaya komputasi yang terbuang percuma untuk mentransformasikan data cacat, menghindari *dirty data pollution* pada lapisan data lakehouse bersama, serta mempermudah atribusi akar masalah ke sumber upstream langsung.
9. **Bagaimana mekanisme pendeteksian Schema Drift struktural secara terprogram jika upstream mengirimkan kolom baru yang tidak dikenali?**
   - *Jawaban*: Dengan menyetel konfigurasi kontrak `strict=True` (atau `strict='filter'`). Mode `strict=True` akan segera melempar `SchemaError` kategori struktural jika terdapat kolom tambahan yang tidak terdaftar dalam definisi kontrak.
10. **Bagaimana mengonversi error report Pandera ke format metrik yang kompatibel dengan time-series database seperti Prometheus?**
    - *Jawaban*: Mengurai dataframe `err.failure_cases`, menghitung agregasi pelanggaran per dimensi kolom dan aturan pengecekan (`check`), lalu memancarkannya (*emit*) sebagai Prometheus Counter menggunakan SDK klien dengan label `contract_name`, `column`, dan `check_type`.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Tim upstream mengganti format penanggalan dari format ISO standar UTC (`2024-03-24T10:00:00Z`) menjadi string representasi lokal tanpa offset zona waktu (`24/03/2024 10:00:00`). Pipeline Anda mendadak mengalami error parser massal.
    - *Solusi Engineering*: Aktifkan penanganan multi-format parsing tervektorisasi pada lapisan ingest, terapkan kontrak transisi dengan parser fallback (`pd.to_datetime` dengan parameter `format='mixed'`), atau tandai data non-ISO sebagai kegagalan kontrak ke DLQ sementara tim upstream dipaksa mengembalikan format standar melalui contract breaking ticket.
12. **Skenario B**: Pipeline ingestion validasi kontrak Anda memproses batch transaksi bank harian. Tiba-tiba terjadi lonjakan kegagalan validasi sebesar 12% karena nomor akun rekening upstream bertambah digit (dari 10 digit menjadi 12 digit). Threshold Circuit Breaker Anda adalah 5%. Apa tindakan arsitektural yang tepat secara urutan kronologis?
    - *Solusi Engineering*:
      1. Circuit Breaker mematikan pipeline secara otomatis untuk mencegah kegagalan rekonsiliasi.
      2. Tim on-call memvalidasi bahwa anomali bukan serangan integritas melainkan perubahan bisnis yang sah (*authorized schema change*).
      3. Rilis versi kontrak baru (misal: `v2.0.0`) dengan pola regex 10–12 digit via *hotfix pull request*.
      4. Eksekusi pengujian regresi CI/CD, deploy versi kontrak baru.
      5. Jalankan mekanisme replay untuk memproses ulang data batch yang tadi tertahan di buffer isolasi.
13. **Skenario C**: Dataset telemetri sensor kesehatan berukuran 50 GB per jam harus divalidasi. Pipeline kehabisan memori (*OOMKilled*) ketika menjalankan `Contract.validate(df, lazy=True)`.
    - *Solusi Engineering*: Tinggalkan pemuatan seluruh file 50 GB ke satu DataFrame Pandas tunggal. Ubah arsitektur menjadi pemrosesan stream/micro-batching menggunakan iterator `pyarrow.dataset` atau baca berkas Parquet per batch baris (misal: 500.000 baris per iterasi), validasi dan tulis ke Silver/DLQ secara independen per partisi untuk menjaga footprint RAM konstan di bawah 2 GB.

---

## 16. Summary

- **Data Contracts** mentransformasikan paradigma kualitas data dari pengujian imperatif ad-hoc yang reaktif menjadi arsitektur deklaratif terprogram yang menjamin keandalan data analitik secara formal.
- Menggunakan engine modern seperti **Pandera** memungkinkan tim platform analitik menerapkan validasi tervektorisasi berkinerja tinggi langsung pada struktur data in-memory (Pandas/PyArrow/Polars) tanpa beban kinerja iterasi Python native.
- Pola arsitektur **Dead-Letter Queue (DLQ)** dan **Circuit Breaker** adalah standar de facto dalam rekayasa data produksi: DLQ memastikan data valid tetap mengalir lancar saat anomali terjadi, sementara Circuit Breaker mematikan eksekusi ketika integritas data rusak secara sistemik melebihi batas toleransi bisnis.
- Penegakan kontrak pada batas ingest (*Ingestion Boundary*) yang dipadukan dengan pengujian regresi otomatis pada **CI/CD pipeline** melindungi *downstream data lakehouse* dari fenomena *silent data corruption* dan *schema drift*.