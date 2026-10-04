# Bab 09 Module 01: Resiliency, Observability & Enterprise Security

---

## SEKSI 01 — IDENTITAS MODUL

* **Mata Kuliah / Jalur Keahlian:** Pemrograman C# & Arsitektur .NET Lanjutan (Advanced .NET Core & Cloud-Native Engineering)
* **Kategori:** 02-Programming-Languages
* **Kode Modul:** CS-ADV-0901
* **Judul Modul:** Resiliency, Observability & Enterprise Security
* **Tingkat Kesulitan:** Advanced / Enterprise Grade
* **Prasyarat:** Pemahaman mendalam tentang C# Asynchronous Programming (`async`/`await`, `Task`, `ValueTask`), Dependency Injection, Middleware ASP.NET Core, HTTP Client Lifecycle (`IHttpClientFactory`), serta dasar-dasar Distributed Systems.
* **Target Runtime / SDK:** .NET 8.0 / .NET 9.0 LTS
* **Dependencies Utama:**
  * `Microsoft.Extensions.Resilience` (Polly v8)
  * `OpenTelemetry.Exporter.OpenTelemetryProtocol` (OTLP)
  * `OpenTelemetry.Extensions.Hosting`
  * `OpenTelemetry.Instrumentation.AspNetCore`
  * `OpenTelemetry.Instrumentation.Http`
  * `Microsoft.AspNetCore.Authentication.JwtBearer`
  * `Microsoft.AspNetCore.DataProtection`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Resilience Pipeline Modern (Polly v8):** Mengonfigurasi strategi *fault tolerance* reaktif dan proaktif—mencakup *Circuit Breaker*, *Exponential Backoff with Jitter*, *Rate Limiting*, *Hedging*, dan *Bulkhead Isolation* menggunakan API berbasis zero-allocation pipeline di .NET 8/9.
2. **Membangun Telemetri Cloud-Native dengan OpenTelemetry (Three Pillars of Observability):** Menginstrumentasi aplikasi secara end-to-end melalui Distributed Tracing (`System.Diagnostics.ActivitySource`), Metric Instruments (`System.Diagnostics.Metrics.Meter`), serta Structured Logging yang mematuhi W3C Trace Context standards.
3. **Menerapkan Proteksi Kriptografis dan Enterprise Identity Management:** Mengonfigurasi *ASP.NET Core Data Protection API* (DPAPI) untuk distributed environments, mengamankan pipeline HTTP melalui validasi JWT berbasis OAuth2/OIDC, mencegah serangan SSRF dan *Resource Exhaustion*, serta mengisolasi secret.
4. **Menganalisis Trade-Off Performa dan Resiliensi:** Mengevaluasi dampak latensi, *tail latency amplification*, alokasi memori heap, dan *thread-pool starvation* saat resilience wrapper diinjeksi pada high-throughput network call.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### The Fallacies of Distributed Computing
Dalam arsitektur monolitik in-process, pemanggilan metode bersifat deterministik: fungsi dipanggil, memori dialokasikan pada stack/heap lokal, dan hasil langsung dikembalikan atau menghasilkan *synchronous exception*. Dalam sistem terdistribusi mikroservis enterprise, asumsi ini hancur. Anda **harus** mengadopsi prinsip *Zero-Trust Network* dan *Expect-Failure Engineering*.

```
[In-Process Call]
Caller ------------(Direct Stack/Heap Jump)------------> Callee
   - Latency: ~Nanoseconds
   - Failure Modes: NullReference, OOM (Deterministic)

[Distributed Network Call]
Caller ---[Serializing]---[TCP Stack]---[Router]---[Firewall]---[Network Hop]---> Callee
   |                                                                                |
   +<---[Timeout? Latency Spike? Drop? 503 Service Unavailable? Split Brain?]-------+
   - Latency: ~Milliseconds s/d Seconds
   - Failure Modes: Partial Outage, Packet Loss, Cascading Exhaustion (Non-deterministic)
```

### Triad Keseimbangan: Resiliency, Observability, dan Security
Ketiga pilar ini tidak dapat dipisahkan:
1. **Resiliency tanpa Observability adalah Kebutaan:** Ketika *Circuit Breaker* trip ke status `Open`, tanpa tracing terdistribusi Anda tidak akan tahu simpul hulu mana yang memicu kaskade kegagalan tersebut.
2. **Resiliency tanpa Security adalah Kerentanan Eksploitasi:** Fitur *Retry* yang agresif tanpa *Rate Limiting* dapat disalahgunakan oleh penyerang menjadi vektor serangan *Denial of Service* (DoS) reflektif internal.
3. **Security tanpa Resiliency dan Observability adalah Kegagalan Operasional:** Mekanisme kriptografi atau validasi token eksternal (misal: fetching JWKS endpoint) yang gagal dihubungi tanpa fallback atau caching pipeline akan melumpuhkan seluruh otentikasi sistem.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran permintaan HTTP masuk yang diproteksi dari lapis otentikasi, diinstrumentasi via OpenTelemetry, dan dialirkan ke layanan hulu (upstream downstream) melalui Resilience Pipeline:

```
[Client / API Consumer]
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ASP.NET Core Request Pipeline                                          │
│                                                                        │
│ 1. [OpenTelemetry Diagnostic Listener]                                 │
│    - Extracts W3C Traceparent Header (trace-id, span-id)               │
│    - Creates root Activity / Span                                      │
│                                                                        │
│ 2. [Security & Authentication Layer]                                  │
│    - OAuth2 Bearer Token Extraction                                    │
│    - Cryptographic Signature Verification (JWKS)                      │
│    - Enforces Rate Limiter (Concurrency / Token Bucket)                │
│                                                                        │
│ 3. [Application Service / Domain Logic]                               │
│    - Executes Core Business Rules                                      │
│    - Emits Business Metrics (Counter, Histogram)                       │
│                                                                        │
│ 4. [Outgoing HTTP Request via Resilient HttpClient]                    │
│    ┌─────────────────────────────────────────────────────────────┐     │
│    │ Resilience Pipeline (Polly v8 Composition)                  │     │
│    │                                                             │     │
│    │  [Rate Limiter Strategy]                                    │     │
│    │         │ (Reject if bucket empty)                          │     │
│    │         ▼                                                   │     │
│    │  [Total Timeout Strategy] (Overall Budget: e.g., 5s)        │     │
│    │         │                                                   │     │
│    │         ▼                                                   │     │
│    │  [Retry Strategy with Jitter] (Attempts: 3, Backoff: Expo)  │     │
│    │         │                                                   │     │
│    │         ▼                                                   │     │
│    │  [Circuit Breaker Strategy] (State: Closed/Open/Half-Open)  │     │
│    │         │                                                   │     │
│    │         ▼                                                   │     │
│    │  [Attempt Timeout Strategy] (Per-try Budget: e.g., 1.5s)    │     │
│    │         │                                                   │     │
│    │         ▼                                                   │     │
│    │  [SocketsHttpHandler] (Connection Pooling, DNS Refresh)     │     │
│    └─────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼ Network Call
┌────────────────────────────────────────────────────────────────────────┐
│ External Downstream Service / Payment Gateway                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Polly v8: The Resilience Pipeline Engine
Pada Polly versi lama (v7 ke bawah), eksekusi kebijakan (*policy*) menggunakan alokasi delegasi berlapis (*nested closures*) yang menyebabkan alokasi memori GC (Garbage Collection) signifikan pada beban jutaan request/detik. Polly v8 merevolusi ini dengan `ResiliencePipeline`:
- **Zero/Minimal Allocation Pipeline:** Menggunakan `ResilienceContext`, struct-like execution patterns, dan delegasi statis internal.
- **Combined Strategy Execution:** Setiap strategi diurutkan secara sekuensial. Alur masuk mengeksekusi strategi dari terluar ke terdalam, sedangkan alur balik (*response/exception*) membalik urutan tersebut.
- **State Machine Circuit Breaker:**
  - `Closed`: Trafik mengalir normal. Kegagalan dihitung dalam sliding window.
  - `Open`: Jika rasio kegagalan melampaui batas (*failure threshold*), sirkuit memutus aliran seketika. Semua panggilan langsung gagal dengan `BrokenCircuitException` tanpa menyentuh jaringan.
  - `Half-Open`: Setelah masa tenang (*break duration*), sejumlah kecil uji coba (*trial requests*) diizinkan lewat. Jika berhasil, sirkuit kembali `Closed`; jika gagal, kembali ke status `Open`.

### 2. Distributed Tracing: Activity & W3C Trace Context
.NET mengintegrasikan OpenTelemetry langsung ke runtime BCL (*Base Class Library*) via namespace `System.Diagnostics`:
- **`ActivitySource` & `Activity`:** Implementasi langsung dari *Tracer* dan *Span* dalam spesifikasi OpenTelemetry.
- **Konteks Propagasi:** Header HTTP standar `traceparent` membawa format:
  `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  - `00`: Version
  - `4bf...`: TraceId (16-byte hex, global untuk seluruh request tree)
  - `00f...`: ParentId / SpanId (8-byte hex, spesifik untuk hop saat ini)
  - `01`: TraceFlags (direkam/sampled)

