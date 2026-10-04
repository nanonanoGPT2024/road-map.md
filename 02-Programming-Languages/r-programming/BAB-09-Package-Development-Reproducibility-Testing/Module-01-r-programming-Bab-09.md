# BAB 09 MODULE 01: Package Development, Reproducibility, & Testing

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: R-PROG-09-01
* **Judul**: Package Development, Reproducibility, & Testing
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**:
  * Penguasaan S3 Object-Oriented Programming dalam R.
  * Pemahaman mendalam terkait R Environments, Closures, dan Non-Standard Evaluation (NSE / Tidy Evaluation).
  * Pengalaman menggunakan Git version control dan command line interface (CLI).
* **Alokasi Waktu**: 18 Jam Pembelajaran (6 Jam Teori Komprehensif, 12 Jam Praktikum & Proyek).
* **Target Capaian**: Insinyur perangkat lunak dan data scientist mampu mengemas kode R modular ke dalam struktur paket standar industri (CRAN-compliant), mengimplementasikan automasi pengujian unit berbasis `testthat` edition 3, menyusun dokumentasi deklaratif via `roxygen2`, serta mengunci determinisme dependensi sistem runtime menggunakan `renv`.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1. **Mengonstruksi dan Mengotomasi Struktur Paket R**: Membangun arsitektur paket R standar produksi menggunakan `usethis` dan `devtools` dengan isolasi `NAMESPACE` dan deklarasi dependensi yang tepat pada `DESCRIPTION`.
2. **Mengelola Dokumentasi Deklaratif**: Mengintegrasikan `roxygen2` tags untuk menghasilkan dokumentasi fungsi, datasets, dan S3 method generics secara otomatis, valid, serta sinkron dengan interface API.
3. **Menerapkan Testing Harness Komprehensif**: Merancang test suite deterministik menggunakan framework `testthat` (Edition 3), mencakup unit testing, boundary testing, mocking external APIs, dan snapshot testing.
4. **Menjamin Reproduksibilitas Deterministik**: Mengisolasi *dependency tree* lingkungan komputasi menggunakan `renv`, mengontrol state lockfile, dan mengompilasi artefak biner yang identik lintas mesin.
5. **Menjalankan Validasi Statis dan Dinamis Standar CRAN**: Menuntaskan siklus `R CMD check --as-cran` dengan toleransi **0 ERROR | 0 WARNING | 0 NOTE**, serta mengeliminasi kebocoran variabel global (NSE issues) via arsitektur kode statis yang bersih.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Scripting vs. Package Engineering
Banyak analis mendekati R sebagai lingkungan eksekusi skrip linier: skrip dibaca dari atas ke bawah, variabel global diinjeksikan ke `.GlobalEnv` melalui operator assign `<-`, dependensi dimuat serampangan via `library()`, dan fungsi-fungsi bergantung pada state eksternal yang rapuh. 

Pendekatan ini tidak *scalable* dan rentan mengalami *silent failures* di lingkungan produksi.

```
Pendekatan Skrip (Imperatif / Stateful):
[Global Environment] <-- Menumpuk variabel bebas
        │
  source("a.R")  --> Mengubah state global
        │
  library(dplyr) --> Membayangi fungsi base (masking)
        │
  source("b.R")  --> Berpotensi crash jika state variabel lokal berubah

Pendekatan Package (Fungsional / Hermetik):
[Isolated Package Namespace]
        │ (Imports eksplisit via NAMESPACE)
  +───────────────────────────────────+
  │ Core Logic & Pure Functions       │
  │ - State terisolasi                │
  │ - Explicit foreign functions call │
  +───────────────────────────────────+
        │ (Exports selektif)
[Consumer Application / API Endpoint]
```

### Mental Model Hermetisitas dan Imutabilitas
1. **Hermetic Execution (Isolasi Mutlak)**: Kode yang berada dalam paket tidak boleh mengasumsikan keberadaan objek apa pun di luar yang dideklarasikan secara eksplisit dalam dependensinya. Jika fungsi Anda membutuhkan `mutate()`, fungsi tersebut harus memanggilnya melalui `dplyr::mutate` atau mendaftarkannya pada direktif `importFrom` di file `NAMESPACE`.
2. **Deterministic Lifecycle**: Paket R bukan sekadar repositori kode, melainkan sebuah artefak biner tervolusi yang melewati siklus hidup: *Source Code* $\rightarrow$ *Bundled Package* $\rightarrow$ *Binary Package* $\rightarrow$ *Installed Package* $\rightarrow$ *Loaded Package* $\rightarrow$ *Attached Package*. Mengetahui posisi eksekusi Anda pada siklus ini mencegah kesalahan pemanggilan simbol memori internal.
3. **Strict Invariant Testing**: Test suite bukanlah opsi tambahan, melainkan spesifikasi fungsional matematis dari software Anda. Pengujian harus memvalidasi kontrak input-output, invarian tipe data, dan batas toleransi komputasi floating point.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup dan Pipa Kompilasi R Package

```
+─────────────────────────────────────────────────────────────────────────+
|                           SOURCE DIRECTORY                              |
|  - DESCRIPTION                                                          |
|  - NAMESPACE                                                            |
|  - R/*.R                                                                |
|  - tests/testthat/*.R                                                   |
|  - src/* (C/C++ jika ada)                                               |
+─────────────────────────────────────────────────────────────────────────+
                                     │
                                     ▼  devtools::document() / roxygen2
+─────────────────────────────────────────────────────────────────────────+
|               AUTOGENERATED ARTIFACTS / META-PARSING                    |
|  - man/*.Rd                                                             |
|  - NAMESPACE (Updated exports/imports)                                  |
+─────────────────────────────────────────────────────────────────────────+
                                     │
                                     ▼  devtools::test() / testthat
+─────────────────────────────────────────────────────────────────────────+
|                          TEST SUITE HARNESS                             |
|  - Unit Tests                                                           |
|  - Snapshot Tests                                                       |
|  - Mock Testing                                                         |
+─────────────────────────────────────────────────────────────────────────+
                                     │
                                     ▼  R CMD build
+─────────────────────────────────────────────────────────────────────────+
|                     PACKAGE BUNDLE (.tar.gz)                            |
+─────────────────────────────────────────────────────────────────────────+
                                     │
                                     ▼  R CMD check --as-cran
+─────────────────────────────────────────────────────────────────────────+
|                       DIAGNOSTIC PIPELINE                               |
|  - Structural Integrity                                                 |
|  - Namespace Consistency                                                |
|  - Documentation Completeness                                           |
|  - Code Execution & Example Parsing                                     |
|  - Global Symbols & Memory Leak Detection                              |
+─────────────────────────────────────────────────────────────────────────+
            │ (Status: 0 ERROR, 0 WARNING, 0 NOTE)
            ▼
+─────────────────────────────────────────────────────────────────────────+
|                PRODUCTION DEPLOYMENT / CRAN RELEASE                     |
|  - renv.lock update                                                     |
|  - System Installation (R CMD INSTALL)                                  |
+─────────────────────────────────────────────────────────────────────────+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Anatomi Fisik File dan Direktori

Setiap paket R terstruktur secara terstandardisasi pada sistem berkas:

```
my_enterprise_package/
├── .Rbuildignore          # RegEx pola berkas yang diabaikan saat R CMD build
├── .gitignore             # Berkas kontrol versi git
├── DESCRIPTION            # Metadata paket, dependensi, dan lisensi
├── NAMESPACE              # Kontrak eksternal API: simbol yang diekspor dan diimpor
├── LICENSE / LICENSE.md   # Berkas lisensi legal (MIT, Apache, GPL, dll.)
├── R/                     # Direktori logika aplikasi kode R murni
│   ├── api_client.R
│   ├── transformers.R
│   └── utils.R
├── man/                   # Berkas dokumentasi format Rd (hasil generasi roxygen2)
│   ├── api_client.Rd
│   └── transformers.Rd
├── tests/                 # Automation test harness
│   ├── testthat.R         # Runner file untuk menjalankan testthat engine
│   └── testthat/          # Implementasi unit test
│       ├── setup-context.R
│       ├── test-api_client.R
│       └── test-transformers.R
└── renv/                  # Direktori infrastruktur isolasi dependensi renv
    ├── activate.R
    └── settings.json
