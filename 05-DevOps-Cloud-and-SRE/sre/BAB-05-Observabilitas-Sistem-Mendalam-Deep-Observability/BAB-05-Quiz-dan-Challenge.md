# Evaluasi Bab 05: Observabilitas Sistem Mendalam (Deep Observability)

---

## 1. Basic Questions (Pilihan Ganda & Isian Singkat)

### Soal 1
Manakah dari kombinasi sinyal berikut yang secara tepat menyusun **The Four Golden Signals** menurut Google SRE?
- A. Rate, Errors, Duration, Saturation
- B. Latency, Traffic, Errors, Saturation
- C. Utilization, Saturation, Errors, Latency
- D. Uptime, Availability, Reliability, Performance

### Soal 2
Metodologi **USE** yang dirancang oleh Brendan Gregg berfokus utama pada observasi:
- A. Transaksi bisnis tingkat aplikasi (Application business logic).
- B. Arsitektur berbasis antarmuka permintaan pengguna (Request/User endpoints).
- C. Sumber daya komputasi dan infrastruktur fisik/logis (Resources/Hardware).
- D. Alur navigasi pengguna pada frontend (Frontend user journeys).

### Soal 3
Header standar W3C TraceContext yang bertugas membawa data sampling flag, trace-id, dan parent span-id adalah:
- A. `tracestate`
- B. `x-b3-traceid`
- C. `traceparent`
- D. `ot-tracer-spancontext`

### Soal 4
Apa dampak langsung dari fenomena *High Cardinality Metric Explosion* pada sistem Time-Series Database (TSDB) seperti Prometheus?
- A. CPU aplikasi target menjadi 100% akibat serialisasi data.
- B. TSDB kehabisan memori (OOM) karena jumlah instansiasi time-series unik melipatgandakan indeks memori.
- C. Koneksi jaringan database terputus akibat paket MTU terlampaui.
- D. Header W3C TraceContext tertolak oleh reverse-proxy.

### Soal 5
Fitur yang memungkinkan integrasi langsung antara metrik histogram TSDB dan jejak spesifik tracing tanpa menambahkan dimensi kardinalitas label baru disebut:
- A. Continuous Profiling
- B. Distributed Context Baggage
- C. Trace Propagation
- D. Exemplars

---

## 2. Intermediate Questions (Analisis & Desain Solusi)

### Soal 1: Pemisahan Metrik Sinyal Latensi
Jelaskan mengapa menghitung latensi rata-rata gabungan (*arithmetic mean latency*) antara HTTP 200 dan HTTP 500 sangat dilarang dalam implementasi Golden Signals! Berikan contoh numerik konkret yang menunjukkan bagaimana metrik tersebut dapat menipu tim SRE (*false sense of security*).

### Soal 2: Struktur W3C TraceContext
Diberikan header W3C berikut:
```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```
Analisislah:
1. Apa arti dari angka `00` di awal?
2. Berapa representasi ukuran byte dari `trace-id` tersebut?
3. Apa implikasi dari bit `01` di bagian paling akhir terhadap subsistem collector downstream?

### Soal 3: Memory Protection pada OTel Collector
Dalam konfigurasi OTel Collector, mengapa processor `memory_limiter` **wajib** diposisikan sebelum processor `batch` pada pipeline konfigurasi? Apa yang terjadi jika urutannya ditukar saat sistem menerima lonjakan trafik masif?

### Soal 4: USE vs RED Diagnostic Selection
Sebuah service berbasis Apache Kafka Consumer membaca pesan transaksi dari topic antrean dan mengeksekusi penulisan ke disk SSD lokal. Tentukan:
1. Metrik apa yang akan Anda pantau menggunakan pendekatan **USE**?
2. Metrik apa yang akan Anda pantau menggunakan pendekatan **RED**?

### Soal 5: Mitigasi Kardinalitas Data
Seorang engineer membuat metrik berikut:
`http_request_duration_seconds_bucket{endpoint="/api/v1/user/102941/payment", customer_email="alice@example.com"}`
Tunjukkan 2 kesalahan fatal pada metrik tersebut dan tuliskan rekonstruksi representasi metrik yang benar sesuai kaidah standar produksi!

---

## 3. Scenario-Based Questions (Kasus Nyata Industri)

### Kasus 1: "The Black Friday Ghost Latency Outage"
**Konteks**: Platform e-commerce Anda mengalami *flash sale*. Dashboard Prometheus menunjukkan rata-rata CPU node klaster adalah 42%, kapasitas RAM tersisa 60%, dan laju error HTTP (RED Errors) bernilai 0.05% (tampak aman). Namun, ribuan laporan komplain masuk ke Twitter pelanggan bahwa tombol "Checkout" macet selama 30 detik sebelum akhirnya gagal.
- **Tugas SRE**:
  1. Identifikasi sinyal apa dari *The Four Golden Signals* yang luput dianalisis oleh tim on-call.
  2. Jelaskan metrik saturasi apa pada layer aplikasi dan container engine yang berpotensi memicu kondisi ini tanpa menaikkan penggunaan CPU.
  3. Langkah diagnostik apa yang harus dijalankan pertama kali untuk memvalidasi masalah latensi ekor (*tail latency*) ini?

