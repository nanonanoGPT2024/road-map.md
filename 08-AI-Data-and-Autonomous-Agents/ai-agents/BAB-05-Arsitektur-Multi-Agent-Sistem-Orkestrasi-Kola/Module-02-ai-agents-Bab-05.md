# BAB 05: Arsitektur Multi-Agent & Sistem Orkestrasi Kolaboratif
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Principal Engineer / Enterprise Architect diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Multi-Agent Sistem (MAS)** berskala enterprise menggunakan pola *Centralized Orchestration* (Supervisor-Worker), *Decentralized Choreography* (Peer-to-Peer Swarms), dan *Blackboard Pattern*.
- **Mengelola State Terdistribusi dan Konsistensi Konteks** antar-agen yang beroperasi secara asinkron menggunakan protokol event-driven dan shared state stores.
- **Mengeliminasi Kegagalan Kaskade (Cascading Failures)** melalui implementasi *circuit breakers*, *dead-letter queues* (DLQ), *token budgeting*, dan mekanisme konsensus terdistribusi.
- **Mengintegrasikan Observabilitas End-to-End** berbasis OpenTelemetry untuk melacak alur eksekusi, latensi, konsumsi token, dan divergensi penalaran (*reasoning divergence*) antar-agen.
- **Membangun Sistem Multi-Agent Siap Produksi** yang deterministik, memiliki batas kegagalan (*blast radius*) terisolasi, dan mendukung auditabilitas kepatuhan (*regulatory compliance*).

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Asynchronous Programming Modern**: Python `asyncio`, *event loops*, *tasks*, *semaphores*, dan *bounded queues*.
- **Distributed Systems Fundamentals**: *Event-Driven Architecture*, message brokers (Kafka/RabbitMQ), ACID vs. BASE, serta *eventual consistency*.
- **LLM Core Internals**: Mekanisme *context window*, *prompt caching*, struktur *embeddings*, *function calling/tool use schema* (OpenAI/Anthropic spec).
- **Data Engineering & Validation**: Pydantic V2, JSON Schema, *state machine modeling*.
- Telah menyelesaikan: **BAB-05 Module 01 - Dasar-Dasar Desain Multi-Agent System**.

---

### 3. Concept & Internal Architecture

Dalam lanskap enterprise, agen LLM tunggal (*monolithic agent*) gagal memenuhi standar produksi karena limitasi kognitif: *context bloat*, distorsi instruksi (*instruction drift*), dan ketidakmampuan mengisolasi hak akses alat (*least-privilege violation*). Modul ini membedah arsitektur internal dari sistem multi-agen tingkat lanjut.

```
                           +------------------------+
                           |  API Gateway / Ingress  |
                           +-----------+------------+
                                       |
                                       v
                     +------------------------------------+
                     |  Supervisor / Orchestrator Agent   |
                     |  - Intent Parser & Task Planner    |
                     |  - Global State Machine Manager    |
                     +---+--------------+--------------+--+
                         |              |              |
         +---------------+              |              +---------------+
         v                              v                              v
+-----------------+            +-----------------+            +-----------------+
| Analyst Agent   |            | Executor Agent  |            | Verifier Agent  |
| - Local Scratch |            | - Safe Sandbox  |            | - Rule-based &  |
| - Private Tools |            | - External APIs |            |   LLM Evaluator |
+--------+--------+            +--------+--------+            +--------+--------+
         |                              |                              |
         +-------------------+----------+------------------------------+
                             |
                             v
           +-----------------------------------+
           |    Distributed Blackboard / Bus   |
           |  (Redis Enterprise / Apache Kafka)|
           |  - Versioned Execution Context    |
           |  - Event Stream & State Machine   |
           +-----------------+-----------------+
                             |
                             v
           +-----------------------------------+
           | Observability: OpenTelemetry/O11y |
           | (Langfuse, Arize, Tracing, Metrics)|
           +-----------------------------------+
```

#### A. Taksonomi Pola Interaksi Agen
1. **Centralized Orchestration (Hub-and-Spoke / Supervisor-Worker)**:
   - Agen Supervisor mengurai *goal* global menjadi Dependency Graph (DAG - *Directed Acyclic Graph*).
   - Supervisor secara eksplisit mendelegasikan subtugas ke Worker, memantau *state transition*, dan mengumpulkan sintesis akhir.
   - *Failure Boundary*: Terpusat. Jika supervisor salah melakukan routing, seluruh alur kerja gagal.
2. **Decentralized Choreography (Peer-to-Peer / Autonomous Swarms)**:
   - Setiap agen bereaksi terhadap event di event bus bersama. Tidak ada koordinator tunggal.
   - Menggunakan format komunikasi berbasis *Agent Communication Language* (ACL) atau format terstruktur (JSON schema standar).
   - Membutuhkan kondisi terminasi berbasis konsensus (*quorum* atau verifikasi invarian) untuk mencegah *infinite execution loops*.
