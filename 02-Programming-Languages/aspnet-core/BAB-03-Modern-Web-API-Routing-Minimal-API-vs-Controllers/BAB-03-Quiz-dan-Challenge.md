# BAB 03: Quiz, Challenge, & Knowledge Check
**Modern Web API & Routing: Minimal API vs Controllers**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Endpoint Routing Engine Architecture
Jelaskan secara mendalam bagaimana arsitektur *Endpoint Routing* di ASP.NET Core bekerja sejak diperkenalkannya pemisahan antara `UseRouting()` dan `UseEndpoints()` (atau implisit di .NET 6/7/8/9). Bagaimana algoritma DFA (*Deterministic Finite Automaton*) matcher membedakan pemilihan endpoint antara route yang didaftarkan melalui Controller (`[Route("api/[controller]")]`) dan Minimal API (`app.MapGet(...)`)?

### Soal 1.2: Action Execution Pipeline vs RequestDelegate
Bandingkan siklus hidup eksekusi sebuah *HTTP request* pada ASP.NET Core MVC/Controller dengan Minimal API. Mengapa Controller membutuhkan komponen seperti `ControllerActionInvoker`, `ModelMetadataProvider`, dan `IActionFilter`, sementara Minimal API dapat mengeksekusi request secara langsung via *compiled delegate* (`RequestDelegate`)? Jelaskan dampaknya terhadap performa dan alokasi memori.

### Soal 1.3: Binding Resolution Precedence di Minimal API
Pada Minimal API, ASP.NET Core menerapkan aturan resolusi inferensi parameter (*parameter binding rules*) secara otomatis tanpa memerlukan atribut eksplisit jika kriteria tertentu terpenuhi. Jelaskan hierarki prioritas resolusi parameter tersebut mulai dari `BindAsync`/`TryParse`, Services (DI), Route Values, Query String, hingga Request Body. Kapan sebuah tipe data dianggap sebagai *Body* versus *Service* secara implisit?

### Soal 1.4: Endpoint Filters (`IEndpointFilter`) vs Action Filters (`IActionFilter`)
Analisis perbedaan arsitektural antara `IEndpointFilter` pada Minimal API dan `IAsyncActionFilter` pada Controller. Mengapa `EndpointFilterInvocationContext` tidak menyediakan akses langsung ke properti controller seperti `ActionDescriptor` atau `ModelStateDictionary`, dan bagaimana cara mengimplementasikan validasi model lintas endpoint menggunakan filter modern ini?

### Soal 1.5: OpenAPI Metadata Discovery Engine
Bagaimana cara kerja metadata extraction engine pada ASP.NET Core untuk membangkitkan dokumen OpenAPI/Swagger antara Controller (berbasis atribut seperti `[ProducesResponseType]`) dan Minimal API (berbasis extension methods seperti `.Produces<T>()` atau `.WithOpenApi()`)? Apa peran dari `EndpointMetadataCollection` dalam konteks ini?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: RequestDelegateGenerator (RDG) dan Native AOT Compilation
Pada .NET 8 dan seterusnya, Minimal API didukung oleh C# Source Generator yang dikenal sebagai *RequestDelegateGenerator* (RDG). Jelaskan apa yang dilakukan oleh RDG pada saat waktu kompilasi (*compile-time*) untuk meniadakan ketergantungan pada *runtime reflection* dan `DynamicMethod.Emit`. Mengapa arsitektur tradisional Controller sangat sulit dibuat kompatibel secara penuh dengan pemangkasan kode (*IL Trimming*) dan Native AOT?

### Soal 2.2: Memory Allocation Footprint: Boxing and Context Lifecycles
Saat sebuah endpoint menerima parameter `struct` berukuran besar atau parsing `int`/`Guid` via Route Data, telusuri alokasi memori heap yang terjadi pada Controller Action versus Minimal API. Dalam kondisi apa Minimal API tetap dapat memicu alokasi *boxing* atau alokasi *closure* yang tidak diinginkan pada runtime?

