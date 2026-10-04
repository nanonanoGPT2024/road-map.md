# ==============================================================================
# SISTEM TELEMETRI TRANSAKSI FINTECH: DETEKSI ANOMALI & LATENSI
# ==============================================================================
suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(scales)
  library(patchwork)
  library(ggrastr) # Wajib: High-performance rendering
})

# 1. GENERASI TELEMETRI SINTETIK SKALA TINGGI
set.seed(101)
N <- 150000

base_time <- as.POSIXct("2024-10-01 00:00:00", tz = "UTC")
dt_telemetry <- data.table(
  txn_id    = 1:N,
  timestamp = base_time + runif(N, min = 0, max = 86400), # 24 Jam
  provider  = sample(c("VISA_DIRECT", "MC_GATEWAY", "QRIS_FAST", "VA_SETTLE"), 
                     N, replace = TRUE, prob = c(0.3, 0.25, 0.35, 0.1)),
  status    = sample(c("SUCCESS", "FAILED", "TIMEOUT"), 
                     N, replace = TRUE, prob = c(0.92, 0.05, 0.03)),
  amount    = rlnorm(N, meanlog = 5.2, sdlog = 1.1)
)

# Injeksi degradasi microservice: Pada jam 14:00 - 16:00, QRIS_FAST mengalami latency-spike
dt_telemetry[, hour := as.numeric(format(timestamp, "%H"))]
dt_telemetry[, latency_ms := rgamma(.N, shape = 2, scale = 40)] # Latensi dasar ~80ms

# Simulasi krisis performa
dt_telemetry[hour %between% c(14, 16) & provider == "QRIS_FAST", 
             `:=`(latency_ms = latency_ms * runif(.N, 5, 25),
                  status = sample(c("SUCCESS", "FAILED", "TIMEOUT"), .N, 
                                  replace = TRUE, prob = c(0.4, 0.3, 0.3)))]

# 2. KOMPUTASI AGREGAT PERFORMA PER JAM MENGGUNAKAN DATA.TABLE
dt_summary <- dt_telemetry[, .(
  total_txns = .N,
  error_rate = sum(status != "SUCCESS") / .N,
  p95_latency = as.numeric(quantile(latency_ms, 0.95)),
  p50_latency = as.numeric(median(latency_ms))
), by = .(provider, hour)][order(provider, hour)]

# 3. VISUALISASI 1: ANALISIS JEJAK LATENSI MASIF MENGGUNAKAN RASTERISASI
# Mencegah memory blowout dan overplotting file vektor sebesar ratusan MB
p_scatter_stream <- ggplot(dt_telemetry, aes(x = timestamp, y = latency_ms, color = status)) +
  rasterise(
    geom_point(alpha = 0.2, size = 0.5), 
    dpi = 300, 
    dev = "ragg"
  ) +
  scale_y_log10(
    labels = label_comma(suffix = " ms"),
    breaks = c(10, 100, 1000, 10000, 50000)
  ) +
  scale_x_datetime(date_labels = "%H:%M", date_breaks = "4 hours") +
  scale_color_manual(
    values = c("SUCCESS" = "#2ecc71", "FAILED" = "#e74c3c", "TIMEOUT" = "#f39c12")
  ) +
  labs(
    title = "Audit Jejak Latensi Transaksi Transaksional (24-Jam)",
    subtitle = "Rasterized scatter rendering mengisolasi lonjakan latensi tanpa degradasi rendering",
    x = "Waktu (UTC)",
    y = "Latency (Log10)",
    color = "Status Eksekusi"
  ) +
  theme_minimal(base_size = 10) +
  theme(legend.position = "top")

# 4. VISUALISASI 2: DUAL-METRIC IMPACT HEATMAP MATRIX
p_heatmap <- ggplot(dt_summary, aes(x = hour, y = provider, fill = error_rate)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = percent(error_rate, accuracy = 0.1)), 
            color = ifelse(dt_summary$error_rate > 0.15, "white", "black"), 
            size = 2.8) +
  scale_fill_gradientn(
    colors = c("#f8f9fa", "#f39c12", "#c0392b"),
    labels = percent_format(),
    name = "Rasio Eror"
  ) +
  scale_x_continuous(breaks = 0:23) +
  labs(
    title = "Konsentrasi Kegagalan Sistem per Provider",
    x = "Jam Operasional",
    y = NULL
  ) +
  theme_minimal(base_size = 10) +
  theme(panel.grid = element_blank())

# 5. VISUALISASI 3: PERBANDINGAN TREN PERSENTIL 95 (P95)
p_p95_trend <- ggplot(dt_summary, aes(x = hour, y = p95_latency, color = provider)) +
  geom_line(linewidth = 1) +
  geom_point(size = 1.8) +
  scale_y_continuous(labels = label_comma(suffix = " ms")) +
  scale_x_continuous(breaks = seq(0, 23, by = 2)) +
  scale_color_brewer(palette = "Dark2") +
  labs(
    title = "Dinamika Latensi Ekstrem (P95)",
    x = "Jam Operasional",
    y = "Latensi P95 (ms)",
    color = "Provider"
  ) +
  theme_minimal(base_size = 10) +
  theme(legend.position = "bottom")

# 6. PENYUSUNAN ARSITEKTUR KANVAS TERPADU MENGGUNAKAN PATCHWORK
production_telemetry_board <- (p_scatter_stream) / 
                              (p_heatmap | p_p95_trend) +
                              plot_layout(heights = c(1.3, 1)) +
                              plot_annotation(
                                title = "INSIDEN METRIK GATEWAY: POST-MORTEM DIAGNOSTIC REPORT",
                                subtitle = "Deteksi degradasi lokalitas layanan QRIS_FAST pada rentang waktu 14:00 - 16:00 UTC",
                                caption = "FinTech Observability Data Engine. Tim Performance SRE.",
                                theme = theme(
                                  plot.title = element_text(size = 14, face = "bold", color = "#1a252f"),
                                  plot.subtitle = element_text(size = 10, color = "#7f8c8d")
                                )
                              )

# Render output final ke device
print(production_telemetry_board)
