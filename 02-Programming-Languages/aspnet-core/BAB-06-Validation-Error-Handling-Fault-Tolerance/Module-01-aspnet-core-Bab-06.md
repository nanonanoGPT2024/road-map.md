# BAB 06 MODULE 01: VALIDATION, ERROR HANDLING, & FAULT TOLERANCE

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum**: Backend Engineering with .NET & C#
*   **Kategori**: 02-Programming-Languages / ASP.NET Core
*   **Kode Modul**: `ASP-06-01`
*   **Tingkat Kesulitan**: Advanced / Enterprise-Grade
*   **Prasyarat**:
    *   Pemahaman mendalam mengenai ASP.NET Core Request Pipeline & Middleware.
    *   Penguasaan C# 12 (Pattern Matching, Records, Async/Await, Task Parallel Library).
    *   Familiaritas dengan Dependency Injection lifecycle (`Transient`, `Scoped`, `Singleton`).
    *   Dasar-dasar HTTP/RESTful API specs dan arsitektur Client-Server.
*   **Target Tech Stack**:
    *   .NET 8.0 SDK (LTS)
    *   C# 12
    *   `FluentValidation.AspNetCore` (v11.x)
    *   `Microsoft.Extensions.Resilience` / Polly v8 Core Engine
    *   RFC 7807 / RFC 9457 (Problem Details for HTTP APIs)

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mendiagnosis dan Mengisolasi Anomali Input**: Mengimplementasikan validasi deklaratif dan imperatif berlapis menggunakan Data Annotations dan FluentValidation pipeline untuk mencegah invalid domain states masuk ke core business logic.
2.  **Membangun Centralized Error Handling Terstandarisasi**: Mengonstruksi arsitektur penanganan pengecualian global menggunakan antarmuka .NET 8 `IExceptionHandler` dan memetakan domain exception ke representasi RFC 9457 *Problem Details* secara terstruktur tanpa kebocoran memori atau data sensitif.
3.  **Mendesain Resilient Distributed Communications**: Mengintegrasikan arsitektur *fault tolerance* modern via Polly v8 (`Microsoft.Extensions.Resilience`) menggunakan strategi *Retry with Exponential Backoff + Full Jitter*, *Circuit Breaker*, *Timeout*, *Bulkhead*, dan *Hedging*.
4.  **Mereduksi Blast Radius Kegagalan Sistem**: Menganalisis *transient faults* versus *non-transient faults* pada distributed networking calls untuk mengeliminasi potensi cascading failures di lingkungan produksi microservices.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Fail-Fast vs. Fault-Tolerant Dichotomy
Seorang software architect memandang sistem melalui lensa dua prinsip yang saling melengkapi:

1.  **Fail-Fast di Tepi Batas (System Boundary)**:
    Jika data input klien tidak valid, tolak seketika (*fail-fast*). Jangan biarkan alokasi memori berlebih, eksekusi query database, atau invoke API downstream terjadi untuk data yang cacat secara struktural atau semantik. Validasi adalah tameng terdepan.
2.  **Fault-Tolerant di Pusat Komunikasi (Distributed Core)**:
    Dalam sistem terdistribusi, jaringan dan layanan pihak ketiga *pasti* akan mengalami kegagalan (*fallacies of distributed computing*). Kesalahan jaringan bukanlah anomali, melainkan kondisi operasional normal. Oleh karena itu, sistem harus mengabsorpsi kegagalan sementara (*transient faults*) secara elegan tanpa memutus ketersediaan layanan (*high availability*).

```
                      BATAS SISTEM (EDGE)             PUSAT SISTEM (CORE)
                 +---------------------------+   +---------------------------+
Input Klien ---->|   PRINSIP: FAIL-FAST      |-->| PRINSIP: FAULT-TOLERANCE  |----> Downstream
                 | (Validasi Ketat, Reject   |   | (Absorpsi Transient Fault,|      Services
                 |  Immediately via RFC 9457)|   |  Circuit Breaker, Jitter) |
                 +---------------------------+   +---------------------------+
```

### Exception Bukan Alat Control-Flow
Exceptions di platform .NET dialokasikan pada Managed Heap dan memicu stack unwinding yang sangat membebani CPU cycles serta instruksi instruksi register pointer. Jangan pernah menggunakan exception untuk logika percabangan bisnis standar (*control flow*). Exception adalah sinyal bahwa terjadi kondisi anomali yang **tidak terduga** di luar domain invariant normal.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Inbound Request & Centralized Error Pipeline (ASP.NET Core .NET 8)
Diagram alur berikut mengilustrasikan bagaimana request diproses, divalidasi via Endpoint Filter / Action Filter, dieksekusi di Domain Core, dan di-intercept oleh `ExceptionHandlerMiddleware` modern via `IExceptionHandler`.

```
[ HTTP Client ]
      │
      ▼
[ Kestrel Web Server ]
      │
      ▼
[ ExceptionHandlerMiddleware ] ◄────────────────────────────────────────┐
      │ (Capture unhandled exceptions)                                  │
      ▼                                                                 │
[ Endpoint / Routing Middleware ]                                       │
      │                                                                 │
      ▼                                                                 │
[ Validation Filter (FluentValidation) ] ──(Invalid)──┐                 │
      │                                                │                │
      ├─► (Valid Input)                                ▼                │
      │                                       [ 400 ProblemDetails ]    │
      ▼                                                │                │
[ Controller / Minimal API Handler ]                   ▼                │
      │                                       [ Terminate Pipeline ]    │
      ▼                                                                 │
[ Application Service / Domain ]                                        │
      │                                                                 │
      ├─► (Domain Logic Succeeded) ──► [ 200 OK / 201 Created ]         │
      │                                                                 │
      └─► (Unhandled Domain Exception Thrown) ──────────────────────────┘
                                                       │
                                                       ▼
                                         [ Custom IExceptionHandler ]
                                                       │
                                                       ▼
                                         [ RFC 9457 ProblemDetails ]
                                                       │
                                                       ▼
                                            [ HTTP Response Out ]
```

### 2. Outbound Request via Polly v8 Resilience Pipeline
Ketika aplikasi memanggil remote downstream (misal: Payment Gateway API), request dialirkan melalui *composed resilience pipeline*.

```
[ Outbound HttpRequestMessage ]
      │
      ▼
[ Polly v8 Combined Resilience Pipeline ]
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Bulkhead / Rate Limiter (Batasi konkurensi eksekusi)      │
  │    │                                                        │
  │    ▼                                                        │
  │ 2. Total Timeout Strategy (Batasi total durasi panggilan)   │
  │    │                                                        │
  │    ▼                                                        │
  │ 3. Circuit Breaker Strategy (Isolasi jika downstream padam) │
  │    │                                                        │
  │    ▼                                                        │
  │ 4. Attempt Timeout Strategy (Timeout per percobaan request) │
  │    │                                                        │
  │    ▼                                                        │
  │ 5. Retry Strategy (Exponential Backoff + Full Jitter)       │
  └─────────────────────────────────────────────────────────────┘
      │
      ▼
[ HttpClientHandler (SocketsHttpHandler) ]
      │
      ▼
[ Jaringan / Downstream Microservice ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. ASP.NET Core .NET 8 `IExceptionHandler`
Sebelum .NET 8, global exception handling bergantung pada custom Middleware (`app.UseMiddleware<ExceptionHandlingMiddleware>()`) atau antarmuka `UseExceptionHandler` berbasis delegate. .NET 8 memperkenalkan antarmuka resmi:

```csharp
namespace Microsoft.AspNetCore.Diagnostics;

