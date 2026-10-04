# BAB 09: Quiz, Challenge, & Knowledge Check
**Package Development, Reproducibility, & Testing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dekoupling Metadata vs Namespace Isolation:**  
   Jelaskan perbedaan mendasar antara direktif `Imports` pada berkas `DESCRIPTION` dan direktif `import()` / `importFrom()` pada berkas `NAMESPACE`. Mengapa mencantumkan dependensi di `DESCRIPTION` saja tidak cukup untuk menjamin resolusi simbol yang aman dalam *runtime execution* sebuah package?
2. **Reproducibility Mechanics via Content-Addressable Storage:**  
   Bagaimana arsitektur `renv` mengisolasi dependensi antar-proyek tanpa menduplikasi instalasi biner fisik di setiap direktori repositori? Jelaskan mekanisme *symlink* atau *hard link* ke *global package cache* serta kondisi di mana isolasi ini dapat terkompromi (misalnya perbedaan OS kernel atau arsitektur CPU).
3. **Semantik Dependensi R: `Depends` vs `Imports` vs `Suggests`:**  
   Uraikan dampak teknis dari penempatan sebuah pustaka eksternal ke dalam `Depends` dibandingkan dengan `Imports`. Kapan sebuah pustaka **wajib** diletakkan di bawah `Suggests`, dan bagaimana pola defensif (*defensive pattern*) yang harus ditulis di dalam fungsi untuk menangani pustaka yang berada di `Suggests`?
4. **Lifecycle & State Initialization: `.onLoad()` vs `.onAttach()`:**  
   Dalam siklus hidup pemuatan paket R, bedakan *execution context* antara fungsi `.onLoad(libname, pkgname)` dan `.onAttach(libname, pkgname)`. Mengapa registrasi method C/C++ (*dynamic symbols*), inisialisasi koneksi database, atau kompilasi Java Virtual Machine (rJava) harus dilakukan pada `.onLoad()` dan bukan pada `.onAttach()`?
5. **Deterministic vs Non-Deterministic Testing pada `testthat`:**  
   Jelaskan risiko penggunaan *snapshot testing* (`testthat::expect_snapshot()`) pada unit test yang memvalidasi representasi teks atau data frame jika package dijalankan di platform lintas-OS (Windows, macOS, Linux). Parameter internal apa (seperti *locale*, *timezone*, dan opsi pencetakan *floating-point*) yang dapat memicu *false negative*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mitigasi NSE (Non-Standard Evaluation) pada `R CMD check`:**  
   Ketika mengompilasi kode berbasis `tidyverse` (seperti `dplyr::mutate(df, total = price * qty)`) di dalam sebuah package, `R CMD check` secara default akan mengeluarkan *NOTE*: `no visible binding for global variable 'price', 'qty'`. Analisis penyebab teknis dari *static analysis warning* ini dan bandingkan dua strategi penyelesaiannya: penggunaan variabel penampung `utils::globalVariables()` versus *data pronoun* `.data$price` dari `rlang`.
2. **Debugging Native Code Compilation & Memory Leaks via Valgrind:**  
   Sebuah package yang mengintegrasikan C++ melalui `Rcpp` lolos uji coba `devtools::test()`, namun mengalami *SIGSEGV (Segmentation Fault)* acak saat dieksekusi dalam worker berbeban tinggi via `parallel::mclapply()`. Bagaimana Anda mereproduksi dan mengisolasi masalah alokasi memori ini menggunakan `R CMD check --use-valgrind`, dan apa saja batasan eksekusi Valgrind terhadap *thread pooling* di R?
3. **Mocking State Tanpa Test Pollution:**  
   Dalam pengujian fungsi yang berinteraksi dengan API eksternal (misalnya fungsi fetching HTTP via `httr2`), Anda menggunakan `testthat::local_mocked_bindings()` atau paket `mockery`. Jelaskan bagaimana *lexical scoping* dan *environment manipulation* di R memungkinkan substitusi fungsi internal paket lain secara lokal, serta bagaimana memastikan *mock state* tersebut otomatis dibersihkan (*reverted*) tanpa mencemari pengujian di unit test berikutnya.
4. **BLAS/LAPACK Divergence dan Floating-Point Non-Determinism:**  
   Dua mesin CI/CD yang berbeda (satu menggunakan Intel MKL di Ubuntu x86_64, satu lagi menggunakan OpenBLAS di Linux aarch64) menghasilkan hash output yang berbeda untuk model matrix factorization yang sama, meskipun `set.seed(42)` telah diatur. Identifikasi akar penyebab arsitektural dari divergensi numerik ini dan bagaimana menyusun kriteria toleransi numerik (`tolerance`) pada pengujian unit aljabar linear.
