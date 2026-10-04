# Bab 06 Module 01: Python Concurrency Architecture — GIL, Native Threading, dan Multiprocessing

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mendiagnosis dan mengukur dampak *Global Interpreter Lock* (GIL) CPython terhadap eksekusi paralel pada beban kerja *CPU-bound* vs *I/O-bound*.
- Merancang, mengimplementasikan, dan mengoptimalkan arsitektur *multithreading* yang aman (*thread-safe*) menggunakan primitif sinkronisasi tingkat rendah (`Lock`, `RLock`, `Semaphore`, `Condition`).
- Membangun *pipeline* komputasi paralel terisolasi berbasis *multiprocessing* dengan protokol *Inter-Process Communication* (IPC) berlatensi rendah (`Queue`, `Pipe`, `SharedMemory`).
- Menganalisis metrik performa (*throughput*, *context-switch latency*, alokasi memori) untuk menentukan trade-off antara *native threads*, *subprocesses*, dan coroutine.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, Anda wajib menguasai:
- **Python Memory Management**: Mekanisme *Reference Counting*, *Garbage Collection* (GC generasi 0, 1, 2), dan alokator `PyMalloc`.
- **Operating System Fundamentals**: Konsep proses, *thread*, *kernel space* vs *user space*, *preemptive scheduling*, *virtual memory*, dan *Copy-on-Write* (CoW).
- **Python Data Model**: Pemahaman mendalam tentang *mutable* vs *immutable objects*, closures, dan *context managers*.

---

### 3. Concept
Arsitektur konkurensi di CPython berpusat pada satu batasan fundamental: **Global Interpreter Lock (GIL)**. GIL adalah *mutual exclusion lock* (mutex) tingkat proses yang mencegah beberapa *native thread* mengeksekusi *bytecode* Python secara bersamaan di dalam satu proses CPython.

Secara internal pada CPython (khususnya implementasi `ceval.c`), interpreter mengalokasikan satu *thread state* (`PyThreadState`) untuk setiap *thread* sistem operasi (POSIX `pthreads` di Linux/macOS atau Windows native threads). Namun, untuk memanipulasi referensi memori internal tanpa menyebabkan korupsi data (*race condition* pada `ob_refcnt`), sebuah thread harus mengakuisisi GIL sebelum menjalankan evaluasi *bytecode* loop (`_PyEval_EvalFrameDefault`).

```text
CPython Bytecode Evaluation Loop:
  [Thread 1] -> Akuisisi GIL -> Eksekusi N Instruksi / Waktu Habis -> Rilis GIL
                                                                         ↓
  [Thread 2] <---------------- Akuisisi GIL <----------------------------+
```

CPython menggunakan mekanisme *interval-based GIL switching* (default: 5 milidetik, diatur via `sys.setswitchinterval`). Ketika interval tercapai, thread yang sedang berjalan diinstruksikan untuk melepaskan GIL, memberikan kesempatan pada thread lain yang sedang berstatus *suspended* untuk bersaing memperebutkannya. Akibatnya:
1. **Beban Kerja I/O-Bound**: GIL dilepaskan secara eksplisit oleh CPython sebelum memanggil fungsi C sistem operasi yang memblokir (seperti `read()`, `write()`, `connect()`, `select()`). Oleh karena itu, *multithreading* sangat efektif untuk konkurensi I/O.
2. **Beban Kerja CPU-Bound**: *Multithreading* tidak meningkatkan kecepatan pemrosesan pada CPU multi-core. Sebaliknya, biaya *context switching*, *cache invalidation*, dan kompetisi perebutan mutex antar-thread (*GIL contention*) justru memperlambat eksekusi dibandingkan implementasi *single-thread*.

Untuk mencapai konkurensi paralel murni (*true parallelism*) pada beban kerja CPU-bound, arsitektur harus dialihkan ke model **Multiprocessing**, di mana setiap proses memiliki *interpreter instance*, ruang memori virtual (*virtual address space*), dan instans GIL independen.

---

