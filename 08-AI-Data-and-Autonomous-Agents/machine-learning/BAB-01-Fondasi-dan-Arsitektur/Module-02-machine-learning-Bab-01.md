# BAB 01: FONDASI DAN ARSITEKTUR
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Machine Learning

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain Arsitektur Sistem ML Produksi (Enterprise-Grade)**: Mengintegrasikan komponen *feature store*, *model registry*, *orchestration pipeline*, dan *low-latency serving engine* yang modular, *fault-tolerant*, dan terisolasi.
2. **Mengeliminasi Training-Serving Skew**: Menerapkan abstraksi data fitur ganda (*point-in-time correct join* untuk pelatihan offline dan *in-memory key-value lookup* sub-milidetik untuk inferensi online).
3. **Mengoptimalkan Throughput dan Latensi Inferensi**: Mengonversi model berbasis PyTorch/Scikit-Learn ke format serialisasi terkompilasi (*ONNX*, *TensorRT*), mengonfigurasi *dynamic batching*, serta memanfaatkan arsitektur inferensi multi-worker berbasis Triton Inference Server atau C++ runtime bindings.
4. **Mengimplementasikan Observabilitas dan Deteksi Degradasi**: Membangun mekanisme pemantauan telemetri real-time (*data drift*, *concept drift*, saturasi hardware, inferensi latensi p95/p99) menggunakan Prometheus, Grafana, dan Evidently/Whylogs.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Pemrograman Python Lanjutan**: Pemahaman mendalam tentang *concurrency* (`asyncio`, `multiprocessing`), GIL (*Global Interpreter Lock*), serta manajemen memori tingkat rendah (*garbage collection*, pointer C-extensions).
*   **Matematika & Dasar ML**: Aljabar linear komputasional (vektorisasi, operasi tensor), kalkulus multivariat (optimasi *gradient descent*), serta metrik evaluasi model (AUC-ROC, Log-Loss, PR-AUC, F1-Score).
*   **Containerization & Orchestration**: Docker multi-stage builds, arsitektur dasar Kubernetes (Pods, Services, StatefulSets, CRDs).
*   **Dasar Jaringan & Komunikasi Data**: Protokol gRPC vs REST, HTTP/2 multiplexing, serta serialisasi biner (Protocol Buffers, FlatBuffers, Apache Arrow).

---

### 3. Concept & Internal Architecture

Memindahkan machine learning dari eksperimen *Jupyter Notebook* ke sistem produksi skala enterprise membutuhkan transformasi paradigma: dari fokus berbasis model (*model-centric*) menjadi fokus berbasis rekayasa sistem (*system-centric*).

```
+---------------------------------------------------------------------------------------------------+
|                                   ENTERPRISE ML SYSTEM TOPOLOGY                                   |
+---------------------------------------------------------------------------------------------------+

   [ Batch Sources ]      [ Streaming Sources ]
   (Data Lake/S3)         (Kafka/Kinesis)
          |                      |
          v                      v
+---------------------------------------------------+
|               FEATURE STORE SYSTEM                |
|  +---------------------+  +--------------------+  |
|  |   Offline Storage   |  |   Online Storage   |  |
|  | (Parquet/Snowflake) |  |   (Redis/DynamoDB) |  |
|  +---------------------+  +--------------------+  |
+---------------------------------------------------+
          | Point-in-time                ^
          | Joins                        | Low-latency Lookups (<5ms)
          v                              |
+---------------------+        +--------------------+
| DISTRIBUTED TRAINING|        | REAL-TIME SERVING  |
|  (PyTorch/Ray Train)|        |  (Triton/FastAPI)  |
+---------------------+        +--------------------+
          |                              ^
          | Artifacts                    | Optimized Engines
          v                              | (ONNX/TensorRT)
+---------------------------------------------------+
|                   MODEL REGISTRY                  |
|          (MLflow/Weights & Biases/OCI)            |
+---------------------------------------------------+
          |                              |
          v                              v
+---------------------------------------------------+
|              OBSERVABILITY & FEEDBACK             |
|   (Prometheus, Evidently AI, Kafka Feedback Loop) |
+---------------------------------------------------+
```

#### Komponen Kunci Arsitektur Produksi:

1. **Feature Store (Dual-Storage Layer)**:
   * **Offline Store**: Berbasis format kolumnar (Apache Parquet, Delta Lake). Digunakan untuk melatih model secara masif dengan *point-in-time correctness* (mencegah kebocoran data masa depan / *data leakage*).
   * **Online Store**: Berbasis *in-memory* NoSQL (Redis, DragonflyDB, DynamoDB). Menyediakan *feature lookup* berlatensi sub-milidetik untuk inferensi *online*.
   * **Registry/Metadata Layer**: Sinkronisasi definisi transformasi data agar logika ekstraksi fitur antara fase training dan serving identik 100%.

2. **Model Compilation & Graph Optimization**:
   * Model standar Python (e.g., PyTorch `.pt` atau Scikit-Learn `.pkl`) bergantung pada runtime Python yang lambat akibat GIL.
   * Model diubah menjadi graf komputasi statis menggunakan **ONNX (Open Neural Network Exchange)** atau **NVIDIA TensorRT**. 
   * Optimasi graf mencakup:
     * *Layer Fusing* (misal: menggabungkan Convolution + BatchNorm + ReLU menjadi satu kernel eksekusi GPU).
     * *Constant Folding* (menghitung operasi bernilai statis saat kompilasi).
     * *Quantization* (FP32 dikonversi ke FP16 atau INT8 untuk memangkas *memory bandwidth* dan mempercepat siklus instruksi ALU/Tensor Core).

