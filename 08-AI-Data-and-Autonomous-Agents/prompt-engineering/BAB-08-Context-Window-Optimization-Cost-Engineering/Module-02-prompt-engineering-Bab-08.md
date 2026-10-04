# BAB 08: Context Window Optimization & Cost Engineering
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Context Management Multi-Tier**: Mengintegrasikan *Prompt Caching* (KV-cache provider-level), *Semantic Caching* (vektor), dan *Exact-Match Caching* untuk memangkas *time-to-first-token* (TTFT) hingga $\ge 65\%$ dan biaya inferensi hingga $\ge 70\%$.
2. **Membangun Algoritma Context Compression & Pruning Adaptif**: Mengimplementasikan teknik kompresi berbasis entropi informasi dan *token-budgeting* dinamis (menggunakan pendekatan setara LLMLingua) tanpa mendegradasi performa pemrosesan *downstream task* (retensi akurasi $\ge 98\%$).
3. **Mengoptimalkan Prefix Alignment untuk Provider-Level Caching**: Merekayasa struktur prompt agar sesuai dengan batasan internal *prefix caching* (OpenAI, Anthropic, DeepSeek, vLLM PagedAttention) guna mencegah *cache eviction* yang tidak disengaja.
4. **Mengotomatisasi Cost Engineering Telemetry & Budget Circuit Breaker**: Merancang sistem observabilitas tingkat produksi menggunakan OpenTelemetry dan sistem penegakan anggaran inferensi (*token budget governor*) yang memutus atau mendegradasi query secara *graceful* sebelum melanggar batas SLA biaya.

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib menguasai:
- **Arsitektur Transformer**: Mekanisme kerja Self-Attention ($Q, K, V$), KV-Cache, dan kompleksitas komputasional attention ($O(N^2)$ vs linear attention).
- **In-Memory & Vector Storage**: Pengoperasian Redis (Data structures: Hashes, TTL, RedisVL) dan Vector Databases (Qdrant/Milvus/Pinecone) untuk *approximate nearest neighbor* (ANN).
- **Sistem Asinkron Python**: `asyncio`, typing lanjutan (`typing.Protocol`, `TypedDict`, `Generic`), dan implementasi HTTP client performa tinggi (`httpx`, `aiohttp`).
- **Tokenomics**: Pemahaman mendalam mengenai Byte-Pair Encoding (BPE), SentencePiece, dan disparitas harga antara token *input (cache hit)*, *input (cache miss)*, dan *output*.

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi KV-Cache dan Prefix Caching
Pada arsitektur decoder-only transformer, proses inferensi dibagi menjadi dua fase utama:
1. **Prefill Phase**: Model memproses seluruh sequence input (prompt) secara paralel untuk menghasilkan representasi matriks Key ($K$) dan Value ($V$).
2. **Decoding Phase**: Model menghasilkan satu token per satu waktu secara autoregresif, memanfaatkan matriks $K$ dan $V$ yang telah disimpan di memori GPU (KV-Cache) agar tidak perlu mengomputasi ulang token sebelumnya.

```
Token Input Sequence: [T_1, T_2, ..., T_N]
Prefill: K_i = W_k * X_i,  V_i = W_v * X_i  (Komputasi paralel, memakan FLOPS tinggi)
Decode:  P(T_{t+1} | T_{1:t}) -> Mengakses KV-Cache dari T_{1:t} di HBM GPU.
```

Dalam sistem multi-tenant skala enterprise (misal Anthropic, OpenAI, atau self-hosted vLLM dengan PagedAttention), provider menerapkan **Prefix Caching**. Jika prefix prompt dari request $B$ identik secara byte-for-byte dengan request $A$ yang telah dieksekusi sebelumnya di instance GPU yang sama (atau tersinkronisasi via distributed cache), engine tidak menjalankan *prefill phase* untuk token-token tersebut. Engine langsung memuat *state* KV-cache dari VRAM/Host Memory.

```
Request A: [SYSTEM_PROMPT] + [FEW_SHOT_EXAMPLES] + [DOC_A] + [USER_QUERY_1]
             \____________________________________/
                      Disimpan di KV-Cache (Hash Prefix)

Request B: [SYSTEM_PROMPT] + [FEW_SHOT_EXAMPLES] + [DOC_A] + [USER_QUERY_2]
             \____________________________________/
                      CACHE HIT! Prefill di-skip. Langsung decode USER_QUERY_2.
```

#### 3.2 Dynamic Context Pruning vs. Context Compression
Mengirimkan seluruh riwayat konteks mentah ke LLM merupakan anti-pattern struktural. Dua pendekatan matematis digunakan untuk reduksi konteks:
- **Context Pruning (Selective Context)**: Menghitung entropi informasi dari unit-unit leksikal (kalimat/frasa). Token atau kalimat dengan *self-information* (negatif log probabilitas $I(x) = -\log P(x)$) yang rendah dieliminasi, karena redundan atau tidak memberikan informasi pembeda.
- **Context Compression (e.g., LLMLingua)**: Menggunakan model *small-language model* (SLM) seperti LLaMA-7B atau BERT-based token classifier untuk memprediksi probabilitas kondisional dari setiap token. Token dengan perplexity rendah di dalam konteks dapat dihapus secara agresif, menyisakan representasi informasi yang padat.

```
Konteks Awal (100 Token): 
"Kami mengonfirmasi bahwa berdasarkan laporan keuangan kuartal ketiga yang dirilis pada hari Jumat, perusahaan mencatat laba bersih sebesar sepuluh miliar rupiah."

Pruning Entropi (40 Token):
"Laporan keuangan Q3 Jumat: perusahaan catat laba bersih sepuluh miliar rupiah."
```

