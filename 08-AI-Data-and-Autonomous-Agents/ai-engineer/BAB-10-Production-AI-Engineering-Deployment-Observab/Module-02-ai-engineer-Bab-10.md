# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Production AI Engineering: Deployment, Observability, and Operations**
**Jalur Pembelajaran: AI Data and Autonomous Agents (ai-engineer)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Arsitektur Serving LLM Berperforma Tinggi:** Mengonfigurasi dan mengoperasikan mesin inferensi modern (*vLLM*, *Triton Inference Server*) dengan teknik *Continuous Batching*, *PagedAttention*, serta pemisahan fase *Prefill* dan *Decode* (*Disaggregated Serving*).
2. **Mengoptimalkan Alokasi Memori GPU dan Throughput:** Menganalisis utilisasi VRAM, mengeliminasi fragmentasi memori *Key-Value (KV) Cache*, dan menerapkan *Speculative Decoding* serta kuantisasi (AWQ/FP8) untuk mencapai target latensi p99 < 800ms pada beban konkurensi tinggi.
3. **Membangun Pipeline Observabilitas Terdistribusi Kelas Enterprise:** Mengintegrasikan instrumen *OpenTelemetry (OTEL)*, *OpenInference*, *Prometheus*, dan *Grafana* untuk melacak metrik vital inferensi (*Time to First Token / TTFT*, *Time Per Output Token / TPOT*, utilisasi KV-cache) serta mendeteksi *semantic drift* dan halusinasi secara *real-time*.
4. **Menerapkan Pola Deployment Robust & High Availability:** Mengembangkan arsitektur *Canary Deployment*, *Shadow Traffic Routing*, dan *Circuit Breaker Fallback Cascade* untuk menjamin SLA ketersediaan 99.99% pada sistem agen AI otonom berskala besar.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **Sistem Komputasi & Akselerator:** Pemahaman mendalam arsitektur GPU (NVIDIA Ampere/Hopper/Ada Lovelace), hierarki memori (SRAM, HBM/VRAM), mekanisme transfer PCIe/NVLink, dan konsep dasar CUDA execution model (Warps, Blocks, Threads).
* **Transformer Internals:** Mekanisme *Self-Attention*, alokasi tensor matriks $Q, K, V$, kompleksitas komputasi $O(N^2)$ pada fase prefill, dan sifat memory-bandwidth bound pada autoregressive decoding.
* **Jaringan & Kontainerisasi Lanjutan:** Docker, Kubernetes (DaemonSets, Custom Resource Definitions, Device Plugins), gRPC over HTTP/2, IPC, dan reverse proxy networking (Envoy/Nginx).
* **Bahasa Pemrograman & Framework:** Python 3.10+ (AsyncIO tingkat lanjut, multithreading, typing), PyTorch internals, dan dasar-dasar C++ runtime binding.

---

## 3. Concept & Internal Architecture

Menjalankan model dasar (Foundation Model) di lingkungan produksi skala enterprise memerlukan pergeseran paradigma dari *stateless microservices* konvensional ke *stateful accelerator-bound runtime*. 

```
+-----------------------------------------------------------------------------------+
|                            ENTERPRISE AI GATEWAY                                  |
|  - Rate Limiting (Token Bucket)        - Semantic Caching (Redis/Qdrant)          |
|  - Auth & Policy Engine (OPA)          - Adaptive Router (Prefill vs Decode)      |
+-----------------------------------------------------------------------------------+
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
+─────────────────────────────────+             +─────────────────────────────────+
|   PREFILL ENGINE POOL (vLLM)    |             |    DECODE ENGINE POOL (vLLM)    |
|   - Compute-Bound Optimization  |             |   - Memory-Bound Optimization   |
|   - High Tensor Parallelism (TP)|             |   - Chunked Prefill Disabled    |
|   - Slotted Context Processing  |             |   - PagedAttention Allocation   |
+─────────────────────────────────+             +─────────────────────────────────+
        │                                                                 ▲
        └──────────────── KV-Cache Transfer via RDMA / NVLink ────────────┘
                                         │
+----------------------------------------┴------------------------------------------+
|                        OBSERVABILITY & SAFETY CONTROL PLANE                       |
|  - Metrics: Prometheus (TTFT, TPOT, VRAM Saturation, Token Count)                 |
|  - Distributed Traces: OpenTelemetry Collector -> Jaeger/Tempo                    |
|  - Guardrails: Llama-Guard / NeMo Guardrails (Async Out-of-band)                   |
+-----------------------------------------------------------------------------------+
```

### 3.1 Bottleneck Inferensi: Prefill vs. Decode

Inferensi LLM terbagi menjadi dua fase dengan profil beban perangkat keras yang bertolak belakang:

1. **Fase Prefill (Prompt Processing):**
   * **Karakteristik:** Memproses seluruh token input secara paralel.
   * **Bottleneck:** *Compute-bound* (bergantung pada throughput TFLOPS Tensor Core GPU).
   * Kompleksitas matriks: Operasi GEMM (*General Matrix Multiply*) mendominasi utilisasi core GPU.
2. **Fase Decode (Token Generation):**
   * **Karakteristik:** Menghasilkan satu token per langkah secara autoregresif. Setiap token baru membutuhkan pemuatan seluruh bobot model dan *KV Cache* historis dari VRAM (HBM) ke cache chip (SRAM).
   * **Bottleneck:** *Memory-bandwidth bound* (bergantung pada kecepatan transfer byte HBM). Rasio Arithmetic Intensity sangat rendah ($\text{FLOPs} / \text{Byte} \ll 1$).

### 3.2 Inovasi PagedAttention dan Manajemen KV Cache

Pada implementasi naif, alokasi memori untuk *KV Cache* dilakukan secara statis dengan mengasumsikan panjang konteks maksimum (*max sequence length*). Hal ini memicu dua masalah utama:
* **Internal Fragmentation:** Ruang memori dialokasikan untuk 4096 token, tetapi permintaan aktual hanya menggunakan 300 token. Sisa memori terkunci dan terbuang.
* **External Fragmentation:** Alokasi memori berurutan (*contiguous memory*) gagal dilakukan ketika ruang memori terpecah, memicu kondisi *Out-of-Memory (OOM)* meskipun total VRAM bebas masih mencukupi.

