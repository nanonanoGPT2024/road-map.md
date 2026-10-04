library(dplyr)
library(tidyr)
library(tibble)
library(stringr)
library(lubridate)

# Simulasi Raw Ingestion Dataset
set.seed(42)
n_records <- 1000

raw_transactions <- tibble(
  trx_id = paste0("TXN-", 100000 + seq_len(n_records)),
  merchant_id = sample(paste0("MRC-", 10:15), n_records, replace = TRUE),
  timestamp = as.character(
    now() - runif(n_records, min = 0, max = 86400 * 30)
  ),
  raw_amount = paste0("IDR ", format(round(runif(n_records, 10000, 2000000), 0), big.mark = ",")),
  payment_status = sample(c("SETTLED", "settled", "PAID", "FAILED", "REFUNDED", NA), n_records, replace = TRUE),
  fee_metadata = sample(c("plat:2500|gw:1500|disc:0", "plat:5000|gw:2000|disc:1000", "plat:1000|gw:500|disc:500"), n_records, replace = TRUE)
)

# -------------------------------------------------------------
# PRODUCTION PIPELINE IMPLEMENTATION
# -------------------------------------------------------------

clean_settlement_pipeline <- function(data_input) {
  stopifnot(is.data.frame(data_input))
  
  processed_df <- data_input |>
    # Defensive Parsing: Bersihkan string & standardisasi tipe data
    mutate(
      timestamp = ymd_hms(.data$timestamp),
      status_clean = str_to_upper(str_trim(.data$payment_status)),
      gross_amount_num = str_remove_all(.data$raw_amount, "[^0-9]") |> as.numeric()
    ) |>
    # Filtering: Hapus anomali atau data invalid
    filter(
      !is.na(.data$timestamp),
      !is.na(.data$gross_amount_num),
      .data$status_clean %in% c("SETTLED", "PAID", "REFUNDED")
    ) |>
    # Normalisasi Status
    mutate(
      is_success = .data$status_clean %in% c("SETTLED", "PAID")
    ) |>
    # Ekstraksi Metadata Biaya (tidyr separate & pivot transformations)
    separate_longer_delim(.data$fee_metadata, delim = "|") |>
    separate_wider_delim(
      .data$fee_metadata,
      delim = ":",
      names = c("fee_type", "fee_amount")
    ) |>
    mutate(fee_amount = as.numeric(.data$fee_amount)) |>
    pivot_wider(
      names_from = .data$fee_type,
      values_from = .data$fee_amount,
      values_fill = 0,
      names_prefix = "fee_"
    ) |>
    # Feature Derivation: Net Realization Calculation
    mutate(
      net_amount = if_else(
        .data$is_success,
        .data$gross_amount_num - (.data$fee_plat + .data$fee_gw) + .data$fee_disc,
        0
      ),
      time_bucket = case_when(
        hour(.data$timestamp) >= 0  & hour(.data$timestamp) < 6  ~ "DAWN",
        hour(.data$timestamp) >= 6  & hour(.data$timestamp) < 12 ~ "MORNING",
        hour(.data$timestamp) >= 12 & hour(.data$timestamp) < 18 ~ "AFTERNOON",
        TRUE                                                     ~ "NIGHT"
      )
    )

  # Agregasi Analitis (dplyr 1.1+ transient grouping via .by)
  merchant_kpi <- processed_df |>
    reframe(
      total_transactions = n(),
      total_successful_volume = sum(.data$gross_amount_num[.data$is_success], na.rm = TRUE),
      net_settled_revenue = sum(.data$net_amount, na.rm = TRUE),
      total_platform_fees = sum(.data$fee_plat[.data$is_success], na.rm = TRUE),
      refund_rate = mean(!.data$is_success, na.rm = TRUE),
      .by = c(.data$merchant_id, .data$time_bucket)
    ) |>
    arrange(.data$merchant_id, desc(.data$net_settled_revenue))
  
  return(merchant_kpi)
}

# Eksekusi Pipeline
final_kpi_table <- clean_settlement_pipeline(raw_transactions)
print(head(final_kpi_table, 10))
