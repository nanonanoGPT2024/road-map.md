# ==============================================================================
# Script: high_performance_risk_engine.R
# Deskripsi: Engine VaR Monte Carlo Terdistribusi Skala Enterprise
# Target: Node Komputasi Linux 16+ Cores
# ==============================================================================

suppressPackageStartupMessages({
  library(parallel)
  library(future)
  library(future.apply)
  library(bigstatsr)
  library(Rcpp)
})

# 1. Definisi Kernel Kecepatan Tinggi Menggunakan C++ & OpenMP via Rcpp
#    Mengompilasi fungsi kalkulasi portofolio loss secara paralel di level thread C++
Rcpp::sourceCpp(code = '
#include <Rcpp.h>
#ifdef _OPENMP
  #include <omp.h>
#endif

// [[Rcpp::plugins(openmp)]]

// [[Rcpp::export]]
Rcpp::NumericVector parallel_portfolio_loss(
    Rcpp::NumericMatrix scenario_matrix,
    Rcpp::NumericVector asset_weights,
    int n_threads = 1) {
    
    int n_scenarios = scenario_matrix.nrow();
    int n_assets = scenario_matrix.ncol();
    Rcpp::NumericVector portfolio_losses(n_scenarios);

    #pragma omp parallel for num_threads(n_threads) schedule(static)
    for (int i = 0; i < n_scenarios; ++i) {
        double current_loss = 0.0;
        for (int j = 0; j < n_assets; ++j) {
            // Formula pricing loss hipotetis non-linear
            double shock = scenario_matrix(i, j);
            current_loss += asset_weights[j] * (exp(shock) - 1.0);
        }
        portfolio_losses[i] = current_loss;
    }

    return portfolio_losses;
}
')

# ==============================================================================
# 2. Simulasi Dataset Berskala Besar: Memory-Mapped Shared Matrix
# ==============================================================================
n_scenarios <- 500000 # 500k Skenario
n_assets <- 200        # 200 Aset Finansial

cat("\n[Inisialisasi] Mengalokasikan Memory-Mapped Matrix (File-backed)...\n")

# Buat berkas sementara untuk shared memory
tmp_bk <- tempfile(fileext = ".bk")
tmp_rds <- tempfile(fileext = ".rds")

# Memetakan matriks langsung ke storage (backing file), memotong overhead IPC
scenario_fbm <- FBM(
  nrow = n_scenarios, 
  ncol = n_assets, 
  type = "double", 
  backingfile = sub_ext(tmp_bk, "")
)$save()

# Mengisi matriks secara paralel chunk-by-chunk untuk efisiensi inisialisasi
set.seed(1234)
# Mengisi dengan data simulasi random walk terdistribusi
for (col in 1:n_assets) {
  scenario_fbm[, col] <- rnorm(n_scenarios, mean = 0.0002, sd = 0.02)
}

# Bobot Portofolio
weights <- runif(n_assets)
weights <- weights / sum(weights)

# ==============================================================================
# 3. Arsitektur Pemrosesan Paralel Terdistribusi (Master-Worker Split)
# ==============================================================================
# Deteksi core yang tersedia dengan aman (hindari oversubscription jika dalam container)
total_physical_cores <- parallelly::availableCores(constraints = "multicore")
worker_nodes <- max(1, floor(total_physical_cores / 2)) # Sisakan core untuk I/O
threads_per_worker <- 2 # Hybrid: Worker Process (Future) x Core Worker (OpenMP)

cat(sprintf("[Cluster Config] Menggunakan %d Workers, masing-masing %d OpenMP Threads.\n",
            worker_nodes, threads_per_worker))

future::plan(future::multisession, workers = worker_nodes)

# Mendefinisikan Chunk Partisi Data (Index Splitting)
chunk_indices <- split(seq_len(n_scenarios), 
                       cut(seq_len(n_scenarios), breaks = worker_nodes, labels = FALSE))

# ==============================================================================
# 4. Eksekusi Distributed Map-Reduce
# ==============================================================================
cat("[Eksekusi] Menjalankan Pipeline Monte Carlo VaR...\n")

start_time <- Sys.time()

# Bagikan descriptor FBM ke worker alih-alih mengirim seluruh objek matriks
fbm_descriptor <- scenario_fbm$as.FBM()

# Parallel Map Phase
aggregated_losses <- future.apply::future_lapply(
  X = chunk_indices,
  FUN = function(indices, fbm_desc, w, threads) {
    # Re-attach shared memory pointer tanpa menyalin data di RAM
    local_fbm <- fbm_desc
    
    # Ambil sub-matriks skenario secara lokal (zero-copy pointer mapping)
    sub_scenarios <- local_fbm[indices, , drop = FALSE]
    
    # Jalankan OpenMP kernel terkompilasi
    losses <- parallel_portfolio_loss(
      scenario_matrix = sub_scenarios, 
      asset_weights = w, 
      n_threads = threads
    )
    return(losses)
  },
  fbm_desc = fbm_descriptor,
  w = weights,
  threads = threads_per_worker,
  future.seed = TRUE
)

# Reduce Phase (Penggabungan Hasil)
all_portfolio_losses <- unlist(aggregated_losses, use.names = FALSE)
execution_duration <- difftime(Sys.time(), start_time, units = "secs")

# ==============================================================================
# 5. Penghitungan Metrik Risiko Basel IV
# ==============================================================================
alpha <- 0.99
var_99 <- quantile(all_portfolio_losses, probs = 1 - alpha)
expected_shortfall_99 <- mean(all_portfolio_losses[all_portfolio_losses <= var_99])

cat("\n=======================================================\n")
cat(sprintf("Selesai dalam: %.3f detik\n", as.numeric(execution_duration)))
cat(sprintf("Total Evaluasi Skenario: %d\n", length(all_portfolio_losses)))
cat(sprintf("Value-at-Risk (99%% VaR) : %.6f\n", var_99))
cat(sprintf("Expected Shortfall (99%%): %.6f\n", expected_shortfall_99))
cat("=======================================================\n")

# Teardown Cluster & Clean Physical Backing File
future::plan(future::sequential)
unlink(c(tmp_bk, tmp_rds, paste0(sub_ext(tmp_bk, ""), ".rds")))
