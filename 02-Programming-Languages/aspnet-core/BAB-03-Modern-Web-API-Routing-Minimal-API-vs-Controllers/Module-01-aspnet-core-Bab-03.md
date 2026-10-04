# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: NET-MOD-03-01
* **Kategori**: 02-Programming-Languages / ASP.NET Core
* **Judul**: Modern Web API & Routing: Minimal API vs Controllers
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Target Runtime**: .NET 8.0 LTS / C# 12
* **Prasyarat**: Pemahaman mendalam tentang C# OOP & Functional features (delegates, lambda expressions, pattern matching), dasar HTTP/RESTful API, Inversion of Control (IoC) & Dependency Injection (DI) pada .NET, serta pipeline middleware ASP.NET Core.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, arsitek/perekayasa perangkat lunak diharapkan mampu:

1. **Menganalisis (Analyze)** perbedaan mendasar arsitektur internal antara ASP.NET Core Controller-based API (`ControllerActionInvoker`) dan Minimal API (`RequestDelegateFactory`).
2. **Mengevaluasi (Evaluate)** dampak performa, jejak alokasi memori (*heap allocations*), waktu startup (*cold start*), dan kesiapan kompilasi *Ahead-Of-Time* (Native AOT) pada kedua paradigma.
3. **Mengimplementasikan (Create)** endpoint performa tinggi menggunakan Endpoint Routing, Route Groups, Endpoint Filters, serta memanfaatkan `TypedResults` untuk kontrak tipe yang kuat (*type-safe*).
4. **Mendesain (Design)** arsitektur modular skala enterprise menggunakan pola arsitektur REPR (*Request-Endpoint-Response*) dan ekstensi modular tanpa mengotori berkas `Program.cs`.
5. **Memitigasi (Mitigate)** masalah umum (*pitfalls*) seperti jebakan siklus hidup layanan (*scoped-in-singleton capture*), kebocoran alokasi delegasi closure, dan ambiguitas rute.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Heavyweight Framework Model vs Direct Request Delegate

Secara historis, ASP.NET Core MVC/Controllers mengadopsi model *convention-over-configuration* yang diwarisi dari arsitektur MVC klasik. Mental model dari Controllers adalah **"Framework-First"**:
* Setiap request harus menembus lapisan abstraksi yang tebal: *Routing Middleware* $\to$ pencarian metadata action melalui refleksi runtime $\to$ instansiasi controller via *Controller Activator* $\to$ eksekusi serangkaian filter MVC global/action/result $\to$ *Model Binding* berbasis refleksi $\to$ eksekusi metode $\to$ konversi `IActionResult` via *Action Result Executors*.
* Framework bertindak sebagai monolit orkestrasi yang menyembunyikan detail mekanis penanganan HTTP di balik abstraksi kelas berbasis warisan (`ControllerBase`).

Sebaliknya, Minimal API (diperkenalkan pada .NET 6 dan dimatangkan pada .NET 7/8) mengadopsi model **"Endpoint-First / Metal-to-the-Glass"**:
* Mental modelnya adalah memetakan URI secara langsung ke delegasi yang dapat dieksekusi (`RequestDelegate`), yaitu `Func<HttpContext, Task>`.
* Tidak ada kebutuhan instansiasi controller berbasis kelas untuk setiap siklus hidup HTTP request.
* Resolusi model binding, konversi tipe, dan ekstraksi parameter dipecahkan pada saat inisialisasi aplikasi (*startup*) menggunakan *Expression Trees* atau *Source Generators* (Native AOT), bukan inspeksi refleksi berulang pada saat runtime.
* Anda tidak memprogram "di dalam batasan framework", melainkan langsung menempelkan fungsi pada *routing table* kernel ASP.NET Core.

```
MENTAL MODEL:
Controller Pipeline:   Request -> [ Routing -> MVC Pipeline -> Reflection Activator -> Action Filter Stack -> Action Method -> Result Executor ] -> Response
Minimal API Pipeline:  Request -> [ Routing Engine (DFA) -> RequestDelegate (Direct Compiled Invoker / AOT Thunk) ] -> Response
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Kedua pendekatan ini memanfaatkan subsistem yang sama untuk pencocokan rute (*Endpoint Routing*), namun jalur eksekusi setelah rute ditemukan divergen secara signifikan.

```
+--------------------------------------------------------------------------------------------------+
|                                    HTTP REQUEST (Kestrel)                                        |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                      EndpointRoutingMiddleware                                    |
|  - Mencocokkan Request URI & HTTP Method ke Endpoint metadata menggunakan DFA (Direct Acyclic Graph)|
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                     EndpointExecutingMiddleware                                  |
|  - Mengambil IEndpointFeature dari HttpContext                                                   |
+--------------------------------------------------------------------------------------------------+
                                                 |
                   +-----------------------------+-----------------------------+
                   | (Branch A: Controllers)                                   | (Branch B: Minimal API)
                   v                                                           v
+------------------------------------+                      +------------------------------------+
|  ControllerActionInvoker           |                      |  EndpointFilter Pipeline           |
|  - Eksekusi IAuthorizationFilter   |                      |  - Eksekusi Route Handler Filters  |
|  - Eksekusi IResourceFilter        |                      |    (In-line / IEndpointFilter)     |
+------------------------------------+                      +------------------------------------+
                   |                                                           |
                   v                                                           v
+------------------------------------+                      +------------------------------------+
|  Controller Activation             |                      |  Direct Invoker Execution          |
|  - IControllerActivator            |                      |  - Dihasilkan via RequestDelegate- |
|  - Instansiasi Controller class    |                      |    Factory (Expression Tree /      |
|  - Resolusi constructor DI         |                      |    Source Generated Thunk)         |
+------------------------------------+                      |  - Resolusi Service/Model Binding  |
                   |                                        +------------------------------------+
                   v                                                           |
+------------------------------------+                                         |
|  Model Binding & Action Execution  |                                         |
|  - IModelBinderProvider            |                                         |
|  - Eksekusi IActionFilter          |                                         |
|  - Invokasi Action Method          |                                         |
|  - Eksekusi IResultFilter          |                                         |
+------------------------------------+                                         |
                   |                                                           |
                   v                                                           v
