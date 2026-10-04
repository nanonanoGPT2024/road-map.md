# SEKSI 01 — IDENTITAS MODUL

* **Mata Kuliah / Kurikulum:** Advanced Python Engineering Core
* **Kategori:** 02-Programming-Languages
* **Kode Modul:** PY-0701
* **Bab:** 07 — Asynchronous & Concurrent Systems
* **Judul Modul:** Asynchronous Programming Lanjutan dengan Asyncio
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang Python Object Model, Generators (`yield`, `yield from`), dan Decorators.
  * Pengetahuan dasar concurrency: Threads vs Processes, Race Conditions, dan Deadlocks.
  * Pengalaman dasar sintaks asynchronous Python (`async`/`await`).
* **Platform & Runtime:** Python 3.11+ (mengadopsi fitur *Structured Concurrency* modern seperti `asyncio.TaskGroup` dan `asyncio.timeout`).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Mekanisme Internal Event Loop CPython:** Menguraikan lifecycle pemanggilan coroutine, registrasi File Descriptor pada sistem I/O Multiplexer (`epoll`, `kqueue`), dan eksekusi callback pada queue internal asyncio.
2. **Menerapkan Paradigma Structured Concurrency:** Mengimplementasikan pola konkurensi modern menggunakan `asyncio.TaskGroup` dan manajemen penanganan error hierarkis via `ExceptionGroup`.
3. **Menguasai Protokol Pembatalan (*Cancellation Protocol*):** Mengontrol propagasi `asyncio.CancelledError`, perancangan *cleanup routine* yang deterministik, dan teknik proteksi alur kritis dengan `asyncio.shield`.
4. **Membangun Primitif Sinkronisasi Asinkron Tingkat Lanjut:** Menggunakan `asyncio.Semaphore`, `asyncio.Event`, `asyncio.Condition`, dan `asyncio.Queue` untuk membatasi *throughput*, *backpressure*, dan mengamankan *shared mutable state*.
5. **Mengintegrasikan Kode Blocking & Profiling Sistem:** Mengisolasi tugas I/O blocking atau CPU-bound ke thread/process pool terpisah tanpa memblokir event loop menggunakan `asyncio.to_thread` dan custom `ThreadPoolExecutor`.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Konduktor Orkestra vs. Dapur Restoran Preemptive

Pada *Preemptive Multitasking* (seperti OS Threads), sistem operasi bertindak seperti manajer dapur agresif yang dapat menghentikan koki di tengah-tengah pemotongan bawang untuk membalik daging panggang. Konteks berpindah secara arbitrer (*preemptive context switch*), memaksa pengembang memasang gembok (*lock*) pada setiap meja dan pisau untuk mencegah bencana *data corruption*.

```
Preemptive Threading:
[Thread 1: Potong Bawang] --DIPAKSA BERHENTI OLEH OS--> [Thread 2: Balik Daging]
                     (Perlu Lock pada Talenan & Pisau)

Cooperative Multitasking (Asyncio):
[Coroutine 1: Panggang Daging] --"Saya sedang tunggu oven matang (await)"--> 
                                     [Coroutine 2: Potong Sayur]
```

Sebaliknya, *Cooperative Multitasking* dengan `asyncio` adalah sebuah orkestra dengan seorang Konduktor tunggal (*Event Loop*) dan musisi yang sangat disiplin (*Coroutines*).
* Setiap instrumen memainkan bagian mereka sampai titik istirahat yang telah ditentukan secara eksplisit (`await`).
* Tidak ada interupsi paksa di tengah baris notasi. Titik penyerahan kontrol sepenuhnya berada di tangan *programmer*.
* Jika seorang musisi memainkan solo piano tanpa henti tanpa melihat konduktor (misalnya menjalankan komputasi CPU intensif atau I/O blocking murni seperti `time.sleep()`), seluruh orkestra berhenti berbunyi.

Prinsip fundamental: **"Yield control early, yield control often, and never block the conductor."**

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur runtime `asyncio` berpusat pada abstraksi non-blocking I/O tingkat OS yang dipadukan dengan scheduler berbasis queue di user space.

```
+---------------------------------------------------------------------------------+
|                                USER APPLICATION SPACE                           |
|                                                                                 |
|  +--------------------+    +--------------------+    +-----------------------+  |
|  | Coroutine Alpha    |    | Coroutine Beta     |    | Coroutine Gamma       |  |
|  | (await read_db())  |    | (await send_msg()) |    | (await worker_job())  |  |
|  +---------+----------+    +---------+----------+    +-----------+-----------+  |
|            |                         |                           |              |
|            +-------------------------+---------------------------+              |
|                                      | yield / await                            |
|                                      v                                          |
|  +---------------------------------------------------------------------------+  |
|  |                            ASYNCIO EVENT LOOP                             |  |
|  |                                                                           |  |
|  |   +-----------------------+         +---------------------------------+   |  |
|  |   |     Ready Queue       |         |        Scheduled / Timers       |   |  |
|  |   | [Task-1] -> [Task-3]  |         | (call_later, call_at, timeouts) |   |  |
|  |   +-----------+-----------+         +----------------+----------------+   |  |
|  |               ^                                      |                    |  |
|  |               |          Loop Iteration              |                    |  |
|  |               +======================================+                    |  |
|  |                                   |                                       |  |
|  |                                   v                                       |  |
|  |                      +------------------------+                           |  |
|  |                      | I/O Multiplexer Engine |                           |  |
|  |                      |  (selectors.Default)   |                           |  |
|  +-----------------------------------+---------------------------------------+  |
+--------------------------------------|------------------------------------------+
                                       |
                                       v OS System Calls
+---------------------------------------------------------------------------------+
|                                OPERATING SYSTEM KERNEL                          |
|                                                                                 |
|           +------------------------------------------------------+              |
|           |    I/O Event Demultiplexer Interface                 |              |
|           |    - Linux: epoll()                                  |              |
|           |    - macOS / BSD: kqueue()                           |              |
|           |    - Windows: I/O Completion Ports (IOCP)            |              |
|           +--------------------------+---------------------------+              |
|                                      |                                          |
|          +---------------------------+---------------------------+              |
|          |                           |                           |              |
|          v                           v                           v              |
|   [Socket: DB Conn]          [Socket: Web Client]         [File/Pipe Descriptors]
+---------------------------------------------------------------------------------+
```

