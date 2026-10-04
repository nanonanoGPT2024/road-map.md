# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Data Structures, Control Flows, and Functional Semantics**
**Kategori: 02-Programming-Languages / R-Programming**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal R Memory Engine:** Memahami representasi `SEXPREC` (S-Expression Record), mekanisme *reference counting* (`REFCNT`), *generational garbage collector* R (R-GC), dan framework ALTREP (*Alternative Representations*).
- **Mengoptimalkan Semantika Copy-on-Write (CoW):** Mengidentifikasi mutasi objek yang memicu alokasi memori berlebih ($O(N^2)$ anti-patterns) dan mengubahnya menjadi operasi *in-place modification* atau alokasi vektor statis.
- **Menguasai Semantik Fungsional & Evaluasi Parsial:** Membedakan closure environments, execution frames, serta lazy evaluation berbasis `PRMSXP` (*Promise Objects*) untuk membangun abstraksi fungsional enterprise.
- **Mendesain Control Flow Skala Produksi:** Mengintegrasikan pattern condition handling tingkat lanjut (`tryCatch`, `withCallingHandlers`, `restart`) dan vectorization idioms yang mengabaikan overhead interpreter R.
- **Membangun Pipeline Data Paralel Terisolasi:** Mengimplementasikan pemrosesan batch bervolume tinggi menggunakan arsitektur non-blocking berbasis functional primitives (`purrr`, `future`, `furrr`) tanpa race conditions dan memory leaks.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memiliki:
- Pemahaman sintaks dasar R (assignment operator `<-`, indexing vector `[]`, `[[]]`, dan fungsi bawaan dasar).
- Pengalaman dasar pemrograman fungsional (higher-order functions seperti `map`, `reduce`, `apply`).
- Pengetahuan arsitektur komputer mendasar: Call Stack, Heap Memory, L1/L2/L3 Cache lines, Pointers, dan Big-O Algorithmic Complexity.
- Instalasi environment kerja: R 4.2+ (disarankan 4.3+ untuk optimasi ALTREP mutakhir), RStudio IDE atau Positron/VSCode R Extension, serta build tools Rtools (Windows) atau `build-essential` (Linux/macOS).

---

## 3. Concept & Internal Architecture

### 3.1 S-Expressions (SEXP) dan Model Memori Internal R

Di balik runtime GNU R, semua objek diekspresikan sebagai pointer ke struktur C bernama `SEXPREC` (`typedef struct SEXPREC *SEXP`). Model ini mencakup nilai skalar (yang sebenarnya merupakan vektor berpanjang 1), fungsi, ekspresi abstrak, hingga environment eksekusi.

```
       +-------------------------------------------------------+
       |                     SEXPREC                           |
       | +---------------------------------------------------+ |
       | |                  sxpinfo_struct                   | |
       | | - type (5 bits): INTSXP, REALSXP, VECSXP, STRSXP  | |
       | | - obj (1 bit): S3/S4 Class indicator              | |
       | | - mark (1 bit): Garbage collector active flag     | |
       | | - refcnt (16/32 bits): Reference counting         | |
       | +---------------------------------------------------+ |
       | +---------------------------------------------------+ |
       | |             struct sxpinfo attrib                 | |
       | |   (Pointer ke linked-list atribut objek: names,   | |
       | |    dim, class, dsb.)                              | |
       | +---------------------------------------------------+ |
       | +---------------------------------------------------+ |
       | |                  union { ... }                    | |
       | |   - vecsxp: pointer ke array data berurutan       | |
       | |   - envsxp: frame, enclosing env, hashtable       | |
       | |   - promsxp: value, expression, environment       | |
       | +---------------------------------------------------+ |
       +-------------------------------------------------------+
```

Variasi tipe data utama dalam representasi C:
- `LGLSXP`: Logical vector (disimpan sebagai C integer, 4 bytes per elemen).
- `INTSXP`: Integer vector (32-bit signed int, 4 bytes per elemen).
- `REALSXP`: Double precision floating point (IEEE 754, 8 bytes per elemen).
- `STRSXP`: Character vector (vektor berisi pointer ke global string cache / `CHARSXP`).
- `VECSXP`: Generic list (vektor berisi pointer ke sembarang `SEXP` lainnya).
- `ENVSXP`: Environment table.
- `CLOSXP`: Closure (fungsi fungsional R reguler).
- `PROMSXP`: Promise untuk evaluasi lambat (lazy evaluation).

### 3.2 Copy-on-Write (CoW) dan ALTREP Framework

R mengadopsi semantik nilai (*pass-by-value* semu). Secara internal, R tidak menduplikasi data saat penugasan variabel baru dilakukan:

```r
x <- runif(1e7) # Alokasi ~80 MB REALSXP
y <- x          # Tidak ada duplikasi memori. y menunjuk ke SEXP yang sama.
```

Pada fase ini, `REFCNT(x)` bernilai 2. Duplikasi data nyata (*deep-copy*) baru dilakukan ketika salah satu variabel dimutasi (*Copy-on-Write*):