├── renv.lock              # JSON file yang memetakan hash dependensi secara absolut
```

### Mekanisme Internal: Search Path vs. Namespaces

Ketika Anda mengeksekusi `library(foo)`:
1. Paket `foo` dimuat ke dalam memori (*loaded*) ke dalam `package:foo` environment.
2. Lingkungan paket `foo` disisipkan ke dalam sistem pencarian global R (*attached* ke `search()`).
3. Di dalam arsitektur internal, paket memiliki **dua environment utama**:
   * **Namespace Environment**: Berisi semua fungsi internal (baik diekspor maupun unexported). *Parent environment*-nya adalah `imports:foo`, yang mewarisi secara langsung dari objek yang diimpor dari dependensi lain, dan berujung pada *base namespace*.
   * **Package Environment**: Antarmuka publik yang ditempelkan ke `search()`. *Parent environment*-nya berubah-ubah tergantung paket apa yang di-*attach* setelahnya.

```
[search() Path]
.GlobalEnv -> package:foo -> package:stats -> ... -> package:base

[Internal Namespace Path untuk package:foo]
Namespace:foo
     │ (parent)
Imports:foo (Simbol-simbol eksplisit dari NAMESPACE file)
     │ (parent)
Namespace:base
```

Hal ini memastikan bahwa resolusi nama internal fungsi di dalam paket Anda tidak dapat dioverwrite/dibayangi (*shadowed*) oleh skrip pemanggil di `.GlobalEnv`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. File `DESCRIPTION`: Kontrak Metadata & Arsitektur Dependensi
File `DESCRIPTION` menggunakan format Debian Control File (DCF). Parameter terpenting adalah pendefinisian dependensi:

* **`Depends`**: Memaksa sistem memuat dan *meng-attach* paket terkait ke `search()` path pengguna. 
  * *Praktik Modern*: **Hindari penggunaan `Depends`** kecuali untuk paket yang memodifikasi sistem bahasa inti (seperti paket R base), karena mencemari namespace pengguna. Pengecualian hanya untuk r-core dependensi minimal, misal: `Depends: R (>= 4.1.0)`.
* **`Imports`**: Paket yang harus terinstalasi. Simbol-simbolnya digunakan secara internal oleh paket Anda via `pkg::func()` atau direktif `@importFrom`. Paket-paket ini dimuat ke memori (*loaded*), tetapi **tidak** di-*attach* ke `search()` pengguna.
* **`Suggests`**: Dependensi sekunder yang digunakan hanya untuk menjalankan pengujian (`testthat`), membangun dokumentasi/vignettes, atau modul fungsionalitas opsional. Pengguna tidak diwajibkan menginstalnya kecuali membutuhkan fitur tersebut.

### 2. File `NAMESPACE` & `roxygen2`
File `NAMESPACE` membatasi visibilitas kode:
* `export(func_name)`: Mengekspos fungsi ke publik.
* `importFrom(package, symbol)`: Membawa fungsi eksternal ke dalam scope paket tanpa memanggil sintaks berat `package::symbol()` berulang kali.
* `S3method(generic, class)`: Mendaftarkan metode S3 ke dalam tabel *method dispatch*.

Mengedit file `NAMESPACE` secara manual rentan kesalahan (*error-prone*). Gunakan `roxygen2` dengan menyematkan tag deklaratif tepat di atas deklarasi fungsi.

### 3. Tidy Evaluation dan Non-Standard Evaluation (NSE) pada R CMD check
Tantangan terbesar saat membuat paket R yang menggunakan ekosistem `tidyverse` (seperti `dplyr` atau `ggplot2`) adalah NSE. Saat menulis:

```r
# Ini memicu NOTE: no visible binding for global variable 'mpg'
subset_data <- function(df) {
  dplyr::filter(df, mpg > 20)
}
```

Alat analisis statis `R CMD check` memeriksa simbol bebas dan menandai `mpg` sebagai variabel global tak terdefinisi. Untuk mengatasi hal ini secara idiomatis, gunakan injection operator `{{ }}` (curly-curly) atau pronouns `.data` dari package `rlang`.

### 4. Hermetisitas Dependensi dengan `renv`
`renv` menciptakan kompartemen independen untuk pustaka R Anda:
* Menggantikan direktori library sistem global dengan sandboxed library lokal (`renv/library`).
* `renv.lock` mencatat metadata deterministik: Nama repositori, SHA komit, versi tepat, dan sumber binary/source dari setiap paket yang digunakan.
* Mencegah paradoks dependency rot, di mana pembaruan pustaka di tingkat OS/Host mematahkan logika internal paket.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah alur lengkap membangun scaffolding paket bernama `statscalcr`, mengonfigurasi dependensi, mengimplementasikan fungsi pure functional, dan mendokumentasikannya.

### Langkah 1: Scaffolding Paket

Jalankan perintah ini di R Console untuk membuat kerangka kerja:

```r
# Jalankan di R Console (Bukan di dalam script package)
usethis::create_package(path = "statscalcr", rstudio = FALSE, open = FALSE)
setwd("statscalcr")
usethis::use_roxygen_md()
usethis::use_testthat(edition = 3)
usethis::use_package("rlang", type = "Imports")
usethis::use_package("purrr", type = "Imports")
usethis::use_package("bench", type = "Suggests")
```

### Langkah 2: Mengatur File `DESCRIPTION`
Perbarui file `DESCRIPTION` secara manual atau programatis:

```dcf
Package: statscalcr
Title: Robust Statistical Calculation and Scale Estimator Engine
Version: 0.1.0
Authors@R: 
    person("Jane", "Doe", , "jane.doe@enterprise.com", role = c("aut", "cre"))
