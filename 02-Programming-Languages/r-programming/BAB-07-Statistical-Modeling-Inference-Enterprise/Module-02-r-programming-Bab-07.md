# BAB 07: Statistical Modeling & Inference Enterprise
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Algoritma Inferensi Tingkat Lanjut**: Menguasai mekanisme numerik *Iteratively Reweighted Least Squares* (IRLS), dekomposisi QR, dekomposisi Cholesky, serta aproksimasi Laplace pada *Generalized Linear Models* (GLM) dan *Generalized Linear Mixed-Effects Models* (GLMM).
2. **Mengoptimalkan *Memory Footprint* dan Komputasi Matriks**: Mengeliminasi *lexical environment leak* pada objek model R, memanfaatkan *sparse matrix* (`Matrix`), dan mengimplementasikan *low-latency model scoring engine* menggunakan `fastglm` dan `RcppEigen`.
3. **Mendesain Arsitektur Produksi Model Inferensial**: Membangun *pipeline* serialisasi model yang aman, deterministik, dan *production-grade* menggunakan format biner efisien (`qs`), serta memaketkannya ke dalam layanan microservice berbasis REST API menggunakan `plumber` di dalam Docker container.
4. **Menerapkan *Defensive Statistical Engineering***: Menangani multikolinearitas ekstrem, *quasi-complete separation*, singularitas matriks kovarians, dan pergeseran kovariat (*covariate drift*) pada level *runtime production*.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Matematika & Teori Statistik**: Kalkulus peubah ganda, aljabar linier terapan (inversi matriks, dekomposisi definit positif), *Maximum Likelihood Estimation* (MLE), dan konsep pengujian hipotesis (Wald test, Likelihood Ratio Test).
- **R Internals**: Pemahaman mendalam mengenai lingkungan R (*lexical scoping*, *closure*, *environments*), sistem S3/S4, dan manipulasi struktur data berkinerja tinggi menggunakan `data.table`.
- **Infrastruktur Dasar**: Perintah dasar Linux shell, konsep dasar virtualisasi berbasis kontainer (Docker), dan protokol HTTP/REST.

---

### 3. Concept & Internal Architecture

#### 3.1. Mekanisme Numerik: Dari OLS ke IRLS dan Estimasi GLMM

Pada model linier standar ($Y = X\beta + \varepsilon$), parameter $\hat{\beta}$ diperoleh melalui penyelesaian *Normal Equations*:

$$(X^T X)\hat{\beta} = X^T Y \implies \hat{\beta} = (X^T X)^{-1} X^T Y$$

Dalam implementasi produksi base R (`.lm.fit`), R **tidak pernah** menginversi matriks $(X^T X)$ secara langsung karena instabilitas numerik akibat pengkondisian matriks (*condition number* $\kappa(X^T X) = \kappa(X)^2$). R menggunakan **Dekomposisi QR**:

$$X = QR$$

Di mana $Q$ adalah matriks ortogonal ($Q^T Q = I$) dan $R$ adalah matriks segitiga atas (*upper triangular*). Persamaan dipecahkan via *back-substitution*:

$$R\hat{\beta} = Q^T Y$$

```
   [ Data Matrix X ]                 [ QR Decomposition ]             [ Parameter Vector β ]
     (n x p matrix)                   X = Q (n x p)                   R β = Q^T Y
                                          R (p x p)                   Solved via Back-Substitution
  ┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
  │ x11 x12 ... x1p │               │ q11 q12 ... q1p │               │  β_0            │
  │ x21 x22 ... x2p │  ──────────>  │ q21 q22 ... q2p │  ──────────>  │  β_1            │
  │ ... ... ... ... │  LAPACK: dqrls│ ... ... ... ... │  Backward     │  ...            │
  │ xn1 xn2 ... xnp │               │  0   0  ... rpp │  Substitution │  β_p            │
  └─────────────────┘               └─────────────────┘               └─────────────────┘
```

Untuk *Generalized Linear Models* (GLM), di mana variabel respon berdistribusi *Exponential Family* dengan fungsi tautan (*link function*) $g(\mu) = \eta = X\beta$, solusi analitis tertutup tidak ada. R menggunakan algoritma **Iteratively Reweighted Least Squares (IRLS)**:

1. **Inisialisasi**: Tentukan nilai awal $\mu^{(0)}$ dan $\eta^{(0)} = g(\mu^{(0)})$.
2. **Hitung Variabel Dependen Kerja (*Working Variable*)**:
   $$z^{(t)} = \eta^{(t)} + (y - \mu^{(t)}) \left( \frac{\partial \eta}{\partial \mu} \right)^{(t)}$$
3. **Hitung Matriks Bobot (*Iterative Weights*)**:
   $$W^{(t)} = \operatorname{diag}\left( \frac{1}{\operatorname{Var}(Y_i) \left( \frac{\partial \eta_i}{\partial \mu_i} \right)^2} \right)^{(t)}$$
4. **Perbarui Estimasi Parameter**:
   $$\beta^{(t+1)} = (X^T W^{(t)} X)^{-1} X^T W^{(t)} z^{(t)}$$
   *Secara internal, R menyelesaikan sistem berbobot ini kembali menggunakan dekomposisi QR terbobot pada setiap iterasi.*
5. **Kriteria Konvergensi**: Iterasi dihentikan ketika deviasi terbobot:
   $$\frac{|D^{(t+1)} - D^{(t)}|}{|D^{(t)}| + 0.1} < \epsilon \quad (\text{default } \epsilon = 10^{-8})$$

#### 3.2. Masalah Lingkungan Leksikal (Lexical Scope) & *Memory Bloat*

Salah satu anomali struktural terbesar pada R adalah bagaimana formula `formula` mengikat lingkungan (*lexical environment*) pemanggilnya.

