# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Bab:** 01 - Fondasi dan Arsitektur  
**Jalur:** AI Engineer Enterprise  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Bottleneck Inferensi LLM:** Membedah fase *Prefill* (Compute-bound) dan *Decode* (Memory Bandwidth-bound), serta menghitung kebutuhan VRAM untuk KV Cache secara presisi.
2. **Menguasai Arsitektur Serving Modern:** Mengimplementasikan dan mengonfigurasi mesin inferensi berperforma tinggi (vLLM/TGI/Triton) dengan *PagedAttention*, *Continuous Batching*, dan *Chunked Prefill*.
3. **Mendesain Enterprise AI Gateway:** Membangun gateway cerdas yang mencakup *Semantic Caching*, mitigasi kegagalan (*Circuit Breaking* & *Fallback*), *Dynamic Rate Limiting*, serta *Constrained Decoding* untuk output JSON deterministik.
4. **Menerapkan Telemetri & Observabilitas Tingkat Lanjut:** Mengintegrasikan OpenTelemetry untuk metrik kritis LLM: *Time-To-First-Token* (TTFT), *Inter-Token-Latency* (ITL), konsumsi token, dan atribusi biaya operasional.

---

## 2. Prerequisite

Untuk menyerap materi ini secara maksimal, Anda harus memahami:
- **Arsitektur Transformer Dasar:** Mekanisme Multi-Head Attention (MHA), Query-Key-Value ($Q, K, V$), self-attention matrix, dan proses autoregressive generation.
- **Sistem Operasi & Konkurensi:** Pemrograman asinkron (`asyncio` Python), pooling koneksi HTTP/gRPC, threading, dan alokasi memori virtual (paging/segmentation).
- **Infrastruktur Modern:** Docker, Kubernetes dasar, sistem penyimpanan *In-Memory* (Redis), dan konsep dasar GPU (CUDA Cores, Tensor Cores, VRAM High Bandwidth Memory/HBM).

---

## 3. Concept & Internal Architecture

Menerapkan Large Language Model (LLM) di lingkungan produksi memiliki karakteristik yang berbeda secara fundamental dari beban kerja microservices web tradisional. Model inferensi bukan sekadar proses stateless CPU; melainkan proses komputasi masif yang dibatasi oleh arsitektur memori GPU.

### 3.1. Fase Inferensi LLM: Prefill vs. Decode

Proses inferensi autoregressif terbagi menjadi dua tahap dengan profil perangkat keras yang berbeda:

1. **Prefill Phase (Prompt Processing):**
   - **Karakteristik:** Menerima seluruh prompt input $N$ token secara bersamaan.
   - **Matriks Komputasi:** Operasi matriks berukuran besar (General Matrix Multiply - GEMM).
   - **Hardware Bound:** **Compute-bound**. GPU Tensor Cores beroperasi pada utilisasi puncak karena komputasi dapat diparalelisasi secara masif di seluruh sequence.
   - **Metrik:** *Time-To-First-Token* (TTFT).

2. **Decode Phase (Token Generation):**
   - **Karakteristik:** Menghasilkan 1 token per langkah iterasi secara sekuensial. Setiap token baru dimasukkan kembali ke context window untuk langkah berikutnya.
   - **Matriks Komputasi:** Operasi matriks-vektor (General Matrix-Vector - GEMV).
   - **Hardware Bound:** **Memory Bandwidth-bound**. GPU harus memuat bobot model bernilai miliaran parameter dan KV Cache dari High Bandwidth Memory (HBM) ke SRAM hanya untuk menghasilkan satu token.
   - **Metrik:** *Inter-Token Latency* (ITL) atau *Time-Per-Output-Token* (TPOT).

```
+-----------------------------------------------------------------------------+
|                          FASE INFERENSI AUTOREGRESSIVE                      |
+-----------------------------------------------------------------------------+
| 1. PREFILL PHASE (Compute-Bound)                                            |
|    Prompt Tokens: [T1, T2, T3, T4] ---> Parallel Forward Pass               |
|    SRAM Utilization: TINGGI (Matrix-Matrix GEMM)                            |
|    Output: Token Pertama (T5) + Inisialisasi KV Cache                       |
+-----------------------------------------------------------------------------+
| 2. DECODE PHASE (Memory Bandwidth-Bound)                                     |
|    Step 1: [KV Cache T1-T4] + T5  ---> Hitung T6  (Load seluruh weights)   |
|    Step 2: [KV Cache T1-T5] + T6  ---> Hitung T7  (Load seluruh weights)   |
|    Step N: [KV Cache T1-Tn] + Tn  ---> Hitung Tn+1 (Load seluruh weights)   |
|    SRAM Utilization: RENDAH | HBM Bandwidth: JENUH                          |
+-----------------------------------------------------------------------------+
```

### 3.2. KV Cache Mechanics & Penghitungan VRAM

Pada Vanilla Transformer, menghitung attention untuk token ke-$i$ memerlukan nilai $K$ dan $V$ dari token $1$ hingga $i-1$. Jika kita tidak menyimpannya, kita harus menghitung ulang seluruh attention dari awal pada setiap token baru ($O(N^2)$ forward passes). **KV Cache** menyimpan tensor $K$ dan $V$ yang telah dihitung sebelumnya di VRAM.

#### Formula Alokasi KV Cache
Untuk model dengan konfigurasi:
- $L$ = Jumlah layer (`num_layers`)
- $H_{kv}$ = Jumlah head KV (`num_key_value_heads`) (Catatan: Pada MQA/GQA, $H_{kv} < H_q$)
- $D$ = Dimensi per head (`hidden_size / num_attention_heads`)
- $P$ = Presisi (Bytes per elemen: FP16/BF16 = 2 bytes, FP8 = 1 byte, INT4 = 0.5 byte)
- $S$ = Panjang sequence (Context Length)
- $B$ = Batch size

Memori KV Cache per token per request dihitung dengan:
$$\text{Memory}_{\text{token}} = 2 \times L \times H_{kv} \times D \times P \quad \text{(Faktor 2 karena ada Key dan Value)}$$

Total Memori KV Cache untuk melayani traffic:
$$\text{Total KV Cache} = B \times S \times \text{Memory}_{\text{token}}$$

