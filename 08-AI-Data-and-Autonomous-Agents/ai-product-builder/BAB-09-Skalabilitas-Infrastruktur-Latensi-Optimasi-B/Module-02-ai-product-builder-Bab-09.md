# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Skalabilitas Infrastruktur, Latensi & Optimasi (Bagian B)**
**Jalur: 08-AI-Data-and-Autonomous-Agents / ai-product-builder**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Bottleneck Inferensi LLM:** Membedakan batas komputasi (*compute-bound*) pada fase *Prefill* dan batas memori (*memory-bound*) pada fase *Decode* menggunakan model analitis *Roofline*.
- **Mengimplementasikan Advanced Serving Engine:** Mengonfigurasi dan mengoperasikan mesin inferensi terdistribusi (*vLLM* dan *Triton Inference Server*) menggunakan *PagedAttention*, *Continuous (Iteration-level) Batching*, dan *Chunked Prefills*.
- **Membangun Arsitektur Akselerasi Latensi:** Merancang pipeline *Speculative Decoding* menggunakan pasangan *Draft Model* dan *Target Model* untuk memangkas *Inter-Token Latency* (ITL) tanpa degradasi kualitas output.
- **Mendesain Elastic GPU Orchestration:** Mengonfigurasi Kubernetes HPA/KEDA berbasis metrik *real-time* GPU (*NVIDIA DCGM* dan *vLLM Waiting Requests Queue*) untuk auto-scaling yang hemat biaya.
- **Mengeliminasi Memory Fragmentation:** Mengelola alokasi *KV-Cache* dinamis dan kuantisasi tingkat lanjut (FP8, AWQ, GPTQ) pada kluster GPU heterogen (*multi-node*, *multi-GPU*).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Konsep Arsitektur Transformer:** Mekanisme *Self-Attention*, alokasi dimensi *Key*, *Value*, *Query*, serta dependensi autoregresif token.
- **Sistem Komputasi GPU & CUDA:** Hierarki memori GPU (HBM/VRAM, SRAM, L1/L2 Cache), streaming multiprocessors (SM), *tensor cores*, dan transfer data Host-to-Device (PCIe vs NVLink).
- **Dasar Distributed Systems:** Model komunikasi paralelisme (*Tensor Parallelism* / TP, *Pipeline Parallelism* / PP) via NCCL (*NVIDIA Collective Communications Library*).
- **Tooling:** Docker, Kubernetes (dasar CRD & Operator), Python 3.11+, PyTorch 2.x, dan profiling tool dasar (`nvidia-smi`, `nsys`).

---

## 3. Concept & Internal Architecture

Inferensi Large Language Model (LLM) di lingkungan produksi memiliki karakteristik beban kerja yang unik dan terbagi menjadi dua fase komputasi yang saling bertolak belakang:

```
+-----------------------------------------------------------------------------------+
|                            LLM INFERENCE PHASES                                   |
+-----------------------------------------------------------------------------------+
|  1. PREFILL PHASE (Prompt Processing)             2. DECODE PHASE (Token Gen)     |
|     - Input: Prompt Tokens [T_1 ... T_n]             - Input: 1 Token [T_current]  |
|     - Compute-Bound (Matrix-Matrix / GEMM)           - Memory-Bound (Matrix-Vector)|
|     - High Arithmetic Intensity                      - Low Arithmetic Intensity    |
|     - Mengisi KV-Cache                               - Membaca/Update KV-Cache     |
|     - Menentukan TTFT (Time-To-First-Token)          - Menentukan ITL (Inter-Token)|
+-----------------------------------------------------------------------------------+
```

### 3.1. Internal Architecture: PagedAttention & Continuous Batching

Pada *naive serving*, KV-Cache dialokasikan secara statis berdasarkan panjang konteks maksimum (*max_seq_len*). Hal ini menyebabkan pemborosan memori (*internal fragmentation*) hingga 60-80% dan memicu *Out-Of-Memory* (OOM) prematur.

*PagedAttention* menyelesaikan masalah ini dengan mengadopsi konsep *Virtual Memory* dan *Paging* dari sistem operasi:
1. **Logical KV Blocks:** Memori KV-Cache dipetakan ke dalam blok-blok logis berukuran tetap (misal: 16 atau 32 token).
2. **Physical KV Blocks:** Alokator mengalokasikan blok memori fisik pada VRAM GPU secara dinamis saat token baru dihasilkan, tanpa mewajibkan blok fisik tersebut berada pada alamat memori yang kontigu (*non-contiguous*).
3. **Block Table:** Struktur data sentral yang merekam pemetaan antara *logical block index* dari setiap *request* dengan *physical block index* pada pool VRAM.

```
Request 1 (Seq len = 7, Block Size = 4)
Logical Blocks:  [ Block 0 (Tokens 0-3) ] -> [ Block 1 (Tokens 4-6) ]
                         |                              |
                         v                              v
Block Table:      Physical Block 3               Physical Block 7
                         ^                              ^
Physical VRAM: [PB0] [PB1] [PB2] [PB3] [PB4] [PB5] [PB6] [PB7] ...
```

*Continuous Batching* (Iteration-level scheduling) bekerja berdampingan dengan PagedAttention. Alih-alih menunggu seluruh *batch* selesai melakukan inferensi (*static batching*), *engine* melakukan penjadwalan ulang pada setiap iterasi *step* generasi token:
- *Request* yang selesai (*EOS token*) langsung dieliminasi dari *batch*, membebaskan blok KV-Cache seketika.
- *Request* baru dari antrean langsung dimasukkan ke dalam *running batch* pada iterasi berikutnya tanpa memblokir siklus komputasi request lain.

### 3.2. Speculative Decoding Internals

*Speculative Decoding* memecahkan batas *memory bandwidth* pada fase *Decode*. Satu model kecil (*Draft Model*, misal 1B-3B) menghasilkan spekulasi $K$ token secara autoregresif dengan latensi sangat rendah. Model target besar (*Target Model*, misal 70B) kemudian mengevaluasi seluruh $K$ kandidat token tersebut secara paralel dalam **satu langkah eksekusi forward pass** (*prefill-like GEMM*).

Aturan penerimaan token (*rejection sampling*) memastikan distribusi probabilitas output akhir identik secara matematis dengan output target model mandiri:

$$P(\text{terima } x_{t+i}) = \min\left(1, \frac{P_{\text{target}}(x_{t+i} \mid x_{<t+i})}{P_{\text{draft}}(x_{t+i} \mid x_{<t+i})}\right)$$

Jika satu token ditolak pada posisi $j \le K$, token berikutnya dibuang, token koreksi disampel dari distribusi selisih probabilitas, dan proses spekulasi diulang.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive Serving) | Production-Grade Engine (vLLM / Triton) |
| :--- | :--- | :--- |
| **Batching Mechanism** | *Static Batching* / *Dynamic Request-level Batching*. Terkunci oleh urutan request terpanjang (*head-of-line blocking*). | *Continuous / Iteration-level Batching*. Scheduler menyisipkan token baru per forward pass step. |
| **Alokasi KV-Cache** | Alokasi array kontigu per request setara `max_sequence_length`. Fragmentasi tinggi. | *Paged KV-Cache* alokasi per blok non-kontigu. Fragmentasi memori turun di bawah 4%. |
| **Karakteristik Latensi** | P99 ITL berfluktuasi tajam saat variasi prompt/completion tinggi. | P99 ITL stabil karena isolasi interaksi antar-request pada level iterasi. |
| **Prefill Scheduling** | Prefill mendominasi seluruh GPU, menyebabkan *bubble* dan latensi ITL melonjak drastis (*jitter*). | *Chunked Prefills*: Memecah prompt panjang menjadi potongan-potongan kecil yang digabungkan dengan token decode. |
| **Inference Parallelism** | Terbatas pada single GPU atau Data Parallelism sederhana via HuggingFace Accelerate. | *Tensor Parallelism* (Megatron-LM style) + *Pipeline Parallelism* via NVLink/NCCL teroptimasi kernel Triton. |

---

## 5. How: Production Workflow

Diagram berikut mengilustrasikan alur siklus hidup request dari ingress gateway hingga streaming ke client:

```
[Client]
   │
   ▼ HTTP/gRPC (SSE / Streaming)
[Load Balancer / Ingress Controller]
   │
   ▼ (Sticky session / Least-Queue routing)
[Serving Gateway / Router (Rust/Go)]
   │
   ▼ In-Memory Async Queue
[Engine Engine Scheduler (Continuous Batching Loop)]
   ├── 1. Chunked Prefill Manager (Potong prompt panjang)
   ├── 2. Block Allocator (PagedAttention KV-Cache Manager)
   │         └── Assigns Logical to Physical Blocks in VRAM
   ├── 3. Speculative Engine (Opsional: Draft Forward Pass)
   ├── 4. Worker Group (TP/PP via NCCL)
   │         └── Execution over Tensor Cores (FlashAttention-3 / FP8 GEMM)
   ├── 5. Sampler (Greedy / Top-P / Min-P)
   └── 6. Detokenizer (Incremental Unicode Streaming Engine)
   │
   ▼ Token Stream via HTTP Server-Sent Events (SSE)
[Client Rendering Stream]
```

---

## 6. Analogy & Diagram ASCII

### Analogi PagedAttention: Hotel Management vs Sewa Rumah Tahunan

- **Naive KV-Cache (Sewa Rumah Tahunan):** Setiap tamu yang datang (request), baik berniat menginap 2 hari atau 1 tahun, dipaksa menyewa gedung apartemen 100 kamar (*max_seq_len* = 4096). VRAM habis seketika meski hanya diisi 10 token. Tamu baru ditolak (*OOM Crash*).
- **PagedAttention (Hotel Modern dengan Kamar Kapsul):** Tamu hanya diberi kunci untuk 1 kapsul (blok 16 token). Ketika kapsul penuh dan tamu masih berbicara, sistem mencarikan kapsul kosong lain di lantai berapa pun (blok fisik non-kontigu). Sistem mencatat nomor kamar di buku resepsionis (*Block Table*). Tamu *check-out* langsung membebaskan kapsul untuk tamu antrean berikutnya.

```
                     ARSIKTEKTUR MEMORI KV-CACHE VRAM
+-------------------------------------------------------------------------+
| TOTAL VRAM (e.g., 80 GB A100/H100)                                      |
+-------------------------------------------------------------------------+
| [Model Weights: ~40GB (FP16 70B via TP=2)] [CUDA Overhead: ~2GB]        |
+-------------------------------------------------------------------------+
| SISA VRAM TERSEDIA UNTUK DYNAMIC KV-CACHE (~38GB)                       |
+-------------------------------------------------------------------------+
| Physical Block Pool (Ukuran 1 Blok = 16 Token x H_dim x Layers):        |
| [Blk 00][Blk 01][Blk 02][Blk 03][Blk 04][Blk 05][Blk 06][Blk 07]...     |
|                                                                         |
| Block Table Tracking:                                                   |
| Request A: [Blk 00] -> [Blk 04] -> [Blk 02] (Panjang 40 Token)          |
| Request B: [Blk 01] -> [Blk 03]             (Panjang 25 Token)          |
| Request C (Speculative): [Blk 05 (Forked from A)] (Branching evaluation)|
+-------------------------------------------------------------------------+
```

---

## 7. Simple & Practical Examples

### 7.1. Simple Example: Inisialisasi High-Throughput Engine via vLLM

Konfigurasi serving engine tingkat produksi dengan aktivasi *Chunked Prefills*, *PagedAttention*, dan batasan alokasi VRAM secara eksplisit.

```python
# simple_vllm_engine.py
from vllm import LLM, SamplingParams

# Konfigurasi parameter inferensi dengan kontrol pemakaian memori yang ketat
llm = LLM(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    tensor_parallel_size=1,            # 1 GPU
    gpu_memory_utilization=0.90,       # 90% dialokasikan untuk Weights + KV-Cache
    max_model_len=4096,                # Batas konteks maksimum
    block_size=16,                     # PagedAttention block size
    enable_chunked_prefill=True,       # Mencegah prefill memblokir decode
    max_num_batched_tokens=2048,       # Batas token yang diproses per iterasi forward
    dtype="bfloat16"                   # Presisi optimal untuk Ampere/Ada/Hopper
)

sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.95,
    max_tokens=128,
    stop=["<|im_end|>"]
)

prompts = [
    "Jelaskan konsep continuous batching dalam 2 kalimat.",
    "Apa perbedaan compute-bound dan memory-bound pada inferensi LLM?"
]

outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    prompt = output.prompt
    generated_text = output.outputs[0].text
    print(f"\n[Prompt]: {prompt}")
    print(f"[Generated]: {generated_text.strip()}")
```