+------------------------------------+                      +------------------------------------+
|  IActionResultExecutor             |                      |  IResult.ExecuteAsync              |
|  - Serialisasi format respon       |                      |  - Tulis langsung ke HttpResponse  |
+------------------------------------+                      +------------------------------------+
                   |                                                           |
                   +-----------------------------+-----------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                     HTTP RESPONSE TO CLIENT                                      |
+--------------------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Endpoint Routing Core & Dynamic Route Matching
Diperkenalkan pada ASP.NET Core 3.0 dan menjadi fondasi utama hingga .NET 8, mesin rute internal menggunakan *Deterministic Finite Automaton* (DFA) berbasis Trie (`DfaMatcher`).
* Jalur URL diproses bukan menggunakan Regex linier $O(N)$, melainkan grafik pohon pencarian terarah (*Directed Acyclic Graph*) $O(K)$, di mana $K$ adalah panjang segmen URI.
* Setiap endpoint (baik controller action maupun lambda Minimal API) direpresentasikan secara internal sebagai instansi kelas `Endpoint`:
  ```csharp
  public class Endpoint
  {
      public RequestDelegate? RequestDelegate { get; }
      public EndpointMetadataCollection Metadata { get; }
      public string? DisplayName { get; }
  }
  ```

### 2. RequestDelegateFactory (RDF) vs ControllerActionInvoker
* **Controller**: Menggunakan `IActionDescriptorCollectionProvider` yang secara global memindai *Assembly* untuk menemukan tipe yang mewarisi `ControllerBase` atau beranotasi `[ApiController]`. Untuk memanggil sebuah method, ASP.NET Core mengalokasikan konteks eksekusi yang kompleks melalui `ControllerActionInvokerCache`, mengalokasikan array parameter objek untuk refleksi runtime (`MethodInfo.Invoke`), dan mengeksekusi siklus hidup filter 7-tahap.
* **Minimal API**: Ditangani oleh `RequestDelegateFactory`. Pada saat startup aplikasi (`app.MapGet(...)`), RDF memeriksa signature delegasi melalui refleksi **hanya satu kali**. Dari signature tersebut, RDF mengompilasi sebuah `Expression<RequestDelegate>` dinamis langsung ke `RequestDelegate` IL via IL Emit / Expression Compilation:
  * Pemanggilan `serviceProvider.GetRequiredService(Type)` di-*hardcode* ke dalam delegasi.
  * Pembacaan `HttpContext.Request.RouteValues` langsung diekstraksi ke tipe primitif menggunakan parser cepat (`int.TryParse`, dsb).
  * Pembacaan `Body` langsung mengarahkan stream ke `System.Text.Json` *reader*.
  * Hasil akhirnya adalah sebuah fungsi pemanggil linear murni yang memiliki efisiensi nyaris setara dengan kode middleware kustom yang ditulis tangan tanpa overhead lapisan MVC.

### 3. Native AOT Mechanics (.NET 8)
Pada .NET 8, RDF dilengkapi dengan *C# Source Generator* (`RequestDelegateGenerator` atau RDG). Jika diaktifkan, pembuatan dynamic delegate berbasis *Expression Tree* ditiadakan. Sebagai gantinya, Roslyn compiler menghasilkan kode C# secara otomatis pada saat kompilasi (*compile-time*) yang memetakan binding HTTP langsung tanpa refleksi sedikit pun, memungkinkan aplikasi dikompilasi menjadi biner mesin murni (*Native AOT*) dengan cold-start di bawah 10ms dan jejak memori awal di bawah 15MB.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Aturan Model Binding pada Minimal API
Minimal API tidak menggunakan `IModelBinder` konvensional. Sebagai gantinya, ia menerapkan aturan inferensi parameter eksplisit dan kaku berdasarkan urutan deterministik:

1. **Parameter Khusus Framework**:
   * `HttpContext`, `HttpRequest`, `HttpResponse`, `ClaimsPrincipal`, `CancellationToken`.
   * Diinjeksi langsung dari konteks koneksi aktif tanpa inferensi parser.
2. **Kandidat `TryParse` (Route / Query / Header)**:
   * Setiap tipe yang mengimplementasikan metode statis:
     * `public static bool TryParse(string? s, out T result)`
     * `public static bool TryParse(string? s, IFormatProvider? provider, out T result)`
     * `public static ValueTask<T?> BindAsync(HttpContext context, ParameterInfo parameter)`
   * Jika nama parameter cocok dengan token rute (misal: `/orders/{id}`), nilai diambil dari *RouteValues*. Jika tidak cocok dengan token rute, diambil dari *Query String*.
3. **Parameter Layanan Dependency Injection (DI)**:
   * Tipe yang terdaftar pada `IServiceProvider` (atau secara eksplisit dianotasi atribut `[FromServices]`).
   * Menggunakan inferensi `IServiceProviderIsService` untuk memverifikasi apakah tipe terdaftar di IoC Container pada saat startup aplikasi.
4. **Parameter Request Body**:
   * Tipe kompleks apa pun yang tidak memenuhi aturan 1–3 diasumsikan secara otomatis sebagai JSON Request Body (`[FromBody]`).
   * Hanya diperbolehkan satu parameter request body per endpoint handler.
5. **Parameter Keyed Services (.NET 8)**:
   * Menggunakan atribut `[FromKeyedServices("serviceKey")]` untuk resolusi instansi layanan spesifik dari container.

### Endpoint Filters Pipeline
Minimal API tidak mendukung MVC `IActionFilter` atau `IResourceFilter`. Mekanisme modifikasi alurnya menggunakan rantai `IEndpointFilter`:

$$\text{Request} \to \text{Filter}_1 \to \text{Filter}_2 \to \dots \to \text{Handler} \to \dots \to \text{Filter}_2 \to \text{Filter}_1 \to \text{Response}$$