```r
y[1] <- 0.5     # Triggers duplicate(x). Alokasi baru ~80 MB untuk y.
```

Sejak R 3.5.0, framework **ALTREP** (*Alternative Representations*) diperkenalkan untuk mengabstraksi representasi data internal:
1. Rentang bilangan berurutan `1:1e9` tidak lagi mengalokasikan 4 GB RAM secara contiguous, melainkan representasi algoritmik berukuran tetap (hanya menyimpan *start*, *step*, dan *length*).
2. Deferalisasi string conversion dan I/O parsing (seperti `readr` atau `arrow` zero-copy memory mapping).

### 3.3 Lexical Scoping, Execution Frames, dan Promises

Fungsi di R adalah *first-class citizens* berupa closure yang mengikat 3 komponen:
1. Argumen formal (*formals*).
2. Tubuh fungsi (*body*).
3. Environment tempat fungsi didefinisikan (*enclosing environment*).

Ketika fungsi dipanggil:
- R membuat *execution environment* baru yang memiliki parent pointer ke *enclosing environment* (bukan calling environment).
- Seluruh argumen formal dimasukkan ke dalam execution environment sebagai **Promise** (`PROMSXP`).
- Sebuah promise terdiri dari:
  - **Expression**: AST dari argumen yang di-passing.
  - **Environment**: Environment tempat argumen dievaluasi.
  - **Value**: Diisi dengan hasil evaluasi hanya saat nilai argumen pertama kali diakses (*memoized / forced*).

---

## 4. Why & What

| Fitur | What (Apa Karakteristiknya) | Why (Mengapa Kritis untuk Enterprise) |
| :--- | :--- | :--- |
| **Vectors vs Generic Lists** | Vektor atomik dialokasikan contiguous di flat memory buffer; Generic list (`VECSXP`) adalah array of pointers. | Vektor atomik memberikan performa SIMD CPU cache lines maksimal. Menggunakan nested lists tanpa alasan arsitektural memicu cache miss dan overhead GC. |
| **Immutable Functional Idioms** | Objek bersifat imutabel secara semantik, mutasi menghasilkan state baru kecuali optimized by reference. | Menghindari *shared-state concurrency bugs*, mempermudah unit testing, memfasilitasi distributed computing (Apache Spark via sparklyr, HPC cluster). |
| **ALTREP Optimization** | Abstraksi data wrapper yang menunda realisasi fisik alokasi memori. | Menurunkan penggunaan RAM hingga 99% pada batch generation array dan memungkinkan transfer data cross-language (R <-> C++ <-> Python via Arrow) tanpa serialization overhead. |
| **Conditions System vs Exceptions** | Pemisahan antara penandaan sinyal error/warning dengan recovery decision via `withCallingHandlers`. | Mengizinkan recovery, log agregasi, dan mutasi error handling tanpa melakukan unrolling stack frame secara destruktif. |

---

## 5. How (Workflow Detail)

Berikut siklus hidup parsing ekspresi, alokasi memori, evaluasi promise, hingga pembersihan GC:

```
[User Code Input]
       │
       ▼
[Lexer / Parser Engine] ───► Menghasilkan Abstract Syntax Tree (LANGSXP)
       │
       ▼
[Evaluation Engine]
       ├─► Evaluasi Argumen ──► Buat Promise (PROMSXP)
       │                        (Expression + Call-site Environment)
       ▼
[Execution Frame Initialization]
       │
       ├─► Bind Formals ke Promise Objects
       ├─► Evaluasi Body Statement per Statement
       │       │
       │       ▼
       │   [Argument Accessed?] 
       │       ├── YES ──► Force Evaluation di Originating Env (Memoize Value)
       │       └── NO  ──► Argumen tidak pernah dievaluasi (Pure Lazy)
       │
       ▼
[Object Mutation Handling]
       │
       ├─► Cek REFCNT(SEXP)
       │       ├── REFCNT == 1 & In-Place Safe ──► Mutasi langsung di buffer C
       │       └── REFCNT > 1                  ──► Jalankan duplicate() -> Update Pointer
       ▼
[Frame Exit & Destruction]
       │
       ▼
[R-GC Generational Sweep]
       ├─► Gen 0 (Objek transien/singkat) -> Sweep frekuensi tinggi
       ├─► Gen 1 (Objek bertahan dari 1 cycle)
       └─► Gen 2 (Objek persisten/global) -> Full sweep frekuensi rendah
```

---

## 6. Analogy & Diagram ASCII

### Analogi Lazy Evaluation & Promises
Bayangkan Anda memesan paket makanan di restoran (*Caller*). Restoran tidak memasak semua menu pembuka, menu utama, dan penutup di awal. Restoran memberikan voucher (*Promise*) untuk masing-masing menu.
- Jika Anda tidak pernah menukar voucher menu penutup (*Unforced Argument*), dapur tidak akan membuang bahan baku untuk memasaknya.
- Begitu Anda meminta menu penutup (*Forced Evaluation*), dapur memasaknya di lingkungan dapur saat itu, mencatat hasilnya di piring Anda, dan jika Anda memintanya lagi, Anda langsung memakannya dari piring tanpa memasak ulang (*Memoization*).

