# Bab 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Internal Kestrel**: Menguasai interaksi antara *OS Socket Layer*, `SocketTransport`, thread I/O (*SocketTransport thread*), dan abstraksi `System.IO.Pipelines` untuk pemrosesan I/O non-blocking dan zero-allocation.
2. **Mengonstruksi Custom Middleware Pipeline Lanjutan**: Mengimplementasikan middleware berbasis konvensi maupun berbasis factory (`IMiddleware`) dengan manipulasi I/O tingkat rendah melalui `PipeReader` dan `PipeWriter`, serta memitigasi risiko *memory leak* dan fragmentasi Large Object Heap (LOH).
3. **Menguasai Internal Dependency Injection Container ASP.NET Core**: Mengidentifikasi dan mencegah anomali *Captive Dependencies*, merancang *dynamic scope boundaries*, memanfaatkan *Keyed Services*, serta mengaudit pohon resolusi dependensi melalui *CallSite Factory*.
4. **Menerapkan Advanced Options Pattern & Live Configuration Reloading**: Mengimplementasikan `IOptions`, `IOptionsSnapshot`, dan `IOptionsMonitor` secara presisi sesuai *lifecycle boundary*, lengkap dengan integrasi token perubahan (`IChangeToken`).
5. **Mendiagnosis Masalah Skalabilitas dan Threading**: Menemukan dan mengatasi *Thread Pool Starvation*, *Sync-over-Async*, *High Allocation Latency Spikes*, serta *unhandled socket aborts* menggunakan tooling diagnostik produksi modern (`dotnet-dump`, `dotnet-counters`, `dotnet-trace`).

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib memahami:
* Fondasi ASP.NET Core dasar (Hosting, Kestrel basics, Dependency Injection lifecycles dasar: *Singleton*, *Scoped*, *Transient*).
* C# tingkat lanjut: `Span<T>`, `Memory<T>`, `ReadOnlySequence<T>`, `ValueTask<T>`, `async`/`await` state machine mechanics, unmanaged pointer awareness, dan generic constraints.
* Konsep sistem operasi: Network sockets (TCP/IP stack), non-blocking I/O (epoll/kqueue/IOCP), context switching, CPU cache locality, dan Large Object Heap (LOH) vs Small Object Heap (SOH) pada Garbage Collector .NET.
* Lingkungan kerja: .NET 8 SDK LTS atau lebih baru terpasang di Linux/macOS/Windows, terminal CLI, dan debugger terkonfigurasi.

---

### 3. Concept & Internal Architecture

#### 3.1 Kestrel Deep Dive & System.IO.Pipelines
Kestrel tidak membaca request HTTP langsung ke dalam buffer `byte[]` atau `MemoryStream` biasa. Penggunaan model I/O konvensional berbasis stream menyebabkan alokasi memori berlebih yang memicu tekanan pada Garbage Collector (GC), khususnya GC Pause generasi 2 (Gen 2).

Kestrel modern dibangun di atas abstraksi transport layer berbasis **`System.IO.Pipelines`**:
* **Transport Engine**: Secara *default*, Kestrel menggunakan `SocketTransport` yang mengikat native socket abstraction (IOCP pada Windows, epoll pada Linux).
* **The Pipe Architecture**: Setiap koneksi TCP dialokasikan sepasang pipa: satu untuk pembacaan (`PipeReader`) dan satu untuk penulisan (`PipeWriter`). Pipa ini meminjam memori dari `MemoryPool<byte>` global (berbasis *slab allocation* berukuran 4096 byte per blok).
* **Zero-Copy Parsing**: Parser HTTP internal Kestrel (`HttpParser<T>`) membedah header dan body langsung dari struktur memori tak berurutan (`ReadOnlySequence<byte>`) tanpa menyalin data ke dalam `string` hingga mutlak diperlukan.

```
[OS Network Socket] 
       │ (epoll / IOCP non-blocking event)
       ▼
[SocketTransport (IConnectionListener)]
       │ ReadAsync into MemoryPool<byte> Slab
       ▼
[PipeWriter (Request Data)] ───► [PipeReader]
                                      │
                                      ▼
                             [HttpParser<T>] (Zero-Copy Header/Method Scan)
                                      │
                                      ▼
                             [HttpContext Allocation via ObjectPool]
                                      │
                                      ▼
                             [RequestDelegate Pipeline]
```

#### 3.2 Middleware Compilation Mechanics
Secara internal, middleware ASP.NET Core direpresentasikan oleh delegasi fungsional:
```csharp
public delegate Task RequestDelegate(HttpContext context);
```
Saat aplikasi dijalankan, `IApplicationBuilder.Build()` mengeksekusi metode chaining yang mengompilasi seluruh middleware terdaftar menjadi sebuah *single nested delegate tree*:
```csharp
Func<RequestDelegate, RequestDelegate>
```
Struktur ini disusun dari middleware terakhir (ekor/terminal) ke middleware pertama (kepala). Setiap middleware menampung referensi ke delegasi berikutnya (`_next`). Panggilan `_next(context)` bukan sekadar pemanggilan event, melainkan eksekusi langsung pada call stack runtime C#.

Terdapat dua paradigma utama:
1. **Convention-Based Middleware**: Didaftarkan via `UseMiddleware<T>()`. Diinstansiasi sekali (*Singleton-like*) saat kompilasi pipeline. Dependensi *scoped* **tidak boleh** diinjeksi via konstruktor (memicu *captive dependency*); dependensi *scoped* harus diinjeksi melalui parameter metode `InvokeAsync(HttpContext context, IScopedDependency dep)`.
2. **Factory-Based Middleware (`IMiddleware`)**: Mengimplementasikan antarmuka `IMiddleware` dan didaftarkan ke DI container. Diinstansiasi per request (*Transient/Scoped*), memvalidasi dependensi secara aman via konstruktor, namun menimbulkan sedikit overhead lookup service provider.

