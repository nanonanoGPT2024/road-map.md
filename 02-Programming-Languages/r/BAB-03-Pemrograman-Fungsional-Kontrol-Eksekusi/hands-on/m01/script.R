# ==============================================================================
# PRODUKSI: PIPELINE PEMROSESAN FINANSIAL FUNGSIONAL (FAULT-TOLERANT)
# ==============================================================================

# 1. Functional Result Container (Monadic Wrapper Pattern)
create_result <- function(success = NULL, error = NULL) {
  list(
    success = success,
    error   = error,
    is_ok   = is.null(error)
  )
}

# 2. Functional Safe Combinator
safely_execute <- function(.f) {
  force(.f)
  function(...) {
    tryCatch(
      expr = {
        res <- .f(...)
        create_result(success = res, error = NULL)
      },
      error = function(e) {
        create_result(success = NULL, error = conditionMessage(e))
      }
    )
  }
}

# 3. Payload Parsers (Pure Business Logic)
validate_and_parse_transaction <- function(record) {
  # Validasi Field Kritis
  if (!is.list(record)) {
    stop("Struktur transaksi malformed: Harus berupa list.")
  }
  
  required_fields <- c("tx_id", "amount", "currency", "status")
  missing_fields <- setdiff(required_fields, names(record))
  if (length(missing_fields) > 0) {
    stop(sprintf("Field wajib hilang: %s", paste(missing_fields, collapse = ", ")))
  }
  
  # Sanitasi dan Parse Tipe Data
  raw_amount <- record$amount
  parsed_amount <- suppressWarnings(as.numeric(raw_amount))
  
  if (is.na(parsed_amount) || is.nan(parsed_amount) || parsed_amount <= 0) {
    stop(sprintf("Nilai amount '%s' tidak valid atau non-positif.", as.character(raw_amount)))
  }
  
  # Validasi Status Domain
  valid_statuses <- c("PENDING", "COMPLETED", "SETTLED")
  if (!record$status %in% valid_statuses) {
    stop(sprintf("Status transaksi '%s' di luar domain valid.", record$status))
  }
  
  # Return Normalized Data Record
  list(
    tx_id  = as.character(record$tx_id),
    amount = parsed_amount,
    fx     = ifelse(record$currency == "USD", 15500.0, 1.0),
    status = record$status
  )
}

# ==============================================================================
# SIMULASI PAYLOAD & EKSEKUSI PIPELINE
# ==============================================================================

untrusted_raw_feed <- list(
  list(tx_id = "TX-001", amount = "500000", currency = "IDR", status = "SETTLED"),
  list(tx_id = "TX-002", amount = "-100", currency = "IDR", status = "COMPLETED"),     # Gagal: amount negatif
  list(tx_id = "TX-003", amount = "abc", currency = "IDR", status = "PENDING"),       # Gagal: parse error
  list(tx_id = "TX-004", amount = "25.5", currency = "USD", status = "SETTLED"),      # Sukses dengan FX
  list(tx_id = "TX-005", missing_key = TRUE),                                          # Gagal: schema error
  list(tx_id = "TX-006", amount = "1200000", currency = "IDR", status = "UNAUTHORIZED")# Gagal: invalid status
)

# Bungkus parser dengan safely combinator
safe_parser <- safely_execute(validate_and_parse_transaction)

# Eksekusi Transformasi: Zero Side-Effect Mapping
processed_pipeline <- lapply(untrusted_raw_feed, safe_parser)

# Filter Keberhasilan dan Kegagalan menggunakan Predikat Fungsional
successful_txs <- Filter(function(res) res$is_ok, processed_pipeline)
failed_txs     <- Filter(function(res) !res$is_ok, processed_pipeline)

cat(sprintf("Total Input : %d\n", length(untrusted_raw_feed)))
cat(sprintf("Valid Txs   : %d\n", length(successful_txs)))
cat(sprintf("Invalid Txs : %d\n\n", length(failed_txs)))

# Cetak Log Audit Kesalahan
cat("--- AUDIT LOG KEGAGALAN TRANSAKSI ---\n")
invisible(lapply(failed_txs, function(item) {
  cat(sprintf("[ERROR LOG] %s\n", item$error))
}))

# Ekstrak Data Valid ke Matriks Terstruktur Menggunakan Functional Extraction
normalized_records <- lapply(successful_txs, function(item) item$success)

# Kalkulasi Nilai Bersih IDR menggunakan Vectorized Functional
total_idr_volume <- Reduce(
  f = function(acc, cur) acc + (cur$amount * cur$fx),
  x = normalized_records,
  init = 0.0
)

cat(sprintf("\nTotal Terproses (IDR Ekuivalen): Rp %.2f\n", total_idr_volume))
