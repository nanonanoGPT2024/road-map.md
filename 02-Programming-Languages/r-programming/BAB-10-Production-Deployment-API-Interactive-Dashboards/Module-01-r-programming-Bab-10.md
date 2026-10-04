# Bab 10: Production Engineering & API Deployment in R
## Module 01: Arsitektur REST API Skala Produksi dengan Plumber dan Asynchronous Execution

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang, membangun, dan mengonfigurasi REST API berbasis R menggunakan paket `plumber` dengan pemisahan *layer* arsitektur yang bersih.
- Mengatasi limitasi *single-threaded runtime* R menggunakan pola *asynchronous execution* melalui integrasi `promises` dan `future`.
- Mengimplementasikan *middleware pipeline* (filter), validasi skema payload, *structured logging*, dan manajemen *lifecycle error* standar HTTP.
- Mengoptimalkan konkurensi dan utilisasi memori API untuk beban kerja komputasi/prediksi analitik pada infrastruktur *containerized*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **R Functional Programming**: Pemahaman mendalam tentang *closures*, *first-class functions*, dan *environments*.
- **Protokol HTTP/1.1**: Status code, metode request (`GET`, `POST`, `PUT`, `DELETE`), headers, MIME types, serta parsing JSON.
- **Konkurensi Dasar**: Perbedaan *process-based concurrency* (forking/multisession) vs *thread-based concurrency*, serta konsep *non-blocking I/O*.
- **Package Management & Tooling**: Penggunaan R 4.x, paket `remotes`/`renv`, dan pengujian berbasis `curl` atau Postman.

---

### 3. Concept
R secara fundamental beroperasi di atas arsitektur *single-threaded execution model*. Artinya, R Runtime hanya memiliki satu *call stack* dan satu *memory heap* aktif per proses. Ketika R mengeksekusi perhitungan matriks intensif atau *scoring model* Machine Learning, proses R akan mengalami *blocking*; tidak ada instruksi lain yang dapat dieksekusi sampai evaluasi tersebut selesai.

Paket `plumber` dibangun di atas `httpuv`, sebuah HTTP server terintegrasi berbasis library C++ `libuv` (komponen inti yang juga mentenagai asynchronous I/O pada Node.js). `httpuv` mengelola *event loop* dan abstraksi socket TCP non-blocking. Namun, begitu HTTP request dialihkan dari C++ layer ke evaluasi R code oleh Plumber router, eksekusi masuk kembali ke lingkungan R *single-threaded*. 

Jika API menerima request komputasi berat, seluruh *incoming request* berikutnya akan mengantre di socket queue hingga thread utama R terbebas. Solusi arsitektural untuk masalah ini adalah mendistribusikan beban komputasi keluar dari *main event loop thread* ke *background worker processes* menggunakan abstraksi `promises` dan `future`. 

Dengan decoupling ini, *main thread* hanya berfungsi sebagai router I/O yang menerima HTTP request, mendelegasikan eksekusi payload ke worker pool via inter-process communication (IPC), mengembalikan Promise, dan segera siap melayani request berikutnya.

---

### 4. Why
Dalam siklus hidup Data Science modern, model Machine Learning yang ditulis dalam R sering kali harus diintegrasikan ke dalam ekosistem *microservices* perusahaan (misalnya backend Go, Java, atau Node.js). 

Menerapkan Plumber secara naif (tanpa konfigurasi asinkronus dan manajemen konkurensi) pada lingkungan produksi sering memicu kegagalan sistemik:
1. **Thread Starvation**: Satu request analitik kompleks yang memakan waktu 3 detik akan membuat ratusan request health-check atau request ringan lainnya mengalami *connection timeout*.
2. **Memory Leaks**: Eksekusi fungsi R berulang pada *global environment* tanpa isolasi ruang lingkup (*scoping*) menyebabkan retensi objek memori yang tak terduplikasi oleh *garbage collector* R.
3. **Unchecked Exceptions**: Error runtime R yang tidak tertangkap oleh filter kustom akan merusak HTTP session atau membocorkan stack trace internal ke konsumen API, melanggar standar kepatuhan keamanan (*information disclosure*).

Menguasai arsitektur Plumber skala produksi memastikan model R Anda dapat dideploy sebagai layanan web mikro yang deterministik, berlatensi rendah, toleran terhadap kegagalan, dan siap diorkestrasi via Kubernetes atau Docker Swarm.

