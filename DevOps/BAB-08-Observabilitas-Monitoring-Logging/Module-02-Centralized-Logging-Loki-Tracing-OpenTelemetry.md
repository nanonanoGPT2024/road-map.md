# Module 02: Centralized Logging (Loki, ELK) & Distributed Tracing (OpenTelemetry, Jaeger)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami pilar kedua (**Logs**) dan pilar ketiga (**Distributed Traces**) dalam arsitektur observabilitas modern.
- Membandingkan trade-off arsitektur logging: **Elasticsearch/OpenSearch (ELK)** dengan pengindeksan teks penuh vs **Grafana Loki** dengan pengindeksan berbasis label ringan.
- Mengonfigurasi agen pengirim log (*Log Shippers*) seperti **Promtail** dan **Fluent Bit** untuk mem-parsing format structured JSON.
- Menulis query log analitik menggunakan bahasa **LogQL**.
- Memahami konsep **Distributed Tracing** standar industri menggunakan **OpenTelemetry (OTel)**: *Traces*, *Spans*, *Parent/Child Spans*, dan *Context Propagation* (`traceparent`).
- Melakukan korelasi data tiga pilar (*Correlated Observability*): dari Metrik Grafana -> klik Trace Jaeger/Tempo -> loncat ke Log Loki dengan `trace_id` yang sama.

---

## 2. Prerequisite
- Memahami konsep dasar HTTP headers dan protokol REST/gRPC (BAB 02).
- Memahami metrik Prometheus dan visualisasi Grafana (BAB 08 Module 01).
- Pemahaman dasar tentang arsitektur Microservices di mana satu transaksi pengguna melewati banyak service independen.

---

## 3. Concept
Tiga pilar observabilitas saling melengkapi untuk menjawab pertanyaan yang berbeda saat insiden terjadi:
1. **Metrics (Prometheus)**: Menjawab pertanyaan *"Kapan ada masalah dan seberapa parah dampaknya?"* (contoh: lonjakan HTTP 500 error).
2. **Distributed Tracing (OpenTelemetry)**: Menjawab pertanyaan *"Di mana letak bottleneck atau titik kegagalan dalam rantai microservices?"* (contoh: Service Keranjang -> Service Checkout -> Service Pembayaran -> Database Query memakan 4.8 detik).
3. **Logs (Loki / ELK)**: Menjawab pertanyaan *"Mengapa kegagalan itu terjadi?"* (contoh: NullPointerException atau timeout koneksi database di baris kode tertentu).

```
   [ User Request ]
         │
         ▼ (Injects HTTP Header: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
   ┌───────────────┐
   │ API Gateway   │ ──(Ship Log with trace_id)──> [ Grafana Loki ]
   └───────┬───────┘                                      ▲
           │ (Propagate Trace Context)                    │ Correlate via
           ▼                                              │ trace_id
   ┌───────────────┐                                      │
   │ Payment API   │ ──(OTLP Spans)──> [ OTel Collector ] ┼──> [ Jaeger / Tempo ]
   └───────┬───────┘                          │           │
           │                                  ▼           │
           ▼                           [ Prometheus ] ────┘
   ┌───────────────┐                    (Metrics)
   │ Database / DB │
   └───────────────┘
```

---

## 4. Why?
1. **Kegagalan Menemukan Error di Lingkungan Microservices**: Jika aplikasi monolitik crash, Anda cukup membuka satu file log server (`tail -f /var/log/app.log`). Dalam arsitektur microservices dengan 80 container tersebar di 10 worker node, mencari log manual adalah hal yang mustahil tanpa centralized logging.
2. **Konteks Asynchronous**: Transaksi pengguna melibatkan pemanggilan REST API, antrean Kafka, background job worker, dan query SQL. Distributed tracing merekatkan seluruh potongan terpisah ini menjadi satu alur linier utuh.
3. **Efisiensi Biaya Storage**: Sistem logging terdahulu (seperti Elasticsearch) mengindeks setiap kata dalam setiap baris log, yang membutuhkan RAM dan disk storage raksasa (seringkali biaya log melebihi biaya komputasi aplikasi itu sendiri). Grafana Loki memecahkan masalah ini dengan hanya mengindeks label metadata (serupa Prometheus), memangkas biaya storage hingga 80%.

---