### Kasus 2: "The Cascading Tracing Disconnect"
**Konteks**: Arsitektur pembayaran terdistribusi terdiri dari:
`Ingress Gateway -> Order Service -> Payment Service (Worker Go) -> 3rd Party Payment API`
Tim SRE mengamati pada dashboard Grafana Tempo bahwa rentang *distributed trace* terputus saat mencapai `Payment Service`. Trace dari `Order Service` tercatat selesai, namun operasi yang dilakukan oleh worker goroutine pada `Payment Service` tercatat sebagai trace baru independen dengan `trace-id` yang berbeda, sehingga waterfall trace terbelah menjadi dua.
- **Tugas SRE**:
  1. Identifikasi akar penyebab masalah teknis (*root cause*) pada kode Go di `Payment Service`.
  2. Tuliskan contoh kode atau logika pemulihan yang harus diterapkan oleh software engineer untuk memperbaiki propagasi context ini!

### Kasus 3: "TSDB Cluster OOM Panic"
**Konteks**: Setelah peluncuran rilis baru microservice Authentication, pod TSDB Prometheus mengalami restart berulang kali (*CrashLoopBackOff / OOMKilled*). Alokasi memori Prometheus yang sebelumnya stabil di 16GB melompat melebihi batas pod sebesar 64GB dalam kurun waktu 15 menit pasca-deployment.
- **Tugas SRE**:
  1. Bagaimana langkah darurat (*mitigasi cepat*) di sisi Kubernetes/Ingress untuk menghentikan loop OOM ini tanpa mematikan layanan otentikasi?
  2. Konfigurasi OTel Collector processor apa yang dapat diinjeksikan secara real-time untuk memangkas label penyebab insiden ini sebelum telemetri mencapai Prometheus?

---

## 4. Practical Chapter Challenge: Advanced Telemetry Architecture Implementation

### Deskripsi Masalah
Perusahaan FinTech Anda memproses transaksi pembayaran instan. Anda diminta membangun fondasi pipeline observabilitas yang tangguh untuk memproses telemetri mikroservis checkout.

### Persyaratan Arsitektural:
1. **Mock Service Tracing Pipeline**:
   - Buat skrip Python mandiri (`opentelemetry_tracing_pipeline.py`) yang mengimplementasikan SDK OpenTelemetry.
   - Layanan harus memiliki 2 tahapan fiktif: `validate_checkout` dan `process_payment`.
   - Propagasikan konteks tracing W3C secara eksplisit antar fungsi tersebut.
2. **Exemplar Integration**:
   - Skrip harus mencatat metrik latensi menggunakan Histogram OTel SDK.
   - Lampirkan `TraceID` transaksi ke dalam observasi histogram latensi sebagai **Exemplar**.
3. **High Cardinality Guard**:
   - Implementasikan fungsi pembersih (*sanitizer*) atribut yang mengeliminasi field kardinalitas tinggi berbahaya (`credit_card`, `user_id`, `session_token`) dan hanya menyisakan atribut yang aman secara semantik (`route_template`, `status_code`).
4. **Collector Architecture Configuration**:
   - Susun konfigurasi YAML Collector yang menerapkan tail-based memory limiters dan OpenMetrics endpoint exporter.

---

## Kunci Jawaban & Panduan Evaluasi

### 1. Kunci Jawaban Basic Questions
1. **B** (Latency, Traffic, Errors, Saturation).
2. **C** (Resources/Hardware - Utilization, Saturation, Errors).
3. **C** (`traceparent`).
4. **B** (TSDB kehabisan memori / OOM karena pelipatgandaan deret waktu time-series unik).
5. **D** (Exemplars).

### 2. Panduan Jawaban Intermediate
1. **Pemisahan Latensi**: HTTP 500 sering gagal secara cepat/fast-fail (misal: koneksi ditolak dalam 2ms), sedangkan request HTTP 200 normal butuh waktu 500ms. Jika 50% request gagal (500) dalam 2ms dan 50% sukses (200) dalam 500ms, nilai rata-rata adalah $\frac{2 + 500}{2} = 251\text{ms}$. SRE mengira performa aplikasi membaik dari 500ms menjadi 251ms, padahal sistem sedang hancur lebur dengan error rate 50%.
2. **W3C Parsing**:
   - `00`: Versi spesifikasi W3C TraceContext saat ini.
   - `trace-id`: 16 byte (direpresentasikan dalam 32 karakter heksadesimal).
   - `01`: `recorded/sampled bit`. Menginstruksikan downstream collector/tracer bahwa trace ini harus disimpan dan direkam ke storage backend.
3. **Memory Limiter Order**: Harus di urutan terdepan agar data telemetri yang baru masuk langsung ditolak/didrop seketika jika RAM Collector sudah mencapai batas limit kritis. Jika diletakkan setelah batch processor, Collector akan tetap memproses alokasi memori internal untuk batching, yang mempercepat trigger OOM sebelum processor limiter sempat bertindak.
4. **USE vs RED pada Consumer**:
   - *USE*: Disk I/O Utilization %, Disk Queue Length (Saturation), Disk Write IO Errors.
   - *RED*: Rate pesan dikonsumsi/detik (Rate), Rate kegagalan deserialisasi atau commit offset (Errors), Durasi eksekusi pengolahan satu pesan (Duration).
5. **Kardinalitas**:
   - Kesalahan: Label `endpoint` mengandung ID dinamis (`102941`), dan menyertakan label `customer_email` (unbounded dimension).
   - Perbaikan:
     `http_request_duration_seconds_bucket{route="/api/v1/user/{id}/payment", status="200"}`
     Nilai ID dan Email dipindahkan ke Span Attributes atau Logs.