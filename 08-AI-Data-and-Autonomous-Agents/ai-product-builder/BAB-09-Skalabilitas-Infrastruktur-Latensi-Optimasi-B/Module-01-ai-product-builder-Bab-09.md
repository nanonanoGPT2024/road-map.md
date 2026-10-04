# Bab 09: Skalabilitas Infrastruktur, Latensi & Optimasi Biaya

---

## 1. Learning Objectives

Setelah menyelesaikan bab ini, peserta didik diharapkan mampu:
- **Menganalisis dan Memetakan Pola Trafik AI**: Mengidentifikasi perbedaan profil latensi *Time-to-First-Token* (TTFT) versus *Time-Per-Output-Token* (TPOT) serta dampaknya terhadap throughput sistem dan *User Experience* (UX).
- **Merancang Arsitektur Semantic Caching**: Mengimplementasikan layer *caching* berbasis kemiripan vektor (*vector similarity*) untuk memangkas latensi inferensi hingga <50ms dan mereduksi biaya API LLM komersial hingga 40-60%.
- **Membangun Model Cascading & Dynamic Routing**: Mengembangkan *intelligent router* yang secara dinamis mengalihkan beban kerja antara model frontier (misal: GPT-4o, Claude 3.5 Sonnet) dan model *cost-efficient* (misal: Llama-3-8B, GPT-4o-mini) berdasarkan kompleksitas kueri.
- **Menerapkan Token-Bucket Rate Limiting & Concurrency Control**: Mengontrol ledakan kuota (*burst traffic*) dan mengisolasi konsumsi token per *tenant* guna mencegah *denial-of-wallet* attacks dan *provider rate-limit exhaustion* (HTTP 429).
- **Mengintegrasikan Context Caching & Prompt Compression**: Memanfaatkan arsitektur *prompt caching* (KV-cache reuse) dari penyedia LLM untuk menekan biaya input token dan latensi *prefill*.

---

## 2. Concept Overview

Membangun produk AI pada skala produksi memperkenalkan tantangan yang belum pernah ditemui pada arsitektur perangkat lunak tradisional. Pada sistem CRUD konvensional, latensi didominasi oleh operasi I/O basis data (skala 5–50 milidetik) dan komputasi CPU yang terprediksi. Sebaliknya, inferensi *Large Language Model* (LLM) melibatkan kalkulasi matriks *autoregressive* masif yang memakan waktu antara 500 milidetik hingga puluhan detik per transaksi.

```
       +-----------------------------------------------------------+
       |                  THE ENTERPRISE AI TRILEMMA               |
       |                                                           |
       |                         Intelligence                      |
       |                       (Reasoning/Model)                   |
       |                             /\                            |
       |                            /  \                           |
       |                           /    \                          |
       |                          /      \                         |
       |                         /   /\   \                        |
       |                        /   /  \   \                       |
       |                       /   /____\   \                      |
       |                      /              \                     |
       |                     /________________\                    |
       |         Cost Efficiency              Low Latency          |
       |        ($/Million Tokens)              (TTFT/TPOT)        |
       +-----------------------------------------------------------+
```

### Mental Model: The AI Trilemma
Setiap arsitektur produk AI beroperasi di bawah batasan *The AI Trilemma*: Anda hanya dapat mengoptimalkan dua dari tiga variabel berikut secara bersamaan:
1. **Intelligence**: Kemampuan penalaran kompleks, akurasi penalaran *zero-shot*, dan kepatuhan instruksi (*instruction-following*).
2. **Low Latency**: Umpan balik kilat yang esensial untuk aplikasi interaktif (*autocomplete*, conversational agents).
3. **Cost Efficiency**: *Unit economics* yang berkelanjutan untuk mendukung jutaan kueri harian tanpa membakar margin laba kotor (*gross margin erosion*).

