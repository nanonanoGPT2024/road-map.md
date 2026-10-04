# BAB 09: Quiz, Challenge, & Knowledge Check
**Fondasi Observabilitas: Metrics, Logs, & Traces**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Konseptual: Monitoring vs. Observabilitas**
   Secara arsitektural, jelaskan perbedaan fundamental antara paradigma *Traditional Monitoring* (berbasis deteksi *known-unknowns*) dengan *Observability* (berbasis eksplorasi *unknown-unknowns*). Mengapa instrumentasi sistem modern bergeser dari sekadar "memeriksa apakah sistem bekerja" menjadi "menyimpulkan kondisi internal sistem dari output eksternalnya"?

2. **Karakteristik Tiga Pilar Telemetri**
   Bandingkan tiga pilar observabilitas (*Metrics*, *Logs*, dan *Traces*) berdasarkan aspek:
   - Efisiensi komputasi & *storage footprint*.
   - Dimensi resolusi informasi kontekstual.
   - Kemampuan deteksi anomali real-time (*time-to-detect*) versus kapasitas investigasi akar masalah (*root cause analysis*).

3. **Model Transmisi Data: Push vs. Pull Engine**
   Analisis mekanisme transmisi metrik menggunakan model *Pull* (misal: Prometheus scraping) versus *Push* (misal: OpenTelemetry push/Datadog agent). Uraikan implikasi keduanya terhadap konfigurasi *network firewall*, *service discovery*, *load spike handling*, dan beban komputasi pada target *ephemeral workloads* (seperti serverless atau auto-scaling containers).

4. **Patologi Unstructured Logging & Paradigma Structured Logging**
   Mengapa pengiriman log berbasis string tak terstruktur (*plain text logs*) yang diproses menggunakan *regex parsing* di tingkat agregator (seperti Logstash atau Fluentd) dianggap sebagai *anti-pattern* fatal pada sistem berskala besar? Jelaskan bagaimana struktur data JSON/Logfmt mengeliminasi overhead CPU parsing dan memungkinkan *downstream analytics* yang deterministik.

5. **Anatomi dan Propagasi Konteks Distributed Tracing**
   Jelaskan komponen dasar sebuah distributed trace: `Trace ID`, `Span ID`, `Parent Span ID`, `Span Context`, dan `Baggage`. Bagaimana mekanisme *W3C Trace Context specification* merepresentasikan identitas trace tersebut melintasi batasan jaringan pada protokol HTTP (melalui header `traceparent` dan `tracestate`)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Bencana Ledakan Kardinalitas (*High-Cardinality Explosion*) pada TSDB**
   Sebuah tim menginstrumentasi metrik Counter: `http_requests_total` dengan label `method`, `path`, `status_code`, dan menyertakan `user_id` atau `order_id` unik sebagai label tambahan. Jelaskan secara mekanis apa yang terjadi di dalam memori Time Series Database (TSDB) (seperti Prometheus chunk index) ketika kardinalitas melonjak drastis, serta bagaimana fenomena ini memicu *Out-Of-Memory (OOM) CrashLoopBackOff*.

2. **Strategi Trace Sampling: Head-Based vs. Tail-Based**
   Bandingkan mekanisme internal *Head-based sampling* (keputusan sampling diambil di ingress/root span) dan *Tail-based sampling* (keputusan sampling diambil di level collector setelah trace selesai). Mengapa *Head-based sampling* kerap gagal menangkap trace bernilai tinggi (seperti trace yang berujung pada error HTTP 500 atau latency p99), dan apa trade-off arsitektural (CPU, memory buffer, latency) yang harus dibayar saat mengimplementasikan *Tail-based sampling* pada OpenTelemetry Collector?

3. **Mekanisme Backpressure pada Log Aggregation Pipeline**
   Ketika log consumer downstream (misal: Elasticsearch/Loki) mengalami *disk saturation* atau throttling, bagaimana *backpressure* merambat mundur melalui agent/shipper (misal: Vector, Fluent Bit) hingga ke level runtime container/aplikasi? Apa konsekuensinya terhadap memory buffer agent, konsumsi storage node (WAL/file-buffering), dan resiko terjadinya pemblokiran I/O pada runtime aplikasi (blocking stdout)?

4. **Metodologi Pengukuran: Golden Signals, RED, dan USE**
   Petakan perbedaan domain penerapan antara:
   - **Google SRE Golden Signals** (*Latency, Traffic, Errors, Saturation*)
   - **RED Method** (*Rate, Errors, Duration*)
   - **USE Method** (*Utilization, Saturation, Errors*)
   Tentukan metodologi mana yang wajib diterapkan pada arsitektur Microservices API layer vs. Infrastruktur Host/Hardware (CPU, Disk, Memory), dan berikan justifikasi teknisnya.

