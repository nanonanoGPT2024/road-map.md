# BAB 10: Quiz, Challenge, & Knowledge Check
**Production Deployment, API, & Interactive Dashboards**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Reaktivitas Shiny dan Siklus Hidup Objek (Reactive Graph Lifecycle):**
   Jelaskan bagaimana Shiny membangun dan mengevaluasi *Directed Acyclic Graph* (DAG) untuk menentukan dependensi antar objek reaktif (`reactive()`, `observe()`, dan `render*()`). Bagaimana mekanisme *invalidation* bekerja ketika nilai input berubah, dan mengapa modifikasi objek di luar konteks reaktif (reaktivitas tanpa dependensi eksplisit) dapat merusak kestabilan aplikasi di lingkungan multi-user?

2. **Arsitektur Stateless Plumber vs Stateful Shiny:**
   Bandingkan model konkurensi dan manajemen state antara REST API berbasis `plumber` dengan dashboard interaktif berbasis `shiny`. Bagaimana perbedaan fundamental ini memengaruhi strategi deployment, horizontal scaling (autoscaling), dan *session persistence* (sticky sessions) pada cluster Kubernetes?

3. **Optimalisasi Layering Docker untuk Dependency R:**
   Kompilasi package R dari source (terutama yang membutuhkan *system libraries* seperti `libxml2`, `libgdal`, atau dependensi C++/Fortran) membutuhkan waktu build yang signifikan. Rancang struktur `Dockerfile` multi-stage yang memisahkan instalasi dependensi OS, *dependency caching* menggunakan `renv`, dan transfer artefak aplikasi untuk meminimalkan waktu CI/CD build time serta ukuran image akhir.

4. **Isolasi Environment dan Namespace Collision:**
   Dalam Shiny Server atau Plumber yang melayani banyak koneksi masuk secara simultan, jelaskan bahaya penggunaan assignment global (`<<-` atau `assign()` ke `.GlobalEnv`). Apa implikasi strukturalnya terhadap *data leakage* antar pengguna (cross-user data contamination) dan bagaimana arsitektur modular (`shiny::moduleServer`) memitigasi risiko namespace collision?

5. **Decoupling Compute vs Presentation Layer:**
   Mengapa menjalankan komputasi analitik berat (misalnya pelatihan model machine learning atau integrasi data terdistribusi) langsung di dalam thread UI Shiny dianggap sebagai *anti-pattern* pada skala enterprise? Jelaskan arsitektur decoupling yang memisahkan layer presentasi (front-end dashboard) dengan layer pemrosesan data (backend microservices/job queues).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Single-Threaded R dan Asynchronous Execution (`promises` & `future`):**
   R secara native bersifat single-threaded. Bedah bagaimana eksekusi fungsi intensif I/O atau komputasi berat di dalam endpoint Plumber memblokir *event loop* HTTP server (httpuv). Tunjukkan bagaimana implementasi kombinasi package `promises` dan `future` (dengan backend `multisession` atau `cluster`) dapat menjaga endpoint tetap non-blocking untuk *request* lain. Sertakan edge-case terkait *overhead fork/socket* dan transfer serialisasi data antar proses worker.

2. **Diagnosa dan Mitigasi Memory Leaks pada Long-Running Processes:**
   Aplikasi Shiny atau API Plumber yang beroperasi terus-menerus sering kali mengalami peningkatan konsumsi RAM (memory creep) hingga memicu Kubernetes OOM-Killed (*Out of Memory*). Bagaimana Anda mendiagnosis apakah kebocoran tersebut berasal dari referensi *closure environment* yang tertahan, alokasi memori internal R, atau memory leak pada level library C/C++ yang di-*wrap* oleh R (misalnya via `Rcpp`)? Jelaskan langkah audit menggunakan profiler memori (`profvis` atau `bench::mark`).

3. **Plumber Serialization Pipeline dan Custom Serializer Overhead:**
   Jelaskan tahapan yang dilalui objek R mulai dari *return value* sebuah route hingga menjadi HTTP response body. Jika API Anda harus mengirimkan GeoJSON atau data frame berukuran puluhan megabyte, jelaskan batasan serializer default `jsonlite` dan rancang mekanisme custom serializer atau streaming response untuk menekan alokasi RAM transien serta latensi serialisasi.

4. **Graceful Shutdown dan Health Checks pada Orchestration Platform:**
   Ketika Kubernetes Pod yang menjalankan Plumber menerima sinyal `SIGTERM` saat proses rolling update, bagaimana perilaku default R runtime dan bagaimana cara mengonfigurasi Plumber/httpuv agar menyelesaikan HTTP request yang sedang berjalan sebelum proses dihentikan? Bagaimana mendesain endpoint `/healthz` (liveness) dan `/readyz` (readiness) yang secara akurat memverifikasi dependensi upstream (misalnya koneksi database pool via `pool`) tanpa membebani performa sistem?

