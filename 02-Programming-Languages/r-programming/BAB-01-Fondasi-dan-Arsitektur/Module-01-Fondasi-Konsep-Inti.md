# Bab 01 Module 01: Arsitektur Eksekusi R, Model Memori, dan Mesin Vektorisasi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis (C4)** arsitektur runtime GNU R, siklus interpretasi *Abstract Syntax Tree* (AST), dan representasi data primitif berbasis struktur C `SEXP` (*S-Expression*).
*   **Mengevaluasi (C5)** semantik mutasi *Copy-on-Modify* menggunakan mekanisme pelacakan referensi memori internal (`tracemem` dan penanda alamat memori).
*   **Mengimplementasikan (C3)** operasi vektorisasi murni (*SIMD-like abstraction*) untuk mengeliminasi overhead *interpreter loop* pada komputasi numerik skala besar.

---

### 2. Konsep Fundamental (Core Concept)
R adalah bahasa pemrograman terinterpretasi dinamis yang dirancang khusus untuk komputasi statistika dan manipulasi data. Secara fundamental, R dibangun di atas interpreter berbasis bahasa C dan Fortran. Semua entitas data dalam R—mulai dari skalar tunggal, vektor, fungsi, hingga *environment*—direpresentasikan dalam struktur C tunggal bernama **`SEXP` (S-Expression pointer)**. 

Tidak seperti bahasa berorientasi objek murni berbasis kelas tunggal (seperti Java), R mengadopsi paradigma fungsional berbasis vektor: **skalar tidak eksis dalam R**. Angka `42` secara internal dialokasikan sebagai vektor numerik dengan panjang 1 (`length = 1`). Operasi data di R bekerja melalui prinsip *vectorized batch dispatch*, memetakan komputasi langsung ke pustaka linier algebra tingkat rendah (BLAS/LAPACK) yang terkompilasi.

---

### 3. Mengapa Konsep Ini Penting (Why / Motivation)
Mayoritas praktisi pemula menulis kode R dengan pola pikir prosedural imperatif (seperti menggunakan loop `for` gaya C/Python). Pendekatan ini menghasilkan performa komputasi yang sangat lambat (*orders of magnitude slower*). 

Penyebab utamanya adalah **interpretasi dinamis overhead** dan **alokasi memori implisit**. Setiap iterasi loop dalam interpreter R mengevaluasi tipe data, memeriksa *method dispatch*, dan memicu alokasi memori baru jika terjadi modifikasi objek di tempat (*in-place modification illusion*). Memahami model memori *Copy-on-Modify* dan mengeksploitasi mesin vektorisasi internal R adalah fondasi wajib sebelum membangun pipeline analitik atau machine learning berkinerja tinggi.

---

### 4. Apa Sebenarnya Konsep Ini (What / Deep-Dive Architecture)
Di balik interpreter R, terdapat tiga pilar arsitektur utama:

1.  **SEXP (S-Expression Data Structure):**
    Setiap objek R berada di tumpukan memori (*heap*) yang dikelola oleh *custom garbage collector* milik R. Struktur C `SEXPREC` membungkus *header* (tipe data/`SEXPTYPE`, atribut, status penandaan GC, dan penghitung referensi) serta payload data aktual.
2.  **Copy-on-Modify (CoM) Semantics:**
    R memberikan ilusi semantik *pass-by-value*. Ketika suatu objek dialokasikan ke variabel baru (`y <- x`), R tidak menduplikasi data di memori; R hanya membuat pointer baru yang merujuk ke blok memori `SEXP` yang sama. Duplikasi fisik (kloning memori) baru dieksekusi secara *lazy* tepat pada saat salah satu variabel tersebut dimutasi nilainya.
3.  **Vectorized Processing Engine:**
    Vektorisasi dalam R bukan sekadar *syntactic sugar*. Pemanggilan fungsi tervektorisasi (`x + y`) melompati lapisan evaluasi interpreter R loop-by-loop dan mengeksekusi loop tingkat rendah pada array C primitif secara berurutan (*contiguous memory access*), memungkinkan pemanfaatan *cache locality* prosesor dan optimasi instruksi SIMD (Single Instruction, Multiple Data).

---

