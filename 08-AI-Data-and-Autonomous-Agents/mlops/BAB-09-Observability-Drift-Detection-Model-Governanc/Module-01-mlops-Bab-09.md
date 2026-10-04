# Bab 09: Observability, Drift Detection, & Model Governance
## Module 01: Fondasi Observabilitas Sistem Machine Learning & Deteksi Drift

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Merancang Arsitektur Telemetri ML**: Membangun pipeline observabilitas decoupled yang menangkap data inferensi (fitur input, prediksi, metadata) tanpa menambah latensi pada *inference hot path*.
- **Menerapkan Pengujian Statistik Drift**: Mengimplementasikan algoritma Kolmogorov-Smirnov (KS-test), Population Stability Index (PSI), dan Wasserstein Distance untuk mendeteksi *Covariate Shift* dan *Prior Probability Shift*.
- **Mengatasi Delayed Ground Truth Problem**: Mengembangkan strategi evaluasi performa model di lingkungan produksi di mana label aktual (*ground truth*) memiliki latensi berhari-hari hingga berbulan-bulan.
- **Mengintegrasikan Metrik ML ke Prometheus/Grafana**: Mengekspos indikator *health* model secara real-time menggunakan format open standard OpenTelemetry dan Prometheus.
- **Membangun Model Governance & Audit Trail**: Menyusun artefak *Model Cards* terprogram dan mencatat garis keturunan data (*lineage tracking*) untuk kepatuhan regulasi (seperti EU AI Act dan standar perbankan).

---

### 2. Concept Overview

Sistem Machine Learning (ML) di lingkungan produksi memiliki karakteristik kegagalan yang berbeda secara fundamental dari rekayasa perangkat lunak tradisional. Perangkat lunak konvensional mengalami kegagalan deterministik: kode melempar *exception*, terjadi *deadlock*, atau *segfault* (kegagalan biner: *up* atau *down*). Sebaliknya, model ML mengalami **Silent Degradation**: API inferensi tetap merespons dengan HTTP status `200 OK` dan latensi rendah (<15ms), namun nilai prediksi yang dihasilkan secara ekonomi merugikan atau tidak lagi relevan akibat dinamika distribusi data dunia nyata.

```
+-----------------------------------------------------------------------------------+
|                            TAXONOMY OF ML FAILURES                                |
+-----------------------------------------------------------------------------------+
|  Software Engine Level (Traditional APM)  |     Statistical Level (ML Observability)      |
|  - Latency (p50, p95, p99)                |  - Data Drift (Covariate Shift): P(X) changes  |
|  - Error Rates (4xx, 5xx)                 |  - Concept Drift: P(Y|X) changes              |
|  - Resource Saturation (CPU, GPU, VRAM)   |  - Prior Shift: P(Y) changes                  |
|  - Throughput (RPS/QPS)                   |  - Pipeline Integrity: Schema violation       |
+-----------------------------------------------------------------------------------+
```

#### Paradigma Distribusi Probabilitas

Secara matematis, model prediktif terawasi (*supervised*) memodelkan probabilitas bersyarat $P(Y|X)$, di mana $X$ merepresentasikan fitur input dan $Y$ adalah target prediksi. Probabilitas bersama dinyatakan sebagai:

$$P(X, Y) = P(X) \cdot P(Y|X)$$

Dari formulasi ini, degradasi performa model dikategorikan ke dalam tiga tipe drift:

1. **Data Drift (Covariate Shift)**: 
   Terjadi perubahan pada distribusi marjinal input $P(X)$, sementara hubungan bersyarat $P(Y|X)$ tetap konstan.
   $$P_{t_0}(X) \neq P_{t_1}(X) \quad \text{dan} \quad P_{t_0}(Y|X) = P_{t_1}(Y|X)$$
   *Contoh*: Pergeseran demografi pengguna aplikasi dari rentang usia 20-30 tahun menjadi 45-60 tahun, namun perilaku risiko kredit untuk masing-masing kelompok umur tetap sama.

