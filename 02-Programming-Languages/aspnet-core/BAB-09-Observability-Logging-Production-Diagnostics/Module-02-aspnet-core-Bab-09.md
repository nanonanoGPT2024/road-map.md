# BAB 09: Observability, Logging & Production Diagnostics
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menguasai Arsitektur Internal Diagnostics .NET**: Memahami subsistem runtime CoreCLR (`EventPipe`, `DiagnosticSource`, `ActivitySource`, `System.Diagnostics.Metrics`) hingga alur transmisi sinyal observabilitas ke level kernel OS.
2. **Merancang Pipeline Zero-Allocation Telemetry**: Mengimplementasikan logging berkinerja tinggi menggunakan C# Source Generators (`[LoggerMessage]`) serta pipeline OpenTelemetry (OTel) yang hemat alokasi heap untuk beban kerja skala enterprise (>50.000 RPS).
3. **Menerapkan Distributed Tracing & W3C TraceContext**: Mengonfigurasi propagasi konteks jejak terdistribusi lintas protokol (HTTP, gRPC, Message Broker seperti Apache Kafka/RabbitMQ) secara nir-celah (*end-to-end trace continuity*).
4. **Mengeksekusi Diagnostic Post-Mortem Tingkat Lanjut**: Melakukan triase dan investigasi insiden produksi (memory leak, CPU spike, deadlocks) secara *non-invasive* di lingkungan kontainer Linux menggunakan `dotnet-dump`, `dotnet-trace`, `dotnet-gcdump`, dan SOS debugger plugin.
5. **Mengelola Cardinality & Telemetry Cost**: Mendesain strategi sampling dinamis, metrik agregasi pra-koleksi, dan mitigasi *high-cardinality explosion* pada sistem backend terdistribusi.

---

### 2. Prerequisite

Peserta wajib menguasai:
*   Dasar runtime CoreCLR: Generational Garbage Collector (Gen 0, Gen 1, Gen 2, LOH/POH), memory layout, dan thread pooling.
*   Pemahaman tentang dasar Dependency Injection (DI) dan Middleware Pipeline ASP.NET Core (.NET 8/9).
*   Pengetahuan dasar mengenai pilar Observabilitas (Logs, Metrics, Traces).
*   Pengalaman operasional dasar menggunakan Docker, Linux cgroups, dan terminal CLI.

---

### 3. Concept & Internal Architecture (Mendalam)

Observabilitas pada .NET modern dibangun langsung di dalam runtime CoreCLR, bukan sekadar abstraksi pihak ketiga. Di bawah ini adalah rincian subsistem internal yang membentuk pondasi telemetri ASP.NET Core:

```
+-------------------------------------------------------------------------+
|                           User / Application Code                       |
|  [LoggerMessage]  |  ActivitySource (Traces)  |  Meter (Metrics API)    |
+---------+--------------------+-------------------------+----------------+
          |                    |                         |
          v                    v                         v
+-------------------+  +-----------------------+  +-----------------------+
| Microsoft.        |  | System.Diagnostics    |  | System.Diagnostics    |
| Extensions.       |  | .Activity             |  | .Metrics              |
| Logging           |  +-----------------------+  +-----------------------+
+---------+---------+          |                         |
          |                    v                         v
          |            +--------------------------------------------------+
          |            | DiagnosticSource / OpenTelemetry SDK Engine      |
          |            +--------------------------------------------------+
          v                                      |
+------------------------------------------------+                        |
| CoreCLR Runtime Engine Subsystems                                       |
|                                                                         |
|  +-------------------------+     +-----------------------------------+  |
|  | EventSource / EventPipe |<----+ Unix Domain Socket / Named Pipe   |  |
|  +------------+------------+     | (/tmp/dotnet-diagnostic-{pid}-socket)|
|               |                  +-----------------+-----------------+  |
+---------------|------------------------------------|--------------------+
                |                                    |
                v                                    v
+--------------------------------+   +------------------------------------+
| Linux Kernel (Perf / LTTng /   |   | External Diagnostics Tools         |
| eBPF Tracing Subsystem)        |   | (dotnet-dump, dotnet-trace, OTel)  |
+--------------------------------+   +------------------------------------+
```

#### A. Subsistem EventPipe & Diagnostics IPC
CoreCLR tidak bergantung pada debugger eksternal untuk mengumpulkan diagnostik. Runtime menyediakan mekanisme internal bernama **EventPipe**.
*   **Inter-Process Communication (IPC):** Saat runtime berjalan di Linux, ia membuka Unix Domain Socket di `/tmp/dotnet-diagnostic-{pid}-socket`. Di Windows, ia membuat Windows Named Pipe.
*   Tool seperti `dotnet-trace` atau `dotnet-dump` bertindak sebagai IPC client yang mengirim perintah streaming ke socket ini tanpa membutuhkan privilege debugger (`ptrace`), sehingga aman dijalankan di lingkungan produksi dengan degradasi performa di bawah 3%.
*   EventPipe mengalirkan *trace events*, *GC execution markers*, *JIT compilations*, dan *thread transitions* secara binary-encoded langsung ke diagnostic client.

