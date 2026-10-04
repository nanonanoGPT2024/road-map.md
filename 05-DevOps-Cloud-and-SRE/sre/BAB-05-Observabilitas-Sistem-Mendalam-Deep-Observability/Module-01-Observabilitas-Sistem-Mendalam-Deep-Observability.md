# Module 01: Observabilitas Sistem Mendalam (Deep Observability)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Site Reliability Engineer (SRE) dan Cloud Platform Engineer diharapkan mampu:
- Mengonseptualisasikan dan mengimplementasikan kerangka kerja telemetri modern menggunakan *The Four Golden Signals* (Google SRE) serta mengombinasikan metodologi *USE* (Utilization, Saturation, Errors) dan *RED* (Rate, Errors, Duration).
- Merancang dan mengoperasikan pipeline telemetri terintegrasi berskala produksi menggunakan *OpenTelemetry SDK* dan *OpenTelemetry Collector* berbasis protokol OTLP (*OpenTelemetry Protocol*).
- Menguasai mekanisme propagasi konteks *Distributed Tracing* lintas batas jaringan mikroservis mengacu pada spesifikasi standar *W3C TraceContext* (`traceparent` dan `tracestate`).
- Mengidentifikasi, mengukur, dan memitigasi bahaya *High Cardinality Explosion* pada sistem metrik berbasis *Time-Series Database* (TSDB) melalui sanitasi dimensi data dan pemanfaatan *Exemplars* untuk menjembatani metrik histogram dan jejak *distributed trace*.

---

## 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- Arsitektur Jaringan Komputer & Protokol: TCP/IP, model HTTP/1.1 vs HTTP/2, gRPC/Protobuf, serta manipulasi *HTTP Request Headers*.
- Dasar-dasar Sistem Terdistribusi: Siklus hidup *request-response* mikroservis, *concurrency primitives*, serta model komputasi asynchronous/event-driven.
- Konsep dasar metrik dan log: Pemanfaatan Prometheus, PromQL, agregasi log (Fluentbit/Logstash/Vector), dan format log terstruktur (JSON).
- Bahasa Pemrograman: Python 3.10+ atau Go 1.20+ untuk membaca dan mengimplementasikan instrumentasi SDK aplikasi.

---

## 3. Concept
Observabilitas (*Observability*) adalah ukuran seberapa baik kondisi internal suatu sistem komputasi terdistribusi dapat disimpulkan (*inferred*) hanya berdasarkan output telemetri eksternalnya. Tidak seperti *monitoring* tradisional yang berfokus pada pertanyaan biner "*Apakah sistem menyala atau mati?*", observabilitas menjawab pertanyaan diagnostik multidimensi: "*Mengapa sistem berperilaku lambat pada 0.1% pengguna di region Asia Pasifik saat payload checkout menyertakan kupon promo tertentu?*"

Pilar observabilitas modern tidak lagi dipisahkan dalam silo terisolasi (Metrics, Logs, Traces), melainkan disatukan melalui *Semantic Conventions* dan korelasi data. Jembatan fundamental ini direalisasikan melalui:
1. **Context Propagation**: Menghubungkan setiap operasi terdistribusi secara kausal dari *entry point* hingga *database query*.
2. **Exemplars**: Mengikat sampel jejak (*trace-id*) spesifik langsung ke dalam *histogram bucket* metrik tanpa memicu ledakan dimensi (*cardinality*).

---