2. **Concept Drift**: 
   Terjadi perubahan pada hubungan bersyarat antara input dan target $P(Y|X)$, terlepas dari apakah $P(X)$ berubah atau tidak.
   $$P_{t_0}(Y|X) \neq P_{t_1}(Y|X)$$
   *Contoh*: Munculnya pola penipuan (*fraud*) baru di platform e-commerce yang secara sengaja mereplikasi atribut transaksi pengguna legal. Nilai input tampak normal, namun label $Y$ telah bergeser.

3. **Prior Probability Shift (Label Shift)**: 
   Terjadi perubahan pada distribusi marjinal target $P(Y)$, sementara distribusi fitur bersyarat $P(X|Y)$ tetap stabil.
   $$P_{t_0}(Y) \neq P_{t_1}(Y) \quad \text{dan} \quad P_{t_0}(X|Y) = P_{t_1}(X|Y)$$
   *Contoh*: Lonjakan persentase kasus gagal bayar pinjaman selama krisis ekonomi global, meskipun karakteristik bawaan nasabah yang gagal bayar tidak berubah.

---

### 3. Why It Matters

Di tingkat enterprise, ketiadaan ML Observability berdampak langsung pada metrik finansial, reputasi hukum, dan operasional:

1. **Finansial (Undetected Silent Failure)**:
   Pada sistem credit scoring institusi finansial, kenaikan suku bunga acuan bank sentral dapat menggeser profil risiko debitur. Model yang tidak dimonitor akan terus menyetujui pinjaman berisiko tinggi. Karena masa jatuh tempo kredit memakan waktu 6–12 bulan (*delayed feedback*), kerugian portofolio terakumulasi sebelum tim menyadari kegagalan model.

2. **Compliance & Regulasi Global**:
   Regulasi seperti *EU AI Act (High-Risk AI Systems)*, *SR 11-7 (Federal Reserve Supervision and Regulation Guidance on Model Risk Management)*, dan GDPR Article 22 menuntut transparansi, pemantauan performa berkesinambungan, serta *auditability*. Kegagalan menyediakan jejak audit versi data, parameter drift, dan bias metrik dapat mengakibatkan sanksi hingga 7% dari omzet global perusahaan.

3. **Operasional (Debugging Data Pipelines)**:
   Mayoritas "drift" di produksi bukan disebabkan oleh fenomena sosiologis alami, melainkan anomali rekayasa data (*upstream data breakage*): perubahan format JSON pihak ketiga, modifikasi timezone dari UTC ke lokal, atau *null-handling* yang tidak terdokumentasi. ML Observability memungkinkan pelacakan hingga ke akar penyebab struktural (*root-cause analysis*) sebelum metrik bisnis terdampak.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur observabilitas ML *event-driven* berlatensi nol pada hot path inferensi:

```
[ Client Application ]
         |
         | (1) POST /predict (Features Payload)
         v
+-------------------------------------------------------------+
| Inference Engine (FastAPI / Triton / TorchServe)           |
|  - Load ML Artifacts                                        |
|  - Execute Prediction                                       |
|  - Fire-and-Forget / Async Telemetry Hook                   |
+-------------------------------------------------------------+
         |                                      |
         | (2) Inline Prediction Response       | (3) Async Emit Event
         v                                      v
  [ Client Application ]           [ Event Broker (Apache Kafka) ]
                                                |
                                                | (Topic: ml-inference-telemetry)
                                                v
                               +---------------------------------+
                               | Log Consumer & Validator        |
                               |  - Schema Validation (Avro)     |
                               +---------------------------------+
                                                |
                        +-----------------------+-----------------------+
                        |                                               |
                        v                                               v
       +---------------------------------+             +---------------------------------+
       | Time-Series Feature Store       |             | Statistical Drift Engine Worker |
       | (ClickHouse / Parquet DataLake) |             | (KS-Test, PSI, Wasserstein)    |
       +---------------------------------+             +---------------------------------+
                        |                                               |
                        |                                               v
                        |                              +---------------------------------+
                        |                              | Prometheus Exporter             |
                        |                              | (Exposes /metrics on port 9090) |
                        |                              +---------------------------------+
                        |                                               |
                        +-----------------------+                       v
                                                |              [ Prometheus Server ]
                                                v                       |
                                       [ Grafana Dashboard ] <----------+
                                                |
                                                | (Alert: PSI > 0.25)
                                                v
                                     [ PagerDuty / Slack Alert ]
```

