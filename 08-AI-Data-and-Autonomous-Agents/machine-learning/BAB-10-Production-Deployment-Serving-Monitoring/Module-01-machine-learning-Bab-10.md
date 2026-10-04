# Bab 10: Production Deployment, Serving & Monitoring
## Modul 01: High-Performance Model Serving Foundations & Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
* **Menganalisis & Mengukur** metrik performa inferensi tingkat sistem (P95/P99 latency, throughput (RPS), GPU/CPU saturation, memory footprint) untuk menentukan batasan Service Level Objective (SLO).
* **Merancang & Mengimplementasikan** arsitektur *serving runtime* berbasis *asynchronous concurrency* dan *dynamic batching* guna memaksimalkan *hardware utilization* tanpa mengorbankan batas ambang latensi (*latency threshold*).
* **Membangun** *production-grade inference microservice* menggunakan FastAPI dan *custom runtime worker engine* yang dilengkapi *structured logging*, validasi skema tensor yang ketat (*zero-copy validation*), dan *graceful degradation*.
* **Mengonfigurasi & Mengintegrasikan** instrumentasi telemetri *Four Golden Signals* (Latency, Traffic, Errors, Saturation) beserta metrik spesifik Machine Learning (drift proxy, batch size distribution) ke dalam ekosistem Prometheus.
* **Mengevaluasi & Memitigasi** kegagalan sistem inferensi akibat *concurrency bottleneck*, *memory leaks* (uncollected tensor graphs), dan *payload degradation* melalui mekanisme *circuit breaker* dan *backpressure*.

---

### 2. Concept Overview

Model serving di lingkungan produksi mentransformasi representasi matematika pasif (artifak bobot model hasil training) menjadi sistem komputasi terdistribusi aktif yang dapat diakses secara deterministik dan reliabel. 

```
+-----------------------------------------------------------------------------+
|                               Mental Model                                  |
|                                                                             |
|   Training World (Throughput-Oriented)   VS   Serving World (Latency-Oriented)|
|   - Goal: Minimum time-to-accuracy          - Goal: Deterministic SLA/SLO   |
|   - Static execution graph                  - Dynamic, concurrent traffic   |
|   - Max batch sizes (VRAM bound)            - Dynamic batching & queues     |
|   - Tolerant to intermittent failures       - High Availability (99.99%)    |
+-----------------------------------------------------------------------------+
```

Proses *inference pipeline* online terdiri atas empat fase serial:
1. **Network Ingress & De-serialization:** Mengubah HTTP/gRPC byte stream menjadi objek memori aplikasi.
2. **Feature Preprocessing & Tensor Validation:** Normalisasi data input, tokenisasi/ekstraksi fitur, dan konversi ke tensor array terstruktur.
3. **Compute Engine Execution:** Eksekusi komputasi forward-pass di CPU/GPU menggunakan runtime teroptimasi (misal: ONNX Runtime, TensorRT, LibTorch).
4. **Post-processing & Response Serialization:** Mengubah tensor output (logits, embeddings) menjadi struktur data respons (JSON/Protobuf) dan mengembalikannya ke klien.

Tantangan utama dari model serving berkecepatan tinggi adalah ketidakcocokan karakteristik komputasi antara I/O-bound operations (menerima request, parsing JSON) dan CPU/GPU-bound operations (eksekusi kernel matriks tensor). Memahami model mental ini krusial: I/O memerlukan arsitektur *asynchronous non-blocking*, sementara eksekusi model memerlukan *dedicated synchronous worker pools* atau runtime C++ terisolasi untuk menghindari fenomena *GIL (Global Interpreter Lock) contention* pada Python.

---

### 3. Why It Matters

