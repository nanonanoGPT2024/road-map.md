# Kurikulum Engineering: R Programming Enterprise Architecture

Selamat datang di repositori kurikulum resmi **R Programming**. Silabus ini dirancang dari perspektif *Senior Technical Curriculum Architect* untuk mentransformasikan praktisi data dari sekadar pengguna skrip ad-hoc menjadi arsitek sistem analitik data modern, komputasi statistik berperforma tinggi, dan rekayasa paket produksi kelas industri.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Bahasa pemrograman R sering disalahpahami sebagai sekadar kakas statistik akademis berkinerja lambat. Dalam realitas rekayasa data dan biostatistik perusahaan modern, R adalah lingkungan komputasi fungsional tingkat tinggi yang sangat teroptimasi (*functional vector-oriented language*). R menggabungkan abstraksi matematika abstrak dengan mesin *low-level* berbasis C dan Fortran.

Pendekatan kurikulum ini berakar pada tiga pilar utama:
1. **Mental Model Komputasi Ter-vektorisasi (Vectorized Thinking):** Mengeliminasi paradigma imperatif prosedural (*explicit for-loops*) dan beralih ke komputasi berbasis vektor atomik, operasi matriks, dan *functional mapping* yang dieksekusi pada level memori contiguous C.
2. **Kekakuan Rekayasa Perangkat Lunak (Software Engineering Rigor):** Menerapkan standar modern pengembangan paket R (`usethis`, `devtools`, `testthat`), manajemen dependensi deterministik (`renv`), isolasi lingkungan (*containerization* dengan Docker), dan otomatisasi CI/CD.
3. **Optimasi Performa & Interoperabilitas Sistem:** Menguasai manipulasi memori *in-place* dengan `data.table`, pemrosesan paralel asinkron melalui ekosistem `future`, integrasi C++ melalui `Rcpp`, serta orkestrasi poliglota bersama Python melalui `reticulate`.

### Engineering Paradigm
* **Declarative & Tidy:** Memanfaatkan semantik modern Tidyverse (`dplyr`, `tidyr`, `purrr`) dan *Tidy Evaluation* (`rlang`) untuk membangun data pipeline deklaratif yang *self-documenting* dan tangguh.
* **Production-Grade Delivery:** Menghadirkan model analitik dan inferensi statistik bukan sebagai *notebook* terisolasi, melainkan sebagai *microservices REST API* (`plumber`), paket modular teruji, atau aplikasi web reaktif berskala enterprise (`shiny` + `golem`).

---

## 2. Learning Roadmap

```plaintext
R Programming: Production Engineering Architecture
│
├── 01. Fondasi R, RStudio Environment, & Vectorized Computing
│   ├── Modul 01: Arsitektur Runtime R & Vektor Atomik
│   ├── Modul 02: Atribut, Matriks, & Operasi Ter-vektorisasi
│   └── Modul 03: Penanganan Subsetting & Coercion Rules
│
├── 02. Data Structures, Control Flows, & Functional Semantics
│   ├── Modul 01: Lists, Data Frames, & S3 Object Orientation
│   ├── Modul 02: Control Flow, Scoping Rules, & Lazy Evaluation
│   └── Modul 03: Pure Functions, Side Effects, & Defensive Assertions
│
├── 03. Data Wrangling & Manipulation dengan Modern Tidyverse
│   ├── Modul 01: Tidy Data Principles & Semantik Native Pipe (|>)
│   ├── Modul 02: Transformasi Kompleks dengan dplyr
│   └── Modul 03: Restrukturisasi Relasional & Nested DataFrames via tidyr
│
├── 04. Data Import, Storage I/O, & Interoperabilitas
│   ├── Modul 01: High-Performance Flat-File & Parquet I/O (readr, arrow)
│   ├── Modul 02: Relational Databases Interface (DBI, dbplyr, pool)
│   └── Modul 03: Interoperabilitas Eksternal via Rcpp & reticulate
│
├── 05. Exploratory Data Analysis & Advanced Visualization
│   ├── Modul 01: Grammar of Graphics Mendalam dengan ggplot2
│   ├── Modul 02: Skala Kustom, Tema Korporat, & Sistem Koordinat
│   └── Modul 03: Komposisi Dashboard Statis & Interaktif (patchwork, plotly)
│
├── 06. Functional Programming & Metaprogramming
│   ├── Modul 01: Abstraksi Tingkat Tinggi dengan purrr
│   ├── Modul 02: Non-Standard Evaluation (NSE) & rlang Tidy Eval
│   └── Modul 03: Metaprogramming, Abstract Syntax Trees (AST), & Expressions
│
├── 07. Statistical Modeling & Inference Enterprise
│   ├── Modul 01: Model Linier, Generalized Linear Models (GLM), & Diagnostik
│   ├── Modul 02: Ekosistem Modern Tidymodels (rsample, recipes, parsnip)
│   └── Modul 03: Model Tuning, Cross-Validation, & Evaluasi (tune, yardstick)
│
├── 08. High-Performance Computing, Profiling, & Optimasi Memori
│   ├── Modul 01: Profiling Memori & Eksekusi (bench, profvis)
│   ├── Modul 02: In-Memory Optimization via data.table
│   └── Modul 03: Komputasi Paralel & Terdistribusi (future, furrr)
│
├── 09. Package Development, Reproducibility, & Testing
│   ├── Modul 01: Arsitektur Paket R Standar CRAN (devtools, usethis)
│   ├── Modul 02: Unit Testing (testthat) & Dokumentasi Formal (roxygen2)
│   └── Modul 03: Determinisme Dependensi (renv) & CI/CD Pipeline
│
└── 10. Production Deployment, API, & Interactive Dashboards
    ├── Modul 01: Enterprise REST API via Plumber
    ├── Modul 02: Arsitektur Aplikasi Skalabel Shiny dengan Framework Golem
    └── Modul 03: Kontainerisasi Docker & Observabilitas Sistem R
```

