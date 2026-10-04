# Bab 04: Data Validation, Continuous Testing, & Quality Gates

## Module 01: Automated Data Validation Pipelines & Quality Gates

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang dan Mengimplementasikan *Data Contracts*** deklaratif untuk memvalidasi integritas struktural, tipe data, rentang nilai, dan keabsahan semantik data sebelum memasuki tahap pelatihan (*training*) maupun inferensi.
2. **Membangun Arsitektur *Quality Gates*** berbasis kode (*code-driven quality gates*) yang mengevaluasi metrik kelayakan data dan menghentikan eksekusi pipeline secara deterministik (*fail-fast*) saat terjadi pelanggaran data.
3. **Mengonfigurasi Mekanisme *Quarantine* dan *Dead-Letter Queue (DLQ)*** untuk data yang korup atau menyimpang (*anomalous data*) guna mengisolasi kegagalan tanpa memutus ketersediaan sistem hilir (*downstream systems*).
4. **Mendeteksi Pergeseran Distribusi Data (*Distributional & Semantic Drift*)** pada level gerbang validasi menggunakan uji statistik non-parametrik (*Kolmogorov-Smirnov*, *Wasserstein Distance*, *Population Stability Index*) sebagai prasyarat eksekusi model.
5. **Mengintegrasikan Validasi Data Kontinu ke dalam Pipeline CI/CD MLOps** menggunakan pola orkestrasi modern yang memisahkan tanggung jawab antara *Data Producer* dan *Data Consumer*.

---

### 2. Concept Overview

Dalam rekayasa perangkat lunak konvensional, kebenaran fungsional ditentukan oleh logika kode deterministik:
$$\text{Output} = f(\text{Input; Code})$$
Jika kode lulus *unit testing*, perilaku sistem cenderung dapat diprediksi. Namun, pada sistem berbasis Machine Learning (ML), logika bisnis dihasilkan secara induktif dari data:
$$\text{Logic} = \mathcal{M}(\text{Data; Algorithm})$$

Perubahan karakteristik data—meskipun skema fisik database tidak berubah—dapat merusak performa model secara drastis tanpa memicu satupun *runtime error* tradisional (*silent failure*).

```
Traditional Software:  [ Code (Dynamic) ] + [ Data (Static Structure) ] ---> [ Deterministic Output ]
ML Systems:            [ Code (Static)  ] + [ Data (Dynamic Distribution)] ---> [ Emergent Behavior   ]
```

Validasi data dalam MLOps beroperasi pada tiga layer abstraksi:

1. **Structural Validation (Skema Sintaksis):** Memverifikasi keberadaan kolom, tipe data dasar (*primitive types*), panjang array, dan format representasi (misalnya: nullability, string formats, regex validation).
2. **Semantic Validation (Logika Bisnis):** Memverifikasi batasan invarian data dunia nyata, korelasi antar-fitur (*cross-column invariants*), dan hukum domain bisnis (misalnya: `umur >= 18`, `tanggal_transaksi <= waktu_sekarang`, `pendapatan_tahunan > pinjaman_bulanan * 12`).
3. **Distributional Validation (Integritas Statistik):** Memverifikasi stabilitas properti statistik data terhadap *baseline* historis (misalnya: rasio nilai nol (*null-rate*), rata-rata (*mean*), varians, entropi kategori, serta metrik divergensi seperti *Population Stability Index* (PSI) atau *Wasserstein Distance*).

**Mental Model: The "Quality Gate" as an Air-Lock**
Bayangkan sebuah fasilitas pengujian partikel steril. Data mentah adalah udara luar yang berpotensi terkontaminasi. *Quality Gate* bertindak sebagai ruang isolasi (*air-lock*). 

Data yang tiba tidak boleh langsung menyentuh *Feature Store* atau *Training Engine*. Data harus melewati serangkaian pengujian terisolasi. Jika lulus seluruh kriteria evaluasi (skema, semantik, distribusi), gerbang terbuka (*green lane*). Jika gagal, katup tertutup, data dialihkan ke *Dead-Letter Queue* (*red lane*), dan insinyur MLOps menerima peringatan telemetri secara terotomatisasi.

