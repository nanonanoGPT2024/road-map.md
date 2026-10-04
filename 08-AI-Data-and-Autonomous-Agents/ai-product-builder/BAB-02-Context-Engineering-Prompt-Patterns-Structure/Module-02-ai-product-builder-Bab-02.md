# Kurikulum Enterprise: AI Product Builder
## Bab 02: Context Engineering, Prompt Patterns, & Structured Output
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Senior/Staff Engineer diharapkan mampu:

1. **Merancang Dynamic Context Assembly Pipeline** yang mengelola token budget secara deterministik menggunakan algoritma *knapsack/greedy pruning* untuk mencegah *context overflow* dan degradasi model (*Lost-in-the-Middle*).
2. **Mengoptimalkan Token Latency & Operational Cost** melalui eksploitasi *Prompt Caching / KV-Cache Hit Optimization* (Anthropic Prompt Caching, vLLM Chunked Prefill, dan OpenAI Cached Tokens) dengan menyusun hierarki context statis-ke-dinamis.
3. **Mengimplementasikan Constrained Decoding & Schema Ingestion Engine** menggunakan Pydantic v2, JSON Schema, dan Context-Free Grammars (CFG) untuk menghasilkan output terstruktur dengan jaminan sintaksis 100% (*Zero-Parser-Failure*).
4. **Membangun Resilient Self-Healing Output Pipeline** yang mendeteksi anomali skema, mengeksekusi *in-flight grammar correction*, dan melakukan *reflection/repair loops* secara otomatis dengan latensi minimal.
5. **Mengaudit & Mengukur Robustness Pola Prompting** menggunakan metrik evaluasi formal (*Exact Match, Semantic F1, Schema Conformance Rate, Token Efficiency Ratio*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam pada:

- **Tokenization Mechanics**: Byte-Pair Encoding (BPE), WordPiece, dan kalkulasi rasio token-to-character pada berbagai famili model (tiktoken, HuggingFace tokenizers).
- **Transformer Inference Lifecycle**: Mekanisme *Prefill Phase* vs *Decode Phase*, Time-To-First-Token (TTFT), Inter-Token Latency (ITL), dan batasan memori KV Cache ($2 \times 2 \times n_{\text{layers}} \times n_{\text{heads}} \times d_{\text{head}} \times \text{seq\_len}$).
- **Modern Python Architecture**: Python 3.11+, `asyncio` concurrency, static typing (`typing`, `TypeVar`), Pydantic v2 Core mechanics (`TypeAdapter`, dynamic model generation).
- **Network & API Fundamentals**: SSE (*Server-Sent Events*) streaming, gRPC/REST transport, HTTP/2 multiplexing.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Fenomena "Lost-in-the-Middle" & U-Shaped Attention Curve
Penelitian empiris (Liu et al., 2023) membuktikan bahwa transformer decoder-only berbasis self-attention tidak memiliki distribusi atensi yang seragam di seluruh rentang *context window*. Kurva retrieval performance mengikuti bentuk huruf **U**:

$$\text{Attention Weight} \propto \frac{\exp(Q_i K_j^T / \sqrt{d_k})}{\sum_m \exp(Q_i K_m^T / \sqrt{d_k})}$$

Tokens yang berada di **10% awal (Primacy Effect)** dan **10% akhir (Recency Effect)** menerima bobot atensi optimal. Informasi krusial yang ditempatkan di palung tengah (middle 20%–80%) mengalami degradasi retrieval rate hingga 40–70% seiring membesarnya context ($N > 16k\text{ tokens}$).

```
Retrieval
Accuracy
 100% |  \                                            /
      |   \                                          /
  50% |    \                                        /
      |     \______________________________________/
   0% +------------------------------------------------->
      0% (System/Prefix)     50% (Payload)      100% (Instruction)
                      Token Index Position
```

#### B. KV Cache Mechanics & Deterministic Prefix Caching
Dalam distributed serving engine (vLLM, TensorRT-LLM) dan proprietary APIs (Anthropic, OpenAI), prompt tokens di-*prefill* menjadi pasangan key-value vector di GPU VRAM. Jika sequential requests memiliki token sequence prefix yang **identik secara biner (byte-for-byte exact match)**, serving engine dapat melompati komputasi prefills menggunakan shared memory blocks (*PagedAttention*).

**Kaidah Invalidation KV-Cache:**
1. Perubahan satu karakter (termasuk whitespace atau timestamp) di token index $k$ akan menginvalidasi seluruh KV Cache dari index $k$ hingga $N$.
2. Urutan penyusunan context harus mengikuti aturan keabadian:
   $$\text{Context} = [\text{System Invariant}] + [\text{Static Few-Shot}] + [\text{Dynamic RAG}] + [\text{User Query}]$$

#### C. Constrained Decoding & Grammar-Guided Generation
Parsing regex atau `try-except json.loads()` manual adalah *anti-pattern* pada skala produksi. Sistem modern menggunakan **Constrained Decoding**:
- **Logit Masking via Context-Free Grammar (CFG)**: Saat decoding token $t_{i}$, engine memeriksa Finite-State Machine (FSM) dari JSON Schema. Token-token dalam vocabulary yang menyebabkan invalid JSON dialokasikan nilai logit $-\infty$.
- Model secara matematis **mustahil** memancarkan token yang melanggar skema grammar yang telah ditentukan.

---

### 4. Why & What

| Dimensi | Naive Prompt Engineering | Production Context Engineering |
| :--- | :--- | :--- |
| **Definisi** | Menulis teks instruksi natural language secara ad-hoc ke dalam model. | Arsitektur deterministik perakitan data, pemetaan memori, dan kompilasi batasan payload. |
| **Integritas Output** | Output berbasis probabilitas, bergantung pada instruksi teks ("Return only JSON"). | Jaminan skema level deterministik melalui grammars/logit masking & Type Validation. |
| **Token Budgeting** | Mengabaikan batasan token hingga terjadi `ContextWindowExceededError`. | Dynamic knapsack allocation, greedy trimming, rolling context window. |
| **Efisiensi Biaya** | Setiap request memicu *full recomputation* komputasi prefill GPU. | Memaksimalkan KV Cache Hit Rate (>80%), menurunkan TTFT hingga 70-90%. |
| **Error Handling** | Mengandalkan regex fallback yang rapuh saat format output meleset. | Algoritma *in-flight grammar correction* dan *reflection-based deterministic repair*. |

---

### 5. How (Workflow Detail)

Pipeline end-to-end Context Engineering kelas enterprise beroperasi melalui 7 tahapan sekuensial:

```
[Raw User Payload] 
       │
       ▼
[1. Token Budget Allocation Engine]
       │  (Alokasi kuota per layer: System, Tools, Examples, RAG, Query)
       ▼
[2. Cache-Optimized Context Assembler]
       │  (Menyusun static prefix invariant -> dynamic volatile suffix)
       ▼
[3. Dynamic Few-Shot Vector Ingestion]
       │  (Sampling N-contoh relevan berdasarkan MMR/Semantic Similarity)
       ▼
[4. Schema & Grammar Compilation]
       │  (Pydantic model -> JSON Schema -> FSM / Grammar Masking)
       ▼
[5. Inference Execution (LLM / Engine API)]
       │  (Constrained generation via Logit Biasing / Function Calling)
       ▼
[6. Streaming Validation & Fast-Fail Parser]
       │  (Validasi stream token parsial; abort cepat jika terjadi schema anomaly)
       ▼
[7. Output Reflection / Self-Healing Loop (Optional)]
       │  (Jika schema validation gagal -> Re-inject anomaly diff ke model)
       ▼
[Validated Structured Domain Model]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Memori Komputer vs Context Window
- **System Instructions & Few-Shot (Static Prefix)** $\approx$ **ROM / OS Kernel Code**. Nilainya statis, tidak berubah antar request, dan di-*cache* langsung di L1/L2 GPU Cache (KV Cache).
- **Dynamic Context / RAG Payload** $\approx$ **RAM (Random Access Memory)**. Dialokasikan secara dinamis sesuai kebutuhan transaksi, dipangkas jika terjadi alokasi berlebih.
- **User Query & Immediate Scratchpad** $\approx$ **CPU Registers**. Tempat eksekusi instruksi langsung yang memiliki visibilitas prioritas tertinggi.

#### Arsitektur Context Assembler & Parser Pipeline

```
+---------------------------------------------------------------------------------------+
| CONTEXT INGESTION & CACHE-ALIGNED PIPELINE                                            |
+---------------------------------------------------------------------------------------+
  [Static System Prompt]       [Static Few-Shot Examples]   <- CACHEABLE PREFIX (Hit!)
  SHA256: 0x9A4B12C...         SHA256: 0xFD89A12...            (Biaya: 10-20% Prefill)
+----------------------------+----------------------------+
| Role: SYSTEM               | Role: SYSTEM (Examples)    |
| Content: "You are an..."   | Content: "Ex 1: {...}"     |
+----------------------------+----------------------------+
               │                            │
               └──────────────┬─────────────┘
                              ▼ (KV Cache Barrier)
+---------------------------------------------------------+
| Dynamic Context Injection (Volatile Buffer)             | <- CACHE MISS REGION
| Token Budget: Max 4000 tokens                           |    (Biaya: 100% Prefill)
|  - RAG Documents (Ordered by Descending Relevance)      |
|  - Recency-Weighted Chat History                        |
+---------------------------------------------------------+
               │
               ▼
+---------------------------------------------------------+
| User Query & Schema Target Constraint                   |
| Role: USER                                              |
| Content: "{query}\nRespond strictly via target schema." |
+---------------------------------------------------------+
               │
               ▼  [INFERENCE WITH LOGIT MASKING]
+---------------------------------------------------------+
| Constrained Generation Engine (vLLM / Guided-JSON API)  |
| State Machine: JSON Parser FSM                          |
| Invalid Tokens Masked to -Infinity                      |
+---------------------------------------------------------+
               │
               ▼
+---------------------------------------------------------+
| Pydantic v2 Core Validation Engine                      |
| If Valid -> Yield Model Instance                        |
| If Invalid -> Self-Correction Reflection Loop           |
+---------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

#### A. Simple Example: Pydantic v2 Strict Enforcement
Contoh dasar parsing terstruktur menggunakan Pydantic v2 dengan model schema generation.

```python
from typing import List, Literal
from pydantic import BaseModel, Field, ValidationError

class SecurityAlert(BaseModel):
    threat_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    cve_identifiers: List[str] = Field(default_factory=list, description="Daftar kode CVE valid, misal: CVE-2024-1234")
    mitigation_steps: str = Field(..., min_length=20)
    confidence_score: float = Field(..., ge=0.0, le=1.0)

# JSON Schema compilation untuk LLM Function Calling / Structured Outputs
json_schema = SecurityAlert.model_json_schema()
# Output json_schema siap diinjeksikan ke parameter `response_format` API
```

#### B. Practical Example: Enterprise Context Compiler & Self-Healing Pipeline
Implementasi penuh arsitektur Context Manager: token budgeting, KV cache prefix management, structured output parsing, dan self-healing loop.

```python
"""
Enterprise Context Engine & Structured Parser
Dependencies: openai>=1.30.0 pydantic>=2.7.0 tiktoken>=0.7.0
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
import tiktoken
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ContextEngine")

T = TypeVar("T", bound=BaseModel)

class FinancialTransactionAudit(BaseModel):
    transaction_id: str = Field(..., pattern=r"^TXN-[0-9]{8}-[A-Z0-9]+$")
    anomalous: bool
    risk_score: float = Field(..., ge=0.0, le=100.0)
    fraud_indicators: List[str] = Field(default_factory=list)
    reconciliation_action: str = Field(..., min_length=10)


class TokenBudgetExceededError(Exception):
    """Raised saat dynamic payload melebihi hard token budget ceiling."""
    pass


class ContextCompiler:
    """Mengompilasi context dengan penataan KV-Cache friendly dan pemangkasan dinamis."""

    def __init__(self, model_name: str = "gpt-4o", max_context_tokens: int = 8192):
        self.model_name = model_name
        self.tokenizer = tiktoken.encoding_for_model(model_name)
        self.max_context_tokens = max_context_tokens

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def assemble_context(
        self,
        system_invariant: str,
        static_few_shots: List[Dict[str, str]],
        dynamic_documents: List[str],
        user_query: str,
        reserved_output_tokens: int = 1000,
    ) -> List[Dict[str, str]]:
        """
        Menyusun messages list dengan menjamin static cacheability dan alokasi budget dinamis.
        """
        base_messages: List[Dict[str, str]] = [{"role": "system", "content": system_invariant}]
        for example in static_few_shots:
            base_messages.append(example)

        static_token_count = sum(self.count_tokens(m["content"]) for m in base_messages)
        query_token_count = self.count_tokens(user_query)
        
        # Hitung sisa budget untuk RAG / Dynamic Docs
        available_dynamic_tokens = (
            self.max_context_tokens - static_token_count - query_token_count - reserved_output_tokens
        )

        if available_dynamic_tokens < 0:
            raise TokenBudgetExceededError(
                f"Static prefix dan query ({static_token_count + query_token_count}) "
                f"melebihi limit konteks yang aman ({self.max_context_tokens - reserved_output_tokens})."
            )

        # Dynamic Documents Selection (Greedy Pruning)
        budgeted_docs: List[str] = []
        consumed_tokens = 0
        for doc in dynamic_documents:
            doc_tokens = self.count_tokens(doc)
            if consumed_tokens + doc_tokens <= available_dynamic_tokens:
                budgeted_docs.append(doc)
                consumed_tokens += doc_tokens
            else:
                logger.warning("Dynamic payload terpotong untuk menjaga KV-cache window integrity.")
                break

        injected_context = "\n---\n".join(budgeted_docs)
        user_payload = (
            f"CONTEXT REPOSITORIES:\n{injected_context}\n\n"
            f"TARGET TRANSACTION AUDIT QUERY:\n{user_query}"
        )

        base_messages.append({"role": "user", "content": user_payload})
        return base_messages


class ResilientStructuredEngine(Generic[T]):
    """Client wrapper untuk structured outputs dengan reflection repair loop."""

    def __init__(self, client: AsyncOpenAI, schema_cls: Type[T], model_name: str = "gpt-4o"):
        self.client = client
        self.schema_cls = schema_cls
        self.model_name = model_name

    async def execute_with_repair(
        self, messages: List[Dict[str, str]], max_retries: int = 2
    ) -> T:
        current_messages = list(messages)
        last_error_trace: Optional[str] = None

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=current_messages,
                    temperature=0.0,  # Wajib deterministik untuk structured parsing
                    response_format={
                        "type": "json_object"
                    },
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Model memancarkan respons kosong.")

                # Deterministic Pydantic validation
                parsed_data = self.schema_cls.model_validate_json(content)
                logger.info(f"Schema validation berhasil pada percobaan ke-{attempt + 1}.")
                return parsed_data

            except (ValidationError, json.JSONDecodeError, ValueError) as err:
                last_error_trace = str(err)
                logger.warning(f"Validation failure pada percobaan ke-{attempt + 1}: {last_error_trace}")

                if attempt == max_retries:
                    break

                # Self-Correction Reflection Loop
                repair_prompt = (
                    f"PREVIOUS RUNTIME ERROR:\n{last_error_trace}\n\n"
                    f"Perbaiki payload JSON di atas agar 100% mematuhi schema Pydantic berikut:\n"
                    f"{json.dumps(self.schema_cls.model_json_schema(), indent=2)}\n"
                    f"Keluarkan HANYA raw JSON tanpa backticks Markdown."
                )
                current_messages.append({"role": "assistant", "content": content or "{}"})
                current_messages.append({"role": "user", "content": repair_prompt})

        raise RuntimeError(f"Gagal memvalidasi output setelah {max_retries + 1} percobaan. Terakhir: {last_error_trace}")


# Orchestrator Execution Example
async def main() -> None:
    client = AsyncOpenAI(api_key="sk-mock-production-key-placeholder")
    compiler = ContextCompiler(model_name="gpt-4o", max_context_tokens=4096)

    # 1. Static Prefix (KV-Cache friendly - Tidak pernah berubah)
    system_invariant = (
        "You are an automated regulatory compliance engine. "
        "Strictly analyze transaction anomalies against SOC2 and Basel III frameworks."
    )
    
    # 2. Static Few-Shot Examples (In-context learning cacheable prefix)
    static_few_shots = [
        {
            "role": "user",
            "content": "AUDIT: TXN-20230101-ABCD | Transfer $1,000,000 to Unknown Offshore Shell",
        },
        {
            "role": "assistant",
            "content": json.dumps({
                "transaction_id": "TXN-20230101-ABCD",
                "anomalous": True,
                "risk_score": 98.5,
                "fraud_indicators": ["Unusual Jurisdiction", "High Volume Rapid Movement"],
                "reconciliation_action": "Freeze immediately and dispatch STR to AML team.",
            }),
        },
    ]

    # 3. Dynamic RAG Content
    dynamic_audit_logs = [
        "Ledger Log 10:45:01 UTC: TXN-20241024-X992 initiated by User U-9812 with IP 185.220.101.5.",
        "Velocity Alert: User U-9812 executed 12 transactions in 180 seconds across 3 geo-locations.",
    ]

    # 4. Target Query
    user_query = "Audit this payload: TXN-20241024-X992 | Total Value: $499,999 to Account KY-991."

    messages = compiler.assemble_context(
        system_invariant=system_invariant,
        static_few_shots=static_few_shots,
        dynamic_documents=dynamic_audit_logs,
        user_query=user_query,
    )

    engine = ResilientStructuredEngine(
        client=client,
        schema_cls=FinancialTransactionAudit,
        model_name="gpt-4o",
    )

    # Mocking call untuk pengujian lokal:
    logger.info("Pipeline compiled successfully. Tokens total: %d", sum(compiler.count_tokens(m['content']) for m in messages))

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Context: Bank Tier-1 Global Core Transaction Ingestion
Sebuah bank multinasional memproses $150.000$ transaksi terindikasi mencurigakan per hari dengan LLM pipeline untuk menyusun laporan *Suspicious Activity Report (SAR)*.

#### Problem
1. **Schema Drift**: Prompt natural language menghasilkan field parsing error sebesar 6.8%, menyebabkan kegagalan pipeline Apache Kafka downstream.
2. **Biaya & Latensi Prefill Melambung**: Rata-rata input context $12.000$ token per tiket audit. Tanpa prompt caching, biaya API prefill mencapai \$45.000/bulan dengan p99 Time-to-First-Token (TTFT) sebesar 4.2 detik.
3. **Lost-in-the-Middle**: 18% indikator penipuan yang terletak di tengah dump log transaksi $10.000$ token gagal diidentifikasi oleh model audit.

#### Solusi Arsitektur
1. **Penataan Prefix Berdasarkan KV Cache Boundaries**:
   - Membekukan System Prompt ($1.200$ token) dan 3 Few-Shot Examples audit ($3.000$ token) pada awal prompt secara identik.
   - Hasil: Mencapai **82% KV Cache Hit Rate** pada gateway penyedia LLM. Biaya token prefill berkurang dari \$0.005/1k token menjadi \$0.00125/1k token (turun 75%). p99 TTFT turun dari 4.2 detik menjadi 850ms.
2. **Context Window Attention Optimization**:
   - Menerapkan *Information Density Sorting*: Indikator penipuan dengan skor anomali rule-engine tinggi dipindahkan dari tengah context ke **Recency Buffer** (200 token sebelum query pengguna).
   - False-negative detection turun dari 18% ke 0.4%.
3. **Constrained JSON Ingestion & Fast-Fail Streaming**:
   - Menggunakan Pydantic v2 validation via native constrained JSON output. Kegagalan parser skema Kafka turun menjadi **0.00%**.

---

### 9. Trade-offs

```
                  ┌──────────────────────────────┐
                  │    Strict JSON Schema Mode   │
                  └──────────────┬───────────────┘
                                 │
                 ▲ Higher Guarantees / Lower Latency
                 │
  ┌──────────────┴──────────────┐  Cost & Latency Penalty  ┌──────────────────────────────┐
  │   Fast Zero-Shot Inference  │ ◄──────────────────────► │ Few-Shot + Chain-of-Thought  │
  │ (Low Latency, Higher Drift) │                          │ (High Accuracy, Token Heavy) │
  └─────────────────────────────┘                          └──────────────────────────────┘
```

| Keputusan Arsitektur | Keuntungan | Kerugian / Konsekuensi | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Strict JSON Schema vs Freeform + CoT** | Zero parsing failure; deterministic data types. | LLM kehilangan kemampuan "reasoning scratchpad" implisit sebelum menyusun token awal. | Buat field `"thinking_trace"` atau `"rationale"` di dalam schema **sebelum** field keputusan final. |
| **Dynamic Few-Shot (MMR Retrieval)** | Context relevansi sangat tinggi untuk edge cases kompleks. | Menghancurkan KV Cache hit rate karena prefix berubah setiap request. | Batasi Dynamic Few-Shot hanya pada query beresiko tinggi; gunakan Static Few-Shot untuk jalur standar. |
| **Aggressive Context Pruning (Greedy)** | Menjamin model tidak melompat keluar dari batasan token budget. | Berpotensi menghilangkan konteks latar belakang yang bernilai marginal. | Terapkan semantic compression (misal: LLMLingua) sebelum greedy truncation. |

---

### 10. Common Mistakes & Troubleshooting

#### Error 1: Dynamic KV Cache Buster di System Prompt
*Anti-pattern:*
```python
# RUSAK: Menghancurkan KV Cache setiap milidetik
system_prompt = f"You are a parser. The current timestamp is {datetime.utcnow().isoformat()}."
```
*Solusi:* Pindahkan timestamps atau request IDs ke akhir context (User prompt suffix).

#### Error 2: Schema Field Ordering Anti-Pattern
*Anti-pattern:* Meletakkan field status/kesimpulan sebelum reasoning:
```json
{
  "is_fraudulent": true,
  "complex_rationale_explanation": "..."
}
```
Transformer memprediksi token secara autoregresif dari kiri ke kanan. Menuntut model memutuskan `"is_fraudulent"` pada token pertama sebelum menulis penjelasannya memaksa tebakan acak.
*Solusi:*
```json
{
  "reasoning_and_evidence": "...",
  "is_fraudulent": true
}
```

#### Error 3: Tokenizer Mismatch saat Budget Allocation
*Anti-pattern:* Menggunakan `len(text.split()) * 1.3` atau tokenizer `cl100k_base` untuk model yang menggunakan `o200k_base`. Hal ini berujung pada silent overflow (`400 InvalidRequestError`).
*Solusi:* Gunakan modul encoding resmi sesuai target engine (`tiktoken.encoding_for_model(model_name)`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Prompt Invariance Partitioning**: Susun urutan prompt: `System Instructions` -> `Few-Shot Examples` -> `Retrieved Documents` -> `Query`.
- [ ] **KV-Cache Alignment Verification**: Pastikan 100% karakter statis prefix identik biner antar concurrent requests.
- [ ] **Thought Buffer Pattern**: Sediakan field `reasoning` sebelum field klasifikasi/boolean pada skema output JSON.
- [ ] **Token Truncation Safety Margin**: Sisakan margin minimal 500 token antara batas maksimal alokasi dan batas mutlak arsitektur model.
- [ ] **Deterministic Parameters**: Kunci `temperature=0.0`, `top_p=1.0`, dan tetapkan `seed` konstan untuk pipeline ekstraksi data.
- [ ] **Fallback / Self-Healing Architecture**: Pasang validation interceptor dengan retry reflection budget maksimal $N=2$.

---

### 12. Hands-on Practice

Buat repositori lokal dan jalankan pengujian integrasi berikut:

#### Struktur Direktori
```
hands-on/m02/
├── context_engine/
│   ├── __init__.py
│   ├── assembler.py
│   ├── schemas.py
│   └── validator.py
├── tests/
│   └── test_cache_alignment.py
└── requirements.txt
```

#### Langkah Implementasi
1. Tulis skema domain pada `schemas.py`: Buat schema `IncidentReport` dengan field `severity`, `impacted_hosts` (List IPv4), dan `root_cause_analysis`.
2. Implementasikan `assembler.py`: Buat class yang menghitung token prefix, mengaudit bytes match, dan merangkai dynamic RAG chunks.
3. Jalankan pengujian KV Cache boundary simulation di `tests/test_cache_alignment.py`:
```bash
pytest hands-on/m02/tests/test_cache_alignment.py -v
```

---

### 13. Exercise

#### Level: Easy
Ubah skema Pydantic berikut agar model dipaksa menyusun analisis multi-langkah sebelum menentukan status mitigasi, lalu validasi skema tersebut menggunakan `TypeAdapter`:
```python
class QuickFix(BaseModel):
    action_type: str
    target_id: int
    approved: bool
```
*Tujuan:* Tambahkan field `step_by_step_rationale` di urutan pertama, tetapkan constraint regex pada `target_id`, dan set batas panjang karakter minimal.

#### Level: Medium
Buat module context budgeting berbasis algoritma **Greedy Packing with Priority Weights**. Diberikan 10 potongan dokumen yang masing-masing memiliki atribut `relevance_score` (float) dan `content` (str). Algoritma harus mengisi konteks hingga maksimal $2000$ token, memprioritaskan dokumen dengan skor tertinggi tanpa melampaui token budget.

#### Level: Hard
Bangun sebuah custom validation interceptor untuk SSE Streaming response. Interceptor harus memvalidasi token JSON saat sedang di-*stream* secara inkremental (*incremental JSON parsing via partialjson/jiter*). Jika terdeteksi token melanggar pola skema sebelum stream berakhir, interceptor harus langsung memutus koneksi HTTP (`fast-abort`) untuk menghemat token dan biaya decoding.

---

### 14. Challenge

**Tantangan Sistem Real-Time:** Rancang sistem ekstraksi payload compliance untuk data laporan kepatuhan perbankan berukuran besar ($40.000$ token) dengan ketentuan:
1. Batas p95 Time-To-Complete adalah $< 5$ detik.
2. Tidak boleh menggunakan model context window besar secara langsung (karena mahal dan latensi decoding tinggi).
3. Buat rancangan arsitektur pemrosesan paralel berbasis **Map-Reduce Context Chunker** yang:
   - Memecah payload menjadi segmen yang selaras dengan boundary KV cache.
   - Menggunakan schema Pydantic parsial pada fase Map.
   - Mengonsolidasi skema akhir dengan schema reduksi pada fase Reduce.
   - Menghasilkan evaluasi output dengan jaminan *zero duplicate anomalies*.
*Tuliskan dokumen arsitektur teknis dan diagram alir state machine sistem tersebut.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)

**Q1: Apa penyebab fenomena "Lost-in-the-Middle" pada arsitektur LLM berbasis self-attention?**
- A) Kehabisan parameter weights pada feed-forward network.
- B) Penurunan bias atensi pada token di posisi tengah rentang konteks dibandingkan posisi awal dan akhir.
- C) Overflow pada register aktivasi di layer Transformer terakhir.
- D) Kesalahan decoding greedy saat membaca karakter non-ASCII.
*Kunci: B. Kurva atensi model Transformer cenderung berbentuk U (U-shaped attention curve), memprioritaskan token di awal (primacy) dan akhir (recency).*

**Q2: Karakteristik utama apa yang diwajibkan agar KV-Cache prefix hit dapat terjadi pada inference server?**
- A) Hanya kesamaan nama system prompt.
- B) Kesamaan token prefix secara deterministik dan biner dari token ke-0 tanpa ada perubahan token tunggal pun.
- C) Nilai parameter `temperature` harus selalu di atas 0.7.
- D) Menggunakan model open-source tanpa fine-tuning.
*Kunci: B. Engine seperti vLLM dan Anthropic/OpenAI caching membutuhkan prefix biner yang persis sama dari indeks awal untuk menggunakan kembali KV cache blocks.*

**Q3: Mengapa parameter `temperature=0.0` sangat direkomendasikan untuk pipeline Structured Extraction?**
- A) Untuk mempercepat proses komputasi perkalian matriks GPU secara floating point.
- B) Untuk menonaktifkan sampling probabilitas stokastik dan memilih token logit tertinggi (argmax/greedy) secara deterministik.
- C) Agar model secara otomatis mengabaikan batas context window.
- D) Karena format JSON membutuhkan token dengan temperature dingin agar tidak crash.
*Kunci: B. Temperature 0.0 menghasilkan greedy decoding yang konsisten dan meminimalkan variasi sintaksis skema.*

**Q4: Apa yang dimaksud dengan Constrained Decoding dalam konteks inferensi LLM?**
- A) Pembatasan jumlah token per detik yang dipancarkan oleh API.
- B) Memfilter output teks menggunakan regex string matching setelah seluruh inferensi selesai.
- C) Modifikasi logit token secara real-time pada decoding loop menggunakan grammar/FSM untuk memblokir token yang tidak valid.
- D) Pembatasan akses pengguna berdasarkan IP address dan rate limiter.
*Kunci: C. Constrained decoding meniadakan logit pada vocabulary yang menyalahi Context-Free Grammar (CFG) target.*

**Q5: Tokenizer apa yang digunakan oleh model GPT-4o untuk menghitung token secara akurat?**
- A) SentencePiece
- B) cl100k_base
- C) o200k_base
- D) WordPiece
*Kunci: C. Model GPT-4o mengadopsi encoding vocab yang lebih luas yaitu `o200k_base`.*

---

#### Intermediate (5 Soal)

**Q6: Mengapa meletakkan dynamic timestamp `Current Time: 2024-10-24T12:00:00Z` di awal system prompt dikategorikan sebagai fatal production anti-pattern?**
- A) Model tidak mengerti format ISO-8601.
- B) Menghancurkan reuse KV-Cache dari token tersebut ke bawah pada setiap detik transaksi baru.
- C) Menyebabkan context pruning engine salah menghitung integer token.
- D) Menghasilkan token NaN pada attention layer.
*Kunci: B. Setiap perubahan karakter pada token prefix awal menggagalkan prefix caching, memaksa full prefill recomputation untuk seluruh konteks berikutnya.*

**Q7: Manakah pola penataan field JSON Schema yang paling memaksimalkan akurasi klasifikasi LLM?**
- A) `{"decision": bool, "evidence_summary": str}`
- B) `{"evidence_summary": str, "decision": bool}`
- C) `{"decision": bool}` tanpa context tambahan
- D) Urutan field tidak mempengaruhi probabilitas autoregresif token LLM.
*Kunci: B. Model membutuhkan ruang token "reasoning scratchpad" sebelum memancarkan label keputusan agar dapat memanfaatkan cross-attention terhadap argumen yang baru dipancarkannya.*

**Q8: Pada Pydantic v2, fungsi method mana yang paling optimal untuk parsing langsung string JSON dari LLM tanpa overhead parsing intermediate dict Python?**
- A) `Model.parse_raw()`
- B) `Model.model_validate(json.loads(text))`
- C) `Model.model_validate_json(text)`
- D) `Model.from_orm(text)`
*Kunci: C. `model_validate_json` mengeksekusi validasi langsung pada level C/Rust core (`pydantic-core`) tanpa membuat dictionary Python intermediate, menghasilkan throughput yang jauh lebih tinggi.*

**Q9: Apa perbedaan mendasar antara Function Calling API dan Raw JSON Prompting?**
- A) Function Calling menggunakan endpoint terpisah di server backend.
- B) Function calling mengompilasi schema menjadi tool parameter types dan sering kali mengintegrasikan native logit masking langsung pada inference engine host.
- C) Raw JSON Prompting tidak memakan token input context window.
- D) Function calling tidak mendukung array dan nested object.
*Kunci: B. Function Calling/Structured Output native mengikat engine decoding loop ke grammar schema target.*

**Q10: Dalam konteks token budgeting, apa itu "Recency Buffer" dan bagaimana posisinya diatur?**
- A) Ruang memori sementara di browser pengguna.
- B) Penempatan token data krusial di akhir sequence context (dekat user query) untuk memanfaatkan Recency Effect dari kurva atensi.
- C) Mekanisme membuang 50% data terakhir dari sistem perpesanan.
- D) Database cache eksternal berbasis Redis.
*Kunci: B. Menempatkan informasi prioritas di akhir sequence context meningkatkan akurasi retrieval karena token tersebut memiliki jarak atensi terdekat dengan instruksi akhir.*

---

#### Production Scenarios (3 Soal)

**Q11: Skenario Kasus Logging Monitoring:**
Sistem parser log audit Anda menghasilkan *Pydantic ValidationError* sebesar 4.5% pada jam sibuk. Kesalahan utamanya adalah LLM menghasilkan teks penjelasan Markdown (seperti ` ```json `) yang membungkus payload output, meskipun system prompt telah menyatakan `"OUTPUT ONLY RAW JSON"`.
*Tindakan arsitektur mitigasi apa yang paling tepat tanpa menambah latensi self-healing loop?*
- A) Menambahkan kata "STRICTLY" dan huruf kapital pada system prompt.
- B) Mengaktifkan parameter native Structured Output (`response_format={"type": "json_object"}` atau JSON Schema Mode) dan menggunakan Pydantic regex pre-validator stripping.
- C) Melakukan fine-tuning model LLM open source menggunakan LoRA.
- D) Menurunkan token budget RAG context.
*Kunci: B. Mengaktifkan mode JSON terstruktur memprogram inference engine untuk menolak token pembungkus di luar syntax JSON, sementara regex stripping pre-validator membersihkan parsing edge cases pada layer aplikasi.*

