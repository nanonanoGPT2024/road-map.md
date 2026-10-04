# BAB 06: Sistem Objek Enterprise
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Internal Dispatch R**: Menginspeksi struktur C-level internal (`SEXP`) dari sistem objek R (S3, S4, R6, dan vctrs/S7), memahami mekanisme pointer dan memory layout, serta menelusuri alur eksekusi method dispatch via R runtime bytecode engine.
2. **Merancang Arsitektur Berorientasi Objek Produksi**: Mengimplementasikan paradigma Hybrid S4/R6 untuk pipeline analitik skala besar, memisahkan domain immutability (pemodelan matematis S4/vctrs) dari stateful lifecycle management (koneksi database, worker pool, telemetry R6).
3. **Mengoptimalkan Kinerja dan Mengeliminasi Overhead Memori**: Mengatasi isu *copy-on-modify* pada objek S3/S4 besar, mengontrol siklus hidup memori menggunakan referensi pointer lingkungan (Environment/External Pointer), serta mencegah *memory leak* akibat *circular references* pada R6.
4. **Membangun Domain Model Enterprise yang Type-Safe**: Mengembangkan sistem kontrak kelas yang memvalidasi integritas data runtime secara deterministik menggunakan *validity methods* S4 dan *custom casting/coercion* vctrs.
5. **Mengimplementasikan Enterprise Design Patterns**: Menerapkan pattern *Repository*, *Strategy*, *Unit of Work*, dan *Observer* menggunakan sistem objek modern di lingkungan produksi R bersertifikasi enterprise.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
* Fundamental sistem tipe dasar R: `environment`, `list`, `pairlist`, `closure`, dan representasi tipe C `SEXP`.
* Konsep dasar S3 (Generic functions, class attribute) dan R6 (Public/private members, `$new()` instantiation).
* Konsep pemodelan memori R: Semantik *Copy-on-Modify* (CoM), *reference counting* (`NAMED` / `REFCNT` flags), dan pengoperasian paket `lobstr`.
* Rekayasa perangkat lunak: Prinsip SOLID, clean architecture, exception handling (`withCallingHandlers`, `tryCatch`), serta pengemasan paket R standar (`NAMESPACE`, `DESCRIPTION`).

---

### 3. Concept & Internal Architecture

Sistem objek dalam R bukanlah monolitik, melainkan evolusi berlapis dari arsitektur fungsional berbasis C.

```
       +-----------------------------------------------------------+
       |                     R User Runtime                        |
       +-----------------------------------------------------------+
         |                       |                       |
   [ S3 Dispatch ]         [ S4 Dispatch ]         [ R6 Class ]
   attr(x, "class")       methods::selectMethod    env-based pointer
         |                       |                       |
+------------------------------------------------------------------+
|                     R Core Engine (C-Level)                      |
|                                                                  |
|   +----------------------------------------------------------+   |
|   |                  SEXP (S-Expression)                     |   |
|   |  - sxpinfo_struct (gc_mark, type, refcnt, attrib, etc.)  |   |
|   |  - union { vecsxp, listsxp, envsxp, symsxp, ... }        |   |
|   +----------------------------------------------------------+   |
|                                                                  |
|   S3:    SEXP tipe vektor/list + ATTRIB("class")                 |
|   S4:    SEXP tipe S4SXP (atau ENVSXP) + ATTRIB(slot-names)      |
|   R6:    SEXP tipe ENVSXP (Pass-by-Reference; NO Copy-on-Modify) |
+------------------------------------------------------------------+
```

#### Struktur C SEXP dan Penanganan Tipe Objek
Di dalam runtime C R (`Rinternals.h`), setiap entitas adalah pointer menuju `SEXPREC`:
```c
struct sexpinfo_struct {
    SEXPTYPE type : 5;
    unsigned int scalar : 1;
    unsigned int altrep : 1;
    unsigned int gp : 16;
    unsigned int mark : 1;
    unsigned int debug : 1;
    unsigned int trace : 1;
    unsigned int spare : 1;
    unsigned int gcgen : 1;
    unsigned int gc_cls : 3;
    unsigned int named : 16; /* Penentu Copy-on-Modify */
};

struct SEXPREC {
    struct sexpinfo_struct sxpinfo;
    struct SEXPREC *attrib;
    struct SEXPREC *gengc_next_node;
    struct SEXPREC *gengc_prev_node;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;
        struct envsxp_struct envsxp;
        struct vecsxp_struct vecsxp;
        /* ... tipe lainnya ... */
    } u;
};
```

1. **S3 Internals (`UseMethod`)**:
   S3 adalah sistem objek berbasis *ad-hoc polymorphism*. Ketika fungsi generik mengeksekusi `UseMethod("fun", x)`, R runtime membaca pointer `ATTRIB(x)`, mencari tag string `"class"`, lalu menyusun string pencarian: `fun.<class_name>` di tabel simbol global maupun namespace pengekspor. Jika objek memiliki vektor kelas `c("class_a", "class_b")`, resolusi pencarian berjalan secara linear: `fun.class_a` -> `fun.class_b` -> `fun.default`. Operasi ini cepat namun tidak memiliki jaminan compile-time maupun runtime typing verification.