Description: Provides high-performance, resilient statistical summary 
    functions designed for production batch validation and streaming sanity checks.
License: MIT + file LICENSE
Encoding: UTF-8
Roxygen: list(markdown = TRUE)
RoxygenNote: 7.3.1
Depends: 
    R (>= 4.1.0)
Imports: 
    purrr (>= 1.0.0),
    rlang (>= 1.1.0)
Suggests: 
    bench,
    testthat (>= 3.2.0)
```

### Langkah 3: Implementasi Fungsi Inti (`R/scale_estimator.R`)

```r
#' @title Calculate Trimmed Scale Metrics
#' @description Computes robust dispersion metrics by calculating a winsorized 
#'   standard deviation, safe against extreme outlier pollution.
#'
#' @param x A numeric vector. Missing values are filtered based on `na.rm`.
#' @param trim A single numeric value between 0 and 0.5 defining the trimming fraction.
#' @param na.rm A logical evaluating to TRUE if NA values must be removed.
#'
#' @return A list containing calculated statistical attributes:
#'   \item{trimmed_mean}{The computed trimmed mean value.}
#'   \item{robust_sd}{Estimated robust standard deviation.}
#'   \item{sample_size}{The effective number of observations evaluated.}
#'
#' @export
#' @importFrom rlang abort is_numeric
#' @examples
#' data <- c(1.2, 2.3, 2.8, 3.1, 105.4) # Outlier intentionally included
#' robust_scale(data, trim = 0.2)
robust_scale <- function(x, trim = 0.1, na.rm = TRUE) {
  if (!rlang::is_numeric(x)) {
    rlang::abort(
      message = paste0("Input 'x' must be numeric. Received type: ", typeof(x)),
      class = "statscalcr_type_error"
    )
  }

  if (!is.numeric(trim) || length(trim) != 1 || trim < 0 || trim >= 0.5) {
    rlang::abort(
      message = "Argument 'trim' must be a single numeric scalar in range [0, 0.5).",
      class = "statscalcr_parameter_error"
    )
  }

  if (na.rm) {
    x <- x[!is.na(x)]
  } else if (any(is.na(x))) {
    rlang::abort(
      message = "Vector 'x' contains NA values and na.rm is FALSE.",
      class = "statscalcr_na_present"
    )
  }

  n <- length(x)
  if (n < 3) {
    rlang::abort(
      message = "Computation requires at least 3 valid observations.",
      class = "statscalcr_insufficient_data"
    )
  }

  sorted_x <- sort(x)
  k <- floor(n * trim)

  # Winsorization mapping
  low_val <- sorted_x[k + 1]
  high_val <- sorted_x[n - k]
  
  winsorized_x <- sorted_x
  if (k > 0) {
    winsorized_x[seq_len(k)] <- low_val
    winsorized_x[seq(n - k + 1, n)] <- high_val
  }

  t_mean <- mean(sorted_x[(k + 1):(n - k)])
  # Robust Winzorized SD adjusted with Bessel's correction factor
  w_var <- sum((winsorized_x - mean(winsorized_x))^2) / (n - 1)
  r_sd <- sqrt(w_var)

  structure(
    list(
      trimmed_mean = t_mean,
      robust_sd = r_sd,
      sample_size = n
    ),
    class = "statscalcr_result"
  )
}

#' @export
print.statscalcr_result <- function(x, ...) {
  cat("--- Robust Scale Estimator Output ---\n")
  cat(sprintf("Effective Sample Size : %d\n", x$sample_size))
  cat(sprintf("Trimmed Mean          : %.4f\n", x$trimmed_mean))
  cat(sprintf("Robust Std Dev        : %.4f\n", x$robust_sd))
  invisible(x)
}
```

### Langkah 4: Implementasi Unit Testing (`tests/testthat/test-scale_estimator.R`)

```r
testthat::test_that("robust_scale calculates correct metrics under normal conditions", {
  vals <- c(10, 11, 12, 13, 14, 15, 100) # 100 outlier
  res <- robust_scale(vals, trim = 1/7, na.rm = TRUE)

  testthat::expect_s3_class(res, "statscalcr_result")
  testthat::expect_equal(res$sample_size, 7)
  # Trimmed removes 10 and 100, leaving 11, 12, 13, 14, 15: mean is 13
  testthat::expect_equal(res$trimmed_mean, 13)
  testthat::expect_type(res$robust_sd, "double")
})

testthat::test_that("robust_scale enforces defensive argument validation", {
  testthat::expect_error(
    robust_scale("invalid string"),
    class = "statscalcr_type_error"
  )

  testthat::expect_error(
    robust_scale(c(1, 2, 3), trim = 0.8),
    class = "statscalcr_parameter_error"
  )

  testthat::expect_error(
    robust_scale(c(1, NA, 3), na.rm = FALSE),
    class = "statscalcr_na_present"
  )

  testthat::expect_error(
    robust_scale(c(1, 2)),
    class = "statscalcr_insufficient_data"
  )
})
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mengurai implementasi `R/scale_estimator.R` dari Seksi 07:

* **Baris 1–17 (`#' @title`, `#' @param`, `#' @return`, `#' @export`, `#' @importFrom`)**: Komentar khusus roxygen2.
  * Tag `@export` menginstruksikan `roxygen2` untuk menambahkan baris `export(robust_scale)` ke dalam file `NAMESPACE`. Tanpa ini, fungsi menjadi private/internal dan tidak dapat diakses langsung oleh konsumen library tanpa menggunakan operator triple colon `:::`.
  * `@importFrom rlang abort is_numeric`: Memasukkan fungsi-fungsi spesifik ini ke namespace internal paket. Mengurangi *overhead lookup* dinamis serta mendokumentasikan asal dependensi secara eksplisit.
* **Baris 19–24**:
  ```r
  if (!rlang::is_numeric(x)) {
    rlang::abort(
      message = paste0("Input 'x' must be numeric. Received type: ", typeof(x)),
      class = "statscalcr_type_error"
    )
  }
  ```
  Alih-alih `stop()`, kita memanggil `rlang::abort()` dengan menyematkan metadata `class`. Penggunaan custom condition classes memfasilitasi programmatic inspection saat pengujian unit atau *structured exception handling* via `tryCatch()`.