### Soal 2.3: Non-buffered Streaming & Large File Upload Handling
Anda diminta membangun endpoint upload file multi-gigabyte. Di Controller, developer sering kali terjebak menggunakan `IFormFile` yang secara otomatis memicu buffering disk/RAM melalui `FormModelBinder`. Bagaimana mekanisme internal Minimal API menangani streaming payload mentah (`HttpRequest.BodyReader` atau `PipeReader`) tanpa memicu memory overhead? Mengapa binding langsung ke `Stream` pada parameter delegasi Minimal API memerlukan perlakuan khusus?

### Soal 2.4: Ambiguous Match Exceptions & DFA Graph Optimization
Diberikan konfigurasi routing berikut:
- Route 1: `app.MapGet("/orders/{id}", ...)`
- Route 2: `app.MapGet("/orders/{code:regex(^[A-Z]{{3}}$)}", ...)`
- Route 3: `app.MapGet("/orders/active", ...)`

Jelaskan bagaimana DFA matcher ASP.NET Core mengevaluasi ketiga route di atas saat request datang dengan path `/orders/active`. Kapan ASP.NET Core melemparkan `AmbiguousMatchException` pada saat request dieksekusi, dan bagaimana mekanisme *literal scoring* vs *constrained parameter scoring* bekerja?

### Soal 2.5: Scoped Service Resolution via Route Group Builder
Perhatikan implementasi berikut:
```csharp
var group = app.MapGroup("/api/v1")
               .AddEndpointFilter<CustomAuditFilter>();
```
Jika `CustomAuditFilter` membutuhkan dependensi berumur `Scoped` (misalnya `ApplicationDbContext`), bagaimana ASP.NET Core mengelola resolusi *Service Provider* untuk filter tersebut di level Route Group? Apa bahayanya jika filter tersebut diinstansiasi sebagai singleton atau diregistrasikan via lambda closure di luar request scope?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi P99 pada Sistem Ingesti IoT Skala Tinggi
*Konteks*: Sebuah platform telemetri IoT menerima 80.000 HTTP POST request per detik yang mengirimkan payload metrik kecil (JSON < 500 byte). Sistem saat ini menggunakan ASP.NET Core Controllers klasik:
```csharp
[ApiController]
[Route("api/metrics")]
public class TelemetryController : ControllerBase
{
    private readonly ITelemetryService _service;
    public TelemetryController(ITelemetryService service) => _service = service;

    [HttpPost]
    public async Task<IActionResult> Ingest([FromBody] MetricPayload payload)
    {
        await _service.ProcessAsync(payload);
        return Ok();
    }
}
```
*Masalah*: Profiling APM menunjukkan bahwa latensi P99 mengalami degradasi parah hingga 600ms, dan GC (*Garbage Collection*) Gen 0/1 Collection terjadi ratusan kali per menit. CPU usage tinggi dihabiskan pada modul `System.Text.Json` dan `Microsoft.AspNetCore.Mvc.Core`.

#### Pertanyaan Diagnostik & Solusi Skenario A:
1. Bedah secara spesifik objek apa saja yang dialokasikan oleh framework MVC per request pada endpoint di atas (analisis Controller activation, Model Binding, ModelState validation, ActionFilter chains, dan IActionResult execution).
2. Rancang refaktorisasi menyeluruh menggunakan Minimal API, C# Source Generators (RDG & STJ Context), dan struktur zero-allocation untuk memangkas Gen 0 allocation hingga titik terendah.

---