Di level enterprise, kegagalan arsitektur serving berimplikasi langsung pada kerugian finansial dan reputasi sistem:
* **Underutilization vs. Latency Trade-off:** Menjalankan inferensi per-request (*batch size = 1*) menghasilkan latensi minimal tetapi membuang hingga 80-90% kapasitas komputasi paralel GPU. Sebaliknya, menunggu batch besar mengakibatkan pelanggaran P99 latency SLA. Diperlukan algoritma *Dynamic Batching* adaptif.
* **Silent Failure & Concept Drift:** Berbeda dari software tradisional yang gagal dengan status error 500, model machine learning yang rusak di produksi sering kali tetap mengembalikan status `200 OK` dengan skor probabilitas yang valid, namun menghasilkan prediksi yang salah secara semantik akibat perubahan distribusi data input.
* **Resource Exhaustion:** Inferensi model berskala besar dapat mengalami memory fragmentation atau kebocoran resource (*tensor memory leak*) ketika referensi graph komputasi tidak dibersihkan oleh garbage collector, memicu restart mendadak pod Kubernetes via OOMKilled (*Out Of Memory*).

Arsitektur serving modern harus mampu mengelola konkurensi ekstrem, menjamin isolasi kegagalan, dan menyuplai metrik real-time untuk auditabilitas sistem.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur *High-Performance Model Serving Node* yang mengimplementasikan *Asynchronous Request Decoupling*, *Dynamic Batching Engine*, dan *Telemetry Exporter*.

