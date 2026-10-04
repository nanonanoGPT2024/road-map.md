# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Concurrency, Parallelism, GIL, Threads & Multiprocessing**  
**Kategori: 02-Programming-Languages / python**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Mekanisme CPython GIL Tingkat Rendah**: Membedah siklus hidup `PyThreadState`, interaksi POSIX threads (`pthreads`) terhadap *GIL release/acquisition cycle*, mekanisme evaluasi loop bytecode di `_PyEval_EvalFrameDefault`, serta implikasi interval context-switching (`sys.setswitchinterval`).
2. **Merancang Sinkronisasi Thread Non-Trivial**: Mengimplementasikan primitif sinkronisasi multithreading tingkat lanjut (`Condition`, `Barrier`, `Semaphore`, `RLock`) untuk mengeliminasi kondisi balapan (*race conditions*), *deadlock*, dan *thread starvation* pada arsitektur I/O terdistribusi.
3. **Menguasai Multiprocessing Berkinerja Tinggi**: Membangun sistem *zero-copy memory sharing* menggunakan `multiprocessing.shared_memory.SharedMemory` dan `memoryview`, memitigasi overhead serialisasi `pickle`, serta mengelola siklus hidup proses (`spawn`, `fork`, `forkserver`) untuk stabilitas OS tingkat kernel.
4. **Membangun Pipeline Hybrid (Process-Thread Pool)**: Merancang subsistem pemrosesan batch/stream enterprise yang menggabungkan *multiprocessing* untuk komputasi CPU-bound dan *multithreading* untuk throughput I/O bound dengan kontrol *backpressure* adaptif.
5. **Mendiagnosis Kegagalan Konkurensi Produksi**: Melakukan audit performa konkurensi menggunakan *profiler* tingkat rendah, mengidentifikasi kebocoran memori pada shared memory, serta mengatasi *priority inversion* dan *zombie processes*.

---

