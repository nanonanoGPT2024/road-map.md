# Bab 04 Module 01: Data Access with Entity Framework Core & Dapper

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** Back-End Engineering with .NET & ASP.NET Core
* **Kategori:** 02-Programming-Languages
* **Modul:** Bab 04 Module 01 — Data Access with Entity Framework Core & Dapper
* **Prasyarat Konseptual:**
  * Pemahaman mendalam tentang C# tingkat lanjut (Generics, LINQ Expressions, Async/Await, Memory Management).
  * Pemahaman tentang Relational Database Management Systems (RDBMS), SQL DDL/DML, Indeks, Tingkat Isolasi Transaksi (ACID), dan Connection Pooling.
  * Pola desain perangkat lunak dasar: Repository Pattern, Unit of Work, dan Dependency Injection (DI) pada ASP.NET Core.
* **Target Tingkat Kemahiran:** Advanced / Enterprise-Grade Architecture.
* **Waktu Penyelesaian:** 8–10 jam eksplorasi mendalam, implementasi kode, dan benchmarking praktis.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Membedakan Mekanisme Internal:** Menganalisis perbedaan mendasar antara model eksekusi Full ORM (EF Core) dan Micro-ORM (Dapper), termasuk overhead runtime, serialisasi metadata, dan siklus hidup koneksi.
2. **Menguasai Change Tracking & Metadata Engine:** Mengendalikan State Manager EF Core secara deterministik untuk skenario agregasi kompleks guna menghindari degradasi performa memory-footprint.
3. **Mengoptimalkan Kompilasi Query:** Menjelaskan dan mengimplementasikan siklus penerjemahan LINQ to SQL, caching Expression Tree, parameterization, serta Compiled Queries.
4. **Membangun Arsitektur Hybrid CQRS:** Menggabungkan EF Core (Write Path / Command) dan Dapper (Read Path / Query) dalam satu konteks transaksi tanpa memicu koneksi ganda atau deadlock.
5. **Mitigasi Masalah Kinerja Akses Data:** Mendiagnosis dan mengeliminasi masalah N+1 Query, Cartesius Explosion, Over-fetching, Connection Pool Starvation, dan Memory Leak akibat pelacakan identitas entitas.
6. **Menerapkan Keamanan & Observabilitas:** Mengamankan pipa akses data dari SQL Injection secara absolut serta mengintegrasikan distributed tracing via OpenTelemetry dan Database Interceptors.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Data access layer (DAL) adalah jembatan antara dua model representasi yang bertolak belakang: **Model Objek Berorientasi Domain** (yang sarat dengan enkapsulasi, hierarki, referensi siklik, dan invarians bisnis) dan **Model Relasional Berbasis Aljabar Himpunan** (tabel, baris, kolom, foreign key, dan set-based operations). Jurang ini dikenal sebagai *Object-Relational Impedance Mismatch*.

Dalam rekayasa sistem berkinerja tinggi:

* **Entity Framework Core adalah Engine Pemelihara Invarian.** Jangan perlakukan EF Core hanya sebagai "query generator". Nilai tertinggi EF Core terletak pada kemampuannya mengelola integritas agregat yang kompleks (Domain-Driven Design), menangani *concurrency conflicts*, dan mengatur mutasi graf objek melalui unit of work terpadu (`DbContext`).
* **Dapper adalah Engine Serialisasi Data Berkecepatan Metal.** Dapper berasumsi pengembang memahami SQL secara mendalam. Dapper bertindak hampir murni sebagai mapper deserialisasi tingkat rendah di atas `IDataReader`, mengeksekusi SQL raw secepat eksekusi native ADO.NET dengan alokasi memori minimal.
* **Pola Pikir Polyglot Persistensi Internal:** Jangan terjebak dalam dikotomi *EF Core vs Dapper*. Dalam arsitektur enterprise modern, keduanya bukan rival melainkan komplemen. Gunakan EF Core untuk operasi *Write-Heavy* yang membutuhkan validasi entitas, event domain, dan graf dependensi. Gunakan Dapper untuk operasi *Read-Heavy* (proyeksi kueri, analitik, pelaporan, API read-only dengan throughput masif) di mana overhead pelacakan state EF Core hanya menjadi pemborosan CPU dan alokasi heap.

```
       [ Client Request ]
               │
               ▼
┌───────────────────────────────┐
│     Application Service       │
└───────┬───────────────┬───────┘
        │ (Command)     │ (Query)
        ▼               ▼
┌───────────────┐ ┌───────────────┐
│    EF Core    │ │    Dapper     │  <-- Hybrid Pattern
│ (Unit of Work)│ │(Raw SQL Direct│
└───────┬───────┘ └───────┬───────┘
        │                 │
        ▼                 ▼
┌───────────────────────────────┐
│     ADO.NET / DbConnection    │
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│       Relational Engine       │
└───────────────────────────────┘
```

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur: Transparansi Arsitektur Internal EF Core vs Dapper

```
                    === EF CORE PIPELINE ===
[LINQ Expression] 
       │
       ▼
[Expression Tree Parsing] ──► [Query Compilation Cache Lookup]
                                        │ (Cache Miss)
                                        ▼
                             [Query Model Visitor]
                                        │
                                        ▼
                             [Relational SQL Translation]
                                        │
                                        ▼
                             [SQL String Cached]
                                        │
                                        ▼
                             [Execute DbCommand via ADO.NET]
                                        │
                                        ▼
                             [DbDataReader Returned]
                                        │
                                        ▼
                             [Materializer Pipeline]
                                        │
                                        ├─► [Allocate Entity Object]
                                        ├─► [Entity Identity Map Lookup]
                                        └─► [Snapshot / Tracking Initialization]
                                        │
                                        ▼
                             [Result Entities in Memory]


                    === DAPPER PIPELINE ===
[Raw SQL Query + Parameters]
       │
       ▼
[SqlMapper Cache Lookup (Command Definition Hash)]
       │ (Cache Hit: Dynamic IL Delegate)
       ▼
[Execute DbCommand via ADO.NET]
       │
       ▼
[DbDataReader Returned]
       │
       ▼
[Direct Emit Dynamic IL Deserializer] ──► [Direct Struct/Class Mapping]
       │
       ▼
[Result Plain Objects (POCO)]
```

### Diagram State Transition: EF Core Change Tracker

