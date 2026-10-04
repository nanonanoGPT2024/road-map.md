# Statistical Modeling & Inference Enterprise

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `R-LANG-07-01`
* **Domain**: 02-Programming-Languages / R Programming
* **Mata Kuliah / Jalur Pembelajaran**: Advanced R for Enterprise Data Science & Quantitative Engineering
* **Tingkat Kesulitan**: Lanjutan (Advanced)
* **Prasyarat**: 
  - Pemahaman mendalam tentang R Data Structures (`data.frame`, S3/S4 classes, Environment scoping).
  - Aljabar Linier Lanjutan (Matriks inversi, eigenvalue, dekomposisi QR, rank matriks).
  - Teori Probabilitas & Statistika Matematis (Maximum Likelihood Estimation, Central Limit Theorem, Hypothesis Testing).
* **Alokasi Waktu**: 18 Jam Pembelajaran Mandiri / 6 Jam Workshop Terbimbing.
* **Target Pembaca**: Production Quant, Enterprise Data Scientist, Machine Learning Engineer, Statistical Systems Architect.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1. **Menganalisis Mekanisme Internal Formula Engine R**: Membedah pembentukan `terms`, `model.frame`, dan `model.matrix`, serta mengeliminasi memory leakage yang diakibatkan oleh *formula lexical scoping capture*.
2. **Menguasai Komputasi Aljabar Linier Terapan**: Menjelaskan dan mengimplementasikan estimasi parameter melalui Dekomposisi QR berbasis Fortran (`dqrls`/LAPACK) versus solusi langsung Persamaan Normal ($X^T X \beta = X^T y$).
3. **Menerapkan Generalized Linear Models (GLM) Berskala Enterprise**: Menurunkan algoritma *Iteratively Reweighted Least Squares* (IRLS) menggunakan fungsi penghubung (*link function*) dan variansi eksponensial secara presisi.
4. **Mengeksekusi Inferensi Statistik Kokoh (*Robust Inference*)**: Mengintegrasikan koreksi heteroskedastisitas dan autokorelasi (estimasi sandwich White/Huber-Eicker dan Newey-West) pada lingkungan produksi.
5. **Mengaudit Asumsi dan Diagnostik Model**: Mendeteksi multikolinearitas ekstrim (Condition Index, Variance Inflation Factor), observasi berpengaruh (*Cook's Distance*, *Leverage*), dan *quasi-complete separation* pada regresi logistik.
6. **Membangun Pipeline Pemodelan Terdistribusi dan Tahan Banting**: Merancang inferensi statistik modular dengan serialisasi model yang aman, paralelisme bootstrap, dan validasi runtime data drift.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa data enterprise, pemodelan statistik bukan sekadar memanggil fungsi `lm()` atau `glm()` lalu mengevaluasi *p-value*. Mental model produksi bertumpu pada tiga postulat:

```
+-----------------------------------------------------------------------+
|                       ENTERPRISE MENTAL MODEL                         |
+-----------------------------------------------------------------------+
| 1. Model Adalah Transformator Aljabar Linier Numerik                  |
|    Setiap formula R (~ x1 + x2) menghasilkan matriks dens/sparse.      |
|    Presisi komputasi dibatasi oleh angka kondisi (condition number)    |
|    dan keterbatasan floating point IEEE 754.                          |
+-----------------------------------------------------------------------+
| 2. Inferensi Mengasumsikan Kebenaran Desain Eksperimen                |
|    p-value bernilai nol bukan jaminan signifikansi riil jika terjadi  |
|    pelanggaran asumsi IID (Independen & Identik Terdistribusi),       |
|    seleksi endogen, atau kebocoran data (data leakage).               |
+-----------------------------------------------------------------------+
| 3. Reproduksibilitas Matematis = Reliabilitas Sistem                  |
|    Model statistik di produksi harus deterministik dalam estimasi,    |
|    kebal terhadap manipulasi input, dan memiliki fail-safe terhadap   |
|    singularitas matriks saat streaming inference.                     |
+-----------------------------------------------------------------------+
```

Jangan memperlakukan formula R sebagai "sintaks dekoratif". Di balik simbol tilde (`~`), R menangkap seluruh *lexical environment* tempat formula didefinisikan. Jika Anda tidak memahami alokasi memori ini, pipeline pemodelan Anda akan mengunci gigabyte memori dan menyebabkan *Out-Of-Memory* (OOM) crash di lingkungan container Kubernetes.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur eksekusi internal pemodelan statistik di R, mulai dari parsing formula simbolik hingga optimasi numerik tingkat rendah:

```
[User Interface]
       │
       ▼
 [ formula: y ~ x1 + x2 ] ─── (Captures Lexical Environment)
       │
       ▼
 [ model.frame(formula, data) ]
       │  ├── Evaluasi variabel, drop NA (na.action)
       │  └── Ekstraksi atribut respons & prediktor
       ▼
 [ model.matrix(terms, mf) ]
       │  ├── Transformasi faktor ke Dummy/Contrast (Treatment, Sum, Helmert)
       │  └── Menghasilkan Design Matrix X berdimensi (n x p)
       ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Komputasi Mesin Numerik (C / Fortran Subroutines)           │
 │                                                             │
 │  OLS (lm):                                                  │
 │   Matrix X ──► .Call(C_Cdqrls) ──► LAPACK / BLAS (DQRDC)    │
 │                │                   (Householder QR)         │
 │                ▼                                            │
 │   Solusi: R * beta = Q^T * y                                │
 │                                                             │
 │  GLM (glm):                                                 │
 │   IRLS Loop: W_t = (g'(mu)^2 * V(mu))^-1                    │
 │              z_t = eta + (y - mu) * g'(mu)                  │
 │              Solve weighted OLS: (X^T W X) beta = X^T W z   │
 │              Iterasi hingga deviance konvergen              │
 └─────────────────────────────────────────────────────────────┘
       │
       ▼
 [ S3 Return Object ] (class: "lm" atau "glm")
       │
       ├── Coef, Residuals, Fitted Values, Rank, QR
       │
       ▼
 [ Inference Engine ] (Heteroskedasticity & Hypothesis Testing)
       │
       ├── Huber-White Sandwich Estimator: (X^T X)^-1 (X^T Omega X) (X^T X)^-1
       ├── Wald Test / Score Test / Likelihood Ratio Test
       └── Multiple Testing Corrections (Benjamini-Hochberg / Bonferroni)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Ekosistem Formula dan Lingkungan (*Lexical Scoping*)
Formula di R dibuat dengan operator `~`. Objek formula membawa kelas `formula` dan mereferensikan *environment* tempat ia dibuat:
```r
f <- y ~ x1 + x2
environment(f) # Menunjuk ke environment aktif saat pembuatan
```
Jika formula dibuat di dalam fungsi pembungkus (*wrapper*), formula tersebut secara default mempertahankan pointer ke seluruh objek di dalam fungsi tersebut. Ini menghalangi *Garbage Collector* (GC) membebaskan memori lokal fungsi jika objek formula dikembalikan atau disimpan.

### 2. Pipeline `model.frame` dan `model.matrix`
- `terms(formula)`: Mengompilasi ekspresi formula menjadi representasi kanonikal, mendata ordo interaksi, intercept, dan respons.
- `model.frame(terms, data)`: Menggabungkan metadata istilah dengan data riil, memfilter missing data via argumen `na.action` (e.g., `na.omit`, `na.fail`), dan mempertahankan atribut tipe data.
- `model.matrix(terms, data)`: Melakukan ekspansi aljabar. Variabel bertipe `factor` dikonversi menjadi kolom kontras biner. Secara default, R menggunakan `contr.treatment` di mana level pertama dijadikan basis (*reference group*).

### 3. Solusi Kuadrat Terkecil Numerik (The Fortran Interface)
`stats::lm` tidak menghitung $\hat{\beta} = (X^T X)^{-1} X^T y$ menggunakan inversi matriks langsung karena angka kondisi (*condition number*) $\kappa(X^T X) = \kappa(X)^2$, yang melipatgandakan eror numerik floating point.

Sebagai gantinya, `lm()` mendelegasikan komputasi ke internal C wrapper `C_Cdqrls` yang mengeksekusi subrutin Fortran LAPACK/LINPACK:
1. Melakukan Dekomposisi QR dari matriks desain $X$: $X = Q R$ di mana $Q$ adalah matriks ortogonal ($Q^T Q = I$) dan $R$ adalah matriks segitiga atas (*upper triangular*).
2. Sistem persamaan $X \beta = y$ bertransformasi menjadi $Q R \beta = y \implies R \beta = Q^T y$.
3. Mengingat $R$ adalah matriks segitiga atas, $\hat{\beta}$ diselesaikan melalui algoritma substitusi balik (*back-substitution*) berkecepatan tinggi dengan stabilitas numerik optimal:
$$\hat{\beta} = R^{-1} (Q^T y)$$
4. Singularitas kolom dideteksi melalui *pivoting*: jika elemen diagonal dari $R$ berada di bawah batas toleransi numerik, kolom yang bersangkutan ditandai sebagai aliased (`NA`) dan rank matriks didegradasi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Ordinary Least Squares (OLS) dan Teorema Gauss-Markov
Model linier klasik dinyatakan sebagai:
$$y = X\beta + \varepsilon, \quad \mathbb{E}[\varepsilon|X] = 0, \quad \text{Var}(\varepsilon|X) = \sigma^2 I_n$$
Berdasarkan Teorema Gauss-Markov, penduga OLS $\hat{\beta} = (X^T X)^{-1} X^T y$ adalah penduga linier tak bias terbaik (*Best Linear Unbiased Estimator* / BLUE). Namun di lingkungan enterprise, dua asumsi sering runtuh:
- **Homoskedastisitas Terlanggar**: $\text{Var}(\varepsilon_i | X) = \sigma_i^2 \neq \text{konstan}$. Akibatnya, standard error dari OLS konvensional menjadi bias ke bawah (*underestimated*), menghasilkan nilai false positive ($p < 0.05$) yang semu.
- **Multikolinearitas**: $\det(X^T X) \to 0$, menyebabkan variansi estimasi parameter meledak mendekati tak hingga:
  $$\text{Var}(\hat{\beta}_j) = \frac{\sigma^2}{(1 - R_j^2) \sum (x_{ij} - \bar{x}_j)^2}$$
  di mana $1 / (1 - R_j^2)$ adalah Variance Inflation Factor (VIF).

### 2. Generalized Linear Models (GLM) dan Algoritma IRLS
Jika variabel respons $y$ berasal dari Keluarga Eksponensial (Bernoulli, Poisson, Gamma), ekspektasi bersyarat dikaitkan dengan prediktor linier via fungsi penghubung $g(\cdot)$:
$$\mathbb{E}[y|X] = \mu, \quad g(\mu) = \eta = X\beta \implies \mu = g^{-1}(X\beta)$$
Fungsi log-likelihood dimaksimalkan dengan estimasi Fisher Scoring / IRLS. Pada setiap iterasi $t+1$:
$$\beta^{(t+1)} = (X^T W_t X)^{-1} X^T W_t z_t$$
di mana:
- $W_t$ adalah matriks bobot diagonal: $W_{ii} = \frac{1}{\text{Var}(\mu_i) \left[g'(\mu_i)\right]^2}$
- $z_t$ adalah variabel respons yang disesuaikan (*working response*): $z_i = \eta_i + (y_i - \mu_i) g'(\mu_i)$

### 3. Asymptotic Inference & Robust Covariance Matrix Estimation
Untuk mengompensasi heteroskedastisitas tanpa memodifikasi estimasi parameter titik $\hat{\beta}$, inferensi enterprise wajib menggunakan estimasi kovariansi sandwich (*Huber-White Heteroskedasticity-Consistent Covariance Matrix*):
$$\widehat{\text{Var}}_{\text{HC}}(\hat{\beta}) = (X^T X)^{-1} \left( \sum_{i=1}^n x_i x_i^T \hat{\varepsilon}_i^2 \cdot \omega_i \right) (X^T X)^{-1}$$
Varian koreksi terstandardisasi mencakup:
- **HC0**: Formulasi dasar White (rentan bias pada sampel terbatas).
- **HC1**: Koreksi derajat kebebasan, $\omega_i = \frac{n}{n - p}$.
- **HC3**: Formulasi resisten terhadap *high-leverage points*, $\omega_i = \frac{1}{(1 - h_{ii})^2}$, di mana $h_{ii}$ adalah elemen diagonal dari projection matrix (hat matrix) $H = X(X^T X)^{-1}X^T$.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi komprehensif implementasi model statistik, ekstraksi parameter tingkat rendah, inspeksi dekomposisi QR, serta perbandingan standard error klasik versus sandwich estimator HC3.

```r
# ==============================================================================
# Script: fundamental_inference_engine.R
# Deskripsi: Dekonstruksi internal OLS, inspeksi QR, dan komputasi SE Robust
# ==============================================================================

# Definisikan seed untuk determinisme absolut
set.seed(42)

# 1. GENERASI DATA DENGAN PELANGGARAN HETEROSKEDASTISITAS
n_obs <- 1000L
x1 <- rnorm(n_obs, mean = 5.0, sd = 1.5)
x2 <- rpois(n_obs, lambda = 3) + 0.5 * x1
# Heteroskedastisitas: Variansi error membesar seiring nilai x1
heteroskedastic_sd <- 0.5 * (x1^1.5)
true_epsilon <- rnorm(n_obs, mean = 0.0, sd = heteroskedastic_sd)

true_beta <- c(Intercept = 2.5, b1 = 1.8, b2 = -0.75)
y <- true_beta["Intercept"] + true_beta["b1"] * x1 + true_beta["b2"] * x2 + true_epsilon

df_data <- data.frame(response = y, pred_1 = x1, pred_2 = x2)

# 2. IMPLEMENTASI FORMULA & EKSTRAKSI MODEL MATRIX
target_formula <- response ~ pred_1 + pred_2
terms_obj <- terms(target_formula)
model_frm <- model.frame(terms_obj, data = df_data)
design_matrix <- model.matrix(terms_obj, data = model_frm)
vector_y <- model.response(model_frm)

# 3. ESTIMASI PARAMETER VIA LOW-LEVEL QR DECOMPOSITION
# Menggunakan LAPACK/BLAS native R
qr_decomp <- qr(design_matrix)
beta_qr <- qr.coef(qr_decomp, vector_y)

# 4. PEMODELAN STANDAR MELALUI stats::lm
fit_lm <- lm(target_formula, data = df_data)

# 5. KOMPUTASI MANUAL STANDARD ERROR: OLS KLASIK VS ROBUST HC3
# Derajat kebebasan (Residual Degrees of Freedom)
n_k <- nrow(design_matrix) - ncol(design_matrix)
residuals_ols <- vector_y - (design_matrix %*% beta_qr)
sigma_squared <- sum(residuals_ols^2) / n_k

# Matriks (X^T X)^-1 diekstraksi via solve pada crossprod atau QR R-matrix
xtx_inv <- solve(crossprod(design_matrix))
cov_classical <- sigma_squared * xtx_inv
se_classical <- sqrt(diag(cov_classical))

# Komputasi Robust Covariance HC3
# Hat matrix diagonal: h_ii
h_diag <- rowSums(qr.Q(qr_decomp)^2) # Ekivalen dengan diag(X (X^TX)^-1 X^T)
hc3_weights <- (residuals_ols / (1 - h_diag))^2
meat_matrix <- crossprod(design_matrix, as.vector(hc3_weights) * design_matrix)
cov_hc3 <- xtx_inv %*% meat_matrix %*% xtx_inv
se_hc3 <- sqrt(diag(cov_hc3))

# 6. PENYAJIAN TABEL PERBANDINGAN INFERENSI
inference_table <- data.frame(
  Koefisien_Point = beta_qr,
  SE_Klasik = se_classical,
  SE_Robust_HC3 = se_hc3,
  t_Stat_Klasik = beta_qr / se_classical,
  t_Stat_Robust = beta_qr / se_hc3,
  P_Val_Klasik = 2 * (1 - pt(abs(beta_qr / se_classical), df = n_k)),
  P_Val_Robust = 2 * (1 - pt(abs(beta_qr / se_hc3), df = n_k))
)

print(round(inference_table, 5))
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari alur kode pada Seksi 07:

1. **Baris 13-17**: `heteroskedastic_sd <- 0.5 * (x1^1.5)`. Membangun ketidakstabilan variansi secara eksplisit. Standar deviasi galat bergantung secara non-linier pada variabel prediktor $x_1$, melanggar postulat Homoskedastisitas $\text{Var}(\varepsilon | X) = \sigma^2$.
2. **Baris 23-26**: 
   - `terms_obj <- terms(target_formula)`: Memvalidasi struktur simbolik tanpa mengikat data, menentukan intercept implisit.
   - `model_frame(...)`: Menggabungkan namespace lingkungan dengan dataframe `df_data`.
   - `model.matrix(...)`: Mengonversi skema menjadi representasi numerik floating-point 64-bit ($X$). Memasukkan kolom skalar `(Intercept)` berisi vektor `1.0`.
3. **Baris 30-31**: `qr_decomp <- qr(design_matrix)`. Menghindari komputasi langsung inversi $X^T X$. R memanggil fungsi Fortran `dqrdc2` yang melakukan faktorisasi Householder dengan *column pivoting*.
4. **Baris 40**: `sigma_squared <- sum(residuals_ols^2) / n_k`. Estimasi variansi residual klasik tak bias ($s^2$). Perhatikan pembagi $n - k$ (bukan $n$) untuk mempertahankan sifat tak bias (*degrees of freedom correction*).
5. **Baris 43**: `xtx_inv <- solve(crossprod(design_matrix))`. `crossprod(A)` mengeksekusi operasi $A^T A$ melalui pemanggilan pustaka BLAS Level 3 `DSYRK`, sekitar $2\times$ lebih cepat dan hemat alokasi memori dibandingkan `t(A) %*% A`.
6. **Baris 48**: `h_diag <- rowSums(qr.Q(qr_decomp)^2)`. Trik optimasi numerik tingkat tinggi. Menghitung elemen diagonal matriks proyeksi $H = X(X^TX)^{-1}X^T$ tanpa membangun matriks $n \times n$ (yang akan menelan memori $1000 \times 1000 \times 8$ bytes). Karena $Q$ memiliki kolom ortonormal, $\text{diag}(H) = \sum_{j=1}^p Q_{ij}^2$.
7. **Baris 49-51**: Formulasi *Meat Matrix* Sandwich HC3: $X^T \Omega_{\text{HC3}} X$ di mana bobot residual diskalakan dengan pembagi $(1 - h_{ii})^2$. Pembagi ini memberikan penalti matematis pada titik dengan *leverage* tinggi, mencegah titik ekstrem mendistorsi inferensi asimtotik.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Bisnis: Credit Risk PD (Probability of Default) Calibration
Sebuah institusi perbankan tier-1 meregulasi modal berbasis Basel III/IV. Anda ditugaskan membangun model *Probability of Default* (PD) menggunakan Regresi Logistik terkalibrasi untuk portofolio pinjaman usaha kecil dan menengah (*SME Loans*).

### Permasalahan Teknis:
1. **Multikolinearitas Tinggi**: Fitur keuangan (e.g., *Debt-to-Equity Ratio*, *Current Ratio*, *Debt Service Coverage*) saling berkorelasi erat.
2. **Class Imbalance & Extreme Leverage**: Jumlah debitur default sangat rendah ($<2\%$), memicu risiko *quasi-complete separation* yang dapat menyebabkan estimasi Maximum Likelihood meledak tak hingga.
3. **Audit Kepatuhan Regulator**: Output model tidak boleh berupa *black box*; koefisien harus memiliki estimasi interval kepercayaan yang valid di bawah asumsi heteroskedastisitas residual, serta stabilitas rank matriks terverifikasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Script produksi di bawah ini mengintegrasikan seluruh pipeline audit matematis: deteksi singularitas, estimasi logistik via Fisher Scoring, inspeksi VIF, robust sandwich testing via paket industri teruji (`sandwich`, `lmtest`), serta pemantauan deviance convergence.

```r
# ==============================================================================
# Script: enterprise_pd_risk_engine.R
# Modul: Produksi Kalibrasi PD dengan Diagnostik Matriks & Sandwich HC
# ==============================================================================

# Pastikan environment steril
rm(list = ls(all.names = TRUE))
gc(verbose = FALSE)

suppressPackageStartupMessages({
  library(sandwich) # High-performance robust matrix estimators
  library(lmtest)   # Hypothesis testing framework
})

# 1. GENERASI DATA SIMULASI PORTFOLIO SME (N = 50,000)
generate_enterprise_data <- function(n_records = 50000L) {
  set.seed(101)
  
  dscr <- pmax(0.1, rnorm(n_records, mean = 1.4, sd = 0.5))          # Debt Service Coverage
  leverage <- pmax(0.2, rnorm(n_records, mean = 2.5, sd = 1.2))      # Debt / Equity
  liquidity <- pmax(0.05, rnorm(n_records, mean = 1.1, sd = 0.4))    # Current Ratio
  # Sintesis multikolinearitas struktural
  synthetic_corr_var <- (0.7 * leverage) + rnorm(n_records, 0, 0.3)
  
  # Prediktor linear (Log-Odds)
  latent_log_odds <- -4.2 - (1.1 * dscr) + (0.65 * leverage) - (0.45 * liquidity)
  prob_default <- 1 / (1 + exp(-latent_log_odds))
  
  # Target biner: 1 = Default, 0 = Performing
  is_default <- rbinom(n_records, size = 1, prob = prob_default)
  
  data.frame(
    default_flag = is_default,
    dscr = dscr,
    leverage = leverage,
    liquidity = liquidity,
    corr_leverage = synthetic_corr_var
  )
}

# 2. AUDIT MULTIKOLINEARITAS: DETEKSI VIA CONDITION INDEX & VIF
calculate_vif <- function(design_mat) {
  # Hilangkan intercept untuk perhitungan VIF prediktor
  has_intercept <- grep("(Intercept)", colnames(design_mat))
  if (length(has_intercept) > 0) {
    X <- design_mat[, -has_intercept, drop = FALSE]
  } else {
    X <- design_mat
  }
  
  vif_vals <- numeric(ncol(X))
  names(vif_vals) <- colnames(X)
  
  for (i in seq_along(vif_vals)) {
    y_sub <- X[, i]
    X_sub <- X[, -i, drop = FALSE]
    # OLS fit antar fitur
    fit_sub <- lm.fit(cbind(1, X_sub), y_sub)
    ss_total <- sum((y_sub - mean(y_sub))^2)
    ss_residual <- sum(fit_sub$residuals^2)
    r_squared <- 1 - (ss_residual / ss_total)
    
    # Proteksi pembagian nol jika multikolinearitas mutlak
    if (r_squared >= 0.9999) {
      vif_vals[i] <- Inf
    } else {
      vif_vals[i] <- 1 / (1 - r_squared)
    }
  }
  return(vif_vals)
}

# 3. PIPELINE ESTIMASI DAN VALIDASI PRODUKSI
run_production_pipeline <- function() {
  portfolio_df <- generate_enterprise_data(50000L)
  
  # Audit Dimensi dan Default Rate
  default_rate <- mean(portfolio_df$default_flag)
  cat(sprintf("[AUDIT] Data Loaded: %d baris. Base Default Rate: %.4f%%\n", 
              nrow(portfolio_df), default_rate * 100))
  
  # Formula model yang berisiko kolinearitas tinggi
  raw_formula <- default_flag ~ dscr + leverage + liquidity + corr_leverage
  
  # Validasi matriks desain
  mf <- model.frame(raw_formula, data = portfolio_df)
  X <- model.matrix(raw_formula, data = mf)
  y <- model.response(mf)
  
  # 3a. Kondisi Numerik Matriks Desain
  # Singular Value Decomposition untuk mendeteksi Condition Number
  singular_values <- svd(scale(X[, -1]))$d
  condition_number <- max(singular_values) / min(singular_values)
  cat(sprintf("[MATRIKS] Condition Index: %.2f ", condition_number))
  
  if (condition_number > 30) {
    cat("-> [PERINGATAN]: Kolinieritas berat terdeteksi (Threshold > 30)\n")
  } else {
    cat("-> [STATUS]: Matriks stabil.\n")
  }
  
  vif_results <- calculate_vif(X)
  cat("[VIF REPORT]\n")
  print(round(vif_results, 3))
  
  # Drop prediktor dengan VIF ekstrem (> 5.0) secara terprogram
  safe_predictors <- names(vif_results[vif_results < 5.0])
  recalibrated_formula <- as.formula(
    paste("default_flag ~", paste(safe_predictors, collapse = " + "))
  )
  cat(sprintf("[REMODELING] Formula Dikalibrasi Ulang: %s\n", deparse(recalibrated_formula)))
  
  # 3b. Estimasi GLM Binomial (Fisher Scoring)
  glm_start_time <- proc.time()
  pd_model <- glm(
    recalibrated_formula,
    data = portfolio_df,
    family = binomial(link = "logit"),
    control = glm.control(maxit = 50, epsilon = 1e-10, trace = FALSE)
  )
  execution_duration <- proc.time() - glm_start_time
  
  if (!pd_model$converged) {
    stop("[FATAL]: Algoritma IRLS GLM gagal mencapai konvergensi.")
  }
  cat(sprintf("[GLM] Konvergensi tercapai dalam %d iterasi. Waktu: %.4f detik.\n", 
              pd_model$iter, execution_duration["elapsed"]))
  
  # 3c. Robust Inference Engine (Heteroskedasticity-Consistent / Sandwich)
  # Menggunakan vcovHC type HC0 untuk binary responses (asymptotic robust standard error)
  robust_cov_matrix <- sandwich::vcovHC(pd_model, type = "HC0")
  robust_test <- lmtest::coeftest(pd_model, vcov = robust_cov_matrix)
  
  cat("\n========================= INFERENSI STANDARD =========================\n")
  print(summary(pd_model)$coefficients)
  
  cat("\n=================== INFERENSI KOKOH (ROBUST HC0) =====================\n")
  print(robust_test)
  
  # Validasi Overdispersion
  deviance_residual <- pd_model$deviance
  df_residual <- pd_model$df.residual
  dispersion_ratio <- deviance_residual / df_residual
  cat(sprintf("\n[OVERDISPERSION METRIC] Deviance/DF: %.4f\n", dispersion_ratio))
  
  return(list(model = pd_model, robust_vcov = robust_cov_matrix))
}

# Eksekusi Pipeline
exec_result <- run_production_pipeline()
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Di lingkungan produksi berskala besar, pemilihan teknik estimasi parameter linear/GLM harus mempertimbangkan kompromi performa numerik, stabilitas rank matriks, dan konsumsi memori.

| Metode / Algoritma | Stabilitas Numerik | Kompleksitas Waktu | Alokasi Memori | Keterbatasan Operasional | Rekomendasi Enterprise |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Persamaan Normal**<br>$(X^T X)^{-1} X^T y$ | Sangat Rendah ($\kappa(X^T X) = \kappa(X)^2$) | $\mathcal{O}(np^2 + p^3)$ (Cepat) | Minimal ($\mathcal{O}(p^2)$) | Runtuh jika matriks singular/ill-conditioned | **Dilarang untuk produksi**. Risiko overflow & instabilitas tinggi. |
| **Dekomposisi QR (Householder)**<br>`stats::lm` (LAPACK `dqrls`) | **Sangat Tinggi** ($\kappa(QR) = \kappa(X)$) | $\mathcal{O}(2np^2 - \frac{2}{3}p^3)$ | Moderat (Menyimpan matriks $Q$ dan $R$) | Membutuhkan alokasi memori berukuran $n \times p$ secara kontinu di RAM | **Standar Industri**. Ideal untuk dataset in-memory hingga puluhan juta baris. |
| **Singular Value Decomposition (SVD)** | **Maksimal** (Epsilon thresholding) | $\mathcal{O}(4np^2 + 8p^3)$ (Paling Lambat) | Tinggi | Komputasi intensif; mahal jika fitur $p > 10,000$ | Gunakan jika matriks desain mendekati *rank deficiency* parah. |
| **IRLS Fisher Scoring**<br>`stats::glm` | Bergantung pada kondisi $X^T W X$ tiap iterasi | $\mathcal{O}(m \cdot (np^2 + p^3))$ di mana $m$ = iterasi | Moderat-Tinggi (Pembaruan matriks $W$ kontinu) | Sensitif terhadap *perfect separation* (koefisien divergen ke $\pm \infty$) | Gunakan kontrol batas konvergensi `epsilon = 1e-8` & `maxit = 25`. |
| **Coordinate Descent Regularized**<br>`glmnet` (L1/L2) | Tinggi (Ditekan oleh regularisasi $\lambda$) | Sangat Efisien pada Sparse Matrix | Sangat Rendah | Inferensi statistik klasik (p-value, interval standar) sulit diturunkan | Gunakan jika dimensi $p \gg n$ atau multikolinearitas tidak dapat dihindari. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Quasi-Complete Separation pada GLM Binomial
- **Kasus**: Prediktor tunggal atau kombinasi linier prediktor memisahkan respons biner secara sempurna ($y=1$ jika $x > c$ dan $y=0$ jika $x \le c$).
- **Manifestasi Kerusakan**: Algoritma IRLS tidak pernah konvergen. Nilai koefisien $\hat{\beta}$ membengkak ke jutaan, dan standard error membengkak ke angka puluhan ribu (misal: $\text{SE} > 5000$), memicu *Wald test p-value* palsu mendekati $1.0$ (fenomena Hauck-Donner).
- **Deteksi**: Periksa apakah ada $\text{SE}(\hat{\beta}_j) > 100 \times \text{median}(\text{SE})$.
- **Mitigasi**: Gunakan regresi logistik terbias (*Firth's Penalized Likelihood* via pustaka `logistf`), yang menambahkan modifikasi penalti Jeffreys prior pada fungsi likelihood.

### 2. Rank Deficiency Akibat Singularitas Desain Matriks
- **Kasus**: Dua variabel berkorelasi linear sempurna ($x_2 = 2 \cdot x_1$) atau terdapat level kategorikal tanpa variansi dalam subset data.
- **Manifestasi Kerusakan**: Matriks $X^T X$ tidak dapat dibalik. `lm()` akan menetapkan koefisien variabel sekunder menjadi `NA` secara diam-diam (*silent failure*).
- **Mitigasi**: Selalu periksa atribut `$rank` dari objek yang dihasilkan versus jumlah kolom di matriks desain:
  ```r
  if (fit$rank < ncol(model.matrix(fit))) {
    warning("Matrix design rank-deficient! Ditemukan multikolinearitas mutlak.")
  }
  ```

### 3. Kebocoran Memori Formula (*Lexical Environment Memory Leak*)
- **Kasus**: Objek formula didefinisikan di dalam fungsi yang memuat objek data mentah berukuran gigabyte:
  ```r
  build_model <- function() {
    huge_blob <- readRDS("heavy_data_10GB.rds")
    # Lingkungan formula ini sekarang mengunci huge_blob di RAM
    form <- target ~ feature_1 + feature_2
    fit <- lm(form, data = huge_blob)
    return(fit)
  }
  ```
- **Manifestasi Kerusakan**: Memori RAM 10GB tidak pernah dibebaskan oleh *Garbage Collector* meskipun fungsi selesai dieksekusi, karena `fit$terms` memegang pointer ke formula, dan formula memegang pointer ke environment eksekusi `build_model`.
- **Mitigasi**: Putus environment formula secara manual sebelum mengembalikan objek:
  ```r
  environment(fit$terms) <- baseenv()
  environment(fit$model) <- baseenv()
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Melakukan Uji Asumsi Klasik OLS pada Objek GLM
* **Kesalahan**: Menjalankan Shapiro-Wilk atau Breusch-Pagan test pada raw residuals model regresi logistik/poisson.
* **Dampak**: Model GLM tidak mengasumsikan galat terdistribusi normal atau bervariansi konstan; pengujian ini secara matematis keliru dan menghasilkan alarm palsu.
* **Solusi**: Gunakan *Deviance Residuals* atau *Dunn-Smyth Randomized Quantile Residuals* (paket `DHARMa`) untuk mengevaluasi goodness-of-fit model GLM.

### 2. P-Hacking melalui Penambahan Multipel Interaksi Tanpa Koreksi Derajat Bebas
* **Kesalahan**: Menambahkan variabel interaksi order tinggi (`x1 * x2 * x3 * x4`) secara membabi buta demi meningkatkan $R^2$.
* **Dampak**: Overfitting ekstrem, inflasi angka kondisi matriks, dan peningkatan drastis Family-Wise Error Rate (FWER).
* **Solusi**: Uji model bersarang (*nested models*) menggunakan Likelihood Ratio Test via `anova(model_reduced, model_full, test = "Chisq")`, dan aplikasikan penyesuaian Benjamini-Hochberg (FDR) pada signifikansi omnibus.

### 3. Membaca Koefisien Kategorikal Tanpa Memeriksa Skema Kontras
* **Kesalahan**: Menginterpretasi nilai koefisien kategori tanpa mengetahui basis referensi (`contr.treatment` vs `contr.sum`).
* **Dampak**: Salah mengidentifikasi arah hubungan bisnis; mengira koefisien adalah deviasi dari grand mean, padahal merupakan perbedaan relatif terhadap baseline level.
* **Solusi**: Audit skema kontras menggunakan `contrasts(df$kategori)` sebelum menjalankan fitting model.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Operator BLAS Terakselerasi**: Hindari pembentukan eksplisit matriks kuadrat jika hanya membutuhkan dot product atau cross product. Gunakan `crossprod(X)` untuk $X^T X$ dan `crossprod(X, y)` untuk $X^T y$.
2. **Standardisasi Pemanggilan Model**: Jangan pernah menggunakan variabel di luar dataframe melalui penulisan formula `df$y ~ df$x`. Pola ini merusak kemampuan serialisasi model (`predict()` akan gagal saat di-deploy karena model mencari objek bernama `df` di memori global).
3. **Konstruksi S3 Method Standar**: Saat membungkus pipeline pemodelan enterprise, buat pembungkus berbasis S3 class yang mengimplementasikan method resmi:
   - `predict.enterprise_model()`
   - `print.enterprise_model()`
   - `summary.enterprise_model()`
4. **Isolasi Sanitasi Kontrak Data**: Validasi tipe data ketat pada kolom prediktor sebelum evaluasi `model.matrix()`. Konversikan karakter ke faktor secara deterministik dengan mendefinisikan seluruh level yang dimungkinkan, mencegah inkonsistensi level yang hilang pada data scoring inference.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Untuk pemrosesan analitik enterprise dengan ukuran matriks mencapai puluhan juta baris, overhead formula interface di R (`model.frame`) bisa menjadi bottleneck utama.

```
                    BENCHMARK PEMROSESAN STATISTIK
┌────────────────────────┬───────────────────┬────────────────────┐
│ Metrik Komputasi       │ stats::lm (Base)  │ RcppEigen / LAPACK │
├────────────────────────┼───────────────────┼────────────────────┤
│ Formula Parsing        │ ~ 0.450 detik     │ Dieliminasi (0 s)  │
│ Matrix Copying         │ Duplikasi Memori  │ Zero-Copy Pointer  │
│ QR Flops Engine        │ Fortran standard  │ AVX-512 Vectorized │
│ Total Waktu (N=5M,P=10)│ ~ 8.20 detik      │ ~ 0.85 detik       │
└────────────────────────┴───────────────────┴────────────────────┘
```

### Implementasi Eksekusi Cepat: Solusi `fastLm` Teroptimasi
Jika dataset Anda telah divalidasi dan tidak mengandung missing values (`NA`), bypass abstraksi S3 dengan memanfaatkan antarmuka `lm.fit()` langsung atau pustaka linear solver teroptimasi BLAS:

```r
# ==============================================================================
# Script: benchmark_high_performance_ols.R
# ==============================================================================

# Generasi data masif: 2.000.000 baris
n_rows <- 2000000L
n_features <- 5L
X_mat <- matrix(rnorm(n_rows * n_features), nrow = n_rows, ncol = n_features)
X_mat <- cbind(1, X_mat) # Append Intercept
true_b <- c(1.5, 0.8, -1.2, 3.0, -0.5, 0.2)
y_vec <- X_mat %*% true_b + rnorm(n_rows, sd = 0.5)

# METODE A: Konvensional via formula (Tinggi alokasi overhead)
time_formula <- system.time({
  df_large <- as.data.frame(X_mat[, -1])
  df_large$y <- as.vector(y_vec)
  fit_conventional <- lm(y ~ ., data = df_large)
})

# METODE B: Low-level Engine (Bypass parsing S3 dan copy)
time_lowlevel <- system.time({
  fit_fast <- lm.fit(x = X_mat, y = y_vec)
})

cat(sprintf("Waktu Eksekusi lm() Formula: %.3f detik\n", time_formula["elapsed"]))
cat(sprintf("Waktu Eksekusi lm.fit() Raw : %.3f detik\n", time_lowlevel["elapsed"]))
cat(sprintf("Faktor Akselerasi: %.2fx lebih cepat\n", 
            time_formula["elapsed"] / time_lowlevel["elapsed"]))
```

---

## SEKSI 16 — KEAMANAN & HARDENING

Model statistik yang di-deploy ke lingkungan enterprise rentan terhadap sejumlah vektor serangan komputasi dan integritas:

### 1. Sanitasi Dynamic Formula Execution (Formula Injection)
Jangan pernah membangun formula statistik menggunakan penggabungan string yang berasal langsung dari input antarmuka API publik tanpa validasi whitelist ketat:
```r
# KERENTANAN (VULNERABLE):
# Input pengguna dari payload JSON: user_input <- "x1; system('rm -rf /')"
# parsed_form <- as.formula(paste("y ~", user_input)) 
# R dapat mengeksekusi ekspresi berbahaya saat evaluasi formula.

# REMEDIASI KOKOH (HARDENED):
safe_variable_whitelist <- c("age", "dscr", "leverage", "liquidity")

sanitize_and_build_formula <- function(response_var, input_predictors) {
  # 1. Validasi karakter alfanumerik legal
  if (!grepl("^[a-zA-Z0-9_]+$", response_var)) {
    stop("Security Violation: Nama respons tidak valid!")
  }
  
  # 2. Whitelist enforcement
  clean_preds <- intersect(input_predictors, safe_variable_whitelist)
  if (length(clean_preds) == 0) {
    stop("Security Violation: Tidak ada variabel input yang sah.")
  }
  
  # 3. Rekonstruksi formula terisolasi
  reformulate(termlabels = clean_preds, response = response_var)
}
```

### 2. Serialisasi Objek Model yang Aman
- **Risiko**: Menyimpan model menggunakan format `save()` atau `saveRDS()` R membawa risiko eksekusi kode acak (*Arbitrary Code Execution*). R environments membundel enclosure fungsi yang dapat dimodifikasi oleh aktor ancaman jika file `.rds` disusupi di storage bucket.
- **Mitigasi**: Di pipeline modern, serialisasikan model menggunakan format terbuka standar seperti ONNX (Open Neural Network Exchange) via package atau ekspor koefisien numerik dan metadata dalam format terisolasi seperti JSON/Protocol Buffers untuk inference engine statis.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Implementasikan pemantauan runtime komprehensif untuk mendeteksi degradasi model di sistem scoring:

```r
# ==============================================================================
# Script: statistical_observability_suite.R
# ==============================================================================

audit_inference_call <- function(fitted_model, new_data, threshold_cooks = 1.0) {
  start_ts <- Sys.time()
  
  # 1. Logging Validasi Dimensi dan Input
  n_incoming <- nrow(new_data)
  if (n_incoming == 0) {
    stop(paste(Sys.time(), "[LOG-ERROR]: Payload data baru berukuran 0 baris."))
  }
  
  # 2. Deteksi Nilai Tak Terduga (Unseen Levels pada Kategorikal)
  terms_model <- terms(fitted_model)
  factor_vars <- names(fitted_model$xlevels)
  
  for (f in factor_vars) {
    if (f %in% colnames(new_data)) {
      unseen <- setdiff(unique(new_data[[f]]), fitted_model$xlevels[[f]])
      if (length(unseen) > 0) {
        warning(sprintf(
          "%s [LOG-WARN]: Level baru terdeteksi pada faktor '%s': [%s]. Prediksi akan gagal.",
          Sys.time(), f, paste(unseen, collapse = ", ")
        ))
      }
    }
  }
  
  # 3. Prediksi Linear & Standar Eror Estimasi Titik
  preds <- predict(fitted_model, newdata = new_data, se.fit = TRUE)
  
  # 4. Deteksi Leverage Outlier (Hat Matrix Diag Extrapolation)
  X_new <- model.matrix(delete.response(terms_model), data = new_data)
  qr_original <- fitted_model$qr
  
  # Evaluasi se.fit: Rasio SE mengindikasikan ekstrapolasi ekstrim
  high_uncertainty_idx <- which(preds$se.fit > (3.0 * mean(preds$se.fit, na.rm = TRUE)))
  if (length(high_uncertainty_idx) > 0) {
    cat(sprintf("%s [LOG-METRIC]: %d observasi teridentifikasi sebagai ekstrapolasi berisiko tinggi.\n",
                Sys.time(), length(high_uncertainty_idx)))
  }
  
  duration <- as.numeric(difftime(Sys.time(), start_ts, units = "secs"))
  cat(sprintf("%s [LOG-INFO]: Scoring %d baris selesai dalam %.4f detik.\n", 
              Sys.time(), n_incoming, duration))
  
  return(data.frame(
    predicted_score = preds$fit,
    std_error = preds$se.fit,
    high_extrapolation_flag = (preds$se.fit > (3.0 * mean(preds$se.fit, na.rm = TRUE)))
  ))
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────┐
│                  R STATISTICAL MODELING CHEAT SHEET                        │
└────────────────────────────────────────────────────────────────────────────┘
 1. OPERASI DASAR FORMULA
    y ~ x1 + x2             : Tanpa interaksi (Additive Model)
    y ~ x1 * x2             : Interaksi penuh (x1 + x2 + x1:x2)
    y ~ (x1 + x2 + x3)^2    : Seluruh interaksi ordo ke-2
    y ~ x1 - 1              : Regresi tanpa intercept (Zero-intercept)
    y ~ I(x1^2)             : Isolasi ekspresi matematis (bukan sintaks formula)

 2. EKSTRAKSI KOMPONEN NUMERIK
    model.frame(f, data)    : Menghasilkan dataframe yang disaring sesuai terms
    model.matrix(f, data)   : Menghasilkan Full Rank / Dummy Matriks Desain (X)
    qr(X)                   : Eksekusi Householder QR Factorization
    qr.coef(qr(X), y)       : Menghitung beta vector tanpa inversi eksplisit

 3. DIAGNOSTIK KINERJA & KESTABILAN
    svd(X)$d                : Ekstraksi singular values -> max(d)/min(d) = Condition Num
    rstandard(fit)          : Standardized residuals (Variance = 1)
    cooks.distance(fit)     : Identifikasi influential points (Threshold: D > 4/n)
    car::vif(fit)           : Variance Inflation Factor (> 5: Waspada, > 10: Bahaya)

 4. INFERENSI KOKOH (ROBUST SUITE)
    sandwich::vcovHC(fit, "HC3") : Estimasi kovariansi robust koreksi leverage tinggi
    sandwich::vcovHAC(fit)       : Koreksi heteroskedastisitas & autokorelasi beruntun
    lmtest::coeftest(fit, vcov.) : Rekalkulasi t-test/z-test dengan matriks kovariansi robust
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Pertanyaan**: Mengapa implementasi internal `stats::lm` menggunakan Dekomposisi QR daripada langsung menghitung $(X^T X)^{-1} X^T y$ via inversi matriks?
   - *A*: Dekomposisi QR menghemat ruang memori hingga 50% dibandingkan alokasi vektor residual biasa.
   - *B*: Inversi langsung $X^T X$ menguadratkan angka kondisi (*condition number*), yang dapat memicu pembatalan katastrofik (*catastrophic cancellation*) dan galat numerik IEEE 754 floating-point.
   - *C*: Operasi perkalian $(X^T X)^{-1}$ tidak didukung oleh pustaka LAPACK/BLAS tingkat rendah.
   - *D*: Algoritma QR hanya berfungsi jika matriks $X$ bertipe sparse, sehingga lebih cepat dieksekusi.
   *Jawaban*: **B**.

2. **Pertanyaan**: Apa konsekuensi struktural jika Anda menulis formula `y ~ x1 + I(x1^2)` tanpa menggunakan operator pembungkus `I()` (menjadi `y ~ x1 + x1^2`)?
   - *A*: Terjadi kesalahan sintaksis fatal (*Syntax Error*) dan eksekusi R terhenti.
   - *B*: R menginterpretasikan `^2` sebagai simbol ekspansi interaksi formula, bukan operasi pemangkatan numerik, sehingga `x1^2` disederhanakan kembali menjadi `x1`.
   - *C*: R secara otomatis mengonversi variabel `x1` menjadi matriks kuadrat dua dimensi.
   - *D*: Koefisien parameter kuadratik akan selalu diinisialisasi dengan angka nol.
   *Jawaban*: **B**.

3. **Pertanyaan**: Dalam regresi linier OLS klasik dengan heteroskedastisitas galat, bagaimana karakteristik penaksir koefisien titik $\hat{\beta}$ dan galat bakunya (*standard error*)?
   - *A*: $\hat{\beta}$ menjadi bias, dan standard error menjadi bias ke atas (*overestimated*).
   - *B*: $\hat{\beta}$ tetap tak bias (*unbiased*), namun standard error konvensional menjadi bias dan tidak valid untuk uji hipotesis.
   - *C*: $\hat{\beta}$ menjadi inkonsisten, namun uji t tetap valid secara asimtotik.
   - *D*: $\hat{\beta}$ dan standard error kedua-duanya menjadi konvergen ke parameter nol.
   *Jawaban*: **B**.

4. **Pertanyaan**: Fungsi apa yang digunakan secara langsung oleh engine R untuk mempercepat kalkulasi operasi $X^T X$ dengan efisiensi memori optimal tanpa membuat salinan transposisi sementara?
   - *A*: `t(X) %*% X`
   - *B*: `crossprod(X)`
   - *C*: `tcrossprod(X)`
   - *D*: `outer(X, X)`
   *Jawaban*: **B**.

5. **Pertanyaan**: Apa yang ditunjukkan oleh nilai Variance Inflation Factor (VIF) sebesar $12.5$ pada sebuah prediktor?
   - *A*: Variabel tersebut memiliki korelasi negatif yang signifikan terhadap respons.
   - *B*: Variansi estimasi koefisien prediktor tersebut melambung $12.5$ kali lipat akibat kolinearitas dengan prediktor lain dalam model.
   - *C*: Residual model memiliki tingkat dispersi $12.5$ kali lebih besar dari distribusi Poisson standar.
   - *D*: Tingkat signifikansi koefisien (p-value) meningkat sebesar $12.5\%$.
   *Jawaban*: **B**.

---

### Soal Tingkat Menengah (Intermediate)

6. **Pertanyaan**: Saat melatih Generalized Linear Model (GLM) keluarga Binomial dengan data imbalanced ekstrem, Anda mendapati estimasi koefisien salah satu fitur bernilai $24.8$ dengan Standard Error sebesar $4210.5$. Fenomena apa yang sedang terjadi dan apa mitigasi matematisnya?
   - *A*: Terjadi *Underdispersion*; gunakan penyesuaian quasi-binomial.
   - *B*: Terjadi *Complete/Quasi-Complete Separation*; selesaikan menggunakan estimasi penalized likelihood (Metode Firth).
   - *C*: Matriks desain mengalami ketiadaan intercept; tambahkan level kontras dummy.
   - *D*: Derajat kebebasan residual bernilai nol; hapus setengah variabel prediktor.
   *Jawaban*: **B**.

7. **Pertanyaan**: Mengapa estimasi variansi sandwich tipe **HC3** lebih disarankan untuk dataset berskala kecil hingga menengah dibandingkan estimator **HC0** White klasik?
   - *A*: HC3 menggunakan matriks identitas terbobot konstan untuk menyerap autokorelasi residual.
   - *B*: HC3 memodifikasi bobot residual kuadrat dengan membaginya dengan $(1 - h_{ii})^2$, memberikan koreksi superior terhadap pengaruh titik ber-leverage tinggi.
   - *C*: HC3 mengeksekusi bootstrap parametrik ribuan kali di belakang layar secara otomatis.
   - *D*: HC0 secara matematis tidak mampu menangani data yang memiliki multikolinearitas moderat.
   *Jawaban*: **B**.

8. **Pertanyaan**: Pada arsitektur runtime microservice R, mengapa menyimpan objek model utuh via `saveRDS(fit_lm, "model.rds")` dapat menyebabkan kebocoran memori (leakage) yang masif ketika file dibaca kembali?
   - *A*: Objek `lm` menyimpan referensi pointer C++ yang dialokasikan di luar area memory management R.
   - *B*: Lingkungan lexical (`environment`) tempat formula didefinisikan ikut diserialisasikan ke dalam file RDS, membundel variabel lingkungan lokal ke disk.
   - *C*: Komponen matriks $Q$ dari dekomposisi QR mengalami inflasi ukuran file sebesar $8\times$ saat proses kompresi gzip.
   - *D*: RDS secara otomatis mengekstrak seluruh data historis dari sesi global R ke dalam format biner.
   *Jawaban*: **B**.

9. **Pertanyaan**: Perhatikan cuplikan eksekusi berikut:
   ```r
   m <- lm(y ~ x, data = df)
   environment(m$terms) <- baseenv()
   ```
   Apa tujuan utama dari manipulasi environment di atas sebelum deployment model ke cloud container?
   - *A*: Mengizinkan model mengakses pustaka eksternal di direktori `/usr/local/lib`.
   - *B*: Memutuskan referensi parent lexical frame dari formula agar garbage collector dapat membersihkan memori dataset training yang besar.
   - *C*: Mempercepat operasi prediksi matriks hingga 100 kali lipat pada arsitektur ARM64.
   - *D*: Mengubah skema kontras bawaan variabel bertipe faktor menjadi numerik ordinal.
   *Jawaban*: **B**.

10. **Pertanyaan**: Jika angka kondisi (*Condition Index*) dari matriks desain terskala bernilai $85.0$, risiko numerik apa yang dihadapi sistem inferensi statistik?
    - *A*: Estimasi deviance Poisson akan menghasilkan angka imajiner kompleks.
    - *B*: Matriks mendekati singularitas parah; perturbasi kecil pada vektor respons $y$ dapat memicu perubahan drastis pada magnitudo dan tanda koefisien $\hat{\beta}$.
    - *C*: Uji Durbin-Watson akan selalu menolak hipotesis nol autokorelasi residual.
    - *D*: Derajat kebebasan residual terhitung melebihi batas integer 32-bit di engine R.
    *Jawaban*: **B**.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek:
Anda ditugaskan merancang paket pustaka internal institusi: **`EnterpriseRobustLM`**. Modul ini harus menjadi wrapper komputasi linear inference enterprise yang memproses jutaan baris data secara efisien, bebas kebocoran memori, kebal terhadap multikolinearitas dan heteroskedastisitas, serta menyediakan S3 diagnostic methods lengkap.

### Spesifikasi Teknis yang Wajib Dipenuhi:

1. **Arsitektur Objek & Input Safety**:
   - Fungsi utama: `fit_enterprise_lm(formula, data, robust_type = c("HC0", "HC1", "HC3"))`.
   - Sanitasi nama prediktor dari regex berbahaya (`[^a-zA-Z0-9_.]`).
   - Ekstraksi matriks menggunakan `model.frame` dan `model.matrix` dengan pemutusan otomatis *formula environment* (`baseenv()`) untuk proteksi memori GC.

2. **Core Computational Engine**:
   - Jika rank matriks desain lebih kecil dari jumlah kolom prediktor ($p$), fungsi harus membuang kolom yang teridentifikasi aliased/singular secara otomatis tanpa melempar fatal error, lalu mencatat log peringatan.
   - Eksekusi parameter fitting menggunakan LAPACK QR factorization native.
   - Hitung nilai VIF dan Matrix Condition Index secara internal.

3. **Inference Suite**:
   - Hitung Robust Covariance Matrix Sandwich berdasarkan argumen yang dipilih pengguna (`HC0`, `HC1`, atau `HC3`).
   - Bangun struktur tabel output yang mencakup: `Estimate`, `Robust_SE`, `t_value`, `p_value`, `VIF`, dan `Leverage_Cooks_D`.

4. **S3 Interface Implementation**:
   - Buat implementasi metode formal S3:
     - `print.enterprise_lm`: Menampilkan ringkasan ringkas dan peringatan kesehatan matriks (*health checks*).
     - `summary.enterprise_lm`: Menampilkan tabel koefisien robust lengkap dengan derajat kebebasan dan matriks korelasi koefisien.
     - `predict.enterprise_lm`: Menyediakan estimasi respons data baru dengan flag diagnostik otomatis jika nilai prediktor data baru berada di luar batas convex hull data latih (*High Leverage Extrapolation Alert*).

### Verifikasi Hasil:
Ujilah modul buatan Anda menggunakan data sintetis dengan $N = 200,000$ baris, 8 variabel prediktor dengan korelasi tinggi antar dua variabel prediktor ($r > 0.95$), dan galat heteroskedastik kuadratik. Pastikan seluruh alur eksekusi selesai di bawah rentang waktu 3 detik, stabil secara numerik, dan tidak menyisakan memory overhead pada heap RAM.