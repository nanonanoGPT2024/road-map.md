# Bab 07: Enterprise Serving Platforms & Compilation

## Modul 01: Core Inference Serving Engines & TensorRT Compilation Pipelines

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Merancang & Mengonfigurasi Inference Server Skala Enterprise**: Menerapkan arsitektur serving multi-model berbasis Triton Inference Server dengan utilisasi *dynamic batching* dan *concurrent model execution*.
*   **Melakukan Graph Compilation & Kernel Optimization**: Mengotomatisasi konversi representasi intermediate (ONNX) menjadi binary engine TensorRT berperforma tinggi melalui *layer/tensor fusion*, *precision calibration* (FP16/INT8), dan konfigurasi *dynamic shape profiles*.
*   **Mengeliminasi Tail Latency (p99)**: Menyeimbangkan parameter *max queue delay* dan *batch size limit* untuk mempertahankan Service Level Objective (SLO) latensi di bawah 15 ms pada throughput tinggi (>2.000 QPS).
*   **Mengimplementasikan Asynchronous gRPC Serving Client**: Membangun client inferensi asinkron dengan *connection pooling*, transfer memori zero-copy via Shared Memory (POSIX/CUDA IPC), dan *circuit breaker pattern*.
*   **Mendiagnosis Failure Mode Perangkat Keras**: Mengidentifikasi serta memitigasi anomali konkurensi GPU seperti VRAM fragmentation, context switching overhead, dan dynamic shape mismatch crash.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Penyajian model machine learning pada lingkungan enterprise berbeda secara mendasar dengan eksekusi lokal berbasis framework standar (seperti vanilla PyTorch atau Hugging Face `pipeline`). Runtime standar beroperasi menggunakan paradigma *imperative execution* yang sarat dengan overhead Python Global Interpreter Lock (GIL), alokasi memori yang tidak efisien, dan ketidakmampuan menjadwalkan batch request lintas koneksi jaringan secara adaptif.

```
+-----------------------------------------------------------------------------+
|                                MENTAL MODEL                                 |
+-----------------------------------------------------------------------------+
|                                                                             |
|   +-----------------------+                 +---------------------------+   |
|   |   Imperative Torch    |                 |   Compiled TensorRT       |   |
|   +-----------------------+                 +---------------------------+   |
|   | Python Interpreter    |                 | Zero Python Overhead      |   |
|   | Op-by-op Dispatch     |    VS           | Fused Hardware Kernels    |   |
|   | Dynamic Allocations   |                 | Static Pre-allocated VRAM |   |
|   | Sequential Queries    |                 | Hardware Dynamic Batching |   |
|   +-----------------------+                 +---------------------------+   |
|                                                                             |
+-----------------------------------------------------------------------------+
```

Enterprise Serving Platform beroperasi sebagai sistem operasi mini khusus inferensi yang memisahkan antara:
1. **Model Compilation & Graph Optimization**: Transformasi struktur komputasi model dari *declarative computation graph* menjadi *monolithic hardware-specific machine code*. Graf komputasi disederhanakan melalui eliminasi operasi redundant (seperti *dead code elimination*, *constant folding*), penggabungan kernel (*operator fusion* seperti `Conv + Bias + ReLU` menjadi satu eksekusi kernel GPU tunggal), serta kuantisasi bobot dan aktivasi ke representasi bit lebih rendah (FP16/INT8).
2. **Execution Runtime Engine**: Manajer konkurensi independen bahasa (C++) yang mengorkestrasi antrean inferensi, menjadwalkan multi-worker thread melintasi berbagai physical compute engine (GPU streaming multiprocessors), dan mengisolasi memory space antar model.
3. **Dynamic Batching Engine**: Algoritma penjadwalan pada lapisan server yang mengumpulkan request inferensi individual dari berbagai koneksi jaringan yang masuk dalam rentang waktu mikrosekon tertentu, membentuk batch tensor dimensional sementara, mengeksekusinya secara paralel dalam satu instruksi kernel GPU, dan memecah kembali hasilnya ke client masing-masing tanpa kebocoran konteks data.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan produksi enterprise:
* **Cost of Compute (Total Cost of Ownership/TCO)**: Menggunakan inference server vanilla PyTorch umumnya hanya menghasilkan 10–25% utilisasi GPU (Tensor Core idle menunggu dispatch CPU). Dengan engine terkompilasi (TensorRT) dan dynamic batching Triton, utilisasi dapat dinaikkan hingga 85–95%, memangkas kebutuhan cluster GPU hingga 4x lipat untuk beban kerja yang sama.
* **Tail Latency Spikes (p99/p99.9)**: Lonjakan throughput secara tiba-tiba tanpa mekanisme batching pintar menyebabkan memory contention dan backpressure yang destruktif, meningkatkan p99 latency dari puluhan milidetik menjadi puluhan detik (timeout cascading).
* **Multi-Tenant Serving & Heterogeneous Hardware**: Enterprise harus mampu melayani puluhan model heterogen (LLM, Vision Transformer, Embedding, Tabular) dalam cluster GPU yang sama secara aman tanpa resiko Out-of-Memory (OOM) satu model meruntuhkan model lainnya.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur end-to-end dari fase kompilasi model *offline* hingga eksekusi inferensi *runtime* terakselerasi dengan Triton Inference Server dan TensorRT:

```
========================================================================================
 FASE 1: OFFLINE COMPILATION & OPTIMIZATION PIPELINE
========================================================================================
 +--------------------+       +---------------------+       +-------------------------+
 | PyTorch Model (.pt)| ----> | Export to ONNX      | ----> | TensorRT Optimizer      |
 +--------------------+       | (Dynamic Axis Spec) |       | (Fusion, Precision,     |
                              +---------------------+       | Dynamic Shape Profiles) |
                                                            +-------------------------+
                                                                         |
                                                                         v
                                                            +-------------------------+
                                                            | Serialized Plan Engine  |
                                                            | (model.plan)            |
                                                            +-------------------------+

========================================================================================
 FASE 2: RUNTIME INFERENCE SERVING (TRITON INFERENCE SERVER)
========================================================================================

  Client HTTP/2 / gRPC Requests
     |              |
     v              v
 +------------------------------------------------------------------------------------+
 | TRITON INFERENCE SERVER CORE (C++ Engine)                                          |
 |                                                                                    |
 |  +------------------------------------------------------------------------------+  |
 |  | Front-End Request Handler (HTTP/REST & gRPC Server)                          |  |
 |  +------------------------------------------------------------------------------+  |
 |         |                                                                          |
 |         v                                                                          |
 |  +------------------------------------------------------------------------------+  |
 |  | Dynamic Batch Scheduler                                                      |  |
 |  |   Queue: [Req 1] -> [Req 2] -> [Req 3]                                        |  |
 |  |   Criteria: max_queue_delay_microseconds: 5000 | max_batch_size: 64           |  |
 |  +------------------------------------------------------------------------------+  |
 |         |                                                                          |
 |         v (Batched Input Tensors via Shared Memory / CUDA Pinned Memory)           |
 |  +------------------------------------------------------------------------------+  |
 |  | Model Instance Manager (Concurrency / Thread Pool)                           |  |
 |  |                                                                              |  |
 |  |   +--------------------------+          +--------------------------+         |  |
 |  |   | Instance Group 0 (GPU 0) |          | Instance Group 1 (GPU 0) |         |  |
 |  |   | TensorRT Execution Context|         | TensorRT Execution Context|         |  |
 |  |   +--------------------------+          +--------------------------+         |  |
 |  |                 \                                   /                        |  |
 |  +------------------\---------------------------------/-------------------------+  |
 +----------------------\-------------------------------/-----------------------------+
                         v                             v
           +----------------------------------------------------------+
           | NVIDIA HARDWARE (Streaming Multiprocessors & HBM/VRAM)   |
           |   [TensorRT Fused Kernels Execution via CUDA Stream]     |
           +----------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Dynamic Batching Engine & Latency Trade-off
Dynamic batching adalah algoritma penjadwalan antrean yang bertindak sebagai buffer adaptif. Ketika request $R_1$ tiba di waktu $t_0$, scheduler tidak langsung mengirimnya ke GPU. Scheduler memulai *countdown timer* sepanjang $\Delta t$ (`max_queue_delay_microseconds`). 

Jika request lanjutan $R_2, R_3, \dots, R_k$ tiba sebelum $\Delta t$ habis dan $k \le \text{max\_batch\_size}$, scheduler menggabungkan seluruh request tersebut menjadi satu continuous tensor berdimensi:
$$\text{Batch Shape} = [k, \text{dim}_1, \text{dim}_2, \dots]$$

Jika waktu $\Delta t$ tercapai sebelum batch penuh, scheduler mengeksekusi inferensi parsial sebesar elemen yang terkumpul. Pendekatan ini mengubah trade-off komputasi secara dramatis:
* **Latency Trade-off**: Menambahkan deterministik penundaan maksimal sebesar $\Delta t$ pada p50 latency, namun meningkatkan throughput sistemik secara eksponensial dan menstabilkan p99 latency ketika traffic spike.

#### Graph Compilers (TensorRT Internal Transformations)
TensorRT mengonversi graf komputasi ONNX menjadi representasi internal yang dioptimasi secara mendalam melalui beberapa tahapan inti:
1. **Vertical Layer Fusion**: Menggabungkan layer sekuensial. Contoh: Operasi `Convolution`, dilanjutkan dengan penambahan `Bias`, lalu aktivasi `ReLU`, dieksekusi dalam satu CUDA kernel tunggal. Hal ini mengeliminasi penulisan aktivasi intermediat ke VRAM (*memory roundtrip bottleneck*).
2. **Horizontal Layer Fusion**: Menggabungkan beberapa layer independen yang membaca input yang sama tetapi memproses arah komputasi yang paralel (seperti projection matrix $Q, K, V$ pada arsitektur Attention Transformer) menjadi satu kernel komputasi besar.
3. **Kernel Auto-Tuning**: Selama fase kompilasi (*engine build phase*), compiler melakukan *benchmarking langsung* di atas target fisik GPU yang dituju. Compiler menguji ratusan variasi algoritma kernel konvolusi/matriks (misal: algoritma Winograd, Direct GEMM, FFT) untuk menentukan algoritma tercepat spesifik terhadap bentuk dimensi tensor target.
4. **Precision Quantization (Calibration)**: Mengonversi weight dan activation tensor dari FP32 (32-bit floating point) ke FP16 atau INT8. Untuk INT8, TensorRT menggunakan algoritma *Kullback-Leibler (KL) Divergence Minimization* untuk menentukan rentang *dynamic range scaling factor* aktivasi tanpa mengorbankan akurasi model.

#### Zero-Copy Memory Management & CUDA IPC
Dalam skenario throughput tinggi, serialisasi JSON melalui REST HTTP menjadi bottleneck utama (dapat memakan hingga 70% waktu total eksekusi). Arsitektur modern menggunakan protokol binary gRPC berlandaskan **CUDA Inter-Process Communication (CUDA IPC)** atau **POSIX System Shared Memory**:
* Server dan Client berjalan pada node yang sama (atau pod Kubernetes yang sama melalui IPC shared volume).
* Client menulis data input langsung ke buffer memori bersama (*shared memory*).
* Triton hanya menerima pointer alamat memori fisik buffer tersebut melalui payload gRPC yang sangat kecil.
* GPU membaca input langsung dari pinned memory via DMA (Direct Memory Access), menghilangkan *memory copy overhead* antara user space, kernel space, dan GPU VRAM.

---

### 6. Production-Ready Code Implementation

Implementasi berikut terdiri dari dua komponen modular standar enterprise:
1. **TensorRT Compilation Engine Builder**: Otomasi konversi model ONNX ke TensorRT Engine dengan konfigurasi *dynamic shapes*, optimasi alokasi workspace, dan fallback mode presisi.
2. **High-Performance Asynchronous Triton Serving Client**: Klien berbasis Python `asyncio` dan `tritonclient.grpc.aio` dengan error handling, tracking latensi inferensi, dan validasi response.

#### Komponen 1: Production TensorRT Builder (`trt_compiler.py`)

```python
"""
TensorRT Engine Compilation Pipeline for Enterprise Deployment.
Requires: tensorrt >= 8.6.0, cuda-python
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Tuple

import tensorrt as trt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TRTCompiler")


class TensorRTCompiler:
    def __init__(self, trt_logger_level: trt.ILogger.Severity = trt.ILogger.WARNING) -> None:
        self.logger = trt.Logger(trt_logger_level)
        trt.init_libnvinfer_plugins(self.logger, namespace="")
        self.builder = trt.Builder(self.logger)
        self.config = self.builder.create_builder_config()

    def build_engine(
        self,
        onnx_model_path: Path | str,
        output_engine_path: Path | str,
        dynamic_shapes: Dict[str, Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[int, ...]]],
        enable_fp16: bool = True,
        max_workspace_bytes: int = 4 * 1024 * 1024 * 1024,  # 4 GB
    ) -> None:
        """
        Builds and serializes a TensorRT Engine from an ONNX graph.

        Args:
            onnx_model_path: Path to the input .onnx file.
            output_engine_path: Path where the .plan engine will be saved.
            dynamic_shapes: Mapping of input name -> (min_shape, optimal_shape, max_shape).
            enable_fp16: Flag to enable mixed precision FP16 kernels.
            max_workspace_bytes: Maximum GPU memory allocated during kernel auto-tuning.
        """
        onnx_path = Path(onnx_model_path)
        out_path = Path(output_engine_path)

        if not onnx_path.exists():
            raise FileNotFoundError(f"Source ONNX file not found at: {onnx_path}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        flag = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = self.builder.create_network(flag)
        parser = trt.OnnxParser(network, self.logger)

        logger.info(f"Parsing ONNX graph from: {onnx_path}")
        with open(onnx_path, "rb") as model_file:
            if not parser.parse(model_file.read()):
                error_msgs = "\n".join(
                    [str(parser.get_error(i)) for i in range(parser.num_errors)]
                )
                raise RuntimeError(f"Failed to parse ONNX network:\n{error_msgs}")

        # Set Workspace Size Pool
        self.config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, max_workspace_bytes)

        # Precision flags
        if enable_fp16:
            if not self.builder.platform_has_fast_fp16:
                logger.warning("Target hardware does not have fast FP16 compute cores. Falling back.")
            else:
                self.config.set_flag(trt.BuilderFlag.FP16)
                logger.info("FP16 precision execution enabled.")

        # Dynamic Shape Optimization Profiles
        profile = self.builder.create_optimization_profile()
        for input_name, (min_s, opt_s, max_s) in dynamic_shapes.items():
            logger.info(
                f"Configuring Profile for '{input_name}': Min={min_s}, Opt={opt_s}, Max={max_s}"
            )
            profile.set_shape(input_name, min_s, opt_s, max_s)

        self.config.add_optimization_profile(profile)

        logger.info("Building TensorRT execution engine (this can take several minutes)...")
        serialized_engine = self.builder.build_serialized_network(network, self.config)

        if serialized_engine is None:
            raise RuntimeError("Engine build failed. Check CUDA errors or hardware limits.")

        logger.info(f"Saving compiled engine binary to: {out_path}")
        with open(out_path, "wb") as f:
            f.write(serialized_engine)
        logger.info("Engine successfully compiled and serialized.")


if __name__ == "__main__":
    compiler = TensorRTCompiler()
    # Contoh dynamic batching: input batch size dinamis dari 1 hingga 32
    # Tensor input: 'input_ids' dengan sequence length tetap 128
    DUMMY_DYNAMIC_PROFILES = {
        "input_ids": (
            (1, 128),   # MIN: batch size 1
            (8, 128),   # OPT: batch size 8 (prioritas optimasi autotuning)
            (32, 128),  # MAX: batch size 32
        )
    }
    
    # Placeholder execution call:
    # compiler.build_engine("model.onnx", "model_repository/transformer/1/model.plan", DUMMY_DYNAMIC_PROFILES)
```

---

#### Komponen 2: Konfigurasi Triton Model (`config.pbtxt`)

Simpan file berikut di `model_repository/transformer/config.pbtxt`:

```protobuf
name: "transformer"
platform: "tensorrt_plan"
max_batch_size: 32

input [
  {
    name: "input_ids"
    data_type: TYPE_INT32
    dims: [ 128 ]
  }
]

output [
  {
    name: "logits"
    data_type: TYPE_FP32
    dims: [ 128, 768 ]
  }
]

# Konfigurasi Dynamic Batching
dynamic_batching {
  max_queue_delay_microseconds: 4000
  preferred_batch_size: [ 8, 16, 32 ]
}

# Multi-Instance Concurrency (Scale execution instances horizontally across single/multi GPU)
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

---

#### Komponen 3: Production Asynchronous Serving Client (`triton_async_client.py`)

```python
"""
Industrial-grade Asynchronous Triton gRPC Client.
Handles connection health checks, serialization, dynamic inference, and latency metrics.
Requires: tritonclient[grpc] >= 2.34.0, numpy
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import tritonclient.grpc.aio as grpcclient
from tritonclient.utils import InferenceServerException

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TritonClient")


