# Bab 07: High-Throughput Model Serving & Deployment Patterns
## Module 01: Low-Latency Inference Engines, Dynamic Batching & gRPC Protocol Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis Profil Latensi & Throughput (Compute vs. Memory Bound):** Mengidentifikasi bottleneck inferensi pada level hardware (FLOPs vs. Memory Bandwidth) dan runtime execution engine untuk menentukan batasan P99 SLA.
*   **Mengimplementasikan Dynamic Batching Engine:** Merancang dan mengonfigurasi mekanisme *adaptive queueing* dengan parameter `max_batch_size` dan `max_queue_delay_microseconds` untuk memaksimalkan saturasi GPU tanpa melanggar latency budget.
*   **Membangun Pipeline Servicing Berbasis gRPC & Protocol Buffers:** Menggantikan REST/JSON overhead dengan serialisasi biner *strongly-typed* berbasis HTTP/2 untuk meminimalkan CPU serialization cost dan transport latency.
*   **Mengelola Konkurensi & Memory Isolation:** Mengorkestrasi inferensi asinkron (*non-blocking event loops*) dengan thread worker pools, pinned host memory (page-locked), dan CUDA streams untuk mengeksekusi multi-tenant model serving yang aman terhadap *Out-of-Memory* (OOM).
*   **Mengevaluasi Trade-Offs Framework Serving:** Memilih arsitektur serving yang optimal (Triton Inference Server, vLLM/TGI, TorchServe, vs. Custom Async C++/Python Engine) berdasarkan karakteristik beban kerja enterprise.

---

### 2. Concept Overview

Menyajikan model machine learning di lingkungan produksi memerlukan pergeseran paradigma dari *development code* (PyTorch/TensorFlow eager execution) ke *production runtime optimization*. Secara fundamental, sistem inferensi modern beroperasi di bawah batasan hukum Amdahl dan trade-off klasik antara **Latency** (waktu pemrosesan satu request, $L$) dan **Throughput** (jumlah request per detik yang dapat diproses sistem, $QPS$ atau $RPS$).

```
Throughput (QPS) = Concurrent Requests / Latency (detik)
```

#### Mental Model: The Restaurant Kitchen Analogy
Bayangkan dapur restoran (GPU/Akselerator) dengan koki berkecepatan tinggi yang mampu memanggang 16 piring steik sekaligus dalam 500 ms.
*   **Naive Serving (Single-item REST API):** Pelayan membawa 1 pesanan steik ke dapur setiap kali pesanan masuk. Koki memanggang 1 piring selama 500 ms. Kapasitas 15 slot panggangan terbuang percuma (GPU underutilization). Latensi = 500 ms, Throughput = 2 steik/detik.
*   **Dynamic Batching:** Pelayan menunggu pesanan terkumpul maksimal 50 ms. Jika dalam 50 ms terkumpul 8 pesanan (atau mencapai batas maksimal 16), pelayan langsung menyerahkannya ke dapur. Koki memanggang 8 steik secara paralel dalam 510 ms. Latensi individual bertambah sedikit (510 ms + waktu tunggu $\le$ 50 ms = 560 ms), tetapi Throughput melonjak drastis menjadi ~15.6 steik/detik.

#### Dua Regime Inferensi GPU
1.  **Compute-Bound (Compute Heavy):** Karakteristik operasi seperti perkalian matriks besar (GEMM) di mana waktu eksekusi didominasi oleh kecepatan arithmetic logic units (ALU/Tensor Cores). Ini terjadi pada batch size besar.
2.  **Memory-Bound (Bandwidth Heavy):** Karakteristik operasi seperti layer norm, activation function, atau autoregressive decoding (LLM token generation tahap *decode*) di mana GPU menghabiskan waktu menunggu data dipindahkan dari High Bandwidth Memory (HBM) ke SRAM/Cache. Dynamic batching menggeser beban dari regime *memory-bound* ke arah *compute-bound* dengan mengamortisasi overhead loading bobot model untuk banyak input sekaligus.

---

### 3. Why It Matters

Di level enterprise, implementasi serving naive (misalnya membungkus model PyTorch dengan Flask atau FastAPI sinkron di balik server Gunicorn) memicu kegagalan sistemik yang masif:

1.  **Pemborosan Biaya Infrastruktur Cloud (GPU Underutilization):** Instans GPU akselerator kelas enterprise (seperti NVIDIA A100/H100) berharga ribuan dolar per bulan. Menyajikan model dengan utilitas Tensor Core di bawah 15% akibat request single-item adalah inefisiensi belanja modal (CapEx/OpEx) yang fatal.
2.  **Tail Latency Catastrophe (P99/P99.9 Spike):** Ketika lonjakan traffic (*burst*) terjadi, model serving tanpa antrean dinamis yang terkontrol akan memicu pembengkakan antrean di tingkat OS/socket. Request akan mengalami *Head-of-Line (HoL) Blocking*, menyebabkan P99 latensi melonjak dari 40 ms menjadi 10.000 ms, yang berujung pada HTTP 504 Gateway Timeout.
3.  **CPU Deserialization Tax:** Payload JSON berukuran besar (misalnya embeddings vektor berdimensi tinggi atau raw image array) membebani CPU host secara intensif hanya untuk mem-parsing string JSON menjadi objek numerik sebelum sempat dikirim ke GPU. gRPC dengan biner Protocol Buffers memangkas overhead CPU ini hingga 80-90%.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan perjalanan request dari client hingga eksekusi inferensi pada akselerator hardware dengan isolasi layer:

```
[ Client Applications ]
        │  ▲
   gRPC │  │ Protobuf Streams (HTTP/2)
        ▼  │
┌────────────────────────────────────────────────────────────────────────┐
│                        gRPC INFERENCE FRONTEND                         │
│  ┌──────────────────────┐  ┌────────────────────────────────────────┐  │
│  │ RPC Request Handlers │  │ Connection Pool & Worker Event Loops   │  │
│  └──────────┬───────────┘  └────────────────────────────────────────┘  │
└─────────────┼──────────────────────────────────────────────────────────┘
              │ Enqueue Request (Payload + asyncio.Future)
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE DYNAMIC BATCHER                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Priority & Timeout-bounded In-Memory Ring Buffer / Deque         │  │
│  │ Triggers: (Queue Size >= max_batch_size) OR (Delay >= max_delay) │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────────────┼──────────────────────────────────┘
                                      │ Batch Tensor Dispatched
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   EXECUTION WORKER POOL & RUNTIME                      │
│                                                                        │
│   Host (CPU) RAM                Pinned Memory (Page-Locked)            │
│   ┌────────────────────────┐    ┌──────────────────────────────────┐   │
│   │ Assembled Batch Tensor │───>│ cudaMemcpyAsync (H2D)            │   │
│   └────────────────────────┘    └────────────────┬─────────────────┘   │
│                                                  │                     │
│ ─────────────────────────────────────────────────┼──────────────────── │
│   Device (GPU) Acceleration Layer                │                     │
│                                                  ▼                     │
│    ┌───────────────────────────────────────────────────────────────┐   │
│    │ CUDA Stream 1 (Execution Engine: ONNX Runtime / TensorRT)     │   │
│    │ Kernels: FP16/INT8 Tensor Cores Optimized Weights             │   │
│    └─────────────────────────────┬─────────────────────────────────┘   │
│                                  │ cudaMemcpyAsync (D2H)               │
│                                  ▼                                     │
│   Device Buffer ──────────> Pinned Memory ──────────> Output Splitter  │
└──────────────────────────────────────────────────────────────┼─────────┘
                                                               │
                     Resolve Specific Future for Each Client   │
                                                               ▼
                                                  [ Response to Client ]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Algoritma Dynamic Batching: Batch Formation Trigger
Dynamic batching beroperasi sebagai *leaky bucket* atau *sliding window* terbalik. Batcher mempertahankan antrean FIFO yang dilindungi oleh lock internal atau thread-safe deque. Sebuah batch dieksekusi jika dan hanya jika salah satu dari kondisi berikut terpenuhi pertama kali:

$$\text{Trigger Execution} \iff (N_{\text{items}} \ge B_{\text{max}}) \lor (t_{\text{current}} - t_{\text{first\_item\_queued}} \ge \Delta t_{\text{max}})$$

Di mana:
*   $N_{\text{items}}$: Jumlah item input yang menunggu di antrean.
*   $B_{\text{max}}$: `max_batch_size` (ditentukan berdasarkan batas memori GPU dan saturation curve).
*   $\Delta t_{\text{max}}$: `max_queue_delay_microseconds` (latensi maksimum yang diizinkan untuk dikorbankan demi efisiensi throughput).

#### 5.2 Host-to-Device (H2D) Overhead & Pinned Memory
Pada arsitektur PCI-Express (PCIe Gen4 x16 memiliki bandwidth teoritis ~31.5 GB/s, PCIe Gen5 ~63 GB/s):
*   **Pageable Memory:** Alokasi memori standar via `malloc()` berada di memori virtual OS yang dapat dipindahkan ke disk (swap). GPU tidak dapat mengakses data ini secara langsung via DMA (Direct Memory Access). CPU harus menyalin data ke *pinned memory* staging area sementara sebelum mentransfernya ke GPU VRAM.
*   **Page-Locked (Pinned) Memory:** Memori yang dialokasikan khusus via `cudaHostAlloc()` atau PyTorch `tensor.pin_memory()`. Memori ini dijamin berada di RAM fisik permanen. DMA controller pada GPU dapat langsung membaca area ini secara paralel terhadap eksekusi CPU tanpa intervensi kernel OS, memangkas transfer latency secara drastis.

#### 5.3 Asynchronous Execution via CUDA Streams
Eksekusi sinkron memblokir CPU thread hingga kernel GPU selesai berjalan (`cudaDeviceSynchronize()`). Dalam sistem inferensi high-throughput, kita menggunakan *CUDA Streams*. Setiap CUDA stream adalah antrean operasi GPU yang dieksekusi secara berurutan, namun antar stream yang berbeda dapat berjalan konkuren:
1.  Stream A: Mentransfer batch $k+1$ dari Host ke Device (`H2D`).
2.  Stream B: Mengeksekusi kernel komputasi untuk batch $k$.
3.  Stream C: Mentransfer hasil batch $k-1$ dari Device ke Host (`D2H`).

#### 5.4 Binary Serialization Overhead: Protobuf vs JSON
JSON adalah format teks murni. Mengirimkan array float berukuran `[1, 512]` via JSON mewajibkan pengonversian IEEE 754 floating-point 32-bit menjadi karakter ASCII string (misal: `-0.023415`), menambahkan koma, dan membungkus kurung siku. Pada sisi receiver, CPU harus mem-parsing token karakter, memvalidasi format string, dan mengonversinya kembali ke floating-point biner.

Protocol Buffers (Protobuf) memadatkan tensor langsung ke dalam memory layout byte mentah (`bytes` field) atau repeated packed primitives. Pengiriman tensor melalui gRPC dapat memanfaatkan *zero-copy* deserialization langsung ke NumPy pointer atau native C++ memory buffer.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end production server:
1.  **Definisi Skema gRPC (`inference.proto`)**
2.  **High-Throughput Async Inference Server dengan Dynamic Batcher (`server.py`)**

#### 6.1 Definisi Protobuf (`inference.proto`)

```protobuf
syntax = "proto3";

package inference;

service InferenceService {
  rpc Predict (PredictRequest) returns (PredictResponse);
}

message PredictRequest {
  string model_name = 1;
  repeated float features = 2; // Flat 1D array of features
  repeated int64 shape = 3;    // e.g., [1, 128]
}

