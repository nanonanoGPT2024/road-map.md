# KURIKULUM TEKNIS ENTERPRISE: ASP.NET CORE (.NET 8/9)
## Topik: 02-Programming-Languages / aspnet-core
## Bab 10: Enterprise Architecture & Cloud-Native Deployment
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur runtime ASP.NET Core untuk lingkungan *cloud-native* berkinerja tinggi (Kubernetes) dengan ketersediaan tinggi (*high availability*) dan toleransi kesalahan (*fault-tolerance*).
- **Menguasai siklus hidup aplikasi (*application lifecycle*) dan graceful shutdown**, memitigasi kegagalan transmisi TCP *in-flight requests* selama proses *rolling update* orkestrasi kontainer.
- **Mengonfigurasi observabilitas terdistribusi (*distributed observability*) enterprise** menggunakan standar OpenTelemetry (Traces, Metrics, Logs) yang diekspor via protokol OTLP berkinerja tinggi.
- **Mengimplementasikan strategi ketahanan (*resilience pipeline*) generasi baru** dengan Polly v8 (`Microsoft.Extensions.Resilience`), mencakup Circuit Breaker, Rate Limiting, Hedging, dan Timeout terdistribusi.
- **Membangun kontainer OCI (*Open Container Initiative*) teroptimasi** menggunakan teknik *multi-stage build* berbasis Ubuntu Chiseled/Distroless dengan prinsip *least privilege* (non-root UID) dan footprint memori minimal.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib memahami:
- Sintaksis C# 12/13 dan platform .NET 8/9 SDK.
- Konsep internal ASP.NET Core Generic Host, Dependency Injection (DI) Service Lifetimes, dan Kestrel Web Server.
- Fondasi arsitektur kontainer OCI (Docker Engine/Containerd) dan primitif orkestrasi Kubernetes (*Pod, Deployment, Service, ConfigMap, Secrets*).
- Protokol jaringan layer 4 hingga layer 7 (TCP/IP, HTTP/1.1, HTTP/2, gRPC).
- Paradigma pemrograman asinkron berbasis `Task`, `ValueTask`, dan `CancellationToken`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. ASP.NET Core Generic Host Runtime & Kestrel Connection Draining
Dalam lingkungan Kubernetes, *termination lifecycle* sebuah Pod tidak terjadi seketika (*instantaneous*). Ketika Pod ditandai untuk dihapus (`Terminating`), dua proses paralel terjadi:
1. Kubernetes Control Plane menghapus Pod dari daftar *Endpoints* Service (propagasi IP ke *kube-proxy* dan *Ingress Controller* membutuhkan latensi beberapa detik).
2. `kubelet` mengirimkan sinyal `SIGTERM` ke *process entrypoint* kontainer (PID 1).

Secara internal, `Microsoft.Extensions.Hosting.Internal.Host` menangani `SIGTERM` dengan memicu `IHostApplicationLifetime.ApplicationStopping`. Kestrel menerima sinyal ini dan mengeksekusi urutan berikut:
- **Stop Accepting New Connections:** Kestrel menutup port *listening* soket TCP.
- **Connection Draining:** Kestrel memberikan tenggat waktu (*grace period*) kepada koneksi TCP aktif untuk menyelesaikan siklus *Request/Response*.
- **Timeout Fallback:** Jika `HostOptions.ShutdownTimeout` tercapai sebelum semua koneksi selesai, Kestrel secara agresif memutuskan koneksi soket via `RST` packets, yang memicu lonjakan status *HTTP 502/503 Bad Gateway* pada klien jika tidak dikonfigurasi secara sinkron dengan Kubernetes `preStop` hook.

```
[kubelet: SIGTERM] ────────┐
                           │ (Parallel Async Operations)
[Endpoints Controller]     ▼
   │ Remove Pod IP  ┌──────────────────────────────────────────────┐
   │ from Endpoints │ Kestrel receives SIGTERM                     │
   ▼                │ 1. ApplicationStopping triggered             │
[Ingress Propagated]│ 2. Stop listening on 0.0.0.0:8080            │
 (Takes 2-5 secs)   │ 3. Drain in-flight requests (Timeout clock)  │
   │                └──────────────────────────────────────────────┘
   │                               │
   ▼                               ▼
Traffic Stops Routing       Pod Exits (Graceful or Hard Kill SIGKILL)
```

#### B. OpenTelemetry (OTel) Semantic Conventions & Trace Propagation
Observabilitas modern ASP.NET Core meninggalkan mekanisme logging berbasis string monolitik dan beralih ke struktur instrumen OpenTelemetry standar W3C `traceparent` (`00-{trace-id}-{parent-id}-{trace-flags}`).
- **`Activity` & `ActivitySource`:** Komponen internal runtime BCL (`System.Diagnostics`) yang merepresentasikan abstraksi *Span* OpenTelemetry tanpa ketergantungan paket eksternal.
- **Trace Propagation:** Middleware ASP.NET Core membaca header HTTP `traceparent` saat *inbound request*, menginisialisasi root/child `Activity`, dan secara otomatis menyuntikkannya ke `AsyncLocal<Activity>` runtime thread context. Setiap *outbound request* via `HttpClient` (yang diinstrumentasi oleh `IHttpClientFactory`) secara otomatis mengekstrak `Activity.Current` dan menyuntikkan header W3C yang sesuai ke *downstream microservice*.
- **OTLP Batch Processing:** Span dan Metrik tidak dikirim secara sinkron via I/O network request karena dapat menghancurkan *throughput* aplikasi. Runtime mengakumulasi telemetri dalam *circular memory buffer* (`BatchActivityExportProcessor`) dan mengirimkannya secara asinkron dalam format Protobuf via HTTP/2 atau gRPC ke OTel Collector.

