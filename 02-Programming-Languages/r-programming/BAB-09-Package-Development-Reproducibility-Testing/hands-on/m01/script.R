#' @title Evaluate Financial Transaction Anomalies
#' @description Implements sliding scale z-score analysis over customer historical 
#'   transaction records to detect potential fraudulent spikes.
#'
#' @param data A data.frame or tibble containing customer transactional ledger.
#' @param id_col Character string representing customer identifier column name.
#' @param amount_col Character string representing the numeric transactional amount column.
#' @param threshold Numeric scalar for threshold cutoff (standard deviations). Default 3.0.
#'
#' @return A data.frame subset containing flagged anomalies with appended diagnostic columns:
#'   \item{rolling_mean}{Calculated baseline mean for the subject}
#'   \item{rolling_sd}{Calculated baseline standard deviation}
#'   \item{anomaly_score}{Calculated absolute z-score}
#'
#' @export
#' @importFrom rlang .data abort is_character is_null
#' @examples
#' df <- data.frame(
#'   cust_id = c("A", "A", "A", "A", "B", "B"),
#'   tx_amount = c(10.5, 11.0, 9.8, 500.0, 100.0, 105.0)
#' )
#' detect_anomalies(df, id_col = "cust_id", amount_col = "tx_amount", threshold = 2.0)
detect_anomalies <- function(data, id_col, amount_col, threshold = 3.0) {
  # 1. Structural Validations
  if (!is.data.frame(data)) {
    rlang::abort("Input 'data' must inherit from data.frame.", class = "fraudguard_invalid_dataframe")
  }
  
  if (!rlang::is_character(id_col) || length(id_col) != 1) {
    rlang::abort("'id_col' must be a single string.", class = "fraudguard_param_error")
  }

  if (!rlang::is_character(amount_col) || length(amount_col) != 1) {
    rlang::abort("'amount_col' must be a single string.", class = "fraudguard_param_error")
  }

  cols <- names(data)
  if (!id_col %in% cols) {
    rlang::abort(sprintf("Column '%s' not found in dataset.", id_col), class = "fraudguard_missing_column")
  }
  if (!amount_col %in% cols) {
    rlang::abort(sprintf("Column '%s' not found in dataset.", amount_col), class = "fraudguard_missing_column")
  }

  if (!is.numeric(data[[amount_col]])) {
    rlang::abort(sprintf("Column '%s' must contain numeric values.", amount_col), class = "fraudguard_type_error")
  }

  # 2. Pure Execution via Base Splitting (Eliminates Heavy External Framework Overhead)
  split_records <- split(data, data[[id_col]])

  flagged_list <- lapply(split_records, function(sub_df) {
    amounts <- sub_df[[amount_col]]
    n <- length(amounts)

    if (n < 3) {
      return(NULL) # Insufficient statistical power to compute sigma
    }

    mu <- mean(amounts, na.rm = TRUE)
    sigma <- stats::sd(amounts, na.rm = TRUE)

    # If zero variance exists across records
    if (is.na(sigma) || sigma < .Machine$double.eps) {
      return(NULL)
    }

    z_scores <- abs((amounts - mu) / sigma)
    is_anomaly <- z_scores > threshold

    if (!any(is_anomaly)) {
      return(NULL)
    }

    sub_res <- sub_df[is_anomaly, , drop = FALSE]
    sub_res$rolling_mean <- mu
    sub_res$rolling_sd <- sigma
    sub_res$anomaly_score <- z_scores[is_anomaly]
    sub_res
  })

  # 3. Aggregation of Sparse Results
  consolidated <- do.call(rbind, flagged_list)
  if (is.null(consolidated) || nrow(consolidated) == 0) {
    # Kembalikan empty frame dengan skema yang terdefinisi rapi
    empty_df <- data[0, , drop = FALSE]
    empty_df$rolling_mean <- numeric(0)
    empty_df$rolling_sd <- numeric(0)
    empty_df$anomaly_score <- numeric(0)
    rownames(empty_df) <- NULL
    return(empty_df)
  }

  rownames(consolidated) <- NULL
  consolidated
}
