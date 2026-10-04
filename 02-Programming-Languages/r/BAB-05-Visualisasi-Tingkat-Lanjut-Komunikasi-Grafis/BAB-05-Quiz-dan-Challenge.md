# BAB 05: Quiz, Challenge, & Knowledge Check
**Visualisasi Tingkat Lanjut & Komunikasi Grafis (ggplot2)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Formalisasi Grammar of Graphics vs Pendekatan Imperatif
Jelaskan perbedaan mendasar secara arsitektural antara paradigma *Grammar of Graphics* (Leland Wilkinson) yang diadopsi oleh `ggplot2` dengan model plotting imperatif pada *base R graphics* (`plot()`, `lines()`, `points()`). Fokuskan analisis Anda pada representasi objek grafis di memori, pemisahan representasi data (*aesthetic mappings*) dari rendering primitif visual, serta implikasi decoupling ini terhadap komposisi visual modular.

### Soal 1.2: Mekanisme Tidy Evaluation dalam Konstruksi Estetika (`aes`)
`ggplot2` mengandalkan *Non-Standard Evaluation* (NSE) dan *Tidy Evaluation* (`rlang`) di balik layer `aes()`. Jelaskan siklus hidup pemrosesan ekspresi di dalam `aes()`:
1. Kapan ekspresi kolom data dievaluasi (*quosure capture* vs *evaluation phase*)?
2. Mengapa pendekatan lawas `aes_string()` didepresiasi?
3. Bagaimana mekanisme injeksi dinamis variabel programatik menggunakan operator *embrace* (`{{ var }}`) atau `.data[[var_name]]` bekerja tanpa memicu *namespace collision*?

### Soal 1.3: Resolusi Graf Eksekusi: `stat_*` vs `geom_*` dan Variabel Terkomputasi
Setiap layer dalam `ggplot2` mengombinasikan komponen geometris (`geom`) dan transformasi statistik (`stat`). 
Jelaskan urutan operasi internal (*pipeline execution order*) saat pemanggilan `geom_histogram()` atau `geom_density()`. Bagaimana mekanisme `after_stat()` (dan sintaks terdepresiasi `..density..` / `stat(density)`) menunda evaluasi *aesthetic mapping* hingga tahap transformasi statistik selesai sebelum diteruskan ke *scale transformation* dan *coordinate rendering*?

### Soal 1.4: Semantik Pemotongan Data: Scale Limits vs Coordinate Limits
Terdapat perbedaan kritis antara:
```r
p + scale_x_continuous(limits = c(lower, upper))
```
dan
```r
p + coord_cartesian(xlim = c(lower, upper))
```
Jelaskan dampak internal kedua pendekatan tersebut terhadap:
1. *Subsetting* baris data (*data pruning* vs *visual zooming*).
2. Perhitungan statistik pada layer turunan (misalnya garis regresi `geom_smooth()` atau estimasi densitas `geom_density()`).
3. Pembuatan *bounding box* dan artefak visual pada batas axis (*axis clipping*).

### Soal 1.5: Arsitektur Pemetaan Dua Arah pada Sistem `scale_*`
Fungsi `scale_*` tidak sekadar memformat label sumbu, melainkan mengontrol pemetaan formal dari *Domain Data* ke *Range Estetika* (warna, ukuran, posisi, bentuk). 
Jelaskan bagaimana sistem skala `ggplot2` membedakan penanganan:
1. Skala kontinu vs skala diskret (termasuk transformasi non-linear seperti `log10` atau `sqrt`).
2. Titik waktu (*timing*) eksekusi transformasi skala: apakah transformasi terjadi sebelum atau sesudah kalkulasi `stat`? Berikan contoh kasus pada `geom_boxplot()` yang membuktikan urutan tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Translasi Internal: Dari Objek `ggplot` ke Pohon `gtable` dan `grid grobs`
Objek bertipe `ggplot` adalah deklarasi deklaratif, bukan bitmap atau vektor instan. Jelaskan tahapan translasi yang terjadi saat fungsi `print.ggplot()` atau `ggplotGrob()` dieksekusi:
1. Peran `ggplot_build()` dalam memvalidasi data, mengeksekusi `Stat`, dan melatih `Scale`.
2. Peran `ggplot_gtable()` dalam mengubah representasi data menjadi *graphical objects* (`grobs`) yang dikemas dalam *grid layout* (`gtable`).
3. Bagaimana sistem *viewports* pada paket `grid` mengisolasi sistem koordinat lokal antar panel, strip facet, dan margin legenda?