3. **Inference Execution Engine**:
   * Melakukan abstraksi eksekusi komputasi menggunakan server performa tinggi (misal: **Triton Inference Server**).
   * Fitur kritikal:
     * **Dynamic Batching**: Menggabungkan request inferensi individual yang datang bersamaan dalam rentang waktu beberapa mikrodetik menjadi satu batch komputasi untuk memaksimalkan paralelisasi hardware tanpa mengorbankan batas SLA latensi.
     * **Multi-Model Concurrency**: Menjalankan beberapa *instance* model secara simultan pada satu atau lebih GPU/CPU.
     * **Shared Memory (IPC)**: Komunikasi data inferensi antar-proses via POSIX/CUDA shared memory tanpa *serialization overhead*.

---

### 4. Why & What

| Dimensi | Kode Eksperimental (Notebook) | Arsitektur ML Produksi (Enterprise) |
| :--- | :--- | :--- |
| **Bentuk Artefak** | File `.ipynb`, `.pkl` non-standar | Image container teruji, artefak ONNX/TensorRT terversi di Registry |
| **Pipeline Data** | Script ad-hoc, Pandas *in-memory* | Streaming/Batch pipelines terkelola via Feature Store (Feast/Hopsworks) |
| **Penanganan State** | Memori lokal tidak terisolasi | Stateless inference worker, distributed cache terisolasi |
| **Latensi Eksekusi** | > 100ms (akibat Python GIL overhead) | < 10ms (engine kompilasi graf statis, zero-copy deserialization) |
| **Skalabilitas** | Terbatas pada RAM mesin lokal | Horizontal auto-scaling berbasis beban request (HPA di Kubernetes) |
| **Monitoring** | Evaluasi statis sekali jalan (e.g., test set) | Telemetri kontinu: *Data Drift*, *Concept Drift*, latency percentiles |

#### Mengapa Perlu Arsitektur Terstandarisasi?
Sistem ML bukan sekadar kode algoritma. Berdasarkan riset Sculley et al. (*Hidden Technical Debt in Machine Learning Systems*), kode ML inti hanya menyumbang sekitar 5% dari keseluruhan basis kode sistem produksi. Sisanya adalah infrastruktur konfigurasi, verifikasi data, ekstraksi fitur, manajemen sumber daya, penyajian model, dan pemantauan. 

Kegagalan membangun arsitektur yang kuat memicu:
* **Training-Serving Skew**: Perbedaan perilaku fitur di training vs serving akibat reimplementasi logika secara manual di backend API.
* **Silent Failures**: Model tidak melempar *exception error*, namun menghasilkan inferensi sampah karena distribusi data input telah bergeser (*covariate shift*).
* **Resource Exhaustion**: Memory leak pada GPU/CPU akibat alokasi tensor berulang tanpa pembersihan konteks yang benar.

---

### 5. How (Workflow Detail)

Alur kerja implementasi produksi terdiri dari 6 tahapan end-to-end:

```
[1. Ingestion] -> [2. Feature Store] -> [3. Train & Convert]
                                              |
[6. Monitor]   <- [5. Low-Latency Serve] <- [4. Register & Validate]
```

1. **Ingestion & Feature Sync**:
   * Stream ingestion (Kafka) menulis fitur real-time ke online store (Redis).
   * Batch ingestion mengagregasi data periodik ke offline lakehouse (Parquet/S3).
2. **Feature Retrieval (Point-in-Time)**:
   * Engine training mengambil fitur historis berdasarkan stempel waktu kejadian untuk menghindari *future data leakage*.
3. **Training & Compilation**:
   * Pelatihan model secara terdistribusi.
   * Ekspor graf komputasi ke format intermediate (ONNX).
   * Validasi matematis: Hasil inferensi ONNX harus identik dengan hasil inferensi PyTorch mentah hingga toleransi absolut $10^{-5}$.
4. **Registration & Automated Validation**:
   * Penyimpanan artefak di Model Registry (MLflow/S3).
   * Pengujian gerbang otomatis (*gatekeeper tests*): latensi p99, throughput minimum, dan batas performa metrik bisnis.
5. **Inference Deployment**:
   * Model dimuat ke dalam runtime teroptimasi.
   * Serving layer mengeksekusi request melalui gRPC dengan payload terkompresi.
6. **Continuous Observability**:
   * Metrik sistem diekspor ke Prometheus.
   * Payload input & output disampel secara asinkron ke Kafka topic untuk dianalisis oleh detektor drift.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima vs Dapur Rumah Tangga
