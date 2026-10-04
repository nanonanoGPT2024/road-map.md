# BAB 08: Rekayasa Machine Learning Modern
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal Ekosistem Tidymodels:** Menguasai mekanisme internal `recipes`, `workflows`, dan evaluasi komputasi berbasis S3/vctrs untuk mencegah *data leakage*.
- **Membangun Pipeline ML Enterprise:** Mengimplementasikan orkestrasi pemodelan terdistribusi menggunakan `future`, `tune`, dan `finetune` dengan alokasi resource memori yang deterministik.
- **Mengemas dan Menyimpan Artefak Model Secara Imutabel:** Memanfaatkan library `bundle`, `vetiver`, dan `pins` untuk memisahkan *environment state* dari artefak inferensi guna eliminasi bloat memori.
- **Mengembangkan REST API High-Throughput:** Mentranslasikan artefak model menjadi microservice menggunakan `plumber`, dikombinasikan dengan strategi konkurensi (multi-process workers) berbasis Docker.
- **Mengimplementasikan Monitoring Data & Model Drift:** Membangun *statistical surveillance pipeline* berbasis divergensi Kullback-Leibler dan Kolmogorov-Smirnov test untuk mendeteksi degradasi performa model di produksi.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Tingkat Lanjut Bahasa R:** Pemrograman berorientasi objek (S3/R6), manipulasi data menggunakan `data.table` dan `dplyr`, serta functional programming dengan `purrr`.
- **R Engine Internals:** Alokasi memori R (Copy-on-Modify semantics, *environments*, garbage collector `gc()`).
- **Prinsip Machine Learning:** Konsep bias-variance trade-off, cross-validation, regularization, tree-based models (XGBoost/LightGBM), hyperparameter optimization.
- **Infrastruktur Dasar:** Docker containerization, REST protocol, POSIX system calls, dan basic cloud storage architectures (AWS S3/GCS/MinIO).

---

### 3. Concept & Internal Architecture

Ekosistem *legacy* Machine Learning di R (seperti package `caret` atau model individual seperti `randomForest` dan `e1071`) memiliki kelemahan mendasar pada level arsitektur: ketidakkonsistenan antarmuka prediktor (`predict.lm` menghasilkan vector, `predict.lda` menghasilkan list), *memory bloat* karena enkapsulasi objek formula yang menangkap *enclosing environment*, serta rentannya pipeline terhadap *data leakage* selama feature engineering.

Modern R Machine Learning merevolusi pendekatan ini melalui **Tidymodels Engine Architecture**:

```
[Raw Data] 
    │
    ▼
[recipes Engine] ──(Prep: Estimasi Statistik Training)──► [Trained Recipe Object]
    │                                                               │
    └───(Bake: Transformasi Deterministik)──────────────────────────┤
                                                                    ▼
                                                            [Workflow State]
                                                                    │
                                                        [parsnip Unified Engine]
                                                                    │
                                                        [Bundle Stripping Phase]
                                                                    │
                                                            [Vetiver Model]
                                                                    │
                                            ┌───────────────────────┴───────────────────────┐
                                            ▼                                               ▼
                                  [pins Artifact Store]                           [Plumber API Engine]
```

#### Mekanisme `recipes`: Prep vs. Bake
`recipes` memisahkan blueprint transformasi data menjadi dua fase:
1. **`prep()`:** Menghitung parameter statistik (misal: mean, standard deviation, PCA eigenvectors, imputation medians) *hanya* dari training partition. Objek `recipe` yang telah di-`prep` menyimpan matriks/vektor parameter ringkasan ke dalam struktur S3 tanpa memuat ulang data mentah asli (`retain = FALSE`).
2. **`bake()`:** Menerapkan transformasi deterministik pada data baru (validation, test, atau live production payload) berdasarkan parameter yang telah dihitung saat `prep()`. Ini menjamin tidak ada kalkulasi statistik global yang bocor dari test partition ke training partition.

#### Memory Management & Environment Stripping
Secara default, formula di R (misal: `y ~ x1 + x2`) mengikat *enclosing environment* tempat formula tersebut dideklarasikan. Jika formula dideklarasikan di dalam global environment yang memuat dataframe sebesar 10 GB, maka fungsi seperti `lm()` atau model wrapper konvensional akan memegang pointer ke environment tersebut. Akibatnya, saat model diserialisasi via `saveRDS()`, seluruh environment 10 GB ikut tersimpan ke dalam disk.

Package `bundle` memutus dependensi ini dengan cara:
- Menghapus referensi parent environment pada objek formula dan function closures.
- Mengekstrak raw underlying model matrix/pointers (misal: C++ pointer pada `xgb.Booster`).
- Mengemas objek menjadi standalone bundle yang hanya berisi bobot inferensi murni.

