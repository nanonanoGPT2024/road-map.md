# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** R-ENG-1001
* **Kategori Kurikulum:** 02-Programming-Languages / R Track
* **Judul Modul:** Package Engineering, API Services, & Kontainerisasi Produksi
* **Level Kompleksitas:** Advanced / Enterprise Engineering
* **Prasyarat Pengetahuan:**
  * Penguasaan pemrograman fungsional R (Environments, Closures, S3/R6 Object Systems).
  * Pemahaman dasar arsitektur HTTP (Methods, Status Codes, Headers, MIME Types).
  * Pemahaman dasar Linux shell scripting dan manajemen dependensi software.
* **Alokasi Waktu Pembelajaran:** 180–240 Menit (Teori Mendalam & Implementasi Praktikum)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengonstruksi** paket R mandiri (*custom R package*) berstandar industri dengan mematuhi spesifikasi `Writing R Extensions`, konfigurasi `NAMESPACE` yang ketat, dan unit testing deterministik menggunakan framework `testthat`.
2. **Merancang dan Mengimplementasikan** microservices RESTful API berbasis R berperforma tinggi menggunakan pustaka `plumber`, lengkap dengan serialisasi payload, deserialisasi, *custom error handler*, dan middleware/filter.
3. **Menganalisis dan Mengatasi** keterbatasan *single-threaded execution model* pada R engine melalui integrasi asynchronous processing (`promises` & `future`).
4. **Membangun** *production-grade container images* (OCI compliant/Docker) untuk runtime R yang ramping, aman (*non-root privilege*), mengadopsi Posit Package Manager (PPM) untuk instalasi biner deterministik, serta terkelola via `renv`.
5. **Mengintegrasikan** sistem observabilitas (structured JSON logging, health checks, metrik Prometheus) dan hardening keamanan pada API R yang dikontainerisasi sebelum di-deploy ke cluster orkestrasi (Kubernetes/ECS).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam siklus hidup rekayasa data dan sains data, transisi dari **analisis interaktif** (*ad-hoc scripting*) ke **rekayasa perangkat lunak produksi** (*software engineering*) menuntut pergeseran paradigma mental secara fundamental:

```
[Ad-hoc Scripting (Interaktif)]        vs.        [Production Engineering (R di Produksi)]
--------------------------------                  ----------------------------------------
- Fokus: Hasil kalkulasi sesaat                  - Fokus: Reliabilitas, determinisme, throughput
- Dependensi: library() global & implicit         - Dependensi: Locked (renv), scoped namespaces
- State: Mutable global environment               - State: Ephemeral, encapsulated, stateless API
- Eksekusi: Manual via IDE (RStudio/Posit)        - Eksekusi: Headless daemon dalam OCI container
- Error Handling: Stop() dan crash                - Error Handling: Structured JSON HTTP response
```

### Mental Model 1: Paket R adalah Kontrak Enkapsulasi Tertinggi
Jangan pernah memandang paket R hanya sebagai cara mendistribusikan kode untuk CRAN. Paket R adalah **unit atomik kode produksi**. Paket menyediakan isolasi namespace, penegakan dokumentasi via `roxygen2`, dependensi eksplisit melalui `DESCRIPTION`, serta mekanisme verifikasi integritas bawaan via `R CMD check`. Jika kode R Anda masuk ke produksi, kode tersebut harus berbentuk paket, bukan kumpulan skrip liar yang dipanggil via `source()`.

### Mental Model 2: Plumber adalah Adapter Antarmuka, Bukan Mesin Bisnis
API layer (`plumber`) hanya berfungsi sebagai *transport adapter* HTTP yang menerjemahkan protokol web (JSON/HTTP) menjadi pemanggilan fungsi R native. Jangan mencampur logika bisnis atau algoritma komputasi di dalam file routing API (`plumber.R`). Logika inti harus hidup di dalam fungsi-fungsi paket R yang telah teruji secara terisolasi.