message PredictResponse {
  repeated float predictions = 1;
  repeated int64 shape = 2;
  int64 batch_size_used = 3;
  double queue_delay_ms = 4;
}
```

> *Catatan kompilasi:* File di atas dikompilasi menggunakan perintah:  
> `python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inference.proto`

#### 6.2 Inference Server (`server.py`)

```python
"""
Production-Grade High-Throughput Inference Server
Architecture: AsyncIO + Worker Thread Pooling + Dynamic Batching Engine + ONNX Runtime
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent import futures
from dataclasses import dataclass, field
from typing import List, Optional

import grpc
import numpy as np
import onnxruntime as ort

# Import generated protobuf classes
import inference_pb2
import inference_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
)
logger = logging.getLogger("InferenceServer")


@dataclass
class QueueItem:
    input_data: np.ndarray
    future: asyncio.Future
    enqueued_time: float = field(default_factory=time.perf_counter)


class DynamicBatcher:
    """
    Thread-safe dynamic batcher running an event-driven flush loop.
    Batches incoming inference requests up to max_batch_size or max_delay_ms.
    """

    def __init__(
        self,
        model_runner: ONNXModelRunner,
        max_batch_size: int = 32,
        max_delay_ms: float = 10.0,
    ) -> None:
        self.model_runner = model_runner
        self.max_batch_size = max_batch_size
        self.max_delay_seconds = max_delay_ms / 1000.0
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._batching_loop())
        logger.info(
            "DynamicBatcher initialized (Max Batch: %d, Max Delay: %.2f ms)",
            self.max_batch_size,
            self.max_delay_seconds * 1000.0,
        )

    async def stop(self) -> None:
        self._shutdown_event.set()
        if self._worker_task:
            await self.queue.put(None)  # Sentinel to unblock queue.get()
            await self._worker_task
        logger.info("DynamicBatcher gracefully stopped.")

    async def enqueue(self, input_tensor: np.ndarray) -> tuple[np.ndarray, int, float]:
        """
        Enqueues an item and awaits completion of batch inference via Future.
        Returns: (output_tensor, batch_size_used, queue_delay_ms)
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        item = QueueItem(input_data=input_tensor, future=future)
        await self.queue.put(item)
        return await future

    async def _batching_loop(self) -> None:
        while not self._shutdown_event.is_set():
            first_item = await self.queue.get()
            if first_item is None:
                break

            items: List[QueueItem] = [first_item]
            start_time = time.perf_counter()

            # Drain queue until max_batch_size or deadline reached
            while len(items) < self.max_batch_size:
                elapsed = time.perf_counter() - start_time
                remaining_time = self.max_delay_seconds - elapsed

                if remaining_time <= 0:
                    break

                try:
                    next_item = await asyncio.wait_for(
                        self.queue.get(), timeout=remaining_time
                    )
                    if next_item is None:
                        break
                    items.append(next_item)
                except asyncio.TimeoutError:
                    break

            # Execute batch inference
            await self._process_batch(items)

    async def _process_batch(self, items: List[QueueItem]) -> None:
        batch_size = len(items)
        now = time.perf_counter()

        try:
            # Concatenate along batch axis (axis 0)
            stacked_inputs = np.concatenate([item.input_data for item in items], axis=0)

            # Delegate blocking model computation to worker thread pool
            loop = asyncio.get_running_loop()
            stacked_outputs = await loop.run_in_executor(
                None, self.model_runner.predict, stacked_inputs
            )

            # Demultiplex output tensors to client futures
            split_outputs = np.split(stacked_outputs, batch_size, axis=0)

            for item, output_slice in zip(items, split_outputs):
                if not item.future.cancelled():
                    queue_delay = (now - item.enqueued_time) * 1000.0
                    item.future.set_result((output_slice, batch_size, queue_delay))

        except Exception as exc:
            logger.exception("Batch execution failure: %s", exc)
            for item in items:
                if not item.future.cancelled():
                    item.future.set_exception(exc)