```
               ┌────────────────────────────────────────────────────────┐
               │                                                        │
               ▼                                                        │
         [ Detached ] ──( Attach / Query with Tracking )──► [ Unchanged ]
               │                                                 │
               │ (Mark Added)                                    │ (Modify Property)
               ▼                                                 ▼
          [ Added ]                                        [ Modified ]
               │                                                 │
               │                                                 │ (Mark Deleted)
               │                                                 ▼
               │                                           [ Deleted ]
               │                                                 │
               └────────────────► [ SaveChanges() ] ◄────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │                                             │
      (Success: Inserts/Updates)                      (Success: Deletes)
                 │                                             │
                 ▼                                             ▼
           [ Unchanged ]                                 [ Detached ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. EF Core Execution & Materialization Engine

EF Core mengabstraksikan database melalui serangkaian lapisan internal:

* **Query Compilation Pipeline:**
  Saat sebuah kueri LINQ dieksekusi, EF Core tidak langsung menjalankan kueri tersebut. Kueri tersebut diperlakukan sebagai sebuah `Expression Tree`.
  * **Parser:** Mengevaluasi node-node ekspresi pohon.
  * **Query Cache Key Generator:** Menghasilkan cache key unik berdasarkan struktur pohon ekspresi (mengabaikan nilai konstanta/parameter kueri).
  * **IQueryCompiler:** Memeriksa memori L1 cache (`CompiledQueryCache`). Jika ada (cache hit), langkah penerjemahan dilewati. Jika tidak (cache miss), ekspresi dialihkan ke `DatabaseProviderModelEvaluator` untuk dipecah menjadi SQL AST (*Abstract Syntax Tree*), dioptimalkan, lalu menghasilkan string SQL relasional spesifik vendor (e.g., PostgreSQL, SQL Server).
* **Identity Map & State Manager:**
  Di dalam instance `DbContext`, terdapat `StateManager`. Komponen ini bertindak sebagai *Identity Map*. Setiap entitas yang dibaca dengan pelacakan (*tracking*) didaftarkan berdasarkan nilai *Primary Key*-nya. 
  * State Manager menyimpan dua hal: **Current Values** dan **Original Values**.
  * Mekanisme **Snapshot Change Tracking** membuat salinan bayangan (*snapshot*) dari entitas saat pertama kali dimuat. Ketika `DetectChanges()` dipanggil (secara eksplisit atau implisit saat `SaveChanges`), EF Core melakukan perbandingan mendalam (*deep-compare*) antara snapshot asli dan nilai saat ini untuk menentukan properti mana saja yang kotor (*dirty*), lalu mengompilasi perintah SQL `UPDATE` minimalis.

### 2. Dapper Execution & JIT Dynamic Method Pipeline

Dapper beroperasi langsung di atas `System.Data.Common.DbConnection`:

* **Dynamic IL Generation (`System.Reflection.Emit`):**
  Alih-alih menggunakan refleksi standar C# (`PropertyInfo.SetValue`) yang memicu overhead CPU tinggi saat membaca kolom database baris demi baris, Dapper memanfaatkan *Dynamic Method Generation*.
  Saat sebuah kueri pertama kali dijalankan:
  1. Dapper membaca skema metadata dari `IDataReader` (tipe kolom, nama kolom, urutan indeks).
  2. Dapper secara runtime mengompilasi sebuah delegate CIL (*Common Intermediate Language*) khusus menggunakan `DynamicMethod`.
  3. Delegate ini setara dengan kode yang ditulis secara manual: membaca nilai dari `IDataRecord.GetInt64(0)`, melakukan unboxing jika tipe non-nullable, dan langsung memanggil *setter* properti objek tujuan.
* **SqlMapper Cache:**
  Delegate IL yang dihasilkan disimpan dalam cache memori lokal berbasis hash: `Command Definition` + `Type Target` + `Database Provider Type`. Pemanggilan kueri kedua dan seterusnya hanya melakukan hash lookup, melewati fase analisis, dan melompat langsung ke eksekusi native delegate secepat compiled C# code.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Kompilasi Kueri LINQ: Mengapa LINQ Menguras Alokasi Memori jika Tidak Dipahami

Ekspresi LINQ seperti:

```csharp
var users = await context.Users
    .Where(u => u.TenantId == tenantId && u.IsActive)
    .ToListAsync(cancellationToken);
```

bukanlah delegate `Func<User, bool>`, melainkan `Expression<Func<User, bool>>`. EF Core mengekstrak parameter capture context (variabel lokal `tenantId`) menjadi SQL Parameter `@__tenantId_0`.

*Bahaya Evaluasi Klien (Client vs Server Evaluation):*
Pada versi EF terdahulu, jika EF tidak dapat menerjemahkan suatu fungsi (misal: method C# kustom) ke dalam SQL, EF secara diam-diam mengeksekusi sisa kueri di memori klien dengan mengambil ribuan baris data (*Cartesian Explosion/Client Evaluation*). Di EF Core modern, hal ini memicu runtime exception (`InvalidOperationException`) kecuali pemanggilan dilakukan secara eksplisit setelah `AsEnumerable()` atau `ToList()`.

### 2. Parameterization vs Query Plan Cache Bloat

Mesin database seperti SQL Server atau PostgreSQL mengompilasi dan menyimpan Execution Plan dari SQL yang masuk.
* **Parameterized Query:** `SELECT * FROM Orders WHERE Id = @orderId` -> Execution plan di-cache satu kali, dipakai berulang kali dengan parameter berbeda.
* **String Concatenation (Anti-Pattern):** `SELECT * FROM Orders WHERE Id = " + orderId` -> Jika dipanggil dengan sejuta nilai `Id` berbeda, mesin database akan dipaksa mengompilasi 1.000.000 execution plan individual. Ini memicu *Plan Cache Pollution/Bloat*, menghabiskan memory cache DB, dan membuat CPU server database melonjak 100%. EF Core dan Dapper secara *default* memaksakan parameterized queries via ADO.NET parameters.

### 3. Change Tracking Mechanics: Snapshot vs Notification

EF Core mendukung dua gaya tracking:
1. **Snapshot Tracking (Default):** Mengonsumsi alokasi heap ekstra karena EF Core menduplikasi state setiap entitas dalam memori. Saat entitas dalam jumlah besar (e.g., 20.000 data) dimuat secara tracked, overhead garbage collector (GC Gen-1 & Gen-2) akan naik drastis saat proses `DetectChanges()` memindai seluruh graf memori.
2. **Notification Tracking:** Mengimplementasikan interface `INotifyPropertyChanging` dan `INotifyPropertyChanged` pada entity class. Entitas memberitahu EF secara langsung ketika ada mutasi. Efisiensi tracking meningkat pesat, namun mengorbankan polusi dependensi infrastruktur pada domain layer (Domain Model menjadi tidak *pure*).

### 4. Split Queries vs Single Query

Ketika melakukan `Include()` pada relasi *one-to-many* atau *many-to-many*:
```csharp
var orders = await context.Customers
    .Include(c => c.Orders)
    .ThenInclude(o => o.LineItems)
    .ToListAsync();
```
* **Single Query (Default):** EF Core menghasilkan `LEFT JOIN`. Jika Customer memiliki 10 Orders, dan tiap Order memiliki 10 LineItems, satu baris data Customer akan diduplikasi sebanyak 100 kali dalam stream database. Hal ini disebut **Cartesian Explosion**.
* **Split Query (`AsSplitQuery()`):** EF Core mengeksekusi kueri terpisah secara berurutan: satu untuk `Customer`, satu untuk `Orders`, satu untuk `LineItems`, lalu menyatukan relasinya di memori via Identity Map. Ini mengurangi I/O throughput jaringan secara drastis, tetapi mengorbankan konsistensi atomik kueri jika ada mutasi konkuren di database di sela-sela eksekusi kueri.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi infrastruktur akses data fundamental yang bersih, mengintegrasikan EF Core untuk write-model dan Dapper untuk read-model, dengan pembagian tanggung jawab yang deterministik.

### 1. Model Domain & Persistence Setup