#### Serving Layer: Vetiver & Plumber
Model yang dibungkus menggunakan `vetiver` secara otomatis mengkapsulasi metadata input prototype (tipe data dan skema via package `vctrs`). Ketika dideploy ke `plumber`, vetiver memvalidasi setiap payload JSON yang masuk terhadap skema prototype ini sebelum diserahkan ke C++ execution engine dari underlying model.

---

### 4. Why & What

| Fitur | Legacy R ML (`caret`, script manual) | Modern Enterprise R (`tidymodels`, `vetiver`) |
| :--- | :--- | :--- |
| **Pencegahan Leakage** | Manual; rentan bocor saat normalisasi pra-split. | Struktural; blueprint terpisah antara `prep()` dan `bake()`. |
| **API Interface** | Beragam (`predict()`, `predict.model()`, format matrix vs data.frame). | Universal; `parsnip` selalu mengembalikan `tibble` dengan kolom terstandardisasi. |
| **Model Serialization** | `saveRDS()` mentah; membawa *bloated environments*. | `bundle` + `vetiver`; artefak ramping, reproducibly isolated. |
| **Serving Runtime** | Script Plumber kustom tanpa validasi payload ketat. | Auto-generated endpoint dengan runtime schema validation via `vctrs`. |
| **Observability** | Script monitoring terpisah tanpa metadata tracking. | Integrasi `pins` versioning + tracking metrik drift real-time. |

---

### 5. How: Workflow Detail

Arsitektur produksi machine learning modern R mengikuti siklus 6 tahap:
1. **Ingestion & Validation:** Membaca data partisi via Apache Arrow (`arrow::open_dataset()`), memvalidasi tipe data schema strict.
2. **Pre-processing Recipe Design:** Menyusun graph transformasi deterministik (imputasi, encoding, normalisasi) menggunakan `recipes`.
3. **Hyperparameter Optimization Engine:** Eksekusi tuning paralel melalui `tune` dan `future` cluster workers dengan cross-validation strata.
4. **Finalization & Bundling:** Ekstraksi best hyperparameter set, fit pada seluruh training partition, strip environment bloat menggunakan `bundle()`.
5. **Deployment:** Pendaftaran model ke Pin Board (S3 bucket), generate service API menggunakan `plumber` dan `vetiver`.
6. **Drift Surveillance:** Cron background worker yang menghitung matriks divergensi populasi untuk fitur dan residual model.

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah lini manufaktur mobil:
- **`recipes`** adalah cetakan pabrik. `prep()` adalah tahap pengukuran cetakan berdasarkan prototipe pertama (training data). `bake()` adalah proses mencetak lempengan baja mobil massal (test/production data) mengikuti ukuran cetakan yang sudah pasti.
- **`parsnip`** adalah universal power socket. Anda dapat mengganti bor listrik dari merek Bosch ke Makita (misal: engine `ranger` ke `randomForest`) tanpa mengubah colokan listrik pada dinding.
- **`bundle` & `vetiver`** adalah inspeksi kargo ekspor. Sebelum mobil dikirim ke luar negeri, semua sampah pabrik, perkakas teknisi, dan barang sisa (enclosing R environment) dibersihkan total dari dalam mobil, menyisakan mobil siap pakai yang ramping dan aman.

```
       TUNING & ORCHESTRATION ARCHITECTURE (PRODUCTION MULTI-WORKER)
       
 ┌─────────────────────────────────────────────────────────────┐
 │                      arrow Dataset                          │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Stratified Split
                ┌───────────────┴───────────────┐
                ▼                               ▼
       [Analysis Split]                [Assessment Split]
                │                               │
        recipe::prep()                          │
                │                               │
                ▼                               ▼
        recipe::bake()                  recipe::bake()
                │                               │
                └───────────────┬───────────────┘
                                ▼
         ┌─────────────────────────────────────────────┐
         │       tune_grid() via future::plan()        │
         │  ┌───────────┐ ┌───────────┐ ┌───────────┐  │
         │  │ Worker 01 │ │ Worker 02 │ │ Worker 03 │  │
         │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  │
         └────────┼─────────────┼─────────────┼────────┘
                  └─────────────┼─────────────┘
                                ▼
                     workflows::finalize()
                                │
                                ▼
                       bundle::bundle()
                                │
                                ▼
                      vetiver::vetiver_model()
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [AWS S3 via pins]                [Plumber REST Microservice]
                                                 │
                                                 ▼
                                        Docker Multi-Worker 
                                        (Gunicorn / Rscript pool)
```

---

### 7. Code Implementation: Production Standard

