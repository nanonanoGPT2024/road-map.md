# Bab 01: Arsitektur Fundamental ASP.NET Core & Host Lifecycle
## Modul 01: Inisialisasi Runtime, WebApplicationBuilder, Kestrel Server, dan Middleware Pipeline Core

---

### 1. Executive Summary & Learning Objectives

Modul ini membedah arsitektur dasar dari ASP.NET Core modern (.NET 8/9). Pembahasan berfokus pada siklus hidup inisialisasi aplikasi melalui Generic Host, konfigurasi `WebApplicationBuilder`, mekanisme internal web server Kestrel, serta eksekusi request melalui delegasi middleware pipeline (`RequestDelegate`).

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
* **Menganalisis (Analyze - C4)** siklus hidup bootstrapping aplikasi mulai dari `Program.cs`, transisi `WebApplicationBuilder` menuju `WebApplication`, hingga terminasi graceful host runtime.
* **Mengonfigurasi (Apply - C3)** Kestrel Web Server pada level socket transport, limitasi threadpool, dan opsi TLS untuk menangani beban konkurensi tinggi.
* **Merancang (Create - C6)** custom middleware pipeline dengan pemahaman mendalam terkait memory allocations, short-circuiting, dan mutasi downstream `HttpContext`.
* **Mengevaluasi (Evaluate - C5)** alokasi objek per-request, transient garbage collection impact, serta pencegahan common pitfalls seperti *synchronous I/O antipatterns* dan *service locator leaks*.

---

### 2. Conceptual Architecture & The "Why"

ASP.NET Core dirancang ulang secara modular dari pendahulunya (.NET Framework / System.Web) untuk mengatasi bottleneck performa struktural: kopling erat terhadap IIS (System.Web.dll), alokasi memori tinggi per-request (monolithic `HttpContext`), ketiadaan runtime modular, dan arsitektur yang tidak mendukung multiplatform.

```
+-----------------------------------------------------------------------+
|                         ASP.NET Framework                             |
|  [System.Web.dll] -> Hard-coupled to IIS -> High Memory Footprint    |
+-----------------------------------------------------------------------+
                                  VS
+-----------------------------------------------------------------------+
|                          ASP.NET Core                                 |
|  [Any OS] -> Kestrel / HTTP.sys -> Modular Pipeline -> Pure DI Host   |
+-----------------------------------------------------------------------+
```

Alasan adopsi arsitektur modern ASP.NET Core:
1. **Separation of Concerns via Generic Host**: Pemisahan konfigurasi aplikasi (DI, configuration provider, logging) dari web server abstraction, memungkinkan codebase yang sama dijalankan sebagai web application, background worker daemon, atau queue processor.
2. **Zero-Overhead Principle**: Anda hanya membayar apa yang Anda gunakan (*pay-for-play*). Middleware pipeline dibangun secara eksplisit; jika aplikasi Anda hanya melayani JSON API, modul session, static files, dan cookie engine tidak akan pernah dialokasikan di pipeline.
3. **High-Performance Kestrel Engine**: Kestrel dibangun di atas abstraksi Socket API platform-level (atau `io_uring` / `libuv`) yang meminimalkan context switching CPU dan memanfaatkan alokasi memori berbasis `ArrayPool` dan `System.IO.Pipelines`.

---

### 3. The "What" (Technical Anatomy & Mechanics)

Anatomi aplikasi ASP.NET Core terdiri dari komponen-komponen utama:

* **Entry Point (`Program.cs`)**: Titik awal eksekusi OS process. Menggunakan modern C# Top-Level Statements.
* **`WebApplicationBuilder`**: Wrapper yang bertanggung jawab mengonsolidasikan empat pilar bootstrapping sebelum host dikunci:
  * `IServiceCollection` (Kontrak Service Descriptor)
  * `ConfigurationManager` (Chaining file `.json`, Environment Variables, Key Vaults)
  * `ILoggingBuilder` (Sink logs: Console, OpenTelemetry, Debug)
  * `IWebHostEnvironment` (Deteksi Development, Staging, Production)
