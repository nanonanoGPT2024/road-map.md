# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kategori** | `02-Programming-Languages` |
| **Kurikulum** | `python` |
| **Bab** | `03` — *Advanced Data Structures & Memory Optimization* |
| **Modul** | `01` — *Struktur Data Lanjutan & Memory Management* |
| **Tingkat Kesulitan** | *Advanced* / Mahir |
| **Prasyarat** | Pemahaman mendalam tentang OOP Python, pointer model, kompleksitas waktu/ruang (Big-O), serta dasar CPython run-time. |
| **Target Persona** | *Backend Engineer*, *Data Platform Engineer*, *High-Performance Computing Specialist*, *Systems Architect*. |
| **Estimasi Waktu Belajar** | 6 - 8 Jam (Teori, Eksplorasi CPython Internals, Hands-on Lab) |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kompetensi terukur untuk:

1. **Menganalisis dan Membedah Arsitektur Memori CPython**: Mengidentifikasi representasi biner objek (`PyObject`), mekanisme alokator berjenjang CPython (*Arenas*, *Pools*, *Blocks*), serta *Small Object Allocator* (PyMalloc).
2. **Mengelola Lifecycle Objek dan Garbage Collection**: Menginspeksi *reference counting*, mendeteksi serta memitigasi *cyclic references* melalui *Tri-color Generational Garbage Collector* (Gen 0, Gen 1, Gen 2).
3. **Mengoptimalkan Struktur Data Tingkat Lanjut**: Mengimplementasikan dan memilih struktur data performa tinggi dari modul `collections` (`deque`, `defaultdict`, `Counter`), `heapq`, `bisect`, dan `array` berdasarkan karakteristik akses memori dan kompleksitas komputasi.
4. **Mereduksi Memory Footprint Ekstrem**: Mengeliminasi overhead `__dict__` dinamis menggunakan `__slots__`, serta mengimplementasikan referensi non-kepemilikan melalui `weakref` guna menghindari *memory leak*.
5. **Melakukan Profiling dan Eliminasi Kebocoran Memori**: Menggunakan *tooling* tingkat produksi (`tracemalloc`, `sys`, `gc`) untuk mendeteksi degradasi memori dan merekayasa struktur data berkapasitas jutaan entri secara deterministik.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Python Sebagai "Pointer-Heavy Graph Engine"

Di dalam bahasa tingkat rendah seperti C atau Rust, deklarasi integer `int x = 42;` mengalokasikan 4 byte langsung pada register CPU atau *stack frame*. Dalam Python (CPython), **semuanya adalah objek heap yang dibungkus oleh pointer**.

```
    C Model:
    Stack/Memory: [ 0x0000002A ]  <-- 4 bytes (Direct value)

    CPython Model:
    Variable 'x' (Name Binding/Pointer)
          │
          ▼
    ┌──────────────────────────────┐
    │          PyObject            │
    ├──────────────────────────────┤
    │ ob_refcnt : 1 (8 bytes)      │
    │ ob_type   : &PyLong_Type (8B)│
    │ ob_size   : 1 (8 bytes)      │
    │ ob_digit  : [42] (4 bytes)   │
    │ ...padding: (4 bytes)        │
    └──────────────────────────────┘ <-- Total: 28 bytes!
```

Sebuah integer sederhana berukuran 28 byte. Sebuah list berisi 1.000.000 integer bukan sekadar blok memori sekuensial dari 1.000.000 angka, melainkan **array dari 1.000.000 pointer 64-bit (8 byte)** yang masing-masing merujuk ke struktur `PyObject` terpisah di heap. Fenomena ini menciptakan masalah *memory fragmentation* dan *cache invalidation* pada CPU L1/L2/L3 cache (dikenal sebagai *pointer chasing*).

### Prinsip Esensial:
1. **Name Binding, Bukan Variabel Tradisional**: Operator `=` tidak menyalin memori; operator tersebut hanya mengikat (*bind*) label ke sebuah alamat memori `PyObject`.
2. **CPython Allocator Bekerja Berlapis**: Python tidak langsung meminta alokasi sistem operasi (`malloc`) untuk objek-objek kecil (≤ 512 bytes), melainkan memotong blok memori internal demi menghindari *system call overhead*.
3. **Pembersihan Bersifat Hibrida**: Deterministik via *Reference Counting* (langsung mati saat referensi = 0), dan Non-deterministik/Periodik via *Generational GC* (hanya untuk mendeteksi siklus circular).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Arsitektur Alokasi Memori CPython (PyMalloc Hierarchy)

```
+====================================================================+
|                         APPLICATION LAYER                          |
|         Python Source Code (Objects: dict, list, int, str)         |
+====================================================================+
                               │
            Objek > 512 bytes? │
               ┌───────────────┴───────────────┐
               │ YES                           │ NO
               ▼                               ▼
    +─────────────────────+        +────────────────────────────────+
    |   Standard C API    |        |        PyMalloc Allocator      |
    |  malloc() / free()  |        |    (Small Object Allocator)    |
    +─────────────────────+        +────────────────────────────────+
               │                                   │
               │                   ┌───────────────┴───────────────┐
               │                   │ Organisasi Memori Internal:   │
               │                   │                               │
               │                   │  Arena (256 KB aligned)       │
               │                   │    ├── Pool (4 KB)            │
               │                   │    │    ├── Block (e.g. 32B)  │
               │                   │    │    ├── Block (32B)       │
               │                   │    │    └── ...               │
               │                   │    └── Pool (4 KB)            │
               │                   └───────────────────────────────┘
               ▼                                   │
+====================================================================+
|                    VIRTUAL MEMORY MANAGER (OS)                     |
|           mmap() / sbrk() / Windows VirtualAlloc()                 |
+====================================================================+
```

### Diagram Siklus Hidup Objek & Generational Garbage Collector

