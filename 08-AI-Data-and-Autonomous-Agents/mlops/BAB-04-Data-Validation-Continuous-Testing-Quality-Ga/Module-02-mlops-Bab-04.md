# BAB 04: DATA VALIDATION, CONTINUOUS TESTING & QUALITY GATES
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Enterprise Data Contract** menggunakan spesifikasi formal (*schema-as-code* dan *semantic assertions*) untuk mencegah *silent data corruption*.
2. **Membangun Multi-Stage Quality Gates** di dalam *pipeline* CI/CD/CT (*Continuous Training*) menggunakan kombinasi Pandera, Great Expectations, dan Evidently AI.
3. **Mengotomatisasi Pengujian Distribusi Data & Deteksi Drift** berbasis kalkulasi statistik lanjutan (*Population Stability Index* / PSI, *Wasserstein Distance*, *Kolmogorov-Smirnov Test*, dan *Jensen-Shannon Divergence*).
4. **Mendesain Mekanisme Automated Circuit Breaker & Rollback** ketika data *batch* atau data *real-time* melanggar ambang batas SLA/SLO kualitas data di lingkungan produksi.
5. **Mengevaluasi Trade-off Kritis** antara latensi komputasi validasi data, cakupan pengujian (*coverage*), biaya infrastruktur (*compute cost*), dan risiko *false positive alert*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
* **Python Lanjutan**: Pemahaman mendalam tentang *type hinting*, *metaclasses*, *decorators*, dan *data structures* (Pandas, Polars, PyArrow).
* **Konsep Inti MLOps (Bab 01–03)**: Reproduksibilitas, pelacakan eksperimen, registri model (*Model Registry*), dan *feature store*.
* **Statistika Terapan**: Distribusi probabilitas, *hypothesis testing* ($p$-value, alpha level), uji non-parametrik, dan metrik dispersi data.
* **Infrastruktur & Kontainerisasi**: Docker, Kubernetes dasar, dan *pipeline tooling* (GitHub Actions, GitLab CI, atau Argo Workflows).

---

### 3. Concept & Internal Architecture

Dalam arsitektur ML produksi modern, kesalahan fatal paling sering terjadi bukan karena *runtime crash* pada kode aplikasi, melainkan karena degradasi senyap (*silent failure*) akibat data anomali atau pergeseran distribusi (*data/covariate drift*). Ketiadaan *Quality Gates* yang ketat menyebabkan model menghasilkan inferensi salah dengan tingkat *confidence* yang tampak meyakinkan.

```
+---------------------------------------------------------------------------------------------------+
|                                PRODUCTION QUALITY GATE ARCHITECTURE                               |
+---------------------------------------------------------------------------------------------------+
  [ Raw Data Sources ]
           |
           v
  +------------------+      Gate 1: Pre-Ingestion Contract
  | Schema Validator | ---> [FAIL] ---> Dead Letter Queue (DLQ) -> PagerDuty Alert
  +------------------+
           | [PASS]
           v
  +------------------+      Gate 2: Statistical & Semantic Gate
  | Semantic Tests   | ---> [FAIL] ---> Quarantine Data Lake -> Slack Notification
  +------------------+
           | [PASS]
           v
  +------------------+      Gate 3: Baseline Distribution Drift Gate
  | Drift Analyzer   | ---> [DRIFT DETECTED] ---> Trigger Retraining Pipeline / Human Review
  +------------------+
           | [NO CRITICAL DRIFT]
           v
  +------------------+      Gate 4: Model Behavioral & Invariant Testing
  | CT / CI Pipeline | ---> [FAIL] ---> Abort Model Registration -> Retain Current Production Model
  +------------------+
           | [PASS]
           v
  [ Model Registry / Production Canary ]
```

Arsitektur *Quality Gate* enterprise dibagi menjadi empat lapisan internal:

#### Lapisan 1: Pre-Ingestion Data Contract (Structural Validation)
Mengisolasi *upstream ingestion* dari *storage*. Lapisan ini memeriksa:
* **Tipe Data & Nullability**: Memastikan tipe primitif (misal: `Int64`, `Float32`, `Categorical`) dan aturan kolom yang tidak boleh kosong (*non-nullable*).
* **Batas Struktural**: Memvalidasi kelengkapan *schema* (tidak ada kolom yang hilang atau kolom tak terduga tanpa deklarasi eksplisit).

#### Lapisan 2: Ingestion & Semantic Assertions
Memvalidasi logika bisnis internal dari nilai yang dikandung oleh data:
* **Range & Bounds**: Memastikan variabel seperti persentase berada dalam interval $[0, 1]$, usia $> 0$, dsb.
* **Relational Integrity**: Memastikan *foreign key*, referensi antar fitur, atau ketergantungan relasional (misal: `start_date <= end_date`) terpenuhi secara konsisten.

#### Lapisan 3: Statistical Drift & Distribution Shift Engine
Mendeteksi apakah sifat statistik populasi baru berbeda secara signifikan dari populasi *baseline* (data latih atau data operasional sebelumnya):
* **Kolmogorov-Smirnov (KS) Test**: Uji non-parametrik dua sampel untuk fitur numerik kontinu guna mendeteksi perbedaan distribusi kumulatif.
* **Population Stability Index (PSI)**: Mengukur kestabilan populasi; nilai $\text{PSI} < 0.1$ (stabil), $0.1 \le \text{PSI} \le 0.2$ (pergeseran moderat), $\text{PSI} > 0.2$ (pergeseran masif, memicu retrain otomatis).
* **Jensen-Shannon (JS) Divergence & Wasserstein Distance**: Pengukuran metrik jarak antar-distribusi probabilitas untuk fitur kategorikal dan numerik berdimensi tinggi.