public interface IExceptionHandler
{
    ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken);
}
```

*   **Mekanisme Eksekusi**: `ExceptionHandlerMiddlewareImpl` menangkap semua *unhandled exceptions* yang bocor dari downstream middleware. Middleware ini mengambil koleksi terdaftar dari `IExceptionHandler` dari DI container dan mengeksekusinya secara berurutan.
*   **Short-Circuiting**: Jika method `TryHandleAsync` mengembalikan nilai `true`, pipeline menganggap exception telah selesai ditangani (*handled*). Jika mengembalikan `false`, runner akan melanjutkan ke instance `IExceptionHandler` berikutnya dalam rantai chain of responsibility.

### 2. RFC 9457 (Problem Details for HTTP APIs)
Menggantikan RFC 7807, RFC 9457 mendefinisikan skema JSON standar untuk menyampaikan metadata error:
*   `type`: URI reference (`string`) yang mengidentifikasi tipe masalah.
*   `title`: Ringkasan singkat yang dapat dibaca manusia (`string`). Tidak boleh berubah antar instansi error yang sama.
*   `status`: HTTP Status Code (`int`).
*   `detail`: Penjelasan spesifik manusia mengenai instansi error ini (`string`).
*   `instance`: URI reference (`string`) yang mengidentifikasi kejadian spesifik error (biasanya berisi request path atau correlation ID).
*   *Extensions*: Properti arbitrer tambahan seperti `traceId`, `errors` (array of validation failures), atau `errorCode`.

### 3. Polly v8 Engine Core (`ResiliencePipeline`)
Polly v8 merepresentasikan penulisan ulang arsitektur Polly yang berfokus pada:
*   **Zero-Allocation Path**: Menggunakan `ValueTask` dan mengurangi memory boxing yang masif di Polly v7.
*   **State Machine Pipeline**: Strategi dihubungkan menjadi state-machine berantai yang dieksekusi melalui delegate: `ResiliencePipeline.ExecuteAsync(Func<CancellationToken, ValueTask<T>> callback)`.
*   **Circuit Breaker State Transitions**:
    *   *Closed*: Request mengalir normal. Jika rasio kegagalan melewati threshold dalam sampling window, state berpindah ke *Open*.
    *   *Open*: Request langsung digagalkan seketika (`BrokenCircuitException`) tanpa menyentuh network layer. Menghindarkan downstream dari beban berlebih.
    *   *Half-Open*: Setelah durasi sleep window habis, sejumlah kecil request uji coba (*trial executions*) diizinkan. Jika berhasil, kembali ke *Closed*; jika gagal, kembali ke *Open*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Validation Paradigm: Data Annotations vs. FluentValidation
*   **Data Annotations (`System.ComponentModel.DataAnnotations`)**:
    *   *Kelebihan*: Deklaratif, built-in, metadata langsung melekat pada Class Properties.
    *   *Kelemahan*: Mengotori Data Transfer Object (DTO) dengan aturan validasi; sulit mengimplementasikan dependensi runtime (seperti pengecekan ke database); tidak mendukung conditional validation yang kompleks secara elegan.
*   **FluentValidation**:
    *   *Kelebihan*: Mengikuti *Single Responsibility Principle* (memisahkan model dari aturan validasi); ekosistem rich fluent syntax; mendukung cross-field validation kompleks; integrasi clean architecture murni; mudah diuji (*unit testing* validator terisolasi).

### Transient vs. Non-Transient Faults
Memahami klasifikasi error adalah prasyarat mutlak sebelum menentukan kebijakan fault tolerance:
1.  **Transient Faults**: Error yang bersifat sementara dan memiliki probabilitas tinggi untuk sukses jika dicoba kembali tanpa perubahan payload.
    *   *Contoh*: HTTP 408 (Request Timeout), HTTP 503 (Service Unavailable), HTTP 504 (Gateway Timeout), TCP connection dropped, DNS resolution glitch, HTTP 429 (Too Many Requests - dengan header `Retry-After`).
2.  **Non-Transient Faults**: Error yang bersifat deterministik dan fatal. Mencoba kembali request ini hanya akan membuang CPU cycles dan bandwidth.
    *   *Contoh*: HTTP 400 (Bad Request), HTTP 401 (Unauthorized), HTTP 403 (Forbidden), HTTP 404 (Not Found), HTTP 422 (Unprocessable Entity).

### Matematika Exponential Backoff & Full Jitter
Percobaan retry simultan dari ribuan client yang gagal secara serentak akan menciptakan fenomena *Retry Storm* (Thundering Herd Problem) yang menghancurkan downstream service.

Formula interval backoff eksponensial standar:
$$T_{\text{wait}} = \text{base\_delay} \times 2^{\text{attempt}}$$

Jika 10.000 clients gagal pada $t=0$, maka pada $t = base\_delay \times 2^1$, seluruh 10.000 clients akan menembak server secara bersamaan. Solusinya adalah **Full Jitter**:
$$T_{\text{jittered}} = \text{Random}(0, \text{base\_delay} \times 2^{\text{attempt}})$$
Full Jitter meratakan distribusi traffic downstream ke rentang waktu yang seragam, menurunkan konkurensi puncak hingga 90%.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental end-to-end terintegrasi di .NET 8: FluentValidation, Custom `IExceptionHandler`, RFC 9457 `ProblemDetails`, dan Polly v8 Resilience Pipeline.

```csharp
// Program.cs
using System.Net;
using FluentValidation;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;

var builder = WebApplication.CreateBuilder(args);

// 1. Registrasi Validasi
builder.Services.AddValidatorsFromAssemblyContaining<CreateOrderRequestValidator>();

// 2. Registrasi Global Error Handling (.NET 8 standard)
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

// 3. Registrasi Polly v8 Resilience Pipeline
builder.Services.AddResiliencePipeline("downstream-pipeline", pipelineBuilder =>
{
    pipelineBuilder
        .AddRetry(new RetryStrategyOptions
        {
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>(),
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            BaseDelay = TimeSpan.FromMilliseconds(200)
        })
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>(),
            FailureRatio = 0.5, // 50% failures
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 8,
            BreakDuration = TimeSpan.FromSeconds(30)
        })
        .AddTimeout(TimeSpan.FromSeconds(3));
});

