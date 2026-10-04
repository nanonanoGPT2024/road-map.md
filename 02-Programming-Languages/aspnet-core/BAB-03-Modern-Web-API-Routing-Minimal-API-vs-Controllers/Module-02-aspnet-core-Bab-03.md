# Kurikulum Rekayasa Perangkat Lunak: ASP.NET Core Enterprise
## Kategori: 02-Programming-Languages
### BAB 03: Modern Web API Routing, Minimal API vs Controllers
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Menganalisis dan merekayasa struktur perutean internal ASP.NET Core berbasis *Deterministic Finite Automaton* (DFA) Matcher dan *Endpoint Routing Middleware*.
*   Mengevaluasi secara mendalam perbedaan arsitektural, alokasi memori, latensi, dan mekanisme eksekusi antara Controller (`ActionInvoker`) dan Minimal API (`RequestDelegateFactory` & Source Generators).
*   Mengimplementasikan teknik *advanced routing*: kustomisasi *Route Constraints*, *Endpoint Filters*, parameter transformers, dan *Route Groups* modular pada skala enterprise.
*   Mengonfigurasi dan mengoptimalkan pemrosesan *high-throughput payload* menggunakan zero/low-allocation streaming (`PipeReader`, `IAsyncEnumerable<T>`) dan Native AOT (*Ahead-Of-Time*) compilation.
*   Mendiagnosis dan memitigasi *route collisions*, *thread pool starvation*, dan *memory leak* akibat penangkapan *scoped services* yang tidak tepat dalam *endpoint delegates*.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
*   Pemrograman C# Modern (C# 12/C# 13): *Pattern Matching, Records, Primary Constructors, ref struct, Async Streams*.
*   Fondasi ASP.NET Core: Siklus hidup HTTP, Middleware Pipeline, Kestrel Web Server, Dependency Injection (DI) Service Lifetimes.
*   Memahami dasar spesifikasi HTTP/1.1, HTTP/2, and HTTP/3 (Multiplexing, Framing, Streaming semantics).
*   Pengalaman implementasi Web API berbasis ASP.NET Core MVC Controller.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Evolusi Pipeline: Dari Legacy IRouter ke Endpoint Routing (DFA Matcher)
Pada arsitektur warisan (ASP.NET Core pre-2.2), *routing* terikat langsung ke dalam *MVC middleware pipeline*. Keputusan rute baru dievaluasi saat *MVC Middleware* dieksekusi, mengakibatkan middleware sebelumnya (seperti `AuthenticationMiddleware` atau `CorsMiddleware`) tidak memiliki visibilitas terhadap endpoint target.

Sejak ASP.NET Core 3.0 hingga .NET 8/9, diterapkan arsitektur **Endpoint Routing** yang membagi proses perutean menjadi dua fase terpisah:
1.  **Selection (`EndpointRoutingMiddleware`):** Mengevaluasi HTTP request URL, HTTP Verb, dan Header untuk menentukan `Endpoint` mana yang cocok menggunakan **DFA Graph Matcher**. Metadata endpoint (seperti Authorization policies, CORS policies, Rate limiting) dilekatkan pada `HttpContext.GetEndpoint()`.
2.  **Execution (`EndpointMiddleware`):** Menjalankan `RequestDelegate` yang terikat pada endpoint tersebut setelah seluruh middleware perantara (auth, compression, rate-limiting) selesai bekerja.

```
Incoming Request
       │
       ▼
┌─────────────────────────────────┐
│     EndpointRoutingMiddleware   │ ──► Eksekusi DfaMatcher (Pencarian O(1) state tree)
└─────────────────────────────────┘ ──► Menetapkan HttpContext.SetEndpoint(endpoint)
       │
       ▼
┌─────────────────────────────────┐
│   Authentication / Authorization│ ──► Membaca Endpoint.Metadata (AuthorizeAttribute)
└─────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│       EndpointMiddleware        │ ──► Menjalankan endpoint.RequestDelegate()
└─────────────────────────────────┘
```

#### 3.2 Anatomi DFA (Deterministic Finite Automaton) Matcher
Saat aplikasi melakukan bootstrap melalui `app.MapGet()` atau `app.MapControllers()`, ASP.NET Core membangun *tree-structured state machine* via `DfaMatcherBuilder`.
*   Setiap segmen URL dipecah menjadi *node* transisi.
*   Segmen literal (misal: `/api/orders`) diprioritaskan di atas segmen parameter (misal: `/api/{id}`), dan parameter diprioritaskan di atas *catch-all* (misal: `/api/{**slug}`).
*   Pemeriksaan *Route Constraints* dilakukan langsung di dalam node transisi DFA, meminimalkan *backtracking*.
*   Hasil kompilasi berupa tabel lompatan (*jump table*) yang dievaluasi dengan kompleksitas mendekati $O(L)$, di mana $L$ adalah jumlah segmen URL, independen dari total jumlah endpoint yang terdaftar ($O(1)$ terhadap ukuran koleksi rute).

#### 3.3 Minimal API vs Controllers: Arsitektur Eksekusi Internal

```
[ HTTP REQUEST DITERIMA OLEH KESTREL ]
                  │
                  ▼
         [ DFA Route Matching ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
 [ Controller Action ]  [ Minimal API Endpoint ]
        │                   │
        ▼                   ▼
ActionDescriptorFactory  RequestDelegateFactory (RDF)
        │                   │
Filter Pipeline (5 types)   EndpointFilter Pipeline
        │                   │
ModelMetadataProvider   ParameterBindingMethodCache
        │                   │
Complex ModelBinder     Source Generated / Direct Binder
(Type Activation, Val)      (Native AOT Friendly)
        │                   │
Reflective Invoke       Compiled Expression / Direct Invoke
        │                   │
IActionResultExecutor   IResult.ExecuteAsync()
        │                   │
        └─────────┬─────────┘
                  ▼
      [ PipeWriter ke Kestrel ]
```