### Siklus Siklus Hidup Eksekusi Task:

```
[Coroutine Created] 
        |
        v asyncio.create_task()
[Task Initialized (Pushed to Ready Queue)]
        |
        v Event Loop Pops Task
[Task Executing via Task.__step()]
        |
   +----+--------------------------------+
   |                                     |
[Awaits on I/O / Sleep]         [Execution Completed]
   |                                     |
   v Register Selector & FD              v
[Task Suspended (Idle)]         [Set Task Result / Exception]
   |                                     |
   v Kernel Notifies Selector Event      v
[Re-enqueued to Ready Queue]    [Execute Done Callbacks]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Evolusi Generator Menuju Native Coroutines
Sebelum Python 3.5, asinkron dibangun di atas generator menggunakan decorator `@asyncio.coroutine` dan `yield from`. Python 3.5 memperkenalkan `async def` dan `await`, menetapkan coroutine sebagai tipe data kelas satu (`coroutine object`) yang divalidasi pada level CPython bytecode:
* Sebuah fungsi `async def` tidak langsung mengeksekusi instruksi ketika dipanggil; ia mengembalikan sebuah *coroutine object*.
* Bytecode `GET_AWAITABLE` dieksekusi ketika menemui ekspresi `await`. Objek yang di-*await* wajib mengimplementasikan protokol magic method `__await__()` yang mengembalikan iterator.

### 2. Anatomi Objek: Future vs Task
* **`asyncio.Future`**: Merepresentasikan hasil akhir dari sebuah operasi asinkron yang belum selesai. Memiliki status internal: `PENDING`, `CANCELLED`, atau `FINISHED`. Objek ini memiliki callback queue (`_callbacks`) yang dieksekusi saat hasilnya disetel melalui `.set_result()` atau `.set_exception()`.
* **`asyncio.Task`**: Merupakan subkelas konkret dari `Future`. `Task` bertugas membungkus coroutine object dan mengoordinasikan eksekusinya dengan event loop. 
  * Metode privat internal `Task.__step()` memanggil coroutine dengan mengirimkan `coro.send(None)` untuk melanjutkan eksekusi.
  * Ketika coroutine menyerahkan kontrol via `await future`, Task menambahkan `Task.__wakeup()` ke callback internal future tersebut. Saat future selesai, `__wakeup()` mendorong kembali Task ke dalam Ready Queue event loop.

### 3. I/O Multiplexing Loop
Event loop CPython menggunakan modul standar `selectors`. Secara internal, implementasi default untuk Linux adalah `EpollSelector`, dan untuk macOS adalah `KqueueSelector`.
Struktur algoritma inti loop (`_run_once`):
1. Menguji scheduled timer events (`_scheduled`). Objek yang sudah jatuh tempo dipindahkan ke ready queue (`_ready`).
2. Menghitung durasi timeout untuk syscall multiplexer: jika ada task di `_ready`, timeout bernilai `0` (non-blocking poll); jika tidak, timeout diambil dari jarak waktu timer terdekat.
3. Memanggil selector: `event_list = selector.select(timeout)`.
4. Memproses semua event I/O yang aktif dari kernel, mendaftarkan callback terkait ke `_ready`.
5. Mengambil dan mengeksekusi semua callback pada antrean `_ready` secara berurutan (*FIFO order*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Structured Concurrency vs `asyncio.gather`
Pada era Python lama, `asyncio.gather(*tasks)` atau `asyncio.ensure_future()` digunakan secara masif. Pola ini memicu masalah besar: **Fire-and-Forget / Unbounded Concurrency / Dangling Tasks**. Jika salah satu task mengalami kegagalan fatal (*crash*), task lainnya tetap berjalan tanpa induk, menyebabkan *resource leak* dan status sistem yang tidak menentu (*state corruption*).

Python 3.11 memperkenalkan paradigma **Structured Concurrency** melalui `asyncio.TaskGroup`.
* **Prinsip Kontensi Leksikal:** Task dibatasi oleh blok konteks `async with asyncio.TaskGroup() as tg:`.
* **Fail-Fast Error Handling:** Jika sebuah child task melempar exception, `TaskGroup` secara otomatis membatalkan (*cancel*) seluruh task lain yang berada dalam grup yang sama.
* Konteks tidak akan pernah keluar sampai semua child task selesai, gagal, atau berhasil dibatalkan.
* Semua exception yang terjadi tidak ditelan, melainkan diagregasi ke dalam struktur pohon `ExceptionGroup` (atau `BaseExceptionGroup`).

```
                    +--------------------------------+
                    |  async with TaskGroup() as tg  |
                    +---------------+----------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
      tg.create_task(A)       tg.create_task(B)       tg.create_task(C)
            |                       |                       |
            | (Runs OK)             | (Throws ValueError!)  | (Running...)
            |                       |                       |
            |                       +-----> [CANCELS] ----->+ (Task C receives
            |                                                  CancelledError)
            v                                               v
    [Exits cleanly]                                  [Exits Cleanly]
            \                       |                      /
             +----------------------+---------------------+
                                    |
                                    v
                     Raises ExceptionGroup to Caller
