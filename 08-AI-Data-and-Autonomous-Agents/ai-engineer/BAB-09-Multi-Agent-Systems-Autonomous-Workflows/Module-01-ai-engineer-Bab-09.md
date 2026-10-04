# Bab 09: Multi-Agent Systems & Autonomous Workflows
## Module 01: Core Architecture of Multi-Agent Systems & Orchestration Protocols

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Merancang dan Mengimplementasikan Arsitektur Multi-Agent:** Mengonstruksi arsitektur orkestrasi agen berbasis *Hierarchical Supervisor* dan *Peer-to-Peer Choreography* menggunakan pola state graph yang deterministik.
*   **Mengisolasi Domain Kognitif & Context Window:** Menghitung dan menerapkan strategi partisi memori (*memory partitioning*) dan *context budgeting* untuk mengeliminasi degradasi penalaran akibat *context stuffing*.
*   **Membangun Protokol Hand-off dan Negosiasi Deterministik:** Mengembangkan mekanisme serah-terima tugas (*hand-off*) antar agen berbasis tipe data terstruktur (*typed schemas*) dengan jaminan konvergensi state.
*   **Mencegah Infinite Execution Loop:** Mengintegrasikan algoritma deteksi siklus graf (*cycle detection*) dan mitigasi kegagalan kaskade (*cascading failure mitigation*) pada eksekusi otonom terdistribusi.
*   **Mengevaluasi Trade-off Orkestrasi:** Memilih antara pendekatan *Centralized Orchestration* vs. *Decentralized Choreography* berdasarkan metrik latensi, biaya inferensi token, konsistensi data, dan toleransi kegagalan.

---

### 2. Concept Overview

Sistem agen tunggal (*Single-Agent System*) menghadapi keterbatasan fundamental ketika dihadapkan pada tugas enterprise yang kompleks: degradasi performa penalaran (*reasoning degradation*) seiring membesarnya ukuran konteks (*context window*), tingginya tingkat halusinasi pada domain multi-disiplin, dan ketidakmampuan membatasi *blast radius* kegagalan eksekusi alat (*tool execution*).

**Multi-Agent Systems (MAS)** memecahkan limitasi ini dengan membagi beban kognitif ke dalam jejaring agen terspesialisasi yang saling berkolaborasi.

```
       [Monolithic Single Agent]                      [Multi-Agent System (Specialized)]
+---------------------------------------+      +-------------+   Hand-off   +-------------+
| System Prompt: Expert in All Domains  |      | Triage /    | -----------> | Domain      |
| Context: 95k tokens (diluted)         |      | Planner     |              | Specialist  |
| Tools: 45 tools registered            |      +------+------+              +------+------+
| Blast Radius: High (Total Failure)    |             |                            |
| Execution: Sequential & Non-isolated  |             +------------+---------------+
+---------------------------------------+                          |
                                                            Shared State Graph
```

Tiga model mental fundamental dalam MAS:

1.  **Pemisahan Perhatian Kognitif (Cognitive Separation of Concerns):** Setiap agen beroperasi dengan instruksi sistem minimalis, instrumen perkakas (*toolsets*) terisolasi, dan jendela konteks terlokalisasi. Agen perencana (*planner*) tidak memerlukan akses ke skema database; agen SQL executor tidak memerlukan pemahaman tentang sentimen pengguna akhir.
2.  **State Graph Deterministik vs. Emergent Collaboration:** 
    *   *Emergent Collaboration* (misal: AutoGen standard) membiarkan agen saling bertukar pesan natural language secara bebas. Pola ini rentan terhadap non-terminasi dan deviasi semantik (*semantic drift*).
    *   *Deterministic State Graph* merepresentasikan sistem multi-agen sebagai *Finite State Machine* (FSM) atau *Directed Acyclic Graph* (DAG). Transisi antar node agen dievaluasi melalui *routing conditions* yang divalidasi oleh skema tipe data ketat.
3.  **Pola Black-Board vs. Message-Passing:**
    *   *Message-Passing:* Agen berkomunikasi secara langsung satu sama lain melalui *point-to-point envelopes*.
    *   *Blackboard Architecture:* Semua agen membaca dari dan memutasi struktur state global tersentralisasi melalui fungsi pereduksi state (*state reducers*) yang murni dan atomik.

