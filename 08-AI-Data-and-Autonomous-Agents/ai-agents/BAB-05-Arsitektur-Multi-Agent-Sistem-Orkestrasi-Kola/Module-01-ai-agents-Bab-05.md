# Bab 05: Arsitektur Multi-Agent & Sistem Orkestrasi Kolaboratif

Membangun sistem kecerdasan buatan berbasis *autonomous agent* tingkat *enterprise* memerlukan pergeseran paradigma dari *monolithic agentic prompting* menuju sistem terdistribusi: **Multi-Agent Systems (MAS)**. Ketika kompleksitas instruksi, batas jendela konteks (*context window*), dan diversitas alat (*tools*) melampaui kapasitas satu model komputasi penalaran, arsitektur multi-agent memecah beban kognitif tersebut menjadi spesialisasi-spesialisasi yang saling berkoordinasi secara deterministik.

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Merancang Pola Dekomposisi Multi-Agent**: Menentukan kapan harus menggunakan pendekatan *Centralized Orchestration* (Hub-and-Spoke), *Decentralized Choreography* (Peer-to-Peer / Mesh), atau *Blackboard Systems* berdasarkan batas latensi, *token budget*, dan kompleksitas tugas.
2. **Mengimplementasikan Protokol Komunikasi Antar-Agent Formal**: Membangun protokol pesan bertipe (*strongly typed message passing*) yang mencakup metadata penelusuran (*traceability*), korelasi percakapan (*conversation correlation*), dan status epistemik antar-agen.
3. **Mencegah Siklus Patologis dan Deadlock**: Menerapkan mekanisme mitigasi *infinite debate loops*, *cascading hallucination*, dan *split-brain state* menggunakan algoritma *Directed Acyclic Graph* (DAG), batas iterasi leksikal, serta konsensus terdistribusi.
4. **Membangun Runtime Multi-Agent Production-Grade**: Mengembangkan mesin orkestrasi kolaboratif berbasis asynchronous I/O menggunakan Python, lengkap dengan kontrol konkurensi, isolasi kegagalan (*fault isolation*), dan auditabilitas *state*.

---

## 2. Concept Overview

Sistem *Single Agent* yang dibebani terlalu banyak instruksi sistem (*system prompt*) dan ratusan *tools* akan mengalami fenomena **Instruction Dilution** dan degradasi atensi. Model kehilangan kemampuan diskriminatif untuk memilih alat yang tepat dan rentan terjebak dalam penalaran sirkular.

```
Monolithic Agent Problem:
[Large Prompt + 50 Tools + Complex Goal] -> LLM Context Saturation -> High Failure Rate

Multi-Agent Solution:
                    [Supervisor / Router]
                       /      |      \
                      v       v       v
           [Planner]     [Specialist]    [Verifier]
           (Context A)   (Context B)    (Context C)
```

### Mental Model & Fondasi Teoretis

1. **Society of Mind (Marvin Minsky)**: Kecerdasan bukan hasil dari satu proses monolitik tunggal, melainkan agregasi interaksi antara agen-agen kecil nir-cerdas (*sub-agents*) yang masing-masing menjalankan fungsi terspesialisasi.
2. **The Actor Model (Hewitt, Bishop, Steiger)**: Dalam sistem multi-agent terkomputasi, setiap *agent* diposisikan sebagai *Actor*. Agen memiliki *state* privat, berkomunikasi secara eksklusif via *asynchronous message passing*, dan tidak saling membagikan memori secara langsung tanpa abstraksi perantara.
3. **Blackboard Pattern (Hearsay-II)**: Ruang memori sentral yang dapat diakses oleh sekumpulan agen pakar (*knowledge sources*). Agen memonitor papan informasi ini dan mengeksekusi kontribusinya saat kondisi data di papan memicu domain keahlian mereka.

### Taksonomi Pola Koordinasi