**PagedAttention** memecahkan kendala ini dengan mengadopsi konsep *Virtual Memory Paging* dari sistem operasi:
* Memori KV Cache dibagi menjadi blok-blok berukuran tetap (*Physical Block*, misal: 16 atau 32 token).
* Logical Blocks dipetakan ke Physical Blocks melalui *Block Table*.
* Blok fisik tidak perlu berada pada alamat VRAM yang berurutan. Alokasi dilakukan secara *on-demand* saat token baru digenerasi.
* Memungkinkan fitur *Copy-on-Write (CoW)* untuk teknik sampling paralel (seperti beam search atau multi-agent prompting), menghemat VRAM hingga 60-80%.

### 3.3 Disaggregated Prefill and Decode Architecture

Pada arsitektur monolitik konvensional, satu instance GPU melayani fase prefill dan decode sekaligus. Ketika sebuah prompt panjang (misal: dokumen legal 32k token) masuk, proses prefill akan memonopoli komputasi GPU, menyebabkan *head-of-line blocking* yang mengakibatkan lonjakan ekstrem (*latency spikes*) pada metrik *Time Per Output Token (TPOT)* untuk permintaan decode yang sedang berjalan.

Arsitektur produksi modern memisahkan pool inferensi:
1. **Prefill Instances:** Dikonfigurasi dengan paralelisme tinggi (*Tensor Parallelism*, throughput tinggi) untuk menyelesaikan pemrosesan prompt secepat mungkin.
2. **Decode Instances:** Dikonfigurasi untuk throughput konkurensi token tinggi dengan utilisasi bandwidth memori maksimal.
3. **KV Cache Transfer:** State KV Cache ditransfer dari instance Prefill ke instance Decode menggunakan protokol berkecepatan tinggi (seperti RDMA via RoCE v2 atau NVLink).

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?

* **Pendekatan API Naif (Model-as-a-Black-Box via External Vendor):**
  * *Risiko Privasi & Kepatuhan:* Paparan data sensitif (PII/HIPAA/GDPR) ke pihak ketiga.
  * *Ketidakpastian Latensi:* Ketiadaan kontrol atas antrean, *cold starts*, dan degradasi performa (*noisy neighbors*).
  * *Biaya Eksponensial:* Skema penagihan per-token menjadi beban finansial tak terprediksi pada throughput jutaan token per jam.
* **Pendekatan Self-Hosted Naif (HuggingFace Transformers + FastAPI):**
  * *Throughput Rendah:* Hanya mampu memproses antrean secara sekuensial atau batch statis. Begitu satu request selesai lebih cepat, GPU menganggur menunggu request terpanjang dalam batch (*tail latency waste*).
  * *VRAM Waste:* Kehabisan memori pada konkurensi rendah karena manajemen buffer KV yang buruk.

### Apa Solusi Arsitektur Produksi Modern?

Sistem inferensi modern menerapkan integrasi penuh antara:
1. **Dynamic / Continuous Batching:** Memasukkan permintaan baru ke dalam batch komputasi yang sedang berjalan di level iterasi token (bukan level request), menghilangkan *idle time* GPU.
2. **Tensor Parallelism (TP) & Pipeline Parallelism (PP):** Memecah layer dan matriks model ke beberapa GPU secara sinkron menggunakan primitives komunikasi NCCL (`All-Reduce`, `All-Gather`).
3. **Chunked Prefill:** Memecah prompt panjang menjadi potongan-potongan kecil yang diproses bersamaan dengan langkah decode reguler, meredam degradasi TPOT.
4. **Full Observability Harness:** Mengaudit setiap transaksi inferensi dari level hardware (utilisasi SM, temperatur thermal, VRAM allocated) hingga level semantik (penyimpangan distribusi embedding, skor toksisitas, evaluasi fakta).

---

## 5. How (Workflow Detail)

Alur kerja eksekusi inferensi enterprise dari ingress gateway hingga token streaming:

```
[Client] ──(1) HTTP/gRPC Request──> [Envoy AI Gateway]
                                           │
                        (2) Check Token Budget & Cache
                                           │
               ┌───────────────────────────┴───────────────────────────┐
      [Cache Hit]                                                 [Cache Miss]
               │                                                       │
   (3a) Return Embeddings                               (3b) Schedule Request
               │                                                       │
               ▼                                                       ▼
        [Client Response]                                     [vLLM Engine Queue]
                                                                       │
                                                       (4) Allocate Logical Blocks
                                                                       │
                                                       (5) Continuous Batch Iteration
                                                                       │
                                                       (6) Attention Kernel (FlashAttn-3)
                                                                       │
                                                       (7) Sample Output Token
                                                                       │
                                                       (8) Stream Token + Emit OTEL Span
                                                                       │
                                                       (9) Check EOS / Max Tokens
                                                                       │
                                                               ┌───────┴───────┐
                                                          [Cont.]           [Done]
                                                               │               │
                                                           Loop to (5)    (10) Free Blocks
```

1. **Ingress Filtering & Routing:** Client mengirimkan payload inferensi. Gateway mengevaluasi kuota rate-limit berbasis token, memeriksa cache semantik berbasis Cosine Similarity pada vektor database.
2. **Queueing & Block Allocation:** Request masuk ke queue scheduler. Scheduler memeriksa ketersediaan Physical Blocks pada VRAM. Logical Block Table diinisialisasi.
3. **Execution Iteration (Continuous Loop):**
   * *Prefill Chunks:* Potongan prompt diproses bersamaan dengan token decode yang aktif.
   * *Kernel Execution:* Kernel FlashAttention (atau PagedAttention) dieksekusi secara native pada hardware Tensor Core.
   * *Sampling:* Logits dihitung, proses penarikan sampel token (*Greedy*, *Top-P*, *Temperature*) dijalankan pada GPU.
4. **Streaming & Observability Interleaving:**
   * Token yang dihasilkan segera di-*detokenize* dan dikirim via Server-Sent Events (SSE) atau gRPC stream.
   * Metrik latensi antar token (*Inter-Token Latency*) dicatat pada histogram OpenTelemetry.
5. **Deregistrasi:** Ketika token *End-of-Sequence (EOS)* tercapai atau batas *max_tokens* terpenuhi, Scheduler melepaskan Physical Blocks kembali ke pool bebas tanpa alokasi ulang memori OS/CUDA.

---

## 6. Analogy & Diagram ASCII

### Analogi PagedAttention: Sistem Perpustakaan Modern vs. Meja Belajar Statis