```
+----------------------------------------------------------------------------------------------------+
|                                    KUBERNETES POD ARCHITECTURE                                     |
|                                                                                                    |
|  [ Ingress / Client Traffic ]                                                                      |
|             |                                                                                      |
|             v (HTTP/2 / gRPC)                                                                      |
|  +-----------------------------------------------------------------------------------------------+ |
|  | API GATEWAY LAYER (FastAPI / Asynchronous Event Loop)                                         | |
|  |  - TLS Termination & Request Authentication                                                    | |
|  |  - Zero-Copy Schema Validation (Pydantic V2 / Core C-Engine)                                  | |
|  |  - Request Tracing (OpenTelemetry Injector)                                                   | |
|  +-----------------------------------------------------------------------------------------------+ |
|             |                                                                                      |
|      (Enqueues Task)                                                                               |
|             v                                                                                      |
|  +-----------------------------------------------------------------------------------------------+ |
|  | DYNAMIC INFERENCE COORDINATOR (Memory-mapped Queue)                                           | |
|  |                                                                                               | |
|  |   [ Inbound Queue ] -> [ Priority Buffer ] -> [ Dynamic Batching Worker ]                     | |
|  |                                                     |                                         | |
|  |        Trigger Condition:                           | Batching Rules:                         | |
|  |        - Max Batch Size Reached (e.g., N=32)        | - Concat tensors along axis 0           | |
|  |        - OR Max Timeout Elapsed (e.g., T=5ms)       | - Retain correlation IDs via Futures    | |
|  +-----------------------------------------------------------------------------------------------+ |
|             |                                                                                      |
|             | (Pointers to Batched Memory Tensors)                                                 |
|             v                                                                                      |
|  +-----------------------------------------------------------------------------------------------+ |
|  | COMPUTE RUNTIME ISOLATION LAYER (ONNX Runtime / C++ Shared Lib)                               | |
|  |  - Multi-threaded Graph Execution (OMP_NUM_THREADS tuning)                                    | |
|  |  - Non-blocking execution outside Python GIL                                                  | |
|  |  - TensorRT / CUDA Engine Execution (if GPU present)                                         | |
|  +-----------------------------------------------------------------------------------------------+ |
|             |                                                                                      |
|      (Scatter Results)                                                                             |
|             v                                                                                      |
|  +-----------------------------------------------------------------------------------------------+ |
|  | RESULT DISPATCHER                                                                             | |
|  |  - Splice batched output back to individual request contexts                                  | |
|  |  - Set result on pending asyncio.Future                                                       | |
|  +-----------------------------------------------------------------------------------------------+ |
|             |                                                                                      |
|             +-------------------------------------------------------------+                        |
|             |                                                             |                        |
|             v                                                             v                        |
|  [ HTTP 200 Client Response ]                             +-------------------------------+        |
|                                                           | TELEMETRY & METRICS PIPELINE  |        |
|                                                           | - Prometheus Exporter (:9090) |        |
|                                                           |   * Request Duration (P95/P99)|        |
|                                                           |   * Dynamic Batch Size Hist   |        |
|                                                           |   * Prediction Value Drift    |        |
|                                                           |   * Error / Fallback Counters |        |
|                                                           +-------------------------------+        |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Dynamic Batching Mechanism
Komputasi matriks pada akselerator modern (CPU AVX-512 atau GPU Tensor Cores) memiliki efisiensi komputasi *FLOPs per watt* yang jauh lebih tinggi ketika memproses matriks multidimensi daripada vektor tunggal.

1. **Enqueue Phase:** Ketika request HTTP masuk, data di-preprocess menjadi tensor dimensi $(1, D)$, diikat ke instance `asyncio.Future`, dan dimasukkan ke antrean thread-safe *Inbound Queue*.
2. **Scheduling Loop:** Thread scheduler terpisah mengevaluasi dua kondisi:
   $$\text{Batch Ready} \iff (\text{Queue.size}() \ge \text{MaxBatchSize}) \lor (t_{\text{current}} - t_{\text{oldest\_request}} \ge \text{MaxLatencyBudget})$$
3. **Execution & Splice:** Seluruh tensor dalam antrean di-*stack* menjadi tensor dimensi $(B, D)$ di mana $B \le \text{MaxBatchSize}$. Inference engine memproses tensor tersebut dalam satu kernel call. Output $(B, C)$ kemudian di-*unslice* kembali ke masing-masing Future ID untuk dikembalikan ke event loop client asalnya.

#### B. Isolasi Global Interpreter Lock (GIL)
Python runtime memiliki batasan mendasar di mana hanya satu OS thread yang dapat mengeksekusi Python bytecode secara bersamaan. Runtime komputasi canggih (seperti ONNX Runtime atau LibTorch C++) melepaskan GIL (`Py_BEGIN_ALLOW_THREADS`) selama evaluasi graf komputasi berlangsung:
* Event loop FastAPI (AsyncIO) berjalan di Main Thread.
* Model Inference dialokasikan ke engine backend C++ yang menggunakan thread pool native (misalnya OpenMP atau Eigen).
* Hal ini menjamin bahwa saat model memproses inferensi intensif, server API tetap responsif menerima koneksi baru dan memproses *health checks*.

#### C. Telemetri dan Deteksi Drift Pasif
Monitoring model produksi memerlukan integrasi metrik performa sistem dan integritas statistik data:
* **The Golden Signals:**
  * **Latency:** Diukur via histogram berpresisi tinggi (fokus pada bucket P95, P99, P99.9).
  * **Traffic:** Rate request per second (RPS).
  * **Errors:** Persentase response status `5xx` atau fallback executions.
  * **Saturation:** Kedalaman antrean dynamic batching dan penggunaan alokasi VRAM/RAM.
* **Model Integrity Signals:**
  * Histogram distribusi probabilitas output model (menggunakan Kullback-Leibler Divergence atau Wasserstein Distance secara offline terhadap baseline validation metrics).
  * Counter untuk nilai invalid atau pemotongan batas (*clamping activations*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi komprehensif high-performance model serving engine menggunakan FastAPI, ONNX Runtime (disimulasikan dengan komputasi tensor teroptimasi berbasis NumPy untuk determinisme), dynamic batcher berbasis antrean asinkron, dan Prometheus metrics exporter lengkap.

```python
# architecture/inference_engine.py
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("inference-engine")

# -----------------------------------------------------------------------------
# PROMETHEUS TELEMETRY CONFIGURATION
# -----------------------------------------------------------------------------
INF_LATENCY_HISTOGRAM = Histogram(
    "model_inference_latency_seconds",
    "Durasi inferensi komputasi model (per batch execution)",
    buckets=[0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500],
)
E2E_LATENCY_HISTOGRAM = Histogram(
    "model_e2e_request_latency_seconds",
    "Durasi end-to-end penanganan request oleh server",
    buckets=[0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0],
)
BATCH_SIZE_HISTOGRAM = Histogram(
    "model_batch_size_distribution",
    "Distribusi ukuran batch pada dynamic batcher",
    buckets=[1, 2, 4, 8, 16, 32, 64],
)
REQUEST_COUNTER = Counter(
    "model_requests_total",
    "Total request yang masuk ke API serving",
    ["status"],
)
QUEUE_SATURATION_GAUGE = Gauge(
    "model_queue_depth",
    "Jumlah item yang sedang mengantre di buffer dynamic batcher",
)

