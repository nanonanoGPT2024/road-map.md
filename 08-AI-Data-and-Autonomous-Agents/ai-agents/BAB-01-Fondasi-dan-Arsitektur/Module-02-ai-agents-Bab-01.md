# Kurikulum Rekayasa Perangkat Lunak AI Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-01: Fondasi dan Arsitektur Agen Otonom
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Mendesain dan mengimplementasikan arsitektur stateful multi-step autonomous agent dengan *deterministic state machine*, *event-driven checkpointing*, dan *sandboxed tool execution*.
*   Mengembangkan arsitektur memori berlapis (*short-term working memory*, *episodic buffer*, *long-term semantic vector index*, dan *hierarchical summarization memory*).
*   Menguasai integrasi teknik *dynamic replanning*, *Reflexion loop*, dan *Actor-Critic evaluation pattern* untuk memitigasi cascading errors dan loop osilasi.
*   Mengimplementasikan runtime eksekusi tool berlatensi rendah dengan *asynchronous I/O*, *strict schema validation* (Pydantic v2), *concurrency throttling*, serta *circuit breaker pattern*.
*   Menghitung, mengevaluasi, dan mengoptimalkan *cost-to-latency trade-offs* serta parameter skalabilitas pada sistem agen skala enterprise.

---

### 2. Prerequisites
*   **Pemrograman Lanjutan**: Python 3.11+ (menguasai `asyncio`, typing lanjutan, metaprogramming, context managers).
*   **Fondasi AI/LLM**: Pemahaman mendalam terkait tokenomics, context window limits, Structured Output generation (Function Calling/Tool Calling JSON Schema), embeddings, dan Vector Search.
*   **Arsitektur Sistem**: Penguasaan pola microservices, distributed caching (Redis), relational transactional storage (PostgreSQL), dan event streaming (Apache Kafka/RabbitMQ).
*   **Modul Terkait**: Kelulusan Modul 01 (*Pengenalan Agen, ReAct Basics, Prompt Engineering untuk Pemanggilan Fungsi*).

---

### 3. Concept & Internal Architecture

Implementasi agen otonom di level enterprise membutuhkan transisi dari sekadar "loop while ReAct sederhana" menuju arsitektur komputasi terdistribusi yang deterministik, terisolasi, dan dapat dipulihkan (*fault-tolerant*).

```
                      +-------------------------------------------------+
                      |              AGENT RUNTIME ENGINE               |
                      +-------------------------------------------------+
                                               |
     +-----------------------------------------+-----------------------------------------+
     |                                         |                                         |
     v                                         v                                         v
+-------------------------+       +-------------------------+       +-------------------------+
|   State & Checkpoint    |       |   Multi-tier Memory     |       | Tool Execution Runtime  |
|         Engine          |       |        Subsystem        |       |        (Sandbox)        |
+-------------------------+       +-------------------------+       +-------------------------+
| - State Graph Transitions|      | - Working State (RAM)   |       | - Schema Validator (v2) |
| - Append-only Event Log |       | - Short-Term Window     |       | - Async Workers Pool    |
| - Postgres/Redis Persist|       | - Semantic Memory (RAG) |       | - Timeout & Rate Limits |
| - Rollback/Replay Cap.  |       | - Hierarchical Summarizer|      | - Circuit Breakers      |
+-------------------------+       +-------------------------+       +-------------------------+
     |                                         |                                         |
     +-----------------------------------------+-----------------------------------------+
                                               |
                                               v
                      +-------------------------------------------------+
                      |           ORCHESTRATION & CRITIC LOOP           |
                      |   (Planner -> Actor -> Critic -> Replanner)     |
                      +-------------------------------------------------+
```

#### 3.1 State Machine & Deterministic Checkpointing
Agen enterprise tidak boleh bergantung pada variabel global in-memory volatile. Arsitektur harus mengadopsi prinsip *Statecharts* atau *Directed Acyclic Graph (DAG) / Cyclic Graph* terkelola.
*   **State Graph Transitions**: Setiap langkah inferensi LLM atau pemanggilan tool adalah mutasi state eksplisit:
    $$\mathcal{S}_{t+1} = f(\mathcal{S}_t, \mathcal{A}_t)$$
    di mana $\mathcal{S}$ adalah agent state dan $\mathcal{A}$ adalah action payload.