* **`WebApplication`**: Objek konkret hasil kompilasi builder via method `.Build()`. Mengimplementasikan `IHost`, `IApplicationBuilder`, dan `IEndpointRouteBuilder`. Objek ini immutable dalam konteks modifikasi DI container.
* **Kestrel Web Server**: Web server HTTP berbasis event-driven I/O asynchronous yang menerima raw TCP bytes dari socket, mem-parsing format RFC (HTTP/1.1, HTTP/2, HTTP/3), dan membungkusnya ke dalam struktur `HttpContext`.
* **Request Processing Pipeline**: Rantai eksekusi dua arah (*two-way pipeline*) berbasis delegasi `Func<RequestDelegate, RequestDelegate>`. Setiap node middleware memiliki kontrol penuh untuk memproses request sebelum diteruskan (`next()`), memodifikasi response, atau menghentikan eksekusi (*short-circuiting*).

---

### 4. Detailed ASCII Architectural Diagram

Diagram berikut memetakan alur fisik data dari level network socket OS hingga penanganan internal di ASP.NET Core pipeline:

```
[ Inbound TCP Socket Connection ]
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Kestrel Web Server Engine                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Socket Transport Layer (SocketReceiver / PipeWriter)  │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │ Read Pipe (ReadOnlySequence)  │
│  ┌──────────────────────────▼────────────────────────────┐  │
│  │ HTTP Parser (HTTP/1.1, HTTP/2, HTTP/3 Frame Decoder) │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │ Creates / Leases               │
│  ┌──────────────────────────▼────────────────────────────┐  │
│  │ Feature Collection Pooling (Provides HttpContext)     │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                       Dispatches HttpContext
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Middleware Pipeline (IApplicationBuilder Execution Tree)    │
│                                                             │
│       ┌──────────────────────┐                              │
│       │ ExceptionHandler     │                              │
│       └──────────┬───────────┘                              │
│         [Next()] │ ▲ [Catch/Transform]                      │
│                  ▼ │                                        │
│       ┌────────────┴─────────┐                              │
│       │ Routing Middleware   │                              │
│       └──────────┬───────────┘                              │
│         [Next()] │ ▲                                        │
│                  ▼ │                                        │
│       ┌────────────┴─────────┐                              │
│       │ Custom Auth / Header │                              │
│       └──────────┬───────────┘                              │
│         [Next()] │ ▲                                        │
│                  ▼ │                                        │
│       ┌────────────┴─────────┐                              │
│       │ Endpoint Execution   │ ── Short-Circuit (Returns)   │
│       └──────────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. The "How" (Step-by-step Implementation Pipeline)

Membangun fondasi host pipeline ASP.NET Core mengikuti tahapan deterministik:

1. **Instansiasi Host Initialization Engine**: Inisialisasi instance `WebApplicationBuilder` menggunakan method statis `WebApplication.CreateBuilder(args)`.
2. **Kustomisasi Server Infrastructure (Kestrel Options)**: Konfigurasi batas buffer, ukuran payload, koneksi limit, dan bind address (IP/Port).
3. **Registrasi Service Catalog**: Definisikan dependency lifetime (`Transient`, `Scoped`, `Singleton`) ke dalam `builder.Services`.
4. **Finalisasi Instansiasi Aplikasi (`.Build()`)**: Freeze service provider. Container DI beralih ke mode *read-only*.
5. **Konstruksi Pipeline Middleware**: Tentukan urutan (*order of execution*) modul middleware. Urutan deklarasi menentukan urutan eksekusi request dan kebalikan dari urutan eksekusi response.
6. **Eksekusi Host Runtime (`.Run()`)**: Kestrel melakukan binding ke TCP socket listener dan memproses request secara non-blocking via threadpool.

---

### 6. Minimal Reproducible Example

Berikut adalah implementasi standalone menggunakan pola C# modern yang menunjukkan inisialisasi host, custom low-overhead inline middleware, dan routing endpoint.

```csharp
// Program.cs
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);

