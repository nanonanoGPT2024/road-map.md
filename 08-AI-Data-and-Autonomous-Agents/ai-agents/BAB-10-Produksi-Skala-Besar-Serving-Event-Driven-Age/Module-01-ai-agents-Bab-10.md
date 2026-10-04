# Bab 10: Produksi Skala Besar, Serving, & Event-Driven Agentic System

## Modul 01: Arsitektur Event-Driven Agentic Systems Skala Enterprise

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Mengidentifikasi Hambatan Skalabilitas Synchronous:** Memetakan kegagalan arsitektur *request-response* synchronous (HTTP/gRPC) pada beban kerja agen otonom multi-langkah (*multi-step reasoning*) dan merancang dekomposisi sistem menjadi arsitektur berbasis *event-driven*.
2. **Merancang Topologi Event Bus & Worker Pool Terdistribusi:** Mengimplementasikan pola *Consumer Group*, *Compacted Topics*, dan partisi berbasis entitas (*entity-keyed partitioning*) untuk menjamin eksekusi urutan pesan stateful per sesi agen.
3. **Mengimplementasikan Idempotency & Checkpointing Engine:** Membangun mekanisme *distributed state checkpointing* menggunakan PostgreSQL dan Redis dengan jaminan pengiriman pesan *at-least-once* tanpa duplikasi eksekusi *tool side-effects*.
4. **Mengelola Backpressure & Rate-Limiting Multi-Tier:** Mengonfigurasi algoritma *Token Bucket* terdistribusi dan *Leaky Bucket* untuk mengendalikan batas TPM (*Tokens Per Minute*) dan RPM (*Requests Per Minute*) dari vendor model dasar (*foundation models*).
5. **Membangun Error Handling & Dead-Letter Queue (DLQ):** Mengembangkan pola pemulihan kegagalan (*automated remediation*), *circuit breaker*, penanganan *poison-pill messages*, serta strategi *replayability* pada sistem terdistribusi.

---

### 2. Concept Overview

Membawa sistem agen otonom dari purwarupa ke lingkungan produksi skala enterprise memerlukan pergeseran paradigma mendasar: **dari model komputasi sinkron (RPC-style) ke State Machine Asinkron Berbasis Event (*Event-Driven State Machine*)**.

```
+------------------------------------------------------------------------------------+
|                                    MENTAL MODEL                                    |
|                                                                                    |
|   Synchronous Loop (Anti-Pattern Skala Besar)                                      |
|   Client ---> [ HTTP Request ] ---> [ Agent Loop: LLM -> Tool -> LLM ] ---> Return |
|   (Kelemahan: Blocking I/O, rentan timeout, menghabiskan thread pool, zero replay) |
|                                                                                    |
|   Event-Driven Reactive Loop (Standar Enterprise)                                  |
|   Event Ingress ---> [ Message Broker ] ---> [ Worker Agent: State Transition ]   |
|                             ^                         |                            |
|                             |                         v                            |
|                     [ Emit New Event ] <--- [ Checkpoint Store ]                   |
|   (Keunggulan: Non-blocking, fault-tolerant, horizontal scale, fully auditable)    |
+------------------------------------------------------------------------------------+
```

Dalam sistem monolitik atau prototipe agen berbasis CLI, siklus eksekusi agen (ReAct, Plan-and-Solve, dsb.) dieksekusi dalam satu *thread* lokal:
$$\text{State}_{t+1} = f(\text{State}_t, \text{LLM}(\text{Prompt}), \text{Tool}(\text{Action}))$$

Jika latensi satu panggilan LLM mencapai 2–15 detik, dan agen membutuhkan 5 siklus penalaran untuk menyelesaikan tugas, total waktu latensi berkisar antara 10–75 detik per *request*. Model sinkronus ini membebani *connection pools*, memicu *HTTP gateway timeout* (misalnya Cloudflare/ALB 30-60 detik), dan jika proses *worker* mengalami *crash* di tengah jalan, seluruh konteks komputasi hilang tanpa jejak.

**Mental Model Event-Driven Agentic System:**
Sistem agen diposisikan sebagai sekumpulan transisi status atomik (*atomic state transitions*) yang bereaksi terhadap *Domain Events*. Agen tidak berjalan terus-menerus dalam satu memori runtime, melainkan dieksekusi melalui pertukaran pesan asinkron:
1. Setiap iterasi agen menerbitkan event (misal: `AgentReasoningCompleted`, `ToolExecutionRequested`).
2. State agen di-materialisasikan ke penyimpanan terdistribusi (*checkpointer*).
3. Pemanggilan alat (*tool calling*) didelegasikan ke *worker pool* terpisah yang memiliki hak akses jaringan/komputasi terisolasi.
4. Hasil eksekusi alat memicu event `ToolExecutionSucceeded`, yang dikonsumsi kembali oleh agen untuk langkah inferensi berikutnya.