3. **Blackboard Architecture Pattern**:
   - Agen tidak berkomunikasi langsung satu sama lain. Komunikasi terjadi melalui shared state (*Blackboard*).
   - Agen spesialis bertindak sebagai *Knowledge Sources* (KS). Mereka terus mengamati Blackboard dan melakukan pembaruan status ketika prasyarat keahlian mereka terpenuhi.

#### B. Isolasi Konteks dan State Machine
Menggabungkan seluruh riwayat obrolan ke dalam setiap agen menyebabkan pemborosan token dan halusinasi. Arsitektur produksi membagi state menjadi tiga lapisan:
- **Ephemeral Scratchpad**: Memori privat milik agen lokal untuk penalaran *Chain-of-Thought* (CoT). Dihapus setelah subtugas selesai.
- **Shared Working Memory (State DAG)**: State struktural terdefinisi yang hanya menyimpan artefak valid (misal: JSON payload tervalidasi Pydantic) yang dapat diakses oleh agen terotorisasi.
- **Long-term Enterprise Memory**: Vector DB dan Graph DB yang diakses via Semantic Retrieval Augmented Generation (RAG) untuk validasi historis dan domain knowledge.

---

### 4. Why & What

| Dimensi | Single Monolithic Agent | Multi-Agent Orchestration (Enterprise) |
| :--- | :--- | :--- |
| **Token Efficiency** | Rendah. Konteks membengkak seiring bertambahnya percakapan dan instruksi alat. | Tinggi. Konteks dipecah secara modular; tiap agen hanya menerima token yang relevan. |
| **Security & RBAC** | Buruk. Satu agen memiliki semua kredensial alat (DB write, API eksternal, bash execution). | Granular. Tiap agen diisolasi dengan peran spesifik dan kredensial *least-privilege*. |
| **Maintainability** | Sulit di-debug. Prompt raksasa (*mega-prompt*) sangat rapuh terhadap perubahan kecil. | Modular. Tiap agen memiliki prompt terisolasi yang dapat di-*unit test* secara independen. |
| **Deterministic Control**| Probabilistik tinggi. Alur eksekusi sulit diprediksi jika menghadapi skenario kompleks. | Hybrid (Deterministik + Stokastik). State machine mengunci alur bisnis; LLM menangani penalaran lokal. |

---

### 5. How (Workflow Detail)

Siklus hidup orkestrasi terstandarisasi produksi mengikuti alur berikut:

1. **Ingress & Schema Enforcement**: Request masuk divalidasi skema payload-nya menggunakan Pydantic. Tidak ada *raw string* yang langsung diproses tanpa sanitasi.
2. **Task Decomposition & Graph Construction**: Supervisor memetakan *intent* pengguna ke dalam *execution plan* yang berbentuk DAG. Subtugas independen dijadwalkan secara paralel via `asyncio.gather`.
3. **Context Pruning & Sanitization**: Sebelum dikirim ke agen spesialis, konteks global dibersihkan dari informasi non-kritis menggunakan token-bucket budgeting.
4. **Execution & Sandboxed Tool Call**: Agen mengeksekusi sub-langkah. Eksekusi alat yang berdampak samping (*state-mutating operations*) harus melewati sandboxing dan *human-in-the-loop validation* (jika threshold risiko tinggi).
5. **Deterministic Verification**: Agen Verifikasi (*Critic/Auditor*) mengevaluasi output agen pekerja terhadap skema aturan ketat (deterministic rules & secondary LLM-as-a-judge).
6. **State Mutation & Convergence**: Jika diverifikasi lolos, Blackboard diperbarui secara atomik. Jika gagal, siklus mitigasi (*reflection loop*) dijalankan dengan batasan maksimum percobaan (*max retry boundary*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan sebuah **Tim Bedah Rumah Sakit Modern**. 
- Dokter Bedah Utama (**Supervisor**) tidak memegang semua instrumen dan tidak memonitor tekanan darah secara langsung. 
- Dokter Anestesi (**Analyst Agent**) memantau tanda-tanda vital secara terus-menerus.
- Perawat Instrumen (**Tool Execution Agent**) hanya bertugas menyediakan alat bedah steril sesuai permintaan.
- Dokter Residen Pengawas (**Verifier/Auditor Agent**) menghitung jumlah kassa dan instrumen sebelum dan sesudah operasi untuk menjamin tidak ada yang tertinggal.
- Papan Status Pasien (**Blackboard**) adalah representasi kebenaran mutlak (*single source of truth*) yang dapat dilihat oleh seluruh tim medis secara simultan.

#### Diagram Interaksi Detail (Sequence Architecture)

```
User/Client       Supervisor          Analyst Worker      Executor Worker        Blackboard (State)
    |                  |                    |                    |                       |
    |--- 1. Submit --->|                    |                    |                       |
    |    Complex Goal  |--- 2. Write Plan ---------------------------------------------->|
    |                  |                                                                 |
    |                  |--- 3. Delegate Subtask A ------>|                               |
    |                  |                    |-- 4. Query RAG                             |
    |                  |                    |-- 5. Analyze                               |
    |                  |                    |-- 6. Write Result A ---------------------->|
    |                  |<-- 7. Task A Done -|                                            |
    |                  |                                                                 |
    |                  |--- 8. Delegate Subtask B (with Result A Context) --------------->|
    |                  |                                         |-- 9. Mutate Ext Sys   |
    |                  |                                         |-- 10. Write Result B->|
    |                  |<-- 11. Task B Done ---------------------|                       |
    |                  |                                                                 |
    |                  |--- 12. Consolidate Final State <--------------------------------|
    |<-- 13. Response -|
```

---

### 7. Code Implementations (Production-Grade)

Berikut adalah implementasi Multi-Agent Orchestrator asinkron menggunakan Python modern (3.11+). Kode ini menerapkan **Supervisor-Worker Pattern**, **Pydantic Structural Enforcement**, **Isolated Contexts**, dan **Exponential Backoff Resilience**.

#### A. Domain State & Protocols

```python
# state_models.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentRole(str, Enum):
    SUPERVISOR = "supervisor"
    DATA_ANALYST = "data_analyst"
    SECURITY_AUDITOR = "security_auditor"
    OUTPUT_SYNTHESIZER = "output_synthesizer"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class AgentTask(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    task_id: str
    assigned_to: AgentRole
    instruction: str
    context_payload: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3


class AgentResult(BaseModel):
    task_id: str
    author: AgentRole
    status: ExecutionStatus
    data: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_ms: float
    token_usage: int


class GlobalState(BaseModel):
    workflow_id: str
    initiator: str
    original_objective: str
    shared_artifacts: Dict[str, Any] = Field(default_factory=dict)
    task_history: List[AgentResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_halted: bool = False
```

#### B. Mock LLM Client & Specialized Workers

```python
# agents.py
import asyncio
import time
import random
from typing import Dict, Any
from state_models import AgentRole, AgentTask, AgentResult, ExecutionStatus


class BaseAgent:
    def __init__(self, role: AgentRole):
        self.role = role

    async def execute(self, task: AgentTask) -> AgentResult:
        raise NotImplementedError


class DataAnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.DATA_ANALYST)

    async def execute(self, task: AgentTask) -> AgentResult:
        start_time = time.perf_counter()
        query = task.context_payload.get("query", "")
        
        # Simulasi latensi pemrosesan dan penalaran LLM
        await asyncio.sleep(0.4)
        
        # Logika analisis domain: Validasi integritas data
        if not query:
            return AgentResult(
                task_id=task.task_id,
                author=self.role,
                status=ExecutionStatus.FAILED,
                data={},
                error_message="Query parameter is missing in context.",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                token_usage=50
            )

        extracted_metrics = {
            "query_analyzed": query,
            "anomalies_detected": 0,
            "metrics": {"latency_p99": 142.5, "error_rate": 0.0012},
            "status": "HEALTHY"
        }
        
        return AgentResult(
            task_id=task.task_id,
            author=self.role,
            status=ExecutionStatus.COMPLETED,
            data=extracted_metrics,
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            token_usage=320
        )


class SecurityAuditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentRole.SECURITY_AUDITOR)

    async def execute(self, task: AgentTask) -> AgentResult:
        start_time = time.perf_counter()
        data_to_audit = task.context_payload.get("data_to_audit", {})
        
        await asyncio.sleep(0.3)
        
        # Validasi keamanan: Audit kebocoran kredensial atau parameter berbahaya
        error_rate = data_to_audit.get("metrics", {}).get("error_rate", 1.0)
        if error_rate > 0.05:
            return AgentResult(
                task_id=task.task_id,
                author=self.role,
                status=ExecutionStatus.REJECTED,
                data={"verdict": "SECURITY_ALERT_HIGH_ERROR_SPIKE"},
                error_message="High anomaly threshold violated.",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                token_usage=180
            )

        return AgentResult(
            task_id=task.task_id,
            author=self.role,
            status=ExecutionStatus.COMPLETED,
            data={"compliance_passed": True, "pci_dss_cleared": True},
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            token_usage=210
        )
```

#### C. Enterprise Supervisor Engine (Orchestrator Core)

```python
# orchestrator.py
import asyncio
import logging
import uuid
import time
from typing import Dict
from state_models import GlobalState, AgentRole, AgentTask, AgentResult, ExecutionStatus
from agents import BaseAgent, DataAnalystAgent, SecurityAuditorAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
logger = logging.getLogger("EnterpriseOrchestrator")


class OrchestratorEngine:
    def __init__(self):
        self.workers: Dict[AgentRole, BaseAgent] = {
            AgentRole.DATA_ANALYST: DataAnalystAgent(),
            AgentRole.SECURITY_AUDITOR: SecurityAuditorAgent(),
        }

    async def _execute_with_retry(self, worker: BaseAgent, task: AgentTask) -> AgentResult:
        retries = 0
        backoff_base = 0.2
        
        while retries <= task.max_retries:
            try:
                result = await worker.execute(task)
                if result.status == ExecutionStatus.COMPLETED:
                    return result
                if result.status == ExecutionStatus.REJECTED:
                    # Jangan retry jika domain logic menolak secara eksplisit
                    logger.warning(f"Task {task.task_id} ditolak secara eksplisit oleh {worker.role}.")
                    return result
                
                logger.warning(f"Task {task.task_id} gagal. Percobaan {retries + 1}/{task.max_retries}. Error: {result.error_message}")
            except Exception as exc:
                logger.error(f"Sistem error pada worker {worker.role}: {str(exc)}")
                
            retries += 1
            if retries <= task.max_retries:
                await asyncio.sleep(backoff_base * (2 ** retries))

        return AgentResult(
            task_id=task.task_id,
            author=worker.role,
            status=ExecutionStatus.FAILED,
            data={},
            error_message="Exceeded maximum retry threshold.",
            execution_time_ms=0.0,
            token_usage=0
        )

    async def run_workflow(self, objective: str, query: str) -> GlobalState:
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        state = GlobalState(
            workflow_id=workflow_id,
            initiator="Enterprise-Core-Gateway",
            original_objective=objective
        )
        
        logger.info(f"Memulai eksekusi alur kerja [{workflow_id}] - Objective: {objective}")

        # Langkah 1: Subtugas Data Analyst
        analyst_task = AgentTask(
            task_id=f"tsk-{uuid.uuid4().hex[:6]}",
            assigned_to=AgentRole.DATA_ANALYST,
            instruction="Analisis metrik operasional data stream.",
            context_payload={"query": query}
        )
        
        analyst_result = await self._execute_with_retry(
            self.workers[AgentRole.DATA_ANALYST], analyst_task
        )
        state.task_history.append(analyst_result)

        if analyst_result.status != ExecutionStatus.COMPLETED:
            logger.error(f"Workflow [{workflow_id}] berhenti: Kegagalan pada Data Analyst.")
            state.is_halted = True
            return state

        # Modifikasi state Blackboard secara terkontrol
        state.shared_artifacts["analyst_metrics"] = analyst_result.data

        # Langkah 2: Subtugas Security Auditor (Membutuhkan data dari output analis)
        auditor_task = AgentTask(
            task_id=f"tsk-{uuid.uuid4().hex[:6]}",
            assigned_to=AgentRole.SECURITY_AUDITOR,
            instruction="Validasi integritas metrik dan lakukan audit kepatuhan.",
            context_payload={"data_to_audit": state.shared_artifacts["analyst_metrics"]}
        )

        auditor_result = await self._execute_with_retry(
            self.workers[AgentRole.SECURITY_AUDITOR], auditor_task
        )
        state.task_history.append(auditor_result)

        if auditor_result.status != ExecutionStatus.COMPLETED:
            logger.error(f"Workflow [{workflow_id}] ditandai tidak aman atau gagal oleh Auditor.")
            state.is_halted = True
            return state

        state.shared_artifacts["security_audit"] = auditor_result.data
        logger.info(f"Alur kerja [{workflow_id}] berhasil diselesaikan secara deterministik.")
        
        return state


if __name__ == "__main__":
    async def main():
        engine = OrchestratorEngine()
        final_state = await engine.run_workflow(
            objective="Audit Performa Infrastruktur Core Banking Kuartal 4",
            query="SELECT * FROM core_banking_logs WHERE region='apac'"
        )
        print("\n--- HASIL EKSEKUSI WORKFLOW ---")
        print(f"Workflow ID : {final_state.workflow_id}")
        print(f"Is Halted   : {final_state.is_halted}")
        print(f"Total Steps : {len(final_state.task_history)}")
        total_tokens = sum(step.token_usage for step in final_state.task_history)
        print(f"Token Digunakan: {total_tokens}")
        print(f"Artifacts   : {final_state.shared_artifacts}")

    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Domain: Pemrosesan Klaim Asuransi Multi-Tier Otomatis (Global InsurTech)
- **Konteks**: Sistem pemrosesan klaim asuransi kesehatan menangani lebih dari 150.000 klaim per hari. Sistem lama yang menggunakan pendekatan *single-agent monolithic* mengalami kegagalan fatal: token exhaustion saat membaca berkas rekam medis yang tebal, serta ketidakmampuan membuktikan alasan penolakan secara hukum (*unexplainable decisions*).
- **Arsitektur Multi-Agent Baru**:
  1. **Triage Agent**: Menerima dokumen PDF/OCR klaim, melakukan klasifikasi jenis klaim, dan mengekstrak entitas medis (ICD-10, CPT codes).
  2. **Policy Verification Agent**: Menghubungi Core Database via gRPC untuk memeriksa polis aktif pemegang asuransi, batasan plafon, dan masa tunggu (*waiting period*).
  3. **Fraud Detection Agent**: Membaca grafik riwayat klaim via Graph RAG untuk mendeteksi *phantom billing* atau pola klaim berulang antar-fasilitas kesehatan.
  4. **Adjudication Arbiter Agent**: Mengumpulkan temuan dari ketiga agen di atas pada shared state engine (Blackboard), menjalankan formula deterministik penentuan klaim, dan menghasilkan berkas putusan hukum.
- **Hasil Metrik Produksi**:
  - **Penurunan Latensi**: Dari rata-rata 42 detik per klaim menjadi 8,4 detik (karena proses verifikasi polis dan fraud berjalan konkuren via DAG).
  - **Efisiensi Biaya Token**: Biaya token menurun sebesar **64%** berkat pemisahan konteks instruksi (tidak memuat seluruh manual underwriting ke tiap worker).
  - **Tingkat Akurasi Keputusan**: Keberhasilan audit eksternal naik dari 89% ke 99,4% dengan rekam jejak audit (*audit trails*) per agen yang tersimpan permanen.

---

### 9. Trade-offs Matrix

| Dimensi Arsitektur | Centralized Orchestration (Supervisor) | Choreography Swarm (Peer-to-Peer) | Shared Blackboard Architecture |
| :--- | :--- | :--- | :--- |
| **Latensi Eksekusi** | Sedang. Terdapat overhead bolak-balik ke supervisor di tiap langkah. | Sangat Rendah. Pesan mengalir langsung antar agen via event bus. | Sedang-Tinggi. Tergantung pada frekuensi pooling/lock pada shared storage. |
| **Biaya Token (LLM)** | Menengah. Supervisor membutuhkan token tambahan untuk penalaran rute. | Rendah. Agen hanya menerima event terfilter. | Paling Hemat. Agen hanya membaca slice data spesifik dari Blackboard. |
| **Skalabilitas Sistem** | Terbatas pada kapasitas komputasi dan memori supervisor node. | Sangat Tinggi (Horizontal). Agen dapat di-scale sebagai Pod Kubernetes independen. | Sangat Tinggi. Skalabilitas bergantung langsung pada distributed storage (Redis/Kafka). |
| **Kompleksitas Debugging**| Rendah. Alur dapat dilacak secara linear melalui eksekusi supervisor. | Sangat Tinggi. Rawan *race conditions*, *deadlocks*, dan siklus tanpa akhir (*endless loops*). | Menengah. Memerlukan audit log yang ketat pada mutasi state blackboard. |
| **Blast Radius** | Terpusat. Kegagalan supervisor menghentikan seluruh sistem. | Terdistribusi. Satu agen mati tidak menghentikan agen non-dependen lainnya. | Terisolasi pada level state; dependensi fungsional tetap ada. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: The "Infinite Ping-Pong" Loop
- **Penyebab**: Dua agen (misal: Coder dan Reviewer) saling melempar output tanpa kondisi terminasi deterministik. Agen A meminta perbaikan minor, Agen B merespons dengan perbaikan yang memicu kritik lain dari Agen A.
- **Deteksi**: Lonjakan konsumsi token secara eksponensial dalam hitungan menit tanpa mutasi status DAG.
- **Solusi Rekayasa**: Terapkan **Hard Iteration Caps** dan **Convergence Scoring**:
  ```python
  if iteration_count >= MAX_PERMISSIBLE_ITERATIONS:
      logger.error("Divergensi terdeteksi: Ambang batas iterasi tercapai. Memaksa eskalasi ke Human-in-the-Loop.")
      state.escalate_to_human = True
      return state
  ```

#### Skenario 2: Context Poisoning / Cascading Hallucination
- **Penyebab**: Agen pertama menghasilkan data halusinasi semi-valid yang lolos sanitasi dasar. Agen kedua membaca halusinasi tersebut sebagai fakta absolut, memperparah kesalahan pada output akhir.
- **Deteksi**: Output akhir menyimpang secara faktual meskipun semua *tool-call* berstatus *success*.
- **Solusi Rekayasa**: Gunakan **Deterministic Assertions & Validator Agents**. Jangan biarkan agen hilir mempercayai *output text* tanpa verifikasi skema ketat menggunakan Pydantic validator dengan *regex constraint* dan *database foreign check verification*.

#### Skenario 3: Shared State Race Condition
- **Penyebab**: Dua agen mengeksekusi subtugas paralel dan menulis hasil ke Blackboard secara asinkron tanpa mekanisme penguncian (*locking*). State tertimpa (*overwritten*), menghilangkan artefak penting.
- **Solusi Rekayasa**: Gunakan **Optimistic Locking** atau **Distributed Mutex** (misal: Redis Redlock) pada tingkat field artefak state, bukan mengunci keseluruhan objek state.

---

### 11. Best Practices (Production Checklist)

- [ ] **State Immutability**: Terapkan immutability pada riwayat tugas; setiap modifikasi state harus menghasilkan versi baru (*append-only event store*).
- [ ] **Granular Least Privilege**: Setiap agen hanya memegang kredensial IAM/API yang mutlak diperlukan untuk perannya. Agen penulis laporan tidak boleh memiliki kredensial write ke database operasional.
- [ ] **Token Cap Budgeting**: Alokasikan kuota token maksimum untuk masing-masing agen per eksekusi alur kerja untuk mencegah pembengkakan biaya tak terduga.
- [ ] **Strict Timeout Handling**: Bungkus setiap pemanggilan agen dengan `asyncio.wait_for(timeout=X)` eksplisit.
- [ ] **OpenTelemetry Spans**: Setiap eksekusi agen wajib membuat child span baru dengan atribut `agent.role`, `task.id`, `token.prompt`, dan `token.completion`.
- [ ] **Deterministic Fallback**: Sediakan jalur degradasi graceful jika model AI eksternal mengalami degradasi performa (*downtime/high latency*).

---

### 12. Hands-on Practice

Buatlah direktori praktikum terisolasi pada environment lokal Anda:
`hands-on/m02/`

#### Struktur Proyek
```text
hands-on/m02/
├── pyproject.toml
├── state.py
├── workers.py
├── orchestrator.py
└── run_verification.py
```

#### Langkah Implementasi:
1. Inisialisasi environment menggunakan Poetry atau `uv`:
   ```bash
   mkdir -p hands-on/m02 && cd hands-on/m02
   python3 -m venv .venv && source .venv/bin/activate
   pip install pydantic==2.6.4
   ```
2. Buat file `state.py` dan salin struktur Pydantic dari Seksi 7.A. Tambahkan field baru `priority: int = 1` pada model `AgentTask`.
3. Buat file `workers.py` dari Seksi 7.B. Tambahkan satu worker baru: `ComplianceAgent` yang bertugas memverifikasi apakah region input sesuai dengan data residency rule (`['apac', 'emea', 'us']`).
4. Buat file `orchestrator.py` yang mengintegrasikan worker baru tersebut dalam urutan eksekusi serial setelah data didapatkan dari `DataAnalystAgent`.
5. Eksekusi alur pengujian melalui `run_verification.py` dengan skenario valid dan skenario anomali (misal: inject `error_rate = 0.12`). Amati bagaimana sirkuit orkestrator menghentikan eksekusi secara deterministik (*halt state*).

---

### 13. Exercises

#### Level Easy
Tambahkan validasi timeout eksplisit pada eksekusi masing-masing worker di file `orchestrator.py`. Jika sebuah worker tidak memberikan respons dalam waktu `500ms`, tandai status tugas tersebut sebagai `TIMEOUT_FAILED` dan pastikan eksekusi dialihkan ke fungsi fallback tanpa mematikan proses utama.

#### Level Medium
Implementasikan pola **Parallel Worker Fan-Out / Fan-In**. Ubah alur kerja agar `DataAnalystAgent` dan sebuah agen baru bernama `SentimentAnalysisAgent` dapat dieksekusi secara konkuren menggunakan `asyncio.gather`. Gabungkan kedua output tersebut ke dalam Blackboard sebelum `SecurityAuditorAgent` dieksekusi.

#### Level Hard
Rancang dan implementasikan mekanisme **Consensus Voting Protocol** (Quorum 2/3). Buat tiga agen independen `RiskEvaluator` dengan variasi prompt/temperatur yang berbeda. Orkestrator hanya boleh meloloskan transaksi keuangan jika minimal 2 dari 3 agen menyetujui transaksi tersebut (`VERDICT == 'APPROVED'`). Jika konsensus gagal dicapai, alirkan status ke antrean dead-letter queue (DLQ) virtual.

---

### 14. Enterprise Architectural Challenge

**Studi Kasus: Sistem Investigasi Penipuan Kartu Kredit Waktu-Nyata (Real-Time Credit Card Fraud Orchestration)**

#### Konteks & Permasalahan:
Sebuah bank multinasional membutuhkan sistem investigasi penipuan transaksi otomatis. Ketika transaksi berisiko tinggi terdeteksi oleh rule-engine konvensional, transaksi ditahan selama maksimal **1.8 detik**. Dalam rentang waktu ini, Multi-Agent System harus:
1. Menganalisis pola transaksi historis 30 hari terakhir.
2. Memeriksa profil geolokasi IP/Device Fingerprint saat ini terhadap lokasi fisik merchant.
3. Menjalankan model penalaran sintetis untuk memutuskan: `APPROVE`, `CHALLENGE_USER_WITH_MFA`, atau `BLOCK_AND_FREEZE`.

#### Batasan Arsitektur:
- **Latensi Maksimum P99**: 1.500 ms (termasuk total inferensi LLM dan I/O jaringan).
- **Hard SLA**: Jika sistem melebihi 1.8 detik, transaksi secara aman dialihkan ke kebijakan fallback (*Graceful Fallback*) tanpa memblokir nasabah yang sah secara sembarangan.
- **Auditability**: Setiap langkah inferensi agen harus disimpan ke database relasional dengan skema terstruktur untuk keperluan audit perbankan.

#### Tugas Rekayasa:
Rancang dokumen arsitektur teknis dan implementasi kode inti (core orchestration loop) yang mencakup:
- Strategi orkestrasi paralel vs serial untuk memenuhi batas latensi 1.500 ms.
- Arsitektur mitigasi token budget (misal: *prompt distillation* atau embedding retrieval terkompresi).
- Penanganan skenario saat penyedia API LLM pihak ketiga mengalami *timeout* atau degradasi performa pada detik ke-1.1.

---

### 15. Quiz Evaluasi Pemahaman

#### Skenario Dasar (5 Pertanyaan)
1. **Apa perbedaan mendasar antara *Centralized Orchestration* dan *Decentralized Choreography* pada Multi-Agent Systems?**
   - *Jawaban*: Orchestration memiliki entitas terpusat (Supervisor) yang mengarahkan alur kerja dan memegang kontrol eksplisit atas state, sedangkan Choreography mendistribusikan tanggung jawab melalui event-driven architecture di mana setiap agen bereaksi secara independen terhadap pesan tanpa koordinator tunggal.

2. **Mengapa menggabungkan seluruh riwayat interaksi antar-agen ke dalam satu percakapan besar (*single prompt context*) dianggap sebagai anti-pattern skala enterprise?**
   - *Jawaban*: Hal ini menyebabkan *context window exhaustion*, meningkatkan latensi inferensi secara signifikan, memicu lonjakan biaya token yang tidak terkontrol, serta meningkatkan risiko halusinasi dan instruksi yang saling bertabrakan (*instruction drift*).

3. **Apa fungsi utama dari arsitektur *Blackboard* dalam koordinasi multi-agen?**
   - *Jawaban*: Berfungsi sebagai penyimpan kebenaran bersama (*shared single source of truth*) yang decoupled, memungkinkan berbagai agen spesialis membaca dan menulis artefak secara asinkron tanpa memerlukan dependensi langsung antar-agen.

4. **Kapan implementasi *exponential backoff* wajib digunakan dalam siklus eksekusi agen?**
   - *Jawaban*: Saat menghadapi kegagalan yang bersifat sementara (*transient failures*), seperti rate limiting (HTTP 429), lonjakan beban API eksternal, atau kunci database sementara (*temporary resource lock*).

5. **Apa peran Pydantic atau schema enforcement engine dalam arsitektur multi-agent berbasis LLM?**
   - *Jawaban*: Mengubah output probabilistik teks bebas dari LLM menjadi objek data yang terstruktur, tervalidasi secara deterministik, dan aman digunakan oleh sistem hilir tanpa risiko injeksi kode atau runtime parsing error.

#### Skenario Menengah (5 Pertanyaan)
6. **Bagaimana cara mencegah fenomena *Cascading Hallucination* di mana kesalahan satu agen memicu kegagalan sistem secara sistemik?**
   - *Jawaban*: Dengan menyisipkan gerbang validasi deterministik (*rule-based sanitizers*) dan agen auditor (*evaluator-judge*) di antara tahap eksekusi tugas sebelum state bersama (Blackboard) diperbarui.

7. **Mengapa penggunaan representasi DAG (*Directed Acyclic Graph*) lebih disukai dalam mengelola dependensi tugas dibanding sekadar loop sekuensial sederhana?**
   - *Jawaban*: DAG memungkinkan optimalisasi latensi melalui paralelisasi tugas-tugas yang independen (*fan-out*), sekaligus secara eksplisit melarang terjadinya siklus ketergantungan melingkar (*circular dependencies*) yang dapat menyebabkan kebuntuan (*deadlock*).

8. **Dalam implementasi Supervisor-Worker, apa risiko arsitektural utama jika Supervisor itu sendiri mengalami kegagalan (*crash*) di tengah eksekusi?**
   - *Jawaban*: Terjadinya *Single Point of Failure* (SPOF) yang menyebabkan alur kerja terhenti tanpa kejelasan status, serta potensi artefak tak terlacak (*orphaned resources*) pada sistem hilir yang telah dimutasi oleh worker.

9. **Apa kegunaan Distributed Tracing (misal: OpenTelemetry) dalam sistem orkestrasi agen otonom?**
   - *Jawaban*: Untuk melacak korelasi kontekstual antar-panggilan asinkron secara end-to-end, mengidentifikasi agen penyebab latensi kritis, serta mengaudit pohon penalaran (*reasoning tree*) dan konsumsi token per transaksi.

10. **Bagaimana mekanisme *Optimistic Concurrency Control* diterapkan pada state Blackboard yang diakses banyak agen secara bersamaan?**
    - *Jawaban*: Setiap pembaruan state menyertakan nomor versi (*version ID*). Jika versi pada storage telah berubah sejak terakhir kali dibaca oleh agen, mutasi ditolak dan agen harus membaca ulang data terbaru sebelum mencoba menulis kembali.

#### Analisis Kasus Produksi (3 Pertanyaan Kasus)
11. **Kasus A**: Agen Coder dan Agen Tester Anda terjebak dalam *infinite ping-pong loop*. Coder memperbaiki bug A namun memicu bug B; Tester mengembalikannya ke Coder, yang kemudian memperbaiki bug B namun memicu bug A kembali. Metrik menunjukkan token billing membengkak $3,000 dalam 30 menit. 
    *Pertanyaan*: Apa perbaikan arsitektural konkret yang harus segera diimplementasikan?
    - *Solusi Analisis*: Terapkan ambang batas iterasi maksimal (*circuit breaker max retry = 3*). Jika batas tercapai, sistem menghentikan loop secara otomatis, membekukan diff kode terakhir, menandai status kegagalan konvergensi (*convergence failure*), dan mengeksekusi fallback alert ke human-in-the-loop (senior developer) dengan melampirkan log kegagalan terstruktur.

12. **Kasus B**: Agen Verifikasi Anda menolak sebuah payload transaksi karena nilai ambang batas anomali melampaui batas keamanan. Namun, Agen Eksekutor sebelumnya telah telanjur memanggil API transfer dana pihak ketiga yang bersifat *state-mutating*.
    *Pertanyaan*: Kesalahan arsitektur apa yang terjadi di sini, dan bagaimana desain transaksi perbankan yang seharusnya?
    - *Solusi Analisis*: Pelanggaran prinsip *Two-Phase Commit (2PC) / Reservation Pattern*. Agen eksekutor tidak boleh langsung memanggil API transfer permanen sebelum verifikasi selesai. Desain yang benar: Agen Eksekutor hanya melakukan *hold/reserve fund*, lalu Agen Verifikasi melakukan audit menyeluruh. Transaksi hanya di-*commit* (capture) jika seluruh verifikasi menghasilkan status lolos; jika ditolak, fungsi kompensasi (*compensating transaction/rollback*) dieksekusi secara otomatis.

13. **Kasus C**: Sistem multi-agent Anda mengalami degradasi latensi dramatis (P99 naik dari 3 detik ke 45 detik) ketika beban transaksi naik 400%. Observabilitas menunjukkan supervisor kehabisan resource CPU dan thread blocking.
    *Pertanyaan*: Bagaimana memigrasikan arsitektur orkestrasi tersebut agar mampu menangani lonjakan beban tinggi (*high-throughput spike*)?
    - *Solusi Analisis*: Dekonstruksi Supervisor monolitik menjadi *Event-Driven Choreography* menggunakan message broker terdistribusi (Apache Kafka atau RabbitMQ). Ubah eksekusi worker menjadi stateless consumer groups yang berjalan di atas auto-scaled Kubernetes pods (KEDA). Komunikasi langsung antar-node digantikan dengan asynchronous event passing, dan state disimpan secara terdistribusi pada Redis Cluster dengan mekanisme per-key TTL.

---

### 16. Summary

1. **Modularitas Kognitif**: Arsitektur Multi-Agent System (MAS) enterprise yang efektif memecah kompleksitas domain menjadi batasan-batasan konteks kecil yang diisolasi secara fungsional.
2. **State Management Sebagai Fondasi**: Keberhasilan sistem multi-agen produksi tidak terletak pada kehebatan prompt LLM semata, melainkan pada ketahanan pengelolaan *shared state*, validasi skema tipe data secara deterministik, serta pemeliharaan integritas data terdistribusi.
3. **Resiliensi Deterministik vs. Penalaran Stokastik**: LLM harus diperlakukan sebagai mesin inferensi lokal stokastik yang selalu dibatasi oleh aturan deterministik, sirkuit pengaman (*circuit breaker*), batasan iterasi konvergensi, dan observabilitas OpenTelemetry yang ketat.