---

### 5. What
Komponen inti dalam ekosistem produksi Plumber meliputi:

- **Plumber Router**: Mesin routing yang memetakan pola URI dan HTTP verbs ke fungsi R menggunakan anotasi komentar khusus (`#* @get`, `#* @post`).
- **Filters (Middleware)**: Interseptor siklus hidup request yang mengeksekusi logika validasi token autentikasi, rate limiting, request-id injection, dan logging sebelum mencapai endpoint target.
- **Serializers**: Komponen konversi objek R internal (list, data.frame, vector) menjadi representasi teks/biner HTTP (seperti JSON via `jsonlite`, feather, RDS, atau biner image PNG).
- **Asynchronous Execution Stack (`promises` + `future`)**: 
  - `future`: Driver eksekusi paralel yang mengabstraksi spawning R session baru (`multisession`) atau worker eksternal.
  - `promises`: Pola representasi nilai masa depan (*deferred computation*) yang memungkinkan `httpuv` menangguhkan respon HTTP tanpa memblokir event loop.
- **Error Boundaries**: Handler global untuk menangani `warning` dan `error` kondisi R, memetakannya secara konsisten ke RFC 7807 Problem Details atau standar JSON API.

---

### 6. How
Alur pemrosesan request dalam arsitektur Plumber Asinkronus:

1. **Ingress**: Klien mengirimkan HTTP POST request berisi payload JSON.
2. **Socket Layer**: C++ `httpuv` membaca byte stream dari kernel socket buffer, mem-parsing HTTP headers, dan memicu event `onHeaders`/`onBody`.
3. **Filter Pipeline**: 
   - Filter `cors`: Menambahkan header CORS yang diizinkan.
   - Filter `logger`: Membuat UUID unik (`X-Request-ID`) dan mencatat waktu kedatangan.
   - Filter `validator`: Memvalidasi payload JSON terhadap skema menggunakan schema validator.
4. **Endpoint Router**: Router memetakan URI ke handler yang membungkus komputasi dalam fungsi `future_promise()`.
5. **Worker Delegation**: Evaluasi dialihkan ke proses R worker terpisah di dalam *future plan pool*. Main thread terbebas dan langsung memproses request HTTP lain pada event loop.
6. **Worker Completion**: Worker menyelesaikan komputasi matriks/prediksi dan mengirimkan hasilnya kembali ke main thread via socket/file descriptors IPC.
7. **Resolution & Serialization**: Promise teresolusi. Plumber memproses output melalui serialisator (misal `unboxed_json`) dan mengonversi format ke payload JSON.
8. **Egress**: `httpuv` mengirimkan byte payload ke klien dengan HTTP status 200 OK.

---

### 7. Analogy
Bayangkan sebuah restoran analitik:
- **Plumber Tradisional**: Pelayan (Main R Thread) mengambil pesanan Anda, lalu berjalan ke dapur, memasak sendiri makanan tersebut (komputasi data), menatanya di piring, dan mengantarkannya ke meja Anda. Selama pelayan memasak di dapur, pelanggan baru yang berdiri di pintu masuk restoran diabaikan sepenuhnya dan tidak bisa masuk.
- **Plumber Asinkronus (Produksi)**: Pelayan (Main R Thread/`httpuv`) mencatat pesanan, menaruh tiket pesanan ke *conveyor belt* dapur (Background Worker Pool via `future`), memberikan Anda kartu tunggu (Promise), lalu langsung menyapa pelanggan berikutnya di pintu masuk. Koki di dapur (R Worker Processes) memasak makanan secara independen. Begitu koki selesai memasak, pelayan hanya mengambil piring siap saji dan membawanya ke meja Anda.

---

### 8. Diagram
```
Client HTTP Request
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Process: Plumber Master Process (PID: 1001)           │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ httpuv Event Loop (C++ / Libuv)                  │  │
│  │ Non-blocking Socket Receiver                    │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │                            │
│                           ▼                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Plumber Pipeline (Filters: Auth, Log, Validate)  │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │                            │
│                           ▼                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Endpoint Handler: promises::future_promise()     │  │
│  └────────────┬────────────────────────▲────────────┘  │
│               │ (IPC Serialization)    │ (Resolved)    │
└───────────────┼────────────────────────┼───────────────┘
                │                        │
       ┌────────▼────────────────────────┴───────┐
       │ Future Multisession Worker Pool         │
       │                                         │
       │  ┌───────────────────────────────────┐  │
       │  │ Worker 1 (R PID: 1002) - ML Model │  │
       │  └───────────────────────────────────┘  │
       │  ┌───────────────────────────────────┐  │
       │  │ Worker 2 (R PID: 1003) - ML Model │  │
       │  └───────────────────────────────────┘  │
       │  ┌───────────────────────────────────┐  │
       │  │ Worker N (R PID: 100N) - ML Model │  │
       │  └───────────────────────────────────┘  │
       └─────────────────────────────────────────┘
```