### Skenario B: Race Condition dan State Leakage pada Endpoint Filter
*Konteks*: Sebuah startup fintech membuat sistem autentikasi transaksi menggunakan Minimal API dengan *Endpoint Filter* untuk melakukan pengecekan saldo dan *distributed lock*:
```csharp
public class TransactionLockFilter : IEndpointFilter
{
    private readonly ILockService _lockService;
    private string _currentLockKey; // Disimpan di level field filter

    public TransactionLockFilter(ILockService lockService)
    {
        _lockService = lockService;
    }

    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context, 
        EndpointFilterDelegate next)
    {
        var request = context.GetArgument<TransactionRequest>(0);
        _currentLockKey = $"lock:{request.AccountId}";

        if (!await _lockService.AcquireAsync(_currentLockKey))
            return Results.Conflict("Concurrent transaction detected.");

        try
        {
            return await next(context);
        }
        finally
        {
            await _lockService.ReleaseAsync(_currentLockKey);
        }
    }
}
```
Pendaftaran endpoint:
```csharp
app.MapPost("/api/transactions", HandleTransaction)
   .AddEndpointFilter<TransactionLockFilter>();
```
*Masalah*: Di bawah beban concurrency tinggi, terjadi situasi fatal di mana akun nasabah A melepaskan lock milik nasabah B, menyebabkan *double-spending* dan data integrity corruption.

#### Pertanyaan Diagnostik & Solusi Skenario B:
1. Mengapa race condition di atas terjadi? Jelaskan siklus hidup (*lifecycle instantiation*) dari `IEndpointFilter` saat didaftarkan melalui `.AddEndpointFilter<T>()` pada Minimal API.
2. Tuliskan kode perbaikan filter di atas agar sepenuhnya *thread-safe*, memanfaatkan context execution yang benar, dan menjamin bahwa data lock tidak pernah bocor antar request yang berjalan paralel.

---

### Skenario C: Arsitektur Monolith-to-Modular Micro-APIs Enterprise
*Konteks*: Enterprise Core Banking ingin memodernisasi monolith internal yang memiliki 450+ Controller endpoints. Tim arsitektur terbagi menjadi dua kubu:
- **Kubu A**: Ingin mempertahankan Controller dengan alasan kemudahan isolasi domain melalui folder structure, generic base controller, automatic validation pipeline (`FluentValidation` + `ActionFilter`), dan familiaritas tim (20+ developer).
- **Kubu B**: Ingin migrasi 100% ke Minimal API dengan alasan kecepatan cold-start container (Kubernetes auto-scaling), performa tinggi, dan Native AOT readiness. Namun mereka kesulitan menjaga keteraturan struktur project karena Minimal API rentan berubah menjadi file `Program.cs` yang masif ("Spaghetti Route File").

#### Pertanyaan Diagnostik & Solusi Skenario C:
1. Sebagai Principal Architect, lakukan perbandingan trade-off komprehensif antara kedua pendekatan di atas menggunakan matriks:
   - *Cold-start & Footprint memory*
   - *Maintainability & Modular Organization*
   - *Team Cognitive Load & Developer Ergonomics*
   - *Compilation time & Build pipelines*
2. Rancang arsitektur implementasi folder, abstraksi modul (`IRouteModule` atau Group Pattern), dan pipeline validasi yang membedah bagaimana 450+ endpoint dapat diorganisasikan menggunakan Minimal API secara modular, rapi, dan scalable tanpa framework eksternal (murni native features .NET).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Secure Idempotent Transaction Gateway

#### Deskripsi Masalah
Anda ditugaskan merancang API gateway internal untuk memproses pembayaran berkecepatan tinggi. Endpoint ini harus menerima data transaksi, menjamin idempotensi, memvalidasi payload, dan mengeksekusi proses secara aman. Implementasi sebelumnya menggunakan Controllers gagal memenuhi Service Level Objective (SLO): throughput minimal 25.000 RPS dengan latensi maksimal (P99) < 20ms pada mesin 4 Core / 8GB RAM.

#### Kebutuhan Fungsional & Non-Fungsional
1. **Endpoint**: `POST /api/v2/payments/charge`
2. **Payload**:
   ```json
   {
     "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
     "amount": 150000.00,
     "currency": "IDR",
     "targetAccount": "ACC-992182"
   }
   ```
