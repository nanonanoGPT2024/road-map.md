# MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Autonomous Agents & RL

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengevaluasi dan Merancang** arsitektur *Multi-Agent System* (MAS) stateful berbasis graph siklik (*Cyclic Directed Graph*) yang terisolasi, deterministik, dan toleran terhadap kegagalan (*fault-tolerant*).
2. **Mengonstruksi** *Execution Engine* agen otonom menggunakan pola *Stateful Actor Pattern* dengan mekanisme *Time-Travel Debugging*, persistensi *state snapshot*, dan mitigasi *infinite-loop*.
3. **Mengintegrasikan** infrastruktur memori hibrida (*Short-term Working Memory*, *Episodic Vector Store*, dan *Semantic Knowledge Graph*) dengan garansi konsistensi data transaksional (ACID/BASE).
4. **Membangun dan Mengoptimalkan** *pipeline alignment* Reinforcement Learning (DPO/PPO) skala produksi dengan validasi reward eksplisit, mitigasi *reward hacking*, dan perlindungan model terhadap *catastrophic forgetting*.
5. **Mengimplementasikan** kontrol produksi enterprise mencakup *Latency Budgeting*, *Semantic Circuit Breakers*, *Token Cost Hedging*, dan *Deterministic Fallback Mechanisms*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Python Lanjutan (3.11+)**: AsyncIO (`async`/`await`, `TaskGroup`, `Semaphore`), Typing (`TypeVar`, `Generic`, `Annotated`), metaprogramming, dan serialisasi data (Pydantic v2).
- **Fondasi Agentic & Prompt Engineering**: Prinsip dasar ReAct (*Reasoning + Acting*), Chain-of-Thought (CoT), serta pemanggilan fungsi (*Function Calling / Tool Calling*).
- **Dasar Reinforcement Learning**: Markov Decision Processes (MDP), Policy Gradient, Value Iteration, dan formulasi Loss Function RLHF.
- **Sistem Terdistribusi**: Konsep konsistensi data, Redis Pub/Sub, arsitektur event-driven, dan Vector Database (HNSW indexing, cosine similarity).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 The Stateful Actor Model in Autonomous Agents
Dalam arsitektur enterprise, agen otonom tidak boleh diperlakukan sebagai loop `while True` monolitik yang memanggil LLM secara sekuensial. Pola ini rentan terhadap *state corruption*, *unbounded memory growth*, dan ketidakmampuan pulih pasca-kegagalan (*crash-recovery*).

Arsitektur produksi mengadopsi variasi dari **Actor Model**:
- **State Partitioning**: Setiap entitas eksekusi memiliki *state* terisolasi yang diwakili oleh struktur data *immutable* atau *append-only*.
- **Message Passing**: Agen berkomunikasi secara asinkron melalui *inbox* yang divalidasi oleh skema kontrak data.
- **State Checkpointing**: Pada setiap transisi edge dalam graph eksekusi, engine menyimpan representasi *snapshot* (delta state) ke *durable store* (Redis, PostgreSQL). Jika node eksekusi crash (misalnya timeout dari provider LLM), agen dapat melanjutkan eksekusi dari *checkpoint* terakhir secara idempoten.

```
       [Input Payload]
              │
              ▼
    ┌───────────────────┐
    │ State Checkpointer│◄──────────┐
    │ (PostgreSQL/Redis)│           │ Snapshot
    └─────────┬─────────┘           │ Delta
              │ Restore State       │
              ▼                     │
    ┌───────────────────┐           │
    │   Execution Node  ├───────────┘
    │  (LLM Reasoning)  │
    └─────────┬─────────┘
              │ Tool Call Intent
              ▼
    ┌───────────────────┐
    │ Semantic Guardrail│──(Violation)──► [Deterministic Fallback]
    └─────────┬─────────┘
              │ Passed
              ▼
    ┌───────────────────┐
    │ Tool Execution Bus│
    │(Isolated Sandbox) │
    └───────────────────┘
```

### 3.2 Cyclic Graph Routing & Multi-Agent Collaboration
Pendekatan rantai linier (*Chains*) membatasi kemampuan agen untuk melakukan koreksi mandiri (*self-reflection* atau *reflexion*). Produksi membutuhkan **Cyclic Directed Graphs** di mana:
- **Node**: Unit komputasi atomik (LLM call, deterministic data processing, database write).
- **Edge**: Jalur transisi bersyarat (*conditional edges*) yang mengevaluasi output node sebelumnya untuk menentukan node berikutnya berdasarkan evaluasi logis (bukan sekadar heuristik teks).
- **Reducer**: Fungsi agregasi deterministik yang mengatur bagaimana *state update* dari beberapa node digabungkan (misalnya: `Operator.add` untuk append log pesan, overwrite untuk update variabel target).

### 3.3 Hybrid Memory Engine Architecture
Sebuah agen otonom memerlukan 3 tingkatan memori:
1. **Working Memory (In-Context / Short-Term)**: Buffer token aktif berisi interaksi yang sedang berjalan, dikompresi menggunakan dynamic token summarization saat mendekati batas konteks.
2. **Episodic Memory (Mid-Term)**: Disimpan dalam Vector Database (Dense/Sparse Embeddings) untuk mengingat interaksi masa lalu berdasarkan kedekatan semantik (*semantic similarity*).
3. **Declarative/Semantic Memory (Long-Term)**: Disimpan dalam Knowledge Graph (Entity-Relation triples) untuk relasi deterministik (misalnya, hak akses pengguna, preferensi bisnis inti, aturan regulasi).

### 3.4 Production RL: Dari RLHF ke Direct Preference Optimization (DPO)
Pada skala enterprise, pelatihan Proximal Policy Optimization (PPO) tradisional mahal dan tidak stabil karena membutuhkan 4 model aktif serentak di GPU memory: *Policy Model*, *Value Model*, *Reference Model*, dan *Reward Model*.

**DPO (Direct Preference Optimization)** merevolusi pipeline ini dengan mengekspresikan probabilitas reward secara analitis langsung melalui implicit reward:

$$r(x, y) = \beta \log \frac{\pi_\theta(y \mid x)}{\pi_{\text{ref}}(y \mid x)}$$

Objektif loss DPO diturunkan menjadi:

$$\mathcal{L}_{\text{DPO}}(\pi_\theta; \pi_{\text{ref}}) = -\mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w \mid x)}{\pi_{\text{ref}}(y_w \mid x)} - \beta \log \frac{\pi_\theta(y_l \mid x)}{\pi_{\text{ref}}(y_l \mid x)} \right) \right]$$

Keunggulan Arsitektur:
- Menghilangkan *Reward Model training loop* dan *Value Function estimation*.
- Stabil secara numerik (tidak ada divergensi PPO policy updates).
- Mengurangi kebutuhan VRAM GPU hingga 40-50% saat training alignment agen.

---

## 4. Why & What

| Dimensi | Pola Naif (Proof-of-Concept) | Pola Produksi Enterprise |
| :--- | :--- | :--- |
| **State Management** | Global in-memory variable (Python dictionary). Hilang saat proses crash. | Distributed, versioned state persistence (PostgreSQL/Redis) dengan dukungan *time-travel*. |
| **Control Flow** | Unbounded while loop (`while not stop_condition`). | Bound execution graph dengan batas iterasi maksimum, timeout per node, dan semantic circuit breakers. |
| **Tool Execution** | Agen memanggil arbitrary API secara langsung tanpa validasi. | Isolated sandboxed execution, strict Pydantic payload verification, audit logging, & idempotency tokens. |
| **Failure Mode** | LLM berhalusinasi atau exception unhandled -> Proses mati. | Graceful degradation, error reflection node, deterministic hard-coded fallback. |
| **Optimization** | Rely on continuous Zero-Shot prompting dengan prompt raksasa. | Continuous alignment via DPO checkpoints, dynamic system context, dan task-specific LoRA adapters. |

---

## 5. How (Workflow Detail)

Alur kerja orkestrasi agen otonom siklik pada skala enterprise:

```
[User Request]
       │
       ▼
 1. State Initializer (Validasi schema, enrich context dari Episodic Memory)
       │
       ▼
 2. Supervisor / Planner Node (Menghasilkan Action Plan terstruktur)
       │
       ├────────────────────────────────────────┐
       ▼                                        ▼
 3. Specialized Worker Node (Async)       4. Deterministic Evaluator
    - Execute Tool (Sandbox)                 - Skema output valid?
    - Catch transient error                  - Constraint terpenuhi?
       │                                        │
       └───────────────────┬────────────────────┘
                           │
                           ▼
 5. Reflection & Guardrail Node
    ├── [Kondisi Gagal / Halusinasi]: Increment retry counter -> Loop kembali ke Planner
    └── [Kondisi Berhasil]: Write Snapshot -> Return Final State -> Stream output ke Client
```

1. **Initialization & Ingestion**: Request divalidasi via Pydantic schema, ID sesi dibuat, dan state diinisialisasi bersama *Working Memory*.
2. **Context Enrichment**: Pencarian asinkron ke Vector Database dan Knowledge Graph untuk menyuntikkan fakta relevan ke system prompt.
3. **Execution Loop (Bounded)**:
   - Node perencana menganalisis state dan memancarkan aksi.
   - Guardrail memvalidasi apakah parameter tool aman dan sesuai schema.
   - Worker mengeksekusi tool dengan timeout ketat (`asyncio.wait_for`).
   - Hasil tool ditambahkan ke daftar pesan (append-only reducer).
4. **Self-Reflection & Condition Routing**:
   - Node evaluasi memverifikasi apakah jawaban menyelesaikan masalah atau membutuhkan iterasi lanjut.
   - Jika `step_count > MAX_STEPS`, transisikan paksa ke node fallback deterministik.
5. **State Persist & Flush**: Snapshot state ditulis secara transaksional ke checkpoint store. Output dikirim ke user.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Operasi (OS)
Sebuah sistem agen otonom produksi analog dengan **Modern Operating System**:
- **LLM**: CPU. Mampu melakukan komputasi probabilistik tingkat tinggi, namun tidak memiliki memori permanen dan tidak memiliki akses I/O langsung secara aman.
- **Context Window**: RAM (L1/L2 Cache). Ruang kerja cepat, berbiaya tinggi, dan terbatas.
- **Vector DB / Graph**: Non-Volatile Storage (SSD/NVMe). Penyimpanan eksternal untuk data masa lalu.
- **Guardrails / State Engine**: OS Kernel & Memory Protection. Mengatur alokasi resource, mencegah segmentation fault (infinite loop), dan membatasi *system calls* (tools) yang tidak aman.

### Diagram Arsitektur Multi-Agent Cyclic Graph

```
+-----------------------------------------------------------------------------------+
|                        ENTERPRISE AGENT RUNTIME (CORE)                            |
|                                                                                   |
|                  +-----------------------------------------+                      |
|                  |       Incoming Action Request           |                      |
|                  +--------------------+--------------------+                      |
|                                       |                                           |
|                                       v                                           |
|                  +-----------------------------------------+                      |
|                  |       State Schema Validation           |                      |
|                  +--------------------+--------------------+                      |
|                                       |                                           |
|                                       v                                           |
|        +-------------------> [ Supervisor Node ] <-------------------+            |
|        |                              |                              |            |
|        |                              v                              |            |
|        |                  [ Conditional Router Edge ]                |            |
|        |                   /                     \                   |            |
|        |        (Route: Data Agent)       (Route: Action Agent)      |            |
|        |                 /                         \                 |            |
|        |                v                           v                |            |
|        |      +-------------------+       +-------------------+      |            |
|        |      | Data Retrieval    |       | Action Executor   |      |            |
|        |      | Worker Node       |       | Worker Node       |      |            |
|        |      +---------+---------+       +---------+---------+      |            |
|        |                |                           |                |            |
|        |                +-------------+-------------+                |            |
|        |                              |                              |            |
|        |                              v                              |            |
|        |                 +--------------------------+                |            |
|        |                 |   Deterministic Tools    |                |            |
|        |                 | (API, VectorDB, Sandbox) |                |            |
|        |                 +------------+-------------+                |            |
|        |                              |                              |            |
|        |                              v                              |            |
|        |                 +--------------------------+                |            |
|        |                 | Dynamic Evaluator Node   |                |            |
|        |                 |   (Confidence Scoring)   |                |            |
|        |                 +------------+-------------+                |            |
|        |                              |                              |            |
|        |                   [ Is Goal Completed? ]                    |            |
|        |                   /                    \                    |            |
|        |             (No / Retry)             (Yes)                  |            |
|        +-------------------+                    |                    |            |
|        |                                        v                    |            |
|  [Step < Limit]                   +---------------------------+      |            |
|        ^                          | Final Response Synthesizer|      |            |
|        |                          +-------------+-------------+      |            |
|  [Step >= Limit]                                |                    |            |
|        |                                        v                    |            |
|        +-----> [ Fallback Node ] ---> +--------------------+         |            |
|                                       | Checkpointer Store |         |            |
|                                       | (PostgreSQL/Redis) |         |            |
|                                       +--------------------+         |            |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Pure Python Async State Machine Agent
Implementasi mendasar agen berbasis Finite State Machine (FSM) tanpa dependensi library eksternal yang kompleks.

```python
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