```
[ Inisialisasi Objek Baru ]
            │
            ▼
┌─────────────────────────┐
│     Reference Count     │  ref_cnt == 0  ┌─────────────────────────┐
│     ob_refcnt = 1       │ ─────────────> │ Deallocator (Segera)    │
└─────────────────────────┘                │ Free memory pool/block  │
            │                              └─────────────────────────┘
            │ ref_cnt > 0 tapi terlibat siklus sirkular?
            ▼
┌────────────────────────────────────────────────────────────────────┐
│                  Cyclic Garbage Collector Engine                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   Generation 0 (Objek Baru)                                        │
│   Threshold tercapai -> Scan references, potong siklus tak terjangkau│
│       │                                                            │
│       │ Selamat (Survivors)                                        │
│       ▼                                                            │
│   Generation 1 (Objek Transisional)                                │
│   Threshold tercapai -> Scan Gen 0 + Gen 1                         │
│       │                                                            │
│       │ Selamat (Survivors)                                        │
│       ▼                                                            │
│   Generation 2 (Objek Umur Panjang / Long-lived: Module, Class)    │
│   Threshold tercapai -> Full Collection (Expensive / Stop-the-world│
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur `PyObject` dan `PyVarObject`
Di dalam kode sumber CPython (`Include/object.h`), semua tipe data turunan Python membungkus makro dasar:

```c
typedef struct _object {
    _PyObject_HEAD_EXTRA // Makro untuk tracking linked-list GC
    Py_ssize_t ob_refcnt;
    struct _typeobject *ob_type;
} PyObject;

typedef struct {
    PyObject ob_base;
    Py_ssize_t ob_size; /* Jumlah item untuk objek dinamis (list, tuple) */
} PyVarObject;
```
- `ob_refcnt`: Bilangan bulat 64-bit yang melacak berapa banyak variabel/struktur merujuk ke memori ini.
- `ob_type`: Pointer ke objek tipe (misalnya `PyLong_Type`, `PyList_Type`), yang mendefinisikan metode, ukuran alokasi, dan *function pointer* tabel virtual (*vtable*).

### 2. PyMalloc: Arena, Pool, dan Block
CPython mengelompokkan alokasi objek kecil (1 hingga 512 byte) ke dalam sistem hierarki:
- **Block**: Unit alokasi terkecil. Ukurannya selalu kelipatan 8 atau 16 byte (misalnya: 8, 16, 24, ..., 512 byte). Objek dengan kebutuhan memori 20 byte dialokasikan ke dalam blok 24 byte.
- **Pool**: Kumpulan blok dengan ukuran (*size class*) yang seragam. Berukuran tetap 4 KB (sesuai ukuran *virtual page* OS pada umumnya).
- **Arena**: Alokasi memori heap sebesar 256 KB yang sejajar (*aligned*) pada batas 256 KB, diperoleh langsung dari OS via `malloc()` atau `mmap()`. Satu arena berisi 64 pool.
- **Tujuan Arsitektural**: Mencegah *kernel context switching* akibat pemanggilan `brk()` / `mmap()` berulang untuk objek kecil bertempo singkat.

### 3. Generational Garbage Collector (Tri-Color Marking Modifikasi)
Siklus referensi (seperti `a.b = b; b.a = a`) tidak dapat dibersihkan oleh *Reference Counting* karena nilai `ob_refcnt` minimal bernilai 1 secara permanen.
- Setiap objek kontainer (objek yang bisa memuat referensi lain, seperti `dict`, `list`, `set`, *custom class*) dialokasikan dengan ekstensi header: `PyGC_Head`.
- Python memelihara tiga daftar ganda berantai (*doubly linked lists*): **Gen 0, Gen 1, dan Gen 2**.
- Algoritma melakukan traversal *gc_refs*:
  1. Menyalin nilai `ob_refcnt` ke field sementara `gc_refs`.
  2. Melakukan traversal setiap referensi dalam kontainer dan mendiskon `gc_refs` target sebanyak 1.
  3. Jika setelah traversal suatu objek memiliki `gc_refs == 0`, objek tersebut diidentifikasi sebagai kandidat *unreachable circular reference*.
  4. Objek yang tetap memiliki `gc_refs > 0` dan objek yang dapat dijangkau darinya dipertahankan dan dipromosikan ke generasi berikutnya.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Perbandingan Struktur Data Koleksi Teroptimasi

| Struktur Data | Modul / Primitif | Kompleksitas Waktu (Rata-rata) | Kompleksitas Memori | Kapan Harus Digunakan? |
| :--- | :--- | :--- | :--- | :--- |
| **`list`** | Built-in | Indexing: $O(1)$<br>Append: Amortized $O(1)$<br>Pop/Insert Left: $O(n)$ | Tinggi (Over-allocates array pointer) | Koleksi umum yang jarang dimodifikasi di awal (*head*). |
| **`deque`** | `collections` | Indexing: $O(n)$<br>Append/Pop (Left/Right): $O(1)$ | Menengah (Blok linked-list 64 elemen) | Queue, FIFO, sliding-window buffers, LIFO stack performa tinggi. |
| **`heapq`** | `heapq` (Binary Heap) | Push/Pop: $O(\log n)$<br>Min element: $O(1)$ | Rendah (Berjalan langsung di atas `list` native) | Priority queue, pemrosesan event stream, seleksi k-terbesar/terkecil. |
| **`bisect`** | `bisect` (Binary Search)| Search/Insert index: $O(\log n)$<br>Shift items: $O(n)$ | Minimal (Berjalan di atas list terurut) | Lookup range dinamis, indexing tabel pencarian tetap (*read-heavy*). |
| **`array`** | `array` | Indexing: $O(1)$<br>Append: Amortized $O(1)$ | Sangat Rendah (Blok C-primitif kontinu tanpa `PyObject`) | Pemrosesan jutaan data numerik homogen tanpa ketergantungan NumPy. |

### Mekanisme `__slots__`
Secara default, setiap instansiasi kelas Python memiliki kamus dinamis `__dict__` untuk menyimpan atribut instans. Kamus ini berupa `PyDictObject` yang mengonsumsi minimal ratusan byte untuk mengantisipasi alokasi hash dinamis.
Dengan mendefinisikan `__slots__ = ('attr1', 'attr2')`, CPython:
1. Meniadakan alokasi `__dict__` dan `__weakref__` (kecuali dideklarasikan eksplisit).
2. Menggantikan kamus dinamis dengan struktur array C internal berukuran tetap berbasis *descriptor offset*.
3. Mereduksi penggunaan memori per instans hingga 60% – 80%.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi praktis untuk menganalisis jejak memori (*memory footprint*), mengamati perilaku *cyclic reference*, serta membuktikan efisiensi `__slots__` dan struktur data khusus.

```python
"""
Fundamental Code: Advanced Data Structures & Memory Exploration
File: memory_fundamentals.py
"""