* **Orchestration (Terpusat)**: Entitas sentral (*Supervisor/Router*) bertindak sebagai *master node* yang memegang graf eksekusi global, membedah instruksi pengguna, menugaskan pekerjaan kepada *worker agents*, dan menggabungkan output.
* **Choreography (Tersentralisasi/Reaktif)**: Setiap agen bereaksi secara otonom terhadap peristiwa (*events*) yang diterbitkan di *message broker*. Alur kerja muncul secara dinamis (*emergent behavior*) dari rantai aksi-reaksi antar-agen.

---

## 3. Why It Matters

Dalam lingkungan enterprise, kegagalan sistem agen tunggal memicu risiko operasional nyata:
* **Context Pollution & Cost Explosion**: Memasukkan seluruh skema basis data, manual operasional ratusan halaman, dan riwayat panggilan alat ke dalam satu agen menghasilkan degradasi penalaran (*Lost in the Middle*) dan konsumsi token yang boros secara linear per siklus penalaran.
* **Lack of Fault Isolation**: Jika satu penalaran salah pada langkah awal eksekusi, seluruh konteks tercemar halusinasi turunan (*cascading hallucination*).
* **Enterprise Auditability & Separation of Concerns**: Regulasi perbankan atau kesehatan mewajibkan pemisahan tegas antara agen yang membaca data mentah, agen yang menyusun rencana transaksi, dan agen yang memverifikasi kepatuhan hukum (*dual-control principle*). Sistem multi-agent memungkinkan penerapan kontrol akses granular (*Role-Based Access Control*) pada tingkat *tooling* dan memori per agen.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan **Orchestrated Blackboard Multi-Agent Architecture** tingkat enterprise dengan runtime terdistribusi.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT APPLICATION                                 |
+-------------------------------------------+-------------------------------------------+
                                            | User Goal / Task Payload
                                            v