### 3. ASP.NET Core Data Protection Stack
Arsitektur DPAPI di ASP.NET Core memecahkan masalah enkripsi *symmetric at rest*:
- **Key Ring Management:** Kunci dirotasi secara otomatis (default 90 hari). Kunci disimpan secara eksternal (Redis/SQL Database) dan dienkripsi saat istirahat (*at rest*) menggunakan Azure Key Vault atau AWS KMS.
- **Authenticated Encryption:** Menggunakan algoritma enkripsi terautentikasi secara default (HMAC-SHA256 + AES-CBC atau AES-GCM). Data yang dilindungi tidak hanya dienkripsi, tetapi memiliki integritas yang divalidasi guna mencegah serangan pemalsuan payload (*ciphertext tampering*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Math of Jittered Exponential Backoff
Menggunakan *exponential backoff* murni ($t = B \times 2^c$) dalam sistem skala besar adalah anti-pattern yang menyebabkan fenomena **Thundering Herd Problem**. Ketika downstream node down dan pulih, ribuan request klien yang melakukan backoff pada interval yang sama persis akan membombardir downstream secara simultan di setiap kelipatan waktu $t$.

Solusinya adalah menyuntikkan keacakan (**Full Jitter** atau **Decorrelated Jitter**):

$$\text{Full Jitter: } T_{\text{sleep}} = \text{UniformRandom}(0, \min(T_{\text{max}}, B \times 2^{\text{attempt}}))$$

```
Without Jitter:
Client 1: ----[ 2s ]----> Retry ----[ 4s ]----> Retry ----[ 8s ]---->
Client 2: ----[ 2s ]----> Retry ----[ 4s ]----> Retry ----[ 8s ]---->  <-- Keduanya memukul server bersamaan!

With Decorrelated Jitter:
Client 1: --[ 1.4s ]--> Retry ------[ 4.2s ]------> Retry --[ 6.1s ]-->
Client 2: ----[ 2.3s ]----> Retry --[ 2.8s ]--> Retry --------[ 8.7s ]->  <-- Beban tersebar merata (smoothed load)
```

### Circuit Breaker Mechanics: Failure Rate vs Minimum Throughput
Mengonfigurasi Circuit Breaker hanya dengan persentase kegagalan adalah kesalahan pemula. Jika batas kegagalan diatur ke 50%, dan aplikasi hanya menerima 2 request, di mana 1 request timeout, sirkuit akan trip secara prematur.
Oleh karena itu, strategi enterprise membutuhkan **tiga parameter wajib**:
1. `FailureRatio`: Rasio kegagalan (misal: 0.5 atau 50%).
2. `MinimumThroughput`: Jumlah request minimum dalam window sampling (misal: 100 request) sebelum evaluasi rasio diaktifkan.
3. `SamplingDuration`: Rentang waktu window kalkulasi bergerak (misal: 30 detik).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi konfigurasi terintegrasi dari Resilience Pipeline menggunakan API modern `Microsoft.Extensions.Resilience` di .NET 8/9.

```csharp
// File: Program.cs
using System.Net;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using Polly.Timeout;

var builder = Host.CreateApplicationBuilder(args);

// Daftarkan Resilience Pipeline ke Dependency Injection Container
builder.Services.AddResiliencePipeline<string, HttpResponseMessage>("EnterpriseHttpPipeline", pipelineBuilder =>
{
    // 1. Total Timeout Strategy (Mencakup seluruh durasi eksekusi termasuk semua retries)
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(10),
        OnTimeout = args =>
        {
            Console.WriteLine($"[CRITICAL] Total Timeout terlampaui setelah 10 detik! Context: {args.Context.OperationKey}");
            return ValueTask.CompletedTask;
        }
    });

    // 2. Retry Strategy dengan Decorrelated Jitter
    pipelineBuilder.AddRetry(new RetryStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .Handle<TimeoutRejectedException>()
            .HandleResult(response => response.StatusCode is 
                HttpStatusCode.InternalServerError or 
                HttpStatusCode.BadGateway or 
                HttpStatusCode.ServiceUnavailable or 
                HttpStatusCode.GatewayTimeout),
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true, // Mengaktifkan Decorrelated Jitter otomatis
        Delay = TimeSpan.FromMilliseconds(500),
        OnRetry = args =>
        {
            Console.WriteLine($"[WARN] Retry attempt #{args.AttemptNumber}. Delaying for {args.RetryDelay.TotalMilliseconds}ms. Reason: {args.Outcome.Exception?.Message ?? args.Outcome.Result?.StatusCode.ToString()}");
            return ValueTask.CompletedTask;
        }
    });

    // 3. Circuit Breaker Strategy
    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .HandleResult(response => response.StatusCode is 
                HttpStatusCode.InternalServerError or 
                HttpStatusCode.ServiceUnavailable),
        FailureRatio = 0.5, // 50% kegagalan memicu circuit breaker
        MinimumThroughput = 10, // Minimal 10 request dalam sliding window
        SamplingDuration = TimeSpan.FromSeconds(30),
        BreakDuration = TimeSpan.FromSeconds(15),
        OnOpened = args =>
        {
            Console.WriteLine($"[ALERT] Circuit Breaker state berubah menjadi OPEN selama {args.BreakDuration.TotalSeconds}s! Downstream dianggap tidak sehat.");
            return ValueTask.CompletedTask;
        },
        OnClosed = _ =>
        {
            Console.WriteLine("[INFO] Circuit Breaker pulih dan kembali ke status CLOSED.");
            return ValueTask.CompletedTask;
        },
        OnHalfOpened = _ =>
        {
            Console.WriteLine("[INFO] Circuit Breaker masuk ke fase HALF-OPEN. Menguji downstream...");
            return ValueTask.CompletedTask;
        }
    });

    // 4. Per-Attempt Timeout Strategy (Mencegah satu request blocking terlalu lama)
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(2)
    });
});

var app = builder.Build();

// Contoh Eksekusi Pipeline via Keyed Provider
var pipelineProvider = app.Services.GetRequiredService<ResiliencePipelineProvider<string>>();
var pipeline = pipelineProvider.GetPipeline<HttpResponseMessage>("EnterpriseHttpPipeline");

using var httpClient = new HttpClient();

try
{
    var response = await pipeline.ExecuteAsync(async cancellationToken =>
    {
        // Eksekusi HTTP call simulasi
        return await httpClient.GetAsync("https://httpbin.org/status/503", cancellationToken);
    }, CancellationToken.None);

    Console.WriteLine($"Status Akhir: {response.StatusCode}");
}
catch (BrokenCircuitException bce)
{
    Console.WriteLine($"Permintaan ditolak seketika oleh Circuit Breaker: {bce.Message}");
}
catch (Exception ex)
{
    Console.WriteLine($"Pipeline gagal memproses request: {ex.Message}");
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari implementasi pipeline di Seksi 07:

1. **`builder.Services.AddResiliencePipeline<string, HttpResponseMessage>("EnterpriseHttpPipeline", ...)`**
   *Mendaftarkan pipeline generik yang beroperasi pada output `HttpResponseMessage` dengan key berjenis `string`. Metode ekstensi ini menyimpan konfigurasi dalam DI container secara thread-safe dan singleton.*
2. **`pipelineBuilder.AddTimeout(new TimeoutStrategyOptions { Timeout = TimeSpan.FromSeconds(10) })`**
   *Menempatkan Total Timeout di lapisan terluar. Jika kalkulasi Retry + Backoff + Processing Time melebihi 10 detik, cancellation token pipeline dibatalkan paksa.*
3. **`PredicateBuilder<HttpResponseMessage>().Handle<HttpRequestException>().HandleResult(...)`**
   *Mendefinisikan kriteria kegagalan secara granular. Pipeline hanya merespons pengecualian level transport (`HttpRequestException`) atau error HTTP 5xx tertentu. Kesalahan klien (4xx) sengaja tidak di-retry karena deterministik.*
4. **`BackoffType = DelayBackoffType.Exponential` & `UseJitter = true`**
   *Menginstruksikan kalkulator delay internal Polly v8 untuk mendistribusikan waktu tidur retry menggunakan randomisasi decorrelated, mencegah gelombang request periodik yang serempak.*
5. **`FailureRatio = 0.5` & `MinimumThroughput = 10`**
   *Mencegah false-positive. Circuit breaker tidak akan membuka sirkuit jika baru 3 request yang gagal dari total 4 request. Perhitungan persentase baru dimulai setelah ambang 10 request tercapai dalam `SamplingDuration` 30 detik.*
6. **`BreakDuration = TimeSpan.FromSeconds(15)`**
   *Waktu tunggu downstream diberi kesempatan untuk cooling down/self-healing. Selama 15 detik ini, CPU dan thread pool tidak membuang resource untuk memanggil downstream yang sudah diketahui rusak.*
7. **Per-Attempt Timeout (`TimeSpan.FromSeconds(2)`) di lapis terdalam**
   *Memastikan bahwa setiap percobaan individual segera dihentikan jika melewati 2 detik, memberi sisa waktu budget pada Total Timeout (10 detik) untuk menjalankan percobaan retry berikutnya.*

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Pemrosesan Pembayaran Berbeban Tinggi (Fintech Payment Gateway)
* **Konteks:** Sistem menangani 5.000 transaksi/detik saat flash sale. Layanan `OrderService` memanggil gateway pembayaran pihak ketiga (`AcquiringBankApi`).
* **Masalah:** Pada jam sibuk, `AcquiringBankApi` mengalami degradasi performa: latensi naik dari 200ms menjadi 15 detik per call, diikuti oleh error 504 Gateway Timeout sporadis.
* **Dampak Katastropik Awal:**
  1. Thread pool ASP.NET Core pada `OrderService` kehabisan thread pekerja (*thread pool starvation*) karena thread terblokir menunggu respons IO socket yang lambat.
  2. Retry tanpa jitter menyebabkan ribuan container mereplikasi request yang sama, memperparah downtime bank rekanan.
  3. Ketiadaan *Trace ID* cross-boundary membuat tim SRE dan Fraud Analysis gagal melacak korelasi antara keranjang belanja pengguna yang gagal dan mutasi rekening bank yang menggantung (*unreconciled state*).
* **Solusi Enterprise:**
  1. Implementasi **Bulkhead Isolation** dan **Rate Limiter** di level client untuk membatasi request konkuren maksimum ke bank rekanan hingga 200 koneksi simultan.
  2. Implementasi **OpenTelemetry Distributed Tracing** dengan propagasi traceparent standar W3C untuk menyinkronkan ID audit.
  3. Implementasi **ASP.NET Core Data Protection API** terdistribusi yang memproteksi payload kartu kredit/PII di memori cache Redis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah kode produksi terintegrasi yang menggabungkan:
1. Resilient Outgoing Client (Polly v8).
2. OpenTelemetry Tracing & Metrics (Three Pillars).
3. Secure Distributed DPAPI Data Protection.

```csharp
// Program.cs
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Net;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Mvc;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using Polly.Timeout;

var builder = WebApplication.CreateBuilder(args);

// ==========================================
// 1. OBSERVABILITY CONFIGURATION (OpenTelemetry)
// ==========================================
const string ServiceName = "Fintech.PaymentProcessor";
const string ServiceVersion = "1.0.0";

var paymentActivitySource = new ActivitySource(ServiceName, ServiceVersion);
var paymentMeter = new Meter(ServiceName, ServiceVersion);
var transactionCounter = paymentMeter.CreateCounter<long>("payments.processed.count", "transaksi", "Jumlah transaksi berhasil/gagal");
var transactionDurationHistogram = paymentMeter.CreateHistogram<double>("payments.processing.duration", "ms", "Durasi pemrosesan transaksi");

builder.Services.AddSingleton(paymentActivitySource);
builder.Services.AddSingleton(paymentMeter);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(serviceName: ServiceName, serviceVersion: ServiceVersion)
        .AddAttributes([new KeyValuePair<string, object>("deployment.environment", builder.Environment.EnvironmentName)]))
    .WithTracing(tracing => tracing
        .AddSource(ServiceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(opt => opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317")))
    .WithMetrics(metrics => metrics
        .AddMeter(ServiceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(opt => opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317")));

// ==========================================
// 2. ENTERPRISE DATA PROTECTION (DPAPI)
// ==========================================
// Menyimpan key secara persisten ke direktori aman (di produksi: Azure Blob/Redis/Vault)
var keysFolder = Path.Combine(builder.Environment.ContentRootPath, "temp-keys");
builder.Services.AddDataProtection()
    .SetApplicationName("FintechEnterpriseSystem")
    .PersistKeysToFileSystem(new DirectoryInfo(keysFolder))
    .SetDefaultKeyLifetime(TimeSpan.FromDays(90));

// ==========================================
// 3. RESILIENCE PIPELINE DEFINITION (Polly v8)
// ==========================================
builder.Services.AddResiliencePipeline<string, HttpResponseMessage>("BankGatewayPipeline", pipelineBuilder =>
{
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions { Timeout = TimeSpan.FromSeconds(5) });
    pipelineBuilder.AddRetry(new RetryStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .Handle<TimeoutRejectedException>()
            .HandleResult(r => r.StatusCode == HttpStatusCode.RequestTimeout || (int)r.StatusCode >= 500),
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true,
        Delay = TimeSpan.FromMilliseconds(300)
    });
    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .HandleResult(r => (int)r.StatusCode >= 500),
        FailureRatio = 0.4,
        MinimumThroughput = 5,
        SamplingDuration = TimeSpan.FromSeconds(20),
        BreakDuration = TimeSpan.FromSeconds(10)
    });
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions { Timeout = TimeSpan.FromSeconds(1.5) });
});

builder.Services.AddHttpClient("BankClient", client =>
{
    client.BaseAddress = new Uri("https://httpbin.org");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

var app = builder.Build();

// ==========================================
// 4. BUSINESS LOGIC & ENDPOINTS
// ==========================================
app.MapPost("/api/v1/payments/process", async (
    [FromBody] PaymentRequest request,
    [FromServices] IHttpClientFactory httpClientFactory,
    [FromServices] ResiliencePipelineProvider<string> pipelineProvider,
    [FromServices] IDataProtectionProvider dataProtectionProvider,
    [FromServices] ActivitySource activitySource,
    CancellationToken cancellationToken) =>
{
    var stopwatch = Stopwatch.StartNew();
    using var activity = activitySource.StartActivity("ProcessPaymentTransaction", ActivityKind.Internal);
    
    // Proteksi Data Sensitif (PII Enkripsi)
    var protector = dataProtectionProvider.CreateProtector("Payment.CardDetails.v1");
    string encryptedCardNumber = protector.Protect(request.CardNumber);
    
    activity?.SetTag("payment.order_id", request.OrderId);
    activity?.SetTag("payment.encrypted_payload_len", encryptedCardNumber.Length);

    var client = httpClientFactory.CreateClient("BankClient");
    var pipeline = pipelineProvider.GetPipeline<HttpResponseMessage>("BankGatewayPipeline");

    try
    {
        // Eksekusi panggilan dengan Resilience Pipeline yang memantau token eksekusi
        var response = await pipeline.ExecuteAsync(async stateToken =>
        {
            var payload = new { OrderId = request.OrderId, Amount = request.Amount };
            return await client.PostAsJsonAsync("/status/200", payload, stateToken);
        }, cancellationToken);

        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "success"));
        transactionDurationHistogram.Record(stopwatch.ElapsedMilliseconds, new KeyValuePair<string, object>("status", "success"));

        activity?.SetStatus(ActivityStatusCode.Ok);
        return Results.Ok(new PaymentResponse(true, "Transaction approved", Guid.NewGuid().ToString()));
    }
    catch (BrokenCircuitException ex)
    {
        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "circuit_broken"));
        activity?.SetStatus(ActivityStatusCode.Error, "Downstream circuit open");
        activity?.RecordException(ex);

        return Results.StatusCode(StatusCodes.Status503ServiceUnavailable);
    }
    catch (Exception ex)
    {
        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "error"));
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        activity?.RecordException(ex);

        return Results.StatusCode(StatusCodes.Status500InternalServerError);
    }
});

