# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur AI End-to-End** berbasis *Event-Driven* dan *Streaming Pipeline* (Server-Sent Events / SSE) yang tahan terhadap *rate-limiting* dan kegagalan pihak ketiga (*provider downtime*).
2. **Mengurangi Latensi Inferensi Sistem** dengan mengoptimalkan metrik *Time to First Token* (TTFT) dan *Time Per Output Token* (TPOT) menggunakan teknik *semantic caching*, *speculative execution*, dan *streaming chunk parsers*.
3. **Menerapkan Kontrak Data Deterministik** (*Deterministic Output Validation*) menggunakan Pydantic V2 dan mekanisme *grammar-based decoding* / *JSON Schema repair* untuk menjamin integrasi sistem downstream tanpa error deserialisasi.
4. **Membangun Sistem Multi-Provider Fallback & Dynamic Routing** yang mengatur *traffic* LLM secara adaptif berdasarkan *cost*, *context-window availability*, *latency budget*, dan *error rate* secara terotomatisasi.
5. **Menerapkan Standar Observabilitas GenAI Enterprise** dengan melacak *token-level latency*, metrik biaya (*cost attribution* per *tenant*), serta jejak terdistribusi (*distributed tracing*) menggunakan OpenTelemetry semantic conventions untuk GenAI.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Pemrograman Python Tingkat Lanjut**: Pemahaman mendalam tentang *Asyncio*, *Generators*, *Context Managers*, dan konkurensi berbasis *event-loop*.
* **Dasar LLM API**: Penggunaan REST/SDK dasar OpenAI/Anthropic (Chat Completions, role definition, parameter `temperature`, `top_p`).
* **Sistem Jaringan & Protokol HTTP**: HTTP/1.1 vs HTTP/2, streaming chunking, WebSocket, dan Server-Sent Events (SSE).
* **Basis Data Vektor & Caching**: Pengoperasian dasar Redis dan konsep *cosine similarity* pada vector embeddings.
* **Format & Validasi Data**: JSON Schema, Pydantic V2 dasar, dan manipulasi *Abstract Syntax Tree* (AST) sederhana.

---

### 3. Concept & Internal Architecture

Membangun produk AI pada skala enterprise membutuhkan pergeseran paradigma dari *request-response* monolitik tradisional ke arsitektur *asynchronous, streaming-first, and resilient proxy*.

```
+---------------------------------------------------------------------------------------+
|                               ENTERPRISE AI GATEWAY                                  |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   +------------------+      +-------------------+      +--------------------------+   |
|   |  Client Ingress  | ---> |   Rate Limiter    | ---> |     Semantic Cache       |   |
|   |  (HTTP/2 SSE)    |      |  (Token Bucket)   |      |   (Redis + Embeddings)   |   |
|   +------------------+      +-------------------+      +--------------------------+   |
|                                                                      | (Cache Miss)   |
|                                                                      v                |
|   +------------------+      +-------------------+      +--------------------------+   |
|   | Downstream Output| <--- | Guardrails Engine | <--- | Dynamic Routing Core     |   |
|   | Repair & Deser   |      | (Toxicity, PII)   |      | (Latency/Cost Optimizer) |   |
|   +------------------+      +-------------------+      +--------------------------+   |
|                                                                      |                |
|                                              +-----------------------+----------------+
|                                              |                       |
|                                              v                       v
|                                    +-------------------+   +--------------------+
|                                    | Provider Primary  |   | Provider Secondary |
|                                    | (e.g. OpenAI)     |   | (e.g. Anthropic)   |
|                                    +-------------------+   +--------------------+
+---------------------------------------------------------------------------------------+
```

#### A. Dekonstruksi Latensi LLM: TTFT vs TPOT
Dalam produk AI real-time, latensi total ($L_{total}$) dirumuskan sebagai:

$$L_{total} = TTFT + (TPOT \times N_{tokens})$$

* **Time To First Token (TTFT)**: Waktu yang dibutuhkan dari saat request dikirim hingga token pertama diterima oleh klien. Bergantung pada:
  * Waktu antrean provider (*queue time*).
  * Pemrosesan konteks awal (*prefill phase*) yang memproses seluruh input prompt menggunakan parallel computing matrix.
  * Efisiensi *Key-Value (KV) Caching* pada sisi infrastruktur inferensi provider.
* **Time Per Output Token (TPOT)**: Waktu yang dihabiskan untuk menghasilkan setiap token secara autoregresif (*decoding phase*). Bersifat serial: token $t$ harus selesai diproses sebelum token $t+1$ dapat diprediksi.

Untuk merancang UI yang responsif, sistem enterprise harus mengoptimalkan TTFT menggunakan arsitektur *streaming* murni, sehingga pengguna mendapatkan persepsi instan (*perceived zero-latency*), sementara validasi data dilakukan secara *on-the-fly*.

#### B. Dynamic Routing dan Fallback Cascade
Enterprise tidak boleh bergantung pada satu *upstream provider*. Ketika terjadi lonjakan eror (HTTP 429 *Too Many Requests*, HTTP 503 *Service Unavailable*), sistem harus melakukan degradasi secara terkontrol (*graceful degradation*) melalui *routing cascade*:

1. **Tier-1 (High-Performance Engine)**: GPT-4o / Claude 3.5 Sonnet untuk tugas penalaran kompleks.
2. **Tier-2 (Fast & Cost-Optimized Fallback)**: Mistral Large / GPT-4o-mini / Llama 3.3 70B (self-hosted vLLM).
3. **Tier-3 (Degraded Rule-Based/Cached Engine)**: Hasil cache semantik atau respons deterministik yang sudah disiapkan.

