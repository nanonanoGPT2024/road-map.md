# BAB 10: Production Deployment, API, & Interactive Dashboards
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur API berbasis R (`plumber`) berkinerja tinggi yang bersifat non-blocking menggunakan paradigma asynchronous (`promises` dan `future`).
- **Membangun** sistem koneksi database tingkat enterprise yang aman dan efisien menggunakan teknik *connection pooling* (`pool`).
- **Mengembangkan** aplikasi web analitik reaktif (`shiny`) berskala besar menggunakan *Shiny Modules* dan isolasi *state* untuk mencegah kebocoran memori (*memory leak*).
- **Mengonfigurasi dan mengorkestrasi** aplikasi R dalam lingkungan kontainer (Docker) dan kluster (Kubernetes) dengan penanganan *sticky sessions*, *health probes*, dan observabilitas (*metrics* & *structured logging*).
- **Menganalisis dan memitigasi** *bottleneck* performa yang melekat pada model eksekusi *single-threaded* bawaan R Runtime.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
- Pemahaman mendalam tentang *functional programming* di R (lingkup *environments*, *closures*, dan evaluasi *lazy*).
- Pemahaman dasar framework API `plumber` dan framework reaktif `shiny`.
- Pengalaman praktis dengan protokol HTTP, WebSocket, format serialisasi data (JSON), dan *stateless vs stateful communication*.
- Penguasaan *containerization* tingkat dasar (Dockerfile, multi-stage build, Docker network).
- Pemahaman dasar arsitektur sistem terdistribusi, *reverse proxy* (Nginx/Traefik), dan manajemen memori OS (Linux POSIX process model).

---

### 3. Concept & Internal Architecture

#### 3.1 Model Runtime R & Batasan Konkurensi
R secara historis dan fundamental dirancang sebagai *single-threaded runtime engine*. R mengoperasikan satu *call stack* dan satu *heap memory pool* utama. Ketika R menjalankan komputasi CPU-intensive (misalnya pelatihan model XGBoost atau agregasi data masif via `dplyr`), *event loop* runtime akan terblokir (*blocked*).

```
                      +-----------------------------+
                      |   Client HTTP Requests      |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |  libuv Event Loop (httpuv)  |
                      +-----------------------------+
                                     |
                [Non-blocking I/O]  / \  [Blocking Execution]
                                   /   \
                                  v     v
             +----------------------+ +-------------------------+
             | Future Worker Pool   | | Main R Execution Thread |
             | (Background Process) | | (BLOCKED during heavy   |
             +----------------------+ |  computation)           |
                        |             +-------------------------+
                        v
             +----------------------+
             | Resolved Promises    |
             | to httpuv Response   |
             +----------------------+
```

Framework produksi R seperti `plumber` dan `shiny` berjalan di atas package `httpuv`, yang mengintegrasikan *event loop* `libuv` (komponen inti yang sama dengan Node.js) langsung ke dalam proses R. 
- Pada mode sinkron bawaan, satu *request* komputasi berat akan memblokir seluruh *request* lain yang antre di `httpuv`.
- Untuk mencapai standar enterprise, arsitektur R harus diubah menjadi **hybrid asynchronous execution model** menggunakan package `promises` dan `future`.

#### 3.2 Siklus Hidup Request Plumber
Pipeline eksekusi `plumber` melibatkan beberapa tahapan:
1. **Request Ingestion**: `httpuv` menerima paket TCP, mem-parsing HTTP frame, dan menyerahkannya ke objek router Plumber.
2. **Filter Processing**: Filter mengeksekusi logika lintas-fungsi (*cross-cutting concerns*) secara sekuensial (autentikasi JWT, parsing token, injeksi Request ID). Jika filter melempar error atau tidak memanggil `forward()`, request langsung dihentikan.
3. **Route Matching & Deserialization**: Plumber mencocokkan URL path dan HTTP verb, lalu mengonversi body payload menjadi parameter fungsi R via serializer/deserializer.
4. **Execution & Promise Handling**: Handler rute mengeksekusi logika bisnis. Jika handler mengembalikan sebuah objek `promise`, Plumber melepaskan thread utama `httpuv` agar dapat menerima request lain, sementara komputasi dilanjutkan pada *worker process* latar belakang (`multisession` atau `cluster`).
5. **Serialization & Response Delivery**: Setelah *promise* berstatus `resolved`, hasil diserialisasi ke format target (JSON, binary feather/arrow) dan dikirim kembali ke klien via `httpuv`.

#### 3.3 Shiny Session State & Reactive Graph Topology
Aplikasi Shiny enterprise mengelola *state* melalui *Directed Acyclic Graph* (DAG) reaktif:
- Setiap koneksi browser menginisiasi sebuah WebSocket dupleks penuh (*full-duplex*).
- Objek `session` diisolasi di memori server per klien.
- Dependensi reaktif (`reactiveVal`, `reactive`, `observeEvent`) bertindak sebagai node dalam DAG. Perubahan pada node *input* memicu propagasi *invalidation* ke seluruh node turunan secara topologis.
- **Masalah Produksi**: Jika objek besar dibagikan secara global tanpa enkapsulasi modul atau isolasi *environment*, memori server akan cepat habis (*Out of Memory / OOM*) dan data antar pengguna dapat bocor (*state leakage*).

