# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Arsitektur Siklik (Cyclic Graph Engine)** untuk agen otonom menggunakan pola state-machine deterministik, beralih dari pipeline linear (DAG) ke eksekusi adaptif multi-langkah.
2. **Mengonstruksi Mekanisme Pemanggilan Tool (Tool Calling) Bergaransi Tipe** menggunakan *Grammar-Constrained Decoding* dan schema validation tingkat runtime untuk mengeliminasi *malformed payload errors* hingga 0%.
3. **Membangun Sistem Isolasi Eksekusi Tool (Tool Execution Sandboxing)** dengan proteksi *Resource Limiting*, *Dynamic Timeouts*, dan *Circuit Breakers* guna mencegah eksekusi *runaway processes* dan eksfiltrasi data.
4. **Mengimplementasikan State Management, Persistence, dan Checkpointing** yang mendukung *Human-in-the-Loop* (HITL) interrupt, state rollback, dan time-travel debugging pada skala enterprise.
5. **Mengintegrasikan Observabilitas End-to-End** mencakup distributed tracing, token-budget enforcement, dan metrik latensi pada setiap tahapan penalaran (*reasoning step*).

---

## 2. Prerequisite

Peserta wajib menguasai:

* **Sistem Terdistribusi & Async Python**: Mahir dalam `asyncio`, concurrency primitives (`Lock`, `Semaphore`), generator, dan typing lanjutan (`TypeVar`, `Annotated`, `TypedDict`).
* **Data Modeling & Validasi**: Penguasaan mendalam atas Pydantic v2 (Core schema, serialization, context-aware validation).
* **LLM Internal Mechanics**: Memahami logit sampling, temperature, grammar-based constraints (Outlines/JSON Schema masking), dan struktur konteks attention (KV cache management).
* **Dasar ReAct & Tool Use**: Memahami format pesan native OpenAI/Anthropic function calling dan abstraksi dasar pemanggilan LLM.

---

## 3. Concept & Internal Architecture

Arsitektur produksi sistem agen otonom tidak bertumpu pada satu prompt besar (*monolithic mega-prompt*), melainkan pada runtime state machine yang memisahkan antara **Reasoning Engine (LLM)**, **State Store (Graph Memory)**, dan **Execution Environment (Tool Sandbox)**.

```
+-----------------------------------------------------------------------------------+
|                            AGENT RUNTIME ENVIRONMENT                              |
|                                                                                   |
|  +------------------------+       State Transition        +--------------------+  |
|  |     State Engine       |<----------------------------->|  Checkpoint Store  |  |
|  | (Message History,      |                               | (Postgres/Redis    |  |
|  |  Scratchpad, Context)  |                               |  Distributed Lock) |  |
|  +-----------+------------+                               +--------------------+  |
|              |                                                                    |
|              v                                                                    |
|  +------------------------+      Structured Output        +--------------------+  |
|  |   Reasoning Engine     |------------------------------>| Schema Enforcement |  |
|  |  (LLM Inference Core)  |   (Grammar-Constrained Logits)|  (Pydantic V2)     |  |
|  +-----------+------------+                               +---------+----------+  |
|              ^                                                      |             |
|              | Observation Feedback                                 v             |
|  +-----------+------------+                               +--------------------+  |
|  |   Observation Layer    |                               | Policy & Security  |  |
|  | (Error Normalization,  |<-----------------------+      | Guardrails (RBAC)  |  |
|  |  Context Pruning)      |                        |      +---------+----------+  |
|  +------------------------+                        |                |             |
|                                                    |                v             |
|  +-------------------------------------------------+---------------------------+  |
|  |                      ISOLATED TOOL EXECUTION RUNTIME                        |  |
|  |                                                                             |  |
|  |  [Tool Worker: Subprocess / Container / WASM / Rate-Limited Async Pool]     |  |
|  |  +-------------------+  +-------------------+  +-------------------------+  |  |
|  |  | SQL Runner (RO)   |  | HTTP Webhook Exec |  | Vector Search Retriever |  |  |
|  |  +-------------------+  +-------------------+  +-------------------------+  |  |
|  |                                                                             |  |
|  |  Failures: Circuit Breaker -> Fallback -> Standardized Exception Handling   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 3.1. Siklus Hidup Eksekusi State Machine

Arsitektur siklik beroperasi melalui loop transisi state diskrit:

1. **State Ingestion & Pruning**: State saat ini dimuat dari Checkpoint Store. Pesan lama dipangkas atau diringkas sesuai token budget runtime menggunakan sliding-window buffer untuk mempertahankan working memory.
2. **Logit-Constrained Inference**: LLM memproses graph state bersama registri tools. Token decoding dibatasi oleh parser formal (JSON Schema context-free grammar) langsung pada probabilitas logit untuk memvalidasi pemanggilan fungsi sebelum token selesai digenerasi.
3. **Static & Semantic Policy Check**: Payload pemanggilan tool dievaluasi oleh sistem policy deterministik (RBAC, SQL write block, domain whitelist).
4. **Sandboxed Concurrent Execution**: Tool dieksekusi secara asinkron dalam worker terisolasi dengan constraint memori, CPU, dan timeout. Jika terjadi kegagalan (misalnya: connection reset atau validation error), engine menginjeksi traceback error ke scratchpad sebagai observasi, bukan melempar fatal exception ke client.
5. **State Reduction & Reflection**: Hasil eksekusi dikonversi menjadi `ToolMessage`, dimasukkan ke state graph melalui fungsi *reducer*, lalu dievaluasi kembali oleh LLM untuk menentukan apakah goal tercapai atau memerlukan iterasi lanjutan.

---

## 4. Why & What

| Dimensi | Pendekatan Linear (Chains / DAG) | Pendekatan Siklik (Stateful Graph Agent) |
| :--- | :--- | :--- |
| **Pola Kontrol** | Alur satu arah dari langkah $A \to B \to C$. | Perulangan deterministik berbasis kondisi transisi (*edge-based routing*). |
| **Error Recovery** | Gagal total jika salah satu node upstream mengalami error atau output tidak valid. | *Self-correction*: Error diekspos ke model sebagai observasi untuk dicoba ulang secara adaptif. |
| **State Tracking** | Ephemeral, context dikirim secara penuh melalui function argument. | Terpusat, menggunakan Checkpoint Store terisolasi dengan isolasi per-thread. |
| **Human Interaction** | Sulit dihentikan di tengah proses tanpa membatalkan konteks. | Mendukung *Interrupt*: State disimpan, runtime ditunda, dan dapat dilanjutkan pasca persetujuan. |
| **Deterministic Bound**| Mudah diprediksi, namun tidak mampu menangani masalah non-deterministik. | Dapat dibatasi dengan *max-iteration limits*, *token budget*, dan *time envelopes*. |

### Mengapa Pendekatan Linear Gagal di Enterprise

Sistem berbasis DAG (Direct Acyclic Graph) mengasumsikan setiap sub-tugas dapat diprediksi secara apriori. Kenyataannya, data enterprise bersifat dinamis: kueri database menghasilkan payload kosong, REST API mengembalikan kode HTTP 429, atau dokumen PDF mengandung data korup. 

Sistem berbasis siklik memperlakukan kegagalan sistem eksternal bukan sebagai crash, melainkan sebagai **observasi lingkungan** yang memungkinkan agen memformulasikan ulang hipotesis, mengubah parameter kueri, atau mengeksekusi fallback tool.

---

## 5. How (Workflow Detail)

Alur kerja agen produksi mengikuti mekanisme state-driven berikut:

```
 [User Input] 
       |
       v
