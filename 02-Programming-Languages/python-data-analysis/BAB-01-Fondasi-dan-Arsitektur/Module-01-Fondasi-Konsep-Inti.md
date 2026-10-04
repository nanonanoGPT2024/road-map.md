# Bab 01 Module 01: Arsitektur Komputasi Numerik Python, Memory Layout, dan Vektorisasi Data

---

### 1. Learning Objectives
*   Menganalisis overhead memori struktural dari CPython primitives (`PyObject`) dibandingkan dengan contiguous memory buffers.
*   Mengidentifikasi perbedaan mekanis antara traversal pointer berbasis linked/reference list dengan memory access pattern berbasis stride.
*   Mengimplementasikan operasi numerik berbasis vektorisasi SIMD (Single Instruction, Multiple Data) untuk mengeliminasi overhead CPython interpreter loop.
*   Mengukur dampak CPU cache hierarchy (L1, L2, L3 cache lines) terhadap performa pembacaan array multidimensi (C-contiguous vs Fortran-contiguous).
*   Merancang arsitektur pipeline data ingestion lokal yang memanfaatkan pre-allocated contiguous buffers untuk meminimalkan latensi pemrosesan dan degradasi garbage collector (GC).

---

### 2. Concept Definition
Komputasi numerik dalam Python modern dibangun di atas abstraksi memori berkinerja tinggi yang menggantikan sistem dynamic-typing milik CPython runtime dengan typed, contiguous buffer memory blocks. 

Secara formal, *Data Analysis Engine* (seperti NumPy, Pandas backend) adalah implementasi wrapper C/C++/Fortran di sekitar blok memori mentah yang berurutan. Karakteristik dasarnya ditentukan oleh:
$$\text{Memory Address}(i_0, i_1, \dots, i_k) = \text{Base Address} + \sum_{j=0}^{k} (i_j \times \text{stride}_j)$$
di mana:
*   $\text{Base Address}$ adalah pointer memori mentah segmen data.
*   $\text{stride}_j$ merepresentasikan lompatan byte (*byte offset*) yang dibutuhkan untuk bergeser satu indeks pada dimensi ke-$j$.
*   $i_j$ adalah indeks posisi koordinat tensor/matriks.

---

### 3. Why It Matters
CPython mengorbankan performa komputasi demi fleksibilitas bahasa. Setiap tipe data integer atau float di Python dibungkus (*boxed*) dalam struktur heap CPython yang besar:
*   Objek `int` standar di Python 64-bit memakan alokasi 28 byte di heap, bukan 4 atau 8 byte native memory.
*   Koleksi data native seperti `list` tidak menyimpan data secara contiguous, melainkan menyimpan array of pointers yang mereferensikan instance `PyObject` lain yang tersebar di heap (*pointer indirection*).

```
CPython List:
[ Pointer 0 ] ---> Heap: [ PyObject: Type, RefCount, Value ]
[ Pointer 1 ] ---> Heap: [ PyObject: Type, RefCount, Value ] (Non-contiguous, Cache-Hostile)

Contiguous Buffer (NumPy / Native C-Array):
[ Value 0 | Value 1 | Value 2 | Value 3 ] (Contiguous, Cache-Friendly, SIMD-Enabled)
```

Konsekuensi arsitektural di skala produksi:
1.  **Cache Thrashing:** Pengecekan pointer acak menyebabkan CPU L1/L2 cache misses berulang.
2.  **Interpreter Overhead:** Setiap iterasi loop mengevaluasi tipe data secara dinamis (*dynamic type resolution*), memeriksa global interpreter state, dan menambah/mengurangi reference counter (`ob_refcnt`).
3.  **GC Pressure:** Jutaan entitas `PyObject` membebani cyclic garbage collector Python, memicu jeda eksekusi tak terprediksi (*stop-the-world latency spike*).

---

