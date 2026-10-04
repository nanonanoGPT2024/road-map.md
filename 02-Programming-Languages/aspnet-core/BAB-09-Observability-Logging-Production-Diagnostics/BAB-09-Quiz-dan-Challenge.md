# BAB 09: Quiz, Challenge, & Knowledge Check
**Observability, Logging, & Production Diagnostics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Structured Logging vs. Unstructured Logging & Heap Allocation:**
   Jelaskan mengapa penggunaan *string interpolation* standar (`logger.LogInformation($"User {userId} logged in at {DateTime.UtcNow}")`) sangat dihindari dalam jalur eksekusi berfrekuensi tinggi (*hot path*) ASP.NET Core. Bagaimana pola *semantic/structured logging* dengan template parameter (`"User {UserId} logged in at {LoginTime}"`) dan pemanfaatan source generator `[LoggerMessage]` mampu mengeliminasi alokasi *heap* (zero-allocation) serta *boxing overhead*?

2. **Diferensiasi Semantik Health Check (Liveness vs. Readiness vs. Startup):**
   Dalam orkestrasi container seperti Kubernetes, jelaskan secara mendalam perbedaan tanggung jawab arsitektural antara *Startup Probe*, *Liveness Probe*, dan *Readiness Probe*. Apa konsekuensi katastropik jika sebuah dependensi eksternal (misalnya konektivitas ke database PostgreSQL atau Redis cache) didaftarkan ke dalam pemeriksaan *Liveness Probe* alih-alih *Readiness Probe*?

3. **Mekanika Propagasi Distributed Tracing (W3C Trace Context):**
   Uraikan bagaimana standar W3C Trace Context merepresentasikan korelasi *request* terdistribusi lintas batas proses/jaringan. Jelaskan peranan spesifik serta format header HTTP dari `traceparent` (termasuk *version*, *trace-id*, *parent-id/span-id*, dan *trace-flags*) serta `tracestate`. Bagaimana ASP.NET Core runtime memetakan header ini secara otomatis ke dalam `System.Diagnostics.Activity`?

4. **Metrik: Dimensionality & Cardinality Explosion:**
   Jelaskan arsitektur metrik modern berbasis `System.Diagnostics.Metrics` (`Meter`, `Counter<T>`, `Histogram<T>`). Apa yang dimaksud dengan *high cardinality explosion* pada dimensi/tag metrik (misalnya menyertakan `UserId` atau `OrderId` sebagai tag dalam metrik HTTP counter Prometheus)? Bagaimana dampaknya terhadap konsumsi memori Time-Series Database (TSDB) dan kinerja alokasi memori runtime internal?

5. **Arsitektur Pengumpulan Diagnostik Runtime via EventPipe:**
   Jelaskan cara kerja subsistem `EventPipe` di dalam .NET Core runtime yang menjadi fondasi alat diagnostik seperti `dotnet-trace` dan `dotnet-counters`. Mengapa mekanisme ini jauh lebih aman dan memiliki *overhead* performa yang sangat minim saat dijalankan pada *production environment* Linux container dibandingkan dengan teknik *invasive profiler injection* atau *OS-level ptrace*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Async Context Preservation & Asynchronous Local Storage (`AsyncLocal<T>`):**
   Ketika mengimplementasikan *custom logging scope* (`ILogger.BeginScope`) atau memanipulasi *correlation context*, ASP.NET Core mengandalkan `AsyncLocal<T>` untuk propagasi context antar thread worker pool. Jelaskan siklus hidup mutasi context ini: bagaimana `ExecutionContext` disalin (*copy-on-write*) saat terjadi *context switch* melalui `await`, dan mengapa mutasi objek mutable di dalam `AsyncLocal<T>` dapat memicu kebocoran konteks (*context bleed*) atau inkonsistensi pembacaan data antar cabang async paralel (`Task.WhenAll`)?