```
       Global Environment (.GlobalEnv)
  ┌──────────────────────────────────────────────┐
  │  large_dataset (10 GB)                       │
  │  temp_variables, API keys, cache             │
  │                                              │
  │  fit <- glm(y ~ x1 + x2, data = df)          │
  │   │                                          │
  │   └───> fit$terms                            │
  │          └───> environment() ────────────────┼───┐ (Menyimpan referensi ke .GlobalEnv)
  └──────────────────────────────────────────────┘   │
                                                     │
  Objek model diserialisasi via saveRDS(fit)         │
  Akibat: 10 GB data di .GlobalEnv ikut tersimpan!  │
  Ukuran file model: 15 KB (harapan) -> 10 GB (faktual) ◄┘
```

Ketika model `lm`, `glm`, atau `lmer` dibuat, komponen `terms` membawa atribut `.Environment`. Jika model disimpan menggunakan `saveRDS()` atau `serialize()`, R runtime akan menyertakan seluruh objek yang berada dalam *scope* lingkungan tersebut. Di lingkungan produksi berkapasitas memori ketat, kebocoran memori ini dapat menyebabkan crash seketika (*OOM Killer*).

---

### 4. Why & What

| Dimensi | Pendekatan Base R Default (`glm`, `saveRDS`) | Pendekatan Enterprise Engineering (`fastglm`, `qs`, Pruned Architecture) |
| :--- | :--- | :--- |
| **Metode Estimasi** | Single-threaded LAPACK routines (`dqrls`) melalui C/FORTRAN standard. | Multithreaded AVX-accelerated Matrix operations via `Eigen` / `BLAS`. |
| **Konsumsi Memori Objek** | Menyimpan *data frame*, *residuals*, *effects*, *qr*, *fitted values*, dan referensi lingkungan lengkap (Rata-rata 50 MB - 5 GB). | Hanya menyimpan *stripped vector parameter*, matriks varians-kovarians, dan level metadata (Ukuran: < 50 KB). |
| **Throughput Scoring (Predict)** | Mengandalkan parsing `data.frame` lambat dengan overhead `model.frame` dan formula overhead ($\approx 200 - 500 \text{ req/sec}$). | Menggunakan operasi perkalian matriks vektor langsung $X\beta$ berbasis `Rcpp` atau `Matrix` sparse ($\ge 10.000 \text{ req/sec}$). |
| **Stabilitas Numerik** | Terhenti (*crash* atau melempar *warning*) saat terjadi separasi data (*quasicomplete separation*) atau multikolinearitas. | Dilengkapi *L2-penalization* (Ridge fallback), pemotongan gradien, dan deteksi dini singularitas rank. |
| **Arsitektur Deploy** | Script monolitik, interaksi interaktif via RStudio/notebook. | REST API berbasis Plumber terisolasi dalam *lightweight* Docker container, stateless, autoscalable. |

---

### 5. How (Workflow Detail)

Alur kerja dari pelatihan hingga eksekusi inferensi di level enterprise mengikuti tahapan deterministik berikut:

```
[1. Data Extraction & Sparse Matrix Prep]
                  │
                  ▼
[2. Numerical Stabilization & Regularization Checks]
                  │
                  ▼
[3. High-Performance Model Fitting (fastglm / glmmTMB)]
                  │
                  ▼
[4. Model Pruning & Environment Detachment]
                  │
                  ▼
[5. Ultra-Compressed Serialization (qs format)]
                  │
                  ▼
[6. Containerized Deployment (Plumber API + Multi-worker)]
                  │
                  ▼
[7. High-Throughput Matrix-Based Scoring Pipeline]
```

1. **Data Prep**: Data ditransformasi ke format `dgCMatrix` (Compressed Sparse Column) untuk menangani *one-hot encoding* berkardinalitas tinggi secara hemat memori.
2. **Stabilization**: Validasi kondisi rank matriks menggunakan `rcond()`. Jika matriks buruk (*ill-conditioned*), aktifkan regularisasi Tikhonov (L2 Ridge penalty).
3. **Fitting**: Komputasi menggunakan *accelerated solver* yang tidak mengalokasikan memori perantara secara berlebih.
4. **Pruning**: Komponen non-esensial (`residuals`, `fitted.values`, `weights`, `prior.weights`, `model`, `linear.predictors`) dibuang. Atribut environment pada objek `terms` disetel ke `emptyenv()`.
5. **Serialization**: Serialisasi biner menggunakan kompresi Zstandard tingkat lanjut via library `qs`.
6. **Deploy**: Layanan API Plumber membungkus model ke dalam worker pool statis, membaca input JSON, memvalidasi skema menggunakan validasi berbasis kontrak, dan mengembalikan probabilitas inferensial beserta interval kepercayaan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Jet Tempur vs Pesawat Angkut Kargo
*Model R default ibarat pesawat angkut kargo*: setiap kali Anda meminta pesawat tersebut terbang untuk menjalankan sebuah misi (melakukan inferensi), ia membawa serta seluruh suku cadang pabrik, kru manufaktur, blueprint desain, dan seluruh sisa bahan bakar produksi (formula environment, residuals, full matrix input). 

*Model Pruning & Production Engine ibarat jet tempur supersonik*: Anda membongkar seluruh kabin penumpang, membuang peralatan pabrik, dan hanya menyisakan kokpit dan mesin penembak terarah (vektor koefisien $\beta$, matriks kovarians tereduksi, fungsi inverse-link).

