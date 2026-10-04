# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Internal Asyncio**: Menguraikan siklus hidup `EventLoop`, `Task`, `Future`, mekanisme low-level `selectors` (`epoll`/`kqueue`), serta membandingkan performa *default event loop* CPython dengan `uvloop`.
2. **Menguasai Structured Concurrency & Synchronization Primitives**: Mengimplementasikan `asyncio.TaskGroup`, `asyncio.Queue`, `asyncio.Semaphore`, `asyncio.Event`, dan `asyncio.Condition` untuk mencegah *task leakage* serta mengelola konkurensi terkontrol.
3. **Membangun Arsitektur Resilient & Graceful Shutdown**: Merancang *lifecycle manager* yang menangani sinyal OS (`SIGINT`, `SIGTERM`), eksekusi *cleanup*, *draining queues*, pembatalan tugas bertingkat (*cascading cancellation*), dan *exception handling* berbasis `ExceptionGroup`.
4. **Mengintegrasikan Async I/O dengan CPU-bound Task**: Menerapkan delegasi komputasi berat menggunakan `concurrent.futures.ProcessPoolExecutor` dan `ThreadPoolExecutor` secara asinkron tanpa memblokir thread loop utama.
5. **Mendeteksi dan Memitigasi Bottleneck Produksi**: Melakukan *debugging*, *profiling* latensi loop, *blocking call detection*, dan *memory leak profiling* menggunakan modul `tracemalloc`, `asyncio` debug mode, dan metrik latensi I/O.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar coroutine (`async`/`await`) dan generator Python.
* Pemrograman multithreading dan multiprocessing dasar di CPython beserta batasan Global Interpreter Lock (GIL).
* Pengetahuan fundamental POSIX I/O: Socket, File Descriptor (FD), non-blocking I/O mode, dan TCP handshake.
* Python 3.11+ (fitur modern: `TaskGroup`, `ExceptionGroup`, context managers asinkron).

---

## 3. Concept & Internal Architecture

Asyncio bukan thread manager, melainkan kerangka kerja *single-threaded cooperative multitasking* berbasis *Event Loop*.

```
+-------------------------------------------------------------------------+
|                              Python User Code                           |
|      async def foo(): await bar()      TaskGroup / Queue / Semaphore    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                           Asyncio Framework Layer                       |
|   +-----------------------+                    +--------------------+   |
|   |         Task          | --(wraps)--------> |       Future       |   |
|   | (drives coroutines)   |                    | (holds state/res)  |   |
|   +-----------------------+                    +--------------------+   |
|               |                                           |             |
|               +--------------------+----------------------+             |
|                                    v                                    |
|                      +--------------------------+                       |
|                      |        Event Loop        |                       |
|                      |  - Ready Queue (deque)   |                       |
|                      |  - Scheduled (min-heap)  |                       |
|                      +--------------------------+                       |
+-----------------------------------|-------------------------------------+
                                    v
+-------------------------------------------------------------------------+
|                      I/O Multiplexing (Selectors)                       |
|        Linux: epoll      |      macOS/BSD: kqueue      |  Windows: IOCP |
+-----------------------------------|-------------------------------------+
                                    v
+-------------------------------------------------------------------------+
|                             OS Kernel Space                             |
|      Network Sockets / Non-blocking File Descriptors / Timers           |
+-------------------------------------------------------------------------+
```

### A. Anatomi Event Loop CPython
Loop beroperasi dalam siklus deterministik:
1. **Scheduled Timers Execution**: Loop memeriksa min-heap `_scheduled`. Callback yang telah mencapai batas waktu dipindahkan ke antrean `_ready`.
2. **I/O Polling (`selector.select(timeout)`)**: Loop menghitung durasi hingga jadwal timer terdekat berikutnya, menggunakannya sebagai nilai `timeout` untuk memanggil `epoll_wait()` / `kevent()`. Panggilan ini mengembalikan daftar file descriptor (FD) yang berstatus *ready* (bisa dibaca atau ditulis tanpa memblokir kernel).
3. **Execution of Ready Callbacks**: Loop memproses setiap item di antrean FIFO `_ready` (mengeksekusi callback internal, memanggil `.step()` coroutine).
4. **Stopping Criteria Evaluation**: Jika antrean kosong dan tidak ada socket atau task yang terdaftar, loop ditutup.

