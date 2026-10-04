# Kurikulum Enterprise Python Engineering
## Topik: Python (02-Programming-Languages)
### BAB 10: Production-Ready Engineering & Microservices
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer enterprise mampu:
- Menguasai arsitektur internal event loop Python (`asyncio` engine, `uvloop`, dan integrasi libuv C-bindings) pada beban konkurensi ultra-tinggi (*high-throughput, low-latency*).
- Mendesain dan mengimplementasikan microservices berbasis komunikasi gRPC (HTTP/2 multiplexing + Protocol Buffers) dan RESTful (FastAPI/ASGI) dengan konektivitas non-blocking.
- Mengonfigurasi arsitektur runtime worker tingkat lanjut (*Gunicorn master process fork model* dipadukan dengan *Uvicorn worker ASGI pipelines*).
- Mengintegrasikan instrumen *distributed tracing* kontekstual (OpenTelemetry SDK), metrik Prometheus terstruktur, dan *structured zero-allocation JSON logging*.
- Membangun pola ketahanan sistem (*resilience patterns*): Distributed Circuit Breaker dengan state synchronization berbasis Redis, Concurrency Limiters (Bulkhead), dan Exponential Backoff dengan Jitter.
- Mengelola state connection pools yang aman untuk thread dan coroutine pada layer basis data (*asyncpg* / SQLAlchemy 2.0 async engine) guna mencegah leaking koneksi dan starvation.

---

### 2. Prerequisite

Sebelum mendalami modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- **Core Python**: Python 3.11/3.12 syntax, Type Hinting (`typing`, `Protocol`, generic typing), Context Managers (`__aenter__`, `__aexit__`), dan Descriptor Protocol.
- **Concurrency Fundamentals**: Perbedaan fundamental antara OS Threads, Multiprocessing, dan Cooperative Coroutines (Green Threads vs Asynchronous Generators).
- **Networking Protocol**: OSI Layer 4 vs Layer 7, handshake TCP/TLS, frame multiplexing HTTP/2, WebSocket, dan serialisasi payload biner vs teks.
- **Docker & Containerization**: Arsitektur Linux cgroups, namespaces, signal handling (`SIGTERM`, `SIGKILL`), dan multi-stage build.

---

### 3. Concept & Internal Architecture

Python microservices skala produksi menuntut pemahaman mendalam tentang bagaimana runtime CPython berinteraksi dengan sistem operasi host, memori, dan antrean event.

```
+-------------------------------------------------------------------------------+
|                       LINUX HOST OS (KERNEL SPACE)                            |
|    epoll (Linux) / kqueue (BSD/macOS) / IOCP (Windows) System Call Engine     |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ I/O Multiplexing (File Descriptors Readiness)
                                      ▼
+-------------------------------------------------------------------------------+
|                   UVLOOP ENGINE (C-BINDING / LIBUV LAYER)                     |
|  - Fast Epoll Abstraction   - Zero-Copy Buffers    - High-Resolution Timers  |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ uvloop C-API Bridge
                                      ▼
+-------------------------------------------------------------------------------+
|                        PYTHON ASYNCIO EVENT LOOP                              |
|  +------------------------+  +----------------------+  +--------------------+ |
|  | Task Queue / Ready Q   |  | Polling Mechanism    |  | Timer Heap (MinPQ) | |
|  | (collections.deque)    |  | (Non-blocking I/O)   |  | (heapq callbacks)  | |
|  +------------------------+  +----------------------+  +--------------------+ |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ Coroutine Evaluation (PEP 492)
                                      ▼
+-------------------------------------------------------------------------------+
|                     CPYTHON RUNTIME & MEMORY EXECUTION                        |
|  [Frame Execution Engine]  --> PyEval_EvalFrameDefault                        |
|  [GIL (Global Int. Lock)]  --> Released during Network/Socket Native Waits    |
|  [PyMalloc Allocator]      --> Small Objects Arenas (<512 bytes)              |
+-------------------------------------------------------------------------------+
```

#### 3.1. The Event Loop Internal Mechanics: `asyncio` vs `uvloop`
Event loop standar Python (`asyncio.SelectorEventLoop`) dibangun di atas modul built-in `selectors`, yang membungkus pemanggilan OS system call: `epoll()` pada Linux, `kqueue()` pada BSD/macOS. 

Saat coroutine menjalankan `await socket.recv()`, urutan internal yang terjadi adalah:
1. File descriptor (FD) dari socket didaftarkan ke OS Selector dengan event flag `EVENT_READ`.
2. Coroutine ditangguhkan (*suspended*); kontrol eksekusi frame memori dikembalikan ke dispatcher event loop melalui generator yield protocol.
3. Event loop mengevaluasi `epoll_wait()`. Di sini, **Global Interpreter Lock (GIL) dilepas** di layer C binding CPython, memungkinkan OS bekerja pada native level.
4. Ketika paket jaringan masuk ke NIC, kernel menandai FD siap dibaca. `epoll_wait()` mengembalikan FD aktif.
5. GIL diakuisisi kembali oleh CPython runtime.
6. Callback socket memindahkan data ke frame buffer dan menjadwalkan task terkait ke dalam `_ready` FIFO queue (`collections.deque`), menggeser status coroutine menjadi runnable untuk diproses pada tick berikutnya.

