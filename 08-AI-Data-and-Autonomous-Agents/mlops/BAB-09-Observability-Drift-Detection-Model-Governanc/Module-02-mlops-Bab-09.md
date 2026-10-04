# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Observability, Drift Detection & Model Governance**  
**Kategori: 08-AI-Data-and-Autonomous-Agents (MLOps)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Merancang & Mengimplementasikan Observability Pipeline End-to-End**: Membangun arsitektur telemetri probabilistik dan deterministik untuk melacak payload inferensi, latensi, dan metrik sistem secara *near real-time* menggunakan OpenTelemetry, Prometheus, dan streaming broker (Kafka).
2. **Mengeksekusi Deteksi Drift Multi-Metrik Secara Matematis**: Mengimplementasikan algoritma statistik univariat dan multivariat (*Population Stability Index* (PSI), *Kolmogorov-Smirnov Test* (KS-Test), *Wasserstein Distance*, dan *Maximum Mean Discrepancy* (MMD)) pada data berkecepatan tinggi dengan optimasi komputasi streaming.
3. **Mengatasi Tantangan Delayed Ground Truth**: Menerapkan arsitektur rekonsiliasi data asinkron untuk mendeteksi *concept drift* ketika label aktual (*ground truth*) memiliki latensi berhari-hari atau berbulan-bulan menggunakan proksi performa dan inferensi Bayesian.
4. **Menerapkan Enterprise Model Governance & Audit Trails**: Mengonfigurasi *lineage tracking*, *cryptographic model signing*, SBOM (*Software Bill of Materials* untuk ML), serta artefak kepatuhan regulasi (EU AI Act, SOC2 Tipe II) menggunakan MLflow Governance, OpenLineage, dan Cosign/Sigstore.

---

## 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib menguasai:
- **Statistika & Teori Probabilitas Lanjut**: Uji hipotesis non-parametrik, fungsi distribusi kumulatif (CDF), divergensi Kullback-Leibler (KL Divergence), dan estimasi densitas kernel (KDE).
- **Sistem Terdistribusi**: Pemahaman mendalam terkait message broker (*event streaming* via Apache Kafka/Pulsar), sistem penyimpanan berbasis objek (S3/GCS), dan arsitektur analitik (Apache Iceberg/ClickHouse).
- **Containerization & Service Mesh**: Kubernetes Lanjut (Custom Resource Definitions, Envoy proxy sidecar injection, metrics-server).
- **Core MLOps**: Model packaging, MLflow lifecycle, REST/gRPC inferencing pattern (Triton/vLLM/TorchServe).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Taksonomi Drift: Data, Concept, dan Pipeline Drift

Dalam sistem inferensi produksi, degradasi performa model dapat dikategorikan ke dalam tiga dimensi ortogonal:

1. **Covariate Shift / Data Drift ($P(X) \neq P_{ref}(X)$ tapi $P(Y|X) = P_{ref}(Y|X)$)**:
   Distribusi fitur masukan ($X$) berubah seiring waktu, namun pemetaan fungsional antara fitur terhadap target ($Y$) tetap konstan. Contoh: Perubahan demografi pengguna baru pada sistem credit scoring akibat ekspansi geografis.
2. **Concept Drift ($P(Y|X) \neq P_{ref}(Y|X)$ tapi $P(X) = P_{ref}(X)$)**:
   Distribusi probabilitas kondisional target berubah terhadap fitur masukan. Pola input sama, namun makna target telah bergeser secara fundamental. Contoh: Pola transaksi yang sebelumnya sah kini diklasifikasikan sebagai penipuan (*fraud*) karena adaptasi taktik pelaku kejahatan siber pasca-regulasi perbankan baru.
3. **Prior Probability Shift / Label Drift ($P(Y) \neq P_{ref}(Y)$)**:
   Distribusi kelas target berubah secara marginal.
4. **Pipeline / Data Quality Drift**:
   Distribusi berubah bukan karena dinamika dunia nyata, melainkan *upstream schema breakage*, *loss of precision*, unit metrik yang tidak konsisten (misal: milimeter menjadi inci), atau *null value spikes*.

```
   Training Time (Reference)               Production Time (Inference)
┌───────────────────────────────┐       ┌───────────────────────────────┐
│ Fitur X_ref ~ P_ref(X)        │       │ Fitur X_curr ~ P_curr(X)      │
│ Target Y_ref ~ P_ref(Y|X)     │       │ Target Y_curr ~ P_curr(Y|X)   │
└──────────────┬────────────────┘       └──────────────┬────────────────┘
               │                                       │
               ▼                                       ▼
       [Model Training] ───────────────► [Inference Engine]
                                               │  │
    ┌──────────────────────────────────────────┘  └────────────────────────────────┐
    ▼                                                                              ▼
[Covariate Shift Check]                                                   [Concept Shift Check]
Uji: P_curr(X) == P_ref(X) ?                                              Uji: P_curr(Y|X) == P_ref(Y|X) ?
Algoritma: PSI, KS-Test, Wasserstein, MMD                                Algoritma: Delayed Reconciliation, Error Proxy
```

### 3.2 Matematika Deteksi Drift

#### 3.2.1 Population Stability Index (PSI)
Digunakan secara ekstensif pada fitur kategorikal dan numerik yang dibinning:
$$\text{PSI} = \sum_{b=1}^{B} \left( P_b - Q_b \right) \times \ln\left(\frac{P_b}{Q_b}\right)$$
Di mana:
- $B$ adalah jumlah bin (*quantiles* atau *equal-width*).
- $P_b$ adalah proporsi sampel aktual/produksi pada bin $b$.
- $Q_b$ adalah proporsi sampel referensi/baseline pada bin $b$.
- Batasan industri:
  - $\text{PSI} < 0.1$: Tidak ada perubahan signifikan (*No Shift*).
  - $0.1 \le \text{PSI} < 0.25$: Terjadi pergeseran moderat (*Moderate Drift*), picu warning telemetri.
  - $\text{PSI} \ge 0.25$: Pergeseran signifikan (*Severe Drift*), picu mitigasi/retraining.