##### Controller Architecture (`ActionInvoker` Pipeline)
*   **Aktivasi:** Melibatkan alokasi controller instance per request via `IControllerActivator`.
*   **Binding:** Menjalankan `IModelBinderFactory`, `ICompositeModelBinder`, `IModelValidator` (FluentValidation atau DataAnnotations), yang memicu alokasi heap besar untuk *binding context*, *validation dictionaries*, dan *reflection caches*.
*   **Filter Pipeline:** 5 level filter (*Authorization, Resource, Action, Exception, Result*) yang dieksekusi secara serial melalui nested state machines.
*   **Eksekusi:** Melibatkan invokasi `ActionMethodExecutor` yang membungkus pemanggilan reflektif method C#.

##### Minimal API Architecture (`RequestDelegateFactory` Engine)
*   **Kompilasi:** Pada fase start-up (atau saat build via *RDG - Request Delegate Generator* pada .NET 8/9 Native AOT), `RequestDelegateFactory.Create()` mengompilasi parameter handler ke dalam ekspresi terkompilasi (*compiled lambda expression*) atau kode C# statis.
*   **Binding:** Menggunakan inferensi statis berbasis convention:
    *   `T` terdaftar di DI? Diambil dari `IServiceProvider`.
    *   `T` adalah `HttpContext`, `HttpRequest`, `ClaimsPrincipal`, `CancellationToken`? Di-inject secara direct access.
    *   `TryParse` atau `BindAsync` terdefinisi? Dipanggil langsung tanpa perantara `IModelBinder`.
    *   Tipe primitif/string? Diambil dari `RouteValueDictionary` atau `IQueryCollection`.
    *   Tipe kompleks? Dideserialisasi langsung via `System.Text.Json` dari request body stream (`HttpRequest.BodyReader`).
*   **Zero-Overhead Results:** Menggunakan antarmuka `IResult` (seperti `TypedResults.Ok()`) yang langsung menulis byte ke Kestrel `PipeWriter` tanpa abstraksi perantara `ActionContext` atau `IActionResultExecutor`.

---

### 4. Why & What

| Dimensi | Controller-based API | Minimal API |
| :--- | :--- | :--- |
| **Pola Arsitektur** | Model-View-Controller / Component-per-Controller | Route-to-Code / Micro-endpoints / Vertical Slice |
| **Alokasi Memori (Per-Request)** | Tinggi (~2KB - 8KB dasar per request) karena aktivasi context dan binding reflection | Mendekati nol (~200B - 500B dasar per request) |
| **Cold-Start & Throughput** | Lebih lambat saat startup akibat reflection scanning pada seluruh controller assembly | Startup instan, throughput RPS (Requests Per Second) hingga 15-30% lebih tinggi |
| **Dukungan Native AOT** | Buruk/Sangat Sulit (bergantung heavily pada dynamic runtime reflection) | Sangat Baik (didukung native oleh .NET 8/9 RDG Source Generators) |
| **Ekosistem & Ekstensibilitas** | Ekosistem warisan sangat matang (Filter pipeline granular, Model Binder kompleks) | Ringkas, berbasis `EndpointFilter`, komposisi fungsional |

*   **Kapan Menggunakan Minimal API:** Microservices berlatensi sangat rendah, arsitektur *Native AOT*, integrasi *Serverless (AWS Lambda/Azure Functions)*, gateway routing throughput tinggi, serta aplikasi baru berbasis *Vertical Slice Architecture*.
*   **Kapan Menggunakan Controller:** Aplikasi enterprise warisan (*monolith* besar) yang sangat terikat dengan *MVC filter pipeline* ekstensif, konvensi multi-action kompleks dengan konvensi global yang sulit dimigrasikan ke endpoint filters.

---

### 5. How (Workflow Detail)

#### Siklus Hidup Eksekusi Request pada Minimal API dengan Endpoint Filter

1.  **Socket Layer:** Kestrel menerima byte framing dari client, menginstansiasi `HttpContext`.
2.  **Route Match:** `EndpointRoutingMiddleware` mengevaluasi rute via DFA Matcher. Ditemukan kecocokan endpoint Minimal API.
3.  **Endpoint Metadata Resolution:** Middleware pipeline mengeksekusi *Cors*, *Authentication*, *Authorization*, dan *Rate Limiting* berdasarkan metadata yang ditempelkan melalui extension methods (misal: `.RequireAuthorization()`, `.RequireRateLimiting()`).
4.  **Endpoint Invocation:** `EndpointMiddleware` memanggil `RequestDelegate`.
5.  **Filter Invocation Chain:**
    *   Endpoint Filter 1: Pre-invocation (validasi parameter, tracing context propagation).
    *   Endpoint Filter 2: Execution gate (misal: payload auditing).
    *   Target Method: Pemanggilan method/delegate bisnis logic.
    *   Endpoint Filter 2: Post-invocation handling.
    *   Endpoint Filter 1: Post-invocation handling.
