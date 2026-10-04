# BAB 07: Arsitektur Enterprise & Clean Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Core Domain Model Murni (Rich Domain Model)** menggunakan C# 12 / .NET 8+ tanpa ketergantungan pada dependensi eksternal (zero external dependencies) dengan prinsip Domain-Driven Design (DDD).
2. **Mengeksekusi Pola Transaksional Outbox (Transactional Outbox Pattern)** menggunakan EF Core `SaveChangesInterceptor` untuk menjamin konsistensi data antara database relasional dan message broker (menghindari dual-write hazard).
3. **Membangun CQRS (Command Query Responsibility Segregation) Pipeline** tingkat enterprise memanfaatkan MediatR Pipeline Behaviors untuk Idempotensi, Validasi FluentValidation, Cross-Cutting Logging, dan Metrics OpenTelemetry.
4. **Menerapkan Result Pattern** terstruktur untuk mengeliminasi penggunaan exception sebagai alur kendali logika bisnis (anti-pattern control flow exceptions) guna mengoptimalkan throughput dan alokasi memori runtime .NET.
5. **Mengevaluasi dan Mengatasi Trade-off Performa** antara abstraksi Clean Architecture murni dengan kebutuhan high-throughput read operations (Dapper read models vs EF Core tracked entities).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Runtime & SDK**: .NET 8.0 SDK atau lebih baru.
* **C# Language Features**: Records, Pattern Matching, Init-only setters, Primary Constructors, Generic Constraints, ValueTask, Unsafe code awareness, dan Async/Await internals (`SynchronizationContext`, `TaskScheduler`).
* **Entity Framework Core**: Change Tracker lifecycle, Shadow Properties, Interceptors, Owned Entities, dan Raw SQL projections.
* **Dasar Arsitektur**: Pemahaman dasar Bab 07 Modul 01 mengenai Onion Architecture, Dependency Inversion Principle (DIP), dan pemisahan Core vs Infrastructure.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi enterprise Clean Architecture bukan sekadar memisahkan folder menjadi *Core*, *Application*, dan *Infrastructure*, melainkan menegakkan batas isolasi domain (*Domain Isolation Boundary*) di mana domain engine runtime tidak boleh terdistorsi oleh framework I/O, serialisasi HTTP, maupun ORM persistence concerns.

```
       +-------------------------------------------------------------+
       | Presentation Layer (Web API, Minimal API, gRPC, Worker)     |
       +-------------------------------------------------------------+
                                     |
                                     v
       +-------------------------------------------------------------+
       | Application Layer (Commands, Queries, Behaviors, DTOs)     |
       +-------------------------------------------------------------+
                                     |
                                     v
       +-------------------------------------------------------------+
       | Domain Layer (Aggregates, Entities, Value Objects, Events)  |
       |                   *NO EXTERNAL REFERENCES*                  |
       +-------------------------------------------------------------+
                                     ^
                                     | (Implements interfaces via DIP)
       +-------------------------------------------------------------+
       | Infrastructure Layer (EF Core, Redis, Kafka, Azure SDK)     |
       +-------------------------------------------------------------+
```

#### Komponen Internal Kritis:

1. **Rich Domain Model vs. Anemic Domain Model**:
   * *Anemic Domain Model*: Entity hanya kumpulan getter/setter publik tanpa aturan proteksi invariansi. Modifikasi state tersebar di Service Layer, menyebabkan kebocoran domain logic dan potensi state tidak valid.
   * *Rich Domain Model*: Entity membungkus *encapsulation boundary*. Setter bersifat `private` atau `internal`. Modifikasi state hanya melalui metode eksplisit domain yang memvalidasi domain invariants. Menghasilkan *Domain Events* secara in-memory saat terjadi mutasi state bisnis yang sah.

2. **Domain Events vs. Integration Events**:
   * *Domain Events*: Mengindikasikan perubahan internal dalam batas aggregate yang sama. Terjadi dalam satu konteks bounded context dan disinkronkan dalam database transaction yang sama. Bersifat in-process.
   * *Integration Events*: Mengindikasikan kejadian penting untuk bounded context atau sistem lain. Harus di-publish keluar boundary menggunakan network serialization (JSON/Protobuf) melalui message bus.

3. **Dual-Write Problem & Transactional Outbox Pattern**:
   * Saat handler menulis ke relational database via EF Core dan mempublikasikan event ke Kafka/RabbitMQ secara sekuensial, kegagalan jaringan setelah commit database akan menyebabkan message hilang. Sebaliknya, mempublikasikan message sebelum commit database dapat menimbulkan *phantom message* jika database commit mengalami rollback.
   * *Solusi Produksi*: Tulis entitas bisnis dan pesan outbox ke dalam satu transaksi ACID database lokal. Background publisher (Worker/Debezium/Poller) bertugas menyalurkan pesan dari tabel outbox ke broker dengan jaminan *At-Least-Once Delivery*.