#### Skenario: Prediksi Probabilitas Default Kartu Kredit High-Throughput
Implementasi berikut menggunakan `tidymodels`, `xgboost`, `bundle`, `vetiver`, dan `plumber` dengan standar rekayasa perangkat lunak enterprise.

##### File: `train_and_bundle.R`
```R
#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tidymodels)
  library(xgboost)
  library(bundle)
  library(vetiver)
  library(pins)
  library(arrow)
  library(future)
})

set.seed(42)

# 1. Pipeline Logging Setup
log_info <- function(msg) {
  cat(sprintf("[%s] [INFO] %s\n", format(Sys.time(), "%Y-%m-%d %H:%M:%OS3"), msg))
}

# 2. Simulasi Dataset Transaksi Kredit (Enterprise Context)
generate_synthetic_credit_data <- function(n_rows = 50000) {
  tibble::tibble(
    transaction_id = uuid::UUIDgenerate(n = n_rows),
    loan_amount    = runif(n_rows, 1000, 50000),
    interest_rate  = runif(n_rows, 5.0, 28.5),
    annual_income  = rlnorm(n_rows, meanlog = 10.5, sdlog = 0.75),
    debt_to_income = runif(n_rows, 0.01, 0.65),
    delinq_2yrs    = rpois(n_rows, lambda = 0.3),
    home_ownership = sample(c("RENT", "OWN", "MORTGAGE"), n_rows, replace = TRUE, prob = c(0.4, 0.1, 0.5)),
    default_flag   = factor(
      rbinom(n_rows, size = 1, prob = 0.12),
      levels = c(1, 0),
      labels = c("default", "current")
    )
  )
}

log_info("Generating dataset partitions...")
raw_data <- generate_synthetic_credit_data(25000)

# 3. Stratified Partitioning
data_split <- initial_split(raw_data, prop = 0.80, strata = default_flag)
train_df   <- training(data_split)
test_df    <- testing(data_split)

# 4. Recipe Engineering (Strict Data Leakage Prevention)
credit_recipe <- recipe(default_flag ~ ., data = train_df) %>%
  update_role(transaction_id, new_role = "id_variable") %>%
  step_novel(all_nominal_predictors()) %>%
  step_unknown(all_nominal_predictors()) %>%
  step_dummy(all_nominal_predictors(), one_hot = TRUE) %>%
  step_zv(all_predictors()) %>%
  step_normalize(all_numeric_predictors())

# 5. Parsnip Model Specification with Engine Parameters
xgb_spec <- boost_tree(
  trees          = tune(),
  tree_depth     = tune(),
  learn_rate     = tune(),
  loss_reduction = tune()
) %>%
  set_engine("xgboost", nthread = 1, tree_method = "hist") %>%
  set_mode("classification")

# 6. Workflow Composition
credit_workflow <- workflow() %>%
  add_recipe(credit_recipe) %>%
  add_model(xgb_spec)

# 7. Cross-Validation & Parallel Tuning Setup
cv_folds <- vfold_cv(train_df, v = 5, strata = default_flag)

xgb_grid <- grid_latin_hypercube(
  trees(range = c(100, 500)),
  tree_depth(range = c(3, 8)),
  learn_rate(range = c(-3, -1), trans = log10_trans()),
  loss_reduction(range = c(-2, 1), trans = log10_trans()),
  size = 8
)

log_info("Executing hyperparameter optimization via future workers...")
plan(multisession, workers = 2)

tune_results <- tune_grid(
  credit_workflow,
  resamples = cv_folds,
  grid      = xgb_grid,
  metrics   = metric_set(roc_auc, pr_auc),
  control   = control_grid(save_pred = FALSE, parallel_over = "resamples")
)

plan(sequential) # Reset parallel backend

# 8. Model Finalization
best_params <- select_best(tune_results, metric = "pr_auc")
log_info(sprintf("Best Tuning Result: trees=%d, depth=%d, lr=%.5f", 
                 best_params$trees, best_params$tree_depth, best_params$learn_rate))

final_workflow <- finalize_workflow(credit_workflow, best_params)
fitted_workflow <- fit(final_workflow, data = train_df)

# 9. Out-of-Sample Evaluation
test_predictions <- predict(fitted_workflow, new_data = test_df, type = "prob") %>%
  bind_cols(test_df %>% select(default_flag, transaction_id))

auc_score <- roc_auc(test_predictions, truth = default_flag, .pred_default)$.estimate
log_info(sprintf("Out-of-sample Test ROC-AUC: %.4f", auc_score))

# 10. Bundle Stripping & Model Pinning
log_info("Bundling model to strip extraneous environment context...")
bundled_workflow <- bundle::bundle(fitted_workflow)

# Inisialisasi Vetiver Model Metadata
v_model <- vetiver_model(
  model       = bundled_workflow,
  model_name  = "credit_scoring_xgb",
  versioned   = TRUE,
  description = "Production XGBoost Credit Risk Classifier",
  save_ptype  = train_df %>% select(-default_flag, -transaction_id) %>% slice_head(n = 5)
)

# Pinning ke filesystem lokal (dapat disubstitusi dengan pins::board_s3)
board_path <- file.path(tempdir(), "model_registry")
if (!dir.exists(board_path)) dir.create(board_path, recursive = TRUE)

board <- board_folder(board_path, versioned = TRUE)
vetiver_pin_write(board, v_model)

log_info(sprintf("Model artifact successfully pinned to: %s", board_path))
```