#### Lapisan 4: Pre-Deployment Behavioral & Invariant Gates
Sebelum artefak model dipromosikan ke tahap *canary* atau *production*:
* **Directional/Metamorphic Testing**: Verifikasi bahwa peningkatan fitur tertentu menghasilkan perubahan output model yang logis (misalnya: menaikkan *credit score* pemohon pinjaman tidak boleh menaikkan probabilitas *default*).
* **Fairness & Slice-based Testing**: Memastikan metrik model (misal: F1-Score, ECE / *Expected Calibration Error*) tidak anjlok pada irisan populasi kritis (*sub-population slices*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Ad-hoc Checks) | Pendekatan Enterprise Continuous Testing |
| :--- | :--- | :--- |
| **Pendeteksian Error** | Reaktif; diketahui setelah komplain pengguna atau performa bisnis merosot tajam. | Proaktif; diblokir di *pipeline gate* sebelum model/data menyentuh produksi. |
| **Spesifikasi Data** | Berupa dokumentasi teks atau asumsi implisit data scientist dalam Jupyter Notebook. | *Data Contract as Code*, dapat dieksekusi secara otomatis, dan di-*versioning* dengan Git. |
| **Pengujian Model** | Hanya mengukur metrik agregat global (misal: global Test Accuracy atau ROC-AUC). | Multi-dimensi: Invarian, irisan data mikro (*slicing*), stabilitas probabilistik, dan toleransi derau (*noise*). |
| **Tindakan Pasca-Gagal** | Investigasi manual, *downtime* tak terprediksi, pemulihan darurat tanpa batas waktu pasti. | *Circuit breaking* otomatis, *traffic rerouting* ke model *fallback*, isolasi data ke *quarantine bucket*. |

---

### 5. How (Workflow Detail)

Alur kerja operasional eksekusi Quality Gates di produksi adalah sebagai berikut:

```
[New Batch / Event Arrival]
           │
           ▼
[1. Parse Schema & Contract Validation (Pandera/Pydantic)]
           │
     ┌─────┴───────────────┐
  Schema Match?      Schema Broken?
     │                     │
   (Yes)                   ▼
     │            [Quarantine Batch + Log Telemetry + Exit Code 1]
     ▼
[2. Semantic & Logical Assertions (GX / Polars Checks)]
     │
     ┌─────┴───────────────┐
  Valid Semantics?   Broken Logic?
     │                     │
   (Yes)                   ▼
     │            [Dead-Letter Queue + PagerDuty Alert]
     ▼
[3. Distributional Drift Profiler (Evidently / PSI Calc)]
     │
     ┌─────┴───────────────┐
  PSI <= 0.2?        PSI > 0.2?
     │                     │
   (Yes)                   ▼
     │            [Flag for Human Audit / Trigger Continuous Training]
     ▼
[4. Model Shadow / Canary Evaluation (Invariant Testing)]
     │
     ┌─────┴───────────────┐
  Gates Passed?      Slice Degradation?
     │                     │
   (Yes)                   ▼
     │            [Block Deployment + Rollback Deployment Status]
     ▼
[5. Promote to Production Registry & Serving]
```

1. **Definisi Kontrak**: Tim Data Engineering dan Data Science menetapkan berkas spesifikasi skema dan distribusi target (disimpan dalam bentuk *contract definition file* di Git).
2. **Validasi Ingesti**: Data baru yang masuk diproses melalui *runtime parser*. Bila struktur kolom atau tipe data rusak, *batch* dialihkan ke *Dead Letter Queue* (DLQ), dan proses *pipeline* dihentikan secara deterministik (*Exit Code 1*).
3. **Analisis Semantik**: Memeriksa kelayakan nilai internal menggunakan assertions vectorized guna mempertahankan performa I/O tinggi.
4. **Analisis Drift Komparatif**: Data baru dikomparasi secara statistikal terhadap *Golden Baseline Dataset*. Perubahan signifikan pada fitur-fitur kritis (*critical features*) akan memicu jalur penanganan khusus (*conditional DAG branching*).
5. **Continuous Model Testing**: Sebelum model baru hasil retrain diizinkan melayani *traffic*, model diuji terhadap *stress-test suite* mencakup *minimum functionality tests*, *invariance tests*, dan *directional expectation tests*.
6. **Promosi Terbimbing**: Hanya artefak yang lulus 100% ambang batas pengujian yang mendapatkan label `Production-Ready` di *Model Registry*.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Otomotif Presisi Tinggi
Bayangkan sebuah pabrik perakitan mobil listrik kelas dunia:
* **Unit Kontrak Data (Laser Gauge)**: Sebelum lembaran baja masuk ke mesin pres, pemindai laser memeriksa ketebalan milimeter baja tersebut. Bila terlalu tebal atau tipis 0.1 mm saja, lempengan langsung ditolak sebelum merusak mesin cetak.
* **Uji Semantik (Chemical Purity Test)**: Menguji apakah komposisi kimia baterai lithium bebas dari kontaminan cair yang berpotensi menyebabkan kebakaran termal.
* **Uji Drift (Toleransi Keausan Mesin)**: Mengukur apakah getaran mesin perakitan mulai menyimpang dari kurva normal perakitan bulan lalu, mendeteksi kerusakan sebelum menghasilkan suku cadang cacat.
* **Model Behavioral Gate (Uji Tabrak & Sensor Otomatis)**: Mobil jadi dimasukkan ke simulator rintangan ekstrem untuk memastikan rem otomatis selalu aktif saat ada pejalan kaki dalam kondisi hujan lebat sebelum mobil dikirim ke konsumen.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Skema Deklaratif dengan Validasi Semantik Menggunakan Pandera

Contoh sederhana ini menunjukkan validasi *type-safety*, batas numerik (*numerical bounds*), dan uji hipotesis dasar menggunakan Pandera.