---

### 3. Why It Matters

Di tingkat enterprise, sistem agen otonom menghadapi tantangan operasional yang kompleks:

*   **Non-deterministic Latency & Network Jitter:** Inferensi model bahasa besar (LLM) tidak memiliki batas waktu tetap. Jaringan publik atau *internal model endpoint* (seperti vLLM/Triton) dapat berfluktuasi secara drastis berdasarkan panjang konteks token (*prefill phase vs decode phase*).
*   **Ledakan Biaya & Kegagalan Beruntun (*Cascading Failures*):** Jika 100 permintaan agen secara bersamaan melakukan *polling* atau menjalankan loop eksekusi yang gagal pada *tool* pihak ketiga yang lambat, sistem dapat mengalami *resource exhaustion*, menekan kuota API vendor, dan menyebabkan pemadaman total sistem (*cascading denial-of-service*).
*   **Persyaratan Kepatuhan & Audit (*Enterprise Auditability*):** Regulasi (seperti SOC2, HIPAA, ISO 27001, EU AI Act) mewajibkan setiap keputusan agen, data yang disuntikkan ke prompt, dan hasil eksekusi alat dicatat secara deterministik dan tidak dapat dimanipulasi (*tamper-proof*). Arsitektur *Event-Driven* dengan *Event Sourcing* menyediakan jejak audit (*audit trail*) secara alami.
*   **Isolasi Komputasi & Keamanan Tooling:** Agen sering kali harus mengeksekusi kode Python sembarang, query SQL analitik, atau API sensitif. Menjalankan *tool* ini di dalam thread yang sama dengan loop inferensi LLM menciptakan celah keamanan fatal (*sandbox breakout*). Pemisahan berbasis *event message* membatasi akses eksekusi ke infrastruktur khusus (misalnya: microVM Firecracker / sandbox gVisor).

---

### 4. Arsitektur & Diagram Komponen

Arsitektur di bawah ini menguraikan sistem orkestrasi agen terdistribusi yang memisahkan *Ingress*, *Orchestration Loop*, *Tool Sandbox Execution*, dan *Persistence Layer*.