##### File: `api_service.R`
Microservice execution script yang di-mount oleh runtime container.
```R
#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(plumber)
  library(vetiver)
  library(pins)
  library(bundle)
  library(xgboost)
  library(recipes)
  library(workflows)
})

# 1. Inisialisasi Registry Board
board_path <- file.path(tempdir(), "model_registry")
board <- board_folder(board_path, versioned = TRUE)

# 2. Baca Model dari Registry
v_model <- vetiver_pin_read(board, "credit_scoring_xgb")

# Unbundle underlying model components safely
v_model$model <- bundle::unbundle(v_model$model)

# 3. Buat Plumber Router dengan Vetiver
pr <- plumber::pr()

# Healthcheck Endpoint
pr <- pr %>%
  pr_get("/healthz", function(res) {
    res$status <- 200
    list(status = "UP", timestamp = Sys.time())
  })

# Expose model endpoint dengan automatic prototype schema validation
vetiver_api(pr, v_model, type = "prob")

# 4. Jalankan Plumber API
# Di environment produksi, port dan host dikonfigurasi melalui ENV vars
port <- as.integer(Sys.getenv("PORT", "8080"))
host <- Sys.getenv("HOST", "0.0.0.0")

cat(sprintf("[INIT] Serving Vetiver API on %s:%d\n", host, port))
pr$run(host = host, port = port, swagger = FALSE)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Domain:** Global Fintech Payment Gateway.
- **Problem Statement:** Memprediksi fraud kartu kredit pada volume transaksi ~10 juta transaksi/hari.
- **SLA Ingestion to Scoring:** Total end-to-end API latency $\le 45\text{ ms}$ pada p99.
- **Skala:** 400 requests per detik (RPS) pada *peak hours*.

#### Arsitektur Desain
```
                                 KUBERNETES CLUSTER (EKS)
                        ┌───────────────────────────────────────────────┐
                        │              Ingress NGINX Controller         │
                        └───────────────────────┬───────────────────────┘
                                                │ Least Connections Load Balancing
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
      ┌─────────────────────────────┐                       ┌─────────────────────────────┐
      │ Pod 1: Plumber Model Worker │                       │ Pod n: Plumber Model Worker │
      │ ┌─────────────────────────┐ │                       │ ┌─────────────────────────┐ │
      │ │  gunicorn/R process     │ │                       │ │  gunicorn/R process     │ │
      │ │  pool (4 workers)       │ │                       │ │  pool (4 workers)       │ │
      │ └───────────┬─────────────┘ │                       │ └───────────┬─────────────┘ │
      └─────────────┼───────────────┘                       └─────────────┼───────────────┘
                    │                                                     │
                    └──────────────────────────┬──────────────────────────┘
                                               │
                                               ▼
                              ┌──────────────────────────────────┐
                              │ AWS S3 Pin Board (Model Registry)│
                              └──────────────────────────────────┘
