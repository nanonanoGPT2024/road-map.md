# Bab 09 Module 01: Observability, Logging, & Production Diagnostics

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Spesialisasi:** ASP.NET Core Enterprise Architecture (.NET 8/9)
* **Modul:** Bab 09 Module 01 — Observability, Logging, & Production Diagnostics
* **Tingkat Kesulitan:** Advanced / L4-L5
* **Prasyarat:** Pemahaman mendalam tentang ASP.NET Core Middleware Pipeline, Dependency Injection Lifecycle, Asynchronous Programming (`async`/`await`, `ValueTask`), serta infrastruktur container (Docker/Kubernetes).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Membangun Arsitektur Three Pillars of Observability:** Mengonfigurasi dan mengintegrasikan Metrics, Distributed Traces, dan Structured Logs secara natif menggunakan OpenTelemetry .NET SDK ke endpoint OpenTelemetry Protocol (OTLP).
2. **Menerapkan Zero/Low-Allocation High-Performance Logging:** Menggantikan runtime string formatting logging dengan Compile-Time Source Generators (`[LoggerMessage]`) guna meminimalisasi tekanan Gen0 Garbage Collection di jalur throughput tinggi.
3. **Menguasai API Diagnostik Inti .NET Runtime:** Mengorkestrasi instrumentasi kustom menggunakan `System.Diagnostics.Activity`, `ActivitySource`, `Meter`, dan `Counter<T>` untuk propagasi context W3C TraceContext (`traceparent`, `tracestate`).
4. **Melakukan Triage Insiden Produksi Live:** Mengoperasikan toolchain CLI diagnostik .NET (`dotnet-dump`, `dotnet-trace`, `dotnet-counters`, `dotnet-gcdump`) tanpa menghentikan proses aplikasi untuk mendeteksi memory leaks, thread pool starvation, dan high-CPU spikes.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam sistem terdistribusi modern, kegagalan bukan lagi anomali melainkan kepastian statistik. Debugging menggunakan *step-by-step local debugger* tidak dapat diimplementasikan pada kluster produksi yang melayani jutaan transaksi per detik. 

Pergeseran paradigma mental model yang wajib diadopsi adalah:

```
+-------------------------------------------------------------------------+
|                  PARADIGMA PEMANTAUAN APLIKASI                          |
+-------------------------------------------------------------------------+
| Monitoring Reaktif (Tradisional)    vs    Observabilitas Proaktif (Modern) |
| - "Apakah sistem menyala?"              - "Mengapa latensi naik p99?"    |
| - Text-based unformatted logs           - Structured Event Streams      |
| - Siloed metrics & alerts               - Unified Traces-Metrics-Logs   |
| - Post-mortem via server restart        - Runtime Memory/Thread Dumps   |
+-------------------------------------------------------------------------+
```

Observabilitas bukanlah sekadar "menambah logging". Observabilitas adalah kemampuan untuk **menyimpulkan status internal sistem hanya berdasarkan output eksternalnya**. Anda tidak lagi menebak di mana letak bottleneck; Anda menginterogasi data telemetri yang terhubung melalui *Distributed Context Propagation*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup pemrosesan telemetri dari HTTP request yang masuk, melewati pipeline ASP.NET Core, runtime engine, hingga diekspor ke OTel Collector:

```
[ Incoming HTTP Request ]
  W3C Headers: traceparent, tracestate
             │
             ▼
┌────────────────────────────────────────────────────────┐
│ ASP.NET Core Hosting Pipeline (Kestrel)                │
│  - Activity Creation via DiagnosticSource              │
│  - Ingress Middleware: Correlation Context Extracted  │
└────────────┬───────────────────────────────────────────┘
             │
             ├─────────────────────────────────────────────────┐
             ▼                                                 ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│ Application Execution Scope   │               │ OpenTelemetry .NET SDK Engine │
│                               │               │                               │
│  [ActivitySource]             │               │ [TracerProvider]              │
│    └─► Span: Database Query   │──────Traces──►│  └─► BatchActivityProcessor   │
│                               │               │                               │
│  [Meter / Counter]            │               │ [MeterProvider]               │
│    └─► OrdersProcessedCount   │─────Metrics──►│  └─► PeriodicExportingReader  │
│                               │               │                               │
│  [ILogger via SourceGen]      │               │ [LoggerProvider]              │
│    └─► Structured Log Record  │──────Logs────►│  └─► BatchLogRecordProcessor  │
└───────────────────────────────┘               └──────────────┬────────────────┘
                                                               │
                                                               │ OTLP / gRPC
                                                               ▼
                                                ┌───────────────────────────────┐
                                                │   OpenTelemetry Collector     │
                                                │   (OTel Collector Gateway)    │
                                                └──────────────┬────────────────┘
                                                               │
                                ┌──────────────────────────────┼──────────────────────────────┐
                                ▼                              ▼                              ▼
                        ┌──────────────┐               ┌──────────────┐               ┌──────────────┐
                        │ Trace Store  │               │ Metric Store │               │  Log Store   │
                        │ (Tempo/Jaeger│               │ (Prometheus/ │               │ (Loki/Elastic│
                        │  OpenSearch) │               │  Mimir)      │               │  ClickHouse) │
                        └──────────────┘               └──────────────┘               └──────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. W3C TraceContext Propagation (`traceparent` header)
`System.Diagnostics.Activity` mengimplementasikan standar W3C. Format header HTTP `traceparent` terdiri dari 4 field:
```
version - trace_id                         - parent_id/span_id - trace_flags
00      - 4bf92f3577b34da6a3ce929d0e0e4736 - 00f067aa0ba902b7  - 01
```
* **version (2 hex):** Format versi saat ini (`00`).
* **trace_id (32 hex):** Identifier global unik untuk keseluruhan alur transaksi terdistribusi.
* **parent_id / span_id (16 hex):** Identifier segmen operasi spesifik saat ini.
* **trace_flags (8-bit bitmap):** `01` menandakan *sampled* (diteruskan dan disimpan oleh collector).

### 2. EventPipe & DiagnosticSource Runtime Subsystem
.NET Core menggunakan **EventPipe** sebagai subsistem komunikasi tracing *cross-platform* (menggantikan ETW di Windows). 
* Ketika Anda memanggil `Activity.Start()`, runtime mengevaluasi apakah ada `ActivityListener` terdaftar yang tertarik pada `ActivitySource` tersebut.
* Jika tidak ada listener yang aktif, alokasi objek `Activity` di-bypass secara efisien, mengembalikan referensi `null`. Ini memotong biaya komputasi mendekati 0 ns saat telemetri dimatikan.
* Diagnostics CLI tools (`dotnet-trace`, `dotnet-dump`) berkomunikasi langsung dengan .NET runtime via **UNIX Domain Socket** (Linux/macOS) atau **Named Pipe** (Windows) yang di-expose secara otomatis di `/tmp/dotnet-diagnostic-{pid}-{disambiguation_key}-socket`.

### 3. ILogger Internals & Allocation Bottleneck
Pemanggilan log standar:
```csharp
_logger.LogInformation("Order {OrderId} processed for user {UserId}", orderId, userId);
```
Menyebabkan:
1. Alokasi array `object[]` untuk menampung parameter (`orderId`, `userId`).
2. Boxing untuk setiap tipe data nilai/value type (`int`, `Guid`, `struct`).
3. Parsing string template saat runtime.

Source Generator `[LoggerMessage]` menyelesaikan persoalan ini secara fundamental dengan cara meng-generate class bertipe `LogDefineOptions` yang mengimplementasikan caching `Action<ILogger, ...>` yang bertipe kuat (*strongly-typed*) dan bebas alokasi array heap.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Structured Logging vs Unstructured Text Logging
Log bukan lagi kalimat deskriptif naratif, melainkan representasi dokumen data semi-terstruktur (JSON). Mengapa? Log parsing regex di log aggregators (Elastic/Loki) menguras sumber daya CPU dan rentan terhadap kegagalan parsing jika format kalimat berubah.

| Fitur | Unstructured Log | Structured Log |
| :--- | :--- | :--- |
| **Penyimpanan** | Plain text / Raw String | Key-Value Properties (JSON / MessagePack) |
| **Parsing** | Regex berat saat query | Terindeks secara native |
| **Indeksasi** | Full-text scan | B-Tree / Columnar store indexing |
| **Konteks** | Mudah hilang antar service | Otomatis terikat `TraceId` dan `SpanId` |

### OpenTelemetry Engine
OpenTelemetry (OTel) adalah standar industri netral-vendor dari Cloud Native Computing Foundation (CNCF). Arsitekturnya di .NET terdiri dari:
1. **API:** Komponen spesifikasi yang diimplementasikan langsung di Base Class Library (BCL) melalui namespace `System.Diagnostics` (`ActivitySource`, `Activity`, `Meter`, `Counter`).
2. **SDK:** Pustaka runtime (`OpenTelemetry.dll`) yang mengumpulkan data dari API, mengaplikasikan *Samplers*, *Processors*, dan mengirimkannya ke pipeline melalui *Exporters*.

### Sampling Strategy
Dalam sistem dengan beban 100.000 request per detik, mengekspor 100% trace akan membebani jaringan dan storage. OpenTelemetry menyediakan mekanisme sampling:
* **AlwaysOn / AlwaysOff:** Cocok untuk staging/testing.
* **TraceIdRatioBasedSampler:** Mengambil persentase acak deterministik (misalnya 5% dari keseluruhan transaksi).
* **ParentBasedSampler:** Jika panggilan hulu (*upstream caller*) melakukan sampling, layanan hilir (*downstream*) menghormati keputusan tersebut. Pola ini merupakan standar emas di level enterprise.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)

Implementasi modern .NET 8 menggunakan High-Performance Logger Source Generator, custom `ActivitySource`, dan integrasi OpenTelemetry SDK secara terpadu.

### Langkah 1: Mendefinisikan Metrics dan Tracing Source
Buat telemetry instrumentation provider terpusat untuk aplikasi.

```csharp
// Telemetry/AppDiagnostics.cs
using System.Diagnostics;
using System.Diagnostics.Metrics;

