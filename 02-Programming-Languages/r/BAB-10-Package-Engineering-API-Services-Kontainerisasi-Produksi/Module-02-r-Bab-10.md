# Kurikulum Enterprise R: Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Package Engineering, API Services, Kontainerisasi & Produksi**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis Internal R Runtime**: Menguasai arsitektur event loop `httpuv`, interaksi libuv, serta siklus hidup Generational Garbage Collector (GC) R dalam proses daemon persisten.
2. **Merancang API Asinkron Berkinerja Tinggi**: Mengimplementasikan non-blocking asynchronous REST API menggunakan ekosistem `plumber`, `promises`, dan `future` untuk mencegah *event loop starvation*.
3. **Mengabstraksi Keamanan & Observabilitas**: Membangun pipeline middleware untuk autentikasi zero-trust, structured logging (JSON), custom error handling, dan instrumentasi metrik Prometheus/OpenTelemetry.
4. **Menerapkan Rekayasa Kontainer Standar OCI**: Menulis Multi-stage Build `Dockerfile` yang dioptimasi untuk arsitektur R, meminimalisasi ukuran image, mengisolasi dependensi C/C++ (BLAS/LAPACK), dan berjalan di bawah prinsip non-root user.
5. **Mengorkestrasi Arsitektur Produksi Skala Horisontal**: Mendesain topology microservice R dengan Reverse Proxy (Traefik/Nginx), load balancing, Redis caching layer, dan health check probe untuk Kubernetes orchestration.

---

## 2. Prerequisite
Engineer wajib memiliki pemahaman mendalam pada domain berikut:
* **Advanced R**: Lexical scoping, environment tree, pointer address via `lobstr`, reference counting, functional programming (`purrr`), serta S3/R6 Object-Oriented System.
* **Sistem Operasi & Jaringan**: POSIX signals (`SIGTERM`, `SIGKILL`), fork and spawn process model, TCP/IP socket connection, HTTP/1.1 & HTTP/2 spec, TLS termination.
* **Linux & Containers**: Linux namespaces, cgroups v2, multi-stage Docker builds, OCI images, shell scripting.
* **Alat Pengujian**: Profiling R code via `profvis`, load testing menggunakan `k6` atau `hey`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Arsitektur Single-Thread R dan httpuv Event Loop
R secara native bersifat *single-threaded*, mengeksekusi instruksi secara sekuensial di dalam satu thread utama. Ketika API framework seperti `plumber` dijalankan, server HTTP dibangun di atas paket `httpuv`, yang membungkus library C++ performa tinggi: **libuv** (abstraksi asynchronous I/O cross-platform berbasis event loop) dan **http-parser**.

```
+-------------------------------------------------------------+
|                     R Native Process                        |
|                                                             |
|  +-------------------------+     +-----------------------+  |
|  |     Plumber Router      |     | Global Environment    |  |
|  |  (Filters, Controllers) |     | (State, Model Cache)  |  |
|  +------------^------------+     +-----------^-----------+  |
|               |                              |              |
|  +------------v------------------------------v-----------+  |
|  |                    R Execution Thread                 |  |
|  +----------------------------^--------------------------+  |
|                               | (Synchronous Callback)       |
|  +----------------------------v--------------------------+  |
|  |                   httpuv C++ Layer                    |  |
|  |  +---------------------+      +--------------------+  |  |
|  |  |   libuv Event Loop  | <--> |   http-parser      |  |  |
|  |  +----------^----------+      +--------------------+  |  |
+----------------|--------------------------------------------+
                 | (epoll / kqueue)
        [ Incoming TCP Requests ]
```

1. **TCP Ingestion**: `libuv` menangani socket non-blocking pada kernel level (`epoll` di Linux).
2. **HTTP Parsing**: Saat request byte masuk, `http-parser` mengurai headers dan payload.
3. **Execution Handoff**: `httpuv` memicu callback R di thread utama. Jika endpoint mengeksekusi operasi sinkron yang intensif (seperti inferensi matriks CPU 500ms), **seluruh event loop terblokir**. Request lain yang masuk akan tertahan di backlog buffer kernel OS.

### 3.2 Model Eksekusi Asinkron: `promises` dan `future`
Untuk memecahkan batasan *event loop blocking*, ekosistem R menggunakan abstraksi `promises` (terinspirasi dari JavaScript ES6 Promises/A+ spec) dan `future`.

```
Client Request -> [httpuv Loop] -> Trigger Future -> Dispatch to Worker Process (PID: 2045)
                         |                                |
             (Loop tetap melayani ping/healthz)           | (CPU Heavy Computing)
                         |                                |
                      Promise Resolves <------------------+
                         |
                 Send HTTP 200 OK
```

