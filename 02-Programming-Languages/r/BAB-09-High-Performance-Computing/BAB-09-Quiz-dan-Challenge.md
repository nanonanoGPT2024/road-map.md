# BAB 09: Quiz, Challenge, & Knowledge Check
**High-Performance Computing (HPC), Profiling, & Rcpp**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Pertanyaan 1: Sampling Profiler vs Deterministic Profiler
Jelaskan perbedaan fundamental dalam cara kerja *sampling/statistical profiler* (seperti `Rprof` dan visualisasinya di `profvis`) dibandingkan *deterministic/instrumented profiler*. Mengapa `Rprof` menggunakan interval sampling berbasis timer sinyal OS (misalnya tiap 10–20 milidetik) alih-alih mencegat (*intercepting*) setiap eksekusi fungsi R? Apa konsekuensi teknis dari pendekatan ini terhadap deteksi *micro-bottleneck* (fungsi berkecepatan mikrodetik)?

### Pertanyaan 2: ALTREP dan Mekanisme Copy-on-Modify
R mengandalkan semantik *Copy-on-Modify*. Sejak R versi 3.5, diperkenalkan arsitektur **ALTREP** (*Alternative Representations*). Jelaskan bagaimana ALTREP mencegah alokasi memori berlebih saat mengeksekusi operasi seperti `x <- 1:1e9` dan `y <- x[1:100]`. Bagaimana ALTREP berinteraksi dengan Garbage Collector (GC), dan pada kondisi apa representasi ALTREP secara tak sengaja "ter-materialisasi" (*materialized*) menjadi vektor konvensional di RAM?

### Pertanyaan 3: Life-Cycle SEXP dan Rcpp RAII
Dalam C API standar R, alokasi objek `SEXP` wajib dilindungi secara manual menggunakan makro `PROTECT()` dan dilepaskan dengan `UNPROTECT()`. Jelaskan bagaimana pustaka **Rcpp** mengabstraksi mekanisme proteksi ini melalui paradigma **RAII** (*Resource Acquisition Is Initialization*). Apa yang terjadi pada *garbage collection protection stack* R ketika kelas C++ seperti `Rcpp::NumericVector` dialokasikan di dalam *scope* lokal versus ketika terjadi C++ *exception* yang dilempar (*thrown*) kembali ke runtime R?

### Pertanyaan 4: Model Konkurensi: POSIX Fork vs Socket/RPC
Jelaskan perbedaan mendasar antara model konkurensi berbasis **Process Forking** (`parallel::mclapply` di Linux/macOS) dan model **Socket/Worker Clusters** (`parallel::parLapply` atau `future::multisession`). Tinjau secara spesifik dari tiga aspek:
1. *Memory sharing* dan perilaku Copy-on-Write (COW).
2. Overhead *inter-process communication* (IPC) dan serialisasi data.
3. Keterbatasan sistem operasi (mengapa forking tidak bekerja natively di Windows).

### Pertanyaan 5: Batas Optimalisasi Vectorized Base R vs Rcpp Explicit Loops
Sering dikatakan bahwa "R vectorized code sudah ditulis dalam bahasa C, sehingga mengonversinya ke Rcpp tidak akan memberikan lonjakan performa yang signifikan." Buktikan mengapa argumen ini adalah miskonsepsi dalam arsitektur memori modern. Tinjau jawaban Anda berdasarkan konsep *cache locality* (L1/L2/L3 cache), alokasi vektor intermediat temporer pada ekspresi bertingkat (misalnya: `res <- (a + b) * c - d`), dan instruksi SIMD.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Pertanyaan 1: In-Place Mutation dan Side-Effect Leakage di Rcpp
Perhatikan potongan kode C++ via Rcpp berikut:
```cpp
// [[Rcpp::export]]
void inplace_scale(Rcpp::NumericVector x, double factor) {
    for(int i = 0; i < x.size(); ++i) {
        x[i] *= factor;
    }
}
```
Ketika fungsi ini dipanggil di R dengan:
```r
a <- c(1.0, 2.0, 3.0)
b <- a
inplace_scale(a, 2.0)
```
Mengapa nilai `b` di lingkungan R ikut berubah menjadi `c(2.0, 4.0, 6.0)`, melanggar paradigma imutabilitas R? Jelaskan secara arsitektural bagaimana `Rcpp::NumericVector` membungkus *pointer* mendasar dari objek `SEXP`, dan metode apa yang harus diterapkan jika developer ingin mengizinkan in-place mutation secara aman tanpa merusak integritas objek yang memiliki multiple binding (*reference count* > 1)?