---

### 9. Simple Example
Di bawah ini adalah implementasi minimal API Plumber dengan decorator standar.

Simpan sebagai file `api_simple.R`:
```r
# api_simple.R
library(plumber)

#* @apiTitle Simple Analytics API
#* @apiDescription Minimal microservice prototype

#* Echo parameter masukan
#* @param message Pesan teks yang akan dikembalikan
#* @get /echo
function(message = "") {
  list(
    status = "success",
    timestamp = Sys.time(),
    echo_message = paste0("Echo: ", message)
  )
}

#* Menghitung nilai mean dari array angka
#* @post /calculate-mean
#* @serializer unboxed_json
function(req) {
  raw_body <- req$postBody
  data <- jsonlite::fromJSON(raw_body)
  
  if (!is.numeric(data$numbers)) {
    stop("Input harus berupa array numerik.")
  }
  
  list(
    count = length(data$numbers),
    mean = mean(data$numbers)
  )
}
```

Script untuk menjalankan server:
```r
# run_simple.R
library(plumber)

r <- plumb("api_simple.R")
r$run(host = "0.0.0.0", port = 8080)
```

---

### 10. Practical Example
Berikut adalah implementasi skala produksi dengan structured logging, middleware validasi, penanganan error terpusat, dan evaluasi inferensi asinkronus menggunakan `future` dan `promises`.

#### File: `production_api.R`
```r
library(plumber)
library(promises)
library(future)
library(jsonlite)

# 1. Konfigurasi Concurrency Plan
# Inisialisasi pool worker background process independen
future::plan(future::multisession, workers = 4)

# Load dataset referensi atau model artifact ke dalam memori worker (Dummy Model)
TRAINED_MEAN <- 50.0
TRAINED_SD <- 10.0

#* @apiTitle Enterprise Scoring API
#* @apiDescription Layanan inferensi analitik non-blocking skala enterprise

#* ----------------------------------------------------
#* FILTER 1: Request Tracer & Structured Logging
#* ----------------------------------------------------
#* @filter request_tracer
function(req, res) {
  req$request_id <- paste0("req-", digest::digest(paste0(Sys.time(), runif(1)), algo = "crc32"))
  req$start_time <- Sys.time()
  
  cat(jsonlite::toJSON(list(
    level = "INFO",
    type = "incoming_request",
    id = req$request_id,
    method = req$REQUEST_METHOD,
    path = req$PATH_INFO,
    remote_addr = req$REMOTE_ADDR
  ), auto_unbox = TRUE), "\n")
  
  plumber::forward()
}

#* ----------------------------------------------------
#* FILTER 2: Context Timing
#* ----------------------------------------------------
#* @filter timing
function(req, res) {
  # Eksekusi downstream selesai sebelum blok ini keluar
  on.exit({
    duration_ms <- as.numeric(difftime(Sys.time(), req$start_time, units = "secs")) * 1000
    res$setHeader("X-Response-Time-Ms", sprintf("%.2f", duration_ms))
    res$setHeader("X-Request-ID", req$request_id)
    
    cat(jsonlite::toJSON(list(
      level = "INFO",
      type = "completed_request",
      id = req$request_id,
      status = res$status,
      duration_ms = duration_ms
    ), auto_unbox = TRUE), "\n")
  }, add = TRUE)
  
  plumber::forward()
}

#* ----------------------------------------------------
#* ENDPOINT: Healthcheck (Liveness / Readiness Probe)
#* ----------------------------------------------------
#* @get /healthz
#* @serializer unboxed_json
function(res) {
  res$status <- 200
  list(
    status = "UP",
    timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
    workers_available = future::nbrOfWorkers()
  )
}

#* ----------------------------------------------------
#* ENDPOINT: Asynchronous Prediction (Non-blocking)
#* ----------------------------------------------------
#* Memproses inferensi fitur tabular secara asinkronus
#* @post /v1/predict
#* @serializer unboxed_json
function(req, res) {
  # A. Parsing & Validasi Input Payload
  body <- tryCatch({
    jsonlite::fromJSON(req$postBody)
  }, error = function(e) {
    NULL
  })
  
  if (is.null(body) || is.null(body$features) || !is.numeric(body$features)) {
    res$status <- 400
    return(list(
      error = list(
        code = "INVALID_PAYLOAD",
        message = "Payload JSON harus memiliki key 'features' dengan nilai array numerik.",
        request_id = req$request_id
      )
    ))
  }
  
  features_data <- body$features
  req_id <- req$request_id
  
  # B. Isolasi Komputasi Berat via Future Promise
  # Komputasi dieksekusi di background R session, membebaskan main process
  promises::future_promise({
    # Simulasi latensi komputasi model ML
    Sys.sleep(0.5)
    
    # Hitung Z-Score Matrix Normalization
    z_scores <- (features_data - TRAINED_MEAN) / TRAINED_SD
    probabilities <- 1 / (1 + exp(-z_scores))
    score <- mean(probabilities)
    
    list(
      score = score,
      classification = ifelse(score > 0.5, "HIGH_RISK", "LOW_RISK"),
      processed_elements = length(features_data)
    )
  }) %...>% (function(result) {
    # Resolusi Sukses
    res$status <- 200
    list(
      success = TRUE,
      request_id = req_id,
      data = result
    )
  }) %...!% (function(err) {
    # Resolusi Gagal (Error Boundary)
    res$status <- 500
    cat(jsonlite::toJSON(list(
      level = "ERROR",
      id = req_id,
      message = err$message
    ), auto_unbox = TRUE), "\n")
    
    list(
      success = FALSE,
      request_id = req_id,
      error = list(
        code = "INFERENCE_ERROR",
        message = "Terjadi kegagalan internal saat menghitung estimasi probabilitas."
      )
    )
  })
}
```

