# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Validation, Error Handling & Fault Tolerance — ASP.NET Core**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan mengoptimasi pipeline validasi asinkron berkinerja tinggi menggunakan **FluentValidation** dan **MediatR Pipeline Behaviors** tanpa mengorbankan alokasi memori (*low allocation overhead*).
- Mengimplementasikan standar spesifikasi industri **RFC 7807 (Problem Details for HTTP APIs)** secara konsisten menggunakan fitur asli .NET 8+ (`IExceptionHandler`, `ProblemDetailsService`).
- Membangun strategi ketahanan layanan (*fault tolerance*) tingkat lanjut menggunakan **Polly v8 (Core Resiliency Pipeline)**, mencakup pola *Circuit Breaker*, *Advanced Hedging*, *Bulkhead Isolation*, dan *Dynamic Rate Limiting*.
- Mendiagnosis, memitigasi, dan mengotomasi penanganan *transient faults* serta *cascading failures* pada komunikasi antar-layanan (*inter-service microservices communication*).
- Mengintegrasikan metadata observability (W3C TraceContext, Activity Trace ID, dan Correlation ID) ke dalam kontrak kesalahan sistem secara otomatis.

---

## 2. Prerequisite
Untuk memahami materi ini secara komprehensif, peserta diwajibkan telah menguasai:
- Konsep dasar ASP.NET Core Middleware Pipeline dan Dependency Injection Service Lifetimes (`Transient`, `Scoped`, `Singleton`).
- Pemrograman Asinkron C# tingkat lanjut (`Task`, `ValueTask`, `CancellationToken`, `SynchronizationContext`).
- Pengenalan pola arsitektur CQRS (Command Query Responsibility Segregation) dan mediator pattern via MediatR.
- Penggunaan dasar HTTP Client Factory dan Polly v7/v8 primitives.

---

## 3. Concept & Internal Architecture (Mendalam)

### A. The Unified Resiliency and Exception Architecture
Arsitektur penanganan kesalahan dan ketahanan pada ASP.NET Core modern beroperasi di dua layer utama:
1. **In-Process Pipeline (ASP.NET Core Middleware Stack & MediatR Pipeline)**: Bertanggung jawab terhadap validasi payload, otorisasi kontekstual, pemetaan eksepsi internal menjadi representasi eksternal, dan short-circuiting request invalid.
2. **Out-of-Process / Boundary Pipeline (Polly Resilience Handler)**: Bertanggung jawab terhadap dependensi eksternal (Database, REST downstream, Cache, Message Broker) guna mencegah *thread pool starvation* dan *cascading failures*.

```
[ Incoming HTTP Request ]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ ASP.NET Core Middleware Pipeline                       │
│  - CorrelationIdMiddleware (W3C TraceContext)          │
│  - ExceptionHandlerMiddleware (IExceptionHandler)      │
│  - Routing & Endpoint Execution                        │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│ Application Boundary (MediatR Pipeline Behaviors)      │
│  - ValidationBehavior<TRequest, TResponse>             │
│    └─ FluentValidation (Fast Fail / Aggregate)         │
│  - Logging & Metrics Behavior                          │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│ Domain / Infrastructure Boundary (Polly v8 Engines)   │
│  - Rate Limiter Pipeline                               │
│  - Circuit Breaker Engine                              │
│  - Hedging / Timeout Pipeline                          │
│  - Retry with Jitter Strategy                          │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
              [ Downstream Dependency ]
```

### B. RFC 7807 (Problem Details) Internal Mechanics
Di masa lalu, developer sering menuliskan custom middleware yang memanipulasi `context.Response` secara manual melalui `context.Response.WriteAsync()`. Mulai .NET 8, ASP.NET Core memperkenalkan interface terstandarisasi `IExceptionHandler`. Pipeline internal `ExceptionHandlerMiddleware` mengeksekusi rantai `IExceptionHandler` secara berurutan (*chain of responsibility*).

Ketika terjadi *unhandled exception*, runtime tidak lagi mematikan koneksi secara brutal atau mengekspos stack trace mentah. Sebaliknya, pipeline memanggil `IProblemDetailsService` untuk memformat *payload* ke dalam struktur JSON terstandarisasi dengan MIME type `application/problem+json`. Komponen ini secara otomatis menginjeksi:
- `type`: URI referensi tipe error (dokumentasi spesifikasi API).
- `title`: Ringkasan error yang *human-readable*.
- `status`: Kode status HTTP.
- `detail`: Penjelasan spesifik insiden terkait.
- `instance`: Alur URI saat eksekusi berlangsung.
- `extensions`: Metadata tambahan seperti `traceId`, `errorCode`, dan `validationErrors`.