var app = builder.Build();

// Pipeline Middleware
app.UseExceptionHandler(); // Mengaktifkan ExceptionHandlerMiddleware
app.UseHttpsRedirection();

// 4. Minimal API Endpoint dengan Manual Validation Execution
app.MapPost("/api/orders", async (
    [FromBody] CreateOrderRequest request,
    IValidator<CreateOrderRequest> validator,
    ResiliencePipelineProvider<string> pipelineProvider,
    CancellationToken ct) =>
{
    var validationResult = await validator.ValidateAsync(request, ct);
    if (!validationResult.IsValid)
    {
        return Results.ValidationProblem(
            validationResult.ToDictionary(),
            statusCode: (int)HttpStatusCode.BadRequest,
            title: "Validation Failed");
    }

    var pipeline = pipelineProvider.GetPipeline("downstream-pipeline");

    // Eksekusi outbound call di dalam Resilience Pipeline
    var downstreamResult = await pipeline.ExecuteAsync(
        async token => await MockExternalPaymentGatewayCall(request, token),
        ct);

    return Results.Ok(new { OrderId = Guid.NewGuid(), Status = downstreamResult });
});

app.Run();

// --- MOCK SERVICE ---
static async ValueTask<string> MockExternalPaymentGatewayCall(CreateOrderRequest req, CancellationToken ct)
{
    // Simulasi transient error
    if (Random.Shared.Next(1, 4) == 1)
    {
        throw new HttpRequestException("Payment gateway unreachable (Transient Error).");
    }

    await Task.Delay(100, ct); // Network latency
    return "PAID_SUCCESSFULLY";
}

// --- DTO & VALIDATOR ---
public record CreateOrderRequest(string CustomerEmail, decimal Amount, string Currency);

public class CreateOrderRequestValidator : AbstractValidator<CreateOrderRequest>
{
    public CreateOrderRequestValidator()
    {
        RuleFor(x => x.CustomerEmail)
            .NotEmpty().WithMessage("CustomerEmail wajib diisi.")
            .EmailAddress().WithMessage("Format email tidak valid.");

        RuleFor(x => x.Amount)
            .GreaterThan(0).WithMessage("Amount harus lebih besar dari 0.");

        RuleFor(x => x.Currency)
            .NotEmpty()
            .Length(3).WithMessage("Currency harus 3 karakter ISO (e.g. IDR, USD).");
    }
}

// --- GLOBAL EXCEPTION HANDLER (.NET 8) ---
public sealed class GlobalExceptionHandler(ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Unhandled exception captured: {Message}", exception.Message);

        var (statusCode, title, detail) = exception switch
        {
            BrokenCircuitException => (
                (int)HttpStatusCode.ServiceUnavailable,
                "Circuit Breaker Triggered",
                "Layanan downstream sedang tidak tersedia sementara waktu. Silakan coba kembali nanti."),
            TimeoutException => (
                (int)HttpStatusCode.GatewayTimeout,
                "Network Timeout",
                "Downstream request melampaui batas waktu yang ditentukan."),
            _ => (
                (int)HttpStatusCode.InternalServerError,
                "Internal Server Error",
                "Terjadi kesalahan internal pada server.")
        };

        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = detail,
            Instance = httpContext.Request.Path
        };

        problemDetails.Extensions.Add("traceId", httpContext.TraceIdentifier);

        httpContext.Response.StatusCode = statusCode;
        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);

        return true; // Exception berhasil ditangani
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen kode dari Seksi 07:

1.  `builder.Services.AddValidatorsFromAssemblyContaining<CreateOrderRequestValidator>();`
    Memindai assembly tempat validator berada via Reflection saat bootstrap time dan mendaftarkan semua implementasi `IValidator<T>` ke DI Container dengan lifetime `Scoped`.
2.  `builder.Services.AddExceptionHandler<GlobalExceptionHandler>();`
    Mendaftarkan implementasi `IExceptionHandler` baru milik .NET 8. Memungkinkan multiple exception handler yang dirangkai secara linier.
3.  `builder.Services.AddProblemDetails();`
    Mengonfigurasi service core ASP.NET Core untuk menghasilkan payload berbasis RFC 7807/9457 saat terjadi kegagalan pipeline.
4.  `pipelineBuilder.AddRetry(new RetryStrategyOptions { ... })`
    Mengonfigurasi strategi Retry. `BackoffType = DelayBackoffType.Exponential` dan `UseJitter = true` memastikan interval penundaan berlipat ganda secara dinamis dengan sebaran acak matematis guna memecah resonansi trafik (*retry storm*).
5.  `pipelineBuilder.AddCircuitBreaker(new CircuitBreakerStrategyOptions { ... })`
    Mengonfigurasi sirkuit pengaman. Jika rasio kegagalan mencapai 50% (`FailureRatio = 0.5`) dalam jendela waktu 10 detik (`SamplingDuration`), dengan volume minimal 8 eksekusi (`MinimumThroughput`), status sirkuit meloncat ke `Open` selama 30 detik (`BreakDuration`).
6.  `var validationResult = await validator.ValidateAsync(request, ct);`
    Mengeksekusi validasi secara asynchronous. Sangat krusial menggunakan asynchronous validation agar thread pool tidak terblokir jika validator memerlukan parsing token atau I/O boundary check.
7.  `return Results.ValidationProblem(validationResult.ToDictionary(), ...);`
    Mengonversi failure list dari FluentValidation menjadi kamus `IDictionary<string, string[]>` standar, lalu di-stream langsung ke client dengan format RFC 9457 `HttpValidationProblemDetails` (Status Code 400).
8.  `await pipeline.ExecuteAsync(async token => ... , ct);`
    Membungkus panggilan I/O downstream di dalam State Machine Polly v8. Seluruh logic retry, sirkuit proteksi, dan timeout diatur secara non-blocking via zero-allocation struct-based runners.
9.  `public async ValueTask<bool> TryHandleAsync(...)`
    Metode utama dari `IExceptionHandler`. Mengembalikan `ValueTask<bool>` untuk meminimalkan alokasi memori GC saat mengeksekusi asynchronous execution path.
10. `problemDetails.Extensions.Add("traceId", httpContext.TraceIdentifier);`
    Menyuntikkan correlation ID tracing ke dalam payload response RFC 9457 agar insinyur SRE dapat melacak log yang relevan di OpenTelemetry / Kibana / Datadog secara instan.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks: High-Throughput E-Commerce Payment Gateway
Sebuah platform E-Commerce memproses 5.000 transaksi/detik pada event Harbolnas. Sistem mengandalkan pihak ketiga: *Core Banking Engine* (Third-Party Payment Partner) untuk otorisasi kartu kredit dan e-wallet.