#### 3.4 Connection Pooling Menggunakan Package `pool`
Koneksi database langsung (`DBI::dbConnect`) bersifat mahal (*high overhead latency*) karena melibatkan *TCP handshake*, negosiasi SSL/TLS, dan alokasi sesi database. Pada arsitektur konkurensi:
- Membuat koneksi per request akan membuat database mengalami *connection exhaustion*.
- Package `pool` mengelola *pool of connections* yang persisten. Koneksi dipinjam (*checked out*) oleh thread/worker untuk satu transaksi/kueri dan segera dikembalikan (*checked in*) ke pool tanpa menutup soket TCP fisik.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional R | Pendekatan Enterprise R (Modul Ini) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Sinkron (*blocking main thread*). Request A menahan Request B. | Asinkron berbasis `promises` + `future` multisession. Non-blocking I/O. |
| **Koneksi Database** | Membuka/menutup koneksi per request (`dbConnect`/`dbDisconnect`). | *Connection Pooling* dinamis via package `pool` dengan pemulihan otomatis. |
| **Arsitektur Shiny** | Monolitik (`ui.R` dan `server.R` besar), variabel global tidak terkontrol. | Modular (`Shiny Modules`), namespaced reactivity, dan pemisahan *business logic*. |
| **Skalabilitas** | Skala vertikal (menambah CPU/RAM mesin tunggal). | Skala horizontal (Stateless Docker containers diatur via Traefik/Kubernetes). |
| **Observabilitas** | Logging teks standar via `print()` atau `cat()` ke STDOUT. | *Structured JSON Logging* (`logger`) dengan korelasi `Request-ID` & metrik Prometheus. |
| **Error Handling** | Fatal crash (R execution abort) saat terjadi *unhandled exception*. | Global error boundary, *graceful degradation*, dan pemetaan status kode HTTP standar. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi terbagi menjadi 4 layer utama:

```
[Client App / SPA]
       |
       v (HTTPS / WSS)
[Ingress / Reverse Proxy: Traefik or Nginx]
       |
       +---> Sticky Session Route (Shiny Dashboard)
       |
       +---> Round Robin Load Balancing (Plumber API Workers)
               |
               v
     +-------------------+
     | Container Instance|
     |   (Docker: R)     |
     |                   |
     | [Filter Middleware|
     |   - Log Tracing   |
     |   - Auth / JWT    |
     |                   |
     | [Async Handler]   | ---> [Future Multisession Pool]
     |                   |              | (Heavy compute/ML)
     | [DB Pool Manager] | <------------+
     +---------+---------+
               |
               v (Managed Connections)
       [PostgreSQL / MySQL]
```

1. **Ingress & Traffic Splitting**:
   - Traffic HTTP API diarahkan secara *stateless load-balancing* (Round Robin).
   - Traffic Shiny diarahkan menggunakan *Sticky Session* berbasis cookie (`affinity: cookie`), karena koneksi WebSocket terikat langsung ke satu proses R yang menyimpan memori sesi pengguna.
2. **Middleware Processing**:
   - `Request-ID` diinjeksi atau diekstraksi dari header HTTP `X-Request-ID`.
   - Token JWT didekripsi dan divalidasi tanda tangannya sebelum mencapai handler bisnis.
3. **Execution Offloading**:
   - Komputasi analitik atau kueri database lambat dibungkus ke dalam blok `future::future()` yang mengembalikan `promises::promise()`.
   - Thread utama Plumber segera kembali menerima koneksi baru dari `httpuv`.
4. **Data Access via Pool**:
   - Eksekutor mengambil koneksi yang valid dari *pool* global, mengeksekusi kueri berparameter (*parameterized query* untuk mitigasi SQL Injection), dan mengembalikan koneksi seketika.
5. **Instrumentation & Telemetry**:
   - Middleware menghitung latensi eksekusi dan mengekspos endpoint internal `/metrics` yang kompatibel dengan *Prometheus scraper*.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Bintang Lima
- **Pendekatan Naif**: Satu koki (R Engine) menerima pesanan, memotong daging, memasak, mengantar makanan ke meja, lalu baru menerima pesanan pelanggan berikutnya. Dapur mengalami *bottleneck* total jika ada satu pesanan steak matang lambat.
- **Pendekatan Enterprise**: 
  - Koki Utama (Thread `httpuv`) hanya menerima pesanan dari pelayan dan menyerahkan tiket ke juru masak asisten di belakang (*Future Worker Pool*).
  - Koki Utama bebas menerima 100 pesanan lain tanpa henti.
  - Perkakas dapur berat (panci, kompor gas bertekanan tinggi) dikelola dalam satu rak bersama (*Connection Pool*) di mana siapa pun yang selesai memasak langsung mengembalikan alat tersebut ke tempatnya agar bisa digunakan juru masak lain.

#### Diagram Arsitektur Internal R Plumber Enterprise

```
+-----------------------------------------------------------------------------------+
| Linux Container (R Plumber Process Runtime)                                       |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Main Thread (httpuv Engine)                                                 |  |
|  |                                                                             |  |
|  |   [Incoming Request] ---> [Filter: Request-ID] ---> [Filter: Auth JWT]       |  |
|  |                                                             |               |  |
|  |                                                             v               |  |
|  |                                                     [Router Matching]       |  |
|  |                                                             |               |  |
|  |                                                             v               |  |
|  |                                                    [Async Handler]          |  |
|  |                                                             |               |  |
|  |       +-----------------------------------------------------+               |  |
|  |       | Offload via promises::promise()                                     |  |
|  |       v                                                                     |  |
|  |  (Main thread returns to event loop immediately)                            |  |
|  +-------|-------------------------------------------------------------^-------+  |
|          |                                                             |          |
|          | Inter-Process Communication (IPC via sockets)               |          |
|          v                                                             |          |
|  +-------------------------------------------------------------+       |          |
|  | Future Background Worker Pool (multisession)                |       |          |
|  |                                                             |       |          |
|  |   Worker 1: [DB Query via pool] ---> [Data Wrangling]       |       |          |
|  |   Worker 2: [Scoring ML Model]  ---> [Matrix Ops] ----------+-------+          |
|  |   Worker N: [External REST Call]---> [JSON Parsing]         | (Resolved)       |  |
|  +-------------------------------------------------------------+                  |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Implementasi Non-blocking Endpoint Asinkron

File: `simple_async_api.R`
```r
library(plumber)
library(promises)
library(future)

# Inisialisasi worker pool di latar belakang
future::plan(future::multisession, workers = 2)

#* @apiTitle Simple Async Plumber Engine

