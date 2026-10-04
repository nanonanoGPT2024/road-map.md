# Kurikulum Enterprise R: Rekayasa Komputasi & Performa Skala Besar

## Bab 02: Sistem Tipe Data, Memori Internal & Vektorisasi
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah Struktur Internal R S-Expression (SEXP):** Mengidentifikasi tata letak biner dari `SEXPREC`, flags `sxpinfo`, dan representasi heap internal C level R.
- **Mengaudit Siklus Hidup Memori dan Garbage Collection:** Mengontrol mekanisme *Copy-on-Write* (CoW), tracking referensi (`REFCNT`), dan Generational GC (Gen 0, 1, 2) untuk mengeliminasi alokasi yang tidak perlu.
- **Mengimplementasikan dan Memanfaatkan Framework ALTREP (Alternative Representations):** Mengembangkan pipeline data berkapasitas memori mendekati nol (*zero-copy data ingestion*) dengan *memory-mapped files* dan vektor non-materialized.
- **Merancang Kernel Vektorisasi Kustom (SIMD & Cache Locality):** Menulis algoritma komputasi intensif berkinerja tinggi menggunakan C/C++ (`cpp11`/`Rcpp`) yang memanfaatkan *contiguous memory layout*, pointer arithmetic, dan vektorisasi perangkat keras.
- **Membangun Arsitektur Pipeline Data Enterprise:** Memproses dataset berukuran gigabita hingga terabita pada kluster produksi dengan latensi deterministik dan konsumsi memori terikat (*bounded memory footprint*).

---

### 2. Prerequisite

Sebelum menempuh modul lanjutan ini, peserta wajib menguasai:
- Pengetahuan fundamental tipe data R (vektor atomik, list, atribut, `data.frame`).
- Pemahaman dasar arsitektur sistem operasi: Virtual Memory, Page Cache, Cache Lines (L1/L2/L3), Pointer, Heap vs Stack.
- Familiaritas dengan bahasa C/C++ tingkat menengah (alokasi memori manual, struct, dereferencing pointer).
- Pengalaman dasar dalam profilisasi kode R menggunakan paket seperti `bench` atau `profvis`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi SEXP (S-Expression) dan Header Memori
Di tingkat kernel C runtime R, setiap objek—mulai dari integer tunggal, matriks, hingga *closure* (fungsi)—direpresentasikan sebagai pointer ke sebuah struktur `SEXPREC` (S-Expression Record).

```
          +--------------------------------------------------------+
          |                      SEXPREC                           |
          +--------------------------------------------------------+
          | sxpinfo (4 bytes / 32-bit bitfield)                    |
          |   - TYPE (5 bits)   : INTSXP, REALSXP, VECSXP, dll.    |
          |   - GC (1 bit)      : Mark/Sweep generation state      |
          |   - REFCNT (16 bits): Reference Counting system        |
          |   - ATTR (1 bit)    : Flag kepemilikan atribut         |
          +--------------------------------------------------------+
          | SEXP attrib         : Pointer ke Pairlist Atribut      |
          +--------------------------------------------------------+
          | SEXP gengc_next_node: Pointer doubly linked list GC    |
          | SEXP gengc_prev_node: Pointer doubly linked list GC    |
          +--------------------------------------------------------+
          | union vecsxp / listsxp / ...                           |
          |   - R_xlen_t length : Panjang vektor (64-bit int)      |
          |   - R_xlen_t truelength: Alokasi kapasitas internal    |
          +========================================================+
          | PAYLOAD DATA (Array Kontigu Langsung)                  |
          | [ byte 0 | byte 1 | byte 2 | ... | byte N ]            |
          +--------------------------------------------------------+
```

Struktur memori ini dibagi menjadi dua kategori alokasi utama di runtime R:
1. **Node Heap (Cons Cells / `ncells`):** Tempat penyimpanan struktur `SEXPREC` itu sendiri (berukuran tetap, 32 byte pada arsitektur 64-bit).
2. **Vector Heap (`vcells`):** Tempat data aktual/payload disimpan (misal: 1 juta float untuk `REALSXP`). Vector heap dialokasikan secara kontigu dalam blok 8-byte untuk menjaga keselarasan memori (*memory alignment*).

#### 3.2. Evolusi Mekanisme Modifikasi Data: Dari `NAMED` ke Reference Counting (`REFCNT`)
Hingga R 3.5.x, R menggunakan sistem `NAMED` heuristik (nilai: 0, 1, atau 2) yang sangat konservatif:
- `NAMED = 0`: Objek temporer, aman dimodifikasi di tempat (*in-place*).
- `NAMED = 1`: Objek hanya terikat pada satu nama variabel.
- `NAMED = 2`: Objek terikat lebih dari satu nama; setiap mutasi berikutnya **wajib menduplikasi memori penuh** (*Copy-on-Write*). Sekali mencapai 2, `NAMED` tidak pernah kembali ke 1.

Mulai R 3.6.0+, sistem *Reference Counting* formal (`REFCNT`) diperkenalkan:
- Setiap SEXP memiliki counter presisi 16-bit (`REFCNT(x)`).
- Ketika referensi dihapus (`rm()` atau keluar dari *lexical scope*), `REFCNT` dikurangi.
- Mutasi vektor hanya akan menduplikasi data payload jika `REFCNT > 1`. Jika `REFCNT == 1`, mutasi dilakukan *in-place* (modifikasi langsung di alamat memori yang sama), meminimalkan *memory pressure*.

#### 3.3. Framework ALTREP (Alternative Representations)
Diperkenalkan pada R 3.5.0, ALTREP mendefinisikan ulang vektor R dari sekadar "blok memori kontigu statis" menjadi antarmuka objek berbasis pointer fungsi (vtable). Sebuah kelas ALTREP memisahkan metadata vektor dari data aktualnya.

