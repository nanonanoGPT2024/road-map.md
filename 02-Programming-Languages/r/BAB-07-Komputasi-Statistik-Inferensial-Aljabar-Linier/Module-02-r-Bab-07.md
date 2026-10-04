# BAB 07: Komputasi Statistik Inferensial & Aljabar Linier
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Mendiagnosis, mengonfigurasi, dan mengoptimalkan subsistem aljabar linier R tingkat kernel (*BLAS/LAPACK backend*) pada arsitektur server produksi Linux Enterprise.
*   Mengimplementasikan dekomposisi matriks tingkat lanjut ($QR$, Cholesky, SVD) untuk menyelesaikan komputasi statistik inferensial terdistribusi secara stabil tanpa degradasi numerik (*floating-point catastrophic cancellation*).
*   Merancang dan mengoperasikan *pipeline* pemodelan linier dan inferensi multivariat berskala besar menggunakan representasi *sparse matrix* (`Matrix::dgCMatrix`) dengan efisiensi memori tingkat tinggi.
*   Mengisolasi dan memitigasi *race condition* serta *thread oversubscription* pada integrasi antara *OpenMP multithreading BLAS* dan paralelisasi proses R (`parallel`, `future`).
*   Membangun *robust covariance estimation engine* (sandwich estimators, bootstrap) yang siap produksi (*fault-tolerant*, deterministik, dan teruji secara performa).

---

### 2. Prerequisite
*   **Sistem Komputer & Runtime:** Pemahaman mendalam mengenai arsitektur x86_64, hirarki *cache* CPU (L1/L2/L3), *SIMD vectorization* (AVX-2, AVX-512), dan manajemen memori OS Linux (glibc allocator, swap, *dirty pages*).
*   **Matematika & Statistik:** Aljabar linier matriks intermediate (invertibilitas, rank matriks, ortogonalitas, *positive-definiteness*), kalkulus multivariat, dan statistik inferensial (OLS, WLS, *sandwich variance-covariance estimation*).
*   **R Internals:** Pemahaman struktur data internal R C API (`SEXP`, `REALSXP`), pointer, *copy-on-modify semantics*, serta pengenalan framework `ALTREP`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Tata Letak Memori Matriks di R (Column-Major Order & SEXP)
R mengalokasikan matriks sebagai vektor primitif 1D bertipe `REALSXP` (untuk bilangan real *double precision* 64-bit IEEE 754) di dalam *heap* memori R, yang dikelola oleh *Garbage Collector* (GC). Atribut dimensi `dim` menentukan interpretasi 2D. R menerapkan konvensi **Column-Major** (diwarisi dari Fortran):

$$A_{m \times n} \implies \text{Index}(i, j) = i + (j - 1) \times m \quad (\text{1-based indexing})$$

```
Matrix A (3x2):
      [,1] [,2]
[1,]   10   40
[2,]   20   50
[3,]   30   60

Continuous Memory Layout (Heap):
+------+------+------+------+------+------+
|  10  |  20  |  30  |  40  |  50  |  60  |
+------+------+------+------+------+------+
 0x00   0x08   0x10   0x18   0x20   0x28  (Bytes)
```

Mengakses elemen secara transversal per baris (*row-wise traversal*) menghancurkan lokalitas spasial *CPU cache lines* (64 bytes). Operasi harus didesain untuk berjalan secara *column-wise* guna memaksimalkan *cache-hit* L1/L2.

#### 3.2. Lapisan Abstraksi BLAS dan LAPACK
R tidak mengeksekusi perkalian matriks primitif melalui loop C native. R mendelegasikan komputasi ke BLAS (*Basic Linear Algebra Subprograms*) dan LAPACK (*Linear Algebra Package*):

1.  **BLAS Level 1:** Operasi Vektor-Vektor ($y \leftarrow \alpha x + y$, dot product). Kompleksitas $O(n)$, rasio memori terhadap komputasi tinggi.
2.  **BLAS Level 2:** Operasi Matriks-Vektor ($y \leftarrow \alpha A x + \beta y$). Kompleksitas $O(n^2)$.
3.  **BLAS Level 3:** Operasi Matriks-Matriks ($C \leftarrow \alpha A B + \beta C$, `DGEMM`). Kompleksitas $O(n^3)$, rasio komputasi terhadap transfer memori optimal, sangat cocok untuk blok cache dan paralelisasi SIMD.

Secara *default*, instalasi R menggunakan R Reference BLAS yang berjalan secara *single-threaded* dan tidak memanfaatkan instruksi modern x86. Pada arsitektur produksi, pustaka dinamis `libRblas.so` harus di-*link* secara dinamis ke implementasi teroptimasi:
*   **OpenBLAS:** Kernel open-source yang dioptimalkan per arsitektur mikro CPU.
*   **Intel oneAPI MKL (Math Kernel Library):** Teroptimasi penuh untuk arsitektur Intel dengan dukungan AVX-512 dan paralelisasi hybrid OpenMP.

```
+---------------------------------------------------------------+
|                       User Script (R)                        |
|                  X %*% Y     |     solve(A, b)                |
+---------------------------------------------------------------+
                               |
                               v
+---------------------------------------------------------------+
|                 R Engine Runtime (SEXP Layer)                 |
|               src/main/array.c: matprod()                     |
+---------------------------------------------------------------+
                               |
                               v
+---------------------------------------------------------------+
|                      R BLAS/LAPACK Wrapper                     |
|                        (R_Home/lib/libR.so)                   |
+---------------------------------------------------------------+
                               |
        +----------------------+----------------------+
        | Dynamic Link                                | Dynamic Link
        v                                             v
+-------------------------------+             +-------------------------------+
|     libRblas.so (Internal)    |             |      libopenblas.so / MKL     |
|   (Unoptimized, Single-core)  |             | (AVX-512, OpenMP Multi-thread)|
+-------------------------------+             +-------------------------------+
```

#### 3.3. Dekomposisi Numerik vs. Inversi Naif
Menghitung estimator OLS secara naif:

$$\hat{\beta} = (X^T X)^{-1} X^T y$$

Melakukan komputasi eksplisit $(X^T X)^{-1}$ adalah anti-pattern kritis:
1.  **Kondisi Matriks Memburuk (*Condition Number Squaring*):**
    $$\kappa(X^T X) = (\kappa(X))^2$$
    Jika $\kappa(X) = 10^8$, maka $\kappa(X^T X) = 10^{16}$. Pada sistem IEEE 754 *double-precision* (presisi $\approx 15-17$ digit desimal), seluruh signifikansi numerik hilang menjadi noise pembulatan (*catastrophic cancellation*).