# -----------------------------------------------------------------------------
# CONTRACT SPECIFICATIONS (DATA SCHEMAS)
# -----------------------------------------------------------------------------
class InferenceRequestPayload(BaseModel):
    features: List[float] = Field(
        ...,
        min_items=4,
        max_items=4,
        description="Fitur vektor input numerik berukuran tepat 4 dimensi",
        example=[5.1, 3.5, 1.4, 0.2],
    )

class InferenceResponsePayload(BaseModel):
    prediction: int = Field(..., description="Kelas prediksi hasil inferensi")
    probabilities: List[float] = Field(..., description="Distribusi probabilitas softmax")
    model_version: str = Field(..., description="Identitas versi artefak model")
    processing_time_ms: float = Field(..., description="Durasi komputasi inferensi internal")

# -----------------------------------------------------------------------------
# MODEL RUNTIME WRAPPER
# -----------------------------------------------------------------------------
class MockONNXRuntimeEngine:
    """
    Simulasi runtime engine teroptimasi C-backend (e.g., ONNX Runtime/TensorRT).
    Menerapkan komputasi tervektorisasi murni menggunakan NumPy.
    """
    def __init__(self, model_version: str = "v1.2.0") -> None:
        self.model_version = model_version
        # Inisialisasi bobot sintetis: Layer linear (4 fitur -> 3 kelas)
        rng = np.random.default_rng(seed=42)
        self.weights = rng.standard_normal((4, 3), dtype=np.float32)
        self.bias = np.zeros((3,), dtype=np.float32)
        logger.info("Artefak model terinisialisasi. Version: %s", self.model_version)

    def forward(self, batch_tensor: np.ndarray) -> np.ndarray:
        """
        Eksekusi batch forward-pass matematis: Softmax(X @ W + b)
        Non-blocking context pada backend aslinya melepaskan Python GIL.
        """
        if batch_tensor.ndim != 2 or batch_tensor.shape[1] != 4:
            raise ValueError(f"Shape tensor tidak valid: {batch_tensor.shape}, ekspektasi: (N, 4)")
        
        # Matrix multiplication & bias addition
        logits = np.dot(batch_tensor, self.weights) + self.bias
        # Numerically stable Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probabilities = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        return probabilities

# -----------------------------------------------------------------------------
# ASYNCHRONOUS DYNAMIC BATCHER
# -----------------------------------------------------------------------------
@dataclass
class QueueItem:
    tensor_slice: np.ndarray
    future: asyncio.Future
    enqueued_at: float