### 4. Why
Di lingkungan produksi skala besar, pemahaman konkurensi Python membedakan antara sistem yang *scalable* dan sistem yang mengalami kebuntuan performa:
- **Mencegah Masalah Skalabilitas Tersembunyi**: Menggunakan `threading` untuk pemrosesan citra (*image processing*), kriptografi, atau transformasi *data frame* besar akan memicu pemborosan utilisasi core CPU hingga 100% tanpa peningkatan *throughput*.
- **Keamanan Memori dan Konsistensi Data**: Operasi Python tingkat tinggi (seperti `a += 1` atau `dict[k] = v`) bukan merupakan operasi atomik di tingkat *bytecode*. Kegagalan memahami batas atomisitas menyebabkan korupsi data (*race conditions*) yang sulit dilacak.
- **Efisiensi Sumber Daya Cloud**: Memilih antara *multithreading* (memori bersama, overhead rendah) dan *multiprocessing* (memori terisolasi, overhead tinggi via serialisasi `pickle`) berdampak langsung pada tagihan komputasi server (RAM vs vCPU allocation).

---

### 5. What
Komponen kunci arsitektur konkurensi Python meliputi:

1. **`threading.Thread`**: Abstraksi tingkat tinggi di atas *native OS thread*. Berbagi *heap memory* yang sama dalam satu proses.
2. **Primitif Sinkronisasi Thread**:
   - `threading.Lock`: Primitif mutual exclusion paling dasar (non-reentrant).
   - `threading.RLock`: *Reentrant lock*, dapat diakuisisi berulang kali oleh thread pemilik yang sama tanpa memicu *deadlock*.
   - `threading.Semaphore`: Mengontrol akses ke sekumpulan sumber daya dengan kapasitas terbatas.
   - `threading.Condition`: Memungkinkan satu atau lebih thread menunggu hingga diberi notifikasi oleh thread lain bahwa suatu kondisi telah terpenuhi.
3. **`multiprocessing.Process`**: Instansiasi proses baru yang menduplikasi atau menginisialisasi ulang interpreter Python menggunakan metode *start* (`fork`, `spawn`, atau `forkserver`).
4. **Mekanisme IPC (Inter-Process Communication)**:
   - `multiprocessing.Queue`: Antrean FIFO berbasis pipe berkinerja tinggi yang aman secara multiproses (*thread- and process-safe*).
   - `multiprocessing.Pipe`: Kanal komunikasi dua arah (*duplex*) berkecepatan tinggi antar dua titik proses.
   - `multiprocessing.shared_memory.SharedMemory`: Alokasi blok memori bersama secara langsung tanpa biaya *marshalling/serialization* (`pickle`).
5. **`concurrent.futures.Executor`**: API seragam tingkat tinggi (`ThreadPoolExecutor` dan `ProcessPoolExecutor`) untuk mengelola siklus hidup *worker pool* dan abstraksi hasil asinkron (`Future`).

---

### 6. How
Alur kerja internal manajemen *thread* dan *process* berlangsung melalui fase berikut:

#### Siklus Hidup Eksekusi Thread (CPython GIL Management)
1. Thread utama menginisialisasi `threading.Thread(target=fn)` dan memanggil `.start()`.
2. Interpreter memanggil `pthread_create` di level OS kernel.
3. Thread baru membuat struktur internal `PyThreadState`.
4. Thread masuk ke status *runnable*, mencoba mengakuisisi GIL via fungsi C `take_gil()`.
5. Thread memproses *bytecode* hingga:
   - Selesai.
   - Batas waktu `switchinterval` habis (sinyal rilis `drop_gil()` diaktifkan).
   - Menjalankan syscall I/O (eksplisit memanggil `Py_BEGIN_ALLOW_THREADS` dan melepas GIL).
6. GIL dilepas (`drop_gil()`), OS menjadwalkan thread lain yang siap jalan.

