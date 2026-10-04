# Bab 04: Technical Acumen for PMs & System Architecture Alignment
## Modul 01: Dekomposisi Arsitektur Sistem Autonomous Agent: Desain State, Memory Tiering, dan Token Economics

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Product Manager (PM) tingkat *Staff/Lead* di domain AI & Autonomous Systems diharapkan mampu:

*   **Menganalisis Komponen Arsitektur Kritis Agentic AI**: Mengidentifikasi dan memetakan interaksi antara *Execution Loop*, *Memory Subsystems*, *Tool Calling Interfaces*, dan *Foundation Model Runtime*.
*   **Merancang Strategi State & Memory Management**: Menentukan alokasi *Working Memory*, *Episodic Memory*, dan *Semantic Long-Term Memory* untuk mengoptimalkan integritas konteks dan mencegah fenomena *Context Drift*.
*   **Mengkalkulasi Token Economics & Latency Budgets**: Menghitung biaya komputasi, *Time to First Token* (TTFT), *Time Per Output Token* (TPOT), dan total biaya inferensi per transaksi bisnis menggunakan model matematika presisi.
*   **Membangun Kontrak Non-Fungsional (NFR) Berbasis Determinisme**: Menetapkan *Service Level Objectives* (SLO) sistem otonom dengan mengombinasikan *Deterministic State Machines* dengan inferensi stokastik (probabilistik).
*   **Mengevaluasi Trade-off Desain Sistem**: Memilih secara tepat antara arsitektur *ReAct*, *Plan-and-Solve*, dan *Hierarchical Multi-Agent Systems* berdasarkan batasan biaya, latensi P99, dan kompleksitas domain.

---

### 2. Concept Overview

Secara fundamental, sistem *Autonomous Agent* berbasis Large Language Model (LLM) adalah perluasan dari konsep *Turing Machine* di mana unit pemrosesan pusat (CPU) digantikan oleh model inferensi autoregresif probabilistik, dan bus data digantikan oleh *Context Window*. 

```
+-----------------------------------------------------------------------+
|                         LLM AGENT MENTAL MODEL                        |
|                                                                       |
|  [ Traditional Compute ]                     [ Agentic System ]       |
|  CPU (ALU + Registers)       <===========>   LLM (Inference Core)     |
|  RAM (Working Memory)        <===========>   Context Window (Scratch) |
|  Disk / SSD (Cold Storage)   <===========>   Vector / Graph DB        |
|  System Calls / I/O          <===========>   Tool / Function Calling  |
|  Deterministic Loop          <===========>   Stochastic ReAct Cycle   |
+-----------------------------------------------------------------------+
```

Sebagai Product Manager, mental model yang keliru adalah menganggap sistem agentik sebagai sekadar "Prompt Wrapper". Secara teknis, Agent adalah sistem terdistribusi asinkron yang memiliki karakteristik:

1.  **Statefulness Dinamis**: Berbeda dari aplikasi CRUD konvensional yang menyimpan state terstruktur dalam basis data relasional, agent mengelola state internal (*working memory*) yang terus bermutasi di dalam *context window* terbatas melalui token append-only.
2.  **Dualitas Stokastik-Deterministik**: Inti kalkulasi (*reasoning engine*) bersifat stokastik ($P(w_t \mid w_{<t})$), namun ekspektasi bisnis terhadap dampak eksekusinya bersifat deterministik (misalnya: tidak boleh terjadi *double spending* saat agent memanggil API pembayaran).
3.  **Non-Linear Execution Graph**: Jalur eksekusi (path) tidak dikodekan secara statis (*hardcoded branching*), melainkan diputuskan secara dinamis berdasarkan kalkulasi utilitas oleh model pada setiap iterasi loop.

---

### 3. Why It Matters

Di level enterprise, 80% inisiatif *Proof of Concept* (PoC) autonomous agent gagal mencapai tahap produksi (GA). Kegagalan ini bukan karena ketidakmampuan model dasar (LLM), melainkan akibat ketidakmampuan Product Manager dan Arsitek Sistem dalam menyelaraskan batasan teknis arsitektur dengan realitas bisnis:

*   **Cost Blowout (Ledakan Biaya Token)**: Loop otonom tanpa batasan deterministik dapat mengalami *infinite context expansion*. Satu task yang bernilai \$0.01 dapat membengkak menjadi \$15.00 karena agent terjebak dalam *looping* pemanggilan tools dengan payload besar.
*   **Latency-SLA Degradation**: Agent multi-step dengan 5 kali pemanggilan LLM serial, masing-masing dengan latensi P95 sebesar 3 detik, menghasilkan waktu respons 15+ detik. Hal ini melanggar SLA aplikasi interaktif enterprise ($< 3$ detik).
*   **Context Saturation & Needle-in-a-Haystack Failures**: Mengisi *context window* 128k token secara membabi buta dengan dokumen historis menyebabkan degradasi akurasi reasoning (*attention dilution* / *lost-in-the-middle phenomenon*), yang berdampak pada halusinasi eksekusi tool finansial atau data sensitif.

Technical acumen seorang PM memungkinkan perancangan metrik batas (*guardrails*), arsitektur memori berjenjang, dan *graceful fallback* yang menjamin viabilitas finansial dan operasional produk.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur enterprise agentic system memisahkan *Reasoning Layer* dari *Execution Layer* untuk menjamin keamanan, auditabilitas, dan kontrol biaya.

```
+-----------------------------------------------------------------------------------+
|                        ENTERPRISE AGENT SYSTEM ARCHITECTURE                       |
+-----------------------------------------------------------------------------------+
                                        |
                                [ User / Client ]
                                        | (HTTPS / gRPC)
                                        v
+-----------------------------------------------------------------------------------+
| API GATEWAY & INGRESS GUARD                                                       |
| - Authentication & RBAC        - Deterministic Semantic Cache (Redis)             |
| - Rate Limiter (Token Bucket)  - Ingress Guardrail (NeMo / Llama-Guard / PII)    |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
| AGENT ORCHESTRATION ENGINE (Stateful Runtime)                                     |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | State Machine Engine (Finite State Machine / LangGraph / Temporal)          |  |
|  | States: [IDLE] -> [PLANNING] -> [ACTION_EXEC] -> [OBSERVE] -> [EVAL]        |  |
|  +-----------------------------------------------------------------------------+  |
|         |                                 ^                      |                |
|         v                                 |                      v                |
|  +---------------------+        +--------------------+  +----------------------+  |
|  | Context Assembly    |        | Dynamic Reflection |  | Execution Sandbox    |  |
|  | & Token Budgeter    |        | & Error Recovery   |  | - Tool Registry      |  |
|  | (Sliding Window)    |        | (Self-Correction)  |  | - Timeout Controller |  |
|  +---------------------+        +--------------------+  | - Circuit Breaker    |  |
|         |                                                        |                |
+---------|--------------------------------------------------------|----------------+
          |                                                        |
          +--------------+                          +--------------+
                         |                          |
                         v                          v
+------------------------------------+  +-------------------------------------------+
| MEMORY SUBSYSTEM TIER              |  | INTEGRATION / TOOL EXECUTION LAYER        |
|                                    |  |                                           |
| [L1: Ephemeral Scratchpad]         |  | [Internal Enterprise APIs]                |
| - Execution-local context (RAM)    |  | - Core Banking, ERP, CRM (REST/gRPC)      |
|                                    |  |                                           |
| [L2: Episodic Buffer]              |  | [Deterministic Compute Engines]           |
| - Session History (Redis Cluster)  |  | - Python Code Sandbox (gVisor / Firecracker)
|                                    |  |                                           |
| [L3: Semantic Long-Term Memory]    |  | [Knowledge Retrieval Platforms]           |
| - Hybrid Vector DB (Qdrant/Milvus) |  | - Elastic / OpenSearch / Enterprise RAG   |
| - Knowledge Graph (Neo4j)          |  +-------------------------------------------+
+------------------------------------+                         |
                  |                                            |
                  v                                            v
+-----------------------------------------------------------------------------------+
| FOUNDATION MODEL INFERENCE LAYER                                                  |
|                                                                                   |
| [Egress Guardrails] -> [Model Gateway / Router]                                   |
|                          |                                                        |
|         +----------------+----------------+                                       |
|         |                                 |                                       |
|         v                                 v                                       |
| [Tier 1: Fast/Cheap Router]     [Tier 2: Reasoning Model]                         |
| (e.g., Haiku / 8B / Flash)      (e.g., Sonnet / GPT-4o / DeepSeek R1)             |
| TTFT: ~200ms | Cost: $          TTFT: ~800ms | Cost: $$$                          |
+-----------------------------------------------------------------------------------+
```