### 4. What It Is
Arsitektur analisis data berbasis Python memisahkan kontrol layer (Python execution runtime) dari computational layer (BLAS/LAPACK, C, Fortran, dan SIMD machine instructions). Komponen fundamentalnya meliputi:

1.  **Homogeneous Buffer Allocation:** Memori dialokasikan sebagai satu blok contiguous linear array dengan tipe data tunggal fixed-width (misal: `float64`, `int32`), mengeliminasi metadata overhead per elemen.
2.  **Metadata Layer (Strides & Shape):** Dimensi array multidimensi hanyalah ilusi matematis yang diatur oleh metadata:
    *   `shape`: tuple penanda ukuran tiap dimensi, misalnya `(1000, 4)`.
    *   `strides`: tuple penanda jumlah byte yang harus dilewati di memori fisik untuk berpindah ke elemen berikutnya di dimensi tersebut.
3.  **SIMD Execution Vectorization:** Instruksi CPU modern (AVX-512, AVX2, ARM Neon) dapat memproses 4 hingga 8 float 64-bit dalam satu CPU instruction cycle jika data tersusun secara contiguous di memori.

---

### 5. What It Is NOT
*   **Bukan sekadar "menghindari `for` loop":** Menulis `[x * 2 for x in data]` tetap mengeksekusi CPython loop di layer interpreter. Vektorisasi sejati mendelegasikan iterasi ke instruksi mesin level C tanpa intervensi interpreter.
*   **Bukan multi-threading otomatis:** Vektorisasi memanfaatkan paralelisme instruksi level data (SIMD), bukan multithreading berbasis worker thread atau process concurrency.
*   **Bukan substitusi Database Execution Engine:** Operasi in-memory array tidak menggantikan OLAP columnar engine jika data melampaui kapasitas RAM tanpa mekanisme chunking atau out-of-core computing.

---

### 6. How It Works
Saat skrip Python menginisialisasi contiguous array dan menjalankan komputasi:

1.  **Alokasi:** Runtime meminta blok memori melalui `malloc` ke kernel OS. Sistem mengembalikan contiguous virtual address range.
2.  **Buffer Descriptor (`PyBufferProcs` / Array Interface):** Pointer data mentah dibungkus oleh struct Python tipis berisi metadata (`shape`, `strides`, `dtype`).
3.  **Zero-Copy Slicing:** Operasi manipulasi array dasar (seperti `reshape`, slicing, transpose) tidak menyalin data fisik. Operasi ini hanya memodifikasi tuple metadata `strides` dan `shape`, menghasilkan pointer view baru pada offset memori yang sama.
4.  **CPU Cache Line Fetching:** Ketika operasi SIMD dieksekusi, satu operasi pembacaan memori mengambil satu cache-line penuh (umumnya 64 bytes / 8 nilai float-64 berturutan). Ini mencegah L1 data-cache eviction yang tidak diinginkan.

---

### 7. ASCII Architecture / Workflow Diagram

```
+-----------------------------------------------------------------------------------+
|                            APPLICATION LAYER (Python)                             |
|                           array_c = array_a + array_b                             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|               NUMPY / C-EXTENSION RUNTIME DISPATCHER                              |
|   1. Verifikasi Shape, Dtype, dan Memory Flags (C_CONTIGUOUS / ALIGNED)           |
|   2. Bypass Python GIL (Global Interpreter Lock)                                 |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         LOW-LEVEL COMPUTATIONAL KERNEL                            |
|             Hardware Accelerated Kernel (e.g., OpenBLAS / MKL / SIMD)             |
+-----------------------------------------------------------------------------------+
       |                                                              |
       v                                                              v
+------------------------------------+      +---------------------------------------+
|        MEMORY ACCESS PATTERN       |      |             CPU REGISTERS             |
|                                    |      |                                       |
| [Addr 0x00]: Data A [8 Bytes]      |=====>| AVX2/AVX-512 Vector Registers (YMM/ZMM)|
| [Addr 0x08]: Data A [8 Bytes]      |      | Load 4-8 Float64 sekaligus            |
| [Addr 0x10]: Data A [8 Bytes]      |      |                                       |
| [Addr 0x18]: Data A [8 Bytes]      |      | CPU Execution Core: Single Cycle ADD  |
+------------------------------------+      +---------------------------------------+
```

