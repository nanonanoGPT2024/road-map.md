# BAB 07: High-Throughput Model Serving & Deployment Patterns
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengonfigurasi Dynamic Batching Engine**: Mengoptimalkan throughput inferensi menggunakan Triton Inference Server atau vLLM dengan parameter batch delay dan queue size yang terikat pada target Service Level Objective (SLO) p99 latency.
- **Mengimplementasikan Pola Advanced Routing**: Mengonfigurasi *Shadow Traffic* (dark traffic), *Canary Deployment*, dan *A/B Testing* pada level L7 traffic mesh menggunakan Istio VirtualService dan Envoy Gateway untuk inferensi model AI.
- **Mengeliminasi Bottleneck Serialisasi dan Bus I/O**: Mengimplementasikan transmisi data zero-copy memanfaatkan CUDA Pinned Host Memory, System V Shared Memory, dan CUDA Inter-Process Communication (IPC).
- **Menganalisis dan Memitigasi Degradasi Memori GPU**: Memahami paging KV Cache (PagedAttention), fragmentation avoidance, serta mengonfigurasi Tensor Parallelism (TP) dan Pipeline Parallelism (PP) untuk model berskala besar di tahap serving.
- **Mengintegrasikan Observability Tingkat Lanjut**: Mengonfigurasi metrik inferensi real-time (compute vs queue latency, cache hit rate, GPU duty cycle) dan mengaitkannya ke autoscaler berbasis event (KEDA).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Arsitektur Sistem Terdistribusi**: Pemahaman protokol HTTP/2, gRPC, multiplexing, protocol buffers, dan service mesh (Envoy/Istio).
- **Fundamental Akselerasi Hardware (NVIDIA CUDA)**: Konsep dasar streaming multiprocessor (SM), CUDA streams, host-to-device memory transfers (`cudaMemcpy`), dan paging memori GPU.
- **Orkestrasi Container Tingkat Enterprise**: Kubernetes (K8s) manifests, CRDs, Custom Metrics API, Dynamic Resource Allocation (DRA) untuk vGPU/GPU Passthrough.
- **Python Concurrency & Systems Programming**: `asyncio`, memory buffers (`ctypes`, `numpy`), shared memory (`multiprocessing.shared_memory`), dan C-bindings.

---

### 3. Concept & Internal Architecture

Model serving konvensional yang dibangun di atas web server berbasis CPU (seperti Flask, FastAPI, atau Django yang memanggil runtime PyTorch) memicu kegagalan sistemik saat menerima beban konkuren tinggi:
1. **Python Global Interpreter Lock (GIL)** memblokir eksekusi thread multi-core untuk deserialisasi tensor.
2. Eksekusi inferensi berjalan secara serial atau memicu *thread contention* pada GPU runtime.
3. GPU Compute Core (Tensor Cores / CUDA Cores) mengalami *starvation* (idle) akibat latensi transfer bus PCI-e yang berulang-ulang untuk payload single-item.

#### Dynamic Batch Scheduler Internal Loop
Untuk mengatasi masalah efisiensi GPU, inference server enterprise (misalnya Triton Inference Server) menggunakan scheduler internal berbasis hardware queue:

```
[ Ingress Payload 1 ] ──┐
[ Ingress Payload 2 ] ──┼──> [ Priority Queue ] ──> [ Dynamic Batcher ]
[ Ingress Payload 3 ] ──┘         (Ring Buffer)      │
                                                     ├── max_queue_delay_microseconds: 5000
                                                     └── max_batch_size: 64
                                                             │
                                                             ▼
                                                [ Assembled Batch Matrix ]
                                                             │
                                                 (CUDA Pinned Host Memory)
                                                             │  cudaMemcpyAsync
                                                             ▼
                                                    [ GPU Device Memory ]
                                                             │
                                                    [ Execution Engine ]
                                               (TensorRT / ONNX / PyTorch)
```

Dynamic batch scheduler beroperasi menggunakan algoritma *time-bounded queue pooling*:
1. Request pertama masuk ke queue scheduler, memicu timer countdown `max_queue_delay_microseconds`.
2. Request berikutnya dimasukkan ke dalam batch yang sedang dibentuk hingga timer habis ATAU ukuran batch mencapai `max_batch_size`.
3. Scheduler membentuk *contiguous tensor memory block* langsung di host pinned memory (`cudaHostAlloc`), mengeksekusi transfer asinkron (`cudaMemcpyAsync`) melalui CUDA stream independen, dan melepaskan batch ke Tensor Cores tanpa menghentikan thread I/O pada ingress network.

#### LLM Serving & PagedAttention KV-Cache Memory Architecture
Pada Large Language Models (LLM), serving throughput dibatasi oleh alokasi memori untuk Key-Value (KV) Cache selama fase decoding autoregresif. 

Alokasi tradisional mengalokasikan contiguous virtual memory sebesar context window maksimum (misal: 8192 tokens) untuk setiap request. Hal ini memicu dua masalah besar:
- **Internal Fragmentation**: Alokasi dialokasikan untuk 8192 token, namun prompt pengguna hanya menghasilkan 200 token.
- **External Fragmentation**: Memori fisik GPU terpecah menjadi fragmen-fragmen kecil yang tidak bersebelahan, memicu CUDA Out-Of-Memory (OOM) meskipun memori bebas total masih mencukupi.

Arsitektur serving modern (vLLM / TensorRT-LLM) mengimplementasikan **PagedAttention**:

```
Logical KV Cache Blocks (Per Sequence)
Sequence A:  [ Block 0 ] ──> [ Block 1 ] ──> [ Block 2 ]
Sequence B:  [ Block 0 ] ──> [ Block 1 ]

                           │  Block Table Translation
                           ▼
Physical KV Cache Blocks (GPU DRAM Page Pool)
[ Physical Page 0x01 ] <── Seq A: Block 0
[ Physical Page 0x02 ] <── Seq B: Block 1
[ Physical Page 0x03 ] <── Free Page
[ Physical Page 0x04 ] <── Seq A: Block 2
[ Physical Page 0x05 ] <── Seq B: Block 0
[ Physical Page 0x06 ] <── Seq A: Block 1
```