6.  **Direct Response Serialization:** Instance `IResult` (misal: `Results.Ok(dto)`) mengeksekusi `ExecuteAsync(HttpContext)`. Serializer `System.Text.Json` langsung menulis payload terkompresi ke `HttpContext.Response.BodyWriter` (`PipeWriter`).
7.  **Socket Flush:** Flush buffer ke soket kernel tanpa pemanggilan model formatting MVC.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (Controller) vs Pintu Otomatis Fast-Track (Minimal API)
*   **Controller (Bandara Internasional):** Setiap penumpang (request) harus melewati aula pusat, masuk ke loket konvensional, diinspeksi oleh petugas bagasi, dicek berkas identitasnya melalui berbagai divisi birokrasi berulang kali (Action Filters, Model Binders, Controller Activator), baru diperbolehkan naik pesawat. Aman dan sangat terstruktur, tetapi biayanya tinggi dan lambat.
*   **Minimal API (Fast-Track Biometrik):** Penumpang langsung diarahkan ke gerbang otomatis berbasis sensor wajah (DFA Matcher). Sensor membaca tiket langsung (Compiled Delegate Binder), pintu terbuka seketika, dan penumpang langsung duduk di pesawat. Minimal interaksi manusia, alokasi energi mendekati nol, dan throughput sangat tinggi.

#### Diagram DFA Routing Table Lookup

```
                 [ ROOT NODE "/" ]
                        │
                  api (Literal)
                        │
                 [ NODE "/api" ]
                        │
                orders (Literal)
                        │
               [ NODE "/api/orders" ]
               ├── (GET)  ──► ListOrdersDelegate
               ├── (POST) ──► CreateOrderDelegate
               └── {id:guid} (Constraint Node: Guid)
                        │
             [ NODE "/api/orders/{id}" ]
             ├── (GET)    ──► GetOrderByIdDelegate
             └── (DELETE) ──► DeleteOrderByIdDelegate
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Advanced Route Constraints & Binding
Menggunakan Route Constraint bawaan dan inline regex, serta multiple parameter source.

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// Constraint: id harus integer positif, status regex terbatas pada Enum string
app.MapGet("/api/v1/warehouses/{warehouseId:int:min(1)}/inventory/{status:regex(^(in-stock|backordered|discontinued)$)}", 
    (int warehouseId, string status, [FromQuery] int? page, [FromQuery] int? pageSize) =>
{
    return TypedResults.Ok(new
    {
        WarehouseId = warehouseId,
        Status = status,
        Page = page ?? 1,
        PageSize = pageSize ?? 50
    });
})
.WithName("GetWarehouseInventory");

app.Run();
```

#### 7.2 Practical Example: Production-Grade Modular Minimal API dengan Endpoint Filters & TypedResults

Berikut arsitektur produksi modular menggunakan `RouteGroupBuilder`, zero-allocation `TypedResults`, dan endpoint filtering untuk *request validation*:

##### Kontrak & Model
```csharp
// Domain/Models.cs
namespace Enterprise.Routing.Domain;

public readonly record struct CreatePaymentRequest(
    decimal Amount, 
    string Currency, 
    string AccountNumber, 
    string IdempotencyKey);

public readonly record struct PaymentResponse(
    Guid TransactionId, 
    string Status, 
    DateTime UtcTimestamp);
```

##### Custom Route Constraint
```csharp
// Infrastructure/Routing/CurrencyRouteConstraint.cs
namespace Enterprise.Routing.Infrastructure.Routing;

public sealed class CurrencyRouteConstraint : IRouteConstraint
{
    private static readonly HashSet<string> SupportedCurrencies = new(StringComparer.OrdinalIgnoreCase)
    {
        "USD", "EUR", "IDR", "SGD", "JPY"
    };

    public bool Match(
        HttpContext? httpContext,
        IRouter? route,
        string routeKey,
        RouteValueDictionary values,
        RouteDirection routeDirection)
    {
        if (values.TryGetValue(routeKey, out var value) && value is string currencyStr)
        {
            return SupportedCurrencies.Contains(currencyStr);
        }
        return false;
    }
}
```

##### Validation Endpoint Filter
```csharp
// Infrastructure/Filters/ValidationFilter.cs
namespace Enterprise.Routing.Infrastructure.Filters;

using FluentValidation;

public sealed class ValidationFilter<T> : IEndpointFilter where T : class
{
    private readonly IValidator<T> _validator;

    public ValidationFilter(IValidator<T> validator)
    {
        _validator = validator;
    }

    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context, 
        EndpointFilterDelegate next)
    {
        var targetArgument = context.Arguments.OfType<T>().FirstOrDefault();

        if (targetArgument is null)
        {
            return TypedResults.Problem(
                detail: "Payload body parsing failed.",
                statusCode: StatusCodes.Status400BadRequest);
        }

        var validationResult = await _validator.ValidateAsync(targetArgument, context.HttpContext.RequestAborted);

        if (!validationResult.IsValid)
        {
            return TypedResults.ValidationProblem(validationResult.ToDictionary());
        }

        return await next(context);
    }
}
```

