# BAB-05: Exploratory Data Analysis & Advanced Visualization
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Membedah dan mengoptimalkan pipeline grafis internal R (*The Graphics Engine Pipeline*), mulai dari abstraksi `ggplot2` hingga manipulasi tingkat rendah `grid` (*Graphic Objects/grobs* dan *Viewports*).
- Merancang dan mengimplementasikan arsitektur visualisasi data skala *enterprise* yang mampu memproses ratusan juta observasi tanpa degradasi memori melalui teknik hibrida *raster-vector* dan *data aggregation downsampling*.
- Membangun pipeline *automated headless reporting* berkecepatan tinggi menggunakan *device drivers* modern (`ragg`, `Cairo`) yang terintegrasi dalam sistem kontainerisasi mikroservis.
- Mengidentifikasi, mengisolasi, dan merekayasa ulang *bottleneck* performa visualisasi (I/O, *memory allocation*, *device rasterization*, dan *overplotting*).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **R Dasar & Lanjutan**: Pemahaman mendalam tentang R environment, non-standard evaluation (NSE) via `rlang`, S3/vctrs object system, dan manipulasi memori (*copy-on-modify semantics*).
- **Manipulasi Data Skala Besar**: Operasi mutasi, agregasi, dan pengindeksan menggunakan `data.table` atau `collapse`.
- **Dasar `ggplot2`**: Pemahaman konseptual tentang *Grammar of Graphics* (data, aesthetic mappings, layers, scales, coordinates, facets).
- **Sistem Operasi & Grafis Komputasi**: Konsep dasar *rasterization*, *vector graphics* (PDF/SVG), *colour spaces* (sRGB, Display P3), font rendering engines (FreeType, HarfBuzz), serta manajemen memori sistem UNIX/Linux (POSIX signals, headless display virtual servers seperti Xvfb).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Grafik Mesin R: Dari Layer Deklaratif ke Framebuffer
Sistem visualisasi data di R terdiri dari beberapa lapisan abstraksi hierarkis:

```
+------------------------------------------------------------------+
|                   User Layer (Declarative API)                   |
|                        ggplot2 / patchwork                       |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|               Data Transformation & Aesthetics Mapping            |
|                  Stat Layer, Scales, Coordinates                 |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|                 Low-Level Layout Engine (grid)                   |
|           gTree, grob (Graphic Object), Viewport Tree            |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|               C-Level Graphics Engine (GE / engine.c)            |
|                Display List Management, Clipping                 |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|                     Graphic Device Drivers                       |
|         ragg (AGG) | Cairo (cairo-pdf/png) | Native (png/pdf)     |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
|              Output (File / Framebuffer / Display)               |
+------------------------------------------------------------------+
```

1. **User Layer (`ggplot2`)**:
   Pengguna mendeklarasikan mapping data ke estetika grafis. Pada tahap ini, tidak ada piksel atau garis geometris yang digambar. Objek `ggplot` sebenarnya adalah `list` bertipe S3 yang menyimpan referensi data, mapping ekspresi, layer prototipe, dan skala logis.

2. **Data Transformation & Plot Building (`ggplot_build`)**:
   Fungsi internal `ggplot_build(p)` mengonversi objek deklaratif menjadi representasi data mentah yang siap digambar:
   - Data dipisah berdasarkan facet (panel).
   - `Stat` menghitung data turunan (misal: frekuensi histogram, *kernel density estimation*, garis regresi).
   - Skala memetakan nilai data ke skala estetik seragam (misal: domain kontinu diubah ke interval [0, 1] atau palet hex warna).

3. **Grob & Viewport Assembly (`ggplot_gtable`)**:
   Fungsi `ggplot_gtable()` mengambil data dari tahap build dan mengonversinya menjadi objek `gtable`. Di sinilah abstraksi `ggplot2` bertransformasi murni menjadi primitif `grid`:
   - **`grob` (Graphic Object)**: Komponen individual seperti garis (`linesGrob`), poligon (`polygonGrob`), atau teks (`textGrob`).
   - **`gTree` (Graphic Tree)**: Koleksi hierarkis dari grob yang dapat dimanipulasi secara rekursif.
   - **`Viewport`**: Wilayah gambar persegi panjang lokal yang menetapkan sistem koordinat koordinat independen, clipping rules, dan orientasi spasial.

4. **C-Level Graphics Engine (`GE`) & Display List**:
   Struktur data C internal R menerima print request dari `grid`. Jika display list aktif, R menyimpan setiap instruksi primitif dalam alokasi memori internal untuk memungkinkan *resizing* dinamis pada interactive window. Pada skenario batch/headless, display list sebaiknya dinonaktifkan (`record = FALSE`) untuk mencegah kebocoran memori (*memory leak*).