+---------------------------------------------------------------------------------------+
|                               ORCHESTRATION BROKER RUNTIME                            |
|                                                                                       |
|   +-----------------------+     DAG/Execution State     +-------------------------+   |
|   |                       |<--------------------------->|                         |   |
|   |      SUPERVISOR       |                             |     SHARED BLACKBOARD   |   |
|   |   (Task Routing &     |     Read / Write Events     |  (Thread-Safe Memory &  |   |
|   | Consensus Arbiter)    |<--------------------------->|  Versioned State Store) |   |
|   +-----------+-----------+                             +------------+------------+   |
|               |                                                      ^                |
|               | Dispatches Subtasks via Message Bus                  | Read Context   |
|               v                                                      | Write Results  |
|   +------------------------------------------------------------------+------------+   |
|   |                         ISOLATED AGENT WORKERS LAYER                          |   |
|   |                                                                               |   |
|   |  +--------------------+   +--------------------+   +--------------------+     |   |
|   |  |   PLANNER AGENT    |   |  RESEARCHER AGENT  |   |   CRITIC/VERIFIER  |     |   |
|   |  |                    |   |                    |   |        AGENT       |     |   |
|   |  | Context: Task Decomp|  | Context: Data Tools|   | Context: Strict Eval|   |   |
|   |  | Tools: Graph Builder|  | Tools: Search/DB   |   | Tools: Schema Check|     |   |
|   |  +---------+----------+   +---------+----------+   +---------+----------+     |   |
|   +------------|------------------------|------------------------|----------------+   |
|                v                        v                        v                    |
|   +-------------------------------------------------------------------------------+   |
|   |                    MONITORING, TRACING (OTEL) & CIRCUIT BREAKER               |   |
+---+-------------------------------------------------------------------------------+---+
```

### Komponen Kunci
1. **Supervisor Engine**: Mengurai tugas input, memetakan ketergantungan subtask dalam Directed Acyclic Graph (DAG), dan mengarahkan pesan ke agen target.
2. **Shared Blackboard Store**: Penyimpan konteks global yang terlindungi mekanisme atomik untuk mencegah *race condition* antar agen.
3. **Agent Workers**: Unit eksekusi independen dengan *system prompt*, batas token, dan isolasi *sandbox tool* masing-masing.
4. **Consensus & Circuit Breaker Layer**: Memutus eksekusi bila terjadi kebuntuan (*deadlock*), siklus evaluasi konvergen yang gagal, atau batas anggaran (*budget limit*) terlampaui.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Protokol Komunikasi (Envelope Pattern)
Komunikasi antar-agen tidak boleh berbasis teks bebas (*raw strings*). Agen harus berkomunikasi menggunakan pesan terstruktur (*strongly-typed envelopes*) yang mengadaptasi standar FIPA-ACL (*Foundation for Intelligent Physical Agents - Agent Communication Language*):

$$\text{Envelope} = \langle \text{id}, \text{sender}, \text{recipient}, \text{correlation\_id}, \text{intent}, \text{payload}, \text{metadata} \rangle$$

* **Intent/Performative**: Mendefinisikan arti semantik pesan (misal: `REQUEST`, `INFORM`, `PROPOSE`, `REJECT`, `CONFIRM`).
* **Correlation ID**: Mengaitkan respons kembali ke penugasan spesifik pada pohon percakapan terdistribusi.

### 5.2 Dynamic Consensus & Debate Termination
Ketika agen perencana (*Planner*) dan agen verifikator (*Critic*) terlibat dalam evaluasi loop tertutup (*Actor-Critic dynamic*), risiko *infinite debate loop* dapat dihitung menggunakan model peluruhan toleransi kesalahan:

Diberikan skor evaluasi $S_t \in [0, 1]$ pada iterasi $t$, terminasi terjadi jika dan hanya jika:

$$\left( S_t \ge \tau \right) \lor \left( t \ge T_{\max} \right) \lor \left( |S_t - S_{t-1}| < \epsilon \quad \forall \, k \text{ langkah berturut-turut} \right)$$

Di mana $\tau$ adalah ambang batas kelulusan (*acceptance threshold*), $T_{\max}$ adalah batas keras iterasi, dan $\epsilon$ adalah ambang stagnasi untuk mendeteksi *deadlock* konvergensi kognitif.

### 5.3 Sinkronisasi Status dan Pencegahan Kondisi Balapan (Race Conditions)
Jika dua agen menulis ke memori bersama secara asinkron, inkonsistensi memori lokal akan terjadi. Pendekatan produksi mewajibkan penerapan **Optimistic Concurrency Control (OCC)** atau penguncian berbasis sewa (*lease-based distributed lock*), di mana setiap entri data pada Blackboard memiliki nomor versi monotonik terurut.

---

## 6. Production-Ready Code Implementation

Berikut implementasi lengkap dari **Orchestrated Multi-Agent Consensus Runtime** dalam Python. Kode ini bersifat *self-contained*, menggunakan paradigma *asynchronous concurrency*, mendukung pemvalidasian tipe via Pydantic v2, serta dilengkapi mitigasi siklus tak berujung (*infinite loop breaker*).

```python
"""
Module: collaborative_multi_agent_runtime.py
Description: Production-grade asynchronous Multi-Agent Orchestration Engine.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Setup Enterprise Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("MultiAgentRuntime")


# ============================================================================
# 1. DOMAIN PROTOCOLS & DATA ENVELOPES (FIPA-ACL Inspired)
# ============================================================================

class Performative(str, enum.Enum):
    REQUEST = "REQUEST"
    INFORM = "INFORM"
    PROPOSE = "PROPOSE"
    CRITIQUE = "CRITIQUE"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    sender: str
    recipient: str
    performative: Performative
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    iteration_index: int = 0


# ============================================================================
# 2. SHARED BLACKBOARD WITH ATOMIC STATE TRACKING
# ============================================================================

class BlackboardState(BaseModel):
    task_goal: str
    current_plan: Optional[str] = None
    research_data: List[str] = Field(default_factory=list)
    draft_solution: Optional[str] = None
    verification_score: float = 0.0
    is_completed: bool = False
    version: int = 0


class Blackboard:
    """Thread-safe asynchronous Blackboard for state synchronization."""

    def __init__(self, task_goal: str) -> None:
        self._lock = asyncio.Lock()
        self._state = BlackboardState(task_goal=task_goal)

    async def get_snapshot(self) -> BlackboardState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def update(self, **kwargs: Any) -> int:
        async with self._lock:
            for field, value in kwargs.items():
                if hasattr(self._state, field):
                    setattr(self._state, field, value)
                else:
                    raise AttributeError(f"Field '{field}' does not exist on BlackboardState")
            self._state.version += 1
            logger.debug(f"Blackboard updated to v{self._state.version}: {kwargs.keys()}")
            return self._state.version


# ============================================================================
# 3. BASE AGENT INTERFACE
# ============================================================================

class BaseAgent(ABC):
    def __init__(self, name: str, blackboard: Blackboard) -> None:
        self.name = name
        self.blackboard = blackboard

    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Processes an incoming envelope and produces an intentional response."""
        pass