### 7.2. Practical Example: High-Concurrency Async Client dengan Circuit Breaker & Streaming

Kode Python ini menggunakan `httpx` async client dengan pola *circuit breaking* dan pengujian latensi *Time-To-First-Token* (TTFT) serta *Inter-Token Latency* (ITL).

```python
# client_stream_resilience.py
import asyncio
import time
import json
import logging
from typing import AsyncGenerator
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LLMClient")

class CircuitBreakerOpenException(Exception):
    pass

class LLMCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()
            logger.error(f"Circuit Breaker TRIPPED to OPEN. Failure count: {self.failure_count}")

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_state_change > self.recovery_timeout:
                self.state = "HALF-OPEN"
                logger.warning("Circuit Breaker transitioned to HALF-OPEN. Testing backend health.")
                return True
            return False
        return True # HALF-OPEN

class ResilientLLMClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.breaker = LLMCircuitBreaker()
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=10.0))

    async def stream_inference(self, prompt: str) -> AsyncGenerator[str, None]:
        if not self.breaker.allow_request():
            raise CircuitBreakerOpenException("Circuit breaker aktif: Serving engine tidak sehat.")

        payload = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "prompt": prompt,
            "max_tokens": 150,
            "stream": True,
            "temperature": 0.2
        }

        t_start = time.perf_counter()
        t_first_token = None
        token_count = 0
        last_token_time = None
        itl_history = []

        try:
            async with self.client.stream("POST", f"{self.base_url}/v1/completions", json=payload) as response:
                if response.status_code != 200:
                    self.breaker.record_failure()
                    raise RuntimeError(f"Engine mengembalikan HTTP {response.status_code}")

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    data_str = line[len("data: "):].strip()
                    if data_str == "[DONE]":
                        break

                    chunk = json.loads(data_str)
                    token = chunk["choices"][0]["text"]
                    current_time = time.perf_counter()

                    if t_first_token is None:
                        t_first_token = current_time
                        ttft_ms = (t_first_token - t_start) * 1000
                        logger.info(f"TTFT: {ttft_ms:.2f} ms")
                    else:
                        itl = (current_time - last_token_time) * 1000
                        itl_history.append(itl)

                    last_token_time = current_time
                    token_count += 1
                    yield token

                self.breaker.record_success()
                
                # Metric calculation
                avg_itl = sum(itl_history) / len(itl_history) if itl_history else 0.0
                total_duration = time.perf_counter() - t_start
                logger.info(
                    f"Generated {token_count} tokens in {total_duration:.2f}s | "
                    f"Mean ITL: {avg_itl:.2f} ms | Throughput: {token_count/total_duration:.2f} tps"
                )

        except Exception as e:
            self.breaker.record_failure()
            logger.error(f"Error streaming LLM response: {str(e)}")
            raise e

async def main():
    client = ResilientLLMClient("http://localhost:8000")
    test_prompt = "Instruksi: Tulis skrip shell untuk automated backup Postgres."
    
    print("Menerima respons streaming:")
    try:
        async for token in client.stream_inference(test_prompt):
            print(token, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[Gagal Eksekusi]: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study: E-Commerce SuperApp Enterprise Support Engine

### Arsitektur Sistem Produksi

```
[25,000 Concurrent User SSE Connections]
                      │
                      ▼
       [Cloudflare Enterprise WAF / DDoS]
                      │
                      ▼
        [Kong Ingress Gateway (HTTP/2)]
                      │
    ┌─────────────────┴─────────────────┐
    ▼                                   ▼
[Semantic Cache (Redis)]     [Custom LLM Dispatcher Router (Go)]
  (Hits: 38% Cache Ratio)               │
                                        ▼ (gRPC Internal Mesh)
                     [K8s Cluster: LLM Serving Pool]
                     ┌───────────────────────────────────────────────┐
                     │ Pod 1-8: H100 (80GB SXM5)                     │
                     │  - Model: Llama-3-70B-Instruct-AWQ (FP8)      │
                     │  - Parallelism: TP=2, Continuous Batching     │
                     │  - Speculative Engine: Llama-3-8B Draft       │
                     │  - KV-Cache Allocation: 0.92 Memory Pool      │
                     └───────────────────────────────────────────────┘
                                        │
                                        ▼ (DCGM Exporter + Custom vLLM Metrics)
                            [Prometheus + KEDA Controller]
                                        │
                     (Autoscaling: scale out Pods if Queue Depth > 12)