---

### 3. Why It Matters

Kegagalan data dalam sistem ML enterprise memiliki implikasi kritis:

1. **Silent Model Degradation:**
   Model tidak akan melempar *exception* jika sebuah fitur bernilai `NaN` yang kemudian terisi angka `0` akibat proses imputasi default yang tidak terkontrol. Namun, model *credit scoring* dapat tiba-tiba menolak jutaan nasabah yang memenuhi syarat atau menyetujui pinjaman berisiko tinggi.
2. **Training-Serving Skew:**
   Inkonsistensi antara pipeline ekstraksi data *offline* (training) dan pipeline inferensi *online* (serving) dapat menciptakan bias latensi dan fitur yang merusak akurasi prediksi real-time.
3. **Cascading Pipeline Contamination:**
   Jika data kotor masuk ke dalam *Feature Store*, seluruh model turunan yang mengonsumsi *feature group* tersebut akan terdistorsi. Biaya komputasi untuk melakukan pembersihan data retroaktif dan *retraining* massal berkali-kali lipat lebih besar dibanding validasi preventif di tepi ingestion (*edge of ingestion*).
4. **Kepatuhan Regulasi & Auditabilitas (Governance):**
   Regulasi ketat seperti Basel III/IV (perbankan) atau FDA SaMD (kesehatan) mewajibkan bukti deterministik bahwa model hanya dilatih dan dieksekusi menggunakan data yang lolos uji verifikasi integritas yang tercatat secara kriptografis atau terikat versi (*version-pinned*).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan end-to-end arsitektur pipeline validasi data kontinu yang menerapkan gerbang kualitas (*quality gates*), karantina data, dan pelaporan observabilitas.

