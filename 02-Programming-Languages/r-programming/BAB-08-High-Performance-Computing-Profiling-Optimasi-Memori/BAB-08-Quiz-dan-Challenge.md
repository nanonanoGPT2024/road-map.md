# BAB 08: Quiz, Challenge, & Knowledge Check
**High-Performance Computing, Profiling, & Optimasi Memori**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Copy-on-Write (CoW) dan Evolusi Reference Counting
Jelaskan secara mendalam bagaimana semantik *Copy-on-Write* (CoW) beroperasi pada R modern (R $\ge$ 3.5.0 dengan sistem `REFCNT`) dibandingkan mekanisme legacy `NAMED`. Mengapa modifikasi elemen tunggal pada satu kolom di dalam `data.frame` standar berukuran 10 GB dapat memicu duplikasi memori parsial yang signifikan (*shallow copy* vs *deep copy*), dan pada kondisi apa *modification in-place* benar-benar dijamin oleh R engine?

### Soal 1.2: Arsitektur ALTREP (Alternative Representations)
Jelaskan prinsip kerja arsitektur ALTREP yang diperkenalkan pada R 3.5.0. Analisis bagaimana ALTREP mencegah *eager materialization* pada alokasi vektor masif seperti `1:1e9` atau pembacaan file via paket modern (`vroom`, `arrow`). Apa konsekuensi performa dan konsumsi memori ketika vektor ALTREP tanpa sengaja diteruskan ke pustaka C/C++ eksternal legacy melalui SEXP pointer konvensional?

### Soal 1.3: Profiling Deterministik vs Statistical Profiling
Bandingkan arsitektur kerja antara *deterministic tracing* (seperti `Rprofmem`) dan *statistical/sampling profiling* (seperti `Rprof` dan antarmuka `profvis`). Mengapa *sampling profiler* dengan interval waktu standar (misal: 10ms atau 20ms) dapat memberikan bias sistematis terhadap fungsi komputasi mikro, dan bagaimana interaksi antara *Bytecode Compiler* (JIT) R dengan profiling call-stack dapat mengaburkan visibilitas bottleneck sebenarnya?

### Soal 1.4: Vektorisasi Tingkat Rendah dan Pipa Eksekusi CPU
Secara fundamental, "vektorisasi" dalam R sering disalahpahami sekadar mengganti *for-loop* dengan keluarga fungsi `*apply`. Jelaskan perbedaan mekanistis antara:
1. Vektorisasi tingkat bahasa (eksekusi loop di level C internal R via primitive functions).
2. Vektorisasi tingkat perangkat keras (*Single Instruction, Multiple Data* / SIMD seperti AVX-512).
Mengapa operasi loop sekuensial yang ditulis dengan `for` pada R modern terkadang dapat mendekati performa `sapply`, namun tetap kalah jauh dari operasi berbasis array primitif (`+`, `*`, `colSums`)?

### Soal 1.5: Siklus Hidup Alokasi Memori: NCELLS, VCELLS, dan GC Generasional
Jelaskan arsitektur memori R yang terbagi atas `NCELLS` (*cons cells*) dan `VCELLS` (*vector cells*). Bagaimana *tri-generational mark-and-sweep garbage collector* (Gen 0, 1, dan 2) pada R menentukan kapan pembersihan memori harus dieksekusi? Mengapa log eksekusi yang menunjukkan pemanggilan `gc()` secara berulang (*GC thrashing*) merupakan indikasi adanya inefisiensi alokasi sementara (*ephemeral allocations*) dan bukan solusi untuk membebaskan memori?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Interoperabilitas Memori Rcpp: Zero-Copy vs Deep-Copy
Perhatikan cuplikan deklarasi C++ via Rcpp berikut:
```cpp
// Implementasi A
NumericVector process_A(NumericVector x) {
    x[0] = 999.0;
    return x;
}

// Implementasi B
NumericVector process_B(const NumericVector& x) {
    NumericVector y = clone(x);
    y[0] = 999.0;
    return y;
}
```
Jelaskan implikasi arsitektur dari kedua implementasi tersebut terhadap lingkungan memori R pemanggil. Bagaimana `process_A` dapat melanggar invarian fungsionalitas murni R (*side-effects* tak terduga)? Bagaimana Anda memanfaatkan struktur data seperti `Rcpp::NumericVector` dan `arma::mat` (RcppArmadillo) dengan argumen `copy_aux_mem = false` untuk mencapai komputasi matriks *zero-copy* tanpa memicu *segmentation fault* saat GC R dijalankan?