2. **S4 Internals (`R_do_slot` & Table Cache)**:
   Objek S4 memiliki tag internal `SEXPTYPE` bernilai `S4SXP` (atau `OBJSXP`). Slot-slot data disimpan sebagai atribut (`ATTRIB`), namun metadata kelas dikelola oleh paket `methods`. Pemanggilan generik S4 (`standardGeneric("fun")`) mengaktifkan algoritma C-level dispatch yang mengevaluasi multi-argumen (*multiple dispatch*). R melakukan hashing terhadap kombinasi tipe argumen dan mengecek *dispatch table cache*. Jika cache miss, R menghitung jarak inheritance terkecil pada directed acyclic graph (DAG) hierarki kelas, mengompilasi method, lalu memasukkannya ke cache dispatch. Validitas struktur dijamin oleh fungsi C `R_check_class_and_super` dan metode validasi pengguna.

3. **R6 Internals (`ENVSXP` Encapsulation)**:
   R6 tidak menggunakan sistem atribut S3/S4 untuk enkapsulasi state, melainkan mengeksploitasi semantik *pass-by-reference* dari tipe `ENVSXP` (Environment). Objek R6 adalah `ENVSXP` yang dibungkus atribut S3 `"R6"`. Properti dan fungsi metode disimpan langsung sebagai *bindings* di dalam environment tersebut atau di *enclosing parent environment* (inheritance chain). Variabel privat (`private`) dipisahkan ke dalam environment independen yang diproteksi dari akses luar melalui *lexical scoping*, di mana fungsi-fungsi publik memiliki enclosing environment yang dapat melihat environment privat, namun environment privat tidak diekspos ke antarmuka pemanggil publik.

4. **vctrs & S7 Foundation**:
   Sistem modern (`vctrs`) memformalkan komputasi tipe berbasis vektor di atas S3 dengan aturan aljabar tipe: `vec_ptype2()` (mencari *common type*) dan `vec_cast()` (melakukan *type coercion*). S7 menggabungkan kestabilan formalitas S4 dengan performa S3 melalui spesifikasi properties, dispatch ganda/jamak terstandarisasi, dan C-level acceleration layer.

---

### 4. Why & What

| Dimensi | S3 | S4 | R6 | Modern S7 / vctrs |
| :--- | :--- | :--- | :--- | :--- |
| **Paradigma** | Functional OO | Formal Functional OO | Encapsulated / Classical OO | Formal Functional OO Modern |
| **State Semantics** | Value (Copy-on-Modify) | Value (Copy-on-Modify) | Reference (In-place Mutation) | Value (Copy-on-Modify) |
| **Dispatch Mechanism** | Single-argument runtime | Multiple-argument DAG cache | Dynamic Environment lookup | Fast Multiple dispatch |
| **Enkapsulasi** | Terbuka (Convention) | Formal via Accessor/Slot | Ketat (Public, Private, Active) | Terdefinisi via Properties |
| **Kasus Penggunaan Enterprise** | Ekstensi pustaka, print, generic IO ringan | Komputasi kuantitatif, biostatistik, kontrak data ketat | Pipeline stateful, koneksi DB/gRPC, worker agent | Vector-native custom types, domain modeling generasi baru |

#### Mengapa Tidak Menggunakan Satu Sistem Saja?
Perusahaan sering kali terjebak dalam kesalahan arsitektur: mencoba memaksakan pemodelan analitik murni ke dalam R6 (mengorbankan optimasi vektor, fungsi murni, dan idempotensi), atau sebaliknya, memaksakan pengelolaan state koneksi database dan pooling thread ke dalam S3/S4 (menyebabkan *unintended memory copies* berukuran puluhan gigabyte dan race condition pada mutating states). Arsitektur R enterprise membagi domain menjadi:
* **Mathematical & Data Domain (Immutable)**: Gunakan S4 atau vctrs/S7. Setiap transformasi menghasilkan instans baru yang deterministik tanpa efek samping (*pure functional transformation*).
* **Infrastructure & Orchestration Domain (Stateful)**: Gunakan R6. Mengelola koneksi jaringan, locking file, caching, dan pipeline orchestration state.

---

### 5. How (Workflow detail)

Alur desain sistem objek enterprise mengikuti siklus kontraktual yang ketat:

```
[ Domain Definition ]
        |
        v
+-------------------------------+
|  1. S4 / vctrs Data Schema    | ---> Validasi invariansi matematis (assert types, dimensions)
+-------------------------------+
        |
        v
+-------------------------------+
|  2. Serialization Boundaries  | ---> Serialization/Deserialization ke Parquet/Protobuf/JSON
+-------------------------------+
        |
        v
+-------------------------------+
|  3. R6 Infrastructure Service | ---> Service menerima S4 schema, mengatur I/O stateful
+-------------------------------+
        |
        v
+-------------------------------+
|  4. Execution & Teardown      | ---> Finalizer R6 membersihkan koneksi, lock, external pointers
+-------------------------------+
```