class ONNXModelRunner:
    """Encapsulates runtime sessions and hardware execution."""

    def __init__(self, model_path: str) -> None:
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 4
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        # Hardware execution provider configuration
        providers = [
            (
                "CUDAExecutionProvider",
                {
                    "device_id": 0,
                    "arena_extend_strategy": "kNextPowerOfTwo",
                    "gpu_mem_limit": 2 * 1024 * 1024 * 1024,  # 2 GB limit
                    "cudnn_conv_algo_search": "EXHAUSTIVE",
                    "do_copy_in_default_stream": True,
                },
            ),
            "CPUExecutionProvider",
        ]

        logger.info("Loading ONNX Session from %s", model_path)
        self.session = ort.InferenceSession(
            model_path, sess_options=sess_options, providers=providers
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def predict(self, batch_tensor: np.ndarray) -> np.ndarray:
        """Synchronous inference call invoked inside thread pool."""
        return self.session.run(
            [self.output_name], {self.input_name: batch_tensor.astype(np.float32)}
        )[0]


class InferenceServicer(inference_pb2_grpc.InferenceServiceServicer):
    """gRPC Service implementation handling ingress network calls."""

    def __init__(self, batcher: DynamicBatcher) -> None:
        self.batcher = batcher

    async def Predict(
        self,
        request: inference_pb2.PredictRequest,
        context: grpc.aio.ServicerContext,
    ) -> inference_pb2.PredictResponse:
        # Input validation
        if not request.features or not request.shape:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid input tensors")

        try:
            # Reshape input from 1D flat array to tensor shape
            np_data = np.array(request.features, dtype=np.float32).reshape(
                list(request.shape)
            )

            # Delegate to dynamic batcher
            result, batch_size, delay = await self.batcher.enqueue(np_data)

            # Construct Protobuf response
            return inference_pb2.PredictResponse(
                predictions=result.flatten().tolist(),
                shape=list(result.shape),
                batch_size_used=batch_size,
                queue_delay_ms=delay,
            )

        except ValueError as val_err:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, f"Shape mismatch: {val_err}"
            )
        except Exception as err:
            logger.error("Internal processing error: %s", err)
            context.abort(
                grpc.StatusCode.INTERNAL, "Inference engine computation error"
            )


