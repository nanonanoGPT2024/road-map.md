# Kurikulum Enterprise: AI Engineer
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-04: LLM APIs, Tooling, & Orkestrasi Model
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur orkestrasi LLM multi-provider berbasis *state machine* terdistribusi yang tahan banting (*fault-tolerant*).
- Menguasai implementasi *Structured Outputs* dan *Strict Mode Tool Calling* menggunakan skema JSON deterministik (Pydantic V2) dengan validasi runtime tanpa degradasi parsing token.
- Mengimplementasikan pola arsitektur *Dynamic Provider Routing*, *Hedging Requests*, dan *Fallback Cascades* guna menjaga SLA ketersediaan 99.99% dan meminimalkan p99 latency.
- Membangun pipeline *streaming token* berbasis *Server-Sent Events* (SSE) yang terintegrasi secara asinkron dengan eksekusi paralel alat eksternal (*tool execution*).
- Menerapkan instrumentasi telemetri terpadu (OpenTelemetry/OTel) untuk pelacakan metrik kritis: *Time to First Token* (TTFT), *Time Per Output Token* (TPOT), *tokens/sec*, serta atribusi biaya inferensi per tenant secara presisi.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Python Lanjutan**: Asyncio (event loop, tasks, semaphores), metaprogramming, context manager, dan typing sistem Python 3.11+.
- **Dasar LLM APIs**: Pemanggilan RESTful API dasar (OpenAI, Anthropic), penanganan parameter inferensi (`temperature`, `top_p`, `max_tokens`, `presence_penalty`).
- **Data Serialization**: JSON Schema Draft 7/2020-12, deserialisasi data dengan Pydantic V2.
- **Networking & Protokol**: HTTP/2, multiplexing koneksi, Server-Sent Events (SSE), protokol gRPC dasar.
- **Sistem Terdistribusi**: Konsep Circuit Breaker, Exponential Backoff with Jitter, Leaky/Token Bucket Rate Limiting, dan Redis/Key-Value memory store.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanika Tool Calling & Constrained Decoding
Pada arsitektur LLM modern, *Tool Calling* (atau *Function Calling*) bukanlah proses di mana model mengeksekusi kode secara mandiri. Model bertindak sebagai *reasoning engine* yang melakukan emisi token terstruktur yang merepresentasikan niat pemanggilan fungsi (*intent to call a function*).

```
+---------------------------------------------------------------------------------------+
| LLM INFERENCE ENGINE (vLLM / SGLang / OpenAI Triton Engine)                           |
|                                                                                       |
| +-----------------------------------------------------------------------------------+ |
| | Context: System Prompt + Chat History + Tools Definitions (JSON Schema)           | |
| +-----------------------------------------------------------------------------------+ |
|                                          |                                            |
|                                          v                                            |
|                        +-----------------------------------+                          |
|                        | Autoregressive Next-Token Sampling|                          |
|                        +-----------------------------------+                          |
|                                          |                                            |
|                    Logits Distribution Over Vocabulary (V)                            |
|                                          |                                            |
|                                          v                                            |
|           +-------------------------------------------------------------+             |
|           | Grammar-Constrained Logit Bias (FSM Masking)                |             |
|           | Masking token di luar skema valid:                          |             |
|           | P(token_invalid) = -inf                                     |             |
|           +-------------------------------------------------------------+             |
|                                          |                                            |
|                                          v                                            |
|                                Deterministic Token                                    |
|                      {"name": "fetch_balance", "arguments": ...}                      |
+---------------------------------------------------------------------------------------+
```

