# BAB 06: Quiz, Challenge, & Knowledge Check
**Visualisasi Data Analitik & Declarative Dashboarding**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Imperative vs. Declarative Visualization Paradigms**  
   Bandingkan paradigma *imperative visualization* (seperti pada modul inti Matplotlib) dengan *declarative grammar of graphics* (seperti pada Altair/Vega-Lite). Bagaimana perbedaan mendasar pada proses translasi antara data atribut ke visual mark (*encodings*), dan apa implikasi arsitekturalnya terhadap portabilitas visualisasi lintas platform (misal: export ke web runtime vs rendering bitmap server-side)?

2. **Execution Graph: Streamlit Script Runner vs. Dash Reactive DAG**  
   Analisis mekanisme evaluasi state pada dashboarding: Bedakan siklus eksekusi *top-to-bottom re-run* milik Streamlit dengan *Directed Acyclic Graph (DAG) reactive callback* milik Plotly Dash. Apa trade-off performa CPU backend, kompleksitas state management, dan konkurensi antar-sesi pengguna dari kedua model tersebut?

3. **Rendering Pipelines: SVG, HTML5 Canvas, dan WebGL**  
   Ketika merender visualisasi berbasis web (misal menggunakan Plotly atau Bokeh), jelaskan batasan komputasi dan memori pada *Document Object Model* (DOM) saat menggunakan **SVG** dibandingkan dengan rendering bitmap dinamis via **Canvas** dan akselerasi GPU via **WebGL**. Kapan limitasi jumlah node SVG ($N > 10.000$) mulai menyebabkan *frame drop* dan *latency unresponsiveness*?

4. **Figure-Level vs. Axes-Level Objects di Seaborn & Matplotlib**  
   Jelaskan secara struktural perbedaan objek antara antarmuka *Axes-level* (misal: `sns.scatterplot(..., ax=ax)`) dan *Figure-level* (misal: `sns.relplot(...)` yang mengembalikan `FacetGrid`). Mengapa manipulasi *subplot geometry*, integrasi ke dalam layout engine kustom, dan thread safety pada backend multi-threaded jauh lebih terkontrol saat menggunakan objek *Axes-level* secara eksplisit?

5. **Payload Serialization Overhead pada Interaktivitas Dashboard**  
   Dalam dashboard analitik interaktif berbasis Python yang berkomunikasi via WebSocket/HTTP REST (client-server architecture), jelaskan bagaimana format serialisasi data (JSON standar vs Apache Arrow / Feather / Binary Protocol Buffers) memengaruhi throughput dan memory footprint pada browser klien ketika mentransfer dataset analitik berukuran >100 MB.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Matplotlib Global State Lifecycle & Memory Leaks pada Production Worker**  
   Eksekusi kode berikut dijalankan berulang kali dalam worker proses Celery/FastAPI untuk menghasilkan chart secara periodik:
   ```python
   import matplotlib.pyplot as plt

   def generate_report_chart(data, report_id):
       fig, ax = plt.subplots()
       ax.plot(data['timestamp'], data['value'])
       fig.savefig(f"reports/{report_id}.png")
       # plt.clf() dipanggil di sini oleh developer
   ```
   Mengapa `plt.clf()` atau `plt.cla()` gagal mencegah memory leak secara persisten, dan mengapa `plt.close(fig)` atau penggunaan antarmuka berorientasi objek murni tanpa modul `pyplot` (`from matplotlib.figure import Figure; fig = Figure(); Canvas(fig)...`) wajib diterapkan pada skenario server headless?

2. **Downsampling Dinamis & Visual Buffering via Datashader**  
   Ketika memvisualisasikan data time-series frekuensi tinggi atau scatter plot geospasial dengan $N = 50.000.000$ titik pengamatan, browser akan mengalami *out-of-memory* (OOM) crash jika seluruh koordinat di-push ke client. Jelaskan arsitektur pipeline *server-side rasterization* menggunakan **Datashader**: bagaimana representasi data diagregasi ke dalam grid piksel 2D sebelum dikonversi menjadi citra/array dinamis sesuai level *zoom* dan *pan* viewport klien?

3. **Race Condition & Mutable State Desynchronization pada `st.session_state`**  
   Pada platform Streamlit multi-user, bagaimana interaksi asinkron (misalnya pooling thread latar belakang atau pembagian resource via decorator `@st.cache_resource`) dapat memicu race condition jika terjadi mutasi in-place terhadap objek yang disimpan di `st.session_state`? Bagaimana mekanisme isolasi thread pada session context Streamlit mencegah interferensi antar tab browser milik pengguna yang berbeda?

4. **Callback Diamond Dependency & Infinite Loops pada Plotly Dash**  
   Perhatikan topologi reaktif Dash di mana Output $C$ bergantung pada Input $A$ dan $B$, namun Input $B$ juga diperbarui oleh callback lain yang dipicu oleh $A$ (*diamond dependency*). Bagaimana Dash scheduler menyelesaikan dependensi ini? Kapan kondisi race condition atau redundant compute dapat terjadi, dan bagaimana konfigurasi `prevent_initial_call` serta pemanfaatan `dash.no_update` mengoptimalkan jalur eksekusi tersebut?