* **`future::multisession`**: Membuat cluster background R worker terisolasi melalui background sockets. Data diserialisasi via R connection.
* **`future::multicore`**: Menggunakan kernel POSIX `fork()`. Lebih hemat memori melalui *Copy-On-Write* (COW), namun tidak aman bila R terhubung dengan multi-threaded BLAS (OpenBLAS/MKL) atau grafis/GUI handles, karena rawan memicu *deadlock*.
* **`promises::%...>%`**: Operator pipe asinkron yang mendaftarkan callback ke event loop `httpuv`. Worker mengeksekusi instruksi di background, sementara R thread utama segera kembali melayani request HTTP berikutnya.

### 3.3 Siklus Hidup R Generational Garbage Collector (GC)
R mengimplementasikan Tri-color generational collector:
* **Node Class / Cons Cells**: Tipe data skalar, ekspresi bahasa, pasangan atribut.
* **Vector Cells**: Tipe data array numerik, integer, raw vector byte buffer.
* **Generasi (Gen 0, 1, 2)**: Objek baru lahir di Gen 0. Jika bertahan dari siklus pembersihan, dinaikkan ke Gen 1 dan Gen 2.

Pada daemon API berumur panjang (*long-running processes*), kebocoran memori umum terjadi bukan karena GC gagal, melainkan karena pointer referensi yang tersimpan secara tidak sengaja di dalam *lexical closure*, *package-level environment*, atau *plumber filters*. GC tidak akan membersihkan memori yang masih memiliki *in-degree edge* dari root node (`.GlobalEnv`).

---

## 4. Why & What
* **Mengapa Menggunakan R di Produksi?** R adalah *lingua franca* untuk komputasi statistik canggih, bioinformatika, ekonometrika, dan model aktuaria yang sering kali tidak memiliki ekuivalen 1:1 di runtime lain (Python/Go/Rust).
* **Masalah Arsitektural**: R runtime didesain untuk analisis interaktif in-memory, bukan untuk *concurrency daemon*.
* **Solusi**: Transformasi R dari script-based ke *Twelve-Factor Microservice*. Kita mengisolasi R dalam kontainer stateless, menggunakan reverse proxy untuk menangani konkurensi I/O tinggi, dan mendistribusikan komputasi CPU via dynamic process pools.

---

## 5. How (Workflow Detail)

Arsitektur produksi enterprise mengadopsi pola **Process-per-Core + Asynchronous Execution**:

```
[ Ingress: Traefik / Nginx (SSL Termination, Rate Limiting, Round-Robin) ]
         |
         +--> Worker Replica 1 (Container: R Plumber Port 8000)
         |       |--> Thread Utama (httpuv Event Loop)
         |       |--> Future Pool (Background Worker PID 101, PID 102)
         |
         +--> Worker Replica 2 (Container: R Plumber Port 8000)
         |       |--> Thread Utama (httpuv Event Loop)
         |       |--> Future Pool (Background Worker PID 201, PID 202)
         |
         +--> Worker Replica N (...)
```

### Langkah Deployment Produksi:
1. **Request Intake**: Nginx/Traefik menerima HTTP request eksternal, memverifikasi TLS, dan membagi beban ke beberapa instance kontainer R.
2. **Security & Validation Layer**: Plumber Filter mengeksekusi autentikasi header (JWT/Bearer), memvalidasi struktur payload request via schema checker (misal: `checkmate`).
3. **Execution Offload**: Endpoint membungkus komputasi inferensi ke dalam `future::future({ ... })`.
4. **Structured Response**: Serializer JSON mengubah R objects menjadi string JSON berstandar RFC 8259 tanpa konversi skalar/array yang ambigu.
5. **Observability Emit**: Filter akhir (post-routing hook) mencatat metrik latensi dan status HTTP ke logging stream JSON standar (stdout).

---

## 6. Analogy & Diagram ASCII

### Analogi: Dapur Restoran Eksekutif
* **R Single-Threaded murni**: Satu Master Chef menerima pesanan di kasir, memasak sendiri di wajan, membungkus makanan, dan menyerahkannya. Jika ada pesanan daging wagyu yang butuh 30 menit memanggang, seluruh antrean kasir terhenti total.
* **Plumber + Asynchronous Future**: Kasir (httpuv Event Loop) menerima pesanan, mencatat tiket, lalu menyerahkannya ke asisten koki di dapur belakang (Future Worker). Kasir langsung melayani pembeli berikutnya. Begitu daging matang, kasir memanggil nama pemesan dan menyerahkan makanan.

### Diagram Alur Internal Plumber Pipeline