PagedAttention membagi KV Cache menjadi blok-blok berukuran tetap (misalnya 16 token per halaman fisik). Sistem menggunakan *Block Table* untuk memetakan alokasi logis ke alamat fisik GPU yang tersebar secara dinamis. Pola ini memangkas pemborosan memori KV Cache dari ~60-80% menjadi di bawah 4%, memungkinkan penambahan throughput concurrency (batch size) hingga berkali-kali lipat pada kapasitas VRAM yang sama.

---

### 4. Why & What

| Dimensi | Naive Serving (FastAPI + PyTorch) | Enterprise Model Serving Engine (Triton / vLLM) |
| :--- | :--- | :--- |
| **Concurrency & Execution** | Terhambat Python GIL; eksekusi sekuensial per process worker. | Multi-threading native C++; concurrent model execution pools. |
| **Batching Mechanism** | Manual async loop; rentan timeout dan pemborosan CPU thread. | Algoritma dynamic batching native hardware berbasis hardware timer. |
| **Memory Allocation** | Alokasi VRAM dinamis; fragmentasi tinggi; rawan OOM. | Static VRAM pre-allocation; dynamic paging (PagedAttention); CUDA zero-copy. |
| **Protokol Komunikasi** | Umumnya terbatas pada HTTP/1.1 JSON (high parsing overhead). | Native HTTP/2 gRPC streaming, KServe v2 Data Plane standard, Shared Memory IPC. |
| **Hardware Saturation** | GPU Duty Cycle sering kali < 30% akibat data copy bottleneck. | GPU Duty Cycle stabil > 85% dengan pipelined queueing dan pinned memory. |

---

### 5. How: Workflow Detail

Alur hidup inferensi model high-throughput kelas enterprise:

```
[Client App]
     │
     ▼ (1) gRPC Request (Protobuf payload)
[L7 Envoy Gateway / Ingress]
     │
     ├─── (2a) Shadow Copy (Non-blocking) ──> [Experimental Model Pod (Canary)]
     │
     ▼ (2b) Primary Route
[Model Serving Engine: Triton Inference Server]
     │
     ▼ (3) gRPC Worker Thread
[System V / CUDA IPC Shared Memory Check]
     │
     ▼ (4) Enqueue ke Model Input Scheduler
[Dynamic Batching Buffer]
     ├─── Cek: queue_delay >= timeout ATAU batch_size == max_batch?
     │
     ▼ (5) Form Contiguous Batch Array
[CUDA Stream Manager]
     ├─── cudaMemcpyAsync (Host Pinned RAM -> GPU VRAM)
     │
     ▼ (6) Non-blocking Compute Execution
[Tensor Cores / Engine Runtime (TensorRT/ONNX)]
     ├─── Compute forward pass
     │
     ▼ (7) Result Generation
[CUDA Stream Synchronization]
     ├─── cudaMemcpyAsync (GPU VRAM -> Host Pinned RAM)
     │
     ▼ (8) gRPC Response Serialization
[Client App]
```

1. **Ingress & Traffic Splitting**: Klien memanggil endpoint via HTTP/2 gRPC. Service Mesh (Envoy) menerima payload dan mengaplikasikan routing policy (misal: 90% diarahkan ke baseline, 10% di-mirror ke shadow canary deployment).
2. **Buffer Ingestion & Zero-Copy**: Data dipetakan ke memory buffer. Jika data berada pada node K8s yang sama, runtime menggunakan System V Shared Memory (`shm_open`) atau CUDA IPC Memory handle untuk menghindari transfer TCP loopback.
3. **Queueing & Batch Formation**: Dynamic batch scheduler menahan request selama $\Delta t$ mikrodetik. Saat kondisi terpenuhi, scheduler membentuk batch homogen berdimensi $[B, \dots]$ langsung pada memori pinned.
4. **Asynchronous Execution**: Tensor dipindahkan ke GPU DRAM melalui dedicated CUDA Copy Stream. Eksekusi kernel dilakukan di Compute Stream yang terpisah secara asinkron tanpa memblokir CPU.
5. **Egress & Stream Back**: Hasil inferensi dikonversi kembali ke streaming protobuf gRPC response dan dikembalikan ke klien.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengangkutan Peti Kemas Pelabuhan
Bayangkan Anda menjalankan jasa pengiriman barang menggunakan kapal kargo raksasa (GPU).
- **Naive Serving (FastAPI)**: Setiap kali ada satu paket kiriman datang dari pelanggan, kapal langsung berlayar menyeberangi samudra untuk mengantar satu paket tersebut. Kapal berukuran masif tetapi hanya membawa 1 kg barang (GPU Compute Underutilized, konsumsi bahan bakar/energi tinggi, antrean pengirim lain memanjang).
- **Dynamic Batching Enterprise Engine**: Pelabuhan memiliki dermaga penampungan dengan batas toleransi waktu keberangkatan. Jika ada kiriman datang, kapal menunggu maksimal 10 menit (max delay) ATAU sampai kontainer kapal terisi penuh 1.000 paket (max batch size). Setelah salah satu syarat terpenuhi, kapal langsung berangkat membawa kapasitas optimal.