* **Baris 26–31**: Pengecekan skalar invarian batas. Menguji tidak hanya tipe data, tetapi juga panjang (`length(trim) != 1`) dan rentang domain matematis ($0 \le \text{trim} < 0.5$).
* **Baris 33–39**: Penanganan `NA` hermetis. Jika `na.rm = FALSE` dan ada `NA`, eksekusi segera dihentikan dengan sinyal error yang jelas, alih-alih mengalirkan nilai NaN yang merusak perhitungan hilir.
* **Baris 48–56 (Winsorization Process)**:
  ```r
  low_val <- sorted_x[k + 1]
  high_val <- sorted_x[n - k]
  ```
  Mengambil nilai ambang batas bawah dan atas secara deterministik, lalu menggantikan data pada tail distribusi untuk menstabilkan varians dari pengaruh anomali/outlier.
* **Baris 63–70**:
  ```r
  structure(
    list(...),
    class = "statscalcr_result"
  )
  ```
  Mengembalikan output sebagai structured S3 object. Pendekatan ini memisahkan representasi data dari representasi visual.
* **Baris 73–79**:
  ```r
  #' @export
  print.statscalcr_result <- function(x, ...) {
    ...
    invisible(x)
  }
  ```
  Implementasi metode S3 `print`. Tag `@export` akan secara otomatis dikenali roxygen2 untuk didaftarkan sebagai `S3method(print, statscalcr_result)` dalam file `NAMESPACE`. Metode cetak selalu mengembalikan objek utama secara `invisible(x)` untuk mempertahankan pipeline fungsional jika diintegrasikan dengan method chaining.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi: Mesin Penilaian Risiko Finansial (Enterprise Anti-Fraud System)
Sebuah institusi perbankan multinasional membutuhkan pustaka komputasi statistik internal bernama `fraudguard`. Pustaka ini dieksekusi di dalam container orchestration (Kubernetes) untuk menghitung anomali skor transaksi kartu kredit secara real-time maupun batch execution.

### Permasalahan Teknis:
1. **Flaky Dependency Matrix**: Library komputasi eksternal sering memperbarui versi di CRAN, menyebabkan inkonsistensi kalkulasi floating point pada klaster Kubernetes saat replikasi instance baru dijalankan.
2. **NSE Vulnerability & Memory Bloat**: Implementasi sebelumnya menggunakan `dplyr::filter(amount > threshold)` yang memicu catatan `no visible binding for global variable` saat audit kepatuhan kode dan berpotensi salah mengambil variabel lingkungan global (`threshold` dari luar skrip).
3. **Audit Kepatuhan & Regulasi**: Seluruh dependensi pihak ketiga harus dikunci (*locked*), dan performa fungsi analitik inti harus diuji dengan *zero tolerance* terhadap runtime crash.

### Solusi Arsitektural:
1. Merancang paket terstruktur `fraudguard` dengan validasi kontrak skema input via `vctrs` / `rlang`.
2. Penggunaan `renv` level enterprise yang membekukan versi R dan package hashes ke dalam lockfile internal yang aman.
3. Arsitektur data masking yang aman menggunakan *tidy evaluation pronoun* `.data[[var]]` untuk mengeliminasi NOTE R CMD check secara permanen.
4. Test harness komprehensif mencakup snapshot error dan deterministic numerical tests.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah file implementasi paket `fraudguard` yang siap pakai untuk kasus nyata penilaian anomali fraud.

### 1. Struktur File: `R/fraud_detector.R`

```r
#' @title Evaluate Financial Transaction Anomalies
#' @description Implements sliding scale z-score analysis over customer historical 
#'   transaction records to detect potential fraudulent spikes.
#'
#' @param data A data.frame or tibble containing customer transactional ledger.
#' @param id_col Character string representing customer identifier column name.
#' @param amount_col Character string representing the numeric transactional amount column.
#' @param threshold Numeric scalar for threshold cutoff (standard deviations). Default 3.0.
#'
#' @return A data.frame subset containing flagged anomalies with appended diagnostic columns:
#'   \item{rolling_mean}{Calculated baseline mean for the subject}
#'   \item{rolling_sd}{Calculated baseline standard deviation}
#'   \item{anomaly_score}{Calculated absolute z-score}
#'
#' @export
#' @importFrom rlang .data abort is_character is_null
#' @examples
#' df <- data.frame(
#'   cust_id = c("A", "A", "A", "A", "B", "B"),
#'   tx_amount = c(10.5, 11.0, 9.8, 500.0, 100.0, 105.0)
#' )
#' detect_anomalies(df, id_col = "cust_id", amount_col = "tx_amount", threshold = 2.0)
detect_anomalies <- function(data, id_col, amount_col, threshold = 3.0) {
  # 1. Structural Validations
  if (!is.data.frame(data)) {
    rlang::abort("Input 'data' must inherit from data.frame.", class = "fraudguard_invalid_dataframe")
  }
  
  if (!rlang::is_character(id_col) || length(id_col) != 1) {
    rlang::abort("'id_col' must be a single string.", class = "fraudguard_param_error")
  }

  if (!rlang::is_character(amount_col) || length(amount_col) != 1) {
    rlang::abort("'amount_col' must be a single string.", class = "fraudguard_param_error")
  }

  cols <- names(data)
  if (!id_col %in% cols) {
    rlang::abort(sprintf("Column '%s' not found in dataset.", id_col), class = "fraudguard_missing_column")
  }
  if (!amount_col %in% cols) {
    rlang::abort(sprintf("Column '%s' not found in dataset.", amount_col), class = "fraudguard_missing_column")
  }

  if (!is.numeric(data[[amount_col]])) {
    rlang::abort(sprintf("Column '%s' must contain numeric values.", amount_col), class = "fraudguard_type_error")
  }

  # 2. Pure Execution via Base Splitting (Eliminates Heavy External Framework Overhead)
  split_records <- split(data, data[[id_col]])

  flagged_list <- lapply(split_records, function(sub_df) {
    amounts <- sub_df[[amount_col]]
    n <- length(amounts)

    if (n < 3) {
      return(NULL) # Insufficient statistical power to compute sigma
    }

    mu <- mean(amounts, na.rm = TRUE)
    sigma <- stats::sd(amounts, na.rm = TRUE)

    # If zero variance exists across records
    if (is.na(sigma) || sigma < .Machine$double.eps) {
      return(NULL)
    }

    z_scores <- abs((amounts - mu) / sigma)
    is_anomaly <- z_scores > threshold

    if (!any(is_anomaly)) {
      return(NULL)
    }

    sub_res <- sub_df[is_anomaly, , drop = FALSE]
    sub_res$rolling_mean <- mu
    sub_res$rolling_sd <- sigma
    sub_res$anomaly_score <- z_scores[is_anomaly]
    sub_res
  })

  # 3. Aggregation of Sparse Results
  consolidated <- do.call(rbind, flagged_list)
  if (is.null(consolidated) || nrow(consolidated) == 0) {
    # Kembalikan empty frame dengan skema yang terdefinisi rapi
    empty_df <- data[0, , drop = FALSE]
    empty_df$rolling_mean <- numeric(0)
    empty_df$rolling_sd <- numeric(0)
    empty_df$anomaly_score <- numeric(0)
    rownames(empty_df) <- NULL
    return(empty_df)
  }

  rownames(consolidated) <- NULL
  consolidated
}
```

