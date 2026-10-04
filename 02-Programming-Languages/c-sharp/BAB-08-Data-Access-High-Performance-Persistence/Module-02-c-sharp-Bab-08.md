# BAB 08: Data Access & High-Performance Persistence
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal Arsitektur EF Core & Dapper**: Memahami siklus hidup evaluasi LINQ expression tree, *state manager*, *identity map*, mekanisme dynamic IL emission (`DynamicMethod`) Dapper, serta pipeline jaringan ADO.NET.
- **Mengoptimalkan Pipeline Data Access**: Mengimplementasikan *compiled queries*, `DbBatch`, *streaming queries* (`IAsyncEnumerable`), zero-allocation projection, dan mitigasi *Cartesian explosion* menggunakan *split queries*.
- **Mendesain Pola Transaksional & Resiliensi Tingkat Lanjut**: Mengimplementasikan *Transactional Outbox Pattern*, kustomisasi `IExecutionStrategy` untuk *transient error handling*, mitigasi *distributed deadlocks*, dan isolasi multi-tenant (RLS vs Schema-per-tenant).
- **Mendiagnosis & Mengeliminasi Bottleneck Produksi**: Melakukan investigasi memory leak pada Dapper cache, thread-safety violation pada `DbContext`, connection starvation, dan pemborosan CPU akibat re-kompilasi query LINQ dinamis.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib memahami:
- **C# Lanjut**: `Span<T>`, `Memory<T>`, `IAsyncEnumerable<T>`, Expression Trees (`Expression<Func<T, bool>>`), Reflection & IL Emission dasar.
- **Data Access Fundamentals**: Pemahaman dasar ORM (EF Core CRUD, Migrations, Entity Configurations) dan Micro-ORM (Dapper query dasar).
- **Engine Database Relasional**: ACID Isolation Levels (Read Committed, Repeatable Read, Serializable, Snapshot Isolation), Indexes (B-Tree, GiST, Covering Indexes), Execution Plans, dan Lock Escalation.
- **Networking & Concurrency**: Socket buffers, TCP connection pool mechanics, threading model C# (`async`/`await`, `SynchronizationContext`, `TaskScheduler`).

---

### 3. Concept & Internal Architecture

Akses data berkinerja tinggi pada platform .NET modern (.NET 8/9) bergantung pada pemahaman mendalam tentang interaksi antara lapisan abstraksi tingkat tinggi (EF Core), micro-abstraksi (Dapper), wrapper driver (ADO.NET), dan protokol soket database.

```
+-------------------------------------------------------------------+
|                        Application Layer                          |
+---------------------------------+---------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+-------------------------------+               +-------------------+
|       EF Core 8/9 Engine      |               |   Dapper Engine   |
|  - LINQ Expression Tree       |               |  - SQL String Key |
|  - Relational Model Cache     |               |  - Dynamic IL Gen |
|  - Change Tracker / Snapshot  |               |  - DynamicMethod  |
|  - Query Compilation Engine   |               |    Cache (L1)     |
+---------------+---------------+               +---------+---------+
                |                                         |
                |  +--------------------------------------+
                |  |
                v  v
+-------------------------------------------------------------------+
|                     ADO.NET Provider (Npgsql/SqlData)             |
|  - DbCommand / DbBatch (Pipelined Command Transmission)           |
|  - DbConnection Pool (Physical connection multiplexing/pooling)   |
|  - DbDataReader (TDS / PostgreSQL Wire Protocol Parsing)          |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                 Kernel & Network Socket Layer                     |
|  - TCP Send/Receive Buffers (Zero-Copy Socket API)                |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                   Physical Database Server                        |
|  - Query Engine, Buffer Pool, WAL Engine, Lock Manager            |
+-------------------------------------------------------------------+
```

#### A. Arsitektur Internal EF Core Change Tracker
Change Tracker di EF Core beroperasi sebagai implementasi ganda dari pola *Identity Map* dan *Unit of Work*.
1. **Identity Map**: Disimpan dalam `IdentityMap<TKey>` internal berbasis hash-table. Memastikan bahwa dalam satu scope `DbContext`, satu baris baris tabel fisik hanya direpresentasikan oleh tepat satu *reference instance* objek CLR.
2. **Snapshot vs Proxy Tracking**:
   - Secara *default*, EF Core menggunakan **Snapshot Tracking**. Saat entitas dimuat dari database via query tracking, EF Core membuat salinan mendalam (*shadow clone*) dari nilai-nilai properti entitas tersebut ke dalam internal array `StateManager`.
   - Ketika `DetectChanges()` dipanggil (baik manual maupun otomatis sebelum `SaveChanges()`), EF Core mengiterasi setiap entitas terdaftar, membandingkan nilai properti saat ini dengan nilai pada *snapshot array*. Kompleksitas waktu operasi ini adalah $\mathcal{O}(N \times M)$ di mana $N$ adalah jumlah entitas ter-track dan $M$ adalah jumlah properti per entitas.
   - **Notification Tracking** (menggunakan `INotifyPropertyChanged`) mengeliminasi proses *snapshot comparison*, langsung menandai status `Modified` saat setter properti dipanggil.

#### B. Pipeline Kompilasi Query EF Core
Pipeline eksekusi LINQ to Entities:
1. **Query Parsing**: Mengurai `IQueryable` ke dalam AST (Abstract Syntax Tree).
2. **Query Model Extraction**: Mengidentifikasi parameter, sub-queries, dan projections.
3. **Relational Translation**: Menerjemahkan node LINQ ke Relational AST khusus database provider.
4. **Shaped Query Compilation**: Membangun delegasi CLR (`Func<QueryContext, DbDataReader, T>`) untuk menghidrasi baris tabular menjadi objek graf.
5. **Query Cache**: Menggunakan relational query cache key untuk menghindari overhead parsing pada eksekusi berikutnya.