```
       INGRESS TRAFFIC ROUTING ARCHITECTURE (ISTIO + TRITON)
      
                               +-------------------+
                               |   Client Request  |
                               +---------+---------+
                                         |
                                         v
                         +-------------------------------+
                         |   Istio Ingress Gateway       |
                         |   (Envoy L7 Proxy Engine)     |
                         +---------------+---------------+
                                         |
                +------------------------+------------------------+
                |                                                 | (Mirror / Shadow 100%)
                | (Production Route 100%)                         v
                v                                   +---------------------------+
  +---------------------------+                     |  Triton Server (Canary)   |
  |  Triton Server (v1 - Stable)|                   |  - Model: FraudNet_v2     |
  |  - Model: FraudNet_v1     |                     |  - Output: Metrics Only   |
  |  - Execution: TensorRT    |                     |    (No state change)      |
  +-------------+-------------+                     +---------------------------+
                |
                v
  +-------------------------------------------------------------+
  |                   TRITON INTERNALS (POD)                    |
  |                                                             |
  |   +-----------------------------------------------------+   |
  |   |             gRPC Service Endpoint (HTTP/2)          |   |
  |   +--------------------------+--------------------------+   |
  |                              |                              |
  |                              v                              |
  |   +-----------------------------------------------------+   |
  |   |       Dynamic Batch Scheduler & Priority Queue      |   |
  |   |  - Delay window: 5ms   - Max Batch: 128 items       |   |
  |   +--------------------------+--------------------------+   |
  |                              |                              |
  |             +----------------+----------------+             |
  |             v                                 v             |
  |   +--------------------+            +--------------------+  |
  |   | CUDA Stream 1      |            | CUDA Stream 2      |  |
  |   | Engine Instance #0 |            | Engine Instance #1 |  |
  |   +---------+----------+            +---------+----------+  |
  |             |                                 |             |
  |             +----------------+----------------+             |
  |                              v                              |
  |   +-----------------------------------------------------+   |
  |   |         Hardware Acceleration (NVIDIA A100/H100)    |   |
  |   |             Tensor Cores (FP16 / INT8)              |   |
  |   +-----------------------------------------------------+   |
  +-------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Triton Model Configuration (`config.pbtxt`)
Berikut adalah konfigurasi industri untuk model deep learning berbasis ONNX/TensorRT yang mengaktifkan dynamic batching, multi-instance execution, dan pinned memory optimization.

```protobuf
name: "fraud_detection_model"
platform: "tensorrt_plan"
max_batch_size: 128

input [
  {
    name: "dense_input"
    data_type: TYPE_FP32
    dims: [ 48 ]
  },
  {
    name: "sparse_input"
    data_type: TYPE_INT32
    dims: [ 16 ]
  }
]

output [
  {
    name: "probability"
    data_type: TYPE_FP32
    dims: [ 1 ]
  }
]

# Konfigurasi Dynamic Batch Scheduler
dynamic_batching {
  max_queue_delay_microseconds: 4000
  preferred_batch_size: [ 32, 64, 128 ]
  preserve_ordering: false
  priority_levels: 2
  default_priority_level: 1
}

# Skalabilitas Instance Tingkat Hardware (Multi-Worker Execution per GPU)
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

#### B. Practical Example: Production gRPC Client & Istio Shadow Routing

##### 1. High-Throughput Asynchronous Client (`client.py`)
Kode ini memanfaatkan `tritonclient.aio.grpc` dengan non-blocking event loops, keepalive ping gRPC enterprise, dan concurrency pools.

```python
#!/usr/bin/env python3
"""
Enterprise High-Throughput Asynchronous Client for Triton Inference Server
Features: gRPC streaming, zero memory recreation, keepalive tuning.
"""

import asyncio
import logging
import sys
import numpy as np
import tritonclient.aio.grpc as grpcclient
from tritonclient.grpc import service_pb2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("InferenceClient")

TRITON_ENDPOINT = "10.244.2.15:8001"
MODEL_NAME = "fraud_detection_model"
CONCURRENT_TASKS = 50

# Custom gRPC Channel Options untuk High-Throughput Enterprise Workloads
GRPC_CHANNEL_OPTIONS = [
    ("grpc.max_receive_message_length", 64 * 1024 * 1024),
    ("grpc.max_send_message_length", 64 * 1024 * 1024),
    ("grpc.keepalive_time_ms", 10000),
    ("grpc.keepalive_timeout_ms", 5000),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
]

async def send_inference_request(
    client: grpcclient.InferenceServerClient, 
    sample_id: int
) -> np.ndarray:
    """Mengirim request inferensi tunggal yang akan di-batch oleh server side."""
    try:
        # Generate dummy input arrays (Simulasi payload 1 dimensi tanpa batch dimension)
        dense_data = np.random.randn(48).astype(np.float32)
        sparse_data = np.random.randint(0, 1000, size=(16,)).astype(np.int32)

        # Inisialisasi Triton InferInput
        inputs = [
            grpcclient.InferInput("dense_input", [48], "FP32"),
            grpcclient.InferInput("sparse_input", [16], "INT32")
        ]
        inputs[0].set_data_from_numpy(dense_data)
        inputs[1].set_data_from_numpy(sparse_data)

        # Inisialisasi Triton InferRequestedOutput
        outputs = [grpcclient.InferRequestedOutput("probability")]

        # Eksekusi Asynchronous Inference Call
        response = await client.infer(
            model_name=MODEL_NAME,
            inputs=inputs,
            outputs=outputs,
            request_id=f"req_{sample_id}"
        )

        result_tensor = response.as_numpy("probability")
        return result_tensor

    except grpcclient.InferenceServerException as err:
        logger.error(f"Inference error on sample {sample_id}: {err.message()}")
        raise

async def worker_pool_executor(total_requests: int):
    """Menjalankan concurrent client calls via shared gRPC pool."""
    logger.info(f"Connecting to Triton server at: {TRITON_ENDPOINT}")
    
    async with grpcclient.InferenceServerClient(
        url=TRITON_ENDPOINT, 
        channel_args=GRPC_CHANNEL_OPTIONS
    ) as triton_client:
        
        # Validasi status kesiapan server
        if not await triton_client.is_model_ready(MODEL_NAME):
            logger.critical(f"Model {MODEL_NAME} is not ready for serving.")
            sys.exit(1)

        logger.info(f"Firing {total_requests} requests across concurrency pool...")
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)

        async def bounded_call(req_id: int):
            async with semaphore:
                return await send_inference_request(triton_client, req_id)

        tasks = [bounded_call(i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_ops = [res for res in results if not isinstance(res, Exception)]
        logger.info(f"Batch execution completed. Success rate: {len(successful_ops)}/{total_requests}")

if __name__ == "__main__":
    asyncio.run(worker_pool_executor(total_requests=500))
```

