#* @apiTitle Production Inference Engine API
#* @apiDescription Enterprise-grade Plumber API skeleton with auth and async execution.
#* @apiVersion 1.0.0

library(plumber)
library(promises)
library(future)
library(checkmate)

# Konfigurasi worker pool untuk async execution
future::plan(future::multisession, workers = 2)

# --- 1. MIDDLEWARE: Request ID & Audit Logging ---
#* @filter trace
function(req, res) {
  req$request_id <- uuid::UUIDgenerate()
  req$start_time <- Sys.time()
  
  # Forward ke handler berikutnya
  plumber::forward()
  
  # Post-processing setelah handler selesai dieksekusi
  duration <- as.numeric(difftime(Sys.time(), req$start_time, units = "secs"))
  message(sprintf("[%s] %s %s - Status: %s - %.4fs", 
                  req$request_id, req$REQUEST_METHOD, req$PATH_INFO, res$status, duration))
}

# --- 2. MIDDLEWARE: Token-Based Authentication ---
#* @filter auth
function(req, res) {
  # Lewatkan endpoint dokumentasi dan healthcheck dari autentikasi
  unprotected_paths <- c("/healthz", "/__docs__/", "/openapi.json")
  if (req$PATH_INFO %in% unprotected_paths) {
    return(plumber::forward())
  }
  
  auth_header <- req$HTTP_AUTHORIZATION
  valid_token <- Sys.getenv("API_SECRET_TOKEN", "super-secret-production-token")
  
  if (is.null(auth_header) || !grepl("^Bearer ", auth_header)) {
    res$status <- 401
    return(list(error = "Unauthorized", message = "Missing or malformed Authorization header."))
  }
  
  token <- sub("^Bearer ", "", auth_header)
  if (!identical(token, valid_token)) {
    res$status <- 403
    return(list(error = "Forbidden", message = "Invalid API credentials."))
  }
  
  plumber::forward()
}

# --- 3. ENDPOINT: Healthcheck (Kubernetes Liveness/Readiness Probe) ---
#* Liveness probe untuk orchestrator
#* @get /healthz
#* @serializer json
function(res) {
  res$status <- 200
  list(
    status = "healthy",
    timestamp = Sys.time(),
    r_version = R.version.string
  )
}

# --- 4. ENDPOINT: Async Heavy Inference ---
#* Melakukan simulasi inferensi ML intensif secara asinkron
#* @post /v1/predict
#* @param payload:list Data input prediksi
#* @serializer json
function(req, res) {
  raw_body <- req$postBody
  
  # Validasi input menggunakan library checkmate (Defensive Programming)
  parsed_data <- tryCatch({
    jsonlite::fromJSON(raw_body)
  }, error = function(e) {
    NULL
  })
  
  if (is.null(parsed_data) || !is.list(parsed_data)) {
    res$status <- 400
    return(list(error = "Bad Request", message = "Invalid JSON payload provided."))
  }
  
  # Validasi skema (contoh sederhana: memastikan adanya field 'features')
  if (!"features" %in% names(parsed_data) || !is.numeric(parsed_data$features)) {
    res$status <- 422
    return(list(error = "Unprocessable Entity", message = "Field 'features' must be an array of numeric values."))
  }
  
  features <- parsed_data$features
  
  # Delegasikan kalkulasi berat ke proses latar belakang
  promises::future_promise({
    # Simulasi perhitungan matematika berat
    Sys.sleep(1.5) 
    score <- sum(features * 1.5) / length(features)
    
    list(
      score = score,
      classification = ifelse(score > 50, "HIGH_RISK", "LOW_RISK")
    )
  }) %...>% (function(val) {
    res$status <- 200
    list(
      request_id = req$request_id,
      result = val,
      processed_at = Sys.time()
    )
  }) %...!% (function(err) {
    res$status <- 500
    list(
      request_id = req$request_id,
      error = "Internal Server Error",
      detail = err$message
    )
  })
}