### B. Coroutine, Task, dan Future
* **Coroutine**: Objek yang dihasilkan dari fungsi `async def`. Objek ini memiliki method internal `.send(val)` dan `.throw(err)`, membungkus *frame execution context*.
* **Future**: Wadah status (*state container*) tingkat rendah yang mewakili hasil akhir dari operasi asinkron yang belum selesai. Memiliki tiga state: `PENDING`, `CANCELLED`, dan `FINISHED`.
* **Task**: Subclass dari `Future` yang bertugas menjalankan coroutine. `Task` menjadwalkan dirinya sendiri ke dalam event loop melalui `loop.call_soon()`. Setiap kali coroutine melakukan `await` pada future yang belum selesai, task melepaskan kendali loop dan menunggu callback penyelesaian dari future tersebut sebelum memanggil `.send()` kembali (*re-entering coroutine*).

### C. Standard Event Loop vs uvloop
* **Default CPython (`asyncio.SelectorEventLoop`)**: Ditulis dalam Python dengan modul C `selectors`. Setiap iterasi loop membawa overhead alokasi objek Python, pengecekan tipe dinamis, dan delegasi callback.
* **uvloop**: Drop-in replacement berbasis **libuv** (mesin C yang menggerakkan Node.js). `uvloop` mengimplementasikan core loop, socket transport, dan state management sepenuhnya di dalam bahasa C/Cython. Mengurangi alokasi memori secara drastis, mengoptimalkan *system call batching*, dan menghasilkan throughput 2–4x lebih tinggi dibanding loop bawaan CPython.

---

## 4. Why & What

| Kategori | Thread-per-Request / Pre-forking | Asynchronous Event Loop (Asyncio) |
| :--- | :--- | :--- |
| **Model Konkurensi** | Preemptive Multitasking | Cooperative Multitasking |
| **Konsumsi Memori** | Tinggi (~2MB–8MB stack size per thread) | Sangat Rendah (~2KB–4KB overhead per task) |
| **Batas Konkurensi** | Terbatas pada ~1.000–5.000 thread per node OS | Mampu mencapai puluhan/ratusan ribu concurrent FD |
| **Konteks Switching** | Ditangani kernel OS (mahal: flushing cache CPU) | Ditangani user space runtime (murah: function state switch) |
| **Kelemahan Fatal** | Race conditions tak terprediksi, overhead memori | Satu blocking call non-async akan melumpuhkan seluruh loop |

### Mengapa Asyncio?
Ketika aplikasi enterprise menangani puluhan ribu koneksi I/O simultan (misalnya WebSocket, microservice aggregator, streaming pipeline), thread model tradisional gagal karena *kernel thread exhaustion* dan tingginya biaya *CPU cache thrashing*. Asyncio memecahkan masalah ini dengan mempertahankan model single-thread (atau sedikit worker) yang secara selektif memproses FD berbasis ketersediaan event di layer OS kernel.

---

## 5. How (Workflow Detail)

Alur kerja eksekusi asinkron end-to-end:

```
[User invokes: await reader.read(1024)]
              |
              v
[Task melepaskan eksekusi, Socket didaftarkan ke Selector dengan mode READ]
              |
              v
[Selector Engine memanggil epoll_ctl(EPOLL_CTL_ADD, fd, EPOLLIN)]
              |
              v
[Event Loop melanjutkan eksekusi Task lain di ready queue...]
              |
              v
[OS Kernel: Data paket TCP tiba di NIC -> buffer kernel terisi]
              |
              v
[Selector Engine: epoll_wait() mengembalikan status FD Ready]
              |
              v
[Event Loop memicu Callback Socket Transport]
              |
              v
[Callback membaca raw byte dari socket -> mengisi internal Future result]
              |
              v
[Future.set_result(data) -> Memindahkan Task terkait ke Event Loop ready queue]
              |
              v
[Event Loop memanggil task.__step() -> Coroutine melanjutkan eksekusi pasca-await]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Dapur Restoran Bintang Lima

* **Multithreading (Preemptive)**: Anda menyewa 100 koki. Setiap koki bertanggung jawab atas 1 pesanan. Saat memanggang daging selama 30 menit, koki tersebut berdiri diam di depan oven. Dapur segera penuh sesak, biaya sewa koki mahal, dan mereka sering bertabrakan di lorong.
* **Asyncio (Cooperative Single-Threaded)**: Anda menyewa 1 *Executive Chef* jenius (Loop) dan memberinya 100 timer digital (OS Kernel Epoll). Chef memasukkan daging ke oven, menyalakan timer (register FD), lalu segera memotong sayuran untuk pesanan lain. Ketika timer oven berdering (*I/O ready*), Chef kembali ke oven untuk mengeluarkan daging. Chef tidak pernah berdiri menganggur.

### Diagram: Task Lifecycle & Synchronization Architecture

```
                       +----------------------+
                       |      Task Created    |
                       +----------------------+
                                  |
                                  v