---

### 3. Why It Matters: Masalah di Dunia Nyata & Kebutuhan Enterprise

Dalam arsitektur *monolithic agent*, penambahan perkakas (*tools*) secara linear meningkatkan kemungkinan kesalahan pemilihan alat (*tool misrouting*) oleh LLM secara eksponensial. Ketika sebuah agen memiliki 30+ tools, akurasi pemanggilan parameter menurun hingga 40% pada LLM kelas menengah.

Kebutuhan enterprise yang memaksa adopsi Multi-Agent Systems mencakup:

*   **Cost & Latency Optimization melalui Tiering Model:** Penggunaan LLM berbiaya tinggi (e.g., Claude 3.5 Sonnet, GPT-4o) dapat dibatasi hanya untuk agen supervisor/perencana, sementara sub-tugas mekanistik (ekstraksi entitas, validasi sintaks, eksekusi SQL) dialihkan ke model yang lebih kecil, cepat, dan murah (e.g., Llama 3.1 8B, Claude 3.5 Haiku).
*   **Auditability & Boundary Governance:** Regulasi enterprise (GDPR, HIPAA, PCI-DSS) menuntut pembatasan akses data yang ketat. Dalam MAS, *Data Compliance Agent* dapat mengintersepsi artefak sebelum dikonsumsi oleh *Public-facing Agent*, bertindak sebagai *hard boundary guardrail*.
*   **Mitigasi Cascade Failures:** Jika sebuah agen analisis mengalami error timeout atau eksepsi tak terduga, sistem orkestrator dapat mengisolasi kegagalan tersebut, mengembalikan state ke titik *checkpoint* terakhir, dan merutekan tugas ke agen cadangan tanpa meruntuhkan seluruh sesi pengguna.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengilustrasikan **Hierarchical Multi-Agent Supervisor Pattern** dengan *State Graph Routing Engine*, *Shared Blackboard Memory*, dan *Isolated Tool Sandboxes*.

```
+---------------------------------------------------------------------------------------+
|                                    SHARED STATE GRAPH                                 |
|  - thread_id: UUID                                                                    |
|  - context_variables: dict                                                            |
|  - node_history: List[ExecutionStep]                                                  |
|  - convergence_status: Enum(IN_PROGRESS, COMPLETED, FAILED)                           |
+-------------------------------------------+-------------------------------------------+
                                            ^
                       Read/Write via       | Atomic Reducer
                       Typed Envelope       v
             +------------------------------------------------------+
             |             SUPERVISOR / ROUTER AGENT                |
             |  - Model: High-Reasoning Tier (e.g., Claude Sonnet)  |
             |  - Role: Task Decomposition, Routing, Consensus      |
             +-----------+------------------------------+-----------+
                         |                              |
            Task Handoff |                 Task Handoff |
                         v                              v
    +-----------------------------+    +-----------------------------+
    |      RESEARCHER AGENT       |    |       VERIFIER AGENT        |
    | - Model: Fast Tier (SLM)    |    | - Model: Deterministic LLM  |
    | - Scope: Data Gathering     |    | - Scope: Syntax & Logic Eval|
    +--------------+--------------+    +--------------+--------------+
                   |                                  |
                   v                                  v
    +-----------------------------+    +-----------------------------+
    |      TOOL SANDBOX A         |    |       TOOL SANDBOX B        |
    | - Vector DB Retrieval       |    | - Static Code Analyzer      |
    | - Web Search API            |    | - Unit Test Runner          |
    +-----------------------------+    +-----------------------------+
```