---

## 3. Navigasi Silabus

### [Bab 01: Fondasi R, RStudio Environment, & Vectorized Computing](./01-fondasi-dan-vektorisasi)
Fokus pada pemahaman mesin eksekusi R, representasi memori primitif, dan eliminasi imperatif for-loop melalui komputasi vektor.
* **[Modul 01: Arsitektur Runtime R & Vektor Atomik](./01-fondasi-dan-vektorisasi/01-runtime-dan-vektor.md)**
  * Arsitektur interpreter R, tipe data atomik (`logical`, `integer`, `double`, `character`, `complex`, `raw`).
  * Alokasi memori contiguous dan representasi low-level.
  * Deliverable: Benchmark komparatif struktur data primitif via R CLI.
* **[Modul 02: Atribut, Matriks, & Operasi Ter-vektorisasi](./01-fondasi-dan-vektorisasi/02-matriks-dan-vektorisasi.md)**
  * Metadata atribut, dimensi, operasi matriks, *broadcasting/recycling rules*.
  * SIMD vector operations bawaan R runtime.
  * Deliverable: Implementasi algoritma matriks ter-vektorisasi murni tanpa loop imperatif.
* **[Modul 03: Penanganan Subsetting & Coercion Rules](./01-fondasi-dan-vektorisasi/03-subsetting-dan-coercion.md)**
  * Aturan koersi implisit dan eksplisit, mekanika operator subsetting (`[`, `[[`, `$`).
  * Negative indexing, logical masks, dan pemfilteran memori efisien.
  * Deliverable: Suite ekstraksi data multidimensi dengan proteksi type-safety.

### [Bab 02: Data Structures, Control Flows, & Functional Semantics](./02-struktur-data-dan-kontrol-alur)
Mempelajari ekosistem struktur data heterogen, semantik evaluasi ekspresi, dan paradigma fungsi murni.
* **[Modul 01: Lists, Data Frames, & S3 Object Orientation](./02-struktur-data-dan-kontrol-alur/01-lists-dan-data-frames.md)**
  * Generic vector (Lists), anatomi `data.frame` sebagai kumpulan vektor paralel.
  * Dasar sistem objek S3: class attributes, generic functions, dan method dispatch.
  * Deliverable: Struktur objek S3 kustom beserta *print* dan *summary methods*.
* **[Modul 02: Control Flow, Scoping Rules, & Lazy Evaluation](./02-struktur-data-dan-kontrol-alur/02-scoping-dan-lazy-evaluation.md)**
  * Lexical scoping, Search Path, Execution Environments.
  * Mekanisme *Lazy Evaluation* dan konsep *Promises*.
  * Deliverable: Modul kontrol alur fungsional dengan pelacakan runtime environment.