```

#### Komponen Pipeline Produksi
1. **Dynamic Scaling:** Kubernetes Horizontal Pod Autoscaler (HPA) melakukan scale out pod R plumber berdasarkan metrik HTTP requests throughput menggunakan Prometheus Adapter.
2. **Payload Deserialization:** Vetiver menolak request berformat malformed tanpa membebani inference core, mengembalikan error `HTTP 422 Unprocessable Entity` secara instan.
3. **In-Memory Thread Safety:** XGBoost dieksekusi dengan single-thread per request worker (`nthread = 1`) untuk mengeliminasi thread contention pada Linux CFS (Completely Fair Scheduler), sementara konkurensi ditangani oleh scaling horizontal multi-worker.

---

### 9. Trade-offs

| Dimensi Arsitektural | Opsi A: Monolithic R Pipeline (`base::predict` + RData) | Opsi B: Modern Decoupled (`tidymodels` + `bundle` + `vetiver`) | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Inference Latency** | **Lebih Cepat (~5-10 ms)** pada payload tunggal karena bypass schema validation abstraction layer. | **Sedikit Overhead (~15-20 ms)** akibat validasi skema tipe via `vctrs::vec_cast`. | Skema validasi mengorbankan sekian milidetik demi proteksi mutlak terhadap *type-mutation attack* dan unhandled runtime exceptions. |
| **Memory Footprint** | **Tinggi (Rentan Leakage)**. Model membawa seluruh history environment. | **Rendah (Optimal)**. Artifact hanya berisi bobot murni hasil ekstraksi `bundle()`. | Memory footprint yang kecil memungkinkan utilisasi pod packing yang lebih padat di Kubernetes node. |
| **Maintenance & Portability**| **Rendah**. Kode inference terikat erat dengan format preprocessing buatan manual. | **Tinggi**. Workflow terenkapsulasi penuh; model dapat dipindah ke environment lain tanpa script pembantu terpisah. | Memudahkan integrasi dengan pipeline CI/CD modern dan interoperabilitas lintas tim ML/DevOps. |
| **Throughput Scaling** | Terbatas pada komputasi native single-threaded R process. | Mendukung horizontal autoscaling via container stateless. | Memerlukan infrastruktur container orchestration (K8s/Docker Swarm), menaikkan *cost* infrastruktur. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Data Leakage pada Preprocessing Recipe
* **Kesalahan:** Memanggil `prep()` pada keseluruhan dataset sebelum membagi data menjadi train dan test.
* **Gejala:** Metrik evaluasi pada validation set tampak superior ($AUC > 0.99$), namun performa ambruk saat diterapkan pada live streaming data.
* **Troubleshooting:** Pastikan pemanggilan `prep()` **hanya** menerima objek `training(split)`. Pengujian data testing harus dilakukan eksklusif melalui `bake(trained_recipe, new_data = testing(split))`.

#### 2. Plumber Server Stalling (Event-Loop Blocking)
* **Kesalahan:** Menjalankan model inferensi berdurasi panjang langsung pada default Plumber event-loop. Karena single-threaded, request klien kedua akan antre (block) hingga inferensi pertama tuntas.
* **Gejala:** Latensi melonjak drastis hingga puluhan detik saat traffic naik (> 50 RPS), memicu `HTTP 504 Gateway Timeout`.
* **Solusi:**
  - Gunakan package `promises` dan `future` di dalam endpoint handler untuk inferensi async.
  - Jalankan Plumber di balik process manager multi-worker seperti multi-container pod di Kubernetes atau menggunakan reverse-proxy yang mengarahkan traffic ke pool instance Rscript yang berbeda.

#### 3. S3 Serialization Bloat
* **Kesalahan:** Menyimpan model menggunakan standard `save()` atau `saveRDS()` langsung terhadap objek workflow.
* **Gejala:** Ukuran file artefak model mencapai $500\text{ MB} - 2\text{ GB}$ untuk model decision tree sederhana.
* **Solusi:** Selalu jalankan `bundle::bundle(fitted_workflow)` sebelum persistensi. Objek bundle akan memotong pointer lingkungan R yang tidak terpakai.

---

### 11. Best Practices (Production Checklist)

- [ ] **Validasi Skema Strict:** Skema prototype inferensi dideklarasikan dan diverifikasi menggunakan `vetiver::vetiver_model(save_ptype = ...)`.
- [ ] **Deterministic Seed Management:** Selalu atur seed pseudorandom number generator (`set.seed()`) secara global dan per worker cross-validation split.
- [ ] **Decoupled Preprocessing:** Feature engineering tidak mengandalkan fungsi ad-hoc di luar implementasi resmi `step_*` dalam `recipes`.
- [ ] **Containerization Hygiene:** Docker image menggunakan base multi-stage build berbasis Rocker (`rocker/r-ver`) dengan layer dependensi binary Linux (`rspm`) untuk build time yang cepat dan deterministik.
- [ ] **Immutability Versioning:** Setiap registrasi model ke registry board (`pins`) menggunakan commit hash Git atau UUID semantik sebagai identitas rilis artefak.
- [ ] **Health and Readiness Probes:** Container mengekspos endpoint `/healthz` yang secara mandiri memverifikasi ketersediaan artefak model di memori.

---

### 12. Hands-on Practice

Buat struktur direktori berikut di environment kerja Anda:
```bash
mkdir -p hands-on/m02/{config,scripts,models,api}
cd hands-on/m02
```

#### Langkah 1: Siapkan Script Pemodelan (`scripts/01_train.R`)
Tulis script yang membaca dataset `mtcars` (sebagai demonstrasi teknis arsitektur), mendefinisikan target regresi efisiensi bahan bakar (`mpg`), mengeksekusi recipe tuning, dan meng-export artefak model via `bundle`.

```R
# hands-on/m02/scripts/01_train.R
suppressPackageStartupMessages({
  library(tidymodels)
  library(bundle)
  library(pins)
  library(vetiver)
})

