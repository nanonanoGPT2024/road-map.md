# BAB 02: Dependency Injection & Configuration Deep Dive
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Internal IoC Container .NET**: Menguasai siklus hidup *CallSite*, *ServiceLookup Engine*, strategi kompilasi runtime (*DynamicMethod/IL Emit* vs *Runtime Reflection*), serta mekanisme pelacakan *GC Root* pada objek yang di-*resolve*.
2. **Mendeteksi dan Memitigasi Anti-Pattern Tingkat Lanjut**: Mengidentifikasi *Captive Dependencies*, kebocoran memori akibat *Transient IDisposable*, serta *thread-safety lock contention* pada *singleton factory* sebelum kode mencapai fase staging.
3. **Menguasai Keyed Services dan Dynamic Assembly Scanning**: Mengimplementasikan injeksi dependensi bersyarat menggunakan fitur native .NET 8/9 *Keyed Services* dan mengotomatisasi registrasi modular menggunakan *Scrutor*.
4. **Membangun Custom Configuration Provider yang Resilien**: Mengembangkan provider konfigurasi kustom berbasis *event-driven push model* atau polling dengan memanfaatkan `IChangeToken` dan integrasi *secrets engine* eksternal.
5. **Menerapkan Options Pattern Tingkat Enterprise**: Mengonfigurasi `IOptions<T>`, `IOptionsSnapshot<T>`, dan `IOptionsMonitor<T>` secara tepat guna dengan validasi skema berbasis *Data Annotations* dan *Fluent Validation*, serta memanfaatkan `ValidateOnStart()` untuk skenario *fail-fast deployment*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **C# Tingkat Lanjut**: Pemahaman mendalam tentang *Reflection*, *Expression Trees*, *Memory Allocation* (Stack vs Heap), delegasi, generics tingkat lanjut (*covariance/contravariance*), dan pola `IDisposable`/`IAsyncDisposable`.
*   **.NET Garbage Collection Internals**: Pemahaman tentang Gen 0, Gen 1, Gen 2, *Large Object Heap* (LOH), dan bagaimana relasi antar objek mempertahankan *GC Root* aktif.
*   **Asynchronous Programming**: Penanganan konkurensi, `ValueTask`, `TaskCompletionSource`, pembatalan via `CancellationToken`, dan bahaya *sync-over-async*.
*   **Dasar ASP.NET Core**: Memahami konsep *Middleware pipeline*, `WebApplicationBuilder`, dan siklus hidup HTTP Request di Kestrel.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal ServiceProvider Engine & ServiceLookup

Di balik abstraksi `IServiceProvider`, library `Microsoft.Extensions.DependencyInjection` (MS.DI) menggunakan arsitektur modular untuk mengubah deskriptor dependensi (`ServiceDescriptor`) menjadi graf objek fungsional berkinerja tinggi.

```
+-------------------------------------------------------------------------------+
|                             WebApplicationBuilder                             |
|  builder.Services.AddScoped<IOrderService, OrderService>();                   |
+-------------------------------------------------------------------------------+
                                      |
                                      v BuildServiceProvider()
+-------------------------------------------------------------------------------+
|                            ServiceProviderEngine                              |
|                                                                               |
|  +--------------------+    Lookup    +-------------------------------------+  |
|  |  CallSiteFactory   | -----------> | ServiceCallSite (Graph Definition)  |  |
|  +--------------------+              +-------------------------------------+  |
|                                                         |                     |
|            +--------------------------------------------+                     |
|            v                                            v                     |
|   [Development Mode]                           [Production Mode]              |
|   DynamicMethodEngine                          ILEmit / RuntimeEngine         |
|   - Generates IL via DynamicMethod             - Direct Reflection or         |
|   - Fast startup, high memory optimization       JIT-compiled Expression Tree |
+-------------------------------------------------------------------------------+
                                      |
                                      v Resolve Instance
+-------------------------------------------------------------------------------+
|                              Resolved Instance                                |
|  - Root Scope (Singleton Cache + Root Disposables)                            |
|  - Request Scope (Scoped Cache + Scoped Disposables)                          |
+-------------------------------------------------------------------------------+
```

1. **CallSiteFactory**: Saat dependensi diminta pertama kali via `GetService()` atau injeksi konstruktor, `CallSiteFactory` mengevaluasi dependensi secara rekursif dan menyusun pohon struktur internal bernama `ServiceCallSite`. Jenis-jenis CallSite meliputi:
   *   `ConstructorCallSite`: Merepresentasikan pemanggilan konstruktor dengan parameter yang harus di-*resolve*.
   *   `ConstantCallSite`: Merepresentasikan instance yang didaftarkan secara statis via `AddSingleton<T>(T instance)`.
   *   `ServiceProviderCallSite`: Mengembalikan pointer ke instance kontainer itu sendiri.
   *   `FactoryCallSite`: Merepresentasikan resolusi via delegasi `Func<IServiceProvider, object>`.

2. **ServiceProvider Engine Types**:
   *   `DynamicMethodServiceProviderEngine`: Menghasilkan bytecode CIL (Common Intermediate Language) secara dinamis menggunakan `DynamicMethod` untuk mengompilasi graf dependensi menjadi fungsi delegasi murni tanpa overhead pemanggilan refleksi berulang.
   *   `RuntimeServiceProviderEngine`: Menggunakan refleksi langsung (`ConstructorInfo.Invoke`). Umumnya hanya dipakai pada lingkungan yang melarang generasi IL dinamis (misal: platform AOT tertentu yang tidak mendukung JIT compilation secara penuh).

3. **Verifikasi Validasi Scope (*Scope Validation*)**:
   Ketika `ValidateScopes` diaktifkan (default pada environment `Development`), `CallSiteValidator` melakukan traversal pada seluruh graf `ServiceCallSite`. Jika dependensi berumur `Scoped` berada di dalam konstruktor dependensi `Singleton`, engine akan melempar exception:
   `InvalidOperationException: Cannot consume scoped service 'X' from singleton 'Y'.`

#### B. Kebocoran Memori Transient IDisposable

Salah satu jebakan terbesar pada MS.DI adalah penanganan objek `Transient` yang mengimplementasikan `IDisposable` atau `IAsyncDisposable`. Kontainer IoC ASP.NET Core mengadopsi prinsip: **"Siapa yang membuat, dia yang bertanggung jawab membuang."**