## 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib memahami:
* **Arsitektur Sistem Operasi**: Virtual memory, page translation, context switching, memory mapping (`mmap`), POSIX signals (`SIGCHLD`, `SIGTERM`), dan system calls (`fork`, `clone`, `futex`).
* **Python Fondasi & Bab 06 Modul 01**: Dasar-dasar `threading.Thread`, `multiprocessing.Process`, pemahaman high-level GIL, I/O-bound vs CPU-bound tasks.
* **Memori & Pointer**: Representasi data biner, serialisasi data (`struct`, `pickle`), buffer protocol Python, dan garbage collection reference counting (`PyObject`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 CPython GIL Internals: POSIX Futex, Mutex, dan Evaluasi Bytecode

Global Interpreter Lock (GIL) bukan sekadar sakelar *boolean* di tingkat Python; GIL di CPython diimplementasikan sebagai kombinasi *mutex* dan *condition variable* sistem operasi (pada POSIX, ini dibungkus di atas primitive `pthread_mutex_t` dan `pthread_cond_t`).

```
           +-------------------------------------------------------+
           |                CPython Runtime Engine                 |
           +-------------------------------------------------------+
                                      |
                 Bytecode Execution Loop (_PyEval_EvalFrameDefault)
                                      |
         +----------------------------+----------------------------+
         |                                                         |
 [Thread A Running]                                        [Thread B Suspended]
   - Memegang GIL                                            - Menunggu gil_cond
   - Mengeksekusi opcodes                                    - Status: Blocked
   - gil_drop_request = 0                                    - Menghitung interval switch
         |                                                         |
         v                                                         v
   Tercapai Switch Interval ---------------------------> Mengirimkan drop request
   (Default: 5ms)                                         gil_drop_request = 1
         |                                                         |
         v                                                         |
   Thread A mendeteksi drop request                                |
   - Menyimpan thread context                                      |
   - Release GIL (pthread_mutex_unlock)                            |
   - Signal gil_cond (pthread_cond_signal) ------------------------+
   - Thread A istirahat (wait gil_cond)                            |
                                                                   v
                                                            Thread B bangun:
                                                            - Re-acquire GIL
                                                            - Running bytecode
```

Secara internal pada `ceval_gil.h` dan `ceval.c`:
* Struktur data `struct _gil_runtime_state` mengelola pointer `locked` (atomic integer), `switch_interval` (default 5000 mikrodetik), dan conditional variable `gil_cond` serta `switch_cond`.
* Ketika Thread A berjalan, ia mengeksekusi bytecode di `_PyEval_EvalFrameDefault()`. Thread B yang ingin berjalan akan tidur di `pthread_cond_timedwait` selama `switch_interval`.
* Jika interval tercapai dan Thread A belum melepaskan GIL secara sukarela (misalnya melalui operasi I/O native atau pemanggilan C extension), Thread B menaikkan flag atomik `gil_drop_request = 1`.
* Thread A memeriksa flag ini secara berkala pada batas evaluasi opcode. Jika aktif, Thread A melepaskan GIL, menembakkan signal ke Thread B, dan menangguhkan dirinya sendiri sampai Thread B selesai atau melepaskan giliran.

#### Konsekuensi Multi-Core CPU: "Convoy Effect"
Pada mesin *multi-core*, mekanisme ini memicu **Convoy Effect**. Thread CPU-bound akan terus berebut GIL dengan Thread I/O-bound. Ketika Thread I/O selesai menunggu socket data dan siap berjalan, ia harus mengantre di kernel scheduler, sementara Thread CPU-bound terus memicu perebutan kembali GIL segera setelah melepaskannya. Ini menyebabkan latensi degradatif pada aplikasi multithreaded murni yang mencampur aduk beban kerja.

### 3.2 Threading Synchronization Primitives: Deep Dive

Untuk mencegah balapan data pada modifikasi state non-atomik di luar kontrol GIL (misalnya: operasi multi-langkah seperti *check-then-act*):

* **`threading.Lock` vs `threading.RLock`**: `Lock` berbasis C-level synchronization primitive (`PyThread_type_lock`). `RLock` (Reentrant Lock) menambahkan pencatatan *thread ownership* (`owner_id`) dan *recursion level counter*. Sebuah thread dapat mengakuisisi `RLock` berkali-kali tanpa *self-deadlock*, namun pelepasan (`release()`) harus simetris dengan jumlah akuisisi.
* **`threading.Condition`**: Mengasosiasikan `Lock` internal dengan antrean tunggu. Mengizinkan thread untuk tidur (*sleep*) hingga kondisi logis dunia nyata terpenuhi (`wait()`), dan thread lain mengubah state serta membangunkan satu (`notify()`) atau semua worker (`notify_all()`). Sangat krusial untuk implementasi Producer-Consumer terkelola.
* **`threading.Barrier`**: Primitif sinkronisasi siklis yang memblokir sejumlah fixed thread hingga seluruh thread mencapai barrier point (`wait()`). Barrier mencegah eksekusi berlanjut ke fase berikutnya sebelum semua subtask independen rampung.

### 3.3 Multiprocessing: Process Creation Semantics & Memory Isolation

Python menyediakan tiga konteks start process via OS:
1. **`fork` (Legacy POSIX default, rentan unsafe di threaded code)**:
   * Mengkloning *address space* induk secara *Copy-on-Write* (CoW).
   * **Bahaya fatal**: State thread lain pada proses induk **tidak** dikloning. Jika ada thread lain yang sedang memegang lock allocator internal CPython pada saat `fork()` dipanggil, lock tersebut akan terkunci selamanya (*deadlocked*) di dalam memori proses anak.
2. **`spawn` (Default Windows & macOS, opsional di Linux)**:
   * Menginstansiasi proses baru yang bersih dari interpreter biner `python`.
   * Membaca ulang module script, menginisialisasi runtime baru. Tidak ada state memori kotor dari proses induk yang terbawa.
   * Kekurangan: Startup time lebih lambat dan semua parameter harus dapat di-pickle (`pickle.dumps`).
3. **`forkserver` (Rekomendasi Linux Enterprise)**:
   * Proses server single-threaded yang murni di-*spawn* di awal.
   * Setiap proses worker baru dihasilkan dari *forking* server bersih ini, memitigasi bahaya deadlock multithreaded sambil mempertahankan kecepatan instansiasi yang tinggi.

### 3.4 Shared Memory & Zero-Copy IPC

Alih-alih mentransfer state besar antarproses melalui serialization `pickle` di atas UNIX Domain Socket atau OS Pipe (`multiprocessing.Queue`) yang memakan biaya alokasi memori berlipat ganda, modul `multiprocessing.shared_memory` (diperkenalkan sejak Python 3.8) memanfaatkan system call POSIX `shm_open` dan `mmap`.

```
                    Process Master (Owner)
              +--------------------------------+
              | - Buat SharedMemory segment   |
              | - Tulis data array / struct    |
              +---------------+----------------+
                              |
               POSIX Shared Memory: /dev/shm/*
              +--------------------------------+
              | Raw Binary Block (Kernel Ring) |
              +--------------------------------+
               ^              ^               ^
               |              |               |
        Attach (mmap)   Attach (mmap)   Attach (mmap)
               |              |               |
      +--------+-----+ +------+------+ +------+--------+
      | Worker 1     | | Worker 2    | | Worker N      |
      | memoryview   | | memoryview  | | memoryview    |
      | zero-copy    | | zero-copy   | | zero-copy     |
      +--------------+ +-------------+ +---------------+
```

Proses master mengalokasikan segment memori di `/dev/shm` (RAM-backed filesystem), kemudian proses-proses worker me-mount segment biner yang sama secara langsung ke *virtual address space* masing-masing. Melalui Python `memoryview` atau library seperti `numpy`, pembacaan dan mutasi in-place terjadi pada level native pointer tanpa ada satupun byte yang di-*copy* atau di-*pickle*.

---

## 4. Why & What

| Dimensi | Multithreading (Native Python) | Multiprocessing (Standard IPC / Queue) | Multiprocessing (Zero-Copy Shared Memory) |
| :--- | :--- | :--- | :--- |
| **GIL Bound** | Ya (Satu core CPU aktif per waktu runtime) | Tidak (Bebas GIL, multi-core sejati) | Tidak (Bebas GIL, multi-core sejati) |
| **Memory Footprint**| Sangat Rendah (Shared address space) | Sangat Tinggi (Isolasi memori total, CoW fragmentation) | Efisien (Isolasi memori terpisah, heap biner dibagi) |
| **Biaya Komunikasi**| Sangat Rendah (Pointer sharing, perhatikan lock) | Tinggi (Overhead serialisasi OS Pipe / Socket) | Hampir Nol (Akses memoryview native) |
| **Kematangan Fault**| Buruk (Segfault di 1 thread membunuh process) | Sangat Baik (Crash worker terisolasi) | Baik (Data korup jika atomic mutasi gagal) |
| **Beban Penggunaan**| I/O Bound (HTTP clients, DB queries, Web scrap) | CPU-bound diskrit, parsing JSON massal | Pemrosesan citra, inferensi ML, matrix data besar |

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Menggunakan `multiprocessing.Queue` untuk mentransfer matriks floating-point 500MB di antara 8 worker akan memicu serialisasi objek 500MB ke bytes, transfer via socket OS (beban kernel context-switch), dan rekonstruksi objek di sisi anak. Total memori yang terbakar seketika bisa mencapai `500MB * 3 = 1.5GB` per transmisi worker, memicu OOM (*Out Of Memory*) killer pada infrastruktur container (seperti Kubernetes pods).

---

## 5. How (Workflow detail)

Implementasi arsitektur produksi pipeline hybrid multi-proses dan multi-thread mengikuti alur berikut:

```
[ Ingest Stream / Payload File ]
             |
             v
 [ 1. Master Initializer ] 
     |---> Buat SharedMemory segment (/dev/shm/app_mem_*)
     |---> Inisialisasi memoryview wrapper
             |
             +----------------------------+
             |                            |
             v                            v
 [ Worker Process 1 (CPU Pool) ]  [ Worker Process 2 (CPU Pool) ]
     |---> Mount SharedMemory          |---> Mount SharedMemory
     |---> Buat ThreadPool (I/O)       |---> Buat ThreadPool (I/O)
             |                                 |
             +---------------+                 +---------------+
             |               |                 |               |
             v               v                 v               v
       Thread A (Fetch) Thread B (Push)  Thread A (Fetch) Thread B (Push)
             |               |                 |               |
             +-------+-------+                 +-------+-------+
                     |                                 |
                     +----------------+----------------+
                                      |
                                      v
                        [ 3. POSIX Sync Primitive ]
                        (Condition / Semaphore via Lock)
                                      |
                                      v
                         [ 4. Clean Unlink & Exit ]
```

1. **Inisialisasi Master**: Master process mendeklarasikan memori terdistribusi via POSIX Shared Memory dan mendaftarkan signal handler (`SIGTERM`, `SIGINT`) untuk *fail-safe resource cleanup*.
2. **Kloning Proses Aman**: Sub-proses di-*spawn* menggunakan context `spawn` atau `forkserver` untuk menjamin tidak ada residu lock runtime CPython.
3. **Pemberian Task Melalui Offsets**: Master tidak mengirimkan data mentah via IPC queue, melainkan hanya mengirimkan metadata primitif: `(offset_start, offset_end, shape, dtype)` melalui lightweight IPC queue.
4. **Thread-level I/O Concurrency**: Masing-masing sub-proses memanfaatkan `ThreadPoolExecutor` lokal untuk mengeksekusi panggilan eksternal (misal: push ke Object Storage atau cache Redis) tanpa menghalangi komputasi proses worker lain.
5. **Deterministic Tear Down**: Melalui context management atau blok `finally:`, shared memory di-*close* di semua worker, dan di-*unlink* secara eksklusif oleh master process.

---

## 6. Analogy & Diagram ASCII

### Analogi Dapur Restoran Bintang Lima

* **CPython Multithreading (Single GIL Kitchen)**: Terdapat 4 koki (Thread), tetapi hanya ada **1 Pisau Dapur Utama (GIL)**. Walaupun ada 4 koki di ruangan yang sama, hanya 1 koki yang bisa memotong daging pada satu detik tertentu. Koki lain hanya bisa menunggu giliran, kecuali koki yang sedang menaruh adonan ke oven kue (I/O Wait), ia melepaskan pisau tersebut sehingga koki lain bisa memotong.
* **Multiprocessing Standar (Banyak Dapur Terpisah + Kurir Antar Ruangan)**: Dibuat 4 gedung dapur terpisah (Process). Jika Dapur 1 mau mengirimkan adonan ke Dapur 2, adonan harus dibekukan dan dipaketkan ke dalam kotak kargo (Pickling/Serialization), dibawa lewat jalan raya umum (OS Pipe), dibuka bungkusnya di Dapur 2 (Unpickling). Proses ini sangat lambat dan memakan energi logistik.
* **Shared Memory (Satu Meja Putar Stainless Steel Raksasa di Antara Dapur)**: Terdapat 4 dapur terpisah dengan pintu tembus ke **1 Meja Putar Raksasa (POSIX Shared Memory)**. Master meletakkan adonan mentah di meja tersebut. Keempat dapur bisa langsung menguleni adonan yang sama di koordinat masing-masing tanpa ada bungkus kargo dan tanpa kurir.

```
THREADING (1 Memory Space, Shared Heap, GIL Bottleneck):
Process Memory Space
+----------------------------------------------------+
|  Global Heap (Python Objects, PyObject Variables)  |
|                                                    |
|  [ Thread 1 ]  ---\                                |
|  [ Thread 2 ]  ----> [ GIL MUTEX ] -> Execution Engine
|  [ Thread 3 ]  ---/                                |
+----------------------------------------------------+

MULTIPROCESSING SHARED MEMORY (Isolated Heaps, Zero-Copy Shared Segment):
Process Master                Process Worker 1              Process Worker 2
+-----------------------+     +-----------------------+     +-----------------------+
| Local Heap (Bebas GIL)|     | Local Heap (Bebas GIL)|     | Local Heap (Bebas GIL)|
| Python Interpreter 1  |     | Python Interpreter 2  |     | Python Interpreter 3  |
+-----------+-----------+     +-----------+-----------+     +-----------+-----------+
            |                             |                             |
            \---------------------+       |       +---------------------/
                                  |       |       |
                                  v       v       v
                   +---------------------------------------------+
                   |  OS POSIX Shared Memory Block (/dev/shm)    |
                   |  [ Raw Continuous Bytes - Zero Serialization]|
                   +---------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Reentrant Lock & Producer-Consumer via Condition Variable

Contoh ini mendemonstrasikan koordinasi producer-consumer multithreaded murni menggunakan `threading.Condition` untuk mengontrol *buffer capacity* tanpa melakukan polling (*busy-waiting* CPU).

```python
"""
production_condition_queue.py
Implementasi bounded thread-safe queue dengan backpressure menggunakan threading.Condition.
"""

from __future__ import annotations
import threading
import time
from typing import Generic, TypeVar, List

T = TypeVar("T")


class BoundedEventQueue(Generic[T]):
    def __init__(self, capacity: int) -> None:
        self._capacity: int = capacity
        self._queue: List[T] = []
        self._lock: threading.Lock = threading.Lock()
        # Condition terikat pada lock internal
        self._not_full: threading.Condition = threading.Condition(self._lock)
        self._not_empty: threading.Condition = threading.Condition(self._lock)

    def put(self, item: T, timeout: float | None = None) -> bool:
        """Menambahkan item ke antrean, block jika kapasitas penuh."""
        with self._not_full:
            start_time = time.monotonic()
            while len(self._queue) >= self._capacity:
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                    self._not_full.wait(timeout=remaining)
                else:
                    self._not_full.wait()

            self._queue.append(item)
            # Notifikasi konsumen bahwa data telah tersedia
            self._not_empty.notify()
            return True

    def get(self, timeout: float | None = None) -> T:
        """Mengambil item dari antrean, block jika antrean kosong."""
        with self._not_empty:
            start_time = time.monotonic()
            while len(self._queue) == 0:
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        raise TimeoutError("Queue empty timeout exceeded")
                    self._not_empty.wait(timeout=remaining)
                else:
                    self._not_empty.wait()

            item = self._queue.pop(0)
            # Notifikasi produser bahwa slot telah tersedia
            self._not_full.notify()
            return item

    def size(self) -> int:
        with self._lock:
            return len(self._queue)


def demo_simple_condition() -> None:
    queue: BoundedEventQueue[int] = BoundedEventQueue(capacity=3)

    def producer() -> None:
        for i in range(5):
            success = queue.put(i, timeout=2.0)
            print(f"[Producer] Produced: {i} | Status: {success}")
            time.sleep(0.05)

    def consumer() -> None:
        time.sleep(0.2)  # Delay start untuk menunjukkan buffer filling up
        for _ in range(5):
            val = queue.get(timeout=2.0)
            print(f"  [Consumer] Consumed: {val}")
            time.sleep(0.1)

    t_prod = threading.Thread(target=producer, name="ProducerThread")
    t_cons = threading.Thread(target=consumer, name="ConsumerThread")

    t_prod.start()
    t_cons.start()
    t_prod.join()
    t_cons.join()


if __name__ == "__main__":
    demo_simple_condition()
```

### 7.2 Practical Example: Zero-Copy Shared Memory Frame Processor

Contoh industri berikut mengimplementasikan kluster pemrosesan data biner massal (misal: simulasi frame video mentah atau array analitik finansial) menggunakan `multiprocessing.shared_memory` bersamaan dengan `spawn` process context. Data di-generate di memori bersama, dimutasi secara in-place oleh worker tanpa serialization overhead.

```python
"""
production_zero_copy_engine.py
Komputasi paralel zero-copy in-place array mutator enterprise.
"""

from __future__ import annotations
import multiprocessing as mp
from multiprocessing import shared_memory
import struct
import sys
import time
from typing import List, Tuple

# Metadata Array: 10,000,000 Integer 64-bit = ~80 Megabytes
ARRAY_SIZE = 10_000_000
DATA_TYPE = "q"  # 64-bit signed long long (8 bytes)
BYTE_SIZE = struct.calcsize(DATA_TYPE)
TOTAL_BYTES = ARRAY_SIZE * BYTE_SIZE


def worker_task(
    shm_name: str,
    start_idx: int,
    end_idx: int,
    scalar_multiplier: int
) -> None:
    """
    Subproses worker: Mengaitkan diri ke POSIX Shared Memory yang sudah ada,
    membungkus byte buffer ke memoryview, dan melakukan in-place mutation.
    """
    existing_shm = None
    try:
        # 1. Attach ke memory block yang ada via identifier nama
        existing_shm = shared_memory.SharedMemory(name=shm_name)
        
        # 2. Bungkus raw buffer ke memoryview bertipe format native
        # 'q' adalah signed 64-bit int. Cast memoryview langsung tanpa copy
        raw_mv = memoryview(existing_shm.buf)
        typed_mv = raw_mv.cast(DATA_TYPE)
        
        # 3. Eksekusi komputasi in-place mutasi
        # Segment slicing pada typed_mv tidak mengalokasikan data baru
        for i in range(start_idx, end_idx):
            typed_mv[i] = typed_mv[i] * scalar_multiplier

    except Exception as exc:
        sys.stderr.write(f"Worker Error on slice [{start_idx}:{end_idx}]: {exc}\n")
        raise
    finally:
        # Penting: Tutup akses file descriptor memori di proses worker
        if existing_shm is not None:
            existing_shm.close()


def run_parallel_zero_copy_engine(num_workers: int = 4) -> None:
    # Memaksa context 'spawn' demi portabilitas dan keamanan state memori
    ctx = mp.get_context("spawn")
    
    print(f"[*] Mengalokasikan {TOTAL_BYTES / (1024 * 1024):.2f} MB di Shared Memory...")
    master_shm = shared_memory.SharedMemory(create=True, size=TOTAL_BYTES)
    
    try:
        # Inisialisasi data secara serial oleh Master
        print("[*] Menginisialisasi array biner mentah...")
        raw_view = memoryview(master_shm.buf)
        int_view = raw_view.cast(DATA_TYPE)
        for i in range(ARRAY_SIZE):
            int_view[i] = 1  # Nilai awal 1

        print(f"[*] Sampel awal (indeks 0..4): {list(int_view[0:5])}")

        # Tentukan pembagian beban kerja berbasis segment offset
        chunk_size = ARRAY_SIZE // num_workers
        workers: List[mp.Process] = []
        multiplier = 5

        t_start = time.perf_counter()

        for w_id in range(num_workers):
            start_i = w_id * chunk_size
            # Pastikan worker terakhir menangani residu pembagian
            end_i = ARRAY_SIZE if w_id == num_workers - 1 else (w_id + 1) * chunk_size
            
            p = ctx.Process(
                target=worker_task,
                args=(master_shm.name, start_i, end_i, multiplier),
                name=f"ZeroCopyWorker-{w_id}"
            )
            workers.append(p)
            p.start()

        for p in workers:
            p.join()
            if p.exitcode != 0:
                raise RuntimeError(f"Worker {p.name} exit dengan error code: {p.exitcode}")

        t_elapsed = time.perf_counter() - t_start
        print(f"[+] Komputasi Paralel Selesai dalam {t_elapsed:.4f} detik.")
        print(f"[*] Sampel akhir (indeks 0..4 pasca perkalian): {list(int_view[0:5])}")
        
        # Validasi integritas
        assert int_view[0] == multiplier, "Integritas mutasi data gagal!"
        assert int_view[ARRAY_SIZE - 1] == multiplier, "Batas data ujung gagal!"

    finally:
        # Cleanup Lifecycle: Close handle proses induk dan hapus POSIX segment dari OS
        print("[*] Membersihkan SharedMemory segment dari kernel OS...")
        master_shm.close()
        master_shm.unlink()


if __name__ == "__main__":
    run_parallel_zero_copy_engine(num_workers=4)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Engine Transkripsi & Ingestion Audit Finansial Real-time (FinTech Core)
* **Kebutuhan**: Memproses batch 50.000 dokumen ledger per detik. Masing-masing dokumen membutuhkan:
  1. Parsing biner dan dekripsi payload (CPU-Bound).
  2. Kalkulasi checksum SHA-512 & verifikasi signature (CPU-Bound berat).
  3. Verifikasi balance ke distributed memory database (Redis/Aerospike) via network pool (I/O-Bound).
  4. Penyimpanan audit trail ke Cloud Object Storage (I/O-Bound berlatensi fluktuatif).

### Masalah Arsitektur Sebelumnya
Pendekatan naif menggunakan `ThreadPoolExecutor` global mengalami stagnasi total akibat kontensi GIL pada kalkulasi SHA-512. CPU usage mentok di 100% pada satu core (Core-0) sementara 31 core lainnya di instance AWS `c6i.8xlarge` menganggur. Upaya migrasi ke `multiprocessing.Pool` biasa menyebabkan lonjakan konsumsi RAM hingga 48GB karena serialisasi payload antar socket, mengakibatkan Linux OOM killer memusnahkan engine setiap 3 jam.

### Solusi Arsitektur Enterprise: Hybrid Multi-Tier Pipeline

```
+-------------------------------------------------------------------------------+
|                    Master Ingestion Process (Async IO / POSIX Network)        |
|  - Menerima raw payload batch via UDP/eBPF socket                             |
|  - Menyimpan byte stream ke POSIX Shared Memory Ring-Buffer                   |
|  - Menembakkan segment coordinate pointer ke Process Worker Pool via IPC Pipe |
+-------------------------------------------------------------------------------+
                                      |
                                      v
       +---------------------------------------------------------------+
       | Process Worker Farm (Spawned - 1 Worker per Dedicated CPU Core)|
       | Menerima Tuple: (shm_segment_id, offset, length)               |
       +---------------------------------------------------------------+
                 |                                             |
                 v (Zero-Copy Read)                            v (Zero-Copy Read)
       +----------------------------+                +----------------------------+
       |   Worker Process 1         |                |   Worker Process N         |
       |   - Dekripsi Biner         |                |   - Dekripsi Biner         |
       |   - CPU Core SHA-512 Calc  |                |   - CPU Core SHA-512 Calc  |
       |   - Status: Verified       |                |   - Status: Verified       |
       +--------------+-------------+                +--------------+-------------+
                      |                                             |
                      +----------------------+----------------------+
                                             |
                                             v
                      +---------------------------------------------+
                      | Local ThreadPoolExecutor (I/O Farm Internal)|
                      | Worker Process tidak dibebani blocking I/O: |
                      |   * Thread 1: Async Dispatch to Redis       |
                      |   * Thread 2: Write audit payload to S3     |
                      |   * GIL terlepas bebas selama socket syscall|
                      +---------------------------------------------+
```

### Implementasi Pola Hybrid Engine Terdistribusi:

```python
"""
enterprise_hybrid_engine.py
Arsitektur Hybrid Concurrency Pipeline: Process Worker Farm + Local Thread I/O Pool.
"""

from __future__ import annotations
import concurrent.futures
import hashlib
import multiprocessing as mp
import os
import time
from typing import Dict, Any, NamedTuple


class LedgerTask(NamedTuple):
    transaction_id: str
    raw_payload: bytes


class ProcessingResult(NamedTuple):
    transaction_id: str
    digest: str
    dispatched: bool
    worker_pid: int


def io_network_dispatch(tx_id: str, digest: str) -> bool:
    """
    Simulasi operasi I/O bound: Pengiriman ke Redis/S3.
    Selama I/O sleep, interpreter Python otomatis melepaskan GIL.
    """
    time.sleep(0.01)  # Simulasi latensi RTT socket 10ms
    return True


def hybrid_process_worker(task_queue: mp.Queue, result_queue: mp.Queue) -> None:
    """
    Process Worker: Berjalan independen pada 1 Core CPU.
    Menggunakan ThreadPool internal untuk melakukan delegasi I/O tak-terbatas.
    """
    pid = os.getpid()
    # Mengalokasikan 4 thread per CPU process untuk handling network latency
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=4, thread_name_prefix=f"WorkerIO-{pid}"
    ) as thread_pool:
        while True:
            task: LedgerTask | None = task_queue.get()
            if task is None:
                # Poison Pill diterima, hentikan processing
                break

            # 1. CPU-Bound Heavy Execution (Bebas GIL antar-proses)
            hasher = hashlib.sha512()
            for _ in range(5_000):  # Simulasi compute-intensive derivation loop
                hasher.update(task.raw_payload)
            digest = hasher.hexdigest()

            # 2. I/O-Bound Execution didelegasikan ke Thread Pool internal
            future = thread_pool.submit(io_network_dispatch, task.transaction_id, digest)
            
            # Non-blocking collection handling
            def on_complete(fut: concurrent.futures.Future[bool], t_id=task.transaction_id, dig=digest) -> None:
                try:
                    success = fut.result()
                    result_queue.put(ProcessingResult(t_id, dig, success, pid))
                except Exception as ex:
                    # Logging error boundary
                    sys.stderr.write(f"I/O Exception on {t_id}: {ex}\n")

            future.add_done_callback(on_complete)


def run_enterprise_pipeline() -> None:
    ctx = mp.get_context("spawn")
    task_queue: mp.Queue = ctx.Queue(maxsize=1000)
    result_queue: mp.Queue = ctx.Queue()

    num_cpu_workers = max(1, mp.cpu_count() - 1)
    workers = []

    print(f"[*] Inisialisasi Hybrid Architecture: Spawning {num_cpu_workers} CPU Workers...")
    for _ in range(num_cpu_workers):
        p = ctx.Process(target=hybrid_process_worker, args=(task_queue, result_queue))
        p.start()
        workers.append(p)

    # Ingest Batch
    total_messages = 100
    print(f"[*] Mengirim {total_messages} beban transaksi ledger...")
    for i in range(total_messages):
        payload = f"TRANSACTION_RECORD_{i}_XYZ_CORP_BALANCE_SHEET".encode("utf-8")
        task_queue.put(LedgerTask(f"TX-{i:05d}", payload))

    # Kirim Poison Pill ke setiap worker
    for _ in range(num_cpu_workers):
        task_queue.put(None)

    # Kumpulkan hasil
    received_results = 0
    start_time = time.perf_counter()
    while received_results < total_messages:
        res: ProcessingResult = result_queue.get()
        received_results += 1

    total_time = time.perf_counter() - start_time
    print(f"[+] Sukses memproses {received_results} transaksi dalam {total_time:.2f}s.")
    print(f"[+] Throughput: {received_results / total_time:.2f} tx/sec.")

    for p in workers:
        p.join()


if __name__ == "__main__":
    run_enterprise_pipeline()
```

---

## 9. Trade-offs

Mengonfigurasi konkurensi adalah seni menyeimbangkan kompromi perangkat keras dan kernel:

```
                  [ ARSITEKTUR KONKURENSI ]
                              |
       +----------------------+----------------------+
       |                                             |
[ PURE THREADING ]                            [ PURE MULTIPROCESS ]
  + Skalabilitas memori irit (MBs)              + Penggunaan 100% Core CPU sejati
  + Komunikasi in-memory pointer gratis         + Isolasi kegagalan penuh
  - Terkekang oleh CPython GIL                  - Overhead konsumsi memori masif (GBs)
  - Race condition fatal pada level memori      - Beban serialisasi payload (Pickle)
       |                                             |
       \----------------------+----------------------/
                              |
                   [ HYBRID PROCESS-THREAD ]
                     (Arsitektur Optimal)
       + Utilisasi seluruh CPU core via worker terisolasi
       + Threadpool lokal menyerap blocking socket I/O
       + Memori terkontrol via IPC offset / SharedMemory
       - Kompleksitas kode & siklus debug sangat tinggi
       - Risiko resource leak jika shared memory crash
```

### Matriks Kompromi Teknis:
1. **Performance vs Latency**: Pola Threading memberikan *latensi terendah* untuk memulai task (sub-millisecond creation), sementara Multiprocessing memiliki *throughput tertinggi* untuk kalkulasi intensif meskipun inisiasi `spawn` membutuhkan waktu 50ms - 200ms.
2. **Resource Consumption vs Fault Isolation**: Threading berbagi ruang memori yang sama; satu segmentation fault atau crash memory corrupt di thread native extension C (seperti TensorFlow/NumPy) akan membunuh seluruh proses master. Multiprocessing mengisolasi memori; jika worker meledak, master process tetap hidup dan dapat me-respawn worker pengganti.
3. **Financial Cost (Cloud Infrastructure)**: Multiprocessing naif yang boros memori memaksa enterprise melakukan scale-up vertikal ke instance memory-optimized AWS `r6i` (mahal). Optimalisasi hybrid atau zero-copy shared memory memungkinkan deployment pada instance compute-optimized `c6i` dengan biaya 40% lebih rendah untuk throughput yang sama.

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pola 1: Insecure Forking pada Aplikasi Multi-Thread
* **Gejala Fatal**: Subproses anak mengalami hang/freeze permanen (*deadlock*) tepat setelah `p.start()`.
* **Akar Masalah**: Memanggil `multiprocessing.Process` dengan default start method `fork` di Linux ketika proses induk sudah memiliki thread background aktif (misalnya thread logger, collector metrik NewRelic/Datadog). Thread background memegang lock internal CPython saat `fork()` dipanggil.
* **Solusi**: Selalu eksplisit tentukan context di file entrypoint:
  ```python
  import multiprocessing as mp
  # Set di baris paling awal execution
  mp.set_start_method("spawn", force=True) # atau "forkserver"
  ```

### Anti-Pola 2: Kebocoran Posix Shared Memory (/dev/shm OOM)
* **Gejala Fatal**: Ruang disk `/dev/shm` habis (`No space left on device`), memicu kegagalan crash di seluruh sistem host.
* **Akar Masalah**: Subproses yang meng-create `SharedMemory` crash atau di-kill menggunakan `SIGKILL` (`kill -9`) sebelum mengeksekusi method `shm.unlink()`. File deskriptor shared memory tetap tertahan di kernel Linux.
* **Solusi**: Buat wrapper menggunakan POSIX signal handling dan context manager deterministik:
  ```python
  import signal
  import sys
  from multiprocessing import shared_memory

  class SafeSharedMemory:
      def __init__(self, size: int):
          self.shm = shared_memory.SharedMemory(create=True, size=size)
          # Trap standard kill signals
          signal.signal(signal.SIGINT, self._cleanup_signal)
          signal.signal(signal.SIGTERM, self._cleanup_signal)

      def _cleanup_signal(self, signum, frame):
          self.cleanup()
          sys.exit(128 + signum)

      def cleanup(self):
          try:
              self.shm.close()
              self.shm.unlink()
          except FileNotFoundError:
              pass
  ```

### Anti-Pola 3: Livelock pada Busy-Waiting
* **Gejala Fatal**: CPU Core melonjak 100%, tetapi tidak ada pekerjaan nyata yang selesai.
* **Akar Masalah**: Menggunakan `while not queue.empty(): pass` tanpa mekanisme back-off atau sinkronisasi sleep/condition.
* **Solusi**: Jangan pernah melakukan *manual polling status*. Manfaatkan primitif event-driven: `threading.Event`, `threading.Condition`, atau blocking queue reads (`queue.get(block=True, timeout=...)`).

---

## 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur berikut sebelum mempromosikan kode konkurensi ke production:

- [ ] **Context Selection**: Gunakan `spawn` atau `forkserver` untuk `multiprocessing`. Hindari raw `fork` murni pada Linux containers modern.
- [ ] **Isolasi Tugas Beban Kerja**: Pisahkan dengan tegas: `concurrent.futures.ThreadPoolExecutor` untuk panggilan API, DB, Network I/O; `concurrent.futures.ProcessPoolExecutor` murni untuk kalkulasi CPU.
- [ ] **Batasi Antrean (Bounded Queue)**: Jangan pernah membuat `mp.Queue()` tanpa batas parameter `maxsize`. Antrean tak terbatas akan memicu OOM cascade ketika produser melampaui kemampuan konsumen.
- [ ] **Zero-Copy untuk Data Ukuran Mega/Giga**: Gunakan `multiprocessing.shared_memory` bersama `memoryview` untuk payload di atas 10MB.
- [ ] **Proteksi Zombie Process**: Pastikan seluruh `Process` di-join atau didaftarkan pada exit handler (`atexit.register`).
- [ ] **Thread Naming Identifiers**: Tetapkan nama thread deskriptif (`thread_name_prefix="PaymentDispatcher-"`) untuk mempermudah identifikasi saat menganalisis stack trace lewat `py-spy` atau `gdb`.
- [ ] **Deadlock Prevention via Hierarchy**: Jika harus mengakuisisi lebih dari satu lock, tetapkan aturan akuisisi berurutan secara deterministik berdasarkan ID lock global yang konsisten.
- [ ] **Signal Handling**: Sub-proses wajib menangani graceful degradation pada sinyal `SIGTERM`.

---

## 12. Hands-on Practice

Buatlah direktori praktikum dengan hierarki:
```
hands-on/
└── m02/
    ├── pipeline_bench.py
    └── ring_buffer_shm.py
```

### Langkah Praktikum 1: Membangun Thread-Safe Circular Ring Buffer
Buka file `hands-on/m02/ring_buffer_shm.py` dan buat buffer byte berbasis memori tetap (*bounded circular buffer*) yang dapat digunakan lintas thread menggunakan sinkronisasi `threading.Condition` dan `memoryview`.

```python
# hands-on/m02/ring_buffer_shm.py
from __future__ import annotations
import threading
import time

class ThreadSafeRingBuffer:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._buffer = bytearray(capacity)
        self._write_pos = 0
        self._read_pos = 0
        self._count = 0
        self._lock = threading.Lock()
        self._cond_push = threading.Condition(self._lock)
        self._cond_pop = threading.Condition(self._lock)

    def write_byte(self, byte_val: int) -> None:
        with self._cond_push:
            while self._count == self._capacity:
                self._cond_push.wait()
            self._buffer[self._write_pos] = byte_val
            self._write_pos = (self._write_pos + 1) % self._capacity
            self._count += 1
            self._cond_pop.notify()

    def read_byte(self) -> int:
        with self._cond_pop:
            while self._count == 0:
                self._cond_pop.wait()
            byte_val = self._buffer[self._read_pos]
            self._read_pos = (self._read_pos + 1) % self._capacity
            self._count -= 1
            self._cond_push.notify()
            return byte_val

if __name__ == "__main__":
    rb = ThreadSafeRingBuffer(capacity=5)
    
    def writer():
        for b in range(10):
            rb.write_byte(b)
            print(f"[Writer] Wrote byte: {b}")
            time.sleep(0.02)

    def reader():
        for _ in range(10):
            val = rb.read_byte()
            print(f"  [Reader] Read byte: {val}")
            time.sleep(0.05)

    tw = threading.Thread(target=writer)
    tr = threading.Thread(target=reader)
    tw.start(); tr.start()
    tw.join(); tr.join()
```

### Langkah Praktikum 2: Verifikasi & Benchmark
Jalankan benchmark perbandingan transmisi `multiprocessing.Queue` versus `multiprocessing.shared_memory` pada file `hands-on/m02/pipeline_bench.py`. Ukur waktu transmisi array data 50MB di antara 2 proses.

---

## 13. Exercise

### Level Easy
Tuliskan script multithreaded menggunakan `threading.Barrier` yang mengoordinasikan 3 thread worker (misal: Worker Data, Worker Network, Worker GPU). Masing-masing thread melakukan persiapan selama durasi acak, dan tidak ada satupun worker yang boleh mulai memproses tugas sebelum ketiganya selesai melakukan inisialisasi di barrier tersebut.

### Level Medium
Buat sebuah pool worker multiprocessing kustom (maksimal 2 subproses) tanpa modul `multiprocessing.Pool` bawaan. Pool harus menggunakan dua instance `multiprocessing.Queue` (Task Queue dan Result Queue), mengimplementasikan mekanisme *Poison Pill* untuk mematikan subproses secara bersih saat master selesai, serta menangani timeout jika eksekusi task subproses macet melebihi batas waktu 3 detik.

### Level Hard
Rancang modul cache memori terdistribusi IPC lokal (`ZeroCopyKeyValueCache`). Master mengalokasikan satu blok `SharedMemory` sebesar 64MB. Kunci cache dipetakan menggunakan tabel hash biner sederhana dengan fixed-size bucket slots. Tulis fungsi `get(key: str) -> bytes` dan `set(key: str, val: bytes) -> bool` yang thread-safe dan process-safe menggunakan `multiprocessing.Lock` antar proses. Tidak boleh ada pemanggilan modul serialisasi `pickle` sama sekali.

---

## 14. Challenge

**Skenario Tantangan Tingkat Arsitek:**
Sebuah bursa perdagangan komoditas (*crypto/equity exchange*) mendesain *order book matching engine* deterministik in-memory. 
* Persyaratan:
  1. Engine harus mampu menerima 100.000 order masuk per detik via thread network socket (mock socket diperbolehkan).
  2. Matching Engine kalkulasi core adalah proses terpisah (*Single-Writer, Bebas Lock*) untuk menghindari kontensi memori dan latensi kernel context-switch.
  3. Master dan Engine berkomunikasi melalui implementasi struktur data **Lock-Free Single-Producer Single-Consumer (SPSC) Circular Queue** di atas POSIX Shared Memory menggunakan nilai integer memory pointers atomik.
  4. Jika antrean penuh, master process harus menerapkan strategi *Backpressure Drop Notification* seketika tanpa men-stall socket server.
  
**Tugas Anda**: Buat arsitektur minimum yang dapat dieksekusi lengkap tanpa dependensi eksternal selain CPython Standard Library. Tunjukkan throughput order parsing dan buktikan ketiadaan memory leak selama simulasi load 10 detik.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Analisis Singkat)
1. Apa fungsi dari flag internal `gil_drop_request` di CPython dan kapan ia diubah nilainya menjadi 1?
2. Mengapa metode start process `fork` berbahaya jika dipanggil dalam program Python yang sudah menginisialisasi multithreading?
3. Sebutkan perbedaan mekanis antara `threading.Lock` dan `threading.RLock`! Kapan Anda wajib menggunakan `RLock`?
4. Apa yang menyebabkan *Convoy Effect* pada interaksi thread I/O-bound dan CPU-bound di Python?
5. Mengapa pemanggilan `shm.close()` pada `multiprocessing.shared_memory` belum menghapus segment memori tersebut dari sistem operasi Linux?