5. **Tracing Context Leakage & Thread Overhead**
   Pada bahasa pemrograman yang memanfaatkan asynchronous execution pool atau event loop non-blocking (misal: Java CompletableFuture, Node.js async/await, atau Go goroutines), bagaimana kebocoran konteks (*context propagation loss*) dapat terjadi? Bagaimana mekanisme passing context context-aware abstraction (seperti `context.Context` di Go) mencegah *orphan spans*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The High-Cardinality Midnight Outage
Saat peluncuran promosi midnight flash-sale, cluster Prometheus produksi mengalami *freeze*, tidak merespons query alerting rule, dan akhirnya mati akibat OOM. Analisis awal menunjukkan log: `allocating memory for new series chunks failed`. Tim SRE buta terhadap kondisi sistem, Grafana menampilkan status `N/A`, dan Alertmanager gagal memicu pager.
- **Pertanyaan Diagnostik:**
  1. Bagaimana langkah darurat untuk memulihkan monitoring tanpa menghapus data historis WAL yang ada di disk?
  2. Query metrik metadata apa yang dapat Anda jalankan via Prometheus TSDB CLI/API offline tool untuk mendeteksi label penyebab ledakan *series*?
  3. Desain kebijakan *metric sanitation/relabelling* pada level scraping configuration untuk mencegah metrik ber-kardinalitas tinggi masuk ke storage engine di masa mendatang.

### Skenario B: Distributed Trace Context Loss Melalui Asynchronous Broker
Sebuah transaksi perbankan melibatkan alur mikroservis: `API Gateway` -> `Order Service` -> `Kafka Broker` -> `Payment Service` -> `Notification Service`. Laporan pengguna menunjukkan transaksi checkout memakan waktu 15 detik, tetapi distributed tracing di Jaeger hanya menampilkan trace dari `API Gateway` ke `Order Service` dengan durasi 40 milidetik, lalu terputus. Span untuk `Payment Service` dan `Notification Service` berdiri sendiri-sendiri dengan `Trace ID` baru.
- **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat di mana titik kegagalan propagasi konteks terjadi dalam arsitektur asinkronus berbasis broker tersebut.
  2. Bagaimana cara menginjeksi (`inject`) dan mengekstrak (`extract`) metadata OpenTelemetry context ke dalam atribut/header record Kafka secara manual maupun otomatis?
  3. Bagaimana memodelkan hubungan span antara operasi *produce* message dan operasi *consume/process* message menggunakan tipe span link (`SpanLink`) versus parent-child span?

### Skenario C: Disk Exhaustion & Cascade Failure pada Log Aggregator
Sebuah bug pada production release menyebabkan puluhan mikroservis mencetak stack trace error Java ribuan kali per detik secara berulang. Log ingestion pipeline (Elasticsearch/OpenSearch) mencapai *read-only watermark* (95% disk used), menyebabkan indexing terhenti. Log forwarder agent (Fluent Bit) di setiap node Kubernetes mulai menimbun *in-memory chunk buffer*, memicu kegagalan OOM pada pod daemonset dan membocorkan disk node worker karena file `/var/log/containers/*` terus membengkak tanpa ter-purge.
- **Pertanyaan Diagnostik:**
  1. Bagaimana urutan mitigasi prioritas untuk menyelamatkan host worker nodes dari risiko *disk pressure eviction* akibat penumpukan file log lokal?
  2. Konfigurasi mitigasi apa yang wajib dipasang pada Fluent Bit (`Mem_Buf_Limit`, `storage.type`, `storage.max_chunks_up`) untuk melindungi diri dari *cascading failure* ketika upstream ingestion mati?
  3. Rancang strategi arsitektur log filtering dan rate-limiting dinamis pada level Collector tanpa perlu merestart pod mikroservis backend.

---

## 4. Chapter Challenge

**Tantangan Praktis: End-to-End Unified Observability Pipeline Implementation**

### Problem
Organisasi Anda memiliki sistem microservice sederhana berbasis dua service: `frontend-proxy` (Go) dan `checkout-engine` (Node.js/Python). Saat ini, tim mengalami kesulitan mengkorelasikan kelambatan transaksi karena metrik, log, dan trace berada di silo terpisah tanpa korelasi langsung. Anda diminta membangun fondasi observabilitas terpadu menggunakan standar **OpenTelemetry (OTel)**.

### Requirements
1. **Instrumentasi Kode Terpadu:**
   - Implementasikan *Distributed Tracing* antar kedua service melalui HTTP injection/extraction (W3C format).
   - Pastikan setiap structured log record (JSON) yang di-generate oleh service otomatis menyuntikkan `trace_id` dan `span_id` dari konteks tracing aktif secara deterministik.