```
 [ Root ServiceProvider ]  -----------------------> [ Memory Leak Risk! ]
           |                                         Holds references to all
           |---> Resolves Transient IDisposable      Root-instantiated IDisposables
           |     (e.g., ExportReportService)         until App Domain shutdown!
           |
 [ Request Scope ] (HTTP Request Ends)
           |
           +---> Resolves Transient IDisposable
           |     (Disposed safely when Request Scope completes!)
```

Jika dependensi `Transient` mengimplementasikan `IDisposable`:
*   Jika di-*resolve* dari dalam HTTP Request Scope (`Scoped`), objek tersebut dicatat dalam list pelacakan disposal scope HTTP tersebut. Saat request selesai, HTTP context memicu `scope.Dispose()`, dan semua objek transient di dalamnya dibersihkan dari heap oleh GC.
*   Jika di-*resolve* langsung dari **Root Provider** (misal: di dalam background worker singleton, atau via `app.Services.GetRequiredService<T>()`), objek tersebut akan masuk ke dalam list pelacakan disposal internal Root Provider (`_disposables`). **Objek ini tidak akan pernah dilepas oleh Garbage Collector sampai aplikasi ASP.NET Core benar-benar berhenti (*shutdown*)**, memicu kebocoran memori (Memory Leak) bertipe Gen 2 starvation.

#### C. Internals Options Pattern: IOptions vs IOptionsSnapshot vs IOptionsMonitor

| Fitur | `IOptions<T>` | `IOptionsSnapshot<T>` | `IOptionsMonitor<T>` |
| :--- | :--- | :--- | :--- |
| **Lifetime** | Singleton | Scoped | Singleton |
| **Reload Support** | Tidak mendukung reload dinamis | Mendukung reload per HTTP request baru | Mendukung reload real-time (event-driven) |
| **Named Options** | Tidak (hanya `Options.DefaultName`) | Ya (`Get(name)`) | Ya (`Get(name)`) |
| **Overhead** | Minimum (di-cache sekali di root) | Alokasi per HTTP Request | Ringan via Thread-Safe Cache & Invalidation Token |
| **Konsistensi** | Konsisten statis sepanjang aplikasi hidup | Konsisten sepanjang satu siklus HTTP Request | Nilai selalu merefleksikan perubahan detik itu |
| **Mekanisme Reload** | N/A | Dihitung ulang saat Request Scope dibuat | Berlangganan ke `IChangeToken` internal |

---

### 4. Why & What

#### Mengapa Tidak Menggunakan Service Locator?
Service Locator (misal menginjeksi `IServiceProvider` langsung ke domain logic lalu memanggil `.GetService<T>()`) adalah anti-pattern enterprise karena:
*   **Mengaburkan Kontrak Dependensi**: Kelas menyembunyikan ketergantungannya di dalam implementasi metode, bukan mengeksposnya secara transparan melalui konstruktor.
*   **Mempersulit Unit Testing**: Pengujian unit mengharuskan penyusunan *mock provider* yang rumit alih-alih sekadar menyediakan mock interface langsung ke konstruktor.
*   **Risiko Runtime Exception**: Kegagalan resolusi baru terdeteksi saat jalur kode (*code path*) dieksekusi, mematikan kapabilitas *fail-fast* saat startup.

#### Mengapa Butuh Keyed Services (.NET 8+)?
Sebelum .NET 8, jika sistem memiliki implementasi ganda dari sebuah interface (misal: `IPaymentGateway` untuk Stripe, Adyen, dan PayPal), arsitek terpaksa menggunakan Factory Pattern manual berbasis `Func<string, IPaymentGateway>`, atau library pihak ketiga. Fitur native Keyed Services menyederhanakan resolusi dependensi dengan identifier unik langsung pada engine container, memangkas *boilerplate code* dan overhead alokasi memori.

---

### 5. How (Workflow Detail)

#### Resolusi Dependensi End-to-End pada ASP.NET Core
1. **Penerimaan Request**: Kestrel menerima koneksi TCP, memparsing HTTP frame, dan membuat `HttpContext`.
2. **Pembuatan Request Scope**: `IHttpActivityFeature` bersama middleware pipeline memanggil `IServiceScopeFactory.CreateScope()`.
3. **Penyusunan Kontroler**: `IControllerActivator` mengevaluasi konstruktor kontroler yang dipanggil.
4. **Traversal Dependensi**:
   *   Engine memeriksa apakah instance terdaftar sebagai `Singleton`. Jika ya, cari di Root Singleton Cache. Jika belum ada, lakukan instansiasi dengan *thread-safe lock*, simpan di cache, dan kembalikan.
   *   Engine memeriksa apakah instance `Scoped`. Jika ya, cari di Request Scope Cache. Jika belum, lakukan instansiasi dan daftarkan ke list disposal scope lokal.
   *   Jika instance `Transient`, buat baru. Jika kelas mengimplementasikan `IDisposable`, daftarkan referensinya ke disposal tracker scope pemanggil.
5. **Eksekusi Logika**: Request diproses melalui middleware dan action handler.
6. **Destruksi & Pembersihan**: Saat request berakhir, middleware pipeline mengeksekusi `scope.DisposeAsync()`.
7. **Pemicuan GC**: Semua referensi yang dipegang oleh scope dilepaskan dari GC root, memungkinkan memori dialokasikan ulang pada siklus Gen 0/1 berikutnya.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Skala Industri
*   **Root Container (Singleton)**: Dapur Pusat (Central Kitchen). Berdiri satu kali selama restoran beroperasi. Mesin penggiling utama berada di sini.
*   **Scoped Container (Scoped)**: Meja Tamu individual. Dibuat ketika tamu datang, dipakai sepanjang hidangan disajikan, dan dibersihkan total saat tamu membayar tagihan dan pergi.
*   **Transient**: Alat sekali pakai (seperti serbet kertas atau sedotan). Dibuat baru setiap kali ada yang meminta.
*   **Jebakan Captive Dependency**: Pelayan meja (Scoped) ditarik paksa menjadi bagian permanen dari Dapur Pusat (Singleton). Pelayan tersebut tidak pernah berganti pakaian, tidak pernah istirahat, dan membawa sisa makanan dari tamu pertama ke seluruh tamu berikutnya selama bertahun-tahun.

