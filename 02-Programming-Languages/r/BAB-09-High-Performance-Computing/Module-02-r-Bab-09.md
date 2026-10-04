# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (High-Performance Computing di R)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Runtime R & Memory Footprint:** Memahami representasi internal objek R (`SEXP`), mekanisme *Reference Counting* (`NAMED`/`REFCNT`), dan *Copy-on-Modify* untuk meminimalkan alokasi memori redundan.
2. **Mengimplementasikan Zero-Copy & Native Acceleration:** Menulis ekstensi C++ performa tinggi menggunakan `Rcpp` dan `OpenMP` yang berinteraksi langsung dengan struktur data native R tanpa biaya *copy overhead*.
3. **Mendesain Arsitektur Paralel Terdistribusi (Scale-Out):** Mengorkestrasi beban kerja komputasi skala enterprise melintasi multi-node cluster menggunakan protokol `future`, `callr`, dan cluster scheduler (seperti Slurm/Kubernetes).
4. **Mengelola Komputasi Out-of-Core:** Memproses dataset berukuran multi-gigabyte/terabyte yang melebihi kapasitas RAM melalui *Memory-Mapped Files* (`bigstatsr`, `arrow`) dan arsitektur *Shared Memory* POSIX.
5. **Menghilangkan Bottleneck & Concurrency Hazards:** Mengidentifikasi dan memitigasi *deadlock* multithreading (misal: konflik OpenBLAS dengan POSIX fork), *serialization overhead*, dan *cache thrashing*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
* **Core R Fundamentals:** Penggunaan R tingkat lanjut (vektorisasi, functional programming via `lapply`/`purrr`, manipulasi environments).
* **Sistem Operasi & Arsitektur Komputer:** Pemahaman mendalam tentang *Virtual Memory*, *POSIX threads* (`pthreads`), *Process Forking* (`fork()`), CPU Caches (L1/L2/L3), dan *NUMA architecture*.
* **C++ Basics (C++11/C++14/C++17):** Pengetahuan tentang pointers, references, STL containers, dan template dasar.
* **Perkakas Profiling:** Pengalaman dasar menggunakan `profvis`, GNU `gdb`, atau Linux `perf`.

---

## 3. Concept & Internal Architecture

### 3.1 Struktur Data Internal R (`SEXP`) dan Memory Subsystem
Dalam interpreter R standar (GNU R), setiap objek didefinisikan sebagai pointer menuju struktur `SEXPREC` (S-Expression Record), disingkat `SEXP`. 

```c
// Representasi konseptual GNU R SEXPREC di C internal
typedef struct SEXPREC {
    SEXPREC_HEADER header;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;
        struct envsxp_struct envsxp;
        struct closxp_struct closxp;
        struct promsxp_struct promsxp;
        struct vecsxp_struct vecsxp; // Digunakan oleh vektor numerik/karakter
    } u;
} SEXPREC, *SEXP;
```

Struktur `SEXPREC_HEADER` menyimpan informasi vital:
* **`type` (SEXPTYPE):** Menentukan tipe data primitif (`INTSXP`, `REALSXP`, `STRSXP`, `VECSXP` untuk list, dll.).
* **`mark`:** Bit penanda untuk Garbage Collector (GC) berbasis *generational mark-and-sweep*.
* **`refcnt`:** Sejak R 3.1.0, R beralih dari mekanisme primitif `NAMED` ke tracking referensi komprehensif. Jika `REFCNT > 1`, modifikasi apa pun terhadap objek akan memicu duplikasi memori penuh (*deep copy*) melalui semantik *Copy-on-Modify* (CoM).

### 3.2 Thread Safety dan R Single-Threaded Evaluation Loop
R engine didesain sebagai sistem *single-threaded*. Interpreter mengeksekusi *Read-Eval-Print Loop* (REPL) di dalam thread utama (*main thread*). Global state R (termasuk symbol table, call stack, dan GC state) **tidak thread-safe**.

```
+-------------------------------------------------------------+
| R Main Thread (Single-Threaded Execution Environment)       |
|                                                             |
|  +-------------+    +-------------+    +-----------------+  |
|  | Call Stack  | -> | Symbol Table| -> | Memory Allocator|  |
|  +-------------+    +-------------+    +--------+--------+  |
|                                                 |           |
+-------------------------------------------------|-----------+
                                                  v
                                     +------------------------+
                                     | Garbage Collector (GC) |
                                     | Generational Tracing   |
                                     +------------------------+
```

Konsekuensi arsitektur:
1. Anda tidak dapat mengeksekusi interpreter R secara konkuren di dalam thread POSIX yang berbeda pada satu proses memori yang sama tanpa memicu *segmentation fault*.
2. Paralelisasi intra-node murni R harus menggunakan:
   * **Multi-processing (Shared-nothing / Forking):** Memanfaatkan syscall `fork()` (Linux/macOS) dengan *Copy-on-Write* (CoW), atau
   * **Multi-processing (Socket-based IPC):** Membuat instance R baru yang berkomunikasi via TCP/IP sockets (`PSOCK`).
   * **Native Shared-Memory Threading:** Mengalihkan loop komputasi berat ke C++ via `Rcpp` menggunakan thread pool native (`OpenMP`, `std::thread`, Intel TBB) yang hanya mengakses array C primitif tanpa menyentuh *R API* atau *R Memory Allocator*.

### 3.3 Zero-Copy Semantics via `Rcpp`
Ketika data dilewatkan dari R ke C++ melalui library `Rcpp`:
* Instansiasi `Rcpp::NumericVector x(s_exp_ptr)` **tidak** menyalin array data. Konstruktor ini bertindak sebagai *proxy object* tipis yang membungkus pointer data primitif C (`double*`) di dalam heap R.
* Akses data melalui pointer langsung (`REAL(s_exp_ptr)` atau `x.begin()`) memberikan throughput bandwidth memori maksimal sekelas instruksi assembly native.
* Modifikasi data *in-place* dimungkinkan jika objek tidak diproteksi oleh referensi lain, menghindari lonjakan footprint RAM.

