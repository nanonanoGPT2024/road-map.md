# BAB-05: Visualisasi Tingkat Lanjut & Komunikasi Grafis
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *software engineer* dan *data architect* diharapkan mampu:
- Membedah arsitektur internal *graphics engine* R (`graphics`, `grid`, dan *pipeline* rendering `ggplot2`).
- Mengembangkan ekstensi kustom `ggplot2` tingkat lanjut dengan mengimplementasikan `Stat` dan `Geom` berbasis `ggproto`.
- Memanipulasi *graphical objects* (`grob`), *viewports*, dan struktur layout `gtable` secara programatik untuk perakitan kanvas kompleks.
- Membangun *headless visualization microservice/pipeline* berbasis R yang memproses data berdensitas tinggi secara deterministik, efisien terhadap memori, dan bebas dari *memory leaks*.
- Mengoptimalkan output grafis untuk lingkungan produksi skala enterprise (PDF/A, SVG interaktif, rasterisasi resolusi tinggi via backend `ragg` dan `Cairo`).

---

### 2. Prerequisite
Untuk memahami materi secara optimal, Anda wajib menguasai:
- **Object-Oriented Programming di R**: Pemahaman terhadap S3 system, environment scoping, dan paradigma prototipe (`ggproto`).
- **Data Wrangling Tingkat Lanjut**: Penguasaan mendalam atas `data.table` atau `dplyr` dan `rlang` (*tidy evaluation* / NSE).
- **Sistem Operasi & Grafis Komputasi**: Konsep dasar *raster* vs *vector*, manajemen *color space* (sRGB, Display P3, CMYK), tipografi digital (FreeType, HarfBuzz), dan *graphics device buffer*.

---

### 3. Concept & Internal Architecture

Visualisasi di R beroperasi di atas abstraksi berlapis yang menghubungkan kode deklaratif tingkat tinggi dengan *subsystem* grafis berbasis C pada *core runtime*.

```
+-------------------------------------------------------------------+
|                        ggplot2 Layer                              |
|   User API: ggplot() + geom_*() + stat_*() + theme()              |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                 ggproto Object System (State Machine)             |
|   Data Transformation -> Stat$compute_*()                         |
|   Geometric Mapping   -> Geom$draw_*()                            |
+---------------------------------+---------------------------------+
                                  | Menghasilkan
                                  v
+-------------------------------------------------------------------+
|                           grid Engine                             |
|   - Viewports (Hierarchical coordinate systems & clipping)        |
|   - Grobs (grob, gList, gTree: lines, text, rect, polygons)       |
|   - gtable (Tabular layout engine for nested grobs)               |
+---------------------------------+---------------------------------+
                                  | Evaluasi rendering
                                  v
+-------------------------------------------------------------------+
|                      C-Level Graphics Engine                      |
|   (R Graphics Device Driver Interface: GEdevice, GEDevDesc)       |
+---------------------------------+---------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+---------------------------------+   +-----------------------------+
| Vector Backends (Cairo, PDF)    |   | Raster Backends (ragg, AGG) |
| PostScript, SVG, PDF Canvas     |   | Pixel Buffer, Anti-Aliasing |
+---------------------------------+   +-----------------------------+
```

#### Komponen Utama Arsitektur

1. **ggproto Object System**:
   Sistem prototipe mandiri (terinspirasi dari JavaScript/Self) yang digunakan `ggplot2` untuk menghindari *overhead* S4. Objek `ggproto` memiliki metode dan *state* yang dapat diwariskan (*inherited*). Siklus hidup eksekusi `ggplot2` berjalan deterministik:
   $$\text{Layer Data} \xrightarrow{\text{Stat}} \text{Transformed Data} \xrightarrow{\text{Scale}} \text{Aesthetic Coordinates} \xrightarrow{\text{Geom}} \text{Grob}$$

2. **The `grid` Subsystem**:
   Fondasi grafis modern R yang memisahkan definisi objek dari proses rendering fisik. 
   - **Viewport**: Node koordinat hierarkis dengan transformasi skala matriks ($x, y, \text{width}, \text{height}$) dan mekanisme *clipping*.
   - **Grob (Graphical Object)**: Struktur data yang merepresentasikan primitif visual (lingkaran, poligon, teks) sebelum diarahkan ke *device driver*.
   - **gTree**: Komposisi *tree* berisi *nested grobs* dan *child viewports*.