Secara internal:
1. **Konstruksi Logit Masking via Finite State Machine (FSM):** Ketika parameter `strict: true` diaktifkan (misalnya pada OpenAI Structured Outputs atau pustaka inferensi lokal seperti *Outlines*/*SGLang*), skema JSON dikompilasi menjadi sebuah *Deterministic Finite Automaton* (DFA).
2. **Sampling Token Terpandu:** Pada setiap langkah autoregresif, DFA mengevaluasi status parsing saat ini. Logit dari token pada kosakata model ($V$) yang melanggar transisi tata bahasa yang valid akan dimanipulasi dengan nilai $-\infty$. Ini menjamin 100% kepatuhan terhadap sintaksis skema JSON target tanpa bergantung pada kemampuan model untuk menolak berhalusinasi sintaks.

#### B. Dynamic Routing & Multi-Provider Cascading
Arsitektur produksi tidak boleh bergantung pada satu *upstream model provider* (Single Point of Failure / SPOF). Diperlukan *Routing Layer* yang berada di antara aplikasi dan provider API.

```
                           +--------------------+
                           |    Client App      |
                           +--------------------+
                                      |
                                      v
                     +----------------------------------+
                     |    Model Gateway / Orchestrator  |
                     +----------------------------------+
                                      |
         +----------------------------+----------------------------+
         | (1. Check Cache)           | (2. Route Decision)        |
         v                            v                            v
+------------------+         +------------------+        +------------------+
| Semantic Cache   |         | Circuit Breaker  |        | Telemetry & Cost |
| (Vector + Redis) |         | (State Tracking) |        | Attribution (OTel|
+------------------+         +------------------+        +------------------+
                                      |
              +-----------------------+-----------------------+
              | Primary Path (Fast/Cost-Effective)            | Fallback Path (High Availability)
              v                                               v
    +--------------------+                          +--------------------+
    | Primary Provider   |                          | Secondary Provider |
    | (e.g., Anthropic)  |                          | (e.g., OpenAI /    |
    | Claude 3.5 Sonnet  |                          |  Azure Bedrock)    |
    +--------------------+                          +--------------------+
              | (Fail / Timeout > 2s)                         |
              +-----------------------------------------------+
```

Routing Layer mengelola:
1. **Circuit Breaking:** Memantau HTTP status 429 (Rate Limit Exceeded), 500/503 (Server Errors), dan metrik p99 latency. Jika ambang batas error terlampaui dalam jendela waktu geser (*sliding window*), sirkuit dialihkan ke status `OPEN`, secara instan meneruskan request ke *secondary provider*.
2. **Hedging Requests:** Untuk kasus kritis dengan SLA latensi ketat, request dapat dikirimkan ke Provider A, dan jika dalam $X$ milidetik belum ada *first chunk* (TTFT) yang diterima, request yang sama dikirimkan ke Provider B secara spekulatif (*speculative racing*). Response pertama yang valid digunakan, sementara request yang tertinggal langsung dibatalkan (*cancellation context*).

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Prototipe / Skrip Dasar) | Pendekatan Enterprise (Arsitektur Produksi) |
| :--- | :--- | :--- |
| **Parsing Output** | Regex extraction atau `json.loads()` berbasis *prompt engineering* biasa ("tolong jawab dalam format JSON"). Rawan *schema failure*. | **Strict Structured Outputs** berbasis grammar-constrained decoding (Pydantic v2 + JSON Schema compiler) yang dijamin valid pada layer inferensi. |
| **Penanganan Error** | Blok `try-except` generik dengan `sleep(1)` statis. | **Stateful Resiliency**: Exponential backoff dengan Full Jitter, Dynamic Circuit Breaker, dan Fallback Cross-Provider/Cross-Region. |
| **Latensi & Stream** | Menunggu seluruh respon terkumpul (`stream=False`), baru memicu rendering UI dan pemanggilan fungsi. | **Multiplexed SSE Streaming**: Stream token langsung diteruskan ke UI, sementara parser asinkron mendeteksi blok eksekusi tool secara paralel. |
| **Manajemen State** | Menyimpan riwayat obrolan dalam memori lokal aplikasi (RAM instance tunggal). | **Distributed Checkpointing**: State graph tersimpan di Redis/Postgres dengan transactional lock dan memory compaction/summarization. |
| **Observabilitas** | `print()` log atau logging file teks standar. | **OpenTelemetry Tracing**: Distributed tracing span per-step orkestrasi, pelacakan rasio *cache hit*, profiling TTFT/TPOT, dan alokasi cost per user. |

---

### 5. How (Workflow detail)

Alur kerja eksekusi terdistribusi dari sebuah orkestrator inferensi tingkat produksi:

```
[User Query]
     |
     v
[1. Request Normalization & Context Hydration]
     |---> Mengambil Session State dari Redis
     |---> Mengambil Metadata Tenant & Budget Constraints
     |
     v
[2. Dynamic Router Evaluation]
     |---> Cek Status Circuit Breaker tiap Provider
     |---> Pilih Engine: (Misal: Tier 1 -> OpenAI, Tier 2 -> Bedrock Claude)
     |
     v
[3. Execution Loop with Grammar Constraints]
     |---> Mengirim Request dengan Skema Tools teregistrasi (Strict Mode)
     |
     +---> [Response: Tool Call Detected?]
     |         |
     |         |-- YES --> [4. Parallel Async Tool Invocation]
     |         |                 |---> Eksekusi I/O Bound tools (DB, API eksternal)
     |         |                 |---> Validasi payload output terhadap response schema
     |         |                 +---> Format hasil eksekusi sebagai ToolMessage
     |         |                 +---> Append ke State Memory -> Loop kembali ke Step 3
     |         |
     |         +-- NO  --> [5. Stream Completion Token]
     |                           |---> Kirim token via SSE ke UI
     |                           +---> Catat TTFT dan TPOT ke OpenTelemetry Collector
     v
[6. State Persistence & Telemetry Flush]
     |---> Commit Delta State ke Distributed Storage
     +---> Catat Metrik Token Usage, Latency, Estimasi Biaya ($)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional & Menara Pengawas Udara
Bayangkan sistem orkestrasi ini sebagai **Menara Pengawas Udara (Air Traffic Control - ATC)**:
- **LLM** adalah **Pilot**: Sangat cerdas dalam bernavigasi dan mengambil keputusan kontekstual, tetapi tidak boleh mengatur jadwal pendaratan atau mengisi bahan bakar sendiri secara langsung.
- **Tools/APIs** adalah **Kru Darat (Ground Crew)**: Layanan spesialis (pengisian bahan bakar, bagasi, teknisi mekanik) yang hanya bekerja jika ada instruksi terstandarisasi.
- **Structured Outputs** adalah **Protokol Radio Standar Penerbangan (Aviation Alphabet/Format)**: Pilot tidak diizinkan berbicara santai ("Halo bro, sepertinya saya mau turun"). Pilot harus menggunakan parameter baku ("Roger, descent to flight level 100, heading 240"). Jika format salah, ATC langsung menolak instruksi tersebut.
- **Circuit Breaker** adalah **Protokol Cuaca Bandara**: Jika landasan pacu utama tertutup badai salju (upstream LLM down/rate-limited), ATC langsung mengalihkan rute pendaratan ke bandara alternatif terdekat (*fallback provider*) tanpa membiarkan pesawat kehabisan bahan bakar di udara.

#### Diagram Interaksi State Machine
```
               +----------------------------------------------------+
               |                State: INITIALIZED                  |
               +----------------------------------------------------+
                                         |
                                         v
                         +-------------------------------+
                         |      State: LLM_GENERATING    |
                         +-------------------------------+
                            /                         \
            (Tool Calls Returned)                 (Terminal Text Chunk)
                          /                             \
                         v                               v
         +-------------------------------+     +--------------------+
         |   State: PARALLEL_EXECUTING   |     |  State: STREAMING  |
         +-------------------------------+     +--------------------+
                         |                               |
              (All Tools Finished)                  (End of Stream)
                         |                               |
                         v                               v
         +-------------------------------+     +--------------------+
         |    State: APPEND_HISTORY      |     |  State: COMPLETED  |
         +-------------------------------+     +--------------------+
                         |
                         +--> (Loop ke LLM_GENERATING)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Strict Tool Definition Menggunakan Pydantic v2
Kode dasar mendefinisikan tool schema dengan *deterministic validation*:

```python
from typing import List
from pydantic import BaseModel, Field

class DatabaseQueryArgs(BaseModel):
    """Argumen untuk melakukan query data customer secara analitik."""
    customer_ids: List[str] = Field(
        description="Daftar ID customer unik (UUID format). Minimal 1, maksimal 50.",
        min_length=1,
        max_length=50
    )
    metric_type: str = Field(
        description="Metrik yang ingin di-aggregate.",
        pattern="^(churn_risk|lifetime_value|total_spend)$"
    )

# Ekstraksi schema JSON kompatibel OpenAI Function / Anthropic Tools
schema = DatabaseQueryArgs.model_json_schema()
print(schema)
```

#### B. Practical Enterprise Example: Resilient Orchestration Engine
Implementasi produksi yang menggabungkan Circuit Breaker, Exponential Jitter Backoff, Fallback Provider, dan Parallel Strict Tool Calling.

```python
import asyncio
import json
import logging
import random
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OrchestratorCore")

# ============================================================================
# 1. DOMAIN SCHEMAS & TOOLS
# ============================================================================

class StockCheckInput(BaseModel):
    sku: str = Field(description="Kode SKU inventaris, format: SKU-XXXXX")
    warehouse_id: str = Field(description="Region gudang logistik, contoh: 'JKT-01'")

class ToolExecutionResult(BaseModel):
    tool_name: str
    output: Any
    is_error: bool = False

async def execute_mock_inventory(sku: str, warehouse_id: str) -> Dict[str, Any]:
    """Simulasi pemanggilan database inventaris riil secara asynchronous."""
    await asyncio.sleep(0.15)  # Simulasi I/O delay
    if "ERROR" in sku:
        raise ValueError(f"Inventaris SKU {sku} korup atau tidak ditemukan.")
    return {"sku": sku, "warehouse": warehouse_id, "available_quantity": 42}

REGISTRY: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {
    "check_stock": lambda **kwargs: execute_mock_inventory(**kwargs)
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Periksa sisa ketersediaan stok produk pada gudang tertentu.",
            "parameters": StockCheckInput.model_json_schema(),
            "strict": True
        }
    }
]

# ============================================================================
# 2. RESILIENCY INFRASTRUCTURE: CIRCUIT BREAKER & RETRY
# ============================================================================

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit Breaker TRIPPED to OPEN. Failure count: {self.failure_count}")

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - (self.last_failure_time or 0) > self.recovery_time:
                self.state = "HALF-OPEN"
                logger.info("Circuit Breaker transitioned to HALF-OPEN.")
                return True
            return False
        return True  # HALF-OPEN

async def execute_with_retry_and_breaker(
    fn: Callable[..., Coroutine[Any, Any, Any]],
    breaker: CircuitBreaker,
    max_retries: int = 3,
    base_delay: float = 0.5,
    *args, **kwargs
) -> Any:
    if not breaker.allow_request():
        raise CircuitBreakerOpenException("Provider sirkuit saat ini OPEN. Fast failing...")

    for attempt in range(1, max_retries + 1):
        try:
            res = await fn(*args, **kwargs)
            breaker.record_success()
            return res
        except Exception as ex:
            logger.warning(f"Percobaan {attempt}/{max_retries} gagal: {str(ex)}")
            if attempt == max_retries:
                breaker.record_failure()
                raise
            # Exponential Backoff with Full Jitter
            sleep_duration = random.uniform(0, base_delay * (2 ** (attempt - 1)))
            await asyncio.sleep(sleep_duration)

# ============================================================================
# 3. DOCKING MULTI-PROVIDER SIMULATOR
# ============================================================================

async def mock_primary_provider_call(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Provider Utama: Cepat namun disimulasikan dapat mengalami intermiten 503."""
    # Simulasi intermiten kegagalan jika dipicu oleh data uji
    last_msg = messages[-1].get("content", "")
    if "TRIGGER_FAILURE" in last_msg:
        raise ConnectionResetError("HTTP 503: Provider overload.")

    await asyncio.sleep(0.2)
    # Output mock: Mengembalikan tool call pada putaran pertama
    if len(messages) == 1:
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "check_stock",
                        "arguments": json.dumps({"sku": "SKU-99011", "warehouse_id": "JKT-01"})
                    }
                }
            ]
        }
    return {"role": "assistant", "content": "Stok barang tersedia sebanyak 42 unit.", "tool_calls": None}

async def mock_secondary_provider_call(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Provider Cadangan: Latensi lebih tinggi tapi keandalan 100%."""
    await asyncio.sleep(0.4)
    if len(messages) == 1:
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_sec999",
                    "type": "function",
                    "function": {
                        "name": "check_stock",
                        "arguments": json.dumps({"sku": "SKU-99011", "warehouse_id": "JKT-01"})
                    }
                }
            ]
        }
    return {"role": "assistant", "content": "[FALLBACK] Stok barang SKU-99011 aman: 42 unit siap dikirim.", "tool_calls": None}

# ============================================================================
# 4. ENTERPRISE ORCHESTRATION PIPELINE
# ============================================================================

class EnterpriseOrchestrator:
    def __init__(self):
        self.primary_breaker = CircuitBreaker(failure_threshold=2, recovery_time=5.0)

    async def _route_model_call(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Routing cerdas dengan circuit-breaker dan fallback cascade."""
        try:
            logger.info("Mencoba eksekusi melalui Primary Provider...")
            return await execute_with_retry_and_breaker(
                mock_primary_provider_call,
                self.primary_breaker,
                max_retries=2,
                base_delay=0.2,
                messages=messages,
                tools=TOOLS_SCHEMA
            )
        except (CircuitBreakerOpenException, Exception) as err:
            logger.error(f"Primary Provider gagal total ({err}). Dialihkan ke Secondary Fallback Provider...")
            return await mock_secondary_provider_call(messages=messages, tools=TOOLS_SCHEMA)

    async def _dispatch_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Mengeksekusi multiple tool call secara paralel dan memvalidasi output."""
        tasks = []
        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = json.loads(call["function"]["arguments"])
            handler = REGISTRY.get(fn_name)
            if not handler:
                raise NotImplementedError(f"Tool {fn_name} tidak terdaftar di runtime.")
            tasks.append(self._safe_execute_tool(call["id"], fn_name, handler, fn_args))

        return await asyncio.gather(*tasks)

    async def _safe_execute_tool(self, call_id: str, name: str, handler: Callable, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res = await handler(**args)
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(res)
            }
        except Exception as e:
            logger.error(f"Eksekusi tool {name} gagal: {e}")
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps({"error": str(e)})
            }

    async def run(self, user_query: str) -> str:
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_query}]
        max_turns = 5
        current_turn = 0

        while current_turn < max_turns:
            current_turn += 1
            logger.info(f"--- Siklus Inferensi Ke-{current_turn} ---")
            
            # Step 1: Inferensi LLM via Routing System
            response = await self._route_model_call(messages)
            messages.append(response)

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                # Terminal output tercapai
                return response.get("content") or ""

            # Step 2: Eksekusi Tool Paralel
            logger.info(f"Memproses {len(tool_calls)} Tool Call paralel...")
            tool_results = await self._dispatch_tools(tool_calls)
            
            # Step 3: Pasang hasil eksekusi kembali ke Context
            messages.extend(tool_results)

        raise TimeoutError("Eksekusi melampaui batas putaran maksimum (potensi reasoning loop).")

# ============================================================================
# 5. DEMO EKSEKUSI
# ============================================================================

async def main():
    orchestrator = EnterpriseOrchestrator()
    
    print("\n=== Uji Coba 1: Alur Normal (Primary Berhasil) ===")
    out1 = await orchestrator.run("Tolong periksa ketersediaan SKU-99011 di gudang JKT-01.")
    print(f"Hasil Akhir: {out1}\n")

    print("=== Uji Coba 2: Skenario Provider Failure (Trigger Fallback) ===")
    out2 = await orchestrator.run("TRIGGER_FAILURE: Periksa inventaris darurat.")
    print(f"Hasil Akhir: {out2}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Perusahaan**: FinTech SuperApp (Investasi, Payment, dan Pinjaman).
- **Beban Sistem**: 120.000 request per menit (RPM) pada jam sibuk bursa saham.
- **SLA**: TTFT $\le 800\text{ ms}$, p99 Latency $\le 2.5\text{ s}$, Ketersediaan 99.99%.

#### Masalah Utama
1. **Model Drift & Parsing Failures**: Implementasi sebelumnya mengandalkan string-parsing Markdown codeblock JSON. Tingkat kegagalan parsing mencapai 2.4% saat load tinggi, menyebabkan kegagalan transaksi portofolio.
2. **Cascading Provider Outages**: Pada saat salah satu provider utama mengalami lonjakan error 504 Gateway Timeout, seluruh microservice customer support macet total karena retry storm.

#### Arsitektur Solusi
1. **Adopsi Strict Structured Outputs**: Semua definisi transaksi dikonversi ke *JSON Schema draft-2020-12* yang terikat langsung ke Pydantic V2 engine. Kegagalan parsing menurun dari 2.4% menjadi **0.0000%** (zero-syntax error).
2. **Distributed Hedged Requests Engine**:
   - Jika *Time-To-First-Token* (TTFT) dari Provider Utama melampaui ambang batas $650\text{ ms}$, orkestrator secara asinkron menembakkan *hedged request* identik ke Secondary Provider pada region berbeda.
   - Pemenang balapan (*winner of the race*) menyuplai streaming SSE ke client; koneksi yang kalah langsung dibatalkan via HTTP/2 `RST_STREAM`.
3. **Semantic Caching**: Memasang Redis Vector Cache di depan orchestrator. Pertanyaan faktual berulang (misal: "Berapa batas transfer harian?") dijawab langsung dalam latensi $< 25\text{ ms}$ tanpa memanggil upstream model, memangkas biaya operasional sebesar **34%**.

---

### 9. Trade-offs

```
                  Latensi Rendah (Low Latency)
                             /  \
                            /    \
                           /      \
                          /   A    \
                         /          \
  Keandalan Maksimal    /____________\   Efisiensi Biaya
 (Multi-Provider/Hedge)                   (Single Provider/No Hedge)
```

1. **Hedged Requests vs. Biaya Cloud (Cost Trade-off)**
   - *Keuntungan*: P99 latency terpangkas drastis (hingga 60%) karena memotong *tail latency* dari provider lambat.
   - *Konsekuensi*: Penggunaan token ganda jika kedua provider merespons hampir bersamaan, meningkatkan tagihan bulanan sekitar 10-15%.

2. **Strict Mode Constraints vs. Token Throughput (Performance Trade-off)**
   - *Keuntungan*: Jaminan 100% kepatuhan format JSON, parsing data tidak akan pernah gagal di layer backend.
   - *Konsekuensi*: Waktu kompilasi awal FSM (*prefix build*) dapat menambah initial delay 50-200ms pada request pertama sebuah schema unik.

3. **In-Memory Graph State vs. Distributed Checkpoint (Scalability Trade-off)**
   - *In-Memory*: Sangat cepat ($< 1\text{ ms}$ overhead), tapi rentan data loss saat pod Kubernetes mengalami *eviction/restart*.
   - *Distributed (Postgres/Redis)*: Mendukung resumable conversational long-running workflow, tapi menambah *network I/O roundtrip* pada setiap pergantian node/turn.

---

### 10. Common Mistakes & Troubleshooting

#### 1. JSON Parsing Anti-Pattern (Markdown Stripping)
* **Kesalahan**: Menulis logika pembersihan seperti `response.replace("```json", "").replace("```", "")`. Saat model menyisipkan teks natural sebelum tanda *backtick*, `json.loads` melempar `JSONDecodeError`.
* **Solusi**: Gunakan native `tools` API dengan parameter `tool_choice: {"type": "function", "function": {"name": "..."}}` atau `response_format: {"type": "json_object"}` / JSON Schema.

#### 2. Unbounded Retry Storms
* **Kesalahan**: Mengulang pemanggilan API LLM dengan fixed delay (`time.sleep(2)`) saat terkena rate limit (HTTP 429).
* **Solusi**: Terapkan algoritma **Full Jitter Exponential Backoff**:
  $$\text{Delay} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
  di mana $B$ adalah *base delay* dan $M$ adalah batas atas delay (*max ceiling*).

#### 3. Blocking the Event Loop during Tool Execution
* **Kesalahan**: Menjalankan library database sinkron (misal: `psycopg2` standard atau `requests.get`) langsung di dalam async handler tool. Hal ini membekukan event loop Node/Python dan memblokir seluruh client streaming lain.
* **Solusi**: Gunakan library non-blocking/asinkron (`httpx`, `asyncpg`) atau delegasikan fungsi sinkron ke thread terpisah:
  ```python
  loop = asyncio.get_running_loop()
  result = await loop.run_in_executor(None, synchronous_heavy_io_function, arg1)
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Validasi Skema Strict**: Selalu pasang `additionalProperties: False` pada JSON Schema tool jika provider mewajibkannya untuk *grammar-constrained compilation*.
- [ ] **Timeout Terkalibrasi**: Pasang HTTP client timeout eksplisit: Connect timeout 3 detik, Read timeout 15-30 detik.
- [ ] **Idempotency Keys**: Kirim header idempotency (misal: `X-Idempotency-Key` atau `client_request_id`) guna mencegah eksekusi mutasi ganda (pembayaran/transfer) jika koneksi terputus di tengah jalan.
- [ ] **Safe Tool Error Bubbling**: Jika tool internal crash/gagal, tangkap error-nya dan bungkus dalam payload JSON error ke model, jangan biarkan exception mematikan runtime orchestration.
- [ ] **Sanitasi Tool Input**: Terapkan validasi tipe data ketat di backend handler tool. Anggap data yang dihasilkan model sebagai data tidak aman (*untrusted input*).
- [ ] **OpenTelemetry Integration**: Cantumkan `gen_ai.system`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`, dan `gen_ai.response.model` pada distributed tracing span.
- [ ] **Cost-Cap Safeguards**: Batasi `max_tokens` dan tentukan limit loop orkestrator (`max_turns <= 5`) untuk mencegah loop alasan rekursif (*infinite reasoning loop*) yang menguras anggaran.

---

### 12. Hands-on Practice

Buatlah direktori lab untuk modul ini pada sistem lokal Anda:
`hands-on/m02/`

#### Langkah 1: Siapkan Virtual Environment & Dependencies
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic==2.6.4 httpx==0.27.0
```

#### Langkah 2: Buat File Server Simulator & Engine
Buat file `hands-on/m02/production_orchestrator.py` menggunakan implementasi yang disediakan pada **Seksi 7.B**.

#### Langkah 3: Tambahkan Scenario Testing Harness
Tambahkan kode berikut pada bagian bawah file untuk menguji skenario ekstrem (Simulasi High-Load Concurrent Calls):

```python
async def run_stress_test():
    print("\n--- MENJALANKAN STRESS TEST KONKURENSI (50 REQUEST) ---")
    orchestrator = EnterpriseOrchestrator()
    queries = [
        "Tolong periksa ketersediaan SKU-99011 di gudang JKT-01." if i % 4 != 0 
        else "TRIGGER_FAILURE: Uji keandalan saat upstream down." 
        for i in range(50)
    ]
    
    start_time = time.perf_counter()
    results = await asyncio.gather(*[orchestrator.run(q) for q in queries], return_exceptions=True)
    duration = time.perf_counter() - start_time
    
    success_count = sum(1 for r in results if isinstance(r, str))
    fail_count = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"Selesai dalam: {duration:.2f} detik")
    print(f"Sukses: {success_count} | Gagal: {fail_count}")
    print(f"Throughput: {len(queries)/duration:.2f} req/detik")

if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(run_stress_test())
```

Jalankan pengujian:
```bash
python production_orchestrator.py
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `StockCheckInput` pada Seksi 7.B agar memiliki validasi tambahan:
- `warehouse_id` hanya boleh menerima salah satu nilai dari whitelist berikut: `["JKT-01", "SBY-02", "MDN-01"]`.
- Jika argumen di luar nilai tersebut, validasi Pydantic harus menolak request sebelum dieksekusi.

#### Level Medium
Tambahkan mekanisme **Caching Layer** asinkron sederhana berbasis dictionary memory dengan TTL (*Time-to-Live*):
- Buat decorator `@async_cache(ttl_seconds=30)` yang membungkus pemanggilan model.
- Kunci cache dibentuk dari kombinasi hashing string list message input.
- Pastikan request identik yang datang berturut-turut dalam kurun waktu 30 detik dijawab seketika tanpa masuk ke fungsi inferensi.

#### Level Hard
Rancang dan implementasikan fitur **Parallel Tool Execution dengan Dependency Graph**:
- Skenario: Model memanggil dua tool: `get_customer_profile(user_id)` dan `calculate_discount(tier)`.
- Namun `calculate_discount` membutuhkan nilai `tier` yang hanya didapatkan dari hasil eksekusi `get_customer_profile`.
- Bangun mekanisme *Directed Acyclic Graph* (DAG) scheduler di dalam runtime orkestrator yang mampu mendeteksi dependensi parameter dan mengeksekusi tool secara bertahap secara otomatis (Tool 1 dijalankan lebih dulu, lalu outputnya dipetakan ke input Tool 2, sementara tool independen lain berjalan paralel).

---

### 14. Challenge

**Skenario**: Sistem *Multi-Agent Trading & Compliance Safeguard*.
Sebuah platform manajemen aset kripto membutuhkan engine eksekusi transaksi terotomatisasi via LLM dengan ketentuan ketat:
1. **Aturan Bisnis**:
   - Jika order bernilai $> \$50,000$, eksekusi tool wajib melalui mekanisme *Human-in-the-Loop* (HITL). Runtime orkestrasi harus membekukan state (*suspend state machine*), menyimpan *checkpoint* ke storage permanen, dan mengembalikan token verifikasi ke client.
   - Sistem harus dapat melanjutkan eksekusi (*resume*) dari checkpoint yang sama setelah ada webhook approval dari manajer portofolio tanpa menjalankan ulang step-step sebelumnya.
2. **Kondisi Ekstrem**:
   - Upstream API LLM sering mengalami *silent dropping* (koneksi HTTP tidak diputus, namun token terhenti tanpa delimiter `[DONE]`).
3. **Misi Anda**:
   Rancang arsitektur komponen, state schema, dan mekanisme *heartbeat timeout stream watchdog* yang dapat mendeteksi kondisi gantung ini dalam waktu maksimal 3 detik, lalu mengalihkan proses ke fallback provider secara *lossless* tanpa mengulang persetujuan HITL yang sudah selesai.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda & Konsep)

1. Apa fungsi utama logit masking berbasis Grammar/FSM pada eksekusi Structured Outputs?
   - A. Mempercepat koneksi TCP ke server LLM.
   - B. Memaksa probabilitas token di luar format JSON skema target bernilai $-\infty$.
   - C. Mengenkripsi payload API agar aman dari kebocoran data.
   - D. Menyimpan response ke dalam disk lokal secara otomatis.

2. Mengapa penggunaan library HTTP sinkron (seperti `requests`) dihindari pada aplikasi streaming LLM performa tinggi berbasis FastAPI/Asyncio?
   - A. Karena library sinkron memakan kuota token lebih banyak.
   - B. Karena memblokir event loop thread utama, melumpuhkan pemrosesan I/O klien lain.
   - C. Karena library sinkron tidak mendukung autentikasi Bearer Token.
   - D. Format data dari library sinkron tidak kompatibel dengan Pydantic.

3. Pada siklus Circuit Breaker, status apa yang mengizinkan sebuah request percobaan dikirim setelah periode cooldown tercapai?
   - A. OPEN
   - B. CLOSED
   - C. HALF-OPEN
   - D. ISOLATED

4. Apa arti metrik **TTFT** pada monitoring inferensi model LLM?
   - A. Total Time for Training
   - B. Time to First Token
   - C. Token-to-Function Transmission
   - D. Total Terminal Flush Time

5. Pada protokol Server-Sent Events (SSE), string penanda standar yang menandakan akhir dari stream data LLM adalah:
   - A. `data: {"status": "finished"}`
   - B. `event: close`
   - C. `data: [DONE]`
   - D. `<EOF>`

---

#### B. Pertanyaan Intermediate (Analisis Kasus Singkat)

6. Jelaskan risiko arsitektur jika Anda mengizinkan LLM mengeksekusi tool database SQL dengan hak akses `DROP` atau `DELETE` menggunakan parameter mentah dari model tanpa validasi layer isolasi!
7. Bagaimana algoritma *Full Jitter* mencegah fenomena *Thundering Herd Problem* saat puluhan worker service mencoba reconnect bersamaan ke LLM provider yang baru saja pulih dari outage?
8. Mengapa parameter `temperature=0` sangat direkomendasikan ketika model diarahkan untuk menghasilkan Tool Call terstruktur pada sistem produksi?
9. Apa perbedaan esensial antara *Function Calling* konvensional dengan *Hedged Request Calling* pada layer API Gateway?
10. Sebutkan satu skenario di mana deserialisasi Pydantic akan gagal meskipun model LLM menghasilkan output dengan format JSON valid!

---

#### C. Skenario Kasus Produksi

11. **Skenario Rate Limiting**: Service Anda tiba-tiba menerima rentetan HTTP 429 dari OpenAI API pada jam peluncuran produk baru. Log menunjukkan quota TPM (Tokens Per Minute) terlampaui, padahal RPM (Requests Per Minute) masih jauh di bawah batas. Apa penyebab sistemik yang paling mungkin terjadi pada payload orkestrasi Anda, dan perbaikan apa yang harus diterapkan pada context window management?

12. **Skenario Latensi Menggantung (P99 Degradation)**: Metrik aplikasi menunjukkan P50 latency berada di angka $1.2\text{ s}$, tetapi P99 membengkak hingga $18.5\text{ s}$. Setelah dianalisis, hal ini disebabkan oleh pemanggilan model dengan serial tool call berjumlah 4-6 fungsi per turn. Bagaimana Anda mendesain ulang alur pemanggilan tool tersebut agar latensi p99 mendekati angka rata-rata?

13. **Skenario Silent Hallucination pada Parameter Tool**: Model memanggil tool `transfer_funds(source_account, target_account, amount)`. Model memberikan tipe data yang benar secara sintaksis, namun mengisikan `target_account` dengan UUID fiktif yang tidak terdaftar di sistem core banking. Di layer manakah validasi penanganan ini harus diletakkan, dan bagaimana payload respons dikembalikan ke model agar model dapat membetulkan keputusannya (*self-correction loop*)?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A (Basic)
1. **B** — Logit bias/masking mengatur distribusi probabilitas logit token non-skema menjadi $-\infty$ sehingga mustahil terpilih saat sampling.
2. **B** — Operasi sinkron membekukan single-threaded asyncio event loop, menurunkan throughput konkurensi.
3. **C** — HALF-OPEN adalah status uji coba berkala untuk memastikan apakah dependency upstream sudah benar-benar pulih.
4. **B** — Time to First Token (waktu dari request dikirim hingga karakter/token awal diterima oleh client).
5. **C** — Nilai string literal `data: [DONE]` adalah standar de facto yang diadopsi industri streaming LLM API.

#### Bagian B (Intermediate)
6. **Risiko**: Terjadinya SQL Injection berbasis Prompt Injection. Jika prompt pengguna berhasil memanipulasi intent model, LLM dapat mengeksekusi kueri destruktif yang menghapus database produksi secara permanen. Tool harus selalu diisolasi dengan *least privilege principle* (akses Read-Only, parameterized queries).
7. **Analisis**: Tanpa jitter, seluruh client yang gagal akan me-retry secara serentak pada interval waktu yang persis sama (misal kelipatan 2, 4, 8 detik), menyebabkan lonjakan traffic berulang (*spikes*) yang kembali melumpuhkan server target. Full Jitter menyebarkan request secara seragam (*uniform distribution*).
8. **Alasan**: `temperature=0` mematikan entropi acak pada sampling token (greedy decoding), memaksa model memilih jalur token dengan probabilitas tertinggi, memastikan konsistensi dan determinisme ekstraksi parameter tool.
9. **Perbedaan**: Function Calling berkaitan dengan emisi schema argument oleh LLM. Hedged Requests adalah strategi infrastruktur networking di mana satu request inferensi dikirim ke lebih dari 1 provider/region secara paralel untuk mengeliminasi tail-latency.
10. **Kasus Kegagalan**: Ketika JSON valid secara sintaksis (misal: `{"age": -25}`), namun melanggar validasi semantik domain logic yang ditentukan oleh Pydantic validator (`Field(gt=0)`).

#### Bagian C (Skenario Kasus Produksi)
11. **Penyebab & Solusi**: Lonjakan TPM diakibatkan oleh membesarnya *Prompt History* yang tidak dikontrol (misalnya seluruh riwayat obrolan panjang dikirim berulang-ulang tanpa kompresi pada setiap request). Solusi: Terapkan *Context Window Compaction*—gunakan algoritma rolling buffer (hanya simpan $K$ putaran terakhir), buang tool responses yang berukuran masif dari history masa lalu, atau terapkan *asynchronous background summarization* untuk memadatkan history obrolan lama menjadi ringkasan singkat.
12. **Solusi Latensi**:
    - Evaluasi apakah tool executions tersebut independen satu sama lain. Jika independen, ubah eksekusi sekuensial menjadi konkuren menggunakan `asyncio.gather()` secara paralel.
    - Manfaatkan fitur *Parallel Tool Calling* bawaan model modern agar model memuntahkan seluruh instruksi tool sekaligus dalam satu single response roundtrip, bukan satu per satu.
13. **Solusi Validasi & Self-Correction**:
    - Validasi **wajib diletakkan di layer backend application logic** (Domain Handler), bukan mempercayai output LLM secara mentah.
    - Handler menangkap ketidakberadaan UUID tersebut dari database, lalu mengembalikan pesan error terstruktur ke LLM sebagai pesan peran `tool`: `{"status": "failed", "code": "ACCOUNT_NOT_FOUND", "message": "Nomor rekening tujuan 0x123 tidak valid. Minta pengguna mengonfirmasi ulang nomor rekening."}`.
    - Model membaca konteks kegagalan tersebut pada siklus reasoning berikutnya dan menghasilkan jawaban klarifikasi yang sopan kepada pengguna akhir (*guided reflection*).

---

### 16. Summary

1. **Tool Calling Modern Bersifat Deterministik**: Melalui *Grammar-Constrained Decoding* dan *Strict JSON Schema compilation*, output model dijamin patuh pada struktur data tanpa error parsing, menggeser fokus developer dari membersihkan string menjadi memvalidasi semantik domain.
2. **Resilience by Design**: Mengintegrasikan LLM API pada skala enterprise membutuhkan pertahanan mendalam: *Circuit Breaker* mencegah cascading failure, *Exponential Backoff with Full Jitter* menangani rate limiting, dan *Fallback Providers* menjamin uptime tinggi.
3. **Konkurensi Asinkron Non-Negotiable**: Seluruh I/O operasi, streaming token SSE, dan pemanggilan tool wajib berjalan non-blocking di atas Python `asyncio` engine guna mencegah degradasi throughput sistem di bawah beban konkurensi tinggi.
4. **Eksekusi Aman & Terobservasi**: LLM adalah reasoning layer, bukan execution boundary. Validasi hak akses, sanitasi parameter, timeout guards, penanganan dependensi data (DAG), serta pelacakan telemetri presisi (TTFT/TPOT/Cost via OTel) adalah fondasi wajib arsitektur AI produksi.