### 5. Cara Kerja (Under-the-Hood / Mechanism)

#### Siklus Eksekusi dan Modifikasi Objek
1.  **Parsing & AST Construction:** Kode R dikonversi dari string menjadi pohon sintaksis ekspresi R (`pairlist` atau `language object`).
2.  **Evaluasi Lingkungan (*Environment Evaluation*):** Interpreter mengevaluasi simbol dalam *lexical scope* saat ini.
3.  **Pemeriksaan Reference Count (Refcnt):**
    *   Jika objek memiliki `refcnt == 1`, mutasi dapat dilakukan langsung di tempat (*modify-in-place*), bergantung pada apakah objek memiliki atribut terproteksi.
    *   Jika objek memiliki `refcnt > 1`, interpreter R menduplikasi seluruh payload array ke alamat memori baru sebelum mengaplikasikan modifikasi, lalu menurunkan refcnt objek lama dan mengarahkan simbol pemanggil ke alamat baru.
4.  **Vector Recycling Rule:** Jika dua vektor dengan panjang berbeda dioperasikan bersama, R secara otomatis mereplikasi elemen-elemen dari vektor yang lebih pendek hingga panjangnya setara dengan vektor yang lebih panjang. Jika panjang vektor yang lebih panjang bukan merupakan kelipatan eksak dari panjang vektor pendek, *runtime* memunculkan peringatan (*warning*), namun eksekusi tetap dilanjutkan.

---

### 6. Diagram Alur Kerja (ASCII Diagram)

```text
ALOKASI DAN MUTASI MEMORI (COPY-ON-MODIFY)

Keadaan Awal:
+-------------+
| Variabel: x | -------> [ SEXP SXPINFO ]
+-------------+          [ Data: 1, 2, 3 ] (Alamat: 0x001A, REFCNT: 1)

Operasi Bind: y <- x
+-------------+
| Variabel: x | -------\
+-------------+         +-> [ SEXP SXPINFO ]
| Variabel: y | -------/    [ Data: 1, 2, 3 ] (Alamat: 0x001A, REFCNT: 2)
+-------------+

Mutasi: y[1] <- 99L (Copy-on-Modify Triggered)
+-------------+
| Variabel: x | -----------> [ SEXP SXPINFO ]
+-------------+              [ Data: 1, 2, 3 ]  (Alamat: 0x001A, REFCNT: 1)
                             
+-------------+              [ DUPLIKASI + MUTASI ]
| Variabel: y | -----------> [ SEXP SXPINFO ]
+-------------+              [ Data: 99, 2, 3 ] (Alamat: 0x009F, REFCNT: 1)
```

---

### 7. Contoh Kode Sederhana (Minimal Reproducible Example)

Contoh ini menunjukkan verifikasi semantik *Copy-on-Modify* menggunakan fungsi diagnostik internal R.

```R
# Mematikan kompilasi JIT sementara untuk inspeksi deterministik
compiler::enableJIT(0)

# 1. Alokasi Vektor Awal
x <- c(10L, 20L, 30L, 40L)

# Aktifkan pelacakan memori eksplisit
cat("Status tracemem awal:\n")
tracemem(x)

# 2. Binding Objek Baru (Shared Memory Reference)
y <- x

# Periksa alamat dasar memori via base::tracemem
# Kedua variabel merujuk pada alamat yang sama tanpa alokasi baru
cat("\nMemodifikasi elemen y...\n")

# 3. Trigger Copy-on-Modify
y[2] <- 999L

# Validasi nilai
cat("\nIsi x:", paste(x, collapse = ", "), "\n")
cat("Isi y:", paste(y, collapse = ", "), "\n")

# Hentikan pelacakan
untracemem(x)
```

---

