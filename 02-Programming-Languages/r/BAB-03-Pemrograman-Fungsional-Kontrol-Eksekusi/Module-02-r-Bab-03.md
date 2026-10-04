# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Pemrograman Fungsional & Kontrol Eksekusi — Bahasa R**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai semantik evaluasi internal R (*Lazy Evaluation*, struktur data `PROMSXP`, dan rantai *Environment/Lexical Scoping*) untuk mencegah memory leak dan bug komputasi laten.
- Membangun *Function Factories*, *Closures*, dan abstraksi *Higher-Order Functions* (HOF) tingkat lanjut untuk arsitektur *data pipeline* yang modular dan dapat dikomposisikan (*composable*).
- Mengimplementasikan sistem penanganan kondisi (*Condition Handling System*) berbasis *Condition Signaling*, `withCallingHandlers`, `tryCatch`, dan *Restarts* untuk orkestrasi pipeline data tanpa *unhandled abort*.
- Mengoptimalkan eksekusi fungsional menggunakan teknik *memoization*, vektorisasi berbasis C-level internals, dan integrasi ekosistem `purrr` serta `rlang` (*Tidy Evaluation*) pada skala enterprise.
- Merancang dan menerapkan arsitektur *Execution Engine* yang tangguh (*fault-tolerant*), terinstrumentasi dengan metrik observabilitas, serta siap-produksi (*production-ready*).

---

## 2. Prerequisite
Untuk mengikuti modul ini secara optimal, peserta wajib memahami:
- Sintaksis dasar R, manipulasi vektor atomik, list, dan `data.frame`.
- Kontrol alur dasar: `if-else`, loop `for`/`while`, serta pemanggilan fungsi dasar.
- Konsep dasar struktur data pointer dan alokasi memori (stack vs. heap).
- Pengalaman dasar dengan *package management* di R menggunakan `renv` atau `devtools`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Lexical Scoping & The Environment Tree
R mengevaluasi simbol menggunakan aturan *lexical scoping*. Setiap kali fungsi dipanggil, R runtime membentuk *execution environment* baru yang terikat pada *enclosing environment* (tempat fungsi didefinisikan, bukan tempat fungsi dipanggil).

```
 +---------------------------------------------------------+
 |                   Global Environment                    |
 |  x <- 10                                                |
 |  factory <- function(a) { ... }                         |
 +----------------------------^----------------------------+
                              | (Parent Pointer)
 +----------------------------+----------------------------+
 |             Execution Env of factory(a = 5)             |
 |  a <- 5                                                 |
 |  worker <- function(val) { val + a + x }                |
 +----------------------------^----------------------------+
                              | (Enclosing Environment)
 +----------------------------+----------------------------+
 |             Execution Env of worker(val = 2)            |
 |  val <- 2                                               |
 |  Lookup: val (Local: 2) -> a (Parent: 5) -> x (Root: 10)|
 +---------------------------------------------------------+
```

Di tingkat C runtime GNU R:
- Setiap environment direpresentasikan sebagai struktur `ENVSXP` yang memuat tabel simbol (hash table atau pairlist) dan pointer `ENCLOS` ke parent environment.
- *Closure* adalah objek `CLOSXP` yang terdiri dari tiga komponen: `FORMALS` (daftar argumen), `BODY` (ekspresi AST), dan `CLOENV` (pointer ke environment tempat closure diciptakan).

### 3.2 Lazy Evaluation & Struktur `PROMSXP`
Argumen fungsi dalam R tidak dievaluasi saat fungsi dipanggil, melainkan dibungkus ke dalam objek internal bertipe `PROMSXP` (*Promise Object*). 

Struktur `PROMSXP` memuat tiga field inti:
1. `PRVALUE`: Menyimpan hasil evaluasi ekspresi (awalnya bernilai `R_NilValue`/`unboundValue`).
2. `PREXPR`: Menyimpan *Abstract Syntax Tree* (AST) dari ekspresi yang di-passing sebagai argumen.
3. `PRENV`: Pointer ke environment tempat ekspresi harus dievaluasi.