// 1. Service Registrations
builder.Services.AddEndpointsApiExplorer();

// Konfigurasi internal Kestrel secara eksplisit
builder.WebHost.ConfigureKestrel(serverOptions =>
{
    serverOptions.AddServerHeader = false; // Security hardening: Hapus header Server: Kestrel
    serverOptions.Limits.MaxRequestBodySize = 10 * 1024 * 1024; // 10 Megabytes
});

var app = builder.Build();

// 2. Middleware Orchestration
// Inline Custom Middleware: Profiling Execution Time
app.Use(async (context, next) =>
{
    var startTimestamp = System.Diagnostics.Stopwatch.GetTimestamp();

    // Lanjutkan eksekusi ke middleware downstream
    await next(context);

    // Proses fase return / response
    var elapsed = System.Diagnostics.Stopwatch.GetElapsedTime(startTimestamp);
    context.Response.Headers.Append("X-Execution-Time", $"{elapsed.TotalMilliseconds:F4}ms");
});

// 3. Terminal Endpoint
app.MapGet("/api/health", () => TypedResults.Ok(new 
{ 
    Status = "Healthy", 
    TimestampUtc = DateTimeOffset.UtcNow 
}));

app.Run();
```

---

### 7. Production-Grade Enterprise Scenario

Kasus dunia nyata: Membangun Web Core Gateway dengan proteksi Kestrel Socket, correlation tracking via scoped contexts, graceful lifecycle event handling, dan middleware isolasi error yang mematuhi standar RFC 7807 (ProblemDetails).

#### Directory Structure:
```
CoreArchitecture/
├── Middlewares/
│   ├── CorrelationIdMiddleware.cs
│   └── GlobalExceptionHandlingMiddleware.cs
├── Infrastructure/
│   └── HostLifecycleObserver.cs
└── Program.cs
```

#### File: `Middlewares/CorrelationIdMiddleware.cs`
```csharp
namespace CoreArchitecture.Middlewares;

public sealed class CorrelationIdMiddleware
{
    private const string CorrelationHeader = "X-Correlation-Id";
    private readonly RequestDelegate _next;

    public CorrelationIdMiddleware(RequestDelegate next)
    {
        _next = next ?? throw new ArgumentNullException(nameof(next));
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // 1. Ambil atau buat ID korelasi baru
        if (!context.Request.Headers.TryGetValue(CorrelationHeader, out var correlationId) || 
            string.IsNullOrWhiteSpace(correlationId))
        {
            correlationId = Guid.NewGuid().ToString("N");
        }

        // 2. Simpan di HttpContext.Items untuk dependensi runtime downstream
        context.Items[CorrelationHeader] = correlationId.ToString();

        // 3. Inject kembali ke Response Headers menggunakan OnStarting callback (aman dari streaming lock)
        context.Response.OnStarting(() =>
        {
            context.Response.Headers[CorrelationHeader] = correlationId.ToString();
            return Task.CompletedTask;
        });

        await _next(context);
    }
}
```

#### File: `Middlewares/GlobalExceptionHandlingMiddleware.cs`
```csharp
using System.Net;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;

namespace CoreArchitecture.Middlewares;

public sealed class GlobalExceptionHandlingMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<GlobalExceptionHandlingMiddleware> _logger;

    public GlobalExceptionHandlingMiddleware(RequestDelegate next, ILogger<GlobalExceptionHandlingMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception occurred: {Message}", ex.Message);
            await HandleExceptionAsync(context, ex);
        }
    }

    private static async Task HandleExceptionAsync(HttpContext context, Exception exception)
    {
        // Jika response stream sudah terkirim sebagian (headers sent), throw ke runtime
        if (context.Response.HasStarted)
        {
            throw new InvalidOperationException("Headers already sent, cannot write error payload.", exception);
        }

        context.Response.Clear();
        context.Response.StatusCode = (int)HttpStatusCode.InternalServerError;
        context.Response.ContentType = "application/problem+json";

        var problemDetails = new ProblemDetails
        {
            Status = context.Response.StatusCode,
            Title = "An unexpected internal fault occurred.",
            Detail = "The server encountered an unrecoverable state.",
            Instance = context.Request.Path
        };

        if (context.Items.TryGetValue("X-Correlation-Id", out var correlationId))
        {
            problemDetails.Extensions["correlationId"] = correlationId;
        }

        var json = JsonSerializer.Serialize(problemDetails);
        await context.Response.WriteAsync(json);
    }
}
```

#### File: `Infrastructure/HostLifecycleObserver.cs`
```csharp
namespace CoreArchitecture.Infrastructure;