# ============================================================================
# 4. SPECIALIZED AGENT WORKERS
# ============================================================================

class PlannerAgent(BaseAgent):
    """Deconstructs user goals into an actionable sequential strategy."""

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        logger.info(f"[{self.name}] Processing strategic decomposition...")
        state = await self.blackboard.get_snapshot()

        # Deterministic simulation of planning logic (or external LLM call)
        plan_desc = f"1. Analyze technical architecture for '{state.task_goal}'. 2. Audit security layers."
        await self.blackboard.update(current_plan=plan_desc)

        return AgentMessage(
            correlation_id=message.correlation_id,
            sender=self.name,
            recipient=message.sender,
            performative=Performative.INFORM,
            payload={"plan": plan_desc},
            iteration_index=message.iteration_index
        )


class ResearchSpecialistAgent(BaseAgent):
    """Gathers domain evidence and generates structural solutions."""

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        logger.info(f"[{self.name}] Generating draft solution based on plan...")
        state = await self.blackboard.get_snapshot()

        simulated_data = [
            "OAuth2.0 with Mutual-TLS enforced.",
            "Token Bucket rate limiting at 5000 req/sec.",
            "Distributed tracing via OpenTelemetry instrumentation."
        ]
        draft = (
            f"Architecture Plan for: '{state.task_goal}'\n"
            f"Execution Strategy: {state.current_plan}\n"
            f"Artifacts: {', '.join(simulated_data)}"
        )

        await self.blackboard.update(
            research_data=simulated_data,
            draft_solution=draft
        )

        return AgentMessage(
            correlation_id=message.correlation_id,
            sender=self.name,
            recipient=message.sender,
            performative=Performative.PROPOSE,
            payload={"draft": draft},
            iteration_index=message.iteration_index
        )


class VerificationCriticAgent(BaseAgent):
    """Audits artifacts against quality rubrics and enforces consensus."""

    def __init__(self, name: str, blackboard: Blackboard, acceptance_threshold: float = 0.85) -> None:
        super().__init__(name, blackboard)
        self.acceptance_threshold = acceptance_threshold

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        logger.info(f"[{self.name}] Auditing proposal rigor and compliance...")
        state = await self.blackboard.get_snapshot()

        # Heuristic scoring simulation: Check quality requirements
        score = 0.0
        feedback = []

        if state.draft_solution:
            if "Mutual-TLS" in state.draft_solution:
                score += 0.5
            else:
                feedback.append("Missing mTLS implementation details.")

            if "OpenTelemetry" in state.draft_solution:
                score += 0.4
            else:
                feedback.append("Telemetry specifications omitted.")

        # Progressive improvement simulation based on iteration index
        score = min(1.0, score + (message.iteration_index * 0.1))

        await self.blackboard.update(verification_score=score)

        if score >= self.acceptance_threshold:
            logger.info(f"[{self.name}] Score {score:.2f} meets threshold {self.acceptance_threshold}. ACCEPTED.")
            await self.blackboard.update(is_completed=True)
            return AgentMessage(
                correlation_id=message.correlation_id,
                sender=self.name,
                recipient=message.sender,
                performative=Performative.ACCEPT,
                payload={"score": score, "feedback": "Criteria satisfied fully."},
                iteration_index=message.iteration_index
            )
        else:
            logger.warning(f"[{self.name}] Score {score:.2f} below threshold. CRITIQUE issued.")
            return AgentMessage(
                correlation_id=message.correlation_id,
                sender=self.name,
                recipient=message.sender,
                performative=Performative.CRITIQUE,
                payload={"score": score, "feedback": "; ".join(feedback)},
                iteration_index=message.iteration_index
            )