#### C. Semantic Caching Engine
Alih-alih melakukan *exact-string match* caching (yang gagal mendeteksi parafrase), *Semantic Cache* menggunakan *vector distance threshold*.
1. Masukan prompt diubah menjadi embedding vector $V_q$.
2. Cari $K$-nearest neighbor pada Redis Vector Store dengan batasan *cosine distance*:
   
   $$\text{similarity} = \frac{V_q \cdot V_{cache}}{\|V_q\| \|V_{cache}\|}$$

3. Jika $\text{similarity} \ge 0.95$ (ambang batas ketat), kembalikan respons tersimpan secara instan (<20ms), memotong biaya token hingga 100% dan menurunkan latensi drastis.

#### D. Validasi Output Deterministik & Partial Streaming JSON Parser
Ketika LLM digunakan sebagai subsistem backend, ia harus menghasilkan data terstruktur (misal: JSON). Namun, mekanisme streaming menghasilkan pecahan string (*chunks*). Arsitektur produksi menggunakan parser berbasis status (*finite-state parser*) yang mampu mereparasi JSON parsial saat streaming berlangsung, memvalidasi schema menggunakan AST validation, dan menolak token halusinasi sebelum dikonsumsi oleh subsistem downstream.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Prototipe / POC) | Arsitektur Enterprise AI (Produksi) |
| :--- | :--- | :--- |
| **Integrasi API** | Direct call SDK synchronous (`openai.ChatCompletion.create`) | Asynchronous, resilient proxy gateway dengan non-blocking I/O. |
| **Manajemen Kegagalan** | Retry loop sederhana (berisiko *thundering herd*). | Circuit breaker pattern + Adaptive exponential backoff + Jitter + Dynamic Fallback. |
| **Output Data** | Mengandalkan prompt: "Keluarkan dalam format JSON". | JSON Schema Enforcement murni via grammar constraints, AST schema repair, dan validasi Pydantic V2. |
| **Penanganan Latensi** | Klien menunggu hingga token selesai dihasilkan secara penuh (blocking). | Streaming penuh berbasis SSE dengan optimasi TTFT dan parsial parse token. |
| **Efisiensi Biaya** | Setiap request identik memicu kalkulasi inferensi baru. | Semantic cache berbasis kemiripan vektor + Prompt token compression. |
| **Visibilitas** | Print statement log / standard file logger. | OpenTelemetry Tracing, token usage attribution per tenant, metrik TTFT/TPOT real-time. |

---

### 5. How (Workflow Detail)

Alur eksekusi request pada Gateway AI Produksi berjalan sebagai berikut:

```
[Client]                [Gateway Core]           [Semantic Cache]       [LLM Providers]
   |                           |                        |                      |
   |--- 1. POST /v1/chat ----->|                        |                      |
   |    (Prompt + Schema)      |--- 2. Generate Hash -->|                      |
   |                           |    & Query Vector      |                      |
   |                           |                        |                      |
   |                           |<-- 3. Cache Miss ------|                      |
   |                           |                                               |
   |                           |--- 4. Check Health & Select Route ----------->|
   |                           |    (Circuit Breakers: Healthy)                |
   |                           |                                               |
   |                           |--- 5. Stream Request (SSE) ------------------>|
   |                           |                                               |
   |<-- 6. SSE Headers (200) --|                                               |
   |                           |<-- 7. First Token Chunk ----------------------|
   |<-- 8. Stream Token (TTFT)-|                                               |
   |                           |<-- 9. Subsequent Chunks ----------------------|
   |<-- 10. Stream Tokens -----|                                               |
   |                           |                                               |
   |                           |<-- 11. Stream Completed ----------------------|
   |                           |                                               |
   |                           |--- 12. Validate Structure (Pydantic)          |
   |                           |--- 13. Save to Semantic Cache --------------->|
   |                           |--- 14. Emit Telemetry (OTel)                  |
   |<-- 15. [DONE] ------------|                                               |
```

