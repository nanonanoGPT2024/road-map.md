# ==============================================================================
# PIPELINE AUDIT TRANSAKSI KEUANGAN HIGH-PERFORMANCE
# ==============================================================================
library(data.table)
library(collapse)
library(bench)

# Atur lingkungan thread
setDTthreads(0) # 0 = Deteksi otomatis semua core fisik & logis

# 1. SIMULASI DATASET TICK REALISTIS (25 JUTA BARIS)
generate_production_data <- function() {
  n_tx <- 25e6
  message("Mengalokasikan memori awal untuk 25 juta transaksi...")
  
  # Timestamp acak berurutan dalam rentang 24 jam
  start_epoch <- as.numeric(as.POSIXct("2026-03-30 00:00:00", tz = "UTC"))
  
  tx_table <- data.table(
    tx_id     = 1:n_tx,
    acc_id    = sample(1:200000, n_tx, replace = TRUE),
    currency  = sample(c("USD", "EUR", "JPY", "GBP"), n_tx, replace = TRUE),
    raw_amt   = round(rexp(n_tx, rate = 0.002) + 1, 2),
    timestamp = as.POSIXct(start_epoch + sort(runif(n_tx, 0, 86400)), 
                           origin = "1970-01-01", tz = "UTC")
  )
  
  # Data Snapshot Kurs (Update tiap 15 detik = 5760 baris per mata uang)
  fx_times <- seq(from = as.POSIXct("2026-03-30 00:00:00", tz = "UTC"),
                  to   = as.POSIXct("2026-03-30 23:59:59", tz = "UTC"), 
                  by   = "15 sec")
  
  fx_rates <- rbindlist(lapply(c("USD", "EUR", "JPY", "GBP"), function(curr) {
    base_rate <- switch(curr, "USD" = 1.0, "EUR" = 1.08, "JPY" = 0.0067, "GBP" = 1.28)
    data.table(
      currency  = curr,
      fx_time   = fx_times,
      rate_usd  = base_rate * (1 + sin(seq_along(fx_times) / 100) * 0.02)
    )
  }))
  
  return(list(tx = tx_table, fx = fx_rates))
}

# Inisialisasi Data
data_bundle <- generate_production_data()
tx_data <- data_bundle$tx
fx_data <- data_bundle$fx
rm(data_bundle) # Bebaskan memori pointer awal
invisible(gc())

# ==============================================================================
# 2. PIPELINE PRODUKSI: ROLLING JOIN & AGREGASI TINGKAT LANJUT
# ==============================================================================

execute_audit_pipeline <- function(dt_tx, dt_fx) {
  
  message("Memulai High-Performance Pipeline...")
  time_start <- Sys.time()
  
  # Langkah A: Validasi & Filtering In-Place
  # Menggunakan i subsetting tanpa duplikasi tabel
  dt_tx <- dt_tx[raw_amt > 0 & !is.na(timestamp)]
  
  # Langkah B: Persiapan Pengurutan untuk Rolling Join
  # Rolling join membutuhkan pengurutan pada join keys
  setkeyv(dt_fx, c("currency", "fx_time"))
  setkeyv(dt_tx, c("currency", "timestamp"))
  
  # Langkah C: Rolling Join (LOCF - Last Observation Carried Forward)
  # Mengaitkan setiap transaksi ke snapshot rate_usd paling terkini (roll = TRUE)
  message("Mengeksekusi Rolling Join (LOCF As-Of Match)...")
  dt_tx <- dt_fx[dt_tx, roll = TRUE, on = .(currency, fx_time = timestamp)]
  
  # Ubah nama kolom hasil join secara in-place
  setnames(dt_tx, old = "fx_time", new = "timestamp")
  
  # Langkah D: Mutasi In-Place Terhitung (Normalisasi ke USD)
  message("Kalkulasi Normalisasi In-Place (:=)...")
  dt_tx[, amt_usd := raw_amt * rate_usd]
  
  # Langkah E: Akselerasi Agregasi Ekstrem menggunakan Mesin 'collapse'
  message("Agregasi Akun Keuangan via collapse Micro-Engine...")
  
  # Ekstraksi komponen jam secara in-place via ITime
  dt_tx[, tx_hour := as.integer(as.ITime(timestamp)) %/% 3600L]
  
  # Gunakan Fast Group By dan Fast Aggregation dari collapse
  # Pengelompokan multi-kolom yang optimal secara biner
  g_acc <- GRP(dt_tx, by = c("acc_id", "tx_hour"), sort = FALSE)
  
  summary_metrics <- fsummarise(
    dt_tx,
    total_usd       = fsum(amt_usd, g_acc),
    mean_usd        = fmean(amt_usd, g_acc),
    max_usd         = fmax(amt_usd, g_acc),
    tx_count        = fnobs(amt_usd, g_acc),
    keep.group_vars = TRUE
  )
  
  time_end <- Sys.time()
  message("Pipeline Selesai dalam: ", round(difftime(time_end, time_start, units = "secs"), 2), " detik.")
  
  return(summary_metrics)
}

# Eksekusi Pipeline
audit_result <- execute_audit_pipeline(tx_data, fx_data)

# Tampilkan ringkasan hasil
message("\nStruktur Hasil Ringkasan Agregasi:")
print(head(audit_result, 5))
message("Total Grup Unik Dihasilkan: ", nrow(audit_result))