from __future__ import annotations
import sys
import gc
from collections import deque
import heapq
import array

class RegularNode:
    """Node standar menggunakan __dict__ implisit."""
    def __init__(self, value: int) -> None:
        self.value = value
        self.next = None

class SlottedNode:
    """Node teroptimasi menggunakan __slots__ statis."""
    __slots__ = ('value', 'next')

    def __init__(self, value: int) -> None:
        self.value = value
        self.next: SlottedNode | None = None

def analyze_object_footprint() -> None:
    print("=== 1. ANALISIS FOOTPRINT MEMORI DASAR ===")
    empty_list = []
    empty_dict = {}
    empty_deque = deque()
    
    print(f"Size list kosong    : {sys.getsizeof(empty_list)} bytes")
    print(f"Size dict kosong    : {sys.getsizeof(empty_dict)} bytes")
    print(f"Size deque kosong   : {sys.getsizeof(empty_deque)} bytes")

    reg_node = RegularNode(42)
    slot_node = SlottedNode(42)

    # sys.getsizeof(reg_node) HANYA menghitung overhead instance, 
    # TIDAK termasuk dictionary internal instance (__dict__).
    reg_total_size = sys.getsizeof(reg_node) + sys.getsizeof(reg_node.__dict__)
    slot_total_size = sys.getsizeof(slot_node)

    print(f"Regular Node (Instance + __dict__): {reg_total_size} bytes")
    print(f"Slotted Node (Flat layout)        : {slot_total_size} bytes")
    print(f"Penghematan Ruang Memori          : {((reg_total_size - slot_total_size) / reg_total_size) * 100:.2f}%\n")

def demonstrate_cyclic_gc() -> None:
    print("=== 2. ANALISIS DETEKSI SIKLUS (CYCLIC GC) ===")
    gc.collect()  # Flush garbage state awal
    gc.disable()  # Nonaktifkan background auto-GC untuk pengujian manual

    class CycleHolder:
        def __init__(self, name: str) -> None:
            self.name = name
            self.cycle = None

    node_a = CycleHolder("NodeA")
    node_b = CycleHolder("NodeB")
    node_a.cycle = node_b
    node_b.cycle = node_a

    print(f"Ref count node_a awal: {sys.getrefcount(node_a) - 1}")  # Diskon referensi sys.getrefcount

    del node_a
    del node_b

    # Di titik ini, kedua objek tidak dapat dijangkau aplikasi, 
    # namun tetap hidup di heap karena siklus ref_count == 1
    uncollected_before = gc.collect(generation=0)
    print(f"Siklus objek terdeteksi & dieksekusi oleh Gen 0 GC: {uncollected_before} objek")

    gc.enable()  # Kembalikan state default GC
    print()

def demonstrate_fast_primitives() -> None:
    print("=== 3. DATA STRUCTURE SPECIALIZATION ===")
    # Array C homogen vs List of Objects
    c_style_int_array = array.array('i', range(1000))
    py_style_int_list = list(range(1000))

    # Ukuran list hanya menghitung array pointer-nya, belum menghitung objek integer di dalamnya
    total_list_mem = sys.getsizeof(py_style_int_list) + sum(sys.getsizeof(x) for x in py_style_int_list)
    total_array_mem = sys.getsizeof(c_style_int_array)

    print(f"1000 Ints via Primitive Array : {total_array_mem} bytes")
    print(f"1000 Ints via Native List     : {total_list_mem} bytes")
    print(f"Rasio Efisiensi Array:List    : 1 : {total_list_mem / total_array_mem:.1f}\n")

if __name__ == "__main__":
    analyze_object_footprint()
    demonstrate_cyclic_gc()
    demonstrate_fast_primitives()
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari segmen implementasi penting pada Seksi 07:

1. **`__slots__ = ('value', 'next')`**:
   - Menghilangkan pointer bawaan `tp_dictoffset` dari definisi tipe kelas CPython.
   - Mengalokasikan array penunjuk atribut tetap berukuran 2 elemen (16 byte pada sistem 64-bit).
   - Mencegah *arbitrary attribute assignment* dinamis di masa eksekusi (seperti `slot_node.unknown = 10` akan memunculkan `AttributeError`), meningkatkan determinisme integritas objek.
2. **`reg_total_size = sys.getsizeof(reg_node) + sys.getsizeof(reg_node.__dict__)`**:
   - `sys.getsizeof(obj)` merupakan pemanggilan fungsi C *shallow* (`tp_basicsize` + `tp_itemsize * ob_size`).
   - Objek berbasis kelas reguler memiliki pointer ke kamus atribut terpisah (`__dict__`). Untuk membaca kapasitas riil, memori kamus atribut wajib diikutsertakan.
3. **`gc.disable()` & `gc.collect(generation=0)`**:
   - Menghentikan pembersihan otomatis sementara agar metrik pembersihan siklus isolasi dapat diuji.
   - Objek siklis `node_a` dan `node_b` yang kehilangan referensi dari *root namespace* langsung diidentifikasi oleh parser `Gen 0` menggunakan teknik tracing *decrement-and-sweep*.
4. **`c_style_int_array = array.array('i', range(1000))`**:
   - Tipe specifier `'i'` menginstruksikan CPython untuk mengalokasikan array bertipe primitif `signed int` (4 bytes per entitas) secara padat dan berurutan (*contiguous buffer*).
   - Menghapus overhead 28 byte yang biasanya menempel pada setiap instans `PyObject` bertipe int, menaikkan performa traversal CPU L1/L2 cache secara drastis.

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi: Sistem Rate Limiting & Aggregator Metrik Real-Time