app.Run();

// ==========================================
// 5. CONTRACTS
// ==========================================
public record PaymentRequest(string OrderId, decimal Amount, string CardNumber);
public record PaymentResponse(bool IsSuccess, string Message, string TransactionId);
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pola / Strategi | Keuntungan | Kerugian & Batasan | Best For / Anti-Pattern |
| :--- | :--- | :--- | :--- |
| **Polly v8 Pipeline vs Polly v7 Policies** | Zero-allocation pada path eksekusi utama, performa heap meningkat drastis, integrasi natif dengan generic abstractions .NET 8. | Pola penulisan berbeda secara fundamental; breaking changes dalam konfigurasi API legacy. | **Best For:** Aplikasi modern ber-throughput sangat tinggi.<br>**Anti-Pattern:** Melakukan migrasi massal kode warisan tanpa refactoring arsitektur. |
| **Exponential Backoff vs Constant Delay** | Mencegah resonansi beban downstream; memberikan adaptasi dinamis saat sistem down. | Waktu respon tail klien meningkat tajam; sulit memprediksi *worst-case latency* tanpa Total Timeout. | **Best For:** Panggilan jaringan inter-service asinkron.<br>**Anti-Pattern:** Operasi synchronous UI-facing yang membutuhkan respon sub-second deterministik. |
| **OpenTelemetry In-Process vs Sidecar Daemon (Collector)** | Konfigurasi direct-to-backend lebih ringkas, dependencies infrastruktur minimal. | Mengonsumsi resource CPU/Memory aplikasi utama; berpotensi kehilangan span/metrik jika aplikasi crash mendadak. | **Best For:** Lingkungan development atau arsitektur monolit kecil.<br>**Anti-Pattern:** Kubernetes cluster enterprise berskala ribuan node (sebaiknya gunakan Otel Collector sidecar/daemonset). |
| **DPAPI vs Cloud HSM (KMS)** | Sangat cepat, lokal in-memory execution, bebas latensi network hop kriptografi. | Kebutuhan konfigurasi sinkronisasi key-ring lintas node container; resiko kehilangan kunci jika storage epiferal hilang. | **Best For:** Enkripsi session payload, anti-CSRF, cookie, atau transit state.<br>**Anti-Pattern:** Penyimpanan master kunci regulasi kepatuhan PCI-DSS Tier 1 (gunakan HSM murni). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Tail Latency Amplification (Amplifikasi Latensi Buntut)
Jika rantai panggilan memiliki kedalaman $N=4$ mikroservis, dan masing-masing melakukan retry 3 kali dengan timeout 2 detik:
Dalam skenario kegagalan upstream paling ujung, latensi kumulatif terburuk dapat mencapai:
$$\text{Worst Case Latency} = 3 \times 3 \times 3 \times 2s = 54\text{ detik}$$
**Solusi:** Terapkan **Hedging Strategy** atau **Distributed Context Propagation** di mana `CancellationToken` membawa *Deadline* absolut dari gerbang gateway terluar (*Budget-based execution*).