3. **Idempotency**:
   - Header wajib: `X-Idempotency-Key: <UUID>`
   - Jika key sudah pernah diproses dan masih dalam cache/store, return HTTP 409 Conflict atau cache response sebelumnya.
   - Pengecekan dan penguncian idempotensi harus diimplementasikan melalui **`IEndpointFilter` reusable**.
4. **Validation**:
   - `amount` harus > 0.
   - `currency` hanya boleh "IDR" atau "USD".
   - `targetAccount` harus diawali prefiks "ACC-".
   - Model binding harus zero-allocation atau minimum allocation (gunakan Source-Generated JSON Context).
5. **Architectural Constraints**:
   - Wajib menggunakan **Minimal API** dengan **Endpoint Route Grouping**.
   - Harus kompatibel dengan **Native AOT** (`PublishAot=true`), dilarang menggunakan JSON Serializer berbasis reflection runtime.
   - Dilarang menggunakan memory buffering untuk pembacaan header / parameter.
   - Terapkan Typed Results (`TypedResults.Ok(...)`, `TypedResults.Conflict(...)`, `TypedResults.BadRequest(...)`).

#### Output yang Diharapkan
Sediakan implementasi C# lengkap yang memuat:
1. Deklarasi DTO dan `JsonSerializerContext` berbasis Source Generator.
2. Implementasi `IdempotencyEndpointFilter` yang stateless dan concurrency-safe.
3. Definisi extension method `MapPaymentEndpoints(this IEndpointRouteBuilder routes)` yang menerapkan Route Grouping, Typed Results, dan metadata OpenAPI.
4. Kode konfigurasi `Program.cs` yang mengintegrasikan seluruh komponen di atas secara bersih.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental arsitektur routing DFA matcher vs MVC legacy route table.
- [ ] Siklus hidup lengkap request pada Minimal API vs Controller pipeline.
- [ ] Aturan inferensi binding parameter pada Minimal API (`FromServices`, `FromBody`, `FromRoute`, `FromQuery`, `BindAsync`).
- [ ] Cara kerja C# Source Generator (RequestDelegateGenerator) di .NET 8+ dalam memproduksi eksekutor endpoint tanpa reflection.
- [ ] Cara mengisolasi middleware, authorization, dan cross-cutting concerns menggunakan `RouteGroupBuilder`.
- [ ] Cara kerja dan lifetime instances dari `IEndpointFilter`.
- [ ] Mekanisme metadata OpenAPI menggunakan `EndpointMetadataCollection` dan `TypedResults`.
- [ ] Keterbatasan dan trade-off Controllers terhadap Native AOT compilation dan runtime trimming.

### Saya tidak perlu menghafal:
- [ ] Seluruh overload method dari `EndpointRouteBuilderExtensions.MapMethods`.
- [ ] Konfigurasi internal compiler regex flags untuk DFA Route Constraints.
- [ ] Implementasi internal method `DynamicMethod.Emit` yang dipakai fallback legacy Minimal API.
- [ ] Format spesifikasi JSON OpenAPI schema secara manual baris demi baris.

### Saya harus bisa melakukan:
- [ ] Mengonversi Controller legacy kompleks yang memiliki Action Filters menjadi Minimal API dengan `IEndpointFilter` tanpa mengubah behavioral logic.
- [ ] Mengonfigurasi `JsonSerializerContext` untuk mencapai serialisasi JSON zero-reflection pada Minimal API.
- [ ] Mengimplementasikan Custom Model Binder via `BindAsync` atau `TryParse` untuk parsing custom type secara efisien.
- [ ] Melakukan troubleshooting dan memperbaiki masalah `AmbiguousMatchException` pada route path yang bertabrakan.
- [ ] Mendesain struktur modular untuk aplikasi berskala enterprise (ratusan endpoint) berbasis Minimal API tanpa penurunan readability.
- [ ] Melakukan profiling alokasi memori heap (Gen 0/1/2) antara implementasi Controller vs Minimal API menggunakan dotnet-dump atau dotMemory.