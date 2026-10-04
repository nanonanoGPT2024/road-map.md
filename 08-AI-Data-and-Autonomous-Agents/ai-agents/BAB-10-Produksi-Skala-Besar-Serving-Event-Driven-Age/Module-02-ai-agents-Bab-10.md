# KURIKULUM SISTEM ENTERPRISE: AI AGENTS
## KATEGORI: 08-AI-Data-and-Autonomous-Agents
### BAB 10: Produksi Skala Besar, Serving & Event-Driven Agents
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Event-Driven

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Architect dan Senior AI Engineer diharapkan mampu:
1. **Menganalisis dan Memilih Pola Komunikasi (Architectural Evaluation):** Mengidentifikasi kelemahan mendasar model sinkronus (HTTP/gRPC request-response) pada *agentic workflow* dan mengevaluasi transisi ke arsitektur *event-driven* berbasis *message broker* (Kafka/RabbitMQ/Redis Streams).
2. **Merancang Topologi Event-Driven Multi-Agent System (ED-MAS):** Mendesain *backplane* komunikasi asinkronus yang mencakup *choreography vs. orchestration*, *agent mesh*, *state persistence*, dan *distributed transaction* (Saga Pattern).
3. **Mengimplementasikan Idempotensi dan State Consistency:** Mengonstruksi sistem konsumsi event yang menjamin semantik *at-least-once delivery* dengan *deduplication engine*, *distributed locking* (Redlock), dan *transactional outbox pattern*.
4. **Membangun Resilient Worker Engine Skala Enterprise:** Menulis *production-grade worker* asinkronus dengan fitur penanganan *backpressure*, *dynamic batching*, *heartbeat preservation* selama inferensi LLM durasi panjang, serta mitigasi *poison-pill payload* via *Dead Letter Queue* (DLQ).
5. **Menginstrumentasi Observabilitas Komprehensif:** Mengintegrasikan W3C Trace Context propagation ke dalam event metadata untuk pelacakan *distributed tracing* end-to-end melintasi batas sistem asinkronus menggunakan OpenTelemetry.

---

### 2. Prerequisite

Sebelum menempuh materi ini, peserta wajib menguasai fondasi berikut:
* **Concurrency & Asynchronous Programming:** Pemahaman mendalam tentang `asyncio`, *event loop*, *task scheduling*, dan *thread/process pool execution* pada Python.
* **Distributed Streaming & Messaging:** Konsep *partitioning*, *consumer groups*, *offset management*, *acknowledgments*, dan *rebalancing* pada Apache Kafka atau Redis Streams.
* **Core Agent Architecture:** Siklus ReAct (Reasoning + Acting), *tool calling/function calling*, *memory management* (ephemeral vs persistent), dan struktur *state graph*.
* **Database & Caching Internals:** Mekanisme isolasi transaksi ACID, *optimistic/pessimistic concurrency control*, TTL, serta struktur data Redis (Hash, Sorted Set, Streams).
* **Enterprise Distributed Tracing:** Spesifikasi OpenTelemetry, context injection/extraction melintasi transport layer non-HTTP.

---

### 3. Concept & Internal Architecture

Penerapan agen AI otonom pada lingkungan *enterprise production* menuntut pergeseran paradigma dari *synchronous microservices* ke *asynchronous event-driven architecture* (EDA). Pada sistem monolitik atau REST-based agent, koneksi HTTP dipertahankan terbuka (*held-open socket*) selama LLM melakukan *chain-of-thought*, mengeksekusi multi-step external tools, dan melakukan sintesis akhir. Pendekatan ini rentan terhadap *cascading failures*, *connection pool exhaustion*, dan *timeout cascade*.