+-------------------> [ Ready Queue: loop._ready ]
|                                 |
|                                 v
|                      +----------------------+
|                      | Task runs: .__step() |
|                      +----------------------+
|                                 |
|         +-----------------------+-----------------------+
|         | Await unready Future  | Yield via sleep/I/O   | Completed/Error
|         v                       v                       v
|  +--------------+       +---------------+       +---------------+
|  | Register     |       | Add to        |       | State:        |
|  | callback to  |       | _scheduled    |       | FINISHED or   |
|  | Future       |       | (Min-Heap)    |       | EXCEPTION     |
|  +--------------+       +---------------+       +---------------+
|         |                       |                       |
|         v                       v                       v
|  [ Wait FD / I/O ]      [ Timeout Expired ]     [ Remove from   ]
|         |                       |               [ Parent Group  ]
+---------+-----------------------+
```

---

## 7. Implementation: Simple vs. Practical Production Example

### A. Simple Example (Anti-Pattern vs Modern TaskGroup)

```python
# GAYA LAMA (DEPRECATED PATTERN DI PRODUKSI MODERN): asyncio.gather
# Kekurangan: Jika satu task gagal, task lain tetap berjalan liar (orphan/leaked tasks)
import asyncio

async def fetch_data(id: int):
    if id == 2:
        raise ValueError("Data corrupt!")
    await asyncio.sleep(0.1)
    return {"id": id, "data": "valid"}

async def old_runner():
    try:
        results = await asyncio.gather(fetch_data(1), fetch_data(2), fetch_data(3))
    except Exception as e:
        print(f"Error caught: {e}") # fetch_data(1) dan (3) berisiko tetap hidup tanpa kontrol!
```

```python
# GAYA MODERN (PYTHON 3.11+): Structured Concurrency dengan asyncio.TaskGroup
# Keunggulan: Otomatis membatalkan task saudara jika salah satu task mengalami kegagalan.
import asyncio

async def modern_runner():
    try:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(fetch_data(1))
            t2 = tg.create_task(fetch_data(2))
            t3 = tg.create_task(fetch_data(3))
        # Seluruh task dijamin selesai sebelum block context keluar
        print(t1.result(), t3.result())
    except* ValueError as eg:  # ExceptionGroup filtering
        for exc in eg.exceptions:
            print(f"Caught structured failure: {exc}")