#### Alur Eksekusi Data:
1.  **Ingress:** Pengguna mengirimkan *intent* kompleks ke antarmuka sistem.
2.  **Initialization:** *State Graph Engine* menginisialisasi state global dengan token budget dan cycle counter ($C = 0$).
3.  **Triage & Plan:** *Supervisor Agent* memetakan masalah, mengevaluasi dependencies, dan menghasilkan rencana delegasi.
4.  **Handoff Execution:** Supervisor memancarkan instruksi terstruktur ke *Researcher Agent*. Jendela konteks dibersihkan; hanya payload instruksi yang dikirimkan.
5.  **Tool Operation:** *Researcher Agent* mengeksekusi tools dalam *sandbox* terisolasi dan mengembalikan hasil ke state global melalui pereduksi mutasi (*state reducer*).
6.  **Verification Gate:** State dirutekan ke *Verifier Agent* untuk validasi kualitas hasil kerja. Jika tidak valid, state dikembalikan ke *Researcher* dengan umpan balik kegagalan.
7.  **Consensus & Termination:** Setelah kondisi konvergensi tercapai, Supervisor mengompilasi respons final dan menghentikan eksekusi graf.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme State Hand-off & Context Budgeting
Dalam sistem terdistribusi, komunikasi antar-agen tidak boleh mengandalkan penerusan seluruh riwayat obrolan (*raw chat history*). Meneruskan seluruh riwayat obrolan menyebabkan pembengkakan konteks secara eksponensial:

$$\text{Token Count}(t) = \sum_{i=1}^{t} \left(\text{prompt}_i + \text{response}_i + \sum \text{tool\_outputs}_i\right)$$

Untuk mencegah ledakan konteks, sistem wajib menggunakan **Isolated Envelope Hand-off**. Supervisor bertindak sebagai pemangkas konteks (*context pruner*). Konteks yang dikirimkan ke sub-agen hanyalah:
1.  Target operasional spesifik (*atomic task directive*).
2.  Data dependensi minimal yang divalidasi (*lean payload*).
3.  Batasan output terstruktur (*Pydantic output schema*).

#### B. Dynamic Convergence vs. Divergence Control
Sistem agen otonom dapat terjebak dalam kondisi *livelock* (agen A meminta revisi dari agen B, yang menghasilkan output yang kembali ditolak oleh agen A). 
Untuk menjamin konvergensi deterministik, arsitektur harus menerapkan tiga invariant matematis:
*   **Max Iteration Limit ($I_{max}$):** Pembatas mutlak eksekusi loop. Jika iterasi $i \ge I_{max}$, sistem dipaksa memasuki *Graceful Degradation Fallback*.
*   **State Hash Cycle Detection:** State engine mencatat nilai hash kriptografis dari payload setiap node. Jika $H(S_t) == H(S_{t-k})$, sistem mendeteksi infinite loop dan menghentikan rantai eksekusi (*circuit breaker*).
*   **Monotonic State Progression:** Setiap langkah agen harus mengurangi metrik entropi tugas atau meningkatkan metrik kelengkapan tugas secara terukur.

---

### 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python murni dengan model konkurensi `asyncio` dan validasi skema ketat menggunakan `Pydantic v2`. Arsitektur ini merealisasikan *Typed State Graph Multi-Agent System* yang dilengkapi proteksi siklus dan penanganan kesalahan runtime.