```
+-----------------------------------------------------------------------------------+
|                        EVENT-DRIVEN AGENT BACKPLANE                               |
|                                                                                   |
|  +---------------------+      Kafka / Redis Streams      +---------------------+  |
|  |   Ingress Gateway   |  ============================>  |  Agent Worker Pool  |  |
|  | (Event Producer)    |       Topic: agent.tasks        |  (Consumer Group)   |  |
|  +---------------------+                                 +----------+----------+  |
|             |                                                       |             |
|             | Metadata Injection                                    | Heartbeat   |
|             v                                                       v Thread      |
|  +---------------------+   Distributed State / Lock      +---------------------+  |
|  | Context Propagation |  <============================> |  Long-Running LLM   |  |
|  |  (Trace Context)    |   Redis (Redlock + Checkpoints) |   Inference / Tools |  |
|  +---------------------+                                 +----------+----------+  |
|                                                                     |             |
|                                                                     v             |
|  +---------------------+                                 +---------------------+  |
|  | Dead Letter Queue   |  <============================  | Event Egress Engine |  |
|  | (DLQ / Poison Pill) |       On Failure / Timeout      | (Producer / Sinks)  |  |
|  +---------------------+                                 +---------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Komponen Arsitektur Internal:

1. **Ingress Event Gateway & Schema Enforcement:**
   Setiap instruksi atau pemicu (*trigger*) masuk melalui gateway yang memvalidasi *payload* terhadap skema kontrak yang ketat (menggunakan Pydantic/Protobuf/Avro) sebelum masuk ke *message broker*. Gateway bertindak sebagai produsen (*producer*) murni yang tidak terikat waktu eksekusi agen.

2. **Distributed Checkpointing & State Store:**
   Agen tidak menyimpan *state* pada memori lokal kontainer. Memori eksekusi, jejak histori (*scratchpad*), dan status *graph execution* dipersistensikan secara atomik ke *shared distributed state store* (seperti PostgreSQL dengan JSONB/Pgvector atau Redis) menggunakan *versioned snapshotting*. Hal ini memungkinkan pemulihan instan jika pod/kontainer pekerja mati di tengah siklus penalaran.

3. **Isolated Heartbeat & Concurrency Management:**
   *Broker consumer group* (seperti Kafka Consumer) mewajibkan *heartbeat* reguler. LLM reasoning call yang memakan waktu 15–90 detik dapat memicu *consumer group rebalance* jika dijalankan pada thread/loop yang sama dengan *poller*. Arsitektur produksi memisahkan *poll loop* dari *execution engine* menggunakan arsitektur *producer-consumer internal queue* atau thread terpisah, menjaga *consumer liveness* tetap terisolasi dari *LLM I/O latency*.

4. **Distributed Concurrency Lock (Redlock Engine):**
   Mencegah *race condition* pada manipulasi *state* pengguna atau entitas yang sama oleh dua event paralel. Lock diambil dengan batas TTL yang diperpanjang secara otomatis (*heartbeat lock extension*) selama proses penalaran agen masih berjalan.

5. **Egress Dispatcher & Saga Orchestration:**
   Output dari agen tidak dikembalikan sebagai respons HTTP langsung, melainkan dipublikasikan kembali ke topik event hilir (`agent.executions.completed` atau `agent.executions.failed`). Jika alur kerja membutuhkan koordinasi lintas agen (misal: *Researcher Agent* -> *Coder Agent* -> *Tester Agent*), orkestrator memproses event keluaran agen sebelumnya untuk mentransisikan *state machine* global menggunakan pola *Saga (Choreographed atau Orchestrated)*.

---

### 4. Why & What

| Dimensi | Synchronous RPC / REST Agents | Asynchronous Event-Driven Agents |
| :--- | :--- | :--- |
| **Model Eksekusi** | *Blocking* / *Semi-blocking thread-per-request*. | *Fully Decoupled Non-blocking Message Passing*. |
| **Ketahanan Jaringan** | Rentan putus koneksi (*broken pipe*) saat LLM mengalami latensi tinggi. | Sangat toleran; status tersimpan di broker, klien dapat memutus koneksi. |
| **Skalabilitas Worker** | Terbatas oleh *HTTP socket descriptor* dan *thread pool size*. | Elastis; *auto-scale* berdasarkan *topic lag* / antrean pesan. |
| **Toleransi Kegagalan** | Request gagal total jika server crash di tengah *tool execution*. | Event dapat diproses ulang (*re-delivered*) dari titik kegagalan (*checkpoint*). |
| **Manajemen Beban** | Risiko *thundering herd* menembus kuota rate limit LLM provider. | Terkendali melalui *bounded consumer concurrency* dan *rate-limited pollers*. |
| **Observabilitas** | Mudah dilacak via header HTTP standar. | Membutuhkan propagasi manual *W3C Trace Context* dalam event envelope. |

#### Alasan Beralih ke Event-Driven:
LLM adalah dependensi probabilistik dengan *non-deterministic latency*. Eksekusi rantai agen (*agentic loops*) yang melibatkan perulangan *thought-action-observation* dapat berlangsung dari hitungan detik hingga beberapa menit. 

Memaksakan paradigma *request-response* sinkronus pada beban kerja ini menghasilkan arsitektur yang rapuh (*brittle*). Event-driven architecture mengisolasi produsen instruksi dari eksekutor, meratakan lonjakan beban (*load leveling*), dan memampukan *backpressure management* otomatis saat kuota inferensi eksternal mendekati batas kritis.

---

### 5. How (Workflow Detail)

Alur kerja operasional eksekusi tugas pada arsitektur agen berbasis event diatur melalui tahapan berikut:

```
[External Event] 
       │
       ▼
1. Validation & Tracing Injection (Producer)
       │
       ▼
2. Write to Topic: `agent.tasks`
       │
       ▼
3. Worker Fetch Event (Kafka/Redis Consumer)
       │
       ├─► Check In-Memory/Redis Idempotency Store (Dedup Key)
       │     └─► Exists? ──► ACK Broker & Discard Event
       │
       ├─► Acquire Distributed Redlock (Target Entity ID)
       │     └─► Lock Failed? ──► NACK & Re-queue / Sleep Backoff
       │
       ├─► Separate Background Heartbeat Task (Keep Alive Kafka & Lock)
       │
       ├─► Load Agent Session Checkpoint (State Store)
       │
       ├─► Execute Agent Cognitive Loop (ReAct, Tools, LLM Calls)
       │
       ├─► Persist Updated State Checkpoint (Atomic Update)
       │
       ├─► Release Distributed Lock
       │
       ├─► Publish to Egress Topic (`agent.results` / `agent.mutations`)
       │
       └─► Manual Offset Commit (ACK Message to Broker)
```

1. **Ingress & Correlation:** Gateway menerima instruksi, menyuntikkan `traceparent`, `causation_id`, `correlation_id`, dan `idempotency_key` ke dalam metadata envelope, kemudian menerbitkan event ke broker.
2. **Atomic Ingestion:** Worker mengambil pesan. Sebelum komputasi dimulai, worker memeriksa `idempotency_key` pada Redis Cache dengan operasi `SETNX`. Jika key telah ada (sedang diproses atau selesai), pesan diabaikan dan langsung di-*commit*.
3. **Locking & Boundary Protection:** Worker mengunci *session identifier* menggunakan Redis Distributed Lock. Ini mencegah agen paralel lain memanipulasi riwayat percakapan atau state entitas yang sama.
4. **Execution Isolation:** Thread komputasi agen dijalankan secara asinkron. Sebuah task independen di *background* memperpanjang sewa lock (*lock extension*) dan mengirimkan *heartbeat* ke broker untuk mencegah rebalancing consumer group.
5. **State Commitment & Outbox:** Setelah loop kognitif tuntas, checkpoint *state* ditulis ke PostgreSQL/Redis. Event hasil akhir dipancarkan ke antrean keluaran menggunakan pola *Transactional Outbox* untuk menjamin konsistensi antara data yang tersimpan dan event yang dikirim.
6. **Offset Acknowledgment:** Hanya setelah state tersimpan dan event hasil dipancarkan, worker melakukan *manual commit offset* ke broker.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan **Synchronous REST Agent** seperti seorang pelanggan yang menelepon seorang analis intelijen dan tetap memegang gagang telepon selama sang analis pergi ke perpustakaan, membaca 10 buku, menelepon kantor cabang, dan menulis laporan. Jika kabel telepon terputus di menit ke-15, seluruh usaha terbuang sia-sia dan analis harus mengulang dari awal.

Sebaliknya, **Event-Driven Agent** beroperasi seperti **Pusat Pengendali Operasi Penerbangan (Airport Ground Control)**:
Setiap instruksi masuk berupa surat tugas terdaftar (*Event Card*) yang dimasukkan ke kotak surat (*Kafka Partition*). Petugas pelaksana (*Worker*) mengambil kartu tugas, mencatat stempel waktu, menaruh papan "Sedang Dikerjakan" di loker pesawat (*Distributed Lock*), mengeksekusi tugas secara bertahap, mencatat log di buku induk (*State Store*), dan jika selesai, melempar berkas laporan ke baki "Penerbangan Siap Lepas Landas" (*Egress Event*). Jika petugas pingsan di tengah jalan, papan penanda otomatis kedaluwarsa, petugas lain melihat kartu tugas di buku induk, dan melanjutkan proses dari pos pemeriksaan terakhir tanpa mengulang dari nol.

#### Diagram Topologi Produksi

```
                              ┌────────────────────────────────────────┐
                              │            Event Bus (Kafka)           │
                              │  Topics:                               │
                              │  - core.orders.created (Partitioned)   │
                              │  - agent.evaluations.dlq               │
                              │  - agent.actions.executed              │
                              └───────┬────────────────────────▲───────┘
                                      │                        │
                     Fetch Payload    │                        │ Emit Action Event
                  ┌───────────────────┘                        └───────────────────┐
                  │                                                                │
                  ▼                                                                │