```

### B. Practical Production Example: Resilient Worker Pipeline

Arsitektur produksi: Worker pool berbasis worker-queue dengan graceful shutdown, rate limiting melalui Semaphore, backpressure, dan penanganan sinyal OS terpadu.

```python
#!/usr/bin/env python3
import asyncio
import logging
import signal
import sys
from typing import NoReturn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(taskName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EnterpriseAsyncPipeline")

class ResilientPipeline:
    def __init__(self, max_concurrency: int = 5, queue_capacity: int = 50):
        self.queue: asyncio.Queue[int] = asyncio.Queue(maxsize=queue_capacity)
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.shutdown_event = asyncio.Event()
        self.worker_tasks: list[asyncio.Task] = []

    async def producer(self) -> None:
        """Memproduksi data ke antrean dengan backpressure terkontrol."""
        payload_id = 0
        try:
            while not self.shutdown_event.is_set():
                payload_id += 1
                # Backpressure terjadi di sini jika queue penuh (queue.put akan block)
                await self.queue.put(payload_id)
                logger.info(f"Produced payload: #{payload_id} (Queue Size: {self.queue.qsize()})")
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info("Producer menerima sinyal terminasi. Menghentikan produksi.")
            raise

    async def worker(self, worker_id: int) -> None:
        """Memproses item antrean dengan proteksi semaphore & retry logic."""
        logger.info(f"Worker-{worker_id} diinisialisasi.")
        while True:
            try:
                # Mengambil tugas dengan timeout singkat agar worker bisa mengevaluasi shutdown_event
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if self.shutdown_event.is_set() and self.queue.empty():
                    break
                continue
            except asyncio.CancelledError:
                break

            try:
                async with self.semaphore:
                    await self._process_payload(worker_id, item)
            finally:
                self.queue.task_done()

        logger.info(f"Worker-{worker_id} selesai dan membersihkan state.")

    async def _process_payload(self, worker_id: int, item: int) -> None:
        """Simulasi I/O bounded processing dengan error boundary."""
        logger.info(f"Worker-{worker_id} memproses item #{item}")
        await asyncio.sleep(0.2)  # Simulasi request HTTP / query database

    async def run(self) -> None:
        # Inisialisasi pool worker
        for i in range(5):
            task = asyncio.create_task(self.worker(i), name=f"WorkerTask-{i}")
            self.worker_tasks.append(task)

        producer_task = asyncio.create_task(self.producer(), name="ProducerTask")

        # Tunggu sampai sinyal shutdown diterima
        await self.shutdown_event.wait()

        # Mulai proses Graceful Shutdown
        logger.info("Memulai proses Graceful Shutdown...")
        producer_task.cancel()
        await asyncio.gather(producer_task, return_exceptions=True)

        logger.info("Menunggu pengurasan antrean (Draining queue)...")
        await self.queue.join()

        logger.info("Menghentikan seluruh worker task...")
        for task in self.worker_tasks:
            task.cancel()
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        logger.info("Pipeline berhasil dimatikan secara bersih tanpa kehilangan data.")

def register_signal_handlers(pipeline: ResilientPipeline, loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(trigger_shutdown(pipeline, sig))
        )

async def trigger_shutdown(pipeline: ResilientPipeline, sig: signal.Signals) -> None:
    logger.warning(f"Sinyal {sig.name} tertangkap! Mengaktifkan shutdown pipeline.")
    pipeline.shutdown_event.set()

async def main() -> None:
    loop = asyncio.get_running_loop()
    pipeline = ResilientPipeline(max_concurrency=3, queue_capacity=10)
    register_signal_handlers(pipeline, loop)
    await pipeline.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: Multi-Source IoT Ingestion Gateway
* **Problem**: Sebuah enterprise armada logistik menerima paket telemetri GPS dari 100.000 kendaraan setiap 5 detik melalui koneksi TCP raw/WebSocket. Sistem sebelumnya (berbasis multithreading WSGI worker) kolaps pada 4.000 koneksi karena *memory exhaustion* (alokasi memori OS thread mencapai >32GB) dan koneksi drop massal.
* **Architecture Solution**:
  1. Digunakan edge-layer berbasis Python 3.11 dengan `uvloop` dan protokol kustom `asyncio.Protocol` (bukan Stream layer yang memiliki overhead abstraksi lebih tinggi).
  2. Implementasi **Backpressure Control**: Jika buffer downstream (Kafka broker sink) melambat, socket ingress secara dinamis memanggil `transport.pause_reading()` untuk menghentikan konsumsi kernel TCP window. Begitu buffer terurai di bawah batas ambang bawah (low watermark), ingress memanggil `transport.resume_reading()`.
  3. Memisahkan deserialisasi komputasi CPU-bound (protokol parsing biner/Protobuf) ke sub-proses `ProcessPoolExecutor` melalui antrean `asyncio.Queue` terisolasi, menjaga latency loop tetap di bawah 1 milidetik.
* **Hasil**:
  * Penggunaan memori berkurang dari 32GB menjadi **1.2GB**.
  * Konkurensi stabil menangani **100.000 koneksi aktif simultan** dengan p99 latency < 15ms.

---

## 9. Trade-Offs

| Faktor Desain | Menggunakan Asyncio Murni | Menggunakan Worker Multi-Threaded | Hybrid (Asyncio + ProcessPool) |
| :--- | :--- | :--- | :--- |
| **Throughput (I/O)** | Maksimum (100k+ RPS) | Menengah (~5k–10k RPS) | Sangat Tinggi |
| **CPU-Bound Latency**| Sangat Buruk (Loop terblokir) | Terbatas oleh GIL CPython | Optimal (Load balance ke multi-core) |
| **Kompleksitas Kode**| Tinggi (harus bebas dari blocking call) | Menengah (locking race condition) | Sangat Tinggi (IPC serialization overhead) |
| **Memory Footprint** | Minimal (~beberapa KB/koneksi) | Besar (MB per thread stack) | Moderat (memory per process pool) |
| **Cost Infrastructure**| Rendah (Optimalisasi node hemat biaya) | Sangat Tinggi (Server besar & vertikal) | Efisien (Linear scaling per CPU Core) |

---

## 10. Common Mistakes & Troubleshooting

### 1. Memanggil Fungsi Pemblokir (Blocking I/O)
* **Penyebab**: Menjalankan library sinkron seperti `requests.get()`, `time.sleep()`, atau query DB blocking (`psycopg2`) di dalam coroutine.
* **Dampak**: Seluruh event loop berhenti. Semua task client lain mengalami pembekuan (freezing) koneksi.
* **Solusi**: Gunakan library native non-blocking (`httpx`, `asyncpg`) atau delegasikan ke executor:
  ```python
  loop = asyncio.get_running_loop()
  result = await loop.run_in_executor(None, sync_blocking_function, arg1)
  ```

### 2. Task Leaks ("Fire and Forget" Trap)
* **Penyebab**: Memanggil `asyncio.create_task(coro())` tanpa menyimpan referensi task atau tanpa pengawasan `TaskGroup`.
* **Dampak**: Exception yang terjadi di dalam task tersebut hilang ditelan runtime (*Task exception was never retrieved*), dan saat garbage collector menghapus objek task yang belum selesai, koneksi socket atau file handling menjadi zombie leak.
* **Solusi**: Kelola masa hidup task menggunakan `asyncio.TaskGroup` atau simpan dalam `set` referensi global yang secara eksplisit dihapus saat task selesai melalui `task.add_done_callback()`.

### 3. Starvation Akibat Unbounded Concurrency
* **Penyebab**: Menggunakan `asyncio.gather(*[worker(i) for i in range(100_000)])` sekaligus tanpa batas penahan.
* **Dampak**: Menghabiskan *file descriptors* OS (`OSError: [Errno 24] Too many open files`), dan membanjiri downstream backend (Database Connection Exhaustion).
* **Solusi**: Terapkan `asyncio.Semaphore(value=MAX_CONCURRENCY)` untuk membatasi eksekusi aktif.

---

## 11. Best Practices (Production Checklist)

- [ ] **Aktifkan Asyncio Debug Mode di Lingkungan Staging**: Set `PYTHONASYNCIODEBUG=1` atau `loop.set_debug(True)` untuk mendeteksi blocking call yang melebihi batas waktu (misal >100ms).
- [ ] **Gunakan `uvloop` di Lingkungan Linux Produksi**: Inisialisasi sedini mungkin:
  ```python
  import uvloop
  uvloop.install()
  ```
- [ ] **Standardisasi Python 3.11+ `TaskGroup`**: Tinggalkan `asyncio.gather` untuk eksekusi paralel yang membutuhkan integritas transaksional dan isolasi error.
- [ ] **Tentukan Batas Timeout di Setiap Eksekusi I/O**: Jangan pernah menunggu socket tanpa timeout. Bungkus dengan `asyncio.timeout(seconds)`:
  ```python
  async with asyncio.timeout(5.0):
      await client.connect()
  ```
- [ ] **Terapkan Batas Antrean (Bounded Queues)**: Selalu deklarasikan `asyncio.Queue(maxsize=N)`. Antrean *unbounded* akan menghabiskan memori RAM ketika laju penerimaan (*arrival rate*) melampaui laju pemrosesan (*service rate*).
- [ ] **Tangani Sinyal OS Secara Bersih**: Pastikan `SIGINT` dan `SIGTERM` memicu penutupan resource, draining queue, dan pemutusan koneksi DB/broker dengan benar.

---

## 12. Hands-on Practice

Buat dan jalankan pipeline resilient lengkap dengan sistem profiling blocking call di direktori `hands-on/m02/`.

### Langkah 1: Persiapan Struktur Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat File `pipeline_engine.py`

```python
# hands-on/m02/pipeline_engine.py
import asyncio
import time
import sys

# Aktifkan runtime debug mode untuk mendeteksi event loop blockage
async def simulate_io_call(item_id: int):
    # Simulasi latency asinkron yang sehat
    await asyncio.sleep(0.05)
    return f"Processed-{item_id}"

async def simulate_unintentional_blocking_call():
    # Meniru developer pemula yang memanggil sleep blocking
    # Loop debug mode akan mencatat peringatan jika waktu eksekusi > threshold
    time.sleep(0.15)

async def worker(queue: asyncio.Queue, worker_id: int):
    while True:
        item = await queue.get()
        try:
            if item == 999: # Trigger block
                await simulate_unintentional_blocking_call()
            res = await simulate_io_call(item)
            print(f"[Worker-{worker_id}] Finished: {res}")
        finally:
            queue.task_done()

async def main():
    loop = asyncio.get_running_loop()
    # Log blocking callback yang berjalan lebih lama dari 100ms
    loop.slow_callback_duration = 0.100

    queue = asyncio.Queue(maxsize=20)
    workers = [asyncio.create_task(worker(queue, i), name=f"Worker-{i}") for i in range(3)]

    # Kirim payload data
    for i in range(10):
        await queue.put(i)
    
    # Sisipkan payload yang memicu blocking call
    await queue.put(999)

    await queue.join()

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    print("Pipeline Execution Completed Successfully.")

if __name__ == "__main__":
    # Jalankan dengan debug mode aktif
    asyncio.run(main(), debug=True)
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan file tersebut menggunakan terminal:
```bash
python3 pipeline_engine.py
```

*Verifikasi output*: Anda akan melihat log runtime standar diikuti peringatan internal asyncio debug engine:
`Executing <Task pending ...> took 0.15X seconds`, yang membuktikan bahwa event loop secara presisi mengidentifikasi lokasi blocking code.

---

## 13. Exercises

### Level Easy
Modifikasi kode pada bagian `pipeline_engine.py` agar menangkap kegagalan I/O ketika nilai payload bernilai negatif (`item < 0`). Error harus ditangani di tingkat worker tanpa menghentikan worker lain yang sedang berjalan, dan nilai error tersebut harus dicatat ke dictionary *failure counter*.

### Level Medium
Buat sebuah kelas `DynamicBatcher` menggunakan `asyncio.Queue` yang mengumpulkan item hingga mencapai ukuran batch 50 item ATAU batas waktu akumulasi 200ms tercapai (mana yang lebih dulu terpenuhi). Setelah salah satu syarat tercapai, batch tersebut diproses secara asinkron ke downstream mock handler.

### Level Hard
Rancang arsitektur **Rate-Limited Distributed Scraper Pool** dengan spesifikasi:
* Mampu mengeksekusi 1.000 job scraping konkuren.
* Dibatasi oleh global rate limit sebesar 50 request per detik per domain menggunakan algoritma **Token Bucket** berbasis asinkron murni (`asyncio.Lock` dan `asyncio.sleep`).
* Tangani skenario di mana server target mengembalikan HTTP 429: sistem harus menahan (*backoff*) seluruh task yang membidik domain tersebut selama durasi tertentu tanpa menghentikan task yang membidik domain lain.

---

## 14. Real-World Architectural Challenge

**Konteks Kasus**:
Anda adalah Principal Systems Architect di sebuah bursa perdagangan aset kripto (*crypto exchange*). Anda diminta merancang sistem **Real-Time Market Data Broadcaster**.

**Spesifikasi Persyaratan Sistem**:
1. Gateway harus mempertahankan 50.000 koneksi WebSocket client secara simultan.
2. Menerima feed stream market depth dari core matching engine (format protobuf biner) dengan volume rata-rata 25.000 message/detik.
3. Setiap client memiliki bandwidth jaringan yang bervariasi. *Slow consumer* (client dengan koneksi seluler buruk) tidak boleh membuat buffer memori gateway membengkak, dan sama sekali tidak boleh memperlambat pengiriman data ke *fast consumer*.
4. Jika buffer pengiriman untuk client tertentu melampaui 100 paket yang belum terkirim, koneksi client tersebut harus diputus secara sepihak (*drop slow client policy*) demi melindungi integritas server.
5. Gunakan structured concurrency, custom memory tracking, dan zero non-async dependencies.

**Tugas Anda**: Buat spesifikasi desain arsitektur lengkap beserta skeleton kode implementasinya (menggunakan socket server non-blocking murni atau modul transport/protocol asyncio), lengkapi dengan mekanisme pendeteksian backpressure dan proteksi OOM (Out-Of-Memory).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Konseptual & Fundamental)

1. **Apa perbedaan mendasar antara implementasi `asyncio.sleep(1)` dan `time.sleep(1)` di dalam sebuah coroutine?**
   * *Jawaban*: `asyncio.sleep(1)` mendaftarkan callback timer ke dalam min-heap event loop dan melepaskan kontrol eksekusi (*yield control*) sehingga coroutine lain dapat berjalan selama 1 detik tersebut. Sebaliknya, `time.sleep(1)` adalah panggilan sistem sinkron yang memblokir OS thread saat itu secara penuh; event loop tidak dapat berputar, dan semua coroutine lain ikut terhenti selama 1 detik.

2. **Mengapa pemanggilan fungsi async tanpa kata kunci `await` (contoh: memanggil `fetch()` di baris kode tanpa penampung) tidak mengeksekusi fungsi tersebut?**
   * *Jawaban*: Di Python, memanggil fungsi `async def` hanya menghasilkan sebuah *coroutine object*, belum menjadwalkannya ke event loop. Coroutine baru dieksekusi jika dimasukkan ke event loop melalui `await`, dibungkus ke dalam `asyncio.Task` melalui `create_task()`, atau dieksekusi dengan `asyncio.run()`.

3. **Kapan sebuah objek Python berstatus "awaitable"?**
   * *Jawaban*: Suatu objek bersifat *awaitable* jika mengimplementasikan method internal `__await__()` yang mengembalikan iterator, atau merupakan instance dari `asyncio.Future` / `asyncio.Task` / objek coroutine native yang dihasilkan dari fungsi `async def`.

4. **Apa fungsi utama dari `asyncio.Semaphore` dalam pemrosesan data paralel?**
   * *Jawaban*: Berfungsi membatasi jumlah konkurensi maksimum dari tugas yang mengakses resource bersama (seperti koneksi database atau remote API) secara bersamaan guna mencegah resource exhaustion.

5. **Apa keunggulan arsitektural `asyncio.TaskGroup` (Python 3.11+) dibandingkan `asyncio.gather`?**
   * *Jawaban*: `TaskGroup` menerapkan *Structured Concurrency*. Jika salah satu sub-task di dalam `TaskGroup` gagal (melempar exception), task lain yang berada di dalam grup yang sama otomatis dibatalkan (*cascading cancellation*), dan seluruh error dibungkus secara aman di dalam `ExceptionGroup`. `asyncio.gather` tidak membatalkan task saudara yang masih berjalan secara otomatis, berpotensi memicu *task leakage*.

---

### Bagian B: Intermediate (Arsitektur & Troubleshooting)

6. **Bagaimana cara kerja integrasi antara `ThreadPoolExecutor` dengan Asyncio Event Loop ketika menjalankan fungsi legacy synchronous?**
   * *Jawaban*: Fungsi dijalankan pada OS thread terpisah di dalam worker pool. Event loop membuat `asyncio.Future` di thread utama. Ketika thread pool selesai mengeksekusi fungsi, callback thread pool memanggil `loop.call_soon_threadsafe(future.set_result, data)`, yang secara aman menyuntikkan hasil kembali ke antrean `_ready` pada event loop di thread utama.

7. **Jelaskan siklus hidup (*lifecycle*) status pada sebuah objek `asyncio.Future`!**
   * *Jawaban*: Dimulai dari status `PENDING` saat diinisialisasi. Status berpindah ke `FINISHED` ketika nilainya diisi via `.set_result(val)` atau saat exception disuntikkan via `.set_exception(err)`. Jika method `.cancel()` dipanggil sebelum penyelesaian, statusnya berpindah ke `CANCELLED`. Sekali berpindah dari `PENDING`, status tidak dapat diubah kembali.

8. **Mengapa mutating data structure global (seperti `dict` bawaan Python) di dalam coroutine asyncio yang berjalan pada satu loop umumnya tidak membutuhkan `asyncio.Lock`, namun mutasi multi-langkah tetap memerlukannya?**
   * *Jawaban*: Pada single-thread event loop, operasi atomik tunggal (seperti `d[k] = v`) tidak akan diinterupsi karena multitasking bersifat *kooperatif* (hanya berpindah konteks pada titik `await`). Namun, operasi multi-langkah yang diselingi `await` (seperti *read-then-await-then-write*) rentan mengalami interupsi eksekusi oleh task lain di antara titik-titik `await` tersebut, sehingga membutuhkan `asyncio.Lock` untuk menjamin integritas urutan logika.

9. **Apa perbedaan teknis mendasar antara `asyncio.Protocol` / `asyncio.Transport` API dengan `StreamReader` / `StreamWriter` API?**
   * *Jawaban*: `Transport/Protocol` adalah abstraksi low-level berbasis callback (mirip event model Twisted/Node.js) dengan efisiensi memori tinggi dan tanpa layer buffering berlebih. `StreamReader/StreamWriter` adalah layer abstraksi tingkat tinggi berbasis coroutine (`await stream.read()`) yang lebih mudah digunakan, tetapi membawa overhead wrapper alokasi memori internal buffer tambahan.

10. **Bagaimana mekanisme kernel OS seperti `epoll` memberi tahu asyncio bahwa suatu socket siap dibaca tanpa membuang siklus CPU (busy-wait)?**
    * *Jawaban*: Asyncio mendaftarkan FD socket ke kernel via system call `epoll_ctl`. Saat memanggil `epoll_wait`, thread asyncio diistirahatkan (*sleep state*) oleh scheduler OS. Saat paket network tiba, hardware NIC membangkitkan interrupt yang membuat kernel menandai socket tersebut sebagai ready, lalu kernel membangunkan thread event loop tepat pada pemanggilan `epoll_wait` tersebut.

---

### Bagian C: Production Scenarios (Analisis & Solusi)

11. **Skenario Kasus 1**:
    Sebuah microservice analitik berbasis Asyncio mengalami degradasi performa: latensi pemrosesan naik secara eksponensial setelah berjalan selama 6 jam di produksi. CPU usage berada di level 100%, tetapi load network I/O sangat rendah. Profiling menunjukkan ada puluhan ribu task berstatus *pending* yang tidak pernah selesai.
    * *Pertanyaan*: Apa kemungkinan besar *root cause* dari permasalahan arsitektur ini, dan langkah mitigasi apa yang wajib diterapkan?
    * *Jawaban*: Ini adalah indikasi klasik **Task Leakage** yang disertai akumulasi callback di heap memory event loop. Hal ini biasanya dipicu oleh pemanggilan `asyncio.create_task()` untuk background operation yang menunggu `Future` atau socket stream eksternal yang tidak memiliki mekanisme batas waktu (`timeout`), atau karena exception di dalam background task ditekan tanpa memanggil cleanup routine.
    * *Mitigasi*:
      1. Terapkan `asyncio.timeout()` pada seluruh background I/O operations.
      2. Migrasikan seluruh pemanggilan independen ke `asyncio.TaskGroup` (Python 3.11+) untuk memastikan pembatalan deterministik.
      3. Pasang metrik monitoring jumlah task aktif (`len(asyncio.all_tasks())`) ke dashboard observability untuk memicu alert saat terdeteksi anomali pertumbuhan task.

12. **Skenario Kasus 2**:
    Aplikasi web scraper asinkron Anda tiba-tiba terhenti secara mendadak (*silent crash*) tanpa pesan Python traceback di log file ketika dijalankan di dalam container Kubernetes, dan Kubernetes mencatat status container dihentikan dengan status `OOMKilled (Exit Code 137)`.
    * *Pertanyaan*: Mengapa arsitektur asynchronous I/O yang efisien dapat memicu lonjakan penggunaan memori hingga terkena OOM kill, dan bagaimana cara mendesain arsitektur pencegahannya?
    * *Jawaban*: Fenomena ini terjadi akibat **Unbounded Ingestion/Concurrency**. Scraper memproduksi task atau membaca payload jauh lebih cepat daripada laju kapasitas processing atau penyimpanan downstream (kehilangan *Backpressure*). Jika worker menggunakan `asyncio.Queue()` tanpa menentukan kapasitas (`maxsize`), jutaan pesan/byte akan diakumulasikan di RAM, menghabiskan alokasi batas memori cgroup container.
    * *Mitigasi*:
      1. Tentukan batas ketat kapasitas buffer: `asyncio.Queue(maxsize=BOUNDED_VALUE)`.
      2. Terapkan backpressure: producer harus diblokir (`await queue.put()`) saat kapasitas penuh.
      3. Batasi konkurensi total request aktif menggunakan `asyncio.Semaphore`.

13. **Skenario Kasus 3**:
    Saat deployment service WebSocket berskala besar, tim DevOps mengeluhkan bahwa setiap kali pod Kubernetes melakukan rolling update, ribuan koneksi client terputus secara mendadak (`connection reset by peer`), memicu kegagalan transaksi dan *reconnect storm* yang melumpuhkan gateway backend.
    * *Pertanyaan*: Desain arsitektur graceful shutdown seperti apa yang harus diimplementasikan di layer Python Asyncio untuk mengatasi masalah tersebut?
    * *Jawaban*:
      1. Tangkap sinyal `SIGTERM` yang dikirim oleh Kubernetes saat pod akan dimatikan menggunakan `loop.add_signal_handler()`.
      2. Hentikan penerimaan koneksi baru (*stop accepting incoming handshakes*).
      3. Kirim WebSocket Close Frame dengan status code standar (misal 1001 - Going Away) ke seluruh client aktif yang terhubung secara teratur.
      4. Berikan masa tenggang (*grace period drain*) dengan `asyncio.wait_for(queue.join(), timeout=DRAIN_TIMEOUT)` untuk membiarkan in-flight message selesai diproses.
      5. Batalkan sisa worker task yang tersisa secara terstruktur menggunakan pembatalan bertingkat dan pastikan loop ditutup dengan benar sebelum masa `terminationGracePeriodSeconds` Kubernetes berakhir.

---

## 16. Summary

* **Event Loop Engine**: Bekerja secara single-threaded cooperative multitasking menggunakan low-level I/O multiplexer (`epoll`, `kqueue`) dari kernel OS untuk mengoperasikan puluhan ribu socket konkuren dengan alokasi memori minimal.
* **Modern Asyncio Execution**: Python 3.11+ menetapkan **Structured Concurrency** via `asyncio.TaskGroup` sebagai standar industri modern guna mengeliminasi task leakage, menjamin penutupan resource terprediksi, dan mengintegrasikan penanganan error multi-task melalui `ExceptionGroup`.
* **Resilience in Production**: Skalabilitas aplikasi enterprise bergantung pada penerapan batas antrean (**Bounded Queue**), regulasi batas konkurensi (**Semaphore**), deteksi blocking call menggunakan runtime debug engine, isolasi beban CPU-bound via `ProcessPoolExecutor`, dan mekanisme **Graceful Shutdown** terintegrasi berbasis penanganan sinyal OS.