Kelas-kelas dasar ALTREP:
- **`Compact Sequences`:** Vektor seperti `1:1e9` tidak mengalokasikan 4 GB RAM, melainkan hanya 1 struct metadata yang menyimpan `start = 1`, `step = 1`, `length = 1e9` (hanya berukuran ~48 byte).
- **`Deferred String Conversions`:** Konversi string (misalnya dari representasi data berformat waktu atau JSON) ditunda sampai elemen individual diakses.
- **`Memory-Mapped Files`:** Menghubungkan langsung file biner di disk ke dalam ruang alamat virtual vektor R via `mmap()` (POSIX) atau `MapViewOfFile()` (Win32), melewati batasan RAM fisik.

#### 3.4. Level-Level Vektorisasi dan Hardware Interfacing
Vektorisasi dalam R bukanlah sekadar "menghilangkan loop `for`". Secara arsitektur, vektorisasi terbagi menjadi tiga lapis:
1. **R Interpreter Vectorization:** Loop dialihkan dari evaluasi interpretasi AST R ke C/Fortran primitives terkompilasi (`.Internal` / `.Primitive`). Ini memotong *overhead* evaluasi *dynamic type checking* pada setiap iterasi.
2. **Cache-line Contiguity:** Vektor primitif atomik R (`INTSXP`, `REALSXP`, `RAWSXP`) disimpan dalam memori kontigu. CPU membaca data dalam blok *Cache Line* (umumnya 64 byte). Komputasi loop dalam C yang mengakses data secara sekuensial memaksimalkan efisiensi *hardware prefetcher* CPU dan meminimalkan *L1/L2/L3 cache misses*.
3. **SIMD (Single Instruction, Multiple Data):** Kompilasi kode C/C++ modern yang mendasari R menggunakan instruksi prosesor AVX-256 atau AVX-512. Satu instruksi mesin memproses 4, 8, atau 16 elemen floating-point sekaligus dalam register CPU secara paralel.

---

### 4. Why & What

| Dimensi | Paradigma Naif (R Konvensional) | Paradigma Modern (Production-Engineered R) |
| :--- | :--- | :--- |
| **Why (Tujuan Desain)** | Kemudahan penulisan skrip analitis ad-hoc, mementingkan kemudahan sintaks daripada konsumsi sumber daya mesin. | Throughput deterministik, stabilitas pemrosesan data volume besar, pencegahan terminasi paksa oleh OS (*OOM Killer*). |
| **What: Alokasi Memori** | Duplikasi implisit (*hidden copies*) akibat `c()`, penambahan kolom bertahap pada `data.frame`, konversi tipe data implisit (*type coercion*). | Alokasi deterministik satu kali di awal (*pre-allocation*), manipulasi pointer memori, optimasi siklus hidup objek via ALTREP. |
| **What: Modifikasi** | Modifikasi fungsional murni menghasilkan alokasi memori $O(N)$ pada setiap mutasi. | Modifikasi *in-place* mutatif berbasis C/C++ API atau implementasi `data.table` yang memanfaatkan pointer address update. |
| **What: Komputasi** | Loop R berulang yang melakukan *dynamic type checking* dan alokasi objek temporer di setiap iterasi. | Eksekusi vektor terkompilasi (SIMD-enabled native code) yang beroperasi pada blok memori kontigu. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektural untuk mendiagnosis, memprofiling, dan mengoptimalkan representasi memori internal R:

```
[Mulai: Script / Pipeline Lambat & Boros Memori]
                         │
                         ▼
   [Langkah 1: Audit Duplikasi Memori Eksplisit & Implisit]
       - Gunakan lobstr::obj_addr() untuk verifikasi pointer.
       - Gunakan base::tracemem() untuk mendeteksi event duplikasi.
                         │
                         ▼
      [Apakah terjadi duplikasi tidak terduga?]
      ├──► YA ──► [Analisis Penyebab Duplikasi]
      │             - REFCNT > 1?
      │             - Modifikasi atribut (names, dim, class)?
      │             - Coercion tipe data (e.g., Integer -> Real)?
      │             │
      │             ▼
      │           [Refaktorisasi Alur Mutasi]
      │             - Pre-alokasi memori ukuran penuh.
      │             - Gunakan in-place memory replacement.
      │             - Tunda penetapan atribut hingga array final.
      │
      └──► TIDAK
             │
             ▼
   [Langkah 2: Evaluasi Skala Dataset vs Kapasitas RAM]
      ├──► Dataset > 80% RAM ──► [Implementasi ALTREP / Disk-Backed Memory Map]
      │                            - bigstatsr / fst / arrow memory mapping.
      │                            - Akses partisi data secara zero-copy.
      │
      └──► Dataset <= 80% RAM
             │
             ▼
   [Langkah 3: Vektorisasi Tingkat Rendah (SIMD & Cache Locality)]
       - Evaluasi bottleneck komputasi via profvis::profvis().
       - Tulis kernel C++ via cpp11 / Rcpp.
       - Hilangkan dynamic type checks; gunakan pointer traversal kontigu.
       - Enforce compiler auto-vectorization (-O3 -march=native -fopenmp).
                         │
                         ▼
   [Selesai: Pipeline Produksi Berkinerja Tinggi & Stabil]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan ruang penyimpanan logistik.
- **Pendekatan Naif (Copy-on-Write Berulang):** Anda memiliki palet berisi 1.000.000 kotak barang. Ketika Anda ingin mengubah label dari 1 kotak saja, sistem gudang membuat salinan penuh 1.000.000 kotak tersebut ke lorong gudang lain, mengubah label pada 1 kotak di salinan baru, lalu membuang palet lama ke tempat pembuangan sampah (*Garbage Collector*). Jika Anda mengulangi proses ini 1.000 kali, gudang akan runtuh akibat kehabisan ruang (*Out of Memory*).
- **Pendekatan ALTREP:** Anda tidak memindahkan barang fisik ke gudang. Anda hanya memiliki "buku manifes digital" yang memberi petunjuk: *"Data ini tersimpan di kontainer truk nomor 42 di pelabuhan. Saat prosesor Anda butuh kotak nomor 500.000, ambil langsung detik itu juga dari truk, proses, dan jangan simpan di lorong gudang utama."*

#### Diagram Arsitektur: Mutasi Standar vs Modifikasi In-Place C++ Pointer

```
SKENARIO A: Mutasi Naif di R (Copy-on-Write)
x <- 1:1000000; y <- x; y[1] <- 99L