### Tantangan Arsitektural:
1.  **Cascading System Failure**: Pada puncak beban, Bank API mengalami latensi parah (naik dari 150ms ke 12 detik).
2.  **Thread Pool Starvation**: Ribuan request ASP.NET Core menunggu respon Bank API. Kestrel kehabisan worker thread (*thread pool exhaustion*), menyebabkan endpoint lain yang tidak berhubungan (seperti `/catalog` dan `/health`) ikut lumpuh (*cascading total outage*).
3.  **Payload Inconsistency**: Bank API kadang mengirimkan error response berformat XML atau HTML 502 Bad Gateway mentah yang membuat parser downstream crash dengan `NullReferenceException` yang tidak terduga.

### Solusi Komprehensif:
1.  **Strict Boundary Validation**: Memvalidasi data request secara komprehensif di boundary sebelum menyentuh I/O queue.
2.  **Resilience Pipeline Layered Design**:
    *   **Per-Attempt Timeout**: 2 detik. Jika Bank API tidak merespons dalam 2 detik, drop attempt tersebut.
    *   **Polly v8 Hedging Strategy**: Mengirim request paralel alternatif jika request pertama tidak merespon dalam 1.2 detik (khusus idempotent read operations).
    *   **Circuit Breaker**: Putus koneksi jika Bank API gagal terus menerus, alihkan transaksi ke secondary fallback gateway (misal: Backup Gateway B).
3.  **Strict Exception Translation**: Intercept crash pihak ketiga via `IExceptionHandler` dan terbitkan response RFC 9457 yang aman, tanpa membocorkan trace internal ke customer.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur produksi menggunakan .NET 8, Clean Architecture DTO/Domain separation, `EndpointFilter` untuk validasi otomatis, dan integrasi HTTP Client Resilience Handler terdaftar di DI.

### 1. Model Domain & Request DTO

```csharp
namespace ProductionGateway.Domain;

public record ProcessPaymentCommand(
    Guid MerchantId,
    string PaymentMethod,
    decimal Amount,
    string Currency,
    string IdempotencyKey);

public record PaymentResult(Guid TransactionId, string Status, DateTime Timestamp);
```

### 2. Validasi Deklaratif (FluentValidation)

```csharp
using FluentValidation;
using ProductionGateway.Domain;

namespace ProductionGateway.Validation;

public class ProcessPaymentCommandValidator : AbstractValidator<ProcessPaymentCommand>
{
    private static readonly HashSet<string> AllowedCurrencies = ["IDR", "USD", "SGD"];
    private static readonly HashSet<string> AllowedMethods = ["CREDIT_CARD", "E_WALLET", "QRIS"];

    public ProcessPaymentCommandValidator()
    {
        RuleFor(x => x.MerchantId)
            .NotEmpty().WithMessage("MerchantId must not be empty.");

        RuleFor(x => x.PaymentMethod)
            .Must(AllowedMethods.Contains)
            .WithMessage($"PaymentMethod must be one of: {string.Join(", ", AllowedMethods)}");

        RuleFor(x => x.Amount)
            .GreaterThan(1000m).When(x => x.Currency == "IDR")
            .WithMessage("Minimum IDR transaction is 1000.");

        RuleFor(x => x.Currency)
            .Must(AllowedCurrencies.Contains)
            .WithMessage("Unsupported currency code.");

        RuleFor(x => x.IdempotencyKey)
            .NotEmpty()
            .MaximumLength(64)
            .Matches("^[a-zA-Z0-9_-]+$").WithMessage("IdempotencyKey contains invalid characters.");
    }
}
```

### 3. Otomatisasi Validasi via Minimal API Endpoint Filter

```csharp
using FluentValidation;
using Microsoft.AspNetCore.Http;

namespace ProductionGateway.Filters;

public class ValidationFilter<T> : IEndpointFilter where T : class
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var validator = context.HttpContext.RequestServices.GetService<IValidator<T>>();
        if (validator is null)
        {
            return await next(context);
        }

        var argument = context.Arguments.OfType<T>().FirstOrDefault();
        if (argument is null)
        {
            return TypedResults.BadRequest("Request payload cannot be deserialized or is empty.");
        }

        var validationResult = await validator.ValidateAsync(argument, context.HttpContext.RequestAborted);
        if (!validationResult.IsValid)
        {
            return TypedResults.ValidationProblem(validationResult.ToDictionary());
        }

        return await next(context);
    }
}
```

### 4. Custom Exceptions Layer

```csharp
namespace ProductionGateway.Exceptions;

public abstract class DomainException(string message) : Exception(message);

public class PaymentGatewayUnavailableException(string message, Exception? inner = null) 
    : DomainException(message);

public class DuplicateTransactionException(string idempotencyKey) 
    : DomainException($"Transaction with Idempotency-Key '{idempotencyKey}' has already been processed.");
```

### 5. Resilient External Payment Client via `Microsoft.Extensions.Http.Resilience`

```csharp
using System.Net;
using System.Text.Json;
using Polly;
using Polly.CircuitBreaker;
using Polly.Timeout;
using ProductionGateway.Domain;
using ProductionGateway.Exceptions;

namespace ProductionGateway.Infrastructure;

public interface IPaymentGatewayClient
{
    Task<PaymentResult> AuthorizePaymentAsync(ProcessPaymentCommand command, CancellationToken ct);
}

public class BankPaymentGatewayClient(HttpClient httpClient, ILogger<BankPaymentGatewayClient> logger) 
    : IPaymentGatewayClient
{
    public async Task<PaymentResult> AuthorizePaymentAsync(ProcessPaymentCommand command, CancellationToken ct)
    {
        try
        {
            var response = await httpClient.PostAsJsonAsync("/v1/charge", command, ct);

            if (!response.IsSuccessStatusCode)
            {
                if (response.StatusCode == HttpStatusCode.Conflict)
                {
                    throw new DuplicateTransactionException(command.IdempotencyKey);
                }

                var errorContent = await response.Content.ReadAsStringAsync(ct);
                logger.LogError("Bank API returned status code {Status}: {Payload}", response.StatusCode, errorContent);
                throw new PaymentGatewayUnavailableException($"Bank API rejected call with status {response.StatusCode}");
            }

            var result = await response.Content.ReadFromJsonAsync<PaymentResult>(cancellationToken: ct);
            return result ?? throw new JsonException("Null payload received from downstream bank gateway.");
        }
        catch (BrokenCircuitException ex)
        {
            logger.LogCritical(ex, "Circuit Breaker OPEN for Bank API. Fallback triggered.");
            throw new PaymentGatewayUnavailableException("Payment Gateway is temporarily suspended due to elevated failure rates.", ex);
        }
        catch (TimeoutRejectedException ex)
        {
            logger.LogWarning(ex, "Request timed out on downstream call.");
            throw new PaymentGatewayUnavailableException("The payment downstream timed out.", ex);
        }
    }
}
```

### 6. Production Exception Handler (RFC 9457 Compliant)