### C. Polly v8: The Unified Strategy Engine
Polly v8 (`Microsoft.Extensions.Resilience`) merupakan penulisan ulang arsitektur Polly dari nol (*zero-allocation target*) yang berfokus pada performa tinggi:
- **ResiliencePipeline**: Menggantikan abstraksi `Policy` legacy. Pipeline dieksekusi secara terpadu tanpa alokasi closures/lambdas berlebih.
- **State Machine Circuit Breaker**: Menggunakan algoritma sliding window berbasis sampling data run-time (bukan sekadar hitungan absolut), meminimalkan *false-positive trip* saat traffic melonjak drastis.
- **Hedging Engine**: Mengirim request duplikat secara paralel jika request pertama melampaui ambang batas latensi p95/p99 tertentu, mengambil respon tercepat, dan membatalkan request lain melalui `CancellationToken`.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise (.NET 8+) |
| :--- | :--- | :--- |
| **Validasi Input** | DataAnnotations pada DTO, logic bercampur di Controller. | FluentValidation decoupled dari DTO, dieksekusi di MediatR Pipeline via declarative rules. |
| **Penanganan Error** | Blok `try-catch` redundan di setiap Controller Action; Custom middleware manual. | `IExceptionHandler` chain, RFC 7807 standard response, automatic activity tracing correlation. |
| **Resilience & Retry** | Loop retry manual, `Thread.Sleep`, atau HttpClient wrapper sederhana. | Polly v8 `ResiliencePipeline`, reactive exponential backoff + jitter, bulkhead isolation. |
| **Downstream Outage** | Menyebabkan kaskade timeout, thread pool exhaustion, seluruh cluster down. | Circuit Breaker memutus koneksi dalam milidetik, fallback strategy menyajikan graceful degradation. |

---

## 5. How (Workflow Detail)

1. **Request Intake**:
   - Request masuk ke ASP.NET Core Kestrel engine.
   - Ekstrak atau generate `TraceParent` header untuk menjamin korelasi log end-to-end.
2. **Pre-Processing (Validation Pipeline)**:
   - Request dipetakan ke Command/Query (CQS).
   - `ValidationBehavior` memindai semua validator terdaftar (`IValidator<TRequest>`).
   - Validasi dijalankan secara paralel/asinkron. Jika ditemukan pelanggaran aturan, pipeline dilempar sebagai `ValidationException` terstruktur, menghentikan eksekusi handler domain (*short-circuit*).
3. **Execution & Resilience Boundary**:
   - Jika validasi lolos, kontrol diteruskan ke Handler.
   - Panggilan ke dependensi downstream dibungkus oleh `ResiliencePipeline`.
   - Engine mengevaluasi status *Circuit Breaker*: Jika `Open`, request langsung ditolak dengan `BrokenCircuitException` tanpa menyentuh jaringan.
   - Jika `Closed`, request dikirimkan dengan *Timeout* dan *Retry with Full Jitter*.
4. **Exception Handling & Problem Details Generation**:
   - Jika terjadi exception (misal: timeout, downstream fault, atau validation error), alur ditangkap oleh `ExceptionHandlerMiddleware`.
   - `CustomExceptionHandler` menentukan mapping status HTTP (misal: `ValidationException` -> `400 Bad Request`, `NotFoundException` -> `404 Not Found`, `TimeoutRejectedException` -> `504 Gateway Timeout`).
   - Response diformat menjadi `ProblemDetails` RFC 7807 dan dikirim ke client dengan MIME type `application/problem+json`.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Kelistrikan Rumah Pintar
Bayangkan sebuah instalasi listrik modern di gedung bertingkat:
- **Validation (FluentValidation)**: Petugas keamanan di gerbang yang memeriksa ukuran dan izin muatan truk barang sebelum masuk gerbang. Truk ilegal langsung ditolak di pos gerbang tanpa membebani lift barang.
- **Circuit Breaker (Polly)**: MCB (Miniature Circuit Breaker) di panel listrik. Jika terjadi korsleting (downstream API down), MCB langsung jeglek (trip). Arus listrik seketika diputus agar kabel tidak terbakar (mencegah *thread pool starvation*).
- **Hedging (Polly)**: Memesan dua taksi secara bersamaan dari dua aplikasi berbeda pada jam sibuk; naik taksi yang tiba lebih dahulu, dan membatalkan pesanan taksi yang lain secara instan.
- **Problem Details (RFC 7807)**: Formulir klaim asuransi standar internasional. Apapun jenis kecelakaannya, formulir memiliki nomor registrasi, kode insiden, penyebab, dan cap stempel yang sama polanya, memudahkan audit pihak ketiga.