[Alamat 0x001A] SEXP (INTSXP) ---> [Data: 1, 2, 3, ..., 1000000]
       ▲                 ▲
       │                 │
    Nama: x           Nama: y  (REFCNT = 2)

                    === Eksekusi: y[1] <- 99L ===

[Alamat 0x001A] SEXP (INTSXP) ---> [Data: 1, 2, 3, ..., 1000000] (x menunjuk ke sini)
[Alamat 0x009F] SEXP (INTSXP) ---> [Data: 99, 2, 3, ..., 1000000] (y diduplikasi ke alamat baru)


SKENARIO B: Operasi Mutasi Zero-Copy Melalui Pointer C++ (Rcpp/cpp11)
void update_direct(SEXP x) { int* ptr = INTEGER(x); ptr[0] = 99; }

[Alamat 0x001A] SEXP (INTSXP) ---> [Data: 1, 2, 3, ..., 1000000]
       ▲                               ▲
       │                               │
    Nama: x                      ptr dereference (Update in-place bitwise)
                                       ▼
                                 [Data: 99, 2, 3, ..., 1000000] (Tanpa Alokasi Baru)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Deteksi Duplikasi Memori & Evaluasi Alamat Pointer

```r
# Simple Example: Membedah Duplikasi Memori menggunakan tracemem & lobstr
library(lobstr)

# 1. Alokasi Vektor Besar
size <- 5e6 # 5 juta integer (~20 MB)
x <- integer(size)

cat("Alamat memori awal x:", obj_addr(x), "\n")
cat("Ukuran objek:", obj_size(x), "bytes\n")

# Aktifkan pelacakan memori native
tracemem(x)

# 2. Binding baru (Aliasing)
y <- x
cat("Alamat memori y setelah binding (Zero-Copy):", obj_addr(y), "\n")
# x dan y berbagi payload data yang persis sama di memori

# 3. Mutasi elemen memicu duplikasi karena REFCNT > 1
cat("--- Memulai Mutasi yang Memicu Duplikasi ---\n")
y[1] <- 42L
cat("Alamat memori baru y setelah mutasi:", obj_addr(y), "\n")

# Hentikan pelacakan
untracemem(x)

# 4. Bukti ALTREP Sequence Memory Footprint
compact_seq <- 1:1e9
cat("Ukuran 1 Miliar Integer via ALTREP:", obj_size(compact_seq), "bytes\n")
```

#### 7.2. Practical Example: Engine Vektorisasi Berkinerja Tinggi Menggunakan C++ Interop (`cpp11`)

Kode ini mengimplementasikan normalisasi Z-score dan Rolling Moving Average tanpa alokasi vektor temporer per-iterasi, berjalan langsung di level kontigu memori C++.

Simpan skrip C++ ini sebagai `kernel_engine.cpp`:

```cpp
#include <cpp11.hpp>
#include <cmath>
#include <algorithm>

using namespace cpp11;

[[cpp11::register]]
writable::doubles zscore_simd_inplace(doubles input) {
    R_xlen_t n = input.size();
    if (n == 0) return writable::doubles();

    // Pass 1: Hitung mean dengan penambahan kontigu
    double sum = 0.0;
    const double* src = REAL(input);
    for (R_xlen_t i = 0; i < n; ++i) {
        sum += src[i];
    }
    double mean = sum / n;

    // Pass 2: Hitung varians (Welford/Two-pass)
    double sq_diff_sum = 0.0;
    for (R_xlen_t i = 0; i < n; ++i) {
        double diff = src[i] - mean;
        sq_diff_sum += diff * diff;
    }
    double std_dev = std::sqrt(sq_diff_sum / (n - 1));

    // Alokasi memori output tepat SATU KALI
    writable::doubles output(n);
    double* dest = REAL(output);

    // Pass 3: Transformasi Z-score (Compiler auto-vectorizes this loop)
    double inv_std = 1.0 / std_dev;
    #pragma omp simd
    for (R_xlen_t i = 0; i < n; ++i) {
        dest[i] = (src[i] - mean) * inv_std;
    }

    return output;
}
```

Skrip orkestrator dan benchmark R:

```r
library(cpp11)
library(bench)

# Kompilasi C++ code on-the-fly
cpp_source("kernel_engine.cpp")

# Siapkan data pengujian skala menengah-besar (20 juta elemen float ~ 160 MB)
set.seed(42)
n_records <- 2e7
raw_data <- rnorm(n_records)

# Baseline: R murni (Vectorized idiomatic R)
r_vectorized_zscore <- function(x) {
  mu <- mean(x)
  sigma <- sd(x)
  (x - mu) / sigma # Menghasilkan setidaknya 2-3 vektor temporer di RAM
}

# Benchmark Performa & Konsumsi Memori
cat("Memulai eksekusi benchmark Z-Score...\n")
res <- bench::mark(
  r_base = r_vectorized_zscore(raw_data),
  cpp_kernel = zscore_simd_inplace(raw_data),
  iterations = 5,
  check = TRUE
)

print(res[, c("expression", "min", "median", "itr/sec", "mem_alloc", "n_gc")])
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Pemrosesan 40 Juta Baris Telemetri IoT Finansial pada Server RAM Terbatas
**Konteks Masalah:**
Sebuah platform analitik finansial harus memproses log transaksi harian sebesar 40.000.000 entri (ekuivalen ~3,2 GB data biner mentah). Server pemrosesan memiliki *hard memory limit* sebesar 4 GB RAM di kluster container Kubernetes. Jika penggunaan RAM melebihi 4 GB, kernel Linux mengirim sinyal `SIGKILL` (OOM Killer).

**Akar Masalah (Metode Naif):**
```r
# PENDEKATAN LAMA (FATAL: CRASH DENGAN ERROR OOM)
raw_df <- read.csv("daily_tick_data.csv") # Membutuhkan ~8-10 GB RAM karena overhead string & representasi SEXP data.frame

