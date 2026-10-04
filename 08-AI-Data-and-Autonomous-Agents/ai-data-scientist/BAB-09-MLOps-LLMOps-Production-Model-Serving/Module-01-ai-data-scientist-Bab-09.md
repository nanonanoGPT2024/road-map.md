# Kurikulum: AI Data Scientist (Track 08: AI-Data and Autonomous Agents)
## Bab 09: MLOps, LLMOps, & Production Model Serving
### Modul 01: Arsitektur Model Serving Skala Produksi, Drift Detection, & Continuous Feedback Loop

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Mendesain & Mengimplementasikan** arsitektur *inference serving engine* terisolasi berlatensi rendah ($P99 < 50\text{ ms}$) menggunakan FastAPI dan abstraction layer inference C++ (ONNX Runtime / TensorRT).
*   **Mengembangkan Engine Deteksi Drift Otomatis** pada lingkungan streaming dan micro-batch dengan kalkulasi metrik statistik: *Population Stability Index* (PSI) dan *Two-sample Kolmogorov-Smirnov* (KS) Test secara terprogram.
*   **Membangun Asynchronous Observability Pipeline** berbasis OpenTelemetry dan Prometheus metrics untuk menangkap inferensi input-output tanpa menambah latency overhead pada core serving path.
*   **Merancang Strategi Mitigasi & Fallback Failure** saat mendeteksi anomali payload, kegagalan memory GPU (*Out-of-Memory / OOM*), dan *silent predictive degradation* secara otomatis via Circuit Breaker pattern.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Model machine learning di lingkungan riset (Jupyter Notebook) beroperasi dalam ruang tertutup dan statis: data pelatihan bersifat deterministik, batch size seragam, dan tidak ada konkurensi. Di lingkungan produksi, model machine learning bukanlah artefak statis melainkan **komponen komputasi stateful yang rentan terhadap degradasi entropy data**.

```
            LINGKUNGAN RISET                      LINGKUNGAN PRODUKSI
       ┌────────────────────────┐             ┌─────────────────────────┐
       │   Static Clean Data    │             │   Dirty Streaming Data  │
       │           ▼            │             │            ▼            │
       │   Offline Evaluation   │             │   Dynamic Concurrency   │
       │    (Accuracy, ROC)     │             │    Latency & Memory     │
       │           ▼            │             │            ▼            │
       │      Saved Model       │             │ Silent Predictive Decay │
       │       (.pkl/.pt)       │             │   (Data/Concept Drift)  │
       └────────────────────────┘             └─────────────────────────┘
```

#### Paradigma Serving: MLOps vs. LLMOps
1. **Classical MLOps Serving**: Berfokus pada throughput terprediksi, model tabular/vision/NLP berukuran tetap ($<2\text{ GB}$), deterministik, latensi dalam satuan milidetik ($1\text{ ms} - 50\text{ ms}$). Beban komputasi didominasi oleh operasi *matrix multiplication* standar (BLAS/cuBLAS) dengan memory footprint yang stabil.
2. **LLMOps Serving**: Berfokus pada dinamika *autoregressive generation*, non-deterministik, model raksasa ($7\text{B} - 70\text{B}+$ parameter), latensi dalam hitungan detik (*Time-to-First-Token* / TTFT dan *Inter-Token-Latency* / ITL). Bottleneck utama bergeser dari compute-bound ke *memory-bandwidth bound* akibat alokasi memori dinamis untuk KV-Cache (*PagedAttention*).

#### Taksonomi Degradasi Prediktif (Model Drift)
Model produksi mengalami degradasi melalui tiga vektor perubahan probabilitas bersama (*joint probability distribution*) $P(X, Y) = P(X) \cdot P(Y|X)$:
*   **Covariate Shift (Data Drift)**: Perubahan pada distribusi fitur input $P(X)$, sementara hubungan kondisional $P(Y|X)$ tetap konstan. *Contoh: Perubahan demografi pengguna aplikasi e-commerce.*
*   **Concept Drift**: Perubahan pada pemetaan relasi fungsional target $P(Y|X)$, meskipun distribusi input $P(X)$ tidak berubah. *Contoh: Pola belanja kartu kredit saat terjadi resesi global.*
*   **Prior Probability Shift**: Perubahan pada distribusi variabel target $P(Y)$, sementara representasi $P(X|Y)$ tidak berubah.