```csharp
app.MapPost("/data", (Payload data) => Results.Ok(data))
   .AddEndpointFilter(async (invocationContext, next) =>
   {
       // Pre-execution logic
       var result = await next(invocationContext);
       // Post-execution logic
       return result;
   });
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut perbandingan langsung (*side-by-side*) implementasi endpoint CRUD sederhana untuk agregat `Product`:

### Pendekatan 1: Controller-Based API

```csharp
// ProductsController.cs
using Microsoft.AspNetCore.Mvc;

namespace ArchitecturalComparison.Controllers;

[ApiController]
[Route("api/v1/[controller]")]
[Produces("application/json")]
public sealed class ProductsController : ControllerBase
{
    private readonly IProductRepository _repository;

    public ProductsController(IProductRepository repository)
    {
        _repository = repository;
    }

    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetById([FromRoute] Guid id, CancellationToken ct)
    {
        var product = await _repository.FindByIdAsync(id, ct);
        if (product is null)
        {
            return NotFound();
        }

        return Ok(new ProductDto(product.Id, product.Name, product.Price));
    }

    [HttpPost]
    [ProducesResponseType(typeof(ProductDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> Create([FromBody] CreateProductRequest request, CancellationToken ct)
    {
        if (request.Price <= 0)
        {
            return BadRequest("Price must be greater than zero.");
        }

        var product = new Product(Guid.NewGuid(), request.Name, request.Price);
        await _repository.SaveAsync(product, ct);

        return CreatedAtAction(nameof(GetById), new { id = product.Id }, new ProductDto(product.Id, product.Name, product.Price));
    }
}
```

### Pendekatan 2: Minimal API (Modern .NET 8 Idiom)

```csharp
// ProductEndpoints.cs
using Microsoft.AspNetCore.Http.HttpResults;

namespace ArchitecturalComparison.Endpoints;

public static class ProductEndpoints
{
    public static RouteGroupBuilder MapProductEndpoints(this RouteGroupBuilder group)
    {
        group.MapGet("/{id:guid}", GetById)
             .WithName(nameof(GetById))
             .WithSummary("Mengambil produk berdasarkan ID");

        group.MapPost("/", Create)
             .WithName(nameof(Create))
             .WithSummary("Membuat produk baru");

        return group;
    }

    private static async Task<Results<Ok<ProductDto>, NotFound>> GetById(
        Guid id, 
        IProductRepository repository, 
        CancellationToken ct)
    {
        var product = await repository.FindByIdAsync(id, ct);
        if (product is null)
        {
            return TypedResults.NotFound();
        }

        return TypedResults.Ok(new ProductDto(product.Id, product.Name, product.Price));
    }

    private static async Task<Results<CreatedAtRoute<ProductDto>, BadRequest<string>>> Create(
        CreateProductRequest request, 
        IProductRepository repository, 
        CancellationToken ct)
    {
        if (request.Price <= 0)
        {
            return TypedResults.BadRequest("Price must be greater than zero.");
        }

        var product = new Product(Guid.NewGuid(), request.Name, request.Price);
        await repository.SaveAsync(product, ct);

        return TypedResults.CreatedAtRoute(
            new ProductDto(product.Id, product.Name, product.Price),
            nameof(GetById), 
            new { id = product.Id });
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Minimal API Implementation:
1. `public static RouteGroupBuilder MapProductEndpoints(this RouteGroupBuilder group)`:
   * Memanfaatkan `RouteGroupBuilder` untuk menetapkan rute dasar bersama, autentikasi, serta filter tanpa menduplikasi kode URL.
2. `group.MapGet("/{id:guid}", GetById)`:
   * Mengikat HTTP GET dengan *route constraint* regex bawaan `:guid`. Jika format UUID tidak valid, DFA routing menolaknya dengan HTTP 404 tanpa mengalokasikan delegate eksekusi.
3. `Results<Ok<ProductDto>, NotFound>`:
   * *Discriminated Union pattern* murni di C#. Menghilangkan `IActionResult` yang tidak memiliki tipe jelas (*untyped object*).
   * Menjamin *compile-time type safety* untuk respon. Kompilator memaksa kita hanya mengembalikan objek yang berada dalam definisi tipe generik ini.
   * Mengeliminasi kebutuhan atribut metadata swagger `[ProducesResponseType]` secara manual karena OpenAPI mengekstrak tipe langsung dari signature generik ini.
4. `Guid id, IProductRepository repository, CancellationToken ct`:
   * Binding sepenuhnya otomatis: `Guid id` cocok dengan token `{id:guid}` $\to$ diekstrak dari route.
   * `IProductRepository` terdeteksi di DI container $\to$ diinjeksi via `HttpContext.RequestServices`.
   * `ct` diinjeksi langsung dari sinyal `HttpContext.RequestAborted`.
5. `TypedResults.CreatedAtRoute(...)`:
   * Mengembalikan implementasi konkret dari `IResult` yang menghindari *boxing* dan langsung mengeksekusi serialisasi payload dengan nol alokasi refleksi runtime.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Gateway Ingesti Ledger Finansial Skala Tinggi
* **Kebutuhan**: Layanan *financial event ledger* harus menerima hingga 25.000 HTTP POST/detik per node selama jam beban transaksi puncak.
* **Kendala**:
  * P99 Latency harus $< 10\text{ ms}$.
  * Jejak memori (*Garbage Collection Generation 0/1 allocations*) harus dijaga serendah mungkin untuk menghindari *Stop-The-World GC Pauses*.
  * Setiap transaksi harus divalidasi skema payload-nya secara ketat sebelum diteruskan ke bus pesan (Kafka/Pulsar).
* **Solusi Arsitektur**:
  * Membuang Controller MVC seluruhnya demi menghindari alokasi layer filter dan instansiasi controller.
  * Mengadopsi **Minimal API** dengan `RouteGroupBuilder`, dipadukan dengan **Endpoint Filters** untuk validasi skema berbasis *FluentValidation*.
  * Menggunakan `TypedResults` dan **C# Source Generators** untuk serialisasi JSON Native AOT-ready.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur produksi lengkap dan mandiri tanpa menggunakan Controller:

```csharp
// Program.cs
using System.Text.Json.Serialization;
using FluentValidation;
using Microsoft.AspNetCore.Http.HttpResults;

var builder = WebApplication.CreateSlimBuilder(args);

// Konfigurasi JSON Serializer untuk Native AOT & High Efficiency
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonSerializerContext.Default);
});

// Registrasi Core Services
builder.Services.AddSingleton<ITransactionLedgerQueue, InMemoryHighThroughputQueue>();
builder.Services.AddValidatorsFromAssemblyContaining<CreateLedgerTransactionValidator>();

var app = builder.Build();

// Pemetaan Route Group
var v1Ledger = app.MapGroup("/api/v1/ledger-transactions")
                  .AddEndpointFilter<ValidationEndpointFilter<CreateLedgerTransactionRequest>>();

// Definisi Endpoint
v1Ledger.MapPost("/", async Task<Results<Accepted<TransactionReceipt>, BadRequest<string>>> (
    CreateLedgerTransactionRequest request,
    ITransactionLedgerQueue queue,
    CancellationToken ct) =>
{
    var transactionId = Guid.NewGuid();
    var entity = new LedgerEntry(
        transactionId, 
        request.SourceAccountId, 
        request.DestinationAccountId, 
        request.Amount, 
        request.Currency, 
        DateTimeOffset.UtcNow
    );

    await queue.EnqueueAsync(entity, ct);

    var receipt = new TransactionReceipt(transactionId, "QUEUED", DateTimeOffset.UtcNow);
    return TypedResults.Accepted($"/api/v1/ledger-transactions/{transactionId}", receipt);
});

app.Run();

// ==========================================
// KONTRAK DATA & VALIDASI
// ==========================================

public readonly record struct CreateLedgerTransactionRequest(
    Guid SourceAccountId,
    Guid DestinationAccountId,
    decimal Amount,
    string Currency
);

public readonly record struct TransactionReceipt(
    Guid TransactionId,
    string Status,
    DateTimeOffset Timestamp
);

public sealed class CreateLedgerTransactionValidator : AbstractValidator<CreateLedgerTransactionRequest>
{
    public CreateLedgerTransactionValidator()
    {
        RuleFor(x => x.SourceAccountId).NotEmpty();
        RuleFor(x => x.DestinationAccountId).NotEmpty();
        RuleFor(x => x.SourceAccountId).NotEqual(x => x.DestinationAccountId)
            .WithMessage("Source and Destination accounts must be distinct.");
        RuleFor(x => x.Amount).GreaterThan(0.0001m);
        RuleFor(x => x.Currency).NotEmpty().Length(3);
    }
}

// ==========================================
// ENTERPRISE ENDPOINT FILTER PIPELINE
// ==========================================

public sealed class ValidationEndpointFilter<T> : IEndpointFilter where T : class
{
    private readonly IValidator<T>? _validator;

    public ValidationEndpointFilter(IValidator<T>? validator = null)
    {
        _validator = validator;
    }

    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        if (_validator is null)
        {
            return await next(context);
        }

        // Cari argumen dalam konteks handler yang sesuai dengan generic T
        for (int i = 0; i < context.Arguments.Count; i++)
        {
            if (context.Arguments[i] is T validatableObject)
            {
                var validationResult = await _validator.ValidateAsync(validatableObject, context.HttpContext.RequestAborted);
                if (!validationResult.IsValid)
                {
                    return TypedResults.ValidationProblem(validationResult.ToDictionary());
                }
                break;
            }
        }

        return await next(context);
    }
}

// ==========================================
// INFRASTRUKTUR / MODEL DOMAIN
// ==========================================

public record LedgerEntry(
    Guid Id, 
    Guid SourceAccountId, 
    Guid DestinationAccountId, 
    decimal Amount, 
    string Currency, 
    DateTimeOffset CreatedAt
);

public interface ITransactionLedgerQueue
{
    ValueTask EnqueueAsync(LedgerEntry entry, CancellationToken ct);
}

public sealed class InMemoryHighThroughputQueue : ITransactionLedgerQueue
{
    public ValueTask EnqueueAsync(LedgerEntry entry, CancellationToken ct)
    {
        // Simulasi penulisan internal non-allocating ring buffer / Channel<T>
        return ValueTask.CompletedTask;
    }
}

// ==========================================
// NATIVE AOT JSON SERIALIZER CONTEXT
// ==========================================

[JsonSerializable(typeof(CreateLedgerTransactionRequest))]
[JsonSerializable(typeof(TransactionReceipt))]
[JsonSerializable(typeof(Microsoft.AspNetCore.Mvc.ValidationProblemDetails))]
public partial class AppJsonSerializerContext : JsonSerializerContext
{
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektur | Minimal API (.NET 8) | Controller-Based API (`ControllerBase`) |
| :--- | :--- | :--- |
| **Throughput (RPS)** | Maksimal. Lebih sedikit overhead pemanggilan instruksi CPU per request. | Moderat hingga Tinggi. Overhead alokasi siklus hidup MVC. |
| **Alokasi Memori Heap** | Sangat Rendah. Menggunakan `ValueTask` & `TypedResults` tanpa abstraksi berat. | Tinggi. Alokasi array parameter refleksi dan context objek per invocation. |
| **Startup / Cold-Start** | Sangat Cepat. Eksekusi mapping linear, mendukung Native AOT secara penuh. | Lambat. Membutuhkan *Assembly Scanning* dan inisialisasi metadata model binding. |
| **Native AOT Ready** | Ya, didukung native via C# Source Generators (`RequestDelegateGenerator`). | Tidak sepenuhnya didukung. Penggunaan refleksi runtime MVC memicu *trimming warnings*. |
| **Separation of Concerns** | Membutuhkan disiplin arsitektur (ekstensi kustom/pola REPR). Rawan menjadi file tunggal spaghetti jika tidak diawasi. | Struktur direktori terisolasi secara alami melalui konvensi folder (`Controllers/`). |
| **Ekosistem Filter** | `IEndpointFilter` (sederhana, langsung, terikat per endpoint/group). | 7 tingkatan MVC Filters (`Authorization`, `Resource`, `Action`, `Result`, `Exception`, dll). |
| **Model Validation** | Eksplisit menggunakan `IEndpointFilter` + FluentValidation atau data annotations manual. | Implisit via `[ApiController]` yang otomatis menjalankan `ModelStateInvalidFilter`. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Ambiguitas Routing pada Endpoint Overlapping
Pada Minimal API, pendefinisian rute berikut akan menyebabkan *startup exception* atau *runtime ambiguous match exception*:

```csharp
app.MapGet("/users/{id}", (string id) => $"String Id: {id}");
app.MapGet("/users/{id:int}", (int id) => $"Int Id: {id}");
```
* **Masalah**: Meskipun routing engine DFA dapat membedakan rute dengan batasan tipe (*type constraint*), dependensi yang terlalu mirip dapat menimbulkan kebingungan prioritas pada fallback.
* **Mitigasi**: Gunakan format URL yang lebih terstruktur atau terapkan batasan regex/constraint secara eksplisit pada rute yang berpotensi tumpang tindih.

### 2. Capturing Scoped Service di Lambda Delegasi
```csharp
// BAHAYA BESAR: CAPTIVE DEPENDENCY / THREAD SAFETY BUGS
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddScoped<IOrderService, OrderService>();
var app = builder.Build();

// OrderService di-resolve di root scope (singleton lifecycle leak!)
var orderService = app.Services.GetRequiredService<IOrderService>();

app.MapGet("/orders", () => orderService.GetOrders()); // BUG!
```
* **Masalah**: Service berstatus `Scoped` diekstraksi di luar lingkup request HTTP dan diubah menjadi *de facto Singleton* melalui closure lambda, memicu *race condition* dan kebocoran memori (misalnya pada `DbContext`).
* **Mitigasi**: Jangan pernah mengambil dependency dari `app.Services` untuk dimasukkan ke handler. Definisikan dependensi langsung sebagai argumen delegasi handler:
  ```csharp
  app.MapGet("/orders", (IOrderService orderService) => orderService.GetOrders());
  ```

### 3. File Upload (Multipart Form Data)
Berbeda dengan Controller yang menyediakan abstraksi sederhana `[FromForm] IFormFile`, penanganan multipart form data pada Minimal API sebelum .NET 7 memerlukan parsing manual stream. Di .NET 8, pastikan parameter didefinisikan secara eksplisit menggunakan `IFormFile` atau `IFormFileCollection`:
```csharp
app.MapPost("/upload", async (IFormFile file) => 
{
    using var stream = file.OpenReadStream();
    // Proses stream file
    return TypedResults.Ok();
}).DisableAntiforgery(); // Perhatikan CSRF token jika menggunakan form binding!
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menumpuk Seluruh Endpoint di Berkas `Program.cs` (*God Program File*)
* **Anti-Pattern**: Menulis ratusan rute dengan logika bisnis berlapis-lapis langsung di dalam berkas konfigurasi `Program.cs`.
* **Solusi Arsitektural**: Pisahkan routing menjadi modul-modul independen menggunakan metode ekstensi `IEndpointRouteBuilder`:

```csharp
// Registrations/EndpointRegistrationExtensions.cs
public static class EndpointRegistrationExtensions
{
    public static IEndpointRouteBuilder MapApplicationEndpoints(this IEndpointRouteBuilder app)
    {
        var apiGroup = app.MapGroup("/api/v1");
        
        apiGroup.MapGroup("/users").MapUserEndpoints();
        apiGroup.MapGroup("/invoices").MapInvoiceEndpoints();
        
        return app;
    }
}
```

### Kesalahan 2: Menggunakan `Results.Json()` Tanpa *Serializer Options* Konsisten
* **Anti-Pattern**: Mengembalikan `Results.Json(new { Data = 123 })` secara manual yang mengabaikan konfigurasi konverter camelCase/PascalCase global pada DI.
* **Solusi**: Gunakan `TypedResults.Ok(new ResponseData(123))` untuk menjamin serialisasi otomatis mengikuti saluran sistem global dan menjaga integrasi OpenAPI.

### Kesalahan 3: Tidak Menyertakan `CancellationToken`
* **Anti-Pattern**: Mengabaikan pembatalan request. Jika client memutuskan koneksi, thread internal tetap mengeksekusi operasi database yang membuang sumber daya.
* **Solusi**: Selalu operasikan `CancellationToken` ke operasi async:
  ```csharp
  app.MapGet("/long-running", async (IDataService service, CancellationToken ct) => 
  {
      return TypedResults.Ok(await service.ExecuteProcessAsync(ct));
  });
  ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Adopsi Pola REPR (Request-Endpoint-Response)**:
   Hindari arsitektur berbasis kumpulan controller raksasa yang menangani belasan action sekaligus. Dengan Minimal API, perlakukan setiap endpoint sebagai satu berkas unit terisolasi (misal: `CreateOrderEndpoint.cs` yang memuat class request, validasi, dan logikanya sendiri).
2. **Gunakan `TypedResults` Bukan `Results`**:
   `TypedResults` mengembalikan tipe konkret (seperti `Ok<T>`, `NotFound`, dll.) yang mengimplementasikan `IResult`. Ini memungkinkan penulisan *unit test* langsung pada nilai balikan metode handler tanpa perlu meng-*host* instansi test server HTTP in-memory.
3. **Standarisasi Pengembalian Format Error dengan RFC 7807 (`ProblemDetails`)**:
   Gunakan middleware standar:
   ```csharp
   builder.Services.AddProblemDetails();
   ```
   Dan kembalikan respon error via `TypedResults.ValidationProblem()` atau `TypedResults.Problem()`.
4. **Isolasi Logika Routing Melalui Route Grouping**:
   Terapkan *security policy* (Autentikasi, Rate Limiting, CORS) pada level group, bukan menduplikasi atribut pada setiap endpoint individu:
   ```csharp
   var secureGroup = app.MapGroup("/api/secure")
                        .RequireAuthorization("AdminOnly")
                        .RequireRateLimiting("FixedWindowPolicy");
   ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan `TypedResults` untuk Unit Testing Tanpa Overhead HTTP Client
Karena Minimal API handler dapat didefinisikan sebagai metode C# statis murni yang mengembalikan tipe generik konkret `Results<T1, T2>`, Anda dapat memverifikasi logika endpoint dengan nol overhead alokasi HTTP server.

```csharp
// Unit Test Handler secara Direct Call (Ultra-Fast)
[Fact]
public async Task GetById_ReturnsNotFound_WhenItemDoesNotExist()
{
    // Arrange
    var mockRepo = new Mock<IProductRepository>();
    mockRepo.Setup(r => r.FindByIdAsync(It.IsAny<Guid>(), default))
             .ReturnsAsync((Product?)null);

    // Act
    var result = await ProductEndpoints.GetById(Guid.NewGuid(), mockRepo.Object, CancellationToken.None);

    // Assert: Langsung verifikasi underlying Result type
    Assert.IsType<NotFound>(result.Result);
}
```

### Meminimalkan Delegasi Allocation via Static Methods
Menggunakan *anonymous inline lambdas* sering kali secara tidak sengaja mengalokasikan memori (*closure capture*) jika mengakses variabel lokal dari *outer scope*. Gunakan metode statis privat murni untuk menjamin delegasi berstatus bebas closure:

```csharp
// Mencegah heap allocation dari lambda capture:
app.MapPost("/process", HandleProcess);

private static async Task<Ok<string>> HandleProcess(RequestData data)
{
    return TypedResults.Ok(data.Value);
}
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Enforce Authorization Boundaries**:
   Selalu amankan grup rute secara ketat menggunakan *chaining authorization policy*:
   ```csharp
   var adminEndpoints = app.MapGroup("/api/v1/admin")
                           .RequireAuthorization(policy => policy.RequireRole("SystemAdmin"))
                           .RequireRateLimiting("StrictApiLimiter");
   ```

2. **Antisipasi *Mass Assignment Vulnerabilities***:
   *Jangan pernah* menerima entitas database/EF Core langsung sebagai parameter input di Minimal API:
   ```csharp
   // SANGAT BERBAHAYA
   app.MapPost("/users", async (User user, AppDbContext db) => { ... });
   ```
   *Wajib* gunakan Data Transfer Object (DTO) khusus bertipe data `record struct` yang membatasi hanya field yang diizinkan untuk di-bind:
   ```csharp
   // AMAN
   app.MapPost("/users", async (CreateUserDto dto, AppDbContext db) => { ... });
   ```

3. **CORS Sanitization**:
   Terapkan kebijakan Cross-Origin Resource Sharing (CORS) eksplisit sebelum mengekspos endpoint ke domain publik:
   ```csharp
   app.UseCors(policy => 
       policy.WithOrigins("https://dashboard.production.internal")
             .AllowAnyMethod()
             .AllowAnyHeader());
   ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Di lingkungan *high-throughput*, teknik logging berbasis string interpolation memicu alokasi string dan boxing bernilai fatal pada throughput CPU. Gunakan **High-Performance Logging Source Generators** (`LoggerMessageAttribute`) di dalam Minimal API Filters:

```csharp
public static partial class LogExtensions
{
    [LoggerMessage(
        EventId = 1001, 
        Level = LogLevel.Information, 
        Message = "Memproses transaksi {TransactionId} untuk Akun {AccountId} sebesar {Amount}")]
    public static partial void LogTransactionProcessing(
        this ILogger logger, 
        Guid transactionId, 
        Guid accountId, 
        decimal amount);
}

// Penggunaan pada Endpoint:
v1Ledger.MapPost("/trace", (
    CreateLedgerTransactionRequest req, 
    ILoggerFactory loggerFactory) =>
{
    var logger = loggerFactory.CreateLogger("LedgerTracking");
    logger.LogTransactionProcessing(Guid.NewGuid(), req.SourceAccountId, req.Amount);
    return TypedResults.Accepted();
});
```

### Integrasi OpenTelemetry Tracing
Minimal API terintegrasi secara otomatis dengan `Activity` dan `DiagnosticSource` ASP.NET Core. Setiap rute grup dan nama rute yang dipetakan menggunakan ekstensi `.WithName("EndpointName")` akan mengisi tag telemetry `http.route` secara otomatis untuk diekspor ke platform seperti Grafana Tempo atau Datadog.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Kapan Menggunakan Apa?

```
                     Apakah project Anda memerlukan:
                     - Native AOT Compilation?
                     - Ultra-low latency / Ultra-high RPS?
                     - Microservices / Serverless Functions?
                                      |
                      +---------------+---------------+
                      |                               |
                     YES                             NO
                      |                               |
                      v                               v
             PILIH: MINIMAL API            Apakah tim Anda memiliki basis
                                           kode Controller raksasa yang
                                           mengandalkan MVC Filters ekstensif?
                                                      |
                                      +---------------+---------------+
                                      |                               |
                                     YES                             NO
                                      |                               |
                                      v                               v
                             PILIH: CONTROLLERS              PILIH: MINIMAL API
```

### Core API Mapping Matrix
* `app.MapGet(pattern, handler)` $\to$ Mengikat HTTP GET
* `app.MapPost(pattern, handler)` $\to$ Mengikat HTTP POST
* `app.MapGroup(prefix)` $\to$ Membuat grup rute hierarkis
* `group.RequireAuthorization(...)` $\to$ Melindungi seluruh endpoint dalam grup
* `group.AddEndpointFilter<T>()` $\to$ Menempelkan cross-cutting interceptor pipeline
* `TypedResults.*` $\to$ Menghasilkan output HTTP biner dengan strong typing (AOT Friendly)

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Tingkat Dasar (Basic)

**Soal 1**: Di balik layar, teknologi struktur data apa yang digunakan oleh ASP.NET Core Endpoint Routing untuk mencocokkan URL rute secara efisien?
* A) Linear Array Search
* B) Directed Acyclic Graph / Deterministic Finite Automaton (DFA) berbasis Trie
* C) Regular Expression Dynamic Matching
* D) Binary Search Tree berbasis Thread

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
ASP.NET Core menggunakan DfaMatcher yang memetakan rute ke dalam struktur pohon deterministik (DFA Trie). Hal ini membuat kompleksitas pencarian rute bersifat independen dari jumlah total endpoint ($O(K)$ berdasarkan panjang URI, bukan $O(N)$ berdasarkan total rute).
</details>

---

**Soal 2**: Apa keuntungan utama penggunaan `TypedResults.Ok<T>()` dibandingkan `Results.Ok()` pada Minimal API?
* A) `TypedResults` otomatis mengenkripsi data payload sebelum dikirimkan melalui HTTP.
* B) `TypedResults` menyediakan *compile-time type safety*, integrasi OpenAPI/Swagger otomatis tanpa atribut tambahan, dan memudahkan pengujian unit (unit testing) tanpa membedah payload HTTP.
* C) `TypedResults` mengonversi eksekusi synchronous menjadi asynchronous secara otomatis.
* D) `TypedResults` hanya dapat digunakan jika aplikasi dikonfigurasi menggunakan Entity Framework Core.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
<code>TypedResults</code> mengembalikan tipe konkret pengimplementasi <code>IResult</code> yang mempertahankan tipe data asli parameter generik, memungkinkan OpenAPI mengekstrak skema secara otomatis dan mempermudah unit testing langsung terhadap properti tipe data tersebut.
</details>