### Metrik Kunci Latensi Inferensi
1. **Time-to-First-Token (TTFT)**: Durasi dari saat server menerima kueri hingga token pertama dihasilkan. TTFT mencakup waktu pemrosesan jaringan, alokasi antrean, dan fase *prompt prefill* (pemrosesan input tokens).
2. **Time-Per-Output-Token (TPOT)**: Waktu yang dihabiskan untuk menghasilkan setiap token berikutnya selama fase *decode* (sifatnya *memory bandwidth bound*).
3. **Tokens Per Second (TPS)**: Kecepatan transfer informasi ke pengguna ($TPS = 1 / TPOT$).

Optimasi infrastruktur AI berpusat pada pemutusan ketergantungan brute-force terhadap satu model terkuat untuk semua skenario. Solusinya adalah membangun *hybrid infrastructure* yang mengombinasikan **Semantic Caching**, **Model Cascading**, dan **Context Caching**.

---

## 3. Why It Matters

Dalam implementasi skala *enterprise*, mengabaikan tata kelola latensi dan biaya dapat melumpuhkan produk sebelum mencapai *product-market fit*:

1. **Gross Margin Erosion**: Penggunaan LLM kelas frontier untuk tugas-tugas sepele (klasifikasi sentimen, ekstraksi entitas dasar) dapat menghabiskan $0.03–$0.06 per kueri. Pada volume 1 juta kueri per hari, biaya operasional dapat mencapai $900.000–$1.800.000 per tahun hanya untuk inferensi teks mentah.
2. **Drop-off Rate Akibat Latensi**: Data industri menunjukkan bahwa penambahan TTFT sebesar 1 detik pada asisten berbasis AI meningkatkan tingkat pembatalan (*drop-off rate*) pengguna hingga 18-25%.
3. **Cascading Failure Akibat Rate Limits (HTTP 429)**: Penyedia komersial memberlakukan *Tokens Per Minute* (TPM) dan *Requests Per Minute* (RPM). Lonjakan trafik pengguna tanpa mekanisme *load smoothing* lokal akan melumpuhkan ketersediaan sistem global.
4. **Denial-of-Wallet Attacks**: Pengguna berbahaya dapat mengirimkan prompt berukuran 128k token secara terus-menerus, memicu tagihan ribuan dolar dalam hitungan jam jika tidak ada kuota dan *hard limits* per tingkat *tenant*.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur *Production-Grade AI Gateway* yang mengisolasi aplikasi dari penyedia model pihak ketiga:

```
[ Client Applications / SDKs ]
              |
              | HTTPS / gRPC Request
              v
+-----------------------------------------------------------------------------------+
|                            AI PROXY GATEWAY LAYER                                 |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | [1] Token Bucket Rate Limiter & Concurrency Manager (Tenant Quota Service)   |  |
|  +-----------------------------------------------------------------------------+  |
|                                     | Token Valid & Concurrency Slot Available    |
|                                     v                                             |
|  +-----------------------------------------------------------------------------+  |
|  | [2] Prompt Sanitizer, Truncator & Context Normalizer                         |  |
|  +-----------------------------------------------------------------------------+  |
|                                     |                                             |
|                                     v                                             |
|  +-----------------------------------------------------------------------------+  |
|  | [3] Semantic Cache Engine (Redis Vector / HNSW Index)                        |  |
|  |     - Embed Query -> Vector Search                                          |  |
|  |     - Cosine Similarity >= Threshold (e.g. 0.94)?                           |  |
|  +-----------------------------------------------------------------------------+  |
|         |                                           |                             |
|     (HIT: Return Cached Response <40ms)         (MISS)                            |
|         |                                           v                             |
|         |                     +------------------------------------------------+  |
|         |                     | [4] Complexity Classifier & Cascade Router     |  |
|         |                     |     - Light/Classification Task? -> Cheap Tier |  |
|         |                     |     - Complex Reasoning Task?    -> Deep Tier  |  |
|         |                     +------------------------------------------------+  |
|         |                                           |                             |
|         |                                           v                             |
|         |                     +------------------------------------------------+  |
|         |                     | [5] Resilient Provider Adapter Pool            |  |
|         |                     |     - Circuit Breakers & Timeout Handlers      |  |
|         |                     |     - Fallback Cascades                        |  |
|         |                     +------------------------------------------------+  |
+---------|-------------------------------------------|-----------------------------+
          |                                           |
          |           +-------------------------------+-------------------+
          |           |                               |                   |
          |           v                               v                   v
          |     +------------+                  +------------+      +------------+
          |     | Fast Tier  |                  | Deep Tier  |      | Fallback   |
          |     | Llama-3-8B |                  | Claude 3.5 |      | GPT-4o-    |
          |     | (vLLM self)|                  | Sonnet     |      | mini       |
          |     +------------+                  +------------+      +------------+
          |           |                               |                   |
          |           +-------------------------------+-------------------+
          |                                           |
          |                                     Stream Chunks / Final Text
          |                                           |
          v                                           v
+-----------------------------------------------------------------------------------+
| [6] Telemetry & Cost Aggregator                                                   |
|     - Log Prompts, Tokens (Input/Output), Latencies (TTFT/TPOT)                   |
|     - Asynchronous Vector Store Upsert for Semantic Cache                         |
+-----------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Semantic Caching
Berbeda dengan *key-value cache* standar (MD5/SHA256 dari teks prompt), semantic caching bekerja berdasarkan kedekatan makna konseptual:
1. Teks prompt dikonversi menjadi embedding vektor via model embedding berlatensi sangat rendah (misal: `text-embedding-3-small` atau lokal `bge-small-en-v1.5`).
2. Indeks HNSW (*Hierarchical Navigable Small World*) diakses untuk mencari vektor yang mirip di database vektor dalam memori (seperti Redis Stack).
3. Jika nilai *Cosine Similarity* $\ge \tau$ (di mana $\tau$ biasanya bernilai antara $0.92$ hingga $0.96$), sistem mendeteksi *Cache Hit*.
4. **Parameter Guardrail**: Semantic cache hanya boleh diterapkan pada transaksi non-deterministik rendah (parameter `temperature: 0.0` atau tugas faktual). Semantic cache tidak boleh diaktifkan jika kueri mengandung variabel waktu sensitif (*ephemeral data*) atau instruksi yang menuntut keberagaman jawaban.

### 5.2 Model Cascading (Speculative / Tiered Routing)
Model cascading adalah teknik mengevaluasi kueri dari model yang paling murah dan cepat terlebih dahulu, kemudian berpindah ke model yang lebih besar hanya jika dibutuhkan:
- **Heuristic / Classifier Routing**: Menggunakan model SLM (*Small Language Model*) atau *Random Forest Classifier* ringan untuk menentukan kompleksitas prompt berdasarkan panjang teks, dependensi kode, kompleksitas instruksi, dan *intent*.
- **Confidence Scoring / Self-Reflection**: Model kecil mengeksekusi instruksi dan mengeluarkan skor kepastian (*confidence score*). Jika skor berada di bawah ambang batas (misal $< 0.8$), kueri diteruskan ke frontier model.
- **Syntactic Fallback**: Kueri dikirim ke model kecil dengan format JSON terstruktur. Jika parser JSON gagal memvalidasi struktur output, sistem mengeksekusi fallback ke model frontier.

### 5.3 Context Caching & Prefix Reuse
Penyedia LLM modern (seperti OpenAI, Anthropic, Google Gemini) menyediakan arsitektur *Prompt Caching*:
- Jika prompt memiliki prefix yang identik $\ge 1024$ token (termasuk *system prompt*, *few-shot examples*, atau dokumen RAG dasar), penyedia menyimpan *KV (Key-Value) Cache* di layer GPU.
- **Dampak Finansial**: Input token yang mengenai *KV Cache* mendapatkan potongan harga hingga 50-80% dan memangkas TTFT hingga 70-80% karena server tidak perlu mengomputasi ulang representasi matematis dari prefix tersebut.
- **Implementasi Desain**: Pertahankan determinisme struktur *system prompt* dan letakkan parameter dinamis (seperti timestamp, nama pengguna) di bagian paling akhir (*suffix*) prompt.

---

## 6. Production-Ready Code Implementation

Berikut implementasi *AI Proxy Gateway* modular menggunakan Python 3.11+, FastAPI, Vector-based Semantic Cache, dan Model Cascading dengan penanganan kesalahan standar industri.

```python
import hashlib
import json
import logging
import math
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "module":"%(name)s", "message":%(message)s}'
)
logger = logging.getLogger("ai_gateway")