```python
"""
Core Multi-Agent Orchestration Framework.
Production-grade implementation with isolated context, typed state transitions, 
and cycle detection.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError

# ============================================================================
# CONFIGURATION & TELEMETRY
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("MultiAgentOrchestrator")


# ============================================================================
# DOMAIN MODELS & SCHEMAS
# ============================================================================

class NodeRole(str, Enum):
    SUPERVISOR = "supervisor"
    RESEARCHER = "researcher"
    VERIFIER = "verifier"
    TERMINAL = "__terminal__"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    REVISION_REQUIRED = "revision_required"
    FAILED = "failed"


class AgentHandoffPayload(BaseModel):
    """Immutable data envelope passed between agents."""
    task_id: UUID = Field(default_factory=uuid4)
    target_node: NodeRole
    instruction: str = Field(..., min_length=5)
    context_data: Dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = Field(default=0, ge=0)


class VerificationResult(BaseModel):
    """Validation output produced by the Verifier Agent."""
    is_valid: bool
    critique: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class SystemState(BaseModel):
    """Deterministic shared state (Blackboard Pattern)."""
    session_id: UUID = Field(default_factory=uuid4)
    original_input: str
    current_node: NodeRole = NodeRole.SUPERVISOR
    intermediate_artifacts: Dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = 0
    max_iterations: int = 5
    execution_trace: List[str] = Field(default_factory=list)
    state_hashes: List[str] = Field(default_factory=list)
    final_output: Optional[str] = None

    def compute_hash(self) -> str:
        """Computes deterministic hash of state to detect livelocks."""
        state_repr = {
            "current_node": self.current_node.value,
            "artifacts": self.intermediate_artifacts,
            "iterations": self.iteration_count
        }
        encoded = json.dumps(state_repr, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# ============================================================================
# AGENT INTERFACES & IMPLEMENTATIONS
# ============================================================================

class BaseAgent(ABC):
    def __init__(self, role: NodeRole) -> None:
        self.role = role

    @abstractmethod
    async def execute(self, state: SystemState) -> AgentHandoffPayload:
        """Executes domain logic and determines the next state handoff."""
        pass


class SupervisorAgent(BaseAgent):
    """
    Decides routing based on global state evaluation.
    Tier: High-Reasoning Model Mock.
    """
    def __init__(self) -> None:
        super().__init__(role=NodeRole.SUPERVISOR)

    async def execute(self, state: SystemState) -> AgentHandoffPayload:
        logger.info(f"[{self.role.value.upper()}] Evaluating system trajectory...")
        
        # State routing logic
        if "research_data" not in state.intermediate_artifacts:
            logger.info(f"[{self.role.value.upper()}] Routing task to RESEARCHER.")
            return AgentHandoffPayload(
                target_node=NodeRole.RESEARCHER,
                instruction="Extract operational metrics and failure signals.",
                context_data={"raw_query": state.original_input},
                iteration_count=state.iteration_count
            )

        if "verification" not in state.intermediate_artifacts:
            logger.info(f"[{self.role.value.upper()}] Routing output to VERIFIER.")
            return AgentHandoffPayload(
                target_node=NodeRole.VERIFIER,
                instruction="Audit the extracted data for factual consistency.",
                context_data={"target_data": state.intermediate_artifacts["research_data"]},
                iteration_count=state.iteration_count
            )

        verification: VerificationResult = state.intermediate_artifacts["verification"]
        if verification.is_valid:
            logger.info(f"[{self.role.value.upper()}] Quality criteria met. Terminating.")
            state.final_output = f"Processed successfully: {state.intermediate_artifacts['research_data']}"
            return AgentHandoffPayload(
                target_node=NodeRole.TERMINAL,
                instruction="Finalize workflow output.",
                iteration_count=state.iteration_count
            )
        else:
            logger.warning(f"[{self.role.value.upper()}] Verification failed. Requesting revision.")
            # Prune invalid artifacts to prevent state pollution
            del state.intermediate_artifacts["research_data"]
            del state.intermediate_artifacts["verification"]
            
            return AgentHandoffPayload(
                target_node=NodeRole.RESEARCHER,
                instruction=f"Re-gather metrics addressing failure: {verification.critique}",
                context_data={"raw_query": state.original_input},
                iteration_count=state.iteration_count
            )


class ResearcherAgent(BaseAgent):
    """
    Executes deep gathering tools and emits domain data.
    Tier: Fast Execution Model / Tool Runner Mock.
    """
    def __init__(self) -> None:
        super().__init__(role=NodeRole.RESEARCHER)

    async def execute(self, state: SystemState) -> AgentHandoffPayload:
        logger.info(f"[{self.role.value.upper()}] Executing isolated data gathering...")
        await asyncio.sleep(0.1)  # Simulate I/O bound tool interaction
        
        # Simulating dynamic state mutation based on iterations
        is_first_attempt = state.iteration_count == 0
        extracted_metric = "CPU_LOAD: 98% | LATENCY: 2400ms" if not is_first_attempt else "INVALID_CORRUPTED_METRICS"

        state.intermediate_artifacts["research_data"] = extracted_metric
        state.execution_trace.append(f"Researcher gathered: {extracted_metric}")

        return AgentHandoffPayload(
            target_node=NodeRole.SUPERVISOR,
            instruction="Review gathered data.",
            context_data={"status": TaskStatus.SUCCESS},
            iteration_count=state.iteration_count
        )


class VerifierAgent(BaseAgent):
    """
    Validates intermediate artifacts against strict invariants.
    Tier: Guardrail / Strict Evaluation Mock.
    """
    def __init__(self) -> None:
        super().__init__(role=NodeRole.VERIFIER)

    async def execute(self, state: SystemState) -> AgentHandoffPayload:
        logger.info(f"[{self.role.value.upper()}] Evaluating artifact integrity...")
        await asyncio.sleep(0.05)  # Simulate validation compute

        target_data = state.intermediate_artifacts.get("research_data", "")
        
        # Invariant checks: Data must not be corrupted
        if "INVALID" in target_data:
            result = VerificationResult(
                is_valid=False,
                critique="Artifact contains corrupted markers.",
                confidence_score=0.99
            )
        else:
            result = VerificationResult(
                is_valid=True,
                critique=None,
                confidence_score=0.95
            )

        state.intermediate_artifacts["verification"] = result
        state.execution_trace.append(f"Verifier status: valid={result.is_valid}")

        return AgentHandoffPayload(
            target_node=NodeRole.SUPERVISOR,
            instruction="Ingest evaluation result.",
            iteration_count=state.iteration_count
        )


# ============================================================================
# ORCHESTRATION ENGINE & EXECUTION GRAPH
# ============================================================================

class CycleDetectedException(RuntimeError):
    """Raised when an infinite state loop is detected via hashing."""
    pass


class TokenBudgetExceededException(RuntimeError):
    """Raised when the execution depth exceeds hard enterprise limits."""
    pass


class MultiAgentGraphEngine:
    """
    Deterministic Graph Engine managing transitions, invariants, and guardrails.
    """
    def __init__(self) -> None:
        self.registry: Dict[NodeRole, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.registry[agent.role] = agent

    async def run(self, initial_query: str, max_iterations: int = 6) -> SystemState:
        state = SystemState(
            original_input=initial_query,
            max_iterations=max_iterations
        )
        
        logger.info(f"[GRAPH_INIT] Session {state.session_id} initialized.")

        while state.current_node != NodeRole.TERMINAL:
            # 1. Invariant: Max Iteration Guardrail
            if state.iteration_count >= state.max_iterations:
                error_msg = f"Max iteration budget ({state.max_iterations}) exceeded."
                logger.error(f"[CIRCUIT_BREAKER] {error_msg}")
                raise TokenBudgetExceededException(error_msg)

            # 2. Invariant: Cycle Detection via State Cryptographic Hashing
            current_hash = state.compute_hash()
            if current_hash in state.state_hashes:
                error_msg = f"Livelock detected: State hash {current_hash} recurred."
                logger.error(f"[CYCLE_BREAKER] {error_msg}")
                raise CycleDetectedException(error_msg)
            
            state.state_hashes.append(current_hash)
            state.iteration_count += 1

            # 3. Route Execution to Target Node
            agent = self.registry.get(state.current_node)
            if not agent:
                raise ValueError(f"Agent with role {state.current_node} is not registered.")

            logger.info(f"\n--- STEP {state.iteration_count}: Node -> {state.current_node.value.upper()} ---")
            handoff: AgentHandoffPayload = await agent.execute(state)

            # 4. State Reduction & Deterministic Transition
            state.current_node = handoff.target_node
            state.execution_trace.append(f"Transitioned to {handoff.target_node.value}")

        logger.info(f"[GRAPH_TERMINATED] Reached terminal node cleanly.")
        return state


# ============================================================================
# ENTRYPOINT DRIVER
# ============================================================================

async def main() -> None:
    # Initialize Engine
    engine = MultiAgentGraphEngine()
    
    # Register Node Actors
    engine.register_agent(SupervisorAgent())
    engine.register_agent(ResearcherAgent())
    engine.register_agent(VerifierAgent())

    # Execute Autonomous Workflow
    telemetry_query = "FETCH_SYSTEM_TELEMETRY: CLUSTER_ALPHA"
    
    try:
        final_state = await engine.run(initial_query=telemetry_query, max_iterations=6)
        print("\n" + "="*50)
        print("WORKFLOW EXECUTION SUMMARY")
        print("="*50)
        print(f"Final Status: SUCCESS")
        print(f"Final Output: {final_state.final_output}")
        print(f"Total Iterations: {final_state.iteration_count}")
        print("Execution Trace:")
        for step in final_state.execution_trace:
            print(f"  -> {step}")
        print("="*50)
    except (CycleDetectedException, TokenBudgetExceededException) as e:
        print(f"\nCRITICAL ENGINE ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Akar Masalah (*Root Cause*) | Dampak Arsitektur | Strategi Mitigasi Teruji (*Enterprise Mitigation*) |
| :--- | :--- | :--- | :--- |
| **Bilateral Deadlock (Ping-Pong Loop)** | Agen A menolak output Agen B; Agen B memvalidasi ulang tanpa perubahan konteks semantik. | *Infinite reasoning loop*, token budget habis seketika, latensi tinggi tak terkendali. | **State Hash History Checkpoint:** Catat SHA-256 state payload. Terapkan $I_{max}$ ketat per node transition dan turunkan parameter *temperature* ke `0.0` pada fase revisi. |
| **Cascading Context Contamination** | Sub-agen memunculkan halusinasi fakta yang tidak disaring, lalu dimasukkan ke dalam shared state. | *Polluted Ground Truth*. Agen downstream membuat kesimpulan berdasarkan data korup. | **Structured Invariant Gate:** Terapkan skema Pydantic ketat antar-node. Hapus artefak invalid dari memori global sebelum handoff (*memory pruning*). |
| **Semantic Drift in Handoff** | Sub-agen salah menginterpretasikan instruksi longgar dari perencana (*supervisor*). | Sub-agen menyelesaikan tugas yang sama sekali tidak relevan dengan query pengguna. | **Context Envelope Restriction:** Gunakan *Structured Directed Prompts* dengan field `task_objective`, `expected_schema`, dan `negative_constraints`. |
| **Tool Execution Throttling (429 Rate Limit)** | Eksekusi konkuren paralel oleh beberapa worker membebani downstream API/database. | Eksepsi tak tertangani yang merusak siklus transisi graf. | **Exponential Backoff Decorator with Jitter** dan pengelompokan eksekusi menggunakan `asyncio.Semaphore`. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap arsitektur koordinasi multi-agen memiliki trade-off fundamental antara otonomi, determinisme, kompleksitas, dan konsumsi sumber daya:

```
[Choreography / Emergent]                             [Hierarchical Orchestration]
High Latency Variance                                 Deterministic Control
Unpredictable Convergence                             Predictable State Path
Low Framework Complexity                              High Engineering Complexity
O(N^2) Communication Links                            O(N) Communication Links
         |                                                       |
         +---------------------------+---------------------------+
                                     |
                          [Hybrid Graph Architecture]
                           - Supervisor handles routing
                           - Peer-to-peer for micro-loops
                           - Strict typed state contracts
