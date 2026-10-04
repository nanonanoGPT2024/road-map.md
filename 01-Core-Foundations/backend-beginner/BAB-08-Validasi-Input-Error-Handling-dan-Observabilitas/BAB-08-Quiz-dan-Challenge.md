# BAB 08: Quiz, Challenge, & Knowledge Check
**Validasi Input, Error Handling, & Observabilitas**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pemisahan Layer Validasi (Transport Boundary vs Domain Model)
Mengapa memvalidasi format data (misalnya: *syntactic validation* seperti tipe data, panjang string, dan format regex) pada layer Transport/Controller saja belum cukup untuk menjamin keabsahan data sistem? Jelaskan perbedaan mendasar antara *Syntactic Validation* di layer boundary dengan *Semantic/Invariant Validation* di layer Domain, serta berikan contoh risiko inkonsistensi data jika keduanya tidak dipisahkan secara arsitektural.

### Soal 1.2: Paradigma Fail-Fast vs Fail-Safe pada Error Handling
Dalam perancangan backend berkinerja tinggi, jelaskan implementasi filosofi *Fail-Fast* versus *Fail-Safe*. Pada layer mana sistem harus menghentikan eksekusi secara instan (*Fail-Fast*) saat mendeteksi anomali, dan pada layer mana sistem harus menerapkan toleransi kesalahan (*Fail-Safe* / *Graceful Degradation*) agar tidak memicu *cascading failure* ke seluruh sistem?

### Soal 1.3: Evolusi Logging: Unstructured vs Structured Contextual Logging
Banyak sistem warisan (*legacy*) menggunakan penulisan log berbasis format teks bebas (contoh: `logger.error("User " + userId + " failed to pay order " + orderId)`). Analisis mengapa pendekatan ini menjadi *bottleneck* kritis dalam infrastruktur modern yang menggunakan Log Aggregator (seperti Elasticsearch, Loki, atau Datadog). Bagaimana *Structured Logging* berbasis JSON dengan *key-value pairs* menyelesaikan masalah indexing, parsing CPU overhead, dan querying skala besar?

### Soal 1.4: Dekonstruksi Standar RFC 7807 (Problem Details for HTTP APIs)
Mengapa mengembalikan response error HTTP kustom seperti `{"status": false, "message": "Something went wrong"}` dianggap sebagai *anti-pattern* pada desain API enterprise? Jelaskan anatomi dari spesifikasi **RFC 7807** (`type`, `title`, `status`, `detail`, `instance`, serta *extension members*) dan bagaimana standarisasi ini mempermudah otomatisasi penanganan error di sisi API consumer/klien.

### Soal 1.5: Tiga Pilar Observabilitas & Context Propagation
Observabilitas bertumpu pada tiga pilar utama: **Metrics**, **Logs**, dan **Traces**. Jelaskan trade-off konsumsi resource (CPU, memory, storage) di antara ketiga pilar tersebut. Bagaimana mekanisme *Context Propagation* (seperti spesifikasi W3C Trace Context: `traceparent` dan `tracestate`) memungkinkan korelasi deterministik antara entri log individual, lonjakan metrik, dan visualisasi distributed trace di arsitektur microservices?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Leak Akibat Unhandled Rejections & Dangling Event Listeners
Pada runtime asynchronous berbasis Event Loop (seperti Node.js) atau Thread Pool (seperti Java/Go), bagaimana sebuah *unhandled exception* atau *unhandled promise rejection* di dalam background worker dapat menyebabkan *memory leak* dan resource exhaustion secara perlahan tanpa langsung mematikan (*crash*) proses utama? Jelaskan siklus hidup memori objek yang tersangkut dalam *rejected state* yang tidak dibersihkan oleh garbage collector.

### Soal 2.2: Transient vs Terminal Errors & Strategi Mitigasi Jitter
Di sebuah layer HTTP/gRPC Client yang memanggil third-party service, klasifikasikan skenario error mana yang tergolong sebagai **Transient Error** (sementara) dan mana yang tergolong sebagai **Terminal Error** (permanen). Mengapa menerapkan retry langsung (*immediate retry*) secara masif saat terjadi downstream network timeout justru menciptakan fenomena *Retry Storm* (Thundering Herd)? Bagaimana formula *Exponential Backoff with Full Jitter* memitigasi problem ini di level algoritma?

### Soal 2.3: Metrik TSDB: Fenomena High-Cardinality Explosion
Sebuah tim backend menambahkan middleware metrik Prometheus untuk menghitung total HTTP request dengan format:
`http_requests_total{method="POST", path="/api/v1/orders/{order_id}", status="200"}`.
Dalam waktu kurang dari 6 jam pasca-deploy di production, Time-Series Database (TSDB) kehabisan RAM dan mengalami *Out-Of-Memory* (OOM) crash loop. Lakukan analisis akar masalah internal (*root-cause*) pada struktur indexing TSDB terkait *high-cardinality labels*, dan berikan solusi perbaikan label metrik yang tepat secara arsitektural.