1. **Definisi Kontrak Tipe (S4/vctrs)**: Tentukan kelas entitas domain. Tulis fungsi `setValidity()` S4 atau `vec_assert()` untuk menjamin bahwa tidak ada objek yang dapat diciptakan dalam state corrupt.
2. **Implementasi Generic Methods**: Tulis generik formal dengan `setGeneric()` atau `S7::new_generic()`. Tentukan signature types secara eksplisit.
3. **Konstruksi Orchestrator (R6)**: Buat kelas orkestrasi yang mengelola state. Injeksi dependensi (seperti logger, connection handler, credentials) via constructor `initialize()`.
4. **Implementasi Active Bindings**: Gunakan *active bindings* R6 untuk properti terhitung (*computed properties*) atau validasi *setter-getter* transparan tanpa membocorkan mutasi langsung ke state internal.
5. **Lifecycle Management**: Implementasikan *finalizer* (`finalize()`) pada R6 untuk menangani *resource acquisition is initialization* (RAII), memastikan soket network atau handle database ditutup ketika objek di-garbage collect oleh R.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
* **S3**: Seperti memberi stempel nama pada kardus tertutup. Siapa pun bisa menambahkan stempel baru, menimpa isinya, atau salah menempelkan label tanpa ada inspeksi bandara.
* **S4**: Seperti kontrak legal notarial. Ada spesifikasi setiap klausul (slot). Jika ada satu klausul tidak sesuai tipe data, dokumen dianggap batal demi hukum (*invalid*).
* **R6**: Seperti brankas fisik dengan kunci kombinasi. Brankas berada di satu ruangan tetap (alamat memori tetap). Anda tidak memfotokopi seluruh brankas saat memasukkan dokumen ke dalamnya; Anda hanya membuka pintu lewat izin brankas dan memodifikasi dokumen di dalamnya secara langsung.

#### Diagram Interaksi Memory Layout & Dispatch Resolusi

```
S3/S4 Memory Model (Copy-on-Modify):
Data [A] (REFCNT=1)  --- assignment: B <- A ---> Data [A] (REFCNT=2)
Modifikasi B@slot    -------------------------> Data [A] (REFCNT=1)
                                                 Data [B] (Baru di-alokasi, REFCNT=1)

R6 Memory Model (Pass-by-Reference):
Instans R6 [Address: 0x7fa2] (Public/Private Environment)
          ^                       ^
          |                       |
     Pointer Ref 1           Pointer Ref 2
 (Objek yang sama, modifikasi dari Pointer Ref 1 terefleksi langsung di Pointer Ref 2)

S4 Multiple Dispatch Matrix (Contoh: Combine Matrix):
+-----------------------+-----------------------+---------------------------+
| Arg 1 \ Arg 2         | MatrixNumeric         | SparseMatrix              |
+-----------------------+-----------------------+---------------------------+
| MatrixNumeric         | method_dense_dense    | method_dense_sparse       |
| SparseMatrix          | method_sparse_dense   | method_sparse_sparse      |
+-----------------------+-----------------------+---------------------------+
Resolusi C-Level: O(1) via hashing cache setelah komputasi jarak inherintansi awal.
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Komparasi Copy-on-Modify vs In-Place Mutation

```r
library(lobstr)
library(R6)

# 1. S3 Copy-on-Modify
data_s3 <- list(payload = 1:1000)
class(data_s3) <- "s3_payload"
cat("Alamat awal S3:", "\n")
print(obj_addr(data_s3))

data_s3_copy <- data_s3
data_s3_copy$payload[1] <- 999L
cat("Alamat S3 setelah mutasi (berbeda = memory duplicated):", "\n")
print(obj_addr(data_s3_copy))

# 2. R6 Reference Semantics
PayloadR6 <- R6Class("PayloadR6",
  public = list(
    payload = NULL,
    initialize = function(payload) self$payload <- payload,
    update_first = function(val) self$payload[1] <- as.integer(val)
  )
)

inst_r6 <- PayloadR6$new(1:1000)
cat("Alamat awal R6:", "\n")
print(obj_addr(inst_r6))

inst_r6_ref <- inst_r6
inst_r6_ref$update_first(999L)
cat("Alamat R6 setelah mutasi (identik = pointer shared):", "\n")
print(obj_addr(inst_r6_ref))
stopifnot(identical(inst_r6$payload[1], 999L))
```

#### B. Practical Example: Enterprise Portfolio Risk Pipeline (Hybrid S4 & R6)

Contoh nyata industri manajemen aset kuantitatif: S4 merepresentasikan instrumen portofolio yang immutable dan tervalidasi matematis; R6 bertindak sebagai *Engine Runner* yang mengelola state eksekusi, cache, dan dependensi logging.

```r
library(methods)
library(R6)

# ==============================================================================
# 1. DOMAIN LAYER (IMMUTABLE S4 DATA OBJECTS)
# ==============================================================================

setClass(
  "FinancialInstrument",
  slots = c(
    ticker = "character",
    notional = "numeric",
    currency = "character"
  ),
  prototype = list(
    ticker = NA_character_,
    notional = 0.0,
    currency = "USD"
  )
)

setValidity("FinancialInstrument", function(object) {
  errors <- character()
  if (length(object@ticker) != 1 || nchar(object@ticker) == 0) {
    errors <- c(errors, "Ticker harus berupa string non-kosong skalar.")
  }
  if (length(object@notional) != 1 || object@notional < 0) {
    errors <- c(errors, "Notional harus skalar numerik non-negatif.")
  }
  if (!object@currency %in% c("USD", "EUR", "IDR", "SGD")) {
    errors <- c(errors, paste("Mata uang tidak didukung:", object@currency))
  }
  if (length(errors) == 0) TRUE else errors
})

setClass(
  "PortfolioSnapshot",
  slots = c(
    snapshot_id = "character",
    timestamp = "POSIXct",
    instruments = "list"
  )
)