*Contoh Kasus:* Llama-3-70B (Grouped-Query Attention: $L=80$, $H_{kv}=8$, $D=128$, Presisi BF16 = 2 bytes):
$$\text{Memory}_{\text{token}} = 2 \times 80 \times 8 \times 128 \times 2 = 327{,}680 \text{ Bytes} \approx 320 \text{ KB/token}$$
Jika melayani batch size $B=32$ dengan sequence length $S=8{,}192$:
$$\text{Total KV Cache} = 32 \times 8{,}192 \times 327{,}680 \text{ Bytes} \approx 85.89 \text{ GB}$$
*Hanya untuk KV cache saja, sistem membutuhkan lebih dari satu GPU A100 (80GB) penuh tanpa memperhitungkan bobot model (yang memakan ~140GB di FP16).*

### 3.3. PagedAttention & Virtual Memory

Pendekatan serving tradisional mengalokasikan memori KV Cache secara kontigu berdasarkan *panjang maksimum token yang mungkin terjadi* (misal: reservasi langsung 4096 token). Ini menghasilkan **Internal & External Fragmentation** hingga 60-80%.

**PagedAttention** (dipopulerkan oleh vLLM) menyelesaikan masalah ini menggunakan prinsip *Virtual Memory Operating System*:
- Memori fisik KV Cache dibagi menjadi blok-blok berukuran tetap (misal: 16 atau 32 token per block).
- Engine mengelola **Block Table** yang memetakan *logical token blocks* ke *physical GPU memory blocks*.
- Memori dialokasikan secara *on-demand* saat token baru dihasilkan. Jika blok penuh, alokasikan blok non-kontigu baru.
- Memungkinkan **Copy-on-Write (CoW)** untuk operasi *parallel sampling* dan *tree search*.

```
LOGICAL BLOCKS (Request Sequence)
+---------------+---------------+---------------+
| Logical Blk 0 | Logical Blk 1 | Logical Blk 2 |
| Token 0 - 15  | Token 16 - 31 | Token 32 - 47 |
+---------------+---------------+---------------+
        |               |               |
        v               v               v
BLOCK TABLE (Mapping)
| Logical: 0 -> Physical: 7  |
| Logical: 1 -> Physical: 3  |
| Logical: 2 -> Physical: 12 |

PHYSICAL GPU MEMORY (Non-contiguous Allocation)
+----------+----------+----------+----------+----------+
| Block 3  | Block 7  | Block 12 | Empty    | Block X  |
| (Log 1)  | (Log 0)  | (Log 2)  |          | (Other)  |
+----------+----------+----------+----------+----------+
```

### 3.4. Continuous Batching vs. Static Batching

- **Static/Dynamic Naive Batching:** Engine menunggu kumpulan request, menggabungkannya ke dalam batch, mengeksekusi inferensi sampai seluruh request selesai. Masalah: Jika Request A meminta 10 token dan Request B meminta 500 token, Request A selesai cepat namun GPU tetap memproses padding kosong untuk A sampai B selesai (*GPU Underutilization*).
- **Continuous (Iteration-level) Batching:** Scheduler beroperasi pada setiap langkah generasi token individual. Begitu sebuah request mencapai token `[EOS]`, request tersebut dikeluarkan dari batch, dan slot kosong langsung diisi oleh request baru dari antrean (antrean prefill disisipkan di antara langkah decode).

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Produksi?
1. **Model Wrapper Standar (HuggingFace Pipeline/PyTorch Naive):**
   - Menjalankan model via Flask/FastAPI sederhana dengan PyTorch naive menghasilkan utilisasi GPU di bawah 15%.
   - Tidak ada continuous batching: throughput hanya berskala secara vertikal dengan latensi tinggi.
   - Sering memicu OOM (*Out Of Memory*) saat menerima concurrent requests dengan panjang token tak terduga.
2. **Ketergantungan Model Monolitik Tanpa Gateway:**
   - Tidak adanya semantic caching mengakibatkan ribuan kueri serupa (misal FAQ nasabah perbankan) dihitung ulang di level LLM, meningkatkan pengeluaran API hingga 40-70%.
   - Kegagalan downstream provider (seperti rate-limit 429 atau outage OpenAI/Anthropic) langsung membuat aplikasi user-facing crash tanpa mitigasi fallback.

### Apa yang Kita Bangun?
Arsitektur produksi AI terbagi menjadi dua layer utama:
1. **Serving Inference Layer:** Menggunakan high-performance engine berbasis Rust/C++/CUDA yang mengimplementasikan PagedAttention, Continuous Batching, dan Tensor Parallelism.
2. **Resilient AI Gateway Layer:** Layer proksi enterprise yang bertindak sebagai perimeter pertahanan: menyediakan semantic caching, dynamic failover, constrained validation, rate limiting token, dan OpenTelemetry tracing.

---

## 5. How (Workflow Detail)

Alur penanganan kueri di level arsitektur produksi:

```
[ Client Request ]
       |
       v
[ AI Gateway ]
  ├── 1. Auth & Rate Limiter (Token Bucket / User Tiers)
  ├── 2. Prompt Normalization & Canonical Hashing
  ├── 3. Semantic Cache Lookup (Vector DB / Redis Vector Similarity)
  │      ├─ Cache HIT (Similarity > 0.96) ──> Kembalikan respon langsung (< 15ms)
  │      └─ Cache MISS ─────────────────────> Lanjut ke Pipeline Eksekusi
  ├── 4. Routing & Circuit Breaker (Healthy Engine Selection)
  │
  v
[ Inference Engine Cluster (vLLM / Triton) ]
  ├── 5. Continuous Batching Scheduler
  │      ├─ Interleave Prefill (Prompt baru) & Decode (Token berjalan)
  │      └─ PagedAttention Allocator (Dynamic Block Table Mapping)
  ├── 6. Speculative Decoding / Quantized Kernels Execution
  ├── 7. Constrained Decoding Guard (XGrammar / Logit Masking untuk JSON)
  │
  v
[ Stream Processor & Telemetry ]
  ├── 8. Token Streaming via Server-Sent Events (SSE)
  ├── 9. Async Write-Back ke Semantic Cache (untuk prompt generalizable)
  └── 10. Emit OpenTelemetry Spans (TTFT, ITL, Cost, Token Count)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Restoran Cepat Saji Kelas Dunia
- **Vanilla Serving:** Seorang koki menerima 4 pesanan sekaligus. Dia memasak semua pesanan bersamaan, namun menolak menerima pelanggan baru sampai pelanggan dengan pesanan terlama selesai makan. Meja dapur penuh dengan piring kosong yang dipesan sejak awal (*Memory Fragmentation*).
- **Continuous Batching + PagedAttention:** Koki bekerja per irisan waktu (*time-slice*). Begitu satu burger selesai dibungkus, burger tersebut langsung diantarkan ke kasir. Pelanggan baru yang baru masuk langsung dilayani tahap awalnya (*Prefill*) tanpa menunggu pesanan pelanggan lama tuntas dimasak (*Continuous Batching*). Bahan makanan ditaruh di loker fleksibel modular yang dipanggil dengan nomor loker (*PagedAttention*).

### Arsitektur Sistem Gateway & Serving

```
+-------------------------------------------------------------------------------+
|                            ENTERPRISE AI RUNTIME                              |
+-------------------------------------------------------------------------------+
                                     |
               HTTP/gRPC Ingress     v
