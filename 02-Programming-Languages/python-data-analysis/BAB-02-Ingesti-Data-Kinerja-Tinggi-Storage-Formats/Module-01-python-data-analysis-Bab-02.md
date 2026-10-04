# Bab 02 Module 01: Fondasi Arsitektur NumPy — Ndarray Memory Layout, Strides, dan SIMD Vectorization

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik mampu:
*   **Mendiagnosis dan mengukur** *memory footprint* serta *cache locality* dari struktur data Python native (`list`) dibandingkan dengan `numpy.ndarray` menggunakan profiling memori level rendah.
*   **Menganalisis dan memanipulasi** metadata internal array (`shape`, `strides`, `dtype`, dan `flags`) untuk mengeliminasi operasi alokasi memori yang redundan.
*   **Mengimplementasikan komputasi terarah (*vectorized operations*)** yang memaksimalkan instruksi SIMD (*Single Instruction, Multiple Data*) pada CPU arsitektur x86_64/ARM64.
*   **Mengevaluasi dan merekayasa struktur *memory view*** menggunakan teknik manipulasi *strides* tanpa melakukan duplikasi data pada *heap memory*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
*   **Dasar Arsitektur Sistem Komputer**: Pemahaman terkait CPU Cache Hierarchy (L1, L2, L3), RAM, Memory Bus, dan konsep *Pointer Arithmetic*.
*   **Model Memori CPython**: Representasi objek di CPython (`PyObject`, reference counting, dynamic typing overhead).
*   **Python 3.10+ Intermediate**: Pemahaman kuat terhadap *type hinting*, *slicing*, dan *context manager*.

---

## 3. Concept

Di balik performa eksekusi komputasi data berskala besar, bottleneck utama CPython bukanlah kecepatan clock CPU murni, melainkan **abstraksi dinamis objek** dan **lokalitas memori yang buruk (*poor cache locality*)**.

### Model Memori CPython Native (`list`)
Objek `list` dalam Python standar sebenarnya adalah array pointer (`PyObject**`). Setiap elemen di dalam list adalah pointer yang merujuk ke lokasi memori acak (*scattered heap allocation*) tempat objek Python yang sebenarnya berada. 

```
Python List:
[ Pointer 0 ] ---> PyObject (Integer: 42)    [Heap: 0x7ffd01]
[ Pointer 1 ] ---> PyObject (Integer: 43)    [Heap: 0x7ffa14]
[ Pointer 2 ] ---> PyObject (Integer: 44)    [Heap: 0x7ffe90]
```

Kondisi ini menyebabkan:
1.  **Pointer Chasing**: CPU harus melakukan *dereferencing* pointer berkali-kali.
2.  **Cache Misses**: Data tidak berada dalam blok memori yang berdekatan, sehingga CPU L1/L2 Cache Prefetcher gagal memuat data ke register sebelum dibutuhkan.
3.  **Memory Overhead**: Setiap `int` di Python membungkus nilai integer primitif C dalam struktur `PyObject` (ukuran standar 28 byte untuk satu integer sederhana).

### Arsitektur Internal `numpy.ndarray`
`numpy.ndarray` mengimplementasikan representasi homogen berbasis *contiguous memory block* yang ditulis dalam bahasa C (`PyArrayObject`). Struktur ini memisahkan **metadata deskriptor** dari **payload data mentah**:

```
PyArrayObject Header (Metadata):
├── data: Pointer ke blok memori kontinu (void*)
├── dtype: Deskriptor tipe data (e.g., float64, int32)
├── shape: Tuple dimensi array (e.g., (1000, 1000))
├── strides: Tuple lompatan byte per dimensi (e.g., (8000, 8))
└── flags: Metadata status memori (C_CONTIGUOUS, WRITEABLE, dll.)
```

Data numerik aktual disimpan sebagai blok memori primitif yang kontinu, identik dengan array primitif di bahasa C atau Fortran. Hal ini memungkinkan pemanfaatan fitur hardware modern secara langsung:
*   **L1/L2 Cache Locality**: CPU memuat data satu *cache line* (umumnya 64 byte) secara utuh.
*   **SIMD Vectorization**: Instruksi seperti AVX-512 atau ARM NEON dapat memproses beberapa data floating-point (misalnya, delapan data 64-bit float sekaligus) dalam satu siklus instruksi CPU.