setValidity("PortfolioSnapshot", function(object) {
  errors <- character()
  valid_instruments <- vapply(object@instruments, function(x) is(x, "FinancialInstrument"), logical(1))
  if (!all(valid_instruments)) {
    errors <- c(errors, "Semua elemen dalam 'instruments' harus merupakan instans S4 'FinancialInstrument'.")
  }
  if (length(errors) == 0) TRUE else errors
})

# S4 Generic & Method Dispatch untuk Valuasi Portofolio
setGeneric("calculateExposure", function(entity, fx_rate) {
  standardGeneric("calculateExposure")
})

setMethod("calculateExposure", signature(entity = "FinancialInstrument", fx_rate = "numeric"),
  function(entity, fx_rate) {
    entity@notional * fx_rate
  }
)

setMethod("calculateExposure", signature(entity = "PortfolioSnapshot", fx_rate = "numeric"),
  function(entity, fx_rate) {
    sum(vapply(entity@instruments, calculateExposure, numeric(1), fx_rate = fx_rate))
  }
)

# ==============================================================================
# 2. INFRASTRUCTURE & SERVICE LAYER (STATEFUL R6 ENGINE)
# ==============================================================================

RiskAnalyticsEngine <- R6Class("RiskAnalyticsEngine",
  private = list(
    ..engine_id = character(0),
    ..is_initialized = logical(0),
    ..execution_history = list(),
    ..fx_rates = numeric(0),
    
    log_internal = function(msg) {
      cat(sprintf("[%s] [ENGINE: %s] %s\n", Sys.time(), private$..engine_id, msg))
    }
  ),
  public = list(
    initialize = function(engine_id, initial_fx = c("USD" = 1.0, "IDR" = 0.000065)) {
      if (missing(engine_id) || nchar(engine_id) == 0) {
        stop("Engine ID valid diperlukan.")
      }
      private$..engine_id <- engine_id
      private$..fx_rates <- initial_fx
      private$..is_initialized <- TRUE
      private$log_internal("Inisialisasi Risk Engine berhasil.")
    },
    
    update_fx = function(currency, rate) {
      stopifnot(is.numeric(rate) && rate > 0)
      private$..fx_rates[currency] <- rate
      private$log_internal(sprintf("FX Rate untuk %s diperbarui menjadi %f", currency, rate))
      invisible(self)
    },
    
    execute_portfolio_risk = function(snapshot) {
      if (!inherits(snapshot, "PortfolioSnapshot")) {
        stop("Parameter snapshot wajib berupa instans S4 'PortfolioSnapshot'.")
      }
      
      private$log_internal(sprintf("Memproses validasi risk untuk Snapshot: %s", snapshot@snapshot_id))
      
      total_exposure_base <- 0
      for (inst in snapshot@instruments) {
        fx <- private$..fx_rates[inst@currency]
        if (is.na(fx)) {
          stop(sprintf("Kurs untuk mata uang %s tidak ditemukan di engine cache.", inst@currency))
        }
        total_exposure_base <- total_exposure_base + calculateExposure(inst, fx)
      }
      
      execution_log <- list(
        id = snapshot@snapshot_id,
        timestamp = Sys.time(),
        exposure_usd = total_exposure_base,
        instrument_count = length(snapshot@instruments)
      )
      
      private$..execution_history <- append(private$..execution_history, list(execution_log))
      return(execution_log)
    },
    
    finalize = function() {
      private$log_internal("Membersihkan resource dan mematikan engine instance.")
    }
  ),
  active = list(
    engine_status = function() {
      list(
        engine_id = private$..engine_id,
        initialized = private$..is_initialized,
        total_executions = length(private$..execution_history)
      )
    }
  )
)

# ==============================================================================
# 3. PIPELINE INTEGRATION RUNTIME
# ==============================================================================

# Pembuatan Entity S4 (Deterministic, Type Safe)
bond <- new("FinancialInstrument", ticker = "ID_GOV_10Y", notional = 1000000000, currency = "IDR")
equity <- new("FinancialInstrument", ticker = "AAPL", notional = 50000, currency = "USD")

portfolio <- new("PortfolioSnapshot",
                 snapshot_id = "PORT-GLOBAL-001",
                 timestamp = Sys.time(),
                 instruments = list(bond, equity))

# Orkestrasi via R6 Engine
engine <- RiskAnalyticsEngine$new("PROD-RISK-WORKER-01")
risk_metric <- engine$execute_portfolio_risk(portfolio)
print(risk_metric)
print(engine$engine_status)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Scoring Telemetri IoT Otomotif Nasional memproses 500.000 streaming events per menit. Setiap event membawa payload sensor kendaraan (GPS, RPM, Braking Pressure, Acceleration).

#### Problem Statement
Pipeline analitik awal dibangun murni menggunakan S3 data.frames dan method dispatch standar. Saat memproses streaming micro-batch (per 5 detik):
1. **Memory Bloat**: Garbage collection (GC) memicu latency freeze hingga 12 detik karena semantik copy-on-modify menduplikasi data payload pada setiap rantai transformasi fungsional.
2. **Type Desync**: S3 tidak mampu memvalidasi perubahan schema dari perangkat IoT firmware versi lama, menyebabkan downstream crash secara acak (*silent type coercion: integer -> character*).