---

### 8. Minimal Reproducible Example
Contoh berikut menunjukkan disparitas memori dan mekanisme *strided memory indexing* tanpa dependensi eksternal selain standard library, kemudian dibandingkan dengan NumPy ndarray memory view.

```python
import sys
import array
import numpy as np

# 1. Alokasi Memori: CPython List of Int vs Standard Library Array vs NumPy Array
sample_size = 1000

python_list = [i for i in range(sample_size)]
c_type_array = array.array('l', [i for i in range(sample_size)])
numpy_array = np.arange(sample_size, dtype=np.int64)

list_element_overhead = sys.getsizeof(python_list) + sum(sys.getsizeof(i) for i in python_list)
c_array_overhead = sys.getsizeof(c_type_array)
numpy_overhead = sys.getsizeof(numpy_array)

print(f"Memory List CPython: {list_element_overhead} bytes")
print(f"Memory Array stdlib: {c_array_overhead} bytes")
print(f"Memory NumPy Array : {numpy_overhead} bytes (termasuk buffer data contiguous)")

# 2. Inspect Memory Strides
matrix = np.arange(12, dtype=np.int32).reshape(3, 4)
print("\n--- Metadata Matriks 3x4 (Int32: 4 bytes per elemen) ---")
print(f"Bentuk (Shape)   : {matrix.shape}")
print(f"Strides Fisik    : {matrix.strides} -> (Lompat {matrix.strides[0]} bytes per baris, {matrix.strides[1]} bytes per kolom)")
print(f"Alamat Base (Hex): {hex(matrix.ctypes.data)}")

# 3. Validasi Strided Byte Offset
row, col = 2, 3
expected_offset = row * matrix.strides[0] + col * matrix.strides[1]
print(f"Offset Kalkulasi Elemen [{row}, {col}]: {expected_offset} bytes dari Base Pointer")
```

---

### 9. Real-World Practical Scenario
Skenario: Pipeline finansial *high-frequency order-book analysis* menerima burst tick order execution. Kita harus menghitung Weighted Average Price (VWAP) secara streaming untuk 10.000 order ticks per window dengan target latensi p99 di bawah 5 milidetik, tanpa memicu overhead alokasi memori GC.