#* Endpoint komputasi berat yang dieksekusi secara non-blocking
#* @get /compute-heavy
function() {
  # Eksekusi dilempar ke background worker
  future::future({
    # Simulasi proses berat (misal: estimasi bootstrap 3 detik)
    Sys.sleep(3)
    hasil <- mean(rnorm(1e6))
    list(
      status = "SUCCESS",
      worker_pid = Sys.getpid(),
      result = hasil
    )
  }) %...>% (function(response) {
    # Handler saat promise berhasil diselesaikan
    response
  }) %...!% (function(err) {
    # Handler jika terjadi failure/exception
    list(status = "ERROR", message = err$message)
  })
}

#* Endpoint ringan yang merespons instan meski /compute-heavy sedang berjalan
#* @get /ping
function() {
  list(status = "HEALTHY", timestamp = Sys.time())
}
```

#### 7.2 Practical Example: Enterprise-Grade Plumber API dengan Connection Pooling, Structured Logging, dan JWT Guard

File: `enterprise_api.R`
```r
library(plumber)
library(promises)
library(future)
library(pool)
library(DBI)
library(RSQLite)
library(logger)
library(jose)
library(jsonlite)

# ---------------------------------------------------------
# 1. KONFIGURASI DAN INFRASTRUKTUR RUNTIME
# ---------------------------------------------------------
future::plan(future::multisession, workers = 4)

# Format structured logging (JSON) ke stdout
logger::log_layout(logger::layout_json())
logger::log_appender(logger::appender_stdout)

# Inisialisasi Database Connection Pool
# Menggunakan SQLite in-memory untuk portabilitas demonstrasi, 
# dapat langsung diganti dengan RPostgres::Postgres()
db_pool <- pool::dbPool(
  drv = RSQLite::SQLite(),
  dbname = ":memory:",
  maxSize = 10,
  idleTimeout = 30000
)

