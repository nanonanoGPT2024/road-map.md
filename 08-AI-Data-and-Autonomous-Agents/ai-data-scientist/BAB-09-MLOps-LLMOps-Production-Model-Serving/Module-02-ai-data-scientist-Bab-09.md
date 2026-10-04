# Kurikulum Enterprise: AI & Data Science
## Kategori: 08-AI-Data-and-Autonomous-Agents
### Bab 09: MLOps, LLMOps, dan Production Model Serving
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat *Staff/Principal Engineer* dalam:

1. **Merancang & Mengimplementasikan Arsitektur Serving High-Throughput / Low-Latency**: Membangun kluster inferensi model machine learning tradisional dan Large Language Model (LLM) memanfaatkan *iteration-level continuous batching*, *PagedAttention*, dan paralelisasi terdistribusi (*Tensor & Pipeline Parallelism*).
2. **Optimalisasi Kompilasi & Kuantisasi Hardware-Aware**: Mengonversi graf model PyTorch ke format ONNX dan TensorRT/TensorRT-LLM dengan kalibrasi kuantisasi *Post-Training Quantization* (INT8/INT4 AWQ/GPTQ) tanpa degradasi akurasi signifikan.
3. **Membangun Sistem Deployment Zero-Downtime**: Mengorkestrasi strategi *Canary Deployment*, *Shadow Traffic/Dark Launch*, dan *Blue-Green* berbasis *Service Mesh* (Istio) dengan metrik *Automated Rollback* (Argo Rollouts) menggunakan indikator P99 Latency dan *Data Drift*.
4. **Implementasi Continuous Monitoring & Drift Detection**: Merancang *pipeline observability* inferensi yang memantau *Time-To-First-Token* (TTFT), *Time-Per-Output-Token* (TPOT), *GPU Memory Saturation*, serta mendeteksi *Data Drift* dan *Concept Drift* secara *real-time* via Prometheus, Grafana, dan Evidently AI.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* **Infrastruktur & Containerization**: Arsitektur internal Linux (cgroups, namespaces), Docker runtime, dan orkestrasi Kubernetes tingkat menengah (CRDs, HPA, Services, Ingress).
* **Deep Learning Frameworks**: PyTorch internals (`torch.nn`, autograd, CUDA memory allocators, PyTorch C++ extension).
* **Hardware & Akselerasi Grafis**: Pemahaman mendalam mengenai arsitektur GPU (NVIDIA Ampere/Hopper), CUDA Cores, Tensor Cores, HBM (High Bandwidth Memory), dan interkoneksi NVLink/PCIe.
* **Networking & Protocols**: Protokol gRPC (HTTP/2, Protobuf serialization), REST, WebSocket, dan Server-Sent Events (SSE).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Runtime Inferensi Modern: Mengapa Paradigma Tradisional Runtuh

Pada arsitektur monolitik konvensional (misal: FastAPI/Flask membungkus model PyTorch mentah), eksekusi inferensi berjalan di bawah kontrol Global Interpreter Lock (GIL) Python, mengunci satu proses inferensi per *worker*. Saat beban konkurensi meningkat, terjadi:
1. **Head-of-Line (HoL) Blocking**: Permintaan inferensi dengan *payload* kecil tertahan di belakang inferensi dengan *payload* besar.
2. **GPU Underutilization**: Tensor Cores menganggur (*idle*) saat menunggu transfer data dari Host Memory (RAM) ke Device Memory (VRAM).
3. **Memory Thrashing**: Alokasi memori dinamis PyTorch runtime memicu fragmentasi pada alokator caching CUDA.

Untuk mengatasi inefisiensi ini, arsitektur *serving* tingkat *enterprise* memisahkan lapisan *I/O Gateway* dari lapisan *Execution Engine* menggunakan sistem seperti **Triton Inference Server** untuk model analitis/CV/NLP tradisional, dan **vLLM / TensorRT-LLM** untuk model generatif.

```
+-----------------------------------------------------------------------------------+
|                            ENTERPRISE SERVING STACK                               |
+-----------------------------------------------------------------------------------+
|  [Ingress / Gateway (Envoy/Istio)] ---> [Dynamic Router & Rate Limiter]           |
+-----------------------------------------------------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
+-------------------------------+                   +-------------------------------+
|  TRITON INFERENCE SERVER      |                   |  vLLM / TENSORRT-LLM ENGINE   |
|  (Tabular, CV, Audio Models)  |                   |  (Generative LLM Serving)     |
+-------------------------------+                   +-------------------------------+
| * C++ Native Core Engine      |                   | * PagedAttention Virtual Mem  |
| * Dynamic Batching Queue      |                   | * Continuous/Cell Batching    |
| * Concurrent Model Execution  |                   | * Distributed Engine (TP/PP)  |
| * Shared Memory (POSIX/CUDA)  |                   | * Prefill/Decode Disaggr.     |
+-------------------------------+                   +-------------------------------+
                |                                                   |
                +-------------------------+-------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|            NVIDIA GPU (CUDA Runtime, Tensor Cores, HBM3 / NVLink)                 |
+-----------------------------------------------------------------------------------+
```

#### 3.2. PagedAttention dan Manajemen KV-Cache

Pada inferensi LLM, tahap autoregresif menuntut penyimpanan *Key-Value Cache* (KV-cache) dari token-token sebelumnya untuk menghindari komputasi ulang matriks perhatian (*Attention Matrix*). 