```
   BASE R GLM ARTIFACT STRUCTURE (OBESE)
   ┌──────────────────────────────────────────────────────────────┐
   │ model.dump.rds (520 MB)                                      │
   │  ├── $coefficients      (8 bytes * p)                        │
   │  ├── $residuals         (8 bytes * n)  <-- Hapus di Prod     │
   │  ├── $fitted.values     (8 bytes * n)  <-- Hapus di Prod     │
   │  ├── $effects           (8 bytes * n)  <-- Hapus di Prod     │
   │  ├── $weights           (8 bytes * n)  <-- Hapus di Prod     │
   │  ├── $model             (Full Raw Data Frame) <-- Fatal Leak │
   │  └── $terms                                                  │
   │        └── .Environment (Menyimpan seluruh namespace)        │
   └──────────────────────────────────────────────────────────────┘
                               │
                      [ PRODUCTION PRUNING ]
                               │
                               ▼
   LEAN PRODUCTION ENGINE ARTIFACT (SLIM)
   ┌──────────────────────────────────────────────────────────────┐
   │ model.production.qs (14 KB)                                  │
   │  ├── $coefficients  (Vektor numerik murni)                  │
   │  ├── $link_inv      (Fungsi inverse-link matematis)          │
   │  ├── $vcov          (p x p covariance matrix untuk CI)       │
   │  └── $feature_names (Vektor string validasi skema)           │
   │  (Environment diputus: environment(terms) <- emptyenv())     │
   └──────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi dan Solusi Lexical Scope Bloat

```R
# simple_leak_demo.R
library(pryr)

simulate_leak <- function() {
  # Simulasi data besar di dalam scope fungsi
  large_payload <- data.frame(matrix(runif(1e7), ncol = 10)) # ~80 MB
  
  # Dataframe kecil untuk pelatihan
  train_df <- data.frame(
    y = rbinom(100, 1, 0.5),
    x1 = rnorm(100),
    x2 = rnorm(100)
  )
  
  # Model dilatih di dalam environment fungsi ini
  fit <- glm(y ~ x1 + x2, data = train_df, family = binomial())
  return(fit)
}

# Model naive
leaky_model <- simulate_leak()

# Simpan ke disk
temp_leaky <- tempfile(fileext = ".rds")
saveRDS(leaky_model, temp_leaky)
cat(sprintf("Ukuran file leaky model: %.2f MB\n", file.info(temp_leaky)$size / 1e6))

# Solusi: Model Pruning Function
prune_glm <- function(model) {
  # 1. Putus lexical environment pada formula dan terms
  model$terms <- terms(model)
  environment(model$terms) <- baseenv()
  environment(model$formula) <- baseenv()
  
  # 2. Hapus data internal yang tidak dibutuhkan untuk inferensi
  model$model <- NULL
  model$data <- NULL
  model$residuals <- NULL
  model$fitted.values <- NULL
  model$effects <- NULL
  model$prior.weights <- NULL
  model$weights <- NULL
  model$linear.predictors <- NULL
  model$y <- NULL
  
  # 3. Minimalkan komponen QR (opsional, pertahankan jika butuh se.fit)
  model$qr$qr <- NULL 
  
  return(model)
}

pruned_model <- prune_glm(simulate_leak())
temp_pruned <- tempfile(fileext = ".rds")
saveRDS(pruned_model, temp_pruned)
cat(sprintf("Ukuran file pruned model: %.2f KB\n", file.info(temp_pruned)$size / 1e3))
```

#### 7.2. Practical Example: Production-Grade Regularized Inference Engine

Kode berikut mendemonstrasikan implementasi GLM termodifikasi dengan dekomposisi matriks terakselerasi, pemangkasan komprehensif, dan *scoring matrix engine* tanpa dependensi S3 predict yang lambat.

```R
# enterprise_inference_engine.R
suppressPackageStartupMessages({
  library(Matrix)
  library(fastglm)
  library(qs)
  library(microbenchmark)
})

# 1. Dataset Generator (Simulasi Credit Risk Scoring)
set.seed(42)
N <- 250000
P <- 20

X_raw <- matrix(rnorm(N * P), nrow = N, ncol = P)
colnames(X_raw) <- paste0("feature_", seq_len(P))
true_beta <- c(runif(P, -1.5, 1.5))
prob <- 1 / (1 + exp(- (X_raw %*% true_beta - 0.5)))
y <- rbinom(N, 1, prob)

# 2. High-Performance Model Fitting (Matrix-based FastGLM)
# Menghindari overhead formula interface base R
cat("[INFO] Fitting model menggunakan fastglm (Eigen-backed)...\n")
start_time <- Sys.time()
fit_fast <- fastglm(
  x = cbind(Intercept = 1, X_raw),
  y = y,
  family = binomial(link = "logit"),
  method = 2 # Dekomposisi Cholesky terakselerasi
)
cat(sprintf("[INFO] Fitting selesai dalam: %.3f detik\n", as.numeric(difftime(Sys.time(), start_time, units = "secs"))))

# 3. Abstraksi Production Inference Object
ProductionGLMEngine <- function(coefficients, vcov_matrix, link_inv_fun, feature_names) {
  structure(
    list(
      coefficients = coefficients,
      vcov_matrix = vcov_matrix,
      link_inv = link_inv_fun,
      feature_names = feature_names,
      version = "1.0.0"
    ),
    class = "ProductionGLMEngine"
  )
}

# Ekstraksi matriks varians-kovarians
V_cov <- vcov(fit_fast)
dimnames(V_cov) <- list(c("Intercept", colnames(X_raw)), c("Intercept", colnames(X_raw)))

prod_engine <- ProductionGLMEngine(
  coefficients = coef(fit_fast),
  vcov_matrix = V_cov,
  link_inv_fun = function(eta) 1 / (1 + exp(-eta)),
  feature_names = colnames(X_raw)
)

# 4. Ultra-Fast Scoring Function (Pure Vectorized Matrix Algebra)
predict_production <- function(engine, new_data_mat, compute_ci = FALSE, alpha = 0.05) {
  # Validasi Kolom
  if (!all(engine$feature_names %in% colnames(new_data_mat))) {
    stop("Input matrix tidak memiliki schema feature yang identik.")
  }
  
  # Susun matriks komputasi dengan Intercept
  X <- cbind(1, new_data_mat[, engine$feature_names, drop = FALSE])
  
  # Score linear predictor: eta = X %*% beta
  eta <- as.vector(X %*% engine$coefficients)
  mu <- engine$link_inv(eta)
  
  if (!compute_ci) {
    return(list(score = mu))
  }
  
  # Standard Error: sqrt(diag(X %*% V %*% t(X))) dioptimasi tanpa menghitung seluruh outer product
  se_eta <- sqrt(rowSums((X %*% engine$vcov_matrix) * X))
  z_crit <- qnorm(1 - alpha / 2)
  
  ci_lower <- engine$link_inv(eta - z_crit * se_eta)
  ci_upper <- engine$link_inv(eta + z_crit * se_eta)
  
  list(score = mu, ci_lower = ci_lower, ci_upper = ci_upper)
}