# Setup tabel skema awal
DBI::dbExecute(db_pool, "
  CREATE TABLE risk_scores (
    user_id TEXT PRIMARY KEY,
    score REAL,
    category TEXT,
    updated_at TEXT
  )
")
DBI::dbExecute(db_pool, "
  INSERT INTO risk_scores VALUES 
  ('USR-001', 785.5, 'PRIME', datetime('now')),
  ('USR-002', 590.0, 'SUBPRIME', datetime('now'))
")

# JWT Secret Key (Pada produksi, ambil dari Sys.getenv('JWT_SECRET'))
JWT_SECRET_KEY <- "c2VjcmV0LWtleS1kZW1vLWVudGVycHJpc2UtZGF0YS1zY2llbmNlLTEyMzQ1"

# ---------------------------------------------------------
# 2. MIDDLEWARE / FILTERS
# ---------------------------------------------------------

#* @filter request_logger
function(req, res) {
  # Injeksi / Propagasi Request ID
  req_id <- req$HTTP_X_REQUEST_ID
  if (is.null(req_id) || req_id == "") {
    req_id <- paste0("req_", as.numeric(Sys.time()), "_", sample(1000:9999, 1))
  }
  req$request_id <- req_id
  res$setHeader("X-Request-ID", req_id)
  
  start_time <- Sys.time()
  
  # Forward ke handler berikutnya
  plumber::forward()
  
  # Log setelah eksekusi selesai
  duration_ms <- as.numeric(difftime(Sys.time(), start_time, units = "secs")) * 1000
  logger::log_info(
    request_id = req$request_id,
    method = req$REQUEST_METHOD,
    path = req$PATH_INFO,
    status = res$status,
    latency_ms = round(duration_ms, 2)
  )
}

#* @filter auth_guard
function(req, res) {
  # Lewatkan endpoint metrik dan liveness probe dari autentikasi
  if (req$PATH_INFO %in% c("/health", "/metrics", "/openapi.json")) {
    return(plumber::forward())
  }
  
  auth_header <- req$HTTP_AUTHORIZATION
  if (is.null(auth_header) || !grepl("^Bearer ", auth_header)) {
    res$status <- 401
    return(list(
      error = "UNAUTHORIZED", 
      message = "Missing or malformed Authorization header.",
      request_id = req$request_id
    ))
  }
  
  token <- sub("^Bearer ", "", auth_header)
  
  # Verifikasi tanda tangan JWT
  auth_result <- tryCatch({
    # Parsing claim token
    claims <- jose::jwt_decode_hmac(token, secret = charToRaw(JWT_SECRET_KEY))
    
    # Validasi masa berlaku token (exp)
    if (!is.null(claims$exp) && as.numeric(Sys.time()) > claims$exp) {
      stop("Token expired")
    }
    claims
  }, error = function(e) {
    NULL
  })
  
  if (is.null(auth_result)) {
    res$status <- 403
    return(list(
      error = "FORBIDDEN", 
      message = "Invalid or expired cryptographic token.",
      request_id = req$request_id
    ))
  }
  
  # Lampirkan context pengguna ke environment request
  req$user_context <- auth_result
  plumber::forward()
}

# ---------------------------------------------------------
# 3. CONTROLLERS & ASYNC ROUTES
# ---------------------------------------------------------

#* Liveness / Readiness Health Check
#* @get /health
#* @serializer unboxedJSON
function(res) {
  # Verifikasi kesiapan DB Pool
  db_ok <- pool::dbIsValid(db_pool)
  if (!db_ok) {
    res$status <- 503
    return(list(status = "DEGRADED", database = "DISCONNECTED"))
  }
  
  list(
    status = "SERVING",
    timestamp = Sys.time(),
    active_pool_conns = db_pool$counters$free
  )
}

#* Endpoint Query Risiko Finansial (Asinkron & Parameterized)
#* @get /api/v1/risk-profile
#* @param user_id:string Identifier nasabah
#* @serializer json
function(req, res, user_id = "") {
  if (user_id == "") {
    res$status <- 400
    return(list(
      error = "BAD_REQUEST", 
      message = "Parameter 'user_id' wajib disertakan.",
      request_id = req$request_id
    ))
  }
  
  req_id <- req$request_id
  
  # Menggunakan connection pool dalam future block
  # Pool object dilempar aman dengan mengeksekusi koneksi di dalam thread eksekusi
  future::future({
    # Ambil koneksi dari pool untuk satu transaksi kueri aman
    conn <- pool::poolCheckout(db_pool)
    on.exit(pool::poolReturn(conn), add = TRUE)
    
    query <- "SELECT user_id, score, category, updated_at FROM risk_scores WHERE user_id = ?"
    params <- list(user_id)
    
    record <- DBI::dbGetQuery(conn, query, params = params)
    
    # Simulasi kalkulasi analitik tambahan di background worker
    Sys.sleep(0.5)
    
    if (nrow(record) == 0) {
      return(list(found = FALSE))
    }
    
    list(
      found = TRUE,
      payload = as.list(record[1, ])
    )
  }) %...>% (function(data_result) {
    if (!data_result$found) {
      res$status <- 404
      return(list(
        error = "NOT_FOUND",
        message = sprintf("User dengan ID '%s' tidak ditemukan.", user_id),
        request_id = req_id
      ))
    }
    
    list(
      status = "SUCCESS",
      data = data_result$payload,
      meta = list(
        request_id = req_id,
        processed_at = Sys.time()
      )
    )
  }) %...!% (function(err) {
    logger::log_error(request_id = req_id, error = err$message)
    res$status <- 500
    list(
      error = "INTERNAL_SERVER_ERROR",
      message = "Gagal memproses kalkulasi profil risiko.",
      request_id = req_id
    )
  })
}

# ---------------------------------------------------------
# 4. TEARDOWN HOOKS
# ---------------------------------------------------------
# Registrasi pembersihan resource saat engine dimatikan
# Dijalankan via entrypoint script sebelum proses R keluar
reg.finalizer(globalenv(), function(e) {
  if (exists("db_pool") && pool::dbIsValid(db_pool)) {
    pool::poolClose(db_pool)
  }
}, onexit = TRUE)
```

---

### 8. Real World Case Study: Enterprise Credit Scoring Under High Load

#### 8.1 Latar Belakang Masalah
Sebuah institusi Multi-Finance memiliki model credit scoring berbasis XGBoost yang di-wrap menggunakan API Plumber sinkron dasar. Pada jam sibuk (09:00 - 11:00), sistem menerima 250 requests/detik dari cabang di seluruh Indonesia.

**Insiden Produksi**:
- Latensi P99 meroket dari 120ms ke 28 detik.
- Terjadi *cascade timeout* pada HTTP Ingress.
- Server R kehabisan koneksi PostgreSQL (*FATAL: remaining connection slots are reserved for non-replication superuser connections*).
- Driver Shiny internal yang memonitor real-time fraud ikut terputus (*WebSocket connection dropped*).

#### 8.2 Analisis Akar Masalah (Root Cause Analysis)
1. **Thread Blocking**: Endpoint inferensi model membutuhkan waktu 180ms CPU-bound. Dengan model sinkron, 1 proses R hanya bisa melayani maksimal 5.5 req/detik.
2. **Koneksi DB Konvensional**: Setiap *hit* memanggil `DBI::dbConnect()` dan `DBI::dbDisconnect()`. Negosiasi TLS database memakan 45ms per request.
3. **Shiny & API Berada di Instance Sama**: Shiny dashboard fraud analitik berbagi resource CPU yang sama dengan Plumber API, sehingga *event loop* `httpuv` Shiny kehabisan jatah komputasi.

#### 8.3 Solusi Arsitektural yang Diimplementasikan
1. **Pemisahan Fisik**: Memecah layanan menjadi dua kluster terpisah:
   - `Credit-Scoring-API` (Plumber Stateless di Kubernetes Deployment).
   - `Fraud-Monitor-Dashboard` (Shiny Stateful di Kubernetes StatefulSet dengan Traefik Sticky Sessions).
2. **Plumber Asynchronous Engine**:
   - Memodifikasi handler prediksi model ke dalam pola `future::future()` menggunakan plan `multisession` (4 worker per kontainer).
   - Mengalokasikan 8 Replicas Kontainer Plumber di Kubernetes dengan HPA (*Horizontal Pod Autoscaler*) berdasarkan utilisasi CPU (target 65%).
3. **Penerapan Database Pooling**:
   - Menerapkan `pool::dbPool` dengan limit maksimal 5 koneksi per pod kontainer, dipadukan dengan PgBouncer di layer infrastruktur database.
4. **Hasil**:
   - Kapasitas throughput sistem melonjak dari 15 req/detik menjadi 550 req/detik.
   - Latensi P99 terpangkas stabil di angka 145ms.
   - Utilisasi koneksi DB turun 70% berkat reuse koneksi via *pool*.

---

### 9. Trade-offs: Architectural Matrix

Setiap keputusan rekayasa sistem memiliki konsekuensi yang terukur:

| Pilihan Arsitektur | Keuntungan | Konsekuensi & Trade-off |
| :--- | :--- | :--- |
| **Async Execution (`promises`/`future`)** | Mencegah blokir total pada `httpuv`. Throughput sistem meningkat drastis di bawah konkurensi tinggi. | Menambah *overhead latency* baseline (sekitar 5-15ms) untuk IPC (*Inter-Process Communication*) dan serialisasi data antar-worker. Debugging *stack trace* menjadi jauh lebih kompleks. |
| **Connection Pooling (`pool`)** | Menghilangkan latency TCP/TLS handshake database berulang. Mencegah kolapsnya DB server dari lonjakan koneksi. | Jika terdapat kueri yang mengalami kebocoran *transaction lock*, koneksi dalam pool dapat terkunci selamanya (*pool starvation*) jika parameter `idleTimeout` tidak dikonfigurasi ketat. |
| **Posit Connect vs Standalone Kubernetes (ShinyProxy / Traefik)** | **Posit Connect**: Manajemen *out-of-the-box*, integrasi LDAP/SAML instan, zero-configuration R-environment.<br>**K8s**: Fleksibilitas skala tak terbatas, integrasi ekosistem Cloud-Native, bebas biaya lisensi software komersial. | **Posit Connect**: Biaya lisensi komersial tinggi per user/core, kustomisasi jaringan ingress terbatas.<br>**K8s**: Membutuhkan kapabilitas DevOps internal yang matang, pengelolaan Docker image R berukuran besar (1-3GB), penanganan *sticky session* manual. |
| **Model Preloading di Worker Memory** | Waktu inferensi kilat karena model machine learning sudah dimuat ke RAM masing-masing worker saat *startup*. | Penggunaan memori pod kontainer berlipat ganda (*linear terhadap jumlah multisession worker*). Resiko pod di-kill oleh OS akibat *OOMKilled* (Out Of Memory). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kebocoran Memori Reaktif di Shiny (Reactive Memory Leak)
* **Gejala**: Penggunaan RAM kontainer Shiny terus naik secara bertahap dan tidak pernah turun meski pengguna sudah menutup tab browser.
* **Penyebab**: Menggunakan fungsi observasi global atau mendaftarkan observer ke variabel di luar lingkup server fungsi modul tanpa membersihkannya (`session$onSessionEnded`).
* **Solusi**: Pastikan seluruh `observe()`, `observeEvent()`, dan reaktif didefinisikan secara strictly encapsulated di dalam server function modul. Manfaatkan handler pembersihan:
  ```r
  my_module_server <- function(id, shared_pool) {
    moduleServer(id, function(input, output, session) {
      obs <- observe({ ... })
      session$onSessionEnded(function() {
        obs$destroy() # Hancurkan referensi observer saat sesi berakhir
      })
    })
  }
  ```

#### 10.2 Database Connection Starvation
* **Gejala**: Plumber API tiba-tiba menggantung (*hang*) pada semua request database, mengembalikan error `Timeout waiting for connection from pool`.
* **Penyebab**: Koneksi diambil menggunakan `pool::poolCheckout()`, tetapi saat terjadi error pada baris logika di bawahnya, proses keluar dari fungsi sebelum `pool::poolReturn()` dieksekusi.
* **Solusi**: Gunakan blok `on.exit(pool::poolReturn(conn), add = TRUE)` langsung pada baris setelah koneksi di-checkout, atau gunakan fungsi pembungkus transaksi otomatis:
  ```r
  # POLA AMAN:
  conn <- pool::poolCheckout(my_pool)
  on.exit(pool::poolReturn(conn), add = TRUE)
  # Jalankan query... Jika error terjadi di sini, on.exit TETAP dieksekusi.
  ```

#### 10.3 Putusnya Sesi WebSocket Shiny di Balik Ingress Kontainer
* **Gejala**: Aplikasi Shiny sering memunculkan pesan abu-abu (*Disconnected from the server*) setelah 60 detik idle atau saat pod replika bertambah.
* **Penyebab**: 
  1. Ingress controller (seperti Nginx atau AWS ALB) tidak mengonfigurasi *read/write timeout* WebSocket yang cukup panjang.
  2. Sticky session tidak aktif, sehingga paket HTTP upgrade WebSocket mendarat di pod kontainer yang berbeda dari inisialisasi awal.
* **Solusi**: Konfigurasikan Ingress annotation:
  ```yaml
  # Contoh Traefik Ingress Route
  traefik.ingress.kubernetes.io/affinity: "true"
  traefik.ingress.kubernetes.io/session-cookie-name: "SHINY_STICKY"
  # Set timeout koneksi WebSocket ke 3600s
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum melakukan rilis ke lingkungan Production:

- [ ] **12-Factor App Compliance**: Seluruh kredensial rahasia (DB host, user, password, JWT Secret) dimuat via `Sys.getenv()` dan tidak ada rahasia yang di-commit ke repositori Git.
- [ ] **Worker Plan Isolation**: Rencana konkurensi diatur secara eksplisit menggunakan `future::plan(future::multisession, workers = as.numeric(Sys.getenv("WORKER_COUNT", 2)))`.
- [ ] **Standardized Error Responses**: Seluruh respon error HTTP menggunakan format payload terstruktur yang konsisten (misal: RFC 7807 *Problem Details*) yang memuat `request_id` untuk penelusuran log.
- [ ] **SQL Sanitization**: 100% kueri SQL menggunakan *parameterized queries* (`DBI::dbGetQuery(conn, sql, params = list(...))`), tidak ada konkatenasi string SQL mentah.
- [ ] **Liveness & Readiness Probes**: Terdapat pemisahan endpoint `/healthz` (liveness: mengecek ketersediaan proses R) dan `/ready` (readiness: memverifikasi bahwa pool koneksi DB dan aset model telah selesai dimuat ke RAM).
- [ ] **Non-root Container Execution**: Kontainer R Docker tidak berjalan sebagai `USER root`, melainkan sebagai pengguna terbatas sistem (misal: `USER rstudio` atau `USER nonroot`).
- [ ] **Graceful Shutdown**: Mengimplementasikan penanganan sinyal `SIGTERM` untuk menutup *database connection pool* dan menyelesaikan *active inflight requests* sebelum pod dimatikan paksa.

---

### 12. Hands-on Practice

Implementasi kontainerisasi produksi berkinerja tinggi. Seluruh artefak proyek ini ditempatkan pada direktori `hands-on/m02/`.

#### Langkah 1: Struktur Proyek
Buat struktur direktori berikut di terminal:
```bash
mkdir -p hands-on/m02/app
cd hands-on/m02
```

#### Langkah 2: Kode Aplikasi API (`hands-on/m02/app/api.R`)
```r
library(plumber)
library(promises)
library(future)
library(logger)

# Alokasi worker berdasarkan CPU core
future::plan(future::multisession, workers = 2)

logger::log_layout(logger::layout_json())
logger::log_appender(logger::appender_stdout)

#* @apiTitle Production Ingestion API
#* @apiDescription Enterprise-grade asynchronous Plumber runtime.

#* @filter tracing
function(req, res) {
  req_id <- req$HTTP_X_REQUEST_ID
  if (is.null(req_id) || req_id == "") {
    req_id <- paste0("gen_", as.hexmode(sample(1e6:9e6, 1)))
  }
  req$request_id <- req_id
  res$setHeader("X-Request-ID", req_id)
  plumber::forward()
}

#* Liveness Probe
#* @get /healthz
function(res) {
  list(status = "UP")
}

#* Asynchronous Heavy Analytics Simulation
#* @get /api/v1/forecast
#* @param days:int Jumlah hari prediksi
function(req, res, days = 7) {
  num_days <- as.numeric(days)
  req_id <- req$request_id
  
  if (is.na(num_days) || num_days <= 0) {
    res$status <- 400
    return(list(error = "INVALID_PARAM", message = "Nilai 'days' harus integer positif."))
  }
  
  future::future({
    # Simulasi estimasi Monte Carlo
    Sys.sleep(1) # Beban kerja I/O atau komputasi
    simulated_values <- cumsum(rnorm(num_days, mean = 0.5, sd = 2))
    simulated_values
  }) %...>% (function(val) {
    list(
      status = "SUCCESS",
      meta = list(request_id = req_id),
      data = list(projection = val)
    )
  }) %...!% (function(err) {
    res$status <- 500
    logger::log_error(request_id = req_id, message = err$message)
    list(status = "FAIL", error = err$message)
  })
}
```

#### Langkah 3: Script Bootstrapper Runtime (`hands-on/m02/app/entrypoint.R`)
```r
library(plumber)
library(logger)

PORT <- as.numeric(Sys.getenv("PORT", "8080"))
HOST <- Sys.getenv("HOST", "0.0.0.0")

logger::log_info(message = "Bootstrapping Plumber API Engine...", port = PORT, host = HOST)

pr <- plumber::pr("app/api.R")
pr$run(host = HOST, port = PORT, swagger = FALSE)
```

#### Langkah 4: Dockerfile Enterprise Multi-Stage (`hands-on/m02/Dockerfile`)
```dockerfile
# Menggunakan base image R teruji
FROM rocker/r-ver:4.3.2

# Instal dependensi sistem Linux yang dibutuhkan
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libsodium-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Setup non-root execution user
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

WORKDIR /home/appuser/service

# Instalasi packages R
RUN R -e "install.packages(c('plumber', 'promises', 'future', 'logger', 'jsonlite'), repos='https://cloud.r-project.org/')"

# Salin aset aplikasi
COPY app/ ./app/

# Set kepemilikan file ke user non-root
RUN chown -R appuser:appuser /home/appuser/service

USER appuser

EXPOSE 8080

# Environment variables bawaan
ENV HOST=0.0.0.0
ENV PORT=8080

ENTRYPOINT ["Rscript", "app/entrypoint.R"]
```

#### Langkah 5: Eksekusi dan Verifikasi Build
Jalankan perintah berikut di direktori `hands-on/m02/`:
```bash
# 1. Build image Docker
docker build -t r-enterprise-api:latest .

# 2. Jalankan kontainer
docker run -d --name r-api-prod -p 8080:8080 r-enterprise-api:latest

# 3. Uji liveness endpoint
curl -i http://localhost:8080/healthz

# 4. Uji endpoint asinkron dengan injeksi Request-ID
curl -i -H "X-Request-ID: test-trace-001" "http://localhost:8080/api/v1/forecast?days=5"

# 5. Periksa structured JSON log dari kontainer
docker logs r-api-prod

# 6. Bersihkan kontainer
docker rm -f r-api-prod
```

---

### 13. Exercise

#### Level Easy
Konversikan skrip fungsi pemodelan linier berikut menjadi handler endpoint Plumber asinkron menggunakan operator `%...>%` dan `future::future()`:
```r
train_lm <- function(data) {
  Sys.sleep(2)
  model <- lm(mpg ~ wt + hp, data = mtcars)
  coef(model)
}
```
*Tujuan*: Handler tidak boleh memblokir thread saat jeda 2 detik berjalan.

#### Level Medium
Buat sebuah filter middleware Plumber yang:
1. Membaca header `X-Consumer-Key`.
2. Mencocokkan nilai key tersebut dengan vektor validasi yang disimpan di variabel environment (`ALLOWED_KEYS="KEY1,KEY2,KEY3"`).
3. Jika cocok, tambahkan waktu mulai presisi tinggi (`nanotime` atau `Sys.time()`) ke atribut `req`.
4. Jika tidak cocok, tolak request dengan status code `401 Unauthorized` dalam payload JSON standar.

#### Level Hard
Rancang arsitektur aplikasi Shiny modular lengkap dengan kriteria:
1. Terdapat modul UI/Server: `dataFilterModule` dan `timeSeriesPlotModule`.
2. Komunikasi antar modul tidak boleh menggunakan variabel global, melainkan via `reactiveVal` atau `reactive` parameters (*dependency injection pattern*).
3. Data ditarik dari SQLite database menggunakan koneksi `pool` yang dioper ke modul server.
4. Menerapkan isolasi visualisasi sehingga pergeseran slider waktu di UI tidak mengeksekusi ulang kueri database utama (*decoupling data fetch vs rendering*).

---

### 14. Challenge

**Skenario**: Sistem *Dynamic Pricing Engine* untuk platform ride-hailing berskala nasional yang dikembangkan menggunakan R.
* **Kebutuhan**:
  - API wajib melayani hingga 800 *Pricing Inference requests per second*.
  - Latensi maksimal toleransi P99 adalah 150 ms.
  - Model inferensi menggunakan ensemble `ranger` (Random Forest) yang memakan RAM 400 MB per instance.
  - Setiap request harus merekam jejak evaluasi fitur ke log stream (Kafka/Prometheus).
* **Tantangan Arsitektur**:
  1. Bagaimana Anda merancang topologi Pod Kubernetes (konfigurasi CPU, RAM Limit/Request, dan jumlah worker `future`) untuk menghindari proses R terkena *eviction* atau *OOMKilled*?
  2. Bagaimana memitigasi overhead alokasi memori Linux saat proses R melakukan *forking* (`multicore` vs `multisession`) pada container yang memiliki batasan cgroups?
  3. Susun spesifikasi konfigurasi Docker, Kubernetes Deployment YAML (lengkap dengan *readinessProbe* berbasis fungsional inferensi), dan HPA (*Horizontal Pod Autoscaler*) untuk mengatasi fluktuasi lonjakan traffic tak terduga.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa runtime bawaan R bersifat *single-threaded*?**
   * *A.* Karena R tidak mendukung kompilasi C++.
   * *B.* Karena R engine dibangun di atas satu heap environment dan stack call tunggal yang tidak memiliki locking mekanisme *thread-safe* bawaan.
   * *C.* Karena sistem operasi melarang komputasi paralel pada bahasa scripting.
   * *D.* Karena paket `httpuv` membatasi eksekusi R menjadi satu thread saja.
2. **Apa peran utama dari package `promises` dalam pengembangan API Plumber?**
   * *A.* Mengompilasi kode R menjadi bahasa assembly.
   * *B.* Memisahkan thread utama `httpuv` dari operasi blocking sehingga API dapat terus menerima koneksi TCP baru.
   * *C.* Menghubungkan R langsung ke Redis Cache.
   * *D.* Melakukan deployment otomatis ke cloud server.
3. **Mengapa penggunaan `DBI::dbConnect()` secara langsung di dalam setiap fungsi handler Plumber dianggap sebagai anti-pattern di lingkungan produksi?**
   * *A.* Karena DBI tidak mendukung database PostgreSQL.
   * *B.* Karena DBI mematikan proses R jika terjadi query error.
   * *C.* Karena biaya overhead *handshake* koneksi berulang dapat menyebabkan degradasi latensi tinggi dan kehabisan slot koneksi database.
   * *D.* Karena koneksi DBI tidak dapat membaca data bertipe JSON.
4. **Apa fungsi utama dari `plumber::forward()` dalam sebuah filter?**
   * *A.* Mengalihkan koneksi ke domain URL yang berbeda.
   * *B.* Meneruskan siklus request ke tahapan/filter/endpoint berikutnya dalam pipeline Plumber.
   * *C.* Me-restart proses kontainer secara berkala.
   * *D.* Mengirimkan output respon JSON ke klien secara instan.
5. **Pada infrastruktur load balancing, mengapa aplikasi Shiny membutuhkan mekanisme *Sticky Sessions* sedangkan API Plumber pada umumnya tidak?**
   * *A.* Karena Shiny tidak mendukung protokol HTTP/2.
   * *B.* Karena Shiny menyimpan memori *stateful* sesi pengguna (termasuk WebSocket) langsung di dalam memori proses pod R tertentu.
   * *C.* Karena Plumber tidak bisa dijalankan di atas protokol HTTPS.
   * *D.* Karena Shiny memerlukan bandwidth jaringan yang jauh lebih besar.

#### Bagian 2: Intermediate (5 Soal)
6. **Perhatikan skenario berikut:**
   ```r
   #* @get /data
   function() {
     val <- future::future({
       res <- download_huge_file()
       parse(res)
     })
     return(val)
   }
   ```
   **Apa kegagalan sistem yang terjadi pada implementasi di atas jika operator `%...>%` tidak digunakan?**
   * *A.* Kode akan menghasilkan syntax error kompilasi R.
   * *B.* Plumber akan langsung mengembalikan representasi serialisasi dari objek *future* yang belum ter-resolve ke klien, bukan data hasil komputasinya.
   * *C.* Background worker akan langsung mengalami crash seketika.
   * *D.* Port API akan terblokir dan mati.
7. **Bagaimana cara kerja package `pool` dalam mendeteksi dan memulihkan koneksi database yang terputus (stale/broken connection)?**
   * *A.* `pool` melakukan validasi keaktifan koneksi menggunakan uji ping internal sebelum menyerahkan soket koneksi ke aplikasi (`checkout validation`).
   * *B.* `pool` me-restart seluruh proses R jika salah satu koneksi terputus.
   * *C.* `pool` bergantung sepenuhnya pada laporan error dari browser klien.
   * *D.* `pool` tidak memvalidasi, melainkan membiarkan query melempar *fatal exception*.
8. **Ketika membangun aplikasi Shiny berskala besar, apa keuntungan utama menerapkan konsep *Shiny Modules* menggunakan `NS()`?**
   * *A.* Meningkatkan kecepatan visualisasi plot CSS secara drastis.
   * *B.* Menjamin isolasi ID *input* dan *output* (namespacing), sehingga komponen logika dapat digunakan kembali (*reusable*) tanpa konflik state ID.
   * *C.* Mengurangi konsumsi memori server menjadi nol.
   * *D.* Menghilangkan ketergantungan pada runtime R.
9. **Apa bahaya dari penggunaan `future::plan(multicore)` di dalam lingkungan kontainer Linux yang menjalankan library multithreaded (seperti OpenBLAS atau MKL)?**
   * *A.* Terjadinya *deadlock* sistem akibat inkonsistensi status memori saat proses di-fork oleh POSIX sub-process.
   * *B.* Ukuran image Docker membengkak lebih dari 10 GB.
   * *C.* Request ID akan terduplikasi di seluruh klien.
   * *D.* Koneksi SSL/TLS database akan terdekripsi otomatis.
10. **Bagaimana cara yang tepat untuk merekam jejak (*tracing*) satu request transaksi lintas beberapa worker pada arsitektur asynchronous R?**
    * *A.* Mengandalkan PID proses sistem operasi saja.
    * *B.* Meng-inject UUID `Request-ID` unik di layer middleware, lalu meneruskannya secara eksplisit ke dalam closure `future::future()` dan format log terstruktur.
    * *C.* Mencatat seluruh request ke dalam file teks `.txt` statis di root directory.
    * *D.* Mematikan background worker dan beralih ke mode sinkron.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**:
    Tim Anda meluncurkan API scoring menggunakan Docker di Kubernetes. Setelah 4 jam berjalan stabil, satu per satu pod kontainer mati dengan exit code `137`. Berdasarkan inspeksi log Kubernetes, pod dimatikan oleh sistem dengan status `OOMKilled`. 
    *Konfigurasi kontainer*: Base image R, `future::plan(multisession, workers = 8)`, memori limit pod = 2GB. Model yang dimuat ke memori berukuran 350 MB.
    **Apa akar masalah arsitekturalnya dan langkah perbaikan terbaiknya?**
12. **Skenario Kasus 2**:
    Aplikasi Shiny menampilkan metrik analitik finansial secara *real-time*. Pada dashboard tersebut, Anda menggunakan global variable `global_balance <<- 0` di luar fungsi server untuk menghitung akumulasi seluruh nilai transaksi.
    **Apa resiko enterprise-grade data security & integrity yang timbul dari desain ini, dan bagaimana solusinya?**
13. **Skenario Kasus 3**:
    Sebuah Plumber API async dirancang untuk membaca database eksternal melalui koneksi `pool`. Namun, di bawah uji beban konkurensi (load testing) 100 concurrent virtual users, latensi API melonjak drastis dan log dipenuhi pesan:
    `Error in poolCheckout(pool): Timeout expired while waiting for a connection to become available`.
    **Langkah diagnosa sistem apa saja yang harus diambil untuk mengidentifikasi letak kebocoran koneksi (connection leakage)?**

---

### Jawaban Kuis & Evaluasi

#### Bagian 1: Basic
1. **B** - R runtime beroperasi di atas stack tunggal tanpa memori *locking primitive* bawaan yang aman untuk multi-threading langsung pada objek R.
2. **B** - `promises` bekerja bersama `httpuv` untuk melepaskan thread penerima request utama saat komputasi berlangsung di thread/proses lain.
3. **C** - Pembuatan koneksi TCP dan autentikasi baru secara berulang sangat membebani DB server dan menambahkan latency puluhan milidetik per request.
4. **B** - `plumber::forward()` adalah fungsi kontrol alur internal untuk menyerahkan eksekusi ke filter turunan atau handler target.
5. **B** - Shiny melacak status stateful (graph reaktif, memori UI) yang terikat langsung di instance server tempat sesi dibuka.

#### Bagian 2: Intermediate
6. **B** - Tanpa operator promise `%...>%`, Plumber akan memperlakukan objek *future* sebagai data serial biasa dan mengembalikannya sebelum nilai di dalamnya selesai dihitung.
7. **A** - `pool` menerapkan *checkout validation* otomatis; koneksi yang rusak di tingkat soket akan dibuang dan dibuatkan koneksi baru sebelum dikembalikan ke kode R.
8. **B** - Namespacing via `NS()` mengisolasi ID antar instansiasi modul sehingga tidak terjadi tabrakan *state* di graph reaktif.
9. **A** - POSIX `fork()` yang digunakan oleh `multicore` tidak aman (*not async-signal-safe*) jika dikombinasikan dengan library matematika BLAS/LAPACK yang mengoperasikan thread pool sendiri, memicu hang atau *deadlock*.
10. **B** - Injeksi Request ID eksplisit yang diteruskan ke konteks worker adalah standar korelasi log di sistem terdistribusi.

#### Bagian 3: Solusi Kasus Produksi
11. **Analisis Skenario 1**:
    * **Akar Masalah**: Pola `multisession` menduplikasi proses R latar belakang. Jika 1 worker memakan RAM dasar 100MB + Model 350MB = 450MB, maka 8 worker akan memakan $8 \times 450\text{ MB} = 3.6\text{ GB}$, melebihi limit Kubernetes pod sebesar 2GB. OS Linux OOM Killer langsung mengirim sinyal `SIGKILL` (Exit code 137).
    * **Solusi**: Turunkan jumlah worker per kontainer menjadi 2 atau 3 worker, lalu tingkatkan replikasi Pod horizontal (Kubernetes HPA). Pasang Memory Request: 1.5GB dan Limit: 2GB per Pod.
12. **Analisis Skenario 2**:
    * **Resiko**: Variabel yang didefinisikan dengan assignment super-assignment operator `<<-` di luar server function bersifat *shared across all user sessions* di dalam proses R yang sama. Hal ini memicu kebocoran data sensitif antar nasabah (*cross-session contamination*) dan potensi manipulasi data tak terkontrol (*race condition*).
    * **Solusi**: Pindahkan variabel ke dalam lingkup `server <- function(input, output, session)` menggunakan isolasi `reactiveVal(0)`.
13. **Analisis Skenario 3**:
    * **Diagnosa**:
      1. Periksa apakah ada rute API yang memanggil `poolCheckout()` tetapi tidak mengeksekusi `poolReturn()` saat terjadi error logika (biasanya akibat ketiadaan blok `on.exit(poolReturn())`).
      2. Periksa parameter `maxSize` pada pool initialization; sesuaikan kapasitas pool dengan jumlah worker konkuren.
      3. Analisis metrik koneksi database melalui `pool$counters` untuk melihat selisih antara *allocated* dan *free* connections.
      4. Periksa kueri lambat di database (*long running queries*) yang memegang koneksi terlalu lama menggunakan `pg_stat_activity`.

---

### 16. Summary

1. **R Runtime Concurrency**: R bersifat *single-threaded*, namun integrasi antara `httpuv`, `promises`, dan `future` memungkinkan komputasi off-process non-blocking berkinerja tinggi.
2. **Resource Management**: Pola pembuatan koneksi ad-hoc adalah penyebab utama degradasi sistem; adopsi *connection pooling* via `pool` bersifat wajib untuk sistem database skala produksi.
3. **Architecture Decoupling**: Aplikasi analitik analitis harus dipisahkan: Plumber melayani layer data/API secara *stateless*, sementara Shiny menangani visualisasi interaktif secara *stateful* di balik *Sticky Ingress*.
4. **Resilience & Observability**: Lingkungan enterprise mewajibkan ekosistem kontainer yang mengimplementasikan *health probes* (`/healthz`, `/ready`), manajemen sinyal POSIX, dan *structured logging* ber-korelasi `Request-ID` untuk mempermudah monitoring operasional.