Pada implementasi primitif:
* Memori dialokasikan secara statis berdasarkan panjang konteks maksimum ($L_{max}$).
* Jika $L_{max} = 4096$, tetapi pengguna hanya menghasilkan 200 token, maka $\approx 95\%$ memori KV-cache terbuang secara internal (*internal fragmentation*).
* Memori yang dialokasikan harus bersebelahan (*contiguous memory*), memicu *external fragmentation*.

**PagedAttention** menyelesaikan masalah ini dengan meminjam prinsip *Virtual Memory Paging* dari Kernel Sistem Operasi:
1. KV-cache dipecah menjadi blok-blok berukuran tetap (*block size*, misal: 16 atau 32 token).
2. Tensor memori fisik dialokasikan secara non-kontigu di HBM.
3. *Logical Block Table* memetakan urutan token logis ke blok fisik HBM secara dinamis.
4. Token baru dialokasikan ke blok yang ada; jika blok penuh, *engine* meminta alokasi blok fisik baru dari *free block pool*.

$$\text{Memori KV Cache Per Token} = 2 \times 2 \times n_{\text{layers}} \times n_{\text{heads}} \times d_{\text{head}} \times \text{bytes per element}$$

Contoh untuk LLaMA-3-8B (FP16):
$$\text{Memori} = 4 \times 32 \times 32 \times 128 \times 2\text{ byte} = 1.048.576\text{ byte} \approx 1\text{ MB per token}$$
Dengan PagedAttention, utilisasi memori KV-cache meningkat dari $\approx 20\text{--}40\%$ menjadi $>96\%$, memungkinkan peningkatan ukuran *batch* hingga $4\times \text{--} 8\times$.

#### 3.3. Static vs. Dynamic vs. Continuous Batching

* **Static Batching**: Model menunggu hingga $N$ request terkumpul sebelum inferensi dimulai. Jika traffic rendah, latency membengkak karena *timeout window*.
* **Dynamic Batching (Triton Engine)**: Inferensi dieksekusi jika $N$ request terkumpul ATAU batas waktu delay maksimum $T_{max}$ tercapai. Cocok untuk inferensi satu lintasan (*single-pass*) seperti BERT, ResNet, XGBoost.
* **Continuous / Iteration-Level Batching (vLLM Engine)**: Pada LLM, proses inferensi terbagi dua fase: **Prefill** (*compute-bound*, memproses token prompt secara paralel) dan **Decode** (*memory-bandwidth bound*, memproduksi satu token per iterasi per sequence). Continuous batching mengevaluasi ulang *batch pool* pada setiap iterasi *decode*. Request yang telah menghasilkan token akhir (`<EOS>`) langsung dikeluarkan dari batch, dan request baru yang sedang menunggu langsung dimasukkan ke *slot* yang kosong tanpa menunggu seluruh sequence lain selesai.

---

### 4. Why & What

| Dimensi | Pendekatan Naive (Flask / FastAPI) | Pendekatan Enterprise (Triton / vLLM) |
| :--- | :--- | :--- |
| **Throughput** | Rendah ($<50$ req/sec per GPU). | Sangat Tinggi ($>2000$ req/sec per GPU via Dynamic/Continuous Batching). |
| **Model Concurrency** | Satu instance model per GPU; memicu *idle GPU*. | Multi-model pipeline berjalan bersamaan di memori GPU yang sama secara asynchronous. |
| **GPU Memory Overhead** | Terjadi fragmentasi tinggi karena dynamic memory allocation PyTorch. | *Zero-copy memory transfer* (CUDA Shared Memory) dan eliminasi fragmentasi (PagedAttention). |
| **Orchestration & Deploy** | Rolling restart manual, rawan kegagalan koneksi (*connection dropping*). | Zero-downtime Canary Deployment dengan evaluasi latensi P99 otomatis berbasis Envoy & Service Mesh. |
| **Data & Concept Drift** | Analisis pasif mingguan/bulanan dari dump database log. | Ekstraksi statistik inferensi inline secara *real-time* via streaming buffer ke Evidently AI & Prometheus. |

---

### 5. How (Workflow Detail)

Alur kerja inferensi enterprise end-to-end terdiri dari siklus berikut:

```
[Klien] --(1. gRPC/SSE Request)--> [Ingress / Istio Envoy Proxy]
                                                |
               +--------------------------------+
               | (Routing: Canary / Shadow / Production)
               v
[Dynamic Router & Token Bucket Limiter]
               |
               v
[Engine Runtime (vLLM / Triton)]
   |
   +---> [Tokenizer / Preprocessor Pipeline]
   |
   +---> [Scheduler: Iteration-Level Queue]
   |        |
   |        +---> [PagedAttention Memory Allocator] (HBM Allocation)
   |
   +---> [CUDA Kernel Execution Engine (TensorRT-LLM Core)]
            |
            v
   [Detokenizer / Postprocessor] --(2. Chunk Output via SSE)--> [Klien]
            |
            v (Asynchronous Event Egress)
[Kafka / Redpanda Broker]
   |
   v
[Evidently Drift Collector / Prometheus Exporter]
   |
   +---> [Prometheus Server] ---> [Grafana / Alertmanager]
   |
   +---> [Argo Rollouts Controller] ---> (Trigger Auto-Rollback jika Drift/Error Spike)
```