4. **Change Tracker & EF Core Interceptor Internals**:
   * Selama `DbContext.SaveChangesAsync`, `DbContext` menjalankan deteksi perubahan.
   * Kita menyisipkan `SaveChangesInterceptor` untuk mengekstrak seluruh `IDomainEvent` dari aggregate yang terlibat, mengonversinya menjadi record `OutboxMessage`, dan menyisipkannya ke `DbSet<OutboxMessage>` dalam transaksi atomic yang sama secara transparan.

---

### 4. Why & What

| Dimensi | Pendekatan Monolit Tradisional (CRUD/N-Tier) | Clean Architecture Enterprise Tingkat Lanjut |
| :--- | :--- | :--- |
| **Model Domain** | Anemic Data Classes (DTOs bertopeng Entity), validasi di UI/Controller. | Ubiquitous Language, Aggregate Roots dengan invariant enforcement ketat. |
| **I/O Coupling** | Logika bisnis mengimpor `DbContext`, `HttpRequest`, atau AWS SDK langsung. | Domain murni C# POCO, dependensi dibalikkan via Interface/Ports. |
| **Message Safety** | Publish event langsung ke RabbitMQ/Kafka setelah save data (Rentan Dual-Write). | Transactional Outbox terintegrasi via EF Core Interceptor (Guaranteed Consistency). |
| **Error Handling** | Lempar exception (`throw CustomException`) untuk error validasi atau data not found. | `Result<T, E>` / Result Pattern: Eksekusi prediktif tanpa alokasi overhead StackTrace. |
| **Query Scaling** | Tracking entities dimuat penuh ke memori walau hanya menampilkan 3 field di UI. | Segregated Read Engine (Dapper/EF Core Raw Projections via NoTracking) bypass domain. |

---

### 5. How (Workflow Detail)

Alur eksekusi request mutasi data (Command) dari Presentation layer menuju Domain dan Infrastructure:

```
[HTTP POST Request]
         |
         v
[Minimal API Endpoint] -> Unpack payload to Command Record
         |
         v
[MediatR / Pipeline Invocation]
         |
         +--> [LoggingBehavior]: Catat CorrelationId, Start Timer
         |
         +--> [ValidationBehavior]: Jalankan FluentValidation. Jika gagal -> Return Result.Failure
         |
         +--> [IdempotencyBehavior]: Periksa Idempotency-Key di Cache/DB. Jika pernah diproses -> Return Cached Result
         |
         +--> [CommandHandler]: Handle command
                  |
                  +--> Load Aggregate via IRepository (EF Core Tracking)
                  +--> Execute Business Method pada Entity:
                  |        - Periksa invariant
                  |        - Mutasi internal state
                  |        - Raise DomainEvent (tambahkan ke internal collection)
                  +--> Return Result.Success
         |
         v
[UnitOfWork / SaveChangesAsync Interceptor]
         |
         +--> Ambil semua Aggregate yang menghasilkan Domain Events
         +--> Ubah Domain Events menjadi OutboxMessage instances
         +--> Tambahkan OutboxMessage ke Transaction yang sama
         +--> COMMIT Database Transaction (Atomic)
         |
         v
[HTTP 200/201/204 Response] dikirim ke klien
         |
         | (Asynchronous Background Task)
         v
[Outbox Processor Worker] -> Poll outbox table -> Publish to Message Broker -> Update ProcessedAtUtc
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Kokpit Pesawat Komersial
* **Core Domain**: Pilot, navigasi dasar, dan hukum aerodinamika. Tidak peduli apakah instrumen menggunakan kabel mekanik konvensional atau sistem Fly-By-Wire elektronik digital. Hukum gravitasi dan manuver pesawat tetap sama.
* **Presentation**: Tombol, tuas, dan layar tampilan di kokpit tempat pilot berinteraksi.
* **Infrastructure**: Pompa hidrolik, aktuator elektrik, tangki avtur, dan radio transponder. Jika pompa hidrolik (EF Core/PostgreSQL) diganti dengan aktuator listrik modern (MongoDB/EventStore), insting kendali pilot (Domain logic) tidak mengalami modifikasi.

#### Diagram Transaksi Outbox & MediatR Pipeline

```
========================= APPLICATION PIPELINE EXECUTION =========================