3. **Graphics Engine & Device Drivers**:
   R Core menyediakan API C (`R_GE_*`) yang dihubungkan ke *driver* spesifik. Backend standar (`quartz`, `windows`, `x11`) memiliki limitasi performa dan inkonsistensi rendering lintas platform. Pada pipeline enterprise modern, backend modern wajib digunakan:
   - `ragg`: Berbasis *Anti-Grain Geometry* (AGG) C++ library. Sangat cepat, rendering sub-pixel presisi, tidak bergantung pada dependensi display server X11/Wayland.
   - `Cairo`: Menangani *vector rendering* berkualitas tinggi (PDF, SVG) dengan dukungan *font embedding* native.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Base R | Pendekatan Enterprise (`grid` + `ggproto` + `ragg`) |
| :--- | :--- | :--- |
| **Arsitektur Layout** | Mengandalkan mutasi global `par(mfrow)` dan *side-effects*. Sulit diprediksi pada *nested layout*. | Hierarkis (*tree-based* via `gtable`), isolasi viewport, *canvas nesting* murni tanpa *side-effects*. |
| **Extensibility** | Membungkus fungsi *wrapper* yang merusak komposabilitas visualisasi. | Menulis subclass `Stat` dan `Geom` modular yang langsung kompatibel dengan operator `+` dan skala native `ggplot2`. |
| **Headless Rendering** | Kerap gagal pada server Linux (CI/CD / Docker) karena ketergantungan pada pustaka X11 GUI. | Bebas dependensi X11 menggunakan software rasterizer modern (`ragg::agg_png`). |
| **Tipografi & I18N** | Masalah font rendering dan *kerning* yang rusak pada platform cross-compilation. | HarfBuzz text shaping dan FreeType rasterizer terintegrasi langsung via library `systemfonts`. |
| **Manajemen Memori** | *Memory leak* saat me-render puluhan ribu plot dalam loop batch akibat penumpukan *graphics device state*. | Alokasi dev eksplisit, deterministik buffer flush, dan destruksi objek kanvas secara terkontrol. |

---

### 5. How (Workflow Detail)

Untuk mengimplementasikan visualisasi enterprise tingkat lanjut, alur kerja rekayasa grafis dibagi menjadi empat fase:

```
[Phase 1: Prototyping Component] 
       |---> Subclass ggproto(Stat)  -> override compute_group()
       |---> Subclass ggproto(Geom)  -> override draw_panel() (Return Grob)
       |---> Wrapper function        -> expose layer API
       |
[Phase 2: Canvas Assembly]
       |---> ggplot_build()         -> Validasi data aesthetics
       |---> ggplot_gtable()        -> Transformasi ke struktur gtable
       |---> grid / gtable editing  -> Injeksi watermark / header dinamis
       |
[Phase 3: Headless Serialization Pipeline]
       |---> Set Device Context     -> ragg::agg_png() / CairoPDF()
       |---> Stream Rendering       -> grid.draw()
       |---> Device Shutdown        -> dev.off() & resource garbage collection
       |
[Phase 4: Artifact Validation]
       |---> Dimension & DPI Audit
       |---> Color Space Conformance Check
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem rendering R seperti sistem teater profesional:

```
               [ SCRIPT & DATA ]
            (Data Frame & Aesthetic)
                       |
                       v
         [ SUTRADARA & PRODUSER ] 
               (ggplot2 Core)
      Mengatur tempo, skala, peran aktor.
                       |
                       v
            [ TIM TATA PANGGUNG ]
             (grid & gtable Engine)
   +---------------------------------------+
   | VIEWPORT (Panggung Utama)             |
   |   +-------------------------------+   |
   |   | VIEWPORT (Kamar Aktor)        |   |
   |   |   [GROB]   [GROB]             |   |
   |   |   (Kursi)  (Lampu)            |   |
   |   +-------------------------------+   |
   +---------------------------------------+
                       |
                       v
          [ TEKNISI KAMERA / REKORDER ]
       (Graphics Device Driver: ragg/Cairo)
                       |
        +--------------+--------------+
        v                             v
  [ Film 35mm (SVG/PDF) ]      [ Foto Digital (PNG) ]
```

- Data adalah **naskah**.
- `ggproto` (`Stat`/`Geom`) adalah **resep pemanggungan**.
- `grid` adalah **struktur fisik panggung (Viewport)** dan **properti panggung (Grob)**.
- *Graphics Device* adalah **kamera sensor** yang mencetak aksi fisik panggung menjadi medium akhir (vektor atau piksel).

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Memahami Low-Level `grid` dan Viewport Hierarkis

Contoh berikut menunjukkan isolasi koordinat dan hierarki rendering murni menggunakan pustaka `grid` tanpa `ggplot2`.

```r
library(grid)