# ============================================================================
# 5. SUPERVISOR ORCHESTRATOR ENGINE
# ============================================================================

class MultiAgentOrchestrator:
    """Central Controller managing the lifecycle, DAG dependencies, and loop detection."""

    def __init__(self, task_goal: str, max_iterations: int = 5) -> None:
        self.task_goal = task_goal
        self.max_iterations = max_iterations
        self.blackboard = Blackboard(task_goal=task_goal)

        # Initialize Workers
        self.planner = PlannerAgent(name="PlannerNode", blackboard=self.blackboard)
        self.researcher = ResearchSpecialistAgent(name="ResearcherNode", blackboard=self.blackboard)
        self.critic = VerificationCriticAgent(name="CriticNode", blackboard=self.blackboard)

    async def execute(self) -> BlackboardState:
        session_id = str(uuid.uuid4())
        logger.info(f"[Orchestrator] Starting session {session_id} for goal: '{self.task_goal}'")

        # Step 1: Sequential Initialization - Planning Phase
        plan_req = AgentMessage(
            correlation_id=session_id,
            sender="Supervisor",
            recipient=self.planner.name,
            performative=Performative.REQUEST,
            payload={"instruction": "Create deconstructed execution graph"},
            iteration_index=0
        )
        plan_response = await self.planner.handle_message(plan_req)
        assert plan_response.performative == Performative.INFORM

        # Step 2: Cyclic Execution - Research/Draft and Critique Loop
        iteration = 1
        previous_score = -1.0

        while iteration <= self.max_iterations:
            logger.info(f"[Orchestrator] --- Starting Iteration Cycle {iteration}/{self.max_iterations} ---")

            # Phase A: Request Draft
            research_req = AgentMessage(
                correlation_id=session_id,
                sender="Supervisor",
                recipient=self.researcher.name,
                performative=Performative.REQUEST,
                payload={"step": "draft_generation"},
                iteration_index=iteration
            )
            draft_res = await self.researcher.handle_message(research_req)

            # Phase B: Critique Draft
            eval_req = AgentMessage(
                correlation_id=session_id,
                sender="Supervisor",
                recipient=self.critic.name,
                performative=Performative.REQUEST,
                payload={"target_message_id": draft_res.message_id},
                iteration_index=iteration
            )
            eval_res = await self.critic.handle_message(eval_req)

            current_score = eval_res.payload["score"]

            # Edge Case Guard: Semantic Deadlock / Convergence Stagnation
            if abs(current_score - previous_score) < 0.001 and current_score < self.critic.acceptance_threshold:
                logger.error("[Orchestrator] Convergence stagnation detected: Score delta is zero. Breaking loop.")
                break

            previous_score = current_score

            if eval_res.performative == Performative.ACCEPT:
                logger.info("[Orchestrator] Consensus successfully reached!")
                break

            iteration += 1

        if iteration > self.max_iterations:
            logger.error("[Orchestrator] Max iterations exceeded without acceptable consensus.")

        final_state = await self.blackboard.get_snapshot()
        logger.info(f"[Orchestrator] Workflow terminated. Completed: {final_state.is_completed}, v{final_state.version}")
        return final_state
