# Bab 08: Context Window Optimization & Cost Engineering
## Modul 01: Tokenomics, KV-Cache Dynamics, dan Context Pruning Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Menganalisis Profil Tokenomics Terdistribusi:** Menghitung dan memproyeksikan *unit economics* inferensi (Input, Output, Cache Write, Cache Read) menggunakan model biaya deterministik dengan akurasi deviasi < 2%.
*   **Merancang Strategi KV Cache Optimization:** Menyusun struktur prompt modular yang mengeksploitasi *deterministic prefix matching* untuk mencapai cache hit rate $\ge 85\%$ pada LLM provider tier-1 (Anthropic, OpenAI, Google Cloud Vertex AI).
*   **Mengimplementasikan Dynamic Context Pruning:** Membangun *production-grade context compaction engine* berbasis semantic relevance filtering, token truncation, dan syntax minification yang mampu mereduksi token input hingga 40-60% tanpa degradasi retrieval accuracy (Recall@K $\ge 0.95$).
*   **Memitigasi Anomali *Lost-in-the-Middle*:** Menerapkan topologi penyusunan konteks non-linear berbasis kurva atensi $U\text{-shape}$ guna meminimalkan degradasi recall informasi faktual pada konteks panjang ($>32\text{k}$ token).
*   **Membangun Context Budgeting & Circuit Breaking:** Mengembangkan sistem kontrol inferensi dengan batasan latensi dan biaya hard-cap berbasis dynamic token budgeting.

---

### 2. Concept Overview

Dalam arsitektur *Large Language Model* berbasis Transformer, *context window* bukanlah media penyimpanan statis seperti RAM konvensional, melainkan ruang aktivasi komputasi sementara di mana setiap token berinteraksi melalui mekanisme *scaled dot-product attention*:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Secara naif, kompleksitas komputasi attention bersifat kuadratik $\mathcal{O}(N^2)$ terhadap panjang konteks ($N$), baik dari sisi beban komputasi (FLOPs) maupun memori aktivasi *Key-Value* (KV) Cache. Meskipun implementasi inferensi modern menggunakan optimasi seperti *FlashAttention*, *PagedAttention*, dan *Grouped-Query Attention* (GQA) yang mereduksi memory footprint, biaya inferensi tetap diskalakan secara linier terhadap jumlah token input dan kuadratik terhadap token generasi output.

```
       Konsep Mental: Model Biaya & Retensi Atensi LLM

Token Attention Weight
  ^
1.0 | [High Focus]                                    [High Focus]
    | \                                              /
0.5 |  \               "Lost-in-the-Middle"         /
    |   \__________________________________________/
0.0 +----------------------------------------------------> Posisi Token
    0% (System / Prefix)     50% (Body Konteks)      100% (Suffix/Query)
    
    [--- STATIC CACHE ---]   [-- DYNAMIC PRUNING --] [-- RECENCY ANCHOR --]
    Biaya: Read Cache (10-25%) Biaya: Drop / Minify   Biaya: Full Input (100%)
```

Optimasi konteks dan rekayasa biaya (*cost engineering*) beroperasi pada irisan tiga prinsip fundamental:
1.  **Token Asymmetry:** Token input berharga jauh lebih murah (1x) dibandingkan token output (3x - 5x), namun token input mendominasi 95% volume data pada arsitektur Enterprise RAG dan Autonomous Agent.
2.  **KV Cache Persistence (Prompt Caching):** LLM gateway modern dapat menyimpan representasi tensor KV cache dari segmen token yang berulang. Cache read berharga 75%–90% lebih murah daripada cache write/uncached processing dan memangkas *Time-To-First-Token* (TTFT) secara drastis.
3.  **Information Density vs. Attention Dilution:** Menambahkan teks dokumen mentah ke dalam konteks menimbulkan fenomena *needle-in-a-haystack degradation* dan memicu halusinasi ketika *signal-to-noise ratio* (SNR) menurun drastis di area tengah konteks window.