class AgentStep(str, Enum):
    PLAN = "PLAN"
    ACT = "ACT"
    REFLECT = "REFLECT"
    END = "END"

@dataclass
class AgentState:
    task: str
    current_step: AgentStep = AgentStep.PLAN
    history: List[str] = field(default_factory=list)
    iteration_count: int = 0
    is_success: bool = False
    max_iterations: int = 3

class MinimalAutonomousAgent:
    async def plan_node(self, state: AgentState) -> AgentState:
        state.history.append(f"[PLAN] Analyzing task: {state.task}")
        await asyncio.sleep(0.01)  # Simulasi compute async
        state.current_step = AgentStep.ACT
        return state

    async def act_node(self, state: AgentState) -> AgentState:
        state.history.append(f"[ACT] Executing action for iteration {state.iteration_count}")
        await asyncio.sleep(0.01)
        state.current_step = AgentStep.REFLECT
        return state

    async def reflect_node(self, state: AgentState) -> AgentState:
        state.iteration_count += 1
        state.history.append(f"[REFLECT] Validating results. Iteration: {state.iteration_count}")
        await asyncio.sleep(0.01)
        
        # Kondisi deterministik selesai
        if state.iteration_count >= 2:
            state.is_success = True
            state.current_step = AgentStep.END
        elif state.iteration_count >= state.max_iterations:
            state.current_step = AgentStep.END
        else:
            state.current_step = AgentStep.PLAN
        return state

    async def run(self, task: str) -> AgentState:
        state = AgentState(task=task)
        while state.current_step != AgentStep.END:
            if state.current_step == AgentStep.PLAN:
                state = await self.plan_node(state)
            elif state.current_step == AgentStep.ACT:
                state = await self.act_node(state)
            elif state.current_step == AgentStep.REFLECT:
                state = await self.reflect_node(state)
        return state

# Eksekusi
if __name__ == "__main__":
    agent = MinimalAutonomousAgent()
    final_state = asyncio.run(agent.run("Proses Audit Log Transaksi Finansial"))
    print(f"Status Sukses: {final_state.is_success}")
    print("History Eksekusi:\n" + "\n".join(final_state.history))
```

### 7.2 Practical Example: Enterprise Cyclic Multi-Agent Engine
Implementasi tingkat produksi dengan validasi skema runtime (Pydantic), *custom memory store*, pembatas siklus (*circuit-breaker loop*), dan penanganan error terisolasi.

```python
from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any, Callable, Dict, List, Literal, Optional, Sequence
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EnterpriseAgentRuntime")

# ==========================================
# 1. SCHEMAS & STATE DEFINITION
# ==========================================

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: Optional[str] = None

def append_messages(existing: List[Message], new_messages: List[Message]) -> List[Message]:
    """Append-only reducer untuk pesan state."""
    return existing + new_messages

class GraphState(BaseModel):
    session_id: str
    task_input: str
    messages: Annotated[List[Message], append_messages] = Field(default_factory=list)
    next_node: str = "orchestrator"
    retry_count: int = 0
    max_retries: int = 3
    final_output: Optional[str] = None
    is_terminal: bool = False

# ==========================================
# 2. CHECKPOINT STORE (MOCK DISTRIBUTED DB)
# ==========================================

class DistributedCheckpointer:
    def __init__(self) -> None:
        self._storage: Dict[str, List[str]] = {}

    async def save_snapshot(self, session_id: str, state: GraphState) -> None:
        state_json = state.model_dump_json()
        if session_id not in self._storage:
            self._storage[session_id] = []
        self._storage[session_id].append(state_json)
        logger.info(f"Checkpoint persisted for session '{session_id}'. Version {len(self._storage[session_id])}")

    async def get_latest_snapshot(self, session_id: str) -> Optional[GraphState]:
        if session_id in self._storage and self._storage[session_id]:
            latest_json = self._storage[session_id][-1]
            return GraphState.model_validate_json(latest_json)
        return None

# ==========================================
# 3. NODE IMPLEMENTATIONS & ENGINE
# ==========================================