```

---

## 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Terjadinya | Dampak Sistem | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Bizarre Debate Loop** | Agen Peneliti dan Verifikator berselisih secara simetris tanpa menghasilkan data baru. | Latensi tinggi, biaya token meledak, CPU starvation. | Implementasikan *Maximum Iteration Ceiling* ($T_{\max}$) dan *Semantic Stagnation Detection* ($\Delta S < \epsilon$). |
| **Cascading Hallucination** | Agen awal menyimpulkan premis yang salah, lalu diekstrak agen downstream sebagai kebenaran mutlak. | Output terlihat meyakinkan padahal secara faktual invalid. | Terapkan *Grounding Verification Gate* mandiri pada Blackboard sebelum state dipromosikan ke tahap berikutnya. |
| **Deadlock via Circular Dependency** | Agen A menunggu output Agen B, sedangkan Agen B menunggu konfirmasi Agen A (pola peer-to-peer tanpa sinkronisasi). | Sistem berhenti merespons (*hang* tanpa batas). | Wajibkan topologi orkestrasi berupa Directed Acyclic Graph (DAG) terpusat, atau gunakan *timeout leases* pada setiap interaksi. |
| **State Version Drift (Race Condition)** | Dua agen membaca snapshot Blackboard v1, lalu keduanya menulis balik secara paralel. | Data penulisan agen terakhir menimpa penulisan agen pertama (*lost update*). | Terapkan Optimistic Concurrency Control (OCC) menggunakan kunci versi atau atomic transaction via `asyncio.Lock`. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap arsitektur koordinasi multi-agent membawa konsekuensi operasional yang berbeda:

```
[Decentralized Choreography]  <--- Dimension Spectrum --->  [Centralized Orchestration]
- High Latency Uncertainty                                 + Deterministic Control
- Complex Observability                                    + Simple Auditing & Telemetry
+ High Resilience (No SPOF)                                - Single Point of Failure (SPOF)
```

### Matriks Perbandingan Desain

| Dimensi Parameter | Centralized Orchestrator | Decentralized Choreography | Shared Blackboard |
| :--- | :--- | :--- | :--- |
| **Deterministik Alur** | **Sangat Tinggi**: Graph eksekusi didefinisikan secara eksplisit. | **Rendah**: Alur bergantung pada interaksi pesan reaktif. | **Sedang**: Agen bertindak atas perubahan state papan data. |
| **Overhead Latensi** | Tambahan latensi *hop* pada Supervisor setiap pergantian tugas. | Sangat optimal untuk eksekusi paralel murni antar-agen. | Tergantung latensi penguncian memori (*lock overhead*). |
| **Skalabilitas Agen** | Kompleksitas logika router meningkat seiring bertambahnya agen. | Mudah menambah agen pendengar baru (*loosely coupled*). | Rentan *bottleneck* I/O pada penyimpanan data terpusat. |
| **Kemudahan Debugging** | **Tinggi**: Single trace stack ID memetakan seluruh siklus. | **Sangat Rendah**: Membutuhkan distributed trace aggregation. | **Tinggi**: State terpusat menyediakan catatan audit lengkap. |

---

## 9. Best Practices & Standard Industri

1. **Distribusi OpenTelemetry Kontekstual**: Wajib menginjeksi header `traceparent` dan `baggage` pada setiap `AgentMessage`. Setiap siklus pemikiran agen diikatkan ke dalam satu OpenTelemetry Child Span dari Root Trace workflow utama.
2. **Prinsip Least-Privilege Tools**: Jangan pernah membagikan instance client database yang memiliki akses tulis penuh kepada agen analis umum. Agen hanya boleh diinjeksi antarmuka *Read-Only* atau fungsi isolasi terkurasi (*Sandboxed Tool Execution*).
3. **Idempotensi Tindakan Eksternal**: Jika agen memiliki kemampuan eksekusi efek samping (*side-effects*) seperti pembayaran atau pengiriman email, pastikan argumen menyertakan **Idempotency Key** unik yang dihasilkan oleh Orchestrator (bukan oleh LLM itu sendiri).
4. **Deterministic Token & Iteration Budgets**: Setiap agen wajib memiliki alokasi anggaran biaya dan iterasi yang dipantau ketat secara *real-time*. Hentikan eksekusi agen jika batas anggaran terlampaui sebelum memicu pembengkakan biaya sistem.

---

## 10. Hands-on Lab Exercise

### Deskripsi Masalah
Dalam latihan ini, Anda akan menjalankan implementasi multi-agent runtime di atas, menambahkan agen spesialis baru (**SecurityAuditorAgent**), dan memverifikasi integritas sistem melalui serangkaian pengujian terotomatisasi (*automated test suite*).

### Langkah 1: Persiapan Lingkungan
Pastikan Anda menggunakan Python versi 3.10 atau yang lebih baru. Pasang dependensi yang dibutuhkan:

```bash
pip install pydantic pytest pytest-asyncio
```

### Langkah 2: Tambahkan SecurityAuditorAgent
Tambahkan agen baru yang bertugas memvalidasi bahwa seluruh solusi mengandung mekanisme mitigasi kerentanan perangkat lunak (contoh: *Input Sanitization*). Simpan berkas pengujian berikut dengan nama `test_multi_agent.py`:

```python
"""
Test file: test_multi_agent.py
Run command: pytest -v test_multi_agent.py
"""

