# Kurikulum Enterprise: Inference Engineering
## BAB 09: Observability, Profiling & Benchmarking
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang & Mengimplementasikan Arsitektur Telemetri End-to-End**: Membangun pipeline observabilitas terdistribusi untuk LLM inference engines (vLLM, TensorRT-LLM, Triton) menggunakan OpenTelemetry (OTel), Prometheus, Tempo, dan ClickHouse tanpa mengorbankan *throughput*.
- **Membedah & Mengukur Metrik Kritis GenAI**: Mengisolasi dan mengukur secara presisi metrik *Time-to-First-Token* (TTFT), *Inter-Token Latency* (ITL), *Time-Per-Output-Token* (TPOT), *KV-Cache Allocation/Eviction Rates*, serta utilisasi *High-Bandwidth Memory* (HBM).
- **Melakukan Low-Level GPU Profiling**: Menggunakan NVIDIA CUPTI, Nsight Systems (`nsys`), dan PyTorch Profiler untuk mendeteksi *kernel serialization*, *SM (Streaming Multiprocessor) underutilization*, dan *memory bandwidth bottleneck*.
- **Mengeksekusi Automated Saturation Benchmarking**: Menjalankan pengujian beban deterministik menggunakan GenAI-Perf dan Triton Perf Analyzer untuk memetakan kurva *concurrency vs. latency Pareto frontier* pada klaster GPU multi-node.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
- Pemahaman arsitektur inferensi LLM: Fase *Prefill* (Compute-bound) vs. *Decode* (Memory bandwidth-bound), mekanisme *PagedAttention*, dan *Continuous Batching*.
- Pengalaman menengah dengan Python asynchronous (`asyncio`), arsitektur web streaming (*Server-Sent Events* / gRPC streaming), dan framework PyTorch.
- Penguasaan konsep dasar observabilitas: Metrik (Meters, Gauges, Histograms), *Distributed Tracing* (Trace context, Spans, Propagation), dan Log Aggregation.
- Akses ke lingkungan Linux berbasis NVIDIA GPU (arsitektur Ampere, Hopper, atau lebih baru) dengan driver NVIDIA, CUDA Toolkit (>= 12.0), dan Docker/Container Toolkit terinstal.

---

### 3. Concept & Internal Architecture

Observabilitas pada sistem *inference engineering* memiliki karakteristik yang fundamental berbeda dari arsitektur *microservices* CRUD tradisional. Perbedaan ini bersumber dari sifat eksekusi model pada hardware akselerator:

```
+----------------------------------------------------------------------------------------------------+
|                                    INFERENCE PIPELINE ARCHITECTURE                                 |
+----------------------------------------------------------------------------------------------------+
  [ HTTP/gRPC Request ]
           │
           ▼
┌──────────────────────┐       OTel Trace Context Injected (W3C TraceContext)
│  API Gateway / Router│─────────────────────────────────────────────────────────────┐
└──────────┬───────────┘                                                             │
           │                                                                         ▼
           ▼                                                          ┌────────────────────────────┐
┌──────────────────────────────────────────────────────────────┐      │ OpenTelemetry Collector    │
│ Inference Engine (e.g., vLLM / Triton)                       │      │ (Batched OTLP Receiver)    │
│                                                              │      └──────────────┬─────────────┘
│  ┌────────────────────────────────────────────────────────┐  │                     │
│  │ Scheduler & Continuous Batching Loop                   │  │                     ├────────────────┐
│  │  - Prefill Queue (Compute-Bound, High GEMM Intensity)  │  │                     ▼                ▼
│  │  - Decode Queue (Memory-Bound, HBM Bandwidth Latency)  │  │            ┌─────────────────┐ ┌──────────┐
│  └───────────────┬────────────────────────────────────────┘  │            │ Prometheus/Mimir│ │Tempo/    │
│                  │                                           │            │ (Metrics Store) │ │Jaeger    │
│                  ▼                                           │            └─────────────────┘ └──────────┘
│  ┌────────────────────────────────────────────────────────┐  │                     ▲
│  │ PagedAttention Engine / KV Cache Manager               │  │                     │
│  │  - Logical/Physical Block Allocator                    │──┼─ GPU Cache Metrics ─┘
│  └───────────────┬────────────────────────────────────────┘  │  (Block usage, preemptions)
│                  │ CUDA Stream Submissions                   │
│                  ▼                                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ GPU Hardware Layer (NVIDIA Hopper / Ampere)            │  │
│  │  - Streaming Multiprocessors (SMs)                     │  │
│  │  - Tensor Cores & HBM3 Subsystem                       │  │
│  │  - Hardware Trace: CUPTI Events / CUDA Activity API    │──┼─ Low-Level Profiling Output
│  └────────────────────────────────────────────────────────┘  │  (nsys traces, PyTorch Kineto)
└──────────────────────────────────────────────────────────────┘
```