5. **Divergensi Dynamic Symbol Registration:**  
   Apa implikasi keamanan dan performa dari menyertakan file `src/init.c` dengan `R_registerRoutines()` dan `R_useDynamicSymbols(dll, FALSE)` dibandingkan membiarkan R menyelesaikan resolusi simbol C/C++ secara dinamis pada saat *runtime*? Mengapa CRAN mewajibkan *strict symbol registration*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kegagalan Pipeline CI/CD Akibat "Ghost" Dependencies dan Strict Checks
Pipeline CI/CD enterprise Anda yang mengeksekusi `R CMD check --as-cran` tiba-tiba gagal secara masif setelah seorang engineer menggabungkan *pull request* fitur pelaporan baru. Error log menunjukkan:
```text
* checking package dependencies ... ERROR
Namespace dependency not required: ‘readxl’
* checking R code for possible problems ... NOTE
generate_report: no visible global function definition for ‘read_excel’
* checking compiled code ... OK
Status: 1 ERROR, 1 NOTE
```
Developer bersikeras bahwa kode berjalan lancar di komputer lokalnya melalui `devtools::load_all()` dan pengujian lokal sukses 100%.
* **Pertanyaan Diagnostik:**
  1. Mengapa `devtools::load_all()` menyembunyikan defisiensi deklarasi dependensi ini di mesin lokal developer, sedangkan `R CMD check` pada container CI/CD menangkapnya sebagai *ERROR* fatal?
  2. Langkah-langkah refactoring dan git pre-commit hook apa yang harus diterapkan pada `DESCRIPTION` dan `NAMESPACE` untuk mengotomatisasi pendeteksian kegagalan deklarasi ini sebelum kode masuk ke *remote branch*?

### Skenario B: Broken Lockfile & Compiler Incompatibility pada Multi-Architecture Fleet
Tim Data Science Anda memperbarui model inferensi dengan menaikkan versi package `arrow` dan `torch` di dalam lockfile `renv.lock`. Ketika image Docker dideploy ke cluster produksi Kubernetes yang menggunakan kombinasi node arsitektur Intel Xeon (x86_64) dan AWS Graviton3 (ARM64), seluruh pod pada node ARM64 masuk ke dalam status `CrashLoopBackOff`. Log container ARM64 mencatat kegagalan kompilasi dependensi C++ native saat eksekusi `renv::restore()`, sedangkan pod di x86_64 berjalan normal.
* **Pertanyaan Diagnostik:**
  1. Mengapa `renv::restore()` mencoba mengompilasi dari *source code* pada container ARM64 sementara pada node x86_64 ia mengunduh *pre-compiled binary*, dan bagaimana manajemen repository internal (seperti Posit Package Manager/P3M) menangani perbedaan arsitektur ini?
  2. Rancang arsitektur deployment image yang sepenuhnya deterministik (bebas dari overhead kompilasi *on-boot* pada pod) untuk armada *multi-architecture* tersebut.

### Skenario C: Circular Dependency dan Degradasi Performa Monolit Internal
Organisasi Anda memiliki satu package inti internal bernama `enterpriseR` yang berisi ratusan fungsi: koneksi database, visualisasi ggplot, transformasi data, algoritma kuantitatif, hingga integrasi internal auth. Seiring bertambahnya tim, waktu kompilasi package memakan waktu 40 menit, unit testing berjalan sangat lambat, dan pembaruan pada modul plotting sering kali mematahkan fungsi perhitungan risiko kuantitatif akibat konflik versi dependensi transitif.
* **Pertanyaan Diagnostik:**
  1. Bagaimana strategi dekomposisi monolit package `enterpriseR` menjadi ekosistem modular (misal: *micro-packages*) tanpa menimbulkan *circular dependency* antar paket?
  2. Bagaimana mendesain mekanisme versioning dan distribusi internal (melalui MiniCRAN, Posit Package Manager, atau GitHub/GitLab Enterprise releases) agar tim downstream dapat mengunci versi dependensi mereka secara independen tanpa memutus interoperabilitas?

---

## 4. Chapter Challenge

**Tantangan Praktis: Enterprise-Grade R Package Core dengan Native Integration & Robust Test Harness**

### Problem Statement
Anda ditugaskan merancang paket R skala produksi bernama **`fastrisk`**. Paket ini bertugas menghitung metrik *Value at Risk* (VaR) historis dan *Parametric VaR* pada portfolio aset skala jutaan observasi menggunakan komputasi C++ (`Rcpp`), dengan audit integrasi dependensi yang ketat, isolasi lingkungan via `renv`, dan pengujian berbasis CI yang wajib lolos `R CMD check` dengan status **0 Errors, 0 Warnings, 0 Notes**.

### Requirements:
1. **Package Skeleton & Metadata:**
   * Inisialisasi struktur package R standar menggunakan `usethis` atau secara programatik.
   * Konfigurasi `DESCRIPTION` secara ketat: Penulis, Lisensi MIT/Apache-2.0, deklarasi `Encoding: UTF-8`, dependensi `R (>= 4.2.0)`, serta `Imports` dan `Suggests` yang presisi.
   * `NAMESPACE` harus sepenuhnya dihasilkan secara otomatis via `roxygen2` tags (larang pengeditan manual).