class DynamicBatcher:
    def __init__(
        self,
        engine: MockONNXRuntimeEngine,
        max_batch_size: int = 16,
        max_latency_budget_seconds: float = 0.005,  # 5ms
    ) -> None:
        self.engine = engine
        self.max_batch_size = max_batch_size
        self.max_latency_budget = max_latency_budget_seconds
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._batch_processing_loop())
        logger.info("Dynamic Batcher worker engine dimulai.")

    async def stop(self) -> None:
        self._shutdown_event.set()
        if self._worker_task:
            await self._worker_task
        logger.info("Dynamic Batcher worker engine dihentikan secara graceful.")

    async def predict(self, feature_vector: List[float]) -> Tuple[int, List[float]]:
        if self._shutdown_event.is_set():
            raise RuntimeError("Serving Engine sedang dalam status shutdown.")

        tensor_slice = np.array(feature_vector, dtype=np.float32)
        loop = asyncio.get_running_loop()
        item_future: asyncio.Future = loop.create_future()
        
        queue_item = QueueItem(
            tensor_slice=tensor_slice,
            future=item_future,
            enqueued_at=time.perf_counter(),
        )
        
        await self.queue.put(queue_item)
        QUEUE_SATURATION_GAUGE.set(self.queue.qsize())
        
        return await item_future

    async def _batch_processing_loop(self) -> None:
        while not self._shutdown_event.is_set():
            items_to_process: List[QueueItem] = []
            
            try:
                # Menunggu item pertama dengan timeout idle
                first_item = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                items_to_process.append(first_item)
            except asyncio.TimeoutError:
                continue

            start_deadline = time.perf_counter() + self.max_latency_budget

            # Harvesting batch tambahan hingga batas ukuran atau timeout tercapai
            while len(items_to_process) < self.max_batch_size:
                remaining_time = start_deadline - time.perf_counter()
                if remaining_time <= 0:
                    break
                try:
                    next_item = await asyncio.wait_for(self.queue.get(), timeout=max(0.0, remaining_time))
                    items_to_process.append(next_item)
                except asyncio.TimeoutError:
                    break

            # Update metrik antrean
            QUEUE_SATURATION_GAUGE.set(self.queue.qsize())
            BATCH_SIZE_HISTOGRAM.observe(len(items_to_process))

            # Eksekusi inferensi batch
            await self._execute_batch(items_to_process)

    async def _execute_batch(self, batch_items: List[QueueItem]) -> None:
        t_start = time.perf_counter()
        
        try:
            # Menggabungkan data menjadi satu kesatuan 2D Tensor
            stacked_array = np.stack([item.tensor_slice for item in batch_items], axis=0)
            
            # Eksekusi komputasi forward-pass di thread pool terpisah agar event loop bebas
            loop = asyncio.get_running_loop()
            probabilities = await loop.run_in_executor(None, self.engine.forward, stacked_array)
            predictions = np.argmax(probabilities, axis=1)

            inf_duration = time.perf_counter() - t_start
            INF_LATENCY_HISTOGRAM.observe(inf_duration)

            # Membagi hasil inferensi kembali ke masing-masing Future pemohon
            for idx, item in enumerate(batch_items):
                if not item.future.cancelled():
                    item.future.set_result(
                        (int(predictions[idx]), probabilities[idx].tolist())
                    )
        except Exception as exc:
            logger.error("Terjadi kegagalan kritis pada eksekusi batch: %s", str(exc), exc_info=True)
            for item in batch_items:
                if not item.future.cancelled():
                    item.future.set_exception(exc)

# -----------------------------------------------------------------------------
# APPLICATION ENTRYPOINT & LIFECYCLE MANAGEMENT
# -----------------------------------------------------------------------------
engine_instance = MockONNXRuntimeEngine()
batcher_instance = DynamicBatcher(
    engine=engine_instance,
    max_batch_size=16,
    max_latency_budget_seconds=0.005,
)

async def lifespan(app: FastAPI):
    # Startup: Inisialisasi thread loop dan memory allocations
    batcher_instance.start()
    yield
    # Shutdown: Flush remaining items dan cleanup resources
    await batcher_instance.stop()