+--------------+     Requires Tool?
|  Agent Node  | ----------------------> No  -----> [Final Response]
+--------------+                                           |
       ^  ^                                                |
       |  +---------------------------------------+        |
       |                                          |        |
  Yes  |                                          |        |
       v                                          |        |
+--------------+     Requires Human Approval?     |        |
| Policy Guard | ---> Yes ---> [Interrupt State]  |        |
+--------------+                     |            |        |
       | No                          v            |        |
       v                     (Human Action:       |        |
+--------------+             Approve/Reject/Edit) |        |
| Tool Sandbox |                     |            |        |
|  Execution   |<--------------------+            |        |
+--------------+                                  |        |
       |                                          |        |
       v                                          |        |
+--------------+                                  |        |
| State Reducer| ---------------------------------+        |
+--------------+                                           v
                                                        [DONE]
```

1. **Input Normalization**: Mengubah query user, context metadata, dan authentication token ke dalam `AgentState`.
2. **Reasoning Step**: Agent Node mengeksekusi inferensi. Engine memutuskan apakah akan memanggil satu/banyak tool (parallel tool call) atau mengembalikan respons final.
3. **Policy Evaluation**: Agen memvalidasi apakah tool yang dipanggil masuk kategori *destructive* (misalnya: modifikasi DB, pengiriman email eksternal). Jika destructive, status berubah menjadi *suspended* dan memicu event HITL.
4. **Execution & Sandboxing**: Tool dijalankan dengan isolasi runtime. Metrik eksekusi dicatat ke OpenTelemetry tracing span.
5. **State Update**: Output diumpankan kembali ke `AgentState` melalui mekanisme reducer untuk memicu iterasi penalaran berikutnya.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Operasi (OS)

Bayangkan sebuah arsitektur komputer modern:
* **LLM adalah CPU**: Mengatur logika, mengolah instruksi, dan merencanakan eksekusi, tetapi tidak menyimpan data state permanen.
* **Agent State adalah RAM**: Scratchpad dinamis untuk menyimpan variabel lokal, message memory, dan frame eksekusi saat ini.
* **Checkpointing adalah Swap File / Virtual Memory**: Mekanisme penyimpanan status thread ke disk ketika proses ditunda (*suspended*).
* **Tools adalah Peripheral I/O (Disk, NIC, GPU)**: Device eksternal yang lambat, rentan kegagalan, dan wajib diakses melalui driver serta permission level yang ketat (*Kernel Space vs User Space*).

### State Machine Lifecycle

```
[IDLE] 
  │
  │ User Prompt
  ▼
[REASONING] ──(No Tool Needed)───────────────────────────────┐
  ▲                                                          │
  │                                                          │
  │ Observation Injected                                     │
  │                                                          │
[UPDATING STATE]                                             │
  ▲                                                          │
  │                                                          │
  │ Tool Success / Error Log                                 ▼
[EXECUTING TOOL] ◄─── Approved ─── [AWAITING APPROVAL]   [TERMINATED]
  ▲                                      ▲                   ▲
  │                                      │                   │
  │ Requires Exec                        │ Action Critical   │
  └─────────────── [POLICY CHECK] ───────┘                   │
                          │                                  │
                          └──── Policy Violation ────────────┘
