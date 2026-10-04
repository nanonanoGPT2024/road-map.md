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
