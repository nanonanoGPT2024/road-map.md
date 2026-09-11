# BAB 08 — Quiz, Challenge, & Knowledge Check: Observabilitas Sistem

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Jelaskan perbedaan mendasar antara 3 pilar observabilitas: Metrics, Logs, dan Distributed Traces!
2. Mengapa tipe data `Counter` di Prometheus hanya diperbolehkan naik nilainya, dan apa yang terjadi jika instance aplikasi direstart?
3. Apa perbedaan antara tipe data `Histogram` dan `Summary` dalam Prometheus?
4. Mengapa Grafana Loki menggunakan strategi *no-text indexing* (hanya mengindeks label metadata), dan apa dampaknya terhadap konsumsi biaya storage?
5. Apa struktur dari header standar W3C `traceparent`, dan informasi apa saja yang dikandungnya?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Apa yang dimaksud dengan fenomena *High Cardinality Bomb* di Prometheus, dan mengapa menempatkan `user_id` atau `email` sebagai label metrik dapat menyebabkan server Prometheus OOM (*Out of Memory*)?
7. Tuliskan query PromQL untuk menghitung laju request per detik (RPS) rata-rata dalam jendela 5 menit dari metrik Counter `http_requests_total`.
8. Mengapa rata-rata (*average*) waktu respons seringkali menyesatkan dalam evaluasi performa sistem web, dan bagaimana cara menghitung $p99$ latency menggunakan PromQL?
9. Jelaskan bagaimana mekanisme *Inhibition Rules* di Alertmanager mencegah terjadinya *alert fatigue* (banjir notifikasi) saat switch router utama data center mengalami kerusakan!
10. Apa perbedaan antara *Head-Based Sampling* dan *Tail-Based Sampling* dalam arsitektur OpenTelemetry Collector?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Pada pukul 02:15 WIB, dashboard Grafana menunjukkan alert bahwa latensi API Gateway melonjak dari 45ms ke 3.2 detik. Menggunakan pendekatan 3 pilar observabilitas terpadu, jelaskan langkah demi langkah sistematis seorang SRE mendiagnosis akar masalah hingga ke baris kode spesifik!
12. **Skenario 2**: Perusahaan Anda memproses 80.000 request per detik. Mengaktifkan tracing 100% menyebabkan storage Jaeger penuh dalam 2 jam dan tagihan cloud melonjak $12.000. Strategi sampling dan filtering apa yang harus diterapkan pada OpenTelemetry Collector?
13. **Skenario 3**: Tim developer mengeluh bahwa query di Grafana Loki sering menghasilkan error `maximum active streams limit exceeded`. Periksa kemungkinan kesalahan dalam cara developer mengonfigurasi label stream Promtail dan berikan solusinya!

---

## B. Practical Chapter Challenge: Full-Stack Observability Pipeline

### Deskripsi Skenario
Rancang dan simulasikan arsitektur observabilitas enterprise terpadu untuk microservice Checkout:
1. **Instrumentasi Metrik Prometheus**:
   - Mengekspos endpoint `/metrics` dengan Counter untuk HTTP request status, Gauge untuk koneksi pool database aktif, dan Histogram untuk latensi HTTP.
2. **Alerting Rules PromQL**:
   - Buat rule alert: Jika HTTP 5xx error rate $> 1.5\%$ selama 3 menit atau Memory $> 85\%$, kirim alert `CRITICAL` ke PagerDuty.
3. **OpenTelemetry Context Propagation**:
   - Menghasilkan W3C `traceparent` header di API Gateway dan meneruskannya ke backend service.
   - Menginjeksikan `trace_id` ke dalam logger terpusat JSON.
4. **Grafana Unified View**:
   - Dokumentasikan rancangan visual di mana developer dapat mengklik data point di grafik metrik yang langsung membuka Jaeger trace dan Loki logs yang relevan.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 4 Tipe metrik Prometheus: Counter, Gauge, Histogram, Summary.
- [ ] Sintaks dasar PromQL: `rate()`, `histogram_quantile()`, `sum() by ()`.
- [ ] Arsitektur Alertmanager: Grouping, Deduplication, Inhibition, Silencing.
- [ ] Perbedaan arsitektur full-text ELK vs label-indexed Loki.
- [ ] Standar OpenTelemetry: Traces, Spans, Context Propagation via W3C Trace Context.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh fungsi matematika PromQL yang jarang digunakan (misal `deriv()`, `holt_winters()`).
- [ ] Konfigurasi internal kompleks storage engine TSDB block compactor.

### Saya Harus Bisa Melakukan:
- [ ] Mengekspos endpoint `/metrics` dari aplikasi Node.js / Go / Python.
- [ ] Mengonfigurasi file `prometheus.yml` untuk scraping dan alerting.
- [ ] Menganalisis latensi microservices menggunakan waterfall trace Gantt chart.
- [ ] Mem-filter log JSON menggunakan bahasa LogQL di Grafana Loki.

```text
Checklist Kesiapan BAB 08:
[ ] Memahami konsep 3 Pilar Observabilitas
[ ] Menjalankan hands-on Prometheus exporter & alert m01
[ ] Menjalankan hands-on OpenTelemetry tracing & logging m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
