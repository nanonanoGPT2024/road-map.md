# BAB 05: Quiz, Challenge, & Knowledge Check
**Exploratory Data Analysis & Advanced Visualization**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Transformasi Koordinat vs. Transformasi Skala:**
   Jelaskan perbedaan mendasar antara melakukan transformasi data menggunakan skala (misalnya, `scale_y_log10()`) dibandingkan menggunakan sistem koordinat (misalnya, `coord_trans(y = "log10")`). Analisis implikasinya terhadap kalkulasi layer statistik (seperti `geom_smooth()` atau `stat_summary()`) dan visualisasi grid garis panduan (*grid lines*).

2. **Semantik Pemetaan Estetika (*Aesthetic Mapping*) vs. Parameter Statis:**
   Dalam arsitektur *Grammar of Graphics*, jelaskan perbedaan evaluasi kompilasi antara `aes(color = "blue")` dan `geom_point(color = "blue")`. Mengapa pemetaan string konstan di dalam `aes()` menginisialisasi skala diskret baru alih-alih langsung mengubah warna visual dari *grobs* (*grid graphical objects*)?

3. **Mekanika Pemisahan Data: Long vs. Wide Data Format:**
   Mengapa `ggplot2` mewajibkan data berada dalam bentuk *tidy/long format* (`tidyr::pivot_longer()`) daripada *wide format* untuk pemetaan multivariat? Bagaimana relasi antara struktur *long format* ini dengan model internal pengelompokan implisit (*implicit grouping*) melalui estetika seperti `group`, `color`, atau `linetype`?

4. **Hierarki Persepsi Visual (Cleveland & McGill):**
   Urutkan saluran perseptual visual (*visual encoding channels*) berdasarkan akurasi decoding kognitif manusia menurut teori Cleveland & McGill (panjang, posisi sumbu sejajar, area, rona warna, sudut). Bagaimana prinsip ini memandu Anda dalam memilih antara *grouped bar chart*, *stacked bar chart*, dan *small multiples (faceting)* saat mengeksplorasi interaksi tiga variabel kategorikal?

5. **Kopling antara `Stat` dan `Geom`:**
   Setiap layer visual di `ggplot2` merupakan kombinasi dari `Stat` (transformasi statistik) dan `Geom` (representasi geometris). Jelaskan apa yang terjadi di balik layar ketika Anda memanggil `geom_bar()` tanpa argumen tambahan dibandingkan dengan `geom_col()`. Bagaimana cara Anda memanfaatkan parameter `stat = "identity"` pada geometri yang secara *default* menggunakan agregasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Lifecycle Render Grafik: `ggplot_build` hingga `gtable`:**
   Uraikan tahap-tahap eksekusi internal yang dilewati objek grafik sejak pemanggilan deklaratif `p <- ggplot(...) + geom_*()` hingga akhirnya digambar oleh sistem rendering grafis perangkat lunak (*graphic device*). Apa peran dari fungsi `ggplot_build(p)` dan `ggplot_gtable(ggplot_build(p))` dalam pipeline rendering tersebut?

2. **Dilema Pemotongan Data: `coord_cartesian(xlim = ...)` vs. `scale_x_continuous(limits = ...)`:**
   Seorang data engineer menemukan anomali bahwa nilai kuartil pada `geom_boxplot()` berubah drastis setelah ia mempersempit batas sumbu X. Diagnosis kesalahan logika pemanggilan fungsi mana yang menyebabkan masalah ini, bedah mekanisme internal *out-of-bounds* (OOB) handling pada skala, dan jelaskan mengapa `coord_cartesian()` mempertahankan integritas statistik data sementara `scale limits` membuangnya (*censoring*).