# Bersihkan kanvas grafis aktif
grid.newpage()

# Viewport 1: Container Induk (Margin 10% di sekeliling)
vp_parent <- viewport(
  x = 0.5, y = 0.5, 
  width = 0.8, height = 0.8,
  just = "center",
  name = "vp_parent"
)
pushViewport(vp_parent)

# Gambar border container induk
grid.rect(gp = gpar(col = "#1E293B", lwd = 2, fill = "#F8FAFC"))

# Viewport 2: Kuadran Kiri Bawah (Skala koordinat dinormalisasi 0 - 100)
vp_child <- viewport(
  x = 0.05, y = 0.05,
  width = 0.4, height = 0.4,
  just = c("left", "bottom"),
  xscale = c(0, 100),
  yscale = c(0, 100),
  name = "vp_child"
)
pushViewport(vp_child)

# Render elemen visual di dalam child viewport menggunakan satuan 'native'
grid.rect(gp = gpar(col = "#EF4444", fill = "#FEE2E2", lty = "dashed"))
grid.points(
  x = unit(c(10, 50, 90), "native"),
  y = unit(c(20, 80, 40), "native"),
  pch = 19,
  gp = gpar(col = "#DC2626", cex = 1.5)
)
grid.text(
  label = "Child Native Context",
  x = unit(50, "native"),
  y = unit(90, "native"),
  gp = gpar(fontsize = 10, fontface = "bold", col = "#991B1B")
)

# Navigasi kembali ke root tree
upViewport(2)
```

#### B. Practical Example: Mengembangkan Custom Geom & Stat Menggunakan `ggproto`

Skenario: Membangun visualisasi toleransi metrik produksi (*Confidence Ribbon Envelope*) yang secara otomatis menghitung *moving median* dan rentang interkuartil (IQR), lalu me-render *ribbon* dan garis tengah dalam satu layer modular.

```r
library(ggplot2)
library(grid)

# 1. Definisi Custom Stat: StatMovingIQR
StatMovingIQR <- ggproto("StatMovingIQR", Stat,
  required_aes = c("x", "y"),
  
  setup_params = function(data, params) {
    if (is.null(params$window_size)) {
      params$window_size <- 5
    }
    return(params)
  },
  
  compute_group = function(data, scales, window_size = 5) {
    # Pastikan data terurut berdasarkan X
    data <- data[order(data$x), ]
    n <- nrow(data)
    
    if (n < window_size) {
      stop("Ukuran observasi lebih kecil dari parameter window_size.")
    }
    
    # Pre-alokasi vektor kalkulasi
    y_med <- numeric(n)
    y_lower <- numeric(n)
    y_upper <- numeric(n)
    
    k <- floor(window_size / 2)
    
    for (i in seq_len(n)) {
      idx_min <- max(1, i - k)
      idx_max <- min(n, i + k)
      window_vals <- data$y[idx_min:idx_max]
      
      y_med[i] <- median(window_vals, na.rm = TRUE)
      y_lower[i] <- quantile(window_vals, 0.25, na.rm = TRUE)
      y_upper[i] <- quantile(window_vals, 0.75, na.rm = TRUE)
    }
    
    data.frame(
      x = data$x,
      y = y_med,
      ymin = y_lower,
      ymax = y_upper
    )
  }
)

# 2. Definisi Custom Geom: GeomEnvelope (Komposisi Polygon Grob + Line Grob)
GeomEnvelope <- ggproto("GeomEnvelope", Geom,
  required_aes = c("x", "y", "ymin", "ymax"),
  default_aes = aes(
    colour = "#0F172A",
    fill = "#38BDF8",
    alpha = 0.3,
    linewidth = 1,
    linetype = 1
  ),
  
  draw_group = function(data, panel_params, coord) {
    # Transformasi koordinat data ke physical viewport unit (0 - 1)
    coords_ribbon_upper <- coord$transform(
      data.frame(x = data$x, y = data$ymax), 
      panel_params
    )
    coords_ribbon_lower <- coord$transform(
      data.frame(x = rev(data$x), y = rev(data$ymin)), 
      panel_params
    )
    coords_line <- coord$transform(data, panel_params)
    
    # Polygon Grob untuk pita toleransi (Envelope Ribbon)
    ribbon_grob <- polygonGrob(
      x = c(coords_ribbon_upper$x, coords_ribbon_lower$x),
      y = c(coords_ribbon_upper$y, coords_ribbon_lower$y),
      gp = gpar(
        fill = data$fill[1],
        col = NA,
        alpha = data$alpha[1]
      )
    )
    
    # Polyline Grob untuk central median line
    line_grob <- linesGrob(
      x = coords_line$x,
      y = coords_line$y,
      gp = gpar(
        col = data$colour[1],
        lwd = data$linewidth[1] * .pt,
        lty = data$linetype[1]
      )
    )
    
    # Gabungkan menjadi satu grob tree hierarkis
    grobTree(ribbon_grob, line_grob)
  }
)