## 4. Why
Seiring transformasi monolit menjadi ratusan mikroservis yang di-deploy di atas klaster Kubernetes dinamis, masalah operasional bergeser dari kegagalan deterministik (*known-unknowns*) menjadi kegagalan stokastik (*unknown-unknowns*):
- **Tracing Silo Degradation**: Tanpa korelasi, tim SRE menghabiskan MTTR (*Mean Time To Resolution*) berjam-jam untuk mencocokkan *timestamp* log antar server yang berpotensi memiliki *clock skew*.
- **Metrics Explosion Outage**: Developer yang secara naif menyertakan `user_id` atau `email` ke dalam label Prometheus dapat melipatgandakan kebutuhan memori RAM TSDB hingga ratusan gigabyte dalam hitungan menit, melumpuhkan infrastruktur monitoring itu sendiri (*OOMKilled*).
- **Inadequate Signal Coverage**: Hanya memantau metrik infrastruktur (CPU/RAM) sering kali memberikan false-positive rasa aman (*all green*), padahal downstream database sedang mengalami *deadlock* antrean transaksi yang mengakibatkan 99% HTTP requests mengalami *timeout* (kegagalan memetakan sinyal *Saturation* dan *Latency P99*).

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 The Four Golden Signals
Didefinisikan dalam *Google SRE Book*, empat sinyal emas merupakan indikator kesehatan absolut dari sistem yang melayani trafik:
1. **Latency**: Waktu yang dibutuhkan untuk menyelesaikan suatu *request*. Harus dibedakan secara tegas antara *successful request latency* dan *failed request latency* (misal: HTTP 500 yang gagal instan dalam 2ms tidak boleh menurunkan persentil rata-rata latensi HTTP 200 yang membutuhkan 2000ms).
   - Metrik kunci: Percentile Latency ($P50, P95, P99$). Hindari penggunaan rata-rata (*arithmetic mean*).
2. **Traffic**: Ukuran kuantitatif beban permintaan pada sistem.
   - Contoh: HTTP *requests per second* (RPS), *transactions per second* (TPS), *concurrent streaming sessions*, atau *network I/O throughput*.
3. **Errors**: Laju permintaan yang mengalami kegagalan.
   - Diklasifikasikan menjadi *explicit errors* (HTTP 500 Internal Server Error) dan *implicit/semantic errors* (HTTP 200 dengan payload `{"status": "failed", "reason": "item_out_of_stock"}`).
4. **Saturation**: Seberapa "penuh" kapasitas sistem Anda, memetakan fraksi sumber daya yang paling dibatasi (*most constrained bottleneck*).
   - Menyoroti antrean sebelum sistem kolaps: *Thread pool wait queue depth*, *database connection pool exhaustion*, *Kubernetes CFS throttle percentage*.

### 5.2 USE vs RED Methods
Pendekatan diagnostik observabilitas dibedakan berdasarkan domain targetnya:
- **RED Method (Tom Wilkie)** berfokus pada arsitektur berbasis *Request/Service*:
  - **R**ate: Jumlah request per detik yang diproses.
  - **E**rrors: Jumlah request yang gagal per detik.
  - **D**uration: Waktu yang dihabiskan oleh request-request tersebut.
  *Kapan digunakan?* Sangat ideal untuk *microservice edge API*, HTTP REST, GraphQL, dan gRPC endpoints.
- **USE Method (Brendan Gregg)** berfokus pada arsitektur berbasis *Resource/Hardware*:
  - **U**tilization: Persentase waktu suatu resource sibuk melayani pekerjaan (misal: disk I/O 85%).
  - **S**aturation: Tingkat pekerjaan ekstra yang tidak dapat dilayani segera dan harus mengantre (misal: OS *load average* > jumlah CPU core, *run-queue length*).
  - **E**rrors: Jumlah kejadian galat perangkat/hardware (misal: *network interface dropped packets*, memory ECC errors).
  *Kapan digunakan?* Wajib digunakan saat menganalisis infrastruktur level rendah: Node Linux, CPU, Memory bus, Network Interface Cards (NIC), Storage disk arrays, JVM Heap.