2. **Diagnostik ThreadPool Starvation Melalui Metric dan Dump:**
   Aplikasi mengalami lonjakan latensi dramatis (HTTP 504 Gateway Timeout), namun utilisasi CPU host terpantau rendah (< 20%). Metrik `ThreadPool.PendingWorkItemCount` terus meningkat, sementara `ThreadPool.ThreadCount` merangkak naik sangat lambat (kira-kira 1-2 thread per detik). Uraikan rantai penyebab teknis dari fenomena *sync-over-async* ini. Perintah `dotnet-dump` apa saja yang harus dieksekusi dalam CLI debugger SOS (`dotnet-dump analyze`) untuk memvalidasi bahwa aplikasi sedang mengalami *ThreadPool Starvation* dan menemukan stack trace thread pemblokir?

3. **Internal Memory Profiling: Finalizer Queue vs. Event Handler Leak:**
   Dalam analisis memory dump menggunakan `dotnet-dump` dengan ekstensi SOS, Anda menemukan bahwa `GC Heap` didominasi oleh objek generasi 2 (Gen 2) yang seharusnya berumur pendek. Jelaskan bagaimana Anda membedakan dua skenario berikut menggunakan perintah SOS (`!dumpheap -stat`, `!gcroot`, `!finalizequeue`):
   - Objek tertahan karena referensi tidak sengaja (*unsubscribed C# events* atau *static event delegates*).
   - Objek tertahan karena implementasi *finalizer* kustom (`~MyClass()`) yang menyebabkan objek lolos (*promoted*) dari Gen 0 ke Gen 1/Gen 2 akibat eksekusi asinkronus oleh *Finalizer Thread*.

4. **OpenTelemetry Activity Lifecycle & ActivitySource:**
   Jelaskan perbedaan mendasar antara `ActivitySource.StartActivity` dengan parameter status `ActivityKind` (Server, Client, Producer, Consumer, Internal). Kapan *activity* bernilai `null` meskipun kueri pemanggilannya valid? Bagaimana cara kerja mekanisme *sampling* (misalnya `TraceIdRatioBasedSampler` atau `ParentBasedSampler`) dalam OpenTelemetry .NET SDK menentukan apakah sebuah `Activity` harus direkam (*sampled*) secara penuh atau hanya dipropagasikan secara no-op?

5. **Analisis High CPU Menggunakan Linux Perf dan `dotnet-trace`:**
   Sebuah microservice ASP.NET Core yang berjalan di dalam Linux Alpine container mengalami utilisasi CPU 100%. Jelaskan langkah demi langkah diagnostik non-destruktif untuk mengisolasi akar masalah:
   - Bagaimana cara menggunakan `dotnet-trace collect` dengan provider `Microsoft-DotNETCore-SampleProfiler` untuk menangkap trace tanpa mematikan container?
   - Mengapa teknik *stack unrolling* pada environment Linux container terkadang menghasilkan symbol yang *unresolved* (`[unknown]`), dan bagaimana file symbol map crossgen/PDB harus dikonfigurasi menggunakan `DOTNET_EnableWriteEngine` atau `COMPlus_PerfMap`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi - Cascading Failure Akibat Logging Sink Blocker
*Konteks Sistem:*  
Platform pembayaran memproses 8.000 transaksi per detik (TPS). Tim mengonfigurasi Serilog dengan sink Elasticsearch HTTP secara langsung (tanpa message broker perantara) untuk kebutuhan audit real-time. Pada jam sibuk, cluster Elasticsearch mengalami latensi penulisan disk yang tinggi (I/O saturation), menyebabkan latensi respons cluster Elastic melambung dari 10ms menjadi 8.000ms.

*Gejala:*  
Dalam hitungan detik, seluruh pod aplikasi ASP.NET Core mengalami lonjakan penggunaan memori secara eksponensial, kehabisan *ThreadPool threads*, berhenti merespons *health check probes*, dan akhirnya di-*restart* paksa oleh Kubernetes secara beruntun (*crash looping / cascading failure*).

*Pertanyaan Diagnostik:*
1. Mengapa konfigurasi synchronous logging sink atau asynchronous sink dengan buffer yang tidak terikat (*unbounded buffer*) dapat melumpuhkan seluruh eksekusi request thread pool aplikasi?
2. Bagaimana arsitektur *buffer drop strategy* (`BoundedChannelFullMode.DropWrite`) dan *out-of-process log shipping* (misalnya via Vector, FluentBit, atau Serilog Audit/Async Sink terisolasi) dapat mencegah degradasi performa sink mematikan *core payment processing*?

### Skenario B: Distributed Tracing & Observability Void pada Message Bus Async
*Konteks Sistem:*  
Aplikasi e-commerce memproses pesanan melalui arsitektur event-driven: Web API menerima `SubmitOrderCommand`, memvalidasi data, lalu mempublikasikan pesan `OrderPlacedEvent` ke Apache Kafka. Background Worker service membaca pesan tersebut dan memproses penagihan ke payment gateway eksternal.

*Gejala:*  
Pada dashboard distributed tracing (misalnya Jaeger/Grafana Tempo), jejak jejak trace (*trace path*) terputus tepat setelah Web API mempublikasikan pesan ke Kafka. Transaksi di Background Worker muncul sebagai *trace root* baru yang independen tanpa referensi ke upstream caller, sehingga tim SRE tidak dapat mengukur total *end-to-end latency* dari klik user hingga verifikasi pembayaran.

*Pertanyaan Diagnostik:*
1. Apa kegagalan teknis yang terjadi pada fase propagasi metadata trace antara *Kafka Producer* dan *Kafka Consumer*?
2. Implementasikan secara konseptual (menggunakan C# dan `System.Diagnostics.Activity`) bagaimana Anda mengekstrak header W3C dari HTTP context, menginjeksikannya ke dalam *Kafka Message Headers*, dan merekonstruksi span anak (*child span* atau *follow-from span*) di sisi Background Worker consumer.

### Skenario C: Kebocoran Memori Skala Masif Terkait DiagnosticSource Listener
*Konteks Sistem:*  
Sebuah enterprise SaaS mengimplementasikan modul APM *in-house* kustom untuk melacak durasi eksekusi EF Core SQL Query. Modul ini berlangganan (*subscribes*) ke `DiagnosticListener.AllListeners` pada saat bootstrapping aplikasi.

*Gejala:*  
Setelah 48 jam beroperasi di production, penggunaan memori pod meningkat perlahan tapi pasti dari 300MB menjadi 14GB (OOMKilled). Hasil pembacaan metrik menunjukkan objek bertipe `System.Diagnostics.DiagnosticListener` dan `Observer<KeyValuePair<string, object>>` terus bertambah tanpa pernah dibersihkan oleh Garbage Collector.

*Pertanyaan Diagnostik:*
1. Bagaimana siklus hidup pemanggilan event listener pada `DiagnosticListener` dapat memicu kebocoran memori permanen jika objek *subscriber* tidak mengelola *subscription token* (`IDisposable`) dengan benar saat instansiasi komponen scoped/transient?
2. Bagaimana Anda mengaudit rantai referensi GC root dari dump file tersebut untuk membuktikan bahwa event listener tersebut adalah biang keladi alokasi memori yang tidak terbebas (*uncollected objects*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Production Observability & Diagnostics Engine
Membangun infrastruktur observabilitas berkinerja tinggi pada microservice transaksi finansial ASP.NET Core yang memenuhi standar audit perbankan tanpa mengorbankan alokasi memori runtime.

#### 1. Problem Statement
Microservice transaksi saat ini memiliki masalah serius:
- Menghasilkan alokasi GC sebesar ~45MB/detik hanya dari interpolasi string logging di *hot-path*.
- Tidak memiliki korelasi tracing saat memanggil HTTP dependency eksternal.
- Health check membebani database utama karena melakukan kueri `SELECT * FROM Orders` setiap 5 detik via Kubernetes Liveness Probe.
- Tim SRE tidak memiliki visibilitas metrik latensi persentil P99 secara real-time.

#### 2. Functional & Technical Requirements
1. **Zero-Allocation Structured Logging Engine:**
   - Implementasikan *structured logging* menggunakan C# Source Generators (`[LoggerMessage]`) untuk seluruh event *critical transaction* (Transaction Initiated, Validated, Processing, Completed, Failed).
   - Terapkan custom scope menggunakan `ILogger.BeginScope` yang menyertakan context audit wajib: `TenantId`, `UserId`, `TraceId`, dan `MachineName` secara otomatis melalui ASP.NET Core middleware.

2. **Distributed Tracing & Outgoing Propagation:**
   - Konfigurasikan custom `ActivitySource` bernama `"Enterprise.FinancialPlatform.Engine"`.
   - Buat *custom outgoing HTTP DelegatingHandler* yang menginjeksi W3C TraceContext ke dependency eksternal dan mencatat *custom baggage* untuk `tenant.tier` (VIP/Regular).
   - Buat child span eksplisit saat pemrosesan hashing transaksi finansial dengan tag atribut yang relevan (`payment.currency`, `payment.amount`).

3. **Enterprise Metrics Instrumentation:**
   - Gunakan `System.Diagnostics.Metrics.Meter` untuk mengekspos:
     - `Counter<long>`: Total jumlah transaksi berdasarkan status (`success`, `insufficient_funds`, `network_error`).
     - `Histogram<double>`: Distribusi durasi eksekusi pemrosesan transaksi dalam satuan milidetik dengan batas eksplisit (*explicit bucket boundaries* untuk SLA P50, P90, P99).
   - Batasi kardinalitas: Dilarang keras menyertakan data dinamis unik (`UserId`, `TransactionId`, `AccountNumber`) sebagai tag/label metrik.

4. **Production-Grade Health Checks:**
   - Pisahkan endpoint:
     - `/healthz/live`: Hanya memvalidasi aliveness internal aplikasi (kemampuan merespons HTTP dasar).
     - `/healthz/ready`: Memvalidasi konektivitas dependency (Database Ping & Redis Ping) menggunakan timeout agresif (maksimal 1.5 detik per check).
   - Output endpoint `/healthz/ready` harus berformat JSON terstruktur yang mencantumkan status individual, latency komponen, dan error message (jika ada, tanpa membocorkan connection string).

5. **Diagnostic Automation Artifact:**
   - Siapkan shell script diagnostik (`diagnose.sh`) yang siap dijalankan di container target untuk:
     - Mengambil *counter real-time* selama 30 detik (`dotnet-counters`).
     - Mengumpulkan *CPU profiling trace* 10 detik dengan format nettrace (`dotnet-trace`).
     - Memicu *memory dump* darurat saat memori mencapai ambang batas 85% (`dotnet-dump`).

#### 3. Constraints
- **Alokasi Heap:** Logging method pada *hot path* pemrosesan transaksi tidak boleh menghasilkan alokasi memori GC Gen 0 tambahan (tervalidasi via benchmark atau unit test memory constraint).
- **Sensitivitas Data (PII/Compliance):** Nomor kartu kredit (PAN), CVV, dan PIN nasabah dilarang keras muncul dalam logging, span tags, maupun metric dimensions. Terapkan mekanisme masking jika data melintas.
- **Ketergantungan Eksternal:** Solusi harus menggunakan library resmi .NET Core (`Microsoft.Extensions.*`, `System.Diagnostics.*`) dan OpenTelemetry .NET SDK standar tanpa *third-party monolithic APM agent* berbayar.

#### 4. Expected Output
1. Implementasi C# kelas/service:
   - `TransactionLoggerExtensions.cs` (Source generated log methods).
   - `CorrelationContextMiddleware.cs` (Scope injection).
   - `TransactionMetrics.cs` (Meter & metrics management).
   - `DependencyTracingHandler.cs` (DelegatingHandler tracing & propagation).
   - Registrasi konfigurasi `Program.cs` yang memuat seluruh integrasi OpenTelemetry, Serilog (dengan BoundedChannel configuration), dan Custom Health Checks.
2. File script `diagnose.sh` siap pakai dengan parameterisasi PID target.
3. Dokumen analisis singkat mengenai cara menganalisis dump file hasil script tersebut menggunakan perintah SOS `dotnet-dump analyze` jika terjadi starvation atau leak.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal `ILoggerFactory`, `ILoggerProvider`, dan bagaimana *pipeline* log filtering bekerja di ASP.NET Core.
- [ ] Mengapa *string interpolation* menyebabkan *boxing* tipe nilai (*value types*) dan alokasi `string` di heap, serta cara kerja `[LoggerMessage]` source generator menghindarinya.
- [ ] Format standar W3C Trace Context (`traceparent` dan `tracestate`) dan interoperabilitasnya dengan OpenTelemetry SDK.
- [ ] Perbedaan fundamental antara `System.Diagnostics.Activity` (.NET internal tracing primitives) dan kelas OpenTelemetry API (`Tracer`, `Span`).
- [ ] Bahaya fatal *high-cardinality tags* pada TSDB (Prometheus, InfluxDB) dan perbedaannya dengan logging metadata.
- [ ] Perbedaan fungsional antara `dotnet-dump` (memori/state crash), `dotnet-trace` (CPU profiling/latensi), `dotnet-gcdump` (ringkasan alokasi heap tanpa memory payload), dan `dotnet-counters` (metrik real-time).
- [ ] Mekanisme kerja SOS Debugging Extension (`!clrstack`, `!dumpheap`, `!gcroot`, `!threads`, `!syncblk`) untuk investigasi insiden production.
- [ ] Mengapa *Liveness Probe* yang menguji dependensi eksternal dapat memicu *cascading reboot loop* yang memperparah kegagalan sistem.

### Saya tidak perlu menghafal:
- [ ] Struktur bitwise persis dari *hexadecimal value* pada flag byte W3C `trace-flags` (cukup pahami fungsinya untuk *sampled flag* `01` vs `00`).
- [ ] Sintaks perintah detail dari seluruh sub-opsi LLDB saat membuka dump di Linux (fokus pada abstraksi `dotnet-dump analyze`).
- [ ] Seluruh nama event provider internal .NET runtime (cukup tahu provider kunci: `Microsoft-Windows-DotNETRuntime`, `Microsoft-DotNETCore-SampleProfiler`).
- [ ] Nomor registri port standar untuk setiap vendor APM (Jaeger, Zipkin, OTLP gRPC/HTTP).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *high-performance structured logging* dengan source generator `[LoggerMessage]` untuk mengeliminasi alokasi pada hot-path.
- [ ] Mengonfigurasi distributed tracing kustom menggunakan `ActivitySource` dan mengekspor datanya ke endpoint OTLP (*OpenTelemetry Protocol*).
- [ ] Menginstrumentasikan metrik performa aplikasi menggunakan `Meter`, `Counter`, dan `Histogram` dengan dimensi kardinalitas terkontrol.
- [ ] Mengonfigurasi endpoint ASP.NET Core Health Checks secara granular dengan pemisahan liveness dan readiness serta *custom response writer*.
- [ ] Menjalankan alat diagnostik CLI .NET (`dotnet-trace`, `dotnet-dump`, `dotnet-counters`) langsung di dalam production container Linux tanpa merusak integritas proses yang sedang berjalan.
- [ ] Melakukan analisis post-mortem sederhana pada file crash dump menggunakan SOS command untuk mengidentifikasi ThreadPool starvation, deadlock, atau memory leak.