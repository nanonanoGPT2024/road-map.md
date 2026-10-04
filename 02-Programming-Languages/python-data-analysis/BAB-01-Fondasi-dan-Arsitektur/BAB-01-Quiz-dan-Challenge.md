# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Komputasi & Arsitektur Memori NumPy**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Internal `ndarray`
Sebuah objek `numpy.ndarray` pada level implementasi C Python (`PyArrayObject`) dipisahkan secara tegas antara *array metadata* (header) dan *data buffer* (raw contiguous bytes).
* **Pertanyaan:** Sebutkan 5 komponen struktural utama yang tersimpan di dalam metadata header tersebut! Jelaskan secara arsitektural mengapa pemisahan antara metadata dan data buffer memungkinkan operasi seperti `reshape()`, `transpose()`, dan *slicing* berjalan dalam kompleksitas waktu $O(1)$ tanpa mengalokasi ulang memori buffer data utama!

### Soal 1.2: Matematika Penurunan Alamat Memori (Byte Striding)
Diberikan sebuah array 3 dimensi berukuran matriks $A$ dengan shape $(D_0, D_1, D_2)$ dan tipe data `float64` (8 bytes per elemen), tersimpan dalam layout C-contiguous.
* **Pertanyaan:** 
  1. Turunkan rumus analitis untuk menghitung *strides tuple* $(S_0, S_1, S_2)$ dalam satuan *bytes*.
  2. Jika indeks elemen yang ingin diakses adalah $(i, j, k)$, tuliskan persamaan matematika pointer offset (dalam byte) dari alamat dasar (*base memory address* $B$) buffer data menuju elemen target!

### Soal 1.3: C-Order vs. Fortran-Order dan Implikasinya terhadap CPU Cache
Dalam arsitektur hardware modern, CPU mentransfer data dari RAM ke CPU Cache (L1/L2/L3) dalam satuan *Cache Lines* (umumnya 64 bytes).
* **Pertanyaan:** Mengapa iterasi baris demi baris pada array berukuran $10000 \times 10000$ bertipe `float64` dengan layout C-contiguous menghasilkan *throughput* komputasi yang jauh lebih tinggi dibandingkan iterasi kolom demi kolom pada array yang sama? Jelaskan fenomena ini dengan merujuk pada konsep *Spatial Locality* dan *Cache Misses* (khususnya *Capacity* vs *Compulsory Misses*)!

### Soal 1.4: Mekanisme Memory View vs. Deep Copy
Perhatikan kode berikut:
```python
import numpy as np

large_matrix = np.ones((10000, 10000), dtype=np.float64)
sub_view = large_matrix[100:200, 100:200]
sub_copy = large_matrix[100:200, 100:200].copy()
```
* **Pertanyaan:** 
  1. Bagaimana Anda membuktikan secara programmatic via Python interpreter bahwa `sub_view` berbagi memori fisik dengan `large_matrix`, sedangkan `sub_copy` tidak? (Sebutkan atribut internal yang harus diinspeksi).
  2. Apa konsekuensi siklus hidup memori (*memory lifecycle/garbage collection*) dari `large_matrix` jika referensi global terhadap `large_matrix` dihapus menggunakan `del large_matrix`, namun objek `sub_view` masih dirujuk oleh variabel aktif lain?

### Soal 1.5: Arsitektur Zero-Copy Broadcasting
NumPy memungkinkan operasi aritmatika antara dua array dengan dimensi berbeda tanpa menduplikasi data melalui mekanisme *Broadcasting*.
* **Pertanyaan:** Bagaimana NumPy merekayasa nilai shape dan *strides* secara internal ketika sebuah array 1D dengan shape `(3,)` dioperasikan dengan array 2D berukuran `(4, 3)`? Jelaskan mengapa manipulasi nilai *stride* menjadi `0` memungkinkan komputasi *broadcasting* berjalan sepenuhnya *zero-copy*!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Bahaya Undefined Behavior pada `as_strided`
Modul `numpy.lib.stride_tricks.as_strided` memberikan akses direct manipulation terhadap pointer strides. Diberikan potongan kode berikut:
```python
import numpy as np
from numpy.lib.stride_tricks import as_strided

x = np.array([1, 2, 3, 4], dtype=np.int32)
y = as_strided(x, shape=(3, 3), strides=(4, 4))
```
* **Pertanyaan:** 
  1. Berapa alokasi byte aktual dari array `x`? 
  2. Apa yang terjadi ketika elemen `y[2, 2]` dievaluasi oleh sistem? Jelaskan bahaya *segmentation fault*, *data corruption*, atau pembacaan *garbage memory* yang terjadi di tingkat address space proses OS!