---

### 3. Why It Matters (Dampak di Dunia Nyata & Enterprise)

Kegagalan sistem software konvensional biasanya menghasilkan *HTTP 500 Internal Server Error* yang mudah tertangkap oleh *Application Performance Monitoring* (APM). Sebaliknya, **kegagalan machine learning di produksi bersifat senyap (*silent failure*)**:
*   Sistem tetap mengembalikan kode *HTTP 200 OK*, latensi stabil di angka $15\text{ ms}$, penggunaan CPU/GPU normal.
*   Namun, model skor kredit tiba-tiba meloloskan 80% pinjaman berisiko tinggi karena adanya perubahan pola distribusi pendapatan pasca-regulasi perbankan baru (Covariate Shift).
*   **Financial & Reputational Risk**: Pada industri finansial atau kesehatan, kegagalan menangkap penurunan performa model selama 48 jam dapat mengakibatkan jutaan dolar kerugian pinjaman macet (*default rate*) atau salah diagnosis klinis massal.

Tantangan enterprise mencakup kepatuhan regulasi (seperti *EU AI Act* dan *SR 11-7 Model Risk Management Guidance* di US) yang mewajibkan audit trail komprehensif, deteksi bias berkelanjutan, serta arsitektur pemulihan (*disaster recovery & model rollback*) terotomatisasi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur serving decoupled berlatensi rendah dengan *asynchronous drift detection telemetry loop*:

```
                                  KLIEN (Web / Mobile / Microservice)
                                                  │
                                                  │ (1) Inbound Request (HTTPS / gRPC)
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY / INGRESS CONTROLLER                                │
│                   (Rate Limiting, TLS Termination, Auth, Routing)                      │
└───────────────────────────────────┬────────────────────────────────────────────────────┘
                                    │
                                    │ (2) Internal Dispatch
                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          INFERENCE SERVING RUNTIME (FastAPI)                           │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────────────────┐  │
│  │   Input Sanitization   │  │ Optimized Inference C++│  │   Zero-Copy Prometheus   │  │
│  │   & Schema Validation  │─►│ (ONNX Runtime / vLLM)  │─►│   Telemetry Extraction   │  │
│  │   (Pydantic / Rust)    │  │ (Dynamic Batching Engine)│ │ (Counters, Histograms)   │  │
│  └────────────────────────┘  └────────────────────────┘  └─────────────┬────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┼───────────────┘
                                    │                                    │
           (3) Response (HTTP 200)  │                                    │ (4) Telemetry Push
                  P99 < 50ms        │                                    ▼
                                    │                      ┌───────────────────────────┐
                                    ▼                      │ Prometheus Metric Scraper │
                            KLIEN MENERIMA HASIL           └─────────────┬─────────────┘
                                                                         │
                                                                         ▼
                                    ┌──────────────────────────────────────────────────┐
                                    │ Grafana Dashboard & Prometheus AlertManager      │
                                    └──────────────────────────────────────────────────┘

     ┌───────────────────────────────────────────────────────────────────────────┐
     │                     ASYNC TELEMETRY WORKER POOL                           │
     │  (5) Low-Priority Non-Blocking Feature Logging via In-Memory Buffer / Queue│
     └──────────────────────────────────────┬────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               EVENT BROKER (Apache Kafka)                              │
│                    Topic: 'model-telemetry-inferences-v1'                              │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DRIFT DETECTION MICROSERVICE                              │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Sliding Window Accumulator (e.g., Last 10,000 requests)                          │  │
│  │ Baseline Reference Distribution (Retrieved from Feature Store / Cold Storage)    │  │
│  │ Statistical Calculators:                                                         │  │
│  │   - Population Stability Index (PSI) per Continuous & Categorical Feature        │  │
│  │   - Two-Sample Kolmogorov-Smirnov (KS) Test per Feature                          │  │
│  └────────────────────────────────────────┬─────────────────────────────────────────┘  │
└───────────────────────────────────────────┼────────────────────────────────────────────┘
                                            │
               ┌────────────────────────────┴───────────────────────────┐
               │                                                        │
               ▼ (Jika PSI > 0.2 atau KS p-val < 0.01)                  ▼ (Status Normal)
┌───────────────────────────────────────────┐         ┌──────────────────────────────────┐
│        MODEL ORCHESTRATION ENGINE         │         │      TELEMETRY DATA LAKE         │
│             (Airflow / Kubeflow)          │         │    (Parquet on Ceph / S3)        │
│  - Memicu Pipeline Retraining Otomatis    │         │  - Gold Dataset untuk Next Run   │
│  - Alerting Slack / PagerDuty P1          │         └──────────────────────────────────┘
└───────────────────────────────────────────┘
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Dynamic Batching Engine
Pada model serving modern (misal Triton Inference Server atau vLLM), request dari ribuan client tidak dieksekusi secara individual satu per satu ($Batch=1$), karena overhead perpindahan kernel CUDA dan *memory bus throughput* akan mendominasi eksekusi.
*   **Dynamic Batching Scheduler** menahan request masuk dalam antrean buffer selama rentang waktu tertentu ($T_{delay}$, misal $2\text{ ms}$) atau sampai kapasitas batch tercapai ($Max_{batch}$, misal $64$).
*   Request digabungkan menjadi single tensor, diproses dalam satu siklus GPU matrix-multiplication, kemudian di-*slice* kembali untuk dikirimkan ke masing-masing client via mapping request-ID.

#### Landasan Matematis Drift Detection

##### 1. Population Stability Index (PSI)
Digunakan untuk mengukur deviasi distribusi probabilitas dari populasi *Actual* ($A$) terhadap populasi *Reference / Expected* ($E$).
Dataset di-binning menjadi $B$ interval (biasanya 10 desil berbasis quantil referensi):

$$\text{PSI} = \sum_{b=1}^{B} \left( P(A_b) - P(E_b) \right) \times \ln\left( \frac{P(A_b)}{P(E_b)} \right)$$

*Di mana:*
*   $P(A_b) = \frac{\text{Jumlah sampel aktual di bin } b}{\text{Total sampel aktual}}$
*   $P(E_b) = \frac{\text{Jumlah sampel referensi di bin } b}{\text{Total sampel referensi}}$

*Interpreting Thresholds:*
*   $\text{PSI} < 0.1$: **No Significant Distribution Change**. Model tetap beroperasi normal.
*   $0.1 \le \text{PSI} \le 0.2$: **Moderate Shift**. Muncul indikasi drift. Trigger sistem logging tingkat tinggi.
*   $\text{PSI} > 0.2$: **Significant Drift**. Distribusi inferensi menyimpang signifikan dari data training. Trigger alert dan automated retraining.

##### 2. Two-Sample Kolmogorov-Smirnov (KS) Test
Digunakan untuk variabel kontinu guna memverifikasi apakah dua kumpulan data kontinu empiris berasal dari distribusi kontinu yang sama tanpa asumsi parametrik.
Statistik uji KS dihitung sebagai deviasi supremum dari dua *Empirical Cumulative Distribution Functions* (ECDF), $F_{ref}(x)$ dan $F_{act}(x)$:

$$D = \sup_{x} |F_{ref}(x) - F_{act}(x)|$$

Jika $p\text{-value} < \alpha$ (umumnya $\alpha=0.01$), maka hipotesis nol ($H_0$: Sampel berasal dari distribusi yang sama) ditolak. Hal ini membuktikan bahwa fitur input telah mengalami pergeseran statistik signifikan secara parametrik maupun non-parametrik.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi serving layer arsitektural lengkap berbasis:
1. **Clean Architecture Separation** (Schema, Engine, Telemetry, Drift).
2. **FastAPI** dengan non-blocking execution via worker queues.
3. **Statistical Drift Calculation Engine** komprehensif (PSI & KS-Test via `scipy`/`numpy`).
4. **Instrumentasi Prometheus Metrics**.

```python
"""
production_model_serving.py
--------------------------------------------------------------------------------
Production-Grade High-Throughput Serving Engine with Statistical Drift Detection
Author: Senior Technical Curriculum Architect
Platform: Python 3.10+, FastAPI, NumPy, SciPy, Prometheus
--------------------------------------------------------------------------------
"""