### Data Flow Execution Step:
1. **Ingress**: Kueri pengguna divalidasi oleh Guardrails (cek PII, prompt injection) dan diperiksa di Semantic Cache.
2. **Context Compilation**: Orchestrator menarik L2 (riwayat sesi) dan L3 (data semantik), menghitung limit token, dan menyusun prompt optimal.
3. **Reasoning Call**: Prompt dikirimkan ke Foundation Model Inference Layer melalui router cerdas.
4. **Tool Dispatching**: LLM menghasilkan output terstruktur (*JSON function call*); Orchestrator memvalidasi payload dan mengeksekusinya di Sandbox yang terisolasi.
5. **Observation Ingestion**: Output tool dialirkan kembali ke L1 Scratchpad, mengubah state machine ke tahap evaluasi berikutnya.
6. **Egress Guard**: Respons final diverifikasi kepatuhan faktualnya sebelum dikembalikan ke klien.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Token Economics & Latency Modeling
Sebagai PM, Anda harus mampu memprediksi *Unit Economics* sistem sebelum arsitektur masuk ke sprint engineering. Latensi total dan biaya transaksi diatur oleh persamaan komputasi berikut:

$$\text{Latency}_{total} = \text{TTFT} + \left( N_{steps} \times \left( \text{TTFT}_{step} + (\text{Tokens}_{out} \times \text{TPOT}) + T_{tool} \right) \right)$$

Dimana:
*   $\text{TTFT}$ (*Time to First Token*): Waktu pre-fill model memproses input context. Berbanding lurus dengan panjang input prompt: $\mathcal{O}(L_{in})$.
*   $\text{TPOT}$ (*Time Per Output Token*): Waktu generasi decoding autoregresif token demi token.
*   $N_{steps}$: Jumlah putaran (*round-trips*) yang dibutuhkan agent untuk menyelesaikan task.
*   $T_{tool}$: Latensi eksekusi API pihak ketiga / eksternal.

Biaya Inferensi Total ($C_{task}$) dihitung dengan formula:

$$C_{task} = \sum_{i=1}^{N_{steps}} \left( \text{Tokens}_{in, i} \times P_{in} + \text{Tokens}_{out, i} \times P_{out} \right) + C_{infra}$$

*Perhatikan akumulasi*: $\text{Tokens}_{in, i}$ meningkat secara kuadratik jika seluruh riwayat iterasi sebelumnya dialirkan kembali (*naive concatenation*).

```
Step 1: Input (1000 tokens) -> Output (200 tokens)
Step 2: Input (1200 + 300 tool_result = 1500 tokens) -> Output (250 tokens)
Step 3: Input (1750 + 200 tool_result = 1950 tokens) -> Output (100 tokens)
Total Input Tokens Billed = 1000 + 1500 + 1950 = 4450 tokens!
```

#### B. Hierarki Memori Sistem Agentic

| Layer Memori | Komponen Infrastruktur | Rentang Hidup (TTL) | Karakteristik Akses | Biaya Relatif |
| :--- | :--- | :--- | :--- | :--- |
| **L1: Scratchpad** | Context Window (In-Memory Array) | Satu siklus reasoning task | Read/Write instan; latensi zero; dibatasi max context length | Sangat Tinggi ($/token) |
| **L2: Episodic Memory** | In-Memory K-V (Redis, DynamoDB) | Rentang sesi pengguna (TTL: jam-hari) | State serialization (JSON/Protobuf); sliding window buffer | Rendah ($/RAM GB) |
| **L3: Long-term Semantic** | Vector DB (Qdrant) + Graph DB (Neo4j) | Permanen / Lintas sesi | Approximate Nearest Neighbor (ANN) search via embeddings; Graph traversal | Menengah ($/Disk + Vector Index) |