#### A. Anatomi Eksekusi LLM: Prefill vs. Decode Phase
1. **Fase Prefill (Prompt Processing)**:
   - Sifat: *Compute-bound*.
   - Karakteristik: Memproses seluruh token input secara paralel menggunakan operasi matrix-matrix multiplication (GEMM).
   - Metrik Utama: **TTFT (Time-to-First-Token)**. TTFT mencakup waktu antrean (*queue time*), tokenisasi prompt, transfer tensor ke GPU, dan eksekusi komputasi prefill.
2. **Fase Decode (Token Generation)**:
   - Sifat: *Memory bandwidth-bound*.
   - Karakteristik: Menghasilkan token satu per satu secara autoregresif menggunakan operasi matrix-vector multiplication (GEMV). Kinerja dibatasi oleh kecepatan membaca bobot model dan *KV Cache* dari HBM ke *SRAM / Register Files*.
   - Metrik Utama: **ITL (Inter-Token Latency)** atau **TPOT (Time-Per-Output-Token)**.

#### B. Mekanisme Internal Telemetri Tanpa Overhead
Mengambil metrik atau span tracing di dalam inner loop generasi token LLM berpotensi merusak *throughput* sistem (*observer effect*). Untuk meniadakan degradasi latensi:
- **Non-blocking Metrics Collection**: Metrik token diakumulasikan dalam memori shared atomic counters atau diekstraksi secara asinkron dari ring buffer scheduler inference engine.
- **CUDA Event Profiling vs. Wall-Clock**: Latensi GPU tidak boleh diukur menggunakan `time.time()` atau `std::chrono` karena CPU thread memicu *asynchronous launch* ke CUDA stream. Menggunakan `cudaDeviceSynchronize()` pada inner loop untuk mencatat waktu akan mengosongkan *pipeline queue* GPU (*GPU starvation*). Pengukuran latensi internal wajib menggunakan `cudaEventRecord` dan `cudaEventElapsedTime`.

---

### 4. Why & What

| Dimensi | APM Tradisional (CRUD Apps) | Inference Engineering Observability |
| :--- | :--- | :--- |
| **Satuan Eksekusi Utama** | HTTP Request-Response lifecycle tunggal. | Multi-phase stream: 1 Prompt $\to N$ Token output sequential steps. |
| **Bottleneck Hardware** | CPU Utilization, Database I/O, Network I/O. | GPU Memory Bandwidth (HBM), SM Occupancy, Tensor Core saturation, PCIe/NVLink throughput. |
| **Metrik Latensi Kritis** | P95/P99 HTTP Duration. | TTFT (Prompt processing) vs. ITL / TPOT (Generation cadence) vs. E2E Latency. |
| **Manajemen Memori** | Heap/Stack Allocation, Garbage Collection cycles. | KV Cache Block Allocation, PagedAttention fragmentation, GPU Out-Of-Memory (OOM) preemptions. |
| **Tracing Model** | Span per RPC/Database query. | Nested context: Request Span $\to$ Queue Span $\to$ Prefill Span $\to$ Continuous Decode Spans (Sampling-based). |

---

### 5. How (Workflow Detail)

Alur kerja implementasi observabilitas dan profiling di tingkat produksi terdiri dari 5 tahap berurutan:

1. **Instrumentation Layer**:
   - Engine mengintegrasikan hooks OpenTelemetry untuk mengekstrak W3C context dari request header.
   - Scheduler mengukur durasi antrean (*queuing delay*), batch scheduling overhead, dan latensi komputasi token.
2. **Metric Aggregation & Scraping**:
   - Exporter mengekspos metrik Prometheus pada endpoint `/metrics`.
   - Mengambil metrik vital: `vllm:num_requests_running`, `vllm:num_requests_waiting`, `vllm:gpu_cache_usage_factor`, `vllm:time_to_first_token_seconds`, `vllm:time_per_output_token_seconds`.
3. **Trace Propagation over Streaming**:
   - Token streaming (SSE/gRPC) menyematkan trace ID. Metadata tiap chunk membawa span status tanpa menghambat pengiriman payload karakter ke klien.
4. **Targeted Deep Profiling (Triggered/Ad-hoc)**:
   - Jika P99 ITL melampaui batas ambang (*SLA breach*), sistem mengaktifkan *PyTorch Profiler* atau *NVIDIA CUPTI continuous recording* selama interval waktu terbatas ($N$ batch) untuk menangkap eksekusi CUDA kernel tanpa membebani runtime secara permanen.
5. **Continuous Benchmarking & Verification**:
   - Menjalankan pipeline regresi otomatis menggunakan generator beban (*synthetic workload generator*) untuk mensimulasikan distribusi panjang token Pareto (misal: prompt panjang - output pendek, atau kebalikannya).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Telemetri Pit Stop Formula 1 vs. Spidometer Mobil Penumpang