### Arsitektur Alur Request & Eksepsi
```
+---------------------------------------------------------------------------------------+
| HTTP POST /api/v1/payments                                                            |
+---------------------------------------------------------------------------------------+
     │
     ▼
[ CorrelationIdMiddleware ] ---> Tempel Activity.Current.TraceId
     │
     ▼
[ ExceptionHandlerMiddleware ] <----+ (Menangkap Unhandled Exception)
     │                              │
     ▼                              │
[ ValidationBehavior (MediatR) ]    │
     │                              │
     ├── Invalid Data? ─────────────+ Throw ValidationException (RFC 400)
     │   (Fast Fail)                │
     ▼ Valid Data                   │
[ ProcessPaymentCommandHandler ]    │
     │                              │
     ▼ (Call Downstream Gateway)    │
+--------------------------------+  │
| Polly v8 Resilience Pipeline   |  │
|  - RateLimiter (Client-Level)  |  │
|  - CircuitBreaker              |  │
|  - Timeout (e.g. 2.5s)         |  │
|  - Retry (Jitter Backoff)      |  │
+--------------------------------+  │
     │                              │
     ├── Downstream 500 / Hang? ────+ Throw TimeoutRejected / BrokenCircuit (RFC 503/504)
     ▼
[ External Payment Gateway API ]
```

---

## 7. Practical Example (Enterprise Grade Implementation)

Implementasi berikut menggunakan .NET 8 / C# 12 murni tanpa modul tiruan.

### 1. Model Domain, Response, dan Request
```csharp
namespace Enterprise.Core.Contracts;

public sealed record ProcessPaymentCommand(
    Guid OrderId,
    decimal Amount,
    string Currency,
    string CardToken
);

public sealed record PaymentResult(
    Guid TransactionId,
    string Status,
    DateTime ProcessedAtUtc
);
```

### 2. FluentValidation Implementation
```csharp
using FluentValidation;

namespace Enterprise.Core.Validation;

public sealed class ProcessPaymentCommandValidator : AbstractValidator<ProcessPaymentCommand>
{
    private static readonly string[] SupportedCurrencies = ["USD", "EUR", "IDR", "SGD"];

    public ProcessPaymentCommandValidator()
    {
        RuleFor(x => x.OrderId)
            .NotEmpty().WithMessage("OrderId wajib disertakan.");

        RuleFor(x => x.Amount)
            .GreaterThan(0).WithMessage("Nominal transaksi harus lebih besar dari 0.")
            .PrecisionScale(18, 2, false).WithMessage("Format desimal maksimal 2 angka di belakang koma.");

        RuleFor(x => x.Currency)
            .NotEmpty()
            .Must(c => SupportedCurrencies.Contains(c))
            .WithMessage(x => $"Mata uang '{x.Currency}' tidak didukung. Pilihan: {string.Join(", ", SupportedCurrencies)}");

        RuleFor(x => x.CardToken)
            .NotEmpty().WithMessage("CardToken representasi instrumen bayar wajib diisi.")
            .Matches(@"^tok_[a-zA-Z0-9]{24,32}$").WithMessage("Format CardToken tidak valid.");
    }
}
```

### 3. Pipeline Behavior MediatR untuk Validasi Otomatis
```csharp
using FluentValidation;
using MediatR;

namespace Enterprise.Core.Behaviors;

public sealed class ValidationBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : notnull
{
    private readonly IEnumerable<IValidator<TRequest>> _validators;

    public ValidationBehavior(IEnumerable<IValidator<TRequest>> validators)
    {
        _validators = validators;
    }

    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        if (!_validators.Any())
        {
            return await next();
        }

        var context = new ValidationContext<TRequest>(request);

        var validationResults = await Task.WhenAll(
            _validators.Select(v => v.ValidateAsync(context, cancellationToken))
        );

        var failures = validationResults
            .SelectMany(r => r.Errors)
            .Where(f => f is not null)
            .ToList();

        if (failures.Count != 0)
        {
            throw new ValidationException(failures);
        }

        return await next();
    }
}
```

### 4. Global Exception Handler Berbasis RFC 7807 (`IExceptionHandler`)
```csharp
using System.Diagnostics;
using FluentValidation;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Polly.CircuitBreaker;
using Polly.Timeout;

namespace Enterprise.Core.Exceptions;

public sealed class GlobalExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(
        IProblemDetailsService problemDetailsService,
        ILogger<GlobalExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        var traceId = Activity.Current?.Id ?? httpContext.TraceIdentifier;

        _logger.LogError(
            exception,
            "Terjadi kesalahan fatal selama pemrosesan request. TraceId: {TraceId}",
            traceId);

        var (statusCode, title, detail, extensions) = exception switch
        {
            ValidationException valEx => (
                StatusCodes.Status400BadRequest,
                "Bad Request - Validation Failure",
                "Satu atau lebih bidang request tidak memenuhi aturan validasi.",
                new Dictionary<string, object?>
                {
                    ["errors"] = valEx.Errors
                        .GroupBy(e => e.PropertyName)
                        .ToDictionary(g => g.Key, g => g.Select(e => e.ErrorMessage).ToArray())
                }),

            BrokenCircuitException => (
                StatusCodes.Status503ServiceUnavailable,
                "Service Downstream Unavailable",
                "Sistem pembayaran pihak ketiga sedang mengalami gangguan berkepanjangan. Circuit Breaker Terbuka.",
                null),

            TimeoutRejectedException => (
                StatusCodes.Status504GatewayTimeout,
                "Gateway Timeout",
                "Dependensi eksternal gagal memberikan respons dalam batas waktu yang ditentukan.",
                null),

            _ => (
                StatusCodes.Status500InternalServerError,
                "Internal Server Error",
                "Terjadi kesalahan internal yang tidak dapat dipulihkan.",
                null)
        };

        httpContext.Response.StatusCode = statusCode;

        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = detail,
            Instance = httpContext.Request.Path
        };

        problemDetails.Extensions["traceId"] = traceId;
        problemDetails.Extensions["timestampUtc"] = DateTime.UtcNow;

        if (extensions is not null)
        {
            foreach (var (key, value) in extensions)
            {
                problemDetails.Extensions[key] = value;
            }
        }

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            ProblemDetails = problemDetails,
            Exception = exception
        });
    }
}
```