#### C. Arsitektur Internal Dapper (Dynamic Method Generation)
Dapper bekerja hampir menyamai kecepatan ADO.NET murni karena menghindari *reflection overhead* saat runtime:
1. **Cache Lookup**: Dapper menerima string SQL dan tipe parameter, lalu membuat hash cache key.
2. **IL Emission**: Pada panggilan pertama untuk query tertentu, Dapper menggunakan `System.Reflection.Emit.DynamicMethod` untuk menghasilkan kode CIL (Common Intermediate Language) secara *in-memory*.
3. **Data Reader Hydration**: CIL yang di-generate membaca langsung dari `DbDataReader.GetInt32(ordinal)`, `DbDataReader.GetString(ordinal)`, dan menulis langsung ke field/properti objek target melalui instruksi `OpCodes.Stfld` atau `OpCodes.Callvirt`.
4. **Cache Storage**: Delegasi yang telah dikompilasi disimpan dalam internal concurrent cache (`ConcurrentDictionary<TypeHandlerCacheKey, Func<IDataReader, object>>`).

---

### 4. Why & What

| Pendekatan / Fitur | What (Apa itu?) | Why (Mengapa Digunakan?) |
| :--- | :--- | :--- |
| **Compiled Queries** (`EF.CompileAsyncQuery`) | Mekanisme *pre-compilation* LINQ Expression Tree menjadi delegasi CLR statis yang dapat dipanggil langsung. | Menghilangkan overhead parsing Expression Tree dan perakitan SQL string secara berulang pada *hot path* (menghemat 30%-60% alokasi CPU per query). |
| **DbBatch (ADO.NET)** | API pengiriman multi-perintah SQL ke database server dalam satu *network round-trip*. | Menghindari *latency amplification* dari eksekusi berulang ($N$ round-trips dieliminasi menjadi 1 round-trip ke DB socket). |
| **Split Queries** (`AsSplitQuery`) | Strategi pemisahan 1 query LINQ multi-JOIN menjadi $N$ query terpisah yang dieksekusi secara terkoordinasi. | Mencegah **Cartesian Explosion** (duplikasi data baris akibat `JOIN` pada relasi 1-to-Many) yang membebani memori dan bandwidth jaringan. |
| **ExecuteUpdate / Delete** (Bulk API) | Operasi langsung ke database tanpa memuat entitas ke memori dan tanpa Change Tracker. | Mengurangi alokasi memori ke level nol untuk mutasi masif; mengeksekusi langsung SQL `UPDATE`/`DELETE` di engine database. |
| **Connection Pooling & DbContext Pooling** | Penggunaan kembali objek instance `DbContext` dan koneksi fisik soket database via pool internal. | Alokasi `DbContext` melibatkan banyak alokasi objek internal (`StateManager`, `ChangeTracker`, dependensi internal). Pooling memotong beban GC generasi 0 secara dramatis. |

---

### 5. How (Workflow Detail)

Berikut adalah workflow eksekusi data access tingkat tinggi untuk sebuah *batch write* yang melibatkan kustomisasi interceptor, execution strategy, dan ADO.NET pipeline:

```
[Application Request]
       |
       v
1. [Execution Strategy (Retry Loop)] 
   Begin Execution with Transient Fault Handler
       |
       v
2. [IDbCommandInterceptor / SaveChangesInterceptor]
   Intercept: Modifikasi Shadow Properties (Audit Trail, TenantId, Timestamps)
       |
       v
3. [DbContextPool / DbConnection]
   Lease Connection dari Pool -> Buka Soket (jika belum aktif)
       |
       v
4. [Transaction Coordinator]
   Buka Transaksi Database (Isolasi: Read Committed / Serializable)
       |
       v
5. [ADO.NET DbBatch Execution]
   Pack multiple statements into a single network packet buffer
       |
       v
6. [Database Engine Execution]
   Parse -> Optimize -> Execute -> WAL Flush -> Release Locks
       |
       v
7. [Hydration Pipeline / Outbox Event Dispatch]
   Pipelined Read -> Commit Transaction -> Dispatch In-Memory Domain Events
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (EF Core vs Dapper vs ADO.NET)

- **EF Core (Tracking)**: Penumpang VIP dengan pemandu pribadi, pelacak bagasi GPS, check-in otomatis, inspeksi paspor komprehensif, dan pengawalan sampai kursi pesawat. Sangat aman dan terstruktur, namun memerlukan staf yang sangat banyak (overhead CPU/Memori tinggi).
- **Dapper**: Pelari maraton tanpa bagasi yang memiliki tiket elektronik langsung di smartphone, melewati *fast-track gate* langsung ke pintu kabin. Hanya melakukan hal minimal untuk masuk ke pesawat secepat mungkin.
- **Cartesian Explosion Diagram**:

```
Model Relasional: 1 Customer memiliki 10 Orders, masing-masing Order memiliki 10 Items.

QUERY DENGAN SINGLE QUERY (AsSingleQuery - Default):
SELECT * FROM Customers 
JOIN Orders ON ... 
JOIN OrderItems ON ...

HASIL NETWORK STREAM:
Customer data diduplikasi: 1 * 10 * 10 = 100 KALI!
+---------------+---------------+---------------+
| Customer Data |  Order Data   |   Item Data   |
| (Duplikasi)   |  (Duplikasi)  |  (Unik)       |
+---------------+---------------+---------------+
| John Doe      | Order #1      | Item #101     |
| John Doe      | Order #1      | Item #102     |
| ...           | ...           | ...           |
| John Doe      | Order #10     | Item #200     |  -> Total 100 baris dikirim via TCP!
+---------------+---------------+---------------+

