# Bab 09: Observability, Profiling, & Benchmarking
## Module 01: High-Fidelity Inference Telemetry, Distributed Tracing, & Core LLM Serving Metrics

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Telemetri Zero-Overhead:** Mengonfigurasi pipeline observabilitas berbasis Prometheus dan OpenTelemetry yang mampu menangani throughput inferensi tinggi tanpa mendegradasi *Inter-Token Latency* (ITL).
- **Mengisolasi dan Mengukur Metrik Kritis LLM Serving:** Menghitung secara presisi metrik *Time to First Token* (TTFT), *Time Per Output Token* (TPOT / ITL), *Generation Throughput* (tokens/sec), dan *KV Cache Saturation* secara real-time.
- **Menginstrumentasikan Distributed Tracing Lintas-Komponen:** Mengimplementasikan propagasi konteks OpenTelemetry dari API Gateway, melewati Continuous Batching Scheduler, hingga eksekusi kernel inferensi GPU.
- **Menganalisis Performa Berdasarkan Karakteristik Fase Model:** Membedakan degradasi performa pada fase *Prefill* (compute-bound) versus fase *Decode* (memory-bandwidth-bound) menggunakan data instrumentasi kuantitatif.

---

### 2. Concept Overview

Mengamati sistem inferensi model bahasa skala besar (LLM Serving) memiliki karakteristik yang secara fundamental berbeda dari sistem *stateless web service* konvensional.

```
Web Service Tradisional:
[ Request ] ──────> [ Compute: O(N) ] ──────> [ Response Tunggal ]
Metrik Kunci: Request Latency, Error Rate, QPS

LLM Inference Serving:
                    ┌── Prefill Phase (Compute-Bound) ──┐
[ Prompt Tokens ] ─>│ Parallel GEMM: O(Prompt_Len)      │─> [ First Token (TTFT) ]
                    └── Decode Phase (Memory-Bound) ────┘
                    │ Iterative Autoregressive: O(1)    │─> [ Token 1 (ITL) ]
                    │ Iterative Autoregressive: O(1)    │─> [ Token 2 (ITL) ]
                    │ ...                               │─> ...
                    │ Iterative Autoregressive: O(1)    │─> [ Token N (EOS) ]
Metrik Kunci: TTFT, ITL/TPOT, KV-Cache Saturation, Preemption Rate
```

#### Pergeseran Paradigma Observabilitas

1. **Dua Fase Komputasi yang Berbeda:**
   - **Prefill (Context) Phase:** Memproses seluruh prompt input secara paralel. Fase ini sangat bergantung pada kapabilitas *Compute Core* (Tensor Cores / FLOPs bound). Metrik determinannya adalah **Time to First Token (TTFT)**.
   - **Decode (Generation) Phase:** Menghasilkan token berikutnya secara autoregresif, satu per satu. Setiap langkah eksekusi melibatkan pembacaan seluruh bobot model dan *Key-Value (KV) Cache* dari VRAM ke SRAM, sehingga fase ini bersifat *Memory-Bandwidth Bound*. Metrik determinannya adalah **Inter-Token Latency (ITL)** atau **Time Per Output Token (TPOT)**.

2. **Dinamika Dynamic Continuous Batching:**
   Scheduler mesin inferensi modern (seperti vLLM atau TensorRT-LLM) terus menggabungkan request yang sedang berada pada fase prefill dan decode ke dalam satu *iteration batch*. Hal ini menyebabkan *tail latency* (P99) mudah terdistorsi jika request baru dengan prompt panjang masuk saat request lain sedang dalam proses decoding.

3. **Status Stateful pada Memori GPU (KV Cache):**
   Kapasitas inferensi dibatasi secara ketat oleh ketersediaan VRAM untuk alokasi blok KV Cache. Observabilitas harus mampu mendeteksi *KV Cache Exhaustion*, *Request Eviction*, dan *Preemption Event* sebelum terjadi degradasi performa sistem.

---

### 3. Why It Matters