┌─────────────────────────────────────────────────────────────┐                    │
│                      AGENT WORKER DAEMON                    │                    │
│                                                             │                    │
│  ┌────────────────────────┐     ┌────────────────────────┐  │                    │
│  │ Broker Consumer Engine │     │ Deduplication Guard    │  │                    │
│  │ (AsyncIO Poller)       │────►│ (Redis SETNX Check)    │  │                    │
│  └──────────┬─────────────┘     └───────────┬────────────┘  │                    │
│             │                               │               │                    │
│             │ Keep-Alive Heartbeat          │ Acquire Lock  │                    │
│             ▼                               ▼               │                    │
│  ┌────────────────────────┐     ┌────────────────────────┐  │                    │
│  │ Lock Lease Extender    │     │ Distributed Redlock    │  │                    │
│  │ (TTL Watchdog)         │     │ (Resource Contention)  │  │                    │
│  └────────────────────────┘     └───────────┬────────────┘  │                    │
│                                             │               │                    │
│                                             ▼               │                    │
│                                 ┌────────────────────────┐  │                    │
│                                 │ Agent Cognitive Core   │  │                    │
│                                 │ (LLM / Tool Invocation)│  │                    │
│                                 └───────────┬────────────┘  │                    │
│                                             │               │                    │
│                                             ▼               │                    │
│                                 ┌────────────────────────┐  │                    │
│                                 │ Checkpoint Committer   │  │                    │
│                                 │ (Postgres / Redis Pg)  │──┼────────────────────┘
│                                 └────────────────────────┘  │ Manual ACK/Offset
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory Asynchronous Agent Loop dengan Concurrency Control
Implementasi dasar antrean pesan berbasis `asyncio.Queue` untuk memahami pemisahan antara penerima event dan eksekutor LLM dengan pembatasan konkurensi (*backpressure sederhana*).

```python
import asyncio
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@dataclass
class AgentTaskEvent:
    event_id: str
    session_id: str
    payload: Dict[str, Any]

class SimpleAsyncAgentWorker:
    def __init__(self, queue: asyncio.Queue, concurrency_limit: int = 2):
        self.queue = queue
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def simulate_llm_inference(self, prompt: str) -> str:
        # Simulasi latensi eksekusi kognitif LLM
        await asyncio.sleep(2.0)
        return f"LLM Output for: {prompt}"

    async def process_task(self, event: AgentTaskEvent) -> None:
        async with self.semaphore:
            logging.info(f"Processing event: {event.event_id} on session {event.session_id}")
            result = await self.simulate_llm_inference(event.payload.get("instruction", ""))
            logging.info(f"Finished event {event.event_id}: {result}")

    async def run(self) -> None:
        while True:
            event = await self.queue.get()
            # Jalankan worker tanpa memblokir perulangan antrean
            asyncio.create_task(self.process_task(event))
            self.queue.task_done()

async def main():
    task_queue = asyncio.Queue()
    worker = SimpleAsyncAgentWorker(queue=task_queue, concurrency_limit=2)
    
    # Jalankan consumer daemon di background
    worker_task = asyncio.create_task(worker.run())

    # Menembakkan beberapa event secara asinkron
    for i in range(5):
        event = AgentTaskEvent(
            event_id=str(uuid.uuid4()),
            session_id=f"session-{i % 2}",
            payload={"instruction": f"Analisis risiko audit transaksi #{1000 + i}"}
        )
        await task_queue.put(event)

    await task_queue.join()
    worker_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
```

---

#### B. Practical Example: Enterprise-Grade Event-Driven Consumer Agent (Redis Streams + Redlock + OTel Trace Injection + Resilient Tool Calling)
Implementasi skala produksi yang siap di-deploy menggunakan Redis Streams sebagai message bus, Redis distributed lock, Pydantic schemas, trace propagation, dan fallback Dead Letter Queue (DLQ).