Aplikasi web biasa mirip dengan mobil penumpang: Anda hanya butuh spidometer (HTTP latency) dan indikator bensin (CPU/RAM). 
Sistem *Inference Engineering* adalah mobil Formula 1: 
- TTFT adalah akselerasi 0-100 km/jam saat keluar dari tikungan tajam (Prefill/Compute burst).
- ITL adalah konsistensi kecepatan putaran mesin per milidetik di trek lurus (Memory bandwidth streaming).
- KV Cache adalah sisa kompon pada ban balap: begitu terdegradasi (*fragmentation/preemption*), mobil terpaksa masuk pit stop darurat (*swapping to CPU memory*), menyebabkan catatan waktu hancur seketika (*latency cliff*).

```
+--------------------------------------------------------------------------------------------------+
|                            END-TO-END TELEMETRY PIPELINE FLOW                                    |
+--------------------------------------------------------------------------------------------------+
Client Request
      │
      ▼
┌───────────────┐  Span: "http_request" [TraceId: 4bf92f3577b34da6a3ce929d0e0e4736]
│ API Gateway   │  Attributes: {model: "llama-3-70b", client_id: "fintech-core"}
└───────┬───────┘
        │ Context Propagation via gRPC metadata
        ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Inference Worker (Engine Scheduler)                                                    │
│                                                                                        │
│ ┌─ Child Span: "inference_queue" ──────────────────────────────────────────────────┐   │
│ │ Duration: 12ms | Attributes: {waiting_requests: 42, gpu_kv_usage: 0.82}          │   │
│ └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│ ┌─ Child Span: "prefill_phase" ────────────────────────────────────────────────────┐   │
│ │ Duration: 45ms | Attributes: {prompt_tokens: 1024, tps: 22755.5}                 │   │
│ │ CUDA Kernel: at::native::vectorized_elementwise_kernel (SM Occupancy: 94%)       │   │
│ └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│ ┌─ Child Span: "decode_phase" ─────────────────────────────────────────────────────┐   │
│ │ Duration: 580ms | Attributes: {output_tokens: 128, mean_itl_ms: 4.53}           │   │
│ │ Tokens Streamed: [Token 1, Token 2, ..., Token 128]                              │   │
│ │ PagedAttention Kernel: vllm::paged_attention_v2_kernel (HBM Bandwidth: 89%)     │   │
│ └──────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────────┬─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ Prometheus    │             │ Jaeger/Tempo  │             │ ClickHouse    │
│ (Histograms)  │             │ (Waterfalls)  │             │ (Token Logs)  │
└───────────────┘             └───────────────┘             └───────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Non-blocking Latency Profiler Menggunakan CUDA Events
Skrip tingkat rendah ini mendemonstrasikan cara mengukur waktu eksekusi kernel inferensi secara akurat pada level GPU stream tanpa memblokir thread Python runtime.

```python
# simple_gpu_profiler.py
import torch
import time

class CUDAPreciseTimer:
    """
    Mengukur durasi eksekusi GPU secara presisi tanpa memicu synchronous CPU stall
    sebelum eksekusi kernel benar-benar selesai dijadwalkan.
    """
    def __init__(self):
        self.start_event = torch.cuda.Event(enable_timing=True)
        self.end_event = torch.cuda.Event(enable_timing=True)

    def __enter__(self):
        self.start_event.record()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_event.record()

    def elapsed_time_ms(self) -> float:
        # Menunggu eksekusi event pada stream selesai sebelum membaca waktu
        self.end_event.synchronize()
        return self.start_event.elapsed_time(self.end_event)

# Validasi implementasi
if __name__ == "__main__":
    assert torch.cuda.is_available(), "CUDA environment wajib tersedia."
    
    # Alokasi tensor simulasi inferensi
    device = torch.device("cuda:0")
    weights = torch.randn(4096, 4096, device=device, dtype=torch.float16)
    inputs = torch.randn(128, 4096, device=device, dtype=torch.float16)

    timer = CUDAPreciseTimer()
    
    # Eksekusi fase compute
    with timer:
        outputs = torch.matmul(inputs, weights)

    gpu_latency = timer.elapsed_time_ms()
    print(f"[Engine Telemetry] Kernel Matmul Latency: {gpu_latency:.4f} ms")
```

#### B. Practical Example: Production-Grade Inference Telemetry Server
Implementasi asinkronik berbasis FastAPI yang mensimulasikan inferensi continuous batching dengan injeksi OpenTelemetry, metrik kustom Prometheus (TTFT, ITL, KV Cache), dan ekspor trace OTLP standar industri.

```python
# production_inference_telemetry.py
import asyncio
import time
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import prometheus_client
from prometheus_client import Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# 1. Konfigurasi OpenTelemetry SDK
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("enterprise-inference-engine", "1.0.0")

# 2. Definisi Metrik Prometheus Khusus Generative AI
TTFT_HISTOGRAM = Histogram(
    "llm_time_to_first_token_seconds",
    "Durasi pemrosesan prompt hingga token pertama dihasilkan (TTFT)",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)