#### Solusi Arsitektural (The Clean OOP Architecture)
Merestrukturisasi pipeline dengan pemisahan tanggung jawab yang tajam:
1. **Core Types (`vctrs` / S4 record)**: Membuat representasi vektor terkustomisasi (`SensorVector`) menggunakan `vctrs` yang mengalokasikan memory contiguous C array, mencegah duplikasi atribut per baris dan mematikan silent coercion.
2. **State Machine (`R6`)**: Membuat `TelemetrySessionManager` berbasis R6 untuk menjaga koneksi persistent ke Apache Kafka dan Redis cache state driver secara *in-place*.
3. **Double Dispatch Driver Evaluation**: Menerapkan S4 multiple dispatch untuk resolusi scoring berdasarkan kombinasi `DeviceFirmwareVersion` dan `TelemetryEventClass`.

```r
library(R6)
library(methods)

# 1. Definisi Signature Event Melalui S4
setClass("EventPayload", slots = c(device_id = "character", metrics = "numeric"))
setClass("LegacyEventPayload", contains = "EventPayload")
setClass("ModernEventPayload", contains = "EventPayload")

# 2. Driver Engine Registry via R6
DriverSessionRegistry <- R6Class("DriverSessionRegistry",
  private = list(
    ..storage = NULL,
    ..lock_token = character(0)
  ),
  public = list(
    initialize = function() {
      private$..storage <- new.env(parent = emptyenv(), hash = TRUE)
      private$..lock_token <- UUIDgenerate()
    },
    
    upsert_state = function(driver_id, status_code) {
      assign(driver_id, status_code, envir = private$..storage)
      invisible(self)
    },
    
    get_state = function(driver_id) {
      if (exists(driver_id, envir = private$..storage, inherits = FALSE)) {
        return(get(driver_id, envir = private$..storage, inherits = FALSE))
      }
      return(NULL)
    }
  )
)

# 3. Multiple Dispatch Matrix Processing
setGeneric("processScoring", function(event, session_manager) standardGeneric("processScoring"))

setMethod("processScoring", signature(event = "LegacyEventPayload", session_manager = "DriverSessionRegistry"),
  function(event, session_manager) {
    # Penanganan data telemetry legacy dengan normalisasi khusus
    score <- mean(event@metrics) * 0.85
    session_manager$upsert_state(event@device_id, score)
    return(score)
  }
)

setMethod("processScoring", signature(event = "ModernEventPayload", session_manager = "DriverSessionRegistry"),
  function(event, session_manager) {
    # Telemetry modern dengan kalkulasi direct vectorised
    score <- sqrt(sum(event@metrics^2))
    session_manager$upsert_state(event@device_id, score)
    return(score)
  }
)
```

#### Hasil Metrik Produksi:
* **Garbage Collection Overhead**: Menurun 82% (dari rata-rata 3.2 detik per batch menjadi 0.58 detik).
* **Throughput**: Meningkat dari 45.000 events/detik menjadi 140.000 events/detik per compute node.
* **Pipeline Crash**: Mencapai 0 insiden terkait schema desync selama 90 hari operasional berturut-turut.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off | Mitigasi Kinerja |
| :--- | :--- | :--- | :--- |
| **S4 Strict Validation (`validityMethod`)** | Menjamin integritas data mutlak pada domain sensitif (financial/medical). Mencegah silent bugs. | *Overhead latency*: Validasi dieksekusi setiap kali instans diubah melalui slot accessor konvensional. | Hindari memanggil validasi berulang kali di dalam loop mikro. Validasi saat boundary data masuk, lalu gunakan functional core. |
| **R6 In-Place Reference Mutation** | Mengeliminasi salinan memori Copy-on-Modify. Sangat ideal untuk data streams dan shared states. | Hilangnya sifat fungsional murni (idempotensi). Risiko *unintended state mutation* dan *race condition* jika dieksekusi secara paralel. | Terapkan metode `$clone(deep = TRUE)` saat objek dipassing keluar boundary domain. Pasang locking semaphores. |
| **S4 Multiple Dispatch** | Desain clean polymorphis. Menghilangkan nested branching (`if/else` atau `switch`) yang rapuh. | Overhead pencarian method pada cache miss pertama kali; kompleksitas inheritance DAG sulit dilacak jika terlalu dalam. | Batasi kedalaman inheritance S4 maksimal 3 layer. Lakukan pre-compilation method cache saat package bootstrapping. |
| **Active Bindings (R6)** | Sintaks bersih seperti properti reguler, enkapsulasi mutasi transparan. | 3-5x lebih lambat daripada akses field internal langsung karena memicu evaluasi fungsi closure internal. | Jangan gunakan active bindings untuk operasi yang dipanggil jutaan kali di tight loops. Gunakan pure internal getters. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: R6 Circular Reference Leak (Macet di Garbage Collector)
* **Gejala**: RAM server terus meningkat secara linear (*memory leak*) hingga dieksekusi oleh OS OOM Killer, meskipun objek R6 sudah di-`rm()` dan `gc()` dipanggil.
* **Akar Masalah**: Objek Parent memegang pointer Child, dan Child memegang pointer Parent di dalam environment masing-masing. Siklus referensi closure R mencegah refcount turun ke 0.
* **Troubleshooting & Fix**: Putus siklus referensi secara eksplisit di dalam `$finalize()` atau gunakan pattern Weak References via package `later` atau *environment unbinding*.

```r
# SALAH: Circular reference tanpa pembersihan
Parent <- R6Class("Parent", public = list(child = NULL))
Child <- R6Class("Child", public = list(parent = NULL))

p <- Parent$new()
c <- Child$new()
p$child <- c
c$parent <- p
rm(p, c); gc() # Memori environment tetap menggantung di heap

# BENAR: Manajemen siklus hidup eksplisit
ParentClean <- R6Class("ParentClean",
  public = list(
    child = NULL,
    dispose = function() {
      if (!is.null(self$child)) {
        self$child$parent <- NULL
        self$child <- NULL
      }
    }
  )
)
```