```python
from __future__ import annotations
import asyncio
import json
import logging
import sys
import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ValidationError
import redis.asyncio as aioredis

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "trace_id":"%(name)s", "message":"%(message)s"}',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EnterpriseAgentSystem")

# --- CONTRACT DEFINITIONS ---
class TracingContext(BaseModel):
    traceparent: str = Field(default_factory=lambda: f"00-{uuid.uuid4().hex}-0000000000000001-01")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class TaskPayload(BaseModel):
    account_id: str
    transaction_id: str
    amount: float
    currency: str = "USD"
    instruction: str

class AgentEventEnvelope(BaseModel):
    event_id: str
    idempotency_key: str
    timestamp: float = Field(default_factory=time.time)
    tracing: TracingContext
    payload: TaskPayload

# --- PRODUCTION EVENT-DRIVEN AGENT ENGINE ---
class ProductionEventDrivenAgent:
    def __init__(
        self,
        redis_client: aioredis.Redis,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        dlq_stream_name: str
    ):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.dlq_stream_name = dlq_stream_name
        self.is_running = False

    async def initialize_consumer_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id="0",
                mkstream=True
            )
            logger.info(f"Consumer group '{self.group_name}' initialized.")
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group '{self.group_name}' already exists.")
            else:
                raise e

    async def acquire_distributed_lock(self, lock_key: str, ttl_ms: int = 15000) -> Optional[str]:
        lock_token = str(uuid.uuid4())
        # NX: set if not exist, PX: millisecond TTL
        acquired = await self.redis.set(f"lock:{lock_key}", lock_token, nx=True, px=ttl_ms)
        return lock_token if acquired else None

    async def release_distributed_lock(self, lock_key: str, lock_token: str) -> None:
        # Atomic lock release using Lua script to avoid releasing someone else's expired lock
        lua_release = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(lua_release, 1, f"lock:{lock_key}", lock_token)

    async def check_and_set_idempotency(self, idempotency_key: str, ttl_sec: int = 86400) -> bool:
        # Menolak jika key sudah dieksekusi dalam 24 jam terakhir
        is_first_entry = await self.redis.set(f"idempotency:{idempotency_key}", "PROCESSING", nx=True, ex=ttl_sec)
        return bool(is_first_entry)

    async def mark_idempotency_complete(self, idempotency_key: str, ttl_sec: int = 86400) -> None:
        await self.redis.set(f"idempotency:{idempotency_key}", "COMPLETED", xx=True, ex=ttl_sec)

    async def execute_agent_reasoning(self, envelope: AgentEventEnvelope) -> Dict[str, Any]:
        """
        Simulasi Core Cognitive Loop: ReAct Framework / Autonomous Tool Execution
        """
        logger.info(
            f"Agent cognitive step started. Causation ID: {envelope.tracing.correlation_id}",
            extra={"trace_id": envelope.tracing.traceparent}
        )
        # Simulasi LLM Token Generation + I/O network tool call
        await asyncio.sleep(1.5)

        # Logika deterministic evaluator
        is_fraud = envelope.payload.amount > 10000.0
        reasoning_decision = {
            "verdict": "FLAG_SUSPICIOUS" if is_fraud else "APPROVE",
            "confidence": 0.98 if is_fraud else 0.99,
            "tool_executions": ["aml_blacklisted_check", "geolocation_risk_matrix"],
            "processed_at": time.time()
        }
        return reasoning_decision

    async def send_to_dead_letter_queue(self, raw_message: Dict[Any, Any], error_reason: str) -> None:
        dlq_payload = {
            "original_payload": json.dumps(raw_message),
            "failure_reason": error_reason,
            "failed_at": str(time.time()),
        }
        await self.redis.xadd(self.dlq_stream_name, dlq_payload)
        logger.warning(f"Message diverted to DLQ: {error_reason}")

    async def process_event(self, message_id: str, raw_data: Dict[bytes, bytes]) -> None:
        decoded_data = {k.decode("utf-8"): v.decode("utf-8") for k, v in raw_data.items()}

        try:
            # 1. Validation & Schema Enforcement
            envelope_data = json.loads(decoded_data.get("data", "{}"))
            envelope = AgentEventEnvelope.model_validate(envelope_data)
        except (ValidationError, json.JSONDecodeError) as err:
            logger.error(f"Malformed payload. Dropping to DLQ: {err}")
            await self.send_to_dead_letter_queue(decoded_data, f"Validation failure: {str(err)}")
            await self.redis.xack(self.stream_name, self.group_name, message_id)
            return

        # 2. Check Idempotency Barrier
        is_new_event = await self.check_and_set_idempotency(envelope.idempotency_key)
        if not is_new_event:
            logger.info(f"Duplicate event detected: {envelope.idempotency_key}. Acknowledging without re-run.")
            await self.redis.xack(self.stream_name, self.group_name, message_id)
            return

        # 3. Distributed Lock Execution Boundary
        lock_token = await self.acquire_distributed_lock(envelope.payload.account_id)
        if not lock_token:
            logger.warning(f"Entity account_id={envelope.payload.account_id} locked by another worker. Rescheduling.")
            # NACK: Tidak di-ACK, pesan akan tetap di Pel (Pending Entries List) untuk diambil retry nanti
            return

        try:
            # 4. Core Reasoning Execution
            decision = await self.execute_agent_reasoning(envelope)

            # 5. Emit Outbox / Next State Event
            egress_event = {
                "parent_event_id": envelope.event_id,
                "correlation_id": envelope.tracing.correlation_id,
                "decision": json.dumps(decision)
            }
            await self.redis.xadd("agent.evaluations.completed", egress_event)

            # 6. Finalize Transaction State & ACK Broker
            await self.mark_idempotency_complete(envelope.idempotency_key)
            await self.redis.xack(self.stream_name, self.group_name, message_id)
            logger.info(f"Task {envelope.event_id} successfully finalized and ACKed.")

        except Exception as exc:
            logger.critical(f"Unrecoverable runtime error during agent cycle: {exc}", exc_info=True)
            # Revert processing flag so event can be retried if ephemeral
            await self.redis.delete(f"idempotency:{envelope.idempotency_key}")
            await self.send_to_dead_letter_queue(decoded_data, f"Runtime failure: {str(exc)}")
            await self.redis.xack(self.stream_name, self.group_name, message_id)
        finally:
            await self.release_distributed_lock(envelope.payload.account_id, lock_token)

    async def start(self) -> None:
        self.is_running = True
        await self.initialize_consumer_group()
        logger.info(f"Worker {self.consumer_name} started polling from {self.stream_name}...")

        while self.is_running:
            try:
                # Read 1 message at a time, block max 2000ms
                response = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=1,
                    block=2000
                )

                if not response:
                    await asyncio.sleep(0.1)
                    continue

                for _, stream_messages in response:
                    for message_id_bytes, raw_payload in stream_messages:
                        msg_id = message_id_bytes.decode("utf-8")
                        await self.process_event(msg_id, raw_payload)

            except asyncio.CancelledError:
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Polling loop unexpected exception: {e}")
                await asyncio.sleep(1.0)

    async def stop(self) -> None:
        self.is_running = False
        await self.redis.aclose()


# --- HARNESS SIMULATION ---
async def test_driver():
    redis_instance = aioredis.from_url("redis://localhost:6379", decode_responses=False)
    
    # Bersihkan environment uji
    await redis_instance.flushall()

    stream_topic = "financial.transactions"
    dlq_topic = "financial.transactions.dlq"
    group = "risk_evaluator_group"

    agent_worker = ProductionEventDrivenAgent(
        redis_client=redis_instance,
        stream_name=stream_topic,
        group_name=group,
        consumer_name="node-us-east-1a",
        dlq_stream_name=dlq_topic
    )

    worker_task = asyncio.create_task(agent_worker.start())

    # 1. Publish Normal High-Risk Task
    valid_task = AgentEventEnvelope(
        event_id="evt_01",
        idempotency_key="idemp_hash_001",
        tracing=TracingContext(),
        payload=TaskPayload(
            account_id="ACC_88190",
            transaction_id="TX_9921",
            amount=15500.0,
            instruction="Analisis pola pencucian uang instan lintas perbatasan."
        )
    )
    await redis_instance.xadd(stream_topic, {"data": valid_task.model_dump_json()})

    # 2. Publish Duplicate Task (Harus tertelan idempotency guard)
    await redis_instance.xadd(stream_topic, {"data": valid_task.model_dump_json()})

    # 3. Publish Corrupted/Poison-Pill Payload (Harus dialihkan ke DLQ tanpa menumbangkan worker)
    await redis_instance.xadd(stream_topic, {"data": "CORRUPTED_NON_JSON_DATA"})

    # Berikan waktu untuk consumer mengeksekusi
    await asyncio.sleep(5.0)

    # Verifikasi Isi DLQ
    dlq_records = await redis_instance.xlen(dlq_topic)
    logger.info(f"Verified DLQ Depth: {dlq_records} message(s)")

    # Cleanup
    worker_task.cancel()
    await agent_worker.stop()

if __name__ == "__main__":
    try:
        asyncio.run(test_driver())
    except KeyboardInterrupt:
        pass
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Global FinTech: Autonomous Financial Crime & Anti-Money Laundering (AML) Mesh
* **Konteks Skala:** Institusi perbankan tier-1 dengan volume 50.000 transaksi/detik secara global. Setiap transaksi berisiko medium-tinggi wajib dievaluasi oleh sistem agen multi-tahap (Graph Analyzer, Historical Behaviour Analyzer, External Watchlist Verification, dan SAR Document Generator).
* **Masalah Awal (REST Monolith):** Sistem sebelumnya memanggil Agent Service via Synchronous gRPC. Saat terjadi lonjakan Black Friday, latensi inferensi LLM (~2.8 detik) membuat antrean HTTP gateway meluap (*gateway timeouts 504*), 18% panggilan *dropped*, dan memory leak menyebabkan cascading failure pada seluruh cluster microservices.
* **Arsitektur Solusi (Event-Driven Agentic Mesh):**
  1. **Ingress Invalidation:** Mengganti HTTP endpoints dengan Apache Kafka (32 Partisi berdasar `hash(account_id)`). Transaksi langsung di-commit ke Kafka dalam 4 milidetik.
  2. **Worker Isolation:** Agent Worker Pool dikelompokkan dalam Kubernetes HPA (Horizontal Pod Autoscaler) yang dikendalikan oleh metrik KEDA (*Kubernetes Event-driven Autoscaling*) berdasarkan **Consumer Lag**, bukan CPU/Memory.
  3. **Distributed Sagas & Idempotency:** Jika LLM mendeteksi pola pencucian uang, worker tidak memanggil API internal Core Banking secara sinkron. Worker memancarkan event `aml.flagged.suspicious`. Event ini dikonsumsi oleh orkestrator Saga yang memicu pemblokiran rekening secara asinkron.
  4. **Hasil Produksi:** 
     * Ketersediaan sistem (*Uptime*) melonjak dari 97.4% menjadi **99.995%**.
     * Drop rate transaksi: **0%** (seluruh event tersimpan di Kafka storage cluster berdurasi 7 hari).
     * Penghematan biaya komputasi sebesar 34% berkat perataan kurva konsumsi beban (*load-leveling*).

---

### 9. Trade-offs

Desain arsitektur event-driven mengharuskan rekayasawan menimbang kompromi trade-off berikut:

```
+───────────────────────────+────────────────────────────────────────────────────────+
| Aspek Desain              | Trade-offs / Dampak Sistem                             |
+───────────────────────────+────────────────────────────────────────────────────────+
| Event-Driven (Asinkron)   | [+] Bebas timeout, decoupled, backpressure terkontrol. |
| vs Synchronous (REST/RPC) | [-] Kompleksitas tracing tinggi, debugging sulit,       |
|                           |     tidak ramah interaksi UI instan (membutuhkan SSE/  |
|                           |     WebSocket untuk pembaruan status ke klien akhir).  |
+───────────────────────────+────────────────────────────────────────────────────────+
| Exactly-Once Semantics    | [+] Menghindari re-eksekusi tools (cth: double debit). |
| vs At-Least-Once Delivery | [-] Overhead kinerja signifikan, koordinasi distributed|
|                           |     transaksi dua fase (2PC) menurunkan throughput 60%.|
+───────────────────────────+────────────────────────────────────────────────────────+
| In-Memory Agent Memory    | [+] Latensi eksekusi sangat rendah (<1ms akses memory).|
| vs Externalized Store     | [-] Kehilangan seluruh konteks penalaran jika node pod |
| (Redis / Distributed Pg)  |     mati terkena Kubernetes OOMKilled atau evictions.  |
+───────────────────────────+────────────────────────────────────────────────────────+
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. Consumer Group Rebalance Akibat Latensi Inferensi LLM
* **Gejala:** Worker log menampilkan pesan `CommitFailedException` atau consumer berulang kali terlempar dari Kafka group (*eviction*) setiap kali agen menganalisis dokumen panjang.
* **Root Cause:** Default Kafka `max.poll.interval.ms` (misal 5 menit) terlewati karena loop penalaran agen memblokir thread/loop yang sama dengan poller Kafka, sehingga heartbeat berhenti dikirim.
* **Troubleshooting & Remediasi:** Jangan pernah menjalankan LLM reasoning langsung di thread konsumsi utama. Gunakan arsitektur *Internal Decoupled Worker*: Loop poller Kafka hanya bertugas mengambil event dan memasukannya ke `asyncio.Queue` lokal internal, sementara satu task latar belakang khusus terus menerus memanggil `poll()` untuk mengirim *liveness heartbeat*.