### 2. DNS Caching via HttpClient vs SocketsHttpHandler
`HttpClient` instansiasi naif (`new HttpClient()`) mengabaikan perubahan rekaman DNS (TTL) karena mengunci soket TCP. Sebaliknya, pembuangan `HttpClient` secara instan pada setiap request memicu kehabisan port TCP (**Socket Exhaustion** dalam status `TIME_WAIT`).
**Solusi:** Gunakan `IHttpClientFactory` atau konfigurasikan `SocketsHttpHandler`:
```csharp
var handler = new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(2), // DNS refresh setiap 2 menit
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(1),
    MaxConnectionsPerServer = 200
};
var client = new HttpClient(handler);
```

### 3. Masking/Redacting Sensitive Tracing Data (Kebocoran PII di Logs/Spans)
Secara default, Activity tags dan OTel instrumentation dapat merekam *Query String* atau *Header* yang memuat informasi sensitif (misal: Authorization header, data kartu kredit, token JWT).
**Solusi:** Buat processor/enricher khusus untuk menyaring string:
```csharp
// Membersihkan URL sebelum dicatat ke Span
activity.SetTag("http.url", SanitizeUrl(context.Request.Path));
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengabaikan CancellationToken pada Pipeline Execution
```csharp
// SALAH: Token dari luar diabaikan di internal delegasi
await pipeline.ExecuteAsync(async ct => 
{
    return await httpClient.GetAsync("https://api.internal/data"); // ct tidak di-pass!
}, cancellationToken);