async def serve() -> None:
    # 1. Initialize mock/real model artifact
    # Note: Assumes dynamic batch shape on axis 0: [None, 128]
    model_runner = ONNXModelRunner("model.onnx")

    # 2. Start Dynamic Batcher
    batcher = DynamicBatcher(
        model_runner=model_runner, max_batch_size=16, max_delay_ms=5.0
    )
    batcher.start()

    # 3. Initialize gRPC Async Server
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
            ("grpc.so_reuseport", 1),
        ]
    )

    inference_pb2_grpc.add_InferenceServiceServicer_to_server(
        InferenceServicer(batcher), server
    )

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logger.info("Serving gRPC traffic on %s", listen_addr)

    await server.start()

    async def graceful_shutdown():
        logger.warning("Initiating graceful shutdown sequence...")
        await server.stop(grace=5.0)
        await batcher.stop()

    # Handling loop execution
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await graceful_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
```

---

### 7. Edge Cases & Failure Modes

Sistem serving real-time high-concurrency rentan terhadap degradasi performa cascading jika edge case berikut tidak ditangani:

#### 1. Dynamic Shape Explosion & Memory Fragmentation
*   **Kasus:** Request yang masuk memiliki panjang sequence ($S$) yang bervariasi secara ekstrem (misal teks/NLP: request A memiliki 8 token, request B memiliki 4.096 token).
*   **Dampak:** Padding dilakukan ke sequence terpanjang (4.096 token) untuk seluruh batch. Hal ini menyebabkan komputasi mubazir (padding FLOPs > 90%) dan alokasi matriks perantara yang memicu GPU CUDA Out-Of-Memory (OOM).
*   **Mitigasi:** Gunakan *bucketing strategies* (mengelompokkan antrean berdasarkan rentang panjang dimensi: 0-128, 129-512, dst.) atau beralih ke dynamic sequence engine (seperti FlashAttention dengan PagedAttention) yang tidak memerlukan zero-padding pada dimensi memori.

#### 2. Head-of-Line (HoL) Blocking pada Timeouts
*   **Kasus:** Klien yang mengalami network drop memutuskan koneksi saat request sudah berada di dalam antrean Dynamic Batcher.
*   **Dampak:** Engine tetap memproses request tersebut di dalam batch, menghabiskan alokasi waktu komputasi GPU, kemudian gagal mengembalikan hasil ke channel gRPC yang sudah tertutup.
*   **Mitigasi:** Implementasikan pengecekan `context.is_active()` atau `future.cancelled()` secara periodik tepat sebelum perakitan batch dilakukan. Batalkan item yang sudah kadaluwarsa dari batch array.

#### 3. Poison Pill Inferences & Segmentation Faults
*   **Kasus:** Tensor bernilai NaN/Inf atau berdimensi anomali lolos ke layer C++ runtime engine (ONNX/TensorRT).
*   **Dampak:** Crash pada C++ level execution provider dapat membunuh seluruh proses master (*exit code 139 - SIGSEGV*), melumpuhkan seluruh container inference pod.
*   **Mitigasi:** Strict payload validation di layer Protobuf deserialization (cek finite bounds menggunakan numpy `np.isfinite()`), dan isolasi proses worker runtime dari gRPC networking layer menggunakan IPC (Inter-Process Communication) atau multiprocessing wrapper.

---

### 8. Trade-offs & Alternatif Solusi

Setiap arsitektur serving dirancang untuk mengorbankan salah satu dimensi performa demi dimensi lain:

| Arsitektur Serving | Latency (P99) | Throughput (QPS) | Kompleksitas Setup | Dynamic Batching Support | Model Concurrency / Multi-Instance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FastAPI + PyTorch (Naive)** | Buruk (~100-500ms) | Sangat Rendah (< 50) | Sangat Rendah | Manual / Eksternal | Terbatas (GIL Bound) |
| **TorchServe** | Sedang (~30-80ms) | Menengah (~300) | Menengah | Built-in (Config-based) | Baik (Multi-worker C++ backend) |
| **Custom Async gRPC + ONNX (Engine Kita)** | Sangat Rendah (~5-15ms) | Tinggi (~1,500+) | Tinggi | Kustom (Code-level logic) | Fleksibel via Thread/Process Pool |
| **NVIDIA Triton Inference Server** | Terendah (~2-8ms) | Maksimal (~5,000+) | Sangat Tinggi | C++ Native Dynamic Batcher | Ekstrem (Ensemble models, BLS, dynamic instances) |
| **vLLM / TGI (Khusus LLM)** | Optimal utk Token Gen | Ekstrem utk Dekoding | Menengah-Tinggi | PagedAttention Continuous Batching | Khusus Decoder-Only Transformer |

#### Keputusan Desain: gRPC vs. HTTP/REST
*   **Pilih gRPC jika:** Berada dalam komunikasi *East-West* (antar microservice internal), memerlukan streaming bi-direksional (misal: input audio kontinu / output token LLM), dan membutuhkan utilisasi CPU minimum pada serialization.
*   **Pilih HTTP/REST jika:** API terekspos langsung ke *North-South* client (browser/web publik), integrasi sederhana dengan API Gateway standar tanpa gRPC-Web proxy, dan payload kecil yang tidak sensitif terhadap overhead string JSON parsing.

---

### 9. Best Practices & Standard Industri

Untuk menjamin reliability kelas enterprise pada serving layer:

1.  **Engine Warm-Up Execution:** Saat container runtime melakukan bootstrapping, jalankan 10 hingga 50 siklus inferensi sintetis (*dummy data*) dengan representasi `max_batch_size`.
    *   *Alasan:* Framework seperti PyTorch/CUDA, ONNX Runtime, dan TensorRT melakukan inisialisasi kernel CUDA lazy-loading, alokasi memori memory arena, dan optimasi runtime saat batch pertama dieksekusi. Tanpa warm-up, request user pertama akan terkena penalti latensi hingga 5.000 ms.
2.  **NUMA Node CPU Pinning:** Konfigurasikan container (via `numactl` atau Kubernetes CPU Manager) agar CPU core worker dipin ke NUMA socket yang sama dengan PCIe slot di mana GPU terpasang.
    *   *Alasan:* Menghindari penalti latensi transfer PCIe bus yang melintasi *Ultra Path Interconnect (UPI)* antar CPU socket.
3.  **Adaptive Max Queue Delay:** Jangan menetapkan parameter `max_delay_ms` lebih besar dari 20% total target P99 Latency Budget. Jika P99 SLA adalah 50 ms, waktu tunggu dynamic batching tidak boleh melebihi 10 ms.
4.  **Graceful Backpressure:** Terapkan bounded memory queues. Jika antrean Dynamic Batcher penuh (misal antrean mencapai kapasitas 1.024 item), segera tolak request baru dengan status code `grpc.StatusCode.RESOURCE_EXHAUSTED` (HTTP 429 Too Many Requests) daripada membiarkan memori membengkak hingga container terkena Linux OOM Killer (`SIGKILL`).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta untuk membangun dan menguji high-throughput inference engine untuk model neural network dense, lalu mengevaluasi efisiensi dynamic batching terhadap latensi sistem saat menangani lonjakan request konkuren.

#### Langkah 1: Persiapan Environment
Pasang library yang dibutuhkan:
```bash
pip install numpy onnx onnxruntime grpcio grpcio-tools
```

#### Langkah 2: Buat Model ONNX Dummy
Buat skrip `create_model.py` untuk mengenerate model ONNX dengan batch axis dinamis:
```python
# create_model.py
import torch
import torch.nn as nn