### Soal 2.2: Memory Leak Terselubung via Slicing Buffer Raksasa
Sebuah microservice analitik memproses citra satelit beresolusi tinggi (array berukuran $20000 \times 20000$ bertipe `float32`, total footprint memori $\approx 1.6\text{ GB}$). Microservice ini hanya membutuhkan area $10 \times 10$ pixel (*bounding box*) untuk disimpan ke dalam cache memori jangka panjang:
```python
def extract_roi(high_res_image):
    # high_res_image: shape (20000, 20000)
    roi = high_res_image[:10, :10]
    return roi
```
* **Pertanyaan:** Mengapa penggunaan fungsi di atas menyebabkan microservice mengalami *Out of Memory* (OOM) seiring berjalannya waktu meskipun array yang disimpan hanya berukuran $10 \times 10$? Tuliskan modifikasi kode satu baris untuk mengatasi masalah kebocoran memori ini secara permanen beserta justifikasi teknisnya!

### Soal 2.3: In-Place Mutation vs. Temporary Allocation Overhead
Perhatikan dua strategi akumulasi matriks berikut pada array berukuran $5000 \times 5000$:
```python
# Pendekatan A
A = A + B

# Pendekatan B
A += B
# atau np.add(A, B, out=A)
```
* **Pertanyaan:** Bedah perbedaan internal eksekusi mesin antara Pendekatan A dan Pendekatan B! Mengapa Pendekatan A dapat memicu lonjakan penggunaan RAM (*peak memory spike*) sebesar $2 \times$ hingga $3 \times$ ukuran matriks, dan bagaimana pengaruhnya terhadap overhead alokator memori C (`malloc` / `free`)?

### Soal 2.4: Memory Alignment dan Dampaknya terhadap SIMD Vectorization
Instruksi modern CPU (seperti AVX2, AVX-512) mengeksekusi operasi vectorized secara optimal ketika alamat memori data sejajar (*aligned*) pada kelipatan byte tertentu (misal: kelipatan 32 atau 64 byte).
* **Pertanyaan:** 
  1. Bagaimana cara memeriksa status alignment dari array NumPy via atribut `.flags`?
  2. Apa degradasi performa yang terjadi jika data buffer tidak aligned ketika Universal Function (ufunc) NumPy mencoba mengeksekusi instruksi *vectorized load* (misal: instruksi assembly `_mm256_load_pd` vs `_mm256_loadu_pd`)?

### Soal 2.5: Bottleneck Buffer Execution pada Non-Contiguous ufuncs
Ketika ufunc dijalankan pada array yang terfragmentasi (misalnya hasil dari slicing langkah mundur `a[::-2, ::-2]`), array tersebut kehilangan flag `C_CONTIGUOUS` dan `F_CONTIGUOUS`.
* **Pertanyaan:** Jelaskan mekanisme internal yang terpaksa dilakukan oleh loop engine internal ufunc NumPy ketika mengeksekusi operasi pada array non-contiguous tersebut! Mengapa kondisi ini memicu *internal buffering loop*, menurunkan performa hingga berkali-kali lipat dibanding operasi pada array contiguous?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Pipeline FinTech High-Frequency Trading (HFT)
Sebuah sistem *real-time feature engineering* menerima aliran harga pasar saham (100.000 quote per detik). Pipeline mengumpulkan array ring-buffer berukuran 10.000 elemen dan menjalankan window kalkulasi moving average setiap kali ada quote baru. 
Teknisi menggunakan kode berikut:
```python
def update_and_calculate(current_window, new_tick):
    # current_window: np.ndarray shape (10000,)
    # new_tick: float
    updated_window = np.append(current_window[1:], new_tick)
    return np.mean(updated_window)
```
Setelah 1 jam berjalan, CPU utilization pipeline mencapai 100% dan latency melonjak drastis dari 5 mikrodetik menjadi 450 mikrodetik per eksekusi, mengakibatkan sistem trading mengalami delay fatal.
* **Pertanyaan Diagnostik:**
  1. Analisis akar masalah (root cause) performa pada fungsi `np.append` di atas dari perspektif alokasi memori heap C dan *data copy overhead*.
  2. Rancang solusi arsitektur zero-copy menggunakan konsep *strided pointer array* atau *circular buffer pre-allocated array* yang mempertahankan waktu eksekusi tetap sub-mikrodetik konstan $O(1)$!

