# Bab 02 Module 01: Dependency Injection & Configuration Deep Dive

---

## SEKSI 01 — IDENTITAS MODUL

*   **Track:** Backend Engineering & Cloud Architecture
*   **Kategori:** 02-Programming-Languages
*   **Teknologi:** ASP.NET Core (.NET 8+)
*   **Bab:** 02 — Arsitektur Core Engine ASP.NET Core
*   **Modul:** 01 — Dependency Injection & Configuration Deep Dive
*   **Target Audience:** Senior Software Engineers, Backend Tech Leads, Systems Architects
*   **Prasyarat:**
    *   Pemahaman mendalam tentang C# tingkat lanjut (Generics, Reflection, Delegates, Threading, Memory Management).
    *   Prinsip Object-Oriented Design & SOLID (khususnya *Inversion of Control* dan *Dependency Inversion Principle*).
    *   Pengalaman membangun REST API minimal dengan ASP.NET Core dasar.
*   **Estimasi Waktu Selesai:** 150 – 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Menganalisis Internal Runtime Service Provider:** Membedah arsitektur internal `Microsoft.Extensions.DependencyInjection`, termasuk peran `CallSiteFactory`, kompilasi pohon ekspresi (*compiled expression trees*), hingga mekanisme IL-Emit pada resolusi instansiasi.
2.  **Mengeliminasi Cacat Desain Lifecycle:** Mengidentifikasi dan merekayasa mitigasi terhadap *Captive Dependencies*, kebocoran memori berbasis Scope (`Memory Leaks via Root Disposal Tracking`), dan ketidaksesuaian konkurensi pada multithreading.
3.  **Mengimplementasikan Pola Options Tingkat Lanjut:** Mengonfigurasi, memvalidasi secara ketat (*fail-fast on start*), dan mengonsumsi konfigurasi menggunakan `IOptions<T>`, `IOptionsSnapshot<T>`, dan `IOptionsMonitor<T>` sesuai karakteristik beban kerja.
4.  **Membangun Custom Configuration Provider:** Merancang dan mengintegrasikan sumber konfigurasi kustom (*custom configuration source*) yang mendukung hot-reloading real-time dan abstraksi enkripsi tanpa memblokir thread I/O.
5.  **Menerapkan Arsitektur Inversi Dependensi Terisolasi:** Mengabstraksikan dependensi lintas layer pada arsitektur monolit modular atau microservices menggunakan *Service Descriptor Manipulation* dan *Scrutor-driven Assembly Scanning*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Paradigma "Container as an Engine, Not a Service Locator"

Banyak engineer pemula memandang IoC (*Inversion of Control*) Container sekadar sebagai *dictionary* global tempat meletakkan dan mengambil objek melalui `IServiceProvider.GetService<T>()`. Ini adalah cacat mental fundamental. Pola tersebut adalah **Service Locator**, sebuah anti-pattern yang menyembunyikan dependensi kelas, merusak *testability*, dan mengaburkan siklus hidup objek (*object lifecycle*).