# 3. Layer Constructor API
stat_moving_envelope <- function(mapping = NULL, data = NULL, geom = "envelope",
                                 position = "identity", na.rm = FALSE, 
                                 show.legend = NA, inherit.aes = TRUE, 
                                 window_size = 5, ...) {
  layer(
    stat = StatMovingIQR, 
    data = data, 
    mapping = mapping, 
    geom = geom, 
    position = position, 
    show.legend = show.legend, 
    inherit.aes = inherit.aes,
    params = list(window_size = window_size, na.rm = na.rm, ...)
  )
}

# Mapping registrasi geom
geom_envelope <- function(...) {
  # Alias untuk geom pendukung
  GeomEnvelope
}
```

```r
# Testing eksekusi komponen
set.seed(42)
n_points <- 100
test_data <- data.frame(
  timestamp = seq(1, n_points),
  metric = sin(seq(0.1, 10, length.out = n_points)) * 20 + rnorm(n_points, sd = 4)
)

p <- ggplot(test_data, aes(x = timestamp, y = metric)) +
  geom_point(alpha = 0.4, color = "#64748B") +
  stat_moving_envelope(window_size = 9, fill = "#0EA5E9", colour = "#0284C7", linewidth = 1.2) +
  theme_minimal() +
  labs(
    title = "Sistem Telemetri Mesin: Moving IQR Envelope",
    subtitle = "Komputasi native ggproto StatMovingIQR dan GeomEnvelope",
    x = "Waktu Pemantauan (detik)",
    y = "Amplitudo Getaran (mm/s)"
  )

print(p)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Pipeline Headless Multi-Threaded untuk Pelaporan Kepatuhan Portofolio Keuangan
Sebuah institusi finansial global mengelola lebih dari 250.000 portofolio investasi individual. Setiap penutupan kuartal, sistem harus menghasilkan 250.000 dokumen pelaporan visual format PDF/A dan *high-resolution thumbnail* dalam waktu kurang dari 2 jam.

#### Masalah Utama
1. Backend default R (`pdf()` dan `png()`) mengalami kebocoran memori internal jika dipanggil ratusan ribu kali dalam satu proses R.
2. Render grafis berbasis kurva densitas finansial memerlukan *subpixel precision* dan *font embedding* legal (Helvetica Neue LT Pro).
3. Terjadi *resource deadlock* jika R dijalankan bersamaan dengan *web-renderer* seperti Chromium/Puppeteer.

#### Solusi Arsitektur
Menggunakan R murni dengan engine `ragg` dan `Cairo`, diisolasi menggunakan *process-level pool* berbasis `callr` untuk menjamin nol degradasi *garbage collector*, serta integrasi `gtable` untuk menempatkan *security watermark* secara terenkapsulasi.