```

### Konteks & Masalah Bisnis
Platform E-Commerce SuperApp skala nasional meluncurkan asisten virtual interaktif untuk menangani *customer complaints*, *refund status*, dan rekomendasi produk selama festival belanja *Single's Day* (11.11).
- **Volume Trafik:** Lonjakan dari rata-rata 1.200 req/s ke *peak* 25.000 req/s.
- **SLA:** P95 *Time-to-First-Token* (TTFT) < 800 ms, P95 *Inter-Token Latency* (ITL) < 35 ms.
- **Kendala Awal:** Kluster GPU berbasis arsitektur naive vLLM standar (FP16 tanpa speculative decoding) mengalami *Queue Saturation* parah. VRAM OOM terjadi secara berkala karena ledakan ukuran histori chat (ragam context window dari 500 hingga 12.000 token). Biaya operasional GPU melonjak 400% di atas estimasi budget tanpa memenuhi target SLA.

### Solusi Rekayasa Infrastruktur
1. **Penerapan Speculative Decoding Berpasangan:**
   - **Target Model:** `Meta-Llama-3-70B-Instruct` terkuantisasi via AWQ 4-bit / FP8 execution.
   - **Draft Model:** `Meta-Llama-3-8B-Instruct` (FP8).
   - Kedua model dimuat ke dalam memori bersama pada pasangan GPU (2x H100 SXM5 per Pod). Model 8B bertindak sebagai generator spekulatif 4 token ke depan ($K=4$), dievaluasi paralel oleh model 70B.
2. **KEDA Auto-Scaling Berdasarkan Antrean Token Riil:**
   - Tidak menggunakan *CPU/Memory metrics* bawaan K8s karena GPU utilitas selalu menunjukkan 99-100% meskipun mesin hanya memproses antrean kosong (*idle pooling loops*).
   - Metrik kustom diekstraksi dari vLLM endpoint: `vllm:num_requests_waiting` dan `vllm:gpu_cache_usage_factor`.
   - Scale-up dipicu seketika jika `num_requests_waiting > 10` selama lebih dari 3 detik.
3. **Prefix Caching & Semantic Router:**
   - *System prompt* customer care (~1.500 token instruksi, guardrails, format JSON output) memiliki token identik pada setiap request.
   - Mengaktifkan `enable_prefix_caching=True` pada vLLM. *Hash logical block* dari system prompt disimpan permanen di VRAM; alokator tidak pernah menghitung ulang KV-Cache untuk bagian prompt pembuka ini.
4. **Chunked Prefills:**
   - Menghilangkan latensi *jitter* dengan memecah dokumen histori transaksi panjang menjadi potongan 512 token, digabungkan dalam antrean generasi decode.

### Hasil Kuantitatif Produksi
- **Latensi:** P95 ITL terpangkas sebesar 62% (dari 68 ms menjadi 26 ms per token). P95 TTFT turun dari 2.100 ms ke 420 ms berkat *Automatic Prefix Caching*.
- **Throughput:** Kluster mampu menangani peningkatan beban sebesar 3,4x lipat pada jumlah *hardware* GPU yang sama.
- **Efisiensi Finansial:** Menurunkan kebutuhan provisioning GPU dari proyeksi 96 unit H100 menjadi hanya 32 unit H100 SXM5, memangkas biaya infrastruktur sebesar 66,7% (penghematan setara ~$180.000/bulan).

---

## 9. Trade-offs Architecture Matrix

| Strategi Arsitektur | Keuntungan Utama | Kerugian / Risiko | Dampak Latensi (TTFT vs ITL) | Dampak Biaya Hardware |
| :--- | :--- | :--- | :--- | :--- |
| **Speculative Decoding** | Mempercepat kecepatan generasi token (*decode*) hingga 2-3x tanpa degradasi akurasi. | Membutuhkan alokasi VRAM ekstra untuk memuat model *draft*; komputasi terbuang jika acceptance rate rendah (<50%). | TTFT: Netral/Sedikit Naik.<br>ITL: Turun signifikan (-40% s.d. -65%). | Naik sedikit (butuh VRAM cadangan untuk draft model). |
| **FP8 / AWQ Quantization** | Memangkas footprint VRAM hingga 50%; throughput *batching* naik 2x lipat. | Degradasi marjinal pada penalaran matematis/sintaks kode ketat; kalibrasi bobot non-trivial. | TTFT: Turun signifikan.<br>ITL: Turun moderat (memory bound berkurang). | Turun drastis (dapat menggunakan GPU tier lebih rendah). |
| **Chunked Prefills** | Menghilangkan *spikes* pada ITL; membuat latensi decode stabil dan konsisten. | Sedikit menaikkan TTFT keseluruhan untuk dokumen/prompt yang sangat besar. | TTFT: Naik moderat (+10% s.d. +25%).<br>ITL: Sangat stabil (P99 jitter hilang). | Netral. |
| **Tensor Parallelism (TP > 1)** | Mengurangi latensi per token dengan membagi matriks ke banyak GPU via NVLink. | Overhead sinkronisasi NCCL `AllReduce`; inefisien jika dilakukan antar node non-NVLink. | TTFT: Turun.<br>ITL: Turun (selama bandwidth interkoneksi GPU > 600 GB/s). | Naik (memerlukan interkoneksi super-cepat SXM/NVLink). |

---

## 10. Common Mistakes & Troubleshooting Guide

### 10.1. Common Anti-Patterns in High-Scale Serving

1. **Mengabaikan Prefill-induced ITL Bubbles:**
   - *Anti-Pattern:* Menjalankan serving engine dengan membiarkan prompt berukuran 8k token dieksekusi secara instan tanpa chunking.
   - *Dampak:* Seluruh proses decode token untuk 50 user lain terhenti total (*freeze*) selama 300-800 ms saat GPU memproses GEMM prompt besar tersebut.
   - *Solusi:* Selalu konfigurasikan `enable_chunked_prefill=True` dan batasi `max_num_batched_tokens`.

2. **Salah Mengonfigurasi Metrik HPA (Kubernetes Autoscaling):**
   - *Anti-Pattern:* Melakukan auto-scale GPU Pod menggunakan metrik standar CPU Utilization atau `container_gpu_utilization`.
   - *Dampak:* Pod tidak pernah *scale up* saat antrean macet parah (karena model engine yang sedang menunggu IO/antrean tidak selalu membakar compute core), atau Pod tidak pernah *scale down* karena alokasi memori vLLM statis 90% dianggap sebagai kebocoran memori.
   - *Solusi:* Gunakan metrik KEDA berbasis antrean nyata: `vllm:num_requests_waiting > X`.

3. **Inappropriate Block Size pada PagedAttention:**
   - *Anti-Pattern:* Menggunakan `block_size=8` untuk output yang rata-rata panjang (>2000 token) atau sebaliknya `block_size=64` untuk request super pendek.
   - *Dampak:* Block size terlalu kecil menyebabkan overhead pemetaan *Block Table* melonjak di CPU runtime; block size terlalu besar memicu *internal fragmentation* tinggi.
   - *Solusi:* Standar industri optimal adalah 16 atau 32 token per blok.

### 10.2. Production Incident Diagnostic Runbook

```
+-------------------------------------------------------------------------------+
| MASALAH 1: Client mendadak menerima HTTP 503 / "Engine core engine queue full"|
+-------------------------------------------------------------------------------+
  Langkah Diagnosis:
  1. Jalankan pengecekan metrik vLLM:
     curl -s http://<pod-ip>:8000/metrics | grep -E "vllm:num_requests_waiting|vllm:gpu_cache_usage_factor"
  2. Analisis output:
     - Jika vllm:gpu_cache_usage_factor >= 0.99: KV-Cache jenuh.
     - Jika vllm:num_requests_waiting melonjak > 100: Beban masuk melampaui kemampuan komputasi.
  Mitigasi Cepat:
  - Turunkan max_model_len pada konfigurasi pod deployment.
  - Aktifkan semantic caching di gateway depan.
  - Naikkan batas replika pada HPA KEDA.