#### 2. Poison Pill Events & Infinite Crash-Loops
* **Gejala:** Satu event spesifik memicu *unhandled exception* (misal: parsing JSON gagal atau token context window melebihi kapasitas LLM), menyebabkan container crash, restart, membaca kembali event yang sama dari offset terakhir, dan crash lagi selamanya (*CrashLoopBackOff*).
* **Root Cause:** Ketiadaan blok pengaman (*circuit breaker/dead-letter mechanism*) yang menangkap error sebelum mencapai batas toleransi restart broker.
* **Troubleshooting & Remediasi:** Terapkan semantik *Max Retries via Header Counter*. Jika retry melebihi ambang batas (misal: 3 kali), secara terprogram interupsi alur, emit event ke Dead Letter Queue (DLQ), dan majukan (*commit*) offset pesan tersebut.

#### 3. Redlock Deadlock / Split-Brain Execution
* **Gejala:** State agen terdistorsi karena dua instance worker mengupdate memori percakapan entitas yang sama secara bersamaan.
* **Root Cause:** Nilai TTL pada Redlock terlalu pendek. Worker A mengalami *garbage collection pause* atau jeda jaringan LLM, lock kedaluwarsa, Worker B mengambil lock untuk entitas yang sama, kemudian Worker A bangkit dan menulis datanya secara tumpang tindih.
* **Troubleshooting & Remediasi:** Terapkan teknik *Watchdog Lease Extension* (mirip mekanisme Redisson). Selama coroutine agen berstatus aktif berjalan, background timer secara berkala memperbarui sisa TTL Redis Lock hingga statusnya secara eksplisit ditutup dalam blok `finally`.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis sistem agent event-driven ke produksi:

- [ ] **Schema Registry Enforcement:** Validasi semua payload masuk dan keluar menggunakan schema validation library (Pydantic V2 / Avro Schema Registry) dengan opsi `extra="forbid"`.
- [ ] **Context Injection W3C:** Metadata event wajib menyertakan atribut `traceparent`, `tracestate`, dan `correlation_id` untuk visibilitas OpenTelemetry lintas microservices.
- [ ] **Partition Keying Strategy:** Tentukan partition key berdasarkan *Entity ID* (misal: `account_id` atau `session_id`), bukan acak (*round-robin*). Ini menjamin bahwa urutan instruksi (*ordering*) untuk entitas yang sama selalu diproses sesuai kronologi pada satu partisi tunggal.
- [ ] **Idempotent Guard:** Pastikan setiap eksekusi tool berstatus *safe-to-retry* atau dilindungi oleh distributed idempotency keys pada database level.
- [ ] **Dead Letter Queue (DLQ) Monitoring:** Konfigurasikan alarm metrik alerting (Prometheus/PagerDuty) saat laju masuk DLQ melebihi ambang 0.1% dari total throughput traffic.
- [ ] **Graceful Shutdown Hooks:** Daftarkan penanganan sinyal sistem `SIGTERM` dan `SIGINT` untuk menghentikan konsumsi pesan baru, menyelesaikan transaksi yang sedang berada di tengah-tengah pemanggilan tool, melepaskan distributed lock, dan melakukan commit offset terakhir sebelum proses dihentikan.
- [ ] **Backpressure Throttling:** Pantau kuota TPM (*Tokens Per Minute*) dan RPM (*Requests Per Minute*) dari penyedia LLM. Sambungkan sistem pembaca event ke rate-limiter sentral (Token Bucket) untuk memperlambat *consumer poll rate* secara dinamis ketika kuota hampir habis.

---

### 12. Hands-on Practice

Panduan laboratorium terarah untuk membangun sistem event-driven agent lokal yang tangguh terhadap *poison pill* dan *duplicate execution*.

#### File Layout Setup (`hands-on/m02/`)
```
hands-on/m02/
├── docker-compose.yml
├── requirements.txt
├── schemas.py
└── worker.py
```

#### Langkah 1: Siapkan Environment Infrastruktur
Buat berkas `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'
services:
  redis-broker:
    image: redis:7.2-alpine
    container_name: m02-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
```
Jalankan instance:
```bash
cd hands-on/m02/
docker compose up -d
```

#### Langkah 2: Setup Dependencies
Buat berkas `hands-on/m02/requirements.txt`:
```txt
redis==5.0.1
pydantic==2.6.0
```
Instalasi dependencies pada virtual environment Anda:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Langkah 3: Eksekusi File Worker
Salin kode praktis pada **Seksi 7B (Practical Example)** ke dalam berkas `hands-on/m02/worker.py`. Jalankan consumer daemon:
```bash
python worker.py
```

#### Langkah 4: Verifikasi Resiliensi
Buka terminal baru untuk memantau stream langsung pada Redis CLI:
```bash
docker exec -it m02-redis redis-cli

# Periksa status pesan sukses
XREAD STREAMS agent.evaluations.completed 0-0

# Periksa pesan yang dilempar ke DLQ karena poison payload
XREAD STREAMS financial.transactions.dlq 0-0

# Periksa key idempotensi yang tersimpan
KEYS idempotency:*
```

---

### 13. Exercise

#### Level 1 (Easy)
Tambahkan mekanisme *Exponential Backoff Retry* lokal pada method `execute_agent_reasoning()`. Jika fungsi LLM mengalami `TimeoutError`, fungsi harus mencoba ulang maksimal 3 kali dengan jeda eksponensial (1s, 2s, 4s) sebelum menaikkan exception ke penanganan tingkat atas.

#### Level 2 (Medium)
Modifikasi engine pada `worker.py` agar mendukung fitur **Sliding Window Rate Limiter**. Batasi worker agar hanya memproses maksimal 5 eksekusi tugas per 10 detik secara terpusat menggunakan struktur data Redis Sorted Set (`ZREVRANGEBYSCORE`). Jika kuota penuh, tunda konsumsi pesan dari broker tanpa membuat Kafka me-rebalance worker.

#### Level 3 (Hard)
Bangun arsitektur **Choreographed Dual-Agent Pipeline**. Buat dua worker independen:
1. `ClassifierAgentWorker`: Mengonsumsi event teks mentah dari stream `input.tickets`, mengekstraksi sentimen serta tingkat urgensi, lalu memancarkan event ke stream `tickets.classified`.
2. `ActionAgentWorker`: Mengonsumsi event dari `tickets.classified`. Jika urgensi berkategori "CRITICAL", ia memanggil tool notifikasi eksternal dan menulis hasil akhir ke `notifications.dispatched`. 
Pastikan kedua worker berkomunikasi secara strictly asynchronous, menerapkan *Distributed Trace ID propagation*, dan tahan banting terhadap crash pada salah satu worker.

---

### 14. Challenge

**Skenario Kasus Kompleks: "The Zero-Downtime Agent Topology Migration"**