namespace Enterprise.Observability.Telemetry;

public static class AppDiagnostics
{
    // Nama harus unik, direkomendasikan menggunakan Service Name
    public const string ServiceName = "OrderProcessingService";
    public const string ServiceVersion = "1.0.0";

    // Distributed Tracing Source
    public static readonly ActivitySource ActivitySource = new(ServiceName, ServiceVersion);

    // Metrics Meter
    public static readonly Meter Meter = new(ServiceName, ServiceVersion);

    // Metric Instruments
    public static readonly Counter<long> OrdersPlacedCounter = 
        Meter.CreateCounter<long>(
            name: "orders.placed.count",
            unit: "{order}",
            description: "Total jumlah pesanan yang berhasil ditempatkan.");

    public static readonly Histogram<double> OrderProcessingDuration = 
        Meter.CreateHistogram<double>(
            name: "orders.processing.duration",
            unit: "ms",
            description: "Durasi pemrosesan pesanan dalam milidetik.");
}
```

### Langkah 2: Mendefinisikan High-Performance Logger (Zero-Allocation)

```csharp
// Logging/OrderLoggerExtensions.cs
using Microsoft.Extensions.Logging;

namespace Enterprise.Observability.Logging;

public static partial class OrderLoggerExtensions
{
    [LoggerMessage(
        EventId = 1001,
        Level = LogLevel.Information,
        Message = "Order {OrderId} initialized for customer {CustomerId} with total amount {Amount}.")]
    public static partial void LogOrderInitialized(
        this ILogger logger, string orderId, string customerId, decimal amount);

    [LoggerMessage(
        EventId = 1002,
        Level = LogLevel.Error,
        Message = "Order {OrderId} failed payment processing after {ElapsedMs}ms. Reason: {FailureReason}")]
    public static partial void LogPaymentFailed(
        this ILogger logger, string orderId, double elapsedMs, string failureReason, Exception? ex);
}
```

### Langkah 3: Konfigurasi Pipeline OpenTelemetry di Program.cs

```csharp
// Program.cs
using Enterprise.Observability.Logging;
using Enterprise.Observability.Telemetry;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

// Konfigurasi Resource Attributes yang mengidentifikasi instance service
var resourceBuilder = ResourceBuilder.CreateDefault()
    .AddService(serviceName: AppDiagnostics.ServiceName, serviceVersion: AppDiagnostics.ServiceVersion)
    .AddTelemetrySdk()
    .AddEnvironmentVariableDetector();

// 1. Logging Setup (OpenTelemetry Logging Bridge)
builder.Logging.ClearProviders();
builder.Logging.AddOpenTelemetry(loggingOptions =>
{
    loggingOptions.SetResourceBuilder(resourceBuilder);
    loggingOptions.IncludeFormattedMessage = true;
    loggingOptions.IncludeScopes = true;
    loggingOptions.AddOtlpExporter(otlpOptions =>
    {
        otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
    });
});

// 2. Tracing & Metrics Setup
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing
            .SetResourceBuilder(resourceBuilder)
            .AddSource(AppDiagnostics.ServiceName)
            .AddAspNetCoreInstrumentation(opts =>
            {
                opts.RecordException = true;
            })
            .AddHttpClientInstrumentation(opts =>
            {
                opts.RecordException = true;
            })
            .AddOtlpExporter(otlpOptions =>
            {
                otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
            });
    })
    .WithMetrics(metrics =>
    {
        metrics
            .SetResourceBuilder(resourceBuilder)
            .AddMeter(AppDiagnostics.ServiceName)
            .AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddRuntimeInstrumentation()
            .AddOtlpExporter(otlpOptions =>
            {
                otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
            });
    });

var app = builder.Build();

app.MapPost("/orders", async (OrderRequest request, ILogger<Program> logger) =>
{
    var stopwatch = Stopwatch.StartNew();
    
    // Membuka Span tracing kustom
    using (var activity = AppDiagnostics.ActivitySource.StartActivity("ProcessOrderTransaction"))
    {
        activity?.SetTag("order.id", request.OrderId);
        activity?.SetTag("customer.id", request.CustomerId);

        logger.LogOrderInitialized(request.OrderId, request.CustomerId, request.TotalAmount);

        // Simulasi kalkulasi/eksekusi
        await Task.Delay(Random.Shared.Next(50, 150));

        // Update metrics
        AppDiagnostics.OrdersPlacedCounter.Add(1, new KeyValuePair<string, object?>("currency", request.Currency));
        
        stopwatch.Stop();
        AppDiagnostics.OrderProcessingDuration.Record(
            stopwatch.Elapsed.TotalMilliseconds, 
            new KeyValuePair<string, object?>("payment_method", request.PaymentMethod));

        activity?.SetStatus(ActivityStatusCode.Ok);
        
        return Results.Ok(new { Status = "Completed", Id = request.OrderId });
    }
});

