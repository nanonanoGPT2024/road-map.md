library(plumber)
library(fraudEngine)

# Setup filter: Global Error Handling, Request Auditing, & Correlation ID
#* @filter request_trace
function(req, res) {
  req$request_id <- req$HTTP_X_CORRELATION_ID
  if (is.null(req$request_id) || req$request_id == "") {
    req$request_id <- paste0("req-", as.numeric(Sys.time()) * 1000)
  }
  
  start_time <- Sys.time()
  
  # Lanjutkan ke filter/endpoint berikutnya
  forward()
  
  end_time <- Sys.time()
  duration_ms <- as.numeric(difftime(end_time, start_time, units = "secs")) * 1000
  
  # Structured Logging via stdout (akan ditangkap oleh Docker log forwarder)
  log_entry <- list(
    request_id = req$request_id,
    method = req$REQUEST_METHOD,
    path = req$PATH_INFO,
    status = res$status,
    latency_ms = round(duration_ms, 2),
    client_ip = req$REMOTE_ADDR,
    timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
  )
  cat(jsonlite::toJSON(log_entry, auto_unbox = TRUE), "\n", file = stdout())
}

#* Evaluasi risiko anomali transaksi finansial
#* @post /api/v1/fraud/evaluate
#* @parser json
#* @serializer json
function(req, res) {
  payload <- req$body

  # Guard statement payload checking
  if (!is.list(payload) || is.null(payload$transaction_id)) {
    res$status <- 400
    return(list(
      error = "BadRequest",
      request_id = req$request_id,
      message = "Payload body kosong atau format invalid. Diperlukan JSON object."
    ))
  }

  # Eksekusi scoring dengan isolasi safe handler
  eval_result <- tryCatch(
    {
      fraudEngine::evaluate_transaction(
        transaction_id = as.character(payload$transaction_id),
        amount = as.numeric(payload$amount),
        velocity_1h = as.integer(payload$velocity_1h),
        is_foreign = as.integer(payload$is_foreign)
      )
    },
    error = function(err) {
      res$status <- 422
      list(
        error = "UnprocessableValidation",
        request_id = req$request_id,
        message = err$message
      )
    }
  )

  return(eval_result)
}

#* Liveness Probe untuk Kubernetes / AWS ECS
#* @get /healthz
#* @serializer json
function(res) {
  res$status <- 200
  list(status = "healthy")
}