public sealed class HostLifecycleObserver : IHostedService
{
    private readonly IHostApplicationLifetime _lifetime;
    private readonly ILogger<HostLifecycleObserver> _logger;

    public HostLifecycleObserver(IHostApplicationLifetime lifetime, ILogger<HostLifecycleObserver> logger)
    {
        _lifetime = lifetime;
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _lifetime.ApplicationStarted.Register(OnStarted);
        _lifetime.ApplicationStopping.Register(OnStopping);
        _lifetime.ApplicationStopped.Register(OnStopped);

        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;

    private void OnStarted() => _logger.LogInformation("LIFECYCLE: Application engine initialized and listening for traffic.");
    private void OnStopping() => _logger.LogWarning("LIFECYCLE: SIGTERM received. Drainage of in-flight connections initiated.");
    private void OnStopped() => _logger.LogCritical("LIFECYCLE: Execution halted. All host resources unallocated.");
}
```

#### File: `Program.cs`
```csharp
using CoreArchitecture.Infrastructure;
using CoreArchitecture.Middlewares;

var builder = WebApplication.CreateBuilder(args);

// Configure Hardware & Socket Limits via Kestrel Engine
builder.WebHost.ConfigureKestrel(options =>
{
    options.Limits.MaxConcurrentConnections = 50_000;
    options.Limits.MaxConcurrentUpgradedConnections = 10_000;
    options.Limits.Http2.MaxStreamsPerConnection = 250;
    options.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(2);
    options.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(15);
});

// Service IoC Registrations
builder.Services.AddHostedService<HostLifecycleObserver>();

var app = builder.Build();

// ---------------------- PIPELINE ORDERING STRICT ENFORCEMENT ----------------------
// 1. Error Handler Middleware berada di paling luar untuk menangkap failure downstream
app.UseMiddleware<GlobalExceptionHandlingMiddleware>();

// 2. Correlation Tracking & Context Initialization
app.UseMiddleware<CorrelationIdMiddleware>();

// 3. Routing Engine
app.UseRouting();

// 4. Secured Business Logic Execution Endpoint
app.MapGet("/api/order-dispatch", async (HttpContext context) =>
{
    // Simulasi operational task non-blocking
    await Task.Delay(10);
    
    return TypedResults.Ok(new 
    { 
        TrackingNumber = Guid.NewGuid().ToString("D"),
        NodeExecutionTimeUtc = DateTime.UtcNow 
    });
});

await app.RunAsync();
```

---

### 8. Edge Cases, Failure Modes & Defensive Engineering

* **Response Already Started**: Jika exception terjadi setelah byte response pertama dikirim ke client (`context.Response.HasStarted == true`), middleware tidak dapat memodifikasi status code atau menulis body `ProblemDetails`. Tindakan defensif: Cek `HasStarted` sebelum memanggil `Response.Clear()` atau `WriteAsync()`.
* **Async Short-Circuiting Memory Leak**: Middleware yang mengeksekusi blocking call synchronous (misal: `.Wait()` atau `.Result` pada async task) di dalam pipeline akan mengakibatkan **Thread Pool Starvation**. Hindari penggunaan I/O sync secara mutlak; gunakan async non-blocking method hingga level transport (`Stream.ReadAsync`).
* **SIGTERM vs Kubernetes Termination Grace Period**: Default graceful shutdown ASP.NET Core adalah 30 detik. Jika orchestrator mematikan pod dalam 10 detik, in-flight request akan diputus paksa. Konfigurasikan:
  ```csharp
  builder.Services.Configure<HostOptions>(opts => opts.ShutdownTimeout = TimeSpan.FromSeconds(45));
  ```

---

### 9. Performance Profiling & Memory Footprint Considerations

* **`HttpContext` Lifespan Scope & Thread Safety**: Objek `HttpContext` dipool oleh Kestrel untuk menghindari alokasi GC Gen0/Gen1 yang masif. **`HttpContext` TIDAK thread-safe**. Jika thread background memproses konteks tanpa menyalin state, data akan tertimpa saat koneksi berikutnya meminjam slot tersebut dari context pool.
* **Synchronous I/O Overhead**: Secara default, Kestrel melarang Synchronous I/O:
  ```csharp
  // JANGAN UBAH INI KECUALI LEGACY CRITICAL DEPENDENCY:
  options.AllowSynchronousIO = false; 
  ```
  Mengaktifkan sync I/O dapat memblok thread worker Kestrel dan menurunkan *Request Per Second* (RPS) dari 100k+ ke hitungan ratusan akibat starvation.

---

### 10. Security Hardening & Zero-Trust Vector Analysis

1. **Information Leakage via Protocol Headers**: Kestrel secara default dapat menambahkan server signature (`Server: Kestrel`). Hilangkan jejak arsitektural ini untuk mencegah OS fingerprinting:
   ```csharp
   serverOptions.AddServerHeader = false;
   ```
2. **Slowloris Mitigation**: Penyerang membuka ratusan koneksi TCP dan mengirimkan header HTTP dengan sangat lambat untuk menghabiskan socket handler. Kestrel memitigasi ini dengan enforcing minimum data rates:
   ```csharp
   serverOptions.Limits.MinRequestBodyDataRate = new MinDataRate(bytesPerSecond: 240, gracePeriod: TimeSpan.FromSeconds(5));
   serverOptions.Limits.MinResponseDataRate = new MinDataRate(bytesPerSecond: 240, gracePeriod: TimeSpan.FromSeconds(5));
   ```
3. **Large Payload DoS**: Batasi alokasi payload request secara eksplisit:
   ```csharp
   serverOptions.Limits.MaxRequestBodySize = 2 * 1024 * 1024; // 2 MB
   ```

---

### 11. Anti-Patterns & Common Pitfalls

#### Anti-Pattern 1: Service Locator via HttpContext.RequestServices
*Bad Practice:*
```csharp
app.Use(async (context, next) =>
{
    // ANTI-PATTERN: Mengakses service manual via request services memutus analisis dependensi statis
    var dbContext = context.RequestServices.GetRequiredService<MyDbContext>();
    await dbContext.PerformWorkAsync();
    await next(context);
});
```
*Best Practice:* Gunakan scoped factory atau abstraksi factory yang di-inject melalui konstruktor standard class-based middleware atau parameter delegate endpoint injection:
```csharp
app.MapGet("/data", async (MyDbContext db) => await db.GetDataAsync());
```

#### Anti-Pattern 2: Captured Captive Dependencies
Mendaftarkan middleware berbasis instance (`app.UseMiddleware<MyMiddleware>()`) sebagai singleton tetapi menyuntikkan (inject) service berspesifikasi `Scoped` ke dalam konstruktornya:
```csharp
// Kesalahan Fatal:
public class MyMiddleware
{
    // Scoped service di dalam singleton constructor akan menyebabkan state Scoped 
    // menjadi abadi dan dishare antar user concurrent, mengakibatkan multithreading race condition!
    public MyMiddleware(RequestDelegate next, IScopedRepository repo) { ... }
}
```
*Perbaikan:* Inject scoped dependency ke dalam method `InvokeAsync(HttpContext context, IScopedRepository repo)`.

---

### 12. Architectural Trade-offs & Alternatives Matrix

| Pendekatan / Framework | Throughput / Overhead | Fleksibilitas Desain | Kompleksitas Infrastruktur | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **ASP.NET Core (Kestrel Edge Server)** | Ekstrem Tinggi (Direct Socket) | Tinggi (Modular Pipeline) | Rendah (Self-contained Process) | Microservices, High RPS APIs, Cloud-native deployments |
| **ASP.NET Core (Behind IIS / Reverse Proxy)** | Sedang-Tinggi (IPC/Loopback hop) | Menengah (IIS Intercepts) | Menengah-Tinggi (Konfigurasi OS level IIS) | Intranet Enterprise legacy, Windows Authentication spesifik |
| **Legacy ASP.NET (.NET 4.8 Framework)** | Rendah (Monolithic Object lifecycle) | Sangat Rendah (Blackbox system) | Sangat Tinggi (Terikat OS Windows) | Legacy codebase maintenance only |
| **FastEndpoints / Carter Layer** | Ekstrem Tinggi (Lightweight Routing wrapper) | Sangat Tinggi (Vertical Slice Architecture) | Rendah | Domain-Driven Design APIs berorientasi maintainability |

---

### 13. Deep Dive Internals / Under The Hood

Ketika paket TCP tiba di Network Interface Card (NIC):
1. **Socket Transport**: Native socket implementation menempatkan frame bytes ke memory buffer yang dialokasikan oleh `MemoryPool<byte>`.
2. **`PipeReader` Extraction**: Menggunakan `System.IO.Pipelines` untuk parsing streaming stream zero-allocation. Objek `PipeReader` memindai batas carriage return / line feed (`\r\n\n`) dari request header HTTP.
3. **`DefaultHttpContextFactory`**: ASP.NET Core mengambil instance `DefaultHttpContext` dari internal pool. Objek ini membungkus layer low-level tanpa mengalokasikan memori baru di Managed Heap jika pool slot tersedia.
4. **Execution Pipeline Chaining**: Delegasi internal `RequestDelegate` dijalankan. Karena rantai dibangun sekali di awal saat booting (berbentuk functional nested closure: `_next(_context)`), overhead pemanggilan middleware upstream-downstream hanyalah pointer jump antar method calls tanpa reflection traversal.

---

### 14. Observability, Telemetry & Diagnostics

Gunakan high-performance zero-allocation logging via source generators (`LoggerMessageAttribute`) dan instrumentasikan activity tracking:

```csharp
// Infrastructure/TelemetryDiagnostics.cs
using System.Diagnostics;

public static class DiagnosticsTelemetry
{
    public static readonly ActivitySource ActivitySource = new("Enterprise.CoreArchitecture", "1.0.0");
}

public static partial class LogExtensions
{
    [LoggerMessage(EventId = 1001, Level = LogLevel.Information, Message = "Inbound connection assigned from {ClientIp}")]
    public static partial void LogConnectionReceived(this ILogger logger, string clientIp);
}
```

Implementasi di endpoint atau middleware:
```csharp
app.Use(async (context, next) =>
{
    using var activity = DiagnosticsTelemetry.ActivitySource.StartActivity("CustomMiddlewareExecution");
    activity?.SetTag("http.client_ip", context.Connection.RemoteIpAddress?.ToString());

    await next(context);
});
```

---

### 15. Testing & Verification Strategies

ASP.NET Core menyediakan library `Microsoft.AspNetCore.Mvc.Testing` yang menjalankan in-memory WebApplication instance via `TestServer` tanpa perlu membuka physical TCP port:

```csharp
// Tests/PipelineIntegrationTests.cs
using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public class PipelineIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public PipelineIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Request_ShouldPassThrough_AndReturnCorrelationIdHeader()
    {
        // Act
        var response = await _client.GetAsync("/api/order-dispatch");

        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(response.Headers.Contains("X-Correlation-Id"));
        
        var correlationId = response.Headers.GetValues("X-Correlation-Id").FirstOrDefault();
        Assert.False(string.IsNullOrWhiteSpace(correlationId));
    }
}
```
*(Catatan: Pastikan `Program.cs` mengekspos visibilitas melalui internal visibility atau `public partial class Program { }` di akhir file).*

---

### 16. Ecosystem Integration & Dependencies

Integrasi stack production yang sering ditambahkan di fase host setup:
* **Logging Framework**: Serilog / OpenTelemetry Collector (`Serilog.AspNetCore`) menggantikan native console parser demi structural JSON log format.
* **Metrics Pipeline**: Prometheus via `prometheus-net.AspNetCore` menginjeksi metrics endpoint langsung ke Kestrel pipeline sebelum routing engine.
* **Reverse Proxy Orchestration**: `Yarp.ReverseProxy` (Yet Another Reverse Proxy), framework native yang berjalan langsung di atas Kestrel middleware pipeline untuk skenario high-throughput routing.

---

### 17. Operational Checklist (Production-Readiness)

* [ ] Kestrel Server Header dihapus (`AddServerHeader = false`).
* [ ] Parameter `MaxRequestBodySize` dikonfigurasi eksplisit sesuai kebutuhan fungsional payload.
* [ ] MinDataRate untuk read/write diaktifkan untuk proteksi serangan Slowloris.
* [ ] Forwarded Headers Middleware dikonfigurasi jika aplikasi berada di belakang reverse proxy (NGINX, Cloudflare, Traefik, AWS ALB).
* [ ] Graceful termination handling (`HostOptions.ShutdownTimeout`) disesuaikan dengan scheduler container platform (Kubernetes / ECS).
* [ ] Middleware pipeline order diverifikasi: Handling Exception $\rightarrow$ Correlation $\rightarrow$ HSTS $\rightarrow$ Routing $\rightarrow$ Auth $\rightarrow$ Endpoints.
* [ ] Tidak ada synchronous blocking code (`Task.Wait()`, `Task.Result`) di sepanjang alur middleware request processing.

---

### 18. Self-Assessment & Hands-on Challenges

#### Pertanyaan Konseptual:
1. Mengapa memanggil `context.Response.Headers.Add()` setelah memanggil `await _next(context)` berpotensi menimbulkan runtime exception? Bagaimana cara mengatasinya?
2. Jelaskan perbedaan mendasar siklus hidup instance class-based middleware konvensional dibanding class-based middleware yang mengimplementasikan `IMiddleware` interface!

#### Hands-on Challenge:
**Rancang Rate-Limiting Inline Middleware Sederhana**
* Bangun custom middleware yang menolak request (Status 429 Too Many Requests) jika IP yang sama melakukan lebih dari 5 request dalam jendela 10 detik.
* Gunakan `System.Collections.Concurrent.ConcurrentDictionary` atau `IMemoryCache`.
* Middleware harus menulis status response dan short-circuit (tidak memanggil `_next(context)`).

---

### 19. Further Reading & References

1. Microsoft Official Docs: *ASP.NET Core Architecture and Fundamentals*.
2. Fowler, David: *ASP.NET Core Diagnostic Scenarios & Asynchronous programming guidance* (GitHub dotnet/runtime repository).
3. Techempower Benchmarks: *Round 22 Web Framework Performance Insights (Round-trip Plaintext & JSON Kestrel tests)*.
4. Skeet, Jon: *Writing High-Performance .NET Code & Deep Dive into Async/Await Lifecycle*.

---

### 20. Conclusion & Next Step Preview

Anda telah menuntaskan pemahaman mendalam terkait runtime host lifecycle ASP.NET Core, internal processing Kestrel, dan manipulasi middleware pipeline flow. Pengetahuan ini adalah pondasi struktural sebelum melangkah ke abstraksi fungsional selanjutnya.

**Modul Berikutnya**: **Bab 01 - Modul 02: Advanced Dependency Injection Runtime Framework**, di mana kita akan membedah internal engine `Microsoft.Extensions.DependencyInjection`, ServiceDescriptor storage, Garbage Collector impacts pada container lifecycle, serta deteksi Captive Dependencies secara otomatis di compile-time dan run-time.