#### Kesalahan 2: Akses Slot S4 Langsung Menggunakan Operasi `@` di Luar Domain Boundary
* **Gejala**: Kode hancur (*breaking changes*) secara sistemik ketika schema/slot internal diperbarui, atau invariansi data rusak karena `@<-` tidak memicu fungsi validasi bawaan.
* **Akar Masalah**: Mengabaikan fungsi enkapsulasi accessor demi kepraktisan penulisan kode.
* **Troubleshooting & Fix**: Larang penggunaan `@` di file eksternal package. Wajibkan implementasi dan pemanggilan *getter* dan *setter* generics (`setGeneric("amount<-", ...)`).

#### Kesalahan 3: Shallow Clone Pitfall pada R6
* **Gejala**: Ketika melakukan kloning instans R6 menggunakan `inst$clone()`, modifikasi field yang bertipe environment/list di instans baru secara misterius mengubah isi data instans lama.
* **Akar Masalah**: Parameter default `deep = FALSE` hanya menyalin environment tingkat pertama; sub-objek yang bertipe environment tetap merujuk pada alamat referensi yang sama.
* **Troubleshooting & Fix**: Definisikan metode deep cloning kustom jika memiliki sub-objek referensi:

```r
ServiceEngine <- R6Class("ServiceEngine",
  public = list(
    state_env = NULL,
    initialize = function() {
      self$state_env <- new.env()
      self$state_env$val <- 100
    }
  ),
  private = list(
    deep_clone = function(name, value) {
      if (name == "state_env") {
        # Duplikasi environment secara mendalam
        new_env <- new.env()
        for (n in ls(value, all.names = TRUE)) {
          assign(n, get(n, envir = value), envir = new_env)
        }
        return(new_env)
      }
      value
    }
  )
)
```

---

### 11. Best Practices (Production Checklist)

#### Standard Development Checklist

1. [ ] **Class Blueprint Purity**: Seluruh field internal R6 privat diawali dengan prefix `..` untuk menghindari name collision dengan private methods.
2. [ ] **S4 Class Validity Contracts**: Seluruh kelas S4 memiliki fungsi validasi komprehensif (`setValidity`) yang memeriksa: panjang elemen (length 1 scalars check), bounded ranges, missing values (`NA`), dan sanitasi strings.
3. [ ] **Type Narrowing**: Constructor fungsional tidak pernah menerima `...` tanpa unpacking eksplisit dan type assertions via `checkmate` atau `assertthat`.
4. [ ] **Locking Mechanisms**: Setiap instans R6 di-lock saat inisialisasi (`lock_class = TRUE` di R6 definition) untuk mencegah runtime monkey-patching liar oleh modul eksternal.
5. [ ] **Serialization Portability**: Objek yang membawa pointer native C (`externalptr`) harus mengimplementasikan hook serialization/unserialization kustom (`reg.finalizer`, pack/unpack routines) agar aman saat dipassing ke parallel cluster worker (`mirai`, `future`).
6. [ ] **Accessor Immutability**: Setter S4 wajib mengembalikan hasil validitas sebelum return value (`validObject(object)` dieksekusi eksplisit di setter).
7. [ ] **Clear Separation of Concerns**: Objek penampung data murni (Data Transfer Objects) diimplementasikan via S4 atau S7; kelas pengendali orchestration, koneksi IO, dan message bus diimplementasikan via R6.

---

### 12. Hands-on Practice

Buatlah struktur direktori kerja berikut untuk menyimpan latihan: `hands-on/m02/`.
Implementasikan arsitektur database telemetry pipeline yang memisahkan Value Object (S4) dan Connection Repository Manager (R6).

#### Langkah 1: Buat S4 Value Object Data
Simpan di: `hands-on/m02/01_telemetry_metric.R`

```r
library(methods)

setClass(
  "TelemetryMetric",
  slots = c(
    metric_id = "character",
    values = "numeric",
    timestamp_epoch = "integer"
  )
)

setValidity("TelemetryMetric", function(object) {
  if (length(object@metric_id) != 1 || is.na(object@metric_id)) {
    return("metric_id harus berupa skalar character non-NA.")
  }
  if (any(is.infinite(object@values))) {
    return("values tidak boleh mengandung nilai tak hingga (Inf/-Inf).")
  }
  if (length(object@timestamp_epoch) != 1 || object@timestamp_epoch <= 0L) {
    return("timestamp_epoch harus berupa integer positif valid.")
  }
  TRUE
})

# Accessor Functions
setGeneric("metricId", function(self) standardGeneric("metricId"))
setMethod("metricId", "TelemetryMetric", function(self) self@metric_id)

setGeneric("metricMean", function(self) standardGeneric("metricMean"))
setMethod("metricMean", "TelemetryMetric", function(self) mean(self@values, na.rm = TRUE))
```

#### Langkah 2: Buat R6 Connection Manager dengan RAII Pattern
Simpan di: `hands-on/m02/02_repository_manager.R`