2.  **Efisiensi Dekomposisi QR:**
    $X$ difaktorkan menjadi $Q R$, di mana $Q \in \mathbb{R}^{n \times p}$ adalah matriks ortogonal ($Q^T Q = I$), dan $R \in \mathbb{R}^{p \times p}$ adalah segitiga atas (*upper triangular*).
    $$X^T X = (Q R)^T (Q R) = R^T Q^T Q R = R^T R$$
    $$X^T y = R^T Q^T y$$
    Persamaan normal menjadi:
    $$R^T R \hat{\beta} = R^T Q^T y \implies R \hat{\beta} = Q^T y$$
    Karena $R$ adalah segitiga atas, $\hat{\beta}$ diselesaikan melalui substitusi balik (*back-substitution*) menggunakan LAPACK `DTRTRS` dengan kompleksitas $O(p^2)$, tanpa menginversikan matriks secara eksplisit dan menjaga stabilitas kondisi pada $\kappa(X)$.

#### 3.4. Arsitektur Matriks Jarang (Sparse Matrix) `dgCMatrix`
Untuk sistem berdimensi tinggi ($p \gg 10.000$) di mana fraksi elemen bernilai nol $> 95\%$, alokasi *dense* membutuhkan memori masif ($O(n \times p)$). Format CSC (*Compressed Sparse Column*) pada paket `Matrix` (`dgCMatrix`) mengkompresi struktur data menjadi 3 vektor internal:
*   `x`: Vektor real (tipe `double`) penyimpan elemen non-nol, panjang $nnz$ (*number of non-zeros*).
*   `i`: Vektor integer (0-based) penyimpan indeks baris dari tiap elemen di `x`, panjang $nnz$.
*   `p`: Vektor integer indeks awal kolom pada vektor `x` dan `i`, panjang $ncols + 1$.

```
Dense Matrix (4x4):
[1.0,  0.0,  0.0,  2.0]
[0.0,  3.0,  0.0,  0.0]
[0.0,  0.0,  0.0,  4.0]
[5.0,  0.0,  0.0,  0.0]

Representasi dgCMatrix (CSC):
p: [0, 2, 3, 3, 5]     -> Kolom 0 mulai idx 0, Kol 1 idx 2, Kol 2 idx 3 (kosong), Kol 3 idx 3
i: [0, 3, 1, 0, 2]     -> Baris: (Col 0: baris 0, 3), (Col 1: baris 1), (Col 3: baris 0, 2)
x: [1.0, 5.0, 3.0, 2.0, 4.0] -> Nilai non-nol
```

---

### 4. Why & What

| Pendekatan | Mekanisme | Kompleksitas Waktu | Stabilitas Numerik | Konsumsi Memori |
| :--- | :--- | :--- | :--- | :--- |
| **Inversi Naif**<br>`solve(t(X) %*% X) %*% t(X) %*% y` | Menghitung perkalian luar lalu inversi penuh | $O(n p^2 + p^3)$ | **Sangat Buruk**<br>$\kappa(X^T X) = \kappa(X)^2$ | $O(p^2)$ *dense allocation* |
| **Cholesky Factorization**<br>`chol(t(X) %*% X)` | Faktorisasi $L L^T$ matriks simetris definit-positif | $O(n p^2 + \frac{1}{3} p^3)$ | **Moderat**<br>Sensitif terhadap matriks *near-singular* | $O(p^2)$ intermediate buffer |
| **QR Decomposition**<br>`qr.solve(X, y)` | Faktorisasi Householder orthogonal-triangular | $O(2 n p^2 - \frac{2}{3} p^3)$ | **Sangat Baik**<br>Presisi terjaga hingga batas mesin | $O(n p)$ in-place transformation |
| **Singular Value Dec. (SVD)**<br>`svd(X)` | Faktorisasi $U \Sigma V^T$ | $O(4 n p^2 + 8 p^3)$ | **Maksimal**<br>Mendeteksi singularitas sempurna | $O(n p + p^2)$ |

*   **Mengapa ini penting?** Dalam lingkungan komputasi berkecepatan tinggi, kegagalan numerik tidak selalu memicu *exception/error*. Seringkali kegagalan muncul dalam bentuk *silent corruption*: nilai koefisien melenceng secara subtil, p-value menjadi tidak valid (*false positive inferential conclusion*), atau estimasi kovariansi menghasilkan varians negatif.
*   **Apa solusinya?** Arsitektur komputasi statistik harus mengabstraksi penanganan aljabar linier dengan aturan deterministik: memvalidasi *condition number*, memanfaatkan *pivoting*, memilih algoritma dekomposisi berbasis densitas data, serta mengisolasi pemanggilan komputasi matriks pada subsistem BLAS yang terkonfigurasi optimal.

---

### 5. How (Workflow Detail)

Alur kerja arsitektur inferensi statistik tingkat lanjut berkinerja tinggi mengikuti tahapan berikut:

```
[Input Design Matrix X, Vector y]
               |
               v
 [Dimensi & Densitas Spasial Matrix]
    |                          |
    | (Sparsity > 90%)         | (Dense / Modest Sparsity)
    v                          v
[Convert ke dgCMatrix]     [Validasi Memori Alokasi (SEXP Size)]
    |                          |
    +------------+-------------+
                 |
                 v
   [Estimasi Kondisi Matrix (rcond)]
                 |
        +--------+--------+
        |                 |
(rcond < 1e-12)    (rcond >= 1e-12)
        |                 |
        v                 v
[Regularisasi/SVD]   [Pilih Dekomposisi]
(Ridge/Truncated)         |
        |                 +-----------------------+
        |                 |                       |
        |           (n >= p)                    (n < p)
        |                 v                       v
        |           [QR Factorization]       [Cholesky Kernel / Dual]
        |           (Householder)            (XtX + lambda*I)
        +-----------------+-----------------------+
                          |
                          v
         [Solve Triangular System (Backsolve)]
                          |
                          v
      [Ekstraksi Inferensi: Residuals & Degrees of Freedom]
                          |
                          v
   [Robust Covariance Engine: Sandwich Estimator (HC0-HC3)]
                          |
                          v
   [Output: Coefficients, SE, t-stat, p-values, CI]
```

1.  **Ingestion & Profiling:** Analisis rasio *sparsity* (jumlah nol terhadap total entri). Jika di atas ambang batas (default: 85%), konversikan ke format kompresi kolom sparse.
2.  **Pemeriksaan Resiprokal Kondisi:** Evaluasi kepekaan numerik melalui estimasi resiprokal kondisi LAPACK (`rcond`). Hindari fungsi `kappa()` yang mahal ($O(p^3)$) di lingkungan berlatensi rendah.
3.  **Branching Dekomposisi:** Tentukan rute faktorisasi. Bila matriks bertipe sparse, manfaatkan algoritma SuiteSparse (CHOLMOD/SPQR). Bila dense, arahkan ke LAPACK `dgeqp3` (QR dengan *column pivoting*) atau `dposv` (Cholesky).
4.  **Inferential Derivation:** Turunkan matriks proyeksi tanpa membentuk matriks topi (*Hat Matrix*) $H = X(X^T X)^{-1}X^T$ secara utuh di memori (konsumsi memori $H$ adalah $O(n^2)$, fatal untuk $n = 1.000.000$).
5.  **Robust Post-Estimation:** Terapkan koreksi heteroskedastisitas (*sandwich covariance matrix*) melalui evaluasi residual terbobot vektor-ke-matriks.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rel Kereta Logistik vs. Truk Gandeng Bebas Hambatan
*   **Inversi Matriks Naif:** Seperti memindahkan kargo dengan membalikkan arah seluruh rangkaian kereta api di rel tunggal yang sempit; rawan tabrakan antar-gerbong (presisi numerik hancur akibat *rounding error* kumulatif) dan membutuhkan stasiun pemutar super raksasa (alokasi memori $O(n^3)$).
*   **Faktorisasi QR / Cholesky:** Seperti memisahkan kontainer kargo ke jalur cabang segitiga yang dirancang khusus. Setiap gerbong didorong secara bertahap satu per satu dari atas ke bawah (*back-substitution*); proses cepat, teratur, deterministik, dan bebas risiko tabrakan data.