ITL_HISTOGRAM = Histogram(
    "llm_inter_token_latency_seconds",
    "Latensi antar generasi token output (ITL/TPOT)",
    buckets=[0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.1]
)
KV_CACHE_USAGE = Gauge(
    "llm_kv_cache_usage_ratio",
    "Persentase alokasi PagedAttention KV Cache Blocks (0.0 - 1.0)"
)

app = FastAPI(title="Production Observability Inference Engine")

class MockContinuousEngine:
    """Simulasi mesin inferensi dengan latensi realistis Prefill & Decode."""
    async def generate_stream(self, prompt: str, max_tokens: int) -> AsyncGenerator[str, None]:
        # Simulasi alokasi KV Cache
        KV_CACHE_USAGE.set(0.74)
        
        # Fase Prefill (Compute-bound)
        prefill_delay = 0.045  # 45ms
        await asyncio.sleep(prefill_delay)
        yield "Initial"

        # Fase Decode (Memory bandwidth-bound)
        for i in range(max_tokens - 1):
            decode_delay = 0.012  # 12ms per token (~83 tokens/sec)
            await asyncio.sleep(decode_delay)
            yield f" token_{i+1}"
            
        KV_CACHE_USAGE.set(0.68)

engine = MockContinuousEngine()

@app.post("/v1/completions")
async def completions(request: Request):
    # Ekstraksi W3C TraceContext dari Header
    carrier = dict(request.headers)
    context = TraceContextTextMapPropagator().extract(carrier=carrier)

    async def token_generator_wrapper() -> AsyncGenerator[bytes, None]:
        with tracer.start_as_current_span("llm_request_execution", context=context) as req_span:
            start_time = time.perf_counter()
            first_token = True
            last_token_time = start_time
            total_tokens = 0

            with tracer.start_as_current_span("prefill_stage") as prefill_span:
                stream = engine.generate_stream(prompt="Enterprise Architecture Spec", max_tokens=10)
                
                async for token in stream:
                    current_time = time.perf_counter()
                    if first_token:
                        ttft = current_time - start_time
                        TTFT_HISTOGRAM.observe(ttft)
                        prefill_span.set_attribute("llm.ttft_seconds", ttft)
                        req_span.set_attribute("llm.time_to_first_token", ttft)
                        first_token = False
                    else:
                        itl = current_time - last_token_time
                        ITL_HISTOGRAM.observe(itl)

                    last_token_time = current_time
                    total_tokens += 1
                    
                    yield f"data: {token}\n\n".encode("utf-8")

            req_span.set_attribute("llm.total_output_tokens", total_tokens)
            req_span.set_attribute("llm.e2e_latency_seconds", time.perf_counter() - start_time)

    return StreamingResponse(token_generator_wrapper(), media_type="text/event-stream")

@app.get("/metrics")
async def get_metrics():
    """Endpoint scraping Prometheus standar."""
    return StreamingResponse(
        content=iter([generate_latest()]),
        media_type=CONTENT_TYPE_LATEST
    )

if __name__ == "__main__":
    import uvicorn
    # Jalankan server dengan HTTP/1.1 atau HTTP/2
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Platform**: Tier-1 Payment Processing Core (Asia Tenggara).
- **Workload**: Hybrid Architecture RAG + Autonomous Risk Summarization.
- **Skala**: 64x NVIDIA H100 (8 node HGX), memproses puncak 8.500 *concurrency request/detik*.
- **Framework**: vLLM didistribusikan menggunakan Ray cluster.

#### Masalah Produksi (The Incident)
Pada jam beban puncak (Flash Sale 11.11), latensi P99 sistem meledak dari **80 ms menjadi 2.400 ms**. Klien mengalami timeout bertingkat (*cascading failure*), namun metrik CPU utilitas normal (28%) dan GPU SM Utilization tampak stabil pada kisaran 70%.

#### Investigasi Diagnostik
1. **Analisis Distributed Tracing**:
   Visualisasi span di Jaeger mengonfirmasi bahwa TTFT melonjak drastis pada request yang datang saat ukuran prompt melebihi 4.000 token.
2. **Koleksi Metrik PagedAttention**:
   Prometheus mengekspos metrik `vllm:num_requests_waiting` melonjak tajam bersamaan dengan metrik `vllm:gpu_cache_usage_factor` mencapai plateau konstan **1.0 (100%)**.
3. **CUPTI Kernel Deep-Dive Profiling**:
   Tim SRE mengaktifkan *Nsight Systems remote profiling snapshot* selama 10 detik. Hasil trace menunjukkan:
   - Terjadi badai *preemption events*: Engine terpaksa membuang alokasi KV blocks request yang sedang decode ke CPU host memory (*swapping*) untuk memprioritaskan prefill request baru.
   - Terjadi *PCIe Bus saturation*: Jalur transfer host-to-device tercekik saat mengembalikan data swap KV cache ke GPU memory.