#### Siklus Hidup Eksekusi Multiprocessing
1. Proses induk (*parent*) mendefinisikan *worker function* dan menginstansiasi `multiprocessing.Process`.
2. Sistem mengeksekusi metode start:
   - **`spawn`** (Default di Windows & macOS): Proses baru diluncurkan dari nol, Python baru dieksekusi, hanya modul esensial yang dimuat ulang.
   - **`fork`** (Legacy di Unix): Proses menduplikasi memori induk via *Copy-on-Write*. Cepat, tetapi rentan *deadlock* jika parent memiliki thread aktif saat forking.
3. Argumen fungsi diserialisasi ke dalam *byte stream* via modul `pickle`.
4. Komunikasi dilakukan melalui file descriptor (Pipes) atau segmen POSIX Shared Memory.
5. Proses anak mengembalikan hasil, diserialisasi ulang, lalu ditangkap oleh proses induk.

---

### 7. Analogy
Bayangkan sebuah **Dapur Restoran Terpusat**:
- **Proses Single-Thread**: Satu koki bekerja di satu meja dapur. Dia memotong sayur (CPU) dan menunggu oven matang (I/O).
- **Multithreading dengan GIL**: Dapur memiliki 4 koki (*Native Threads*), namun mereka harus berbagi **satu set pisau koki master** (GIL). Hanya satu koki yang dapat memotong bahan pada satu waktu. Ketika koki 1 memasukkan loyang ke oven (I/O syscall), dia menyerahkan pisau ke koki 2. Namun jika semua koki harus memotong daging secara konstan (CPU-bound), pisau terus berpindah tangan secara repetitif; mereka tidak memotong lebih cepat, justru membuang tenaga merebutkan pisau.
- **Multiprocessing**: Restoran membuka **4 dapur terpisah secara fisik**. Masing-masing dapur memiliki koki sendiri dan pisau sendiri secara independen. Mereka dapat memotong daging secara bersamaan pada waktu yang sama persis tanpa gangguan. Namun, jika Dapur 1 ingin mengirim bahan ke Dapur 2, mereka harus mengepak bahan tersebut ke dalam kardus, menyegelnya, memuatnya ke truk, dan mengirimkannya (overhead *pickle* dan IPC).

---

### 8. Diagram

```text
=============================================================================
                MODEL ARSITEKTUR MEMORI: THREADING VS MULTIPROCESSING
=============================================================================

 MODEL A: MULTITHREADING (Single Process, Single GIL)
 +-------------------------------------------------------------------------+
 | Operating System Virtual Memory Space (Process ID: 1042)                |
 |                                                                         |
 |  Heap Memory: Global Variables, Object Allocations, Loaded Modules     |
 |  [ Shared Data: {'metric_counter': 42} ]                               |
 |                                                                         |
 |   +-----------------------------------------------------------------+   |
 |   | CPython Runtime Instance                                        |   |
 |   |                     [ GLOBAL INTERPRETER LOCK ]                 |   |
 |   |                                  |                              |   |
 |   |          +-----------------------+-----------------------+      |   |
 |   |          | Holds Mutex                                   | Wait |   |
 |   |          v                                               v      |   |
 |   |   +---------------+                             +---------------+   |
 |   |   | Thread-1      |                             | Thread-2      |   |
 |   |   | (PyThreadState)                             | (PyThreadState)   |
 |   |   +-------+-------+                             +-------+-------+   |
 |   +-----------|---------------------------------------------|-----------+
 |               v                                             v           |
 |       +---------------+                             +---------------+   |
 |       | Stack Space 1 |                             | Stack Space 2 |   |
 +-------+---------------+-----------------------------+---------------+---+
                 |                                             |
 OS Scheduler    v                                             v
 Kernel:      [Core 0]                                      [Core 1] (Idle/Wait)

-----------------------------------------------------------------------------

 MODEL B: MULTIPROCESSING (Isolated Processes, Isolated GILs)
 +-----------------------------------+     +-----------------------------------+
 | Process 1 (PID: 2001)             |     | Process 2 (PID: 2002)             |
 | Virtual Address Space A           |     | Virtual Address Space B           |
 |                                   |     |                                   |
 | Heap: [Data Copy A]               |     | Heap: [Data Copy B]               |
 | Runtime: [GIL 1]                  |     | Runtime: [GIL 2]                  |
 | Thread:  [MainThread 1]           |     | Thread:  [MainThread 2]           |
 +-----------------+-----------------+     +-----------------+-----------------+
                   |                                         |
                   |       IPC: SharedMemory / Pipe / Queue  |
                   +==================[ OS IPC ]=============+
                   |                                         |
 OS Scheduler:     v                                         v
                [Core 0]                                  [Core 1]
               (Running)                                 (Running)
=============================================================================
```