import abc
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
import numpy as np
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field, field_validator
from scipy import stats
from starlette.responses import Response

# --------------------------------------------------------------------------- #
# 1. LOGGING & OBSERVABILITY CONFIGURATION
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("ServingEngine")

PREDICTION_LATENCY = Histogram(
    "model_prediction_latency_seconds",
    "Latensi inferensi model dalam detik",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5],
)
INFERENCE_REQUEST_COUNT = Counter(
    "model_inference_requests_total",
    "Total request inferensi yang masuk",
    ["status"],
)
DRIFT_ALERT_COUNTER = Counter(
    "model_feature_drift_alerts_total",
    "Total anomali drift terdeteksi per fitur",
    ["feature_name", "metric"],
)

# --------------------------------------------------------------------------- #
# 2. CONTRACT DOMAIN: SCHEMAS & DTO
# --------------------------------------------------------------------------- #
class InferenceInput(BaseModel):
    transaction_amount: float = Field(..., gt=0.0, description="Nominal transaksi, harus bernilai positif.")
    account_age_days: float = Field(..., ge=0.0, description="Umur akun pengguna dalam hari.")
    risk_score_external: float = Field(..., ge=0.0, le=1.0, description="Skor risiko dari vendor eksternal [0-1].")
    device_trust_index: float = Field(..., ge=-1.0, le=1.0, description="Indeks kepercayaan device [-1 sampai 1].")

    @field_validator("transaction_amount")
    def validate_anomalous_upper_bound(cls, value: float) -> float:
        if value > 1_000_000_000.0:
            raise ValueError("Payload transaksi melampaui batas wajar operasional (1 Miliar).")
        return value

class PredictionResponse(BaseModel):
    prediction_id: str
    fraud_probability: float
    is_fraud: bool
    inference_time_ms: float
    model_version: str

# --------------------------------------------------------------------------- #
# 3. INTERFACES & RUNTIME MODEL INFERENCE ABSTRACTION
# --------------------------------------------------------------------------- #
class AbstractInferenceModel(abc.ABC):
    @abc.abstractmethod
    def predict(self, feature_matrix: np.ndarray) -> np.ndarray:
        """Eksekusi inferensi mentah pada runtime terisolasi."""
        pass

class MockOptimizedInferenceEngine(AbstractInferenceModel):
    """
    Mock engine yang mensimulasikan runtime C++ (ONNX Runtime / TensorRT)
    dengan waktu eksekusi sub-10ms.
    """
    def __init__(self, model_version: str = "v1.0.4"):
        self.model_version = model_version
        # Bobot deterministik sederhana untuk simulasi klasifikasi
        self._weights = np.array([0.00005, -0.001, 2.5, -1.8])
        self._bias = -0.5

    def predict(self, feature_matrix: np.ndarray) -> np.ndarray:
        if feature_matrix.ndim != 2 or feature_matrix.shape[1] != 4:
            raise ValueError(f"Dimensi matriks input tidak valid: {feature_matrix.shape}")
        
        # Logistik sigmoid
        raw_logits = np.dot(feature_matrix, self._weights) + self._bias
        probabilities = 1.0 / (1.0 + np.exp(-raw_logits))
        return probabilities