**Masalah**: Sebuah sistem API Gateway berbasis microservices memproses 100.000 request per detik. Arsitektur harus melacak pola perilaku client dalam *sliding-window* 60 detik untuk mendeteksi *distributed abuse* dan menghitung metrik percentil latensi (P99, P50).
Implementasi awal menggunakan struktur Python bawaan:
- Menyimpan history request berupa `list` berisi tuple `(timestamp, latency)`.
- Menggunakan `list.pop(0)` untuk membuang metrik kadaluarsa di luar jendela 60 detik.
- Menghitung percentile dengan memanggil fungsi `sorted()` setiap metrik diminta.

**Dampak Kegagalan Produksi**:
1. Pemanggilan `list.pop(0)` beroperasi pada kompleksitas $O(n)$, memicu *CPU spikes* parah akibat *memory relocation* jutaan elemen pointer di memori heap CPython.
2. Ukuran memori melambung tinggi (> 12 GB RAM) karena *memory over-allocation* pada resizing list dan retensi referensi siklis dari instans error context.
3. GC Gen 2 sering melakukan *stop-the-world pauses*, menyebabkan latency p99 API gateway melonjak melebihi 2.500 ms.

**Solusi Arsitektural**:
- Mengimplementasikan `collections.deque(maxlen=K)` untuk membatasi ukuran memori secara ketat dengan alokasi buffer tetap serta operasi push/pop kiri-kanan $O(1)$.
- Menggunakan `heapq` untuk memelihara top-k request terburuk secara streaming ($O(\log k)$).
- Menghapus atribut dinamis dengan `__slots__` pada event payload wrapper.
- Mengatur ambang batas dan eksekusi GC secara terprediksi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah kode produksi untuk engine *Metric Collector & Sliding-Window Rate Limiter*:

```python
"""
Production Module: Low-Latency High-Throughput Metric Collector & Rate Limiter
File: metrics_engine.py
"""

from __future__ import annotations
import time
import sys
import gc
from collections import deque
import heapq
from typing import NamedTuple, List, Optional, Tuple

class MetricEvent:
    """Representasi payload metrik ultra-ringan tanpa overhead dynamic dictionary."""
    __slots__ = ('timestamp', 'latency_ms', 'status_code')

    def __init__(self, timestamp: float, latency_ms: float, status_code: int) -> None:
        self.timestamp = timestamp
        self.latency_ms = latency_ms
        self.status_code = status_code

    def __lt__(self, other: MetricEvent) -> bool:
        # Dibutuhkan oleh heap ordering
        return self.latency_ms < other.latency_ms

class SlidingWindowBuffer:
    """
    Koleksi metrik bounded berbasis ring/deque buffer.
    Menjamin operasi Append dan Eviction selalu O(1) konstan tanpa alokasi memori berlebih.
    """
    __slots__ = ('max_window_sec', 'events', '_capacity')

    def __init__(self, max_window_sec: float, capacity: int = 100_000) -> None:
        self.max_window_sec = max_window_sec
        self._capacity = capacity
        # Bounded deque mencegah memory unbounded growth
        self.events: deque[MetricEvent] = deque(maxlen=capacity)

    def record_event(self, latency_ms: float, status_code: int) -> None:
        now = time.monotonic()
        # Amortized O(1) push; jika melebihi batas, elemen tertua dibuang otomatis dari kiri di level C
        self.events.append(MetricEvent(now, latency_ms, status_code))

    def purge_expired(self, current_time: float) -> int:
        """Membersihkan elemen yang keluar dari window waktu dengan O(k) di mana k = elemen kedaluwarsa."""
        evicted = 0
        threshold = current_time - self.max_window_sec
        # Akses elemen paling kiri secara konstan
        while self.events and self.events[0].timestamp < threshold:
            self.events.popleft()
            evicted += 1
        return evicted

class LatencyTracker:
    """
    Melacak Top-K transaksi terlambat menggunakan bounded min-heap.
    Kapasitas memory dijamin O(K).
    """
    __slots__ = ('k', 'heap')

    def __init__(self, k: int = 10) -> None:
        self.k = k
        self.heap: List[Tuple[float, float]] = []  # Menyimpan tuple: (latency_ms, timestamp)

    def push_latency(self, latency_ms: float, timestamp: float) -> None:
        if len(self.heap) < self.k:
            heapq.heappush(self.heap, (latency_ms, timestamp))
        else:
            # Jika latensi lebih besar dari elemen terkecil di Top-K saat ini, gantikan
            if latency_ms > self.heap[0][0]:
                heapq.heapreplace(self.heap, (latency_ms, timestamp))

    def get_top_k(self) -> List[Tuple[float, float]]:
        """Mengembalikan metrik top-k terurut dari terkecil ke terbesar."""
        return sorted(self.heap, reverse=True)

class PerformanceTelemetryEngine:
    """Fasad Orkestrasi Pemrosesan Metrik."""
    def __init__(self, window_sec: float = 60.0) -> None:
        self.buffer = SlidingWindowBuffer(max_window_sec=window_sec)
        self.top_slow_requests = LatencyTracker(k=5)

    def ingest(self, latency_ms: float, status_code: int) -> None:
        now = time.monotonic()
        self.buffer.record_event(latency_ms, status_code)
        self.top_slow_requests.push_latency(latency_ms, now)

    def run_maintenance_cycle(self) -> dict:
        now = time.monotonic()
        purged = self.buffer.purge_expired(now)
        return {
            "purged_records": purged,
            "active_window_size": len(self.buffer.events),
            "top_slow_events": self.top_slow_requests.get_top_k()
        }

if __name__ == "__main__":
    import random

    print("=== SIMULASI STREAMING 200.000 METRIK DENGAN LOW MEMORY FOOTPRINT ===")
    engine = PerformanceTelemetryEngine(window_sec=2.0)

    # Catat jejak awal GC
    gc.collect()
    start_time = time.perf_counter()

    for idx in range(200_000):
        # Bangkitkan payload acak
        latency = random.uniform(5.0, 450.0)
        status = 200 if latency < 400.0 else 504
        engine.ingest(latency_ms=latency, status_code=status)

        # Simulasi maintenance window berkala tiap 50.000 operasi
        if idx % 50_000 == 0 and idx > 0:
            time.sleep(0.1)  # Simulasi pergeseran waktu
            telemetry = engine.run_maintenance_cycle()
            print(f"Batch {idx} | Aktif: {telemetry['active_window_size']} items | Dihapus: {telemetry['purged_records']}")

    elapsed = time.perf_counter() - start_time
    print(f"\nSelesai memproses 200.000 event dalam {elapsed:.4f} detik.")
    print(f"Throughput: {200_000 / elapsed:.2f} events/detik")
    print(f"Top 5 Latency Terburuk (ms): {engine.top_slow_requests.get_top_k()}")
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Karakteristik Struktur Data

```
              Memori Rendah
                   ▲
                   │     ● array.array
                   │
                   │     ● Slotted Classes
                   │
                   │               ● deque
                   │     ● list
                   │
                   │                      ● dict / Regular Class
                   └────────────────────────────────────────► Fleksibilitas Tinggi