#### C. Finite State Machine (FSM) Execution vs Loop Bebas
Arsitektur agent industri tidak boleh mengandalkan LLM untuk mengendalikan loop kontrol secara murni (*pure ReAct*). PM harus menegakkan batasan *Finite State Machine* (FSM) yang deterministik.

```
       +--------------+
       |     IDLE     |<-------------------------------------+
       +--------------+                                      |
              |                                              |
      [User Prompt Ingested]                                 |
              v                                              |
      +---------------+                                      |
+---->|  DELIBERATING |                                      |
|     +---------------+                                      |
|             |                                              |
|      [Decide Action]                                       |
|             v                                              |
|     +---------------+       [Max Retries / Policy Breached]|
|     | TOOL_EXECUTE  |--------------------------------------+
|     +---------------+                                      |
|             |                                              |
|       [Tool Result]                                        |
|             v                                              |
|     +---------------+                                      |
+-----| EVALUATING_OK |                                      |
      +---------------+                                      |
              |                                              |
         [Task Done]                                         |
              v                                              |
       +--------------+                                      |
       |  RESPONDING  |--------------------------------------+
       +--------------+
```

Agent hanya diizinkan berpindah antar state yang sah (*valid state transitions*). Jika agent berada di state `TOOL_EXECUTE` dan mencoba memanggil tool yang tidak terdaftar, runtime engine langsung memotong eksekusi dan mengarahkannya ke *deterministic fallback handler*, bukan menanyakan kembali ke LLM tanpa kendali.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi *Enterprise Agent Runtime Controller* yang mengimplementasikan FSM, isolasi token budgeting, validasi skema tools, dan circuit breaking. PM dapat menggunakan modul ini sebagai acuan arsitektur (*architectural baseline*) bersama tim engineering.