```csharp
// Domain Entity
namespace CoreDataStore.Domain;

public sealed class Order
{
    public Guid Id { get; private set; }
    public string OrderNumber { get; private set; } = null!;
    public Guid CustomerId { get; private set; }
    public decimal TotalAmount { get; private set; }
    public OrderStatus Status { get; private set; }
    public DateTime CreatedAtUtc { get; private set; }

    private readonly List<OrderItem> _items = [];
    public IReadOnlyCollection<OrderItem> Items => _items.AsReadOnly();

    private Order() { } // Required for EF Core Materialization

    public static Order Create(string orderNumber, Guid customerId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(orderNumber);
        
        return new Order
        {
            Id = Guid.NewGuid(),
            OrderNumber = orderNumber,
            CustomerId = customerId,
            Status = OrderStatus.Pending,
            CreatedAtUtc = DateTime.UtcNow,
            TotalAmount = 0m
        };
    }

    public void AddItem(string productSku, decimal unitPrice, int quantity)
    {
        if (quantity <= 0) throw new ArgumentOutOfRangeException(nameof(quantity), "Quantity must be > 0");
        if (unitPrice < 0) throw new ArgumentOutOfRangeException(nameof(unitPrice), "UnitPrice cannot be negative");

        var item = new OrderItem(Guid.NewGuid(), Id, productSku, unitPrice, quantity);
        _items.Add(item);
        TotalAmount += unitPrice * quantity;
    }

    public void MarkAsCompleted()
    {
        if (Status != OrderStatus.Pending)
            throw new InvalidOperationException($"Cannot complete order from state: {Status}");
        
        Status = OrderStatus.Completed;
    }
}

public sealed class OrderItem
{
    public Guid Id { get; private set; }
    public Guid OrderId { get; private set; }
    public string ProductSku { get; private set; } = null!;
    public decimal UnitPrice { get; private set; }
    public int Quantity { get; private set; }

    internal OrderItem(Guid id, Guid orderId, string productSku, decimal unitPrice, int quantity)
    {
        Id = id;
        OrderId = orderId;
        ProductSku = productSku;
        UnitPrice = unitPrice;
        Quantity = quantity;
    }

    private OrderItem() { } // EF Core
}

public enum OrderStatus
{
    Pending = 1,
    Completed = 2,
    Cancelled = 3
}
```

### 2. EF Core Context & Explicit Configuration

```csharp
using Microsoft.EntityFrameworkCore;
using CoreDataStore.Domain;

namespace CoreDataStore.Infrastructure;

public sealed class ApplicationDbContext : DbContext
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OrderItem> OrderItems => Set<OrderItem>();

    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
        : base(options)
    {
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ApplicationDbContext).Assembly);
    }
}

// Fluent Configuration (Clean Separation of Concerns)
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

public sealed class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("orders");

        builder.HasKey(o => o.Id);

        builder.Property(o => o.Id)
            .ValueGeneratedNever();

        builder.Property(o => o.OrderNumber)
            .HasMaxLength(64)
            .IsRequired();

        builder.HasIndex(o => o.OrderNumber)
            .IsUnique();

        builder.Property(o => o.TotalAmount)
            .HasPrecision(18, 4);

        builder.Property(o => o.Status)
            .HasConversion<int>()
            .IsRequired();

        builder.Property(o => o.CreatedAtUtc)
            .IsRequired();

        // Enkapsulasi backing field navigasi
        builder.HasMany(o => o.Items)
            .WithOne()
            .HasForeignKey(i => i.OrderId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.Metadata
            .FindNavigation(nameof(Order.Items))!
            .SetPropertyAccessMode(PropertyAccessMode.Field);
    }
}
```

### 3. Dual Engine Execution: Dapper & EF Core Orchestration