```r
library(R6)

MockTelemetryRepository <- R6Class("MockTelemetryRepository",
  private = list(
    ..is_connected = logical(0),
    ..buffer = list(),
    ..max_buffer_size = integer(0),
    
    flush_internal = function() {
      cat(sprintf("[DB PERSISTENCE] Menulis %d metrics ke cold storage...\n", length(private$..buffer)))
      private$..buffer <- list()
    }
  ),
  public = list(
    initialize = function(max_buffer_size = 5L) {
      private$..max_buffer_size <- as.integer(max_buffer_size)
      private$..is_connected <- TRUE
      cat("[CONNECTION] Terhubung ke Mock In-Memory Database.\n")
    },
    
    save_metric = function(metric) {
      if (!private$..is_connected) {
        stop("Koneksi database telah ditutup!")
      }
      if (!inherits(metric, "TelemetryMetric")) {
        stop("Parameter metric harus instans valid dari TelemetryMetric S4.")
      }
      
      idx <- length(private$..buffer) + 1
      private$..buffer[[idx]] <- metric
      cat(sprintf("[BUFFER] Disimpan: %s. Ukuran buffer saat ini: %d\n", metricId(metric), idx))
      
      if (length(private$..buffer) >= private$..max_buffer_size) {
        private$flush_internal()
      }
      invisible(self)
    },
    
    close = function() {
      if (private$..is_connected) {
        if (length(private$..buffer) > 0) {
          private$flush_internal()
        }
        private$..is_connected <- FALSE
        cat("[CONNECTION] Koneksi database berhasil ditutup rapi.\n")
      }
    },
    
    finalize = function() {
      # Emergency cleanup jika developer lupa memanggil self$close()
      self$close()
    }
  ),
  lock_class = TRUE
)
```

#### Langkah 3: Eksekusi Pipeline Orchestration
Simpan di: `hands-on/m02/03_pipeline_runner.R`

```r
source("hands-on/m02/01_telemetry_metric.R")
source("hands-on/m02/02_repository_manager.R")

# Jalankan pipeline dengan kontrol eksekusi aman
run_pipeline <- function() {
  repo <- MockTelemetryRepository$new(max_buffer_size = 3L)
  on.exit(repo$close(), add = TRUE)
  
  for (i in 1:7) {
    metric <- new("TelemetryMetric",
                  metric_id = sprintf("SENSOR_VOLT_%03d", i),
                  values = c(12.1, 12.3, 11.9, 12.0) + (i * 0.05),
                  timestamp_epoch = as.integer(Sys.time()) + i)
    
    repo$save_metric(metric)
  }
}

cat("\n--- MEMULAI RUNNING PIPELINE TELEMETRY ---\n")
run_pipeline()
cat("--- PIPELINE SELESAI ---\n")
```

---

### 13. Exercise

#### Level Easy
Ubah definisi kelas S4 `TelemetryMetric` di hands-on 01 untuk memasukkan slot `tags` bertipe `character`. Tambahkan validasi agar semua string di dalam `tags` tidak boleh memiliki spasi. Uji validasi ini dengan memicu pembuatan objek yang sengaja salah format menggunakan blok `stopifnot(inherits(try(...), "try-error"))`.

#### Level Medium
Buat method generic S4 `normalizeMetric` yang menerapkan multiple dispatch:
1. `signature(metric = "TelemetryMetric", method = "character")`: Melakukan transformasi z-score jika method = "zscore", dan min-max scaling jika method = "minmax". Kembalikan objek `TelemetryMetric` baru yang slot `values`-nya telah dinormalisasi.
2. Jika string `method` tidak dikenali, lemparkan custom error: `"Metode normalisasi tidak didukung: <method>"`.

#### Level Hard
Buat implementasi *Observer Pattern* berbasis R6:
* Buat kelas `Subject` R6 yang memiliki fungsi: `$subscribe(observer_r6)`, `$unsubscribe(observer_r6)`, dan `$notify(data)`.
* Buat dua kelas Observer R6 independen: `ConsoleLogger` (mencetak payload ke console) dan `AlertThresholdSystem` (memeriksa jika `metricMean(data) > threshold`, maka trigger alert).
* Pastikan `Subject` menangani siklus unsubscription secara aman tanpa menyebabkan kebocoran memori akibat pointer environment yang menggantung di subscriber list.

---

### 14. Challenge

#### Deskripsi Tantangan Sistem Perbankan Transaksional
Sebuah bank investasi memerlukan modul audit ledger transaksi derivatif intraday berkinerja tinggi di R. Anda diminta mendesain subsistem komputasi dengan spesifikasi ekstrem berikut tanpa menggunakan paket pihak ketiga di luar `methods` dan `R6`:

1. **Transactional Unit of Work Pattern (R6)**:
   * Bangun kelas `TransactionContext` (R6). Engine ini bertindak sebagai buffer transaksi in-memory stateful.
   * Mendukung transaksi bertingkat: `$begin_transaction()`, `$commit()`, dan `$rollback()`.
   * Jika ada exception error yang dilempar di tengah kalkulasi, context harus otomatis me-rollback state saldo/posisi ke kondisi awal checkpoint terdekat (*fail-safe zero data loss*).
2. **Double Dispatch Audit Matching (S4)**:
   * Tentukan tipe instrumen dasar: `AbstractPosition`, dengan turunan `EquityPosition` dan `BondPosition`.
   * Tentukan instrumen matching rule: `ComplianceRule`, dengan turunan `SanctionedCountryRule` dan `NotionalThresholdRule`.
   * Terapkan generic S4 `evaluateCompliance(position, rule)` yang mengevaluasi secara simultan kombinasi tipe posisi dan tipe compliance. Kembalikan instans S4 `AuditResult` berisi status validitas boolean dan timestamp validasi.