**Q12: Skenario Kasus Billing & Latensi Meledak:**
Sebuah aplikasi chatbot dokumen legal menggunakan pola Few-Shot (5 contoh putusan pengadilan panjang) dan RAG dynamic search. Biaya operasional melonjak 400% dalam 1 bulan, dan p99 TTFT mencapai 6 detik. Saat dianalisis, KV-Cache hit rate berada di angka 0%.
Susunan pesan saat ini:
1. `User Query` + `Current Session ID`
2. `Dynamic Legal Documents (RAG)`
3. `System Prompt`
4. `Static Few-Shot Examples`
*Perubahan urutan pipeline apa yang WAJIB diterapkan?*
- A) Pindahkan Few-Shot ke database terpisah tanpa mengirimkannya ke konteks.
- B) Ubah urutan menjadi: 1. `System Prompt` -> 2. `Static Few-Shot Examples` -> 3. `Dynamic Documents` -> 4. `User Query` + `Session ID`.
- C) Ubah seluruh prompt menjadi representasi Base64.
- D) Panggil LLM dua kali dengan konteks terpisah lalu gabungkan string hasilnya.
*Kunci: B. KV-Cache membutuhkan urutan statis invariant di posisi indeks token paling depan agar GPU dapat memakai ulang precomputed cache blocks secara konsisten antar request pengguna.*