```

### 2. Protokol Pembatalan (*Cancellation Protocol*)
Membatalkan sebuah task (`task.cancel()`) bukanlah operasi terminasi paksa berbasis thread signaling (`SIGKILL`). Pembatalan adalah mekanisme injeksi exception kooperatif:
1. Pemanggilan `task.cancel()` menjadwalkan injeksi `asyncio.CancelledError` ke dalam coroutine yang sedang di-suspend saat ia menerima giliran eksekusi di `__step()`.
2. Exception ini muncul di baris tempat `await` sedang berhenti.
3. Coroutine **dapat** menangkap `CancelledError` menggunakan blok `try...finally` atau `except asyncio.CancelledError:` untuk melakukan pembersihan sumber daya (menutup koneksi DB, flush buffer file).
4. Coroutine **harus** melempar kembali (`re-raise`) `CancelledError` jika penanganannya tidak dimaksudkan untuk menghentikan pembatalan secara eksplisit. Menelan exception ini tanpa izin akan merusak siklus penutupan TaskGroup.

### 3. Context Variables (`contextvars`)
Dalam pemrograman multithread, Thread-Local Storage (`threading.local`) digunakan untuk menyimpan state spesifik per alur eksekusi (seperti ID request, tenant ID, database transaction handle). Pada asyncio, beberapa task berjalan pada thread yang sama, sehingga `threading.local` tidak berguna.
Solusinya adalah modul `contextvars`. Task yang dibuat via `create_task()` menduplikasi konteks variabel task induk secara otomatis (Copy-on-Write semantics), memastikan isolasi penuh antar alur tanpa tabrakan state.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh berikut mendemonstrasikan paradigma *Structured Concurrency* modern, penanganan timeout dengan batas deterministik menggunakan `asyncio.timeout`, sinkronisasi via `asyncio.Queue`, dan penanganan `CancelledError`.

```python
import asyncio
from typing import NoReturn


async def producer(queue: asyncio.Queue[int], count: int) -> None:
    """Memproduksi item numerik ke dalam bounded queue."""
    for item in range(1, count + 1):
        await asyncio.sleep(0.05)  # Simulasi I/O non-blocking (e.g., fetch event)
        await queue.put(item)
        print(f"[Producer] Produced item: {item}")
    print("[Producer] Selesai memproduksi data.")


async def consumer(queue: asyncio.Queue[int], consumer_id: int) -> NoReturn:
    """Mengkonsumsi item dari queue tanpa henti sampai dibatalkan."""
    try:
        while True:
            item = await queue.get()
            try:
                print(f"[Consumer-{consumer_id}] Memproses item: {item}")
                await asyncio.sleep(0.1)  # Simulasi latensi pemrosesan
            finally:
                # Menandai pemrosesan task selesai terlepas dari exception
                queue.task_done()
    except asyncio.CancelledError:
        print(f"[Consumer-{consumer_id}] Menerima sinyal pembatalan, membersihkan state...")
        raise  # Re-raise agar task lifecycle selesai secara semantik


