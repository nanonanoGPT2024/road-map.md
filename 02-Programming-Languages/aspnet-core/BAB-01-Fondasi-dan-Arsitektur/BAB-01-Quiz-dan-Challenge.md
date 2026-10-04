# BAB 01: Quiz, Challenge, & Knowledge Check
**.NET Runtime, Hosting, & Request Pipeline Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: WebApplicationBuilder vs Generic Host (`IHostBuilder`)
Jelaskan perbedaan mendasar antara model hosting tradisional `IHostBuilder` / `Startup.cs` (.NET Core 2.x - 3.x / 5) dengan model modern `WebApplicationBuilder` (.NET 6+) dari perspektif:
1. Tahapan inisialisasi konfigurasi (*two-stage initialization* vs *single-stage*).
2. Kapan `IServiceProvider` (DI container) dibekukan (*frozen/built*).
3. Mengapa arsitektur baru ini memungkinkan deteksi miskonfigurasi dependensi secara lebih awal saat fase *bootstrapping*?

### Soal 1.2: Siklus Hidup dan Thread Safety `HttpContext`
`HttpContext` adalah abstraksi runtime paling krusial dalam ASP.NET Core. 
1. Mengapa instansi `HttpContext` **tidak thread-safe** dan dirancang untuk di-*recycle* menggunakan pooling (`IHttpExtendedFeatures` / object pooling)?
2. Jelaskan konsekuensi internal pada CLR heap dan kestabilan aplikasi jika seorang engineer melakukan *fire-and-forget* (`Task.Run`) yang mereferensikan instance `HttpContext` dari request yang telah selesai diproses (*request completion*).

### Soal 1.3: Arsitektur I/O Kestrel dan `System.IO.Pipelines`
Kestrel telah berevolusi dari implementasi berbasis Libuv menjadi managed Sockets transport yang didukung oleh `System.IO.Pipelines`.
1. Masalah memori apa yang inheren pada manipulasi raw socket streaming (`byte[]` buffer allocation & GC pinning) yang diselesaikan oleh `PipeReader` dan `PipeWriter`?
2. Bagaimana mekanisme *backpressure* dikelola di antara socket hardware layer dan downstream middleware pipeline?

### Soal 1.4: Dualitas ThreadPool (.NET Runtime: Worker Threads vs IOCP Threads)
Dalam melayani request HTTP throughput tinggi:
1. Apa peran spesifik dari **Worker Threads** versus **I/O Completion Port (IOCP) Threads** di dalam CLR ThreadPool?
2. Saat thread mengeksekusi panggilan asynchronous I/O murni (misalnya membaca database network stream via `await dbContext.Users.ToListAsync()`), thread mana yang aktif, kapan context-switch terjadi, dan di mana IOCP thread mengambil alih *continuation*?

### Soal 1.5: Komposisi dan Determinisme `RequestDelegate`
Middleware pipeline ASP.NET Core sering digambarkan sebagai rantai *Russian Doll*.
1. Secara internal, bagaimana method chaining `app.Use(...)` dikompilasi menjadi rantai eksekusi tunggal `RequestDelegate`? Apakah ini berupa list iteratif runtime atau nested dynamic closure?
2. Jelaskan mengapa urutan pemanggilan middleware bersifat deterministik dan tidak dapat dimodifikasi secara dinamis setelah `app.Build()` dieksekusi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Mekanika *Captive Dependency* dan Scope Validation
Diberikan konfigurasi berikut di `Program.cs`:
```csharp
builder.Services.AddSingleton<ICacheService, DistributedCacheService>();
builder.Services.AddScoped<IUserRepository, UserRepository>();
builder.Services.AddSingleton<IOrderProcessingService, OrderProcessingService>(); 
// OrderProcessingService menginjeksi IUserRepository via constructor
```
1. Jelaskan secara mekanis bagaimana dependensi `IUserRepository` (Scoped) menjadi *Captive Dependency* di dalam `OrderProcessingService` (Singleton).
2. Bagaimana CLR Garbage Collector terhalang mereklamasi instance `IUserRepository` dan `DbContext` yang menempel padanya?
3. Bagaimana runtime ASP.NET Core mendeteksi anomali ini saat `builder.Host.UseDefaultServiceProvider(o => o.ValidateScopes = true)` aktif, dan pada fase apa validasi tersebut dieksekusi (bootstrap vs first resolution)?