* **Pendekatan Tradisional (Statis):** Anda memesan seluruh aula perpustakaan (4096 kursi) untuk satu orang mahasiswa, hanya karena mahasiswa tersebut *mungkin* membawa 4096 halaman buku referensi. Mahasiswa lain dilarang masuk aula meskipun 4000 kursi di dalamnya kosong melompong. Perpustakaan cepat penuh padahal ruangannya sepi.
* **PagedAttention (Dinamis):** Mahasiswa hanya diberikan satu lembar catatan binder pada satu waktu. Saat lembar tersebut penuh, pustakawan mencarikan loker kosong mana pun yang tersedia di gedung (tidak perlu berurutan) dan mencatat nomor lokernya di buku indeks mahasiswa. Jika dua mahasiswa membaca bab buku yang sama persis, mereka berbagi loker yang sama (*Shared Memory/Copy-on-Write*).

### Diagram Memori: Tradisional vs. PagedAttention

```
TRADITIONAL KV ALLOCATION (Contiguous Reservation)
GPU VRAM:
[Req 1: Token 1-10][.......... RESERVED SPACE (WASTED) ..........][Req 2: Token 1-5][.... WASTED ....]
*Masalah: Fragmentasi internal tinggi, OOM terjadi meski 70% VRAM kosong!

PAGEDATTENTION MEMORY LAYOUT (Non-Contiguous Paging)
Logical Blocks (Request 1):   [L_Block 0] -> [L_Block 1] -> [L_Block 2]
                                  │              │              │
                                  ▼              ▼              ▼
Physical VRAM Pool:          [P_Block 8]    [P_Block 2]    [P_Block 14]
                             (Tokens 0-15)  (Tokens 16-31) (Tokens 32-47)

Logical Blocks (Request 2):   [L_Block 0] -> [L_Block 1]
                                  │              │
                                  ▼              ▼
Physical VRAM Pool:          [P_Block 0]    [P_Block 5]
*Keuntungan: Efisiensi memori mendekati 96-98%, kapasitas throughput batch meningkat drastis!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Implementasi Dasar Async Engine vLLM

Contoh dasar berikut mendemonstrasikan bagaimana menginisialisasi engine vLLM secara asinkron dengan konfigurasi memori terpadu:

```python
import asyncio
from vllm import AsyncEngineArgs, AsyncLLMEngine, SamplingParams

async def main():
    # Konfigurasi parameter engine untuk efisiensi produksi
    engine_args = AsyncEngineArgs(
        model="mistralai/Mistral-7B-Instruct-v0.2",
        tensor_parallel_size=1,            # 1 GPU
        gpu_memory_utilization=0.90,       # Cadangkan 90% VRAM untuk model & KV cache
        max_model_len=4096,
        enforce_eager=False                # Gunakan CUDA Graphs untuk akselerasi
    )
    
    engine = AsyncLLMEngine.from_engine_args(engine_args)
    
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.95,
        max_tokens=150
    )
    
    prompt = "Jelaskan perbedaan mendasar antara latensi prefill dan latensi decode."
    request_id = "req-001"
    
    # Menjalankan inferensi dan streaming token output
    results_generator = engine.generate(prompt, sampling_params, request_id)
    
    print(f"Prompt: {prompt}\nResponse: ", end="", flush=True)
    async for request_output in results_generator:
        # Mengambil delta token terbaru
        text = request_output.outputs[0].text
        print(text, end="\r", flush=True)
    print("\n\nInferensi selesai.")

if __name__ == "__main__":
    asyncio.run(main())
```

### 7.2 Practical Example: Enterprise Production Server dengan OpenTelemetry & Prometheus

Implementasi standar industri di bawah ini mencakup:
* Integrasi **FastAPI** asinkron.
* Custom **Prometheus Metrics** untuk *TTFT*, *TPOT*, dan pemantauan utilisasi *KV-Cache*.
* Tracing terdistribusi menggunakan **OpenTelemetry**.
* Penanganan lifecycle shutdown yang aman (*graceful shutdown*).

```python
import time
import uuid
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.sampling_params import SamplingParams

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# --- 1. INISIALISASI OBSERVABILITY (OpenTelemetry & Prometheus) ---
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer("production-llm-engine", "1.0.0")
span_processor = BatchSpanProcessor(ConsoleSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)

HISTOGRAM_TTFT = Histogram(
    "llm_time_to_first_token_seconds",
    "Durasi pemrosesan prompt hingga emisi token pertama",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
HISTOGRAM_TPOT = Histogram(
    "llm_time_per_output_token_seconds",
    "Durasi generasi per token lanjutan pada fase decode",
    buckets=[0.01, 0.02, 0.04, 0.08, 0.16, 0.32]
)
COUNTER_TOKENS_TOTAL = Counter(
    "llm_generated_tokens_total",
    "Total token yang diproses oleh engine",
    ["type"]
)
GAUGE_ACTIVE_REQUESTS = Gauge(
    "llm_active_requests",
    "Jumlah inferensi yang sedang berjalan secara paralel"
)

# --- 2. ENGINE LIFECYCLE MANAGEMENT ---
engine: AsyncLLMEngine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine_args = AsyncEngineArgs(
        model="Qwen/Qwen2.5-7B-Instruct",
        tensor_parallel_size=1,
        gpu_memory_utilization=0.85,
        max_model_len=4096,
        max_num_seqs=128,              # Konkurensi dinamis maksimum
        disable_log_requests=True      # Hindari logging berlebih di jalur cepat
    )
    engine = AsyncLLMEngine.from_engine_args(engine_args)
    yield
    # Graceful teardown bila diperlukan

app = FastAPI(title="Enterprise LLM Serving Subsystem", lifespan=lifespan)

# --- 3. PYDANTIC SCHEMAS ---
class InferenceRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)

# --- 4. INFERENCE STREAMING GENERATOR ---
async def stream_tokens(
    request_id: str,
    prompt: str,
    sampling_params: SamplingParams,
    parent_span_context
) -> AsyncGenerator[str, None]:
    GAUGE_ACTIVE_REQUESTS.inc()
    start_time = time.perf_counter()
    first_token_received = False
    last_token_time = start_time
    total_tokens_emitted = 0

    with tracer.start_as_current_span("vllm_generate_stream", context=parent_span_context) as span:
        span.set_attribute("llm.request_id", request_id)
        span.set_attribute("llm.prompt_len", len(prompt))
        
        try:
            results_generator = engine.generate(prompt, sampling_params, request_id)
            async for request_output in results_generator:
                current_time = time.perf_counter()
                
                # Menghitung Metrik TTFT
                if not first_token_received:
                    ttft = current_time - start_time
                    HISTOGRAM_TTFT.observe(ttft)
                    span.set_attribute("llm.ttft_seconds", ttft)
                    first_token_received = True
                else:
                    # Menghitung Metrik TPOT
                    tpot = current_time - last_token_time
                    HISTOGRAM_TPOT.observe(tpot)
                
                last_token_time = current_time
                
                # Ekstrak delta teks
                output = request_output.outputs[0]
                chunk = output.text_diff if hasattr(output, "text_diff") else output.text
                
                total_tokens_emitted = len(output.token_ids)
                yield f"data: {chunk}\n\n"
                
            COUNTER_TOKENS_TOTAL.labels(type="output").inc(total_tokens_emitted)
            span.set_attribute("llm.output_tokens_len", total_tokens_emitted)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            yield f"data: [ERROR: {str(e)}]\n\n"
        finally:
            GAUGE_ACTIVE_REQUESTS.dec()