### Soal 2.2: Fenomena CoW Invalidation pada Forking Multi-Core (`parallel::mclapply`)
Di lingkungan POSIX/Linux, fungsi `parallel::mclapply` mengandalkan *system call* `fork()` untuk menduplikasi *parent process* ke *worker processes* dengan ekspektasi konsumsi memori *zero-overhead* melalui CoW di level OS pages. Namun, dalam banyak skenario produksi pemrosesan data besar di R, memori server langsung membengkak drastis (*OOM crash*) sesaat setelah *worker* mulai berjalan. Bedah mengapa *Garbage Collector* R dan manipulasi *reference count* internal secara inheren memicu invalidasi CoW pada OS page table, dan bagaimana strategi mitigasi arsitekturalnya!

### Soal 2.3: Memory Fragmentation dan Keterbatasan Memory Allocator
Sebuah batch job R berjalan selama 48 jam, memproses jutaan file teks kecil. Profiling menunjukkan bahwa penggunaan memori aktif (objek yang hidup di sesi R via `object.size`) hanya 2 GB, namun metrik *Resident Set Size* (RSS) pada sistem operasi (via `top` atau cgroups) menunjukkan angka 45 GB dan terus meningkat hingga dihentikan oleh Linux OOM Killer. 
1. Mengapa fungsi `base::gc()` tidak mampu menurunkan nilai RSS tersebut ke sistem operasi?
2. Bagaimana mekanisme interaksi antara *glibc malloc arena fragmentation* dan alokator memori internal R?
3. Langkah konfigurasi OS atau *alternative allocator* (seperti `jemalloc` / `mimalloc`) apa yang harus diterapkan untuk menstabilkan konsumsi RSS tersebut?

### Soal 2.4: State Collision dan Desinkronisasi PRNG Paralel
Saat mendistribusikan simulasi Monte Carlo berbasis R ke 64 *cores* paralel menggunakan PSOCK cluster (`parallel::makeCluster`), eksekusi fungsi `set.seed(12345)` di sesi utama sebelum delegasi komputasi sering kali menghasilkan artefak kritis di mana setiap *worker* memproduksi urutan angka acak yang identik, atau terjadi korelasi silang (*cross-stream correlation*).
Jelaskan kelemahan algoritma *Mersenne-Twister* standar R dalam komputasi terdistribusi dan bedah mekanisme internal implementasi *L'Ecuyer-CMRG* (`RNGkind("L'Ecuyer-CMRG")`) dalam mengisolasi state space via rekursi matriks transisi 6x6.

### Soal 2.5: Thread Safety Violation pada OpenMP dalam Shared Memory Rcpp
Ketika mengimplementasikan paralelisasi multi-threading menggunakan OpenMP di dalam kode C++ yang dikompilasi via Rcpp:
```cpp
#pragma omp parallel for
for(int i = 0; i < n; ++i) {
    // Komputasi numerik intensif
    // ...
    if(kondisi_error) {
        Rcpp::Rcout << "Error pada iterasi " << i << std::endl;
        Rcpp::checkUserInterrupt();
    }
}
```
Identifikasi dua pelanggaran fatal *thread-safety* pada kode di atas terkait interaksi dengan R API. Mengapa pemanggilan fungsi R Core API (termasuk I/O dan alokasi memori R SEXP) dari dalam *worker thread* OpenMP di luar *master thread* dapat memicu *race condition*, korupsi stack pointer R, atau *hard crash* fatal pada proses R?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM Killer pada Pipeline Data Skala 120 GB
*Konteks Arsitektur:* 
Sebuah sistem pipeline analitik harian memproses dataset transaksi perbankan bulanan berukuran total 120 GB (format CSV mentah). Pipeline berjalan pada instance cloud AWS `r5.4xlarge` (16 vCPU, 128 GB RAM) menggunakan R 4.3. Pipeline gagal setiap malam dengan status *Exit Code 137* (Killed by Linux OOM Killer).