### 2. File Pengujian Unit & Robustness: `tests/testthat/test-fraud_detector.R`

```r
testthat::test_that("detect_anomalies correctly detects extreme transactional deviations", {
  test_data <- data.frame(
    account_id = c("ACC1", "ACC1", "ACC1", "ACC1", "ACC2", "ACC2", "ACC2"),
    amount = c(100.0, 102.0, 98.0, 10000.0, 50.0, 52.0, 49.0),
    stringsAsFactors = FALSE
  )

  alerts <- detect_anomalies(
    data = test_data,
    id_col = "account_id",
    amount_col = "amount",
    threshold = 1.5
  )

  testthat::expect_s3_class(alerts, "data.frame")
  testthat::expect_equal(nrow(alerts), 1)
  testthat::expect_equal(alerts$account_id[1], "ACC1")
  testthat::expect_equal(alerts$amount[1], 10000.0)
  testthat::expect_true(alerts$anomaly_score[1] > 1.5)
})

testthat::test_that("detect_anomalies handles corner cases without throwing unhandled signals", {
  # Kasus: Seluruh nasabah memiliki transaksi identik (Standar deviasi = 0)
  zero_var_data <- data.frame(
    account_id = c("ACC1", "ACC1", "ACC1"),
    amount = c(10.0, 10.0, 10.0)
  )

  testthat::expect_no_error({
    res <- detect_anomalies(zero_var_data, "account_id", "amount")
  })
  testthat::expect_equal(nrow(res), 0)
  testthat::expect_true("anomaly_score" %in% names(res))

  # Kasus: Observasi per grup kurang dari batas minimum statistik (n < 3)
  low_obs_data <- data.frame(
    account_id = c("ACC1", "ACC1"),
    amount = c(10.0, 1000.0)
  )
  res_low <- detect_anomalies(low_obs_data, "account_id", "amount")
  testthat::expect_equal(nrow(res_low), 0)
})

testthat::test_that("detect_anomalies aborts safely on illegal input shapes", {
  invalid_matrix <- matrix(1:10, ncol = 2)
  testthat::expect_error(
    detect_anomalies(invalid_matrix, "id", "amount"),
    class = "fraudguard_invalid_dataframe"
  )

  valid_df <- data.frame(id = 1:5, val = 1:5)
  testthat::expect_error(
    detect_anomalies(valid_df, "non_existent_column", "val"),
    class = "fraudguard_missing_column"
  )
})
```

### 3. File Setup Reproduksibilitas: `renv.lock` (Cuplikan Konfigurasi Minimal)

```json
{
  "R": {
    "Version": "4.3.3",
    "Repositories": [
      {
        "Name": "CRAN",
        "URL": "https://packagemanager.posit.co/cran/2024-03-01"
      }
    ]
  },
  "Packages": {
    "rlang": {
      "Package": "rlang",
      "Version": "1.1.3",
      "Source": "Repository",
      "Repository": "CRAN",
      "Hash": "42696660f56a59600a7905f6396e47be"
    },
    "testthat": {
      "Package": "testthat",
      "Version": "3.2.1",
      "Source": "Repository",
      "Repository": "CRAN",
      "Hash": "0cf2a4fb8f504d6e902c2e6fca78e792"
    }
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih arsitektur dependensi dan testing strategy dalam pembuatan paket menuntut evaluasi trade-off teknis:

| Karakteristik / Pilihan | `Imports` Spesifik vs `Depends` | Tidyverse vs Base R murni dalam Paket | `testthat` (3e) vs `RUnit` / `tinytest` |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | **Imports:** Sangat Rendah. Mengisolasi ruang simbolis.<br>**Depends:** Tinggi. Membebani seluruh search path pengguna. | **Tidyverse:** Tinggi (puluhan transitive dependencies).<br>**Base R:** Minimal (Zero external dependencies). | **testthat:** Menengah-Besar.<br>**tinytest:** Nol dependensi, footprint super ringan. |
| **Kecepatan Cold-Start / CI**| Cepat saat inisialisasi lingkungan. | **Base R:** Instan saat dimuat.<br>**Tidyverse:** Menambah waktu build kontainer Docker (compilation time). | **tinytest:** Kompilasi test instan.<br>**testthat:** Sedikit lebih lambat namun memiliki paralelisme (`testthat::test_local()`). |
| **Keterbacaan Kode & Fitur**| Imports memaksa kejelasan pemanggilan simbol (`pkg::fun`). | **Tidyverse:** Ekspresif, readable via pipelines.<br>**Base R:** Verbose, membutuhkan defensive programming manual. | **testthat (3e):** Snapshot testing, mocking ekstensif, BDD syntax.<br>**tinytest:** Syntax sederhana namun primitif. |
| **Stabilitas & Pemeliharaan**| `Imports` mencegah masking bug.<br>`Depends` memicu tabrakan fungsional antar paket. | **Base R:** Sangat stabil (kompatibilitas mundur terjamin puluhan tahun).<br>**Tidyverse:** Sering terjadi API deprecation lifecycle. | `testthat` merupakan standar de facto industri dan ekosistem CRAN global. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "No Visible Binding for Global Variable" Pitfall
Saat menulis logika transformasi data frame menggunakan `dplyr` atau `data.table` di dalam paket, compiler statis `R CMD check` menandai nama kolom sebagai variabel global tak bertuan:

```r
# SALAH: Memicu NOTE pada R CMD check
clean_data <- function(df) {
  dplyr::filter(df, status == "ACTIVE" & balance > 0)
}
```

*Solusi Defensif*: Gunakan data pronoun `.data` dari pustaka `rlang`:

```r
# BENAR: Lolos analisis statis CRAN tanpa mematikan strict check
#' @importFrom rlang .data
clean_data <- function(df) {
  dplyr::filter(df, .data$status == "ACTIVE" & .data$balance > 0)
}
```

### 2. Platform-Specific Path Separators
Jangan pernah mengasumsikan separator direktori adalah `/` atau `\`:

```r
# SALAH: Berpotensi crash pada arsitektur Windows/Solaris
file_path <- paste0(system.file("extdata", package = "fraudguard"), "/", filename)

