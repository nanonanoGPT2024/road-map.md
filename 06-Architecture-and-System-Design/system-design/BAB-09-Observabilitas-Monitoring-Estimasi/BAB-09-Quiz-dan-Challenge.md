# BAB 09 — Evaluasi, Quiz, & Chapter Challenge
## Observabilitas, Monitoring, & Estimasi Kapasitas

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah menguasai dua keterampilan vital arsitek sistem terdistribusi:
1. **Back-of-the-Envelope Estimation**: Menghitung kapasitas matematis kasar sistem sebelum implementasi (Throughput QPS, Peak Load, 5-Year Storage Projection dengan overhead replikasi dan index, Bandwidth Ingress/Egress, serta Caching Pareto 80/20).
2. **Observabilitas Terdistribusi**: Menguasai Tiga Pilar Observabilitas (Metrics, Structured Logs, Traces), metodologi RED & USE, propagasi W3C Trace Context (`traceparent`), serta identifikasi bottleneck performa menggunakan visualisasi Flame Graph / Waterfall.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Berapa jumlah detik dalam sehari ($86.400 \approx 100.000$) dan bagaimana menghitung QPS dari volume harian secara cepat.
- [ ] Rasio perbandingan latensi: RAM (~100ns) vs NVMe SSD (~1ms) vs Trans-Atlantik RTT (~150ms).
- [ ] Mengapa estimasi storage wajib memperhitungkan indeks basis data (+30-50%) dan faktor replikasi (3x).
- [ ] Perbedaan fokus antara RED Method (Rate, Errors, Duration untuk request) dan USE Method (Utilization, Saturation, Errors untuk resource).
- [ ] Bagaimana `trace_id` dan `span_id` menghubungkan log terisolasi dari puluhan microservices menjadi satu alur kronologis yang utuh.

### Saya Tidak Perlu Menghafal:
- Rumus aproksimasi desimal presisi tinggi hingga digit ke-5.
- Semua implementasi internal protokol biner gRPC OTLP exporter.

### Saya Harus Bisa Melakukan:
- [ ] Menghitung kebutuhan resource server, memory Redis, dan disk cloud dalam waktu < 5 menit.
- [ ] Membaca grafik waterfall distributed trace untuk menemukan akar masalah latensi sistem.
- [ ] Merancang format log terstruktur JSON dengan korelasi trace context.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Berapa perkiraan kasar jumlah request per detik (QPS) jika sebuah aplikasi melayani 86,4 juta request dalam satu hari?**
2. **Apa yang dimaksud dengan prinsip Pareto 80/20 dalam konteks penentuan ukuran kapasitas RAM cache?**
3. **Sebutkan Tiga Pilar Observabilitas dan pertanyaan apa yang dijawab oleh masing-masing pilar tersebut.**
4. **Apa perbedaan antara Rate pada RED Method dan Utilization pada USE Method?**
5. **Apa fungsi dari header HTTP `traceparent` dalam standar W3C Trace Context?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Jika data mentah baru sebuah aplikasi adalah 500 GB per hari, berapa estimasi kapasitas disk nyata yang harus dialokasikan untuk 3 tahun ke depan jika database menggunakan Master + 2 Replicas dan memiliki index overhead sebesar 40%?**
7. **Mengapa memasukkan `user_id` atau `email` sebagai label dimensi pada metrik Prometheus (`http_requests_total`) dianggap sebagai anti-pattern berbahaya (High Cardinality)?**
8. **Jelaskan perbedaan antara p50, p95, dan p99 latency. Mengapa p99 seringkali menjadi metrik paling kritis bagi kepuasan pengguna di aplikasi e-commerce?**
9. **Apa perbedaan antara Head-Based Sampling dan Tail-Based Sampling pada distributed tracing, dan kapan kita harus menggunakan Tail-Based Sampling?**
10. **Bagaimana cara mendeteksi masalah "Thread Starvation" pada CPU menggunakan USE Method sebelum server benar-benar crash?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Kapasitas Layanan Berbagi Foto (Instagram Mini)**  
   Sebuah aplikasi berbagi foto memiliki 50 juta Daily Active Users (DAU).
   - Rata-rata 1 pengguna mengunggah 1 foto per hari (ukuran rata-rata foto 500 KB).
   - Rata-rata 1 pengguna melihat 40 foto per hari di feed mereka.
   - Hitung:
     a. Write QPS rata-rata dan Peak Write QPS (asumsikan peak = 2x).
     b. Kebutuhan storage disk untuk foto selama 1 tahun (asumsikan disimpan di AWS S3 tanpa index).
     c. Bandwidth keluar (egress) harian dalam satuan Gbps.

12. **Skenario 2: Melacak Insiden "Payment Timeout Misterius"**  
   Pengguna melaporkan bahwa saat promo diskon berlangsung, pembayaran mereka sering gagal dengan pesan `504 Gateway Timeout`. Metrik CPU server pembayaran menunjukkan penggunaan hanya 25%.
   - Bagaimana Anda menggunakan Distributed Tracing untuk menemukan akar penyebab masalah ini?
   - Sebutkan kemungkinan komponen yang menjadi bottleneck tersembunyi meskipun CPU masih rendah (misal: connection pool exhaustion, lock contention, atau third-party gateway throttle).

13. **Skenario 3: Desain Arsitektur Observabilitas FinTech Skala Enterprise**  
   Sebuah bank digital memproses 20.000 transaksi per detik dan memiliki 60 microservices di Kubernetes.
   - Rancang arsitektur pipeline observabilitas lengkap (OpenTelemetry Collector DaemonSet, Prometheus, Grafana, Loki/Elasticsearch, Jaeger/Tempo).
   - Tentukan strategi *Sampling Rate* dan *Data Masking* untuk mencegah nomor rekening dan CVV pelanggan bocor ke storage log.

---

## 🏆 Chapter Challenge: Observability & Capacity Blueprint for Global Streaming

### Problem Statement
Anda ditunjuk sebagai Principal Architect untuk merancang platform video on-demand global baru:
- Target: 20 Juta DAU global.
- Video playback rata-rata: 2 jam per pengguna per hari (Bitrate 1080p: 2.5 Mbps).
- Komponen backend: API Gateway, User Auth, Video Catalog Service, Recommendation Engine, Transcoding Workers, dan CDN Edge.

### Deliverables:
1. **Complete Capacity Estimation Sheet**:
   - Total egress bandwidth dari CDN ke pengguna (Gbps / Tbps).
   - Estimasi biaya bandwidth bulanan kasar.
   - Kebutuhan database catalog storage dan caching Redis.
2. **Full Observability Architecture**:
   - Diagram aliran metrik, log, dan trace dari Browser/Smart TV hingga ke Observability Cluster backend.
   - Definisi 3 Service Level Indicators (SLI) dan Service Level Objectives (SLO) kritis beserta batas Error Budget Burn Rate.
   - Skema W3C Traceparent injection pada request streaming video segment (HLS/DASH).