---

### 3. Why It Matters

Dalam skala enterprise, inefisiensi pengelolaan konteks secara langsung merusak viabilitas ekonomi dan stabilitas sistem.

*   **Penyusutan Margin Finansial:** Misalkan sebuah sistem Customer Support Agent melayani $100.000$ interaksi per hari. Jika setiap panggilan menyertakan riwayat percakapan tidak terkompresi sebesar $15.000$ token menggunakan model berbiaya $\$3,00$ per 1M input tokens, biaya input harian mencapai $\$4.500$ (sekitar $\$135.000$/bulan). Dengan dynamic pruning dan prompt caching terstruktur (mencapai $80\%$ cache hit dan pemangkasan token $50\%$), konsumsi token dapat dipangkas hingga tersisa $\$675$/hari—menghemat lebih dari $\$1,3$ juta per tahun.
*   **Latensi Sistem dan SLA Breach:** Waktu komputasi pre-fill token berbanding lurus dengan panjang input token yang belum di-*cache*. Input sebesar $64\text{k}$ token tanpa caching dapat menghasilkan TTFT lebih dari 4–8 detik, menyebabkan *timeout* pada downstream reverse proxy dan melanggar SLA aplikasi interaktif real-time.
*   **Degradasi Penalaran Deterministik (*Context Rotting*):** Dokumen berulang, boilerplate HTML/JSON yang redundan, serta *chat history* usang mengacaukan matriks atensi LLM. Model kerap mengabaikan instruksi sistem utama ketika dikubur di bawah riwayat log yang masif.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur pipeline optimasi konteks berikut dirancang untuk mencegat (*intercept*), membedah, memangkas, dan menata ulang *prompt payload* sebelum mencapai API endpoint penyedia LLM.