* **Latar Belakang:** Anda adalah Lead Architect pada platform e-commerce enterprise. Sistem lama menggunakan sebuah agen monolitik ("OrderAgent") yang mengonsumsi stream `orders.events` dan menangani inventori, penipuan, dan konfirmasi email secara sekuensial. 
* **Target:** Anda diminta memecah monolit ini menjadi 3 micro-agents independen yang berbasis EDA (*InventoryAgent*, *FraudAgent*, *CommunicationAgent*) yang berjalan secara paralel (*fan-out pattern*).
* **Kondisi & Batasan Ekstrem:**
  1. Topik `orders.events` memiliki beban konstan 12.000 events/detik tanpa toleransi downtime atau penghentian publisher.
  2. Migrasi tidak boleh menghasilkan **duplikasi aksi** (seperti pengiriman email ganda atau pemotongan inventori dua kali).
  3. Ada 150.000 transaksi yang statusnya saat ini masih berada di tengah eksekusi ("In-Flight") pada sistem lama.
* **Tugas Anda:** Rancang dokumen arsitektur dan strategi implementasi teknis (beserta pseudocode orchestration/routing layer) yang menguraikan:
  - Strategi *Dual-Writing* atau *Shadow Pipeline*.
  - Mekanisme rekonsiliasi state menggunakan *Distributed Feature Flags* dan *Transactional Outbox*.
  - Strategi penanganan kegagalan (*compensating transactions*) jika salah satu dari 3 agen baru gagal mengeksekusi tugas pada arsitektur fan-out baru tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### Sesi 1: Basic (5 Pertanyaan)
1. **Mengapa pemanggilan REST API sinkronus langsung ke LLM dianggap sebagai anti-pattern pada agentic system skala besar?**
   * A. Karena LLM tidak mendukung protokol HTTP.
   * B. Karena socket HTTP rentan putus akibat latensi penalaran yang panjang, memicu *cascading failures* dan kehabisan *connection pool*.
   * C. Karena broker pesan lebih murah dibandingkan dengan server REST.
   * D. Karena REST API tidak memungkinkan pemakaian format JSON.
   *(Jawaban: B — Non-deterministic latency dari LLM membebani socket connection pool pada caller).*

2. **Apa fungsi utama dari `idempotency_key` pada arsitektur agen berbasis pesan?**
   * A. Mempercepat laju inferensi token LLM.
   * B. Mengenkripsi payload sebelum masuk ke message broker.
   * C. Memastikan bahwa pesan yang dikirim berulang (*at-least-once delivery*) tidak mengeksekusi ulang aksi atau mutasi state yang sama.
   * D. Mengelompokkan consumer ke dalam partisi yang identik.
   *(Jawaban: C — Idempotensi menjamin determinisme hasil meskipun broker mendeliver pesan lebih dari sekali).*

3. **Komponen apa yang digunakan untuk menampung event yang secara permanen gagal divalidasi atau diproses agar antrean utama tidak terblokir?**
   * A. Ingress API Gateway.
   * B. Dead Letter Queue (DLQ).
   * C. Distributed Locking Manager.
   * D. Ephemeral Scratchpad Memory.
   *(Jawaban: B — DLQ menampung poison pills agar pemrosesan event sehat lainnya terus berjalan).*

4. **Dalam paradigma Event-Driven, bagaimana cara melacak urutan pemanggilan antar-agen yang berlangsung secara asinkron melintasi berbagai message stream?**
   * A. Dengan melihat log sistem operasi Linux lokal worker.
   * B. Mengandalkan `timestamp` dari database terpusat.
   * C. Menyuntikkan W3C Trace Context (`traceparent` dan `correlation_id`) ke dalam metadata event envelope.
   * D. Membaca pesan satu per satu secara manual.
   *(Jawaban: C — W3C Trace Context menjamin kesinambungan observability secara distributed).*

5. **Apa kegunaan dari distributed lock (seperti Redlock) saat worker agen membaca sebuah event?**
   * A. Mencegah partisi broker dari kepenuhan kapasitas disk.
   * B. Memastikan hanya ada satu worker yang memanipulasi *state* dari suatu entitas spesifik dalam satu waktu.
   * C. Mengamankan password worker dari ancaman kebocoran memori.
   * D. Menghentikan akses internet agen ke LLM provider.
   *(Jawaban: B — Mencegah *race condition* dan *concurrent writes* pada sesi/entitas yang sama).*

---

#### Sesi 2: Intermediate (5 Pertanyaan)
6. **Jika eksekusi penalaran agen memakan waktu 45 detik, risiko operasional apa yang dihadapi pada Kafka Consumer default, dan bagaimana solusinya?**
   * A. Broker akan menghapus topik secara otomatis; solusinya ubah setting disk retention.
   * B. `max.poll.interval.ms` terlampaui sehingga consumer dianggap mati dan memicu *rebalance storm*; solusinya pisahkan thread konsumsi/heartbeat dari worker eksekusi.
   * C. LLM provider akan memutus API key; solusinya rotasi kredensial per request.
   * D. Redis Stream akan otomatis berganti nama; solusinya gunakan database relasional.
   *(Jawaban: B — Poller broker wajib menjaga kontinuitas pengiriman sinyal heartbeat secara terisolasi).*

7. **Mengapa implementasi distributed lock pada Redis wajib dilepaskan menggunakan skrip Lua daripada perintah `DEL` standar?**
   * A. Karena perintah `DEL` standar tidak didukung oleh versi modern Redis.
   * B. Skrip Lua berjalan lebih cepat dibandingkan perintah dasar C pada Redis core.
   * C. Untuk menjamin atomisitas verifikasi token kepemilikan; memastikan worker tidak secara tidak sengaja menghapus lock milik worker lain yang diperoleh setelah lock miliknya kedaluwarsa.
   * D. Karena skrip Lua secara otomatis merestart worker jika terjadi kegagalan.
   *(Jawaban: C — Pola `if get(key) == token then del(key)` mencegah penghapusan lock lintas-proses yang tidak sah).*

8. **Pola arsitektur apa yang menjamin bahwa mutasi basis data internal agen dan penerbitan event hilir ke broker pesan berjalan secara atomik tanpa risiko *dual-write failure*?**
   * A. Command Query Responsibility Segregation (CQRS).
   * B. Transactional Outbox Pattern.
   * C. Peer-to-Peer Agent Mesh.
   * D. Model-View-Controller (MVC).
   *(Jawaban: B — Outbox pattern menyimpan perubahan data dan event dalam satu transaksi lokal database yang sama sebelum di-relay ke broker).*