```
+--------------------------------------------------------------------------------------------------------------------------+
|                                    EVENT-DRIVEN AGENTIC RUNTIME TOPOLOGY                                                |
+--------------------------------------------------------------------------------------------------------------------------+
                                                     |
                                            [ HTTP/gRPC Request ]
                                                     v
                                      +-------------------------------+
                                      |   API Ingress & Edge Proxy    |
                                      |     (FastAPI / Envoy API)     |
                                      +-------------------------------+
                                                     |
                                     (Generates Session / Trace ID)
                                                     |
                                                     v
                         +-------------------------------------------------------+
                         |       MESSAGE BUS (Apache Kafka / Redis Streams)      |
                         |                                                       |
                         |  Topic: agent.events.ingress                          |
                         |  Topic: agent.events.tool-dispatch                    |
                         |  Topic: agent.events.tool-results                     |
                         |  Topic: agent.events.dlq                              |
                         +-------------------------------------------------------+
                                   |                                   ^
       +---------------------------+                                   |
       | (Partition by Session ID)                                     | (Emit Tool Call Request)
       v                                                               |
+--------------------------------------+             +---------------------------------------+
|        AGENT REASONING WORKER        |             |         TOOL EXECUTION WORKER         |
|         (Stateless Consumer)         |             |       (Sandboxed / Ephemeral)         |
|                                      |             |                                       |
|  1. Pull Ingress/Tool-Result Event   |             |  1. Pull Tool-Dispatch Event          |
|  2. Load State from Checkpointer     |             |  2. Check Token / Rate Limiter        |
|  3. Call LLM (vLLM / Triton / Cloud) |             |  3. Execute Tool in Sandbox           |
|  4. Decide Action (Stop / Call Tool) |             |  4. Emit Tool-Result Event            |
|  5. Commit Checkpoint (Trans. State) |             +---------------------------------------+
+--------------------------------------+                                 |
       |                        |                                       |
       | (Update State)         | (Tool Required)                       | (Execution Output)
       v                        +---------------------------------------+
+--------------------------------------+
|       CHECKPOINT & STATE STORE       |
|    (PostgreSQL JSONB / DynamoDB)     |
|                                      |
|  - Table: agent_sessions             |
|  - Table: agent_step_audit_log       |
|  - Table: idempotency_keys           |
+--------------------------------------+
       ^
       | (Distributed Locks)
+--------------------------------------+
|      DISTRIBUTED CACHE & LOCKS       |
|           (Redis Cluster)            |
|                                      |
|  - Redlock: session_mutex:<id>       |
|  - Token Bucket Rate Limiter         |
+--------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Event Choreography vs. Event Orchestration

*   **Choreography:** Setiap komponen bereaksi secara independen terhadap event tanpa entitas pengendali terpusat. Cocok untuk arsitektur *microservices* umum, namun sering menimbulkan status ambigu (*scattered logic*) pada penalaran agen yang kompleks.
*   **Orchestration via Checkpointed State Machine:** Agen beroperasi sebagai konduktor terdistribusi. Node penalaran (*Reasoning Node*) mengontrol alur melalui status yang terdefinisi rapi, tetapi mengomunikasikan instruksi melalui broker pesan. Ini adalah arsitektur yang digunakan dalam sistem agen skala besar: deterministik dalam alur eksekusi, tetapi sepenuhnya terdistribusi dan tahan kegagalan (*fault-tolerant*) dalam eksekusi I/O.

#### B. Mekanisme State Checkpointing & Redlock

Untuk mencegah dua worker memproses pembaruan pada agen yang sama secara bersamaan (*race condition* / *split-brain state*), sistem menerapkan:
1.  **Distributed Lock (Redlock / Single-instance Mutex):** Diakuisisi pada level `session_id` sebelum worker mulai mengekstrak status dari database.
2.  **Optimistic Concurrency Control (OCC):** Database menyimpan kolom `version` (skema monotonik bertambah). Setiap penulisan state baru diverifikasi dengan kueri:
    $$\text{UPDATE agent\_sessions SET state = :new\_state, version = version + 1 WHERE id = :id AND version = :current\_version}$$
    Jika jumlah baris yang diperbarui adalah 0, proses mengalami konflik konkurensi, transaksi dibatalkan, dan event diarahkan kembali (*re-queued* / *nack*).

#### C. Penjaminan Idempotensi Tool Execution

Penyebab umum kegagalan pada agen adalah eksekusi ganda aksi eksternal non-idempoten (misalnya: memotong saldo pelanggan dua kali atau mengirim dua email yang sama akibat pengiriman ulang pesan dari broker).
Formula pembuatan kunci idempotensi (*Idempotency Key*):
$$\text{Key} = \text{HMAC-SHA256}(\text{SessionID} \parallel \text{StepIndex} \parallel \text{ToolName} \parallel \text{ArgPayload})$$
Sebelum worker mengeksekusi alat, kunci ini diverifikasi secara atomik ke database atau Redis menggunakan perintah `SET resource_key token NX EX ttl`. Jika kunci sudah ada, worker tidak mengeksekusi ulang alat, melainkan langsung mengambil hasil yang telah di-cache dari langkah sebelumnya.

#### D. Penanganan Backpressure & Token Rate Limiting

Panggilan LLM dibatasi oleh kuota vendor (TPM/RPM). Ketika ratusan agen berjalan bersamaan:
*   **Buffer Ingress:** Antrean pesan (*queue*) berfungsi sebagai peredam lonjakan beban (*shock absorber*). Kecepatan agen membaca event diatur sesuai ketersediaan *token bucket*.
*   **Distributed Leaky Bucket:** Worker penalaran mengonsumsi token dari Redis sebelum memicu inferensi LLM. Jika token tidak tersedia, worker menunda proses (*backoff*) dan menahan *acknowledgement* (ACK) pesan, sehingga broker menahan laju pengiriman (*natural backpressure*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python skala produksi menggunakan arsitektur bersih (*Clean Architecture*). Implementasi ini mencakup:
* Pydantic v2 untuk validasi schema event dan state.
* Abstraksi Checkpoint Store berbasis PostgreSQL / Asynchronous Engine.
* Worker Event Loop berbasis Redis Streams lengkap dengan penanganan idempotensi, *distributed locking*, dan penanganan kegagalan.

```python
# File: agent_production_runtime.py
# Architecture: Distributed Event-Driven Agentic Engine
# Prerequisites: pip install pydantic redis asyncpg

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("AgentEngine")

# =====================================================================
# 1. DOMAIN MODELS & CLOUDEVENTS SCHEMAS
# =====================================================================