### 5. Konfigurasi Polly v8 Resilient HTTP Client
```csharp
using System.Net;
using Microsoft.Extensions.DependencyInjection;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using Polly.Timeout;

namespace Enterprise.Core.Resilience;

public static class ResilienceRegistrationExtensions
{
    public static IServiceCollection AddPaymentGatewayClient(
        this IServiceCollection services, 
        IConfiguration configuration)
    {
        services.AddHttpClient("PaymentGatewayClient", client =>
        {
            client.BaseAddress = new Uri(configuration["PaymentGateway:BaseUrl"] 
                ?? "https://api.paymentprovider.internal/");
            client.DefaultRequestHeaders.Add("Accept", "application/json");
        })
        .AddResilienceHandler("payment-resilience-pipeline", builder =>
        {
            // 1. Rate Limiting (Maksimal 100 concurrent ops, antrean 50)
            builder.AddConcurrencyLimiter(100, 50);

            // 2. Timeout Per Attempt
            builder.AddTimeout(new TimeoutStrategyOptions
            {
                Timeout = TimeSpan.FromSeconds(3)
            });

            // 3. Retry Strategy dengan Exponential Backoff & Full Jitter
            builder.AddRetry(new RetryStrategyOptions<HttpResponseMessage>
            {
                MaxRetryAttempts = 3,
                BackoffType = DelayBackoffType.Exponential,
                UseJitter = true,
                Delay = TimeSpan.FromMilliseconds(300),
                ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
                    .Handle<HttpRequestException>()
                    .Handle<TimeoutRejectedException>()
                    .HandleResult(res => res.StatusCode is HttpStatusCode.InternalServerError 
                                      or HttpStatusCode.BadGateway 
                                      or HttpStatusCode.ServiceUnavailable 
                                      or HttpStatusCode.GatewayTimeout)
            });

            // 4. Advanced Circuit Breaker
            builder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
            {
                FailureRatio = 0.5, // 50% kegagalan dalam window
                SamplingDuration = TimeSpan.FromSeconds(30),
                MinimumThroughput = 20, // Minimal 20 request sebelum evaluasi dimulai
                BreakDuration = TimeSpan.FromSeconds(15),
                ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
                    .Handle<HttpRequestException>()
                    .Handle<TimeoutRejectedException>()
                    .HandleResult(res => (int)res.StatusCode >= 500)
            });

            // 5. Total Combined Timeout Execution
            builder.AddTimeout(new TimeoutStrategyOptions
            {
                Timeout = TimeSpan.FromSeconds(10)
            });
        });

        return services;
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Payment Switch High-Throughput (Flash Sale E-Commerce)
- **Kondisi Beban**: 25.000 Request/detik saat event promo berlangsung serentak.
- **Masalah**: Salah satu bank partner (*Acquiring Bank B*) mengalami penurunan performa drastis (*degraded performance*). Respon yang biasanya ~200ms membengkak menjadi 45 detik sebelum akhirnya timeout.
- **Dampak Awal Tanpa Fault Tolerance Modern**:
  1. Thread pool ASP.NET Core habis terpakai (*starvation*) karena ribuan thread menunggu I/O socket yang macet.
  2. Latensi rata-rata API Gateway melonjak dari 40ms menjadi 12.000ms.
  3. Kestrel menolak koneksi baru (*HTTP 503 Server Too Busy*), melumpuhkan sistem pembayaran untuk bank lain yang sebenarnya sehat (*cascading failure*).

### Solusi Arsitektur
1. **Dynamic Hedging & Circuit Breaker**:
   - Jika Gateway Bank B tidak merespons dalam 1.200ms (p95 threshold), Polly secara proaktif memicu request paralel (*hedging*) ke Bank Partner Alternatif (Bank C).
   - Apabila rasio kegagalan Bank B mencapai 40% dalam 20 detik, *Circuit Breaker* membuka sirkuit ke Bank B selama 30 detik.
2. **Kompensasi Fallback Otomatis**:
   - Transaksi baru langsung dialihkan ke Bank C secara deterministik tanpa interupsi pengguna.
3. **Problem Details dengan Machine-Readable Fault Code**:
   - Apabila seluruh kanal acquire gagal, klien mendapatkan payload RFC 7807 berisi kode spesifik `BANK_PARTNER_CONGESTION` sehingga aplikasi front-end otomatis menawarkan opsi metode pembayaran alternatif (seperti Virtual Account bank lain / E-Wallet).

---

## 9. Trade-offs

| Dimensi Rekayasa | Opsi Dipilih: Resilient Pipeline + RFC 7807 | Alternatif: Bare Minimal Manual Handling |
| :--- | :--- | :--- |
| **Latency Impact** | Menambah overhead ~0.5ms - 2ms untuk evaluasi state machine Polly dan pipeline interception. | Nol overhead abstraksi; eksekusi raw code lebih cepat secara teoretis. |
| **Memory Allocation** | Relatif rendah pada Polly v8, tetapi FluentValidation menghasilkan alokasi objek sementara untuk string errors. | Zero memory footprint tambahan jika mengandalkan status code murni tanpa payload error detail. |
| **Cascading Resilience**| **Sangat Tinggi**. Mencegah kegagalan total sistem terdistribusi melalui fail-fast dan resource isolation. | **Sangat Rendah**. Risiko tinggi kegagalan berantai (*domino effect*) melumpuhkan seluruh cluster aplikasi. |
| **Developer Ergonomics**| Terpusat, aturan deklaratif, logging konsisten, mudah diuji via unit/integration test. | Terfragmentasi, duplikasi kode penanganan error dan perulangan `try-catch` di ratusan endpoint. |

---

## 10. Common Mistakes & Troubleshooting

### 1. *Retry Storms* Akibat Absennya Jitter
- **Kesalahan**: Mengonfigurasi Retry dengan interval tetap (misal: tepat tiap 2 detik).
- **Dampak**: Ketika downstream server sempat down dan pulih, ribuan request me-retry di detik yang sama persis, menghantam downstream server hingga crash kembali (*thundering herd problem*).
- **Solusi**: Wajib gunakan `DelayBackoffType.Exponential` dengan `UseJitter = true`.

### 2. Mengabaikan `CancellationToken` pada Rantai Asinkron
- **Kesalahan**: Menerima `CancellationToken` di Controller/Handler tetapi tidak meneruskannya ke method `HttpClient.SendAsync`, `DbContext.SaveChangesAsync`, atau Polly Pipeline.
- **Dampak**: Saat client memutus koneksi (misal browser ditutup), server tetap menjalankan eksekusi downstream dan database yang mahal hingga selesai secara sia-sia.
- **Solusi**: Teruskan parameter `CancellationToken` di seluruh level call-stack.

### 3. Masking Critical Exceptions
- **Kesalahan**: Menangkap `System.Exception` dan mengembalikan respons sukses dengan status string `"FAILED"`.
- **Dampak**: Monitoring APM (Datadog, Dynatrace, New Relic) mendeteksi request sebagai HTTP 200 OK, menyamarkan SLO/SLA yang memburuk dari deteksi alert engineer.
- **Solusi**: Gunakan status code HTTP yang presisi via ProblemDetails RFC 7807 (4xx untuk kesalahan klien, 5xx untuk anomali infrastruktur).

---

## 11. Best Practices (Production Checklist)

- [ ] **Problem Details Format**: Selalu sertakan `traceId` (W3C standard) pada extension `ProblemDetails` agar support team dapat melacak log di OpenTelemetry/Elasticsearch langsung dari layar pengguna.
- [ ] **Idempotency on Retries**: Jangan pernah menjalankan auto-retry tanpa proteksi idempoten untuk method non-idempoten (seperti `POST /payments`). Pastikan downstream API mendukung `Idempotency-Key` header.
- [ ] **Circuit Breaker Granularity**: Pisahkan instans Circuit Breaker per target endpoint/host, bukan satu circuit breaker global untuk seluruh koneksi HTTP downstream.
- [ ] **Validation Short-Circuit**: Terapkan `CascadeMode = CascadeMode.Stop` pada FluentValidation untuk rule yang berat (seperti pengecekan DB asinkron) agar tidak dieksekusi jika validasi format dasar sudah gagal.
- [ ] **Graceful Degradation**: Sediakan data fallback yang masuk akal (misal: mengambil data rekomendasi dari redis-cache lokal jika Microservice Machine Learning down).

---

## 12. Hands-on Practice

Simpan seluruh file berikut ke dalam struktur direktori: `hands-on/m02/`

### Struktur File:
```text
hands-on/m02/
├── EnterpriseResilienceApi/
│   ├── Controllers/
│   │   └── OrdersController.cs
│   ├── Domain/
│   │   └── OrderContracts.cs
│   ├── Infrastructure/
│   │   ├── ResilientPaymentService.cs
│   │   └── GlobalExceptionHandler.cs
│   ├── Validation/
│   │   └── CreateOrderValidator.cs
│   ├── appsettings.json
│   ├── Program.cs
│   └── EnterpriseResilienceApi.csproj
```

### Langkah 1: Inisialisasi Project dan Dependency
Jalankan perintah shell berikut:
```bash
mkdir -p hands-on/m02/EnterpriseResilienceApi
cd hands-on/m02/EnterpriseResilienceApi
dotnet new webapi -controllers -f net8.0
dotnet add package FluentValidation.AspNetCore
dotnet add package Microsoft.Extensions.Resilience
```

### Langkah 2: Buat File Domain Contracts (`Domain/OrderContracts.cs`)
```csharp
namespace EnterpriseResilienceApi.Domain;