---

**Soal 3**: Bagaimana Minimal API menentukan secara default bahwa sebuah objek parameter harus diambil dari HTTP Request Body?
* A) Parameter tersebut harus secara wajib dianotasi dengan atribut `[FromBody]`.
* B) Parameter tersebut memiliki nama `body`.
* C) Tipe data parameter merupakan tipe kompleks yang tidak terdaftar di DI Container dan tidak memiliki implementasi metode statis `TryParse` atau `BindAsync`.
* D) Minimal API tidak mendukung deserialisasi Request Body secara otomatis.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: C</b><br/>
Mekanisme model binding inferensial Minimal API memperlakukan semua tipe kompleks yang bukan bagian dari primitive/TryParseable types dan tidak terdaftar di Dependency Injection container secara otomatis sebagai request body JSON.
</details>

---

**Soal 4**: Apa yang terjadi jika dua endpoint di Minimal API didefinisikan dengan route template yang sama persis dan HTTP method yang sama?
* A) Aplikasi akan menimpa endpoint pertama dengan endpoint kedua secara diam-diam.
* B) Kestrel akan melempar `AmbiguousMatchException` pada saat request pertama yang cocok tiba di runtime.
* C) Aplikasi secara acak memilih salah satu endpoint menggunakan algoritma round-robin.
* D) Endpoint kedua diabaikan dan aplikasi mengeluarkan peringatan pada log console.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
Routing engine akan mengizinkan aplikasi melakukan startup, tetapi ketika request yang cocok dievaluasi dan DFA matcher menemukan dua kandidat endpoint yang identik tanpa pembeda yang valid, framework akan melempar <code>AmbiguousMatchException</code> dan mengembalikan respon HTTP 500.
</details>