### Bagian 2: Intermediate (Arsitektural & Performa)
6. Bagaimana cara Python melepaskan GIL saat sebuah thread mengeksekusi operasi C-native seperti kalkulasi hash `hashlib.sha256()` atau `socket.recv()`?
7. Apa kelemahan utama komunikasi antar-proses yang bergantung pada `multiprocessing.Queue` ketika menangani payload matriks numerik biner berukuran ratusan megabyte?
8. Mengapa mutasi in-place pada Python `memoryview` yang membungkus `SharedMemory` diklasifikasikan sebagai operasi *zero-copy*?
9. Jelaskan bahaya *Priority Inversion* pada multithreading, dan bagaimana primitif sinkronisasi modern memitigasinya!
10. Bagaimana cara kerja internal primitif `threading.Condition.wait()` terhadap lock yang terkait? Apakah lock tetap dipegang saat thread tidur?

### Bagian 3: Skenario Kasus Produksi (Troubleshooting Lapangan)

11. **Kasus A**:
    Aplikasi microservice berbasis `ProcessPoolExecutor` di server Kubernetes tiba-tiba mengalami crash massal dengan pesan error: `SIGBUS: Bus error`. Setelah diinvestigasi, master proses menggunakan `multiprocessing.shared_memory` dan membuat segment berukuran dinamis. Apa akar masalah sistem operasi terhadap error `SIGBUS` ini dan bagaimana memperbaikinya?