* **[Modul 03: Pure Functions, Side Effects, & Defensive Assertions](./02-struktur-data-dan-kontrol-alur/03-fungsi-defensif.md)**
  * Desain fungsi deterministik murni, copy-on-modify semantics.
  * Defensive programming via `stopifnot()` dan assertion assertions (`checkmate`).
  * Deliverable: Paket utility fungsi defensif anti-fail dengan error handler kustom.

### [Bab 03: Data Wrangling & Manipulation dengan Modern Tidyverse](./03-tidy-data-wrangling)
Transformasi data deklaratif berkecepatan tinggi mengadopsi standar Tidy Data dan ekosistem modern R.
* **[Modul 01: Tidy Data Principles & Semantik Native Pipe (|>)](./03-tidy-data-wrangling/01-prinsip-tidy-dan-pipe.md)**
  * Kaidah data rapi Hadley Wickham, transisi dari Magrittr (`%>%`) ke Native Pipe (`|>`).
  * Implikasi performa alokasi pipeline.
  * Deliverable: Normalisasi dataset multidimensi berantakan ke dalam format Tidy standar.
* **[Modul 02: Transformasi Kompleks dengan dplyr](./03-tidy-data-wrangling/02-transformasi-dplyr.md)**
  * Operasi lanjutan dengan verb utama: `select`, `filter`, `mutate`, `summarise`, `relocate`.
  * Window functions, grouping sets via `pick()`, dan integrasi across-mutations.
  * Deliverable: Pipeline analitik metrik agregasi transaksi keuangan skala multi-kolom.
* **[Modul 03: Restrukturisasi Relasional & Nested DataFrames via tidyr](./03-tidy-data-wrangling/03-nested-dataframes-tidyr.md)**
  * Pivoting rumit (`pivot_longer`, `pivot_wider`), normalisasi data hierarkis.
  * List-columns dan manipulasi nested data frames via `nest()` dan `unnest()`.
  * Deliverable: Pipeline pembersihan data klinis hierarkis berstruktur kompleks.

### [Bab 04: Data Import, Storage I/O, & Interoperabilitas](./04-io-dan-interoperabilitas)
Menghubungkan R ke penyimpanan modern berkecepatan tinggi, database relasional, dan runtime bahasa lain.
* **[Modul 01: High-Performance Flat-File & Parquet I/O (readr, arrow)](./04-io-dan-interoperabilitas/01-flatfile-parquet-io.md)**
  * Ingestion berkas teks besar dengan `readr`.
  * Pembacaan dan penulisan Apache Parquet serta IPC Feather berkinerja tinggi menggunakan `arrow`.
  * Deliverable: Benchmark komparatif kecepatan baca/tulis CSV vs Parquet multi-gigabyte.
* **[Modul 02: Relational Databases Interface (DBI, dbplyr, pool)](./04-io-dan-interoperabilitas/02-koneksi-database-dbi-dbplyr.md)**
  * Koneksi enterprise PostgreSQL/DuckDB melalui `DBI`, connection pooling via `pool`.
  * Lazily-evaluated SQL pushdown optimization via `dbplyr`.
  * Deliverable: Pipeline ekstraksi database transaksional tanpa sintaks SQL mentah.
* **[Modul 03: Interoperabilitas Eksternal via Rcpp & reticulate](./04-io-dan-interoperabilitas/03-interop-rcpp-reticulate.md)**
  * Mengintegrasikan komputasi performa tinggi C++ ke dalam R via `Rcpp`.
  * Integrasi lingkungan Python dua arah yang mulus dengan `reticulate`.
  * Deliverable: Modul komputasi numerik intensif berbasis C++ yang dipanggil langsung dari sesi R.

### [Bab 05: Exploratory Data Analysis & Advanced Visualization](./05-visualisasi-dan-eda)
Visualisasi berbasis *Grammar of Graphics* standar publikasi dan analitik interaktif tingkat lanjut.
* **[Modul 01: Grammar of Graphics Mendalam dengan ggplot2](./05-visualisasi-dan-eda/01-grammar-of-graphics-ggplot2.md)**
  * Pemetaan estetika (*mappings*), lapisan geometris (*geoms*), transformasi statistik (*stats*).
  * Layer architecture dan anatomi objek plot ggplot2.
  * Deliverable: Visualisasi distribusi multidimensi kompleks siap publikasi akademis/industri.