+-------------------------------------------------------------------------------+
| MASALAH 2: GPU Out-Of-Memory (CUDA OOM) saat runtime berjalan beberapa jam    |
+-------------------------------------------------------------------------------+
  Langkah Diagnosis:
  1. Periksa alokasi VRAM via PyTorch Caching Allocator:
     Periksa log untuk pesan: "CUDA out of memory. Tried to allocate X GiB"
  Mitigasi:
  - Parameter gpu_memory_utilization default vLLM adalah 0.90.
  - Jika container menjalankan background thread CUDA (misal: embedding model kecil atau tokenization eksternal),
    turunkan gpu_memory_utilization ke 0.80 atau 0.85 untuk memberikan ruang bagi CUDA context host memory.
```

---

## 11. Best Practices & Production Checklist

### Infrastructure & Configuration
- [ ] **Gunakan Kernel FlashAttention-2 / FlashAttention-3:** Pastikan CUDA toolkit dan driver NVIDIA kompatibel dengan arsitektur GPU target (misal: Turing, Ampere, Ada Lovelace, Hopper).
- [ ] **Lock Engine Dtype ke BF16 atau FP8:** Hindari FP32 sepenuhnya. Gunakan Bfloat16 jika model asli FP16/BF16, atau gunakan kuantisasi FP8 (native Hopper/Ada) untuk memangkas konsumsi bandwidth memori.
- [ ] **Prefix Caching Aktif:** Aktifkan `--enable-prefix-caching` pada vLLM jika aplikasi Anda memiliki template instruksi, system context, atau Few-Shot examples yang seragam.
- [ ] **Isolasi TP (Tensor Parallelism) dalam Satu Node:** Jangan pernah melakukan Tensor Parallelism lintas node jaringan kecuali menggunakan interkoneksi InfiniBand/RoCE 800 Gbps dengan NVLink switch. Untuk antar-node, gunakan Pipeline Parallelism atau independent replicas.

### Monitoring & Observability
- [ ] Pasang **NVIDIA DCGM Exporter** pada setiap node kluster K8s untuk memonitor `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_MEM_COPY_UTIL`, dan temperatur hardware.
- [ ] Pantau metrik spesifik LLM secara real-time via Prometheus:
  - `vllm:time_to_first_token_seconds_bucket` (SLA TTFT)
  - `vllm:time_per_output_token_seconds_bucket` (SLA ITL)
  - `vllm:num_requests_running` vs `vllm:num_requests_waiting`
  - `vllm:gpu_cache_usage_factor` (Kapasitas KV-Cache tersisa)

---

## 12. Hands-on Practice: Membangun Inference Cluster dengan Autoscaling Mock & Engine Testing

Semua file untuk praktikum ini disimpan pada path: `hands-on/m02/`

### Struktur Direktori
```text
hands-on/m02/
├── Dockerfile.vllm
├── compose.yaml
├── keda-scaledobject.yaml
├── load_test.py
└── test_client.py
```

### Langkah 1: Siapkan Konfigurasi Docker Compose

Buat file `hands-on/m02/compose.yaml` untuk mengorkestrasi vLLM server dengan konfigurasi produksi:

```yaml
# hands-on/m02/compose.yaml
services:
  vllm-engine:
    image: vllm/vllm-openai:v0.6.3.post1
    container_name: vllm-prod-engine
    runtime: nvidia
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    ports:
      - "8000:8000"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    ipc: host
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    command: >
      --model Qwen/Qwen2.5-1.5B-Instruct
      --gpu-memory-utilization 0.85
      --max-model-len 2048
      --block-size 16
      --enable-chunked-prefill
      --max-num-batched-tokens 1024
      --disable-log-requests
```

### Langkah 2: Buat Manifest KEDA ScaledObject

Buat file `hands-on/m02/keda-scaledobject.yaml` untuk autoscaling berbasis antrean:

```yaml
# hands-on/m02/keda-scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-autoscaler
  namespace: llm-serving
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-deployment
  minReplicaCount: 1
  maxReplicaCount: 8
  cooldownPeriod: 300
  pollingInterval: 5
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-k8s.monitoring.svc:9090
        metricName: vllm_num_requests_waiting
        query: sum(vllm:num_requests_waiting{namespace="llm-serving"})
        threshold: "5"
```

### Langkah 3: Script Load Testing untuk Menguji Dynamic Batching & Antrean

Buat file `hands-on/m02/load_test.py` untuk mensimulasikan beban konkuren tinggi dan memverifikasi ketahanan sistem:

```python
# hands-on/m02/load_test.py
import asyncio
import aiohttp
import time
import random
import numpy as np

TARGET_URL = "http://localhost:8000/v1/completions"
CONCURRENT_USERS = 30
TOTAL_REQUESTS = 150

PROMPTS = [
    "Tuliskan fungsi binary search dalam Python beserta analisis kompleksitasnya.",
    "Jelaskan prinsip kerja arsitektur Transformer dan mekanisme self-attention secara detail.",
    "Berikan analisis perbedaan ACID dan BASE pada sistem basis data modern.",
    "Bagaimana cara men-debug latency spiking pada aplikasi microservice berbasis gRPC?"
]

async def send_inference_request(session: aiohttp.ClientSession, req_id: int):
    prompt = random.choice(PROMPTS)
    payload = {
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "prompt": prompt,
        "max_tokens": 100,
        "temperature": 0.3
    }
    
    t_start = time.perf_counter()
    try:
        async with session.post(TARGET_URL, json=payload) as response:
            status = response.status
            data = await response.json()
            latency = (time.perf_counter() - t_start) * 1000
            
            if status == 200:
                return {"status": "SUCCESS", "latency": latency, "tokens": len(data["choices"][0]["text"].split())}
            else:
                return {"status": f"HTTP_{status}", "latency": latency, "tokens": 0}
    except Exception as e:
        return {"status": "ERROR", "latency": (time.perf_counter() - t_start) * 1000, "error": str(e)}