public sealed record CreateOrderRequest(
    string CustomerId,
    decimal TotalAmount,
    string ItemCode,
    int Quantity
);

public sealed record OrderResponse(
    Guid OrderId,
    string Status,
    string PaymentReference,
    DateTime CreatedAtUtc
);
```

### Langkah 3: Buat Validator FluentValidation (`Validation/CreateOrderValidator.cs`)
```csharp
using FluentValidation;
using EnterpriseResilienceApi.Domain;

namespace EnterpriseResilienceApi.Validation;

public sealed class CreateOrderValidator : AbstractValidator<CreateOrderRequest>
{
    public CreateOrderValidator()
    {
        RuleFor(x => x.CustomerId)
            .NotEmpty().WithMessage("CustomerId tidak boleh kosong.")
            .MinimumLength(5).WithMessage("CustomerId minimal 5 karakter.");

        RuleFor(x => x.TotalAmount)
            .GreaterThan(0).WithMessage("TotalAmount harus bernilai positif.");

        RuleFor(x => x.ItemCode)
            .NotEmpty().WithMessage("ItemCode wajib diisi.")
            .Matches(@"^[A-Z]{3}-\d{4}$").WithMessage("ItemCode harus memiliki format XXX-9999 (misal: PRD-1024).");

        RuleFor(x => x.Quantity)
            .InclusiveBetween(1, 100).WithMessage("Kuantitas pemesanan hanya diizinkan antara 1 hingga 100 unit.");
    }
}
```

### Langkah 4: Implementasikan Exception Handler RFC 7807 (`Infrastructure/GlobalExceptionHandler.cs`)
```csharp
using System.Diagnostics;
using FluentValidation;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Polly.CircuitBreaker;
using Polly.Timeout;