### 8. Breakdown Kode Sederhana
*   `compiler::enableJIT(0)`: Menonaktifkan *Just-In-Time Compiler* internal R agar tahapan bytecode compiler tidak mengaburkan penelusuran alokasi memori primitif.
*   `x <- c(10L, 20L, 30L, 40L)`: Mengalokasikan vektor bertipe integer (`INTSXP`) dengan panjang 4. Sufiks `L` memaksa penyimpanan sebagai 32-bit integer, menghindari alokasi default 64-bit floating point (`REALSXP`).
*   `tracemem(x)`: Menandai objek `SEXP` pada tingkat C engine untuk mencetak output ke stdout setiap kali payload memori fisik objek diduplikasi.
*   `y <- x`: Tidak ada duplikasi memori. Alamat memori `y` identik dengan `x`.
*   `y[2] <- 999L`: Karena referensi `x` dan `y` menunjuk ke alamat yang sama, R mendeteksi potensi konflik referensi ganda. Interpreter mengalokasikan blok memori baru, menyalin seluruh data dari `x`, mengubah indeks ke-2 menjadi 999, dan mencetak pesan: `tracemem[0x... -> 0x...]:`.

---

### 9. Contoh Kasus Nyata / Praktis (Realistic Implementation)

Kasus: Pemrosesan Normalisasi Sinyal Sensor Geospasial (10 juta titik data). Membandingkan pola naif (pertumbuhan dinamis dan modifikasi serial) dengan arsitektur vektorisasi berbasis alokasi *pre-allocated contiguous memory*.

```R
# Generator Dataset Skala Menengah (10 Juta Elemen)
generate_sensor_stream <- function(n_points) {
  set.seed(42)
  return(runif(n_points, min = -100.0, max = 500.0))
}

# Pendekatan Naif: Pertumbuhan Objek Dinamis (Anti-Pattern Mutasi Memori)
process_naive <- function(raw_data) {
  # Mengambil sampel kecil karena algoritma O(N^2) memori tidak feasible untuk 10jt
  sample_data <- raw_data[1:10000]
  processed <- numeric(0) # Inisialisasi vektor nol
  
  for (i in seq_along(sample_data)) {
    # Memicu alokasi ulang memori di setiap iterasi loop (Copy-on-Modify terus menerus)
    if (sample_data[i] > 0) {
      processed <- c(processed, log(sample_data[i]))
    } else {
      processed <- c(processed, 0.0)
    }
  }
  return(processed)
}

# Pendekatan Produksi: Vektorisasi Penuh (Zero-Copy Interpreter Loops)
process_vectorized <- function(raw_data) {
  # 1. Alokasi mask berbasis boolean vectorization (pustaka internal C)
  positive_mask <- raw_data > 0.0
  
  # 2. Pre-allocation vektor hasil (menghindari duplikasi dinamis)
  result <- numeric(length(raw_data))
  
  # 3. Vectorized subset replacement (Instruksi terpusat)
  result[positive_mask] <- log(raw_data[positive_mask])
  
  return(result)
}

# Eksekusi Pemrosesan Skala Penuh
n_records <- 1e7
cat("Generating", n_records, "records...\n")
sensor_data <- generate_sensor_stream(n_records)

cat("Mengeksekusi pipeline vektorisasi...\n")
start_time <- proc.time()
processed_data <- process_vectorized(sensor_data)
execution_time <- proc.time() - start_time

cat(sprintf("Selesai dalam: %.3f detik.\n", execution_time[["elapsed"]]))
cat(sprintf("Penggunaan memori objek akhir: %.2f MB\n", 
            object.size(processed_data) / (1024^2)))
```

---

### 10. Bedah Arsitektur Kasus Praktis
Pada `process_vectorized`:
1.  Operasi `raw_data > 0.0` dieksekusi melalui C primitive function `.Primitive(">")`. Loop dilakukan pada *contiguous memory array* `REALSXP` di level C, menghasilkan vektor logika (`LGLSXP`).
2.  `numeric(length(raw_data))` memanggil alokasi memori tunggal via `allocVector(REALSXP, n)` di heap R. Tidak ada fragmentasi memori.
3.  Ekspresi `result[positive_mask] <- log(raw_data[positive_mask])`:
    *   `log(...)` memanggil fungsi internal C berkecepatan tinggi yang mendukung instruksi streaming.
    *   Penggantian subset dilakukan melalui penulisan langsung ke slot memori yang telah dialokasikan tanpa mereplikasi struktur secara keseluruhan berulang kali.

---

### 11. Potensi Jebakan & Anti-Patterns (Common Pitfalls & Edge Cases)