split <- initial_split(mtcars, prop = 0.75)
train_data <- training(split)
test_data  <- testing(split)

rec <- recipe(mpg ~ cyl + disp + hp + wt, data = train_data) %>%
  step_normalize(all_numeric_predictors())

mod_spec <- linear_reg(penalty = 0.1, mixture = 0.5) %>%
  set_engine("glmnet")

wf <- workflow() %>%
  add_recipe(rec) %>%
  add_model(mod_spec) %>%
  fit(data = train_data)

# Bundling dan Pinning
bundled_wf <- bundle(wf)
board <- board_folder("../models", versioned = TRUE)
v <- vetiver_model(bundled_wf, model_name = "glmnet_fuel_consumption", save_ptype = train_data[1:2, c("cyl", "disp", "hp", "wt")])
vetiver_pin_write(board, v)
cat("[SUCCESS] Model trained, bundled, and pinned.\n")
```

#### Langkah 2: Siapkan Entrypoint API (`api/app.R`)
```R
# hands-on/m02/api/app.R
suppressPackageStartupMessages({
  library(plumber)
  library(vetiver)
  library(pins)
  library(bundle)
  library(glmnet)
  library(recipes)
  library(workflows)
})

board <- board_folder("../models", versioned = TRUE)
v <- vetiver_pin_read(board, "glmnet_fuel_consumption")
v$model <- bundle::unbundle(v$model)

pr <- plumber::pr()
vetiver_api(pr, v)
pr$run(port = 8000, host = "0.0.0.0")
```

#### Langkah 3: Eksekusi dan Verifikasi API
Buka dua terminal terpisah:

**Terminal 1 (Jalankan Pelatihan & Server):**
```bash
Rscript scripts/01_train.R
Rscript api/app.R
```

**Terminal 2 (Uji Inferensi via cURL):**
```bash
curl -X POST "http://localhost:8000/predict" \
     -H "Content-Type: application/json" \
     -d '[
           {"cyl": 6, "disp": 160.0, "hp": 110, "wt": 2.62},
           {"cyl": 8, "disp": 360.0, "hp": 175, "wt": 3.44}
         ]'