Mental model yang benar:
1.  **IoC Container adalah Execution Graph Factory:** Anda tidak meminta dependensi di tengah-tengah runtime eksekusi bisnis. Anda mendaftarkan cetak biru (*blueprint/descriptors*), dan container mengompilasi pohon resolusi objek (*Object Graph*) pada *Composition Root* aplikasi saat inisialisasi.
2.  **Request Pipeline adalah Pure Scope Boundary:** Setiap HTTP Request bukan hanya jalur pipa eksekusi middleware, melainkan sebuah batas transaksional memori (*memory transactional boundary*) yang diwakili oleh `IServiceScope`. Semua dependensi yang membawa konteks request (misal: Unit of Work, DbContext, User Context) terisolasi secara hermetis di dalam scope tersebut dan **wajib hancur bersamaan** saat request berakhir.
3.  **Configuration adalah Layered Flattened Tree:** Konfigurasi di .NET bukan dokumen JSON statis. Konfigurasi adalah struktur data *key-value hierarchy* yang dinormalisasi menjadi representasi string berjenjang (*flattened string tree*). Setiap *Configuration Provider* hanyalah lapisan transparan yang menimpa (*override*) kunci yang identik berdasarkan urutan registrasi (*LIFO / Last-In-Wins*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Lifecycle Resolution Tree & Memory Boundaries

```
+-----------------------------------------------------------------------------+
|                               ROOT CONTAINER                                |
|                                                                             |
|  [Singleton Service A]  <------------------------------------------------+  |
|  (Hidup selama proses aplikasi aktif; Dibuat 1x; Thread-Safe)            |  |
|                                                                          |  |
|  +-----------------------------+         +-----------------------------+ |  |
|  |     HTTP REQUEST SCOPE 1    |         |     HTTP REQUEST SCOPE 2    | |  |
|  |                             |         |                             | |  |
|  |  [Scoped Service B1]        |         |  [Scoped Service B2]        | |  |
|  |  (Terisolasi pada Scope 1)  |         |  (Terisolasi pada Scope 2)  | |  |
|  |             |               |         |             |               | |  |
|  |             v               |         |             v               | |  |
|  |  [Transient Service C1]     |         |  [Transient Service C2]     | |  |
|  |  (Instansiasi Baru)         |         |  (Instansiasi Baru)         | |  |
|  +-----------------------------+         +-----------------------------+ |  |
|                 |                                       |                |  |
|                 v                                       v                |  |
|     (Disposed saat Scope 1 mati)            (Disposed saat Scope 2 mati) |  |
|                                                                          |  |
+--------------------------------------------------------------------------+--+
                                  |
                                  v
                    (Disposed saat Root App Shutdown)
```

### 2. Configuration Layering Precedence (Last Write Wins)

```
[appsettings.json]
       |
       v
[appsettings.{Environment}.json]  --> Meng-override appsettings.json
       |
       v
[Environment Variables]           --> Meng-override settings berbasis file
       |
       v
[Command Line Arguments]          --> Precedence tertinggi (Override mutlak)
       |
       v
+-------------------------------+
|  IConfigurationRoot Flattened  | --> Dikonversi ke Options Pattern
+-------------------------------+     (IOptions, IOptionsSnapshot, IOptionsMonitor)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Arsitektur Internal `Microsoft.Extensions.DependencyInjection`

Container bawaan ASP.NET Core dirancang dengan fokus performa ekstrem (*zero/low allocations*). Komponen utamanya adalah:

1.  **`IServiceCollection`**: Implementasi dari `IList<ServiceDescriptor>`. Ini hanyalah fase deklarasi murni. Setiap `ServiceDescriptor` menyimpan:
    *   `ServiceType`: Abstraksi/Interface.
    *   `ImplementationType` / `ImplementationInstance` / `ImplementationFactory`: Cara menginstansiasinya.
    *   `Lifetime`: Enum `Transient`, `Scoped`, atau `Singleton`.
2.  **`CallSiteFactory`**: Saat metode `BuildServiceProvider()` dipanggil, data pada `IServiceCollection` ditransfer ke `CallSiteFactory`. Komponen ini bertugas menganalisis ketergantungan konstruktor antar-service dan membentuk graf ketergantungan yang disebut `ServiceCallSite`.
3.  **`ServiceProviderEngine`**: ASP.NET Core memiliki beberapa mesin evaluasi dependensi internal:
    *   *DynamicServiceProviderEngine*: Menggunakan kombinasi interpretasi awal dan kompilasi runtime. Resolusi ke-1 dan ke-2 diproses menggunakan refleksi ekspresi pohon murni (*interpreted*). Jika dependensi dipanggil berulang kali secara konstan, engine akan menghasilkan Dynamic Method (IL-Emit) runtime untuk mengoptimalkan pemanggilan ke level kecepatan instruksi mesin mentah (*native compiled call*).
    *   *RuntimeServiceProviderEngine*: Berbasis kompilasi ekspresi (`Expression<Func<ServiceProviderEngineScope, object>>`).
4.  **Scope Boundary & Tracking (`ServiceProviderEngineScope`)**:
    *   Menerapkan antarmuka `IServiceProvider` dan `IAsyncDisposable`.
    *   Menyimpan tabel `Dictionary<ServiceCacheKey, object>` untuk men-cache instance dependensi ber-lifetime `Scoped`.
    *   Menyimpan koleksi `List<object> _disposables`. Setiap kali objek yang mengimplementasikan `IDisposable` atau `IAsyncDisposable` dibuat:
        *   Jika lifetime-nya `Scoped`, dimasukkan ke `_disposables` milik scope tersebut.
        *   Jika lifetime-nya `Transient` namun dipanggil dari scope tersebut, dimasukkan juga ke `_disposables` scope tersebut.
        *   **CRITICAL:** Jika service `Transient` yang mengimplementasikan `IDisposable` di-resolve langsung dari **Root Provider**, objek tersebut akan ditahan oleh Root Provider selamanya hingga aplikasi mati, menyebabkan **Memory Leak**.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Lifetime Behavior Matrix

| Lifetime | Siklus Hidup | Resolusi Multi-Thread | Konteks Ideal |
| :--- | :--- | :--- | :--- |
| **Transient** | Dibuat setiap kali diminta (*per resolution*). | Aman jika service tidak menyimpan state internal. | Stateless calculation, lightweight command handlers. |
| **Scoped** | Dibuat sekali per instance `IServiceScope` (misal per HTTP Request). | Tidak thread-safe jika scope dibagi lintas thread paralel (`Task.WhenAll`). | EF Core `DbContext`, Unit of Work, User Identity Context. |
| **Singleton** | Dibuat sekali pada pemanggilan pertama (atau saat register) dan bertahan seumur aplikasi. | **Wajib Thread-Safe**. Multi-thread akan mengeksekusi instance yang identik. | Memory Cache, Message Bus Client, Metrics Collector. |

### 2. The Dreaded Captive Dependency

*Captive Dependency* terjadi ketika dependensi dengan masa hidup pendek (*shorter lifetime*) di-inject ke dalam dependensi dengan masa hidup panjang (*longer lifetime*).
*   **Contoh:** Sebuah service ber-lifetime `Singleton` menerima inject `Scoped` service (misal: `DbContext`).
*   **Dampak:**
    1.  Service `Scoped` tersebut "ditawan" (*held captive*) oleh `Singleton`, menjadikannya *de facto* Singleton.
    2.  `DbContext` tidak pernah hancur (*never disposed*), mengakibatkan akumulasi memory tracking EF Core yang eksplosif.
    3.  Multi-threading crash: `DbContext` bukan thread-safe. Jika dua HTTP request mengeksekusi metode pada Singleton tersebut, keduanya akan mengakses instance `DbContext` yang sama secara konkuren, memicu `InvalidOperationException: A second operation was started on this context before a previous operation completed`.

### 3. Options Pattern: Perbedaan Tiga Serangkai

*   `IOptions<T>`:
    *   Lifetime: **Singleton**.
    *   Dihitung sekali saat pertama kali diakses.
    *   **Tidak mendukung** pembacaan perubahan file konfigurasi (*reload tokens ignored*).
    *   Alokasi memori paling minimal, performa pembacaan tercepat.
*   `IOptionsSnapshot<T>`:
    *   Lifetime: **Scoped**.
    *   Dihitung ulang satu kali untuk setiap HTTP Request / Scope baru.
    *   Membaca perubahan data konfigurasi saat runtime secara dinamis per request.
    *   Tidak dapat di-inject ke dalam Singleton service.
*   `IOptionsMonitor<T>`:
    *   Lifetime: **Singleton**.
    *   Menggunakan `IOptionsChangeTokenSource<T>` untuk mendeteksi perubahan konfigurasi seketika (*real-time notifications*).
    *   Menyediakan properti `.CurrentValue` dan event listener `.OnChange((newOptions, named) => {})`.
    *   Dapat di-inject ke dalam kelas Singleton maupun Scoped.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi clean architecture setup yang mendemonstrasikan Configuration Engine, Options Pattern dengan validasi ketat (*Data Annotations & Custom Validation*), serta pembersihan lifecycle yang aman.

```csharp
// File: Program.cs
using System.ComponentModel.DataAnnotations;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

// 1. Hardening DI Validation (Fail-Fast saat Booting)
builder.Host.UseDefaultServiceProvider((context, options) =>
{
    var isDevelopment = context.HostingEnvironment.IsDevelopment();
    // Validasi Scopes mendeteksi Scoped service masuk ke Singleton
    options.ValidateScopes = isDevelopment;
    // Validasi Build memeriksa ketersediaan seluruh dependency graph saat startup
    options.ValidateOnBuild = true;
});

// 2. Setup Strongly-Typed Configuration dengan Options Validation
builder.Services.AddOptions<DatabaseResilienceOptions>()
    .Bind(builder.Configuration.GetSection(DatabaseResilienceOptions.SectionName))
    .ValidateDataAnnotations()
    .Validate(config =>
    {
        if (config.MaxRetryAttempts < 3 && config.EnableCircuitBreaker)
        {
            return false; // Validasi kustom lintas-properti
        }
        return true;
    }, "Circuit breaker membutuhkan minimal 3 retry attempts untuk stabilitas.")
    .ValidateOnStart(); // Memaksa validasi gagal saat startup, BUKAN saat first request!

// 3. Registrasi Services berdasarkan LifeCycle yang Benar
builder.Services.AddSingleton<IMetricsCollector, InMemoryMetricsCollector>();
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddTransient<ITaxCalculator, TaxCalculator>();

var app = builder.Build();

app.MapGet("/process-order", async (IOrderService orderService) =>
{
    await orderService.ProcessOrderAsync(1001, 500.0m);
    return Results.Ok(new { Status = "Processed" });
});

app.Run();

// ==========================================
// KELAS MODEL DAN KONTRAK
// ==========================================

public sealed class DatabaseResilienceOptions
{
    public const string SectionName = "DatabaseResilience";

    [Required(ErrorMessage = "ConnectionTimeoutSeconds wajib diisi.")]
    [Range(1, 120, ErrorMessage = "Timeout harus antara 1 sampai 120 detik.")]
    public int ConnectionTimeoutSeconds { get; init; }

    [Range(1, 10)]
    public int MaxRetryAttempts { get; init; } = 3;

    public bool EnableCircuitBreaker { get; init; } = true;
}

public interface IMetricsCollector
{
    void IncrementProcessedOrders();
}

public sealed class InMemoryMetricsCollector : IMetricsCollector
{
    private long _processedCount;
    public void IncrementProcessedOrders() => Interlocked.Increment(ref _processedCount);
}

public interface ITaxCalculator
{
    decimal CalculateTax(decimal amount);
}

public sealed class TaxCalculator : ITaxCalculator
{
    public decimal CalculateTax(decimal amount) => amount * 0.11m; // 11% PPN
}

public interface IOrderService
{
    Task ProcessOrderAsync(long orderId, decimal amount);
}

public sealed class OrderService : IOrderService, IDisposable
{
    private readonly ITaxCalculator _taxCalculator;
    private readonly IMetricsCollector _metricsCollector;
    private readonly DatabaseResilienceOptions _options;
    private bool _disposed;

    public OrderService(
        ITaxCalculator taxCalculator,
        IMetricsCollector metricsCollector,
        IOptionsSnapshot<DatabaseResilienceOptions> options)
    {
        _taxCalculator = taxCalculator;
        _metricsCollector = metricsCollector;
        _options = options.Value; // Dievaluasi scoped per-request
    }

    public Task ProcessOrderAsync(long orderId, decimal amount)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);

        var tax = _taxCalculator.CalculateTax(amount);
        _metricsCollector.IncrementProcessedOrders();
        
        // Logika bisnis disimulasikan
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _disposed = true;
            // Cleanup unmanaged resources di sini jika ada
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanik dari kode di Seksi 07:

*   **Baris 9–16:** `builder.Host.UseDefaultServiceProvider(...)`
    *   `options.ValidateScopes = isDevelopment`: Memeriksa runtime apakah dependensi scoped dipanggil langsung dari root provider atau dari service singleton. Sangat disarankan aktif di *Development* karena menambah overhead traversal graf pada runtime.
    *   `options.ValidateOnBuild = true`: Memeriksa integritas seluruh tree dependency saat `Build()` dipanggil. Jika ada interface yang lupa diregistrasi tapi dibutuhkan oleh konstruktor service lain, aplikasi akan melempar exception **saat proses boot aplikasi**, bukan saat rute endpoint pertama kali diakses oleh klien.
*   **Baris 19–30:** `builder.Services.AddOptions<DatabaseResilienceOptions>()...ValidateOnStart()`
    *   `.Bind(...)`: Mengaitkan section JSON ke representasi POCO class.
    *   `.ValidateDataAnnotations()`: Menjalankan validasi berbasis atribut data (`[Required]`, `[Range]`).
    *   `.Validate(...)`: Menambahkan aturan validasi kustom tingkat lanjut (korelasi antar dua properti: `MaxRetryAttempts` dan `EnableCircuitBreaker`).
    *   `.ValidateOnStart()`: Menjalankan eksekusi `IStartupValidator`. Jika appsettings salah format, aplikasi langsung *crash fast* saat startup dengan output log kesalahan yang eksplisit.
*   **Baris 33–35:** Registrasi Lifecycles:
    *   `IMetricsCollector` (Singleton): Aman karena menggunakan operasi atomic `Interlocked.Increment` yang thread-safe.
    *   `IOrderService` (Scoped): Menjamin isolasi eksekusi per HTTP invocation, serta menjamin metode `Dispose()` dieksekusi secara otomatis saat request selesai.
    *   `ITaxCalculator` (Transient): Stateless logic engine, tidak memegang unmanaged resources sehingga instansiasinya sangat cepat dan segera dipungut oleh Garbage Collector (Gen0).
*   **Baris 92:** `IOptionsSnapshot<DatabaseResilienceOptions> options`
    *   Konstruktor `OrderService` menggunakan `IOptionsSnapshot`. Jika file `appsettings.json` diubah pada server tanpa me-restart server, request baru berikutnya akan langsung membaca nilai terbaru tersebut secara transparan.

---

## SEKSI 09 — STUDI KASUS NYATA (High-Throughput Multi-Tenant Fintech Engine)

### Deskripsi Masalah
Sebuah platform Payment Gateway memproses jutaan transaksi per hari. Platform ini melayani ratusan Tenant (*Merchants*).
Tantangan Arsitektur:
1.  **Konfigurasi Dinamis Per-Tenant:** Setiap merchant memiliki konfigurasi enkripsi API Key, batas *retry*, dan URL endpoint bank mitra yang berbeda. Konfigurasi ini disimpan di centralized database/vault dan dapat diubah sewaktu-waktu oleh Merchant via Dashboard tanpa restart sistem.
2.  **Masalah Latensi:** Pengambilan konfigurasi via database I/O pada setiap transaksi secara langsung menimbulkan *database bottleneck* dan latensi tinggi (+80ms per request).
3.  **Masalah Memory Leak:** Upaya tim sebelumnya meng-cache konfigurasi di Singleton Service menyebabkan *stale data* dan kebocoran memori karena dynamic service creation tidak terkelola dengan baik pada IoC scope.

### Solusi Desain
1.  Bangun **Custom Configuration Provider** terkomputasi di memory dengan background reloading via polling/change-tokens.
2.  Buat **Tenant Context Resolver** yang hidup di level `Scoped`.
3.  Gunakan pola **Factory + Keyed Services** (.NET 8) untuk mengisolasi gateway client per tenant secara deterministik.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur lengkap Custom Configuration Source dan Dynamic Multi-Tenant Provider:

```csharp
using System.Collections.Concurrent;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Primitives;

namespace Enterprise.Fintech.Core;

// 1. DATA MODEL FOR TENANT CONFIGURATION
public record TenantPaymentConfig(string MerchantId, string ApiKey, string GatewayUrl, int TimeoutMs);

// 2. CUSTOM CONFIGURATION SOURCE & PROVIDER (Thread-Safe & Reloadable)
public class TenantDatabaseConfigurationSource : IConfigurationSource
{
    public IConfigurationProvider Build(IConfigurationBuilder builder)
    {
        return new TenantDatabaseConfigurationProvider();
    }
}

public class TenantDatabaseConfigurationProvider : ConfigurationProvider
{
    private readonly Timer _reloadTimer;

    public TenantDatabaseConfigurationProvider()
    {
        // Polling setiap 30 detik untuk mendeteksi perubahan konfigurasi dari database
        _reloadTimer = new Timer(_ => LoadDataFromDatabase(), null, Timeout.Infinite, Timeout.Infinite);
    }

    public override void Load()
    {
        LoadDataFromDatabase();
        // Aktifkan timer berkala setelah pembacaan awal
        _reloadTimer.Change(TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
    }

    private void LoadDataFromDatabase()
    {
        // Simulasi query database / Vault:
        var externalData = FetchMockDataFromDatabase();

        var newDictionary = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);

        foreach (var tenant in externalData)
        {
            // Meratakan hierarki (flattening) ke format path IConfiguration
            // Format: Tenants:{MerchantId}:{Property}
            newDictionary[$"Tenants:{tenant.MerchantId}:ApiKey"] = tenant.ApiKey;
            newDictionary[$"Tenants:{tenant.MerchantId}:GatewayUrl"] = tenant.GatewayUrl;
            newDictionary[$"Tenants:{tenant.MerchantId}:TimeoutMs"] = tenant.TimeoutMs.ToString();
        }

        // Bandingkan apakah ada data yang berubah
        if (!DictionariesAreEqual(Data, newDictionary))
        {
            Data = newDictionary;
            OnReload(); // Trigger IChangeToken reload notifications
        }
    }

    private static List<TenantPaymentConfig> FetchMockDataFromDatabase()
    {
        return
        [
            new("MERCHANT-ALPHA", "SEC-KEY-ALPHA-12345", "https://bank-a.com/api", 5000),
            new("MERCHANT-BETA", "SEC-KEY-BETA-99999", "https://bank-b.com/api", 3000)
        ];
    }

    private static bool DictionariesAreEqual(IDictionary<string, string?> first, IDictionary<string, string?> second)
    {
        if (first.Count != second.Count) return false;
        foreach (var pair in first)
        {
            if (!second.TryGetValue(pair.Key, out var val) || val != pair.Value)
                return false;
        }
        return true;
    }
}

// 3. EXTENSION METHODS
public static class CustomConfigurationExtensions
{
    public static IConfigurationBuilder AddTenantDatabaseSource(this IConfigurationBuilder builder)
    {
        return builder.Add(new TenantDatabaseConfigurationSource());
    }
}

// 4. TENANT ACCESSOR ABSTRACTION
public interface ITenantContextAccessor
{
    string CurrentTenantId { get; set; }
}

public class TenantContextAccessor : ITenantContextAccessor
{
    // Scoped request context
    public string CurrentTenantId { get; set; } = string.Empty;
}

// 5. SECURE RUNTIME RESOLVER FOR MERCHANTS
public interface IPaymentGatewayExecutor
{
    Task<string> ExecutePaymentAsync(decimal amount);
}

public class PaymentGatewayExecutor : IPaymentGatewayExecutor
{
    private readonly ITenantContextAccessor _tenantAccessor;
    private readonly IConfiguration _configuration;
    private readonly IHttpClientFactory _httpClientFactory;

    public PaymentGatewayExecutor(
        ITenantContextAccessor tenantAccessor,
        IConfiguration configuration,
        IHttpClientFactory httpClientFactory)
    {
        _tenantAccessor = tenantAccessor;
        _configuration = configuration;
        _httpClientFactory = httpClientFactory;
    }

    public async Task<string> ExecutePaymentAsync(decimal amount)
    {
        var tenantId = _tenantAccessor.CurrentTenantId;
        if (string.IsNullOrWhiteSpace(tenantId))
        {
            throw new InvalidOperationException("Tenant Context tidak teridentifikasi pada pipeline!");
        }

        // Pembacaan konfigurasi instan melalui internal memory provider
        var apiKey = _configuration[$"Tenants:{tenantId}:ApiKey"];
        var gatewayUrl = _configuration[$"Tenants:{tenantId}:GatewayUrl"];
        var timeout = _configuration.GetValue<int>($"Tenants:{tenantId}:TimeoutMs");

        if (apiKey == null || gatewayUrl == null)
        {
            throw new KeyNotFoundException($"Merchant '{tenantId}' tidak memiliki konfigurasi gateway valid!");
        }

        var client = _httpClientFactory.CreateClient("PaymentClient");
        client.Timeout = TimeSpan.FromMilliseconds(timeout);

        // Simulasi request payment
        return await Task.FromResult($"Transacted {amount} for {tenantId} via {gatewayUrl}. Key: {apiKey[..4]}****");
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Built-in DI vs Third-Party (Contoh: Autofac)

| Aspek | Built-in (`Microsoft.Extensions.DI`) | Autofac / Lamar / Castle Windsor |
| :--- | :--- | :--- |
| **Throughput / Allocation** | **Ekstrem.** Dioptimalkan langsung oleh tim runtime Core CLR. Hampir tanpa alokasi memori berlebih. | Cenderung lebih lambat dan menghasilkan alokasi object graf yang lebih besar. |
| **Fitur Lanjutan** | Terbatas pada konstruktor murni, Keyed Services (.NET 8+). Tidak mendukung Property Injection out-of-the-box. | Sangat kaya: Circular Dependency Resolution, Interception (AOP), Named Modules, Property Injection. |
| **Kompabilitas Framework** | Standar default ASP.NET Core, minimal risiko *breaking change* pada versi .NET baru. | Bergantung pada pembaruan pustaka pihak ketiga pihak komunitas. |

### 2. Evaluasi Options Pattern: Memory vs Freshness

```
                Kecepatan Akses / Alokasi Rendah
                     IOptions<T>
                         ▲
                        / \
                       /   \
                      /     \
  IOptionsSnapshot<T> ◄──────► IOptionsMonitor<T>
 Freshness Per-Request        Real-time Event Notifications
 (Scoped Memory Cache)        (Singleton Memory Footprint)
```

*   **Pilih `IOptions<T>`**: Jika konfigurasi benar-benar statis (misal: AWS Region, Application Identity) yang nilainya hanya didapatkan saat cold-booting container instance.
*   **Pilih `IOptionsSnapshot<T>`**: Jika konfigurasi sering berubah saat runtime (misal: Feature Flags per-request) dan hanya dikonsumsi oleh `Scoped` services.
*   **Pilih `IOptionsMonitor<T>`**: Jika nilai konfigurasi harus direfleksikan seketika di dalam `Singleton` components (misal: Dynamic Thread Pool Sizing, Dynamic Circuit Breaker Threshold).

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Captive Dependency di Dalam Background Service (`IHostedService`)
`BackgroundService` diregistrasikan sebagai **Singleton**. Jika Anda menyuntikkan `DbContext` atau dependensi scoped lainnya langsung ke dalam konstruktor `BackgroundService`, Anda akan mengalami *Captive Dependency Crash*.

**Solusi:** Inject `IServiceScopeFactory`, lalu buat *manual scope* di dalam loop pemrosesan.

```csharp
public class QueueWorker : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;

    public QueueWorker(IServiceScopeFactory scopeFactory)
    {
        _scopeFactory = scopeFactory;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            // PEMBUATAN MANUAL SCOPE BOUNDARY
            using (var scope = _scopeFactory.CreateScope())
            {
                var dbContext = scope.ServiceProvider.GetRequiredService<MyDbContext>();
                await dbContext.ProcessPendingQueueAsync(stoppingToken);
            } // Di sini MyDbContext secara deterministik dieksekusi Dispose()-nya!

            await Task.Delay(5000, stoppingToken);
        }
    }
}
```

### 2. Disposing Asinkron (`IAsyncDisposable`)
Jika dependensi Scoped Anda mengimplementasikan `IAsyncDisposable` (misal: `SqlConnection`, `BlobStream`), tetapi Anda membuat scope manual menggunakan `using (var scope = ...)` sintaks sinkron, maka metode dispose sinkron akan dipaksa berjalan secara *sync-over-async*, yang berpotensi memicu *deadlock* pada thread pool.

**Mitigasi:** Selalu gunakan `await using` untuk resolusi scope manual jika ada service asinkron:
```csharp
await using (var asyncScope = _scopeFactory.CreateAsyncScope())
{
    var asyncService = asyncScope.ServiceProvider.GetRequiredService<ITransferChannel>();
    await asyncService.StreamDataAsync();
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Anti-Pattern: Mengakses `IServiceProvider` Secara Langsung di Bisnis Layer

```csharp
// FATAL ERROR: Service Locator Anti-Pattern
public class InvoiceService
{
    private readonly IServiceProvider _provider;
    public InvoiceService(IServiceProvider provider) => _provider = provider;

    public void GenerateInvoice()
    {
        // Menyembunyikan dependency, menyulitkan unit testing, bypass graf engine
        var taxService = _provider.GetRequiredService<ITaxService>();
        taxService.Compute();
    }
}

// BENAR: Nyatakan dependency secara eksplisit di konstruktor
public class InvoiceService
{
    private readonly ITaxService _taxService;
    public InvoiceService(ITaxService taxService) => _taxService = taxService;

    public void GenerateInvoice()
    {
        _taxService.Compute();
    }
}
```

### 2. Delimiter Konfigurasi Lintas Sistem Operasi
*   **Kesalahan:** Menggunakan colon `:` saat mendeklarasikan Environment Variables di Docker atau Linux bash:
    `ENV DatabaseSettings:ConnectionString="Server=..."` (Gagal pada sistem Linux tertentu).
*   **Perbaikan:** Gunakan standard double underscore `__` yang secara otomatis dipetakan oleh .NET Configuration Provider menjadi separator hierarki:
    `ENV DatabaseSettings__ConnectionString="Server=..."`

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Enkapsulasi Registrasi dengan Extension Methods:** Kelompokkan registrasi dependensi berdasarkan domain arsitektur. Jangan mencemari `Program.cs` dengan ratusan baris registrasi.
    ```csharp
    // Program.cs
    builder.Services.AddInfrastructureServices(builder.Configuration);
    builder.Services.AddApplicationServices();
    ```
2.  **Immutability Configuration Options:** Selalu gunakan modifier `init` atau deklarasikan properti options sebagai immutable class/records untuk mencegah modifikasi tidak sengaja di tingkat bisnis runtime.
3.  **Fail-Fast Configuration Pattern:**
    Jangan pernah membiarkan konfigurasi yang salah terbaca saat ada user yang menyentuh endpoint. Gunakan `.ValidateOnStart()` bersamaan dengan `ValidateDataAnnotations()`.
4.  **Hindari Membuka Multi-Scope Paralel pada Request yang Sama:** Satu HTTP request = Satu Scope. Jangan memecah `Task.Run` di dalam controller dan mencoba meneruskan `IServiceProvider` request ke thread latar belakang tersebut.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1.  **Hindari Refleksi Berulang via ActivatorUtilities:** Jika Anda sering menginstansiasi objek runtime secara dinamis, jangan gunakan `Activator.CreateInstance`. Manfaatkan `ObjectFactory` terkompilasi dari:
    ```csharp
    // Compile factory delegate sekali di Singleton level
    private static readonly ObjectFactory _orderFactory = 
        ActivatorUtilities.CreateFactory(typeof(OrderProcessor), [typeof(IOrderSource)]);
    ```
2.  **Matikan `ValidateScopes` di Production:** Validasi scope memerlukan pengecekan metadata type graf yang membebani alokasi startup dan CPU.
    ```csharp
    builder.Host.UseDefaultServiceProvider((context, options) =>
    {
        options.ValidateScopes = context.HostingEnvironment.IsDevelopment();
        options.ValidateOnBuild = context.HostingEnvironment.IsDevelopment();
    });
    ```
3.  **Gunakan Keyed Services daripada Multi-Implementation Enumeration:** Pada .NET 8, daripada meng-inject `IEnumerable<IPaymentStrategy>` lalu melakukan LINQ `.First(x => x.Type == current)` pada setiap request, gunakan native `AddKeyedScoped`:
    ```csharp
    builder.Services.AddKeyedScoped<IPaymentStrategy, CreditCardStrategy>("credit");
    builder.Services.AddKeyedScoped<IPaymentStrategy, CryptoStrategy>("crypto");

    // Di Controller / Minimal API:
    app.MapPost("/pay", ([FromKeyedServices("credit")] IPaymentStrategy strategy) => ...);
    ```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Redirection of Sensitive Configuration Secrets:**
    *   Jangan pernah menyimpan password, secret key, atau token di `appsettings.json`.
    *   Di lingkungan produksi, gunakan provider pihak ketiga seperti HashiCorp Vault, AWS Secrets Manager, atau Azure Key Vault.
    *   Di level development, gunakan **Secret Manager Tool**:
        `dotnet user-secrets set "Payment:SecretKey" "dev-key-123"`
2.  **Sanitisasi Configuration Dumps (Logging Prevention):**
    Saat melakukan debugging konfigurasi, hindari mencetak seluruh `IConfigurationRoot.GetDebugView()`. Ini akan mengekspos semua database credentials dan secret keys ke logs monitoring (*Plaintext Exposure*).
3.  **Validation Masking:** Selalu implementasikan custom logging sanitizer jika ada opsi konfigurasi yang gagal divalidasi agar *connection string* tidak ikut termuntahkan ke log file dalam bentuk teks terbuka.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendeteksi dependensi yang bermasalah secara programatik sebelum aplikasi mengalami crash di production, kita dapat mengaitkan logging diagnostics pada pipeline startup:

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// INSPEKSI DEPENDENCY INJECTION SECARA PROGRAMATIK DI DEV MODE
if (app.Environment.IsDevelopment())
{
    var configurationRoot = (IConfigurationRoot)app.Configuration;
    
    // Dump struktur provider konfigurasi
    foreach (var provider in configurationRoot.Providers)
    {
        app.Logger.LogInformation("Configuration Provider Aktif: {ProviderType}", provider.GetType().Name);
    }
}
```

Jika terjadi masalah "Dependency cannot be resolved", gunakan tools:
*   Melihat Call Tree Dependency: Jalankan aplikasi dengan environment variable `DOTNET_PRINT_TELEMETRY_MESSAGE=1`.
*   Aktifkan internal logging Core DI dengan menambahkan filter level trace di `appsettings.Development.json`:
    ```json
    "Logging": {
      "LogLevel": {
        "Microsoft.Extensions.DependencyInjection": "Trace"
      }
    }
    ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Matrix Lifecycle DI ASP.NET Core

| Tipe Registrasi | Instansiasi Objek | Kapan Di-Dispose? | Cocok Untuk | Bahaya Terbesar |
| :--- | :--- | :--- | :--- | :--- |
| **`AddTransient<T>`** | Setiap dipanggil / di-resolve. | Bersamaan dengan Scope tempat dia dibuat. | Lightweight stateless logic. | Memory leak jika resolve IDisposable dari root provider. |
| **`AddScoped<T>`** | 1x per `IServiceScope` (HTTP Request). | Saat HTTP Request / Scope berakhir. | Context data, database connection (`DbContext`). | Captive dependency (disuntikkan ke Singleton). |
| **`AddSingleton<T>`** | 1x seumur hidup aplikasi. | Saat aplikasi dimatikan (*graceful shutdown*). | Global state, caches, single network clients. | Race Condition / Thread-safety bug. |

### 2. Matrix Perbedaan Options Family

| Interface | Lifecycle | Mengikuti Perubahan Config File? | Bisa Masuk Singleton? |
| :--- | :--- | :--- | :--- |
| **`IOptions<T>`** | Singleton | **Tidak** (Static snapshot awal) | **Ya** |
| **`IOptionsSnapshot<T>`** | Scoped | **Ya** (Dievaluasi ulang per request) | **Tidak** (Throw Scope Exception) |
| **`IOptionsMonitor<T>`** | Singleton | **Ya** (Mendengarkan event perubahan) | **Ya** |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman teknis Anda dengan menganalisis pertanyaan berikut:

### Kategori Basic
1.  **Pertanyaan:** Apa yang terjadi jika sebuah service ber-lifetime `Transient` yang mengimplementasikan `IDisposable` di-resolve langsung dari root provider (`app.Services.GetRequiredService<T>()`)?
    *   *Jawaban Teknis:* Objek tersebut akan diinstansiasi dan dimasukkan ke dalam daftar pembersihan internal (`_disposables`) milik root container. Karena root container tidak pernah mati sampai aplikasi berhenti sepenuhnya, objek tersebut tidak akan pernah dipungut oleh Garbage Collector (GC), menimbulkan *Memory Leak*.
2.  **Pertanyaan:** Kapan konstruktor sebuah service dengan lifetime `Singleton` dieksekusi?
    *   *Jawaban Teknis:* Secara default, dieksekusi secara *lazy* pada saat service tersebut pertama kali diminta (di-resolve). Namun, jika kita menggunakan metode overload `AddSingleton(new MyService())`, konstruktor dieksekusi secara *eager* pada saat fase konfigurasi sebelum runtime pipeline berjalan.
3.  **Pertanyaan:** Antara `appsettings.json`, `Environment Variables`, dan `CommandLineArgs`, mana yang memiliki prioritas penimpaan (*override*) tertinggi secara default di ASP.NET Core?
    *   *Jawaban Teknis:* `CommandLineArgs` memiliki prioritas tertinggi, menimpa `Environment Variables`, dan `Environment Variables` menimpa `appsettings.json`.
4.  **Pertanyaan:** Mengapa method `IServiceScopeFactory.CreateScope()` wajib dibungkus dalam blok `using` atau `await using`?
    *   *Jawaban Teknis:* Blok `using` memastikan pemanggilan metode `Dispose()` pada scope. Tanpa pemanggilan `Dispose()`, semua resource yang diciptakan dalam scope tersebut (termasuk koneksi database dan instance scoped lainnya) tidak akan dilepaskan secara deterministik ke resource pool.
5.  **Pertanyaan:** Apa fungsi parameter `ValidateScopes = true` pada runtime options?
    *   *Jawaban Teknis:* Parameter tersebut memvalidasi dependensi secara agresif untuk memastikan bahwa service dengan lifetime Scoped tidak pernah di-resolve secara langsung ataupun tidak langsung dari Root Container maupun dari service ber-lifetime Singleton.

### Kategori Intermediate
6.  **Pertanyaan:** Mengapa Anda tidak bisa meng-inject `IOptionsSnapshot<T>` ke dalam konstruktor sebuah service yang terdaftar sebagai `Singleton`?
    *   *Jawaban Teknis:* Karena `IOptionsSnapshot<T>` didaftarkan dengan lifetime `Scoped` (agar dapat membaca ulang konfigurasi per request). Menyuntikkannya ke `Singleton` akan melanggar aturan dependency boundary dan memicu `InvalidOperationException` jika scope validation diaktifkan.
7.  **Pertanyaan:** Apa perbedaan fundamental internal antara `IOptionsSnapshot<T>` dan `IOptionsMonitor<T>` dalam merespons reload konfigurasi?
    *   *Jawaban Teknis:* `IOptionsSnapshot<T>` membaca ulang konfigurasi secara sinkron pada saat scope baru dibentuk dan menguncinya selama siklus hidup scope tersebut. Sedangkan `IOptionsMonitor<T>` mendaftarkan listener ke `IChangeToken` sumber konfigurasi dan memperbarui nilainya seketika (*real-time push updates*) pada instance Singleton yang sama melalui `.CurrentValue`.
8.  **Pertanyaan:** Dalam konteks kompilasi Expression Tree internal pada ASP.NET Core DI (`DynamicServiceProviderEngine`), apa yang terjadi saat service yang sama di-resolve berulang kali ribuan kali?
    *   *Jawaban Teknis:* Pada resolusi awal, engine menginterpretasikan graf menggunakan refleksi ekspresi untuk menghemat startup time. Setelah ambang batas pemanggilan terlampaui, engine memicu kompilasi latar belakang yang menghasilkan Dynamic IL-Emit delegate (*compiled call site*), memangkas overhead pemanggilan ekspresi refleksi ke performa setara pemanggilan kode C# langsung.
9.  **Pertanyaan:** Misalkan Anda memiliki 2 service: `ServiceA` (Singleton) dan `ServiceB` (Scoped). Bagaimana cara aman bagi `ServiceA` untuk memanggil fungsionalitas `ServiceB` tanpa menyebabkan *Captive Dependency*?
    *   *Jawaban Teknis:* `ServiceA` tidak boleh meng-inject `ServiceB` di konstruktor. Sebagai gantinya, `ServiceA` meng-inject `IServiceScopeFactory`. Ketika sebuah metode di `ServiceA` butuh mengeksekusi `ServiceB`, metode tersebut harus membuat scope sementara secara on-demand: `using (var scope = _scopeFactory.CreateScope()) { var b = scope.ServiceProvider.GetRequiredService<ServiceB>(); b.Execute(); }`.
10. **Pertanyaan:** Apa bahaya penggunaan metode `IConfiguration.Get<T>()` berulang-ulang di dalam hot path eksekusi HTTP Request dibandingkan menggunakan `IOptions<T>`?
    *   *Jawaban Teknis:* `IConfiguration.Get<T>()` menggunakan mekanisme refleksi penuh untuk memetakan key-value string ke POCO properties pada setiap kali pemanggilan, yang menghasilkan alokasi memori heap tinggi dan konsumsi CPU besar. Sebaliknya, `IOptions<T>` hanya memetakan konfigurasi satu kali dan me-cache referensi instansinya di memori.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Enterprise Fault-Tolerant Dynamic Configuration Hub"

### Skenario
Sebuah sistem High-Frequency Processing Engine membutuhkan module konfigurasi independen yang memuat batas Rate Limiting per IP dan skema fallback API secara dinamis tanpa pernah melakukan *restart process*.

### Instruksi Tugas

1.  **Inisialisasi Project:**
    Buat Web API project baru (.NET 8):
    ```bash
    dotnet new web -n DynamicConfigEngine
    cd DynamicConfigEngine
    ```
2.  **Spesifikasi Requirement:**
    *   Buat kelas konfigurasi `RateLimitingRules`:
        *   `MaxRequestsPerMinute` (int, 10–10000).
        *   `WhitelistedIps` (string array, validasi format IP address).
        *   `EnableAdaptiveThrottling` (boolean).
    *   Terapkan **Fail-Fast Validation**: Jika konfigurasi `MaxRequestsPerMinute` diisi di bawah 10 pada `appsettings.json`, aplikasi harus gagal booting (*crash on start*) dan memunculkan error message yang terstruktur.
    *   Implementasikan **Custom Configuration Source** yang membaca aturan dari sebuah file teks mentah lokal `emergency-rules.txt` yang berisi instruksi:
        ```text
        EMERGENCY_SHUTDOWN=FALSE
        RATE_LIMIT_OVERRIDE=50
        ```
    *   Pastikan konfigurasi dari file `emergency-rules.txt` ini mendengarkan perubahan file (*file system watcher / change token*) sehingga ketika Anda mengubah teks di dalamnya dan menyimpannya (Save), nilai konfigurasi pada engine langsung berubah tanpa restart!
    *   Sediakan sebuah middleware atau endpoint `/check-rate-limit` yang mengonsumsi konfigurasi ini menggunakan `IOptionsMonitor<RateLimitingRules>`.
    *   Buat background worker (`IHostedService`) yang secara periodik (setiap 5 detik) menulis log nilai konfigurasi saat ini ke konsol, dengan membuktikan bahwa implementasi dependency injection pada Singleton BackgroundService tersebut **bebas dari Captive Dependency**.

### Kriteria Kelulusan Evaluasi
1.  Aplikasi menolak jalan jika input `appsettings.json` tidak lolos validasi Data Annotations saat booting (`ValidateOnStart()`).
2.  File `emergency-rules.txt` dapat diubah saat aplikasi sedang aktif, dan endpoint `/check-rate-limit` langsung merefleksikan nilai baru tersebut.
3.  Tidak ditemukan eksekusi Service Locator `provider.GetService<T>()` di dalam endpoint handler maupun di layer bisnis. Semua dependensi disuntikkan secara deklaratif via *Constructor Injection* atau *Method Injection* (Minimal APIs).
4.  Background Worker berjalan kontinu tanpa melempar `ObjectDisposedException` atau memicu *Memory Leak*.