async def run_pipeline() -> None:
    """Mengorkestrasi producer-consumer pipeline via TaskGroup."""
    # Bounded queue untuk mencegah unbounded memory explosion (backpressure)
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=5)
    
    try:
        # Menetapkan batas total operasi keseluruhan pipa via timeout context manager
        async with asyncio.timeout(2.0):
            async with asyncio.TaskGroup() as tg:
                # Spawn workers
                c1 = tg.create_task(consumer(queue, consumer_id=1))
                c2 = tg.create_task(consumer(queue, consumer_id=2))
                
                # Spawn producer
                p = tg.create_task(producer(queue, count=10))
                
                # Tunggu producer selesai mengirim semua data
                await p
                
                # Tunggu queue dikosongkan sepenuhnya oleh consumer
                await queue.join()
                
                # Batalkan consumer yang berjalan secara infinite loop
                c1.cancel()
                c2.cancel()
                
    except TimeoutError:
        print("[Pipeline] ERROR: Eksekusi pipeline melampaui batas hard timeout!")
    except* Exception as eg:
        # Penanganan ExceptionGroup secara terstruktur (Python 3.11+)
        print(f"[Pipeline] Terjadi kesalahan fatal: {eg.exceptions}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis alur kode Seksi 07:

1. **`async def producer(queue: asyncio.Queue[int], count: int)`**: Mendefinisikan coroutine produsen data dengan static type hinting.
2. **`await queue.put(item)`**: Jika queue telah mencapai kapasitas maksimum (`maxsize=5`), coroutine ini akan di-*suspend* oleh event loop. Inilah mekanisme dasar **backpressure**; produsen dicegah mengisi memori jika konsumen lambat.
3. **`async def consumer(...) -> NoReturn`**: Menandakan fungsi ini dirancang berjalan terus-menerus (*daemon worker loop*) hingga interupsi pembatalan terjadi.
4. **`item = await queue.get()`**: Konsumen menangguhkan eksekusi jika queue kosong. Event loop melepaskan kontrol CPU untuk task produsen.
5. **`finally: queue.task_done()`**: Menjamin status task counter dalam `queue` selalu didekremen, mencegah `queue.join()` menggantung selamanya (*deadlock*) jika eksekusi pemrosesan data melempar exception tak terduga.
6. **`except asyncio.CancelledError: ... raise`**: Mengimplementasikan cancellation protocol standar. Jika blok ini menangkap exception tanpa melakukan `raise`, TaskGroup akan hang atau melaporkan error pembatalan abnormal.
7. **`queue = asyncio.Queue(maxsize=5)`**: Membatasi antrean hingga maksimal 5 item di memori Heap.
8. **`async with asyncio.timeout(2.0):`**: Context manager Python 3.11 yang mengonfigurasi scheduled timer callback. Jika eksekusi blok melebihi 2.0 detik, interrupt `TimeoutError` diinjeksikan ke task aktif saat ini.
9. **`async with asyncio.TaskGroup() as tg:`**: Membuka batas konkurensi terstruktur. Seluruh task yang diinstansiasi via `tg.create_task()` diawasi secara hierarkis.
10. **`await queue.join()`**: Memblokir coroutine `run_pipeline` (bukan thread OS) hingga counter internal antrean bernilai nol (seluruh item yang di-`put` telah diimbangi oleh `task_done`).
11. **`c1.cancel(); c2.cancel()`**: Membatalkan infinite loop workers secara deterministik setelah tugas pemrosesan selesai.
12. **`except* Exception as eg:`**: Sintaks exception handler modern untuk menangkap *pattern matching* subset exception di dalam instance `ExceptionGroup`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Resilient High-Throughput Webhook Ingestion Engine
Sebuah sistem agregator pembayaran memproses puluhan ribu notifikasi webhook per menit dari berbagai payment gateway (Stripe, Midtrans, Xendit). 

**Masalah Arsitektural:**
1. **Third-party Flakiness:** Pihak downstream sering kali mengalami lonjakan latensi, respons timeout, atau rate-limit (HTTP 429).
2. **Thread Starvation:** Pendekatan arsitektur berbasis multithread konvensional mengonsumsi memory heap masif (~8MB per thread stack) dan menghabiskan resource OS context switching saat mencapai 5.000 konkurensi koneksi.
3. **Cascading Failure:** Satu downstream partner yang *down* tidak boleh menyebabkan seluruh task webhook queue menumpuk dan menenggelamkan server internal.

**Kebutuhan Solusi:**
Membangun *Dispatcher Core* berbasis `asyncio` yang memiliki:
* **Concurrency Limiting:** Membatasi koneksi outgoing simultan menggunakan `asyncio.Semaphore`.
* **Circuit Breaker & Backpressure:** Mencegah pemanggilan layanan yang sedang *degraded*.
* **Fault-Tolerant Retry Loop:** Menggunakan *exponential backoff* dengan jitter tanpa memblokir thread.
* **Graceful OS Signal Handling:** Menangani sinyal `SIGINT`/`SIGTERM` untuk mengosongkan *flight-data* secara bersih sebelum server mati.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi lengkap *Resilient Webhook Dispatcher Engine* tingkat produksi:

```python
import asyncio
import logging
import random
import signal
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(task_name)s) %(message)s",
)


class TaskNameFilter(logging.Filter):
    """Menyuntikkan ID/Nama Task asyncio ke dalam record log."""
    def filter(self, record: logging.LogRecord) -> bool:
        task = asyncio.current_task()
        record.task_name = task.get_name() if task else "MainEngine"
        return True


# Pasang filter logging
for handler in logging.root.handlers:
    handler.addFilter(TaskNameFilter())

logger = logging.getLogger("WebhookDispatcher")


@dataclass(frozen=True)
class WebhookPayload:
    event_id: str
    target_url: str
    payload_data: dict
    retries_left: int = 3
    base_delay_seconds: float = 0.5


class CircuitBreakerOpenException(Exception):
    """Dilempar ketika circuit breaker mendeteksi downstream offline."""
    pass


class AsyncCircuitBreaker:
    """Circuit Breaker untuk memproteksi downstream system yang tidak sehat."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 5.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            if self.state == "OPEN":
                if now - self.last_state_change > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                    logger.warning("Circuit beralih ke HALF-OPEN. Menguji koneksi downstream.")
                    return True
                return False
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    async def record_failure(self) -> None:
        async with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                self.last_state_change = asyncio.get_event_loop().time()
                logger.error(f"Circuit tripped ke status OPEN! downstream failure >= {self.failure_threshold}")


class ResilientDispatcher:
    def __init__(self, concurrency_limit: int, max_queue_size: int) -> None:
        self.queue: asyncio.Queue[WebhookPayload] = asyncio.Queue(maxsize=max_queue_size)
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.circuit_breaker = AsyncCircuitBreaker()
        self._shutdown_event = asyncio.Event()

    async def mock_http_post(self, target_url: str, data: dict) -> int:
        """Simulasi HTTP I/O non-blocking dengan potensi kegagalan jaringan."""
        await asyncio.sleep(random.uniform(0.05, 0.2))  # Latensi jaringan
        # Simulasi 15% downstream outage
        if random.random() < 0.15:
            raise ConnectionError("503 Service Unavailable: Remote Host Down")
        return 200

    async def _send_with_retry(self, item: WebhookPayload) -> None:
        """Worker execution unit dengan Exponential Backoff + Jitter."""
        async with self.semaphore:
            if not await self.circuit_breaker.can_execute():
                logger.warning(f"Dropping event {item.event_id}: Circuit breaker OPEN")
                return

            current_retry = 0
            while current_retry <= item.retries_left:
                try:
                    # Terapkan timeout per request individu secara eksplisit
                    async with asyncio.timeout(0.5):
                        status = await self.mock_http_post(item.target_url, item.payload_data)
                        if status == 200:
                            await self.circuit_breaker.record_success()
                            logger.info(f"Delivered event {item.event_id} successfully.")
                            return

                except (ConnectionError, TimeoutError) as exc:
                    current_retry += 1
                    await self.circuit_breaker.record_failure()
                    if current_retry > item.retries_left:
                        logger.error(f"Failed to deliver event {item.event_id} after {item.retries_left} retries: {exc}")
                        return
                    
                    # Full Jitter Exponential Backoff Calculation
                    backoff = item.base_delay_seconds * (2 ** (current_retry - 1))
                    jittered_delay = random.uniform(0, backoff)
                    logger.warning(f"Retry {current_retry} for event {item.event_id} sleeping for {jittered_delay:.2f}s")
                    await asyncio.sleep(jittered_delay)

    async def worker(self, worker_id: int) -> None:
        """Loop internal worker task."""
        while not self._shutdown_event.is_set() or not self.queue.empty():
            try:
                # Menggunakan timeout pendek agar worker secara berkala mengecek shutdown flag
                async with asyncio.timeout(0.2):
                    item = await self.queue.get()
            except TimeoutError:
                continue

            try:
                await self._send_with_retry(item)
            finally:
                self.queue.task_done()
        
        logger.info(f"Worker-{worker_id} safely exited.")

    async def enqueue_webhook(self, payload: WebhookPayload) -> bool:
        """Pintu masuk pengiriman payload dengan mekanisme non-blocking backpressure."""
        try:
            self.queue.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            logger.error(f"Backpressure triggered! Queue overflow, rejecting event: {payload.event_id}")
            return False

    async def shutdown(self) -> None:
        """Graceful shutdown protocol."""
        logger.warning("Shutdown sequence diinisiasi...")
        self._shutdown_event.set()
        await self.queue.join()
        logger.info("Seluruh sisa antrean antrean berhasil diproses.")


async def main() -> None:
    dispatcher = ResilientDispatcher(concurrency_limit=10, max_queue_size=100)
    loop = asyncio.get_running_loop()

    # Setup penanganan sinyal shutdown POSIX secara asinkron
    def handle_signal():
        asyncio.create_task(dispatcher.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Fallback untuk platform tanpa dukungan sinyal penuh (seperti standard Windows IOCP loop)
            pass

    async with asyncio.TaskGroup() as tg:
        # Spawn Consumer Worker Pool
        workers = [
            tg.create_task(dispatcher.worker(i), name=f"Worker-{i}")
            for i in range(5)
        ]

        # Enqueue sample webhooks
        for i in range(25):
            payload = WebhookPayload(
                event_id=f"evt_{i:04d}",
                target_url="https://api.partner.com/webhook",
                payload_data={"transaction_id": 1000 + i, "amount": random.randint(10, 500)},
            )
            enqueued = await dispatcher.enqueue_webhook(payload)
            if not enqueued:
                break
            await asyncio.sleep(0.01)

        # Memicu shutdown otomatis untuk keperluan demonstrasi
        await dispatcher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih model konkurensi menuntut evaluasi trade-off arsitektural yang ketat.

### Tabel Komparasi Karakteristik Runtime

| Dimensi Parameter | Asyncio (Cooperative) | Multi-Threading (Preemptive) | Multi-Processing (Process Isolated) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Single-thread, single-process, 1 CPU core | OS threads, preempted by OS kernel | Multiple isolated OS processes |
| **Batas GIL (Global Interpreter Lock)**| Terikat ketat pada 1 Core GIL | Terikat GIL untuk instruksi murni Python | Memotong batasan GIL (1 Core per Process) |
| **Konsumsi Memori** | **Ultra Rendah** (~2-4 KB per coroutine task) | **Sedang** (~8 MB per thread OS default stack) | **Tinggi** (Duplikasi memory address space) |
| **Biaya Context Switch**| **Sangat Rendah** (Hanya pointer switch di heap user space) | **Tinggi** (CPU Ring-3 ke Ring-0 transition cache invalidation)| **Tertinggi** (TLB flushing & memory pages swap) |
| **Kesesuaian Beban Kerja**| High Concurrency Network I/O, WebSockets, Scraping | Moderate I/O, C-extensions yang melepaskan GIL | CPU-Bound Heavy Computation (ML/Math/Encoding) |
| **Kompleksitas Debugging**| Memerlukan pemahaman alur async/cancellation yang disiplin | Rawan Race Conditions, Deadlocks, Heisenbugs | Kompleksitas IPC (Inter-Process Communication) & Serialization |

### Kapan Menggunakan Asyncio?
* Sistem Anda menangani lebih dari 5.000 koneksi I/O simultan yang sebagian besar waktunya dihabiskan untuk menunggu (Network idle, Database read/write).
* Microservices yang membutuhkan latensi footprint memory minimal untuk efisiensi container pod Kubernetes.

### Kapan Menghindari Asyncio?
* Pemrosesan data komputasi intensif numerik murni tanpa I/O (gunakan `multiprocessing` atau tools berbasis Rust/C extensions).
* Basis kode legacy yang dipenuhi library synchronous terikat blocking socket murni tanpa alternatif async (e.g., driver DB kuno).

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Masked `CancelledError`
Jika sebuah library atau blok kode Anda menangkap exception tingkat tinggi secara serampangan:
```python
# SANGAT BERBAHAYA:
try:
    await asyncio.sleep(10)
except Exception:
    # Ini menangkap CancelledError di Python < 3.8, namun di Python 3.8+ 
    # CancelledError mewarisi BaseException. Namun pola di bawah tetap mematikan:
    pass

try:
    await do_io()
except BaseException:  # Menelan CancelledError!
    pass
```
*Dampak:* Event loop kehilangan kemampuan untuk membatalkan Task tersebut. `TaskGroup` akan menggantung (*hang*) selamanya saat mencoba shutdown.

### 2. Phantom Blocking (CPU starvation)
Menjalankan komputasi CPU intensif di dalam event loop utama:
```python
async def compute_heavy_hash(data: bytes):
    # MEMATIKAN SISTEM: Mengunci loop selama 3 detik.
    # Seluruh socket lain tidak akan diproses (Dropping health checks, timeout client)!
    result = hashlib.pbkdf2_hmac('sha256', data, b'salt', 10_000_000)
    return result
```
*Solusi:* Pindahkan komputasi CPU keluar dari loop menggunakan executor pool:
```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, sync_heavy_cpu_func, data)
```

### 3. Task Garbaged Collected Prematurely
CPython menghapus objek yang ref-count-nya mencapai nol.
```python
# KESALAHAN UMUM:
async def start_background():
    # Referensi ke task ini tidak disimpan dalam variabel/set
    asyncio.create_task(some_long_running_job()) 