@dataclass(frozen=True)
class InferenceMetrics:
    client_latency_ms: float
    request_id: str
    is_success: bool
    error_message: Optional[str] = None


class ProductionTritonClient:
    def __init__(self, server_url: str = "localhost:8001", connection_timeout: float = 5.0) -> None:
        self.server_url = server_url
        self.connection_timeout = connection_timeout
        self._client: Optional[grpcclient.InferenceServerClient] = None

    async def initialize(self) -> None:
        """Establishes connection and asserts server readines."""
        try:
            self._client = grpcclient.InferenceServerClient(
                url=self.server_url,
                channel_args=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.http2.max_pings_without_data", 0),
                ]
            )
            # Ensure the server is live and ready
            if not await self._client.is_server_live():
                raise ConnectionError(f"Triton server at {self.server_url} is not live.")
            if not await self._client.is_server_ready():
                raise ConnectionError(f"Triton server at {self.server_url} is not ready.")
            
            logger.info(f"Successfully connected to Triton server at: {self.server_url}")
        except Exception as e:
            logger.error(f"Failed to connect to inference server: {str(e)}")
            await self.close()
            raise

    async def infer(
        self,
        model_name: str,
        input_data: np.ndarray,
        request_id: str,
        model_version: str = "1"
    ) -> Tuple[np.ndarray, InferenceMetrics]:
        """
        Executes an asynchronous inference request with strict error handling and tracing.

        Args:
            model_name: Target model identifier.
            input_data: Numpy array matching expected model input shape (excluding dynamic batch).
            request_id: Unique string to track telemetry.
            model_version: String version of the target model artifact.

        Returns:
            Tuple of (output_array, InferenceMetrics).
        """
        if self._client is None:
            raise RuntimeError("Client is not initialized. Call initialize() first.")

        start_time = time.perf_counter()

        # Konfigurasi Input Tensor
        inputs: List[grpcclient.InferInput] = []
        input_tensor = grpcclient.InferInput("input_ids", input_data.shape, "INT32")
        input_tensor.set_data_from_numpy(input_data)
        inputs.append(input_tensor)

        # Konfigurasi Output Request
        outputs: List[grpcclient.InferRequestedOutput] = []
        outputs.append(grpcclient.InferRequestedOutput("logits"))

        try:
            # Mengirimkan request melalui gRPC pipeline
            response = await self._client.infer(
                model_name=model_name,
                model_version=model_version,
                inputs=inputs,
                outputs=outputs,
                request_id=request_id,
                timeout=self.connection_timeout
            )
            
            output_arr = response.as_numpy("logits")
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            metrics = InferenceMetrics(
                client_latency_ms=duration_ms,
                request_id=request_id,
                is_success=True
            )
            return output_arr, metrics

        except InferenceServerException as ise:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"InferenceServerException on req {request_id}: {ise.message()} (Status: {ise.status()})")
            metrics = InferenceMetrics(
                client_latency_ms=duration_ms,
                request_id=request_id,
                is_success=False,
                error_message=ise.message()
            )
            raise
        except Exception as ex:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Unexpected error executing inference req {request_id}: {str(ex)}")
            metrics = InferenceMetrics(
                client_latency_ms=duration_ms,
                request_id=request_id,
                is_success=False,
                error_message=str(ex)
            )
            raise
            
    async def close(self) -> None:
        """Closes gRPC client channels gracefully."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Triton gRPC connection pool closed.")


async def main():
    client = ProductionTritonClient(server_url="localhost:8001")
    try:
        await client.initialize()
        
        # Simulasi Input Data Batching (Shape: [Batch=1, SeqLen=128])
        dummy_input = np.ones((1, 128), dtype=np.int32)
        
        # Mengirim beberapa request secara concurrent menggunakan asyncio.gather
        tasks = [
            client.infer(
                model_name="transformer", 
                input_data=dummy_input, 
                request_id=f"req-uuid-{i}"
            )
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Task encountered error: {res}")
            else:
                output, metrics = res
                logger.info(f"Req {metrics.request_id} processed in {metrics.client_latency_ms:.2f} ms with output shape {output.shape}")
                
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

*   **VRAM Out of Memory (OOM) During Engine Build**:
    *   *Mekanisme*: TensorRT mengevaluasi ratusan algoritma kernel secara paralel dan mengalokasikan workspace memori besar secara agresif.
    *   *Mitigasi*: Batasi parameter `set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, limit_in_bytes)`. Jangan pernah menjalankan kompilasi TensorRT bersamaan dengan proses serving yang sedang aktif di GPU yang sama.
*   **Dynamic Shape Divergence**:
    *   *Mekanisme*: Client mengirimkan input tensor dengan shape yang keluar dari batas profil optimasi (`min_shape` atau `max_shape`).
    *   *Dampak*: Server Triton melempar error `INVALID_ARG` seketika dan menolak eksekusi graf komputasi.
    *   *Mitigasi*: Tambahkan layer input validation/padding di level client proxy atau gunakan fitur Triton *Sequence/Dynamic Batching Padding* untuk menormalkan shape sebelum masuk ke execution engine.
*   **Queue Starvation & Cascading Tail Latency**:
    *   *Mekanisme*: Nilai `max_queue_delay_microseconds` disetel terlalu tinggi (misal: > 50 ms) pada sistem dengan traffic rendah. Request individual tertahan lama hanya untuk menunggu batch penuh yang tidak kunjung datang.
    *   *Mitigasi*: Lakukan load profiling sistematis. Nilai `max_queue_delay_microseconds` harus berada pada rentang 5–15% dari target latency SLA aplikasi (umumnya antara 1.000 hingga 5.000 $\mu s$).
*   **CUDA Context Corruption**:
    *   *Mekanisme*: Unhandled segmentation fault pada salah satu custom C++ backend engine merusak driver context GPU.
    *   *Dampak*: Seluruh model instance di GPU yang sama gagal melayani request lanjutan (*GPU fell off the bus*).
    *   *Mitigasi*: Gunakan *Triton Health Probes* (`/v2/health/ready`) terintegrasi dengan Kubernetes Liveness & Readiness Probes untuk me-restart pod secara terisolasi.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter / Arsitektur | Triton + TensorRT Engine | vLLM Engine (PagedAttention) | Vanilla PyTorch (TorchServe) |
| :--- | :--- | :--- | :--- |
| **Kasus Penggunaan Optimal** | Heterogeneous Models (CNN, ViT, BERT, Tabular, Audio) | LLM Spesifik (Generative Autoregressive Transformer) | Prototyping, Model yang sering di-retrain |
| **Throughput (QPS)** | **Sangat Tinggi** (Fused C++ Kernels) | **Sangat Tinggi** (Khusus LLM Token Decoding) | Rendah (GIL & Python Overhead) |
| **Latency SLA (p99)** | **Deterministik & Terendah** (<10 ms feasible) | Dinamis tergantung input context & output generation | Fluktuatif (Tergantung Garbage Collection & GIL) |
| **Compile Time Overhead** | Sangat Lama (Memerlukan kompilasi AOT per tipe GPU) | Rendah (JIT compiling kernels via Triton-Lang) | **Nol** (Interpretatif langsung dari `.pt`) |
| **Fleksibilitas Graf** | Kaku (Bentuk tensor dibatasi profil dynamic shape) | Fleksibel terhadap context length bervariasi | **Sangat Fleksibel** (Eksekusi Python arbitrary) |

---

### 9. Best Practices & Standard Industri

1. **Strict Versioning Repository Structure**:
   Selalu pisahkan artefak model menggunakan model repository format deterministik Triton:
   ```text
   model_repository/
   └── <model_name>/
       ├── config.pbtxt
       ├── 1/
       │   └── model.plan   <-- Serialized TensorRT engine
       └── 2/
           └── model.plan
   ```
2. **Deterministic Pre-Warming**:
   Engine TensorRT yang baru dimuat (*cold state*) sering kali memiliki latensi spike pada request pertama karena initial GPU memory paging. Jalankan warmup script menggunakan input sintetik saat inisialisasi pod sebelum mengalihkan traffic load balancer.
3. **Pemberian Metrik Observability via Prometheus**:
   Pantau metrik standar industri yang disediakan Triton secara bawaan pada port `:8002`:
   * `nv_inference_request_duration_us`: Durasi inferensi aktual pada GPU.
   * `nv_inference_queue_duration_us`: Waktu tunggu tensor dalam antrean dynamic batching. Jika metrik ini naik melampaui SLA, segera trigger *Horizontal Pod Autoscaler (HPA)*.
   * `nv_gpu_utilization` & `nv_gpu_memory_used`: Pemantauan saturasi compute dan fragmentasi VRAM.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas mengoptimalkan microservice ekstraksi fitur yang mengalami kegagalan memenuhi SLA latensi (target p99 < 15ms pada beban 1.000 QPS). Anda akan mengekspor model Transformer sederhana, mengompilasinya menjadi engine TensorRT dengan FP16, mengonfigurasi Triton Dynamic Batching, dan memvalidasi throughput menggunakan alat uji beban.

#### Langkah 1: Persiapan Environment
Pastikan Anda berada di lingkungan dengan GPU NVIDIA (Compute Capability >= 7.0) dan Docker terpasang dengan NVIDIA Container Toolkit.

```bash
# Buat direktori kerja
mkdir -p triton_lab/model_repository/feature_extractor/1
cd triton_lab
```

#### Langkah 2: Buat Model Dummy dan Ekspor ke ONNX
Simpan skrip berikut sebagai `export_onnx.py` dan jalankan:

```python
import torch
import torch.nn as nn

class FeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(128, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 64)
        )
    def forward(self, x):
        return self.encoder(x)

model = FeatureExtractor().eval().cuda()
dummy_input = torch.randn(1, 128, device='cuda')

# Ekspor dengan dynamic batch axis
torch.onnx.export(
    model,
    dummy_input,
    "feature_extractor.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={
        "input": {0: "batch_size"},
        "output": {0: "batch_size"}
    },
    opset_version=17
)
print("ONNX export completed successfully.")
```
```bash
python3 export_onnx.py
```

#### Langkah 3: Kompilasi ONNX ke TensorRT Engine Menggunakan `trtexec`
Gunakan tool utilitas bawaan `trtexec` di dalam container NVIDIA TensorRT:

```bash
docker run --gpus all --rm -v $(pwd):/workspace nvcr.io/nvidia/tensorrt:23.08-py3 \
  trtexec --onnx=/workspace/feature_extractor.onnx \
          --saveEngine=/workspace/model_repository/feature_extractor/1/model.plan \
          --fp16 \
          --minShapes=input:1x128 \
          --optShapes=input:16x128 \
          --maxShapes=input:64x128 \
          --workspace=2048
```

#### Langkah 4: Tulis Konfigurasi Server (`config.pbtxt`)
Buat file `model_repository/feature_extractor/config.pbtxt`:

```protobuf
name: "feature_extractor"
platform: "tensorrt_plan"
max_batch_size: 64

input [
  {
    name: "input"
    data_type: TYPE_FP32
    dims: [ 128 ]
  }
]

output [
  {
    name: "output"
    data_type: TYPE_FP32
    dims: [ 64 ]
  }
]

dynamic_batching {
  max_queue_delay_microseconds: 3000
  preferred_batch_size: [ 8, 16, 32, 64 ]
}

instance_group [
  {
    count: 2
    kind: KIND_GPU
  }
]
```

#### Langkah 5: Jalankan Triton Inference Server
Jalankan container Triton Server dengan me-mount direktori model:

```bash
docker run --gpus all --rm -d \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repository:/models \
  --name triton-serving-lab \
  nvcr.io/nvidia/tritonserver:23.08-py3 \
  tritonserver --model-repository=/models
```

Periksa kesiapan server:
```bash
curl -v localhost:8000/v2/health/ready
# Output HTTP 200 OK menandakan server siap melayani inferensi.
```

#### Langkah 6: Validasi & Stress Testing dengan `perf_analyzer`
Gunakan `perf_analyzer` untuk mengukur p99 latency dan throughput di bawah simulasi beban concurrent:

```bash
docker run --gpus all --rm --net=host \
  nvcr.io/nvidia/tritonserver:23.08-py3-sdk \
  perf_analyzer -m feature_extractor \
                -u localhost:8001 \
                -i grpc \
                --concurrency-range 4:32:4 \
                --shape input:128 \
                --percentile=99
```

#### Kriteria Keberhasilan Validasi Lab:
1. `perf_analyzer` mencatat throughput melebihi 5.000 request per second (Inferences/Second).
2. p99 latency tetap stabil di bawah 10 ms pada konkurensi request tinggi.
3. Server metrics pada `curl localhost:8002/metrics` menunjukkan parameter dynamic batching berhasil mengonsolidasikan request secara otomatis tanpa penolakan request (`EXEC_COUNT` meningkat seiring bertambahnya beban).