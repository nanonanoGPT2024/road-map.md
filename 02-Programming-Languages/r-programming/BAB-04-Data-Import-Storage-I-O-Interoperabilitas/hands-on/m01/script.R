# ==============================================================================
# PIPELINE I/O KOMPREHENSIF: FUNDAMENTAL DEMONSTRATION
# ==============================================================================

# Pastikan package yang dibutuhkan tersedia
required_pkgs <- c("data.table", "arrow", "qs")
for (pkg in required_pkgs) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}

library(data.table)
library(arrow)
library(qs)

# Inisialisasi direktori kerja terisolasi
temp_io_dir <- file.path(tempdir(), "r_io_lab")
if (!dir.exists(temp_io_dir)) dir.create(temp_io_dir, recursive = TRUE)

# ------------------------------------------------------------------------------
# 1. Pembangkitan Data Sintetis Skala Menengah (~500,000 baris)
# ------------------------------------------------------------------------------
set.seed(42)
n_rows <- 500000

synthetic_data <- data.table(
  transaction_id = 1:n_rows,
  customer_id    = sample(sprintf("CUST_%05d", 1:50000), n_rows, replace = TRUE),
  amount         = round(rnorm(n_rows, mean = 250, sd = 75), 2),
  status         = sample(c("PENDING", "COMPLETED", "FAILED"), n_rows, replace = TRUE, prob = c(0.1, 0.85, 0.05)),
  timestamp      = Sys.time() - runif(n_rows, min = 0, max = 86400 * 30)
)

raw_csv_path  <- file.path(temp_io_dir, "transactions.csv")
native_rds_path <- file.path(temp_io_dir, "transactions.rds")
modern_qs_path  <- file.path(temp_io_dir, "transactions.qs")
parquet_path    <- file.path(temp_io_dir, "transactions.parquet")

# Simpan sebagai CSV dasar
data.table::fwrite(synthetic_data, raw_csv_path)

# ------------------------------------------------------------------------------
# 2. Base R Connections API: Chunk Streaming (Memproses baris tanpa saturasi RAM)
# ------------------------------------------------------------------------------
process_csv_in_chunks <- function(file_path, chunk_size = 100000) {
  con <- file(file_path, open = "r")
  on.exit(close(con), add = TRUE) # Menjamin resource dibebaskan
  
  header <- readLines(con, n = 1)
  col_names <- strsplit(header, ",")[[1]]
  
  total_completed_amount <- 0.0
  total_completed_rows <- 0L
  
  repeat {
    lines <- readLines(con, n = chunk_size)
    if (length(lines) == 0) break
    
    # Konversi teks baris ke data.table sederhana
    chunk_dt <- data.table::fread(text = paste(lines, collapse = "\n"), col.names = col_names)
    
    # Agregasi stream
    completed_subset <- chunk_dt[status == "COMPLETED"]
    total_completed_amount <- total_completed_amount + sum(completed_subset$amount)
    total_completed_rows <- total_completed_rows + nrow(completed_subset)
  }
  
  return(list(rows = total_completed_rows, total_amount = total_completed_amount))
}

# ------------------------------------------------------------------------------
# 3. High-Speed Threaded Parsing: data.table::fread
# ------------------------------------------------------------------------------
read_via_fread <- function(file_path) {
  # fread menggunakan multi-thread & mmap secara otomatis
  dt <- data.table::fread(
    file            = file_path,
    nThread         = 2, # Membatasi ke 2 thread untuk komparasi terstandar
    showProgress    = FALSE,
    select          = c("transaction_id", "amount", "status") # Load kolom yang relevan saja
  )
  return(dt)
}

# ------------------------------------------------------------------------------
# 4. Binary Serializations: Native RDS vs Modern QS
# ------------------------------------------------------------------------------
# Simpan via native RDS & QS
saveRDS(synthetic_data, native_rds_path, compress = "gzip")
qs::qsave(synthetic_data, modern_qs_path, preset = "fast", nthreads = 2)

read_via_qs <- function(file_path) {
  return(qs::qread(file_path, nthreads = 2))
}

# ------------------------------------------------------------------------------
# 5. Columnar Engine & Predicate Pushdown: Apache Parquet
# ------------------------------------------------------------------------------
arrow::write_parquet(
  x           = synthetic_data, 
  sink        = parquet_path,
  compression = "zstd", 
  compression_level = 3
)

query_parquet_pushdown <- function(file_path) {
  # Buka dataset sebagai pointer metadata Arrow
  ds <- arrow::open_dataset(file_path, format = "parquet")
  
  # Lakukan query: Hanya scan partisi yang status == 'COMPLETED' dan ambil kolom tertentu
  result <- ds |>
    dplyr::filter(status == "COMPLETED" & amount > 300) |>
    dplyr::select(transaction_id, amount) |>
    dplyr::collect() # Mengalokasikan data ke R HANYA pada hasil akhir
    
  return(result)
}

# ------------------------------------------------------------------------------
# Eksekusi Demonstrasi
# ------------------------------------------------------------------------------
cat("[1] Menjalankan Base R Chunk Processing...\n")
chunk_res <- process_csv_in_chunks(raw_csv_path, chunk_size = 150000)
cat(sprintf("    Total Baris Sukses: %d | Total Nilai: %.2f\n", chunk_res$rows, chunk_res$total_amount))

cat("[2] Menjalankan data.table::fread Parsing...\n")
dt_res <- read_via_fread(raw_csv_path)
cat(sprintf("    Baris dimuat: %d | Kolom: %d\n", nrow(dt_res), ncol(dt_res)))

cat("[3] Menjalankan Deserialisasi QS...\n")
qs_res <- read_via_qs(modern_qs_path)
cat(sprintf("    Baris dimuat dari format qs: %d\n", nrow(qs_res)))

cat("[4] Menjalankan Arrow Predicate Pushdown...\n")
arrow_res <- query_parquet_pushdown(parquet_path)
cat(sprintf("    Baris hasil pushdown query: %d\n", nrow(arrow_res)))