### Soal 2.4: Log Injection (CWE-117) dan Strategi Masking PII
Jelaskan vektor serangan *Log Injection* (*Carriage Return Line Feed* / CRLF injection) pada sistem logging backend yang tidak melakukan sanitasi input string dari user. Selain eksploitasi integritas log, bagaimana mekanisme performa scrubbing/masking data sensitif (Personally Identifiable Information - PII seperti nomor kartu kredit, NIK, password) harus diterapkan di layer middleware/interceptor tanpa membebani runtime CPU dengan parsing Regex yang lambat (*catastrophic backtracking*)?

### Soal 2.5: TCP Half-Open & Connection Leak Akibat Faulty Error Handlers
Sebuah backend service berkomunikasi dengan database relational menggunakan connection pool. Pada salah satu fungsi query data kompleks, terjadi exception `QueryTimeoutException`. Namun, blok error handling gagal mengeksekusi penutupan koneksi (`connection.close()` atau mengembalikan handle ke pool) karena alur eksekusi terinterupsi oleh runtime panic/fatal error. Jelaskan kondisi socket TCP secara internal (*TCP Half-Open* / socket leak), dampaknya terhadap ketersediaan pool koneksi, serta mekanisme internal database driver modern (seperti *context cancellation* atau *driver keep-alive probes*) untuk mengatasinya.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Flash-Sale Logging Avalanche (Bottleneck Skala Besar)
Sebuah platform e-commerce meluncurkan flash sale dengan lonjakan traffic hingga 150.000 Request Per Second (RPS) pada API Gateway dan Order Service. Tim engineering sebelumnya menyetel log level ke `DEBUG` untuk memudahkan pelacakan bug selama proses deployment staging, tetapi lupa mengubahnya kembali ke `WARN`/`ERROR` saat promosi ke environment Production. 

Tiba-tiba, latensi rata-rata (p99) meroket dari 45ms menjadi 8.500ms, CPU utilization server menyentuh 100%, disk I/O wait melesat tinggi, dan akhirnya seluruh instance service mengalami status *Not Ready* pada orkestrasi Kubernetes. Menariknya, database utama kapasitasnya masih terpakai 30% dan tidak mengalami bottleneck.

**Pertanyaan Diagnostik Terarah:**
1. Mengapa operasi penulisan log I/O yang bersifat sepele (*trivial*) dapat melumpuhkan throughput pemrosesan CPU backend secara sistemik? Analisis perbedaan dampaknya jika sistem menggunakan synchronous logging vs asynchronous buffered logging.
2. Langkah mitigasi cepat (*immediate emergency containment*) apa yang harus dilakukan di production tanpa harus melakukan rebuild image dan redeploy service?
3. Rancang arsitektur logging modern yang tahan banting untuk beban tinggi, mencakup konsep *Dynamic Log Level switching* via distributed configuration, *ring-buffer / drop-on-backpressure*, dan *rate-limiting logging*.

---

### Skenario B: The Silent Inventory Discrepancy (Data Integrity & Partial Failure)
Sebuah platform reservasi tiket bioskop memiliki flow checkout transaksi yang melibatkan 3 tahapan dalam satu eksekusi request:
1. Menahan kursi di Redis Cache (*Lock seat TTL 10 menit*).
2. Memotong saldo wallet pengguna via External Payment Gateway.
3. Mencatat `Order` status `CONFIRMED` ke database PostgreSQL.

Pada saat event konser berskala nasional dibuka, terjadi lonjakan request bersamaan untuk kursi-kursi premium. Muncul ratusan komplain pengguna: saldo wallet terpotong, kursi di denah aplikasi berubah menjadi kosong kembali (tidak ter-booking), dan tidak ada record tiket yang tercipta di PostgreSQL. 

Hasil audit log menunjukkan terjadi error: `PostgresConnectionTimeout` pada langkah ke-3 akibat database connection pool jenuh. Error handler me-rethrow exception secara mentah dan mengembalikan status HTTP 500 ke klien.

**Pertanyaan Diagnostik Terarah:**
1. Lakukan bedah forensik arsitektural: Pelanggaran error handling dan transaksi terdistribusi (*distributed transaction boundary*) apa yang menyebabkan saldo user terpotong tanpa adanya record order yang tercipta?
2. Bagaimana desain mekanisme *Compensating Transaction* (Saga Pattern atau 2-Phase Compensation) yang harus diimplementasikan ketika langkah ke-3 mengalami kegagalan permanen maupun transient?
3. Rancang pola *Idempotency-Key* yang terintegrasi dari layer validasi input hingga database level untuk menjamin bahwa proses retry otomatis dari sisi klien akibat response HTTP 500 tidak memicu pemotongan saldo ganda (*double-spending*).