12. **Kasus B**:
    Sebuah daemon Python memproses ribuan task CPU per hari. Anda mendapati penggunaan RAM server merangkak naik secara linear (*memory leak*) hingga server kehabisan memori setiap akhir pekan, meskipun garbage collector `gc.collect()` dipanggil secara eksplisit di proses induk. Arsitektur menggunakan worker multiprocessing via method `spawn`. Di mana lokasi kebocoran memori paling potensial dan bagaimana mendeteksinya?

13. **Kasus C**:
    Anda memiliki web backend multithreaded (menggunakan WSGI container dengan 16 worker threads). Ketika traffic meningkat, latensi p99 melonjak dari 15ms menjadi 3500ms, namun utilisasi CPU host hanya terdeteksi 12%. Profiling awal menunjukkan sebagian besar thread menghabiskan waktu di status `futex_wait`. Identifikasi apa yang sedang terjadi di runtime CPython dan susun langkah perbaikan arsitekturnya!

---

## 16. Summary

* **CPython GIL**: Merupakan mekanisme perlindungan manajemen memori non-thread-safe internal CPython (`PyObject` reference counting). GIL dilepaskan secara periodik berdasarkan `sys.getswitchinterval()` atau secara otomatis ketika thread melakukan native syscall (I/O, eksekusi extension terisolasi).
* **Multithreading**: Optimal secara eksklusif untuk operasi **I/O-Bound** (jaringan, database, file system). Multithreading pada pekerjaan CPU-bound di mesin multi-core justru mendegradasi throughput karena *Convoy Effect* dan overhead kontensi mutex GIL.
* **Process Creation Semantics**: Memilih antara `spawn`, `fork`, dan `forkserver` berdampak langsung pada stabilitas memori. `spawn` memberikan isolasi heap total dan membersihkan state mutex residual dari proses induk, menjadikannya standar stabilitas production.
* **Zero-Copy Architecture**: Penggunaan `multiprocessing.shared_memory` bersama dengan `memoryview` memangkas overhead serialisasi `pickle` dan IPC OS Pipes, mengubah performa komunikasi antar core dari skala ratusan milidetik menjadi hitungan sub-mikrodetik.
* **Arsitektur Hybrid Enterprise**: Desain perangkat lunak konkurensi modern yang paling tangguh memanfaatkan keunggulan keduanya: Proses multi-core mandiri untuk memecah beban komputasi CPU, dipadukan dengan thread pool internal di tiap proses untuk melayani blocking I/O secara konkruen.