#### 3.3 Dependency Injection Container Internals
DI container bawaan (`Microsoft.Extensions.DependencyInjection`) dirancang untuk kecepatan eksekusi tinggi menggunakan mesin kompilasi ekspresi internal:
* **CallSiteFactory**: Bertanggung jawab memvalidasi dependensi dan menyusun pohon resolusi (*call site graph*).
* **ILEmitResolver / DynamicMethod**: Container tidak menggunakan refleksi (`System.Reflection`) saat runtime request berlangsung. Container mengompilasi pohon dependensi menjadi IL bytecode dinamis pada resolusi pertama, menghasilkan performa eksekusi yang setara dengan instansiasi manual (`new Service()`).
* **Captive Dependency Anomaly**: Terjadi ketika service dengan masa hidup lebih panjang (*Singleton*) menginjeksi service dengan masa hidup lebih pendek (*Scoped*). Instance *Scoped* tersebut terperangkap di dalam *Singleton*, tidak pernah dibersihkan oleh Garbage Collector, dan berisiko membagi *state* antar-request/antar-user yang berbeda (*concurrency bug* fatal).

---

### 4. Why & What

| Pertanyaan | Jawaban & Analisis Rekayasa |
| :--- | :--- |
| **Why not use standard `Stream` for reading bodies?** | `Stream.ReadAsync` tradisional mengharuskan developer mengalokasikan array byte (`byte[]`) sendiri atau membaca ke `MemoryStream`. Tindakan ini menyebabkan alokasi berulang di heap, fragmentasi memori, dan eskalasi ke LOH jika payload berukuran > 85.000 byte. `System.IO.Pipelines` meminjam memori dari pool terkelola, mendukung konsumsi bertahap (*backpressure*), dan tidak memicu alokasi heap baru saat payload bertambah besar. |
| **Why does Captive Dependency break multitenancy/security?** | Jika `DbContext` (Scoped) terperangkap dalam background worker (Singleton), maka cache level 1 dari EF Core tidak pernah di-*clear*. Data transaksi dari Tenant A dapat bocor ke Tenant B, dan konkurensi multi-thread pada instans `DbContext` yang sama akan memicu crash `InvalidOperationException: A second operation was started on this context before a previous operation completed`. |
| **What is `IOptionsMonitor<T>` vs `IOptionsSnapshot<T>`?** | `IOptionsSnapshot<T>` dihitung ulang per request (Scoped) dan menjamin konsistensi nilai sepanjang siklus hidup request tersebut. `IOptionsMonitor<T>` adalah Singleton yang membaca konfigurasi secara real-time via `IChangeToken`, memungkinkan pembaruan konfigurasi tanpa me-restart container/pod, serta menyediakan event handler `OnChange`. |

---

### 5. How (Workflow Detail)

Berikut adalah siklus hidup penanganan request HTTP berkinerja tinggi dari transport socket hingga middleware pipeline:

```
[OS Kernel]
  │
  ├─ 1. TCP Handshake selesai; Socket read ready.
  ▼
[Kestrel SocketTransport]
  │
  ├─ 2. Alokasi Buffer dari MemoryPool<byte>.
  ├─ 3. PipeWriter.GetMemory() -> Socket.ReceiveAsync() -> PipeWriter.Advance().
  ├─ 4. PipeWriter.FlushAsync() memicu event downstream.
  ▼
[Kestrel ConnectionHandler]
  │
  ├─ 5. PipeReader membaca stream bytes tak terputus.
  ├─ 6. HttpParser memeriksa batas Header (CRLF).
  ├─ 7. Parsing method, path, headers ke internal feature collections.
  ├─ 8. HttpContext dikonstruksi dari ObjectPool<DefaultHttpContext>.
  ▼
[Middleware Pipeline Execution]
  │
  ├─ 9.  Middleware-1 (Global Diagnostics & Exception Handler)
  │        └─ delegasi ke _next(context)
  ├─ 10. Middleware-2 (High-Throughput Zero-Copy Payload Auditor)
  │        └─ membaca `context.Request.BodyReader` secara streaming
  ├─ 11. Middleware-3 (Authentication / Authorization / Scope Validation)
  │        └─ resolusi dynamic scoped services via ServiceProvider Engine
  ├─ 12. Middleware-4 (EndpointRouting / Terminal Middleware)
  │        └─ Menulis payload balik ke `context.Response.BodyWriter`
  ▼
[Kestrel Output Flush]
  │
  ├─ 13. Flush data ke soket OS via PipeWriter non-blocking I/O.
  ├─ 14. HttpContext di-reset dan dikembalikan ke ObjectPool.
  └─ 15. Memory buffer dikembalikan ke MemoryPool.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Distribusi Air Kota Bertekanan Tinggi

* **Stream Konvensional = Ember Manual**: Anda ingin mengalirkan air dari pipa sumber ke bak penampung. Setiap kali air mengalir, Anda harus membeli ember baru (`new byte[4096]`), menuangkan isinya, lalu membuang ember tersebut ke tempat sampah (Garbage Collection). Jika volume air besar, Anda butuh ember raksasa yang membutuhkan derek khusus untuk membuangnya (Large Object Heap).
* **System.IO.Pipelines = Kanal Pipa Sirkular Fleksibel**: Pipa transport langsung terhubung ke katup pemrosesan. Air mengalir melalui segmen-segmen pipa yang dapat digunakan kembali (*reusable memory slabs*). Segmen pipa yang sudah kosong langsung dialirkan kembali ke hulu untuk diisi air baru, tanpa ada ember yang dibeli atau dibuang.
* **Captive Dependency = Teknisi Magang yang Terkunci di Gudang Sentral**: Teknisi magang (*Scoped Dependency*) bertugas membawa catatan untuk satu shift (*Single Request*). Jika ia diajak masuk dan dikunci di dalam brankas pusat (*Singleton*), ia tidak pernah pulang. Catatan shift pertamanya terus digunakan untuk shift-shift berikutnya selama bertahun-tahun, mencampurkan data inventaris hari pertama dengan hari-hari selanjutnya secara permanen.

#### Diagram Arsitektur Memory & Pipeline Execution
```
+-----------------------------------------------------------------------------+
|                                KESTREL CORE                                 |
|                                                                             |
|  [OS Socket] <---> [SocketTransport]                                        |
|                          │                                                  |
|                          ▼                                                  |
|           +-------------------------------+                                 |
|           |   MemoryPool<byte> (Slabs)   |                                 |
|           +-------------------------------+                                 |
|                     ▲          │                                            |
|        Rent Buffers │          │ Return Buffers                             |
|                     │          ▼                                            |
|             [System.IO.Pipelines (PipeReader/PipeWriter)]                   |
|                                │                                            |
|                                ▼                                            |
|                   [HttpParser (ReadOnlySequence)]                           |
+--------------------------------┼--------------------------------------------+
                                 │
                                 ▼