```csharp
using System.Net;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using ProductionGateway.Exceptions;

namespace ProductionGateway.Diagnostics;

public sealed class ProductionExceptionHandler(
    IProblemDetailsService problemDetailsService,
    ILogger<ProductionExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Exception caught by production boundary: {Type} - {Message}", 
            exception.GetType().Name, exception.Message);

        var (status, title) = exception switch
        {
            PaymentGatewayUnavailableException => (StatusCodes.Status503ServiceUnavailable, "Payment Gateway Outage"),
            DuplicateTransactionException => (StatusCodes.Status409Conflict, "Idempotency Conflict"),
            _ => (StatusCodes.Status500InternalServerError, "Internal Server Failure")
        };

        httpContext.Response.StatusCode = status;

        return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            ProblemDetails = new ProblemDetails
            {
                Status = status,
                Title = title,
                Detail = exception.Message,
                Instance = httpContext.Request.Path
            },
            Exception = exception
        });
    }
}
```

### 7. Program.cs Composition Root

```csharp
using FluentValidation;
using Microsoft.Extensions.Http.Resilience;
using Polly;
using ProductionGateway.Diagnostics;
using ProductionGateway.Domain;
using ProductionGateway.Filters;
using ProductionGateway.Infrastructure;
using ProductionGateway.Validation;

var builder = WebApplication.CreateBuilder(args);

// Logging
builder.Logging.ClearProviders();
builder.Logging.AddConsole();

// Core Services
builder.Services.AddValidatorsFromAssemblyContaining<ProcessPaymentCommandValidator>();
builder.Services.AddExceptionHandler<ProductionExceptionHandler>();
builder.Services.AddProblemDetails();

// Resilient Typed HttpClient Setup with Polly v8
builder.Services.AddHttpClient<IPaymentGatewayClient, BankPaymentGatewayClient>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["PaymentGateway:BaseUrl"] ?? "https://api.mockbank.com");
    client.Timeout = TimeSpan.FromSeconds(10); // Ultimate overall safety net
})
.AddStandardResilienceHandler(options =>
{
    // Konfigurasi Standar: Timeout Attempt -> Retry -> Circuit Breaker -> Timeout Total
    options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(2);
    
    options.Retry.MaxRetryAttempts = 3;
    options.Retry.BackoffType = DelayBackoffType.Exponential;
    options.Retry.UseJitter = true;
    options.Retry.Delay = TimeSpan.FromMilliseconds(200);

    options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(30);
    options.CircuitBreaker.FailureRatio = 0.4; // 40% failure
    options.CircuitBreaker.MinimumThroughput = 10;
    options.CircuitBreaker.BreakDuration = TimeSpan.FromSeconds(15);

    options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(6);
});

var app = builder.Build();

app.UseExceptionHandler();
app.UseHttpsRedirection();

// Endpoint
app.MapPost("/api/v1/payments", async (
    ProcessPaymentCommand command,
    IPaymentGatewayClient paymentClient,
    CancellationToken ct) =>
{
    var result = await paymentClient.AuthorizePaymentAsync(command, ct);
    return TypedResults.Ok(result);
})
.AddEndpointFilter<ValidationFilter<ProcessPaymentCommand>>();

app.Run();

// Assembly pointer for integration testing
public partial class Program;
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Data Annotations vs. FluentValidation

| Dimensi Evaluasi | Data Annotations | FluentValidation |
| :--- | :--- | :--- |
| **Separation of Concerns** | Rendah. DTO coupling dengan metadata rules. | Sangat Tinggi. Model POCO terisolasi murni dari validasi. |
| **Rule Expressiveness** | Terbatas (Regex, Range, Required). | Sangat Ekspresif (Conditional, Nested, Cross-Field). |
| **Testing Isolation** | Sulit diuji tanpa instansiasi validation contexts. | Sangat mudah di-unit-test secara decoupled via `TestValidate`. |
| **Performance Overhead** | Rendah (Cached metadata runtime). | Sedikit alokasi object untuk rule engine. |
| **Asynchronous Validation** | Tidak didukung secara native. | Didukung penuh (`MustAsync`, `ValidateAsync`). |

### 2. Error Handling Approaches

| Dimensi Evaluasi | Controller/Handler `try-catch` | Custom Middleware | `IExceptionHandler` (.NET 8+) |
| :--- | :--- | :--- | :--- |
| **Maintenance Cost** | Ekstrem Tinggi (Duplikasi ribuan boilerplate). | Rendah (Terpusat). | Sangat Rendah (Pemisahan chaining terstruktur). |
| **Memory Allocation** | Bergantung pada scope implementasi. | Menengah (Middleware context allocation). | Teroptimasi (`ValueTask` based, zero overhead). |
| **RFC 9457 Alignment** | Manual mapping di setiap controller. | Terpusat via logic manual. | Terintegrasi native via `IProblemDetailsService`. |
| **Execution Flow** | Melingkupi method lokal saja. | Menangkap seluruh pipeline downstream. | Terstandarisasi di bawah `ExceptionHandlerMiddleware`. |

### 3. Fault-Tolerance Strategies: Retry vs. Hedging vs. Circuit Breaker

| Karakteristik | Retry Strategy | Hedging Strategy | Circuit Breaker |
| :--- | :--- | :--- | :--- |
| **Tujuan Utama** | Mengatasi glitch jaringan temporal. | Memangkas tail latency (P99). | Menghentikan *cascading collapse*. |
| **Dampak Beban Server** | Menambah beban downstream (berbahaya). | Menggandakan trafik network. | Mengurangi beban downstream ke nol. |
| **Applicability** | Hanya untuk *idempotent operations*. | Hanya untuk *non-mutating idempotent calls*. | Semua jenis calls outbound. |
| **Latency Penalty** | Tinggi ($attempt \times delay$). | Sangat Rendah (Parallel execution). | Nol saat Open (Fail-Fast instan). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Sync-over-Async Deadlock di Validation Engine**:
    *   *Problem*: Memanggil `.Validate(request)` yang di dalamnya terdapat rule `.MustAsync(...)` menggunakan `.Result` atau `.GetAwaiter().GetResult()`.
    *   *Konsekuensi*: Thread starvation seketika pada lingkungan Kestrel berkonkurensi tinggi.
    *   *Solusi*: Gunakan selalu pipeline asinkronus secara menyeluruh: `await validator.ValidateAsync(...)`.
2.  **Stateful Circuit Breaker pada Multi-Instance Replicas**:
    *   *Problem*: Circuit Breaker Polly diinisialisasi in-memory (`Singleton` per-process container). Jika aplikasi di-scale menjadi 10 pod Kubernetes, state breaker terisolasi per pod.
    *   *Konsekuensi*: Satu pod mungkin membuka circuit (Open), sementara 9 pod lainnya masih terus membanjiri downstream yang sekarat.
    *   *Solusi*: Set `FailureRatio` dan `MinimumThroughput` dengan perhitungan agregat per-pod, atau gunakan Envoy/Service Mesh out-of-process circuit breaking jika dibutuhkan global state.
3.  **JSON Deserialization Failure Sebelum Endpoint Filters**:
    *   *Problem*: Jika client mengirim malformed JSON (misal tanda kurung tidak tertutup), model binding Kestrel gagal sebelum `ValidationFilter` dieksekusi.
    *   *Konsekuensi*: Exception `BadHttpRequestException` dilempar langsung ke global exception handler.
    *   *Solusi*: Pastikan `GlobalExceptionHandler` menangani `BadHttpRequestException` secara spesifik dan memetakannya ke HTTP 400 Problem Details, bukan dibiarkan jatuh ke HTTP 500.
4.  **Non-Idempotent Retries yang Memicu Double Charge**:
    *   *Problem*: Melakukan retry pada endpoint pembayaran non-idempotent ketika downstream mengalami response network dropped (downstream sudah memproses charge, tapi ACK network putus).
    *   *Konsekuensi*: Rekening nasabah didebet dua kali.
    *   *Solusi*: Jangan pernah memasang Retry Strategy pada POST mutating calls tanpa menyertakan HTTP Header `Idempotency-Key` yang dipahami dan dijamin oleh downstream engine.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Leaking Stack Traces ke Production Response
```csharp
// BURUK: Membocorkan arsitektur internal dan sensitive traces ke penyerang
catch (Exception ex)
{
    return Results.Json(new { Error = ex.Message, Stack = ex.StackTrace }, statusCode: 500);
}
```
**Perbaikan**: Pisahkan internal logging dengan payload publik via RFC 9457:
```csharp
// BENAR: Log trace secara detail di server, kembalikan generic correlation ID ke client
logger.LogError(ex, "Database connection failure");
return Results.Problem(
    title: "An unexpected error occurred.",
    statusCode: StatusCodes.Status500InternalServerError,
    extensions: new Dictionary<string, object?> { ["traceId"] = httpContext.TraceIdentifier });