*   **Event-Sourcing Checkpoint**: Seluruh input, output model, token delta, dan tool execution response disimpan secara *append-only* ke storage persisten. Jika terjadi *network partition* atau worker crash, status agen dapat direkonstruksi (*replay*) hingga langkah mutasi terakhir yang valid.

#### 3.2 Hierarchical Memory Architecture
*   **Working Memory**: Kumpulan ephemeral tokens aktif yang saat ini masuk ke dalam prompt context window.
*   **Short-Term Episodic Memory**: Riwayat interaksi sesi aktif yang dikelola melalui strategi *Sliding Window with Semantic Eviction* atau *Hierarchical Summarization* (meringkas turn $T_{-N}$ hingga $T_{-k}$ menggunakan model berbiaya rendah).
*   **Long-Term Semantic Memory**: Pengambilan memori berbasis vector similarity search yang dikombinasikan dengan metadata filtering dan temporal decay algorithms:
    $$\text{Score}(d) = \alpha \cdot \text{CosineSim}(q, d) + \beta \cdot e^{-\lambda \Delta t} + \gamma \cdot \text{Relevance}(d)$$

#### 3.3 Sandboxed Tool Execution Engine
Tool tidak dieksekusi secara telanjang (*raw function call*) di proses utama server. Eksekusi membutuhkan:
*   **Syntactic & Semantic Gatekeeper**: Parsing parameter ketat berbasis schema JSON terverifikasi (Pydantic v2).
*   **Resource Bounds**: Throttling execution timeout, rate-limiting upstream API, dan pembatasan concurrency per tenant.
*   **Idempotency & Reversibility**: Penanganan tool non-idempotent (misal: mutasi database, payment processing) melalui idempotency keys dan transactional compensation patterns (Saga Pattern).

---

### 4. Why & What
*   **What**: Arsitektur agen produksi adalah framework rekayasa perangkat lunak terintegrasi yang memisahkan modul kognitif LLM dari runtime eksekusi, memori persisten, dan proteksi kegagalan infrastruktur.
*   **Why**: 
    *   *Mengapa bukan chained prompts biasa?* Rantai prompt linear (chains) bersifat kaku dan gagal ketika model menemui kegagalan perantara (*intermediate errors*). Agen dapat melakukan *self-correcting* dan memilih jalur alternatif.
    *   *Mengapa bukan raw while loop?* Raw loop rentan mengalami *infinite execution loops*, *context-window overflow*, memory leakage, dan *unguarded external tool mutations* (misalnya: model memanggil API transfer dana 100 kali berturut-turut karena parsing error).

---

### 5. How (Workflow Detail)
Alur eksekusi enterprise autonomous agent runtime:
1.  **State Initialization**: Request masuk, runtime memuat context metadata, preferensi tenant, dan riwayat memori persisten via session ID.
2.  **Context Assembly & Compaction**: Working memory dikonstruksi; jika melebihi *soft budget* token, jalankan *Hierarchical Memory Summarizer*. Long-term memory relevan ditarik via RAG.
3.  **Planning / Decision Step**: Model memproses state, menghasilkan *Plan* atau memilih *Action Tool* beserta argumen terstruktur.
4.  **Critic & Guardrail Evaluation**: Payload action dicek oleh modul evaluator (cek integritas skema, *policy boundary check*, privilege control).
5.  **Sandboxed Tool Execution**: Eksekutor asinkron menjalankan fungsi terpilih dalam konteks terisolasi, menangkap telemetry (latency, memory usage, exception).
6.  **Observation Ingestion & Checkpointing**: Hasil eksekusi (*Observation*) dimasukkan ke state graph. Lakukan commit checkpoint ke basis data.
7.  **Reflexion / Convergence Loop**: Model mengevaluasi apakah *Task Objective* telah terpenuhi:
    *   Jika **Selesai**: Format output final dan return response.
    *   Jika **Gagal/Error**: Masuk ke loop *Reflexion*, bentuk error diagnosis, lakukan update sub-goal, kembali ke langkah 3.
    *   Jika **Mencapai Limit**: Break execution, picu fallback human-in-the-loop atau safe error state.

---

### 6. Analogy & Diagram ASCII