QUERY DENGAN SPLIT QUERY (AsSplitQuery):
Query 1: SELECT * FROM Customers WHERE Id = @Id;                 -> 1 baris
Query 2: SELECT * FROM Orders WHERE CustomerId = @Id;            -> 10 baris
Query 3: SELECT * FROM OrderItems WHERE OrderId IN (...);        -> 100 baris
Total network payload: 111 baris bersih tanpa data string/blob berulang!
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Compiled Query dengan Zero-Allocation Projection

```csharp
using System.Diagnostics.CodeAnalysis;
using Microsoft.EntityFrameworkCore;

namespace Enterprise.DataAccess.Samples;

public sealed record CustomerSummaryDto(Guid Id, string FullName, decimal TotalBalance);

public sealed class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Order> Orders => Set<Order>();

    // Thread-safe Compiled Query delegate
    public static readonly Func<AppDbContext, Guid, IAsyncEnumerable<CustomerSummaryDto>> GetCustomerSummariesByTenant =
        EF.CompileAsyncQuery((AppDbContext context, Guid tenantId) =>
            context.Customers
                .AsNoTracking()
                .Where(c => c.TenantId == tenantId && c.IsActive)
                .Select(c => new CustomerSummaryDto(
                    c.Id,
                    c.FirstName + " " + c.LastName,
                    c.Orders.Sum(o => (decimal?)o.TotalAmount) ?? 0m
                )));
}

public sealed class Customer
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public required string FirstName { get; set; }
    public required string LastName { get; set; }
    public bool IsActive { get; set; }
    public List<Order> Orders { get; set; } = [];
}

public sealed class Order
{
    public Guid Id { get; set; }
    public Guid CustomerId { get; set; }
    public decimal TotalAmount { get; set; }
}
```

#### B. Practical Example: Hybrid Production-Grade Persistence Architecture (EF Core 9 + Dapper + DbBatch + Interceptors)

Implementasi pola *Outbox Writer* yang menggunakan EF Core untuk domain modeling, Interceptor untuk automatic auditing, dan fallback ke `DbBatch` untuk *high-throughput bulk flushing*.