```csharp
using System.Data;
using CoreDataStore.Domain;
using Dapper;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

namespace CoreDataStore.Infrastructure;

// Read Projection DTO (Immutable Record optimized for Dapper)
public sealed record OrderSummaryDto(
    Guid Id,
    string OrderNumber,
    decimal TotalAmount,
    string Status,
    DateTime CreatedAtUtc,
    int TotalItemsCount
);

public interface IOrderService
{
    Task<Guid> CreateOrderAsync(string orderNumber, Guid customerId, CancellationToken ct);
    Task<OrderSummaryDto?> GetOrderSummaryAsync(Guid orderId, CancellationToken ct);
}

public sealed class OrderService : IOrderService
{
    private readonly ApplicationDbContext _dbContext;

    public OrderService(ApplicationDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    // EF Core: Writes, Invariants, State Tracking
    public async Task<Guid> CreateOrderAsync(string orderNumber, Guid customerId, CancellationToken ct)
    {
        var order = Order.Create(orderNumber, customerId);
        order.AddItem("SKU-CORE-NET8", 150000m, 2);
        order.AddItem("SKU-BOOK-ARCH", 350000m, 1);

        await _dbContext.Orders.AddAsync(order, ct);
        await _dbContext.SaveChangesAsync(ct);

        return order.Id;
    }

    // Dapper: High performance direct read query (Zero Tracking, Direct Memory Deserialization)
    public async Task<OrderSummaryDto?> GetOrderSummaryAsync(Guid orderId, CancellationToken ct)
    {
        // Reusing EF Core's underlying ADO.NET connection to avoid opening a new connection
        var dbConnection = _dbContext.Database.GetDbConnection();
        
        if (dbConnection.State != ConnectionState.Open)
        {
            await dbConnection.OpenAsync(ct);
        }

        const string sql = """
            SELECT 
                o.Id,
                o.OrderNumber,
                o.TotalAmount,
                CASE o.Status 
                    WHEN 1 THEN 'Pending' 
                    WHEN 2 THEN 'Completed' 
                    ELSE 'Cancelled' 
                END AS Status,
                o.CreatedAtUtc,
                COALESCE(COUNT(i.Id), 0) AS TotalItemsCount
            FROM orders o
            LEFT JOIN OrderItems i ON o.Id = i.OrderId
            WHERE o.Id = @OrderId
            GROUP BY o.Id, o.OrderNumber, o.TotalAmount, o.Status, o.CreatedAtUtc;
            """;

        var command = new CommandDefinition(
            commandText: sql,
            parameters: new { OrderId = orderId },
            transaction: _dbContext.Database.CurrentTransaction?.GetDbTransaction(),
            cancellationToken: ct
        );

        return await dbConnection.QuerySingleOrDefaultAsync<OrderSummaryDto>(command);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanika dari kode fundamental di atas:

### `OrderConfiguration.cs`
* `builder.Property(o => o.TotalAmount).HasPrecision(18, 4);`: Mendefinisikan skala dan presisi eksplisit. Menghindari pemotongan desimal secara tidak sengaja oleh konversi implisit RDBMS driver default yang sering kali menggunakan `decimal(18,2)`.
* `builder.Metadata.FindNavigation(nameof(Order.Items))!.SetPropertyAccessMode(PropertyAccessMode.Field);`: **Konsep Domain Driven Design krusial.** Baris ini memaksa EF Core mem-bypass getter/setter publik dan langsung menyuntikkan data relational ke *private backing field* `_items`. Ini melindungi enkapsulasi: pihak luar tidak bisa seenaknya memanggil method `.Clear()` atau `.Add()` tanpa melalui domain method `AddItem()`.

### `OrderService.cs`
* `var dbConnection = _dbContext.Database.GetDbConnection();`: Mengambil instance `DbConnection` fisik yang sama yang dikelola oleh EF Core instance. Ini menghemat alokasi koneksi pada connection pool dan memungkinkan EF Core serta Dapper berbagi sesi database yang persis sama.
* `if (dbConnection.State != ConnectionState.Open) await dbConnection.OpenAsync(ct);`: EF Core membuka dan menutup koneksi secara *lazy* (hanya saat `SaveChangesAsync` atau kueri LINQ dieksekusi). Saat Dapper dipanggil secara langsung lewat connection yang sama, kita harus memastikan state-nya terbuka.
* `transaction: _dbContext.Database.CurrentTransaction?.GetDbTransaction()`: **Koordinasi Transaksi.** Jika kita membuka transaksi EF Core via `await _dbContext.Database.BeginTransactionAsync()`, baris ini memastikan Dapper beroperasi di bawah payung transaksi ID yang sama. Jika Dapper gagal, transaksi EF Core akan me-rollback operasi keduanya secara atomik.
* `var command = new CommandDefinition(..., cancellationToken: ct);`: Praktik terbaik Dapper. Hindari `dbConnection.QueryAsync(sql, param)`. Gunakan struct `CommandDefinition` untuk meneruskan `CancellationToken` secara native ke ADO.NET command level (`IDbCommand.Cancel()`). Jika client menutup koneksi HTTP, soket pembacaan database langsung dibatalkan di level database engine.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial High-Frequency Ledger & Settlement Core
* **Konteks:** Platform FinTech memproses transfer dana antar-rekening dan settlement akhir hari (*End-of-Day*).
* **Beban Sistem:**
  * Write Path: 2.000 transaksi/detik pada jam sibuk. Membutuhkan locking ketat, audit log komprehensif, event sourcing/domain state mutation, pencegahan *Double Spending*, serta invariant domain check.
  * Read Path: 15.000 request/detik untuk dashboard balance, rekonsiliasi realtime, dan laporan kepatuhan auditor.
* **Titik Kegagalan Sistem Lama:**
  Menggunakan EF Core murni untuk seluruh sistem. Ketika auditor menarik laporan histori 100.000 jurnal entri melalui kueri LINQ dengan relasi kompleks, Change Tracker memakan RAM hingga 4 GB, memicu GC Pause selama 3-5 detik, membuat *timeout* pada Write Path transaksi yang sedang berlangsung, dan akhirnya memicu *Connection Pool Starvation*.
* **Solusi Arsitektural:**
  1. **Write Path:** EF Core dengan *Optimistic Concurrency Token* (`xmin` di PostgreSQL atau `rowversion` di SQL Server), pelacakan isolasi perubahan pada agregat `AccountBalance` dan `JournalEntry`.
  2. **Read Path:** Dapper dengan unbuffered streaming (`CommandFlags.None`), kueri flat yang dialirkan langsung tanpa memuat seluruh dataset sekaligus ke RAM, membypass Change Tracker secara absolut.
  3. Mengikat keduanya dalam sebuah pipeline transaksi terkoordinasi jika operasi write membutuhkan pembacaan data skalar cepat untuk locking validasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi level enterprise dari skenario sistem Ledger FinTech tersebut.

### 1. Database Schema (PostgreSQL DDL)

```sql
CREATE TABLE accounts (
    id UUID PRIMARY KEY,
    account_number VARCHAR(32) NOT NULL UNIQUE,
    balance NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    row_version XID NOT NULL -- PostgreSQL Concurrency Token
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    reference_id VARCHAR(64) NOT NULL UNIQUE,
    source_account_id UUID NOT NULL REFERENCES accounts(id),
    destination_account_id UUID NOT NULL REFERENCES accounts(id),
    amount NUMERIC(18, 4) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_transactions_source ON transactions(source_account_id, timestamp_utc);
CREATE INDEX idx_transactions_dest ON transactions(destination_account_id, timestamp_utc);
```

### 2. Domain Models & Exception

```csharp
namespace FinancialLedger.Domain;

public sealed class InsufficientFundsException : Exception
{
    public InsufficientFundsException(string message) : base(message) { }
}

public sealed class Account
{
    public Guid Id { get; private set; }
    public string AccountNumber { get; private set; } = null!;
    public decimal Balance { get; private set; }
    public string Currency { get; private set; } = null!;
    public uint RowVersion { get; private set; } // Shadow mapped Concurrency Token

    private Account() { }

    public Account(Guid id, string accountNumber, string currency, decimal initialBalance)
    {
        Id = id;
        AccountNumber = accountNumber;
        Currency = currency;
        Balance = initialBalance;
    }

    public void Debit(decimal amount)
    {
        if (amount <= 0) throw new ArgumentException("Amount must be positive", nameof(amount));
        if (Balance < amount) throw new InsufficientFundsException($"Account {AccountNumber} has insufficient funds.");
        Balance -= amount;
    }

    public void Credit(decimal amount)
    {
        if (amount <= 0) throw new ArgumentException("Amount must be positive", nameof(amount));
        Balance += amount;
    }
}

public sealed class LedgerTransaction
{
    public Guid Id { get; private set; }
    public string ReferenceId { get; private set; } = null!;
    public Guid SourceAccountId { get; private set; }
    public Guid DestinationAccountId { get; private set; }
    public decimal Amount { get; private set; }
    public DateTime TimestampUtc { get; private set; }

    private LedgerTransaction() { }

    public LedgerTransaction(string referenceId, Guid sourceId, Guid destinationId, decimal amount)
    {
        Id = Guid.NewGuid();
        ReferenceId = referenceId;
        SourceAccountId = sourceId;
        DestinationAccountId = destinationId;
        Amount = amount;
        TimestampUtc = DateTime.UtcNow;
    }
}
```

### 3. EF Core Context with Concurrency Mapping

```csharp
using Microsoft.EntityFrameworkCore;
using FinancialLedger.Domain;

namespace FinancialLedger.Infrastructure;

public sealed class LedgerDbContext : DbContext
{
    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<LedgerTransaction> Transactions => Set<LedgerTransaction>();

    public LedgerDbContext(DbContextOptions<LedgerDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Account>(builder =>
        {
            builder.ToTable("accounts");
            builder.HasKey(a => a.Id);
            builder.Property(a => a.AccountNumber).HasMaxLength(32).IsRequired();
            builder.Property(a => a.Balance).HasPrecision(18, 4);
            builder.Property(a => a.Currency).HasMaxLength(3).IsRequired();

            // PostgreSQL Concurrency Token mapping
            builder.Property(a => a.RowVersion)
                   .HasColumnName("row_version")
                   .IsRowVersion();
        });

        modelBuilder.Entity<LedgerTransaction>(builder =>
        {
            builder.ToTable("transactions");
            builder.HasKey(t => t.Id);
            builder.Property(t => t.ReferenceId).HasMaxLength(64).IsRequired();
            builder.HasIndex(t => t.ReferenceId).IsUnique();
            builder.Property(t => t.Amount).HasPrecision(18, 4);
        });
    }
}
```

### 4. Enterprise-Grade Hybrid Ledger Service

```csharp
using System.Data;
using Dapper;
using FinancialLedger.Domain;
using Microsoft.EntityFrameworkCore;

namespace FinancialLedger.Infrastructure;

public sealed record TransactionReportDto
{
    public Guid TransactionId { get; init; }
    public string ReferenceId { get; init; } = null!;
    public string SourceAccountNumber { get; init; } = null!;
    public string DestinationAccountNumber { get; init; } = null!;
    public decimal Amount { get; init; }
    public DateTime TimestampUtc { get; init; }
}

public interface ILedgerService
{
    Task ExecuteTransferAsync(string refId, Guid sourceId, Guid destId, decimal amount, CancellationToken ct);
    IAsyncEnumerable<TransactionReportDto> StreamAccountStatementsAsync(Guid accountId, CancellationToken ct);
}

public sealed class LedgerService : ILedgerService
{
    private readonly LedgerDbContext _dbContext;

    public LedgerService(LedgerDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    // WRITE WORKFLOW: Fully Protected via EF Core Transaction & Optimistic Concurrency
    public async Task ExecuteTransferAsync(string refId, Guid sourceId, Guid destId, decimal amount, CancellationToken ct)
    {
        // Resilient execution strategy handles transient connection drops
        var strategy = _dbContext.Database.CreateExecutionStrategy();

        await strategy.ExecuteAsync(async () =>
        {
            await using var transaction = await _dbContext.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, ct);

            try
            {
                var sourceAccount = await _dbContext.Accounts
                    .SingleOrDefaultAsync(a => a.Id == sourceId, ct)
                    ?? throw new KeyNotFoundException($"Source account not found: {sourceId}");

                var destAccount = await _dbContext.Accounts
                    .SingleOrDefaultAsync(a => a.Id == destId, ct)
                    ?? throw new KeyNotFoundException($"Destination account not found: {destId}");

                // Enforce Business Logic / Invariants
                sourceAccount.Debit(amount);
                destAccount.Credit(amount);

                var ledgerEntry = new LedgerTransaction(refId, sourceId, destId, amount);
                await _dbContext.Transactions.AddAsync(ledgerEntry, ct);

                // Menjalankan SaveChanges. Jika ada intervensi thread lain terhadap row_version, DbUpdateConcurrencyException dipicu
                await _dbContext.SaveChangesAsync(ct);
                await transaction.CommitAsync(ct);
            }
            catch (DbUpdateConcurrencyException ex)
            {
                await transaction.RollbackAsync(ct);
                throw new InvalidOperationException("High contention detected. Concurrency collision on Account balance update. Retry transaction.", ex);
            }
            catch (Exception)
            {
                await transaction.RollbackAsync(ct);
                throw;
            }
        });
    }

    // READ WORKFLOW: Dapper Pipeline with Memory-Stream Optimization (Unbuffered)
    public async IAsyncEnumerable<TransactionReportDto> StreamAccountStatementsAsync(
        Guid accountId, 
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        var connection = _dbContext.Database.GetDbConnection();
        if (connection.State != ConnectionState.Open)
        {
            await connection.OpenAsync(ct);
        }

        const string sql = """
            SELECT 
                t.id AS TransactionId,
                t.reference_id AS ReferenceId,
                s.account_number AS SourceAccountNumber,
                d.account_number AS DestinationAccountNumber,
                t.amount AS Amount,
                t.timestamp_utc AS TimestampUtc
            FROM transactions t
            INNER JOIN accounts s ON t.source_account_id = s.id
            INNER JOIN accounts d ON t.destination_account_id = d.id
            WHERE t.source_account_id = @AccountId OR t.destination_account_id = @AccountId
            ORDER BY t.timestamp_utc DESC;
            """;

        // Menggunakan CommandFlags.None untuk eksekusi Unbuffered: Data distreaming langsung dari network buffer
        // Tidak memuat 100k data ke memori List<T> terlebih dahulu!
        var command = new CommandDefinition(
            commandText: sql,
            parameters: new { AccountId = accountId },
            flags: CommandFlags.None,
            cancellationToken: ct
        );

        // Eksekusi raw IDataReader via Dapper reader
        var reader = await connection.ExecuteReaderAsync(command);
        var rowParser = reader.GetRowParser<TransactionReportDto>();

        while (await reader.ReadAsync(ct))
        {
            yield return rowParser(reader);
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih antara EF Core murni, Dapper murni, atau Hybrid CQRS melibatkan trade-off arsitektural yang jelas:

| Metrik Arsitektur | Entity Framework Core 8 | Dapper 2.x | Raw ADO.NET (`DbCommand`) |
| :--- | :--- | :--- | :--- |
| **Abstraksi Database** | Sangat Tinggi (Bebas Provider via Migrations & Relational Translator) | Rendah (SQL Dialect Terikat Langsung ke Vendor Database) | Nyaris Nol (Manual API) |
| **Kecepatan Eksekusi** | Sedang - Tinggi (Setelah Expression Tree Cached) | Sangat Tinggi (~98% kecepatan raw ADO.NET) | Maksimal (Limitasi driver native) |
| **Alokasi Heap Memory** | Tinggi (Identity Map, Metadata, Snapshot States) | Sangat Rendah (Dynamic IL parsing langsung ke struct/object) | Terendah (Zero extra allocation jika dikelola manual) |
| **Kompleksitas Query** | Sangat Baik untuk Graf Agregat Kompleks; Menurun drastis pada Windowing Functions, Common Table Expressions (CTE). | Sempurna untuk SQL Arbitrer (CTE, `UNION`, Windowing, Stored Procedures kompleks). | Sama seperti Dapper, tetapi boilerplate kodenya masif. |
| **Otomasi Migrasi** | *Out-of-the-box* via `ef migrations`. Sinkronisasi skema terjamin. | Manual (Memerlukan DbUp, Flyway, atau Liquibase). | Manual. |
| **DDD Aggregate Enkapsulasi**| Luar biasa (Mendukung private backing field, value objects, domain events). | Rapuh (Membutuhkan mapping constructor atau properti dengan setter terbuka). | Rapuh (Manual parsing). |
| **Beban Perawatan** | Rendah saat model bisnis berubah; refactoring LINQ aman secara compile-time. | Menengah; perubahan skema database rawan memicu runtime error jika SQL string usang. | Sangat Tinggi; rentan runtime error akibat typo ordinal indeks kolom. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Connection Pool Exhaustion akibat Menggantungkan DataReader
* **Mekanisme Insiden:** Ketika kueri membaca data dalam jumlah besar via Dapper `QueryAsync<T>` tanpa pembatalan atau koneksi tidak dilepas dalam blok `await using`, `DbConnection` fisik tidak dikembalikan ke ADO.NET Pool. 
* **Dampak:** Di bawah beban 1.000 concurrent request, pool koneksi default (biasanya berukuran `Max Pool Size=100`) akan habis dalam hitungan detik. Kueri berikutnya akan hang selama 15 detik sebelum melemparkan `TimeoutException: Timeout expired. The timeout elapsed prior to obtaining a connection from the pool`.
* **Solusi:** Pastikan `DbContext` atau `DbConnection` selalu memiliki lifetime terkelola (Scoped per HTTP Request), dan konsumsi data reader hingga selesai atau batalkan secara eksplisit.

### 2. Transaction Deadlocks saat Sinkronisasi EF Core & Dapper
* **Mekanisme Insiden:** EF Core mengeksekusi *tracked update* pada baris A di tabel `accounts`. Tanpa melakukan commit, modul lain memanggil Dapper pada koneksi berbeda untuk membaca atau mengupdate baris yang sama dengan tingkat isolasi `RepeatableRead` atau `Serializable`.
* **Dampak:** Lock escalation memicu mutual dependency deadlock antara koneksi EF Core dan koneksi Dapper. Database engine mengorbankan salah satu transaksi sebagai *Deadlock Victim*.
* **Solusi:** Jangan pernah membuka koneksi baru dari factory jika sedang berada di dalam alur eksekusi service yang sama. Gunakan `_dbContext.Database.GetDbConnection()` dan pastikan `_dbContext.Database.CurrentTransaction?.GetDbTransaction()` diteruskan ke pemanggilan Dapper.

### 3. LINQ Subquery Cartesian Explosion
* **Mekanisme Insiden:** Melakukan kueri tiga tingkat: `Users -> Orders -> OrderItems`.
* **Dampak:** 1 User dengan 20 Orders, dan masing-masing 10 OrderItems akan mengembalikan $1 \times 20 \times 10 = 200$ baris duplikasi untuk satu entitas User dari server database ke aplikasi.
* **Solusi:** Gunakan `.AsSplitQuery()` untuk memecah SQL menjadi 3 kueri SELECT terpisah yang efisien, ATAU proyeksikan langsung via Dapper menjadi DTO datar.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Masalah N+1 Query

❌ **Salah:** Mengakses properti navigasi di dalam loop secara implisit (Lazy Loading) atau mengeksekusi kueri di dalam iterasi:
```csharp
var orders = await context.Orders.ToListAsync();
foreach (var order in orders)
{
    // Mengirim 1 network call SELECT per iterasi ke database!
    var items = await context.OrderItems.Where(i => i.OrderId == order.Id).ToListAsync();
}
```

✔ **Benar:** Gunakan Eager Loading via `Include()` pada EF Core, atau Group Query via Dapper:
```csharp
// Solusi EF Core Eager Loading
var orders = await context.Orders
    .Include(o => o.Items)
    .ToListAsync(cancellationToken);

// Atau Solusi Dapper Multi-Mapping dalam 1 Network Round-Trip
const string sql = """
    SELECT o.*, i.* 
    FROM orders o 
    INNER JOIN OrderItems i ON o.Id = i.OrderId;
    """;

var orderDictionary = new Dictionary<Guid, Order>();
await connection.QueryAsync<Order, OrderItem, Order>(
    sql,
    (order, item) =>
    {
        if (!orderDictionary.TryGetValue(order.Id, out var currentOrder))
        {
            currentOrder = order;
            orderDictionary.Add(currentOrder.Id, currentOrder);
        }
        // Asumsi relasi manual
        return currentOrder;
    },
    splitOn: "Id"
);
```

### 2. Mengabaikan AsNoTracking untuk Kueri Read-Only

❌ **Salah:** Menjalankan kueri pelaporan murni dengan pelacakan bawaan:
```csharp
var highValueOrders = await context.Orders
    .Where(o => o.TotalAmount > 1000000)
    .ToListAsync(); // EF Core melacak semua entitas ini di StateManager!
```

✔ **Benar:** Gunakan `AsNoTracking()` atau `AsNoTrackingWithIdentityResolution()`:
```csharp
var highValueOrders = await context.Orders
    .AsNoTracking()
    .Where(o => o.TotalAmount > 1000000)
    .ToListAsync(cancellationToken);
```
*Dampak:* Mengurangi pemakaian heap allocations hingga 60% dan mempercepat pemrosesan hingga 3x lipat karena snapshot generator dilewati seutuhnya.

### 3. Menggunakan IEnumerable alih-alih IQueryable Sebelum Filtering

❌ **Salah:** Filtering dieksekusi di memori aplikasi setelah mengunduh seluruh isi tabel:
```csharp
IEnumerable<Order> query = context.Orders;
// Database memuntahkan SELURUH baris tabel orders lewat kabel jaringan!
var filtered = query.Where(o => o.Status == OrderStatus.Completed).ToList(); 
```

✔ **Benar:** Pastikan tipe data tetap `IQueryable` hingga titik eksekusi terminal:
```csharp
IQueryable<Order> query = context.Orders;
// Filter diterjemahkan menjadi klausa WHERE di level SQL Server/Postgres
var filtered = await query
    .Where(o => o.Status == OrderStatus.Completed)
    .ToListAsync(cancellationToken);
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Explicit Column Projections:** Jangan pernah memetakan entitas domain lengkap jika UI atau caller hanya membutuhkan dua kolom. Gunakan LINQ `Select(x => new MyDto(...))` atau Dapper custom SELECT. Hal ini meminimalkan I/O disk database dan alokasi *network packet size*.
2. **Kompilasi Kueri Berulang (Compiled Queries):** Untuk kueri dengan frekuensi panggilan masif (misal: otentikasi User via Token atau API Key lookup):
   ```csharp
   private static readonly Func<ApplicationDbContext, string, Task<User?>> GetUserByApiKeyCompiled =
       EF.CompileAsyncQuery((ApplicationDbContext ctx, string key) =>
           ctx.Users.AsNoTracking().FirstOrDefault(u => u.ApiKey == key));
   ```
   Pendekatan ini memotong *tree hashing* dan query evaluation overhead ke level nol.
3. **Konfigurasi Database Indexing dari Fluent API:** Jangan mendefinisikan index terpisah secara acak di DB. Deklarasikan via `IEntityTypeConfiguration<T>`:
   ```csharp
   builder.HasIndex(x => new { x.TenantId, x.CreatedAtUtc })
          .IncludeProperties(x => x.TotalAmount); // Covering Index
   ```
4. **Hindari Magic String pada Dapper:** Gunakan pustaka pembantu atau `nameof()` untuk parameter mapping, atau gunakan source-generators yang memverifikasi kecocokan nama kolom SQL dengan tipe C# saat proses kompilasi (*compile-time safety*).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Benchmark Performa: EF Core vs Dapper vs ADO.NET (Fetch 1000 Rows)

| Runner | Method | Mean Execution Time | Allocated Memory | Gen 0 GC | Gen 1 GC |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Raw ADO.NET** | `DbDataReader` Manual | 2.10 ms | 120 KB | 15.62 | - |
| **Dapper 2.x** | `QueryAsync<Dto>` | 2.35 ms | 145 KB | 19.53 | - |
| **EF Core 8** | `AsNoTracking().ToListAsync()` | 3.80 ms | 380 KB | 46.87 | 7.81 |
| **EF Core 8** | Tracked `ToListAsync()` | 7.90 ms | 1.15 MB | 140.62 | 31.25 |

### 2. Batching Updates di EF Core 7 & 8
Dahulu, untuk mengupdate 5.000 baris, EF Core harus membaca 5.000 entitas ke memori, memodifikasi propertinya, lalu mengeksekusi 5.000 statement `UPDATE`. Kini, gunakan operasi *ExecuteUpdate* dan *ExecuteDelete*:

```csharp
// Menghasilkan 1 kali eksekusi SQL langsung ke database engine tanpa alokasi entitas di heap
await context.Orders
    .Where(o => o.Status == OrderStatus.Pending && o.CreatedAtUtc < cutoffDate)
    .ExecuteUpdateAsync(s => s
        .SetProperty(b => b.Status, OrderStatus.Cancelled),
        cancellationToken);
```

### 3. Dapper Unbuffered vs Buffered Optimization
Secara default, Dapper mengeksekusi kueri dengan parameter `buffered: true`. Artinya, seluruh data stream di-buffer ke dalam `List<T>` di memori aplikasi sebelum hasil dikembalikan.
Untuk dataset analitik berukuran besar:
```csharp
// Mengalirkan data per baris secara lazy langsung dari network buffer via IEnumerable/IDataReader
var largeDataStream = connection.Query<AuditLogDto>(
    sql, 
    parameters, 
    buffered: false // Unbuffered! Memory footprint konstan mendekati 0 MB
);
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. SQL Injection Prevention
SQL Injection terjadi ketika input pengguna yang tidak tervalidasi dirangkai langsung (*string concatenation*) ke dalam string SQL engine.

❌ **Fatal Vulnerability (Dapper):**
```csharp
// Serangan SQLi: userSearch = "'; DROP TABLE Users; --"
string query = $"SELECT * FROM Products WHERE Sku = '{userSearch}'"; 
var result = await connection.QueryAsync<Product>(query);
```

✔ **Impenetrable Defense (Parameterized Query):**
```csharp
string query = "SELECT * FROM Products WHERE Sku = @Sku";
var result = await connection.QueryAsync<Product>(query, new { Sku = userSearch });
```

❌ **Fatal Vulnerability (EF Core Raw SQL):**
```csharp
string rawSql = $"SELECT * FROM Products WHERE Category = '{categoryInput}'";
var products = await context.Products.FromSqlRaw(rawSql).ToListAsync();
```

✔ **Impenetrable Defense (Interpolated SQL):**
```csharp
// FromSqlInterpolated otomatis mengubah C# interpolated string menjadi parameterized DbParameter!
var products = await context.Products
    .FromSqlInterpolated($"SELECT * FROM Products WHERE Category = {categoryInput}")
    .ToListAsync();
```

### 2. Mitigasi Dynamic SQL Ordering Injection
Parameterization database standar `@Param` tidak dapat digunakan pada klausa struktural seperti `ORDER BY`, nama kolom, atau nama tabel.
*Solusi:* Terapkan *Strict Whitelisting* sebelum query dieksekusi:

```csharp
public static class SqlOrderSanitizer
{
    private static readonly HashSet<string> AllowedColumns = new(StringComparer.OrdinalIgnoreCase)
    {
        "CreatedAtUtc", "TotalAmount", "OrderNumber"
    };

    public static string SanitizeSortColumn(string clientInput)
    {
        if (AllowedColumns.TryGetValue(clientInput, out var safeColumn))
        {
            return safeColumn;
        }
        throw new SecurityException("Untrusted sort column detected!");
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Interceptors untuk Audit Logging dan Diagnostics
EF Core menyediakan `DbCommandInterceptor` untuk menangkap, memanipulasi, dan mengukur waktu eksekusi perintah database pada tingkat internal.

```csharp
using System.Data.Common;
using System.Diagnostics;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Logging;

namespace FinancialLedger.Infrastructure.Diagnostics;

public sealed class PerformanceCommandInterceptor : DbCommandInterceptor
{
    private readonly ILogger<PerformanceCommandInterceptor> _logger;
    private const long SlowQueryThresholdMs = 200;

    public PerformanceCommandInterceptor(ILogger<PerformanceCommandInterceptor> logger)
    {
        _logger = logger;
    }

    public override async ValueTask<DbDataReader> ReaderExecutedAsync(
        DbCommand command,
        CommandExecutedEventData eventData,
        DbDataReader result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Duration.TotalMilliseconds > SlowQueryThresholdMs)
        {
            _logger.LogWarning(
                "SLOW QUERY DETECTED ({Duration} ms). Command: {CommandText}",
                eventData.Duration.TotalMilliseconds,
                command.CommandText
            );
        }

        return await base.ReaderExecutedAsync(command, eventData, result, cancellationToken);
    }
}
```

### 2. Registrasi Interceptor pada ASP.NET Core DI
```csharp
services.AddSingleton<PerformanceCommandInterceptor>();

services.AddDbContextPool<ApplicationDbContext>((sp, options) =>
{
    options.UseNpgsql(connectionString)
           .AddInterceptors(sp.GetRequiredService<PerformanceCommandInterceptor>());
});
```

### 3. OpenTelemetry Distributed Tracing
Instrumentasi akses data secara otomatis mencakup pelacakan span ADO.NET (yang menangkap baik EF Core maupun Dapper tanpa modifikasi kode):

```csharp
services.AddOpenTelemetry()
    .WithTracing(tracerProviderBuilder =>
    {
        tracerProviderBuilder
            .AddAspNetCoreInstrumentation()
            .AddEntityFrameworkCoreInstrumentation(options =>
            {
                options.SetDbStatementForText = true; // Rekam statement SQL asli ke span tracing
            })
            .AddNpgsql(); // Menginstrumentasi ADO.NET layer (mencakup kueri Dapper!)
    });
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Quick Reference: Kapan Menggunakan EF Core vs Dapper

```
               ┌───────────────────────────────┐
               │ Apakah Operasi Bersifat Write │
               │     atau Butuh Invariant      │
               │         Aggregasi DDD?        │
               └───────────────┬───────────────┘
                               │
                      ┌────────┴────────┐
                      │                 │
                   [ YA ]            [ TIDAK ]
                      │                 │
                      ▼                 ▼
          ┌───────────────────────┐ ┌───────────────────────┐
          │  Gunakan EF Core      │ │ Apakah Kueri Kompleks │
          │  - State Tracking     │ │ (CTE, Window, Union,  │
          │  - Concurrency Checks │ │  High Throughput)?    │
          │  - SaveChanges UoW    │ └───────────┬───────────┘
          └───────────────────────┘             │
                                       ┌────────┴────────┐
                                       │                 │
                                    [ YA ]            [ TIDAK ]
                                       │                 │
                                       ▼                 ▼
                           ┌───────────────────────┐ ┌───────────────────────┐
                           │    Gunakan Dapper     │ │ EF Core Read-Only:    │
                           │    - Raw SQL Tuning   │ │ .AsNoTracking()       │
                           │    - Zero Tracking    │ │ Proyeksi .Select()    │
                           │    - Stream Unbuffered│ └───────────────────────┘
                           └───────────────────────┘
```

### Sintaksis Kunci Anti-Lupa

* **EF Core No-Tracking:** `context.Entities.AsNoTracking().Where(...).ToListAsync(ct)`
* **EF Core Split Query:** `context.Entities.Include(e => e.Children).AsSplitQuery().ToListAsync(ct)`
* **EF Core Batch Update:** `context.Entities.Where(e => e.IsExpired).ExecuteDeleteAsync(ct)`
* **Dapper Cancellation & Timeout:** `connection.QueryAsync(new CommandDefinition(sql, params, cancellationToken: ct, commandTimeout: 30))`
* **Dapper Unbuffered Streaming:** `connection.Query<T>(sql, params, buffered: false)`
* **Sinkronisasi Koneksi:** `var conn = context.Database.GetDbConnection();`
* **Sinkronisasi Transaksi:** `var tx = context.Database.CurrentTransaction?.GetDbTransaction();`

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah pemahaman konseptual dan internal Anda dengan menjawab pertanyaan-pertanyaan berikut:

### Kategori Basic

1. **Apa perbedaan mendasar antara cara kerja `IQueryable<T>` dan `IEnumerable<T>` saat memfilter data dari RDBMS di EF Core?**
   * *Jawaban:* `IQueryable<T>` membawa ekspresi pohon (`Expression Tree`) yang diterjemahkan langsung oleh penyedia database menjadi klausa relasional SQL (e.g. `WHERE`) sehingga eksekusi filtering terjadi di sisi mesin database server. `IEnumerable<T>` mengeksekusi evaluasi di memori aplikasi klien (*in-memory*), yang berarti seluruh data tabel akan dialirkan terlebih dahulu melalui jaringan sebelum difilter oleh CLR runtime.

2. **Mengapa pemanggilan `.AsNoTracking()` pada EF Core secara signifikan meningkatkan throughput operasi baca?**
   * *Jawaban:* Karena EF Core melewati tahap pembuatan salinan bayangan (*identity snapshot generation*) pada `StateManager`, menonaktifkan identity lookup pada Identity Map internal, dan membebaskan Garbage Collector dari memindai objek-objek tersebut saat `DetectChanges()` dijalankan.

3. **Bagaimana Dapper memetakan baris hasil query database ke objek C# secara jauh lebih cepat daripada pustaka ORM tradisional lama?**
   * *Jawaban:* Dapper menghasilkan delegate Intermediate Language (CIL) secara dinamis saat runtime menggunakan `System.Reflection.Emit` yang di-cache di memori. Ini membuat proses pembacaan properti dari `IDataReader` berjalan setara dengan kode C# terkompilasi murni, tanpa beban komparasi metadata refleksi berulang pada setiap baris data.

4. **Kapan masalah N+1 Query terjadi pada aplikasi data access? Berikan contohnya.**
   * *Jawaban:* Masalah N+1 terjadi ketika aplikasi mengeksekusi 1 kueri untuk mengambil kumpulan $N$ rekaman data induk, lalu mengeksekusi kueri terpisah tambahan sebanyak $N$ kali untuk mengambil relasi anak dari masing-masing rekaman tersebut secara berulang di dalam iterasi loop, alih-alih mengambil semuanya sekaligus via `JOIN` atau batching.

5. **Apa fungsi dari `CommandDefinition` pada Dapper dibanding mengirimkan raw string parameter biasa?**
   * *Jawaban:* `CommandDefinition` menyediakan kontrol tingkat lanjut atas eksekusi ADO.NET `DbCommand`, memungkinkan penyertaan parameter penting seperti `CancellationToken`, eksplisit `IDbTransaction`, alokasi `CommandTimeout`, serta flags operasional memori (`CommandFlags.Buffered` vs `CommandFlags.None`).

---

### Kategori Intermediate

6. **Apa yang dimaksud dengan "Cartesian Explosion" pada EF Core dan bagaimana cara mengatasinya tanpa menulis SQL manual?**
   * *Jawaban:* Cartesian Explosion terjadi saat melakukan eager-loading (`Include`) terhadap beberapa relasi *collection* secara simultan dalam *Single Query*, menghasilkan SQL `LEFT JOIN` berganda yang menduplikasi kolom data induk ribuan kali ke jaringan. Solusinya adalah memanggil method `.AsSplitQuery()` agar EF Core memecah kueri menjadi statement SQL individual yang dieksekusi terpisah per relasi dan disatukan kembali di memori.

7. **Bagaimana cara mengkoordinasikan Dapper dan EF Core agar dapat berjalan di bawah satu transaksi atomik yang sama tanpa error connection state?**
   * *Jawaban:* Dapper harus menggunakan instance `DbConnection` fisik yang sama milik EF Core (`_context.Database.GetDbConnection()`). Selanjutnya, transaksi lokal yang dibuka oleh EF Core (`_context.Database.BeginTransactionAsync()`) harus diakses via `_context.Database.CurrentTransaction.GetDbTransaction()` dan dioper secara eksplisit ke dalam parameter transaksi Dapper.

8. **Apa perbedaan teknis mendasar antara `CommandFlags.Buffered` dan `CommandFlags.None` saat mengeksekusi kueri Dapper dengan 500.000 data?**
   * *Jawaban:* `Buffered` (default) membaca seluruh 500.000 data ke dalam memori aplikasi sekaligus dan menyimpannya di `List<T>`, yang dapat memicu alokasi heap masif dan GC Pause (Out of Memory). `CommandFlags.None` (unbuffered) membuka stream langsung di mana data dibaca baris demi baris secara berurutan (*lazy pull*) langsung dari socket buffer jaringan via `IDataReader`, menjaga memory footprint aplikasi tetap datar (*constant memory*).

9. **Bagaimana EF Core mendeteksi konflik konkurensi (Concurrency Conflict) secara optimis pada PostgreSQL vs SQL Server?**
   * *Jawaban:* Pada SQL Server, EF Core memanfaatkan kolom bertipe `rowversion` / `timestamp` yang otomatis berubah setiap baris dimutasi. Pada PostgreSQL, EF Core umumnya memetakan kolom sistem bawaan `xmin` (ID transaksi pembuat/pengubah baris) sebagai shadow token beranotasi `.IsRowVersion()`. Saat `UPDATE` dijalankan, EF Core menambahkan klausa `WHERE [Id] = @Id AND [ConcurrencyToken] = @OriginalToken`. Jika baris telah diubah pihak lain, baris terpengaruh bernilai 0, memicu `DbUpdateConcurrencyException`.

10. **Mengapa interpolasi string `$""` aman digunakan pada EF Core via `FromSqlInterpolated`, namun sangat berbahaya jika digunakan via `FromSqlRaw`?**
    * *Jawaban:* `FromSqlInterpolated` menerima parameter bertipe `FormattableString`. EF Core mengekstrak argumen yang disuntikkan dan otomatis mengubahnya menjadi ADO.NET `DbParameter` (@p0, @p1) secara native di belakang layar. Sebaliknya, `FromSqlRaw` hanya menerima objek `string` biasa, sehingga interpolasi string `$""` akan dievaluasi oleh C# sebelum masuk ke EF Core, menghasilkan penggabungan teks mentah (*string concatenation*) yang rentan terhadap SQL Injection.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Enterprise Flash-Sale Inventory & Ledger Processing Engine"

#### Deskripsi
Bangunlah sebuah Web API ASP.NET Core minimalis berkinerja tinggi yang mensimulasikan penjualan *Flash Sale* dengan aturan integritas ketat (ketersediaan stok tidak boleh negatif di bawah serbuan ribuan transaksi konkuren) menggunakan kombinasi **EF Core** dan **Dapper**.

#### Spesifikasi Fungsional & Teknis

1. **Database Schema (PostgreSQL atau SQL Server):**
   * Tabel `products`: `id` (GUID), `sku` (string), `stock_quantity` (int), `price` (decimal), `concurrency_token` (RowVersion/xmin).
   * Tabel `orders`: `id` (GUID), `product_id` (GUID), `customer_id` (GUID), `quantity` (int), `created_at_utc` (DateTime).
2. **Write Flow (EF Core 8):**
   * Endpoint: `POST /api/flash-sale/checkout`
   * Muat entitas agregat `Product`, kurangi `stock_quantity` via domain method.
   * Buat entitas `Order`.
   * Simpan via `SaveChangesAsync` yang dilindungi *Optimistic Concurrency Control*.
   * Jika terjadi benturan konkurensi (`DbUpdateConcurrencyException`), lakukan *exponential backoff retry* (maksimal 3 kali percobaan) menggunakan Polly atau custom loop sebelum mengembalikan HTTP 409 Conflict.
3. **Read Flow (Dapper 2.x):**
   * Endpoint: `GET /api/flash-sale/analytics/top-products`
   * Gunakan Dapper untuk mengeksekusi Common Table Expression (CTE) yang menghitung total penjualan, sisa stok, dan volume pendapatan per jam secara flat.
   * Stream data hasil langsung menggunakan `IAsyncEnumerable<T>` dengan mode `CommandFlags.None` (Unbuffered).
4. **Validasi Kualitas Kode:**
   * Tidak boleh ada N+1 query.
   * Tidak boleh ada alokasi heap yang tidak perlu (gunakan `AsNoTracking` untuk read-only checks).
   * Seluruh method database harus menghormati `CancellationToken`.
   * Tulis satu unit test/integration test yang menyimulasikan 50 thread konkuren mencoba membeli 1 produk yang hanya memiliki sisa stok 10 item. Pastikan tepat 10 transaksi berhasil dan 40 lainnya ditolak secara aman tanpa korupsi data.