#### Alur Eksekusi Data:
1. **Inference Execution**: Engine inferensi melayani payload prediksi secara sinkron.
2. **Telemetry Dispatch**: Middleware secara asinkron mengirimkan paket data (UUID inferensi, timestamp, vektor fitur, prediksi, versi model) ke Kafka topic `ml-inference-telemetry`. Ini menjamin overhead latensi inferensi $\le 1$ ms.
3. **Buffering & Batch Processing**: Drift Worker mengonsumsi data dari Kafka, mengagregasikannya dalam jendela geser (*sliding window*), dan membandingkannya terhadap dataset *baseline/reference* yang tersimpan di Model Registry.
4. **Metric Exportation**: Drift Worker mengekspos skor statistik ke Prometheus, yang dievaluasi oleh Alertmanager untuk memicu orkestrasi *retraining* atau *fallback*.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Population Stability Index (PSI)
PSI mengukur pergeseran distribusi populasi antara dataset referensi ($B$, baseline) dan target aktual ($T$) dalam jangka waktu tertentu. Variabel kontinu dibagi ke dalam $k$ bin (biasanya $k=10$ berdasarkan kuantil baseline).

$$PSI = \sum_{i=1}^{k} \left( \% T_i - \% B_i \right) \times \ln\left( \frac{\% T_i}{\% B_i} \right)$$

Di mana:
- $\% B_i$: Persentase observasi pada bin $i$ di dataset referensi.
- $\% T_i$: Persentase observasi pada bin $i$ di dataset produksi.

```
Interpretasi Nilai PSI:
+-------------------+-----------------------------------------------------+
| Nilai PSI         | Interpretasi & Tindakan yang Diambil                 |
+-------------------+-----------------------------------------------------+
| PSI < 0.10        | Tidak ada pergeseran signifikan (Insignificant).    |
| 0.10 <= PSI < 0.25| Pergeseran moderat (Warning). Pantau lebih ketat.    |
| PSI >= 0.25       | Pergeseran signifikan (Action Required).            |
|                   | Picu pipeline retraining atau alihkan ke fallback.  |
+-------------------+-----------------------------------------------------+
```

#### 5.2. Two-Sample Kolmogorov-Smirnov (KS) Test
KS-Test adalah uji non-parametrik yang membandingkan dua distribusi kumulatif kontinu empiris ($F_{ref}(x)$ dan $F_{curr}(x)$). KS-Test mencari jarak absolut supremum antar kedua kurva distribusi:

$$D = \sup_x |F_{ref}(x) - F_{curr}(x)|$$

Hipotesis nol ($H_0$) menyatakan bahwa kedua sampel ditarik dari distribusi kontinu yang identik. Jika *p-value* lebih kecil dari tingkat signifikansi $\alpha$ (misal $\alpha = 0.05$), $H_0$ ditolak, menandakan terjadinya *drift*.

#### 5.3. Penanganan Delayed Ground Truth
Jika label target aktual membutuhkan waktu untuk diperoleh, metrik evaluasi standar (seperti $F_1$-score, ROC-AUC, MAPE) tidak dapat dihitung secara real-time. Tiga strategi mitigasi teknis yang digunakan adalah:

1. **Proxy Performance Estimation (Metode CBPE)**:
   *Confidence-Based Performance Estimation* memanfaatkan probabilitas terkalibrasi dari model untuk memprediksi metrik performa (misalnya ROC-AUC) tanpa memerlukan label aktual, berdasarkan estimasi ketidakpastian (*uncertainty metrics*).
2. **Monitoring Feature Drift sebagai Proksi Kritis**:
   Jika input $X$ mengalami drift signifikan pada fitur yang memiliki *feature importance* (SHAP value) tinggi, performa model diasumsikan terdegradasi.
3. **Targeted Fast-Verification Sampling**:
   Mengirimkan sampel kecil inferensi produksi (misalnya 1%) secara acak ke tim annotator manusia (*Human-in-the-Loop*) untuk pelabelan prioritas cepat, guna menghasilkan estimasi performa harian yang valid secara statistik.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi drift detection engine modular yang mengekspos metrik ke Prometheus, dilengkapi schema validation via Pydantic v2 dan uji statistik numerik yang robust.

#### Struktur File:
```
ml_observability/
├── domain/
│   └── models.py
├── engine/
│   └── drift_detector.py
├── metrics/
│   └── prometheus_exporter.py
└── main.py
```

#### File: `ml_observability/domain/models.py`
```python
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, field_validator
import datetime

class InferenceRecord(BaseModel):
    inference_id: str
    model_version: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    features: Dict[str, float]
    prediction: float

    @field_validator("features")
    def validate_features_non_empty(cls, v: Dict[str, float]) -> Dict[str, float]:
        if not v:
            raise ValueError("Fitur input tidak boleh kosong.")
        return v

class FeatureDriftResult(BaseModel):
    feature_name: str
    psi_score: float
    ks_statistic: float
    ks_p_value: float
    has_drifted: bool
    drift_level: str  # "NONE", "MODERATE", "CRITICAL"
```

#### File: `ml_observability/engine/drift_detector.py`
```python
import numpy as np
import scipy.stats as stats
from typing import Dict, List, Tuple
from ml_observability.domain.models import FeatureDriftResult

class StatisticalDriftEngine:
    """
    Engine untuk mendeteksi pergeseran distribusi fitur numerik 
    menggunakan uji Kolmogorov-Smirnov dan Population Stability Index (PSI).
    """

    def __init__(self, baseline_data: Dict[str, np.ndarray], bins: int = 10, alpha: float = 0.05):
        self.baseline_data = baseline_data
        self.bins = bins
        self.alpha = alpha
        self._precalculate_baseline_quantiles()

    def _precalculate_baseline_quantiles(self) -> None:
        self.quantiles: Dict[str, np.ndarray] = {}
        for feature, values in self.baseline_data.items():
            if len(values) < self.bins:
                raise ValueError(f"Data baseline untuk fitur '{feature}' terlalu sedikit.")
            # Hitung quantil pemisah untuk alokasi bin yang merata pada baseline
            q = np.linspace(0, 100, self.bins + 1)
            self.quantiles[feature] = np.percentile(values, q)

    def calculate_psi(self, baseline: np.ndarray, target: np.ndarray, feature_name: str) -> float:
        """
        Menghitung skor PSI dengan smoothing Laplacian untuk mencegah log(0).
        """
        bins = self.quantiles[feature_name]
        # Pastikan bin boundaries menampung extreme values di target
        bins[0] = -np.inf
        bins[-1] = np.inf

        base_counts, _ = np.histogram(baseline, bins=bins)
        target_counts, _ = np.histogram(target, bins=bins)

        # Konversi ke proporsi persentase dengan zero-division prevention
        epsilon = 1e-4
        base_pct = (base_counts + epsilon) / (len(baseline) + (len(base_counts) * epsilon))
        target_pct = (target_counts + epsilon) / (len(target) + (len(target_counts) * epsilon))

        psi_val = np.sum((target_pct - base_pct) * np.log(target_pct / base_pct))
        return float(psi_val)

    def calculate_ks_test(self, baseline: np.ndarray, target: np.ndarray) -> Tuple[float, float]:
        """
        Menghitung Two-Sample KS-Test.
        Mengembalikan: (ks_statistic, p_value)
        """
        res = stats.ks_2samp(baseline, target)
        return float(res.statistic), float(res.pvalue)

    def analyze_drift(self, current_data: Dict[str, np.ndarray]) -> Dict[str, FeatureDriftResult]:
        results: Dict[str, FeatureDriftResult] = {}

        for feature, target_array in current_data.items():
            if feature not in self.baseline_data:
                continue

            base_array = self.baseline_data[feature]
            psi_score = self.calculate_psi(base_array, target_array, feature)
            ks_stat, ks_pval = self.calculate_ks_test(base_array, target_array)

            # Keputusan Drift Logic: Konvergensi PSI dan KS-Test
            is_drifted = (psi_score >= 0.25) or (ks_pval < self.alpha)

            if psi_score >= 0.25 or ks_pval < (self.alpha / 10):
                drift_level = "CRITICAL"
            elif psi_score >= 0.10 or ks_pval < self.alpha:
                drift_level = "MODERATE"
            else:
                drift_level = "NONE"

            results[feature] = FeatureDriftResult(
                feature_name=feature,
                psi_score=psi_score,
                ks_statistic=ks_stat,
                ks_p_value=ks_pval,
                has_drifted=is_drifted,
                drift_level=drift_level
            )

        return results
```