---

### 9. Simple Example
Contoh berikut mendemonstrasikan bahwa operasi aritmetika in-place (`counter += 1`) bukan operasi atomik, sehingga memerlukan `Lock` untuk menghindari kondisi *race condition*.

```python
import threading
import time

class UnsafeCounter:
    def __init__(self) -> None:
        self.value: int = 0

    def increment(self) -> None:
        # Non-atomic: Membaca self.value, menambah 1, lalu menyimpan kembali.
        current = self.value
        time.sleep(0.00001)  # Memaksa OS context-switch / GIL release
        self.value = current + 1

class ThreadSafeCounter:
    def __init__(self) -> None:
        self.value: int = 0
        self._lock: threading.Lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:
            current = self.value
            time.sleep(0.00001)
            self.value = current + 1

def run_worker(counter_obj: UnsafeCounter | ThreadSafeCounter, iterations: int) -> None:
    for _ in range(iterations):
        counter_obj.increment()

if __name__ == "__main__":
    ITERATIONS = 50
    THREADS_COUNT = 4
    EXPECTED_TOTAL = ITERATIONS * THREADS_COUNT

    # 1. Jalankan Counter Tidak Aman
    unsafe = UnsafeCounter()
    threads = [threading.Thread(target=run_worker, args=(unsafe, ITERATIONS)) for _ in range(THREADS_COUNT)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"[UNSAFE] Expected: {EXPECTED_TOTAL}, Actual: {unsafe.value}")

    # 2. Jalankan Counter Aman
    safe = ThreadSafeCounter()
    threads = [threading.Thread(target=run_worker, args=(safe, ITERATIONS)) for _ in range(THREADS_COUNT)]
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"[SAFE]   Expected: {EXPECTED_TOTAL}, Actual: {safe.value}")
```

---

### 10. Practical Example
Sistem pemrosesan log telemetri streaming dengan *Producer-Consumer Architecture* yang menggunakan `multiprocessing` untuk parsing intensif CPU, dikombinasikan dengan pembagian tugas melalui antrean terproteksi dan *graceful shutdown*.