---

**Soal 5**: Fitur apa pada Minimal API yang berfungsi setara dengan Action Filters pada MVC Controller?
* A) `IActionFilter`
* B) `IEndpointFilter`
* C) `IMiddleware`
* D) `IRouteHandlerFilter`

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
<code>IEndpointFilter</code> adalah interface resmi yang diperkenalkan pada .NET 7 untuk mengintersepsi, memodifikasi argumen, atau memvalidasi eksekusi dari handler Minimal API sebelum dan sesudah handler dijalankan.
</details>

---

### Tingkat Lanjut (Intermediate)

**Soal 6**: Mengapa Minimal API dengan Native AOT (.NET 8) melarang penggunaan refleksi dinamis dan dynamic code emission via Expression Trees pada `RequestDelegateFactory`?
* A) Karena kode biner Native AOT tidak memiliki runtime JIT (Just-In-Time) compiler yang dibutuhkan untuk mengompilasi Expression Tree menjadi instruksi mesin pada saat runtime.
* B) Karena Native AOT tidak mengizinkan pengalokasian memori pada Thread Stack.
* C) Karena Microsoft membatasi penggunaan Expression Tree hanya untuk Entity Framework 6.
* D) Karena sistem operasi Linux tidak mendukung pemanggilan fungsi virtual berbasis tabel pointer.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: A</b><br/>
Native AOT membuang seluruh komponen runtime JIT compiler untuk memangkas ukuran biner dan mengoptimalkan performa. Oleh sebab itu, semua kode yang membutuhkan kompilasi IL dinamis saat aplikasi berjalan (seperti <code>Expression.Compile()</code>) akan gagal jika tidak digantikan oleh Roslyn compile-time source generator (RDG).
</details>