+-----------------------------------------------------------------------------+
|                          COMPILED MIDDLEWARE TREE                           |
|                                                                             |
|   HttpContext                                                               |
|        │                                                                    |
|        ├──► [AuditLogMiddleware (Zero-Alloc)]                               |
|        │          │                                                         |
|        │          ├── (Advance Pipeline via _next)                          |
|        │          ▼                                                         |
|        ├──► [DynamicScopeValidationMiddleware]                              |
|        │          │                                                         |
|        │          ├── (Advance Pipeline via _next)                          |
|        │          ▼                                                         |
|        └──► [Terminal Execution Engine / Minimal API]                       |
|                   │                                                         |
|                   ▼                                                         |
|        [Response.BodyWriter.WriteAsync(ZeroCopyMemory)]                     |
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Deteksi dan Isolasi Pipeline Execution

Berikut implementasi konseptual untuk memahami resolusi middleware pipeline berbasis inline compilation:

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// Middleware 1: Execution Order & Metric Tracker
app.Use(async (context, next) =>
{
    context.Response.Headers.Append("X-Pipeline-Engine", "Kestrel-Custom-Core");
    var startTime = System.Diagnostics.Stopwatch.GetTimestamp();

    await next(context);

    var elapsedMs = System.Diagnostics.Stopwatch.GetElapsedTime(startTime).TotalMilliseconds;
    Console.WriteLine($"[DIAGNOSTICS] Path: {context.Request.Path} executed in {elapsedMs:F4} ms");
});

// Terminal Middleware
app.Run(async (context) =>
{
    context.Response.ContentType = "text/plain";
    await context.Response.WriteAsync("Core Pipeline Functional.");
});

app.Run();
```

#### 7.2 Practical Example: Enterprise Zero-Allocation Request Body Inspector & Dynamic Scoped Resolution

Skenario: Middleware enterprise yang membaca request body payload JSON secara streaming langsung melalui `System.IO.Pipelines`, melakukan hash payload (misalnya untuk audit integritas transaksi perbankan), menginjeksi *Keyed Service*, dan mengonsumsi live configurations tanpa alokasi memori berlebih.

```csharp
// Infrastructure/Security/PayloadAuditorMiddleware.cs
namespace Enterprise.Core.Architecture.Middleware;

using System.Buffers;
using System.IO.Pipelines;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

public sealed class AuditorOptions
{
    public const string SectionName = "AuditorSettings";
    public bool Enabled { get; set; } = true;
    public int MaxInspectPayloadBytes { get; set; } = 1024 * 1024; // 1 MB
}

public interface IAuditStorageService
{
    Task RecordPayloadHashAsync(string path, string hashValue, CancellationToken ct);
}

public sealed class DatabaseAuditStorageService : IAuditStorageService
{
    private readonly ILogger<DatabaseAuditStorageService> _logger;

    public DatabaseAuditStorageService(ILogger<DatabaseAuditStorageService> logger)
    {
        _logger = logger;
    }

    public Task RecordPayloadHashAsync(string path, string hashValue, CancellationToken ct)
    {
        _logger.LogInformation("Audit committed to DB: {Path} -> Hash: {Hash}", path, hashValue);
        return Task.CompletedTask;
    }
}

public sealed class PayloadAuditorMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<PayloadAuditorMiddleware> _logger;
    private readonly IOptionsMonitor<AuditorOptions> _optionsMonitor;

    public PayloadAuditorMiddleware(
        RequestDelegate next,
        ILogger<PayloadAuditorMiddleware> logger,
        IOptionsMonitor<AuditorOptions> optionsMonitor)
    {
        _next = next;
        _logger = logger;
        _optionsMonitor = optionsMonitor;
    }

    public async Task InvokeAsync(HttpContext context, IAuditStorageService auditStorage)
    {
        var currentOptions = _optionsMonitor.CurrentValue;

        if (!currentOptions.Enabled || !HttpMethods.IsPost(context.Request.Method))
        {
            await _next(context);
            return;
        }

        // Aktifkan buffering jika middleware downstream (seperti controller model binder) 
        // tetap membutuhkan Request.Body Stream asli untuk dibaca ulang.
        context.Request.EnableBuffering();

        var pipeReader = context.Request.BodyReader;
        string computedHash = await ComputeSha256FromPipeReaderAsync(pipeReader, currentOptions.MaxInspectPayloadBytes, context.RequestAborted);

        // Reset stream position ke 0 agar downstream components dapat membaca body tanpa terhambat
        context.Request.Body.Position = 0;

        await auditStorage.RecordPayloadHashAsync(context.Request.Path, computedHash, context.RequestAborted);

        await _next(context);
    }

    private static async Task<string> ComputeSha256FromPipeReaderAsync(PipeReader reader, int maxBytes, CancellationToken ct)
    {
        using var incrementalHash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        long totalBytesRead = 0;

        while (true)
        {
            ReadResult result = await reader.ReadAsync(ct);
            ReadOnlySequence<byte> buffer = result.Buffer;

            try
            {
                if (buffer.IsEmpty && result.IsCompleted)
                {
                    break;
                }

                foreach (ReadOnlyMemory<byte> segment in buffer)
                {
                    int bytesToProcess = segment.Length;
                    if (totalBytesRead + bytesToProcess > maxBytes)
                    {
                        bytesToProcess = (int)(maxBytes - totalBytesRead);
                    }

                    incrementalHash.AppendData(segment.Span[..bytesToProcess]);
                    totalBytesRead += bytesToProcess;

                    if (totalBytesRead >= maxBytes)
                    {
                        break;
                    }
                }
            }
            finally
            {
                // Wajib menginformasikan PipeReader sejauh mana data telah diperiksa (examined)
                // dan sejauh mana data telah dikonsumsi (consumed).
                // Kita gunakan buffer.Start agar Kestrel TIDAK membuang isi stream body,
                // sehingga dapat dibaca kembali oleh MVC Model Binding downstream.
                reader.AdvanceTo(buffer.Start, buffer.End);
            }

            if (result.IsCompleted || totalBytesRead >= maxBytes)
            {
                break;
            }
        }

        byte[] finalHash = incrementalHash.GetHashAndReset();
        return Convert.ToHexString(finalHash);
    }
}
```

```csharp
// Program.cs - Pendaftaran Dependensi Terstruktur
using Enterprise.Core.Architecture.Middleware;

var builder = WebApplication.CreateBuilder(args);

// Konfigurasi Options Monitor
builder.Services.Configure<AuditorOptions>(
    builder.Configuration.GetSection(AuditorOptions.SectionName));