namespace EnterpriseResilienceApi.Infrastructure;

public sealed class GlobalExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(IProblemDetailsService problemDetailsService, ILogger<GlobalExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        var traceId = Activity.Current?.Id ?? httpContext.TraceIdentifier;
        _logger.LogError(exception, "Unhandled Exception tertangkap di GlobalExceptionHandler. TraceId: {TraceId}", traceId);

        var (statusCode, title, detail) = exception switch
        {
            ValidationException valEx => (
                StatusCodes.Status400BadRequest,
                "Validation Error",
                string.Join("; ", valEx.Errors.Select(e => e.ErrorMessage))),

            BrokenCircuitException => (
                StatusCodes.Status503ServiceUnavailable,
                "Circuit Breaker Active",
                "Downstream dependency sedang tidak stabil. Request dihentikan sementara."),

            TimeoutRejectedException => (
                StatusCodes.Status504GatewayTimeout,
                "Request Timeout",
                "Batas waktu eksekusi operasi downstream terlampaui."),

            _ => (
                StatusCodes.Status500InternalServerError,
                "Server Fault",
                "Terjadi kesalahan internal yang tidak diharapkan pada server.")
        };

        httpContext.Response.StatusCode = statusCode;

        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = detail,
            Instance = httpContext.Request.Path
        };

        problemDetails.Extensions["traceId"] = traceId;

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            ProblemDetails = problemDetails,
            Exception = exception
        });
    }
}
```

### Langkah 5: Buat Resilient Payment Service (`Infrastructure/ResilientPaymentService.cs`)
```csharp
using Polly;
using Polly.Registry;

namespace EnterpriseResilienceApi.Infrastructure;

public interface IPaymentService
{
    Task<string> ExecutePaymentAsync(decimal amount, CancellationToken cancellationToken);
}

public sealed class ResilientPaymentService : IPaymentService
{
    private readonly HttpClient _httpClient;
    private readonly ResiliencePipeline _pipeline;
    private readonly ILogger<ResilientPaymentService> _logger;

    public ResilientPaymentService(
        HttpClient httpClient,
        ResiliencePipelineProvider<string> pipelineProvider,
        ILogger<ResilientPaymentService> logger)
    {
        _httpClient = httpClient;
        _pipeline = pipelineProvider.GetPipeline("payment-resilience-pipeline");
        _logger = logger;
    }