# 5. Serialisasi Efisien Menggunakan QS
model_path <- tempfile(fileext = ".qs")
qsave(prod_engine, model_path, preset = "archive")
cat(sprintf("[INFO] Ukuran Engine Produksi Tersimpan: %.2f KB\n", file.info(model_path)$size / 1e3))

# 6. Benchmark Kecepatan Inferensi (Batch 1000 Observasi)
batch_test <- X_raw[1:1000, ]
bm <- microbenchmark(
  prod_scoring = predict_production(prod_engine, batch_test, compute_ci = TRUE),
  times = 100L
)
print(summary(bm)[, c("expr", "min", "mean", "median", "max")])
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Institusi FinTech Payment Gateway memproses rata-rata 3.500 transaksi per detik ($N = 3.500 \text{ TPS}$). Setiap transaksi membutuhkan *real-time probability of default / fraud risk score* dalam jendela SLA ketat: **kurang dari 15 milidetik (P99)**, termasuk proses deserialisasi jaringan dan inferensi statistik. Terdapat efek hierarkis temporal karena sifat transaksi yang terkelompokkan berdasarkan *Merchant Category Code* (MCC) dan *Card Issuer*.

#### Solusi Arsitektur
1. **Model**: Menggunakan *Mixed-Effects Logistic Regression* (`glmmTMB`) untuk menangkap variasi acak (*random intercept*) per MCC, kemudian memisahkan estimasi *fixed effects* ($\beta$) dan *Best Linear Unbiased Predictors* (BLUPs, $b_j$) ke dalam tabel referensi cepat (*lookup table* berbasis *in-memory cache* Redis atau R environments).
2. **Scoring Pipeline**: Plumber API multi-instance diatur di belakang Load Balancer (NGINX), dieksekusi secara *stateless* di dalam klaster Kubernetes.

#### Implementasi Layanan (Plumber REST API Endpoint)

```R
# plumber.R
library(plumber)
library(qs)

# Global variables di dalam container (dimuat sekali saat boot)
ENGINE <- NULL

#* @filter cors
function(res) {
  res$setHeader("Access-Control-Allow-Origin", "*")
  plumber::forward()
}

#* @init
function() {
  ENGINE <<- qread("/opt/ml/models/production_glm_engine.qs")
  cat("[BOOT] Production Engine berhasil dimuat ke dalam memori proses worker.\n")
}

#* @post /v1/predict
#* @serializer unboxedJSON
function(req, res) {
  start_proc <- Sys.time()
  
  # 1. Parsing and Defensive Validation
  body <- req$postBody
  if (is.null(body) || nchar(body) == 0) {
    res$status <- 400
    return(list(error = "Request body payload kosong."))
  }
  
  parsed_data <- tryCatch({
    jsonlite::fromJSON(body)
  }, error = function(e) {
    NULL
  })
  
  if (is.null(parsed_data) || !is.data.frame(parsed_data)) {
    res$status <- 422
    return(list(error = "Format payload harus berupa JSON array of objects yang valid."))
  }
  
  # Konversi ke Matrix
  input_mat <- as.matrix(parsed_data)
  
  # 2. Execution Scoring Matrix
  result <- tryCatch({
    pred <- predict_production(
      engine = ENGINE,
      new_data_mat = input_mat,
      compute_ci = FALSE
    )
    
    latency_ms <- as.numeric(difftime(Sys.time(), start_proc, units = "secs")) * 1000
    
    list(
      status = "SUCCESS",
      predictions = pred$score,
      latency_ms = round(latency_ms, 2)
    )
  }, error = function(e) {
    res$status <- 500
    list(status = "INFERENCE_ERROR", message = e$message)
  })
  
  return(result)
}

#* @get /health
function() {
  list(status = "HEALTHY", timestamp = Sys.time())
}
```

#### Container Dockerfile Produksi

```dockerfile
# Multi-stage optimized enterprise Dockerfile
FROM rocker/r-ver:4.3.2 AS base

# Install OS dependencies untuk kompilasi C++ / LAPACK
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install R packages layer
RUN R -e "install.packages(c('plumber', 'qs', 'fastglm', 'Matrix', 'jsonlite'), repos='https://cloud.r-project.org/')"

# Salin artifak model dan script
COPY production_glm_engine.qs /opt/ml/models/production_glm_engine.qs
COPY plumber.R /app/plumber.R

EXPOSE 8080

# Jalankan worker Plumber
ENTRYPOINT ["R", "-e", "pr <- plumber::plumb('/app/plumber.R'); pr$run(host='0.0.0.0', port=8080)"]
```

---

### 9. Trade-offs