```r
# Script Pipeline Produksi: engine_report_renderer.R
library(ggplot2)
library(ragg)
library(grid)
library(gtable)

render_portfolio_report <- function(portfolio_id, data_frame, output_filepath) {
  # 1. Pipeline ggplot: Kurva Distribusi Aset & Risiko
  p_base <- ggplot(data_frame, aes(x = returns)) +
    geom_density(fill = "#0284C7", alpha = 0.4, color = "#0369A1", linewidth = 0.8) +
    geom_vline(aes(xintercept = mean(returns)), color = "#DC2626", linetype = "dashed") +
    theme_classic(base_size = 9, base_family = "sans") +
    theme(
      plot.margin = margin(t = 20, r = 20, b = 20, l = 20, unit = "pt"),
      axis.title = element_text(face = "bold")
    ) +
    labs(
      title = paste0("Analisis Risiko Portofolio: Ref #", portfolio_id),
      subtitle = "VaR (95%) vs Distribusi Historis Simulasi Monte Carlo",
      x = "Tingkat Pengembalian Bersih (%)",
      y = "Densitas Probabilitas"
    )
  
  # 2. Modifikasi Layout Rendah: gtable Object Mutator
  gt <- ggplot_gtable(ggplot_build(p_base))
  
  # Inject grob Watermark Kepatuhan Audit Finansial
  watermark_grob <- textGrob(
    label = "CONFIDENTIAL - RESTRICTED FINANCIAL RECORD",
    x = 0.5, y = 0.5,
    rot = 30,
    gp = gpar(col = "#E2E8F0", fontsize = 24, fontface = "bold", alpha = 0.6)
  )
  
  # Letakkan watermark di balik panel utama (panel = index 1 pada viewport grid ggplot)
  panel_idx <- which(gt$layout$name == "panel")
  gt <- gtable_add_grob(
    x = gt, 
    grobs = watermark_grob, 
    t = gt$layout$t[panel_idx], 
    l = gt$layout$l[panel_idx], 
    z = -Inf, # Kirim ke background layer terdalam
    name = "audit_watermark"
  )
  
  # 3. Deterministic High-Throughput Rasterization Backend
  # Menggunakan ragg::agg_png untuk konsistensi cross-platform & memory recycling
  tryCatch({
    agg_png(
      filename = output_filepath,
      width = 2400, 
      height = 1600, 
      res = 300, 
      scaling = 1.2
    )
    
    grid.draw(gt)
  }, finally {
    # Wajib menjamin penutupan device bahkan jika terjadi runtime error
    if (dev.cur() > 1) {
      dev.off()
    }
  })
  
  return(file.exists(output_filepath))
}

# Simulasi Eksekusi Pipeline Produksi
df_monte_carlo <- data.frame(returns = rnorm(50000, mean = 7.5, sd = 3.2))
temp_output <- tempfile(fileext = ".png")

success <- render_portfolio_report(
  portfolio_id = "PF-990812-X",
  data_frame = df_monte_carlo,
  output_filepath = temp_output
)

cat(sprintf("Proses render selesai. Status: %s. Output path: %s\n", success, temp_output))
```

---

### 9. Trade-offs: Analisis Komparasi Arsitektur Visualisasi

```
          Skalabilitas & Throughput
                    ▲
                    │        [ragg AGG Direct Buffer]
                    │        (Sangat Cepat, Raster Saja)
                    │
                    │                  [Cairo PDF/SVG]
                    │                  (Vektor, Render Lambat)
                    │
                    │   [Standard ggplot2 (dev.print)]
                    │   (Beban overhead tinggi)
                    │
  ──────────────────┼────────────────────────────────► Fleksibilitas Desain
                    │                                 & Interaktivitas
                    │
                    │       [Plotly / HTMLWidgets]
                    │       (Interaktif, DOM Berat,
                    │        Bukan untuk Batch 100K+)
```

| Parameter | Base R Graphics | ggplot2 + Standard Device (`png`/`pdf`) | Modern Pipeline (`ggproto` + `ragg`) | Interactive DOM (`htmlwidgets`/`plotly`) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (plot/sec)** | ~120 - 150 plot/s | ~15 - 25 plot/s | ~80 - 110 plot/s | ~2 - 5 plot/s (Headless Browser) |
| **Latency Per Frame** | < 10 ms | ~40 - 65 ms | ~10 - 15 ms | > 200 ms |
| **Footprint Memori** | Rendah (~10 MB) | Sedang (~50 MB) | Sangat Rendah & Terprediksi | Ekstrem Tinggi (> 250 MB per proses Chromium) |
| **Dukungan Tipografi** | Sangat Terbatas | Tergantung OS Window Manager | Native cross-platform via FreeType | Mengikuti CSS Engine |
| **Skalabilitas Batch** | Tinggi, rentan *state pollution* | Rentan bocor memori | Sangat Tinggi (Aman untuk paralelisme worker) | Tidak layak untuk jutaan PDF |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: Penumpukan Device State Mengakibatkan Memory Leaks
* **Gejala**: RAM server membengkak secara eksponensial saat merender ribuan plot berulang kali hingga R dihentikan oleh OS (OOM Killer).
* **Penyebab**: Penggunaan `dev.off()` tanpa blok pengaman `tryCatch` atau `on.exit()`. Jika plotting gagal di tengah jalan, device tetap menggantung dan mengunci memory buffer C.
* **Solusi**:
```r
safe_render <- function(plot_obj, path) {
  ragg::agg_png(path, width = 1200, height = 800)
  on.exit(if (dev.cur() > 1) dev.off(), add = TRUE)
  grid.draw(plot_obj)
}
```