class EnterpriseAgentEngine:
    def __init__(self, checkpointer: DistributedCheckpointer) -> None:
        self.checkpointer = checkpointer

    async def orchestrator_node(self, state: GraphState) -> Dict[str, Any]:
        logger.info(f"[{state.session_id}] Executing Orchestrator Node...")
        await asyncio.sleep(0.05)  # Simulasi latency inferensi LLM
        
        # Logika deterministik perutean berdasarkan state
        if state.retry_count > 0:
            return {
                "next_node": "data_worker",
                "messages": [Message(role="assistant", content="Mencoba ulang melalui Data Worker dengan strategi defensif.")]
            }
            
        return {
            "next_node": "data_worker",
            "messages": [Message(role="assistant", content="Memulai ekstraksi data analitik.")]
        }

    async def data_worker_node(self, state: GraphState) -> Dict[str, Any]:
        logger.info(f"[{state.session_id}] Executing Data Worker Node...")
        await asyncio.sleep(0.05)
        
        # Simulasi flakiness untuk memicu conditional reflection
        if state.retry_count == 0:
            logger.warning(f"[{state.session_id}] Worker mendeteksi dependensi data gagal divalidasi!")
            return {
                "next_node": "evaluator_node",
                "messages": [Message(role="tool", content="ERROR: Invalid telemetry response schema.")]
            }
            
        # Simulasi keberhasilan pada percobaan berikutnya
        return {
            "next_node": "evaluator_node",
            "messages": [Message(role="tool", content="SUCCESS: Telemetry data valid: [Metric A=99.4%, Metric B=0.1%]")]
        }

    async def evaluator_node(self, state: GraphState) -> Dict[str, Any]:
        logger.info(f"[{state.session_id}] Executing Evaluator (Guardrail) Node...")
        latest_message = state.messages[-1].content if state.messages else ""
        
        if "SUCCESS" in latest_message:
            return {
                "next_node": "finalizer_node",
                "messages": [Message(role="system", content="Evaluasi lolos verifikasi integritas.")]
            }
        
        # Evaluasi kegagalan dan penanganan infinite-loop
        new_retry = state.retry_count + 1
        if new_retry >= state.max_retries:
            logger.error(f"[{state.session_id}] Maximum retries reached. Mengalihkan ke Fallback.")
            return {
                "next_node": "fallback_node",
                "retry_count": new_retry,
                "messages": [Message(role="system", content="Threshold retry terlampaui. Menghentikan siklus.")]
            }
            
        return {
            "next_node": "orchestrator",
            "retry_count": new_retry,
            "messages": [Message(role="system", content=f"Kegagalan terdeteksi. Memicu retry siklus ke-{new_retry}.")]
        }

    async def finalizer_node(self, state: GraphState) -> Dict[str, Any]:
        logger.info(f"[{state.session_id}] Executing Finalizer...")
        output = f"Tugas '{state.task_input}' berhasil diproses secara otonom."
        return {
            "next_node": "end",
            "final_output": output,
            "is_terminal": True
        }

    async def fallback_node(self, state: GraphState) -> Dict[str, Any]:
        logger.info(f"[{state.session_id}] Executing Fallback Node...")
        output = f"Peringatan: Tugas '{state.task_input}' gagal diproses mandiri. Rute fallback deterministik dieksekusi."
        return {
            "next_node": "end",
            "final_output": output,
            "is_terminal": True
        }

    # ==========================================
    # 4. GRAPH RUNTIME EXECUTION
    # ==========================================

    async def run(self, session_id: str, task: str) -> GraphState:
        state = GraphState(session_id=session_id, task_input=task)
        state.messages.append(Message(role="user", content=task))
        
        node_registry: Dict[str, Callable[[GraphState], Any]] = {
            "orchestrator": self.orchestrator_node,
            "data_worker": self.data_worker_node,
            "evaluator_node": self.evaluator_node,
            "finalizer_node": self.finalizer_node,
            "fallback_node": self.fallback_node,
        }

        while not state.is_terminal:
            current_node_name = state.next_node
            node_fn = node_registry.get(current_node_name)
            
            if not node_fn:
                raise RuntimeError(f"Node execution error: Unknown node '{current_node_name}'")

            # Eksekusi node atomik
            node_output: Dict[str, Any] = await node_fn(state)
            
            # Aplikasi reducer dan pembaruan state secara deterministik
            for key, val in node_output.items():
                if key == "messages":
                    state.messages = append_messages(state.messages, val)
                else:
                    setattr(state, key, val)

            # Persistensi snapshot setelah setiap transisi state
            await self.checkpointer.save_snapshot(session_id, state)
            
            if state.next_node == "end":
                state.is_terminal = True

        return state

# ==========================================
# 5. ENTRYPOINT TEST
# ==========================================