9. **Apa perbedaan krusial antara Agent Choreography dan Agent Orchestration pada arsitektur asinkron?**
   * A. Choreography tidak menggunakan format JSON, Orchestration wajib JSON.
   * B. Choreography mengandalkan agen yang bereaksi terhadap event secara desentralisasi tanpa koordinator tunggal; Orchestration menggunakan satu controller terpusat yang mengatur transisi state antar-agen.
   * C. Choreography hanya dapat dijalankan di cloud AWS, sedangkan Orchestration di Kubernetes.
   * D. Orchestration lebih cepat daripada Choreography dalam segala situasi.
   *(Jawaban: B — Desentralisasi reaksi event vs kendali alur terpusat adalah pembeda inti).*

10. **Bagaimana cara menangani *Backpressure* saat agen mengonsumsi pesan dari Kafka namun kuota TPM (*Tokens Per Minute*) API LLM hilir telah menyentuh batas 95%?**
    * A. Segera hapus seluruh pesan yang tersisa di Kafka partition.
    * B. Matikan pod worker secara paksa (*hard-kill*).
    * C. Tunda (*pause/sleep*) pemanggilan loop polling Kafka atau kurangi *fetch size* secara terprogram tanpa memutus consumer group session.
    * D. Alihkan konsumsi traffic langsung ke server database utama.
    *(Jawaban: C — Memperlambat konsumsi pada layer consumer memungkinkan penyesuaian rate-limit tanpa kehilangan integritas status cluster).*

---

#### Sesi 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1:**
    Sebuah sistem perbankan multi-agen mendeteksi anomali di mana saldo rekening seorang nasabah terpotong dua kali untuk satu instruksi transfer agen yang sama. Setelah audit log, ditemukan bahwa worker pertama mengalami freeze sesaat (*Stop-the-world JVM/GC pause*) selama 20 detik saat memanggil tools payment, menyebabkan distributed lock kedaluwarsa. Worker kedua mengambil event yang sama dari antrean, dan keduanya mengeksekusi API pembayaran pihak ketiga. 
    **Pertanyaan Analisis:** Mekanisme arsitektur apa yang paling efektif untuk memitigasi kegagalan *split-brain/stale execution* ini secara permanen?
    * *Rasional Jawaban:* Terapkan teknik **Fencing Tokens** (token yang meningkat secara monoton setiap kali lock diambil) yang divalidasi oleh penerima aksi hilir/database, dikombinasikan dengan penyematan *Unique Idempotency Key* berbasis hash transaksi yang diverifikasi secara strictly atomik pada endpoint Third-Party Payment Gateway.

12. **Skenario Kasus 2:**
    Sebuah pipeline ekstraksi dokumen polis asuransi berbasis agen dijalankan di atas klaster Kubernetes dengan Kafka broker. Beberapa dokumen berukuran raksasa (500 halaman PDF) menyebabkan worker mengalami crash akibat *Out-of-Memory (OOM)*. Pod me-restart, mengambil kembali dokumen PDF yang sama dari offset Kafka yang belum di-ACK, dan mengalami OOM kembali. Kondisi ini membuat puluhan ribu dokumen klaim normal di belakangnya tertahan total (*head-of-line blocking*).
    **Pertanyaan Analisis:** Langkah mitigasi terstruktur apa yang harus diimplementasikan pada level gateway dan worker consumer?
    * *Rasional Jawaban:* 
      1. Terapkan validasi dimensi file (*payload guard*) di tingkat Ingress API Gateway; tolak atau pecah dokumen sebelum masuk antrean.
      2. Pada consumer, implementasikan *Claim-Check Pattern* di mana isi payload disimpan di Object Storage (S3) dan Kafka hanya membawa metadata referensi.
      3. Pasang *Retry-Count Header Tracking*; jika pesan yang sama diambil lebih dari $N$ kali tanpa berhasil mencapai commit (terdeteksi via interceptor), secara otomatis bypass pesan tersebut ke *Dead Letter Queue (DLQ)* dan pancarkan peringatan kritis ke tim operasional.

13. **Skenario Kasus 3:**
    Sistem Support Agent Anda menggunakan auto-scaling berbasis utilisasi CPU pod worker. Saat beban antrean tiket membludak dari 500 menjadi 50.000 pesan di broker, rata-rata CPU worker hanya tercatat sebesar 15% karena mayoritas waktu dihabiskan untuk menunggu I/O network response dari external LLM provider. Akibatnya, sistem tidak melakukan auto-scale dan latensi penanganan tiket membengkak dari 1 menit menjadi 6 jam.
    **Pertanyaan Analisis:** Metrik apa yang seharusnya menjadi pemicu scaling pada horizontal pod autoscaler (HPA) dan arsitektur apa yang wajib diubah?
    * *Rasional Jawaban:* Metrik autoscaling wajib dialihkan dari metrik berbasis sumber daya lokal kontainer (CPU/Memory) menjadi metrik **Consumer Lag Broker** (menggunakan KEDA / Prometheus Kafka Exporter). Kapasitas konkurensi worker per pod juga harus dimaksimalkan dengan pola IO non-blocking (`asyncio`) murni sehingga satu pod dapat menangani ratusan event yang menunggu I/O network secara paralel tanpa perlu menambah pod secara berlebihan.

---

### 16. Summary

1. **Dekopel Total Kognitif Agen:** Sistem agen di lingkungan enterprise tidak boleh digabungkan secara sinkronus dengan ingress layer. Pemisahan berbasis *event-driven architecture* (EDA) mutlak diperlukan untuk mengisolasi ketidakpastian latensi eksekusi LLM dari stabilitas platform.
2. **Determinisme Melalui Idempotensi:** Karena jaringan terdistribusi hanya mampu menjamin semantik *at-least-once delivery*, setiap komponen worker agen wajib menerapkan *idempotent boundary* (menggunakan hashing payload dan status check berbasis Redis/DB) guna mencegah eksekusi ganda pada tool yang menghasilkan mutasi finansial atau struktural.
3. **Observabilitas Sebagai Entitas Utama:** Komunikasi asinkronus menghilangkan visibilitas linear. Metadata W3C Trace Context wajib disuntikkan ke dalam envelope setiap event untuk mempertahankan riwayat penalaran (*reasoning chain*) end-to-end melintasi berbagai antrean broker dan worker cluster.
4. **Isolasi Kegagalan (Fault Containment):** Arsitektur produksi wajib dilengkapi pertahanan berlapis: pemisahan thread heartbeat poller, dynamic rate limiting, penanganan deadlock berbasis atomic distributed locking, serta perutean kegagalan deterministik ke *Dead Letter Queue* guna meniadakan risiko *poison-pill cascade*.