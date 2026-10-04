# BAB 10: Quiz, Challenge, & Knowledge Check
**Package Engineering, API Services, & Kontainerisasi Produksi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Namespace Isolation & Dynamic Symbol Resolution:**  
   Jelaskan perbedaan mendasar antara mekanisme pencarian simbol di *Global Environment* (`.GlobalEnv`) versus namespace internal sebuah R package. Mengapa penggunaan fungsi seperti `export()` dan `importFrom()` pada berkas `NAMESPACE` secara eksplisit menjadi syarat mutlak untuk mencegah *namespace pollution* dan *name masking collision* pada *production-grade application*?

2. **Event Loop & Concurrency Model pada Plumber:**  
   R secara inheren merupakan *single-threaded runtime*. Jelaskan bagaimana *framework* seperti `plumber` menangani HTTP request lifecycle via `httpuv`. Apa implikasi struktural dari sifat *single-threaded* ini terhadap eksekusi komputasi analitik intensif (misal: *matrix inversion* atau *tree traversal*), dan mengapa satu *long-running request* dapat mendegradasi latensi seluruh *client pipeline*?

3. **Deterministik State Management via `renv`:**  
   Bagaimana arsitektur *content-addressable cache* dan deklarasi metadata pada `renv.lock` menjamin *hermetic builds* pada R runtime? Bandingkan pendekatan isolasi dependensi ini dengan mekanisme *virtual environment* pada Python (`venv`/`poetry`), khususnya terkait cara R menangani kompilasi dependensi native C/C++/Fortran.

4. **Multi-Stage Build & Attack Surface Reduction:**  
   Dalam konteks kontainerisasi microservice R, jelaskan peran *Multi-Stage Docker Build*. Komponen sistem apa saja (misalnya compiler toolchain seperti `gcc`, `gfortran`, *header files* `-dev`) yang harus dieliminasi dari *build stage* ke *runtime stage*, dan bagaimana hal tersebut berdampak pada ukuran *image layer* serta postur keamanan kontainer (CVE mitigation)?

5. **Interface Boundary: Rcpp vs R C-API (`.Call`):**  
   Saat membangun internal engine performa tinggi di dalam package R, arsitek dapat memilih antara R C-API native (`.Call`) dan abstractions berbasis `Rcpp`. Jelaskan perbedaan *cost of marshaling*, penanganan *garbage collection allocation tracing* (PROTECT/UNPROTECT), serta overhead abstraksi C++ object wrapper terhadap latensi level mikrodetik.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Diagnostik Memory Leak & Invisible Environments:**  
   Sebuah microservice `plumber` mengalami peningkatan *Resident Set Size* (RSS) secara monotonik hingga memicu *Out-Of-Memory (OOM) Killer* oleh kernel Linux setelah 72 jam berjalan di lingkungan produksi. Setelah diteliti, tidak ada variabel global baru yang dibuat. Bagaimana Anda memvalidasi apakah kebocoran memori ini berasal dari *uncollected environments* pada *function closures*, alokasi native C++ via `Rcpp` yang lolos dari *R Garbage Collector*, atau fragmentasi memori pada allocator `glibc`?

2. **Scaling Concurrency: Multi-Worker Preforking vs Asynchronous I/O:**  
   Ketika mengoperasikan R API pada beban konkurensi tinggi, developer dihadapkan pada dua pilihan: menggunakan eksekusi asinkron (`promises` + `later` / `future`) di dalam satu process, atau menerapkan *pre-forked process worker model* di belakang reverse proxy (seperti Gunicorn/Nginx memanggil multiple R instances via socket). Analisis skenario di mana model asinkron internal R tetap gagal menjaga *throughput*, dan jelaskan mengapa *process-based isolation* menjadi keharusan arsitektur untuk CPU-bound services.

3. **Binary Compatibility & Dynamic Linking Trilemma:**  
   Anda membangun container R berbasis Alpine Linux (`musl libc`) untuk meminimalkan ukuran image, namun package analitik kustom Anda yang mengompilasi library C/Fortran eksternal (misal: OpenBLAS, LAPACK) mengalami *segmentation fault* acak saat runtime. Jelaskan akar permasalahan ABI (Application Binary Interface) ini dan bandingkan konsekuensinya jika beralih ke *glibc-based minimal image* seperti Debian-slim (`rocker/r-ver`).

4. **Health Check Anti-Pattern & Thread Starvation:**  
   Sebuah *Liveness/Readiness Probe* Kubernetes dikonfigurasi untuk memanggil endpoint `/healthz` pada microservice `plumber`. Namun, saat microservice menerima lonjakan kalkulasi model yang berat, Kubernetes secara keliru menganggap pod mati dan melakukan restart berulang (*CrashLoopBackOff*). Mengapa arsitektur single-threaded R menyebabkan false-positive failure ini, dan bagaimana mendesain mekanisme health-check decoupling yang akurat tanpa memblokir thread eksekusi utama?

