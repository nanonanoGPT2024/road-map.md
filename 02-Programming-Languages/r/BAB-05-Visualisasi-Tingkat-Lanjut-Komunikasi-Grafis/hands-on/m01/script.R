# ==============================================================================
# SCRIPT 02: Sistem Monitoring Latensi Finansial Komposit Skala Produksi
# ==============================================================================

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
  library(scales)
  library(dplyr)
  library(ragg) # Driver Grafis AGG Berkinerja Tinggi
})

# 1. Pembangkitan Data Telemetri Sintetis Skala Besar
set.seed(101)
timestamps <- seq(
  from = as.POSIXct("2026-03-30 00:00:00", tz = "UTC"),
  to = as.POSIXct("2026-03-30 23:00:00", tz = "UTC"),
  by = "15 mins"
)
n_points <- length(timestamps)

# Simulasi metrik transaksi
telemetry_data <- data.frame(
  time = timestamps,
  tx_volume = round(rnorm(n_points, mean = 12000, sd = 2500) + 
                    sin(seq(0, 3*pi, length.out = n_points)) * 4000),
  error_count = rpois(n_points, lambda = 8),
  latency_p50 = rnorm(n_points, mean = 45, sd = 5),
  latency_p99 = rnorm(n_points, mean = 210, sd = 30) + 
                c(rep(0, 60), rchisq(n_points - 60, df = 25) * 8)
) %>%
  mutate(
    error_rate_pct = (error_count / tx_volume) * 100,
    sla_breached = latency_p99 > 350
  )

# 2. Global Style Variables
COLOR_PRIMARY   <- "#0F172A" # Dark Slate
COLOR_ACCENT    <- "#2563EB" # Blue
COLOR_DANGER    <- "#DC2626" # Deep Crimson
COLOR_GRID      <- "#E2E8F0" # Slate-200
FONT_FAMILY     <- "sans"

# Base Theme Konsisten
theme_telemetry <- function() {
  theme_minimal(base_family = FONT_FAMILY, base_size = 10) %+replace%
    theme(
      plot.title = element_text(size = 12, face = "bold", color = COLOR_PRIMARY, hjust = 0, margin = margin(b = 4)),
      plot.subtitle = element_text(size = 9, color = "#64748B", hjust = 0, margin = margin(b = 10)),
      plot.caption = element_text(size = 8, color = "#94A3B8", hjust = 1, margin = margin(t = 6)),
      panel.grid.major.y = element_line(color = COLOR_GRID, linewidth = 0.4),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_line(color = COLOR_GRID, linewidth = 0.2, linetype = "dotted"),
      panel.background = element_rect(fill = "#FFFFFF", color = NA),
      plot.background = element_rect(fill = "#FFFFFF", color = NA),
      axis.title = element_text(size = 9, face = "bold", color = "#334155"),
      axis.text = element_text(size = 8, color = "#64748B"),
      legend.position = "none",
      plot.margin = margin(t = 8, r = 16, b = 8, l = 16)
    )
}

# 3. Plot Atas: Throughput Volume Transaksi & Anomali Error
p_volume <- ggplot(telemetry_data, aes(x = time)) +
  geom_col(
    aes(y = tx_volume, fill = sla_breached),
    width = 800,
    alpha = 0.85
  ) +
  geom_line(
    aes(y = error_rate_pct * 15000), 
    color = COLOR_DANGER,
    linewidth = 0.8
  ) +
  scale_fill_manual(values = c("FALSE" = "#94A3B8", "TRUE" = COLOR_DANGER)) +
  scale_y_continuous(
    name = "Volume Transaksi / 15m",
    labels = scales::label_number(scale_cut = scales::cut_short_scale()),
    sec.axis = sec_axis(
      transform = ~ . / 15000,
      name = "Error Rate (%)",
      labels = scales::label_percent(scale = 1, accuracy = 0.1)
    )
  ) +
  scale_x_datetime(labels = scales::label_date(format = "%H:%M", tz = "UTC"), expand = c(0, 0)) +
  labs(
    title = "Audit Telemetri API Gateway & Pelanggaran Ambang Batas",
    subtitle = "Volume transaksi normal vs titik anomali kegagalan SLA performa",
    x = NULL
  ) +
  theme_telemetry() +
  theme(axis.text.x = element_blank()) # Menghilangkan label X untuk sinkronisasi layout vertikal

# 4. Plot Bawah: Karakteristik Tail-Latency (P50 vs P99)
p_latency <- ggplot(telemetry_data, aes(x = time)) +
  geom_ribbon(
    aes(ymin = latency_p50, ymax = latency_p99),
    fill = COLOR_ACCENT,
    alpha = 0.2
  ) +
  geom_line(aes(y = latency_p50), color = COLOR_ACCENT, linewidth = 0.7, linetype = "dotted") +
  geom_line(aes(y = latency_p99), color = COLOR_ACCENT, linewidth = 1.0) +
  geom_hline(yintercept = 350, color = COLOR_DANGER, linetype = "dashed", linewidth = 0.7) +
  annotate(
    geom = "label",
    x = max(telemetry_data$time) - 1800,
    y = 350,
    label = "SLA Breach Threshold: 350ms",
    size = 2.7,
    color = "#FFFFFF",
    fill = COLOR_DANGER,
    fontface = "bold",
    label.size = NA,
    hjust = 1
  ) +
  scale_y_continuous(
    name = "Latency (Milidetik)",
    limits = c(0, max(telemetry_data$latency_p99) * 1.15),
    labels = scales::label_comma(suffix = " ms")
  ) +
  scale_x_datetime(
    name = "Waktu Pemantauan (UTC) - 30 Maret 2026",
    labels = scales::label_date(format = "%H:%M", tz = "UTC"),
    expand = c(0, 0)
  ) +
  labs(
    subtitle = "Distribusi Tail Latency: P50 (Dotted) vs P99 (Solid) dengan SLA Envelope Area",
    caption = "Sistem Audit Reliabilitas Infrastruktur Finansial - Laporan Otomatis"
  ) +
  theme_telemetry()

# 5. Komposisi Aljabar Tingkat Lanjut Menggunakan Patchwork
composite_dashboard <- (p_volume / p_latency) +
  plot_layout(heights = c(1.2, 1.0)) &
  theme(
    # Memastikan sinkronisasi batas canvas kiri dan kanan secara absolut
    plot.margin = margin(r = 20, l = 20)
  )

# 6. Kompilasi dan Ekspor Menggunakan Device Modern ragg::agg_png
output_file <- file.path(tempdir(), "financial_latency_audit.png")

ragg::agg_png(
  filename = output_file,
  width = 11,
  height = 7,
  units = "in",
  res = 320, # Kualitas Cetak Tinggi (Retina/Print DPI)
  scaling = 1.0
)

# Render hierarki gtable ke device aktif
print(composite_dashboard)

# Flushing memory buffer dan penutupan koneksi file
invisible(dev.off())

message(paste("[SUCCESS] Dashboard berhasil dirender ke target:", output_file))