```
[ HTTP Inbound: POST /api/v1/predict ]
                 |
                 v
   +----------------------------+
   |   Hook: preroute           |  --> Catat Start Timestamp, Buat Request-ID
   +----------------------------+
                 |
                 v
   +----------------------------+
   |   Filter: auth_filter      |  --> Verifikasi Bearer Token / API-Key
   +----------------------------+
                 | (Valid)
                 v
   +----------------------------+
   |   Parser: parse_json       |  --> Parse Request Body ke R List
   +----------------------------+
                 |
                 v
   +----------------------------+
   |   Endpoint Handler         |  --> future::future({ Model Inference })
   +----------------------------+
                 | (Returns Promise)
                 v
   +----------------------------+
   |   Serializer: serializer_json | -> Konversi R Matrix/List ke JSON Buffer
   +----------------------------+
                 |
                 v
   +----------------------------+
   |   Hook: postroute          |  --> Log JSON Structured: Status, Duration, Path
   +----------------------------+
                 |
                 v
[ HTTP Outbound: 200 OK + Payload ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Asynchronous Non-blocking Endpoint
Menggunakan `plumber`, `promises`, dan `future` untuk simulasi komputasi berat tanpa memblokir request lain.

```r
# simple_async.R
library(plumber)
library(promises)
library(future)

# Inisialisasi pool background worker
plan(multisession, workers = 2)

#* @apiTitle Simple Async Plumber

#* Health check endpoint (harus merespons cepat meski ada heavy job)
#* @get /healthz
function() {
  list(status = "healthy", timestamp = Sys.time())
}

#* Simulasi komputasi intensif tanpa memblokir healthz
#* @get /heavy-compute
function() {
  future({
    # Simulasi perhitungan berat (misal bootstrap sampling)
    Sys.sleep(5)
    result <- mean(rnorm(1e7))
    result
  }) %...>% (function(val) {
    list(status = "completed", mean_value = val)
  }) %...!% (function(err) {
    list(status = "error", message = err$message)
  })
}
```

### 7.2 Practical Example: Enterprise Inference Engine
Implementasi microservice API inferensi XGBoost/Matrix lengkap dengan:
1. Structured Logging (Log correlation ID).
2. Input validation menggunakan `checkmate`.
3. Authentication Hook.
4. Error handler terpusat.
5. Prometheus metric scraper ready.

```r
# inst/api/entrypoint.R
suppressPackageStartupMessages({
  library(plumber)
  library(promises)
  library(future)
  library(logger)
  library(jsonlite)
  library(checkmate)
  library(uuid)
})

# Setup Future workers pool
plan(multisession, workers = parallelly::availableCores(omit = 1))

# Konfigurasi JSON Structured Logging
log_formatter(formatter_json())
log_appender(appender_stdout)

# Inisialisasi Plumber Router
pr <- pr()

# ---------------------------------------------------------
# HOOKS: Request Tracing & Structured Logging
# ---------------------------------------------------------
pr <- pr_hook(pr, "preroute", function(req) {
  req$HTTP_X_REQUEST_ID <- req$HTTP_X_REQUEST_ID %||% UUIDgenerate()
  req$start_time <- proc.time()[["elapsed"]]
})

pr <- pr_hook(pr, "postroute", function(req, res) {
  duration_ms <- (proc.time()[["elapsed"]] - req$start_time) * 1000
  log_info(
    request_id = req$HTTP_X_REQUEST_ID,
    remote_addr = req$REMOTE_ADDR,
    method = req$REQUEST_METHOD,
    path = req$PATH_INFO,
    status = res$status,
    latency_ms = round(duration_ms, 2)
  )
})

# ---------------------------------------------------------
# FILTER: Authentication Middleware
# ---------------------------------------------------------
pr <- pr_filter(pr, "auth", function(req, res) {
  # Endpoint public /healthz & /readyz diizinkan bypass auth
  if (req$PATH_INFO %in% c("/healthz", "/readyz", "/openapi.json")) {
    return(forward())
  }
  
  auth_header <- req$HTTP_AUTHORIZATION
  valid_token <- Sys.getenv("API_SECRET_BEARER", "super-secret-token")
  
  if (is.null(auth_header) || !grepl("^Bearer ", auth_header)) {
    res$status <- 401
    return(list(error = "Unauthorized", message = "Missing or malformed Authorization header."))
  }
  
  token <- sub("^Bearer ", "", auth_header)
  if (!identical(token, valid_token)) {
    res$status <- 403
    return(list(error = "Forbidden", message = "Invalid credentials."))
  }
  
  forward()
})

# ---------------------------------------------------------
# ENDPOINTS: Observability & Health Probes
# ---------------------------------------------------------
#* Liveness Probe
#* @serializer unboxedJSON
#* @get /healthz
function() {
  list(status = "UP")
}