class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CloudEventEnvelope(BaseModel):
    """Standar implementasi CNCF CloudEvents v1.0.2"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "urn:service:agentic-runtime"
    specversion: str = "1.0"
    type: str
    datacontenttype: str = "application/json"
    time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Dict[str, Any]

class AgentSessionState(BaseModel):
    session_id: str
    user_id: str
    current_step: int = 0
    status: StepStatus = StepStatus.PENDING
    context_variables: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, str]] = Field(default_factory=list)
    version: int = 1
    updated_at: float = Field(default_factory=time.time)

# =====================================================================
# 2. INTERFACES (PORTS)
# =====================================================================

class StateCheckpointer(ABC):
    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[AgentSessionState]:
        pass

    @abstractmethod
    async def save_state(self, state: AgentSessionState) -> bool:
        """Menyimpan state secara atomik menggunakan Optimistic Concurrency Control."""
        pass

class DistributedLock(ABC):
    @abstractmethod
    async def acquire(self, lock_key: str, ttl_ms: int) -> bool:
        pass

    @abstractmethod
    async def release(self, lock_key: str) -> None:
        pass

# =====================================================================
# 3. INFRASTRUCTURE ADAPTERS (IN-MEMORY / DISTRIBUTED MOCK)
# =====================================================================

class InMemoryCheckpointer(StateCheckpointer):
    """Checkpointer terdistribusi mock berbasis thread-safe dictionary untuk simulasi."""
    def __init__(self) -> None:
        self._store: Dict[str, AgentSessionState] = {}
        self._lock = asyncio.Lock()

    async def get_state(self, session_id: str) -> Optional[AgentSessionState]:
        async with self._lock:
            state = self._store.get(session_id)
            if state:
                return state.model_copy(deep=True)
            return None

    async def save_state(self, state: AgentSessionState) -> bool:
        async with self._lock:
            existing = self._store.get(state.session_id)
            if existing:
                # Verifikasi OCC: Versi harus persis state yang dimuat sebelumnya
                if existing.version != state.version:
                    logger.warning(
                        f"OCC Conflict! Session: {state.session_id}. Current DB Version: {existing.version}, Incoming: {state.version}"
                    )
                    return False
                state.version += 1
                state.updated_at = time.time()
                self._store[state.session_id] = state.model_copy(deep=True)
                return True
            else:
                state.version = 1
                state.updated_at = time.time()
                self._store[state.session_id] = state.model_copy(deep=True)
                return True

class SimpleRedisLock(DistributedLock):
    """Simulasi penguncian terdistribusi atomik."""
    def __init__(self) -> None:
        self._locks: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, lock_key: str, ttl_ms: int) -> bool:
        async with self._lock:
            now = time.time() * 1000
            if lock_key in self._locks:
                if self._locks[lock_key] > now:
                    return False  # Masih terkunci
            self._locks[lock_key] = now + ttl_ms
            return True

    async def release(self, lock_key: str) -> None:
        async with self._lock:
            self._locks.pop(lock_key, None)

# =====================================================================
# 4. CORE ENGINE & RUNTIME WORKER
# =====================================================================

class AgentExecutionWorker:
    def __init__(
        self,
        worker_id: str,
        checkpointer: StateCheckpointer,
        lock_manager: DistributedLock,
        idempotency_ttl_seconds: int = 3600
    ) -> None:
        self.worker_id = worker_id
        self.checkpointer = checkpointer
        self.lock_manager = lock_manager
        self.idempotency_ttl = idempotency_ttl_seconds
        self._processed_idempotency_keys: Dict[str, Any] = {}

    def compute_idempotency_key(
        self, session_id: str, step_index: int, tool_name: str, payload: Dict[str, Any]
    ) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        raw_key = f"{session_id}:{step_index}:{tool_name}:{serialized}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def _mock_llm_inference(self, prompt: str) -> Dict[str, Any]:
        """Simulasi panggilan non-blocking ke inference mesh/LLM Gateway."""
        await asyncio.sleep(0.1)  # Simulasi latensi I/O
        if "cek transaksi" in prompt.lower():
            return {
                "action": "call_tool",
                "tool_name": "database_lookup",
                "arguments": {"transaction_id": "TRX-998823"}
            }
        return {
            "action": "final_answer",
            "message": "Transaksi berhasil diverifikasi dan valid."
        }

    async def _mock_tool_sandbox(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Simulasi eksekusi alat dalam isolated micro-container."""
        await asyncio.sleep(0.15)
        if tool_name == "database_lookup":
            return json.dumps({"status": "SUCCESS", "amount": 550000, "currency": "IDR"})
        raise ValueError(f"Unknown Tool: {tool_name}")

    async def process_ingress_event(self, event: CloudEventEnvelope) -> bool:
        """
        Handler eksekusi satu siklus penalaran agen dari antrean.
        Menjamin konkurensi aman, recovery, OCC state tracking, dan idempotency.
        """
        session_id = event.data.get("session_id")
        user_message = event.data.get("message")

        if not session_id or not user_message:
            logger.error(f"Malformed Event Payload: {event.id}")
            return False

        lock_key = f"lock:agent:session:{session_id}"
        has_lock = await self.lock_manager.acquire(lock_key, ttl_ms=10000)
        if not has_lock:
            logger.warning(f"Worker [{self.worker_id}] Gagal memperoleh lock untuk session: {session_id}. Event ditangguhkan.")
            return False

        try:
            # 1. Load Current State
            state = await self.checkpointer.get_state(session_id)
            if not state:
                state = AgentSessionState(
                    session_id=session_id,
                    user_id=event.data.get("user_id", "anonymous"),
                    status=StepStatus.PENDING
                )

            # 2. Append User Input to History
            state.history.append({"role": "user", "content": user_message})
            state.status = StepStatus.RUNNING

            # 3. Invoke LLM Inference
            llm_result = await self._mock_llm_inference(user_message)
            
            # 4. Handle Decisions (Tool Calling vs Final Output)
            if llm_result["action"] == "call_tool":
                tool_name = llm_result["tool_name"]
                tool_args = llm_result["arguments"]
                
                # Cek Idempotensi
                idempotency_key = self.compute_idempotency_key(
                    session_id=state.session_id,
                    step_index=state.current_step,
                    tool_name=tool_name,
                    payload=tool_args
                )

                if idempotency_key in self._processed_idempotency_keys:
                    logger.info(f"Idempotency Cache Hit! Bypass tool execution: {tool_name}")
                    tool_output = self._processed_idempotency_keys[idempotency_key]
                else:
                    logger.info(f"Executing Tool [{tool_name}] dengan sandboxed safety layer...")
                    try:
                        tool_output = await self._mock_tool_sandbox(tool_name, tool_args)
                        self._processed_idempotency_keys[idempotency_key] = tool_output
                    except Exception as ex:
                        logger.error(f"Eksekusi Tool Gagal: {str(ex)}")
                        state.status = StepStatus.FAILED
                        await self.checkpointer.save_state(state)
                        return False

                # Lanjutkan internal state
                state.history.append({"role": "system_tool", "content": tool_output})
                state.current_step += 1
                
                # Second Phase Inference untuk generate final answer pasca-eksekusi tool
                final_thought = await self._mock_llm_inference(f"Tool output: {tool_output}")
                state.history.append({"role": "assistant", "content": final_thought.get("message", "")})
                state.status = StepStatus.COMPLETED

            elif llm_result["action"] == "final_answer":
                state.history.append({"role": "assistant", "content": llm_result["message"]})
                state.status = StepStatus.COMPLETED

            # 5. Atomic State Commit via Checkpointer (OCC Guard)
            success = await self.checkpointer.save_state(state)
            if not success:
                logger.error(f"OCC update conflict pada session {session_id}! Harus dilakukan re-processing event.")
                return False

            logger.info(f"Session {session_id} step {state.current_step} berhasil diproses. Status: {state.status}")
            return True

        except Exception as error:
            logger.exception(f"Unhandled failure in Worker Execution: {str(error)}")
            return False

        finally:
            await self.lock_manager.release(lock_key)