+-------------------------------------------------------------------------------+
|                             AI GATEWAY (FastAPI / Rust)                       |
|  +--------------------+  +--------------------+  +-------------------------+  |
|  | Rate Limiter (Redis|  | Semantic Caching   |  | Circuit Breaker         |  |
|  | Sliding Window)    |  | (Vector Similarity)|  | (Fallback Orchestrator) |  |
|  +--------------------+  +--------------------+  +-------------------------+  |
+-------------------------------------------------------------------------------+
               |                                           |
               | Inference Request                         | Fallback Request
               v                                           v
+-----------------------------+             +----------------------------------+
| PRIMARY: Self-Hosted Engine |             | SECONDARY: Fallback Engine       |
| (vLLM on 4x H100 GPU Nodes) |             | (External Enterprise LLM APIs)   |
|                             |             |                                  |
| +-------------------------+ |             |  * OpenAI GPT-4o                 |
| | Scheduler (Iteration-   | |             |  * Anthropic Claude 3.5 Sonnet   |
| | level continuous batch) | |             +----------------------------------+
| +-------------------------+ |
| | PagedAttention Engine   | |
| | [GPU Block Table Alloc] | |
| +-------------------------+ |
| | AWQ/FP8 Quantized Base  | |
| +-------------------------+ |
+-----------------------------+
               |
               v
+-------------------------------------------------------------------------------+
|                       OBSERVABILITY & STREAMING PIPELINE                      |
|  * Server-Sent Events (SSE) Stream Controller                                 |
|  * OpenTelemetry Exporter (Metrics: TTFT, ITL, Tokens, GPU Memory Allocation) |
|  * Distributed Tracing (Langfuse / OpenInference collector)                   |
+-------------------------------------------------------------------------------+
```

---

## 7. Implementation: Simple vs. Practical

### 7.1. Simple Example: Kalkulator KV Cache & Profiler Memori

Gunakan script ini untuk menghitung kebutuhan spesifik hardware sebelum melakukan deploy model LLM ke infrastruktur produksi.

```python
"""
kv_cache_calculator.py
Menghitung konsumsi memori bobot model dan KV cache secara presisi.
"""

from dataclasses import dataclass

@dataclass
class ModelSpec:
    name: str
    num_layers: int
    num_attention_heads: int
    num_kv_heads: int
    hidden_size: int
    vocab_size: int
    total_params_billion: float

LLAMA_3_8B = ModelSpec(
    name="Meta-Llama-3-8B",
    num_layers=32,
    num_attention_heads=32,
    num_kv_heads=8,  # Grouped Query Attention (GQA)
    hidden_size=4096,
    vocab_size=128256,
    total_params_billion=8.03
)

LLAMA_3_70B = ModelSpec(
    name="Meta-Llama-3-70B",
    num_layers=80,
    num_attention_heads=64,
    num_kv_heads=8,  # GQA
    hidden_size=8192,
    vocab_size=128256,
    total_params_billion=70.6
)

def calculate_hardware_footprint(
    spec: ModelSpec, 
    precision_bytes: float, 
    batch_size: int, 
    context_length: int
) -> dict:
    # 1. Hitung dimensi head
    head_dim = spec.hidden_size // spec.num_attention_heads
    
    # 2. Ukuran weights model
    model_weight_gb = (spec.total_params_billion * 10**9 * precision_bytes) / (1024**3)
    
    # 3. KV Cache per token: 2 (K & V) * Layer * KV Heads * Head Dim * Presisi
    bytes_per_token = 2 * spec.num_layers * spec.num_kv_heads * head_dim * precision_bytes
    
    # 4. Total KV cache untuk context window target
    total_kv_cache_gb = (bytes_per_token * context_length * batch_size) / (1024**3)
    
    # 5. Total VRAM teoritis minimal (+ 20% CUDA context & activation runtime overhead)
    activation_overhead_multiplier = 1.20
    total_vram_required_gb = (model_weight_gb + total_kv_cache_gb) * activation_overhead_multiplier

    return {
        "model_name": spec.name,
        "precision_bytes": precision_bytes,
        "weight_vram_gb": round(model_weight_gb, 2),
        "kv_cache_per_token_kb": round(bytes_per_token / 1024, 2),
        "total_kv_cache_gb": round(total_kv_cache_gb, 2),
        "recommended_vram_gb": round(total_vram_required_gb, 2)
    }

if __name__ == "__main__":
    # Skenario: Batch size 16, Context 8192 tokens, Presisi BF16 (2 bytes)
    results = calculate_hardware_footprint(LLAMA_3_70B, precision_bytes=2, batch_size=16, context_length=8192)
    print("=== ESTIMASI HARDWARE PRODUCTION SERVING ===")
    for k, v in results.items():
        print(f"{k}: {v}")
```

---

### 7.2. Practical Example: Enterprise AI Gateway Berperforma Tinggi

Berikut implementasi production-grade AI Gateway menggunakan `FastAPI`, `Pydantic v2`, `Redis` (untuk Semantic/Exact Caching), dan `Circuit Breaker` pattern. Gateway ini menyediakan endpoint terpadu dengan mitigasi fallback otomatis ke model sekunder jika inference worker lokal overload/gagal.

```python
"""
production_gateway.py
Enterprise Resilient AI Gateway with Caching, Circuit Breaking, and Structured Output.
Requirement dependencies: fastapi, uvicorn, httpx, redis, pydantic
"""

import time
import json
import hashlib
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx
import redis.asyncio as redis

# Setup Logging Industri
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("EnterpriseAIGateway")

# --- SCHEMA DEFINITIONS ---
class StrictExtractionSchema(BaseModel):
    user_intent: str = Field(description="Klasifikasi intensi pelanggan")
    risk_level: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    action_items: List[str] = Field(description="Langkah penanganan yang diekstrak")
    confidence_score: float = Field(ge=0.0, le=1.0)

class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.0
    require_structured: bool = False

class CompletionResponse(BaseModel):
    text: str
    source: str  # "cache", "primary_engine", "fallback_engine"
    latency_ms: float
    usage: Dict[str, int]