---

**Soal 7**: Apa risiko fatal yang terjadi jika sebuah dependency bertipe `Scoped` diekstrak menggunakan operator assignment dari `app.Services` di dalam berkas konfigurasi root program lalu digunakan di dalam handler Minimal API?
* A) Runtime akan melempar `NullReferenceException` seketika.
* B) Service tersebut menjadi tertahan pada *root container* (*Captive Dependency*), mengubah siklus hidupnya menjadi Singleton, memicu kebocoran memori (*memory leak*), dan menyebabkan *concurrency conflict* jika objek tersebut tidak thread-safe.
* C) Dependency injection container akan mematikan aplikasi secara otomatis.
* D) HTTP pipeline akan memblokir semua request jaringan yang masuk.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
Mengambil instance Scoped langsung dari root provider (<code>app.Services</code>) membungkus dependensi tersebut di dalam memori root/singleton. Untuk dependensi non-thread-safe seperti EF Core <code>DbContext</code>, hal ini mengakibatkan konflik state saat diakses oleh multi-thread request secara bersamaan.
</details>

---

**Soal 8**: Manakah implementasi metode statis yang benar agar sebuah *Value Object* kustom dapat dibaca secara otomatis dari URL Query Parameter atau Route Parameter oleh Minimal API tanpa perlu atribut tambahan?
* A) `public bool ParseHttp(string raw)`
* B) `public static bool TryParse(string? s, IFormatProvider? provider, out T result)`
* C) `public T ConvertFrom(ReadOnlySpan<char> input)`
* D) `public void InitializeFromRoute(HttpContext ctx)`

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
<code>RequestDelegateFactory</code> secara khusus memeriksa keberadaan metode statis <code>TryParse</code> (dengan signature <code>(string?, out T)</code> atau <code>(string?, IFormatProvider?, out T)</code>). Keberadaan metode ini menandakan tipe tersebut mampu mem-parse nilainya sendiri dari string rute/query.
</details>