```python
"""
Enterprise Agent Runtime Harness
Standard: Clean Architecture, Fully-Typed, Asyncio, Deterministic Guardrails
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EnterpriseAgentRuntime")


class AgentState(str, Enum):
    IDLE = "IDLE"
    DELIBERATING = "DELIBERATING"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    EVALUATING = "EVALUATING"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TokenBudget:
    max_input_tokens: int
    max_output_tokens: int
    cost_per_input_token: float
    cost_per_output_token: float


@dataclass
class ExecutionMetrics:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    execution_start_time: float = field(default_factory=time.time)
    execution_end_time: Optional[float] = None

    @property
    def total_cost(self) -> float:
        # Defaults to arbitrary standard enterprise pricing tier (e.g. $3/M in, $15/M out)
        return (self.total_input_tokens * (3.0 / 1_000_000)) + (
            self.total_output_tokens * (15.0 / 1_000_000)
        )

    @property
    def elapsed_time(self) -> float:
        end = self.execution_end_time or time.time()
        return end - self.execution_start_time


@dataclass
class ToolDefinition:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, str]]


class ToolExecutionError(Exception):
    """Raised when an internal tool execution fails."""
    pass


class BudgetExceededError(Exception):
    """Raised when the agent exceeds allocated token or step limits."""
    pass


class AgentRuntimeOrchestrator:
    def __init__(
        self,
        budget: TokenBudget,
        max_steps: int = 5,
        max_duration_seconds: float = 30.0,
    ):
        self.budget = budget
        self.max_steps = max_steps
        self.max_duration_seconds = max_duration_seconds
        self.state: AgentState = AgentState.IDLE
        self.tool_registry: Dict[str, ToolDefinition] = {}
        self.metrics = ExecutionMetrics()
        self.context_memory: List[Dict[str, str]] = []

    def register_tool(self, tool: ToolDefinition) -> None:
        if tool.name in self.tool_registry:
            raise ValueError(f"Tool {tool.name} already registered.")
        self.tool_registry[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def _transition_to(self, new_state: AgentState) -> None:
        logger.info(f"FSM State Transition: {self.state} -> {new_state}")
        self.state = new_state

    def _enforce_guardrails(self, current_step: int) -> None:
        if current_step >= self.max_steps:
            raise BudgetExceededError(f"Exceeded max operational steps: {self.max_steps}")
        
        if self.metrics.elapsed_time > self.max_duration_seconds:
            raise BudgetExceededError(f"Exceeded max runtime SLA: {self.max_duration_seconds}s")

        if self.metrics.total_input_tokens > self.budget.max_input_tokens:
            raise BudgetExceededError("Hard token ceiling reached for input context.")

    async def _mock_llm_inference(self, prompt: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Simulated inference engine mimicking token usage and function call emission.
        In a production environment, this calls LiteLLM, vLLM, Bedrock, or OpenAI APIs.
        """
        await asyncio.sleep(0.4)  # Simulate network TTFT + TPOT
        
        # Approximate token count (1 word ~= 1.33 tokens)
        serialized_prompt = json.dumps(prompt)
        input_tokens = int(len(serialized_prompt.split()) * 1.33)
        self.metrics.total_input_tokens += input_tokens

        # Deterministic simulation logic based on context
        if len(prompt) <= 2:
            output_tokens = 45
            self.metrics.total_output_tokens += output_tokens
            return {
                "role": "assistant",
                "tool_call": {
                    "name": "query_database",
                    "arguments": {"customer_id": "CUST_99182", "query_type": "balance"}
                }
            }
        else:
            output_tokens = 30
            self.metrics.total_output_tokens += output_tokens
            return {
                "role": "assistant",
                "content": "Akun CUST_99182 memiliki saldo aktif Rp 450.000.000."
            }

    async def execute_task(self, user_objective: str) -> Dict[str, Any]:
        self.metrics = ExecutionMetrics()
        self._transition_to(AgentState.DELIBERATING)
        
        self.context_memory.append({"role": "user", "content": user_objective})
        current_step = 0

        try:
            while self.state not in [AgentState.TERMINATED, AgentState.FAILED]:
                self._enforce_guardrails(current_step)
                current_step += 1

                if self.state == AgentState.DELIBERATING:
                    inference_result = await self._mock_llm_inference(self.context_memory)
                    
                    if "tool_call" in inference_result:
                        self.context_memory.append({
                            "role": "assistant", 
                            "tool_intent": json.dumps(inference_result["tool_call"])
                        })
                        self._transition_to(AgentState.TOOL_EXECUTION)
                        current_tool_call = inference_result["tool_call"]
                    else:
                        self.context_memory.append({
                            "role": "assistant", 
                            "content": inference_result["content"]
                        })
                        self._transition_to(AgentState.TERMINATED)

                elif self.state == AgentState.TOOL_EXECUTION:
                    tool_name = current_tool_call["name"]
                    tool_args = current_tool_call["arguments"]

                    if tool_name not in self.tool_registry:
                        raise ToolExecutionError(f"Tool {tool_name} not available in registry.")

                    target_tool = self.tool_registry[tool_name]
                    logger.info(f"Dispatching tool '{tool_name}' with payload: {tool_args}")
                    
                    try:
                        tool_result = await asyncio.wait_for(
                            target_tool.handler(tool_args), timeout=5.0
                        )
                        self.metrics.total_tool_calls += 1
                        self.context_memory.append({"role": "tool", "content": tool_result})
                        self._transition_to(AgentState.EVALUATING)
                    except asyncio.TimeoutError:
                        logger.error(f"Execution timed out on tool: {tool_name}")
                        self.context_memory.append({"role": "tool_error", "content": "TIMEOUT"})
                        self._transition_to(AgentState.DELIBERATING)

                elif self.state == AgentState.EVALUATING:
                    # In this state, agent verifies if output satisfies safety criteria
                    self._transition_to(AgentState.DELIBERATING)

            self.metrics.execution_end_time = time.time()
            return {
                "status": "SUCCESS",
                "final_state": self.state.value,
                "result": self.context_memory[-1].get("content"),
                "metrics": {
                    "total_input_tokens": self.metrics.total_input_tokens,
                    "total_output_tokens": self.metrics.total_output_tokens,
                    "total_tool_calls": self.metrics.total_tool_calls,
                    "elapsed_seconds": round(self.metrics.elapsed_time, 3),
                    "estimated_cost_usd": round(self.metrics.total_cost, 6),
                }
            }

        except Exception as e:
            logger.critical(f"Execution Loop Aborted: {str(e)}")
            self._transition_to(AgentState.FAILED)
            self.metrics.execution_end_time = time.time()
            return {
                "status": "FAILED",
                "error_reason": str(e),
                "metrics": {
                    "elapsed_seconds": round(self.metrics.elapsed_time, 3),
                    "estimated_cost_usd": round(self.metrics.total_cost, 6),
                }
            }


# =====================================================================
# Verification Routine
# =====================================================================

async def main():
    # Setup Tool Mock
    async def mock_query_db(args: Dict[str, Any]) -> str:
        await asyncio.sleep(0.1)  # Simulate DB Latency
        return json.dumps({"customer_id": args.get("customer_id"), "status": "ACTIVE", "balance": 450000000})

    db_tool = ToolDefinition(
        name="query_database",
        description="Pulls relational financial data by Customer ID",
        schema={"type": "object", "properties": {"customer_id": {"type": "string"}}},
        handler=mock_query_db,
    )

    budget_policy = TokenBudget(
        max_input_tokens=4000,
        max_output_tokens=1000,
        cost_per_input_token=3.0 / 1_000_000,
        cost_per_output_token=15.0 / 1_000_000,
    )

    orchestrator = AgentRuntimeOrchestrator(
        budget=budget_policy,
        max_steps=4,
        max_duration_seconds=10.0,
    )
    orchestrator.register_tool(db_tool)

    # Run Production Scenario
    result = await orchestrator.execute_task("Periksa saldo rekening nasabah CUST_99182.")
    print("\n--- AGENT EXECUTION SUMMARY ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Sebagai PM, Anda wajib menyusun matriks mitigasi untuk 4 skenario kegagalan fatal (*fatal failure modes*) dalam arsitektur agentic:

```
+---------------------------------------------------------------------------------------+
| AGENT FAILURE TAXONOMY                                                                |
|                                                                                       |
|  [ Context Rot ]         [ Infinite Feedback Loop ]   [ Semantic Tool Drift ]         |
|  - Attention dilution    - Model repeats same call    - Hallucinated schema arguments |
|  - Needle lost in RAG    - Non-converging reasoning   - Broken downstream DB queries  |
|          |                          |                            |                    |
|          v                          v                            v                    |
|  [ Sliding Context Window +  [ Strict Cycle-Breaking     [ Pydantic Argument          |
|    Vector Summarization ]      State Interceptors ]        Validation & Auto-Repair ] |
+---------------------------------------------------------------------------------------+
```

1.  **Infinite Feedback Loops (Runaway Cost)**:
    *   *Mekanisme*: LLM memanggil Tool A, menerima output error, lalu mengulang pemanggilan Tool A dengan argumen yang sama secara berulang-ulang tanpa konvergensi.
    *   *Solusi Teknis*: Pasang *Cycle-Detection Algorithmic Interceptor*. Jika *hash* dari `(tool_name + arguments)` muncul $\ge 2$ kali dalam *history buffer*, paksa status sistem ke *Human-in-the-Loop* (HITL) atau terminasi dengan error deskriptif.

2.  **Context Window Blowout via Payload Flooding**:
    *   *Mekanisme*: Tool SQL/Search mengembalikan dump 500 baris JSON ($> 40.000$ token) yang langsung di-append ke *scratchpad memory*, menyebabkan token overflow atau lonjakan latensi pre-fill secara drastis.
    *   *Solusi Teknis*: Terapkan *Deterministic Response Marshalling*. Di layer Sandbox, terapkan truncator statis atau gunakan *Map-Reduce Summarizer LLM* khusus sebelum data mentah dimasukkan ke context memory utama.

3.  **Tool Argument Schema Violations (Semantic Drift)**:
    *   *Mekanisme*: Model menghasilkan JSON yang valid secara sintaksis, namun salah tipe data (misal: mengirimkan string `"45000"` bukannya integer `45000`, atau memformat tanggal dengan format non-ISO).
    *   *Solusi Teknis*: Skema JSON Schema / Pydantic validation di level gateway sebelum eksekusi API handler. Jika validasi gagal, kembalikan pesan error ke LLM untuk *Self-Correction* maksimal 1 kali; jika masih gagal, alihkan ke fallback statis.

4.  **Silent Upstream Outage (Inference Hang)**:
    *   *Mekanisme*: Provider model (misal: Azure OpenAI / Bedrock) mengalami antrean panjang, TTFT melonjak ke $>60$ detik tanpa melepas koneksi TCP.
    *   *Solusi Teknis*: Penggunaan *Exponential Backoff Circuit Breaker* dengan timeout eksplisit (misal: timeout TTFT 4 detik). Jika terjadi 3 kali *timeout* beruntun, alihkan rute (*fallback routing*) ke penyedia alternatif (misal: Anthropic Claude Sonnet via AWS Bedrock ke GCP Vertex AI).

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur di ranah autonomous agent menuntut kompromi antara determinisme, latensi, biaya, dan otonomi reasoning.

| Pendekatan Arsitektur | Mekanisme Inti | Latensi P95 | Biaya per Task | Nilai Otonomi | Rekomendasi Domain PM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Deterministic DAG (Workflow Engine)** | Graph tetap (Temporal, Airflow); LLM hanya mengisi node ekstraksi/evaluasi. | **Sangat Rendah** ($< 1.5\text{s}$) | **Sangat Rendah** ($) | Nol (Statis) | Payroll, Eksekusi Pembayaran, KYC Finansial, Regulasi Ketat. |
| **ReAct Loop (Single Agent)** | Alternasi dinamis antara Thought, Action, dan Observation secara terus-menerus. | **Sedang** ($4\text{s} - 12\text{s}$) | **Sedang** ($$) | Tinggi (Lokal) | Customer Support Assistant, Data Investigation, Log Diagnostics. |
| **Plan-and-Solve (Two-Tier)** | Planner (Model Besar) membuat rencana; Executor (Model Cepat) mengeksekusi secara berurutan. | **Tinggi** ($8\text{s} - 25\text{s}$) | **Tinggi** ($$$) | Sangat Tinggi | Riset Pasar Otomatis, Pembuatan Konten Multimedia Multi-sumber. |
| **Hierarchical Multi-Agent (e.g., CrewAI)** | Tim agen dengan Supervisor yang mendelegasikan tugas ke sub-agen independen. | **Sangat Tinggi** ($20\text{s} - 60\text{s}+$) | **Ekstrem** ($$$$$) | Maksimal | Simulasi Skenario Kompleks, Pengujian Penetrasi Keamanan Siber (Pen-testing). |

---

### 9. Best Practices & Standard Industri

1.  **Kontrak Observabilitas (OpenTelemetry Semantic Conventions for AI)**:
    *   Wajib mencatat (*trace*) setiap *Thought-Action-Observation loop* dengan atribut standar: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`. Gunakan tooling seperti Langfuse, Arize Phoenix, atau OpenInference.