*   **Pola Pertumbuhan Vektor Dinamis (`c() in loop`):**
    ```R
    # ANTI-PATTERN
    vec <- c()
    for (i in 1:n) {
      vec <- c(vec, i) # Alokasi O(n^2), memori terus menerus di-kloning dan dibuang
    }
    ```
*   **Vector Recycling yang Tidak Diinginkan:**
    ```R
    x <- c(1, 2, 3, 4, 5)
    y <- c(10, 20)
    z <- x + y
    # Hasil: c(11, 22, 13, 24, 15) disertai Warning.
    # Jika panjang x adalah kelipatan pasti y (misal len=6), TIDAK ADA WARNING sama sekali.
    # Hal ini sering menjadi sumber bug fatal dalam pipeline finansial/matematis.
    ```
*   **Kehilangan Tipe Data Primitif (*Type Coercion Hell*):**
    Menyimpan satu elemen string ke dalam vektor numerik akan mengubah *seluruh* elemen vektor menjadi string (`STRSXP`), memicu overhead memori 8x lebih besar dan hilangnya kompatibilitas operasi matematika.

---

### 12. Analisis Trade-offs

| Dimensi | Pendekatan Serial (Iteratif Loop) | Pendekatan Vektorisasi R Murni | Operasi Matriks / C++ Bindings (Rcpp) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Waktu** | $O(N)$ di atas kertas, namun sering menjadi $O(N^2)$ akibat alokasi memori | $O(N)$ riil, dieksekusi pada loop internal terkompilasi | $O(N)$ atau $O(N/K)$ dengan optimasi multithreading (OpenMP/SIMD) |
| **Kompleksitas Memori** | Tinggi (banyak relik alokasi memori yang memicu agresi GC) | Rendah hingga Sedang (tergantung pembuatan vektor *mask* temporer) | Minimum (kontrol alokasi memori langsung pada raw pointer) |
| **Maintainability** | Mudah dibaca oleh programmer dari latar belakang C/Java | Sangat ringkas, idomatis untuk ekosistem R | Memerlukan rantai *toolchain* kompilator C++ (Rtools/GCC) |
| **Latensi Eksekusi** | Buruk (overhead pemanggilan evaluator R per iterasi) | Sangat Rendah untuk transformasi elemen umum | Terendah untuk pemrosesan stateful kompleks |

---

### 13. Benchmark & Karakteristik Performa

Pengujian dilakukan menggunakan package `bench` untuk mengevaluasi alokasi memori riil dan waktu eksekusi:

```R
library(bench)

run_benchmark <- function(n) {
  data <- runif(n)
  
  bench::mark(
    loop_with_preallocation = {
      res <- numeric(n)
      for(i in seq_len(n)) {
        res[i] <- data[i] * 2
      }
      res
    },
    vectorized = {
      data * 2
    },
    iterations = 10,
    check = TRUE
  )
}

# Eksekusi untuk 1.000.000 elemen
benchmark_results <- run_benchmark(1e6)
print(benchmark_results[, c("expression", "min", "median", "mem_alloc", "n_gc")])
```

#### Karakteristik Performa Tipikal:
*   **Vectorized:** Eksekusi $\approx$ 1-3 milidetik, konsumsi alokasi memori: $\approx$ 7.63 MB (alokasi tunggal untuk vektor hasil), $0$ Garbage Collection cycles.
*   **Loop with Preallocation:** Eksekusi $\approx$ 60-100 milidetik (30x hingga 50x lebih lambat), alokasi memori: $\approx$ 7.63 MB, membebani R runtime loop call stack.
*   **Loop dynamically growing (`c()`):** Eksekusi *abysmal* (menit), jutaan alokasi temporer, memicu ratusan siklus Garbage Collection.

---

### 14. Komparasi Solusi / Pendekatan Alternatif
Untuk permasalahan manipulasi data tabular besar, terdapat beberapa paradigma utama:

1.  **Base R Vectorization:** Menggunakan `.Primitive` dan fungsi built-in (`ifelse`, vektor logika).
    *   *Kelebihan:* Dependensi nol (zero external dependency), stabil.
    *   *Kekurangan:* Menghasilkan banyak objek vektor temporer per operasi intermediate.