### 3.4 Out-of-Core Processing via POSIX Shared Memory & `mmap`
Untuk data berskala Terabyte, RAM konvensional akan mengalami *Out-Of-Memory* (OOM). Mekanisme *memory-mapped files* (`mmap`) memetakan berkas pada disk langsung ke dalam ruang alamat virtual proses (*virtual address space*). 

Sistem operasi mengelola *page caching* secara otomatis:
* Data dibaca dari disk ke RAM secara *lazy* (saat diakses via *page fault*).
* Modifikasi ditulis kembali ke persistent storage secara asinkron via *dirty pages*.
* Beberapa proses worker independen dapat membaca buffer memori fisik yang persis sama tanpa duplikasi overhead.

---

## 4. Why & What

| Dimensi | Native R Loop | Parallel Sockets (`parallel::makeCluster`) | Forking (`mclapply`) | Rcpp + OpenMP | Out-of-Core (`bigstatsr` / `arrow`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Single-threaded | Multi-process (Isolated) | Multi-process (CoW) | Multithreaded (Shared RAM) | Asynchronous Streaming / Disk Mapped |
| **Overhead Komunikasi** | 0 ms | Sangat Tinggi (TCP Serialization) | Rendah (Hanya setup proses) | 0 ms (Shared Pointers) | I/O Bound (Disk throughput) |
| **Konsumsi Memori** | $1\times$ | $N \times \text{Ukuran Data}$ | $1\times \text{ hingga } N\times$ (Jika CoW pecah) | $1\times$ (Zero-Copy) | Sangat Rendah (Sub-RAM Footprint) |
| **Platform Compatibility**| Cross-Platform | Cross-Platform | POSIX Only (Linux/macOS) | Cross-Platform | Cross-Platform |
| **Safety / Stability** | Stabil | Sangat Tinggi (Isolasi memori) | Rawan Deadlock jika ada OpenBLAS | Harus thread-safe murni | Sangat Tinggi |

### Mengapa Perlu Arsitektur HPC Hybrid di R?
Komputasi enterprise sering menghadapi tantangan *embarrassingly parallel* berskala masif (seperti simulasi risiko keuangan, genomika, atau tuning hyperparameter) yang dibatasi oleh:
1. Biaya serialisasi R (`serialize()`) yang membengkak saat mentransfer objek data besar antar worker.
2. Interupsi berkala Garbage Collector R yang memblokir instruksi CPU saat volume objek di memory heap mencapai jutaan node.

Solusi arsitektur modern adalah memisahkan lapisan: **R sebagai State Coordinator & Orchestrator**, dan **C++ / POSIX Memory-Mapped I/O sebagai Execution Engine**.

---

## 5. How (Workflow Detail)

Arsitektur HPC end-to-end pada runtime R dirancang mengikuti alur kerja berikut:

```
[ Dataset Skala Besar (Disk: Parquet / Flat Binary) ]
                          |
                          v
         [ Layer 1: Memory-Mapping Engine ]
             - POSIX mmap() via bigstatsr / Arrow
             - Alamat virtual dialokasikan tanpa baca penuh
                          |
                          +-----------------------------------+
                          |                                   |
                          v                                   v
             [ Layer 2A: Intra-Node Parallel ]   [ Layer 2B: Inter-Node Cluster ]
             - Rcpp + OpenMP threads             - future.batchtools / Slurm
             - Zero-Copy read array pointer      - Partisi indeks didistribusikan
             - SIMD Vectorization                - Task chunking non-data transfer
                          |                                   |
                          +-----------------+-----------------+
                                            |
                                            v
                         [ Layer 3: Lock-Free Aggregation ]
                             - Reduksi numerik in-place
                             - Atomic operations
                                            |
                                            v
                             [ Hasil Akhir: Objek R Standar ]
```

### Prosedur Implementasi Eksekusi HPC:
1. **Inisialisasi Shared Storage / Mapped Object:** Jangan memuat data ke memori R menggunakan `read.csv` atau `readRDS`. Buat berkas biner memory-backed menggunakan format `bigstatsr::FBM` (*Filebacked Big Matrix*) atau Apache Arrow IPC buffer.
2. **Dekompilasi Kernel Komputasi ke C++:** Identifikasi *hotspot* algoritma (loop terdalam) dan konversi ke dalam bentuk C++ yang mematuhi batasan *thread safety* (tidak ada pemanggilan fungsi R runtime dari dalam thread anak).
3. **Konfigurasi Scheduler Worker:** Buat abstraksi worker melalui library `future`. Gunakan topology *multicore* pada satu mesin atau cluster sockets/Slurm pada cluster terdistribusi.
4. **Distribusi Indeks (Bukan Data):** Worker hanya menerima rentang indeks data (misal: row `10,000` s.d `50,000`), bukan salinan data aktual. Worker membuka descriptor memory-map yang sudah ada untuk membaca slice data.
5. **Eksekusi dan Reduksi Hasil:** Reduksi matriks/vektor dilakukan secara asinkron, mengembalikan struktur data minimal ke sesi R master.

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Manufaktur
* **Single-threaded R:** Satu pekerja manual mengambil satu persatu material dari gudang, mengolahnya di meja kerja kecil, lalu mengembalikannya ke gudang. Meja kerja sering penuh sampah (*Garbage Collection*), memaksa pekerja berhenti total untuk menyapu.
* **PSOCK Parallelism:** Membangun 16 gedung pabrik baru yang identik. Setiap kali ada pekerjaan, seluruh isi gudang difotokopi dan dikirim via kurir pos (TCP/IP Serialization) ke masing-masing gedung. Sangat boros kertas dan waktu pengiriman.
* **Shared Memory + Rcpp/OpenMP (Arsitektur HPC):** Gudang utama menggunakan rak geser berkecepatan tinggi (*Memory Mapping*). Enam belas lengan robot industri (*OpenMP native threads*) bekerja bersamaan di satu ruangan besar, langsung merakit komponen di atas sabuk konveyor bersama tanpa proses fotokopi atau jeda kurir.

### Topologi Arsitektur Memori: Native Sockets vs Shared Memory Architecture

```
MODEL TRADISIONAL (PSOCK CLUSTER - DUPLIKASI PENUH):
+---------------------------------------------------------------------------------+
| RAM MESIN                                                                       |
|                                                                                 |
|  +--------------------+   TCP Serialization    +--------------------+           |
|  | Master R Process   | =====================> | Worker 1 Process   | (PID 1002)|
|  | Data: 10GB [SEXP]  |   (Latency Tinggi,     | Data: 10GB [SEXP]  |           |
|  +--------------------+    CPU 100% Saturation)+--------------------+           |
|            |                                                                    |
|            |              TCP Serialization    +--------------------+           |
|            +=================================> | Worker 2 Process   | (PID 1003)|
|                                                | Data: 10GB [SEXP]  |           |
|                                                +--------------------+           |
| TOTAL RAM TERPAKAI: 30 GB (Rawan Terjadi Out-Of-Memory)                         |
+---------------------------------------------------------------------------------+

MODEL ENTERPRISE HIGH-PERFORMANCE (SHARED MEMORY + ZERO-COPY KERNEL):
+---------------------------------------------------------------------------------+
| RAM MESIN / VIRTUAL MEMORY SPACE                                                |
|                                                                                 |
|  +---------------------------------------------------------------------------+  |
|  | Memory-Mapped Storage / POSIX Shared Heap (FBM / Arrow IPC)               |  |
|  | Binary Array Block [100 GB File on Disk/NVMe -> Mapped to Virtual Memory]  |  |
|  +---------------------------------------------------------------------------+  |
|           ^                         ^                         ^                 |
|           | (Pointer Dereference)   | (Pointer Dereference)   |                 |
|           | (Zero-Copy Read)        | (Zero-Copy Read)        |                 |
|  +--------------------+    +--------------------+    +--------------------+     |
|  | R Master Orchestr. |    | R Worker 1         |    | R Worker 2         |     |
|  | PID 2001           |    | PID 2002           |    | PID 2003           |     |
|  | Pointer Ref Only   |    | Pointer Ref Only   |    | Pointer Ref Only   |     |
|  +--------------------+    +--------------------+    +--------------------+     |
|           |                         |                         |                 |
|           v                         v                         v                 |
|   [ OpenMP Threads ]        [ OpenMP Threads ]        [ OpenMP Threads ]        |
|   Core 0-3 Execution        Core 4-7 Execution        Core 8-11 Execution       |
|                                                                                 |
| TOTAL RAM EFEKTIF DIGUNAKAN: Ukuran Buffer Nyata Sesuai Cache Kernel OS         |
+---------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Parallel In-Place Matrix Row-Sum via Rcpp & OpenMP
Kode berikut menunjukkan integrasi C++ native di R yang menggunakan komputasi multithreaded murni tanpa membuat salinan data memori R.

Simpan file ini dengan nama `parallel_ops.cpp`:

```cpp
#include <Rcpp.h>
#include <omp.h>

// [[Rcpp::plugins(openmp)]]

//' @title Hitung Row Sum Paralel Menggunakan OpenMP
//' @param X SEXP Matrix Numerik
//' @param num_threads Jumlah thread CPU yang dialokasikan
//' @return NumericVector hasil reduksi
// [[Rcpp::export]]
Rcpp::NumericVector parallel_row_sums(const Rcpp::NumericMatrix& X, int num_threads = 4) {
    int nrow = X.nrow();
    int ncol = X.ncol();
    
    // Alokasi hasil (hanya satu alokasi vektor output di R memory heap)
    Rcpp::NumericVector out(nrow);
    
    // Ambil direct pointer ke memory buffer R
    const double* p_X = X.begin();
    double* p_out = out.begin();
    
    // Konfigurasi OpenMP
    omp_set_num_threads(num_threads);
    
    // Eksekusi paralel tingkat C++ level tanpa interupsi R Interpreter
    #pragma omp parallel for schedule(static) shared(p_X, p_out, nrow, ncol)
    for (int i = 0; i < nrow; ++i) {
        double sum = 0.0;
        for (int j = 0; j < ncol; ++j) {
            // Memory layout matriks R adalah Column-Major Order (Fortran-style): index = i + j * nrow
            sum += p_X[i + j * nrow];
        }
        p_out[i] = sum;
    }
    
    return out;
}
```

Script eksekusi dan verifikasi di R:

```r
library(Rcpp)

# Kompilasi native code di runtime
sourceCpp("parallel_ops.cpp")

# Buat dataset uji
set.seed(42)
n_rows <- 5000000
n_cols <- 10
mat <- matrix(rnorm(n_rows * n_cols), nrow = n_rows, ncol = n_cols)

# Benchmark verifikasi kebenaran
res_cpp <- parallel_row_sums(mat, num_threads = 4)
res_base <- rowSums(mat)

# Verifikasi numerik
stopifnot(all.equal(res_cpp, res_base))
cat("Verifikasi Sukses: Output C++/OpenMP identik dengan base::rowSums\n")
```

---

### 7.2 Practical Example: Enterprise High-Throughput Monte Carlo Simulation via Out-of-Core FBM & Asynchronous Workers

Kasus implementasi simulasi opsi finansial Monte Carlo berskala 50.000.000 iterasi. Jika seluruh matriks path simulasi disimpan dalam memori biasa, kebutuhan memori mencapai lebih dari 40 GB. Kita menggunakan `bigstatsr` (*Filebacked Big Matrix*) untuk mendistribusikan penulisan hasil simulasi secara asinkron langsung ke disk.

```r
suppressPackageStartupMessages({
  library(bigstatsr)
  library(future)
  library(future.apply)
})

# 1. Konfigurasi Environment & Cluster
plan(multisession, workers = 4)
total_simulations <- 50000000 # 50 Juta Lintasan
time_steps <- 10              # 10 Interval Waktu
chunk_size <- 5000000         # Partisi 5 Juta per batch

cat("Mengalokasikan Filebacked Big Matrix pada filesystem...\n")
# Buat Filebacked Matrix (out-of-core backing store)
backing_file <- tempfile(fileext = ".bk")
fbm_results <- FBM(
  nrow = total_simulations,
  ncol = time_steps,
  type = "double",
  backingfile = sub_ext(backing_file, "")
)

# Catat pointer deskriptor FBM (bukan salinan data)
fbm_desc <- describe(fbm_results)

# 2. Definisikan Fungsi Monte Carlo Geometric Brownian Motion (GBM) di Worker
monte_carlo_worker <- function(desc, row_indices, S0 = 100, mu = 0.05, sigma = 0.2, T = 1.0, steps = 10) {
  # Pasang kembali shared pointer ke FBM lokal proses ini
  x_fbm <- big_attach(desc)
  
  n_sims <- length(row_indices)
  dt <- T / steps
  drift <- (mu - 0.5 * sigma^2) * dt
  vol <- sigma * sqrt(dt)
  
  # Alokasi buffer kalkulasi lokal per-worker
  local_paths <- matrix(0.0, nrow = n_sims, ncol = steps)
  
  # Simulasi vectorized per worker
  current_prices <- rep(S0, n_sims)
  for (t in seq_len(steps)) {
    z <- rnorm(n_sims)
    current_prices <- current_prices * exp(drift + vol * z)
    local_paths[, t] <- current_prices
  }
  
  # Tulis langsung ke backing-disk memory space secara independen
  x_fbm[row_indices, ] <- local_paths
  
  return(length(row_indices))
}

# 3. Eksekusi Paralel Chunked Index
cat("Memulai eksekusi paralel terdistribusi...\n")
chunks <- split(seq_len(total_simulations), ceiling(seq_len(total_simulations) / chunk_size))

t_start <- Sys.time()
simulated_counts <- future_lapply(chunks, function(idx_batch) {
  monte_carlo_worker(
    desc = fbm_desc, 
    row_indices = idx_batch,
    S0 = 100, mu = 0.05, sigma = 0.2, T = 1.0, steps = time_steps
  )
}, future.seed = TRUE)

t_end <- Sys.time()

cat(sprintf("Selesai memproses %s simulasi dalam %s detik.\n", 
            format(sum(unlist(simulated_counts)), big.mark = ","),
            round(difftime(t_end, t_start, units = "secs"), 2)))

# 4. Validasi Hasil Menggunakan Out-Of-Core Summary (Tanpa Menarik Semua ke RAM)
mean_terminal_price <- big_apply(fbm_results, a.FUN = function(X, ind) {
  mean(X[ind, time_steps])
}, a.combine = "c", ind = seq_len(total_simulations))

cat(sprintf("Rata-rata harga akhir instrumen: %.4f (Expected ~ %.4f)\n", 
            mean(mean_terminal_price), 100 * exp(0.05 * 1.0)))

# Bersihkan resources backing store
plan(sequential)
unlink(paste0(sub_ext(backing_file, ""), c(".bk", ".rds")))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Financial High-Frequency Risk Engine
* **Profil Klien:** Tier-1 Investment Bank.
* **Problem Statement:** Sistem regulasi Basel III/FRTB mewajibkan kalkulasi Value at Risk (VaR) dan Expected Shortfall (ES) dari portofolio derivatif 25.000 instrumen di bawah 10.000 skenario shock pasar (*historical stress test*). Eksekusi di sistem R vanilla menggunakan `parLapply` memakan waktu **4,5 jam** dan kerap mengalami kegagalan *Node Eviction* (OOM Killer) di Kubernetes pod cluster saat proses transfer matriks korelasi 25.000 $\times$ 25.000.
* **Target SLA:** Pipeline agregasi risiko harus selesai dalam waktu kurang dari **15 menit** sebelum jam pembukaan bursa (Cut-off jam 06:00 AM).

### Analisis Akar Masalah (Root Causes):
1. **TCP Serialization Bottleneck:** Mengirim matriks skenario dan portofolio ke 64 node pods memakan bandwidth jaringan lokal hingga 10 Gbps jenuh selama 40 menit hanya untuk serialisasi `serialize()`.
2. **Copy-on-Write Broken:** Forking engine (`mclapply`) menduplikasi memori secara masif saat fungsi interpolasi kubik C++ native memicu modifikasi alamat memori sementara di pointer internal R.
3. **Garbage Collection Throttling:** Setiap worker mengalokasikan jutaan objek vektor numerik kecil sementara, menyebabkan proses berhenti (*stop-the-world GC pause*) hingga 35% total runtime.

### Solusi Arsitektur HPC Terdistribusi:
1. **Penyimpanan Matriks Berbasis Apache Arrow Plasma / IPC Shared Memory:** Seluruh matriks shock pasar disimpan dalam format read-only shared memory partition. Semua pods me-mount volume SSD NVMe paralel via format zero-copy memory map.
2. **Kompilasi Core Pricing Engine dengan Rcpp + OpenMP:** Menggantikan logic interpolasi R dengan custom kernel C++ yang mematuhi pointer-alignment AVX-512.
3. **Topologi Orchestration Berbasis `future.batchtools` Terintegrasi ke Slurm:** Menghapus komunikasi socket inter-worker. R master hanya mem-publish job array ID ke Slurm scheduler. Setiap Slurm node mengambil partition index, menulis kalkulasi intermediate ke file FBM lokal, dan melakukan reduksi bertingkat (*tree reduction*).

```
[ Financial Market Data (10,000 Shocks x 25,000 Instruments) ]
                              |
                              v
        +-----------------------------------------------+
        | Shared POSIX NVMe Volume (Arrow Memory Map)   |
        +-----------------------------------------------+
                  /               |               \
                 v                v                v
        [ Slurm Node 01 ]  [ Slurm Node 02 ]  [ Slurm Node N ]
        +---------------+  +---------------+  +---------------+
        | R Coordinator |  | R Coordinator |  | R Coordinator |
        | Rcpp Kernel   |  | Rcpp Kernel   |  | Rcpp Kernel   |
        | OpenMP 32 Thd |  | OpenMP 32 Thd |  | OpenMP 32 Thd |
        +---------------+  +---------------+  +---------------+
                 \                |                /
                  v               v               v
        +-----------------------------------------------+
        | Hierarchical Quantile Tree Reduction (Disk)   |
        +-----------------------------------------------+
                              |
                              v
            [ Basel III Risk Metrics Computed ]
```

### Hasil Akhir (Metrics Comparison):
* **Execution Time:** Turun dari **270 menit** ke **8 menit 12 detik** (Akselerasi $\approx 33\times$).
* **Network Throughput Overhead:** Berkurang dari **420 GB transferred data** menjadi **hanya 120 MB** (karena arsitektur zero-data-movement via memory mapping).
* **Memory Stability:** Node pod memory consumption stabil konstan di angka 3,2 GB RAM flat per node (bebas dari bahaya OOM kill).

---

## 9. Trade-offs

Setiap keputusan optimasi HPC membawa konsekuensi arsitektural. Berikut komparasi trade-off:

```
+---------------------------------------------------------------------------------------+
| MATRIKS TRADE-OFF ARSITEKTUR HPC R                                                    |
+---------------------+-------------------+---------------------+-----------------------+
| Arsitektur          | Keuntungan        | Kerugian/Risiko     | Skenario Penggunaan   |
+---------------------+-------------------+---------------------+-----------------------+
| Rcpp + OpenMP       | Latensi terendah; | Debugging kompleks; | Operasi matriks murni;|
| (Zero-Copy)         | Throughput instruksi| Memory corruption jika| Algoritma iteratif  |
|                     | CPU maksimal;     | salah indeks array; | berulang (Markov/MCMC)|
|                     | Memory footprint  | Crash interpreter   |                       |
|                     | terkecil.         | jika panggil R API. |                       |
+---------------------+-------------------+---------------------+-----------------------+
| Forking             | Sangat mudah      | Tidak jalan di Win; | Transformasi data R   |
| (`mclapply`)        | diimplementasikan;| Bahaya deadlock jika| standar;              |
|                     | Tidak ada biaya   | link dengan BLAS;   | Batch processing satu |
|                     | transfer data     | CoW pecah memicu    | mesin POSIX.          |
|                     | inisial.          | OOM instan.         |                       |
+---------------------+-------------------+---------------------+-----------------------+
| Sockets             | Isolasi memori    | Overhead serialisasi| Worker heterogen      |
| (`PSOCK` /          | total (aman);     | masif;              | melintasi OS;         |
| `callr`)            | Cross-platform.   | Latensi transfer    | Task independen ber-  |
|                     |                   | data besar sangat   | durasi panjang (jam). |
|                     |                   | buruk.              |                       |
+---------------------+-------------------+---------------------+-----------------------+
| Out-of-Core FBM     | Mengolah data     | Bergantung pada     | Data tabular gigantik;|
| (`bigstatsr`)       | > RAM; Data aman  | kecepatan I/O Disk; | Model linear/PCA pada |
|                     | pada media disk.  | Setup struktur data | data genetik/keuangan.|
|                     |                   | lebih kaku.         |                       |
+---------------------+-------------------+---------------------+-----------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Forking Deadlock dengan Multithreaded BLAS (OpenBLAS / MKL)
* **Penyebab:** Ketika R dikompilasi dengan pustaka BLAS multi-thread (seperti Intel MKL atau OpenBLAS), thread pool BLAS diinisialisasi sebelum proses di-*fork*. Berdasarkan standar POSIX, saat `fork()` dipanggil, hanya thread pemanggil yang diduplikasi ke proses anak (*child process*). Mutex lock internal BLAS yang sedang dipegang oleh thread lain pada proses induk akan berada dalam status *locked* permanen di proses anak, menyebabkan proses *hang/deadlock* tanpa batas.
* **Troubleshooting & Fix:** Matikan multi-threading internal BLAS sebelum memanggil `mclapply` atau `future::multicore`:

```r
library(RhpcBLASctl)

# Matikan multithreading BLAS sebelum fork
blas_set_num_threads(1)
omp_set_num_threads(1)

# Sekarang aman mengeksekusi forking
res <- parallel::mclapply(1:10, function(i) {
  # Komputasi linear algebra aman di sini
  matrix(rnorm(100), 10, 10) %*% matrix(rnorm(100), 10, 10)
}, mc.cores = 4)

# Kembalikan alokasi thread BLAS jika diperlukan komputasi linear algebra terpadu
blas_set_num_threads(4)
```

### 10.2 Dangling Pointer pada Alokasi Sementara Rcpp
* **Penyebab:** Menyimpan pointer langsung ke array sementara yang dialokasikan oleh Rcpp constructor inline. Objek sementara akan segera dihapus dari heap oleh garbage collector setelah ekspresi selesai dievaluasi, meninggalkan pointer mengambang (*dangling pointer*).
* **Troubleshooting:**

```cpp
// SALAH (MEMICU SEGMENTATION FAULT ATAU SILENT DATA CORRUPTION):
double* get_bad_pointer(Rcpp::NumericMatrix M) {
    return M.begin(); // Berbahaya jika M dipanggil dari ekspresi anonim sementara
}

// BENAR: Selalu pastikan SEXP dilindungi atau kelola data di C++ STL jika lifetime panjang
// [[Rcpp::export]]
void process_matrix_safely(Rcpp::NumericMatrix M) {
    // Pastikan objek M di-pass by reference atau handle dengan scope terproteksi
    double* ptr = M.begin();
    // Gunakan ptr secara eksklusif HANYA di dalam lifetime function scope ini
    ptr[0] = 42.0;
}
```

### 10.3 Broken Copy-on-Write Akibat Mutasi Metadata
* **Penyebab:** Pada Linux, `fork()` memanfaatkan *Copy-on-Write* (CoW) untuk menghemat memori. Namun, operasi sepele seperti membaca atribut class, memanggil `names(x) <-`, atau modifikasi metadata kecil pada objek R besar di dalam child process akan meningkatkan nilai `REFCNT` dan memaksa kernel Linux menduplikasi seluruh blok memori 100 GB ke RAM child process, berujung pada OOM Crash.
* **Troubleshooting:** Pastikan data besar di R environment bersifat murni *read-only*. Jangan pernah memanggil fungsi yang mengubah atribut objek atau melakukan casting tipe data implisit (misal: integer ke numeric) di dalam loop child process.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis kode komputasi performa tinggi ke environment produksi:

- [ ] **BLAS Thread Sanitization:** Pustaka BLAS dinonaktifkan multithreading-nya (`blas_set_num_threads(1)`) jika sistem menggunakan paralelisasi tingkat proses (`fork`/`multisession`).
- [ ] **Native Zero-Copy Guarantee:** Kernel Rcpp menerima matriks besar menggunakan `const Rcpp::NumericMatrix&` (referensi konstan) untuk menghindari duplikasi data di batas FFI (Foreign Function Interface).
- [ ] **Thread-Safety Compliance:** Tidak ada interaksi ke R API (seperti `Rcpp::Rcout`, `R::rnorm`, `Rf_eval`, atau alokasi objek R) dari dalam blok eksekusi paralel OpenMP `#pragma omp parallel`.
- [ ] **Serialization Cost Elimination:** Arsitektur transfer data besar menggunakan file-backed descriptors (`FBM` atau Arrow Memory-Mapped Table) daripada passing variabel global via socket argument.
- [ ] **Garbage Collection (GC) Optimization:** Melakukan pre-allocation vektor penuh sebelum loop; hindari mutasi `x <- c(x, new_val)` yang memicu reallocation memory terus menerus.
- [ ] **NUMA Node Pinning:** Pada server multi-socket NUMA, jalankan proses R master menggunakan utilitas `numactl --interleave=all` atau bind proses worker ke NUMA node lokal untuk mencegah latensi bus QPI/UPI.
- [ ] **Deterministic Random Number Generation (RNG):** Selalu atur generator RNG paralel yang kompatibel dengan L'Ecuyer (`RNGkind("L'Ecuyer-CMRG")` atau parameter `future.seed = TRUE`) untuk memastikan hasil simulasi dapat direproduksi (*reproducible*).

---

## 12. Hands-on Practice

Praktikum ini akan memandu Anda membangun modul akselerasi algoritma optimasi numerik skala besar. Seluruh artefak kode wajib disimpan di direktori: `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── Makefile
├── src/
│   └── distance_kernel.cpp
└── run_hpc_pipeline.R
```

### Langkah 1: Siapkan Direktori Praktikum
Buka terminal dan buat folder kerja:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

### Langkah 2: Buat Kernel Jarak Euklides Terdistribusi (C++ & OpenMP)
Simpan file berikut di `hands-on/m02/src/distance_kernel.cpp`:

```cpp
#include <Rcpp.h>
#include <cmath>
#include <omp.h>

// [[Rcpp::plugins(openmp)]]

//' Menghitung Pairwise Euclidean Distance Matrix Paralel
//' @param A Matriks referensi (N x D)
//' @param B Matriks query (M x D)
//' @param threads Alokasi CPU cores
//' @return Matriks Jarak (N x M)
// [[Rcpp::export]]
Rcpp::NumericMatrix compute_euclidean_distance_par(const Rcpp::NumericMatrix& A, 
                                                   const Rcpp::NumericMatrix& B, 
                                                   int threads = 4) {
    int n = A.nrow();
    int m = B.nrow();
    int d = A.ncol();
    
    if (d != B.ncol()) {
        Rcpp::stop("Dimensi fitur matrix A dan B tidak sinkron!");
    }
    
    Rcpp::NumericMatrix dist(n, m);
    
    const double* pA = A.begin();
    const double* pB = B.begin();
    double* pDist = dist.begin();
    
    omp_set_num_threads(threads);
    
    #pragma omp parallel for schedule(dynamic, 64) shared(pA, pB, pDist, n, m, d)
    for (int j = 0; j < m; ++j) {
        for (int i = 0; i < n; ++i) {
            double acc = 0.0;
            for (int k = 0; k < d; ++k) {
                // Column-major indexing
                double diff = pA[i + k * n] - pB[j + k * m];
                acc += diff * diff;
            }
            pDist[i + j * n] = std::sqrt(acc);
        }
    }
    
    return dist;
}
```

### Langkah 3: Buat Production Script Integrasi
Simpan script berikut di `hands-on/m02/run_hpc_pipeline.R`:

```r
#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(Rcpp)
  library(microbenchmark)
})

cat("=== HPC Production Pipeline Module 02 ===\n")

# Kompilasi C++ Kernel
kernel_path <- "src/distance_kernel.cpp"
cat(sprintf("Mengompilasi kernel C++: %s ...\n", kernel_path))
sourceCpp(kernel_path)

# Inisialisasi Mock Data Skala Tinggi
N <- 10000  # Objek A
M <- 2000   # Objek B
D <- 50     # Dimensi

cat(sprintf("Mengalokasikan matriks: A (%dx%d), B (%dx%d)\n", N, D, M, D))
set.seed(123)
mat_A <- matrix(rnorm(N * D), nrow = N, ncol = D)
mat_B <- matrix(rnorm(M * D), nrow = M, ncol = D)

# Baseline Benchmark: Pure R implementation
r_distance_subset <- function(A, B) {
  # Eksekusi sampel kecil untuk estimasi baseline
  as.matrix(dist(rbind(A[1:100, ], B[1:50, ])))[1:100, 101:150]
}

cat("Memulai eksekusi benchmark performa (1 Thread vs 4 Threads)...\n")
bm <- microbenchmark(
  Cpp_1_Thread = compute_euclidean_distance_par(mat_A, mat_B, threads = 1),
  Cpp_4_Thread = compute_euclidean_distance_par(mat_A, mat_B, threads = 4),
  times = 5
)

print(bm)

# Validasi Presisi Numerik
cat("Memverifikasi presisi hasil...\n")
sample_cpp <- compute_euclidean_distance_par(mat_A[1:10, ], mat_B[1:5, ], threads = 1)
sample_r <- as.matrix(dist(rbind(mat_A[1:10, ], mat_B[1:5, ])))[1:10, 11:15]

diff_val <- max(abs(sample_cpp - sample_r))
if (diff_val < 1e-12) {
  cat(sprintf("[BERHASIL] Verifikasi numerik valid (Max diff: %e)\n", diff_val))
} else {
  stop(sprintf("[ERROR] Deviasi numerik terdeteksi: %e\n", diff_val))
}
```

### Langkah 4: Eksekusi Pipeline
Jalankan script via terminal:
```bash
Rscript run_hpc_pipeline.R
```

Periksa hasil output benchmark, pastikan scaling akselerasi thread mendekati linear (speedup $>3\times$ pada 4 cores).

---

## 13. Exercise

### Level Easy: Identifikasi Pelanggaran Copy-on-Modify
Diberikan script R berikut yang mengalami penurunan performa parah pada komputasi 50.000 iterasi.
```r
# Bad pattern
slow_accumulator <- function(n) {
  res <- c()
  for (i in 1:n) {
    res <- c(res, i * 2) # Mengapa ini bermasalah?
  }
  return(res)
}
```
* **Tugas Anda:** 
  1. Jelaskan apa yang terjadi pada *internal memory heap* R pada setiap iterasi loop.
  2. Tulis ulang kode di atas menggunakan teknik *vector pre-allocation* dan alternatif *functional vectorization*. Buktikan percepatan performa minimal $100\times$ via `bench::mark()`.

### Level Medium: Thread-Safe Parallel Moving Average di Rcpp
* **Kebutuhan:** Bangun fungsi `Rcpp` bernama `parallel_moving_average(const Rcpp::NumericVector& vec, int window_size, int threads)` menggunakan OpenMP.
* **Kriteria Keberhasilan:**
  * Tidak menggunakan library RcppRoll atau implementasi loop R.
  * Menangani kalkulasi boundary secara elegan.
  * Bebas dari kondisi *data race* (verifikasi via compiler sanitizer `-fsanitize=thread`).

### Level Hard: Dynamic Work-Stealing Cluster Task Scheduler
* **Kebutuhan:** Buat custom distributed scheduler di R murni menggunakan arsitektur non-blocking socket IPC (`parallel::makeCluster(..., type = "PSOCK")`).
* **Kriteria Keberhasilan:**
  * Mengirimkan $1.000$ task berdurasi eksekusi acak (non-uniform job time) ke 8 background workers.
  * Worker yang selesai lebih awal harus mengambil task berikutnya (*work-stealing/dynamic scheduling*), menghindari antrean kaku (*static chunking*).
  * Sistem harus mampu mendeteksi worker yang crash secara deterministik tanpa membuat seluruh master pipeline terhenti (*hang*).

---

## 14. Challenge

### Studi Kasus: Out-of-Core Real-time Genome-Wide Association Study (GWAS) Kernel

#### Deskripsi Skenario:
Sebuah konsorsium bioinformatika memiliki dataset matriks varian genetik (*Single Nucleotide Polymorphism* - SNP) berukuran **400.000 subjek $\times$ 500.000 marker genetik**. File tersimpan dalam format mentah biner flat (tipe integer 8-bit, estimasi volume $\approx 200\text{ GB}$). RAM server yang tersedia terbatas pada angka **32 GB**.

Anda ditugaskan mendesain sistem kalkulasi matriks korelasi Pearson antara setiap marker genetik dengan vektor fenotipe klinis (panjang 400.000 float64).

#### Spesifikasi & Batasan Teknis:
1. **Zero High-RAM Usage:** Sistem dilarang mengalokasikan memori RAM proses R melebihi 16 GB pada kondisi puncak (*peak memory*).
2. **Architecture Requirements:**
   * Harus mengimplementasikan custom C++ parser yang membaca blok biner disk via `mmap()` atau `bigstatsr::FBM`.
   * Loop pemrosesan statistika harus di-unroll secara efisien dan diparalelkan dengan `OpenMP` serta instruksi SIMD (*Single Instruction, Multiple Data*).
   * Menghitung nilai $t$-statistic dan $p$-value untuk setiap 500.000 marker secara streaming.
3. **Resilience & SLA:**
   * Sistem harus memiliki kemampuan *checkpointing*: jika proses terputus di marker ke-250.000, eksekusi dapat di-*resume* tanpa memulai ulang dari awal.
   * Keseluruhan pemrosesan 500.000 marker harus tuntas dalam waktu $\le 30$ menit pada server 32-core.

#### Output yang Diharapkan:
Desain arsitektur end-to-end, skema alokasi virtual memory, kode kernel C++ terintegrasi, dan failure-recovery mechanism script di R.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic Knowledge (Pilihan Ganda / Konsep Singkat)
1. Apa arti dari status bit `REFCNT > 1` pada struktur internal `SEXPREC` di R?
2. Mengapa fungsi `mclapply` di R base tidak menghasilkan percepatan paralel ketika dijalankan pada sistem operasi Microsoft Windows?
3. Apa perbedaan mendasar antara tipe paralel cluster `FORK` dan `PSOCK` dalam konsumsi memori fisik RAM?
4. Apa yang menyebabkan pemanggilan fungsi R runtime seperti `Rcpp::Rcout` atau `rnorm()` berbahaya di dalam blok multithreading OpenMP?
5. Mengapa format representasi matriks R disebut sebagai *Column-Major Order*? Bagaimana rumusan indeks linear 1D untuk mengakses sel baris $i$ dan kolom $j$ pada matriks dengan jumlah baris $N$?

### Bagian B: Intermediate (Analisis Arsitektur & Kasus)
1. Analisis mengapa penggunaan `serialize()` secara masif pada cluster berbasis `PSOCK` dapat menyebabkan CPU utilization pada worker node terlihat rendah meskipun task sedang berjalan.
2. Anda memiliki matriks 20 GB. Anda menggunakan `future::plan(multicore)` pada Linux. Namun tak lama setelah eksekusi berjalan, Linux OS memicu *OOM Killer*. Mengapa semantik *Copy-on-Write* (CoW) gagal melindungi konsumsi RAM Anda?
3. Bagaimana mekanisme *Page Fault* pada memori virtual memungkinkan paket seperti `bigstatsr` memproses file 150 GB di dalam mesin yang hanya memiliki RAM 16 GB?
4. Mengapa kita harus menyetel alokasi thread internal pustaka OpenBLAS/MKL ke angka `1` sebelum melakukan task parallelization di level proses R?
5. Dalam kondisi apa teknik paralelisasi komputasi justru menghasilkan runtime yang lebih lambat secara signifikan dibandingkan eksekusi serial satu core (*Amdahl's Law penalty*)?

### Bagian C: Skenario Kasus Produksi
1. **Skenario Deadlock di Cluster Kubernetes:**
   Sebuah microservice R di dalam container Docker Kubernetes mengeksekusi komputasi paralel menggunakan paket `parallel` (`mcmapply`). Service tersebut sering mengalami kondisi *freeze/unresponsive* tanpa memicu pesan error apa pun, dan health check probe Kubernetes akhirnya me-restart container secara paksa. Hasil dump stacktrace menunjukkan instruksi berhenti di `libopenblas.so`. Analisis apa yang terjadi dan tuliskan instruksi konfigurasi Dockerfile / R script untuk memulihkannya.
2. **Skenario Memory Leak di Rcpp:**
   Seorang insinyur perangkat lunak mengimplementasikan algoritma optimasi di C++ menggunakan `Rcpp`. Meskipun ia tidak menggunakan operator `new` atau alokasi pointer mentah manual, konsumsi RAM proses R master terus membengkak secara linear dari 500 MB hingga 64 GB seiring berjalannya simulasi harian. Identifikasi kemungkinan kesalahan arsitektural yang berkaitan dengan GC tracking dan proxy object Rcpp.
3. **Skenario Network Saturation pada Distributed Slurm Node:**
   Sebuah tim quant mengeksekusi batch testing pada 100 node cluster Slurm menggunakan R. Begitu script berjalan, performa I/O jaringan internal data center kolaps, dan waktu pembacaan file membengkak hingga $50\times$ lebih lambat. Pola pembacaan file apa yang dilakukan oleh worker script R yang memicu badai I/O (*I/O storm*) tersebut, dan bagaimana arsitektur staging caching lokal memitigasinya?

---

## 16. Summary

1. **R Runtime Constraints:** Interpreter GNU R bersifat single-threaded dan tidak thread-safe. Pustaka komputasi enterprise mengatasi batasan ini dengan membagi layer: R sebagai *control plane/orchestrator*, dan sub-engine C++/POSIX sebagai *execution plane*.
2. **Memory Hierarchy Awareness:** Efisiensi komputasi tingkat tinggi di R sangat bergantung pada pemahaman alokasi memori internal (`SEXP`). Duplikasi tersembunyi via *Copy-on-Modify* harus dieliminasi menggunakan teknik *pre-allocation*, *zero-copy C++ pointers* via `Rcpp`, dan penghindaran *broken-CoW* pada proses forking.
3. **Overhead Minimization:** Paralelisasi terdistribusi yang efisien bukan sekadar menambah jumlah core, melainkan meminimalkan rasio transfer data versus kalkulasi. Menghindari serialisasi TCP dengan mengadopsi *POSIX Shared Memory* atau *Memory-Mapped Files* (`bigstatsr`, `arrow`) adalah kunci utama skalabilitas enterprise.
4. **Resilient Production Pipeline:** Arsitektur komputasi performa tinggi yang handal wajib mengisolasi konkurensi (mencegah deadlock multi-threading BLAS), menjamin reproduktifitas numerik RNG, dan menerapkan proteksi terhadap lonjakan alokasi memori (*OOM prevention*).