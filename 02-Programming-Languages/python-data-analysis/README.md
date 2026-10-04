# Enterprise Python Data Analysis: Architectural Curriculum & Production Engineering

Selamat datang di kurikulum definitif **Python Data Analysis**. Silabus ini dirancang oleh *Senior Technical Curriculum Architect* untuk mentransformasi praktisi data konvensional menjadi *Production Data Analytics Engineer* dan *High-Performance Quantitative Analyst*.

---

## 1. Course Overview & Mindset

### Paradigma Rekayasa Data Modern
Sebagian besar praktisi terjebak dalam paradigma data analysis usang: memuat seluruh file `.csv` mentah ke dalam RAM melalui `pandas.read_csv`, mengabaikan tipe data numerik, menggunakan `for-loop` atau `.apply()` lambat yang terhambat oleh *Global Interpreter Lock* (GIL), serta membiarkan pipeline analitik gagal tanpa validasi skema runtime.

Kurikulum ini mengadopsi standar rekayasa enterprise:
* **Vectorization-First & Memory Efficiency**: Memahami alokasi memori buffer C/Fortran, *strides*, serta mengeksekusi operasi SIMD (*Single Instruction, Multiple Data*) alih-alih iterasi sekuensial.
* **Modern In-Memory Architecture**: Transisi dari struktur memori *object-pointer-heavy* milik Pandas lawas ke ekosistem **Apache Arrow columnar format** dan performa multithreaded **Polars** berbasis Rust.
* **Out-of-Core & Parallel Scalability**: Menyelesaikan bottleneck komputasi data skala gigabyte-ke-terabyte menggunakan lazy evaluation, predicate pushdown, Dask, dan Ray tanpa dependensi instan terhadap klaster Apache Spark yang mahal.
* **Production Data Quality & Contracts**: Menerapkan data contract deklaratif via Pandera dan Great Expectations, dilengkapi profiling profiler memori, automated testing (Pytest), serta integrasi pipeline CI/CD.

```
       TRADISIONAL (RAPUH)                      ENTERPRISE ENGINE (KURIKULUM INI)
+--------------------------------+      +---------------------------------------------------+
|  Pandas 1.x Object Dtypes      |      |  Apache Arrow Backend & Polars Lazy Expressions   |
|  Uncompressed CSV I/O          | ---> |  Parquet Snappy/ZSTD with Predicate Pushdown      |
|  Slow Python Loops / .apply()  |      |  SIMD-Vectorized NumPy / Rust Multithreading Engine|
|  Ad-hoc Notebooks (No Tests)   |      |  Data Contracts (Pandera) + Scalable Task Graphs  |
+--------------------------------+      +---------------------------------------------------+
```

---

## 2. Learning Roadmap