### Soal 2.2: ThreadPool Starvation Akibat Sync-over-Async
Pada ASP.NET Full Framework (4.x), *sync-over-async* (`.Result` atau `.GetAwaiter().GetResult()`) sering kali menyebabkan deadlock karena kehadiran `SynchronizationContext`. ASP.NET Core **tidak memiliki** `SynchronizationContext`.
1. Mengapa praktik sync-over-async di ASP.NET Core tetap dapat melumpuhkan server secara katastropik (*ThreadPool Starvation*) pada beban request tinggi?
2. Jelaskan interaksi antara *Hill-Climbing Algorithm* milik ThreadPool dengan keterlambatan injeksi thread baru (thread injection rate throttling ~1-2 thread per 500ms) saat bottleneck terjadi.

### Soal 2.3: Server GC vs Workstation GC dalam Kontainer Docker/Kubernetes
Secara *default*, aplikasi ASP.NET Core yang berjalan di server mengaktifkan **Server Garbage Collection (Server GC)**.
1. Bagaimana arsitektur internal Server GC mengalokasikan Managed Heap per logical core (vCPU)?
2. Dalam lingkungan microservices (Kubernetes Pod) dengan cgroups memory limit ketat (misal `resources.limits.memory: "512Mi"`), mengapa Server GC dapat memicu status `OOMKilled` lebih cepat daripada Workstation GC jika tidak dikonfigurasi dengan flag GC heap limit yang tepat?

### Soal 2.4: Mutasi dan Deserialisasi pada `IFeatureCollection`
`HttpContext.Features` adalah representasi dari pattern *Type-safe Extensible Interface/Property Bag*.
1. Bagaimana Kestrel mengoptimalkan alokasi memori internalnya melalui implementasi `FeatureReferences<TRef>` struct dibanding melakukan look-up berbasis `Dictionary<Type, object>` standar?
2. Jika sebuah custom middleware memodifikasi atau mengganti instance `IHttpConnectionFeature`, bagaimana hal tersebut berdampak langsung pada downstream middleware seperti `ForwardedHeadersMiddleware` atau TLS termination logging?

### Soal 2.5: Deep Dive Graceful Shutdown Sequence
Ketika Kestrel menerima signal `SIGTERM` dari orchestrator (Kubernetes):
1. Uraikan urutan eksekusi internal komponen berikut:
   - `IHostApplicationLifetime.ApplicationStopping`
   - Kestrel Socket Unbinding / Stop Accepting New TCP Connections
   - In-flight Request Drain Timeout (`HostOptions.ShutdownTimeout`)
   - `IHostApplicationLifetime.ApplicationStopped`
   - Dispose Transient/Scoped/Singleton Containers
2. Apa yang terjadi pada request HTTP yang sedang aktif di tengah-tengah pemrosesan ketika batas `ShutdownTimeout` terlampaui? Bagaimana cara mendeteksi interupsi tersebut di level aplikasi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden ThreadPool Starvation & Cascade 504 pada Flash Sale
**Konteks Arsitektur:**
Sistem e-commerce enterprise menjalankan payment gateway adapter menggunakan ASP.NET Core 8 di Kubernetes. Traffic melonjak dari 1.000 RPS menjadi 35.000 RPS dalam 30 detik saat flash sale. Metrik monitoring menunjukkan:
- CPU Usage: Rendah (~20-25%).
- Memory Usage: Stabil di 40%.
- HTTP Request Queue Length (Kestrel): Meroket tajam.
- Response Time p99: Naik dari 45ms ke 30.000ms (timeout).
- Error log: Dominasi `System.TimeoutException` dan HTTP 504 Bad Gateway dari reverse proxy (Envoy).
- Thread Count (CLR): Naik secara linear lambat dari 30 ke 300+.