* **Eksperimen ML (Dapur Rumah Tangga)**: Anda memasak satu porsi hidangan. Anda mengambil bahan langsung dari kulkas, memotongnya tanpa ukuran presisi, memasaknya, dan langsung menyajikannya. Pendekatan ini tidak bisa diskalakan untuk melayani 1.000 pelanggan dalam 1 jam.
* **Enterprise ML (Dapur Industri Restoran Bintang Lima)**: 
  * **Feature Store = *Mise en place***: Semua bahan telah dicuci, dipotong, dan ditakar sebelumnya di workstation khusus. Koki tinggal mengambil bahan yang siap pakai.
  * **ONNX/TensorRT = Mesin Khusus Industri**: Memotong tahapan manual menjadi siklus instan terotomasi.
  * **Dynamic Batching = Manajemen Oven**: Daripada memanggang 1 loyang pizza setiap kali pesanan masuk, oven pintar menunggu selama 5 milidetik untuk mengumpulkan hingga 8 loyang pizza sekaligus dan memanggangnya bersamaan tanpa membuat pelanggan pertama menunggu terlalu lama.

#### Diagram Internal: Dynamic Batching & Serving Queue
```
Client 1 ----Req A (t=0ms)----> [ Triton / Async Engine ]
Client 2 ----Req B (t=1ms)----> |  Queue: [A, B, C]    |
Client 3 ----Req C (t=2ms)----> |  (Max Batch Window:  |
                                |   5ms OR Size: 4)    |
                                +----------------------+
                                           |
                                [ Tensor Assembly ] -> Bentuk Batch Tensor: [3, Feature_Dim]
                                           |
                                  [ ONNX Execution ] -> Eksekusi Paralel (CUDA Cores)
                                           |
                                [ Tensor Splitter ] -> Pecah Response [A_out, B_out, C_out]
                                           |
Client 1 <---Resp A (t=7ms)----------------+
Client 2 <---Resp B (t=7ms)----------------+
Client 3 <---Resp C (t=7ms)----------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Kompilasi Sklearn/PyTorch ke ONNX Runtime Engine
Contoh ini mendemonstrasikan serialisasi model regresi PyTorch ke ONNX, diikuti dengan perbandingan eksekusi inferensi menggunakan C-accelerated ONNX Runtime.

```python
import time
import numpy as np
import onnxruntime as ort
import torch
import torch.nn as nn

# 1. Definisikan Model PyTorch Sederhana
class InferenceModule(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

input_dim = 64
hidden_dim = 128
model = InferenceModule(input_dim, hidden_dim)
model.eval()

# 2. Export ke Format ONNX
dummy_input = torch.randn(1, input_dim, dtype=torch.float32)
onnx_file_path = "model_artifact.onnx"

torch.onnx.export(
    model,
    dummy_input,
    onnx_file_path,
    input_names=["INPUT__0"],
    output_names=["OUTPUT__0"],
    dynamic_axes={
        "INPUT__0": {0: "batch_size"},
        "OUTPUT__0": {0: "batch_size"}
    },
    opset_version=17
)

# 3. Setup ONNX Runtime Session dengan Optimasi Penuh
sess_options = ort.SessionOptions()
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
sess_options.intra_op_num_threads = 4

session = ort.InferenceSession(onnx_file_path, sess_options, providers=["CPUExecutionProvider"])

# 4. Benchmark Inferensi (Batch Size = 32)
benchmark_payload = np.random.randn(32, input_dim).astype(np.float32)

# Benchmark PyTorch Native
with torch.no_grad():
    torch_payload = torch.from_numpy(benchmark_payload)
    start_pt = time.perf_counter()
    for _ in range(1000):
        _ = model(torch_payload)
    end_pt = time.perf_counter()

# Benchmark ONNX Runtime
ort_inputs = {"INPUT__0": benchmark_payload}
start_ort = time.perf_counter()
for _ in range(1000):
    _ = session.run(None, ort_inputs)
    end_ort = time.perf_counter()

print(f"PyTorch CPU 1000 iterasi: {(end_pt - start_pt) * 1000:.2f} ms")
print(f"ONNX Runtime 1000 iterasi: {(end_ort - start_ort) * 1000:.2f} ms")
```

#### B. Practical Example: Production-Grade High-Throughput Serving Microservice
Implementasi arsitektur inferensi berbasis FastAPI dengan koneksi non-blocking ke cache fitur (simulasi Online Feature Store) dan ONNX Runtime teroptimasi, lengkap dengan validasi skema via Pydantic v2 dan metrik Prometheus.

```python
import asyncio
from contextlib import asynccontextmanager
import time
from typing import List
import numpy as np
import onnxruntime as ort
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
import uvicorn

# Prometheus Instrumentation Metrics
REQ_LATENCY = Histogram(
    "inference_latency_seconds",
    "Model inference latency distribution",
    buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1]
)
PREDICTION_COUNTER = Counter(
    "predictions_total",
    "Count of prediction invocations",
    ["status"]
)

# Pydantic Schemas
class PredictionRequest(BaseModel):
    entity_id: str = Field(..., description="ID Entitas unik (misal: user_id)")
    dynamic_signals: List[float] = Field(..., min_length=4, max_length=4, description="Sinyal real-time konteks client")

class PredictionResponse(BaseModel):
    entity_id: str
    risk_score: float
    inference_time_ms: float

# Simulasi Feature Store Connector (Online Store Client)
class OnlineFeatureStoreClient:
    async def get_online_features(self, entity_id: str) -> np.ndarray:
        # Simulasi latensi async Redis read (sub-milidetik)
        await asyncio.sleep(0.001)
        # Mengembalikan 60 fitur agregasi yang telah dihitung sebelumnya
        return np.random.uniform(-1.0, 1.0, size=(60,)).astype(np.float32)

# Global State Container
class EngineState:
    session: ort.InferenceSession = None
    feature_store: OnlineFeatureStoreClient = None