# --- 5. CONTROLLER ENDPOINTS ---
@app.post("/v1/chat/completions")
async def chat_completions(req: InferenceRequest, raw_request: Request):
    if engine is None:
        raise HTTPException(status_code=503, detail="LLM Engine belum siap.")

    # Ekstraksi Context Distributed Trace dari Ingress W3C Headers
    carrier = dict(raw_request.headers)
    context = TraceContextTextMapPropagator().extract(carrier=carrier)
    
    request_id = f"gen-{uuid.uuid4().hex}"
    sampling_params = SamplingParams(
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens
    )

    COUNTER_TOKENS_TOTAL.labels(type="input").inc(len(req.prompt.split()))

    return StreamingResponse(
        stream_tokens(request_id, req.prompt, sampling_params, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id
        }
    )

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Tier-1 FinTech Core Banking - Fraud Analysis & Chat Gateway
* **Profil Beban:** 12.000 Request per Menit (200 RPS) pada jam sibuk.
* **Kebutuhan SLA:** 
  * P99 Time to First Token (TTFT) < 400ms.
  * P99 Time Per Output Token (TPOT) < 25ms.
  * Zero Data Exfiltration (regulasi data finansial ketat / OJK & ISO 27001).

### Detail Arsitektur & Strategi Mitigasi

```
                             [Inbound 200 RPS Client Traffic]
                                            │
                                            ▼
                    +───────────────────────────────────────────────+
                    |    Envoy Proxy (mTLS Termination + Rate Limit)|
                    +───────────────────────────────────────────────+
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
       +───────────────────────────+                 +───────────────────────────+
       |   AZ-1 Inference Cluster  |                 |   AZ-2 Inference Cluster  |
       |  (Active)                 |                 |  (Active)                 |
       |                           |                 |                           |
       | 4x H100 80GB (NVLink)     |                 | 4x H100 80GB (NVLink)     |
       | vLLM v0.6+                |                 | vLLM v0.6+                |
       | Model: Llama-3.1-70B-FP8  |                 | Model: Llama-3.1-70B-FP8  |
       | TP=4, Chunked Prefill=ON  |                 | TP=4, Chunked Prefill=ON  |
       +───────────────────────────+                 +───────────────────────────+
                     │                                             │
                     └──────────────────────┬──────────────────────┘
                                            │
                                            ▼
       +─────────────────────────────────────────────────────────────────────────+
       |               Fallback Circuit Breaker (Hystrix Pattern)                |
       |   If Cluster p99 > 800ms OR Error Rate > 1%:                            |
       |   Route to Small Fast Engine (Mistral-7B-AWQ on 1x A100 per AZ)        |
       +─────────────────────────────────────────────────────────────────────────+
```

1. **Pemilihan Format Presisi dan Paralelisme:**
   * Menggunakan model **Llama-3.1-70B** terkuantisasi **FP8 (Floating Point 8)**. Bobot model membutuhkan ~70 GB VRAM, menyisakan sisa memori besar pada node 4x H100 (total 320 GB HBM3) murni untuk KV Cache blocks.
   * Menggunakan **Tensor Parallelism (TP=4)** via NVLink inter-GPU bandwidth (900 GB/s), memastikan komunikasi `All-Reduce` tidak menjadi bottleneck.
2. **Chunked Prefill Implementation:**
   * Menetapkan parameter `enable_chunked_prefill=True` dengan `max_num_batched_tokens=512`. Prompt perbankan berukuran besar (rekam jejak transaksi nasabah) dipecah rata sehingga tidak melumpuhkan token decode yang sedang streaming ke nasabah lain.
3. **Hasil Benchmark Produksi:**
   * Rata-rata Utilisasi VRAM KV Cache stabil di 85-88%.
   * P99 TTFT terpangkas dari **2.400ms** (arsitektur naif) menjadi **320ms**.
   * P99 TPOT stabil pada **18ms per token**.

---

## 9. Trade-offs

Setiap parameter konfigurasi inferensi produksi membawa kompromi teknik yang signifikan:

| Parameter Arsitektur | Keuntungan | Kerugian / Risiko | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Tensor Parallelism (TP) Tinggi** (e.g., TP=8) | Latensi per token lebih rendah; mampu memuat model berukuran sangat besar. | Terikat interkoneksi perangkat keras (wajib NVLink/NVSwitch). Skalabilitas menurun tajam jika menggunakan interkoneksi PCIe standar. | Model > 70B parameter pada node HGX/DGX kelas atas. |
| **FP8 / AWQ 4-bit Quantization** | Kebutuhan memori berkurang hingga 50-75%; throughput batching melonjak drastis. | Potensi degradasi kemampuan penalaran kompleks (*reasoning degradation*) atau sintaksis format khusus (JSON schema). | Task klasifikasi teks, percakapan natural, routing, peringkasan dokumen. |
| **Agresif Dynamic Batching** (`max_num_seqs > 256`) | Throughput keseluruhan sistem ($Tokens/Sec$) optimal secara ekonomi. | Latensi TPOT meningkat bagi setiap individu klien (*Jitter* tinggi); risiko memori meledak bila prompt panjang. | Sistem pemrosesan batch *asynchronous* (e.g., ekstraksi dokumen massal malam hari). |
| **Aggressive Speculative Decoding** | Mempercepat fase decode hingga 2x-3x lipat pada skenario teks deterministik. | Memboroskan resource VRAM dan komputasi GPU sekunder jika draft model sering salah tebak (*acceptance rate* < 50%). | Skenario generasi kode sumber, sintaksis terstruktur kaku (JSON generation). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Degradation: KV-Cache Truncation Tanpa Notifikasi
* **Gejala:** Engine tidak mengalami crash (*no OOM*), tetapi model tiba-tiba mulai menjawab tidak nyambung, melupakan instruksi sistem, atau memotong kalimat secara prematur.
* **Penyebab:** Konfigurasi parameter `max_model_len` pada runtime diset lebih rendah daripada ukuran prompt input, atau gateway memotong konteks tanpa melempar error HTTP 400.
* **Solusi Debugging:**
  Verifikasi alokasi token aktual pada log vLLM:
  ```bash
  # Periksa panjang token prompt vs batas model
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "test", "prompt": "...", "max_tokens": 100}' -v
  ```
  Pasang validasi ketat pada lapisan ingress gateway: jika `input_tokens + max_tokens > max_model_len`, tolak request sebelum mencapai queue engine.