### Execution Frame vs Enclosing Scoping

```
+-------------------------------------------------------------+
| Global Environment (R_GlobalEnv)                            |
|  - service_tax <- 0.11                                      |
|  - create_invoicer() ---------------------------------+     |
+-------------------------------------------------------|-----+
                                                        | Creates
                                                        ▼
+-------------------------------------------------------------+
| Closure Enclosing Environment                               |
|  - discount_rate <- 0.05                                    |
|                                                             |
|  calculate_total() [Function Pointer]                       |
+-------------------------------------------------------------+
               ▲
               │ Parent Env Pointer
+--------------┴----------------------------------------------+
| Execution Frame (Setiap fungsi dipanggil: calculate_total) |
|  - items <- [SEXP Array: 100, 200, 300]                     |
|  - subtotal <- sum(items)                                   |
|  - Execution local: discount_rate dicari ke parent          |
+-------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Tracing CoW & ALTREP Internals
Gunakan paket `lobstr` untuk melihat representasi pointer memori dan status ALTREP.

```r
library(lobstr)

# 1. Eksplorasi ALTREP
v_altrep <- 1:1e6
obj_size(v_altrep) 
# [Output: ~680 B] -> ALTREP Integer sequence, bukan 4 MB fisik!

v_realized <- c(v_altrep, 2L)
obj_size(v_realized)
# [Output: ~4 MB] -> Realisasi alokasi memori fisik terjadi saat representasi rusak

# 2. Tracking Memory Pointer & Copy-on-Write
vec_a <- runif(5)
lobstr::obj_addr(vec_a)
# Misal: "0x12a4b8700"

vec_b <- vec_a
lobstr::obj_addr(vec_b)
# Identik: "0x12a4b8700" (REFCNT bertambah, data tidak digandakan)

vec_b[1] <- 999.0
lobstr::obj_addr(vec_b)
# Berubah: "0x12a6e9100" (Terdivergensi via CoW duplicate)
```

### 7.2 Practical Example: Enterprise Memory Profiling & Functional Pipeline

Contoh implementasi functional pipeline yang membandingkan anti-pattern alokasi inkremental versus *pre-allocated vectorized functional pattern*.

```r
library(bench)
library(purrr)

# Anti-Pattern: Pertumbuhan Vektor Inkremental (Memory thrashing & O(N^2) copying)
process_incremental <- function(n) {
  res <- numeric(0)
  for (i in seq_len(n)) {
    # CoW dipicu di setiap iterasi karena penugasan ulang ke variabel yang sama
    res <- c(res, sqrt(i) * 2.5)
  }
  res
}

# Production Pattern: Pre-allocation + Direct In-Place Indexing
process_preallocated <- function(n) {
  res <- numeric(n) # Direct SEXP allocation
  for (i in seq_len(n)) {
    res[i] <- sqrt(i) * 2.5 # In-place write (REFCNT == 1)
  }
  res
}

# Pure Vectorized Pattern: Menggunakan runtime C-level vectorization
process_vectorized <- function(n) {
  sqrt(seq_len(n)) * 2.5
}

# Benchmarking
n_elements <- 50000
benchmark_results <- bench::mark(
  incremental  = process_incremental(n_elements),
  preallocated = process_preallocated(n_elements),
  vectorized   = process_vectorized(n_elements),
  iterations   = 10,
  check        = TRUE
)

print(benchmark_results[, c("expression", "min", "median", "itr/sec", "mem_alloc", "n_gc")])
```

---

## 8. Real-World Case Study: Enterprise Scale

### Skenario
Sebuah institusi kuantitatif perbankan memproses data streaming portofolio risiko harian. Terdapat 2.000.000 instrumen finansial yang harus divalidasi, disesuaikan dengan kurva suku bunga acuan (*volatility adjustment*), dan ditransformasikan menjadi metrik Value at Risk (VaR).

### Masalah
Implementasi awal menggunakan R script monolitik dengan iterasi berbasis dynamic `data.frame` appending via loop. Sistem kehabisan memori (OOM) pada container berkapasitas 16 GB, dengan waktu eksekusi mencapai 48 menit dan tingkat GC trashing mencapai 60% dari total runtime.

### Solusi Arsitektural Produksi
Mengubah struktur data menjadi contiguous typed matrices/atomic vectors, mengeksploitasi semantik lazy evaluation untuk bypass komputasi instrumen yang *inactive*, serta mendistribusikan beban komputasi secara *pure-functional parallel* tanpa shared memory concurrency issues.

```r
library(future)
library(furrr)
library(bench)

# Konfigurasi worker threads non-blocking
plan(multisession, workers = 4)