### Skenario B: Race Condition & Data Corruption pada Inference Pipeline Multi-Worker
Sebuah sistem computer vision memproses batch video stream menggunakan arsitektur multiprocessing:
* Master process memuat model dan frame tensor raksasa berukuran `(1000, 1080, 1920, 3)` ke dalam memori bersama (`multiprocessing.shared_memory`).
* 8 worker processes spawned membaca batch masing-masing melalui view slicing: `batch = shared_array[start_idx:end_idx]`.
* Masing-masing worker menjalankan fungsi normalisasi gambar berikut:
```python
def preprocess(batch):
    batch /= 255.0  # Normalisasi in-place
    return run_inference(batch)
```
Hasil inference yang keluar dari worker secara sporadis menghasilkan output sampah (angka NaN atau deteksi objek yang salah total), dan master process mengalami crash korupsi data saat memproses frame berikutnya.
* **Pertanyaan Diagnostik:**
  1. Identifikasi mekanisme penyebab terjadinya *data corruption* pada skenario tersebut!
  2. Bagaimana Anda menegakkan isolasi memori atau proteksi immutability pada array NumPy tanpa mengorbankan performa *zero-copy memory sharing* antar proses?

### Skenario C: Arsitektur Backend Feature Store Skala 500 GB
Tim Data Engineering ditugaskan untuk menyajikan dataset feature embedding berukuran 500 GB agar dapat diakses dengan latency sub-milidetik oleh puluhan worker machine learning pada satu unit node komputasi berkapasitas RAM 64 GB.
Dua pendekatan arsitektural diajukan:
* **Pendekatan 1:** Memuat data secara bertahap menggunakan chunking via serialization formats (misal: Apache Parquet / Feather) dibaca menggunakan pandas/pyarrow lalu dikonversi ke NumPy.
* **Pendekatan 2:** Memanfaatkan `np.memmap` (Memory-Mapped File) yang di-persist di NVMe SSD berkecepatan tinggi.
* **Pertanyaan Diagnostik:**
  1. Bedah mekanisme *Virtual Memory System*, *Paging*, dan *Page Faults* pada sistem operasi Linux saat mengeksekusi Pendekatan 2 (`np.memmap`) pada array yang ukurannya jauh melampaui RAM fisik!
  2. Kapan Pendekatan 2 akan mengalami degradasi performa drastis (*thrashing*), dan strategi optimasi layout memori (misalnya *spatial reordering* atau *blocking*) apa yang harus diterapkan pada file biner disk agar akses slice tetap optimal?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance 2D Rolling Window Feature Extractor (Zero-Copy Implementation)

#### Problem Statement
Dalam pemrosesan sinyal citra medis dan geospasial, ekstraksi fitur lokal matriks (seperti localized standard deviation, filtering, konvolusi) memerlukan pembentukan sliding window 2D berukuran $K_h \times K_w$ di atas matriks citra sumber berukuran $H \times W$. 
Pendekatan naif menggunakan nested loop Python atau pemotongan slice manual menghasilkan duplikasi data memori masif sebesar $O(H \times W \times K_h \times K_w)$, yang secara instan menghabiskan RAM pada matriks berskala besar.

Tugas Anda adalah merancang dan mengimplementasikan sebuah modul engine sliding window 2D *zero-copy* murni berbasis manipulasi strides (`as_strided`), disertai lapisan validasi keamanan memori ketat.

#### Requirements
1. **Fungsi Utama:** Buat fungsi dengan signatur:
   ```python
   def rolling_window_2d(arr: np.ndarray, window_shape: tuple[int, int], step: tuple[int, int] = (1, 1)) -> np.ndarray:
       ...
   ```
