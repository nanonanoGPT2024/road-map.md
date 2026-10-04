# ==============================================================================
# Enterprise Factor Risk Attribution Engine
# Focus: Extreme Collinearity Resilience, Singular Protection, Zero Matrix Inverse
# ==============================================================================

#' High-Performance Robust Regression Solver for Risk Attribution
#' 
#' @param returns Vector of asset returns (length n)
#' @param factors Matrix of factor exposures (dimensions n x k)
#' @param ridge_lambda Floating factor regularization parameter (L2 penalty)
#' @param rcond_tolerance Floating threshold for singular value cutoff
#' @return A robust list containing coefficients, robust standard errors, and rank status
factor_risk_engine <- function(returns, 
                               factors, 
                               ridge_lambda = 1e-4, 
                               rcond_tolerance = .Machine$double.eps * 1e4) {
  
  # 1. Validasi Input Defensif
  if (!is.matrix(factors)) {
    factors <- as.matrix(factors)
  }
  stopifnot(nrow(factors) == length(returns))
  
  n <- nrow(factors)
  k <- ncol(factors)
  
  # 2. Dekomposisi SVD untuk Matriks Desain
  # X = U %*% D %*% t(V)
  svd_decomp <- svd(factors)
  U <- svd_decomp$u
  d <- svd_decomp$d
  V <- svd_decomp$v
  
  # Evaluasi Bilangan Kondisi (Condition Number)
  condition_number <- d[1] / d[k]
  
  # 3. Penanganan Singularity & Tikhonov (Ridge) Filtering via SVD
  # Solusi penalitas: (X^T X + lambda * I)^(-1) X^T y
  # Ekivalen SVD: V %*% diag(d / (d^2 + lambda)) %*% U^T %*% y
  d_regularized <- d / (d^2 + ridge_lambda)
  
  # Potong dimensi jika nilai singular di bawah batas toleransi numerik
  rank_effective <- sum(d > (d[1] * rcond_tolerance))
  if (rank_effective < k) {
    warning(sprintf("Peringatan: Matriks eksposur faktor Rank-Deficient! Rank: %d dari %d", 
                    rank_effective, k))
    zero_indices <- (rank_effective + 1):k
    d_regularized[zero_indices] <- 0
  }
  
  # 4. Estimasi Koefisien (Beta) via Proyeksi SVD Terfilter
  # beta_hat = V %*% D_reg %*% (U^T %*% y)
  # Operasi BLAS Level 2: Matriks-Vektor
  Uty <- crossprod(U, returns)
  scaled_vector <- d_regularized * Uty
  beta_hat <- V %*% scaled_vector
  
  # 5. Penghitungan Residual & Statistik Inferensial Cepat
  fitted_vals <- factors %*% beta_hat
  residuals <- returns - fitted_vals
  
  df_residuals <- n - rank_effective
  residual_variance <- as.numeric(crossprod(residuals) / df_residuals)
  
  # 6. Varians-Kovarians Koefisien Robust SVD
  # Var(Beta) = sigma^2 * V %*% diag(d^2 / (d^2 + lambda)^2) %*% t(V)
  cov_scaling <- (d / (d^2 + ridge_lambda))^2
  # Membentuk V %*% diag(cov_scaling) %*% V^T secara efisien:
  # V %*% diag(cov_scaling) ekivalen dengan memodulasi kolom-kolom V
  V_scaled <- sweep(V, MARGIN = 2, STATS = sqrt(cov_scaling), FUN = "*")
  vcov_beta <- residual_variance * tcrossprod(V_scaled)
  
  se_beta <- sqrt(pmax(diag(vcov_beta), 0))
  t_stats <- beta_hat / se_beta
  p_values <- 2 * pt(-abs(t_stats), df = df_residuals)
  
  list(
    coefficients = as.vector(beta_hat),
    standard_errors = se_beta,
    t_statistics = as.vector(t_stats),
    p_values = as.vector(p_values),
    condition_number = condition_number,
    effective_rank = rank_effective,
    residual_variance = residual_variance
  )
}

# ==============================================================================
# Verifikasi Stabilitas Numerik dalam Kondisi Ekstrem
# ==============================================================================

# Membuat data sintesis dengan kolinearitas hampir sempurna
n_samples <- 2500
n_factors <- 10

X_pathological <- matrix(rnorm(n_samples * n_factors), n_samples, n_factors)
# Buat kolom ke-10 identik dengan kolom ke-9 ditambah jitter numerik sangat kecil
X_pathological[, 10] <- X_pathological[, 9] + rnorm(n_samples, sd = 1e-12)

real_beta <- rnorm(n_factors)
y_sim <- X_pathological %*% real_beta + rnorm(n_samples, sd = 0.5)

cat("[+] Menguji Algoritma Standar vs Robust Factor Engine...\n")

# lm() standar
lm_fit <- lm(y_sim ~ X_pathological - 1)

# Engine Kustom
engine_fit <- factor_risk_engine(y_sim, X_pathological, ridge_lambda = 1e-5)

cat(sprintf("Bilangan Kondisi X: %.2e\n", engine_fit$condition_number))
cat(sprintf("Effective Rank yang Terdeteksi: %d / %d\n", engine_fit$effective_rank, n_factors))
cat(sprintf("Koefisien Terestimasi Pertama: %.4f (Manual) vs %.4f (lm)\n", 
            engine_fit$coefficients[1], coef(lm_fit)[1]))