#### 3.2.2 Kolmogorov-Smirnov (KS) Test
Uji non-parametrik dua sampel untuk variabel kontinu kontinu yang membandingkan Fungsi Distribusi Kumulatif empiris ($F_{1}(x)$ dan $F_{2}(x)$):
$$D = \sup_{x} |F_{ref}(x) - F_{curr}(x)|$$
Hipotesis Nol ($H_0$): Kedua sampel berasal dari distribusi kontinu yang sama. Jika $p\text{-value} < \alpha$ (umumnya $\alpha=0.01$ atau $0.05$), $H_0$ ditolak.

#### 3.2.3 Wasserstein Distance (Earth Mover's Distance)
Mengukur kerja minimal yang dibutuhkan untuk mentransformasikan satu distribusi probabilitas menjadi distribusi lain:
$$W_1(u, v) = \int_{-\infty}^{\infty} |U(x) - V(x)| dx$$
Di mana $U(x)$ dan $V(x)$ berturut-turut merupakan CDF empiris dari distribusi referensi dan target. Keunggulan: Memberikan metrik jarak yang mulus (*smooth metric*) bahkan saat kedua distribusi memiliki *support* yang saling lepas (*disjoint support*), tidak sensitif terhadap jumlah bin seperti PSI.

### 3.3 Arsitektur Telemetri Terdistribusi High-Throughput

Dalam throughput tingkat tinggi (>10.000 QPS), menghitung drift secara *in-line* pada inference engine akan merusak service level objective (SLO) latensi ($p99 < 15\text{ms}$). Oleh karena itu, digunakan pemisahan arsitektural:

```
[Client Application]
        │
        │ HTTPS / gRPC (Payload & Metadata)
        ▼
┌────────────────────────────────────────────────────────┐
│ Inference Service (e.g., Triton / FastAPI via Envoy)   │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Model Engine (PyTorch / ONNX Runtime)              │ │
│ └─────────────────────────┬──────────────────────────┘ │
│                           │ Non-blocking Async Dispatch │
│ ┌─────────────────────────▼──────────────────────────┐ │
│ │ Telemetry Sidecar (FluentBit / Vector)             │ │
│ └─────────────────────────┬──────────────────────────┘ │
└───────────────────────────┼────────────────────────────┘
                            │ Kafka Protocol
                            ▼
┌────────────────────────────────────────────────────────┐
│ Apache Kafka (Topic: ml-inference-telemetry-v1)       │
│ Partitions: Hashed by Model_ID + Model_Version         │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│ Real-Time Window Monitor  │ │ Long-Term Cold Storage    │
│ (Flink / Faust Engine)    │ │ Vectorized Parquet Sink   │
│ - Sliding Window (5m)     │ │ S3 / GCS / Iceberg        │
│ - T-Digest / HyperLogLog  │ └─────────────┬─────────────┘
│ - Alert via OpenTelemetry │               │
└─────────────┬─────────────┘               ▼
              ▼                ┌───────────────────────────┐
┌───────────────────────────┐  │ Offline Batch Drift &     │
│ Prometheus / Alertmanager │  │ Reconciliation Job        │
│ Grafana Dashboard         │  │ (Ray / Spark / Evidently) │
└───────────────────────────┘  └───────────────────────────┘
```

---

## 4. Why & What

| Dimensi | Pendekatan Reaktif Tradisional | Observability & Governance Lanjutan |
| :--- | :--- | :--- |
| **Pemicu Retraining** | Jadwal statis (misal: setiap Minggu malam) atau komplain manual dari end-user. | Deteksi deviasi statistik otomatis (PSI/Wasserstein) dan proksi degradasi performa (*event-driven*). |
| **Resolusi Latensi Drift** | Menunggu rekonsiliasi label ground-truth (bisa berbulan-bulan). | Algoritma *Unsupervised Drift Detection* + Bayesian Uncertainty Estimation pada *prediction window*. |
| **Audit & Kepatuhan** | Metadata model disimpan ad-hoc di spreadsheet; artefak binary tanpa proteksi integritas. | Immutable Model Lineage (OpenLineage), SBOM terverifikasi, dan Cryptographic Attestation (Sigstore/Cosign). |
| **Overhead Inferensi** | Uji statistik dilakukan synchronous di path inferensi, membebani $p99$ response time. | Asynchronous dual-path telemetry: zero-latency impact via non-blocking ring buffer dan event-streaming. |

---

## 5. How (Workflow Detail)

1. **Instrumentation & Extraction**: Payload inferensi (fitur masukan, probabilitas output, tensor embeddings, `model_version`, `trace_id`) ditangkap menggunakan OpenTelemetry SDK tanpa mengorbankan performa thread komputasi utama.
2. **Buffer & Streaming**: Sidecar process mengekstrak log inferensi melalui shared memory (IPC) atau local socket, lalu mengirimkannya secara batch ke Apache Kafka.
3. **Stateless vs. Stateful Processing**:
   - *Stream Processing (Hot Path)*: Apache Flink atau daemon Python kustom menggunakan algoritma *t-digest* untuk menghitung aproksimasi kuantil dan mendeteksi anomali/outlier univariat secara instan.
   - *Batch Reconciliation (Cold Path)*: Apache Spark / Celery worker membaca Parquet sink dari data lake, membandingkan data produksi periode $T_w$ terhadap data acuan *baseline* ($T_0$), lalu mengeksekusi KS-Test dan Wasserstein Distance.
4. **Scoring & Alerting**: Nilai drift diagregasi. Jika melampaui *threshold* batas kritis:
   - Alerting dikirim via OpenTelemetry Metric Exporter ke Prometheus/Alertmanager.
   - Event trigger dikirim ke orchestrator (misal: Airflow/Kubeflow Pipelines) untuk mengevaluasi mitigasi atau retraining.