// BENAR: Forward token internal ke seluruh synchronous/asynchronous IO
await pipeline.ExecuteAsync(async stateToken => 
{
    return await httpClient.GetAsync("https://api.internal/data", stateToken);
}, cancellationToken);
```

### Kesalahan Fatal 2: Melakukan Retry pada Kasus Non-Idempotent (POST/PATCH)
Melakukan retry pada panggilan HTTP POST pembuatan pesanan atau pembayaran dapat menyebabkan penagihan ganda (*double charge*) jika kegagalan pertama sebenarnya terjadi pada saat transmisi *acknowledgement* (ACK) balik, bukan saat eksekusi hulu.
*Cara Menghindari:*
* Selalu sertakan header **Idempotency-Key** (misal: UUIDv4) pada setiap mutasi data.
* Pastikan server downstream memvalidasi idempotensi sebelum memproses eksekusi finansial.
* Konfigurasikan retry hanya pada idempotensi yang terjamin (GET, PUT teruji, atau POST dengan engine idempotency terverifikasi).

### Kesalahan Fatal 3: DPAPI Key Ring Terisolasi pada Ephemeral Container (Docker)
Ketika container di-restart di Kubernetes, default key DPAPI yang disimpan di `/root/.aspnet/DataProtection-Keys` musnah.
Akibatnya: Seluruh authentication cookie atau encrypted payload yang dibuat sebelum pod restart menjadi **tidak terbaca/rusak (CryptographicException: The payload was invalid)**.
*Cara Menghindari:* Selalu arahkan lokasi persistensi kunci ke shared resilient storage (Azure Blob Storage, Redis, atau AWS S3) yang dienkripsi dengan Master Key KMS.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### Enterprise Checklist (Production Readiness)
1. **Resilience Strategy Order:** Urutan pipeline Polly v8 **wajib** mengikuti hukum dari luar ke dalam:
   $$\text{Fallback} \to \text{Total Timeout} \to \text{Retry} \to \text{Circuit Breaker} \to \text{Attempt Timeout}$$
2. **Standardized Semantic Conventions:** Ikuti penamaan OpenTelemetry Semantic Conventions (misal: gunakan `http.request.method`, bukan `http.method` atau `Method`).
3. **Structured Logging Enrichment:** Jangan pernah melakukan interpolasi string pada logger:
   ```csharp
   // SALAH (Menghancurkan indexing & memicu alokasi string heap):
   logger.LogInformation($"Processing order {orderId} for customer {customerId}");

   // BENAR (Message template dengan semantic tokens):
   logger.LogInformation("Processing order {OrderId} for customer {CustomerId}", orderId, customerId);
   ```
4. **Graceful Degradation:** Selalu sediakan strategi *Fallback* jika Circuit Breaker terbuka (misal: mengambil data stale dari cache Redis lokal alih-alih mengembalikan HTTP 500 ke pengguna).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Zero-Allocation Polly Context
Dalam high-load system, objek `ResilienceContext` dapat di-*pool* untuk menghilangkan overhead GC.

```csharp
// Menggunakan ResilienceContextPool untuk zero-allocation context acquisition
var context = ResilienceContextPool.Shared.Get(
    operationKey: "ProcessPayment",
    cancellationToken: cancellationToken);

try
{
    // Gunakan context yang dipinjam dari object pool
    var outcome = await pipeline.ExecuteOutcomeAsync(static async (ctx, state) =>
    {
        var result = await state.client.GetStringAsync("/health", ctx.CancellationToken);
        return Outcome.FromResult(result);
    }, context, (client: httpClient, stateData: "extra"));
}
finally
{
    // Kembalikan context ke object pool
    ResilienceContextPool.Shared.Return(context);
}
```

### Memory Impact Comparison Table

| Pendekatan | Allocations / Op | CPU Overhead | Throughput Impact |
| :--- | :--- | :--- | :--- |
| Naive Try-Catch Loop | ~128 bytes | Sangat Rendah | Cepat, tapi tidak aman tanpa circuit breaker |
| Polly v7 Policy Wrap | ~1.4 KB | Menengah | Memicu GC Gen 0 pressure di atas 50K rps |
| Polly v8 Pipeline + Pooling | **0 bytes** (Amortized)| Rendah | Mendekati kecepatan bare-metal async execution |

---

## SEKSI 16 — KEAMANAN & HARDENING

### Defensive Architecture: SSRF Mitigation & Secure Secret Lifecycle
1. **Server-Side Request Forgery (SSRF) Hardening:**
   Jika URL downstream diambil berdasarkan input pengguna atau integrasi dinamis:
   * Batasi resolusi DNS ke skema `https://` saja.
   * Blokir segment IP Privat (RFC 1918) seperti `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, serta loopback `127.0.0.1` dan AWS metadata `169.254.169.254`.

```csharp
public static async Task ValidateDownstreamUriAsync(Uri targetUri)
{
    if (targetUri.Scheme != Uri.UriSchemeHttps)
        throw new SecurityException("Hanya protokol HTTPS terverifikasi yang diizinkan!");

    var hostEntry = await Dns.GetHostEntryAsync(targetUri.DnsSafeHost);
    foreach (var address in hostEntry.AddressList)
    {
        if (IPAddress.IsLoopback(address) || IsPrivateSubnet(address))
        {
            throw new SecurityException($"Akses ke segmen jaringan privat ditolak: {address}");
        }
    }
}