#### B. Activity & Distributed Context Propagation (W3C TraceContext)
Engine tracing .NET berpusat pada `System.Diagnostics.Activity`.
*   Objek `Activity` merepresentasikan sebuah unit eksekusi kerja (identik dengan *Span* pada OpenTelemetry).
*   Proses propagasi jejak menggunakan standar **W3C Trace Context**:
    *   `traceparent`: Berisi informasi versi (1-byte), trace-id (16-byte hex), parent-id/span-id (8-byte hex), dan trace-flags (1-byte bitmask, misal `01` untuk recorded/sampled).
    *   `tracestate`: Menyimpan metadata spesifik vendor sistem pemantauan tanpa merusak integritas `traceparent`.
*   Konteks ini didistribusikan secara transparan di dalam memory thread menggunakan `AsyncLocal<Activity>`, menjamin korelasi jejak tetap konsisten kendati eksekusi melintasi thread boundary akibat `await/async`.

#### C. Memory Allocations pada Pipeline Logging
Alur logging tradisional menggunakan `ILogger.LogInformation("Processing order {Id}", orderId)` memiliki masalah performa internal:
1.  **Boxing Allocation:** Jika parameter bertipe value type (misal `Guid`, `int`, `DateTime`), runtime akan mem-box parameter tersebut ke dalam heap sebagai `object`.
2.  **Array Allocation:** Kompiler membuat array `object[]` baru di managed heap untuk menampung parameter params.
3.  **Template Parsing:** String formatting engine mem-parse format template runtime secara berulang.

Solusi enterprise menggunakan `[LoggerMessage]` (Source Generator), di mana Roslyn Source Generator mengeksekusi kompilasi kode C# di compile-time yang membuat kelas turunan statis dengan cache instance `Action<ILogger, T1, Exception>` dan menggunakan `LoggerMessage.Define`, menghasilkan **zero allocations** (0 bytes di GC heap) saat level log tidak aktif, dan alokasi minimal (hanya payload target sink) saat aktif.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Logging Engine** | `ILogger.LogX` langsung dengan string interpolation atau boxing object array. | Roslyn Source-Generated Logging (`[LoggerMessage]`) + Serilog/OTel sinks sinkron-asinkron berbasis ring-buffer. |
| **Distributed Tracing** | Penulisan CorrelationId manual ke HTTP headers via custom middleware sederhana. | Instrumentasi native `ActivitySource` terstandarisasi W3C Trace Context via OpenTelemetry SDK. |
| **Metrics Collection** | Polling database atau hitungan runtime manual via static atomic integer. | `System.Diagnostics.Metrics` (`Meter`, `Counter`, `Histogram`) diekspor via OTLP gRPC ke Prometheus/Mimir. |
| **Investigasi Insiden** | Merestart kontainer atau menyisipkan log baru dan mendeploy ulang (*trial-error*). | Diagnostic non-invasive runtime profiling via Unix IPC socket (`dotnet-dump`, `dotnet-trace`). |
| **Dampak Performa** | GC thrashing tinggi (Gen 0/1 exhaustion), context-switching berlebih, IO blocking. | Alokasi memori mendekati nol, streaming I/O asinkron tak memblokir thread pool runtime. |

---

### 5. How (Workflow Detail)

Alur pipeline pemrosesan telemetri modern pada ASP.NET Core terdiri dari beberapa tahapan:

1.  **Inisiasi & Ekstraksi Header Konteks**:
    *   Permintaan HTTP masuk ke ASP.NET Core Kestrel.
    *   Hosting Kestrel mengekstrak header `traceparent` dan `tracestate`.
    *   Hosting secara otomatis membuat root `Activity` yang dihubungkan dengan span pengirim.
2.  **Instrumentasi Eksekusi Bisnis**:
    *   Aplikasi menjalankan logika domain.
    *   Developer memulai child `Activity` menggunakan domain-specific `ActivitySource`.
    *   Jika log dipanggil, *Source Generator* membaca template statis, memformat parameter tanpa boxing, dan menyuntikkan `TraceId` serta `SpanId` secara otomatis via semantic conventions.
    *   Metrik (misal: order count, latency bucket) diperbarui via thread-safe `Counter` atau `Histogram`.
3.  **Exporting & Batching Engine**:
    *   OpenTelemetry SDK mengumpulkan `LogRecord`, `Activity`, dan `MetricPoint`.
    *   Komponen `BatchExportProcessor` menahan rekaman di dalam ring buffer in-memory untuk meminimalkan I/O syscalls.
    *   Worker background thread secara periodik men-serialize batch menggunakan protobuf dan mengirimkannya melalui transmisi OTLP/gRPC (port 4317) ke OpenTelemetry Collector.
4.  **Diagnostic Interception (Saat Terjadi Insiden)**:
    *   Diagnostic tool CLI menyambung ke socket Unix `/tmp/dotnet-diagnostic-{pid}-socket`.
    *   Klien mengirim instruksi snapshot memori CoreCLR atau buffer circular event tracing tanpa mematikan proses utama yang sedang melayani request.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kotak Hitam Pesawat Komersial Modern
Bayangkan pesawat modern (ASP.NET Core Application):
1.  **Logging Tradisional** bagaikan pramugari menulis manual catatan setiap kali ada turbulensi di selembar kertas; menghabiskan kertas dan mengalihkan fokus pramugari dari melayani penumpang.
2.  **Source-Generated Logging & OpenTelemetry** adalah sensor digital otomatis avionik: setiap tekanan kabin, derajat putaran mesin, dan komunikasi radio langsung distreaming tanpa membebani pilot ke sistem penerima data via kabel terisolasi.
3.  **CoreCLR EventPipe** adalah antarmuka diagnostik di kokpit di mana teknisi darat dapat mencolokkan kabel pembaca saat pesawat sedang transit di bandara untuk menganalisis getaran turbin secara instan tanpa harus mematikan mesin pesawat.