Setelah tim melakukan inspeksi thread dump via `dotnet-dump`, ditemukan ribuan stack trace dengan pola berikut:
```text
System.Threading.Monitor.Wait
System.Threading.Tasks.Task.Wait
PaymentGateway.Client.LegacyCryptoSigner.SignPayload(...)
PaymentGateway.Middleware.SignatureVerificationMiddleware.InvokeAsync(...)
```

**Pertanyaan Diagnostik:**
1. Analisis akar masalah (root cause) sistematis: Mengapa CPU rendah padahal antrean request menumpuk dan response time hancur?
2. Mengapa ThreadPool tidak langsung menaikkan jumlah worker thread secara instan menjadi 3.000 untuk menyerap lonjakan request tersebut?
3. Langkah remidiasi darurat (quick mitigation) apa yang dapat diubah pada runtime level configuration (`runtimeconfig.json` / environment variable) sebelum codebase refactoring selesai?
4. Bagaimana restrukturisasi kode permanen pada `SignatureVerificationMiddleware` agar masalah ini tidak dapat terjadi lagi secara arsitektural?

---

### Skenario B: Race Condition dan State Corruption pada Middleware Telemetri
**Konteks Arsitektur:**
Sebuah tim platform engineering membuat custom middleware untuk melakukan auditing request payload dan response time ke centralized Kafka cluster. Mereka mengimplementasikan middleware berikut:

```csharp
public class AuditLoggingMiddleware
{
    private readonly RequestDelegate _next;
    private readonly IAuditKafkaProducer _producer;
    private AuditPayload _currentPayload; // State disimpan di field class

    public AuditLoggingMiddleware(RequestDelegate next, IAuditKafkaProducer producer)
    {
        _next = next;
        _producer = producer;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        _currentPayload = new AuditPayload
        {
            TraceId = context.TraceIdentifier,
            Path = context.Request.Path,
            StartTime = DateTime.UtcNow
        };

        // Membaca request body untuk audit
        context.Request.EnableBuffering();
        using (var reader = new StreamReader(context.Request.Body, leaveOpen: true))
        {
            _currentPayload.RequestBody = await reader.ReadToEndAsync();
            context.Request.Body.Position = 0;
        }

        await _next(context);

        _currentPayload.StatusCode = context.Response.StatusCode;
        _currentPayload.DurationMs = (DateTime.UtcNow - _currentPayload.StartTime).TotalMilliseconds;

        // Kirim log secara async tanpa menahan response pipeline (fire-and-forget)
        _ = Task.Run(() => _producer.SendAuditAsync(_currentPayload));
    }
}
```

Setelah rilis ke staging environment dengan beban concurrency tinggi (500 user paralel):
- Audit log di Kafka tercampur-aduk: `TraceId` milik User A berisi `RequestBody` dari User B.
- Terjadi sporadic `ObjectDisposedException` dan `NullReferenceException` di background thread.
- Terjadi high memory retention dan unhandled process crash.

**Pertanyaan Diagnostik:**
1. Identifikasi minimal **tiga kesalahan arsitektur fatal** terkait lifecycle, thread-safety, dan resource management pada implementasi middleware di atas.
2. Jelaskan siklus hidup (*instance lifecycle*) dari class Middleware yang didaftarkan via `app.UseMiddleware<T>()`. Mengapa penggunaan instance variable (`_currentPayload`) pada level class middleware merupakan pelanggaran fatal?
3. Tuliskan kode perbaikan (*refactored production-grade version*) dari `AuditLoggingMiddleware` yang:
   - Bersifat completely thread-safe dan stateless.
   - Tidak membocorkan state antar-request.
   - Menghindari silent failure pada unhandled exception di asynchronous logging task.

---

### Skenario C: Trade-off Arsitektur High-Throughput Edge Ingestion (Minimal API vs Controller vs Raw Kestrel Middleware)
**Konteks Arsitektur:**
Perusahaan IoT Automotive sedang merancang edge collector service baru yang harus menerima telemetri GPS dan status sensor dari 500.000 kendaraan yang terhubung secara konstan via HTTP/2 dan HTTP/3 POST request berukuran kecil (< 512 bytes payload). Service ini harus memproses hingga **150.000 RPS per node server** dengan target SLA p99 latency < 5ms.