* **[Modul 02: Skala Kustom, Tema Korporat, & Sistem Koordinat](./05-visualisasi-dan-eda/02-skala-dan-tema-ggplot2.md)**
  * Membangun custom color palettes, transformation scales, penyesuaian sumbu.
  * Rekayasa tema korporat kustom yang *reusable* dan *accessible*.
  * Deliverable: Paket tema grafik terstandardisasi untuk visual branding korporat.
* **[Modul 03: Komposisi Dashboard Statis & Interaktif (patchwork, plotly)](./05-visualisasi-dan-eda/03-komposisi-dan-interaktivitas.md)**
  * Komposisi layout multi-panel deklaratif menggunakan `patchwork`.
  * Konversi visualisasi statis menjadi grafik web interaktif via `plotly::ggplotly`.
  * Deliverable: Executive report multi-panel interaktif berbasis visualisasi ggplot2.

### [Bab 06: Functional Programming & Metaprogramming](./06-functional-dan-metaprogramming)
Pondasi rekayasa pustaka: automasi fungsional murni dan manipulasi sintaks R pada waktu kompilasi/interpretasi.
* **[Modul 01: Abstraksi Tingkat Tinggi dengan purrr](./06-functional-dan-metaprogramming/01-pemrograman-fungsional-purrr.md)**
  * Operasi keluarga `map()`, type-safe variants (`map_dbl`, `map_df`), fungsi pemotong (`pluck`).
  * Penanganan kegagalan secara anggun menggunakan `possibly()`, `safely()`, dan `quietly()`.
  * Deliverable: Mesin ETL paralel berbasis fungsi murni yang toleran terhadap *runtime crash*.
* **[Modul 02: Non-Standard Evaluation (NSE) & rlang Tidy Eval](./06-functional-dan-metaprogramming/02-tidy-evaluation-rlang.md)**
  * Konsep Data Masking, Injection operator (`!!`, `!!!`), dan Embracing operator (`{{ }}`).
  * Evaluasi ekspresi dinamis di dalam fungsi pembungkus (wrapper functions).
  * Deliverable: Wrapper kustom fleksibel untuk dplyr/ggplot2 yang mendukung passing column-name dinamis.
* **[Modul 03: Metaprogramming, Abstract Syntax Trees (AST), & Expressions](./06-functional-dan-metaprogramming/03-metaprogramming-ast.md)**
  * Representasi kode sebagai data: `call`, `symbol`, `expression`.
  * Inspeksi AST menggunakan `lobstr`, manipulasi struktur pohon sintaks sebelum eksekusi.
  * Deliverable: Domain-Specific Language (DSL) mini untuk parsing aturan validasi data bisnis.

### [Bab 07: Statistical Modeling & Inference Enterprise](./07-pemodelan-statistik-dan-inferensi)
Pemodelan statistik teruji secara empiris dan penerapan arsitektur modern machine learning dengan Tidymodels.
* **[Modul 01: Model Linier, Generalized Linear Models (GLM), & Diagnostik](./07-pemodelan-statistik-dan-inferensi/01-statistik-inferensial-glm.md)**
  * Regresi linier OLS, GLM (Logistic, Poisson), formulasi model via formula interface (`~`).
  * Diagnostik residual, multikolinearitas (VIF), goodness-of-fit.
  * Deliverable: Laporan analisis inferensial statistik lengkap dengan uji asumsi ketat.
* **[Modul 02: Ekosistem Modern Tidymodels (rsample, recipes, parsnip)](./07-pemodelan-statistik-dan-inferensi/02-arsitektur-tidymodels.md)**
  * Pemisahan data deterministik via `rsample`, feature engineering terotomasi via `recipes`.
  * Abstraksi antarmuka algoritma machine learning terstandarisasi dengan `parsnip`.
  * Deliverable: End-to-end preprocessing dan training pipeline yang tervolume dan modular.
* **[Modul 03: Model Tuning, Cross-Validation, & Evaluasi (tune, yardstick)](./07-pemodelan-statistik-dan-inferensi/03-tuning-dan-evaluasi.md)**
  * Hyperparameter tuning berbasis grid search dan Bayesian optimization via `tune`.
  * Validasi silang bertingkat (nested CV), evaluasi metrik kinerja model via `yardstick`.
  * Deliverable: Workflow tuning model prediktif terotomasi dengan laporan kurva ROC dan precision-recall.