// Pendaftaran scoped dependency untuk auditing
builder.Services.AddScoped<IAuditStorageService, DatabaseAuditStorageService>();

// Registrasi .NET 8 Keyed Services untuk demonstrasi multi-tenant/multi-strategy engine
builder.Services.AddKeyedSingleton<IValidatorStrategy, StrictValidatorStrategy>("Strict");
builder.Services.AddKeyedSingleton<IValidatorStrategy, PermissiveValidatorStrategy>("Permissive");

var app = builder.Build();

// Pipeline Registration
app.UseMiddleware<PayloadAuditorMiddleware>();

app.MapPost("/api/v1/payments", (PaymentRequest payload, [FromKeyedServices("Strict")] IValidatorStrategy validator) =>
{
    validator.Validate();
    return Results.Ok(new { Status = "Accepted", TransactionId = Guid.NewGuid() });
});

app.Run();

// Kontrak Pembantu
public interface IValidatorStrategy { void Validate(); }
public sealed class StrictValidatorStrategy : IValidatorStrategy { public void Validate() => Console.WriteLine("Strict Execution"); }
public sealed class PermissiveValidatorStrategy : IValidatorStrategy { public void Validate() => Console.WriteLine("Permissive Execution"); }
public sealed record PaymentRequest(decimal Amount, string RecipientIban);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks
Sebuah institusi switching perbankan memproses 120.000 Request Per Second (RPS) pada gateway otorisasi transaksi. Setiap request berisi payload ISO-8583 dalam format JSON/Binary.

#### Masalah Produksi
Saat beban transaksi memuncak:
1. **GC Spikes**: Server mengalami CPU Spike hingga 100% dan latency p99.9 membengkak dari 15ms menjadi 4.5 detik.
2. **LOH Fragmentation**: Analisis dump memori menunjukkan jutaan instans `byte[]` dan `MemoryStream` berukuran 90 KB teralokasi di LOH saat membaca payload, memicu *Full GC (Gen 2 Blocking)* secara berkala.
3. **Thread Pool Exhaustion**: Implementasi middleware lama menggunakan synchronous read: `new StreamReader(context.Request.Body).ReadToEnd()`. Ini memicu *Sync-over-Async*, menghabiskan worker thread pada ThreadPool dalam hitungan detik.

#### Solusi Arsitektural
1. Mengganti penggunaan `StreamReader` dengan `PipeReader` berbasis `System.IO.Pipelines` dan `ReadOnlySequence<byte>`.
2. Menggunakan `ArrayPool<byte>.Shared` atau memori internal pipeline untuk mencegah alokasi objek heap baru pada setiap request.
3. Mengonfigurasi batas ThreadPool minimum sesuai core CPU bare-metal (`ThreadPool.SetMinThreads`).
4. Mengaudit seluruh pipeline dependensi untuk menyingkirkan *Captive Dependencies* dengan mengaktifkan opsi `ValidateScopes = true` dan `ValidateOnBuild = true` pada DI ServiceProvider.

#### Metrik Dampak
* Latency p99.9 turun dari **4.500 ms** menjadi **12 ms**.
* Alokasi memori GC berkurang sebesar **87%**.
* Gen 2 GC Collections turun dari 45 kali/menit menjadi 0 kali/jam pada beban puncak.
* Kapasitas throughput meningkat 3.2x lipat pada infrastruktur komputasi yang identik.

---

### 9. Trade-offs

```
                  ARSITEKTUR PIPELINE STREAMING
                                ▲
                                │
                 Zero-Allocation (Pipelines)
                 - Latency sangat rendah
                 - Penggunaan memori minimal
                 - Kompleksitas kode tinggi
                                │
                                │
                                ┼────────────────────────►
                                │    Classic Stream Buffering
                                │    - Developer experience tinggi (mudah)
                                │    - High GC Pressure & LOH Risk
                                │    - Latency buruk pada beban tinggi
                                │
```

| Parameter Arsitektur | Low-Level `System.IO.Pipelines` | Standar ASP.NET Core `Stream/ModelBinder` |
| :--- | :--- | :--- |
| **Throughput & Allocations** | **Tinggi (Zero-Copy)**. Tidak ada duplikasi memori antar transport dan parsing logic. | **Sedang - Rendah**. Memerlukan deserializer serializer yang sering mengalokasikan string/buffer per request. |
| **Complexity & Maintainability** | **Sangat Kompleks**. Wajib mengelola pointer `SequencePosition`, `AdvanceTo`, penanganan partial buffer, dan status slice. | **Rendah**. Logika deklaratif menggunakan `[FromBody]` dan atribut validasi standar. |
| **DI Lifecycle: Singleton vs Scoped** | **Singleton**: Sangat cepat, resolusi *call site* tunggal, rentan data race jika memiliki state. | **Scoped**: Aman untuk data per-request, namun memicu overhead alokasi `ServiceScope` dan tracking `IDisposable`. |
| **Options: Monitor vs Snapshot** | **IOptionsMonitor**: Real-time reload via event token, thread-safe overhead kecil, Singleton friendly. | **IOptionsSnapshot**: Terisolasi per request (Scoped), alokasi objek baru per HttpContext, tidak bisa diinjeksi ke Singleton. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal 1: Captive Dependency (Scoped didalam Singleton)
```csharp
// FATAL ANTI-PATTERN
public sealed class SecurityTokenCache // Didaftarkan sebagai Singleton
{
    private readonly ApplicationDbContext _dbContext; // DbContext adalah SCOPED!

    public SecurityTokenCache(ApplicationDbContext dbContext)
    {
        _dbContext = dbContext; // Captive Dependency! Context tidak akan pernah ter-dispose.
    }
}
```
*Dampak*: Kebocoran memori (cache query EF Core membesar selamanya), thread safety violation saat request dieksekusi secara simultan.  
*Solusi*: Gunakan `IServiceScopeFactory` di dalam Singleton untuk membuat batasan scope manual ketika mutlak dibutuhkan:
```csharp
public sealed class SecurityTokenCache
{
    private readonly IServiceScopeFactory _scopeFactory;

    public SecurityTokenCache(IServiceScopeFactory scopeFactory)
    {
        _scopeFactory = scopeFactory;
    }

    public async Task ProcessAsync()
    {
        using var scope = _scopeFactory.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        await dbContext.PerformOperationAsync();
    }
}
```