#* Readiness Probe (Cek koneksi dependency eksternal/resource)
#* @serializer unboxedJSON
#* @get /readyz
function(res) {
  # Simulasi dependensi memori & worker pool readiness
  ready <- length(future::resolved(future(TRUE))) == 1
  if (!ready) {
    res$status <- 503
    return(list(status = "DEGRADED", reason = "Worker pool exhausted"))
  }
  list(status = "READY")
}

# ---------------------------------------------------------
# ENDPOINTS: Model Inference (Asynchronous Execution)
# ---------------------------------------------------------
#* Prediksi Risiko Kredit
#* @post /v1/predict/credit-risk
#* @parser json
#* @serializer unboxedJSON
function(req, res) {
  body <- req$body
  
  # Validasi Input secara ketat menggunakan checkmate
  coll <- makeAssertCollection()
  assert_number(body$income, lower = 0, add = coll)
  assert_number(body$loan_amount, lower = 1, add = coll)
  assert_int(body$credit_score, lower = 300, upper = 850, add = coll)
  assert_string(body$employment_status, add = coll)
  
  if (!coll$isEmpty()) {
    res$status <- 422
    return(list(
      error = "Unprocessable Entity",
      validation_errors = coll$getMessages()
    ))
  }
  
  # Copy data ke isolated context untuk thread worker
  input_data <- list(
    income = body$income,
    loan_amount = body$loan_amount,
    credit_score = body$credit_score,
    dti = body$loan_amount / max(body$income, 1)
  )
  
  # Offload CPU compute ke worker process
  future({
    # Simulasi inferensi algoritma skoring kredit
    weights <- c(dti = 0.4, score = -0.005, intercept = 2.1)
    linear_predictor <- (input_data$dti * weights[["dti"]]) + 
                        (input_data$credit_score * weights[["score"]]) + 
                        weights[["intercept"]]
    probability <- 1 / (1 + exp(-linear_predictor))
    
    list(
      default_probability = round(probability, 4),
      risk_category = if (probability > 0.5) "HIGH" else "LOW",
      processed_by_pid = Sys.getpid()
    )
  }) %...>% (function(inference_result) {
    res$status <- 200
    c(list(request_id = req$HTTP_X_REQUEST_ID), inference_result)
  }) %...!% (function(err) {
    log_error("Inference failure: {err$message}")
    res$status <- 500
    list(error = "Internal Server Error", message = "Computation failed.")
  })
}

# Centralized Error Handling
pr_set_error(pr, function(req, res, err) {
  log_error("Unhandled Exception: {err$message}")
  res$status <- 500
  list(error = "Internal Server Error", detail = err$message)
})