---

### 11. Real World Example
**Skenario: Sistem Deteksi Fraud Real-time pada Platform Financial Technology**

Sebuah bank digital memproses hingga 1.500 transaksi per detik (*card-present transaction*). Tim Data Science membuat model berbasis *Gradient Boosted Decision Trees* (`xgboost`) dalam bahasa R untuk mendeteksi anomali penarikan dana.

**Implementasi Lapangan**:
1. **Cluster Setup**: API Plumber dikemas ke dalam Docker image berbasis minimal Linux (Debian slim / Rocker). Container tersebut dijalankan di atas kluster Kubernetes (EKS).
2. **Reverse Proxying**: NGINX Ingress Controller diimplementasikan di depan Plumber Pods untuk mengakhiri enkripsi TLS/HTTPS dan melakukan connection keep-alive buffering.
3. **Scaling Model**: Karena setiap R pod dibatasi oleh alokasi 1 Core CPU secara efisien, deployment menggunakan HPA (*Horizontal Pod Autoscaler*) berdasarkan metrik HTTP queue depth dan utilisasi CPU. 
4. **Isolasi Memori**: Model tree sebesar 350 MB dimuat sekali saat inisialisasi master container, lalu di-*share* secara read-only ke pool worker melalui memori `mmap` untuk menghemat alokasi RAM per instance container dari 2 GB menjadi 600 MB.

Dampaknya, API mampu menghasilkan P99 latency di bawah 85 milidetik dengan *throughput* stabil tanpa memblokir probe *readiness* dari Kubernetes.

---

### 12. Trade-offs

| Parameter | Pendekatan Synchronous (Native) | Pendekatan Asynchronous (`future`/`promises`) | Pendekatan External Queue (Celery/Redis/R) |
|---|---|---|---|
| **Throughput (I/O)** | Sangat Rendah (Tergantung proses paling lambat) | Tinggi (I/O non-blocking, multi-core processing) | Sangat Tinggi (Decoupled total via message broker) |
| **P99 Latency** | Terdegradasi tajam saat concurrent traffic tinggi | Relatif stabil mendekati durasi inferensi murni | Cenderung lambat karena overhead pooling & roundtrip broker |
| **Complexity** | Sangat Rendah (Runtun sequential) | Menengah (Perlu manajemen *promises* & IPC) | Tinggi (Membutuhkan cluster Redis/RabbitMQ terpisah) |
| **Memory Footprint** | Minimal (1 master process instance) | Bergantung jumlah worker (`multisession` menggandakan footprint) | Terpisah dari API Server (Worker terisolasi) |
| **Debugging** | Sederhana (Stack trace native R) | Kompleks (Stack trace async terpisah lintas proses) | Kompleks (Pelacakan distributed context via tracing ID) |