### 10.2 CUDA Out of Memory (OOM) Saat Runtime Berjalan Stabil
* **Gejala:** Sistem berjalan lancar selama 2 jam, kemudian tiba-tiba melempar error: `CUDA out of memory. Tried to allocate X MiB`.
* **Penyebab:** Fragmentasi memori akibat alokasi PyTorch di luar kontrol engine vLLM (misal: proses embedding tambahan yang dijalankan dalam container yang sama) atau parameter `gpu_memory_utilization` disetel terlalu tinggi (misal: `0.98`), tidak menyisakan ruang bagi kernel kompilasi dinamis CUDA Graphs.
* **Solusi:**
  Setel batasan ketat alokasi memori vLLM ke nilai aman (`0.85` hingga `0.90`). Pastikan tidak ada library lain yang memanggil `torch.cuda.empty_cache()` atau mengalokasikan tensor pada runtime yang sama.

### 10.3 Tail Latency Explosion Akibat Chunked Prefill Misconfiguration
* **Gejala:** Rata-rata latensi sangat baik, tetapi metrik P99 melonjak hingga 5-10 detik secara acak.
* **Penyebab:** Konfigurasi `max_num_batched_tokens` bernilai terlalu besar (misal: > 8192) sementara sistem menerima dokumen teks berukuran besar, membuat proses prefill memblokir proses batch decoding yang sedang berjalan.
* **Solusi:**
  Turunkan nilai `max_num_batched_tokens` ke angka 512 atau 1024 pada model 7B-14B untuk membagi proses prefill ke dalam potongan komputasi yang seragam.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa kesiapan operasional berikut sebelum meluncurkan sistem inferensi AI ke produksi:

### Resource & Compute
- [ ] Model dieksekusi dengan *FlashAttention-2* atau *PagedAttention* yang aktif natively (verifikasi via log driver CUDA).
- [ ] Interkoneksi multi-GPU terverifikasi menggunakan protokol P2P NVLink (`nvidia-smi topo -m` menunjukkan status `NV#`).
- [ ] Kuota VRAM teralokasi: minimal 10-15% ruang kosong disisakan untuk CUDA Graphs dan workspace buffers (`gpu_memory_utilization <= 0.90`).
- [ ] Penggunaan CPU Core diisolasi via `numactl` untuk membatasi overhead transfer data cross-socket NUMA.

### Scalability & Availability
- [ ] Mekanisme *Health Probe* (`/health` & `/ready`) dikonfigurasi dengan validasi respons faktual (bukan sekadar HTTP ping).
- [ ] Timeout limit terpasang berjenjang: Gateway Timeout (e.g., 60s), Engine Scheduler Queue Timeout (e.g., 10s).
- [ ] Arsitektur Auto-scaling (KEDA / HPA) dipicu oleh metrik antrean internal (`vllm:num_requests_waiting`), bukan metrik utilisasi CPU/GPU standar.

### Observability & Security
- [ ] PII Stripping / Masking engine terpasang secara *inline* sebelum request menyentuh queue engine AI.
- [ ] Metrik p95/p99 untuk TTFT, TPOT, dan Total Request Duration diekspor ke Prometheus.
- [ ] Distributed tracing W3C context dilewatkan secara transparan di seluruh lapisan microservices.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah kluster inferensi siap-produksi lengkap dengan monitoring metrics Prometheus dan OpenTelemetry tracing.

### Struktur Direktori Hands-on
Pastikan struktur folder Anda tersusun sebagai berikut:
```text
hands-on/m02/
├── config/
│   └── prometheus.yml
├── docker-compose.yml
├── requirements.txt
├── server.py
└── test_client.py
```

### Langkah 1: Siapkan Environment Dependency
Simpan dependensi ke dalam file `hands-on/m02/requirements.txt`:
```text
vllm>=0.6.2
fastapi>=0.115.0
uvicorn>=0.31.0
pydantic>=2.9.0
prometheus-client>=0.21.0
opentelemetry-api>=1.27.0
opentelemetry-sdk>=1.27.0
httpx>=0.27.2
```

### Langkah 2: Konfigurasi Monitoring Prometheus
Simpan file `hands-on/m02/config/prometheus.yml`:
```yaml
global:
  scrape_interval: 2s

scrape_configs:
  - job_name: "llm-serving-engine"
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

### Langkah 3: Setup Orkestrasi Docker Compose
Simpan file `hands-on/m02/docker-compose.yml` untuk memonitor infrastruktur:
```yaml
services:
  prometheus:
    image: prom/prometheus:v2.54.1
    container_name: production-ai-prometheus
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Langkah 4: Implementasi Engine Core
Gunakan kode dari **Seksi 7.2 (Practical Example)** dan simpan ke dalam `hands-on/m02/server.py`.

### Langkah 5: Skrip Uji Beban Paralel
Simpan file `hands-on/m02/test_client.py` untuk mensimulasikan beban konkurensi:
```python
import asyncio
import httpx
import time

URL = "http://localhost:8000/v1/chat/completions"

PROMPTS = [
    "Jelaskan konsep arsitektur microservices dalam 3 kalimat.",
    "Bagaimana prinsip kerja algoritma continuous batching pada GPU?",
    "Berikan contoh kode implementasi singleton pattern di bahasa Rust.",
    "Analisis kelemahan protokol HTTP/1.1 dibanding HTTP/2 dan HTTP/3."
] * 10  # 40 request konkuren

async def send_inference_request(client: httpx.AsyncClient, request_id: int, prompt: str):
    start = time.perf_counter()
    payload = {
        "prompt": prompt,
        "temperature": 0.5,
        "max_tokens": 128
    }
    
    first_token_time = None
    total_tokens = 0
    
    try:
        async with client.stream("POST", URL, json=payload, timeout=60.0) as response:
            if response.status_code != 200:
                print(f"[Req {request_id}] Gagal: HTTP {response.status_code}")
                return
            
            async for chunk in response.aiter_text():
                if chunk and first_token_time is None:
                    first_token_time = time.perf_counter()
                total_tokens += 1
                
        total_duration = time.perf_counter() - start
        ttft = (first_token_time - start) if first_token_time else 0
        print(f"[Req {request_id:02d}] Sukses | TTFT: {ttft*1000:.1f}ms | Total Waktu: {total_duration:.2f}s")
    except Exception as e:
        print(f"[Req {request_id:02d}] Exception: {str(e)}")

async def main():
    print(f"Memulai pengujian beban terhadap {len(PROMPTS)} request...")
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            send_inference_request(client, idx, prompt)
            for idx, prompt in enumerate(PROMPTS)
        ]
        start_benchmark = time.perf_counter()
        await asyncio.gather(*tasks)
        print(f"Uji beban selesai dalam {time.perf_counter() - start_benchmark:.2f} detik.")

if __name__ == "__main__":
    asyncio.run(main())
```

