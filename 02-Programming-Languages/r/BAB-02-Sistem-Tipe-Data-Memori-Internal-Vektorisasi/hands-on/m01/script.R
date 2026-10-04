# ==============================================================================
# PIPELINE PEMROSESAN HIGH-FREQUENCY TICK-DATA
# ==============================================================================

# Simulasi data mentah tick sensor (100.000 data point)
set.seed(42)
n_ticks <- 1e5
raw_prices <- 100 + cumsum(rnorm(n_ticks, mean = 0.01, sd = 0.5))

# ------------------------------------------------------------------------------
# PENDEKATAN 1: NAIF & NON-VEKTORISASI (Bencana Performa & Memori)
# ------------------------------------------------------------------------------
process_naive <- function(prices) {
  transformed_data <- numeric(0) # Inisialisasi kosong
  
  for (i in seq_along(prices)) {
    # CoW & Re-alokasi kuadratik pada setiap langkah!
    if (prices[i] > 100) {
      val <- log(prices[i]) * 1.5
    } else {
      val <- log(prices[i]) * 0.5
    }
    transformed_data <- c(transformed_data, val)
  }
  return(transformed_data)
}

# ------------------------------------------------------------------------------
# PENDEKATAN 2: ARSITEKTUR VEKTORISASI & PRE-ALLOCATION (Standar Produksi)
# ------------------------------------------------------------------------------
process_optimized <- function(prices) {
  len <- length(prices)
  
  # Strategi Vektorisasi Penuh: Menghilangkan Loop Interpreter
  # 1. Alokasi mask kondisi berbasis Boolean Vector (C-Speed)
  condition_mask <- prices > 100
  
  # 2. Vektorisasi transformasi logaritma (SIMD-enabled C backend)
  log_prices <- log(prices)
  
  # 3. Operasi vektor inplace via seleksi indeks (Zero Duplication Spikes)
  result <- numeric(len)
  result[condition_mask]  <- log_prices[condition_mask] * 1.5
  result[!condition_mask] <- log_prices[!condition_mask] * 0.5
  
  return(result)
}

# ------------------------------------------------------------------------------
# BENCHMARKING & OBSERVASI MEMORI/WAKTU
# ------------------------------------------------------------------------------
# Catatan: Jumlah iterasi pendekatan naif dibatasi agar benchmark selesai rasional
n_sub <- 20000
cat(sprintf("--- Memulai Benchmark pada %d elemen ---\n", n_sub))

# Uji Pendekatan Naif
gc(full = TRUE, verbose = FALSE)
time_naive_start <- Sys.time()
res_naive <- process_naive(raw_prices[1:n_sub])
time_naive_end <- Sys.time()
dur_naive <- as.numeric(difftime(time_naive_end, time_naive_start, units = "secs"))
cat(sprintf("Pendekatan Naif      : %f detik\n", dur_naive))

# Uji Pendekatan Teroptimasi
gc(full = TRUE, verbose = FALSE)
time_opt_start <- Sys.time()
res_opt <- process_optimized(raw_prices[1:n_sub])
time_opt_end <- Sys.time()
dur_opt <- as.numeric(difftime(time_opt_end, time_opt_start, units = "secs"))
cat(sprintf("Pendekatan Teroptimasi: %f detik\n", dur_opt))

cat(sprintf("Speedup Factor       : %.2fx lipat lebih cepat!\n", dur_naive / dur_opt))

# Validasi Identitas Hasil Komputasi
stopifnot(isTRUE(all.equal(res_naive, res_opt)))
cat("Validasi: Output kedua implementasi identik 100% secara numerik.\n")