---

### 13. When To Use
Gunakan arsitektur Plumber skala produksi ketika:
- Anda memiliki model analitik, aktuaria, atau biostatistika canggih yang ditulis menggunakan paket R khusus (misal: `survival`, `lme4`, `brms`, `tidymodels`) yang tidak memiliki ekivalen di bahasa lain.
- Layanan perlu merespons payload secara langsung (*real-time synchronous response*) dengan throughput moderat hingga tinggi (100–2.000 QPS dengan horizontal scaling).
- Tim didominasi oleh R engineers yang bertanggung jawab penuh terhadap *end-to-end lifecycle* dari training model hingga ke layer penyajian (*serving*).

---

### 14. When NOT To Use
Hindari penggunaan arsitektur ini jika:
- **High-throughput I/O Streaming**: Layanan hanya berfungsi sebagai proxy forwarding data mentah atau WebSockets berdensitas jutaan koneksi bersamaan (Gunakan Go, Node.js, atau Rust).
- **Proses Berdurasi Sangat Panjang (> 30 detik)**: Komputasi batch analitik berukuran gigabyte. Gunakan model *background job processing* berbasis asynchronous polling (misal `celery`, AWS SQS/Lambda, atau `callr` yang dipisah dari API).
- **Embedded Ultra-low Latency Hardware**: Layanan membutuhkan response time deterministik di bawah level sub-milidetik (Gunakan C++, C, atau C via micro-framework).

---

### 15. Common Mistakes
1. **Mengabaikan Mutasi State Global**: Menggunakan assignment global (`<<-`) di dalam endpoint handler. Dalam arsitektur asynchronous dengan multi-worker, tiap worker memiliki *isolated memory space*; mutasi state di Worker A tidak akan pernah terefleksi di Worker B.
2. **Blocking Main Thread dengan Heavy Task**: Menjalankan evaluasi berdurasi 5 detik di dalam endpoint tanpa membungkusnya dengan `promises::future_promise()`. Ini melumpuhkan endpoint `/healthz` dan memicu Kubernetes membunuh kontainer karena dianggap *unresponsive*.
3. **Membocorkan Database Connections**: Membuka koneksi pool SQL di dalam fungsi handler tanpa blok `on.exit(DBI::dbDisconnect(conn))` yang menjamin pemutusan koneksi saat fungsi error/berhenti mendadak.
4. **Serialization Overhead Trap**: Mengembalikan objek data frame mentah R yang sangat besar ke serialisator JSON bawaan. Hal ini memakan utilisasi CPU sangat tinggi untuk konversi string JSON dan menimbulkan beban serialization latency masif. Gunakan *feather/arrow* serialization untuk bulk data transfer.

---

### 16. Best Practices (Production Checklist)
- [ ] **State Isolation**: Pastikan seluruh endpoint bersifat *pure functions*; tidak bergantung pada state yang tertinggal di sesi sebelumnya.
- [ ] **Structured Logging**: Log seluruh aktivitas dalam format JSON valid (`stdout`) menggunakan library seperti `logger` agar mudah diparsing oleh log aggregator (Datadog/Elasticsearch).
- [ ] **Explicit Typing**: Hindari tipe data longgar. Validasi struktur JSON request payload di layer filter paling awal menggunakan `checkmate` atau skema JSON (`jsonvalidate`).
- [ ] **Explicit Serializer Configuration**: Gunakan `@serializer unboxed_json` daripada `json` bawaan untuk mencegah konversi skalar menjadi array JSON berukuran 1 elemen secara tidak sengaja.
- [ ] **Signal Handling & Graceful Shutdown**: Tangkap signal `SIGTERM` dan `SIGINT` untuk memberi waktu pada worker pool menyelesaikan proses sebelum proses induk dimatikan.
- [ ] **Non-root Container Execution**: Jalankan Plumber API di dalam kontainer Docker menggunakan akun service non-root (*least privilege principle*).

---

### 17. Troubleshooting