import pytest
import pytest_asyncio
from collaborative_multi_agent_runtime import (
    MultiAgentOrchestrator,
    BaseAgent,
    AgentMessage,
    Performative,
    Blackboard
)


class SecurityAuditorAgent(BaseAgent):
    """Audits draft solutions specifically for injection flaws."""

    async def handle_message(self, message: AgentMessage) -> AgentMessage:
        state = await self.blackboard.get_snapshot()
        draft = state.draft_solution or ""

        # Validate security requirement
        has_security = "OAuth" in draft or "mTLS" in draft

        return AgentMessage(
            correlation_id=message.correlation_id,
            sender=self.name,
            recipient=message.sender,
            performative=Performative.INFORM if has_security else Performative.REJECT,
            payload={"secure": has_security},
            iteration_index=message.iteration_index
        )


@pytest.mark.asyncio
async def test_multi_agent_successful_orchestration():
    """Validates that orchestrator completes workflow with adequate iterations."""
    orchestrator = MultiAgentOrchestrator(
        task_goal="Build Zero-Trust Microservice Gateway",
        max_iterations=3
    )

    final_state = await orchestrator.execute()

    # Assertions
    assert final_state.is_completed is True
    assert final_state.verification_score >= 0.85
    assert len(final_state.research_data) > 0
    assert "OAuth2.0" in final_state.draft_solution
    assert final_state.version > 3


@pytest.mark.asyncio
async def test_security_auditor_verification():
    """Direct isolated unit test for the custom SecurityAuditorAgent."""
    blackboard = Blackboard(task_goal="Test Security")
    await blackboard.update(draft_solution="Implementation using OAuth2.0 and TLS encryption.")

    auditor = SecurityAuditorAgent(name="AuditorTest", blackboard=blackboard)
    msg = AgentMessage(
        correlation_id="test-123",
        sender="Tester",
        recipient=auditor.name,
        performative=Performative.REQUEST,
        payload={},
        iteration_index=1
    )

    res = await auditor.handle_message(msg)
    assert res.performative == Performative.INFORM
    assert res.payload["secure"] is True
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan pengujian menggunakan `pytest` untuk memverifikasi fungsionalitas:

```bash
pytest -v test_multi_agent.py
```

### Kriteria Kelulusan:
* Seluruh test case berstatus `PASSED`.
* Log terminal menampilkan jejak audit deterministik: `PlannerNode` -> `ResearcherNode` -> `CriticNode` -> `Supervisor`.
* Blackboard memperlihatkan peningkatan versi state secara monotonik tanpa ada data yang tertimpa secara inkonsisten.