```
*Dampak:* Garbage Collector (GC) dapat mendeteksi task yang sedang berjalan sebagai *unreferenced object* dan memusnahkannya di tengah eksekusi, melempar pesan peringatan misterius: `Task was destroyed but it is pending!`.
*Solusi:* Selalu simpan referensi task ke dalam `set` global atau gunakan `TaskGroup`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Memanggil Fungsi Asinkron Tanpa `await`
```python
# SALAH
async def log_event(msg: str):
    await db.save(msg)

async def handle_request():
    log_event("User logged in")  # Mengembalikan coroutine object, BUKAN mengeksekusinya!
    return {"status": "ok"}
```
*Cara Menghindari:* Aktifkan environment variable `PYTHONASYNCIODEBUG=1`. Python akan mengeluarkan runtime warning: `RuntimeWarning: coroutine 'log_event' was never awaited`.

### Kesalahan 2: Menggunakan Library Synchronous di Lingkungan Asinkron
```python
import requests # LIBRARY BLOCKING!
import time

# SALAH
async def fetch_data():
    time.sleep(1) # Memblokir thread event loop
    return requests.get("https://api.example.com") # Memblokir socket loop
```
*Solusi:* Gunakan modul non-blocking murni yang dibangun dengan async sockets.
```python
import asyncio
import httpx # LIBRARY NON-BLOCKING