```
+-----------------------------------------------------------------------------------------------+
|                                    DATA VALIDATION PIPELINE                                    |
+-----------------------------------------------------------------------------------------------+

 [ Data Sources ]
  - Batch S3/GCS
  - Stream Kafka
         |
         v
+-----------------------+
|  Ingestion Worker     | <--- Mengonsumsi Batch / Micro-batch
+-----------------------+
         |
         | Raw DataFrame
         v
+-----------------------------------------------------------------------------------------------+
| QUALITY GATE ENGINE                                                                           |
|                                                                                               |
|  +---------------------+      +---------------------+      +-------------------------------+  |
|  | Layer 1: Structural | ---> | Layer 2: Semantic   | ---> | Layer 3: Distributional Check |  |
|  | (Types, Nulls, Regex)|      | (Invariants, Bounds)|      | (PSI, Drift against Baseline) |  |
|  +---------------------+      +---------------------+      +-------------------------------+  |
+-----------------------------------------------------------------------------------------------+
         |                                           |
         | Pass All Checks                           | Violations Found (Breached Threshold)
         v                                           v
+-------------------------------+           +---------------------------------------------------+
| PROMOTED DATASET              |           | DEAD-LETTER QUEUE (DLQ) / QUARANTINE              |
|                               |           |                                                   |
| - Write to Feature Store      |           | - Write raw payload + Violation Metadata to S3/GCS|
| - Trigger Training Pipeline   |           | - Log validation report JSON                      |
| - Update Baseline Profile     |           | - Publish Alert (Slack/PagerDuty/Prometheus)      |
+-------------------------------+           +---------------------------------------------------+
         |                                           |
         v                                           v
[ Downstream ML Model / Prod ]              [ Incident Management & Remediation Engine ]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Data Contract
*Data Contract* adalah perjanjian formal antara penyedia data (*data producers*) dan konsumen data (*ML engineers/consumers*) yang menetapkan:
* **Schema Contract:** Nama kolom, representasi fisik (e.g., `Float64`), dan predikat nullabilitas.
* **Semantic Contract:** Invarian batas minimum, maksimum, keunikan, serta ekspresi relasional antar-kolom.
* **Service Level Objectives (SLO) Kualitas:** Persentase kelonggaran anomali (misal: *toleransi error < 0.01%* untuk data non-kritis, *0%* untuk data target/label).

#### B. Uji Statistik Distribusi pada Quality Gate
Selain memvalidasi batas statis, data numerik kontinu harus diuji terhadap pergeseran distribusi menggunakan metrik statistik:

1. **Population Stability Index (PSI):**
   Digunakan untuk mengukur seberapa jauh distribusi variabel aktual ($A$) telah bergeser dari distribusi dasar/referensi ($B$). Rentang dibagi menjadi $k$ bin:
   $$PSI = \sum_{i=1}^{k} \left( P(A_i) - P(B_i) \right) \times \ln\left(\frac{P(A_i)}{P(B_i)}\right)$$
   * Interpretasi Standar Industri:
     * $PSI < 0.1$: Tidak ada perubahan signifikan (*Pass*).
     * $0.1 \le PSI < 0.25$: Terjadi pergeseran moderat (*Warning Gate*).
     * $PSI \ge 0.25$: Terjadi pergeseran distribusi masif (*Fail Gate / Hard Stop Retraining*).

2. **Wasserstein Distance (Earth Mover's Distance):**
   Mengukur usaha minimal yang diperlukan untuk mentransformasikan distribusi peluang satu ke distribusi lainnya:
   $$l_1(u, v) = \int_{-\infty}^{+\infty} |U(x) - V(x)| dx$$
   Metrik ini sensitif terhadap pergeseran skala dan bentuk, efektif untuk data kontinu bervolume tinggi.

#### C. Isolasi Kegagalan (Quarantine Pattern)
Alih-alih membiarkan seluruh batch gagal dan memicu downtime pada layanan end-to-end, sistem menggunakan arsitektur pemisahan:
* Data row-level yang valid dipisahkan dan diproses jika skenario memungkinkan (*lenient routing*).
* Untuk pipeline model retraining terawasi (*supervised*), kegagalan pada ambang batas batch (*batch-level breach*) memicu penghentian total (*circuit breaker pattern*). Seluruh batch dialihkan ke bucket karantina terenkripsi bersama dengan *execution telemetry metadata* (kode kesalahan, nilai aktual, aturan yang dilanggar).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem validasi data end-to-end berbasis Python dengan clean architecture, *type-hints* ketat, menggunakan pustaka `pandera` dan `scipy` untuk inferensi statistik.

#### Struktur Modul
* `contracts.py`: Definisi skema dan aturan data.
* `evaluator.py`: Engine penilai statistik distribusi (PSI).
* `quality_gate.py`: Orkestrator eksekusi validasi dan penanganan *fail-fast/DLQ*.

```python
# contracts.py
from typing import Optional
import pandera.polars as pa
import polars as pl
from pydantic import BaseModel, Field


class TransactionValidationContract(pa.DataFrameModel):
    """
    Data Contract untuk transaksi finansial yang akan dikonsumsi oleh model Fraud Detection.
    Menggunakan Polars engine untuk performa pemrosesan paralel throughput tinggi.
    """
    transaction_id: str = pa.Field(unique=True, nullable=False, regex=r"^TXN-[0-9]{8}-[A-Z0-9]{4}$")
    user_id: str = pa.Field(nullable=False)
    amount: float = pa.Field(ge=0.01, le=500000.0, nullable=False)
    user_age: int = pa.Field(ge=18, le=120, nullable=False)
    risk_score: float = pa.Field(ge=0.0, le=1.0, nullable=False)
    is_fraud_label: Optional[int] = pa.Field(isin=[0, 1], nullable=True)

    class Config:
        strict = True  # Menolak kolom tambahan di luar spesifikasi kontrak
        coerce = False  # Menolak implicit type coercion untuk menjamin determinisme tipe data