#### 2. Masalah: Garis Tumpang Tindih (Overplotting) Menghancurkan Kinerja Vektor (PDF)
* **Gejala**: Dokumen PDF hasil export berukuran ratusan megabyte dan membuat browser atau aplikasi pembaca PDF macet total saat rendering.
* **Penyebab**: Mengekspor *scatterplot* dengan 500.000 titik sebagai PDF vektor murni. Setiap titik menjadi instruksi grafis individual di dalam PDF tree.
* **Solusi**: Terapkan hybrid rendering. Gunakan rasterisasi parsial pada elemen data densitas tinggi via paket `ggrastr`:
```r
# Gunakan ggrastr untuk merender titik sebagai layer bitmap di dalam kanvas vektor PDF
# p + ggrastr::rasterise(geom_point(alpha = 0.1), dpi = 300)
```

#### 3. Masalah: Text Clipping pada Margin Luar Plot
* **Gejala**: Label kustom yang diinjeksi via `grid` terpotong sebagian di ujung kanvas.
* **Penyebab**: Viewport `ggplot2` panel memiliki flag `clip = "on"` secara default.
* **Solusi**: Ubah flag clipping pada `gtable` target:
```r
gt$layout$clip[gt$layout$name == "panel"] <- "off"
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Backend Isolation**: Larang pemanggilan default `png()`, `jpeg()`, atau `pdf()`. Wajibkan `ragg::agg_png()` untuk raster atau `Cairo::CairoPDF()` untuk vektor.
2. [ ] **No Side-Effects Execution**: Fungsi perakitan visualisasi harus murni fungsional: menerima data frame/parameter, mengembalikan objek `gTree` atau file path secara atomik.
3. [ ] **Font Determinism**: Deklarasikan *font face* secara eksplisit menggunakan `systemfonts::register_font()` agar hasil render Linux CI/CD identik dengan lokal macOS/Windows.
4. [ ] **Dynamic Sizing**: Hindari nilai absolut satuan piksel tanpa skala base DPI. Gunakan unit absolut tipografi (`points`, `cm`, `inches`) untuk layout publikasi.
5. [ ] **Defensive Device Handling**: Wajib membungkus *lifecycle* graphics device dalam handler `on.exit(dev.off(), add = TRUE)`.
6. [ ] **Garbage Collector Tuning**: Pada loop batch raksasa, jalankan pembersihan memori periodik secara programatik:
```r
if (i %% 500 == 0) gc(verbose = FALSE, full = TRUE)
```

---

### 12. Hands-on Practice

Buat seluruh file berikut pada struktur direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Direktori & Konfigurasi Pipeline
Simpan kode berikut sebagai `hands-on/m02/01_pipeline_setup.R`:

```r
# hands-on/m02/01_pipeline_setup.R
dir.create("hands-on/m02/output", recursive = TRUE, showWarnings = FALSE)

suppressPackageStartupMessages({
  library(ggplot2)
  library(grid)
  library(gtable)
  library(ragg)
})

cat("[INFO] Environment setup completed successfully.\n")
```

#### Langkah 2: Konstruksi Custom Geom Crosshair Analytics
Simpan kode berikut sebagai `hands-on/m02/02_custom_geom.R`:

```r
# hands-on/m02/02_custom_geom.R
library(ggplot2)
library(grid)

# GeomCrosshair: Menandai ambang batas kritis (X dan Y intercept) dengan styling khusus
GeomCrosshair <- ggproto("GeomCrosshair", Geom,
  required_aes = c("xintercept", "yintercept"),
  default_aes = aes(
    colour = "#DC2626",
    linewidth = 0.5,
    linetype = "dashed",
    alpha = 0.8
  ),
  
  draw_panel = function(data, panel_params, coord) {
    # Transformasi nilai skala intercept ke sistem koordinat kanvas
    ranges <- coord$backtransform_range(panel_params)
    
    # Siapkan data segmentasi
    x_lines <- data.frame(
      x = data$xintercept,
      xend = data$xintercept,
      y = rep(ranges$y[1], nrow(data)),
      yend = rep(ranges$y[2], nrow(data)),
      alpha = data$alpha,
      colour = data$colour,
      linewidth = data$linewidth,
      linetype = data$linetype
    )
    
    y_lines <- data.frame(
      x = rep(ranges$x[1], nrow(data)),
      xend = rep(ranges$x[2], nrow(data)),
      y = data$yintercept,
      yend = data$yintercept,
      alpha = data$alpha,
      colour = data$colour,
      linewidth = data$linewidth,
      linetype = data$linetype
    )
    
    segments_data <- rbind(x_lines, y_lines)
    trans_segments <- coord$transform(segments_data, panel_params)
    
    segmentsGrob(
      x0 = unit(trans_segments$x, "native"),
      y0 = unit(trans_segments$y, "native"),
      x1 = unit(trans_segments$xend, "native"),
      y1 = unit(trans_segments$yend, "native"),
      gp = gpar(
        col = trans_segments$colour,
        lwd = trans_segments$linewidth * .pt,
        lty = trans_segments$linetype,
        alpha = trans_segments$alpha
      )
    )
  }
)