*Log Investigasi Awal:*
```r
# Potongan kode pipeline legacy
library(readr)
library(dplyr)

raw_data <- list.files("/data/daily/", full.names = TRUE) %>%
    lapply(read_csv) %>%
    bind_rows()

processed <- raw_data %>%
    filter(status == "SETTLED") %>%
    mutate(fee_usd = amount * 0.015) %>%
    group_by(merchant_id) %>%
    summarise(total_volume = sum(amount), total_fee = sum(fee_usd))
```

*Pertanyaan Diagnostik:*
1. Lakukan audit menyeluruh terhadap titik-titik alokasi memori yang menyebabkan pelipatgandaan jejak memori (*memory footprint multiplier*) hingga melebihi batas 128 GB RAM fisik.
2. Desain ulang arsitektur pemrosesan data tersebut menggunakan kombinasi pendekatan *chunked processing* / *streaming*, ALTREP, atau pustaka columnar out-of-core (`arrow` dataset engine atau `duckdb`) tanpa harus menaikkan skala hardware (vertically scale-up). Sertakan arsitektur pipeline baru dalam kode pseudocode/R idiomatis berkinerja tinggi.

---

### Skenario B: Race Condition dan Deadlock pada High-Throughput Scraper Engine
*Konteks Arsitektur:* 
Sebuah engine *market surveillance* mengekstraksi data *order book* dari 200 bursa kripto secara simultan. Arsitektur dibangun menggunakan arsitektur paralel `future` + `promises` di atas cluster PSOCK lokal. Tim menemukan bahwa secara berkala beberapa thread *worker* mengalami *deadlock* total (CPU 0% namun proses tidak pernah selesai), dan file log agregat harian mengalami korupsi data (*interleaved incomplete text writes*).

*Potongan Kode Masalah:*
```r
library(future)
plan(multisession, workers = 16)

results <- lapply(exchange_urls, function(url) {
    future({
        data <- fetch_order_book(url) # Melakukan HTTP request dengan libcurl
        # Menulis metrik langsung ke file sentral
        cat(paste(Sys.time(), url, length(data), "\n"), 
            file = "/var/log/surveillance_metrics.log", append = TRUE)
        return(compute_spread(data))
    })
})
```

*Pertanyaan Diagnostik:*
1. Mengapa operasi penulisan file menggunakan `cat(..., append = TRUE)` secara paralel di multi-process environment memicu korupsi data (analisis dari perspektif *POSIX file locking* dan *unbuffered write contention*)?
2. Apa penyebab struktural worker mengalami *deadlock* atau *infinite hang* pada fungsi pemanggilan jaringan di dalam worker PSOCK, dan bagaimana mengkonfigurasi socket timeout serta arsitektur IPC (*Inter-Process Communication*) yang deterministik?
3. Rancang pola arsitektur producer-consumer yang aman (*thread/process-safe logging*) untuk skenario ini tanpa membebani thread komputasi analitik.

---

### Skenario C: Trade-off Arsitektur Sistem: In-Memory Distributed Cluster vs Memory-Mapped Storage
*Konteks Arsitektur:* 
Sebuah tim kuantitatif sedang membangun sistem backtesting portofolio berfrekuensi tinggi (*high-frequency backtester*). Volume data fitur teknikal matriks berukuran dimensi $5.000.000 \times 2.000$ (float64, estimasi ukuran mentah: ~80 GB). Algoritma backtesting mengeksekusi operasi optimasi numerik berulang (iterasi konvergensi non-linear) di mana baris dan kolom diakses secara acak (*random non-sequential access*).