```
+-----------------------------------------------------------------------------+
|                            ROOT CONTAINER (Singleton)                       |
|  [Cache: IMetricsCollector, IDbConnectionFactory, IOptionsMonitorCache]     |
|                                                                             |
|      +---------------------------------------------------------------+      |
|      |               HTTP REQUEST 1 SCOPE (Thread Pool A)            |      |
|      |  [Cache: AppDbContext, IOrderRepository, IUnitOfWork]         |      |
|      |                                                               |      |
|      |  Creates: Transient Validator (Disposed at end of Request 1)  |      |
|      +---------------------------------------------------------------+      |
|                                                                             |
|      +---------------------------------------------------------------+      |
|      |               HTTP REQUEST 2 SCOPE (Thread Pool B)            |      |
|      |  [Cache: AppDbContext, IOrderRepository, IUnitOfWork]         |      |
|      +---------------------------------------------------------------+      |
|                                                                             |
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Injeksi Modern Menggunakan Keyed Services (.NET 8+)

```csharp
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

// Registrasi Keyed Services ke MS.DI Container
builder.Services.AddKeyedSingleton<IPaymentGateway, StripePaymentGateway>("stripe");
builder.Services.AddKeyedSingleton<IPaymentGateway, AdyenPaymentGateway>("adyen");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalPaymentGateway>("paypal");

builder.Services.AddScoped<CheckoutProcessor>();

var app = builder.Build();

app.MapPost("/checkout/{provider}", (
    [FromRoute] string provider,
    [FromBody] CheckoutRequest request,
    [FromServices] IServiceProvider sp) =>
{
    // Mengambil service secara dinamis berdasarkan key tanpa Service Locator anti-pattern
    var gateway = sp.GetKeyedService<IPaymentGateway>(provider.ToLowerInvariant());
    
    if (gateway is null)
        return Results.BadRequest(new { Error = $"Provider '{provider}' tidak didukung." });

    var result = gateway.Process(request.Amount);
    return Results.Ok(new { Status = "Success", TransactionId = result });
});

app.Run();

// Kontrak Interface & Domain Models
public record CheckoutRequest(decimal Amount);

public interface IPaymentGateway
{
    string Process(decimal amount);
}

public sealed class StripePaymentGateway : IPaymentGateway
{
    public string Process(decimal amount) => $"STRIPE-TX-{Guid.NewGuid():N}";
}

public sealed class AdyenPaymentGateway : IPaymentGateway
{
    public string Process(decimal amount) => $"ADYEN-TX-{Guid.NewGuid():N}";
}

public sealed class PayPalPaymentGateway : IPaymentGateway
{
    public string Process(decimal amount) => $"PAYPAL-TX-{Guid.NewGuid():N}";
}

// Konsumsi Keyed Service melalui Konstruktor via Primary Constructor
public sealed class CheckoutProcessor(
    [FromKeyedServices("stripe")] IPaymentGateway stripeGateway,
    [FromKeyedServices("adyen")] IPaymentGateway adyenGateway)
{
    public string ExecutePrimary(decimal amount) => stripeGateway.Process(amount);
    public string ExecuteFallback(decimal amount) => adyenGateway.Process(amount);
}
```

#### B. Robust Options Pattern dengan FluentValidation dan ValidateOnStart

```csharp
using FluentValidation;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

// Bind dan daftarkan Options Pipeline secara eksplisit
builder.Services.AddOptions<DatabaseOptions>()
    .Bind(builder.Configuration.GetSection(DatabaseOptions.SectionName))
    .ValidateDataAnnotations()
    .ValidateOnStart(); // Fail-fast saat bootstrapping aplikasi

builder.Services.AddSingleton<IValidator<DatabaseOptions>, DatabaseOptionsValidator>();
builder.Services.AddSingleton<IValidateOptions<DatabaseOptions>, FluentValidateOptions<DatabaseOptions>>();

var app = builder.Build();

app.MapGet("/db-status", (IOptionsMonitor<DatabaseOptions> monitor) =>
{
    var currentOptions = monitor.CurrentValue;
    return Results.Ok(new { Host = currentOptions.Host, Port = currentOptions.Port });
});

app.Run();

// Definisi Options POCO
public sealed class DatabaseOptions
{
    public const string SectionName = "DatabaseConfig";
    public string Host { get; set; } = string.Empty;
    public int Port { get; set; }
    public string DatabaseName { get; set; } = string.Empty;
    public int MaxPoolSize { get; set; } = 100;
}

// Validator Menggunakan FluentValidation
public sealed class DatabaseOptionsValidator : AbstractValidator<DatabaseOptions>
{
    public DatabaseOptionsValidator()
    {
        RuleFor(x => x.Host).NotEmpty().WithMessage("Database Host wajib diisi.");
        RuleFor(x => x.Port).InclusiveBetween(1024, 65535).WithMessage("Port di luar jangkauan port sistem.");
        RuleFor(x => x.DatabaseName).NotEmpty().WithMessage("Nama database tidak boleh kosong.");
        RuleFor(x => x.MaxPoolSize).GreaterThan(0).LessThanOrEqualTo(1000);
    }
}

// Jembatan Integrasi Antara FluentValidation dan IValidateOptions ASP.NET Core
public sealed class FluentValidateOptions<TOptions> : IValidateOptions<TOptions> where TOptions : class
{
    private readonly IServiceProvider _serviceProvider;