# Menjalankan router jika dipanggil langsung
if (sys.nframe() == 0) {
  pr$run(host = "0.0.0.0", port = 8000)
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Sistem Real-Time Fraud Risk Scoring (Fintech Multinasional)
* **Konteks**: Lembaga keuangan memproses transaksi pembayaran digital dengan beban puncak **1.500 transaksi per detik (TPS)**. Model scoring matematis berbasis R (penjumlahan matriks terbobot, isolasi anomali spatio-temporal) menghasilkan p95 latency yang sebelumnya mencapai 4.200ms di arsitektur monolitik, sering kali mengalami crash `OOMKilled` (Out of Memory) di Kubernetes.

### Solusi Arsitektural:
1. **Dekomposisi Monolit**: Memisahkan model inferensi ke dalam *stateless microservice container* R yang sangat ramping.
2. **Reverse Proxy & Concurrency Buffer**: Menempatkan **Traefik Edge Router** di depan pod R. Traefik menerapkan circuit breaking, rate limiting, dan buffering socket pool.
3. **Optimasi Container Engine**:
   * Menghilangkan alokasi memori berulang dengan serialisasi model menggunakan format native C binary `qs` (`qs::qread`) saat bootstrap kontainer.
   * Kubernetes HPA (Horizontal Pod Autoscaler) dikonfigurasi berdasarkan metrik kustom latensi HTTP (Prometheus metrics) bukan sekadar CPU metrics, scaling dinamis dari 5 ke 40 pods.
4. **Hasil**:
   * Latensi **p95 turun dari 4.200ms menjadi 42ms**.
   * Utilisasi RAM per worker berkurang hingga 68% berkat shared read-only mapping data referensi.
   * Ketersediaan layanan (Uptime) mencapai 99.98% selama periode flash sale.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Dimensi Arsitektur | Pilihan A: In-Process Forking (`future::multicore`) | Pilihan B: Background Workers (`future::multisession`) | Pilihan C: Pod Horizontal Scaling (K8s Native) |
| :--- | :--- | :--- | :--- |
| **Throughput & Speed** | Ekstrem (zero-copy memory via Copy-On-Write). | Sedang (overhead serialisasi data inter-process). | Sangat Tinggi (Terdistribusi di berbagai Node). |
| **Stability / Safety** | **Bahaya**: Deadlock pada OpenMP/BLAS atau package eksternal C++. | **Aman**: Lingkungan memori terisolasi penuh, crash worker tidak mematikan parent. | **Paling Aman**: Isolasi penuh level Linux namespace dan cgroups. |
| **Memory Footprint** | Sangat Hemat pada startup, berisiko melar seiring write operations. | Moderat (Setiap worker mereplikasi base R footprint ~40MB). | Mahal (Setiap container menjalankan runtime OS mini + R stack). |
| **Infrastruktur & Cost**| Murah (Beban komputasi terpusat pada server bare-metal besar). | Murah hingga Moderat. | Lebih mahal (Kebutuhan cluster Kubernetes & ingress controller). |
| **Rekomendasi Enterprise**| Dihindari untuk API kritis produksi. | Cocok untuk deployment server mandiri (EC2/VM tunggal). | **Standar Emas Enterprise**: Kombinasi K8s Pods + 2 Multisession workers per Pod. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Memory Leak Melalui Lexical Closure
* **Penyebab**: Menyimpan fungsi callback di dalam environment filter yang tanpa disengaja membawa reference ke objek dataframe raksasa dari enclosing scope.
* **Diagnosis**: Gunakan paket `lobstr` dan profiler alokasi objek.
  ```r
  # Identifikasi ukuran environment
  lobstr::obj_size(topenv())
  ```
* **Solusi**: Bersihkan variabel temporer dengan `rm(var)` dan panggil `gc()` secara periodik bila mutasi objek data besar terjadi, atau gunakan environment terisolasi (`new.env(parent = emptyenv())`).

### 10.2 Event Loop Starvation Akibat Blocking I/O
* **Penyebab**: Memanggil operasi lambat secara sinkron langsung di handler (misal: query SQL `DBI::dbGetQuery` tanpa async wrapper).
* **Solusi**: Pindahkan I/O call ke dalam blok `future({...})`.

### 10.3 Deadlock OpenMP / Multicore Forking
* **Gejala**: Kontainer R tiba-tiba berhenti merespons (hang indefinitely), penggunaan CPU 0%, tidak ada log error.
* **Penyebab**: Panggilan `mclapply` atau `future::multicore` saat library multi-threaded C/Fortran (seperti OpenBLAS) aktif.
* **Solusi**: Set environment variables di level container OS:
  ```bash
  export OMP_NUM_THREADS=1
  export OPENBLAS_NUM_THREADS=1
  export MKL_NUM_THREADS=1
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Non-Root Execution**: Docker container HARUS mengeksekusi R di bawah UID non-root (misal: `UID 1000: rstudio` atau `appuser`).
- [ ] **Twelve-Factor Configuration**: Konfigurasi database, secret credentials, dan URL eksternal wajib dibaca dari Environment Variables (`Sys.getenv()`), BUKAN hardcoded di dalam R script.
- [ ] **Signal Handling (Graceful Shutdown)**: Tangkap sinyal `SIGTERM` untuk mengizinkan worker menyelesaikan proses pipeline transaksi sebelum mematikan pod.
- [ ] **Deterministic Serialization**: Hindari serialization otomatis R yang ambigu. Selalu gunakan `@serializer unboxedJSON` untuk skalar, atau pastikan array skalar tetap di-serialize sebagai JSON array bila diperlukan client via `jsonlite::unbox()` / `I()`.
- [ ] **Health Checks Probes**: Sediakan pemisahan eksplisit antara endpoint `/healthz` (liveness: webserver hidup) dan `/readyz` (readiness: model terload di memory dan siap scoring).
- [ ] **No Local Disk Dependencies**: Kontainer R harus bersifat ephemeral. Dilarang menulis artifacts sementara ke direktori root container; gunakan ephemeral storage `/tmp` jika mutlak diperlukan.

---

## 12. Hands-on Practice

Struktur direktori kerja implementasi:
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── src/
    ├── api.R
    └── run.R
```

### Langkah 1: Buat R Script API & Runtime Loader
Tulis kode berikut pada `hands-on/m02/src/api.R`:
```r
library(plumber)
library(jsonlite)

#* @apiTitle Production Enterprise API
#* @apiDescription Minimal microservice showcase

#* @get /healthz
#* @serializer unboxedJSON
function() {
  list(status = "OK", pid = Sys.getpid())
}

#* @post /echo
#* @parser json
#* @serializer unboxedJSON
function(req) {
  list(
    message = "Success",
    client_ip = req$REMOTE_ADDR,
    received_payload = req$body
  )
}
```

Tulis file loader pada `hands-on/m02/src/run.R`:
```r
library(plumber)

port <- as.integer(Sys.getenv("PORT", "8000"))
pr <- plumb("/app/src/api.R")
pr$run(host = "0.0.0.0", port = port)
```

### Langkah 2: Rekayasa Multi-Stage Dockerfile
Tulis Dockerfile performa tinggi di `hands-on/m02/Dockerfile`:
```dockerfile
# ---------------------------------------------------
# STAGE 1: Dependency Builder
# ---------------------------------------------------
FROM rocker/r-ver:4.3.3 AS builder

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN R -e "install.packages(c('plumber', 'jsonlite', 'promises', 'future', 'logger', 'checkmate'), repos='https://cloud.r-project.org/')"

# ---------------------------------------------------
# STAGE 2: Lightweight Runtime Image
# ---------------------------------------------------
FROM rocker/r-ver:4.3.3

# Metadata OCI standard
LABEL maintainer="Enterprise Architecture Team"
LABEL version="1.0.0"

RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4 \
    libssl3 \
    libxml2 \
    libsodium23 \
    && rm -rf /var/lib/apt/lists/*

# Salin pre-compiled library dari builder
COPY --from=builder /usr/local/lib/R/site-library /usr/local/lib/R/site-library

# Buat non-root service account
RUN groupadd -g 1001 rgroup && \
    useradd -u 1001 -g rgroup -m -s /bin/bash rappuser

WORKDIR /app
COPY src/ /app/src/

RUN chown -R rappuser:rgroup /app

USER rappuser

EXPOSE 8000

ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PORT=8000

STOPSIGNAL SIGTERM

ENTRYPOINT ["Rscript", "/app/src/run.R"]
```

### Langkah 3: Konfigurasi Nginx Reverse Proxy
Tulis konfigurasi reverse proxy di `hands-on/m02/nginx.conf`:
```nginx
events { worker_connections 1024; }

http {
    upstream plumber_backend {
        # Round-robin load balancing ke 2 instance kontainer R
        server r_api_1:8000;
        server r_api_2:8000;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://plumber_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeout tuning untuk operasi R compute
            proxy_connect_timeout 5s;
            proxy_read_timeout 60s;
        }
    }
}
```

### Langkah 4: Orkestrasi Docker Compose
Tulis file `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - r_api_1
      - r_api_2

  r_api_1:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - PORT=8000

  r_api_2:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - PORT=8000
```

### Langkah 5: Eksekusi dan Verifikasi Load
Jalankan stack:
```bash
cd hands-on/m02/
docker compose up --build -d
```
Verifikasi load-balancer round-robin mendistribusikan request ke PID/kontainer berbeda:
```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/healthz
```

---

## 13. Exercise

### Level Easy
Ubah `api.R` untuk menambahkan endpoint `@get /system-info` yang mengembalikan arsitektur CPU (`R.version$arch`), versi OS (`R.version$os`), dan total memory usage session R saat ini menggunakan fungsi internal `gc()`.

### Level Medium
Buat custom Plumber Filter bernama `rate_limiter` yang memanfaatkan environment R internal untuk menghitung request per IP address (dari header `X-Real-IP`). Jika IP yang sama mengirim lebih dari 10 request per detik, return HTTP status `429 Too Many Requests`.

### Level Hard
Implementasikan sebuah pattern *Graceful Shutdown Handler* di script `run.R`. Intersepsi sinyal POSIX `SIGTERM`. Ketika sinyal diterima, hentikan intake request baru, tunggu semua tugas di dalam background worker `future` yang sedang berjalan hingga selesai (maksimal timeout 15 detik), cetak log shutdown bersih, lalu panggil `quit(status = 0)`.

---

## 14. Challenge

**Tantangan Arsitektur**: Bangun *High-Throughput Model Serving Pipeline* di R dengan kriteria ketat enterprise berikut:
1. **Model Cache Layer**: Buat sistem Dynamic Model Loading. API harus mampu meload 5 binary model GLM/XGBoost berbeda yang tersimpan di disk `/models/{model_id}.rds` secara on-demand (lazy load).
2. **LRU Cache Mechanism**: Batasi memori cache internal hanya untuk maksimal 2 model yang paling sering diakses. Gunakan mekanisme Least Recently Used (LRU) evicting policy berbasis R6 class.
3. **Resilience**: Jika input payload inferensi menyebabkan R worker segfault/crash (simulasikan dengan dereferensi invalid address via C/foreign memory pointer), event loop API server utama **TIDAK BOLEH MATI**. Client harus menerima HTTP 500 terstruktur, dan worker process yang mati harus secara otomatis di-spawn ulang oleh worker supervisor pool.
4. **Verifikasi**: Jalankan pengujian konkurensi via tool benchmark (`k6` atau Apache Bench) dengan 100 concurrent virtual users selama 60 detik tanpa kegagalan koneksi TCP (0% dropped packets).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)
1. Apa peran arsitektural paket `httpuv` dalam ekosistem Plumber?
   * A. Mengkompilasi kode R menjadi shared library C++ native.
   * B. Menyediakan HTTP web server engine berbasis library asynchronous libuv.
   * C. Menggantikan peran Garbage Collector dalam mengelola alokasi RAM R.
   * D. Melakukan transpilasi otomatis skrip R menjadi format JavaScript.