5. **Cold-Start Latency & Package Lazy-Loading Optimization:**  
   Bagaimana mekanisme database `LazyData` dan byte-compiled code (`LazyLoad: true`) di dalam R package bekerja di level sistem operasi? Bagaimana struktur ini mempengaruhi efisiensi penggunaan shared memory (*Copy-on-Write*) saat menggunakan process forking, dan langkah profiling apa yang harus dilakukan untuk menekan cold-start latency container dari orde puluhan detik ke sub-detik?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Catastrophic Latency Spikes pada Core ML Scoring API
* **Konteks:** Sebuah microservice scoring credit risk berbasis package R kustom dan `plumber` di-deploy di Kubernetes dengan autoscaler (HPA) berdasarkan CPU Utilization (target 70%). API mengekspos endpoint `/v1/score` yang menerima JSON payload, melakukan transformasi fitur via `data.table`, dan inferensi model `xgboost`.
* **Insiden:** Saat terjadi event flash sale, request rate melonjak dari 50 RPS ke 800 RPS. Latensi p99 meroket dari 45ms ke 12.000ms. CPU utilization pod tercatat melompat ke 98%, tetapi HPA lambat melakukan scale out. Pod mengalami cascade failure dan request timeout massal. Analisis awal menunjukkan parsing payload JSON besar via library default R memakan waktu signifikan, dan GC (Garbage Collection) cycle terpicu ratusan kali per detik.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *architectural bottleneck* utama pada parsing payload JSON dan alokasi memori internal R pada *high-throughput scenario* ini.
  2. Rancang strategi perbaikan end-to-end: mulai dari optimasi parsing I/O, penyesuaian GC tuning (`R_GC_MEM_GROW`), segregasi model worker, hingga mitigasi cold-start pada HPA Kubernetes.

### Skenario B: Race Condition dan State Leakage pada Stateful Calculation Engine
* **Konteks:** Tim aktuaria mengonversi package R analitik internal menjadi API multi-tenant menggunakan `plumber`. Untuk mempercepat performa agregasi multi-dimensi, developer mengimplementasikan caching layer sederhana menggunakan environment tingkat package (`pkg_env <- new.env(parent = emptyenv())`).
* **Insiden:** Laporan audit sistem mendeteksi anomali: Tenant X menerima hasil estimasi margin risiko yang memuat data histori dari Tenant Y. Investigasi menunjukkan bahwa saat dua concurrent request masuk dengan profil payload berbeda, request kedua membaca *intermediate state* yang sedang ditulis oleh request pertama. Selain itu, penggunaan memori container tumbuh tak terbatas seiring waktu.
* **Pertanyaan Diagnostik:**
  1. Jelaskan bagaimana *lexical scoping* dan *package namespace encapsulation* menyebabkan state leakage ini ketika R script dipaparkan sebagai stateless HTTP server.
  2. Rekonstruksi arsitektur state management tersebut agar strictly *stateless*, thread-safe, dan implementasikan mekanisme garbage collection/cleanup otomatis segera setelah lifecycle HTTP request berakhir.

### Skenario C: Migrasi Monolithic Legacy R Script ke Cloud-Native Microservices
* **Konteks:** Perusahaan logistik global memiliki script R monolitik (5.000 baris) yang menjalankan peramalan rute (menggunakan dependensi spasial native seperti `sf`, `gdal`, `geos`) yang dipicu oleh cron job batch setiap jam. Script ini kerap gagal di server produksi karena konflik versi dependensi library C sistem dan memory exhaustion. CTO menuntut script ini dipecah menjadi decoupled API service berstandar enterprise yang dapat melayani kalkulasi on-demand via HTTP.
* **Tantangan Arsitektur:** Dependensi spasial (`GDAL/GEOS/PROJ`) terkenal sulit dikompilasi, rentan *dependency hell*, dan menghasilkan image Docker berukuran sangat besar (>2.5 GB) yang memperlambat deployment CI/CD.
* **Pertanyaan Diagnostik:**
  1. Rancang arsitektur paket R modular baru yang memisahkan pure computational core, system-level spatial bindings, dan presentation/API layer.
  2. Buat blue-print strategi CI/CD pipeline dan Docker containerization (multi-stage) yang mampu memangkas ukuran image secara drastis, mengunci dependensi C/R secara deterministik, serta memisahkan *heavy long-running spatial calculation* dari *synchronous API gateway*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade High-Throughput Inference Service Packaging and Containerization

#### Problem Statement
Sebuah model regresi regularisasi kustom dan algoritma optimasi portfolio portabel perlu didistribusikan ke cluster Kubernetes perbankan. Solusi saat ini berupa folder tak berstruktur berisi script `.R` yang di-load manual menggunakan `source()`, tanpa standardisasi dependensi, tanpa automated testing, dan dijalankan langsung di host machine tanpa isolasi runtime.