```python
import pandera as pa
from pandera.typing import Series
import pandas as pd


class CreditApplicationSchema(pa.DataFrameModel):
    applicant_id: Series[str] = pa.Field(
        unique=True, regex=r"^APP-\d{6}$", nullable=False
    )
    age: Series[int] = pa.Field(ge=18, le=75, nullable=False)
    annual_income: Series[float] = pa.Field(ge=0.0, nullable=False)
    debt_to_income_ratio: Series[float] = pa.Field(ge=0.0, le=1.0)
    loan_status: Series[str] = pa.Field(
        isin=["APPROVED", "REJECTED", "UNDER_REVIEW"]
    )

    @pa.check("annual_income", name="income_positive_check")
    def check_income_positive(cls, income: Series[float]) -> Series[bool]:
        return income > 0.0


# Contoh eksekusi
data_valid = pd.DataFrame(
    {
        "applicant_id": ["APP-100201", "APP-100202"],
        "age": [25, 42],
        "annual_income": [55000.0, 120000.0],
        "debt_to_income_ratio": [0.25, 0.40],
        "loan_status": ["APPROVED", "UNDER_REVIEW"],
    }
)

try:
    CreditApplicationSchema.validate(data_valid, lazy=True)
    print("✓ Skenario validasi skema dasar berhasil dieksekusi tanpa error.")
except pa.errors.SchemaErrors as exc:
    print(f"✗ Validasi Gagal:\n{exc.failure_cases}")
```

---

#### B. Practical Example: Production-Grade Quality Gate & Drift Circuit Breaker

Berikut adalah implementasi sistem *Continuous Testing Gate* siap pakai untuk pipeline CI/CD produksi. Mengintegrasikan validasi kontrak skema, kalkulasi metrik drift numerik menggunakan *Population Stability Index* (PSI), dan *Automated Deployment Gate Evaluator*.