| Pendekatan / Algoritma | Keuntungan (*Pros*) | Kerugian / Risiko (*Cons*) | Memory Complexity | Latency SLA Impact | Cost Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard Base `glm()` Object** | Fitur diagnostik lengkap, inferensi inferensial otomatis via `summary()`. | Membawa *lexical scope*, overhead memori masif, lambat untuk scoring. | $O(N \times P)$ (Sangat boros) | Buruk ($> 50 \text{ ms}$) | Membutuhkan RAM instance cloud lebih tinggi. |
| **Stripped Array-Based Engine** | Ringan (< 50 KB), zero lexical leaks, eksekusi setara native C++. | Kehilangan metadata residual, tidak bisa menjalankan `plot()` atau S3 standard post-fit. | $O(P)$ untuk weights | Ultra Rendah ($< 2 \text{ ms}$) | Biaya server minimum (hemat hingga 80% RAM). |
| **Sparse Matrix Input (`dgCMatrix`)** | Memungkinkan komputasi fitur kategorikal besar tanpa OOM. | Operasi slicing dan indexing sparse matrix memiliki sedikit CPU overhead pada batch kecil. | $O(\text{nnz})$ (proporsional thd *non-zero elements*) | Rendah ($< 5 \text{ ms}$) | Mengurangi alokasi memori secara drastis pada data jarang. |
| **Full Laplace GLMM (`glmmTMB`)** | Menangkap korelasi hierarkis grup secara akurat. | Komputasi random effects berdimensi besar berat; scoring perlu lookup table. | $O(P + J \times K)$ ($J$ groups, $K$ random terms) | Sedang ($10 - 25 \text{ ms}$) | Membutuhkan CPU tinggi saat training; ringan saat scoring via caching. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: Quasi-Complete Separation pada Regresi Logistik
* **Gejala**: Parameter $\beta$ meledak ke angka ekstrem ($> 50$ atau $< -50$), standar error bernilai sangat besar (`Inf` atau ribuan), dan muncul warning: `glm.fit: fitted probabilities numerically 0 or 1 occurred`.
* **Akar Masalah**: Suatu prediktor secara sempurna membagi label $Y = 1$ dan $Y = 0$. Log-likelihood mencapai asimtot tak terhingga sehingga konvergensi numerik gagal.
* **Solusi Enterprise**: Gunakan penalti *Firth's Penalized Likelihood* (`logistf`) atau regularisasi Ridge (L2 penalty) via `glmnet` dengan $\alpha = 0$ dan $\lambda$ kecil:
  ```R
  # Solusi: Ridge Penalization Fallback
  library(glmnet)
  fit_ridge <- glmnet(X, y, family = "binomial", alpha = 0, lambda = 1e-4)
  ```

#### 2. Masalah: Objek Model Menggelembung Saat Disimpan (RDS File Bloat)
* **Gejala**: File model `.rds` berukuran ratusan megabyte padahal hanya melatih model dari data beberapa ribu baris.
* **Akar Masalah**: Formula `formula(y ~ .)` mengunci `.GlobalEnv` atau execution context yang memuat objek-objek besar lainnya.
* **Solusi Defensif**:
  ```R
  strip_formula_env <- function(f) {
    environment(f) <- emptyenv()
    f
  }
  # Putuskan environment sebelum objek disimpan
  environment(model$terms) <- emptyenv()
  ```

#### 3. Masalah: Kolom Baru Berubah Level pada Data Kategorikal (*Factor Mismatch*)
* **Gejala**: Pada sistem inferensi produksi, fungsi `predict()` melempar error: `factor X has new levels` atau koefisien bergeser karena pengurutan kolom matriks tidak konsisten.
* **Akar Masalah**: Representasi one-hot encoding dilakukan secara implisit tanpa *schema reference*.
* **Solusi Defensif**: Simpan vektor eksplisit seluruh feature columns dan implementasikan *matrix alignment guard*:
  ```R
  align_matrix_columns <- function(new_mat, reference_cols) {
    missing_cols <- setdiff(reference_cols, colnames(new_mat))
    if (length(missing_cols) > 0) {
      zero_mat <- matrix(0, nrow = nrow(new_mat), ncol = length(missing_cols))
      colnames(zero_mat) <- missing_cols
      new_mat <- cbind(new_mat, zero_mat)
    }
    # Kembalikan urutan kolom identik sesuai reference_cols
    new_mat[, reference_cols, drop = FALSE]
  }
  ```

---

### 11. Best Practices (Production Checklist)

| Kategori | Item Checklist | Status Validasi |
| :--- | :--- | :--- |
| **Arsitektur Model** | Objek model telah dipangkas dari `residuals`, `model`, `fitted.values`, dan `prior.weights`. | [ ] Wajib |
| **Arsitektur Model** | Environment pada `terms` dan `formula` disetel ke `emptyenv()` atau `baseenv()`. | [ ] Wajib |
| **Stabilitas Numerik** | Dilakukan validasi matriks singular via `rcond()` sebelum melakukan inversi atau Cholesky. | [ ] Wajib |
| **Stabilitas Numerik** | Regularisasi diaktifkan untuk prediktor berkorelasi tinggi ($> 0.85$) untuk mencegah matrix degradation. | [ ] Rekomendasi |
| **Serialisasi** | File model dikompresi menggunakan library `qs` (bukan default `saveRDS()`) untuk I/O latensi rendah. | [ ] Wajib |
| **REST API** | API memiliki endpoint `/health` statis yang merespons status container tanpa alokasi memori. | [ ] Wajib |
| **REST API** | Terdapat error handling komprehensif (`tryCatch`) di seluruh blok input parsing untuk mengisolasi kegagalan worker. | [ ] Wajib |
| **Monitoring** | Metrik *scoring latency* dan deviasi distribusi prediksi (drift) dipantau ke logging standard (JSON logging). | [ ] Rekomendasi |

---

### 12. Hands-on Practice

Ikuti langkah-langkah di bawah ini untuk membangun sistem pelatihan model inferensial dan deployment API produksi. Simpan seluruh file di direktori: `hands-on/m02/`.

```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Langkah 1: Buat Script Pelatihan dan Ekspor Model (`train_and_export.R`)

```R
# hands-on/m02/train_and_export.R
suppressPackageStartupMessages({
  library(fastglm)
  library(qs)
})

cat("[1/4] Menggenerasi dataset sintetis...\n")
set.seed(123)
n_train <- 100000
p <- 15

X <- matrix(rnorm(n_train * p), nrow = n_train, ncol = p)
feature_names <- sprintf("var_%02d", 1:p)
colnames(X) <- feature_names