#### Diagram Alir Telemetri Runtime Enterprise

```
                                  [ INCOMING REQUEST ]
                                           |
                                           v
               +-------------------------------------------------------+
               | ASP.NET Core Hosting Layer (Kestrel Pipeline)         |
               | - Extract W3C Header: traceparent, tracestate         |
               | - Start In-Memory Activity: Activity.Current          |
               +---------------------------+---------------------------+
                                           |
                                           v
       +-----------------------------------------------------------------------+
       | Domain Application Execution Pipeline                                 |
       |                                                                       |
       |    [Business Logic] --(Records)--> [System.Diagnostics.Metrics]       |
       |           |                                    |                      |
       |      (Executes)                                v                      |
       |           |                        [Aggregator Engine]                |
       |           v                                    |                      |
       |    [LoggerMessage]                             |                      |
       |    (0-Alloc Format)                            v                      |
       |           |                        +-----------------------+          |
       |           +----------------------->| Memory Ring Buffer    |          |
       |                                    | (BatchExportProcessor)|          |
       |                                    +-----------+-----------+          |
       +------------------------------------------------|----------------------+
                                                        |
                                                        v (OTLP / gRPC Proto)
                                            +-----------------------+
                                            | OpenTelemetry         |
                                            | Collector Agent       |
                                            +-----------+-----------+
                                                        |
                            +---------------------------+---------------------------+
                            |                           |                           |
                            v                           v                           v
                 +--------------------+     +--------------------+     +--------------------+
                 | Grafana Tempo /    |     | Prometheus /       |     | Grafana Loki /     |
                 | Jaeger (Traces)    |     | Mimir (Metrics)    |     | OpenSearch (Logs)  |
                 +--------------------+     +--------------------+     +--------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Zero-Allocation Source-Generated Logging

Implementasi `[LoggerMessage]` untuk menghindari alokasi heap saat pembuatan log.

```csharp
// File: OrderProcessingLogs.cs
using Microsoft.Extensions.Logging;

namespace Enterprise.Observability.Samples;

public static partial class OrderProcessingLogs
{
    // Menggunakan compile-time code generation: Zero allocation, 
    // tidak ada boxing untuk parameter 'orderId' (Guid) dan 'amount' (decimal).
    [LoggerMessage(
        EventId = 1001,
        Level = LogLevel.Information,
        Message = "Order {OrderId} processed successfully with amount {Amount:C}. Execution time: {ElapsedMs}ms")]
    public static partial void LogOrderProcessed(
        this ILogger logger, 
        Guid orderId, 
        decimal amount, 
        double elapsedMs);

    [LoggerMessage(
        EventId = 1002,
        Level = LogLevel.Error,
        Message = "Failed to process order {OrderId}. Reason: {FailureReason}")]
    public static partial void LogOrderFailed(
        this ILogger logger, 
        Exception exception, 
        Guid orderId, 
        string failureReason);
}
```

#### B. Practical Example: Production-Grade Observability Setup

Contoh lengkap implementasi kustom `ActivitySource`, `Meter`, dan konfigurasi OpenTelemetry SDK terpadu dalam ASP.NET Core.

##### 1. Domain Instrumentation Core (`TelemetryDiagnostics.cs`)
```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;

namespace Enterprise.Observability.Core;

public sealed class TelemetryDiagnostics : IDisposable
{
    public const string ServiceName = "Enterprise.OrderService";
    public const string ServiceVersion = "1.0.0";

    // Trace Instrument
    public ActivitySource ActivitySource { get; } = new(ServiceName, ServiceVersion);

    // Metrics Instrument
    public Meter Meter { get; } = new(ServiceName, ServiceVersion);
    
    // Explicit Metrics types
    public Counter<long> OrdersPlacedCounter { get; }
    public Histogram<double> OrderProcessingDurationMs { get; }

    public TelemetryDiagnostics()
    {
        OrdersPlacedCounter = Meter.CreateCounter<long>(
            name: "orders.placed.total",
            unit: "{orders}",
            description: "Total orders successfully placed in the system.");

        OrderProcessingDurationMs = Meter.CreateHistogram<double>(
            name: "orders.processing.duration",
            unit: "ms",
            description: "Duration of the end-to-end order placement operation.");
    }

    public void Dispose()
    {
        ActivitySource.Dispose();
        Meter.Dispose();
    }
}
```

##### 2. Business Service Implementation (`OrderService.cs`)
```csharp
using System.Diagnostics;
using Microsoft.Extensions.Logging;

namespace Enterprise.Observability.Core;

public record OrderRequest(Guid OrderId, decimal Amount, string CustomerTier);

public interface IOrderService
{
    Task ProcessOrderAsync(OrderRequest request, CancellationToken cancellationToken);
}

public class OrderService : IOrderService
{
    private readonly TelemetryDiagnostics _telemetry;
    private readonly ILogger<OrderService> _logger;

    public OrderService(TelemetryDiagnostics telemetry, ILogger<OrderService> logger)
    {
        _telemetry = telemetry;
        _logger = logger;
    }