### 5.3 OpenTelemetry Architecture (SDK & Collector)
OpenTelemetry (OTel) adalah standar industri *vendor-neutral* di bawah naungan Cloud Native Computing Foundation (CNCF).
- **OTel SDK**: Ditanamkan dalam kode aplikasi untuk *tracing*, pencatatan *metrics*, dan *logging context propagation*. Menggunakan *TracerProvider*, *MeterProvider*, dan *BatchSpanProcessor*.
- **OTel Collector**: Proxy independen berkinerja tinggi yang menerima telemetri melalui protokol OTLP (gRPC default port 4317, HTTP port 4318). Pipeline kolektor terbagi menjadi:
  - **Receivers**: Menerima data dalam berbagai format (OTLP, Jaeger, Zipkin, Prometheus pull).
  - **Processors**: Melakukan batching, memory limiting (*shedding load* jika RAM mendekati ambang batas batas aman), sampling, dan manipulasi atribut (menghapus PII/Personal Identifiable Information).
  - **Exporters**: Menerjemahkan format internal OpenTelemetry ke tujuan akhir backend penyimpanan (Prometheus, Jaeger, ClickHouse, AWS CloudWatch, Datadog).

```
[Aplikasi Microservice A]
       |
       | OTLP/gRPC (Port 4317)
       v
+-----------------------------------------------------------+
|                   OpenTelemetry Collector                 |
|  +-----------------------------------------------------+  |
|  | Receivers: otlp (grpc/http)                         |  |
|  +-----------------------------------------------------+  |
|                            |                              |
|  +-----------------------------------------------------+  |
|  | Processors: memory_limiter -> batch -> transform    |  |
|  +-----------------------------------------------------+  |
|                            |                              |
|  +-----------------------------------------------------+  |
|  | Exporters: prometheus (metrics) | otlp/tempo (traces) |  |
|  +-----------------------------------------------------+  |
+-----------------------------------------------------------+
        |                                     |
        v                                     v
 [Prometheus TSDB]                     [Grafana Tempo]
```