```

### Anti-Pattern 2: Blind Retry tanpa Jitter
```csharp
// BURUK: Static interval memicu Thundering Herd Problem
services.AddHttpClient("Downstream")
    .AddTransientHttpErrorPolicy(policy => policy.WaitAndRetryAsync(3, _ => TimeSpan.FromSeconds(2)));
```
**Perbaikan**: Selalu gunakan Exponential Backoff dengan Jitter:
```csharp
// BENAR: Menyebarkan retry interval secara acak
options.Retry.BackoffType = DelayBackoffType.Exponential;
options.Retry.UseJitter = true;
options.Retry.Delay = TimeSpan.FromMilliseconds(500);
```

### Anti-Pattern 3: Menggunakan Exceptions untuk Bisnis Logic Validasi
```csharp
// BURUK: Melempar exception untuk validasi alur normal
if (user.Age < 18) 
    throw new UserUnderageException("User must be 18+");
```
**Perbaikan**: Gunakan FluentValidation atau Result Pattern:
```csharp
// BENAR: Kembalikan Result type atau validasi secara imperatif di boundary
public Result RegisterUser(User user)
{
    if (user.Age < 18)
        return Result.Failure("USER_UNDERAGE", "User must be 18+");
    return Result.Success();
}
```

### Anti-Pattern 4: Tidak Mengaitkan CancellationToken ke Polly Pipeline
```csharp
// BURUK: Menghiraukan request cancellation dari browser/klien
await pipeline.ExecuteAsync(async _ => await client.GetAsync(url));
```
**Perbaikan**: Ikat `CancellationToken` dari upstream HTTP Context:
```csharp
// BENAR: Pipeline membatalkan retry loop seketika saat client disconnect
await pipeline.ExecuteAsync(async token => await client.GetAsync(url, token), httpContext.RequestAborted);
```

### Anti-Pattern 5: Mutasi Singleton Service di dalam Exception Handler
```csharp
// BURUK: Stateful bug pada singleton exception handler
public class GlobalExceptionHandler : IExceptionHandler
{
    private int _errorCount = 0; // Race condition mutasi multi-threading
    ...
}
```
**Perbaikan**: `IExceptionHandler` harus bersifat *Stateless* atau menggunakan thread-safe constructs/metrics counters.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Arsitektur Validasi**:
    Tempatkan model validasi sedekat mungkin dengan boundary input (Application Layer). Validasi struktural (string format, rentang angka, regex) dieksekusi di HTTP Controller/Minimal API Filter, sedangkan validasi bisnis state-dependent dieksekusi di Application/Domain Service.
2.  **Struktur Status Code HTTP RFC 9457 yang Konsisten**:
    *   `400 Bad Request`: Payload JSON malformed atau parse error.
    *   `422 Unprocessable Entity`: JSON valid, namun gagal aturan bisnis/validasi field. (Alternatif: Gunakan `400` untuk semua validation problem jika mengikuti standar default ASP.NET Core).
    *   `409 Conflict`: Benturan idempotency key atau concurrency token state (ETag).
    *   `503 Service Unavailable`: Circuit breaker sedang `Open`.
    *   `504 Gateway Timeout`: Attempt timeout atau total request timeout tercapai.
3.  **Resilience Pipeline Layer Ordering**:
    Urutan layering pada Polly v8 sangat krusial:
    $$\text{Outer} \longrightarrow [\text{Total Timeout}] \longrightarrow [\text{Retry}] \longrightarrow [\text{Circuit Breaker}] \longrightarrow [\text{Attempt Timeout}] \longrightarrow \text{Inner (Network)}$$
    *Alasan*: Attempt Timeout membatasi durasi per panggilan individual; Circuit Breaker memonitor kegagalan per attempt; Retry mencoba kembali jika terjadi transient failure; dan Total Timeout menggaransi seluruh siklus loop berhenti jika total waktu kumulatif habis.
4.  **Correlation ID Propagation**:
    Sertakan header `traceparent` (W3C standard) atau custom `X-Correlation-Id` di setiap outbound request menggunakan delegating handler agar error dari downstream dapat ditelusuri silang.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Zero-Allocation Exception Routing via `ValueTask`
Dengan beralih dari middleware custom konvensional ke .NET 8 `IExceptionHandler`, return type `ValueTask<bool>` mengeliminasi alokasi heap `Task<bool>` pada critical error paths:
```csharp
public ValueTask<bool> TryHandleAsync(...) => ValueTask.FromResult(true);
```

### 2. Singleton Compiled FluentValidation Instances
Hindari merefleksi validator baru di setiap request. Gunakan registrasi assembly scan default yang mendaftarkan validator sebagai `Scoped` atau `Singleton` (jika validator sepenuhnya stateless):
```csharp
builder.Services.AddValidatorsFromAssemblyContaining<TValidator>(ServiceLifetime.Singleton);
```

### 3. Mengeliminasi `Regex` Backtracking pada Validasi Input
Regex yang tidak terkompilasi rentan terhadap *Catastrophic Backtracking* yang memblokir CPU:
```csharp
// Optimal: C# GeneratedRegex source generators
[GeneratedRegex(@"^[a-zA-Z0-9_-]+$", RegexOptions.Compiled)]
private static partial Regex SafeIdempotencyRegex();
```

### 4. Zero-Copy Problem Details Streaming
Gunakan `IProblemDetailsService` bawaan .NET 8 yang menulis response langsung ke `PipeWriter` stream HTTP context tanpa melakukan buffering string JSON di memori:
```csharp
await problemDetailsService.TryWriteAsync(new ProblemDetailsContext { ... });
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi CWE-209: Information Exposure Through an Error Message
Serangan injeksi SQL atau deserialization attacks sering memicu error database internal. Jika stack trace atau detail query terekspos, attacker dapat memetakan skema database internal secara trivial.
*   **Enforcement**: Pastikan environment produksi mematikan `app.UseDeveloperExceptionPage()`. Terapkan mapping error strict di mana `Detail` untuk 500 Internal Error hanya menampilkan pesan statis generik.

