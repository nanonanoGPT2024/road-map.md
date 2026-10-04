# Kurikulum Rekayasa Perangkat Lunak Enterprise: Python
## Kategori: 02-Programming-Languages
### BAB 01: Fondasi dan Arsitektur
#### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Software Engineer / Staff Backend Engineer diharapkan mampu:
* Membedah siklus evaluasi CPython dari source code, Abstract Syntax Tree (AST), Control Flow Graph (CFG), Bytecode, hingga eksekusi pada Virtual Machine CPython Frame Evaluation Loop.
* Menganalisis dan memitigasi overhead alokasi memori internal CPython (*PyMalloc*, *Arenas*, *Pools*, *Blocks*, *Reference Counting*, dan *Cyclic Tracing Garbage Collector* Generational).
* Merancang sistem konkuren throughput tinggi yang mengatasi keterbatasan *Global Interpreter Lock* (GIL) memanfaatkan *subinterpreters* (PEP 684/PEP 554), multiprocessing zero-copy shared memory (`multiprocessing.shared_memory`), dan asynchronous I/O primitives.
* Mengimplementasikan metaprogramming tingkat lanjut menggunakan *Descriptor Protocol* (`__get__`, `__set__`, `__delete__`), *Metaclasses*, dan class generation dinamis untuk membangun framework internal berkinerja tinggi.
* Menerapkan optimasi struktur data tingkat rendah dengan `__slots__`, zero-copy `memoryview`, serta buffer protocol guna memangkas memory footprint dan latency pada skala data terabita.
* Melakukan profiling deterministik dan sampling pada level produksi menggunakan `cProfile`, `py-spy`, dan `tracemalloc` tanpa menimbulkan stop-the-world penalty yang signifikan.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
* Pemrograman Python tingkat menengah (struktur data bawaan, OOP, closures, basic decorators, generators).
* Pemahaman arsitektur sistem komputer: hierarki memori (L1/L2/L3 cache, RAM), CPU pipelining, virtual memory paging, serta OS-level threads vs kernel processes.
* Pengetahuan dasar bahasa pemrograman C (pointer, manual memory allocation `malloc`/`free`, struct layout) untuk memahami implementasi CPython runtime.
* Pengalaman mengoperasikan Linux environment, profiling tools OS (perf, htop), serta jaringan TCP/IP.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. CPython Runtime Execution Pipeline
Eksekusi kode Python pada CPython runtime melalui beberapa tahapan diskrit:

1. **Tokenizing & Parsing**: Source code (`.py`) dibaca oleh tokenizer menjadi stream token lexical. Parser CPython (berbasis PEG parser sejak Python 3.9) mengonversi token-token ini menjadi *Abstract Syntax Tree* (AST).
2. **Compilation**: AST ditransformasikan ke dalam *Control Flow Graph* (CFG). Compiler kemudian mengoptimalkan jump paths dan membangkitkan *Python Bytecode* (`PyCodeObject`).
3. **Evaluation Loop**: Interpreter mengeksekusi bytecode via function pointer evaluation loop raksasa yang secara historis dikenal sebagai `_PyEval_EvalFrameDefault` di modul `Python/ceval.c`. Sejak Python 3.11+, pipeline ini dilengkapi dengan *Specializing Adaptive Interpreter* (PEP 659), yang memantau instruksi bytecode saat runtime dan menggantinya dengan varian terspesialisasi (inline caches) jika tipe data yang diobservasi bersifat stabil.

```
Source Code (.py)
       │
       ▼
[Tokenizer & PEG Parser] ──────────► Abstract Syntax Tree (AST)
                                              │
                                              ▼
                                   [Symbol Table & Compiler]
                                              │
                                              ▼
                                     PyCodeObject (Bytecode)
                                              │
                                              ▼
                                ┌───────────────────────────┐
                                │   CPython Virtual Machine │
                                │  _PyEval_EvalFrameDefault │
                                │  (PEP 659 Adaptive Tier)  │
                                └───────────────────────────┘
```

#### 3.2. Hierarki Manajemen Memori: PyMalloc
CPython menghindari overhead pemanggilan kernel OS (`malloc`/`free`) secara langsung untuk objek-objek kecil (<= 512 bytes) dengan mengimplementasikan allocator khusus bernama **PyMalloc**:

* **Arena (256 KB)**: Alokasi memori berukuran besar yang diperoleh langsung dari OS via `mmap()` atau `malloc()`. Arena dipecah menjadi Pools.
* **Pool (4 KB)**: Menampung kumpulan *Blocks* dengan ukuran seragam. Pool berukuran 4 KB sesuai dengan ukuran standar virtual memory page pada arsitektur x86_64.
* **Block (8 - 512 Bytes)**: Unit terkecil alokasi objek CPython. Blok dibagi menjadi 64 *size-classes* dengan interval 8 byte (misal: class 0 = 8 byte, class 1 = 16 byte, dst).
* **Direct OS Allocation**: Objek yang membutuhkan memori > 512 bytes langsung dialokasikan lewat system allocator standar (`PyMem_RawMalloc` wrapper dari `malloc`).