#### Interaksi Sub-Sistem Hardware & Software
```
+-----------------------------------------------------------------------+
| USER SPACE (Linux x86_64)                                             |
|                                                                       |
|  R Process (PID: 40921)                                               |
|  +-----------------------------------------------------------------+  |
|  | Global Environment                                              |  |
|  | X: [Matrix, 500000 x 50] -> SEXP Data Buffer (200 MB)          |  |
|  +-----------------------------------------------------------------+  |
|         |                                                             |
|         | Calls: .Internal(qr(...)) / LAPACK Wrapper                  |
|         v                                                             |
|  +-----------------------------------------------------------------+  |
|  | libopenblas.so.0 / libmkl_rt.so                                 |  |
|  |                                                                 |  |
|  | Thread Pool Control (OMP_NUM_THREADS=8)                         |  |
|  |   Worker 1: Worker 2: Worker 3: ... : Worker 8                  |  |
|  +-----------------------------------------------------------------+  |
+---------|----------|----------|------------|--------------------------+
          |          |          |            |
+---------v----------v----------v------------v--------------------------+
| CPU EXECUTION REGISTERS & HARDWARE CACHE                              |
|                                                                       |
|  +-----------------------+   +-----------------------+                |
|  | Core 0: AVX-512 FMA   |   | Core 1: AVX-512 FMA   |                |
|  | [512-bit Vector Regs] |   | [512-bit Vector Regs] |  ... 8 Cores   |
|  +-----------------------+   +-----------------------+                |
|              ^                           ^                            |
|              +-------------+-------------+                            |
|                            | Prefetch Data Line                       |
|  +-----------------------------------------------------------------+  |
|  | L3 Cache Block (Shared, 32MB)                                   |  |
|  | Cache-aware Matrix Tiling Blocks (dgTiled)                      |  |
|  +-----------------------------------------------------------------+  |
|                            ^                                          |
|                            | DRAM Fetch via Memory Controller Bus     |
|  +-----------------------------------------------------------------+  |
|  | System RAM (DDR4/DDR5 ECC Channel)                             |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi Catastrophic Cancellation
Contoh ini mendemonstrasikan bagaimana pembentukan $X^T X$ secara naif merusak estimasi regresi pada matriks Hilbert bergejala multikolinearitas ekstrem.

```r
# simple_numerical_instability.R
# Demonstrasi instabilitas numerik: Inversi Naif vs QR Decomposition

set.seed(42)

# Buat matriks prediktor yang hampir ill-conditioned (Hilbert-like block)
n <- 100
p <- 10
X <- matrix(rnorm(n * p), nrow = n, ncol = p)

# Tambahkan korelasi ekstrem pada kolom terakhir
X[, p] <- X[, 1] + X[, 2] + 1e-8 * rnorm(n)

# Ground truth beta
true_beta <- matrix(seq(1, p), ncol = 1)
y <- X %*% true_beta + rnorm(n, sd = 0.01)

# 1. Pendekatan Naif: Inversi Eksplisit (X^T * X)^-1
beta_naive <- tryCatch({
  XtX <- t(X) %*% X
  rcond_XtX <- rcond(XtX)
  message(sprintf("[WARN] Reciprocal condition XtX: %.18e", rcond_XtX))
  solve(XtX) %*% t(X) %*% y
}, error = function(e) {
  message(paste("[FAIL] Inversi Naif Gagal:", e$message))
  return(rep(NA, p))
})

# 2. Pendekatan Industri: QR Decomposition (via qr.solve)
qr_decomp <- qr(X)
beta_qr <- qr.solve(qr_decomp, y)

# Evaluasi Relative Error terhadap Ground Truth
calc_rel_error <- function(est, truth) {
  sqrt(sum((est - truth)^2)) / sqrt(sum(truth^2))
}

cat("\n=== HASIL PERBANDINGAN NUMERIK ===\n")
cat(sprintf("Relative Error (Naif) : %.10e\n", calc_rel_error(beta_naive, true_beta)))
cat(sprintf("Relative Error (QR)   : %.10e\n", calc_rel_error(beta_qr, true_beta)))
```

#### 7.2. Practical Example: Production-Grade Robust Inference Engine
Implementasi mesin inferensi linier dengan sandwich covariance matrix (koreksi heteroskedastisitas Huber-White HC1), dukungan matriks jarang, *numerical guardrail*, dan memori terkontrol.

```r
# robust_inference_engine.R

suppressPackageStartupMessages({
  library(Matrix)
})