##### 2. Istio VirtualService: Dark/Shadow Traffic Routing (`virtual-service.yaml`)
Pola ini mengirimkan salinan 100% traffic produksi nyata ke model Canary tanpa memblokir alur utama atau mengembalikan respons Canary ke user.

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: fraud-detection-router
  namespace: ml-serving
spec:
  hosts:
  - "fraud-detection.internal.corp"
  gateways:
  - mesh
  - istio-system/internal-gateway
  http:
  - name: "fraud-detection-primary-with-shadow"
    match:
    - uri:
        prefix: /inference.v2.InferenceService/
    route:
    - destination:
        host: fraud-detector-stable.ml-serving.svc.cluster.local
        port:
          number: 8001
      weight: 100
    # Shadow / Mirroring Configuration
    mirror:
      host: fraud-detector-canary.ml-serving.svc.cluster.local
      port:
        number: 8001
    mirrorPercentage:
      value: 100.0
```

---

### 8. Real World Case Study: Enterprise Scale

#### Skenario FinTech: Real-time Anti-Fraud Pipeline
- **Entitas**: Payment Gateway Internasional (Tier-1 Bank).
- **Kebutuhan**: Memproses 40.000 transaksi/detik (QPS) pada jam puncak (peak hour).
- **Latency SLO**: Total SLA waktu eksekusi inferensi p99 < 12 ms.
- **Model**: Pipeline komposit yang terdiri dari LightGBM (ekstraksi tabular 200 fitur) + Deep Neural Network (Graph Attention Network untuk mendeteksi *money mule*).

#### Masalah Sistemik Awal
Arsitektur awal menggunakan FastAPI yang di-deploy di 200 pod Kubernetes CPU. 
- CPU utilization melonjak hingga 95%.
- Latensi p99 mencapai 140 ms akibat GC overhead dan thread swapping.
- Saat dipindahkan ke GPU via PyTorch TorchServe default, utilisasi GPU hanya 18% (*PCI-e bottle-necked*), memicu penumpukan antrean internal. Biaya infrastruktur mencapai $85.000/bulan untuk sewa compute GPU.

#### Solusi Arsitektural yang Diterapkan
1. **Transformasi Runtime**:
   - Model dikonversi ke **TensorRT Execution Engine** terkuantisasi FP16 dengan CUDA graph static memory traces.
2. **Dynamic Batching Hyperparameter Tuning**:
   - Mengatur `max_queue_delay_microseconds: 3000` (3 ms).
   - Mengatur `max_batch_size: 256`.
3. **Deployment Pattern**:
   - Mengimplementasikan Istio L7 ingress dengan gRPC multiplexing.
   - Mengaktifkan pinned host memory pool berukuran 8 GB pada Triton pod manifest (`IPC_LOCK` privilege).

#### Hasil Pasca-Implementasi
- **Throughput**: Mampu melayani 52.000 QPS stabil dengan hanya 8 instance GPU NVIDIA A100.
- **Latency**: P99 turun drastis ke level **7.8 ms** (jauh di bawah batas toleransi 12 ms).
- **GPU Duty Cycle**: Utilisasi GPU meningkat dari 18% ke **88%**.
- **Penghematan Biaya**: Mengurangi cluster footprint sebesar 62%, menghasilkan efisiensi biaya sebesar $52.000/bulan.

---

### 9. Trade-offs

| Dimensi Keputusan | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Batch Timeout Tuning** | Low Delay (misal: 500 $\mu s$) | High Delay (misal: 15.000 $\mu s$) | **Low Delay**: Latensi per request rendah, tetapi batch size kecil $\rightarrow$ throughput rendah, cost per inference mahal.<br>**High Delay**: Throughput masif, saturasi GPU tinggi, tetapi latensi p99 baseline meningkat secara artifisial. |
| **Model Routing Strategy** | In-Cluster Dark/Shadow Traffic | Canary Deployment Traffic Split | **Shadow**: Aman tanpa risiko dampak ke user, tetapi menggandakan resource cost compute backend (100% redundant inference load).<br>**Canary**: Hemat resource, tetapi membawa risiko degradasi metrik/error bisnis ke porsi pengguna aktif yang terkena split. |
| **Engine Quantization** | FP16 Half Precision | INT8 Post-Training Quantization (PTQ) | **FP16**: Akurasi stabil, proses ekspor mudah, throughput moderat.<br>**INT8**: Throughput meningkat hingga 2x-3x, penggunaan VRAM turun 50%, tetapi membutuhkan kalibrasi dataset ekstensif untuk mencegah akurasi drop. |
| **Parallelism Topology** | Tensor Parallelism (TP) | Pipeline Parallelism (PP) | **TP**: Latensi minimal, cocok untuk serving real-time, tetapi butuh interkoneksi inter-GPU bandwidth ultra-tinggi (NVLink).<br>**PP**: Beroperasi baik di jaringan standar (PCI-e/InfiniBand biasa), tetapi memicu latency bubble (idle wait stages). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Unbounded Memory Allocation (CUDA Out of Memory)
- **Gejala**: Triton / Serving engine melempar status crash loop: `CUDA error: out of memory during initialization or runtime`.
- **Root Cause**: `max_batch_size` dinaikkan secara ekstrem tanpa memperhitungkan alokasi buffer TensorRT engine dan workspace VRAM bersamaan dengan concurrent model instances (`instance_group`).
- **Solusi**: Hitung budget VRAM dengan rumus deterministik:
  $$\text{VRAM}_{\text{total}} \ge \text{VRAM}_{\text{static\_weights}} + N_{\text{instances}} \times (\text{VRAM}_{\text{workspace}} + \text{Batch}_{\text{max}} \times \text{Size}_{\text{activation\_tensor}})$$
  Batasi memory pool Triton menggunakan argumen CLI: `--gpu-memory-fraction=0.85`.

#### 2. Istio Shadow Traffic Amplification Side-Effects
- **Gejala**: Database analitik atau downstream systems menerima double events atau duplicate transactions.
- **Root Cause**: Model Canary yang dipasang sebagai shadow receiver mengeksekusi *side-effects* fungsional (seperti memanggil webhooks eksternal atau menulis record log ke transactional DB).
- **Solusi**: Isolasikan side-effects pada layer routing. Canary shadow target harus berstatus **read-only / metric-sink**. Semua external call sinkronus di-mock atau diarahkan ke storage analitik terisolasi.

#### 3. PCI-e Host-to-Device Memory Bus Congestion
- **Gejala**: GPU metrics menunjukkan `SM Active` rendah, tetapi latensi inferensi total melonjak tinggi.
- **Root Cause**: Data arrays dialokasikan oleh framework client dalam non-pinned virtual memory (pageable memory). CPU OS melakukan page-locking on-the-fly yang memblokir DMA engine.
- **Solusi**: Pastikan alokasi memory host berstatus pinned (`cudaHostAlloc` atau shared memory System V). Nonaktifkan NUMA node interleaving cross-socket pada level kernel OS via `numactl --interleave=all`.

---

### 11. Best Practices (Production Checklist)

| Tahapan | Area Pengecekan | Tindakan Validasi Standar Produksi |
| :--- | :--- | :--- |
| **Runtime Engine** | Memory Pinning | Konfigurasikan volume `/dev/shm` (shared memory) pada pod K8s dengan `mountPath: /dev/shm` bertipe `EmptyDir` berukuran minimal 4 GB. |
| **Runtime Engine** | Warm-Up Requests | Siapkan model artifacts bersama file `model_warmup.json` agar kernel GPU terkompilasi penuh sebelum pod dialokasikan traffic produksi oleh K8s Readiness Probe. |
| **Batching** | Dynamic SLO Alignment | Nilai `max_queue_delay_microseconds` tidak boleh melebihi 20% dari total Latency SLO budget aplikasi. |
| **Networking** | Connection Pooling | Client wajib mengaktifkan HTTP/2 multiplexing dan gRPC keep-alive timeouts untuk mencegah penutupan koneksi TCP secara prematur. |
| **Reliability** | Circuit Breaking | Konfigurasikan Envoy `outlierDetection` pada VirtualService untuk melepaskan instance model yang lambat secara otomatis. |
| **Autoscaling** | Reactive vs Predictive | Gunakan KEDA (Kubernetes Event-driven Autoscaling) dengan scaler `prometheus` yang memantau metrik `nv_inference_queue_duration_us`, bukan CPU/Memory Utilization pod. |
| **Security** | Payload Sanitization | Terapkan payload boundary validation sebelum array dialokasikan ke memori GPU untuk mencegah CUDA memory pointer crash exploit. |

---

### 12. Hands-on Practice: Triton High-Throughput Serving & Dynamic Batching Tuning

#### Tujuan Praktikum
Mengonfigurasi Triton Inference Server dengan dynamic batching, men-deploy model ONNX, memverifikasi perbandingan throughput vs latensi menggunakan tool resmi `perf_analyzer`, dan menganalisis dampaknya terhadap saturasi GPU.

#### Langkah 1: Persiapan Workspace & Model Artefak
Buka terminal dan siapkan struktur direktori di path `hands-on/m02/`:

```bash
mkdir -p hands-on/m02/model_repository/simple_identity/1
cd hands-on/m02/
```

Buat file pembentuk model dummy ONNX menggunakan script Python berikut:

```python
# generate_model.py
import torch
import torch.nn as nn