### Pertanyaan 2: OpenMP dan Pelanggaran Thread-Safety R Core
Anda menulis fungsi Rcpp yang diakselerasi dengan OpenMP:
```cpp
#include <Rcpp.h>
#include <omp.h>

// [[Rcpp::plugins(openmp)]]
// [[Rcpp::export]]
void parallel_worker(Rcpp::NumericVector x) {
    #pragma omp parallel for
    for(int i = 0; i < x.size(); ++i) {
        if (x[i] < 0) {
            Rcpp::Rcout << "Negative value at: " << i << std::endl;
        }
        x[i] = std::sqrt(std::abs(x[i]));
    }
}
```
Mengapa kode di atas memiliki cacat desain kritis yang berpotensi menghasilkan *Segmentation Fault* atau *heap corruption* secara acak di server produksi? Tinjau keterbatasan arsitektur R Core C API terhadap operasi multithreading (terutama I/O R, memory allocator R, dan error handler `Rf_error`).

### Pertanyaan 3: BLAS Thread-Contention dalam Model Multiprocessing
Sebuah simulasi statistik menggunakan fungsi RcppArmadillo atau base R yang mengeksekusi dekomposisi matriks `chol()` di dalam loop paralel via `mclapply(mc.cores = 32)`. Lingkungan komputasi menggunakan backend OpenBLAS atau Intel MKL. Mengapa performa komputasi justru anjlok 10x lipat lebih lambat dibandingkan eksekusi single-core, dan penggunaan CPU menunjukkan utilisasi tinggi pada *kernel system time* (*context switching*)? Bagaimana mekanisme penanganan *nested parallelism* untuk mengatasi anomali ini?

### Pertanyaan 4: Serialisasi Objek Tak Tereksport (Non-Exportable References)
Saat mendistribusikan beban komputasi menggunakan paket `future` (`multisession` cluster), pengiriman objek model seperti koneksi database (`DBI::dbConnect`), *external pointers* C++ (`Rcpp::XPtr`), atau environment model neural network (misalnya objek XGBoost pointer) menyebabkan crash atau worker mengembalikan pointer `0x0` (NULL). Analisis siklus serialisasi/deserialisasi IPC di R dan jelaskan pola arsitektur yang benar untuk mendistribusikan objek yang membungkus resource C/C++ eksternal.

### Pertanyaan 5: Truncated ALTREP Materialization pada Rcpp Direct Pointer Access
Jika sebuah fungsi Rcpp dirancang menerima vektor integer besar dengan mengekstrak raw pointer menggunakan `INTEGER(x)` atau `DATAPTR(x)` untuk eksekusi loop berkecepatan tinggi, apa implikasinya jika input yang dilewatkan dari R adalah objek ALTREP *compact sequence* (seperti `seq_len(1e9)`)? Jelaskan mengapa pendekatan tersebut dapat memicu lonjakan memori tak terduga (*RAM spike*) hingga puluhan Gigabyte sebelum komputasi C++ dimulai.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM Killer dan Starvasi Worker pada VM 128-Core
**Konteks:** Sistem *batch-scoring* portofolio risiko kredit memproses data frame sebesar 15 GB di sebuah instans Linux (128 vCPU, 256 GB RAM). Pipeline mengeksekusi komputasi menggunakan `parallel::mclapply(..., mc.cores = 64)`.
**Masalah:** 
Secara teori, mekanisme POSIX `fork()` memanfaatkan *Copy-on-Write* (COW), sehingga 15 GB data awal seharusnya digunakan bersama (*read-only shared memory*). Namun, 10 menit setelah proses berjalan, swap space membengkak, kernel Linux mengeksekusi `OOM Killer` yang menghentikan worker secara acak, dan server tidak merespons (*unresponsive*). CPU utilization turun drastis dari 6400% ke mendekati 0%.
**Analisis Log:**
Sistem mencatat adanya pemanggilan Garbage Collection (`gc()`) frekuen di dalam fungsi worker sebelum eksekusi selesai.