### 5.4 Context Propagation & W3C TraceContext
Untuk merekonstruksi alur eksekusi asinkron antar puluhan mikroservis, *distributed tracing* mengandalkan injeksi dan ekstraksi metadata HTTP headers. W3C TraceContext mendefinisikan dua header esensial:
1. `traceparent`: Berisi 4 field dengan delimitasi strip (`-`):
   - `version` (2 hex char): Saat ini selalu `00`.
   - `trace-id` (32 hex char / 16 byte): Identitas unik global untuk keseluruhan siklus hidup satu transaksi dari hulu ke hilir.
   - `parent-id` / `span-id` (16 hex char / 8 byte): Identitas unik segmen eksekusi pemanggil saat ini.
   - `trace-flags` (8-bit field, 2 hex char): Contoh `01` menandakan transaksi ini disampel (*recorded/sampled*).
   *Contoh representasi string:* `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
2. `tracestate`: Pasangan *key-value* buram (*opaque*) yang dirancang untuk membawa metadata spesifik vendor sistem pemantauan (misal: `congo=t61rcWkgMzE,rojo=00f067a1`).

### 5.5 High Cardinality Metrics Handling & Exemplars
- **High Cardinality**: Mengacu pada jumlah kombinasi nilai unik yang mungkin ada pada label/dimensi sebuah metrik. Jika sebuah metrik memiliki label:
  $$\text{Total Time Series} = \prod (\text{Jumlah Value Unik Label}_i)$$
  Memasukkan dimensi dengan kardinalitas tak terbatas (seperti `user_id`, `uuid`, `credit_card_number`, atau `ip_address`) akan melipatgandakan deret waktu (*time-series explosion*), mengakibatkan crash pada TSDB karena kebutuhan alokasi index memory yang eksponensial.
- **Exemplars**: Solusi mutakhir standar OpenMetrics/Prometheus. Memungkinkan kita menyisipkan referensi eksternal (berupa `TraceID` dan `SpanID`) ke dalam observasi metrik histogram tertentu, **tanpa** menciptakan label baru. TSDB menyimpan Exemplar di luar indeks time-series utama, sehingga query Grafana dapat langsung mengarahkan klik mouse dari lonjakan titik grafik metrik latensi $P99$ langsung ke *waterfall trace* transaksi bersangkutan.

---

## 6. How
Implementasi observabilitas mendalam dilakukan dengan langkah-langkah terstruktur berikut:
1. **Sanitasi Dimensi Metrik**: Identifikasi label metrik. Pertahankan kardinalitas rendah hingga menengah (contoh: `http_status_code`, `method`, `route_pattern` seperti `/api/v1/users/{id}` bukan `/api/v1/users/1298412`).
2. **Setup Instrumentasi OTel SDK**: Inisialisasi `TracerProvider` dan `MeterProvider` dengan konfigurasi *Resource* (misal: `service.name`, `deployment.environment`).
3. **Konfigurasi Context Injector/Extractor**: Gunakan `TraceContextTextMapPropagator` bawaan W3C untuk menyisipkan header pada klien HTTP keluar (*egress*) dan membaca header pada middleware server masuk (*ingress*).
4. **Deploy OTel Collector Pipeline**: Jalankan OTel Collector sebagai *Sidecar* (per Kubernetes Pod) atau *DaemonSet* untuk menangani *offloading* telemetri tanpa membebani thread aplikasi utama.
5. **Aktifkan Exemplars pada OpenMetrics Exporter**: Konfigurasikan penyimpanan TSDB (Prometheus `--enable-feature=exemplar-storage`) dan atur SDK untuk melampirkan context trace aktif saat mencatat metrik latensi.

---

## 7. Analogy
Bayangkan sistem mikroservis Anda sebagai sistem ekspedisi kargo internasional:
- **USE Method** seperti memeriksa kesehatan truk dan jalan raya: Berapa persen muatan truk terisi (*Utilization*), berapa banyak paket menumpuk di gudang menunggu giliran angkut (*Saturation*), dan apakah ada truk mogok di jalan (*Errors*).
- **RED Method** seperti mengukur kepuasan pelanggan terhadap layanan paket: Berapa paket yang dikirim per jam (*Rate*), berapa paket yang hilang/rusak (*Errors*), dan berapa lama waktu kirim rata-rata hingga paket sampai ke penerima (*Duration*).
- **W3C TraceContext** adalah nomor resi global (*Tracking Number*) yang ditempelkan di amplop terluar dokumen ekspedisi. Saat kurir A menyerahkan paket ke kurir B (lompatan lintas negara/jaringan), nomor resi utama tetap sama (`trace-id`), namun bukti serah terima lokal dicatat pada sub-resi (`span-id`).
- **High Cardinality vs Exemplar**: Menaruh nama setiap individu penerima paket pada papan informasi ringkasan status gudang akan membuat papan tersebut meledak karena kehabisan ruang (*High Cardinality Explosion*). Sebagai gantinya, manajer gudang hanya mencatat total berat paket pada rentang berat tertentu (*Histogram*), lalu menyematkan satu nomor resi referensi (*Exemplar*) di samping sampel paket yang sangat berat, sehingga jika perlu penyelidikan, staf tinggal mengecek nomor resi tersebut.

---

## 8. Diagram (ASCII)

```
        CLIENT / INGRESS
               |
        HTTP GET /checkout (No Context)
               v
+-------------------------------+
|       Service: API-GATEWAY    |
| - Generate TraceID: 4bf92...  |
| - SpanID: 00f06...            |
| - Record Metrik Latency       |
|   + Exemplar: TraceID         |
+-------------------------------+
               |
               | HTTP Request Headers:
               | traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
               v
+-------------------------------+
|     Service: PAYMENT-SERVICE  |
| - Extract W3C traceparent     |
| - Inherit TraceID: 4bf92...   |
| - Generate Child SpanID: c12..|
| - Query SQL Postgres          |
+-------------------------------+
               |
               | OTLP Batch Span Data
               v
+-------------------------------+
|     OpenTelemetry Collector   |
| - memory_limiter processor    |
| - batch processor             |
+-------------------------------+
       /                 \
      /                   \
     v                     v