### Mental Model 3: Kontainer adalah Artefak Imut (*Immutable Artifact*)
Sebuah kontainer produksi tidak boleh melakukan kompilasi pustaka saat runtime atau mengunduh dependensi secara dinamis saat *booting*. Kontainer harus membawa *environment binary* yang identik, terkunci secara matematis melalui checksum `renv.lock`, berukuran sekecil mungkin, dan dijalankan dengan hak akses minimal (*least privilege*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram 1: Siklus Hidup Permintaan HTTP pada Plumber Microservice

```
                   CLIENT REQUEST (JSON via POST)
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ Ingress / Reverse Proxy   │ (Nginx / Cloud Load Balancer)
                   │ (SSL Termination, Rate)   │
                   └─────────────┬─────────────┘
                                 │ HTTP (Forwarded)
                                 ▼
                   ┌───────────────────────────┐
                   │ Plumber (httpuv event-loop│
                   └─────────────┬─────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       [Filter: Authentication]       [Filter: Request Logger]
       (Verifikasi Bearer Token)      (Inject UUID & Timestamp)
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                                 ▼
                      [Endpoint Matcher]
                     (e.g., POST /v1/score)
                                 │
                                 ▼
                  [Payload Parser & Validation]
                   (JSON Schema / Type Casting)
                                 │
                 ┌───────────────┴───────────────┐
                 ▼ (Valid)                       ▼ (Invalid)
       [Core Package Domain]             [HTTP 400 Bad Request]
       (fraudEngine::evaluate())                 │
                 │                               │
                 ▼                               │
       [Payload Serializer]                      │
       (JSON serialization)                      │
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                                 ▼
                    HTTP RESPONSE (JSON Content)
```

### Diagram 2: Alur Kompilasi & Build Multi-Stage Kontainer Produksi

```
  Source Code + renv.lock + DESCRIPTION
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 1: Builder Image                              │
│ - Base: rocker/r-ver:4.3.2                          │
│ - Setup Linux toolchain (gcc, g++, make)            │
│ - Fetch Pre-compiled Binaries (PPM via Posit)       │
│ - renv::restore() -> Build R package library        │
│ - R CMD INSTALL --build myEnginePkg                 │
└──────────────────────────┬──────────────────────────┘
                           │ Artifacts (.so, R libraries, binaries)
                           ▼
┌─────────────────────────────────────────────────────┐
│ STAGE 2: Production Runtime Image                   │
│ - Minimal system runtime libraries (libcurl, openssl)│
│ - Salin library dari STAGE 1                        │
│ - Tambah non-root user (appuser, UID 1001)          │
│ - Definisikan Entrypoint (Rscript run_api.R)        │
│ - Konfigurasi Healthcheck probe (/healthz)          │
└─────────────────────────────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi dan Mekanisme Namespace Paket R
R mengelola pemanggilan objek dan dependensi menggunakan dua mekanisme namespace:
* **Importing (`Imports` pada `DESCRIPTION` & direktif `importFrom` pada `NAMESPACE`):** Memetakan objek eksternal ke dalam private namespace paket Anda tanpa mencemari `search()` path global R. Ketika paket Anda memanggil `jsonlite::fromJSON`, pemanggilan ini dilewati langsung ke environment paket sasaran, mencegah *name masking collision*.
* **Exporting (`export` pada `NAMESPACE`):** Menentukan antarmuka publik yang dapat diakses pengguna luar atau layer API Plumber.

Struktur file paket standar:
```
myEnginePkg/
├── DESCRIPTION         # Metadata paket, dependensi, versi
├── NAMESPACE           # Definisi kontrol ekspor/impor (auto-generated roxygen2)
├── R/                  # Kode logika domain bisnis murni
│   ├── calculate.R
│   └── utils.R
├── tests/              # Validasi otomatis via testthat
│   ├── testthat.R
│   └── testthat/
│       └── test-calculate.R
├── inst/               # File aset arbitrary yang disertakan dalam instalasi
│   └── extdata/
└── man/                # File dokumentasi Rd (auto-generated)
```

### 2. Mekanisme Internal Plumber dan `httpuv`
Plumber dibangun di atas package `httpuv`, yang mengompilasi runtime libuv (event loop asinkron berbasis I/O multiplexing yang sama dengan Node.js) dan modul C++ HTTP-parser:
* **Event Loop Single-Thread:** R secara default bersifat *single-threaded*. Saat Plumber menerima HTTP request, `httpuv` membaca socket pada event loop C++, mengubah HTTP buffer mentah menjadi environment `req` R, lalu mengeksekusinya di R thread utama.
* **Filter Stack:** Middleware Plumber dieksekusi secara berurutan (*cascading chain*). Pemanggilan `plumber::forward()` menyerahkan kontrol eksekusi ke filter berikutnya. Apabila filter langsung mengembalikan nilai tanpa `forward()`, eksekusi rantai routing terhenti dan mengembalikan response seketika (*early exit*).

### 3. Lingkungan Eksekusi & Search Path
Saat R dijalankan dalam container headless, R tidak memuat workspace file `.RData` (jika dipanggil via flag `--no-save --no-restore`). Environment R yang bersih terdiri dari rantai hirarki:
$$\text{R\_GlobalEnv} \longrightarrow \text{package:plumber} \longrightarrow \dots \longrightarrow \text{package:base}$$
Paket terisolasi menghindari polusi ke `R_GlobalEnv`. Hal ini krusial untuk mencegah kebocoran memori (*memory leak*) pada aplikasi long-running daemon seperti microservice.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Determinisme Dependensi: Arsitektur `renv`
Dalam rekayasa sistem terdistribusi, dependensi yang mengambang (*unpinned floating dependencies*) adalah penyebab utama kegagalan fatal pada deployment kontainer. Modul `renv` memisahkan dependensi menjadi dua artefak:
* **`renv.lock`:** Dokumen JSON deklaratif yang mencatat versi persis, sumber repository (CRAN, Posit Public Package Manager/PPM, GitHub), dan hash integritas dari setiap paket dependensi rekursif.
* **Isolated Library:** Ruang direktori terisolasi tempat paket diinstal, sepenuhnya terpisah dari sistem library R global.

Saat bekerja dengan kontainer Linux, instalasi paket source C/C++ (seperti `Rcpp`, `arrow`, `data.table`) memakan waktu kompilasi yang signifikan. Solusinya adalah mengonfigurasi URL CRAN ke mirror PPM yang menyediakan **pre-compiled binary packages** untuk platform Linux spesifik (misal: Ubuntu Focal/Jammy). 

Rumus target URL Posit PPM:
$$\text{https://packagemanager.posit.co/cran/__linux__/[distribution\_codename]/latest}$$

### 2. Konkurensi & Karakteristik Non-Blocking I/O R
Karena R engine bersifat single-threaded, request HTTP yang membutuhkan komputasi berat akan memblokir request lain (*blocking queue*).
Untuk memitigasi ini dalam lingkungan Plumber:
* **I/O Asynchronous via `promises` & `future`:** Plumber mendukung eksekusi asynchronous. Endpoint yang menjalankan tugas komputasi tinggi atau query database eksternal dapat mendelegasikan beban ke sub-proses worker menggunakan abstraksi `future::future()` yang mengembalikan objek `promises::promise()`.
* Event loop `httpuv` segera dibebaskan untuk menerima koneksi HTTP berikutnya, sementara *promise* diselesaikan di latar belakang (*background evaluation*).

### 3. Lifecycle Manajemen Sinyal POSIX dalam Docker
Ketika Docker Daemon mengeksekusi `docker stop`, sinyal `SIGTERM` dikirim ke PID 1 di dalam kontainer. Jika kontainer Anda dijalankan dengan membungkus perintah R di dalam shell script tanpa penanganan sinyal yang tepat (`exec Rscript ...`), shell akan menelan sinyal tersebut, dan R tidak akan pernah menjalankan *graceful shutdown*. Setelah grace period habis (biasanya 10 detik), Docker akan mengirimkan `SIGKILL`, yang berisiko memotong transaksi data yang sedang berjalan, merusak state file, atau memutus koneksi socket secara paksa.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah konstruksi dasar: sebuah fungsi analitik di dalam struktur paket minimal, dipaparkan melalui API Plumber, dan dikonfigurasi untuk kontainerisasi.

### Langkah 1: Struktur Kode Paket (`creditEngine/R/score.R`)
```r
#' Menghitung probabilitas gagal bayar berdasarkan rasio finansial
#'
#' @param dti_ratio Numerik, Debt-to-Income ratio (antara 0 hingga 1)
#' @param credit_utilization Numerik, utilisasi limit kredit (antara 0 hingga 1)
#' @return List berisi credit score (0-1000) dan klasifikasi risiko
#' @export
calculate_credit_risk <- function(dti_ratio, credit_utilization) {
  # Validasi input batas pertahanan awal
  if (!is.numeric(dti_ratio) || dti_ratio < 0 || dti_ratio > 1) {
    stop("Argumen 'dti_ratio' harus berupa numerik dalam rentang [0, 1].")
  }
  if (!is.numeric(credit_utilization) || credit_utilization < 0 || credit_utilization > 1) {
    stop("Argumen 'credit_utilization' harus berupa numerik dalam rentang [0, 1].")
  }

  # Formula komputasi deterministik sederhana
  penalty_score <- (dti_ratio * 400) + (credit_utilization * 500)
  base_score <- 1000 - penalty_score
  
  risk_grade <- if (base_score >= 750) {
    "LOW"
  } else if (base_score >= 550) {
    "MEDIUM"
  } else {
    "HIGH"
  }

  list(
    score = as.integer(round(base_score)),
    risk_grade = risk_grade,
    timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
  )
}
```

### Langkah 2: Antarmuka Layanan API (`plumber.R`)
```r
#* @apiTitle Credit Risk Evaluation Engine API
#* @apiDescription Layanan REST API untuk kalkulasi risiko kredit nasabah secara real-time.
#* @apiVersion 1.0.0

#* Parse request JSON body secara otomatis
#* @parser json

#* Evaluasi skor kredit nasabah
#* @post /v1/credit-score
#* @param req Request environment object
#* @serializer json
function(req, res) {
  body <- req$body

  # Validasi payload body eksistensi
  if (is.null(body$dti_ratio) || is.null(body$credit_utilization)) {
    res$status <- 400
    return(list(
      error = "MalformedPayload",
      message = "Atribut 'dti_ratio' dan 'credit_utilization' wajib disertakan."
    ))
  }

  # Panggil domain logic dari paket
  result <- tryCatch(
    {
      calculate_credit_risk(
        dti_ratio = as.numeric(body$dti_ratio),
        credit_utilization = as.numeric(body$credit_utilization)
      )
    },
    error = function(e) {
      res$status <- 422
      list(
        error = "UnprocessableEntity",
        message = e$message
      )
    }
  )

  return(result)
}

#* Healthcheck Probe
#* @get /healthz
#* @serializer json
function(res) {
  res$status <- 200
  list(status = "UP", engine = "R-Plumber-Production")
}
```

### Langkah 3: Script Bootstrapper Headless (`entrypoint.R`)
```r
library(plumber)

port <- as.integer(Sys.getenv("PORT", "8080"))
host <- Sys.getenv("HOST", "0.0.0.0")

pr <- pr("plumber.R")

pr$run(
  host = host,
  port = port,
  swagger = FALSE # Wajib dinonaktifkan di environment produksi untuk keamanan
)
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis `creditEngine/R/score.R`
* **Baris 1–6 (`#' ...`):** Komentar Roxygen2. Direktif `@export` adalah kunci utama yang memerintahkan `roxygen2::roxygenise()` untuk mendaftarkan nama fungsi `calculate_credit_risk` ke dalam file `NAMESPACE`. Tanpa anotasi ini, fungsi tersebut bersifat privat internal dan tidak bisa diakses langsung via `library(creditEngine)`.
* **Baris 8–13:** *Defensive Programming Principle*. Memvalidasi tipe data dan invariant batas komputasi numerik secara eksplisit sebelum menyentuh logika komputasi. Kegagalan validasi langsung memicu error terisolasi via `stop()`.
* **Baris 27:** Memformat timestamp ke format ISO-8601 berzona waktu UTC. Menghindari ambiguasi penafsiran tanggal/waktu pada microservices yang berjalan di berbagai zona server.

### Analisis `plumber.R`
* **Baris 1–3 (`#* @apiTitle ...`):** Anotasi metadata OpenAPI/Swagger. Parser Plumber mengompilasi komentar khusus yang diawali karakter `#*` sebagai registrasi router decorator.
* **Baris 6 (`#* @parser json`):** Menginstruksikan modul parser Plumber untuk memproses HTTP incoming request body yang memiliki header `Content-Type: application/json` menggunakan deserializer internal (biasanya `jsonlite::fromJSON`) dan memuat hasilnya ke objek `req$body`.
* **Baris 9 (`#* @post /v1/credit-score`):** Meregistrasikan verb HTTP POST untuk routing path `/v1/credit-score`.
* **Baris 11 (`#* @serializer json`):** Menginstruksikan Plumber untuk mengalirkan return value fungsi melalui `jsonlite::toJSON()` sebelum di-stream kembali ke HTTP socket response.
* **Baris 24–35 (`tryCatch(...)`):** Mencegah *uncaught exception* membunuh process R. Error dari fungsi paket ditangkap dan ditransformasi menjadi format standard JSON dengan kode status HTTP yang tepat (`422 Unprocessable Entity`), bukan membiarkan server mengembalikan generic crash `500 Internal Server Error`.

### Analisis `entrypoint.R`
* **Baris 3–4 (`Sys.getenv(...)`):** Ekstraksi konfigurasi runtime mengikuti panduan *Twelve-Factor App* (Konfigurasi melalui Environment Variables). Host `0.0.0.0` wajib digunakan di dalam kontainer agar Plumber mendengarkan semua antarmuka jaringan kontainer virtual, bukan hanya `127.0.0.1` (loopback) yang tidak bisa diakses dari luar host kontainer.
* **Baris 10 (`swagger = FALSE`):** Mencegah server merender dokumentasi Swagger UI secara publik pada environment live, mereduksi attack surface profiling arsitektur internal API.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Bisnis & Operasional
Sebuah institusi FinTech multi-nasional mengoperasikan layanan penilaian transaksi fraud (Fraud Detection). Sistem pemrosesan transaksi upstream mengeksekusi rata-rata **400 transaksi per detik (TPS)**. Setiap transaksi wajib divalidasi oleh model fraud berbasis R dalam batasan SLA p99 di bawah **80 milidetik**.

### Permasalahan Arsitektur
1. **Model Script Monolitik:** Tim data science sebelumnya menggunakan script R mandiri yang dimuat via `source("model.R")`. Tidak ada unit test, dan tabrakan versi pustaka sering terjadi saat dependensi global server diperbarui.
2. **Kerapuhan Runtime:** Setiap kali script R mengalami *unhandled error* (misal nilai kolom NA yang tidak terduga), R session mengalami *crash abort*, memutus koneksi HTTP pool pada load balancer.
3. **Waktu Pembangunan Kontainer yang Lambat:** Proses deployment CI/CD memakan waktu 45 menit karena setiap pipeline menjalankan kompilasi source code pustaka R dari CRAN dari awal (*from source*).

### Solusi Rekayasa
1. **Paketisasi Domain Model:** Mengemas logika ekstraksi fitur dan scoring model ke dalam paket R terisolasi: `fraudEngine`. Menulis testing ketat dengan coverage > 90%.
2. **API Resilien via Plumber:** Membangun REST microservice dengan error-handling bertingkat, request-id tracing, dan graceful exception masking.
3. **Pemanfaatan PPM & Docker Multi-Stage:** Menggunakan Posit Public Package Manager binary URL pada Ubuntu 22.04 LTS (Jammy) untuk memangkas waktu build kontainer dari 45 menit menjadi **< 2 menit**.
4. **Isolasi Non-Root & Resource Limits:** Mengamankan kontainer dengan UID non-root 1001 dan deployment resource envelope untuk mencegah OOM (Out Of Memory) killer mematikan host server node.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

### 1. Struktur Modul Paket `fraudEngine`
File `fraudEngine/DESCRIPTION`:
```dcf
Package: fraudEngine
Title: Real-time Transaction Fraud Evaluation Engine
Version: 1.2.0
Authors@R: person("Systems", "Engineering", email = "syseng@fintech.internal", role = c("aut", "cre"))
Description: Production scoring module for enterprise real-time transaction streams.
Depends: R (>= 4.3.0)
Imports:
    checkmate (>= 2.2.0),
    jsonlite (>= 1.8.7)
Suggests:
    testthat (>= 3.1.0)
License: Proprietary
Encoding: UTF-8
RoxygenNote: 7.2.3
```

File `fraudEngine/R/detector.R`:
```r
#' Evaluasi Transaksi Finansial terhadap Pola Anomali
#'
#' @param transaction_id Karakter unik penanda transaksi.
#' @param amount Numerik nilai transaksi (harus positif).
#' @param velocity_1h Integer frekuensi transaksi user dalam 1 jam terakhir.
#' @param is_foreign Integer/Boolean (0 atau 1) indikator transaksi luar negeri.
#' @return List berisi fraud probability score dan rekomendasi aksi.
#' @importFrom checkmate assert_string assert_number assert_int
#' @export
evaluate_transaction <- function(transaction_id, amount, velocity_1h, is_foreign) {
  # Validasi input berkinerja tinggi menggunakan C-level checks dari package checkmate
  checkmate::assert_string(transaction_id, min.chars = 5)
  checkmate::assert_number(amount, lower = 0.01)
  checkmate::assert_int(velocity_1h, lower = 0)
  checkmate::assert_int(is_foreign, lower = 0, upper = 1)

  # Bobot model linier sederhana (representasi model komputasi inferensi)
  intercept <- -4.5
  weight_amount <- 0.0003
  weight_velocity <- 0.35
  weight_foreign <- 1.8

  z <- intercept + 
       (amount * weight_amount) + 
       (velocity_1h * weight_velocity) + 
       (is_foreign * weight_foreign)
  
  # Fungsi logistik: 1 / (1 + e^-z)
  probability <- 1 / (1 + exp(-z))
  
  action <- if (probability >= 0.85) {
    "BLOCK"
  } else if (probability >= 0.50) {
    "MANUAL_REVIEW"
  } else {
    "APPROVE"
  }

  list(
    transaction_id = transaction_id,
    fraud_probability = round(probability, 4),
    recommended_action = action,
    evaluated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
  )
}
```

File `fraudEngine/tests/testthat/test-detector.R`:
```r
testthat::test_that("Evaluasi transaksi valid mengembalikan output dengan skema yang benar", {
  res <- evaluate_transaction(
    transaction_id = "TX-998877",
    amount = 1500.50,
    velocity_1h = 2,
    is_foreign = 1
  )
  
  testthat::expect_type(res, "list")
  testthat::expect_equal(res$transaction_id, "TX-998877")
  testthat::expect_true(res$fraud_probability >= 0 && res$fraud_probability <= 1)
  testthat::expect_true(res$recommended_action %in% c("APPROVE", "MANUAL_REVIEW", "BLOCK"))
})

testthat::test_that("Detektor menolak input non-valid secara deterministik", {
  testthat::expect_error(
    evaluate_transaction("TX-1", -10, 2, 0),
    regexp = "Element 1 is not >= 0.01"
  )
  testthat::expect_error(
    evaluate_transaction(12345, 100, 2, 0),
    regexp = "Must be of type 'string'"
  )
})
```

### 2. Implementasi API Plumber Produksi (`server/plumber.R`)
```r
library(plumber)
library(fraudEngine)

# Setup filter: Global Error Handling, Request Auditing, & Correlation ID
#* @filter request_trace
function(req, res) {
  req$request_id <- req$HTTP_X_CORRELATION_ID
  if (is.null(req$request_id) || req$request_id == "") {
    req$request_id <- paste0("req-", as.numeric(Sys.time()) * 1000)
  }
  
  start_time <- Sys.time()
  
  # Lanjutkan ke filter/endpoint berikutnya
  forward()
  
  end_time <- Sys.time()
  duration_ms <- as.numeric(difftime(end_time, start_time, units = "secs")) * 1000
  
  # Structured Logging via stdout (akan ditangkap oleh Docker log forwarder)
  log_entry <- list(
    request_id = req$request_id,
    method = req$REQUEST_METHOD,
    path = req$PATH_INFO,
    status = res$status,
    latency_ms = round(duration_ms, 2),
    client_ip = req$REMOTE_ADDR,
    timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
  )
  cat(jsonlite::toJSON(log_entry, auto_unbox = TRUE), "\n", file = stdout())
}

#* Evaluasi risiko anomali transaksi finansial
#* @post /api/v1/fraud/evaluate
#* @parser json
#* @serializer json
function(req, res) {
  payload <- req$body

  # Guard statement payload checking
  if (!is.list(payload) || is.null(payload$transaction_id)) {
    res$status <- 400
    return(list(
      error = "BadRequest",
      request_id = req$request_id,
      message = "Payload body kosong atau format invalid. Diperlukan JSON object."
    ))
  }

  # Eksekusi scoring dengan isolasi safe handler
  eval_result <- tryCatch(
    {
      fraudEngine::evaluate_transaction(
        transaction_id = as.character(payload$transaction_id),
        amount = as.numeric(payload$amount),
        velocity_1h = as.integer(payload$velocity_1h),
        is_foreign = as.integer(payload$is_foreign)
      )
    },
    error = function(err) {
      res$status <- 422
      list(
        error = "UnprocessableValidation",
        request_id = req$request_id,
        message = err$message
      )
    }
  )

  return(eval_result)
}

#* Liveness Probe untuk Kubernetes / AWS ECS
#* @get /healthz
#* @serializer json
function(res) {
  res$status <- 200
  list(status = "healthy")
}
```

### 3. File Dockerfile Produksi Multi-Stage (`Dockerfile`)
```dockerfile
# ====================================================================
# STAGE 1: Dependency Builder & Package Compiler
# ====================================================================
FROM rocker/r-ver:4.3.2 AS builder

# Hindari interaktivitas debian frontend
ENV DEBIAN_FRONTEND=noninteractive

# Update repository dan install build-tools sistem native
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Konfigurasi repositori Posit Package Manager (Ubuntu 22.04 LTS binary mirror)
RUN echo 'options(repos = c(PPM = "https://packagemanager.posit.co/cran/__linux__/jammy/latest"))' >> /usr/local/lib/R/etc/Rprofile.site

# Buat direktori staging dependensi
WORKDIR /build

# Salin definisi lockfile dependensi renv
COPY renv.lock ./
ENV RENV_VERSION=1.0.3
RUN R -e "install.packages('remotes'); remotes::install_version('renv', version = Sys.getenv('RENV_VERSION'))"
RUN R -e "renv::restore()"

# Salin dan install modul internal paket fraudEngine
COPY fraudEngine/ /build/fraudEngine/
RUN R CMD INSTALL --build /build/fraudEngine/

# ====================================================================
# STAGE 2: Lightweight Minimal Production Runtime
# ====================================================================
FROM rocker/r-ver:4.3.2-slim AS runtime

# Install hanya shared libraries yang diperlukan saat runtime
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4 \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Setup user non-privileged untuk kepatuhan Least Privilege (Security)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Ambil pustaka yang sudah dikompilasi dari STAGE 1
COPY --from=builder /usr/local/lib/R/site-library /usr/local/lib/R/site-library

# Salin kode API server
COPY server/ /app/

# Alihkan kepemilikan direktori kerja ke appuser
RUN chown -R appuser:appgroup /app

# Switch user ke non-root
USER appuser

# Expose port HTTP daemon
EXPOSE 8080

ENV PORT=8080
ENV HOST=0.0.0.0

# Konfigurasi Healthcheck OCI
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1

# Eksekusi entrypoint menggunakan exec form (mengirimkan sinyal POSIX langsung ke R)
ENTRYPOINT ["Rscript", "/app/plumber.R"]
```

### 4. Konfigurasi Deployment Orkestrasi (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  fraud-detection-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: fraud_engine_api
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - HOST=0.0.0.0
      - R_CONFIG_ACTIVE=production
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1024M
        reservations:
          cpus: '0.5'
          memory: 256M
    restart: on-failure
    security_opt:
      - no-new-privileges:true
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Tabel 1: Kerangka Kerja REST API di Ekosistem R

| Parameter Perbandingan | `plumber` | `RestRserve` | `FastRWeb` |
| :--- | :--- | :--- | :--- |
| **Model Arsitektur** | Decorator annotations berbasis `httpuv` | High-performance C++ backend (`Rserve`) | Direct Web Server CGI/Rserve |
| **Throughput (RPS)** | Rendah–Sedang (~800–2.000 TPS) | Ekstrem Tinggi (> 10.000 TPS) | Sedang |
| **Kurva Belajar** | Sangat Rendah (Intuitif, mirip FastAPI) | Sedang (Perlu pemahaman socket & C) | Tinggi (Arsitektur legacy) |
| **Dokumentasi OpenAPI**| Native & Terintegrasi Otomatis | Perlu konfigurasi manual | Tidak Didukung |
| **Dukungan Asinkron** | Native via `promises`/`future` | Mendukung multiprocess via forks | Terbatas |
| **Rekomendasi Penggunaan**| Standar microservice umum | Layanan ultra-low latency & throughput masif | Legacy interop maintenance |

### Tabel 2: Strategi Manajemen Dependensi di Docker

| Kriteria Evaluasi | Manual `install.packages()` | `renv` Snapshot Lock | Sistem Native (Nix / Conda) |
| :--- | :--- | :--- | :--- |
| **Determinisme** | Sangat Buruk (versi dapat berubah) | Sangat Tinggi (kunci versi & hash) | Tertinggi (immutable store) |
| **Kecepatan Build** | Cepat jika binary, lambat jika source | Sangat Cepat (dengan binary PPM) | Sedang hingga Cepat |
| **Ukuran Image** | Bervariasi | Terkontrol | Cenderung Besar (Conda) |
| **Kompleksitas CI** | Rendah | Rendah (cukup file `renv.lock`) | Tinggi (DSL terpisah) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Bottleneck Single-Threaded Event Loop
* **Skenario:** Salah satu endpoint API Anda mengeksekusi iterasi algoritma MCMC (*Markov Chain Monte Carlo*) yang memakan waktu 15 detik.
* **Dampak:** Seluruh request dari client lain—termasuk request monitoring `/healthz` dari load balancer—akan mengalami *freeze* total (terantre). Load balancer menganggap container *unresponsive* dan membunuh kontainer secara prematur.
* **Mitigasi:** Delegasikan tugas komputasi berat ke worker asinkron menggunakan abstraksi `promises`:
```r
#* @get /compute-heavy
function() {
  promises::future_promise({
    # Komputasi berat terisolasi di background process R terpisah
    heavy_statistical_model()
  })
}
```

### 2. Akumulasi Memori dari Copy-on-Write (CoW)
* **Skenario:** Mengirim dataframe besar ke beberapa fungsi internal di dalam endpoint yang memodifikasi atribut data secara lokal.
* **Dampak:** R menduplikasi objek di memori (*shallow/deep copy* akibat semantik Copy-on-Write). Jika kontainer memiliki batasan memori ketat (misal 512MB), sistem operasi Linux akan memicu sinyal `SIGKILL` melalui **OOM (Out Of Memory) Killer**.
* **Mitigasi:** Bersihkan objek intermediate besar secara eksplisit via `rm(big_data); gc(verbose = FALSE)` atau gunakan pustaka data *in-place modification* seperti `data.table` atau struktur pointer C++ via `R6`.

### 3. Masalah Sinyal PID 1 (The PID 1 Zombie Reaping Problem)
* **Skenario:** Menjalankan script R langsung menggunakan perintah `CMD Rscript entrypoint.R` atau via perantara script shell tanpa meneruskan sinyal POSIX.
* **Dampak:** Proses R menjadi PID 1 di dalam namespace kontainer. R engine secara native **tidak dirancang** untuk bertindak sebagai *init process*. R tidak akan membersihkan *zombie child processes* (jika menggunakan multi-threading fork) dan mengabaikan sinyal `SIGTERM` saat stop container, menyebabkan data loss.
* **Mitigasi:** Gunakan *lightweight init system* seperti `tini` di dalam Dockerfile jika menggunakan sub-proses kompleks:
```dockerfile
RUN apt-get update && apt-get install -y tini
ENTRYPOINT ["/usr/bin/tini", "--", "Rscript", "entrypoint.R"]
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Polusi Namespace dengan `library()` di Dalam Skrip Paket
* **Kesalahan Fatal:** Menuliskan `library(dplyr)` atau `require(jsonlite)` di dalam file `.R` yang berada di direktori `R/` suatu paket.
* **Konsekuensi:** `R CMD check` akan gagal dengan status *Error/Warning*. Memanggil `library()` memodifikasi search-path global seluruh sesi R runtime, menimpa fungsi dengan nama yang sama (*function masking*).
* **Solusi Benar:** Cantumkan dependensi di bagian `Imports:` pada file `DESCRIPTION`, dan gunakan format `package::function()` atau direktif Roxygen `#' @importFrom package function`.

### 2. Mengandalkan `setwd()` dan Dynamic Path Relatif
* **Kesalahan Fatal:** Menulis `setwd("/home/user/api")` atau membaca data via `read.csv("../../data.csv")`.
* **Konsekuensi:** Path absolut membuat kontainer portabel hancur seketika saat di-mount ke path host yang berbeda.
* **Solusi Benar:** Ambil file aset paket menggunakan fungsi sistem `system.file("extdata", "model.rds", package = "fraudEngine")`.

### 3. Injeksi Ekspresi Dinamis Tanpa Sanitasi
* **Kesalahan Fatal:** Membaca payload string JSON lalu mengevaluasinya via `eval(parse(text = payload$query))`.
* **Konsekuensi:** **Remote Code Execution (RCE)**. Penyerang dapat mengirimkan payload string `system("rm -rf /")` yang akan dieksekusi secara native oleh R interpreter.
* **Solusi Benar:** Lakukan parsing hanya menggunakan deserializer skalar tipe data ketat, dan jangan pernah menggunakan `eval(parse())` untuk input dari antarmuka luar.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Paket R sebagai *Single Source of Truth*:**
   * Jangan meletakkan logika analitik di dalam file skrip routing `plumber.R`. Seluruh model, transformer, utilitas sanitasi, dan algoritma **wajib** dipaketkan ke dalam modul R ber-namespace yang lulus pengujian `R CMD check --no-manual --as-cran`.
2. **Kepatuhan Terhadap Semantic Versioning (SemVer):**
   * Gunakan pola `MAJOR.MINOR.PATCH` pada file `DESCRIPTION`.
   * Naikkan `MAJOR` untuk perubahan *breaking change* pada payload API/kontrak fungsi.
   * Naikkan `MINOR` untuk penambahan fitur backwards-compatible.
   * Naikkan `PATCH` untuk perbaikan bug fixing internal.
3. **Penyusutan Image Docker Menggunakan Binary Mirror:**
   * Selalu prioritaskan Posit Package Manager (PPM) Linux binary URLs pada file `/etc/Rprofile.site`. Pemasangan binary memangkas waktu build di pipeline CI/CD hingga 95% dibanding kompilasi source native.
4. **Isolasi Izin (Non-Root User Enforcement):**
   * Default Docker berjalan sebagai user `root`. Dalam sistem produksi enterprise (misal: OpenShift, PCI-DSS compliance), kontainer yang berjalan sebagai `root` langsung ditolak oleh security admission controller. Buat dan alihkan pengguna ke user non-root (UID >= 1000).

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Serializer Optimization: `jsonify` vs `jsonlite`
Secara default, Plumber menggunakan `jsonlite::toJSON` untuk serialisasi data return. Untuk volume payload data tabular besar (ribuan baris), `jsonlite` mengalami bottleneck overhead konversi S3-class. Gunakan package C++ murni `jsonify` untuk meningkatkan throughput serialisasi hingga 3x lipat:
```r
#* @serializer custom
function(val, req, res, errorHandler) {
  res$setHeader("Content-Type", "application/json")
  res$body <- jsonify::to_json(val, unbox = TRUE)
  return(res$toResponse())
}
```

### 2. Multi-Worker Concurrency Menggunakan Reverse Proxy
Karena Plumber berjalan single-process per instance, jangan mencoba membuat multi-thread internal di dalam single memory session untuk request handling. 
Pola produksi standar industri adalah **skala horizontal**:
* Jalankan beberapa instans kontainer R Plumber (misal: 4 kontainer pada satu host node).
* Letakkan Reverse Proxy (seperti NGINX, Envoy, atau HAProxy) di depan kontainer untuk membagi beban transaksi menggunakan algoritma *Round Robin* atau *Least Connections*.

```
                ┌─────────────────────────────────┐
                │          NGINX Ingress          │
                └───────┬────────┬────────┬───────┘
                        │        │        │
           ┌────────────┘        │        └────────────┐
           ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Plumber Pod #1   │  │ Plumber Pod #2   │  │ Plumber Pod #3   │
│ (Port 8080)      │  │ (Port 8080)      │  │ (Port 8080)      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Proteksi Terhadap Denial of Service (Payload Size Limiter)
Server `httpuv` secara default dapat menerima request payload besar yang berisiko menghabiskan memori kontainer. Batasi ukuran HTTP body di awal inisialisasi Plumber:
```r
# Batasi parsing payload maksimal 2 Megabytes (2 * 1024 * 1024 bytes)
options(httpuv.maxRequestSize = 2097152)
```

### 2. Hardening Image Container (Read-Only Root Filesystem)
Dalam cluster Kubernetes produksi yang ketat, kontainer harus mampu berjalan di bawah konfigurasi `readOnlyRootFilesystem: true`. 
Pastikan R hanya menulis data cache/temporary ke direktori `/tmp` yang di-mount sebagai `emptyDir`:
```dockerfile
# Di dalam Dockerfile
ENV TMPDIR=/tmp
```

### 3. Pembersihan Informasi Header Server (*Information Disclosure*)
Secara default, response web server menyertakan header signature yang membocorkan teknologi backend. Hapus atau manipulasi header signature ini di layer filter:
```r
#* @filter strip_headers
function(res) {
  forward()
  res$setHeader("Server", "Protected-API")
  res$setHeader("X-Powered-By", "Enterprise-Engine")
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Di lingkungan produksi tanpa akses interaktif console, log yang dihasilkan oleh aplikasi R harus dapat diparsing oleh log aggregator modern (seperti FluentBit, Datadog, ELK Stack, Grafana Loki).

### Structured JSON Logger Implementation
Gunakan library `logger` dengan format JSON serializer, atau cetak baris tunggal JSON langsung ke output descriptor stream `file = stdout()`:

```r
log_event <- function(level = "INFO", message, request_id = NULL, ...) {
  payload <- list(
    timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
    level = level,
    request_id = request_id,
    message = message,
    context = list(...)
  )
  # Unbox untuk skalar primitive agar JSON rapi
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE), "\n", file = stdout())
}

# Contoh Pemanggilan
log_event(
  level = "WARN", 
  message = "Anomali skor transaksi terdeteksi tinggi",
  request_id = "req-171092812",
  transaction_id = "TX-8821",
  risk_score = 0.94
)
```

Output pada Docker Standard Output:
```json
{"timestamp":"2024-03-20T09:30:00Z","level":"WARN","request_id":"req-171092812","message":"Anomali skor transaksi terdeteksi tinggi","context":{"transaction_id":"TX-8821","risk_score":0.94}}
```

### Health Check Standard: Tiga Serangkai Probes
Implementasikan endpoint observabilitas terpisah untuk cluster manager:
1. **`/livez` (Liveness):** Memverifikasi apakah event loop R masih bernafas. Jika endpoint ini mengembalikan response != 200, kubernetes akan me-restart kontainer.
2. **`/readyz` (Readiness):** Memverifikasi apakah dependensi internal (seperti koneksi database, model file `.rds` yang dimuat di memori) siap melayani traffic request.
3. **`/metrics`:** Mengekspos counter metrik kinerja aplikasi (dapat diintegrasikan dengan paket `openmetrics`).

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Komando CLI Package Engineering
```bash
# Inisialisasi kerangka paket baru
R -e "usethis::create_package('namaPaket')"

# Sinkronisasi dokumentasi Roxygen2 ke NAMESPACE & man/
R -e "devtools::document()"

# Menjalankan seluruh test unit secara lokal
R -e "devtools::test()"

# Validasi standar kualitas integritas ketat R
R CMD build .
R CMD check --as-cran --no-manual namaPaket_*.tar.gz
```

### 2. Komando Manajemen Dependensi `renv`
```bash
# Inisialisasi environment renv terisolasi pada proyek
R -e "renv::init()"

# Simpan snapshot dependensi terkini ke renv.lock
R -e "renv::snapshot()"

# Pulihkan dependensi secara deterministik dari renv.lock
R -e "renv::restore()"
```

### 3. Komando Build & Test Kontainer Docker
```bash
# Build image dengan tag nama dan versi
docker build -t fintech/fraud-engine:1.2.0 .

# Jalankan container dengan limitasi memori dan mapping port
docker run -d --rm \
  --name fraud_api \
  -p 8080:8080 \
  --memory="512m" \
  --cpus="1.0" \
  fintech/fraud-engine:1.2.0

# Verifikasi status healthcheck
docker inspect --format='{{json .State.Health}}' fraud_api | jq
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Apa fungsi utama file `NAMESPACE` pada sebuah paket R berstandar produksi?**
   * A. Menyimpan variabel global dan API token secara aman.
   * B. Mengatur isolasi fungsi mana yang diimpor dari paket lain dan fungsi mana yang diekspos ke publik.
   * C. Mendefinisikan port HTTP yang akan dibuka oleh microservice.
   * D. Mengontrol alokasi memori RAM untuk interpreter R.
   * *Jawaban:* **B**. `NAMESPACE` bertindak sebagai *gatekeeper* enkapsulasi: mencegah tabrakan nama (*name masking*) dan mengontrol visibilitas antarmuka fungsi paket.

2. **Mengapa pemanggilan fungsi `library(package)` dilarang di dalam kode paket R?**
   * A. Karena library() tidak didukung pada sistem operasi Linux.
   * B. Karena memperlambat kompilasi Dockerfile.
   * C. Karena memodifikasi global search path sesi R, menyebabkan efek samping polusi lingkungan eksekusi secara global.
   * D. Karena fungsinya otomatis dihapus oleh roxygen2.
   * *Jawaban:* **C**. Di dalam paket, dependensi harus dideklarasikan di `DESCRIPTION` dan diimpor secara modular melalui `NAMESPACE` untuk menghindari efek polusi global search path.

3. **Anotasi Plumber manakah yang digunakan untuk menangani request masuk dengan metode POST pada rute `/predict`?**
   * A. `#* @get /predict`
   * B. `#* @endpoint POST /predict`
   * C. `#* @post /predict`
   * D. `#* @action /predict:post`
   * *Jawaban:* **C**. Plumber memetakan decorator verb HTTP secara langsung via `#* @<http_method> <path>`.

4. **Mengapa penggunaan host `127.0.0.1` di dalam container Docker membuat API tidak dapat diakses dari host luar?**
   * A. Karena `127.0.0.1` adalah port, bukan alamat IP.
   * B. Karena `127.0.0.1` hanya merujuk pada antarmuka loopback internal di dalam namespace kontainer lokal itu sendiri.
   * C. Karena docker engine otomatis memblokir koneksi port 80.
   * D. Karena Plumber hanya mendukung protokol IPv6.
   * *Jawaban:* **B**. Di dalam kontainer, proses harus di-bind ke alamat `0.0.0.0` (semua antarmuka jaringan kontainer) agar lalu lintas bridge Docker dapat diteruskan dengan benar.

5. **Apa fungsi utama file `renv.lock` dalam alur kerja rekayasa produksi?**
   * A. Mengenkripsi kode sumber R agar tidak bisa dibaca oleh pihak ketiga.
   * B. Mengunci versi, sumber repositori, dan checksum dependensi paket secara deterministik.
   * C. Mengatur batas memori maksimum yang boleh digunakan R runtime.
   * D. Menyimpan riwayat perubahan commit Git secara otomatis.
   * *Jawaban:* **B**. `renv.lock` adalah manifest metadata JSON deklaratif yang menjamin bahwa environment komputasi di-restore pada kondisi paket yang identik secara biner.

---

### Soal Intermediate & Advanced (6–10)

6. **Bagaimana karakteristik eksekusi single-threaded pada R mempengaruhi Plumber ketika menangani endpoint komputasi panjang?**
   * A. Permintaan lain akan dieksekusi di core CPU lain secara otomatis oleh runtime base R.
   * B. R akan langsung melempar error HTTP 503 Service Unavailable.
   * C. Seluruh permintaan HTTP berikutnya akan tertahan dalam blocking queue hingga komputasi pertama tuntas, memicu risiko timeout pada load balancer.
   * D. Plumber otomatis melakukan fork proses baru untuk setiap request yang masuk.
   * *Jawaban:* **C**. Karena event loop R bersifat single-threaded, komputasi sinkron yang panjang akan memblokir thread R utama dari memproses request lain, menghentikan penanganan socket HTTP.

7. **Mengapa penggunaan Posit Public Package Manager (PPM) Linux binary URLs sangat direkomendasikan pada tahapan build Docker daripada CRAN standar?**
   * A. Karena PPM menyediakan paket gratis sedangkan CRAN berbayar.
   * B. Karena PPM mendistribusikan pustaka C/C++ yang sudah dikompilasi secara biner untuk distro Linux target, memangkas waktu instalasi secara masif tanpa memicu gcc compilation.
   * C. Karena PPM tidak membutuhkan deklarasi file DESCRIPTION.
   * D. Karena CRAN tidak kompatibel dengan Docker.
   * *Jawaban:* **B**. Di Linux, CRAN default hanya menyediakan source code `.tar.gz` yang mewajibkan kompilasi native C/C++/Fortran saat build Docker. PPM menyediakan pre-built binaries untuk distro seperti Ubuntu Jammy, menghemat waktu build secara signifikan.

8. **Manakah dari pernyataan berikut yang paling tepat mengenai penanganan sinyal POSIX `SIGTERM` oleh Docker pada proses R?**
   * A. R secara native menangani semua sinyal shutdown tanpa konfigurasi tambahan.
   * B. Jika container dijalankan menggunakan wrapper shell script tanpa `exec`, sinyal `SIGTERM` akan ditelan oleh shell, menyebabkan proses R dimatikan paksa via `SIGKILL` setelah grace period timeout.
   * C. Docker tidak pernah mengirimkan sinyal `SIGTERM` ke kontainer Linux.
   * D. Plumber secara otomatis menghentikan kontainer ketika idle selama 5 menit.
   * *Jawaban:* **B**. Shell yang bertindak sebagai PID 1 tanpa meneruskan sinyal akan mengabaikan `SIGTERM`, menghalangi proses R di bawahnya untuk menjalankan *graceful connection cleanup*.

9. **Apa manfaat arsitektur mengimplementasikan pola Docker multi-stage build untuk aplikasi R Plumber?**
   * A. Memungkinkan kontainer menjalankan dua interpreter R sekaligus dalam satu pod.
   * B. Memisahkan toolchain kompilasi sistem (gcc, make, header files dev) di builder stage dari runtime stage, menghasilkan ukuran image final yang jauh lebih ramping dan aman.
   * C. Meningkatkan batas memori RAM heap R secara otomatis.
   * D. Mengeliminasi kebutuhan file `renv.lock`.
   * *Jawaban:* **B**. Multi-stage build mengisolasi dependensi build-time (compiler, dev libraries) dan hanya menyalin artefak biner hasil instalasi ke runtime image minimal, memperkecil attack surface dan ukuran image.

10. **Dalam konteks hardening keamanan microservice R di lingkungan Kubernetes, mengapa container harus dikonfigurasi dengan user non-root (misal: `USER 1001`)?**
    * A. Karena interpreter R menolak mengeksekusi kalkulasi numerik jika dijalankan sebagai user root.
    * B. Membatasi dampak keamanan jika terjadi eksploitasi Container Escape/RCE, sehingga penyerang tidak langsung mendapatkan kendali root host system.
    * C. Untuk mempercepat waktu pembacaan file permission di dalam storage pod.
    * D. Memastikan Plumber dapat membaca file `/etc/shadow`.
    * *Jawaban:* **B**. Prinsip *Least Privilege* menegaskan bahwa proses tidak boleh berjalan dengan hak akses root jika tidak diperlukan. Ini memperkecil eskalasi hak akses pada skenario eksploitasi keamanan atau *container breakout*.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Tantangan
Anda ditugaskan oleh Lead Infrastructure Architect untuk membangun microservice **"Dynamic Pricing Engine"** yang siap dideploy ke cluster produksi. Layanan ini harus menghitung penyesuaian harga tiket pesawat berdasarkan elastisitas permintaan dan kapasitas kursi yang tersisa.

### Spesifikasi Kebutuhan Proyek

#### 1. Komponen Paket R (`pricingEngine`)
* Buat paket R baru bernama `pricingEngine`.
* Implementasikan fungsi inti:
  $$\text{adjusted\_price} = \text{base\_price} \times \left(1 + \frac{\text{demand\_factor}}{\text{seats\_left}}\right)$$
* Input parameter:
  * `base_price` (numerik > 0)
  * `demand_factor` (numerik, rentang 0.0 hingga 2.0)
  * `seats_left` (integer, minimal 1)
* Tulis minimal **3 unit test** menggunakan `testthat` untuk memverifikasi validitas komputasi, proteksi division-by-zero, dan tipe data argument.

#### 2. Komponen API Plumber (`plumber.R`)
* Implementasikan filter audit logging berformat JSON yang mencetak `request_id`, `path`, `execution_time_ms`, dan `status`.
* Endpoint POST: `/api/v1/pricing/calculate`
  * Serializer: JSON.
  * Lakukan validasi input payload JSON. Kembalikan kode status HTTP 400 jika atribut payload tidak lengkap.
* Endpoint GET: `/healthz` (mengembalikan status UP).

#### 3. Komponen Kontainerisasi & Hardening
* Tulis `Dockerfile` yang:
  * Menggunakan base image `rocker/r-ver:4.3.2`.
  * Mengatur mirror Posit PPM untuk instalasi dependensi Linux binary secara deterministik.
  * Menginstal paket internal `pricingEngine` dari source lokal.
  * Menjalankan daemon di bawah user non-privileged `appuser` (UID: 1001).
  * Menyediakan instruksi `HEALTHCHECK`.

### Acceptance Criteria & Panduan Pengujian

1. **Pengujian Integritas Paket:**
   ```bash
   R -e "devtools::check(pkg = 'pricingEngine', error_on = 'warning')"
   # Output harus: 0 errors | 0 warnings | 0 notes
   ```

2. **Pengujian Fungsionalitas API via cURL:**
   ```bash
   # Jalankan kontainer
   docker build -t pricing-engine:1.0.0 .
   docker run -d -p 8080:8080 --name test_pricing pricing-engine:1.0.0

   # Test Healthcheck Probe
   curl -i -X GET http://localhost:8080/healthz
   # Respon yang diharapkan: HTTP/1.1 200 OK

   # Test Pricing Calculation Endpoint (Valid)
   curl -i -X POST http://localhost:8080/api/v1/pricing/calculate \
     -H "Content-Type: application/json" \
     -d '{"base_price": 500000, "demand_factor": 1.2, "seats_left": 10}'
   # Respon yang diharapkan: HTTP/1.1 200 OK dengan payload JSON kalkulasi akurat

   # Test Sanitasi Input (Invalid Argument)
   curl -i -X POST http://localhost:8080/api/v1/pricing/calculate \
     -H "Content-Type: application/json" \
     -d '{"base_price": -100, "demand_factor": 1.2, "seats_left": 0}'
   # Respon yang diharapkan: HTTP/1.1 400 atau 422 dengan pesan error deskriptif
   ```

3. **Verifikasi Keamanan User Non-Root:**
   ```bash
   docker exec test_pricing whoami
   # Output HARUS menampilkan: appuser (Bukan root!)
   ```