## 5. What?
Komponen arsitektur Logging & Tracing modern:
- **Fluent Bit / Promtail**: Daemon/DaemonSet ringan di setiap server yang membaca file log container di `/var/log/pods/`, mengekstrak metadata JSON, dan mem-push log ke server penyimpanan.
- **Grafana Loki**: Mesin penyimpanan log horizontal yang dirancang khusus untuk bekerja harmonis dengan Prometheus. Tidak mengindeks isi teks mentah, melainkan mengelompokkan log dalam stream berdasarkan label (`app`, `environment`, `namespace`).
- **OpenTelemetry (OTel)**: Standar terbuka netral vendor dari CNCF untuk API, SDK, dan tooling guna menghasilkan, mengumpulkan, dan mengekspor data telemetri (Metrics, Logs, Traces).
- **Jaeger / Grafana Tempo**: Backend terdistribusi untuk menyimpan, mengindeks, dan menampilkan visualisasi grafik gantt chart dari rentang durasi waktu (*spans*) distributed trace.

---

## 6. How?
Alur kerja Distributed Tracing & Logging Terpadu:
1. **Ingress Gateway**: Permintaan HTTP masuk ke API Gateway. Middleware OpenTelemetry membuat `trace_id` unik sepanjang 32 karakter heksadesimal (misal `4bf92f3577b34da6a3ce929d0e0e4736`) dan `span_id` (16 karakter).
2. **W3C Context Propagation**: Saat API Gateway memanggil microservice Order melalui HTTP, client HTTP menyuntikkan header standar W3C:
   `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`.
3. **Span Hierarchy**: Service Order mengekstrak header tersebut, menjadikannya parent, dan membuat child span baru untuk query database PostgreSQL.
4. **Structured Log Injection**: Logger aplikasi (Pino, Winston, Zap, Logback) secara otomatis menyertakan atribut `"trace_id"` dan `"span_id"` pada setiap baris log JSON.
5. **OTLP Export**: SDK OpenTelemetry mengirimkan data span via protokol gRPC/HTTP OTLP ke **OpenTelemetry Collector**, yang kemudian meneruskannya ke Jaeger/Tempo.
6. **Grafana Trace-to-Logs Jump**: Insinyur yang melihat span error di Jaeger/Tempo dapat mengklik tombol *"Explore in Loki"* untuk langsung melihat semua baris log dari seluruh container yang memiliki `trace_id` tersebut.

---

