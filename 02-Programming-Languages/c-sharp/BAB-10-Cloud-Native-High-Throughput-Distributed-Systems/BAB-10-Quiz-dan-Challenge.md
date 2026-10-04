# BAB 10: Quiz, Challenge, & Knowledge Check
**Cloud-Native, High-Throughput & Distributed Systems**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: ThreadPool Starvation vs. Asynchronous Non-Blocking I/O
Jelaskan secara mendalam siklus hidup alokasi *thread* pada .NET `ThreadPool` ketika melayani lonjakan *traffic* I/O terdistribusi. Apa yang secara mekanis terjadi di tingkat CLR ketika *engineer* menerapkan antipattern *sync-over-async* (misalnya `.Result` atau `.GetAwaiter().GetResult()`) di bawah beban 50.000 RPS, dan mengapa `ThreadPool.SetMinThreads` hanya dianggap sebagai mitigasi darurat sementara (*band-aid*), bukan solusi arsitektural yang benar?

### Soal 1.2: Lifecycle Socket, DNS Refresh, dan `IHttpClientFactory`
Mengapa instansiasi langsung `new HttpClient()` menyebabkan *socket exhaustion* (*ephemeral port starvation*) pada sistem konkurensi tinggi, sementara penggunaan `HttpClient` sebagai *singleton* murni tanpa konfigurasi tambahan memicu insiden kegagalan *failover* DNS? Analisis bagaimana arsitektur `IHttpClientFactory` mengelola `HttpMessageHandler` melalui *pooling*, dan jelaskan peran parameter `PooledConnectionLifetime` pada `SocketsHttpHandler` di lingkungan containerized (Kubernetes).

### Soal 1.3: Distributed Tracing Context & W3C TraceContext Propagation
Dalam komunikasi asinkron lintas batas jaringan (HTTP, gRPC, dan Message Broker seperti Kafka/RabbitMQ), jelaskan bagaimana .NET merepresentasikan trace context menggunakan kelas `Activity` dan OpenTelemetry API. Bagaimana format header standar W3C (`traceparent` dan `tracestate`) diserialisasi, disuntikkan (*inject*), diekstraksi (*extract*), dan dipropagasi oleh *runtime* .NET tanpa memerlukan intervensi manual pada setiap *signature* method?

### Soal 1.4: Kubernetes Health Probes: Liveness, Readiness, dan Startup
Jelaskan perbedaan mendasar antara Liveness, Readiness, dan Startup Probe dari perspektif *traffic routing* dan *lifecycle management* pod di Kubernetes. Bagaimana sebuah implementasi *health check* yang salah—seperti mengeksekusi *ping* langsung ke basis data terdistribusi di dalam *Liveness Probe* ASP.NET Core—dapat memicu fenomena *cascading failure* (runtuhnya seluruh klaster) saat basis data mengalami lonjakan latensi sesaat?

### Soal 1.5: Cache Stampede Mitigation & Two-Tier Caching Architecture
Jelaskan fenomena *Cache Stampede* (*thundering herd problem*) ketika sebuah *cache key* berstatus *high-read* mengalami kedaluwarsa (*expiration*). Bandingkan mekanisme mitigasi menggunakan pendekatan *Distributed Mutex/Locking* dengan pendekatan *Probabilistic Early Expiration* (algoritma XFetch). Bagaimana arsitektur *Hybrid Caching* (L1 In-Memory via `IMemoryCache` + L2 Out-of-Process via Redis) mengoptimalkan latensi sub-milidetik sekaligus menjaga konsistensi data lintas replika?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Kestrel Architecture, `System.IO.Pipelines`, dan Zero-Copy Parsing
Analisis arsitektur internal Kestrel saat menerima paket TCP dari *socket layer* hingga masuk ke *pipeline middleware*. Mengapa abstraksi klasik `System.IO.Stream` menimbulkan overhead alokasi memori yang masif (GC pressure) pada throughput jutaan request per detik, dan bagaimana `System.IO.Pipelines` (`PipeReader`/`PipeWriter`) beserta `ReadOnlySequence<byte>` memungkinkan manipulasi buffer memori secara *zero-copy* tanpa alokasi objek baru pada *managed heap*?