```python
import time
import numpy as np

class HighFrequencyVWAPEngine:
    def __init__(self, capacity: int = 100_000):
        self.capacity = capacity
        # Pre-allocation: Alokasi contiguous buffer satu kali saat bootup
        self.prices = np.empty(capacity, dtype=np.float64)
        self.volumes = np.empty(capacity, dtype=np.float64)
        self.cursor = 0

    def ingest_batch(self, batch_prices: np.ndarray, batch_volumes: np.ndarray) -> None:
        batch_len = len(batch_prices)
        if self.cursor + batch_len > self.capacity:
            # Shift buffer jika kapasitas window penuh (circular buffer sederhana)
            self.prices[:self.cursor - batch_len] = self.prices[batch_len:self.cursor]
            self.volumes[:self.cursor - batch_len] = self.volumes[batch_len:self.cursor]
            self.cursor -= batch_len
            
        # Zero-allocation write langsung ke block contiguous yang sudah ada
        self.prices[self.cursor:self.cursor + batch_len] = batch_prices
        self.volumes[self.cursor:self.cursor + batch_len] = batch_volumes
        self.cursor += batch_len

    def compute_vwap(self, window_size: int) -> float:
        if self.cursor < window_size:
            idx_start = 0
            idx_end = self.cursor
        else:
            idx_start = self.cursor - window_size
            idx_end = self.cursor

        # Slicing menghasilkan Memory View (Zero-copy)
        p_slice = self.prices[idx_start:idx_end]
        v_slice = self.volumes[idx_start:idx_end]

        # Operasi SIMD-vectorized: Dot Product / Sum
        # vwap = sum(price * volume) / sum(volume)
        sum_volume = np.sum(v_slice)
        if sum_volume == 0.0:
            return 0.0
            
        # np.dot dioptimasi via hardware instruction (FMA: Fused Multiply-Add)
        cumulative_turnover = np.dot(p_slice, v_slice)
        return float(cumulative_turnover / sum_volume)

# Eksekusi Simulasi
engine = HighFrequencyVWAPEngine(capacity=500_000)

# Generate synthetic input stream batch (10,000 tick)
np.random.seed(42)
mock_prices = np.random.uniform(100.0, 150.0, size=10_000)
mock_volumes = np.random.uniform(1.0, 50.0, size=10_000)

# Benchmark eksekusi ingest dan compute
start_time = time.perf_counter()
engine.ingest_batch(mock_prices, mock_volumes)
vwap = engine.compute_vwap(window_size=5_000)
latency_ms = (time.perf_counter() - start_time) * 1000

print(f"Hasil Kalkulasi VWAP: {vwap:.4f}")
print(f"Latensi Eksekusi (Ingest + Compute): {latency_ms:.4f} ms")
```

---

### 10. Trade-Off Analysis

| Aspek | CPython Native Primitive (`list` of `dict`/`float`) | Contiguous Numeric Buffer (`numpy.ndarray`) | Apache Arrow (Columnar Buffer) |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | Ekstrem (~28-40 byte overhead per float point). | Minimal (Hanya ukuran native type, misal: 8 byte per `float64`). | Minimal (Zero-copy serialization, fixed-size bitmasks). |
| **Akses Elemen Acak**| Cepat ($O(1)$) tapi menghasilkan cache-miss karena pointer chasing. | Cepat ($O(1)$) via direct stride pointer math; Sangat ramah CPU Cache. | Dioptimasi untuk batch retrieval / columnar scans. |
| **Mutabilitas & Resize**| Sangat fleksibel (Operasi append dinamis berbiaya amortized $O(1)$). | Sangat mahal ($O(N)$ jika perlu resize/realloc block fisik baru). | Immutable secara desain; append membutuhkan batch chunking. |
| **Fleksibilitas Skema**| Heterogeneous (dapat memuat sembarang object Python bersamaan). | Homogeneous (hanya satu tipe data per array buffer). | Homogeneous per kolom; mendukung complex nested structures. |
| **Interoperabilitas**| Terisolasi di CPython VM ecosystem. | Standar de facto Python Data Science (C/C++ runtime bindings). | Lintas bahasa (C++, Rust, Go, Java) tanpa marshalling penalty. |

---

### 11. Anti-Patterns & Common Traps

#### Anti-Pattern 1: Loop Concatenation Memory Leaks / Spikes
Menggunakan `np.append()` di dalam iterasi looping untuk mengumpulkan data stream.

```python
# KODE SALAH (Inisialisasi memori berulang)
import numpy as np
data = np.array([])
for i in range(10_000):
    # Tragedi Performa: Merealokasi dan mengkopi seluruh data berulang kali O(N^2)
    data = np.append(data, float(i))
```

```python
# KODE PERBAIKAN (Pre-allocation atau List Ingestion ke Buffer Tunggal)
import numpy as np
# Solusi A: Pre-allocate jika ukuran batas atas diketahui
size = 10_000
data = np.empty(size, dtype=np.float64)
for i in range(size):
    data[i] = float(i)

# Solusi B: Kumpulkan di standard list dulu, konversi sekali jalan
temp = [float(i) for i in range(size)]
data = np.array(temp, dtype=np.float64)
```