private static bool IsPrivateSubnet(IPAddress ip)
{
    var bytes = ip.GetAddressBytes();
    return ip.AddressFamily switch
    {
        System.Net.Sockets.AddressFamily.InterNetwork =>
            bytes[0] == 10 ||
            (bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31) ||
            (bytes[0] == 192 && bytes[1] == 168) ||
            (bytes[0] == 169 && bytes[1] == 254),
        _ => false
    };
}
```

2. **In-Memory Secret Sanitization:**
   Hindari menampung plaintext token, password, atau API key ke dalam objek immutable `string` karena string akan tertahan di Large Object Heap (LOH) atau Gen 2 tanpa dapat dihapus secara deterministik sampai proses Garbage Collection berjalan.
   Gunakan struktur `Memory<char>` atau array byte yang dapat di-overwrite via `Array.Clear(...)` atau manipulasi via pinned pointers dengan `CryptographicOperations.ZeroMemory(...)`.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Diagnostic Pipeline Troubleshooting Guide
Ketika distributed trace terputus atau metrik tidak tampil pada Grafana/Jaeger dashboard:

1. **Verifikasi Propagasi Header W3C:**
   Jalankan sniffer atau telusuri via handler debug:
   ```csharp
   public class TraceLogHandler : DelegatingHandler
   {
       protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
       {
           if (request.Headers.TryGetValues("traceparent", out var values))
           {
               Console.WriteLine($"[TRACE-DEBUG] Outgoing traceparent: {string.Join(",", values)}");
           }
           else
           {
               Console.WriteLine("[TRACE-DEBUG-WARN] Tidak ada W3C traceparent header yang dipropagasi!");
           }
           return await base.SendAsync(request, cancellationToken);
       }
   }
   ```
2. **Inspeksi Exception yang Direkam di OpenTelemetry:**
   Pastikan setiap catch-block yang menangani error juga memanggil:
   `activity?.RecordException(ex);`
   `activity?.SetStatus(ActivityStatusCode.Error, ex.Message);`
   Tanpa pemanggilan ini, trace span akan tetap berstatus `OK` (warna hijau) pada visualizer distributed trace, meskipun aplikasi sebenarnya menghasilkan response error 500 ke klien.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ENTERPRISE RESILIENCE & OBSERVABILITY CHEAT SHEET                            │
├──────────────────────────────────────┬───────────────────────────────────────┤
│ Pola Polly v8                        │ Aturan Konfigurasi Produksi           │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ Total Timeout                        │ 3x - 5x normal P99 latency SLA        │
│ Per-Attempt Timeout                  │ 1.2x - 1.5x downstream normal P99     │
│ Exponential Backoff                  │ Delay dasar: 200-500ms, WAJIB Jitter  │
│ Circuit Breaker                      │ MinThroughput >= 20, BreakDuration:15s│
│ Rate Limiter                         │ Token Bucket/Concurrency Limiter      │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ OpenTelemetry Tracing Standard       │ Standar Implementasi .NET             │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ Root Span Injection                  │ ActivitySource.StartActivity(...)     │
│ Metric Counter (Total events)        │ Meter.CreateCounter<long>(...)        │
│ Metric Histogram (Duration, size)    │ Meter.CreateHistogram<double>(...)    │
│ Context Propagation                  │ Otomatis via HttpClientInstrumentation│
├──────────────────────────────────────┼───────────────────────────────────────┤
│ Kriptografi & Data Protection        │ Aturan Keamanan                       │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ Key Persistence                      │ Shared Storage (Redis/Azure Blob/SQL) │
│ Key Rotation Interval                │ Maksimal 90 hari                      │
│ PII Encryption                       │ IDataProtector.Protect(plainText)     │
└──────────────────────────────────────┴───────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Mengapa implementasi Retry Strategy sederhana tanpa menyertakan "Jitter" berbahaya pada arsitektur microservices?**
   * *A.* Karena jitter mengurangi konsumsi CPU secara eksponensial.
   * *B.* Karena tanpa jitter, retry serentak dari banyak klien akan membebani downstream pada interval yang sama persis (Thundering Herd).
   * *C.* Karena jitter secara otomatis mengubah error 500 menjadi 200 OK.
   * *D.* Karena tanpa jitter, thread pool akan langsung mengalami unhandled crash.

2. **Format standar yang digunakan OpenTelemetry untuk mempropagasi konteks tracing antar layanan via HTTP Header adalah...**
   * *A.* B3 Propagation Specs saja.
   * *B.* W3C Trace Context (`traceparent`).
   * *C.* OpenTracing Raw Binary Tags.
   * *D.* Custom Bearer Token Metadata.

3. **Status apa yang dimiliki oleh Circuit Breaker ketika ia mengizinkan sejumlah kecil request sampel lewat untuk menguji pemulihan downstream?**
   * *A.* `Closed`
   * *B.* `Open`
   * *C.* `Half-Open`
   * *D.* `Isolating`

4. **Komponen BCL .NET mana yang bertindak sebagai ekuivalen asli dari "Span" OpenTelemetry?**
   * *A.* `System.Threading.Thread`
   * *B.* `System.Diagnostics.Activity`
   * *C.* `System.Diagnostics.TraceSource`
   * *D.* `System.Threading.Tasks.Task`

5. **Apa yang terjadi secara default jika ASP.NET Core Data Protection API tidak dikonfigurasi penyimpanan kuncinya secara eksternal dalam container Docker yang mengalami restart?**
   * *A.* Kunci otomatis disinkronkan ke kernel OS host.
   * *B.* Key-ring musnah, menyebabkan data terenkripsi sebelumnya tidak bisa didekripsi kembali.
   * *C.* Sistem secara default menolak start dan melempar `MissingKeyRingException`.
   * *D.* Data didekripsi otomatis menjadi format plaintext.

---

### Soal Tingkat Menengah (Intermediate)
6. **Perhatikan urutan pipeline Polly v8 berikut: Timeout Total -> Retry -> Circuit Breaker -> Timeout Per-Attempt. Apa yang terjadi jika urutan Circuit Breaker ditaruh di luar Retry?**
   * *A.* Pipeline tidak dapat di-compile.
   * *B.* Circuit breaker akan menghitung setiap percobaan retry internal sebagai kegagalan terpisah, sehingga sirkuit dapat trip prematur hanya dari satu request pengguna yang gagal berulang kali.
   * *C.* Retry tidak akan pernah tereksekusi ketika terjadi network timeout.
   * *D.* Circuit breaker akan berubah status menjadi permanen `Closed`.

7. **Bagaimana cara mencegah memory leak / gen-2 fragmentation saat membuat span kustom menggunakan `ActivitySource` pada throughput 100.000 request/detik?**
   * *A.* Menggunakan `GC.Collect()` setelah setiap aktivitas ditutup.
   * *B.* Memastikan tidak ada listener yang mendaftar ke `ActivitySource` jika tidak diamati, dan meminimalisir penambahan string dinamis tak berbatas pada `Activity.Tags`.
   * *C.* Membuat `new ActivitySource()` di dalam setiap scope request controller.
   * *D.* Mengubah semua parameter `Activity` menjadi synchronous struct thread-blocking.

8. **Manakah alasan teknis paling tepat mengapa kita tidak boleh melakukan retry pada HTTP POST endpoint tanpa menyertakan mekanisme Idempotency Key?**
   * *A.* Karena HTTP POST tidak didukung oleh framework Polly v8.
   * *B.* Karena jika request pertama berhasil diproses di server namun koneksi terputus saat mengirimkan respon, retry akan mengeksekusi mutasi/transaksi finansial untuk kedua kalinya.
   * *C.* Karena memory buffer HTTP POST stream otomatis disposed pada retry pertama.
   * *D.* Karena HTTP standard RFC 9110 secara ketat melarang retry pada semua jenis status code selain 200.

9. **Saat mengonfigurasi `SocketsHttpHandler` untuk aplikasi enterprise, parameter mana yang wajib diatur untuk mencegah stale DNS issues sekaligus menjaga TCP connection reuse?**
   * *A.* `EnableMultipleHttp2Connections = false`
   * *B.* `PooledConnectionLifetime` disetel ke interval terbatas (misal: 2-5 menit).
   * *C.* `ConnectTimeout = Timeout.InfiniteTimeSpan`
   * *D.* `MaxConnectionsPerServer = 1`

10. **Ketika circuit breaker pada Polly v8 berpindah ke status `Open`, exception spesifik apa yang dilempar secara instan ke pemanggil tanpa melakukan network IO?**
    * *A.* `TimeoutRejectedException`
    * *B.* `BrokenCircuitException`
    * *C.* `HttpRequestException`
    * *D.* `TaskCanceledException`

---

### Kunci Jawaban & Rasional Singkat
1. **B** — Jitter merandomisasi waktu tunggu untuk mencegah sinkronisasi pemanggilan ulang (*Thundering Herd*).
2. **B** — Standar W3C Trace Context mendefinisikan header `traceparent` dan `tracestate`.
3. **C** — Fase `Half-Open` adalah kondisi uji coba (canary check) untuk memvalidasi kesehatan upstream.
4. **B** — `System.Diagnostics.Activity` adalah model native BCL untuk OpenTelemetry Span.
5. **B** — DataProtection menyimpan kunci di ephemeral storage `/root/.aspnet` jika tidak diikat ke persistent volume/external store.
6. **B** — Menempatkan Circuit Breaker di luar Retry menyebabkan amplifikasi metrik kegagalan karena setiap looping retry internal membebani sampling breaker.
7. **B** — `ActivitySource` memiliki optimasi bypass instan jika tidak ada listener (`activitySource.HasListeners()`), dan penambahan unbounded dynamic tags memicu fragmentasi string table.
8. **B** — POST secara default adalah non-idempotent; hilangnya ACK jaringan berpotensi memicu duplicate execution jika di-retry secara buta.
9. **B** — `PooledConnectionLifetime` memastikan koneksi lama ditutup secara elegan dan koneksi baru membuka resolusi alamat DNS yang telah diperbarui.
10. **B** — Polly v8 melempar `BrokenCircuitException` saat sirkuit berada pada status `Open`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Resilient & Auditable Stock Brokerage Gateway"

#### Deskripsi Spesifikasi Tugas:
Anda diminta membangun API Gateway mini untuk platform saham terdistribusi menggunakan .NET 8/9. Gateway ini harus meneruskan order beli saham ke layanan *Market Mock Engine* yang sengaja dibuat tidak stabil (sering melempar error 500, latensi tinggi, dan putus koneksi acak).

#### Kriteria Keberhasilan (Acceptance Criteria):
1. **Resilience Pipeline Requirements:**
   * Bangun pipeline bernama `"StockOrderPipeline"` menggunakan `Microsoft.Extensions.Resilience`.
   * **Total Timeout:** 8 detik.
   * **Retry:** Maksimum 3 percobaan, *Decorrelated Jitter*, interval awal 250ms, hanya berlaku untuk HTTP 5xx dan network timeout.
   * **Circuit Breaker:** Membuka sirkuit jika persentase error $\ge 50\%$ dari minimal 8 transaksi dalam sampling 15 detik. *Break Duration* disetel ke 10 detik.
   * **Per-Attempt Timeout:** Maksimum 2 detik per percobaan IO.
2. **Observability Requirements:**
   * Instrumentasikan endpoint pemesanan saham menggunakan `ActivitySource("Brokerage.Gateway")`.
   * Buat metrik kustom:
     * `Meter("Brokerage.Gateway")`
     * Counter: `stock.orders.attempted`
     * Counter: `stock.orders.failed`
     * Histogram: `stock.orders.execution_time` (merekam latensi total per transaksi).
   * Sematkan tag pada span: `stock.symbol`, `stock.volume`, dan `stock.order_type`.
3. **Security & Cryptography Requirements:**
   * Sebelum mengirim data ke mock engine, nomor rekening investor (`InvestorAccountNumber`) harus dienkripsi menggunakan `IDataProtector` dengan purpose `"Brokerage.Investor.Data.v1"`.
   * Implementasikan validasi idempotensi sederhana: Endpoint menerima header `X-Idempotency-Key`. Jika key yang sama dikirim dalam kurun waktu 5 menit dengan order yang sukses, kembalikan data cache transaksi yang sama tanpa menembak backend engine kembali.

#### Validasi Pengujian:
* Simulasikan 50 request paralel dengan 30% tingkat kegagalan di backend menggunakan tools seperti *k6* atau skrip async C#.
* Pastikan log menampilkan status transisi Circuit Breaker (`Closed` -> `Open` -> `Half-Open` -> `Closed`).
* Buktikan melalui export tracing bahwa trace parent ID dipropagasi secara sukses ke backend downstream.