Arsitek sistem sedang memperdebatkan tiga opsi pipeline framework ASP.NET Core:
- **Opsi 1:** Standard MVC Controller (`[ApiController]`) dengan model binding automasi.
- **Opsi 2:** ASP.NET Core Minimal APIs (`app.MapPost(...)`) dengan native JSON source generator.
- **Opsi 3:** Custom Pure Middleware Pipeline (`app.Run(RequestDelegate)`) yang beroperasi langsung di atas `System.IO.Pipelines` dan `System.Text.Json.Utf8JsonReader` tanpa layer routing ASP.NET Core sama sekali.

**Pertanyaan Diagnostik:**
1. Bedah overhead performa (*allocations*, *call-stack depth*, *boxing/unboxing*, dan *routing evaluation*) dari Opsi 1 dibanding Opsi 2 dan Opsi 3.
2. Dalam kondisi throughput ekstrem ini, jelaskan pengaruh *Endpoint Routing Middleware* (`EndpointRoutingMiddleware` & `EndpointMiddleware`) terhadap alokasi heap per-request.
3. Berikan rekomendasi arsitektural yang didasarkan pada perbandingan trade-off yang objektif:
   - Kecepatan throughput vs Kemudahan maintainability/ekstensibilitas tim engineering.
   - Kapan Opsi 3 mutlak dibutuhkan, dan apa risiko teknis (*technical debt*) yang dibawa jika mengabaikan standard abstraction layer ASP.NET Core?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Allocation Circuit-Breaker Pipeline Guard

#### Deskripsi Skenario
Dalam sistem core banking ber-throughput tinggi, layanan backend downstream rentan mengalami degradasi performa yang merembet ke seluruh ekosistem (*cascading failure*). Anda ditugaskan oleh Principal Architect untuk membangun sebuah **Custom Middleware Pipeline Guard** yang berfungsi sebagai proteksi tingkat tinggi pada request pipeline sebelum request diteruskan ke downstream microservices/database.

#### Problem Statement
Middleware bawaan framework atau third-party sering kali menghasilkan alokasi memori berlebih (`GC pressure`) dan tidak mampu membedakan pembatalan request dari client (*client disconnect/timeout*) dengan degradasi downstream internal, yang menyebabkan ThreadPool tertekan dan metrik healthcheck bias.

#### Requirements
Buat implementasi custom middleware bernama `ResilientPipelineGuardMiddleware` dengan spesifikasi teknis:

1. **Active Concurrency Limiter (Non-blocking):**
   - Batasi eksekusi concurrent request pipeline maksimum `N` (misal 5.000 concurrent request).
   - Jika kapasitas penuh, request harus **segera ditolak** dengan HTTP Status `429 Too Many Requests` tanpa menunggu, dan menyertakan header `Retry-After: 5`.
   - Gunakan primitif sinkronisasi non-blocking dan lock-free (misal `Interlocked` / `SemaphoreSlim(N, N)` tanpa pemborosan alokasi task).

2. **Zero-Allocation Execution Path:**
   - Pada *happy path*, middleware tidak boleh mengalokasikan object baru di Managed Heap (Gunakan `ValueTask`, hindari closure allocation `lambda capture`, gunakan struct jika membutuhkan state holder).

3. **Graceful Cancellation & Abort Propagation:**
   - Sambungkan `context.RequestAborted` (CancellationToken) ke downstream pipeline dengan timeout dinamis (maksimal 3 detik pemrosesan per request).
   - Jika client memutuskan koneksi di tengah jalan (*aborted*), middleware harus menangkap `OperationCanceledException`, membatalkan downstream execution, menghentikan logging yang tidak perlu, dan mengembalikan HTTP status yang sesuai tanpa melempar unhandled exception ke root host.

4. **Telemetry & Feature Collection Mutation:**
   - Catat durasi request secara presisi tinggi menggunakan `ValueStopwatch` (struct-based, zero allocation).
   - Suntikkan custom feature `IPipelineGuardFeature` ke dalam `context.Features` sehingga downstream controller/minimal API dapat membaca informasi apakah request tersebut masuk dalam kategori *high-concurrency window*.