1. **Ingress & Authentication**: Klien mengirimkan request via HTTP/2 streaming endpoint bersama payload prompt dan skema data yang diinginkan.
2. **Context Enrichment & Sanitization**: Sistem memvalidasi kuota tenant, memfilter PII (*Personally Identifiable Information*), dan menyusun prompt final.
3. **Semantic Cache Lookup**: Gateway menghitung embedding prompt dan mengecek *vector similarity index*. Jika hit, respons dialirkan langsung dari cache dalam hitungan milidetik.
4. **Adaptive Route Selection**: Jika miss, sistem memeriksa status *Circuit Breaker* tiap provider, lalu memilih model terbaik berdasarkan bobot latensi, biaya, dan ketersediaan kuota.
5. **Upstream Streaming Execution**: Gateway membuka koneksi streaming asinkron ke provider yang dipilih.
6. **Token Interception, Repair, & Yield**: Gateway mem-parse *delta stream*, mencatat metrik TTFT saat chunk pertama tiba, memvalidasi integritas parsial, dan meneruskannya ke klien via SSE.
7. **Post-Processing & Telemetry**: Setelah token selesai ([DONE]), gateway memverifikasi output akhir terhadap skema Pydantic, menyimpan pasangan prompt-respons ke Semantic Cache, dan mencatat total latensi, TPOT, serta token cost ke sistem observabilitas.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima (*Haute Cuisine*)
* **Pendekatan Naif**: Pelayan mengambil pesanan, berjalan ke dapur, menunggu koki memasak hidangan 5-course dari awal sampai selesai selama 45 menit tanpa memberi kabar, baru membawa semua makanan sekaligus ke meja. Jika kompor gas koki rusak, pelanggan langsung dibiarkan lapar tanpa solusi.
* **Arsitektur Enterprise**:
  * **Semantic Cache (Garderobe/Mise en place)**: Pelayan mengecek apakah makanan pembuka standar yang identik sudah siap saji di konter pendingin. Jika ada, sajikan dalam 10 detik.
  * **Streaming (Tasting Course per Spoon)**: Koki langsung menyajikan sendok hidangan pertama begitu siap (TTFT instan), menjaga pelanggan tetap terlibat sambil hidangan berikutnya dimasak secara serial (TPOT).
  * **Circuit Breaker & Fallback (Kompor Cadangan & Chef Pengganti)**: Jika kompor gas utama (OpenAI) padam, sistem dapur otomatis mengalihkan pesanan ke kompor listrik cadangan (Anthropic) tanpa pelanggan menyadari adanya gangguan teknis.
  * **Schema Repair (Quality Control Inspector)**: Sebelum makanan ditaruh di nampan saji, inspektur memastikan bentuk plating presisi sesuai standar menu. Bila ada tetesan saus yang melenceng, langsung dibersihkan sebelum mencapai meja.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Resilient Multi-Provider Fallback Routing
Contoh implementasi dasar mekanisme *fallback* asinkron menggunakan abstraksi Python modern:

```python
import asyncio
from typing import AsyncGenerator
import httpx

class SimpleLLMFallback:
    def __init__(self):
        # Konfigurasi endpoint mock/real
        self.providers = [
            {"name": "primary-provider", "url": "https://api.openai.com/v1/chat/completions", "key": "sk-mock-1"},
            {"name": "secondary-provider", "url": "https://api.anthropic.com/v1/messages", "key": "sk-mock-2"}
        ]

    async def _call_provider(self, client: httpx.AsyncClient, provider: dict, prompt: str) -> str:
        # Simulasi kegagalan untuk mendemonstrasikan fallback
        if provider["name"] == "primary-provider":
            await asyncio.sleep(0.1)
            raise httpx.HTTPStatusError("503 Service Unavailable", request=None, response=httpx.Response(503))
        
        # Provider kedua sukses
        await asyncio.sleep(0.05)
        return f"Respons sukses dari {provider['name']} untuk: {prompt}"

    async def execute_with_fallback(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=2.0) as client:
            last_error = None
            for prov in self.providers:
                try:
                    return await self._call_provider(client, prov, prompt)
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    last_error = exc
                    continue
            raise RuntimeError(f"Semua provider gagal. Eror terakhir: {last_error}")

# Eksekusi runner
if __name__ == "__main__":
    runner = SimpleLLMFallback()
    result = asyncio.run(runner.execute_with_fallback("Analisis data finansial ini."))
    print(result)
```

#### B. Practical Example: Enterprise Streaming AI Engine dengan Semantic Caching & Output Validation

Implementasi tingkat produksi lengkap dengan Server-Sent Events (SSE), Pydantic parsing, dan in-memory vector cache simulation:

```python
from __future__ import annotations

import asyncio
import json
import math
import time
from typing import AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------
# 1. DATA CONTRACTS (PYDANTIC V2)
# ---------------------------------------------------------
class FinancialMetric(BaseModel):
    metric_name: str = Field(description="Nama metrik keuangan")
    value: float = Field(description="Nilai kuantitatif metrik")
    trend: str = Field(description="UP, DOWN, atau NEUTRAL")

class FinancialAnalysisResponse(BaseModel):
    company_code: str
    sentiment: str
    metrics: List[FinancialMetric]
    executive_summary: str

# ---------------------------------------------------------
# 2. IN-MEMORY SEMANTIC CACHE SIMULATOR
# ---------------------------------------------------------
class SemanticVectorCache:
    def __init__(self, similarity_threshold: float = 0.92):
        self.similarity_threshold = similarity_threshold
        # Penyimpanan struktur: List of tuples (embedding_vector, payload_dict)
        self.storage: List[tuple[List[float], dict]] = []

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    async def get(self, query_vector: List[float]) -> Optional[dict]:
        for cached_vector, payload in self.storage:
            similarity = self._cosine_similarity(query_vector, cached_vector)
            if similarity >= self.similarity_threshold:
                return payload
        return None

    async def set(self, query_vector: List[float], payload: dict) -> None:
        self.storage.append((query_vector, payload))

# ---------------------------------------------------------
# 3. ENTERPRISE GATEWAY CORE ENGINE
# ---------------------------------------------------------
class ProductionAIGateway:
    def __init__(self, cache: SemanticVectorCache):
        self.cache = cache
        self.circuit_open = False
        self.consecutive_failures = 0
        self.failure_threshold = 3

    async def _mock_embedding(self, text: str) -> List[float]:
        """Menghasilkan embedding deterministik mock untuk representasi string."""
        await asyncio.sleep(0.01)
        length = len(text)
        return [float((hash(text + str(i)) % 1000) / 1000.0) for i in range(8)]

    async def _simulate_provider_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Simulasi streaming LLM upstream (SSE raw text)."""
        raw_json_chunks = [
            '{"company_code": "BBCA",',
            ' "sentiment": "BULLISH",',
            ' "metrics": [',
            '   {"metric_name": "Net Profit Margin", "value": 31.5, "trend": "UP"},',
            '   {"metric_name": "NPL Gross", "value": 1.2, "trend": "DOWN"}',
            ' ],',
            ' "executive_summary": "Kinerja kuartal ketiga menunjukkan efisiensi operasional tinggi."}'
        ]

        if self.circuit_open:
            raise ConnectionError("Circuit Breaker OPEN: Provider hulu sedang tidak stabil.")

        for chunk in raw_json_chunks:
            await asyncio.sleep(0.05)  # Simulasi TPOT (50ms per chunk)
            yield chunk

    async def execute_stream(
        self, prompt: str
    ) -> AsyncGenerator[Dict[str, str], None]:
        request_start = time.perf_counter()
        query_vector = await self._mock_embedding(prompt)

        # 1. Cek Semantic Cache
        cached_result = await self.cache.get(query_vector)
        if cached_result:
            yield {
                "event": "cache_hit",
                "data": json.dumps(cached_result),
                "ttft": "0.001"
            }
            return

        # 2. Inisialisasi Eksekusi Streaming
        accumulated_chunks: List[str] = []
        is_first_token = True
        ttft = 0.0

        try:
            stream = self._simulate_provider_stream(prompt)
            async for token_chunk in stream:
                if is_first_token:
                    ttft = time.perf_counter() - request_start
                    is_first_token = False
                    yield {"event": "metrics", "ttft": f"{ttft:.4f}"}

                accumulated_chunks.append(token_chunk)
                yield {"event": "token", "chunk": token_chunk}

            # 3. Post-Stream Verification & Deserialization Check
            full_response_raw = "".join(accumulated_chunks)
            parsed_data = json.loads(full_response_raw)
            validated_output = FinancialAnalysisResponse.model_validate(parsed_data)

            # Simpan hasil tervalidasi ke Semantic Cache
            await self.cache.set(query_vector, validated_output.model_dump())

            # Reset kegagalan pada keberhasilan eksekusi
            self.consecutive_failures = 0

            tpot = (time.perf_counter() - request_start - ttft) / max(len(accumulated_chunks), 1)
            yield {"event": "metrics", "tpot": f"{tpot:.4f}"}
            yield {"event": "done", "status": "COMPLETED"}

        except (ConnectionError, Exception) as err:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_threshold:
                self.circuit_open = True
            
            yield {"event": "error", "message": f"Pipeline failure: {str(err)}"}
            return

# ---------------------------------------------------------
# 4. RUNNER
# ---------------------------------------------------------
async def main():
    cache_store = SemanticVectorCache(similarity_threshold=0.95)
    gateway = ProductionAIGateway(cache=cache_store)

    prompt_test = "Analisis kinerja keuangan emiten Bank Central Asia terbaru"
    
    print("=== Eksekusi Request 1 (Cache Miss - Pipeline Stream Penuh) ===")
    async for message in gateway.execute_stream(prompt_test):
        print(f"[{message.get('event')}] -> {message}")

    print("\n=== Eksekusi Request 2 (Cache Hit - Zero Latency Path) ===")
    async for message in gateway.execute_stream(prompt_test):
        print(f"[{message.get('event')}] -> {message}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Customer Support Agentic Platform - PT FinTech Solusi Nusantara (10 Juta DAU)

* **Skala & Beban Transaksi**: 1.200 permintaan per detik (*Peak QPS*), melayani komplain transaksi perbankan dan *dispute handling*.
* **Permasalahan Utama**:
  1. *Provider Rate Limits*: Lonjakan request di awal bulan membuat OpenAI API melempar error 429 beruntun pada 14% request.
  2. *Cost Explosion*: Biaya inferensi tembus $180,000/bulan akibat pengulangan pertanyaan identik (misal: "Bagaimana cara cetak mutasi rekening?").
  3. *Unstructured Hallucination*: 3.2% respons LLM gagal diproses sistem Core Banking karena format JSON terpotong di tengah stream.

#### Solusi Rekayasa yang Diimplementasikan:
1. **Tiered Semantic Caching Layer**:
   * Redis Enterprise Cluster disebar pada 3 zona ketersediaan dengan ekstensi RediSearch Vector Similarity.
   * Pertanyaan dengan kemiripan vektor di atas 0.94 langsung dilayani tanpa hit ke LLM provider.
   * **Hasil**: 42% dari total traffic berhasil ditangani langsung oleh cache, menghemat biaya $75,600 per bulan dan mengurangi latensi p99 dari 4.2 detik menjadi 35 milidetik.

2. **Adaptive Dynamic Failover Router (LangGraph + Envoy Proxy)**:
   * Dibangun state-machine berbasis Envoy yang mengevaluasi performa hulu secara berkala.
   * Jalur Utama: Claude 3.5 Sonnet via AWS Bedrock (Target SLA: 99.9%).
   * Jalur Sekunder (Fallback jika error rate > 2% dalam window 1 menit): vLLM cluster lokal yang menjalankan Llama 3.3 70B pada node GPU Kubernetes internal.

3. **Deterministic Stream Repair**:
   * Menggunakan pipeline *streaming JSON parser* berbasis C-extension yang memvalidasi *JSON syntax* parsial secara streaming.
   * Apabila model memotong tanda kurung penutup saat batas *max_tokens* tercapai, sistem melakukan perbaikan AST sintaks otomatis (*auto-closing bracket repair*) sebelum menyerahkan payload ke layer perbankan.

---

### 9. Trade-offs

Setiap keputusan arsitektur pada AI Product Platform membawa konsekuensi teknis nyata:

| Pendekatan Rekayasa | Keuntungan (+)| Kerugian & Biaya (-) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Semantic Caching Agresif** (Threshold $\le 0.90$) | Menghemat biaya token hingga 60-80%; Latensi super cepat (<50ms). | Risiko *false-positive match* tinggi; Klien dapat menerima jawaban konteks lama yang tidak presisi. | FAQ, pencarian pengetahuan statis, panduan pengguna umum. |
| **Grammar-Based Constrained Decoding** (e.g. Outlines, Guidance) | Output dijamin 100% mematuhi regex/JSON Schema secara matematis. | Menambah beban inferensi GPU (penurunan throughput token/detik hingga 15-30%); Membutuhkan akses low-level logits (sulit di API tertutup). | Integrasi core-banking, eksekusi SQL mutation, parsing data medis kritis. |
| **Multi-Provider Fallback Cascade** | Ketersediaan sistem mencapai 99.99%; Mengeliminasi *single point of failure* vendor. | Variasi gaya respons (sintaks dan penalaran berbeda antar model); Kompleksitas pemeliharaan *prompt parity*. | Layanan publik bervolume tinggi, operasional misi kritis, SLA berbayar. |
| **Client-Side SSE Streaming** | TTFT rendah; Pengalaman pengguna sangat responsif. | Penanganan koneksi stateful pada proxy/load balancer sulit; Membutuhkan penanganan *backpressure* jaringan yang ketat. | Antarmuka obrolan interaktif, aplikasi analitik *real-time*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan Backpressure pada SSE Connection
* **Gejala**: Klien mobile dengan koneksi 3G lambat menyebabkan memory leak masif pada instance API Gateway.
* **Akar Masalah**: Gateway membaca token dari provider sangat cepat, namun gagal menerapkan jeda kirim (*backpressure*) ke buffer TCP klien yang tersendat.
* **Solusi**: Gunakan stream generator berbasis `asyncio.Queue` dengan batasan kapasitas (*bounded queue*). Jika buffer klien penuh, hentikan pembacaan upstream sementara:
  ```python
  queue = asyncio.Queue(maxsize=100) # Batasi buffer token
  ```

#### 2. Cache Poisoning pada Semantic Cache
* **Gejala**: Model memberikan respons salah secara konsisten untuk sekumpulan prompt yang mirip.
* **Akar Masalah**: Gateway meng-cache respons dari model tanpa memvalidasi apakah respons tersebut mengandung halusinasi, eror, atau penolakan (*guardrail refusal*).
* **Solusi**: Jangan pernah menyimpan respons ke cache sebelum lolos validasi status (HTTP 200, Pydantic Schema tervalidasi, dan nilai guardrail toxicity = 0).

#### 3. Token Desynchronization pada Retries
* **Gejala**: Menjalankan *retry* otomatis saat request hulu timeout parsial, menyebabkan transaksi di sisi LLM terduplikasi dan tagihan melonjak ganda.
* **Akar Masalah**: Gateway me-retry request yang sebenarnya sedang diproses oleh provider.
* **Solusi**: Terapkan mekanisme Idempotency Key unik berbasis hash dari payload dan tenant ID pada header request (`Idempotency-Key: hash(payload)`).

#### 4. JSON Schema Drift antar Provider Berbeda
* **Gejala**: Prompt berfungsi sempurna pada GPT-4o, tetapi gagal total (*invalid syntax*) saat beralih otomatis ke Anthropic Claude via Fallback Router.
* **Akar Masalah**: Tiap provider memiliki interpretasi berbeda terhadap format *tool call* dan pemanggilan fungsi.
* **Solusi**: Normalisasikan skema ke standar universal JSON Schema draft-07 sebelum diteruskan ke SDK masing-masing provider.

---

### 11. Best Practices (Production Checklist)

#### Security & Compliance
- [ ] PII Sanitization terpasang di ingress (menghapus NIK, No Kartu Kredit, Email sensitif sebelum prompt dikirim ke upstream LLM).
- [ ] Rate limiting bertingkat: *Token Bucket* per Tenant ID dan per User IP address.
- [ ] Output filtering mendeteksi Prompt Injection Reflection (mencegah *jailbreak leak* kembali ke user).

#### Performance & Latency
- [ ] Protokol HTTP/2 diaktifkan secara penuh pada Ingress Controller untuk menghindari *head-of-line blocking* pada ratusan koneksi streaming SSE simultan.
- [ ] Connection Pooling upstream LLM di-keep-alive untuk memangkas handshake TLS (~150ms penghematan per koneksi).
- [ ] Ukuran chunk embeddings dinormalisasi sebelum pencarian *cosine similarity* untuk menjaga konsistensi skoring cache.

#### Reliability & Fallbacks
- [ ] Circuit breaker terpasang dengan konfigurasi: Minimal 5 sampel request, error threshold 50%, cooldown recovery 30 detik.
- [ ] Fallback cascaded minimal 2 tingkat: Tier 1 (Cloud Proprietary) -> Tier 2 (Open Weights / Secondary Cloud).
- [ ] Timeout agresif: Batasi TTFT upstream maksimal 3.5 detik; jika terlampaui, langsung putuskan koneksi dan alihkan ke model cadangan.

#### Observability & Cost Tracking
- [ ] Log mencatat `prompt_tokens`, `completion_tokens`, `total_tokens`, `ttft_ms`, `tpot_ms` untuk tiap session.
- [ ] Integrasi OpenTelemetry Span attributes mengikuti standar semantik OpenTelemetry GenAI: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.completion_tokens`.