5. **Graphic Device Drivers**:
   Driver perangkat grafis bertanggung jawab merender primitif C menjadi representasi raster (piksel) atau vektor (instruksi matematika):
   - **Native X11 / Windows GDI**: Performa lambat, rendering teks buruk, font rendering bergantung sistem operasi lokal.
   - **Cairo (`CairoPNG`, `cairo_pdf`)**: Mendukung antialiasing vektor kualitas tinggi, penanganan *alpha-blending* transparan, dan font embedding berbasis Fontconfig.
   - **Modern AGG (`ragg::agg_png`)**: Menggunakan *Anti-Grain Geometry engine* berbasis C++. Menghilangkan dependensi sistem X11, menghasilkan *anti-aliasing sub-pixel*, eksekusi lebih cepat (30-50% lebih cepat dibanding Cairo), serta memanfaatkan *HarfBuzz* dan *FreeType* secara portabel lintas OS.

---

### 4. Why & What

| Dimensi | Pendekatan Skrip Analisis Kasual | Pendekatan Rekayasa Sistem Produksi Skala Enterprise |
| :--- | :--- | :--- |
| **Render Engine** | Native Device (`png()`, `pdf()`, RStudio IDE default). | High-Performance Offscreen AGG (`ragg::agg_png()`) / Headless Cairo. |
| **Volume Data** | Sample data kecil ($N < 100.000$), langsung di-plot ke memori. | Multi-million row data points; menerapkan *Hexagonal Binning*, *Raster Decimation*, atau *Data Pre-Aggregation*. |
| **Pipeline State** | State visualisasi terikat global environment; manipulasi manual. | Pipeline fungsional, terisolasi, *idempotent*, deterministik, dan terintegrasi dengan CI/CD/Job Orchestrator. |
| **Format Output** | Hardcoded SVG / PDF statis resolusi tunggal. | Multi-tier format: Kompresi Lossless Raster untuk preview, WebP/SVG teroptimasi untuk UI, Vector PDF/X-1a untuk print industri. |
| **Manajemen Memori** | R session dibiarkan memegang objek besar pasca plotting. | Garbage collection eksplisit, pelepasan buffer native device, isolasi worker subprocess melalui worker pooling. |

#### Mengapa Perlu Arsitektur Visualisasi Khusus?
Pada sistem skala enterprise (seperti *automated quantitative reporting* di perbankan atau dashboard telemetri armada sensor IoT), merender ratusan ribu data points menggunakan vector rendering (PDF/SVG standar) akan menghasilkan file berukuran gigabyte yang memicu *browser crash* atau *out-of-memory* (OOM) pada printer driver. Diperlukan arsitektur pipeline terstruktur yang memahami kapan harus melakukan agregasi statistik murni, kapan mengimplementasikan *rasterization* pada koordinat viewport, dan bagaimana mengeksekusi paralelisasi rendering tanpa tabrakan file descriptor.

---

### 5. How (Workflow Detail)

Alur kerja arsitektur sistem visualisasi skala produksi dirancang melalui pipeline berikut:

```
[In-Memory Engine (data.table / Arrow)]
                 │
                 ▼
[Data Abstraction Layer: Adaptive Binning / Density Profiling]
                 │
                 ▼
[Graphic Construction: ggplot2 Layout Specification]
                 │
                 ▼
[Grob Manipulation: Injeksi Metadata, Watermarking, Styling via grid]
                 │
                 ▼
[Headless Graphic Driver: ragg Engine / In-Memory Raw Buffer]
                 │
                 ▼
[Artifact Delivery: High-Speed I/O, S3 Bucket Storage, Zero-Copy Socket]
```

1. **Data Ingestion & In-Memory Preprocessing**: Data diekstrak via Apache Arrow atau `data.table`. Validasi integritas skema data dijalankan menggunakan assertions ketat (`stopifnot` atau package `checkmate`).
2. **Adaptive Decimation**: Apabila dataset melebihi batas render visual manusia (resolusi layar umumnya tidak mampu menampilkan lebih dari $1920 \times 1080 \approx 2 \times 10^6$ piksel secara diskret), terapkan algoritma aggregasi spasial (misal: *Hexagonal 2D Binning* atau agregasi interval berbasis kuantil).
3. **Graph Grammar Construction**: Instansiasi spesifikasi layer menggunakan fungsi murni (pure functions). Hilangkan referensi ke global environment.
4. **Grob Interception & Grid Modification**: Buka representasi gtable plot, modifikasi elemen marginal/viewports secara programatis (misal: menambahkan dynamic micro-branding, audit-trail UUID, atau sistem baseline custom) langsung pada objek representasi C-level sebelum render.
5. **Offscreen Headless Device Rendering**: Mengalokasikan target buffer menggunakan `ragg::agg_png` atau `ragg::agg_tiff`. Pastikan device selalu ditutup via mekanisme fail-safe (`on.exit(dev.off())`).
6. **Delivery & Buffer Clean-Up**: Verifikasi keberadaan file artefak, periksa byte-size, dan panggil `base::gc()` jika memori internal R menahan display list sisa.

---

### 6. Analogy & Diagram ASCII

Bayangkan proses visualisasi data sebagai proses **Pencetakan Buku Arsitektur Klasik**:

```
+--------------------------------------------------------------------------+
| Data Source (Bahan Baku): Jutaan batu bata, semen, dan data material.   |
+--------------------------------------------------------------------------+
                                    │
                                    ▼
+--------------------------------------------------------------------------+
| ggplot2 (Arsitek): Membuat cetak biru (Blueprint). Tidak ada batu fisik. |
| Menyatakan: "Dinding A butuh tinggi 10 meter, dicat merah".               |
+--------------------------------------------------------------------------+
                                    │
                                    ▼
+--------------------------------------------------------------------------+
| grid (Mandor Konstruksi / Layout Manager): Mengatur grid, menghitung     |
| proporsi ruangan (Viewport), dan menaruh kotak-kotak komponen (grobs).   |
+--------------------------------------------------------------------------+
                                    │
                                    ▼
+--------------------------------------------------------------------------+
| Graphic Engine & ragg (Pabrik Percetakan / Mesin Offset Modern):         |
| Mengubah blueprint logis menjadi semprotan tinta mikroskopis berkecepatan|
| tinggi langsung ke lembaran kertas (Piksel/Raster Buffer).                |
+--------------------------------------------------------------------------+
```

Jika Anda meminta mencetak satu juta batu bata individual dalam bentuk miniatur 3D (rendering vektor untuk $10^6$ observasi), mesin percetakan akan meledak kehabisan kertas dan tinta. Pendekatan arsitektur yang benar adalah mencetak **gambar tekstur dinding batu bata** (raster aggregation) yang terlihat identik di mata manusia dengan biaya dan konsumsi sumber daya yang jauh lebih efisien.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Intercepting & Manipulating the Grid Tree
Contoh dasar bagaimana memanipulasi *grob* internal dari objek `ggplot2` sebelum mencapai output stream:

```r
library(ggplot2)
library(grid)

# 1. Definisi Plot Sederhana
p <- ggplot(mtcars, aes(x = wt, y = mpg)) +
  geom_point(color = "steelblue") +
  theme_minimal()

# 2. Bangun Representasi gtable (Grob Table)
gt <- ggplotGtable(p)

# 3. Inspeksi struktur Layout
# gt$layout mendefinisikan posisi visual: t (top), l (left), b (bottom), r (right)
panel_idx <- which(gt$layout$name == "panel")

# 4. Injeksi Grob Baru Tingkat Rendah (Watermark di belakang data)
watermark <- textGrob(
  label = "CONFIDENTIAL",
  x = 0.5, y = 0.5,
  gp = gpar(fontsize = 40, col = rgb(0.8, 0.8, 0.8, 0.4), fontface = "bold")
)

# Menambahkan grob kustom tepat di layer panel
gt <- gtable::gtable_add_grob(
  gt, 
  watermark, 
  t = gt$layout$t[panel_idx], 
  l = gt$layout$l[panel_idx], 
  name = "confidential_watermark"
)

# 5. Render ke Null Device untuk Validasi, lalu cetak
grid.newpage()
grid.draw(gt)
```

#### B. Practical Example: Industrial-Grade High-Throughput Plot Generation Engine
Implementasi fungsi produksi yang aman, menangani edge cases, menggunakan engine grafis AGG, dan zero-leak file handling:

```r
library(ggplot2)
library(ragg)
library(checkmate)

render_enterprise_timeseries <- function(data, 
                                         x_col, 
                                         y_col, 
                                         output_file, 
                                         width_px = 1920, 
                                         height_px = 1080, 
                                         dpi = 300) {
  # 1. Validasi Input Defensif
  assert_data_frame(data, min.rows = 2)
  assert_string(x_col)
  assert_string(y_col)
  assert_names(names(data), must.include = c(x_col, y_col))
  assert_path_for_output(output_file, overwrite = TRUE)
  assert_int(width_px, lower = 100)
  assert_int(height_px, lower = 100)
  assert_int(dpi, lower = 72, upper = 600)

  # 2. Plotting Menggunakan Tidy Evaluation (rlang)
  p <- ggplot(data, aes(x = .data[[x_col]], y = .data[[y_col]])) +
    geom_line(color = "#1D4ED8", linewidth = 0.75, alpha = 0.9) +
    theme_light(base_size = 11) +
    theme(
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "#CBD5E1", fill = NA, linewidth = 0.5),
      axis.title = element_text(face = "bold", color = "#0F172A"),
      axis.text = element_text(color = "#475569")
    ) +
    labs(
      x = toupper(x_col),
      y = toupper(y_col),
      title = "Automated Telemetry Diagnostic Output",
      subtitle = sprintf("Generated on: %s | Host: %s", Sys.time(), Sys.info()[["nodename"]])
    )

  # 3. Setup Graphics Device Driver dengan Fail-Safe Cleanup
  # Menggunakan ragg untuk kecepatan eksekusi dan font rendering independen sistem
  dev_opened <- FALSE
  tryCatch(
    expr = {
      ragg::agg_png(
        filename = output_file,
        width = width_px,
        height = height_px,
        res = dpi,
        scaling = 1.0,
        background = "white"
      )
      dev_opened <- TRUE

      # Konversi dan draw
      print(p)
      
      message(sprintf("[SUCCESS] Rendered graphic successfully to %s", output_file))
    },
    error = function(err) {
      stop(sprintf("[ENGINE_ERROR] Gagal merender grafik: %s", err$message))
    },
    finally = {
      # Memastikan device slot C graphics SELALU ditutup untuk mencegah memory leak
      if (dev_opened) {
        dev.off()
      }
    }
  )

  return(invisible(output_file))
}

# Contoh Pemanggilan Operasional:
sample_data <- data.frame(
  timestamp = seq(as.POSIXct("2026-01-01"), by = "hour", length.out = 1000),
  metric = cumsum(rnorm(1000, mean = 0.05, sd = 1))
)

temp_output <- tempfile(fileext = ".png")
render_enterprise_timeseries(
  data = sample_data, 
  x_col = "timestamp", 
  y_col = "metric", 
  output_file = temp_output
)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sebuah platform *High-Frequency Algorithmic Trading* (HF-Trading) menghasilkan 15 juta catatan metrik latensi dan slippage order per hari per market pair. Tim kepatuhan dan risiko membutuhkan laporan visual inter-day komprehensif beresolusi tinggi setiap pukul 00:00 UTC untuk 120 aset finansial.

#### Permasalahan Utama
1. Menghasilkan plot scatter konvensional dari 15 juta titik menggunakan library standar membutuhkan alokasi RAM hingga 32 GB per sesi, memicu *Linux Out-Of-Memory (OOM) Killer*.
2. Format vektor (PDF/SVG) menghasilkan dokumen berukuran ~1.2 GB per aset, membuat aplikasi PDF Viewer institusional hang.
3. Total waktu pembuatan laporan dengan serial processing adalah ~8 jam, melewati *SLA Window* kepatuhan (maksimum 45 menit).

#### Solusi Arsitektural Terintegrasi
Menggabungkan agregasi visual native fast-binning (`scattermore` / `hexbin`), manipulasi gtable custom untuk watermarking compliance, dan multi-threading execution via `callr` + `furrr` di atas engine rendering `ragg`.

```r
library(data.table)
library(ggplot2)
library(scattermore)
library(furrr)
library(ragg)