    public async Task ProcessOrderAsync(OrderRequest request, CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();

        // Memulai distributed trace span manual
        using Activity? activity = _telemetry.ActivitySource.StartActivity(
            "ProcessOrderOperation", 
            ActivityKind.Internal);

        // Menambahkan semantic attributes (hindari PII seperti nomor kartu kredit)
        activity?.SetTag("order.id", request.OrderId.ToString());
        activity?.SetTag("customer.tier", request.CustomerTier);

        try
        {
            // Simulasi proses bisnis asynchronous
            await Task.Delay(Random.Shared.Next(50, 150), cancellationToken);

            if (request.Amount <= 0)
            {
                throw new ArgumentException("Amount must be greater than zero.");
            }

            stopwatch.Stop();

            // Record Metrics
            _telemetry.OrdersPlacedCounter.Add(1, 
                new KeyValuePair<string, object?>("customer.tier", request.CustomerTier));
            
            _telemetry.OrderProcessingDurationMs.Record(stopwatch.Elapsed.TotalMilliseconds,
                new KeyValuePair<string, object?>("customer.tier", request.CustomerTier));

            // Log output menggunakan zero-allocation engine
            _logger.LogOrderProcessed(request.OrderId, request.Amount, stopwatch.Elapsed.TotalMilliseconds);
            
            activity?.SetStatus(ActivityStatusCode.Ok);
        }
        catch (Exception ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.RecordException(ex);

            _logger.LogOrderFailed(ex, request.OrderId, ex.Message);
            throw;
        }
    }
}
```

##### 3. Program Registration & OpenTelemetry OTLP Exporter (`Program.cs`)
```csharp
using Enterprise.Observability.Core;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

// Registrasi instance instrumen telemetri
builder.Services.AddSingleton<TelemetryDiagnostics>();
builder.Services.AddScoped<IOrderService, OrderService>();

// Konfigurasi OpenTelemetry SDK
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(
            serviceName: TelemetryDiagnostics.ServiceName,
            serviceVersion: TelemetryDiagnostics.ServiceVersion)
        .AddAttributes([
            new KeyValuePair<string, object>("deployment.environment", builder.Environment.EnvironmentName),
            new KeyValuePair<string, object>("host.name", Environment.MachineName)
        ]))
    .WithTracing(tracing => tracing
        .AddSource(TelemetryDiagnostics.ServiceName)
        .AddAspNetCoreInstrumentation(opts =>
        {
            opts.RecordException = true;
        })
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(otlpOptions =>
        {
            // Kirim data trace ke OpenTelemetry Collector agent
            otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
        }))
    .WithMetrics(metrics => metrics
        .AddMeter(TelemetryDiagnostics.ServiceName)
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation() // CPU, Memory, GC, ThreadPool metrics
        .AddProcessInstrumentation()
        .AddOtlpExporter(otlpOptions =>
        {
            otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
        }));

var app = builder.Build();

app.MapPost("/orders", async (OrderRequest request, IOrderService orderService, CancellationToken ct) =>
{
    await orderService.ProcessOrderAsync(request, ct);
    return Results.Accepted(value: new { Status = "Processed", request.OrderId });
});

app.Run();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: 99th Percentile Latency Spike pada FinTech Payment Gateway
*   **Konteks**: Sebuah payment gateway memproses 40.000 transaksi pembayaran per detik pada jam sibuk menggunakan kluster Kubernetes (EKS) dengan node .NET 8.
*   **Gejala Masalah**: Meskipun utilisasi CPU rata-rata hanya 45%, latensi *p99* melonjak drastis dari 80ms menjadi 2.800ms. Sering terjadi timeout sporadis pada HTTP client downstream.
*   **Investigasi**:
    1.  Tim SRE menghubungkan container via Kubernetes debug pod dan menjalankan profiling trace non-invasive:
        ```bash
        dotnet-trace collect --process-id $(pgrep -f dotnet) --providers Microsoft-Windows-DotNETRuntime:0x4c14fccbd:5 --duration 00:00:30
        ```
    2.  Analisis file `.nettrace` menggunakan *SpeedScope* mengidentifikasi *blocking time* yang sangat masif di thread synchronization.
    3.  Inspeksi memori via dump analysis:
        ```bash
        dotnet-dump collect --process-id $(pgrep -f dotnet)
        dotnet-dump analyze core_dump
        > dumpheap -stat
        ```
        Hasil analisa menemukan miliaran instance `System.String` dan `System.Object[]` mengantre di memori.
    4.  **Root Cause Ditemukan**:
        *   Developer menggunakan Serilog dengan custom sink synchronous file lock pada block `ILogger.LogInformation($"Order {order.Id} details: {JsonSerializer.Serialize(order)}")`.
        *   Interpolasi string menyebabkan string generation dan boxing masif memicu GC Gen 0 & Gen 1 berjalan nonstop (*GC Thrashing*).
        *   Sink sinkron menyebabkan lock contention pada disk I/O, menahan ThreadPool threads sehingga terjadi *Thread Pool Starvation*.
*   **Solusi Rekayasa**:
    1.  Mengganti seluruh format string interpolasi menjadi Source-Generated `[LoggerMessage]`.
    2.  Memutus serialisasi JSON dari inline-logging, memindahkan data kontekstual ke `Activity.SetTag` dan structured parameters.
    3.  Mengganti synchronous log sink menjadi OpenTelemetry OTLP gRPC exporter yang beroperasi menggunakan internal `RingBuffer` asynchronous dengan batching (drop buffer jika overload terlampaui).
