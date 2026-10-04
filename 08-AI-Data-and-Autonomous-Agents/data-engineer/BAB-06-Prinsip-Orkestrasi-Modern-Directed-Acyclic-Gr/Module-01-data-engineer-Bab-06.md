# Modul 01: Prinsip Orkestrasi Modern & Directed Acyclic Graphs (DAG)

Kategori: `08-AI-Data-and-Autonomous-Agents` | Track: `data-engineer` | Level: Advanced

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Memodelkan Dependency Graph:** Mengonseptualisasikan workflow rekayasa data dan inferensi AI multi-tahap sebagai directed acyclic graph formal $G = (V, E)$, memverifikasi kelayakannya secara algoritmik, serta mengidentifikasi relasi dependensi parsial (*partial ordering*).
2. **Mengimplementasikan Algoritma Deteksi Siklus & Pengurutan Topologis:** Mengembangkan algoritma Kahn dan Depth-First Search (DFS) dengan pewarnaan tri-state ($O(|V| + |E|)$) untuk menjamin acyclicity dan mengeksekusi task traversal secara deterministik.
3. **Mendesain Engine State Reconciliation & Idempotensi:** Merancang mesin status terdistribusi (*state machine*) yang mengelola transisi status task (`PENDING`, `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, `UPSTREAM_FAILED`), lengkap dengan mekanisme kompensasi kegagalan, backoff eksponensial, dan jaminan idempotensi operasional.
4. **Mengevaluasi Karakteristik Orkestrasi Modern:** Mengukur perbandingan performa, skalabilitas, dan keandalan antara paradigma *Task-Driven* (Airflow), *Data/Asset-Driven* (Dagster), dan *State/Workflow Engine* (Temporal) dalam konteks beban kerja data lakehouse dan agen otonom.

---

## 2. Concept Overview

Orkestrasi data modern adalah mekanisme deklaratif dan deterministik untuk mengelola eksekusi dependensi, konkurensi, distribusi sumber daya, dan toleransi kesalahan pada serangkaian komputasi heterogen.

### Teori Graf: Directed Acyclic Graph (DAG)

Secara matematis, alur kerja data direpresentasikan sebagai Directed Acyclic Graph:

$$G = (V, E)$$

Di mana:
- $V = \{v_1, v_2, \dots, v_n\}$ adalah himpunan *vertices* (node) yang merepresentasikan unit komputasi atomik (*tasks* atau *assets*).
- $E \subseteq \{(v_i, v_j) \mid v_i, v_j \in V \text{ dan } v_i \neq v_j\}$ adalah himpunan *directed edges* yang merepresentasikan relasi dependensi preseden. Edge terarah $(v_i, v_j)$ menyatakan bahwa komputasi $v_j$ (downstream) hanya dapat dieksekusi setelah komputasi $v_i$ (upstream) selesai dengan status valid.
- **Acyclic Constraint:** Tidak terdapat jalur berarah nontrivial $p = (v_1, v_2, \dots, v_k)$ sedemikian rupa sehingga $v_1 = v_k$. Secara formal:

$$\forall v \in V, \quad \nexists \text{ path } v \leadsto v$$

```
    [Raw Ingestion Task (A)]
           /        \
          v          v
   [Clean Task (B)] [Enrich Task (C)]
          \          /
           v        v
     [Aggregate Task (D)]
              |
              v
   [Feature Store Sync (E)]
```

*Gambar 1: Representasi Kanonikal DAG.* Task $D$ memiliki derajat masuk (*in-degree*) bernilai 2, sehingga membutuhkan terminasi sukses dari Task $B$ dan Task $C$ sebelum state transisinya dapat bergeser ke fase eksekusi.

### Topological Ordering

Untuk mengeksekusi DAG, orchestrator harus menemukan *topological sort*: urutan linier dari semua node di $V$ sedemikian rupa sehingga untuk setiap edge terarah $(u, v) \in E$, node $u$ selalu mendahului node $v$. 

Jika suatu graf memiliki siklus (bukan DAG), urutan linier seperti ini tidak eksis secara matematis, mengindikasikan kebuntuan operasional (*deadlock*). Pengurutan ini diselesaikan melalui:
1. **Algoritma Kahn:** Berbasis *in-degree tracking* ($O(|V| + |E|)$).
2. **Algoritma DFS (Depth-First Search):** Berbasis penelusuran mundur via status pewarnaan (*White*, *Gray*, *Black*).

### Orkestrasi vs. Koreografi

| Dimensi | Orkestrasi (Orchestration) | Koreografi (Choreography) |
| :--- | :--- | :--- |
| **Pola Kontrol** | Sentralistis (Central Controller/Coordinator) | Desentralistis (Autonomous Reactive Components) |
| **State Tracking** | Eksplisit disimpan di Metadata Database | Tersebar via event payload / distributed log |
| **Visibilitas** | Single pane of glass untuk seluruh siklus alur kerja | Terdistribusi; tracing membutuhkan span ID agregat |
| **Penanganan Error** | Pemulihan global, failover terarah, restart deterministik | Retry lokal, compensating transactions (Saga Pattern) |
| **Skenario Ideal** | Batch processing, pipeline ETL/ELT, ML Training, RAG pipeline | Microservices async, reactive streaming, pemrosesan order |

---

## 3. Why It Matters: Masalah di Dunia Nyata & Kebutuhan Enterprise

Dalam arsitektur pipeline produksi skala petabyte dan sistem AI multi-agent, pendekatan tradisional berbasis *Cron Jobs* menghadirkan kelemahan sistemik yang dikenal sebagai **"Cron Hell"**:

1. **Temporal Coupling vs. State-based Dependency:** Cron hanya memicu proses berdasarkan waktu dinding (*wall-clock time*). Apabila sebuah upstream task mengalami pelambatan transmisi data (misal: ekstraksi data ERP melambat dari 10 menit menjadi 75 menit), cron downstream task akan tetap terpicu sesuai jadwal, membaca dataset parsial atau mengunci tabel database yang sedang diisi (*race condition*), berakibat pada korupsi data analitik.
2. **Ketiadaan Visibilitas Global & Idempotensi Gagal:** Saat pipeline 30-langkah mengalami kegagalan di langkah ke-18, skrip cron terisolasi tidak memiliki status lineage. Operator terpaksa me-run ulang pipeline dari langkah ke-1 secara manual, memicu duplikasi data, lonjakan biaya komputasi *warehouse*, atau inkonsistensi metriks agregasi.
3. **Resource Saturation & Cascading Outages:** Cron tidak mengenal *backpressure* atau manajemen *concurrency pool*. Jika ratusan cron tasks aktif bersamaan pada interval waktu umum (contoh: tengah malam), database transaksi dan cluster komputasi mengalami *thundering herd problem* yang memicu degradasi layanan.
4. **Auditability, Lineage, dan AI Reliability:** Model AI generatif dan sistem RAG enterprise membutuhkan asal-usul data (*provenance*) yang ketat. Jika vektor knowledge base diperbarui menggunakan data yang tidak tervalidasi atau tidak sinkron akibat pipeline yang terlewat, inferensi agent LLM menghasilkan halusinasi yang tidak dapat di-reproduksi atau di-debug.

Orkestrasi modern memisahkan **definisi dependensi** dari **jadwal eksekusi**, menggantikan asumsi berbasis waktu dengan transisi status berbasis relasi kausalitas data yang deterministik.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur engine orkestrasi skala enterprise terdiri dari komponen yang terisolasi dengan batas tanggung jawab yang tegas (*separation of concerns*):

```
+-------------------------------------------------------------------------------+
|                             CLIENT / USER SPACE                               |
|                                                                               |
|   +------------------------------------+   +------------------------------+   |
|   |   DAG Definitions (Python Code)    |   | CLI / REST API Client        |   |
|   +-----------------+------------------+   +--------------+---------------+   |
+---------------------|-------------------------------------|-------------------+
                      | Git-Sync / Dynamic Parse            | RPC / HTTP
                      v                                     v
+-------------------------------------------------------------------------------+
|                             ORCHESTRATION PLANE                               |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | API Server / Web Control Plane                                        |   |
|   | - Graph Validation (Cycle Detection)                                 |   |
|   | - DAG Metadata Serialization                                          |   |
|   | - Auth, RBAC & Lineage Explorer                                       |   |
|   +-----------------------------------+-----------------------------------+   |
|                                       |                                       |
|                                       v                                       |
|   +-----------------------------------------------------------------------+   |
|   | Orchestration Engine (Scheduler)                                      |   |
|   |                                                                       |   |
|   |  +------------------------+   Evaluate    +------------------------+  |   |
|   |  | Topological Sorter     | ------------> | State Reconciliation   |  |   |
|   |  | & Dependency Resolver  |               | Loop                   |  |   |
|   |  +------------------------+               +-----------+------------+  |   |
|   |                                                       |               |   |
|   |  +------------------------+                           | State Lock &  |   |
|   |  | Backoff & Retry Logic  |                           | Heartbeat     |   |
|   |  +------------------------+                           v               |   |
|   +-----------------------------------+----------+-----------------------+   |
|                                       |          ^                            |
+---------------------------------------|----------|----------------------------+
                                        |          |
                   Enqueues Ready Tasks |          | State Sync & Leases
                                        v          v
                +-----------------------------------------------+
                | Distributed Metadata Store (PostgreSQL / RAFT)|
                | - DAG Runs, Task Instances, Audit Logs        |
                +-----------------------------------------------+
                                        |
                 Task Dispatch (Push)   v   Task Consumption (Pull)
+-------------------------------------------------------------------------------+
|                            EXECUTION / WORKER PLANE                           |
|                                                                               |
|       +---------------------------------------------------------------+       |
|       | Distributed Message Broker (RabbitMQ / Redis Streams / NATS)  |       |
|       +---+---------------------------+---------------------------+---+       |
|           |                           |                           |           |
|           v                           v                           v           |
|   +---------------+           +---------------+           +---------------+   |
|   | Worker Node 1 |           | Worker Node 2 |           | Worker Node 3 |   |
|   | (Executor)    |           | (Executor)    |           | (Executor)    |   |
|   |  - Task A     |           |  - Task B     |           |  - Task C     |   |
|   |  - Context    |           |  - Context    |           |  - Context    |   |
|   +-------+-------+           +-------+-------+           +-------+-------+   |
|           |                           |                           |           |
+-----------|---------------------------|---------------------------|-----------+
            +---------------------------+---------------------------+
                                        | Read/Write Execution Data
                                        v
                       +----------------------------------+
                       | Data Plane (S3, Snowflake, Trino)|
                       +----------------------------------+
```

### Penjelasan Komponen:

1. **DAG Compiler/Parser:** Menerjemahkan definisi kode deklaratif menjadi struktur data memory graph, memverifikasi ketiadaan siklus dan mendekomposisi dependensi.
2. **Metadata Store:** Database persisten (umumnya ACID-compliant RDBMS) yang menyimpan riwayat *Run Instance*, status node, concurrency lock, dan metrik operasional.
3. **Scheduler & State Reconciler:** Komponen *heartbeat loop* yang secara kontinu mengevaluasi dependensi graf. Jika suatu node memenuhi syarat (seluruh upstream dependencies berstatus `SUCCESS`), node dipindahkan ke state `QUEUED`.
4. **Message Broker / Queue:** Decoupling layer yang mendistribusikan task dari scheduler ke execution workers untuk mencegah starvation dan overload.
5. **Distributed Worker Pool:** Node komputasi elastis yang mengambil task payload, mengisolasi runtime env (via virtualenv/container), mengeksekusi logika atomik, dan mengembalikan return code beserta sinyal heartbeat secara periodik.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 1. Algoritma Pengurutan Topologis: Pendekatan Kahn

Orchestrator memanfaatkan algoritma Kahn untuk memvalidasi graf dan menghasilkan urutan eksekusi yang valid:

1. Hitung *in-degree* (derajat masuk) untuk setiap node $v \in V$.
2. Inisialisasi antrean $Q$ dan masukkan semua node dengan $\text{in-degree}(v) = 0$.
3. Inisialisasi list kosong $L$ (berisi hasil pengurutan).
4. Selama $Q$ tidak kosong:
   - Ambil node $u$ dari $Q$, tambahkan $u$ ke $L$.
   - Untuk setiap tetangga terarah downstream $w$ di mana $(u, w) \in E$:
     - Kurangi $\text{in-degree}(w)$ sebanyak 1.
     - Jika $\text{in-degree}(w) == 0$, masukkan $w$ ke dalam $Q$.
5. Jika jumlah node yang diekstraksi ke dalam $L$ sama dengan $|V|$, graf valid dan $L$ merepresentasikan urutan eksekusi yang layak. Jika $|L| \neq |V|$, graf mengandung sedikitnya satu siklus (**siklus terdeteksi**), dan orkestrasi harus dibatalkan.

### 2. State Machine Lifecycle

Setiap unit komputasi (*Task Instance*) diorkestrasi menggunakan mesin status ketat (*Deterministic Finite Automaton*):

```
       +--------------------+
       |      PENDING       |
       +---------+----------+
                 |
                 | Upstream All SUCCESS
                 v
       +--------------------+
       |       QUEUED       |<--------------------+
       +---------+----------+                     |
                 |                                |
                 | Worker Claims Task             | Retry within Max Limit
                 v                                |
       +--------------------+                     |
       |      RUNNING       |                     |
       +----+----------+----+                     |
            |          |                          |
   Execution|          | Exception /              |
   Success  |          | Non-zero Exit            |
            |          +--------------------------+
            |          |
            |          | Retries Exhausted
            v          v
   +----------+   +----------+
   | SUCCESS  |   |  FAILED  |
   +----------+   +----+-----+
                       |
                       | Propagate Downstream
                       v
              +------------------+
              | UPSTREAM_FAILED  |
              +------------------+
```

- **Transisi `UPSTREAM_FAILED`:** Terjadi secara deterministik tanpa perlu menjalankan task downstream. Jika node $u$ berstatus `FAILED`, setiap node turunan $v$ yang memiliki jalur kausal $u \leadsto v$ secara transitif dialihkan ke status `UPSTREAM_FAILED` (kecuali didefinisikan aturan pengabaian kegagalan/trigger rules khusus seperti `ALL_DONE` atau `ONE_SUCCESS`).

### 3. Jaminan Idempotensi dan State Reconciliation

Orkestrasi modern mematuhi prinsip **idempotensi komputasi**:

$$f(f(x)) = f(x)$$

Menjalankan task instance yang sama secara berulang dengan konteks partisi waktu yang identik harus menghasilkan output state data yang seragam tanpa *side effect* ganda. Implementasi teknis mencakup:

- **Idempotency Keys:** Setiap task execution instance diinjeksi token unik berbasis hash:
  
  $$\text{Key} = \text{HMAC-SHA256}(\text{DAG\_ID} + \text{TASK\_ID} + \text{EXECUTION\_DATE} + \text{RUN\_ID})$$
  
- **Atomic Operations:** Task menuliskan data ke staging table temporal atau S3 temporary path, lalu melakukan swap atomik (`ALTER TABLE ... SWAP WITH` atau `OVERWRITE PARTITION`) saat task beralih ke state `SUCCESS`.

### 4. Backfilling Paradigms

Backfill adalah proses mengeksekusi pipeline pada rentang parameter historis:

- **Logical Date vs. Execution Date:** Scheduler membedakan waktu fisik eksekusi (*wall-clock interval*) dengan parameter data yang diproses (*data interval window*). Task yang berjalan pada `2024-01-02` dapat mengolah window data `[2024-01-01T00:00:00, 2024-01-02T00:00:00)` secara konsisten.
- **Dynamic Task Slicing:** Scheduler memecah interval tahunan menjadi unit harian yang dijalankan secara paralel dengan pembatasan *max active runs* untuk menghindari pemadaman database target.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi **Orchestration Engine Core** mandiri (*zero-external-dependency framework*) yang mencakup:
- DAG definition dengan Kahn's Algorithm Cycle Detection.
- Dependency Resolution & Dynamic Topological Execution.
- Asynchronous Task Execution Engine dengan *State Machine*.
- Mekanisme Retry otomatis dengan *Exponential Backoff & Jitter*.
- Concurrency limiting menggunakan Semaphore.

```python
"""
Enterprise-Grade DAG Orchestration Core Engine
Designed with strict typing, deterministic state reconciliation,
Kahn's cycle validation, and concurrent asynchronous execution.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

# Configure high-precision structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DAGOrchestrator")


class TaskState(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UPSTREAM_FAILED = "UPSTREAM_FAILED"
    SKIPPED = "SKIPPED"


class CyclicDependencyError(Exception):
    """Raised when the graph validation encounters a closed cycle."""
    pass


class TaskExecutionError(Exception):
    """Raised when task execution fails and max retries are exhausted."""
    pass


@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    max_delay_seconds: float = 30.0
    jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (self.backoff_factor ** attempt)
        )
        if self.jitter:
            delay = delay * (0.5 + random.random() / 2.0)
        return delay


@dataclass
class TaskContext:
    dag_id: str
    run_id: str
    task_id: str
    logical_date: datetime
    attempt: int
    metadata: Dict[str, Any] = field(default_factory=dict)


TaskCallable = Callable[[TaskContext], Coroutine[Any, Any, Any]]


class TaskNode:
    def __init__(
        self,
        task_id: str,
        action: TaskCallable,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self.task_id = task_id
        self.action = action
        self.retry_policy = retry_policy or RetryPolicy()
        self.upstream: Set[TaskNode] = set()
        self.downstream: Set[TaskNode] = set()
        self.state: TaskState = TaskState.PENDING
        self.result: Any = None
        self.error: Optional[Exception] = None

    def set_downstream(self, task: TaskNode) -> None:
        self.downstream.add(task)
        task.upstream.add(self)

    def set_upstream(self, task: TaskNode) -> None:
        self.upstream.add(task)
        task.downstream.add(self)

    def __rshift__(self, other: TaskNode) -> TaskNode:
        """Enables bitshift syntax: task_a >> task_b"""
        self.set_downstream(other)
        return other

    def __lshift__(self, other: TaskNode) -> TaskNode:
        """Enables bitshift syntax: task_b << task_a"""
        self.set_upstream(other)
        return other

    def __repr__(self) -> str:
        return f"<TaskNode: {self.task_id} [{self.state.value}]>"


class DAG:
    def __init__(self, dag_id: str, max_concurrency: int = 4) -> None:
        self.dag_id = dag_id
        self.max_concurrency = max_concurrency
        self.nodes: Dict[str, TaskNode] = {}

    def add_task(self, task: TaskNode) -> None:
        if task.task_id in self.nodes:
            raise ValueError(f"Task {task.task_id} already registered in DAG {self.dag_id}.")
        self.nodes[task.task_id] = task

    def validate_acyclic(self) -> List[str]:
        """
        Validates graph using Kahn's Algorithm for Topological Sort.
        Returns topological ordering if valid; raises CyclicDependencyError if cyclic.
        Complexity: O(|V| + |E|)
        """
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        for node in self.nodes.values():
            for downstream in node.downstream:
                in_degree[downstream.task_id] += 1

        queue: List[str] = [n_id for n_id, deg in in_degree.items() if deg == 0]
        topological_order: List[str] = []

        while queue:
            curr_id = queue.pop(0)
            topological_order.append(curr_id)
            for downstream in self.nodes[curr_id].downstream:
                in_degree[downstream.task_id] -= 1
                if in_degree[downstream.task_id] == 0:
                    queue.append(downstream.task_id)

        if len(topological_order) != len(self.nodes):
            cyclic_candidates = [
                n_id for n_id, deg in in_degree.items() if deg > 0
            ]
            raise CyclicDependencyError(
                f"Siklus terdeteksi pada graf DAG '{self.dag_id}'. "
                f"Node yang terisolasi dalam siklus: {cyclic_candidates}"
            )

        return topological_order


class OrchestrationEngine:
    def __init__(self, dag: DAG) -> None:
        self.dag = dag
        self.dag.validate_acyclic()
        self.semaphore = asyncio.Semaphore(dag.max_concurrency)

    async def _execute_task_with_retry(
        self, node: TaskNode, context: TaskContext
    ) -> None:
        policy = node.retry_policy
        for attempt in range(policy.max_retries + 1):
            context.attempt = attempt
            try:
                node.state = TaskState.RUNNING
                logger.info(
                    f"Executing task: '{node.task_id}' (RunID: {context.run_id}, Attempt: {attempt + 1})"
                )
                start_time = time.monotonic()
                
                # Execute underlying business logic coroutine
                node.result = await node.action(context)
                
                duration = time.monotonic() - start_time
                node.state = TaskState.SUCCESS
                logger.info(
                    f"Task '{node.task_id}' succeeded within {duration:.3f}s"
                )
                return
            except Exception as exc:
                node.error = exc
                if attempt < policy.max_retries:
                    delay = policy.calculate_delay(attempt)
                    logger.warning(
                        f"Task '{node.task_id}' failed on attempt {attempt + 1}. "
                        f"Retry scheduled in {delay:.2f}s. Cause: {str(exc)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    node.state = TaskState.FAILED
                    logger.error(
                        f"Task '{node.task_id}' permanently failed after {attempt + 1} attempts. "
                        f"Terminating branch."
                    )

    def _propagate_upstream_failure(self, root_failed_node: TaskNode) -> None:
        """
        Recursively marks downstream dependencies as UPSTREAM_FAILED.
        """
        stack = list(root_failed_node.downstream)
        while stack:
            curr = stack.pop()
            if curr.state not in (TaskState.FAILED, TaskState.UPSTREAM_FAILED):
                curr.state = TaskState.UPSTREAM_FAILED
                logger.warning(
                    f"Task '{curr.task_id}' marked as UPSTREAM_FAILED due to parent failure."
                )
                stack.extend(curr.downstream)

    async def run(self, run_id: Optional[str] = None) -> Dict[str, TaskState]:
        run_id = run_id or f"run_{int(time.time())}"
        logical_date = datetime.now(timezone.utc)
        logger.info(f"Initializing DAG Run '{self.dag.dag_id}' [Run ID: {run_id}]")

        # Track active async task primitives mapped by task_id
        running_tasks: Dict[str, asyncio.Task] = {}
        completed_nodes: Set[str] = set()

        async def runner_wrapper(node: TaskNode) -> None:
            async with self.semaphore:
                ctx = TaskContext(
                    dag_id=self.dag.dag_id,
                    run_id=run_id,
                    task_id=node.task_id,
                    logical_date=logical_date,
                    attempt=0,
                )
                await self._execute_task_with_retry(node, ctx)

        # State reconciliation event loop
        while len(completed_nodes) < len(self.dag.nodes):
            for task_id, node in self.dag.nodes.items():
                if node.state != TaskState.PENDING:
                    continue

                # Check upstream conditions
                if any(up.state == TaskState.FAILED or up.state == TaskState.UPSTREAM_FAILED for up in node.upstream):
                    node.state = TaskState.UPSTREAM_FAILED
                    self._propagate_upstream_failure(node)
                    completed_nodes.add(task_id)
                    continue

                if all(up.state == TaskState.SUCCESS for up in node.upstream):
                    node.state = TaskState.QUEUED
                    logger.debug(f"Queueing task '{task_id}'. Ready for dispatch.")
                    task_coro = asyncio.create_task(runner_wrapper(node))
                    running_tasks[task_id] = task_coro

            if not running_tasks:
                # Break condition: all pending tasks evaluated or cascading failure triggered
                break

            # Await any task completion to advance the state loop
            done, _ = await asyncio.wait(
                running_tasks.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # Evict completed futures and sync states
            finished_ids = [
                t_id for t_id, f in running_tasks.items() if f in done
            ]
            for t_id in finished_ids:
                del running_tasks[t_id]
                node = self.dag.nodes[t_id]
                completed_nodes.add(t_id)

                if node.state == TaskState.FAILED:
                    self._propagate_upstream_failure(node)

        # Build execution summary
        summary = {node_id: node.state for node_id, node in self.dag.nodes.items()}
        logger.info(f"DAG Run Finished. Final status breakdown: {summary}")
        return summary
```

---

## 7. Edge Cases & Failure Modes

### 1. Dynamic Cycles During Runtime Expansion
- **Deskripsi Masalah:** Graph generator dinamis (*dynamic task mapping*) yang memetakan data partisi secara runtime dapat menambahkan dependensi yang tidak sengaja menciptakan siklus tertutup jika dependensi downstream merujuk kembali ke metadata dinamis upstream.
- **Deteksi:** Algoritma deteksi siklus statis gagal mendeteksinya saat bootstrap.
- **Mitigasi:** Eksekusi validasi siklus sekunder pasca ekspansi task (*post-expansion cycle validation*) sebelum task dinamis dipindahkan ke state `QUEUED`. Terapkan immutabilitas struktural graph setelah inisialisasi.

### 2. Zombie Tasks & Split-Brain Execution
- **Deskripsi Masalah:** Worker yang menjalankan task mengalami *network partition* atau *kernel OOM (Out-Of-Memory)*. Heartbeat berhenti dikirim ke scheduler. Scheduler menganggap task hangus (*evicted*) lalu menjadwalkan ulang task yang sama ke Worker lain. Worker pertama pulih secara tak terduga dan tetap menuliskan state.
- **Deteksi:** Mutasi data ganda pada storage target atau anomali duplikasi baris database (*row multiplication*).
- **Mitigasi:** Terapkan **fencing tokens** (nomor sequence monoton yang meningkat secara linear). Task menulis ke data store dengan syarat token worker harus $\ge$ token database saat ini. Alternatif lain: gunakan database lock berbasis waktu sewa (*leased locks*) dengan TTL ketat.

### 3. Starvation pada Fan-Out Graf Luas
- **Deskripsi Masalah:** Pola DAG *fan-out* masif (1 upstream task memicu 10.000 downstream tasks identik) dapat menghabiskan seluruh kapasitas resource queue (*broker starvation*). Task dari DAG prioritas tinggi lain terblokir total (*noisy neighbor*).
- **Deteksi:** Peningkatan metrik *Queue Latency* secara global pada broker messages.
- **Mitigasi:** Batasi konkurensi di level DAG (*per-DAG concurrency limits*) dan terapkan **fair-share priority queues** pada message broker.

### 4. Poison Pill Data & Non-Determinism Retry
- **Deskripsi Masalah:** Skema downstream mengasumsikan input data valid. Upstream menghasilkan payload korup yang lolos eksekusi dasar (contoh: format tanggal bervariasi). Retry eksponensial di downstream akan berulang kali gagal hingga batas habis, menghabiskan resource komputasi secara sia-sia.
- **Mitigasi:** Terapkan pemisahan antara *transient error* (network timeout, rate limit -> izinkan retry) vs. *deterministic error* (schema violation, zero-division, syntax parsing -> langsung alihkan ke `FAILED` dan isolasi ke **Dead Letter Queue (DLQ)**).

---

## 8. Trade-offs & Alternatif Solusi

| Kriteria | Apache Airflow | Dagster | Temporal | Custom Micro-Engine (Section 6) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Abstraksi** | **Task-Centric:** Berfokus pada urutan komputasi. Mengabaikan transfer data state langsung. | **Asset-Centric:** Berfokus pada artefak data yang dihasilkan (SDA: Software-Defined Assets). | **Workflow-as-Code:** Berfokus pada status execution thread, event-driven, deterministik. | **Lightweight Core:** Dirancang khusus untuk embedded, edge, atau in-memory processing. |
| **Penyimpanan State** | Metadata DB (Postgres/MySQL) via scheduler state scan interval. | Event log append-only + Instance database. | Event Sourcing terdistribusi (Cassandra, Postgres) via temporal clusters. | In-Memory (atau serializable ke KV store lokal). |
| **Lineage & Observabilitas** | Perlu plugin tambahan (OpenLineage). | *Built-in* secara native. Menyimpan metadata partisi data. | Berorientasi trace microservice, bukan data cataloging. | Didefinisikan secara manual via metadata context passing. |
| **Overhead Operasional** | **Sangat Tinggi:** Memerlukan Webserver, Scheduler, Broker, Worker daemon, Metadata DB. | **Moderat:** Memerlukan Daemon, Webserver, Storage instance. | **Tinggi:** Perlu Cluster Temporal + Cassandra/Postgres + App Workers. | **Zero:** Menempel (*embedded*) di dalam process runtime aplikasi. |
| **Beban Kerja Ideal** | Batch processing skala enterprise, ELT data warehouse tradisional. | Modern data platform, pipeline machine learning, feature store orchestration. | Long-running business processes, transkripsi LLM multi-step, saga transactions. | CLI tool internal, microservices, pipeline AI-agent mandiri. |

---

## 9. Best Practices & Standar Industri

### 1. Deterministic Runtime Isolation
Pemisahan tegas antara **Orchestration Layer** dan **Execution Layer**. Jangan pernah menjalankan transformasi komputasi data berat (misal: ekstraksi ratusan juta baris via Pandas) di dalam proses internal engine/scheduler. Scheduler hanya bertindak sebagai pengatur lalu lintas; delegasikan eksekusi sebenarnya ke *compute engines* eksternal seperti Databricks, Snowflake, Apache Spark, atau Kubernetes Pods (`KubernetesPodOperator`).

### 2. Idempotensi dengan Pola Write-Audit-Publish (WAP)
Hindari direct overwrite atau append langsung pada production table:
1. **Write:** Tulis hasil data ke staging namespace/partition unik berbasis `run_id`.
2. **Audit:** Jalankan task validasi kualitas data (contoh: mengecek null-rate, skema, batasan rentang menggunakan Great Expectations atau dbt test).
3. **Publish:** Lakukan swap partisi atomik ke tabel utama produksi jika validasi lulus. Jika gagal, hapus staging table dan hentikan downstream pipeline.

### 3. Konfigurasi Observabilitas Berstandar OpenTelemetry
Setiap transisi status graph harus memancarkan trace events. Task ID dipetakan sebagai **Span ID**, dan DAG run instance dipetakan sebagai **Trace ID**. Semua log worker harus distrukturkan dalam format JSON dengan menyertakan context attributes: `run_id`, `dag_id`, `task_id`, `logical_date`, dan `retry_attempt`.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan membangun pipeline ekstraksi dan pengayaan data AI Feature Store berbasis DAG Engine yang telah dibuat pada Section 6. Anda akan mengimplementasikan deteksi kegagalan, mitigasi siklus, dan idempotensi.

### Langkah 1: Persiapan Environment
Simpan implementasi engine dari Bagian 6 ke dalam file bernama `core_orchestrator.py`. Buat script lab baru `pipeline_lab.py`:

```python
import asyncio
import logging
from core_orchestrator import DAG, TaskNode, OrchestrationEngine, TaskContext, CyclicDependencyError

logger = logging.getLogger("PipelineLab")

# 1. Definisikan Task Actions (Unit Komputasi Atomik)
async def fetch_customer_data(ctx: TaskContext) -> dict:
    logger.info(f"[{ctx.task_id}] Mengunduh data transaksi pelanggan...")
    await asyncio.sleep(0.5)
    return {"rows": 1500, "status": "RAW"}

async def clean_transactions(ctx: TaskContext) -> dict:
    logger.info(f"[{ctx.task_id}] Membersihkan format null & deduplikasi baris...")
    await asyncio.sleep(0.4)
    return {"rows": 1495, "status": "CLEAN"}

async def extract_fraud_signals(ctx: TaskContext) -> dict:
    logger.info(f"[{ctx.task_id}] Mengisolasi sinyal transaksi mencurigakan...")
    await asyncio.sleep(0.3)
    return {"signals_detected": 12}

async def generate_vector_embeddings(ctx: TaskContext) -> dict:
    logger.info(f"[{ctx.task_id}] Memanggil LLM API untuk komputasi teks embedding...")
    await asyncio.sleep(0.6)
    return {"embeddings_count": 1495, "dim": 1536}

async def publish_feature_store(ctx: TaskContext) -> str:
    logger.info(f"[{ctx.task_id}] Memperbarui Feature Store produksi secara atomik...")
    await asyncio.sleep(0.2)
    return "SUCCESS_STORE_SYNC"
```

### Langkah 2: Membangun Struktur Dependensi & Eksekusi Sukses
Tambahkan blok orkestrasi berikut ke `pipeline_lab.py`:

```python
async def run_happy_path():
    logger.info("=== MENJALANKAN PIPELINE NORMAL ===")
    dag = DAG(dag_id="customer_feature_pipeline", max_concurrency=2)

    # Inisialisasi node
    t_fetch = TaskNode("fetch_customer_data", fetch_customer_data)
    t_clean = TaskNode("clean_transactions", clean_transactions)
    t_fraud = TaskNode("extract_fraud_signals", extract_fraud_signals)
    t_embed = TaskNode("generate_vector_embeddings", generate_vector_embeddings)
    t_publish = TaskNode("publish_feature_store", publish_feature_store)

    for t in [t_fetch, t_clean, t_fraud, t_embed, t_publish]:
        dag.add_task(t)

    # Konstruksi Dependensi:
    # fetch -> clean -> [fraud, embed] -> publish
    t_fetch >> t_clean
    t_clean >> t_fraud
    t_clean >> t_embed
    t_fraud >> t_publish
    t_embed >> t_publish

    engine = OrchestrationEngine(dag)
    results = await engine.run("run_prod_001")
    print(f"\nHasil Eksekusi Happy Path: {results}\n")

if __name__ == "__main__":
    asyncio.run(run_happy_path())
```

### Langkah 3: Pengujian Validasi Siklus (Cycle Detection Test)
Tambahkan dependensi ilegal (`t_publish >> t_fetch`) untuk menguji deteksi siklus Kahn:

```python
async def run_cyclic_path():
    logger.info("=== MENJALANKAN PENGUJIAN DEPENDENSI SIKLIK ===")
    dag = DAG(dag_id="cyclic_test_pipeline")

    node_a = TaskNode("Node_A", fetch_customer_data)
    node_b = TaskNode("Node_B", clean_transactions)
    dag.add_task(node_a)
    dag.add_task(node_b)

    # Membuat Siklus: A -> B -> A
    node_a >> node_b
    node_b >> node_a

    try:
        engine = OrchestrationEngine(dag)
        await engine.run("run_fail_cycle")
    except CyclicDependencyError as ex:
        logger.error(f"Siklus tertangkap dengan benar oleh algoritma Kahn: {ex}")

if __name__ == "__main__":
    asyncio.run(run_cyclic_path())
```

### Verifikasi Hasil & Kriteria Kelulusan:
1. **Happy Path:** Task `extract_fraud_signals` dan `generate_vector_embeddings` harus dieksekusi secara konkuren sesuai batas `max_concurrency`. Task `publish_feature_store` hanya boleh berjalan jika **kedua** task paralel tersebut berstatus `SUCCESS`.
2. **Cycle Test:** Engine harus menolak kompilasi DAG sebelum proses eksekusi dimulai dan mengeluarkan pesan `CyclicDependencyError`.
3. **State Consistency:** Semua task downstream dari task yang gagal sengaja harus berada pada status `UPSTREAM_FAILED` tanpa memicu pemanggilan worker. Output terminal mencerminkan log structured JSON/timestamped yang deterministik.