```
+---------------------------------------------------------------------------------------+
|                                CONTEXT OPTIMIZATION ENGINE                            |
+---------------------------------------------------------------------------------------+
                                           |
                                    [Raw Input Data]
                                           |
                                           v
                          +---------------------------------+
                          | 1. Token Profiler & Budgeter    |
                          |    - Compute Tiktoken / Byte-Pair|
                          |    - Check Token Quota Allocation|
                          +---------------------------------+
                                           |
                                           v
                          +---------------------------------+
                          | 2. Structural Content Minifier  |
                          |    - Strip JSON / Whitespace    |
                          |    - Remove Markdown Redundancy |
                          +---------------------------------+
                                           |
                                           v
                          +---------------------------------+
                          | 3. Dynamic Relevance Pruner     |
                          |    - BM25 / Cross-Encoder Score |
                          |    - Drop low SNR Chunks        |
                          +---------------------------------+
                                           |
                                           v
                          +---------------------------------+
                          | 4. Context Re-ordering Engine   |
                          |    - U-Shaped Attention Layout  |
                          |    - Inject Recency Anchors     |
                          +---------------------------------+
                                           |
                                           v
                          +---------------------------------+
                          | 5. Deterministic Cache Aligner  |
                          |    - Canonical Prefix Partition |
                          |    - Static vs Dynamic Split    |
                          +---------------------------------+
                                           |
                     +---------------------+---------------------+
                     |                                           |
                     v                                           v
        [Prompt Caching Checkpoint]                 [Ephemeral Tail Segment]
   (System Prompts + Core Schemas)             (Pruned Context Docs + User Query)
   Size: >= 1024 / 2048 tokens                 Size: Variable (Strict Budget)
                     \                                           /
                      \                                         /
                       v                                       v
                     +-------------------------------------------+
                     |  Upstream LLM Provider (Cached Gateway)   |
                     |  - Cache Hit Read: 10-20% Baseline Cost   |
                     |  - TTFT Acceleration: Up to 80% Faster    |
                     +-------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanika Prompt Caching (Prefix Matching)
Penyedia LLM (seperti Anthropic Prompt Caching atau OpenAI Ephemeral Caching) mengindeks KV Cache berdasarkan *cryptographic hash* dari urutan token yang identik secara berurutan, dimulai dari indeks token `0`.
*   **Persyaratan Titik Henti (Checkpoint Boundaries):** Cache bersifat strictly sequential. Jika satu spasi atau karakter berubah di token ke-10, seluruh KV cache dari token ke-10 hingga token ke-$N$ invalid dan harus dikomputasi ulang.
*   **Threshold Minimum:** Cache hanya aktif jika panjang prefix memenuhi ambang batas minimum penyedia (misal: 1.024 token untuk Claude 3.5 Sonnet; 1.024 token untuk GPT-4o).
*   **Struktur Partisi Konteks:**
    1.  *Tier 1: Static System Prefix* (instruksi permanen, tool definitions, skema JSON) $\rightarrow$ **Cached**.
    2.  *Tier 2: Few-Shot Library* (contoh-contoh statis terverifikasi) $\rightarrow$ **Cached**.
    3.  *Tier 3: Semistatis Context Base* (knowledge base umum yang jarang diperbarui) $\rightarrow$ **Cached**.
    4.  *Tier 4: Dynamic Working Memory* (retrieve documents, conversational buffer) $\rightarrow$ **Uncached**.
    5.  *Tier 5: Ephemeral Trigger* (pertanyaan user terkini, output instruction) $\rightarrow$ **Uncached**.

#### B. Dynamic Relevance Pruning
Alih-alih meloloskan seluruh dokumen RAG yang lolos tahap similarity search, Pruning Engine melakukan penyaringan tahap dua (*second-stage filtering*):
*   **Semantic Scoring Gate:** Menghitung skor cross-entropy atau lexical overlap terhadap query terkini. Dokumen dengan nilai relevansi di bawah ambang batas dinamis $\tau$ langsung dieliminasi.
*   **Structural Minification:** Dokumen JSON mentah dikonversi menjadi format ringkas (misalnya representasi berbasis YAML terkompresi atau TSV/CSV) yang mempertahankan relasi hierarkis namun mengeliminasi 30-50% karakter sintaksis penutup (`{}`, `[]`, spasi indentasi ganda).

#### C. Topologi Penataan U-Shaped Attention (*Lost-in-the-Middle Mitigation*)
Berdasarkan temuan empiris Liu et al. (2023), LLM Transformer mempertahankan informasi secara optimal pada 10% awal konteks (karena adanya *attention sink* dan proximity ke instruksi) dan 10% akhir konteks (karena ketiadaan token intervening sebelum generasi decoder). 

Struktur perakitan token optimal:
1.  **Slot 1 (Indeks 0 hingga $0.1N$):** System Prompt, Operational Boundaries, Core Few-Shot Examples.
2.  **Slot 2 (Indeks $0.1N$ hingga $0.3N$):** Dokumen dengan skor relevansi tertinggi ke-1 dan ke-2.
3.  **Slot 3 (Indeks $0.3N$ hingga $0.7N$):** Dokumen dengan skor relevansi sedang (*context payload* terendah dari hasil seleksi).
4.  **Slot 4 (Indeks $0.7N$ hingga $0.9N$):** Dokumen dengan skor relevansi tertinggi ke-3.
5.  **Slot 5 (Indeks $0.9N$ hingga $1.0N$):** Critical Constraints, Query User, and Recency Anchoring Prompts (*"Berdasarkan data di atas, jawab pertanyaan berikut..."*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *high-performance Context Optimizer* dalam Python yang mencakup token budgeting, canonical prefix partitioning untuk prompt caching, text structural compression, dan penataan U-shaped attention.

```python
"""
Production Context Window Optimization & Cost Engineering Engine.
Architecture: Clean Architecture, zero global state, typed, resilient.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

import tiktoken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContextOptimizer")


class CacheControlFlag(str, Enum):
    EPHEMERAL = "ephemeral"
    NONE = "none"


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    relevance_score: float  # Scale 0.0 to 1.0 (e.g., from cross-encoder)
    token_count: int = field(init=False)

    def __post_init__(self) -> None:
        # Approximate or assign token count during instantiation
        object.__setattr__(
            self,
            "token_count",
            len(tiktoken.get_encoding("cl100k_base").encode(self.content)),
        )


@dataclass(frozen=True)
class TokenBudgetConfig:
    max_total_tokens: int
    reserved_output_tokens: int
    min_system_prefix_tokens: int = 1024  # Provider cache threshold
    target_utilization_ratio: float = 0.90


@dataclass
class OptimizedPromptPackage:
    system_instruction: str
    cached_prefix_blocks: List[Dict[str, Any]]
    dynamic_payload_blocks: List[Dict[str, Any]]
    total_input_tokens: int
    estimated_cost_usd: float
    is_cache_eligible: bool


class TokenCounterProtocol(Protocol):
    def count_tokens(self, text: str) -> int:
        ...


class TiktokenTokenizer:
    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        try:
            self._encoder = tiktoken.get_encoding(encoding_name)
        except Exception as err:
            logger.error("Failed to load tiktoken encoding %s: %s", encoding_name, err)
            raise

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoder.encode(text, disallowed_special=()))


class StructuralMinifier:
    """Minifies structured text, markdown, and JSON to eliminate structural waste."""

    @staticmethod
    def minify_json(raw_json_str: str) -> str:
        try:
            parsed = json.loads(raw_json_str)
            return json.dumps(parsed, separators=(",", ":"))
        except json.JSONDecodeError:
            return raw_json_str

    @staticmethod
    def minify_prose(text: str) -> str:
        # Collapse multiple spaces, newlines, and strip edge tokens
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


class ContextWindowOptimizer:
    """
    Main Context Engine responsible for pruning, budgeting, U-shaped arrangement,
    and cache-prefix alignment.
    """

    # Model: Claude 3.5 Sonnet Pricing Reference (per 1,000,000 tokens)
    COST_PER_MILLION_INPUT_WRITE = 3.75  # Cache write
    COST_PER_MILLION_INPUT_READ = 0.30   # Cache read hit
    COST_PER_MILLION_INPUT_REGULAR = 3.00 # Standard non-cached input

    def __init__(
        self,
        budget_config: TokenBudgetConfig,
        tokenizer: Optional[TokenCounterProtocol] = None,
    ) -> None:
        self.config = budget_config
        self.tokenizer = tokenizer or TiktokenTokenizer()
        self.minifier = StructuralMinifier()

    def _calculate_cost(
        self, uncached_tokens: int, cached_tokens: int, is_subsequent_call: bool = True
    ) -> float:
        regular_cost = (uncached_tokens / 1_000_000.0) * self.COST_PER_MILLION_INPUT_REGULAR
        if is_subsequent_call:
            cache_cost = (cached_tokens / 1_000_000.0) * self.COST_PER_MILLION_INPUT_READ
        else:
            cache_cost = (cached_tokens / 1_000_000.0) * self.COST_PER_MILLION_INPUT_WRITE
        return regular_cost + cache_cost

    def _sort_u_shaped(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Sorts chunks such that high relevance is placed at both the beginning
        and the end of the context segment, with medium relevance in the middle.
        """
        if len(chunks) <= 2:
            return chunks

        # Sort descending by relevance score
        sorted_chunks = sorted(chunks, key=lambda x: x.relevance_score, reverse=True)
        
        left_side: List[DocumentChunk] = []
        right_side: List[DocumentChunk] = []

        for idx, chunk in enumerate(sorted_chunks):
            if idx % 2 == 0:
                left_side.append(chunk)
            else:
                right_side.append(chunk)

        # Invert right side so high priority is at the outer tail
        right_side.reverse()
        return left_side + right_side

    def optimize_and_package(
        self,
        system_prompt: str,
        few_shot_examples: str,
        retrieved_documents: List[DocumentChunk],
        user_query: str,
        force_cache: bool = True,
    ) -> OptimizedPromptPackage:
        """
        Executes end-to-end compaction, cache bounding, and payload assembly.
        """
        # Step 1: Minify System Prompts and Queries
        clean_sys_prompt = self.minifier.minify_prose(system_prompt)
        clean_few_shot = self.minifier.minify_prose(few_shot_examples)
        clean_query = self.minifier.minify_prose(user_query)

        # Combine static cache candidate
        static_prefix_text = f"{clean_sys_prompt}\n\n=== EXAMPLES ===\n{clean_few_shot}"
        static_prefix_tokens = self.tokenizer.count_tokens(static_prefix_text)

        # Check cache eligibility threshold
        is_cache_eligible = (
            force_cache and static_prefix_tokens >= self.config.min_system_prefix_tokens
        )

        # Step 2: Calculate Usable Dynamic Token Budget
        usable_budget = int(
            self.config.max_total_tokens * self.config.target_utilization_ratio
        )
        query_tokens = self.tokenizer.count_tokens(clean_query)
        reserved_overhead = self.config.reserved_output_tokens + query_tokens
        
        available_context_budget = usable_budget - static_prefix_tokens - reserved_overhead
        if available_context_budget <= 0:
            raise ValueError(
                f"Static prefix ({static_prefix_tokens} tokens) and queries "
                f"exceed total allowed budget ({usable_budget} tokens)."
            )

        # Step 3: Dynamic Relevance Pruning
        # Filter chunks by relevance score threshold and fit into budget
        sorted_by_score = sorted(
            retrieved_documents, key=lambda d: d.relevance_score, reverse=True
        )
        
        accepted_chunks: List[DocumentChunk] = []
        consumed_tokens = 0

        for chunk in sorted_by_score:
            minified_content = self.minifier.minify_prose(chunk.content)
            chunk_tokens = self.tokenizer.count_tokens(minified_content)
            
            # Prune threshold: ignore zero/very low relevance
            if chunk.relevance_score < 0.25:
                continue

            if consumed_tokens + chunk_tokens <= available_context_budget:
                accepted_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk.chunk_id,
                        content=minified_content,
                        relevance_score=chunk.relevance_score,
                    )
                )
                consumed_tokens += chunk_tokens
            else:
                # Budget saturated
                logger.warning(
                    "Context budget reached. Pruning remaining %d documents.",
                    len(sorted_by_score) - len(accepted_chunks),
                )
                break

        # Step 4: U-Shaped Spatial Arrangement
        reordered_chunks = self._sort_u_shaped(accepted_chunks)

        # Step 5: Assembly of Cache Blocks and Payload Blocks
        cached_blocks: List[Dict[str, Any]] = []
        if is_cache_eligible:
            cached_blocks.append(
                {
                    "type": "text",
                    "text": static_prefix_text,
                    "cache_control": {"type": CacheControlFlag.EPHEMERAL.value},
                }
            )
        else:
            cached_blocks.append({"type": "text", "text": static_prefix_text})

        # Assemble dynamic context
        context_body = "\n\n".join(
            [f"<doc id='{c.chunk_id}'>{c.content}</doc>" for c in reordered_chunks]
        )
        
        dynamic_blocks: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": f"<context_payload>\n{context_body}\n</context_payload>",
            },
            {
                "type": "text",
                "text": f"<user_query>\n{clean_query}\n</user_query>",
            },
        ]

        total_input_tokens = (
            static_prefix_tokens + consumed_tokens + query_tokens
        )
        
        estimated_cost = self._calculate_cost(
            uncached_tokens=consumed_tokens + query_tokens,
            cached_tokens=static_prefix_tokens if is_cache_eligible else 0,
            is_subsequent_call=True,
        )

        return OptimizedPromptPackage(
            system_instruction=clean_sys_prompt,
            cached_prefix_blocks=cached_blocks,
            dynamic_payload_blocks=dynamic_blocks,
            total_input_tokens=total_input_tokens,
            estimated_cost_usd=estimated_cost,
            is_cache_eligible=is_cache_eligible,
        )