*   **Hasil**:
    *   Latensi p99 turun dari 2.800ms menjadi **68ms**.
    *   Alokasi GC per detik turun sebesar **89%**.
    *   Tidak ada lagi kejadian thread pool exhaustion.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    [ Observability Architectural Choices ]
                                       |
            +--------------------------+--------------------------+
            |                                                     |
            v                                                     v
   [ 100% Head Sampling ]                               [ Tail-Based Sampling ]
   - Keuntungan: Data absolut lengkap.                  - Keuntungan: Hanya simpan error/p99 trace.
   - Dampak Buruk: I/O jenuh, biaya OTel                - Dampak Buruk: Perlu OTel Collector tier
     storage masif, GC pressure tinggi.                   dengan footprint memori besar.
```

1.  **Trace Sampling (Head vs Tail Sampling)**:
    *   *Head-Based (Default .NET SDK)*: Keputusan sampling diambil di awal request. Sangat murah dari sisi resource aplikasi, namun jika sampling rate 5%, ada kemungkinan transaksi yang gagal tidak terekam trace-nya.
    *   *Tail-Based*: Keputusan sampling diambil setelah tracing selesai oleh kolektor eksternal. Semua error tersimpan, tetapi memerlukan OTel Collector cluster besar untuk menampung seluruh trace in-memory sementara.
2.  **Telemetry Overhead vs Data Granularity**:
    *   Menambahkan tag berdimensi tinggi (*high cardinality*, contoh: user email, dynamic payload guid) ke dalam `Counter`/`Histogram` akan merusak time-series database (Prometheus/Mimir) dengan konsumsi RAM yang eksponensial.
    *   *Trade-off*: Batasi dimensi metrik hanya pada kategori berhingga (*finite set*) seperti `customer_tier`, `http_status_code`. Simpan data granular unik (GUID, payload ID) di dalam *Distributed Tracing Tags* atau *Structured Logs*.
3.  **Synchronous File Flushing vs Background Ring Buffer**:
    *   Sync Flush menjamin 0% log loss saat hard-crash, tetapi mengorbankan latency throughput hingga 80%.
    *   Async Ring Buffer memberikan throughput maksimal, namun berisiko kehilangan beberapa baris log terakhir jika container dimatikan secara mendadak (`kill -9`).

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: String Interpolation dalam Pemanggilan Log
```csharp
// FATAL: String di-evaluasi dan dialokasikan ke HEAP meskipun level Debug dimatikan!
_logger.LogDebug($"Processing transaction with payload: {payload.ToXml()}");

// PERBAIKAN: Gunakan Source Generator atau cek eksplisit level sebelum serialisasi
if (_logger.IsEnabled(LogLevel.Debug))
{
    _logger.LogDebug("Processing transaction with payload: {Payload}", payload.ToXml());
}
```

#### Kesalahan 2: Cardinality Explosion pada Metrik
```csharp
// FATAL: Menjadikan dynamic identifier sebagai label/tag metrik
_telemetry.OrdersPlacedCounter.Add(1, new KeyValuePair<string, object?>("order.id", order.Id.ToString()));

// PERBAIKAN: Gunakan atribut berdimensi statis/rendah
_telemetry.OrdersPlacedCounter.Add(1, new KeyValuePair<string, object?>("payment.method", "CreditCard"));
```

#### Kesalahan 3: Tidak Membawa TraceContext pada Background Worker / Message Queue
```csharp
// SALAH: Menjalankan Task/Thread baru tanpa menghubungkan parent Activity
Task.Run(() => ProcessBackgroundJob()); // Span ID akan hilang atau terputus!

// PERBAIKAN: Ekstrak context atau pastikan konteks terikat
var parentActivity = Activity.Current;
Task.Run(() => 
{
    using var activity = telemetry.ActivitySource.StartActivity(
        "BackgroundJobExecution", 
        ActivityKind.Internal, 
        parentActivity?.Context ?? default);
    
    // Logika proses background
});
```

#### Prosedur Troubleshooting Insiden Produksi (Cheat Sheet):
1.  **Thread Pool Starvation Detection**:
    ```bash
    dotnet-counters monitor --process-id <PID> --counters System.Runtime
    # Pantau: ThreadPool Completed Work Item Rate vs ThreadPool Thread Count
    ```
2.  **Identifikasi Memory Leak / GC Heap Growth**:
    ```bash
    dotnet-gcdump collect --process-id <PID>
    # Buka file .gcdump di Visual Studio atau PerfView untuk membandingkan delta pertumbuhan tipe objek
    ```
3.  **Investigasi Deadlock / High CPU**:
    ```bash
    dotnet-dump collect --process-id <PID> --type Full
    dotnet-dump analyze <dump_file>
    > clrthreads
    > setthread <thread_num>
    > clrstack -a
    ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Logging:**
    - [ ] 100% hot-path logging menggunakan `[LoggerMessageAttribute]` (Roslyn Source Generation).
    - [ ] Tidak ada penggunaan string interpolation (`$""`) di dalam method ILogger.
    - [ ] Tidak memasukkan PII (Personally Identifiable Information), token authorization, atau nomor kartu kredit ke dalam payload log.
- [ ] **Tracing:**
    - [ ] Semua background consumer (Kafka, RabbitMQ, SQS) mengekstrak header W3C (`traceparent`) dan meneruskannya ke `ActivityContext`.
    - [ ] `ActivitySource` diinstansiasi sebagai instance singleton per module/service (bukan per-request).
    - [ ] Atribut custom span mengikuti OpenTelemetry Semantic Conventions.