---

### Skenario C: The APM Bill Shock & Performance Degradation (Arsitektur & Trade-off)
Sebuah perusahaan startup unicorn teknologi finansial mengadopsi OpenTelemetry dan platform APM komersial (SaaS). Untuk mencapai visibilitas penuh (*100% observability*), tim engineering mengonfigurasi distributed tracing dengan sampling rate **100%** untuk seluruh service (mencakup HTTP request, database queries, internal function spans, dan message broker events) yang memproses total 5 miliar event per minggu.

Dua bulan kemudian:
- Biaya vendor APM membengkak hingga $85.000 per bulan, melampaui total tagihan infrastruktur cloud utama.
- Profiling memory menunjukkan 25% CPU overhead dan 30% alokasi memory per node backend dialokasikan hanya untuk membuat span, context propagation, JSON serialization telemetry payload, dan proses masking string Regex PII secara inline.

**Pertanyaan Diagnostik Terarah:**
1. Evaluasi trade-off arsitektural antara **Head-based Sampling** vs **Tail-based Sampling**. Mana strategi sampling yang paling tepat diterapkan untuk memfilter transaksi normal (berlatensi rendah dan status HTTP 2xx) sambil mempertahankan 100% trace pada transaksi yang mengalami error (HTTP 5xx) atau anomali latensi tinggi (p95/p99 latency spikes)?
2. Bagaimana mendesain arsitektur *Telemetry Collector / Ingestion Pipeline* terpusat (misal: OpenTelemetry Collector) agar pemrosesan berat seperti masking PII, aggregasi data, dan export tracing tidak membebani alokasi CPU aplikasi utama (*offloading overhead*)?
3. Buat kerangka kalkulasi cost-vs-benefit matriks observabilitas: Metrik atau log apa saja yang esensial untuk dipertahankan secara granular, dan informasi apa yang aman untuk diagregasi atau dibuang (*drop*) demi efisiensi biaya tanpa mengorbankan Service Level Objective (SLO).

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Resilient Ingestion Middleware Engine
Bangun modul middleware/interceptor mandiri menggunakan framework/bahasa backend pilihan Anda (Node.js/Go/Java/C#) yang mengintegrasikan layer **Validasi Input Ketat**, **Unified RFC 7807 Error Handler**, dan **Contextual Telemetry Pipeline** tanpa mengandalkan library black-box monolithic.

#### 1. Problem Statement
Banyak backend API dibangun dengan error handling yang tercecer (*scattered try-catches*), format response error yang tidak seragam, log string tanpa context yang menyulitkan debugging, serta celah fatal di mana data sensitif bocor ke log platform pihak ketiga. Anda diminta merancang arsitektur layer transport API yang menerapkan *zero-trust input validation*, *unified domain error translation*, dan *high-performance structured observability*.

#### 2. Functional Requirements
1. **Strict Input Invariant & Schema Validation:**
   - Middleware memvalidasi payload request (JSON) secara ketat. Tolak payload jika mengandung *unknown fields* (mencegah mass assignment/injection).
   - Validasi kegagalan harus mengembalikan representasi detail field mana saja yang gagal beserta kode error mesin (*machine-readable code*).
2. **Standardized RFC 7807 Exception Filter:**
   - Buat representasi error global. Tangkap semua unhandled exception (termasuk runtime panic/crash) dan transformasikan menjadi format payload RFC 7807:
     ```json
     {
       "type": "https://api.domain.com/errors/invalid-order-payload",
       "title": "Unprocessable Entity",
       "status": 422,
       "detail": "Field 'amount' must be greater than 0 and currency must be standard ISO-4217",
       "instance": "/api/v1/orders/req-987a-bc12",
       "invalid_params": [
         {
           "name": "amount",
           "reason": "must_be_positive"
         }
       ],
       "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
     }
     ```
   - Pastikan **Stack Trace teknis internal TIDAK PERNAH bocor** ke output HTTP response pada environment production, namun **WAJIB tercatat lengkap** di internal error log.
3. **Structured Contextual Logging with PII Masker:**
   - Log engine harus menginjeksi: `timestamp` (ISO-8601 UTC), `trace_id`, `span_id`, `http_method`, `path`, `status_code`, `execution_time_ms`, dan `client_ip`.
   - Modul harus memiliki interceptor yang otomatis melakukan sensor/masking pada sensitive fields (seperti `password`, `cvv`, `access_token`, `national_id`) menjadi format `***MASKED***` sebelum data dialirkan ke stdout stream.
4. **Metrics Instrumentation:**
   - Sediakan metric interceptor yang mencatat:
     - `http_server_requests_duration_milliseconds` (Histogram dengan bucket latensi realistis).
     - `http_server_requests_errors_total` (Counter dengan dimensionalitas aman: method, path ter-normalisasi, status class [4xx, 5xx]).

#### 3. Technical Constraints & Non-Functional Requirements
- **Performance Budget:** Middleware pipeline total (validasi, trace parsing, context injection, metrics update) tidak boleh menambah overhead lebih dari **2.5 milidetik** per request.
- **Cardinality Safety:** Normalisasi URL dinamis pada metrik (misal: `/api/v1/users/123e4567-e89b...` harus tercatat sebagai `/api/v1/users/:id`). Jangan biarkan ID dinamis masuk ke label metrik TSDB.
- **Graceful Error Handling:** Jika logging engine atau metrics server crash/mengalami timeout, alur transaksi bisnis utama tidak boleh gagal (*non-blocking telemetry failure*).

#### 4. Deliverables & Expected Output
- File kode implementasi middleware (misal: `validation.middleware`, `error_handler.middleware`, `telemetry.middleware`).
- Demonstrasi Unit/Integration Test yang membuktikan:
  1. Payload invalid memicu response RFC 7807 status 400/422 tanpa mengeksekusi service logic.
  2. Runtime error internal (misal: simulasi database connection drop) memicu response RFC 7807 status 500 dengan stack trace yang hanya muncul di log terminal/file, bukan di HTTP response client.
  3. Log output dalam format JSON valid di mana field sensitif ter-masking dengan benar.
  4. Snapshot data metrik yang membuktikan URL dinamis telah dinormalisasi (*zero cardinality explosion risk*).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk menguji kesiapan arsitektural dan ketuntasan materi Anda sebelum beralih ke level berikutnya.

### Saya harus memahami:
- [ ] Batas fungsional yang tegas antara *Format Validation* (transport level), *Domain Invariant Validation* (entity level), dan *State Integrity Check* (database level).
- [ ] Filosofi dasar klasifikasi error: membedakan antara *Operational/Expected Errors* (kesalahan validasi, not found, unauthenticated) vs *Programmer/Unexpected Errors* (panic, null pointer, syntax failure).
- [ ] Anatomi lengkap dan standarisasi payload error berbasis **RFC 7807** (*Problem Details*).
- [ ] Keterkaitan dan trade-off fungsional antara tiga pilar observabilitas: Metrics (agregasi numerik), Logs (catatan peristiwa berkonteks), dan Traces (alur perjalanan request end-to-end).
- [ ] Bahaya sistemik dari *Cardinality Explosion* pada basis data time-series (TSDB) dan cara mencegahnya.
- [ ] Karakteristik *Transient vs Terminal Errors*, serta matematika dasar dari *Exponential Backoff with Jitter* untuk mencegah cascade collapse pada downstreams.
- [ ] Prinsip pemisahan synchronous logging vs asynchronous non-blocking buffered logging di lingkungan production skala enterprise.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap kode status HTTP langka di luar kategori standar (misal: 418 I'm a teapot, 426 Upgrade Required). Cukup pahami klasifikasi blok 2xx, 3xx, 4xx, dan 5xx.
- [ ] Syntax baris-per-baris Regex kompleks untuk validasi format (misal: regex komprehensif ISO-8601 atau RFC-5322 untuk email). Lebih baik mengandalkan library parsing berstandar industri yang teruji keamanannya terhadap *Regular Expression Denial of Service* (ReDoS).
- [ ] Spesifikasi biner protokol internal wire protocol OpenTelemetry / Prometheus scraping text format secara mendalam.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan Global Centralized Error Handling Interceptor yang menerjemahkan Domain Exception menjadi representasi response API yang bersih, aman, dan konsisten (RFC 7807).
- [ ] Mengonfigurasi engine structured logging (JSON) yang secara otomatis menyertakan Correlation/Trace ID pada setiap log entry dari context request.
- [ ] Menerapkan mekanisme sanitasi data sensitif (PII scrubbing) pada logging transport tanpa menimbulkan degradasi performa I/O atau CPU overhead masif.
- [ ] Mengukur dan mengekspos metrik sistem (latensi percentile p50, p95, p99, error rate, throughput) menggunakan standardisasi label metrik yang aman dari risiko *high cardinality*.
- [ ] Melakukan isolasi akar masalah (*root cause analysis*) insiden produksi secara deterministik dengan mengkorelasikan alert metrik, trace ID, dan timeline structured log.