```

#### Komparasi Arsitektur Multi-Agent

| Parameter Evaluasi | Peer-to-Peer Choreography (e.g., AutoGen standard) | Hierarchical Supervisor (Pola Modul Ini) | Monolithic ReAct Single-Agent |
| :--- | :--- | :--- | :--- |
| **Determinisme Alur** | Sangat Rendah (Emergent behavior) | Tinggi (Dibatasi oleh State Graph) | Menengah (Dibatasi ReAct loop) |
| **Konsumsi Token** | Sangat Boros (Semua chat history disalin) | Efisien (Konteks dipangkas per hand-off) | Efisien di awal, meledak seiring waktu |
| **Kemudahan Debugging** | Sulit (Non-linear message passing) | Mudah (State transitions terisolasi & ter-hash) | Menengah (Linear log tracing) |
| **Blast Radius Kegagalan** | Luas (Dapat merusak seluruh percakapan) | Terlokalisasi (Node gagal dapat di-retry) | Total (Satu tool crash merusak eksekusi) |
| **Kompleksitas Kode** | Rendah (Konfigurasi agen obrolan saja) | Tinggi (Memerlukan state engine eksplisit) | Rendah (Hanya satu loop utama) |

---

### 9. Best Practices & Standard Industri

1.  **State Reducer Immutability:** Jangan pernah memutasi state secara *in-place* tanpa tracking. Gunakan fungsi pereduksi state (*reducer*) fungsional murni. Kembalikan state baru untuk memungkinkan kapabilitas *time-travel debugging* dan *state rollback*.
2.  **Telemetry & Tracing Standar OpenTelemetry:** Setiap transisi agen wajib menginjeksikan trace headers (`traceparent`, `tracestate`). Pantau metrik granular:
    *   *Tokens per task delegation*
    *   *Agent step duration latency*
    *   *Handoff rejection rate* (rasio kegagalan verifikasi terhadap total tugas)
3.  **Strict Token Budget Allocation:** Tetapkan batas biaya moneter dan jumlah token maksimum per node eksekusi. Konfigurasikan fallback otomatis jika anggaran terlampaui:
    ```python
    if state.accumulated_cost_usd > HARD_BUDGET_LIMIT:
        return AgentHandoffPayload(target_node=NodeRole.TERMINAL, instruction="EMERGENCY_BUDGET_HALT")
    ```
4.  **Static Schema Contracts:** Jangan biarkan agen berkomunikasi menggunakan untyped strings. Gunakan objek transmisi data bertipe ketat (*Strictly Typed DTOs*) untuk memastikan parsing selalu tervalidasi pada level runtime sebelum menyentuh logika agen.

---

### 10. Hands-on Lab Exercise: Autonomous Incident Response Swarm

#### Skenario Lab:
Anda bertugas membangun sistem investigasi insiden otomatis (*Automated Site Reliability Swarm*) yang terdiri dari:
1.  **Triage Agent:** Membaca log error mentah, mengekstraksi service target, dan menentukan tingkat keparahan (*severity*).
2.  **Log Forensics Agent:** Mensimulasikan pengambilan trace error dari layanan yang terdampak.
3.  **Remediation Agent:** Menghasilkan patch konfigurasi atau langkah mitigasi operasional.
4.  **Security Reviewer (Gatekeeper):** Memvalidasi rencana remediasi. Jika rencana mengandung tindakan destruktif tanpa proteksi (e.g., `rm -rf`, `DROP TABLE`), remediasi ditolak dan dikembalikan untuk revisi.

#### Instruksi Langkah demi Langkah:

1.  **Persiapan Lingkungan:**
    ```bash
    mkdir multi_agent_lab && cd multi_agent_lab
    python3 -m venv venv
    source venv/bin/activate
    pip install pydantic==2.6.4
    ```

2.  **Definisi State & Kontrak DTO:**
    Buat file `lab_swarm.py`. Definisikan skema state yang mencakup:
    *   `incident_description: str`
    *   `affected_service: Optional[str]`
    *   `severity: Optional[str]`
    *   `remediation_plan: Optional[str]`
    *   `security_approval: bool`

3.  **Implementasikan Logika Agen:**
    *   *Triage Agent:* Parsing string input `"CRITICAL: Database connection exhaustion in PaymentService"`. Ekstrak service dan severity.
    *   *Remediation Agent:* Jika severity `CRITICAL`, sarankan solusi awal: `"Restart service and flush connection pool with aggressive DROP TABLE temp_connections;"`.
    *   *Security Reviewer:* Deteksi string berbahaya (`DROP TABLE`). Jika ditemukan, set `security_approval = False`, berikan critique, dan kembalikan ke Remediation Agent. Remediation agent pada percobaan kedua harus menghasilkan konfigurasi aman: `"Apply connection pooling max_conn=200 via Helm patch"`.

4.  **Jalankan dan Verifikasi Evaluasi Konvergensi:**
    Pastikan engine graf berhasil mendeteksi penolakan pada iterasi pertama, melakukan perbaikan pada iterasi kedua, dan menyelesaikan eksekusi dengan status konvergen tanpa intervensi manusia.

#### Kriteria Keberhasilan:
*   [ ] Trace log menunjukkan transisi: `Triage -> Remediation -> Security -> Remediation (Revisi) -> Security -> Terminal`.
*   [ ] Terbukti bahwa instruksi berbahaya berhasil di-intersepsi dan dibersihkan dari *production release artifact*.
*   [ ] Engine berhenti secara deterministik pada iterasi valid dengan state `security_approval=True`.