[Prometheus TSDB]      [Grafana Tempo]
Metric:                Trace Waterfall:
http_duration_bucket   [API-GATEWAY: 250ms]
  |                     └── [PAYMENT-SERVICE: 230ms]
  └── Exemplar: 4bf92...        └── [Postgres SELECT: 180ms]
      (Klik untuk jump ke trace!)
```

---

## 9. Simple Example
Implementasi format header W3C TraceContext secara manual menggunakan cURL untuk menyimulasikan injeksi konteks ke upstream service:

```bash
# Injeksi context secara eksplisit ke microservice target
curl -X GET http://localhost:8080/api/v1/orders \
  -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" \
  -H "tracestate: vendor_internal_id=98765"
```
Jika microservice upstream telah dikonfigurasi dengan OpenTelemetry, seluruh log, span, dan downstream call yang dipicu oleh curl ini akan memiliki Trace ID yang sama (`4bf92f3577b34da6a3ce929d0e0e4736`), dan langsung disampel untuk dianalisis (`flags: 01`).

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### Konfigurasi Produksi OpenTelemetry Collector (`otel-collector-config.yaml`)
Konfigurasi ini mengamankan pipeline dari lonjakan memori tak terduga (*backpressure*), memproses *telemetry batches*, dan memetakan output traces dan metrics.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  # Melindungi Collector dari kegagalan kehabisan memori (OOM)
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  # Mengelompokkan spans dan metrics guna meningkatkan efisiensi I/O jaringan
  batch:
    send_batch_size: 1024
    timeout: 1s
    send_batch_max_size: 2048

  # Menghapus identitas sensitif (PII) dari atribut trace
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - delete_key(attributes, "http.request.header.authorization")
          - delete_key(attributes, "user.credit_card")

exporters:
  # Prometheus Exporter dengan dukungan Exemplars bawaan
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: sre_app
    send_timestamps: true
    enable_open_metrics: true

  # OTLP exporter untuk distributed tracing backend (Tempo / Jaeger)
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, transform, batch]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
  telemetry:
    logs:
      level: "info"
```

### Konfigurasi Prometheus untuk Menyimpan Exemplars (`prometheus.yml`)
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "otel-collector"
    scrape_interval: 5s
    # Wajib aktifkan OpenMetrics format untuk memproses exemplars
    metrics_path: "/metrics"
    static_configs:
      - targets: ["otel-collector:8889"]