# 1. Domain Modeling: Factory pattern via closure untuk isolasi context
risk_engine_factory <- function(interest_rate_curve) {
  # Enclosing environment menyimpan curve imutabel
  curve <- as.numeric(interest_rate_curve)
  
  function(notionals, volatilities, days_to_expiry, status_flags) {
    # Validasi parameter dimensi (Assert early)
    n <- length(notionals)
    stopifnot(length(volatilities) == n, length(days_to_expiry) == n)
    
    # 2. Vectorized Bitmasking Filter (Bypass evaluasi instrumen inactive)
    active_mask <- status_flags == 1L
    
    # Pre-alokasi buffer output hasil
    var_results <- rep(NA_real_, n)
    
    if (!any(active_mask)) {
      return(var_results)
    }
    
    # Extract subsets untuk SIMD arithmetic
    sub_notional <- notionals[active_mask]
    sub_vol      <- volatilities[active_mask]
    sub_days     <- days_to_expiry[active_mask]
    
    # 3. Vectorized Risk Formula (Zero intermediate heap allocations)
    time_factor <- sqrt(sub_days / 365)
    # Metrik VaR 99%: 2.326 * S * vol * sqrt(t)
    computed_var <- 2.326 * sub_notional * sub_vol * time_factor * (1 + curve[1])
    
    # In-place slotting ke buffer utama
    var_results[active_mask] <- computed_var
    return(var_results)
  }
}

# 2. Data Generator Simulating 2 Million Instruments
generate_mock_instruments <- function(total_records) {
  list(
    notionals      = runif(total_records, 1e4, 1e7),
    volatilities   = runif(total_records, 0.05, 0.8),
    days_to_expiry = sample(30:720, total_records, replace = TRUE),
    status_flags   = sample(c(0L, 1L), total_records, replace = TRUE, prob = c(0.1, 0.9))
  )
}

# 3. Pipeline Eksekusi Paralel Chunked
execute_enterprise_risk_batch <- function(total_records = 2e6, chunk_size = 5e5) {
  message("Mempersiapkan dataset...")
  raw_data <- generate_mock_instruments(total_records)
  
  message("Membagi chunk dataset...")
  num_chunks <- ceiling(total_records / chunk_size)
  chunk_indices <- split(seq_len(total_records), ceiling(seq_len(total_records) / chunk_size))
  
  # Instansiasi Engine dengan scoping parameter global
  calc_risk <- risk_engine_factory(interest_rate_curve = c(0.045))
  
  message("Memulai evaluasi paralel non-blocking...")
  results <- furrr::future_map(
    chunk_indices,
    function(indices) {
      calc_risk(
        notionals      = raw_data$notionals[indices],
        volatilities   = raw_data$volatilities[indices],
        days_to_expiry = raw_data$days_to_expiry[indices],
        status_flags   = raw_data$status_flags[indices]
      )
    },
    .options = furrr_options(seed = TRUE)
  )
  
  # Flattens buffer chunks menjadi single atomic vector (Contiguous memory)
  unlist(results, use.names = FALSE)
}

# Run execution
system.time({
  final_var_vector <- execute_enterprise_risk_batch(total_records = 2e6, chunk_size = 5e5)
})
```

---

## 9. Trade-offs

| Dimensi Arsitektural | Pendekatan A: Pure Vectorization | Pendekatan B: S3/S4 Functional Closures | Pendekatan C: In-Place Mutation via Environments / C-Level Buffers |
| :--- | :--- | :--- | :--- |
| **Performance** | **Ekstrem Tinggi.** Menghilangkan interpretasi bytecode internal, memaksimalkan cache throughput. | **Menengah.** Terkena overhead dispatching fungsi dan evaluasi lexical environment frames. | **Tertinggi.** Bebas overhead duplikasi data dan alokasi ulang memori. |
| **Latency** | Sangat rendah; deterministik. Cocok untuk micro-batching. | Moderat; dipengaruhi traversal chain environment R. | Minimum latency; hampir identik dengan C native. |
| **Scalability** | Skala vertikal CPU sangat efisien. | Sangat baik untuk abstraksi domain terdistribusi (`future`). | Berbahaya untuk multi-threading jika lock-free synchronization gagal. |
| **Memory Cost** | Rendah saat beroperasi pada data atomik flat. | Cenderung tinggi jika closure menangkap pointer environment yang besar tanpa *pruning*. | Minimal, mempertahankan memory footprint flat konstan. |
| **Maintainability** | Sulit di-maintain jika logika bisnis non-linier bertambah. | **Sangat Baik.** Modular, encapsulation terisolasi, mudah diuji unit-test. | **Rendah.** Rawan side-effects dan merusak semantik immutability fungsional. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Memory Bloat Akibat Retensi Lexical Scoping Tak Disengaja
```r
# BUG: Fungsi mengikat objek besar dari environment definisi
build_model <- function() {
  massive_training_data <- runif(1e7) # ~80 MB
  intercept <- 1.45
  
  # Closure menangkap seluruh execution frame dari build_model!
  return(function(x) {
    x * intercept
  })
}