# BENAR
async def fetch_data():
    await asyncio.sleep(1)
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com")
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Python 3.11+ Structured Concurrency:** Hindari pemanggilan manual `asyncio.gather()` untuk dispatch task dinamis; gunakan `asyncio.TaskGroup()`.
2. **Gunakan Timeouts Deklaratif:** Gantikan penggunaan legacy `asyncio.wait_for(coro, timeout)` dengan `async with asyncio.timeout(seconds):` untuk isolasi cancellation boundary yang bersih.
3. **Injeksi File Descriptors Bersih:** Pastikan database pool, HTTP sessions, dan file handles ditutup melalui async context managers (`async with`).
4. **Isolasi Boundary Sinkron:** Ketika terpaksa memanggil fungsi SDK synchronous lawas, bungkus secara eksplisit menggunakan `asyncio.to_thread()` (Python 3.9+).
5. **Jangan Pernah Menggunakan `asyncio.get_event_loop()`:** Di Python modern, pemanggilan ini dapat memicu *undefined behavior* jika tidak ada loop yang aktif. Gunakan **`asyncio.get_running_loop()`** untuk mendapatkan loop saat ini, atau **`asyncio.run()`** sebagai *entry point*.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Substitusi Event Loop Engine dengan `uvloop`
`uvloop` adalah drop-in replacement untuk core event loop Python bawaan. Dibuat di atas pustaka C `libuv` (pustaka yang sama yang mentenagai Node.js). `uvloop` memotong overhead abstraksi Python runtime dan melipatgandakan throughput I/O hingga 2-4x lipat.

```python
import asyncio
import sys

# Inisialisasi engine tercepat
if sys.platform != "win32":
    import uvloop
    uvloop.install()

asyncio.run(main())
```

### 2. Mengurangi Alokasi Overhead dengan Zero-Copy Memoryview
Saat membaca payload jaringan besar dari socket atau stream (`asyncio.StreamReader`), alokasi string/bytes baru dapat membebani memori. Gunakan antarmuka buffer mutable:
```python
async def read_into_buffer(reader: asyncio.StreamReader, n_bytes: int):
    buf = bytearray(n_bytes)
    view = memoryview(buf)
    # Membaca data langsung ke memoryview tanpa alokasi object intermediate
    bytes_read = await reader.readinto(view)
    return view[:bytes_read]
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Slowloris & Connection Exhaustion Attack:**
   *Penyerang membuka ribuan koneksi TCP dan mengirimkan data secara lambat (1 byte tiap beberapa detik), menghabiskan file descriptor event loop.*
   *Hardening:* Terapkan batas waktu pembacaan soket secara mutlak:
   ```python
   async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
       try:
           async with asyncio.timeout(5.0): # Maksimal 5 detik untuk menerima complete request
               header = await reader.readline()
       except TimeoutError:
           writer.close()
           await writer.wait_closed()
   ```

2. **DoS via Unbounded Task Spawning:**
   *Endpoint API yang secara naif menjalankan `asyncio.create_task()` untuk setiap request yang masuk dapat dieksploitasi hingga server Out-of-Memory (OOM).*
   *Hardening:* Batasi konkurensi maksimum global menggunakan `asyncio.Semaphore`.

3. **Exception Information Leakage:**
   *Pohon `ExceptionGroup` dapat merembeskan stacktrace dari infrastruktur internal ke response client.*
   *Hardening:* Intersept seluruh exception di boundary layer dan sanitasi pesan error sebelum dikirim ke luar sistem.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Mengaktifkan Asynchronous Debug Mode
Untuk mendeteksi blocking code yang memperlambat event loop, aktifkan debug mode CPython:
```bash
$ export PYTHONASYNCIODEBUG=1
```
Atau secara programmatic di awal eksekusi:
```python
loop = asyncio.get_running_loop()
loop.set_debug(True)
# Mengatur batas minimum (dalam detik) peringatan eksekusi callback lambat
loop.slow_callback_duration = 0.05  # 50 milidetik
```
Jika ada fungsi blocking yang memakan waktu lebih dari 50ms, event loop akan mencetak peringatan ke logger:
`Executing <Handle ...> took 0.120 seconds!`

### Visualisasi Introspeksi Task
Untuk men-debug kondisi deadlock atau task yang menggantung, dump seluruh task yang aktif saat ini:
```python
def dump_all_active_tasks():
    tasks = asyncio.all_tasks()
    logger.critical(f"Currently active pending tasks count: {len(tasks)}")
    for t in tasks:
        logger.critical(f"Task {t.get_name()} -> State: {t._state}, Frame: {t.get_stack(limit=1)}")
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Sintaks & Primitif Kunci (Python 3.11+)