#### C. Polly v8: The Resilience Pipeline Architecture
Polly v8 merevolusi penanganan ketahanan sistem dengan membuang pola alokasi memori objek berat dari versi terdahulu.
- **Zero-Allocation Pipeline:** Menghilangkan `ISyncPolicy` dan `IAsyncPolicy` berbasis delegasi closure bertingkat. Menggantinya dengan struct/instance stateless `ResiliencePipeline` yang dieksekusi di atas `ResilienceContext`.
- **Eksekusi Komposit:** Berbagai strategi (*Rate Limiter, Total Timeout, Retry, Circuit Breaker, Attempt Timeout*) digabungkan dalam satu *pipeline invocation chain*. Setiap strategi beroperasi seperti middleware internal Kestrel, meminimalkan *thread context switching* dan alokasi heap saat *high-concurrency path*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy .NET) | Pendekatan Cloud-Native Modern (.NET 8/9) |
| :--- | :--- | :--- |
| **Container Base** | Image berbasis Full OS (`mcr.microsoft.com/dotnet/aspnet:8.0`) dengan shell `bash/sh` dan tool root (400MB+). | Ubuntu Chiseled / Distroless runtime image (<100MB), zero OS vulnerabilities (CVE), tanpa shell, non-root user. |
| **Telemetry** | Logging berbasis Text File / EventLog / Proprietary APM SDK (NewRelic, Datadog agent vendor-locked). | OpenTelemetry Vendor-Agnostic, Semantic Conventions, zero-allocation via `System.Diagnostics.Metrics` & `ActivitySource`. |
| **Resilience** | Blok `try-catch` manual dengan retry loop primitif atau Polly v7 yang memicu alokasi memori masif. | Polly v8 `ResiliencePipelineBuilder` terintegrasi native dengan `IHttpClientFactory` dan DI container. |
| **App Lifecycle** | Mematikan proses langsung saat `SIGTERM`, mengabaikan request yang sedang berjalan (*abrupt abortion*). | Koordinasi terencana antara Kubernetes `preStop` sleep hook, Kestrel connection draining, dan cancellation tokens. |
| **Health Checks** | Endpoint monolitik tunggal `/health` yang memeriksa database, message broker, dan memori sekaligus. | Pemisahan tegas: Startup Probe (`/healthz/startup`), Liveness Probe (`/healthz/liveness`), dan Readiness Probe (`/healthz/readiness`). |

---

### 5. How (Workflow Detail)

Alur penanganan siklus hidup aplikasi di klaster orkestrasi pod (Kubernetes):

1. **Inisialisasi Pod:**
   - Kubelet meluncurkan Pod.
   - Kestrel mengikat (*bind*) port kontainer (contoh: 8080).
   - Kubernetes mengeksekusi **Startup Probe**. Selama probe ini belum sukses, Liveness dan Readiness probe dinonaktifkan.
   - Startup Probe sukses -> Pod beralih ke monitoring rutin via Liveness & Readiness Probe.

2. **Fase Operasional:**
   - **Readiness Probe** memverifikasi dependensi krusial (konektivitas database, kesiapan cache). Jika bernilai `Healthy`, lalu lintas (*traffic*) dialirkan oleh Service Ingress ke Pod.
   - **Liveness Probe** memverifikasi bahwa *event loop* runtime .NET tidak mengalami *deadlock* fatal. Jangan pernah mengecek dependensi eksternal di probe ini.

3. **Fase Terminasi & Graceful Draining:**
   - Node di-drain atau deployment di-update. Pod masuk status `Terminating`.
   - **Eksekusi `preStop` Hook:** Pod menjalankan delay terkonfigurasi (misal: `sleep 15`). Ini memberi waktu bagi Ingress Controller untuk memperbarui *routing table* dan membuang IP Pod dari jaringan aktif.
   - **Sinyal `SIGTERM` Dikirim:** Setelah `preStop` selesai, `kubelet` mengirim `SIGTERM`.
   - **Host Shutdown Triggered:** ASP.NET Core membatalkan `IHostApplicationLifetime.ApplicationStopping`.
   - **Kestrel Draining:** Kestrel menolak koneksi TCP baru, namun tetap menyelesaikan koneksi yang sedang diproses hingga batas waktu `ShutdownTimeout`.
   - **Resource Disposal:** Container berhenti secara elegan sebelum `terminationGracePeriodSeconds` Kubernetes terlewati.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Stasiun Pengisian Kereta Cepat
Bayangkan sebuah stasiun kereta api modern:
- **Startup Probe:** Inspeksi kelayakan rel dan sinyal sebelum stasiun dibuka untuk umum.
- **Readiness Probe:** Pintu masuk boarding gate. Jika jalur penuh, gate ditutup sementara, tetapi stasiun tidak dibongkar. Kereta yang sudah ada tetap jalan.
- **Liveness Probe:** Monitor detak jantung petugas pengatur lalu lintas. Jika pingsan (*deadlock*), tim medis darurat langsung menggantinya (*pod restart*).
- **Graceful Shutdown (`preStop` + `SIGTERM`):** Pengumuman bahwa stasiun akan tutup dalam 15 menit. Pintu luar dikunci (*remove from endpoints*), penumpang di dalam peron diantar ke kereta mereka sampai tuntas (*Kestrel drain*), lalu lampu dimatikan total.