```

---

## 7. Implementation: Simple vs. Production

### 7.1. Contoh Sederhana (Naive ReAct Implementation)

Implementasi sederhana rentan gagal di produksi karena mengandalkan parsing regex, ketiadaan penanganan timeout, dan ketiadaan validasi skema tipe:

```python
# ANTI-PATTERN: Jangan gunakan di environment produksi!
import re

def naive_agent(prompt: str, llm_client, tools: dict):
    history = f"Question: {prompt}\n"
    for _ in range(5):
        response = llm_client.predict(history)
        history += response
        if "Final Answer:" in response:
            return response.split("Final Answer:")[1].strip()
        
        # Regex brittle: mudah gagal jika model sedikit berhalusinasi
        match = re.search(r"Action:\s*(\w+)\s*Action Input:\s*(.*)", response)
        if match:
            tool_name, tool_input = match.groups()
            try:
                # Kelemahan: Unsafe execution, rentan injeksi string, blocking I/O
                result = tools[tool_name](tool_input.strip())
            except Exception as e:
                result = str(e)
            history += f"\nObservation: {result}\n"
    return "Failed: Reached maximum iterations."
```

---

### 7.2. Contoh Praktis Standar Industri (Enterprise Stateful Agent Engine)

Berikut adalah implementasi runtime agen otonom berbasis arsitektur stateful modern: asynchronous, type-safe (Pydantic v2), dilengkapi circuit breaker, timeout context, dan checkpointing.

```python
from __future__ import annotations

import asyncio
import enum
import json
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EnterpriseAgentRuntime")

# =====================================================================
# 1. DOMAIN SCHEMAS & STATE DEFINITIONS
# =====================================================================