#' Production Grade Inferential Linear Regression Engine
#' 
#' @param y Vector target numeric (n x 1)
#' @param X Matrix prediktor (dense atau sparse dgCMatrix)
#' @param fit_intercept Logical, apakah menambahkan kolom intercept secara otomatis
#' @param tol_rcond Batas toleransi resiprokal kondisi matriks
#' @return List berisi model statistics, coefficients, standard errors, p-values
fit_robust_ols <- function(y, X, fit_intercept = TRUE, tol_rcond = 1e-12) {
  # 1. Input Validation and Assertions
  stopifnot(is.numeric(y) || is.vector(y), length(y) > 0)
  stopifnot(is.matrix(X) || inherits(X, "sparseMatrix"))
  
  n <- length(y)
  
  if (fit_intercept) {
    if (inherits(X, "sparseMatrix")) {
      X <- cbind2(Matrix(1, nrow = n, ncol = 1, sparse = TRUE), X)
      colnames(X)[1] <- "(Intercept)"
    } else {
      X <- cbind(1, X)
      colnames(X)[1] <- "(Intercept)"
    }
  }
  
  p <- ncol(X)
  if (n <= p) {
    stop(sprintf("Degrees of freedom invalid: n (%d) harus lebih besar dari p (%d)", n, p))
  }
  
  df_residual <- n - p
  
  # 2. Structural Branching: Sparse vs Dense Engine
  is_sparse <- inherits(X, "sparseMatrix")
  
  if (is_sparse) {
    # Ensure optimal Compressed Sparse Column (CSC)
    X <- as(X, "dgCMatrix")
    
    # Cross-product Cholesky factorization via SuiteSparse CHOLMOD
    # P * (X'X) * P' = L * L'
    XtX <- Matrix::crossprod(X)
    
    # Condition checking on sparse matrix representation
    # Menggunakan estimasi norma berbasis LAPACK
    norm_XtX <- Matrix::norm(XtX, "1")
    # Menggunakan faktorisasi Cholesky untuk estimasi determinan & kondisi
    chol_factor <- tryCatch({
      Matrix::Cholesky(XtX, Imult = 0, LDL = FALSE)
    }, error = function(e) {
      stop(sprintf("Matriks singularitas terdeteksi pada sparse Cholesky: %s", e$message))
    })
    
    Xty <- Matrix::crossprod(X, y)
    beta <- Matrix::solve(chol_factor, Xty)
    beta_vec <- as.vector(as.matrix(beta))
    
    # Hitung Residual
    fitted_vals <- as.vector(X %*% beta)
    residuals <- y - fitted_vals
    
    # 3. Robust Sandwich Variance Estimator (HC1) - Sparse Pipeline
    # Cov = (X'X)^-1 * [X' * diag(res^2) * X] * (X'X)^-1 * (n / (n - p))
    # Optimal memory: Hitung Middle Matrix tanpa alokasi diag matrix besar
    omega_diag <- residuals^2
    # Scaling baris matrix X secara in-place via sparse vector multiplication
    X_omega <- X * sqrt(omega_diag)
    middle_matrix <- Matrix::crossprod(X_omega)
    
    # Inversi terfaktor: solve(chol_factor, middle_matrix)
    inv_XtX_middle <- Matrix::solve(chol_factor, middle_matrix)
    cov_matrix <- Matrix::solve(chol_factor, Matrix::t(inv_XtX_middle)) * (n / df_residual)
    
    vcov_matrix <- as.matrix(cov_matrix)
    
  } else {
    # DENSE PATHWAY: Menggunakan Householder QR Decomposition
    rc <- rcond(X)
    if (is.na(rc) || rc < tol_rcond) {
      stop(sprintf("Matrix Design Ill-Conditioned terdeteksi! rcond = %.5e < tol = %.5e", 
                   rc, tol_rcond))
    }
    
    # In-place QR factorization
    qr_obj <- qr(X, LAPACK = TRUE)
    beta_vec <- qr.coef(qr_obj, y)
    
    # Cek rank deficiency
    if (qr_obj$rank < p) {
      warning(sprintf("Rank deficiency terdeteksi: Rank %d < Total Kolom %d", qr_obj$rank, p))
    }
    
    fitted_vals <- as.vector(X %*% beta_vec)
    residuals <- y - fitted_vals
    
    # Sandwich HC1 (Dense)
    # R^-1 calculation
    R <- qr.R(qr_obj)
    # X' * diag(res^2) * X
    X_weighted <- X * (residuals * sqrt(n / df_residual))
    meat <- crossprod(X_weighted)
    
    # bread = (X'X)^-1 = (R' R)^-1 = R^-1 (R^-1)'
    # backsolve menyelesaikan R * inv_R = I
    inv_R <- backsolve(R, diag(p))
    bread <- tcrossprod(inv_R)
    
    vcov_matrix <- bread %*% meat %*% bread
  }
  
  # 4. Statistical Inference Extraction
  se_beta <- sqrt(diag(vcov_matrix))
  t_stats <- beta_vec / se_beta
  p_values <- 2 * (1 - pt(abs(t_stats), df = df_residual))
  
  # Format Summary Data Frame
  coef_table <- data.frame(
    Estimate   = beta_vec,
    Std_Error  = se_beta,
    t_value    = t_stats,
    p_value    = p_values,
    CI_Lower   = beta_vec - qt(0.975, df = df_residual) * se_beta,
    CI_Upper   = beta_vec + qt(0.975, df = df_residual) * se_beta,
    row.names  = if (!is.null(colnames(X))) colnames(X) else paste0("X", seq_len(p))
  )
  
  # Compute Global Metrics
  rss <- sum(residuals^2)
  tss <- sum((y - mean(y))^2)
  r_squared <- 1 - (rss / tss)
  adj_r_squared <- 1 - ((1 - r_squared) * (n - 1) / df_residual)
  
  result <- list(
    coefficients    = coef_table,
    vcov            = vcov_matrix,
    residuals       = residuals,
    fitted.values   = fitted_vals,
    df_residual     = df_residual,
    r_squared       = r_squared,
    adj_r_squared   = adj_r_squared,
    engine_type     = if (is_sparse) "SuiteSparse_CHOLMOD_HC1" else "LAPACK_QR_HC1"
  )
  
  class(result) <- "robust_ols_model"
  return(result)
}