#### Arsitektur Orkestrasi & Telemetri Pod
```
                             KUBERNETES NODE ARCHITECTURE
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                                                                             │
  │   Kubelet                     INGRESS CONTROLLER (NGINX / Envoy)            │
  │      │                                       │                              │
  │      │ Health Checks                         │ Inbound Requests             │
  │      │ (HTTP Probes)                         │ (W3C traceparent injected)   │
  │      ▼                                       ▼                              │
  │  ┌───────────────────────────────────────────────────────────────────────┐  │
  │  │ POD: ASP.NET Core Container (Chiseled Distroless - Non-Root UID:1654)  │  │
  │  │                                                                       │  │
  │  │   ┌────────────────────────────────────────────────────────────────┐  │  │
  │  │   │ Kestrel HTTP Engine (:8080)                                    │  │  │
  │  │   │  ├─ Middleware Pipeline                                        │  │  │
  │  │   │  │   ├─ HealthCheck Middleware (/healthz/*)                    │  │  │
  │  │   │  │   ├─ OpenTelemetry Tracing / Metrics Collector Middleware   │  │  │
  │  │   │  │   └─ Business Logic Handlers (Minimal APIs)                │  │  │
  │  │   │  │        │                                                    │  │  │
  │  │   │  │        ▼                                                    │  │  │
  │  │   │  │   Polly v8 Resilience Pipeline                              │  │  │
  │  │   │  │    [Timeout] -> [RateLimiter] -> [CircuitBreaker] -> [Retry]│  │  │
  │  │   │  │        │                                                    │  │  │
  │  │   │  │        ▼ (Resilient Outbound Call via HttpClient)          │  │  │
  │  │   │  │   External Gateway / Microservice                           │  │  │
  │  │   │  └─────────────────────────────────────────────────────────────┘  │  │
  │  │   │                                                                   │  │
  │  │   │ Runtime Internals:                                                │  │
  │  │   │  ├─ ActivitySource ("Enterprise.OrderApi")                        │  │  │
  │  │   │  ├─ Meter ("Enterprise.OrderApi.Metrics")                         │  │  │
  │  │   │  └─ Batch Telemetry Exporter (Thread Background)                  │  │  │
  │  │   └───────────────────────────────────┬───────────────────────────────┘  │
  │  └───────────────────────────────────────┼──────────────────────────────────┘
  │                                          │ OTLP Protocol (gRPC :4317)
  │                                          ▼
  │                     ┌────────────────────────────────────────┐
  │                     │ OpenTelemetry Collector DaemonSet      │
  │                     │ (Routes to Jaeger, Prometheus, Grafana)│
  │                     └────────────────────────────────────────┘
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### A. Simple Example: Konfigurasi Isolasi Probes Native ASP.NET Core
File: `Program.cs`
```csharp
var builder = WebApplication.CreateBuilder(args);

// Mendaftarkan Health Checks dengan Tag Terisolasi
builder.Services.AddHealthChecks()
    .AddCheck("self", () => Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy(), tags: ["live"])
    .AddCheck("database", () => 
    {
        // Simulasi pemeriksaan DB singkat
        bool dbConnected = true; 
        return dbConnected 
            ? Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy("Database link OK")
            : Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Unhealthy("Database unavailable");
    }, tags: ["ready"]);

var app = builder.Build();

// Liveness Probe: Hanya memvalidasi proses internal (.NET Host tidak crash)
app.MapHealthChecks("/healthz/liveness", new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("live")
});

// Readiness Probe: Memvalidasi ketersediaan dependensi downstream
app.MapHealthChecks("/healthz/readiness", new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready")
});

app.Run();
```

#### B. Practical Enterprise Example: Production-Ready Program.cs
Implementasi komprehensif ASP.NET Core 8/9 yang mengintegrasikan OpenTelemetry, Polly v8 Resilience Pipeline, Kestrel Hardening, dan Graceful Lifetimes.

```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Net;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Http.Resilience;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Polly;

var builder = WebApplication.CreateBuilder(args);

// 1. Kestrel Server Hardening
builder.WebHost.ConfigureKestrel(options =>
{
    options.AddServerHeader = false; // Keamanan: Samarkan header server
    options.Limits.MaxRequestBodySize = 10 * 1024 * 1024; // 10MB
    options.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(2);
    options.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(30);
});

// 2. Lifecycle & Graceful Shutdown Settings
builder.Services.Configure<HostOptions>(options =>
{
    // Berikan Kestrel waktu 30 detik untuk menguras TCP requests aktif
    options.ShutdownTimeout = TimeSpan.FromSeconds(30);
});

// 3. Telemetry Instrumentation Definitions
const string serviceName = "PaymentProcessing.Gateway";
const string serviceVersion = "1.0.0";
var appActivitySource = new ActivitySource(serviceName, serviceVersion);
var appMeter = new Meter(serviceName, serviceVersion);
var transactionCounter = appMeter.CreateCounter<long>("transactions.processed.count");

// 4. OpenTelemetry Core Setup
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(
        serviceName: serviceName,
        serviceVersion: serviceVersion,
        serviceInstanceId: Environment.MachineName))
    .WithTracing(tracing =>
    {
        tracing
            .AddSource(serviceName)
            .AddAspNetCoreInstrumentation(opts =>
            {
                opts.RecordException = true;
                opts.Filter = httpContext => !httpContext.Request.Path.StartsWithSegments("/healthz");
            })
            .AddHttpClientInstrumentation(opts => opts.RecordException = true)
            .AddOtlpExporter(otlp =>
            {
                otlp.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317");
            });
    })
    .WithMetrics(metrics =>
    {
        metrics
            .AddMeter(serviceName)
            .AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddRuntimeInstrumentation()
            .AddOtlpExporter(otlp =>
            {
                otlp.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317");
            });
    });

// 5. Polly v8 Resilient Http Client Configuration
builder.Services.AddHttpClient("DownstreamBankClient", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["DownstreamBank:BaseUrl"] ?? "https://api.bank-mock.internal");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
})
.AddResilienceHandler("BankGatewayPipeline", pipelineBuilder =>
{
    // Resilience strategy execution order: Outermost to Innermost
    
    // Total Request Timeout
    pipelineBuilder.AddTimeout(TimeSpan.FromSeconds(10));

    // Retry Strategy with Jitter
    pipelineBuilder.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true,
        Delay = TimeSpan.FromMilliseconds(200),
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .HandleResult(r => r.StatusCode == HttpStatusCode.RequestTimeout || 
                               r.StatusCode == HttpStatusCode.ServiceUnavailable ||
                               r.StatusCode == HttpStatusCode.GatewayTimeout)
    });

    // Circuit Breaker Strategy
    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        FailureRatio = 0.5, // Trip jika 50% request gagal
        SamplingDuration = TimeSpan.FromSeconds(30),
        MinimumThroughput = 20,
        BreakDuration = TimeSpan.FromSeconds(15),
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .HandleResult(r => (int)r.StatusCode >= 500)
    });

    // Individual Attempt Timeout
    pipelineBuilder.AddTimeout(TimeSpan.FromSeconds(2));
});