```

```python
# evaluator.py
import numpy as np
import polars as pl


class StatisticalDriftEvaluator:
    """
    Evaluator statistik untuk mengukur divergensi distribusi fitur numerik.
    """

    @staticmethod
    def calculate_psi(
        baseline: np.ndarray,
        target: np.ndarray,
        num_bins: int = 10,
        epsilon: float = 1e-4
    ) -> float:
        """
        Menghitung Population Stability Index (PSI) antara dua sample distribusi.
        
        Args:
            baseline: Array 1D distribusi baseline (historis/referensi).
            target: Array 1D distribusi target (data baru).
            num_bins: Jumlah bin partisi.
            epsilon: Nilai smoothing konstan untuk menghindari pembagian dengan nol.
        
        Returns:
            Nilai PSI (float).
        """
        if len(baseline) == 0 or len(target) == 0:
            raise ValueError("Array input tidak boleh kosong.")

        # Tentukan batas quantile dari data baseline
        quantiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        # Hitung frekuensi pada tiap bin
        baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
        target_counts, _ = np.histogram(target, bins=bin_edges)

        # Normalisasi ke proporsi probabilitas
        baseline_pct = baseline_counts / len(baseline)
        target_pct = target_counts / len(target)

        # Lapisan proteksi nilai 0 dengan epsilon
        baseline_pct = np.where(baseline_pct == 0, epsilon, baseline_pct)
        target_pct = np.where(target_pct == 0, epsilon, target_pct)

        # Hitung PSI
        psi_value = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
        return float(psi_value)
```

```python
# quality_gate.py
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandera.errors
import polars as pl
from contracts import TransactionValidationContract
from evaluator import StatisticalDriftEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QualityGateOrchestrator")


class QualityGateBreachException(Exception):
    """Exception khusus yang dilempar saat Quality Gate mendeteksi pelanggaran kritis."""
    pass


class QualityGateReport:
    def __init__(self) -> None:
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.is_passed: bool = False
        self.structural_errors: List[Dict[str, Any]] = []
        self.drift_metrics: Dict[str, float] = {}

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp,
            "passed": self.is_passed,
            "structural_errors": self.structural_errors,
            "drift_metrics": self.drift_metrics
        }, indent=2)