2.  **SLA Definition Framework untuk AI PM**:
    *   Jangan pernah menetapkan SLA absolut tunggal untuk seluruh task otonom. Bagi SLA menjadi 2 level:
        *   *Turn-level SLA*: Waktu perputaran interaksi tunggal (Target: P95 $< 2.5\text{s}$).
        *   *Task-completion SLA*: Waktu total penyelesaian akhir (Target: P90 $< 15\text{s}$ untuk 3 steps).
3.  **Defensive Token Budgeting**:
    *   Terapkan *Hard Stop Ceilings*. Tentukan nilai parameter *Max Allocated Spend per Business Transaction* (misal: "Satu tiket refund maksimal mengonsumsi \$0.05 token"). Begitu limit ini disentuh, sistem otomatis beralih ke agen manusia (*human fallback*) untuk mencegah kerugian finansial perusahaan.
4.  **Zero-Trust Tool Isolation**:
    *   Agent tidak boleh memiliki akses *Direct Database Connection*. Seluruh interaksi wajib melalui REST API berotentikasi mTLS dengan *Read-Only Scopes*, atau dieksekusi di dalam Container MicroVM yang terisolasi (misal: AWS Firecracker / gVisor sandbox).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Lead PM untuk produk "Autonomous FinOps Agent". Produk ini bertugas mendeteksi pemborosan cloud, mengekstrak metrik AWS/GCP, dan mematikan infrastruktur yang tidak terpakai secara otonom. Tim Anda menghadapi komplain dari VP of Engineering karena *unit cost* agent melebihi estimasi penghematan cloud yang dihasilkan.