#### Anti-Pattern 2: Implicit Casting via View Manipulation
Melakukan assignment data floating point ke integer array buffer tanpa penanganan eksplisit, menyebabkan pemotongan data (*data truncation*) diam-diam.

```python
# KODE SALAH
arr = np.array([1, 2, 3], dtype=np.int32)
arr[0] = 99.99  # Silently truncated to 99
```

```python
# KODE PERBAIKAN
arr = np.array([1, 2, 3], dtype=np.int32)
new_val = 99.99
# Pastikan casting eksplisit atau gunakan buffer dengan tipe presisi yang benar
arr_float = arr.astype(np.float64)
arr_float[0] = new_val
```

---

### 12. Edge Cases, Failure Modes & Mitigations
1.  **Non-Contiguous Memory Transpose Access:** 
    *   *Failure Mode:* Operasi `matrix.T` (transpose) menghasilkan array *non-contiguous* (F-contiguous alih-alih C-contiguous). Menerapkan operasi SIMD C-based berikutnya pada view ini dapat menyebabkan penurunan throughput 3x-10x akibat cache invalidation.
    *   *Mitigation:* Periksa flag array `arr.flags['C_CONTIGUOUS']`. Jika bernilai `False`, panggil `np.ascontiguousarray(arr)` sebelum memproses komputasi batch berat.
2.  **Integer Overflow Silent Wrapping:**
    *   *Failure Mode:* NumPy mengadopsi native C arithmetic. Tipe `int32` akan mengalami overflow tanpa memicu `OverflowError` dari Python, menyebabkan error aritmatika fatal yang tidak terdeteksi.
    *   *Mitigation:* Aktifkan proteksi runtime melalui `np.seterr(over='raise')` saat memproses operasi agregasi finansial beresiko.

---

### 13. Performance Implications & Benchmarking
Pengujian komputasi: Operasi normalisasi standar $(X - \mu) / \sigma$ pada $10.000.000$ angka *double-precision floating-point*.

```python
import time
import math
import numpy as np

N = 10_000_000
py_data = [float(x) for x in range(N)]
np_data = np.arange(N, dtype=np.float64)

# 1. Native CPython Iterative Loop
start = time.perf_counter()
py_mean = sum(py_data) / N
py_std = math.sqrt(sum((x - py_mean) ** 2 for x in py_data) / N)
py_result = [(x - py_mean) / py_std for x in py_data]
time_py = time.perf_counter() - start

# 2. Vectorized NumPy Execution Engine
start = time.perf_counter()
np_mean = np.mean(np_data)
np_std = np.std(np_data)
np_result = (np_data - np_mean) / np_std
time_np = time.perf_counter() - start

print(f"CPython Execution Time: {time_py:.4f} detik")
print(f"NumPy Execution Time  : {time_np:.4f} detik")
print(f"Speedup Factor        : {time_py / time_np:.2f}x")
```

*Metrik Tipikal (Intel i7/Apple Silicon, RAM 16GB):*
*   CPython Loop: ~3.50 detik.
*   NumPy Vectorized: ~0.04 detik.
*   Speedup: 80x hingga 100x penghematan waktu eksekusi secara konsisten, didukung oleh L3 Cache spatial locality dan integrasi AVX SIMD registers.

---

### 14. Security, Compliance & Governance Considerations
1.  **Buffer Overrun Attacks / Segmentation Fault:** Mengakses layer memori NumPy via ctypes (`numpy.ndarray.ctypes`) membypass memory bounds safety checking milik Python. Kesalahan kalkulasi byte stride dapat membaca unallocated RAM, menyebabkan kebocoran memori kredensial (*memory sniffing*) atau proses mati seketika (*SIGSEGV*).
2.  **Denial of Service (OOM) via Unbounded Allocation:** Dynamic reshaping array yang dikirim lewat payload eksternal (misal: JSON request body) dapat memaksa kernel OS membunuh worker via Linux OOM Killer. 
    *   *Kebijakan:* Terapkan static input bounds limit dan strict allocation quota di API gateway.