Request ---> [Validation Pipeline] ---> [Idempotency Check]
                     | Fail                     | Found (Duplicate)
                     v                          v
             [Early Result.Fail]        [Return Cached Result]
                     |
                     | Success & Unique
                     v
             [Command Handler]
                     |
                     v
   +----------------- Aggregate Boundary -----------------+
   |                                                      |
   |   Execute: order.ConfirmPayment(paymentDetails)      |
   |                                                      |
   |   1. Invariant: Status Must Be Pending               |
   |   2. Mutate: Status = Confirmed                      |
   |   3. Raise: OrderPaymentConfirmedDomainEvent         |
   |                                                      |
   +------------------------------------------------------+
                     |
                     v
         [SaveChangesInterceptor]
                     |
        +------------+------------+
        |                         |
        v                         v
[Orders Table UPDATE]   [Outbox Table INSERT]
        |                         |
        +------------+------------+
                     |
             (Single ACID Txn)
                     |
                     v
              [Database Commit]
                     |
===================== ASYNCHRONOUS ENGINE =====================
                     |
     [Outbox Background Worker / Poller]
                     |
                     +---> Reads Unprocessed Outbox Records
                     +---> Publishes to Message Broker (Kafka/RabbitMQ)
                     +---> Marks ProcessedAtUtc = DateTime.UtcNow
```

---

### 7. Simple Example & Practical Example

#### A. Aggregate Root Murni dengan Result Pattern & Domain Events

```csharp
// =========================================================================
// Domain Layer: Tanpa dependensi eksternal selain primitif runtime BCL.
// =========================================================================
namespace Enterprise.Domain.Common;

public abstract class Entity<TId>
{
    public TId Id { get; protected set; } = default!;
    
    private readonly List<IDomainEvent> _domainEvents = [];
    public IReadOnlyCollection<IDomainEvent> DomainEvents => _domainEvents.AsReadOnly();

    public void AddDomainEvent(IDomainEvent domainEvent) => _domainEvents.Add(domainEvent);
    public void ClearDomainEvents() => _domainEvents.Clear();
}

public interface IDomainEvent
{
    Guid EventId { get; }
    DateTime OccurredOnUtc { get; }
}

public sealed record Error(string Code, string Message)
{
    public static readonly Error None = new(string.Empty, string.Empty);
    public static implicit operator Result(Error error) => Result.Failure(error);
}

public class Result
{
    protected Result(bool isSuccess, Error error)
    {
        if (isSuccess && error != Error.None || !isSuccess && error == Error.None)
            throw new InvalidOperationException("Invalid Result State");

        IsSuccess = isSuccess;
        Error = error;
    }

    public bool IsSuccess { get; }
    public bool IsFailure => !IsSuccess;
    public Error Error { get; }

    public static Result Success() => new(true, Error.None);
    public static Result Failure(Error error) => new(false, error);
    public static Result<TValue> Success<TValue>(TValue value) => new(value, true, Error.None);
    public static Result<TValue> Failure<TValue>(Error error) => new(default!, false, error);
}

public class Result<TValue> : Result
{
    private readonly TValue _value;

    protected internal Result(TValue value, bool isSuccess, Error error) : base(isSuccess, error)
    {
        _value = value;
    }

    public TValue Value => IsSuccess 
        ? _value 
        : throw new InvalidOperationException("Value cannot be accessed on failed result.");
        
    public static implicit operator Result<TValue>(TValue value) => Success(value);
    public static implicit operator Result<TValue>(Error error) => Failure<TValue>(error);
}
```

```csharp
namespace Enterprise.Domain.Orders;

using Enterprise.Domain.Common;

public sealed record OrderId(Guid Value);
public sealed record Money(decimal Amount, string Currency);

public sealed record OrderPaidDomainEvent(
    Guid EventId, 
    DateTime OccurredOnUtc, 
    OrderId OrderId, 
    decimal Amount
) : IDomainEvent;

public enum OrderStatus
{
    Draft = 1,
    Submitted = 2,
    Paid = 3,
    Cancelled = 4
}

public sealed class Order : Entity<OrderId>
{
    private Order() { } // EF Core Required Constructor

    private Order(OrderId id, Guid customerId, Money totalAmount)
    {
        Id = id;
        CustomerId = customerId;
        TotalAmount = totalAmount;
        Status = OrderStatus.Draft;
    }

    public Guid CustomerId { get; private set; }
    public Money TotalAmount { get; private set; } = null!;
    public OrderStatus Status { get; private set; }
    public DateTime CreatedAtUtc { get; private set; }
    public DateTime? PaidAtUtc { get; private set; }