app.Run();

public record OrderRequest(string OrderId, string CustomerId, decimal TotalAmount, string Currency, string PaymentMethod);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis baris per baris dari implementasi di atas:

1. **`public static readonly ActivitySource ActivitySource = new(ServiceName, ServiceVersion);`**
   * Menginstansiasi engine trace emitter. Komponen ini ringan dan dirancang untuk dibuat satu kali (*singleton/static*). Jika tracing dimatikan pada SDK, objek ini menghasilkan `Activity` bernilai `null` tanpa pemborosan memori.
2. **`[LoggerMessage(EventId = 1001, Level = LogLevel.Information, ...)]`**
   * Menginstruksikan C# Roslyn Compiler untuk menghasilkan kode C# secara otomatis pada tahap kompilasi. Ini menggantikan runtime parsing parameter dengan struct-based state-holder. Alokasi boxing primitif (`decimal`, `double`) sepenuhnya dihilangkan.
3. **`builder.Logging.ClearProviders();`**
   * Menghilangkan logger bawaan seperti Console Logger default yang bersifat *synchronous* dan memicu locking overhead pada STDOUT saat throughput tinggi.
4. **`loggingOptions.IncludeScopes = true;`**
   * Menjamin metadata dari `ILogger.BeginScope` atau konteks TraceId/SpanId otomatis disisipkan (*injected*) ke dalam setiap record log yang dikirim ke OTLP.
5. **`AddAspNetCoreInstrumentation(opts => opts.RecordException = true)`**
   * Mencegat seluruh HTTP Pipeline via `DiagnosticListener`. Jika terjadi unhandled exception, error stack trace otomatis diubah menjadi semantic exception event di dalam active span.
6. **`using (var activity = AppDiagnostics.ActivitySource.StartActivity("ProcessOrderTransaction"))`**
   * Membuka unit eksekusi terdistribusi baru (Child Span). Jika ada incoming HTTP header `traceparent`, `activity.ParentId` otomatis mereferensikan parent caller tersebut. Blok `using` menjamin span ditutup (`Dispose()`) dan durasinya dihitung secara akurat saat operasi selesai.
7. **`activity?.SetTag("order.id", request.OrderId);`**
   * Menambahkan atribut terindeks pada span. Operator conditional access (`?.`) bersifat wajib untuk menghindari `NullReferenceException` jika span tidak di-sample atau tracing tidak aktif.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Skenario: Intermittent High P99 Latency & Connection Pool Exhaustion pada Checkout Service
* **Konteks:** Perusahaan retail high-concurrency mengalami anomali saat Flash Sale: Latensi P99 melesat dari 45ms ke 12.000ms. CPU usage hanya 25%, namun throughput drop signifikan.
* **Investigasi Menggunakan Observability Tiga Pilar:**
  1. *Alerting (Metrics):* Grafana dashboard memperlihatkan metrik `http_server_duration_milliseconds` mengalami spike pada rute `/checkout`. Bersamaan dengan itu, metrik kustom thread pool `threadpool.queue.length` meningkat tajam.
  2. *Correlated Tracing (Distributed Traces):* SRE melacak trace ID dari request yang lambat. Span menunjukkan bahwa `/checkout` menunggu selama 11.500ms pada downstream HTTP Call ke Payment Gateway. 
  3. *Root Cause Profiling (Production Diagnostics):* Operator mengeksekusi `dotnet-trace` pada pod Kubernetes yang terdampak. Analisis flame graph menunjukkan alokasi masif pada `System.Net.Http.SocketsHttpHandler` yang tertahan pada `WaitAsync` di Connection Pool. Developer secara tidak sengaja menginisialisasi `new HttpClient()` di dalam loop alih-alih memanfaatkan `IHttpClientFactory`, memicu Socket Exhaustion.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur produksi lengkap dengan resilient tracing, custom middleware context enricher, serta mitigasi degradasi:

```csharp
// Infrastructure/TelemetryEnrichmentMiddleware.cs
using System.Diagnostics;
using Microsoft.AspNetCore.Http;

namespace Enterprise.Observability.Infrastructure;

public sealed class TelemetryEnrichmentMiddleware
{
    private readonly RequestDelegate _next;

    public TelemetryEnrichmentMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var activity = Activity.Current;
        if (activity != null)
        {
            // Ambil Client-IP dan User-Agent untuk keamanan dan visibilitas operasional
            var ipAddress = context.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            activity.SetTag("http.client_ip", ipAddress);

            if (context.Request.Headers.TryGetValue("X-Tenant-ID", out var tenantId))
            {
                activity.SetTag("tenant.id", tenantId.ToString());
                // Propagasi tenancy ke baggage agar terbawa secara otomatis ke downstream services
                activity.AddBaggage("tenant.id", tenantId.ToString());
            }
        }

        try
        {
            await _next(context);
        }
        catch (Exception ex)
        {
            if (activity != null)
            {
                activity.SetStatus(ActivityStatusCode.Error, ex.Message);
                activity.RecordException(ex);
            }
            throw;
        }
    }
}
```