# --------------------------------------------------------------------------- #
# 4. DRIFT DETECTION ENGINE IMPLEMENTATION
# --------------------------------------------------------------------------- #
class StatisticalDriftEngine:
    def __init__(self, reference_data: np.ndarray, feature_names: List[str], num_bins: int = 10):
        if reference_data.shape[1] != len(feature_names):
            raise ValueError("Dimensi reference data tidak cocok dengan panjang feature_names")
        
        self.feature_names = feature_names
        self.num_bins = num_bins
        self.reference_data = reference_data
        
        # Pre-compute quantile thresholds dari reference dataset
        self.bin_edges: Dict[str, np.ndarray] = {}
        self.ref_distributions: Dict[str, np.ndarray] = {}
        self._initialize_reference_distributions()

    def _initialize_reference_distributions(self) -> None:
        epsilon = 1e-6
        for idx, feat_name in enumerate(self.feature_names):
            col_data = self.reference_data[:, idx]
            quantiles = np.linspace(0, 100, self.num_bins + 1)
            edges = np.percentile(col_data, quantiles)
            edges[0] = -np.inf
            edges[-1] = np.inf
            self.bin_edges[feat_name] = np.unique(edges)
            
            # Hitung proporsi reference
            counts, _ = np.histogram(col_data, bins=self.bin_edges[feat_name])
            prop = counts / len(col_data)
            prop = np.where(prop == 0, epsilon, prop)  # Laplacians-like smoothing
            self.ref_distributions[feat_name] = prop

    def compute_psi(self, feature_name: str, actual_values: np.ndarray) -> float:
        if len(actual_values) == 0:
            return 0.0

        epsilon = 1e-6
        edges = self.bin_edges[feature_name]
        ref_prop = self.ref_distributions[feature_name]

        actual_counts, _ = np.histogram(actual_values, bins=edges)
        actual_prop = actual_counts / len(actual_values)
        actual_prop = np.where(actual_prop == 0, epsilon, actual_prop)

        # Truncate mismatch jika unique bins menghasilkan dimensi dinamis
        min_len = min(len(ref_prop), len(actual_prop))
        ref_p = ref_prop[:min_len]
        act_p = actual_prop[:min_len]

        psi_value = np.sum((act_p - ref_p) * np.log(act_p / ref_p))
        return float(psi_value)

    def compute_ks_test(self, feature_name: str, actual_values: np.ndarray) -> Tuple[float, float]:
        feat_idx = self.feature_names.index(feature_name)
        ref_values = self.reference_data[:, feat_idx]
        statistic, p_value = stats.ks_2samp(ref_values, actual_values)
        return float(statistic), float(p_value)

# --------------------------------------------------------------------------- #
# 5. ASYNCHRONOUS DRIFT BUFFER & WORKER PIPELINE
# --------------------------------------------------------------------------- #
class AsyncInferenceBuffer:
    def __init__(self, drift_engine: StatisticalDriftEngine, buffer_size: int = 2000):
        self.drift_engine = drift_engine
        self.buffer_size = buffer_size
        self._internal_storage: List[List[float]] = []
        self._lock = asyncio.Lock()

    async def ingest(self, features: List[float]) -> None:
        async with self._lock:
            self._internal_storage.append(features)
            if len(self._internal_storage) >= self.buffer_size:
                data_snapshot = np.array(self._internal_storage)
                self._internal_storage.clear()
                # Offload statistical execution ke background thread non-blocking
                asyncio.create_task(self._process_drift_snapshot(data_snapshot))

    async def _process_drift_snapshot(self, snapshot: np.ndarray) -> None:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self._evaluate_drift, snapshot)

    def _evaluate_drift(self, snapshot: np.ndarray) -> None:
        logger.info(f"Mengevaluasi Drift pada {len(snapshot)} streaming inferences...")
        for idx, feat_name in enumerate(self.drift_engine.feature_names):
            actual_stream = snapshot[:, idx]
            
            # Hitung PSI
            psi_val = self.drift_engine.compute_psi(feat_name, actual_stream)
            # Hitung KS Test
            ks_stat, ks_pval = self.drift_engine.compute_ks_test(feat_name, actual_stream)

            logger.info(
                f"[Feature: {feat_name}] PSI: {psi_val:.4f} | KS-Stat: {ks_stat:.4f} | KS p-val: {ks_pval:.4e}"
            )

            # Assert threshold mitigasi
            if psi_val > 0.2:
                DRIFT_ALERT_COUNTER.labels(feature_name=feat_name, metric="PSI").inc()
                logger.warning(f"CRITICAL DRIFT DETECTED: {feat_name} PSI melampaui ambang batas (>0.2): {psi_val:.4f}")

            if ks_pval < 0.01:
                DRIFT_ALERT_COUNTER.labels(feature_name=feat_name, metric="KS").inc()
                logger.warning(f"SIGNIFICANT DISTRIBUTION SHIFT: {feat_name} KS p-value < 0.01: {ks_pval:.4e}")