```
+-----------------------------------------------------------------------+
|                             OS Memory Space                           |
+-----------------------------------------------------------------------+
       │                                              │
       │ Allocations > 512 Bytes                      │ Allocations <= 512 Bytes
       ▼                                              ▼
+---------------------+                      +--------------------------+
|  Standard System    |                      |      PyMalloc System     |
|  malloc() / free()  |                      |                          |
+---------------------+                      |  +--------------------+  |
                                             |  |   Arena (256 KB)   |  |
                                             |  | +----------------+ |  |
                                             |  | |  Pool (4 KB)   | |  |
                                             |  | | [B][B][B][B]...| |  |
                                             |  | +----------------+ |  |
                                             |  +--------------------+  |
                                             +--------------------------+
```

#### 3.3. Dual Garbage Collection Mechanism
CPython mengombinasikan dua arsitektur GC independen:
1. **Reference Counting (Mekanisme Primer)**:
   * Setiap objek membungkus header `PyObject` yang memuat field `ob_refcnt`.
   * Saat referensi bertambah (`Py_INCREF`), counter dinaikkan. Saat referensi berkurang (`Py_DECREF`), counter diturunkan.
   * Ketika `ob_refcnt == 0`, dealokasi memori terjadi seketika (*deterministic deallocation*).
   * **Limitasi**: Tidak dapat mendeteksi *cyclic references* (objek A merujuk ke B, dan B merujuk balik ke A).

2. **Cyclic Generational Garbage Collector (Mekanisme Sekunder)**:
   * Bertugas menangani siklus sirkular pada objek *container* (`dict`, `list`, `set`, `tuple`, custom class).
   * Membagi container ke dalam 3 generasi: Generation 0 (objek baru), Generation 1 (objek yang bertahan dari GC gen 0), Generation 2 (objek *long-lived*).
   * GC mengevaluasi rasio alokasi terhadap dealokasi menggunakan algoritma double-linked list traversal untuk mengisolasi klaster objek yang referensinya hanya berasal dari dalam grup siklus itu sendiri.

#### 3.4. Global Interpreter Lock (GIL) & Solusi Skalabilitas
GIL adalah mutex internal yang mencegah multiple native thread mengeksekusi CPython bytecode secara bersamaan dalam satu proses interpreter. Tujuannya adalah melindungi struktur internal CPython dan integritas `ob_refcnt` dari race condition tanpa memerlukan fine-grained locks di setiap alokasi objek.

* **Dampak**: Operasi CPU-bound tidak dapat diskalakan melintasi core prosesor hanya dengan `threading.Thread`.
* **Solusi Enterprise**:
  1. *Multiprocessing*: Proses terisolasi dengan OS memory overhead tersendiri.
  2. *SharedMemory / IPC Zero-Copy*: Komunikasi performa tinggi antar-proses bypass serialisasi `pickle`.
  3. *Subinterpreters (PEP 684)*: Multiple interpreter instances dalam satu OS process, masing-masing memiliki per-interpreter GIL sendiri (mulai Python 3.12+).
  4. *Free-threaded CPython (PEP 703)*: Build eksperimental Python 3.13+ tanpa GIL menggunakan mimalloc dan biased reference counting.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan di Skala Enterprise | Apa yang Sebenarnya Dilakukan Engine |
| :--- | :--- | :--- |
| **`__slots__` Optimization** | Mencegah runaway memory consumption pada service ingestion jutaan event data per detik. | Menghapus atribut internal dictionary (`__dict__`) pada setiap instance objek dan menggantinya dengan array fixed-offset descriptor pointer statis pada level C-struct. |
| **Descriptor Protocol** | Validasi skema dinamis, lazy-loading resource database, ORM primitives berkinerja tinggi. | Mengintersepsi lookup atribut objek (`.` operator) via fungsi hook `__get__`, `__set__`, dan `__delete__` pada level class, bukan instance. |
| **Zero-Copy Memoryviews** | Memproses payload jaringan biner (misal: streaming Parquet/Protobuf gigabytes) tanpa memory spike. | Mengekspos pointer buffer memori internal C tingkat rendah melalui C-level Buffer Protocol tanpa memicu duplikasi bit-array di RAM. |
| **Adaptive Specialization** | Mempercepat hot loops eksekusi komputasi backend tanpa refactor ke C/Cython. | Bytecode type-neutral dipantau runtime, diubah menjadi opcode terspesialisasi (seperti `BINARY_OP_ADD_INT`) saat tipe stabil teridentifikasi. |

---

### 5. How (Workflow Detail)