# Modifikasi bertahap (membuat copy berkali-kali)
raw_df$log_price <- log(raw_df$price)          # Copy 1
raw_df$norm_vol  <- raw_df$volume / 1000.0      # Copy 2
raw_df <- raw_df[raw_df$price > 0, ]           # Copy 3 (Full duplicated matrix)
```
Total memori yang dikonsumsi melonjak hingga 14 GB, langsung memicu OOM Killer Kubernetes.

**Solusi Rekayasa:**
1. Mengonversi data disk ke format serialisasi biner beralamat kontigu (`fst` atau format kolom Arrow) yang mendukung ALTREP.
2. Membaca dataset langsung menggunakan pemetaan *memory-mapped* (ALTREP zero-copy).
3. Melakukan seleksi dan komputasi in-place menggunakan referensi pointer C++ tanpa materialisasi penuh ke dalam memori kerja R.

```r
library(arrow)
library(dplyr)

# 1. Konversi data tabular disk menjadi format IPC/Feather (Memory-mappable format)
# (Langkah ini dapat dilakukan via streaming/chunking ingestion)
csv_path <- "daily_tick_data.csv"
feather_path <- "daily_tick_data.feather"

# Asumsi dataset telah berada dalam format biner yang mendukung zero-copy
# Membuka file menggunakan Memory-Mapped Dataset
mapped_table <- read_feather(feather_path, mmap = TRUE)

# Objek ini menggunakan ALTREP: Pembacaan kolom tidak mengalokasikan data ke heap R
# sebelum data tersebut benar-benar dievaluasi oleh SIMD instruction.

# 2. Pipeline Transformasi Tanpa Alokasi Menengah
optimized_pipeline <- function(mmap_data) {
  # Menggunakan Arrow compute kernels (C++ engine level) langsung di atas pointer ALTREP
  mmap_data %>%
    filter(price > 0) %>%
    mutate(
      log_price = log(price),
      norm_vol = volume / 1000.0
    ) %>%
    select(timestamp, instrument_id, log_price, norm_vol) %>%
    # Materialisasi terikat langsung ke streaming writer
    write_feather("daily_tick_data_processed.feather")
}