## 7. Analogy
Bayangkan **Distributed Tracing** seperti **Nomor Resi Pengiriman Paket Kurir E-Commerce**:
- Anda membeli barang online dan menerima satu **Nomor Resi Unik** (`trace_id`).
- Barang melewati beberapa pos pemeriksaan: Gudang Penjual (`span_1`), Pusat Sortir Kota A (`span_2`), Penerbangan Kargo (`span_3`), Kurir Motor Lokal (`span_4`).
- Setiap pos pemeriksaan mencatat stempel waktu kedatangan dan keberangkatan (`start_time`, `end_time`).
- Jika paket tertunda 3 hari, Anda tidak perlu menelpon semua gudang di seluruh pulau; Anda cukup memasukkan nomor resi, dan sistem langsung menampilkan bahwa paket tertahan di pos pemeriksaan `span_3` karena cuaca buruk (**Log error di Loki**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               DISTRIBUTED TRACE (WATERFALL GANTT CHART VISUALIZATION)             |
+-----------------------------------------------------------------------------------+

 Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736  (Total Duration: 480ms)

 [1] API Gateway: POST /checkout ────────────────────────────────────────── [480ms]
      │
      ├── [2] Auth Service: Verify JWT ──── [35ms]
      │
      ├── [3] Order Service: Create Pending Order ───────────────────────── [420ms]
      │        │
      │        ├── [4] Postgres: INSERT INTO orders ── [25ms]
      │        │
      │        └── [5] Payment Service: Process Stripe Charge ──────────── [370ms]
      │                 │
      │                 └── [6] External Stripe API: POST /v1/charges ─── [350ms]
      │                          ▲
      │                          └── [Bottleneck Terdeteksi Disini!]
      │
      └── [7] Kafka Producer: Emit 'order_created' ── [15ms]
```

---

## 9. Simple Example: Format Structured JSON Log
Standard output log aplikasi yang siap di-scrape oleh Fluent Bit / Promtail:

```json
{
  "timestamp": "2026-09-11T04:20:15.342Z",
  "level": "error",
  "service": "payment-api",
  "environment": "production",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "message": "Payment gateway timeout after 5000ms",
  "error": {
    "code": "GATEWAY_TIMEOUT",
    "stack": "TimeoutError: Connection timed out at StripeClient.charge (/app/src/stripe.js:84)"
  },
  "http": {
    "method": "POST",
    "route": "/api/v1/charge",
    "status_code": 504,
    "duration_ms": 5002
  }
}
```

---

## 10. Practical Example: Query LogQL pada Grafana Loki
Bahasa query LogQL menggabungkan filter stream label (mirip PromQL) dengan regex parsing teks:

```logql
# 1. Menampilkan seluruh log berlevel 'error' dari container 'payment-api' di namespace 'production'
{namespace="production", app="payment-api"} |= "error"

# 2. Mem-parsing baris log berformat JSON dan memfilter HTTP status code 500 ke atas
{app="payment-api"} | json | http_status_code >= 500

# 3. Menghitung laju (rate) error per-menit untuk dibuatkan grafik panel di Grafana
sum(rate({app="payment-api"} |= "error" [5m])) by (pod)

# 4. Mencari seluruh log dari semua service yang memiliki trace_id spesifik
{namespace="production"} | json | trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
```

---

## 11. Real World Example: Mereduksi Biaya Logging Perusahaan ($50K -> $8K/Bulan)
Sebuah perusahaan e-commerce skala unicorn sebelumnya menggunakan Elasticsearch (ELK) untuk menampung 4 Terabyte log per hari.
- **Masalah**: Biaya cluster Elasticsearch membengkak hingga $50.000 per bulan karena Elasticsearch membuat inverted index untuk setiap kata dan tanda baca di seluruh log, membutuhkan RAM berkapasitas ratusan Gigabyte.
- **Solusi DevOps**:
  1. Migrasi dari ELK ke **Grafana Loki**.
  2. Log disimpan dalam format compressed chunks di object storage murah (AWS S3) dengan retention policy 30 hari.
  3. Memasang **OpenTelemetry** untuk distributed tracing, sehingga developer tidak perlu mencatat log string panjang di setiap langkah eksekusi; cukup rekam data numerik dan metadata dalam Span.
- **Hasil**: Biaya bulanan turun drastis menjadi $8.000 (hemat 84%), dan waktu troubleshooting insiden berkurang karena developer langsung mengklik trace waterfall alih-alih melakukan grep teks manual di ribuan file log.

---

## 12. Trade-offs

| Aspek | Elasticsearch / OpenSearch (ELK) | Grafana Loki |
|---|---|---|
| **Indexing Strategy** | Full-text inverted index pada seluruh pesan log | Hanya mengindeks label metadata (mirip Prometheus) |
| **Konsumsi Storage & RAM** | Sangat Tinggi (Ukuran indeks bisa 1.5x ukuran data mentah) | Sangat Rendah (Penyimpanan chunk terkompresi di S3) |
| **Kecepatan Text Search Bebas** | Sangat Cepat untuk pencarian kata arbitrary | Sedang-Lambat untuk pencarian teks tanpa filter label |
| **Integrasi Ekosistem** | Kibana, Logstash, Beats | Grafana, Prometheus, Tempo (Satu panel terpadu) |
| **Operasional Maintenance** | Kompleks (Sharding, JVM heap tuning, rollover index) | Sederhana (Stateless microservices architecture) |

---

## 13. When To Use
- **Centralized Logging (Loki)**: Seluruh aplikasi cloud-native yang berjalan di Kubernetes untuk diagnosa error dan audit event.
- **Distributed Tracing (OpenTelemetry + Tempo/Jaeger)**: Arsitektur microservices atau arsitektur serverless di mana satu request pengguna melewati $>2$ network hops atau sistem perpesanan asinkron (Kafka/RabbitMQ).

---

## 14. When NOT To Use
- Jangan gunakan Distributed Tracing pada aplikasi monolitik sederhana yang berjalan di single server virtual machine (cukup gunakan APM lokal / built-in profiler sederhana).
- Jangan mencatat payload data sensitif pengguna (password, nomor kartu kredit, CVV, token autentikasi) ke dalam log atau span tags (pelanggaran kepatuhan PCI-DSS & GDPR).

---

## 15. Common Mistakes
1. **Unstructured Plain Text Logs**: Mencetak log seperti `console.log("user logged in " + userId + " status ok")`. Log seperti ini sangat lambat di-parse, tidak bisa difilter secara efisien di LogQL, dan sulit diekstrak ke metrik. Selalu gunakan format Structured JSON.
2. **100% Trace Sampling di High-Throughput Production**: Menyetel sampling rate OpenTelemetry pada angka 100% di sistem dengan 50.000 RPS. Ini akan membebani jaringan dan storage tracing hingga puluhan Gigabyte per menit. Gunakan **probabilistic / head-based sampling** (misal 1% sampai 5%) atau **tail-based sampling** (hanya simpan trace yang lambat $>1\text{s}$ atau yang menghasilkan error).
3. **Kehilangan Trace Context pada Async Thread / Goroutine**: Lupa meneruskan objek `context.Context` (di Go) atau `AsyncLocalStorage` (di Node.js) saat membuat thread background baru, menyebabkan span terputus dari parent trace.

---

## 16. Best Practices
### Must Have
- Cetak seluruh log ke `stdout` dan `stderr` dalam format JSON (sesuai *Twelve-Factor App principle*). Biarkan daemon collector node yang mengurus pengiriman log.
- Sertakan atribut `trace_id` dan `span_id` pada setiap level log error dan warning.
- Standarkan nama kunci JSON log: `timestamp`, `level`, `message`, `service`, `trace_id`.

### Recommended
- Gunakan OpenTelemetry Collector sebagai layer gateway perantara antara aplikasi dan storage backend (Jaeger, Tempo, Datadog), sehingga aplikasi tidak terikat pada satu vendor tertentu.
- Pasang masking filter otomatis untuk membersihkan PII (*Personally Identifiable Information*) sebelum log dikirim ke Loki.

### Advanced
- Terapkan Tail-Based Sampling pada OpenTelemetry Collector: Pertahankan 100% trace untuk request yang mengembalikan status code 5xx atau latensi di atas batas toleransi SLO.

---

## 17. Troubleshooting
- **Masalah**: OpenTelemetry trace terputus di tengah jalan (hanya terlihat span service frontend, span service backend hilang).
  - *Penyebab*: Header HTTP `traceparent` di-strip oleh Nginx reverse proxy atau API gateway yang salah konfigurasi.
  - *Solusi*: Pastikan reverse proxy mengizinkan dan mem-forward header `traceparent` dan `tracestate`.
- **Masalah**: LogQL query menghasilkan error `entry with timestamp too old` di Loki.
  - *Solusi*: Sinkronkan waktu seluruh server worker node menggunakan daemon NTP (`chronyd`). Jam server yang melenceng $>1$ detik akan ditolak oleh Loki chunk builder.

---

## 18. Exercise
1. Tulis skrip konfigurasi Fluent Bit parser untuk membedah baris log Nginx standar ke dalam format field JSON (`client_ip`, `request_method`, `path`, `status_code`, `response_time`).
2. Tulis query LogQL untuk menghitung persentase error rate dari stream log Apache: membagi baris yang mengandung `"status": 500` dengan total seluruh baris log.

---

## 19. Challenge
Implementasikan pipeline observabilitas end-to-end:
- Buat 2 microservices: `Order Service` dan `Inventory Service`.
- Instrumentasi kedua service menggunakan OpenTelemetry SDK untuk saling bertukar header W3C Trace Context.
- Konfigurasikan logger agar secara otomatis menyuntikkan `trace_id` aktif ke dalam log JSON.
- Buktikan bahwa saat terjadi kegagalan di `Inventory Service`, Anda dapat melacak rantai eksekusi dari ID transaksi tunggal di sistem tracing dan menemukan baris log penyebab error di sistem logging.

---

## 20. Summary
- **Logs** memberikan rincian mendalam tentang *mengapa* sistem gagal; **Traces** memetakan *di mana* letak latensi antar-microservices terjadi.
- **Grafana Loki** menawarkan efisiensi biaya penyimpanan yang jauh lebih hemat dibanding Elasticsearch tradisional dengan strategi no-text indexing.
- **OpenTelemetry** adalah standar universal terbuka untuk instrumentasi telemetri tanpa vendor lock-in.
- Korelasi ketiga pilar melalui `trace_id` adalah puncak kematangan observabilitas modern untuk mempercepat MTTR (*Mean Time to Resolution*).