Dua arsitek senior berdebat tentang opsi arsitektur:
* **Arsitek 1:** Menyarankan mendistribusikan matriks tersebut menggunakan klaster memory-distributed via `clustermq` atau `future` di 4 node terpisah (masing-masing 32 GB RAM) via IPC TCP/IP.
* **Arsitek 2:** Menyarankan menggunakan single-node machine (128 GB RAM) dengan *Memory-Mapped Files* melalui format biner berbasis disk (seperti paket `bigstatsr` / `bigmemory` atau format `fst`).

*Pertanyaan Diagnostik:*
1. Bedah trade-off performa latensi I/O antara transfer chunk matriks melalui *TCP/IP Network Stack serialization/deserialization* (Arsitek 1) dibandingkan dengan *Page Fault handling* pada OS Virtual Memory Manager saat melakukan *random memory-mapped access* pada disk NVMe (Arsitek 2).
2. Dari sudut pandang cache hierarchy (L1/L2/L3 cache misses), bagaimana pola tata letak memori (*column-major* milik R/Fortran vs *row-major* milik C) mempengaruhi waktu eksekusi jika matriks 80 GB tersebut diakses secara baris demi baris dalam algoritma optimasi?
3. Berikan rekomendasi arsitektur final yang optimal secara biaya dan waktu eksekusi, serta jelaskan justifikasi teknisnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Rolling Window Estimator Engine via Rcpp, OpenMP, & Zero-Copy Architecture

#### Problem Statement
Dalam analisis kuantitatif keuangan, kalkulasi estimasi parameter statistik berbasis *rolling-window* multi-variat (misal: *Rolling Weighted Exponential Covariance & Shrinkage*) pada data *tick-by-tick* sering menjadi penghambat utama (*bottleneck*). Implementasi standar menggunakan kombinasi loop `lapply`/`zoo::rollapply` pada R membutuhkan waktu berjam-jam untuk dataset 50 juta observasi dan sering kali menghabiskan alokasi RAM karena pembuatan objek perantara (*intermediate allocations*).

Anda ditugaskan merancang *enterprise-grade computational core function* berbasis Rcpp dan OpenMP yang mampu memproses komputasi matriks berkecepatan tinggi dengan efisiensi memori mutlak.

#### Requirements
1. **Core Processing Engine (C++ via Rcpp / RcppArmadillo):**
   * Buat fungsi `fast_rolling_cov(NumericMatrix data, int window_size, double lambda)` menggunakan Rcpp.
   * Fungsi harus menghitung kovarians berbobot eksponensial (*Exponentially Weighted Covariance*) untuk setiap jendela geser sepanjang waktu.
   * Harus menggunakan paralelisasi OpenMP pada komputasi jendela geser untuk memaksimalkan seluruh *core* CPU yang tersedia.
   * Wajib menerapkan prinsip *zero-copy*: Jangan melakukan duplikasi terhadap matriks input `data`. Gunakan pointer memori atau mapping *wrapper* yang memetakan langsung struktur data R ke C++.

2. **Memory & Thread Safety Guard:**
   * Alokasi matriks penampung hasil (*3D array* atau struktur *flat 2D matrix*) harus diinisialisasi sekali saja sejak awal (*pre-allocated memory*).
   * Dilarang keras memanggil fungsi alokasi R SEXP, print to console, atau GC hooks di dalam area loop paralel OpenMP (`#pragma omp parallel for`).
   * Gunakan penanganan thread-local memory buffer untuk menghindari *false sharing* antar L1 cache-lines prosesor.

3. **Benchmarking Harness & Validation:**
   * Bangun harness validasi menggunakan paket `bench::mark()` yang membandingkan:
     a. Implementasi naif di Base R (menggunakan `lapply` / `sapply`).
     b. Implementasi paket standar (misal: antarmuka fungsi dari paket `roll` atau `zoo`).
     c. Engine C++ Rcpp paralel yang Anda bangun.
   * Tunjukkan validasi numerik presisi tinggi: Selisih absolut maksimum (*tolerance*) antara output engine Anda dengan hasil Base R harus berada di bawah threshold $10^{-9}$ (menggunakan `all.equal`).