2.  **`data.table` Internal In-Place Modification (`:=`):**
    *   *Mekanisme:* Melanggar aturan umum *Copy-on-Modify* dengan mengimplementasikan modifikasi memori langsung (*in-place assignment*) via C pointers.
    *   *Kelebihan:* Nol duplikasi memori, efisiensi skala Terabyte.
3.  **`Rcpp` (C++ Integration):**
    *   *Mekanisme:* Membungkus pointer `SEXP` ke dalam kelas C++ (`NumericVector`) dan mengeksekusi loop murni terkompilasi.
    *   *Kelebihan:* Solusi mutlak untuk algoritma stateful / sekuensial rekursif yang tidak dapat divektorisasi secara matematis.

---

### 15. Praktik Terbaik Industri (Production Best Practices)
*   **Pra-alokasi Seluruh Vektor:** Jangan pernah memanggil `c()`, `append()`, `cbind()`, atau `rbind()` di dalam badan iterasi. Selalu gunakan `vector(mode, length)` atau `numeric(n)` sebelum loop.
*   **Gunakan Fungsi Primitif `seq_along()` / `seq_len()`:** Hindari `1:length(x)` karena jika `length(x) == 0`, loop akan mengevaluasi vektor indeks mundur `c(1, 0)`, menghasilkan bug *index-out-of-bounds*.
*   **Eksploitasi Tipe Integer Primitif:** Selalu gunakan sufiks `L` (misal: `1L`, `100L`) untuk data identifikasi, indeks, atau pencacah guna memangkas konsumsi RAM sebesar 50% dibandingkan alokasi default floating-point `numeric` (4 byte vs 8 byte per elemen).
*   **Hapus Objek Memori Raksasa Eksplisit:** Panggil `rm(objek_besar)` diikuti penanganan garbage collection deterministik `gc(verbose = FALSE)` saat memproses batch data pipeline di server berkapasitas RAM terbatas.

---

### 16. Panduan Security & Robustness

*   **Handling `NA`, `NaN`, dan `Inf` dalam Vectorized Logic:**
    Operasi vektorisasi logis sering menghasilkan nilai `NA`. Jika kondisi `if (NA)` dievaluasi pada kontrol alur serial, R melempar error fatal: `missing value where TRUE/FALSE needed`. Pastikan input divalidasi menggunakan `is.finite()` atau gunakan subsetting tervektorisasi:
    ```R
    # Penanganan Robust
    clean_data <- raw_data[!is.na(raw_data) & !is.infinite(raw_data)]
    ```
*   **Ambiguity In Vector Recycling:**
    Mencegah bug fatal pada pergeseran dataset:
    ```R
    safe_vector_add <- function(a, b) {
      if (length(a) != length(b)) {
        stop(sprintf(
          "Security Assertion Failure: Penjang vektor tidak kompatibel. Arg 1: %d, Arg 2: %d", 
          length(a), length(b)
        ))
      }
      return(a + b)
    }
    ```

---

### 17. Verifikasi & Pengujian Kode (Unit Testing)

Implementasi pengujian menggunakan framework `testthat` (Standar Industri R):

```R
library(testthat)

# Definisi Logika
vectorized_scale <- function(x, center, scale) {
  if (!is.numeric(x) || !is.numeric(center) || !is.numeric(scale)) {
    stop("Input harus berupa vektor numerik.")
  }
  if (scale == 0) {
    stop("Scale factor tidak boleh nol.")
  }
  return((x - center) / scale)
}

# Test Suite
test_that("vectorized_scale memproses kalkulasi dengan benar dan mematuhi batas invariant", {
  # Uji Fungsionalitas Dasar
  input_data <- c(10, 20, 30)
  res <- vectorized_scale(input_data, 10, 2)
  expect_equal(res, c(0, 5, 10))
  
  # Uji Immutability (Input Asli Tidak Berubah)
  expect_equal(input_data, c(10, 20, 30))
  
  # Uji Handling Exception
  expect_error(vectorized_scale(input_data, 10, 0), "Scale factor tidak boleh nol.")
  expect_error(vectorized_scale("invalid", 1, 1), "Input harus berupa vektor numerik.")
})
```

---