2. **OpenTelemetry Collector Architecture:**
   - Deploy OpenTelemetry Collector yang menerima OTLP telemetry data (gRPC/HTTP).
   - Konfigurasikan OTel pipeline untuk:
     - Mengirim metrik ke Prometheus (atau memaparkan prometheus scrape endpoint).
     - Mengirim traces ke Jaeger / Grafana Tempo.
     - Mengirim logs ke Grafana Loki / Elasticsearch.
   - Pasang processor batching (`batch`) dan resource attribute processor (`resource`) untuk menyuntikkan environment name (`production`).
3. **Dashboards & Korelasi Telemetri (Grafana):**
   - Buat satu Unified Dashboard di Grafana yang menampilkan metrik RED (Rate, Errors, Duration).
   - Terapkan fitur **Trace-to-Logs** dan **Logs-to-Trace**: Dari baris log di dashboard, engineer dapat mengklik tombol yang langsung membuka distributed trace yang bersangkutan di Tempo, dan sebaliknya, dari Span Tempo dapat melihat log spesifik pada rentang waktu span tersebut.

### Constraints
- Collector tidak boleh mengonsumsi memori lebih dari `256MiB` (gunakan memory limiter processor).
- Terapkan *tail sampling* sederhana pada Collector atau instrumentasi log filtering: Log dengan status level `DEBUG` harus didrop di Collector jika berada di environment produksi, kecuali terjadi status code `>= 500`.
- Dilarang keras menggunakan proprietary agent (wajib murni Open Source: OpenTelemetry, Prometheus, Tempo, Loki, Grafana).

### Expected Output
1. File konfigurasi `docker-compose.yml` atau Kubernetes manifests yang mendemonstrasikan sistem end-to-end yang dapat di-spin up dengan sekali perintah (`docker compose up`).
2. File konfigurasi `otel-collector-config.yaml` yang valid dengan pipeline lengkap (receivers, processors, exporters).
3. Kode instrumentasi minimal kedua service yang membuktikan propagasi context HTTP header dan structured logging injection.
4. Bukti tangkapan layar / log output / trace UI yang memverifikasi bahwa `trace_id` pada structured logs identik dengan `trace_id` pada Jaeger/Tempo UI untuk satu siklus request checkout yang sama.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara White-box Monitoring dan Black-box Monitoring.
- [ ] Anatomi metrik TSDB: Metric Name, Labels/Tags, Timestamp, dan Sample Value.
- [ ] Tipe data metrik fundamental: *Counter*, *Gauge*, *Histogram*, dan *Summary*.
- [ ] Dampak matematika komputasi quantiles/percentiles (p50, p95, p99) pada Histogram vs Summary di arsitektur terdistribusi.
- [ ] Mengapa rata-rata (*average*) adalah metrik yang menyesatkan untuk menganalisis performa latensi jaringan.
- [ ] Konsep W3C TraceContext: Header `traceparent` (version, trace-id, parent-id/span-id, trace-flags).
- [ ] Arsitektur OpenTelemetry: OTel API vs. OTel SDK vs. OTel Collector.
- [ ] Perbedaan dan konsekuensi performa antara synchronous logging vs. asynchronous logging.
- [ ] Definisi Cardinality dalam database analitik dan implikasinya terhadap performa TSDB.

### Saya tidak perlu menghafal:
- [ ] Sintaksis biner internal dari storage engine block format Prometheus (misal: encoding XOR Gorilla compression).
- [ ] Seluruh spesifikasi spec schema OpenTelemetry Semantic Conventions secara detail di luar atribut HTTP/Database standar.
- [ ] Format binary payload gRPC/Protobuf level byte dari protokol OTLP.
- [ ] Semua konfigurasi flags tuning internal database Loki, Tempo, atau Elasticsearch.

### Saya harus bisa melakukan:
- [ ] Menulis konfigurasi `otel-collector-config.yaml` fungsional yang mencakup `receivers`, `processors`, `exporters`, dan `pipelines`.
- [ ] Menganalisis dan memitigasi high cardinality label pada Prometheus menggunakan relabelling rules (`metric_relabel_configs`).
- [ ] Mengonfigurasi logger aplikasi (misal: Zap, Winston, Logback) untuk memproduksi format structured JSON secara otomatis.
- [ ] Melakukan korelasi manual antara baris log dan trace span menggunakan `TraceID` melalui interface Grafana / Log viewer.
- [ ] Mengidentifikasi titik bottleneck microservice (network delay vs computational execution) dengan membaca trace waterfall chart/Gantt chart.
- [ ] Menggunakan cURL untuk menginspeksi dan memverifikasi propagasi header `traceparent` pada incoming dan outgoing HTTP requests.