`uvloop` menggantikan seluruh implementasi `selectors` dan `asyncio.EventLoop` Python murni dengan implementasi native C yang membungkus `libuv` (mesin asinkron berkinerja tinggi yang sama dengan runtime Node.js). `uvloop` memangkas alokasi objek per-loop tick, memanfaatkan arena memori `libuv`, dan mengimplementasikan zero-copy memory buffers, melipatgandakan throughput konkurensi (I/O throughput naik 2x hingga 4x lipat dibanding native Python loop).

#### 3.2. Worker Architecture: Master-Process Preforking
Python tidak dapat mendistribusikan eksekusi coroutine lintas CPU core secara otomatis dalam satu proses karena batas proteksi GIL. Arsitektur produksi wajib menerapkan model **Preforking Master-Worker**:

```
                              +-----------------------+
                              |   GUNICORN (MASTER)   |
                              |  - Manages Workers    |
                              |  - Signal Coordinator |
                              |  - Binding TCP Socket |
                              +-----------------------+
                                     /    |    \
                      Fork Process  /     |     \  Fork Process
                                   /      |      \
                                  ▼       ▼       ▼
                     +-------------+ +-------------+ +-------------+
                     | Worker 1    | | Worker 2    | | Worker N    |
                     | (Uvicorn)   | | (Uvicorn)   | | (Uvicorn)   |
                     | +---------+ | | +---------+ | | +---------+ |
                     | | uvloop  | | | | uvloop  | | | | uvloop  | |
                     | +---------+ | | +---------+ | | +---------+ |
                     | | AsyncIO | | | | AsyncIO | | | | AsyncIO | |
                     | | Pipeline| | | | Pipeline| | | | Pipeline| |
                     | +---------+ | | +---------+ | | +---------+ |
                     +-------------+ +-------------+ +-------------+
```

1. **Master Process**: Berjalan sebagai proses supervisor root non-privileged. Membuka dan mengikat port socket listening (`SO_REUSEPORT` atau shared file descriptor).
2. **Worker Process (Worker 1..N)**: Master memanggil `os.fork()`. Setiap worker mewarisi file descriptor socket listening dan menginstansiasi instance `uvloop` baru.
3. **Connection Acceptance**: Kernel Linux mendistribusikan koneksi masuk (TCP SYN) langsung ke worker queue melalui `SO_REUSEPORT` kernel load balancing, meminimalisasi *thundering herd problem*.
4. **Lifecycle**: Jika worker mati karena *Segmentation Fault* atau *Out-Of-Memory (OOM)*, master process mendeteksi hilangnya PID via signal `SIGCHLD` dan secara deterministik me-re-spawn worker baru.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Flask / Sync Django / ThreadPool) | Pendekatan Modern Enterprise Microservices (FastAPI / gRPC / uvloop) |
| :--- | :--- | :--- |
| **Model Eksekusi** | One-Thread-per-Request. Skalabilitas dibatasi oleh footprint stack memori OS thread (default 8MB virtual memory per thread). | Asynchronous Event Loop. Single thread per core menangani puluhan ribu concurrent connection multiplexed via epoll. |
| **Protokol IPC** | JSON/HTTP 1.1 statis. High overhead parsing string, header berulang tak terkompresi, head-of-line blocking. | gRPC / HTTP/2 & Protobuf binary encoding. Header compression (HPACK), bidirectional streaming, strict typing kontrak protobuf. |
| **Observabilitas** | Raw logging stdout berbasis teks tanpa trace context correlation. Sulit diurai pada aggregate collector. | Distributed Context Propagation via W3C TraceContext standards. Injeksi `trace_id` dan `span_id` otomatis di seluruh hop service. |
| **Fault Handling** | Retry membabi buta (*blind retry*) yang memicu *Cascading Failure* dan menenggelamkan downstream dependency. | State-Aware Circuit Breaker distributed ring-buffer, Adaptive Rate Limiting, graceful degradation dengan fallback response. |

#### Komponen Kunci Arsitektur Produksi
1. **Engine Asinkron**: FastAPI (Layer ASGI) + Uvicorn Workers + UVLoop.
2. **Inter-Service Communication**: gRPC via `grpcio-tools` untuk komunikasi internal mikroservis berlatensi rendah; FastAPI/REST untuk eksternal ingress edge API.
3. **Distributed Resilience Engine**: Circuit breaker state tracking tersinkronisasi lintas node menggunakan Redis key-space expiration dan Lua atomic scripts.
4. **OpenTelemetry Telemetry Pipeline**: Tracing kontekstual terintegrasi gRPC metadata interceptor dan HTTP ASGI middlewares.

---

### 5. How (Workflow detail)

Alur eksekusi request tingkat enterprise dari edge gateway hingga layer database asinkron:

```
[Client] 
   │ (HTTP/2 or gRPC Packet)
   ▼
[Ingress / Reverse Proxy: NGINX / Envoy]
   │ (Pass-through with x-request-id & W3C TraceContext: traceparent)
   ▼
[Uvicorn / uvloop Master/Worker Socket Queue]
   │
   ├─► 1. ASGI Middleware Stack
   │      - Extract TraceContext (OpenTelemetry) -> Inisialisasi Span Root
   │      - Attach Correlation ID ke ContextVar Python
   │      - Inisialisasi Structured Logging context
   │
   ├─► 2. Circuit Breaker Interceptor
   │      - Query local in-memory L1 cache / Redis L2 state: CLOSED?
   │      - IF OPEN -> Throw Fast-Fail (HTTP 503 / gRPC UNAVAILABLE) langsung (tanpa call downsteam)
   │
   ├─► 3. Core Business Logic Execution
   │      - Resolusi Dependency Injection (Engine / Unit-of-Work)
   │      - Dispatch Async RPC calls via gRPC Stub (Multiplexed stream)
   │
   ├─► 4. Database Access via Connection Pool
   │      - Pin connection dari asyncpg / SQLAlchemy AsyncEngine
   │      - Eksekusi asynchronous query via non-blocking socket wire protocol
   │      - Release connection kembali ke pool (Zero leak guarantee via context manager)
   │
   ├─► 5. Response Pipeline & Metrics Aggregation
   │      - Rekam latensi request ke Prometheus Histogram
   │      - Tutup OpenTelemetry Span (kirim batch via OTLP gRPC exporter)
   │      - Kembalikan serialized binary/JSON response
   ▼
[Client Response Delivered]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Skala Besar
- **Synchronous Thread-per-request**: Satu loket check-in hanya melayani satu penumpang dari awal hingga bagasi dinaikkan ke pesawat. Jika koper tersangkut (I/O latency), petugas loket duduk diam memandang koper, melarang antrean bergerak. Untuk 1000 penumpang bersamaan, Anda butuh 1000 petugas loket fisik (OS Context switching overhead menghancurkan CPU).
- **Asynchronous Event Loop**: Satu petugas memproses dokumen tiket dalam 5 detik, lalu memberikan tag bagasi dan menyuruh penumpang mundur ke area tunggu (coroutine ditangguhkan via `await`). Petugas langsung memanggil penumpang berikutnya. Ketika notifikasi speaker berbunyi bahwa bagasi penumpang pertama selesai diperiksa mesin X-Ray (OS epoll event ready), petugas melambaikan tangan memanggil penumpang pertama untuk menerima boarding pass final.
- **Circuit Breaker**: Jembatan penyeberangan rel otomatis. Jika sensor mendeteksi longsor di depan (downstream fail), palang pintu segera ditutup di stasiun awal. Penumpang tidak dibiarkan naik kereta untuk celaka di tengah hutan; mereka langsung dialihkan ke bus atau diberi tiket kompensasi di tempat (*Fail Fast & Graceful Fallback*).

#### ASCII: gRPC vs REST Multiplexing
```
REST / HTTP 1.1 (Head-of-Line Blocking):
TCP Connection 1: [---Request 1---] ----> [Waiting Server Response...] ----> [Response 1]
TCP Connection 2: [---Request 2---] ----> [Waiting Server Response...] ----> [Response 2]
(Membutuhkan banyak koneksi paralel, handshake SSL berulang, memakan socket FD)

gRPC / HTTP/2 (Bidirectional Frame Multiplexing):
Single TCP Conn : [Stream 1: Req Header][Stream 2: Req Data][Stream 1: Req Data][Stream 2: Resp]
(Satu koneksi TCP tunggal menangani ratusan concurrent inter-service call tanpa blocking)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Memahami Raw Coroutine Switching & ContextVar
Contoh ini menunjukkan bagaimana context variabel terisolasi antar coroutine tanpa risiko race condition data logging.

```python
# simple_context_coroutine.py
import asyncio
from contextvars import ContextVar
import uuid

# Variabel kontekstual aman untuk concorrent execution
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="N/A")


async def downstream_service_call(payload: str) -> str:
    # Membaca request_id tanpa passing parameter secara eksplisit
    current_req_id = request_id_ctx.get()
    print(
        f"[{current_req_id}] -> Mengirim payload '{payload}' ke downstream I/O..."
    )
    # Simulasi I/O wait (GIL dilepas di native select)
    await asyncio.sleep(0.1)
    print(f"[{current_req_id}] <- Menerima respons dari downstream.")
    return f"PROCESSED: {payload}"


async def handle_request(client_data: str) -> None:
    # Menghasilkan trace UUID baru untuk setiap coroutine yang masuk
    token = request_id_ctx.set(str(uuid.uuid4())[:8])
    try:
        await downstream_service_call(client_data)
    finally:
        # Reset token untuk mencegah kebocoran konteks
        request_id_ctx.reset(token)


async def main() -> None:
    # Menjalankan 3 request secara konkuren dalam 1 thread OS
    await asyncio.gather(
        handle_request("User-Alpha"),
        handle_request("User-Bravo"),
        handle_request("User-Charlie"),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

#### 7.2. Practical Example: Production Distributed Circuit Breaker & Resilient Worker Engine
Implementasi standar produksi: FastAPI, Circuit Breaker State Machine, dan Async Engine Connection Pooling.

```python
# production_service.py
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
import logging
import sys
import time
from typing import Any, AsyncGenerator, Callable