#### File: `ml_observability/metrics/prometheus_exporter.py`
```python
from prometheus_client import Gauge, Counter
from ml_observability.domain.models import FeatureDriftResult
from typing import Dict

# Definisi Metrik Prometheus
PSI_GAUGE = Gauge(
    "ml_feature_psi_score",
    "Population Stability Index (PSI) per feature",
    ["model_version", "feature_name"]
)

KS_STAT_GAUGE = Gauge(
    "ml_feature_ks_statistic",
    "Kolmogorov-Smirnov Statistic per feature",
    ["model_version", "feature_name"]
)

KS_PVAL_GAUGE = Gauge(
    "ml_feature_ks_p_value",
    "Kolmogorov-Smirnov Test p-value per feature",
    ["model_version", "feature_name"]
)

DRIFT_STATUS_GAUGE = Gauge(
    "ml_feature_drift_status",
    "Binary indicator of drift (1 = Drifted, 0 = Clean)",
    ["model_version", "feature_name", "severity"]
)

DRIFT_ALERTS_COUNTER = Counter(
    "ml_drift_detection_events_total",
    "Total count of drift detection analyses executed",
    ["model_version", "status"]
)

class PrometheusObservabilitySink:
    @staticmethod
    def publish_drift_metrics(model_version: str, drift_results: Dict[str, FeatureDriftResult]) -> None:
        """
        Update Prometheus metrics registry dengan nilai statistik terbaru.
        """
        for feature_name, result in drift_results.items():
            PSI_GAUGE.labels(model_version=model_version, feature_name=feature_name).set(result.psi_score)
            KS_STAT_GAUGE.labels(model_version=model_version, feature_name=feature_name).set(result.ks_statistic)
            KS_PVAL_GAUGE.labels(model_version=model_version, feature_name=feature_name).set(result.ks_p_value)

            # Set status indicator
            is_critical = 1 if result.drift_level == "CRITICAL" else 0
            DRIFT_STATUS_GAUGE.labels(
                model_version=model_version,
                feature_name=feature_name,
                severity="critical"
            ).set(is_critical)

            DRIFT_ALERTS_COUNTER.labels(
                model_version=model_version,
                status=result.drift_level
            ).inc()
```