5. **Dynamic UI Rendering dan JavaScript-R Communication Bottleneck:**
   Pada dashboard Shiny berskala besar, penggunaan berlebihan fungsi `renderUI()` / `uiOutput()` sering menyebabkan *lag* yang signifikan pada rendering browser. Analisis bottleneck yang terjadi pada *WebSocket payload* dan DOM tree rerendering. Bagaimana strategi refactoring untuk memindahkan manipulasi DOM ke client-side menggunakan JavaScript kustom (`session$sendCustomMessage` dan `Shiny.addCustomMessageHandler`)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Cascading Freeze (Bottleneck Skala Besar)
Sebuah perusahaan logistik menggunakan dashboard R Shiny yang di-host di Kubernetes dengan 3 replika Pod di belakang Ingress Controller. Setiap replika dialokasikan 2 Core CPU dan 4 GB RAM. Pada jam operasional sibuk, ketika beberapa manajer serentak menekan tombol *"Generate End-of-Day Route Optimization"*, seluruh UI dashboard dari semua user yang terhubung ke Pod yang sama langsung membeku (*frozen*), WebSocket mengalami timeout, dan Ingress mulai mengembalikan HTTP 504 Gateway Timeout.

*   **Tugas Diagnostik:**
    1. Identifikasi akar penyebab masalah (*root cause*) ditinjau dari arsitektur *event loop* Shiny dan resource contention.
    2. Rancang solusi arsitektural komprehensif: Bagaimana memodifikasi pipeline komputasi rute tersebut tanpa mengorbankan interaktivitas UI dashboard bagi pengguna lain pada Pod yang sama? (Sertakan pertimbangan penggunaan asynchronous task queue seperti Celery/Redis atau integrasi package `future`/`callr`).

### Skenario B: The Cross-Tenant Data Leak (Race Condition & Data Integrity)
Sebuah institusi perbankan mengimplementasikan REST API menggunakan Plumber untuk kalkulasi profil risiko nasabah. API ini deployed pada infrastruktur bare-metal multi-core menggunakan `pm2` atau multi-process clustering. Tiba-tiba seorang nasabah VIP komplain bahwa respons JSON yang mereka terima memuat data portofolio dari nasabah lain yang melakukan kalkulasi pada milidetik yang sama.

*   **Tugas Diagnostik:**
    1. Bedah potensi kegagalan kode di dalam script Plumber yang dapat menyebabkan *state sharing* atau race condition antar concurrent requests. (Tinjau aspek deklarasi variabel global, *filter hooks*, dan lingkungan eksekusi package level).
    2. Tuliskan contoh cuplikan kode anti-pattern yang menyebabkan bug tersebut dan perbaiki (*patch*) agar API bersifat strictly idempotent, thread-safe (isolated per request), dan mematuhi standar keamanan audit industri finansial.

### Skenario C: The Monolith Scaling Dilemma (Arsitektur & Trade-off Sistem)
Tim data science Anda memiliki model prediksi demand real-time berbasis XGBoost. Tim bisnis meminta sistem analytics yang:
1. Menyediakan dashboard real-time dengan kemampuan input *what-if analysis* interaktif (pengguna mengubah parameter visual dan melihat kurva demand bergeser).
2. Mengekspos endpoint API machine learning yang sama untuk dikonsumsi oleh aplikasi mobile backend pihak ketiga dengan target throughput ~1.500 requests/second pada SLA p99 < 50ms.

*   **Tugas Diagnostik:**
    1. Evaluasi secara kritis trade-off jika arsitektur dibangun sebagai satu monolit R Shiny vs arsitektur terdecoupling (Shiny/React frontend + Plumber/FastAPI backend + load balancer).
    2. Apakah Plumber mampu menangani SLA 1.500 rps p99 < 50ms secara native? Jika tidak, bagaimana Anda merancang arsitektur hybrid yang memaksimalkan keunggulan ekosistem R untuk modeling/dashboarding namun tetap memenuhi SLA performa backend berskala tinggi?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Asynchronous Machine Learning Inference API dengan Plumber & Docker

#### 1. Problem Statement
Anda ditugaskan membangun layanan microservice inferensi model berbasis R yang siap untuk lingkungan produksi (*production-grade*). Layanan ini harus mampu memproses prediksi risiko kredit, mencatat metrik telemetri secara terstruktur, mengekspos endpoint pemantauan (*health check*), dan tidak boleh mengalami *blocking* saat menerima beberapa kalkulasi berat secara bersamaan.