async def main() -> None:
    store = DistributedCheckpointer()
    runtime = EnterpriseAgentEngine(checkpointer=store)
    
    session_id = "sess-prod-0091"
    task_payload = "Audit dan Rekonsiliasi Log Anomali Latensi Gateway API"
    
    final_result = await runtime.run(session_id, task_payload)
    print("\n" + "="*60)
    print(f"EKSEKUSI SELESAI | Status Terminal: {final_result.is_terminal}")
    print(f"Output Akhir: {final_result.final_output}")
    print(f"Jumlah Transisi State: {len(final_result.messages)}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Tier-1 FinTech Autonomous Clearing & Liquidity Rebalancing Engine
Perusahaan dompet digital nasional dengan volume transaksi harian \$40M menghadapi volatilitas saldo penyedia likuiditas bank (*Liquidity Providers* - LP) yang fluktuatif di malam hari. 

#### Masalah Produksi:
- Operator manusia lambat mengeksekusi rebalancing antar-LP (SLA > 45 menit), menyebabkan lonjakan *transaction failure rate* hingga 8.2% saat terjadi *traffic spike*.
- Pendekatan aturan statis (*if-else thresholds*) gagal merespons dependensi non-linear: biaya settlement antar-bank, window kliring BI-FAST, dan mitigasi resiko *counterparty default*.

#### Solusi Arsitektur Otonom:
- **Hierarchical Multi-Agent Graph**:
  - **Risk Invariant Agent**: Menggunakan model terverifikasi formal untuk menjamin batas minimum modal cadangan regulasi (*Capital Adequacy Ratio*). Bertindak sebagai *Hard Constraint Gatekeeper*.
  - **Liquidity Predictor Agent**: Melakukan kalkulasi runtun waktu (*Temporal Time-Series Forecasting*) atas *expected outbound payment* untuk 3 jam ke depan.
  - **Execution Agent**: Mengorkestrasikan instruksi mutasi via API perbankan dengan jaminan transaksi dua fase (*Two-Phase Commit* / Saga Pattern).
- **DPO-Trained Policy**:
  - LLM controller tidak diizinkan memanggil arbitrary function. Model diarahkan dengan dataset preferensi DPO yang dilatih khusus menggunakan 50.000 log keputusan historis Head of Treasury. Model memprioritaskan biaya kliring termurah dengan batas waktu settlement teraman.

```
                            [Incoming Treasury Alert]
                                       │
                                       ▼
                       [Supervisor / Coordinator Agent]
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
      [Liquidity Predictor Agent]                [Market Condition Agent]
      (Predict cashflow delta)                   (Fetch spread & fees)
                 │                                           │
                 └─────────────────────┬─────────────────────┘
                                       │
                                       ▼
                         [Proposed Allocation Plan]
                                       │
                                       ▼
                        [Risk Invariant Agent (Gate)]
                                       │
                    ┌──────────────────┴──────────────────┐
               [Rule Pass]                           [Rule Breach]
                    │                                     │
                    ▼                                     ▼
        [Two-Phase Commit Agent]                [Deterministic Rejection]
         (Execute via Saga Bus)                  (Alert Human On-Call)
```

#### Hasil Metrik Produksi:
- **Penurunan Latensi Rebalancing**: Dari 45 menit menjadi 8.4 detik secara *end-to-end*.
- **Efisiensi Biaya Kliring**: Penghematan biaya settlement antar-bank sebesar \$120.000 per kuartal.
- **Toleransi Kesalahan**: 0% pelanggaran limit modal regulator selama 12 bulan operasional secara penuh.

---

## 9. Trade-offs

| Parameter Arsitektur | Pilihan A | Pilihan B | Analisis Kompromi Teknis |
| :--- | :--- | :--- | :--- |
| **Pola Eksekusi Agen** | **ReAct Loop (Single-Agent)** | **Stateful Cyclic Graph (Multi-Agent)** | Single-agent memiliki latensi inferensi lebih rendah (~1-2 detik) dan biaya token hemat, namun rentan *task-drift* dan *hallucination cascading*. Multi-agent graph menawarkan modularitas tinggi, isolasi kegagalan, dan akurasi tinggi, dengan konsekuensi latensi 4-10x lipat dan konsumsi token signifikan. |
| **Model Alignment** | **PPO (Online RLHF)** | **DPO (Offline Alignment)** | PPO mampu mengeksplorasi state space di luar dataset statis melalui live actor-critic loop, tetapi membutuhkan infrastruktur training masif (multi-node GPU) dan penalaan hyperparameter yang sangat sensitif. DPO memberikan stabilitas komputasi absolut, training 3x lebih cepat, namun rentan terhadap dataset bias yang ada dalam data preferensi offline. |
| **Persistensi State** | **In-Memory (Ephemeral)** | **Snapshotting Terdistribusi (Postgres/Redis)** | Ephemeral state memberikan *throughput* maksimal (ratusan ribu operasi per detik) tanpa network I/O overhead. Snapshotting terdistribusi menimbulkan latency penalty (5-15ms per edge transition), namun mutlak diwajibkan untuk enterprise fault-tolerance dan audit compliance. |
| **Eksekusi Tool** | **Parallel Tool Invocation** | **Strict Sequential with Reflection** | Tool parallel mempercepat latensi total (wall-clock time), namun berisiko memicu *race condition* jika tools memanipulasi shared external state (misalnya, update saldo DB). Sequential eksekusi aman dan memiliki konteks audit yang jelas, namun memperlambat siklus penyelesaian tugas. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Runaway Recursion & Token Exhaustion
- **Gejala**: Tagihan LLM membengkak drastis dalam beberapa jam; worker container kehabisan memory (*OOMKilled*).
- **Penyebab**: Node evaluasi agen gagal mencapai kondisi konvergen karena instruksi ambigu, menyebabkan graph melompat bolak-balik antara node analisis dan node aksi tanpa henti.
- **Troubleshooting**: Terapkan *Recursion Limit hard-cap* di level graph engine runtime, bukan di level prompt LLM. Tambahkan counter monotonik pada context state yang memicu pemutusan sirkuit secara deterministik jika `iteration_count > LIMIT`.

### 10.2 State Mutability Pollution
- **Gejala**: State terkontaminasi oleh data dari sesi user lain atau data historis iterasi sebelumnya tidak dapat di-rollback.
- **Penyebab**: Menggunakan struktur data mutable (seperti plain Python dictionary atau default argument list `messages=[]`) yang dibagi lintas thread atau event loop.
- **Troubleshooting**: Terapkan *immutability* menggunakan library validasi seperti Pydantic dengan `frozen=True` atau terapkan fungsi *reducer* murni (`pure functions`) yang selalu menghasilkan object baru saat mutasi state.

### 10.3 Catastrophic Forgetting Pasca-Alignment DPO
- **Gejala**: Model berhasil mengikuti gaya respons preferensi baru, tetapi kemampuan penalaran dasar, coding, atau tool-calling JSON parsing drop drastis.
- **Penyebab**: Nilai koefisien regularisasi $\beta$ terlalu kecil atau training dilakukan terlalu banyak epoch, menyebabkan bobot model bergeser terlalu jauh dari reference model $\pi_{\text{ref}}$.
- **Troubleshooting**: Naikkan nilai parameter $\beta$ (rentang aman produksi: $0.1 \le \beta \le 0.5$). Tambahkan data replay penalaran umum (SFT anchor dataset) ke dalam batch loss calculation.

---

## 11. Best Practices (Production Checklist)

### 12-Factor Agent Architecture Checklist
- [ ] **Contract-First State**: Skema state didefinisikan secara eksplisit menggunakan Pydantic v2 dengan type hints yang ketat.
- [ ] **Idempotent Tool Handlers**: Setiap tool memiliki `idempotency_key` untuk mencegah eksekusi ganda jika terjadi network retry.
- [ ] **Deterministic Circuit Breakers**: Adanya pembatas iterasi maksimum hard-coded dan token budget cap per request.
- [ ] **Separation of Concerns**: Supervisor node hanya bertugas merutekan instruksi, tidak mengeksekusi tools bisnis secara langsung.
- [ ] **Snapshot Checkpointing**: Snapshot tersimpan ke distributed storage pada setiap node boundary untuk memfasilitasi rollback.
- [ ] **Graceful Degradation Fallbacks**: Setiap titik kritis kegagalan memiliki jalur alternatif non-AI (hard-coded logic).
- [ ] **Sandboxed Environments**: Seluruh eksekusi kode dinamis (Python repl, bash commands) berjalan di container terisolasi tanpa akses network internal.
- [ ] **Time-to-Live (TTL) Context**: Dynamic sliding-window summarizer aktif untuk mencegah context-length overflow.
- [ ] **Distributed Tracing**: Setiap langkah node, token count, dan parameter tool diinstrumentasi dengan OpenTelemetry / OpenInference trace ID.
- [ ] **Explicit Schema Guardrails**: Output parsing tool memvalidasi tipe data sebelum data disuntikkan kembali ke input node berikutnya.

---

## 12. Hands-on Practice

Buatlah sistem Multi-Agent otonom lokal dengan persistensi berbasis file system dan circuit-breaker deterministik.

### Struktur Direktori:
```
hands-on/m02/
├── config.py
├── engine.py
├── state.py
└── main.py
```

### Langkah 1: `state.py` (Definisi State & Reducer)
```python
from __future__ import annotations
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field

def message_reducer(current: List[str], update: List[str]) -> List[str]:
    return current + update

class PipelineState(BaseModel):
    session_id: str
    target_metric: str
    current_value: float = 0.0
    logs: Annotated[List[str], message_reducer] = Field(default_factory=list)
    step_count: int = 0
    max_steps: int = 4
    status: str = "INITIALIZED"
```

### Langkah 2: `engine.py` (Orchestration Engine)
```python
import asyncio
from state import PipelineState, message_reducer

class ProductionAgentEngine:
    def __init__(self, state: PipelineState):
        self.state = state

    async def step_diagnose(self) -> None:
        self.state.step_count += 1
        self.state.logs = message_reducer(self.state.logs, [f"[Step {self.state.step_count}] Mendiagnosis metrik {self.state.target_metric}"])
        await asyncio.sleep(0.02)
        # Simulasi perubahan state
        self.state.current_value += 25.0
        if self.state.current_value >= 100.0:
            self.state.status = "SUCCESS"
        else:
            self.state.status = "OPTIMIZING"

    async def step_optimize(self) -> None:
        self.state.step_count += 1
        self.state.logs = message_reducer(self.state.logs, [f"[Step {self.state.step_count}] Mengaplikasikan tuning parameter"])
        await asyncio.sleep(0.02)
        self.state.current_value += 30.0
        if self.state.current_value >= 100.0:
            self.state.status = "SUCCESS"
        else:
            self.state.status = "DIAGNOSING"

    async def execute(self) -> PipelineState:
        while self.state.status not in ["SUCCESS", "FAILED"]:
            if self.state.step_count >= self.state.max_steps:
                self.state.status = "FAILED"
                self.state.logs = message_reducer(self.state.logs, ["[CIRCUIT BREAKER] Iterasi maksimum tercapai."])
                break

            if self.state.status in ["INITIALIZED", "DIAGNOSING"]:
                await self.step_diagnose()
            elif self.state.status == "OPTIMIZING":
                await self.step_optimize()
                
        return self.state
```

### Langkah 3: `main.py` (Runner Entrypoint)
```python
import asyncio
from state import PipelineState
from engine import ProductionAgentEngine

async def run_pipeline():
    initial_state = PipelineState(
        session_id="run-402",
        target_metric="Cache Hit Ratio",
        current_value=10.0,
        max_steps=5
    )
    
    engine = ProductionAgentEngine(initial_state)
    result = await engine.execute()
    
    print(f"Status Akhir : {result.status}")
    print(f"Nilai Metrik : {result.current_value}")
    print("Execution Traces:")
    for log in result.logs:
        print(f" - {log}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

---

## 13. Exercise

### Level Easy
Modifikasi file `state.py` dan `engine.py` pada Hands-on Practice untuk menambahkan field `error_budget: int = 2`. Setiap kali eksekusi diagnosa gagal secara probabilistik, kurangi budget tersebut. Jika `error_budget == 0`, alihkan status state menjadi `FAILED_BY_BUDGET`.
- **Kriteria Penerimaan**: Engine berhenti seketika saat error budget nol, tanpa melanjutkan loop berikutnya.

### Level Medium
Rancang skema DPO Dataset Generator menggunakan Python. Tulis fungsi yang menerima list of agent trajectory pairs (trajectory A vs trajectory B) beserta metrik latensi dan jumlah tool calls, lalu secara deterministik melabeli trajectory mana yang menjadi `chosen` dan mana yang menjadi `rejected` untuk input alignment DPO.
- **Kriteria Penerimaan**: Script menghasilkan output file `dpo_pairs.jsonl` valid dengan skema: `{"prompt": "...", "chosen": "...", "rejected": "..."}`.

### Level Hard
Implementasikan *Time-Travel Debugging* pada `DistributedCheckpointer` di kode *Practical Example*. Tambahkan metode `rollback_to(session_id: str, version: int) -> GraphState` yang mampu memulihkan state engine ke snapshot versi tertentu, membuang state yang lebih baru, dan melanjutkan eksekusi alternatif dari titik tersebut (*forking execution*).
- **Kriteria Penerimaan**: Unit test mendemonstrasikan bahwa state versi 2 dapat di-fork menjadi versi 2-b tanpa merusak riwayat versi awal.

---

## 14. Challenge

### Studi Kasus Kompleks: Multi-Tenant Sovereign Agent Network with Dynamic Latency Hedging
Rancang arsitektur sistem agen otonom tingkat enterprise untuk pemrosesan klaim asuransi kesehatan multi-rumah sakit dengan persyaratan:
1. **Multi-Tenancy Isolation**: Setiap rumah sakit memiliki database, isolated vector store, dan rate-limiting quota masing-masing. State agen tidak boleh bocor lintas tenant (*Strict Context Segregation*).
2. **Dynamic Latency Hedging**: Jika LLM provider utama (misal: Private Hosted Model) merespons lebih dari 2.500 ms (P99 breach), request harus di-hedging secara asinkron ke fallback local model berukuran lebih kecil (misal: quantized 8B LLM) yang di-deploy on-premise tanpa membatalkan checkpoint state awal.
3. **Regulatory Audit Trail**: Setiap perubahan state yang memicu pembayaran reimbursement asuransi harus ditandatangani secara kriptografis (*Cryptographic Nonce & Hash Chaining*) di append-only checkpointer database.

Tugas Anda: Buat dokumen arsitektur teknis lengkap yang mencakup ERD/State Schema, Diagram Alur Eksekusi (ASCII), Mekanisme Penanganan State Concurrency, dan Penjelasan Mitigasi Kegagalan Transaksional.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Mengapa pola loop linier sederhana `while True: agent.step()` tidak direkomendasikan untuk arsitektur agen tingkat produksi?
   - A. Karena Python tidak mendukung multiprocessing di dalam while loop.
   - B. Karena tidak adanya persistensi state, rawan terjebak infinite loop tanpa kontrol, dan rentan terhadap memory leak saat terjadi unhandled crash.
   - C. Karena LLM hanya bisa dipanggil menggunakan pola event-driven berbasis HTTP server.
   - D. Karena library Pydantic tidak kompatibel dengan while loop native.
   *Jawaban*: **B**. State management terdistribusi dan circuit-breaker deterministik mutlak dibutuhkan untuk menjamin reliabilitas.

2. Apa fungsi utama dari *Reducer* dalam pengelolaan state berbasis graph?
   - A. Menghapus pesan lama agar ukuran memory context window menjadi nol.
   - B. Mengompresi file gambar yang dikirimkan oleh user.
   - C. Menentukan aturan agregasi matematis/logis bagaimana state baru digabungkan dengan state yang sudah ada.
   - D. Menjalankan kompilasi kode Python ke bahasa C untuk meningkatkan performa.
   *Jawaban*: **C**. Reducer (seperti fungsi append atau merge dict) bertugas menggabungkan delta update ke snapshot utama secara deterministik.

3. Apa keuntungan matematis utama DPO (Direct Preference Optimization) dibandingkan arsitektur RLHF standar (PPO)?
   - A. DPO tidak memerlukan token embedding layer.
   - B. DPO mengeliminasi kebutuhan model reward terpisah dan estimasi value function dengan memformulasikan loss langsung dari policy model.
   - C. DPO menjamin 100% akurasi faktual tanpa adanya halusinasi.
   - D. DPO hanya dapat dijalankan pada CPU dengan memori kecil.
   *Jawaban*: **B**. DPO menurunkan formulasi closed-form loss yang mengoptimasi policy langsung dari data preferensi tanpa PPO training loop.

4. Apa peran komponen *Checkpointer* dalam arsitektur Stateful Multi-Agent?
   - A. Melakukan fine-tuning bobot LLM secara real-time.
   - B. Menghentikan jaringan internet jika terjadi cyber attack.
   - C. Menyimpan delta snapshot dari GraphState pada setiap transisi edge ke persistent storage untuk keperluan toleransi kesalahan dan debugging.
   - D. Menghitung tagihan token billing secara real-time.
   *Jawaban*: **C**. Checkpointer bertindak sebagai storage layer snapshot untuk recovery dan time-travel capability.

5. Dalam Actor Model untuk AI Agent, bagaimana cara agen-agen yang berbeda saling berinteraksi secara aman?
   - A. Dengan mengakses dan memutasi variabel memori global secara bersamaan.
   - B. Melalui pengiriman pesan asynchronous immutable yang divalidasi oleh skema kontrak data.
   - C. Dengan menulis langsung ke file `.py` yang sedang dieksekusi runtime.
   - D. Menggunakan database file locking di level sistem operasi secara synchronous blocking.
   *Jawaban*: **B**. Prinsip Actor Model mengisolasi state internal dan hanya berkomunikasi via validated message-passing.

### 5 Pertanyaan Intermediate
6. Bagaimana cara mencegah *Cascading Hallucination* ketika Worker Agent pertama mengembalikan output yang cacat ke Supervisor Agent?
   - A. Meningkatkan temperature LLM menjadi 1.0 agar lebih kreatif.
   - B. Menghapus seluruh riwayat chat context dan mengulang dari nol.
   - C. Memasang Evaluator/Guardrail Node dengan skema Pydantic ketat dan conditional edge yang me-route state ke Reflection Node jika validasi gagal.
   - D. Mengganti database vector store dengan relational database standar.
   *Jawaban*: **C**. Guardrail deterministik memotong siklus halusinasi sebelum disuntikkan ke downstream task.

7. Mengapa parameter regularisasi $\beta$ dalam loss function DPO sangat krusial?
   - A. Mengatur learning rate optimizer AdamW.
   - B. Mengontrol seberapa jauh deviasi distribusi probabilitas model baru $\pi_\theta$ diizinkan melenceng dari model referensi $\pi_{\text{ref}}$.
   - C. Menentukan ukuran context window maksimal dari LLM.
   - D. Mengatur kuantisasi bobot model dari FP16 ke INT4.
   *Jawaban*: **B**. Jika $\beta$ terlalu rendah, model mengalami policy collapse / catastrophic forgetting; jika terlalu tinggi, model gagal belajar preferensi baru.

8. Pada implementasi multi-agent asinkron, apa risiko utama jika Reducer pada state messages tidak didesain bersifat append-only atau idempoten?
   - A. GPU memory clock akan mengalami throttling.
   - B. State snapshot akan mengalami race condition di mana update dari satu node menimpa (*overwrite*) update dari node lain tanpa sengaja.
   - C. Output format otomatis berubah menjadi plain text dari JSON.
   - D. Token budget akan otomatis ter-reset ke nilai default.
   *Jawaban*: **B**. Mutasi concurrent tanpa append-only reducer menyebabkan kehilangan data transaksi akibat *last-write-wins race conditions*.

9. Dalam perancangan hybrid memory, data tipe manakah yang paling tepat disimpan di dalam Knowledge Graph dibandingkan Vector Database?
   - A. Transkrip panggilan call-center yang panjang dan tidak terstruktur.
   - B. Deskripsi profil user yang bersifat naratif puitis.
   - C. Aturan relasi kepemilikan aset yang kaku, struktur hak akses organisasi, dan silsilah hierarki perusahaan.
   - D. Log mentah syslog server yang belum diparsing.
   *Jawaban*: **C**. Knowledge Graph unggul mutlak dalam merepresentasikan relasi deterministik, hierarki, dan explicit facts tanpa risiko similarity threshold mismatch.

10. Apa indikator teknis utama yang menunjukkan bahwa sebuah agen otonom mengalami *Reward Hacking* saat di-align menggunakan RL?
    - A. Nilai loss pelatihan menjadi flat (konstan).
    - B. Reward score tinggi secara konsisten, namun respons aktual menghasilkan kalimat nonsensikal berulang yang mengeksploitasi kelemahan parser reward model.
    - C. Waktu pelatihan per epoch menjadi 10x lebih lambat.
    - D. Vector Database kehabisan index disk space.
    *Jawaban*: **B**. Reward hacking terjadi saat policy menemukan shortcut probabilitas untuk memaksimalkan angka fungsi reward tanpa menyelesaikan tugas yang diinginkan.

### 3 Skenario Kasus Produksi
11. **Skenario Kasus A**: Sistem agen deteksi fraud transaksi kartu kredit Anda mengalami lonjakan latensi P99 dari 200ms menjadi 4.500ms saat volume transaksi malam hari naik. Arsitektur saat ini menggunakan Single Agent ReAct loop dengan 4 sequential external tool calls (Identity DB, IP Geolocation, Past History Vector Store, Credit Scoring API).
    - *Solusi Arsitektur Terbaik*:
      - A. Ubah infrastruktur ke arsitektur Directed Acyclic Graph (DAG) di mana 3 tool lookup (Identity, IP, Vector Store) dieksekusi secara asinkron serentak (`asyncio.gather`), lalu satukan outputnya ke satu Evaluator Node deterministik sebelum memanggil Scoring API.
      - B. Naikkan timeout limit client menjadi 30 detik agar LLM leluasa berpikir.
      - C. Hapus pemeriksaan Identity DB dan IP Geolocation dari sistem.
      - D. Ganti runtime Python dengan microservice C++ tanpa mengubah arsitektur sekuensialnya.
    *Jawaban*: **A**. Paralelisasi read-only I/O bound tools melalui async graph memangkas wall-clock latency secara signifikan.

12. **Skenario Kasus B**: Engine agen autonomous trading crypto Anda tiba-tiba mengalami *freeze* di tengah eksekusi order multi-exchange. Pod Kubernetes ter-restart karena host node mengalami hardware failure. Ketika pod baru menyala, agen tidak mengetahui apakah order di Binance sudah terisi atau belum, lalu mengulang eksekusi yang menyebabkan double-spending order.
    - *Solusi Remediasi yang Tepat*:
      - A. Menghapus Kubernetes dan memindahkan sistem ke dedicated server bare-metal tunggal.
      - B. Menerapkan Persistent State Checkpointing ke Redis/PostgreSQL pada setiap state transition, melengkapi setiap tool order dengan Client-Generated Idempotency Keys, dan menjalankan proses startup recovery untuk merekonsiliasi state terakhir sebelum melanjutkannya.
      - C. Mengurangi parameter max_iterations menjadi 1.
      - D. Menambahkan prompt: "Jangan melakukan double order jika server mati".
    *Jawaban*: **B**. Kombinasi snapshot recovery dan idempotency keys adalah solusi absolut tingkat enterprise untuk mencegah double execution pasca-crash.

13. **Skenario Kasus C**: Anda melakukan alignment model 70B menggunakan DPO untuk agen customer support. Namun setelah pelatihan, model kerap menolak menjawab pertanyaan valid dan selalu merespons: "Maaf, saya tidak berhak menjawab hal ini" meskipun pertanyaannya bukan kategori terlarang (False Positive Guardrail).
    - *Akar Masalah dan Solusinya*:
      - A. GPU kekurangan VRAM; solusinya lakukan training ulang dengan 4-bit quantization.
      - B. Terjadi over-optimization akibat nilai $\beta$ DPO yang terlalu longgar dan dataset preferensi `rejected` yang over-represented oleh respons netral, sehingga model mempelajari bahwa respons penolakan statis selalu menghasilkan reward lebih aman. Solusinya: kurasi ulang dataset preferensi dengan variasi kontras yang tajam dan tingkatkan regularisasi KL/adjust parameter $\beta$.
      - C. LLM provider memblokir API key Anda; solusinya buat akun baru.
      - D. State graph engine salah membaca JSON schema; solusinya ganti nama field.
    *Jawaban*: **B**. Data distribution collapse pada dataset DPO menyebabkan mode-collapse di mana policy memilih *safety shortcut* untuk meminimalkan penalti loss.

---

## 16. Summary

- **Stateful Actor Pattern**: Fondasi utama agen otonom produksi bukan loop linier, melainkan sistem berbasis Graph Siklik yang memisahkan *State Management*, *Reasoning Engine*, dan *Tool Execution Bus*.
- **Persistensi & Auditabilitas**: Penggunaan checkpointer snapshot terdistribusi menjamin kemampuan *fault-recovery*, *resilience*, dan *time-travel debugging*, sehingga kegagalan komputasi tidak mengakibatkan *loss of state*.
- **Modern RL Alignment (DPO)**: Produksi bergerak menjauhi kompleksitas infrastruktur 4-model PPO menuju Direct Preference Optimization yang lebih stabil, hemat VRAM, dan dapat diturunkan secara analitis dari data preferensi offline.
- **Enterprise Guardrails**: Kemampuan LLM harus dibatasi oleh pembatas deterministik, semantic circuit breakers, timeout eksplisit, dan isolasi sandbox tool execution guna mencegah kegagalan katastropik, infinite loops, dan kerugian finansial.