### [Bab 08: High-Performance Computing, Profiling, & Optimasi Memori](./08-hpc-dan-optimasi-memori)
Membongkar batasan kecepatan R melalui audit alokasi memori, teknik in-place mutation, dan multithreading.
* **[Modul 01: Profiling Memori & Eksekusi (bench, profvis)](./08-hpc-dan-optimasi-memori/01-profiling-profvis-bench.md)**
  * Analisis bottleneck runtime via `profvis`, mikro-benchmark akurat via `bench`.
  * Deteksi kebocoran alokasi objek dan garbage collector churn.
  * Deliverable: Laporan audit profil performa sistem analitik beserta rekomendasi refaktornya.
* **[Modul 02: In-Memory Optimization via data.table](./08-hpc-dan-optimasi-memori/02-optimasi-memori-datatable.md)**
  * Sintaks canonical `[i, j, by]`, modifikasi data *in-place* menggunakan operator `:=`.
  * Pengindeksan cepat (secondary keys) dan memory footprint reduction.
  * Deliverable: Pemrosesan agregasi dataset 10 juta baris di bawah 1 detik tanpa footprint memori ganda.
* **[Modul 03: Komputasi Paralel & Terdistribusi (future, furrr)](./08-hpc-dan-optimasi-memori/03-paralelisasi-future-furrr.md)**
  * Arsitektur evaluasi asinkron dengan konsep `future`, paralelisasi fungsional via `furrr`.
  * Strategi eksekusi `multisession` vs `cluster` lintas platform sistem operasi.
  * Deliverable: Batch processing terparalelisasi penuh untuk komputasi simulasi Monte Carlo.

### [Bab 09: Package Development, Reproducibility, & Testing](./09-pengembangan-paket-dan-reproducibility)
Mengemas fungsi dan pipeline menjadi pustaka R berskala enterprise yang dapat diverifikasi dan dibagikan secara deterministik.
* **[Modul 01: Arsitektur Paket R Standar CRAN (devtools, usethis)](./09-pengembangan-paket-dan-reproducibility/01-struktur-paket-r.md)**
  * Struktur direktori paket (`R/`, `man/`, `inst/`, `DESCRIPTION`, `NAMESPACE`).
  * Orkestrasi siklus hidup pengembangan paket via `devtools` dan `usethis`.
  * Deliverable: Skeleton paket R mandiri yang lolos verifikasi sintaksis standar `R CMD check`.
* **[Modul 02: Unit Testing (testthat) & Dokumentasi Formal (roxygen2)](./09-pengembangan-paket-dan-reproducibility/02-testing-dan-dokumentasi.md)**
  * Implementasi unit test otomatis berbasis BDD menggunakan `testthat`.
  * Dokumentasi kode sumber tingkat tinggi, panduan fungsi, dan ekspor API via `roxygen2`.
  * Deliverable: Test suite komprehensif dengan code coverage di atas 85% dan dokumentasi manual lengkap.
* **[Modul 03: Determinisme Dependensi (renv) & CI/CD Pipeline](./09-pengembangan-paket-dan-reproducibility/03-renv-dan-cicd.md)**
  * Kuncian dependensi terisolasi deterministik dengan `renv` (`renv.lock`).
  * Integrasi continuous testing dan build automation via GitHub Actions untuk paket R.
  * Deliverable: Pipeline CI/CD fungsional yang menjalankan `R CMD check` dan verifikasi lockfile otomatis.

### [Bab 10: Production Deployment, API, & Interactive Dashboards](./10-deployment-api-dan-shiny)
Operasionalisasi kode R ke lingkungan produksi berbasis layanan mikro web dan dasbor reaktif korporat.
* **[Modul 01: Enterprise REST API via Plumber](./10-deployment-api-dan-shiny/01-rest-api-plumber.md)**
  * Anotasi dekorator Plumber (`#* @get`, `#* @post`), serialisasi JSON, filter request.
  * Penanganan otentikasi Bearer token dan penanganan error terstruktur pada API R.
  * Deliverable: RESTful microservice API untuk melayani inferensi model machine learning secara real-time.
* **[Modul 02: Arsitektur Aplikasi Skalabel Shiny dengan Framework Golem](./10-deployment-api-dan-shiny/02-enterprise-shiny-golem.md)**
  * Desain antarmuka reaktif berbasis modul Shiny, isolasi *namespace*.
  * Pengembangan Shiny sebagai paket R standar industri menggunakan framework `golem`.
  * Deliverable: Aplikasi Shiny skala enterprise yang dimodularisasi penuh dan *production-ready*.