Dalam implementasi skala *enterprise*:
- **Pelanggaran SLA Streaming:** Latensi rata-rata HTTP tidak mampu menangkap fenomena "stuttering" (token macet di tengah streaming). Pengguna manusia sangat sensitif terhadap lonjakan ITL di atas 50-80 ms, meskipun nilai rata-rata keseluruhan sesi tampak normal.
- **Krisis Kapasitas Tersembunyi (KV Cache Starvation):** Tanpa telemetri yang memadai pada level memori manajer model, sistem akan melakukan *preemption* (membuang KV Cache request aktif dan mengulang kalkulasi prefill dari awal), yang dapat memicu lonjakan eksponensial pada latensi P99 dan P99.9.
- **Biaya Operasional GPU:** Mengetahui *Throughput vs. Latency Pareto Frontier* memungkinkan tim platform melakukan kalkulasi ukuran autoscaling cluster secara presisi. Ketidakakuratan metrik menyebabkan alokasi GPU berlebih (*over-provisioning*) yang menghabiskan anggaran infrastruktur bernilai puluhan ribu dolar per bulan.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur observabilitas dirancang menggunakan mekanisme *non-blocking telemetry extraction* berbasis asinkron agar tidak membebani siklus inferensi utama.

```
+---------------------------------------------------------------------------------------+
|                                    INFERENCE NODE                                     |
|                                                                                       |
|  [ Ingress Traffic ]                                                                  |
|          │                                                                            |
|          ▼                                                                            |
|  +─────────────────────────────────────────────────────────────────────────────────+  |
|  | Reverse Proxy / API Gateway (FastAPI / Envoy)                                   |  |
|  | - Context Extraction (W3C TraceContext)                                         |  |
|  | - Ingress Metrics (Active Connections, Ingress Request Rate)                    |  |
|  +──────────────────────────────────────┬──────────────────────────────────────────+  |
|                                         │ Trace Propagation (SpanContext)             |
|                                         ▼                                             |
|  +─────────────────────────────────────────────────────────────────────────────────+  |
|  | Inference Serving Engine (vLLM / Custom Orchestrator)                           |  |
|  |                                                                                 |  |
|  |  +-----------------------------+       +-------------------------------------+  |  |
|  |  | Continuous Batch Scheduler  |       | Telemetry Collector Bridge          |  |  |
|  |  | - Request Queue Monitoring  |       | (Low-overhead Async Ring Buffer)    |  |  |
|  |  | - Batch Composition Control │       |                                     |  |  |
|  |  +──────────────┬──────────────+       | - Prefill Tracker                   |  |  |
|  |                 │                      | - Token Stream Tick Instrumenter    |  |  |
|  |                 ▼                      | - Memory/Cache State Reader         |  |  |
|  |  +─────────────────────────────+       +──────────────────┬──────────────────+  |  |
|  |  | Worker Engine (CUDA Execution|                         │                     |  |
|  |  | - Forward Pass Execution     |                         │ Thread-safe Queue   |  |
|  |  | - KV Cache Paged Allocator   |                         ▼                     |  |
|  |  +─────────────────────────────+       +─────────────────────────────────────+  |  |
|  |                                        | Prometheus Metrics Registry         |  |  |
|  |                                        | (Histograms, Gauges, Counters)      |  |  |
|  +────────────────────────────────────────+──────────────────┬──────────────────+  |  |
|                                                              │                     |  |
+──────────────────────────────────────────────────────────────┼─────────────────────+  |
                                                               │ /metrics scrape        |
                                                               │ OTLP gRPC Export       |
                                                               ▼                        |
                                            +──────────────────────────────────────+    |
                                            | Observability Backend Pipeline       |    |
                                            | - OpenTelemetry Collector            |    |
                                            | - Prometheus Time-Series DB          |    |
                                            | - Jaeger / Tempo Tracing Engine      |    |
                                            | - Grafana Executive Dashboard        |    |
                                            +──────────────────────────────────────+    |
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Metrik Standar Industri untuk LLM Serving

| Metrik | Satuan | Deskripsi Algoritmik | Karakteristik Bottleneck |
| :--- | :--- | :--- | :--- |
| **TTFT (Time to First Token)** | Milliseconds | Waktu dari kedatangan request hingga token output index $0$ dipancarkan. Mencakup waktu antrean (*queue time*) dan *prefill pass*. | GPU Compute Bound, Latensi Penjadwalan |
| **ITL (Inter-Token Latency)** | Milliseconds | Delta waktu antara pemancaran token $k$ dan token $k+1$: $\Delta t = t_{k+1} - t_k$. | GPU Memory Bandwidth Bound |
| **TPOT (Time Per Output Token)** | Milliseconds | Rata-rata waktu per token keluaran: $\frac{\text{Total Generation Time} - \text{TTFT}}{\text{Total Output Tokens} - 1}$. | GPU Memory Bandwidth Bound |
| **Normalized Latency** | ms/token | $\frac{\text{Total End-to-End Latency}}{\text{Total Output Tokens}}$. Menghilangkan bias panjang generasi respons. | Efisiensi Pipeline Komputasi |
| **KV Cache Saturation** | Percentage | $\frac{\text{Used KV Cache Blocks}}{\text{Total Available Blocks}} \times 100\%$. | VRAM Capacity Bound |
| **Preemption Rate** | Ops/Sec | Frekuensi pelepasan paksa KV-Cache aktif akibat VRAM habis saat batch membesar. | VRAM Capacity vs Batch Size Miss |

#### Anatomi Histogram Bucketing yang Tepat

Histogram konvensional dengan *exponential scaling* default pada Web Services gagal menangani LLM Serving:
- Bucket default Prometheus (`[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]`) tidak memiliki resolusi yang cukup untuk ITL (yang berada pada rentang 15 ms hingga 100 ms) sekaligus gagal menangani TTFT panjang (bisa mencapai 3000 ms - 15000 ms pada konteks dokumen masif).
- **Rekomendasi Skala Bucket:**
  - `llm_time_to_first_token_seconds`: `[0.05, 0.1, 0.2, 0.4, 0.8, 1.2, 1.6, 2.0, 3.0, 5.0, 8.0, 15.0, 30.0]`
  - `llm_inter_token_latency_seconds`: `[0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.050, 0.075, 0.100, 0.150, 0.250]`

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Inference Telemetry Manager* berbasis Python modern yang menggabungkan Prometheus dan OpenTelemetry Semantic Conventions v1.27+ untuk sistem streaming LLM.

```python
"""
telemetry_engine.py
Komponen instrumentasi observabilitas produksi untuk inferensi LLM streaming.
Mendukung OpenTelemetry tracing kontekstual dan ekspor metrik Prometheus.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Final, List, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, StatusCode, Tracer
from prometheus_client import Counter, Gauge, Histogram

# ============================================================================
# METRIC DEFINITIONS (Prometheus)
# ============================================================================

HISTOGRAM_TTFT_BUCKETS: Final[List[float]] = [
    0.025, 0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0, 5.0, 10.0, 20.0
]
HISTOGRAM_ITL_BUCKETS: Final[List[float]] = [
    0.008, 0.012, 0.016, 0.020, 0.025, 0.030, 0.040, 0.050, 0.075, 0.100, 0.200
]

METRIC_TTFT = Histogram(
    name="llm_time_to_first_token_seconds",
    documentation="Latensi dari kedatangan request hingga token pertama digenerate (TTFT).",
    labelnames=["model_id", "status"],
    buckets=HISTOGRAM_TTFT_BUCKETS,
)

METRIC_ITL = Histogram(
    name="llm_inter_token_latency_seconds",
    documentation="Latensi antar-token berurutan selama fase decoding (ITL/TPOT).",
    labelnames=["model_id"],
    buckets=HISTOGRAM_ITL_BUCKETS,
)

METRIC_REQUEST_DURATION = Histogram(
    name="llm_request_duration_seconds",
    documentation="Total waktu siklus request inferensi streaming secara utuh.",
    labelnames=["model_id", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

METRIC_TOKENS_GENERATED = Counter(
    name="llm_generated_tokens_total",
    documentation="Jumlah kumulatif token keluaran yang berhasil dikirim ke klien.",
    labelnames=["model_id"],
)

METRIC_ACTIVE_REQUESTS = Gauge(
    name="llm_active_requests_count",
    documentation="Jumlah koneksi streaming inferensi yang sedang aktif diproses.",
    labelnames=["model_id"],
)

METRIC_KV_CACHE_USAGE_RATIO = Gauge(
    name="llm_kv_cache_usage_ratio",
    documentation="Rasio pemanfaatan alokasi blok KV-Cache saat ini (0.0 - 1.0).",
    labelnames=["model_id"],
)


@dataclass(frozen=True)
class StreamMetricsSummary:
    """Snapshot kalkulasi statistik pasca-inferensi."""
    ttft_seconds: float
    total_tokens: int
    duration_seconds: float
    avg_itl_seconds: float
    throughput_tokens_per_sec: float


class InferenceTelemetryContext:
    """
    Manajer konteks per-request untuk tracking telemetri streaming tingkat granular.
    Thread-safe & fully compatible dengan event-loop asynchronous asyncio.
    """

    def __init__(self, model_id: str, tracer: Optional[Tracer] = None) -> None:
        self.model_id: Final[str] = model_id
        self.tracer: Tracer = tracer or trace.get_tracer("llm.inference.engine")
        
        self._start_time: float = 0.0
        self._first_token_time: Optional[float] = None
        self._last_token_time: float = 0.0
        self._token_count: int = 0
        self._span: Optional[Span] = None

    async def __aenter__(self) -> "InferenceTelemetryContext":
        self._start_time = time.perf_counter()
        self._last_token_time = self._start_time
        METRIC_ACTIVE_REQUESTS.labels(model_id=self.model_id).inc()

        self._span = self.tracer.start_span(
            name=f"llm_generate::{self.model_id}",
            attributes={
                "llm.model_name": self.model_id,
                "llm.request.type": "streaming",
            },
        )
        return self

    def record_token_yield(self) -> None:
        """
        Wajib dipanggil tepat sebelum token di-yield ke event loop jaringan.
        Menghitung TTFT pada pemanggilan pertama, dan ITL pada pemanggilan berikutnya.
        """
        now = time.perf_counter()
        self._token_count += 1

        if self._token_count == 1:
            # TTFT Evaluation
            self._first_token_time = now
            ttft = now - self._start_time
            METRIC_TTFT.labels(model_id=self.model_id, status="success").observe(ttft)
            
            if self._span and self._span.is_recording():
                self._span.set_attribute("llm.metrics.ttft_ms", ttft * 1000.0)
                self._span.add_event("first_token_generated", {"timestamp": now})
        else:
            # ITL Evaluation
            itl = now - self._last_token_time
            METRIC_ITL.labels(model_id=self.model_id).observe(itl)

        self._last_token_time = now
        METRIC_TOKENS_GENERATED.labels(model_id=self.model_id).inc()

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        now = time.perf_counter()
        duration = now - self._start_time
        status = "error" if exc_type is not None else "success"

        try:
            METRIC_REQUEST_DURATION.labels(
                model_id=self.model_id, status=status
            ).observe(duration)

            if self._span and self._span.is_recording():
                self._span.set_attribute("llm.response.completion_tokens", self._token_count)
                self._span.set_attribute("llm.metrics.request_duration_ms", duration * 1000.0)
                
                if exc_val:
                    self._span.record_exception(exc_val)
                    self._span.set_status(StatusCode.ERROR, description=str(exc_val))
                else:
                    self._span.set_status(StatusCode.OK)

                self._span.end()
        finally:
            METRIC_ACTIVE_REQUESTS.labels(model_id=self.model_id).dec()

    def summarize(self) -> StreamMetricsSummary:
        """Menghasilkan kalkulasi metrik ringkas setelah stream selesai."""
        if self._token_count == 0 or self._first_token_time is None:
            return StreamMetricsSummary(
                ttft_seconds=0.0,
                total_tokens=0,
                duration_seconds=0.0,
                avg_itl_seconds=0.0,
                throughput_tokens_per_sec=0.0,
            )

        duration = self._last_token_time - self._start_time
        ttft = self._first_token_time - self._start_time
        
        decode_duration = self._last_token_time - self._first_token_time
        decode_tokens = self._token_count - 1
        avg_itl = (decode_duration / decode_tokens) if decode_tokens > 0 else 0.0
        throughput = (self._token_count / duration) if duration > 0 else 0.0

        return StreamMetricsSummary(
            ttft_seconds=ttft,
            total_tokens=self._token_count,
            duration_seconds=duration,
            avg_itl_seconds=avg_itl,
            throughput_tokens_per_sec=throughput,
        )


# ============================================================================
# USAGE DEMONSTRATION & ENGINE INSTRUMENTATION WRAPPER
# ============================================================================

async def mocked_low_level_llm_generator(
    prompt: str,
) -> AsyncGenerator[str, None]:
    """Simulasi engine forward-pass (mock vLLM / TensorRT-LLM output stream)."""
    # Simulasi prefill time (tergantung panjang prompt)
    prefill_delay = 0.05 + (len(prompt) * 0.0001)
    await time.sleep(prefill_delay)

    # Output generation (20 token)
    simulated_tokens = [f"token_{i} " for i in range(20)]
    for token in simulated_tokens:
        # Simulasi decode iteration pass
        await time.sleep(0.015)  # 15ms per decode step
        yield token


async def instrumented_streaming_service(
    prompt: str,
    model_id: str = "meta-llama/Llama-3-70b-instruct",
) -> AsyncGenerator[str, None]:
    """
    Fungsi facade production-ready yang mengekspos stream ke API layer 
    sambil menjamin eksekusi observabilitas zero-leak.
    """
    telemetry = InferenceTelemetryContext(model_id=model_id)

    async with telemetry:
        try:
            generator = mocked_low_level_llm_generator(prompt)
            async for token_chunk in generator:
                telemetry.record_token_yield()
                yield token_chunk
        except Exception as error:
            # Error ditangkap otomatis oleh manajer konteks untuk instrumentasi tracing
            raise error

    # Diagnostic printing di console (hanya saat debugging)
    summary = telemetry.summarize()
    # Log level INFO pada sistem nyata
    print(
        f"[TELEMETRY LOG] TTFT: {summary.ttft_seconds*1000:.2f}ms | "
        f"Avg ITL: {summary.avg_itl_seconds*1000:.2f}ms | "
        f"Throughput: {summary.throughput_tokens_per_sec:.2f} tok/s | "
        f"Tokens: {summary.total_tokens}"
    )


def update_hardware_telemetry(model_id: str, memory_usage_ratio: float) -> None:
    """Fungsi callback periodik yang dipanggil oleh Worker Health Monitor."""
    if not (0.0 <= memory_usage_ratio <= 1.0):
        raise ValueError("Memory usage ratio harus berada di antara 0.0 dan 1.0")
    METRIC_KV_CACHE_USAGE_RATIO.labels(model_id=model_id).set(memory_usage_ratio)
```

---

### 7. Edge Cases & Failure Modes

1. **High-Cardinality Label Explosion:**
   - *Masalah:* Menyertakan `user_id`, `session_id`, atau `prompt` ke dalam Prometheus metric labels akan menghancurkan database time-series (Prometheus OOM crash).
   - *Mitigasi:* Batasi label metrik hanya pada metadata berdimensi rendah: `model_id`, `status` (success/error), `error_code`, dan `priority_tier`. Detail granular seperti `request_id` hanya boleh dialokasikan pada OpenTelemetry Trace Attributes.

2. **Client Abrupt Disconnection:**
   - *Masalah:* Klien memutus koneksi HTTP streaming sebelum generasi token selesai (misal: tombol "Stop Generating" ditekan).
   - *Mitigasi:* Engine wajib menangani `asyncio.CancelledError`. TTFT dan token yang sempat digenerasi harus tetap tercatat secara akurat, disertai label penanda status `status="cancelled"` agar tidak merusak metrik keberhasilan inferensi.

3. **High-Resolution Clock Overhead pada Hot Loop:**
   - *Masalah:* Melakukan *syscall* clock query (`time.time()`) jutaan kali di dalam tight decode loop CPU/GPU dapat menyebabkan *context switching overhead*.
   - *Mitigasi:* Gunakan `time.perf_counter()` di Python (memanfaatkan register invariant TSC hardware CPU tanpa syscall kernel). Jangan pernah melakukan sinkronisasi CUDA (`torch.cuda.synchronize()`) di dalam path telemetri produksi kecuali saat profiling offline.

4. **Tracing Context Memory Leaks:**
   - *Masalah:* Stream terputus di tengah jalan tanpa blok `finally` atau struktur context manager asynchronous menyebabkan span tidak ditutup (`span.end()` tidak terpanggil), mengakibatkan kebocoran alokasi buffer memori trace context.
   - *Mitigasi:* Membungkus seluruh siklus hidup generator ke dalam abstraksi context manager asinkron (`__aenter__` dan `__aexit__`).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | Out-of-the-Box Engine Metrics (e.g., vLLM `/metrics`) | Custom In-Band Telemetry Wrapper (Pendekatan Modul Ini) | eBPF Kernel Tracing (e.g., BCC / Pixie) |
| :--- | :--- | :--- | :--- |
| **Granularitas Konteks** | Rendah. Terisolasi hanya pada level server/engine. Tidak memiliki trace ID aplikasi end-to-end. | **Tinggi.** Terintegrasi penuh dengan Span OpenTelemetry dari client/API gateway. | Sangat Rendah. Fokus pada system call kernel dan frame GPU driver. |
| **Overhead Komputasi** | Sangat Rendah (~0% CPU, diproses internal C++ engine). | Sangat Rendah (< 0.5% overhead per streaming tick). | **Nol Overhead pada Runtime** (Zero modification di layer aplikasi). |
| **Observabilitas Internal Model** | Unggul dalam membaca KV Cache & status PagedAttention internal. | Mengandalkan bridge eksposur dari engine SDK / API. | Buruk dalam membaca representasi logis dari token dan memory pool model. |
| **Rekomendasi Penggunaan** | Dasar metrik infrastruktur node & scaling horizontal. | **Kewajiban untuk SLA tracking, distributed tracing, & business metrics.** | Audit performa kernel CUDA tingkat rendah & debugging PCIe bottle-neck. |

---

### 9. Best Practices & Standard Industri

1. **Adopsi Semantic Conventions Resmi OTel:** Gunakan penamaan atribut yang distandardisasi oleh OpenTelemetry Generative AI SIG:
   - Atribut Request: `gen_ai.system` (e.g., `"vllm"`), `gen_ai.request.model`, `gen_ai.request.max_tokens`, `gen_ai.request.temperature`.
   - Atribut Token Usage: `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`.
2. **Kalkulasi Persentil Latensi Terpisah:** Jangan pernah menggabungkan TTFT dan ITL ke dalam satu histogram latensi tunggal. Menyatukan fase prefill dan decode ke dalam satu metrik menghancurkan signifikansi deviasi standar dan menghilangkan visibilitas bottleneck.
3. **Continuous Golden Signals Dashboard:**
   - Bangun visualisasi Grafana yang memuat setidaknya 4 panel utama:
     1. P90/P99 TTFT Histogram vs Request Concurrency.
     2. P90/P99 ITL (harus dijaga sedatar mungkin di bawah beban).
     3. KV Cache Usage % (Garis bahaya di set pada ambang batas 85%).
     4. Preemption Counter Rate per Minute.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan membangun pipeline telemetri untuk layanan streaming inferensi yang harus mengekspos metrik ke endpoint Prometheus `/metrics` dan memvalidasi apakah sistem mengalami degradasi ITL saat disimulasikan beban konkuren tinggi.

#### Langkah 1: Persiapan Environment
Pasang library yang diperlukan:
```bash
pip install fastapi uvicorn prometheus-client opentelemetry-api opentelemetry-sdk httpx
```

#### Langkah 2: Buat File Server Inferensi (`server.py`)
Implementasikan server mini FastAPI yang mengintegrasikan `telemetry_engine.py` yang telah dibuat pada Bab 6:

```python
# server.py
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Import dari implementasi kode di Seksi 6
from telemetry_engine import instrumented_streaming_service, update_hardware_telemetry

app = FastAPI(title="LLM Production Inference Telemetry Node")

@app.get("/generate")
async def generate(prompt: str = "Tuliskan ringkasan sistem komputasi performa tinggi."):
    async def token_stream():
        async for token in instrumented_streaming_service(prompt=prompt):
            yield f"data: {token}\n\n"
            
    return StreamingResponse(token_stream(), media_type="text/event-stream")

@app.get("/metrics")
async def metrics():
    """Endpoint untuk Prometheus Scraper."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