beta_true <- c(0.2, runif(p, -0.8, 0.8))
X_with_intercept <- cbind(Intercept = 1, X)
logit_p <- as.vector(X_with_intercept %*% beta_true)
prob <- 1 / (1 + exp(-logit_p))
y <- rbinom(n_train, 1, prob)

cat("[2/4] Melatih High-Speed GLM...\n")
model <- fastglm(
  x = X_with_intercept,
  y = y,
  family = binomial(link = "logit"),
  method = 2
)

cat("[3/4] Membangun objek produksi lean...\n")
# Ekstraksi komponen esensial saja
lean_engine <- list(
  coefficients = coef(model),
  vcov = vcov(model),
  feature_names = feature_names,
  family = "binomial",
  link = "logit"
)

cat("[4/4] Menyimpan model via QS engine...\n")
qsave(lean_engine, "lean_glm_model.qs", preset = "archive")
cat("SUCCESS: Model tersimpan di hands-on/m02/lean_glm_model.qs\n")
```

#### Langkah 2: Buat Controller Plumber REST API (`api.R`)

```R
# hands-on/m02/api.R
library(plumber)
library(qs)

# Inisialisasi model di level global
MODEL <- qread("lean_glm_model.qs")

#* @apiTitle Production GLM Scoring Engine
#* @apiDescription Layanan inferensi statistik latensi rendah.

#* @get /health
#* @serializer unboxedJSON
function() {
  list(status = "UP", timestamp = Sys.time())
}

#* @post /score
#* @serializer unboxedJSON
function(req, res) {
  payload <- jsonlite::fromJSON(req$postBody)
  
  if (!is.data.frame(payload)) {
    res$status <- 400
    return(list(error = "Payload harus berupa data frame valid."))
  }
  
  # Validasi kolom hilang
  missing <- setdiff(MODEL$feature_names, colnames(payload))
  if (length(missing) > 0) {
    res$status <- 422
    return(list(error = paste("Feature berikut tidak ditemukan:", paste(missing, collapse = ", "))))
  }
  
  # Rekayasa input matriks
  X_in <- as.matrix(payload[, MODEL$feature_names, drop = FALSE])
  X_full <- cbind(1, X_in)
  
  # Linear combination: eta = X %*% beta
  eta <- as.vector(X_full %*% MODEL$coefficients)
  
  # Inverse link (Logit)
  prob <- 1 / (1 + exp(-eta))
  
  list(
    count = length(prob),
    probabilities = round(prob, 5)
  )
}
```

#### Langkah 3: Eksekusi dan Verifikasi API

Jalankan API dari terminal:

```bash
R -e "pr <- plumber::plumb('api.R'); pr$run(port = 8989)"
```

Uji menggunakan `curl` pada jendela terminal terpisah:

```bash
# Health check
curl -X GET http://localhost:8989/health

# Post test data untuk prediksi
curl -X POST http://localhost:8989/score \
  -H "Content-Type: application/json" \
  -d '[
    {"var_01":0.1, "var_02":-0.5, "var_03":1.2, "var_04":0.0, "var_05":-0.1, "var_06":0.8, "var_07":-0.3, "var_08":0.4, "var_09":-1.1, "var_10":0.2, "var_11":-0.7, "var_12":0.5, "var_13":0.3, "var_14":-0.2, "var_15":0.1}
  ]'