class HighThroughputIdentity(nn.Module):
    def __init__(self):
        super().__init__()
        self.dense = nn.Linear(128, 128)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.dense(x))

model = HighThroughputIdentity().eval()
dummy_input = torch.randn(1, 128)

torch.onnx.export(
    model,
    dummy_input,
    "model_repository/simple_identity/1/model.onnx",
    input_names=["INPUT0"],
    output_names=["OUTPUT0"],
    dynamic_axes={"INPUT0": {0: "batch_size"}, "OUTPUT0": {0: "batch_size"}},
    opset_version=14
)
print("ONNX model generated successfully at model_repository/simple_identity/1/model.onnx")
```
Jalankan script:
```bash
python3 generate_model.py
```

#### Langkah 2: Buat Model Configuration dengan Dynamic Batching
Buat file `hands-on/m02/model_repository/simple_identity/config.pbtxt`:

```protobuf
name: "simple_identity"
platform: "onnxruntime_onnx"
max_batch_size: 64

input [
  {
    name: "INPUT0"
    data_type: TYPE_FP32
    dims: [ 128 ]
  }
]

output [
  {
    name: "OUTPUT0"
    data_type: TYPE_FP32
    dims: [ 128 ]
  }
]

dynamic_batching {
  max_queue_delay_microseconds: 5000
  preferred_batch_size: [ 16, 32, 64 ]
}

instance_group [
  {
    count: 2
    kind: KIND_GPU
  }
]
```

#### Langkah 3: Menjalankan Triton Inference Server Container
Jalankan Triton via Docker dengan mengekspos GPU dan volume shared memory:

```bash
docker run --gpus all --rm -d \
  --shm-size=2g \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repository:/models \
  --name triton_enterprise_demo \
  nvcr.io/nvidia/tritonserver:23.10-py3 \
  tritonserver --model-repository=/models
```

Verifikasi kesehatan server:
```bash
curl -v http://localhost:8000/v2/health/ready
```

#### Langkah 4: Load Testing & Profiling Menggunakan `perf_analyzer`
Jalankan benchmark performa untuk menguji throughput dan p99 latency secara sistematis pada konkurensi bertingkat:

```bash
docker run --net=host --rm \
  nvcr.io/nvidia/tritonserver:23.10-py3-sdk \
  perf_analyzer -m simple_identity \
  -u localhost:8001 -i gRPC \
  --concurrency-range 4:64:8 \
  --percentile=99 \
  --measurement-interval 10000