---

### 15. Verification, Testing & Static Analysis
Pengujian numerik membutuhkan verifikasi toleransi floating-point presisi tinggi dan determinisme layout buffer.

```python
import numpy as np
import pytest

def test_memory_layout_integrity():
    data = np.arange(20, dtype=np.float32).reshape(4, 5)
    
    # Validasi memory stride invariant (4 bytes per float32)
    assert data.strides == (20, 4), f"Expected strides (20, 4), got {data.strides}"
    assert data.flags['C_CONTIGUOUS'] is True
    
    # Slice tidak boleh menghasilkan alokasi memori baru (harus sharing memory view)
    sub_view = data[1:3, 1:4]
    assert np.shares_memory(data, sub_view) is True

def test_floating_point_stability():
    # Demonstrasi validasi toleransi floating point
    val_a = np.array([0.1 + 0.2], dtype=np.float64)
    val_b = np.array([0.3], dtype=np.float64)
    
    # Assert equality biasa akan gagal karena IEEE-754 representation
    # Salah: assert val_a[0] == val_b[0]
    
    # Verifikasi benar: Gunakan toleransi absolute dan relative
    np.testing.assert_allclose(val_a, val_b, rtol=1e-7, atol=1e-12)
```

---

### 16. Operational Readiness, Monitoring & Observability
Metrik kritis saat mengoperasikan distributed worker node (misal: Celery worker yang menjalankan computational analytics):
1.  **Resident Set Size (RSS) Spike Tracking:** Monitor heap leakage akibat representasi Python list yang tidak dibebaskan GC.
2.  **Buffer Allocation Telemetry:** Gunakan `tracemalloc` untuk membedakan alokasi heap CPython standard vs Native C allocators.

```python
import tracemalloc
import numpy as np

tracemalloc.start()
snapshot_before = tracemalloc.take_snapshot()

# Alokasi NumPy Buffer
buffer = np.zeros((1000, 1000), dtype=np.float64) # ~8MB

snapshot_after = tracemalloc.take_snapshot()
top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

print("[Alokasi Memori Operasional]")
for stat in top_stats[:3]:
    print(stat)
```

---

### 17. Best Practices Checklist
*   [ ] **[Essential]** Hindari iterasi eksplisit (`for`, `while`) di atas instance ndarray/Series; gunakan operasi primitif berbasis vectorized operator.
*   [ ] **[Essential]** Tentukan `dtype` secara eksplisit saat menginisialisasi buffer kosong atau membaca dataset tabular (`float32` vs `float64`) untuk memotong konsumsi memori sebesar 50%.
*   [ ] **[Recommended]** Periksa alignment memori (`arr.flags['C_CONTIGUOUS']`) sebelum memasukkan buffer ke low-level computing routines (CFFI, Cython, atau parallel GPU kernels).
*   [ ] **[Recommended]** Manfaatkan `np.empty()` atau `np.zeros()` untuk *pre-allocation* alih-alih teknik konsolidasi linear dinamis seperti `np.concatenate()` atau `np.append()`.
*   [ ] **[Enterprise]** Konfigurasi memory limits pada sub-process pooling untuk mencegah system-wide thrashing akibat uncoordinated native allocation.

---

### 18. Self-Healing, Debugging & Troubleshooting Runbook

#### Masalah: "Process killed: 137 (OOM Killer) saat melakukan pemrosesan data batch"
1.  **Diagnosa Awal:** Periksa memory footprint sebelum crash. Apakah kode menyalin (*copying*) array alih-alih membuat view?
2.  **Investigasi:** Cek status pointer memori menggunakan helper function:
    ```python
    def check_memory_sharing(arr_base, arr_derived):
        print(f"Base pointer: {hex(arr_base.ctypes.data)}")
        print(f"Derived pointer: {hex(arr_derived.ctypes.data)}")
        print(f"Shares Memory? {np.shares_memory(arr_base, arr_derived)}")
    ```