**Pertanyaan Diagnostik:**
1. Bagaimana siklus Garbage Collection R memicu fragmentasi memori pada halaman *Copy-on-Write* (COW) sistem operasi Linux, sehingga mematikan efisiensi memori bersama pada proses anak (*child processes*)?
2. Mengapa modifikasi referensi kecil (seperti penambahan kolom sementara atau pembaruan atribut objek) pada data frame yang di-*fork* menyebabkan seluruh tabel memori diduplikasi secara fisik?
3. Rancang strategi arsitektur ulang untuk sistem ini agar dapat memproses data secara paralel di 64 core tanpa risiko replikasi memori yang memicu OOM (gunakan pendekatan *shared memory* / Apache Arrow / POSIX shared memory).

---

### Skenario B: Race Condition dan Segmentasi Memori pada Fast Rolling-Feature Engine
**Konteks:** Tim Algorithmic Trading membangun sistem ekstraksi fitur mikro-struktur pasar menggunakan Rcpp. Engine tersebut menghitung *rolling exponential weighted covariance* terhadap *tick data* berfrekuensi tinggi (50 juta baris) menggunakan eksekusi paralel OpenMP.
**Masalah:**
Pada saat pengujian beban penuh (*load test*), pipeline secara berkala menghasilkan nilai output `NaN` pada baris tertentu secara non-deterministik. Selain itu, sekitar 1 dari 10 eksekusi mengalami insiden fatal:
`*** caught segfault *** address 0x7ffd9b..., cause 'memory not mapped'`
Saat dieksekusi di *single-thread* (OpenMP disabled), kalkulasi 100% akurat dan crash tidak pernah terjadi.
**Potongan Kode yang Dicurigai:**
```cpp
// [[Rcpp::plugins(openmp)]]
// [[Rcpp::export]]
Rcpp::List compute_rolling_features(Rcpp::NumericMatrix data, int window) {
    int n = data.nrow();
    int p = data.ncol();
    Rcpp::NumericMatrix out(n, p);
    
    #pragma omp parallel for
    for (int j = 0; j < p; ++j) {
        for (int i = window; i < n; ++i) {
            // Kalkulasi matematis kompleks
            double val = internal_calc(data(i, j)); 
            out(i, j) = val;
        }
    }
    return Rcpp::List::create(Rcpp::Named("features") = out);
}
```

**Pertanyaan Diagnostik:**
1. Di mana letak pelanggaran thread-safety pada penulisan matriks `out` dan pemanggilan operator akses `data(i, j)` pada `Rcpp::NumericMatrix` di lingkungan OpenMP?
2. Mengapa operator `()` pada kelas matriks Rcpp tidak *thread-safe* jika memicu bound checking atau alokasi internal R Core?
3. Ubah implementasi fungsi di atas menggunakan pointer C++ mentah (*raw pointers*) atau struktur data standar `std::vector` / C++ thread-safe abstractions yang menjamin integritas memori tanpa segfault dan bebas dari *false sharing* pada CPU cache line.

---

### Skenario C: Trade-off Arsitektur Sistem Real-time Scoring Service
**Konteks:** Anda adalah Principal Architect yang memimpin integrasi model statistik bayesian kompleks ke dalam API mikroservis R (menggunakan Plumber) dengan target SLA *latency* p99 < 150 milidetik di bawah konkurensi 200 *requests per second* (RPS).
**Masalah:**
Fase scoring membutuhkan inversi matriks berdimensi $500 \times 500$ dan pembaruan bobot iteratif sebanyak 100 iterasi per transaksi masuk. Tim mengusulkan 3 opsi implementasi:
- **Opsi 1:** Implementasi Base R murni yang dioptimasi secara vektorisasi + multithreaded OpenBLAS runtime.
- **Opsi 2:** Engine berbasis Rcpp yang menggunakan pustaka C++ linear algebra `RcppArmadillo` yang dikompilasi dengan optimasi `-O3 -march=native`.
- **Opsi 3:** Distribusi beban komputasi via *asynchronous micro-batching* memanfaatkan worker pool `future` berbasis IPC lokal.