```csharp
// Resilient Worker Implementation with High-Volume Logging
// Services/PaymentProcessor.cs
using Enterprise.Observability.Logging;
using Enterprise.Observability.Telemetry;
using System.Diagnostics;

namespace Enterprise.Observability.Services;

public interface IPaymentProcessor
{
    Task<bool> ExecutePaymentAsync(string orderId, decimal amount, CancellationToken ct);
}

public sealed class PaymentProcessor : IPaymentProcessor
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<PaymentProcessor> _logger;

    public PaymentProcessor(HttpClient httpClient, ILogger<PaymentProcessor> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public async Task<bool> ExecutePaymentAsync(string orderId, decimal amount, CancellationToken ct)
    {
        using var activity = AppDiagnostics.ActivitySource.StartActivity("PaymentGatewayCall", ActivityKind.Client);
        
        activity?.SetTag("payment.amount", amount);
        var stopwatch = Stopwatch.StartNew();

        try
        {
            // Simulasi panggilan eksternal dengan distributed tracing headers otomatis terinjeksi oleh HttpClientInstrumentation
            var response = await _httpClient.PostAsJsonAsync(
                "https://api.payment.internal/v1/charge", 
                new { OrderId = orderId, Amount = amount }, 
                ct);

            stopwatch.Stop();

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogPaymentFailed(orderId, stopwatch.Elapsed.TotalMilliseconds, errorBody, null);
                activity?.SetStatus(ActivityStatusCode.Error, "Payment Gateway Rejected Transaction");
                return false;
            }

            return true;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            _logger.LogWarning("Payment for order {OrderId} timed out.", orderId);
            activity?.SetStatus(ActivityStatusCode.Error, "Timeout");
            throw;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogPaymentFailed(orderId, stopwatch.Elapsed.TotalMilliseconds, ex.Message, ex);
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            throw;
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Format Log: Plain Text vs JSON vs Protobuf (OTLP)

```
+-------------------------------------------------------------------------------+
| PERBANDINGAN STRUKTUR TELEMETRI LOGGING                                       |
+-------------------+-----------------+--------------------+--------------------+
| Parameter         | Plain Text      | JSON (Structured)  | Protobuf (OTLP)    |
+-------------------+-----------------+--------------------+--------------------+
| Throughput        | Sangat Rendah   | Sedang - Tinggi    | Sangat Tinggi      |
| Parsing Overhead  | Sangat Berat    | Sedang (SIMD JSON) | Minimal (Binary)   |
| Human Readability | Langsung Dibaca | Cukup Terbaca      | Perlu Tooling      |
| Alokasi Memori    | Tinggi (String) | Sedang (GC Gen0)   | Sangat Rendah      |
| Storage Footprint | 1x (Baseline)   | 1.5x - 2x          | 0.3x - 0.5x        |
+-------------------+-----------------+--------------------+--------------------+
```

### Trace Sampler Trade-Offs

```
AlwaysOn (100% Trace)
├── Keuntungan: Audit trail absolut, tidak ada missing anomaly.
└── Kerugian  : Network saturation, CPU cycle terbuang untuk serialization, biaya storage awan masif.

TraceIdRatioBasedSampler (e.g., 5%)
├── Keuntungan: Penggunaan CPU terprediksi, overhead bandwidth stabil.
└── Kerugian  : Bug edge-case frekuensi rendah (1 banding 100.000) berisiko tidak terekam dalam trace.
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Async Scope Bleeding (Activity.Current Leak):**
   * *Masalah:* `Activity.Current` mengalir melalui `AsyncLocal<T>`. Jika Anda menggunakan background thread fire-and-forget tanpa melepaskan context (`ExecutionContext.SuppressFlow()`), span trace dapat terasosiasi dengan trace request lama yang sudah selesai.
   * *Mitigasi:*
     ```csharp
     using (ExecutionContext.SuppressFlow())
     {
         _ = Task.Run(() => BackgroundJobWorker());
     }
     ```
2. **Cardinality Explosion pada Metrics Tags:**
   * *Masalah:* Memasukkan data berdimensi unik tanpa batas (seperti `UserId`, `OrderId`, atau Timestamp) ke dalam Tag/Dimension `Counter` atau `Histogram`.
   * *Dampak:* Database Time-Series (seperti Prometheus) akan mengalami Out-Of-Memory (OOM) crash karena harus mempertahankan jutaan kombinasi time-series baru secara terus menerus.
   * *Aturan Emas:* Tag metrik HANYA untuk bounded-values berkarakteristik enum (status code, http method, region, failure category).
3. **High-Frequency Deadlocks akibat Synchronous Logging:**
   * Menulis log langsung ke File atau Network disk secara sinkron (`AutoFlush = true` pada volume besar). Kestrel thread worker akan terblokir menunggu I/O disk, memicu Thread Pool Starvation.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. String Interpolation di dalam ILogger