predictor <- build_model()
# massive_training_data tidak dapat di-garbage collect karena predictor
# memegang referensi ke parent environment-nya!
lobstr::obj_size(predictor) # Menunjukkan ukuran ~80 MB!

# SOLUSI: Kosongkan atau bersihkan environment sebelum return
build_model_clean <- function() {
  massive_training_data <- runif(1e7)
  intercept <- 1.45
  
  res_env <- new.env(parent = emptyenv())
  res_env$intercept <- intercept
  
  f <- function(x) {
    x * intercept
  }
  environment(f) <- res_env
  return(f)
}
predictor_clean <- build_model_clean()
lobstr::obj_size(predictor_clean) # Hanya beberapa ratus bytes
```

### Mistake 2: Type Coercion Silent Performance Killer
```r
# BUG: Memasukkan satu elemen string ke atomic numeric vector
vec <- c(1.0, 2.5, 3.8) # REALSXP (Double)
vec[2] <- "2.5"         # Mengubah SELURUH vektor menjadi STRSXP secara instan (Silent Coercion)
# Akibat: Operasi matematika berikutnya menghasilkan runtime error atau crash di modul C++ Rcpp.

# SOLUSI: Validasi tipe data ketat via stopifnot atau runtime assertion framework
safe_numeric_assign <- function(v, idx, val) {
  if (!is.numeric(val)) stop("Validation failed: Type mismatch. Expected numeric.")
  v[idx] <- val
  v
}
```

### Mistake 3: Unhandled Recursion Stack Overflow
```r
# BUG: Dynamic deep recursion melebihi R_CStackLimit
deep_recurse <- function(n) {
  if (n <= 0) return(0)
  return(1 + deep_recurse(n - 1))
}
# deep_recurse(1e6) -> "Error: C stack usage ... is too close to the limit"