### Soal 2.2: Memory Management di Lingkungan Container: GC Tuning & cgroups v2
Ketika aplikasi .NET berjalan di dalam container Linux dengan batasan memori ketat (misal: Memory Limit 512 MB via Kubernetes), jelaskan bagaimana CLR membaca batasan dari subsistem *cgroups* (v1 vs v2). Mengapa *Server GC* dapat menyebabkan *Out-Of-Memory* (OOM) Kills lebih cepat dibanding *Workstation GC* jika alokasi *core* dan memori tidak proporsional? Parameter apa saja (`DOTNET_GCHeapCount`, `DOTNET_GCHighMemPercent`) yang harus disetel untuk mencapai determinisme GC di bawah beban alokasi LOH (*Large Object Heap*) yang intensif?

### Soal 2.3: Distributed Locking Safety: Redlock vs. Single-Instance with Fencing Tokens
Banyak sistem terdistribusi mengimplementasikan *distributed lock* menggunakan Redis. Mengapa implementasi penguncian berbasis *time-to-live* (TTL) sederhana rentan terhadap pelanggaran *mutual exclusion* akibat *stop-the-world* GC pause, *page faults*, atau *network delay*? Bedah kritik Martin Kleppmann terhadap algoritma Redlock, dan jelaskan bagaimana mekanisme *fencing tokens* (monotonically increasing counters) menjamin integritas data pada *storage layer* di hilir.

### Soal 2.4: Outbox Pattern, CDC, dan Ilusi "Exactly-Once" Messaging
Dalam konteks Event-Driven Architecture, buktikan secara teoritis mengapa *Exactly-Once Delivery* adalah hal yang mustahil diwujudkan pada jaringan terdistribusi tanpa koordinasi global yang mahal. Jelaskan implementasi *Transactional Outbox Pattern* menggunakan PostgreSQL dan Change Data Capture (CDC via Debezium) atau polling-publisher. Bagaimana *Consumer* harus dirancang menggunakan prinsip *At-Least-Once Delivery* yang dipadukan dengan teknik *Idempotent Consumer* (Idempotency Key & State Store)?

### Soal 2.5: Resiliency Architecture dengan Polly v8: Dynamic Hedging vs. Circuit Breaking
Pada sistem mikroservis dengan *tail latency amplification*, jelaskan perbedaan peran arsitektural antara *Circuit Breaker Pattern* dan *Hedging Pattern* yang disediakan oleh Polly v8. Bagaimana strategi *Hedging* mengeksekusi request paralel kedua sebelum request pertama *timeout* untuk memangkas p99.9 latensi? Apa risiko sistemik terhadap *downstream service* jika *hedging* tidak dibatasi oleh *concurrency limiter* atau *bulkhead isolation*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Degradation & Cascading Collapse saat Flash Sale
Sebuah platform *e-commerce* berskala besar mengalami degradasi performa ekstrem selama kampanye *Flash Sale*. Metrik pemantauan menunjukkan:
- CPU Utilization di klaster Kubernetes hanya berkisar antara **15% – 25%**.
- Request Queue pada Ingress Controller menumpuk tajam hingga puluhan ribu antrean.
- Response time p99 melonjak dari **45ms** menjadi **18.000ms**, berujung pada error HTTP 504 Gateway Timeout.
- Thread dump via `dotnet-dump` memperlihatkan lonjakan metrik `ThreadPool.PendingWorkItemCount` yang masif, dan ribuan thread berada dalam status `WaitSleepJoin` atau terblokir pada `System.Threading.Monitor.Enter`.
- Tim menemukan log bahwa sebuah *third-party payment gateway client* SDK versi lama dipanggil di tengah pipeline otentikasi menggunakan metode sinkronus: `var token = GetTokenAsync().Result;`.

**Pertanyaan Diagnostik:**
1. Rekonstruksi rantai kausalitas mekanis (*root cause chain*) yang menyebabkan CPU tetap rendah namun latensi sistem kolaps secara total (*thread starvation cascade*).
2. Bagaimana cara membuktikan secara terukur (*empirical profiling*) menggunakan tool CLI Linux (`dotnet-trace`, `dotnet-dump`, `dotnet-counters`) bahwa *starvation* sedang terjadi pada runtime pod produksi?
3. Rancang rencana remediasi instan (*hotfix*) dan arsitektur permanen (*long-term fix*) untuk mengeliminasi pemblokiran thread tersebut tanpa merusak backward compatibility dari SDK pihak ketiga.