❌ **Salah (Anti-Pattern):**
```csharp
// Mengalokasikan string baru di heap terlepas dari apakah LogLevel.Debug aktif atau tidak!
_logger.LogDebug($"Processing payment for user: {user.Id} with payload: {user.Payload}");
```
✔️ **Benar:**
```csharp
// Source Generator hanya mengeksekusi ekstraksi data jika level Debug diaktifkan
[LoggerMessage(EventId = 2001, Level = LogLevel.Debug, Message = "Processing payment for user: {UserId}")]
public static partial void LogUserPayment(this ILogger logger, string userId);
```

### 2. Hilangnya Konteks Tracing pada HTTP Client
❌ **Salah:** Menginstansiasi `new HttpClient()` mentah tanpa handlers.
✔️ **Benar:** Gunakan `AddHttpClient()` di DI container. OpenTelemetry secara otomatis meregistrasikan `DiagnosticsHandler` yang bertugas melakukan inject header `traceparent` ke setiap outgoing HTTP request.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan OpenTelemetry Semantic Conventions:**
   * Selalu gunakan nama atribut standar dari spesifikasi OpenTelemetry:
     * `http.response.status_code` (bukan `StatusCode` atau `http_code`)
     * `server.address` (bukan `hostname` atau `domain`)
     * `db.statement` (bukan `sql_query`)
2. **Redaksi Data Sensitif (PII Scrubbing):**
   * Jangan pernah memasukkan kata sandi, CVV, Authorization token, atau NIK/SSN ke dalam log parameters atau Activity Tags.
3. **Konfigurasi Batching Processor pada Production:**
   * Gunakan `BatchExportProcessor` alih-alih `SimpleExportProcessor`. Batch processor menggunakan bounded memory queue dan memproses pengiriman telemetri secara asinkron di background thread khusus.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Profil komparasi alokasi logging per 100.000 iterasi:

```csharp
// BenchmarkDotNet Simulation Pattern
public class LoggingBenchmark
{
    private readonly ILogger<LoggingBenchmark> _logger;

    // Standard Logging: Alokasi ~3.2 MB memori, 42ms runtime
    public void StandardInterpolatedLogging()
    {
        for (int i = 0; i < 100_000; i++)
        {
            _logger.LogInformation("Transaction {Id} status {Status}", i, "Approved");
        }
    }

    // LoggerMessage Source Generator: Alokasi 0 Bytes Heap, 8ms runtime
    public void HighPerformanceSourceGenLogging()
    {
        for (int i = 0; i < 100_000; i++)
        {
            _logger.LogTransactionStatus(i, "Approved");
        }
    }
}
```

### Pengaturan GC & Thread Allocation
Pastikan OTel batching exporter diatur agar tidak memicu thread thrashing:
```csharp
builder.Services.AddOpenTelemetry().WithTracing(t => t.AddOtlpExporter(opt =>
{
    opt.BatchExportProcessorOptions = new OpenTelemetry.BatchExportProcessorOptions<Activity>
    {
        MaxQueueSize = 2048,
        ScheduledDelayMilliseconds = 5000,
        ExporterTimeoutMilliseconds = 30000,
        MaxExportBatchSize = 512
    };
}));
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitisasi Log Injection (Log Forging):**
   * Karakter line-break (`\r\n`) dalam input pengguna yang tidak divalidasi dapat memecah log entry pada sistem unstructured plain-text, memungkinkan attacker memalsukan jejak log seolah-olah berasal dari sistem keamanan. Structured Logging (JSON) secara inheren melindungi dari kerentanan ini karena string di-encode secara literal.
2. **Koleksi Dump yang Aman:**
   * Memory dump (`dotnet-dump`) mengandung representasi biner mentah dari memory heap, termasuk kunci enkripsi, string koneksi, dan data pengguna dalam plaintext.
   * *Hardening Policy:*
     * Wajib enkripsi file `.dmp` menggunakan AES-256 secara langsung setelah diekstraksi.
     * Batasi hak akses direktori penyimpanan dump pada pod hanya untuk user `root` / sistem kernel Linux via POSIX permission `chmod 600`.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Diagnostic CLI Toolkit Guide (Live Production Incident)

Saat aplikasi bermasalah di environment produksi Linux Container tanpa IDE:

#### 1. Identifikasi Process ID (PID)
```bash
$ dotnet-tool run dotnet-trace ps
# Atau jika diinstal global:
$ dotnet-trace ps
  1432  dotnet  /app/Enterprise.Api
```

#### 2. Investigasi Real-Time CPU & GC Metrics
```bash
$ dotnet-counters monitor --process-id 1432 --counters System.Runtime,Microsoft.AspNetCore.Hosting
```
*Output:*
```text
[System.Runtime]
    % Time in GC since last GC (%)                      85   <-- BAHAYA: GC Thrashing!
    CPU Usage (%)                                       99.8
    Allocated Bytes / Min                           42.5 MB
    ThreadPool Completed Work Item Count             1,234
    ThreadPool Queue Length                             89   <-- Thread starvation