```csharp
using System.Data;
using System.Data.Common;
using Dapper;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Logging;

namespace Enterprise.DataAccess.Production;

// --- Domain Models ---
public abstract class AggregateRoot
{
    private readonly List<object> _domainEvents = [];
    public IReadOnlyCollection<object> DomainEvents => _domainEvents.AsReadOnly();

    public void AddDomainEvent(object @event) => _domainEvents.Add(@event);
    public void ClearDomainEvents() => _domainEvents.Clear();
}

public sealed class Account : AggregateRoot
{
    public Guid Id { get; private set; }
    public Guid TenantId { get; private set; }
    public string AccountNumber { get; private set; } = null!;
    public decimal Balance { get; private set; }
    public uint RowVersion { get; private set; } // Optimistic Locking

    private Account() { } // EF Core reflection constructor

    public static Account Create(Guid tenantId, string accountNumber, decimal initialBalance)
    {
        var account = new Account
        {
            Id = Guid.NewGuid(),
            TenantId = tenantId,
            AccountNumber = accountNumber,
            Balance = initialBalance
        };

        account.AddDomainEvent(new AccountCreatedEvent(account.Id, tenantId, initialBalance));
        return account;
    }

    public void Debit(decimal amount)
    {
        if (amount <= 0) throw new ArgumentException("Amount must be positive", nameof(amount));
        if (Balance < amount) throw new InvalidOperationException("Insufficient funds.");

        Balance -= amount;
        AddDomainEvent(new AccountDebitedEvent(Id, amount, Balance));
    }
}

public sealed record AccountCreatedEvent(Guid AccountId, Guid TenantId, decimal Balance);
public sealed record AccountDebitedEvent(Guid AccountId, decimal Amount, decimal NewBalance);

public sealed record OutboxMessage(Guid Id, string EventType, string Payload, DateTime OccurredOnUtc);

// --- DbContext with Pooling and Interceptors ---
public sealed class BankingDbContext : DbContext
{
    public BankingDbContext(DbContextOptions<BankingDbContext> options) : base(options) { }

    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<OutboxMessage> OutboxMessages => Set<OutboxMessage>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Account>(b =>
        {
            b.HasKey(a => a.Id);
            b.Property(a => a.AccountNumber).HasMaxLength(32).IsRequired();
            b.Property(a => a.Balance).HasPrecision(18, 4);
            b.Property(a => a.RowVersion).IsRowVersion(); // Concurrency Token
            b.HasIndex(a => new { a.TenantId, a.AccountNumber }).IsUnique();
        });

        modelBuilder.Entity<OutboxMessage>(b =>
        {
            b.HasKey(m => m.Id);
            b.Property(m => m.EventType).HasMaxLength(128).IsRequired();
            b.Property(m => m.Payload).HasColumnType("jsonb").IsRequired();
        });
    }
}

// --- High-Performance Custom Interceptor for Auditing ---
public sealed class AuditAndOutboxSaveChangesInterceptor : SaveChangesInterceptor
{
    public override async ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        var context = eventData.Context;
        if (context is null) return await base.SavingChangesAsync(eventData, result, cancellationToken);

        var aggregates = context.ChangeTracker
            .Entries<AggregateRoot>()
            .Where(e => e.Entity.DomainEvents.Any())
            .Select(e => e.Entity)
            .ToList();

        if (aggregates.Count == 0)
            return await base.SavingChangesAsync(eventData, result, cancellationToken);

        var outboxEntries = new List<OutboxMessage>();

        foreach (var aggregate in aggregates)
        {
            foreach (var domainEvent in aggregate.DomainEvents)
            {
                var outbox = new OutboxMessage(
                    Guid.NewGuid(),
                    domainEvent.GetType().AssemblyQualifiedName!,
                    System.Text.Json.JsonSerializer.Serialize(domainEvent),
                    DateTime.UtcNow
                );
                outboxEntries.Add(outbox);
            }
            aggregate.ClearDomainEvents();
        }

        await context.Set<OutboxMessage>().AddRangeAsync(outboxEntries, cancellationToken);
        return await base.SavingChangesAsync(eventData, result, cancellationToken);
    }
}

// --- Hybrid Production Repository (EF Core Read/Write + DbBatch Bulk Pipeline) ---
public sealed class AccountRepository
{
    private readonly BankingDbContext _context;
    private readonly ILogger<AccountRepository> _logger;

    public AccountRepository(BankingDbContext context, ILogger<AccountRepository> logger)
    {
        _context = context;
        _logger = logger;
    }

    public async Task<Account?> GetByIdAsync(Guid id, CancellationToken ct)
    {
        return await _context.Accounts
            .AsTracking()
            .SingleOrDefaultAsync(a => a.Id == id, ct);
    }

    // High performance bulk debiting bypassing EF ChangeTracker via DbBatch (Native ADO.NET)
    public async Task BulkDebitDirectAsync(IReadOnlyList<(Guid AccountId, decimal Amount)> debits, CancellationToken ct)
    {
        if (debits.Count == 0) return;

        var connection = _context.Database.GetDbConnection();
        if (connection.State != ConnectionState.Open)
        {
            await connection.OpenAsync(ct);
        }

        await using var batch = connection.CreateBatch();

        foreach (var (accountId, amount) in debits)
        {
            var batchCommand = batch.CreateBatchCommand();
            batchCommand.CommandText = """
                UPDATE "Accounts" 
                SET "Balance" = "Balance" - @Amount
                WHERE "Id" = @Id AND "Balance" >= @Amount;
            """;

            var paramId = batchCommand.CreateParameter();
            paramId.ParameterName = "@Id";
            paramId.Value = accountId;
            paramId.DbType = DbType.Guid;
            batchCommand.Parameters.Add(paramId);

            var paramAmount = batchCommand.CreateParameter();
            paramAmount.ParameterName = "@Amount";
            paramAmount.Value = amount;
            paramAmount.DbType = DbType.Decimal;
            batchCommand.Parameters.Add(paramAmount);

            batch.BatchCommands.Add(batchCommand);
        }

        // Single network packet flight execution
        var affectedRows = await batch.ExecuteNonQueryAsync(ct);
        _logger.LogInformation("Successfully executed bulk batch debit for {Count} accounts. Rows modified: {Rows}", debits.Count, affectedRows);
    }

    public async Task SaveChangesWithResilienceAsync(CancellationToken ct)
    {
        var strategy = _context.Database.CreateExecutionStrategy();
        await strategy.ExecuteAsync(async () =>
        {
            await using var tx = await _context.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, ct);
            try
            {
                await _context.SaveChangesAsync(ct);
                await tx.CommitAsync(ct);
            }
            catch (DbUpdateConcurrencyException ex)
            {
                _logger.LogError(ex, "Optimistic concurrency conflict occurred.");
                throw;
            }
            catch (Exception ex)
            {
                await tx.RollbackAsync(ct);
                _logger.LogError(ex, "Transaction aborted. Rollback completed.");
                throw;
            }
        });
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Financial Ledger (25.000 TPS)
- **Konteks**: Sebuah payment engine memproses lonjakan transaksi hingga 25.000 request/detik pada hari gajian nasional.
- **Masalah Produksi**:
  1. *Connection Pool Exhaustion*: Database menolak koneksi (`NpgsqlException: The connection pool has been exhausted`).
  2. *High CPU Spikes*: CPU database server melonjak hingga 99% akibat evaluasi dynamic query ad-hoc tanpa caching plan.
  3. *Deadlocks*: Transaksi transfer antar-rekening memicu deadlock massal saat Account A mendebit Account B, bersamaan dengan Account B mendebit Account A.
- **Solusi yang Diterapkan**:
  1. **DbContext Pooling**: Mengaktifkan `AddDbContextPool<BankingDbContext>(options, poolSize: 1024)` pada Program.cs, menurunkan frekuensi garbage collection (Gen 0 GC) sebesar 70% dan menekan overhead alokasi instansiasi.
  2. **Deadlock Ordering Protocol**: Menegakkan *Lock Order Consistency*. Dalam setiap transaksi transfer multi-akun, akun selalu diakses dan dikunci berdasarkan urutan leksikografis ID entitas (`ORDER BY Id ASC`).
  3. **Pipelining dengan PgBouncer & DbBatch**:
     - Memasang PgBouncer di depan Postgres dengan mode *Transaction Pooling*.
     - Mengubah dispatch data log transaksi audit dari operasi `INSERT` individual per-request menjadi micro-batching ADO.NET `DbBatch` berukuran 100 entri per round-trip soket.
  4. **Bulk Mutation API**: Migrasi mutasi massal dari looping `context.Update()` ke `ExecuteUpdateAsync`:
     ```csharp
     await context.Accounts
         .Where(a => a.TenantId == tenantId && a.IsActive)
         .ExecuteUpdateAsync(s => s.SetProperty(a => a.LastAuditUtc, DateTime.UtcNow), ct);
     ```
- **Hasil Metrik**:
  - Latensi P99 terpangkas dari 1.850ms menjadi 42ms.
  - Alokasi memori berkurang dari 4.2 GB/menit menjadi 450 MB/menit.
  - Kejadian deadlock turun menjadi 0 per hari.

---

### 9. Trade-offs

```
                       LATENCY vs ABSTRACTION LEVEL
 Low Latency                                                    High Abstraction
 (Zero Allocation)                                              (High Productivity)
      |                                                                 |
   Raw ADO.NET ----------> Dapper --------------> EF Core -------------> EF Core
    (DbBatch)           (Micro-ORM)            (NoTracking)           (Full Tracking)
      |                      |                      |                       |
      v                      v                      v                       v