---

### Skenario B: Double-Spending & Race Condition pada Split-Brain Network Partition
Sebuah layanan dompet digital (*Core Ledger Service*) mendistribusikan *state* akun pengguna ke 3 data center yang berbeda (DC-East, DC-Central, DC-West) dengan replikasi multi-master asinkron. 
- Terjadi *network partition* parsial yang mengisolasi DC-West dari DC-East dan DC-Central selama 4 menit.
- Seorang pengguna mengeksekusi penarikan dana sebesar \$10.000 melalui API Gateway yang mendistribusikan request secara round-robin.
- Request pertama mendarat di DC-East (saldo awal: \$10.000, dikurangi menjadi \$0).
- Request kedua mendarat di DC-West pada milidetik yang hampir bersamaan karena pengguna menekan tombol transaksi dua kali dengan cepat. Karena isolasi jaringan, DC-West masih membaca saldo \$10.000 dan berhasil memproses penarikan kedua.
- Setelah jaringan pulih (*partition heals*), terjadi anomali *negative balance* yang tidak konsisten pada *ledger*.

**Pertanyaan Diagnostik:**
1. Klasifikasikan arsitektur ini berdasarkan CAP/PACELC Theorem. Mengapa penggunaan replikasi multi-master asinkron fatal untuk transaksi finansial konsistensi tinggi?
2. Bagaimana Anda merancang ulang arsitektur konsistensi data transaksi ini menggunakan kombinasi *Optimistic Concurrency Control* (OCC / ETag / Versioning) dan *Strong Consistency primitives* (seperti Raft consensus, Spanner-like TrueTime, atau Single-Leader strictly ordered write)?
3. Rancang mekanisme rekonsiliasi otomatis (*conflict resolution*) jika partisi jaringan terlanjur terjadi, untuk memastikan audit trail integritas keuangan tidak hilang.

---

### Skenario C: Bottleneck Event Processing Pipeline (Out-of-Order Execution & Head-of-Line Blocking)
Sebuah sistem telemetri IoT memproses 200.000 event/detik dari 500.000 sensor kendaraan menggunakan Apache Kafka dan .NET Consumer Service.
- Setiap event memiliki `SensorId` (dijadikan Message Key) dan *sequential state update* yang ketat (misal: `SpeedUpdate`, `EngineTemperature`, `BrakeApplied`).
- Untuk mempercepat pemrosesan, tim engineering membungkus pemrosesan payload di dalam consumer loop menggunakan `Task.Run()`:
  ```csharp
  while (await consumer.ConsumeAsync(cancellationToken))
  {
      _ = Task.Run(() => ProcessTelemetryAsync(consumer.Current));
  }
  ```
- Akibatnya, terjadi insiden di mana status `EngineOff` dieksekusi sebelum status `EngineFaultDetected`, menyebabkan algoritma prediksi kecelakaan gagal memicu alarm.
- Ketika mereka mencoba menghapus `Task.Run` dan memproses secara serial satu per satu, terjadi *consumer lag* masif (jutaan pesan tertimbun) karena latensi I/O penulisan ke database Time-Series memakan waktu rata-rata 30ms per pesan.

**Pertanyaan Diagnostik:**
1. Mengapa implementasi awal menggunakan `_ = Task.Run(...)` melanggar jaminan keterurutan data (*ordering guarantee*) per entitas dan merusak semantik *commit offset* Kafka?
2. Mengapa pemrosesan serial murni memicu *Head-of-Line (HoL) blocking*, dan mengapa menambah partisi Kafka secara berlebihan bukanlah satu-satunya atau solusi terbaik dalam konteks efisiensi resource consumer?
3. Rancang arsitektur pipeline pemrosesan data konkuren tingkat lanjut di dalam sebuah instance .NET tunggal menggunakan `System.Threading.Channels` atau *Actor-like Mailbox pattern* (berbasis hash dari `SensorId`) yang menjamin:
   - Pemrosesan strictly sequential per `SensorId`.
   - Pemrosesan paralel multi-threaded lintas `SensorId`.
   - Dynamic batching untuk operasi penulisan I/O ke database demi menembus throughput ratusan ribu RPS.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput & Resilient Event Processing Engine