Alur penanganan permintaan payload biner berukuran gigabita pada arsitektur pipeline enterprise:

```
[Network Socket / Ingestion Pipeline]
                 │
                 ▼
     [OS Kernel Socket Buffer]
                 │
                 ▼  (Read into C-Buffer)
     [PyMemoryView / Buffer Protocol]  <--- Zero-Copy Memory Window
                 │
                 ├── Slice Data Segment (Tanpa Alokasi RAM Baru)
                 ▼
    [Custom Struct Packing / Unpacking via Descriptors]
                 │
                 ├── Parsing Skema Strict & Validasi Tipe In-Place
                 ▼
    [Worker Pool Processing (Subinterpreters / ProcessPool + SharedMemory)]
                 │
                 ├── Bypass Global Interpreter Lock
                 ▼
    [Final Sink: Disk / High-Speed Storage]
```

---

### 6. Analogy & Diagram ASCII

#### PyMalloc Analogi: Manajemen Parkir Mobil (Arena, Pool, Block)
Bayangkan CPython sebagai pengelola lahan parkir raksasa:
* **Arena**: Blok tanah luas (256 KB) yang dibeli dari pemerintah kota (OS via `mmap`).
* **Pool**: Jalur parkir khusus (4 KB) di dalam tanah tersebut yang diaspal sesuai dengan ukuran kendaraan tertentu (misal: jalur khusus motor, jalur khusus sedan).
* **Block**: Petak parkir individual (misal: 32 bytes). Sebuah motor (objek kecil) diparkir di petak ini secara instan tanpa perlu izin ke pemerintah kota setiap kali parkir.
* **Large Vehicles**: Truk kontainer (objek > 512 bytes) dilarang masuk ke lahan parkir PyMalloc dan wajib mencari lahan parkir khusus langsung di luar (System `malloc`).

```
+========================================================================+
|                         ARENA (256 KB Chunk)                           |
|  +---------------------------+       +-------------------------------+ |
|  |     POOL 0 (4 KB)         |  ...  |       POOL N (4 KB)           | |
|  |   [Size-Class: 32 Bytes]  |       |     [Size-Class: 64 Bytes]    | |
|  | +----+ +----+ +----+      |       | +------+ +------+ +------+    | |
|  | |Blk1| |Blk2| |Blk3| ...  |       | | Blk1 | | Blk2 | | Blk3 | ...| |
|  | +----+ +----+ +----+      |       | +------+ +------+ +------+    | |
|  +---------------------------+       +-------------------------------+ |
+========================================================================+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Inspecting Bytecode & Specialization
Melihat bagaimana CPython mengeksekusi bytecode dan memverifikasi ketiadaan `__dict__` ketika menggunakan `__slots__`.

```python
import dis

class StandardPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

class SlottedPoint:
    __slots__ = ('x', 'y')
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

def compute_distance_sq(p: SlottedPoint) -> float:
    return p.x * p.x + p.y * p.y

# Inspeksi bytecode evaluasi
print("=== BYTECODE compute_distance_sq ===")
dis.dis(compute_distance_sq)

p_std = StandardPoint(1.0, 2.0)
p_slot = SlottedPoint(1.0, 2.0)

print(f"StandardPoint instance dictionary: {hasattr(p_std, '__dict__')}") # True
print(f"SlottedPoint instance dictionary: {hasattr(p_slot, '__dict__')}")   # False
```

#### 7.2. Practical Example: Enterprise Zero-Copy Binary Telemetry Parser
Parser biner performa tinggi menggunakan descriptor protocol, buffer protocol, dan zero-copy processing tanpa library pihak ketiga.

```python
from __future__ import annotations
import struct
from typing import Any, Union

class UnsignedIntField:
    """Descriptor untuk membaca unsigned int (32-bit) langsung dari memoryview offset."""
    def __init__(self, offset: int):
        self.offset = offset

    def __get__(self, instance: Any, owner: type | None = None) -> Union[int, UnsignedIntField]:
        if instance is None:
            return self
        # Unpack langsung dari buffer tanpa membuat copy string/bytes baru
        return struct.unpack_from(">I", instance.buffer, self.offset)[0]

    def __set__(self, instance: Any, value: int) -> None:
        struct.pack_into(">I", instance.buffer, self.offset, value)

class FloatField:
    """Descriptor untuk membaca float (32-bit) langsung dari memoryview offset."""
    def __init__(self, offset: int):
        self.offset = offset

    def __get__(self, instance: Any, owner: type | None = None) -> Union[float, FloatField]:
        if instance is None:
            return self
        return struct.unpack_from(">f", instance.buffer, self.offset)[0]

    def __set__(self, instance: Any, value: float) -> None:
        struct.pack_into(">f", instance.buffer, self.offset, value)