#### File: `ml_observability/main.py`
```python
import numpy as np
import time
from ml_observability.engine.drift_detector import StatisticalDriftEngine
from ml_observability.metrics.prometheus_exporter import PrometheusObservabilitySink
from prometheus_client import start_http_server

def generate_mock_baseline(n_samples: int = 5000) -> dict:
    """Generate baseline dataset berdistribusi normal."""
    np.random.seed(42)
    return {
        "account_age_months": np.random.normal(loc=36.0, scale=12.0, size=n_samples),
        "debt_to_income_ratio": np.random.beta(a=2, b=5, size=n_samples),
        "transaction_amount_usd": np.random.exponential(scale=100.0, size=n_samples)
    }

def generate_mock_production_stream(n_samples: int = 1000, inject_drift: bool = False) -> dict:
    """Simulasi data inference production."""
    if not inject_drift:
        return {
            "account_age_months": np.random.normal(loc=36.0, scale=12.0, size=n_samples),
            "debt_to_income_ratio": np.random.beta(a=2, b=5, size=n_samples),
            "transaction_amount_usd": np.random.exponential(scale=100.0, size=n_samples)
        }
    else:
        # Simulasi Covariate Shift: Rata-rata transaksi melonjak drastis, DTI bergeser
        return {
            "account_age_months": np.random.normal(loc=37.0, scale=12.0, size=n_samples),
            "debt_to_income_ratio": np.random.beta(a=3, b=3, size=n_samples),  # Skew shifted
            "transaction_amount_usd": np.random.exponential(scale=250.0, size=n_samples)  # Heavy Drift
        }

if __name__ == "__main__":
    print("[+] Menginisialisasi ML Observability Engine...")
    
    # 1. Jalankan Prometheus Exporter HTTP Server di port 8000
    start_http_server(8000)
    print("[+] Prometheus Exporter running on http://localhost:8000/metrics")

    # 2. Inisialisasi Baseline dan Engine
    baseline = generate_mock_baseline(5000)
    engine = StatisticalDriftEngine(baseline_data=baseline)
    model_version = "credit_scoring_v2.1.0"

    iteration = 0
    while True:
        iteration += 1
        # Injeksi drift setelah iterasi ke-3 untuk mensimulasikan kegagalan produksi
        has_drift = iteration >= 3
        print(f"\n--- Iterasi Batch Observabilitas #{iteration} (Inject Drift: {has_drift}) ---")

        prod_data = generate_mock_production_stream(n_samples=1000, inject_drift=has_drift)
        drift_results = engine.analyze_drift(prod_data)

        # Log hasil ke terminal
        for feat, res in drift_results.items():
            print(f"Fitur: {feat:<25} | PSI: {res.psi_score:.4f} | KS p-val: {res.ks_p_value:.4e} | Level: {res.drift_level}")

        # Publish ke Prometheus
        PrometheusObservabilitySink.publish_drift_metrics(model_version, drift_results)
        print("[+] Metrik berhasil diekspor ke Prometheus Registry.")

        time.sleep(10)
```

---

### 7. Edge Cases & Failure Modes

1. **The Small Sample Pitfall (False Drift Alerts)**:
   - *Problem*: Jendela observasi (*sliding window*) yang terlalu kecil ($N < 100$) menghasilkan variansi sampel tinggi. Pengujian KS-Test sangat rentan terhadap *Type I error* (menolak $H_0$ padahal tidak ada drift sistemik).
   - *Mitigasi*: Terapkan ambang batas ukuran minimum sampel sebelum drift engine dijalankan ($N_{min} \ge 500$). Jika ukuran sampel tidak memadai, falling back ke *Cumulative Moving Average* dan lewati inferensi statistik formal.

2. **Extreme Categorical Cardinality**:
   - *Problem*: Algoritma chi-square goodness-of-fit atau cross-entropy drift breakdown saat feature kategorikal memiliki ribuan kategori unik (misal: ID merchant). Kategori baru (*unseen labels*) menghasilkan pembagian dengan nol.
   - *Mitigasi*: Kelompokkan kategori langka ke dalam bin gabungan `"__OTHER__"` secara deterministik, atau pantau metrik *Unseen Category Ratio* sebagai counter metric tersendiri.