2. Mengapa menjalankan R murni secara synchronous di REST API berbahaya untuk traffic tinggi?
   * A. R tidak memiliki tipe data string untuk menangani HTTP response.
   * B. Event loop httpuv terblokir oleh komputasi CPU, menahan pemrosesan request lain.
   * C. R interpreter langsung mengalami crash jika antrean antarmuka TCP melebihi 10 koneksi.
   * D. Memori RAM server langsung dikosongkan secara paksa saat dua request masuk bersamaan.
3. Hook Plumber mana yang dieksekusi tepat sebelum response dikirimkan kembali ke HTTP client?
   * A. `preroute`
   * B. `postroute`
   * C. `preexec`
   * D. `around`
4. Manakah base image Docker resmi yang paling direkomendasikan untuk stabilitas reproducible R enterprise?
   * A. `alpine:latest`
   * B. `ubuntu:latest`
   * C. `rocker/r-ver:<version>`
   * D. `python:slim`
5. Mengapa tag metadata Docker `@serializer unboxedJSON` sering dipakai pada response skalar di Plumber?
   * A. Untuk mengompresi payload response menjadi format `.gzip`.
   * B. Mencegah R mengonversi vektor panjang 1 menjadi JSON array (misal: serialisasi `1` bukan `[1]`).
   * C. Mengenkripsi payload response menggunakan protokol TLS.
   * D. Menjamin response diformat dalam spesifikasi XML.