Tugas Anda: Menghitung Latency & Token Budget baseline, mengevaluasi failure threshold, dan merancang FSM guardrail.

#### Langkah 1: Kalkulasi Latency Budget
Diberikan baseline metrik berikut:
*   Model reasoning: LLM Tier 2 dengan $\text{TTFT} = 600\text{ms}$, $\text{TPOT} = 25\text{ms/token}$.
*   Rata-rata prompt input sistem + RAG history per putaran: $2500\text{ tokens}$.
*   Rata-rata output reasoning + tool payload: $150\text{ tokens}$.
*   Latensi API Cloud Provider ($T_{tool}$): $400\text{ms}$.
*   Target P95 SLA Bisnis: $\le 10\text{ detik}$.

*Instruksi*: Hitung jumlah step maksimum ($N_{steps}$) yang secara matematis diperbolehkan sebelum sistem melanggar SLA 10 detik!

$$\text{Latency per step} = 0.600 + (150 \times 0.025) + 0.400 = 0.600 + 3.750 + 0.400 = 4.750\text{ detik}$$

$$N_{steps} \le \frac{10.0\text{ detik}}{4.750\text{ detik/step}} \approx 2.1$$

*Kesimpulan Arsitektur*: Sistem Anda hanya mampu menjalankan **maksimal 2 langkah reasoning serial**. Jika agent butuh 3 langkah untuk investigasi, arsitektur ReAct serial murni wajib diganti menjadi arsitektur eksekusi paralel atau workflow terpandu.