---

## 4. Why

Mengapa rekayasa arsitektur memori ini mutlak diperlukan dalam rekayasa data produksi?

1.  **Overhead Komputasi Skala Peta/Terabyte**: Eksekusi operasi aritmatika melalui `for` loop di Python menyebabkan overhead evaluasi tipe dinamis (*dynamic type checking*) pada setiap iterasi. Pada 100 juta baris data, evaluasi tipe berulang memakan 90% waktu eksekusi total.
2.  **Efisiensi Memori (Cost Optimization)**: Menyimpan 100 juta integer 64-bit pada Python `list` membutuhkan sekitar ~800 MB (pointer) + ~2.8 GB (objek `int`) = ~3.6 GB. Pada NumPy `ndarray`, 100 juta integer 64-bit (8 byte) secara eksak hanya memakan $10^8 \times 8 \text{ bytes} \approx 800\text{ MB}$. Ini mereduksi kebutuhan RAM server hingga 77%.
3.  **Kompatibilitas Zero-Copy Driver**: Model memori kontinu memungkinkan NumPy membagikan buffer data secara langsung (`zero-copy`) ke pustaka C/C++, CUDA (GPU), Apache Arrow, dan akselerator hardware eksternal tanpa serialisasi/deserialisasi.

---

## 5. What

Komponen kunci yang menyusun arsitektur eksekusi `numpy.ndarray` terdiri dari:

*   **Data Pointer (`data`)**: Alamat memori absolut (pointer) ke byte pertama dari blok data kontinu.
*   **Dtype (`numpy.dtype`)**: Informasi ukuran byte (itemsize), endianness (byte-order), dan interpretasi bit primitif (misal: `int32`, `float64`).
*   **Shape**: Dimensi logis array yang direpresentasikan sebagai tuple integer berukuran $N$, di mana $N$ adalah jumlah dimensi (*rank*).
*   **Strides**: Tuple integer yang mendefinisikan *berapa byte yang harus dilewati di memori* untuk berpindah ke elemen berikutnya di sepanjang setiap dimensi.
*   **Flags**: Penanda status buffer memori:
    *   `C_CONTIGUOUS` (Row-major order: baris berdekatan di memori).
    *   `F_CONTIGUOUS` (Column-major order: kolom berdekatan di memori).
    *   `OWNDATA`: Menentukan apakah array ini mengalokasikan memorinya sendiri atau sekadar meminjam buffer dari array lain (*view*).
    *   `WRITEABLE`: Aksesibilitas mutasi data.

---

## 6. How

### Rumus Navigasi Memori Menggunakan Strides
Untuk array $N$-dimensi dengan koordinat indeks $(i_0, i_1, \dots, i_k)$ dan strides $(S_0, S_1, \dots, S_k)$, lokasi byte absolut dari elemen dihitung menggunakan persamaan:

$$\text{Memory Offset} = \sum_{j=0}^{k} (i_j \times S_j)$$

$$\text{Absolute Memory Address} = \text{Data Pointer} + \text{Memory Offset}$$

### Transisi Operasi: View vs Copy
Saat melakukan slicing atau manipulasi bentuk (*reshaping*):
1.  NumPy memodifikasi nilai `shape` dan `strides` di header metadata, tanpa menyentuh atau menduplikasi blok memori payload.
2.  Operasi ini menghasilkan **View** ($O(1)$ time complexity dan $O(1)$ memory allocation).
3.  **Copy** hanya terjadi jika memori hasil slicing tidak dapat direpresentasikan melalui kombinasi langkah *strides* yang valid, atau saat pemanggilan ekspisit method `.copy()`.

---

## 7. Analogy

Bayangkan sebuah **perpustakaan besar**:

*   **Model Python List**: Buku-buku diletakkan secara acak di lantai gedung dari lantai 1 sampai lantai 5. Anda memegang daftar kertas berisi alamat koordinat GPS setiap buku. Untuk membaca Bab 1 sampai 10, Anda harus berjalan menaiki tangga dan mencari setiap kamar berdasarkan koordinat GPS satu per satu (**Pointer Chasing & High Latency**).
*   **Model NumPy Array**: Buku-buku disusun rapi dalam satu rak panjang secara berurutan. Jika Anda ingin membaca 10 buku berikutnya, Anda cukup melangkah 30 cm ke kanan per buku secara konsisten (**Contiguous Memory & Strides**).
*   **SIMD Execution**: Anda memiliki alat baca mekanis dengan 8 pasang mata yang dapat membaca 8 buku berdampingan di rak tersebut dalam satu lirikan mata secara serentak (**Vectorization**).

---

## 8. Diagram

### Perbandingan Struktur Memori Tingkat Rendah

```
---------------------------------------------------------------------------------
CPython List: list[int] (Terfragmentasi & Menggunakan Pointer)
---------------------------------------------------------------------------------
List Object in Heap (Array of Pointers)
+-----------------------+-----------------------+-----------------------+
| Pointer to Item 0     | Pointer to Item 1     | Pointer to Item 2     |
| [ 0x00007FCA10 ]      | [ 0x00007FCA98 ]      | [ 0x00007FCB20 ]      |
+-----------+-----------+-----------+-----------+-----------+-----------+
            |                       |                       |
            v                       v                       v
     +--------------+        +--------------+        +--------------+
     | PyObject     |        | PyObject     |        | PyObject     |
     | ob_refcnt: 1 |        | ob_refcnt: 1 |        | ob_refcnt: 1 |
     | ob_type: int |        | ob_type: int |        | ob_type: int |
     | ob_ival: 100 |        | ob_ival: 200 |        | ob_ival: 300 |
     +--------------+        +--------------+        +--------------+
     (Memori Tersebar di RAM - Rawan CPU Cache Miss)

---------------------------------------------------------------------------------
NumPy ndarray: ndarray (Contiguous Memory Buffer)
---------------------------------------------------------------------------------
PyArrayObject Header
+---------------------------------------------------------+
| data_ptr: 0x00007FFF00                                  |
| shape: (2, 3)                                           |
| strides: (24, 8)  --> Lompat 24 byte ke baris baru,     |
|                       lompat 8 byte ke elemen kanan.    |
| dtype: float64 (8 bytes per elemen)                     |
+---------------------------------------------------------+
            |
            v
Contiguous Memory Buffer (Direct Binary Data in RAM)
+---------------+---------------+---------------+---------------+---------------+---------------+
| 0x00007FFF00  | 0x00007FFF08  | 0x00007FFF10  | 0x00007FFF18  | 0x00007FFF20  | 0x00007FFF28  |
| 1.0 (float64) | 2.0 (float64) | 3.0 (float64) | 4.0 (float64) | 5.0 (float64) | 6.0 (float64) |
+---------------+---------------+---------------+---------------+---------------+---------------+
|<----------------------------- Dimuat Langsung ke CPU L1 Cache Line -------------------------->|
```

---

## 9. Simple Example

Menginspeksi arsitektur internal array: dimensi, strides, dan pembuktian *Zero-Copy View*.

```python
import numpy as np

# Inisialisasi array 2 dimensi dengan 2 baris dan 3 kolom berdimensi float64 (8 bytes)
arr = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.float64)

print("=== Metadata Array Asli ===")
print(f"Data Base Pointer : {arr.ctypes.data}")
print(f"Shape             : {arr.shape}")
print(f"Dtype             : {arr.dtype} (itemsize: {arr.itemsize} bytes)")
print(f"Strides           : {arr.strides}")
# Strides (24, 8) artinya:
# - Butuh 24 bytes (3 elemen * 8 bytes) untuk melompat ke baris berikutnya.
# - Butuh 8 bytes (1 elemen * 8 bytes) untuk melompat ke kolom berikutnya.

# Membuat Slicing (View)
view_slice = arr[:, 1:]

print("\n=== Metadata View Slice ===")
print(f"Data Base Pointer : {view_slice.ctypes.data}")
print(f"Shape             : {view_slice.shape}")
print(f"Strides           : {view_slice.strides}")
print(f"Shares Memory?    : {np.shares_memory(arr, view_slice)}")
print(f"Owns Data?        : {view_slice.flags.owndata}")

# Bukti Zero-Copy: Mengubah nilai pada view akan mempengaruhi array asli
view_slice[0, 0] = 999.0
print("\n=== Efek Mutasi View Terhadap Array Induk ===")
print(arr)
```