// 6. Enterprise Health Checks Configuration
builder.Services.AddHealthChecks()
    .AddCheck("process_liveness", () => HealthCheckResult.Healthy(), tags: ["live"])
    .AddAsyncCheck("downstream_bank_check", async cancellationToken =>
    {
        // Pemeriksaan konektivitas ringan dengan cancel token eksplisit
        try
        {
            // Simulasi probe network
            await Task.Delay(50, cancellationToken);
            return HealthCheckResult.Healthy("Downstream ping acceptable.");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy("Downstream dependency unreachable.", ex);
        }
    }, tags: ["ready"]);

var app = builder.Build();

// 7. Route Mapping & Probes Configuration
app.MapHealthChecks("/healthz/live", new HealthCheckOptions
{
    Predicate = r => r.Tags.Contains("live"),
    ResponseWriter = async (context, report) =>
    {
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsync($"{{\"status\":\"{report.Status}\"}}");
    }
});

app.MapHealthChecks("/healthz/ready", new HealthCheckOptions
{
    Predicate = r => r.Tags.Contains("ready"),
    ResponseWriter = async (context, report) =>
    {
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsync($"{{\"status\":\"{report.Status}\",\"duration\":\"{report.TotalDuration}\"}}");
    }
});

// 8. Business Endpoints with Explicit Trace Context
app.MapPost("/api/v1/process-payment", async (IHttpClientFactory clientFactory, CancellationToken ct) =>
{
    using var activity = appActivitySource.StartActivity("ProcessPaymentTransaction");
    activity?.SetTag("payment.type", "credit_card");

    try
    {
        var client = clientFactory.CreateClient("DownstreamBankClient");
        
        // Operasi HTTP terproteksi Polly Resilience Pipeline
        var response = await client.GetAsync("/health", ct);
        
        if (!response.IsSuccessStatusCode)
        {
            activity?.SetStatus(ActivityStatusCode.Error, "Bank refused transaction");
            return Results.StatusCode((int)HttpStatusCode.BadGateway);
        }

        transactionCounter.Add(1, new KeyValuePair<string, object?>("status", "success"));
        activity?.SetStatus(ActivityStatusCode.Ok);
        
        return Results.Ok(new { TraceId = Activity.Current?.TraceId.ToString(), Status = "Processed" });
    }
    catch (Exception ex)
    {
        activity?.RecordException(ex);
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        transactionCounter.Add(1, new KeyValuePair<string, object?>("status", "failed"));
        return Results.StatusCode(StatusCodes.Status500InternalServerError);
    }
});

app.Run();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Gateway Pembayaran FinTech (25,000 TPS)
- **Kondisi Awal:** Perusahaan FinTech memproses rata-rata 25.000 transaksi pembayaran per detik pada jam sibuk. Saat dilakukan deployment versi baru via Kubernetes Rolling Update, terjadi lonjakan *drop transaction* hingga 1.8% yang memicu alert kepatuhan PCI-DSS dan kerugian finansial langsung.
- **Analisis Akar Masalah (Root Cause Analysis):**
  1. *Connection Abrupt Termination:* Kontainer menerima `SIGTERM` dan langsung menghentikan proses aplikasi ASP.NET Core sebelum Ingress Controller sempat menghapus IP Pod dari routing table. Klien menerima error *TCP Connection Reset by Peer* (`ECONNRESET`).
  2. *Liveness Probe Cascade Failure:* Liveness probe dikonfigurasi untuk mengeksekusi kueri `SELECT 1` ke database utama PostgreSQL. Ketika koneksi database mengalami peningkatan latensi mendadak, liveness probe gagal serentak di 40 Pod. Akibatnya, Kubernetes me-restart seluruh Pod secara bersamaan (*cascading restart storm*), melumpuhkan seluruh klaster.
  3. *Socket Exhaustion:* Klien internal downstream membuat instansiasi `new HttpClient()` ad-hoc tanpa connection pooling yang tepat, menyebabkan ribuan soket menggantung dalam status `TIME_WAIT`.

- **Solusi Arsitektural Terapan:**
  1. **Deployment Lifecycle Synchronization:**
     Menambahkan `preStop` hook dengan delay 15 detik pada manifest Pod, dan menaikkan `HostOptions.ShutdownTimeout` menjadi 35 detik.
  2. **Refactoring Health Check Primitives:**
     Memisahkan Liveness Probe ke alokasi in-memory (`HealthCheckResult.Healthy()`) tanpa I/O network, dan membatasi Readiness Probe hanya memeriksa kesiapan buffer local connection pool.
  3. **Adopsi Polly v8 & IHttpClientFactory Pooling:**
     Memasang pipeline Circuit Breaker dengan failure rate 50% dan time-window sliding, dikombinasikan dengan exponential backoff retry ber-jitter untuk memecah efek stampede ke server bank upstream.
- **Hasil:** Error rate saat rolling update terpangkas menjadi 0.0000% (zero HTTP 5xx errors across 100+ deployments/month) dan latensi p99 terjaga stabil di bawah 45ms.

---

### 9. Trade-offs