3.  **Remediasi Masalah Mutasi:**
    *   Jika fungsi Anda berisi instruksi `arr = arr[arr > 0]` (boolean indexing), ketahuilah bahwa operasi filtering ini **selalu** membuat deep copy baru di memori, bukan view.
    *   Ubah alur pemrosesan menggunakan in-place computation mask: `np.putmask(arr, arr <= 0, 0)` atau gunakan library stream chunking (misal: memmap arrays `np.memmap`) untuk membatasi working memory.

---

### 19. Interview Engineering Challenge
**Tantangan Tingkat Senior:** Buat fungsi sliding window 1-Dimensi *Moving Average* yang beroperasi secara murni berbasis **Zero-Copy Memory View** menggunakan manipulasi raw strides (tanpa menyalin data elemen ke array perantara dan tanpa eksternal dependency loop).

```python
import numpy as np
from numpy.lib.stride_tricks import as_strided

def zero_copy_sliding_window(arr: np.ndarray, window_size: int) -> np.ndarray:
    """
    Menghasilkan 2D array berbentuk (num_windows, window_size) tanpa melakukan copy memory.
    Input array: 1D Contiguous Buffer (float64).
    """
    if not isinstance(arr, np.ndarray) or arr.ndim != 1:
        raise ValueError("Input harus berupa array 1D NumPy")
    if not arr.flags['C_CONTIGUOUS']:
        arr = np.ascontiguousarray(arr)
        
    num_elements = arr.shape[0]
    if window_size <= 0 or window_size > num_elements:
        raise ValueError("Ukuran window tidak valid")

    num_windows = num_elements - window_size + 1
    element_byte_size = arr.itemsize  # 8 bytes untuk float64

    # REKAYASA STRIDES LEVEL MEMORI:
    # Dimensi 0 (Windows): Bergerak 1 elemen ke kanan -> step 1 * element_byte_size
    # Dimensi 1 (Elemen dalam window): Bergerak 1 elemen ke kanan -> step 1 * element_byte_size
    new_shape = (num_windows, window_size)
    new_strides = (element_byte_size, element_byte_size)

    # PERINGATAN: as_strided membuka akses pointer mentah
    strided_view = as_strided(arr, shape=new_shape, strides=new_strides, writeable=False)
    return strided_view

# Verifikasi Challenge
source = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float64)
windows = zero_copy_sliding_window(source, window_size=3)

print("Sliding Window Views (2D):")
print(windows)
print(f"Memory Sharing Status: {np.shares_memory(source, windows)}")
# Output membuktikan data sharing sempurna: True
```

---

### 20. Mastery Exercises
1.  **Foundation Tier:** Buat sebuah array berdimensi $1000 \times 1000$ bertipe `float64`. Lakukan benchmark waktu eksekusi untuk menghitung jumlah total nilai matriks dengan dua skenario: traversal baris per baris vs traversal kolom per kolom. Analisis mengapa hasilnya berbeda drastis ditinjau dari CPU cache lines.
2.  **Production Tier:** Implementasikan algoritma Z-score normalization kustom yang berjalan secara in-place (memodifikasi array asli tanpa mengalokasikan array target baru sama sekali di RAM). Validasi status base memory pointer sebelum dan sesudah kalkulasi.
3.  **Systems-Level Tier:** Menggunakan module `mmap` dan modul `ctypes` bawaan Python, alokasikan memory-mapped file mentah sebesar 1GB ke sistem operasi. Bungkus (*wrap*) pointer OS file descriptor tersebut langsung ke dalam `numpy.ndarray` menggunakan `np.frombuffer()` tanpa membaca file secara berurutan ke heap memory. Tunjukkan bahwa pembaruan nilai pada array langsung tercermin pada byte file di disk secara real-time.