geom_crosshair <- function(mapping = NULL, data = NULL, stat = "identity",
                           position = "identity", ..., na.rm = FALSE,
                           show.legend = NA, inherit.aes = FALSE) {
  layer(
    geom = GeomCrosshair, mapping = mapping, data = data, stat = stat,
    position = position, show.legend = show.legend, inherit.aes = inherit.aes,
    params = list(na.rm = na.rm, ...)
  )
}
```

#### Langkah 3: Eksekusi Batch Rendering Engine Berperforma Tinggi
Simpan kode berikut sebagai `hands-on/m02/03_batch_render.R`:

```r
# hands-on/m02/03_batch_render.R
source("hands-on/m02/02_custom_geom.R")

generate_telemetry_batch <- function(total_reports = 10) {
  cat(sprintf("[INIT] Memulai batch rendering %d visualisasi...\n", total_reports))
  
  for (id in seq_len(total_reports)) {
    # Sintesis beban data operasional
    sensor_df <- data.frame(
      rpm = rnorm(1000, mean = 5000, sd = 400),
      temp = rnorm(1000, mean = 90, sd = 12)
    )
    
    threshold_df <- data.frame(xintercept = 5800, yintercept = 110)
    
    p <- ggplot(sensor_df, aes(x = rpm, y = temp)) +
      geom_point(alpha = 0.2, color = "#475569") +
      geom_crosshair(data = threshold_df, aes(xintercept = xintercept, yintercept = yintercept),
                     colour = "#B91C1C", linewidth = 0.8) +
      theme_bw(base_size = 10) +
      labs(
        title = sprintf("Sensor Monitoring Node #%03d", id),
        x = "Engine RPM",
        y = "Coolant Temperature (C)"
      )
    
    out_file <- file.path("hands-on/m02/output", sprintf("telemetry_%03d.png", id))
    
    # Eksekusi engine ragg berkecepatan tinggi
    ragg::agg_png(out_file, width = 1200, height = 900, res = 150)
    print(p)
    dev.off()
    
    if (id %% 5 == 0) cat(sprintf("[PROGRESS] Rendered %d/%d reports.\n", id, total_reports))
  }
  cat("[COMPLETED] Batch rendering selesai. Cek direktori: hands-on/m02/output/\n")
}

generate_telemetry_batch(10)
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `01_pipeline_setup.R` untuk memverifikasi ketersediaan font keluarga sistem menggunakan pustaka `systemfonts`. Buat logika pengondisian yang secara dinamis memilih font default `"Arial"` jika font perusahaan `"Helvetica Neue"` tidak terdaftar di OS server.

#### Level Medium
Buat sebuah subclass `Stat` bernama `StatOutlierLabel` yang menerima argumen data variabel continu $Y$. Hitung nilai *fences* Tukey:
$$Q_1 - 1.5 \times \text{IQR} \quad \text{dan} \quad Q_3 + 1.5 \times \text{IQR}$$
Outputkan hanya baris-baris data yang diklasifikasikan sebagai outlier untuk langsung dipetakan ke `geom_text()`.

#### Level Hard
Bangun layout dashboard analitik menggunakan `gtable` secara murni (tanpa bantuan library `patchwork` atau `cowplot`). Gabungkan:
- 1 Heatmap berkorelasi besar (kiri).
- 2 Plot distribusi marjinal (atas dan kanan heatmap).
- 1 Kolom keterangan metadata yang disisipkan di sisi paling kanan dengan lebar fixed `4 cm`.
Pastikan seluruh sumbu (*axis panels*) sejajar secara matematis (*aligned viewports*).

---

### 14. Challenge

**Skenario**: Sistem *fraud-detection* streaming transaksi membutuhkan pembuatan komposit audit visual setiap kali anomali terdeteksi. Dalam hitungan puncak, terdapat lonjakan 100 deteksi anomali per detik.