Manual Mapping        Auto IL Map            LINQ AST Parse          Change Detection
No Change Tracker     No Change Tracker      No State Tracker        In-Memory Snapshot
Max Throughput        High Speed             Complex Projection      Rich Domain Model
High Boilerplate      Medium Boilerplate     Zero Boilerplate        Heavy Memory
```

| Parameter | Raw ADO.NET (`DbBatch`) | Dapper | EF Core (`AsNoTracking`) | EF Core (`ChangeTracking`) |
| :--- | :--- | :--- | :--- | :--- |
| **Alokasi Memori (Gen 0/1/2)** | Sangat Rendah (Minimal) | Rendah (Hanya objek POCO) | Sedang (Object graph + query AST) | Sangat Tinggi (Snapshot clone array) |
| **Throughput (Ops/sec)** | Ekstrem (~95.000) | Sangat Tinggi (~90.000) | Tinggi (~60.000) | Sedang (~20.000) |
| **Productivity / DX** | Rendah (Raw string & index) | Tinggi (SQL murni + automap) | Sangat Tinggi (Type-safe LINQ) | Maksimal (Unit of Work otomatis) |
| **Kompleksitas Query Terdistribusi**| Sulit dikelola | Terkelola dengan baik | Sangat mudah via navigasi | Sangat mudah via navigasi |
| **Dukungan Batching Otomatis** | Manual via API `DbBatch` | Iteratif / Multi-SQL Text | Otomatis via `ExecuteUpdate` | Otomatis via `SaveChanges()` |

---

### 10. Common Mistakes & Troubleshooting

#### A. Memory Leak: Dapper Cache Key String Concatenation
*Kesalahan*: Menggabungkan parameter langsung ke dalam string SQL saat memanggil Dapper.
```csharp
// SANGAT BERBAHAYA: Mengisi cache Dapper sampai OutOfMemoryException (OOM)
for (int i = 0; i < 100000; i++)
{
    var sql = $"SELECT * FROM Users WHERE Id = '{userId}'"; // SQL string unik per iterasi!
    var user = await connection.QueryFirstOrDefaultAsync<User>(sql);
}
```
*Mengapa Terjadi*: Dapper menyimpan delegasi IL emitter di dalam `ConcurrentDictionary` statis dengan key berupa string SQL persis. String SQL dinamis menghasilkan entri cache baru tak terhingga (*memory leak* pada non-GC memory).
*Solusi*: Selalu gunakan parameter query:
```csharp
var sql = "SELECT * FROM Users WHERE Id = @Id";
var user = await connection.QueryFirstOrDefaultAsync<User>(sql, new { Id = userId });
```

#### B. Thread Safety Violation pada DbContext
*Kesalahan*: Membagikan instance `DbContext` ke beberapa thread melalui `Task.WhenAll`.
```csharp
// RUNTIME CRASH: A second operation was started on this context before a previous operation completed.
var task1 = context.Users.ToListAsync();
var task2 = context.Orders.ToListAsync();
await Task.WhenAll(task1, task2);
```
*Solusi*: `DbContext` adalah non-thread-safe. Gunakan `IDbContextFactory<AppDbContext>` untuk menghasilkan instance independen per task parallel:
```csharp
await using var context1 = contextFactory.CreateDbContext();
await using var context2 = contextFactory.CreateDbContext();

var task1 = context1.Users.ToListAsync();
var task2 = context2.Orders.ToListAsync();
await Task.WhenAll(task1, task2);
```

#### C. Connection Leak Akibat Task Cancellation Tanpa Dispose
*Kesalahan*: Mengabaikan handling pembatalan token pada operasi streaming.
*Solusi*: Pastikan `DbDataReader` atau `IAsyncEnumerable` selalu dibungkus dalam `await using` agar koneksi underlying segera dikembalikan ke connection pool saat `TaskCanceledException` dilempar.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan DbContext Pooling**: Konfigurasikan `AddDbContextPool<TContext>()` pada container DI kecuali context menggunakan dependensi transient per-request stateful.
- [ ] **Gunakan AsNoTracking Secara Default**: Jadikan `.UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)` sebagai baseline global, aktifkan tracking hanya ketika mutasi entitas dibutuhkan secara eksplisit.
- [ ] **Pilih Split Query untuk Deep Graph**: Terapkan `.AsSplitQuery()` saat melakukan querying relasi `Include()` lebih dari satu koleksi (1-to-N-to-M).
- [ ] **Eliminasi Single Round-trip Bulk**: Ganti mutasi per-entitas loop dengan `ExecuteUpdateAsync` atau `ExecuteDeleteAsync`.
- [ ] **Explicit Command Timeout Limits**: Konfigurasikan batas timeout eksplisit di connection string dan interceptor; jangan biarkan fallback ke default infinity/30s tanpa audit.
- [ ] **Index Foreign Key & Dynamic Filters**: Pastikan properti yang digunakan dalam Global Query Filters (seperti `TenantId`, `IsDeleted`) memiliki covering compound index di database engine.
- [ ] **Gunakan TagWith untuk Tracing**: Berikan tag deskriptif pada query kompleks untuk kemudahan profiling di database engine:
  ```csharp
  var data = await context.Accounts
      .TagWith("AccountRepository.GetActiveVipAccounts:Line52")
      .Where(...)
      .ToListAsync(ct);
  ```

---

### 12. Hands-on Practice

Buat struktur project berikut di direktori `hands-on/m02/`:

```
hands-on/m02/
├── DataAccessDeepDive.sln
├── src/
│   └── PerformancePersistence/
│       ├── Domain/
│       │   └── Entities.cs
│       ├── Infrastructure/
│       │   ├── AppDbContext.cs
│       │   ├── Interceptors.cs
│       │   └── Repositories.cs
│       └── Program.cs
└── tests/
    └── PersistenceBenchmarks/
        ├── Benchmarks.cs
        └── PersistenceBenchmarks.csproj