1. **Ingress & Traffic Splitting**: Klien mengirimkan request via gRPC atau REST/SSE. Istio Service Mesh membaca *header* HTTP dan mengevaluasi bobot lalu lintas (misal: 90% ke `v1.2.0-stable`, 10% ke `v1.3.0-canary`).
2. **Scheduling & Queueing**: Model server menerima payload, memasukkannya ke antrean batch internal (*dynamic batch queue* atau *iteration-level scheduler*).
3. **Execution**: Scheduler mengeksekusi kernel CUDA yang teroptimasi (TensorRT engines). Untuk LLM, fase Prefill dan Decode diorkestrasi secara bergantian atau disaggregasi (*disaggregated prefill-decode architecture*).
4. **Streaming Response**: Detokenizer mengubah *logits* menjadi token teks dan mengembalikannya ke klien secara *streaming* melalui protokol gRPC stream atau HTTP Server-Sent Events (SSE).
5. **Observability Out-of-Band**: Metrik inferensi (token count, latensi, confidence score, embeddings) dikirimkan secara asinkron via shared memory atau logging buffer ke broker data untuk analisis *Data Drift*.

---

### 6. Analogi & Diagram ASCII

#### Analogi PagedAttention: Hotel Kamar Kapsul vs. Reservasi Sayap Hotel Tradisional
* **Inferensi Tradisional (Static Allocation)**: Seseorang memesan satu sayap hotel berisi 50 kamar (*max length*), meskipun dia hanya datang sendirian dan hanya butuh 1 kamar. Kamar lain tidak boleh diisi orang lain hingga orang tersebut checkout. Hasilnya: Hotel cepat penuh padahal kosong secara de facto.
* **PagedAttention**: Sistem kamar kapsul terpusat. Setiap tamu hanya dialokasikan 1 unit kapsul pada saat ia masuk. Jika ia membawa barang baru di malam hari, ia diberi 1 kapsul tambahan di lantai berapa pun yang masih kosong. Komputer melacak kapsul mana saja yang dimiliki tamu tersebut via buku log (*Page Table*). Kapasitas hotel terpakai maksimal tanpa ada kapsul menganggur.

#### Diagram Interaksi Memori: PagedAttention KV-Cache

```
LOGICAL TOKENS (Sequence A):
[Token 0, Token 1, Token 2] -> Logical Block 0
[Token 3, Token 4, Token 5] -> Logical Block 1
[Token 6]                   -> Logical Block 2 (Sedang diisi)

                    BLOCK TABLE (Sequence A)
                    +---------------+----------------+
                    | Logical Block | Physical Block |
                    +---------------+----------------+
                    |    Block 0    |    Slot #7     |
                    |    Block 1    |    Slot #1     |
                    |    Block 2    |    Slot #9     |
                    +---------------+----------------+

PHYSICAL MEMORY (GPU High Bandwidth Memory - HBM)
+----------+----------+----------+----------+----------+----------+
| Slot #0  | Slot #1  | Slot #2  | ...      | Slot #7  | Slot #9  |
| (Seq B)  | [T3,T4,T5| (Free)   |          | [T0,T1,T2| [T6, _, _]
|          |  Seq A]  |          |          |  Seq A]  |  Seq A]  |
+----------+----------+----------+----------+----------+----------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Konfigurasi Model Triton dengan Dynamic Batching (`config.pbtxt`)

Berikut konfigurasi produksi Triton Inference Server untuk model tabular/klasifikasi berbasis TensorRT/ONNX:

```protobuf
name: "fraud_detector_onnx"
platform: "onnxruntime_onnx"
max_batch_size: 128

input [
  {
    name: "input_features"
    data_type: TYPE_FP32
    dims: [ 48 ]
  }
]