#### Kesalahan Fatal 2: Sync-over-Async pada Middleware
```csharp
// FATAL ANTI-PATTERN
public class BlockingMiddleware
{
    private readonly RequestDelegate _next;
    public BlockingMiddleware(RequestDelegate next) => _next = next;

    public async Task InvokeAsync(HttpContext context, IRemoteRuleService ruleService)
    {
        // Thread pool starvation instan di bawah beban 500+ koneksi konkuren
        var isAllowed = ruleService.CheckRuleAsync(context.Request.Path).Result; 
        if (!isAllowed)
        {
            context.Response.StatusCode = 403;
            return;
        }
        await _next(context);
    }
}
```
*Dampak*: Thread Worker di-blokir menunggu I/O selesai. Kestrel kehabisan thread untuk memproses request baru, memicu *HTTP 503* atau *connection timeouts*.  
*Solusi*: Wajib gunakan `await ruleService.CheckRuleAsync(context.Request.Path)`. Jangan pernah gunakan `.Result`, `.Wait()`, atau `Task.Run().Wait()`.

#### Kesalahan Fatal 3: Kegagalan Pengelolaan PipeReader (`AdvanceTo` Leak)
Jika memanggil `PipeReader.ReadAsync()`, Anda **wajib** memanggil `PipeReader.AdvanceTo()`. Jika Anda lupa memanggil `AdvanceTo`, Kestrel akan mengalami *deadlock* internal pada request tersebut karena loop I/O menganggap buffer belum siap dibebaskan.

#### Panduan Troubleshooting Diagnostik Produksi
1. **Mendeteksi ThreadPool Starvation**:
   Jalankan command line tool `dotnet-counters`:
   ```bash
   dotnet-counters monitor -p <PID> --counters System.Runtime
   ```
   Perhatikan metrik `ThreadPool Worker Thread Count` dan `ThreadPool Queue Length`. Jika `Queue Length` meningkat tajam sementara `CPU Usage` rendah, aplikasi Anda mengalami starvation akibat blocking calls (*Sync-over-Async*).
2. **Memeriksa Scope Leaks & Captive Dependencies secara Otomatis**:
   Pastikan pada `Program.cs` konfigurasi environment development/staging menyertakan validasi ketat:
   ```csharp
   builder.Host.UseDefaultServiceProvider((context, options) =>
   {
       options.ValidateScopes = true;
       options.ValidateOnBuild = true;
   });
   ```

---

### 11. Best Practices (Production Checklist)

| Kategori | Aturan Rekayasa | Alasan Teknis |
| :--- | :--- | :--- |
| **Kestrel Tuning** | Atur `Limits.MaxConcurrentConnections` & `Limits.MaxRequestBodySize` secara eksplisit. | Mencegah serangan *Denial of Service* (DoS) berbasis Slowloris atau memori exhaustion. |
| **Pipelines** | Selalu panggil `reader.AdvanceTo(consumed, examined)` dalam blok `finally`. | Mencegah memory retention pada pool Kestrel dan menghindari kebocoran kapasitas buffer. |
| **DI Architecture** | Aktifkan `ValidateScopes` dan `ValidateOnBuild` di pipeline CI/CD integration tests. | Mencegah captive dependency lolos ke lingkungan staging dan produksi. |
| **Logging I/O** | Hindari membaca `Request.Body` langsung ke string untuk logging di request path utama. | Alokasi string besar memicu tekanan Gen 0/1 GC berlebihan dan degradasi throughput. |
| **Options Pattern** | Gunakan `IOptionsMonitor<T>` untuk konfigurasi yang membutuhkan live reload, hindari polling manual. | Memanfaatkan event token native Windows/Linux OS file change system secara efisien. |
| **Async Discipline** | Terapkan parameter `CancellationToken context.RequestAborted` ke seluruh operasi async downstream. | Menghentikan eksekusi thread dan query database secara instan jika client memutuskan koneksi TCP. |

---

### 12. Hands-on Practice

Buat dan uji implementasi pipeline berkinerja tinggi lengkap dengan custom factory-based middleware dan keyed DI services.

#### Struktur Direktori
```
hands-on/m02/
├── EnterprisePipeline.sln
└── src/
    └── EnterpriseApi/
        ├── EnterpriseApi.csproj
        ├── Program.cs
        ├── appsettings.json
        ├── Middlewares/
        │   └── PerformanceTrackingMiddleware.cs
        ├── Services/
        │   ├── IEngineWorker.cs
        │   └── ProcessingEngines.cs
        └── Options/
            └── RuntimeLimitsOptions.cs
```

#### Langkah-langkah Pembuatan

##### 1. Inisialisasi Proyek
```bash
mkdir -p hands-on/m02/src/EnterpriseApi
cd hands-on/m02/src/EnterpriseApi
dotnet new web
```

##### 2. Konfigurasi `EnterpriseApi.csproj`
Pastikan file proyek menggunakan .NET 8 dengan optimasi kompilasi:
```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <ServerGarbageCollection>true</ServerGarbageCollection>
  </PropertyGroup>
</Project>
```

##### 3. Definisi Options (`Options/RuntimeLimitsOptions.cs`)
```csharp
namespace EnterpriseApi.Options;

public sealed class RuntimeLimitsOptions
{
    public const string Section = "RuntimeLimits";
    public int MaxAllowedBatchItems { get; set; } = 100;
    public bool EnableDeepDiagnostics { get; set; } = true;
}
```

##### 4. Definisi Keyed Engine (`Services/IEngineWorker.cs` & `Services/ProcessingEngines.cs`)
```csharp
namespace EnterpriseApi.Services;

public interface IEngineWorker
{
    string ProcessTransaction(string traceId, int itemsCount);
}

public sealed class StandardEngineWorker : IEngineWorker
{
    public string ProcessTransaction(string traceId, int itemsCount) =>
        $"[STANDARD-ENGINE] Trace: {traceId} processed {itemsCount} items successfully.";
}

public sealed class PriorityEngineWorker : IEngineWorker
{
    public string ProcessTransaction(string traceId, int itemsCount) =>
        $"[PRIORITY-HIGH-ENGINE] Trace: {traceId} VIP priority routing applied for {itemsCount} items.";
}
```