### Langkah 6: Instruksi Eksekusi Hands-on
1. Jalankan Prometheus:
   ```bash
   cd hands-on/m02
   docker compose up -d
   ```
2. Jalankan Server Production LLM (Pastikan CUDA driver terpasang jika menggunakan GPU fisik, atau gunakan mode eager testing):
   ```bash
   python server.py
   ```
3. Di terminal terpisah, jalankan simulasi konkurensi:
   ```bash
   python test_client.py
   ```
4. Buka Prometheus di `http://localhost:9090` dan jalankan kueri:
   ```text
   histogram_quantile(0.99, sum(rate(llm_time_to_first_token_seconds_bucket[1m])) by (le))
   ```

---

## 13. Exercise

### Level Easy
Modifikasi skrip `hands-on/m02/server.py` agar mengekspor metrik Prometheus baru bernama `llm_failed_requests_total` yang menghitung berapa kali terjadi kegagalan komputasi akibat timeout atau payload yang melebihi batas token.
* **Ekspektasi Output:** Counter bertambah setiap kali exception dilempar pada blok `stream_tokens`.

### Level Medium
Implementasikan skema *Semantic Caching* sederhana menggunakan struktur data in-memory (atau Redis) pada lapisan sebelum `engine.generate` dipanggil. 
* Hitung representasi embedding teks prompt masukan.
* Jika kemiripan (*cosine similarity*) dengan prompt terdahulu $\ge 0.95$, kembalikan respons langsung dari cache tanpa memicu inferensi GPU.
* Ukur perbedaan TTFT antara skenario Cache Hit vs. Cache Miss.

### Level Hard
Buat implementasi kustom *Dynamic Output Length Estimator*. Rancang middleware asinkron yang melakukan kalkulasi *pre-flight heuristic* terhadap input prompt:
* Jika input prompt mengandung kata kunci instruksi singkat (e.g., "Ya/Tidak", "Pilihan Ganda"), paksa nilai `max_tokens` menjadi bernilai kecil secara dinamis.
* Alokasikan request tersebut ke queue prioritas tinggi vLLM (`priority=0`), sementara request dengan ekspektasi output panjang dialokasikan ke queue sekunder (`priority=1`).
* Buktikan terjadinya reduksi latensi TTFT pada antrean prioritas tinggi di bawah beban saturasi GPU 100%.

---

## 14. Challenge

### Studi Kasus Produksi Nyata: "The Zero-Downtime Migration of a Multi-Tenant Agent Engine"

Sebuah perusahaan logistik global mengoperasikan platform agen otonom yang memproses dokumen airway bill selama 24/7 tanpa jendela henti operasional (*zero maintenance window*). Kluster inferensi eksisting berjalan di atas 16 node A100 (80GB) yang menjalankan model monolitik Llama-2-70B FP16 dengan arsitektur vLLM versi terdahulu.

#### Sasaran Arsitektur:
Anda ditunjuk sebagai Principal AI Architect untuk memimpin migrasi infrastruktur ini ke kluster berbasis H100 dengan Llama-3.3-70B berbasis FP8 dan konfigurasi *Disaggregated Prefill and Decode*.

#### Kendala Operasional:
1. **Zero Data Loss & No Failed Inferences:** Klien korporat tidak boleh menerima respons HTTP 5xx atau pemutusan koneksi streaming selama proses pergeseran beban.
2. **Keterbatasan Kapasitas Bertahap:** Node H100 baru akan masuk secara bertahap (4 node per minggu selama 1 bulan).
3. **Pemberlakuan Fallback Otomatis:** Jika model baru menghasilkan *hallucination score* di atas ambang batas 0.05 (dievaluasi secara asinkron oleh SLM evaluator out-of-band), jalur request untuk tenant yang bersangkutan harus dikembalikan ke kluster lama secara transparan.

#### Tugas Rekayasa:
Rancang dokumen arsitektur komprehensif yang memuat:
1. Desain *Network Topology Traffic Shifting* (menggunakan service mesh seperti Istio/Envoy) untuk membagi traffic secara persentil bertahap (*Canary & Shadow Deployment*).
2. Mekanisme sinkronisasi state atau penanganan *KV-Cache drain* yang aman pada instance lama sebelum node dinonaktifkan (*Node Draining Strategy*).
3. Desain sistem evaluasi otomatis *in-flight guardrail* yang bertindak sebagai *Circuit Breaker* adaptif jika terjadi anomali drift semantik pada model baru.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (Basic)

#### Q1: Mengapa fase Decode pada eksekusi LLM dikategorikan sebagai memory-bandwidth bound, bukan compute-bound?
* **Jawaban:** Karena pada setiap langkah decode autoregresif, model hanya menghasilkan satu token. Untuk memproses satu token tersebut, akselerator (GPU) wajib memuat seluruh bobot parameter model dan riwayat KV Cache dari HBM (High Bandwidth Memory) ke SRAM lokal chip. Rasio operasi floating point terhadap jumlah byte yang harus ditransfer sangat rendah, sehingga kecepatan pemrosesan dibatasi oleh seberapa cepat memori fisik dapat mentransfer data, bukan kecepatan komputasi Tensor Cores.

#### Q2: Apa perbedaan fundamental antara Continuous Batching (Iteration-level Batching) dan Static Batching konvensional?
* **Jawaban:** Static batching menunggu seluruh request dalam batch menyelesaikan generasi seluruh tokennya hingga token terakhir sebelum membebaskan resource atau menerima batch baru, menyebabkan pemborosan resource saat ada request pendek. Continuous batching beroperasi pada tingkat iterasi kalkulasi token tunggal; begitu sebuah request selesai (menemui EOS), posisinya dalam slot komputasi langsung digantikan oleh request baru dari antrean pada iterasi berikutnya tanpa harus menunggu request lain selesai.