# --- DOMAIN MODELS ---

class GatewayRequest(BaseModel):
    user_id: str
    prompt: str = Field(..., min_length=1, max_length=100000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    force_refresh: bool = Field(default=False)
    max_tokens: int = Field(default=1024, ge=1, le=4096)

class GatewayResponse(BaseModel):
    response_text: str
    model_used: str
    cached: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float

# --- SEMANTIC CACHE SIMULATOR (Vector Sim Hash in Memory) ---

class SemanticCache:
    """
    Simulasi InMemory Vector Similarity Cache menggunakan Cosine Distance.
    Pada implementasi riil, gantikan storage ini dengan Redis Vector Store (HNSW).
    """
    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        # Format: list of tuples (embedding_vector, prompt_text, response_data)
        self.storage: List[Tuple[List[float], str, str, int, int]] = []

    async def get_embedding(self, text: str) -> List[float]:
        """
        Mock embedding generator berlatensi rendah deterministik berbasis hash.
        Untuk production: gunakan client.embeddings.create(model='text-embedding-3-small').
        """
        seed = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16) % (10 ** 8)
        # Menghasilkan vektor normalisasi dimensi 8
        raw_vec = [math.sin(seed + i) for i in range(8)]
        norm = math.sqrt(sum(x * x for x in raw_vec))
        return [x / norm for x in raw_vec]

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        return sum(a * b for a, b in zip(vec_a, vec_b))

    async def lookup(self, prompt: str) -> Optional[Tuple[str, int, int]]:
        query_vec = await self.get_embedding(prompt)
        for cached_vec, _, resp, in_tok, out_tok in self.storage:
            sim = self._cosine_similarity(query_vec, cached_vec)
            if sim >= self.threshold:
                return resp, in_tok, out_tok
        return None

    async def store(self, prompt: str, response: str, in_tok: int, out_tok: int) -> None:
        vec = await self.get_embedding(prompt)
        self.storage.append((vec, prompt, response, in_tok, out_tok))
        # Pembatasan memori sederhana (FIFO)
        if len(self.storage) > 1000:
            self.storage.pop(0)

# --- TOKEN BUCKET RATE LIMITER ---