# Verifikasi: Memori virtual server stabil di bawah 800 MB selama eksekusi
optimized_pipeline(mapped_table)
```

---

### 9. Trade-offs

| Pendekatan Rekayasa | Keuntungan | Biaya / Kerugian | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Pure Vectorized Base R** | - Portabel tanpa compiler.<br>- Mudah didelegasikan ke tim analitik.<br>- Cukup cepat untuk skala $< 5 \text{ juta}$ baris. | - Mengalokasikan array temporer internal pada komputasi bertingkat.<br>- Boros memori jika operasi matematika berantai panjang. | Skrip pelaporan terjadwal, prototipe analitik cepat, batch harian skala kecil/menengah. |
| **In-place / C++ Native Engine (`cpp11` / `Rcpp`)** | - Kontrol penuh atas alokasi ($0$ bytes ekstra).<br>- Mendukung vectorization SIMD CPU.<br>- Waktu eksekusi mendekati batas teoritis hardware. | - Kerentanan terhadap *Memory Corruption* (Segmentation Fault).<br>- Menuntut tim memiliki kapabilitas C++ modern dan pemahaman siklus hidup GC. | Mesin komputasi inti, normalisasi real-time, streaming processing, latency-critical services. |
| **ALTREP / Memory Mapping Frameworks** | - Instant *load time* (0-second load metadata).<br>- Data berukuran ratusan gigabita dapat diakses pada RAM 4 GB.<br>- Mengurangi IO write-back cost. | - Latensi akses data acak (*random access*) terikat pada kecepatan IO disk (SSD/NVMe).<br>- Tidak semua fungsi eksternal R mendukung vektor non-materialized secara native. | Analisis time-series historis masif, platform pemodelan risiko, arsitektur microservice data. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Fragmentasi Memori Akibat Pertumbuhan Objek Berulang (*Dynamic Concatenation*)
```r
# FATAL: Kompleksitas Memori O(N^2) akibat Copy-on-Write
res <- numeric(0)
for (i in 1:1e5) {
  res <- c(res, i) # Mengalokasikan memori baru & menyalin ulang SELURUH elemen lama pada setiap iterasi!
}
```
*Solusi:*
```r
# Solusi Produksi: Pre-allocation O(N)
n <- 1e5
res <- numeric(n)
for (i in 1:n) {
  res[i] <- i # Mutasi in-place via reference counter optimizations
}
```

#### Mistake 2: Memicu Duplikasi Implisit Melalui Penulisan Atribut
Mengubah atribut seperti `names`, `colnames`, atau `dim` pada objek yang dibagikan (`REFCNT > 1`) akan menyalin seluruh payload data, meskipun isi numerik data tersebut tidak berubah sama sekali.

```r
a <- rnorm(1e7)
b <- a # b dan a berbagi alamat memori yang sama
names(b) <- paste0("V_", 1:1e7) # FATAL: Menyalin seluruh array double 80MB hanya untuk menyematkan atribut nama
```
*Troubleshooting:*
Selalu tetapkan atribut sebelum binding variabel dilakukan, atau gunakan representasi data berorientasi indeks (*index-based*) daripada menambahkan nama string individual pada vektor besar.

#### Mistake 3: Memory Leaks pada Persistent Worker Akibat R Generational GC
Pada aplikasi produksi jangka panjang (seperti worker Plumber API atau Celery R worker), R GC mungkin tidak langsung mengembalikan memori sistem operasi (*virtual memory unmapping*) meskipun objek telah dihapus via `rm()`. R mempertahankan alokasi heap untuk penggunaan berikutnya.
*Troubleshooting:*
- Lakukan pemanggilan eksplisit: `rm(huge_object); gc(full = TRUE)`.
- Jika memori OS tetap tidak turun (karena fragmentasi `glibc malloc`), jalankan worker di dalam arsitektur proses *forking-per-request* atau set environment variable `MALLOC_ARENA_MAX=2` untuk membatasi fragmentasi thread pool.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alokasi Deterministik:** Tidak boleh ada ekspresi `c(...)`, `cbind(...)`, atau `rbind(...)` di dalam loop komputasi. Ukuran alokasi harus dihitung di muka (*pre-allocated*).
- [ ] **Tipe Data Atomik Identik:** Pastikan literal numerik menyertakan penanda tipe eksplisit untuk menghindari koersi implisit (gunakan `0L` untuk integer, bukan `0` yang bertipe double).
- [ ] **Gunakan Matrix daripada Data Frame untuk Komputasi Homogen:** `data.frame` adalah kumpulan pointer SEXP (`VECSXP`), yang menyebarkan referensi ke seluruh memori dan merusak *cache locality*. Gunakan matriks dua dimensi (`REALSXP` atau `INTSXP`) yang menjamin tata letak memori 100% kontigu.
- [ ] **Batasi Penetapan Nama Elemen (`names`):** Hindari menamai vektor atomik yang memiliki lebih dari 100.000 elemen. Nama elemen memerlukan penyimpanan `CHARSXP` tambahan dan tabel hash yang secara signifikan memperbesar penggunaan memori heap.
- [ ] **Kompilasi C++ dengan Flag Arsitektur Spesifik:** Saat menyusun modul native C++, terapkan parameter kompilasi `-O3 -march=native -pipe` pada `~/.R/Makevars` untuk memastikan CPU target mengeksekusi instruksi SIMD optimal.
- [ ] **Konfigurasi Lingkungan GC:** Pada server produksi pemrosesan batch besar, atur `R_GC_MEM_GROW` untuk menghindari terlalu seringnya siklus pemindaian GC Gen-0 yang memperlambat throughput sistem.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/
└── m02/
    ├── Makefile
    ├── src/
    │   └── engine.cpp
    └── test_memory.R
```

#### Langkah 1: Siapkan Mesin Native C++ (`hands-on/m02/src/engine.cpp`)
Tulis implementasi C++ yang menangani filter vektor secara *zero-allocation* berbasis raw memory access.

```cpp
#include <cpp11.hpp>
using namespace cpp11;

[[cpp11::register]]
writable::doubles filter_threshold_cpp(doubles data, double threshold) {
    R_xlen_t n = data.size();
    const double* src = REAL(data);

    // Pass 1: Hitung jumlah elemen valid tanpa alokasi baru
    R_xlen_t count = 0;
    for (R_xlen_t i = 0; i < n; ++i) {
        if (src[i] > threshold) {
            count++;
        }
    }

    // Pass 2: Alokasikan memori hasil dengan ukuran presisi
    writable::doubles result(count);
    double* dest = REAL(result);

    R_xlen_t idx = 0;
    for (R_xlen_t i = 0; i < n; ++i) {
        if (src[i] > threshold) {
            dest[idx++] = src[i];
        }
    }

    return result;
}
```

#### Langkah 2: Buat Harness Pengujian & Profiling (`hands-on/m02/test_memory.R`)
```r
library(cpp11)
library(lobstr)
library(bench)

# 1. Kompilasi kernel
cpp11::cpp_source("src/engine.cpp")

# 2. Inisialisasi dataset pengujian masif
n <- 3e7 # 30 Juta baris (~240 MB)
cat("Mengalokasikan", n, "elemen...\n")
vec_source <- runif(n, min = 0, max = 100)

cat("Verifikasi Heap Address:", obj_addr(vec_source), "\n")
cat("Total RAM Vektor:", obj_size(vec_source) / 1024^2, "MB\n\n")

# 3. Pembanding R Murni
filter_r_native <- function(x, thresh) {
  x[x > thresh] # Melibatkan alokasi intermediate logical vector (~120 MB) + result vector
}

# 4. Eksekusi Analisis Profiling
cat("Menjalankan Benchmarking...\n")
bench_result <- bench::mark(
  Native_R = filter_r_native(vec_source, 50.0),
  Engine_CPP = filter_threshold_cpp(vec_source, 50.0),
  iterations = 3,
  check = TRUE
)

print(bench_result[, c("expression", "min", "median", "mem_alloc", "n_gc")])
```

#### Langkah 3: Eksekusi dan Audit
Jalankan skrip di atas via terminal:
```bash
cd hands-on/m02
Rscript test_memory.R
```
Perhatikan perbedaan kolom `mem_alloc` dan frekuensi eksekusi pembersihan sampah `n_gc`. Mesin native C++ mengeliminasi alokasi vektor logika perantara, sehingga mengurangi separuh konsumsi memori puncak (*peak memory*).

---

### 13. Exercise