#### Q3: Masalah apa yang diselesaikan oleh inovasi PagedAttention pada arsitektur vLLM?
* **Jawaban:** PagedAttention mengeliminasi fragmentasi memori internal dan eksternal pada alokasi KV-Cache GPU dengan membagi memori cache menjadi blok-blok diskrit berukuran tetap yang dipetakan secara non-kontigu melalui tabel alamat virtual, memangkas pemborosan memori hingga 60-80% dan melipatgandakan kapasitas throughput batch.

#### Q4: Apa perbedaan metrik TTFT (Time to First Token) dan TPOT (Time Per Output Token)?
* **Jawaban:** TTFT mengukur durasi sejak request pertama kali dikirim hingga token output pertama berhasil dihasilkan (merefleksikan fase Prefill pemrosesan prompt), sedangkan TPOT mengukur rata-rata durasi yang dibutuhkan untuk menghasilkan setiap token tambahan setelah token pertama (merefleksikan kecepatan fase autoregressive Decode).

#### Q5: Mengapa parameter Tensor Parallelism (TP) umumnya dibatasi hanya dalam satu server/node fisik yang sama?
* **Jawaban:** Tensor Parallelism memecah matriks layer model dan membutuhkan komunikasi sinkron antar-GPU pada setiap layer melalui operasi `All-Reduce`. Operasi ini membutuhkan latency jaringan ultra-rendah dan bandwidth sangat besar (seperti NVLink ~900 GB/s). Jika dijalankan lintas server melalui kabel jaringan biasa (misal PCIe atau Ethernet standar), komunikasi jaringan akan mengalami bottleneck parah yang melumpuhkan performa inferensi.

---

### Bagian B: Analisis Tingkat Menengah (Intermediate)

#### Q6: Dalam kondisi apa penggunaan Speculative Decoding justru memperburuk throughput dan latensi sistem inferensi?
* **Jawaban:** Speculative Decoding memperburuk performa jika *Acceptance Rate* (tingkat kecocokan token dari model draft kecil dengan model target besar) sangat rendah (misal < 50-60%). Skenario ini terjadi pada teks yang membutuhkan penalaran logika rumit, instruksi acak non-deterministik, atau domain bahasa yang sangat spesifik di mana draft model sering salah menebak. Akibatnya, GPU membuang siklus komputasi untuk memverifikasi dan membatalkan token tebakan yang salah, menambah overhead komputasi tanpa memberikan akselerasi.

#### Q7: Jelaskan fenomena "Head-of-Line Blocking" pada pemrosesan LLM monolitik dan bagaimana Chunked Prefill mengatasi hal tersebut!
* **Jawaban:** Head-of-Line Blocking terjadi ketika request baru dengan prompt yang sangat panjang (misal 16k token) masuk ke engine saat engine sedang menjalankan fase decode untuk puluhan request aktif. Komputasi prefill yang masif menyita resource GPU secara eksklusif selama beberapa detik, menyebabkan proses decode tertunda dan memicu lonjakan ekstrem pada latensi TPOT klien lain. Chunked Prefill mengatasi ini dengan memotong prompt panjang menjadi beberapa sub-batch kecil (chunks) yang disisipkan secara bertahap bersamaan dengan komputasi token decode reguler pada setiap siklus iterasi.

#### Q8: Bagaimana arsitektur Disaggregated Serving (pemisahan pool Prefill dan Decode) dapat mengoptimalkan efisiensi perangkat keras GPU?
* **Jawaban:** Arsitektur ini memungkinkan pemilihan hardware dan konfigurasi paralelisme yang disesuaikan dengan karakteristik beban:
1. Pool Prefill dioptimalkan untuk beban *compute-bound* dengan mengonfigurasi Tensor Parallelism tinggi pada GPU berkemampuan TFLOPS masif untuk memproses prompt secepat mungkin.
2. Pool Decode dioptimalkan untuk beban *memory-bound* dengan alokasi ukuran batch besar untuk memaksimalkan utilisasi bandwidth memori.
Hal ini mencegah interferensi antar dua fase komputasi yang saling bertolak belakang dan mengeliminasi variansi pada TPOT.

#### Q9: Mengapa metrik utilisasi GPU standar dari `nvidia-smi` (GPU-Util %) sering menyesatkan ketika mengevaluasi efisiensi runtime inferensi LLM?
* **Jawaban:** Metrik `GPU-Util` pada `nvidia-smi` hanya membaca persentase waktu di mana setidaknya satu kernel CUDA aktif berjalan di GPU dalam rentang waktu sampel tertentu. Metrik ini tidak mencerminkan utilisasi sebenarnya dari Tensor Cores, jumlah SM yang idle, atau apakah komputasi terhenti (*stalled*) akibat menunggu data dari memori (memory starvation). GPU bisa menunjukkan utilitas 100% pada `nvidia-smi` padahal sebenarnya hanya menjalankan loop decode yang terhambat bandwidth memori dengan saturasi komputasi nyata di bawah 20%.

#### Q10: Apa implikasi teknis penggunaan kompresi bobot model FP8 dibanding AWQ 4-bit terhadap akurasi dan performa hardware generasi Hopper (H100)?
* **Jawaban:** Format FP8 didukung secara native oleh Tensor Cores arsitektur Hopper dengan kecepatan pemrosesan instruksi hardware penuh tanpa overhead proses dekuantisasi on-the-fly. Kualitas akurasi dan penalaran matematis FP8 hampir identik dengan presisi 16-bit asli (FP16/BF16). Sebaliknya, AWQ 4-bit membutuhkan unpacking/dekuantisasi dari 4-bit ke 16-bit di register GPU sebelum komputasi GEMM dijalankan, yang meskipun menghemat VRAM lebih banyak, dapat membebani register file GPU dan berisiko mendegradasi kemampuan penalaran kompleks model.

---

### Bagian C: Pemecahan Masalah Skenario Kasus Produksi (Production Scenarios)