async def load_test_runner():
    connector = aiohttp.TCPConnector(limit=CONCURRENT_USERS)
    timeout = aiohttp.ClientTimeout(total=60.0)
    
    print(f"Memulai Load Test: {TOTAL_REQUESTS} requests dengan concurrency {CONCURRENT_USERS}...")
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        semaphore = asyncio.Semaphore(CONCURRENT_USERS)

        async def bounded_request(idx):
            async with semaphore:
                return await send_inference_request(session, idx)

        tasks = [bounded_request(i) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)

    # Process metrics
    latencies = [r["latency"] for r in results if r["status"] == "SUCCESS"]
    failures = [r for r in results if r["status"] != "SUCCESS"]

    print("\n--- HASIL EVALUASI LOAD TESTING ---")
    print(f"Total Request: {len(results)}")
    print(f"Sukses: {len(latencies)} | Gagal: {len(failures)}")
    if latencies:
        print(f"P50 Latency: {np.percentile(latencies, 50):.2f} ms")
        print(f"P90 Latency: {np.percentile(latencies, 90):.2f} ms")
        print(f"P99 Latency: {np.percentile(latencies, 99):.2f} ms")
        print(f"Rata-rata Latensi: {np.mean(latencies):.2f} ms")
    if failures:
        print(f"Detail Kegagalan: {failures[:3]}... (Truncated)")

if __name__ == "__main__":
    asyncio.run(load_test_runner())