```python
from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
from dataclasses import dataclass
from queue import Empty
import sys
import time
from typing import Final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(processName)s) %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)

_SENTINEL: Final[None] = None

@dataclass(frozen=True, slots=True)
class TelemetryRecord:
    device_id: str
    timestamp: float
    payload: str

@dataclass(frozen=True, slots=True)
class ProcessedResult:
    device_id: str
    signature: str
    processed_by: str

def cpu_intensive_hasher(payload: str) -> str:
    """Simulasi pemrosesan kriptografi berat (CPU-bound)."""
    current_hash = payload.encode("utf-8")
    for _ in range(25_000):
        current_hash = hashlib.sha256(current_hash).digest()
    return current_hash.hex()

def worker_process(
    task_queue: mp.Queue[TelemetryRecord | None],
    result_queue: mp.Queue[ProcessedResult | None],
    worker_id: int
) -> None:
    """Proses worker terisolasi untuk eksekusi paralel independen."""
    name = f"ComputeWorker-{worker_id}"
    logging.info(f"Worker {name} berhasil dialokasikan.")
    
    while True:
        try:
            record = task_queue.get(timeout=2.0)
        except Empty:
            continue
        except Exception as err:
            logging.error(f"Kesalahan pembacaan antrean: {err}")
            break

        if record is _SENTINEL:
            logging.info(f"Menerima shutdown sentinel. Menghentikan {name}...")
            break

        try:
            signature = cpu_intensive_hasher(record.payload)
            result = ProcessedResult(
                device_id=record.device_id,
                signature=signature,
                processed_by=name
            )
            result_queue.put(result)
        except Exception as err:
            logging.error(f"Gagal memproses record {record.device_id}: {err}")

class TelemetryEngine:
    def __init__(self, num_workers: int = 4) -> None:
        self.num_workers: int = num_workers
        self.task_queue: mp.Queue[TelemetryRecord | None] = mp.Queue(maxsize=1000)
        self.result_queue: mp.Queue[ProcessedResult | None] = mp.Queue()
        self.workers: list[mp.Process] = []

    def start(self) -> None:
        for i in range(self.num_workers):
            proc = mp.Process(
                target=worker_process,
                args=(self.task_queue, self.result_queue, i),
                name=f"WorkerProc-{i}",
                daemon=True
            )
            proc.start()
            self.workers.append(proc)

    def ingest(self, records: list[TelemetryRecord]) -> None:
        for rec in records:
            self.task_queue.put(rec)

    def shutdown(self) -> list[ProcessedResult]:
        logging.info("Memulai koordinasi penghentian teratur (Graceful Shutdown)...")
        # Mengirim racun (poison pill) sentinel ke setiap worker
        for _ in range(self.num_workers):
            self.task_queue.put(_SENTINEL)

        for proc in self.workers:
            proc.join(timeout=5.0)
            if proc.is_alive():
                logging.warning(f"Worker {proc.name} macet. Mematikan paksa (terminate).")
                proc.terminate()

        # Ekstraksi hasil akhir
        collected_results: list[ProcessedResult] = []
        while not self.result_queue.empty():
            collected_results.append(self.result_queue.get_nowait())

        logging.info(f"Shutdown tuntas. Total data terproses: {len(collected_results)}")
        return collected_results

if __name__ == "__main__":
    # Menegakkan metode start eksplisit demi konsistensi lintas platform
    mp.set_start_method("spawn", force=True)

    engine = TelemetryEngine(num_workers=4)
    engine.start()

    sample_dataset = [
        TelemetryRecord(
            device_id=f"IOT-SENSOR-NODE-{idx:04d}",
            timestamp=time.time(),
            payload=json.dumps({"voltage": 3.3 + (idx * 0.01), "status": "NOMINAL"})
        )
        for idx in range(20)
    ]

    t_start = time.perf_counter()
    engine.ingest(sample_dataset)
    results = engine.shutdown()
    t_total = time.perf_counter() - t_start

    print(f"\nEksekusi Selesai dalam {t_total:.3f}s. Sampel hasil:")
    for res in results[:3]:
        print(f" -> ID: {res.device_id} | Signature: {res.signature[:16]}... | Processor: {res.processed_by}")
```

---

### 11. Real World Example
**Skenario**: Sistem Verifikasi & Rekonsiliasi Transaksi Finansial Real-time (Fintech Payment Gateway).

Sebuah gateway pembayaran skala enterprise memproses 150.000 transaksi/menit. Setiap transaksi melewati dua tahap:
1. **Validasi Tanda Tangan Enkripsi & Anti-Fraud** (Intensif CPU, membutuhkan 20ms komputasi murni per transaksi).
2. **Pengecekan Saldo Core Banking via REST/gRPC** (Intensif I/O Jaringan, latensi 60ms).

#### Solusi Arsitektur
Arsitektur hibrida diterapkan untuk memisahkan beban kerja berdasarkan karakteristik operasinya:
- **I/O Network Workers (`ThreadPoolExecutor`)**: 64 thread menangani panggilan HTTP/gRPC keluar tanpa terhalang GIL karena socket I/O melepaskan GIL.
- **CPU Cryptographic Engine (`ProcessPoolExecutor`)**: Memanfaatkan N-Core CPU server secara penuh via proses terisolasi untuk hashing SHA-256 dan verifikasi kunci asimetris.