5. **Lineage Ledger Logging**: Setiap transaksi model, metadata dependensi, hash bobot model, dan evaluasi data dicatat ke dalam OpenLineage backend untuk verifikasi tata kelola.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah model machine learning seperti **Sistem Penjernihan Air Otomatis** di sebuah kota metropolitan:
- **Baseline Training Data**: Karakteristik air pegunungan yang jernih dengan kandungan mineral terukur yang digunakan untuk merancang filter penyaring.
- **Model Inferensi**: Mesin penyaring air yang memproses air masuk dan menghasilkan air siap minum.
- **Data Drift**: Terjadi hujan deras di hulu yang membuat air masuk berlumpur (distribusi input $X$ berubah). Mesin filter mungkin masih bisa beroperasi, tetapi bebannya melonjak dan risiko kontaminasi meningkat.
- **Concept Drift**: Pabrik kimia di dekat sungai membuang limbah baru yang tidak berwarna dan tidak berbau (fitur terlihat identik), namun molekul air tersebut kini bersifat racun bagi manusia ($P(Y|X)$ berubah drastis). Tanpa sensor kimia khusus, filter meloloskan air beracun tersebut.
- **Observability System**: Rangkaian sensor real-time yang memonitor pH, konduktivitas listrik, dan kekeruhan pada pipa inlet ($X$) dan outlet ($Y$) sebelum air dialirkan ke penduduk.

```
       [ INLET: Input Features X ]
                   │
                   ▼
       ┌───────────────────────┐
       │ Sensor A: Data Drift  │ ──► Mengukur: Apakah lumpur/mineral naik?
       │ (PSI, KS-Test)        │     (Perubahan input P(X))
       └───────────┬───────────┘
                   │
                   ▼
       ┌───────────────────────┐
       │ Model: Filter Fisik   │ ──► Menghasilkan Prediksi Y_hat
       └───────────┬───────────┘
                   │
                   ▼
       [ OUTLET: Air Hasil Filter ]
                   │
                   ▼
       ┌───────────────────────┐
       │ Sensor B: Concept     │ ──► Mengukur: Apakah output aman saat
       │ Drift / Delayed Check │     diverifikasi lab? (Ground truth Y)
       └───────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Menghitung PSI dan KS-Test dari Nol

Berikut adalah implementasi Python native (menggunakan `numpy` dan `scipy.stats`) untuk menghitung metrik drift univariat.

```python
import numpy as np
from scipy import stats
from typing import Tuple, Dict

def calculate_psi(
    baseline: np.ndarray, 
    target: np.ndarray, 
    num_bins: int = 10, 
    epsilon: float = 1e-4
) -> float:
    """
    Menghitung Population Stability Index (PSI) antara dua set data kontinu.
    Menggunakan kuantil dari baseline sebagai batas binning yang adil.
    """
    # Tentukan quantile cut-off berdasarkan data baseline
    quantiles = np.linspace(0, 100, num_bins + 1)
    bins = np.percentile(baseline, quantiles)
    # Sesuaikan batas luar untuk menangani nilai di luar batas minimum/maksimum
    bins[0] = -np.inf
    bins[-1] = np.inf

    # Hitung frekuensi absolut
    baseline_counts, _ = np.histogram(baseline, bins=bins)
    target_counts, _ = np.histogram(target, bins=bins)

    # Hitung proporsi probabilitas dengan smoothing epsilon untuk menghindari div-by-zero
    baseline_pct = (baseline_counts / len(baseline)) + epsilon
    target_pct = (target_counts / len(target)) + epsilon

    # Normalisasi kembali agar total proporsi == 1
    baseline_pct /= np.sum(baseline_pct)
    target_pct /= np.sum(target_pct)

    # Formula PSI
    psi_value = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
    return float(psi_value)


def calculate_ks_test(
    baseline: np.ndarray, 
    target: np.ndarray
) -> Tuple[float, float]:
    """
    Menghitung Kolmogorov-Smirnov 2-sample test.
    Returns:
        (ks_statistic, p_value)
    """
    res = stats.ks_2samp(baseline, target)
    return float(res.statistic), float(res.pvalue)


if __name__ == "__main__":
    np.random.seed(42)
    ref_data = np.random.normal(loc=0.0, scale=1.0, size=10_000)
    
    # Kasus 1: Target terdistribusi identik
    curr_data_healthy = np.random.normal(loc=0.0, scale=1.0, size=5_000)
    
    # Kasus 2: Target mengalami pergeseran rata-rata (Covariate Shift)
    curr_data_shifted = np.random.normal(loc=0.35, scale=1.2, size=5_000)

    psi_healthy = calculate_psi(ref_data, curr_data_healthy)
    ks_stat_h, p_val_h = calculate_ks_test(ref_data, curr_data_healthy)
    
    psi_shifted = calculate_psi(ref_data, curr_data_shifted)
    ks_stat_s, p_val_s = calculate_ks_test(ref_data, curr_data_shifted)

    print(f"[Healthy] PSI: {psi_healthy:.4f} | KS: {ks_stat_h:.4f} (p-value: {p_val_h:.4e})")
    print(f"[Shifted] PSI: {psi_shifted:.4f} | KS: {ks_stat_s:.4f} (p-value: {p_val_s:.4e})")
