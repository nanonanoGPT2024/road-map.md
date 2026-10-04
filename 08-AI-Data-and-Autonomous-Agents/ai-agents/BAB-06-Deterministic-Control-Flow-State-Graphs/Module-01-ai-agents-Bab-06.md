# Bab 06: Deterministic Control Flow & State Graphs

## Module 01: Foundations of Cyclic State Graphs & Deterministic Agent Orchestration

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang State Graph Schema** berbasis tipe data mutlak (*strictly typed*) menggunakan Pydantic v2 dan anotasi reducer fungsional untuk mengontrol propagasi delta state.
- **Mengimplementasikan Topologi Directed Cyclic Graph (DCG)** yang mengadopsi model komputasi *Bulk Synchronous Parallel* (BSP) / Pregel untuk siklus evaluasi, koreksi berulang (*reflection/retry*), dan terminasi deterministik.
- **Membangun Dynamic Routing Engines** menggunakan conditional edges murni (*pure function evaluators*) untuk memisahkan logika orkestrasi kontrol dari payload inferensi LLM.
- **Mengintegrasikan Persistence Checkpointing Layer** dengan isolasi thread runtime untuk mendukung fitur *fault tolerance*, *state hydration*, *time-travel inspection*, dan manipulasi mutasi status (*state rewrites*).

---

### 2. Concept Overview
Mayoritas implementasi agen otonom berbasis *pure prompt-chaining* atau ReAct loop murni gagal dalam skala produksi akibat sifat non-deterministik dan ketiadaan batas kontrol (*unbounded execution*). Pendekatan **State Graph** mengatasi masalah ini dengan memodelkan orkestrasi agen bukan sebagai aliran instruksi linier, melainkan sebagai **Finite State Machine (FSM) yang diperluas** (*Extended State Machine*) dalam bentuk **Directed Cyclic Graph (DCG)**.

```
       [State Snapshot: S_t]
                 │
                 ▼
      ┌─────────────────────┐
      │   Graph Execution   │ ◄─── (Superstep k)
      │   Node Computation  │
      └──────────┬──────────┘
                 │
                 ▼
      ┌─────────────────────┐
      │ State Reducer (Bus) │ ──── Delta Updates (ΔS) applied
      └──────────┬──────────┘
                 │
                 ▼
      ┌─────────────────────┐
      │ Conditional Router  │ ──── Pure Deterministic Function
      └──────────┬──────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   [Branch: Node B]   [Loopback: Node A]  ─── (Superstep k+1)
```

#### Mental Model: Pregel & Bulk Synchronous Parallel (BSP)
Eksekusi state graph beroperasi berdasarkan paradigma **Pregel / BSP**:
1. **Superstep ($k$)**: Sekumpulan *node* yang aktif dieksekusi secara paralel atau terurut. Setiap node membaca snapshot status saat ini ($S_t$) yang bersifat *immutable* dan mengembalikan status mutasi inkremental (*delta update*, $\Delta S$).
2. **State Reduction**: Runtime mengagregasi semua $\Delta S$ melalui fungsi peredam (*reducer functions*) yang telah didefinisikan secara eksplisit.
3. **Synchronization Barrier**: Tidak ada node di superstep berikutnya ($k+1$) yang dieksekusi sebelum semua mutasi status pada superstep $k$ berhasil diterapkan dan divalidasi oleh skema.
4. **Deterministic Routing**: Sisi berarah (*edges*) mengevaluasi status baru ($S_{t+1}$) untuk menentukan node mana yang akan dijadwalkan pada superstep berikutnya.

---

### 3. Why It Matters
Dalam arsitektur enterprise, kegagalan orkestrasi agen berdampak langsung pada latensi, biaya inferensi token, dan integritas data.