```
Python Data Analysis Enterprise Engine
│
├── [Bab 01] Fondasi Komputasi & Arsitektur Memori NumPy
│
├── [Bab 02] Ingesti Data Kinerja Tinggi & Storage Formats
│
├── [Bab 03] Data Wrangling Modern: Pandas 2.x & Apache Arrow
│
├── [Bab 04] High-Performance Engine: Polars & Out-of-Core Processing
│
├── [Bab 05] Exploratory Data Analysis & Statistika Terapan Enterprise
│
├── [Bab 06] Visualisasi Data Analitik & Declarative Dashboarding
│
├── [Bab 07] Analisis Runtun Waktu & Ekonometrika Lanjut (Time Series)
│
├── [Bab 08] Pemodelan Statistik Inferensial & Machine Learning Terapan
│
├── [Bab 09] Skalabilitas Data & Komputasi Paralel Terdistribusi (Dask & Ray)
│
└── [Bab 10] Data Contracts, Quality Automation, & Pipeline Engineering
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Komputasi & Arsitektur Memori NumPy](./01-fondasi-numpy-arsitektur-memori/)
Fondasi mutlak performa komputasi Python: layout memori internal, contiguous arrays, dan vektorisasi murni.
* [Modul 01: Arsitektur Memori NumPy: C-Order vs Fortran-Order, Strides, dan Buffer Protocol](./01-fondasi-numpy-arsitektur-memori/01-modul-arsitektur-memori-numpy.md)
  * Membedah memory layout array n-dimensi, manipulasi strides, memory views tanpa salin data (*zero-copy*), dan mitigasi overhead pointer memori bawaan CPython.
* [Modul 02: Vektorisasi Lanjut, Broadcasting Rules, Ufuncs, dan Bitwise Masking](./01-fondasi-numpy-arsitektur-memori/02-modul-vektorisasi-broadcasting.md)
  * Mekanisme internal broadcasting matrix multi-dimensi, implementasi Universal Functions (*ufuncs*) kustom, dan operasi Boolean indexing berkinerja tinggi.

### [Bab 02: Ingesti Data Kinerja Tinggi & Storage Formats](./02-ingesti-akuisisi-data/)
Strategi membaca, serialisasi, dan optimasi format data analitik untuk beban kerja I/O intensif.
* [Modul 01: Benchmarking Format Penyimpanan: CSV vs Parquet vs Feather vs Arrow IPC](./02-ingesti-akuisisi-data/01-modul-benchmarking-storage-formats.md)
  * Analisis trade-off rasio kompresi (Snappy vs ZSTD), throughput I/O, eksekusi *dictionary encoding*, serta *metadata statistics* untuk *partition pruning*.
* [Modul 02: Streaming Ingestion, Chunking Strategy, dan Ingesti Database Relasional via SQLAlchemy & Arrow](./02-ingesti-akuisisi-data/02-modul-streaming-ingestion-chunking.md)
  * Menangani dataset yang melampaui kapasitas RAM menggunakan generator-based streaming, batch chunking, serta koneksi *zero-copy database pooling*.

### [Bab 03: Data Wrangling Modern: Pandas 2.x & Apache Arrow Backend](./03-data-wrangling-pandas-pyarrow/)
Transformasi data idiomatik berkecepatan tinggi menggunakan arsitektur modern Pandas 2.x dan Apache Arrow engine.
* [Modul 01: Integrasi Apache Arrow Backend pada Pandas 2.x: Type Safety & Zero-Copy](./03-data-wrangling-pandas-pyarrow/01-modul-pandas-pyarrow-backend.md)
  * Migrasi tipe data objek rapuh menuju Arrow types yang strictly-typed, optimasi footprint memori string, dan pencegahan *implicit downcasting*.
* [Modul 02: Transformasi Data Kompleks: MultiIndex, Hierarchical Reshaping, & Window Functions](./03-data-wrangling-pandas-pyarrow/02-modul-transformasi-kompleks-multiindex.md)
  * Operasi pivot tables tingkat lanjut, unstacking dimensionalitas tinggi, integrasi *expanding/rolling windows*, dan custom aggregation via `NamedAgg`.
* [Modul 03: Strategi Missing Data, Anomali Imputasi, dan Optimasi Kategori](./03-data-wrangling-pandas-pyarrow/03-modul-missing-data-categorical-optimization.md)
  * Penanganan nilai null native (`pd.NA`), evaluasi bias imputasi, serta reduksi memori skala besar menggunakan Arrow Dictionary Encoding.

### [Bab 04: High-Performance Engine: Polars & Out-of-Core Processing](./04-kinerja-tinggi-polars/)
Evolusi komputasi analitik modern menggunakan Rust-based multithreaded execution engine.
* [Modul 01: Arsitektur Polars: Rust Core, Expression Contexts, dan Multithreading Execution Engine](./04-kinerja-tinggi-polars/01-modul-arsitektur-polars-expressions.md)
  * Konsep evaluasi kontekstual (`select`, `with_columns`, `filter`, `group_by`), paralelisme native tanpa GIL, dan sintaks expressions deklaratif.
* [Modul 02: LazyFrame Optimization: Query Plan Inspection (`explain`), Predicate Pushdown, dan Streaming Engine](./04-kinerja-tinggi-polars/02-modul-lazyframe-query-optimization.md)
  * Memanfaatkan query optimizer otomatis, analisis logical vs physical execution graph, serta out-of-core streaming execution untuk dataset lebih besar dari RAM fisik.

### [Bab 05: Exploratory Data Analysis & Statistika Terapan Enterprise](./05-eda-statistika-terapan/)
Eksplorasi data sistematis yang didukung landasan teori probabilitas dan statistika ketat.
* [Modul 01: Statistika Deskriptif Robust, Uji Distribusi, dan Deteksi Outlier Multivariat](./05-eda-statistika-terapan/01-modul-statistika-deskriptif-outliers.md)
  * Parameter robust (IQR, MAD) vs non-robust, uji normalitas (Shapiro-Wilk, Kolmogorov-Smirnov), serta deteksi anomali multivariat menggunakan Mahalanobis Distance dan Isolation Forest.
* [Modul 02: Korelasi Non-Linear, Uji Hipotesis Parametrik/Non-Parametrik, dan Koreksi Kesalahan Tipe I](./05-eda-statistika-terapan/02-modul-korelasi-uji-hipotesis.md)
  * Evaluasi Pearson, Spearman, Kendall Tau, Distance Correlation; implementasi t-test, Mann-Whitney U, ANOVA, Chi-Square, serta penyesuaian p-value (Bonferroni / FDR Benjamini-Hochberg).

### [Bab 06: Visualisasi Data Analitik & Declarative Dashboarding](./06-visualisasi-data-deklaratif/)
Komunikasi visual data presisi tinggi untuk data scientist, eksekutif, dan sistem otomasi.
* [Modul 01: Visualisasi Eksploratori Produksi via Matplotlib Object-Oriented Interface & Seaborn Engine](./06-visualisasi-data-deklaratif/01-modul-matplotlib-seaborn-oo-api.md)
  * Arsitektur `Figure` dan `Axes`, kustomisasi hierarki canvas, distribusi bivariate/trivariate kompleks, serta standarisasi style analitik perusahaan.
* [Modul 02: Visualisasi Analitik Interaktif Skala Besar dengan Plotly & Deck.gl](./06-visualisasi-data-deklaratif/02-modul-plotly-geospatial-analytics.md)
  * Rendering dataset padat menggunakan WebGL/Plotly-Resampler, plot choropleth/spasial geospatial multi-layer, dan visualisasi diagnostik multidimensi interaktif.

### [Bab 07: Analisis Runtun Waktu & Ekonometrika Lanjut (Time Series)](./07-analisis-runtun-waktu/)
Analisis data temporal, pemodelan stokastik, dan dekomposisi data finansial/operasional.
* [Modul 01: Temporal Indexing, Resampling, Windowing, Autokorelasi (ACF/PACF), dan STL Decomposition](./07-analisis-runtun-waktu/01-modul-indexing-temporal-dekomposisi.md)
  * Manipulasi zona waktu ISO 8601, rolling aggregations dengan offset variabel, deteksi stasionaritas (Augmented Dickey-Fuller / KPSS), dan dekomposisi musiman LOESS.
* [Modul 02: Forecasting Statistik Terapan: Arsitektur ARIMA/SARIMAX dan Evaluasi Walk-Forward](./07-analisis-runtun-waktu/02-modul-forecasting-statistika-arima.md)
  * Pemodelan ekonometrika linier, integrasi regresi eksogen (exogenous covariates), analisis residual diagnostik (Ljung-Box), dan validasi cross-validation temporal bergeser.

### [Bab 08: Pemodelan Statistik Inferensial & Machine Learning Terapan](./08-statistika-inferensial-ml-pra-produksi/)
Bridging analisis data eksploratori menuju pemodelan prediktif inferensial yang siap dideploy.
* [Modul 01: Regresi Linier Tergeneralisasi (GLM) dan Estimasi Probabilistik via Statsmodels](./08-statistika-inferensial-ml-pra-produksi/01-modul-glm-statsmodels-probabilistik.md)
  * Interpretasi logit, probit, regresi Poisson untuk count-data, multikolinearitas (VIF), serta pelaporan koefisien dan confidence interval tingkat enterprise.
* [Modul 02: Feature Engineering Terotomasi, Target Encoding, dan Pipeline Scikit-Learn Robust](./08-statistika-inferensial-ml-pra-produksi/02-modul-feature-engineering-scikit-pipeline.md)
  * Mencegah data leakage fatal via `ColumnTransformer` dan `Pipeline`, rekayasa interaksi fitur non-linear, robust scaling, dan evaluasi berbasis cross-validation berlapis (*nested CV*).

### [Bab 09: Skalabilitas Data & Komputasi Paralel Terdistribusi (Dask & Ray)](./09-skalabilitas-komputasi-paralel/)
Melampaui limitasi memori mesin tunggal menuju klaster terdistribusi tanpa meninggalkan ekosistem Python.
* [Modul 01: Komputasi Terdistribusi In-Memory dengan Dask DataFrame dan Directed Acyclic Graph (DAG)](./09-skalabilitas-komputasi-paralel/01-modul-dask-dataframe-dag.md)
  * Membedah Dask DAG Scheduler, partisi optimal, lazy reduction computations, identifikasi bottleneck worker memory spills, dan Dask Distributed Dashboard.
* [Modul 02: Orchestrasi Analitik Skala Klaster Menggunakan Ray Core dan Modin](./09-skalabilitas-komputasi-paralel/02-modul-ray-core-modin-orchestration.md)
  * Parallel tasks and actors pattern pada Ray, eksekusi Pandas queries otomatis terdistribusi melalui Modin engine, dan manajemen resource klaster.

### [Bab 10: Data Contracts, Quality Automation, & Pipeline Engineering](./10-data-quality-testing-mlops/)
Standar rekayasa perangkat lunak untuk menjaga integritas data pipeline tingkat enterprise.
* [Modul 01: Validasi Skema & Kontrak Data Deklaratif Menggunakan Pandera dan Great Expectations](./10-data-quality-testing-mlops/01-modul-data-contract-great-expectations-pandera.md)
  * Menulis schema models statis berkecepatan tinggi, validasi nullability, domain ranges, checks relasional, dan automated documentation generation.
* [Modul 02: Profiling Memori, Otomasi Analitik, dan Testing Terintegrasi (Pytest & CI Data Pipeline)](./10-data-quality-testing-mlops/02-modul-memory-profiling-ci-data-testing.md)
  * Profiling CPU dan alokasi heap via `scalene` dan `memory_profiler`, penulisan automated data unit-testing dengan Pytest, serta integrasi checks ke dalam pipeline CI/CD GitHub Actions.

---

## 4. Enterprise Capstone Project

### Judul Sistem
**High-Frequency FinTech Multi-Source Settlement & Risk Analytics Engine**

### Deskripsi Masalah
Institusi pembayaran memproses puluhan juta transaksi settlement multi-mata uang harian yang terdistribusi ke dalam puluhan file log transaksi mentah, database PostgreSQL, dan rate feeds API eksternal. Pipeline analitik lama sering mengalami *Out-Of-Memory (OOM)* error, lambat (berjalan lebih dari 4 jam), dan menghasilkan kalkulasi mismatch margin risiko akibat kegagalan menangani floating-point error dan timestamp skew.

### Arsitektur Sistem
```
[Raw Sources: Partitioned Parquet Logs + PostgreSQL Ledger DB + Exchange Rate JSON]
                                    │
                                    ▼
       [Data Ingestion Stage: Polars Streaming / PyArrow Chunked Engines]
                                    │
                                    ▼
         [Validation Gate: Pandera Declarative Schema Contract Enforcer]
                   ├─ Invalid Records  ──> Dead-Letter Parquet Queue
                   └─ Valid Records    ──> Pipeline Core
                                    │
                                    ▼
         [High-Performance Processing Engine: Polars / Dask Graph Execution]
            * Multi-currency currency conversion vectorization
            * Temporal Rolling Windows (1h, 24h risk exposure per merchant)
            * Multi-factor Anomaly & Outlier Filtering (Mahalanobis / Isolation)
                                    │
                                    ▼
    [Reporting & Diagnostics: Automated Aggregates + Interactive Plotly Dashboard]
                                    │
                                    ▼
       [CI/CD Assurance: Pytest Unit/Integration Suite + Scalene Memory Audit]