output [
  {
    name: "fraud_probability"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

# Dynamic Batching Scheduler Engine
dynamic_batching {
  preferred_batch_size: [ 16, 32, 64, 128 ]
  max_queue_delay_microseconds: 5000  # 5ms toleransi latensi untuk mengisi batch
}

# Skalabilitas Konkurensi pada Multi-Core/Multi-Stream
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

#### 7.2. Practical Example: Production-Grade Custom Streaming Server dengan vLLM & Drift Extraction Middleware

Contoh arsitektur Python enterprise yang membungkus *vLLM AsyncLLMEngine* dengan endpoint streaming SSE, serta ekstraksi statistik token secara asinkron ke antrean monitoring drift.

```python
"""
Enterprise Production LLM Serving Node with vLLM and Metric/Drift Interceptor.
Menyediakan interface asynchronous, streaming SSE, dan publish event ke Prometheus/Drift Queue.
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.sampling_params import SamplingParams
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Prometheus Metrics Definition
REQUEST_COUNT = Counter(
    "llm_requests_total", 
    "Total LLM Inference Requests", 
    ["model", "status"]
)
TTFT_HISTOGRAM = Histogram(
    "llm_time_to_first_token_seconds", 
    "Time To First Token latency", 
    ["model"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)
INFERENCE_LATENCY = Histogram(
    "llm_inference_duration_seconds", 
    "Total generation duration", 
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

app = FastAPI(title="Enterprise LLM Engine Node", version="2.0.0")

# Inisialisasi Engine vLLM Terdistribusi
engine_args = AsyncEngineArgs(
    model="meta-llama/Meta-Llama-3-8B-Instruct",
    tensor_parallel_size=1,            # Naikkan sesuai jumlah GPU (e.g., 2, 4, 8)
    gpu_memory_utilization=0.90,       # 90% dialokasikan untuk model + PagedAttention
    max_model_len=4096,
    quantization="awq",                # AWQ INT4 Post-Training Quantization
    enforce_eager=False,               # Aktifkan CUDA Graph compilation
    trust_remote_code=False,
    disable_log_requests=True
)
engine = AsyncLLMEngine.from_engine_args(engine_args)

class ChatCompletionRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=1, le=2048)
    metadata: Dict[str, Any] = Field(default_factory=dict)

async def stream_inference_generator(
    request_id: str,
    prompt: str,
    sampling_params: SamplingParams,
    client_metadata: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    start_time = time.perf_counter()
    first_token_received = False
    generated_tokens_count = 0

    results_generator = engine.generate(prompt, sampling_params, request_id)

    try:
        async for request_output in results_generator:
            if not first_token_received and request_output.outputs[0].token_ids:
                ttft = time.perf_counter() - start_time
                TTFT_HISTOGRAM.labels(model=engine_args.model).observe(ttft)
                first_token_received = True

            # Dapatkan delta token terakhir
            text_chunk = request_output.outputs[0].text
            generated_tokens_count = len(request_output.outputs[0].token_ids)
            
            # Format SSE Protocol
            chunk_payload = {
                "id": request_id,
                "text": text_chunk,
                "finished": request_output.finished
            }
            yield f"data: {json.dumps(chunk_payload)}\n\n"

        total_latency = time.perf_counter() - start_time
        INFERENCE_LATENCY.labels(model=engine_args.model).observe(total_latency)
        REQUEST_COUNT.labels(model=engine_args.model, status="success").observe(1)

        # Trigger drift & analytics event secara background asynchronous
        asyncio.create_task(
            publish_drift_telemetry(prompt, text_chunk, client_metadata)
        )

    except Exception as e:
        REQUEST_COUNT.labels(model=engine_args.model, status="error").observe(1)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        raise

async def publish_drift_telemetry(prompt: str, generated_text: str, metadata: Dict[str, Any]):
    """
    Mock pipeline pengiriman data inferensi ke streaming buffer (Kafka/RabbitMQ) 
    untuk komputasi drift di Evidently AI tanpa mengganggu jalur inferensi utama.
    """
    telemetry_payload = {
        "timestamp": time.time(),
        "prompt_length": len(prompt),
        "output_length": len(generated_text),
        "metadata": metadata
    }
    # Simulasi I/O non-blocking
    await asyncio.sleep(0.001)

@app.post("/v1/chat/completions/stream")
async def chat_completions(req: ChatCompletionRequest):
    req_id = f"req-{uuid.uuid4().hex}"
    sampling_params = SamplingParams(
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
    )

    return StreamingResponse(
        stream_inference_generator(req_id, req.prompt, sampling_params, req.metadata),
        media_type="text/event-stream"
    )

@app.get("/metrics")
async def metrics():
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Fraud Detection & Copilot Finansial Tier-1 Bank (Global Bank X)

* **Skala Sistem**:
  * $50.000$ transaksi per detik (TPS) untuk analisis fraud analitis (*real-time tabular inference*).
  * $15.000.000$ interaksi conversational AI harian untuk Financial Advisor Copilot.
* **Target SLA/SLO**:
  * Tabular Inference P99 Latency: $< 12\text{ ms}$.
  * LLM Copilot Time-To-First-Token (TTFT): $< 350\text{ ms}$, Throughput $> 40\text{ token/sec/user}$.
  * Zero-downtime saat update model (rollout frekuensi 1 minggu sekali).

#### Arsitektur Implementasi:
1. **Tier 1: Tabular Fraud Engine (Triton Inference Server)**
   * Model: XGBoost dan LightGBM dikonversi ke **Treelite / TensorRT Runtime**.
   * Protokol: Komunikasi internal via **gRPC dengan CUDA IPC (Shared Memory)** antar pod pada node yang sama, memotong overhead TCP stack sebesar $70\%$.
   * Topologi: Multi-worker autoscaling diatur oleh KEDA (*Kubernetes Event-driven Autoscaling*) berdasarkan kedalaman antrean (*queue length*) di buffer Apache Kafka.
2. **Tier 2: Generative Copilot Engine (TensorRT-LLM on NVIDIA H100 Cluster)**
   * Model: LLaMA-3-70B dioptimasi dengan kuantisasi **FP8 GEMM Kernels** via TensorRT-LLM.
   * Model Parallelism: 4-Way Tensor Parallelism (TP=4) terhubung lewat NVLink Switch (900 GB/s inter-GPU bandwidth).
   * Arsitektur Disagregasi: Pemisahan node **Prefill-only worker** (GPU H100 PCIe) dan **Decode-only worker** (GPU H100 SXM5), mencegah komputasi prompt besar memblokir kelancaran pengeluaran token pengguna lain.
3. **Traffic Governance & Canary Rollout**:
   * **Istio Service Mesh** mengatur pemisahan lalu lintas produksi.
   * Argo Rollouts menjalankan fase bertahap: $5\% \rightarrow 20\% \rightarrow 50\% \rightarrow 100\%$.
   * Prometheus metric analyzer secara otomatis membatalkan (*rollback*) canary jika:
     $$\text{P99 Latency} > 25\text{ ms} \quad \lor \quad \text{Error Rate } 5xx > 0.05\%$$

---

### 9. Trade-offs

| Pendekatan / Konfigurasi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Rekomendasi Kasus |
| :--- | :--- | :--- | :--- |
| **Kuantisasi INT4 AWQ/GPTQ** | Mengurangi VRAM footprint sebesar $\approx 70\%$; throughput inferensi meningkat $2.5\times\text{--}4\times$. | Kerugian performa minor pada penanganan penalaran kompleks (*complex reasoning*); waktu kompilasi model awal lama. | Inferensi LLM skala masif dengan batasan budget hardware (e.g., L4 / A10G GPUs). |
| **Presisi Penuh FP16/BF16** | Akurasi numerik dan stabilitas matematis identik 100% dengan hasil training. | Membutuhkan GPU VRAM 2x lipat lebih besar; konkurensi batch dibatasi oleh kapasitas HBM. | Sektor kritis tanpa kompromi kesalahan: Diagnostik medis, analisis kepatuhan hukum (*regulatory compliance*). |
| **Speculative Decoding** | Mempercepat *Decode phase* LLM hingga $2\times\text{--}3\times$ latency per token tanpa mengurangi akurasi model utama. | Membutuhkan alokasi VRAM tambahan untuk memuat *Draft Model* kecil; overhead komputasi jika draft model memiliki tingkat penerimaan (*acceptance rate*) $< 60\%$. | Chatbot interaktif low-latency di mana user experience sangat bergantung pada kecepatan token streaming. |
| **Disaggregated Prefill/Decode** | Menghilangkan interferensi komputasi antara fase prefill dan decode; P99 TTFT stabil di bawah beban spike tinggi. | Kompleksitas arsitektur jaringan tinggi (membutuhkan transfer state KV-cache antar pod melalui jaringan berkecepatan tinggi e.g., InfiniBand/RDMA). | Sistem enterprise ultra-scale dengan beban input konteks panjang (e.g., analisis dokumen legal 32k+ token). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **CUDA Out-Of-Memory (OOM) Akibat Static Max Concurrency**: Menyetel parameter konkurensi server tanpa menghitung batas absolut memori KV-cache. Saat 100 request mengirimkan prompt berukuran 4000 token bersamaan, proses crash seketika (*SIGKILL oleh Linux OOM Killer*).
2. **CPU-GPU Sync Bottleneck**: Memanggil operasi sinkronisasi seperti `.cpu()`, `.item()`, atau `print(tensor)` di tengah-tengah loop pemrosesan request. Tindakan ini memaksa GPU pipeline berhenti (*pipeline stall*) menunggu instruksi CPU.
3. **Data Drift False Alarms Akibat Ukuran Window Sampling yang Terlalu Kecil**: Mengukur metrik *Population Stability Index* (PSI) atau *Wasserstein Distance* pada batch data per 1 menit. Deviasi statistik jangka pendek yang normal memicu alarm palsu (*alert fatigue*).

#### Panduan Troubleshooting Operasional
* **Deteksi Memory Leak & Fragmentasi**:
  Jalankan perintah profiling memori internal NVIDIA via runtime shell:
  ```bash
  nvidia-smi --query-gpu=timestamp,memory.used,memory.free,utilization.gpu,utilization.memory --format=csv -l 1
  ```
  Jika memori HBM terus bertambah meski queue kosong, alokator CUDA internal mengalami kebocoran. Terapkan flag `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` untuk mereduksi fragmentasi segmen memori virtual CUDA.
* **Mendiagnosis Latency Spikes (P99 Hang)**:
  Gunakan **NVIDIA Nsight Systems (nsys)** untuk menangkap profiling jejak eksekusi GPU kernel:
  ```bash
  nsys profile --trace=cuda,nvtx,osrt --output=inference_report_%p.qdrep python serving_app.py
  ```
  Analisis visual menggunakan Nsight Systems UI untuk mendeteksi *gap* panjang antar eksekusi kernel yang mengindikasikan bottleneck pada lapisan tokenisasi Python atau deserialisasi gRPC.

---

### 11. Best Practices (Production Checklist)

#### Pre-deployment Checklist
- [ ] Model telah diekspor dan diverifikasi validitas graf komputasinya (ONNX Runtime checker atau TensorRT engine engine validation).
- [ ] Parameter kuantisasi (AWQ/GPTQ/FP8) telah melalui tes regresi akurasi minimum 500 sampel evaluasi standar (*MMLU/Perplexity/F1-score*).
- [ ] Batas atas pemakaian memori KV-cache (`gpu_memory_utilization`) dikunci pada angka aman ($0.85\text{--}0.92$) guna menyisakan ruang untuk alokasi sementara aktivasi kernel.
- [ ] Readiness dan Liveness probe Kubernetes dikonfigurasi menggunakan gRPC health check native, bukan simple HTTP ping yang tidak mengevaluasi kesiapan CUDA runtime.

#### Production Runtime Guardrails
- [ ] Aktifkan *Dynamic Max Context Limiter*: Request dengan total token ($prompt + output$) melebihi kapasitas absolut model ditolak langsung di level gateway (*fail-fast* dengan kode HTTP 400).
- [ ] Pasang circuit breaker pada Envoy/Istio: Buka sirkuit jika latensi rata-rata backend serving melebihi ambang batas degradasi (misal $> 2000\text{ ms}$).
- [ ] Jalankan daemon ekspor metrik hardware native (**NVIDIA DCGM Exporter**) untuk memonitor suhu, throttling hardware, dan konsumsi daya listrik GPU secara granular.

---

### 12. Hands-on Practice

Simpan seluruh file implementasi berikut di direktori target workstation Anda: `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02/triton_repository/simple_dnn/1
cd hands-on/m02
```

#### Langkah 2: Buat Model Dummy dan Ekspor ke ONNX
Buat file `export_onnx.py`:
```python
# hands-on/m02/export_onnx.py
import torch
import torch.nn as nn

class ProductionClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 2)
        )
    def forward(self, x):
        return self.net(x)