```python
#!/usr/bin/env python3
"""
Enterprise MLOps Quality Gate Engine
Implementasi: Schema Enforcement, Semantic Assertions, Statistical Drift Gate.
"""

from typing import Dict, Any, Tuple
import sys
import json
import logging
import numpy as np
import pandas as pd
import pandera as pa
from pandera.typing import Series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("QualityGate")


# ----------------------------------------------------------------------
# 1. DATA CONTRACT SPECIFICATION
# ----------------------------------------------------------------------
class InferenceBatchContract(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(
        unique=True, regex=r"^TXN-[A-Z0-9]{8}$", nullable=False
    )
    transaction_amount: Series[float] = pa.Field(
        ge=0.01, le=1_000_000.0, nullable=False
    )
    user_risk_score: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
    channel_type: Series[str] = pa.Field(
        isin=["WEB", "MOBILE_APP", "POS", "API"], nullable=False
    )
    is_foreign_transaction: Series[int] = pa.Field(isin=[0, 1], nullable=False)

    class Config:
        strict = True  # Tolak jika ada kolom liar tak terdaftar
        coerce = False


# ----------------------------------------------------------------------
# 2. STATISTICAL ENGINE: VECTORIZED PSI IMPLEMENTATION
# ----------------------------------------------------------------------
def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    num_buckets: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """Menghitung Population Stability Index (PSI) antara dua distribusi kontinu.

    Formula: SUM((Actual_% - Expected_%) * ln(Actual_% / Expected_%))
    """
    if len(expected) == 0 or len(actual) == 0:
        raise ValueError("Sampel data tidak boleh kosong.")

    # Tentukan bin split berbasis data referensi (kuantil)
    percentiles = np.linspace(0, 100, num_buckets + 1)
    bins = np.percentile(expected, percentiles)
    bins[0] -= 1e-5
    bins[-1] += 1e-5

    # Hitung frekuensi observasi dalam tiap bin
    expected_counts, _ = np.histogram(expected, bins=bins)
    actual_counts, _ = np.histogram(actual, bins=bins)

    # Konversi ke proporsi persentase dengan Laplace Smoothing (epsilon)
    expected_pct = (expected_counts / len(expected)) + epsilon
    actual_pct = (actual_counts / len(actual)) + epsilon

    # Normalisasi ulang agar total integral probabilitas = 1
    expected_pct /= np.sum(expected_pct)
    actual_pct /= np.sum(actual_pct)

    # Kalkulasi nilai PSI
    psi_vector = (actual_pct - expected_pct) * np.log(
        actual_pct / expected_pct
    )
    return float(np.sum(psi_vector))


# ----------------------------------------------------------------------
# 3. PRODUCTION QUALITY GATE EVALUATOR
# ----------------------------------------------------------------------
class ProductionQualityGateEvaluator:

    def __init__(
        self,
        reference_data: pd.DataFrame,
        psi_threshold: float = 0.15,
        max_failure_rate: float = 0.01,
    ):
        self.ref_data = reference_data
        self.psi_threshold = psi_threshold
        self.max_failure_rate = max_failure_rate

    def evaluate_batch(
        self, batch_data: pd.DataFrame
    ) -> Tuple[bool, Dict[str, Any]]:
        report: Dict[str, Any] = {
            "batch_size": len(batch_data),
            "schema_check": {"passed": False, "failure_cases": None},
            "drift_check": {"passed": False, "psi_scores": {}},
            "decision": "REJECT",
        }

        # Gate 1: Kontrak Skema Struktural & Logis
        try:
            InferenceBatchContract.validate(batch_data, lazy=True)
            report["schema_check"]["passed"] = True
            logger.info("✓ Gate 1: Schema & Data Contracts Passed.")
        except pa.errors.SchemaErrors as exc:
            report["schema_check"]["passed"] = False
            report["schema_check"]["failure_cases"] = exc.failure_cases.to_dict(
                orient="records"
            )
            logger.error(
                f"✗ Gate 1 Failed: Schema violation count = {len(exc.failure_cases)}"
            )
            return False, report

        # Gate 2: Statistical Drift Gate (PSI) pada Fitur Kritis
        drift_passed = True
        critical_features = ["transaction_amount", "user_risk_score"]

        for col in critical_features:
            psi_val = calculate_psi(
                expected=self.ref_data[col].to_numpy(),
                actual=batch_data[col].to_numpy(),
            )
            report["drift_check"]["psi_scores"][col] = psi_val

            if psi_val > self.psi_threshold:
                drift_passed = False
                logger.warning(
                    f"⚠ Drift Detected pada '{col}': PSI={psi_val:.4f} > Limit={self.psi_threshold}"
                )
            else:
                logger.info(
                    f"✓ Fitur '{col}' stabil: PSI={psi_val:.4f} <= Limit={self.psi_threshold}"
                )

        report["drift_check"]["passed"] = drift_passed

        # Keputusan Akhir Circuit Breaker
        if report["schema_check"]["passed"] and report["drift_check"]["passed"]:
            report["decision"] = "PROMOTE_TO_SERVING"
            return True, report
        else:
            report["decision"] = "QUARANTINE_BATCH"
            return False, report


# ----------------------------------------------------------------------
# 4. RUNTIME EXECUTION & CI/CD ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    np.random.seed(42)

    # 1. Baseline Reference Dataset (Data training masa lalu)
    n_baseline = 10_000
    baseline_df = pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:08X}" for i in range(n_baseline)],
            "transaction_amount": np.random.exponential(
                scale=50.0, size=n_baseline
            )
            + 1.0,
            "user_risk_score": np.random.beta(a=2, b=5, size=n_baseline),
            "channel_type": np.random.choice(
                ["WEB", "MOBILE_APP", "POS", "API"], size=n_baseline
            ),
            "is_foreign_transaction": np.random.choice(
                [0, 1], p=[0.9, 0.1], size=n_baseline
            ),
        }
    )

    # 2. Production Batch Ingestion (Mengalami Covariate Drift pada 'user_risk_score')
    n_incoming = 2_000
    drifted_batch_df = pd.DataFrame(
        {
            "transaction_id": [
                f"TXN-{i+20000:08X}" for i in range(n_incoming)
            ],
            "transaction_amount": np.random.exponential(
                scale=52.0, size=n_incoming
            )
            + 1.0,
            # Distribusi bergeser dari Beta(2, 5) ke Beta(5, 2)
            "user_risk_score": np.random.beta(a=5, b=2, size=n_incoming),
            "channel_type": np.random.choice(
                ["WEB", "MOBILE_APP", "POS", "API"], size=n_incoming
            ),
            "is_foreign_transaction": np.random.choice(
                [0, 1], p=[0.85, 0.15], size=n_incoming
            ),
        }
    )

    evaluator = ProductionQualityGateEvaluator(
        reference_data=baseline_df, psi_threshold=0.15
    )

    logger.info("Memulai Evaluasi Quality Gate pada Production Inbound Batch...")
    is_passed, evaluation_report = evaluator.evaluate_batch(drifted_batch_df)

    # Dump JSON Report untuk konsumsi CI/CD Step Runner (e.g., GitHub Actions Artifact)
    with open("quality_gate_report.json", "w") as f:
        json.dump(evaluation_report, f, indent=2)

    logger.info(
        f"Evaluasi Selesai. Hasil Keputusan Final: {evaluation_report['decision']}"
    )

    if not is_passed:
        logger.error(
            "Quality Gate memblokir batch ini. Menghentikan pipeline (System Exit 1)."
        )
        sys.exit(1)
    else:
        logger.info("Batch disetujui untuk konsumsi model produksi.")
        sys.exit(0)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Silent Feature Drift pada Platform FinTech Fraud Detection
* **Skala Sistem**: Sistem melayani 65 juta transaksi per hari di 4 negara Asia Tenggara, memproses data transaksi *streaming* dengan target inferensi $P_{99} < 40\text{ ms}$.
* **Insiden**: Salah satu bank mitra mengubah format parsing *timezone* ISO pada *timestamp* transaksi saat melakukan migrasi infrastruktur internal mereka dari UTC+7 ke UTC+0. 
* **Dampak**: 
  * Fitur turunan bernama `hour_of_day` dan `transaction_velocity_1h` bergeser drastis (7 jam lebih cepat).
  * Model XGBoost yang melayani deteksi penipuan salah mengklasifikasikan transaksi sah tengah hari menjadi transaksi anomali dini hari.
  * *False Positive Rate* melonjak 340%, menyebabkan puluhan ribu kartu debit nasabah terblokir otomatis dalam hitungan 3 jam, menurunkan nilai transaksi sebesar $1.8 Juta USD.
* **Solusi Arsitektural Pasca-Insiden**:
  1. **Deployment Shift-Left Pre-Processing Gate**: Menambahkan kontraktualisasi data berbasis *schema-as-code* di tingkat gateway ingestion menggunakan pustaka Rust/PyArrow sebelum diteruskan ke Kafka.
  2. **Micro-Batch Drift Sentinel**: Menerapkan pengecekan berkala menggunakan windowed PSI tiap 15 menit terhadap parameter fitur turunan.
  3. **Automated Dynamic Traffic Degradation**: Apabila terjadi pelanggaran drift gate ($PSI > 0.2$ selama 2 interval berturut-turut), sistem otomatis memindahkan *traffic* inferensi ke *Rule-Based Heuristic Fallback Engine*, menjaga ketersediaan layanan sekaligus mencegah pemblokiran massal yang salah.

---

### 9. Trade-offs

```
              VALIDATION DEPTH (Comprehensive)
                        ▲
                        │  * Full Invariance & Drift Suites
                        │    (High Latency, High Cloud Cost)
                        │
                        │             * Recommended Production Balance
                        │               (Contract Checks + Windowed Streaming PSI)
                        │
                        │  * Lightweight Assertions
                        │    (Low Latency, Blind to Statistical Drift)
                        ▼
   LOW ◄─────────────────────────────────────────────► HIGH
                  EXECUTION VELOCITY / THROUGHPUT