3. **Memory Integrity Constraint**:
   * Selama 100.000 iterasi transaksi di dalam loop testing simulasi, RAM process R runtime (`gc()`) tidak boleh bertambah lebih dari 5MB (tidak ada copy-on-modify yang bocor dan circular pointer references harus tereliminasi sepenuhnya).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (Pilihan Ganda & Singkat)
1. Apa perbedaan arsitektural paling mendasar antara representasi C SEXP dari objek S3 dibandingkan objek R6?
2. Mengapa assignment objek S4 (`b <- a`) tidak serta-merta menggandakan alokasi memori fisik sebelum terjadi mutasi slot?
3. Apa fungsi C internal R yang dipanggil saat fungsi generik S3 dieksekusi?
4. Mengapa kita tidak boleh menempatkan instans objek R6 mutable sebagai nilai default di dalam parameter formals fungsi R?
5. Manakah atribut SEXP yang menentukan apakah objek S3/S4 akan diduplikasi saat dimodifikasi: `ALTREP`, `REFCNT/NAMED`, atau `MARK`?

#### B. Intermediate (Analisis Kasus & Mekanisme)
6. Jelaskan bagaimana algoritma dispatch resolusi S4 bekerja saat menghadapi inheritance DAG dengan multiple arguments, dan mengapa pemanggilan pertama sering kali lebih lambat daripada pemanggilan berikutnya!
7. Dalam kondisi apa kita wajib mengimplementasikan fungsi privat `deep_clone` pada class R6? Berikan contoh skenario konkretnya!
8. Apa yang terjadi jika objek S4 dimasukkan ke dalam slot objek S4 lain, lalu salah satu slot leaf dimodifikasi? Bagaimana dampaknya terhadap memori?
9. Jelaskan perbedaan antara *Active Bindings* dan metode fungsi reguler pada R6 dalam hal evaluasi closure, kinerja eksekusi, dan interface pengguna.
10. Mengapa pemanggilan `rm(obj_r6); gc()` terkadang gagal membebaskan memori objek R6 yang memiliki referensi silang?

#### C. Skenario Kasus Produksi
11. **Skenario Memory Crash**: Sebuah job R di server batch analitik mengalami *Crash OOM (Out Of Memory)* setelah berjalan 6 jam memproses 20.000 partisi data. Arsitektur kode menggunakan loop yang memanggil method kelas R6: `orchestrator$process(partition_s4)`. Setiap partisi menghasilkan summary data yang di-append ke slot list internal R6. Jelaskan dua akar masalah utama penyebab OOM tersebut dan rancang solusi perbaikannya!
12. **Skenario Parallel Inconsistency**: Sebuah tim kuantitatif mengekspor instans kelas R6 database wrapper ke worker cluster via `parallel::parLapply` atau `future::future_lapply`. Ketika worker mencoba melakukan write data, muncul error: `"invalid externalptr"`. Mengapa hal ini terjadi pada level arsitektur memori R, dan bagaimana strategi serialisasi yang benar untuk objek infrastruktur tersebut?
13. **Skenario Class Collisions**: Dalam sistem modular skala enterprise yang menggabungkan paket internal `CoreRisk` dan `SpecialRisk`, kedua paket mendefinisikan class S4 bernama `RiskMetric`. Ketika kedua paket di-load via `library()`, downstream pipeline menghasilkan dispatch method yang ambigu dan tidak deterministik. Bagaimana Anda merestrukturisasi namespace dan S4 class naming taxonomy untuk menyelesaikan masalah ini secara enterprise-grade?

---

### 16. Summary

1. **Internal Representation**: Objek R berbasis sistem S3/S4 beroperasi dengan semantik nilai fungsional (*Copy-on-Modify*), di mana integritas data dijamin melalui immutability, namun membutuhkan kewaspadaan alokasi memori pada dataset skala masif. Sebaliknya, R6 mengeksploitasi semantik pointer berbasis `ENVSXP` (*Pass-by-Reference*) yang memungkinkan in-place mutation berkinerja tinggi untuk pengelolaan state.
2. **Arsitektur Hibrida**: Paradigma rekayasa perangkat lunak enterprise modern dalam R memadukan keunggulan kedua sistem: gunakan **S4 atau vctrs/S7** untuk memodelkan Domain Entities, Value Objects, dan operasi aljabar data yang menuntut *type contracts* ketat dan determinisme fungsional; gunakan **R6** untuk Infrastructure Services, Orchestrator, Connection Handles, dan Stateful Aggregation Engines.
3. **Resource & Lifecycle Safety**: Pengelolaan memori pada R6 menuntut disiplin software engineering klasik: penanganan RAII via metode `$finalize()`, pemutusan eksplisit rantai *circular references* untuk mencegah GC leak, dan penanganan serialization boundaries saat mendistribusikan komputasi ke worker cluster.
4. **Reliabilitas Skala Enterprise**: Dengan menerapkan teknik verifikasi formal S4 validity rules, defensive cloning pada R6, serta pemisahan peran class boundaries yang bersih, sistem perangkat lunak yang dibangun di atas R runtime mampu mencapai stabilitas, determinisme, dan throughput komputasi berstandar industri perbankan, telekomunikasi, dan bioinformatika.