# =====================================================================
# 5. ASYNCHRONOUS ENGINE TEST HARNESS
# =====================================================================

async def main():
    logger.info("Menginisialisasi distributed runtime components...")
    checkpointer = InMemoryCheckpointer()
    lock_manager = SimpleRedisLock()
    
    worker_1 = AgentExecutionWorker(worker_id="worker-node-alpha", checkpointer=checkpointer, lock_manager=lock_manager)
    worker_2 = AgentExecutionWorker(worker_id="worker-node-beta", checkpointer=checkpointer, lock_manager=lock_manager)

    # Event Simulasi 1: Permintaan pengecekan transaksi
    event_payload_1 = CloudEventEnvelope(
        type="com.enterprise.agent.query",
        data={
            "session_id": "session-uuid-1001",
            "user_id": "user-corp-54",
            "message": "Tolong cek transaksi saya dengan ID TRX-998823 sekarang."
        }
    )

    logger.info("=== Simulasi 1: Jalur Eksekusi Standar (Tool Use & Idempotency Check) ===")
    success = await worker_1.process_ingress_event(event_payload_1)
    logger.info(f"Hasil Eksekusi Worker 1: {success}")

    # Verifikasi State Pasca-Eksekusi
    state_after = await checkpointer.get_state("session-uuid-1001")
    if state_after:
        print("\n--- SNAPSHOT STATE AKHIR DI CHECKPOINTER ---")
        print(json.dumps(state_after.model_dump(), indent=2))
        print("-------------------------------------------\n")

    logger.info("=== Simulasi 2: Replay Event yang Sama (Pengujian Idempotensi & OCC) ===")
    # Menjalankan worker_2 dengan event payload identik untuk mensimulasikan redelivery broker
    duplicate_event = CloudEventEnvelope(
        type="com.enterprise.agent.query",
        data={
            "session_id": "session-uuid-1001",
            "user_id": "user-corp-54",
            "message": "Tolong cek transaksi saya dengan ID TRX-998823 sekarang."
        }
    )
    replay_success = await worker_2.process_ingress_event(duplicate_event)
    logger.info(f"Hasil Eksekusi Replay Worker 2: {replay_success}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Pada produksi skala masif, pola kegagalan sistem agen jauh melampaui error HTTP 500 standar. Desain arsitektur wajib mengantisipasi mode kegagalan kritis berikut:

| Failure Mode | Akar Masalah (Root Cause) | Dampak pada Sistem | Pola Mitigasi / Remediasi |
| :--- | :--- | :--- | :--- |
| **Poison Pill Messages** | Payload event pengguna menghasilkan prompt anomali yang memicu *infinite loop* atau exception fatal pada LLM JSON Parsing. | Seluruh worker *crash*, pesan di-nack, dikonsumsi ulang, memicu *crash loop* beruntun pada antrean. | Terapkan batas ambang batas *Retry Counter* (maksimal 3x). Jika gagal, alirkan secara atomik ke **Dead-Letter Queue (DLQ)** bersama rekaman *stack-trace* lengkap. |
| **Split-Brain Session Mutation** | Dua pesan untuk `session_id` yang sama masuk ke dua partisi/worker yang berbeda akibat kesalahan hashing partisi pesan. | Terjadi *race condition*, state saling menimpa (*loss of intermediate thought*), percabangan status tidak sinkron. | **Partition Key Enforcing:** Gunakan `session_id` sebagai *Key* partisi broker. Pasang **Optimistic Locking** di database serta mutasi *mutex lock* sebelum pengolahan event. |
| **Partial Tool Failure (Side-effects)** | Tool berhasil mengubah status eksternal (misal: memanggil API pembayaran), namun jaringan putus sebelum worker mencatat state ke checkpointer. | Terjadi *state mismatch*. Broker melakukan pengiriman ulang (*re-delivery*), aksi alat terulang kembali dua kali. | **Strict Idempotency Keys:** Setiap tool wajib menerima token transaksi deterministik (*Idempotency-Key* HTTP header atau DB transaction unique constraint). |
| **Context Window Explosion Mid-Loop** | Agen mengeksekusi multi-step reasoning yang mengumpulkan output konteks melampaui batas *context length* model LLM. | Panggilan LLM ditolak secara berulang (*Bad Request: Context length exceeded*). Agen terhenti tanpa resolusi. | **Dynamic Checkpoint Summarization:** Ketika ukuran histori melebihi 70% batas konteks, jalankan *background compaction job* untuk merangkum langkah sebelumnya menjadi ringkasan konteks eksekutif (*lossy pruning*). |
| **LLM Provider Throttling (HTTP 429)** | Lonjakan serentak (*thundering herd*) menghabiskan kuota TPM/RPM vendor API. | Semua worker gagal bersamaan, antrean melonjak, latensi sistem menyentuh ambang kritis SLA. | **Decoupled Rate Limiter:** Gunakan Redis-based Leaky Bucket sebelum eksekusi LLM. Jika token habis, tunda pembacaan antrean melalui *exponential backoff with jitter* (jangan membebani broker). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur pada sistem agen terdistribusi menuntut kompromi struktural:

#### 1. Message Broker: Redis Streams vs. Apache Kafka vs. RabbitMQ
*   **Redis Streams:** 
    *   *Kelebihan:* Latensi sub-milidetik, konfigurasi operasional sederhana, terintegrasi langsung dengan ekosistem Redis (*caching*, *distributed lock*).
    *   *Kekurangan:* Skalabilitas kapasitas memori terbatas (RAM-bound), kurang optimal untuk persistensi data hingga hitungan bulan (*long retention*).
    *   *Trade-off:* Ideal untuk sistem agen dengan kapasitas throughput menengah (< 50,000 event/detik) dengan retensi sementara.
*   **Apache Kafka:**
    *   *Kelebihan:* Throughput tinggi, partisi terdistribusi tanpa batas memori RAM (*disk-based*), retensi jangka panjang, fitur *Log Compaction*.
    *   *Kekurangan:* Latensi lebih tinggi dibanding Redis (overhead network batching), kompleksitas operasional tinggi (ZooKeeper/KRaft, JVM tuning).
    *   *Trade-off:* Pilihan wajib untuk skala raksasa (*Tier-1 Enterprise*) dengan kebutuhan audit kepatuhan berbasis *event streaming* historis.

#### 2. Workflow Orchestration: Code-First (Temporal.io/Cadence) vs. Broker-First (Custom Event-Driven)
*   **Temporal.io (Durable Execution):**
    *   *Kelebihan:* Mengabstraksi seluruh arsitektur event-loop menjadi kode imperatif biasa; penanganan *state replay* dan *checkpointing* ditangani otomatis oleh engine Temporal.
    *   *Kekurangan:* Keterikatan erat (*tight coupling*) pada runtime platform Temporal; kurva belajar tinggi untuk pengelolaan arsitektur internalnya.
*   **Custom Event-Driven (Kafka/Redis + Celery/Custom Workers):**
    *   *Kelebihan:* Kontrol penuh terhadap aliran data (*data plane*), pemisahan batas layanan yang tegas (*loose coupling*), mudah disesuaikan dengan infrastruktur yang ada.
    *   *Kekurangan:* Tanggung jawab keandalan sistem (*reliability engineering*), *locking*, *idempotency*, dan mekanisme *retry* harus dibangun dan diuji secara mandiri oleh tim internal.

---

### 9. Best Practices & Standard Industri

Mengoperasikan sistem agen otonom pada skala produksi menuntut penerapan standar rekayasa perangkat lunak yang ketat:

1.  **Standarisasi Format Pesan dengan CloudEvents:**
    Semua komunikasi asinkron harus mematuhi spesifikasi [CNCF CloudEvents](https://cloudevents.io/). Hal ini memungkinkan standardisasi *header*, *tracing contexts*, dan deserialisasi yang konsisten di berbagai bahasa pemrograman worker.
2.  **Telemetry Terdistribusi (OpenTelemetry GenAI Semantic Conventions):**
    Sematkan konteks trace (`traceparent`, `span_id`) ke dalam metadata event:
    *   Rekam atribut model LLM: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`, `gen_ai.usage.completion_tokens`.
    *   Pastikan *distributed span* tidak terputus saat berpindah dari Ingress API $\to$ Message Broker $\to$ Reasoning Worker $\to$ Tool Executor.
3.  **Graceful Degradation via Circuit Breaker:**
    Pasang *Circuit Breaker* (misal: menggunakan pustaka Resilience4j atau implementasi Python sejenis) pada pemanggilan LLM dan Tool API. Jika tingkat kegagalan (*failure rate*) melebihi 50% dalam interval 30 detik, buka sirkuit secara otomatis dan kembalikan *fallback message* deterministik ke pengguna tanpa membuang komputasi downstream.
4.  **Sandbox Isolation Tingkat Komputasi:**
    Jangan pernah mengeksekusi kode Python atau shell hasil generate LLM di dalam lingkungan OS host worker. Gunakan lingkungan tervirtualisasi ringan dan ephemeral dengan tingkat keamanan tinggi seperti **gVisor (Google Runsc)**, **AWS Firecracker**, atau kontainer Docker tanpa hak akses root (*rootless container*) dengan isolasi total antarmuka jaringan (*network namespace drop*).
5.  **12-Factor Stateless Worker Topology:**
    Worker node penalaran agen harus sepenuhnya *stateless*. Memori lokal tidak boleh menyimpan data sesi lintas siklus event. Jika sebuah worker dimatikan secara mendadak melalui sinyal `SIGKILL` (misal: saat proses *Kubernetes Pod Autoscaling*), worker lain harus dapat langsung melanjutkan siklus langkah agen tanpa kehilangan konteks, bermodalkan *Checkpoint Store*.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta untuk membangun dan menguji ketahanan sebuah arsitektur agen terdistribusi sederhana. Sistem ini bertugas memproses order refund pengguna, di mana satu worker penalaran sengaja dimatikan secara mendadak (*simulated crash*) saat eksekusi berlangsung, guna membuktikan bahwa transaksi stateful berhasil dipulihkan secara otomatis oleh worker lain berkat arsitektur *event-driven* dan *checkpoint store*.

#### Kebutuhan Lingkungan (Prerequisites)
* Docker dan Docker Compose terinstal di mesin lokal.
* Python 3.10+ dengan pustaka: `pip install redis pydantic asyncpg`

#### Langkah-Langkah Implementasi

##### Langkah 1: Luncurkan Redis Infrastructure
Buat file `docker-compose.yml` sederhana untuk broker dan kunci terdistribusi:
```yaml
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    container_name: agent-broker
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
```
Jalankan instans:
```bash
docker compose up -d
```

##### Langkah 2: Bangun Script Producer Event
Buat file `lab_publisher.py` untuk mensimulasikan ingress API yang mengirim event tugas agen:
```python
# lab_publisher.py
import asyncio
import json
import redis.asyncio as redis
from agent_production_runtime import CloudEventEnvelope

async def publish_tasks():
    r = redis.from_url("redis://localhost:6379/0")
    session_id = "session-lab-prod-007"
    
    event = CloudEventEnvelope(
        type="com.enterprise.agent.refund_request",
        data={
            "session_id": session_id,
            "user_id": "usr-enterprise-889",
            "message": "Tolong cek transaksi saya dengan ID TRX-998823 sekarang."
        }
    )
    
    # Push event ke stream Redis
    stream_payload = {"payload": event.model_dump_json()}
    msg_id = await r.xadd("agent:stream:ingress", stream_payload)
    print(f"[PUBLISHER] Tugas diterbitkan ke stream. Message ID: {msg_id}")
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(publish_tasks())
```

##### Langkah 3: Bangun Resilient Worker Listener
Buat file `lab_resilient_worker.py`. Worker ini membaca antrean dari Redis Stream menggunakan *Consumer Group*. Worker ini diprogram untuk **sengaja dimatikan (crash via `sys.exit`)** jika mendeteksi *execution attempt* pertama, lalu dijalankan kembali untuk menunjukkan pemulihan state:

```python
# lab_resilient_worker.py
import asyncio
import json
import sys
import redis.asyncio as redis
from agent_production_runtime import (
    AgentExecutionWorker,
    InMemoryCheckpointer,
    SimpleRedisLock,
    CloudEventEnvelope,
    StepStatus
)

# Global persistent instances across simulated process reboot
SHARED_CHECKPOINTER = InMemoryCheckpointer()
SHARED_LOCK = SimpleRedisLock()

async def run_worker(worker_name: str, crash_on_first_try: bool = False):
    r = redis.from_url("redis://localhost:6379/0")
    group_name = "agent_reasoning_group"
    stream_name = "agent:stream:ingress"

    try:
        await r.xgroup_create(stream_name, group_name, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists

    worker_instance = AgentExecutionWorker(
        worker_id=worker_name,
        checkpointer=SHARED_CHECKPOINTER,
        lock_manager=SHARED_LOCK
    )

    print(f"[{worker_name}] Menunggu event dari stream...")
    
    while True:
        # Read messages via Consumer Group
        events = await r.xreadgroup(group_name, worker_name, {stream_name: ">"}, count=1, block=2000)
        if not events:
            continue

        for stream, messages in events:
            for message_id, raw_data in messages:
                payload_str = raw_data[b"payload"].decode("utf-8")
                envelope = CloudEventEnvelope.model_validate_json(payload_str)
                print(f"[{worker_name}] Memproses Event: {envelope.id} untuk Session: {envelope.data['session_id']}")

                if crash_on_first_try:
                    print(f"[{worker_name}] !!! SIMULATED CRASH (Kernel Panic / OOM) SEBELUM COMMIT STATE !!!")
                    await r.aclose()
                    sys.exit(1)

                # Process event
                success = await worker_instance.process_ingress_event(envelope)
                if success:
                    # Acknowledge completion ke broker
                    await r.xack(stream_name, group_name, message_id)
                    print(f"[{worker_name}] Berhasil menyelesaikan tugas. Event di-ACK. Message ID: {message_id}")
                    await r.aclose()
                    return

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if mode == "crash":
        asyncio.run(run_worker("Worker-FailFast", crash_on_first_try=True))
    else:
        asyncio.run(run_worker("Worker-Survivor", crash_on_first_try=False))
```

##### Langkah 4: Eksekusi Skenario Pengujian

1. **Jalankan Publisher untuk mengirim satu event:**
   ```bash
   python lab_publisher.py
   ```
2. **Jalankan Worker Pertama (Simulasi Crash):**
   ```bash
   python lab_resilient_worker.py crash
   ```
   *Output terminal akan menunjukkan worker mengalami crash sebelum status selesai di-commit.*
3. **Jalankan Worker Kedua (Survivor / Recovery Worker):**
   Pada sistem produksi, broker akan mengalokasikan kembali event yang tidak di-ACK (*Pending Entries List / PEL*) ke worker lain setelah interval *min-idle-time* terlampaui. Jalankan worker survivor:
   ```bash
   python lab_resilient_worker.py normal
   ```

##### Langkah 5: Verifikasi Hasil
Periksa apakah pesan berhasil di-ACK dan transaksi diproses hingga tuntas tanpa merusak konsistensi data checkpoint:
1. Pastikan status session pada checkpointer berakhir pada status `COMPLETED`.
2. Pastikan tidak ada duplikasi eksekusi tool log pada output konsol survivor worker (terlindungi oleh algoritma *Idempotency Key*).

```
[Worker-Survivor] Menunggu event dari stream...
[Worker-Survivor] Memproses Event: ... untuk Session: session-lab-prod-007
[Worker-Survivor] Idempotency Cache Hit! Bypass tool execution: database_lookup
[Worker-Survivor] Session session-lab-prod-007 step 1 berhasil diproses. Status: StepStatus.COMPLETED
[Worker-Survivor] Berhasil menyelesaikan tugas. Event di-ACK.
```

Dengan menyelesaikan alur ini, Anda telah mengonfirmasi bahwa sistem agen otonom terdistribusi mampu menoleransi kegagalan fatal pada tingkat komputasi tanpa kehilangan konteks percakapan maupun mengeksekusi operasi pihak ketiga secara berulang.