# --------------------------------------------------------------------------- #
# 6. APPLICATION CONTAINER & API LAYER
# --------------------------------------------------------------------------- #
FEATURE_KEYS = ["transaction_amount", "account_age_days", "risk_score_external", "device_trust_index"]

# Inisialisasi Mock Baseline Distribution (Training Set)
np.random.seed(42)
SYNTHETIC_BASELINE = np.column_stack([
    np.random.exponential(scale=100.0, size=5000),       # transaction_amount
    np.random.uniform(low=1, high=1000, size=5000),       # account_age_days
    np.random.beta(a=2, b=5, size=5000),                 # risk_score_external
    np.random.normal(loc=0.5, scale=0.2, size=5000)      # device_trust_index
])

inference_engine = MockOptimizedInferenceEngine()
drift_engine = StatisticalDriftEngine(reference_data=SYNTHETIC_BASELINE, feature_names=FEATURE_KEYS)
drift_buffer = AsyncInferenceBuffer(drift_engine=drift_engine, buffer_size=100)

app = FastAPI(
    title="High-Performance ML Serving & Drift Platform",
    description="Enterprise inference architecture dengan statistical continuous monitoring",
    version="1.0.0",
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    response.headers["X-Inference-Engine-Latency"] = f"{duration * 1000:.2f}ms"
    return response

@app.post("/v1/predict", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_single(payload: InferenceInput, background_tasks: BackgroundTasks):
    t_start = time.perf_counter()
    try:
        raw_features = [
            payload.transaction_amount,
            payload.account_age_days,
            payload.risk_score_external,
            payload.device_trust_index,
        ]
        feature_matrix = np.array([raw_features], dtype=np.float32)

        # Eksekusi Inferensi Terisolasi
        probs = inference_engine.predict(feature_matrix)
        fraud_prob = float(probs[0])
        is_fraud = bool(fraud_prob > 0.5)

        t_elapsed = time.perf_counter() - t_start
        PREDICTION_LATENCY.observe(t_elapsed)
        INFERENCE_REQUEST_COUNT.labels(status="success").inc()

        # Non-blocking async queue payload logging
        await drift_buffer.ingest(raw_features)

        return PredictionResponse(
            prediction_id=f"tx_{time.time_ns()}",
            fraud_probability=round(fraud_prob, 4),
            is_fraud=is_fraud,
            inference_time_ms=round(t_elapsed * 1000, 2),
            model_version=inference_engine.model_version,
        )

    except ValueError as val_err:
        INFERENCE_REQUEST_COUNT.labels(status="validation_error").inc()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(val_err))
    except Exception as runtime_err:
        INFERENCE_REQUEST_COUNT.labels(status="internal_error").inc()
        logger.error(f"Inference failure encountered: {str(runtime_err)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference Engine Failure. Fallback circuit open.",
        )

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus Scraper Endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/healthz", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "HEALTHY", "model_loaded": True}
```

---

### 7. Edge Cases & Failure Modes (Operational Realities)

1.  **Memory Leak pada Dynamic C++ Runtime Wrappers**:
    *   *Gejala*: Alokasi memory container Kubernetes (RSS Memory) bertambah secara linear setelah jutaan inferensi meskipun garbage collection Python aktif.
    *   *Penyebab*: Terjadi *dangling pointer* atau *unreleased GPU context* pada interoperabilitas binding C++ (misal: ONNX Runtime C-API via ctypes/cython).
    *   *Mitigasi*: Jalankan serving instances di bawah *Gunicorn/Uvicorn worker recycling* (`--max-requests 50000 --max-requests-jitter 5000`) atau set Kubernetes memory limit keras dengan liveness probe restart otomatis.
2.  **Zero-Variance Feature pada Streaming Payload**:
    *   *Gejala*: Perhitungan PSI menghasilkan nilai `NaN` atau pembagian dengan nol ($DivisionByZero$).
    *   *Penyebab*: Pihak upstream interface mengalami kegagalan transmisi sehingga fitur bernilai konstan (misal: `account_age_days = 0.0` untuk semua entitas).
    *   *Mitigasi*: Terapkan *Laplacian-style continuous smoothing* ($\epsilon = 1e-6$) pada pembagian binning frekuensi dan sanitasi clipping deterministik.
3.  **Backpressure & Exhaustion Antrean Telemetri**:
    *   *Gejala*: Latensi response endpoint melonjak dari $10\text{ ms}$ ke $>2000\text{ ms}$ saat traffic spike.
    *   *Penyebab*: Worker background logging memblokir *Event Loop asyncio* karena *lock contention* antrean atau koneksi message broker Kafka yang timeout.
    *   *Mitigasi*: Implementasi *Drop-Tail Strategy* atau Circular Buffer: Buang telemetri observabilitas inferensi secara parsial jika kapasitas buffer logging melampaui $90\%$, demi memprioritaskan SLA response path pelanggan utama.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Pilihan Pendekatan A | Pilihan Pendekatan B | Analisis Trade-off Engineering |
| :--- | :--- | :--- | :--- |
| **Protokol Transport** | **REST (HTTP/1.1 JSON)** | **gRPC (HTTP/2 Protocol Buffers)** | REST memberikan kemudahan integrasi dan human-readable debugging, namun menimbulkan overhead serialisasi/deserialisasi teks JSON yang masif. gRPC memotong ukuran payload hingga $60\%$ dan CPU serialization time hingga $80\%$, namun membutuhkan setup gateway load-balancer HTTP/2 yang lebih kompleks. |
| **Model Runtime Engine**| **FastAPI + PyTorch Native** | **Triton Inference Server / ONNX** | PyTorch native mempermudah intervensi kode Python kustom, namun memiliki konkurensi buruk karena Python Global Interpreter Lock (GIL). Triton/ONNX Runtime C++ mengisolasi komputasi dari GIL, menyediakan memory-mapped execution, dan dynamic hardware acceleration (TensorRT), tetapi membatasi fleksibilitas eksekusi arbitrary code. |
| **Drift Computation** | **Real-Time Streaming Drift** | **Micro-Batch Windowing Drift** | Real-time streaming (misal: River / ADWIN) mendeteksi pergeseran per-transaksi tetapi memiliki sensitivitas false-positive yang sangat tinggi terhadap noise sesaat. Micro-batch windowing (mengakumulasi per $N$-ribu request) memberikan kestabilan distribusi statistik dan akurasi signifikansi $p$-value yang jauh lebih robust, dengan konsekuensi delay deteksi beberapa menit/jam. |

---

### 9. Best Practices & Standard Industri

*   **P99 Latency Guardrails**: Tetapkan SLA tegas pada edge: $P95 < 25\text{ ms}$, $P99 < 50\text{ ms}$. Jika degradasi internal engine melampaui batas SLA, alihkan request ke fallback model heuristik statis via *Circuit Breaker* (misal: Hystrix pattern).
*   **Model Immutability & Model Registry**: Jangan pernah memuat artefak model langsung dari dynamic cloud storage path tanpa pin checksum. Gunakan hash registri (*SHA-256 integrity hash*) via MLflow Model Registry atau AWS SageMaker Model Registry untuk mencegah ketidaksesuaian artefak.
*   **Zero-Downtime Deployment Patterns**:
    *   *Shadow Deployment (Dark Launch)*: Duplikasi 100% traffic live ke model baru secara paralel tanpa mengembalikan outputnya ke user, semata-mata untuk mengukur kestabilan memori, latensi, dan drift di dunia nyata.
    *   *Canary Deployment*: Alihkan 2% traffic ke model v2. Pantau metrik drift dan error selama rentang $24\text{ jam}$. Naikkan bertahap menjadi 10%, 50%, hingga 100%.
*   **Telemetry Privacy (GDPR/PII Isolation)**: Lakukan hash/anonymize pada input payload sebelum didistribusikan ke pipeline evaluasi drift. Fitur seperti identitas nama, NIK, atau nomor telepon dilarang keras masuk ke drift calculation queue dalam bentuk *plaintext*.

---

### 10. Hands-on Lab Exercise: Implementasi Serving Resisten Drift

#### Skenario Kasus
Model Fraud Detection telah dideploy di cluster staging. Anda ditugaskan untuk:
1. Menjalankan engine serving di atas machine lokal.
2. Melakukan simulasi traffic normal sebanyak 100 request untuk membangun baseline stabil.
3. Menginjeksi anomali distribusi (*Covariate Shift Attack* pada fitur `transaction_amount`) secara masif.
4. Memvalidasi bahwa alert drift secara otomatis terpicu pada Prometheus Metrics endpoint.

#### Langkah 1: Persiapan Environtment
Pasang dependensi Python yang dibutuhkan:
```bash
pip install fastapi uvicorn numpy scipy prometheus_client pydantic requests
```

Simpan kode dari **Section 6** ke dalam file bernama `production_model_serving.py`.

#### Langkah 2: Jalankan Server Inferensi
Eksekusi server menggunakan Uvicorn:
```bash
uvicorn production_model_serving:app --host 0.0.0.0 --port 8000 --workers 1
```

#### Langkah 3: Eksekusi Test Script & Drift Injection Simulation
Buat file baru bernama `simulation_test.py` dan jalankan script berikut untuk mensimulasikan ledakan data drift:

```python
"""
simulation_test.py: Test bench traffic injection & automated assertion
"""
import random
import time
import requests

SERVER_URL = "http://127.0.0.1:8000/v1/predict"
METRICS_URL = "http://127.0.0.1:8000/metrics"

def run_simulation():
    print("--- [TAHAP 1] MENGIRIM NORMAL BASELINE INFERENCES (100 Request) ---")
    for _ in range(100):
        normal_payload = {
            "transaction_amount": float(random.expovariate(1 / 100.0)),
            "account_age_days": float(random.uniform(1, 1000)),
            "risk_score_external": float(random.betavariate(2, 5)),
            "device_trust_index": float(random.gauss(0.5, 0.2)),
        }
        res = requests.post(SERVER_URL, json=normal_payload)
        assert res.status_code == 200

    print("Baseline terkirim. Memeriksa metrik drift...")
    time.sleep(2)
    metrics_res = requests.get(METRICS_URL).text
    assert 'model_feature_drift_alerts_total' not in metrics_res or 'PSI' not in metrics_res
    print("STATUS: Aman. Tidak ada drift terdeteksi.")

    print("\n--- [TAHAP 2] INJEKSI DATA DRIFT: COVARIATE SHIFT PADA transaction_amount (100 Request) ---")
    # Melakukan shift eksponensial besar: mean loncat dari 100 menjadi 50,000 (Anomali Belanja)
    for _ in range(100):
        drifted_payload = {
            "transaction_amount": float(random.expovariate(1 / 50000.0) + 10000),
            "account_age_days": float(random.uniform(1, 1000)),
            "risk_score_external": float(random.betavariate(2, 5)),
            "device_trust_index": float(random.gauss(0.5, 0.2)),
        }
        res = requests.post(SERVER_URL, json=drifted_payload)
        assert res.status_code == 200

    print("Data terinjeksi. Menunggu pemrosesan drift background loop...")
    time.sleep(3)

    print("\n--- [TAHAP 3] VERIFIKASI METRIK PROMETHEUS ---")
    metrics_post_drift = requests.get(METRICS_URL).text
    print("\nSnapshot Output Prometheus Metrics:")
    for line in metrics_post_drift.split("\n"):
        if "model_feature_drift_alerts_total" in line:
            print(f"-> {line}")

    # Assertion Otomatis
    assert 'model_feature_drift_alerts_total{feature_name="transaction_amount",metric="PSI"}' in metrics_post_drift
    print("\n[SUCCESS]: Engine berhasil menangkap Covariate Shift secara otomatis!")

if __name__ == "__main__":
    run_simulation()
```

#### Tolok Ukur Keberhasilan (Acceptance Criteria)
1. **Zero Downtime Prediction**: Semua 200 request HTTP wajib mengembalikan status `200 OK` dengan response time header `X-Inference-Engine-Latency` di bawah batas toleransi ($<20\text{ ms}$).
2. **Deterministic Alert Assertion**: Console logging Uvicorn harus menampilkan log `CRITICAL DRIFT DETECTED` pada fitur `transaction_amount`.
3. **Metric Endpoint Integrity**: Scraper metric `GET /metrics` wajib mengekspos metrik `model_feature_drift_alerts_total{feature_name="transaction_amount",metric="PSI"}` bernilai $\ge 1.0$.