#### Skenario 1: Latency Spike Misterius pada Kluster Produksi
* **Kasus:** Kluster inferensi vLLM Anda melayani model 70B pada 4x GPU H100. Metrik rata-rata p50 TTFT berada di angka 200ms. Namun, metrik p99 melonjak secara sporadis hingga 12.000ms setiap 15 menit sekali, bertepatan dengan hilangnya sebagian koneksi SSE client (*Client Timeout*). Log engine tidak menunjukkan terjadinya crash atau OOM.
* **Pertanyaan Analisis:** Apa akar penyebab paling mungkin dari masalah ini pada konfigurasi runtime/sistem operasi, dan bagaimana langkah mitigasi konkretnya?
* **Analisis & Solusi Rekayasa:**
  1. *Akar Masalah:* Kejadian periodik 15 menit sekali yang memicu spike latensi masif tanpa OOM umumnya disebabkan oleh salah satu dari dua faktor:
     * **PyTorch CPU Garbage Collection / Memory Compaction:** Alokasi tensor dinamis pada host CPU memicu garbage collection global yang membekukan (*freeze*) event loop Python AsyncIO.
     * **Swap Memory Activity / Linux Transparent Huge Pages (THP):** Sistem operasi mencoba mendefrag atau menukar (*swap*) blok memori pinned vLLM ke disk karena kehabisan RAM host (bukan VRAM).
     * **CUDA Graph Recapturing:** Adanya variasi panjang sequence ganjil yang tidak tertampung dalam bucket kompilasi CUDA Graph statis sehingga engine terpaksa menghentikan eksekusi untuk mengompilasi ulang kernel secara runtime.
  2. *Mitigasi:*
     * Nonaktifkan THP pada OS level: `echo never > /sys/kernel/mm/transparent_hugepage/enabled`.
     * Kunci alokasi memori fisik host RAM dengan mengaktifkan lock memory space (`mlockall`).
     * Batasi variasi ukuran batch CUDA graphs pada argumen engine vLLM dan pastikan memory swap GPU diset ke nol: `--swap-space 0`.

#### Skenario 2: Bencana Silent Truncation pada Model Extraction
* **Kasus:** Perusahaan Anda menjalankan pipeline ekstraksi data entitas dari dokumen polis asuransi format PDF panjang. Hasil ekstraksi disimpan ke dalam database. Tim QA menemukan bahwa sekitar 5% data polis kehilangan field-field krusial di bagian akhir dokumen. Tidak ada error HTTP yang terdeteksi di log gateway.
* **Pertanyaan Analisis:** Mengapa fenomena ini terjadi pada layer serving vLLM/FastAPI dan arsitektur validasi apa yang harus dipasang untuk mencegah silent failure ini?
* **Analisis & Solusi Rekayasa:**
  1. *Akar Masalah:* Terjadi *silent truncation* karena panjang prompt input ditambah `max_tokens` melebihi `max_model_len` yang didukung engine, atau parameter `truncation` pada tokenizer vLLM secara default memotong teks dari sisi kanan/akhir tanpa melempar status error. Akibatnya, bagian akhir polis yang memuat informasi krusial tidak pernah masuk ke jendela konteks model.
  2. *Mitigasi:*
     * Pasang *Pre-flight Tokenizer Guard* pada Ingress API Gateway: hitung jumlah token prompt menggunakan tokenizer lokal native yang identik secara deterministik sebelum mengirim payload ke GPU queue.
     * Konfigurasikan response behavior ketat: tolak request dengan error status code `HTTP 413 Payload Too Large` (disertai payload detail: `token_count` vs `max_limit`) daripada memotong teks secara diam-diam.
     * Pasang monitoring metrik prometheus untuk memeriksa output finish reason: tandai request yang selesai dengan status `length` bukan `stop` sebagai peringatan potensi output terpotong.

#### Skenario 3: Starvation pada Kluster Multi-Tenant Akibat Noisy Neighbor
* **Kasus:** Dua divisi berbagi kluster inferensi yang sama: Divisi Analitika (mengirim batch job besar ribuan dokumen teks panjang di latar belakang) dan Divisi Chatbot Customer Service (membutuhkan respons interaktif instan p99 < 500ms). Saat Divisi Analitika menjalankan job, latensi chatbot melonjak hingga 8 detik, memicu komplain dari customer.
* **Pertanyaan Analisis:** Rancang strategi alokasi scheduling dan penyesuaian arsitektur serving untuk mengisolasi beban kerja tersebut tanpa harus membeli perangkat GPU baru!
* **Analisis & Solusi Rekayasa:**
  1. *Akar Masalah:* Penjadwal (*scheduler*) engine memperlakukan seluruh token dalam satu queue FIFO flat secara merata. Batch besar dari Divisi Analitika mendominasi alokasi Physical Block KV-Cache dan jatah komputasi batch iterasi, membuat request chatbot mengalami starvation di dalam antrean.
  2. *Mitigasi Tanpa Tambahan Hardware:*
     * **Multi-Queue Priority Scheduling:** Aktifkan mekanisme prioritas request pada vLLM. Assign request chatbot dengan `priority=0` (High Priority) dan request analitika dengan `priority=1` (Low Priority). Scheduler vLLM akan selalu mendahulukan alokasi slot blok memori dan eksekusi iterasi untuk request berprioritas tinggi.
     * **Chunked Prefill Tuning:** Terapkan batasan ketat `--max-num-batched-tokens 512`. Prompt panjang dari dokumen analitika akan dipotong menjadi potongan kecil 512 token per langkah iterasi, membuka celah waktu bagi eksekusi token decode chatbot secara konsisten pada setiap step.
     * **Rate Limiting di Tingkat Gateway:** Terapkan *Token-Bucket Rate Limiter* terpisah per tenant di level Envoy API Gateway. Batasi Divisi Analitika maksimal mengonsumsi 30% dari kapasitas konkurensi maksimum engine selama jam operasional kerja customer service.

---

## 16. Summary

Mengoperasikan sistem AI otonom dan LLM di lingkungan enterprise menuntut pemahaman mendalam atas batas-batas fisik akselerator komputasi. Kunci utama performa sistem terletak pada eliminasi inefisiensi memori:

1. **Pemisahan Karakteristik Beban:** Fase *Prefill* (compute-bound) dan fase *Decode* (memory-bandwidth bound) memiliki karakteristik perangkat keras yang berbeda. Arsitektur modern mengisolasi kedua fase ini atau menggunakan *Chunked Prefill* untuk meredam degradasi latensi interaktif (*TPOT*).
2. **Optimalisasi Memori melalui PagedAttention:** Inovasi paging virtual memori pada VRAM mengeliminasi fragmentasi alokasi *KV Cache*, menaikkan throughput sistem secara drastis, serta memfasilitasi teknik sampling mutakhir secara efisien.
3. **Observabilitas Berkelanjutan:** Pemantauan AI enterprise tidak boleh terbatas pada metrik server konvensional (CPU/RAM/Ping). Metrik spesifik domain inferensi—seperti *Time to First Token (TTFT)*, *Time Per Output Token (TPOT)*, saturasi *KV-Cache*, dan deteksi *semantic drift*—adalah indikator fundamental untuk menjaga stabilitas SLA operasional pada skala jutaan transaksi.