#### Constraints & Aturan Main
- **Dilarang** menggunakan library eksternal (seperti Polly atau AspNetCoreRateLimit). Gunakan hanya native primitives dari runtime .NET (`System.Threading`, `System.Diagnostics`, `Microsoft.AspNetCore.Http`).
- **Dilarang** menggunakan `new Thread(...)`, `.Result`, `.Wait()`, atau `.GetAwaiter().GetResult()`.
- Wajib menyertakan unit/integration test stub menggunakan `WebApplicationFactory<TProgram>` yang memverifikasi bahwa ketika limit concurrency tercapai, request ke-(N+1) langsung menerima respons HTTP 429 secara konsisten.

#### Expected Output
1. File C# utuh: `ResilientPipelineGuardMiddleware.cs` beserta extension method `UsePipelineGuard()`.
2. Definisi struct `ValueStopwatch` dan interface `IPipelineGuardFeature`.
3. Demonstrasi registrasi pipeline di `Program.cs` yang memposisikan guard ini pada posisi pipeline yang paling tepat secara arsitektural (disertai komentar justifikasi urutan middleware).

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman konseptual dan kapabilitas teknis Anda sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Anatomi transisi eksekusi dari Kestrel socket transport, pembacaan memory streams via `PipeReader`, hingga instansiasi pipeline delegasi `RequestDelegate`.
- [ ] Perbedaan siklus hidup internal antara `.NET Runtime Engine` (CLR/CoreCLR), `Generic Host` container, dan `Kestrel Web Server`.
- [ ] Detail siklus hidup dependensi DI (`Transient`, `Scoped`, `Singleton`) dan bahaya laten *Captive Dependency* dalam aplikasi multi-threaded.
- [ ] Perilaku internal `ThreadPool` (.NET Core runtime), dinamika *Worker Threads* vs *IOCP Threads*, dan bahaya katastropik *ThreadPool Starvation* yang dipicu oleh blocking code.
- [ ] Dampak perbedaan *Server GC* vs *Workstation GC*, dynamic heap scaling, dan konfigurasi cgroups memory limits pada containerized ASP.NET Core environments.
- [ ] Arsitektur internal `HttpContext`, mekanisme pooling-nya, serta mengapa objek ini bersifat non-thread-safe dan terikat secara absolut pada siklus request.
- [ ] Urutan baku *middleware execution pipeline* dan dampak fatal dari salah penempatan middleware mendasar (seperti `UseRouting`, `UseAuthentication`, `UseAuthorization`, dan `UseCors`).

### Saya tidak perlu menghafal:
- [ ] Seluruh signature method overload dari `IApplicationBuilder` atau `IServiceCollection` (cukup pahami konsep dasarnya dan andalkan IDE IntelliSense).
- [ ] Nilai byte-per-byte binary structure dari HTTP/2 frame format atau HTTP/3 QUIC packets (cukup pahami abstraksi transport layer dan bagaimana Kestrel menanganinya).
- [ ] Detail implementasi C++ tingkat rendah dari JIT Compiler RyuJIT atau algoritma assembly GC internal (cukup pahami konsep GC Generation 0/1/2/LOH/POH dan dampaknya pada latency).

### Saya harus bisa melakukan:
- [ ] Menganalisis memory dump dan thread dump aplikasi ASP.NET Core menggunakan tool diagnostik seperti `dotnet-dump`, `dotnet-gcdump`, dan `dotnet-trace` untuk menemukan thread starvation atau memory leak.
- [ ] Mengonfigurasi dan memvalidasi Service Provider Scope saat bootstrapping (`ValidateScopes = true` dan `ValidateOnBuild = true`) untuk mencegah bug dependency injection di production.
- [ ] Membangun custom middleware performa tinggi dengan pendekatan zero/low-allocation memanfaatkan memory-efficient APIs (`ValueTask`, `ArrayPool`, `Span<T>`).
- [ ] Mengatur mekanisme graceful shutdown yang tangguh pada level Kestrel dan Kubernetes pod lifecycle integration (`PreStop` hook dan `IHostApplicationLifetime`).
- [ ] Melakukan troubleshooting koneksi jaringan, port exhaustion, socket leaks, dan konfigurasi connection pooling pada downstream HTTP/TCP invocation.