---

### 12. Hands-on Practice

Buat dan susun direktori kerja berikut untuk mengimplementasikan Gateway Produksi mini:

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

#### Langkah 1: Persiapan Dependensi
Simpan berkas berikut sebagai `requirements.txt`:
```
fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.6.0
httpx>=0.27.0
numpy>=1.26.0
```
Instalasi dependensi:
```bash
pip install -r requirements.txt
```

#### Langkah 2: Implementasi Server Streaming Gateway
Buat file `hands-on/m02/src/main.py`:
```python
import asyncio
import json
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Enterprise AI Gateway M02")

class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=5)
    tenant_id: str = Field(..., example="corp-alpha")

class ExtractionResult(BaseModel):
    ticket_id: str
    urgency: str
    category: str

async def mock_llm_stream(prompt: str):
    """Simulasi upstream LLM yang memancarkan delta JSON token-by-token."""
    payload_tokens = [
        '{"ticket_id":', ' "TCK-9902",',
        ' "urgency":', ' "HIGH",',
        ' "category":', ' "PAYMENT_GATEWAY_TIMEOUT"}'
    ]
    for token in payload_tokens:
        await asyncio.sleep(0.04) # 40ms token generation latency
        yield token

async def sse_event_generator(prompt: str):
    start_time = time.perf_counter()
    first_token_emitted = False
    full_text = []

    try:
        # Kirim event inisialisasi
        yield f"event: ping\ndata: {json.dumps({'status': 'connected'})}\n\n"

        async for token in mock_llm_stream(prompt):
            if not first_token_emitted:
                ttft = time.perf_counter() - start_time
                yield f"event: metric\ndata: {json.dumps({'metric': 'TTFT', 'value_ms': ttft * 1000})}\n\n"
                first_token_emitted = True

            full_text.append(token)
            yield f"event: token\ndata: {json.dumps({'delta': token})}\n\n"

        # Validasi struktur data akhir menggunakan Pydantic
        raw_result = "".join(full_text)
        validated = ExtractionResult.model_validate_json(raw_result)

        yield f"event: validated\ndata: {validated.model_dump_json()}\n\n"
        yield f"event: done\ndata: [DONE]\n\n"

    except Exception as err:
        yield f"event: error\ndata: {json.dumps({'error': str(err)})}\n\n"

@app.post("/v1/agent/extract")
async def extract_ticket_data(req: QueryRequest):
    return StreamingResponse(
        sse_event_generator(req.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Mencegah buffering pada Nginx proxy
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

#### Langkah 3: Eksekusi dan Verifikasi Terminal
Jalankan server:
```bash
python src/main.py
```
Buka terminal kedua dan jalankan curl untuk memverifikasi streaming SSE:
```bash
curl -N -X POST http://localhost:8000/v1/agent/extract \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Sistem saya mengalami timeout saat otorisasi payment", "tenant_id": "corp-alpha"}'
```

Pastikan Anda melihat event `metric` (TTFT), serangkaian event `token`, event `validated`, dan penutup `done` mengalir secara serial tanpa terpotong.

---

### 13. Exercise

#### Level 1 - Easy
* **Deskripsi**: Modifikasi kode praktikum di `hands-on/m02/src/main.py` untuk menambahkan kalkulasi metrik `TPOT` (Time Per Output Token).
* **Kriteria Keberhasilan**: Endpoint harus mengirimkan event SSE tambahan bernama `metric` dengan payload `{"metric": "TPOT", "avg_ms_per_token": ...}` tepat sebelum event `done`.

#### Level 2 - Medium
* **Deskripsi**: Tambahkan middleware *Sliding Window Rate Limiter* dalam aplikasi FastAPI yang membatasi tiap `tenant_id` maksimal hanya boleh melakukan 5 request per detik. Jika melebihi kuota, lemparkan HTTP status 429 *Too Many Requests* dengan header `Retry-After: 1`.
* **Kriteria Keberhasilan**: Eksekusi stress-test sederhana dengan script client asinkron membuktikan request ke-6 pada detik yang sama ditolak secara presisi.

#### Level 3 - Hard
* **Deskripsi**: Bangun mekanisme *Deterministic Fallback Switcher* pada kode praktikum. Buat provider primer yang sengaja melempar eksepsi error (misal 50% probability HTTP 500). Ketika error terjadi di tengah-tengah streaming (sebelum token selesai), sistem harus memancarkan event `event: fallback_triggered`, memutus stream dari provider primer secara bersih, beralih ke provider sekunder, dan menyelesaikan parsing Pydantic hingga tuntas tanpa merusak format event yang diterima klien.
* **Kriteria Keberhasilan**: Sistem berhasil mengalirkan fallback secara transparan dan objek Pydantic akhir tetap tervalidasi valid.

---

### 14. Challenge

Rancang arsitektur komprehensif (dokumen arsitektur teknis dan simulasi kode inti) untuk sistem:

**"Multi-Tenant Distributed GenAI Router dengan Zero Single-Point-of-Failure"**

**Batasan Masalah Teknis**:
1. Sistem harus menangani 3 LLM Upstream: Provider A (Latensi Rendah, SLA 99%), Provider B (Latensi Tinggi, SLA 99.95%), dan Provider C (Lokal on-premise, kapasitas terbatas).
2. Sistem memiliki aturan alokasi dinamis (*Dynamic Routing Rule*):
   * Tenant Tier-Enterprise: Harus memprioritaskan Provider A untuk mengejar target latensi TTFT < 300ms. Jika Provider A down (terdeteksi via Circuit Breaker State OPEN), otomatis dialihkan ke Provider B.
   * Tenant Tier-Free: Wajib dialihkan ke Provider C. Jika Provider C antreannya penuh (*overloaded*), batalkan request secara anggun tanpa mengorbankan kapasitas Tenant Enterprise.
3. Klien mewajibkan respons terenkripsi penuh saat transit, validasi token anggaran real-time (jika token tenant habis di tengah eksekusi, hentikan streaming seketika), dan simpan jejak trace OpenTelemetry secara terisolasi.

Tantangan ini harus diselesaikan tanpa library third-party vendor berbayar (murni memanfaatkan Python asyncio, FastAPI, Redis, dan standard library).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara metrik TTFT (*Time to First Token*) dan TPOT (*Time Per Output Token*)?
2. Mengapa arsitektur Server-Sent Events (SSE) umumnya lebih disukai dibanding WebSocket untuk pipeline obrolan berbasis LLM?
3. Sebutkan satu keuntungan dan satu kelemahan validasi format JSON LLM menggunakan Pydantic V2 pada aplikasi streaming!
4. Apa fungsi penambahan nilai *Jitter* pada algoritma *Exponential Backoff* saat menangani *rate limit* (HTTP 429)?
5. Bagaimana cara kerja *Cosine Similarity* dalam konteks pencarian di dalam *Semantic Vector Cache*?

#### B. Pertanyaan Intermediate
6. Mengapa mekanisme JSON parsing standar (`json.loads()`) dipastikan gagal jika diterapkan langsung pada setiap chunk *streaming* parsial dari LLM? Bagaimana cara mengatasinya?
7. Jelaskan bagaimana *Circuit Breaker Pattern* mencegah fenomena *Cascading Failure* pada downstream service ketika satu LLM provider mengalami *outage* global!
8. Apa yang dimaksud dengan *KV Cache* pada infrastruktur inferensi model autoregresif, dan bagaimana KV Cache secara langsung memengaruhi nilai TTFT saat prompt yang dikirim sangat panjang?
9. Bagaimana strategi menangani *connection drop* dari klien di tengah-tengah streaming agar token inferensi dari LLM provider tidak terus berjalan dan membuang biaya komputasi sia-sia?
10. Sebutkan parameter apa saja yang harus dijadikan *Cache Key* pada implementasi *Semantic Cache* agar data antar tenant tidak bocor satu sama lain (*multi-tenant data isolation*)!

#### C. Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada pukul 09:00 pagi, sebuah sistem asisten AI perbankan mengalami lonjakan latensi. Metrik observabilitas menunjukkan rata-rata TTFT melonjak dari 400ms menjadi 6.5 detik, namun TPOT tetap stabil di angka 30ms/token. Apa kemungkinan akar masalah teknis yang terjadi di sisi hulu (*upstream provider*), dan bagaimana solusi mitigasi gateway Anda?
12. **Skenario Kasus 2**: Sebuah platform e-commerce menggunakan model LLM untuk mengekstrak komplain pengguna menjadi JSON. Ditemukan 5% dari output terpotong tepat pada karakter penutup `}` akibat parameter `max_tokens` tercapai, menyebabkan downstream microservice crash saat deserialisasi. Pendekatan perbaikan struktural apa yang harus diimplementasikan tanpa perlu menaikkan batas `max_tokens` ke angka maksimal yang boros biaya?
13. **Skenario Kasus 3**: Audit performa menemukan bahwa *hit rate* dari *Semantic Cache* Anda sangat rendah (hanya 3%), meskipun tim produk mengonfirmasi bahwa 35% pertanyaan pelanggan memiliki maksud dan makna yang persis sama. Ambang batas *cosine similarity* disetel pada angka 0.98. Langkah evaluasi dan tuning apa yang harus dilakukan?

---

### Jawaban Kuis Evaluasi Pemahaman

#### Jawaban Basic
1. **TTFT vs TPOT**: TTFT mengukur durasi dari request dikirim sampai token pertama tiba di klien (dipengaruhi waktu antrean dan *prefill context*). TPOT mengukur kecepatan generasi token berikutnya per unit token secara serial (*decoding phase*).
2. **Kelebihan SSE vs WebSocket**: SSE berjalan di atas protokol standar HTTP unidirectional (server-to-client), lebih ringan (*stateless HTTP infrastructure*), mudah melewati firewall/corporate proxy, dan mendukung auto-reconnect bawaan peramban tanpa overhead koneksi dua arah WebSocket.
3. **Kelebihan & Kelemahan Pydantic Streaming**: 
   * *Keuntungan*: Menjamin tipe data dan integritas skema terverifikasi sebelum masuk ke database downstream.
   * *Kelemahan*: Mengharuskan akumulasi payload lengkap sebelum validasi final dapat dieksekusi, sehingga parsing skema parsial memerlukan parser transisional khusus.
4. **Fungsi Jitter**: Memberikan variasi acak pada jeda waktu tunggu retry untuk mencegah semua worker klien mencoba me-retry koneksi pada waktu yang persis bersamaan (*thundering herd problem*).
5. **Prinsip Cosine Similarity**: Mengukur sudut kosinus antara dua vektor embedding di ruang multi-dimensi. Nilai 1 berarti orientasi arah vektor identik (makna semantik sama persis), sedangkan nilai 0 atau negatif menunjukkan tidak adanya keterkaitan konteks.

#### Jawaban Intermediate
6. **Kegagalan json.loads parsial**: Karena pecahan string token parsial (misal: `{"nama": "Bud`) memiliki sintaks JSON yang belum tuntas (*unclosed string/brackets*), menyebabkan JSONDecodeError. Penanganannya membutuhkan library *streaming JSON parser* (seperti `jiter` atau *partial JSON AST reconstructor*) yang bisa menutup struktur kurung secara dinamis saat parsing berlangsung.
7. **Circuit Breaker Mitigation**: Pola ini memutus sambungan (*State: OPEN*) secara cepat ke provider yang sakit tanpa mengirim traffic baru. Request berikutnya langsung dialihkan ke fallback provider dalam 0 milidetik, mencegah antrean request menumpuk yang dapat menghabiskan connection pool dan mematikan seluruh instance backend.
8. **KV Cache & Pengaruh ke TTFT**: KV Cache menyimpan komputasi tensor *Key* dan *Value* dari prompt sebelumnya agar tidak dihitung ulang. Jika prompt baru memiliki kecocokan *prefix* dengan cache di GPU provider (*prompt caching*), komputasi *prefill* terpangkas signifikan, menghasilkan TTFT yang jauh lebih singkat. Jika cache miss pada prompt yang sangat panjang, TTFT akan melonjak drastis karena GPU harus memproses seluruh token konteks sekaligus.
9. **Mencegah Token Waste saat Klien Terputus**: Gateway backend harus memonitor sinyal pemutusan koneksi klien (misal via event `request.is_disconnected()` di ASGI). Segera setelah klien membatalkan koneksi, gateway harus membatalkan *async task* pembacaan stream dari provider upstream (`stream.aclose()`).
10. **Komposisi Semantic Cache Key Multi-tenant**: Wajib mengombinasikan `Tenant_ID` + `Environment (Staging/Prod)` + `Vector Embedding of Prompt` + `System Prompt Hash`. Hal ini memastikan query yang sama dari Tenant B tidak pernah mengambil data cache dari Tenant A.

#### Jawaban Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    * *Akar Masalah*: TPOT stabil berarti kapasitas inferensi GPU upstream (*decoding phase*) sebenarnya normal. Lonjakan tajam pada TTFT menandakan terjadi bottleneck pada antrean permintaan (*queue saturation*) di sisi provider, atau kegagalan *prefix cache* (KV Cache miss massal) pada prompt pembuka yang sangat besar.
    * *Solusi Mitigasi*: Gateway harus mengaktifkan timeout agresif pada fase TTFT (misal: timeout jika token pertama belum tiba dalam 2 detik). Gateway kemudian mengarahkan traffic secara otomatis via *Dynamic Router* ke provider sekunder yang memiliki beban antrean lebih longgar.
12. **Analisis Skenario 2**:
    * *Solusi Struktural*: Terapkan parser perbaikan sintaks otomatis (*Auto-repair JSON engine*). Ketika streaming terhenti pada batas token, fungsi *sanitizer* mendeteksi tumpukan kurung kurawal/siku yang belum tertutup (`{`, `[`), kemudian menambahkan penutup string `"` dan karakter penutup `]}` secara deterministik. Alternatif arsitektur: Gunakan model dengan fitur *Constrained Grammars/Outlines* yang menjamin token penutup wajib digenerasikan sebelum alokasi token habis.
13. **Analisis Skenario 3**:
    * *Evaluasi & Tuning*: Ambang batas (*similarity threshold*) 0.98 terlalu ketat (*overly strict*); variasi kata kecil seperti perubahan sinonim atau tanda baca dapat menurunkan skor kosinus ke 0.94 - 0.96. 
    * *Tindakan*:
      1. Turunkan ambang batas secara bertahap ke kisaran **0.93 - 0.95**.
      2. Normalisasikan teks input sebelum di-vektorkan: ubah menjadi huruf kecil (*lowercasing*), hapus spasi berlebih, dan bersihkan tanda baca yang tidak relevan.
      3. Amati apakah terjadi peningkatan *hit rate* tanpa memicu respons yang tidak relevan (*false positives*).

---

### 16. Summary

Merancang produk AI skala enterprise menuntut pemisahan tegas antara logika aplikasi bisnis dan infrastruktur eksekusi inferensi model. Ketergantungan langsung pada SDK vendor model adalah pola anti-produksi (*anti-pattern*) yang rapuh terhadap latensi tak terduga, lonjakan biaya, dan kegagalan jaringan.

Pondasi utama Arsitektur Produksi AI Modul ini berakar pada:
1. **Streaming First & Latency Engineering**: Pemahaman mendalam atas pemisahan komponen TTFT dan TPOT serta pemanfaatan SSE memungkinkan perancangan sistem dengan *perceived zero-latency*.
2. **Resilience & Fault Isolation**: Penerapan *Circuit Breaker*, *Dynamic Routing Fallback*, dan *Jittered Exponential Backoff* menjamin ketersediaan sistem hingga taraf 99.99% terlepas dari performa vendor pihak ketiga.
3. **Deterministic Contracts**: Output AI yang bersifat stokastik diikat oleh validasi skema berbasis Pydantic V2 dan reparasi parsial AST JSON stream, melindungi integritas transaksi sistem backend.
4. **Economic Scalability**: Pemanfaatan *Semantic Cache* multitenan secara presisi memotong biaya inferensi secara signifikan sekaligus melayani jutaan pengguna dengan latensi ultra rendah.