```

| Struktur Data | Keunggulan Utama | Titik Kelemahan | Trade-off Arsitektural |
| :--- | :--- | :--- | :--- |
| **`list`** | Cache locality CPU bagus saat membaca sekuensial, $O(1)$ random index access. | Expensive resizing overhead, $O(n)$ pemotongan dari head/awal array. | Lebih baik untuk data statis atau read-intensive ketimbang data streaming. |
| **`deque`** | $O(1)$ push dan pop dari kedua ujung tanpa memindahkan array, alokasi per blok. | Random indexing memakan $O(n)$, overhead traversing pointer per blok 64 elemen. | Sangat optimal untuk queue, stack, dan windowing; buruk untuk arbitrary access lookup. |
| **`heapq`** | Menghindari full sorting $O(n \log n)$; pencarian min/max konstan $O(1)$. | Tidak mendukung operasi perombakan prioritas arbitrary tanpa rebuild heap ($O(n)$). | Ideal untuk scheduling dan streaming top-k, tidak cocok untuk frequent priority updates. |
| **`__slots__`** | Mereduksi RAM hingga >60%, mencegah penambahan atribut sembarangan. | Memutus *multiple inheritance* jika ada konflik tata letak slot, menonaktifkan `__dict__`. | Sangat baik untuk DTO / high-volume data instances; membatasi metaprogramming dinamis. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Perangkap Shallow vs Deep Memory Sizing
Fungsi `sys.getsizeof()` tidak menelusuri isi kontainer secara rekursif:
```python
import sys
nested = [[1, 2, 3], {4, 5, 6}, "a long string to allocate memory"]
print(sys.getsizeof(nested))  # Output: Hanya ~80 bytes (overhead pointer list utama saja!)
```
*Solusi*: Gunakan custom recursive function dengan penanganan circular reference tracing atau gunakan `tracemalloc`.

### 2. Slicing Memori Menggandakan Alokasi Heap
Operasi slice pada list atau bytes menduplikasi memori:
```python
large_buffer = bytearray(100 * 1024 * 1024) # 100 MB
slice_part = large_buffer[0:50 * 1024 * 1024] # Mengalokasikan 50 MB BARU
```
*Mitigasi*: Manfaatkan `memoryview` untuk zero-copy buffer manipulation:
```python
view = memoryview(large_buffer)
slice_part = view[0:50 * 1024 * 1024] # 0 byte alokasi baru, hanya membagi pointer slice C
```

### 3. Modifikasi Objek Selama Iterasi
Mengubah kapasitas internal `dict` atau `list` saat dilakukan iterasi memicu `RuntimeError`:
```python
data = {i: i for i in range(10)}
for k in data:
    if k % 2 == 0:
        del data[k] # RuntimeError: dictionary changed size during iteration
```
*Mitigasi*: Iterasikan *keys list view* yang terkristalisasi: `for k in list(data.keys()): ...`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menggunakan `list.pop(0)` Sebagai Antrean (FIFO)
```python
# KODE SALAH (Menyebabkan CPU bottleneck akibat shifting seluruh elemen C)
queue = []
for i in range(100_000):
    queue.append(i)
while queue:
    item = queue.pop(0) # O(N) operasi copy memory shift ke kiri!
```
```python
# KODE BENAR (Menggunakan Double Ended Queue)
from collections import deque
queue = deque()
for i in range(100_000):
    queue.append(i)
while queue:
    item = queue.popleft() # O(1) konstan operasi pointer unlinking
```

### Anti-Pattern 2: Memory Leak Tersembunyi via Modul-Level Closure / Global Cache
```python
# KODE SALAH: Cache membesar tanpa batas dan menahan referensi objek
CACHE = {}
def get_user_profile(user_id: int):
    if user_id not in CACHE:
        CACHE[user_id] = fetch_massive_user_record(user_id) # Objek tidak pernah dibebaskan
    return CACHE[user_id]
```
```python
# KODE BENAR: Manfaatkan bounded LRU Cache atau WeakValueDictionary
from functools import lru_cache

@lru_cache(maxsize=10_000)
def get_user_profile(user_id: int):
    return fetch_massive_user_record(user_id)
```

### Anti-Pattern 3: Mutable Default Parameter Menyimpan State Antar Instance
```python
# KODE SALAH: list dialokasikan sekali saat runtime kompilasi fungsi
def append_worker_task(task_id: int, task_list: list = []):
    task_list.append(task_id)
    return task_list
```
```python
# KODE BENAR
def append_worker_task(task_id: int, task_list: list | None = None):
    if task_list is None:
        task_list = []
    task_list.append(task_id)
    return task_list
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Typing Komprehensif dengan Immutability Hint**:
   Terapkan `typing.Sequence` atau `typing.Mapping` untuk input read-only, mencegah mutasi yang tidak diinginkan pada struktur internal.