class SimpleClassifier(nn.Module):

    def __init__(self):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, 2),
        )

    def forward(self, x):
        return self.fc(x)


model = SimpleClassifier().eval()
dummy_input = torch.randn(1, 128)

torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    opset_version=14,
)
print("model.onnx successfully generated.")
```
Jalankan skrip:
```bash
python create_model.py
```

#### Langkah 3: Compile Protobuf & Jalankan Server
Kompilasi protobuf (menggunakan schema dari Sub-bab 6.1):
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inference.proto
```
Jalankan server di terminal pertama:
```bash
python server.py
```

#### Langkah 4: Load Testing Client (Concurrent Benchmark)
Buat file `benchmark_client.py` untuk mengukur throughput dan respons batching di terminal kedua:
```python
# benchmark_client.py
import asyncio
import time
import grpc
import numpy as np
import inference_pb2
import inference_pb2_grpc


async def send_single_inference(
    stub: inference_pb2_grpc.InferenceServiceStub, req_id: int
):
    features = np.random.randn(1, 128).astype(np.float32).flatten().tolist()
    request = inference_pb2.PredictRequest(
        model_name="simple_classifier", features=features, shape=[1, 128]
    )

    start = time.perf_counter()
    response = await stub.Predict(request)
    duration = (time.perf_counter() - start) * 1000.0

    return {
        "id": req_id,
        "latency_ms": duration,
        "batch_size_used": response.batch_size_used,
        "queue_delay_ms": response.queue_delay_ms,
    }


async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = inference_pb2_grpc.InferenceServiceStub(channel)

        print("[Warmup] Sending single sync request...")
        await send_single_inference(stub, 0)

        print("[Benchmark] Launching 100 concurrent requests...")
        start_benchmark = time.perf_counter()
        tasks = [send_single_inference(stub, i) for i in range(1, 101)]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_benchmark

        latencies = [r["latency_ms"] for r in results]
        batches = [r["batch_size_used"] for r in results]

        print("\n=== BENCHMARK REPORT ===")
        print(f"Total Requests Processed : {len(results)}")
        print(f"Total Wall Time          : {total_time:.2f} s")
        print(f"Throughput               : {len(results)/total_time:.2f} QPS")
        print(f"Mean Latency             : {np.mean(latencies):.2f} ms")
        print(f"P95 Latency              : {np.percentile(latencies, 95):.2f} ms")
        print(f"P99 Latency              : {np.percentile(latencies, 99):.2f} ms")
        print(
            f"Average Batch Size Used  : {np.mean(batches):.2f} (Target Max: 16)"
        )
        print("========================")


if __name__ == "__main__":
    asyncio.run(main())
```
Jalankan benchmark client:
```bash
python benchmark_client.py
```

#### Output yang Diharapkan:
```text
=== BENCHMARK REPORT ===
Total Requests Processed : 100
Total Wall Time          : 0.15 s
Throughput               : 666.67 QPS
Mean Latency             : 12.30 ms
P95 Latency              : 14.80 ms
P99 Latency              : 15.20 ms
Average Batch Size Used  : 16.00 (Target Max: 16)
========================
```
*Analisis:* Perhatikan bahwa server secara otomatis menggabungkan 100 request konkuren ke dalam beberapa batch penuh berukuran 16, menghasilkan throughput tinggi (~600+ QPS) dengan latensi tetap rendah (~12 ms), membuktikan efisiensi algoritma dynamic batching yang telah dibangun.