- [ ] **Metrics:**
    - [ ] Tidak ada *High-Cardinality dimensions* (UserID, OrderID, Timestamp) pada label `Counter`, `Histogram`, atau `Gauge`.
    - [ ] Runtime instrumentation aktif (`AddRuntimeInstrumentation`) untuk memonitor GC pauses, LOH allocation, dan thread pool load.
- [ ] **Runtime Diagnostic Readiness:**
    - [ ] Container Linux Image memiliki tool CLI (`dotnet-dump`, `dotnet-trace`) terinstal atau runtime diizinkan membaca socket IPC via temporary mounted volume (`/tmp`).
    - [ ] Environment variable `DOTNET_EnableDiagnostics=1` aktif.

---

### 12. Hands-on Practice

Buatlah implementasi lengkap diagnostik produksi di dalam folder workspace `hands-on/m02/`.

#### Langkah 1: Persiapan Proyek
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
dotnet new webapi -n EnterpriseDiagnosticsLab -f net8.0
cd EnterpriseDiagnosticsLab
dotnet add package OpenTelemetry.Extensions.Hosting --version 1.9.0
dotnet add package OpenTelemetry.Instrumentation.AspNetCore --version 1.9.0
dotnet add package OpenTelemetry.Instrumentation.Http --version 1.9.0
dotnet add package OpenTelemetry.Instrumentation.Runtime --version 1.9.0
dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol --version 1.9.0
dotnet add package OpenTelemetry.Exporter.Console --version 1.9.0
```

#### Langkah 2: Mengonfigurasi Diagnostic Instrumentation
Buat file `Diagnostics.cs`:
```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;

namespace EnterpriseDiagnosticsLab;

public static class Diagnostics
{
    public const string SourceName = "EnterpriseLab.Core";
    public static readonly ActivitySource ActivitySource = new(SourceName, "1.0.0");
    public static readonly Meter Meter = new(SourceName, "1.0.0");

    public static readonly Counter<long> TransactionCounter = 
        Meter.CreateCounter<long>("lab.transactions.count");
    
    public static readonly Histogram<double> LatencyDistribution = 
        Meter.CreateHistogram<double>("lab.transactions.latency.ms");
}
```

#### Langkah 3: Mengonfigurasi Source-Generated Loggers
Buat file `Loggers.cs`:
```csharp
namespace EnterpriseDiagnosticsLab;

public static partial class Loggers
{
    [LoggerMessage(
        EventId = 2001,
        Level = LogLevel.Information,
        Message = "Processing transaction {TransactionId} of type {Type}")]
    public static partial void LogTransactionStart(this ILogger logger, Guid transactionId, string type);