#### Analogi
Bayangkan seorang Kepala Staf Medis (Agent Core Planner) di Unit Gawat Darurat:
*   Dokter tidak langsung mengoperasi pasien sendiri, melainkan membuat instruksi tindakan (Tool Call).
*   Setiap tindakan diverifikasi oleh Apoteker/Kepala Perawat (Schema & Safety Guardrail).
*   Rekam Medis (State Checkpoint) dicatat setiap detik secara permanen di buku log; jika dokter pingsan atau berganti shift, dokter baru dapat melanjutkan detik itu juga tanpa mengulang wawancara pasien.
*   Jika obat pertama gagal menstabilkan pasien, tim melakukan evaluasi klinis cepat (*Reflexion loop*), memperbarui diagnosis, dan memilih protokol terapi berikutnya.

#### Diagram ASCII: Execution Engine Architecture

```
User Request
    |
    v
+--------------------------------------------------------------+
|                    Enterprise Agent Gateway                  |
+--------------------------------------------------------------+
    |
    +---> [1. Load State/Checkpoint] <------- Redis/Postgres
    |
    +---> [2. Context Builder] <------------- Memory Retr. (Vector)
    |
    v
+--------------------------------------------------------------+
|                        Cognitive Loop                        |
|                                                              |
|        +---------------+                                     |
|        | Planner (LLM) |                                     |
|        +---------------+                                     |
|                |                                             |
|                v [Tool Call Proposal]                        |
|        +---------------+                                     |
|        | Policy Guard  | ---> (Rejected: Feedback to Planner)|
|        +---------------+                                     |
|                | (Approved)                                  |
|                v                                             |
|        +---------------+                                     |
|        | Tool Executor | ---> [External APIs / DB / Sandboxes|
|        +---------------+                                     |
|                |                                             |
|                v [Observation Data]                          |
|        +---------------+                                     |
|        | Critic/Reflex | ---> (Failed: Re-plan Triggered)    |
|        +---------------+                                     |
+--------------------------------------------------------------+
    |
    v
[3. Persist State Mutation] ------------> Event Log (Append-only)
    |
    +---> Return Final Payload to Client
```

---

### 7. Code Implementation: Enterprise-Grade Stateful Agent Engine

Implementasi murni Python 3.11+ yang mandiri (*zero external framework wrapper* seperti LangChain/CrewAI), dirancang untuk arsitektur produksi menggunakan asynchronous primitives, validasi tipe data Pydantic v2, sandboxing, checkpointing, dan self-correcting loop.