    public static Result<Order> Create(Guid customerId, decimal amount, string currency)
    {
        if (customerId == Guid.Empty)
            return Result.Failure<Order>(new Error("Order.InvalidCustomer", "CustomerId must not be empty."));

        if (amount <= 0)
            return Result.Failure<Order>(new Error("Order.InvalidAmount", "Total amount must be greater than zero."));

        var order = new Order(new OrderId(Guid.NewGuid()), customerId, new Money(amount, currency))
        {
            CreatedAtUtc = DateTime.UtcNow
        };

        return Result.Success(order);
    }

    public Result MarkAsPaid()
    {
        if (Status != OrderStatus.Draft && Status != OrderStatus.Submitted)
        {
            return Result.Failure(new Error(
                "Order.InvalidStateTransition", 
                $"Cannot transition order status from {Status} to Paid."));
        }

        Status = OrderStatus.Paid;
        PaidAtUtc = DateTime.UtcNow;

        AddDomainEvent(new OrderPaidDomainEvent(
            Guid.NewGuid(), 
            DateTime.UtcNow, 
            Id, 
            TotalAmount.Amount));

        return Result.Success();
    }
}
```

#### B. EF Core Infrastructure & Transactional Outbox Interceptor

```csharp
// =========================================================================
// Infrastructure Layer: Implementasi Interceptor & Database Context
// =========================================================================
namespace Enterprise.Infrastructure.Outbox;

public sealed class OutboxMessage
{
    public Guid Id { get; set; }
    public string Type { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public DateTime OccurredOnUtc { get; set; }
    public DateTime? ProcessedOnUtc { get; set; }
    public string? Error { get; set; }
}
```

```csharp
namespace Enterprise.Infrastructure.Persistence.Interceptors;

using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Enterprise.Domain.Common;
using Enterprise.Infrastructure.Outbox;

public sealed class ConvertDomainEventsToOutboxMessagesInterceptor : SaveChangesInterceptor
{
    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        DbContext? dbContext = eventData.Context;
        if (dbContext is null)
        {
            return base.SavingChangesAsync(eventData, result, cancellationToken);
        }

        var domainEvents = dbContext.ChangeTracker
            .Entries<Entity<OrderId>>() // Atau generic interface terpadu IHasDomainEvents
            .Where(entry => entry.Entity.DomainEvents.Any())
            .Select(entry => entry.Entity)
            .ToList();

        var outboxMessages = domainEvents
            .SelectMany(entity =>
            {
                var events = entity.DomainEvents.ToList();
                entity.ClearDomainEvents();
                return events;
            })
            .Select(domainEvent => new OutboxMessage
            {
                Id = domainEvent.EventId,
                OccurredOnUtc = domainEvent.OccurredOnUtc,
                Type = domainEvent.GetType().AssemblyQualifiedName ?? domainEvent.GetType().Name,
                Content = JsonSerializer.Serialize(domainEvent, domainEvent.GetType())
            })
            .ToList();

        if (outboxMessages.Count != 0)
        {
            dbContext.Set<OutboxMessage>().AddRange(outboxMessages);
        }

        return base.SavingChangesAsync(eventData, result, cancellationToken);
    }
}
```

#### C. MediatR Pipeline Behavior untuk Idempotensi dan UnitOfWork

```csharp
// =========================================================================
// Application Layer: Pipeline Behaviors
// =========================================================================
namespace Enterprise.Application.Behaviors;

using MediatR;
using Microsoft.Extensions.Logging;
using Enterprise.Domain.Common;

public interface IIdempotentCommand<TResponse> : IRequest<TResponse>
{
    Guid RequestId { get; }
}

public interface IIdempotencyService
{
    Task<bool> HasBeenProcessedAsync(Guid requestId, CancellationToken ct);
    Task MarkAsProcessedAsync(Guid requestId, CancellationToken ct);
}