class TelemetryPacket:
    """
    Representasi skema biner fixed-size zero-copy:
    - device_id: uint32 (Offset 0)
    - timestamp: uint32 (Offset 4)
    - metric_a:  float32 (Offset 8)
    - metric_b:  float32 (Offset 12)
    Total size: 16 bytes.
    """
    __slots__ = ('buffer',)
    
    device_id = UnsignedIntField(offset=0)
    timestamp = UnsignedIntField(offset=4)
    metric_a = FloatField(offset=8)
    metric_b = FloatField(offset=12)

    TOTAL_SIZE = 16

    def __init__(self, raw_buffer: Union[bytearray, memoryview]):
        # Membungkus buffer ke dalam memoryview
        self.buffer = memoryview(raw_buffer)
        if self.buffer.nbytes != self.TOTAL_SIZE:
            raise ValueError(f"Ukuran buffer tidak valid. Ekspektasi {self.TOTAL_SIZE} byte, terbaca {self.buffer.nbytes}")

def process_stream_zero_copy(stream_payload: bytearray) -> list[tuple[int, float]]:
    """Memecah paket biner gigabita tanpa overhead alokasi string slice."""
    mv = memoryview(stream_payload)
    total_packets = len(mv) // TelemetryPacket.TOTAL_SIZE
    results = []

    for i in range(total_packets):
        start = i * TelemetryPacket.TOTAL_SIZE
        end = start + TelemetryPacket.TOTAL_SIZE
        # Slice memoryview hanya menghasilkan view baru, bukan deep copy data
        packet_view = mv[start:end]
        packet = TelemetryPacket(packet_view)
        results.append((packet.device_id, packet.metric_a + packet.metric_b))

    return results