#### Level Easy
Diberikan matriks $10.000 \times 100$ bertipe double:
```r
m <- matrix(rnorm(1e6), nrow = 10000, ncol = 100)
```
Identifikasi mengapa operasi berikut memicu duplikasi memori seluruh matriks, dan perbaiki kode tersebut agar beroperasi *in-place*:
```r
# Kode Bermasalah
for(j in 1:ncol(m)) {
  m[, j] <- m[, j] * 2.0
}
```

#### Level Medium
Buatlah sebuah fungsi C++ (menggunakan `cpp11` atau `Rcpp`) bernama `cumulative_sum_bounded(doubles x, double upper_limit)`.
- Input: Vektor numerik `x` dan batasan skalar `upper_limit`.
- Output: Vektor kumulatif yang nilainya otomatis di-reset menjadi $0$ seketika akumulasi melebihi `upper_limit`.
- **Constraint:** Fungsi harus mengalokasikan memori tepat satu kali untuk output vector ($O(1)$ allocation), tanpa pembuatan objek R temporer, dan menggunakan pointer kontinu dereferencing.

#### Level Hard
Rancang arsitektur ring buffer berputar (*circular ring buffer*) berbasis memori bersama menggunakan representasi `RAWSXP`.
- Buffer harus mampu menerima streaming data float 64-bit berkecepatan tinggi tanpa memicu Garbage Collection R sama sekali selama proses penulisan berlangsung (*zero garbage collection cycles*).
- Terapkan mekanisme pengabaian *copy-on-write* dengan memodifikasi payload pointer C internal secara aman melalui API native R.

---

### 14. Challenge

**Tantangan Sistem Produksi: Real-Time Anomaly Detector Berkapasitas 100 Juta Titik Data pada Anggaran RAM 1 GB**

**Spesifikasi Kasus:**
Sistem ingest telemetri Anda menerima aliran data deret waktu finansial dengan volume total 100.000.000 data point double-precision ($100 \times 10^6 \times 8 \text{ bytes} \approx 800\text{ MB}$).
Anda diberikan mesin kontainer dengan batasan absolut memori sebesar **1 GB RAM**.

Jika Anda melakukan pembacaan dan pemrosesan konvensional:
1. Membaca data ke dalam memory vector: $+800\text{ MB}$.
2. Menghitung *rolling exponential moving average* atau standard deviasi: $+800\text{ MB}$ (Total: $1.6\text{ GB} \rightarrow$ **KILLED BY OOM**).

**Tugas Arsitektur:**
1. Desain sistem end-to-end yang membaca data biner tersebut langsung dari disk menggunakan teknik *Zero-Copy ALTREP / Memory-Mapped Vector*.
2. Tulis kernel algoritma deteksi anomali (*Modified Double Exponential Smoothing*) dalam C++ yang langsung memproses *mapped pointer* tersebut secara streaming dengan pemanfaatan register AVX/SIMD CPU.
3. Seluruh proses tidak boleh mengonsumsi memori kerja (*Resident Set Size* / RSS) lebih dari **400 MB RAM** dari awal hingga akhir proses komputasi, dengan throughput minimal **10.000.000 data points per detik**.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. **Berapa ukuran tetap struktur metadata `SEXPREC` dasar pada arsitektur 64-bit di runtime R (di luar data payload)?**
   - A. 8 bytes
   - B. 16 bytes
   - C. 32 bytes
   - D. 64 bytes

2. **Apa yang secara spesifik disimpan oleh tipe internal `INTSXP` pada Vector Heap R?**
   - A. Array pointer string yang di-hash.
   - B. Elemen integer 32-bit bertanda (*signed*) yang tersusun secara kontigu di memori.
   - C. Pasangan linked list nilai dan pointer atribut.
   - D. Representasi floating point IEEE 754 presisi ganda 64-bit.

3. **Mekanisme apa yang bertanggung jawab mencegah penyalinan memori seketika objek ditugaskan ke variabel baru (`y <- x`)?**
   - A. Generational Garbage Collection.
   - B. Lazy Evaluation pada Environment.
   - C. Copy-on-Write (CoW) yang dikendalikan oleh pelacakan `REFCNT`.
   - D. Direct Memory Address Swapping.

4. **Karakteristik utama dari vektor yang diimplementasikan menggunakan framework ALTREP adalah:**
   - A. Selalu dikompilasi ke dalam bytecode assembly sebelum runtime.
   - B. Tidak dapat menerima atribut seperti dimensi atau nama kolom.
   - C. Datanya tidak harus dialokasikan secara penuh pada heap R saat vektor pertama kali dibuat.
   - D. Hanya dapat beroperasi pada tipe data karakter/string.

5. **Apa efek samping utama dari pemanggilan fungsi `names(x) <- c(...)` pada vektor numerik besar yang memiliki `REFCNT > 1`?**
   - A. Mengubah tipe data vektor atomik menjadi sebuah list heterogen.
   - B. Memicu duplikasi penuh seluruh data payload dari vektor tersebut ke alamat memori baru.
   - C. Me-reset pointer garbage collector ke status Generasi 0.
   - D. Mengonversi tipe representasi memori menjadi ALTREP sequence.

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)

6. **Mengapa matriks dua dimensi (`matrix`) memiliki performa komputasi dan akses memori yang jauh lebih tinggi dibandingkan `data.frame` dengan dimensi yang setara dalam algoritma numerik intensif?**
   - A. Matriks menggunakan multithreading native secara implisit di semua fungsi base R.
   - B. Data frame disimpan sebagai `VECSXP` (array of pointers ke vektor kolom terpisah), menyebabkan fragmentasi memori dan *cache misses*, sementara matriks adalah satu blok vektor kontigu tunggal di memori dengan atribut `dim`.
   - C. Matriks tidak didaftarkan ke dalam pelacakan Generational Garbage Collector.
   - D. Data frame membatasi operasi vektorisasi SIMD hanya pada tipe integer.