class TokenBucketLimiter:
    """Mengendalikan volume kueri per user (concurrency & TPS protection)."""
    def __init__(self, capacity: int = 10, refill_rate_per_sec: float = 2.0):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.buckets: Dict[str, Dict[str, float]] = {}

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        if user_id not in self.buckets:
            self.buckets[user_id] = {"tokens": self.capacity, "last_updated": now}

        bucket = self.buckets[user_id]
        elapsed = now - bucket["last_updated"]
        bucket["tokens"] = min(self.capacity, bucket["tokens"] + elapsed * self.refill_rate)
        bucket["last_updated"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True
        return False

# --- COST CALCULATOR ---

class PricingEngine:
    # Biaya per 1K Token
    PRICING = {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
        "gpt-4o": {"input": 0.00500, "output": 0.01500},
        "claude-3-5-sonnet": {"input": 0.00300, "output": 0.01500}
    }

    @classmethod
    def calculate_cost(cls, model: str, in_tokens: int, out_tokens: int) -> float:
        rates = cls.PRICING.get(model, {"input": 0.001, "output": 0.002})
        cost = (in_tokens / 1000 * rates["input"]) + (out_tokens / 1000 * rates["output"])
        return round(cost, 6)

# --- MODEL CASCADING CLIENT ---

class ResilientLLMDispatcher:
    def __init__(self):
        self.cheap_model = "gpt-4o-mini"
        self.premium_model = "claude-3-5-sonnet"

    def is_complex_task(self, prompt: str) -> bool:
        """Heuristik deteksi kompleksitas: panjang token, kata kunci penalaran, format instruksi."""
        complex_triggers = ["architecture", "prove", "step-by-step", "optimize algorithmic", "refactor"]
        if len(prompt.split()) > 300:
            return True
        return any(trigger in prompt.lower() for trigger in complex_triggers)

    async def execute_mock_call(self, model: str, prompt: str, max_tokens: int) -> Tuple[str, int, int]:
        """Simulasi network call ke LLM provider."""
        start_time = time.time()
        # Estimasi token mentah (1 kata ~ 1.3 token)
        in_tokens = int(len(prompt.split()) * 1.3) + 5
        out_tokens = min(max_tokens, 150)

        # Simulasi latensi berdasarkan level model
        if model == self.cheap_model:
            time_delay = 0.25  # Model kecil sangat cepat (TTFT + decode)
            resp = f"[TIER: FAST ({model})] Solusi ringkas untuk: {prompt[:30]}..."
        else:
            time_delay = 0.95  # Model besar butuh alokasi pemrosesan lebih tinggi
            resp = f"[TIER: PREMIUM ({model})] Analisis komprehensif logis: {prompt[:30]}..."

        time.sleep(time_delay)  # Emulasi I/O blocking ringan
        return resp, in_tokens, out_tokens

    async def route_and_execute(self, prompt: str, max_tokens: int) -> Tuple[str, str, int, int]:
        # Cek alur cascading
        target_model = self.premium_model if self.is_complex_task(prompt) else self.cheap_model
        
        try:
            resp, in_t, out_t = await self.execute_mock_call(target_model, prompt, max_tokens)
            return resp, target_model, in_t, out_t
        except Exception as e:
            logger.error(json.dumps({"error": str(e), "action": "trigger_fallback"}))
            # Fallback ke tier lain jika primer gagal
            fallback_model = self.cheap_model if target_model == self.premium_model else self.premium_model
            resp, in_t, out_t = await self.execute_mock_call(fallback_model, prompt, max_tokens)
            return resp, fallback_model, in_t, out_t

# --- GATEWAY APPLICATION ---

app = FastAPI(title="Enterprise AI Gateway", version="1.0.0")

semantic_cache = SemanticCache(threshold=0.95)
rate_limiter = TokenBucketLimiter(capacity=20, refill_rate_per_sec=5.0)
dispatcher = ResilientLLMDispatcher()

@app.post("/v1/chat/completions", response_model=GatewayResponse)
async def handle_completion(payload: GatewayRequest):
    req_start = time.time()

    # 1. Rate Limiting Check
    if not rate_limiter.is_allowed(payload.user_id):
        logger.warning(json.dumps({"event": "rate_limited", "user_id": payload.user_id}))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Tingkat batas permintaan terlampaui. Silakan perlambat transmisi Anda."
        )

    # 2. Semantic Cache Check (Hanya jika temperature == 0 & refresh tidak dipaksa)
    if payload.temperature == 0.0 and not payload.force_refresh:
        cached_result = await semantic_cache.lookup(payload.prompt)
        if cached_result:
            resp_text, in_tok, out_tok = cached_result
            latency = (time.time() - req_start) * 1000
            logger.info(json.dumps({"event": "cache_hit", "latency_ms": latency, "user_id": payload.user_id}))
            return GatewayResponse(
                response_text=resp_text,
                model_used="semantic-cache-v1",
                cached=True,
                latency_ms=round(latency, 2),
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=0.0
            )

    # 3. Model Cascading & Upstream Execution
    resp_text, model_used, in_tok, out_tok = await dispatcher.route_and_execute(
        payload.prompt, payload.max_tokens
    )

    # 4. Asynchronous Cache Insertion (Hanya jika transaksi deterministik)
    if payload.temperature == 0.0:
        await semantic_cache.store(payload.prompt, resp_text, in_tok, out_tok)

    total_latency = (time.time() - req_start) * 1000
    cost = PricingEngine.calculate_cost(model_used, in_tok, out_tok)

    logger.info(json.dumps({
        "event": "llm_completion_success",
        "model": model_used,
        "latency_ms": round(total_latency, 2),
        "tokens": {"input": in_tok, "output": out_tok},
        "cost_usd": cost,
        "user_id": payload.user_id
    }))

    return GatewayResponse(
        response_text=resp_text,
        model_used=model_used,
        cached=False,
        latency_ms=round(total_latency, 2),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Semantic Drift & Cache Poisoning
- **Masalah**: Ambang batas kesamaan vektor (*cosine threshold*) yang terlalu longgar (misal $< 0.88$) dapat mengembalikan jawaban dari pertanyaan yang tampak serupa secara sintaksis namun memiliki negasi kritis.
  *Contoh*: *"Bagaimana cara mengaktifkan SSL?"* vs *"Bagaimana cara menonaktifkan SSL?"* memiliki representasi embedding yang sangat berdekatan.
- **Mitigasi**: Terapkan ekstraksi kata kunci negasi deterministik (*hard filter*) sebelum mengecek kemiripan kosinus, atau naikkan ambang batas ke $\ge 0.95$. Pisahkan cache berdasarkan *namespace tenant* untuk mencegah kebocoran data (*data leakage*).

### 7.2 The Token Overflow Fallback Paradox
- **Masalah**: Ketika model primer yang lebih murah (misal context window 8k) gagal karena prompt melebihi limit token dan fallback dialihkan ke frontier model (context window 128k), biaya transaksi melonjak drastis secara tidak terduga.
- **Mitigasi**: Terapkan *Context Window Truncator* tegas di layer proxy sebelum eksekusi. Tolak kueri jika melampaui alokasi kuota per kueri (*prompt size guardrail*).

### 7.3 Cascading Thundering Herd pada Penyedia Cadangan
- **Masalah**: Ketika penyedia layanan utama (OpenAI) mengalami gangguan total (*HTTP 500/503*), seluruh beban trafik secara serentak mengalir (*failover*) ke penyedia cadangan (Anthropic). Akibatnya, kuota TPM cadangan langsung habis seketika (*instant exhaustion*).
- **Mitigasi**: Terapkan algoritma *Circuit Breaker* (misal pola *Netflix Hystrix*). Jika kegagalan upstream utama melampaui 50% dalam interval 10 detik, *trip the circuit* dan kembalikan pesan *degraded experience* alih-alih membanjiri sistem cadangan.

---

## 8. Trade-offs & Alternatif Solusi

| Parameter Desain | Semantic Caching | Exact Hash Caching | Dynamic Cascading | Single-Frontier Model |
| :--- | :--- | :--- | :--- | :--- |
| **Latensi** | Sangat Rendah (<50ms) | Ekstrem Rendah (<5ms) | Bervariasi (200ms–2000ms) | Tinggi (1000ms–5000ms) |
| **Biaya Infrastruktur** | Butuh Vector DB / RAM | Murah (Standard Redis) | Sangat Hemat Biaya LLM | Sangat Mahal |
| **Akurasi Kontekstual** | Rentan salah tafsir jika threshold $\tau$ rendah | 100% Deterministik | Tinggi (Jika Router akurat) | Maksimal |
| **Kompleksitas Kode** | Tinggi (Vector Index, Embedder) | Sangat Sederhana | Tinggi (Heuristik / Classifier) | Nol (Panggilan Tunggal) |

### Kapan Menggunakan Self-Hosted (vLLM/TGI) vs Managed APIs?
- **Pilih Managed API**: Volume kueri $< 500.000$ token per hari, tim infrastruktur terbatas, membutuhkan kapabilitas penalaran absolut (Frontier models).
- **Pilih Self-Hosted vLLM**: Trafik konsisten $\ge 50$ permintaan per detik (RPS) pada model 8B/70B, regulasi privasi data ketat (on-premise / VPC air-gapped), dan *fixed-cost budget allocation*.

---

## 9. Best Practices & Standar Industri

1. **Streaming First Architecture**: Selalu gunakan antarmuka SSE (*Server-Sent Events*) atau WebSocket untuk mengirimkan token secara inkremental ke antarmuka pengguna. Ini memotong persepsi latensi pengguna (*perceived latency*) dari durasi total (misal 5 detik) menjadi TTFT saja (misal 400 milidetik).
2. **Context Window Optimization**: 
   - Hindari memasukkan seluruh riwayat chat tanpa batas. Terapkan strategi *Sliding Window with Summarization*: pertahankan 5 putaran dialog terakhir secara utuh, dan rangkum dialog sebelumnya menjadi satu ringkasan padat.
3. **FinOps & Hard Quotas**:
   - Berikan setiap unit bisnis, tim, atau pengguna *API Key* unik dengan batas pengeluaran bulanan (*hard budget limit*).
   - Simpan metrik penggunaan token secara *real-time* di TSDB (*Time Series Database*) seperti Prometheus untuk melacak *burn rate*.
4. **Structured Output Enforcement Tanpa Re-prompting**: Gunakan fitur *Constrained Decoding* bawaan (seperti *JSON Mode*, *Grammar-guided decoding*) daripada meminta model mengoreksi outputnya berulang kali melalui re-prompting yang memboroskan token.

---

## 10. Hands-on Lab Exercise: Menguji Latensi & Reduksi Biaya Gateway

### Skenario Lab
Anda diminta untuk menguji performa AI Proxy Gateway lokal yang telah dibangun, memverifikasi efektivitas *Semantic Caching*, dan mengamati perilaku *Model Cascading* ketika menangani kueri dengan kompleksitas berbeda.

### Prasyarat
- Python 3.10+ terinstal.
- Library terpasang: `pip install fastapi uvicorn httpx pydantic`

### Langkah-langkah Praktikum

#### Langkah 1: Jalankan AI Proxy Server
Simpan kode produksi di Bagian 6 ke dalam berkas bernama `gateway.py`, lalu jalankan server:
```bash
python gateway.py
```
*Pastikan log terminal menunjukkan bahwa server aktif di `http://0.0.0.0:8000`.*

#### Langkah 2: Uji Kueri Sederhana (Fast Tier Path)
Buka terminal baru dan kirim kueri klasifikasi sederhana:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_dev_101",
    "prompt": "Klasifikasikan sentimen berikut: Saya sangat puas dengan pelayanan hari ini.",
    "temperature": 0.0
  }'