if __name__ == "__main__":
    # Mensimulasikan data stream masuk sebesar 3 paket (48 bytes)
    mock_payload = bytearray(
        struct.pack(">IIf", 1001, 1699990001, 45.2) + struct.pack(">f", 12.8) +
        struct.pack(">IIf", 1002, 1699990002, 10.5) + struct.pack(">f", 30.0) +
        struct.pack(">IIf", 1003, 1699990003, 99.1) + struct.pack(">f", 0.9)
    )

    aggregated = process_stream_zero_copy(mock_payload)
    print(f"Hasil ekstraksi zero-copy: {aggregated}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform AdTech memproses 120.000 log impression per detik per worker node. Implementasi awal menggunakan standard dynamic class berbasis dictionary (`dict`) dan model threading CPython standar. 

**Gejala Masalah**:
1. *Memory Exhaustion*: Memory footprint mencapai 32 GB dalam waktu 20 menit eksekusi (OOM Killed).
2. *GC Pauses*: Garbage collector Generational Generation-2 memicu latency spike hingga 1.8 detik saat melakukan sweeping siklus referensi, menyebabkan SLA HTTP timeout pada API Gateway downstream.
3. *CPU Throttling*: Threading untuk komputasi analitik terblokir total oleh GIL contention (CPU usage hanya mentok di 100% pada 1 core dari 32 core mesin bare-metal).

#### Arsitektur Solusi
1. **Model Objek Tanpa Dict**: Seluruh domain entity direfaktor menggunakan `__slots__` secara hirarkis, mematikan pembuatan internal `__dict__` dan `__weakref__`.
2. **Deterministic GC Tuning**: Menonaktifkan automatic GC collection (`gc.disable()`) pada path ingestion kritis, diganti dengan sweeping manual terkontrol per batch window off-peak menggunakan `gc.collect(1)`. Siklus referensi dimitigasi dengan `weakref`.
3. **Multiprocessing Zero-Copy Ingestion**: Mengganti dynamic dictionary payloads dengan shared structured arrays memanfaatkan `multiprocessing.shared_memory` untuk mendistribusikan data mentah melintasi 32 worker core tanpa serialization overhead (`pickle`).

```
                              [Ingress Traffic: 120k req/s]
                                            │
                                            ▼
                           +────────────────────────────────+
                           |  Ingress Gateway (uvloop/C)    |
                           +────────────────────────────────+
                                            │
               Raw Bytes Allocation into POSIX Shared Memory (/dev/shm)
                                            │
     ┌──────────────────────────────────────┼──────────────────────────────────────┐
     │                                      │                                      │
     ▼                                      ▼                                      ▼
+──────────────────────────+  +──────────────────────────+  +──────────────────────────+
| Worker 1 (Core 1)        |  | Worker 2 (Core 2)        |  | Worker N (Core N)        |
| - __slots__ Aggregators  |  | - __slots__ Aggregators  |  | - __slots__ Aggregators  |
| - Zero-Copy MemoryView   |  | - Zero-Copy MemoryView   |  | - Zero-Copy MemoryView   |
| - gc.disable() on batch  |  | - gc.disable() on batch  |  | - gc.disable() on batch  |
+──────────────────────────+  +──────────────────────────+  +──────────────────────────+
```

#### Hasil Metrik Produksi:
* **Memory Footprint**: Turun drastis dari 32 GB ke 4.2 GB stabil (penurunan ~86%).
* **P99 Latency**: Turun dari 1.8 detik (GC Pause) ke level flat 45 milidetik.
* **CPU Core Utilization**: Meningkat dari 3.1% (1 dari 32 core) menjadi 94% across all cores.

---

### 9. Trade-offs

| Dimensi Arsitektur | Pendekatan Konvensional (Python Idiomatic) | Pendekatan Ekstrem (Slots, Buffer, Manual GC) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Performance vs Flexibility** | Fleksibel: Objek dapat ditambah atribut secara dinamis saat runtime (`obj.new_attr = val`). | Kaku: `__slots__` melarang penambahan atribut dinamis runtime secara default. | Kecepatan lookup atribut meningkat 20-30%, alokasi memori instance berkurang hingga 60%, namun mengurangi keluwesan monkey patching dan dynamic metadata. |
| **Latency vs Complexity** | Mengandalkan automatic CPython GC. Zero operational code overhead. | Manual GC tuning (`gc.disable()`, `gc.collect(generation)`). | Menghilangkan latency pause p99, namun jika arsitek salah mengidentifikasi cyclic reference, sistem akan mengalami catastrophic memory leak permanen. |
| **Scalability vs Cost** | Horizontal Pod Scaling (menambah replica pod Python kecil). | Scale-up Vertical (Optimasi multiprocessing shared memory di core besar). | Horizontal scaling meningkatkan biaya infrastruktur cloud (network egress, orchestrator management). Shared memory menekan cost infrastruktur namun menuntut penanganan IPC lock dan pointer offset yang kompleks. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1. **Broken Inherited Slots**: Menambahkan `__slots__` pada child class, namun lupa bahwa parent class tidak mendefinisikan `__slots__`. Akibatnya, parent tetap menginstansiasi `__dict__`, menghilangkan keunggulan penghematan memori seluruh hierarki instance.
2. **Mutable Default Argument Memory Leaks**: Menggunakan list/dict sebagai default value fungsi. Nilai tersebut dievaluasi saat modul di-compile, menetap di Heap generasi lama (Generation 2), dan tidak pernah di-cleanup oleh GC.
3. **Ghost References via Closures**: Menangkap referensi objek besar (`self`) di dalam nested function atau lambda yang disimpan pada global event bus, mencegah reference counter turun ke nol.

#### 10.2. Troubleshooting Guide (Memory Leak & CPU Spike)
Jika CPU 100% atau Memory leak terdeteksi di lingkungan produksi:

1. **Sampling Profiling tanpa Restart Service**:
   Gunakan sampling profiler non-intrusif `py-spy` langsung pada PID worker proses:
   ```bash
   py-spy top --pid <PID>
   py-spy dump --pid <PID>
   ```
2. **Analisis Alokasi Memori dengan Tracemalloc**:
   Sisipkan tracking snapshot untuk membedah perbedaan konsumsi line-by-line:
   ```python
   import tracemalloc
   tracemalloc.start(25) # Track 25 frames
   snap1 = tracemalloc.take_snapshot()
   # ... Run suspect transaction workload ...
   snap2 = tracemalloc.take_snapshot()
   
   top_stats = snap2.compare_to(snap1, 'lineno')
   for stat in top_stats[:10]:
       print(stat)
   ```
3. **Mendeteksi Siklus Referensi yang Lolos**:
   Gunakan modul `gc` untuk menginspeksi objek yang terperangkap dalam cycle:
   ```python
   import gc
   gc.set_debug(gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_OBJECTS)
   unreachable = gc.collect()
   print(f"Unreachable objects found: {unreachable}")
   # Periksa gc.garbage untuk melihat objek referensi sirkular
   ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Production Readiness:
- [ ] **Gunakan `__slots__`** pada semua transfer domain entity, DTO, atau event structs yang diinstansiasi > 50.000 kali per lifecycle.
- [ ] **Hindari Metaclass Jika Decorator Cukup**: Jangan menggunakan Metaclass jika problem logic dapat diselesaikan menggunakan Class Decorator atau `__init_subclass__` (PEP 487).
- [ ] **Audit Cyclic Reference**: Pastikan relasi dua arah (seperti parent-child graphs) menggunakan modul `weakref` pada link anak ke induk.
- [ ] **Pilih Struct/Memoryview untuk Biner**: Wajib gunakan `memoryview` dan modul `struct` saat menangani transmisi serialization internal berukuran besar daripada operasi `str`/`bytes` concatenation (`+`).
- [ ] **Set GC Thresholds Berdasarkan Karakteristik Beban Kerja**: Lakukan kalibrasi via `gc.set_threshold(700, 10, 10)` atau disesuaikan dengan volume throughput objek per satuan waktu.
- [ ] **Deterministic Lock-Free Data Handoff**: Terapkan atomic primitives atau concurrency queues tanpa GIL contention saat scaling inter-process.

---

### 12. Hands-on Practice

Buat dan simpan latihan implementasi di folder: `hands-on/m02/`

#### File: `hands-on/m02/advanced_memory_slots.py`
Instruksi: Tulis script demonstrasi komparasi alokasi memori real-time antara standard dynamic class dan slotted class menggunakan `tracemalloc` dan visualisasikan address footprint-nya.

```python
"""
Langkah Praktikum:
1. Jalankan script ini pada command line.
2. Analisis footprint alokasi memori antar implementasi.
"""
import sys
import tracemalloc

class RegularTelemetryEvent:
    def __init__(self, sensor_id: int, reading: float, status: str):
        self.sensor_id = sensor_id
        self.reading = reading
        self.status = status

class OptimizedTelemetryEvent:
    __slots__ = ('sensor_id', 'reading', 'status')
    def __init__(self, sensor_id: int, reading: float, status: str):
        self.sensor_id = sensor_id
        self.reading = reading
        self.status = status

def benchmark_instantiation(cls, iterations: int = 500_000):
    tracemalloc.start()
    tracemalloc.reset_peak()
    
    # Instansiasi koleksi objek
    dataset = [cls(i, float(i) * 1.5, "OPTIMAL") for i in range(iterations)]
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    sample_obj = dataset[0]
    sys_size = sys.getsizeof(sample_obj)
    dict_size = sys.getsizeof(sample_obj.__dict__) if hasattr(sample_obj, '__dict__') else 0
    total_estimated = sys_size + dict_size
    
    print(f"[{cls.__name__}]")
    print(f"  Total Peak RAM Allocated : {peak / 1024 / 1024:.2f} MB")
    print(f"  Per-Instance Size        : {sys_size} bytes (Internal Dict: {dict_size} bytes)")
    print(f"  Total Estimated Per-Obj  : {total_estimated} bytes\n")
    return dataset

if __name__ == "__main__":
    print("Memulai Benchmark Profiling Alokasi Memori...\n")
    data_reg = benchmark_instantiation(RegularTelemetryEvent)
    data_opt = benchmark_instantiation(OptimizedTelemetryEvent)
    
    del data_reg
    del data_opt
```

---

### 13. Exercises

#### Level Easy
Tulis skrip analisis yang memeriksa apakah sebuah class Python tertentu menggunakan `__slots__` atau mengekspos atribut dinamis `__dict__`. Fungsi harus menerima objek sembarang dan mencetak struktur alokasinya.

```python
# Skeleton Kode untuk Diimplementasikan:
from typing import Any

def inspect_object_allocation(target: Any) -> None:
    # IMPLEMENTASIKAN DI SINI
    pass
```
*Solusi Konseptual*: Periksa atribut `hasattr(target, '__dict__')` dan `hasattr(type(target), '__slots__')`.

#### Level Medium
Buat custom descriptor bernama `TypeEnforcedString` yang memvalidasi bahwa nilai yang di-*assign* ke atribut adalah sebuah instance `str` dan panjangnya tidak melebihi batasan tertentu (misal: max 100 karakter). Jika melanggar, lempar exception `TypeError` atau `ValueError`. Validasi harus terjadi secara internal pada hook `__set__`.

```python
class TypeEnforcedString:
    def __init__(self, max_length: int):
        self.max_length = max_length
        self._name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self._name, "")

    def __set__(self, instance: Any, value: Any) -> None:
        # IMPLEMENTASIKAN VALIDASI STRICT DI SINI
        if not isinstance(value, str):
            raise TypeError(f"Field '{self._name}' wajib bertipe str, diterima: {type(value)}")
        if len(value) > self.max_length:
            raise ValueError(f"Field '{self._name}' melebihi batas {self.max_length} karakter")
        instance.__dict__[self._name] = value