```

#### Output Analisis yang Diharapkan
Amati bagaimana throughput (inferensi/detik) melonjak naik seiring naiknya konkurensi karena dynamic batching mulai menggabungkan request, sementara latensi p99 tetap terkontrol di bawah ambang batas timeout scheduler:
```
Concurrency: 4  | Throughput: 1240 infer/sec | Latency p99: 3120 usec
Concurrency: 16 | Throughput: 4890 infer/sec | Latency p99: 4500 usec
Concurrency: 64 | Throughput: 14200 infer/sec| Latency p99: 6850 usec
```

---

### 13. Exercises

#### Level Easy
1. Modifikasi file `config.pbtxt` pada praktikum di atas: ubah `max_queue_delay_microseconds` menjadi `0` (menonaktifkan pooling delay). 
2. Jalankan kembali `perf_analyzer` dengan konkurensi 32. 
3. Catat perubahan throughput total dan rata-rata batch size yang tercatat pada server log (`curl http://localhost:8002/metrics`).
*Deliverable*: Dokumentasi tabel perbedaan throughput dan analisis penyebab penurunan efisiensi batch size.

#### Level Medium
1. Tulis sebuah Python decorator berbasis `asyncio` yang bertindak sebagai local client-side batcher.
2. Decorator harus menahan payload inferensi selama interval 2 ms atau hingga buffer mencapai 16 item sebelum mengirimkan satu request batch besar ke server gRPC Triton.
3. Bandingkan latensi lokal client-side batcher vs mengandalkan Triton server-side dynamic batcher.
*Deliverable*: File script `client_batcher.py` lengkap dengan visualisasi latensi.

#### Level Hard
1. Buat arsitektur deployment Kubernetes yang memuat dua pod Triton: Pod Alpha (Model ResNet50 FP32) dan Pod Beta (Model ResNet50 INT8).
2. Konfigurasikan Istio `VirtualService` dan `DestinationRule` untuk menduplikasi (mirror/shadow) seluruh request dari Pod Alpha ke Pod Beta.
3. Konfigurasikan Prometheus scrape config untuk mengambil metrik latensi dari kedua endpoint model tersebut secara berdampingan.
*Deliverable*: Kumpulan file manifest Kubernetes (`deployment.yaml`, `istio-routing.yaml`, `monitoring.yaml`) yang berhasil di-deploy tanpa error.

---

### 14. Challenge: Zero-Downtime Rollout of a 70B Distributed LLM Under Active Load

#### Deskripsi Skenario
Anda adalah Principal Infrastructure Architect pada platform AI global. Platform Anda melayani model LLM 70 Miliar Parameter (Llama-3-70B) menggunakan engine vLLM terdistribusi di atas multi-node GPU cluster (2 node, masing-masing berisi 8x NVIDIA H100 80GB SXM5, total 16 GPU) menggunakan konfigurasi **Tensor Parallelism (TP) = 8** dan **Pipeline Parallelism (PP) = 2**.

Sistem saat ini sedang menerima beban stabil sebesar **8.000 tokens/second** via streaming gRPC connection dari aplikasi production-critical tanpa ada toleransi downtime (0 request drop).

#### Tantangan Arsitektur
Anda diminta melakukan rolling upgrade runtime vLLM dari versi `v0.4.x` ke versi `v0.6.x` yang memuat pembaruan CUDA base image drivers dan kernel PagedAttention terbaru.

#### Kendala Operasional (Constraints)
1. **GPU Capacity Constraint**: Total kuota node GPU yang tersedia di cloud provider Anda bersifat *hard cap* (hanya tersedia 1 node cadangan tambahan untuk proses staging, tidak memungkinkan melakukan duplikasi cold cluster secara penuh).
2. **Stateful Streaming**: Ribuan client tengah terhubung via long-lived HTTP/2 gRPC streaming connections yang sedang memproses text output autoregresif.
3. **KV Cache Initialization Overhead**: Cold-start load model weights 70B memakan waktu 180 detik per pod node.

#### Instruksi Pengerjaan
Rancang blueprint arsitektur end-to-end yang komprehensif, mencakup:
1. **L7 Draining Strategy**: Bagaimana Anda memanfaatkan mekanisme graceful draining pada level Ingress/Envoy gateway agar long-lived stream tidak terputus di tengah jalan?
2. **Deployment Pipeline & Resource Allocation**: Bagaimana orchestrator memanfaatkan 1 node staging tambahan untuk memindahkan beban per shard tanpa melanggar batas kuota GPU?
3. **Automated Rollback & Fallback Mechanism**: Metrik anomali apa yang memicu pembatalan rollout otomatis secara deterministik, dan bagaimana router mengembalikan payload ke baseline deployment dalam orde sub-detik?

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi utama dari parameter `max_queue_delay_microseconds` pada arsitektur dynamic batching Triton Inference Server?
   - A. Menentukan timeout koneksi HTTP client sebelum memutus soket.
   - B. Menentukan durasi maksimum scheduler boleh menahan request di queue untuk menunggu request lain agar batch optimal terbentuk.
   - C. Mengatur batas waktu eksekusi kernel inferensi di dalam streaming multiprocessor.
   - D. Waktu tunggu read disk I/O saat meload model dari remote object storage.
   *(Jawaban: B — Scheduler menahan request pertama selama periode ini demi mengumpulkan batch yang lebih besar sebelum dikirim ke GPU).*

2. Mengapa penggunaan PagedAttention secara dramatis meningkatkan throughput LLM serving dibandingkan model alokasi memori tradisional?
   - A. Karena mengeliminasi komputasi matriks dot-product attention pada Tensor Cores.
   - B. Karena mengonversi model FP16 menjadi representasi INT4 secara otomatis di runtime.
   - C. Karena mengeliminasi internal dan external memory fragmentation pada KV Cache dengan mengalokasikan virtual block non-kontigu secara dinamis.
   - D. Karena mengubah arsitektur model Transformer autoregresif menjadi model feed-forward non-autoregresif.
   *(Jawaban: C — PagedAttention membagi KV-cache menjadi unit halaman diskrit, menghilangkan pemborosan fragmentasi alokasi VRAM).*