#### Constraints
* **Kompilasi:** Harus dapat dikompilasi secara portabel menggunakan `sourceCpp` dengan flags `-O3 -fopenmp`.
* **Karakteristik Skala:** Matriks uji coba: $1.000.000 \text{ baris} \times 10 \text{ kolom}$ (tipe `double`), `window_size = 500`.
* **Batas Memori:** Eksekusi komputasi engine C++ tidak boleh menaikkan konsumsi RAM proses lebih dari ukuran matriks output yang dialokasikan (Total memory overhead < 5% dari payload ukuran input + output).
* **Batas Waktu:** Implementasi baru harus mencapai target performa minimal **15x lebih cepat** dibandingkan implementasi vektorisasi native R terbaik.

#### Expected Output
1. File implementasi C++ yang bersih dan terdokumentasi rapi (dilengkapi *compiler directives* OpenMP).
2. Script driver R yang mencakup:
   * Pembuatan dataset sintetis (menggunakan stream RNG terisolasi yang stabil).
   * Verifikasi deterministik numerik.
   * Profiling alokasi memori menggunakan `bench::mark(..., check = TRUE, memory = TRUE)`.
   * Ekstraksi metrik efisiensi CPU (utilisasi core, runtime wall-clock vs CPU time, memory garbage collection count).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme transitif alokasi Copy-on-Write (CoW) dan kondisi mutasi memori in-place (`NAMED` vs `REFCNT`).
- [ ] Arsitektur internal ALTREP dan teknik menghindari eager materialization pada dataset masif.
- [ ] Perbedaan fundamental antara statistical profiler (`Rprof`, `profvis`) dan deterministic event tracer (`Rprofmem`).
- [ ] Hierarki alokasi memori R: batas antara `VCELLS` (heap numerik) dan `NCELLS` (pointer nodes), serta pemicu pembersihan tiga generasi Garbage Collector.
- [ ] Bahaya forking model (`mclapply`) pada sistem operasi berbasis POSIX akibat CoW invalidation oleh GC dan alokasi mutasi halaman.
- [ ] Bahaya memanggil R API / SEXP allocation dari thread OpenMP non-utama (Thread Safety Violation).
- [ ] Batasan algoritma pseudo-random number generator (PRNG) standar pada sistem konkurensi paralel dan formulasi mitigasi L'Ecuyer-CMRG.
- [ ] Karakteristik akses memori *Column-Major* vs *Row-Major* dan korelasinya terhadap fenomena CPU *Cache Miss* pada data biner besar.

### Saya tidak perlu menghafal:
- [ ] Sintaks internal makro C tingkat rendah R Core (seperti `PROTECT`, `UNPROTECT`, `DATAPTR`) di luar konteks API modern Rcpp.
- [ ] Nilai byte heksadesimal representasi header objek internal SEXP (misal bit-flags header `sxpinfo`).
- [ ] Formula matematis koefisien transisi internal matriks L'Ecuyer-CMRG secara mendetail.
- [ ] Setiap parameter tuning baris perintah kompilator GCC/Clang (`-fopt-info`, `-march=native`), cukup memahami konsep flag optimasi level dasar `-O2` dan `-O3`.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi bottleneck performa dan jejak alokasi memori menggunakan `profvis` dan `bench::mark()`.
- [ ] Mengeliminasi overhead memori tersembunyi (*shallow copy triggers*) pada pipeline manipulasi data tabular.
- [ ] Mengonversi loop komputasi numerik intensif R menjadi subrutin performa tinggi C++ via Rcpp dengan zero-copy mapping.
- [ ] Mengimplementasikan paralelisasi aman multi-threading OpenMP di C++ atau multi-processing terdistribusi di R tanpa race conditions dan memory deadlocks.
- [ ] Mendiagnosis insiden kebocoran memori (memory leaks) dan fragmentasi heap OS pada proses R jangka panjang menggunakan tools observabilitas Linux (`cgroups`, `smaps`, `perf`).
- [ ] Menentukan arsitektur penyimpanan dan manipulasi data yang tepat antara In-Memory Data Frames, Memory-Mapped Disk Files, dan Columnar Embedded Databases (DuckDB/Arrow) berdasarkan profil akses I/O.