* **ReAct Flaws**: Paradigma ReAct (*Reason + Act*) mengandalkan LLM untuk memutuskan *kapan* harus berhenti dan *alat apa* yang harus dipanggil di setiap putaran. Ketika LLM mengalami halusinasi, sistem terjebak dalam *infinite recursive loops* yang menghabiskan anggaran API token dan melanggar SLA latensi.
* **DAG Limitations**: Orkestrator alur kerja tradisional (seperti Apache Airflow atau Prefect) berbasis *Directed Acyclic Graph* (DAG). DAG secara fundamental menolak siklus (*cycles*), sehingga tidak dapat mengeksekusi pola penting pada agen seperti:
  * *Code generation -> Static analysis fail -> Self-correction loop*.
  * *Draft response -> Critic critique -> Re-draft*.
* **State Graphs as the Enterprise Solution**: Menggabungkan fleksibilitas percabangan dinamis dengan pagar pembatas deterministik (*deterministic guardrails*). Anda menentukan *topologi* dan *kebijakan transisi*, sementara model hanya diizinkan bernalar di dalam batas-batas node yang terisolasi.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur state graph terdistribusi memisahkan komputasi (*node processing*), manipulasi status (*reducer bus*), dan persistensi snapshot status (*checkpointer*).

```
+--------------------------------------------------------------------------------------------------+
|                                    STATE GRAPH RUNTIME ENGINE                                    |
|                                                                                                  |
|   +---------------------+        +--------------------+        +-----------------------------+   |
|   |   Node: Extractor   |        |   Node: Analyzer   |        |     Node: Human Gate        |   |
|   |   (IO/Compute)      |        |   (LLM Reasoning)  |        |     (Interrupt Signal)      |   |
|   +----------+----------+        +---------+----------+        +--------------+--------------+   |
|              |                             |                                  |                  |
|       Yields ΔState                 Yields ΔState                      Yields ΔState             |
|              |                             |                                  |                  |
|              +----------------------+      |      +---------------------------+                  |
|                                     |      |      |                                             |
|                                     v      v      v                                             |
|                           +--------------------------------+                                    |
|                           |      STATE REDUCER ENGINE      |                                    |
|                           |  (Applies Merges / Overwrites) |                                    |
|                           +---------------+----------------+                                    |
|                                           |                                                      |
|                   New Immutable State (S) |                                                      |
|                                           v                                                      |
|                           +--------------------------------+                                    |
|                           |      CONDITIONAL ROUTER        |                                    |
|                           |  Pure Functions (State -> Key) |                                    |
|                           +---------------+----------------+                                    |
|                                           |                                                      |
+-------------------------------------------|------------------------------------------------------+
                                            |
                         Persist / Stream   |  Hydrate Thread State
                                            v
                +-------------------------------------------------------+
                |             STATE PERSISTENCE CHECKPOINTER            |
                |  (PostgreSQL / Redis / SQLite Storage Backing)        |
                |                                                       |
                |   +-------------+  +-------------+  +-------------+   |
                |   | Step 0: S_0 |->| Step 1: S_1 |->| Step 2: S_2 |   |
                |   +-------------+  +-------------+  +-------------+   |
                +-------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. State Reducer Pattern
State didefinisikan sebagai *compound object*. Setiap *field* memiliki operator reduksi yang mengatur bagaimana nilai baru digabungkan dengan nilai lama.

$$\text{Field}_{\text{new}} = \mathcal{R}(\text{Field}_{\text{current}}, \Delta \text{Field})$$

* **Overwrite Reducer**: $\mathcal{R}(A, B) = B$ (Nilai lama ditimpa seluruhnya oleh nilai mutasi).
* **Append/Monoidal Reducer**: $\mathcal{R}(A, B) = A \cup B$ (Array/list mengakumulasi elemen baru, mempertahankan seluruh riwayat interaksi).
* **Numerical Delta Reducer**: $\mathcal{R}(A, B) = A + B$ (Penghitung langkah rekursi atau pemakaian kuota token).

#### B. The Superstep Execution Loop
1. **Resolution**: Runtime mengidentifikasi kumpulan node yang siap dieksekusi berdasarkan evaluasi *edges* pada superstep sebelumnya.
2. **Parallel Dispatch**: Jika beberapa node dijadwalkan secara independen (misalnya pada pola *fan-out*), node dieksekusi secara asinkron via `asyncio.gather`.
3. **Atomic Reduction Barrier**:
   * Jika dua node mencoba memutasi *field* yang sama menggunakan overwrite reducer, konflik status terdeteksi (*race condition*).
   * Reducer yang valid mengeksekusi penggabungan status tanpa efek samping (*pure functions*).
4. **Snapshot Checkpointing**: Snapshot status mutlak disimpan ke *storage backend* dengan mengaitkan `thread_id` dan `checkpoint_id` (berbasis monolitik ID atau UUID v7).
5. **Edge Evaluation**:
   $$\text{NextNode} = \text{EdgeFunc}(S_{t+1})$$
   Jika $\text{NextNode} = \text{END}$, eksekusi dihentikan. Jika tidak, proses berlanjut ke superstep berikutnya.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Enterprise State Graph Engine** murni (tanpa ketergantungan pihak ketiga selain Pydantic) untuk memperlihatkan mekanisme inti Pregel, penanganan status, conditional routing, dan checkpointing.

```python
"""
Enterprise Cyclic State Graph Runtime Engine.
Author: Principal AI Engineer & Distributed Systems Specialist.
Compatibility: Python 3.11+
"""