from fastapi import FastAPI, HTTPException, status
import uvicorn

# ---------------------------------------------------------
# STRUCTURED ENTERPRISE LOGGING CONFIGURATION
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("MicroserviceEngine")


# ---------------------------------------------------------
# RESILIENCE: DISTRIBUTED CIRCUIT BREAKER STATE PATTERN
# ---------------------------------------------------------
class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_time_secs: float = 5.0
    half_open_success_threshold: int = 2


class CircuitBreakerOpenException(Exception):
    """Dilempar saat sirkuit dalam kondisi OPEN untuk memotong eksekusi (Fail Fast)."""

    pass


class DistributedCircuitBreaker:
    """Implementasi Circuit Breaker dengan state machine berbasis in-memory/atomic primitives.

    Untuk deployment multi-node enterprise, gantikan counter dengan Redis Lua
    Scripts.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            current_time = time.time()
            if self.state == CircuitState.OPEN:
                if (
                    current_time - self.last_state_change
                    > self.config.recovery_time_secs
                ):
                    logger.warning(
                        f"CircuitBreaker [{self.name}] Canary transition: OPEN -> HALF_OPEN"
                    )
                    self.state = CircuitState.HALF_OPEN
                    self.failure_count = 0
                    self.success_count = 0
                    self.last_state_change = current_time
                else:
                    raise CircuitBreakerOpenException(
                        f"CircuitBreaker [{self.name}] is OPEN. Fast-failing downstream request."
                    )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as ex:
            if not isinstance(ex, CircuitBreakerOpenException):
                await self._on_failure()
            raise ex

    async def _on_success(self) -> None:
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if (
                    self.success_count
                    >= self.config.half_open_success_threshold
                ):
                    logger.info(
                        f"CircuitBreaker [{self.name}] Canary sukses. State: HALF_OPEN -> CLOSED"
                    )
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.last_state_change = time.time()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self.failure_count += 1
            logger.error(
                f"CircuitBreaker [{self.name}] Mendeteksi error downstream. Count: {self.failure_count}"
            )
            if (
                self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
                and self.failure_count >= self.config.failure_threshold
            ):
                logger.critical(
                    f"CircuitBreaker [{self.name}] Threshold terlampaui! State: {self.state} -> OPEN"
                )
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()


# ---------------------------------------------------------
# RESILIENT DATABASE CLIENT SIMULATION WITH RETRY BACKOFF
# ---------------------------------------------------------
class PaymentGatewayClient:

    def __init__(self):
        self._execution_attempts = 0

    async def process_transaction(
        self, account_id: str, amount: float
    ) -> dict[str, Any]:
        self._execution_attempts += 1
        # Simulasi kegagalan sistem downstream: gRPC connection failure setiap siklus tertentu
        if self._execution_attempts in [1, 2, 3]:
            await asyncio.sleep(0.05)
            raise ConnectionResetError(
                "Downstream Remote Payment Gateway drop connection (RST packet)."
            )

        await asyncio.sleep(0.05)
        return {
            "status": "APPROVED",
            "account_id": account_id,
            "amount": amount,
            "tx_hash": "0x7f8a9c2b",
        }


# Inisialisasi Breaker Singleton
payment_breaker = DistributedCircuitBreaker(
    name="payment_core_rpc",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        recovery_time_secs=4.0,
        half_open_success_threshold=2,
    ),
)
payment_client = PaymentGatewayClient()


# ---------------------------------------------------------
# APPLICATION LIFECYCLE & FASTAPI ENGINE
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing Microservice Engine, warming up pools...")
    yield
    logger.info("Graceful shutdown initiated. Draining pending coroutines...")


app = FastAPI(title="Core-Banking-Orchestrator", lifespan=lifespan)


@app.post("/api/v1/payments", status_code=status.HTTP_200_OK)
async def execute_payment(account_id: str, amount: float):
    try:
        # Wrap downstream RPC call with Distributed Circuit Breaker Pattern
        result = await payment_breaker.execute(
            payment_client.process_transaction,
            account_id=account_id,
            amount=amount,
        )
        return {"code": 200, "data": result}
    except CircuitBreakerOpenException as cbe:
        logger.error(f"Degradation fallback triggered: {str(cbe)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment Core service is unavailable. Circuit breaker activated. Please retry later.",
        )
    except ConnectionResetError as cre:
        logger.error(f"Transient I/O failure: {str(cre)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream dependency failed to reply.",
        )


if __name__ == "__main__":
    # Menjalankan worker Uvicorn berbasis high performance uvloop
    uvicorn.run(
        "production_service:app",
        host="0.0.0.0",
        port=8080,
        workers=1,  # Skala horizontal via container orchestration (Kubernetes Pods)
        loop="uvloop",
        http="httptools",
        access_log=False,  # Hindari overhead synchronous log per request di throughput tinggi
    )
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Arsitektur Payment Processing Core Bank Digital
- **Skala Beban**: 45.000 Transaksi per Detik (TPS) saat peak promo gajian (*Flash Sale*).
- **Infrastruktur**: Kubernetes Cluster (EKS) dengan 80 Pods (FastAPI + gRPC + asyncpg), terhubung ke distributed PostgreSQL Aurora cluster via multi-az read-replicas dan PgBouncer tier.

#### Problem: Cascading Failure & Epoll Socket Exhaustion
Selama lonjakan trafik mendadak, cluster Payment Gateway pihak ketiga mengalami degradasi performa: latensi naik drastis dari 80ms menjadi 12.000ms per request.
- **Dampak pada Python microservice**: 
  1. Coroutine menumpuk secara masif di memory Task Queue (`asyncio._ready`), tidak dapat terselesaikan karena menunggu response I/O socket downstream.
  2. Memory footprint per pod meledak dari 250MB menjadi 4GB akibat retensi request context buffers, memicu Linux OOM Killer (`exit code 137`) secara massal di seluruh cluster Kubernetes.
  3. Saat pod mati dan me-restart, pods baru langsung diserbu sisa request TCP yang antre, mengakibatkan *thundering herd* dan pod restart-loop (CrashLoopBackOff).

#### Solusi Rekayasa Tingkat Enterprise
1. **Penerapan Dynamic Tail-Drop Bulkhead (Concurrency Limiter)**:
   Membatasi eksekusi coroutine concurrent aktif ke downstream service menggunakan `asyncio.Semaphore(1500)`. Jika slot penuh, request ditolak seketika (*fail-fast*) tanpa membuka koneksi baru.
2. **Deterministic Downstream Timeout**:
   Menerapkan deadline budget context via `asyncio.timeout(0.5)` (tersedia natively di Python 3.11+) pada level client gRPC/HTTP stub.
3. **Penyelarasan Pod Lifespan Signal Handling**:
   Menangani OS Signals (`SIGTERM`) di layer Uvicorn dengan konfigurasi `timeout-keep-alive=5` dan `graceful-timeout=30`, memberi kesempatan worker menguras (*drain*) in-flight coroutine sebelum socket ditutup paksa.
4. **Hasil**: Latensi P99 stabil di 120ms; resource pod stabil pada penggunaan memori rata-rata 380MB di beban puncak; downstream outage tidak lagi meruntuhkan cluster lokal karena pemutusan sirkuit instan (*zero-latency fast fail*).

---

### 9. Trade-offs

Setiap keputusan arsitektur mikroservis Python memiliki kompromi teknis yang harus diukur:

| Arsitektur / Pola | Keuntungan | Kerugian & Biaya Operasional |
| :--- | :--- | :--- |
| **gRPC (HTTP/2 Protobuf) vs REST JSON** | Throughput naik hingga 7x; parsing CPU footprint turun 80%; enforce strictly typed contract IDL. | Debugging sulit (payload biner, butuh tools seperti `grpcurl`); load balancing Layer 7 membutuhkan proxy khusus (Envoy) untuk memecah TCP stream multiplexing. |
| **`uvloop` vs CPython Default Event Loop** | Latensi P95/P99 terpangkas 50%; throughput mendekati performa Golang/Node.js I/O; zero-copy kernel transfer. | Kompilasi berbasis C native bindings; menyulitkan debugging stack trace Python level rendah; kompatibilitas platform non-Linux/WSL terbatas. |
| **Distributed Circuit Breaker (Redis-backed)** | State sharing akurat di seluruh pod autoscaling; mencegah *dogpiling* serentak ke downstream service. | Menambah external latency overhead (round-trip Redis call per transaksi); Redis cluster menjadi *Single Point of Failure* baru jika tidak di-cache secara berjenjang (L1 Local Memory + L2 Redis). |
| **Async (asyncpg) vs Sync ORM (SQLAlchemy ThreadPool)** | Utilisasi resource CPU & RAM sangat efisien; single worker dapat menampung 5.000 connection state. | Kerumitan kode meningkat tajam (*async/await viral propagation*); resiko blocking thread jika ada satu third-party library sinkron yang lolos (*event loop starvation*). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal 1: Menjalankan Synchronous / Blocking Code di dalam Coroutine
```python
# ANTI-PATTERN: Menghancurkan seluruh event loop!
@app.get("/data")
async def get_data():
    # requests adalah modul sinkron berbasis blocking socket OS call!
    # Event loop akan terhenti TOTAL selama 2 detik; ribuan client lain ter-freeze!
    response = requests.get("https://api.external.com/wait")
    return response.json()


# PRODUCTION-READY: Delegasikan ke ThreadPool OS via loop run_in_executor
@app.get("/data")
async def get_data():
    loop = asyncio.get_running_loop()
    # Menjalankan I/O sinkron di threadpool CPython terpisah tanpa memblokir event loop
    response = await loop.run_in_executor(
        None, requests.get, "https://api.external.com/wait"
    )
    return response.json()
```

#### 10.2. Kesalahan Fatal 2: Coroutine Task Cancellation Memory Leak
Saat client HTTP menutup koneksi browser secara tiba-tiba sebelum request selesai diproses, ASGI server menaikkan exception `asyncio.CancelledError`. Jika task tidak menangani `CancelledError` secara deterministik pada context manager:
```python
# ANTI-PATTERN: Coroutine cancellation menelan Cleanup logic
try:
    await process_transaction_statement()
except Exception:  # Peringatan: CancelledError di Python 3.8+ mewarisi BaseException!
    await rollback_db()

# PRODUCTION-READY: Tangani BaseException atau gunakan finally block
try:
    await process_transaction_statement()
except asyncio.CancelledError:
    logger.warn(
        "Request dibatalkan oleh Ingress client. Memulai kompensasi transaksi..."
    )
    await rollback_db()
    raise  # Wajib me-raise kembali CancelledError agar event loop membersihkan Task Context
finally:
    await release_db_connection()
```

#### 10.3. Panduan Troubleshooting Terstruktur
1. **Gejala: Latensi API merangkak naik bertahap, event loop lag tinggi**:
   - *Deteksi*: Jalankan loop watcher atau library `aiodebug`. Amati nilai `loop.slow_callback_duration = 0.05` (mendeteksi eksekusi blocking > 50ms).
   - *Fix*: Cari komputasi CPU intensif (misal: serialisasi JSON raksasa, kompresi zip) dan pindahkan ke `ProcessPoolExecutor`.
2. **Gejala: Koneksi PostgreSQL drop dengan error `remaining connection slots are reserved`**:
   - *Deteksi*: Cek metrik pool database. Jika `pool_size + max_overflow` dikalikan jumlah Kubernetes Worker Pods melampaui `max_connections` server PostgreSQL.
   - *Fix*: Turunkan pool size per worker container (misal: 5-10 per worker) dan letakkan connection pooler eksternal stateful seperti **PgBouncer** di depan Postgres.

---

### 11. Best Practices (Production Checklist)

- [ ] **Worker Scaling Model**: Formula alokasi worker process per container: `Workers = 1` hingga `2` per pod container. Skalakan mikroservis secara horizontal melalui Kubernetes Horizontal Pod Autoscaler (HPA) berdasarkan metrik CPU dan Latensi HTTP, bukan menumpuk puluhan worker dalam satu Pod.
- [ ] **Engine Tuning**: Inisialisasi loop `uvloop` secara eksplisit sebelum framework/server booting:
  ```python
  import asyncio
  import uvloop

  asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
  ```
- [ ] **Resource Limits (Bulkhead & Timeout)**: Setiap outbound network I/O (gRPC stub, HTTP client `httpx`, Redis, Postgres) **wajib** memiliki hard timeout yang terkonfigurasi eksplisit. Dilarang keras menggunakan client network dengan default *infinite timeout*.
- [ ] **Strict Typed Payload IDL**: Gunakan Protocol Buffers (`.proto`) untuk seluruh service-to-service internal communication guna meminimalisasi overhead serialisasi teks dan desinkronisasi skema API data payload.
- [ ] **Distributed Tracing Header Propagation**: Ekstrak dan teruskan header W3C (`traceparent`, `tracestate`) pada seluruh outgoing gRPC metadata dan HTTP client headers menggunakan OpenTelemetry API.
- [ ] **Graceful Socket Termination**: Tangkap signal `SIGTERM` di level master process. Berikan delay toleransi (5-10 detik) sebelum memutus koneksi listener agar Kubernetes endpoint routing controller selesai memperbarui routing IP tabel iptables.

---

### 12. Hands-on Practice

Implementasikan struktur microservice siap-produksi dengan melengkapi file-file berikut pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── resilience.py
│   └── tracer.py
├── tests/
│   ├── __init__.py
│   └── test_resilience.py
├── Dockerfile
└── requirements.txt
```

#### Langkah 1: Siapkan dependencies
Simpan file `hands-on/m02/requirements.txt`:
```txt
fastapi>=0.110.0
uvicorn[standard]>=0.28.0
uvloop>=0.19.0
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

#### Langkah 2: Bangun modul ketahanan (Resilience Engine)
Simpan file `hands-on/m02/app/resilience.py`:
```python
import asyncio
import time
from typing import Any, Callable


class CircuitOpenError(Exception):
    pass


class ConcurrencyBulkhead:

    def __init__(self, max_concurrent_calls: int):
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any):
        if self._semaphore.locked():
            # Opsional: langsung fail-fast jika kapasitas penuh tanpa antre
            pass
        async with self._semaphore:
            return await func(*args, **kwargs)


class SimpleCircuitBreaker:

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 5.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_state_change = 0.0

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any):
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit is OPEN. Fast fail.")

        try:
            res = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return res
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                self.last_state_change = time.time()
            raise e
```

#### Langkah 3: Bangun core entrypoint dengan uvloop dan signal handling
Simpan file `hands-on/m02/app/main.py`:
```python
import asyncio
from contextlib import asynccontextmanager
import logging
import sys

from app.resilience import CircuitOpenError, SimpleCircuitBreaker
from fastapi import FastAPI, HTTPException
import uvloop

# Terapkan engine uvloop berkecepatan tinggi
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("AppEngine")

breaker = SimpleCircuitBreaker(failure_threshold=2, reset_timeout=3.0)


# Mock I/O dependency
async def unreliable_downstream_service(should_fail: bool):
    await asyncio.sleep(0.02)
    if should_fail:
        raise IOError("Downstream network timeout simulation.")
    return {"status": "SUCCESS"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing system dependencies...")
    yield
    logger.info("Graceful shutdown executed.")


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"status": "UP"}


@app.get("/execute")
async def execute_task(fail: bool = False):
    try:
        data = await breaker.call(unreliable_downstream_service, fail)
        return data
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail="Circuit breaker OPEN: Service unavailable.",
        )
    except IOError:
        raise HTTPException(status_code=502, detail="Upstream call failed.")
```

#### Langkah 4: Tulis Automation Integration Test
Simpan file `hands-on/m02/tests/test_resilience.py`:
```python
import pytest
from app.resilience import SimpleCircuitBreaker, CircuitOpenError
import asyncio

@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = SimpleCircuitBreaker(failure_threshold=2, reset_timeout=0.2)
    
    async def failing_call():
        raise ValueError("Simulated network crash")
        
    async def healthy_call():
        return "OK"

    # Step 1: Initial failure
    with pytest.raises(ValueError):
        await cb.call(failing_call)
    assert cb.state == "CLOSED"
    
    # Step 2: Trigger threshold failure -> Circuit OPEN
    with pytest.raises(ValueError):
        await cb.call(failing_call)
    assert cb.state == "OPEN"
    
    # Step 3: Fast-fail validation (Instant rejection without executing function)
    with pytest.raises(CircuitOpenError):
        await cb.call(healthy_call)
        
    # Step 4: Wait recovery timeout -> HALF_OPEN recovery
    await asyncio.sleep(0.25)
    result = await cb.call(healthy_call)
    assert result == "OK"
    assert cb.state == "CLOSED"
```

#### Langkah 5: Eksekusi Test Suite
Jalankan pengujian dari root terminal:
```bash
cd hands-on/m02
pytest tests/ -v
```

---

### 13. Exercise

#### Level 1 - Easy
Ubah implementasi `SimpleCircuitBreaker` pada `hands-on/m02/app/resilience.py` agar mengembalikan metrik diagnostik dictionary: `{"state": self.state, "failure_count": self.failure_count, "uptime_since_trip": float}` melalui method publik `.get_diagnostics()`.

#### Level 2 - Medium
Implementasikan decorator `@with_retry_and_backoff(retries=3, base_delay=0.1, max_delay=1.0)` yang mengeksekusi exponential backoff dengan Full Jitter algorithm:
$$\text{Delay} = \text{random.uniform}(0, \min(\text{max\_delay}, \text{base\_delay} \times 2^{\text{attempt}}))$$
Decorator ini hanya boleh me-retry network-transient exceptions (misal: `ConnectionError`, `TimeoutError`) dan dilarang me-retry status client error (misal: Python `ValueError` atau HTTP 4xx).

#### Level 3 - Hard
Rancang middleware ASGI kustom terdistribusi bernama `BulkheadIsolationMiddleware` yang memanfaatkan token-bucket rate limiter non-blocking di memori. Jika concurency connection melebihi batas maksimum per tenant ID (yang diekstrak dari header HTTP `X-Tenant-ID`), middleware harus langsung memutus koneksi dan mengembalikan HTTP status code `429 Too Many Requests` dalam waktu eksekusi kurang dari 1 milidetik tanpa menyentuh routing application logic.

---

### 14. Challenge

**Skenario Kasus**: Anda memimpin tim arsitektur pada sistem settlement kliring finansial berlatensi ultra-rendah. Sistem menerima ribuan transaksi batch dari partner bank melalui streaming payload gRPC.
Tantangan rekayasa:
1. Rancang arsitektur **Adaptive Concurrency Limiter** di Python yang mengimplementasikan algoritma TCP Vegas / Little's Law ($L = \lambda W$) untuk mengukur latensi round-trip P99 secara dinamis.
2. Jika P99 response time melonjak di atas batas ambang baseline (terindikasi overload database), sistem secara otomatis mengecilkan (*choke*) ukuran semaphore pool secara real-time tanpa me-restart worker processes.
3. Arsitektur harus aman dari *Deadlock*, zero GIL lock contention, dan mampu memproses pemulihan (*recovery ramp-up*) kapasitas secara otomatis ketika P99 kembali ke parameter SLA baseline.

*Requirement*: Sediakan blueprint desain arsitektur teknis, diagram sequence interaksi state machine, kalkulasi formula kapasitas buffer, dan kode POC algoritma adaptive queue-nya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa fungsi mendasar pustaka `uvloop` ketika dipasang menggantikan default loop Python `asyncio`?
2. Mengapa multi-threading berbasis library `threading` standar Python tidak memberikan peningkatan throughput linear pada tugas-tugas intensif komputasi CPU (CPU-bound)?
3. Apa perbedaan siklus hidup mendasar antara proses master Gunicorn dan worker Uvicorn saat menerima sinyal `SIGHUP`?
4. Mengapa kita tidak boleh menggunakan method I/O bawaan standar seperti `open()` atau modul `time.sleep()` di dalam fungsi yang dideklarasikan dengan kata kunci `async def`?
5. Protokol transport Layer 4 apa yang digunakan oleh HTTP/2 dan gRPC secara default, dan bagaimana cara kerjanya meminimalisasi overhead jabat tangan koneksi (connection handshake)?

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Jelaskan bagaimana `contextvars.ContextVar` mengisolasi context data antar coroutine yang dieksekusi secara asinkron dalam satu OS thread yang sama, dan mengapa `threading.local()` gagal melakukan hal ini!
2. Bagaimana mekanisme Linux Kernel `SO_REUSEPORT` bekerja memecahkan masalah *Thundering Herd* pada multi-process worker architecture?
3. Pada kondisi apa sebuah `asyncio.CancelledError` dinaikkan ke dalam frame eksekusi coroutine, dan apa bahaya arsitekturalnya jika exception ini ditangkap menggunakan blok sintaksis `except Exception:`?
4. Mengapa pendekatan Connection Pooling database di lingkungan asynchronous microservice (seperti `asyncpg`) membutuhkan alokasi pool size per-worker yang lebih kecil secara drastis dibanding pooling pada model thread-per-request konvensional?
5. Jelaskan fase transisi state dari `HALF_OPEN` ke `OPEN` atau ke `CLOSED` pada Circuit Breaker Pattern, serta tentukan metrik apa yang dijadikan acuan determinasi transisi tersebut!

#### Bagian 3: Skenario Kasus Produksi (3 Skenario)
1. **Skenario Kasus Memory Leak**: 
   Sebuah microservice FastAPI di produksi mengalami peningkatan konsumsi RAM sebesar 15 MB/jam secara konstan hingga terkena Linux OOM killer setiap 48 jam. Hasil profiler memori menunjukkan puluhan ribu instance task `asyncio.Task` berada pada status pending tak terhapus. Analisis kemungkinan akar masalah arsitektur kode dan bagaimana metodologi debugging yang tepat untuk mengisolasinya!
2. **Skenario Deadlock Event Loop**:
   Developer mengintegrasikan client SDK distributed lock berbasis Redis ke dalam service Python. Namun, saat trafik tinggi, seluruh endpoint API service membeku total (*freeze/hang*) dengan P100 latency tanpa melempar exception apapun, sementara utilisasi CPU pod berada di angka 0%. Diagnosis apa yang terjadi pada antrean event loop dan buktikan mekanisme penyebab kebuntuan tersebut!
3. **Skenario Cascading gRPC Failure**:
   Service A memanggil Service B via synchronous streaming gRPC stub. Service C (dependensi hilir dari Service B) mengalami mati total (*hard-down*). Jelaskan skenario domino failure yang akan merambat kembali hingga ke Service A jika tidak ada implementasi timeout budget kontekstual, dan jelaskan langkah mitigasinya dengan pola OpenTelemetry propagation combined with Bulkhead!

---

### 16. Summary

1. **CPython Concurrency Realities**: Skalabilitas microservice Python tingkat tinggi dicapai bukan dengan melawan batasan GIL, melainkan dengan memisahkan concern: I/O Multiplexing non-blocking ditangani oleh cooperative multitasking (`uvloop`/libuv event loop), sedangkan horizontal CPU scaling ditangani oleh multi-worker process master-prefork model.
2. **Inter-Service Superiority**: Transisi dari REST/JSON ke gRPC/Protobuf memotong latensi tail P99 dan pemakaian CPU secara drastis melalui binary serialization, HTTP/2 connection multiplexing, dan typing kontrak interface yang ketat.
3. **Enterprise Resilience is Non-Negotiable**: Microservice produksi tidak boleh mengasumsikan dependensi jaringan selalu sehat. Penggunaan timeout deterministik, bounded queue, concurrency bulkhead, dan distributed circuit breaker adalah fondasi utama guna menghentikan cascading failure di sistem terdistribusi.
4. **Context Safety**: Isolasi observabilitas end-to-end wajib dikawal dengan struktur instrumen modern (`ContextVar`, OpenTelemetry tracing contexts, non-blocking zero-allocation logging) agar metrik transaksi finansial dan trace per-request dapat dilacak dengan presisi tanpa mengorbankan performa latency kritis sistem.