    public FluentValidateOptions(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public ValidateOptionsResult Validate(string? name, TOptions options)
    {
        using var scope = _serviceProvider.CreateScope();
        var validator = scope.ServiceProvider.GetService<IValidator<TOptions>>();
        
        if (validator is null)
            return ValidateOptionsResult.Skip;

        var result = validator.Validate(options);
        if (result.IsValid)
            return ValidateOptionsResult.Success;

        var errors = result.Errors.Select(e => $"Properti: {e.PropertyName} gagal dengan error: {e.ErrorMessage}");
        return ValidateOptionsResult.Fail(errors);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Multi-Tenant Gateway FinTech dengan Dynamic Configuration Reloading

##### Latar Belakang Masalah
Sebuah platform sistem pembayaran core-banking memproses jutaan transaksi per hari untuk lebih dari 500 institusi finansial (tenant). Setiap tenant memiliki konfigurasi rate limiting, routing endpoint, dan enkripsi payload yang berbeda. Persyaratan sistem:
1. Konfigurasi tenant diperbarui langsung di database master atau central config server (HashiCorp Consul).
2. Perubahan parameter enkripsi atau rate-limit harus berlaku **kurang dari 1 detik tanpa melakukan restart pod di Kubernetes**.
3. Sistem tidak boleh mengalami lock contention atau kebocoran memori saat ribuan transaksi konkuren membaca konfigurasi yang sedang di-reload.

##### Solusi Arsitektur
Mengembangkan *Custom Configuration Provider* terdistribusi yang memanfaatkan protokol pub/sub untuk memicu `IChangeToken.OnReload()`, dikombinasikan dengan pemanfaatan `IOptionsMonitor<T>` untuk memastikan pembacaan konfigurasi terjadi tanpa lock locking overhead via thread-safe internal cache.

##### Implementasi Custom Configuration Provider Berbasis Background Poller / Event Stream

```csharp
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Primitives;

public sealed class DatabaseConfigurationSource : IConfigurationSource
{
    private readonly string _connectionString;
    private readonly TimeSpan _pollingInterval;

    public DatabaseConfigurationSource(string connectionString, TimeSpan pollingInterval)
    {
        _connectionString = connectionString;
        _pollingInterval = pollingInterval;
    }

    public IConfigurationProvider Build(IConfigurationBuilder builder)
    {
        return new DatabaseConfigurationProvider(_connectionString, _pollingInterval);
    }
}

public sealed class DatabaseConfigurationProvider : ConfigurationProvider, IDisposable
{
    private readonly string _connectionString;
    private readonly TimeSpan _pollingInterval;
    private readonly Timer _timer;
    private bool _isDisposed;

    public DatabaseConfigurationProvider(string connectionString, TimeSpan pollingInterval)
    {
        _connectionString = connectionString;
        _pollingInterval = pollingInterval;
        _timer = new Timer(ExecuteReloadCycle, null, TimeSpan.Zero, _pollingInterval);
    }

    private void ExecuteReloadCycle(object? state)
    {
        try
        {
            var updatedData = FetchConfigurationsFromRemoteStore();

            if (!AreDictionariesIdentical(Data, updatedData))
            {
                Data = updatedData;
                OnReload(); // Memicu eksekusi event IChangeToken ke seluruh IOptionsMonitor
            }
        }
        catch (Exception ex)
        {
            // Catat log kegagalan parsing konfigurasi, jangan matikan engine host
            Console.Error.WriteLine($"[CRITICAL] Gagal me-reload remote config: {ex.Message}");
        }
    }

    private IDictionary<string, string?> FetchConfigurationsFromRemoteStore()
    {
        // Simulasi query read-optimized atau gRPC call ke database konfigurasi
        var data = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase)
        {
            ["TenantRouting:TenantA:TimeoutMs"] = "1500",
            ["TenantRouting:TenantA:MaxRetries"] = "3",
            ["TenantRouting:TenantB:TimeoutMs"] = "800",
            ["TenantRouting:TenantB:MaxRetries"] = "5"
        };
        return data;
    }

    private static bool AreDictionariesIdentical(IDictionary<string, string?> oldData, IDictionary<string, string?> newData)
    {
        if (oldData.Count != newData.Count) return false;
        foreach (var kvp in oldData)
        {
            if (!newData.TryGetValue(kvp.Key, out var newValue) || kvp.Value != newValue)
                return false;
        }
        return true;
    }

    public void Dispose()
    {
        if (_isDisposed) return;
        _timer.Dispose();
        _isDisposed = true;
    }
}

// Extension Method Builder untuk Fluent API Registration
public static class CustomConfigurationExtensions
{
    public static IConfigurationBuilder AddDatabaseConfiguration(
        this IConfigurationBuilder builder, string connectionString, TimeSpan interval)
    {
        return builder.Add(new DatabaseConfigurationSource(connectionString, interval));
    }
}
```

---

### 9. Trade-offs

#### Analisis Pemilihan Lifetime Dependensi

```
              ALLOCATION LATENCY vs GC PRESSURE TRADE-OFF
              
   [Transient] High Latency per request (Allocation & GC cleanup)
        ^
        |         [Scoped] Balanced (Bound to HttpContext Lifecycle)
        |
        |                      [Singleton] Lowest Latency (Zero per-request allocation,
        |                                                 Highest risk of Concurrency Bugs)
        +--------------------------------------------------------------------------->
       0 ms                       ALLOCATION OVERHEAD PER REQUEST
```

| Tipe Lifetime | Latensi Inisialisasi | Tekanan Garbage Collector (GC) | Thread-Safety Complexity | Risiko Kebocoran Memori |
| :--- | :--- | :--- | :--- | :--- |
| **Singleton** | Zero (setelah startup) | Sangat Rendah (Objek hidup permanen di Gen 2) | Sangat Tinggi (Wajib *thread-safe* & *re-entrant*) | Sedang (State retention/kebocoran via event leak) |
| **Scoped** | Rendah - Sedang | Terisolasi per Request (Dibersihkan pada Gen 0/1) | Rendah (Hanya diakses oleh 1 thread pipeline request) | Rendah (Kecuali terjebak di dalam Captive Dependency) |
| **Transient** | Tinggi (Jika dipanggil berulang) | Tinggi (Mengisi Gen 0 secara cepat, memicu GC pauses) | Rendah (Instance eksklusif per pemanggil) | Kritis (Bila implementasi `IDisposable` di-resolve dari Root) |

#### Evaluasi Pola Konfigurasi

*   **`IOptions<T>`**:
    *   *Kelebihan*: Sangat cepat (hanya sekali resolving pointer alamat memori).
    *   *Kekurangan*: Membutuhkan restart aplikasi untuk menerapkan perubahan konfigurasi. Tidak dapat menangani rotasi kredensial dinamis.
*   **`IOptionsSnapshot<T>`**:
    *   *Kelebihan*: Menjamin konsistensi konfigurasi internal yang sama selama pemrosesan satu HTTP Request.
    *   *Kekurangan*: Menimbulkan alokasi heap baru di setiap request scope, tidak bisa diinjeksi ke dalam kelas Singleton (akan melempar `InvalidOperationException`).
*   **`IOptionsMonitor<T>`**:
    *   *Kelebihan*: Dapat diinjeksi ke Singleton dan Scoped, perubahan instan real-time tanpa restart, mendukung multi-tenant named configuration.
    *   *Kekurangan*: Potensi inkonsistensi state jika nilai konfigurasi berubah tepat di tengah-tengah eksekusi algoritma berurutan.

---

### 10. Common Mistakes & Troubleshooting

#### A. Captive Dependency Bug

```csharp
// KESALAHAN FATAL:
builder.Services.AddSingleton<TelemetryCollector>();
builder.Services.AddScoped<IUserRepository, UserRepository>();

public sealed class TelemetryCollector
{
    private readonly IUserRepository _userRepository; // Scoped di-injeksi ke Singleton!

    public TelemetryCollector(IUserRepository userRepository)
    {
        _userRepository = userRepository; // Captive Dependency!
    }
}
```
*   **Dampak Buruk**: `UserRepository` (dan seluruh dependensinya seperti `DbContext`) yang seharusnya mati di akhir request HTTP, tersandera seumur hidup di dalam `TelemetryCollector`. Terjadi kebocoran memori, data silang antar tenant/user, dan exception: `System.InvalidOperationException: A second operation started on this context instance before a previous operation completed.`
*   **Solusi**:
    1. Pastikan lifetime `TelemetryCollector` disamakan menjadi `Scoped`.
    2. Jika `TelemetryCollector` harus singleton, gunakan `IServiceScopeFactory` secara eksplisit saat membutuhkan unit of work:

```csharp
public sealed class TelemetryCollector(IServiceScopeFactory scopeFactory)
{
    public async Task TrackUserActivityAsync(Guid userId)
    {
        using var scope = scopeFactory.CreateScope();
        var userRepository = scope.ServiceProvider.GetRequiredService<IUserRepository>();
        await userRepository.UpdateLastSeenAsync(userId);
    }
}
```

#### B. Resolusi Transient IDisposable dari Root Container

```csharp
// KESALAHAN FATAL:
public static void Main(string[] args)
{
    var app = builder.Build();
    
    // Engine me-resolve Transient IDisposable langsung dari Root Provider
    var reportGenerator = app.Services.GetRequiredService<ITransientPdfExporter>();
    reportGenerator.ExportStartupDiagnostics();
    // reportGenerator TIDAK DI-DISPOSE dan tetap di-track di _disposables Root selamanya!
}
```
*   **Deteksi**:
    Gunakan dump analysis (`dotnet-dump`) dan jalankan perintah SOS:
    `!dumpheap -type Microsoft.Extensions.DependencyInjection.ServiceLookup.ServiceProviderEngine`
    Periksa ukuran koleksi `_disposables`. Jika ukurannya bertambah secara monoton, ada kebocoran transient disposal.
*   **Solusi**:
    Gunakan `IServiceScope` eksplisit saat melakukan bootstrap resolving:

```csharp
using (var scope = app.Services.CreateScope())
{
    var exporter = scope.ServiceProvider.GetRequiredService<ITransientPdfExporter>();
    exporter.ExportStartupDiagnostics();
} // scope.Dispose() menjamin objek exporter dibersihkan secara aman
```

---

### 11. Best Practices (Production Checklist)

| No | Kategori | Item Pemeriksaan Arsitektur | Dampak Jika Diabaikan |
| :---: | :--- | :--- | :--- |
| [ ] | Container | Aktifkan `ValidateScopes` dan `ValidateOnBuild` di Production saat startup testing pipeline. | Captive dependencies tembus ke environment live. |
| [ ] | Options | Pasang `ValidateOnStart()` pada seluruh pendaftaran konfigurasi penting. | Crash tertunda saat endpoint pertama kali dipanggil pengguna. |
| [ ] | Performance | Hindari penggunaan assembly scanning berulang di runtime; lakukan via Scrutor saat bootstrapping. | Boot latency membengkak signifikan pada container cold-start. |
| [ ] | Concurrency | Pastikan dependensi Singleton bebas dari properti mutabel yang tidak dilindungi lock/atomic primitives. | *Race conditions*, korupsi memori, dan *data leakage*. |
| [ ] | Clean Code | Jangan pernah menginjeksi `IServiceProvider` langsung ke domain logic service (Anti-Pattern Service Locator). | Testing suite rapuh, *code smells*, hilangnya pemetaan dependensi. |
| [ ] | Resource | Jangan daftarkan objek `IDisposable` bertipe `Transient` kecuali di-resolve di dalam bounded scope. | Kebocoran memori Gen 2 starvation yang memicu *pod OOMKilled*. |

---

### 12. Hands-on Practice

Struktur direktori praktikum yang akan kita bangun:
```text
hands-on/m02/
├── EnterpriseDiConfig.csproj
├── Program.cs
├── Infrastructure/
│   ├── DynamicTenantConfigProvider.cs
│   └── ResiliencePaymentEngine.cs
└── Options/
    ├── GatewayOptions.cs
    └── GatewayOptionsValidator.cs
```

#### Langkah 1: Inisialisasi Project dan Dependensi
Buka terminal dan jalankan urutan instruksi shell berikut:

```bash
mkdir -p hands-on/m02/Infrastructure hands-on/m02/Options
cd hands-on/m02
dotnet new web -f net8.0
dotnet add package FluentValidation
dotnet add package FluentValidation.DependencyInjectionExtensions
dotnet add package Scrutor
```

#### Langkah 2: Buat Model Options dan Validator
Simpan kode ini di `Options/GatewayOptions.cs`:

```csharp
namespace EnterpriseDiConfig.Options;

public sealed class GatewayOptions
{
    public const string SectionName = "PaymentEngine";
    public string ApiUrl { get; set; } = string.Empty;
    public int TimeoutSeconds { get; set; }
    public int MaxRetries { get; set; }
}
```

Simpan kode validator di `Options/GatewayOptionsValidator.cs`:

```csharp
using FluentValidation;

namespace EnterpriseDiConfig.Options;

public sealed class GatewayOptionsValidator : AbstractValidator<GatewayOptions>
{
    public GatewayOptionsValidator()
    {
        RuleFor(x => x.ApiUrl).Must(uri => Uri.TryCreate(uri, UriKind.Absolute, out _))
            .WithMessage("Format ApiUrl tidak valid.");
        RuleFor(x => x.TimeoutSeconds).InclusiveBetween(1, 30);
        RuleFor(x => x.MaxRetries).InclusiveBetween(0, 5);
    }
}
```

#### Langkah 3: Implementasikan Modul Infrastruktur
Simpan file ini di `Infrastructure/ResiliencePaymentEngine.cs`:

```csharp
using EnterpriseDiConfig.Options;
using Microsoft.Extensions.Options;

namespace EnterpriseDiConfig.Infrastructure;

public interface IPaymentEngine
{
    string ProcessTransaction(decimal amount);
}

public sealed class ModernPaymentEngine(IOptionsMonitor<GatewayOptions> optionsMonitor) : IPaymentEngine
{
    public string ProcessTransaction(decimal amount)
    {
        var config = optionsMonitor.CurrentValue;
        return $"[Processing ${amount}] Melalui {config.ApiUrl} (Timeout: {config.TimeoutSeconds}s, Retries: {config.MaxRetries})";
    }
}
```

#### Langkah 4: Tulis Kode Program Utama
Tuliskan implementasi lengkap di `Program.cs`:

```csharp
using EnterpriseDiConfig.Infrastructure;
using EnterpriseDiConfig.Options;
using FluentValidation;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

// 1. Konfigurasi DefaultServiceProviderFactory untuk validasi agresif
builder.Host.UseDefaultServiceProvider((context, options) =>
{
    var isDev = context.HostingEnvironment.IsDevelopment();
    options.ValidateScopes = true;
    options.ValidateOnBuild = true;
});

// 2. Registrasi Validasi Options dengan FluentValidation
builder.Services.AddValidatorsFromAssemblyContaining<GatewayOptionsValidator>();

builder.Services.AddOptions<GatewayOptions>()
    .Bind(builder.Configuration.GetSection(GatewayOptions.SectionName))
    .Validate(options =>
    {
        using var serviceProvider = builder.Services.BuildServiceProvider();
        var validator = serviceProvider.GetRequiredService<IValidator<GatewayOptions>>();
        var validationResult = validator.Validate(options);
        return validationResult.IsValid;
    }, "Validasi Options GatewayOptions gagal terhadap aturan bisnis.")
    .ValidateOnStart();

// 3. Registrasi Services via Scrutor Assembly Scanning
builder.Services.Scan(scan => scan
    .FromAssemblyOf<IPaymentEngine>()
    .AddClasses(classes => classes.AssignableTo<IPaymentEngine>())
    .AsImplementedInterfaces()
    .WithSingletonLifetime());

var app = builder.Build();

app.MapGet("/pay", (IPaymentEngine paymentEngine) =>
{
    var message = paymentEngine.ProcessTransaction(100.50m);
    return Results.Ok(new { Timestamp = DateTime.UtcNow, Payload = message });
});

app.Run();
```

#### Langkah 5: Buat File `appsettings.json` yang Valid dan Jalankan
Modifikasi `appsettings.json`:

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "AllowedHosts": "*",
  "PaymentEngine": {
    "ApiUrl": "https://api.gateway.enterprise.com/v1",
    "TimeoutSeconds": 15,
    "MaxRetries": 3
  }
}
```

Jalankan pengujian via terminal:
```bash
dotnet run
```
Akses `http://localhost:<port>/pay` menggunakan curl atau browser untuk mengonfirmasi bahwa graf dependensi berhasil disusun dengan performa optimal. Coba ubah nilai `ApiUrl` menjadi string rusak (misal: `"bukan_url"`), lalu jalankan kembali aplikasi. Perhatikan bagaimana `ValidateOnStart()` memblokir booting aplikasi dan memicu fail-fast exception sebelum server mendengarkan port TCP.

---

### 13. Exercise

1. **Level Easy**: Ubah registrasi dependensi `IPaymentEngine` pada hands-on di atas sehingga dapat di-resolve sebagai **Keyed Service** dengan key `"core-banking"` dan buat satu endpoint minimal API baru yang memanggil instance tersebut melalui atribut `[FromKeyedServices("core-banking")]`.
2. **Level Medium**: Buat sebuah generic wrapper `TenantAwareOptions<T>` yang mengimplementasikan multi-tenancy sederhana dengan membaca tenant identifier dari header HTTP `X-Tenant-ID` dan mengembalikan konfigurasi spesifik tenant menggunakan `IOptionsSnapshot<T>`.
3. **Level Hard**: Kembangkan kustom provider `ConsulConfigurationProvider` yang mengimplementasikan `ConfigurationProvider` dan `IDisposable`. Provider ini harus membuka socket HTTP long-polling ke local Consul agent simulator, mendengarkan perubahan key `/config/app`, dan mengeksekusi `OnReload()` ketika hash index payload key berubah tanpa menimbulkan alokasi memori berlebih (*zero string allocation* saat hashing).

---

### 14. Challenge

**Skenario Kasus Produksi Ekstrem (Tanpa Panduan Solusi Instan):**
Anda adalah Principal Architect pada startup ride-hailing dengan traffic 150.000 RPS. Terjadi insiden keparahan tinggi (P0): Aplikasi mengalami degradasi performa setiap hari pada pukul 12.00 siang di mana CPU spike mencapai 100% dan request latency naik dari 15ms menjadi 4000ms selama 45 detik, lalu normal kembali secara otomatis.

Investigasi awal menemukan petunjuk berikut:
1. Sebuah cron-job di Kubernetes mengupdate ConfigMap berisi data geofencing tarif setiap pukul 12.00 siang.
2. Aplikasi menggunakan `IOptionsMonitor<TariffOptions>` yang diinjeksi ke dalam sebuah Singleton service bernama `FareCalculationEngine`.
3. Di dalam callback `optionsMonitor.OnChange(newOptions => ...)`, engine lama menjalankan kompilasi ekspresi matematika dinamis (*Dynamic Expression Compilation*) untuk membangun routing tree geofencing baru secara sinkron dengan mengunci *reader-writer lock*.

**Tantangan Arsitektur:**
Desain ulang arsitektur sinkronisasi konfigurasi di atas untuk menjamin bahwa proses reload konfigurasi tarif geofencing baru berjalan dengan **zero-lock overhead pada thread pool Kestrel**, transisi evaluasi perhitungan tarif lama ke tarif baru bersifat atomik (`Interlocked.Exchange` pattern atau referensi immutable pointer swapping), dan metrik transaksi throughput tidak mengalami lonjakan latensi (*flat latency profile*) sama sekali saat rotasi data berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara dependensi berumur `Scoped` dan `Transient` pada ASP.NET Core?
2. Mengapa meregistrasikan service bertipe `Transient` yang mengimplementasikan interface `IDisposable` langsung dari Root Container dianggap sebagai praktik berbahaya?
3. Apa perbedaan esensial dari membaca konfigurasi melalui `builder.Configuration.GetSection("...").Get<T>()` dibandingkan dengan menggunakan `builder.Services.Configure<T>(...)`?
4. Kapan waktu yang tepat menggunakan `IOptionsSnapshot<T>` alih-alih `IOptions<T>`?
5. Exception apa yang akan dilemparkan oleh kontainer MS.DI jika service berumur `Scoped` diinjeksi ke dalam konstruktor service berumur `Singleton` saat `ValidateScopes = true`?

#### B. Pertanyaan Intermediate
1. Mengapa `IOptionsSnapshot<T>` tidak dapat diinjeksi ke dalam kelas yang didaftarkan dengan lifetime `Singleton`?
2. Bagaimana cara engine `DynamicMethodServiceProviderEngine` meningkatkan throughput resolusi dependensi dibandingkan dengan engine standar berbasis `RuntimeServiceProviderEngine`?
3. Bagaimana mekanisme internal `IChangeToken` bekerja saat memicu pembaruan nilai pada instance `IOptionsMonitor<T>`?
4. Apa dampak penggunaan library auto-registration seperti Scrutor terhadap metrik *Application Startup Time (Cold Start)* di lingkungan serverless container seperti AWS Lambda atau Google Cloud Run?
5. Sebutkan satu skenario valid di mana injeksi `IServiceScopeFactory` ke dalam kelas `Singleton` diperbolehkan dan bukan merupakan bentuk anti-pattern Service Locator!

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Sebuah background worker (`IHostedService`) singleton memerlukan akses ke database via Entity Framework Core (`AppDbContext`, yang didaftarkan sebagai `Scoped`). Developer menginjeksi langsung `AppDbContext` ke konstruktor worker tersebut. Jelaskan rantai kerusakan teknis (*technical cascading failure*) yang akan terjadi saat background service mengeksekusi iterasi kedua dari background loop!
2. **Skenario 2**: Sistem pembayaran Anda memproses request otorisasi kartu kredit secara masif. Anda mendapati penggunaan memori Gen 2 terus membengkak tajam (*memory ramp-up*) hingga server mengalami Out of Memory (OOM). Profiling dump file menunjukkan jutaan instance `HttpClientHandler` tersimpan di memori. Diketahui bahwa sebuah service `PaymentService` didaftarkan sebagai `Transient`, dan di dalam konstruktornya menginstansiasi `new HttpClient()`. Bagaimana mekanisme IoC container berkontribusi terhadap bencana ini dan bagaimana Anda memperbaikinya secara definitif?
3. **Skenario 3**: Sebuah tim ingin mengimplementasikan secret rotation untuk database password setiap 30 hari. Mereka mengganti `IOptions<DbConfig>` dengan `IOptionsMonitor<DbConfig>`. Namun, aplikasi mereka tetap melempar error otorisasi database lama meskipun value di file konfigurasi telah berubah. Jelaskan mengapa hal ini terjadi pada level connection pooling `NpgsqlConnection` atau `SqlConnection`!

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Pertanyaan Basic
1. **Perbedaan Scoped vs Transient**: Dependensi `Scoped` diinstansiasi satu kali per satu batas scope (pada web apps: per siklus satu HTTP request) dan instance yang sama dibagikan ke seluruh komponen dalam satu request tersebut. Dependensi `Transient` selalu diinstansiasi baru setiap kali dependensi tersebut diminta (*resolved*), bahkan dalam satu request HTTP yang sama.
2. **Bahaya Transient IDisposable di Root**: Root Container tidak memiliki mekanisme pembuangan otomatis berbasis event request. Setiap objek transient yang mengimplementasikan `IDisposable` akan direferensikan dalam list internal kontainer root agar dapat dipanggil method `Dispose()`-nya saat aplikasi shutdown. Akibatnya, objek-objek ini tidak dapat dibersihkan oleh Garbage Collector, menyebabkan kebocoran memori Gen 2 permanen.
3. **Get vs Configure**: Metode `.Get<T>()` membaca konfigurasi secara langsung, mengalokasikan objek baru di memori secara imperatif, dan nilainya terputus dari ekosistem *options pipeline*. Metode `.Configure<T>()` mengintegrasikan konfigurasi ke dalam *Options Pattern framework*, mendukung *dependency injection*, *dynamic reload*, *named options*, dan validasi skema runtime.
4. **Waktu Penggunaan IOptionsSnapshot**: Saat kita membutuhkan nilai konfigurasi yang dapat ter-reload secara otomatis ketika file/sumber konfigurasi berubah, namun tetap menjamin nilai tersebut stabil dan tidak berubah (*consistent view*) selama pemrosesan satu HTTP request berlangsung.
5. **Exception Validasi Scope**: `System.InvalidOperationException` dengan pesan: *"Cannot consume scoped service 'X' from singleton 'Y'"*.

#### Jawaban Pertanyaan Intermediate
1. **Mengapa IOptionsSnapshot Tidak Bisa di Singleton**: Karena `IOptionsSnapshot<T>` didaftarkan dengan lifetime `Scoped`. Menyetujui injeksi service berumur `Scoped` ke dalam service berumur `Singleton` melanggar aturan integritas dependensi (*Captive Dependency*), karena instance scoped tersebut akan terjebak seumur hidup di dalam singleton dan kehilangan kapabilitas scope isolation-nya.
2. **Cara Kerja DynamicMethodServiceProviderEngine**: Alih-alih melakukan inspeksi tipe dan invoking konstruktor secara dinamis berulang-ulang menggunakan `.GetConstructors()` dan `.Invoke()` (refleksi tradisional) yang sangat lambat, engine ini mengompilasi graf pohon dependensi menjadi deretan instruksi MSIL (MicroSoft Intermediate Language) secara *in-memory* saat pertama kali service diakses. Hasilnya berupa delegasi fungsi C# murni yang dieksekusi secepat pemanggilan kode langsung (`new Service(...)`).
3. **Mekanisme IChangeToken pada IOptionsMonitor**: Ketika sumber konfigurasi mendeteksi modifikasi data, provider mengeksekusi callback `OnReload()`. Method ini memicu `IChangeToken` yang dipegang oleh `ConfigurationReloadToken`. `IOptionsMonitor` mendengarkan event token ini, segera membatalkan (*invalidate*) cache internal pada `IOptionsMonitorCache<T>`, dan mengeksekusi delegasi `OnChange` yang terdaftar.
4. **Dampak Scrutor terhadap Cold Start**: Assembly scanning melakukan inspeksi seluruh tipe, interface, dan metadata pada satu atau banyak assembly menggunakan refleksi saat aplikasi pertama kali menyala. Pada lingkungan *serverless* dengan batasan CPU ketat, scanning per puluhan assembly dapat menambah cold-start latency sebesar 200ms - 1500ms.
5. **Skenario Valid IServiceScopeFactory di Singleton**: Pada background process (`IHostedService` atau `BackgroundService`) yang hidup sebagai singleton, ketika service tersebut secara periodik membutuhkan akses ke dependensi yang berumur scoped (seperti `DbContext` untuk melakukan batch processing database), pola yang valid adalah menginjeksi `IServiceScopeFactory`, lalu membungkus eksekusi batch di dalam blok `using (var scope = scopeFactory.CreateScope()) { ... }`.

#### Pembahasan Skenario Kasus Produksi
1. **Skenario 1**:
   *   *Rantai Kerusakan*: Pada iterasi pertama, `AppDbContext` mungkin tampak berjalan normal. Namun, karena dipegang oleh singleton, instance context tersebut tidak pernah di-dispose.
   *   Pada iterasi kedua dan seterusnya, local entity tracker pada context tersebut akan terus membesar (*unbounded memory growth*).
   *   Lebih parah lagi, jika background worker mengeksekusi operasi parallel (misal via `Task.WhenAll`), beberapa thread akan mengakses method `AppDbContext` secara simultan. Karena `DbContext` bersifat **non-thread-safe**, runtime akan seketika melempar exception: `InvalidOperationException: A second operation started on this context instance before a previous operation completed`. Sistem sinkronisasi background worker akan crash.
2. **Skenario 2**:
   *   *Mekanisme Bencana*: Menginstansiasi `new HttpClient()` secara berulang di dalam kelas `Transient` adalah anti-pattern fatal. Setiap `HttpClient` memegang instance `HttpClientHandler` yang mengalokasikan unmanaged socket system resource.
   *   Ketika scope transient selesai, GC membuang pointer managed-nya, tetapi unmanaged socket-nya tetap menggantung pada sistem operasi dalam status `TIME_WAIT` (*socket exhaustion*).
   *   Karena service transient tersebut terus dibuat masif pada setiap transaksi, ribuan handler tertimbun sebelum OS sempat membersihkan socket-nya, melumpuhkan aplikasi secara keseluruhan.
   *   *Solusi*: Hapus instansiasi manual. Daftarkan typed/named client via `builder.Services.AddHttpClient()` dan injeksikan `IHttpClientFactory` atau *Typed Client* ke dalam service untuk memanfaatkan internal socket handler pooling.
3. **Skenario 3**:
   *   *Akar Masalah*: Meskipun `IOptionsMonitor<DbConfig>` berhasil mendeteksi string koneksi atau password baru, `Npgsql` dan `Microsoft.Data.SqlClient` mengelola mekanisme *Connection Pooling* internal sendiri di level driver ADO.NET yang berumur singleton di seluruh proses aplikasi.
   *   Connection pool mencatat connection string yang digunakan saat pool pertama kali diinisialisasi.
   *   Perubahan konfigurasi di level C# tidak secara otomatis mengosongkan koneksi pool TCP yang sudah berstatus *idle* atau *open* di level driver.
   *   *Solusi*: Daftarkan aksi callback pada options monitor:
       ```csharp
       optionsMonitor.OnChange(newConfig => {
           NpgsqlConnection.ClearAllPools(); // atau SqlConnection.ClearAllPools();
       });
       ```
       Perintah ini memaksa driver ADO.NET mematikan seluruh koneksi lama yang tersimpan di pool sehingga koneksi berikutnya dibangun ulang menggunakan kredensial baru.

---

### 16. Summary

Implementasi arsitektur dependency injection dan konfigurasi pada aplikasi enterprise modern memerlukan penguasaan mendalam atas detail internal framework, bukan sekadar memanggil API pendaftaran method dasar.

1. **Pemahaman Lifecycle Kontainer**:
   Penetapan lifetime (`Singleton`, `Scoped`, `Transient`) menentukan bukan hanya kapan objek dibuat, tetapi juga bagaimana objek tersebut dicatat pada GC root dan kapan dialokasikan ulang oleh memori. Mencegah *Captive Dependencies* dan mengeliminasi pemanggilan *Transient IDisposable* dari root adalah pilar stabilitas memori aplikasi ASP.NET Core.

2. **Evolusi Pola Ekosistem Modern**:
   Pemanfaatan native *Keyed Services* di .NET 8/9 menstandarisasi resolusi dependensi bersyarat tanpa perlu mengotori arsitektur dengan *Service Locator* atau custom factory yang rentan alokasi.

3. **Options Architecture & Fail-Fast Resilience**:
   Penggunaan *Options Pattern* wajib dikombinasikan dengan teknik validasi berlapis (`ValidateDataAnnotations`, *FluentValidation*, dan `ValidateOnStart`). Konsep arsitektur yang tangguh harus selalu memegang prinsip: **"Lebih baik aplikasi meledak (crash-fast) dalam hitungan milidetik saat booting startup daripada lolos ke produksi lalu memuntahkan error runtime ke pengguna akhir."** Implementasi `IOptionsMonitor` harus memperhitungkan implikasi konkurensi data, *connection pooling lifecycle*, dan konsistensi thread pada beban throughput tinggi.