```

---

### 13. Exercise

#### Level 1 (Easy)
Diberikan model standar `fit <- glm(mpg ~ wt + hp, data = mtcars)`. Tulis fungsi R yang mengekstraksi parameter koefisien dan menghitung inferensi prediksi secara manual untuk observasi baru (`wt = 3.2`, `hp = 110`) menggunakan aljabar vektor dot-product ($X\beta$), tanpa menggunakan fungsi bawaan `predict()`. Bandingkan hasilnya dengan `predict(fit, newdata = ...)`.

#### Level 2 (Medium)
Bangun fungsi diagnostik matriks numerik `validate_matrix_stability(X)` yang menerima matriks data $X$. Fungsi harus:
1. Memeriksa korelasi antar fitur (Pearson correlation matrix).
2. Menghitung *Condition Number* menggunakan metode rasio *singular values* terkecil dan terbesar via `svd()`.
3. Mengembalikan status boolean: `TRUE` jika matriks stabil numerik ($\kappa < 30$), atau `FALSE` jika matriks terindikasi multikolinearitas parah beserta saran kolom yang harus didrop.

#### Level 3 (Hard)
Kembangkan sistem inferensi berbasis `Rcpp` atau implementasi perkalian matriks paralel yang menghitung *Prediction Confidence Interval* $95\%$ secara instan untuk $100.000$ baris data secara simultan:

$$\hat{\eta} \pm 1.96 \times \sqrt{\operatorname{diag}(X V X^T)}$$

*Syarat*: Anda **dilarang keras** mengalokasikan matriks berukuran $N \times N$ hasil dari $(X V X^T)$ karena akan memicu crash memori (RAM exhaustion). Anda harus menghitung komponen diagonalnya menggunakan perkalian baris element-wise (*row-wise dot product*).

---

### 14. Challenge

**Skenario**: Anda adalah Principal Quantitative Infrastructure Engineer di sebuah bursa perdagangan valuta asing. Sistem Anda menerima sinyal pasar berdimensi tinggi ($P = 200$ variabel kontinu) dengan frekuensi tinggi. 
- Karena volatilitas pasar yang dinamis, struktur kovarians antardata mengalami pergeseran (*concept/covariate drift*).
- Setiap 10 menit, model Generalized Linear Model harus di-*retrain* secara asinkron menggunakan 1.000.000 baris data terbaru tanpa mengganggu proses inferensi transaksi yang sedang berjalan (zero-downtime hot reloading).
- Proses inferensi memiliki batasan waktu komputasi maksimal 8 milidetik per 500 records.

**Tantangan**:
Rancang arsitektur sistem menggunakan R yang memisahkan proses *Trainer Worker* dan *Scoring Engine Worker*. Terapkan mekanisme *memory-mapped files* (`mmap` / `bigstatsr`) atau *atomic pointer swapping* dalam memori bersama (*shared memory*) sehingga model yang baru selesai dilatih dapat langsung dibaca oleh scoring engine tanpa memutus sesi TCP/HTTP yang sedang berjalan dan tanpa lonjakan alokasi memori heap R. Uraikan arsitektur lengkap beserta kode fondasi sinkronisasi model tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Algoritma numerik apa yang secara default digunakan oleh R dalam fungsi `lm.fit` untuk menyelesaikan regresi linier?
   - A. Inversi Matriks Gauss-Jordan
   - B. Dekomposisi QR via LAPACK
   - C. Gradient Descent Stochastic
   - D. LU Decomposition

2. Mengapa menyimpan objek model GLM mentah menggunakan `saveRDS()` berisiko menimbulkan *memory bloat* di lingkungan produksi?
   - A. Format `.rds` tidak mendukung kompresi biner.
   - B. Objek formula pada R mengunci *environment* pemanggilnya dan menyerialisasi seluruh variabel yang ada di dalamnya.
   - C. R mengubah seluruh float menjadi string karakter saat serialisasi.
   - D. Driver storage R selalu memformat ulang file ke ukuran block minimum 1 GB.

3. Pada algoritma *Iteratively Reweighted Least Squares* (IRLS), apa tujuan dari matriks bobot $W^{(t)}$?
   - A. Sebagai penalti L1 regularisasi (Lasso).
   - B. Untuk menyesuaikan varians variabel dependen kerja yang bervariasi bergantung pada nilai ekspektasi $\mu$.
   - C. Untuk menghapus *outliers* secara otomatis pada setiap iterasi.
   - D. Menstabilkan nilai *eigenvalue* yang negatif menjadi definit positif.

4. Manakah komponen di dalam struktur model S3 `glm` yang aman untuk dihapus tanpa memutus kemampuan menghitung nilai prediksi $\mu$?
   - A. `$coefficients`
   - B. `$family$linkinv`
   - C. `$residuals` dan `$fitted.values`
   - D. `$rank`

5. Kondisi apa yang ditandai dengan meledaknya nilai standar error koefisien menjadi sangat besar pada estimasi Logistic Regression?
   - A. Homoskedastisitas
   - B. Quasi-complete separation
   - C. Heteroskedastisitas
   - D. Overdispersion ringan

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Bagaimana cara paling efisien menghitung nilai varians prediksi $\operatorname{Var}(\hat{\eta}) = \operatorname{diag}(X V X^T)$ untuk $N$ baris observasi besar tanpa membuat matriks perantara $N \times N$?
   - A. `diag(X %*% V %*% t(X))`
   - B. `rowSums((X %*% V) * X)`
   - C. `apply(X, 1, function(r) r %*% V %*% r)`
   - D. `as.vector(X %*% diag(V) %*% t(X))`

7. Apa tujuan utama menetapkan `environment(model$terms) <- baseenv()` sebelum serialisasi model?
   - A. Agar model dapat dieksekusi lebih cepat pada arsitektur prosesor ARM.
   - B. Memutus referensi ke lexical environment tempat model dilatih sehingga memori induk tidak terbawa.
   - C. Memaksa kompilasi JIT (Just-In-Time) pada fungsi prediksi.
   - D. Menjamin nilai koefisien tidak berubah menjadi nol secara spontan.

8. Bila matriks prediktor $X$ memiliki *condition number* $\kappa(X) = 10^{14}$, masalah numerik apa yang akan terjadi saat menghitung estimasi parameter?
   - A. Estimasi menjadi bias namun standar error tetap minimum.
   - B. Terjadi pembatalan katastropik (*catastrophic cancellation*) dan galat pembulatan drastis pada inversi matriks.
   - C. Iterasi IRLS akan langsung konvergen pada iterasi pertama.
   - D. Algoritma QR akan menolak eksekusi dan mematikan sistem operasi.

9. Mengapa format serialisasi `qs` lebih disukai dibandingkan `saveRDS` standar pada arsitektur microservice berlatensi tinggi?
   - A. `qs` tidak mendukung tipe data list R.
   - B. `qs` ditulis dalam C++ modern dengan algoritma kompresi Zstandard multi-threaded yang jauh lebih cepat dalam deserialisasi.
   - C. `qs` mengenkripsi data secara otomatis menggunakan SHA-256.
   - D. File `qs` dapat langsung dibaca oleh server Apache HTTP tanpa R runtime.

10. Pada model *Mixed-Effects* (`glmmTMB` / `lme4`), pendekatan apa yang umum digunakan untuk mengaproksimasi integrasi marginal atas efek acak (*random effects*)?
    - A. Aproksimasi Laplace
    - B. Dekomposisi Singular Value (SVD)
    - C. Transformasi Fourier Cepat
    - D. Runge-Kutta Orde 4

#### Bagian 3: Skenario Kasus Produksi (Analisis & Solusi)
11. **Kasus 1**: Sistem Plumber API Anda mengalami *restart* otomatis secara berkala karena *Out-Of-Memory* (OOM) setiap kali menerima lonjakan beban traffic batch scoring (100.000 baris JSON). Analisis profil memori menunjukkan konsumsi RAM melonjak hingga 4 GB lalu container mati, padahal ukuran payload JSON hanya sebesar 20 MB. Bagian mana dari siklus pemrosesan data R yang paling mungkin memicu alokasi memori masif ini, dan bagaimana strategi rekayasa untuk memperbaikinya?
12. **Kasus 2**: Sebuah model regresi logistik yang dilatih secara mingguan tiba-tiba menghasilkan output skor probabilitas yang identik seragam ($0.5000$) untuk seluruh pengguna baru di sistem produksi, tanpa melempar error atau exception apapun pada log sistem. Langkah-langkah forensik apa yang harus Anda lakukan untuk melacak sumber akar permasalahan ini pada pipeline inferensi?
13. **Kasus 3**: Anda diminta mendesain *Zero-Downtime Hot Reloading Architecture* untuk model R berukuran 500 MB di klaster Kubernetes. Bagaimana Anda memastikan worker Plumber yang sedang memproses request aktif tidak mengalami korupsi data (*race condition*) ketika file model di-update dengan versi yang baru?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Pilihan Ganda
1. **B** — R menggunakan rutin FORTRAN/C `dqrls` yang berbasis dekomposisi QR untuk menjamin kestabilan numerik.
2. **B** — Formula R membawa closure environment lengkap yang mereferensikan seluruh objek data di lingkungan eksekusi pembuatan model.
3. **B** — IRLS menyesuaikan bobot secara dinamis karena pada GLM, varians merupakan fungsi dari mean ($V(\mu)$).
4. **C** — Residuals dan fitted values adalah artifak pasca-latih yang tidak diperlukan untuk menghitung proyeksi data baru $X\beta$.
5. **B** — Quasi-complete separation terjadi ketika prediktor memisahkan target secara deterministik sempurna, mendorong logit menuju tak hingga.
6. **B** — Operasi `rowSums((X %*% V) * X)` memanfaatkan sifat aljabar perkalian Hadamard tereduksi, menghindari komputasi dan alokasi matriks perantara berukuran $N \times N$.
7. **B** — Memutus referensi ke lexical scope lama ke namespace kosong (`baseenv` / `emptyenv`) membebaskan garbage collector dari membawa pointer induk.
8. **B** — Condition number yang sangat tinggi ($> 10^{12}$) mendekati batasan presisi ganda IEEE 754 ($10^{-16}$), menyebabkan dekomposisi matriks menghasilkan galat numerik ekstrem.
9. **B** — Library `qs` didesain khusus untuk pertukaran data latensi rendah menggunakan optimasi buffer C++ dan kompresi Zstd/LZ4.
10. **A** — Aproksimasi Laplace mengevaluasi integral likelihood di sekitar mode efek acak menggunakan ekspansi deret Taylor orde kedua.

#### Panduan Solusi Skenario Kasus Produksi
11. **Analisis Kasus 1**:
    - *Akar Masalah*: Fungsi deserialisasi JSON default (`jsonlite::fromJSON`) saat mengurai array besar mengalokasikan banyak objek perantara di memori heap R. Selanjutnya, konversi `data.frame` ke matriks atau penggunaan fungsi bawaan `model.matrix()` melakukan duplikasi memori bertingkat hingga 10-20 kali lipat ukuran payload mentah.
    - *Solusi*: Terapkan *chunk-based streaming inference* (misalnya membagi request ke dalam mikro-batch berukuran 5.000 baris) atau gunakan pipeline berbasis sparse matrix streaming (`bigmemory` / `Matrix`). Matikan pembentukan formula environment dan gunakan operasi perkalian matriks linear langsung.
12. **Analisis Kasus 2**:
    - *Akar Masalah*: Fenomena ini biasanya disebabkan oleh pergeseran urutan kolom atau hilangnya intercept/skala fitur, yang menyebabkan hasil perkalian dot-product linear predictor $\eta = X\beta$ bernilai $0$ (sehingga $\text{logit}^{-1}(0) = \frac{1}{1 + e^{-0}} = 0.5$). Ini bisa terjadi jika nama kolom payload baru tidak cocok sehingga fallback mengisi matriks dengan nilai 0, atau koefisien model tertukar urutannya dengan data input.
    - *Langkah Forensik*: 
      1. Periksa nilai mentah dari vektor $\eta$ (*linear predictor*) sebelum dilewatkan ke fungsi inverse link.
      2. Validasi kecocokan urutan nama kolom (`colnames(X)`) dengan urutan nama koefisien (`names(beta)`).
      3. Periksa distribusi imputasi nilai default pada parsing JSON.
13. **Kasus 3**:
    - *Arsitektur Hot Reloading*: Terapkan pola *Blue-Green Deployment* atau *Rolling Update* di level Pod Kubernetes (bukan me-reload model di dalam single R process yang sedang hidup). 
    - Jika harus diselesaikan di dalam proses R yang sama: Terapkan abstraksi *Pointer Swapping Atomic* melalui R Environment. Muat model baru ke dalam environment sementara yang terisolasi (`env_new`). Setelah deserialisasi sukses $100\%$ dan lolos uji integritas (sanity prediction check), lakukan swap pointer referensi model global: `MODEL_ACTIVE <<- env_new$MODEL`. Garbage collection R akan secara aman membersihkan memori model lama hanya setelah semua request yang sedang menggunakannya selesai dieksekusi.

---

### 16. Summary

1. **Efisiensi Numerik**: Penggunaan aljabar linier terakselerasi melalui dekomposisi QR dan dekomposisi Cholesky adalah fondasi utama inferensi enterprise di R. Hindari inversi matriks langsung $(X^T X)^{-1}$.
2. **Lexical Scope Sanitization**: Objek formula R menyimpan referensi tersembunyi ke memori pemanggilnya. Pembersihan atribut lingkungan (`environment(terms) <- baseenv()`) dan pembuangan artifak non-esensial (`residuals`, `fitted.values`) adalah syarat mutlak mencegah insiden kebocoran memori (OOM) di produksi.
3. **Inference Latency Optimization**: Jangan pernah menggunakan fungsi S3 `predict.glm()` standar pada API endpoint berlatensi tinggi. Gantilah dengan fungsi perkalian matriks vektor langsung ($X\beta$) yang dieksekusi melalui pustaka teroptimasi atau ekstensi C++ (`RcppEigen`), memangkas latensi dari puluhan milidetik menjadi sub-milidetik.
4. **Production Delivery Stack**: Kombinasi format biner terkompresi `qs`, microservice REST API `plumber`, dan kontainerisasi Docker menghasilkan sistem inferensi statistik R yang stateless, deterministik, aman, dan dapat diskalakan secara horizontal (*cloud-native autoscaling*).