# 1. Pipeline Generator Per-Asset (Fully Encapsulated Pure Function)
generate_compliance_asset_plot <- function(asset_id, raw_csv_path, output_dir) {
  dest_file <- file.path(output_dir, sprintf("COMPLIANCE_%s_%s.png", asset_id, Sys.Date()))
  
  # A. Zero-Copy / Fast Memory Ingestion menggunakan data.table
  # Hanya memuat kolom yang dianalisis
  dt <- fread(
    raw_csv_path, 
    select = c("order_timestamp", "latency_micros", "slippage_bps"),
    showProgress = FALSE
  )
  
  # Validasi batas anomali (Threshold Risk Rules)
  dt[, is_breach := (slippage_bps > 50 | latency_micros > 10000)]
  
  # B. Pembangunan Visualisasi Skala Jutaan Baris dengan Engine Scattermore (Fast C-Rasterization)
  p <- ggplot(dt, aes(x = latency_micros, y = slippage_bps)) +
    geom_scattermore(
      aes(color = is_breach),
      pointsize = 2,
      pixels = c(1200, 800), # Virtual resolution buffer
      alpha = 0.4
    ) +
    scale_color_manual(
      values = c("FALSE" = "#0EA5E9", "TRUE" = "#EF4444"),
      labels = c("Normal", "SLA Breach")
    ) +
    scale_x_log10(labels = scales::label_comma()) +
    theme_bw(base_size = 9) +
    labs(
      title = sprintf("Asset Telemetry Profile: %s", asset_id),
      subtitle = sprintf("Evaluated Points: %s rows | Compliance SLA Gatekeeper", format(nrow(dt), big.mark = ",")),
      x = "Execution Latency (Microseconds, Log Scale)",
      y = "Slippage (Basis Points)"
    ) +
    theme(
      legend.position = "bottom",
      plot.title = element_text(face = "bold")
    )
  
  # C. Offscreen Safe Rendering via agg_png
  agg_png(
    filename = dest_file,
    width = 2400,
    height = 1600,
    res = 300
  )
  on.exit(dev.off(), add = TRUE)
  
  print(p)
  
  return(dest_file)
}