### 18. Troubleshooting Guide (FAQ Masalah Nyata)

*   **Gejala:** R session tiba-tiba *crashed* dengan pesan `vector memory exhausted (limit reached?)`.
    *   **Akar Masalah:** Mencapai batas alokasi RAM per sesi (biasanya pada lingkungan R 32-bit atau batas environment RStudio). Alternatif lain: terjadi *Copy-on-Modify chain explosion* di mana objek berganda terduplikasi secara implisit.
    *   **Solusi:** Periksa pointer memori menggunakan `tracemem()`. Naikkan limit lingkungan melalui `.Renviron` dengan mengatur parameter `R_MAX_VSIZE=32Gb` atau alihkan representasi data ke *memory-mapped files* (`bigstatsr` / `arrow`).
*   **Gejala:** Hasil komputasi vektorisasi menghasilkan tipe data karakter tanpa error.
    *   **Akar Masalah:** Terjadi *Implicit Coercion* akibat data frame atau vektor mengandung satu nilai string (misal: `"NULL"` alih-alih `NA`).
    *   **Solusi:** Lakukan assertion tipe data secara deterministik menggunakan `stopifnot(is.numeric(vec))` sebelum mengeksekusi operasi.

---

### 19. Latihan Mandiri Bertingkat (Challenge Labs)

#### Kasus 1: Dasar (Fungsi Deteksi Copy-on-Modify)
Tulis fungsi R yang menerima sembarang objek vektor, melakukan mutasi nilai pada indeks pertama, dan mengembalikan `TRUE` jika objek tersebut memicu salinan memori baru, atau `FALSE` jika mutasi terjadi *in-place*. 
*Hint:* Gunakan pemeriksaan alamat memori atau fungsionalitas dari package dasar.

#### Kasus 2: Menengah (Implementasi Rolling Mean Vektorized Murni)
Bangun fungsi `rolling_mean(x, k)` di mana `x` adalah vektor numerik dan `k` adalah ukuran jendela (*window size*). Anda **dilarang keras** menggunakan loop `for`, `while`, `repeat`, maupun fungsi dari package pihak ketiga.
*Hint:* Gunakan fungsi kalkulasi `cumsum()` dan kalkulasikan selisih batas interval berbasis penggeseran indeks (*lag slicing*).

#### Kasus 3: Lanjut (Sistem Operasi Matriks Sparsitas Berbasis Native C SEXP)
Buat representasi sparse matrix sederhana dalam basis R menggunakan 3 vektor koordinat: `i` (row index), `j` (column index), `v` (numeric value). Implementasikan operasi perkalian skalar tervektorisasi yang mengoptimalkan alokasi memori sedemikian rupa sehingga elemen bernilai nol tidak pernah dialokasikan dalam memori heap. Validasi konsumsi memori menggunakan package `bench` terhadap matriks padat biasa berukuran $10.000 \times 10.000$ (yang 99%-nya bernilai 0).

---

### 20. Rangkuman Inti & Jembatan ke Modul Berikutnya

*   **R Engine Core:** Tidak ada tipe skalar di R. Seluruh data adalah vektor berbasis struktur internal C `SEXP`.
*   **Copy-on-Modify:** Modifikasi variabel bersifat *lazy*; alokasi duplikasi fisik memori di heap hanya terjadi ketika ada lebih dari satu simbol yang merujuk pada `SEXP` yang sama dan salah satunya dimutasi.
*   **Loop vs Vektorisasi:** Loop prosedural di R membawa overhead interpretasi yang masif. Vektorisasi memotong lapisan interpreter R, mendelegasikan iterasi langsung ke kompilasi internal C/Fortran dengan akses memori contiguous.

**Jembatan ke Modul 02:**
Sekarang setelah Anda memahami bagaimana R mengelola memori dan mengeksekusi vektor primitif, kita siap melangkah ke **Bab 01 Module 02: Representasi Struktur Data Intrinsic (Atomic Vectors, Matrices, Lists, dan Data Frames)**. Pada modul selanjutnya, kita akan membedah bagaimana objek heterogen seperti `list` dikelola di heap memori via pointers array, serta implikasi performanya terhadap manipulasi tabular dataset berskala produksi.