### Soal 2.2: Bottleneck Rendering Objek Vektor Skala Masif
Saat merender dataset dengan $N = 5.000.000$ baris menggunakan `geom_point()`, sistem sering kali mengalami *crash* akibat OOM (*Out Of Memory*) atau menghasilkan file PDF berukuran ratusan megabita yang tidak dapat dibuka di pembaca dokumen standar.
1. Analisis mengapa format vektor (PDF/SVG) mengalami kegagalan skalabilitas linear terhadap jumlah observasi primitif geometris.
2. Bandingkan strategi mitigasi performa tinggi berikut dari segi integritas representasi data dan latensi pemrosesan:
   - Penggunaan engine grafis rasterisasi hybrid (misalnya paket `scattermore` atau `ggrastr`).
   - Transformasi agregasi spasial *in-memory* (`geom_hex()`, `geom_bin2d()`).
   - Server-side pre-rasterization via *Datashader-like pipelines*.

### Soal 2.3: Arsitektur Ekstensibilitas `ggproto`
`ggplot2` mengimplementasikan sistem *Object-Oriented* tersendiri bernama `ggproto` (berbasis prototipe/delegasi, mirip JavaScript) dan menolak sistem S3/S4 standar R untuk komponen internalnya.
1. Mengapa Hadley Wickham mendesain `ggproto` khusus untuk layer `ggplot2` alih-alih menggunakan S3 atau R6?
2. Jika Anda membuat *custom Stat* (`StatCustom`), jelaskan perbedaan tanggung jawab fungsional antara metode `compute_group()`, `compute_panel()`, dan `compute_layer()`. Kapan Anda wajib meng-override salah satu dari metode tersebut?

### Soal 2.4: Penyelarasan Layout Kompleks (*Panel Alignment*) pada Objek Multi-Plot
Menggabungkan beberapa plot terpisah menggunakan `gridExtra::grid.arrange()` sering kali menghasilkan sumbu koordinat horizontal ($x$-axis) yang tidak sejajar secara vertikal jika panjang karakter label sumbu vertikal ($y$-axis) pada masing-masing plot berbeda.
1. Mengapa fenomena *misalignment* ini terjadi pada tingkat layout `gtable`?
2. Bagaimana paket modern seperti `patchwork` atau `cowplot::align_plots()` menyelesaikan masalah ini secara komputasi? Jelaskan manipulasi matriks lebar kolom (`widths`) pada objek `gtable` yang dilakukan untuk menjamin *pixel-perfect alignment*.