    [LoggerMessage(
        EventId = 2002,
        Level = LogLevel.Warning,
        Message = "Transaction {TransactionId} flagged for high latency: {Duration} ms")]
    public static partial void LogHighLatencyWarning(this ILogger logger, Guid transactionId, double duration);
}
```

#### Langkah 4: Menghubungkan Pipeline di `Program.cs`
Update file `Program.cs`:
```csharp
using System.Diagnostics;
using EnterpriseDiagnosticsLab;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService("EnterpriseDiagnosticsLab"))
    .WithTracing(tracing => tracing
        .AddSource(Diagnostics.SourceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddConsoleExporter())
    .WithMetrics(metrics => metrics
        .AddMeter(Diagnostics.SourceName)
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddConsoleExporter());

var app = builder.Build();

app.MapGet("/simulate-work/{type}", async (string type, ILogger<Program> logger) =>
{
    var txId = Guid.NewGuid();
    logger.LogTransactionStart(txId, type);

    var sw = Stopwatch.StartNew();
    
    using (Activity? activity = Diagnostics.ActivitySource.StartActivity("SimulateDatabaseQuery"))
    {
        activity?.SetTag("db.system", "postgresql");
        activity?.SetTag("transaction.id", txId.ToString());

        var delay = Random.Shared.Next(10, 400);
        await Task.Delay(delay); // Simulasi delay DB
    }

    sw.Stop();
    var duration = sw.Elapsed.TotalMilliseconds;

    Diagnostics.TransactionCounter.Add(1, new KeyValuePair<string, object?>("transaction.type", type));
    Diagnostics.LatencyDistribution.Record(duration, new KeyValuePair<string, object?>("transaction.type", type));

    if (duration > 250)
    {
        logger.LogHighLatencyWarning(txId, duration);
    }

    return Results.Ok(new { Status = "Complete", TransactionId = txId, DurationMs = duration });
});

app.Run();
```

#### Langkah 5: Eksekusi dan Verifikasi Diagnostik
1.  Jalankan aplikasi:
    ```bash
    dotnet run
    ```
2.  Buka terminal terpisah, kirim request berulang:
    ```bash
    curl http://localhost:5000/simulate-work/payment
    curl http://localhost:5000/simulate-work/inquiry
    ```
3.  Pantau console output: Verifikasi bahwa traces dan metrics diekspor ke console terminal secara realtime dengan korelasi trace-id yang terpasang pada context.

---

### 13. Exercise

#### Level: Easy
Ubah method `LogTransactionStart` pada Hands-on Practice di atas agar mendukung parameter opsional `priority` (integer) menggunakan Source Generator `[LoggerMessage]`, pastikan compile berhasil tanpa peringatan alokasi.

#### Level: Medium
Buat custom `DelegatingHandler` untuk `HttpClient` yang secara manual mengekstrak konteks `Activity.Current` saat ini dan menyuntikkannya ke outgoing HTTP headers menggunakan format W3C `traceparent` secara eksplisit, lalu lakukan validasi bahwa downstream menerima header tersebut.

#### Level: Hard
Tulis custom `IDiagnosticListener` subscription yang mencegat event internal Kestrel runtime (`Microsoft.AspNetCore.Hosting.HttpRequestIn.Start`), lalu secara otomatis menambahkan security attribute `client.ip` yang di-hash (SHA256) ke trace span tanpa mengorbankan throughput request.

---

### 14. Challenge

**Skenario Sistem Distribusi Asinkron Lintas Protokol:**
Anda diminta membangun pipeline distributed tracing nir-celah (*end-to-end trace continuity*) untuk arsitektur transaksi yang melintasi 3 hop protokol yang berbeda:
1.  **Hop 1 (Ingress)**: HTTP REST API menerima order masuk, membuat Span A, kemudian mendeposit payload ke dalam antrean Kafka.
2.  **Hop 2 (Queue Processing)**: Sebuah Worker Service (.NET BackgroundService) membaca event Kafka, mengekstrak W3C context dari custom metadata byte header Kafka, menyambungkan Span B sebagai child dari Span A, lalu memproses transaksi ke database.
3.  **Hop 3 (Egress/gRPC)**: Worker service menghubungi Core-Banking engine via protokol gRPC menggunakan Client interceptor yang secara transparan menyuntikkan trace context ke metadata gRPC (Span C).

**Tantangan Arsitektur:**
1.  Jika salah satu request mengalami exception di level gRPC (Hop 3), span parent (Hop 1 & Hop 2) harus menandai trace status sebagai `Error` dan merekam exception detail tanpa membocorkan kredensial.
2.  Terapkan strategi **Trace Tail Sampling Engine** lokal di mana hanya trace yang mengalami latency total > 500ms atau berstatus Error yang dikirimkan ke collector, sedangkan trace sukses dengan latency cepat di-drop untuk menghemat bandwidth telemetri.
3.  Implementasi harus **0-allocation** pada hot-path message handling loop di Worker Service.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1.  Apa subsistem internal CoreCLR yang bertindak sebagai jalur komunikasi default untuk tools seperti `dotnet-trace` dan `dotnet-dump` pada Linux?
2.  Mengapa pemanggilan `_logger.LogInformation("ID: " + id)` sangat dihindari pada sistem backend enterprise?
3.  Sebutkan dua komponen utama dari format standar W3C Trace Context!
4.  Apa peran dari kelas `System.Diagnostics.ActivitySource` dalam OpenTelemetry .NET ecosystem?
5.  Apa perbedaan mendasar antara tipe metrik `Counter` dan `Histogram` pada `System.Diagnostics.Metrics`?

#### B. Pertanyaan Intermediate
6.  Bagaimana runtime CoreCLR mempertahankan `Activity.Current` agar tetap konsisten melintasi pergantian thread worker pool saat eksekusi kode asynchronous (`await Task`)?
7.  Apa yang dimaksud dengan fenomena *Cardinality Explosion* pada sistem time-series metrics dan bagaimana cara mencegahnya di ASP.NET Core?
8.  Bagaimana cara mengambil memory dump dari kontainer .NET tanpa menghentikan atau me-restart kontainer tersebut?
9.  Mengapa `[LoggerMessage]` source generator lebih efisien daripada metode `ILogger.Log` biasa dari perspektif alokasi Heap dan instruksi CPU?
10. Kapan sebaiknya kita memilih *Tail-based sampling* daripada *Head-based sampling* dalam arsitektur distributed tracing enterprise?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice ASP.NET Core di kubernetes mengalami crash berkala akibat *Out of Memory (OOM) Killed*. Profiling awal menunjukkan heap aplikasi normal, namun memory container terus naik hingga limit. Bagaimana langkah teknis Anda mengidentifikasi apakah kebocoran memori terjadi di *Managed Heap* atau *Native Memory* menggunakan diagnostic tools CLI?
12. **Skenario 2**: Setelah menambahkan instrumentasi tracing OpenTelemetry pada sistem pemrosesan batch yang memproses 100.000 pesan per detik, terjadi lonjakan latensi dan CPU usage naik 40%. Saat dicek, sebagian besar alokasi memori berasal dari telemetry data. Perubahan arsitektur apa yang harus dilakukan pada Telemetry pipeline untuk menanggulanginya?
13. **Skenario 3**: Tim SRE menemukan bahwa distributed trace terputus saat request berpindah dari Kestrel Controller ke library background third-party yang mengelola thread pool internal sendiri. Mengapa korelasi trace-id tersebut hilang dan bagaimana cara memulihkan relasi parent-child span tersebut?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Pertanyaan Basic
1.  **EventPipe** yang berkomunikasi via IPC Unix Domain Socket (`/tmp/dotnet-diagnostic-{pid}-socket`).
2.  Karena operasi konkatenasi string tersebut mengevaluasi string baru di managed heap (Gen 0) terlepas dari apakah level log tersebut sedang diaktifkan atau dinonaktifkan, sehingga memicu GC pressure yang tinggi.
3.  Header `traceparent` (menyimpan version, trace-id, parent-id/span-id, trace-flags) dan header `tracestate` (menyimpan key-value pairs spesifik vendor vendor telemetri).
4.  `ActivitySource` adalah representasi native dari *Tracer* di .NET. Kelas ini bertanggung jawab untuk membuat dan mengelola daur hidup objek `Activity` (Span).
5.  `Counter` merepresentasikan nilai skalar bertambah secara monoton (misal: total request), sedangkan `Histogram` mengukur persebaran statistik nilai (misal: durasi latensi request, ukuran payload).

#### Kunci Pertanyaan Intermediate
6.  CoreCLR menyimpannya menggunakan struktur data internal `AsyncLocal<Activity>`. `AsyncLocal` memanfaatkan mekanisme `ExecutionContext` runtime yang secara otomatis disalin (*captured and restored*) oleh Task Scheduler ke thread baru setiap kali terjadi context switch pada kelanjutan `await`.
7.  *Cardinality Explosion* terjadi ketika developer menyuntikkan label/tag yang memiliki nilai unik sangat besar atau tak terhingga (misal: UUID, hash payload, email) ke dalam metrik. Masing-masing kombinasi label menghasilkan alokasi time-series baru di database (seperti Prometheus), yang akhirnya menyebabkan out-of-memory crash pada server monitoring. Pencegahannya adalah membatasi label hanya pada data enumeration berhingga (*low cardinality*).
8.  Dengan mengeksekusi tool `dotnet-dump collect --process-id <PID>` secara langsung ke target container (bisa via `kubectl exec` atau container sidecar yang membagi process namespace `shareProcessNamespace: true`).
9.  Roslyn Source Generator mendefinisikan *delegate Action* statis terkompilasi (`LoggerMessage.Define`). Keunggulannya: parameter bertipe value-type diteruskan via strongly-typed generics tanpa alokasi boxing (`object`), tidak membuat array params baru di heap, dan secara otomatis menyisipkan guard check (`if (_logger.IsEnabled())`) sebelum mengevaluasi format string.
10. Dipilih ketika aplikasi menangani throughput transaksi masif di mana sebagian besar request sukses (sehingga menyimpan seluruh trace akan memboroskan storage dan bandwidth), tetapi kita tetap membutuhkan visibilitas 100% terhadap seluruh request yang mengalami error atau request dengan latensi ekstrem (*p99/p99.9*).

#### Kunci Skenario Kasus Produksi
11. **Analisa Skenario 1**:
    *   Langkah 1: Eksekusi `dotnet-gcdump collect -p <PID>` dua kali dengan interval 10 menit. Jika managed heap size flat, masalahnya ada di Native Memory.
    *   Langkah 2: Ambil Core Dump penuh: `dotnet-dump collect -p <PID> --type Full`.
    *   Langkah 3: Buka dump dengan `dotnet-dump analyze <dump_path>` lalu jalankan perintah `eeheap -loader` dan `dumpheap -stat`. Jika managed size jauh di bawah total RSS container cgroup memory, periksa native memory allocators (seperti unmanaged P/Invoke, native OpenSSL buffers, atau unmanaged GDI/socket handlers) menggunakan Linux `jemalloc` profiling atau tools seperti `valgrind` / `native memory profiler`.
12. **Analisa Skenario 2**:
    *   Ganti exporter trace dari default processor synchronous menjadi asynchronous `BatchExportProcessor`.
    *   Terapkan **Head-Based Ratio Sampling** pada level .NET SDK (misal: hanya sampling 5% transaksi sukses: `builder.SetSampler(new TraceIdRatioBasedSampler(0.05))`).
    *   Hentikan perekaman atribut span yang berulang atau berukuran besar (hindari menambahkan raw payload request/response ke dalam Tags).
    *   Ubah channel transmisi OTLP ke mode binary Protobuf over gRPC dengan kompresi Gzip diaktifkan.
13. **Analisa Skenario 3**:
    *   *Penyebab*: Background library pihak ketiga kemungkinan menginisiasi thread native mentah tanpa menyalin (*ExecutionContext.SuppressFlow*) atau tidak menggunakan abstractions .NET modern (`Task`/`ThreadPool`), sehingga `AsyncLocal<Activity>` tidak terpropagasi ke thread tersebut.
    *   *Solusi*: Tangkap referensi `Activity.Current?.Context` sebelum dispatch ke background library. Di dalam callback execution thread background library tersebut, buat Activity baru secara manual menggunakan `ActivitySource.StartActivity("ChildTaskName", ActivityKind.Internal, parentContext)`.

---

### 16. Summary

Observabilitas modern pada ASP.NET Core enterprise bukan sekadar pelengkap instalasi logging, melainkan integrasi performa tinggi dari subsistem internal runtime CoreCLR:
1.  **Struktur Terpadu**: Menggabungkan logging nir-alokasi (`[LoggerMessage]`), distributed tracing native (`ActivitySource`), dan agregasi data metrik (`System.Diagnostics.Metrics`) yang selaras dengan standar industri **OpenTelemetry** dan **W3C TraceContext**.
2.  **Efisiensi Runtime**: Pemanfaatan source generation dan alur eksekusi asinkron ring-buffer mutlak diperlukan untuk mencegah GC thrashing dan thread pool exhaustion di bawah beban kerja skala tinggi.
3.  **Kesiapan Produksi**: Kemampuan mengeksekusi live-diagnostics non-invasive (`dotnet-dump`, `dotnet-trace`, `dotnet-counters`) via diagnostic socket IPC memungkinkan triase insiden produksi level enterprise tanpa degradasi ketersediaan sistem (*zero downtime diagnostic*).