public sealed class IdempotentCommandPipelineBehavior<TRequest, TResponse>(
    IIdempotencyService idempotencyService,
    ILogger<IdempotentCommandPipelineBehavior<TRequest, TResponse>> logger)
    : IPipelineBehavior<TRequest, TResponse>
    where TRequest : IIdempotentCommand<TResponse>
    where TResponse : Result
{
    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        if (await idempotencyService.HasBeenProcessedAsync(request.RequestId, cancellationToken))
        {
            logger.LogWarning("Request {RequestId} has already been processed. Skipping.", request.RequestId);
            return (TResponse)Result.Failure(new Error("Concurrency.IdempotentConflict", "Request already handled."));
        }

        TResponse response = await next();

        if (response.IsSuccess)
        {
            await idempotencyService.MarkAsProcessedAsync(request.RequestId, cancellationToken);
        }

        return response;
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Settlement Transaksi Escrow E-Commerce Global
* **Tantangan Arsitektur**:
  Sistem escrow memproses pencairan dana hingga $100M/hari. Masalah utama:
  1. Jaringan payment gateway sering timeout, memicu retry agresif dari klien (risiko double disbursement).
  2. Database deadlocks terjadi pada PostgreSQL saat event settlement di-publish langsung di tengah traffic burst (5000 TPS).
  3. Penggunaan HTTP Status 500 akibat unhandled exception mengaburkan status riil transaksi.
* **Solusi Terpasang**:
  1. *Core Banking Domain Invariants*: Entitas `EscrowAccount` dengan lock version concurrency (`xmin` di PostgreSQL). Mutasi saldo menggunakan Rich Domain logic yang menjamin saldo tidak pernah bernilai negatif.
  2. *Pipeline Idempotensi Terdistribusi*: Memanfaatkan Redis distributed lock dengan MediatR behavior. Payload hash dicocokkan dengan TTL 24 jam.
  3. *Outbox Poller dengan Batching*: Pekerja latar belakang (`BackgroundService`) membaca tabel `Outbox` secara batch sebesar 500 record per polling menggunakan ekspresi SQL:
     ```sql
     SELECT * FROM "OutboxMessages" 
     WHERE "ProcessedOnUtc" IS NULL 
     ORDER BY "OccurredOnUtc" ASC 
     LIMIT 500 
     FOR UPDATE SKIP LOCKED;
     ```
     `FOR UPDATE SKIP LOCKED` mengeliminasi resource contention antar multi-instance worker pod di Kubernetes.

---

### 9. Trade-offs

| Aspek Arsitektur | Clean Architecture Enterprise (Rich DDD + Outbox) | Simple Architecture (Minimal API + Direct DbContext) | Analisis Trade-off Engineering |
| :--- | :--- | :--- | :--- |
| **Throughput (TPS)** | Sedang - Tinggi (Terbebani interceptor, pipeline hooks, dan serialisasi JSON). | Sangat Tinggi (Minimal object allocation, zero indirect layers). | Mengorbankan ~5-15% raw latency/throughput demi integritas finansial dan determinisme. |
| **Latency Read** | Read pipeline terisolasi (CQRS) bisa secepat Simple Architecture via Dapper. | Sangat Rendah jika menggunakan EF Core `AsNoTracking`. | Read path harus dipisah dari Write path untuk menghindari over-abstraction entity loading. |
| **Development Cost** | Tinggi. Membutuhkan disiplin pattern, pipeline behaviors, outbox tables, background engines. | Rendah. Siap pakai dalam hitungan jam untuk sistem CRUD. | Clean Architecture tidak tepat untuk aplikasi berumur pendek atau aplikasi tanpa invariant kompleks. |
| **Data Consistency** | Eventual Consistency pada message broker; Strong ACID pada domain state lokal. | Potensi Partial Failures tinggi (Dual-Write issue jika broker down saat DB commit selesai). | Outbox memprioritaskan Reliability dibanding instant notification ke external boundaries. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kebocoran `IQueryable` dari Repository
* *Kesalahan*: Mengembalikan `IQueryable<T>` dari Domain Repository ke Application Service.
* *Dampak*: Logika persistence (misal: lazy loading, database-specific query operators) bocor ke Application/Presentation Layer. Invariant tidak lagi terlindungi karena query dapat diimprovisasi di luar Aggregate.
* *Solusi*: Repository hanya boleh mengekspos metode yang mengembalikan `Task<AggregateRoot?>` atau collection murni (`IReadOnlyList<T>`).

#### 2. Concurrency Exception pada DbContext Scoped Lifecycle
* *Kesalahan*: Menginjeksi `AppDbContext` secara paralel di dalam `Task.WhenAll()` atau worker thread background tanpa child scope baru.
* *Dampak*: `InvalidOperationException: A second operation was started on this context instance before a previous operation completed.`
* *Solusi*: Gunakan `IServiceScopeFactory` untuk membuat scope individual per task background worker.

#### 3. Outbox Table Bloat (Timbunan Data Outbox)
* *Kesalahan*: Tidak merancang strategi purge/retention pada tabel `OutboxMessages`.
* *Dampak*: Tabel membesar hingga puluhan juta baris, memperlambat sequential scan dan indeks DB.
* *Solusi*: Buat cron-job/partitioning drop table untuk record outbox yang memiliki `ProcessedOnUtc != NULL` dan berusia lebih dari 7 hari.

---

### 11. Best Practices (Production Checklist)

- [ ] **Domain Model Isolation**: Proyek Domain tidak boleh memiliki referensi paket NuGet pihak ketiga (termasuk EF Core, Newtonsoft.Json).
- [ ] **Strict Private Constructors**: Seluruh Aggregate Root dan Entity memiliki private parameterless constructor untuk EF Core materializer, dan factory methods terproteksi untuk instansiasi baru.
- [ ] **Value Objects Immutability**: Gunakan C# `record` dengan init-only properties untuk Value Objects guna menegakkan equality-by-value.
- [ ] **Penyisipan Interceptor**: Pastikan interceptor `ConvertDomainEventsToOutboxMessagesInterceptor` didaftarkan sebagai `Singleton` (jika stateless) atau `Scoped` di `AddDbContext`.
- [ ] **Deadlock Mitigation**: Outbox processing SQL wajib menggunakan locking non-blocking: `FOR UPDATE SKIP LOCKED`.
- [ ] **Structured Logging Correlation**: Setiap log message di MediatR pipeline wajib memuat `CorrelationId` untuk keterlacakan end-to-end melalui distributed trace.
- [ ] **Avoid Anti-Pattern Result Misuse**: Result pattern hanya untuk domain/validation failures, bukan unhandled infrastructure crashes (out-of-memory, network down tetap melempar unhandled exceptions).

---

### 12. Hands-on Practice

Bangun fondasi modul secara manual di lingkungan CLI:

#### Langkah 1: Setup Workspace & Solution Structure
```bash
mkdir -p hands-on/m02/EnterpriseCleanArch
cd hands-on/m02/EnterpriseCleanArch

dotnet new sln -n EnterpriseCleanArch
dotnet new classlib -n Enterprise.Domain -f net8.0
dotnet new classlib -n Enterprise.Application -f net8.0
dotnet new classlib -n Enterprise.Infrastructure -f net8.0
dotnet new webapi -n Enterprise.Api -f net8.0 --use-minimal-apis

dotnet sln add Enterprise.Domain/Enterprise.Domain.csproj
dotnet sln add Enterprise.Application/Enterprise.Application.csproj
dotnet sln add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj
dotnet sln add Enterprise.Api/Enterprise.Api.csproj

# Hubungkan Dependensi (Dependency Inversion Flow)
dotnet add Enterprise.Application/Enterprise.Application.csproj reference Enterprise.Domain/Enterprise.Domain.csproj
dotnet add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj reference Enterprise.Application/Enterprise.Application.csproj
dotnet add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj reference Enterprise.Domain/Enterprise.Domain.csproj
dotnet add Enterprise.Api/Enterprise.Api.csproj reference Enterprise.Infrastructure/Enterprise.Infrastructure.csproj
dotnet add Enterprise.Api/Enterprise.Api.csproj reference Enterprise.Application/Enterprise.Application.csproj
```

#### Langkah 2: Tambahkan Package Dependencies
```bash
# Application Layer
dotnet add Enterprise.Application/Enterprise.Application.csproj package MediatR --version 12.2.0
dotnet add Enterprise.Application/Enterprise.Application.csproj package FluentValidation.DependencyInjectionExtensions --version 11.9.0

# Infrastructure Layer
dotnet add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj package Microsoft.EntityFrameworkCore --version 8.0.3
dotnet add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj package Microsoft.EntityFrameworkCore.SqlServer --version 8.0.3
dotnet add Enterprise.Infrastructure/Enterprise.Infrastructure.csproj package Microsoft.EntityFrameworkCore.Design --version 8.0.3
```

#### Langkah 3: Definisikan Kontrak Database Context
Tambahkan implementasi DbContext di layer `Enterprise.Infrastructure/Persistence/AppDbContext.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using Enterprise.Domain.Orders;
using Enterprise.Infrastructure.Outbox;

namespace Enterprise.Infrastructure.Persistence;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OutboxMessage> OutboxMessages => Set<OutboxMessage>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
```

---

### 13. Exercise

#### Level 1 (Easy):
* **Tugas**: Tambahkan Value Object `Address` (Street, City, PostalCode, Country) ke dalam domain model menggunakan C# 12 `record`.
* **Kriteria**: Pastikan immutable, implementasikan validasi bahwa `PostalCode` tidak boleh kosong dan panjangnya harus valid, kembalikan `Result<Address>`.

#### Level 2 (Medium):
* **Tugas**: Buat generic MediatR `LoggingPipelineBehavior<TRequest, TResponse>` yang menghitung durasi eksekusi command menggunakan `Stopwatch`.
* **Kriteria**: Jika durasi eksekusi melebihi ambang batas 500ms, catat log dengan log level `Warning` yang mencantumkan nama command dan payloadnya.

#### Level 3 (Hard):
* **Tugas**: Bangun implementasi lengkap dari `OutboxProcessorWorker` berbasis `BackgroundService`.
* **Kriteria**:
  1. Harus membuat explicit service scope.
  2. Ambil maksimal 50 outbox message yang belum diproses (`ProcessedOnUtc == null`).
  3. Deserialisasi domain event payload kembali ke tipe aslinya.
  4. Publikasikan domain event ke in-memory notification engine atau simulated broker.
  5. Perbarui status pesan menjadi diproses secara transaksional; tangani exception dan simpan stack trace error ke kolom `OutboxMessage.Error`.

---

### 14. Challenge

**Skenario**: Sistem Multi-Tenant Core Banking Settlement Platform.
* **Kondisi**:
  1. Database terpisah menggunakan isolasi Logical Isolation (Schema-per-tenant).
  2. Kebutuhan mutasi akun finansial mencapai 15.000 TPS saat jam sibuk.
  3. Menggunakan distributed ledger model di mana `Debit` dan `Credit` harus selalu seimbang dalam batas zero-sum tolerance.
* **Tuntutan**:
  * Rancang arsitektur implementasi Clean Architecture murni di mana Domain Model tidak memiliki kesadaran tentang tenant id (*Tenant Agnostic*), namun layer Application dan Infrastructure dapat merutekan koneksi database dinamis dan menaruh outbox messages pada Kafka topic terpisah per tenant secara otomatis.
  * Jelaskan bagaimana Anda merancang *Idempotency Filter* dengan zero latency hit pada round-trip database menggunakan pipeline memory-cache two-tier fallback!

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa Domain layer pada Clean Architecture tidak boleh memiliki referensi paket NuGet pihak ketiga (misal: Entity Framework Core)?
   * *Jawaban*: Agar domain logic tetap independen terhadap perubahan teknologi infrastruktur, mudah diuji secara murni via unit test tanpa mocking rumit, serta terhindar dari pergeseran arsitektur akibat dependensi framework.
2. Apa perbedaan mendasar antara *Anemic Domain Model* dan *Rich Domain Model*?
   * *Jawaban*: Anemic Model menempatkan data murni pada entity dengan public getter/setter dan logika bisnis diletakkan pada services terpisah. Rich Domain Model mengenkapsulasi data dengan private setters dan melindungi validasi invariant langsung di dalam entity itu sendiri.
3. Apa perbedaan siklus hidup antara *Domain Event* dan *Integration Event*?
   * *Jawaban*: Domain Event terjadi secara internal in-process dalam bounded context yang sama dan disinkronkan dalam database transaction yang sama. Integration Event dipublikasikan keluar context boundary melalui message bus untuk konsumsi service/sistem lain.
4. Apa kelemahan utama menggunakan Exception (`throw new Exception()`) untuk menangani logika alur bisnis (control flow)?
   * *Jawaban*: Alokasi memory overhead yang sangat tinggi karena CLR harus menangkap full StackTrace snapshot, menurunkan throughput CPU, dan membuat alur logika program sulit ditebak (*implicit control jump*).
5. Pada pola CQRS, mengapa Query read path disarankan mem-bypass Domain Entity dan Repository?
   * *Jawaban*: Query read path bersifat non-mutating (hanya baca). Memuat data mentah langsung ke DTO melalui Dapper atau EF Core NoTracking menghilangkan overhead tracking Change Tracker dan mapping domain aggregate yang tidak diperlukan, sehingga menghemat CPU dan memori.

#### B. Pertanyaan Intermediate
6. Bagaimana cara `ConvertDomainEventsToOutboxMessagesInterceptor` menjamin atomic delivery antara perubahan state entitas dan message outbox?
   * *Jawaban*: Interceptor mengeksekusi interception hook sebelum commit database (`SavingChangesAsync`), mengekstrak domain event dari aggregate, lalu menambahkannya sebagai record `OutboxMessage` ke dalam `DbContext` yang sama, sehingga perubahan entitas dan outbox message dieksekusi dalam satu transaksi ACID database lokal.
7. Kapan sebaiknya kita menggunakan `ValueTask<T>` alih-alih `Task<T>` pada Application Pipeline Behaviors?
   * *Jawaban*: Saat pipeline method berpeluang besar untuk selesai secara sinkron (misal: hasil validasi gagal langsung mengembalikan Result, atau data idempotent ditemukan di in-memory cache), sehingga runtime mengeliminasi alokasi heap untuk instansiasi object `Task`.
8. Mengapa pada transaksi Outbox di tingkat produksi kita harus menerapkan klausa `FOR UPDATE SKIP LOCKED` pada background poller worker?
   * *Jawaban*: Mencegah instance worker multi-node saling mengunci baris data (lock contention/deadlock) dan menghindari eksekusi ganda antar-pod secara bersamaan dengan membiarkan instance mengambil row berikutnya yang tidak dikunci instance lain.
9. Apa fungsi `Private Parameterless Constructor` pada entity domain yang menerapkan Rich Domain Model di EF Core?
   * *Jawaban*: EF Core membutuhkan constructor tanpa parameter untuk melakukan materialisasi data dari database relasional ke instansiasi instance class tanpa harus memicu validasi logika bisnis yang ada pada public constructor/factory.
10. Bagaimana cara mencegah *Ghost Read* atau write collision pada agregat root yang dimutasi bersamaan tanpa distributed locks?
    * *Jawaban*: Menggunakan Optimistic Concurrency Control dengan menambahkan concurrency token (seperti properti bertipe `byte[]` dengan atribut `[Timestamp]` atau konfigurasi `.IsRowVersion()`) pada EF Core aggregate mapping.

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi e-commerce Anda mengalami lonjakan transaksi *Flash Sale*. Sistem memproses 2.000 request pemesanan per detik. Database server mengalami lonjakan CPU hingga 100%, dan teridentifikasi sebagian besar query berasal dari `ChangeTracker` EF Core yang memverifikasi state entitas read-only di endpoint katalog.
    * *Pertanyaan*: Solusi refaktorisasi arsitektur Clean Architecture apa yang wajib diterapkan segera?
    * *Solusi*: Pisahkan alur Write dan Read secara tegas (CQRS). Pada use case katalog/read, hindari memanggil Repository yang mengembalikan tracked aggregate. Gunakan Dapper atau EF Core `AsNoTracking()` yang langsung memetakan query database mentah ke Flat DTO. Hindari pemanggilan Domain Layer pada alur Read murni ini.

12. **Skenario 2**: Terjadi insiden di mana sebuah event `PaymentReceived` gagal dikirim ke Kafka karena broker kehabisan disk space selama 2 jam. Namun, pesanan di database telah berstatus `Paid`.
    * *Pertanyaan*: Bagaimana Transactional Outbox Pattern menyelamatkan konsistensi sistem ini?
    * *Solusi*: Karena event disimpan di tabel outbox dalam transaksi database yang sama dengan pesanan, state pembayaran tetap aman di database. Outbox poller worker akan terus gagal mempublikasikan pesan dan mencatat retry log tanpa menghilangkan pesan. Begitu disk Kafka diperbesar dan koneksi pulih, worker secara otomatis melanjutkan publikasi event yang tertunda sesuai urutan waktu (`OccurredOnUtc`), menjamin jaminan pengiriman *At-Least-Once*.

13. **Skenario 3**: Sebuah developer membuat MediatR Request Handler yang menginjeksi `IOrderRepository` dan `IPaymentRepository`. Handler tersebut melakukan pemanggilan `orderRepository.Update(order)` kemudian memanggil `paymentRepository.Add(payment)`. Jika koneksi database putus di tengah jalan, state data menjadi corrupt (Order terupdate tapi Payment tidak tersimpan).
    * *Pertanyaan*: Pelanggaran arsitektur apa yang terjadi di sini dan bagaimana desain perbaikannya?
    * *Solusi*: Terjadi pelanggaran Transaction Boundary (Unit of Work). Domain boundary tidak boleh memiliki dependensi tersebar dengan `SaveChanges` terpisah. Perbaikan: Buat Aggregate Root tunggal yang membungkus siklus hidup kedua entitas tersebut jika berada dalam transactional invariant yang sama, atau bungkus seluruh rangkaian penyimpanan repository di bawah orchestrasi *Unit of Work* tunggal yang hanya memanggil satu kali `SaveChangesAsync` di akhir handler.

---

### 16. Summary

1. **Rich Domain Model Enforces Invariants**: Enkapsulasi penuh pada entity mencegah runtime state korup, memastikan seluruh mutasi melalui validasi eksplisit, dan mengabstraksikan domain logic terbebas dari infrastruktur data.
2. **Result Pattern Replaces Exceptions**: Menghilangkan alur eksekusi berbasis exception untuk skenario bisnis yang dapat diprediksi secara drastis menaikkan performa latency CLR dan alokasi memori.
3. **No More Dual-Write Hazard**: Mengintegrasikan Transactional Outbox Pattern via EF Core SaveChangesInterceptor menjamin persistensi data relasional dan event streaming berjalan secara atomic dalam satu transaksi ACID lokal.
4. **Clean Decoupling via CQRS**: Menghindari dogmatisme arsitektur dengan memisahkan Read path (dioptimalkan untuk performa mentah tanpa domain overhead) dan Write path (dioptimalkan untuk perlindungan invariant bisnis tingkat tinggi).