##### Modular Endpoint Definition
```csharp
// Endpoints/PaymentEndpoints.cs
namespace Enterprise.Routing.Endpoints;

using Enterprise.Routing.Domain;
using Enterprise.Routing.Infrastructure.Filters;
using Microsoft.AspNetCore.Http.HttpResults;

public static class PaymentEndpoints
{
    public static IEndpointRouteBuilder MapPaymentEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/v{version:apiVersion}/payments/{currency:currency}")
                       .AddEndpointFilter<LoggingTelemetryFilter>()
                       .WithTags("Payments");

        group.MapPost("/", ProcessPayment)
             .AddEndpointFilter<ValidationFilter<CreatePaymentRequest>>()
             .WithName("ProcessPayment")
             .ProducesValidationProblem()
             .WithOpenApi();

        return app;
    }

    public static async Task<Results<Ok<PaymentResponse>, Conflict<string>, ProblemHttpResult>> ProcessPayment(
        string currency,
        CreatePaymentRequest request,
        CancellationToken ct)
    {
        // Simulasi pemeriksaan Idempotency & pemrosesan transaksi
        if (request.Currency != currency)
        {
            return TypedResults.Conflict("URL Currency does not match body currency declaration.");
        }

        var transactionId = Guid.NewGuid();
        var response = new PaymentResponse(transactionId, "COMMITTED", DateTime.UtcNow);

        return TypedResults.Ok(response);
    }
}
```

##### Registrasi Pipeline
```csharp
// Program.cs
using Enterprise.Routing.Endpoints;
using Enterprise.Routing.Infrastructure.Routing;

var builder = WebApplication.CreateBuilder(args);

// Register Custom Constraint
builder.Services.Configure<RouteOptions>(options =>
{
    options.ConstraintMap.Add("currency", typeof(CurrencyRouteConstraint));
    options.LowercaseUrls = true;
});

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

// Mapping Route Group
app.MapPaymentEndpoints();

app.Run();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*Global Settlement Engine* pada platform FinTech multi-nasional menangani lebih dari 120.000 requests per second (RPS) pada puncak transaksi. Sistem awal mengimplementasikan ASP.NET Core MVC Controller dengan 14 filter global (Logging, Auditing, Model State Validation, HMAC Verification, Tenant Resolution).

#### Masalah Produksi
1.  **Latency Spikes akibat Garbage Collection (GC Pause):** Profiling memory via dotTrace dan PerfView mendeteksi alokasi heap sebesar 18.4 MB/detik per worker core yang didominasi oleh `ActionExecutingContext`, `ControllerActionDescriptor`, array alokasi argumen refleksi, dan string allocation dari model binding MVC. P99 latency menyentuh angka 850ms karena Gen-2 GC triggered setiap 4 detik.
2.  **Thread Pool Starvation:** Filter controller warisan mengeksekusi parsing body stream sinkron sebelum mencapai action target.

#### Solusi Rekayasa
1.  **Refactoring dari MVC Controller ke Minimal API:** Seluruh controller di-refactor menjadi modul *Route Group* statis.
2.  **Native AOT Compilation & Request Delegate Generator (RDG):** Memungkinkan eliminasi kompilasi ekspresi runtime reflection dan pemangkasan total metadata assembly yang tidak terpakai.
3.  **Low-Allocation Parameter Binding:** Migrasi parsing body langsung membaca `HttpRequest.BodyReader` via memory pools (`ArrayPool<byte>`) dan `System.Text.Json` source generation context.
4.  **Endpoint Filters Terpadu:** 14 MVC filter dikonsolidasi menjadi 3 pipeline `IEndpointFilter` fungsional berbasis struct context.

#### Hasil Metrik Pasca Implementasi
*   **Throughput:** Melonjak dari 24.000 RPS menjadi 118.000 RPS per container node node 4-core (Peningkatan ~390%).
*   **Alokasi Memori:** Alokasi heap per request terpangkas 91% (dari 6.2 KB menjadi 540 bytes).
*   **P99 Latency:** Turun drastis dari 850ms ke 14ms di bawah beban kerja peak.
*   **GC Collection Frequency:** Frekuensi Gen-2 collection berkurang dari 15 kali/menit menjadi 0 kali di bawah pengujian 1 jam continuous profiling.

---

### 9. Trade-offs (Analisis Komparatif Arsitektur)

| Komponen Arsitektural | Controllers (MVC) | Minimal APIs | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Startup Overhead** | Tinggi ($O(N)$ assembly scanning) | Rendah (Registrasi linier, precompiled via RDG) | Minimal API unggul untuk *serverless scale-to-zero* dan *rapid auto-scaling pod*. |
| **Throughput & Latency** | Overhead alokasi context MVC (~2-8KB/req) | Overhead mendekati nol via direct invocation | Minimal API menghemat cost infrastructure Kubernetes (memerlukan resource CPU & RAM lebih kecil). |
| **Developer Ergonomics** | Konvensi kaku, pemisahan folder standar | Sangat fleksibel, risiko *spaghetti code* jika tidak diatur | Controller melindungi tim junior via struktur baku; Minimal API menuntut disiplin arsitektur tingkat tinggi (butuh Modular Slicing). |
| **AOT & Trimming Compatibility** | Buruk (banyak warning reflection/trimming) | Didesain khusus untuk Native AOT | Jika target deployment adalah AWS Graviton/Docker scratch Native AOT, Minimal API adalah satu-satunya opsi realistis. |
| **Pola Ekstensibilitas** | Action, Exception, Result, Resource Filters | `IEndpointFilter`, Middleware, Route Handler | Controller Filters memiliki siklus hidup lebih kaya (seperti hooking sebelum parsing model binder); Endpoint Filter hanya membungkus method handler. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Scoped Service Capturing dalam Singleton/Root Delegate
*   **Kesalahan:** Meng-inject scoped service (seperti `DbContext`) langsung ke dalam lambda capture expression atau mendaftarkan endpoint route handler sebagai instance singleton.
    ```csharp
    // ANTI-PATTERN: Menangkap DbContext langsung dari builder scope
    var db = builder.Services.BuildServiceProvider().GetRequiredService<MyDbContext>();
    app.MapGet("/bad-leak", () => db.Users.ToList()); // Memory leak dan concurrency crash!
    ```
*   **Mitigasi:** Biarkan Minimal API engine me-resolve dependency via parameter handler secara otomatis per request:
    ```csharp
    // CORRECT: Di-resolve per-request dari HttpContext.RequestServices
    app.MapGet("/good-scope", async (MyDbContext db, CancellationToken ct) => 
        await db.Users.ToListAsync(ct));
    ```

#### 10.2 Route Ambiguity Collision pada Matching Engine
*   **Gejala:** Runtime melempar `AmbiguousMatchException: The request matched multiple endpoints`.
*   **Penyebab:** Dua route template memiliki presedensi DFA yang identik tanpa constraint yang membedakan.
    ```csharp
    app.MapGet("/orders/{id}", (string id) => ...);
    app.MapGet("/orders/{code}", (string code) => ...); // Tabrakan! DFA tidak bisa membedakan precedence dua string parameter.
    ```
*   **Solusi:** Terapkan Route Constraints eksplisit:
    ```csharp
    app.MapGet("/orders/{id:guid}", (Guid id) => ...);
    app.MapGet("/orders/{code:regex(^[A-Z]{{3}}-\\d{{4}}$)}", (string code) => ...);
    ```

#### 10.3 Missing CancellationToken Propagation
*   **Gejala:** Thread pool exhaustion pada service downstream ketika ribuan user melakukan cancel HTTP request (misal: refresh browser berulang kali).
*   **Mitigasi:** Selalu bind `CancellationToken` ke dalam handler dan alirkan ke semua operasi I/O async:
    ```csharp
    app.MapGet("/stream-data", async (IReportService svc, CancellationToken ct) =>
    {
        return TypedResults.Ok(await svc.GenerateReportAsync(ct));
    });
    ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `TypedResults` di atas `Results`:** `TypedResults` menyediakan compile-time type-safety dan secara otomatis mengekspor response types ke OpenAPI tanpa atribut `[ProducesResponseType]` manual.