### 15.2 Pertanyaan Intermediate (Pilihan Ganda & Singkat)
1. Apa bahaya arsitektural penggunaan `future::plan(multicore)` pada container Linux yang mengaitkan R dengan library OpenBLAS / LAPACK multi-threaded?
2. Dalam implementasi pipeline `promises::%...>%`, di manakah eksekusi callback promise ditangani?
   * A. Di kernel OS driver level.
   * B. Di dalam httpuv event loop thread utama setelah background task resolve.
   * C. Di proses client yang mengirimkan HTTP request.
   * D. Di Redis broker layer.
3. Bagaimana cara memvalidasi contract payload JSON request body secara ketat sebelum diteruskan ke fungsi inferensi R?
4. Apa dampak penggunaan multi-stage build pada rekayasa image Docker untuk production R microservices?
5. Mengapa perintah `gc()` sebaiknya TIDAK dipanggil secara agresif pada setiap kali request HTTP masuk di endpoint Plumber?

### 15.3 Skenario Kasus Produksi (Esai Analitis)
1. **Skenario Latensi Abnormal**: Sebuah API Plumber menunjukkan grafik latensi flat 20ms pada 90% traffic, namun secara periodik p99 melompat tajam ke 8.000ms selama 5 detik, kemudian kembali normal. Tim infrastruktur mengonfirmasi tidak ada throttling CPU di pod. Apa hipotesis akar masalah internal R runtime yang memicu fenomena ini, dan bagaimana pembuktiannya?
2. **Skenario Zombie Process**: Di cluster Kubernetes, Anda mengamati pod API R Plumber Anda perlahan-lahan mengonsumsi seluruh alokasi PID (Process ID) host node hingga pod restart secara paksa. Setelah dicek, ratusan child worker berstatus `<defunct>`. Bagaimana arsitektur process lifecycle R container Anda bermasalah, dan instruksi Dockerfile/system apa yang hilang untuk mencegah hal ini?
3. **Skenario Out-of-Memory (OOM) Cascading Failure**: Di lingkungan produksi, 4 pod replica R API mati serempak akibat OOMKilled oleh kernel Linux saat load data meningkat tajam. Begitu pod baru di-restart oleh deployment controller, mereka langsung mati kembali dalam hitungan detik. Rancang arsitektur penanganan fail-safe yang mencakup Ingress layer, Circuit Breaker, dan Readiness Probes untuk menghentikan efek domino ini!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### 15.1 Basic
1. **B** — `httpuv` mengintegrasikan event loop asynchronous `libuv` dan parser HTTP C++ ke dalam R session.
2. **B** — R bersifat single-threaded native; komputasi CPU intensif yang sinkron mengunci event loop utama httpuv sehingga seluruh koneksi TCP lain macet.
3. **B** — Hook `postroute` dieksekusi setelah router selesai memproses endpoint dan serialisasi payload, tepat sebelum byte dikirim ke wire.
4. **C** — `rocker/r-ver:<version>` membekukan repositori CRAN snapshot berbasis tanggal rilis versi R tersebut, menjamin immutabilitas dan dependensi binary yang teruji.
5. **B** — Vektor R berdimensi 1 (`c("test")`) secara default diserialisasi oleh package `jsonlite` menjadi JSON array `["test"]`. Tag `unboxedJSON` memaksanya menjadi skalar `"test"`.