# SOLUSI: Konversi ke iterative control flow atau tail-call simulation pattern
trampoline <- function(f, ...) {
  function(...) {
    ret <- f(...)
    while (is.function(ret)) {
      ret <- ret()
    }
    ret
  }
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasikan Buffer Statis:** Jangan pernah menggunakan `c()`, `cbind()`, atau `rbind()` di dalam looping. Lakukan pre-allocation dengan tipe eksplisit (`numeric(n)`, `integer(n)`).
- [ ] **Gunakan Typed Nulls:** Saat menginisialisasi vektor kosong, definisikan tipe secara spesifik (`character(0)` alih-alih `NULL` atau `c()`).
- [ ] **Batasi Retention Environment:** Buat enclosing environment minimal pada closure functions untuk menghindari memory leak dari objek intermediate berukuran besar.
- [ ] **Gunakan Condition Handling Non-Destruktif:** Pakai `withCallingHandlers` untuk observability/logging, cadangkan `tryCatch` hanya saat recovery stack unrolling benar-benar diperlukan.
- [ ] **ALTREP Awareness:** Hindari operasi non-vektor pada ALTREP objects yang memaksa alokasi materialisasi penuh ke dalam memori fisik secara prematur.
- [ ] **Hindari Metaprogramming / Non-Standard Evaluation (NSE) di Critical Path:** Fungsi berbasis `eval(parse())` atau dynamic rlang parsing berlebihan menciptakan bottleneck pada CPU cache dan bytecode JIT compiler.

---

## 12. Hands-on Practice

Buat struktur direktori praktikum berikut:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### File: `hands-on/m02/benchmark_cow.R`
Simpan kode evaluasi memory tracking berikut untuk melihat siklus hidup alokasi memori secara nyata.

```r
#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(lobstr)
  library(bench)
})

cat("=== LANGKAH 1: Inisialisasi SEXP Vektor ===\n")
data_vector <- rnorm(1e6) # ~8 MB REALSXP
cat("Address Awal Data Vector:", obj_addr(data_vector), "\n")
cat("Memory Size:", format(obj_size(data_vector)), "\n\n")

cat("=== LANGKAH 2: Shallow Copy Assignment ===\n")
shadow_ref <- data_vector
cat("Address Shadow Reference:", obj_addr(shadow_ref), "\n")
cat("Apakah kedua object identik secara memori?", identical(obj_addr(data_vector), obj_addr(shadow_ref)), "\n\n")

cat("=== LANGKAH 3: Pemicu Copy-on-Write (CoW) ===\n")
shadow_ref[1] <- 9999.99
cat("Address Shadow Reference setelah mutasi:", obj_addr(shadow_ref), "\n")
cat("Address Data Vector asli:", obj_addr(data_vector), "\n")
cat("Address identik?", identical(obj_addr(data_vector), obj_addr(shadow_ref)), "\n\n")

cat("=== LANGKAH 4: Profiling Overhead CoW dalam Loop ===\n")
cow_loop_profiling <- function(n_elements = 10000) {
  acc <- numeric(0)
  for (i in 1:n_elements) {
    acc <- c(acc, i) # Memicu duplikasi memori bertingkat
  }
  acc
}

in_place_profiling <- function(n_elements = 10000) {
  acc <- numeric(n_elements)
  for (i in 1:n_elements) {
    acc[i] <- i # Modifikasi slot langsung
  }
  acc
}

profile_result <- bench::mark(
  cow_accumulation     = cow_loop_profiling(15000),
  in_place_allocation  = in_place_profiling(15000),
  iterations = 5,
  check = TRUE
)

print(profile_result)
```

Jalankan script dengan perintah:
```bash
Rscript hands-on/m02/benchmark_cow.R
```

---

## 13. Exercises

### Level Easy
Tuliskan sebuah fungsi `safe_convert_integer(x)` yang menerima sembarang vektor. Jika vektor tersebut bertipe double dan tidak memiliki komponen pecahan (misal: `c(1.0, 2.0, 5.0)`), konversikan secara in-place ke tipe data integer (`INTSXP`) tanpa menduplikasi objek di memori jika panjang vektor $> 100.000$. Jika terdapat komponen pecahan, lemparkan condition error bertipe `conversion_fractional_error`.

### Level Medium
Rancanglah sebuah higher-order function `memoize_with_ttl(fn, ttl_seconds)` yang membungkus fungsi `fn`. Aturan implementasi:
1. Simpan cache hasil komputasi di dalam dedicated execution environment tertutup.
2. Setiap entri cache memiliki timestamp.
3. Jika pemanggilan fungsi dilakukan dengan argumen yang sama dan belum melewati `ttl_seconds`, return hasil dari cache.
4. Lakukan evaluasi cache lookup secara optimal tanpa menggunakan parsing string.

### Level Hard
Implementasikan sebuah streaming pipe custom `%>>>%` yang mengalirkan evaluasi data dari kiri ke kanan dengan sifat:
1. Tidak pernah mengevaluasi ekspresi di kanan jika ekspresi di kiri melempar error (Short-circuiting condition handling).
2. Mengeksekusi step secara lazy menggunakan promise manipulation (`substitute` dan `delayedAssign`).
3. Mencegah materialisasi data frame ke memori secara penuh jika input merupakan ALTREP generator.
4. Menginjeksi custom tracing metadata (ekspresi, waktu eksekusi CPU, dan memory delta) ke dalam atribut hasil akhir.

---

## 14. Challenge

### Studi Kasus: High-Throughput In-Memory Order Book Engine
Perusahaan prop-trading membutuhkan sistem kalkulasi order-book agregat dengan requirements berikut:
- **Input:** Feed transaksi keuangan sintetis sebanyak 5.000.000 records yang terdiri atas `timestamp` (integer), `symbol` (factor/string), `price` (double), `volume` (integer), dan `action` (1 = Buy, 2 = Sell, 3 = Cancel).
- **Limitasi Infrastruktur:** RAM Server dibatasi 512 MB per proses, dan latensi komputasi total tidak boleh melebihi 1.500 ms.
- **Tantangan Arsitektur:** 
  1. Anda dilarang menggunakan third-party wrapper data table seperti `data.table` atau `polars` (gunakan hanya Core Base R & functional primitives).
  2. Dilarang memicu alokasi copy memory sekunder (Memory delta tidak boleh melompat $> 100\text{ MB}$ di atas ukuran input raw).
  3. Desain struktur state management menggunakan circular buffers atau environment-based indexing untuk melacak running *VWAP* (Volume Weighted Average Price) dan *Order Depth* per simbol.
  4. Bangun recovery harness menggunakan `withCallingHandlers` yang menangani anomali invalid price ($P \le 0$) tanpa mematikan thread komputasi atau membuang data transaksi valid yang berurutan.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara representasi memori `VECSXP` (generic list) dan `REALSXP` (atomic vector) di C-level runtime R?
2. Mengapa instruksi `x <- 1:1e8` dialokasikan secara instan dan hanya menggunakan beberapa ratus bytes memori pada R 3.5.0 ke atas?
3. Kapan sebuah Promise (`PROMSXP`) dievaluasi di R, dan apa yang terjadi jika argumen fungsi tidak pernah dipanggil di dalam tubuh fungsinya?
4. Mengapa operasi `res <- c(res, new_item)` di dalam loop beriterasi $N$ kali memiliki kompleksitas waktu komputasi $O(N^2)$?
5. Manakah yang memiliki performa lebih tinggi: subsetting list menggunakan `[` atau `[[`? Jelaskan alasannya dari sudut pandang struktur pointer R!

### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja Generational Garbage Collector (Gen 0, Gen 1, Gen 2) di R dalam mengelola lifecycle objek sementara versus objek persisten di Global Environment?
7. Jelaskan perbedaan semantik antara fungsi `tryCatch()` dan `withCallingHandlers()` dalam hal stack unrolling!
8. Apa yang menyebabkan sebuah closure function menyebabkan "memory leak" (retensi memori liar) meskipun fungsi pembuatnya telah selesai dieksekusi?
9. Bagaimana mekanisme R membedakan antara modifikasi in-place (*modify-in-place*) dengan *copy-on-write* berdasarkan nilai `REFCNT`?
10. Mengapa lexical scoping di R merujuk pada *enclosing environment* tempat fungsi dibuat, bukan *calling environment* tempat fungsi dipanggil?

### 3 Skenario Kasus Produksi
11. **Kasus 1:** Sebuah cron-job R microservice mengalami crash Out-Of-Memory (OOM) secara periodik setiap 12 jam. Kode service menerima request HTTP via plumber, membuat model `lm()`, mengekstrak koefisien, dan mengembalikan JSON. Script tidak menyimpan objek global. Analisis di mana letak memory leak internal R yang mungkin terjadi!
12. **Kasus 2:** Anda memiliki pipeline paralel berbasis `mclapply` (forking) di platform Linux. Ketika beban komputasi diaktifkan, memori server langsung membengkak 4x lipat dari total ukuran data awal, merusak asumsi copy-on-write memory sharing antar child processes. Identifikasi apa pemicu rusaknya memory sharing pada Linux fork di runtime R tersebut!
13. **Kasus 3:** Pipeline analitik keuangan memproses matrix $10.000 \times 10.000$. Saat melakukan normalisasi kolom via `apply(mat, 2, function(x) (x - mean(x))/sd(x))`, runtime memakan waktu 45 detik dan konsumsi RAM melonjak hingga 4 GB. Bagaimana arsitektur kalkulasi ini harus dirombak total menggunakan Base R functional vectorization tanpa package eksternal?

---

### Kunci Jawaban Evaluasi

#### Jawaban Basic
1. **Perbedaan `VECSXP` vs `REALSXP`:** `REALSXP` adalah blok memori contiguous flat yang berisi raw data 64-bit IEEE double; lokalisasi cache L1/L2 maksimal. `VECSXP` adalah array of pointers, di mana setiap elemen menunjuk ke lokasi memori SEXP lain yang terpisah di heap; membutuhkan dereferensi pointer ganda dan rentan cache miss.
2. **ALTREP Sequence:** Sintaks `1:1e8` menggunakan implementasi ALTREP class integer range. Objek ini tidak mengalokasikan array 100 juta integer fisik di RAM, melainkan hanya menyimpan metadata: class representation, nilai awal (1), selisih langkah (1), dan panjang (1e8).
3. **Promise Evaluation:** Promise dievaluasi secara *lazy* (hanya saat pertama kali nilainya diakses/forced oleh ekspresi lain). Nilai hasil evaluasi kemudian disimpan (*cached/memoized*). Jika argumen tidak pernah dipanggil, expression tidak dievaluasi sama sekali dan tidak memakan waktu komputasi atau memori alokasi.
4. **Kompleksitas $O(N^2)$ pada append loop:** Karena semantik imutabilitas R dan `REFCNT > 1`, setiap pemanggilan `c(res, new_item)` menduplikasi seluruh array yang sudah terbentuk sebelumnya ke lokasi memori baru. Total elemen yang disalin adalah $\sum_{i=1}^{N} i = \frac{N(N+1)}{2}$, yang menghasilkan kompleksitas waktu $O(N^2)$.
5. **Subsetting `[` vs `[[`:** Subsetting `[[` mengekstrak tepat satu pointer SEXP secara langsung dari slot list. Subsetting `[` harus mengalokasikan container list baru (`VECSXP`) untuk membungkus elemen yang dipilih, sehingga menghasilkan overhead alokasi memori tambahan.

#### Jawaban Intermediate
6. **Mekanisme Generational GC R:** 
   - *Gen 0:* Menampung alokasi baru objek transien; dipindai dan dibersihkan paling sering.
   - *Gen 1:* Objek yang selamat dari pembersihan Gen 0 dipromosikan ke Gen 1; dipindai lebih jarang.
   - *Gen 2:* Objek yang bertahan lama (seperti libraries, base packages, global persistent data) dipromosikan ke Gen 2; hanya diperiksa pada saat pembersihan menyeluruh (*full GC collect*), meminimalkan waktu henti (*pause time*).
7. **`tryCatch()` vs `withCallingHandlers()`:**
   - `tryCatch()` melakukan stack unrolling: ketika condition sinyal tertangkap, execution stack langsung dibongkar kembali ke titik deklarasi `tryCatch`, merusak konteks eksekusi tempat error terjadi.
   - `withCallingHandlers()` mengeksekusi handler di dalam execution context tempat error dipicu (tanpa unrolling stack). Ini memungkinkan inspeksi call stack penuh, pembuatan dump state, logging kondisi lokal, atau memicu restarts sebelum memutuskan pembatalan.
8. **Memory Leak pada Closure:** Closure secara otomatis mengikat pointer ke *enclosing environment*-nya. Jika enclosing environment memuat variabel atau objek berukuran besar yang tidak digunakan lagi oleh fungsi closure tersebut, objek besar tersebut tetap terkunci di heap memory dan GC dilarang membersihkannya selama fungsi closure masih memiliki referensi aktif.
9. **Logika `REFCNT` / `NAMED`:** Ketika R mengevaluasi mutasi objek, engine membaca atribut referensi:
   - Jika `REFCNT <= 1`: Tidak ada variabel lain yang memegang objek tersebut, mutasi dilakukan langsung di buffer memori fisik yang ada (*in-place modification*).
   - Jika `REFCNT > 1`: Terdapat referensi jamak ke data tersebut, maka R engine memicu fungsi C internal `duplicate()` untuk mengkloning data ke memori baru sebelum menerapkan mutasi (*Copy-on-Write*).
10. **Lexical Scoping vs Dynamic Scoping:** Lexical Scoping mengikat relasi environment berdasarkan struktur sintaksis penulisan kode sumber pada saat fungsi didefinisikan (*compile/parse time*), bukan urutan pemanggilan fungsi pada stack (*runtime*). Ini memastikan perilaku fungsi bersifat deterministik, independen terhadap lokasi dari mana fungsi tersebut dipanggil.

#### Jawaban Skenario Kasus Produksi
11. **Kasus 1 - Diagnostic & Solusi:**
    Objek formula pada `lm(formula, data)` di R secara otomatis menangkap environment tempat ia didefinisikan (`environment(formula)`). Saat model linear dibuat di dalam handler HTTP, objek model mengikat seluruh execution frame handler tersebut. Jika koefisien diekstrak namun model atau objek formula secara tidak sengaja tersimpan ke logging, cache handler, atau serialisasi parsial, seluruh environment handler beserta payload HTTP-nya tertahan dari GC.
    *Solusi:* Putus referensi environment pada formula sebelum serialisasi atau hapus komponen `$terms` dan `attr(model$terms, ".Environment") <- emptyenv()`.
12. **Kasus 2 - Diagnostic & Solusi:**
    Fitur forking Linux mengandalkan mekanisme OS Copy-on-Write (CoW). Namun, R Garbage Collector secara periodik mengubah bitflag `mark` pada header `SEXPREC` di seluruh objek memori selama GC sweeps berlangsung. Tindakan GC ini memodifikasi halaman memori virtual pada proses child. Modifikasi pada memory page ini memaksa kernel OS memecah *shared pages* dan mengalokasikan halaman fisik baru yang independen di setiap process worker.
    *Solusi:* Sebelum menjalankan `mclapply`, panggil `gc()` secara eksplisit di proses parent untuk menormalkan status memori, matikan compactor sweep jika memungkinkan, atau beralih menggunakan backend thread pools / shared-memory memory-mapped buffers (`bigstatsr` / `arrow`).
13. **Kasus 3 - Diagnostic & Solusi:**
    Fungsi `apply()` memecah matrix menjadi list slice vektor 1 dimensi per kolom di level R bytecode interpreter, yang menciptakan jutaan alokasi transien, disusul overhead loop interpretasi fungsi.
    *Solusi:* Terapkan teknik purely vectorized broadcasting Base R:
    ```r
    # Hitung column means dan column sds menggunakan primitives internal C
    col_means <- colMeans(mat)
    # colSums matrix algebra untuk varians/sd instan
    col_vars <- (colSums(mat^2) - 10000 * col_means^2) / (10000 - 1)
    col_sds <- sqrt(col_vars)
    
    # Normalisasi via matrix sweep vectorized operation
    normalized_mat <- t((t(mat) - col_means) / col_sds)
    # ATAU menggunakan native Base R function:
    normalized_mat <- scale(mat, center = TRUE, scale = TRUE)
    ```
    Pendekatan ini memangkas eksekusi dari 45 detik menjadi < 150 milidetik dengan footprint memori flat karena seluruh perulangan dieksekusi di level assembly compiled BLAS / Lapack C loops.

---

## 16. Summary

1. **SEXP & Memory Engine:** Pemahaman mendalam terhadap struktur internal `SEXPREC` dan status mutasi pointer C merupakan fondasi utama optimasi komputasi performa tinggi di R.
2. **Eliminasi CoW Overhead:** Desain struktur data statis (*pre-allocation*) dan hindari perubahan tipe dinamis (*dynamic type coercion*) untuk mempertahankan operasi write in-place.
3. **Optimasi ALTREP Modern:** Manfaatkan representasi algoritmik ALTREP untuk mengolah dataset besar tanpa menimbulkan jejak memori (*zero physical allocation*).
4. **Lexical Scoping & Memory Safety:** Selalu isolasi execution environment pada closure factories guna mencegah kebocoran memori dari referensi objek yang tertahan secara tidak disengaja.
5. **Production Fault Tolerance:** Pisahkan observability logging dan stack recovery menggunakan `withCallingHandlers` untuk mempertahankan visibilitas sistem secara menyeluruh saat terjadi anomali runtime.