Implementasikan sebuah mesin pemrosesan data (*Ingestion Engine*) mandiri berbasis .NET 8/9 yang mengonsumsi data mentah, memvalidasi, mengalirkan data secara *non-blocking*, dan mendistribusikannya ke penyimpanan downstream dengan keandalan enterprise.

#### 1. Problem Statement
Anda diminta membangun komponen inti dari *High-Velocity Telemetry Gateway* yang harus mampu menerima aliran data telemetri berkecepatan tinggi, memproses validasi bisnis kompleks tanpa alokasi memori berlebih, membatasi beban downstream dengan strategi ketahanan dinamis, dan mencegah kehilangan data saat terjadi pemadaman (*outage*) downstream.

#### 2. Requirements
1. **Pipeline & Concurrency:**
   - Gunakan `System.Threading.Channels` (Bounded Channel) untuk menghubungkan lapisan penerima (*Ingestion API/Socket*) dengan *Processing Workers*.
   - Terapkan strategi *Backpressure* yang tepat (misal: `BoundedChannelFullMode.Wait`) untuk mencegah konsumsi memori tak terkontrol (*Out-Of-Memory*) saat downstream melambat.
   - Implementasikan *Key-Based Sharded Processing Worker Pool* untuk menjamin bahwa pesan dengan `TenantId` yang sama selalu diproses berurutan (*in-order*), namun pesan lintas `TenantId` diproses secara paralel (*concurrent*).
2. **Zero/Low Allocation Parsing:**
   - Payload telemetri masuk dalam format biner atau JSON teks. Eksekusi proses deserialisasi dan validasi data menggunakan `Span<byte>`, `ReadOnlySequence<byte>`, atau `Utf8JsonReader` tanpa mengalokasikan string baru untuk properti-properti data umum.
3. **Resilience & Fault Tolerance:**
   - Bungkus panggilan dependensi *Downstream Sink* menggunakan Polly v8 Resilience Pipeline yang mengintegrasikan:
     - **Circuit Breaker:** Membuka sirkuit jika kegagalan mencapai 40% dalam sampling 10 detik.
     - **Rate Limiter:** Token-bucket rate limiter per instance.
     - **Fallback / Dead-Letter Mechanism:** Jika sirkuit terbuka atau downstream gagal permanen, pesan harus dialihkan ke penyimpanan berbasis *disk* lokal (Outbox/Fallback Sink) tanpa melempar *unhandled exception* ke pemanggil utama.
4. **Observability:**
   - Integrasikan instrumentasi `System.Diagnostics.Activity` (Tracing) yang menambahkan atribut standar OpenTelemetry (`tenant.id`, `batch.size`, `processing.duration`).
   - Sediakan `Meter` (`System.Diagnostics.Metrics`) yang mengekspos metrik:
     - *Counter*: Jumlah pesan sukses/gagal.
     - *Histogram*: Latensi pemrosesan per batch.
     - *ObservableGauge*: Utilisasi antrean channel (persentase buffer terisi).

#### 3. Constraints
- **Alokasi Memori:** Maksimal p95 alokasi GC < 256 bytes per pesan yang diproses di luar buffer channel itu sendiri. Hindari boxing, hindari penutupan ekspresi lambda (`closure captures`), dan manfaatkan `ArrayPool<T>` jika memerlukan *working buffer*.
- **Runtime:** .NET 8.0 atau .NET 9.0 murni menggunakan C# 12/13.
- **Ketergantungan Eksternal:** Diizinkan menggunakan framework resmi Microsoft (`Microsoft.Extensions.*`, `System.Threading.Channels`, `Polly.Core` v8). Tidak diizinkan menggunakan library third-party berat untuk queue (seperti MassTransit atau Brighter) untuk logika internal channel engine; Anda harus membangun arsitektur pemrosesan konkurensinya secara *bare-metal*.