```

---

### 7.2 Practical Example: Enterprise-Grade Production Drift Detector Service

Berikut adalah arsitektur mikro untuk inference validation engine yang mengekstraksi telemetri, menghitung metrik statistik, menghasilkan alert, serta memvalidasi kepatuhan tata kelola.

```python
"""
drift_monitor_service.py
Layanan monitoring inferensi multi-fitur dengan validasi drift dan telemetri terstruktur.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field
from scipy.stats import wasserstein_distance, ks_2samp

# Konfigurasi Logging Terstruktur
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DriftDetectionEngine")


class FeatureMetrics(BaseModel):
    feature_name: str
    psi: float
    ks_statistic: float
    ks_p_value: float
    wasserstein_dist: float
    drift_detected: bool
    status: str


class DriftReport(BaseModel):
    model_id: str
    model_version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_samples: int
    features_evaluated: Dict[str, FeatureMetrics]
    overall_drift_state: bool


class EnterpriseDriftDetector:
    def __init__(
        self,
        model_id: str,
        model_version: str,
        reference_data: Dict[str, np.ndarray],
        psi_threshold: float = 0.2,
        ks_alpha: float = 0.01,
        wasserstein_threshold: float = 0.15
    ):
        self.model_id = model_id
        self.model_version = model_version
        self.reference_data = reference_data
        self.psi_threshold = psi_threshold
        self.ks_alpha = ks_alpha
        self.wasserstein_threshold = wasserstein_threshold
        self._validate_reference_cache()

    def _validate_reference_cache(self) -> None:
        for k, v in self.reference_data.items():
            if not isinstance(v, np.ndarray) or v.ndim != 1:
                raise ValueError(f"Feature '{k}' harus berwujud 1D numpy array.")
            if len(v) < 100:
                raise ValueError(f"Feature '{k}' baseline terlalu kecil (<100 sampel).")

    def _calculate_psi(self, ref: np.ndarray, cur: np.ndarray, bins_count: int = 10) -> float:
        quantiles = np.linspace(0, 100, bins_count + 1)
        bins = np.percentile(ref, quantiles)
        bins[0] = -np.inf
        bins[-1] = np.inf
        
        # Penanganan duplicate quantiles jika data memiliki distribusi diskret tinggi
        bins = np.unique(bins)
        if len(bins) < 2:
            return 0.0

        r_counts, _ = np.histogram(ref, bins=bins)
        c_counts, _ = np.histogram(cur, bins=bins)

        eps = 1e-4
        r_dist = (r_counts / len(ref)) + eps
        c_dist = (c_counts / len(cur)) + eps
        
        r_dist /= np.sum(r_dist)
        c_dist /= np.sum(c_dist)

        return float(np.sum((c_dist - r_dist) * np.log(c_dist / r_dist)))

    def evaluate_batch(self, current_batch: Dict[str, np.ndarray]) -> DriftReport:
        features_eval: Dict[str, FeatureMetrics] = {}
        drift_count = 0
        total_samples = 0

        for feat_name, cur_values in current_batch.items():
            if feat_name not in self.reference_data:
                logger.warning("Fitur tidak terdaftar di baseline: %s. Lewati.", feat_name)
                continue

            ref_values = self.reference_data[feat_name]
            total_samples = len(cur_values)

            # 1. Hitung PSI
            psi_val = self._calculate_psi(ref_values, cur_values)
            
            # 2. Hitung KS-Test
            ks_stat, p_val = ks_2samp(ref_values, cur_values)
            
            # 3. Hitung Wasserstein Distance (Normalized jika diperlukan)
            std_ref = np.std(ref_values) or 1.0
            norm_w_dist = float(wasserstein_distance(ref_values, cur_values) / std_ref)

            # Drift Logic: Multivariat Rule Voting
            is_drift = (
                (psi_val >= self.psi_threshold) or 
                (p_val < self.ks_alpha and norm_w_dist >= self.wasserstein_threshold)
            )

            status = "HEALTHY"
            if is_drift:
                status = "DRIFT_CRITICAL"
                drift_count += 1
            elif psi_val >= (self.psi_threshold * 0.7):
                status = "DRIFT_WARNING"

            features_eval[feat_name] = FeatureMetrics(
                feature_name=feat_name,
                psi=round(psi_val, 4),
                ks_statistic=round(float(ks_stat), 4),
                ks_p_value=float(p_val),
                wasserstein_dist=round(norm_w_dist, 4),
                drift_detected=is_drift,
                status=status
            )

        overall_drift = drift_count > 0

        report = DriftReport(
            model_id=self.model_id,
            model_version=self.model_version,
            total_samples=total_samples,
            features_evaluated=features_eval,
            overall_drift_state=overall_drift
        )

        if overall_drift:
            logger.error("DRIFT TERDETEKSI: Model ID: %s, Versi: %s", self.model_id, self.model_version)
        else:
            logger.info("Batch Evaluasi Normal: Model ID: %s, Versi: %s", self.model_id, self.model_version)

        return report


# Simulasi Integrasi Produksi
if __name__ == "__main__":
    # Generate Synthetic Baseline
    np.random.seed(1337)
    features = ["transaction_amount", "account_age_days", "velocity_score"]
    
    baseline_payload = {
        "transaction_amount": np.random.exponential(scale=50.0, size=5000),
        "account_age_days": np.random.uniform(low=1, high=1000, size=5000),
        "velocity_score": np.random.normal(loc=0.5, scale=0.15, size=5000)
    }

    detector = EnterpriseDriftDetector(
        model_id="fraud_detector_xgboost",
        model_version="v2.1.0",
        reference_data=baseline_payload,
        psi_threshold=0.25,
        ks_alpha=0.01,
        wasserstein_threshold=0.20
    )

    # Payload Produksi yang Mengalami Drift pada transaction_amount & velocity_score
    production_payload = {
        "transaction_amount": np.random.exponential(scale=95.0, size=1200), # Pergeseran skala ekstrim
        "account_age_days": np.random.uniform(low=1, high=1000, size=1200),   # Tidak berubah
        "velocity_score": np.random.normal(loc=0.75, scale=0.3, size=1200)   # Pergeseran rata-rata & variansi
    }

    report = detector.evaluate_batch(production_payload)
    print("\n--- JSON OUTPUT AUDIT COMPLIANCE ---")
    print(report.model_dump_json(indent=2))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Fraud Detection Engine pada Platform FinTech Tier-1 (35.000 QPS)

* **Konteks**: Platform pemrosesan pembayaran memproses 35.000 transaksi per detik menggunakan model ensemble berbasis LightGBM dan Deep Neural Network. Model mengklasifikasikan transaksi sebagai *legitimate* atau *fraudulent*.
* **Permasalahan**: Pada event *Flash Sale Nasional* (11.11), volume transaksi melonjak 400%. Pola belanja bergeser drastis (nominal kecil, frekuensi tinggi, login dari subnet ISP baru). Sistem internal mengalami:
  1. *False Positive Spikes*: Transaksi legal jutaan pengguna terblokir.
  2. *Delayed Ground Truth*: Konfirmasi *chargeback* dari bank penerbit kartu membutuhkan waktu 30 hingga 90 hari, sehingga metrik akurasi tradisional (F1-score, ROC-AUC) **buta total** secara real-time.
* **Solusi Arsitektur**:
  1. **Dual-Ring Telemetry Sampling**: Menggunakan Envoy proxy access log filter, 100% metadata inferensi dialirkan ke Apache Kafka cluster dengan partisi berbasis `user_id`.
  2. **Unsupervised Drift Windowing Engine**: Apache Flink membandingkan distribusi input dengan data baseline 7 hari sebelumnya menggunakan Wasserstein Distance per jendela 15 menit.
  3. **Performance Degradation Proxy**: Karena ground truth tertunda, Flink memonitor metrik *Prediction Confidence Entropy*:
     $$H(p) = - \sum_{c} p(y_c|x) \log p(y_c|x)$$
     Kenaikan tajam pada entropi prediksi mengindikasikan bahwa model berada pada kondisi ketidakpastian tinggi (*high uncertainty*).
  4. **Dynamic Fallback Circuit Breaker**: Ketika drift terdeteksi pada *velocity features* dan entropi model melampaui ambang batas aman ($H > 0.82$), sistem mengaktifkan *Rules Engine Fallback* (deterministic expert rules) untuk membatasi nilai transaksi maksimum tanpa memblokir akun pengguna.
* **Hasil**:
  - Penurunan *False Positive Rate* (FPR) sebesar 42% selama puncak anomali traffic.
  - Waktu deteksi insiden (*Mean Time to Detect* / MTTD) berkurang dari 14 hari menjadi **3 menit**.
  - Total kerugian finansial akibat penipuan dan penolakan transaksi legal berkurang sebesar $3,4 juta USD.

---

## 9. Trade-offs (Sistem Drift & Monitoring)

| Parameter Desain | Pilihan A | Pilihan B | Trade-off & Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **Statistical Test Type** | **Univariate Test** (KS, PSI per fitur) | **Multivariate Test** (MMD, Mahalanobis Distance, Classifier Two-Sample Test) | Univariate sangat cepat ($O(N \log N)$), mudah diinterpretasikan fitur mana yang rusak, namun gagal mendeteksi korelasi antar-fitur yang hancur. Multivariate mendeteksi perubahan dimensional kompleks, tetapi mahal secara komputasi ($O(N^2 \cdot D)$) dan sulit dilacak ke akar masalah (*root-cause localization*). |
| **Sampling Paradigm** | **Full Stream Processing (100% Ingestion)** | **Reservoir Sampling / Stratified Random Sampling (1-5%)** | 100% Ingestion memberikan akurasi absolut untuk *rare-event detection*, namun memakan *network egress* dan *storage cost* masif. Reservoir sampling menstabilkan throughput komputasi dan biaya infrastruktur, namun berisiko melewatkan anomali kelas minoritas (*extreme tail events*). |
| **Windowing Strategy** | **Fixed Sliding Window** (e.g., 1 jam terakhir) | **Adaptive Windowing (ADWIN)** | Fixed Sliding Window mudah diimplementasikan pada database/streaming, namun rentan *false alarm* pada siklus musiman harian (*diurnal patterns*). ADWIN menyesuaikan ukuran jendela secara otomatis berdasarkan variansi statistik, namun kompleks dalam konkurensi terdistribusi. |
| **Telemetry Ingestion** | **In-line Synchronous Logging** | **Asynchronous Out-of-Band Sidecar** | In-line menjamin setiap inferensi tercatat (*zero-loss guarantees*), tetapi menambah p99 latensi sebesar 5-15ms. Asynchronous sidecar memiliki dampak nol terhadap latensi inferensi, tetapi jika node mati (*OOMKilled*), data pada buffer memori bisa hilang. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Common Mistake 1: Data Leakage pada Baseline Quantiles
* **Anti-Pattern**: Menghitung binning quantile pada gabungan data baseline dan data produksi saat evaluasi berkala.
* **Dampak**: Binning boundary berubah setiap kali evaluasi dijalankan, menghilangkan konsistensi perbandingan metrik PSI antar waktu.
* **Solusi**: Bekukan batas kuantil bin (*bin edges*) dari dataset validasi referensi saat model pertama kali di-deploy ke registry (`model_card.metadata.quantiles`). Gunakan array batas statis ini untuk semua inferensi produksi.

### 10.2 Common Mistake 2: "The p-value Paradox" pada Sample Size Ekstrim
* **Anti-Pattern**: Menggunakan Uji Kolmogorov-Smirnov standar pada sampel produksi berukuran masif ($N > 500.000$).
* **Dampak**: Secara matematis, uji KS menjadi hipersensitif terhadap deviasi mikroskopis. Pergeseran data yang sangat sepele ($p\text{-value} \ll 0.0001$) akan memicu alert terus-menerus (*Alert Fatigue*).
* **Solusi**: Jangan bergantung secara eksklusif pada $p$-value jika $N$ sangat besar. Kombinasikan uji hipotesis dengan ukuran efek (*effect size*) seperti Wasserstein Distance atau Normalized Mean Absolute Difference.

### 10.3 Troubleshooting Playbook: Debugging Unidentified Prediction Drift

```
[ALERT: Model Output Drift Detected on Predict_Service_Fraud]
                           │
                           ▼
          Apakah terjadi lonjakan drastis pada Data Quality?
          - Cek: Missing values, Out-of-range categorical, Type mismatches
         ┌─────────────────┴─────────────────┐
        YES                                 NO
         │                                   │
         ▼                                   ▼
[Root Cause: Upstream Pipeline Bug]    Periksa Univariate Feature Drifts
- Bug pada upstream ETL/Payload       - Identifikasi Top-K fitur dengan PSI > 0.25
- Cek schema registry Kafka                        │
- Rollback upstream payload deploy                 ▼
                                      Apakah Drift hanya pada 1-2 fitur eksternal?
                                     ┌─────────────┴─────────────┐
                                    YES                         NO
                                     │                           │
                                     ▼                           ▼
                   [Root Cause: External Shock]    [Root Cause: Macro Trend / Concept Drift]
                   - Misal: Vendor API rusak,      - Perubahan preferensi makro pasar
                     Gempa bumi, Kebijakan Bank.   - Solusi: Trigger full offline retraining
                   - Tindakan: Masking fitur       - Evaluasi arsitektur model baru
                     atau fallback ke default
```

---

## 11. Best Practices (Production Checklist)

### Drift Detection Setup
- [ ] Batas binning kuantil baseline disimpan permanen bersama artefak model (bukan dihitung ulang saat inferensi).
- [ ] Drift multi-metrik diterapkan (kombinasi PSI untuk kategorikal/binning dan Wasserstein Distance untuk numerik).
- [ ] Telemetri payload inferensi menggunakan identifier idempotent (`prediction_id`, `trace_id`).
- [ ] Window evaluasi disesuaikan dengan siklus alami bisnis (misal: siklus musiman 24 jam untuk menghindari alarm palsu akibat perbedaan aktivitas siang/malam).

### Performance & Latency Safeguards
- [ ] Engine inferensi **tidak pernah** mengeksekusi perhitungan statistik secara sinkron di thread utama.
- [ ] Pengiriman log inferensi dioptimalkan menggunakan Apache Kafka atau Ring Buffer berbasis Shared Memory.
- [ ] Telemetry sampler dikonfigurasi secara adaptif: 100% pada *cold start*, turun ke 5-10% saat traffic stabil tinggi.

### Model Governance & Security
- [ ] Model binary memiliki *Cryptographic Signature* (menggunakan Cosign/Sigstore) sebelum di-deploy ke cluster.
- [ ] Model Lineage memetakan setiap model version ke Git commit SHA dataset, hyperparameter, dan dependensi Python runtime (SBOM).
- [ ] Enkripsi data-at-rest dan data-in-transit aktif untuk seluruh log telemetri guna mematuhi undang-undang privasi (GDPR/UU PDP).
- [ ] Model Cards terdokumentasi secara terprogram mencakup *intended use cases*, limitasi, serta hasil uji bias/fairness.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline deteksi drift asinkron berbasis streaming simulasi dan sistem validasi model lineage. Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── config.py
├── baseline_generator.py
├── drift_engine.py
├── test_stream.py
└── test_drift_pipeline.py
```

### File 1: `hands-on/m02/config.py`
```python
from pydantic import BaseModel

class MonitoringConfig(BaseModel):
    psi_warning: float = 0.1
    psi_critical: float = 0.25
    sample_window_size: int = 1000
    features_numeric: list[str] = ["tenure_months", "monthly_charges", "network_usage_gb"]
    features_categorical: list[str] = ["contract_type", "payment_method"]

CONFIG = MonitoringConfig()
```

### File 2: `hands-on/m02/baseline_generator.py`
```python
import numpy as np
import pandas as pd
import json

def generate_and_save_baseline(output_path: str = "baseline_data.parquet", meta_path: str = "bins_metadata.json"):
    np.random.seed(42)
    n = 20_000

    data = {
        "tenure_months": np.random.gamma(shape=2.0, scale=12.0, size=n).clip(1, 72),
        "monthly_charges": np.random.normal(loc=65.0, scale=20.0, size=n).clip(15, 150),
        "network_usage_gb": np.random.exponential(scale=100.0, size=n).clip(0, 1000),
        "contract_type": np.random.choice(["month-to-month", "one-year", "two-year"], size=n, p=[0.5, 0.3, 0.2]),
        "payment_method": np.random.choice(["credit_card", "bank_transfer", "e-wallet"], size=n, p=[0.4, 0.4, 0.2])
    }
    df = pd.DataFrame(data)
    df.to_parquet(output_path)

    # Ekstraksi dan bekukan kuantil
    metadata = {}
    for num_col in ["tenure_months", "monthly_charges", "network_usage_gb"]:
        quantiles = np.linspace(0, 100, 11)
        b_edges = np.percentile(df[num_col], quantiles)
        b_edges[0] = -np.inf
        b_edges[-1] = np.inf
        metadata[num_col] = b_edges.tolist()

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Baseline data tersimpan di {output_path}")
    print(f"Kuantil baseline tersimpan di {meta_path}")

if __name__ == "__main__":
    generate_and_save_baseline()
```

### File 3: `hands-on/m02/drift_engine.py`
```python
import json
import numpy as np
import pandas as pd
from typing import Dict, Any

class ProductionDriftAnalyzer:
    def __init__(self, metadata_path: str):
        with open(metadata_path, "r") as f:
            self.bin_edges = {k: np.array(v) for k, v in json.load(f).items()}

    def evaluate_numerical_psi(self, feature_name: str, current_stream: np.ndarray) -> float:
        if feature_name not in self.bin_edges:
            raise KeyError(f"Fitur {feature_name} tidak ditemukan pada metadata kuantil.")

        bins = self.bin_edges[feature_name]
        
        # Hitung distribusi frekuensi
        cur_counts, _ = np.histogram(current_stream, bins=bins)
        
        # Karena kuantil baseline dibagi 10 bin simetris, frekuensi ideal baseline = 10% per bin
        ref_pct = np.full(len(bins) - 1, 1.0 / (len(bins) - 1))
        
        eps = 1e-4
        cur_pct = (cur_counts / len(current_stream)) + eps
        cur_pct /= np.sum(cur_pct)

        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
        return float(psi)

    def evaluate_categorical_psi(self, baseline_cats: pd.Series, current_cats: pd.Series) -> float:
        categories = baseline_cats.unique()
        ref_counts = baseline_cats.value_counts(normalize=True)
        cur_counts = current_cats.value_counts(normalize=True)

        eps = 1e-4
        psi = 0.0
        for cat in categories:
            r = ref_counts.get(cat, eps)
            c = cur_counts.get(cat, eps)
            psi += (c - r) * np.log(c / r)
        return float(psi)
```

### File 4: `hands-on/m02/test_drift_pipeline.py`
```python
"""
Eksekusi end-to-end integration test untuk memvalidasi performa detektor drift.
"""
import numpy as np
import pandas as pd
from baseline_generator import generate_and_save_baseline
from drift_engine import ProductionDriftAnalyzer
from config import CONFIG

def run_integration_pipeline():
    print("[1] Membangun baseline acuan...")
    generate_and_save_baseline()

    print("[2] Menginisialisasi Drift Analyzer...")
    analyzer = ProductionDriftAnalyzer("bins_metadata.json")
    baseline_df = pd.read_parquet("baseline_data.parquet")

    print("[3] Mensimulasikan Data Ingestion Normal...")
    normal_stream = np.random.normal(loc=65.0, scale=20.0, size=CONFIG.sample_window_size).clip(15, 150)
    psi_normal = analyzer.evaluate_numerical_psi("monthly_charges", normal_stream)
    print(f"-> PSI Normal Stream: {psi_normal:.4f}")
    assert psi_normal < CONFIG.psi_warning, "False positive terdeteksi pada normal stream!"

    print("[4] Mensimulasikan Data Ingestion Mengalami Drift (Inflasi Tagihan)...")
    drifted_stream = np.random.normal(loc=95.0, scale=25.0, size=CONFIG.sample_window_size).clip(15, 150)
    psi_drifted = analyzer.evaluate_numerical_psi("monthly_charges", drifted_stream)
    print(f"-> PSI Drifted Stream: {psi_drifted:.4f}")
    assert psi_drifted >= CONFIG.psi_critical, "Gagal mendeteksi critical drift!"

    print("[5] Evaluasi Categorical Drift...")
    drifted_contracts = pd.Series(np.random.choice(["month-to-month", "one-year", "two-year"], 
                                                   size=1000, p=[0.9, 0.05, 0.05]))
    psi_cat = analyzer.evaluate_categorical_psi(baseline_df["contract_type"], drifted_contracts)
    print(f"-> PSI Categorical Drift: {psi_cat:.4f}")
    assert psi_cat > CONFIG.psi_warning, "Gagal mendeteksi categorical drift!"

    print("\n[SUCCESS] Semua assertion lolos. Pipeline produksi siap digunakan.")

if __name__ == "__main__":
    run_integration_pipeline()
```

---

## 13. Exercise

### Level Easy
Tuliskan fungsi Python `verify_feature_schema(incoming_payload: dict, expected_schema: dict) -> tuple[bool, list[str]]` yang memvalidasi apakah tipe data dan keberadaan setiap key dari dictionary inferensi produksi sesuai dengan schema yang ditentukan tanpa menggunakan library eksternal. Kembalikan error list lengkap jika terjadi anomali schema (Pipeline Drift).

### Level Medium
Buatlah algoritma *Adaptive Reservoir Sampling* berbasis kelas `StreamingReservoirSampler` yang dapat menampung maksimal $K=5000$ sampel dari infinite streaming generator. Sampel yang tersimpan harus mempertahankan representasi distribusi statistik yang tidak bias (*uniform random distribution*) terhadap keseluruhan data yang telah melintas, dengan footprint memory yang konstan $O(K)$.

### Level Hard
Implementasikan algoritma **Maximum Mean Discrepancy (MMD)** dengan Radial Basis Function (RBF) kernel secara tervektorisasi penuh (menggunakan PyTorch atau NumPy murni) untuk mengevaluasi multivariate data drift pada embedding 128 dimensi yang dihasilkan oleh model Deep Learning:
$$\text{MMD}^2(X, Y) = \frac{1}{m^2} \sum_{i,j} k(x_i, x_j) - \frac{2}{mn} \sum_{i,j} k(x_i, y_j) + \frac{1}{n^2} \sum_{i,j} k(y_i, y_j)$$
Optimalkan fungsi tersebut agar komputasi matriks jarak Euclidean ($N \times N$) tidak menghasilkan *Out Of Memory* (OOM) pada sampel batch sebesar $N=20.000$.

---

## 14. Challenge (Studi Kasus Nyata)

### Arsitektur Zero-Latency Governance & Delayed Ground Truth Reconciler

**Skenario**:
Anda ditunjuk sebagai Principal MLOps Engineer di perusahaan Ride-Hailing global. Anda memiliki model *Dynamic Pricing Engine* yang melayani 50.000 request per detik pada jam sibuk. 
Kondisi operasional yang harus dipenuhi:
1. **SLA Latensi**: Waktu inferensi model (termasuk logging telemetri) tidak boleh melebihi **8 milidetik (p99)**.
2. **Delayed Ground Truth**: Efektivitas tarif (*conversion rate* / apakah pengguna menerima harga tersebut) baru diketahui setelah 15 menit, sedangkan margin laba bersih baru diketahui setelah 48 jam pasca rekonsiliasi data mitra pengemudi.
3. **Regulasi Kepatuhan Transportasi**: Anda diwajibkan oleh regulator pemerintah untuk membuktikan bahwa model tidak melakukan diskriminasi harga berdasarkan area/zona demografis sensitif secara real-time. Jika disparitas rasio harga terhadap jarak melampaui ambang batas 15% antar-zona, sistem harus melakukan failover otomatis ke harga standar berbasis regulasi dalam waktu kurang dari 30 detik.

**Tugas Arsitektur**:
Rancang arsitektur produksi lengkap (diagram komponen sistem dan dokumen spesifikasi teknis) yang mencakup:
- Topologi telemetri data dari level Envoy proxy sidecar hingga streaming broker.
- Arsitektur stateful stream processing untuk mendeteksi *Concept Drift* tanpa label instan.
- Mekanisme automated fallback circuit breaker berbasis *Statistical Fairness Constraints*.
- Audit trail lineage menggunakan OpenLineage dan penyimpanan cold-storage immutable compliant.

*(Sajikan rancangan Anda dalam format desain arsitektur teknis yang siap ditinjau oleh Engineering Review Board).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)

1. Apa perbedaan matematis paling mendasar antara *Covariate Shift* dan *Concept Drift*?
2. Mengapa metrik *Population Stability Index* (PSI) membutuhkan nilai smoothing epsilon ($\epsilon$) pada formulasinya?
3. Pada pengujian Kolmogorov-Smirnov (KS) dua sampel, apa arti dari nilai $p\text{-value} = 0.0002$ terhadap hipotesis nol ($H_0$) pada tingkat signifikansi $\alpha = 0.01$?
4. Mengapa logging payload inferensi secara sinkron (*synchronous HTTP/DB calls*) di dalam inference engine dianggap sebagai *anti-pattern* pada sistem high-throughput?
5. Sebutkan dua komponen utama yang harus dicatat oleh OpenLineage untuk memastikan auditability pada fase pelatihan model!

### Bagian 2: Intermediate (Analisis Sistem & Algoritma)

6. Mengapa pada sampel pengujian berjumlah sangat besar ($N > 1.000.000$), uji KS lebih sering memicu alarm drift dibandingkan dengan Wasserstein Distance?
7. Jelaskan bagaimana *Entropy Loss* atau *Prediction Confidence Distribution* dapat digunakan sebagai proksi (*proxy metric*) untuk mendeteksi *concept drift* ketika ground-truth labels mengalami keterlambatan yang signifikan!
8. Apa kelemahan utama dari binning *Equal-Width* dibandingkan dengan binning *Equal-Frequency (Quantiles)* saat menghitung PSI pada data yang memiliki ekor distribusi panjang (*heavy-tailed distribution*)?
9. Dalam konteks keamanan model governance, bagaimana cara mengamankan artefak bobot model (`.onnx` atau `.safetensors`) dari serangan poisoning atau injeksi kode menggunakan Cosign/Sigstore?
10. Bagaimana algoritma *Welford's Algorithm* membantu pemantauan statistik numerik kontinu dalam konteks streaming data real-time?

### Bagian 3: Production Scenarios (Troubleshooting Kasus Riil)

#### Skenario Kasus 1: "The Ghost Drift Alert"
Dua minggu setelah peluncuran model rekomendasi e-commerce, tim operasional menerima alarm kritis: metrik PSI pada fitur `user_device_ip` melonjak dari 0.02 menjadi 0.85. Namun, saat tim Data Scientist memeriksa performa model (CTR dan konversi), metrik bisnis justru mencatatkan rekor tertinggi tanpa penurunan sedikit pun.  
*Pertanyaan*: Apa kemungkinan akar masalah teknis dari alarm drift ini, dan tindakan perbaikan apa yang harus diterapkan pada sistem monitoring?

#### Skenario Kasus 2: "Silent Degradation on Loan Approval"
Sebuah model persetujuan kredit mikro otomatis berbasis XGBoost menunjukkan metrik PSI yang stabil (< 0.05) pada semua fitur selama 6 bulan berturut-turut. Tidak ada satu pun peringatan data drift yang menyala. Namun, setelah audit keuangan kuartalan dilakukan, tingkat *Non-Performing Loan* (NPL / kredit macet) melonjak hingga 400% dari baseline.  
*Pertanyaan*: Jelaskan jenis drift apa yang terjadi, mengapa sistem pemantauan berbasis PSI fitur masukan gagal mendeteksinya, dan bagaimana arsitektur monitoring harus dirancang ulang untuk mengantisipasi masalah ini ke depan!

#### Skenario Kasus 3: "Memory Leak pada Ingestion Sidecar"
Layanan inference service berbasis Kubernetes pod sering mengalami status `CrashLoopBackOff` akibat error `OOMKilled` (Out of Memory) setiap kali traffic melonjak di atas 20.000 QPS. Tim menemukan bahwa memory leak berasal dari sidecar agent yang bertugas mengirimkan telemetri JSON inferensi ke Apache Kafka.  
*Pertanyaan*: Apa kelemahan arsitektur pada sidecar agent tersebut, dan bagaimana Anda mendesain ulang ingestion buffering layer untuk menjamin stabilitas memori pod tanpa kehilangan data inferensi?

---

## 16. Summary

1. **Observabilitas Berkelanjutan vs Monitoring Statis**: Monitoring tradisional hanya mengamati metrik infrastruktur (CPU, Memori, Latensi). Observabilitas MLOps melacak integritas matematika dan probabilitas data ($P(X)$, $P(Y|X)$, $P(Y)$) di sepanjang siklus hidup model.
2. **Kesesuaian Algoritma Drift**:
   - **PSI**: Sangat baik untuk fitur kategorikal atau numerik diskret; sensitif terhadap pemilihan strategi binning.
   - **KS-Test**: Unggul dalam mendeteksi perubahan bentuk kumulatif (CDF) data kontinu, namun rentan *false-alarm* pada ukuran sampel besar.
   - **Wasserstein Distance**: Memberikan metrik jarak absolut yang stabil, mulus, dan tidak terdistorsi oleh ukuran sampel masif.
3. **Delayed Ground Truth Mitigation**: Ketika label aktual tertunda berhari-hari, pantau proksi performa seperti *Prediction Entropy Distribution*, *Feature Attribution Shift* (menggunakan SHAP values windowing), dan *Unsupervised Representation Clustering*.
4. **Governance yang Dapat Diaudit**: Model governance di level enterprise membutuhkan otomatisasi immutable: penandatanganan kriptografis pada artefak model, pencatatan lineage end-to-end melalui OpenLineage, dan pemantauan kepatuhan berbasis regulasi (seperti mitigasi bias demografis) yang terintegrasi langsung ke dalam *CI/CD/CT (Continuous Training)* pipelines.