async def simulate_background_hardware_metrics():
    """Simulasi pembacaan berkala dari GPU memory allocator."""
    async def background_loop():
        while True:
            # Simulasi saturasi cache normal di 42%
            update_hardware_telemetry(
                model_id="meta-llama/Llama-3-70b-instruct", 
                memory_usage_ratio=0.42
            )
            await asyncio.sleep(5)
            
    asyncio.create_task(background_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### Langkah 3: Eksekusi Load Simulation
Jalankan server:
```bash
python server.py
```

Pada terminal terpisah, jalankan *load injection script* sederhana menggunakan `curl` dan `xargs` untuk membuat concurrent streaming hits:
```bash
# Kirim 10 concurrent requests secara simultan
seq 1 10 | xargs -n 1 -P 10 curl -s "http://localhost:8000/generate?prompt=TestInferenceConcurrencyPayload" > /dev/null
```

#### Langkah 4: Verifikasi & Audit Metrik
Scrape endpoint metrik Prometheus:
```bash
curl -s http://localhost:8000/metrics | grep llm_
```

**Keluaran yang Diharapkan:**
Pastikan metrik-metrik berikut telah terisi dan terdistribusi ke dalam bucket:
- `llm_time_to_first_token_seconds_bucket{...}` (Mencatat observasi prefill time).
- `llm_inter_token_latency_seconds_bucket{...}` (Mencatat 20 iterasi per request pada bucket resolusi tinggi di bawah 50ms).
- `llm_generated_tokens_total{model_id="meta-llama/Llama-3-70b-instruct"} 200.0` (10 request $\times$ 20 token).
- `llm_kv_cache_usage_ratio{model_id="meta-llama/Llama-3-70b-instruct"} 0.42`.