#### 2. Requirements & Functional Specs
*   **API Framework:** Gunakan package `plumber`.
*   **Asynchronous Execution:** Endpoint inferensi utama (`POST /v1/predict`) harus memproses komputasi scoring menggunakan package `promises` dan `future` agar request berurutan tidak saling memblokir *event loop*.
*   **Data Validation:** Terapkan validasi skema input data yang ketat (tipe data, range numerik, missing values). Jika input tidak valid, kembalikan HTTP 400 Bad Request dengan payload JSON error yang terstruktur.
*   **Structured Logging & Auditing:** Implementasikan Plumber *filter* untuk mencatat setiap incoming request (timestamp UTC, client IP, endpoint, latency response dalam milidetik, dan HTTP status code) dalam format **JSON Lines (NDJSON)** ke `stdout`.
*   **System Reliability:**
    *   Endpoint `GET /livez`: Mengembalikan HTTP 200 OK jika proses R hidup.
    *   Endpoint `GET /readyz`: Mengembalikan HTTP 200 OK jika model ter-load ke memori dan alokasi resource dalam batas aman; jika tidak, kembalikan HTTP 503 Service Unavailable.
*   **Containerization:** Buat `Dockerfile` berbasis Ubuntu/Debian minimal (misalnya menggunakan base image `rocker/r-ver`) dengan implementasi non-root user, optimasi layer caching dependensi via `renv`, dan konfigurasi environment runtime.

#### 3. Constraints
*   Tidak boleh menggunakan variabel di `.GlobalEnv` untuk menyimpan context request.
*   Total ukuran container image final harus di bawah 1 GB.
*   Aplikasi harus berjalan sebagai non-root user (`UID 10001`) di dalam container demi kepatuhan keamanan CIS Benchmark.

#### 4. Expected Output
1.  **File `plumber.R`**: Script lengkap yang memuat endpoints (`/v1/predict`, `/livez`, `/readyz`), hooks/filters untuk logging, error handling tersentralisasi, dan simulasi inferensi ML asynchronous.
2.  **File `entrypoint.R`**: Script untuk inisialisasi background worker pool (`future::plan(multisession, workers = ...)`) dan menjalankan Plumber router pada port 8080.
3.  **File `Dockerfile`**: Konfigurasi multi-stage build yang mematuhi standar enterprise dan instruksi eksekusi non-root.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan mendasar antara R *event-driven loop* (httpuv) dengan multithreaded server model (seperti Go/Java).
- [ ] Mekanisme DAG pada Reactive Graph Shiny dan dampak fungsi non-reaktif di dalam closure reaktif.
- [ ] Siklus routing HTTP pada Plumber: *Request -> Filters -> Endpoint -> Serializer -> Response*.
- [ ] Mengapa isolasi memory pada R worker processes (fork vs socket) memengaruhi footprint RAM saat scaling horizontal.
- [ ] Konsep Twelve-Factor App yang diaplikasikan pada containerization R (statelessness, port binding, environment variables, logs to stdout).
- [ ] Batasan konkurensi database connection pada R dan implementasi dynamic connection pooling via package `pool`.

### Saya tidak perlu menghafal:
- [ ] Nama seluruh library dependensi Linux (misal: `libcurl4-openssl-dev`, `libssl-dev`) di luar dokumentasi instalasi standar.
- [ ] Sintaks spesifik seluruh CSS tag atau JavaScript helper pada customization Shiny UI; gunakan dokumentasi UI framework sesuai kebutuhan.
- [ ] Parameter konfigurasi low-level httpuv C++ internal; cukup pahami abstraction layer pada Plumber/Shiny.

### Saya harus bisa melakukan:
- [ ] Menulis Plumber API yang asynchronous menggunakan `promises` dan `future` untuk mencegah blocking I/O/compute.
- [ ] Mengonfigurasi `Dockerfile` berbasis multi-stage build dengan integrasi `renv` untuk dependency locking deterministik.
- [ ] Mengimplementasikan structured JSON logging pada middleware R untuk integrasi dengan Log Aggregator (Elasticsearch/Datadog/Loki).
- [ ] Melakukan profiling aplikasi Shiny atau Plumber yang lambat menggunakan `profvis` untuk menemukan exact bottleneck pada CPU atau alokasi memori.
- [ ] Mendesain arsitektur microservices terdistribusi yang memisahkan frontend UI (Shiny/Web), API layer (Plumber), dan backend background worker queues.