```
P99 Latency (Before vs. After Optimization)
========================================================================
Latency (ms)
 2500 ──┐                                   [CRITICAL FAILURE SPIKE]
 2000 ──┤                                            ┌──┐
 1500 ──┤                                            │  │
 1000 ──┤                                            │  │
  500 ──┤                                           ┌┘  └┐
  100 ──┴───────────────────────────────────────────┴────┴──────────────
        00:00   04:00   08:00   12:00   16:00   18:00   20:00   22:00

Optimized: Chunked Prefill Enabled + Dynamic Admission Control
 100 ──┬───────────────────────────────────────────────────────────────
   50 ──┴───────────────────────────────────────────────────────────────
```

#### Solusi Rekayasa
1. **Penerapan Chunked Prefill (`enable_chunked_prefill=True`)**:
   Memecah komputasi prompt panjang menjadi chunk-chunk kecil berukuran seragam (misal: 512 token) yang disisipkan di antara langkah-langkah decode batch reguler, menghilangkan preemption spike pada KV memory.
2. **Dynamic Backpressure Berbasis KV Cache Usage**:
   API Gateway menolak atau mengantrekan request baru di level edge jika `vllm:gpu_cache_usage_factor > 0.90`, mencegah kehabisan blok HBM di level hardware.
3. **Hasil**:
   - P99 latensi stabil turun kembali ke **72 ms** di bawah beban puncak maksimum.
   - GPU Memory Swapping turun hingga 0%.

---

### 9. Trade-offs

| Parameter Desain | Pilihan A | Pilihan B | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Trace Sampling Rate** | **100% In-line Tracing** | **Tail-based Sampling (e.g., 1% Success, 100% Errors/P99)** | Tracing 100% menangkap setiap degradasi latensi tetapi membebani I/O jaringan sebesar ~5-10% dari throughput inference engine dan menghasilkan storage cost ClickHouse/Tempo yang masif. Tail-based sampling adalah standar de facto enterprise. |
| **Profil Kinerja GPU** | **NVIDIA CUPTI / Nsys Continuous** | **Lightweight Prometheus Scraping** | CUPTI / Nsys memberikan visibilitas level instruksi assembly SASS dan memory pipeline, tetapi menimbulkan penalti performa 15% - 35% pada runtime throughput. Wajib diisolasi hanya untuk canary pod atau sesi profiling aktif. |
| **Granularitas Tracing Token** | **Per-Token Span Generation** | **Request-Level Aggregate Metrics** | Membuat OpenTelemetry Span untuk setiap token individual pada stream output menghasilkan jutaan span per detik yang membebani collector. Pendekatan tepat: catat agregat distribusi ITL via histogram lokal, buat span hanya pada boundary request & prefill. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menjalankan Host-Device Synchronization di Telemetry Hooks
*Pola Anti-pattern:*
```python
# ANTI-PATTERN: Memanggil cudaDeviceSynchronize di dalam request hook
start = time.time()
output = model.forward(batch)
torch.cuda.synchronize() # MEMBEBANI SYSTEM: Menghentikan seluruh parallel CUDA stream!
latency = time.time() - start
PROMETHEUS_HISTOGRAM.observe(latency)
```
*Solusi Perbaikan:*
Gunakan asynchronous completion callbacks atau rekam event non-blocking CUDA (`torch.cuda.Event(enable_timing=True)`) yang dievaluasi di akhir batch pipeline tanpa menghentikan worker scheduler.

#### Kesalahan 2: Cardinality Explosion pada Prometheus Metrics
*Pola Anti-pattern:*
Memasukkan atribut dinamis seperti `prompt_id`, `session_uuid`, atau `user_id` ke dalam label metrik:
```python
# ANTI-PATTERN: Ledakan Cardinality di Database Time-Series
TTFT_HISTOGRAM.labels(user_id=request.user_id, prompt=request.prompt[:10]).observe(ttft)
```
*Solusi Perbaikan:*
Batasi dimensi Prometheus hanya pada label bervariasi rendah: `model_name`, `quantization_type`, `tensor_parallel_size`. Pindahkan metadata spesifik pengguna ke OpenTelemetry Span Attributes atau ClickHouse Structured Logs.

#### Kesalahan 3: Mengabaikan SSE Stream Disconnect Handling
Jika klien membatalkan koneksi HTTP di tengah-tengah streaming generasi token, inference server yang tidak terinstrumentasi akan tetap menjalankan komputasi decode hingga selesai (*ghost generation*).
*Solusi Perbaikan:*
Dengarkan sinyal `request.is_disconnected()` pada asynchronous loop dan kirim sinyal abort ke scheduler engine untuk melepaskan KV blocks.

---

### 11. Best Practices (Production Checklist)