2. **Definisikan `__slots__` pada Semua DTO (Data Transfer Object)**:
   Di layer parsing (seperti serialization log, DB row parsing, JSON deserializer), gunakan `__slots__` atau `typing.NamedTuple` untuk menekan alokasi heap jutaan record.
3. **Posisikan GC Sesuai Beban Kerja (Tuning Garbage Collector)**:
   Pada aplikasi batch pipeline bervolume tinggi, lakukan penyesuaian threshold:
   ```python
   # Default CPython: (700, 10, 10)
   # Optimasi untuk batch besar: Kurangi frekuensi full scan Gen 2
   gc.set_threshold(50_000, 50, 25)
   ```
4. **Isolasi Mutasi Shared State Menggunakan Non-blocking Buffers**:
   Gunakan struktur data atomik atau `queue.SimpleQueue` jika memindahkan referensi antar-thread.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Tracing Memory Allocation Menggunakan `tracemalloc`
Modul `tracemalloc` memetakan jejak alokasi langsung ke nomor baris kode Python:

```python
import tracemalloc

tracemalloc.start()
snapshot_before = tracemalloc.take_snapshot()

# Blok eksekusi target
heavy_allocation = [dict(id=i, val=str(i)) for i in range(100_000)]

snapshot_after = tracemalloc.take_snapshot()
top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

print("[Top 3 Memory Allocators]")
for stat in top_stats[:3]:
    print(stat)
```

### 2. Eliminasi Indirection: `__slots__` vs Plain Class vs Tuple vs Dict

| Tipe Entitas | Ukuran Riil (1 Juta Objek Seragam) | Waktu Alokasi (1 Juta Objek) |
| :--- | :--- | :--- |
| **Standard Class (`__dict__`)** | ~152 MB | ~0.42 detik |
| **`__slots__` Class** | ~48 MB | ~0.24 detik |
| **`namedtuple`** | ~48 MB | ~0.31 detik |
| **Primitif `tuple`** | ~40 MB | ~0.15 detik |

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah Algorithmic Complexity Attacks (Hash DoS)
Kamus Python (`dict`) bergantung pada fungsi hashing CPython `SipHash-2-4` yang menggunakan *random seed per-process* secara otomatis untuk menggagalkan collision attack. Namun, jika Anda menerima data eksternal yang diurai langsung menjadi *nested recursive dictionaries*, perhatikan batas kedalaman deserialisasi untuk menghindari stack overflow di layer parser CPython:

```python
import sys
# Batasi recursion depth untuk mencegah Segfault di C-stack
sys.setrecursionlimit(1500)
```

### 2. Membatasi Unbounded In-Memory Queues
Penggunaan `collections.deque` atau `queue.Queue` tanpa parameter `maxlen` atau `maxsize` pada aplikasi penerima request jaringan rentan terhadap serangan Denial of Service (DoS) berbasis *Out-Of-Memory (OOM)*.

```python
# RENTAN: Membuka celah Memory Exhaustion
unbounded_queue = deque()

# TERPROTEKSI: Membatasi jejak memori secara deterministik
bounded_queue = deque(maxlen=50_000)
```

### 3. Mengamankan Destruktor Objek (`__del__`)
Hindari meletakkan logika krusial (seperti menutup koneksi jaringan atau transaksi DB) di dalam metode `__del__`. Objek yang berada di dalam *uncollectable cycle* (pada Python < 3.4 atau jika thread mengalami sudden death) dapat menyebabkan penutupan resource terhambat atau memicu eksekusi *resurrection* yang berbahaya.
Gunakan idiom context manager (`with` statement) untuk deterministic resource release.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Berikut skrip diagnostik untuk menginspeksi status heap dan mengidentifikasi kandidat memory leak pada proses yang sedang berjalan:

```python
"""
Observability Module: Runtime Memory Diagnostics
File: memory_diagnostics.py
"""

from __future__ import annotations
import gc
import sys
from typing import Dict, Any

def inspect_heap_population() -> Dict[str, int]:
    """Menghitung distribusi jumlah instance per tipe objek yang aktif di heap."""
    type_counts: Dict[str, int] = {}
    
    # Traverse seluruh objek yang dipantau oleh Cyclic GC
    for obj in gc.get_objects():
        obj_type = type(obj).__name__
        type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
        
    return dict(sorted(type_counts.items(), key=lambda item: item[1], reverse=True)[:10])

def inspect_generational_gc_metrics() -> Dict[str, Any]:
    """Mengekstrak telemetri internal CPython GC engine."""
    counts = gc.get_count()
    thresholds = gc.get_threshold()
    stats = gc.get_stats()
    
    return {
        "current_generation_counts": {
            "gen0": counts[0],
            "gen1": counts[1],
            "gen2": counts[2]
        },
        "thresholds": {
            "gen0_threshold": thresholds[0],
            "gen1_threshold": thresholds[1],
            "gen2_threshold": thresholds[2]
        },
        "collections_history": {
            "gen0_collections": stats[0]["collections"],
            "gen1_collections": stats[1]["collections"],
            "gen2_collections": stats[2]["collections"]
        }
    }

if __name__ == "__main__":
    print("Top 10 Objek di Heap Saat Ini:")
    for type_name, count in inspect_heap_population().items():
        print(f" - {type_name:<20}: {count} instances")

    print("\nStatus Telemetri Mesin GC:")
    print(inspect_generational_gc_metrics())
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Aturan Emas Memory Optimization CPython
1. **Gunakan struktur data yang tepat**:
   - Butuh FIFO Queue? $\rightarrow$ `collections.deque` (Hindari `list.pop(0)`).
   - Butuh Top-K atau Min/Max stream? $\rightarrow$ `heapq` (Hindari sort berulang).
   - Butuh Array numerik padat? $\rightarrow$ `array.array` (Hindari `list` of `int`).
   - Butuh ratusan ribu instans kelas? $\rightarrow$ Deklarasikan `__slots__`.
2. **Pahami Batasan Ukuran**:
   - `sys.getsizeof()` bersifat *shallow*.
   - Gunakan `tracemalloc` untuk pengukuran riil berbasis snapshot heap.
3. **Lifecycle Aturan Memori**:
   - *Reference count* mencapai 0 $\rightarrow$ Objek langsung dideallokasi seketika.
   - Terjadi siklus referensi (*circular loop*) $\rightarrow$ Menunggu Tri-Color Garbage Collector bekerja pada Gen 0/1/2.
4. **Hindari Memory Duplication**:
   - Gunakan `memoryview` untuk zero-copy slicing terhadap data bytes/buffer besar.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman teknis Anda. Jawab pertanyaan berikut secara mandiri sebelum meninjau kunci jawaban.

### Soal Pemahaman Konsep (Basic)
1. Apa perbedaan mendasar antara alokasi memori sebuah integer pada bahasa C murni dengan objek integer pada CPython?
2. Mengapa pemanggilan `list.pop(0)` memiliki kompleksitas waktu $O(n)$, sedangkan `collections.deque.popleft()` bernilai $O(1)$?
3. Sebutkan dua keuntungan utama penggunaan `__slots__` pada kelas Python!
4. Bilamana sebuah objek dihapus secara deterministik seketika itu juga tanpa menunggu eksekusi Garbage Collector?
5. Mengapa pemanggilan `sys.getsizeof([1, 2, 3])` memberikan hasil yang berbeda jauh dari perkiraan jika kita menjumlahkan ukuran seluruh elemen integer di dalamnya?

### Soal Analisis Lanjutan (Intermediate)
6. Diberikan skenario: Dua objek instans kelas saling merujuk satu sama lain (`a.ref = b` dan `b.ref = a`). Variabel `a` dan `b` kemudian dihapus menggunakan `del a; del b`. Apa yang terjadi pada nilai `ob_refcnt` dari kedua objek tersebut dan bagaimana memori mereka akhirnya dibebaskan?
7. Mengapa array bertipe primitif `array.array('d', [1.0] * 1_000_000)` mengonsumsi memori jauh lebih sedikit dibanding list standar `[1.0] * 1_000_000`?
8. Bagaimana implementasi algoritma *Tri-color Marking* modifikasi CPython mendeteksi siklus tanpa melakukan scanning ke seluruh virtual address space OS?
9. Apa potensi risiko performa yang dapat terjadi jika Anda memanggil `gc.collect(generation=2)` secara berkala pada aplikasi dengan beban request IO tinggi?
10. Bagaimana `memoryview` mengeliminasi *allocation overhead* saat Anda harus memecah buffer data jaringan berukuran 100 MB ke dalam beberapa segmen pemrosesan?

---

### KUNCI JAWABAN & PEMBAHASAN LENGKAP

1. **Jawaban**: Di C, integer dialokasikan langsung sebesar 4 byte (32-bit) atau 8 byte (64-bit) pada stack/register tanpa metadata tambahan. Di CPython, integer merupakan instans `PyObject` (`PyLongObject`) di heap yang membungkus tiga metadata: pencacah referensi (`ob_refcnt`, 8 byte), pointer tipe objek (`ob_type`, 8 byte), serta ukuran digit (`ob_size`, 8 byte) plus array digit nilainya, sehingga menghasilkan konsumsi memori minimal 28 byte.
2. **Jawaban**: `list` pada CPython diimplementasikan secara internal sebagai *contiguous dynamic array of pointers*. Membuang elemen pertama indeks 0 mengharuskan seluruh $n-1$ pointer berikutnya digeser ke kiri sejauh satu alamat memori via operasi `memmove()`, menjadikannya $O(n)$. Sementara `deque` menggunakan struktur *doubly linked-list of blocks* (blok array 64 elemen). Operasi `popleft()` hanya memindahkan pointer baca di blok terdepan atau menghapus blok kosong pertama, bernilai konstan $O(1)$.
3. **Jawaban**: Pertama, meniadakan kamus atribut instans dinamis `__dict__` sehingga menghemat memori antara 60% hingga 80% per instans. Kedua, mempercepat akses baca/tulis atribut karena akses data dialihkan menggunakan offset pointer C tetap (*descriptor layout*) alih-alih melakukan *hash-table lookup*.
4. **Jawaban**: Objek dibebaskan seketika (deterministik) saat *Reference Counting* (`ob_refcnt`) menyentuh angka 0 secara langsung akibat variabel keluar dari *scope*, di-`del`, atau atributnya di-rebind, tanpa perlu campur tangan cyclic Garbage Collector.
5. **Jawaban**: Karena `sys.getsizeof()` melakukan pengukuran *shallow*. Pada struktur kontainer seperti `list`, yang dihitung hanyalah struktur internal array list itu sendiri (header list + kumpulan slot pointer 8-byte ke setiap elemen), bukan representasi ukuran objek `PyObject` yang ditunjuk oleh pointer tersebut.
6. **Jawaban**: Saat `del a` dan `del b` dieksekusi, referensi dari *local namespace* terputus, tetapi nilai `ob_refcnt` masing-masing objek tetap bernilai 1 karena referensi silang internal. Objek menjadi *unreachable* (terisolasi). Objek-objek ini tidak langsung dibebaskan sampai Garbage Collector Generasional (Gen 0/1/2) memicu siklus pemindaian, mendeteksi *dead cycle* melalui simulasi dekremen pointer internal, dan membebaskannya secara kolektif.
7. **Jawaban**: List standar menyimpan $1.000.000$ pointer 64-bit yang masing-masing merujuk ke $1.000.000$ objek `PyFloatObject` terpisah di heap, memicu overhead pointer dan header objek individual. Sementara `array.array('d', ...)` mengalokasikan satu blok memori kontinu tunggal berisi nilai *primitive double precision floating-point* C murni (masing-masing tepat 8 byte padat tanpa header `PyObject`).
8. **Jawaban**: CPython GC tidak melakukan scan ke seluruh memori fisik/virtual OS, melainkan hanya menelusuri rantai *doubly-linked list* internal (`PyGC_Head`) yang secara khusus hanya mendaftarkan objek-objek bertipe kontainer (`dict`, `list`, `tuple`, *custom objects*) yang dialokasikan di Python heap. Objek primitif murni seperti `int` atau `str` tidak dimasukkan ke dalam rantai pemantauan GC.
9. **Jawaban**: Gen 2 GC berisi objek dengan umur terpanjang (*long-lived objects*). Memindai Gen 2 memicu *Full Collection* yang melakukan validasi ke seluruh objek kontainer yang ada di memori aplikasi. Operasi ini menghentikan eksekusi thread (*Stop-the-world pause*) secara signifikan, yang berakibat langsung pada lonjakan *latency spike* (P99/P99.9) pada aplikasi responsif real-time.
10. **Jawaban**: Menggunakan `memoryview` membuat representasi objek yang mengekspos C-*Buffer Protocol*. Operasi slicing pada `memoryview` hanya membuat deskriptor pointer C baru yang mencatat *offset*, panjang (*length*), dan *stride* dari buffer asli yang sudah ada, tanpa menduplikasi alokasi array byte sebesar segmen tersebut di heap (*zero-copy operation*).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Memory-Bounded High-Speed LRU Cache Engine dengan Hard Quota Enforcement"

### Deskripsi Masalah
Banyak aplikasi web mengalami kegagalan memori (OOM Crashes) karena menggunakan cache internal yang tidak memiliki batas kapasitas memori yang tegas (*hard memory quota*). Mengandalkan `maxsize` (jumlah item) pada `functools.lru_cache` sering kali tidak memadai karena ukuran data tiap item bisa bervariasi (misalnya: variasi ukuran JSON dari 1 KB hingga 20 MB).

### Spesifikasi Teknis Proyek
Bangun modul independen bernama `bounded_lru.py` yang mengimplementasikan sistem cache dengan ketentuan:
1. **Batas Memori Absolut**: Cache tidak hanya dibatasi oleh jumlah item, melainkan oleh kuota byte total (contoh: batas maksimum 50 MB).
2. **Karakteristik Kompleksitas**:
   - Lookup data: $O(1)$ amortized.
   - Ingestion data: $O(1)$ amortized.
   - Eviction data terlama (LRU): $O(1)$.
3. **Mekanisme Eviction**: Jika penambahan item baru menyebabkan total estimasi memori heap cache melampaui kuota, sistem harus secara otomatis melakukan eviksi terhadap item yang paling lama tidak diakses (*Least Recently Used*) hingga memori kembali berada di bawah kuota.
4. **Optimasi Internal**:
   - Node internal antrean wajib menggunakan struktur data berbasis `__slots__`.
   - Menggunakan perpaduan `dict` untuk indexing kunci dan *doubly-linked list* kustom untuk melacak urutan akses tanpa overhead overhead relokasi array.
   - Sediakan integrasi context manager / decorator untuk fungsi-fungsi I/O intensif.

### File Template untuk Memulai

```python
"""
Hands-On Assignment: Memory-Bounded LRU Cache Engine
File: bounded_lru.py
"""