    public async Task<string> ExecutePaymentAsync(decimal amount, CancellationToken cancellationToken)
    {
        return await _pipeline.ExecuteAsync(async token =>
        {
            _logger.LogInformation("Mengirim payload pembayaran ke downstream...");
            
            // Mensimulasikan pemanggilan REST downstream yang fluktuatif
            var response = await _httpClient.GetAsync($"/simulate-payment?amount={amount}", token);
            response.EnsureSuccessStatusCode();

            return await response.Content.ReadAsStringAsync(token);
        }, cancellationToken);
    }
}
```

### Langkah 6: Konfigurasi `Program.cs`
```csharp
using FluentValidation;
using EnterpriseResilienceApi.Domain;
using EnterpriseResilienceApi.Infrastructure;
using EnterpriseResilienceApi.Validation;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using Polly.Timeout;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();

// Registrasi FluentValidation
builder.Services.AddValidatorsFromAssemblyContaining<CreateOrderValidator>();

// Registrasi Polly Resilience Pipeline via ResilientPipelineBuilder
builder.Services.AddResiliencePipeline("payment-resilience-pipeline", pipelineBuilder =>
{
    pipelineBuilder
        .AddTimeout(new TimeoutStrategyOptions
        {
            Timeout = TimeSpan.FromSeconds(2)
        })
        .AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 2,
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            Delay = TimeSpan.FromMilliseconds(200)
        })
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 4,
            BreakDuration = TimeSpan.FromSeconds(10)
        });
});

// Mock HttpClient untuk simulasi downstream
builder.Services.AddHttpClient<IPaymentService, ResilientPaymentService>(client =>
{
    client.BaseAddress = new Uri("https://httpstat.us");
});

var app = builder.Build();

app.UseExceptionHandler();

app.MapPost("/api/orders", async (
    CreateOrderRequest request,
    IValidator<CreateOrderRequest> validator,
    IPaymentService paymentService,
    CancellationToken ct) =>
{
    var validationResult = await validator.ValidateAsync(request, ct);
    if (!validationResult.IsValid)
    {
        throw new ValidationException(validationResult.Errors);
    }

    var paymentRef = await paymentService.ExecutePaymentAsync(request.TotalAmount, ct);

    var response = new OrderResponse(
        Guid.NewGuid(),
        "CONFIRMED",
        paymentRef,
        DateTime.UtcNow
    );

    return Results.Ok(response);
});

// Endpoint untuk simulasi downstream failure
app.MapGet("/simulate-payment", (decimal amount) =>
{
    // Simulasi kegagalan acak
    var random = Random.Shared.Next(1, 10);
    if (random <= 6) // 60% peluang kegagalan internal downstream
    {
        return Results.StatusCode(StatusCodes.Status500InternalServerError);
    }
    return Results.Ok($"TXN-SUCCESS-{Guid.NewGuid():N}");
});