| Pilihan Arsitektural | Keuntungan (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Mitigasi Enterprise |
| :--- | :--- | :--- | :--- |
| **OTel Full Instrumentation (100% Trace Sampling)** | Visibilitas sistem mutlak; setiap error dan outlier latensi tertangkap secara presisi. | Beban komputasi CPU meningkat, overhead jaringan masif, dan lonjakan biaya storage telemetry backend. | Terapkan *Parent-based Probabilistic Sampling* (misal: capture 5-10% dari incoming requests, namun 100% dari requests yang menghasilkan HTTP 5xx). |
| **Polly Hedging Strategy** | Mengurangi tail latency (p99/p99.9) secara radikal dengan mengirim request duplikat secara paralel jika request pertama lambat. | Menggandakan beban throughput pada downstream services; berpotensi menyebabkan duplikasi transaksi non-idempoten. | HANYA gunakan hedging pada operasi read-only (Idempotent GET), dan kombinasikan dengan strict Concurrency Limiter. |
| **Ubuntu Chiseled / Distroless Containers** | Ukuran image minimal (~60MB), attack surface minimal (tanpa `apt`, `sh`, atau `curl`), lolos audit keamanan ketat. | Sulit melakukan live-debugging atau troubleshooting jaringan langsung di dalam pod (`kubectl exec` tidak dapat membuka shell). | Gunakan Kubernetes *Ephemeral Debug Containers* (`kubectl debug`) yang me-mount tooling pod temporer ke namespace target. |
| **Panjang Durasi PreStop Sleep Hook** | Mengeliminasi HTTP 502/TCP Reset selama proses rotasi pod di Kubernetes. | Memperlambat kecepatan deployment pipeline CI/CD dan auto-scaling termination pod. | Kalibrasi secara empiris durasi sinkronisasi Ingress Controller (biasanya 5-15 detik cukup aman). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Anti-Pattern: Melakukan Network I/O pada Liveness Probe
- **Kesalahan Fatal:** Menguji database, Redis, atau HTTP eksternal di dalam endpoint yang ditargetkan oleh Kubernetes Liveness Probe.
- **Dampak:** Jika database downstream mengalami lonjakan beban atau down sejenak, Liveness Probe akan timeout. Kubernetes menganggap kontainer ASP.NET Core mati (*deadlocked*) dan me-restart Pod. Restart massal ini memperparah beban database saat koneksi baru diinisialisasi kembali secara serentak.
- **Troubleshooting & Koreksi:**
  Gunakan Liveness Probe **hanya** untuk mengecek apakah proses aplikasi masih bernafas. Dependensi downstream adalah domain milik Readiness Probe.
  ```csharp
  // BENAR: Liveness hanya memeriksa kesiapan thread pool & process memory
  app.MapHealthChecks("/healthz/liveness", new HealthCheckOptions { Predicate = r => r.Tags.Contains("live") });
  ```

#### 2. Kestrel Thread Pool Starvation Akibat Sync-over-Async
- **Gejala:** Latensi melonjak tajam secara eksponensial di bawah beban tinggi; CPU usage terlihat rendah tetapi throughput Kestrel anjlok drastis.
- **Investigasi:** Jalankan `dotnet-counters monitor -p <PID> System.Runtime`. Jika metrik `ThreadPool Completed Work Item Count` tertinggal jauh dibanding `ThreadPool Queue Length`, thread starvation sedang terjadi.
- **Penyebab:** Penggunaan `.Result`, `.Wait()`, atau `.GetAwaiter().GetResult()` pada Task I/O.
- **Koreksi:** Audit seluruh codebase secara strict, gunakan analyzer `Microsoft.VisualStudio.Threading.Analyzers`, dan pastikan semua I/O path bersifat murni `async/await` hingga ke tingkat root controller/minimal API handler.

#### 3. Kehilangan Traces pada OTLP Background Exporter saat Pod Termination
- **Gejala:** Data tracing transaksi-transaksi terakhir sebelum Pod dimatikan tidak pernah muncul di Jaeger / Grafana Tempo.
- **Penyebab:** Proses aplikasi dihentikan sebelum OTel `BatchActivityExportProcessor` sempat melakukan *flush* buffer ke OTel Collector.
- **Koreksi:** Pastikan generic host lifecycle mengizinkan disposal provider secara bersih.
  ```csharp
  // Program.cs
  var app = builder.Build();
  // ... configuration ...
  
  // Pastikan tracer provider di-flush secara eksplisit saat aplikasi berhenti
  var lifetime = app.Services.GetRequiredService<IHostApplicationLifetime>();
  lifetime.ApplicationStopping.Register(() =>
  {
      var tracerProvider = app.Services.GetService<TracerProvider>();
      tracerProvider?.ForceFlush(timeoutMilliseconds: 5000);
  });
  ```

---

### 11. Best Practices (Production Checklist)

#### Keamanan Kontainer (Container Hardening)
- [ ] Image kontainer menggunakan Base OS Chiseled/Distroless (`mcr.microsoft.com/dotnet/nightly/runtime-deps:8.0-chiseled-composite` atau versi rilis non-root).
- [ ] Kontainer berjalan menggunakan non-root user (UID default .NET 8/9 adalah `1654`).
- [ ] Root file system dikonfigurasi `readOnlyRootFilesystem: true` pada SecurityContext Kubernetes Pod; gunakan `emptyDir` mount untuk direktori temporer `/tmp`.

#### Konfigurasi Runtime Kestrel & Lifecycle
- [ ] Header HTTP `Server: Kestrel` dinonaktifkan (`AddServerHeader = false`).
- [ ] `HostOptions.ShutdownTimeout` disetel sinkron dengan waktu terminating pod (minimal 30 detik).
- [ ] Manifest Kubernetes mengimplementasikan `lifecycle.preStop.exec` dengan perintah sleep sebelum mengirim `SIGTERM`.

#### Ketahanan Jaringan (Resilience)
- [ ] Semua instansiasi `HttpClient` didaftarkan via `IHttpClientFactory` dengan Polly v8 Resilience Pipeline.
- [ ] Retry Policy selalu menerapkan algoritma *Decorrelated Jitter* untuk mencegah *Thundering Herd Problem*.
- [ ] Circuit Breaker diisolasi per hostname / downstream dependency.
- [ ] Cancellation Token dioperasikan di seluruh lapisan call-stack dari HTTP Handler hingga database access layer.

#### Observabilitas & Telemetri
- [ ] Format context propagation menggunakan standar W3C `traceparent`.
- [ ] OpenTelemetry diatur untuk mengecualikan (filter out) endpoint `/healthz/*` agar tidak mencemari telemetry backend.
- [ ] Logging terstruktur (*structured logging*) dengan parameter template (bukan string interpolation) untuk mempertahankan atribut semantic metadata.

---

### 12. Hands-on Practice

Buat dan simpan seluruh berkas berikut di direktori target: `hands-on/m02/`

#### File 1: `hands-on/m02/ProductionService.csproj`
```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <InvariantGlobalization>true</InvariantGlobalization>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Http.Resilience" Version="8.10.0" />
    <PackageReference Include="OpenTelemetry.Exporter.OpenTelemetryProtocol" Version="1.9.0" />
    <PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.9.0" />
    <PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.9.0" />
    <PackageReference Include="OpenTelemetry.Instrumentation.Http" Version="1.9.0" />
    <PackageReference Include="OpenTelemetry.Instrumentation.Runtime" Version="1.9.0" />
  </ItemGroup>

</Project>
```

#### File 2: `hands-on/m02/Program.cs`
```csharp
using System.Diagnostics;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Http.Resilience;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Polly;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.AddServerHeader = false;
});

builder.Services.Configure<HostOptions>(options =>
{
    options.ShutdownTimeout = TimeSpan.FromSeconds(30);
});

const string ServiceName = "OrderProcessingEngine";
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService(ServiceName))
    .WithTracing(tracing =>
    {
        tracing
            .AddAspNetCoreInstrumentation(opts =>
            {
                opts.Filter = ctx => !ctx.Request.Path.StartsWithSegments("/healthz");
            })
            .AddHttpClientInstrumentation()
            .AddOtlpExporter();
    })
    .WithMetrics(metrics =>
    {
        metrics
            .AddAspNetCoreInstrumentation()
            .AddRuntimeInstrumentation()
            .AddOtlpExporter();
    });

builder.Services.AddHttpClient("InventoryService", client =>
{
    client.BaseAddress = new Uri("http://localhost:5050");
})
.AddResilienceHandler("DefaultStrategy", pipeline =>
{
    pipeline.AddTimeout(TimeSpan.FromSeconds(5));
    pipeline.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true
    });
});

builder.Services.AddHealthChecks()
    .AddCheck("self_live", () => HealthCheckResult.Healthy(), tags: ["live"])
    .AddCheck("database_ready", () => HealthCheckResult.Healthy(), tags: ["ready"]);

var app = builder.Build();

app.MapHealthChecks("/healthz/liveness", new HealthCheckOptions
{
    Predicate = r => r.Tags.Contains("live")
});

app.MapHealthChecks("/healthz/readiness", new HealthCheckOptions
{
    Predicate = r => r.Tags.Contains("ready")
});

app.MapGet("/api/order/{id}", async (string id, IHttpClientFactory factory, CancellationToken ct) =>
{
    var client = factory.CreateClient("InventoryService");
    return Results.Ok(new { OrderId = id, Status = "Confirmed", Timestamp = DateTime.UtcNow });
});

app.Run();
```

#### File 3: `hands-on/m02/Dockerfile`
```dockerfile
# Multi-stage build menggunakan Ubuntu Chiseled Base
# STAGE 1: Build & Publish
FROM mcr.microsoft.com/dotnet/sdk:8.0-jammy AS build
WORKDIR /src

COPY ["ProductionService.csproj", "./"]
RUN dotnet restore "./ProductionService.csproj"

COPY . .
RUN dotnet publish "./ProductionService.csproj" \
    -c Release \
    -o /app/publish \
    --no-restore \
    /p:UseAppHost=false

# STAGE 2: Ultra-secure, Chiseled Runtime (Non-root UID 1654 built-in)
FROM mcr.microsoft.com/dotnet/nightly/aspnet:8.0-jammy-chiseled AS final
WORKDIR /app
EXPOSE 8080

ENV ASPNETCORE_HTTP_PORTS=8080 \
    DOTNET_EnableDiagnostics=0 \
    ASPNETCORE_ENVIRONMENT=Production

COPY --from=build /app/publish .

# UID 1654 adalah user bawaan chiseled dotnet
USER 1654

ENTRYPOINT ["dotnet", "ProductionService.dll"]
```

#### File 4: `hands-on/m02/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-processing-deployment
  labels:
    app: order-processing
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-processing
  strategy:
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
    type: RollingUpdate
  template:
    metadata:
      labels:
        app: order-processing
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: order-engine
        image: production-order-engine:8.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        securityContext:
          runAsNonRoot: true
          runAsUser: 1654
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"] # Delay sebelum SIGTERM
        livenessProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 2
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 2
        resources:
          limits:
            cpu: "1"
            memory: "512Mi"
          requests:
            cpu: "250m"
            memory: "128Mi"
        env:
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector.observability.svc.cluster.local:4317"
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi endpoint `/healthz/readiness` pada contoh hands-on agar membaca status flag boolean internal statis (`IsMaintenanceMode`).
2. Buat endpoint admin temporer untuk membalikkan flag tersebut menjadi `true`, dan validasi status probe berubah menjadi `HTTP 503 Service Unavailable`.

#### Level: Medium
1. Konfigurasikan Polly v8 Resilience Pipeline khusus pada `IHttpClientFactory` dengan ketentuan:
   - Timeout individu per-attempt: 1.5 detik.
   - Circuit Breaker: Trip jika rasio kegagalan mencapai 40% dalam sampling interval 20 detik, dengan minimum throughput 10 calls.
   - Sediakan fallback handler yang mengembalikan response kosong (`HTTP 200 OK` dengan payload empty array) saat circuit breaker open.

#### Level: Hard
1. Buat custom `IHealthCheck` terdistribusi berkinerja tinggi yang memverifikasi latensi Read/Write ke cache Redis.
2. Health check harus menyertakan batas waktu eksekusi tegas (*cancellation threshold*) 500ms. Jika pengecekan melewati 500ms, kembalikan status `HealthStatus.Degraded`, bukan `Unhealthy`. Integrasikan metrik durasi health check tersebut ke dalam instrumen `Meter` OpenTelemetry.

---

### 14. Challenge

**Studi Kasus Arsitektural: The Zero-Tolerance Storm & Split-Brain Deployment**

Sebuah core-banking system berbasis ASP.NET Core 9 berjalan di atas multi-cluster Kubernetes (Active-Active across two regions). Sistem menangani proses kliring transfer dana bernilai tinggi.

**Skenario Masalah:**
1. Salah satu node pool mengalami *flapping network issue* di mana koneksi TCP antar pod sering mengalami drop parsial dengan *packet loss* 15%.
2. Pipeline resilience bawaan saat ini memicu hedging agresif. Tindakan ini secara tidak sengaja menyebabkan bank sentral menerima transaksi penarikan ganda (*duplicate withdrawal*) pada edge cases tertentu ketika response pertama mengalami delay di layer TCP ACK sementara request hedging berhasil diproses.
3. Saat node bermasalah tersebut di-drain secara otomatis oleh Kubernetes Cluster Autoscaler, pod-pod ASP.NET Core dimatikan secara mendadak, memicu ribuan transaksi tersangkut dalam status "Pending Settlement".

**Tugas Arsitek:**
Rancang arsitektur komprehensif (dokumentasikan dalam spesifikasi teknis dan potongan kode program) yang menyelesaikan problem di atas secara deterministik, mencakup:
- Strategi idempotensi terdistribusi pada tingkat pipeline HTTP outbound ASP.NET Core sebelum Polly mengeksekusi request/retry/hedging.
- Konfigurasi mitigasi hedging agar hanya aktif pada downstream query non-mutatif.
- Mekanisme hand-off transaksi in-flight menggunakan ASP.NET Core Generic Host graceful shutdown token (`CancellationToken` dari `IHostApplicationLifetime.ApplicationStopping`) yang menjamin state transaksi tersimpan di durable distributed transaction storage sebelum proses kontainer mati seutuhnya.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan arsitektural utama antara fungsi Kubernetes Liveness Probe dan Readiness Probe pada aplikasi ASP.NET Core?
2. Mengapa menjalankan kontainer ASP.NET Core menggunakan user default `root` sangat dilarang dalam arsitektur enterprise modern?
3. Apa tujuan dari instruksi `options.AddServerHeader = false;` pada konfigurasi Kestrel?
4. Apa peran dari header HTTP `traceparent` dalam arsitektur distributed tracing W3C?
5. Mengapa alokasi `new HttpClient()` secara lokal di setiap method handler dikategorikan sebagai anti-pattern berat di lingkungan berkinerja tinggi?

#### Pertanyaan Intermediate
6. Bagaimana interaksi teknis antara manifest Kubernetes `lifecycle.preStop.exec` dan opsi Kestrel `HostOptions.ShutdownTimeout` saat terjadi Pod termination?
7. Mengapa Polly v8 Resilience Pipeline dirancang ulang dan meninggalkan fondasi `IAsyncPolicy` dari Polly v7?
8. Bagaimana cara mencegah endpoint health check `/healthz/*` mencemari dashboard metrik dan trace OpenTelemetry Anda?
9. Apa yang terjadi secara internal pada ASP.NET Core ThreadPool ketika terjadi eksekusi kode *Sync-over-Async* (misal: memanggil `.GetAwaiter().GetResult()`) di bawah load 10.000 RPS?
10. Mengapa image berbasis Ubuntu Chiseled / Distroless lebih disukai dibanding Alpine Linux untuk beban kerja runtime .NET skala enterprise?

#### Skenario Kasus Produksi
11. **Skenario 1:** Klaster Kubernetes Anda melakukan *rolling update* deployment baru. Meskipun Anda telah menyediakan 3 replika baru yang berstatus `Running`, klien eksternal menerima gelombang error `HTTP 502 Bad Gateway` selama sekitar 5-10 detik tepat saat pod lama dimatikan. Analisis letak kegagalan konfigurasi dan tentukan solusinya!
12. **Skenario 2:** Aplikasi ASP.NET Core Anda mengalami lonjakan penggunaan memori secara perlahan (*memory leak*) hingga akhirnya dimatikan secara paksa oleh kernel Linux via `OOMKilled` (Out Of Memory). Tracing OTel tidak menunjukkan error. Bagaimana Anda menginvestigasi masalah ini di level BCL/runtime pada kontainer yang tidak memiliki akses shell bash/tools?
13. **Skenario 3:** Tim Anda mengimplementasikan Circuit Breaker menggunakan Polly pada client downstream REST API. Saat downstream service tersebut mengalami degradasi total (100% downstream error), pod ASP.NET Core Anda justru mengalami *CPU spike* mendekati 100% dan latency request lokal ikut lumpuh. Apa kesalahan konfigurasi yang paling mungkin terjadi pada setup resilience pipeline tersebut?

---

#### Kunci Jawaban & Panduan Solusi Evaluasi

##### Jawaban Basic
1. **Liveness Probe** menentukan apakah proses kontainer masih hidup atau mengalami deadlock fatal internal; jika gagal, pod akan di-restart oleh kubelet. **Readiness Probe** menentukan apakah aplikasi siap menerima lalu lintas request dari jaringan (dependensi siap); jika gagal, pod tidak di-restart, melainkan IP-nya dicabut sementara dari routing Ingress/Service.
2. Menjalankan pod sebagai `root` melanggar prinsip *least privilege*. Jika terjadi celah kerentanan *container breakout* (RCE), penyerang akan langsung mendapatkan hak akses administratif penuh ke host kernel node Kubernetes.
3. Untuk keamanan sistem (*security through obscurity*). Menyembunyikan identitas server web Kestrel dari header response HTTP mencegah penyerang melakukan penargetan spesifik terhadap eksploitasi celah keamanan versi web server tertentu.
4. Header `traceparent` berfungsi sebagai jembatan konteks (*context propagation*) yang meneruskan ID jejak telemetri global (`trace-id`), ID span pemanggil (`parent-id`), dan status sampling (`trace-flags`) antar microservices secara terstandarisasi.
5. `new HttpClient()` yang dibuat berulang kali tidak melepaskan socket TCP dasar secara langsung saat di-dispose, melainkan meninggalkannya dalam status `TIME_WAIT`. Hal ini menyebabkan fenomena *Socket Starvation/Exhaustion* yang melumpuhkan kemampuan aplikasi membuka outbound connection baru.

##### Jawaban Intermediate
6. Saat pod di-evict, `preStop` hook dieksekusi terlebih dahulu (misal sleep 15 detik), memberi waktu bagi Kubernetes Endpoints Controller untuk mencabut IP Pod dari semua Ingress Controller. Setelah `preStop` selesai, sinyal `SIGTERM` dikirim ke aplikasi, memicu Kestrel mengaktifkan `ShutdownTimeout` untuk menguras sisa koneksi aktif (*connection draining*) secara bersih tanpa memutus TCP paket secara mendadak.
7. Polly v8 didesain ulang untuk mencapai performa *zero/low allocation* pada *hot path*. Model v7 berbasis alokasi memori heap closure dan objek policy wrapper yang besar, menyebabkan tekanan alokasi pada Garbage Collector (GC) Generasi 0/1 saat menangani throughput puluhan ribu request per detik.
8. Dengan menambahkan filter predikat pada konfigurasi instrumen tracing OpenTelemetry: `opts.Filter = httpContext => !httpContext.Request.Path.StartsWithSegments("/healthz");` sehingga activity tidak dibuat atau diproses ke export buffer.
9. Terjadi pemblokiran thread threadpool yang aktif (`Thread.Sleep` / thread blocking wait). Karena thread kehabisan stok untuk melayani request baru, Kestrel terpaksa meminta runtime menginjeksi thread baru ke pool. Namun, algoritma thread pool injection rate dibatasi secara internal (~1-2 thread per 500ms), memicu antrean *queue request* yang meledak dan latensi sistem yang membeku total (*thread starvation*).
10. Alpine Linux menggunakan pustaka C standard `musl libc`, sedangkan .NET Core dioptimalkan secara mendalam di atas `glibc` (GNU C Library). Implementasi alokasi memori `musl` pada skenario konkurensi tinggi sering memicu fragmentasi memori heap, dan `glibc` pada Ubuntu Chiseled menawarkan performa I/O dan kestabilan thread yang jauh lebih teruji untuk enterprise runtime.

##### Panduan Solusi Skenario Kasus Produksi
11. **Analisis Skenario 1:** Terjadi *race condition* antara propagasi iptables/IP endpoints controller Kubernetes dengan terminasi Kestrel. Pod lama dimatikan sebelum Ingress Controller mencabut IP pod tersebut dari routing list, sehingga Ingress masih mengirim traffic ke pod yang sudah mati.
    **Solusi:** Pasang lifecycle hook `preStop` berupa sleep 10-15 detik di manifest Kubernetes Pod, dan atur `HostOptions.ShutdownTimeout` minimal 30 detik di `Program.cs`.
12. **Analisis Skenario 2:** Gunakan fitur *Kubernetes Ephemeral Debug Container*.
    Jalankan perintah: `kubectl debug -it <pod-name> --image=mcr.microsoft.com/dotnet/monitor:8.0 --target=<container-name>`
    Hubungkan alat diagnostik seperti `dotnet-dump` atau `dotnet-gcdump` ke process ID target aplikasi untuk mengekstrak heap snapshot dan menganalisis object retention path menggunakan Visual Studio / JetBrains dotMemory untuk mendeteksi static reference leaks atau memory pinning.
13. **Analisis Skenario 3:** Terjadi kesalahan konfigurasi di mana Retry Strategy diletakkan di **luar** Circuit Breaker Strategy tanpa Concurrency Limiter, atau `ShouldHandle` mengevaluasi Exception yang salah, memicu loop infinite retry yang berputar cepat (*tight CPU loop*) saat circuit terbuka. Selain itu, alokasi memori akibat exception throwing berkecepatan tinggi (`5000+ exceptions/sec`) memicu GC Thread 100% CPU lock.
    **Solusi:** Urutkan pipeline secara benar: *Fallback -> Total Timeout -> Rate Limiter -> Circuit Breaker -> Retry -> Attempt Timeout*. Tangani kondisi HTTP error menggunakan response status result match, bukan melempar C# Exception (`HandleResult(r => !r.IsSuccessStatusCode)`), untuk menjaga alokasi heap tetap zero.

---

### 16. Summary
- Membangun arsitektur enterprise ASP.NET Core di lingkungan cloud-native membutuhkan orkestrasi yang harmonis antara siklus hidup platform (.NET Hosting Runtime) dan sistem operasi klaster (Kubernetes Pod Lifecycle).
- Isolasi ketat pada Health Check Primitives (Startup, Liveness, Readiness) mutlak diperlukan untuk mencegah insiden *cascading failure* dan *restart storms*.
- Observabilitas modern mengandalkan standar OpenTelemetry terpadu (Metrics, Tracing, Logs) yang dipancarkan secara asinkron melalui OTLP, membebaskan sistem dari *vendor lock-in*.
- Pemanfaatan Polly v8 Resilience Pipeline menyediakan perlindungan jaringan berlapis (*defense-in-depth*) dengan alokasi heap mendekati nol, menjaga aplikasi tetap stabil di bawah tekanan konkurensi ekstrem.
- Container hardening dengan basis Chiseled/Distroless image dan konfigurasi non-root UID menjamin sistem beroperasi dengan postur keamanan enterprise tertinggi sesuai standar kepatuhan regulasi industri modern.