- [ ] **Instrumentasi Metrik Wajib**: Pastikan sistem mengekspos metrik Golden Signal GenAI:
  - `TTFT` (Histogram dengan bucket resolusi tinggi di bawah 100ms).
  - `ITL / TPOT` (Histogram terpisah dari E2E latency).
  - `KV Cache Utilization Factor` (Gauge, alert pada > 0.85).
  - `Running vs Waiting Requests` (Gauge antrean scheduler).
- [ ] **Context Propagation Standard**: Terapkan standar W3C TraceContext (`traceparent` header) melewati reverse proxy, gateway, dan distributed inference worker nodes.
- [ ] **Trace Sampling Strategy**: Terapkan *tail-based sampling* di OpenTelemetry Collector: Simpan 100% trace untuk HTTP status >= 500 atau TTFT > 500ms; simpan 1% trace untuk transaksi normal.
- [ ] **Non-Intrusive Profiling Automation**: Pasang daemon profiling terjadwal yang mengekstraksi snapshot *PyTorch Memory Timeline* secara periodik tanpa mematikan proses server.
- [ ] **Alerting Thresholds**:
  - P99 TTFT > target SLA (misal: 200ms) selama 3 menit berurutan.
  - Alokasi KV Cache mencapai 95% selama lebih dari 30 detik (indikasi degradasi kapasitas batching).
  - Preemption Rate > 0 requests/sec.

---

### 12. Hands-on Practice

Buat direktori latihan kerja di: `hands-on/m02/`

#### Struktur File:
```
hands-on/m02/
├── docker-compose.yml
├── prometheus.yml
├── server.py
├── benchmark_client.py
└── requirements.txt
```

#### File 1: `requirements.txt`
```text
fastapi>=0.110.0
uvicorn>=0.28.0
prometheus-client>=0.20.0
opentelemetry-api>=1.24.0
opentelemetry-sdk>=1.24.0
httpx>=0.27.0
numpy>=1.26.0
```

#### File 2: `docker-compose.yml`
```yaml
version: '3.8'
services:
  inference-node:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1

  prometheus:
    image: prom/prometheus:v2.51.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

#### File 3: `prometheus.yml`
```yaml
global:
  scrape_interval: 2s

scrape_configs:
  - job_name: 'llm-inference'
    static_configs:
      - targets: ['inference-node:8000']
```

#### File 4: `server.py`
Salin kode dari **Seksi 7.B (Production-Grade Inference Telemetry Server)** ke dalam file ini.

#### File 5: `benchmark_client.py`
Eksekutor beban concurrent untuk menghasilkan kurva benchmark metrik TTFT dan ITL:

```python
# hands-on/m02/benchmark_client.py
import asyncio
import time
import httpx
import numpy as np

TARGET_URL = "http://localhost:8000/v1/completions"
CONCURRENCY = 10
TOTAL_REQUESTS = 50

async def send_inference_request(client: httpx.AsyncClient, req_id: int):
    headers = {"traceparent": f"00-4bf92f3577b34da6a3ce929d0e0e4736-000000000000000{req_id:02x}-01"}
    t_start = time.perf_counter()
    ttft = None
    tokens_received = 0

    try:
        async with client.stream("POST", TARGET_URL, headers=headers, timeout=30.0) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    if ttft is None:
                        ttft = time.perf_counter() - t_start
                    tokens_received += 1
        
        total_time = time.perf_counter() - t_start
        itl = (total_time - ttft) / (tokens_received - 1) if tokens_received > 1 else 0
        return {"ttft": ttft, "itl": itl, "tokens": tokens_received, "duration": total_time}
    except Exception as e:
        print(f"Request {req_id} Failed: {e}")
        return None