7. **Pada Generational Garbage Collector milik R, apa perbedaan siklus hidup antara objek yang berada di Generasi 0 (Gen 0) dan Generasi 2 (Gen 2)?**
   - A. Objek Gen 0 diperiksa dan dibersihkan pada setiap interval alokasi cepat, sementara objek Gen 2 telah bertahan dari beberapa siklus GC dan diperiksa jauh lebih jarang untuk menghemat siklus CPU.
   - B. Objek Gen 0 disimpan di swap disk, sedangkan objek Gen 2 berada di CPU L1 Cache.
   - C. Objek Gen 2 merupakan memori yang dialokasikan oleh library C pihak ketiga di luar kendali R runtime.
   - D. Objek Gen 0 hanya dapat dialokasikan menggunakan framework ALTREP.

8. **Manakah dari potongan kode R berikut yang TIDAK memicu duplikasi memori payload saat dieksekusi?**
   - A. `x <- 1:1e6; y <- x; y[1] <- 100L`
   - B. `x <- integer(1e6); x[1] <- 10L` (asumsi `REFCNT(x) == 1`)
   - C. `df <- data.frame(a = 1:1e6); df$a[1] <- 10L`
   - D. `m <- matrix(1:1e6, nrow=1000); rownames(m) <- paste0("R", 1:1000)`

9. **Ketika menulis ekstensi native C++ via `cpp11`, apa fungsi instruksi macro `#pragma omp simd` pada loop iterasi data kontigu?**
   - A. Mengunci thread CPU agar thread lain tidak dapat mengakses pointer memori.
   - B. Menginstruksikan compiler untuk mengonversi loop skalar menjadi instruksi perangkat keras SIMD vektor paralel (e.g., AVX) jika arsitektur CPU mendukungnya.
   - C. Memaksa objek SEXP untuk diduplikasi sebelum dievaluasi.
   - D. Mematikan Generational GC R selama loop berjalan.

10. **Apa kegunaan fungsi C-level `DATAPTR()` pada sistem vektor kontigu dan ALTREP modern di R?**
    - A. Menghapus referensi pointer dari node heap.
    - B. Mengambil pointer memori baca/tulis langsung ke payload data dasar, yang jika dipanggil pada objek ALTREP dapat memicu materialisasi memori secara penuh jika tidak ditangani dengan benar.
    - C. Mengonversi tipe data numerik float menjadi string integer tanpa komputasi.
    - D. Membatasi penulisan array agar read-only.

#### Bagian 3: Skenario Kasus Produksi (Analisis Masalah Sistem)

11. **Skenario Kasus A:**
    Sebuah worker proses batch analitik mengeksekusi fungsi kalkulasi matriks korelasi harian pada server cloud. Meskipun dataset input setiap harinya berukuran konstan (~500 MB), Anda melihat metrik memori kontainer terus meningkat secara bertahap setiap kali pipeline selesai memproses satu batch, hingga akhirnya mencapai batas 8 GB dan mengalami crash setiap akhir pekan. Perintah `gc()` telah ditambahkan di akhir loop utama, namun memori sistem (RSS) yang dilaporkan sistem operasi tidak pernah turun kembali ke titik awal.
    **Pertanyaan Analisis:** Mengapa penambahan `gc()` tidak menurunkan penggunaan memori virtual di tingkat OS, dan arsitektur alokasi memori apa di level runtime C library (`glibc`) yang menyebabkan fenomena ini?

12. **Skenario Kasus B:**
    Tim data engineering Anda melaporkan bahwa sebuah fungsi kustom `clean_ticks()` berjalan 50x lebih lambat ketika dipanggil dari dalam skrip pipeline utama dibandingkan ketika diuji pada baris perintah R terminal secara mandiri dengan input data tiruan yang identik. Pemeriksaan awal menunjukkan bahwa input ke fungsi tersebut di dalam pipeline utama adalah subset dari list bersarang: `data_pipeline$market_data$ticks`.
    **Pertanyaan Analisis:** Berdasarkan arsitektur pelacakan referensi (`REFCNT` / `NAMED`), jelaskan fenomena internal yang menyebabkan degradasi performa drastis ini dan bagaimana cara mengatasinya secara elegan tanpa menulis ulang logika pembersihan data.

13. **Skenario Kasus C:**
    Sebuah aplikasi real-time dashboard analitik memuat file time-series berukuran 12 GB menggunakan framework pembacaan berbasis memory mapping (ALTREP enabled). Pada saat server berjalan normal, latensi pembacaan data sangat instan (< 1 milidetik). Namun, setiap kali server mengalami beban baca tinggi dari puluhan pengguna bersamaan, server tiba-tiba membeku (*system freeze*) dan latensi melonjak hingga puluhan detik, meskipun monitor RAM fisik menunjukkan penggunaan memori pengguna hanya sebesar 20%.
    **Pertanyaan Analisis:** Jelaskan apa yang terjadi di tingkat kernel sistem operasi (terkait *Page Faults*, *Virtual Memory*, dan *Disk Thrashing*) ketika beberapa thread mengakses area acak yang berbeda dari file yang di-memory map tersebut.

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **C** (Struktur `SEXPREC` pada arsitektur 64-bit berukuran 32 byte, terdiri dari bitfield `sxpinfo` 4 byte, 3 pointer atribut/GC 24 byte, dan padding/union header).
2. **B** (Tipe `INTSXP` memetakan langsung array integer bertanda 32-bit di memori C).
3. **C** (`REFCNT` melacak jumlah referensi. Ketika `REFCNT == 1`, mutasi dapat terjadi in-place; ketika `REFCNT > 1`, duplikasi CoW baru dipicu).
4. **C** (ALTREP memisahkan representasi data dari interface vektor, memungkinkan data dihitung secara dinamis atau di-map langsung dari disk tanpa alokasi penuh di RAM).
5. **B** (Atribut merupakan bagian dari metadata SEXP; memperbarui atribut pada objek bersama akan memicu penyalinan payload penuh agar tidak merusak metadata variabel lain yang menunjuk ke array yang sama).