**Q13: Skenario Kasus Payload Context Truncation:**
Sebuah pipeline ingest invoice memproses dokumen dengan panjang token yang bervariasi antara $500$ hingga $15.000$ token. Limit konteks model target adalah $8.192$ token. Saat payload berukuran $10.000$ token masuk, pipeline crash dengan pesan `InvalidRequestError: maximum context length exceeded`.
*Strategi implementasi token budgeter apa yang paling robust untuk mengatasinya secara elegan tanpa crash?*
- A) Gunakan blok `try...except` dan abaikan dokumen yang gagal.
- B) Implementasikan greedy/rolling token budget allocation: hitung kuota token reservasi output dan static prefix, lalu terapkan dynamic document truncation (atau semantic chunk-map extraction) pada dokumen input sebelum dikirimkan ke model.
- C) Konversi teks menjadi gambar dan kirimkan ke endpoint multimodal.
- D) Tingkatkan limit timeout HTTP client ke 120 detik.
*Kunci: B. Alokasi token dinamis wajib mengkalkulasi headroom token output dan prefix invariant sebelum memotong dynamic content secara terukur menggunakan tokenizer.*

---

### 16. Summary

1. **Context Engineering Melampaui Prompt Crafting**: Perancangan konteks produksi adalah disiplin perakitan data deterministik, pengelolaan token budget, dan optimasi pemetaan memori GPU.
2. **Kepatuhan KV-Cache adalah Kunci Efisiensi Biaya**: Menjaga integritas byte-for-byte pada static prefix (System Prompt + Invariant Few-Shots) memangkas TTFT hingga 70-90% dan menurunkan biaya inferensi prefill secara signifikan.
3. **Mitigasi U-Shaped Attention**: Hindari menempatkan data paling penting di tengah-tengah rentang token panjang. Posisikan konteks krusial pada wilayah Primacy (awal) atau Recency (akhir).
4. **Zero-Parser Failure via Constrained Decoding**: Hilangkan regex parsing ad-hoc. Gunakan native JSON Schema enforcement yang dipadukan dengan validasi Pydantic v2 core dan reflection self-healing loops.
5. **Autoregressive Thought Buffering**: Susun skema keluaran terstruktur agar model memancarkan penalaran (*rationale/scratchpad*) sebelum memancarkan klasifikasi atau keputusan final.