```

#### Langkah Praktikum:
1. **Setup Project**:
   ```bash
   mkdir -p hands-on/m02 && cd hands-on/m02
   dotnet new sln -n DataAccessDeepDive
   dotnet new console -n PerformancePersistence -o src/PerformancePersistence
   dotnet new console -n PersistenceBenchmarks -o tests/PersistenceBenchmarks
   dotnet sln add src/PerformancePersistence tests/PersistenceBenchmarks
   ```
2. **Install Dependensi**:
   ```bash
   cd src/PerformancePersistence
   dotnet add package Microsoft.EntityFrameworkCore.SqlServer
   dotnet add package Dapper
   cd ../../tests/PersistenceBenchmarks
   dotnet add package BenchmarkDotNet
   dotnet add reference ../../src/PerformancePersistence/PerformancePersistence.csproj
   ```
3. **Eksekusi Benchmark**:
   Implementasikan perbandingan antara:
   - EF Core Tracking Fetch vs NoTracking Fetch.
   - EF Core Loop Updates vs `ExecuteUpdateAsync`.
   - Dapper Query vs EF Core Compiled Query.
   Jalankan dengan konfigurasi rilis:
   ```bash
   dotnet run -c Release --project tests/PersistenceBenchmarks
   ```

---

### 13. Exercise

#### Level: Easy
Implementasikan custom `ValueConverter` di EF Core yang secara otomatis melakukan kompresi string JSON ke format gzip binary (`byte[]`) saat disimpan ke database dan mendekompresinya kembali saat dibaca.

#### Level: Medium
Buat method ekstensi Dapper `QueryMultipleSplitStreamAsync` yang membaca data *one-to-many* (Parent-Child) menggunakan `QueryMultipleAsync` dan mengembalikan `IAsyncEnumerable<TParent>` secara streaming murni tanpa memuat seluruh dataset anak ke dalam memori RAM terlebih dahulu.

#### Level: Hard
Rancang dan implementasikan kustom `IExecutionStrategy` di EF Core yang:
1. Mengenali PostgreSQL error code `40001` (*serialization_failure*) dan `40P01` (*deadlock_detected*).
2. Melakukan *exponential backoff* dengan *full jitter*.
3. Mengembalikan status metrics ke pipeline OpenTelemetry via `ActivitySource`.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Database Architect untuk platform SaaS E-Commerce Multi-Tenant.
**Tantangan**:
Rancang sistem akses data enterprise dengan kriteria ketat berikut:
1. **Model Isolasi Hibrida**:
   - Tenant Tier Enterprise mendapatkan skema database terisolasi (`tenant_schema_xxx`).
   - Tenant Tier Standard berbagi skema publik menggunakan Postgres Row-Level Security (RLS) via `TenantId`.
2. **Zero-Downtime Schema Evolution**:
   - Koneksi EF Core harus secara dinamis mengarahkan migrasi ke skema yang tepat saat runtime berdasarkan `TenantContext`.
3. **Resilience & Outbox Requirement**:
   - Implementasikan *Transactional Outbox Engine* menggunakan ADO.NET `DbBatch` yang menjamin pesan keluar (outbox events) tersimpan atomik dengan operasi data, dengan garansi penulisan di bawah 15 milidetik pada beban 10.000 batch/detik.
4. **Constraint Khusus**: Dilarang menggunakan transaksi terdistribusi (tidak boleh MSDTC / Two-Phase Commit). Seluruh operasi harus diselesaikan melalui strategi kompensasi lokal dan connection pooling multiplexing.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa fungsi utama dari internal array snapshot pada `StateManager` EF Core?
   - A. Menyimpan koneksi database yang sedang idle.
   - B. Membandingkan nilai properti asli entitas guna mendeteksi mutasi saat `DetectChanges()` dipanggil.
   - C. Menyimpan histori rollback transaksi lokal.
   - D. Menjadi cache permanen lintas request HTTP.

2. Mengapa Dapper jauh lebih efisien dibandingkan serialisasi/deserialisasi reflection standar?
   - A. Karena Dapper melewati lapisan socket TCP.
   - B. Dapper menggunakan CIL generation via `DynamicMethod` untuk menghasilkan delegate akses data langsung ke memory offset.
   - C. Dapper mengompilasi ulang database engine menjadi assembly C#.
   - D. Dapper hanya mendukung tipe data numerik.

3. Apa efek samping dari penggunaan `.AsSingleQuery()` pada relasi 1-ke-Banyak yang kompleks?
   - A. Memory leak pada dynamic IL cache.
   - B. Cartesian Explosion yang menghasilkan payload data duplikat secara masif pada transfer socket.
   - C. Menutup koneksi database secara prematur.
   - D. Memaksa database melakukan lock eskalasi ke level tabel secara instan.

4. Operasi mana yang **tidak** memanfaatkan Change Tracker EF Core?
   - A. `context.Add(entity)`
   - B. `context.Remove(entity)`
   - C. `context.Users.Where(u => u.Id == id).ExecuteDeleteAsync()`
   - D. `context.Entry(entity).State = EntityState.Modified`

5. Apa tujuan utama dari `AddDbContextPool` pada ASP.NET Core?
   - A. Mencegah developer mengeksekusi raw SQL.
   - B. Mendaur ulang instance `DbContext` untuk menurunkan alokasi memori GC Gen 0 pada aplikasi throughput tinggi.
   - C. Mengizinkan pemanggilan satu instance `DbContext` oleh multi-thread secara simultan.
   - D. Membuka 100 koneksi fisik database secara persisten di background.

---

#### Bagian 2: Intermediate (Analisis Singkat)

6. Jelaskan risiko keamanan dan arsitektural dari penggunaan string interpolasi langsung dalam method `FromSqlRaw` di EF Core, dan bagaimana `FromSqlInterpolated` memitigasinya secara internal!
7. Dalam kondisi arsitektural apa penggunaan `.AsSplitQuery()` justru memberikan performa yang **lebih buruk** dibandingkan `.AsSingleQuery()`?
8. Mengapa `IExecutionStrategy` (retry policy) EF Core tidak dapat digunakan bersamaan dengan pemanggilan eksplisit `context.Database.BeginTransaction()` tanpa penanganan khusus?
9. Apa perbedaan mekanis antara `DbCommand.ExecuteNonQuery()` yang dipanggil secara berulang dalam loop vs `DbBatch.ExecuteNonQuery()` di ADO.NET level soket jaringan?
10. Bagaimana cara mendiagnosis bahwa aplikasi Anda mengalami connection pool starvation melalui metrik runtime .NET?

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1 (Memory Out of Memory Crash)**:
    Aplikasi background worker konsumsi pesan Kafka memproses data pengguna menggunakan EF Core dengan code berikut:
    ```csharp
    while (await reader.WaitToReadAsync())
    {
        var msg = await reader.ReadAsync();
        var user = await _context.Users.FirstOrDefaultAsync(u => u.Id == msg.UserId);
        user.UpdateStatus(msg.Status);
        await _context.SaveChangesAsync();
    }
    ```
    Setelah 6 jam, memori worker membengkak dari 150MB menjadi 8GB hingga akhirnya di-kill oleh Linux OOM Killer. Analisis akar penyebab masalah (*root cause*) dan berikan koreksi kode produksinya!

12. **Skenario 2 (Deadlock Transaksional)**:
    Dua microservice secara berkala memutasi data inventory gudang secara bersamaan. Service A mengurangi Product 1 lalu Product 2 dalam transaksi Read Committed. Service B mengurangi Product 2 lalu Product 1 dalam transaksi Read Committed. Deadlock graph menunjukkan kedua thread saling menunggu lock X (Exclusive). Bagaimana Anda menyusun ulang logika persistensi C# untuk mengeliminasi kondisi balapan (*race condition*) ini secara deterministik?

13. **Skenario 3 (Slow Query & High Allocation Investigation)**:
    Profiler menunjukkan sebuah endpoint analitik membaca 10.000 data transaksi dan memakan alokasi 85 MB RAM per eksekusi. Query menggunakan EF Core:
    ```csharp
    var results = await _context.Transactions
        .Include(t => t.Merchant)
        .Include(t => t.LedgerEntries)
        .ToListAsync();
    ```
    Anda ditugaskan merombak query tersebut dengan batas alokasi memori maksimal 2 MB tanpa memutus relasi data yang dibutuhkan oleh presentation layer. Jelaskan langkah optimasi komprehensif Anda!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **B** — Snapshot array menduplikasi nilai properti awal saat entitas di-load, digunakan sebagai baseline diferensial saat `DetectChanges()` dijalankan.
2. **B** — Dapper men-generate CIL via dynamic assembly yang langsung mengakses ordinals `DbDataReader`, memotong seluruh overhead dynamic reflection runtime.
3. **B** — Cartesian Explosion terjadi karena SQL engine menggandakan baris kolom utama untuk setiap baris relasi anak yang di-JOIN.
4. **C** — `ExecuteDeleteAsync` dan `ExecuteUpdateAsync` mengeksekusi direct SQL commands ke engine database tanpa memuat data ke memori ataupun mendaftarkannya ke Change Tracker.
5. **B** — Mengurangi alokasi heap Gen 0 dengan mereset dan menggunakan kembali instance `DbContext` internal.

#### Bagian 2: Intermediate
6. **Jawaban**: `FromSqlRaw` memperlakukan string mentah apa adanya. Jika menggunakan interpolasi `$"SELECT * FROM Tbl WHERE Id = '{id}'"`, string dievaluasi terlebih dahulu oleh runtime C# sebelum masuk ke EF, memicu kerentanan SQL Injection. `FromSqlInterpolated` menerima `FormattableString`, di mana compiler C# mengekstraksi nilai variabel secara terpisah menjadi parameter ADO.NET (`@p0`, `@p1`), menjamin parameterisasi aman.
7. **Jawaban**: Ketika: (a) Database latency round-trip tinggi dan dataset kecil, sehingga biaya membuka $N$ query terpisah lebih mahal dibanding biaya transfer data duplikat; (b) Tidak ada transaksi terisolasi yang membungkus split query, memicu risiko *inconsistent reads* (data anak berubah di antara pembacaan query 1 dan query 2).
8. **Jawaban**: Strategi retry `IExecutionStrategy` membungkus operasi dalam loop. Jika transaksi manual dimulai di luar execution strategy, kegagalan di tengah jalan akan membuat state transaksi lokal tidak konsisten atau throw error karena transaksi lama belum di-rollback sebelum iterasi retry baru dimulai. Solusinya adalah membungkus seluruh blok transaksi di dalam `strategy.ExecuteAsync(async () => { ... })`.
9. **Jawaban**: Panggilan berulang `DbCommand` mengeksekusi proses: Kirim paket -> Tunggu respon network -> Kirim paket berikutnya ($N$ network round trips). Sebaliknya, `DbBatch` mengemas semua command text dan parameter ke dalam buffer soket tunggal, mengirimkannya sekaligus ke server, memotong latensi jaringan drastis ke level satu round-trip.
10. **Jawaban**: Melalui monitoring EventCounters dari provider database (misal: `Npgsql` atau `Microsoft.Data.SqlClient`), perhatikan lonjakan metrik:
    - `Active Connections` mendekati `Max Pool Size`.
    - `Connection Wait Time` atau `Queued Commands` melonjak tajam dari milidetik menjadi hitungan detik.
    - Munculnya exception `TimeoutException: Timeout expired. The timeout elapsed prior to obtaining a connection from the pool`.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Akar Masalah**:
    Objek `_context` bertindak sebagai *long-lived context* (Singleton/Scoped di luar loop). Setiap kali `FirstOrDefaultAsync` dieksekusi, entitas `User` didaftarkan ke `ChangeTracker`. Karena context tidak pernah di-dispose, puluhan ribu entitas menumpuk di `StateManager`, mempertahankan referensinya di Heap RAM dan mencegah Garbage Collector membersihkannya.

    **Solusi Kode Produksi**:
    Gunakan `IDbContextFactory` untuk membuat context per-batch atau manfaatkan `ExecuteUpdateAsync` tanpa tracking:
    ```csharp
    while (await reader.WaitToReadAsync())
    {
        var msg = await reader.ReadAsync();
        
        // Pendekatan Zero-Allocation / Zero-Tracking
        await _context.Users
            .Where(u => u.Id == msg.UserId)
            .ExecuteUpdateAsync(s => s.SetProperty(u => u.Status, msg.Status));
    }
    ```
    Atau jika logika bisnis domain memerlukan instansiasi entity:
    ```csharp
    await using (var scope = _serviceScopeFactory.CreateAsyncScope())
    {
        var context = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var user = await context.Users.FindAsync(msg.UserId);
        user.UpdateStatus(msg.Status);
        await context.SaveChangesAsync();
    }
    ```

12. **Analisis Deadlock & Solusi**:
    Akar masalah adalah *Inconsistent Resource Lock Acquisition Order* (Service A mengunci Record 1 lalu Record 2; Service B mengunci Record 2 lalu Record 1).
    **Solusi**:
    Wajibkan semua operasi mutasi batch mengurutkan kunci data (*deterministic lock ordering*) sebelum melakukan akuisisi lock database:
    ```csharp
    public async Task TransferInventoryAsync(Guid itemA, Guid itemB, int qty)
    {
        // Deterministic Lock Ordering
        var firstId = itemA.CompareTo(itemB) < 0 ? itemA : itemB;
        var secondId = itemA.CompareTo(itemB) < 0 ? itemB : itemA;

        await using var tx = await _context.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted);
        
        // Lock selalu diambil dalam urutan konsisten di semua service
        var item1 = await _context.Inventories.FromSqlInterpolated(
            $"SELECT * FROM Inventories WHERE Id = {firstId} FOR UPDATE").SingleAsync();
            
        var item2 = await _context.Inventories.FromSqlInterpolated(
            $"SELECT * FROM Inventories WHERE Id = {secondId} FOR UPDATE").SingleAsync();

        // Mutasi saldo
        item1.AdjustStock(...);
        item2.AdjustStock(...);

        await _context.SaveChangesAsync();
        await tx.CommitAsync();
    }
    ```

13. **Solusi Perombakan Query**:
    1. Tambahkan `.AsNoTracking()` untuk menghilangkan snapshot tracking array.
    2. Tambahkan `.AsSplitQuery()` untuk memotong Cartesian duplication antara Merchant dan LedgerEntries.
    3. Gunakan seleksi proyeksi langsung (DTO Projections) hanya pada field yang dibutuhkan, menghindari materialisasi entity overhead:
    ```csharp
    public sealed record ReportRowDto(
        Guid TransactionId, 
        decimal Amount, 
        string MerchantName, 
        IReadOnlyList<decimal> LedgerEntries
    );

    var results = await _context.Transactions
        .AsNoTracking()
        .AsSplitQuery()
        .Select(t => new ReportRowDto(
            t.Id,
            t.Amount,
            t.Merchant.Name,
            t.LedgerEntries.Select(l => l.Amount).ToList()
        ))
        .ToListAsync();
    ```
    4. Jika data hanya perlu dibaca berurutan untuk streaming ke JSON response, gunakan `IAsyncEnumerable` tanpa `.ToListAsync()` guna menjaga alokasi memory tetap flat mendekati 0.

---

### 16. Summary

1. **Abstraksi vs Biaya**: Memahami perbedaan antara EF Core (Full tracking Unit of Work), Dapper (CIL Dynamic Method Micro-ORM), dan Native ADO.NET (`DbBatch`) adalah fondasi dalam merancang arsitektur persistence berkinerja tinggi. Gunakan alat yang sesuai dengan beban kerja (Read Heavy vs Rich Domain Mutation).
2. **Eliminasi Overhead Memori**: Snapshot change tracking memiliki kompleksitas $\mathcal{O}(N \times M)$. Kurangi beban garbage collection pada hot-path dengan `AsNoTracking()`, `DbContext Pooling`, dan Bulk Updates API (`ExecuteUpdateAsync`/`ExecuteDeleteAsync`).
3. **Efisiensi Jaringan**: Hindari latensi berulang dengan mengonsolidasikan perintah melalui `DbBatch` dan eliminasi payload membengkak (*Cartesian Explosion*) menggunakan `AsSplitQuery()`.
4. **Determinisme Konkurensi**: Pada sistem ber-throughput tinggi, hindari distributed transactions yang rapuh; terapkan *Lock Order Consistency* untuk mencegah deadlock serta gunakan *Transactional Outbox Pattern* guna menjaga integritas *event-driven architecture*.