- [ ] **Terapkan `RouteGroupBuilder`:** Kapsulasi API versioning, prefix, tag, dan authorization policy per-domain menggunakan Route Groups modular.
- [ ] **Aktifkan Request Delegate Generator (RDG):** Pastikan project file mengaktifkan source generator untuk performa maksimal dan kesiapan Native AOT:
  ```xml
  <PropertyGroup>
      <EnableRequestDelegateGenerator>true</EnableRequestDelegateGenerator>
      <PublishAot>true</PublishAot>
  </PropertyGroup>
  ```
- [ ] **Cegah Allocations pada DTO Binding:** Gunakan `readonly record struct` untuk DTO payload berukuran kecil ($\le$ 4 register CPU / 32 bytes) guna menghindari alokasi heap.
- [ ] **Centralized Route Constraints:** Daftarkan kustom constraint ke dalam `RouteOptions` terpusat, jangan menaruh string regex acak yang panjang di dalam string URL template.
- [ ] **Gunakan `AsParameters` Pattern:** Jika parameter endpoint melebihi 4 argumen, kelompokkan ke dalam class/struct menggunakan atribut `[AsParameters]` untuk menjaga kebersihan kode (*clean signatures*).

---

### 12. Hands-on Practice

Buatlah implementasi lengkap modular endpoint architecture yang disimpan pada direktori target: `hands-on/m02/`.

#### Langkah 1: Setup Proyek
```bash
mkdir -p hands-on/m02/HighScaleRouting
cd hands-on/m02/HighScaleRouting
dotnet new web -f net8.0
dotnet add package FluentValidation.DependencyInjectionExtensions
```

#### Langkah 2: Buat Struktur File
Buat struktur direktori seperti berikut:
```text
hands-on/m02/HighScaleRouting/
├── Infrastructure/
│   ├── Constraints/
│   │   └── SlugConstraint.cs
│   └── Filters/
│       └── ExecutionTimingFilter.cs
├── Modules/
│   ├── IModule.cs
│   ├── ModuleExtensions.cs
│   └── CatalogModule.cs
└── Program.cs
```

#### Langkah 3: Implementasi Modul Abstraksi
Tulis abstraksi modular untuk memisahkan endpoint secara bersih:

```csharp
// Modules/IModule.cs
namespace HighScaleRouting.Modules;

public interface IModule
{
    IEndpointRouteBuilder MapEndpoints(IEndpointRouteBuilder endpoints);
}
```

```csharp
// Modules/ModuleExtensions.cs
namespace HighScaleRouting.Modules;

public static class ModuleExtensions
{
    public static IServiceCollection RegisterModules(this IServiceCollection services)
    {
        var moduleType = typeof(IModule);
        var modules = typeof(Program).Assembly
            .GetTypes()
            .Where(p => moduleType.IsAssignableFrom(p) && !p.IsInterface && !p.IsAbstract)
            .Select(Activator.CreateInstance)
            .Cast<IModule>();

        foreach (var module in modules)
        {
            services.AddSingleton(module);
        }

        return services;
    }

    public static WebApplication MapRegisteredEndpoints(this WebApplication app)
    {
        foreach (var module in app.Services.GetServices<IModule>())
        {
            module.MapEndpoints(app);
        }
        return app;
    }
}
```