# 2. Worker Parallel Orchestration Setup
execute_parallel_reporting <- function(asset_manifest, num_workers = 4) {
  plan(multisession, workers = num_workers)
  
  message(sprintf("Starting batch compliance render across %d workers...", num_workers))
  
  results <- future_map(
    .x = asset_manifest$asset_id,
    .f = function(id) {
      csv_path <- asset_manifest[asset_id == id, path]
      generate_compliance_asset_plot(id, csv_path, tempdir())
    },
    .options = furrr_options(seed = TRUE)
  )
  
  # Reset parallel plan ke sequential
  plan(sequential)
  return(unlist(results))
}
```

#### Hasil Metrik Arsitektur:
- **Pengurangan Ukuran File**: Dari file PDF 1.2 GB per dokumen menjadi 380 KB PNG terkompresi lossless resolusi tinggi (300 DPI, tajam untuk dicetak).
- **Pengurangan Memory Footprint**: Dari 32 GB RAM turun menjadi 650 MB RAM per worker process melalui rendering langsung titik-titik ke offscreen C array via `scattermore`.
- **Waktu Eksekusi**: Waktu eksekusi untuk 120 aset turun dari 8 jam menjadi 11 menit menggunakan 8 parallel workers.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

Ketika merancang arsitektur visualisasi data analitik, seorang lead engineer harus mempertimbangkan trade-off berikut:

| Pilihan Arsitektur | Keunggulan Utama | Konsekuensi Negatif / Biaya |
| :--- | :--- | :--- |
| **Vector-based (PDF / SVG)** | Resolusi independen (*infinite zoom*), standar emas untuk dokumen percetakan regulasi. | Ukuran file linear $O(N)$ terhadap jumlah data points. Crash pada sistem klien jika $N > 100.000$. |
| **Direct Rasterization (`scattermore` / AGG)** | Ukuran file konstan $O(1)$ terhadap $N$ data points. Kecepatan render sangat cepat. | Penurunan ketajaman jika diperbesar (*pixelated*). Kehilangan kemampuan seleksi teks/elemen secara terpisah di file output. |
| **Server-side Headless Pre-rendering** | Klien menerima file statis ringan (PNG/WebP). Beban CPU/GPU browser klien mendekati nol. | Beban komputasi terpusat pada server farm. Membutuhkan kapasitas CPU dan manajemen task queue yang solid. |
| **Interactive Client-side Render (HTMLWidgets / Plotly)** | Interaktivitas penuh (*tooltip, panning, zooming*) langsung di browser pengguna. | Mengirimkan data JSON mentah ke browser. Rentan memory leak pada DOM, potensi kebocoran data sensitif (*data leak*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: Linux Headless Server Error (`cannot open display / X11 connection rejected`)
- **Penyebab**: Perangkat default sistem Linux memanggil sub-sistem X11 saat menggunakan `png()` atau `pdf()`. Ketika dijalankan dalam kontainer Docker atau worker tanpa display monitor fisik, C runtime gagal mengalokasikan context.
- **Troubleshooting & Fix**:
  Jangan gunakan native X11 engine. Gunakan package `ragg` yang beroperasi sepenuhnya pada C++ software rasterizer tanpa butuh display server:
  ```r
  # BAD: Membutuhkan X11 context pada beberapa OS Linux
  png("output.png")
  plot(1:10)
  dev.off()

  # GOOD: 100% headless, tidak butuh dependensi OS GUI
  ragg::agg_png("output.png")
  plot(1:10)
  dev.off()
  ```

#### 2. Masalah: Zombie Graphics Devices & Resource Leak
- **Penyebab**: Terjadi crash/error saat eksekusi plot setelah `png()` atau `pdf()` dibuka, menyebabkan `dev.off()` terlewati. Slot device grafis R (maksimal 64 device simultan) habis.
- **Troubleshooting & Fix**:
  Gunakan blok `on.exit(..., add = TRUE)` segera setelah membuka device untuk memastikan penutupan resource stream secara deterministik:
  ```r
  render_safe <- function(file, expr) {
    ragg::agg_png(file)
    dev_num <- dev.cur()
    on.exit({
      if (dev_num %in% dev.list()) dev.off(dev_num)
    }, add = TRUE)
    
    force(expr)
  }
  ```

#### 3. Masalah: Text Clipping dan Boundary Overflow pada Facet Label Panjang
- **Penyebab**: Algoritma layout `grid` secara ketat memotong elemen jika melebihi ukuran bounding box viewport yang ditentukan.
- **Troubleshooting & Fix**:
  Matikan clipping flag secara eksplisit pada panel layout gtable atau manfaatkan parameter helper `coord_cartesian(clip = "off")` serta konfigurasi margin `theme(plot.margin = margin(...))`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `ragg` Engine**: Ganti semua pemanggilan visualisasi batch ke `ragg::agg_png` untuk konsistensi font lintas OS dan performa rasterisasi optimal.
- [ ] **Hindari Overplotting Vektor**: Jangan pernah mengeksekusi `geom_point()` murni pada dataset dengan $N > 100.000$. Selalu gunakan `geom_hex()`, `geom_bin2d()`, atau `geom_scattermore()`.
- [ ] **Explicit Variable Mapping**: Hindari penggunaan variabel lingkungan global di dalam estetika `aes(x = GlobalVar)`. Selalu lekatkan data ke dataframe input dan gunakan `.data[[var_name]]` atau tidy evaluation syntax (`{{ var }}`).
- [ ] **Lock Dependencies dan Font Binaries**: Pastikan environment produksi memiliki paket font yang terinstal eksplisit (misal: DejaVu Sans, Roboto) dan didaftarkan melalui `systemfonts::register_font()`. Hindari mengandalkan font sistem bawaan.
- [ ] **Automated Memory Cleanup**: Panggil `dev.off()` dalam blok proteksi `tryCatch`/`on.exit()`. Eksekusi `invisible(gc())` jika merender batch besar dalam single long-running worker.
- [ ] **Pemberian Identitas Grafis Unik**: Sematkan ID build atau hash SHA dari data mentah pada caption/footer visualisasi produksi untuk auditabilitas (*data provenance*).

---

### 12. Hands-on Practice

Buatlah direktori latihan dengan struktur berikut pada terminal Anda:
```bash
mkdir -p hands-on/m02/scripts
mkdir -p hands-on/m02/output
cd hands-on/m02
```

Simpan kode pipeline produksi berikut ke dalam file `scripts/eda_pipeline.R`:

```r
# hands-on/m02/scripts/eda_pipeline.R
# Enterprise Automated Diagnostics Generator

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(ragg)
  library(grid)
  library(gtable)
})