---

## 10. Practical Example

Implementasi algoritma pemrosesan citra / sliding window: Menghitung *Moving Average* 2D tanpa alokasi memori tambahan menggunakan manipulasi memori tingkat rendah `lib.stride_tricks.as_strided`.

```python
from typing import Tuple
import numpy as np
import time

def moving_window_2d_stride(
    matrix: np.ndarray, 
    window_shape: Tuple[int, int]
) -> np.ndarray:
    """
    Menghasilkan representasi rolling window 4D menggunakan manipulasi strides.
    Kompleksitas Memori: O(1) alokasi baru (Zero-Copy View).
    """
    if not matrix.flags['C_CONTIGUOUS']:
        matrix = np.ascontiguousarray(matrix)
        
    m_rows, m_cols = matrix.shape
    w_rows, w_cols = window_shape
    
    out_rows = m_rows - w_rows + 1
    out_cols = m_cols - w_cols + 1
    
    if out_rows <= 0 or out_cols <= 0:
        raise ValueError("Window size lebih besar daripada dimensi matriks input.")
        
    s_row, s_col = matrix.strides
    
    # Menghitung strides baru untuk bentuk (out_rows, out_cols, w_rows, w_cols)
    new_shape = (out_rows, out_cols, w_rows, w_cols)
    new_strides = (s_row, s_col, s_row, s_col)
    
    # as_strided membentuk view baru tanpa menduplikasi data payload
    strided_view = np.lib.stride_tricks.as_strided(
        matrix, 
        shape=new_shape, 
        strides=new_strides, 
        writeable=False # Guardrail keamanan memori
    )
    return strided_view

# Driver Execution & Profiling
if __name__ == "__main__":
    # Inisialisasi matriks sintetis (1000 x 1000)
    data = np.random.rand(1000, 1000).astype(np.float64)
    win_size = (3, 3)
    
    start_time = time.perf_counter()
    windows = moving_window_2d_stride(data, win_size)
    # Kalkulasi rata-rata per window secara tervektorisasi penuh via axis reduction (SIMD)
    moving_avg = windows.mean(axis=(2, 3))
    exec_time = time.perf_counter() - start_time
    
    print(f"Matriks Asli Byte Size    : {data.nbytes / (1024**2):.2f} MB")
    print(f"Windows View Theoretical  : {(windows.size * windows.itemsize) / (1024**2):.2f} MB")
    print(f"Actual Memory Used by View: {windows.nbytes / (1024**2):.2f} MB (Header only)")
    print(f"Shares Memory with Source : {np.shares_memory(data, windows)}")
    print(f"Hasil Moving Average Shape: {moving_avg.shape}")
    print(f"Waktu Eksekusi Zero-Copy  : {exec_time * 1000:.4f} ms")
```

---

## 11. Real World Example

### Kasus Industri: Algoritma Matching Engine & VWAP (Volume Weighted Average Price) di Platform FinTech Kuantitatif

Sebuah exchange mata uang kripto menerima puluhan juta data transaksi (*tick data*) per menit. Sistem analisis risiko harus menghitung VWAP secara riil dengan latensi sub-detik untuk mendeteksi anomali harga.

Pendekatan `for-loop` tradisional pada Python native gagal mencapai Service Level Agreement (SLA) latensi (<100 ms). Implementasi di bawah mengoptimalkan operasi menggunakan C-contiguous alignment dan SIMD-vectorized execution.