2. **Algoritma Komputasi (R & Rcpp):**
   * Buat fungsi Rcpp `cpp_var_pnl(NumericVector pnl, double alpha)` yang menghitung persentil empiris kerugian secara optimal menggunakan algoritma partisi cepat di C++. Daftarkan simbol C++ secara eksplisit dengan atribut `.registration = TRUE`.
   * Buat wrapper R `calculate_var(data, alpha = 0.05, method = c("historical", "parametric"))` dengan validasi parameter yang ketat (*fail-fast assertion*).
   * Gunakan non-standard evaluation atau syntax modern (seperti `rlang::check_installed()`) secara higienis tanpa menimbulkan *variable binding note*.
3. **Test Suite & Mocking:**
   * Tulis minimal 5 unit tests menggunakan framework `testthat` (edisi 3):
     - Pengujian edge cases: vektor PnL berisi `NA`, matriks/vektor kosong, nilai `alpha <= 0` atau `>= 1`.
     - Pengujian numerik presisi: verifikasi hasil `fastrisk` terhadap `stats::quantile()` dengan toleransi ketat (`1e-8`).
     - Pengujian snapshot untuk validasi pesan error dan warning.
4. **Reproducibility Layer:**
   * Inisialisasi `renv` dalam package root, pasang dependensi pengembangan (`testthat`, `roxygen2`, `Rcpp`), dan rekam state dalam `renv.lock`.

### Constraints:
* Wajib bersih dari `R CMD check --as-cran` (Status: `0 ERROR, 0 WARNING, 0 NOTE`).
* Tidak boleh menyisakan file artefak lokal atau temporary di folder root package (gunakan `.Rbuildignore` dengan tepat).
* Dilarang menggunakan fungsi berbasis *side-effect* seperti `options()`, `setwd()`, atau `par()` tanpa pembersihan otomatis menggunakan `on.exit()` atau `withr::defer()`.

### Expected Output:
Sebuah repositori/direktori package fungsional dengan struktur direktori lengkap:
```text
fastrisk/
├── .Rbuildignore
├── DESCRIPTION
├── NAMESPACE
├── R/
│   ├── calculate_var.R
│   └── fastrisk-package.R
├── src/
│   ├── RcppExports.cpp
│   ├── init.c (atau auto-generated via roxygen2 Rcpp)
│   └── var_calc.cpp
├── tests/
│   ├── testthat/
│   │   ├── test-calculate_var.R
│   │   └── _snaps/
│   └── testthat.R
└── renv.lock
```
Sertakan cuplikan instruksi baris perintah (CLI) untuk memicu testing, kompilasi dokumentasi, dan eksekusi audit paket.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal dan perbedaan fungsional antara `DESCRIPTION` dan `NAMESPACE`.
- [ ] Siklus hidup pemuatan paket R: mekanika internal `.onLoad()`, `.onAttach()`, dan `.onUnload()`.
- [ ] Konsep *Evaluation Environments* pada R dan mengapa `R CMD check` memicu issue *global variable binding* pada kode yang menggunakan NSE.
- [ ] Mekanisme kerja `renv` (Symlink, Cache, Content Hash, lockfile structure, serta restorasinya).
- [ ] Perbedaan eksekusi antara *in-memory testing* via `devtools::load_all()` dan *clean-room testing* via `R CMD check`.
- [ ] Aturan ketat *Dynamic Symbol Registration* untuk integrasi C/C++ via native API R.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag command-line `R CMD check` (cukup pahami fungsi flag utama seperti `--as-cran`, `--no-manual`, `--use-valgrind`).
- [ ] Sintaksis exact tag boilerplate `roxygen2` untuk setiap tipe objek S4/R6 (dapat merujuk pada manual dokumentasi roxygen2).
- [ ] Struktur JSON internal dari berkas `renv.lock` secara manual (dikelola penuh oleh fungsi `renv::snapshot()` dan `renv::restore()`).

### Saya harus bisa melakukan:
- [ ] Menginisialisasi dan menyusun paket R terstruktur dengan integrasi native code (`Rcpp`) dari awal.
- [ ] Menulis dokumentasi inline lengkap menggunakan `roxygen2` serta mengompilasinya menjadi file `NAMESPACE` dan dokumentasi `.Rd`.
- [ ] Mengisolasi dependensi proyek secara reproducible menggunakan `renv` lintas platform sistem operasi.
- [ ] Menulis unit test komprehensif berbasis `testthat` (Edisi 3) yang menangani edge-cases numerik, validasi error, dan snapshot testing.
- [ ] Mengidentifikasi, mengisolasi, dan merekayasa perbaikan pada isu-isu *NOTE*, *WARNING*, dan *ERROR* saat menjalankan audit `R CMD check --as-cran`.
- [ ] Menerapkan *mocking* dependensi fungsi eksternal/API tanpa menyebabkan kebocoran state (*state leakage*) antar skenario pengujian.