##### 5. Factory-based Middleware (`Middlewares/PerformanceTrackingMiddleware.cs`)
```csharp
namespace EnterpriseApi.Middlewares;

using System.Diagnostics;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

public sealed class PerformanceTrackingMiddleware : IMiddleware
{
    private readonly ILogger<PerformanceTrackingMiddleware> _logger;

    public PerformanceTrackingMiddleware(ILogger<PerformanceTrackingMiddleware> logger)
    {
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        var startTimestamp = Stopwatch.GetTimestamp();
        
        // Pasang correlation ID jika belum ada
        if (!context.Request.Headers.TryGetValue("X-Trace-Id", out var traceId))
        {
            traceId = Guid.NewGuid().ToString("N");
            context.Request.Headers["X-Trace-Id"] = traceId;
        }
        
        context.Response.Headers["X-Trace-Id"] = traceId;

        await next(context);

        var elapsedMs = Stopwatch.GetElapsedTime(startTimestamp).TotalMilliseconds;
        
        _logger.LogInformation("Request {TraceId} ({Method} {Path}) finalized in {Elapsed:F4} ms. Status: {StatusCode}",
            traceId, context.Request.Method, context.Request.Path, elapsedMs, context.Response.StatusCode);
    }
}
```

##### 6. Perbarui `appsettings.json`
```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "RuntimeLimits": {
    "MaxAllowedBatchItems": 250,
    "EnableDeepDiagnostics": true
  },
  "AllowedHosts": "*"
}
```

##### 7. Wiring Engine di `Program.cs`
```csharp
using EnterpriseApi.Middlewares;
using EnterpriseApi.Options;
using EnterpriseApi.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

// Validasi Scope Ketat
builder.Host.UseDefaultServiceProvider(opts =>
{
    opts.ValidateScopes = true;
    opts.ValidateOnBuild = true;
});

// Options Pattern
builder.Services.Configure<RuntimeLimitsOptions>(
    builder.Configuration.GetSection(RuntimeLimitsOptions.Section));

// Registrasi Factory Middleware (Wajib didaftarkan ke DI)
builder.Services.AddTransient<PerformanceTrackingMiddleware>();

// Keyed Services Registration
builder.Services.AddKeyedSingleton<IEngineWorker, StandardEngineWorker>("standard");
builder.Services.AddKeyedSingleton<IEngineWorker, PriorityEngineWorker>("vip");

var app = builder.Build();

// Eksekusi Factory-Based Middleware
app.UseMiddleware<PerformanceTrackingMiddleware>();

app.MapPost("/process", (
    [FromQuery] string tier,
    [FromQuery] int count,
    [FromServices] IServiceProvider sp,
    [FromServices] IOptionsMonitor<RuntimeLimitsOptions> limits) =>
{
    var currentLimit = limits.CurrentValue.MaxAllowedBatchItems;
    if (count > currentLimit)
    {
        return Results.BadRequest(new { Error = $"Count exceeds maximum allowed: {currentLimit}" });
    }

    var worker = tier.ToLowerInvariant() switch
    {
        "vip" => sp.GetRequiredKeyedService<IEngineWorker>("vip"),
        _ => sp.GetRequiredKeyedService<IEngineWorker>("standard")
    };

    var traceId = app.Lifetime.ApplicationStopping.IsCancellationRequested 
        ? "SHUTTING_DOWN" 
        : Guid.NewGuid().ToString("N");

    var result = worker.ProcessTransaction(traceId, count);
    return Results.Ok(new { Response = result });
});

app.Run();
```

##### 8. Pengujian dan Verifikasi
Jalankan aplikasi dari terminal:
```bash
dotnet run
```
Kirim request HTTP via `curl`:
```bash
curl -i -X POST "http://localhost:5000/process?tier=vip&count=50" -H "X-Trace-Id: MANUAL-TRACE-99"
```
Verifikasi bahwa header response mengandung `X-Trace-Id`, dan log terminal mencatat latency dalam hitungan fraksi milidetik tanpa kebocoran alokasi.

---

### 13. Exercise

#### Level 1 - Easy
1. Modifikasi `PerformanceTrackingMiddleware` agar menambahkan header response `X-Server-Processing-Ticks` yang berisi total tick sistem selama middleware downstream bekerja.
2. Daftarkan service `GuidGenerator` bertipe *Transient*, lalu injeksikan ke dalam endpoint Minimal API. Verifikasi bahwa setiap request menghasilkan UUID baru.

#### Level 2 - Medium
1. Ubah middleware convention-based biasa agar mampu membaca konfigurasi via `IOptionsSnapshot<T>`. Perhatikan di mana Anda menginjeksinya (konstruktor vs metode `InvokeAsync`). Buktikan mengapa injeksi via konstruktor memicu error jika menggunakan `IOptionsSnapshot`.
2. Implementasikan middleware yang menolak request (Short-Circuit) dengan status code `413 Payload Too Large` jika header `Content-Length` melebihi nilai yang ditentukan pada `RuntimeLimitsOptions`.

#### Level 3 - Hard
1. Buat custom middleware yang membaca seluruh isi payload stream, namun menerapkan limit proteksi berbasis `ReadOnlySequence<byte>`: jika payload lebih dari 64 KB, hentikan pembacaan segera, putuskan koneksi (`context.Abort()`), dan jangan sampai mengalokasikan string atau array baru ke heap. Pastikan pointer advance reader dikelola dengan benar tanpa meninggalkan *hanging buffers*.

---

### 14. Challenge

**Skenario Rekayasa Lanjutan**:  
Anda diminta merancang arsitektur **Zero-Allocation Reverse Proxy Gateway Pipeline** internal untuk microservices streaming data sensor bervolume tinggi.

**Spesifikasi Tantangan**:
1. Buat custom terminal middleware yang mem-proxy request `POST /telemetry/stream` langsung ke backend mock socket tanpa melalui layer Controller/Minimal API serialization.
2. Gunakan `context.Request.BodyReader` dan `context.Response.BodyWriter` secara tandem. Salin payload request secara streaming menggunakan buffer berukuran 4 KB yang dipinjam dari `ArrayPool<byte>.Shared` atau `MemoryPool<byte>.Shared`.
3. Terapkan algoritma backpressure: jika downstream writer mendeteksi status pending (`PipeWriter.FlushAsync()` menghasilkan status incomplete), reader harus menunda pembacaan socket hulu untuk mencegah lonjakan memori RAM.
4. **Batasan Mutlak**: 
   * Dilarang menggunakan alokasi `new byte[]`, `MemoryStream`, atau pemanggilan `.ToString()` pada body data.
   * Tingkat alokasi heap Gen 0 untuk request streaming berukuran 10 MB harus tercatat sebesar **0 byte** pada profiling memory profiler (di luar objek framework `DefaultHttpContext`).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. **Apa tipe data delegasi dasar dari rantai middleware pipeline di ASP.NET Core?**
   * A. `Action<HttpContext>`
   * B. `Func<HttpContext, Task<bool>>`
   * C. `RequestDelegate` yang merepresentasikan `Func<HttpContext, Task>`
   * D. `EventHandler<HttpContextEventArgs>`