2. **Zero-Copy Mandate:** Array output yang dihasilkan harus berdimensi 4: `(out_h, out_w, K_h, K_w)`. Array ini **wajib** merupakan sebuah *view* dari array input asli. Dilarang keras melakukan duplikasi buffer memori (`np.copy()`, `np.array()`, list comprehension, dsb).
3. **Safety Guardrail:** Validasi kondisi boundary pointer:
   * Array input wajib berupa 2D contiguous array (`C_CONTIGUOUS`).
   * Window size tidak boleh melebihi dimensi matriks sumber.
   * Langkah stride (`step`) harus mendukung arbitrary interval $\ge 1$.
   * Tandai flag writeable array hasil menjadi `False` (`arr.flags.writeable = False`) untuk mencegah data corruption pada array sumber akibat modifikasi downstream.
4. **Benchmarking & Memory Proof:**
   * Tunjukkan bukti programatik bahwa penambahan window view tersebut tidak menambah alokasi memori heap (footprint memori $\approx 0$ bytes overhead selain metadata header).
   * Lakukan benchmark performa kalkulasi ringkasan statistik (misal: `np.mean(axis=(-2, -1))`) terhadap matriks input $4000 \times 4000$ dengan window $64 \times 64$, bandingkan execution time dan peak memory footprint terhadap pendekatan looping/ekstraksi konvensional!

#### Constraints
* Hanya boleh menggunakan pustaka standar Python dan `numpy`.
* Tidak boleh menggunakan modul eksternal tingkat tinggi seperti `skimage.util.view_as_windows` atau `scipy.signal`.
* Implementasi harus kebal terhadap memory boundary overreach (tidak boleh memicu segmentation fault saat mengakses indeks batas maksimum output).

#### Expected Output
* File skrip Python modular (`rolling_window.py`) berisi implementasi fungsi dan unit test assertions.
* Laporan profil memori (menggunakan modul `tracemalloc` atau `memory_profiler`) yang mendokumentasikan:
  1. Perbandingan byte size memori array asal vs array window view.
  2. Status pointer memori (`.base` identification).
  3. Latency execution time dari algoritma.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda sebelum melangkah ke bab optimasi vektorisasi tingkat lanjut.

### Saya harus memahami:
- [ ] Arsitektur representasi internal objek `PyArrayObject` pada C API (Header metadata vs Data Buffer).
- [ ] Peran dan representasi atribut `shape`, `dtype`, `strides`, `data`, dan `flags` (`C_CONTIGUOUS`, `F_CONTIGUOUS`, `OWNDATA`, `WRITEABLE`).
- [ ] Rumus matematika pemetaan multi-dimensional index ke linear address offset via byte-strides.
- [ ] Dampak hierarki CPU Cache (L1, L2, L3, cache line 64-byte) serta perbandingan layout C-order vs Fortran-order terhadap spatial locality.
- [ ] Aturan resmi NumPy Broadcasting Mechanism dan implementasi zero-copy via 0-byte striding.
- [ ] Siklus hidup Garbage Collector (CPython Reference Counting) ketika subarray view mempertahankan eksistensi array induk di memori.
- [ ] Implikasi memori pemetaan file menggunakan `np.memmap` terhadap OS Virtual Memory Management (Paging, Page Faults, Swapping).

### Saya tidak perlu menghafal:
- [ ] Seluruh nilai flag heksadesimal internal C-API NumPy (misal: nilai biner bitwise untuk flag bitmask).
- [ ] Rumus micro-benchmark latency siklus clock assembly instruksi SIMD spesifik vendor CPU (misal: perbedaan latency cycle pasti antara Intel AVX-512 vs AMD Zen AVX-512).
- [ ] Variasi sintaks legacy dari modul-modul deprecated di luar namespace resmi modern `numpy`.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi apakah sebuah operasi menghasilkan *view* atau *copy* secara programatik menggunakan atribut `.base` dan flag memori.
- [ ] Menggunakan `np.lib.stride_tricks.as_strided` secara presisi dan aman tanpa memicu *segmentation fault* atau membaca *unallocated heap space*.
- [ ] Melakukan debugging dan perbaikan memory leak yang disebabkan oleh reference retention pada array berukuran besar.
- [ ] Menulis operasi aritmatika in-place (`out=` parameter) untuk mengeliminasi alokasi array temporer pada komputasi skala besar.
- [ ] Melakukan inspeksi alignment array dan menstrukturkan alokasi memori agar kompatibel dengan SIMD hardware vectorization.
- [ ] Mengukur memory footprint aktual, peak memory allocation, dan profiling latency menggunakan kombinasi `sys.getsizeof`, atribut `.nbytes`, modul `tracemalloc`, dan benchmarking berbasis timer CPU beresolusi tinggi.