```
Pastikan respons mengembalikan estimasi prediksi numerik secara deterministik.

---

### 13. Exercises

#### Level Easy
Modifikasi skrip pelatihan pada direktori `hands-on/m02/scripts/01_train.R` agar `credit_recipe` menangani korelasi multikolinearitas tinggi dengan menambahkan step filtering korelasi (`step_corr()`) dengan ambang batas (threshold) $r = 0.85$. Lakukan uji coba baking terhadap training split untuk memverifikasi prediktor mana saja yang dieliminasi.

#### Level Medium
Buat sebuah custom metric set pada `tidymodels` menggunakan fungsi `yardstick::metric_set()` yang secara simultan mengevaluasi metrik klasifikasi tidak seimbang: Balanced Accuracy (`bal_accuracy`), Area Under Precision-Recall Curve (`pr_auc`), dan F-beta Measure (`f_meas`, dengan $\beta = 2$). Terapkan pada tuning grid cross-validation dan tampilkan top 3 model terbaik berdasarkan metrik $F_2$.

#### Level Hard
Rancang modul monitoring *Data Drift* mandiri di R. Modul harus menerima dua dataframe (`reference_baseline` dan `current_inference_batch`), kemudian untuk setiap fitur bertipe numerik:
1. Hitung statistik dua sampel Kolmogorov-Smirnov test (`ks.test()`).
2. Hitung metriks Population Stability Index (PSI).
3. Jika nilai $p\text{-value} < 0.01$ atau $\text{PSI} > 0.25$, catat critical alert ke format log JSON terstruktur (stdout) yang memuat nama fitur, nilai metrik drift, dan timestamp.

---

### 14. Challenge

**Skenario:** Anda adalah Staff Machine Learning Engineer di platform e-commerce skala nasional. Tim pemasaran sering kali meluncurkan kampanye mendadak yang memicu *covariate shift* parah pada model estimasi *Click-Through-Rate* (CTR).

**Tantangan Arsitektur:**
1. Desain arsitektur *Dynamic Shadow Deployment* di mana API service Plumber menerima permintaan traffic produksi, menjalankan dua model paralel:
   - **Model Active:** Model stabil saat ini.
   - **Model Challenger:** Model baru yang terus dilatih ulang via batch cron.
2. API harus mengembalikan respon hanya dari *Model Active* (dengan overhead penambahan latensi $\le 10\text{ ms}$ untuk logging async), namun mendistribusikan payload serta prediksi kedua model secara asinkronus ke buffer penyimpanan lokal via Apache Arrow IPC stream buffer.
3. Buat fail-safe circuit breaker: jika *Model Active* menghasilkan residual error rate abnormal (misal format output `NA` akibat input di luar *novel range*), sistem secara otomatis mem-fallback inferensi ke *Model Challenger* tanpa memicu return error `500` ke pengguna.

*Tuliskan arsitektur desain komponen dan script wrapper Plumber engine yang mengimplementasikan circuit-breaker ini tanpa ketergantungan framework eksternal di luar R ecosystem.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Apa perbedaan mendasar antara fungsi `prep()` dan `bake()` dalam package `recipes`?**
   - *Jawaban:* `prep()` mengeksekusi perhitungan dan estimasi parameter statistik transformasi (seperti mean, deviasi standar, atau mapping level kategorikal) hanya dari dataset pelatihan (training partition). Sedangkan `bake()` menerapkan transformasi tersebut pada dataset lain (testing, inferensi baru) menggunakan parameter yang telah disimpan sebelumnya tanpa menghitung ulang statistik.

2. **Mengapa penggunaan formula R standar `y ~ .` rentan menyebabkan kebocoran memori (memory bloat) saat diserialisasi dengan `saveRDS()`?**
   - *Jawaban:* Formula di R mengikat environment tempat formula tersebut pertama kali didefinisikan (*lexical scoping enclosing environment*). Objek `saveRDS()` secara default akan melakukan traversal dan menyimpan seluruh variabel serta data frame besar yang berada di dalam lingkup environment tersebut.

3. **Komponen Tidymodels manakah yang bertanggung jawab menyatukan data preprocessor (`recipes`) dan algoritma model (`parsnip`) ke dalam satu objek utuh?**
   - *Jawaban:* Package `workflows`.

4. **Apa peran fungsi `save_ptype` dalam pembuatan objek `vetiver_model()`?**
   - *Jawaban:* `save_ptype` menyimpan struktur prototipe data (skema kolom dan tipe data kolom via `vctrs`) dari data input pelatihan. Prototipe ini digunakan di level API untuk memvalidasi tipe data payload JSON yang masuk ke endpoint model secara deterministik.

5. **Apa fungsi utama dari package `bundle` sebelum menyimpan model ML ke storage?**
   - *Jawaban:* Menghapus dependensi environment yang tidak diperlukan, membersihkan pointer eksternal sementara, dan mengemas model ke format yang portabel dan berukuran minimal.

#### Intermediate Questions
6. **Pada tuning hyperparameter menggunakan `tune_grid()`, mengapa parameter `parallel_over = "resamples"` lebih disukai daripada `parallel_over = "everything"` pada dataset berukuran besar?**
   - *Jawaban:* Memparalelkan proses pada level `resamples` mendistribusikan satu chunk data partisi ke satu worker untuk menguji seluruh grid parameter sekaligus. Ini meminimalkan overhead transfer memori (IPC serialization cost) data pelatihan antar proses jika dibandingkan dengan memparalelkan tiap kombinasi grid model.

7. **Bagaimana cara kerja validasi tipe data runtime pada API `vetiver` ketika menerima input payload JSON dengan nilai yang salah (misal: string numerik `"100"` pada kolom bertipe `double`)?**
   - *Jawaban:* `vetiver` menggunakan modul `vctrs::vec_cast()`. Jika string `"100"` dapat di-casting ke double secara lossless, tipe data disesuaikan. Jika nilai tidak valid (misal: `"seratus"`), API akan langsung menggagalkan request dengan mengembalikan HTTP code `422 Unprocessable Entity` beserta pesan validasi skema yang jelas sebelum mencapai komputasi underlying model.

8. **Mengapa model XGBoost yang dieksekusi di dalam service container multi-worker Plumber disarankan memiliki konfigurasi parameter engine `nthread = 1`?**
   - *Jawaban:* Mengizinkan tiap worker mengeksekusi multi-threading internal saat container sendiri telah menjalankan banyak worker proses akan menyebabkan *thread thrashing/contention* dan CPU throttling pada Linux kernel scheduler, menurunkan stabilitas latency p99.

9. **Apa fungsi dari fungsi `step_novel()` dalam pipeline `recipes` dan apa dampaknya jika step ini dilewati pada model klasifikasi multi-kategori di produksi?**
   - *Jawaban:* `step_novel()` mengalokasikan kategori khusus untuk menampung level string kategorikal baru yang belum pernah muncul pada data training. Jika dilewati, data inferensi baru yang memiliki kategori asing akan memicu error eksekusi model (karena ketidakcocokan dimensi model matrix) atau menghasilkan nilai `NA`.

10. **Bagaimana arsitektur storage `pins` mengelola versi (versioning) model machine learning yang disimpan di cloud backend (seperti S3 atau MinIO)?**
    - *Jawaban:* `pins` menyimpan setiap rilis model dalam subdirektori terisolasi yang diidentifikasi oleh timestamp atau hash konten, dilengkapi file metadata `metadata.yaml` yang mencatat hash SHA, tipe class, dan dependensi package R yang digunakan untuk pemodelan tersebut.

#### Skenario Kasus Produksi
11. **Skenario A:** Model Plumber Anda berjalan normal pada traffic pengujian internal, namun ketika diterapkan ke load balancer produksi dengan 200 RPS, konsumsi memori server meningkat linear hingga kehabisan RAM (OOM Crash). Setelah diperiksa, file kode tidak menyimpan state global di R script. Di manakah kemungkinan akar masalahnya?
    - *Solusi Analitis:* Masalah kemungkinan terletak pada serialisasi log request/response atau akumulasi execution context formula dalam closure di Plumber router. Selain itu, Plumber secara default tidak membersihkan memori secara agresif. Penanganan: Panggil `gc()` secara periodik via background filter, pastikan logging menggunakan external non-blocking stream (seperti forwarder Fluentd/stdout murni tanpa array buffer lokal di R), dan nonaktifkan Swagger UI (`swagger = FALSE`) pada production build.

12. **Skenario B:** Model XGBoost yang dilatih dengan Tidymodels memberikan akurasi tinggi, tetapi saat dideploy via Plumber di Docker Alpine Linux, hasil prediksi selalu identik untuk setiap input payload yang berbeda. Tidak ada pesan error yang muncul pada console. Apa yang terjadi?
    - *Solusi Analitis:* Terjadi kegagalan alignment model matrix pada saat pembuatan dummy variables (`step_dummy`) di fase `bake`. Ini sering kali terjadi jika payload data baru tidak melewati `step_unknown()` atau `step_novel()`, atau level faktor tidak terurut persis dengan prototipe data pelatihan karena environment locale yang berbeda antara mesin training (misal: Ubuntu UTF-8) dan runtime container (Alpine C locale). Gunakan image berbasis Ubuntu/Debian (`rocker/r-ver`) dan pastikan konfigurasi locale identik.

13. **Skenario C:** Sistem monitoring mendeteksi penurunan nilai ROC-AUC sebesar 18% dalam kurun waktu 3 minggu pada model deteksi penipuan transaksi. Namun, tes Kolmogorov-Smirnov pada semua fitur numerik menunjukkan bahwa distribusi data input tidak mengalami perubahan yang signifikan secara statistik ($p\text{-value} > 0.05$). Analisis fenomena ini dari sudut pandang machine learning modern dan langkah rekayasa apa yang harus diambil.
    - *Solusi Analitis:* Fenomena ini mengindikasikan terjadinya **Concept Drift** (bukan *Covariate Shift*). Hubungan probabilitas posterior $P(Y|X)$ telah bergeser meskipun distribusi data fitur marginal $P(X)$ tetap konstan—dalam konteks ini, pelaku penipuan telah mengubah taktik kejahatan tanpa mengubah profil data transaksi standar. Solusi rekayasa:
      1. Tarik sampel data ground-truth terbaru yang telah dilabeli manual oleh tim fraud operations.
      2. Latih ulang model dengan pembobotan waktu (*time-decay weighting*) menggunakan parameter `case_weights` di Tidymodels.
      3. Tambahkan fitur relasional baru yang menangkap pola interaksi temporal.

---

### 16. Summary

Modern R Machine Learning telah berevolusi dari sekadar eksperimen statistika manual menjadi disiplin rekayasa perangkat lunak produksi yang tangguh. Inti dari ekosistem modern ini berpusat pada pemisahan concerns yang ketat:

```
[Feature Engineering Design] ──► [Model Fitting & Tuning] ──► [Stripping & Artifact Store] ──► [Containerized Serving]
      (recipes engine)               (parsnip & workflows)             (bundle & pins)               (vetiver & plumber)
```

1. **Determinisme Pemrosesan:** Melalui modularisasi `prep()` dan `bake()`, pipeline menjamin integritas statistik dan eliminasi kebocoran data (*data leakage*) secara inheren.
2. **Kerapian Memori:** Pendekatan arsitektural berbasis `bundle` menghilangkan referensi environment yang berlebihan, memungkinkan footprint container yang ramping dan cepat dalam orkestrasi microservice.
3. **Produksi Siap Pakai:** Integrasi `vetiver` dan `plumber` menghadirkan standardisasi contract-driven API dengan validasi tipe runtime yang ketat, mentranslasikan ekosistem R menjadi *inference engine* kelas enterprise yang siap diskalakan secara horizontal pada arsitektur cloud modern.