#### 15.2 Intermediate
1. **Bahaya Fork Safety**: OpenBLAS menginisialisasi thread pools internal sebelum fork POSIX dipanggil. Setelah `fork()`, mutex locks library C++ tersebut dapat terjebak dalam kondisi terkunci (inconsistent state), menghasilkan indefinite deadlock pada worker child process.
2. **B** — Background process mengeksekusi perhitungan, namun callback resolving ditangani di thread utama melalui poll handler libuv event loop.
3. **Validasi Skema**: Menggunakan assertion packages seperti `checkmate`, `assertthat`, atau validasi skema JSON berbasis `jsonvalidate` (JSON Schema draft-07) pada layer Plumber Filter sebelum request mencapai Controller handler.
4. **Dampak Multi-Stage**: Mengeliminasi build-time compiler dependencies (gcc, g++, gfortran, dev tools header) dari image akhir. Ini memangkas drastis ukuran image (sering kali dari >1.5GB ke <250MB) serta mereduksi CVE security attack surface.
5. **Dampak Pemanggilan GC Agresif**: Pemanggilan `gc()` mengeksekusi *Stop-The-World (STW)* pause pada R execution thread, menghentikan pemrosesan I/O socket dan memperburuk throughput server secara artifisial.

#### 15.3 Skenario Kasus Produksi
1. **Hipotesis GC Stop-The-World & Buffer Saturation**: Akumulasi temporary R objects di Generasi 2 (Gen 2) memicu *Full GC Cycle*. Jika heap memory besar, pemindaian mark-and-sweep memakan waktu multi-detik (STW pause). Pembuktian: Jalankan profiler session, atau catat output `gcinfo(TRUE)` ke file log untuk mencocokkan spike latensi p99 dengan timestamp log pembersihan Garbage Collector.
2. **Hilangnya Init System (PID 1 Reaper)**: Di dalam kontainer Docker, proses R dijalankan sebagai PID 1. Sebagai root process di isolated PID namespace, default Linux kernel mewajibkan PID 1 untuk me-reap (mengambil return code) child process yang telah terminate. Jika background worker spawn/die tanpa di-*waitpid* oleh R, mereka menjadi Zombie (`<defunct>`). **Solusi**: Tambahkan lightweight init system di Docker container, misal menggunakan flag `docker run --init` atau menyertakan utility `tini` (`ENTRYPOINT ["/usr/bin/tini", "--", "Rscript", ...]`).
3. **Pola Remediasi Cascading OOM**:
   * *Ingress Layer*: Terapkan Circuit Breaker dan Rate Limiting pada Ingress (Traefik/Nginx) untuk menolak request dengan status HTTP 429 atau 503 saat traffic melonjak melewati kapasitas aman pod.
   * *Readiness Probe Tuning*: Pisahkan liveness probe dan readiness probe. Konfigurasikan `/readyz` pada R pod agar mengukur memory consumption via `gc()`. Jika penggunaan RAM melampaui 80% ambang batas cgroup limits, `/readyz` mengembalikan status 503 Service Unavailable, sehingga Ingress controller otomatis mencabut pod tersebut dari load balancer upstream pool sebelum sempat dibunuh oleh Linux kernel OOM Killer.
   * *Stateless Resource Isolation*: Alihkan beban parsing dataset raksasa ke blob storage (S3) dan batch background workers terpisah, alih-alih memprosesnya di pod real-time inferensi.

---

## 16. Summary
* **Arsitektur Fundamental**: Menjalankan R di lingkungan enterprise menuntut pemahaman mendalam atas batas arsitektural R engine: ia merupakan runtime fungsional berbasis single-threaded execution context yang dikawinkan dengan C++ libuv asynchronous loop (`httpuv`).
* **Non-Blocking Execution Model**: Komputasi intensif dan I/O blocking wajib dialihkan dari thread loop utama menggunakan pola asinkron (`promises` + `future::multisession`).
* **Microservices Design Pattern**: Pola produksi modern menuntut pemisahan tugas ketat: Kontainer R harus bersifat ephemeral, stateless, terisolasi via non-root execution multi-stage build Docker, diproteksi oleh Ingress Reverse Proxy terdepan, serta dilengkapi instrumentasi observabilitas (Structured Logs & Health Probes) yang siap diorkestrasi oleh Kubernetes.