### 2. Regular Expression Denial of Service (ReDoS) Protection
Validasi string panjang menggunakan Regex yang rentan dapat dimanfaatkan attacker untuk memicu DoS dengan CPU utilization 100%.
*   **Enforcement**: Berikan timeout eksplisit pada seluruh validasi Regex di FluentValidation:
```csharp
RuleFor(x => x.Notes).Matches("...", RegexOptions.None, TimeSpan.FromMilliseconds(250));
```

### 3. Rate-Limiting Fallback Endpoint & Retries Quota
Attacker dapat sengaja menembak server dengan payload yang memicu outbound call downstream untuk menguras connection pool kita (*Denial of Wallet* atau *Downstream Resource Starvation*).
*   **Enforcement**: Pasang Polly `RateLimiterStrategy` atau ASP.NET Core `RateLimitingMiddleware` sebelum pipeline outbound dipicu.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Structured Logging Metrics untuk Resilience State
Logging teks konvensional menyulitkan agregasi query dashboard. Polly v8 menyajikan event hooks terstruktur:

```csharp
options.CircuitBreaker.OnOpened = args =>
{
    logger.LogCritical("Circuit Breaker transitioned to OPEN! Duration: {BreakDuration}s. Handled Result: {Outcome}",
        args.BreakDuration.TotalSeconds,
        args.Outcome.Exception?.Message ?? args.Outcome.Result?.StatusCode.ToString());
    return ValueTask.CompletedTask;
};

options.Retry.OnRetry = args =>
{
    logger.LogWarning("Polly Retry Attempt #{Attempt} executed after {Delay}ms delay.",
        args.AttemptNumber,
        args.RetryDelay.TotalMilliseconds);
    return ValueTask.CompletedTask;
};
```

### 2. OpenTelemetry Metrics Integrations
Polly v8 secara otomatis mengemisi OpenTelemetry meters:
*   `resilience.polly.strategy.execution.duration`: Histogram durasi eksekusi strategy.
*   `resilience.polly.circuitbreaker.state`: Nilai gauge yang menunjukkan status circuit (`0` Closed, `1` Open, `2` Half-Open).
*   `resilience.polly.retry.attempts`: Counter jumlah percobaan retry.