```

---

## 13. Exercises

### Level Easy
Ubah parameter `block_size` pada instance vLLM dari 16 menjadi 32, lalu jalankan benchmark throughput sederhana.
- **Kriteria Keberhasilan:** Laporkan perubahan memori yang teralokasi pada startup log vLLM dan perubahan total throughput request/detik.

### Level Medium
Konfigurasikan script monitoring Python independen yang melakukan *polling* setiap 1 detik ke endpoint `/metrics` dari vLLM. Buat mekanisme *alerting* sederhana ke konsol jika `vllm:num_requests_waiting` bernilai lebih dari 0 selama 5 detik berturut-turut.
- **Kriteria Keberhasilan:** Script berhasil memicu alert saat script `load_test.py` dijalankan pada konkurensi di atas batas kemampuan satu GPU.

### Level Hard
Implementasikan sebuah sistem *Custom Dispatcher* menggunakan FastAPI yang bertindak sebagai *Smart Gateway* di depan dua instance model:
- 1 Instance Primary (FP16/BF16 Model)
- 1 Instance Fallback (Kuantisasi Ringan / Model Kecil)
Dispatcher harus memeriksa metrik antrean dari Instance Primary. Jika `num_requests_waiting > 20`, request baru dialihkan (*shedding/routing*) secara mulus ke Instance Fallback.
- **Kriteria Keberhasilan:** Saat traffic spike, tidak ada request yang mengalami timeout atau HTTP 503; request yang dialihkan mencatat header HTTP `X-Served-By: Fallback-Engine`.

---

## 14. Architecture Challenge

### Skenario Kasus: Multi-Tenant Heterogeneous GPU Serving Architecture
Perusahaan SaaS Anda menyediakan API generasi kode untuk 50.000 engineer enterprise secara simultan. Anda dihadapkan pada kendala infrastruktur berikut:
- **Ketersediaan Perangkat Keras:** Kluster GPU Anda heterogen karena keterbatasan stok cloud:
  - 8x NVIDIA A100 (80GB SXM4)
  - 16x NVIDIA L40S (48GB PCIe)
  - 24x NVIDIA A10G (24GB PCIe)
- **Kebutuhan Beban Kerja:**
  - Tenant Tier-1 (VIP): Memerlukan penalaran penuh dari model 70B (`Meta-Llama-3-70B-Instruct`) dengan SLA P95 TTFT < 500ms dan streaming latency ITL < 25ms.
  - Tenant Tier-2 (Standard): Menggunakan model 8B (`Meta-Llama-3-8B-Instruct`) untuk auto-complete sederhana.
  - Spike traffic harian sering terjadi pada jam 09:00 - 11:00 pagi WIB.

### Tugas Desain Anda:
1. Rancang arsitektur pembagian beban kerja (*allocation mapping*) ke dalam kluster GPU yang heterogen tersebut. Tentukan GPU mana yang dialokasikan untuk model 70B (dan skema paralelismenya: TP/PP), serta model mana yang ditempatkan pada L40S dan A10G.
2. Definisikan strategi kuantisasi yang tepat per tipe GPU tanpa mengorbankan kualitas sintaksis coding (evaluasi batasan FP8 pada A10G vs L40S vs A100).
3. Buat skema *Admission Control* dan *Dynamic Load Routing* yang mencegah Tenant Tier-2 mengambil resource VRAM dari antrean Tenant Tier-1.
4. Dokumentasikan arsitektur ini dalam bentuk diagram alur sistem dan spesifikasi teknis konfigurasi serving engine.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Mengapa fase Decode pada LLM dikategorikan sebagai *Memory-Bound*?**
   - A. Karena ukuran prompt terlalu besar untuk dimuat ke SRAM.
   - B. Karena forward pass dilakukan satu token per step, sehingga rasio transfer bobot model dan KV-Cache dari VRAM ke Tensor Core jauh lebih besar daripada jumlah kalkulasi aritmatika yang dilakukan.
   - C. Karena CPU tidak mampu mengirimkan instruksi PCIe dengan cepat.
   - D. Karena model inferensi tidak menggunakan kuantisasi.
   *Jawaban:* **B**. Pada fase decode, setiap forward pass hanya memproses satu token, sehingga aritmetic intensity-nya rendah dan kecepatan eksekusi dibatasi oleh memory bandwidth GPU (*Memory-Bound*).

2. **Apa fungsi utama dari arsitektur *PagedAttention*?**
   - A. Menghapus kebutuhan KV-Cache secara permanen.
   - B. Menghilangkan fragmentasi memori VRAM dengan memetakan memori KV-Cache ke dalam blok-blok logis dan fisik yang non-kontigu.
   - C. Mengurangi parameter model menggunakan metode pruning dinamis.
   - D. Mengubah floating point FP16 menjadi integer 4-bit secara otomatis.
   *Jawaban:* **B**. PagedAttention mengadopsi konsep virtual paging sistem operasi untuk mengalokasikan memori KV-cache secara non-kontigu sehingga mengurangi pemborosan alokasi statis.

3. **Metrik apa yang mengukur durasi dari saat prompt dikirimkan hingga karakter/token pertama diterima oleh client?**
   - A. Inter-Token Latency (ITL).
   - B. Queries Per Second (QPS).
   - C. Time-To-First-Token (TTFT).
   - D. Model Flops Utilization (MFU).
   *Jawaban:* **C**. TTFT adalah metrik kritis yang merefleksikan kecepatan fase *Prefill*.

4. **Pada kondisi apa *Speculative Decoding* memberikan percepatan (*speedup*) tertinggi?**
   - A. Saat output model bersifat acak (*high entropy/temperature* tinggi).
   - B. Saat model draft memiliki acceptance rate yang tinggi (misal: teks yang repetitif, dokumen formal, kode terstruktur).
   - C. Saat bandwidth memori GPU sangat rendah dan model target berukuran di bawah 1B parameter.
   - D. Saat inference dilakukan pada CPU lawas.
   *Jawaban:* **B**. Speculative decoding paling optimal saat teks mudah diprediksi oleh draft model sehingga sebagian besar token spekulasi diterima oleh target model.

5. **Apa kelemahan utama dari mekanisme *Static Batching* pada inferensi LLM?**
   - A. Menghabiskan terlalu banyak interkoneksi jaringan.
   - B. Terjadinya *Head-of-line blocking*, di mana request yang pendek harus menunggu request yang paling panjang selesai sebelum batch baru diproses.
   - C. Menghasilkan token yang tidak valid secara sintaksis.
   - D. Tidak mendukung model Transformer modern.
   *Jawaban:* **B**. Static batching mengunci eksekusi bersamaan, menyia-nyiakan resource saat sequence pendek telah memancarkan token EOS lebih awal.

---

### Bagian 2: Intermediate (5 Soal)
1. **Bagaimana mekanisme *Continuous Batching* (Iteration-level scheduling) mengatasi inefisiensi Static Batching?**
   - A. Dengan menyatukan seluruh prompt ke dalam satu string tunggal.
   - B. Dengan menjadwalkan ulang *batch* pada setiap iterasi eksekusi token; sequence yang selesai segera diekstraksi dan sequence baru dari antrean langsung disisipkan.
   - C. Dengan mengubah semua operasi matriks menjadi operasi single-thread.
   - D. Dengan menolak semua prompt yang memiliki panjang melebihi rata-rata sequence.
   *Jawaban:* **B**. Penjadwalan pada tingkat forward pass step memungkinkan pergantian token masuk dan keluar secara elastis tanpa *GPU compute bubble*.

2. **Apa dampak langsung dari pengaktifan *Chunked Prefills* terhadap metrik TTFT dan ITL?**
   - A. Menurunkan TTFT secara drastis untuk semua tipe request.
   - B. Menstabilkan ITL (mengurangi jitter) bagi request decode yang sedang berjalan, dengan kompromi sedikit menaikkan TTFT pada prompt berukuran besar.
   - C. Menghilangkan latensi jaringan secara permanen.
   - D. Membuat konsumsi memori VRAM melonjak secara eksponensial.
   *Jawaban:* **B**. Chunked prefills memecah komputasi prefill masif menjadi bagian-bagian kecil yang disisipkan bersamaan dengan decode, menghilangkan jeda panjang pada request yang sedang streaming.

3. **Mengapa *Tensor Parallelism* (TP) umumnya dibatasi hanya dalam cakupan satu mesin fisik (single node)?**
   - A. Karena keterbatasan lisensi software model open-source.
   - B. Karena TP membutuhkan komunikasi latensi ultra-rendah dan bandwidth sangat masif (NVLink) untuk operasi *AllReduce* antar-layer yang sering; latensi jaringan ethernet biasa akan merusak performa.
   - C. Karena PyTorch tidak mendukung komputasi multi-node.
   - D. Karena model transformer hanya dapat dimuat pada satu bus PCIe.
   *Jawaban:* **B**. Overhead transmisi tensor activation antar-GPU pada setiap layer transformer via ethernet akan mendominasi dan mengeliminasi keuntungan paralelisasi komputasi.

4. **Apa yang terjadi ketika parameter `gpu_memory_utilization` disetel ke 1.0 (100%) pada vLLM engine?**
   - A. Engine akan berjalan dengan performa komputasi maksimal tanpa kendala.
   - B. Risiko sangat tinggi terjadinya crash *CUDA Out-of-Memory* (OOM) karena tidak ada VRAM tersisa untuk CUDA context runtime, dynamic PyTorch memory buffers, dan overhead komunikasi driver.
   - C. Secara otomatis mengaktifkan kompresi kuantisasi 1-bit.
   - D. vLLM menolak inisialisasi karena parameter tersebut wajib di bawah 0.5.
   *Jawaban:* **B**. Margin memori (umumnya disetel antara 0.85 - 0.92) mutlak diperlukan untuk menampung alokasi dinamis selain model weights dan KV pool.

5. **Dalam teknik *Speculative Decoding*, jika token ke-3 dari 4 token spekulasi yang diajukan oleh draft model ditolak oleh target model, maka tindakan apa yang diambil sistem?**
   - A. Seluruh 4 token langsung dibuang dan proses dibatalkan (*re-prompt*).
   - B. Token ke-1 dan ke-2 diterima, token ke-3 dikoreksi via sampling target model, token ke-4 dibuang, lalu forward pass spekulasi baru dimulai dari token ke-3 yang telah terkoreksi.
   - C. Draft model dihukum dengan mengurangi parameter layer-nya.
   - D. Target model dipaksa menerima token tersebut guna menjaga throughput.
   *Jawaban:* **B**. Mekanisme verifikasi autoregresif menerima prefix kandidat valid hingga titik penolakan pertama, mengoreksi token tersebut, dan membuang token selanjutnya.

---

### Bagian 3: Production Case Scenarios (3 Skenario Kasus)

#### Skenario 1: The "Frozen Stream" Anomaly
**Kondisi:** Sistem serving LLM Anda menyajikan rata-rata 300 token streaming per detik ke antarmuka pengguna web. Secara berkala, setiap beberapa menit, teks streaming pengguna web mendadak terhenti (*freeze*) selama 1,5 hingga 2 detik, lalu kembali memuntahkan sekelompok token dengan sangat cepat. Metrik monitoring menunjukkan utilitas GPU berada pada 100%, namun tidak ada pesan error di log.
- **Analisis:** Mengapa fenomena ini terjadi?
- **Tindakan:** Solusi arsitektural apa yang wajib diaktifkan pada engine vLLM untuk mengeliminasi fenomena tersebut?
*Solusi Analisis & Tindakan:* Fenomena ini disebabkan oleh kedatangan prompt berukuran sangat masif (*long-context prefill*) yang diproses secara utuh dalam satu batch iterasi tanpa pemotongan. Fase prefill yang monopolistik ini memblokir eksekusi fase decode dari seluruh request lain yang sedang aktif (*head-of-line compute starvation*). Solusi teknisnya adalah mengaktifkan **Chunked Prefills** (`--enable-chunked-prefill=True`) serta membatasi token budget per forward pass step melalui parameter `--max-num-batched-tokens` (misal disetel ke 512 atau 1024).

#### Skenario 2: Autoscaling Crash Loop under Morning Burst
**Kondisi:** Pada pukul 08:30 WIB, traffic sistem naik 5x lipat. Cluster Kubernetes HPA yang dikonfigurasi menggunakan metrik CPU pod `targetCPUUtilizationPercentage: 75%` mendadak membuat 10 pod vLLM baru secara bersamaan. Akibatnya, server database dan model storage bucket mengalami saturasi bandwidth (I/O Bottleneck), pod baru memerlukan waktu 8 menit untuk *pull* bobot model (80GB), dan traffic antrean yang menumpuk memicu timeout HTTP 504 massal.
- **Analisis:** Sebutkan dua kegagalan fatal pada desain arsitektur deployment ini!
- **Tindakan:** Bagaimana mendesain ulang arsitektur scaling ini agar tangguh terhadap burst traffic?
*Solusi Analisis & Tindakan:* Dua kesalahan: (1) Menggunakan CPU metrics untuk aplikasi serving LLM yang perilakunya decoupled dari utilitas CPU; (2) Cold-start latency pod yang terlalu lambat karena download bobot model saat scaling runtime. Desain ulang: (a) Ganti metrik scaling ke **KEDA** berbasis `vllm:num_requests_waiting` dari Prometheus; (b) Terapkan **Pre-warmed Model Storage** menggunakan *ReadWriteMany* NVMe Storage Class terdistribusi (seperti JuiceFS/EFS/Local SSD caching) atau DaemonSet cache lokal sehingga model weights dapat dimuat ke VRAM dalam hitungan detik tanpa transfer jaringan eksternal; (c) Terapkan strategi *Horizontal Buffer* (selalu pertahankan minimal 2 idle warm replicas).

#### Skenario 3: High ITL on Multi-Node Deployment
**Kondisi:** Sebuah tim teknik mencoba menyajikan model `Llama-3-70B` secara terdistribusi di atas dua buah node server fisik. Setiap server memiliki 2x GPU NVIDIA A100 PCIe (40GB). Tim menghubungkan kedua node tersebut melalui jaringan kabel 10Gbps Ethernet biasa dan mengonfigurasi Tensor Parallelism `TP=4`. Saat benchmark dijalankan, throughput generasi token sangat lambat: hanya 3 token/detik (ITL > 300ms).
- **Analisis:** Jelaskan akar penyebab mendasar (*root cause*) penurunan performa ekstrem ini!
- **Tindakan:** Bagaimana konfigurasi arsitektur paralelisme yang seharusnya diterapkan pada keterbatasan hardware tersebut?
*Solusi Analisis & Tindakan:* Tensor Parallelism (TP) membutuhkan pertukaran tensor aktivasi antar-GPU pada setiap layer melalui operasi komunikasi kolektif `AllReduce`. Bandwidth jaringan 10Gbps Ethernet (~1.25 GB/s) sangat tidak memadai jika dibandingkan dengan bus NVLink (~600 GB/s) atau PCIe Gen4 (~64 GB/s). Jaringan ethernet lambat tersebut menjadi bottleneck kritis. Konfigurasi yang benar: Hindari TP melintasi node ethernet biasa. Gunakan kombinasi **Pipeline Parallelism (PP=2)** antar node (komunikasi hanya terjadi di batas stage pipeline), dipadukan dengan **Tensor Parallelism (TP=2)** internal di dalam masing-masing node lokal melalui interkoneksi PCIe internal.

---

## 16. Summary

Mengoperasikan model LLM pada skala enterprise memerlukan pergeseran paradigma dari *standard web serving* menuju arsitektur *high-performance distributed computing*:
1. **Dinamika Komputasi:** Fase *Prefill* (Compute-Bound, GEMM) dan fase *Decode* (Memory-Bound, GEMV) memiliki profil beban hardware yang kontras. Pengelolaan latensi memerlukan pemisahan metrik TTFT dan ITL.
2. **Efisiensi Memori dengan PagedAttention:** Paging memori KV-Cache ke dalam blok-blok fisik non-kontigu menghilangkan alokasi statis yang boros, memungkinkan penerapan *Continuous Batching* yang memaksimalkan utilisasi GPU tanpa *head-of-line blocking*.
3. **Optimasi Berkelanjutan:** *Speculative Decoding*, *Chunked Prefills*, dan kuantisasi (AWQ/FP8) bertindak sebagai akselerator latensi dan throughput kunci, memangkas biaya infrastruktur secara drastis seraya menjaga kestabilan P99 response time.
4. **Resiliensi Tingkat Produksi:** Autoscaling wajib digerakkan oleh antrean real-time engine (`num_requests_waiting`) via KEDA, dipadukan dengan circuit breaker, isolasi layer paralelisme (TP/PP), dan prefix caching untuk menjamin keandalan sistem berskala puluhan ribu konkurensi.