```text
[HTTP Webhook Payload]
         │
         ▼
[IO ThreadPoolExecutor]  ──(Release GIL pada I/O)──> [Call Banking API Services]
         │
         ▼ (Data Diterima)
[ProcessPoolExecutor]    ──(Multi-Core True Parallelism)──> [CPU Hashing / Fraud Calculation]
         │
         ▼
[Storage Ingestion (DB)]
```

Dampak Implementasi di Produksi:
- Penggunaan `Threading` murni untuk CPU Hashing menghasilkan latensi P99 sebesar **2.800 ms** (karena GIL starvation).
- Refaktor ke `ProcessPoolExecutor` dengan alokasi 8 proses pekerja menurunkan latensi P99 menjadi **115 ms**, meningkatkan *throughput* validasi hingga 650%.

---

### 12. Trade-offs

| Dimensi | Single-Threaded Event Loop (`asyncio`) | Multi-Threading (`threading`) | Multi-Processing (`multiprocessing`) |
| :--- | :--- | :--- | :--- |
| **Model Memori** | Single Heap Memory | Shared Heap Memory | Isolated Virtual Address Spaces |
| **GIL Contention** | Nihil (Single thread) | Sangat Tinggi pada CPU-bound | Tidak Ada (Independen GIL) |
| **Overhead Memori** | Sangat Rendah (~KB per task) | Rendah (~8MB default thread stack) | Tinggi (Duplikasi CPython runtime / CoW) |
| **IPC & Data Transfer** | Pointer dereference langsung | Pointer dereference langsung | Overhead Serialisasi (`pickle`) / IPC |
| **Debugging Complexity** | Menengah (Stack trace async) | Sangat Tinggi (Deadlock, Race Condition) | Tinggi (Manajemen Zombie, Broken Pipes) |
| **Kesesuaian Beban Kerja** | Web API, I/O Jaringan Tinggi | I/O Disk, Akses DB Lawas, C-Extensions | Komputasi Numerik, Kriptografi, ML/AI |

---

### 13. When To Use
Gunakan pendekatan terarah berdasarkan karakteristik beban:
- **Pilih `multithreading` ketika:**
  1. Melakukan operasi I/O-bound (baca/tulis disk, network socket, kueri database) di mana GIL dilepaskan secara internal oleh CPython atau driver eksternal C.
  2. Berinteraksi dengan library native C/C++ (seperti NumPy, OpenCV, Polars) yang mengeksekusi komputasi numerik di luar GIL menggunakan `Py_BEGIN_ALLOW_THREADS`.
  3. Aplikasi memerlukan akses baca-tulis berlatensi rendah ke struktur data dalam memori yang sama tanpa overhead serialisasi data.

- **Pilih `multiprocessing` ketika:**
  1. Melakukan komputasi CPU-bound murni (kompresi berkas, enkripsi/dekripsi, parsing dokumen JSON/XML masif, pemrosesan citra).
  2. Menginginkan isolasi kesalahan (*fault isolation*): jika satu proses *crash* karena pelanggaran segmentasi (*segmentation fault*), proses induk dan pekerja lainnya tetap berjalan.
  3. Menargetkan pemanfaatan 100% dari seluruh core CPU yang tersedia di server.

---

### 14. When NOT To Use
- **JANGAN gunakan `threading` untuk:**
  - Pemrosesan data komputasi intensif murni di Python. *GIL contention* akan menyebabkan fenomena *convoy effect*, di mana performa justru anjlok lebih lambat daripada eksekusi berurutan (*sequential*).
  - Sistem yang menuntut skalabilitas I/O ultra-tinggi (misalnya >10.000 koneksi bersamaan). Pada skala ini, alokasi *thread stack* OS akan menghabiskan RAM; gunakan `asyncio` sebagai alternatif.