```csharp
// Setup OpenTelemetry di Program.cs
builder.Services.AddOpenTelemetry()
    .WithMetrics(meterProviderBuilder =>
    {
        meterProviderBuilder
            .AddMeter("Polly")
            .AddPrometheusExporter();
    });
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ASP.NET CORE RESILIENCE & ERROR CHEAT SHEET               │
├────────────────────────────┬─────────────────────────────────────────────────┤
│ IExceptionHandler (.NET 8) │ builder.Services.AddExceptionHandler<THandler>()│
│                            │ builder.Services.AddProblemDetails()            │
│                            │ app.UseExceptionHandler();                      │
├────────────────────────────┼─────────────────────────────────────────────────┤
│ RFC 9457 Problem Details   │ app.MapPost(..., () => Results.Problem(...))    │
│                            │ app.MapPost(..., () => Results.ValidationProblem│
├────────────────────────────┼─────────────────────────────────────────────────┤
│ FluentValidation Setup     │ services.AddValidatorsFromAssemblyContaining<T> │
│                            │ validator.ValidateAsync(dto, cancellationToken) │
├────────────────────────────┼─────────────────────────────────────────────────┤
│ Polly v8 Standard Pipeline │ services.AddHttpClient<T>()                     │
│                            │   .AddStandardResilienceHandler(opt => { ... }) │
├────────────────────────────┼─────────────────────────────────────────────────┤
│ Jittered Exponential Retry │ opt.Retry.BackoffType =                         │
│                            │   DelayBackoffType.Exponential;                 │
│                            │ opt.Retry.UseJitter = true;                     │
├────────────────────────────┼─────────────────────────────────────────────────┤
│ Circuit Breaker Config     │ opt.CircuitBreaker.FailureRatio = 0.5;          │
│                            │ opt.CircuitBreaker.BreakDuration = 30s;         │
└────────────────────────────┴─────────────────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Tingkat Basic

1.  **Pertanyaan**: Apa perbedaan utama antara status code HTTP `400 Bad Request` dan `422 Unprocessable Entity` dalam konteks validasi API modern?
    *   **Jawaban**: HTTP `400 Bad Request` menandakan adanya error struktural sintaksis (misalnya format JSON cacat sehingga parser gagal melakukan deserialization), sedangkan HTTP `422 Unprocessable Entity` (atau `400` dengan sub-errors dalam RFC 9457) menandakan sintaksis request valid dan terbaca, namun isinya melanggar aturan semantik domain atau validasi logic.
2.  **Pertanyaan**: Mengapa melempar exception (`throw new Exception()`) untuk kegagalan validasi reguler dianggap sebagai anti-pattern di ASP.NET Core?
    *   **Jawaban**: Karena exceptions memicu alokasi memori yang masif di Heap, overhead penangkapan stack trace, dan instruksi *context switching* runtime yang menghabiskan ribuan siklus CPU. Validasi adalah skenario bisnis yang lumrah (*expected path*), sehingga harus ditangani menggunakan alur kondisional kontrol biasa atau Result types.
3.  **Pertanyaan**: Apa peran spesifik method `TryHandleAsync` pada interface `IExceptionHandler` di .NET 8?
    *   **Jawaban**: Menerima request context dan exception yang unhandled, menulis respons HTTP Problem Details yang sesuai jika mampu menanganinya, lalu mengembalikan nilai boolean: `true` jika exception berhasil diatasi (menghentikan eksekusi handler berikutnya) atau `false` untuk melimpahkan penanganan ke handler berikutnya dalam rantai pipeline.
4.  **Pertanyaan**: Sebutkan tiga komponen wajib dalam payload error RFC 9457 (Problem Details)!
    *   **Jawaban**: Tiga komponen standar: `type` (URI identifier masalah), `title` (deskripsi singkat yang seragam), dan `status` (HTTP status code yang sesuai).
5.  **Pertanyaan**: Apa yang dimaksud dengan *Transient Fault*? Berikan dua contoh response HTTP yang termasuk kategori ini!
    *   **Jawaban**: Kondisi kegagalan temporal yang memiliki probabilitas tinggi untuk pulih dengan sendirinya jika request dicoba kembali setelah interval waktu tertentu. Contoh: HTTP 503 (Service Unavailable) dan HTTP 504 (Gateway Timeout).

### Bagian 2: Tingkat Intermediate

6.  **Pertanyaan**: Jelaskan fenomena *Retry Storm* (Thundering Herd) dan bagaimana algoritma *Full Jitter* menyelesaikannya secara matematis!
    *   **Jawaban**: Retry Storm terjadi ketika ribuan client yang gagal melakukan percobaan ulang secara bersamaan pada interval waktu yang sinkron, sehingga melipatgandakan beban downstream yang sedang bermasalah hingga down total. Full Jitter menyelesaikannya dengan memasukkan variabel acak seragam antara 0 hingga batas atas exponential backoff ($T_{\text{wait}} = \text{Random}(0, \text{base} \times 2^{\text{attempt}})$), memecah sinkronisasi lonjakan request dan meratakan distribusi trafik.
7.  **Pertanyaan**: Bagaimana lifecycle state dari *Circuit Breaker* (Closed, Open, Half-Open) bekerja untuk melindungi layanan hilir (*downstream*)?
    *   **Jawaban**:
        *   *Closed*: Sirkuit beroperasi normal dan membiarkan request lewat sembari mengukur rasio kegagalan.
        *   *Open*: Jika kegagalan melewati ambang batas, sirkuit terbuka dan langsung menggagalkan request di sisi client (*fail-fast*) tanpa menyentuh jaringan downstream.
        *   *Half-Open*: Setelah masa tunggu selesai, sejumlah kecil traffic uji coba dialirkan. Jika sukses, status kembali ke *Closed*; jika gagal kembali ke *Open*.
8.  **Pertanyaan**: Mengapa penggunaan method synchronous `.Validate()` dari FluentValidation di dalam asynchronous Minimal API handler berbahaya bagi performa server Kestrel?
    *   **Jawaban**: Jika validator tersebut memiliki ketergantungan async (seperti `MustAsync`) yang dipaksa berjalan synchronous (`.GetAwaiter().GetResult()`), ini akan memicu *sync-over-async* pattern. Pada kondisi konkurensi tinggi, hal ini menyebabkan *Thread Pool Starvation* karena thread pemanggil diblokir menunggu context task selesai, menurunkan throughput Kestrel secara drastis hingga sistem berhenti merespons.
9.  **Pertanyaan**: Dalam urutan composite resilience pipeline Polly v8, mengapa strategi *Circuit Breaker* harus ditempatkan di sebelah dalam (*inner*) dari strategi *Retry*?
    *   **Jawaban**: Agar Circuit Breaker dapat mengukur dan merespons hasil dari setiap percobaan panggilan jaringan individu yang dieksekusi oleh Retry strategy. Jika Circuit Breaker ditempatkan di luar (*outer*), maka sirkuit hanya akan mencatat kegagalan setelah seluruh percobaan retry habis, yang menunda pembukaan sirkuit dan memperpanjang paparan downstream ke beban berlebih.
10. **Pertanyaan**: Apa bahaya arsitektural dari mengeksekusi strategi Retry pada HTTP POST request yang tidak idempotent?
    *   **Jawaban**: Jika upstream mengirimkan POST (misalnya `/charge-wallet`), lalu downstream sebenarnya berhasil memproses pembayaran namun koneksi TCP terputus sebelum downstream sempat mengirimkan ACK, maka strategi retry otomatis akan mengirimkan request duplikat. Tanpa mekanisme *Idempotency-Key*, ini akan memicu *Double-Charging* atau duplikasi mutasi resource pada sistem keuangan downstream.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Resilient Multi-Tenant B2B Billing Dispatcher Engine"

#### Skenario:
Anda ditunjuk sebagai Lead Platform Engineer untuk membangun billing microservice di sebuah platform SaaS berskala besar. Sistem bertugas memproses invoice bulanan dan menagihkannya ke Payment Gateway rekanan melalui HTTP API.

#### Persyaratan Teknis:
1.  **Spesifikasi Framework**: .NET 8, C# 12, Minimal API.
2.  **Validasi Input**:
    *   Gunakan `FluentValidation`.
    *   Validasi `InvoiceId` (format: `INV-YYYY-XXXXX`), `MerchantId` (Guid valid), `LineItems` (minimal 1 item, maksimum 100 item), dan `TotalAmount` (harus sama persis dengan kalkulasi penjumlahan unit price * quantity dari seluruh Line Items).
    *   Otomatisasi validasi menggunakan custom `IEndpointFilter`.
3.  **Centralized Error Handling**:
    *   Implementasikan class `BillingExceptionHandler` yang mengimplementasikan `IExceptionHandler`.
    *   Semua output kegagalan harus mengadopsi struktur RFC 9457 `ProblemDetails`.
    *   Sertakan `traceId`, `timestamp`, dan `errorCode` khusus di dictionary `extensions`.
4.  **Resilience Layer (Polly v8)**:
    *   Konfigurasikan resilient `HttpClient` bernama `PaymentGatewayClient`.
    *   Implementasikan strategi bertingkat:
        1.  *Total Request Timeout*: 5 detik.
        2.  *Retry*: Maksimal 3 percobaan, Exponential Backoff + Full Jitter, hanya untuk transient error (`HttpRequestException`, 5xx, dan 429).
        3.  *Circuit Breaker*: Sampling window 15 detik, failure threshold 50%, minimum throughput 5 requests, break duration 10 detik.
        4.  *Attempt Timeout*: 1.5 detik per panggilan.
5.  **Simulasi Chaos/Downstream**:
    *   Buat mock service dengan endpoint `/v1/invoices/settle` yang secara acak menghasilkan 504 Gateway Timeout (30% probabilitas), delay latensi 3 detik (20% probabilitas), dan 200 OK (50% probabilitas).

#### Kriteria Pengujian Keberhasilan:
*   Unit Test: Memvalidasi `InvoiceValidator` dengan skenario kalkulasi `TotalAmount` yang tidak sinkron dengan `LineItems`.
*   Integration Test: Mengirimkan rentetan 20 request beruntun ke mock service yang rusak dan memvalidasi bahwa setelah 5 kegagalan berturut-turut, HTTP 503 Problem Details (Circuit Breaker OPEN) langsung kembali ke client dalam waktu kurang dari 5 milidetik (*fail-fast* terbukti bekerja).
*   Logging Test: Memverifikasi via Console Logger bahwa transisi State Circuit Breaker (`Closed -> Open -> Half-Open`) tercatat dalam format structured log (JSON).