cat("[1/4] Generating synthetic telemetry dataset (500,000 observations)...\n")
set.seed(42)
N <- 500000
telemetry_data <- data.table(
  sensor_id = sample(sprintf("SENSOR-%03d", 1:10), N, replace = TRUE),
  signal_noise_ratio = rnorm(N, mean = 25, sd = 5),
  vibration_amplitude = rgamma(N, shape = 2, scale = 1.5),
  status = sample(c("Nominal", "Degraded", "Critical"), N, replace = TRUE, prob = c(0.85, 0.12, 0.03))
)

cat("[2/4] Constructing composite production plot...\n")
# Kita merender distribusi 2D menggunakan hexagonal binning untuk mencegah vector bloat
p <- ggplot(telemetry_data, aes(x = signal_noise_ratio, y = vibration_amplitude)) +
  geom_hex(bins = 60) +
  scale_fill_viridis_c(option = "inferno", trans = "log10", name = "Density (Log10)") +
  facet_wrap(~ status, ncol = 3) +
  theme_minimal(base_size = 12) +
  theme(
    strip.background = element_rect(fill = "#E2E8F0", color = NA),
    strip.text = element_text(face = "bold", color = "#1E293B"),
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    plot.title = element_text(face = "bold", size = 14)
  ) +
  labs(
    title = "Sensor Diagnostic Telemetry Distribution Profile",
    subtitle = sprintf("Batch Run ID: %s | Records Processed: %d", uuid::UUIDgenerate(), nrow(telemetry_data)),
    x = "Signal-to-Noise Ratio (dB)",
    y = "Vibration Amplitude (mm/s)",
    caption = "Enterprise Asset Integrity Management System"
  )

cat("[3/4] Modifying lower-level grobs for corporate watermarking...\n")
gt <- ggplotGtable(p)

# Injeksi banner status resmi di layout paling atas
banner_grob <- rectGrob(
  gp = gpar(fill = "#1E293B", col = NA)
)
banner_text <- textGrob(
  "INTERNAL USE ONLY - TELEMETRY COMPLIANCE AUDIT",
  gp = gpar(col = "white", fontsize = 8, fontface = "bold")
)
banner_tree <- grobTree(banner_grob, banner_text)

# Tambahkan satu baris di bagian atas gtable
gt <- gtable_add_rows(gt, heights = unit(0.5, "cm"), pos = 0)
gt <- gtable_add_grob(gt, banner_tree, t = 1, l = 1, r = ncol(gt))

cat("[4/4] Rendering to disk using headless ragg engine...\n")
output_target <- "output/sensor_diagnostic_report.png"

agg_png(
  filename = output_target,
  width = 2800,
  height = 1400,
  res = 300,
  scaling = 1.1
)
grid.draw(gt)
dev.off()

cat(sprintf("[FINISHED] Report successfully compiled to %s (Size: %0.2f KB)\n", 
            output_target, file.info(output_target)$size / 1024))