# BENAR: Hermetis lintas platform OS
file_path <- file.path(system.file("extdata", package = "fraudguard"), filename)
```

### 3. Namespace S3 Method Registration Leakage
Jika Anda mendefinisikan S3 method untuk generic yang dimiliki oleh paket lain (misalnya method `autoplot` untuk `ggplot2`), mendeklarasikan fungsi sederhana `autoplot.my_class <- function(...)` tanpa mengekspor via `S3method(ggplot2::autoplot, my_class)` pada file `NAMESPACE` akan mengakibatkan method dispatch gagal dieksekusi ketika pengguna tidak sengaja memuat pustaka dengan urutan terbalik.

### 4. Flaky Floating Point Equality dalam Unit Testing
Jangan pernah menggunakan `expect_equal` murni pada perhitungan numerik kompleks tanpa mempertimbangkan representasi IEEE 754:

```r
# SALAH: Rentan gagal antar kompilator C / arsitektur prosesor (x86_64 vs ARM64)
testthat::expect_true((0.1 + 0.2) == 0.3) # Evaluates to FALSE!

# BENAR: Memasukkan toleransi mesin
testthat::expect_equal(0.1 + 0.2, 0.3, tolerance = 1e-8)
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `library()` atau `require()` di Dalam Kode Paket
* **Kesalahan**: Menempatkan sintaks `library(purrr)` di dalam berkas yang berada pada folder `R/`. Tindakan ini akan mengubah search path secara agresif pada mesin pengguna atau memunculkan error fatal saat runtime.
* **Perbaikan**: Hapus semua sintaks `library()`. Daftarkan pustaka pada field `Imports:` di file `DESCRIPTION`, lalu gunakan panggilan namespace eksplisit `purrr::map()` atau deklarasikan `@importFrom purrr map` pada dokumentasi roxygen.

### 2. Mengubah Global State Tanpa Restorasi (`Side Effects Violation`)
* **Kesalahan**: Mengubah opsi global atau direktori kerja via `options()`, `par()`, atau `setwd()` di dalam fungsi paket tanpa mengembalikannya ke state semula.
* **Perbaikan**: Manfaatkan `on.exit()` dari base R atau paket `withr` untuk merestorasi parameter global seketika saat fungsi keluar (*return* atau *error*).

```r
# BENAR: Mutasi environment diproteksi secara lokal
generate_plot <- function(data) {
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old_par), add = TRUE)
  
  graphics::par(mfrow = c(2, 1))
  # Lakukan proses plotting...
}
```

### 3. Hardcoded Dependency Paths pada `renv`
* **Kesalahan**: Menyertakan cache lokal absolut `/home/username/.cache/R/renv` ke dalam Git repository.
* **Perbaikan**: Pastikan berkas `.gitignore` mengabaikan seluruh isi folder `renv/library` dan `renv/python`. Komit **hanya** `renv.lock`, `renv/activate.R`, dan `renv/settings.json`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### Standar Rekayasa Paket Profesional:
1. **Aturan "0-0-0" R CMD Check**: Sebelum merge ke branch `main`, jalankan pengecekan CRAN yang sangat ketat:
   ```r
   devtools::check(args = c("--as-cran", "--no-manual"))
   ```
   Target yang wajib tercapai dalam continuous integration (CI) adalah:
   `Status: 0 ERRORs, 0 WARNINGs, 0 NOTEs`.
2. **Kompilasi Byte-Code**: Pastikan field `ByteCompile: true` terdapat pada file `DESCRIPTION` agar R mengompilasi interpreter AST ke dalam bytecode saat instalasi, meningkatkan latensi eksekusi fungsi secara signifikan.
3. **Dokumentasi Internal vs Publik**:
   * Simbol publik wajib diberi tag `@export` dan dokumentasi `@examples` yang runnable.
   * Simbol internal helper **tidak boleh** diberi `@export`. Gunakan tag `@noRd` jika ingin menulis roxygen block semata-mata untuk referensi developer lain tanpa menghasilkan file `.Rd` publik di direktori `man/`.