from __future__ import annotations

import asyncio
import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    TypeVar,
    get_type_hints,
)

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("StateGraphEngine")

# --- CORE TYPES & STATE SCHEMAS ---

class ReducerOperator:
    """Kumpulan operator reduksi deterministik standar."""
    @staticmethod
    def append(current: list[Any], update: list[Any]) -> list[Any]:
        if not isinstance(current, list) or not isinstance(update, list):
            raise TypeError("Append reducer requires both operands to be lists.")
        return current + update

    @staticmethod
    def overwrite(current: Any, update: Any) -> Any:
        return update if update is not None else current

    @staticmethod
    def increment(current: int, update: int) -> int:
        return current + update


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentState(BaseModel):
    """
    Representasi skema status insiden enterprise.
    Mendukung konfigurasi reducer melalui anotasi Metadata.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    incident_id: str
    raw_payload: str
    parsed_logs: Annotated[list[str], ReducerOperator.append] = Field(default_factory=list)
    severity: Annotated[IncidentSeverity, ReducerOperator.overwrite] = IncidentSeverity.LOW
    remediation_attempts: Annotated[int, ReducerOperator.increment] = 0
    requires_human_intervention: Annotated[bool, ReducerOperator.overwrite] = False
    is_resolved: Annotated[bool, ReducerOperator.overwrite] = False
    execution_trace: Annotated[list[str], ReducerOperator.append] = Field(default_factory=list)


# --- CHECKPOINT PERSISTENCE LAYER ---

@dataclass(frozen=True)
class CheckpointRecord:
    thread_id: str
    step: int
    state_payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseCheckpointer(ABC):
    """Abstraksi persistence engine untuk State Snapshots."""

    @abstractmethod
    async def save_checkpoint(self, thread_id: str, step: int, state: BaseModel) -> None:
        pass

    @abstractmethod
    async def load_latest_checkpoint(self, thread_id: str, state_cls: Type[T]) -> Optional[tuple[int, T]]:
        pass


T = TypeVar("T", bound=BaseModel)


class InMemoryCheckpointer(BaseCheckpointer):
    """Thread-safe In-Memory Checkpointer dengan dukungan time-travel inspection."""

    def __init__(self) -> None:
        self._storage: dict[str, list[CheckpointRecord]] = {}
        self._lock = asyncio.Lock()

    async def save_checkpoint(self, thread_id: str, step: int, state: BaseModel) -> None:
        async with self._lock:
            if thread_id not in self._storage:
                self._storage[thread_id] = []
            record = CheckpointRecord(
                thread_id=thread_id,
                step=step,
                state_payload=state.model_dump(mode="json"),
            )
            self._storage[thread_id].append(record)
            logger.debug("Checkpoint persisted: thread=%s, step=%d", thread_id, step)

    async def load_latest_checkpoint(self, thread_id: str, state_cls: Type[T]) -> Optional[tuple[int, T]]:
        async with self._lock:
            history = self._storage.get(thread_id, [])
            if not history:
                return None
            latest = history[-1]
            deserialized_state = state_cls.model_validate(latest.state_payload)
            return latest.step, deserialized_state


# --- GRAPH ENGINE COMPONENTS ---

NodeAction = Callable[[T], Awaitable[dict[str, Any]]]
RoutingPredicate = Callable[[T], str]
END = "__END__"


class StateGraphException(Exception):
    """Base exception class for State Graph runtime violations."""
    pass


class RecursionLimitExceeded(StateGraphException):
    """Dilempar ketika graf melewati batas iterasi siklik maksimum."""
    pass


class StateGraph(Generic[T]):
    """
    Engine Orkestrator Siklik yang mengelola Node, Reducer, 
    Conditional Edges, dan Sinkronisasi Superstep.
    """

    def __init__(self, state_schema: Type[T], checkpointer: Optional[BaseCheckpointer] = None) -> None:
        self.state_schema = state_schema
        self.checkpointer = checkpointer or InMemoryCheckpointer()
        self.nodes: dict[str, NodeAction[T]] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, RoutingPredicate[T]] = {}
        self.entry_point: Optional[str] = None
        self._reducers: dict[str, Callable[[Any, Any], Any]] = self._extract_reducers()

    def _extract_reducers(self) -> dict[str, Callable[[Any, Any], Any]]:
        """Mengekstrak fungsi reducer yang disematkan via tipe Annotated."""
        reducers: dict[str, Callable[[Any, Any], Any]] = {}
        type_hints = get_type_hints(self.state_schema, include_extras=True)
        for field_name, hint in type_hints.items():
            if hasattr(hint, "__metadata__") and hint.__metadata__:
                for meta in hint.__metadata__:
                    if callable(meta):
                        reducers[field_name] = meta
                        break
            if field_name not in reducers:
                reducers[field_name] = ReducerOperator.overwrite
        return reducers

    def add_node(self, key: str, action: NodeAction[T]) -> None:
        if key in self.nodes or key == END:
            raise ValueError(f"Reserved or duplicate node key: {key}")
        self.nodes[key] = action

    def set_entry_point(self, key: str) -> None:
        if key not in self.nodes:
            raise KeyError(f"Entry point {key} must exist in registered nodes.")
        self.entry_point = key

    def add_edge(self, start_key: str, end_key: str) -> None:
        if start_key not in self.nodes:
            raise KeyError(f"Source node {start_key} not registered.")
        if end_key not in self.nodes and end_key != END:
            raise KeyError(f"Destination node {end_key} not registered.")
        self.edges[start_key] = end_key

    def add_conditional_edge(self, source_key: str, routing_fn: RoutingPredicate[T]) -> None:
        if source_key not in self.nodes:
            raise KeyError(f"Source node {source_key} not registered.")
        self.conditional_edges[source_key] = routing_fn

    def _apply_state_mutation(self, current_state: T, delta: dict[str, Any]) -> T:
        """
        Menerapkan mutasi status delta melalui pipeline reducer yang terdaftar
        secara deterministik dan mengembalikan snapshot baru.
        """
        raw_current = current_state.model_dump()
        for key, update_value in delta.items():
            if key not in raw_current:
                raise AttributeError(f"Mutation target key '{key}' does not exist on {self.state_schema.__name__}")
            reducer = self._reducers.get(key, ReducerOperator.overwrite)
            raw_current[key] = reducer(raw_current[key], update_value)

        return self.state_schema.model_validate(raw_current)

    async def execute(
        self,
        initial_input: dict[str, Any],
        thread_id: str,
        recursion_limit: int = 25,
    ) -> T:
        """
        Menjalankan loop eksekusi graf berbasis Superstep / Pregel model.
        """
        if not self.entry_point:
            raise StateGraphException("Entry point is not set.")

        step = 0
        latest_checkpoint = await self.checkpointer.load_latest_checkpoint(thread_id, self.state_schema)

        if latest_checkpoint:
            step, current_state = latest_checkpoint
            logger.info("Resuming execution from Checkpoint Step %d for Thread %s", step, thread_id)
        else:
            current_state = self.state_schema.model_validate(initial_input)
            await self.checkpointer.save_checkpoint(thread_id, step, current_state)

        current_node_key: str = self.entry_point

        while current_node_key != END:
            if step >= recursion_limit:
                raise RecursionLimitExceeded(
                    f"Max recursion steps ({recursion_limit}) exceeded at node '{current_node_key}'."
                )

            step += 1
            node_fn = self.nodes[current_node_key]
            logger.info("[Superstep %d] Executing Node: '%s'", step, current_node_key)

            # Node memproses snapshot state yang bersifat read-only (deep copied)
            read_only_state = current_state.model_copy(deep=True)
            try:
                state_delta = await node_fn(read_only_state)
            except Exception as e:
                logger.error("Node execution failure in '%s': %s", current_node_key, str(e), exc_info=True)
                raise StateGraphException(f"Node '{current_node_key}' failed: {str(e)}") from e

            # Reducer Phase (Sinkronisasi barrier)
            current_state = self._apply_state_mutation(current_state, state_delta)

            # Persistence Phase
            await self.checkpointer.save_checkpoint(thread_id, step, current_state)

            # Routing Phase
            if current_node_key in self.conditional_edges:
                router_fn = self.conditional_edges[current_node_key]
                next_node_key = router_fn(current_state)
                logger.debug("Conditional routing from '%s' resolved to '%s'", current_node_key, next_node_key)
            elif current_node_key in self.edges:
                next_node_key = self.edges[current_node_key]
            else:
                next_node_key = END

            current_node_key = next_node_key

        logger.info("Graph execution successfully reached END node at Step %d", step)
        return current_state


# --- WORKFLOW NODE IMPLEMENTATIONS ---

async def log_parsing_node(state: IncidentState) -> dict[str, Any]:
    """Menguraikan muatan teks mentah menjadi entri log diskret."""
    logs = [f"PARSED: {line.strip()}" for line in state.raw_payload.split("\n") if line.strip()]
    return {
        "parsed_logs": logs,
        "execution_trace": [f"log_parsing_node evaluated at {datetime.now(timezone.utc).isoformat()}"],
    }


async def triage_severity_node(state: IncidentState) -> dict[str, Any]:
    """Menganalisis anomali pada log untuk menentukan tingkat keparahan insiden."""
    severity = IncidentSeverity.LOW
    for log in state.parsed_logs:
        if "FATAL" in log or "CRITICAL" in log:
            severity = IncidentSeverity.CRITICAL
            break
        elif "ERROR" in log:
            severity = IncidentSeverity.HIGH

    return {
        "severity": severity,
        "execution_trace": [f"triage_severity_node categorized as {severity.value}"],
    }


async def automated_remediation_node(state: IncidentState) -> dict[str, Any]:
    """Mencoba memperbaiki anomali secara otonom."""
    new_attempts = 1
    # Simulasi: Jika sudah dicoba 2 kali, perbaikan otomatis dianggap gagal
    resolved = state.remediation_attempts + new_attempts >= 2
    return {
        "remediation_attempts": new_attempts,
        "is_resolved": resolved,
        "execution_trace": [
            f"automated_remediation_node executed attempt #{state.remediation_attempts + new_attempts}"
        ],
    }


async def human_escalation_node(state: IncidentState) -> dict[str, Any]:
    """Gerbang eskalasi manual saat sistem otomatis gagal."""
    return {
        "requires_human_intervention": True,
        "execution_trace": ["human_escalation_node triggered: Human on-call assigned"],
    }


# --- DETERMINISTIC ROUTING RULES ---

def route_after_triage(state: IncidentState) -> str:
    """Routing deterministik berdasarkan keparahan insiden."""
    if state.severity == IncidentSeverity.CRITICAL:
        return "human_escalation_node"
    return "automated_remediation_node"


def route_after_remediation(state: IncidentState) -> str:
    """Evaluasi siklik untuk perbaikan otomatis."""
    if state.is_resolved:
        return END
    if state.remediation_attempts >= 2:
        return "human_escalation_node"
    # Membentuk Loop Kembali untuk Re-Try Deterministic Loop
    return "automated_remediation_node"


# --- FACTORY & DEMONSTRATION RUNNER ---

def build_incident_workflow() -> StateGraph[IncidentState]:
    graph = StateGraph(IncidentState)

    # Register nodes
    graph.add_node("log_parsing_node", log_parsing_node)
    graph.add_node("triage_severity_node", triage_severity_node)
    graph.add_node("automated_remediation_node", automated_remediation_node)
    graph.add_node("human_escalation_node", human_escalation_node)

    # Set Entry Point
    graph.set_entry_point("log_parsing_node")

    # Define Topologies
    graph.add_edge("log_parsing_node", "triage_severity_node")
    graph.add_conditional_edge("triage_severity_node", route_after_triage)
    graph.add_conditional_edge("automated_remediation_node", route_after_remediation)
    graph.add_edge("human_escalation_node", END)

    return graph


async def main() -> None:
    workflow = build_incident_workflow()
    thread_id = "incident-prod-9842"

    initial_payload = {
        "incident_id": thread_id,
        "raw_payload": (
            "2023-10-27T10:00:01 INFO Connection established\n"
            "2023-10-27T10:00:03 ERROR Database deadlocked on transaction 491\n"
            "2023-10-27T10:00:05 ERROR Retrying connection failed"
        ),
    }

    logger.info("--- Memulai Eksekusi State Graph ---")
    final_state = await workflow.execute(initial_input=initial_payload, thread_id=thread_id)

    print("\n--- FINAL EXECUTION STATE DUMP ---")
    print(final_state.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

#### 1. Unbounded Cyclic Recurrence (Infinite Loop)
* **Karakteristik**: Agen terus-menerus gagal dalam siklus refleksi/perbaikan tanpa pernah mencapai kondisi terminasi deterministik.
* **Mitigasi**:
  * Terapkan `recursion_limit` yang divalidasi pada runtime engine (seperti parameter pada kode di atas).
  * Terapkan state counter dengan `increment` reducer pada field eksekusi (`attempts`). Evaluasi *edge* wajib memiliki cabang *fallback* menuju status degradasi atau eskalasi manusia saat batas tercapai:
    ```python
    if state.attempts >= MAX_ATTEMPTS:
        return "fallback_node"
    ```

#### 2. Reducer Write Contention & Race Conditions
* **Karakteristik**: Ketika terjadi percabangan paralel (*fan-out*), dua node mengembalikan mutasi untuk field skema yang sama secara konkuren, sementara reducer dikonfigurasi dengan semantik `overwrite`.
* **Mitigasi**:
  * Isolasi skema: Batasi hak mutasi node hanya pada subset field tertentu yang bersifat privat bagi node tersebut.
  * Hanya gunakan *commutative/monoidal reducers* (seperti `append`, `set union`, atau `numeric sum`) pada state keys yang diakses bersama oleh beberapa node paralel.

#### 3. State Drift & Context Poisoning
* **Karakteristik**: Pada skema yang menggunakan append reducer secara berlebihan, riwayat percakapan atau trace log terus membesar secara monoton hingga melewati batas token context window LLM.
* **Mitigasi**: Buat *Compactor Node* reguler yang memotong (*truncate*), merangkum (*summarize*), atau membuang pesan sistem terlama dengan *sliding window mechanism* sebelum diteruskan kembali ke model.

#### 4. Checkpoint Deserialization Incompatibility
* **Karakteristik**: Versi kode agen diperbarui di lingkungan produksi saat proses thread berumur panjang (*long-running*) sedang berlangsung. Checkpoint lama yang dimuat kembali gagal divalidasi oleh skema Pydantic baru.
* **Mitigasi**:
  * Terapkan skema migrasi berbasis semver atau field default opsional pada Pydantic (`Field(default=None)`).
  * Simpan skema metadata version di setiap entri checkpoint storage.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Evaluasi | ReAct Pattern Loop | Workflow Engine DAGs (Airflow/Prefect) | Finite State Machine (FSM) Murni | Cyclic State Graphs (Engine di atas / LangGraph) |
| :--- | :--- | :--- | :--- | :--- |
| **Topologi Aliran** | Tak Berbentuk (Diarahkan LLM) | Non-Cyclic Terarah (DAG) | FSM Linier/Ketat | Directed Cyclic Graph (DCG) |
| **Dukungan Loop/Siklus** | Ya (Tidak Terbatas) | Tidak Didukung (Ilegal) | Terbatas pada status statis | Native & Terkontrol (*via BSP*) |
| **Deterministik Routing** | Sangat Rendah | Sangat Tinggi | Absolut | Sangat Tinggi (Terisolasi dari LLM) |
| **Biaya Token** | Tinggi (Rentan boros) | Terendah (Hanya di node) | Nol/Sangat Rendah | Terkendali (Batas siklus terukur) |
| **State Persistence** | Transient (Hilang jika *crash*) | Persistent per Task DB | Persistent per State transition | Checkpoint Snapshot Granular |
| **Human-in-the-Loop** | Sangat Sulit | Polling Task Terbatas | Melalui State Transition Gate | Native Breakpoints / Hydration |

---

### 9. Best Practices & Standard Industri

1. **State Immutability Contract**: Node tidak boleh memutasi state input secara langsung (*in-place mutation*). Node harus selalu mengembalikan kamus mutasi delta ($\Delta S$). Pelanggaran terhadap prinsip ini merusak keandalan proses *rollback* dan pelacakan audit.
2. **Idempotency Keys**: Setiap pemanggilan tool eksternal yang memicu *side-effect* (misalnya penagihan API gateway, mutasi database, atau pengiriman webhook) di dalam node wajib menyertakan kunci idempoten berbasis hash:
   $$\text{IdempotencyKey} = \text{HMAC-SHA256}(\text{thread\_id} + \text{node\_key} + \text{step})$$
3. **Pure Routing Functions**: Kondisi percabangan pada edge (`RoutingPredicate`) harus merupakan fungsi murni tanpa *side-effect* I/O dan tidak boleh memanggil inferensi LLM tambahan secara langsung di level edge. Seluruh komputasi harus selesai di dalam node.
4. **Structured OpenTelemetry Context**: Pancarkan event audit untuk setiap siklus superstep dengan format span standar industri:
   ```json
   {
     "trace_id": "bfd91e6b376c4e09",
     "span_name": "superstep_execution",
     "attributes": {
       "agent.engine": "StateGraph",
       "agent.thread_id": "incident-prod-9842",
       "agent.step": 3,
       "agent.node": "automated_remediation_node",
       "agent.state_size_bytes": 1042
     }
   }
   ```

---

### 10. Hands-on Lab Exercise: Membangun Code Self-Correction Graph dengan Checkpoint Time-Travel

#### Skenario Lab
Anda ditugaskan merancang *Code Generation & Self-Healing Runtime Engine*. Agen harus:
1. Menghasilkan kode Python berdasarkan instruksi pengguna.
2. Mengeksekusi verifikasi sintaks dan pengujian unit terisolasi.
3. Melakukan *loop back* untuk memperbaiki kode jika pengujian gagal (maksimal 3 kali percobaan).
4. Menyimpan checkpoint di setiap langkah untuk memungkinkan rollback (*time-travel*) ke versi kode tertentu.

#### Langkah 1: Inisialisasi Environment
Pastikan dependensi minimal terpasang:
```bash
pip install pydantic==2.6.4 typing_extensions
```

#### Langkah 2: Definisikan Schema & Node Perbaikan

Buat berkas `lab_self_healing_graph.py`:

```python
import asyncio
from typing import Annotated, Any
from pydantic import BaseModel, Field
# Gunakan engine StateGraph dan Operator dari implementasi Section 6
from engine import StateGraph, ReducerOperator, END

class CodeGenerationState(BaseModel):
    task_prompt: str
    generated_code: Annotated[str, ReducerOperator.overwrite] = ""
    lint_errors: Annotated[list[str], ReducerOperator.overwrite] = Field(default_factory=list)
    iteration: Annotated[int, ReducerOperator.increment] = 0
    test_passed: Annotated[bool, ReducerOperator.overwrite] = False

# --- IMPLEMENTASI NODE ---

async def generator_node(state: CodeGenerationState) -> dict[str, Any]:
    """Menghasilkan implementasi kode (disimulasikan)."""
    # Pada iterasi awal, hasilkan kode yang sengaja salah secara sintaks/logika
    if state.iteration == 0:
        buggy_code = "def add(a, b): return a - b  # Buggy implementation"
    else:
        # Simulasi LLM memperbaiki kode setelah membaca lint_errors
        buggy_code = "def add(a, b): return a + b  # Fixed implementation"
        
    return {
        "generated_code": buggy_code,
        "iteration": 1,
    }

async def tester_node(state: CodeGenerationState) -> dict[str, Any]:
    """Menjalankan evaluasi pengujian terhadap generated_code."""
    errors = []
    # Evaluasi logika sederhana
    local_namespace = {}
    try:
        exec(state.generated_code, {}, local_namespace)
        add_func = local_namespace.get("add")
        if not add_func or add_func(2, 3) != 5:
            errors.append("AssertionError: add(2, 3) did not equal 5")
    except Exception as ex:
        errors.append(f"ExecutionError: {str(ex)}")

    passed = len(errors) == 0
    return {
        "lint_errors": errors,
        "test_passed": passed
    }

# --- EDGE ROUTER ---

def evaluate_test_results(state: CodeGenerationState) -> str:
    if state.test_passed:
        return END
    if state.iteration >= 3:
        print("[Router] Percobaan perbaikan habis. Menghentikan siklus.")
        return END
    print(f"[Router] Pengujian gagal dengan error: {state.lint_errors}. Mengarahkan kembali ke perbaikan.")
    return "generator_node"

# --- PERAKITAN GRAF ---

def create_code_healing_graph() -> StateGraph[CodeGenerationState]:
    graph = StateGraph(CodeGenerationState)
    graph.add_node("generator_node", generator_node)
    graph.add_node("tester_node", tester_node)
    
    graph.set_entry_point("generator_node")
    graph.add_edge("generator_node", "tester_node")
    graph.add_conditional_edge("tester_node", evaluate_test_results)
    
    return graph

async def run_lab():
    engine = create_code_healing_graph()
    thread = "session-dev-1"
    
    input_data = {
        "task_prompt": "Buat fungsi Python 'add(a, b)' yang menjumlahkan dua bilangan."
    }
    
    final_result = await engine.execute(initial_input=input_data, thread_id=thread)
    print("\n=== HASIL AKHIR EKSEKUSI ===")
    print(f"Iterasi Dibutuhkan : {final_result.iteration}")
    print(f"Status Kelulusan   : {final_result.test_passed}")
    print(f"Kode Akhir         : {final_result.generated_code}")
    print(f"Lint Errors        : {final_result.lint_errors}")

if __name__ == "__main__":
    asyncio.run(run_lab())
```

#### Langkah 3: Verifikasi Eksekusi dan Penugasan Lanjutan
1. Jalankan kode di atas dan pastikan bahwa pada langkah pertama pengujian gagal, kemudian runtime melakukan siklus kembali (*loop back*) ke `generator_node`, hingga akhirnya lolos di langkah berikutnya.
2. **Tugas Mandiri Lanjutan**: Perluas class `InMemoryCheckpointer` untuk menambahkan fungsi `rollback_to_step(thread_id: str, target_step: int)`. Modifikasi skrip agar setelah eksekusi selesai, engine dapat melakukan *re-hydrate* status dari langkah ke-1 dan menjalankan kembali eksekusi dengan variasi input prompt secara deterministik. Evaluasi integritas snapshot state yang dihasilkan.