3. **Multi-collinearity Masking**:
   - *Problem*: Pengujian drift univariat (fitur per fitur) gagal menangkap interaksi korelasi multivariat. Distribusi marginal $P(X_1)$ dan $P(X_2)$ mungkin tampak normal, namun korelasi bersama $\text{Corr}(X_1, X_2)$ mengalami kerusakan (*broken joint dependency*).
   - *Mitigasi*: Implementasikan *Multivariate Drift Detection* berkala menggunakan rekonstruksi *Autoencoder Error* atau *Kernel Two-Sample Test (Maximum Mean Discrepancy / MMD)* pada layer monitoring batch.

---

### 8. Trade-offs & Alternatif Solusi

Setiap strategi drift detection memiliki kompromi antara latensi, memori, komputasi, dan akurasi:

```
+--------------------------+-----------------------+---------------------+-------------------------------+
| Metode / Arsitektur      | Kompleksitas Komputasi| Konsumsi Memori     | Keunggulan & Batasan          |
+--------------------------+-----------------------+---------------------+-------------------------------+
| Univariate KS-Test       | O(N log N)            | Sedang              | Bagus untuk data kontinu;     |
|                          |                       | (Menyimpan sampel)  | tidak bisa untuk kategorikal. |
+--------------------------+-----------------------+---------------------+-------------------------------+
| Population Stability     | O(N)                  | Sangat Rendah       | Cepat; sensitif terhadap      |
| Index (PSI)              |                       | (Hanya bin counts)  | pemilihan batas binning.      |
+--------------------------+-----------------------+---------------------+-------------------------------+
| Wasserstein Distance     | O(N log N)            | Sedang              | Memberikan nilai jarak fisik; |
| (Earth Mover's Dist)     |                       |                     | interpretasi skala tergantung|
|                          |                       |                     | magnitudo data.               |
+--------------------------+-----------------------+---------------------+-------------------------------+
| Autoencoder              | O(N * Forward_Pass)   | Tinggi              | Mampu menangkap interaksi     |
| Reconstruction Error     |                       | (Eksekusi Neural Net| multivariat kompleks; butuh   |
|                          |                       | di GPU/CPU)         | resource komputasi besar.     |
+--------------------------+-----------------------+---------------------+-------------------------------+
```

#### Real-time Streaming vs Batch Sliding Window
- **Streaming Point-in-time Drift (misal ADWIN, River)**: Memperbarui statistik pada setiap payload baru. Bagus untuk deteksi instan anomali masif, tetapi sensitif terhadap noise individual dan membutuhkan infrastruktur stateful streaming (Apache Flink).
- **Batch Scheduled Drift (Evidently AI, Cron KS-test)**: Menghitung metrik setiap jam atau hari sekali. Hemat biaya komputasi, tahan terhadap fluktuasi sementara (*micro-spikes*), namun memiliki keterlambatan deteksi (*detection lag*).

---

### 9. Best Practices & Standar Industri

1. **Zero-Inference Impact Isolation**:
   Logging telemetri prediksi wajib menggunakan pola non-blocking (misal: *Async background thread*, *UDP packet dispatch*, atau *Kafka producer buffer*). Gangguan atau latensi pada monitoring backend tidak boleh menyebabkan timeout pada proses inferensi klien.

2. **Dual-Baseline Strategy**:
   Gunakan dua baseline berbeda untuk perbandingan analitis:
   - **Static Gold Baseline**: Data pengujian final (*holdout validation set*) saat model dilatih dan divalidasi.
   - **Moving Baseline (Previous Period)**: Data produksi dari jendela 7 hari sebelumnya. Ini mencegah false alarm akibat musim (*seasonality*, seperti pola akhir pekan).