#### Langkah 4: Implementasi Constraint & Filter
```csharp
// Infrastructure/Constraints/SlugConstraint.cs
namespace HighScaleRouting.Infrastructure.Constraints;

using System.Text.RegularExpressions;

public sealed partial class SlugConstraint : IRouteConstraint
{
    [GeneratedRegex("^[a-z0-9]+(?:-[a-z0-9]+)*$", RegexOptions.Compiled)]
    private static partial Regex SlugRegex();

    public bool Match(HttpContext? httpContext, IRouter? route, string routeKey, RouteValueDictionary values, RouteDirection routeDirection)
    {
        if (values.TryGetValue(routeKey, out var value) && value is string slugStr)
        {
            return SlugRegex().IsMatch(slugStr);
        }
        return false;
    }
}
```

```csharp
// Infrastructure/Filters/ExecutionTimingFilter.cs
namespace HighScaleRouting.Infrastructure.Filters;

using System.Diagnostics;

public sealed class ExecutionTimingFilter : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var result = await next(context);
            return result;
        }
        finally
        {
            stopwatch.Stop();
            context.HttpContext.Response.Headers.Append("X-Response-Time-Ms", stopwatch.ElapsedMilliseconds.ToString());
        }
    }
}
```

#### Langkah 5: Implementasi Catalog Module
```csharp
// Modules/CatalogModule.cs
namespace HighScaleRouting.Modules;

using HighScaleRouting.Infrastructure.Filters;
using Microsoft.AspNetCore.Http.HttpResults;

public sealed class CatalogModule : IModule
{
    public IEndpointRouteBuilder MapEndpoints(IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/v1/catalog")
                             .AddEndpointFilter<ExecutionTimingFilter>()
                             .WithTags("Catalog");

        group.MapGet("/products/{slug:slug}", GetProductBySlug)
             .WithName("GetProductBySlug");

        return endpoints;
    }

    private static Ok<ProductDto> GetProductBySlug(string slug)
    {
        return TypedResults.Ok(new ProductDto(
            Id: Guid.NewGuid(), 
            Slug: slug, 
            Name: $"Product for {slug}", 
            Price: 199.99m));
    }
}

public readonly record struct ProductDto(Guid Id, string Slug, string Name, decimal Price);
```

#### Langkah 6: Program Entry Point
```csharp
// Program.cs
using HighScaleRouting.Infrastructure.Constraints;
using HighScaleRouting.Modules;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<RouteOptions>(options =>
{
    options.ConstraintMap.Add("slug", typeof(SlugConstraint));
    options.LowercaseUrls = true;
});

builder.Services.RegisterModules();

var app = builder.Build();

app.UseHttpsRedirection();

// Registrasi endpoint dari discovery modul
app.MapRegisteredEndpoints();

app.Run();
```

---

### 13. Exercise

#### Level: Easy
Ubah method `GetProductBySlug` pada modul latihan di atas untuk menangani kondisi produk tidak ditemukan, mengembalikan tipe gabungan terdefinisi ketat: `Results<Ok<ProductDto>, NotFound<string>>`. Uji endpoint dengan query slug `"out-of-stock-item"`.

#### Level: Medium
Implementasikan kustom parameter model binding via static method `BindAsync` pada record struct `PaginationParams` yang mengekstrak `page` dan `pageSize` dari QueryString dengan default fallback (`page=1, pageSize=20`), serta melempar HTTP 400 Bad Request jika user mengirimkan `pageSize > 100`.

#### Level: Hard
Bangun sebuah generic dynamic route matcher fallback menggunakan `MatcherPolicy` internal ASP.NET Core yang mengarahkan trafik legacy (`/v0/{resource}/{id}`) ke route baru (`/api/v1/{resource}/{id}`) secara in-memory (URL rewrite internal pada DFA level) tanpa memicu HTTP 301/302 Redirect ke client.

---

### 14. Challenge

**Studi Kasus:** Anda adalah Lead Architect di platform IoT Smart-City. Sistem menerima telemetry streaming dari 2.000.000 sensor kendaraan via endpoint `/telemetry/{deviceId:guid}/stream`.
*   **Permasalahan:** Payload stream ditransmisikan terus menerus dalam bentuk binary chunks berkecepatan tinggi via chunked-transfer-encoding. MVC pipeline kolaps karena thread pool starvation dan *OOM (Out Of Memory)* akibat penampungan byte ke memory sebelum Action Controller dimulai.
*   **Tantangan Arsitektur:**
    1.  Rancang route handler Minimal API murni zero-allocation yang mem-bypass seluruh proses buffering default ASP.NET Core.
    2.  Konsumsi request body secara langsung melalui `PipeReader` (`HttpContext.Request.BodyReader`).
    3.  Lakukan pemrosesan parsing framing protokol biner kustom langsung dari `ReadOnlySequence<byte>`.
    4.  Implementasikan mekanisme *Backpressure* terintegrasi: jika downstream processing engine melambat, Kestrel harus menghentikan pembacaan TCP socket secara asinkron tanpa memakan RAM.
    5.  Buktikan secara arsitektural bahwa tidak ada thread pool yang terblokir (`0` sync-over-async) dan latensi garbage collection berada di level terendah.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1.  **Kapan DFA Matcher ASP.NET Core membangun transition table untuk rute aplikasi?**
    *   A. Setiap kali ada HTTP request masuk ke web server.
    *   B. Saat fase bootstrap/startup aplikasi berlangsung (`WebApplication.Build()` / run).
    *   C. Secara lazy saat rute bersangkutan dipanggil pertama kali.
    *   D. Di-compile langsung oleh Roslyn compiler saat `dotnet build`.
    *   *Kunci:* **B** | *Alasan:* DFA dibangun secara in-memory saat aplikasi melakukan bootstrap dan mengonsolidasikan semua endpoint sources.