2. **Kapan instance dari middleware berbasis konvensi (*Convention-based Middleware*) diinstansiasi oleh Kestrel?**
   * A. Sekali pada saat startup/pembentukan pipeline application builder (*Singleton-like lifecycle*).
   * B. Diinstansiasi ulang pada setiap request masuk.
   * C. Diinstansiasi setiap kali ada GC Gen 2 collection.
   * D. Hanya jika ada controller yang memanggilnya.
3. **Mengapa `IOptionsSnapshot<T>` tidak dapat diinjeksi ke dalam konstruktor sebuah service Singleton?**
   * A. Karena `IOptionsSnapshot<T>` hanya mendukung data format XML.
   * B. Karena `IOptionsSnapshot<T>` memiliki lifetime Scoped, yang jika diinjeksi ke Singleton akan menjadi Captive Dependency.
   * C. Karena `IOptionsSnapshot<T>` memerlukan koneksi database aktif.
   * D. Karena Singleton tidak memiliki akses ke `IConfiguration`.
4. **Apa yang terjadi jika middleware Anda tidak memanggil `await next(context)`?**
   * A. Runtime akan melempar exception `NullReferenceException`.
   * B. Request mengalami short-circuit; pipeline downstream tidak dieksekusi dan flow langsung kembali ke middleware upstream.
   * C. Kestrel server crash secara instan.
   * D. Request akan dialihkan ke route fallback `/error`.
5. **Apa fungsi dari `context.Request.EnableBuffering()`?**
   * A. Mengompresi request body menggunakan algoritma GZIP.
   * B. Mengalihkan request stream body agar disimpan sementara di disk/memori sehingga dapat di-seek (`Position = 0`) dan dibaca lebih dari satu kali.
   * C. Mengalokasikan LOH memory buffer instan.
   * D. Mematikan thread pool synchronization.

#### 5 Pertanyaan Intermediate
6. **Pada arsitektur `System.IO.Pipelines`, apa konsekuensi teknis jika developer memanggil `PipeReader.AdvanceTo(buffer.Start, buffer.Start)` tanpa pernah memajukan posisi consumed?**
   * A. Data langsung terhapus dari RAM.
   * B. Data yang sama akan terus terbaca pada pemanggilan `ReadAsync()` berikutnya, berpotensi memicu infinite loop CPU 100%.
   * C. Socket koneksi TCP otomatis ditutup oleh OS.
   * D. Memory pool langsung membuang koneksi tersebut.
7. **Dalam kondisi apa sebuah `Scoped` service dapat bertindak seolah-olah menjadi `Singleton` tanpa memicu compile-time error?**
   * A. Jika didaftarkan sebelum pemanggilan `builder.Build()`.
   * B. Ketika diinjeksi ke dalam konstruktor Middleware Convention-Based tanpa validasi scope diaktifkan.
   * C. Jika service tersebut mengimplementasikan `IDisposable`.
   * D. Jika service diakses di dalam endpoint Minimal API.
8. **Bagaimana mekanisme internal .NET 8 Keyed Services menyelesaikan dependensi yang berbeda untuk satu interface yang sama?**
   * A. Menggunakan string matching via dynamic reflection pada setiap pemanggilan method.
   * B. Menggunakan struktur lookup internal dictionary berbasis pasangan `(Type, ServiceKey)` langsung pada service call site resolution engine.
   * C. Membuat instans baru dari seluruh service yang terdaftar lalu membuang yang tidak cocok.
   * D. Mengakses cache database redis internal.
9. **Apa perbedaan mendasar antara `reader.AdvanceTo(buffer.End)` dan `reader.AdvanceTo(buffer.Start, buffer.End)`?**
   * A. Keduanya identik dalam segala aspek.
   * B. Versi pertama menandai seluruh buffer telah dikonsumsi dan dapat ditimpa; versi kedua menyatakan data telah diperiksa (*examined*) hingga akhir namun belum dikonsumsi (*consumed*).
   * C. Versi kedua menyebabkan deadlock soket seketika.
   * D. Versi pertama mengalokasikan Large Object Heap.
10. **Apa dampak langsung dari fenomena *Sync-over-Async* (seperti memanggil `.GetAwaiter().GetResult()`) pada performa Kestrel di lingkungan throughput tinggi?**
    * A. Latency berkurang drastis karena task langsung dieksekusi inline.
    * B. Alokasi memori GC berkurang menjadi nol.
    * C. Thread Pool Starvation: Worker threads terkunci dalam status sleep/wait, mencegah Kestrel memproses socket connection baru.
    * D. CPU context switching otomatis dinonaktifkan oleh runtime.

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus 1**:
    Tim Anda merilis fitur baru yang menggunakan `IOptionsMonitor<DatabaseSettings>`. Namun, saat file `appsettings.json` diubah di server produksi Kubernetes, konfigurasi pada service worker Anda tidak pernah ter-update secara otomatis tanpa me-restart Pod. Padahal kode sudah menggunakan `IOptionsMonitor`. 
    *Apa akar masalah arsitektural yang paling mungkin di lingkungan Linux Container/Kubernetes?*
    * A. Kubernetes `ConfigMap` yang di-mount sebagai symlink tidak selalu memicu inotify file change notification standard Linux jika file watcher .NET hanya mengawasi physical inode aslinya.
    * B. `IOptionsMonitor` tidak kompatibel dengan file format JSON.
    * C. Kubernetes otomatis mematikan thread pool Kestrel.
    * D. CancellationToken internal `IOptionsMonitor` selalu ter-cancel otomatis di sistem operasi non-Windows.