3. **EU AI Act & Governance Metadata Schema**:
   Setiap kali model dideploy ke produksi, wajib didaftarkan *Model Card* terprogram dalam format JSON/YAML yang menyertakan:
   - Hash Git commit artefak model.
   - Hash dataset pelatihan (data provenance).
   - Batas ambang toleransi drift operasional.
   - Metrik pengujian *Fairness & Disparate Impact* antar kelompok demografi.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Principal MLOps Engineer di platform fintech. Model regresi penilaian risiko kredit (`credit_risk_model`) telah dideploy. Tugas Anda adalah memvalidasi sistem observabilitas dengan mengeksekusi script yang memicu drift buatan, lalu memverifikasi respons scraping metrik Prometheus.

#### Langkah 1: Persiapan Lingkungan
Buat direktori kerja baru dan install dependensi yang dibutuhkan:
```bash
mkdir -p mlops_drift_lab && cd mlops_drift_lab
python3 -m venv venv
source venv/bin/activate
pip install numpy scipy prometheus-client pydantic requests
```

#### Langkah 2: Setup Implementasi Kode
Buat file `lab_monitor.py` dan salin seluruh implementasi dari **Bagian 6 (Production-Ready Code Implementation)** ke dalam file tersebut (gabungkan class atau gunakan modularitas Python).

#### Langkah 3: Eksekusi Deteksi Drift
Jalankan script monitoring pada Terminal 1:
```bash
python lab_monitor.py
```

*Output yang diharapkan pada terminal:*
```text
[+] Menginisialisasi ML Observability Engine...
[+] Prometheus Exporter running on http://localhost:8000/metrics

--- Iterasi Batch Observabilitas #1 (Inject Drift: False) ---
Fitur: account_age_months        | PSI: 0.0031 | KS p-val: 7.8210e-01 | Level: NONE
Fitur: debt_to_income_ratio      | PSI: 0.0052 | KS p-val: 4.1200e-01 | Level: NONE
Fitur: transaction_amount_usd    | PSI: 0.0028 | KS p-val: 9.3100e-01 | Level: NONE
[+] Metrik berhasil diekspor ke Prometheus Registry.
...
--- Iterasi Batch Observabilitas #3 (Inject Drift: True) ---
Fitur: account_age_months        | PSI: 0.0121 | KS p-val: 1.1500e-01 | Level: NONE
Fitur: debt_to_income_ratio      | PSI: 0.3129 | KS p-val: 0.0000e+00 | Level: CRITICAL
Fitur: transaction_amount_usd    | PSI: 0.8942 | KS p-val: 0.0000e+00 | Level: CRITICAL
[+] Metrik berhasil diekspor ke Prometheus Registry.
```

#### Langkah 4: Validasi Metrik Prometheus
Buka Terminal 2 dan lakukan HTTP request untuk mengecek metrik yang diekspos:
```bash
curl -s http://localhost:8000/metrics | grep ml_feature_drift_status
```

*Output Verifikasi Keberhasilan:*
```text
# HELP ml_feature_drift_status Binary indicator of drift (1 = Drifted, 0 = Clean)
# TYPE ml_feature_drift_status gauge
ml_feature_drift_status{feature_name="account_age_months",model_version="credit_scoring_v2.1.0",severity="critical"} 0.0
ml_feature_drift_status{feature_name="debt_to_income_ratio",model_version="credit_scoring_v2.1.0",severity="critical"} 1.0
ml_feature_drift_status{feature_name="transaction_amount_usd",model_version="credit_scoring_v2.1.0",severity="critical"} 1.0
```

#### Langkah 5: Tugas Analisis
Jawab pertanyaan berikut untuk memvalidasi pemahaman:
1. Mengapa `debt_to_income_ratio` memiliki KS p-value `0.0000e+00`? Apa makna nilai tersebut terhadap hipotesis nol ($H_0$)?
2. Jika traffic transaksi turun drastis di akhir pekan, konfigurasi metrik apa yang perlu disesuaikan agar tidak memicu false alarm pada PSI? Jelaskan strategi windowing yang tepat.