2.  **Manakah middleware yang bertanggung jawab menentukan endpoint mana yang sesuai dengan URL dan menempelkannya ke `HttpContext`?**
    *   A. `EndpointMiddleware`
    *   B. `EndpointRoutingMiddleware`
    *   C. `MvcMiddleware`
    *   D. `RoutingExecutionMiddleware`
    *   *Kunci:* **B** | *Alasan:* `EndpointRoutingMiddleware` mengeksekusi routing logic dan menaruh hasilnya pada context, sedangkan `EndpointMiddleware` bertugas mengeksekusi delegate endpoint tersebut di akhir pipeline.

3.  **Metode response Minimal API apa yang menghasilkan *compile-time type safety* tanpa alokasi overhead formatting MVC?**
    *   A. `Results.Json()`
    *   B. `TypedResults.*`
    *   C. `new JsonResult()`
    *   D. `IActionResult`
    *   *Kunci:* **B** | *Alasan:* `TypedResults` mengembalikan strongly typed generic `IResult` types yang mengeliminasi boxing dan mendukung metadata OpenAPI secara otomatis.

4.  **Apa status kompilasi Minimal API ketika flag Native AOT diaktifkan pada .NET 8/9?**
    *   A. Runtime Expression Tree Compilation.
    *   B. Request Delegate Generator (RDG) C# Source Generator.
    *   C. Dynamic IL Emission (System.Reflection.Emit).
    *   D. Interpreted Mode via Roslyn.
    *   *Kunci:* **B** | *Alasan:* Native AOT tidak memperbolehkan dynamic code generation di runtime, sehingga .NET menggunakan Request Delegate Generator (RDG) untuk memproduksi static binding code saat build time.

5.  **Bagaimana cara paling idiomatik mengelompokkan path URL umum, dependency injection filter, dan otentikasi pada Minimal API?**
    *   A. Menggunakan nested controllers.
    *   B. Menggunakan `RouteGroupBuilder` via `app.MapGroup()`.
    *   C. Memisahkan Kestrel instances ke multiple ports.
    *   D. Menulis custom middleware untuk setiap rute.
    *   *Kunci:* **B** | *Alasan:* `app.MapGroup()` dirancang khusus untuk membagikan prefix, filter, metadata otorisasi, dan konfigurasi lintas koleksi endpoint.

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis)
6.  **Apa akar penyebab `AmbiguousMatchException` pada DFA routing?**
    *   A. Kestrel kehabisan socket descriptor.
    *   B. DFA tree mendeteksi dua atau lebih endpoints dengan skor presedensi yang sama persis untuk pola URL request tertentu.
    *   C. Route constraint bernilai false pada salah satu controller.
    *   D. Ada controller dengan nama yang sama di namespace yang berbeda.
    *   *Kunci:* **B** | *Alasan:* DFA tidak dapat menentukan endpoint mana yang harus dieksekusi jika dua cabang memiliki bobot literal/parameter yang identik tanpa pembeda unik.

7.  **Jika parameter sebuah method Minimal API bukan tipe primitif, bukan bagian dari dependency injection container, dan tidak memiliki kustom `BindAsync`/`TryParse`, dari manakah engine akan mencoba membacanya?**
    *   A. Header `User-Agent`.
    *   B. Route values.
    *   C. Deserialisasi JSON dari Request Body.
    *   D. Ditolak saat startup/compile time.
    *   *Kunci:* **C** | *Alasan:* Konvensi inferensi parameter Minimal API menetapkan bahwa tipe kompleks yang tidak terdaftar di DI diasumsikan berasal dari request body (`[FromBody]`).

8.  **Manakah urutan siklus eksekusi yang benar pada pemanggilan request ke endpoint yang dibungkus oleh `IEndpointFilter`?**
    *   A. Endpoint Delegate $\to$ Filter Before $\to$ Filter After.
    *   B. Filter Before $\to$ Endpoint Delegate $\to$ Filter After.
    *   C. Filter After $\to$ Filter Before $\to$ Endpoint Delegate.
    *   D. Tergantung setting middleware Kestrel.
    *   *Kunci:* **B** | *Alasan:* Seperti middleware miniatur, kode sebelum `await next(context)` dieksekusi sebelum delegate target, dan kode setelahnya dieksekusi setelah target selesai.

9.  **Mengapa implementasi static method `BindAsync` lebih diutamakan dibandingkan MVC Model Binder tradisional untuk microservice latensi rendah?**
    *   A. `BindAsync` bekerja langsung tanpa alokasi metadata dictionary, validation tracking, dan refleksi framework MVC.
    *   B. MVC Model Binder tidak mendukung asynchronous parsing.
    *   C. `BindAsync` dijalankan di background thread pool terpisah secara otomatis.
    *   D. MVC Model Binder tidak kompatibel dengan JSON.
    *   *Kunci:* **A** | *Alasan:* `BindAsync` diikat secara statis oleh compiler/RDF, melewati runtime instantiation context model binding MVC yang sangat berat.

