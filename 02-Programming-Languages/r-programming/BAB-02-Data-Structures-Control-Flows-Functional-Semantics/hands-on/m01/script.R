# Production Engine: Financial Streaming Core Pipeline
# Environment: R 4.2+ Native Linux/macOS/Windows

suppressPackageStartupMessages({
  # Tidak ada dependensi eksternal, murni Base R untuk performa maksimum
})

#' Factory closure untuk menghasilkan konverter mata uang terisolasi
#' @param fx_table Named numeric vector berisi rate pertukaran terhadap base USD
#' @return Closure yang mempertahankan lookup state terisolasi
build_currency_engine <- function(fx_table) {
  # Enclosing environment menampung mapping kurs secara privat
  if (!is.numeric(fx_table) || is.null(names(fx_table))) {
    stop("INVALID_FX_TABLE: Format harus berupa named numeric vector.")
  }
  
  cached_rates <- fx_table
  total_conversions_processed <- 0L
  
  function(amounts, from_currencies) {
    if (length(amounts) != length(from_currencies)) {
      stop("LENGTH_MISMATCH: Dimensi vektor nominal dan mata uang tidak sinkron.")
    }
    
    # Resolusi kurs tervektorisasi melalui indeks nama (hash map internal C)
    rates <- cached_rates[from_currencies]
    
    # Validasi mata uang yang tidak terdaftar
    invalid_mask <- is.na(rates)
    if (any(invalid_mask)) {
      unrecognized <- unique(from_currencies[invalid_mask])
      stop(sprintf("CURRENCY_NOT_RECOGNIZED: Valuta [%s] tidak terdaftar.", 
                   paste(unrecognized, collapse = ", ")))
    }
    
    # Mutasi state analitik privat internal
    total_conversions_processed <<- total_conversions_processed + length(amounts)
    
    # Return skalar nominal dalam USD
    return(amounts / rates)
  }
}

#' Pemrosesan batch transaksi finansial secara murni fungsional dan tervektorisasi
#' @param transaction_stream List of data frames yang merepresentasikan streaming batches
#' @param engine Functional currency converter
#' @return Clean data frame tunggal yang terkonsolidasi
process_transaction_batches <- function(transaction_stream, engine) {
  # Proteksi pre-alokasi: Hindari growing object loop pattern (c() / rbind() berulang)
  num_batches <- length(transaction_stream)
  sanitized_list <- vector(mode = "list", length = num_batches)
  
  for (i in seq_len(num_batches)) {
    batch <- transaction_stream[[i]]
    
    # Validasi struktur data mendasar
    if (!is.data.frame(batch)) {
      warning(sprintf("Batch ke-%d dilewati: Bukan representasi data.frame.", i))
      next
    }
    
    # Ekstraksi komponen atomik
    tx_id  <- batch[["tx_id"]]
    amount <- batch[["amount"]]
    curr   <- batch[["currency"]]
    status <- batch[["status"]]
    
    # 1. Vectorized Logical Gate: Filtering status aktif dan validasi non-missing
    valid_record_mask <- !is.na(tx_id) & 
                         !is.na(amount) & 
                         !is.na(curr) &
                         (amount > 0) & 
                         (status == "COMPLETED")
    
    if (!any(valid_record_mask)) {
      next
    }
    
    # Subsetting aman
    sub_id     <- tx_id[valid_record_mask]
    sub_amount <- amount[valid_record_mask]
    sub_curr   <- curr[valid_record_mask]
    
    # 2. Eksekusi Fungsional Transformasi Kurs
    usd_amounts <- engine(amounts = sub_amount, from_currencies = as.character(sub_curr))
    
    # 3. Anomaly Detection Tervektorisasi (Z-Score Ambang Statis per batch)
    mean_val <- mean(usd_amounts)
    sd_val   <- sd(usd_amounts)
    
    # Tangani kasus edge jika deviasi standar nol atau NA
    is_anomaly <- if (!is.na(sd_val) && sd_val > 0) {
      abs(usd_amounts - mean_val) > (2.5 * sd_val)
    } else {
      rep(FALSE, length(usd_amounts))
    }
    
    # Simpan hasil dalam list berindeks (Memory Allocation Optimal: 0 duplicate reallocs)
    sanitized_list[[i]] <- data.frame(
      tx_id = sub_id,
      original_amount = sub_amount,
      currency = sub_curr,
      amount_usd = round(usd_amounts, 2),
      is_anomaly = is_anomaly,
      stringsAsFactors = FALSE
    )
  }
  
  # Filter elemen NULL (akibat skip)
  sanitized_list <- sanitized_list[!vapply(sanitized_list, is.null, logical(1))]
  
  # Rekonsiliasi matriks/tabel tunggal via do.call rbind efisien
  if (length(sanitized_list) == 0) {
    return(data.frame())
  }
  
  consolidated_result <- do.call(rbind, sanitized_list)
  rownames(consolidated_result) <- NULL
  return(consolidated_result)
}

# -----------------------------------------------------------------------------
# RUNTIME SIMULATION & EXECUTION
# -----------------------------------------------------------------------------
set.seed(42)

# Global rates table
fx_rates <- c("USD" = 1.0, "EUR" = 0.92, "JPY" = 155.4, "GBP" = 0.78, "IDR" = 16200.0)
currency_converter <- build_currency_engine(fx_rates)

# Sintesis data stream (3 batch)
generate_mock_batch <- function(n) {
  data.frame(
    tx_id = paste0("TX-", sample(10000:99999, n)),
    amount = c(runif(n - 2, 10, 5000), -50, NA), # Injeksi invalid amount dan missing
    currency = sample(c("USD", "EUR", "JPY", "GBP", "IDR"), n, replace = TRUE),
    status = sample(c("COMPLETED", "FAILED", "PENDING"), n, replace = TRUE, prob = c(0.8, 0.1, 0.1)),
    stringsAsFactors = FALSE
  )
}

mock_stream <- list(
  generate_mock_batch(10),
  generate_mock_batch(15),
  generate_mock_batch(8)
)

# Eksekusi Pipeline
final_pipeline_output <- process_transaction_batches(mock_stream, currency_converter)

# Tampilkan Hasil Pemrosesan
cat("=== EKSEKUSI PEMROSESAN FINANSIAL SUKSES ===\n")
print(head(final_pipeline_output, 10))