```python
import numpy as np
import time

def generate_tick_data(n_samples: int) -> np.ndarray:
    """Simulasi data transaksi pasar finansial kontinu: [Price, Volume]."""
    np.random.seed(42)
    prices = np.random.uniform(25000.0, 30000.0, size=(n_samples, 1)).astype(np.float64)
    volumes = np.random.uniform(0.01, 2.5, size=(n_samples, 1)).astype(np.float64)
    return np.ascontiguousarray(np.hstack((prices, volumes)))

def compute_vwap_native_python(ticks: list) -> float:
    """Implementasi Python unvectorized menggunakan for-loop overhead tinggi."""
    cumulative_price_vol = 0.0
    cumulative_vol = 0.0
    for i in range(len(ticks)):
        p = ticks[i][0]
        v = ticks[i][1]
        cumulative_price_vol += p * v
        cumulative_vol += v
    return cumulative_price_vol / cumulative_vol if cumulative_vol != 0 else 0.0

def compute_vwap_vectorized(ticks: np.ndarray) -> float:
    """
    Eksekusi tervektorisasi SIMD.
    Operasi aritmatika dieksekusi di level instruksi register C tanpa pointer dereference.
    """
    prices = ticks[:, 0]
    volumes = ticks[:, 1]
    
    # Dot product mengompilasi operasi perkalian-akumulasi secara paralel (FMA Instruction)
    vwap = np.dot(prices, volumes) / np.sum(volumes)
    return float(vwap)

# Benchmark Produksi
N = 5_000_000
raw_ticks_np = generate_tick_data(N)
raw_ticks_py = raw_ticks_np.tolist()

# 1. Benchmark Native Python Loop
t0 = time.perf_counter()
res_py = compute_vwap_native_python(raw_ticks_py)
t_py = time.perf_counter() - t0

# 2. Benchmark NumPy Vectorized SIMD
t1 = time.perf_counter()
res_np = compute_vwap_vectorized(raw_ticks_np)
t_np = time.perf_counter() - t1

print(f"Data points processed: {N:,} ticks")
print(f"Native Python Execution Time : {t_py:.4f} detik | Result: {res_py:.4f}")
print(f"Vectorized Execution Time    : {t_np:.4f} detik | Result: {res_np:.4f}")
print(f"Speedup Factor               : {t_py / t_np:.2f}x lipat lebih cepat")
```

---

## 12. Trade-offs

| Parameter | Python Native (`list` of `dict`/`primitive`) | NumPy Contiguous `ndarray` |
| :--- | :--- | :--- |
| **Memory Footprint** | Sangat Buruk (Overhead pointer 8-byte + `PyObject` 28-byte per item). | Optimal/Minimal (Presisi absolut $N \times \text{byte size}$ tanpa header overhead per elemen). |
| **Cache Locality** | Lemah. Fragmentasi memori tinggi menyebabkan terus-menerus terjadi *L1 Cache Miss*. | Sangat Baik. Memori sekuensial memfasilitasi pemanfaatan jalur data bus secara optimal. |
| **Operasi Modifikasi Dimensi**| Lambat. Append/Insert memerlukan realokasi dinamis pointer array. | Terbatas. Dimensi bersifat *fixed-size*. Penambahan ukuran memerlukan re-alokasi penuh array baru. |
| **Fleksibilitas Data** | Sangat Fleksibel. Menerima berbagai jenis tipe data heterogen dalam satu kontainer. | Kaku/Statis. Tipe data homogen. Konversi otomatis ke tipe data paling longgar (*upcasting*). |
| **SIMD Hardware Acceleration**| Tidak Mendukung. Operasi dieksekusi per-elemen via CPython Interpreter Loop. | Mendukung Secara Penuh. Terintegrasi langsung dengan instruksi AVX2, AVX-512, atau NEON. |
| **Development Complexity** | Rendah. Logika prosedural natural bagi pemula. | Sedang-Tinggi. Memerlukan pemahaman aljabar linier, *broadcasting rules*, dan manipulasi strides. |

---

## 13. When To Use

*   **Komputasi Numerik Terstruktur Skala Besar**: Operasi data matriks, array multidimensi, sinyal audio/video, dan bobot neural network.
*   **Aplikasi Finansial Latensi Rendah**: Kalkulasi portofolio, risk modelling (Monte Carlo), dan kalkulasi spread harga orderbook secara real-time.
*   **Manipulasi Citra dan Sensor**: Data LiDAR, kamera monokrom/RGB, dan sensor IoT dengan throughput pembacaan tinggi.
*   **Pipeline Machine Learning Tingkat Rendah**: Pra-pemrosesan data sebelum disalurkan ke pipeline PyTorch, TensorFlow, atau Scikit-Learn.

---

## 14. When NOT To Use