10. **Apa dampak performa dari penggunaan atribut `[AsParameters]` pada signature Minimal API?**
    *   A. Menurunkan kecepatan eksekusi sebesar 50% karena serialisasi.
    *   B. Memetakan banyak sumber data (Query, Route, Body, Services) ke dalam satu struct/class tanpa overhead tambahan yang signifikan.
    *   C. Memaksa Kestrel menggunakan HTTP/1.0.
    *   D. Mencegah penggunaan Native AOT.
    *   *Kunci:* **B** | *Alasan:* `[AsParameters]` adalah fitur sintaksis & source-generated yang mengemas parameter rumit ke dalam satu objek terpadu tanpa penalti performa runtime reflection.

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario:** Tim backend Anda melaporkan bahwa sebuah service authentication yang baru dimigrasi dari Controller ke Minimal API mengalami crash dengan error: `Cannot access a disposed object. Object name: 'MyDbContext'`. Hal ini terjadi tepat ketika mereka menambahkan lambda expression:
    ```csharp
    var service = app.Services.GetRequiredService<ITokenService>();
    app.MapPost("/token", () => service.GenerateToken());
    ```
    Di mana `ITokenService` terdaftar sebagai **Transient**, dan di dalamnya menyuntikkan `MyDbContext` (Scoped). Mengapa error ini terjadi pada Minimal API dan bagaimana memperbaikinya secara definitif?
    *   *Solusi & Rationale:* Kode di atas melakukan anti-pattern *Captive Dependency* di luar scope request. `app.Services` adalah Root ServiceProvider. Ketika `ITokenService` di-resolve dari root, dependency scoped miliknya (`MyDbContext`) diaktifkan di level root container atau langsung di-dispose setelah startup selesai. Ketika endpoint `/token` dipanggil berulang kali, delegate mengeksekusi instance yang memegang `MyDbContext` yang sudah disposed. Solusi: Jangan resolve manual dari root! Daftarkan dependency langsung sebagai parameter method handler: `app.MapPost("/token", (ITokenService service) => service.GenerateToken());` sehingga engine Minimal API me-resolve-nya dari `HttpContext.RequestServices` yang memiliki scope request yang valid.

12. **Skenario:** Anda mendapati deployment service pada production Kubernetes cluster mengalami peningkatan konsumsi CPU drastis (100% Core Load) saat routing mengevaluasi regex constraint:
    `{taxCode:regex(^([0-9a-zA-Z]+)*$)}`.
    Serangan apa yang sedang terjadi dan bagaimana perbaikan pada level routing ASP.NET Core?
    *   *Solusi & Rationale:* Terjadi kerentanan **ReDoS (Regular Expression Denial of Service)** akibat *catastrophic backtracking* pada pola regex `^([0-9a-zA-Z]+)*$`. Ketika payload input berupa string panjang yang tidak valid (misal: 100 karakter alphanumeric diakhiri karakter khusus), algoritma regex engine NFA default melakukan iterasi backtracking eksponensial $O(2^n)$. Solusi: 1) Ganti regex route constraint menjadi constraint yang aman non-backtracking. 2) Buat custom `IRouteConstraint` menggunakan Source Generated Regex (`[GeneratedRegex]`) dengan timeout ketat (`TimeSpan.FromMilliseconds(100)`). 3) Jangan gunakan Regex pada route template jika pengecekan bisa diganti dengan format sederhana seperti GUID, Integer, atau custom `IParsable<T>`.

13. **Skenario:** Sebuah endpoint streaming telemetri performa tinggi mengembalikan `IAsyncEnumerable<SensorData>`. Pengujian menunjukkan latensi data sampai ke klien bertambah hingga 5 detik (data diterima sekaligus secara berkala, bukan realtime item-by-item). Tidak ada middleware kompresi yang aktif. Di manakah letak permasalahannya?
    *   *Solusi & Rationale:* Secara default, serializer `System.Text.Json` dalam pipeline web API dapat melakukan buffering chunks untuk efisiensi transfer data jika buffer output response Kestrel belum melampaui ambang batas flush threshold atau framing chunked HTTP belum dipaksa flush. Solusi: Pastikan handler melakukan flush secara eksplisit ke response stream per iterasi, atau konfigurasikan `JsonSerializerOptions` dengan streaming pipeline langsung ke `HttpResponse.BodyWriter.FlushAsync()` setiap item terkirim, atau gunakan format Server-Sent Events (SSE) / newline-delimited JSON (`application/x-ndjson`) yang secara eksplisit memicu `await Response.Body.FlushAsync()`.

---

### 16. Summary
*   **Endpoint Routing** memisahkan evaluasi kecocokan rute via `EndpointRoutingMiddleware` (menggunakan struktur data **Deterministic Finite Automaton / DFA**) dari eksekusinya di `EndpointMiddleware`. Hal ini memberikan kompleksitas waktu pencarian rute konstan $O(1)$ terhadap ukuran total rute.
*   **Minimal API** mengeliminasi overhead besar arsitektur MVC (seperti refleksi `ActionInvoker`, serialisasi bertingkat `IActionResultExecutor`, serta alokasi konteks model binding). Melalui pemanfaatan `RequestDelegateFactory` dan **Request Delegate Generator (RDG)** pada C#, Minimal API secara signifikan mengurangi jejak alokasi memori per request dan kompatibel penuh dengan **Native AOT**.
*   **Controller MVC** tetap memiliki nilai guna pada aplikasi enterprise dengan sistem filter legasi yang saling terikat, namun **Modular Minimal API** yang dikombinasikan dengan `RouteGroupBuilder`, `IEndpointFilter`, dan `TypedResults` menyediakan arsitektur yang jauh lebih scalable, hemat sumber daya komputasi (*cost-effective*), dan memiliki performa deterministik untuk kebutuhan skala industri modern.