```

#### 3. Mengambil Runtime CPU Flame Graph
```bash
$ dotnet-trace collect --process-id 1432 --format Speedscope --duration 00:00:30
# Hasil tracing (.speedscope.json) dapat dibuka di https://www.speedscope.app untuk mencari hotspot bottleneck CPU.
```

#### 4. Ekstraksi Memory Crash Dump
Jika aplikasi mengalami Memory Leak atau Deadlock:
```bash
$ dotnet-dump collect --process-id 1432 --type Full -o /tmp/app_deadlock.dmp
$ dotnet-dump analyze /tmp/app_deadlock.dmp
```
*Perintah esensial di dalam prompt analyze:*
* `clrthreads`: Menampilkan daftar semua managed thread beserta status lock-nya.
* `dumpheap -stat`: Menganalisis komposisi tipe data terbesar di GC Heap.
* `syncblk`: Memeriksa objek sinkronisasi monitoryang terkunci (Deadlock detection).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-------------------------------------------------------------------------------+
|                      ENTERPRISE OBSERVABILITY CHEAT SHEET                     |
+-------------------+-----------------------------------------------------------+
| Konsep            | Sintaks / Komponen Kunci                                  |
+-------------------+-----------------------------------------------------------+
| Source Gen Logger | [LoggerMessage(EventId, LogLevel, Message)]               |
| Trace Emitter     | ActivitySource.StartActivity("Name", ActivityKind.Server) |
| Metric Counter    | Meter.CreateCounter<long>("name", "unit")                 |
| Metric Histogram  | Meter.CreateHistogram<double>("name", "ms")               |
| W3C Propagation   | traceparent: 00-{traceid}-{spanid}-{flags}                |
| OTLP Endpoint     | Default: gRPC 4317, HTTP Protobuf 4318                    |
| CPU Profiling CLI | dotnet-trace collect -p <PID>                             |
| Live Metrics CLI  | dotnet-counters monitor -p <PID>                          |
| Memory Dump CLI   | dotnet-dump collect -p <PID> --type Full                  |
+-------------------+-----------------------------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Tingkat Dasar (Basic)

1. **Apa fungsi utama dari header `traceparent` dalam arsitektur distributed tracing?**
   * A. Menyimpan access token JWT untuk otentikasi antar-service.
   * B. Mengalirkan TraceId, Parent SpanId, dan Sampling Flags melintasi batas jaringan untuk mengkorelasikan operasi terdistribusi.
   * C. Menentukan rute load balancer pada ingress controller.
   * D. Melakukan enkripsi end-to-end pada body payload HTTP.

2. **Mengapa penggunaan `[LoggerMessage]` source generator lebih cepat dibandingkan `ILogger.LogInformation` standar?**
   * A. Karena langsung mengeksekusi penulisan ke socket OS secara parallel.
   * B. Karena menghindari string parsing runtime, mencegah alokasi array `object[]`, dan menghilangkan alokasi boxing untuk value-type.
   * C. Karena log secara otomatis disimpan ke local disk tanpa kompresi.
   * D. Karena mematikan fitur sanitasi teks pada framework logging.

3. **Komponen OpenTelemetry mana yang bertugas mendefinisikan instrumen pengukuran metrik di BCL .NET?**
   * A. `System.Diagnostics.Metrics.Meter`
   * B. `System.Diagnostics.ActivitySource`
   * C. `OpenTelemetry.Exporter.Console`
   * D. `Microsoft.Extensions.Logging.ILogger`

4. **Karakteristik metrik apa yang terjadi jika Anda memasukkan `OrderId` unik sebagai Tag ke dalam Prometheus Counter?**
   * A. Deadlock Exception
   * B. Buffer Overflow
   * C. Cardinality Explosion
   * D. NullReferenceException

5. **Tool .NET CLI apa yang digunakan untuk melihat statistik pemakaian CPU dan alokasi memori GC secara live tanpa profiling overhead tinggi?**
   * A. `dotnet-build`
   * B. `dotnet-counters`
   * C. `dotnet-watch`
   * D. `dotnet-test`

---

### Tingkat Menengah (Intermediate)

6. **Kapan instance `Activity` yang dihasilkan oleh `ActivitySource.StartActivity()` bernilai `null`?**
   * A. Ketika terjadi network disconnection ke database.
   * B. Ketika tidak ada `ActivityListener` yang terdaftar atau sampling policy memutuskan untuk tidak me-record span tersebut.
   * C. Ketika aplikasi dieksekusi di bawah mode `Release`.
   * D. Ketika waktu eksekusi melebihi batas timeout 5 detik.

7. **Apa risiko arsitektural jika mengimplementasikan `SimpleExportProcessor` alih-alih `BatchExportProcessor` pada aplikasi produksi dengan trafik tinggi?**
   * A. Request HTTP akan diblokir secara sinkron setiap kali log atau span dikirimkan ke OTel Collector, menyebabkan lonjakan drastis pada latensi sistem.
   * B. Data tracing akan hilang secara permanen karena tidak ada mekanisme retry.
   * C. Garbage Collector tidak akan pernah membersihkan heap Gen2.
   * D. File binary aplikasi akan terkunci oleh operating system.

8. **Bagaimana cara mencegah memory leak konteks `Activity.Current` pada operasi fire-and-forget asynchronous background task?**
   * A. Memanggil `GC.Collect()` secara paksa sebelum spawn thread.
   * B. Menggunakan `ExecutionContext.SuppressFlow()` untuk mencegah inheritance context ke child thread.
   * C. Mengubah method menjadi synchronous blocking (`.GetAwaiter().GetResult()`).
   * D. Menyetel `Activity.Current = null` di dalam controller endpoint.

9. **Ketika menganalisis memory dump menggunakan `dotnet-dump analyze`, perintah apa yang digunakan untuk mengidentifikasi keberadaan thread yang terkunci dalam status circular deadlock?**
   * A. `dumpheap -stat`
   * B. `pe`
   * C. `syncblk`
   * D. `gchandles`

10. **Apa perbedaan fungsional mendasar antara trace `Tag` dan trace `Baggage` pada OpenTelemetry?**
    * A. `Tag` hanya dikirim ke Jaeger, sedangkan `Baggage` dikirim ke Prometheus.
    * B. `Tag` bersifat lokal pada Span yang bersangkutan, sedangkan `Baggage` otomatis dipropagasikan melintasi service downstream melalui header HTTP (`baggage`).
    * C. `Tag` hanya mendukung data integer, sedangkan `Baggage` mendukung format XML.
    * D. `Tag` dievaluasi saat runtime, sedangkan `Baggage` dievaluasi saat compile-time.

---

### Kunci Jawaban Kuis

1. **B** — Header `traceparent` mengimplementasikan standar W3C untuk menjaga kontinuitas identitas trace di berbagai node infrastruktur.
2. **B** — Source generation mengalihkan pembuatan parser ke waktu kompilasi dan memanfaatkan typed-struct templates.
3. **A** — `Meter` adalah factory class resmi dari BCL runtime untuk instrumen pengukuran numerik.
4. **C** — Cardinality Explosion terjadi ketika kombinasi unik label melebihi kapasitas memori time-series engine.
5. **B** — `dotnet-counters` mengonsumsi EventCounters/Meter secara ringan melalui runtime IPC socket.
6. **B** — Mengurangi alokasi: jika exporter atau listener tidak mendengarkan, engine OTel mengembalikan `null`.
7. **A** — `SimpleExportProcessor` mengekspor data secara inline/sinkron pada calling thread.
8. **B** — `SuppressFlow()` menghentikan propagasi context `AsyncLocal` yang mengikat alur eksekusi.
9. **C** — `syncblk` (Synchronization Block Table) menampilkan thread ownership dan waiter list pada sync blocks.
10. **B** — Baggage melintasi batas jaringan (*in-band propagation*); Tags bersifat scoped ke current span.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Skenario Proyek: Fault-Tolerant Distributed Invoicing Engine

Bangun sebuah ASP.NET Core Web API mandiri yang mensimulasikan sistem penagihan faktur enterprise dengan spesifikasi berikut:

#### Kebutuhan Fungsional & Non-Fungsional:
1. **Instrumentasi Tracing Kustom:**
   * Buat `ActivitySource` bernama `Enterprise.Invoicing`.
   * Pada rute `POST /api/invoices/process`, buat Parent Span `ProcessInvoice`.
   * Jika nilai invoice > Rp 100.000.000, tandai span dengan atribut `invoice.is_priority = true`.
   * Simulasikan child operation dengan sub-span `ValidateTaxRegistration` dan `PersistToDatabase`.
2. **High-Performance Logging Source Generation:**
   * Jangan gunakan interpolated string logging. 
   * Definisikan class partial `InvoiceLogger` dengan event untuk:
     * `InvoiceReceived(string invoiceId, decimal amount)`
     * `InvoiceRejected(string invoiceId, string validationError)`
3. **Kustom Metrik BCL:**
   * Definisikan `Meter` bernama `Enterprise.Invoicing`.
   * Implementasikan `Counter<long>` untuk menghitung `invoices.processed.total` dengan atribut `status` (`success` / `failed`).
   * Implementasikan `Histogram<double>` untuk mengukur latensi pemrosesan database.
4. **OpenTelemetry OTLP Exporter:**
   * Konfigurasikan OTel SDK di `Program.cs` agar mengekspor seluruh telemetri ke endpoint lokal OTLP collector (`http://localhost:4317`).
5. **Production Incident Simulation & Diagnostic Task:**
   * Buat endpoint tersembunyi `POST /api/diagnostics/leak-memory` yang menambahkan `byte[]` 10MB ke `static List<byte[]>` setiap kali dipanggil.
   * Jalankan aplikasi melalui CLI (`dotnet run -c Release`).
   * Gunakan tool `dotnet-counters` untuk memantau peningkatan heap size.
   * Ekstrak dump menggunakan `dotnet-dump collect`.
   * Jalankan `dotnet-dump analyze` dan tuliskan analisis: tipe data apa yang memakan memori terbesar di heap beserta alamat referensinya!