- **JANGAN gunakan `multiprocessing` untuk:**
  - Mengirim objek Python kompleks berukuran gigabyte antar-proses secara intensif, kecuali menggunakan `SharedMemory`. Biaya *serialization* (`pickle.dumps`) dan deserialisasi (`pickle.loads`) melalui pipes akan mendominasi dan mengeliminasi keuntungan performa paralelisme.
  - Lingkungan komputasi mikro dengan kapasitas RAM terbatas (seperti container 256MB atau perangkat IoT), karena instansiasi beberapa proses CPython dapat memicu *Out-Of-Memory* (OOM) killer.

---

### 15. Common Mistakes
1. **Deadlock Akibat Urutan Penguncian yang Inkonsisten (*Lock Ordering Problem*)**:
   ```python
   # SALAH: Memicu circular wait
   # Thread A                   # Thread B
   with lock_1:                 with lock_2:
       with lock_2:                 with lock_1:
           pass                         pass
   ```
   *Solusi*: Tetapkan hierarki akuisisi lock global secara seragam atau gunakan mekanisme `threading.Lock` dengan timeout.

2. **Penggunaan Start Method `fork` di Lingkungan Multithreaded**:
   Memanggil `multiprocessing.set_start_method("fork")` saat proses induk sudah menjalankan background thread dapat menyebabkan proses anak mengalami *deadlock* instan jika thread induk memegang lock tepat saat sistem mengeksekusi syscall `fork()`.
   *Solusi*: Gunakan selalu start method `"spawn"` atau `"forkserver"` pada arsitektur modern.

3. **Lupa Memberikan Batas Antrean (*Unbounded Queues*)**:
   Menggunakan `multiprocessing.Queue()` tanpa menentukan parameter `maxsize` pada produser yang lebih cepat daripada konsumen akan menyebabkan antrean menampung objek tanpa batas hingga kehabisan RAM.

4. **Mengabaikan Proteksi `if __name__ == '__main__':`**:
   Pada sistem operasi berbasis `spawn` (Windows & macOS modern), kode luar fungsi yang tidak dilindungi blok guard ini akan dieksekusi ulang secara tak terbatas oleh setiap proses anak yang baru dibentuk (*fork bomb accident*).

---

### 16. Best Practices (Production Checklist)
- [ ] Tentukan secara tegas karakteristik beban kerja: **I/O-Bound** (gunakan threads/async) atau **CPU-Bound** (gunakan processes).
- [ ] Selalu bungkus eksekusi `Lock` di dalam *context manager* (`with lock:`) guna menjamin pelepasan lock meskipun terjadi unhandled exception.
- [ ] Inisialisasi pool menggunakan `concurrent.futures.ProcessPoolExecutor` atau `ThreadPoolExecutor` di dalam blok `with` untuk menjamin terminasi thread/proses pekerja.
- [ ] Batasi jumlah worker proses maksimum tidak melebihi kapasitas core CPU riil: `os.cpu_count()` (atau alokasikan `os.cpu_count() - 1` agar menyisakan resource bagi OS scheduler).
- [ ] Hindari dependensi status global (*global state mutation*); prioritaskan fungsi murni (*pure functions*) yang menerima input terdefinisi dan mengembalikan output terisolasi.
- [ ] Konfigurasikan penanganan sinyal terminasi (`SIGTERM`, `SIGINT`) untuk membersihkan *shared memory* dan menghentikan worker secara terkontrol tanpa meninggalkan *zombie process*.

---

### 17. Troubleshooting
- **Gejala: Utilisasi CPU stuck di 100% pada 1 core saja, padahal script dijalankan dengan 16 threads.**
  - *Akar Masalah*: Beban kerja CPU-bound terikat oleh CPython GIL.
  - *Diagnostik*: Jalankan profiler seperti `py-spy` menggunakan flag `--gil` (`py-spy record --gil -p <PID>`) untuk mengamati persentase *GIL acquisition contention*.
  - *Solusi*: Migrasikan kode dari `threading.Thread` ke `multiprocessing.Pool` atau refaktor algoritma ke ekstensi native C/Cython/Rust yang melepas GIL.