**Pertanyaan Diagnostik:**
1. Evaluasi Opsi 1 dan Opsi 3: Mengapa keduanya dijamin gagal memenuhi SLA latency p99 < 150ms pada beban 200 RPS? Tinjau latency overhead dari *context switching* OpenBLAS dan serialisasi IPC pada `future`.
2. Pada Opsi 2, bagaimana Anda mengonfigurasi penggunaan memori matriks Armadillo (`arma::mat`) agar tidak melakukan *deep-copy* saat menerima payload matriks dari payload Plumber JSON?
3. Rancang arsitektur konkurensi proses Plumber (misal: multi-process isolation via worker model/Gunicorn-like R supervisor) yang dipadukan dengan komputasi Rcpp single-threaded/deterministic per core untuk menghindari saturasi CPU dan thread contention.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Parallel Rolling Covariance Engine

#### Deskripsi Masalah
Dalam analisis data runtun waktu skala besar (seperti telemetri IoT atau pasar finansial), fungsi rolling window bawaan R (misalnya via `zoo::rollapply` atau manipulasi loop konvensional) tidak memiliki throughput yang memadai untuk dataset dengan skala $10^7$ observasi dan puluhan variabel. Penggunaan fungsi vectorized R murni sering kali kehabisan memori (*out of memory*) karena pembentukan alokasi slice matriks temporer di setiap iterasi window.

Anda diminta merancang, mengimplementasikan, dan membuktikan efisiensi dari **High-Throughput Parallel Rolling Covariance Engine** berbasis C++ via `Rcpp` dan `RcppArmadillo`/`std::vector` yang mampu menghitung varians dan kovarians bergerak secara multi-thread dengan *zero-copy overhead*.

#### Kebutuhan Teknis (Requirements)
1. **Fungsi Utama:** Buat fungsi C++ via Rcpp dengan signature:
   ```cpp
   // [[Rcpp::export]]
   Rcpp::List parallel_rolling_cov(
       Rcpp::NumericMatrix X, 
       Rcpp::NumericMatrix Y, 
       int window, 
       int n_threads
   );
   ```