3. Apa keuntungan performa utama protokol gRPC dibandingkan REST HTTP/1.1 JSON standar dalam inferensi high-throughput?
   - A. gRPC mengonversi layer komputasi CUDA menjadi binary machine code secara langsung.
   - B. gRPC menggunakan HTTP/2 multiplexing dan encoding binary protobuf, menghilangkan overhead string parsing JSON dan socket head-of-line blocking.
   - C. gRPC secara otomatis mengaktifkan quantization INT8 pada backend server.
   - D. gRPC tidak membutuhkan alokasi port network pada interface host.
   *(Jawaban: B — Serialisasi biner Protocol Buffers dan multiplexing HTTP/2 memangkas CPU utilization dan latensi deserialisasi).*

4. Manakah komponen hardware yang paling sering menjadi bottleneck utama (*chokepoint*) pada serving model non-batched berukuran kecil?
   - A. Tensor Cores GPU.
   - B. Bus PCI-e (Host-to-Device Memory Transfer).
   - C. High Bandwidth Memory (HBM) pada modul GPU.
   - D. Storage NVMe lokal.
   *(Jawaban: B — Payload kecil berulang memicu latensi tinggi pada bus PCI-e karena overhead inisiasi transfer data melampaui waktu eksekusi komputasi kernel).*

5. Apa fungsi dari Pinned Host Memory (`cudaHostAlloc`) dalam konteks model serving?
   - A. Mengunci bobot model di dalam cache L2 prosesor CPU.
   - B. Menyediakan blok memori fisik pada host RAM yang dijamin tidak akan dipindahkan oleh OS paging, memungkinkan DMA (Direct Memory Access) asinkron mentransfer data langsung ke GPU.
   - C. Menghapus kebutuhan alokasi VRAM pada kartu GPU.
   - D. Mengenkripsi payload inferensi sebelum dikirim ke public network.
   *(Jawaban: B — Pinned memory memungkinkan transfer DMA langsung tanpa intervensi CPU core, krusial untuk streaming berkecepatan tinggi).*

#### B. Pertanyaan Intermediate
6. Dalam deployment pola Istio Shadow Traffic (Mirroring) untuk model inferensi, apa yang terjadi pada response payload yang dihasilkan oleh instance model Canary (shadow)?
   - A. Response dari instance Canary dikembalikan ke client jika respons tersebut selesai lebih cepat daripada respons instance Primary.
   - B. Response dari instance Canary di-merge dengan response instance Primary sebelum dikirimkan ke client.
   - C. Response dari instance Canary di-drop oleh Envoy proxy pada layer network; metrik dan telemetry tetap diekstrak dan dicatat.
   - D. Response dari instance Canary otomatis ditulis ke dalam tabel database PostgreSQL cluster.
   *(Jawaban: C — Shadow routing secara eksplisit mengabaikan payload balasan shadow engine dari client untuk menjaga konsistensi state sistem).*

7. Parameter apa yang perlu disesuaikan pada Triton Inference Server jika p99 latency aplikasi melonjak tinggi saat traffic spike, meskipun utilisasi GPU baru mencapai 40%?
   - A. Menaikkan nilai `max_queue_delay_microseconds` ke angka yang lebih besar.
   - B. Menurunkan nilai `max_queue_delay_microseconds` dan menaikkan jumlah instance pada `instance_group`.
   - C. Menghapus konfigurasi `preferred_batch_size`.
   - D. Menurunkan clock speed GPU via NVML.
   *(Jawaban: B — Latensi melonjak pada GPU utilization rendah menandakan request tertahan terlalu lama di queue scheduler atau kekurangan worker instance independen untuk mengeksekusi stream paralel).*

8. Apa perbedaan mendasar antara Tensor Parallelism (TP) dan Pipeline Parallelism (PP) saat melakukan distributed LLM serving?
   - A. TP membagi bobot layer horizontal di antara GPU dalam single step, membutuhkan komunikasi inter-GPU all-reduce latensi sangat rendah; PP membagi layer secara sekuensial antar tahapan pipeline.
   - B. PP hanya dapat diimplementasikan pada single GPU; TP membutuhkan multi-node compute cluster.
   - C. TP memproses dokumen teks; PP hanya memproses model berbasis citra (computer vision).
   - D. TP tidak membutuhkan komunikasi data antar GPU sama sekali.
   *(Jawaban: A — Tensor Parallelism memecah individual linear layers pada tensor cores terdistribusi, sangat sensitif terhadap latensi bus antarkartu).*

9. Mengapa autoscaling berbasis rata-rata CPU utilization (HPA standar) dianggap tidak memadai untuk cluster high-throughput model serving berbasis GPU?
   - A. Karena CPU tidak digunakan sama sekali dalam siklus inferensi modern.
   - B. Beban kerja bottleneck berada di VRAM dan Tensor Cores GPU; CPU sering kali idle saat antrean request menumpuk pada GPU queue scheduler, menyebabkan HPA terlambat melakukan scale out.
   - C. Metrik CPU Kubernetes tidak dapat dibaca jika container menjalankan runtime Docker.
   - D. Karena K8s Metrics Server mematikan pod secara otomatis jika konsumsi CPU di bawah 10%.
   *(Jawaban: B — GPU inference pod dapat mengalami kegagalan SLO akibat overload antrean GPU sementara CPU pod tetap berada di bawah ambang batas autoscaling).*

10. Apa risiko terbesar dari pengaturan `max_batch_size` yang terlalu besar saat mengeksekusi model vision dengan dynamic shapes?
    - A. Triton server menolak me-load model saat startup.
    - B. Peningkatan drastis risiko alokasi dynamic buffer VRAM melampaui kapasitas fisik GPU, menyebabkan CUDA Out of Memory (OOM) fatal yang menumbangkan pod secara mendadak.
    - C. Penurunan resolusi gambar input secara otomatis oleh library CUDA.
    - D. Protokol gRPC otomatis beralih ke mode HTTP/1.0.
    *(Jawaban: B — Dynamic shapes dengan batch besar memicu alokasi tensor activation yang eksplosif secara mendadak di VRAM, memicu OOM panic crash).*