4. **Pemisahan Modul R/**: Satu berkas di dalam `R/` idealnya mewakili satu domain logika atau satu class object beserta metode S3 miliknya. Jangan membuat satu berkas masif `all_functions.R` atau sebaliknya membuat file per dua baris helper.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Mengurangi Overhead Panggilan Simbol Namespace
Panggilan berulang dengan operator ganda `::` (misal `base::matrix()`) di dalam loop besar yang dieksekusi jutaan kali memiliki penalti mikro-latensi akibat lookup environment berulang.

```r
# Lambat jika dieksekusi 10^7 kali:
for(i in seq_len(n)) {
  val <- stats::rnorm(1)
}

# Jauh Lebih Cepat: Import simbol secara eksplisit pada NAMESPACE
# via @importFrom stats rnorm
for(i in seq_len(n)) {
  val <- rnorm(1)
}
```

### 2. Menghemat Memori Melalui In-Place Modifications (Alokasi Vektor)
Di dalam kode paket, hindari modifikasi objek bertahap yang memicu salinan memori (copy-on-modify):

```r
# MEMORY LEAK / GC PRESSURE (Kompleksitas O(N^2))
accumulator <- numeric(0)
for (i in 1:100000) {
  accumulator <- c(accumulator, i * 2) # Terjadi relokasi buffer terus-menerus
}

# OPTIMAL & ZERO-OVERHEAD ALLOCATION (Kompleksitas O(N))
accumulator <- numeric(100000) # Memesan kontigu memori sekaligus
for (i in 1:100000) {
  accumulator[i] <- i * 2
}
```

### 3. Profiling Terintegrasi pada Paket
Uji runtime fungsi utama sebelum rilis menggunakan package `bench` di folder `tests/` atau direktori instrumen khusus:

```r
bench::mark(
  pure_base = detect_anomalies(test_df, "id", "amt"),
  iterations = 100,
  check = FALSE
)
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah RCE (Remote Code Execution) dari Formula Parsing
Fungsi `as.formula()` atau `eval(parse(text = ...))` sangat berbahaya jika menerima string mentah dari endpoint atau user eksternal, karena memungkinkan injeksi sistem shell via: `eval(parse(text = "system('rm -rf /')"))`.
* **Hardening**: Jangan pernah memakai `eval(parse())`. Gunakan abstraksi `rlang::parse_expr()` jika terpaksa memanipulasi ekspresi, atau validasi struktur input via enum whitelist.

### 2. Sanitasi Penulisan Berkas Sementara
Jika paket Anda menghasilkan data transien (misalnya *file exporter* atau *cache engine*), jangan menulis sembarangan di direktori kerja root atau `/tmp` global:

```r
# AMAN: Menggunakan isolate temporary directory yang dikelola oleh instance R
safe_temp_dir <- tempfile(pattern = "pkg_sandbox_")
dir.create(safe_temp_dir)
on.exit(unlink(safe_temp_dir, recursive = TRUE), add = TRUE)
```

### 3. Masking Credentials dan Hardcoded Secrets
Jangan pernah memasukkan token otentikasi API atau URI database privat ke dalam kode fungsi di direktori `R/` atau dataset di `data/`. Ambil secrets dari variabel lingkungan sistem (*environment variables*):

```r
get_api_key <- function() {
  key <- Sys.getenv("ENTERPRISE_API_KEY")
  if (identical(key, "")) {
    rlang::abort("Environment variable 'ENTERPRISE_API_KEY' is not configured.",
                 class = "fraudguard_missing_secret")
  }
  key
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Structured Logging di Lingkungan Paket
Hindari menyematkan `print()` atau `cat()` sembarangan ke stdout console pengguna saat eksekusi paket internal. Gunakan sistem structured signaling:

```r
#' @importFrom rlang inform
log_diagnostic <- function(message, verbose = getOption("fraudguard.verbose", FALSE)) {
  if (isTRUE(verbose)) {
    rlang::inform(
      message = paste0("[FRAUDGUARD-CORE] ", Sys.time(), " : ", message),
      class = "fraudguard_diagnostic_message"
    )
  }
}
```

### Debugging Menggunakan Diagnostic Flags
Konsumen atau tim operasional dapat mengaktifkan tracing tanpa memodifikasi kode paket:

```r
# Diaktifkan oleh pengguna secara eksternal:
options(fraudguard.verbose = TRUE)
```

### Mocking Komponen Eksternal dalam Pengujian
Gunakan `testthat::with_mocked_bindings()` untuk menguji respons error jaringan tanpa memerlukan koneksi internet aktif:

```r
testthat::test_that("fetch_remote_rules handles network drops safely", {
  # Mock fungsi download internal agar selalu melempar error
  testthat::with_mocked_bindings(
    fetch_payload = function(...) stop("Network timeout simulation"),
    {
      testthat::expect_error(
        load_remote_risk_matrix("http://api.internal/rules"),
        class = "fraudguard_network_failure"
      )
    }
  )
})
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Command Palette Developer R Package (`devtools` & `usethis`)

| Aksi / Pipeline | Perintah Utama | Dampak Sistem |
| :--- | :--- | :--- |
| **Scaffold Package** | `usethis::create_package("path/to/pkg")` | Menginisialisasi arsitektur direktori fisik. |
| **Regenerate Docs** | `devtools::document()` | Mengeksekusi `roxygen2`, memperbarui `man/*.Rd` dan `NAMESPACE`. |
| **Interactive Test** | `devtools::load_all()` (`Ctrl+Shift+L`) | Mengompilasi dan memuat semua fungsi ke memori lokal tanpa instalasi. |
| **Run Tests** | `devtools::test()` (`Ctrl+Shift+T`) | Menjalankan seluruh test runner di folder `tests/testthat/`. |
| **Strict Audit** | `devtools::check(args = "--as-cran")` | Menjalankan pipa uji statis dan dinamis CRAN. |
| **Lock Dependencies**| `renv::snapshot()` | Mengunci snapshot hash dependensi ke file `renv.lock`. |
| **Restore Isolation**| `renv::restore()` | Menyamakan pustaka fisik lokal dengan `renv.lock`. |

### Template Roxygen2 Header

```r
#' @title Judul Fungsi yang Jelas dan Ringkas
#' @description Penjelasan teknis mengenai fungsi dan algoritma di dalamnya.
#'
#' @param input_name Tipe dan deskripsi data yang diharapkan.
#' @return Struktur kembalian (Class S3, Data Frame, dsb.).
#'
#' @export
#' @importFrom package_name function_name
#' @examples
#' # Kode contoh yang valid dan executable
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman Anda terhadap konsep yang dipelajari.

### Soal Pilihan Ganda (Tingkat Basic)

1. **Di manakah dependensi pustaka harus didaftarkan jika fungsi tersebut hanya digunakan untuk validasi assertions di dalam folder `tests/`?**
   * A. Pada field `Depends:` di `DESCRIPTION`.
   * B. Pada direktif `importFrom` di file `NAMESPACE`.
   * C. Pada field `Suggests:` di `DESCRIPTION`.
   * D. Cukup memanggil `library()` di awal setiap berkas tes.

2. **Perintah apa yang digunakan untuk menghasilkan dokumentasi `.Rd` dari sintaks komentar `#'` secara otomatis?**
   * A. `devtools::check()`
   * B. `devtools::document()`
   * C. `devtools::install()`
   * D. `renv::snapshot()`

3. **Mengapa penggunaan operator assign assignment global `<<-` di dalam fungsi paket sangat dilarang oleh CRAN policy?**
   * A. Karena membuat alokasi CPU meningkat menjadi 100%.
   * B. Karena merusak sifat idempotensi fungsi dan mengontaminasi state environment pengguna.
   * C. Karena R CMD check tidak mendukung sintaks operator panah dobel.
   * D. Karena mematikan sistem S3 Method Dispatch.

4. **Bagaimana cara mengekspos metode S3 `print.my_class` ke sistem luar agar tercatat dengan benar pada `NAMESPACE` melalui roxygen2?**
   * A. Memberikan anotasi `@exportMethod`.
   * B. Memberikan tag `@export` tepat di atas deklarasi fungsi print.
   * C. Menuliskan `@S3method print my_class` di file DESCRIPTION.
   * D. Memasukkan nama fungsinya ke dalam vector `globalVariables()`.

5. **Apa fungsi utama dari berkas `renv.lock` dalam alur kerja rekayasa data?**
   * A. Mempercepat eksekusi interpreter R dengan mengompilasi kode menjadi C++.
   * B. Mengunci daftar dependensi, versi pustaka, dan hash repositori agar lingkungan komputasi deterministik dan dapat direproduksi secara identik.
   * C. Melindungi source code agar tidak dapat diinspeksi oleh pengguna umum.
   * D. Menggantikan peran berkas `DESCRIPTION` pada paket.

---

### Soal Praktikal & Pemecahan Masalah (Tingkat Intermediate)

6. **Saat menjalankan `devtools::check()`, Anda menerima pesan diagnostik berikut:**
   `* checking R code for possible problems ... NOTE`
   `process_transactions: no visible binding for global variable ‘user_id’`
   **Jelaskan akar penyebab masalah ini dan bagaimana cara memperbaikinya secara elegan tanpa mematikan fitur checking!**

7. **Jelaskan perbedaan struktural mendasar antara objek yang dicantumkan pada field `Imports` vs field `Depends` di dalam file `DESCRIPTION` dari perspektif `search()` path!**

8. **Anda memiliki suite pengetesan `testthat`. Salah satu fungsi bergantung pada API eksternal yang lambat dan fluktuatif. Bagaimana arsitektur pengetesan yang benar agar test suite Anda deterministik, cepat, dan tidak bergantung pada status koneksi internet?**

9. **Jika suatu paket mengekspor fungsi yang mendefinisikan S3 generic baru via `UseMethod()`, apa yang wajib disertakan pada berkas implementasi dan dokumentasinya?**

10. **Kapan Anda harus menggunakan snapshot test (`testthat::expect_snapshot()`) dibandingkan equality assertion klasik (`testthat::expect_equal()`)? Berikan skenario penggunaannya!**

---

### Kunci Jawaban & Panduan Evaluasi

1. **C**. Seluruh dependensi yang tidak dipanggil oleh fungsionalitas inti saat paket diinstal oleh konsumen umum (seperti framework pengujian dan tool benchmarking) wajib diletakkan di bawah `Suggests:`.
2. **B**. `devtools::document()` mengeksekusi engine `roxygen2` untuk mem-parsing sintaks komentar metadata dan menyinkronkan file Rd serta `NAMESPACE`.
3. **B**. Fungsi murni (*pure functions*) dalam paket tidak boleh memiliki efek samping (*side effects*) yang memodifikasi state di luar scope lokalnya secara tidak terkontrol. Penggunaan `<<-` berpotensi menimpa variabel milik pengguna di `.GlobalEnv`.
4. **B**. `roxygen2` secara cerdas mengidentifikasi bahwa nama fungsi mematuhi pola `{generic}.{class}` dan secara otomatis mendaftarkannya sebagai `S3method(print, my_class)` di dalam file `NAMESPACE`.
5. **B**. `renv.lock` adalah spesifikasi deklaratif platform yang memetakan snapshot repositori dan dependensi pustaka untuk menjamin portabilitas absolut lintas container atau mesin dev.
6. **Akar Masalah**: Pustaka analisis statis R mendeteksi adanya simbol `user_id` yang tidak dideklarasikan di scope lokal, biasanya akibat pemanggilan Non-Standard Evaluation (NSE) pada ekosistem tidyverse (misal: `dplyr::select(df, user_id)`).
   **Solusi**: Gunakan import pronoun `.data` dari pustaka `rlang` (`dplyr::select(df, .data$user_id)`) atau daftarkan nama variabel via `utils::globalVariables(c("user_id"))` di file terpisah `R/globals.R`. Cara pertama (.data pronoun) lebih direkomendasikan.
7. Objek pada `Depends` akan dimuat (*loaded*) sekaligus ditempelkan (*attached*) langsung ke rantai `search()` global pengguna, meningkatkan risiko name clashing. Sedangkan pustaka pada `Imports` hanya dimuat ke memori (*loaded*) ke dalam namespace lokal paket Anda, tanpa pernah muncul di dalam rantai `search()` pengguna.
8. Gunakan teknik **Mocking**. Manfaatkan fungsi `testthat::with_mocked_bindings()` atau paket `httptest`/`webmockr` untuk memotong interaksi socket HTTP level rendah dan mengembalikan respon payload *mock* statis yang telah ditentukan sebelumnya.
9. Fungsi generic harus mengeksekusi `UseMethod("nama_generic")`, diberi dokumentasi lengkap dengan tag `@export`, dan menyertakan fallback default method seperti `nama_generic.default` untuk menangani tipe data yang tidak dikenali dengan pesan error informatif via `rlang::abort()`.
10. `expect_snapshot()` digunakan ketika Anda menguji output tekstual kompleks, pesan peringatan (*warnings*), pesan error terformat (*error conditions*), atau print output representasi S3/S4 method yang rentan mengalami perubahan tipografi/formatting, di mana memvalidasi string manual via `expect_equal()` akan sangat rapuh (*brittle*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Enterprise Metric Normalizer (`metricforge`)

#### Skenario Penugasan:
Sebagai Staff Engineer, Anda diminta merancang paket R bernama `metricforge` yang akan didistribusikan ke klaster RStudio Server internal di divisi Enterprise Data Analytics. Paket ini bertugas membersihkan, memvalidasi, dan melakukan re-skala (normalisasi) metrik bisnis skala besar dengan performa tinggi dan zero defect.

#### Spesifikasi Fungsional:
1. **Scaffolding Proyek**:
   * Buat paket R baru bernama `metricforge` menggunakan utilitas `usethis`.
   * Konfigurasikan lisensi menggunakan MIT License.
   * Kunci struktur menggunakan `renv` dan pastikan dependensi minimum tercatat.
2. **Implementasi Komputasi (`R/normalize.R`)**:
   * Buat generic S3 `normalize_scores(x, ...)` dan metode spesifik untuk:
     * `numeric`: Normalisasi rentang min-max ke domain $[0, 1]$ atau Z-Score standardization (tergantung argumen enum `method = c("minmax", "zscore")`).
     * `data.frame`: Menormalkan semua kolom numerik secara otomatis sambil mengabaikan kolom non-numerik, mengembalikan tipe dataframe yang sama.
   * Sertakan parameter `na.rm = TRUE`.
   * Lakukan validasi input defensif: Jika standar deviasi dari data bernilai nol atau rentang min-max identik, kembalikan vektor nol dengan class condition warning `metricforge_zero_variance`.
3. **Quality Assurance & Testing Harness (`tests/testthat/`)**:
   * Buat minimal **8 unit tests** yang mencakup:
     * Verifikasi keakuratan matematis dari normalisasi min-max dan z-score.
     * Pengujian penanganan input skalar tunggal atau vektor kosong.
     * Exception assertion saat input non-numerik dioperasikan pada class numeric.
     * Snapshot test untuk output method S3 `print.metricforge_normalized`.
4. **Dokumentasi & Validasi CRAN**:
   * Tuliskan dokumentasi roxygen2 secara lengkap (`@title`, `@description`, `@param`, `@return`, `@export`, `@examples`).
   * Pastikan direktori `man/` dan berkas `NAMESPACE` terkompilasi sempurna via `devtools::document()`.
   * Eksekusi `devtools::check(args = "--as-cran")` dan pastikan hasil akhir menunjukkan:
     **`0 ERRORs | 0 WARNINGs | 0 NOTEs`**.

#### Kriteria Keberhasilan Eksekusi:
* Seluruh test suite lolos (*green*) saat dieksekusi via `devtools::test()`.
* Tidak ada variabel global liar atau dependensi tak terdaftar.
* File `renv.lock` valid dan siap digunakan untuk provisioning environment secara hermetis di sistem CI/CD target.