app = FastAPI(
    title="High-Performance ML Serving Runtime",
    version="1.0.0",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# HTTP ENDPOINTS
# -----------------------------------------------------------------------------
@app.post(
    "/v1/models/classifier:predict",
    response_model=InferenceResponsePayload,
    status_code=status.HTTP_200_OK,
)
async def predict_endpoint(payload: InferenceRequestPayload) -> InferenceResponsePayload:
    start_time = time.perf_counter()
    try:
        pred_class, probs = await batcher_instance.predict(payload.features)
        
        total_time = (time.perf_counter() - start_time) * 1000.0
        E2E_LATENCY_HISTOGRAM.observe(total_time / 1000.0)
        REQUEST_COUNTER.labels(status="success").inc()

        return InferenceResponsePayload(
            prediction=pred_class,
            probabilities=probs,
            model_version=engine_instance.model_version,
            processing_time_ms=round(total_time, 3),
        )
    except Exception as exc:
        REQUEST_COUNTER.labels(status="error").inc()
        logger.error("Error processing request: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference pipeline execution error: {str(exc)}",
        )

@app.get("/healthz", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, str]:
    """Kubernetes liveness and readiness probe."""
    return {"status": "healthy", "model_version": engine_instance.model_version}

@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Scrape endpoint standar Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

### 7. Edge Cases & Failure Modes

Sistem serving produksi wajib menangani skenario degradasi ekstrem tanpa memicu *cascading failures*:

1. **Backpressure Failure saat Antrean Meluap:**
   * *Problem:* Beban RPS masuk melebihi laju inferensi maksimal ($\lambda > \mu$), mengakibatkan antrean `asyncio.Queue` tumbuh tak terbatas (*unbounded memory growth*), memicu *Out-Of-Memory (OOM)*.
   * *Mitigation:* Implementasi *Bounded Queue* dengan batas ukuran statis. Ketika antrean penuh, tolak request seketika menggunakan HTTP `503 Service Unavailable` disertai header `Retry-After`. Jangan biarkan latensi antrean terakumulasi.

2. **Poison Pill Payload (NaN, Infs, Shape Mismatch):**
   * *Problem:* Klien mengirimkan nilai float `NaN` atau string yang lolos deserialisasi, namun saat masuk ke kalkulasi dot product, seluruh output matriks pada batch tersebut terinfeksi menjadi `NaN`.
   * *Mitigation:* Validasi *strict type casting* dan cek keberadaan `np.isnan(tensor).any()` pada level validasi input sebelum tensor dialokasikan ke Dynamic Batcher Queue.

3. **GPU Engine Timeout & Driver Deadlock:**
   * *Problem:* Kernel C++ mengalami segfault atau driver CUDA hang karena fragmentasi memori, menyebabkan batch worker terhenti permanen (*deadlock*).
   * *Mitigation:* Pasang deadline guard menggunakan `asyncio.wait_for` pada tingkat eksekusi `run_in_executor`. Terapkan mekanisme *Heartbeat Healthcheck* independen yang merestart pod jika worker terdeteksi beku selama $> 2 \times \text{SLO}$.

4. **Koneksi Klien Terputus (Cancelled Requests):**
   * *Problem:* Klien mengalami timeout di sisi mereka dan memutus koneksi, tetapi server tetap memproses komputasi tensor berat tersebut di latar belakang, menyia-nyiakan alokasi hardware.
   * *Mitigation:* Gunakan polling `future.cancelled()` sebelum menyusun batch inferensi. Lewatkan komputasi tensor yang pemohonnya sudah tidak aktif.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Arsitektur | In-House Custom Serving (FastAPI + Engine) | Specialized Serving Engine (Triton / TorchServe) | Embedded Model Serving (In-Process C++) |
| :--- | :--- | :--- | :--- |
| **Throughput & GPU Utilization** | Sedang - Bagus untuk skenario CPU, terbatas oleh overhead Python wrapper pada beban super tinggi. | Sangat Tinggi - Komputasi C++ native, dynamic batching tingkat hardware, multi-model concurrent execution. | Ekstrem - Nol overhead komunikasi jaringan atau soket RPC. |
| **Operational Complexity** | Sangat Rendah - Sederhana di-debug, pipeline preprocessing Python native dapat diintegrasikan langsung. | Tinggi - Membutuhkan konfigurasi model repository yang kaku, Docker image khusus, dan kurva belajar format konfigurasi. | Sangat Tinggi - Mengharuskan tim ML menulis kode inferensi dalam ekosistem C++/Rust/Go. |
| **Flexibility Pre/Post Processing** | Sangat Tinggi - Fleksibilitas penuh untuk logika parsing kompleks, tokenisasi dinamis, database lookup sekunder. | Sedang - Membutuhkan ensemble pipeline configuration atau custom C++/Python backends yang kompleks. | Rendah - Logika preprocessing terikat ketat dengan bahasa inang aplikasi. |
| **Rekomendasi Penggunaan** | Standard Enterprise API, throughput < 5,000 RPS, pipeline integrasi fitur yang dinamis. | High-throughput GPU inference cluster, LLM, Computer Vision realtime, multi-framework serving. | Sistem ultra low-latency (misal: High-Frequency Trading, robotics edge devices, gaming engines). |

---

### 9. Best Practices & Standard Industri

1. **Zero Downtime Updates:** Jangan pernah melakukan restart in-place. Gunakan strategi Kubernetes *RollingUpdate* dengan lifecycle hook `preStop` (sleep 5-10 detik untuk menguras koneksi yang ada) dan `readinessProbe` yang baru mengembalikan status HTTP 200 setelah model selesai di-load ke VRAM.
2. **Resource Requests & Limits Pinning:** Selalu tetapkan batas Kubernetes `requests.cpu` == `limits.cpu` dan `requests.memory` == `limits.memory` untuk mengalokasikan kelas *Guaranteed Quality of Service (QoS)*. Ini mencegah pod serving di-evict sewaktu-waktu saat host mengalami memory pressure.
3. **Optimasi Thread Pool:**
   ```bash
   # Hindari perebutan konteks CPU switching berlebihan di dalam container
   export OMP_NUM_THREADS=1
   export MKL_NUM_THREADS=1
   export OPENBLAS_NUM_THREADS=1
   ```
4. **Decouple Heavy Preprocessing:** Jika inferensi model memerlukan preprocessing berat (misalnya resize video resolusi tinggi), jangan lakukan di main serving pod. Gunakan *preprocessing worker cluster* terpisah yang mengirimkan tensor yang sudah dinormalisasi via gRPC shared memory.
5. **Circuit Breakers:** Implementasikan circuit breaker di level gateway API (misal: Envoy/Kong) yang langsung menolak trafik jika latensi P99 melampaui batas toleransi (misalnya 150ms selama window 1 menit).

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan menguji performa model serving engine di bawah beban konkurensi tinggi, memvalidasi efisiensi dynamic batching, dan menganalisis metrik Prometheus yang dihasilkan.

#### Langkah 1: Persiapan Environment
Buat file dependency dan install library yang dibutuhkan:
```bash
cat << 'EOF' > requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.28.0
numpy==1.26.4
prometheus-client==0.20.0
httpx==0.27.0
locust==2.24.0
EOF

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Langkah 2: Jalankan Inference Service
Simpan kode implementasi pada Section 6 ke dalam file bernama `server.py`, lalu jalankan server:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 1 --log-level warning &
```

Verifikasi server merespons dengan benar:
```bash
curl -X POST http://127.0.0.1:8000/v1/models/classifier:predict \
  -H "Content-Type: application/json" \
  -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
```

Output yang diharapkan:
```json
{"prediction":0,"probabilities":[...],"model_version":"v1.2.0","processing_time_ms":...}
```

#### Langkah 3: Eksekusi Load Testing Simulasi Konkurensi
Buat skrip load testing `locustfile.py` untuk menguji dynamic batcher:
```python
# locustfile.py
from locust import HttpUser, task, between

class InferenceUser(HttpUser):
    wait_time = between(0.001, 0.005) # Frekuensi request tinggi

    @task
    def predict(self):
        payload = {"features": [5.1, 3.5, 1.4, 0.2]}
        self.client.post("/v1/models/classifier:predict", json=payload)
```

Jalankan pengujian headless Locust selama 30 detik:
```bash
locust -f locustfile.py --headless -u 50 -r 10 --run-time 30s --host http://127.0.0.1:8000
```

#### Langkah 4: Evaluasi Metrik Produksi
Ambil snapshot metrik dari scrape endpoint Prometheus dan periksa pemanfaatan Dynamic Batching:
```bash
curl -s http://127.0.0.1:8000/metrics | grep -E "model_batch_size_distribution_bucket|model_inference_latency_seconds_bucket"
```

#### Kriteria Keberhasilan:
* Request berhasil dieksekusi dengan *Failure Rate* = 0%.
* Metrik `model_batch_size_distribution_bucket` menunjukkan peningkatan frekuensi pada bucket ukuran batch $> 1$ (misal: 4, 8, atau 16), membuktikan Dynamic Batching berhasil mengelompokkan request konkruen secara otomatis.
* Endpoint `/healthz` tetap responsif dengan status `200 OK` selama pengujian berlangsung.