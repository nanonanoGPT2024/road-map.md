library(R6)
library(S7)

# ==============================================================================
# 1. DOMAIN LAYER: S7 CONTRACTS & MULTIPLE DISPATCH
# ==============================================================================

# Entitas Abstrak: Instrumen Finansial
FinancialInstrument <- new_class(
  name = "FinancialInstrument",
  properties = list(
    ticker   = class_character,
    quantity = class_numeric,
    price    = class_numeric
  ),
  validator = function(self) {
    if (self@quantity <= 0) return("Quantity harus bernilai positif.")
    if (self@price <= 0) return("Price harus bernilai positif.")
    NULL
  }
)

# Entitas Konkret: Saham (Equity)
Equity <- new_class(
  name = "Equity",
  parent = FinancialInstrument,
  properties = list(
    exchange = class_character
  )
)

# Entitas Konkret: Obligasi (Bond) dengan kupon
Bond <- new_class(
  name = "Bond",
  parent = FinancialInstrument,
  properties = list(
    coupon_rate = class_numeric,
    maturity_years = class_numeric
  ),
  validator = function(self) {
    if (self@coupon_rate < 0 || self@coupon_rate > 1) {
      return("Coupon rate harus berada pada rentang 0.0 - 1.0.")
    }
    NULL
  }
)

# Generic Method: Kalkulasi Nominal Nilai Pasar
market_value <- new_generic("market_value", "instrument")

method(market_value, Equity) <- function(instrument) {
  instrument@quantity * instrument@price
}

method(market_value, Bond) <- function(instrument) {
  # Value kalkulasi obligasi disederhanakan: par value + accrued amortized coupon
  base_val <- instrument@quantity * instrument@price
  coupon_accrual <- base_val * (instrument@coupon_rate / instrument@maturity_years)
  return(base_val + coupon_accrual)
}

# ==============================================================================
# 2. INFRASTRUCTURE & STATE LAYER: R6 CLEARING LEDGER
# ==============================================================================

ClearingLedger <- R6Class(
  classname = "ClearingLedger",
  private = list(
    ..broker_id   = character(0),
    ..cash_balance = 0.0,
    ..holdings     = list(),
    ..audit_trail  = list(),
    
    record_audit = function(action, amount, status) {
      audit_id <- paste0("AUD-", as.integer(Sys.time()), "-", length(private$..audit_trail) + 1)
      entry <- list(
        id = audit_id,
        action = action,
        amount = amount,
        timestamp = Sys.time(),
        status = status
      )
      private$..audit_trail[[length(private$..audit_trail) + 1]] <- entry
    }
  ),
  public = list(
    initialize = function(broker_id, initial_cash) {
      stopifnot(is.character(broker_id) && length(broker_id) == 1)
      stopifnot(is.numeric(initial_cash) && initial_cash >= 0)
      
      private$..broker_id <- broker_id
      private$..cash_balance <- initial_cash
      private$record_audit("INITIALIZE", initial_cash, "SUCCESS")
    },
    
    # Eksekusi kliring instrumen finansial
    clear_order = function(instrument, side = c("BUY", "SELL")) {
      side <- match.arg(side)
      
      # Validasi kontrak domain S7
      if (!S7_inherits(instrument, FinancialInstrument)) {
        stop("LedgerException: Objek transaksi bukan merupakan FinancialInstrument yang valid.")
      }
      
      # Polimorfisme fungsional melalui S7 generic
      execution_cost <- market_value(instrument)
      ticker <- instrument@ticker
      
      if (side == "BUY") {
        if (private$..cash_balance < execution_cost) {
          private$record_audit(paste("BUY", ticker), execution_cost, "FAILED_INSUFFICIENT_FUNDS")
          stop(sprintf("Insufisiensi Kas: Butuh %.2f, Saldo %.2f", execution_cost, private$..cash_balance))
        }
        
        # Mutasi State In-Place
        private$..cash_balance <- private$..cash_balance - execution_cost
        current_qty <- private$..holdings[[ticker]] %||% 0
        private$..holdings[[ticker]] <- current_qty + instrument@quantity
        
      } else if (side == "SELL") {
        current_qty <- private$..holdings[[ticker]] %||% 0
        if (current_qty < instrument@quantity) {
          private$record_audit(paste("SELL", ticker), execution_cost, "FAILED_INSUFFICIENT_HOLDINGS")
          stop(sprintf("Insufisiensi Portofolio: Saham dimiliki %.0f, Order Jual %.0f", 
                       current_qty, instrument@quantity))
        }
        
        private$..cash_balance <- private$..cash_balance + execution_cost
        private$..holdings[[ticker]] <- current_qty - instrument@quantity
      }
      
      private$record_audit(paste(side, ticker), execution_cost, "SETTLED")
      return(invisible(TRUE))
    },
    
    print = function(...) {
      cat("=========================================\n")
      cat(sprintf("Broker ID     : %s\n", private$..broker_id))
      cat(sprintf("Cash Balance  : $%.2f\n", private$..cash_balance))
      cat("Holdings      :\n")
      if (length(private$..holdings) == 0) {
        cat("  [KOSONG]\n")
      } else {
        for (tkr in names(private$..holdings)) {
          cat(sprintf("  - %s: %.0f unit\n", tkr, private$..holdings[[tkr]]))
        }
      }
      cat(sprintf("Audit Entries : %d records\n", length(private$..audit_trail)))
      cat("=========================================\n")
      invisible(self)
    }
  ),
  active = list(
    cash_balance = function() { private$..cash_balance },
    holdings = function() { private$..holdings },
    audit_trail = function() { private$..audit_trail }
  )
)

# Helper untuk menangani NULL values
`%||%` <- function(a, b) if (is.null(a)) b else a

# ==============================================================================
# 3. CONCURRENT-READY EXECUTION TEST PIPELINE
# ==============================================================================

# Inisialisasi State Engine
ledger <- ClearingLedger$new(broker_id = "BRK-NYC-001", initial_cash = 1000000)

# Inisialisasi Domain Entities (S7 Contracts)
apple_stock <- Equity(
  ticker = "AAPL", 
  quantity = 1500, 
  price = 180.5, 
  exchange = "NASDAQ"
)

us_treasury <- Bond(
  ticker = "UST10Y", 
  quantity = 500, 
  price = 980.0, 
  coupon_rate = 0.045, 
  maturity_years = 10
)

# Operasi Transaksi Melalui Engine
message("Eksekusi Order Pembelian AAPL...")
ledger$clear_order(apple_stock, side = "BUY")

message("Eksekusi Order Pembelian Obligasi UST10Y...")
ledger$clear_order(us_treasury, side = "BUY")

# Cetak status buku besar
print(ledger)

# Mencoba transaksi yang melanggar batasan saldo
tryCatch({
  massive_order <- Equity(ticker = "TSLA", quantity = 10000, price = 250.0, exchange = "NASDAQ")
  ledger$clear_order(massive_order, side = "BUY")
}, error = function(e) {
  message(sprintf("Caught expected business exception: %s", e$message))
})

# Verifikasi Audit Trail Terakhir
tail(ledger$audit_trail, 1)