12. **Skenario Kasus 2**:
    Sebuah aplikasi ASP.NET Core mengalami lonjakan konsumsi memori stabil (tidak pernah turun) hingga mencapai 8 GB setelah berjalan selama 3 hari, meskipun traffic sedang rendah. Saat dianalisis menggunakan `dotnet-dump`, ditemukan jutaan objek instance Entity Framework `DbContext` masih berada di memory heap Gen 2.
    *Investigasi arsitektur mana yang paling valid untuk menemukan bug tersebut?*
    * A. Kestrel MemoryPool mengalami memory leak internal pada buffer soket TCP.
    * B. Terdapat service `Singleton` yang menginjeksi `DbContext` langsung via konstruktor (Captive Dependency), atau ada background task singleton yang membuat `IServiceScope` namun tidak memanggil `.Dispose()` pada scope tersebut.
    * C. Logging console diaktifkan pada level `Trace`.
    * D. Aplikasi menggunakan HTTP/2 dan bukannya HTTP/1.1.
13. **Skenario Kasus 3**:
    Sebuah payment gateway service memproses upload file mutasi rekening batch (payload 50 MB per request). Sesaat setelah traffic naik, server mengalami freeze berkala selama 2 hingga 4 detik di mana seluruh request lain tertahan (*p99 degradation*). Diagnostic tool menunjukkan CPU 100% pada *GC Pause Type: Non-Concurrent / Gen 2*.
    *Apa perbaikan arsitektur tercepat dan paling efisien untuk masalah ini?*
    * A. Meningkatkan core CPU server menjadi dua kali lipat.
    * B. Menghentikan pembacaan body via `MemoryStream` / model binding array byte yang mengalokasikan buffer di Large Object Heap (LOH); beralih ke pembacaan disk berbasis streaming chunking (`PipeReader` atau file streaming langsung ke temporary file).
    * C. Mengubah seluruh service dari Scoped menjadi Transient.
    * D. Mematikan fitur Kestrel socket multiplexing.

---

### Kunci Jawaban & Evaluasi

#### Pertanyaan Basic
1. **C**: `RequestDelegate` didefinisikan secara resmi sebagai `delegate Task RequestDelegate(HttpContext context)`.
2. **A**: Convention-based middleware dikompilasi ke dalam delegasi pohon middleware sekali saja saat aplikasi melakukan build pipeline di startup.
3. **B**: `IOptionsSnapshot<T>` didesain dengan siklus hidup Scoped. Menaruh Scoped dependency di dalam Singleton memicu Captive Dependency.
4. **B**: Tidak mengeksekusi `await next(context)` berarti memutus rantai pipeline (short-circuiting), sehingga request langsung berbalik ke upstream middleware.
5. **B**: `EnableBuffering()` mengizinkan stream pembacaan body Kestrel dibaca berulang kali dengan cara menyalin aliran stream ke memori/file sementara jika penunjuk stream digeser kembali ke `Position = 0`.

#### Pertanyaan Intermediate
6. **B**: Jika posisi `consumed` tidak pernah dimajukan, Kestrel menganggap data tersebut belum diproses dan akan mengembalikan paket byte yang sama pada pemanggilan `ReadAsync()` berikutnya, mengakibatkan perulangan tak berujung (infinite read loop).
7. **B**: Middleware berbasis konvensi adalah Singleton defakto. Jika dependensi Scoped dimasukkan ke dalam konstruktornya (dan validasi scope dinonaktifkan), instance scoped tersebut akan terikat selamanya pada singleton middleware tersebut.
8. **B**: .NET 8 Keyed Services menggunakan call site mapping berbasis kunci registrasi pada container engine tanpa overhead pemindaian refleksi dinamis yang lambat pada saat request runtime.
9. **B**: `AdvanceTo(buffer.End)` mengonsumsi seluruh rentang byte (membebaskannya dari pool). `AdvanceTo(buffer.Start, buffer.End)` menandai bahwa data telah dibaca hingga akhir untuk keperluan inspeksi/pencarian, namun belum dikonsumsi sehingga tetap ada di buffer untuk pembacaan berikutnya.
10. **C**: Memblokir thread async secara sinkronus (*Sync-over-Async*) menguras ketersediaan thread di ThreadPool, mengakibatkan request-request baru antre di queue tanpa ada thread yang tersedia untuk mengeksekusinya.

#### Skenario Kasus Produksi
11. **A**: Pada Linux/Kubernetes, update ConfigMap sering menggunakan atomic symlink swap. File provider .NET terkadang memerlukan penanganan khusus atau path mount yang tepat agar file change event (`INotify`) terpantau secara konsisten.
12. **B**: Objek yang tidak pernah ter-dispose dan terus menumpuk di memori heap Gen 2 biasanya terikat pada referensi root hidup, seperti Singleton atau un-disposed Scope context.
13. **B**: Alokasi payload 50 MB langsung mendarat di Large Object Heap (> 85.000 byte), yang hanya bisa dibersihkan melalui Gen 2 Full GC. Full GC Gen 2 memblokir seluruh eksekusi thread runtime (*Stop-the-World pause*). Streaming chunking memecah konsumsi ke dalam buffer kecil yang tidak membebani LOH.

---

### 16. Summary

```
+───────────────────────────────────────────────────────────────────────────────+
|                 RINGKASAN ARSITEKTUR TINGKAT TINGGI ASP.NET CORE              |
+───────────────────────────────────────────────────────────────────────────────+
| 1. KESTREL & PIPELINES                                                        |
|    - Menggunakan MemoryPool<byte> untuk menghindari alokasi GC Small/Large    |
|      Object Heap.                                                             |
|    - System.IO.Pipelines mengabstraksikan socket loop dengan backpressure     |
|      dan zero-copy sequence parsing.                                          |
|                                                                               |
| 2. MIDDLEWARE COMPILATION                                                     |
|    - Convention-Based: Cepat, Singleton-by-default, Scoped via InvokeAsync(). |
|    - Factory-Based (IMiddleware): Scoped-friendly, resolusi dependensi        |
|      eksplisit per-request via DI container.                                  |
|                                                                               |
| 3. DEPENDENCY INJECTION DISCIPLINE                                            |
|    - Singleton mengikat dependensi selamanya.                                 |
|    - Captive Dependencies merusak isolasi tenant, konkurensi, dan memicu      |
|      memory leak Gen 2.                                                       |
|    - Wajib aktifkan ValidateScopes dan ValidateOnBuild di semua CI pipeline.  |
|                                                                               |
| 4. PRODUCTION TUNING & DIAGNOSTICS                                            |
|    - Tolak Sync-over-Async (.Result / .Wait()) untuk mencegah ThreadPool      |
|      Starvation.                                                              |
|    - Pantau runtime metrics secara periodik menggunakan dotnet-counters       |
|      dan dotnet-dump.                                                         |
+───────────────────────────────────────────────────────────────────────────────+
```