model = ProductionClassifier()
model.eval()

dummy_input = torch.randn(1, 32, requires_grad=False)
output_path = "triton_repository/simple_dnn/1/model.onnx"

torch.onnx.export(
    model,
    dummy_input,
    output_path,
    export_params=True,
    opset_version=17,
    do_constant_folding=True,
    input_names=['input_tensor'],
    output_names=['output_tensor'],
    dynamic_axes={
        'input_tensor': {0: 'batch_size'},
        'output_tensor': {0: 'batch_size'}
    }
)
print(f"Model exported successfully to {output_path}")
```
Jalankan skrip:
```bash
python3 export_onnx.py
```

#### Langkah 3: Konfigurasi Model Repository Triton
Buat file `triton_repository/simple_dnn/config.pbtxt`:
```protobuf
name: "simple_dnn"
platform: "onnxruntime_onnx"
max_batch_size: 64

input [
  {
    name: "input_tensor"
    data_type: TYPE_FP32
    dims: [ 32 ]
  }
]

output [
  {
    name: "output_tensor"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

dynamic_batching {
  preferred_batch_size: [ 8, 16, 32, 64 ]
  max_queue_delay_microseconds: 2000
}
```

#### Langkah 4: Deploy Triton Server Menggunakan Docker Container
```bash
docker run --rm -d --gpus all \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/triton_repository:/models \
  --name triton-enterprise-serving \
  nvcr.io/nvidia/tritonserver:24.01-py3 \
  tritonserver --model-repository=/models
```
*Pastikan kesehatan Triton via curl:*
```bash
curl -v localhost:8000/v2/health/ready
```

#### Langkah 5: Load Testing & Metrik Evaluasi dengan Triton Perf Analyzer
Jalankan benchmark performa untuk menguji efisiensi dynamic batching:
```bash
docker run --rm -it --net=host \
  nvcr.io/nvidia/tritonserver:24.01-py3-sdk \
  perf_analyzer -m simple_dnn --percentile=99 --concurrency-range 1:16:2
```

---

### 13. Exercise

#### Level: Easy
Modifikasi file `config.pbtxt` pada latihan Triton di atas:
* Ubah alokasi model agar memiliki **2 model instance** yang berjalan paralel pada 1 GPU yang sama.
* Set `max_queue_delay_microseconds` menjadi 10.000 (10 milidetik).
* Eksekusi `perf_analyzer` kembali dan catat perbedaan *Throughput (Infer/sec)* serta *P99 Latency*.

#### Level: Medium
Tulis sebuah skrip Python berbasis library `onnxruntime` yang melakukan:
1. Membaca model ONNX dari `hands-on/m02/triton_repository/simple_dnn/1/model.onnx`.
2. Melakukan optimasi graf secara programatik (*Graph Optimization Level: ORT_ENABLE_ALL*).
3. Mengeksekusi inferensi benchmark menggunakan profiling mode native ONNX Runtime dan menyimpan output trace JSON untuk dievaluasi.

#### Level: Hard (Argo Rollouts & Istio Canary Deployment Configuration)
Tuliskan manifes Kubernetes lengkap yang terdiri dari:
1. File `Rollout` (API `argoproj.io/v1alpha1`) untuk model inference service dengan strategi Canary:
   * Langkah bertahap: $10\%$, $25\%$, $50\%$.
   * Menghubungkan ke `AnalysisTemplate` yang memicu query Prometheus:
     $$\text{rate}(\text{http_requests_total}\{\text{status}=~"5.*",\text{service}="model-serving"\}[\text{2m}]) > 0.01$$
2. Objek `AnalysisTemplate` dengan mekanisme rollback otomatis jika kondisi kegagalan terpenuhi 2 kali berturut-turut.

---

### 14. Challenge

**Skenario Tantangan**:
Anda adalah Principal Infrastructure Architect pada platform AI Retail Enterprise. Selama periode *Flash Sale*, lalu lintas kueri multimodal (teks dan gambar pengguna) melonjak dari 500 req/sec menjadi 12.000 req/sec secara tiba-tiba.

**Spesifikasi Desain Sistem yang Wajib Anda Rancang (Arsitektural & Konfiguratif)**:
1. **Algoritma Dynamic Request Routing**: Rancang skema mitigasi antrean jika HBM GPU mengalami utilisasi $>95\%$. Bagaimana mekanisme *graceful degradation* (misal: pengalihan sebagian beban non-kritis ke model yang dikuantisasi lebih agresif atau model fallback lokal berbasis CPU)?
2. **Real-time Feature Drift Interceptor**: Model rekomendasi menerima masukan embedding visual pengguna. Rancang skema sistem streaming tanpa jeda (*zero-overhead latency*) yang mampu mendeteksi *covariate shift* pada data embedding berdimensi 512 tanpa memperlambat pipeline response inferensi di bawah 20ms P99.
3. **Penyusunan Fail-Safe Guardrails**: Susun diagram alir arsitektur komprehensif beserta penjelasan komponen konkurensi data pipeline, buffer broker, caching tier (Redis/Dragonfly), dan automated auto-scaling policies menggunakan custom GPU telemetry metrics (Tensor Core active cycle percentage, bukan hanya GPU Memory Used).

*(Kerjakan analisis arsitektur ini secara menyeluruh dalam bentuk dokumen desain teknis formal).*

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa fungsi utama dari alokasi *KV-Cache* dalam inferensi model berbasis Decoder-only Transformer?
2. Bagaimana mekanisme kerja *Dynamic Batching* pada model server seperti Triton Inference Server berbeda dari *Static Batching* konvensional?
3. Sebutkan indikator utama perbedaan antara *Data Drift* dan *Concept Drift* pada sistem inferensi machine learning di produksi.
4. Apa peran dari *Logical Block Table* dalam algoritma *PagedAttention*?
5. Mengapa format representasi graf komputasi teroptimasi seperti ONNX atau TensorRT menghasilkan latensi inferensi yang jauh lebih rendah dibandingkan model PyTorch `.pt` langsung?

#### 5 Pertanyaan Intermediate
6. Mengapa pendekatan *Iteration-Level Continuous Batching* pada LLM jauh lebih superior dalam meningkatkan utilisasi GPU dibandingkan pendekatan *Dynamic Batching* standar yang diterapkan pada model CNN/BERT?
7. Bagaimana kuantisasi jenis **Activation-aware Weight Quantization (AWQ)** melindungi akurasi inferensi LLM dibandingkan teknik *Uniform Post-Training Quantization* standar?
8. Dalam konteks observabilitas performa LLM, jelaskan implikasi teknis jika metrik *Time-To-First-Token* (TTFT) sangat rendah, namun *Time-Per-Output-Token* (TPOT) mengalami lonjakan drastis (*degraded*). Bagian mana dari sistem yang menjadi bottleneck?
9. Jelaskan perbedaan mendasar antara mekanisme deployment *Shadow Traffic (Dark Launch)* dan *Canary Deployment* pada serving model AI enterprise! Kapan Shadow Traffic wajib digunakan?
10. Bagaimana Anda mengonfigurasi Kubernetes Horizontal Pod Autoscaler (HPA) untuk pod inferensi GPU agar tidak mengalami masalah *flapping* (skala naik-turun terlalu cepat) saat terjadi lonjakan traffic burst?

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah kluster LLM serving (vLLM) melayani pengguna enterprise dengan panjang konteks rata-rata 8.000 token. Saat jam puncak, metrik P99 response time tiba-tiba melonjak hingga $10\times$ lipat, dan log server mencatat *Request preemption event: KV-cache blocks evicted to host memory*. Apa akar masalah dari sistem tersebut, dan konfigurasi apa yang harus diubah pada layer engine scheduler?
12. **Skenario 2**: Anda meluncurkan model klasifikasi risiko kredit baru via canary release dengan pembagian traffic $10\%$. Metrik error rate HTTP adalah $0\%$, dan P99 latency berada di bawah ambang $15\text{ ms}$. Namun, sistem peringatan dini mendeteksi metrik *Wasserstein Distance* pada distribusi skor prediksi canary menyimpang $40\%$ dibanding baseline model yang aktif. Keputusan arsitektur apa yang harus diambil oleh automated pipeline, dan bagaimana investigasinya?
13. **Skenario 3**: Perusahaan Anda memproses pipeline NLP multi-tahap: *Speech-to-Text (Whisper)* $\rightarrow$ *Information Extraction (LLaMA-3-8B)* $\rightarrow$ *Sentiment Analysis (RoBERTa)*. Penggunaan REST calls HTTP internal antar kontainer menyebabkan latensi kumulatif membengkak hingga $1.2\text{ detik}$. Rancang perbaikan arsitektur inference pipeline terpadu menggunakan fitur Triton Ensemble dan CUDA Shared Memory untuk memangkas latensi hingga $<400\text{ ms}$.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Pertanyaan Basic
1. KV-Cache menyimpan matriks key dan value dari token yang telah diproses sebelumnya sehingga pada setiap langkah autoregresif baru, model tidak perlu menghitung ulang representasi representasional token masa lalu dari awal.
2. Static batching menuntut ukuran batch penuh sebelum eksekusi dimulai; Dynamic batching menggabungkan kueri yang masuk secara independen dalam sebuah jendela waktu tunda toleransi (*queue delay limit*) hingga batas preferensi batch tercapai untuk dieksekusi bersamaan.
3. *Data Drift* adalah perubahan pada distribusi fitur input data independen $P(X)$ tanpa mengubah relasi dengan label; *Concept Drift* adalah pergeseran relasi fungsional antara fitur input terhadap probabilitas label target $P(Y|X)$.
4. Memetakan alamat blok token logis yang berurutan secara abstrak ke alamat blok memori fisik GPU (HBM) yang tersebar secara non-kontigu, mengeliminasi fragmentasi alokasi VRAM.
5. Menghilangkan ketergantungan pada runtime Python/GIL, menerapkan fusi kernel (*kernel fusion* seperti penggabungan Conv+ReLU), constant folding, serta eliminasi node graf komputasi redundan secara native pada level instruksi instruksi GPU.

#### Jawaban Pertanyaan Intermediate
6. Dynamic batching standar memperlakukan 1 request sebagai 1 kesatuan hingga token terakhir selesai diproduksi. Request dengan prompt pendek terpaksa tertahan menunggu request lain dengan respon token panjang. Continuous batching mengevaluasi batch pada setiap *decoding iteration step*, melepas sequence yang telah menemui token stop dan memasukkan request baru langsung ke dalam slot komputasi yang kosong.
7. AWQ mengobservasi distribusi aktivasi model dan mempertahankan presisi tinggi (FP16) secara selektif hanya pada $1\%$ bobot (*salient weights*) yang memiliki magnitudo aktivasi terbesar, sementara $99\%$ bobot lainnya dikuantisasi menjadi INT4, sehingga mencegah runtuhnya kapabilitas penalaran logis model.
8. TTFT yang cepat berarti fase *Prefill* (pemrosesan input prompt) berjalan efisien dan bandwidth komputasi (*compute-bound*) GPU mencukupi. TPOT yang lambat menunjukkan bahwa fase *Decode* terhambat, yang menandakan *GPU Memory Bandwidth Saturation* (karena autoregresi membaca KV-cache secara serial untuk tiap token) atau konkurensi batch terlalu padat sehingga terjadi *thrashing* cache memori.
9. *Canary Deployment* mengirim sebagian kecil traffic asli ($5\text{--}10\%$) ke model baru di mana pengguna menerima respon model tersebut secara nyata. *Shadow Traffic* menduplikasi 100% traffic produksi nyata ke model baru di latar belakang tanpa mengirim responnya ke klien. Shadow wajib digunakan pada model berisiko kepatuhan tinggi (seperti sistem *Medical Diagnosis* atau *Algorithmic Trading*) untuk memvalidasi stabilitas komputasi dan akurasi tanpa menimbulkan risiko bisnis/finansial bagi pengguna akhir.
10. Konfigurasikan algoritma HPA dengan kebijakan penstabil (*stabilization window*) untuk scale down (misal: 300 detik), gunakan metrik gabungan antara utilisasi Tensor Core GPU melalui DCGM Prometheus Exporter dan kedalaman antrean (*queue length*), serta tetapkan *cooldown period* yang memadai untuk mencegah instansiasi kontainer yang terlalu sering.

#### Panduan Solusi Kasus Produksi
11. **Akar Masalah**: *Memory Exhaustion on KV-Cache*. Kapasitas memori PagedAttention habis terisi oleh request konkurensi tinggi dengan konteks masukan panjang. Engine terpaksa memindahkan (*swap*) blok KV-cache dari VRAM GPU ke RAM Host (CPU memori) atau membatalkan komputasi token yang sedang berjalan (*preemption*). 
    **Solusi**: Turunkan nilai parameter `max_num_seqs` (jumlah konkurensi paralel maksimum yang diproses per iterasi), naikkan `gpu_memory_utilization` ke batas optimal (e.g. 0.95 jika stabil), atau terapkan arsitektur *Chunked Prefill* (`enable_chunked_prefill=True`) agar komputasi prefill masif dapat dipartisi ke dalam batch decode yang lebih teratur.
12. **Keputusan**: Hentikan alur Canary Rollout secara instan via Argo Rollouts (*Abort & Rollback to stable*). 
    **Investigasi**: Kueri log data inferensi canary dan jalankan uji drift multivariat pada feature store untuk mengidentifikasi fitur input mana yang memicu deviasi prediksi. Validasi apakah pipeline preprocessing model canary menerima data dengan skema normalisasi yang berbeda dari model baseline (misal: kegagalan standard scaler atau perbedaan parsing encoding input).
13. **Desain Perbaikan**: 
    Satukan ketiga model tersebut ke dalam satu node/kluster yang dikelola oleh **Triton Ensemble Architecture**. Buat satu file konfigurasi graf pipa `ensemble_scheduler` di Triton. Aliran output tensor dari model Whisper dioperasikan langsung sebagai input tensor model LLaMA dan RoBERTa secara in-memory melalui **CUDA Shared Memory**. Menghapus total overhead serialisasi/deserialisasi JSON via HTTP, menghilangkan overhead transisi jaringan antarmuka TCP/IP, dan memangkas waktu inferensi kumulatif menjadi operasi memori lokal GPU berkecepatan tinggi.

---

### 16. Summary

Modul ini telah membedah arsitektur inferensi skala enterprise untuk model analitis tradisional dan Large Language Model:

* **Engine Level**: Penggunaan runtime modern (Triton Inference Server dan vLLM/TensorRT-LLM) mengeliminasi overhead eksekusi runtime bahasa interpreted dan memaksimalkan saturasi komputasi GPU Tensor Core.
* **Memori & Algoritma**: *PagedAttention* menyelesaikan problem fundamental fragmentasi memori KV-cache pada LLM, yang berkolaborasi dengan *Iteration-Level Continuous Batching* untuk melipatgandakan throughput penyajian token.
* **Infrastruktur Produksi**: Deployment zero-downtime menuntut keterpaduan antara Service Mesh (Istio), orkestrasi rollback otomatis (Argo Rollouts), dan observabilitas mendalam (Prometheus metrics & Evidently AI drift detection) guna mendeteksi kegagalan performa serta anomali statistik data sebelum berdampak sistemik pada layanan enterprise.