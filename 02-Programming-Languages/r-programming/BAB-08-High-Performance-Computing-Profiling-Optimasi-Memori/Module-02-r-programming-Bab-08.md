# Kurikulum Enterprise R Programming: Bab 08 - Modul 02
## Topik: High-Performance Computing (HPC), Profiling, & Optimasi Memori Tingkat Lanjut

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal R Memory Model**: Menjelaskan struktur C-level `SEXP`, mekanisme pointer, sistem Garbage Collection generasi 0/1/2, dan optimasi *Alternative Representations* (ALTREP).
- **Mendiagnosis Kemacetan Komputasi**: Menjalankan profiling deterministik dan statistik menggunakan `bench`, `profvis`, dan `tracemem` untuk mengisolasi alokasi memori berlebih (*memory churn*) dan latensi CPU tak terkendali.
- **Mengeliminasi *Copy-on-Modify***: Merancang transformasi data yang mempertahankan semantik *in-place modification* dan meminimalkan duplikasi buffer heap.
- **Mengintegrasikan Komputasi Native Berkecepatan Tinggi**: Mengembangkan fungsi C++ tingkat lanjut via `Rcpp` dan `cpp11` yang memanfaatkan referensi memori langsung (*zero-copy pass-through*).
- **Membangun Pipeline Paralel Terdistribusi**: Mengimplementasikan arsitektur *multiprocessing* menggunakan framework `future` dan `parallel`, mengelola *Inter-Process Communication* (IPC), dan menghindari perangkap *fork-unsafe* pada lingkungan produksi enterprise.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, Anda wajib memahami:
- Sintaksis dasar dan lanjutan R (struktur vektor, *list*, *environment*, S3/S4 OOP).
- Konsep dasar arsitektur sistem komputer: *Heap vs Stack*, *CPU Cache Line* (L1/L2/L3), *Pointers*, dan sinyal proses POSIX.
- Pengetahuan dasar C/C++ (tipe data primitif, pointer, referensi `&`, dan kompilasi *toolchain* seperti `gcc`/`clang`).
- Familiaritas dengan shell Linux/UNIX dan manajemen proses (`top`, `htop`, batas memori `cgroups`).

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Struktur Data Internal R: C-Level SEXP
Di balik abstraksi R, seluruh objek (vektor, fungsi, *environment*, *promise*) direpresentasikan oleh satu struktur data C tunggal bernama `SEXP` (*S-Expression Pointer*). Objek `SEXP` adalah pointer ke union `SEXPREC`.

```c
/* Representasi Konseptual SEXPREC pada r-source/src/include/Rinternals.h */
struct SEXPREC {
    SEXPREC_HEADER header;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;
        struct envsxp_struct envsxp;
        struct closxp_struct closxp;
        struct promsxp_struct promsxp;
        struct vecsxp_struct vecsxp; /* Mengelola Vektor (INTSXP, REALSXP, dll.) */
    } u;
};

struct SEXPREC_HEADER {
    sxpinfo_node sxpinfo; /* Bitfields: tipe objek, mark GC, tingkat REFCNT */
    struct SEXPREC *attrib; /* Atribut objek (names, class, dim, dll.) */
    struct SEXPREC *gengc_next_node;
    struct SEXPREC *gengc_prev_node;
};
```

Setiap alokasi vektor di R menempati dua area memori:
1. **Node Header (`SEXPREC`)**: Berada di dalam *Node Pool* R (memori terkelola R dengan ukuran tetap, biasanya 32 byte pada arsitektur 64-bit).
2. **Vector Data Buffer**: Alokasi array mentah bertipe skalar yang dialokasikan di *Heap* melalui *R Vector Heap* (`Vcells`).

#### 3.2. Copy-on-Modify (CoM) dan Evolusi Pelacakan Pointer (`REFCNT`)
R menggunakan semantik *pass-by-value* secara visual, namun diimplementasikan sebagai *lazy evaluation* dengan *Copy-on-Modify*. 
- Sebelum R 3.1.0, R menggunakan sistem `NAMED` (skala 0, 1, 2) yang sangat konservatif: jika objek pernah di-assign (`NAMED == 2`), R akan menduplikasi objek seutuhnya saat mutasi, memicu lonjakan penggunaan memori.
- Sejak R 3.1.0 (dan disempurnakan di R 4.0+), R mengimplementasikan **Reference Counting (`REFCNT`)**. Setiap header objek menyimpan hitungan berapa banyak pointer/simbol yang merujuk padanya:
  - `REFCNT == 0`: Objek sementara (dapat langsung dimodifikasi *in-place* atau di-*garbage collect*).
  - `REFCNT == 1`: Objek unik. Mutasi langsung dilakukan pada buffer yang ada (*in-place modification*) tanpa alokasi baru.
  - `REFCNT > 1`: Objek dibagikan. Mutasi akan memicu deep copy buffer vector, menduplikasi data, menurunkan `REFCNT` objek asal, dan menginisialisasi buffer baru dengan `REFCNT = 1`.

#### 3.3. Arsitektur Garbage Collector (GC): Generational Mark-and-Sweep
R mengadopsi *Generational Garbage Collector* 3 generasi (Gen 0, Gen 1, Gen 2):
- **Gen 0 (Ephemeral)**: Objek baru yang dialokasikan dalam siklus eksekusi lokal (variabel sementara fungsi).
- **Gen 1**: Objek yang selamat dari satu siklus pembersihan Gen 0.
- **Gen 2 (Old/Tenured)**: Objek yang selamat dari pembersihan berulang (misal: paket yang dimuat, data frame global).