*   **Data Heterogen Kompleks Berorientasi Entitas**: Ketika setiap baris memiliki struktur field dinamis yang bervariasi secara bebas (Gunakan `dict`, `dataclass`, atau Pydantic).
*   **Operasi Append Dinamis Frekuensi Tinggi**: Menambahkan elemen satu per satu via loop berulang. Operasi `np.append` menyalin ulang seluruh array ke lokasi memori baru ($O(N)$ per append). Gunakan native Python `list` untuk pengumpulan data awal, lalu konversi ke `ndarray` sekali saja.
*   **Struktur Data Graf atau Pohon Non-Linier**: Algoritma traversing yang bergantung pada model referensi pointer antar simpul node lebih tepat ditangani dengan Python pointer/graph library (e.g., NetworkX).

---

## 15. Common Mistakes

### 1. Involuntarily Triggering Memory Copies (Implicit Copy)
Membuat array baru di memori secara tidak sadar akibat penggunaan *fancy indexing* (menggunakan list integer sebagai indeks):

```python
arr = np.arange(10_000_000)

# Slicing: Menghasilkan VIEW (Zero Memory Allocation)
view_arr = arr[0:5_000_000]
print(view_arr.flags.owndata)  # False -> Menggunakan buffer yang sama

# Fancy Indexing: Menghasilkan COPY (Mengalokasikan memori baru di heap!)
copy_arr = arr[[0, 1, 2, 3, 4]]
print(copy_arr.flags.owndata)  # True -> Mengalokasikan memori terpisah
```

### 2. Menggunakan Loop Python untuk Operasi Aritmatika pada Array
Mengiterasi `ndarray` menggunakan `for x in arr:` membatalkan seluruh optimasi C-buffer karena CPython terpaksa merekonstruksi pointer `PyObject` untuk setiap elemen skalar pada saat runtime loop berlangsung.

### 3. Mengabaikan Layout Urutan Memori (C-Order vs Fortran-Order)
Melakukan operasi pengurangan/agregasi kolom pada array yang disusun secara C-Contiguous menghasilkan waktu komputasi yang jauh lebih lambat karena CPU meloncat antar *cache lines*.

```python
# Array besar dengan C-Contiguous (Row-major)
matrix = np.ones((20000, 20000), order='C')

# Melakukan traversal searah baris (Sangat Cepat - Mengikuti Cache Locality)
row_sum = matrix.sum(axis=1)

# Melakukan traversal memotong kolom (Jauh Lebih Lambat - Memaksa Strided Cache Misses)
col_sum = matrix.sum(axis=0)
```

---

## 16. Best Practices

1.  **Validasi Layout Buffer Memori**: Pastikan array yang diproses dalam fungsi intensif memori memiliki flag `C_CONTIGUOUS` jika algoritma melakukan iterasi baris, atau `F_CONTIGUOUS` jika algoritma memanfaatkan algoritma aljabar linier berbasis BLAS Fortran.
2.  **Gunakan In-Place Operations untuk Data Raksasa**: Manfaatkan parameter `out=` untuk mencegah pembuatan array temporer baru di memori:
    ```python
    # Mencegah alokasi memori array perantara
    np.add(a, b, out=a)  # Nilai langsung ditulis kembali ke buffer a
    ```
3.  **Hindari Upcasting Implicit**: Selalu definisikan tipe data secara eksplisit saat inisialisasi:
    ```python
    # Default float seringkali float64. Jika presisi float32 mencukupi,
    # penghematan bandwidth bus memori mencapai 50%!
    data = np.zeros((1000, 1000), dtype=np.float32)
    ```
4.  **Terapkan Read-Only Flag pada Memory Views**: Jika Anda memanipulasi *strides* secara kustom, kunci writeable flag untuk mencegah *memory corruption* atau *segmentation faults*:
    ```python
    custom_view.flags.writeable = False
    ```

---

## 17. Troubleshooting