3. **Non-Standard Evaluation (NSE) dan Programmatic Faceting:**
   Saat menulis fungsi pembungkus (*wrapper function*) produksi untuk visualisasi otomatis:
   ```r
   create_report_plot <- function(df, x_var, y_var, facet_var) {
     ggplot(df, aes(x = {{ x_var }}, y = {{ y_var }})) +
       geom_point() +
       facet_wrap(vars({{ facet_var }}))
   }
   ```
   Jelaskan peran *embracing operator* (`{{ }}`) dari package `rlang`. Apa konsekuensinya terhadap eksekusi jika Anda mencoba menggunakan sintaks lama `facet_wrap(~ facet_var)` di dalam fungsi yang menerima variabel sebagai argumen simbolis atau string?

4. **Ekstensi `ggproto` dan Pembuatan Geometri Kustom:**
   Arsitektur modular `ggplot2` memanfaatkan sistem OOP berbasis prototipe (`ggproto`). Jika Anda diminta merancang layer analitik kustom `stat_confidence_ellipse()`, metode kelas apa (`compute_group`, `compute_panel`, atau `draw_group`) yang wajib di-override untuk menghitung matriks kovarians per subgrup data sebelum *grobs* digenerasikan?

5. **Artefak Overplotting dan Saturasi Alpha Blending:**
   Saat memplot 1.000.000 titik observasi, penggunaan transparansi (`alpha = 0.01`) gagal mendeteksi multimodalitas karena masalah *numerical underflow* dan *color space clamping* pada perangkat grafis. Jelaskan secara mekanistis mengapa pendekatan agregasi ruang 2D seperti *hexagonal binning* (`geom_hex()`) atau rasterisasi dinamis (`scattermore` / `ggrastr`) lebih superior dari sudut pandang konsumsi memori dan ketelitian analitis.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Crash OOM pada Automated Batch Reporting Service
Sebuah microservice batch reporting berbasis R berjalan di Kubernetes pod (RAM Limit: 4GB). Service ini mengeksekusi script RMarkdown/Quarto untuk membuat laporan berkala performa sensor IoT yang terdiri dari 15 juta baris data telemetri berfrekuensi tinggi.
Ketika fungsi visualisasi dieksekusi menggunakan kombinasi `ggplot2` standar dengan format ekspor PDF vektor (`ggsave("out.pdf", device = "pdf")`), pod mengalami insiden *Out of Memory* (OOM) dan di-terminate dengan `Exit Code 137`. Menariknya, filtering data awal hanya memakan memori ~800MB RAM.

* **Pertanyaan Diagnostik:**
  1. Mengapa output berbasis format vektor (PDF) menyebabkan lonjakan memori eksponensial selama konversi *grob* ke display list dan disk file pada volume data 15 juta titik?
  2. Solusi arsitektural apa yang harus diimplementasikan pada pipeline visualisasi tersebut untuk menghasilkan visualisasi yang tetap tajam secara visual namun tidak mengekspos jutaan node objek vektor ke dokumen PDF akhir? Rancang mitigasi teknisnya menggunakan integrasi raster-vektor hybrid.

---

### Skenario B: Visual Masking & Bias Data Agregasi pada Analisis Fraud Finansial
Tim investigasi fraud mengevaluasi distribusi anomali penarikan dana menggunakan panel visualisasi:
```r
p <- ggplot(fraud_data, aes(x = transaction_type, y = amount)) +
  geom_boxplot(outlier.shape = NA) +
  stat_summary(fun = "mean", geom = "point", color = "red") +
  facet_wrap(~ risk_category, scales = "free_y")
```
Setelah dilakukan deployment ke level operasional, tim audit menemukan bahwa pola penarikan masif dari fraud ring berskala jutaan dolar tidak terdeteksi oleh analis. Penyelidikan menunjukkan visualisasi tersebut menyembunyikan karakteristik sebaran bimodalnya secara fatal dan memberikan estimasi visual yang salah.