```

#### Level Hard
Rancang arsitektur metaclass bernama `ZeroOverheadRegistryMeta` yang mendaftarkan seluruh turunan class ke dalam registry tersentralisasi tanpa memicu pemanggilan manual. Class yang dihasilkan wajib otomatis memvalidasi bahwa semua class turunan memiliki atribut `__slots__` yang didefinisikan. Jika turunan tidak mendefinisikan `__slots__`, gagalkan proses parsing/kompilasi class saat proses importing dengan melempar `TypeError`.

```python
class ZeroOverheadRegistryMeta(type):
    REGISTRY: dict[str, type] = {}

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        # 1. Validasi keberadaan __slots__ jika bukan base class
        if bases and "__slots__" not in namespace:
            raise TypeError(f"Arsitektur Enterprise mewajibkan __slots__ pada sub-class: '{name}'")
        
        # 2. Bangkitkan class
        cls = super().__new__(mcs, name, bases, namespace)
        
        # 3. Daftarkan ke global registry (kecuali root class)
        if bases:
            mcs.REGISTRY[name] = cls
        return cls

# Verifikasi:
class AbstractBaseEntity(metaclass=ZeroOverheadRegistryMeta):
    __slots__ = ()

class ValidOrderEntity(AbstractBaseEntity):
    __slots__ = ('order_id', 'amount')