# ==========================================
# Verification & Functional Demonstration
# ==========================================
if __name__ == "__main__":
    # Inisialisasi mock token budget
    config = TokenBudgetConfig(
        max_total_tokens=4096,
        reserved_output_tokens=512,
        min_system_prefix_tokens=100,  # Diturunkan untuk unit test demonstration
        target_utilization_ratio=0.95,
    )
    optimizer = ContextWindowOptimizer(budget_config=config)

    # 1. Definisi Konten
    sys_prompt = "You are an elite Enterprise Financial Analyst Agent. Answer strictly using factual data."
    few_shot = "Q: Margin 2022? A: 14.5%.\nQ: Margin 2023? A: 18.2%."
    
    docs = [
        DocumentChunk("DOC_001", "Competitor acquisitions increased overall burn rate by 12% in Q3.", 0.88),
        DocumentChunk("DOC_002", "Unrelated disclaimer: Cookies are used on our tracking portals.", 0.05), # Expected to be pruned
        DocumentChunk("DOC_003", "Net operational profit stood at $4.2M, beating wall street estimates.", 0.95),
        DocumentChunk("DOC_004", "Employee headcount grew from 1,200 to 1,450 across all branches.", 0.62),
    ]
    query = "Summarize the primary financial drivers for the recorded operational profit."

    # 2. Eksekusi Optimasi
    result = optimizer.optimize_and_package(
        system_prompt=sys_prompt,
        few_shot_examples=few_shot,
        retrieved_documents=docs,
        user_query=query,
    )

    print("=== SUMMARY HASIL OPTIMASI KONTEKS ===")
    print(f"Total Input Tokens      : {result.total_input_tokens}")
    print(f"Cache Eligible          : {result.is_cache_eligible}")
    print(f"Estimated Cost (USD)    : ${result.estimated_cost_usd:.6f}")
    print("\nStruktur Dynamic Blocks Payload:")
    for b in result.dynamic_payload_blocks:
        print(f"--- BLOCK TYPE: {b['type']} ---")
        print(b["text"][:150] + "...\n")