---

**Soal 9**: Bagaimana cara yang tepat untuk memisahkan definisi ratusan endpoint Minimal API ke dalam class-class terpisah agar kode tetap modular dan mendukung Open-Closed Principle?
* A) Menggunakan inheritance dengan membuat Base Minimal API Class.
* B) Menggunakan C# Extension Methods yang memperluas `IEndpointRouteBuilder` atau `RouteGroupBuilder` untuk meregistrasikan kumpulan endpoint pada file terisolasi.
* C) Membuat controller kosong lalu memanggil Minimal API di dalam konstruktor controller.
* D) Menyatukan seluruh class menjadi berkas nested class di dalam `Program.cs`.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
Membuat extension methods pada <code>IEndpointRouteBuilder</code> atau <code>RouteGroupBuilder</code> adalah idiom arsitektural standar industri pada .NET modern untuk memecah endpoint menjadi file-file kecil yang modular dan terfokus (sejalan dengan konsep Single Responsibility Principle).
</details>

---

**Soal 10**: Apa perbedaan fungsional utama antara eksekusi `Results.ValidationProblem(...)` dan `TypedResults.ValidationProblem(...)` dalam konteks kontrak API?
* A) `Results.ValidationProblem` mengembalikan HTTP status 401 Unauthorized, sedangkan `TypedResults` mengembalikan status 400 Bad Request.
* B) `TypedResults.ValidationProblem` menghasilkan metadata skema response eksplisit (RFC 7807 `HttpValidationProblemDetails`) ke sistem OpenAPI generator, sementara `Results.ValidationProblem` mengembalikan antarmuka `IResult` non-generik yang terdeteksi sebagai respon untyped (tipe tidak spesifik) kecuali jika ditambahkan atribut eksplisit.
* C) `Results.ValidationProblem` otomatis membatalkan thread database, sedangkan `TypedResults` tidak.
* D) Tidak ada perbedaan fungsional sama sekali, keduanya merupakan alias identik.