# Skenario berikut harus melempar TypeError saat runtime loading:
# class InvalidOrderEntity(AbstractBaseEntity):
#     pass
```

---

### 14. Challenge (Tantangan Studi Kasus Kompleks)

**Studi Kasus**: Anda memimpin tim arsitektur pada bank investasi Tier-1. Sistem Order Routing harus mengevaluasi 5.000.000 order per detik. Setiap data order diterima dalam format byte array mentah (binary stream).
Aturan sistem:
1. Tidak diizinkan melakukan decoding string UTF-8 atau instansiasi dictionary untuk field order.
2. Tidak boleh ada alokasi baru pada Heap memory selama proses routing keputusan (harus *zero-allocation loop*).
3. Transaksi routing harus memverifikasi apakah `price` > threshold dan `flag` bernilai valid.
4. Desain sistem menggunakan `memoryview`, `struct`, dan multiprocessing shared memory yang memetakan order buffer melintasi 8 worker core secara lock-free.

*Output yang Diharapkan*: Rancang dokumen arsitektur dan Proof-of-Concept (PoC) Python murni yang membuktikan bahwa rate throughput mencapai target 5 juta evaluasi biner per detik tanpa intervensi GC sweeping (verifikasi via `gc.get_stats()`).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa perbedaan fundamental antara Reference Counting dan Cyclic Garbage Collector pada CPython?**
   * *Jawaban*: Reference counting langsung mendealokasikan objek begitu counter-nya mencapai 0 secara deterministik, namun gagal menangani relasi siklik. Cyclic GC bertugas melakukan sweeping periodik untuk membersihkan objek siklik yang saling mereferensikan satu sama lain di generasi memori (Gen 0, 1, 2).
2. **Kapan alokasi memori sebuah objek dilewatkan dari PyMalloc langsung ke System Malloc?**
   * *Jawaban*: Saat ukuran objek yang dialokasikan melebihi 512 bytes.
3. **Mengapa penambahan atribut `__slots__ = ()` dapat menghemat pemakaian memori RAM?**
   * *Jawaban*: Karena `__slots__` mencegah alokasi internal hash table `__dict__` pada setiap instance objek, menggantikannya dengan struktur array pointer fixed-offset.
4. **Apa implikasi dari keberadaan Global Interpreter Lock (GIL) terhadap arsitektur I/O-bound vs CPU-bound?**
   * *Jawaban*: I/O-bound diuntungkan karena thread CPython melepaskan GIL saat menunggu I/O (seperti network/disk syscall). Sebaliknya, komputasi CPU-bound terhambat karena hanya satu thread yang dapat mengeksekusi bytecode CPython pada satu waktu.
5. **Kapan fungsi `__set_name__` pada descriptor protocol dipanggil oleh CPython?**
   * *Jawaban*: Dipanggil secara otomatis pada saat class owner sedang dibuat (saat class creation phase), memberikan informasi nama atribut class ke descriptor instance.

#### Intermediate (5 Pertanyaan)
6. **Bagaimana mekanisme kerja Specializing Adaptive Interpreter (PEP 659) pada Python 3.11+?**
   * *Jawaban*: Interpreter memantau kestabilan tipe data pada tiap instruksi bytecode saat runtime. Jika instruksi bersifat monomorfik (tipe operand konsisten), opcode generik digantikan dengan opcode terspesialisasi (inline cache) untuk melompati dynamic type checking overhead.
7. **Mengapa pemanggilan `gc.disable()` sering dijumpai pada framework high-throughput batch worker?**
   * *Jawaban*: Untuk menghindari GC traversal pauses mendadak pada jalur eksekusi kritis. Dealokasi tetap bekerja deterministik melalui reference counting murni selama kode tidak memproduksi siklus referensi.
8. **Jelaskan apa itu Buffer Protocol pada CPython dan bagaimana kaitannya dengan `memoryview`!**
   * *Jawaban*: Buffer protocol adalah level C-API yang memungkinkan objek mengekspos pointer array memori raw-nya secara langsung. `memoryview` adalah wrapper Python di atas protocol ini yang memungkinkan manipulasi slice data tanpa menyalin isi buffer di RAM (*zero-copy*).
9. **Apa bahaya dari mendefinisikan inheritance: `class Derived(Base)` di mana `Derived` menggunakan `__slots__` tetapi `Base` tidak?**
   * *Jawaban*: Penghematan memori menjadi sia-sia karena class `Derived` akan tetap mewarisi dan menginstansiasi alokasi `__dict__` milik class `Base`.
10. **Bagaimana cara kerja Subinterpreters (PEP 684) dalam mengatasi batasan threading model CPython?**
    * *Jawaban*: Subinterpreters memungkinkan adanya multiple interpreter runtime yang terisolasi sepenuhnya di dalam satu proses OS yang sama, di mana setiap interpreter memiliki GIL sendiri sehingga mampu mengeksekusi komputasi Python murni secara konkuren di multi-core.

#### Skenario Kasus Produksi (3 Pertanyaan Kasus)
11. **Kasus 1**: Sistem financial data streaming Anda mengalami lonjakan latency P99 dari 20ms ke 2.500ms setiap 30 detik. Profiler menunjukkan lonjakan terjadi saat sweep Generasi 2 pada modul `gc`. Struktur data apa yang kemungkinan besar menyebabkannya dan bagaimana mitigasi arsitekturalnya?
    * *Analisis Solusi*: Sistem menimbun ratusan ribu objek container (`dict` atau `list`) yang saling merujuk (cyclic reference) sehingga terdorong ke Generation 2 GC. Mitigasi: Ubah container menjadi `__slots__` fixed-size, gunakan `weakref` pada back-reference, atau matikan full sweep dan jadwalkan `gc.collect(1)` secara deterministik saat jeda transaksi.
12. **Kasus 2**: Worker microservice Anda membaca file binary 10 GB dari disk. Ketika menggunakan implementasi `data[:1024]` secara repetitif dalam loop, pod di-kill oleh Kubernetes OOM (Out Of Memory). Padahal ukuran pod memory limit adalah 12 GB. Mengapa hal ini terjadi dan bagaimana solusinya?
    * *Analisis Solusi*: Standard slice `bytes` (`data[a:b]`) melakukan alokasi dan deep memory copy dari substring binary baru di heap pada setiap iterasi. Solusi: Gunakan `mv = memoryview(data)` lalu lakukan slice pada `mv[a:b]` yang menghasilkan pointer slicing zero-copy tanpa konsumsi RAM baru.
13. **Kasus 3**: Tim data engineering Anda mengeluhkan bahwa pipeline parallel processing menggunakan `multiprocessing.Pool` justru menghasilkan runtime yang lebih lambat 3x lipat dibanding single-thread saat memproses dataset data-frame NumPy berukuran raksasa. Identifikasi bottleneck utama dan solusi arsitekturnya!
    * *Analisis Solusi*: Bottleneck terjadi pada Inter-Process Communication (IPC). Worker process melakukan serialisasi dan deserialisasi masif via standard `pickle` di atas UNIX pipes. Solusi: Migrasikan passing data buffer ke `multiprocessing.shared_memory.SharedMemory` sehingga seluruh sub-proses mengakses array memori fisik yang sama tanpa biaya copy atau pickle.

---

### 16. Summary

```
                       CPYTHON ARCHITECTURAL RUNTIME