```
Argumen pemanggilan: run_job(data = fetch_db(), limit = 100)

+------------------ PROMSXP (data) ------------------+
| PRVALUE : R_NilValue (Belum dievaluasi)            |
| PREXPR  : quote(fetch_db())                        |
| PRENV   : Pointer ke Caller Environment            |
+----------------------------------------------------+
                         |
      Saat simbol 'data' pertama kali diakses:
                         v
+------------------ PROMSXP (data) ------------------+
| PRVALUE : <SEXP: DataFrame hasil eksekusi>         |
| PREXPR  : quote(fetch_db())                        |
| PRENV   : R_NilValue (Dibersihkan untuk GC)        |
+----------------------------------------------------+
```

Evaluasi terjadi ketika simbol dievaluasi (*forced*). Sekali dievaluasi, `PRVALUE` diisi dengan hasil komputasi dan `PRENV` diarahkan ke `R_NilValue` guna memfasilitasi *Garbage Collection* (GC). Jika argumen tidak pernah dipanggil dalam fungsi, ekspresi tidak akan pernah dieksekusi, menghemat I/O dan alokasi memori.

### 3.3 Sistem Kondisi Lanjutan (R Condition Handling Mechanism)
Berbeda dengan arsitektur C++ atau Java yang menggunakan stack unwinding langsung pada blok `try-catch`, sistem kondisi R diadaptasi langsung dari Common Lisp.

```
       [ Signal Condition via signalCondition() / warning() / stop() ]
                                    |
          +-------------------------+-------------------------+
          |                                                   |
[ withCallingHandlers ]                                   [ tryCatch ]
- Stack TIDAK di-unwind.                                  - Stack DI-UNWIND seketika.
- Handler dieksekusi di context tempat                    - Context berpindah ke titik tryCatch.
  kondisi dibangkitkan.                                   - Stack frame lokal hancur.
- Cocok untuk: Logging, telemetry,                        - Cocok untuk: Fallback value, pemulihan
  inspeksi call stack, custom restarts.                     eksekusi global.
```

- **`withCallingHandlers`**: Menginisialisasi handler yang dipanggil langsung pada *frame* tempat sinyal dibangkitkan. Stack execution frame masih utuh, memungkinkan inspeksi jejak audit (*stack trace backtrace*) presisi tinggi.
- **`tryCatch`**: Menerapkan strategi *exiting handlers*. Begitu kondisi cocok, kontrol segera dipindahkan kembali ke blok pemanggil, membersihkan seluruh frame di bawahnya melalui pemanggilan `longjmp` pada level C runtime.

---

## 4. Why & What

| Pendekatan | Karakteristik Utama | Masalah yang Diselesaikan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Imperative Loop (`for`/`while`)** | Mutasi state eksplisit, manual indexing, alokasi memori dinamis jika tidak dipre-alokasi. | Logika sekuensial ketat dengan *early exit* kompleks berbasis interaksi hardware/stream IO mentah. | Algoritma *state-machine* lokal atau transformasi in-place C-interface. |
| **Base Functional (`lapply`, `vapply`)** | Deklaratif, abstraksi iterasi, *type-safe* (`vapply`), alokasi internal teroptimasi di C level. | Meniadakan bug mutasi index dan *out-of-bounds*; memformalkan pemrosesan koleksi data homogen/heterogen. | Transformasi data tanpa dependensi eksternal, pembuatan package *core* base-R. |
| **Advanced Functional (`purrr`)** | Konsistensi sintaks, *strict typing*, integrasi pipe (`|>`), fungsionalitas *ad-hoc composition*. | Menghilangkan inkonsistensi output *type coercion* pada `sapply`; simplifikasi komposisi HOF kompleks. | Pipeline data berskala enterprise, transformasi analitik data modern. |
| **Function Factories & Closures** | Enkapsulasi parameter, komputasi *stateful* tanpa variabel global, konfigurasi dinamis. | Redundansi komputasi konfigurasi; overhead parsing argumen berulang pada eksekusi iteratif tinggi. | Pembangkitan konektor dinamis, custom validator, dynamic cost-function generation. |

---

## 5. How (Workflow Detail)

Arsitektur orkestrasi evaluasi fungsional di R mengikuti tahapan berikut:

```
+-----------------------------------------------------------------------------+
| 1. Inisialisasi Higher-Order Factory & Prapemrosesan Konfigurasi             |
|    - Validasi parameter konfigurasi secara statis.                          |
|    - Evaluasi ekspresi kritis via force() untuk mencegah lazy binding bug.  |
+-----------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------+
| 2. Pendaftaran Condition Handlers & Observability Context                   |
|    - Registrasi withCallingHandlers() untuk logging instan & audit call stack|
|    - Inisialisasi tryCatch() untuk fallback recovery.                       |
+-----------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------+
| 3. Eksekusi Fungsional Terproteksi (Mapping / Transformation)               |
|    - Evaluasi elemen stream via vapply / purrr::map_*                      |
|    - Pemanfaatan copy-on-modify minimization & dynamic restart points.      |
+-----------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------+
| 4. Evaluasi Akhir & Unwinding Safety Context                                 |
|    - Parsing struktur data hasil transformasi.                              |
|    - Evaluasi memory footprint & pembersihan pointer environment.           |
+-----------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem kerja ini seperti pesanan di **Restoran Modern Berbintang**:

1. **Lazy Evaluation (`PROMSXP`)**: Pelayan menerima pesanan *"Steak Medium-Rare"* (AST & Environment). Dapur tidak langsung memasak saat tiket pesanan ditulis. Dapur baru menyalakan kompor ketika pelanggan benar-benar duduk dan siap makan (*forced evaluation*). Jika pelanggan mendadak membatalkan pesanan sebelum makanan disentuh, tidak ada bahan makanan yang terbuang sia-sia.
2. **Closure / Factory**: Sebuah cetakan pembuat pasta. Anda memberikan cetakan ukuran 2mm (*captured state*). Setiap kali Anda memasukkan adonan (*input data*), pasta yang keluar selalu berukuran 2mm tanpa perlu mengukur ulang cetakan setiap detik.
3. **`withCallingHandlers` vs `tryCatch`**:
   - `withCallingHandlers`: Sensor asap di dapur. Ketika mendeteksi asap, sensor mencatat suhu ruangan dan memotret lokasi insiden secara *real-time* tanpa menghentikan koki yang sedang memasak.
   - `tryCatch`: Sistem penyemprot air otomatis (*fire sprinkler*) darurat. Ketika suhu melonjak kritis, sprinkler membasahi seluruh dapur, menghentikan seluruh proses memasak seketika, dan mengalihkan pesanan ke restoran cabang (*fallback*).

```
                      PROMISES & CLOSURES IN ACTION
                      
 Caller Env: [ run_pipeline(cfg) ]
      |
      |-- (Passes expression unevaluated) -----------------+
      v                                                    |
 Closure Env: [ worker_factory() ]                        |
      |                                                    |
      +---> Local State: [ cached_cfg = force(cfg) ]       |
      |                                                    |
      +---> Generates Anonymous Worker:                    |
               \                                           |
                \---> Inputs: [ record_stream ]            |
                         \                                 |
                          \---> Evaluates Argument: <------+
                                [ PROMSXP: PRVALUE <- evaluated ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Menghindari Pitfall Lazy Evaluation pada Factory
Di R, jika Anda mendefinisikan factory tanpa mengevaluasi argumen secara paksa (*forcing*), keterlambatan evaluasi (*late binding*) dapat mengubah nilai parameter saat closure dipanggil.

```r
# --- PENDEKATAN BERBAHAYA (Lazy Binding Trap) ---
bad_multiplier_factory <- function(n) {
  # n tidak di-force
  function(x) {
    x * n
  }
}

factor <- 2
times_two <- bad_multiplier_factory(factor)
factor <- 10 # Mengubah variabel global/caller sebelum closure dieksekusi
times_two(5)
# Hasil: 50 (Bukan 10!), karena evaluasi n ditunda sampai times_two dipanggil.

# --- PENDEKATAN ENTERPRISE (Force Evaluation) ---
clean_multiplier_factory <- function(n) {
  force(n) # Memaksa PROMSXP n dievaluasi seketika pada frame ini
  function(x) {
    x * n
  }
}

factor <- 2
times_two_clean <- clean_multiplier_factory(factor)
factor <- 10
times_two_clean(5)
# Hasil konsisten: 10
```

### 7.2 Practical Example: Enterprise Function Factory dengan Type-Safe Mapping & Recovery

```r
#' @title Build a Robust Pipeline Transformer
#' @description Mengonstruksi transformer fungsional dengan skema validasi ketat,
#' tracking metrik, dan penanganan kondisi via withCallingHandlers.
#' @param schema_type Tipe data target yang diharapkan ('numeric', 'character').
#' @param fallback_val Nilai default jika parsing menghasilkan error/warning.
#' @return Fungsi closure terisolasi untuk transformasi vektor data.
create_resilient_transformer <- function(schema_type = c("numeric", "character"), 
                                         fallback_val = NA) {
  schema_type <- match.arg(schema_type)
  force(fallback_val)
  
  # Audit trail internal closure
  metrics <- new.env(parent = emptyenv())
  metrics$invocations <- 0L
  metrics$errors <- 0L
  metrics$warnings <- 0L
  
  transformer_function <- function(raw_input) {
    metrics$invocations <- metrics$invocations + 1L
    
    # Eksekusi terproteksi menggunakan dual-layer condition handling
    result <- tryCatch(
      expr = {
        withCallingHandlers(
          expr = {
            if (is.null(raw_input) || length(raw_input) == 0L) {
              signalCondition(
                structure(
                  class = c("empty_input_condition", "condition"),
                  list(message = "Input vector is empty or NULL.")
                )
              )
              return(fallback_val)
            }
            
            # Type casting terarah
            converted <- switch(
              schema_type,
              "numeric"   = as.numeric(raw_input),
              "character" = as.character(raw_input)
            )
            
            if (any(is.na(converted) & !is.na(raw_input))) {
              warning("Coercion generated NA values unexpectedly.")
            }
            
            converted
          },
          warning = function(w) {
            metrics$warnings <- metrics$warnings + 1L
            # Mengizinkan warning diteruskan ke upstream handler tanpa unwinding
          }
        )
      },
      empty_input_condition = function(cond) {
        metrics$warnings <- metrics$warnings + 1L
        fallback_val
      },
      error = function(e) {
        metrics$errors <- metrics$errors + 1L
        fallback_val
      }
    )
    
    return(result)
  }
  
  # Export accessor untuk metrics observability
  attr(transformer_function, "get_metrics") <- function() {
    as.list(metrics)
  }
  
  return(transformer_function)
}

# Inisialisasi dan uji coba praktis
num_parser <- create_resilient_transformer(schema_type = "numeric", fallback_val = -1)
dataset <- list("100", "200", "INVALID_DATA", NULL, "500")

# Menggunakan purrr::map atau vapply untuk mapping fungsional terisolasi
processed_data <- vapply(dataset, function(elem) {
  num_parser(elem)
}, FUN.VALUE = numeric(1L))

print(processed_data)
# Output: [1] 100 200  -1  -1 500

# Inspeksi telemetry internal closure
print(attr(num_parser, "get_metrics")())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario
Sistem ETL di Bank Multinasional memproses ingest transaksi harian dari 10.000 file batch JSON/CSV yang dikirim secara asynchronous oleh ratusan cabang.

### Masalah
- Parser sering *crash* di tengah eksekusi karena inkonsistensi tipe data di payload batch cabang tertentu.
- Implementasi standar menggunakan `tryCatch` global menghentikan *parsing stack* seketika (*early exit*), membuang seluruh transaksi valid yang berada di batch yang sama.
- Audit compliance regulator mewajibkan pencatatan *full stack trace* pada setiap anomali data tanpa boleh menghentikan proses ingestion transaksi valid lainnya.

### Solusi Arsitektur
Membangun modul fungsional: **"Resilient Ingestion Engine via Calling Handlers & Functional Folds"**. Engine ini memanfaatkan `withCallingHandlers` untuk inspeksi stack dan pencatatan audit log secara *in-place*, serta menggunakan `purrr::safely` wrapper untuk isolasi fault-domain tingkat baris.

```r
# Implementation: Ingestion Pipeline Terproteksi
library(purrr)

#' Record structure validator & transformer
parse_transaction_record <- function(raw_record) {
  # Emulasi parsing record
  if (is.null(raw_record$account_id)) {
    stop("CRITICAL_SCHEMA_ERROR: 'account_id' is missing.")
  }
  if (!is.numeric(raw_record$amount)) {
    warning("DATA_MUTATION_WARNING: 'amount' coerced to numeric.")
    raw_record$amount <- as.numeric(raw_record$amount)
  }
  if (is.na(raw_record$amount) || raw_record$amount <= 0) {
    stop("BUSINESS_LOGIC_ERROR: Invalid transaction amount.")
  }
  
  list(
    account_id = as.character(raw_record$account_id),
    amount     = raw_record$amount,
    status     = "PROCESSED"
  )
}

#' Execution Engine Core
execute_batch_ingest <- function(batch_payload) {
  # Audit storage
  audit_logger <- function(cond, record_idx) {
    # sys.calls() masih utuh karena dipanggil via withCallingHandlers!
    call_stack <- sys.calls()
    cat(sprintf("[AUDIT][%s][Record: %d] %s\n", 
                format(Sys.time(), "%Y-%m-%d %H:%M:%OS3"),
                record_idx, 
                conditionMessage(cond)))
  }
  
  # Wrapping fungsi parser dengan calling handler untuk inspeksi tanpa aborting
  monitored_parser <- function(idx, record) {
    withCallingHandlers(
      expr = {
        parse_transaction_record(record)
      },
      warning = function(w) {
        audit_logger(w, idx)
        invokeRestart("muffleWarning") # Meredam propagate console spam
      },
      error = function(e) {
        audit_logger(e, idx)
        # Sinyal akan berlanjut ke tryCatch pembungkus safely/purrr
      }
    )
  }
  
  # Proteksi fault domain per record (purrr::safely pattern)
  safe_step <- purrr::safely(monitored_parser, otherwise = NULL)
  
  # Fungsional mapping terisolasi
  results <- purrr::imap(batch_payload, ~ safe_step(.y, .x))
  
  # Transposisi hasil: agregasi data sukses vs metadata error
  transposed <- purrr::transpose(results)
  successful_records <- purrr::compact(transposed$result)
  failures <- purrr::keep(transposed$error, ~ !is.null(.x))
  
  list(
    ingested_data = successful_records,
    metrics = list(
      total = length(batch_payload),
      success = length(successful_records),
      failed = length(failures)
    )
  )
}

# --- SIMULASI WORKLOAD ENTERPRISE ---
mock_batch <- list(
  list(account_id = "ACC-001", amount = 1500.50),
  list(account_id = "ACC-002", amount = "3200.00"), # Membangkitkan warning
  list(account_id = NULL,      amount = 500),       # Error skema fatal
  list(account_id = "ACC-004", amount = -90.00),    # Error logic bisnis
  list(account_id = "ACC-005", amount = 8500.00)
)

ingestion_output <- execute_batch_ingest(mock_batch)
cat("\n--- RINGKASAN INGESTION ---\n")
print(ingestion_output$metrics)
cat("Jumlah data valid tersimpan: ", length(ingestion_output$ingested_data), "\n")
```

---

## 9. Trade-offs

```
                       COMPLEXITY VS OVERHEAD
  Low Overhead                                        High Reliability
+------------------------+-----------------------+---------------------+
|      vapply / C-Loop   |      purrr::map_*     | withCallingHandlers |
|                        |                       |   + Safe Wrappers   |
| - Memory: Minimal      | - Memory: Moderate    | - Memory: Tinggi    |
| - Latency: Sub-ms      | - Latency: Sedang     | - Latency: Tinggi   |
| - Safety: Statis ketat | - Safety: Modular     | - Safety: Maksimal  |
+------------------------+-----------------------+---------------------+
  Low Traceability                                    Full Audit / Trace
```

### 1. Performance vs Latency
- `vapply()` dan looping C-level memiliki latency terendah (orde mikrodetik) karena tidak mengalokasikan context per-record.
- `withCallingHandlers()` yang dipadukan dengan pemanggilan `sys.calls()` dan `purrr::safely` membawa overhead eksekusi 5x–15x lebih tinggi per record. Hanya gunakan isolasi mendalam ini pada pipeline boundary atau saat dependensi eksternal tidak stabil.

### 2. Scalability vs Memory Footprint
- R secara default menggunakan *Copy-on-Modify*. Mutasi objek di dalam loop imperatif tanpa pra-alokasi memicu kompresi RAM $O(N^2)$.
- Fungsional mapping via `purrr` atau `lapply` mengalokasikan list pointer diawal ($O(N)$), namun jika setiap *frame closure* menyimpan data referensi besar tanpa pembersihan environment (`rm()` atau unbinding), GC akan tertunda dan memicu *Memory Spike*.

### 3. Engineering Cost vs Robustness
- Penggunaan `tryCatch` standar membutuhkan sedikit baris kode namun menghilangkan konteks debug secara permanen (*stack unwound*).
- Sistem penanganan kondisi kustom (`condition classes` + `restarts`) memerlukan abstraksi desain yang kompleks di awal, namun memangkas rata-rata waktu investigasi insiden produksi (*Mean Time to Recovery* / MTTR) dari hitungan jam ke hitungan menit.

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Dynamic Variable Binding dalam Iterasi Functional
```r
# SALAH: Functor mengikat simbol variabel loop, bukan nilai per siklus
fun_list <- vector("list", 3)
for (i in 1:3) {
  fun_list[[i]] <- function() i  # i dievaluasi secara lazy saat pemanggilan
}
fun_list[[1]]() # Menghasilkan 3, bukan 1!

# BENAR: Putuskan keterikatan lingkungan via force() atau pembentukan lexical scope unik
fun_list_fixed <- vector("list", 3)
for (i in 1:3) {
  local({
    idx <- i
    fun_list_fixed[[idx]] <- function() idx
  })
}
fun_list_fixed[[1]]() # Menghasilkan 1
```

### Mistake 2: Menyembunyikan Error Nyata Menggunakan `tryCatch(..., error = function(e) NULL)`
```r
# SALAH: Anti-pattern Silent Failure
suppress_all <- function(x) {
  tryCatch(as.numeric(x$non_existent_field) * 10, error = function(e) NULL)
}
# Output NULL tidak memberikan kejelasan apakah sistem kekurangan field, tipe data korup, atau OOM!

# BENAR: Menerapkan Typed Condition Trapping
safe_extract <- function(x) {
  tryCatch(
    expr = {
      if (!"target" %in% names(x)) {
        stop(structure(class = c("missing_key_error", "error", "condition"),
                       list(message = "Field 'target' absent.", key = "target")))
      }
      as.numeric(x$target) * 10
    },
    missing_key_error = function(e) {
      warning(sprintf("Peringatan: %s Menggunakan nilai fallback 0.", e$message))
      0
    }
  )
}
```

### Panduan Troubleshooting Debugging Frame
Saat pipeline mengalami kegagalan di dalam rantai HOF (`purrr`/`lapply`), eksekusi perintah:
```r
# Masuk ke post-mortem interactive debugger saat unhandled error terjadi
options(error = recover)

# Atau cetak calls hierarchy langsung di calling handler:
withCallingHandlers(
  my_pipeline_call(),
  error = function(e) {
    cat("Execution trace:\n")
    print(sys.calls())
  }
)
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Paksa Evaluasi Argumen Factory**: Selalu terapkan fungsi `force()` pada setiap argumen pembentuk *closure* / *factory* untuk memvalidasi dan memutus rantai `PROMSXP`.
- [ ] **Type-Safe Mapping Obligation**: Hindari fungsi ambigu seperti `sapply()` pada lingkungan produksi. Wajib gunakan `vapply()` dengan spesifikasi `FUN.VALUE` eksplisit atau gunakan famili `purrr::map_<type>()` (`map_dbl`, `map_chr`, `map_lgl`).
- [ ] **Definisikan Custom Condition Classes**: Jangan melempar error menggunakan plain text `stop("pesan")`. Selalu buat S3 condition subclass agar upstream handler dapat memfilter exception secara selektif tanpa regex parsing.
- [ ] **Isolasi Side-Effect**: Pisahkan fungsi komputasi murni (*pure functions*) dari fungsi I/O atau mutasi basis data.
- [ ] **Batasi Retention Environment**: Closure yang dibuat di dalam environment yang menampung objek besar (seperti koneksi database atau *raw data payload*) akan menahan objek tersebut dari GC. Bersihkan objek temporer menggunakan `rm(big_data)` sebelum mereturn closure.
- [ ] **Muffle Warnings Terkendali**: Saat menangani peringatan yang sudah diantisipasi di dalam `withCallingHandlers`, gunakan `invokeRestart("muffleWarning")` guna mencegah pencemaran log konsol engine host.

---

## 12. Hands-on Practice

Buatlah direktori praktikum dengan hierarki berikut:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 1: Buat Engine Telemetri Fungsional
Simpan kode berikut sebagai `engine.R`:

```r
# hands-on/m02/engine.R

#' Functional Pipeline Circuit Breaker
make_pipeline_executor <- function(threshold_failures = 3L) {
  force(threshold_failures)
  consecutive_failures <- 0L
  is_circuit_open <- FALSE
  
  function(data_chunk, transformation_fn) {
    if (is_circuit_open) {
      stop("CIRCUIT_BREAKER_OPEN: Pipeline dihentikan sementara demi stabilitas sistem.")
    }
    
    result <- tryCatch(
      expr = {
        out <- transformation_fn(data_chunk)
        consecutive_failures <<- 0L # Reset jika sukses
        out
      },
      error = function(e) {
        consecutive_failures <<- consecutive_failures + 1L
        if (consecutive_failures >= threshold_failures) {
          is_circuit_open <<- TRUE
        }
        stop(e)
      }
    )
    result
  }
}
```

### Langkah 2: Buat Pipeline Parser & Consumer
Simpan kode berikut sebagai `main.R`:

```r
# hands-on/m02/main.R
source("engine.R")

# Transformer logic
risky_parser <- function(x) {
  if (is.character(x) && x == "FATAL") {
    stop("Database connection timed out!")
  }
  if (!is.numeric(x)) {
    stop("Invalid data format: must be numeric.")
  }
  x * 2
}

executor <- make_pipeline_executor(threshold_failures = 2L)

test_stream <- list(10, 20, "FATAL", "FATAL", 50)

cat("Memulai eksekusi stream...\n")
for (idx in seq_along(test_stream)) {
  cat(sprintf("\nMemproses payload [%d]... ", idx))
  step_result <- tryCatch(
    executor(test_stream[[idx]], risky_parser),
    error = function(e) {
      paste("ERROR_CAPTURED:", conditionMessage(e))
    }
  )
  cat(step_result, "\n")
}
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan melalui terminal:
```bash
Rscript main.R
```
Pastikan pada payload ke-4 circuit breaker terbuka dan melempar pesan error `CIRCUIT_BREAKER_OPEN`.

---

## 13. Exercise

### Level Easy
Modifikasi fungsi `vapply` standar untuk membaca vector string bertipe tanggal (`"2023-01-01"`, `"INVALID"`, `"2023-05-12"`) menggunakan wrapper functional sederhana. Jika format string tidak valid, kembalikan nilai default `NA_real_` tanpa menghentikan iterasi.
- **Fokus**: Menangani warning dan error secara lokal.

### Level Medium
Buat sebuah *Function Factory* bernama `make_rate_limiter(fn, max_calls_per_second)`:
- Factory harus mengembalikan closure baru yang membungkus parameter fungsi `fn`.
- Setiap kali closure dipanggil melampaui `max_calls_per_second`, closure secara otomatis memanggil `Sys.sleep()` secukupnya untuk memastikan eksekusi tidak melampaui limit laju yang ditentukan.
- **Fokus**: State management dalam lexical environment closure.

### Level Hard
Implementasikan struktur fungsional *Monadic Container* sederhana di R (seperti pola `Either` / `Result`):
- Buat konstruktor `success(value)` dan `failure(error_condition)`.
- Buat fungsi bind `and_then(result_container, fn)` yang mengevaluasi `fn` hanya jika status kontainer adalah `success`.
- Jika status kontainer adalah `failure`, lewati pemanggilan fungsi `fn` dan *propagate* error secara otomatis tanpa memicu terminasi eksekusi runtime.
- **Fokus**: Functional composition tingkat tinggi dan abstraksi komputasi aman.

---

## 14. Challenge

### Skenario Kasus
Sebuah sistem High-Frequency Algorithmic Trading (HFAT) di R mengeksekusi puluhan ribu order limit setiap detik melalui pipeline fungsional modular. Pada arsitektur berjalan saat ini:
1. Sinyal trading dievaluasi melalui serangkaian fungsi komposisi `purrr::compose(signal_alpha, risk_filter, order_routing)`.
2. Saat market mengalami volatilitas ekstrem, `risk_filter` melempar warning dan transient error terkait likuiditas bursa yang fluktuatif.
3. Arsitektur `tryCatch` yang terpasang saat ini menyebabkan pembatalan seluruh order batch, menghabiskan waktu komputasi berharga dan menghasilkan kerugian finansial akibat *unexecuted trades*.

### Misi Arsitektural
Rancang sebuah framework eksekusi transaksi berbasis **Restart Frames (`withRestarts` / `invokeRestart`)** murni di base-R:
- Jika order gagal lolos `risk_filter` karena toleransi spread tipis (*soft breach*), kondisi harus membangkitkan restart frame `reprice_order` yang memotong kuantitas lot order sebesar 50% dan langsung melanjutkan eksekusi ke step `order_routing` tanpa mengulang komputasi `signal_alpha` dari awal.
- Jika order mengalami *hard breach* (margin minus), panggil restart frame `abort_trade` yang mencatat log audit ke shared telemetry buffer dan beralih ke order berikutnya tanpa merusak alur call stack loop engine utama.
- Buktikan bahwa solusi Anda tidak mengalokasikan memori duplikat (*zero-copy validation*) menggunakan inspeksi objek address via `tracemem()`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: 5 Pertanyaan Basic
1. Apa nilai kembalian dari struktur internal `PROMSXP` pada field `PRVALUE` sebelum ekspresi di-*forced*?
2. Mengapa pemanggilan `force(x)` penting di dalam sebuah *Function Factory* di R?
3. Sebutkan perbedaan utama alur eksekusi antara `tryCatch()` dan `withCallingHandlers()` saat sebuah kondisi dibangkitkan!
4. Di environment mana sebuah fungsi di R mencari simbol variabel yang tidak didefinisikan secara lokal di dalam tubuh fungsinya?
5. Mengapa penggunaan fungsi `sapply()` dilarang secara ketat dalam pipeline data enterprise level?

### Bagian B: 5 Pertanyaan Intermediate
6. Bagaimana cara mematikan propagasi warning ke level global konsol ketika kita memproses warning tersebut di dalam `withCallingHandlers`?
7. Apa yang terjadi pada pointer environment suatu closure jika closure tersebut mengembalikan fungsi lain yang mereferensikan objek besar dari lingkungan pembuatnya?
8. Bagaimana implementasi mekanisme evaluasi *Late Binding* dapat menyebabkan bug pada loop pembuatan daftar fungsi (`for (i in 1:n) { funcs[[i]] <- function() i }`)?
9. Terangkan perbedaan semantik kontrol alur antara *Exiting Handlers* dan *Calling Handlers* menurut standar arsitektur R!
10. Bagaimana representasi objek internal R (`CLOSXP`) mengikat *formals*, *body*, dan *enclosing environment*?

### Bagian C: 3 Skenario Kasus Produksi
11. **Kasus 1**: Pipeline ETL harian memproses data transaksi bank. Tiba-tiba konsumsi RAM melonjak hingga 64GB dan membunuh instance R (OOM-Kill), padahal ukuran file CSV input hanya 2GB. Dari perspektif alur kontrol fungsional dan memory allocation R, apa akar masalah yang paling mungkin terjadi dan bagaimana membedah alur perbaikannya?
12. **Kasus 2**: Tim analitik membuat custom error handling menggunakan `tryCatch` untuk menangkap network timeout ke microservice eksternal. Namun saat terjadi timeout, sistem gagal mengambil informasi nomor baris atau stack trace asli dari fungsi deep-down yang memicu error tersebut. Mengapa hal ini terjadi dan bagaimana rancangan solusi penanganannya?
13. **Kasus 3**: Anda diminta mengaudit performa sebuah package internal. Anda menemukan ribuan closure dibangkitkan secara dinamis per detik di dalam loop pemrosesan streaming. Profiling menunjukkan CPU time banyak tersita pada siklus *Garbage Collection* (GC). Langkah refactoring arsitektur fungsional apa yang harus diambil untuk mereduksi tekanan alokasi GC tersebut?

---

## 16. Summary

- **Lexical Scoping & Closures**: R mengikat fungsi langsung ke lingkungan tempat fungsi tersebut didefinisikan. *Function Factories* memanfaatkan karakteristik ini untuk mengenkapsulasi status (*stateful closures*) tanpa mencemari global environment.
- **Lazy Evaluation**: Evaluasi argumen fungsi ditunda hingga simbol argumen diakses langsung. Pemahaman terhadap struktur `PROMSXP` (`PREXPR`, `PRENV`, `PRVALUE`) merupakan kunci untuk mencegah perilaku *late-binding bug* melalui fungsi `force()`.
- **Condition Handling Hierarchy**:
  - `withCallingHandlers()`: Beroperasi secara *in-place* tanpa merusak call stack; fondasi utama untuk logging, telemetri, inspeksi frame, dan implementasi strategi *restart*.
  - `tryCatch()`: Mekanisme penanganan dengan stack unwinding langsung; ideal untuk menetapkan nilai fallback dan pemulihan batas eksekusi global.
- **Production Pipeline Readiness**: Pipeline data enterprise yang tangguh menggabungkan fungsional mapping bertipe ketat (`vapply`, `purrr`), isolasi error domain granular (`purrr::safely` / S3 custom conditions), dan manajemen alokasi memori yang disiplin terhadap siklus hidup garbage collection.