class PipelineQualityGate:
    """
    Komponen orkestrator yang mengeksekusi kontraktual validasi data,
    evaluasi metrik drift, pemisahan DLQ, dan penegakan quality gate.
    """

    def __init__(
        self,
        quarantine_dir: Path,
        psi_threshold: float = 0.20
    ) -> None:
        self.quarantine_dir = quarantine_dir
        self.psi_threshold = psi_threshold
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _route_to_quarantine(self, df: pl.DataFrame, report: QualityGateReport) -> None:
        """Menyimpan data terkontaminasi beserta manifes kesalahan ke DLQ."""
        trace_id = f"quarantine_{int(datetime.now(timezone.utc).timestamp())}"
        data_path = self.quarantine_dir / f"{trace_id}_payload.parquet"
        manifest_path = self.quarantine_dir / f"{trace_id}_manifest.json"

        df.write_parquet(data_path)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        logger.error(f"DATA ISOLATED: Payload dialihkan ke DLQ di {data_path}")

    def execute_gate(
        self,
        incoming_data: pl.DataFrame,
        baseline_data: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Mengeksekusi pipeline pengecekan data. Melempar QualityGateBreachException
        apabila syarat kualitas tidak terpenuhi secara deterministik.
        """
        report = QualityGateReport()
        logger.info(f"Memulai evaluasi data batch. Total baris: {incoming_data.height}")

        # Langkah 1: Validasi Sintaksis & Semantik Struktural via Pandera
        try:
            validated_df = TransactionValidationContract.validate(incoming_data)
        except pandera.errors.SchemaErrors as err:
            logger.error("Pelanggaran Structural & Semantic Contract terdeteksi.")
            for failure in err.failure_cases.to_dicts():
                report.structural_errors.append(failure)
            report.is_passed = False
            self._route_to_quarantine(incoming_data, report)
            raise QualityGateBreachException(
                f"Quality Gate Ditolak: Ditemukan {len(report.structural_errors)} anomali struktural."
            ) from err

        # Langkah 2: Evaluasi Distribusi Fitur Numerik Kritis
        features_to_check = ["amount", "risk_score"]
        drift_failed = False

        for feature in features_to_check:
            base_values = baseline_data.get_column(feature).to_numpy()
            curr_values = validated_df.get_column(feature).to_numpy()

            psi_score = StatisticalDriftEvaluator.calculate_psi(base_values, curr_values)
            report.drift_metrics[f"{feature}_psi"] = psi_score
            logger.info(f"Metrik Drift [{feature}] - Nilai PSI: {psi_score:.4f}")

            if psi_score >= self.psi_threshold:
                drift_failed = True
                logger.warning(
                    f"Drift breach terdeteksi pada fitur '{feature}'! "
                    f"PSI {psi_score:.4f} melampaui batas {self.psi_threshold}"
                )

        if drift_failed:
            report.is_passed = False
            self._route_to_quarantine(validated_df, report)
            raise QualityGateBreachException(
                "Quality Gate Ditolak: Terjadi divergensi distribusi data (Data Drift Breach)."
            )

        report.is_passed = True
        logger.info("Quality Gate Berhasil Divalidasi: Seluruh invarian lolos verifikasi.")
        return validated_df
```

```python
# main.py (Simulasi Pengujian Pipeline)
from pathlib import Path
import numpy as np
import polars as pl
from quality_gate import PipelineQualityGate, QualityGateBreachException

def generate_mock_baseline(n_samples: int = 1000) -> pl.DataFrame:
    np.random.seed(42)
    return pl.DataFrame({
        "transaction_id": [f"TXN-20231010-{i:04d}" for i in range(n_samples)],
        "user_id": [f"USR-{i}" for i in range(n_samples)],
        "amount": np.random.exponential(scale=50.0, size=n_samples) + 1.0,
        "user_age": np.random.randint(18, 70, size=n_samples),
        "risk_score": np.random.beta(a=2, b=5, size=n_samples),
        "is_fraud_label": np.random.choice([0, 1], size=n_samples, p=[0.98, 0.02])
    })

def generate_mock_incoming_corrupted(n_samples: int = 500) -> pl.DataFrame:
    """Mensimulasikan data baru yang membawa pelanggaran skema semantik."""
    df = generate_mock_baseline(n_samples)
    # Suntikkan anomali: umur di bawah batas legal dan ID tidak cocok format regex
    return df.with_columns([
        pl.when(pl.col("user_age") < 25)
          .then(pl.lit(15)) # Pelanggaran batas usia
          .otherwise(pl.col("user_age"))
          .alias("user_age"),
        pl.lit("INVALID_TXN_FORMAT").alias("transaction_id") # Pelanggaran format regex
    ])

if __name__ == "__main__":
    quarantine_path = Path("./quarantine_dlq")
    gate = PipelineQualityGate(quarantine_dir=quarantine_path, psi_threshold=0.20)

    baseline_data = generate_mock_baseline(2000)
    corrupted_data = generate_mock_incoming_corrupted(500)

    logger.info("Mengeksekusi pengujian dengan data korup...")
    try:
        gate.execute_gate(incoming_data=corrupted_data, baseline_data=baseline_data)
    except QualityGateBreachException as e:
        logger.error(f"Sinyal Interupsi Diterima: {e}")
        logger.info("Pipeline Training dihentikan secara aman (Fail-Fast).")
```

---

### 7. Edge Cases & Failure Modes

1. **Cold Start Problem pada Distribusi Baru:**
   * *Problem:* Saat menginisialisasi fitur baru yang belum memiliki riwayat statistik, komputasi metrik komparatif seperti PSI atau KS-Test akan gagal karena tidak tersedianya data baseline.
   * *Mitigasi:* Terapkan aturan *Bootstrapping Validation Stage*. Data baseline harus dialokasikan secara eksplisit dari partisi *historical holdout* sebelum gate distribusi diaktifkan, atau tetapkan mode *Warm-up* di mana hanya validasi struktural/semantik yang dieksekusi secara ketat.
2. **Small Batch Inaccuracy (Ukuran Sampel Terlalu Kecil):**
   * *Problem:* Pengujian statistik non-parametrik (seperti PSI dan Chi-Square) mengalami bias ekstrem ketika dieksekusi pada ukuran batch mikro (misal: $N < 100$). Anomali palsu (*false positives*) sering terjadi.
   * *Mitigasi:* Konfigurasikan *Dynamic Test Decoupling*: jika ukuran batch $< N_{min}$, lewatkan uji statistik distribusi individual dan alihkan data ke dalam buffer agregasi geser (*sliding window accumulator*) sebelum uji pergeseran distribusi dilakukan.
3. **High-Cardinality Categorical Drift:**
   * *Problem:* Munculnya kategori baru pada level inferensi (*unseen categories*) yang tidak ada saat training.
   * *Mitigasi:* Skema *Data Contract* wajib mendeklarasikan perlakuan invarian kategori: apakah sistem mengizinkan token `<UNKNOWN>` secara default atau mewajibkan penolakan keras (*hard rejection*) via filter `isin` pada skema.
4. **Extreme Multicollinearity Breakdown:**
   * *Problem:* Fitur-fitur individu tetap berada dalam rentang minimum dan maksimum yang valid, tetapi korelasi multivariat antar-fitur berubah secara liar (contoh: pendapatan $100.000/bulan dengan riwayat pengangguran).
   * *Mitigasi:* Implementasikan validasi fungsional multi-kolom (*Cross-Column Invariants*) menggunakan kalkulasi *Mahalanobis Distance* atau batasan ekspresi predikatif eksplisit.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | In-Line DataFrame Validation (e.g., Pandera) | Framework Eksternal Skala Besar (e.g., Great Expectations) | Schema Registry Terdistribusi (e.g., Protobuf / Deequ) |
| :--- | :--- | :--- | :--- |
| **Latensi Eksekusi** | **Sangat Rendah (Mikro/Milidetik):** Berjalan secara *in-memory* langsung pada Polars/Pandas structures. Cocok untuk serving & batch mikro. | **Sedang ke Tinggi:** Memiliki overhead orkestrasi internal, profiling JSON, dan pembentukan metadata suite yang berat. | **Sangat Rendah (Layer Jaringan):** Validasi biner pada tingkat serialisasi data streams (Kafka/gRPC). |
| **Beban Infrastruktur** | **Nol:** Menyatu (*embedded*) langsung di dalam runtime container kode pipeline ML Anda. | **Tinggi:** Seringkali membutuhkan backend database untuk penyimpanan data docs dan metrik checkpoint. | **Tinggi:** Membutuhkan cluster Spark (AWS Deequ) atau ekosistem Schema Registry mandiri. |
| **Skalabilitas Data** | Dibatasi memori lokal satu node (dapat dimitigasi dengan arsitektur Polars Streaming/Arrow chunks). | Skalabel ke platform terdistribusi (Spark, SQL engines) tetapi lambat pada data batch kecil. | Sangat terdistribusi, efisien untuk throughput petabyte dalam skala data streaming. |
| **Kemudahan Authoring** | **Sangat Tinggi:** Didefinisikan menggunakan Python native dataclass/Pydantic style syntax. | **Menengah:** Berbasis declarative JSON suites atau fluent Python API yang verbose. | **Rendah:** Membutuhkan definisi IDL biner kaku (*Strict schema evolution rules*). |

---

### 9. Best Practices & Standar Industri

1. **Shift-Left Data Validation:**
   Validasi data wajib diterapkan sedekat mungkin dengan sumbernya (*Data Producer*). Jangan menunggu data mencapai tahap rekayasa fitur (*feature engineering*) untuk mengevaluasi tipe data dan anomali rentang nilai.
2. **Deklarasi Eksplisit Larangan Implicit Type Coercion:**
   Matikan konversi tipe implisit (seperti string `"123"` menjadi integer `123`). Bias imputasi yang tidak terdeteksi sering kali berakar dari *parser engine* yang terlalu permisif.
3. **Data Contract Versioning:**
   Gunakan Semantic Versioning (`vMAJOR.MINOR.PATCH`) untuk skema data validasi:
   * *PATCH:* Perubahan komentar atau modifikasi batas toleransi non-kritis.
   * *MINOR:* Penambahan fitur opsional (nullable fields).
   * *MAJOR:* Penghapusan kolom, perubahan tipe data, atau pengetatan batasan invarian yang menyebabkan *breaking changes*.
4. **Metrik Observabilitas Terintegrasi:**
   Setiap hasil eksekusi *Quality Gate* wajib memancarkan metrik ke platform telemetri sistem (misalnya: Prometheus, Datadog):
   * `data_quality_gate_passed{pipeline="fraud_model"} 1`
   * `data_quality_violations_total{column="user_age"} 42`
   * `data_distribution_psi{feature="amount"} 0.28`

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah MLOps Engineer di platform pinjaman digital (*fintech lending*). Tim data engineering sering mengirimkan batch transaksi harian yang mengandung inkonsistensi skema dan pergeseran distribusi akibat perubahan API pada aplikasi seluler. Tugas Anda adalah memvalidasi data menggunakan pipeline otomatis, memverifikasi kegagalan, dan memastikan data korup terisolasi di karantina.

#### Langkah 1: Persiapan Lingkungan
Buat file `requirements.txt` dan instal dependensi yang diperlukan:
```bash
pip install polars==0.20.15 pandera[polars]==0.18.0 numpy==1.26.4
```

#### Langkah 2: Eksekusi Kode Validasi
Simpan implementasi kelas `TransactionValidationContract`, `StatisticalDriftEvaluator`, dan `PipelineQualityGate` dari **Bagian 6** ke dalam file kerja Anda:
* `contracts.py`
* `evaluator.py`
* `quality_gate.py`

#### Langkah 3: Mensimulasikan Skenario Data Lolos (*Pass Scenario*)
Buat skrip `run_test_pass.py`:
```python
# run_test_pass.py
from pathlib import Path
import polars as pl
import numpy as np
from quality_gate import PipelineQualityGate

quarantine_path = Path("./quarantine_dlq")
gate = PipelineQualityGate(quarantine_dir=quarantine_path, psi_threshold=0.20)

np.random.seed(100)
# Distribusi identik
baseline_df = pl.DataFrame({
    "transaction_id": [f"TXN-20231010-{i:04d}" for i in range(1000)],
    "user_id": [f"USR-{i}" for i in range(1000)],
    "amount": np.random.exponential(scale=50.0, size=1000) + 1.0,
    "user_age": np.random.randint(18, 70, size=1000),
    "risk_score": np.random.beta(a=2, b=5, size=1000),
    "is_fraud_label": np.random.choice([0, 1], size=1000, p=[0.98, 0.02])
})

incoming_df = pl.DataFrame({
    "transaction_id": [f"TXN-20231011-{i:04d}" for i in range(1000)],
    "user_id": [f"USR-{i}" for i in range(1000)],
    "amount": np.random.exponential(scale=51.0, size=1000) + 1.0, # Perubahan minor yang dapat diterima
    "user_age": np.random.randint(18, 70, size=1000),
    "risk_score": np.random.beta(a=2.02, b=5.01, size=1000),
    "is_fraud_label": np.random.choice([0, 1], size=1000, p=[0.98, 0.02])
})

print("Menjalankan Pengujian Data Sehat...")
promoted_data = gate.execute_gate(incoming_data=incoming_df, baseline_data=baseline_df)
print(f"SUKSES: {promoted_data.height} baris dipromosikan ke feature store.")
```

Jalankan skrip:
```bash
python run_test_pass.py
```
*Output yang Diharapkan:*
```text
[INFO] Memulai evaluasi data batch. Total baris: 1000
[INFO] Metrik Drift [amount] - Nilai PSI: 0.0142
[INFO] Metrik Drift [risk_score] - Nilai PSI: 0.0098
[INFO] Quality Gate Berhasil Divalidasi: Seluruh invarian lolos verifikasi.
SUKSES: 1000 baris dipromosikan ke feature store.
```

#### Langkah 4: Mensimulasikan Skenario Data Drift (*Failure Scenario*)
Buat skrip `run_test_drift.py` untuk menguji pergeseran drastis pada parameter distribusi pengeluaran (*amount*):
```python
# run_test_drift.py
from pathlib import Path
import polars as pl
import numpy as np
from quality_gate import PipelineQualityGate, QualityGateBreachException

quarantine_path = Path("./quarantine_dlq")
gate = PipelineQualityGate(quarantine_dir=quarantine_path, psi_threshold=0.20)

np.random.seed(100)
baseline_df = pl.DataFrame({
    "transaction_id": [f"TXN-20231010-{i:04d}" for i in range(1000)],
    "user_id": [f"USR-{i}" for i in range(1000)],
    "amount": np.random.exponential(scale=50.0, size=1000) + 1.0,
    "user_age": np.random.randint(18, 70, size=1000),
    "risk_score": np.random.beta(a=2, b=5, size=1000),
    "is_fraud_label": np.random.choice([0, 1], size=1000, p=[0.98, 0.02])
})

# Anomali: Skala pengeluaran tiba-tiba melambung secara masif (Distribusi bergeser jauh)
drifted_incoming_df = pl.DataFrame({
    "transaction_id": [f"TXN-20231012-{i:04d}" for i in range(1000)],
    "user_id": [f"USR-{i}" for i in range(1000)],
    "amount": np.random.exponential(scale=350.0, size=1000) + 50.0, # Massive Drift!
    "user_age": np.random.randint(18, 70, size=1000),
    "risk_score": np.random.beta(a=2, b=5, size=1000),
    "is_fraud_label": np.random.choice([0, 1], size=1000, p=[0.98, 0.02])
})

print("Menjalankan Pengujian Data dengan Anomali Distribusi...")
try:
    gate.execute_gate(incoming_data=drifted_incoming_df, baseline_data=baseline_df)
except QualityGateBreachException as e:
    print(f"GERBANG TERKUNCI: {e}")
```

Jalankan skrip:
```bash
python run_test_drift.py
```
*Output yang Diharapkan:*
```text
[INFO] Memulai evaluasi data batch. Total baris: 1000
[WARNING] Drift breach terdeteksi pada fitur 'amount'! PSI 1.2541 melampaui batas 0.2
[ERROR] DATA ISOLATED: Payload dialihkan ke DLQ di quarantine_dlq/quarantine_..._payload.parquet
GERBANG TERKUNCI: Quality Gate Ditolak: Terjadi divergensi distribusi data (Data Drift Breach).
```

#### Langkah 5: Verifikasi Hasil Karantina (DLQ Inspection)
Periksa folder `./quarantine_dlq` untuk memvalidasi bahwa artefak payload data dan manifes log kegagalan telah tersimpan dengan benar:
```bash
ls -la ./quarantine_dlq
cat ./quarantine_dlq/*_manifest.json
```
Anda akan melihat manifes JSON yang merinci secara tepat waktu kegagalan dan nilai PSI yang menyebabkan quality gate menghentikan jalannya pipeline pelatihan. Pipeline downstream tetap aman dari polusi data.