```

### Persyaratan Teknis & Deliverables
1. **Engine Core (Polars & PyArrow)**:
   * Mengonsumsi dataset transaksi multi-partisi (>10GB sintetis atau riil) dengan batas maksimum alokasi RAM mesin < 2GB menggunakan streaming/lazy evaluation.
   * Tidak boleh menggunakan nested for-loop konvensional maupun fungsi `.apply()` python lambat pada transformasi tabular.
2. **Data Contracts & Integrity**:
   * Skema data didefinisikan menggunakan **Pandera Data Model**. Rekor data yang melanggar kontrak dialirkan secara otomatis ke *Dead-Letter Partition* tanpa menghentikan pipeline utama.
3. **Analitik Risiko Temporal & Anomali**:
   * Agregasi dynamic rolling window untuk mendeteksi *velocity fraud* (misal: lebih dari 10 transaksi per kartu dalam rentang 60 detik).
   * Deteksi anomali volume dan nilai transaksi berbasis uji statistika multivariat.
4. **Benchmarking & Memory Profiling Report**:
   * Laporan komparasi mendalam antara implementasi legacy Pandas vs Polars Engine: CPU Time, Peak Heap Memory (`scalene`), dan Disk Footprint.
5. **Production Readiness (CI/CD Suite)**:
   * Test suite berbasis **Pytest** dengan cakupan edge-cases (missing values, leap year, duplicate transaction IDs, data corruption).

---

## Petunjuk Memulai
Untuk memulai perjalanan ini, arahkan terminal Anda ke modul pertama:
```bash
cd 01-fondasi-numpy-arsitektur-memori
cat 01-modul-arsitektur-memori-numpy.md
```
Gunakan Python 3.10+ dan virtual environment khusus:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy pandas pyarrow polars dask statsmodels scikit-learn seaborn plotly pandera pytest scalene
```