```
*Amati response:* Model yang digunakan adalah `gpt-4o-mini` (Fast Tier), biaya minimal, dan `cached: false`.

#### Langkah 3: Uji Semantic Caching (Cache Hit Verification)
Kirim kembali kueri dengan teks yang identik untuk menguji cache:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_dev_101",
    "prompt": "Klasifikasikan sentimen berikut: Saya sangat puas dengan pelayanan hari ini.",
    "temperature": 0.0
  }'
```
*Amati response:* Model yang digunakan berubah menjadi `semantic-cache-v1`, `cached: true`, latensi turun drastis ke angka satuan milidetik, dan `cost_usd: 0.0`.

#### Langkah 4: Uji Model Cascading (Deep Tier Activation)
Kirim kueri kompleks yang memicu kata kunci arsitektur atau penalaran mendalam:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_dev_102",
    "prompt": "Tolong buatkan architecture perancangan sistem backend distributed microservices dengan toleransi kesalahan tingkat tinggi step-by-step.",
    "temperature": 0.0
  }'
```
*Amati response:* Sistem secara otomatis mengidentifikasi kompleksitas tugas dan mengalihkan eksekusi ke model tier tinggi (`claude-3-5-sonnet`), memvalidasi bahwa modul evaluasi heuristik berjalan sesuai spesifikasi.

#### Langkah 5: Uji Proteksi Rate Limiting (Burst Test)
Jalankan loop cepat untuk memicu pembatasan kuota:
```bash
for i in {1..25}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"user_id": "spammer_user", "prompt": "Ping", "temperature": 0.0}'
done
```
*Amati output:* Pada permintaan awal, terminal akan merespons status `200`. Setelah kapasitas token bucket (20 token) habis, gateway akan merespons dengan HTTP status `429 (Too Many Requests)`, melindungi upstream model dari ancaman *resource exhaustion*.