```python
# Entrypoint Aplikasi
asyncio.run(main())

# Mendapatkan loop aktif
loop = asyncio.get_running_loop()

# Structured Concurrency (Modern)
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(coro1(), name="Worker-1")
    task2 = tg.create_task(coro2(), name="Worker-2")
# Di titik ini, seluruh task dijamin selesai atau dibatalkan.

# Structured Timeout
async with asyncio.timeout(5.0):
    await perform_io()

# Mengabaikan timeout pembatalan (Protection Critical Work)
await asyncio.shield(save_database_transaction())

# Delegasi Synchronous / Blocking Code
result = await asyncio.to_thread(sync_blocking_function, arg1, arg2)

# Primitif Sinkronisasi
lock = asyncio.Lock()               # Mutex mutual exclusion
sem = asyncio.Semaphore(10)         # Pembatas throughput koneksi
event = asyncio.Event()             # Sinyal broadcasting antar task (set/wait)
queue = asyncio.Queue(maxsize=100)  # FIFO pipeline dengan backpressure
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman Anda terhadap arsitektur dan mekanisme internal `asyncio`.

### Soal Tingkat Dasar (Basic)

1. **Apa yang terjadi secara internal jika sebuah fungsi yang dideklarasikan dengan `async def` dipanggil tanpa menggunakan kata kunci `await`?**
   * A. Fungsi langsung dieksekusi secara otomatis di thread terpisah.
   * B. Mengembalikan coroutine object yang tidak dieksekusi sama sekali, disertai potensi warning dari Python.
   * C. Menghasilkan pesan kesalahan sintaks (*SyntaxError*).
   * D. Event loop memblokir proses hingga fungsi selesai.

2. **Manakah metode yang benar untuk menjalankan fungsi I/O blocking synchronous (misal: penulisan file standar atau library legacy) dari dalam coroutine di Python 3.9+?**
   * A. `await asyncio.run(blocking_func)`
   * B. `await asyncio.to_thread(blocking_func)`
   * C. `asyncio.create_task(blocking_func)`
   * D. `yield from blocking_func`

3. **Perilaku default apa yang membedakan `asyncio.TaskGroup` dibandingkan `asyncio.gather` ketika salah satu child task gagal dan melempar exception?**
   * A. `TaskGroup` mendiamkan exception dan terus melanjutkan task yang tersisa.
   * B. `TaskGroup` secara otomatis membatalkan seluruh task lain yang berada di dalam grup tersebut.
   * C. `TaskGroup` melempar thread panic dan mematikan seluruh interpreter Python.
   * D. Tidak ada perbedaan fungsional; keduanya identik.

4. **Bagaimana hierarki kelas exception `asyncio.CancelledError` pada Python versi 3.8 dan yang lebih baru?**
   * A. Mewarisi langsung dari `Exception`.
   * B. Mewarisi langsung dari `StandardError`.
   * C. Mewarisi langsung dari `BaseException`.
   * D. Mewarisi langsung dari `RuntimeError`.

5. **Apa fungsi utama dari parameter `maxsize` pada inisialisasi `asyncio.Queue`?**
   * A. Membatasi ukuran byte payload yang dapat dimasukkan ke queue.
   * B. Mengimplementasikan mekanisme backpressure dengan menahan (`await put()`) saat queue penuh.
   * C. Memaksa queue menghapus item paling lama jika kapasitas terlampaui (*drop oldest*).
   * D. Menentukan batas jumlah worker yang boleh membaca queue secara paralel.

---

### Soal Tingkat Lanjutan (Intermediate)

6. **Diberikan skenario di mana task `A` sedang menunggu pada `await asyncio.shield(task_B)`. Jika task `A` menerima sinyal pembatalan (`cancel()`), apa yang terjadi pada task `B`?**
   * A. `task_B` akan langsung ikut dibatalkan secara bersamaan.
   * B. `task_B` melempar `SystemError` karena kehilangan referensi induk.
   * C. `task_B` terus berjalan hingga selesai tanpa terpengaruh pembatalan pada `task_A`.
   * D. Event loop langsung membekukan eksekusi `task_B`.

7. **Mengapa penulisan exception handling berikut dianggap sebagai anti-pattern fatal pada asyncio modern?**
   ```python
   try:
       await do_critical_network_job()
   except BaseException:
       logger.error("Job failed")
   ```
   * A. Mengurangi performa CPython bytecode compiler hingga 50%.
   * B. Menelan `CancelledError`, sehingga Task menolak dibatalkan dan menggantungkan koordinasi shutdown `TaskGroup`.
   * C. `BaseException` tidak dapat menangkap kesalahan parsing JSON.
   * D. Menyebabkan runtime melepaskan lock secara sepihak.

8. **Bagaimana mekanisme internal CPython mengonstruksi pemanggilan kembali (*resumption*) dari coroutine yang sedang di-suspend saat I/O socket telah siap?**
   * A. Kernel mengirimkan interupsi hardware langsung ke register CPU task.
   * B. OS I/O Demultiplexer memberitahu selector loop, yang kemudian memindahkan callback `Task.__wakeup` ke Ready Queue loop.
   * C. Thread background tersembunyi secara preemptif membangunkan coroutine tersebut.
   * D. Coroutine terus-menerus mem-polling kernel dalam teknik *busy-waiting loop*.

9. **Jika Anda menjalankan kode berikut di dalam thread utama: `time.sleep(5)`, apa dampaknya terhadap task background asyncio yang sedang menunggu timer `asyncio.sleep(1)`?**
   * A. Task background tetap berjalan tepat waktu karena asyncio menggunakan multithreading internal.
   * B. Task background terhenti total dan baru dapat merespons timer setelah 5 detik berlalu ketika thread utama dibebaskan.
   * C. Event loop memotong eksekusi `time.sleep(5)` secara paksa demi menjamin SLA latency.
   * D. Python runtime akan mendistribusikan task yang tertunda ke core CPU lain secara instan.

10. **Bagaimana `contextvars.ContextVar` mempertahankan integritas nilai antar-task jika dibandingkan dengan `threading.local`?**
    * A. Menyimpan context di file deskriptor OS kernel.
    * B. Mengabaikan konteks induk dan selalu mengembalikan nilai default global.
    * C. Mengimplementasikan struktur data immutable yang disalin secara aman (shallow copy context) ke task anak saat `create_task()` dipanggil.
    * D. Membatasi agar setiap context variable hanya bisa dibaca oleh satu task saja sepanjang waktu.

---

### Kunci Jawaban & Rasional

1. **B**: Sintaks `async def` menghasilkan coroutine generator wrapper. Memanggil fungsinya hanya mengalokasikan objek coroutine, bukan mengeksekusinya.
2. **B**: `asyncio.to_thread()` adalah abstraction layer resmi tingkat tinggi untuk mengalihkan blocking call ke default worker `ThreadPoolExecutor` internal loop tanpa membekukan event loop.
3. **B**: Karakteristik Structured Concurrency mewajibkan pola fail-fast: kegagalan salah satu child task memicu pembatalan menyeluruh pada task saudara lainnya di TaskGroup yang sama.
4. **C**: Di Python 3.8+, `CancelledError` diturunkan dari `BaseException` untuk mencegahnya tertangkap secara tidak sengaja oleh blok `except Exception:` umum.
5. **B**: Kapasitas batas atas queue memaksa produsen menunggu (`await queue.put()`) saat kapasitas penuh, membangun mekanisme kendali laju aliran transmisi data (*backpressure*).
6. **C**: `asyncio.shield` memutus propagasi pembatalan dari pemanggil ke inner task. Task A menerima `CancelledError`, namun Task B tetap berjalan sampai selesai.
7. **B**: Menangkap `BaseException` tanpa melempar kembali (`re-raise`) `CancelledError` akan mematikan mekanisme pembatalan terkoordinasi, menyebabkan runtime hangs saat shutdown.
8. **B**: Asyncio tidak menggunakan busy waiting. Event multiplexer (seperti `epoll`) mengembalikan daftar FD yang aktif, memicu loop memasukkan callback internal task ke dalam `_ready` FIFO queue.
9. **B**: Karena asyncio berjalan pada single-thread, `time.sleep` memblokir thread OS tersebut sepenuhnya. Conductor (loop) terkunci; tidak ada task lain yang dapat diproses hingga kontrol CPU kembali.
10. **C**: `ContextVar` menggunakan paradigma functional programming (copy-on-write context mapping). Task baru mewarisi snapshot context task pembuatnya tanpa risiko race condition antar task selevel.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: High-Performance Distributed Rate-Limited Web Health Aggregator

#### Deskripsi
Bangun sebuah utilitas baris perintah (*CLI Service*) produksi yang bertugas memeriksa *health-check status* dari 100 URL eksternal secara bersamaan dengan pembatasan (*rate-limiting*) yang sangat ketat dan proteksi konkurensi terstruktur.

#### Spesifikasi Fungsional & Arsitektural:
1. **Concurrency Constraints:**
   * Tidak boleh ada lebih dari **7 request keluar (outgoing HTTP calls)** yang berjalan bersamaan di waktu yang sama (Gunakan `asyncio.Semaphore`).
   * Menggunakan model **Structured Concurrency** (`asyncio.TaskGroup`) di Python 3.11+. Tidak diizinkan menggunakan `asyncio.gather`.
2. **Resilience & Timeouts:**
   * Setiap request per target URL memiliki ambang batas timeout maksimal **1.5 detik** menggunakan `asyncio.timeout`.
   * Jika request timeout atau mengembalikan kode 5xx, sistem harus mencoba ulang (*retry*) maksimal 2 kali dengan *exponential backoff*.
3. **Producer-Consumer Architecture:**
   * URL dimasukkan ke dalam `asyncio.Queue(maxsize=20)`.
   * Sebanyak 5 worker coroutine membaca dari antrean tersebut dan mengumpulkan hasil ke shared thread-safe datastructure.
4. **Graceful Shutdown Protocol:**
   * Tangkap sinyal `SIGINT` (Ctrl+C). Ketika sinyal diterima, hentikan pengambilan URL baru dari antrean, tunggu task yang sedang berjalan di dalam worker menyelesaikan tugasnya (maksimal 3 detik grace period), lalu simpan metrik ke file log lokal sebelum program keluar secara bersih.
5. **Observabilitas:**
   * Tampilkan progress log secara non-blocking yang menginformasikan: Task ID, Waktu Latensi (ms), Status Respon, dan Sisa Isi Queue.
   * Debug flag harus tersedia untuk mengidentifikasi jika ada operasi sinkron yang menahan event loop melebihi 20ms.