<details>
<summary>Jawaban & Penjelasan</summary>
<b>Jawaban: B</b><br/>
<code>TypedResults.ValidationProblem</code> mengembalikan tipe konkret <code>ValidationProblem</code> yang secara bawaan menyematkan metadata spesifikasi RFC 7807 ke OpenAPI/Swagger, memudahkan dokumentasi skema validasi otomatis tanpa perlu mengotori method dengan deklarasi atribut <code>[ProducesResponseType]</code>.
</details>

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Praktikum: Resilient E-Commerce Voucher Engine
Buatlah sebuah subsistem API independen berkinerja tinggi menggunakan arsitektur **Minimal API** murni (tanpa Controller) pada .NET 8 dengan rincian kebutuhan sebagai berikut:

#### 1. Spesifikasi Endpoint
* **`POST /api/v1/vouchers/claim`**:
  * Menerima Request Payload:
    ```json
    {
      "voucherCode": "DISCOUNT50",
      "customerId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "orderAmount": 250000.00
    }
    ```
  * Respons Sukses (HTTP 200 OK):
    ```json
    {
      "claimId": "guid",
      "discountAmount": 50000.00,
      "finalAmount": 200000.00,
      "claimedAt": "2026-03-30T10:00:00Z"
    }
    ```
  * Respons Validasi Gagal (HTTP 400 Bad Request / RFC 7807 ProblemDetails):
    * `voucherCode` wajib diisi, alfanumerik, maksimal 12 karakter.
    * `orderAmount` harus $> 0$.

#### 2. Kriteria Teknis & Arsitektur
1. **Zero-Controller Rule**: Seluruh pipeline tidak boleh mengimpor paket MVC (`Microsoft.AspNetCore.Mvc`) atau class turunan `ControllerBase`.
2. **Modular Architecture**: Implementasikan endpoint di file terpisah (`ClaimVoucherEndpoint.cs`) menggunakan extension method pada `RouteGroupBuilder`.
3. **Validation Pipeline**: Terapkan validasi input payload menggunakan **FluentValidation** yang diintegrasikan secara elegan menggunakan **`IEndpointFilter` generik**.
4. **Strong Typing Response**: Gunakan `Results<Ok<ClaimResponse>, ValidationProblem, NotFound<string>>` sebagai tipe balikan handler tanpa `IActionResult`.
5. **Observability**: Buat metrik sederhana menggunakan `ILogger` dengan memanfaatkan `LoggerMessageAttribute` generator untuk mencatat setiap voucher yang berhasil di-*claim* tanpa alokasi string heap.

#### 3. Kriteria Verifikasi Pengujian
* Buatlah Unit Test menggunakan xUnit yang memanggil static method handler secara **direct invocation** (mengirimkan argumen model dan dependency tiruan/mock langsung ke fungsi handler) dan lakukan *assertion* bahwa status hasil balikan berupa `Ok<ClaimResponse>`. Modul praktikum ini harus lulus kompilasi tanpa peringatan pemangkasan (*trimming warnings*).