* **Pertanyaan Diagnostik:**
  1. Identifikasi setidaknya dua kesalahan metodologis dalam desain plot di atas yang menyebabkan distorsi interpretasi distribusi data finansial dengan variansi ekstrem (*heavy-tailed*).
  2. Tuliskan ulang dan modifikasi spesifikasi grafik tersebut menjadi sebuah layout *distribution diagnostic plot* komprehensif (misalnya mengkombinasikan *Raincloud Plot*, distribusi densitas, dan *jittered actual values* yang dibatasi secara deterministik) agar representasi median, dispersi ekor (*tail events*), dan multimodalitas tampak secara transparan.

---

### Skenario C: Multi-Panel Grid Alignment & Render Race Conditions pada Dashboard Paralel
Sebuah platform analitik mengeksekusi pipeline visualisasi multivariat paralel menggunakan package `future` dan `patchwork` untuk menggabungkan 6 chart interaktif dan statis ke dalam layout matriks kompleks. 
Namun, visualisasi gabungan sering menghasilkan output di mana sumbu X antar sub-plot tidak sejajar (*misaligned axes*) akibat perbedaan lebar label sumbu Y (misal: panel atas menampilkan angka ribuan "1,000", panel bawah menampilkan angka miliaran "1,000,000,000"). Selain itu, proses render sering menghasilkan plot korup ketika diakses oleh *concurrent requests*.

* **Pertanyaan Diagnostik:**
  1. Bagaimana mekanisme arsitektural `gtable` menyelesaikan koordinat visual, dan mengapa deklarasi margin bawaan gagal mengunci keselarasan posisi panel (*panel bounding boxes*) ketika label numerik memiliki lebar karakter (*string width*) yang tidak seragam?
  2. Jelaskan langkah standardisasi kalkulasi ukuran grob menggunakan fungsi tingkat rendah `gtable_combine()` / `grid::unit` atau fitur alignment eksplisit pada `patchwork` / `cowplot` untuk menjamin bahwa plot panel vertikal memiliki sumbu X yang sejajar secara piksel (*pixel-perfect alignment*), bebas dari efek perbedaan lebar teks label Y.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Telemetry Anomaly Detection Diagnostic Engine

#### Problem:
Sebagai Principal Platform Engineer di fasilitas pengujian wahana antariksa, Anda menerima stream data telemetri getaran mesin roket sebesar 5 juta titik data time-series per tes. Data mengalami anomali sensor (*glitches*), noise acak, dan pergeseran frekuensi struktural. Tim mekanik membutuhkan modul visualisasi otomatis yang dapat mendiagnosis sinyal ini secara instan setelah pengujian selesai tanpa menyebabkan memori server crash, sekaligus mampu menonjolkan area anomali getaran secara presisi.

#### Requirements:
1. **Pipeline Ingestion & Data Structuring:**
   - Simulasikan/bangun dataset 5.000.000 observasi dengan kolom: `timestamp` (POSIXct), `sensor_id` (kategorikal: 4 sensor), `vibration_amplitude` (numerik kontinu bimodal), dan `is_anomaly` (boolean: hasil deteksi machine learning, rasio ~0.1%).
2. **Dynamic Processing & Hybrid Rendering:**
   - Gunakan pendekatan rasterisasi selektif (misalnya via `scattermore` atau `ggrastr`) untuk memplot titik-titik data dasar agar waktu kompilasi grafis di bawah 5 detik dan ukuran file akhir kecil.
   - Buat layer anomali (`is_anomaly == TRUE`) menggunakan penanda vektor resolusi tinggi berwarna kontras yang berada tepat di atas layer raster.
3. **Advanced Faceting & Statistical Summary:**
   - Terapkan layout *multipanel* independen untuk setiap sensor dengan sinkronisasi sumbu waktu (sumbu X).
   - Tambahkan layer moving average interaktif (*rolling mean & confidence interval ribbon*) menggunakan kalkulasi analitis dinamis (misalnya `slider` atau `data.table::frollmean`) tanpa memperlambat pipeline render grafik.