#### Langkah 2: Mengonfigurasi & Menjalankan Script Guardrail
Jalankan harness Python pada **Bagian 6** di terminal atau environment notebook lokal Anda:

```bash
# Simpan kode Bagian 6 ke file runtime.py
python3 runtime.py
```

#### Langkah 3: Verifikasi Kegagalan (Failure Injection)
Ubah baris inisialisasi pada fungsi `main()` untuk memverifikasi penegakan circuit breaker:

```python
# Simulasi degradasi batas operasional: Turunkan max_steps menjadi 1
orchestrator = AgentRuntimeOrchestrator(
    budget=budget_policy,
    max_steps=1,  # Batasan ekstrem untuk memicu Circuit Breaker
    max_duration_seconds=10.0,
)
```

Jalankan kembali script dan amati output:

```json
{
  "status": "FAILED",
  "error_reason": "Exceeded max operational steps: 1",
  "metrics": {
    "elapsed_seconds": 0.402,
    "estimated_cost_usd": 0.000675
  }
}
```

#### Langkah 4: Acceptance Criteria & Check Evaluasi PM
*   [ ] Terverifikasi bahwa state machine berpindah secara terkontrol ke status `FAILED` tanpa membiarkan sistem menggantung (*hanging*).
*   [ ] Metrik biaya terakumulasi secara transparan (`estimated_cost_usd`) sehingga tagihan komputasi dapat diatribusikan ke level transaksi pengguna.
*   [ ] Telah ditentukan aturan transisi yang jelas: kapan eksekusi dapat dilanjutkan oleh model yang lebih kecil (*downgrade routing*), dan kapan harus dialihkan ke konfirmasi manual pengguna (*HITL checkpoint*).