app.Run();
```

---

## 13. Exercise

### Level Easy
Modifikasi `CreateOrderValidator` agar menambahkan validasi opsional: Jika `TotalAmount` bernilai di atas 10.000.000, maka `Quantity` tidak boleh lebih dari 5 unit (Aturan *High Value Anti-Fraud*).

### Level Medium
Tambahkan *Fallback Strategy* pada pipeline Polly di `ResilientPaymentService`. Jika Circuit Breaker sedang `Open` atau request mengalami timeout berulang kali, kembalikan response default bertuliskan `"OFFLINE_PAYMENT_QUEUED"` dan status code HTTP 202 Accepted, bukan membiarkan request berakhir 503 Service Unavailable.

### Level Hard
Implementasikan sebuah Custom MediatR Pipeline Behavior (`ResiliencePipelineBehavior<TRequest, TResponse>`) generik yang menerapkan Polly Resilience Pipeline langsung pada pemanggilan Handler in-process, memanfaatkan Attribute `[ResilientCommand(StrategyName = "CriticalStrategy")]` yang disematkan secara deklaratif di atas Command class.

---

## 14. Challenge

**Skenario**: Anda adalah Lead Architect pada sistem Core Banking yang menangani transfer kliring antar-bank pada jam operasional puncak (*peak hours*).
- **Spesifikasi Beban**: 80.000 request/menit terdistribusi pada 4 bank kliring yang berbeda.
- **Batasan Downstream**: Masing-masing bank partner memiliki limitasi konkurensi (Bank 1: 50 req/sec, Bank 2: 30 req/sec, Bank 3 & 4: 100 req/sec). Setiap bank memiliki karakteristik degradasi latensi yang berbeda secara dinamis.
- **Tugas**:
  1. Rancang arsitektur sistem fault tolerance menggunakan .NET 8 yang mampu mempartisi rate-limiting dan circuit breaking per-tenant (per-kode bank target) secara dinamis menggunakan `ResiliencePipelineRegistry<string>`.
  2. Pastikan jika salah satu bank mengalami kegagalan, pesan transaksi tidak dibuang melainkan diarahkan secara asinkron ke antrean transit (*Dead-Letter Buffer*) menggunakan transactional outbox pattern terisolasi, sembari memformat response RFC 7807 secara presisi kepada client yang memuat estimasi ketersediaan downstream kembali (*Retry-After* header).
  3. Buktikan secara arsitektural bahwa implementasi ini tidak akan menyebabkan alokasi memori heap berlebih (*zero high-gen GC pressure*) di bawah beban maksimum.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa fungsi dari spesifikasi RFC 7807 dalam perancangan API enterprise modern?
2. Mengapa penggunaan `try-catch` manual di setiap controller action dianggap sebagai *anti-pattern* pada ASP.NET Core?
3. Sebutkan perbedaan perilaku dasar antara status Circuit Breaker `Closed`, `Open`, dan `Half-Open`!
4. Mengapa penerapan validasi via MediatR Pipeline Behavior lebih unggul dibanding meletakkan kode validasi di dalam constructor Command/DTO?
5. Apa kegunaan utama interface `IExceptionHandler` yang diperkenalkan pada .NET 8 menggantikan middleware konvensional?

### 5 Pertanyaan Intermediate
1. Mengapa penambahan mekanisme *Jitter* sangat krusial saat merancang strategi Exponential Backoff Retry pada sistem terdistribusi skala besar?
2. Bagaimana mekanisme kerja `IProblemDetailsService` dalam mengekspos Activity Trace ID W3C tanpa menyebabkan overhead parsing log secara manual?
3. Apa perbedaan esensial dari strategi ketahanan isolasi *Bulkhead* (Concurrency Limiter) dibanding *Rate Limiter* konvensional?
4. Kapan sebaiknya strategi *Hedging* digunakan, dan mengapa strategi ini berbahaya jika dieksekusi pada endpoint yang tidak idempoten?
5. Bagaimana cara kerja integrasi antara `CancellationToken` milik Kestrel engine dengan `Polly.Timeout` pipeline agar resource downstream socket segera terbebas saat koneksi klien terputus mendadak?

### 3 Skenario Kasus Produksi
1. **Kasus 1**: Sistem Anda menggunakan Polly Retry (3x) terhadap downstream API. Saat downstream API mengalami pemadaman total (total outage), CPU Usage pada aplikasi ASP.NET Core Anda justru melonjak hingga 100% dan latency melonjak drastis bagi seluruh user. Diagnosis akar masalah arsitekturalnya dan berikan solusi perbaikannya!
2. **Kasus 2**: Client enterprise Anda melaporkan bahwa ketika mereka mengirimkan payload JSON invalid ke API, beberapa error ditolak dengan status HTTP 400 disertai RFC 7807, tetapi validasi terkait database uniqueness lolos dan menghasilkan HTTP 500 unhandled DB conflict. Bagaimana menstrukturkan pipeline validasi dua tingkat secara elegan?
3. **Kasus 3**: Audit keamanan mendeteksi bahwa pesan *exception detail* pada production environment secara tidak sengaja membocorkan potongan connection string database ke dalam attribute `detail` ProblemDetails. Desain bagaimana mengamankan pipeline `IExceptionHandler` agar informasi sensitif di-sanitasi secara deterministik tanpa menghilangkan jejak `TraceId` untuk debugging internal tim SRE.

---

## 16. Summary

- Validasi enterprise modern memisahkan aturan input secara deklaratif dari logic endpoint melalui **FluentValidation** dan **MediatR Pipeline Behavior**, menghasilkan kode yang *testable*, *decoupled*, dan *fast-failing*.
- Mulai .NET 8+, penanganan kesalahan terpusat disederhanakan dan dibakukan melalui interface **`IExceptionHandler`** dan **`IProblemDetailsService`**, memproduksi respon kesalahan terstandarisasi **RFC 7807 (`application/problem+json`)** yang secara konsisten mengaitkan konteks metadata tracing observabilitas (`TraceId`).
- Ketahanan sistem terdistribusi membutuhkan strategi proaktif di level infrastruktur. **Polly v8** menyediakan engine ketahanan terpadu (*Resilience Pipelines*) yang mengintegrasikan **Concurrency Limiter, Timeout, Exponential Backoff with Jitter, dan Circuit Breaker** secara efisien tanpa penalti alokasi memori berlebih.
- Kombinasi validasi komprehensif, pelaporan error standar, dan ketahanan terhadap dependensi eksternal menjamin aplikasi enterprise tidak mengalami kegagalan kaskade (*cascading failure*), menjaga ketersediaan sistem (*high availability*), dan mempertahankan SLO/SLA yang tinggi di bawah tekanan beban produksi ekstrem.