Siklus GC dipicu secara otomatis ketika batas alokasi memori (*heap trigger limit*) terlampaui. GC memicu penangguhan eksekusi R (*Stop-the-World pause*). Jika kode Anda mengalokasikan jutaan vektor kecil di dalam loop, GC Gen 0 akan berjalan terus-menerus, menyebabkan latensi CPU tinggi meski penggunaan memori puncak terlihat rendah.

#### 3.4. Framework ALTREP (Alternative Representations)
Diperkenalkan pada R 3.5.0, ALTREP mengubah mekanisme representasi vektor di R. Vektor tidak lagi wajib berupa alokasi array sekuensial penuh di RAM:
- Vektor urutan integer sederhana `1:1e9` tidak lagi mengalokasikan 4 GB RAM. ALTREP hanya menyimpan parameter titik awal (`1`), kenaikan (`1`), dan panjang (`1.000.000.000`). Ukuran memorinya konstan: 48 byte.
- ALTREP memungkinkan pembacaan berkas (seperti string dari file CSV atau array biner dari Apache Arrow/Parquet) dipetakan via *Memory-Mapped Files* (`mmap`), menunda alokasi RAM hingga elemen data benar-benar diakses (*lazy loading*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional R | Pendekatan High-Performance Engineering |
| :--- | :--- | :--- |
| **Model Eksekusi** | Single-threaded interpreter, serial execution. | Multi-threaded native compute (OpenMP) + asynchronous multi-process. |
| **Manipulasi Memori** | Mengandalkan *implicit copying* melalui sub-setting `df[i, ] <- ...`. | *Zero-copy mutation* (`data.table` by-reference `:=`), ALTREP, dan buffer pointer. |
| **Karakteristik Bottleneck**| Terjebak pada GC thrashing akibat alokasi loop dinamis. | Vektorisasi SIMD, alokasi statis di awal (*pre-allocation*), atau translasi C++ native. |
| **I/O Storage Interface** | Serialisasi standar `read.csv()`, `saveRDS()`. | Format *binary column-oriented* terkompresi via IPC (`Arrow`, `fst`). |

R dirancang oleh ahli statistik untuk interaktivitas, bukan rekayasa performa tinggi *out-of-the-box*. Namun, fondasi R adalah C. Mengetahui batasan dan titik pintas internal R memungkinkan kita mengeksekusi komputasi data skala gigabyte hingga terabyte dengan efisiensi yang setara dengan C++ atau Rust.

---

### 5. How (Workflow Profiling & Optimasi)

Berikut adalah siklus hidup rekayasa performa sistem R di lingkungan produksi:

```
[1. Baseline Benchmarking] 
       │ (bench::mark)
       ▼
[2. Profiling Statistik & Alokasi]
       │ (profvis / Rprof)
       ├─────────────────────────────────┐
       ▼ [Memory-bound: GC Thrashing]    ▼ [CPU-bound: Hot Loops]
[3A. Audit Pointer & CoM]         [3B. Vektorisasi Algoritmik]
       │ (tracemem / lobstr)             │ (SIMD / C++ Rcpp/cpp11)
       ▼                                 ▼
[4A. Implementasi ALTREP / In-Place] [4B. Paralelisasi Worker Process]
       │ (`data.table` / `arrow`)         │ (`future` topology)
       └────────────────┬────────────────┘
                        ▼
[5. Validasi Regresi & cgroups Verification]
```

1. **Baseline Benchmarking**: Tetapkan metrik awal menggunakan paket `bench`. Jangan gunakan `Sys.time()` yang memiliki resolusi timer rendah dan mengabaikan intervensi GC.
2. **Profiling**: Jalankan `profvis` untuk mengekstraksi *Flame Graph*. Identifikasi apakah waktu komputasi terkonsumsi pada eksekusi kode atau *overhead* garbage collection (`<GC>`).
3. **Audit Memory Duplication**: Pasang pelacak `base::tracemem()` pada objek utama untuk mendeteksi baris kode spesifik yang memicu penggandaan pointer memori.
4. **Intervensi Khusus**:
   - Jika *CPU-bound*: Pindahkan algoritma perulangan rekursif ke C++ via `Rcpp` atau implementasikan OpenMP.
   - Jika *Memory-bound*: Terapkan sintaks *by-reference* atau petakan data besar via disk-backed *memory mapping*.
5. **Verifikasi Produksi**: Uji beban kode di dalam Docker container dengan limit CPU dan memori berbasis Linux `cgroups`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan dan Mesin Fotokopi
Bayangkan memori R seperti perpustakaan:
- **Konvensional (Copy-on-Modify)**: Anda meminjam buku ensiklopedia seberat 10 kg. Anda hanya ingin mengganti satu kata pada halaman 400. Alih-alih mencoret halaman tersebut, staf perpustakaan memfotokopi seluruh isi 1.000 halaman buku tersebut, menaruhnya di meja baru, mengubah satu kata itu, dan membuang buku lama ke tempat sampah daur ulang (Garbage Collector).
- **Arsitektur Produksi (In-Place & Zero-Copy)**: Staf perpustakaan memberi Anda izin mengubah langsung tinta pada halaman 400 di buku aslinya tanpa menyentuh halaman lain, tanpa duplikasi, dan tanpa membebani fasilitas daur ulang.

#### Diagram Arsitektur Internal: Memory Copy vs In-Place Pointer Manipulation

```
KASUS A: Copy-on-Modify (Inisiator Latensi & GC Pressure)

Simbol "df1" ──► [SEXPREC Header: REFCNT=2] ──► [ Data Buffer: 10M Baris (Heap: 800MB) ]
                                      ▲
Simbol "df2" ─────────────────────────┘
                                      │
Tindakan: df2$col_a[1] <- 999         │
                                      ▼ (Memicu Deep Copy Otomatis)
Simbol "df1" ──► [SEXPREC Header: REFCNT=1] ──► [ Data Buffer: 10M Baris (Asli: 800MB) ]
Simbol "df2" ──► [SEXPREC Header: REFCNT=1] ──► [ Data Buffer Baru (Duplikat: 800MB) ]
                                                Total Alokasi Heap: 1.6 GB!

───────────────────────────────────────────────────────────────────────────────────────

KASUS B: In-Place Modification (data.table `:=` atau C++ Direct Pointer)

Simbol "dt1" ──► [SEXPREC Header: REFCNT=1] ──► [ Data Buffer: 10M Baris (Heap: 800MB) ]
                                      │
Tindakan: dt1[, col_a := 999]         │ (In-place direct pointer memory write)
                                      ▼
Simbol "dt1" ──► [SEXPREC Header: REFCNT=1] ──► [ Data Buffer: 10M Baris (Heap: 800MB) ]
                                                Total Alokasi Heap Tetap: 800 MB.
```

---

### 7. Code Implementation: Simple vs Practical Example

#### 7.1. Simple Example: Deteksi Mutasi Memori & Profiling Alokasi

```r
# Prasyarat: install.packages(c("bench", "lobstr"))
library(bench)
library(lobstr)

# 1. Mendeteksi Copy-on-Modify secara Transparan
x <- integer(1e6) # Vektor 1 juta integer (~4 MB)
cat("Alamat memori awal:", lobstr::obj_addr(x), "\n")

# Aktifkan pelacakan memori native
tracemem(x)

# Modifikasi via copy-on-modify standar
y <- x
cat("Alamat memori y sebelum mutasi (shared):", lobstr::obj_addr(y), "\n")

# Memodifikasi elemen pertama memicu copy karena REFCNT > 1
y[1] <- 42L
cat("Alamat memori y setelah mutasi:", lobstr::obj_addr(y), "\n")

untracemem(x)

# 2. Benchmarking Komparatif: Profiling Efisiensi Alokasi Memori
benchmark_alokasi <- bench::mark(
  loop_tanpa_prealokasi = {
    vec <- integer(0)
    for (i in 1:1e4) {
      vec <- c(vec, i) # Buruk: Memori di-reallokasi berulang kali
    }
    vec
  },
  loop_dengan_prealokasi = {
    vec <- integer(1e4) # Optimal: Alokasi statis 1 kali
    for (i in 1:1e4) {
      vec[i] <- i
    }
    vec
  },
  vektorisasi_murni = {
    1:1e4 # Zero-allocation ALTREP
  },
  iterations = 20,
  check = TRUE
)

print(benchmark_alokasi[, c("expression", "min", "median", "mem_alloc", "n_gc")])
```

#### 7.2. Practical Example: High-Throughput Batch Processing & Rcpp Kernel
Skenario: Memproses komputasi kalkulasi moving average berbobot (*exponentially weighted sliding window*) pada matriks deret waktu skala enterprise tanpa alokasi memori redundan.

Simpan modul C++ berikut pada file: `kernel_engine.cpp`
```cpp
#include <Rcpp.h>
using namespace Rcpp;

// [[Rcpp::plugins(openmp)]]
// [[Rcpp::export]]
NumericVector compute_weighted_ma_cpp(const NumericVector& data, double alpha, int window) {
    int n = data.size();
    if (window > n || window <= 0) {
        stop("Parameter window berada di luar batas array.");
    }
    
    // Alokasi memori output tepat satu kali
    NumericVector result(n - window + 1);
    
    // Optimasi pointer direct memory access
    const double* p_data = data.begin();
    double* p_res = result.begin();
    
    for (int i = 0; i <= n - window; ++i) {
        double weighted_sum = 0.0;
        double weight_factor = 1.0;
        double sum_weights = 0.0;
        
        for (int j = 0; j < window; ++j) {
            double current_weight = std::pow(1.0 - alpha, j);
            weighted_sum += p_data[i + (window - 1 - j)] * current_weight;
            sum_weights += current_weight;
        }
        p_res[i] = weighted_sum / sum_weights;
    }
    
    return result;
}
```

File Utama R: `pipeline_production.R`
```r
library(Rcpp)
library(future)
library(future.apply)
library(data.table)

# Kompilasi native kernel C++ secara dynamic
Rcpp::sourceCpp("kernel_engine.cpp")

# Implementasi Native R untuk perbandingan arsitektural
compute_weighted_ma_r <- function(data, alpha, window) {
  n <- length(data)
  res <- numeric(n - window + 1)
  weights <- (1 - alpha)^(0:(window - 1))
  sum_w <- sum(weights)
  weights_rev <- rev(weights)
  
  for (i in seq_len(n - window + 1)) {
    # Memicu alokasi slice sementara pada RAM secara agresif
    window_data <- data[i:(i + window - 1)]
    res[i] <- sum(window_data * weights_rev) / sum_w
  }
  return(res)
}

# Inisialisasi Dataset Simulasi Skala Besar
set.seed(42)
n_ticks <- 1e6
raw_series <- cumsum(rnorm(n_ticks))

cat("Memulai audit performa komputasi...\n")

# Benchmark Eksekusi Single-Thread
bench_results <- bench::mark(
  Implementasi_R = compute_weighted_ma_r(raw_series[1:50000], alpha = 0.1, window = 50),
  Implementasi_Rcpp = compute_weighted_ma_cpp(raw_series[1:50000], alpha = 0.1, window = 50),
  iterations = 5,
  check = TRUE
)
print(bench_results[, c("expression", "median", "mem_alloc", "n_gc")])

# Pipeline Paralelisasi Asinkron Skala Enterprise
cat("\nMenjalankan Multiprocessing Topology via 'future'...\n")

# Konfigurasi worker topology berbasis ketersediaan core CPU mesin
future::plan(multisession, workers = max(1, parallel::detectCores() - 1))

# Simulasi partisi data shard berukuran besar
n_shards <- 4
shard_size <- n_ticks / n_shards
shards <- split(raw_series, ceiling(seq_along(raw_series) / shard_size))

# Pemrosesan parallel asynchronous non-blocking
start_time <- Sys.time()
futures_list <- future.apply::future_lapply(shards, function(shard) {
  compute_weighted_ma_cpp(shard, alpha = 0.05, window = 100)
}, future.seed = TRUE)

total_duration <- Sys.time() - start_time
cat(sprintf("Selesai memproses %d records lintas %d shards paralel. Waktu: %.2f detik\n", 
            n_ticks, n_shards, as.numeric(total_duration, units = "secs")))

# Bersihkan resources cluster
future::plan(sequential)
```

---

### 8. Real World Case Study: Financial High-Frequency Tick Risk Engine

#### 8.1. Konteks Masalah
Sebuah firma *quantitative trading* mengelola data pergerakan order-book pasar saham (50 juta baris per batch, sekitar 4.8 GB di disk). Sistem lama dibangun menggunakan loop R native dan dataframe `base`, memicu crash Out-of-Memory (OOM) pada container Kubernetes (memory limit 16 GB), dengan latensi eksekusi melebihi 18 menit.

#### 8.2. Root Cause Analysis (RCA) via Profiling
Profiling menggunakan `profvis` mengungkap dua titik kegagalan utama:
1. Mutasi kolom metrik volatilitas menggunakan `df$volatility[i] <- ...` menyebabkan deep-copy seluruh 50 juta record setiap 100 iterasi. Alokasi kumulatif melampaui 120 GB memori virtual, memaksa OS melakukan paging ke swap memory hingga container terbunuh oleh Linux OOM Killer.
2. Komputasi matriks korelasi menggunakan array R native memicu siklus GC Gen 0 yang menghentikan prosesor (*stop-the-world*) sebanyak 4.200 kali selama eksekusi.

#### 8.3. Desain Solusi Arsitektural
1. **Memory-Mapped Storage Layer**: Data dimuat menggunakan Apache Arrow (`arrow::read_feather()`), memanfaatkan IPC buffer berbasis ALTREP langsung dari NVMe SSD tanpa overhead alokasi RAM.
2. **Zero-Copy In-Place Mutator**: Modifikasi kolom diganti total menggunakan referensi pointer `data.table` (`:=`).
3. **C++ SIMD Vectorization Engine**: Perhitungan Value at Risk (VaR) dan kalkulasi rolling standard deviation didelegasikan ke shared library C++ dengan vektorisasi SIMD OpenMP.
4. **Isolated Process Pooling**: Penggunaan `parallel::makeCluster(type = "PSOCK")` untuk isolasi worker, mencegah *memory leakage* antar siklus trading harian.

#### 8.4. Hasil Metrik Produksi

| Metrik | Arsitektur Lama (Base R Pipeline) | Arsitektur Baru (Arrow + C++ + PSOCK) | Peningkatan |
| :--- | :--- | :--- | :--- |
| **Peak Memory Consumption** | > 16.0 GB (OOM Crash) | 2.1 GB Stable | **7.6x Lebih Hemat** |
| **Total Pipeline Latency** | ~18 Menit (jika RAM 64GB) | 14.8 Detik | **~73x Lebih Cepat** |
| **Garbage Collection Pauses**| 4.238 interupsi | 12 interupsi | **99.7% Penurunan GC** |
| **Container Scalability** | Gagal scale-out pada node 16GB | Stabil di node 4GB | **Reduksi Biaya Cloud 75%** |

---

### 9. Trade-offs Architecture Analysis

| Parameter Arsitektur | Fork-based Multiprocessing (`fork`) | Socket-based Multiprocessing (`psock`) | C++ In-Process Multi-threading (OpenMP) |
| :--- | :--- | :--- | :--- |
| **Overhead Inisialisasi** | Sangat Rendah (instan via COW OS). | Tinggi (harus spawn proses R baru dan kirim data). | Hampir Nol (alokasi thread pool instan). |
| **Kompatibilitas OS** | POSIX only (Linux/macOS). crash pada GUI/RStudio. | Lintas Platform (Linux, Windows, macOS). | Lintas Platform (tergantung dukungan compiler). |
| **Konsumsi Memori** | Menggunakan Copy-on-Write (efisien awal, bahaya fragmentasi). | Tinggi (tiap worker menduplikasi R environment dasar ~40-80MB). | Nol overhead proses R; berbagi ruang heap address space secara langsung. |
| **Safety / Kestabilan** | Rentan dead-lock jika thread library C++ di-fork. | Sangat Tinggi. Proses sepenuhnya terisolasi secara memori. | Rentan Race Condition dan Crash Segmentation Fault (Core Dump) mematikan R host. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mengabaikan Copying pada Operasi Penambahan Kolom Data Frame
*Kesalahan*: Mengira sintaksis `df$baru <- x` tidak memakan memori.
*Dampak*: R menduplikasi seluruh list internal dataframe. Jika dataframe berukuran 2 GB, operasi ini mendadak membutuhkan minimal 4 GB RAM.
*Solusi*: Gunakan `data.table::set()` atau `setDT(df)[, baru := x]`.

#### 10.2. Penggunaan `fork` pada Lingkungan Multi-Threaded Rcpp
*Kesalahan*: Menggabungkan `mclapply()` (forking) dengan library linear algebra seperti OpenBLAS atau `RcppParallel`.
*Dampak*: Deadlock instan pada worker child process, membuat proses pipeline berhenti (*hang*) selamanya tanpa pesan error (*zombie process*).
*Solusi*: Gunakan cluster socket terpisah (`future::plan(multisession)`) atau batasi thread OpenBLAS ke 1 (`RhpcBLASctl::blas_set_num_threads(1)`) sebelum pemanggilan fork.

#### 10.3. Kebocoran Memori pada Sesi R Panjang (Plumber API / Long-running Daemons)
*Kesalahan*: Membiarkan variabel besar tersimpan di Global Environment atau *enclosing environment* fungsi (*lexical closures*).
*Dampak*: GC R tidak akan pernah membersihkan objek yang memiliki referensi aktif di root set, memicu kebocoran memori progresif (*memory leak*).
*Solusi*: Bungkus eksekusi batch di dalam fungsi lokal, gunakan `rm()` diikuti `gc()` secara periodik hanya jika diperlukan, atau manfaatkan `callr::r()` untuk mengeksekusi sub-task dalam proses R terisolasi yang langsung musnah setelah eksekusi selesai.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alokasi Statis Terlebih Dahulu**: Jangan pernah memperbesar ukuran vektor/matriks/list secara inkremental dalam sebuah loop.
- [ ] **Vectorization Over Loops**: Pastikan kalkulasi memanfaatkan operasi SIMD bawaan C-core R ketimbang evaluasi interpreter manual.
- [ ] **Audit Mutasi Memori**: Gunakan `tracemem()` selama fase unit testing untuk memvalidasi bahwa tidak ada duplikasi data yang tidak diinginkan pada dataset besar.
- [ ] **Gunakan Framework ALTREP**: Manfaatkan format penyimpanan modern seperti `parquet` atau `fst` yang mendukung streaming data langsung ke RAM tanpa parsing teks CSV.
- [ ] **Optimasi Ukuran Tipe Data**:
  - Gunakan `integer` (`1L`, 4 byte) alih-alih `numeric` (`1.0`, 8 byte) jika tidak membutuhkan presisi desimal.
  - Hindari representasi kategori dengan tipe `character` berulang; gunakan `factor` untuk mengonversi string ke integer dictionary.
- [ ] **Isolasi Worker Paralel**: Saat mendesain batch worker terdistribusi, pastikan data yang ditransfer via jaringan/socket berukuran minimal. Lakukan reduksi/agregasi data di sisi worker sebelum dikembalikan ke proses induk.
- [ ] **Batas Memori Kontainer**: Konfigurasi parameter lingkungan R `R_MAX_VSIZE` sesuai batas limit memori cgroup Docker untuk mencegah pembunuhan proses tak terduga oleh Linux OOM Killer.

---

### 12. Hands-on Practice: Membangun Modul Native High-Performance

Ikuti langkah-langkah praktikum berikut. Simpan semua file di direktori kerja: `hands-on/m02/`

#### Langkah 1: Persiapan Struktur Direktori
Buka terminal dan buat direktori kerja:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Langkah 2: Menulis Kernel C++ Mutasi In-Place
Buat file bernama `matrix_ops.cpp`:
```cpp
#include <Rcpp.h>
using namespace Rcpp;

// Mengalikan matriks numerik dengan skalar secara in-place tanpa deep-copy
// [[Rcpp::export]]
void scale_matrix_inplace(NumericMatrix mat, double factor) {
    int total_elements = mat.nrow() * mat.ncol();
    
    // Pointer langsung ke memori internal R
    double* ptr = mat.begin();
    
    for (int i = 0; i < total_elements; ++i) {
        ptr[i] *= factor;
    }
}
```

#### Langkah 3: Menulis Script Pengujian & Profiling
Buat file bernama `profile_run.R`:
```r
library(Rcpp)
library(bench)
library(lobstr)

# Kompilasi C++
Rcpp::sourceCpp("matrix_ops.cpp")

# Buat matriks 5000 x 5000 (~190 MB)
cat("Mengalokasikan matriks 5000x5000...\n")
mat_base <- matrix(runif(25e6), nrow = 5000, ncol = 5000)
mat_cpp <- matrix(mat_base, nrow = 5000, ncol = 5000) # Salinan terpisah untuk pengujian

cat("Alamat memori mat_base awal:", lobstr::obj_addr(mat_base), "\n")
cat("Alamat memori mat_cpp awal :", lobstr::obj_addr(mat_cpp), "\n\n")

# Eksekusi Benchmark
cat("Menjalankan perbandingan profiling...\n")
bench_res <- bench::mark(
  Base_R_Scale = {
    # Memicu alokasi matriks baru 190 MB
    mat_base <- mat_base * 2.5
  },
  Cpp_Inplace_Scale = {
    # Mengubah langsung array pointer, alokasi memori = 0 byte
    scale_matrix_inplace(mat_cpp, 2.5)
  },
  iterations = 10,
  check = FALSE
)

print(bench_res[, c("expression", "min", "median", "mem_alloc", "n_gc")])

cat("\nAlamat memori mat_base akhir:", lobstr::obj_addr(mat_base), " (Berubah!)\n")
cat("Alamat memori mat_cpp akhir :", lobstr::obj_addr(mat_cpp), " (Tetap konsisten!)\n")
```

#### Langkah 4: Eksekusi dan Verifikasi
Jalankan script via terminal:
```bash
Rscript profile_run.R
```
Amati kolom `mem_alloc` dan `n_gc` pada output terminal. Pendekatan Base R akan mencatat alokasi ratusan megabyte dan memicu Garbage Collection, sementara `Cpp_Inplace_Scale` mencatat alokasi 0 byte dan 0 siklus GC.

---

### 13. Exercise

#### Level 1 (Easy): Eliminasi Bottleneck Append Vektor
Diberikan fungsi berikut yang berjalan sangat lambat:
```r
generate_primes_naive <- function(n) {
  primes <- c()
  for (i in 2:n) {
    is_prime <- TRUE
    if (i > 2) {
      for (j in 2:floor(sqrt(i))) {
        if (i %% j == 0) { is_prime <- FALSE; break }
      }
    }
    if (is_prime) primes <- c(primes, i)
  }
  primes
}
```
*Tugas*: Refactor fungsi tersebut menggunakan teknik *static pre-allocation* atau algoritma *Sieve of Eratosthenes* tervektorisasi. Ukur penurunan alokasi memori (`mem_alloc`) dan peningkatan latensi menggunakan paket `bench`.

#### Level 2 (Medium): Transformasi Pipeline Data Table By-Reference
Diberikan script manipulasi data frame 5 juta baris:
```r
set.seed(123)
n <- 5e6
df <- data.frame(
  id = 1:n,
  kategori = sample(letters[1:5], n, replace = TRUE),
  nilai = rnorm(n)
)

# Pipeline Tidak Efisien:
df$nilai_normalisasi <- (df$nilai - mean(df$nilai)) / sd(df$nilai)
df$status <- ifelse(df$nilai_normalisasi > 0, "High", "Low")
df <- df[df$status == "High", ]
```
*Tugas*: Konversi seluruh alur kerja di atas menjadi 100% *in-place modification* menggunakan paket `data.table`. Buktikan melalui `lobstr::obj_addr()` bahwa tidak ada duplikasi data frame yang terjadi selama kalkulasi kolom berlangsung.

#### Level 3 (Hard): Hybrid Streaming Matrix Normalizer (Rcpp + OpenMP)
*Tugas*: Buat sebuah fungsi Rcpp `normalize_matrix_parallel(NumericMatrix mat)` yang menormalisasi matriks numerik masif (skala 10.000 x 10.000) menggunakan teknik Min-Max Scaling per baris secara paralel menggunakan thread pool OpenMP (`#pragma omp parallel for`).
*Batasan*:
1. Matriks asli harus dimodifikasi secara in-place (*zero-allocation*).
2. Fungsi tidak boleh menghasilkan race condition saat mencari nilai minimum dan maksimum per baris.
3. Bandingkan performanya terhadap eksekusi serial R native `t(apply(mat, 1, function(x) ...))`.

---

### 14. Challenge: Real-Time Network Packet Inspection Engine

Rancang dan bangun arsitektur pemrosesan aliran paket data jaringan (*high-throughput streaming buffer*) dengan skenario berikut:
- **Kondisi Data**: Data aliran paket masuk via soket biner terkompresi dengan kecepatan 100.000 frame per detik. Setiap paket memiliki panjang variabel antara 64 hingga 1500 byte.
- **Batasan Sistem**: 
  - Host server hanya memiliki alokasi memori maksimal 2 GB RAM (dibatasi Docker `cgroups`).
  - Total latency inspeksi tidak boleh melebihi 50 milidetik per jendela batch (1 detik data window = 100.000 baris).
  - Sistem harus mendeteksi pola serangan DDoS (*SYN flood pattern*) secara real-time.

*Persyaratan Solusi*:
1. Rancang arsitektur buffer sirkular (*ring buffer*) menggunakan C++ via `Rcpp` untuk menghindari GC thrashing.
2. Terapkan pemrosesan paralel asinkron antara *Reader Process* (penerima soket biner) dan *Analytic Engine Worker* (kalkulasi entropi IP sumber).
3. Buat skema *backpressure* otomatis: apa yang dilakukan sistem saat laju paket melampaui kapasitas komputasi worker tanpa memicu OOM Crash.
4. Buat dokumen arsitektur komprehensif, diagram aliran paket memori, dan implementasi prototipe yang dapat diverifikasi performanya menggunakan simulator generator paket.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa modifikasi elemen tunggal pada vektor R panjang dapat memicu deep copy di memori?**
   - A. Karena R selalu mengeksekusi kode di stack memory.
   - B. Karena objek tersebut memiliki nilai `REFCNT > 1` (dibagikan oleh lebih dari satu referensi simbol).
   - C. Karena C-level SEXP tidak mendukung tipe data array dinamis.
   - D. Karena Garbage Collector secara otomatis mengunci buffer heap.
   *Jawaban: B*

2. **Apa peran utama dari arsitektur ALTREP pada R 3.5+?**
   - A. Mengganti kompiler GCC dengan Clang.
   - B. Mengizinkan vektor diwakili secara abstrak di memori tanpa harus mengalokasikan array penuh di awal.
   - C. Mengalihkan alokasi memori R langsung ke GPU.
   - D. Menghapus ketergantungan pada struktur `SEXPREC`.
   *Jawaban: B*

3. **Perintah dasar R mana yang digunakan secara native untuk melacak perubahan alamat memori akibat Copy-on-Modify?**
   - A. `debug()`
   - B. `traceback()`
   - C. `tracemem()`
   - D. `lobstr::ref()`
   *Jawaban: C*

4. **Berapa banyak generasi yang dikelola oleh sistem Generational Garbage Collector pada R?**
   - A. 2 Generasi (Young dan Old).
   - B. 3 Generasi (Gen 0, Gen 1, Gen 2).
   - C. 4 Generasi (Eden, Survivor 1, Survivor 2, Tenured).
   - D. R tidak menggunakan generational GC melainkan reference counting murni.
   *Jawaban: B*

5. **Apa efek negatif dari memicu fungsi `gc()` secara manual di dalam perulangan loop data processing?**
   - A. Menyebabkan memori heap bocor seketika.
   - B. Memicu segmentasi fault pada pointer C++.
   - C. Menurunkan latensi komputasi secara ekstrem karena memaksakan *full stop-the-world scan* pada seluruh generasi memori.
   - D. Menghapus objek global yang sedang aktif.
   *Jawaban: C*

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Ketika mengeksekusi `data.table::set(DT, i, j, value)`, apa yang terjadi di level memori internal R?**
   - A. Seluruh objek `DT` disalin ke buffer virtual baru.
   - B. SEXP dari kolom `j` dimodifikasi secara langsung (*in-place pointer mutation*) tanpa menduplikasi objek tabel induk.
   - C. Kolom `j` dikonversi sementara menjadi tipe string.
   - D. Terjadi serialisasi tabel ke disk secara berkala.
   *Jawaban: B*

7. **Mengapa profiling menggunakan `profvis` menunjukkan adanya waktu komputasi yang tinggi pada label `<GC>`?**
   - A. R sedang menunggu koneksi database eksternal.
   - B. Loop kode Anda mengalokasikan terlalu banyak objek sementara berumur pendek, memicu pembersihan Gen 0 secara repetitif.
   - C. Sistem operasi sedang melakukan swapping disk akibat kekurangan CPU cache.
   - D. Compiler Rcpp lupa menyertakan flag `-O3`.
   *Jawaban: B*

8. **Apa bahaya fatal menggunakan strategi paralel `fork` (misal: `parallel::mclapply`) pada lingkungan yang menggunakan multi-threaded linear algebra (seperti OpenBLAS) atau RStudio?**
   - A. Memori RAM langsung terhapus bersih.
   - B. Potensi terjadinya *thread deadlock* di tingkat OS kernel yang menyebabkan sesi R hang total.
   - C. Skrip otomatis terkonversi menjadi single-thread secara diam-diam.
   - D. Ukuran data frame membengkak 100 kali lipat.
   *Jawaban: B*

9. **Jika sebuah objek R dioper ke fungsi C++ melalui `Rcpp::NumericVector x`, bagaimana mekanisme transmisi datanya secara default?**
   - A. Seluruh array disalin elemen demi elemen ke dalam memory stack C++.
   - B. Pointer internal objek SEXP dioper langsung (*pass-by-reference wrapper*), tanpa alokasi deep-copy awal.
   - C. Objek dikonversi menjadi format JSON sebelum diparsing oleh C++.
   - D. Dibuat shared memory file temporer di direktori `/tmp`.
   *Jawaban: B*

10. **Manakah dari format penyimpanan berikut yang secara native memanfaatkan zero-copy read via IPC/mmap pada ekosistem R modern?**
    - A. CSV via `read.csv`.
    - B. Standar RDS via `saveRDS`/`readRDS`.
    - C. Apache Arrow Feather / IPC format via paket `arrow`.
    - D. Kompresi GZIP tarball.
    *Jawaban: C*

#### Bagian 3: Production Scenario (3 Kasus Komprehensif)

11. **Skenario 1 (Kasus API Container Memory Bloat)**:
    *Kasus*: Anda memelihara layanan Microservice Plumber API yang memproses scoring model machine learning. Setelah berjalan selama 48 jam dan melayani 200.000 request, konsumsi memori kontainer naik secara konstan dari 300 MB ke 3.8 GB (membentur batas cgroups dan akhirnya di-kill oleh sistem). Profiling menunjukkan tidak ada objek baru di Global Environment.
    *Pertanyaan*: Apa penyebab struktural paling mungkin dari fenomena ini, dan bagaimana arsitektur solusinya?
    *Solusi Analisis*:
    - Penyebab: Kemungkinan besar terjadi retensi memori di dalam *lexical closure* fungsi scoring model, atau fragmentasi alokasi pada level *glibc/malloc* Linux yang tidak mengembalikan memori yang telah dilepaskan oleh GC R kembali ke OS kernel. Penyebab lain adalah *caching* internal environment pada model object (misal: formula model R sering mengikat seluruh environment tempat ia diciptakan, termasuk dataframe latihan).
    - Solusi: 
      1. Stripping model environment: bersihkan atribut formula model dari parent environment-nya (`model$terms <- NULL`, hapus `attr(model, ".Environment")`).
      2. Terapkan worker-recycle architecture: jalankan proses scoring di dalam proses isolasi jangka pendek menggunakan `callr::r()` atau restart worker Plumber secara periodik setelah mencapai ambang batas transaksi tertentu (misal: setiap 10.000 request).
      3. Atur allocator environment variable Linux: `MALLOC_ARENA_MAX=2` untuk meredam fragmentasi virtual heap.

12. **Skenario 2 (Kasus Cluster Communication Bottleneck)**:
    *Kasus*: Sebuah job parallel analytics memproses matriks 8 GB lintas 16 node worker menggunakan `parallel::parLapply(cl, chunks, fun)`. Alih-alih mendapatkan peningkatan kecepatan 16x, pemrosesan justru berjalan 2x lebih lambat dibandingkan eksekusi serial pada satu mesin tunggal. CPU utilization worker terpantau rata-rata di bawah 15%.
    *Pertanyaan*: Jelaskan anomali bottleneck arsitektur ini dan berikan rekayasa perbaikannya.
    *Solusi Analisis*:
    - Penyebab: Masalah utama terletak pada *serialization overhead* dan *I/O Socket Saturation*. Membagi dan mentransmisikan data mentah 8 GB melalui socket loopback TCP/IP lokal ke 16 worker terpisah membutuhkan proses serialisasi (`serialize()`), pengiriman via network stack, dan deserialisasi (`unserialize()`) di setiap worker. Waktu I/O transmisi memori jauh melampaui waktu komputasi data itu sendiri (*communication-to-computation ratio* sangat buruk).
    - Solusi:
      1. Ubah arsitektur pengiriman data: alih-alih mengirim partisi data mentah via socket R, simpan dataset pada *shared memory file* (`/dev/shm`) atau format memory-mapped Parquet/Arrow.
      2. Berikan hanya indeks/pointer offset baris ke masing-masing worker (`parLapply(cl, 1:16, worker_by_index)`). Tiap worker membaca data secara langsung dari media memory-mapped secara zero-copy.
      3. Kurangi jumlah worker jika overhead context switching lebih tinggi dari kalkulasi.

13. **Skenario 3 (Kasus Mutasi Data Frame Multi-Thread Crash)**:
    *Kasus*: Seorang data engineer menulis algoritma mutasi paralel internal C++ menggunakan OpenMP pada pointer array dataframe R (`SEXPREC*`). Saat dijalankan pada unit testing lokal skala kecil kode berjalan lancar, namun ketika dipindahkan ke production server dengan throughput 64 thread, sistem mengalami *Immediate Core Dump* (Segmentation Fault) secara intermiten.
    *Pertanyaan*: Mengapa manipulasi langsung pointer memori internal R tidak aman di lingkungan multi-threaded C++, dan bagaimana pola arsitektur proteksi yang benar?
    *Solusi Analisis*:
    - Penyebab: R adalah sistem berbasis *single-threaded runtime*. R API, alokasi heap via `R_alloc`/`allocVector`, dan Garbage Collector R **tidak thread-safe**. Jika thread OpenMP mencoba mengakses, mengubah ukuran, atau mengalokasikan memori SEXP R saat thread R utama memicu siklus Garbage Collection, GC akan membaca state pointer yang korup, menyebabkan pointer melompat ke invalid memory address (*Segmentation Fault*).
    - Solusi:
      1. Isolasi Memori: Alokasikan memori native standar C++ (seperti `std::vector<double>`) di luar memori R, salin pointer mentah ke context C++ murni sebelum memanggil `#pragma omp parallel`.
      2. Jalankan komputasi OpenMP hanya pada buffer native C++ tersebut tanpa menyentuh R API sama sekali di dalam region thread paralel.
      3. Setelah komputasi paralel selesai dan seluruh thread bergabung kembali (*joined* ke thread master), salin hasilnya kembali ke buffer memori R, atau bungkus pointer C++ tersebut sebagai objek eksternal (`Rcpp::XPtr`).

---

### 16. Summary

1. **Struktur Dasar SEXP**: Segala hal di R adalah pointer C-level SEXP. Memahami representasi internal ini adalah kunci dalam mendiagnosis masalah performa ekstrem.
2. **Karakteristik Copy-on-Modify**: R membatasi salinan buffer memori hanya jika sebuah objek memiliki multi-referensi (`REFCNT > 1`). Mengembangkan kode enterprise menuntut eliminasi duplikasi memori implisit melalui modifikasi *by-reference* (`data.table`) atau alokasi *in-place* C++.
3. **Penyebab Latensi Garbage Collector**: Siklus GC yang tinggi merupakan indikator langsung dari alokasi objek dinamis berskala masif dalam iterasi loop. Pre-alokasi statis dan pemanfaatan vektorisasi SIMD secara drastis menekan interupsi GC (*Stop-the-World pause*).
4. **Peran Modern ALTREP**: ALTREP mengubah batas memori R dengan memvalidasi struktur data virtual dan integrasi I/O berbasis *memory mapping* (Apache Arrow), memungkinkan analisis data yang ukurannya melampaui kapasitas RAM fisik tanpa *memory pressure*.
5. **Akselerasi Hybrid Native**: Menggabungkan ekosistem analitik R dengan efisiensi memori native via `Rcpp` atau `cpp11` adalah standar industri untuk memotong latensi CPU-bound, dengan catatan mutasi komputasi multi-threaded harus terisolasi dari siklus hidup GC single-threaded bawaan R.