- **Gejala: `RuntimeError: Resource temporarily unavailable` atau `OSError: Cannot allocate memory`.**
  - *Akar Masalah*: Pembuatan native thread atau subproses melampaui limit OS kernel (`max user processes` atau `sys.vm.max_map_count`).
  - *Diagnostik*: Periksa batasan sistem operasi via terminal: `ulimit -u` dan `sysctl vm.max_map_count`.
  - *Solusi*: Batasi jumlah thread/worker melalui pola *Worker Pool* tetap (*bounded pool size*), jangan membuat thread ad-hoc per request.

- **Gejala: Aplikasi multiprocessing hang tanpa log error saat transfer data besar.**
  - *Akar Masalah*: Deadlock internal pada `multiprocessing.Queue` karena buffer pipa OS (OS pipe buffer) penuh sebelum proses induk memanggil `join()`.
  - *Solusi*: Konsumsi seluruh data antrean hingga kosong sebelum memanggil `proc.join()`, atau gunakan `SharedMemory` untuk muatan data bervolume gigabyte.

---

### 18. Exercise
Implementasikan kelas **`BoundedParallelWorkerPool`** yang memenuhi kriteria berikut:
1. Menggunakan `multiprocessing` untuk menjalankan N-pekerja paralel.
2. Menerima kumpulan angka acak (list of integers).
3. Setiap pekerja menghitung apakah bilangan tersebut merupakan bilangan prima (*primality test*) menggunakan algoritma deterministik.
4. Menerapkan mekanisme pelaporan progres secara thread-safe ke konsol setiap kali sebuah batch selesai diproses.
5. Menangani interupsi keyboard (`Ctrl+C`) secara anggun tanpa menampilkan jejak exception *broken pipe* yang kotor.

---

### 19. Challenge
Rancang dan bangun sistem **In-Memory Zero-Copy Matrix Computation Pipeline**:
- **Spesifikasi Teknis**:
  1. Proses Induk membuat dua matriks numerik berukuran $5.000 \times 5.000$ bertipe *double precision float* (`float64`).
  2. Data dialokasikan langsung ke dalam segmen `multiprocessing.shared_memory.SharedMemory` dan dipetakan ke dalam array `numpy` melalui buffer mentah (tanpa serialisasi `pickle` dan tanpa duplikasi alokasi RAM).
  3. Buat 4 proses worker independen yang masing-masing mengambil kuadran matriks yang berbeda ($2.500 \times 2.500$), lalu mengeksekusi operasi transformasi matematis intensif (misal: normalisasi matriks dan perkalian parsial).
  4. Seluruh sinkronisasi batas eksekusi (*synchronization barrier*) harus diatur menggunakan `multiprocessing.Barrier`.
  5. Pastikan memori bersama dibebaskan (`unlink()`) secara deterministik di blok `finally` proses induk, bahkan jika worker mengalami kegagalan fatal.

---

### 20. Summary
- **CPython GIL** dirancang untuk menjamin keamanan *thread-safety* internal pada sistem alokasi memori dan penghitungan referensi (`refcounting`), namun membatasi eksekusi paralel murni hanya pada 1 thread aktif per waktu untuk *bytecode* Python.
- **Multithreading** ideal untuk konkurensi **I/O-bound** dan pemanggilan pustaka C tingkat rendah, karena *thread* berbagi ruang memori secara langsung dan sistem operasi dapat mengalihkan eksekusi saat operasi I/O memblokir.
- **Multiprocessing** menghindari batasan GIL dengan cara memisahkan proses dan interpreter CPython secara utuh pada tiap *core* CPU. Model ini krusial untuk komputasi **CPU-bound**, namun menghasilkan konsekuensi berupa biaya alokasi memori yang lebih besar dan latensi komunikasi antar-proses (IPC).
- Untuk menghasilkan kode produksi yang stabil, insinyur perangkat lunak harus mendesain arsitektur konkurensi dengan mempertimbangkan batas-batas primitif sinkronisasi, membersihkan *resource* secara teratur, serta memilih metode eksekusi sistem operasi (`spawn` vs `fork`) yang tepat guna menghindari kondisi kebuntuan (*deadlock*).