```

---

### 7. Edge Cases & Failure Modes

*   **Cache Invalidation Thrashing:** 
    *   *Penyebab:* Menyisipkan metadata dinamis (seperti `datetime.utcnow()`, `request_id`, atau `user_ip`) ke dalam system prompt atau awal prefix cache.
    *   *Dampak:* Cache misses mencapai 100%, menghapus keuntungan finansial dan menambah latensi write cache terus menerus.
    *   *Solusi:* Isolasi parameter dinamis secara mutlak ke dalam *Ephemeral Tail Segment* di bagian akhir prompt.
*   **Syntactic Truncation Corruption:**
    *   *Penyebab:* Pemotongan token secara paksa di tengah payload struktural (misalnya, memotong string JSON valid pada karakter ke-$K$).
    *   *Dampak:* LLM menghasilkan decoding failure, me-looping kurung kurawal tanpa henti, atau halusinasi syntax schema.
    *   *Solusi:* Selalu validasi struktur setelah pruning. Jika parsing gagal, terapkan *structural drop-level* (menghapus objek node utuh) alih-alih *byte-level cut*.
*   **Tokenizer Discrepancy Multi-Tenancy:**
    *   *Penyebab:* Menggunakan tokenizer OpenAI (`cl100k_base` atau `o200k_base`) untuk menghitung estimasi kuota pada model Anthropic Claude atau Google Gemini.
    *   *Dampak:* Perbedaan perhitungan token sebesar 5–18%, memicu HTTP 400 (`context_length_exceeded`) mendadak pada *traffic peak*.
    *   *Solusi:* Buat provider-specific tokenizer adapter yang menggunakan byte-level safety margin konservatif (buffer 5% dari total context).

---

### 8. Trade-offs & Alternatif Solusi

| Pendekatan | Latency (TTFT) | Biaya Inferensi | Integritas Semantik | Kompleksitas Arsitektur |
| :--- | :--- | :--- | :--- | :--- |
| **Full Uncut Context** | Sangat Buruk (High TTFT) | Ekstrem ($$$$) | Tinggi (namun rentan Lost-in-the-Middle) | Sangat Rendah |
| **Map-Reduce Summarization** | Buruk (Multi-call latency) | Tinggi (Biaya API summarizer) | Sedang (Resiko bias reduksi fakta penting) | Tinggi |
| **Vector RAG Top-K Naif** | Cepat | Rendah | Rendah (Fragmentasi informasi & missing edge) | Rendah |
| **Dynamic Pruning + KV Caching (Solusi Desain)** | Sangat Cepat (Cache Read) | Sangat Rendah ($) | Sangat Tinggi (Terfilter & U-Shaped aligned) | Menengah-Tinggi |

---

### 9. Best Practices & Standard Industri

1.  **Strict Cache-Partition Separation:** Terapkan pemisahan tegas menggunakan tag identifikasi deklaratif. Seluruh static context di atas garis partisi dilarang memiliki mutasi satu spasi pun antar *thread session*.
2.  **Enforce Dynamic XML Delimiters:** Gunakan XML delimiters `<context>`, `<rules>`, `<data>` karena model foundation modern (Claude, GPT, Command R) telah di-*pre-train* untuk mengenali batasan spasial XML secara probabilistik lebih konsisten dibandingkan tanda kurung biasa atau triple markdown backticks.
3.  **Circuit Breaker & Fallback Escalation:** Jika context window upstream mengalami limitasi quota mendadak, engine harus memiliki eskalasi otomatis:
    *   *Level 1:* Drop dokumen dengan relevansi $< 0.5$.
    *   *Level 2:* Konversi tabular/JSON menjadi extractive prose bullet points.
    *   *Level 3:* Degradasikan ke fallback model dengan context window lebih besar dan biaya rendah (misal: Claude 3.5 Haiku atau GPT-4o-mini).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertindak sebagai AI Architect yang diminta memperbaiki sistem Enterprise Knowledge Retrieval yang saat ini membakar biaya API sebesar $\$500$/hari dengan rata-rata TTFT mencapai $6,2$ detik akibat meloloskan $35\text{k}$ token log transaksi mentah pada setiap query.

#### Langkah Pengerjaan
1.  **Setup Project Environment:**
    ```bash
    mkdir -p context-optimization-lab && cd context-optimization-lab
    python3 -m venv venv && source venv/bin/activate
    pip install tiktoken requests pydantic
    ```
2.  **Profiling Baseline:** Tulis skrip profiling untuk mengevaluasi prompt tanpa optimasi sepanjang $30.000$ token. Hitung estimasi biaya harian dengan asumsi volume $10.000$ call/hari pada GPT-4o.
3.  **Implementasi Pipeline Optimasi:** Integrasikan implementasi `ContextWindowOptimizer` dari Bagian 6 ke dalam service code Anda.
4.  **Eksekusi Minifikasi & Sorting U-Shaped:** Masukkan mock context 20 dokumen finansial dengan variasi relevansi $0.1$ hingga $0.98$.
5.  **Verifikasi Target Metrik:**
    *   Pastikan total input tokens tereduksi minimal **50%**.
    *   Pastikan struktur system prompt dan few-shot examples di-serialize pada urutan paling awal untuk memicu cache tag.
    *   Verifikasi dokumen dengan relevansi $<0.25$ di-drop secara deterministik.
    *   Periksa urutan dokumen akhir untuk memastikan chunk relevansi tertinggi menempati posisi paling awal dan paling akhir dari segmen dokumen.