from __future__ import annotations
import sys
from typing import Any, Optional

class CacheNode:
    """Node Doubly-Linked List dengan optimasi memori __slots__."""
    __slots__ = ('key', 'value', 'size_bytes', 'prev', 'next')

    def __init__(self, key: str, value: Any, size_bytes: int) -> None:
        self.key = key
        self.value = value
        self.size_bytes = size_bytes
        self.prev: Optional[CacheNode] = None
        self.next: Optional[CacheNode] = None

class MemoryBoundedLRUCache:
    def __init__(self, max_memory_bytes: int) -> None:
        self.max_memory_bytes = max_memory_bytes
        self.current_memory_bytes = 0
        self._lookup: dict[str, CacheNode] = {}
        
        # Inisialisasi Dummy Sentinel Head & Tail untuk eliminasi edge case pointer
        self._head = CacheNode("__HEAD__", None, 0)
        self._tail = CacheNode("__TAIL__", None, 0)
        self._head.next = self._tail
        self._tail.prev = self._head

    def _estimate_size(self, key: str, val: Any) -> int:
        """
        Kalkulasi estimasi footprint memori (Shallow + Primitive length estimation).
        Lengkapi logika ini secara komprehensif!
        """
        # Implementasikan kalkulasi ukuran key + val + overhead CacheNode
        pass

    def get(self, key: str) -> Optional[Any]:
        # Implementasikan logika pengambilan item & updating recency node ke MRU position
        pass

    def put(self, key: str, value: Any) -> None:
        # 1. Hitung ukuran baru
        # 2. Jika key sudah ada, sesuaikan selisih memori
        # 3. Selama current_memory_bytes + size_baru > max_memory_bytes, lakukan evict LRU (node dekat tail)
        # 4. Tambahkan node baru ke posisi paling depan (head)
        pass

    def current_usage(self) -> tuple[int, int]:
        """Mengembalikan (current_bytes, total_items)."""
        return self.current_memory_bytes, len(self._lookup)

# ==========================================
# VERIFIKASI PRAKTIKUM
# ==========================================
if __name__ == "__main__":
    # Batas ketat: 10 Kilobytes (10 * 1024 bytes)
    cache = MemoryBoundedLRUCache(max_memory_bytes=10 * 1024)
    
    print("[1] Memulai pengujian ingestion cache...")
    # Tulis skenario pengujian di sini:
    # - Tambahkan string payload besar
    # - Pastikan eviksi otomatis terjadi tanpa memicu memory leak
    # - Cetak status pemakaian byte sebelum dan sesudah eviksi
```

### Kriteria Kelulusan Evaluasi (Definition of Done):
- Berhasil mengeksekusi operasi `put()` dan `get()` tanpa ada manipulasi $O(n)$ pencarian list linear.
- Total memori yang tercatat di `current_memory_bytes` tidak pernah melampaui batas `max_memory_bytes` saat dibanjiri jutaan data payload secara berulang.
- Seluruh variabel penampung pointer referensi terbebas dari siklus liar saat penghapusan instans cache. Divalidasi menggunakan modul `gc.collect()`.