| Gejala Masalah | Investigasi Root Cause | Langkah Remediasi |
|---|---|---|
| **HTTP 502 / 504 Gateway Timeout** | Main event loop R mengalami blocking atau antrean worker `future` telah jenuh (*saturated*). | Tambah jumlah `workers` pada `future::plan()`, atau naikkan replika pod secara horizontal. Identifikasi operasi sinkronus yang belum di-wrap `future_promise`. |
| **Kubernetes OOMKilled (Out of Memory)** | Mode `multisession` menduplikasi objek besar ke seluruh sub-proses R, melampaui limit RAM kontainer. | Gunakan memory-efficient formats (e.g., SQLite/DuckDB connection) atau gunakan model *forking* (`future::multicore`) pada OS berbasis Linux/Unix dengan mekanisme Copy-On-Write (COW). |
| **Worker R Menjadi Zombie (PID Hang)** | Worker process macet saat menunggu I/O eksternal (misal: database lock atau download network). | Pasang limit timeout eksplisit pada semua operasi network I/O (`httr::timeout`, `DBI` connection timeout). Gunakan library `later` untuk menghentikan promise yang hung. |
| **High Memory Fragmentation** | R Garbage Collector (`gc()`) tidak mengembalikan memori virtual ke OS setelah parsing payload JSON yang masif. | Panggil `gc(verbose = FALSE)` secara periodik di akhir batch request processing, atau atur threshold memory allocator via env variable `MALLOC_ARENA_MAX=2`. |

---

### 18. Exercise
**Instruksi Penugasan**:
Rancanglah sebuah script Plumber API bernama `exercise_api.R` yang memenuhi kualifikasi teknis berikut:
1. Sediakan endpoint HTTP POST `/v1/matrix-transform`.
2. Validasi bahwa payload yang masuk berisi:
   - `matrix_data`: Array 2-dimensi numerik.
   - `factor`: Angka skalar numerik.
3. Eksekusi perkalian skalar matriks secara asinkronus menggunakan `future_promise`.
4. Jika payload tidak valid (misal `factor` bernilai string atau bukan angka), kembalikan respons error dengan HTTP Status Code 422 (Unprocessable Entity) beserta payload JSON terstruktur.
5. Lengkapi endpoint dengan kalkulasi waktu pemrosesan di server (`X-Computation-Time-Sec`) yang disematkan ke dalam respons body.

---

### 19. Challenge
**Studi Kasus Arsitektur Tingkat Tinggi**:
Buat implementasi produksi lengkap sistem penyajian model scoring berbasis Plumber yang menerapkan pola **Circuit Breaker** dan **Graceful Fallback**.

**Persyaratan Sistem**:
1. Buat router Plumber yang mengekspos endpoint `/v1/complex-inference`.
2. Endpoint harus memanggil sub-sistem inferensi simulasi berat (gunakan `Sys.sleep(runif(1, 0.1, 2.0))`).
3. Tetapkan SLA: Jika komputasi berjalan melebihi batas waktu (timeout) 750 milidetik, batalkan eksekusi promise tersebut dan langsung kembalikan respon *fallback* (misal: nilai mean historis: `0.15`) dengan status HTTP 206 (Partial Content) beserta indikator flag `"fallback_applied": true`.
4. Jika rasio kegagalan/timeout melampaui 50% dari 10 request terakhir, aktifkan kondisi *Circuit Breaker OPEN*: seluruh request berikutnya selama 10 detik langsung ditolak dengan status HTTP 503 (Service Unavailable) tanpa memicu background worker sama sekali.
5. Seluruh state circuit breaker wajib dipertahankan secara thread-safe menggunakan atomic locking pattern atau environment state manager independen.

---

### 20. Summary
Paket `plumber` mentransformasi bahasa pemrograman R dari sekadar environment analisis ad-hoc menjadi platform microservices yang tangguh. Melalui pemahaman mendalam tentang *underlying event loop* `httpuv` dan integrasi eksekusi non-blocking via `future` dan `promises`, developer dapat mengatasi hambatan bawaan *single-threaded runtime* R.

Mengoperasikan Plumber di lingkungan produksi menuntut penerapan pola rekayasa perangkat lunak standar industri: validasi input yang ketat, isolasi proses komputasi, penanganan error struktural, dan instrumentasi logging berbasis JSON. Dengan arsitektur ini, performa layanan inferensi machine learning R dapat diskalakan secara horizontal dan deterministik di dalam platform kontainer modern.