async def main():
    print(f"Menjalankan benchmark dengan concurrency={CONCURRENCY}, total={TOTAL_REQUESTS}...")
    limits = httpx.Limits(max_keepalive_connections=CONCURRENCY, max_connections=CONCURRENCY * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = []
        for i in range(TOTAL_REQUESTS):
            tasks.append(send_inference_request(client, i))
            if len(tasks) >= CONCURRENCY:
                pass
        
        results = await asyncio.gather(*tasks)
        
    valid_results = [r for r in results if r is not None]
    ttfts = [r["ttft"] * 1000 for r in valid_results]
    itls = [r["itl"] * 1000 for r in valid_results]

    print("\n--- HASIL BENCHMARK TELEMETRI ---")
    print(f"Total Requests Berhasil: {len(valid_results)}/{TOTAL_REQUESTS}")
    print(f"TTFT (ms) -> P50: {np.percentile(ttfts, 50):.2f} | P90: {np.percentile(ttfts, 90):.2f} | P99: {np.percentile(ttfts, 99):.2f}")
    print(f"ITL  (ms) -> P50: {np.percentile(itls, 50):.2f} | P90: {np.percentile(itls, 90):.2f} | P99: {np.percentile(itls, 99):.2f}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 13. Exercise

#### Tingkat: Easy
Tambahkan counter metrik kustom di Prometheus (`llm_tokens_generated_total`) pada file `server.py` yang melacak total token yang dihasilkan, dengan pemisahan label tipe token: `type="prefill"` vs `type="decode"`.
- *Verifikasi*: Jalankan beban via `benchmark_client.py` dan periksa endpoint `/metrics` untuk memastikan nilai counter bertambah secara akurat.

#### Tingkat: Medium
Modifikasi endpoint inferensi untuk menyematkan metadata kinerja langsung ke HTTP chunk respons terakhir (trailer metadata SSE):
- Kirim event SSE terakhir bertipe `event: metrics` yang berisi JSON payload: `{"ttft_ms": ..., "mean_itl_ms": ..., "total_tokens": ...}`.
- Tangkap event trailer ini pada `benchmark_client.py` dan validasi apakah data trailer klien cocok dengan metrik internal server.

#### Tingkat: Hard
Tulis skrip Python kustom menggunakan `torch.profiler` (`Kineto`) yang secara terprogram mengaktifkan trace GPU profiling hanya saat terdeteksi *anomaly latency spike* (misal: ada request dengan TTFT > 100ms).
- Simpan memory timeline dan kernel activity trace ke dalam format Chrome trace JSON (`/tmp/trace_<timestamp>.json`).
- Pastikan profil hanya aktif selama 1 siklus batch abnormal dan langsung nonaktif secara otomatis guna mencegah penurunan performa beruntun.

---

### 14. Challenge

#### Skenario: Arsitektur Zero-Overhead Live GPU Profiling Engine
Anda ditugaskan merancang subsistem observabilitas untuk inference cluster berskala 128 GPU H100 yang melayani model Llama-3-70B FP8.

#### Spesifikasi Tantangan:
1. **Target**: Deteksi secara real-time degradasi performa yang disebabkan oleh *GPU Memory Bandwidth Saturation* dan *CUDA Kernel Serialization*.
2. **Batasan Keras**:
   - Total overhead telemetri terhadap throughput server tidak boleh melebihi **1.5%**.
   - Tidak diizinkan melakukan sinkronisasi thread CPU-GPU secara blocking (`torch.cuda.synchronize()` dilarang keras).
   - Metrik trace harus mampu mengidentifikasi *outlier worker* dalam konfigurasi Tensor Parallelism (TP=8) jika salah satu GPU mengalami degradasi frekuensi clock (Thermal Throttling).
3. **Luaran yang Diuji**:
   - Skema arsitektur data path pengumpulan trace & metrik.
   - Algoritma isolasi GPU straggler (worker paling lambat yang menahan ring-allreduce pada tensor parallelism).
   - Strategi ekspor trace volume tinggi tanpa memicu disk bottleneck lokal pada cluster nodes.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)
1. **Mengapa metrik latensi konvensional (Total Request Duration) tidak cukup untuk mengevaluasi kinerja inferensi LLM?**
   - *Jawaban*: Karena Total Duration mengaburkan perbedaan mendasar antara komputasi intensif fase *Prefill* (TTFT) dan pemrosesan sekuensial fase *Decode* yang dibatasi oleh bandwidth memori (ITL/TPOT).
2. **Apa yang diukur oleh metrik Inter-Token Latency (ITL)?**
   - *Jawaban*: Waktu yang dibutuhkan model untuk menghasilkan satu token baru setelah token pertama terbit, yang merepresentasikan kecepatan streaming aktual yang dirasakan pengguna.
3. **Fase inferensi LLM mana yang umumnya berkarakteristik Memory Bandwidth-Bound?**
   - *Jawaban*: Fase Decode (Autoregressive generation), di mana setiap token baru membutuhkan transfer seluruh model weight dan KV cache dari HBM ke cache chip prosesor.
4. **Apa dampak buruk dari penambahan label bervariasi unik (seperti Request ID) pada metrik Prometheus?**
   - *Jawaban*: Menyebabkan ledakan kardinalitas (*cardinality explosion*), menghabiskan RAM time-series database dan memperlambat evaluasi query secara drastis.
5. **Apa fungsi utama dari implementasi PagedAttention pada Inference Engine?**
   - *Jawaban*: Mengurangi fragmentasi memori KV cache dengan mengalokasikannya ke dalam blok-blok virtual non-kontigu, mirip paging virtual memory sistem operasi.

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. **Mengapa memanggil `torch.cuda.synchronize()` di dalam loop telemetri produksi dianggap sebagai anti-pattern fatal?**
   - *Jawaban*: Perintah tersebut memaksa CPU menunggu hingga seluruh instruksi GPU di stream selesai, mengosongkan antrean eksekusi GPU (*pipeline bubble*), menghentikan pemrosesan paralel batch lain, dan meruntuhkan throughput inferensi.
7. **Bagaimana cara melacak keterkaitan antara prompt prefill dengan ratusan token output streaming dalam satu distributed trace?**
   - *Jawaban*: Melalui context propagation: Buat root Span saat request tiba, turunkan child span untuk tahap Prefill, dan satukan generasi token decode di bawah rentang parent span yang sama dengan atribut ringkasan (tanpa membuat jutaan individual token spans).
8. **Apa arti praktis jika rasio metrik `gpu_cache_usage_factor` bernilai 0.99 sementara `num_requests_waiting` terus bertambah?**
   - *Jawaban*: Kapasitas KV Cache pada GPU telah jenuh. Engine tidak memiliki ruang memori untuk menampung context batch baru, sehingga request baru tertahan di antrean dan risiko request preemption/swapping sangat tinggi.
9. **Kapan sebaiknya teknisi memilih PyTorch Profiler dibanding NVIDIA Nsight Systems (`nsys`)?**
   - *Jawaban*: PyTorch Profiler ideal untuk debugging level framework aplikasi (korelasi modul operator PyTorch dengan CUDA kernel). Nsight Systems dipilih untuk analisis bare-metal level sistem operasi, runtime driver, hardware NVLink interconnect, dan deep GPU kernel profiling.
10. **Bagaimana mekanisme W3C TraceContext dipropagasi pada protokol komunikasi berbasis Server-Sent Events (SSE)?**
    - *Jawaban*: TraceContext diinjeksikan melalui HTTP Request Header standar (`traceparent`) saat koneksi streaming pertama kali diinisiasi oleh klien.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: *Sistem Anda menunjukkan TTFT P99 melonjak tinggi saat jam sibuk, tetapi metrik ITL stabil dan konsisten rendah. Identifikasi letak bottleneck dan tindakan mitigasi yang harus diambil.*
    - *Solusi Analitis*: Bottleneck berada pada *Queuing Delay* di scheduler atau komputasi *Prefill*. Akar masalah: Prompt besar masuk bersamaan menghabiskan kapasitas GEMM core GPU, atau request mengantre karena keterbatasan slot alokasi batch. Mitigasi: Terapkan *Chunked Prefill*, tambah alokasi node tensor parallel, atau pasang reverse proxy rate limiter untuk membatasi concurrency prompt panjang.
12. **Skenario 2**: *Pada klaster multi-GPU Tensor Parallelism (TP=4), terjadi lonjakan ITL secara periodik. Telemetri CPU dan GPU utilitas tampak seragam di angka 60%, namun P99 tetap terganggu. Bagaimana Anda mengisolasi masalah ini menggunakan telemetri kernel?*
    - *Solusi Analitis*: Jalankan trace ringkas dengan filter event `ncclKernel_AllReduce`. Jika durasi AllReduce bervariasi tinggi di antara GPU ranks, identifikasi kecepatan clock tiap engine melalui metrik driver (`nvidia-smi --query-gpu=clocks.current.sm`). Jika salah satu rank mengalami *thermal throttling*, node tersebut akan menjadi straggler yang memperlambat 3 GPU lainnya pada setiap barrier pertukaran token.
13. **Skenario 3**: *OpenTelemetry Collector Anda mengalami OOM (Out-of-Memory) crash berulang kali saat traffic streaming inferensi mencapai 10.000 tokens/sec. Tindakan arsitektur apa yang wajib dieksekusi?*
    - *Solusi Analitis*: Hentikan pembuatan span per-token di level inferensi engine. Alihkan perekaman token ke agregasi in-memory metrics lokal (Histogram ITL), aktifkan *tail-based sampling processor* pada OTel Collector untuk membuang 99% trace transaksi sehat, dan konfigurasikan `batch processor` dengan `send_batch_max_size` serta `timeout` yang agresif.

---

### 16. Summary

- **Dualitas Kinerja Generative AI**: Evaluasi inferensi LLM menuntut pemisahan mutlak antara **TTFT** (karakteristik komputasi/prefill) dan **ITL/TPOT** (karakteristik bandwidth memori/decode). Menggabungkan keduanya ke dalam durasi tunggal adalah kesalahan fatal.
- **Prinsip Non-blocking Telemetri**: Hardware GPU bekerja secara asinkron terhadap CPU runtime. Telemetri tingkat produksi wajib mengandalkan CUDA Events dan asinkronik exporter untuk mencegah GPU starvation.
- **Kondisi Kritis KV Cache**: Manajemen memori pada inference engine (PagedAttention) merupakan indikator kesehatan utama sistem. Saturasi blok cache memicu badai swapping memori yang merusak kestabilan latensi tail P99.
- **Observabilitas Proporsional**: Implementasikan instrumentasi metrik yang berfokus pada Golden Signals GenAI, dan gunakan profiling mendalam (CUPTI / Nsys) secara selektif guna menjaga stabilitas dan efisiensi throughput sistem produksi.