```

| Dimensi | Opsi A: Deep Statistical & Exhaustive Validation | Opsi B: Lean Schema & Boundary Validation Only |
| :--- | :--- | :--- |
| **Compute & Cost** | Sangat Tinggi. Pengujian statistik distribusi (seperti Wasserstein Distance skala besar) memakan CPU & memori intensif. | Sangat Rendah. Pengecekan tipe dan rentang nilai (*range boundary*) memiliki kompleksitas $O(N)$ yang dapat divorteksikan dengan SIMD. |
| **Inference Latency Impact** | Mengurangi *throughput* inferensi *real-time*; hanya layak dijalankan secara *asynchronous* atau dalam mode *micro-batch*. | Dapat ditanam langsung secara *in-line* pada *hot-path* serving API dengan latensi sub-milidetik. |
| **Coverage Risk** | Rendah. Mampu menangkap *covariate shift* tak kasat mata meskipun skema data tampak normal. | Tinggi. Rawan terhadap *silent failure* ketika skema valid namun arti statistik atau semantik data telah bergeser total. |
| **Alert Fatigue** | Cenderung tinggi. Variasi musiman acak (*seasonality variance*) dapat memicu alarm drift palsu jika ambang batas statis (*hard threshold*). | Sangat rendah. Alarm hanya berbunyi jika terjadi pelanggaran struktural yang nyata (skema patah). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Drift Testing pada Fitur Non-Stasioner
* **Kesalahan**: Menjalankan tes Kolmogorov-Smirnov atau PSI pada fitur seperti `cumulative_user_spend` atau `total_transaction_count` yang nilainya secara alami bertambah seiring waktu.
* **Gejala**: Pipeline Continuous Training selalu terpicu (*infinite retrain loop*) atau CI/CD terus-menerus gagal akibat sinyal drift palsu.
* **Solusi**: Transformasikan variabel non-stasioner menjadi rasio, selisih (*differencing* $\Delta t$), atau *windowed aggregations* (misal: rata-rata pergeseran 7 hari) sebelum dimasukkan ke dalam Drift Gate.

#### 2. Blocking Production CI/CD Tanpa Memperhitungkan Ukuran Sampel ($N$)
* **Kesalahan**: Menggunakan uji $p$-value murni (misal: $p < 0.05$ pada uji KS) pada dataset berukuran sangat besar ($N > 500,000$).
* **Gejala**: Secara matematis, dengan ukuran sampel masif, deviasi yang sangat sepele dan tidak relevan secara praktis akan menghasilkan $p$-value mendekati 0, menyebabkan pengujian selalu gagal.
* **Solusi**: Gunakan pengukuran *Effect Size* atau *Distance-based metrics* (misalnya: PSI, Wasserstein Distance, atau Total Variation Distance) sebagai pengganti $p$-value murni untuk *gate-blocking criteria*.

#### 3. Mengabaikan Unknown Categorical Levels
* **Kesalahan**: Menguji fitur kategorikal hanya berdasarkan persentase distribusi tanpa membatasi perilaku saat level baru (*unseen categorical labels*) muncul di data produksi.
* **Gejala**: Skrip drift lolos, namun pipeline prediksi model mengalami *crash* saat menjalankan teknik *One-Hot Encoding* atau *Target Encoding*.
* **Solusi**: Terapkan penanganan ketat pada *schema contract*: tetapkan aturan *out-of-vocabulary* (OOV) token handling, atau blokir ingest menggunakan `pa.Field(isin=[...])` dengan opsi fallback yang jelas.

---

### 11. Best Practices (Production Checklist)

Gunakan tabel kepatuhan ini sebelum mengaktifkan gerbang otomatisasi ke produksi:

| Area | Item Pemeriksaan (*Checklist*) | Kategori | Frekuensi Evaluasi |
| :---: | :--- | :---: | :---: |
| **Inbound Gate** | Skema tipe data, nullability, dan format ID didefinisikan via *Data Contract as Code*. | Mandatori | Setiap Ingestion / Batch |
| **Inbound Gate** | Seluruh data yang melanggar kontrak dipisahkan ke *Dead-Letter-Queue* (DLQ) tanpa *pipeline crash*. | Mandatori | Real-Time |
| **Semantic Gate** | Aturan rentang fisis/ekonomis (misal: rasio hutang $\ge 0$, persentase $\le 100\%$) diverifikasi. | Mandatori | Setiap Ingestion / Batch |
| **Statistical Gate** | Ambang batas PSI disetel pada $\text{PSI} \le 0.1$ (stabil) dan $0.1 < \text{PSI} \le 0.2$ (peringatan). | Rekomendasi | Periodik / Windowed |
| **Statistical Gate** | Menghapus fitur berkorelasi tinggi dengan waktu (*time-dependent features*) dari drift suite absolut. | Mandatori | Saat Desain Model |
| **Pre-Deploy Gate** | Validasi invarian dan arah (*metamorphic test*) selesai dijalankan pada kandidat model retrain. | Mandatori | Setiap Build CI/CD |
| **Infrastructure** | Metrik pengujian data dialirkan ke sistem observabilitas terpusat (Prometheus/Datadog). | Rekomendasi | Real-Time |
| **Governance** | Setiap perubahan kontrak data melalui proses *Pull Request* dan *approval* lintas tim Data/ML. | Mandatori | Saat Rilis Skema |

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sistem *Continuous Quality Gate* modular yang siap dijalankan dalam container.

#### Struktur Direktori Hands-on (`hands-on/m02/`)
```
hands-on/m02/
├── contracts/
│   └── feature_contract.py
├── data/
│   ├── baseline_features.csv
│   └── incoming_stream.csv
├── gates/
│   ├── __init__.py
│   ├── drift_gate.py
│   └── schema_gate.py
├── run_quality_gates.py
└── requirements.txt
```

#### Langkah 1: Siapkan Dependencies
Tulis file `hands-on/m02/requirements.txt`:
```txt
pandas>=2.0.0
numpy>=1.24.0
pandera>=0.18.0
scipy>=1.10.0
```
Instalasi environment:
```bash
pip install -r hands-on/m02/requirements.txt
```

#### Langkah 2: Buat Skrip Kontrak Data
Tulis file `hands-on/m02/contracts/feature_contract.py`:
```python
import pandera as pa
from pandera.typing import Series