4. **Publication-Ready Styling & Accessibility:**
   - Terapkan tema minimalis performa tinggi (*dark mode* untuk tampilan ruang kontrol).
   - Gunakan palet ramah buta warna (*Colorblind Safe* / Color Universal Design).
   - Label sumbu X dan Y harus terformat rapi dengan konversi unit metrik standar (Hz / G-Force).

#### Constraints:
- Dilarang merender 5 juta titik secara murni menggunakan `geom_point()` standar tanpa rasterisasi.
- Penggunaan RAM selama proses render grafik dari awal hingga file tersimpan tidak boleh melebihi 2 GB.
- Visualisasi harus disimpan ke disk dalam format PNG (300 DPI, 1920x1080) dan PDF tanpa *vector bloating*.
- Seluruh pipeline pembuatan grafik harus dibungkus dalam modul fungsi fungsional murni (*idempotent function*).

#### Expected Output:
Skrip R mandiri (*self-contained script*) yang:
1. Memiliki validasi assertion pra-render terhadap tipe data input.
2. Membentuk dan merender compound plot menggunakan `patchwork` atau manipulasi `gtable`.
3. Menghasilkan visualisasi telemetri berkinerja tinggi yang menampilkan jutaan titik getaran latar belakang abu-abu transparan (raster), anomali merah menyala (vektor), dan tren rata-rata bergerak oranye tebal (vektor).
4. Mencetak log benchmark waktu eksekusi (`bench::mark` atau `system.time`) dan jejak alokasi memori yang membuktikan efisiensi sistem.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Logika fondasi *Grammar of Graphics*: pemisahan antara Data, Skala (*Scales*), Geometri (*Geoms*), Transformasi Statistik (*Stats*), Koordinat (*Coords*), dan *Faceting*.
- [ ] Siklus internal arsitektur `ggplot2`: dari objek deklaratif, evaluasi data oleh `ggplot_build()`, konversi struktural ke *gtable*, hingga materialisasi grafis melalui *grid grobs*.
- [ ] Perbedaan deterministik antara *data clipping/censoring* pada `scale_*_continuous(limits = ...)` vs *visual zooming* pada `coord_cartesian(xlim = ...)`.
- [ ] Prinsip pemetaan kognitif dan persepsi visual (Peringkat saluran visual Cleveland & McGill) untuk menghindari representasi data yang menyesatkan (*misleading charts*).
- [ ] Batasan perangkat grafis (*graphic devices*) dan arsitektur file format (PDF, SVG vektor vs PNG, WebP raster) terhadap beban render data masif.

### Saya tidak perlu menghafal:
- [ ] Nama-nama argumen tema mikro secara presisi (seperti `axis.ticks.length.x.bottom`). Manfaatkan dokumentasi interaktif `?theme`.
- [ ] Kode heksadesimal spesifik untuk setiap palet visual (gunakan fungsi builder seperti `scales::hue_pal()` atau paket `viridis`).
- [ ] Semua nama stat method bawaan internal R; cukup pahami mapping default dari geom yang sering dipakai dan cara meng-override-nya menggunakan `stat = "identity"`.

### Saya harus bisa melakukan:
- [ ] Menulis fungsi kustom yang aman menggunakan paradigma *Tidy Evaluation* (`{{ }}` / `.data[[var]]`) untuk visualisasi data programmatic.
- [ ] Mengatasi masalah *overplotting* ekstrem secara profesional menggunakan agregasi densitas 2D (*hexagonal binning*), kontur, atau *hybrid rasterization engine*.
- [ ] Mendiagnosis dan memperbaiki *layout misalignment* multi-grafik menggunakan abstraksi tingkat tinggi (`patchwork`, `cowplot`) atau tingkat rendah (`gtable`).
- [ ] Merancang grafik diagnostik distribusi komprehensif (*Raincloud plots*, perbandingan median/IQR, penandaan outlier) untuk mendeteksi multimodalitas data tanpa bias agregasi.
- [ ] Melakukan profiling dan debugging bottleneck memori/waktu pada proses kompilasi visualisasi skala besar di lingkungan produksi headless server.