class Role(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    tool_name: str
    arguments: Dict[str, Any]

class Message(BaseModel):
    role: Role
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

class AgentState(BaseModel):
    thread_id: str
    messages: List[Message] = Field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 10
    is_completed: bool = False
    interrupted: bool = False
    pending_approvals: List[ToolCall] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# =====================================================================
# 2. ISOLATED TOOL RUNTIME WITH CIRCUIT BREAKER & TIMEOUT
# =====================================================================

class CircuitBreakerOpenException(Exception):
    pass

class ToolCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error("Circuit breaker tripped to OPEN state.")

    def allow_execution(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_time_sec:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker entering HALF-OPEN state.")
                return True
            return False
        return True # HALF-OPEN allows traffic to test recovery

class BaseTool:
    name: str
    description: str
    args_schema: Type[BaseModel]
    is_sensitive: bool = False

    def __init__(self, timeout_sec: float = 5.0):
        self.timeout_sec = timeout_sec
        self.circuit_breaker = ToolCircuitBreaker()

    async def run(self, **kwargs) -> str:
        if not self.circuit_breaker.allow_execution():
            raise CircuitBreakerOpenException(f"Tool '{self.name}' is temporarily unavailable (circuit open).")

        # Validasi skema runtime menggunakan Pydantic v2
        try:
            validated_args = self.args_schema.model_validate(kwargs)
        except ValidationError as ve:
            return f"Validation Error on Tool '{self.name}': {ve.json()}"

        try:
            # Isolasi proses dengan boundary timeout yang ketat
            result = await asyncio.wait_for(self._execute(validated_args), timeout=self.timeout_sec)
            self.circuit_breaker.record_success()
            return result
        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            logger.error(f"Timeout executing tool {self.name} after {self.timeout_sec}s.")
            return f"Error: Tool '{self.name}' execution timed out."
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.exception(f"Unhandled error in tool {self.name}: {e}")
            return f"Error executing tool '{self.name}': {str(e)}"

    async def _execute(self, validated_args: BaseModel) -> str:
        raise NotImplementedError

# =====================================================================
# 3. PRODUCTION TOOLS IMPLEMENTATION
# =====================================================================

class SQLQueryInput(BaseModel):
    query: str = Field(..., description="The PostgreSQL read-only query to run.")

class SQLRunnerTool(BaseTool):
    name = "sql_runner"
    description = "Executes read-only SQL queries against reporting database."
    args_schema = SQLQueryInput
    is_sensitive = False

    async def _execute(self, validated_args: SQLQueryInput) -> str:
        # Static Safety Guard: Mencegah eksekusi query destruktif
        forbidden_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
        if any(keyword in validated_args.query.upper() for keyword in forbidden_keywords):
            return "Execution Rejected: Destructive SQL detected. Access restricted to SELECT."
        
        await asyncio.sleep(0.1) # Simulasi network I/O
        return json.dumps([{"order_id": 1024, "customer_id": "C-9821", "amount": 1450000, "status": "FLAGGED"}])

class TransferFundsInput(BaseModel):
    account_id: str = Field(..., regex=r"^ACC-\d{4}$")
    amount: float = Field(..., gt=0.0)

class TransferFundsTool(BaseTool):
    name = "transfer_funds"
    description = "Initiates financial wire transfer between accounts."
    args_schema = TransferFundsInput
    is_sensitive = True # Membutuhkan Human Approval

    async def _execute(self, validated_args: TransferFundsInput) -> str:
        await asyncio.sleep(0.2)
        return json.dumps({"status": "SUCCESS", "tx_hash": f"0x{uuid.uuid4().hex}"})

# =====================================================================
# 4. AGENT CORE ENGINE & STATE MACHINE RUNNER
# =====================================================================

class MockLLMClient:
    """Mock LLM engine yang merefleksikan interface Tool Calling modern."""
    async def generate(self, messages: List[Message], available_tools: List[Dict[str, Any]]) -> Message:
        await asyncio.sleep(0.2)
        last_message = messages[-1]
        
        if last_message.role == Role.USER:
            return Message(
                role=Role.ASSISTANT,
                content="I will check suspicious transactions first.",
                tool_calls=[ToolCall(tool_name="sql_runner", arguments={"query": "SELECT * FROM orders WHERE status = 'FLAGGED'"})]
            )
        
        if last_message.role == Role.TOOL and "1024" in last_message.content:
            return Message(
                role=Role.ASSISTANT,
                content="Identified suspicious order. I must refund it to account ACC-9999.",
                tool_calls=[ToolCall(tool_name="transfer_funds", arguments={"account_id": "ACC-9999", "amount": 1450000.0})]
            )
            
        return Message(
            role=Role.ASSISTANT,
            content="Task completed: Suspicious transactions audited and refunded."
        )

class ProductionAgentEngine:
    def __init__(self, llm_client: MockLLMClient, tools: List[BaseTool]):
        self.llm_client = llm_client
        self.tools: Dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self.checkpoints: Dict[str, AgentState] = {}

    def _save_checkpoint(self, state: AgentState):
        # Deepcopy serialization pattern untuk state persistence
        self.checkpoints[state.thread_id] = state.model_copy(deep=True)

    async def step(self, state: AgentState) -> AgentState:
        if state.iteration_count >= state.max_iterations:
            state.is_completed = True
            state.messages.append(Message(role=Role.SYSTEM, content="Execution budget exhausted."))
            return state

        state.iteration_count += 1
        logger.info(f"--- [Thread: {state.thread_id}] Step {state.iteration_count} ---")

        # 1. Reasoning Step (Inference)
        llm_response = await self.llm_client.generate(state.messages, [])
        state.messages.append(llm_response)

        # 2. Evaluation Step: Check for completion
        if not llm_response.tool_calls:
            state.is_completed = True
            return state

        # 3. Validation and Execution Step
        for tool_call in llm_response.tool_calls:
            target_tool = self.tools.get(tool_call.tool_name)
            if not target_tool:
                state.messages.append(Message(
                    role=Role.TOOL,
                    tool_call_id=tool_call.id,
                    content=f"ToolNotFound: Tool '{tool_call.tool_name}' is not registered."
                ))
                continue

            # Human-in-the-Loop Interruption Check
            if target_tool.is_sensitive:
                logger.warning(f"Sensitive action detected: '{tool_call.tool_name}'. Halting execution for approval.")
                state.interrupted = True
                state.pending_approvals.append(tool_call)
                self._save_checkpoint(state)
                return state

            # Asynchronous Sandboxed Execution
            execution_result = await target_tool.run(**tool_call.arguments)
            state.messages.append(Message(
                role=Role.TOOL,
                tool_call_id=tool_call.id,
                content=execution_result
            ))

        self._save_checkpoint(state)
        return state

    async def run(self, thread_id: str, prompt: Optional[str] = None) -> AgentState:
        if thread_id in self.checkpoints:
            state = self.checkpoints[thread_id]
        else:
            state = AgentState(thread_id=thread_id)
            if prompt:
                state.messages.append(Message(role=Role.USER, content=prompt))
            self._save_checkpoint(state)

        while not state.is_completed and not state.interrupted:
            state = await self.step(state)

        return state

    async def resume_with_approval(self, thread_id: str, approved: bool) -> AgentState:
        state = self.checkpoints.get(thread_id)
        if not state or not state.interrupted:
            raise ValueError("Thread is not in an interrupted state.")

        pending_calls = state.pending_approvals
        state.pending_approvals = []
        state.interrupted = False

        for tool_call in pending_calls:
            if approved:
                logger.info(f"Human authorized execution of '{tool_call.tool_name}'.")
                target_tool = self.tools[tool_call.tool_name]
                result = await target_tool.run(**tool_call.arguments)
            else:
                logger.warning(f"Human REJECTED execution of '{tool_call.tool_name}'.")
                result = "Execution Denied by Human-in-the-Loop Supervisor."
            
            state.messages.append(Message(
                role=Role.TOOL,
                tool_call_id=tool_call.id,
                content=result
            ))

        self._save_checkpoint(state)
        return await self.run(thread_id)

# =====================================================================
# 5. RUNTIME VERIFICATION EXECUTION
# =====================================================================

async def main():
    agent_engine = ProductionAgentEngine(
        llm_client=MockLLMClient(),
        tools=[SQLRunnerTool(), TransferFundsTool()]
    )
    
    thread_id = "fin-audit-tx-001"
    
    print("\n--- PHASE 1: Initial Autonomous Run ---")
    state = await agent_engine.run(
        thread_id=thread_id,
        prompt="Audit suspicious transactions and resolve unauthorized debits."
    )
    
    print(f"Status: Interrupted? {state.interrupted} | Completed? {state.is_completed}")
    print(f"Pending Approvals: {[t.tool_name for t in state.pending_approvals]}")

    print("\n--- PHASE 2: Human Supervision (Approve Sensitive Step) ---")
    final_state = await agent_engine.resume_with_approval(thread_id=thread_id, approved=True)
    
    print(f"Final Status: Completed? {final_state.is_completed}")
    for idx, msg in enumerate(final_state.messages):
        print(f"[{msg.role.upper()}]: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Automated Anti-Money Laundering (AML) & Sanction Screening Engine
* **Perusahaan**: Tier-1 Multinational Neo-Bank.
* **Problem**: Sistem pemrosesan transaksi manual menangani 150.000 peringatan fraud setiap hari. Waktu resolusi rata-rata mencapai 48 jam per kasus, dengan tingkat *false-positive* 88%. Tim compliance mengalami *alert fatigue* ekstrem.
* **Solusi**: Membangun *Autonomous AML Investigation Agent* dengan graph architecture:
  * Terhubung ke 12 data silo (Core Banking Database, Swift logs, LexisNexis API, Internal KYC Vault).
  * Menjalankan kueri analisis topologi graf secara rekursif untuk mendeteksi jaringan transfer mencurigakan (*smurfing/layering*).
  * Checkpoint PostgreSQL terdistribusi dengan Redis stream broker untuk mengisolasi state investigasi per transaksi.
  * Human-in-the-Loop (HITL) mewajibkan dua analis independen menandatangani persetujuan sebelum akun dibekukan (*Dual-Control Policy*).

### Arsitektur Deployment Topologi

```
                                 [API Gateway]
                                       │
                      Load Balanced via Thread Hash Ring
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
    [Agent Runner: Worker 1]                              [Agent Runner: Worker 2]
    ┌──────────────────────────────┐                      ┌──────────────────────────────┐
    │  - Local Memory LRU Cache    │                      │  - Local Memory LRU Cache    │
    │  - Semantic Guardrails Engine│                      │  - Semantic Guardrails Engine│
    └──────────────┬───────────────┘                      └──────────────┬───────────────┘
                   │                                                     │
                   └──────────────────────────┬──────────────────────────┘
                                              │
                   ┌──────────────────────────┴──────────────────────────┐
                   ▼                                                     ▼
     [PostgreSQL State Store]                               [Sandboxed Tool Workers]
    (Checkpoints, BLOB Audits,                             (Isolated Docker Engine,
     Distributed Lock per Thread)                           Strict Egress Proxies)
```

* **Hasil Metrik Produksi**:
  * Latensi investigasi terpangkas dari **48 jam menjadi 42 detik**.
  * Akurasi klasifikasi false-positive meningkat hingga **99.4%**.
  * Efisiensi biaya: Penurunan $3.2M/tahun untuk biaya denda regulasi keterlambatan pelaporan.

---

## 9. Trade-offs

| Dimensi | Native Function Calling (OpenAI/Anthropic) | State Machine Graph (LangGraph/Custom State) | Pure ReAct Prompting (Text-in, Text-out) |
| :--- | :--- | :--- | :--- |
| **Token Cost** | Rendah: Ditangani di layer parsing engine penyedia model. | Sedang-Tinggi: Mengharuskan snapshot konteks/state ditransmisikan ulang. | Sangat Tinggi: Riwayat penalaran panjang terduplikasi pada setiap panggilan. |
| **Latency** | Sangat Rendah: Logit-constrained decoding langsung dari inference engine. | Sedang: Ditambah overhead persistensi state dan I/O checkpointing. | Tinggi: Perlu parsing teks mentah dan parsing ulang saat output tidak valid. |
| **Determinism** | Tinggi pada level skema input, Rendah pada level eksekusi alur kontrol. | **Sangat Tinggi**: Kontrol penuh atas siklus, validasi transisi, dan rollback. | Sangat Rendah: Rentan loop tak terbatas dan halusinasi output syntax. |
| **Recovery Power** | Rendah: Menyerahkan penanganan error secara penuh ke sisi developer. | **Sangat Tinggi**: Mendukung state rollback, node fallback, dan time-travel debug. | Rendah: Sangat bergantung pada kemampuan model membaca stack trace mentah. |

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Context Window Starvation via Unpruned Tool Outputs
* **Masalah**: Agen memanggil tool database atau web scraping yang mengembalikan payload JSON mentah sebesar 50.000 baris. Konteks window langsung terisi penuh (*context overflow*), menyebabkan latensi melonjak drastis dan model mengalami amnesia (*lost in the middle*).
* **Solusi**: Terapkan *Projection Masking Layer* dan *Map-Reduce Tool Output Transformer*:
  ```python
  def sanitize_tool_output(raw_output: dict, max_tokens: int = 1000) -> str:
      # Proyeksikan hanya kolom esensial
      projected = {k: v for k, v in raw_output.items() if k in ["id", "status", "summary"]}
      serialized = json.dumps(projected)
      # Estimasi rasio kasar: 1 token ~= 4 karakter
      if len(serialized) > max_tokens * 4:
          return serialized[:max_tokens * 4] + "... [Output Truncated by Runtime]"
      return serialized
  ```

### Anti-Pattern 2: Zombie Loop Execution (Non-Terminating State)
* **Masalah**: Model menerima pesan error dari tool yang sama dan terus mencoba memanggilnya berulang kali tanpa mengubah parameter, menghabiskan batas rate API dan token budget.
* **Solusi**: Pasang *Sliding-Window Failure Detector* pada state machine. Jika `tool_call` identik dipanggil 3 kali berturut-turut dengan hasil observasi error, paksa transisi state ke node `escalate_to_human`.

### Anti-Pattern 3: Insecure Tool Sandboxing (Command/SQL Injection)
* **Masalah**: Mengizinkan agen menyusun query string mentah (raw query assembly) secara bebas.
* **Solusi**: Jangan pernah mengekspos interpreter shell mentah atau koneksi database dengan hak akses tulis (`write-access`). Gunakan parametrized execution dan batasi privileges hanya ke level read-only replica.

---

## 11. Best Practices (Production Checklist)

1. [ ] **State Determinism**: Pastikan semua modifikasi state graph bersifat murni (*idempotent updates via pure state reducers*).
2. [ ] **Grammar Constraints**: Wajibkan strict mode (`strict=True` pada OpenAI JSON Schema) untuk menjamin parameter model cocok 100% dengan class Pydantic.
3. [ ] **Concurrency Isolation**: Kunci baris state per-thread menggunakan distributed lock (e.g., Redis Redlock) selama proses penalaran untuk mencegah *race conditions*.
4. [ ] **Payload Sanitization**: Pangkas token output tool sebelum dimasukkan ke dalam riwayat pesan scratchpad.
5. [ ] **Explicit Timeouts**: Tetapkan batas waktu timeout independen pada tiga level: LLM inferensi, runtime tool, dan siklus loop keseluruhan.
6. [ ] **Circuit Breakers**: Implementasikan circuit breaker per tool endpoint eksternal untuk menghentikan pemanggilan cascade ke service yang sedang down.
7. [ ] **Destructive Action Barriers**: Wajibkan breakpoint persetujuan manusia (*Human Approval*) untuk seluruh aksi yang memiliki efek samping permanen (DB drop, fund wire, sending notifications).
8. [ ] **Comprehensive Telemetry**: Gunakan span context terdistribusi (OpenTelemetry) yang melacak: `agent.loop`, `agent.reasoning`, `tool.validate`, `tool.execute`.

---

## 12. Hands-on Practice

Struktur direktori praktikum yang harus dibangun pada subdirektori workspace:

```
hands-on/m02/
├── app/
│   ├── __init__.py
│   ├── agent.py
│   ├── circuit_breaker.py
│   ├── state.py
│   └── tools.py
├── config/
│   └── settings.py
├── tests/
│   ├── __init__.py
│   └── test_agent_graph.py
├── requirements.txt
└── run_audit.py
```

### Panduan Implementasi Bertahap:

1. **Inisialisasi Project**:
   ```bash
   mkdir -p hands-on/m02/app hands-on/m02/config hands-on/m02/tests
   cd hands-on/m02
   ```
2. **Dependensi (`requirements.txt`)**:
   ```text
   pydantic>=2.6.0
   pytest>=8.0.0
   pytest-asyncio>=0.23.0
   ```
3. **Konfigurasi Lingkungan**:
   Buat `app/state.py` dengan skema `AgentState` persisten, dan `app/circuit_breaker.py` untuk isolasi error eksternal.
4. **Validasi Test Harness**:
   Jalankan `pytest tests/test_agent_graph.py` untuk memvalidasi bahwa timeout dan kegagalan fungsi tidak membuat agent runner mengalami crash.

---

## 13. Exercises

### Level Easy
Modifikasi kelas `SQLRunnerTool` pada kode bagian 7.2 untuk menambahkan validasi parameterized limit: Pastikan query `SELECT` otomatis disisipkan klausa `LIMIT 100` jika klausa `LIMIT` belum didefinisikan secara eksplisit oleh model.

### Level Medium
Tambahkan mekanisme **Dynamic Token Budget Trimmer** pada `ProductionAgentEngine`: Jika akumulasi total karakter dalam riwayat `messages` melebihi $8.000$ karakter, otomatis pangkas pesan peran `tool` terlama dan ganti isinya dengan string ringkas: `"[Payload purged from scratchpad to preserve context window]"`.

### Level Hard
Implementasikan **Episodic Tool Memory Reflection Node**: Bangun interceptor pada runtime state machine. Jika sebuah tool melempar exception:
1. Simpan pesan error dan input ke context list `failed_attempts`.
2. Pada iterasi berikutnya, suntikkan system directive dinamis ke model yang memperingatkan: *"Your previous call to {tool_name} failed with payload {args}. You are strictly forbidden from reusing those identical arguments."*
3. Pastikan eksekusi ini diverifikasi melalui unit test otomatis menggunakan `pytest-asyncio`.

---

## 14. Challenge

Rancang arsitektur dan bangun implementasi prototipe untuk: **Autonomous Cloud Incident Remediation Agent**.

### Spesifikasi:
1. **Multi-Step Triage**: Mengambil data metrik dari mock monitoring API, mendeteksi service yang mengalami memory leak (OOM).
2. **Dynamic Tool Sub-Selection**: Memilih tool yang relevan dari registri berisi > 50 tools menggunakan semantic similarity scoring (Tool RAG pattern), bukan menyuntikkan seluruh tool schema sekaligus ke context window.
3. **Dual-Key Authorization Protocol**: Eksekusi restart server produksi atau rollback traffic routing memerlukan token approval terenkripsi HMAC yang disuntikkan secara dinamis melalui antarmuka CLI.
4. **Idempotent Rollback System**: Jika proses mitigasi gagal di tengah jalan, runtime harus mengeksekusi urutan *reverting actions* secara terbalik (Saga Pattern) untuk mengembalikan infrastruktur cloud ke state stabil semula.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa JSON Schema-constrained decoding lebih unggul dibandingkan parsing teks mentah dengan regex pada ReAct loop?
   * A. Karena regex meningkatkan latensi inferensi GPU secara eksponensial.
   * B. Karena constrained decoding membatasi probabilitas token di level sampling logit, menjamin payload valid secara sintaksis sebelum output selesai digenerasi.
   * C. Karena JSON Schema memperkecil ukuran parameter model LLM.
   * D. Karena model LLM tidak mampu memproses karakter kurung kurawal tanpa grammar engine.

2. Komponen manakah dalam arsitektur agen siklik yang berperan sebagai "Virtual Memory / Disk"?
   * A. Execution Sandbox Worker.
   * B. LLM Inference Layer.
   * C. Checkpoint Store.
   * D. Policy Engine Guard.

3. Apa bahaya utama dari tidak membatasi ukuran output payload tool yang dimasukkan ke scratchpad context?
   * A. Menyebabkan deadlock pada prosesor CPU database.
   * B. Context window starvation yang memicu token overflow dan hilangnya instruksi awal (*lost-in-the-middle*).
   * C. Mengubah konfigurasi temperature LLM secara permanen.
   * D. Membatalkan hak akses API model.

4. Kapan status eksekusi agen harus dialihkan ke mode `INTERRUPTED`?
   * A. Ketika eksekusi tool memakan waktu lebih dari 100 milidetik.
   * B. Ketika model mengembalikan token akhir `Final Answer`.
   * C. Ketika aksi yang akan dieksekusi tergolong destructive atau memiliki risiko bisnis tinggi (Human-in-the-Loop checkpoint).
   * D. Ketika database Redis kehabisan memori.

5. Apa fungsi dari circuit breaker yang dipasang pada tool runtime wrapper?
   * A. Mempercepat proses query SQL dengan indexing otomatis.
   * B. Menghentikan pemanggilan berulang ke sistem eksternal yang sedang mengalami down/kegagalan terus-menerus.
   * C. Mengenkripsi payload JSON menggunakan AES-256.
   * D. Menghapus log error dari observasi LLM.

---

### Bagian 2: Intermediate (Analisis Singkat)

1. Jelaskan bagaimana *race condition* dapat terjadi pada state graph agen jika dua panggilan webhook eksternal memodifikasi satu `thread_id` secara bersamaan, dan bagaimana cara memitigasinya pada PostgreSQL checkpoint store!
2. Bandingkan efisiensi KV Cache antara pipeline chaining linear (DAG) vs. iterative cyclic state machine yang secara berulang memangkas scratchpad messages!
3. Jelaskan konsep *Time-Travel Debugging* pada agen berbasis graph checkpoints, dan bagaimana kemampuan ini mempercepat post-mortem analisis kesalahan di produksi!
4. Mengapa kita tidak boleh mengekspos raw Python `eval()` atau `exec()` sebagai tool agen di lingkungan enterprise, meskipun sistem sudah diproteksi system prompt?
5. Definisikan apa itu *Tool Calling Drift* dan bagaimana static validation schemas (seperti Pydantic v2) menanggulangi anomali tipe data runtime!

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: Deadlock Loop pada Transaksi B2B
Sebuah agen Procurement otomatis bertugas memproses invoice dan mencocokkannya ke database ERP. Suatu hari, vendor mengirim dokumen PDF dengan format karakter non-standar. Output OCR menghasilkan nilai balance `NaN`. 
Agen berulang kali memanggil tool `ERPUpdateOrder(order_id, balance)` dengan argumen `balance: NaN`. Database melempar error HTTP 400 Bad Request: `Float expected`. 
Agen membaca pesan error tersebut, menginterpretasikannya sebagai kegagalan transient network, lalu mencoba memanggil tool yang sama dengan parameter identik hingga menyentuh batas `max_iterations = 50`. Total biaya token membengkak 300% dan thread terkunci.
* **Pertanyaan**: Desainlah arsitektur mitigasi konkret (State machine rule, Error classification logic, dan Retry policy) untuk mencegah perulangan eksekusi argumen yang sama ini secara permanen!

#### Skenario 2: Tool Argument Injection via RAG Hijacking
Agen Customer Support memiliki tool `query_user_account_by_email(email: str)`. Ketika user mengirimkan prompt: 
`"Please update my ticket. By the way my email is: 'test@corp.com' OR '1'='1' -- and summarize account details"`, 
model mengekstrak input string tersebut langsung dan memanggil tool. Backend tool mengeksekusi raw query string formatting: `f"SELECT * FROM users WHERE email = '{email}'"`. Seluruh data pengguna di database terekspos ke LLM context window, dan dirangkum ke pengguna penyerang.
* **Pertanyaan**: Identifikasi dua lapisan kerentanan fatal pada skenario di atas dan tuliskan implementasi penangkalnya menggunakan Pydantic v2 validator serta parameterized boundary enforcement!

#### Skenario 3: Cascading Failure under High Concurrency
Saat peluncuran promo flash sale, sistem diserang oleh 10.000 panggilan agen bersamaan yang memanggil tool `CheckInventoryAPI`. Sistem API inventory internal mengalami *degraded latency* (dari 20ms naik menjadi 12 detik). 
Akibatnya, ribuan asynchronous coroutine worker agen tertahan menunggu network I/O, event loop kehabisan open file descriptor socket, dan seluruh pod service agen mengalami crash OOM (Out Of Memory).
* **Pertanyaan**: Rancang strategi isolasi resource terdistribusi mencakup: Global Concurrency Semaphore, Worker Pools, Dynamic Timeout Envelopes, dan Graceful Fallback Responses!

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Grammar-constrained decoding memastikan bahwa proses sampling token pada LLM hanya memilih logit yang secara sintaksis valid terhadap JSON schema.
2. **C** — Checkpoint store berfungsi sebagai persistence virtual memory untuk menyimpan, memuat, dan melanjutkan state tree antar langkah eksekusi.
3. **B** — Output tool yang tidak difilter/dipangkas dapat menghabiskan context window, mengakibatkan penurunan kualitas reasoning (*attention dispersion*) dan memicu context length exceeded error.
4. **C** — Aksi-aksi yang menimbulkan modifikasi persisten pada sistem eksternal atau mutasi data sensitif harus selalu ditahan untuk persetujuan manusia (HITL).
5. **B** — Circuit breaker memutus siklus pemanggilan saat kegagalan eksternal berturut-turut mencapai threshold tertentu, melindungi ekosistem dari *cascading service degradation*.

#### Bagian 2: Intermediate
1. **Mitigasi Race Condition**: Dua modifikasi simultan pada thread_id yang sama dapat menyebabkan *lost updates* pada graph history. Mitigasi: Terapkan *Pessimistic Row-Level Locking* (`SELECT ... FOR UPDATE` di PostgreSQL) atau distributed locking (misal: Redis Redlock) berbasis `thread_id` selama node transition berlangsung.
2. **Efisiensi KV Cache**: Pada DAG linear, KV Cache dapat digunakan kembali secara bertahap karena teks hanya tumbuh ke depan. Pada agen siklik yang melakukan pruning scratchpad di tengah proses, modifikasi token di posisi tengah membatalkan KV cache downstream, sehingga membutuhkan evaluasi ulang parsial (*cache invalidation*). Desain state harus mempertahankan prefix yang stabil agar KV cache reuse tetap optimal.
3. **Time-Travel Debugging**: Karena setiap langkah agen disimpan sebagai immutable checkpoint delta di storage, engineer dapat memuat ulang thread ke spesifik `step_id` di masa lalu, mengubah prompt atau schema tool, dan memutar ulang (*replay*) eksekusi dari titik tersebut tanpa harus mengulang proses dari awal.
4. **Resiko Insecure Sandboxing**: System prompt bukan security boundary. Serangan Indirect Prompt Injection dari dokumen/data yang diproses dapat memanipulasi model untuk menyuntikkan kode berbahaya (seperti `os.system('rm -rf /')` atau eksfiltrasi environment variables).
5. **Tool Calling Drift**: Fenomena di mana model secara sporadis mengubah format tipe data (misal: passing string `"100"` alih-alih integer `100`, atau memformat array menjadi format teks terpisah koma). Pydantic v2 mendeteksi dan melakukan coercion secara deterministik pada tipe data dasar, atau melempar schema error terstruktur ke agent scratchpad jika data tidak dapat dikonversi.

#### Bagian 3: Skenario Kasus Produksi
1. **Solusi Deadlock Loop**:
   * *State History Signature Tracking*: Simpan hash signature `sha256(tool_name + json_dumps(sorted_args))` dalam state.
   * *Duplicate Error Interceptor*: Jika hash yang identik menghasilkan exception berturut-turut, runtime langsung membatalkan tool execution node dan mengalihkan edge ke fallback classifier (*deterministic routing bypass*).
   * *Structured Exception Response*: Error yang dikirim ke LLM harus menyertakan tipe ekspektasi secara eksplisit: `{"error_type": "ValidationError", "expected_type": "float", "received_value": "NaN", "guidance": "Do not re-attempt with NaN. Fetch correct value or abort."}`.
2. **Solusi RAG Injection**:
   * *Pydantic Sanitization Boundary*:
     ```python
     class UserLookupSchema(BaseModel):
         email: EmailStr = Field(..., description="Valid corporate email format")
     ```
     Pydantic's `EmailStr` langsung menolak string injeksi SQL sebelum LLM memanggil database.
   * *Database Driver Parameterization*:
     Gunakan parameterized query absolut pada database layer:
     `cursor.execute("SELECT id, name FROM users WHERE email = %s", (validated_args.email,))`.
3. **Solusi Cascading Failure**:
   * *Global Semaphore*: Batasi konkurensi pemanggilan tool secara global menggunakan `asyncio.Semaphore(100)` per pod, mengantrekan kelebihan request.
   * *Dynamic Timeout Envelope*: Pangkas timeout tool menjadi `timeout=3.0` detik di bawah high load (menggunakan adaptive deadline budget).
   * *Circuit Breaker Deployment*: Jika kegagalan API mencapai 50% dalam window 10 detik, switch ke OPEN dan kembalikan response cached/degraded: `"Inventory data temporarily unavailable. Please retry later"`.

---

## 16. Summary

* Desain agen produksi modern bertumpu pada **Cyclic State Machine** terisolasi, bukan linear DAG chains.
* **Grammar-Constrained Decoding** dan validasi Pydantic v2 mutlak diperlukan di batas runtime untuk mengeliminasi ketidakcocokan tipe dan kegagalan struktur data.
* Runtime agen harus memperlakukan kegagalan sistem eksternal bukan sebagai program crash, melainkan sebagai **observasi lingkungan** yang disuntikkan kembali ke dalam state loop untuk memicu *self-correction*.
* **Checkpoint Persistence Engine** memungkinkan isolasi thread, audit trail mendalam, time-travel debugging, dan mekanisme *Human-in-the-Loop* pada operasi berisiko tinggi.
* Tanpa guardrails yang ketat (**Tool Sandboxing, Dynamic Context Pruning, Rate Limiting, Circuit Breakers**), sistem agen otonom rentan terhadap exploit prompt injection, runaway resource usage, dan kegagalan cascade di lingkungan enterprise.