+-------------------------------------------------------------------------+
|  Bytecode Interpretation: PEG Parser -> AST -> CFG -> Opcode Optimizer  |
|  Frame Evaluation: PEP 659 Adaptive Specialization (Inline Caching)     |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
                     CPYTHON MEMORY MANAGEMENT
+-------------------------------------------------------------------------+
|  Small Allocations (<= 512B)  | PyMalloc Engine: Arena (256KB)          |
|                               | -> Pool (4KB) -> Size-Class Block       |
+-------------------------------+-----------------------------------------+
|  Large Allocations (> 512B)   | System Call: OS Standard malloc()       |
+-------------------------------+-----------------------------------------+
|  Deallocation Strategy        | 1. Deterministic Reference Counting     |
|                               | 2. Cyclic Generational Tracing GC       |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
                   ENTERPRISE OPTIMIZATION PRIMITIVES
+-------------------------------------------------------------------------+
|  __slots__                     | Bypasses __dict__, fixed-offset layout |
|  Buffer Protocol / memoryview  | Zero-copy pointer slicing              |
|  Shared Memory / Subinterpreters| Concurrency scaling bypassing GIL     |
+-------------------------------------------------------------------------+
```

Penguasaan internal CPython membedakan perekayasa piranti lunak level pemula dari level prinsipal. Melalui pemahaman cara kerja VM Frame Loop, PyMalloc memory pooling, generational garbage collector, serta teknik eliminasi dynamic hash tables (`__slots__`), sistem enterprise dapat beroperasi dengan konsumsi memori minimum, latensi P99 rendah, dan throughput pemrosesan biner skala tinggi. Pola-pola arsitektural ini membentuk dasar implementasi engine data berkinerja tinggi, distributed backends, dan microservices mission-critical modern.