```

Jalankan script dari direktori `hands-on/m02`:
```bash
Rscript scripts/eda_pipeline.R
```

---

### 13. Exercise

#### Level Easy
Buat sebuah fungsi mandiri `render_safe_scatter(df, x_var, y_var, output_path)` yang menerima data frame sembarang, mevalidasi bahwa kedua variabel bertipe numerik, dan menyimpannya ke file PNG menggunakan `ragg::agg_png` dengan resolusi 150 DPI. Pastikan fungsi mengembalikan `TRUE` jika berhasil dan mengimplementasikan `on.exit(dev.off())`.

#### Level Medium
Ambil plot time-series multivariat dari dataset `airquality`. Konversi plot tersebut menjadi objek `gtable`. Temukan posisi panel *Ozone* dan panel *Temp*, lalu menggunakan package `grid`, tambahkan garis horizontal merah tebal (spesifikasi: intercept $Y = 100$ untuk Ozone, dan $Y = 80$ untuk Temp) secara manual langsung pada level `grob`, bukan melalui `geom_hline()` ggplot2.

#### Level Hard
Rancang modul visualisasi parallel micro-batching. Modul harus:
1. Menerima data frame 5 juta baris berisi koordinat geospasial lintang/bujur dan metrik anomali.
2. Memecah data berdasarkan ID regional (10 region).
3. Menggunakan `furrr` dengan 4 workers untuk merender 10 peta density rasterisasi terpisah secara bersamaan ke disk.
4. Memonitor dan membatasi konsumsi memori maksimum per worker agar tidak melebihi alokasi 500 MB RAM per proses.

---

### 14. Challenge

**Skenario Sistem Telemetri Skala Exabyte:**
Sebuah konsorsium energi memiliki 5.000 turbin angin yang mengirimkan sinyal getaran berfrekuensi 100 Hz. Setiap hari, tercipta 432 juta metrik time-series per turbin. Anda diminta merancang **Core Engine Visualisasi Monitoring Anomali** yang diintegrasikan ke dalam backend pipeline kontainerisasi Docker.

**Persyaratan Tantangan:**
1. Engine harus menerima stream data atau chunk berbasis file Apache Parquet.
2. Dilarang keras melakukan full in-memory vector plot (menghindari OOM). Implementasikan algoritma *Min-Max LTTB (Largest Triangle Three Buckets)* atau *hexagonal aggregation* pada streaming chunks sebelum masuk ke ggplot graphics pipeline.
3. Output grafis harus berformat SVG interaktif ringan ($< 150 \text{ KB}$ per turbin) ATAU ultra-high resolution WebP/PNG dengan skala dinamis yang siap dikonsumsi oleh aplikasi front-end React.
4. Bangun wrapper fungsional yang tahan terhadap interupsi POSIX, thread-safe, dan memiliki *zero OS dependency footprint* (tidak boleh bergantung pada pustaka X11, Pango, atau cairo sistem host).
5. Tuliskan arsitektur teknis, diagram aliran data komponen, dan implementasi prototipe R yang memenuhi SLA render $< 1.5$ detik per grafik per turbin.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa fungsi `print(p)` atau `grid.draw(p)` harus dipanggil secara eksplisit ketika merender objek ggplot di dalam fungsi R atau perulangan (loop)?
2. Apa perbedaan fungsional utama antara objek `grob` dan objek `viewport` dalam hierarki package `grid`?
3. Mengapa grafik format PDF berbasis vektor yang berisi 1.000.000 titik scatter plot dianggap sebagai antipattern performa arsitektur?
4. Manakah graphics device driver yang direkomendasikan untuk eksekusi headless production modern di R: `png()`, `CairoPNG()`, atau `ragg::agg_png()`? Sebutkan alasan utamanya.
5. Apa konsekuensi fatal jika Anda lupa memanggil `dev.off()` setelah membuka graphical device di lingkungan production task worker?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja fungsi `ggplotGtable()` dan pada fase apa dari pipeline grafis manipulasi layout kustom dapat diinjeksikan?
7. Mengapa display list management pada core R graphics engine dapat memicu *memory leak* pada server batch generating, dan bagaimana cara mematikan fungsi tersebut?
8. Bagaimana package `scattermore` atau `scatterD3` mampu merender jutaan data points secara dramatis lebih cepat dibanding layer `geom_point()` standar?
9. Jelaskan perbedaan mendasar antara representasi ukuran layout menggunakan unit absolut (`unit(2, "cm")`) dan unit relatif (`unit(1, "null")`) pada objek `gtable`.
10. Bagaimana Anda mencegah evaluasi prematur atau kegagalan scoping lingkungan ketika memetakan nama kolom string dinamis ke dalam parameter `aes()` pada pipeline fungsional visualisasi?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah cron job R yang merender 10.000 PDF visualisasi harian mengalami error `all devices are in use` setelah 64 iterasi pertama, kemudian job berhenti. Komponen arsitektur apa yang rusak dan bagaimana Anda merekayasa perbaikannya secara permanen?
12. **Skenario 2**: Sistem container Docker berbasis Alpine Linux yang mengeksekusi pipeline visualisasi R gagal merender teks non-ASCII (karakter kanji dan aksen latin) dan font tampak rusak (tofu / kotak-kotak). Jelaskan *root cause* dari sisi engine font dan bagaimana cara mengonfigurasinya dengan benar.
13. **Skenario 3**: Sebuah REST API berbasis plumber melayani visualisasi chart dynamically-generated on-demand. Saat menerima 200 concurrent requests, konsumsi CPU melonjak 100% dan API mengalami crash karena out-of-memory. Bagaimana Anda mendesain ulang arsitektur rendering visualisasi API tersebut?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1. Objek `ggplot` adalah deklarasi struktur data (S3 object). Operasi rendering visual sebenarnya hanya terjadi ketika metode `print()` atau `plot()` dipanggil, yang secara internal memicu `ggplot_build()` dan `grid.draw()`. Di luar global REPL console (seperti di dalam lingkup fungsi atau loop), auto-printing dinonaktifkan oleh R interpreter.
2. `grob` (Graphic Object) merepresentasikan elemen grafis primitif yang digambar (garis, titik, poligon, teks), sedangkan `viewport` merepresentasikan wilayah atau sistem koordinat (ruang spasial) tempat grob diletakkan dan dipotong (clipped).
3. Format vektor menyimpan setiap titik sebagai instruksi koordinat matematis dan XML/drawing tags tersendiri. Pada 1 juta titik, ukuran file membengkak hingga ratusan megabyte, membebani memori CPU/GPU saat proses dekode di penampil dokumen (PDF viewer/browser), dan menyebabkan aplikasi klien hang atau crash.
4. `ragg::agg_png()`. Alasan: Menggunakan Anti-Grain Geometry engine berbasis C++ yang sepenuhnya software-based (tidak butuh X11 server), rendering tipografi superior via FreeType/HarfBuzz, dan memiliki performa sekitar 30-50% lebih cepat dibanding native maupun Cairo devices.
5. Slot graphics device pada R process akan tetap terbuka dan terkunci (maksimal limit default adalah 64 devices). Jika limit tercapai, R tidak akan bisa membuka device grafis baru dan melempar *fatal error*, serta dapat menahan buffer memori yang memicu akumulasi *memory leak*.

#### Jawaban Intermediate
6. `ggplotGtable()` mengonversi representasi visual plot yang sudah dibersihkan (`ggplot_build`) menjadi kisi tabel grafis (`gtable`) yang berisi koleksi grob dan viewport. Injeksi layout kustom (seperti memodifikasi header, menambah baris, atau menyisipkan elemen di latar belakang) dilakukan setelah `ggplotGtable()` dieksekusi dan sebelum `grid.draw()` dipanggil.
7. R Graphics Engine mempertahankan salinan instruksi grafis di memori internal agar dapat menggambar ulang jika window diubah ukurannya (*resizing*). Pada batch server tanpa display, riwayat ini tidak diperlukan dan terus membesar. Kita dapat menonaktifkan pencatatan ini atau menggunakan headless engine yang mengabaikan display list recording (`record = FALSE`).
8. `scattermore` mengabaikan sistem pembuatan grob individual R. Ia menggunakan kernel C/C++ internal untuk langsung melakukan software rasterization dari data mentah langsung ke memory bitmap array (piksel), kemudian mentransfer hasil akhir bitmap tersebut sebagai satu gambar raster tunggal ke R viewport.
9. `unit(x, "cm")` adalah dimensi fisik mutlak yang nilainya tidak akan berubah berapapun ukuran total grafik. Sebaliknya, `unit(x, "null")` adalah dimensi fleksibel relatif (mirip prinsip CSS flexbox) yang akan mengisi proporsi sisa ruang kanvas yang belum dipakai oleh unit absolut.
10. Menggunakan mekanisme Tidy Evaluation modern: memetakan string variabel dengan `.data[[var_name]]` di dalam `aes()` atau menggunakan inject operator `{{ var }}` jika parameter dilewatkan sebagai ekspresi quosure simbolik, serta mengandalkan library `rlang`.

#### Jawaban Skenario Kasus Produksi
11. **Analisis Skenario 1**: Error `all devices are in use` terjadi karena perulangan tidak menutup device yang telah dialokasikan (melewati batas 64 device). Perbaikan: Pindahkan pembukaan dan penutupan device ke dalam fungsi terisolasi dengan menggunakan pola `dev_id <- dev.cur(); on.exit(dev.off(dev_id), add = TRUE)`. Pastikan penutupan terjadi bahkan jika proses pembuatan plot di tengah iterasi mengalami runtime exception.
12. **Analisis Skenario 2**: Distribusi Linux minimalis seperti Alpine tidak menyediakan meta-package font default maupun font fallback cache. Engine HarfBuzz/FreeType yang digunakan driver tidak menemukan pemetaan glyph font yang sesuai. Solusi: Pasang paket sistem seperti `font-noto` atau `msttcorefonts-installer`, daftarkan font TTF secara eksplisit menggunakan `systemfonts::register_font()`, dan tentukan font family name tersebut secara presisi pada konfigurasi theme ggplot (`base_family = "Noto Sans"`).
13. **Analisis Skenario 3**: Melakukan *on-the-fly computational rendering* untuk 200 parallel concurrent request langsung di web application process R (Plumber adalah single-threaded by default) akan menghabiskan memori dan memblokir event loop. Desain ulang arsitektur:
    - Pisahkan proses komputasi visualisasi dari API thread menggunakan async worker queue (misal: Redis + Celery/LiteQueue/RSysQ).
    - Terapkan mekanisme caching: Jika parameter query identik, kembalikan static pre-rendered image dari reverse proxy (Nginx) atau CDN/S3 bucket.
    - Turunkan ukuran data mentah menggunakan edge pre-aggregation (misal: agregasi SQL/DuckDB terlebih dahulu) sebelum menyerahkan array koordinat akhir ke R plotting function.

---

### 16. Summary

Mengembangkan sistem visualisasi analitik skala enterprise pada bahasa pemrograman R menuntut pemahaman arsitektur yang melampaui antarmuka deklaratif dasar `ggplot2`. Fondasi performa tinggi bertumpu pada kemampuan mengontrol hierarki layout tingkat rendah pada `grid` engine (`grobs`, `gTree`, dan `viewports`), serta memilih perangkat grafis offscreen modern berbasis C/C++ seperti `ragg` yang memotong ketergantungan rapuh terhadap environment X11 lokal.

Pada dataset bervolume raksasa, efisiensi sistem tidak dicapai dengan memaksakan rendering vektor mentah titik demi titik, melainkan dengan merancang pipeline adaptif: data dipadatkan melalui algoritma decimation, adaptive binning, atau rasterisasi in-memory sebelum diubah menjadi objek visual. Dengan menerapkan defensive programming, isolasi proses paralel, sanitasi resource device grafis via safe cleanup pattern, dan audit metadata logging, sistem visualisasi R mampu bertransformasi menjadi infrastruktur pelaporan enterprise yang deterministik, skalabel, dan tangguh terhadap beban analitik ekstrem.