```python
"""
Enterprise Autonomous Agent Execution Runtime
File: agent_runtime.py
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
import logging
import traceback
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional, Type
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s")
logger = logging.getLogger("EnterpriseAgentRuntime")


# =====================================================================
# 1. State Models & Memory Schemas
# =====================================================================

class ToolExecutionResult(BaseModel):
    tool_name: str
    status: Literal["SUCCESS", "FAILED"]
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentState(BaseModel):
    session_id: str
    task_objective: str
    messages: List[Message] = Field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    is_completed: bool = False
    final_output: Optional[str] = None
    execution_history: List[ToolExecutionResult] = Field(default_factory=list)


# =====================================================================
# 2. Tool Architecture & Sandboxed Registry
# =====================================================================

class BaseToolSchema(BaseModel):
    """Base class untuk validasi skema parameter tool"""
    pass


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        schema: Type[BaseToolSchema],
        handler: Callable[..., Coroutine[Any, Any, Any]],
        timeout_seconds: float = 10.0
    ):
        self.name = name
        self.description = description
        self.schema = schema
        self.handler = handler
        self.timeout_seconds = timeout_seconds

    async def execute(self, raw_input: Dict[str, Any]) -> ToolExecutionResult:
        start_time = asyncio.get_event_loop().time()
        try:
            # 1. Strict Schema Validation Gate
            validated_params = self.schema(**raw_input)
            
            # 2. Sandboxed Execution with Resource Timeout
            coro = self.handler(**validated_params.model_dump())
            result = await asyncio.wait_for(coro, timeout=self.timeout_seconds)
            
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=self.name,
                status="SUCCESS",
                output=result,
                execution_time_ms=elapsed
            )
        except ValidationError as ve:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=self.name,
                status="FAILED",
                error=f"Parameter Validation Error: {str(ve)}",
                execution_time_ms=elapsed
            )
        except asyncio.TimeoutError:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=self.name,
                status="FAILED",
                error=f"Timeout of {self.timeout_seconds}s exceeded during execution",
                execution_time_ms=elapsed
            )
        except Exception as e:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=self.name,
                status="FAILED",
                error=f"Runtime Exception: {str(e)}",
                execution_time_ms=elapsed
            )


# =====================================================================
# 3. Checkpointing & State Persistence Layer
# =====================================================================

class StateCheckpointer:
    """Simulasi persisten storage (misal: PostgreSQL / DynamoDB)"""
    def __init__(self):
        self._storage: Dict[str, List[str]] = {}

    async def save_checkpoint(self, state: AgentState):
        if state.session_id not in self._storage:
            self._storage[state.session_id] = []
        serialized = state.model_dump_json()
        self._storage[state.session_id].append(serialized)
        logger.debug(f"[Checkpoint] State saved for session {state.session_id}, step={state.iteration_count}")

    async def get_latest_checkpoint(self, session_id: str) -> Optional[AgentState]:
        history = self._storage.get(session_id)
        if not history:
            return None
        return AgentState.model_validate_json(history[-1])


# =====================================================================
# 4. Core Autonomous Agent Engine
# =====================================================================

class EnterpriseAgentEngine:
    def __init__(self, checkpointer: StateCheckpointer):
        self.tools: Dict[str, ToolDefinition] = {}
        self.checkpointer = checkpointer

    def register_tool(self, tool: ToolDefinition):
        self.tools[tool.name] = tool
        logger.info(f"Tool terdaftar: {tool.name}")

    async def _mock_llm_call(self, state: AgentState) -> Dict[str, Any]:
        """
        Simulasi inferensi model frontier yang mengembalikan Structured Output
        (Function Calling). Di implementasi nyata, ganti dengan OpenAI/Anthropic SDK.
        """
        await asyncio.sleep(0.1) # Simulasi latency jaringan
        step = state.iteration_count

        # Simulasi alur deterministik: step 0 panggil query_db, step 1 analyse, step 2 selesai
        if step == 0:
            return {
                "thought": "Untuk menjawab permintaan analisis inventaris, saya harus membaca database inventaris terlebih dahulu.",
                "action": "call_tool",
                "tool_name": "query_database",
                "tool_args": {"sql_query": "SELECT item, stock FROM inventory WHERE stock < 10;"}
            }
        elif step == 1:
            # Observasi dari step 0 dievaluasi
            last_exec = state.execution_history[-1]
            if last_exec.status == "SUCCESS":
                return {
                    "thought": "Data inventaris didapatkan. Sekarang saya akan menjalankan kalkulasi resupply order.",
                    "action": "call_tool",
                    "tool_name": "calculate_order",
                    "tool_args": {"items": last_exec.output, "target_stock": 50}
                }
            else:
                return {
                    "thought": "Pengambilan data gagal. Mencoba strategi perbaikan.",
                    "action": "call_tool",
                    "tool_name": "query_database",
                    "tool_args": {"sql_query": "SELECT * FROM fallback_inventory;"}
                }
        else:
            return {
                "thought": "Seluruh data telah diperoleh dan kalkulasi restock telah selesai. Saya siap menyusun respons akhir.",
                "action": "finish",
                "final_answer": "Rekomendasi Restock:\n- Widget A: Order 42 unit\n- Gadget B: Order 48 unit."
            }

    async def step(self, state: AgentState) -> AgentState:
        """Satu iterasi dari siklus kognitif (Plan -> Guard -> Execute -> Critic)"""
        state.iteration_count += 1
        logger.info(f"--- Memulai Iterasi {state.iteration_count} [Session: {state.session_id}] ---")

        # 1. Inferensi LLM
        decision = await self._mock_llm_call(state)
        
        # 2. Tangani Termination Condition
        if decision.get("action") == "finish":
            state.is_completed = True
            state.final_output = decision.get("final_answer")
            state.messages.append(Message(role="assistant", content=state.final_output or ""))
            await self.checkpointer.save_checkpoint(state)
            return state

        # 3. Tool Execution Path
        tool_name = decision.get("tool_name")
        tool_args = decision.get("tool_args", {})
        thought = decision.get("thought", "")
        
        state.messages.append(Message(role="assistant", content=f"Thought: {thought} | Action: {tool_name}"))

        if tool_name not in self.tools:
            # Reflexion injection: Agent salah memanggil nama tool
            error_obs = f"System Error: Tool '{tool_name}' tidak ditemukan dalam runtime."
            logger.warning(error_obs)
            state.execution_history.append(
                ToolExecutionResult(tool_name=tool_name, status="FAILED", error=error_obs, execution_time_ms=0.0)
            )
            state.messages.append(Message(role="tool", content=error_obs, name=tool_name))
        else:
            # Eksekusi Tool dalam Sandbox
            tool = self.tools[tool_name]
            result = await tool.execute(tool_args)
            state.execution_history.append(result)
            
            obs_payload = json.dumps(result.output) if result.status == "SUCCESS" else f"Error: {result.error}"
            state.messages.append(Message(role="tool", content=obs_payload, name=tool_name))
            logger.info(f"Tool {tool_name} dieksekusi dengan status: {result.status} ({result.execution_time_ms:.2f}ms)")

        # 4. Commit State Transition ke Storage
        await self.checkpointer.save_checkpoint(state)
        return state

    async def run(self, session_id: str, objective: str, max_iterations: int = 5) -> AgentState:
        """Main Loop Execution Engine"""
        # Load checkpoint jika ada, jika tidak ada create new state
        existing_state = await self.checkpointer.get_latest_checkpoint(session_id)
        if existing_state and not existing_state.is_completed:
            state = existing_state
            logger.info(f"Melanjutkan sesi {session_id} dari iterasi ke-{state.iteration_count}")
        else:
            state = AgentState(
                session_id=session_id,
                task_objective=objective,
                max_iterations=max_iterations,
                messages=[Message(role="user", content=objective)]
            )
            await self.checkpointer.save_checkpoint(state)

        while not state.is_completed and state.iteration_count < state.max_iterations:
            state = await self.step(state)

        if not state.is_completed:
            logger.error(f"Sesi {session_id} gagal konvergen dalam batas {state.max_iterations} iterasi.")
            state.final_output = "Error: Eksekusi agen melebihi batas iterasi tanpa konvergensi."
            await self.checkpointer.save_checkpoint(state)

        return state


# =====================================================================
# 5. Production Tool Declarations & Main Driver
# =====================================================================

class QueryDBSchema(BaseToolSchema):
    sql_query: str = Field(..., min_length=5, description="Valid SQL query string")

async def query_db_handler(sql_query: str) -> List[Dict[str, Any]]:
    # Mock database async I/O
    await asyncio.sleep(0.05)
    return [
        {"item": "Widget A", "stock": 8},
        {"item": "Gadget B", "stock": 2}
    ]

class OrderCalcSchema(BaseToolSchema):
    items: List[Dict[str, Any]]
    target_stock: int = Field(gt=0, description="Kapasitas target stock yang diinginkan")

async def calculate_order_handler(items: List[Dict[str, Any]], target_stock: int) -> Dict[str, int]:
    await asyncio.sleep(0.02)
    orders = {}
    for entry in items:
        needed = target_stock - entry["stock"]
        orders[entry["item"]] = max(0, needed)
    return orders


async def main():
    checkpointer = StateCheckpointer()
    engine = EnterpriseAgentEngine(checkpointer=checkpointer)

    # Daftarkan tools
    engine.register_tool(
        ToolDefinition(
            name="query_database",
            description="Eksekusi query SELECT ke database internal",
            schema=QueryDBSchema,
            handler=query_db_handler,
            timeout_seconds=3.0
        )
    )
    engine.register_tool(
        ToolDefinition(
            name="calculate_order",
            description="Hitung delta stok kebutuhan inventaris",
            schema=OrderCalcSchema,
            handler=calculate_order_handler,
            timeout_seconds=2.0
        )
    )

    task = "Identifikasi item inventaris dengan stok kurang dari 10, dan hitung kuota restock ke target 50."
    session = "sess-prod-tier1-89234"
    
    result_state = await engine.run(session_id=session, objective=task)
    
    print("\n================ FINAL AGENT EXECUTION RESULT ================")
    print(f"Status Finished: {result_state.is_completed}")
    print(f"Total Iterations: {result_state.iteration_count}")
    print(f"Output:\n{result_state.final_output}")
    print("==============================================================")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Autonomous Cloud Infrastructure Incident Mitigator (Level Tier-1 Telco / FinTech)

*   **Latar Belakang**: Sebuah platform pembayaran memproses $300.000 transaksi/menit. Pada jam sibuk, terjadi *cascading connection timeout* akibat deadlock di microservice *Settlement Engine*. SRE manual membutuhkan 20 menit untuk menganalisis metrik, menemukan node bermasalah, dan memutus traffic.
*   **Arsitektur Agen Terapan**:
    *   **Orchestration**: *Actor-Critic State Graph*. Satu model (Actor) bertindak membaca log Prometheus/Datadog dan membuat payload perintah remediation (misal: *graceful pod restart*, *drain node*, *increase thread pool*).
    *   **Memory Multi-tier**: Long-term semantic store menyimpan *Runbooks SRE* dan post-mortem insiden sebelumnya.
    *   **Guarded Tool Execution**: Agent tidak memiliki akses bash root mentah. Semua action dieksekusi melalui *Kubernetes Mutation API Adapter* yang divalidasi oleh *Policy Engine* (Open Policy Agent/OPA). Jika agent mengajukan penghapusan namespace core atau database master, command otomatis di-reject dan feedback dikirim ke Reflexion loop.
    *   **Dampak Bisnis**: Mean Time to Detect and Remediate (MTTR) terpangkas dari **22 menit menjadi 48 detik**. 94% insiden recurring diselesaikan secara otonom tanpa eskalasi ke staf On-Call SRE.

---

### 9. Trade-offs

| Dimensi Arsitektural | Pendekatan Ringan (Shallow Chain / Simple Loop) | Pendekatan Enterprise (State Machine & Guarded Sandbox) | Dampak & Kompromi Teknis |
| :--- | :--- | :--- | :--- |
| **Latensi (Latency)** | Sangat Rendah (100ms - 800ms) | Tinggi (2s - 15s per iterasi) | Pola Multi-loop membutuhkan multiple forward-pass inference + validasi skema runtime. |
| **Throughput & Concurrency**| Tinggi (Ribuan request/sec stateless) | Sedang hingga Rendah | Persistensi checkpoint ke storage dan rate-limiting eksternal membatasi I/O concurrency. |
| **Keandalan (Reliability)** | Sangat Rendah (<60% task completion kompleks)| Sangat Tinggi (>95% convergence) | Kemampuan rollback state dan penanganan error terisolasi mencegah fatal system crash. |
| **Biaya Token (Cost)** | Minimal | Eksponensial (3x - 10x lipat) | Validasi skema, injection context, long-term RAG, dan self-reflection menguras context window. |
| **Kompleksitas Kode** | Trivial (50 baris kode script) | Tinggi (Ratusan - ribuan baris, observability, distributed worker) | Butuh keahlian SRE & Distributed System mendalam untuk maintenance. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Endless Loop Trap (Model Oscillation)
*   **Gejala**: Agen terus memanggil tool yang sama dengan parameter yang sama berulang kali meski menerima error.
*   **Root Cause**: LLM tidak memiliki mekanisme membedakan antara "eksekusi pertama gagal" dan "eksekusi kedua sedang dicoba". Riwayat percakapan tidak menyertakan context *failure analysis*.
*   **Solusi**: Terapkan deteksi duplikasi hash parameter. Jika $H(\text{Action}_t) == H(\text{Action}_{t-1})$ dengan hasil `FAILED`, injeksikan *deterministic system prompt* yang memaksa model mengubah taktik atau berhenti.

#### 2. Context Window Exhaustion via Bloated Observation Payloads
*   **Gejala**: LLM crash dengan status code 400 (`context_length_exceeded`) setelah tool mengembalikan database payload berupa array 50.000 JSON rows.
*   **Root Cause**: Agen membuang output mentah dari tool langsung ke working memory.
*   **Solusi**: Wajibkan *Data Redaction & Truncation Layer* di antara tool runner dan agent state. Potong return payload maksimal 2.000 token atau jalankan summarizer sebelum diumpankan ke model.

#### 3. Unbounded Side-Effects (Lack of Idempotency)
*   **Gejala**: Akun bank nasabah terdebit 3 kali karena network timeout saat eksekusi tool API debit internal.
*   **Root Cause**: Tool debit tidak mendukung idempotency key atau retry logic yang membabi buta tanpa pengecekan status state sebelumnya.
*   **Solusi**: Sematkan UUID *idempotency_key* deterministik yang diikat ke `session_id` + `step_id` pada seluruh mutation request payload.

---

### 11. Best Practices (Production Checklist)

- [ ] **Strict Typing**: Semua parameter input/output tool divalidasi dengan runtime validation library (Pydantic v2 / Zod).
- [ ] **Deterministic Checkpointing**: State disimpan ke storage persisten *sebelum* dan *sesudah* setiap eksekusi tool.
- [ ] **Resource Deadlines**: Setiap tool diberi *hard execution timeout* menggunakan `asyncio.wait_for` untuk mencegah zombie task hanging.
- [ ] **Cost-Control Hard Limit**: Batasi maksimum `iteration_count` dan akumulasi budget USD/token per sesi pemanggilan agent.
- [ ] **Human-in-the-Loop (HITL) Interceptor**: Sediakan breakpoint status `REQUIRES_APPROVAL` untuk tool berisiko tinggi (misal: `drop_table`, `refund_payment`, `send_broadcast`).
- [ ] **Structured Logging & Tracing**: Ekspor span data ke OpenTelemetry (OTel), lacak *Prompt Tokens*, *Completion Tokens*, dan *Tool Latency* secara detail.
- [ ] **Safe Serialization**: Objek kompleks/koneksi (seperti socket atau connection pool) tidak boleh disimpan langsung di dalam state JSON.

---

### 12. Hands-on Practice
Langkah-langkah pembuatan agentic pipeline yang dapat disimpan pada folder direktori: `hands-on/m02/`

#### Task: Mengembangkan Self-Healing Multi-Step Web Scraper Agent
1.  **Langkah 1**: Buat direktori `hands-on/m02/` dan file virtual environment:
    ```bash
    mkdir -p hands-on/m02 && cd hands-on/m02
    python3 -m venv .venv && source .venv/bin/activate
    pip install pydantic httpx
    ```
2.  **Langkah 2**: Buat file `runtime_core.py`. Salin modul eksekusi stateful agent dari Seksi 7.
3.  **Langkah 3**: Buat file `scraper_tools.py`. Definisikan dua tools:
    *   `fetch_http_page`: Mengambil HTML dari URL dengan timeout 5 detik.
    *   `parse_dom_selector`: Mengekstrak teks dari HTML menggunakan CSS Selector string.
4.  **Langkah 4**: Simulasikan kasus kegagalan di mana URL pertama menghasilkan status code `403 Forbidden`.
5.  **Langkah 5**: Implementasikan *Reflexion prompt* yang menangkap exception `403`, lalu meminta model mencoba URL cermin (*fallback mirror URL*) atau menggunakan scraper proxy.
6.  **Langkah 6**: Jalankan pipeline dan verifikasi bahwa file checkpoint `checkpoint_session_*.json` terbentuk di disk secara bertahap untuk tiap step.

---

### 13. Exercises

#### Level Easy
Ubah implementasi `BaseToolSchema` di kode Seksi 7 untuk menambahkan tool kalkulator aritmatika yang menangani pembagian dengan angka nol (`ZeroDivisionError`). Tangkap error ini dan kembalikan pesan ramah tanpa mematikan loop agent.

#### Level Medium
Tambahkan mekanisme **Dynamic Token Budget Truncator** pada class `EnterpriseAgentEngine`. Jika total panjang karakter dari seluruh `messages` di dalam `AgentState` melampaui 10.000 karakter, rangkum pesan-pesan terlama (kecuali System Prompt dan Pesan Terakhir) menjadi satu ringkasan berbobot maksimal 500 karakter.

#### Level Hard
Rancang arsitektur **Human-In-The-Loop (HITL) Interceptor Pattern**. 
Tambahkan parameter `requires_approval: bool = True` pada definisi `ToolDefinition`. Modifikasi fungsi `step()` agar ketika tool jenis ini dipanggil, state berubah menjadi status `SUSPENDED_WAITING_HUMAN`, menghasilkan event notifikasi, dan menyimpan checkpoint ke disk. Buat fungsi terpisah `resume_with_approval(session_id: str, approved: bool)` yang dapat memulihkan state dari storage dan melanjutkan eksekusi jika disetujui, atau membatalkannya jika ditolak.

---

### 14. Challenge: Production Multi-Tenant SQL Agent with Data Leakage Shield
Rancang dan implementasikan dari nol sebuah sistem agen otonom analisis data untuk enterprise multi-tenant dengan parameter:
1.  **Isolasi Tenant**: Agen harus melayani berbagai tenant dari satu shared infrastructure. Setiap tenant hanya boleh mengeksekusi kueri pada schema database milik mereka sendiri.
2.  **Tool AST Verification**: Agen memiliki tool bernama `execute_analytic_sql`. Tool ini tidak boleh mengeksekusi kueri secara langsung, melainkan harus mengurai *Abstract Syntax Tree (AST)* dari query SQL menggunakan library parsing (misalnya `sqlglot`) untuk memvalidasi:
    *   Hanya statement `SELECT` yang diizinkan (tidak boleh ada mutasi `UPDATE`, `DROP`, `DELETE`, `ALTER`).
    *   Tidak boleh mengakses system catalogs atau tables di luar namespace tenant.
3.  **Autonomous Recovery from Syntax Error**: Jika syntax SQL gagal dieksekusi database engine, state loop harus menangkap error log parser database, memasukkannya ke feedback loop, dan memberikan kesempatan maksimal 3 kali perbaikan bagi model untuk meregenerasi syntax SQL yang benar.
4.  **Persyaratan**: Kode harus asynchronous murni, fully-typed dengan Pydantic v2, dan menyertakan integrasi unit tests sederhana.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa perbedaan arsitektural mendasar antara prompt chaining konvensional dan autonomous agent runtime?
2. Mengapa schema input tool harus divalidasi secara ketat pada runtime (misal menggunakan Pydantic) sebelum dieksekusi oleh mesin agen?
3. Apa fungsi utama *State Checkpoint* yang disimpan secara append-only di sistem agen produksi?
4. Sebutkan satu bahaya arsitektur jika return value dari sebuah tool dibiarkan berukuran masif (tanpa batasan ukuran)!
5. Apa yang dimaksud dengan *Working Memory* dalam konteks context window LLM?

#### Intermediate (5 Pertanyaan)
6. Jelaskan bagaimana *Reflexion pattern* bekerja untuk memulihkan agen dari kegagalan eksekusi perantara (*intermediate failure*)!
7. Bagaimana strategi menangani tool yang bersifat non-idempotent (misalnya transaksi finansial) agar tidak terjadi eksekusi ganda saat runtime mengalami timeout jaringan?
8. Mengapa menyimpan koneksi jaringan atau database socket instance secara langsung di dalam objek *Agent State* dianggap sebagai antipattern?
9. Bagaimana temporal decay algorithm membantu optimasi pengambilan data pada *Long-term Semantic Memory*?
10. Dalam kondisi seperti apa arsitektur multi-step autonomous agent **tidak tepat** untuk digunakan dan sebaiknya diganti dengan pipeline deterministic biasa?

#### Skenario Kasus Produksi (3 Skenario)
11. **Skenario A**: Sistem autonomous agent customer support Anda mengalami crash berantai ketika melayani 500 pengguna secara bersamaan. Database connection pool habis dan latensi model melonjak dari 1 detik menjadi 40 detik. Apa 3 langkah mitigasi arsitektur yang harus Anda terapkan pada runtime engine?
12. **Skenario B**: Model agen terjebak dalam *infinite loop* saat menjalankan tool pencarian data internal: Model selalu mengubah satu kata kunci kecil yang tetap menghasilkan return 0 records, menghabiskan credit API sebesar $50 per sesi. Bagaimana Anda mendesain *Oscillation Breaker* secara programatis untuk memutus loop ini secara elegan?
13. **Skenario C**: Agen integrasi HR enterprise memiliki tool untuk menghapus status cuti karyawan. Karena halusinasi model atas instruksi ambigu pengguna, agen salah memanggil tool tersebut dengan target seluruh departemen engineering. Evaluasi kelemahan desain sistem ini dan rancang arsitektur pertahanan berlapisnya (*Defense-in-depth*)!

---

### 16. Summary
Membangun autonomous agent kelas produksi memerlukan pergeseran fokus dari sekadar *prompting tricks* menjadi *rekayasa sistem terdistribusi*. Komponen kunci agen enterprise mencakup:
1.  **State Machine Deterministik**: Mengelola state mutasi dan persistensi event log secara persisten untuk keandalan dan kapabilitas pemulihan sistem.
2.  **Tool Execution Sandbox**: Melindungi sistem dari halusinasi parameter melalui validasi schema ketat, penanganan timeout asinkron, dan pembatasan hak akses eksekusi.
3.  **Memory Management Bertingkat**: Menggabungkan working memory ringkas, episodic summary, dan long-term retrieval untuk mencegah lonjakan biaya token dan context window exhaustion.
4.  **Error Recovery & Reflexion Loop**: Memungkinkan agen mendeteksi kesalahan secara mandiri dan menyusun rencana perbaikan tanpa menyebabkan infinite loop atau kegagalan sistemik.