#### 4. Expected Output
1. File kode sumber lengkap yang bersih, modular, dan siap produksi (dapat dijalankan via `Program.cs` atau terdistribusi dalam arsitektur class yang rapi).
2. Kode benchmark sederhana berbasis `BenchmarkDotNet` atau harness pengujian *synthetic load generator* yang mensimulasikan minimal 100.000 pesan konkuren untuk memverifikasi:
   - Throughput (RPS).
   - Metrik GC Collection (Gen 0, Gen 1, Gen 2, dan Alokasi Total).
   - Verifikasi integritas urutan pemrosesan per `TenantId`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Kestrel, siklus eksekusi middleware ASP.NET Core, dan transport layer berbasis socket.
- [ ] Mekanisme kerja .NET ThreadPool: peran Hill-Climbing algorithm, Global vs Local queues, work stealing, serta implikasi ThreadPool starvation.
- [ ] Dampak arsitektural penggunaan `ValueTask` vs `Task`, serta batasan operasional `ValueTask` (larangan *double-await*).
- [ ] Pola kerja `System.IO.Pipelines` dan pengolahan data biner berkecepatan tinggi menggunakan `Span<T>`, `Memory<T>`, dan `ArrayPool<T>`.
- [ ] Karakteristik dan tuning Garbage Collector (Server GC vs Workstation GC, Gen 0/1/2, LOH, POH) di bawah limitasi container (cgroups).
- [ ] Konsep fundamental sistem terdistribusi: Teorema CAP, Teorema PACELC, Fallacies of Distributed Computing, dan konsistensi data (Strong vs Eventual).
- [ ] Cara kerja distributed locking yang aman beserta kelemahan Redlock, TTL drifting, dan pentingnya verifikasi storage via *fencing tokens*.
- [ ] Pola-pola reliabilitas cloud-native: Outbox Pattern, Saga Pattern (Orchestration vs Choreography), Idempotent Consumers, dan Backpressure propagation.
- [ ] Mekanisme internal arsitektur Polly v8 (Resilience Pipelines, Dynamic Hedging, Circuit Breaking, Rate Limiting).
- [ ] Prinsip OpenTelemetry: W3C TraceContext propagation, Activity API, Semantic Conventions, Structured Logging, dan ekspos metrik via Prometheus/OTLP.

### Saya tidak perlu menghafal:
- [ ] Sintaks exact baris-per-baris dari konfigurasi runtime `runtimeconfig.json` atau opsi environment variable CLR tingkat rendah (cukup pahami konsep dan temukan dokumen referensinya saat dibutuhkan).
- [ ] Setiap method signature dari class konfigurasi Polly v8 atau OpenTelemetry SDK (cukup pahami flow builder-nya).
- [ ] Detail implementasi spesifik algoritma hashing kriptografis atau internal encoding byte protokol biner tertentu (cukup pahami batas memori dan mekanisme transfer datanya).
- [ ] Perintah spesifik tool monitoring Kubernetes (seperti flag parameter `kubectl top` atau argumen `helm`) di luar konsep orkestrasi resource dasarnya.

### Saya harus bisa melakukan:
- [ ] Melakukan diagnosa mendalam terhadap thread pool starvation dan memory leak pada aplikasi produksi menggunakan CLI tools (`dotnet-dump`, `dotnet-trace`, `dotnet-gcdump`, `dotnet-counters`).
- [ ] Merancang dan mengimplementasikan pipeline asinkronus berperforma tinggi menggunakan `System.Threading.Channels` dengan jaminan ketahanan backpressure.
- [ ] Mengonfigurasi `SocketsHttpHandler` dan `IHttpClientFactory` secara optimal untuk throughput tinggi, DNS failover yang aman, dan pooling koneksi yang efisien.
- [ ] Menulis algoritma pemrosesan data/parsing berbasis *Zero-Allocation* menggunakan `Span<byte>`, `ReadOnlySequence<byte>`, dan `Utf8JsonReader`.
- [ ] Membangun consumer loop pesan terdistribusi yang aman dengan semantik idempotensi dan penanganan *out-of-order execution*.
- [ ] Mengonfigurasi strategi Health Check Kubernetes (Liveness, Readiness, Startup) secara terisolasi tanpa memicu dependensi melingkar (*cascading collapse*).
- [ ] Menginstrumentasikan aplikasi terdistribusi secara menyeluruh dengan OpenTelemetry Activity Source dan Metric Meters untuk visibilitas end-to-end yang dapat diaudit.