5. **Perceptual Uniformity, Luminance Distortion, dan Color Spaces**  
   Mengapa colormap klasik seperti `Jet` atau `Rainbow` dilarang dalam visualisasi analitik kuantitatif berstandar ilmiah/enterprise? Jelaskan konsep *perceptually uniform colormaps* (seperti `Viridis` atau `Cividis`) dalam ruang warna CAM02-UCS/CIELAB, dan bagaimana penurunan saturasi/luminans yang tidak monoton dapat memanipulasi interpretasi magnitudo gradien data oleh retina manusia.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Browser Crash & Memory Bloat Akibat High-Frequency Telemetry Dashboard
* **Konteks:** Perusahaan IIoT memonitor 10.000 turbin angin. Setiap turbin mengirimkan 10 metrik sensorik per detik ke server. Tim frontend membangun dashboard operasional berbasis web menggunakan visualisasi berbasis SVG murni yang menerima stream data via WebSocket.
* **Gejala Masalah:** Dalam 15 menit setelah dashboard dibuka di control room, browser menghabiskan memori hingga 4 GB RAM, kipas laptop berputar maksimal (CPU 100%), dan browser akhirnya mengalami crash (*Out-of-Memory / Canvas context lost*).
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi akar masalah pada level rendering engine DOM klien dan transmisi data. Mengapa pendekatan *append-to-DOM* pada setiap paket data sensorik bersifat non-skalabel?
  2. Rancang arsitektur pipeline rendering ulang yang memisahkan ingestion stream dari visual presentation: tentukan downsampling algorithm (misalnya Largest-Triangle-Three-Buckets / LTTB), framework rendering yang tepat (Canvas/WebGL vs SVG), dan strategi buffering interval (fixed-frame refresh rate, misal 30 FPS throttle).

### Skenario B: Cross-Tenant Data Leakage Akibat Misuse Cache pada Multi-Tenant Declarative Dashboard
* **Konteks:** Sebuah startup FinTech membangun analytical reporting portal untuk 50 klien enterprise menggunakan Streamlit. Dashboard menggunakan decorator `@st.cache_data` dan `@st.cache_resource` secara ekstensif untuk memangkas latency eksekusi query SQL yang berat.
* **Gejala Masalah:** Seorang analis dari Bank X membuka dashboard portofolio pinjaman, dan secara acak dapat melihat data portofolio rahasia milik Bank Y setelah menerapkan filter rentang tanggal tertentu. Insiden ini diklasifikasikan sebagai P0 Security Breach.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana mekanisme *key hashing* internal pada decorator caching Streamlit (`@st.cache_data`) bekerja? Jelaskan secara teknis bagaimana ketiadaan tenant-identifier (misal `tenant_id` atau user session token) dalam parameter fungsi cache dapat menyebabkan cache collision lintas sesi.
  2. Tuliskan pola refaktorisasi signature fungsi dan dependency injection untuk parameter fungsi yang di-cache agar menjamin isolasi data 100% antar-penyewa (*strict tenancy isolation*) tanpa mematikan efisiensi cache untuk query non-sensitif.

### Skenario C: Trade-off Arsitektural Dashboard Skala Enterprise (5.000 Concurrent Users)
* **Konteks:** Departemen Logistik Global perlu menyediakan dashboard pelacakan shipment real-time dengan basis pengguna mencapai 5.000 *concurrent active users* pada jam sibuk. Fitur mencakup: filtering rute global, cross-filtering chart interaktif (klik pada bar chart memperbarui map visual), dan export dataset yang terfilter.
* **Dilema:** Tim terbelah menjadi dua kubu:
  * *Kubu 1:* Mengusulkan arsitektur **Pure Streamlit/Gradio** demi kecepatan time-to-market dan kemudahan implementasi Python murni.
  * *Kubu 2:* Mengusulkan arsitektur **Decoupled System**: Backend FastAPI + Redis cache + Apache Arrow Flight API, dengan Frontend declarative berbasis client-side framework (React + Vega-Lite / Plotly.js / deck.gl).
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis titik kegagalan (*single point of failure*) dan batas skalabilitas horizontal dari kubu 1 (Streamlit script runner model) ketika menghadapi beban 5.000 sesi concurrent dengan koneksi WebSocket persisten dan memory consumption per proses Python.
  2. Buat matriks evaluasi trade-off (Development Velocity, Infrastructure Cost, Concurrent Scaling Capacity, UI/UX Latency, dan State Synchronization) yang membenarkan mengapa Kubu 2 adalah pilihan yang tepat untuk target non-functional requirements tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Financial Anomaly Telemetry Dashboard
**Deskripsi Masalah:**  
Anda bertindak sebagai Principal Data Platform Architect di sebuah bursa efek digital. Tim Risk Management membutuhkan dashboard analitik investigatif performa tinggi yang mampu memvisualisasikan anomali likuiditas pasar modal dari dataset transaksi berukuran besar (10.000.000 orderbook records). Sistem harus responsif, bebas memory leak, dan mendukung interaksi cross-filtering latensi sub-detik tanpa membebani browser client.