#### 3.3 Hierarchical Dynamic Context Architecture
Arsitektur produksi tingkat lanjut membagi pemrosesan context window ke dalam empat layer mitigasi:
1. **Layer 0 - Deterministic Exact Cache**: Hash SHA-256 pada prompt normal. O(1) latency lookup, nol inferensi.
2. **Layer 1 - Semantic Vector Cache**: Normalisasi embeddings query, pencarian threshold kesamaan ($\cos(\theta) \ge 0.96$). Menghasilkan respons instan untuk pertanyaan semantik yang identik.
3. **Layer 2 - Context Budgeting & Dynamic Compressor**: Jika terjadi cache miss, dokumen dan riwayat dipangkas sesuai alokasi kuota token dinamis (*Token Budget Allocator*) dan diurutkan agar prefix tetap statis.
4. **Layer 3 - Engine-Level Prefix Alignment**: Prompt disusun secara deterministik: elemen statis ditempatkan di paling awal (*head*), elemen semi-statis di tengah (*body*), dan elemen dinamis di paling akhir (*tail*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise Context Architecture |
| :--- | :--- | :--- |
| **Penyusunan Prompt** | Menggabungkan dynamic context (waktu, ID user) di awal prompt. | **Prefix Stabilization**: Konfigurasi sistem dan RAG statis di awal; timestamp dan query dinamis di akhir. |
| **Pengelolaan Token** | Mengirim seluruh riwayat obrolan (unbounded array) hingga menabrak context limit LLM. | **Token Budget Governor**: Dynamic sliding window berbasis priority weight, compression ratio, dan budget capping. |
| **Ekonomi Inferensi** | Membayar 100% harga token input standar secara berulang untuk dokumen yang sama. | **Multi-Tier Caching**: Penghematan 50%-80% biaya input menggunakan Provider Prompt Caching + Redis Cache. |
| **Latensi TTFT** | Linier terhadap panjang dokumen ($O(N)$ sampai $O(N^2)$ prefill compute time). | Dekat dengan konstan ($O(1)$) untuk segmen cache hit berkat bypass prefill phase. |
| **Penanganan Kegagalan** | Request crash dengan error HTTP 429/400 (Context Length Exceeded). | Graceful degradation: Pruning otomatis, adaptive model routing, selective summarization. |

---

### 5. How: Workflow Detail

Alur kerja Context Window Optimization dan Cost Engineering end-to-end:

```
[User Request Ingestion]
           │
           ▼
[Step 1: Normalization & Query Sanitation]
           │
           ▼
[Step 2: Check L0 Cache (Exact Hash via Redis)] ──(HIT)──> [Return Cached Response]
           │ (MISS)
           ▼
[Step 3: Check L1 Cache (Semantic via Vector Store)] ──(HIT)──> [Return Cached Response]
           │ (MISS)
           ▼
[Step 4: Token Budget Allocation Engine]
   ├─ Alokasi Kuota: System Core (10%)
   ├─ Alokasi Kuota: Retrieved RAG Documents (50%)
   ├─ Alokasi Kuota: Conversation History (25%)
   └─ Buffer Output Reservation (15%)
           │
           ▼
[Step 5: Dynamic Context Pruning & Compression]
   ├─ Prune riwayat obrolan lama (Decay factor)
   ├─ Kompres dokumen RAG via Information Density Filter
   └─ Eliminasi token sintaksis yang tidak menambah semantic value
           │
           ▼
[Step 6: Prefix Alignment Assembly]
   ├─ [STATIC] System Instruction (Hashable prefix block)
   ├─ [STATIC] Knowledge Base References (Sorted, invariant)
   ├─ [DYNAMIC] Session History Window
   └─ [HIGHLY DYNAMIC] User Query & Realtime Metadata
           │
           ▼
[Step 7: Telemetry & Budget Enforcement Check]
   ├─ Cek Akumulasi Biaya Organisasi / Jam
   └─ Lewati ke fallback model jika mendekati hard limit
           │
           ▼
[Step 8: Execution via LLM Provider (Prompt Caching Enabled)]
           │
           ▼
[Step 9: Post-Processing, Cost Tracking, L0/L1 Cache Insertion]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Perpustakaan Riset Korporasi
Bayangkan Anda menyewa seorang peneliti jenius berbayar per kata yang dia baca (LLM):
- **Naive Approach**: Setiap kali Anda bertanya, Anda membawakan 5 buku tebal yang sama, menaruh catatan hari ini di halaman pertama, dan menyuruhnya membaca ulang seluruh isi 5 buku tersebut dari awal sebelum menjawab.
- **Enterprise Approach**:
  1. Anda menaruh 5 buku tersebut secara permanen di meja kerjanya (*Prefix/KV-Cache*).
  2. Anda hanya menyelipkan memo baru di halaman terakhir (*Dynamic Tail*).
  3. Anda menyewa asisten magang berbiaya rendah untuk merangkum 5 buku menjadi 20 halaman inti sebelum dibaca oleh peneliti utama (*Context Compression*).
  4. Jika pertanyaan yang sama pernah dijawab kemarin, Anda langsung mengambil salinan jawabannya dari laci arsip tanpa memanggil sang peneliti (*Exact/Semantic Cache*).

#### Arsitektur Fisik & Data Flow (ASCII)

```
========================================================================================
                          ENTERPRISE CONTEXT ENGINE ARCHITECTURE
========================================================================================

           +-------------------------------------------------------+
           |                    Client Request                     |
           +-------------------------------------------------------+
                                       |
                                       v
        +-------------------------------------------------------------+
        |                 Ingress Gateway & Normalizer                |
        +-------------------------------------------------------------+
               |                                            |
        (Hash Lookup)                              (Embedding Lookup)
               v                                            v
    +--------------------+                       +--------------------+
    |  L0: Redis Cache   |                       | L1: Semantic Cache |
    |   (Exact Match)    |                       | (Cosine Sim >=.96) |
    +--------------------+                       +--------------------+
         |              \                             |              \
       (HIT)           (MISS)                       (HIT)           (MISS)
         |                \                           |                \
         v                 \                          v                 v
   [Fast Return]            +-------------------> [Fast Return]   +------------------+
                                                                  |  Budget Governor |
                                                                  +------------------+
                                                                           |
         +-----------------------------------------------------------------+
         |
         v
+-----------------------------------------------------------------------------------+
| Context Optimizer Pipeline                                                        |
|                                                                                   |
|  1. Context Partitioning:                                                         |
|     +-------------------------+-------------------------+----------------------+  |
|     |  System Prompt (Static) | RAG Documents (Static)  | History + Query (Dyn)|  |
|     +-------------------------+-------------------------+----------------------+  |
|                                                                                   |
|  2. Compression Layer (LLMLingua / Perplexity Scorer):                           |
|     [Raw Tokens: 12,000] =====> [Filter Entropi Rendah] =====> [Tokens: 3,500]     |
|                                                                                   |
|  3. Prefix Alignment (Boundary padding to 1,024-token cache blocks):              |
|     [Block 0: Static Core] -> [Block 1: Docs Context] -> [Block 2: Tail/Query]    |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
        +-------------------------------------------------------------+
        |     LLM Gateway (vLLM / Anthropic Claude / OpenAI / DeepSeek)|
        |                                                             |
        |     * Provider KV-Cache Hit Tracker                         |
        |     * Cost Accumulator & Prometheus Telemetry Metric        |
        +-------------------------------------------------------------+
                                       |
                                       v
           +-------------------------------------------------------+
           |                Downstream Response Stream             |
           +-------------------------------------------------------+
========================================================================================
```

---

### 7. Implementation Examples

#### 7.1 Simple Example: Dynamic Sliding Window dengan Boundary Token Allocator
Implementasi dasar penegakan anggaran token riwayat obrolan menggunakan library tiktoken:

```python
import tiktoken

def enforce_sliding_window(
    messages: list[dict[str, str]], 
    max_tokens: int, 
    model_name: str = "gpt-4o"
) -> list[dict[str, str]]:
    """
    Mempertahankan System Prompt (index 0) dan memotong riwayat terlama
    agar total token tidak melebihi alokasi max_tokens.
    """
    encoding = tiktoken.encoding_for_model(model_name)
    
    if not messages:
        return []
    
    # Simpan system prompt jika ada di awal
    system_message = messages[0] if messages[0]["role"] == "system" else None
    working_messages = messages[1:] if system_message else messages[:]
    
    system_tokens = len(encoding.encode(system_message["content"])) if system_message else 0
    available_tokens = max_tokens - system_tokens
    
    if available_tokens <= 0:
        raise ValueError("Budget token tidak cukup untuk menampung system prompt.")
    
    selected_messages: list[dict[str, str]] = []
    current_tokens = 0
    
    # Iterasi mundur dari pesan terbaru ke pesan lama
    for message in reversed(working_messages):
        msg_tokens = len(encoding.encode(message["content"])) + 4 # Overhead format pesan
        if current_tokens + msg_tokens <= available_tokens:
            selected_messages.insert(0, message)
            current_tokens += msg_tokens
        else:
            break
            
    if system_message:
        return [system_message] + selected_messages
    return selected_messages
```

#### 7.2 Practical Example: Enterprise Multi-Tier Context Optimizer & Caching Engine
Di bawah ini adalah sistem orkestrasi skala produksi yang mencakup:
1. Exact Prompt Hashing (L0).
2. Context Pruning heuristik berbasis *information density*.
3. Penataan prompt deterministik untuk memaksimalkan *Anthropic Prompt Caching* (`cache_control`).
4. Ekstraksi metrik efisiensi biaya (*Cost Telemetry*).

```python
#!/usr/bin/env python3
"""
Production Context Window & Cost Optimization Engine.
Mematuhi standar asynchronous, strict typing, dan structured logging.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ContextOptimizer")

# Pricing matrix per 1M tokens (USD) - Contoh: Claude 3.5 Sonnet
PRICE_INPUT_STANDARD = 3.00
PRICE_INPUT_CACHE_READ = 0.30  # Penghematan 90%
PRICE_INPUT_CACHE_WRITE = 3.75 # 25% overhead penulisan pertama
PRICE_OUTPUT = 15.00


@dataclass(frozen=True)
class OptimizationMetrics:
    original_tokens: int
    compressed_tokens: int
    cache_hit: bool
    estimated_cost_usd: float
    latency_ms: float


class HeuristicContextCompressor:
    """
    Kompresor konteks deterministik performa tinggi:
    Menghilangkan stopwords, whitespaces berlebih, dan token non-esensial dari dokumen.
    """
    
    # Regex untuk karakter berulang dan spasi redundan
    WHITESPACE_SUB = re.compile(r"\s+")
    CODE_COMMENT_SUB = re.compile(r"(#.*?$|//.*?$|/\*.*?\*/)", re.MULTILINE)
    
    # Set token pengisi sintetis berbobot semantik rendah
    STOPWORDS = {
        "bahwa", "adalah", "merupakan", "tersebut", "yang", "dan", "di", "ke", 
        "pada", "untuk", "dari", "dengan", "ini", "itu", "dalam", "sebagai"
    }

    @classmethod
    def compress(cls, text: str, aggressiveness: float = 0.3) -> str:
        """
        Mengompresi teks dokumen berdasarkan rasio agresivitas (0.0 - 1.0).
        """
        if aggressiveness <= 0.0:
            return text

        # 1. Normalisasi Whitespace & Komentar
        cleaned = cls.CODE_COMMENT_SUB.sub("", text)
        cleaned = cls.WHITESPACE_SUB.sub(" ", cleaned).strip()

        if aggressiveness < 0.5:
            return cleaned

        # 2. Pruning leksikal selektif untuk kompresi tinggi
        words = cleaned.split(" ")
        filtered_words = [
            w for w in words 
            if w.lower() not in cls.STOPWORDS or len(w) > 6
        ]
        return " ".join(filtered_words)


class ContextWindowOrchestrator:
    """
    Orkestrator utama pengelolaan konteks LLM enterprise.
    Menangani deterministic cache, budget allocation, dan prompt-cache boundary injection.
    """

    def __init__(self, api_key: str, redis_mock_store: Optional[Dict[str, str]] = None):
        self.api_key = api_key
        # Menggunakan in-memory dict sebagai representasi mock Redis instance
        self.exact_cache: Dict[str, str] = redis_mock_store if redis_mock_store is not None else {}
        self.compressor = HeuristicContextCompressor()

    @staticmethod
    def _compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def assemble_prompt_with_cache_boundaries(
        self,
        system_instruction: str,
        knowledge_documents: List[str],
        user_query: str,
        token_budget: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Menyusun payload prompt sesuai spesifikasi cache control block.
        Bagian statis diberi penanda breakpoint KV-cache.
        """
        # 1. Kompresi dokumen jika ukuran gabungan terlalu besar
        merged_docs = "\n\n".join(knowledge_documents)
        estimated_doc_tokens = len(merged_docs) // 4  # Estimasi kasar: 1 token ≈ 4 karakter
        
        if estimated_doc_tokens > (token_budget * 0.6):
            logger.info("Dokumen melebihi batas 60% anggaran. Mengaktifkan kompresi konteks.")
            merged_docs = self.compressor.compress(merged_docs, aggressiveness=0.4)

        # 2. Susun pesan dengan boundary prefix cache Anthropic format
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Knowledge Base Context:\n{merged_docs}",
                        # Marker cache_control menandakan batas prefix KV-cache provider
                        "cache_control": {"type": "ephemeral"}
                    },
                    {
                        "type": "text",
                        "text": f"Pertanyaan: {user_query}"
                    }
                ]
            }
        ]
        
        total_estimated_tokens = (len(system_instruction) + len(merged_docs) + len(user_query)) // 4
        return messages, total_estimated_tokens

    async def execute_query(
        self,
        system_instruction: str,
        knowledge_documents: List[str],
        user_query: str,
        token_budget: int = 8000
    ) -> Tuple[str, OptimizationMetrics]:
        start_time = time.perf_counter()
        
        # 1. L0 Cache Check (Exact Hash terhadap keseluruhan context input)
        raw_signature = f"{system_instruction}:{json.dumps(knowledge_documents)}:{user_query}"
        cache_key = self._compute_hash(raw_signature)
        
        if cache_key in self.exact_cache:
            latency = (time.perf_counter() - start_time) * 1000
            logger.info(f"L0 Cache Hit. Hash: {cache_key[:8]}")
            return self.exact_cache[cache_key], OptimizationMetrics(
                original_tokens=len(raw_signature) // 4,
                compressed_tokens=0,
                cache_hit=True,
                estimated_cost_usd=0.0,
                latency_ms=latency
            )

        # 2. Context Optimization & Boundary Injection
        messages, est_tokens = self.assemble_prompt_with_cache_boundaries(
            system_instruction=system_instruction,
            knowledge_documents=knowledge_documents,
            user_query=user_query,
            token_budget=token_budget
        )

        # 3. Payload Construction ke Provider API
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-25",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": [
                {
                    "type": "text",
                    "text": system_instruction,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            "messages": messages
        }

        # 4. Dispatch Async Network Call (Menggunakan Mock Engine jika tanpa live API Key)
        if self.api_key == "MOCK_KEY":
            # Simulasi respons engine
            latency = (time.perf_counter() - start_time) * 1000
            simulated_response = "Ini adalah jawaban mock berbasis optimasi konteks enterprise."
            self.exact_cache[cache_key] = simulated_response
            
            # Simulasi kalkulasi biaya
            cost = (est_tokens * PRICE_INPUT_CACHE_READ / 1_000_000) + (100 * PRICE_OUTPUT / 1_000_000)
            return simulated_response, OptimizationMetrics(
                original_tokens=len(raw_signature) // 4,
                compressed_tokens=est_tokens,
                cache_hit=False,
                estimated_cost_usd=cost,
                latency_ms=latency
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        latency = (time.perf_counter() - start_time) * 1000
        output_text = data["content"][0]["text"]
        
        # Ekstraksi token usage aktual dari header telemetry provider
        usage = data.get("usage", {})
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        regular_input = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Hitung biaya riil
        actual_cost = (
            (cache_read * (PRICE_INPUT_CACHE_READ / 1_000_000)) +
            (cache_creation * (PRICE_INPUT_CACHE_WRITE / 1_000_000)) +
            (regular_input * (PRICE_INPUT_STANDARD / 1_000_000)) +
            (output_tokens * (PRICE_OUTPUT / 1_000_000))
        )

        # Simpan hasil di L0 Cache
        self.exact_cache[cache_key] = output_text

        return output_text, OptimizationMetrics(
            original_tokens=len(raw_signature) // 4,
            compressed_tokens=cache_read + cache_creation + regular_input,
            cache_hit=cache_read > 0,
            estimated_cost_usd=actual_cost,
            latency_ms=latency
        )


# Demonstration Execution Harness
if __name__ == "__main__":
    import asyncio

    async def main():
        orchestrator = ContextWindowOrchestrator(api_key="MOCK_KEY")
        
        system_rules = "Anda adalah financial risk auditor enterprise. Berikan analisis berbasis fakta."
        corporate_reports = [
            "Laporan Keuangan Q1 PT Korporasi Mega: Pendapatan tercatat Rp 500M dengan EBITDA marjin 22%. Beban operasional terkendali.",
            "Laporan Keuangan Q2 PT Korporasi Mega: Pendapatan meningkat ke Rp 580M, laba bersih bersih Rp 110M. Risiko likuiditas rendah.",
            "Laporan Keuangan Q3 PT Korporasi Mega: Pendapatan melonjak ke Rp 650M. Terdapat ekspansi pabrik baru di Cikarang seluas 4 hektar."
        ]
        user_query = "Bagaimana tren pendapatan dari Q1 hingga Q3 dan rencana ekspansinya?"

        print("=== RUN 1: Cold Invocation (Cache Creation) ===")
        res1, metrics1 = await orchestrator.execute_query(
            system_rules, corporate_reports, user_query
        )
        print(f"Output: {res1}")
        print(f"Tokens: {metrics1.compressed_tokens}, Cost: ${metrics1.estimated_cost_usd:.6f}, Latency: {metrics1.latency_ms:.2f}ms\n")

        print("=== RUN 2: Warm Invocation (L0 Exact Cache Hit) ===")
        res2, metrics2 = await orchestrator.execute_query(
            system_rules, corporate_reports, user_query
        )
        print(f"Output: {res2}")
        print(f"Tokens: {metrics2.compressed_tokens}, Cost: ${metrics2.estimated_cost_usd:.6f}, Latency: {metrics2.latency_ms:.2f}ms")

    asyncio.run(main())
```

---

### 8. Real World Case Study: Global FinTech Risk Analysis Gateway

#### Kasus Masalah
Sebuah platform perbankan global memproses **120.000 query audit risiko/menit**. Setiap query harus mengevaluasi dokumen regulasi AML (*Anti-Money Laundering*) setebal 45.000 token yang digabungkan dengan riwayat transaksi rekening pengguna (*tail tokens*).
- **Arsitektur Awal**: Dokumen regulasi dikirim secara utuh pada setiap panggilan model OpenAI `gpt-4o` tanpa caching.
- **Dampak Finansial**:
  $$\text{Input Biaya Harian} = 120.000 \times 60 \times 24 \times \frac{45.000}{1.000.000} \times \$2,50 = \$19.440.000/\text{hari} \quad (\text{Tidak realistis \& kolaps})$$
- **Dampak Latensi**: TTFT rata-rata mencapai **4.200 ms**, memicu pelanggaran SLA gateway HTTP timeout (5 detik).

#### Solusi Rekayasa Konteks
1. **Penerapan vLLM Self-Hosted Cluster dengan PagedAttention & Automatic Prefix Caching (APC)**:
   - Dokumen regulasi AML (45.000 token) di-load ke VRAM GPU sebagai *Persistent Frozen Prefix*.
   - Hash prefix dokumen AML dipertahankan statis selama 7 hari siklus regulasi.
2. **Context Compression Dinamis pada Riwayat Transaksi**:
   - Menerapkan model kompresi ringan (SLM) on-premise untuk memfilter metadata transaksi mentah berbasis deviasi skor Z anomaly, mengurangi token riwayat dari rata-rata 3.500 token menjadi 450 token.
3. **Prefix Stabilization**:
   - Menghapus timestamp dinamis dari System Message (dipindahkan ke Payload Metadata di akhir query).

```
[SEBELUM]
Role: System | Content: "Waktu server: 2026-03-31T08:12:01Z. Aturan AML: [45k tokens]..."
-> HASH BERUBAH SETIAP DETIK. CACHE INVALIDATION: 100%.

[SESUDAH]
Role: System | Content: "Aturan AML: [45k tokens]..." -> CACHE HIT 99.8%
Role: User   | Content: "Metadata Waktu: 2026-03-31T08:12:01Z. Data: [450 tokens]..."
```

#### Hasil Terukur (Benchmarked Post-Implementation)
- **Token Input Reduksi**: Biaya pemrosesan riwayat turun 87% berkat kompresi SLM.
- **Provider Cache Hit Ratio**: Mencapai 98,2% pada dokumen regulasi.
- **TTFT (P99)**: Turun drastis dari **4.200 ms** menjadi **310 ms**.
- **Net Cost Savings**: Efisiensi biaya operasional mencapai **$18,8 juta/hari** (penurunan beban inferensi sebesar $\approx 96,7\%$).

---

### 9. Trade-offs: Architectural Decision Matrix

Setiap optimasi konteks memiliki konsekuensi teknis. Gunakan matriks berikut sebagai referensi evaluasi arsitektur:

```
+---------------------------+-----------------------+---------------------+---------------------+----------------------+
| Pendekatan Optimasi       | Latency Impact        | Cost Reduction      | Akurasi Retensi     | Kompleksitas Sistem  |
+---------------------------+-----------------------+---------------------+---------------------+----------------------+
| Exact Cache (Redis SHA256)| Eliminasi total (99%) | Turun 100% per hit  | 100% (Identik)      | Sangat Rendah        |
| Semantic Cache (Vector)   | Rendah (< 15ms lookup)| Turun 100% per hit  | 90-95% (Semantic    | Sedang (Tuning       |
|                           |                       |                     | Drift risk)         | similarity threshold)|
| Aggressive Token Pruning  | Menambah 20-40ms      | Turun 40-70%        | 85-92% (Risiko      | Tinggi (Dependency SLM|
| (Entropy / LLMLingua)     | (waktu kompresi)      |                     | kehilangan detail)  | model lokal)         |
| Prefix Caching (Provider) | TTFT turun 60-80%     | Turun 50-90% input  | 100% (Lossless)     | Rendah-Sedang        |
|                           |                       |                     |                     | (Disiplin prompt)    |
| Sliding Window Naive      | Netral                | Terkendali linier   | Rusak pada konteks  | Sangat Rendah        |
|                           |                       |                     | jangka panjang      |                      |
+---------------------------+-----------------------+---------------------+---------------------+----------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: "Cache Busting" Akibat Metadata Dinamis di Awal Prompt
*   **Gejala**: Prefix cache hit ratio bernilai 0% pada dashboard penyedia LLM (Anthropic/OpenAI/vLLM), padahal konten dokumen 100% sama.
*   **Akar Masalah**: Menyisipkan elemen dinamis seperti `Current Timestamp`, `Request ID`, atau `User Session ID` pada baris pertama prompt.
*   **Perbaikan**: Pindahkan seluruh variabel dinamis ke blok token paling belakang (*tail*) dari struktur pesan.

#### Anti-Pattern 2: Non-Deterministic Serialization Dokumen JSON/Dict
*   **Gejala**: Exact cache miss tidak menentu padahal data input secara logika identik.
*   **Akar Masalah**: Menggunakan `str(dict_data)` bawaan bahasa pemrograman yang urutan *key*-nya tidak terurut secara deterministik sebelum di-hash.
*   **Perbaikan**: Gunakan serialisasi kanonikal: `json.dumps(dict_data, sort_keys=True, separators=(',', ':'))`.

#### Anti-Pattern 3: Needle-in-a-Haystack Degradation akibat Over-Compression
*   **Gejala**: LLM mengalami halusinasi atau mengabaikan instruksi format jawaban spesifik setelah context compressor diaktifkan.
*   **Akar Masalah**: Algoritma kompresi memangkas token sintaksis yang membawa dependensi gramatikal kritis bagi instruksi sistem (*system constraints*).
*   **Perbaikan**: **Isolasi Proteksi Token**: Jangan pernah mengompresi blok System Prompt; terapkan pruning dan kompresi *hanya* pada dokumen referensi pihak ketiga (*retrieved knowledge chunks*).

---

### 11. Best Practices (Production Checklist)

- [ ] **Prefix Invariance**: System prompt, function/tool schema definitions, dan dokumen acuan diurutkan secara leksikografis dan ditaruh di awal prompt.
- [ ] **Block Boundary Alignment**: Panjang blok prefix dihitung agar memenuhi ambang batas minimum aktivasi provider cache (misal: Anthropic minimal 1.024 token; DeepSeek blok kelipatan 64 token).
- [ ] **Dynamic Budget Guardrails**: Token input dihitung secara akurat menggunakan tokenizer native (misal: `tiktoken` untuk OpenAI, tokenizers HuggingFace untuk model open-weights) sebelum payload dikirim ke jaringan.
- [ ] **Circuit Breaker Biaya Terpasang**: Terapkan rate-limiting berbasis akumulasi token harian (*Token Leak Prevention*), bukan sekadar RPM (*Requests Per Minute*).
- [ ] **Telemetry OpenInference/OpenTelemetry**: Catat metrik granular per transaksi: `cache_read_tokens`, `cache_write_tokens`, `regular_tokens`, `compression_ratio`, dan `dollar_cost`.
- [ ] **Fallback Degradation Route**: Siapkan model cadangan berbiaya rendah (misal: beralih dari model frontier ke model SLM) secara dinamis jika kuota biaya bulanan melewati ambang 85%.

---

### 12. Hands-on Practice: Hands-on / m02/

Praktikum ini memandu Anda mengonstruksi sebuah micro-service context optimization yang memvalidasi efisiensi cache dan kompresi.

#### Struktur Direktori
```
hands-on/m02/
├── Dockerfile
├── requirements.txt
├── docker-compose.yml
├── config.py
├── compressor.py
├── orchestrator.py
└── main.py
```

#### Langkah Pengerjaan

##### 1. Siapkan file dependensi: `hands-on/m02/requirements.txt`
```text
httpx==0.27.0
pydantic==2.8.2
redis==5.0.7
tiktoken==0.7.0
pytest==8.2.2
pytest-asyncio==0.23.7
```

##### 2. Tulis Modul Kompresi: `hands-on/m02/compressor.py`
```python
import re

class ProductionContextPruner:
    """Modul pemangkasan konteks untuk mengurangi redundansi token."""
    
    @staticmethod
    def prune_context(text: str) -> str:
        # Hapus whitespace redundan dan trailing linebreaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
```

##### 3. Tulis Core Orchestrator: `hands-on/m02/orchestrator.py`
```python
import hashlib
import json
from typing import Dict, Any, Tuple
from compressor import ProductionContextPruner

class EnterpriseContextGateway:
    def __init__(self):
        self.exact_cache: Dict[str, str] = {}
        self.pruner = ProductionContextPruner()

    def process_and_route(
        self, 
        system_prompt: str, 
        large_context: str, 
        user_query: str
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Menghasilkan payload terstruktur dengan penataan prefix caching.
        """
        # Prune context
        optimized_context = self.pruner.prune_context(large_context)
        
        # Buat deterministic payload
        cache_key = hashlib.sha256(
            f"{system_prompt}::{optimized_context}::{user_query}".encode()
        ).hexdigest()

        if cache_key in self.exact_cache:
            return {"status": "hit", "response": self.exact_cache[cache_key]}, True

        # Susun payload dengan boundary prefix
        payload = {
            "system": system_prompt,
            "context_block": optimized_context,
            "query": user_query,
            "cache_key": cache_key
        }
        
        return payload, False

    def store_result(self, cache_key: str, response: str):
        self.exact_cache[cache_key] = response
```

##### 4. Harness Driver & Verification: `hands-on/m02/main.py`
```python
import time
from orchestrator import EnterpriseContextGateway

def run_benchmarks():
    gateway = EnterpriseContextGateway()
    
    system = "Anda asisten kepatuhan perbankan. Ringkas dokumen secara tegas."
    context = """
    Laporan Kepatuhan 2026:
    
    
    Unit A telah memenuhi standar ISO 27001. Audit independen tidak menemukan defisiensi kritis.
    
    Unit B mengalami keterlambatan pelaporan insiden selama 2 jam, telah diselesaikan.
    """
    query = "Sebutkan temuan audit Unit B."

    print("Step 1: Melakukan query pertama (Cold Cache)...")
    payload, is_hit = gateway.process_and_route(system, context, query)
    assert not is_hit, "Seharusnya cache miss pada eksekusi perdana."
    
    # Simulasikan hasil panggilan LLM
    mock_llm_response = "Unit B terlambat melapor selama 2 jam namun sudah beres."
    gateway.store_result(payload["cache_key"], mock_llm_response)
    print("Cold Call selesai. Respons disimpan di cache.")

    print("\nStep 2: Menjalankan query yang sama persis (Warm Cache)...")
    t0 = time.perf_counter()
    res, is_hit = gateway.process_and_route(system, context, query)
    elapsed = (time.perf_counter() - t0) * 1000
    
    assert is_hit, "Seharusnya cache hit!"
    print(f"Warm Call Berhasil! Response: {res['response']}")
    print(f"Lookup Latency: {elapsed:.4f} ms")

if __name__ == "__main__":
    run_benchmarks()
```

---

### 13. Exercises

#### Level Easy
Tulis fungsi Python `estimate_cost(input_tokens: int, output_tokens: int, cache_read_tokens: int, model: str) -> float` yang menghitung total pengeluaran secara presisi menggunakan formula pemotongan harga Claude 3.5 Sonnet:
- Regular Input: \$3.00 / 1M
- Cache Read: \$0.30 / 1M
- Output: \$15.00 / 1M

#### Level Medium
Buat sebuah decorator Python `@enforce_token_budget(max_tokens=4096, tokenizer_name="cl100k_base")`. Jika sebuah fungsi menerima parameter `prompt: str` yang melebihi batas `max_tokens`, potong (*truncate*) parameter string tersebut dari bagian tengah teks (*middle-out truncation*) dan tambahkan peringatan log, sehingga instruksi awal dan akhir prompt tetap utuh.

#### Level Hard
Rancang dan implementasikan class `EntropyContextCompressor` berbasis probabilitas n-gram leksikal:
- Hitung frekuensi kemunculan token di dalam korpus teks input.
- Berikan skor *surprisal* pada tiap kalimat:
  $$S(\text{kalimat}) = -\frac{1}{M}\sum_{i=1}^{M}\log_2(P(w_i))$$
- Eliminasi 30% kalimat yang memiliki rata-rata surprisal terendah (paling dapat diprediksi/redundant).

---

### 14. Challenge: Multi-Tenant Budget-Enforced Gateway

#### Konteks Masalah
Perusahaan SaaS Anda menyediakan API Agentic RAG yang digunakan oleh **500 tenant korporasi**. Setiap tenant memiliki batas kredit finansial harian yang ketat (misal: \$50/hari per tenant). Beberapa pengguna nakal dari satu tenant mengirimkan prompt berukuran 100.000 token secara terus-menerus, yang berpotensi menghabiskan kuota satu tenant dalam 10 menit atau menyebabkan starvation pada resource pool organisasi.

#### Persyaratan Arsitektur
Bangun arsitektur microservice (menggunakan FastAPI/Pydantic/Redis) yang memenuhi kriteria:
1. **Dynamic Cost Projection**: Menghitung estimasi biaya terburuk (*worst-case cost*) **sebelum** query dieksekusi ke LLM backend.
2. **Atomic Budget Reservation**: Mengurangi kuota tenant secara atomik di Redis (`DECRBY` atau Lua Scripting). Jika sisa deposit tenant tidak mencukupi untuk worst-case cost, tolak request secara instan dengan status code `HTTP 402 (Payment Required)`.
3. **Adaptive Degradation Strategy**:
   - Jika sisa kuota tenant $> 20\%$: Eksekusi model default (`gpt-4o`).
   - Jika sisa kuota tenant $\le 20\%$: Turunkan (*fallback*) context window secara otomatis via kompresi agresif dan rutekan ke model ekonomis (`gpt-4o-mini`).
4. **Reconciliation Loop**: Setelah inferensi selesai dan jumlah token aktual (*actual tokens used*) diterima dari LLM provider, kembalikan selisih token yang dicadangkan (*refund unspent reserved tokens*) ke saldo tenant secara presisi.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Konseptual (Basic)
1. Apa alasan komputasional mendasar mengapa *Prefix Caching (KV-Cache reuse)* menurunkan metrik Time-To-First-Token (TTFT) secara drastis?
2. Di manakah posisi terbaik untuk menempatkan timestamp server dalam prompt terstruktur jika Anda ingin memanfaatkan Provider-Level Prompt Caching?
3. Mengapa token *output* pada hampir seluruh penyedia LLM dihargai 3x hingga 5x lipat lebih mahal dibandingkan token *input*?
4. Apa perbedaan mendasar antara *Deterministic Exact Cache* dan *Semantic Cache*?
5. Berapa batas minimum jumlah token prefix yang disyaratkan oleh Anthropic API agar mekanisme caching ephemeral aktif pada suatu blok pesan?

#### Pertanyaan Arsitektur (Intermediate)
6. Jelaskan bagaimana algoritma *PagedAttention* pada vLLM memecahkan fragmentasi memori virtual GPU pada KV-cache multi-tenant.
7. Mengapa kompresi konteks berbasis LLMLingua lebih aman terhadap akurasi model dibandingkan sekadar menghapus stopwords menggunakan daftar statis (static stopwords removal)?
8. Jika sebuah sistem memiliki rasio cache hit 80% pada L1 Semantic Cache, potensi bahaya apa (*semantic drift*) yang dapat menimpa pengguna akhir jika similarity threshold disetel terlalu rendah (misal: $\cos(\theta) = 0.82$)?
9. Bagaimana strategi penataan prompt yang tepat saat menggunakan *Tool Calling / Function Calling* agar skema tools tersebut tersimpan rapi di KV-cache?
10. Mengapa pendekatan "Summarize-on-the-fly" menggunakan LLM lain untuk memangkas konteks obrolan sering kali menjadi anti-pattern dalam konteks cost engineering?

#### Studi Kasus Rekayasa Sistem (Production Scenarios)

##### Kasus A
Sistem customer support Anda mengalami lonjakan tagihan token hingga 400% dalam 24 jam setelah rilis fitur baru, padahal *Daily Active Users* (DAU) stagnan. Setelah diaudit, engineer baru menambahkan baris kode:
```python
messages = [{"role": "system", "content": f"Session: {uuid.uuid4()} | {BASE_INSTRUCTION}"}] + history
```
Jelaskan dampak baris kode tersebut terhadap sistem inferensi LLM provider dan berikan perbaikan arsitekturalnya secara konkret!

##### Kasus B
Sebuah aplikasi analisa legal memiliki 10.000 dokumen kontrak PDF (masing-masing 30 halaman). Banyak query menanyakan klausul spesifik yang serupa di seluruh dokumen. Anda diminta merancang sistem caching yang mengombinasikan Redis dan Vector Database untuk memangkas biaya pemrosesan dokumen tersebut hingga minimal 80%. Gambarkan arsitektur komponen datanya!

##### Kasus C
Pada pipeline Agentic RAG multi-hop, agent melakukan iterasi hingga 10 langkah (*reflection loop*). Di setiap langkah, seluruh output intermediate ditambahkan ke conversation history. Pada langkah ke-8, agent sering kali mengalami context window overflow atau mengalami degradasi penalaran (*attention loss*). Solusi teknis apa yang harus diterapkan pada context state engine tanpa menghapus memori kritis agent?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Konseptual (Basic)
1. **Solusi**: KV-Cache reuse melewati *Prefill Phase* (perkalian matriks $Q \times K^T$ dan $V$ untuk token-token yang sudah ada). GPU tidak perlu menghitung ulang representasi aktivasi token lama dan langsung melompat ke fase *Autoregressive Decoding* untuk token baru.
2. **Solusi**: Di bagian paling akhir prompt (*tail*), tepat bersamaan dengan `user query` atau tepat sebelum token inferensi model, agar tidak memutus rantai prefix hash blok instruksi dan referensi dokumen di atasnya.
3. **Solusi**: Prefill phase diproses secara paralel memanfaatkan seluruh compute core GPU secara efisien (compute-bound). Sebaliknya, generation/output phase bersifat sekuensial (memory-bandwidth bound); menghasilkan 1 token membutuhkan transfer seluruh bobot model dan KV-cache dari VRAM ke chip register, membuat eksekusi output jauh lebih mahal secara operasional per unit token.
4. **Solusi**: *Exact Cache* menggunakan pencocokan biner/hash string (SHA-256) dengan kompleksitas $O(1)$ dan akurasi deterministik 100%. *Semantic Cache* menggunakan representasi vektor densitas tinggi (embeddings) dan kalkulasi kedekatan kosinus untuk menemukan makna serupa walau susunan kata berbeda, namun memiliki toleransi error.
5. **Solusi**: 1.024 token. Blok di bawah 1.024 token tidak memenuhi syarat pembuatan checkpoint cache ephemeral pada Anthropic Claude API.

#### Jawaban Arsitektur (Intermediate)
6. **Solusi**: Layaknya paging pada sistem operasi OS fisik, PagedAttention membagi KV-cache ke dalam blok-blok memori berukuran tetap (*pages*) yang tidak harus berurutan secara fisik di VRAM. Ini mengeliminasi fragmentasi internal/eksternal dan memungkinkan *sharing* KV-cache block antar prompt yang memiliki prefix identik menggunakan copy-on-write pointers.
7. **Solusi**: LLMLingua mengevaluasi probabilitas kondisional token $P(x_i | x_{<i})$ menggunakan bahasa model. Token stopwords yang membawa negasi penting (misal: "tidak", "bukan") atau relasi logika akan memiliki surprisal tinggi dan dipertahankan. Sebaliknya, penghapusan statis membabi-buta berisiko membalikkan arti kalimat secara fatal.
8. **Solusi**: Terjadi *False Positive Retrieval*. Pertanyaan yang tampaknya mirip secara leksikal namun memiliki intensi berkebalikan (misal: "Bagaimana cara menutup rekening?" vs "Bagaimana cara membatalkan penutupan rekening?") akan dianggap sama, sehingga sistem menyajikan jawaban lama yang keliru dan membahayakan kepatuhan transaksi.
9. **Solusi**: Definisi JSON schema untuk tools harus dideklarasikan secara statis, diurutkan menurut nama fungsi (sort alphabetically), dan diinjeksi pada blok instruksi sistem paling atas agar membentuk prefix cacheable block yang tidak berubah antar request.
10. **Solusi**: Menggunakan model frontier untuk merangkum percakapan menambah biaya inferensi LLM baru ($Cost_{summary} + Cost_{final}$) dan menambah latensi serial baru. Tanpa seleksi ketat, proses perangkuman justru menghabiskan lebih banyak biaya komputasi dibanding melakukan token pruning terstruktur berbasis SLM lokal atau sliding window.

#### Panduan Solusi Studi Kasus

##### Solusi Kasus A
- **Akar Masalah**: Pemasangan `uuid.uuid4()` pada baris pertama prompt System menyebabkan string prefix selalu unik di setiap request. Akibatnya, rasio cache hit provider-level hancur menjadi 0% (*cache miss 100%*). Provider terpaksa mengeksekusi *prefill* ulang untuk `BASE_INSTRUCTION` dan riwayat pesan pada setiap siklus, melipatgandakan konsumsi token input berbayar penuh.
- **Perbaikan Arsitektural**:
  Pindahkan UUID pelacakan ke HTTP Request Header (misal: `X-Request-ID`) atau taruh di bagian terbawah prompt bersama query:
  ```python
  # System prompt murni statis (Hash stabil)
  messages = [
      {"role": "system", "content": BASE_INSTRUCTION},
      *history,
      {"role": "user", "content": f"Context Meta: [ID: {uuid.uuid4()}]\nQuery: {actual_user_query}"}
  ]
  ```

##### Solusi Kasus B
- **Arsitektur Solusi**:
  1. *Layer Chunking Deterministik*: Ekstraksi 10.000 PDF menjadi dokumen teks kanonikal, chunking per pasal regulasi/kontrak dengan ID deterministik.
  2. *Redis Doc-Store*: Simpan chunk pasal dalam Redis string store berindeks `doc:{hash_pasal}`.
  3. *Canonical Ingestion & Prompt Assembly*: Saat ada query, jalankan embedding retrieval. Urutkan (*sort*) potongan pasal hasil retrieve berdasarkan ID dokumen/pasal sebelum digabungkan ke prompt. Dengan urutan deterministik ini, dokumen-dokumen kontrak yang sering dipanggil bersamaan akan membentuk urutan prefix identik, memicu Provider Prompt Cache Hit $\ge 80\%$.
  4. *L1 Semantic Query Cache*: Simpan pasangan query hukum dan respons final di Vector DB dengan threshold kesamaan ketat ($\ge 0.97$).

##### Solusi Kasus C
- **Arsitektur Solusi (Hierarchical Scratchpad Context)**:
  1. Jangan gunakan append murni pada conversation history. Buat struktur data *State Scratchpad* terpisah.
  2. Terapkan **Observation Masking**: Setiap kali step $N$ selesai, pangkas detail log eksekusi (*tool execution raw outputs*) dari step $N-1$ menjadi ringkasan 1 baris, hanya sisakan parameter *Action* dan *Action Input* serta kesimpulan esensial.
  3. Pertahankan System Goal dan Final State di buffer terisolasi.
  4. Terapkan sliding window pada jejak reasoning: simpan hanya 2 langkah intermediate terakhir secara detail, sementara langkah 1 hingga $N-2$ dikompresi menjadi *compact event log*. Ini menjaga token footprint tetap di bawah 25% kapasitas context window sekaligus mencegah attention degradation.

---

### 16. Summary
1. **Ekonomi Konteks Modern**: Mengoptimalkan context window bukan hanya sekadar mencegah error `ContextWindowExceeded`, melainkan rekayasa efisiensi biaya (*Cost Engineering*) yang menentukan kelayakan komersial sistem AI.
2. **Kunci Prefix Caching**: Caching berbasis KV-Cache provider menuntut disiplin urutan token yang deterministik. Struktur prompt wajib mengikuti aturan hierarki: **Statis di Head (Awal), Semi-Statis di Tengah, Dinamis di Tail (Akhir)**.
3. **Multi-Tier Mitigation**: Arsitektur produksi yang resilient mengombinasikan Exact Match Cache (Redis) untuk query identik, Semantic Cache untuk variasi linguistik, Context Compressor untuk data RAG masif, dan Provider Prompt Caching untuk mengeksekusi sisa token yang lolos filter.
4. **Boundary Guardrails**: Pengendalian biaya yang kokoh membutuhkan penegakan anggaran token secara preventif (*pre-flight budget checks & circuit breakers*), bukan sekadar audit analitik setelah tagihan membengkak.