```

---

## 11. Real World Example
Pada sebuah platform perbankan digital, terjadi anomali di mana 1.5% transaksi transfer dana mengalami timeout HTTP 504. Metrik CPU dan Memory server berada pada tingkat pemanfaatan rendah (25% CPU - USE Utilization false-safe).
1. **Analisis Sinyal Saturation**: Menggunakan USE method, tim SRE memantau metrik saturation antrean koneksi connection pool database (`hikaricp_pending_threads`). Terlihat lonjakan drastis dari 0 ke 50 (batas maksimum pool terlampaui).
2. **Pemanfaatan Metrik Latency & Exemplars**: Melalui dashboard Grafana, SRE melihat histogram latensi HTTP P99 melonjak hingga 15.000ms. SRE mengklik titik bucket $P99$ pada grafik metrik Prometheus, yang langsung membaca *Exemplar* yang melampirkan `TraceID: e3b0c44298fc1c149afbf4c8996fb924`.
3. **Distributed Trace Inspection**: SRE langsung diarahkan ke Jaeger/Tempo menggunakan TraceID tersebut. Jejak trace memperlihatkan rentang waktu 14.8 detik dihabiskan pada child span:
   `db.query: SELECT * FROM accounts WHERE user_id = ? FOR UPDATE;`
   Ditemukan akar masalah: Terjadi *distributed lock contention* pada baris akun yang sama akibat proses batch reconciliation paralel yang tidak terisolasi. Tanpa korelasi konteks metrik-ke-trace, diagnosis ini membutuhkan pembongkaran ribuan baris log transaksi secara manual.

---

## 12. Trade-offs

| Pendekatan Observabilitas | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) |
| :--- | :--- | :--- |
| **High Cardinality Metrics (Raw IDs)** | Granularitas absolut; analisis instan per pengguna di tingkat metrik. | Risiko *TSDB OOM Crash*, biaya memori RAM TSDB melonjak drastis, retensi data anjlok. |
| **Metrics Agregasi Rendah + Exemplars** | Performa TSDB stabil, biaya infrastruktur rendah, korelasi tetap instan ke *TraceID*. | Membutuhkan tracing backend terpisah (Tempo/Clickhouse) yang terpasang stabil. |
| **Full Distributed Tracing (100% Sampling)** | Tidak ada satupun transaksi bermasalah yang terlewatkan. | *Network overhead* masif, *storage cost* meledak, CPU penalty pada proses serialisasi OTLP. |
| **Head-based Probabilistic Sampling (e.g. 5%)** | Beban I/O rendah, biaya penyimpanan minimal, throughput aplikasi stabil. | Risiko anomali langka (*rare edge-case latency spikes*) tidak tercakup dalam sampel trace. |

---

## 13. When To Use
- Gunakan **The Four Golden Signals** sebagai baseline pembuatan dashboard operasional utama dan Service Level Objectives (SLO).
- Gunakan **RED Method** untuk memonitor komponen HTTP, gRPC microservices, dan API Gateways.
- Gunakan **USE Method** secara ketat pada pemantauan komponen komputasi dasar: Worker Node, VM Hypervisor, Database Engine Storage, serta Kafka Broker instances.
- Gunakan **Exemplars** ketika Anda memerlukan visibilitas granular hingga level ID transaksi tanpa merusak stabilitas cluster TSDB Anda.

---

## 14. When NOT To Use
- Jangan gunakan **Distributed Tracing dengan sampling 100%** di sistem high-throughput (misal: pemrosesan streaming 100.000 event/detik) tanpa *tail-based sampling processor*, karena tracing overhead akan menurunkan throughput aplikasi.
- Jangan gunakan **High Cardinality Labels** pada metrik Prometheus. Jika Anda memerlukan pencarian berbasis string bebas, gunakan *log aggregation engine* (seperti Grafana Loki atau Elasticsearch) atau atribut span tracing.
- Jangan gunakan **RED Method** untuk mengevaluasi kesehatan sistem penyimpanan murni (Disk SAN, Memory allocation) karena disk tidak memiliki konsep *request duration* semantik yang sama dengan *service endpoint*.

---

## 15. Common Mistakes
1. **Memasukkan ID Transaksi ke Label Metrik**:
   *Salah*: `http_requests_total{route="/orders", user_id="USR-109283", order_id="ORD-99381"}`
   *Benar*: `http_requests_total{route="/orders", status="200"}` + Sematkan `order_id` ke dalam Span Attributes dan Exemplars.
2. **Menghitung Latensi Agregat Gabungan**:
   Menggabungkan latensi error (misal: HTTP 503 yang langsung *fail fast* dalam 1ms) ke dalam metrik rata-rata latensi HTTP 200, sehingga menciptakan ilusi seolah-olah sistem berjalan sangat cepat padahal sedang mengalami degradasi parah.
3. **Mengabaikan Context Propagation pada Thread Asinkron**:
   Menjalankan goroutine atau background thread worker baru tanpa meneruskan `context.Context` (Go) atau `attach(context)` (Python/Java), yang mengakibatkan rantai *trace* putus di tengah jalan (*broken traces*).

---

## 16. Best Practices
1. **Standardize Semantic Conventions**: Gunakan konvensi penamaan standar OpenTelemetry (misal: `http.response.status_code`, `rpc.method`, `db.system`). Jangan menciptakan format nama field baru yang bersifat ad-hoc.
2. **Terapkan Tail-Based Sampling**: Gunakan OTel Collector tail-based sampling untuk menyimpan 100% trace yang menghasilkan galat (HTTP 5xx) atau yang melebihi batas durasi latensi tertentu (misal: durasi > 2 detik), dan hanya simpan 1% dari transaksi HTTP 200 normal.
3. **Enforce Memory Limiters**: Selalu pasang *processor memory_limiter* pada OTel Collector sebagai processor urutan pertama untuk mencegah Collector mengalami crash saat terjadi *traffic spikes*.

---

## 17. Troubleshooting

| Gejala Masalah | Investigasi Akar Masalah | Solusi Remediasi |
| :--- | :--- | :--- |
| **Trace terputus (Orphan Spans)** | Header W3C `traceparent` tidak diinjeksi ke panggilan HTTP keluar (*egress client*). | Pastikan HTTP Client di-instrumentasi dengan OTel SDK propagator wrapper. |
| **Prometheus OOM / Scrape Timeout** | Kardinalitas meledak (*metric explosion*) akibat penambahan label dinamis baru. | Gunakan Prometheus `scrape_series_limit` atau drop label berbahaya via collector `transform/metric_relabel_configs`. |
| **Exemplars tidak muncul di Grafana** | Output format scraper masih menggunakan OpenMetrics versi legacy, atau fitur belum aktif. | Tambahkan flag `--enable-feature=exemplar-storage` pada server Prometheus dan format header `Accept: application/openmetrics-text`. |
| **OTel Collector dropped data** | Buffer queue penuh karena downstream trace backend lambat menerima data. | Tingkatkan ukuran `send_batch_max_size` dan alokasikan kapasitas replika Collector (HPA). |

---

## 18. Exercise
1. Buat pemetaan arsitektural metrik untuk sistem *Online Payment Gateway*:
   - Tentukan minimal 2 metrik Golden Signals untuk setiap kategori (*Latency, Traffic, Errors, Saturation*).
   - Petakan metrik mana yang menggunakan pendekatan RED dan mana yang menggunakan USE.
2. Ambil sebuah string `traceparent` berikut:
   `00-a8b2c3d4e5f60718293a4b5c6d7e8f90-1122334455667788-01`
   Bedah dan jelaskan nilai serta fungsi dari masing-masing 4 segmen komponennya!

---

## 19. Challenge
Rancang sebuah dokumen arsitektur koleksi telemetri OTel Collector tingkat lanjut (*Advanced Architecture Blueprint*) yang mampu menangani beban **50.000 OTLP spans/detik** dengan persyaratan:
- Membuang atribut sensitif PII (`email`, `phone_number`, `token`).
- Memastikan rasio sampel 100% untuk seluruh span yang memiliki atribut `error=true` atau latensi $\ge 1500\text{ms}$.
- Melakukan sampling probabilistik 2% untuk transaksi pembayaran normal (sukses).
- Menjamin Collector tidak melampaui alokasi batas memori Pod sebesar 2 GiB. Tuliskan file konfigurasi pipeline OTel Collector yang merefleksikan arsitektur ini secara lengkap.

---

## 20. Summary
Observabilitas modern bukan sekadar mengumpulkan data dalam jumlah masif, melainkan menyusun arsitektur telemetri yang terhubung, efisien, dan memiliki daya analitik prediktif:
- **Golden Signals, RED, dan USE** membentuk kerangka metodologi pemantauan yang komprehensif, mencakup layanan mikroservis hingga hardware bare-metal.
- **OpenTelemetry** menyediakan standardisasi industri dalam instrumentasi kode dan normalisasi data telemetri.
- **Context Propagation W3C** menjamin keterlacakan kausal transaksi lintas batas sistem jaringan terdistribusi.
- **Exemplars** menjadi jembatan paling efisien untuk mengatasi paradoks *high cardinality*, memungkinkan korelasi presisi dari metrik ringkasan langsung menuju detail jejak (*traces*) mikro tanpa membahayakan keandalan infrastruktur monitoring SRE.