* **[Modul 03: Kontainerisasi Docker & Observabilitas Sistem R](./10-deployment-api-dan-shiny/03-docker-dan-observabilitas.md)**
  * Pembuatan multi-stage Dockerfile teroptimasi untuk runtime R dan C++ dependencies.
  * Strategi logging terstruktur (`logger`), metrik performa, dan kesiapan deploy ke Kubernetes/Cloud Run.
  * Deliverable: Docker container image R production-ready dengan footprint terkompresi dan healthcheck API.

---

## 4. Enterprise Capstone Project

### Judul Sistem
**Enterprise Real-Time Financial Risk Analytics Engine & Automated Actuarial Microservice**

### Deskripsi Arsitektur
Capstone Project ini menuntut peserta untuk membangun sebuah sistem terpadu end-to-end yang memproses jutaan transaksi perbankan, memodelkan probabilitas gagal bayar (*Credit Default Risk*), dan menyediakan antarmuka analitik interaktif serta API publikasi:

```plaintext
[Data Source: PostgreSQL / S3 Parquet]
                    │
                    ▼
[Batch & Stream ETL Pipeline (arrow + data.table)]
                    │
                    ▼
[Feature Engineering & Model Pipeline (tidymodels)]
                    │
      ┌─────────────┴─────────────┐
      ▼                           ▼
[Plumber REST API Engine]    [Modular Shiny Dashboard (golem)]
      │                           │
      └─────────────┬─────────────┘
                    ▼
[Multi-stage Dockerized Container + GitHub Actions CI/CD]
```

### Komponen Wajib Capstone
1. **Paket R Mandiri (Internal R Package):**
   * Seluruh logika analisis harus dibungkus dalam bentuk paket R yang lolos verifikasi ketat `R CMD check --as-cran` tanpa warning dan tanpa error.
   * Dokumentasi fungsi tergenerasi penuh melalui `roxygen2` dan ditinjau dengan coverage `testthat` $\ge 85\%$.
2. **High-Performance Ingestion & Cleaning Engine:**
   * Membaca dataset transaksi historis berukuran multi-gigabyte format Parquet via `arrow`.
   * Transformasi metrik agregasi risiko likuiditas memanfaatkan manipulasi *in-place* mutasi memori `data.table` dan fungsi akselerasi numerik `Rcpp`.
3. **Reproducible Modeling & Inference Framework:**
   * Pemanfaatan `recipes` untuk penanganan *missing values*, standardisasi fitur, dan penanganan ketidakseimbangan kelas (*class imbalance*).
   * Pelatihan model ensemble (misalnya Regularized GLM + Gradient Boosting) via `parsnip` & evaluasi metrik diskriminasi (AUC-ROC, Brier Score) via `yardstick`.
4. **Decoupled API & Executive User Interface:**
   * **Inference Endpoint:** REST API via `plumber` yang menerima payload transaksi baru dalam format JSON dan mengembalikan estimasi risiko kredit secara real-time.
   * **Executive Dashboard:** Aplikasi interaktif berbasis `shiny` berarsitektur modular `golem` yang memvisualisasikan portofolio risiko menggunakan visualisasi `ggplot2` dan `plotly`.
5. **Production Deployment Standards:**
   * Isolasi dependensi menggunakan `renv.lock`.
   * Kontainerisasi penuh aplikasi menggunakan multi-stage `Dockerfile` berbasis image resmi Rocker (`rocker/r-ver`).
   * Skrip otomasi CI/CD via GitHub Actions yang menjalankan linting kode (`lintr`), pengujian unit otomatis (`testthat`), dan pembangunan Docker image secara headless.

---

## Standar Kode & Panduan Kontribusi
* Seluruh skrip R wajib mematuhi [Tidyverse Style Guide](https://style.tidyverse.org/).
* Gunakan operator Native Pipe `|>` untuk seluruh modul (R $\ge$ 4.1.0).
* Komentar fungsi internal wajib menyertakan tipe input/output eksplisit serta catatan kompleksitas waktu/memori.
* Untuk memulai perjalanan belajar, silakan akses modul pertama di **[Bab 01: Fondasi R, RStudio Environment, & Vectorized Computing](./01-fondasi-dan-vektorisasi)**.