class CustomerChurnFeatures(pa.DataFrameModel):
    customer_id: Series[str] = pa.Field(unique=True, regex=r"^CUST-\d{5}$")
    tenure_months: Series[int] = pa.Field(ge=0, le=120)
    monthly_charges: Series[float] = pa.Field(ge=10.0, le=500.0)
    contract_type: Series[str] = pa.Field(
        isin=["MONTH_TO_MONTH", "ONE_YEAR", "TWO_YEAR"]
    )
    total_support_calls: Series[int] = pa.Field(ge=0, le=50)

    class Config:
        strict = True
        coerce = True
```

#### Langkah 3: Implementasikan Drift Engine
Tulis file `hands-on/m02/gates/drift_gate.py`:
```python
import numpy as np
from scipy.stats import ks_2samp


def evaluate_feature_drift(
    ref_col: np.ndarray, curr_col: np.ndarray, ks_alpha: float = 0.01
) -> dict:
    """Mengevaluasi perbedaan distribusi menggunakan Kolmogorov-Smirnov Test."""
    ks_stat, p_val = ks_2samp(ref_col, curr_col)
    return {
        "ks_statistic": float(ks_stat),
        "p_value": float(p_val),
        "drift_detected": bool(p_val < ks_alpha),
    }
```

#### Langkah 4: Bangun Pipeline Runner
Tulis file `hands-on/m02/run_quality_gates.py`:
```python
import sys
import pandas as pd
import numpy as np
from contracts.feature_contract import CustomerChurnFeatures
from gates.drift_gate import evaluate_feature_drift
import pandera as pa

# 1. Generate Synthetic Data
np.random.seed(1337)
n_samples = 1000

baseline_df = pd.DataFrame(
    {
        "customer_id": [f"CUST-{i:05d}" for i in range(n_samples)],
        "tenure_months": np.random.randint(1, 72, size=n_samples),
        "monthly_charges": np.random.normal(loc=70.0, scale=15.0, size=n_samples),
        "contract_type": np.random.choice(
            ["MONTH_TO_MONTH", "ONE_YEAR", "TWO_YEAR"], size=n_samples
        ),
        "total_support_calls": np.random.poisson(lam=2, size=n_samples),
    }
)

incoming_df = baseline_df.copy()
# Introduksi Drift: lonjakan biaya bulanan drastis
incoming_df["monthly_charges"] = np.random.normal(
    loc=120.0, scale=25.0, size=n_samples
)

# 2. Gate 1: Check Data Contracts
print("--- [GATE 1] Running Schema & Contract Gate ---")
try:
    CustomerChurnFeatures.validate(incoming_df)
    print("✓ Kontrak Valid.")
except pa.errors.SchemaError as e:
    print(f"✗ Gagal Kontrak: {e}")
    sys.exit(1)

# 3. Gate 2: Check Drift Gate
print("\n--- [GATE 2] Running Statistical Drift Gate ---")
drift_result = evaluate_feature_drift(
    baseline_df["monthly_charges"].values,
    incoming_df["monthly_charges"].values,
)
print(f"Hasil Evaluasi 'monthly_charges': {drift_result}")

if drift_result["drift_detected"]:
    print(
        "✗ CRITICAL WARNING: Distribusi bergeser secara signifikan! Memblokir pipeline."
    )
    sys.exit(2)
else:
    print("✓ Distribusi stabil.")
    sys.exit(0)