### Case 1: Terjadi Lonjakan Memori Liar (*Memory Leak via View Retention*)
*   **Gejala**: Memori server tidak pernah turun meskipun proses slicing data hanya mengambil sub-elemen kecil.
*   **Penyebab Root-Cause**: Slicing menghasilkan *view*. Walaupun array hasil slicing sangat kecil, *base array* yang masif tidak dapat dibersihkan oleh Garbage Collector CPython karena referensi pointer basis data masih terkunci oleh sub-array tersebut (`view.base` menahan seluruh blok memori).
*   **Solusi**:
    ```python
    # Potensial memory retention leak
    large_dataset = np.ones((50000, 50000), dtype=np.float64) # ~20 GB
    sub_selection = large_dataset[0:5, 0:5] # View menahan seluruh alokasi 20 GB!
    del large_dataset # Garbage collector gagal membersihkan memori 20 GB

    # Solusi Arsitektural: Lepaskan dependensi basis memori via explicit copy
    sub_selection = large_dataset[0:5, 0:5].copy()
    del large_dataset # Buffer 20 GB berhasil dibebaskan dari RAM secara instan
    ```

### Case 2: Performa Vektorisasi Tiba-tiba Melambat 10x Lipat
*   **Penyebab**: Terjadinya non-contiguous striding akibat operasi slicing multi-axis yang tidak beraturan, memutus optimasi instruksi SIMD pada CPU hardware.
*   **Solusi**:
    ```python
    if not arr.flags['C_CONTIGUOUS']:
        arr = np.ascontiguousarray(arr)
    # Jalur pipa komputasi SIMD terpulihkan
    ```

---

## 18. Exercise

1.  **Inspeksi Memori Strides**: Buat matriks 3 dimensi dengan dimensi `(4, 3, 2)` bertipe data `int16` (2 byte). Tulis fungsi untuk menghitung secara manual nilai `strides` teoretis untuk format Row-Major (C-Contiguous), kemudian verifikasi perhitungan Anda menggunakan atribut `.strides` dari NumPy.
2.  **Benchmark Profiling**: Bandingkan waktu eksekusi dan konsumsi memori untuk menjumlahkan semua angka ganjil antara $1$ sampai $10^7$ menggunakan:
    *   Pendekatan 1: List Comprehension native Python dipadu fungsi built-in `sum()`.
    *   Pendekatan 2: `np.ndarray` dengan pemfilteran berbasis *boolean masking* dan method `.sum()`.

---

## 19. Challenge

### Misi: Mengimplementasikan Algoritma 1D Convolusi Menggunakan Strides Tanpa Duplikasi Memori

Tuliskan sebuah fungsi kelas produksi dengan spesifikasi berikut:
*   **Fungsi**: `fast_1d_convolve(signal: np.ndarray, kernel: np.ndarray) -> np.ndarray`
*   **Batasan Ketat**:
    1.  Dilarang menggunakan fungsi bawaan `np.convolve`, `scipy.signal`, atau loop iterasi Python `for`.
    2.  Gunakan manipulasi memori `np.lib.stride_tricks.as_strided` untuk mengekstraksi seluruh segmen sub-sinyal secara *zero-copy*.
    3.  Lakukan perkalian dot product dengan kernel menggunakan vektorisasi hardware.
    4.  Lakukan validasi array input untuk menjamin eksekusi aman (*memory safety*). Pastikan flag memory writeable dinonaktifkan pada view internal untuk mencegah potensi *segmentation fault*.
*   **Target Efisiensi**: Waktu eksekusi harus stabil di bawah 20 milidetik untuk sinyal sepanjang $1.000.000$ elemen dengan ukuran kernel $64$.

---

## 20. Summary

1.  **Dua Pilar Kecepatan**: Kecepatan superior eksekusi NumPy berakar dari **blok memori primitif yang kontinu** dan **eliminasi abstraksi dinamis CPython**.
2.  **Metadata vs Payload**: Header `PyArrayObject` mengontrol dimensi dan orientasi data melalui tuple **`shape`** dan **`strides`**, memungkinkan operasi transformasi bentuk tanpa alokasi memori baru (*Zero-Copy Views*).
3.  **Sinergi Hardware**: Struktur contiguous array memfasilitasi optimalisasi hardware secara penuh: meminimalkan *cache miss* pada L1/L2 data cache dan mengaktifkan instruksi paralel **SIMD (AVX/NEON)**.
4.  **Efisiensi Sistem**: Pemahaman arsitektur memori tingkat rendah mencegah jebakan umum seperti memory leaks akibat view retention, biaya alokasi fancy indexing yang tidak disengaja, dan degradasi latensi pada pipeline pengolahan data berskala enterprise.