#### C. Skenario Kasus Produksi
11. **Skenario Kasus 1**: Sistem deteksi penipuan Anda menggunakan Triton Server dengan konfigurasi `max_queue_delay_microseconds: 8000` (8 ms). Latency SLA total aplikasi dari gateway ke gateway adalah 15 ms. Saat event flash sale berlangsung, klien melaporkan bahwa 15% request mengalami *gRPC DEADLINE_EXCEEDED (status code 4)*. Metrik GPU menunjukkan utilisasi Tensor Core stabil di angka 95%.
    - *Analisis Tindakan*: Apa root cause masalah tersebut dan bagaimana langkah mitigasi arsitektural yang paling presisi tanpa mengorbankan stabilitas model?
    - *Jawaban & Solusi Terarah*:
      - **Root Cause**: Queue wait time + batch execution time melampaui deadline timeout client (15 ms). Ketika GPU mencapai saturasi 95%, scheduler antrean mengalami *tail latency explosion* di mana request yang masuk belakangan harus mengantre di belakang beberapa batch yang sedang berjalan.
      - **Mitigasi**: (1) Kurangi `max_queue_delay_microseconds` menjadi 2000 $\mu s$ (2 ms) untuk mencegah deep pooling saat load jenuh. (2) Pasang circuit breaker / rate limiter pada Istio Ingress Gateway untuk me-reject atau mengalihkan ke model fallback ringan (*graceful degradation*) jika inference queue depth melebihi threshold. (3) Tambahkan horizontal scale worker pod GPU melalui KEDA berbasis queue size metric.

12. **Skenario Kasus 2**: Anda mengonfigurasi Shadow Deployment via Istio untuk menguji model NLP baru (Model B) yang dioptimasi dengan INT8 PTQ terhadap Model Baseline (Model A) FP16. Setelah traffic shadow diaktifkan pada skala 100%, pod instance Model A (Primary) tiba-tiba mengalami kenaikan latensi p99 sebesar 80%, padahal hardware Model A dan Model B terisolasi pada pod yang berbeda.
    - *Analisis Tindakan*: Mengapa performa primary model ikut terdegradasi meskipun beban inferensi komputasi berjalan di pod yang berbeda?
    - *Jawaban & Solusi Terarah*:
      - **Root Cause**: Bottleneck terjadi pada layer upstream network/ingress proxy (Envoy Gateway) atau database logging. Envoy Ingress Gateway mengalami saturasi I/O socket / CPU thread exhaustion karena harus menduplikasi (mirroring), mengenkapsulasi ulang, dan mentransmisikan ulang 100% network packets secara ganda pada konkurensi puncak. Alternatif lain, kedua pod bersaing memperebutkan shared network bandwidth pada interface physical host yang sama (Node NIC congestion).
      - **Mitigasi**: (1) Turunkan persentase shadow mirroring dari 100% ke sample rate yang representatif (misal: 10% atau 20%). (2) Terapkan isolasi worker node fisik secara terpisah untuk environment eksperimen menggunakan Kubernetes NodeAffinity/Taints. (3) Alokasikan resource CPU/Thread pool khusus pada Envoy Gateway DaemonSet untuk menangani mirror packet processing.

13. **Skenario Kasus 3**: Sebuah cluster serving vLLM yang menjalankan model LLM 13B mengalami penurunan tajam pada throughput generation (token/s per user) saat konkurensi naik dari 100 ke 400 user aktif, meskipun metrik VRAM masih menunjukkan 20 GB free space.
    - *Analisis Tindakan*: Apa yang menyebabkan terjadinya starvation tersebut padahal VRAM belum terisi penuh 100%?
    - *Jawaban & Solusi Terarah*:
      - **Root Cause**: Memory fragmentation bukan penyebabnya berkat PagedAttention, tetapi free space 20 GB tersebut sengaja dikunci oleh parameter safety margin (`gpu_memory_utilization`), atau bottleneck telah bergeser dari kapasitas memori (*Capacity Bound*) menjadi bandwidth memori (*Memory-Bandwidth Bound*) pada fase Autoregressive Generation Decoding. Pada konkurensi 400 user, GPU SM menghabiskan siklus clock hanya untuk meload bobot model dari HBM ke SRAM secara berulang untuk setiap decoding token step, memicu memory bus saturation (HBM bandwidth throttling).
      - **Mitigasi**: (1) Aktifkan *Chunked Prefill* untuk menyatukan fase compute-bound prefill dengan memory-bound decode dalam single batch iteration. (2) Terapkan *Speculative Decoding* menggunakan draft model kecil untuk menghasilkan beberapa token per clock cycle memory load. (3) Pertimbangkan implementasi Tensor Parallelism untuk membagi beban transfer bandwidth bobot model melintasi interface beberapa kartu GPU HBM.

---

### 16. Summary

Implementasi model serving tingkat enterprise menuntut pergeseran fundamental dari paradigma synchronous web framework (FastAPI/PyTorch) menuju **dedicated asynchronous hardware execution engines** (Triton Inference Server, vLLM, TensorRT-LLM). 

Pilar keberhasilan serving high-throughput berakar pada:
1. **Dynamic Batching**: Menyeimbangkan rasio kompromi antara latensi individual (SLO budget) dan utilisasi hardware (saturation efficiency) melalui time-bounded queue management.
2. **Pola Traffic L7 Modern**: Memungkinkan validasi arsitektur inferensi tanpa risiko kegagalan sistemik melalui *Shadow/Dark Traffic* dan *Canary Routing* pada network mesh.
3. **Optimasi Memori Tingkat Rendah**: Menghilangkan serialisasi bottleneck via CUDA Pinned Host Memory, Inter-Process Communication (IPC) zero-copy, dan teknik alokasi non-kontigu mutakhir seperti *PagedAttention*.
4. **Metrik Observabilitas Berbasis Hardware**: Memonitor queue latency dan GPU SM duty cycle secara presisi sebagai sinyal penggerak autoscaling (KEDA), bukan mengandalkan metrik CPU konvensional yang menyesatkan.