# Verifikasi Eksekusi Pipeline
if (sys.nframe() == 0) {
  # Simulasi data dengan heteroskedastisitas struktural
  n_obs <- 20000
  p_feats <- 15
  
  X_raw <- matrix(rnorm(n_obs * p_feats), nrow = n_obs, ncol = p_feats)
  colnames(X_raw) <- sprintf("feat_%02d", 1:p_feats)
  
  true_w <- c(2.5, runif(p_feats, 0.5, 3.0))
  # Varians residual berbanding lurus dengan kuadrat fitur pertama (Heteroskedastic)
  error_sd <- 0.5 + 1.2 * abs(X_raw[, 1])
  noise <- rnorm(n_obs, mean = 0, sd = error_sd)
  
  y_raw <- 2.5 + X_raw %*% true_w[-1] + noise
  
  start_time <- Sys.time()
  fit_dense <- fit_robust_ols(y_raw, X_raw, fit_intercept = TRUE)
  dense_time <- Sys.time() - start_time
  
  cat(sprintf("[EXECUTION OK] Engine: %s | Time: %.4f s\n", 
              fit_dense$engine_type, as.numeric(dense_time)))
  print(head(fit_dense$coefficients, 5))
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform teknologi finansial (*fintech*) Tier-1 melayani 5.000.000 pengguna aktif dengan pipeline *risk pricing* dinamis. Sistem wajib melakukan kalibrasi ulang model risiko kredit (*exposure default estimation*) setiap subuh. Matrix desain berisi:
*   $N = 2.000.000$ observasi pinjaman historis.
*   $P = 1.200$ fitur (kombinasi variabel kontinu, *one-hot encoded categorical*, dan interaksi sparse antar-merchant).
*   Sparsity matriks mencapai $96.8\%$.
*   *SLA*: Estimasi koefisien inferensial lengkap (termasuk interval kepercayaan 99% dan *robust standard errors*) harus selesai dalam waktu kurang dari 60 detik dengan penggunaan RAM dibatasi maksimum 16 GB.

Pendekatan terdahulu menggunakan fungsi default `lm()` memicu *Out-Of-Memory (OOM) Killer* sistem operasi Linux pada node 64 GB karena `lm()` mencoba mengonversi matriks sparse menjadi matriks dense dan membentuk *model frame* internal R ganda.

#### Arsitektur Solusi
Arsitektur dirancang menggunakan *Out-of-Core Batching Construction* yang dimuat langsung ke objek `Matrix::dgCMatrix`, kemudian didekomposisi menggunakan modul Cholesky sparse teroptimasi dengan *AMD/OpenBLAS AVX-2 threading*:

```
+--------------------------------------------------------------------------+
| Enterprise Ingestion Layer: PostgreSQL -> Chunked Binary Arrow           |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
| R Master Coordinator (Memory-Bounded: < 16 GB)                           |
|                                                                          |
| 1. Sparse Matrix Instantiation (Direct CSC dgCMatrix generation)         |
|    Total Alloc: ~ 450 MB (jauh lebih hemat vs Dense: 19.2 GB)            |
|                                                                          |
| 2. Set OpenMP Thread Boundary:                                           |
|    RhpcBLASctl::blas_set_num_threads(8)                                  |
|                                                                          |
| 3. High-Performance Normal Equations Formulation:                       |
|    XtX = Matrix::crossprod(X)   -> Symm Sparse (1200 x 1200)             |
|    Xty = Matrix::crossprod(X, y) -> Dense Vec (1200 x 1)                 |
|                                                                          |
| 4. SuiteSparse CHOLMOD Factorization with AMD Ordering                   |
|    P * (XtX + lambda * I) * P' = L * L'                                  |
|                                                                          |
| 5. Chunked Heteroskedasticity-Consistent Bread-Meat Compute             |
|    Parallel Matrix Multiply without Memory Duplication                   |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
| Validation & Audit Gate: Check condition number, NaN coefficients       |
| Push coefficients & SE to HashiCorp Vault / Metadata Model Registry      |
+--------------------------------------------------------------------------+
```

#### Skrip Solusi Produksi

```r
# production_fintech_engine.R

suppressPackageStartupMessages({
  library(Matrix)
  library(RhpcBLASctl)
})

run_fintech_calibration_pipeline <- function(n_obs = 2000000, 
                                            n_dense = 20, 
                                            n_sparse_cats = 1000, 
                                            n_threads = 8) {
  # Isolasi threading level OS
  blas_set_num_threads(n_threads)
  omp_set_num_threads(n_threads)
  
  message(sprintf("[INIT] Menjalankan Pipeline Fintech Risk: N=%d, Threads=%d", n_obs, n_threads))
  
  # 1. Sintesis Matriks Input Sparse Skala Besar (Simulasi Data Warehouse)
  # Di produksi: Baca langsung via Arrow/DuckDB streaming ke triplet (i, j, x)
  set.seed(101)
  
  message("[DATA] Mengalokasikan sparse design matrix...")
  # Simulasikan data transaksi yang sangat sparse
  nnz_per_col <- 10000
  total_sparse_entries <- nnz_per_col * 20 # 20 kolom aktif per user rata-rata
  
  i_idx <- sample(0:(n_obs - 1), total_sparse_entries, replace = TRUE)
  j_idx <- sample(0:(n_sparse_cats - 1), total_sparse_entries, replace = TRUE)
  x_vals <- runif(total_sparse_entries, 0.1, 5.0)
  
  # Bangun direct dgTMatrix -> dgCMatrix tanpa dense intermediary
  sparse_block <- sparseMatrix(
    i = i_idx + 1,
    j = j_idx + 1,
    x = x_vals,
    dims = c(n_obs, n_sparse_cats),
    giveCsparse = TRUE
  )
  
  # Fitur Kontinu (Dense Block)
  dense_block <- matrix(rnorm(n_obs * n_dense), nrow = n_obs, ncol = n_dense)
  dense_sparse <- as(dense_block, "dgCMatrix")
  
  # Gabungkan Prediktor
  X <- cbind2(dense_sparse, sparse_block)
  colnames(X) <- c(sprintf("dense_%02d", 1:n_dense), sprintf("cat_%04d", 1:n_sparse_cats))
  
  p <- ncol(X)
  message(sprintf("[DATA] Dimensi Total: %d baris x %d kolom. Memori: %.2f MB", 
                  nrow(X), p, as.numeric(object.size(X)) / 1024^2))
  
  # True weights & Target y
  true_beta <- c(rnorm(n_dense, 2, 0.5), rep(0, n_sparse_cats))
  true_beta[n_dense + seq(1, 50)] <- runif(50, 1.0, 2.5) # sinyal sparse
  
  # Generasi y terbobot
  y <- as.vector(X %*% true_beta) + rnorm(n_obs, mean = 0, sd = 1.5)
  
  # 2. Eksekusi Estimasi Inti
  t_start <- Sys.time()
  
  # Regularisasi Tikhonov mikro (Ridge) untuk stabilitas numerik: lambda = 1e-4
  lambda_ridge <- 1e-4
  
  message("[COMPUTE] Membentuk XtX dan Crossproduct...")
  XtX <- Matrix::crossprod(X)
  
  # Injeksi Ridge pada diagonal: XtX_reg = XtX + lambda * I
  diag(XtX) <- diag(XtX) + lambda_ridge
  
  message("[COMPUTE] Menghitung Faktorisasi Cholesky Sparse...")
  # Menggunakan SuiteSparse CHOLMOD dengan automatic fill-reducing permutation (AMD)
  chol_X <- Matrix::Cholesky(XtX, perm = TRUE, LDL = FALSE)
  
  Xty <- Matrix::crossprod(X, y)
  beta_hat <- Matrix::solve(chol_X, Xty)
  
  t_solve <- Sys.time()
  message(sprintf("[COMPUTE] Faktorisasi selesai dalam: %.3f detik", 
                  as.numeric(difftime(t_solve, t_start, units = "secs"))))
  
  # 3. Memory-Safe Chunked Residual Variance Estimation
  message("[INFERENCE] Menghitung standard error via chunking...")
  chunk_size <- 500000
  n_chunks <- ceiling(n_obs / chunk_size)
  
  res_sq_sum <- 0
  
  for (c_idx in seq_len(n_chunks)) {
    idx_start <- ((c_idx - 1) * chunk_size) + 1
    idx_end <- min(c_idx * chunk_size, n_obs)
    
    X_chunk <- X[idx_start:idx_end, ]
    y_chunk <- y[idx_start:idx_end]
    
    pred_chunk <- as.vector(X_chunk %*% beta_hat)
    residuals_chunk <- y_chunk - pred_chunk
    res_sq_sum <- res_sq_sum + sum(residuals_chunk^2)
    
    # Hapus referensi untuk membantu garbage collector
    rm(X_chunk, y_chunk, pred_chunk, residuals_chunk)
  }
  
  sigma2_est <- res_sq_sum / (n_obs - p)
  message(sprintf("[INFERENCE] Sigma^2 Estimasi: %.4f", sigma2_est))
  
  # Hitung varians koefisien: diag((XtX)^-1) * sigma2
  # Tidak menginversi XtX secara langsung! Selesaikan sistem identitas sparse terpilih
  # Estimasi diagonal inversi:
  inv_diag <- Matrix::diag(Matrix::solve(chol_X, Matrix::Diagonal(p)))
  se_beta <- sqrt(abs(inv_diag * sigma2_est))
  
  t_total <- Sys.time()
  total_duration <- as.numeric(difftime(t_total, t_start, units = "secs"))
  message(sprintf("[SUCCESS] Total Durasi Eksekusi Pipeline: %.2f detik (SLA < 60s)", total_duration))
  
  # Return Ringkasan Audit
  return(data.frame(
    Param_Index = 1:10,
    Param_Name  = colnames(X)[1:10],
    Beta_Est    = as.vector(beta_hat)[1:10],
    Std_Error   = se_beta[1:10],
    Z_Score     = (as.vector(beta_hat)[1:10] / se_beta[1:10])
  ))
}

# Driver Runner (Dijalankan jika dipanggil standalone)
if (sys.nframe() == 0) {
  # Jalankan pada konfigurasi beban benchmark moderat
  perf_audit <- run_fintech_calibration_pipeline(
    n_obs = 100000, 
    n_dense = 10, 
    n_sparse_cats = 200, 
    n_threads = 4
  )
  print(perf_audit)
}
```

---

### 9. Trade-offs

```
                  ACCURACY / STABILITY
                          ^
                          |       * SVD (Truncated/Full)
                          |
                          |     * QR Decomposition
                          |
                          |   * Cholesky Decomposition
                          |
                          | * Naive Inverse (solve(XtX))
                          +----------------------------------> THROUGHPUT / SPEED
```

#### Analisis Trade-off Arsitektural

1.  **Dekomposisi QR vs Dekomposisi Cholesky:**
    *   *QR ($O(2np^2)$):* Tidak memerlukan pembentukan eksplisit matriks $X^T X$. Sangat stabil ketika matriks memiliki rentang dinamis nilai yang sangat besar. Trade-off: Secara komputasi membutuhkan waktu $2\times$ lebih lama dibanding Cholesky dan sulit diparalelkan pada matriks sparse berskala sangat masif.
    *   *Cholesky ($O(np^2 + \frac{1}{3}p^3)$):* Sangat cepat pada arsitektur BLAS bertingkat tinggi dan sangat efisien pada representasi sparse (SuiteSparse CHOLMOD). Trade-off: Mengharuskan pembentukan $X^T X$, yang mengkuadratkan nilai rasio kondisi ($\kappa(X)^2$). Memerlukan jaminan positif definit penuh.
2.  **Multithreading BLAS vs Paralelisasi R Multi-Process:**
    *   *BLAS Multithreading (OpenMP/MKL):* Paralelisasi Level 3 BLAS (`DGEMM`) sangat efisien pada operasi tunggal matriks raksasa.
    *   *Process-level Concurrency (`mclapply`, `future`):* Menghadapi bencana **Thread Oversubscription** jika dipadukan tanpa isolasi. Jika R memanggil 16 worker process paralel, dan setiap worker mengeksekusi BLAS dengan 16 thread, CPU akan dibebani 256 thread aktif pada 16 core hardware, memicu destruksi performa akibat *excessive context-switching* pada kernel scheduler Linux.
    *   *Rule of Thumb:* Jika memproses matriks masif tunggal: `threads = max_cores`. Jika memproses batch bootstrap/koleksi model independen paralel: `R_workers = max_cores`, dan paksa `blas_set_num_threads(1)`.
3.  **Dense vs Compressed Sparse Column (CSC):**
    *   Matriks sparse memiliki overhead pointer struktural (`p` dan `i` arrays). Jika densitas matriks non-nol $> 15\%$, format sparse justru menggunakan memori lebih besar daripada representasi dense standar dan menurunkan pemanfaatan *SIMD cache lines*.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Umum (Anti-Patterns)
1.  **Menggunakan Inversi Eksplisit untuk Menyelesaikan Sistem Linier:**
    *   *Salah:* `beta <- solve(t(X) %*% X) %*% t(X) %*% y`
    *   *Benar:* `beta <- solve(crossprod(X), crossprod(X, y))` atau `qr.solve(X, y)`
2.  **Menghitung Hat Matrix Eksplisit untuk Residual Standard Errors:**
    *   *Salah:* `H <- X %*% solve(t(X) %*% X) %*% t(X); res <- y - H %*% y` ($O(n^2)$ memory leak)
    *   *Benar:* `res <- y - X %*% beta` ($O(n)$ footprint)
3.  **Mengabaikan Indeks Basis 0 vs Basis 1 saat Integrasi C/Fortran:**
    *   Format CSC (`dgCMatrix`) internal C menggunakan indeks baris 0-based. Memanipulasinya langsung via pointer `@i` dari R level tanpa offset $+1$ menyebabkan pembacaan memori terlarang (*segmentation fault*).
4.  **Kegagalan Mengunci Threading BLAS pada Proses Paralel Forked:**
    *   Menggunakan `parallel::mclapply()` tanpa mematikan OpenBLAS threading memicu *deadlock* internal pada libc/pthreads di lingkungan Linux glibc tertentu.

#### 10.2. Troubleshooting Run-time Playbook

*   **Gejala:** R session langsung *crash* dengan pesan `Terminated` atau `Killed` tanpa jejak stack trace R.
    *   **Root Cause:** Linux OOM Killer menghentikan proses akibat alokasi memori matriks dense yang melebihi batas cgroup/RAM fisik.
    *   **Solusi:** Periksa estimasi memori sebelum instansiasi: $\text{Bytes} = n \times p \times 8$. Terapkan *sparse conversion* atau *chunked loading*.
*   **Gejala:** Sistem mengeluarkan pesan peringatan: `system is computationally singular: reciprocal condition number = 1.2e-19`.
    *   **Root Cause:** Multikolinearitas sempurna; dua atau lebih kolom prediktor linear dependen.
    *   **Solusi:** Hitung matriks rank via LAPACK `qr(X)$rank`. Terapkan eliminasi variabel dengan *variance inflation factor* (VIF) atau suntikkan *shrinkage penalty* (Ridge: $\lambda I$).
*   **Gejala:** Penggunaan CPU mencapai $1600\%$ (pada 16 core) tetapi throughput komputasi jauh lebih lambat dibanding *single-thread*.
    *   **Root Cause:** Thread thrashing / oversubscription.
    *   **Solusi:** Eksekusi `RhpcBLASctl::blas_set_num_threads(1)` sebelum memasuki loop paralelisasi tingkat aplikasi.

---

### 11. Best Practices (Production Checklist)

1.  [ ] **BLAS Dynamic Link Audit:** Verifikasi bahwa R terhubung ke OpenBLAS atau MKL menggunakan `sessionInfo()` atau `extSoftVersion()["BLAS"]`.
2.  [ ] **Condition Number Gating:** Pasang gerbang pelindung numerik sebelum melakukan dekomposisi (`stopifnot(rcond(A) > 1e-12)`).
3.  [ ] **No Explict Matrix Invert:** Audit seluruh basis kode; larang keras fungsi `solve(A)` yang dipanggil dengan satu argumen tanpa target vektor `b`.
4.  [ ] **Optimized Cross-Product:** Ganti seluruh operasi `t(X) %*% X` dengan `Matrix::crossprod(X)` atau `crossprod(X)` (menghemat alokasi satu matriks transpose intermediat).
5.  [ ] **Thread Concurrency Confinement:** Tentukan konfigurasi eksplisit:
    *   Batch processing / Embarrassingly parallel: `BLAS Threads = 1`, `Worker Cores = N`.
    *   Single heavy matrix computation: `BLAS Threads = N`, `Worker Cores = 1`.
6.  [ ] **Pre-allocated Sparse Buffers:** Jika membangun matriks sparse dinamis, hindari pemanggilan berulang `rbind()` atau `cbind()`. Tampung dalam format koordinat triplet (`i, j, x`) pada *vector buffer* primitif lalu bangun `sparseMatrix()` dalam satu operasi akhir.
7.  [ ] **Enforce IEEE 754 Sanity Checks:** Periksa keberadaan nilai `NaN`, `Inf`, atau `-Inf` pada matriks output numerik menggunakan `anyNA()` dan `all(is.finite())`.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/
└── m02/
    ├── Makefile
    ├── src/
    │   ├── 01_blas_benchmark.R
    │   ├── 02_sparse_decomposition.R
    │   └── 03_verification_audit.R
    └── output/
```

#### Langkah 1: Siapkan Konfigurasi Lingkungan (`Makefile`)
Buat file `hands-on/m02/Makefile`:

```makefile
.PHONY: all setup benchmark sparse verify clean

all: setup benchmark sparse verify

setup:
	mkdir -p src output
	Rscript -e "install.packages(c('Matrix', 'RhpcBLASctl', 'microbenchmark'), repos='https://cloud.r-project.org')"

benchmark:
	Rscript src/01_blas_benchmark.R

sparse:
	Rscript src/02_sparse_decomposition.R

verify:
	Rscript src/03_verification_audit.R

clean:
	rm -rf output/*
```

#### Langkah 2: Buat Skrip Benchmark BLAS (`src/01_blas_benchmark.R`)

```r
# src/01_blas_benchmark.R
suppressPackageStartupMessages({
  library(RhpcBLASctl)
  library(microbenchmark)
})

cat("=== AUDIT PERFORMA MULTITHREADED BLAS ===\n")
cat(sprintf("BLAS Implementation Path: %s\n", extSoftVersion()["BLAS"]))
cat(sprintf("Total Cores Terdeteksi  : %d\n", get_num_cores()))

# Matriks dense 3000 x 3000 double precision (~72 MB)
dim_size <- 3000
cat(sprintf("Membentuk matriks acak: %d x %d...\n", dim_size, dim_size))
set.seed(123)
A <- matrix(rnorm(dim_size^2), nrow = dim_size)
B <- matrix(rnorm(dim_size^2), nrow = dim_size)

thread_counts <- c(1, 2, 4)
max_cores <- get_num_cores()
if (max_cores >= 8) thread_counts <- c(thread_counts, 8)

results <- data.frame()

for (tc in thread_counts) {
  blas_set_num_threads(tc)
  cat(sprintf("Benchmarking dengan %d BLAS thread(s)...\n", tc))
  
  bench <- microbenchmark(
    dgemm = { C <- A %*% B },
    times = 5
  )
  
  med_time <- median(bench$time) / 1e9 # Konversi ke detik
  gflops <- (2 * (dim_size / 1000)^3) / med_time
  
  results <- rbind(results, data.frame(
    Threads = tc,
    Duration_Sec = med_time,
    GFLOPS = gflops
  ))
}

print(results)
saveRDS(results, "output/blas_benchmark_results.rds")
cat("[OK] Hasil benchmark disimpan di output/blas_benchmark_results.rds\n")
```

#### Langkah 3: Buat Skrip Dekomposisi Sparse Lanjutan (`src/02_sparse_decomposition.R`)

```r
# src/02_sparse_decomposition.R
suppressPackageStartupMessages({
  library(Matrix)
})

cat("=== AUDIT REKAYASA DEKOMPOSISI SPARSE SUITESPARSE ===\n")

# Bangun sparse banded Poisson matrix berukuran 50.000 x 50.000
n_dim <- 50000
cat(sprintf("Membangun Poisson matrix sparse: %d x %d...\n", n_dim, n_dim))

# Diagonal utama dan off-diagonal
main_diag <- rep(4, n_dim)
off_diag <- rep(-1, n_dim - 1)

A_sparse <- bandSparse(
  n_dim, 
  k = c(0, 1, -1), 
  diagonals = list(main_diag, off_diag, off_diag), 
  symmetric = TRUE
)

# Sifat: Positif Definit Simetris
b <- rnorm(n_dim)

# Eksekusi Dekomposisi Cholesky Terfaktor
cat("Menjalankan faktorisasi Cholesky Sparse dengan SuiteSparse CHOLMOD...\n")
t0 <- Sys.time()
chol_fact <- Cholesky(A_sparse, perm = TRUE, LDL = FALSE)
x_sol <- solve(chol_fact, b)
t1 <- Sys.time()

compute_time <- as.numeric(difftime(t1, t0, units = "secs"))
cat(sprintf("Selesai memecahkan %d sistem linier sparse dalam: %.4f detik\n", n_dim, compute_time))

# Evaluasi Residual Presisi: ||A*x - b|| / ||b||
res <- as.vector(A_sparse %*% x_sol) - b
relative_residual <- sqrt(sum(res^2)) / sqrt(sum(b^2))
cat(sprintf("Norm Residual Relatif: %.18e\n", relative_residual))

stopifnot(relative_residual < 1e-12)

saveRDS(list(dimension = n_dim, residual = relative_residual, duration = compute_time), 
        "output/sparse_solve_results.rds")
cat("[OK] Solusi divalidasi dan disimpan di output/sparse_solve_results.rds\n")
```

#### Langkah 4: Buat Skrip Verifikasi & Validasi Integritas (`src/03_verification_audit.R`)

```r
# src/03_verification_audit.R
cat("=== FINAL VALIDATION & REPORT ENGINE ===\n")

res_blas <- readRDS("output/blas_benchmark_results.rds")
res_sparse <- readRDS("output/sparse_solve_results.rds")

# Validasi Skalabilitas Threading
speedup_observed <- res_blas$Duration_Sec[1] / res_blas$Duration_Sec[nrow(res_blas)]
cat(sprintf("[AUDIT] Rasio Speedup BLAS (%d Threads vs 1 Thread): %.2fx\n", 
            res_blas$Threads[nrow(res_blas)], speedup_observed))

# Validasi Presisi Sparse
cat(sprintf("[AUDIT] Presisi Residual Sparse Solver: %.5e\n", res_sparse$residual))

if (res_sparse$residual < 1e-12 && speedup_observed > 1.1) {
  cat("\n[PASSED] SELURUH UJI VERIFIKASI ARSITEKTUR MEMENUHI SYARAT PRODUKSI.\n")
} else {
  cat("\n[WARNING] SISTEM MEMERLUKAN OPTIMASI TINGKAT KERNEL BLAS/LAPACK.\n")
}
```

Jalankan seluruh proses melalui terminal:
```bash
make all
```

---

### 13. Exercise

#### Level Easy
Tuliskan sebuah fungsi R `detect_collinear_columns(X, tol = 1e-7)` yang menerima matriks dense numerik $X$, mengeksekusi faktorisasi QR dengan *column pivoting* LAPACK (`qr(X, tol = tol)`), lalu mengembalikan indeks dan nama kolom yang bersifat *linearly dependent* (redundan).
*Petunjuk:* Manfaatkan atribut `pivot` dan `rank` dari objek QR hasil komputasi.

#### Level Medium
Buat sebuah fungsi `weighted_least_squares_chol(y, X, w)` untuk menyelesaikan persoalan Weighted Least Squares (WLS):

$$\min_{\beta} \sum_{i=1}^n w_i (y_i - X_i \beta)^2$$

*Ketentuan:*
1.  Vektor bobot $w_i > 0$.
2.  Jangan pernah membentuk matriks diagonal $W_{n \times n}$ secara eksplisit.
3.  Gunakan penskalaan baris in-place berbasis aljabar linier sebelum faktorisasi Cholesky.
4.  Lakukan mitigasi jika salah satu nilai bobot bernilai non-positif.

#### Level Hard
Rancang modul komputasi *Rolling Window Covariance Estimator* untuk matriks deret waktu $Y_{T \times K}$ ($T = 100.000$, $K = 500$) dengan ukuran jendela *sliding* $W = 1.000$. Modul harus menghitung inversi matriks kovariansi pada setiap pergeseran waktu $t = W+1, \dots, T$.
*Batasan Arsitektural:* Dilarang melakukan komputasi faktorisasi penuh $O(K^3)$ pada setiap langkah bergeser. Wajib menerapkan *Rank-2 Update* formula **Sherman-Morrison-Woodbury**:

$$(A + u v^T)^{-1} = A^{-1} - \frac{A^{-1} u v^T A^{-1}}{1 + v^T A^{-1} u}$$

untuk memperbarui $(X_{new}^T X_{new})^{-1}$ dari $(X_{old}^T X_{old})^{-1}$ dengan kompleksitas $O(K^2)$ per translasi waktu.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah konsorsium perbankan multinasional membutuhkan mesin analitik sentralisasi untuk mendeteksi sindikat transaksi pencucian uang (*AML/Graph Analytics*). Matriks relasi transaksi direpresentasikan oleh matriks ketetanggaan (*Adjacency Graph*) sangat besar: $N = 10.000.000$ entitas rekening, dengan rata-rata 15 koneksi per entitas ($nnz \approx 150.000.000$).

**Objektif:**
Bangun fungsi arsitektur R murni (hanya diizinkan menggunakan pustaka `Matrix`, `parallel`, dan C-interface native jika mendesak) yang mengimplementasikan **Implicitly Restarted Lanczos Bidiagonalization / Truncated SVD** untuk mengekstraksi 20 *singular vectors* terbesar matriks relasi tersebut guna memetakan *eigen-centrality* komunitas tersembunyi.

**Spesifikasi dan Kendala Arsitektural:**
1.  **Memory Wall:** Memori RAM total server dibatasi ketat maksimum 32 GB. Pemuatan matriks menjadi dense akan langsung memicu terminasi paksa oleh OS.
2.  **Zero Loss of Orthogonality:** Basis vektor Krylov yang dihasilkan rentan kehilangan sifat ortogonal akibat *floating-point cancellation*. Anda wajib merancang mekanisme *re-orthogonalization* (Gram-Schmidt termodifikasi).
3.  **Strict Convergence Metric:** Toleransi konvergensi residu singular values $||\Sigma_k - \Sigma_{k-1}||_\infty < 10^{-8}$.
4.  **No High-Level Blackbox:** Dilarang menggunakan paket wrapper tingkat tinggi seperti `irlba`, `svds`, atau `rARPACK`. Algoritma rantai matriks-vektor sparse iteratif harus dirancang secara fundamental di atas operator `Matrix::crossprod` dan manipulasi primitif `SEXP`.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1.  **Format penyimpanan array apa yang digunakan secara native oleh R untuk matriks dense di tingkat memori internal?**
    *   *A)* Row-Major (seperti Bahasa C/Python)
    *   *B)* Compressed Sparse Row (CSR)
    *   *C)* Column-Major (seperti Fortran)
    *   *D)* Block Morton Layout
2.  **Mengapa operasi `solve(A) %*% b` merupakan anti-pattern dibandingkan dengan `solve(A, b)`?**
    *   *A)* Karena `solve(A) %*% b` menghasilkan matriks transpose secara default.
    *   *B)* Karena `solve(A)` menghitung inversi penuh eksplisit secara tidak stabil dan lambat ($O(n^3)$), sedangkan `solve(A, b)` menggunakan substitusi faktorisasi langsung ($O(n^2)$).
    *   *C)* Karena `solve(A, b)` menggunakan CPU GPU-accelerated path secara otomatis.
    *   *D)* Karena `solve(A) %*% b` membatasi tipe data matriks ke bilangan bulat 32-bit.
3.  **Tiga vektor integer dan numerik apa yang mendasari struktur data objek sparse `dgCMatrix` di pustaka `Matrix`?**
    *   *A)* `x` (values), `r` (rows), `c` (columns)
    *   *B)* `p` (column pointers), `i` (row indices 0-based), `x` (non-zero values)
    *   *C)* `dim` (dimensions), `val` (values), `mask` (binary booleans)
    *   *D)* `A` (matrix), `b` (rhs vector), `u` (solution)
4.  **Jika matriks $X$ memiliki condition number $\kappa(X) = 10^7$, berapa perkiraan condition number dari matriks normal equations $X^T X$?**
    *   *A)* $10^7$
    *   *B)* $2 \times 10^7$
    *   *C)* $10^{14}$
    *   *D)* $\sqrt{10^7} \approx 3162$
5.  **Instruksi CPU vectorization apa yang dimanfaatkan oleh pustaka BLAS modern (seperti MKL/OpenBLAS) untuk mengeksekusi beberapa perkalian double-precision secara paralel dalam satu siklus clock?**
    *   *A)* SSE (128-bit) saja
    *   *B)* RISC Instruction Fetch
    *   *C)* SIMD / AVX-2 / AVX-512 FMA (Fused Multiply-Add)
    *   *D)* Non-Volatile Memory Addressing

#### Bagian 2: Intermediate (5 Pertanyaan)
6.  **Apa implikasi utama dari algoritma dekomposisi QR berbasis Householder Reflections terhadap kestabilan sistem linear dibandingkan dekomposisi Cholesky?**
    *   *A)* QR lebih lambat $10\times$ tanpa keunggulan numerik apapun.
    *   *B)* QR bekerja langsung pada matriks $X$ tanpa menghitung $X^T X$, sehingga menjaga condition number tetap pada skala $\kappa(X)$, bukan $(\kappa(X))^2$.
    *   *C)* QR