### Soal 2.5: Typography Rendering Pipeline & Font Metric Collisions
Saat menyusun visualisasi untuk media cetak/korporat dengan font kustom (misal: TTF/OTF internal institusi):
1. Mengapa pemanggilan `theme(text = element_text(family = "CustomFont"))` sering kali gagal me-render tipografi yang benar saat disimpan via `ggsave("plot.png", type = "cairo")` di lingkungan Linux headless (CI/CD server)?
2. Jelaskan perbedaan cara kerja internal antara graphic device standar R, `cairo_pdf()`, dan engine berbasis modern C++ `ragg` (`ragg::agg_png()`) dalam membaca metrik font (*glyph shaping*, *kerning*, *fallback fonts*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Engine Otomasi Pelaporan Skala Besar
Sebuah institusi kliring perbankan memiliki sistem otomatisasi berbasis batch R yang menghasilkan 15.000 laporan PDF performa portofolio harian untuk klien institusional. Setiap PDF memuat 6 plot tren volatilitas multi-tahun (masing-masing $\approx 250.000$ titik data transaksi frekuensi tinggi). 
- **Kondisi Eksisting:** Batch job berjalan selama 6,5 jam pada node server 64-core 256GB RAM, sering kali mati mendadak karena *memory fragmentation*, dan ukuran rata-rata 1 file PDF mencapai 85 MB.
- **Investigasi Awal:** Developer menggunakan `geom_line()` standar, font eksternal via paket `showtext`, rendering default `pdf()`, dan facetting `facet_wrap(~portfolio_id)`.
- **Pertanyaan Diagnostik:**
  1. Identifikasi 3 bottleneck struktural terparah pada arsitektur pipeline visualisasi di atas.
  2. Rancang ulang arsitektur rendering pipeline tersebut (meliputi manipulasi data pra-visualisasi, pemilihan graphic device, teknik rasterisasi selektif, dan isolasi memori proses worker R) agar waktu eksekusi total terpangkas menjadi $< 45$ menit dengan ukuran file PDF $< 3$ MB per laporan tanpa kehilangan keterbacaan data tren ekstrem (*spikes/anomalies*).

### Skenario B: Audit Integritas Data & Visual Bias pada Tim Kepatuhan Finansial
Tim Audit Kepatuhan menemukan anomali pada visualisasi pelaporan batas risiko kredit (*Credit Value at Risk*). Analis sebelumnya membuat plot agregasi menggunakan kode berikut:

```r
ggplot(risk_data, aes(x = branch_id, y = var_exposure)) +
  geom_bar(stat = "summary", fun = "mean", fill = "steelblue") +
  stat_summary(fun.data = "mean_se", geom = "errorbar", width = 0.2) +
  scale_y_continuous(limits = c(0, 1000000))
```

- **Insiden:** Terjadi *under-reporting* risiko eksposur sistemik sebesar ratusan juta dolar. Beberapa cabang dengan lonjakan risiko bernilai di atas $1.000.000$ ternyata diabaikan dari perhitungan rata-rata cabang tanpa memunculkan error atau warning pada log eksekusi otomatis.
- **Pertanyaan Diagnostik:**
  1. Analisis mekanisme internal `ggplot2` yang menyebabkan data ekstrem di atas $1.000.000$ tereliminasi secara diam-diam (*silent data loss*) sebelum `stat_summary()` menghitung metrik rata-rata dan *error bar*.
  2. Tunjukkan perbaikan kode yang tepat untuk menampilkan batas visual $0$ hingga $1.000.000$ pada layar tanpa mengorbankan integritas kalkulasi statistik seluruh baris observasi.
  3. Jelaskan mengapa pemilihan visualisasi menggunakan *bar chart* untuk nilai agregasi eksposur risiko (dikenal sebagai anti-pattern *"Dynamite Plot"*) secara fundamental menyembunyikan risiko ekor tebal (*fat-tailed distribution*), dan berikan rekomendasi representasi visual alternatif yang secara ketat mempertahankan visualisasi variabilitas, densitas distribusi, dan *extreme outliers*.

### Skenario C: Arsitektur Microservice Rendering Headless Berbasis Docker
Anda ditugaskan merancang *microservice* API R (`Plumber`) yang dideploy di atas Kubernetes cluster berbasis Linux Alpine/Debian minimal. API ini menerima payload JSON (berisi metrik streaming data operasional), mengonstruksinya menjadi visualisasi interaktif-statis berkualitas cetak, dan mengembalikan Base64-encoded string PNG ke gateway web frontend dalam latensi target $< 300\text{ ms}$.
- **Hambatan Teknis:** 
  - Tidak ada sistem windowing X11 (*headless container*).
  - Tuntutan konkurensi tinggi ($100\text{ RPS}$).
  - *Engine* rendering grafis R bawaan tidak bersifat thread-safe dan memicu *segmentation faults* jika terjadi race condition akses driver OS.
- **Pertanyaan Diagnostik:**
  1. Mengapa driver grafis default `grDevices::png()` gagal beroperasi pada arsitektur kontainer minimalis headless, dan apa konsekuensinya terhadap ketergantungan paket sistem OS (seperti `libpng`, `cairo`, `pango`, `freetype2`)?
  2. Evaluasi arsitektur rendering menggunakan `ragg::agg_png()` vs `Cairo::CairoPNG()` untuk deployment microservice ini. Mana yang memiliki keunggulan deterministik dalam isolasi memori, performa rendering *multithreaded/stateless*, dan dependensi sistem?
  3. Rancang strategi manajemen memori dan lifecycle process di R (misalnya: penggunaan worker pool via `callr` atau `mirai`) untuk mencegah *memory leaks* akumulatif yang diakibatkan oleh kompilasi objek `gtable` berulang dalam satu instance R runtime.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Multi-Asset Volatility Monitor Engine

#### Problem Statement
Sebuah *quantitative trading desk* membutuhkan sistem visualisasi *post-trade analysis* otomatis. Sistem harus memproses $1.000.000$ baris data tick pasar (multi-asset: FX, Crypto, Equities, Commodities) dan menghasilkan visualisasi diagnostik multi-panel terkalibrasi tinggi dalam format PNG dan PDF. Visualisasi harus menyandingkan pergerakan harga, estimasi volatilitas lokal (bukan parametrik kaku), visualisasi volume trading termampatkan, serta indikasi visual anomali per jam tanpa mengalami *visual distortion*, *silent data dropping*, atau pembengkakan memori.

#### Architectural & Technical Requirements
1. **Pipa Data & Tidy Evaluation:**
   - Bangun fungsi kustom dengan signature:
     `generate_market_diagnostics(data, asset_sym, x_time, y_price, y_volume, filter_quantile = 0.99)`
   - Implementasikan *Tidy Evaluation* penuh (`enquo`, `{{ }}`, `.data`) sehingga fungsi dapat menerima nama kolom unquoted secara fleksibel dan aman dari *environment leaking*.
2. **Kalkulasi & Layering Tingkat Lanjut:**
   - **Panel 1 (Main Price & Regime):** Render pergerakan harga. Terapkan smoothing volatilitas non-parametrik (misal: LOESS atau restricted cubic spline) menggunakan `geom_smooth()` atau custom stat. 
   - Tambahkan *highlighting* anomali otomatis menggunakan titik merah (`geom_point`) yang dievaluasi *in-place* menggunakan `after_stat()` atau kalkulasi dinamis untuk titik-titik yang deviasinya melampaui $3\sigma$ dari rolling baseline.
   - **Panel 2 (High-Density Volume Profile):** Visualisasikan volume tick. Karena kepadatan titik data ($N$ besar), gunakan teknik visualisasi anti-overplotting (misal: `geom_bin2d` atau kombinasi `geom_segment` dengan alpha presisi dan blending mode).
3. **Komposisi Multi-Plot & Strict Alignment:**
   - Gabungkan Panel 1 dan Panel 2 secara vertikal dengan rasio perbandingan $70:30$.
   - Terapkan library `patchwork` atau perakitan manipulasi `gtable` langsung. Seluruh sumbu horizontal ($X$-axis, time dimension) harus terkunci sejajar secara mutlak (*pixel-perfect vertical alignment*), terlepas dari jumlah digit/format angka pada label sumbu vertikal ($Y$-axis).
4. **Non-destructive Coordinate Clipping:**
   - Terapkan batasan visual horizontal dan vertikal dinamis berdasarkan parameter `filter_quantile` tanpa menghapus baris data di luar batas (menjaga kalkulasi model smoothing di Panel 1 tetap valid hingga ke batas terluar visualisasi).
5. **Production Theming & Headless Typography:**
   - Rancang tema khusus berbasis korporat (`theme_market_dark()` atau `theme_market_light()`) menggunakan `theme()` yang memodifikasi minimal 15 parameter visual (margin, panel borders, grid line major/minor hierarchy, strip facets, axis ticks, typography sizing menggunakan metrik `pt`).
   - Ekspor grafik menggunakan graphic device `ragg::agg_png` dengan resolusi $300\text{ DPI}$, ukuran dimensi yang presisi ($3000 \times 2000$ piksel), dan pastikan font non-sistemik dimuat tanpa crash.

#### Constraints
- Waktu eksekusi total untuk $1.000.000$ baris data (dari data frame mentah hingga file PNG tersimpan di disk) harus diselesaikan di bawah **8 detik** pada mesin standar (4 core, 8GB RAM).
- Penggunaan memori puncak (*peak RAM usage*) tidak boleh melampaui **1.5 GB**.
- Dilarang keras menggunakan *base R plots* di dalam pipeline; seluruh visualisasi harus berakar dari paradigma objek `ggplot2` / `grid`.

#### Expected Output
1. Satu skrip R fungsional dan modular (`market_viz_engine.R`) yang berisi:
   - Generator data sintetis realistis ($1.000.000$ baris) menggunakan `tibble` (memuat `timestamp`, `asset_id`, `price` dengan random walk, dan `volume` dengan right-skewed lognormal distribution).
   - Implementasi fungsi `generate_market_diagnostics()`.
   - Implementasi *custom theme*.
   - Benchmark profiling performa eksekusi menggunakan paket `tictoc` atau `bench::mark()`.
2. Output gambar resolusi tinggi (`diagnostics_output.png`) yang menampilkan *dual-panel aligned dashboard* yang tajam, bebas dari distorsi pelabelan, dan terhindar dari *visual clipping*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup rendering `ggplot2`: Data $\rightarrow$ Aesthetic Mapping $\rightarrow$ Stat Transformation $\rightarrow$ Scale Training/Mapping $\rightarrow$ Coordinate Transformation $\rightarrow$ Facet Layout $\rightarrow$ Grob Generation via `grid`.
- [ ] Perbedaan formal antara *data pruning* pada `scale_*_continuous(limits = ...)` dengan *visual zooming* pada `coord_cartesian(xlim = ..., ylim = ...)`.
- [ ] Mekanisme kerja internal `after_stat()` dan `after_scale()` dalam menunda evaluasi variabel estetika.
- [ ] Arsitektur hirarki `grid`: Objek `grob`, `gList`, `gTree`, dan manipulasi sel matriks `gtable`.
- [ ] Keunggulan dan batas arsitektural sistem OO `ggproto` dibandingkan model S3/S4/R6.
- [ ] Konsekuensi komputasi dan perbedaan representasi antara vektor primitif (PDF/SVG) vs rasterisasi diskret (AGG/Cairo/PNG) pada rendering dataset densitas ultra-tinggi.
- [ ] Cara kerja manipulasi ruang lingkup ekspresi (*tidy evaluation*, quosures, data masking) dalam fungsi yang membungkus layer-layer `ggplot2`.

### Saya tidak perlu menghafal:
- [ ] Nama-nama argumen warna heksadesimal spesifik atau palet bawaan R (cukup pahami penggunaan abstraksi `scale_color_*` dan manipulasi color space).
- [ ] Kode numerik untuk simbol plotting `pch` atau tipe garis `lty` (gunakan referensi visual saat dibutuhkan).
- [ ] Seluruh parameter konfigurasi mikro dari `theme()` (terdapat $>90$ argumen; cukup pahami hierarki inheritance: `line`, `rect`, `text`, `title`, dan cara kerja inheritance inheritance `element_blank()` / `element_grob()`).
- [ ] Rincian implementasi C internal library FreeType atau HarfBuzz (cukup pahami API tingkat tinggi yang terekspos via engine `ragg` dan `systemfonts`).

### Saya harus bisa melakukan:
- [ ] Membangun fungsi wrapper visualisasi yang aman secara konseptual dan dinamis menggunakan tidy evaluation (`{{ }}`).
- [ ] Mendiagnosis dan memperbaiki *silent data drop* pada kalkulasi statistik layer akibat pembatasan sumbu visual.
- [ ] Menjajarkan sumbu horizontal dan vertikal secara presisi (*pixel-perfect alignment*) antar multiple-plot independen menggunakan manipulasi `patchwork` atau perataan `gtable widths`.
- [ ] Mengekstrak, memodifikasi, dan menyusun ulang struktur internal plot menggunakan `ggplotGrob()`, manipulasi `gtable`, dan rendering `grid::grid.draw()`.
- [ ] Mengonfigurasi pipeline rendering headless di lingkungan server produksi (Docker/CI) menggunakan engine `ragg` dengan manajemen font kustom yang deterministik.
- [ ] Mengeliminasi bottleneck rendering pada data skala jutaan baris melalui teknik agregasi statistik in-engine atau rasterisasi hibrida terisolasi.