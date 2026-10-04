suppressPackageStartupMessages({
  library(rlang)
  library(purrr)
})

# ==============================================================================
# AUDIT RULE COMPILER & ENGINE
# ==============================================================================

#' Representasi Pembuatan Rule Generator Berbasis Tidy Metaprogramming
#' Mengonversi representasi deklaratif list menjadi rlang Quosure/Expression
compile_rule <- function(field, operator, threshold) {
  # 1. Validasi Keamanan Simbol (Mencegah Arbitrary Code Execution)
  valid_operators <- c(">", ">=", "<", "<=", "==", "!=", "%in%")
  if (!operator %in% valid_operators) {
    abort(paste0("Operator '", operator, "' tidak diizinkan demi keamanan!"))
  }
  
  field_sym <- sym(field)
  op_sym    <- sym(operator)
  
  # 2. Bangun Ekspresi AST Menggunakan Quasiquotation
  # Bentuk: .data[[field]] op threshold
  rule_expr <- expr((!!op_sym)(.data[[!!field]], !!threshold))
  
  return(rule_expr)
}

#' Rule Combiner: Menggabungkan Banyak Aturan Menggunakan Reduksi Fungsional
#' Transformasi: [Rule1, Rule2, Rule3] -> Rule1 & Rule2 & Rule3
compose_rules <- function(rule_expressions, logic = c("AND", "OR")) {
  logic <- match.arg(logic)
  combiner_op <- if (logic == "AND") sym("&") else sym("|")
  
  # Functional Reduction via purrr::reduce
  reduce(rule_expressions, function(acc, nxt) {
    expr((!!combiner_op)(!!acc, !!nxt))
  })
}

#' Execution Engine: Menerapkan Rule AST ke Data Tanpa Mutasi State Global
audit_dataset <- function(data, composed_rule_expr) {
  stopifnot(is.data.frame(data))
  
  # Masukkan pronoun data mask secara eksplisit
  # eval_tidy mengikat data frame ke .data pronoun
  eval_mask <- as_data_mask(data)
  
  # Evaluasi ekspresi terkomposisi
  tryCatch({
    mask_indices <- eval_tidy(composed_rule_expr, data = eval_mask)
    # Sanitasi index boolean dari missing values
    mask_indices <- mask_indices & !is.na(mask_indices)
    
    # Return subset transaksi yang melanggar audit
    data[mask_indices, , drop = FALSE]
  }, error = function(e) {
    abort(paste("Gagal mengevaluasi audit engine:", e$message))
  })
}

# ==============================================================================
# VERIFIKASI PADA DATASET SIMULASI TRANSAKSI KEUANGAN
# ==============================================================================

# Simulasi data transaksi
set.seed(42)
n_transaksi <- 10
portfolio_data <- data.frame(
  tx_id         = sprintf("TX-%04d", 1:n_transaksi),
  leverage      = c(1.2, 4.1, 2.3, 5.0, 3.2, 1.1, 3.8, 6.2, 2.9, 4.5),
  risk_exposure = c(1e6, 6e6, 2e6, 8e6, 3e6, 5e5, 7e6, 9e6, 4e6, 5.5e6),
  region        = c("US", "APAC", "EMEA", "APAC", "US", "EMEA", "APAC", "APAC", "US", "APAC"),
  stringsAsFactors = FALSE
)

# 1. Definisi Konfigurasi Rule Bisnis (Bisa berasal dari JSON atau Database)
business_rules_config <- list(
  list(field = "leverage",      operator = ">",  threshold = 3.5),
  list(field = "risk_exposure", operator = ">=", threshold = 5e6),
  list(field = "region",        operator = "==", threshold = "APAC")
)

# 2. Kompilasi Rule Secara Fungsional (Map: config -> AST expressions)
compiled_rules <- map(business_rules_config, function(rule) {
  compile_rule(
    field     = rule$field,
    operator  = rule$operator,
    threshold = rule$threshold
  )
})

# 3. Komposisi Rule Menjadi Satu AST Tunggal (AND condition)
final_audit_ast <- compose_rules(compiled_rules, logic = "AND")

cat("Terbangun AST Audit Rule Dinamis:\n")
print(final_audit_ast)
cat("\n")

# 4. Eksekusi Engine Terhadap Dataset
flagged_transactions <- audit_dataset(portfolio_data, final_audit_ast)

cat("Hasil Transaksi Yang Terkena Flag Pelanggaran Risiko:\n")
print(flagged_transactions)