**Tugas Arsitektur**:
Rancang dan implementasikan modul R *production-grade* yang:
1. Memproses payload data transaksi (*micro-batch*) dan menghasilkan grafik pelaporan *multi-panel* secara atomik.
2. Memiliki batas waktu eksekusi ketat (*latency deadline*) maksimal **15 milidetik** per render plot.
3. Menjamin konsumsi memori *flat* (tidak ada *leakage*) setelah pengujian ketahanan me-render 50.000 grafik beruntun.
4. Menghasilkan visualisasi dengan watermark SHA-256 hash transaksi yang tertanam langsung pada layer primitif kanvas untuk menjamin *anti-tampering*.

*Catatan: Kerjakan tanpa menggunakan libraries wrapper eksternal tingkat tinggi (`cowplot`, `ggpubr`, dsb). Solusi harus berbasis native `grid`, `ggproto`, dan `ragg`.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pemahaman Konseptual (Basic)
1. Apa peran arsitektur fundamental dari pustaka `grid` dalam ekosistem grafis R?
2. Mengapa modifikasi parameter global menggunakan `par()` tidak bekerja pada objek `ggplot2`?
3. Sebutkan perbedaan siklus hidup komputasi antara metode `compute_group` dan `compute_panel` pada objek `ggproto(Stat)`!
4. Apa fungsi dari primitif unit `unit(x, "native")` pada manipulasi kanvas `grid`?
5. Mengapa format representasi `gtable` dibutuhkan sebelum suatu plot dirender ke sebuah *device*?

#### Bagian B: Analisis & Optimasi (Intermediate)
6. Jelaskan mengapa backend `ragg::agg_png` memiliki throughput rendering raster yang jauh melampaui default backend `grDevices::png` pada platform Linux!
7. Kapan sebuah elemen visual wajib didelegasikan ke `draw_group` alih-alih `draw_panel` di dalam implementasi kustom `Geom`?
8. Bagaimana strategi Anda mencegah *vector inflation problem* saat mengekspor visualisasi berisi jutaan titik observasi ke dalam format PDF?
9. Bagaimana cara kerja hierarki *clipping* pada sistem viewport `grid` dan apa dampaknya jika parameter `clip = "on"` diaktifkan pada layer text anotasi?
10. Mengapa pemanggilan `ggplot_build()` diperlukan sebelum kita membedah dan memanipulasi koordinat fisik dari objek `ggplot`?

#### Bagian C: Kasus Masalah Produksi (Production Scenarios)
11. **Skenario 1**: Sebuah microservice berbasis Docker R me-render visualisasi dengan backend `pdf()`. Pada mesin lokal pengembang (macOS), tipografi teks bahasa Mandarin ter-render dengan sempurna. Namun, saat dideploy ke Kubernetes cluster (Alpine/Debian), karakter tersebut berubah menjadi kotak kosong (tofu characters). Di mana akar masalahnya dan bagaimana arsitektur font rendering yang benar untuk mengatasinya?
12. **Skenario 2**: Script batch reporting menghasilkan error `Error in dev.off() : cannot shut down device 1 (the null device)`. Analisis apa yang memicu kondisi ini dalam arsitektur multithread/paralel dan bagaimana rancangan blok eksekusi yang *fault-tolerant*!
13. **Skenario 3**: Sebuah proses pemantauan real-time mengalami degradasi kecepatan sistemik: render ke-1 membutuhkan waktu 12 ms, namun setelah berjalan 6 jam, render ke-10.000 membutuhkan waktu 450 ms per plot meski volume baris data yang diproses konstan. Di manakah titik kebocoran performa tipikal pada skenario rendering R ini?

---

### 16. Summary

Visualisasi data enterprise di R melampaui sekadar eksplorasi interaktif dengan `ggplot()`. Keandalan sistem di level industri mensyaratkan penguasaan fondasi grafis:

- Sistem objek `ggproto` memisahkan transformasi analitik (`Stat`) dari komputasi geometri rendering (`Geom`).
- Subsystem `grid` memegang kontrol mutlak atas hierarki kanvas, *viewport*, dan objek layout (`gtable`).
- Backend modern (`ragg`, `Cairo`) menghilangkan ketergantungan pada server GUI X11, menyediakan subpixel anti-aliasing presisi, dan menjaga stabilitas alokasi memori.
- Disiplin rekayasa perangkat lunak—seperti penanganan device deterministik via `on.exit()`, tipografi native cross-platform, dan teknik rasterisasi selektif—merupakan fondasi wajib dalam membangun microservice grafis berskala enterprise.