```

Jalankan pengujian:
```bash
python hands-on/m02/run_quality_gates.py
```
*Output yang diharapkan: Gate 1 berhasil, Gate 2 mendeteksi drift secara sukses dan mematikan eksekusi dengan status code 2.*

---

### 13. Exercise

#### Latihan 1 (Tingkat: Easy)
Perluas skema `CustomerChurnFeatures` di file `feature_contract.py` untuk menyertakan kolom baru: `internet_service` yang hanya boleh bernilai `"DSL"`, `"FIBER_OPTIC"`, atau `"NO"`. Tulis pengujian unit yang memastikan data dengan label `"CABLE"` memicu kegagalan skema.

#### Latihan 2 (Tingkat: Medium)
Modifikasi skrip `gates/drift_gate.py` agar tidak hanya mengembalikan uji KS, tetapi juga menghitung *Wasserstein Distance* (Earth Mover's Distance) dari modul `scipy.stats.wasserstein_distance`. Tetapkan ambang batas dinamis: jika nilai Wasserstein Distance melebihi 10% dari standar deviasi data referensi, tandai sebagai anomali distribusi.

#### Latihan 3 (Tingkat: Hard)
Rancang sebuah decorator Python `@quality_gate(contract_cls, drift_ref_df)` yang membungkus fungsi inferensi batch model. Jika data input masukan gagal pada validasi kontrak, fungsi tidak boleh menjalankan inferensi, melainkan langsung menyimpan payload kotor ke disk lokal (`quarantine/broken_data.parquet`) dan mengembalikan representasi error JSON terstruktur tanpa melempar unhandled exception.

---

### 14. Challenge

**Skenario Kasus**:
Anda adalah Principal MLOps Engineer di sebuah marketplace logistik global. Sistem Anda memproses ratusan juta data telemetri GPS armada dan waktu estimasi pengiriman (*Estimated Time of Arrival* / ETA). Tim Anda menghadapi dua tantangan besar:
1. **Temporal Non-Stationarity**: Variasi musiman harian (jam sibuk vs tengah malam) dan cuaca musiman menyebabkan distribusi kecepatan kendaraan bergeser drastis setiap beberapa jam, memicu ratusan alarm *false positive* pada drift detector konvensional Anda.
2. **Schema Ingestion Parity**: Data berasal dari puluhan vendor aplikasi kurir pihak ketiga yang sering kali menambahkan kolom arbitrer, mengubah format timestamp dari integer Unix Epoch ke string ISO-8601 tanpa pemberitahuan sebelumnya.

**Tugas Arsitektur**:
Rancang dokumen arsitektur dan rancangan komponen teknis (*high-level & low-level design*) untuk **Adaptive Context-Aware Quality Gate System**. Solusi Anda harus mampu:
* Membedakan secara cerdas antara *pergeseran konteks yang valid* (misal: badai musiman yang menurunkan kecepatan rata-rata di area tertentu) dengan *anomali data riil* (misal: sensor GPS malfungsi memancarkan kecepatan negatif atau lonjakan akibat degradasi aplikasi).
* Menerapkan validasi kontrak data dinamis dengan mekanisme resolusi otomatis (*dynamic schema adaptation / backward compatibility layers*).
* Menjelaskan mekanisme fail-safe: bagaimana sistem perutean melayani prediksi ETA saat gerbang mendeteksi anomali kritis pada 20% armada tanpa mematikan total operasional bisnis logistik.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara pemeriksaan data berbasis *Schema Validation* dan *Statistical Drift Detection*?
2. Mengapa *lazy evaluation* (`lazy=True`) pada Pandera sangat disarankan saat mengeksekusi validasi kontrak data di pipeline batch CI/CD?
3. Apa indikasi statistik apabila nilai *Population Stability Index* (PSI) berada di angka $0.25$?
4. Mengapa validasi data harus dijalankan sebelum data dimasukkan ke dalam *Feature Store*?
5. Sebutkan satu kekurangan fatal dari pengujian unit tradisional (*unit tests*) berbasis mock data jika diterapkan pada validasi machine learning!

#### B. Pertanyaan Intermediate
6. Bagaimana cara menangani fenomena di mana pengujian hipotesis dua sampel (seperti *Kolmogorov-Smirnov Test*) selalu menghasilkan $p\text{-value} \approx 0$ pada dataset berukuran puluhan juta baris?
7. Dalam konteks pengujian model, jelaskan apa yang dimaksud dengan *Metamorphic/Directional Testing* dan berikan satu contoh konkretnya pada model *pricing engine*!
8. Apa kelemahan utama metrik *Mean Squared Error* (MSE) global sehingga kita wajib menerapkan *Slice-based Testing* sebelum melakukan deployment model?
9. Jelaskan trade-off antara penggunaan *Strict Schema Contract* (`strict=True`, menolak semua kolom tak terdaftar) versus *Tolerant Contract* (`strict=False`) dalam arsitektur microservices berbasis ML!
10. Bagaimana arsitektur *Dead-Letter Queue* (DLQ) bekerja sama dengan Quality Gates untuk mempertahankan ketersediaan sistem tanpa kehilangan jejak transaksi yang rusak?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah pipeline Continuous Training (CT) otomatis Anda tiba-tiba mengalami *infinite retraining loop*: model baru dilatih, diuji, lulus, di-deploy, tetapi 30 menit kemudian Drift Gate memicu pipeline retraining kembali. Setelah diinvestigasi, tidak ada perubahan kode. Apa akar masalah arsitektural yang paling mungkin terjadi dan bagaimana cara memutus siklus tersebut?
12. **Skenario 2**: Anda memiliki model klasifikasi risiko medis yang memproses data citra dan tabular pasien. Pengujian akurasi agregat menunjukkan performa model 94%. Namun saat diterapkan di satu rumah sakit daerah terpencil, model gagal total dan menghasilkan diagnosis salah yang fatal. Di tahap Quality Gate mana kegagalan ini seharusnya dicegah, dan pengujian spesifik apa yang harus dipasang?
13. **Skenario 3**: Sistem streaming fraud detection Anda dituntut memproses 20.000 transaksi per detik dengan latensi maksimal 15 milidetik. Implementasi validasi drift berbasis kernel density estimation memperlambat inferensi menjadi 120 milidetik. Rancang arsitektur komputasi Quality Gate yang memungkinkan inferensi tetap di bawah batas 15 ms tanpa mengorbankan pengawasan drift!

---

### Kunci Jawaban & Solusi Quiz

#### Jawaban Basic
1. *Schema Validation* menguji struktur deterministik data (tipe data, format, batasan nilai fisis/nullability). *Statistical Drift Detection* menguji perubahan sifat stokastik atau sebaran kurva probabilitas data antar-waktu tanpa ada pelanggaran struktur skema.
2. `lazy=True` memungkinkan Pandera mengumpulkan seluruh kasus kegagalan pada seluruh kolom sekaligus dalam satu proses pemindaian (*full scan*), bukan berhenti pada kegagalan pertama (*fail-fast*), sehingga engineer mendapatkan laporan komprehensif mengenai seluruh anomali data.
3. Nilai $\text{PSI} > 0.20$ menandakan terjadinya pergeseran populasi yang signifikan (*significant distribution shift*), yang mengindikasikan bahwa data saat ini telah jauh berbeda dari data acuan, sehingga model berisiko tinggi mengalami penurunan performa.
4. Mencegah *data corruption* mengotori *offline* maupun *online storage*, yang dapat merusak kualitas fitur untuk proses inferensi real-time maupun pelatihan model di masa depan secara permanen.
5. Unit test tradisional hanya memvalidasi integritas logika instruksi baris kode (*code behavior*), bukan kualitas, integritas, ketergantungan statistik, maupun distribusi dari data yang diproses (*data behavior*).

#### Jawaban Intermediate
6. Karena peningkatan ukuran sampel ($N$) yang sangat masif membatasi deviasi standar kesalahan estimasi, sehingga uji signifikansi mendeteksi perbedaan terkecil sekalipun sebagai hal signifikan. Solusinya: beralih dari pengujian berbasis signifikansi $p$-value ke pengukuran berbasis *Effect Size* atau jarak metrik absolut (misal: Wasserstein-1 Distance, Cosine Distance, atau binned PSI).
7. *Metamorphic/Directional Testing* adalah pengujian perilaku model di mana kita memverifikasi perubahan arah output yang dipicu oleh perubahan terarah pada input. Contoh: Pada model *pricing engine*, jika parameter `distance_km` ditingkatkan sementara parameter lainnya tetap (*ceteris paribus*), maka output `predicted_price` harus selalu lebih besar atau sama, tidak boleh lebih rendah.
8. MSE global dapat menyamarkan performa buruk pada kelompok minoritas penting (misalnya: kelompok demografis kecil atau transaksi bernilai sangat tinggi). *Slice-based testing* memecah metrik ke dalam irisan segmen mikro untuk memastikan tidak ada degradasi lokal yang tertutup oleh rata-rata global yang tampak bagus.
9. *Strict Schema Contract* menjamin stabilitas dan keamanan model secara absolut dari input tak dikenal, tetapi rentan merusak *backward compatibility* saat tim upstream menambahkan fitur baru. *Tolerant Contract* fleksibel terhadap evolusi skema, tetapi membuka celah *silent corruption* jika ada kolom penting yang terlewat atau terjadi salah penamaan (*typo* pada nama field).
10. Data yang melanggar gerbang validasi tidak dilemparkan sebagai *unhandled exception* yang mematikan worker, melainkan dialihkan secara asinkron ke topik Kafka terpisah atau bucket S3 karantina (DLQ) bersama dengan metadata error JSON. Sistem terus memproses data yang valid, sementara data bermasalah di-inspeksi dan di-replay kemudian oleh tim operasional.

#### Jawaban Skenario Kasus Produksi
11. **Solusi Skenario 1**: Akar masalah adalah fenomena *Feedback Loop Bias* atau pergeseran target baseline statis: model baru yang dilatih mengubah perilaku pengguna atau prediksi yang disimpan kembali sebagai input data referensi, atau ambang batas drift membandingkan data produksi dengan data training generasi pertama alih-alih data training yang digunakan model saat ini. Solusi: Sesuaikan baseline drift secara dinamis ke dataset yang digunakan oleh model yang sedang aktif, dan terapkan mekanisme *cooldown period* serta batas maksimal retraining otomatis (misalnya: maksimal retrain 1 kali dalam 24 jam) sebelum mewajibkan supervisi manual (*human-in-the-loop gate*).
12. **Solusi Skenario 2**: Kegagalan ini seharusnya dicegah pada **Gate 4: Pre-Deployment Behavioral & Slice-based Testing**. Pengujian yang harus dipasang adalah *Subgroup Fairness & Invariant Slice Testing*. Data pengujian harus dipartisi berdasarkan metadata spesifik (lokasi demografis, tipe perangkat pemindai medis di daerah pelosok, dll). Model hanya boleh dideploy jika performa metrik (seperti *Sensitivity* atau *Recall*) pada irisan kelompok terburuk (*worst-performing slice*) berada di atas batas toleransi klinis minimum, bukan hanya mengandalkan rata-rata global 94%.
13. **Solusi Skenario 3**: Pisahkan jalur eksekusi inferensi (*synchronous hot-path*) dari jalur validasi drift (*asynchronous cold-path*). Pada hot-path (latensi $<15\text{ ms}$), jalankan hanya validasi skema ringan dan batas tipe data terkompilasi (misal via C++/Rust binding atau schema parser SIMD). Salurkan input dan prediksi secara asinkron ke antrian pesan (seperti Apache Kafka). Di latar belakang (*background workers*), kumpulkan data dalam bentuk *sliding micro-batch* (misal: per 10.000 transaksi atau per 1 menit) untuk menghitung statistik distribusi dan PSI. Jika drift terdeteksi di cold-path, sistem mengirimkan sinyal kendali (*control signal*) ke serving fleet untuk memperbarui status routing traffic secara dinamis.

---

### 16. Summary

Implementasi continuous testing dan quality gates tingkat lanjut merupakan fondasi utama keandalan sistem Machine Learning di skala enterprise:
* **Pergeseran Paradigma**: Kualitas sistem ML tidak ditentukan oleh tingginya metrik akurasi saat evaluasi eksperimental awal, melainkan oleh ketahanan (*resilience*) infrastruktur dalam mendeteksi dan menolak anomali data di sepanjang siklus hidup operasional.
* **Pendekatan Berlapis**: Quality Gates harus dirancang secara bertingkat: diawali dari pencegahan kesalahan struktural (*Data Contracts*), penegakan integritas logika (*Semantic Assertions*), pemantauan pergeseran sebaran (*Statistical Drift Gates*), hingga pengujian perilaku model (*Invariant & Slice Testing*).
* **Automasi Terkendali**: Penerapan *Continuous Training* dan *Continuous Deployment* wajib dilengkapi dengan mekanisme *Circuit Breakers* dan *Dead-Letter Queues*. Tindakan ini meminimalisir intervensi manual tanpa mengekspos sistem produksi ke risiko kegagalan berantai (*cascading failures*).