state = EngineState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Lifespan: Load Model dan Init Connections
    sess_opt = ort.SessionOptions()
    sess_opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_opt.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    sess_opt.intra_op_num_threads = 2
    
    # Inisialisasi ONNX Runtime Engine
    state.session = ort.InferenceSession("model_artifact.onnx", sess_opt, providers=["CPUExecutionProvider"])
    state.feature_store = OnlineFeatureStoreClient()
    yield
    # Teardown logic
    del state.session

app = FastAPI(title="Production Inference Worker", lifespan=lifespan)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.post("/v1/predict", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_endpoint(payload: PredictionRequest):
    start_time = time.perf_counter()
    try:
        # 1. Asynchronous Feature Fetch dari Online Store
        online_feats = await state.feature_store.get_online_features(payload.entity_id)
        
        # 2. Gabungkan Fitur Online Store + Sinyal Input Request (Total: 64 fitur)
        request_feats = np.array(payload.dynamic_signals, dtype=np.float32)
        full_feature_vector = np.concatenate([online_feats, request_feats]).reshape(1, -1)
        
        # 3. Eksekusi Inferensi Teroptimasi (Sync execution dibungkus dalam loop terproteksi)
        # Menghindari blocking event loop jika model berat
        loop = asyncio.get_running_loop()
        ort_inputs = {"INPUT__0": full_feature_vector}
        
        raw_output = await loop.run_in_executor(
            None, 
            state.session.run, 
            None, 
            ort_inputs
        )
        
        pred_value = float(raw_output[0][0][0])
        
        # 4. Instrumentasi dan Response Assembly
        duration = time.perf_counter() - start_time
        REQ_LATENCY.observe(duration)
        PREDICTION_COUNTER.labels(status="success").inc()
        
        return PredictionResponse(
            entity_id=payload.entity_id,
            risk_score=pred_value,
            inference_time_ms=duration * 1000.0
        )
    except Exception as e:
        PREDICTION_COUNTER.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=f"Inference Engine Failure: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Real-Time Payment Fraud Detection System
* **Kebutuhan Bisnis**: Platform sistem pembayaran memproses **35.000 transaksi per detik (TPS)** pada jam puncak. Setiap otorisasi transaksi harus dievaluasi oleh model ML untuk mendeteksi penipuan dengan batas latensi ketat: **SLA end-to-end $\le$ 15ms pada $p99$**.

#### Bottleneck Awal:
1. Model Scikit-Learn RandomForest di-load melalui microservice Python Flask murni. Latensi inferensi berada pada rentang **60-80ms** akibat komputasi pohon keputusan yang tidak terparalelisasi di CPU dan GIL lock.
2. Penarikan fitur agregasi historis (misal: "Jumlah transaksi user dalam 1 jam terakhir") dilakukan via query SQL ke database relasional langsung, memicu *connection pool starvation* dan *query timeout*.

#### Solusi Arsitektur Produksi:
```
[ Payment Gateway ]
        |
        | (gRPC Request: txn_id, card_id, amount)
        v
[ Go API Gateway Layer ] 
        |
        +---> [ Redis Cluster ] (Feature Retrieval: Velocity features, card stats) [< 2ms]
        |
        +---> [ Triton Inference Cluster ] 
                    | (Dynamic Batching Engine: Batch Size=64, Max Queue Delay=2ms)
                    | (Model: LightGBM dikonversi ke ONNX FP16 Engine)
                    v
              Inferensi Tensor GPU/CPU Vectorized [< 3ms]
        |
        v
[ Response ke Payment Gateway ] (Total Latensi: 8 - 11ms pada p99)
        |
        | (Async Logging via Zero-Copy RingBuffer)
        v
[ Apache Kafka ] ---> [ Drift Detection / Evidently AI Engine ]
```

#### Hasil Terukur:
* Latensi inferensi $p99$ dipangkas dari **75ms menjadi 3.2ms**.
* Throughput per node meningkat **12x lipat**, memungkinkan perusahaan mengurangi armada kluster komputasi dari 80 node instans c5.4xlarge AWS menjadi hanya 12 node g4dn.xlarge, memangkas biaya infrastruktur bulanan hingga **62%**.
* Eliminasi total *training-serving skew* menggunakan *shared transformation module* di Feast Feature Store.

---

### 9. Trade-offs

Setiap keputusan arsitektur dalam sistem ML produksi melibatkan kompromi teknis yang signifikan:

| Parameter | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Batching Strategy** | **Dynamic Batching** | **Single Item Processing** | Dynamic batching melipatgandakan *system throughput* (QPS) hingga 5-10x, namun menambahkan latensi penalti mikro ($+1$ hingga $3\text{ ms}$) bagi request pertama yang masuk ke antrean. |
| **Presisi Model** | **FP32 (Full Precision)** | **INT8 (Quantized)** | INT8 memangkas jejak memori (*memory footprint*) hingga 75% dan melipatgandakan throughput, tetapi berisiko mengalami degradasi akurasi/F1-score jika teknik post-training quantization (PTQ) tidak dikalibrasi secara ketat. |
| **Komunikasi Protokol**| **gRPC (Protobuf)** | **REST (JSON)** | gRPC memangkas *network payload* dan waktu deserialisasi hingga 40-60% berkat format biner HTTP/2, namun memerlukan dependensi klien terkompilasi (*client stub*) dan lebih rumit diintegrasikan dengan edge router publik. |
| **Pipeline Pola Data** | **Synchronous Feature Fetch** | **Enriched Payload by Client**| Mengambil fitur di backend menjamin integritas fitur dan keamanan data, tetapi menambahkan latensi jaringan ke database online. Payload yang diperkaya oleh client meniadakan database lookups, tetapi membuka celah manipulasi data (*security spoofing*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Training-Serving Skew Akibat Perbedaan Imputasi Data
* **Gejala**: Model mencapai AUC 0.98 saat evaluasi offline, namun akurasi rill anjlok drastis (AUC ~0.55) segera setelah di-deploy ke lingkungan produksi.
* **Root Cause**: Tahap preprocessing saat training menggunakan `sklearn.impute.SimpleImputer` yang menghitung *mean* secara global pada seluruh dataset training. Di server produksi, logika inferensi menggunakan nilai default `0` atau logika buatan tangan yang berbeda saat menangani *missing values*.
* **Solusi**: Bungkus pipeline transformasi data ke dalam format serialisasi yang immutable (*Pipelines* yang diekspor ke ONNX bersamaan dengan estimatormu, atau gunakan *Feature Store Transform Functions* terpusat).

#### 2. Memory Leaks pada Long-Running Inference Workers
* **Gejala**: Penggunaan RAM/VRAM pod inference bertambah secara gradual hingga pod dimatikan paksa oleh sistem operasi (*OOMKilled* / Exit Code 137).
* **Root Cause**: Menyimpan riwayat inferensi atau logging tensor PyTorch/TensorFlow langsung ke dalam list Python tanpa memutus graf komputasi (contoh: lupa mengeksekusi `.detach().cpu().numpy()` atau `with torch.no_grad():`). Hal ini menyebabkan *directed acyclic graph* (DAG) komputasi tetap tersimpan di memori dan tidak bisa dibersihkan oleh Garbage Collector.
* **Solusi**: Jalankan runtime eksekusi inferensi di dalam konteks eksplisit tanpa pelacakan gradien. Gunakan `py-spy` atau `tracemalloc` untuk profiling memori:
  ```bash
  py-spy dump --pid <PID_WORKER>
  ```

#### 3. Thread Contention & GIL Bottlenecks
* **Gejala**: Menambah core CPU pada instance Kubernetes tidak meningkatkan throughput inferensi, malah latensi semakin memburuk.
* **Root Cause**: Terjadi *thread contention* ekstrem antara internal thread OpenMP/MKL dari library numerik (NumPy/ONNX) dengan multi-threading server ASGI Python (Uvicorn).
* **Solusi**: Batasi *intra* dan *inter-op parallelism* secara manual via environment variable sebelum engine di-load:
  ```bash
  export OMP_NUM_THREADS=1
  export OPENBLAS_NUM_THREADS=1
  export MKL_NUM_THREADS=1
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-deployment Gate (CI/CD Pipeline)
- [ ] Artefak model diekspor ke format non-komputasi graf Python murni (ONNX / TensorRT / TorchScript).
- [ ] Dilakukan uji regresi numerik: `np.allclose(pytorch_out, onnx_out, atol=1e-5)` bernilai `True`.
- [ ] Uji performa beban (*Stress Testing*) menggunakan tools benchmark (e.g., `triton-perf-analyzer` atau `Locust`) untuk memvalidasi batas kurva degradasi latensi p99.
- [ ] Pydantic / Protobuf schemas dikunci versinya (*strict semantic versioning*) untuk mencegah rusaknya kontrak data payload.

#### Infrastructure & Runtime Hardening
- [ ] Resource limits (CPU/Memory/GPU) pada Kubernetes Manifest didefinisikan secara presisi (mencegah *noisy neighbor problem*).
- [ ] Health probe dikonfigurasi terpisah: `/healthz/live` (cek alur proses worker) dan `/healthz/ready` (cek apakah model artifact sudah sukses dialokasikan ke memori GPU/RAM).
- [ ] Tidak melakukan eksekusi komputasi berat secara sinkron langsung di main thread event loop framework web.

#### Post-deployment Observability
- [ ] Instrumentasi metrik dasar: Throughput (RPS), Latensi inferensi (p50, p95, p99), Error Rate (5xx).
- [ ] Ekspor *Data Drift Metrics* menggunakan uji Kolmogorov-Smirnov atau Wasserstein Distance pada interval reguler (tiap 1 jam / 24 jam) membandingkan distribusi input produksi terhadap data baseline pelatihan.

---

### 12. Hands-on Practice

Buat dan simpan struktur file berikut di folder `hands-on/m02/`:

```
hands-on/m02/
├── Dockerfile
├── requirements.txt
├── generate_model.py
├── server.py
└── client_stress_test.py
```

#### Langkah 1: Siapkan `requirements.txt`
```text
fastapi>=0.110.0
uvicorn>=0.28.0
onnx>=1.15.0
onnxruntime>=1.17.0
torch>=2.2.0
numpy>=1.26.0
pydantic>=2.6.0
requests>=2.31.0
prometheus-client>=0.20.0
```

#### Langkah 2: Buat Pipeline Kompilasi `generate_model.py`
```python
import torch
import torch.nn as nn

class ProductionClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(16, 64),
            nn.BatchNorm1d(64),
            nn.SiLU(),
            nn.Linear(64, 32),
            nn.SiLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.network(x)

if __name__ == "__main__":
    model = ProductionClassifier()
    model.eval()
    
    # Generate random training state untuk dummy weights
    dummy_input = torch.randn(1, 16, dtype=torch.float32)
    
    torch.onnx.export(
        model,
        dummy_input,
        "production_model.onnx",
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input_tensor"],
        output_names=["probabilities"],
        dynamic_axes={
            "input_tensor": {0: "batch_size"},
            "probabilities": {0: "batch_size"}
        }
    )
    print("[SUCCESS] Production model exported successfully to production_model.onnx")
```

#### Langkah 3: Bangun Server Produksi `server.py`
```python
import asyncio
from contextlib import asynccontextmanager
import os
import time
import numpy as np
import onnxruntime as ort
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
import uvicorn

class ModelInferenceService:
    def __init__(self, model_path: str):
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.intra_op_num_threads = int(os.environ.get("ORT_INTRA_THREADS", "2"))
        
        self.session = ort.InferenceSession(
            model_path, 
            sess_options=opts, 
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def infer(self, features: np.ndarray) -> np.ndarray:
        return self.session.run(None, {self.input_name: features})[0]

service_container = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    service_container["inference"] = ModelInferenceService("production_model.onnx")
    yield
    service_container.clear()

app = FastAPI(lifespan=lifespan)

class InferencePayload(BaseModel):
    client_id: str
    features: list[float] = Field(..., min_length=16, max_length=16)

class InferenceResult(BaseModel):
    client_id: str
    prediction: float
    execution_time_ms: float

@app.post("/predict", response_model=InferenceResult)
async def predict(payload: InferencePayload):
    t_start = time.perf_counter()
    try:
        input_data = np.array([payload.features], dtype=np.float32)
        loop = asyncio.get_running_loop()
        
        preds = await loop.run_in_executor(
            None, 
            service_container["inference"].infer, 
            input_data
        )
        
        t_duration = (time.perf_counter() - t_start) * 1000.0
        return InferenceResult(
            client_id=payload.client_id,
            prediction=float(preds[0][0]),
            execution_time_ms=t_duration
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False)
```

#### Langkah 4: Buat Script Stress Test Asinkron `client_stress_test.py`
```python
import asyncio
import time
import httpx
import numpy as np

URL = "http://localhost:8080/predict"
TOTAL_REQUESTS = 200
CONCURRENCY = 20

async def send_request(client: httpx.AsyncClient, req_id: int):
    features = np.random.randn(16).tolist()
    payload = {"client_id": f"client_{req_id}", "features": features}
    try:
        t0 = time.perf_counter()
        resp = await client.post(URL, json=payload, timeout=5.0)
        t1 = time.perf_counter()
        return resp.status_code, (t1 - t0) * 1000.0
    except Exception:
        return 500, 0.0

async def main():
    limits = httpx.Limits(max_keepalive_connections=CONCURRENCY, max_connections=CONCURRENCY)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [send_request(client, i) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
    latencies = [lat for code, lat in results if code == 200]
    errors = [code for code, _ in results if code != 200]
    
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Success: {len(latencies)} | Errors: {len(errors)}")
    if latencies:
        print(f"Mean Latency: {np.mean(latencies):.2f} ms")
        print(f"P95 Latency: {np.percentile(latencies, 95):.2f} ms")
        print(f"P99 Latency: {np.percentile(latencies, 99):.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Langkah Eksekusi Hands-on:
1. Jalankan `python generate_model.py` untuk mengompilasi model ke format ONNX.
2. Jalankan `python server.py` di terminal pertama.
3. Jalankan `python client_stress_test.py` di terminal kedua untuk menguji latensi throughput sistem produksi lokal Anda.

---

### 13. Exercise

#### Tingkat Easy
* **Deskripsi**: Tambahkan *endpoint* readiness probe `/healthz` pada file `server.py` yang memeriksa ketersediaan sesi ONNX di memori.
* **Kriteria Keberhasilan**: Endpoint me-return status code 200 jika engine ter-load, atau 503 Service Unavailable jika sesi belum diinisialisasi.

#### Tingkat Medium
* **Deskripsi**: Ubah `server.py` agar mengimplementasikan *dynamic request batching manual* sederhana menggunakan antrean `asyncio.Queue` yang memproses tensor input dalam satu pemanggilan `session.run()` ketika jumlah antrean mencapai 8 item atau timeout mencapai batas 5 milidetik.
* **Kriteria Keberhasilan**: Throughput (`client_stress_test.py`) meningkat minimal 30% dengan latensi p99 tidak bertambah lebih dari 5ms.

#### Tingkat Hard
* **Deskripsi**: Implementasikan modul deteksi drift berbasis metrik statistik *Population Stability Index (PSI)* di server inferensi. Bandingkan distribusi data input batch produksi yang masuk terhadap referensi baseline statis (vektor distribusi normal acak) setiap 100 request. Jika nilai PSI melampaui ambang batas 0.25, server harus memicu *warning log event* terstruktur (JSON).
* **Kriteria Keberhasilan**: Sistem berhasil mendeteksi deviasi distribusi secara otomatis tanpa menghentikan jalur komputasi utama inferensi (non-blocking).

---

### 14. Challenge

#### Skenario: Arsitektur Resilience Degradasi Jaringan di Edge Computing
Anda adalah Lead ML Engineer di perusahaan logistik otonom. Armada drone otonom Anda menggunakan unit inferensi berbasis NVIDIA Jetson yang terpasang langsung pada drone (edge), namun sebagian fitur historis (misal: peta cuaca makro lokal, status zonasi udara militer) harus ditarik dari server cloud pusat melalui koneksi seluler 4G/5G yang tidak stabil.

#### Tantangan Teknis:
1. Bangun arsitektur inferensi hybrid yang mampu:
   * Menjalankan model secara lokal dengan latensi inferensi total $\le 20\text{ ms}$.
   * Menangani pemutusan total koneksi seluler (*complete network cutoff*) secara mulus tanpa kegagalan program (*zero crashes*).
   * Menerapkan fallback strategi fitur (*graceful feature degradation*): Jika online feature store cloud tidak dapat dihubungi dalam batas waktu timeout 5ms, sistem harus secara dinamis mengompensasi nilai fitur yang hilang menggunakan *local offline heuristic baseline* atau *imputation state* terkompresi tanpa merusak distribusi tensor kalkulasi model.
2. Desain skema sinkronisasi data telemetri: Ketika jaringan pulih, drone harus secara otomatis melakukan *burst streaming* log inferensi yang sempat tersimpan secara lokal ke Apache Kafka di cloud tanpa menimbulkan *out-of-memory* (OOM) pada storage terbatas perangkat edge.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda & Analisis Singkat)
1. Apa penyebab utama sistem inferensi berbasis Python Flask/Django standar memiliki performa *concurrency* yang buruk untuk model Machine Learning?
   * *Jawaban*: Python Global Interpreter Lock (GIL) membatasi eksekusi multithreaded murni pada satu core CPU untuk bytecode Python, sehingga komputasi tensor terhalang untuk memanfaatkan multithreading sejati secara simultan di tingkat interpreter.
2. Apa fungsi utama artefak ONNX dibanding file serialisasi `pickle` (`.pkl`)?
   * *Jawaban*: ONNX mengonversi kode model menjadi graf komputasi biner yang independen dari runtime bahasa pemrograman (*language-agnostic*), memungkinkan optimasi hardware tingkat rendah dan meniadakan kerentanan eksekusi arbitrary code yang ada pada file `pickle`.
3. Mengapa teknik *point-in-time correct join* sangat krusial dalam Feature Store?
   * *Jawaban*: Untuk mencegah kebocoran data masa depan (*data leakage*) pada fase pelatihan, dengan memastikan bahwa fitur yang digabungkan pada target kejadian mencerminkan kondisi data sebelum stempel waktu kejadian tersebut terjadi.
4. Apa yang dimaksud dengan *Constant Folding* pada optimasi kompilasi model ML?
   * *Jawaban*: Teknik kompilator yang menyederhanakan ekspresi komputasi konstan pada fase build/kompilasi (misal: $2 \times \pi$) sehingga nilainya langsung diganti dengan hasil statis tanpa perlu dikalkulasi ulang pada setiap siklus inferensi run-time.
5. Metrik latensi mana yang paling kritis untuk dievaluasi dalam sistem ML mission-critical: Mean Latency atau p99 Latency? Mengapa?
   * *Jawaban*: Latensi $p99$. Nilai rata-rata (*mean*) menyembunyikan variansi ekstrim (*tail latency*). P99 mengukur latensi terburuk yang dialami oleh 1% pengguna/transaksi, yang merupakan parameter penentu keberhasilan SLA sistem enterprise.

#### Soal Intermediate (Arsitektur & Konseptual)
6. Jelaskan bagaimana mekanisme *Dynamic Batching* pada serving engine seperti Triton mampu meningkatkan throughput sistem secara keseluruhan!
   * *Jawaban*: Dynamic batching mengumpulkan permintaan inferensi independen dari thread yang berbeda dalam jendela batas waktu kecil (*delay window*) dan menyatukannya ke dalam satu tensor batch besar. Operasi matriks berukuran besar ini dapat dieksekusi secara masif dan paralel oleh core komputasi (SIMD/Tensor Cores), mengeliminasi overhead *kernel launch* dan memaksimalkan saturasi hardware.
7. Apa perbedaan mendasar antara *Data Drift* dan *Concept Drift*?
   * *Jawaban*: *Data Drift* (Covariate Shift) adalah perubahan pada distribusi fitur input $P(X)$ sementara relasi bersyarat terhadap output tetap sama $P(Y|X)$. *Concept Drift* adalah pergeseran relasi fungsional/probabilistik aktual antara fitur input dan target label $P(Y|X)$ berubah, terlepas dari apakah distribusi input $P(X)$ berubah atau tidak.
8. Bagaimana shared memory (IPC) memangkas latensi pada komunikasi antar-proses inferensi?
   * *Jawaban*: Shared memory memungkinkan dua proses (misal: Web Server dan Serving Engine) mengakses buffer memori fisik (RAM/VRAM) yang sama secara langsung melalui pointer memori, meniadakan proses serialisasi, deserialisasi, dan operasi salin data (*data copying*) melalui network stack TCP/loopback.
9. Jelaskan risiko menerapkan Post-Training Quantization (PTQ) INT8 tanpa fase kalibrasi dataset (*uncalibrated quantization*)!
   * *Jawaban*: Nilai floating point akan dipetakan (*clipping/scaling*) ke rentang integer [-128, 127] secara serampangan. Tanpa dataset kalibrasi yang representatif untuk mencari skala dinamis dan offset nol yang presisi, pemangkasan nilai ekstrem dapat merusak akurasi model secara katastropik.
10. Mengapa kita harus memisahkan metrik readiness probe dan liveness probe pada deployment Kubernetes pod ML?
    * *Jawaban*: Model ML memerlukan waktu pemuatan artefak yang signifikan ke RAM/VRAM saat startup. Jika liveness probe memeriksa alur sebelum model selesai dimuat, Kubernetes akan menganggap pod macet dan melakukan restart terus-menerus (*crash loop backoff*). Readiness probe mengontrol kapan trafik boleh dialirkan, sedangkan liveness probe hanya mengontrol apakah proses worker masih hidup.

#### Skenario Kasus Produksi

11. **Kasus 1**: Sistem rekomendasi e-commerce Anda mengalami lonjakan latensi dari 12ms menjadi 850ms setiap kali kampanye diskon kilat (*flash sale*) dimulai. Utilisasi CPU kluster serving melonjak hingga 100%, tetapi utilisasi GPU hanya berada di angka 15%. Analisis letak kegagalan arsitekturnya dan tentukan solusi perbaikannya!
    * *Solusi Arsitektural*: Terjadi CPU-bottleneck pada lapisan pra-pemrosesan data (*data preprocessing bottleneck*) atau deserialisasi payload JSON yang berjalan di CPU sebelum data dikirim ke GPU. Solusinya: Pindahkan pra-pemrosesan data langsung ke graf model (menggunakan ONNX custom op / operator TorchVision GPU), ubah protokol transfer dari JSON/REST menjadi gRPC/Protobuf, dan aktifkan shared-memory dynamic batching pada inference server.

12. **Kasus 2**: Tim Anda mendeteksi bahwa akurasi model credit scoring menurun tajam dalam 3 bulan terakhir. Pipeline CI/CD Anda memicu proses *retraining* otomatis menggunakan data 3 bulan tersebut. Namun setelah model baru dideploy, tingkat default pembayaran pinjaman justru semakin meningkat. Apa kesalahan validasi sistem ML Anda?
    * *Solusi Arsitektural*: Tim mengalami jebakan *Feedback Loop / Confirmation Bias*. Data yang dikumpulkan selama 3 bulan terakhir hanya mencakup data debitur yang disetujui oleh model sebelumnya (*selection bias*), sehingga model baru tidak pernah dilatih menggunakan profil nasabah yang ditolak. Solusinya: Terapkan strategi *exploration-exploitation* (mengalirkan persentase kecil, misal 2-5% transaksi ke model kontrol acak / heuristik) dan lakukan evaluasi menggunakan dataset counterfactual yang tidak terdistorsi oleh keputusan model sebelumnya.

13. **Kasus 3**: Sebuah bank digital multinasional mewajibkan arsitektur inferensi berjalan di multi-region (Singapura dan Frankfurt). Karena kepatuhan regulasi GDPR dan PDPA, data transaksi pengguna tidak boleh keluar dari wilayah hukum masing-masing region. Bagaimana Anda mendesain arsitektur Feature Store dan sinkronisasi modelnya?
    * *Solusi Arsitektural*:
      * Terapkan arsitektur *Decoupled Federated Feature Store*: Online dan Offline store dipisahkan per region (Isolasi data payload transaksi secara strictly regional).
      * Pisahkan metadata fitur (definisi skema transformasi kode fitur) yang dikelola terpusat via GitOps repository secara global.
      * Model dilatih menggunakan teknik *Federated Learning* atau model dilatih di satu region menggunakan fitur agregasi anonim (*anonymized/pseudonymized differential privacy data*).
      * Model artefak didistribusikan secara *downstream* dari global registry ke cluster Triton lokal masing-masing region. Eksekusi inferensi berjalan 100% lokal di dalam yurisdiksi data tanpa transfer data lintas batas negara.

---

### 16. Summary

Membangun sistem Machine Learning kelas enterprise membutuhkan perubahan fundamental dari komputasi berbasis skrip interaktif menuju rekayasa perangkat lunak berskala besar yang deterministik, terukur, dan tervolume tinggi.

Pilar utama arsitektur ML produksi mencakup:
1. **Pemisahan Jalur Fitur**: Integrasi Feature Store untuk memastikan *point-in-time correctness* pada pelatihan data historis dan penyajian fitur sub-milidetik pada jalur inferensi online.
2. **Optimalisasi Komputasi Graf**: Penggunaan intermediate representation (ONNX/TensorRT) dan runtime terkompilasi untuk memangkas dependensi interpreter bahasa tingkat tinggi dan membebaskan komputasi dari belenggu thread lock (GIL).
3. **Penyajian Cepat & Terukur**: Pemanfaatan dynamic batching, shared-memory IPC, dan komunikasi biner (gRPC) untuk mencapai throughput maksimal dengan latensi rendah pada persentil tinggi ($p99$).
4. **Sistem Deteksi Drift & Degradasi**: Observabilitas telemetri aktif terhadap distribusi statistik data input dan metrik inferensi secara kontinu, memastikan integritas sistem sebelum degradasi performa mempengaruhi keandalan operasional enterprise.