#### Requirements
1. **Package Engineering Standard:**
   - Bangun struktur R package resmi (`portfolio.engine`) yang mematuhi validasi `R CMD check --as-cran` tanpa error, tanpa warning, dan tanpa notes non-trivial.
   - Pisahkan algoritma kalkulasi intensif ke dalam C++ via `Rcpp` untuk optimasi matrix multiplications.
   - Sediakan dokumentasi fungsi berbasis `roxygen2` dan unit testing komprehensif menggunakan `testthat` (coverage minimal 85%).
2. **Deterministic Dependency Isolation:**
   - Inisialisasi dan kunci seluruh dependensi paket menggunakan `renv` (memastikan zero dynamic unpinned dependency resolution).
3. **API Implementation (`plumber`):**
   - Bangun REST API interface yang mengekspos endpoint `/api/v1/optimize` (POST) dan `/livez` (GET).
   - Implementasikan *input validation schema* yang ketat (menolak missing values, malformed JSON, data out-of-bounds) sebelum data masuk ke execution engine.
   - Logika eksekusi tidak boleh menyimpan state apa pun di level package environment.
   - Pasang structural error handling dengan HTTP status code yang representatif (400, 422, 500) dengan JSON error payload standar RFC 7807.
4. **Hardened Multi-Stage Docker Container:**
   - **Stage 1 (Builder):** Berbasis base image Linux stabil, memuat seluruh toolchain kompilasi native (`build-essential`, `gfortran`, headers). Tahap ini melakukan `renv::restore()` dan `R CMD INSTALL`.
   - **Stage 2 (Runtime):** Image minimal (distroless atau slim-based). Salin hanya runtime R libraries, compiled binaries, dan assets yang diperlukan.
   - Container harus berjalan menggunakan non-root user (`appuser` UID 10001).
   - Ukuran final image harus berada di bawah ambang batas rasional (< 450 MB).

#### Constraints
* Dilarang menggunakan `.GlobalEnv` untuk menyimpan data atau konfigurasi.
* Hindari library bloat: Jangan memasukkan framework besar seperti `tidyverse` utuh; gunakan dependensi terarah (`data.table`, `jsonlite`, atau specific packages).
* Seluruh rahasia/konfigurasi runtime harus dibaca via POSIX-compliant Environment Variables.

#### Expected Output
1. Direktori R Package dengan struktur standar (`DESCRIPTION`, `NAMESPACE`, `R/`, `src/`, `tests/`).
2. Script `entrypoint.R` yang menginisiasi Plumber router programmatically.
3. Berkas `Dockerfile` (multi-stage) dan `.dockerignore` yang optimal.
4. Output log deterministik dari `R CMD check` dan unit testing yang berhasil (*pass* 100%).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan antara Search Path R, Namespace Environment, dan Imports Environment dalam siklus resolusi fungsi.
- [ ] Mekanisme parsing dan serialisasi JSON pada R serta implikasi performa alokasi vektor terhadap R Garbage Collector.
- [ ] Model komputasi Plumber di atas `httpuv`, interaksi single-threaded event loop, dan strategi mitigasi blocking operations.
- [ ] Cara kerja `renv` dalam mengisolasi libraries via hardlinks dan lockfile schema (`renv.lock`).
- [ ] Anatomi dynamic shared object (`.so`) yang dihasilkan dari kompilasi C/C++ via `Rcpp` dan cara R mengikat simbol native tersebut (`useDynLib`).
- [ ] Prinsip kerja Multi-stage container builds untuk R (eliminasi build-time compiler dependencies pada runtime image).
- [ ] Risiko keamanan menjalankan container R sebagai `root` user dan cara mitigasi hak akses file-system di lingkungan kontainer.

### Saya tidak perlu menghafal:
- [ ] Seluruh macro flag alokasi memory low-level R C-API (seperti `PROTECT_WITH_INDEX`).
- [ ] Flag baris perintah compiler manual (`gcc`/`gfortran`) untuk setiap dependensi arsitektur OS; serahkan pada `R CMD config` dan `Makevars`.
- [ ] Setiap baris syntax parameter konfigurasi server Swagger internal pada Plumber.
- [ ] Format spesifik per-byte dari binary serialization `.rds` R.

### Saya harus bisa melakukan:
- [ ] Mengonversi sekumpulan script procedural R menjadi package formal yang lolos `R CMD check` tanpa dependensi sirkular.
- [ ] Menulis modul C++ menggunakan `Rcpp` untuk mengeksekusi operasi loop-heavy dan mengintegrasikannya secara native ke dalam R package.
- [ ] Mengonfigurasi dan mengunci status ekosistem paket R menggunakan `renv::init()` dan `renv::snapshot()`.
- [ ] Membangun REST API berbasis Plumber dengan error handling, parameter validation, dan structured logging yang aman untuk observability tools.
- [ ] Menulis Dockerfile multi-stage untuk R application yang menghasilkan artifact berukuran minimal, aman, dan siap pakai di cluster Kubernetes.
- [ ] Mendiagnosis penyebab memory leak dan CPU saturation pada container R menggunakan Linux native profiling tools (`perf`, `top`, valgrind, atau custom memory tracing).