#### Bagian 2: Intermediate
6. **B** (Matriks menjamin *spatial cache locality* karena seluruh data terletak pada satu memori kontigu, sedangkan data frame mendistribusikan kolom sebagai pointer terpisah yang memicu lompatan alamat memori dan *cache misses*).
7. **A** (Generational GC R mengelompokkan objek berdasarkan usia alokasi. Objek Gen 0 dipindai sangat sering, sedangkan objek Gen 2 diasumsikan stabil dan jarang dipindai guna menekan overhead CPU).
8. **B** (Karena `x` dialokasikan secara eksklusif dan tidak di-binding ke variabel lain, `REFCNT` bernilai 1, memungkinkan mutasi indeks array dilakukan secara in-place tanpa alokasi).
9. **B** (Pragma tersebut memberi tahu compiler untuk mengaktifkan SIMD vectorization pada loop target).
10. **B** (`DATAPTR()` mengembalikan pointer memori langsung. Pada ALTREP, jika objek belum termaterialisasi di RAM, pemanggilan fungsi ini akan memaksa data dimuat ke memori fisik secara penuh, meniadakan efisiensi zero-copy).

#### Bagian 3: Panduan Jawaban Skenario Produksi
11. **Analisis Kasus A:**
    R runtime menggunakan alokator memori standar sistem (`glibc malloc` pada Linux). Ketika objek besar dialokasikan dan dihapus melalui `gc()`, memori dikembalikan ke heap milik R runtime, bukan secara otomatis di-unmap (`brk`/`sbrk` atau `munmap`) ke kernel sistem operasi. Hal ini terjadi karena fragmentasi memori: jika sebuah chunk kecil memori di ujung atas heap masih aktif, alokator C tidak dapat menurunkan ambang batas break heap ke OS. Akibatnya, Resident Set Size (RSS) terlihat terus meningkat di level monitor sistem operasi (memory retention). Solusi arsitekturnya adalah mengisolasi pemrosesan batch ke dalam worker transien (*forked processes*) yang diakhiri secara berkala, atau mengonfigurasi alokator memori alternatif seperti `jemalloc` yang lebih agresif dalam mengembalikan *dirty pages* ke kernel.
12. **Analisis Kasus B:**
    Pada skrip terminal mandiri, objek diuji dalam kondisi terisolasi dengan `REFCNT == 1`. Pada kondisi ini, operasi manipulasi vektor di dalam fungsi berjalan secara mutasi in-place. Namun, saat objek berasal dari struktur bersarang (`data_pipeline$market_data$ticks`), referensi objek tersebut dipegang oleh environment induk dan list penampungnya, sehingga `REFCNT > 1`. Setiap kali fungsi `clean_ticks()` melakukan mutasi elemen array terkecil sekalipun, runtime R mendeteksi adanya aliasing dan memicu duplikasi penuh seluruh struktur memori (*deep copy*) pada setiap iterasi. Solusinya: ekstrak objek ke variabel lokal terisolasi dan putus referensinya dari list induk sebelum mutasi dilakukan, atau gunakan operasi berbasis pointer C++/`data.table` yang secara eksplisit melakukan update in-place tanpa terhalang pelacakan referensi hierarkis.
13. **Analisis Kasus C:**
    Pada ALTREP memory-mapped files, data sebenarnya berada di penyimpanan disk (SSD/NVMe) dan dipetakan ke Virtual Memory Space via kernel Page Table. Ketika banyak pengguna melakukan akses acak (*random access*) secara konkuren ke bagian file yang belum termuat di RAM, sistem operasi mengalami lonjakan *Major Page Faults*. Kernel terpaksa menghentikan eksekusi thread untuk membaca halaman memori 4KB dari disk secara fisik. Jika IO bandwidth disk jenuh (*I/O bottleneck*), terjadi fenomena *Disk Thrashing*: CPU menghabiskan seluruh waktunya menunggu antrean I/O disk selesai alih-alih mengeksekusi komputasi data, menyebabkan latensi melonjak drastis dan sistem terlihat membeku meskipun alokasi memori fisik R masih rendah.

---

### 16. Summary

1. **SEXP & Memory Layout:** Seluruh objek R adalah pointer ke struktur `SEXPREC` di level C. Pemrosesan performa tinggi memerlukan pemahaman mendalam tentang pemisahan antara alokasi *Node Heap* (metadata) dan *Vector Heap* (kontigu numerik payload) untuk memaksimalkan *cache locality*.
2. **Copy-on-Write Kontemporer:** Sistem pelacakan mutasi R telah berevolusi dari heuristik `NAMED` menjadi sistem *Reference Counting* (`REFCNT`) presisi. Menghindari duplikasi memori $O(N)$ bergantung pada kemampuan programmer menjaga `REFCNT == 1` atau mendelegasikan modifikasi langsung melalui pointer layer C/C++.
3. **Revolusi ALTREP:** Framework ALTREP mendisrupsi paradigma komputasi in-memory R klasik dengan memungkinkan manipulasi objek masif melalui metadata tanpa materialisasi fisik ke RAM. Ini membuka jalan bagi integrasi zero-copy dengan format disk terstruktur seperti Arrow, Feather, dan binary mapped files.
4. **Vektorisasi SIMD Native:** Vektorisasi optimal tercapai bukan semata dengan menghindari loop di R, melainkan memastikan eksekusi komputasi memori kontigu pada native code (C++) yang dioptimalkan oleh instruksi SIMD prosesor (AVX/SSE) dengan alokasi memori deterministik tunggal di awal proses.