**Requirements:**
1. **Data Ingestion & Downsampling Engine:**
   * Bangun modul data pipeline menggunakan Python (bisa menggunakan Polars/DuckDB) yang mengomputasi *LTTB (Largest-Triangle-Three-Buckets)* atau rasterisasi binned aggregasi untuk menurunkan 10.000.000 datapoints time-series menjadi maksimal 2.000 representasi visual per viewport tanpa menghilangkan puncak anomali (*spikes/dips*).
2. **Declarative Dashboard Implementation:**
   * Bangun dashboard menggunakan framework deklaratif Python (Plotly Dash, Panel, atau Streamlit dengan engine WebGL/Altair).
   * Visualisasi wajib mencakup minimal dua plot interaktif:
     1. Time-series Volume/Price dengan zona anomali (highlighted anomalies via rolling z-score/isolation forest).
     2. Cross-sectional dynamic scatter plot (Slippage vs. Order Size) menggunakan rendering berbasis WebGL (`scattergl`).
3. **State Management & Optimization:**
   * Terapkan arsitektur caching yang memisahkan data fetching mentah dengan view state transformation.
   * Pastikan tidak ada data mentah 10M record yang dikirimkan langsung sebagai JSON raw string ke frontend.
   * Terapkan throttle/debounce pada interaksi pengguna (slider windowing atau date range picker) minimal 300ms untuk mencegah overloading thread backend.

**Constraints:**
* Penggunaan memori backend Python worker tidak boleh melebihi 1,5 GB saat dashboard aktif dijalankan oleh minimal 3 sesi paralel.
* Client-side DOM rendering tidak boleh melebihi 2.500 SVG/Canvas nodes.
* Latensi pembaruan chart saat merespons event filter/zoom harus di bawah 500 milidetik (*sub-second response time*).

**Expected Output:**
* Repositori kode modular yang memuat:
  * Engine downsampling / aggregasi data (`aggregator.py`).
  * Deklarasi UI dan reactive graph callbacks (`app.py`).
  * Unit test beban profiling memori menggunakan `tracemalloc` atau `memory_profiler` untuk membuktikan tidak ada memory leakage pada looping redraw.
  * Dokumen singkat (Architecture Runbook) berformat Markdown yang menjelaskan alur data dari file parquet mentah hingga ke layar analis.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *Grammar of Graphics* (Wilkinson model: data, mark, encoding, scale, guide) vs *Canvas Drawing/Procedural* API.
- [ ] Perbedaan siklus hidup memori antara backend Matplotlib non-GUI (`Agg`) dengan GUI backends.
- [ ] Arsitektur internal reaktif Streamlit (WebSocket loop, rerun dari baris pertama, session runner) vs Dash (Flask server, stateless/stateful callbacks via POST/WebSocket).
- [ ] Dampak pemilihan colormap perceptually uniform (Viridis/Plasma) vs diverging (Coolwarm/RdBu) vs qualitative (Set1/Tab10) pada akurasi kognitif data.
- [ ] Batasan kapasitas Web Browser: perbedaan struktural dan alokasi memori antara DOM-based SVG, 2D HTML5 Canvas, dan hardware-accelerated WebGL.
- [ ] Konsep algoritma downsampling visualisasi (LTTB, min-max binning) untuk visualisasi time-series masif.
- [ ] Vektor serangan dan celah keamanan dalam caching multi-user (`st.cache_data`, Dash memoization) yang berpotensi memicu information leakage.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter opsional styling Matplotlib/Seaborn (misal: `rc_params` dictionary keys, formatting strings spesifik untuk garis atau tick locator formatters).
- [ ] Seluruh spesifikasi skema skalar JSON Vega-Lite secara manual tanpa bantuan skema generator/Altair API.
- [ ] Penamaan heksadesimal kode warna individual dalam palet warna standar.
- [ ] Sintaks styling detail CSS/Bootstrap classes untuk komponen dashboarding.

### Saya harus bisa melakukan:
- [ ] Menulis visualisasi analitik berlapis (*layered grammar of graphics*) menggunakan Seaborn modern interface atau Altair dengan binding interaktif (*selections, conditions, tooltips*).
- [ ] Mengonfigurasi backend Matplotlib headless berorientasi objek murni tanpa global state (`matplotlib.figure.Figure`) dalam container atau asynchronous server worker tanpa memicu OOM leak.
- [ ] Mengimplementasikan *cross-filtering* yang terisolasi antar-sesi pengguna pada framework dashboard deklaratif (Streamlit/Dash).
- [ ] Menghubungkan dashboard dengan data layer berskala besar menggunakan query engine in-process (seperti DuckDB atau Polars) yang merasterisasi atau mengagregasi data sebelum ditranslasikan ke visual mark.
- [ ] Mengidentifikasi dan merefaktor bottleneck latensi dashboard menggunakan browser performance profiler (DevTools Network & Performance tab) dan server-side execution profilers.