2. **Kalkulasi Single-Pass / Update Numerik Stabil:**
   Implementasikan algoritma pembaruan online numerik yang stabil (seperti modifikasi Welford's algorithm untuk rolling window sliding) untuk menghindari kehilangan presisi numerik (*catastrophic cancellation*) dan menghindari *re-computation* seluruh elemen di dalam window dari awal ($O(1)$ complexity per step window, bukan $O(W)$).
3. **Konkurensi Thread-Safe (OpenMP):**
   Membagi partisi komputasi antar kolom/fitur (atau chunk data horizontal) secara multi-thread menggunakan OpenMP tanpa memanggil satu pun fungsi internal R C API di dalam blok `#pragma omp parallel`.
4. **Zero-Copy Memory Access:**
   Akses data input `X` dan `Y` harus dilakukan melalui pointer memori langsung (`const double*`) tanpa melakukan duplikasi atau instansiasi objek `Rcpp::NumericMatrix` di dalam loop internal.

#### Batasan Teknis (Constraints)
- Tidak boleh terjadi alokasi memori dinamis di dalam inner loop komputasi C++.
- Wajib bebas dari kebocoran memori (*memory leak*). Kode harus tervalidasi bersih melalui pengujian AddressSanitizer (ASAN).
- Penggunaan CPU scaling harus linier hingga minimal 8 core (speedup minimal $5.5\times$ dibanding eksekusi 1 core pada dataset 10 juta baris).
- Output yang dihasilkan harus identik secara presisi numerik (toleransi $10^{-9}$) dengan kalkulasi referensi R dasar.

#### Ekspektasi Output Deliverables
1. **Source Code Lengkap:** File C++ (`.cpp`) yang memuat modul Rcpp dengan konfigurasi compile flags yang optimal (`-O3`, `-mavx2`, OpenMP support).
2. **Skrip Profiling & Benchmark:** Skrip R yang membandingkan:
   - Penggunaan memori (via `bench::mark()` atau `profvis`).
   - Throughput (iterasi per detik) terhadap `zoo::rollapply()` atau loop native R.
   - Uji skalabilitas thread (1, 2, 4, 8 threads).
3. **Laporan Diagnostik Singkat:** Tunjukkan grafik atau tabel hasil benchmark yang membuktikan performa eksekusi, efisiensi konsumsi RAM, dan ketiadaan overhead Garbage Collection (GC = 0).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme deteksi profil eksekusi sampling oleh `Rprof` dan keterbatasannya dalam mengukur latency instruksi tingkat mikroprosesor.
- [ ] Arsitektur internal `SEXP` (S-Expression) dan sistem penandaan memori (*generation-based garbage collection*) pada runtime R.
- [ ] Cara kerja Copy-on-Modify, alokasi memori ALTREP, dan skenario yang membatalkan optimasi ALTREP.
- [ ] Bahaya thread-safety pada R Core API: Mengapa alokasi memori R, deserialisasi, evaluasi ekspresi, dan I/O *harus* dieksekusi secara strictly single-threaded.
- [ ] Arsitektur Fork-based Multiprocessing (`mclapply`) vs Socket-based RPC Multiprocessing (`future::multisession`), beserta karakteristik Copy-on-Write (COW) pada OS Linux.
- [ ] Dampak buruk dari *thread contention* yang timbul akibat benturan nesting antara library OpenBLAS/MKL dan model paralelisme R.
- [ ] Konsep abstraksi RAII pada `Rcpp` dan pemetaan representasi tipe data R ke primitif C++ (`SEXP` $\leftrightarrow$ `NumericVector` $\leftrightarrow$ `std::vector` $\leftrightarrow$ `arma::mat`).

### Saya tidak perlu menghafal:
- [ ] Nilai numerik konstan dari tipe internal `SEXPTYPE` (misalnya `REALSXP = 14`, `INTSXP = 13`).
- [ ] Seluruh sintaks dan signature fungsi primitif pada header C R murni (`Rinternals.h`).
- [ ] Detail implementasi register instruksi assembly instruksi vektorisasi CPU (seperti daftar register AVX-512) di luar flag kompilator dasar (`-march=native`).
- [ ] Kode implementasi internal pemanggilan soket TCP/IP pada abstraksi paket `parallel::makeCluster()`.

### Saya harus bisa melakukan:
- [ ] Menjalankan visual profiling makro menggunakan `profvis` untuk mendeteksi bottleneck fungsi dan lokasi lonjakan alokasi memori (*memory churn*).
- [ ] Melakukan mikro-benchmarking presisi tinggi bebas bias menggunakan paket `bench` untuk mengevaluasi waktu eksekusi serta frekuensi alokasi Garbage Collection (GC levels 0/1/2).
- [ ] Menulis modul C++ berkinerja tinggi menggunakan `Rcpp` dan `RcppArmadillo` yang dapat diekspor langsung ke R environment.
- [ ] Menerapkan paralelisasi loop C++ secara aman menggunakan OpenMP tanpa melanggar batasan single-thread R Core API.
- [ ] Mengonfigurasi variabel lingkungan eksekusi paralel (seperti `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, dan `MKL_NUM_THREADS`) untuk meniadakan saturasi context-switching pada cluster HPC.
- [ ] Memeriksa dan mendebug *memory leak*, *undefined behavior*, dan *buffer overflow* pada ekstensi C++/Rcpp menggunakan compiler flags AddressSanitizer (`-fsanitize=address`) dan Valgrind.
- [ ] Merancang arsitektur pipeline pemrosesan data masif paralel yang mengeliminasi overhead serialisasi IPC menggunakan pemetaan memori (*memory-mapped files*) atau *shared memory primitives*.