# --- CIRCUIT BREAKER STATE MACHINE ---
class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"[CIRCUIT BREAKER] Threshold tercapai ({self.failure_count}). Status berubah ke OPEN!")

    def allow_execution(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_time_sec:
                self.state = "HALF-OPEN"
                logger.warning("[CIRCUIT BREAKER] Periode recovery selesai. Status berubah ke HALF-OPEN!")
                return True
            return False
        if self.state == "HALF-OPEN":
            # Berikan akses terbatas untuk uji coba
            return True
        return False

# --- GATEWAY ENGINE ---
class ResilientAIEngine:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.circuit_breaker = CircuitBreaker()
        self.primary_engine_url = "http://localhost:8000/v1/completions" # Misal: vLLM Endpoint
        self.fallback_engine_url = "https://api.openai.com/v1/chat/completions"
        self.http_client = httpx.AsyncClient(timeout= httpx.Timeout(10.0, connect=3.0))

    def _compute_cache_key(self, prompt: str, schema_enforced: bool) -> str:
        raw_key = f"{prompt.strip()}__struct_{schema_enforced}"
        return f"llm_cache:{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()}"

    async def get_cached_response(self, cache_key: str) -> Optional[dict]:
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Gagal membaca cache Redis: {e}")
        return None

    async def set_cache_response(self, cache_key: str, data: dict, ttl_sec: int = 3600):
        try:
            await self.redis.set(cache_key, json.dumps(data), ex=ttl_sec)
        except Exception as e:
            logger.warning(f"Gagal menyimpan cache Redis: {e}")

    async def _call_primary_engine(self, payload: dict) -> dict:
        """Memanggil Self-Hosted vLLM Instance"""
        response = await self.http_client.post(self.primary_engine_url, json=payload)
        response.raise_for_status()
        return response.json()

    async def _call_fallback_engine(self, prompt: str) -> dict:
        """Fallback jika cluster on-premise mengalami degrade"""
        logger.warning("[FALLBACK TRIGGERED] Mengalihkan inferensi ke Cloud Provider!")
        # Mocking fallback upstream external API
        await httpx.AsyncClient().get("https://httpbin.org/delay/0") # Dummy async call
        return {
            "choices": [{"text": json.dumps({
                "user_intent": "Layanan dialihkan ke fallback engine",
                "risk_level": "LOW",
                "action_items": ["Investigasi log primary server"],
                "confidence_score": 0.99
            })}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35}
        }

    async def execute(self, req: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        cache_key = self._compute_cache_key(req.prompt, req.require_structured)

        # 1. Periksa Cache
        cached_result = await self.get_cached_response(cache_key)
        if cached_result:
            return CompletionResponse(
                text=cached_result["text"],
                source="cache",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )

        # 2. Validasi Circuit Breaker untuk Primary Node
        if self.circuit_breaker.allow_execution():
            try:
                # Simulasikan pemanggilan payload vLLM
                vllm_payload = {
                    "prompt": req.prompt,
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                }
                
                # Mock call bila testing lokal tanpa vLLM:
                # result = await self._call_primary_engine(vllm_payload)
                # Ganti dengan mock execution terkendali:
                result = {
                    "choices": [{"text": json.dumps({
                        "user_intent": "Komplain Transaksi Gagal",
                        "risk_level": "HIGH",
                        "action_items": ["Kreditkan saldo reversi", "Kirim notifikasi SMS"],
                        "confidence_score": 0.94
                    })}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 40, "total_tokens": 90}
                }
                
                self.circuit_breaker.record_success()
                
                output_text = result["choices"][0]["text"]
                
                # Simpan ke Cache
                await self.set_cache_response(cache_key, {"text": output_text})

                return CompletionResponse(
                    text=output_text,
                    source="primary_engine",
                    latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                    usage=result.get("usage", {})
                )

            except Exception as e:
                logger.error(f"[PRIMARY FAILURE] Terjadi error pada primary engine: {e}")
                self.circuit_breaker.record_failure()
                # Jatuh ke Fallback di bawah

        # 3. Fallback Path
        fallback_res = await self._call_fallback_engine(req.prompt)
        output_text = fallback_res["choices"][0]["text"]

        return CompletionResponse(
            text=output_text,
            source="fallback_engine",
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            usage=fallback_res.get("usage", {})
        )

# --- FASTAPI LIFESPAN & CONTROLLER ---
redis_pool: Optional[redis.Redis] = None
gateway_engine: Optional[ResilientAIEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool, gateway_engine
    redis_pool = redis.from_url("redis://localhost:6379", decode_responses=True)
    gateway_engine = ResilientAIEngine(redis_client=redis_pool)
    yield
    await redis_pool.aclose()

app = FastAPI(title="Enterprise AI Gateway", lifespan=lifespan)

@app.post("/v1/chat/secure-complete", response_model=CompletionResponse)
async def secure_complete(req: CompletionRequest):
    if not gateway_engine:
        raise HTTPException(status_code=500, detail="Engine tidak terinisialisasi.")
    
    try:
        response = await gateway_engine.execute(req)
        
        # Jika klien mewajibkan JSON tervalidasi skema
        if req.require_structured:
            try:
                StrictExtractionSchema.model_validate_json(response.text)
            except Exception as val_err:
                logger.error(f"Structured Output Validation Failed: {val_err}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, 
                    detail="Model menghasilkan output yang melanggar JSON Schema."
                )

        return response
    except Exception as exc:
        logger.critical(f"Unhandled Gateway Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Fraud Intelligence & AML Pipeline pada Bank Tier-1
* **Latar Belakang Kasus:** Sebuah bank multinasional memproses 40 juta event transaksi per hari. Sistem lama menggunakan LLM API publik komersial untuk menganalisis narasi transaksi anomali (*suspicious activity reports* - SAR).
* **Kendala yang Muncul:**
  1. *Cost Spike:* Biaya bulanan menembus \$180,000 USD akibat jutaan prompt SAR berukuran rata-rata 3,500 token yang diproses ulang tanpa caching.
  2. *Data Sovereignty Violation:* Regulator keuangan melarang transmisi data Personally Identifiable Information (PII) keluar dari boundary VPC on-premise.
  3. *Latency degradation:* Jam sibuk (pukul 13:00 - 16:00) menyebabkan antrean API memuncak dengan P99 latency > 18 detik, memicu timeout pada sistem approval transaksi real-time.

### Solusi Arsitektur Produksi yang Diimplementasikan:
1. **Cluster Serving Mandiri:**
   - Deploy 2 node DGX H100 (masing-masing 8x H100 SXM5 80GB).
   - Menjalankan model `Llama-3-70B-Instruct` dengan kuantisasi **AWQ (4-bit)** dan aktivasi FP16.
   - Tensor Parallelism (`tp=4`) per model instance, menghasilkan 4 worker independen di 2 node.
   - Mengaktifkan **Chunked Prefill** (`max_num_batched_tokens=4096`) untuk mencegah request berukuran besar memblokir request pendek.
2. **AI Gateway Hybrid:**
   - **Semantic Cache:** Menggunakan Redis Vector Search dengan cosine similarity threshold 0.97 untuk mendeteksi pola deskripsi transaksi yang identik. Menghasilkan cache hit 42%.
   - **Local Anonymization Engine:** Model ringan (RoBERTa token classification) menghapus nama dan nomor rekening sebelum tokenisasi KV cache.
   - **Constrained Generation:** Menerapkan Outlines/Grammars pada engine inferensi untuk memaksa output sesuai enum schema AML compliance bank tanpa kesalahan format.

### Hasil Metrik Produksi:
| Parameter Metrik | Sebelum Implementasi | Setelah Implementasi | Delta Performa |
| :--- | :--- | :--- | :--- |
| **P99 Inference Latency** | 18,200 ms | 640 ms | **28.4x Lebih Cepat** |
| **System Throughput** | 45 req/sec (Throttled) | 680 req/sec | **15.1x Scale** |
| **Monthly Infrastructure Cost** | \$180,000 USD | \$32,000 USD (Amortisasi Server) | **Efisiensi 82.2%** |
| **Compliance Breach Rate** | 0.04% (Resiko PII Leak) | 0.00% (Strict VPC Air-gap) | **Zero Violation** |

---

## 9. Trade-offs

Setiap keputusan arsitektur serving LLM melibatkan kompromi fundamental sistem:

```
          [ THROUGHPUT ]
             /      \
            /        \
           /          \
   [ LATENCY ] ---- [ COST/PRECISION ]
```

### 1. Throughput vs. Latency (TTFT & ITL)
- **Aggressive Batching (High Max Batch Size):** Mengoptimalkan saturasi GPU Tensor Cores, meningkatkan total throughput token/detik secara global.
- *Trade-off:* Meningkatkan *Time-To-First-Token* (TTFT) dan *Inter-Token Latency* (ITL) bagi pengguna individu karena waktu alokasi memori dan context-switching yang lebih tinggi.

### 2. Quantization Precision vs. Perplexity/Reliability
- **INT4 (AWQ/GPTQ) vs. FP16:**
  - INT4 memangkas konsumsi VRAM hingga 65%, memungkinkan model 70B berjalan pada satu GPU 80GB alih-alih membutuhkan 2-4 GPU.
- *Trade-off:* Menghasilkan degradasi skor perplexity minor (~0.1 - 0.3) dan penurunan akurasi pada penalaran matematika multi-langkah serta penurunan kemampuan mengikuti schema JSON yang rumit.

### 3. Chunked Prefill vs. Pure Prefill
- **Chunked Prefill:** Memecah prompt input panjang menjadi potongan-potongan token lebih kecil dan menyisipkannya bersama fase decode request lain.
- *Trade-off:* Mencegah starvation pada request kecil, tetapi menambah TTFT absolut untuk prompt panjang.

---

## 10. Common Mistakes & Troubleshooting

### 1. Kesalahan Fatal KV Cache OOM di Bawah Beban Konkuren
* **Penyebab:** Konfigurasi `gpu_memory_utilization` diatur terlalu tinggi (misal: 0.98) di vLLM. Ketika PyTorch runtime mengalokasikan memori aktivasi dinamis sesaat atau konteks library eksternal dialokasikan, CUDA langsung crash dengan `RuntimeError: CUDA out of memory`.
* **Solusi Enterprise:** Batasi `gpu_memory_utilization=0.88 - 0.90`. Sisakan ruang 10-12% VRAM untuk buffer fragmentasi memori driver CUDA dan activation spikes.

### 2. Kegagalan Constrained Decoding Menggunakan Regular Expressions
* **Penyebab:** Memaksa model menghasilkan JSON menggunakan regex mentah yang salah atau terlalu ketat pada awal token generasi. Jika model memilih token pembuka yang dilarang oleh finite-state-machine (FSM), logit processor memaksakan token probabilitas terendah, menghasilkan output teks berulang (*infinite looping `}}}}`*).
* **Solusi Enterprise:** Gunakan Context-Free Grammar (CFG) modern seperti XGrammar yang terintegrasi langsung di level C++/CUDA logit processing kernel. Selalu sediakan handling error `max_tokens` fallback jika sequence terjebak.

### 3. Idle Streaming Connections Menghabiskan File Descriptors
* **Penyebab:** Klien menutup koneksi browser secara mendadak saat streaming SSE (Server-Sent Events) berlangsung, namun worker backend tetap mengeksekusi inferensi sampai selesai (*Orphan Inference Generation*).
* **Solusi Enterprise:** Pasang handler pembatalan streaming aktif:
  ```python
  if await request.is_disconnected():
      logger.info("Klien disconnect! Batalkan engine generation task.")
      engine_task.cancel()
  ```

---

## 11. Best Practices (Production Checklist)

### Checklist Konfigurasi Engine Inferensi
- [ ] **PagedAttention Enabled:** Block size diatur ke 16 atau 32 token bergantung pada distribusi rata-rata panjang output.
- [ ] **Kuantisasi Adaptif:** Gunakan AWQ atau FP8 untuk decoding-heavy tasks jika inferensi dibatasi VRAM.
- [ ] **Continuous Batching Dynamic Scheduling:** Matikan opsi static batching pada serving layer.
- [ ] **Chunked Prefill Active:** Parameter token chunking diatur seimbang (`max_num_batched_tokens` di angka 2048 - 4096).
- [ ] **Disable Unused GPU Memory Cache:** Pastikan `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` diaktifkan untuk mengurangi fragmentasi VRAM.

### Checklist Resiliensi Gateway
- [ ] **Circuit Breaker:** Konfigurasi threshold transisi (maksimal 3-5 kegagalan beruntun dengan cooling period 30 detik).
- [ ] **Strict Timeout Management:** Pasang 3 lapis timeout: *Connect Timeout* (2s), *TTFT Timeout* (5s), dan *Total Processing Timeout* (60s).
- [ ] **Schema Conformance Testing:** Validasi struktural Pydantic v2 dijalankan sebelum payload dilempar kembali ke upstream caller.
- [ ] **Observabilitas Metrik:** Kirim metrik berikut ke Datadog/Prometheus:
  - `llm_time_to_first_token_seconds` (Histogram)
  - `llm_inter_token_latency_seconds` (Histogram)
  - `llm_token_throughput_total` (Counter)
  - `llm_cache_hit_ratio` (Gauge)

---

## 12. Hands-on Practice

Target path penyimpanan proyek: `hands-on/m02/`

### Skenario Praktikum:
Bangun end-to-end local benchmark gateway yang menguji throughput antara unoptimized endpoint vs mock continuous batching endpoint dengan Redis Semantic Cache.

### Langkah 1: Struktur Proyek
Buat struktur direktori kerja berikut:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

### Langkah 2: Buat Environment Dependencies
Simpan pada file `requirements.txt`:
```txt
fastapi>=0.110.0
uvicorn>=0.28.0
redis>=5.0.0
httpx>=0.27.0
pydantic>=2.6.0
locust>=2.24.0
```
Instalasi:
```bash
pip install -r requirements.txt
```

### Langkah 3: Setup Redis Service via Docker
```bash
docker run -d --name local-redis-ai -p 6379:6379 redis:7-alpine
```

### Langkah 4: Terapkan Kode Gateway
Salin kode praktikal dari **Seksi 7.2** ke `src/gateway.py`.

### Langkah 5: Buat Script Uji Beban (Locust Benchmark)
Simpan pada `src/locustfile.py`:
```python
from locust import HttpUser, task, between
import json
import random

PROMPTS = [
    "Ekstrak entitas: Nasabah meminta penutupan kartu kredit nomor 4111-2222 dengan segera.",
    "Ekstrak entitas: Transaksi anomali terdeteksi sebesar Rp 50.000.000 pada jam 03.00 pagi.",
    "Analisis sentimen: Saya sangat kecewa aplikasi mobile banking sering error saat transfer dana.",
    "Ekstrak entitas: Permohonan limit kredit baru ditolak oleh sistem tanpa alasan jelas."
]

class AIGatewayUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def test_complete_structured(self):
        payload = {
            "prompt": random.choice(PROMPTS),
            "max_tokens": 128,
            "temperature": 0.0,
            "require_structured": True
        }
        headers = {"Content-Type": "application/json"}
        with self.client.post("/v1/chat/secure-complete", json=payload, headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "source" in data:
                    response.success()
                else:
                    response.failure("Key 'source' hilang dari respon.")
            else:
                response.failure(f"HTTP Error Status: {response.status_code}")
```

### Langkah 6: Eksekusi Uji Beban
1. Jalankan Gateway Server di Terminal 1:
   ```bash
   uvicorn src.gateway:app --port 8080 --workers 4
   ```
2. Jalankan Headless Load Test di Terminal 2:
   ```bash
   locust -f src/locustfile.py --headless -u 50 -r 10 -t 30s --host http://localhost:8080
   ```
3. Amati perubahan rasio respon sumber data (transisi dari `primary_engine` menuju `cache` dengan latensi < 10ms).

---

## 13. Exercise

### Level Easy
Modifikasi kalkulator KV Cache pada **Seksi 7.1** agar dapat menghitung konsumsi memori model dengan arsitektur **Multi-Query Attention (MQA)** di mana nilai $H_{kv} = 1$ terlepas dari jumlah Query Heads ($H_q$). Uji dengan spesifikasi model Falcon-40B ($L=60$, $H_q=64$, $D=128$, $P=2$).
*Kriteria Penerimaan:* Script mencetak perbedaan penghematan persentase VRAM KV Cache antara MHA standar vs MQA.

### Level Medium
Tambahkan *sliding window rate limiter* berbasis user identifier (misal header `X-User-ID`) ke dalam gateway FastAPI menggunakan Redis sorted set (`ZADD`, `ZRANGEBYSCORE`). Batasi maksimal 10 request per 60 detik per user. Jika melebihi batasan, lempar respons `HTTP 429 Too Many Requests` tanpa mengeksekusi LLM.
*Kriteria Penerimaan:* Unit test membuktikan request ke-11 dalam periode window 60 detik berhasil ditolak.

### Level Hard
Implementasikan Logit Processor kustom sederhana secara simulasi di Python yang mengimplementasikan metode *Greedy Grammar Masking*. Sistem menerima schema JSON sederhana `{"status": "OK" | "FAILED"}`. Pada setiap penentuan token berikutnya, processor harus secara matematis mengubah bobot (logits) dari semua token selain yang valid secara sintaksis JSON menjadi $-\infty$.
*Kriteria Penerimaan:* Sistem tidak pernah menghasilkan string yang gagal divalidasi oleh `json.loads()`.

---

## 14. Challenge

### Studi Kasus: Multi-Tenant Zero-Interference Serving Cluster
Sebuah konglomerat healthcare memiliki 3 unit bisnis berbeda yang berbagi cluster komputasi GPU yang sama (8x NVIDIA H100 80GB):
1. **Unit Emergensi Radiologi:** Beban kueri rendah (~5 req/detik), tetapi memerlukan hard SLO P99 latensi under 500ms dan ketersediaan 99.999%.
2. **Unit Riset Biomedis:** Beban analitik batch dokumen panjang (100,000+ token context), toleran terhadap latency (bisa running background), namun menghabiskan seluruh KV cache memory.
3. **Unit Chatbot Pasien Publik:** Beban traffic masif fluktuatif di siang hari (spikes hingga 1,500 req/detik), prompt pendek (< 200 token).

**Tantangan Arsitektur Anda:**
Rancang spesifikasi arsitektur inferensi end-to-end yang menjamin Unit Biomedis **tidak akan pernah** menyebabkan OOM atau degradasi latensi pada Unit Emergensi Radiologi, sembari mempertahankan utilisasi GPU cluster di atas 80%.

**Persyaratan Solusi:**
1. Desain strategi alokasi GPU (Virtual GPU/vGPU slices vs Multi-Instance GPU/MIG vs vLLM Dedicated Slotted Queues).
2. Mekanisme preemptive scheduling pada inference queue: bagaimana cara menjeda (*pause/evict*) prefill dokumen biomedis secara deterministik jika kueri radiologi tiba-tiba masuk?
3. Spesifikasi arsitektur caching layer dan data boundary isolation agar data pasien radiologi terisolasi total secara regulasi HIPAA.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Mengapa fase Decode pada inferensi LLM bersifat Memory Bandwidth-bound alih-alih Compute-bound?**
   - A. Karena ukuran input prompt jauh lebih besar daripada output token.
   - B. Karena model harus memuat ulang miliaran parameter bobot jaringan dari HBM GPU ke register/SRAM hanya untuk memproses satu token baru per langkah.
   - C. Karena GPU Tensor Cores dinonaktifkan secara otomatis saat decoding berlangsung.
   - D. Karena matriks attention tidak dapat dikalikan secara asinkron.
   *Jawaban:* **B**. Pada decoding autoregresif, batch size yang kecil membuat rasio komputasi terhadap pembacaan memori sangat rendah; operasi didominasi pemindahan data parameter dari HBM ke compute units.

2. **Berapa jumlah tensor yang disimpan di dalam KV Cache untuk setiap layer decoder Transformer?**
   - A. Tiga ($Q, K, V$)
   - B. Dua ($K$ dan $V$)
   - C. Satu ($V$ saja, karena $K$ dapat diturunkan kembali)
   - D. Bergantung pada ukuran batch
   *Jawaban:* **B**. Hanya Key ($K$) dan Value ($V$) yang di-cache untuk reuse self-attention pada token-token berikutnya. Query ($Q$) hanya dibutuhkan untuk token yang sedang dievaluasi.

3. **Prinsip dasar sistem operasi yang diadaptasi oleh PagedAttention untuk menyelesaikan masalah fragmentasi memori adalah:**
   - A. Virtual Memory Paging
   - B. Round-robin Process Scheduling
   - C. Thread Mutex Locking
   - D. Direct Memory Access (DMA)
   *Jawaban:* **A**. PagedAttention mengadopsi konsep virtual memory paging, di mana KV cache fisik dialokasikan dalam non-contiguous memory blocks yang dipetakan melalui block table.

4. **Karakteristik utama dari Continuous Batching (Iteration-level batching) adalah:**
   - A. Memproses batch hanya jika seluruh request memiliki jumlah token yang sama persis.
   - B. Scheduler mengevaluasi antrean pada setiap langkah generasi token individual, membuang sequence yang selesai dan menyisipkan request baru.
   - C. Mengunci thread CPU sampai satu siklus batch forward pass selesai sempurna.
   - D. Mewajibkan model di-compile ulang setiap kali batch size berubah.
   *Jawaban:* **B**. Continuous batching bekerja di level iterasi token tunggal, memaksimalkan utilisasi GPU tanpa terblokir oleh request yang memiliki panjang keluaran bervariasi.

5. **Apa fungsi utama dari implementasi Circuit Breaker pada AI Gateway?**
   - A. Mempercepat koneksi internet GPU node.
   - B. Menghentikan sementara pengiriman request ke model backend yang sedang crash/unhealthy untuk mencegah *cascading failure* dan beralih ke fallback.
   - C. Mengenkripsi token LLM agar aman dari penyadapan.
   - D. Menghapus history chat secara berkala dari database.
   *Jawaban:* **B**. Circuit Breaker memonitor kegagalan downstream; jika error rate melampaui batas, sirkuit "terbuka" dan request langsung dialihkan atau ditolak tanpa membebani sistem yang sedang pulih.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus)

6. **Model dengan Grouped-Query Attention (GQA) memiliki 32 Query Heads dan 8 Key-Value Heads. Berapa penghematan ukuran KV Cache dibandingkan Multi-Head Attention (MHA) konvensional?**
   - A. 2x Lebih Hemat
   - B. 4x Lebih Hemat
   - C. 8x Lebih Hemat
   - D. 16x Lebih Hemat
   *Jawaban:* **B**. Pada MHA konvensional, rasio head $Q:KV = 32:32$ (1). Pada GQA ini, rasio $Q:KV = 32:8$, sehingga jumlah tensor KV yang disimpan berkurang sebesar faktor $32 / 8 = 4\times$ (menghemat 75% memori KV cache).

7. **Pada kondisi traffic seperti apa teknik Chunked Prefill memberikan dampak performa paling signifikan?**
   - A. Ketika seluruh traffic hanya terdiri dari kueri-kueri pendek satu baris (misal prompt < 20 token).
   - B. Ketika sistem melayani kueri context panjang (misal analisis dokumen 8K token) bersamaan dengan kueri interaktif pendek (misal chatbot) secara bersamaan.
   - C. Ketika model berjalan secara offline tanpa koneksi jaringan.
   - D. Ketika GPU memiliki VRAM tak terbatas.
   *Jawaban:* **B**. Tanpa chunked prefill, request dokumen panjang akan memonopoli komputasi GPU selama ratusan milidetik, menyebabkan *spikes* latensi ekstrem (ITL starvation) bagi request chatbot interaktif.

8. **Mengapa validasi skema JSON menggunakan regex post-processing murni pada output LLM sering dianggap suboptimal untuk enterprise-grade system?**
   - A. Karena regex memakan 90% VRAM GPU.
   - B. Karena regex tidak dapat membatalkan eksekusi jika model menghasilkan output halusinasi non-valid, membuang token compute berharga sebelum divalidasi.
   - C. Karena regex hanya dapat dijalankan di arsitektur ARM.
   - D. Karena regex otomatis mengubah temperatur sampling model menjadi 1.0.
   *Jawaban:* **B**. Post-processing regex membiarkan model menghabiskan waktu dan komputasi menghasilkan ratusan token invalid sebelum akhirnya di-reject di aplikasi. Pendekatan modern menggunakan *constrained decoding (logit masking)* yang mengarahkan pemilihan token secara deterministik sejak token pertama.

9. **Jika sebuah server GPU menunjukkan metrik: Tensor Core Activity = 22%, HBM Memory Bandwidth Utilization = 96%, apa diagnosa engineering Anda terhadap beban kerja tersebut?**
   - A. Sistem sedang menjalankan heavy Prompt Prefill.
   - B. Sistem sedang berada pada fase Autoregressive Token Decoding dengan ukuran batch yang kecil.
   - C. Driver CUDA mengalami freeze.
   - D. Server kehabisan storage SSD NVMe.
   *Jawaban:* **B**. Decoding autoregressif dengan batch kecil dibatasi oleh kecepatan memori memindahkan bobot model ke cache compute (Memory Bandwidth-bound), sehingga pemanfaatan Tensor Core tampak sangat rendah meskipun memory bus jenuh.

10. **Apa risiko arsitektural utama dalam menerapkan Semantic Caching dengan similarity threshold yang terlalu longgar (misal Cosine Distance < 0.80)?**
    - A. Memory leak pada container gateway.
    - B. False Cache Hit: Sistem mengembalikan jawaban dari kueri sebelumnya yang konteks semantiknya berbeda secara substansial (misal: "Transfer Rp 10jt" dianggap sama dengan "Transfer Rp 100jt").
    - C. Penurunan kecepatan jaringan sebesar 50%.
    - D. Database vector crash karena index jenuh.
    - *Jawaban:* **B**. Threshold yang terlalu permisif memicu *false positive matches*, yang dapat berakibat fatal pada aplikasi enterprise finansial atau medis di mana detail angka dan entitas kecil mengubah makna kueri secara menyeluruh.

---

### Bagian 3: Production Scenarios (Analisis & Rekomendasi Solusi)

#### Kasus 1: Insiden Lonjakan Latensi (TTFT Spike Incident)
*Skenario:* Pada saat peluncuran fitur baru, metrik P99 TTFT melompat dari 350ms menjadi 9,200ms, sementara ITL (Inter-Token Latency) relatif stabil di kisaran 30ms/token. Utilisasi memori GPU tercatat berada di angka 94%.  
* **Pertanyaan:** Apa akar masalah (*root cause*) yang paling mungkin terjadi, dan apa 2 langkah mitigasi konkret yang harus dieksekusi pada inference engine?
* **Solusi & Rekomendasi:**
  - *Root Cause:* **Prefill Starvation & KV Cache Thrashing**. Tingginya volume request baru menyebabkan antrean prefill menumpuk (*queue buildup*). Karena alokasi memori KV cache mendekati batas maksimum (94%), engine terpaksa menunda eksekusi prompt baru (*request stalling*) atau melakukan evict/swapping block memory KV Cache ke Host Memory (RAM CPU).
  - *Langkah Mitigasi Konkret:*
    1. Aktifkan **Chunked Prefill** (`--enable-chunked-prefill`) untuk memecah komputasi prompt besar dan menggabungkannya secara interleaving dengan iterasi decode yang ada.
    2. Kurangi parameter `max_num_seqs` pada scheduler vLLM untuk membatasi jumlah konkurensi request aktif, serta atur `gpu_memory_utilization=0.88` untuk memberikan headroom alokasi blok fisik yang aman.

#### Kasus 2: Degradasi Model Akibat Kuantisasi Agresif
*Skenario:* Tim engineering memutuskan untuk mengonversi model routing internal 70B dari FP16 ke INT4-GPTQ demi menghemat biaya server agar dapat berjalan di 1x A100 (80GB). Setelah deploy, akurasi sistem integrasi JSON drop drastis: API Gateway menerima 18% error format JSON tidak terbaca (*malformed syntax*).
* **Pertanyaan:** Mengapa kuantisasi INT4 merusak output terstruktur lebih parah daripada teks naratif biasa, dan bagaimana arsitektur serving harus diubah tanpa menambah GPU?
* **Solusi & Rekomendasi:**
  - *Analisis:* Representasi bobot INT4 memotong rentang dinamis parameter secara ekstrem. Karakter struktural khusus (seperti `{`, `}`, `"`, `:`) dan logika induksi sintaksis formal berada pada batas distribusi probabilitas token yang sangat sensitif (*outlier activations*). Kuantisasi naive memotong representasi ini sehingga model rentan memilih token penutup yang salah.
  - *Perbaikan Arsitektur:*
    1. Ganti metode kuantisasi ke **AWQ (Activation-aware Weight Quantization)** atau **FP8 (jika menggunakan arsitektur Ada/Hopper)** yang melindungi 1% bobot/aktivasi paling penting (*salient weights*) dari degradasi presisi.
    2. Terapkan **Constrained Decoding Engine** (seperti *Outlines* atau *XGrammar*) di layer serving. Ini memaksakan parsing validitas state machine langsung pada logit level, menjamin 100% syntactical correctness terlepas dari degradasi bobot model.

#### Kasus 3: Thundering Herd Problem pada Semantic Cache
*Skenario:* Sistem menyimpan data FAQ promo diskon di Redis Vector Cache. Tepat pukul 00:00, cache TTL expired secara serentak. 10.000 pengguna secara simultan menanyakan kueri serupa dalam rentang waktu 5 detik. Akibatnya, cluster vLLM seketika mengalami crash OOM.
* **Pertanyaan:** Pola kegagalan apa yang sedang terjadi, dan bagaimana mendesain ulang arsitektur AI Gateway untuk mengatasi fenomena ini?
* **Solusi & Rekomendasi:**
  - *Analisis:* Fenomena ini adalah **Cache Stampede (Thundering Herd Problem)**. Ketika cache kunci populer expired, ribuan request bersamaan mendeteksi *cache miss* secara simultan dan seluruhnya meneruskan kueri ke backend LLM worker yang tidak siap menangani surge komputasi prefill masif secara bersamaan.
  - *Redesign Arsitektur:*
    1. **Probabilistic Early Expiration (XFetch Algorithm):** Perbarui nilai cache di background sebelum waktu TTL benar-benar habis berdasarkan probabilitas kalkulasi waktu komputasi LLM.
    2. **Mutex/Distributed Locking pada Gateway:** Ketika *cache miss* pertama kali terdeteksi untuk sebuah cluster semantik, kunci resource tersebut di Redis menggunakan token lock (`SET NX EX`). Hanya 1 request yang diizinkan memanggil LLM engine untuk mengisi cache, sementara 9.999 request lainnya dibuat menunggu (*await with timeout*) nilai cache baru tersebut tersedia.

---

## 16. Summary

Mengoperasikan sistem AI Engineer di level enterprise membutuhkan pemahaman mendalam tentang batasan fisik komputasi akselerator:
1. **Dinamika Hardware:** Prefill dibatasi oleh kecepatan hitung Tensor Cores (**Compute-Bound**), sedangkan Decode dibatasi oleh throughput transfer data memori HBM (**Memory Bandwidth-Bound**).
2. **Evolusi Serving:** Penggunaan **PagedAttention** memangkas pemborosan VRAM akibat fragmentasi memori KV Cache, sementara **Continuous Batching** memaksimalkan throughput sistem secara dinamis.
3. **Resiliensi Gateway:** Sistem produksi tidak boleh mengekspos model mentah secara telanjang. Gateway wajib menyediakan layer pertahanan berupa **Semantic Caching**, **Circuit Breaking**, penegakan skema terstruktur via **Constrained Logit Processing**, serta pelacakan metrik telemetri granular (**TTFT**, **ITL**, dan **Cost Allocation**).
4. **Prinsip Trade-off:** Arsitek sistem AI harus senantiasa menyeimbangkan segitiga kompromi antara tingkat kuantisasi, throughput konkurensi, latensi individual, serta realitas anggaran infrastruktur komputasi.