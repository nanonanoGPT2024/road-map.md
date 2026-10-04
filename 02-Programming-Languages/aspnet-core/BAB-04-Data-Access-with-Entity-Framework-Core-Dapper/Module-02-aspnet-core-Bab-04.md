# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (EF Core & Dapper)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. Membedah arsitektur internal **Entity Framework Core (EF Core)** meliputi State Management, Query Compilation Pipeline, dan Execution Strategy.
2. Menguasai fitur lanjutan **Dapper** seperti multi-mapping, multiple result sets, streaming (`CommandBehavior.SequentialAccess`), dan custom Type Handlers.
3. Mengarsiteki pola **Hybrid Data Layer (CQRS)** yang memadukan EF Core untuk domain write-model (Transactional Unit of Work) dan Dapper untuk read-model performa tinggi.
4. Menerapkan strategi konkurensi optimistik (*Optimistic Concurrency Control*) berbasis RowVersion/Concurrency Tokens untuk mencegah *Lost Updates*.
5. Mengimplementasikan ketahanan koneksi (*Connection Resiliency*), kustomisasi Interceptors, dan Savepoints pada transaksi database kompleks.
6. Mendiagnosis degradasi performa akses data (N+1 query, Cartesian explosion, memory bloat) melalui profiling terstruktur dan APM.

---

## 2. Prerequisite

Peserta wajib memahami materi fondasi berikut:
* Pemrograman C# 12 dan .NET 8 modern (Async/Await, Generic Constraints, Records, LINQ Expression Trees).
* Konsep dasar EF Core (DbContext, DbSet, Migrations, Fluent API dasar).
* Konsep dasar SQL RDBMS (PostgreSQL/SQL Server): Transaction Isolation Levels (Read Committed, Repeatable Read, Serializable), Indexing (B-Tree, Clustered/Non-Clustered), Execution Plans.
* Telah menyelesaikan Modul 01: Fondasi ORM dan Micro-ORM.

---

## 3. Concept & Internal Architecture

### 3.1 Siklus Hidup dan State Tracker EF Core
EF Core bukan sekadar SQL generator; EF Core adalah implementasi pola **Identity Map** dan **Unit of Work**. Jantung dari EF Core adalah `ChangeTracker`.

```
Entity Instance In Memory
       │
       ▼
┌──────────────────┐
│  ChangeTracker   │ ◄─── Snapshot Strategy / INotifyPropertyChanged
└────────┬─────────┘
         │
         ├─── Detached  (Tidak dilacak oleh DbContext)
         ├─── Unchanged (Identik dengan basis data)
         ├─── Added     (Akan dieksekusi via INSERT saat SaveChanges)
         ├─── Modified  (Deteksi mutasi properti via Snapshot comparison)
         └─── Deleted   (Akan dieksekusi via DELETE saat SaveChanges)
```

1. **Snapshot-Based Tracking (Default)**: Saat entitas dimuat dari basis data tanpa `.AsNoTracking()`, EF Core membuat salinan *deep-copy* (snapshot) dari nilai-nilai properti entitas tersebut di dalam memori.
2. **DetectChanges()**: Dipanggil secara implisit oleh `SaveChanges()` atau secara eksplisit. EF Core melakukan iterasi ke seluruh entitas yang dilacak, membandingkan nilai saat ini dengan snapshot. Operasi ini bernilai $O(N)$ terhadap jumlah entitas terdaftar.
3. **Identity Map**: Mencegah instansiasi ganda untuk satu baris data unik (Primary Key) dalam satu siklus `DbContext`. Jika ID `101` sudah ada di memori, query berikutnya yang menghasilkan ID `101` akan mengembalikan referensi instansi yang sama, bukan objek baru.

### 3.2 LINQ Query Compilation Pipeline
Ketika query LINQ dieksekusi pada EF Core, tahapan berikut dilalui sebelum SQL dikirimkan ke provider database:

```
[LINQ Expression Tree]
          │
          ▼
┌─────────────────────────────────┐
│       Query Compilation         │
│  (Parser, Visitor, Cache Check) │
└─────────────────┬───────────────┘
                  │
          Cache Hit? ──Yes──┐
                  │ No      │
                  ▼         │
┌─────────────────────────┐ │
│  Query Model Relational │ │
│    Translation & SQL    │ │
└─────────────────────────┘ │
                  │         │
                  ▼         │
┌─────────────────────────┐ │
│ Compiled Execution Plan │◄┘
└─────────────────┬───────────────┘
                  │
                  ▼
         [ADO.NET DbCommand]
                  │
                  ▼
          [Database Server]
```

* **Query Cache**: EF Core menyimpan hasil kompilasi Expression Tree menjadi SQL generator delegate di cache internal berbasis hashing dari AST (Abstract Syntax Tree). Parameter dinamis dalam query LINQ tidak membatalkan cache, namun *dynamic schema* atau pemanggilan fungsi non-parametrik akan memicu kompilasi ulang.
* **Materialization**: ADO.NET `DbDataReader` membaca baris demi baris, dan EF Core memetakan nilai kolom ke properti objek C# melalui delegasi kompilasi ekspresi (`IL generation`).

### 3.3 Anatomi Dapper: Eksekusi Direct IL-Emit Micro-ORM
Dapper memangkas semua abstraksi *Change Tracking*, *Identity Map*, dan *Expression Parsing*. 

* Ketika `QueryAsync<T>` dijalankan, Dapper memeriksa internal cache `ConcurrentDictionary<QueryCacheKey, CacheCheckResult>`.
* Kunci cache tersusun dari SQL string, tipe parameter, tipe return, dan connection string.
* Jika tidak ada dalam cache, Dapper menggunakan **Reflection.Emit** (Dynamic Method) untuk membuat *in-memory dynamic IL code* yang secara langsung membaca ordinal dari `IDataReader` dan menyetel properti objek target. Hasilnya: overhead alokasi memori dan siklus CPU mendekati ADO.NET murni.

---

## 4. Why & What

| Fitur / Karakteristik | EF Core Lanjutan | Dapper Lanjutan |
| :--- | :--- | :--- |
| **Paradigma Utama** | Full-fledged ORM (Domain Modeling & UoW) | Micro-ORM (Data Mapper) |
| **Change Tracking** | Otomatis via State Tracker | Manual (Tidak Ada) |
| **SQL Generation** | Otomatis via LINQ Provider Relasional | Manual (Raw SQL ditulis oleh Developer) |
| **Memory Footprint** | Menengah ke Tinggi (Snapshot + Identity Map) | Minimal (Hanya buffer pembacaan data) |
| **Kompleksitas Query** | Terbatas pada kapabilitas translasi LINQ | Tidak terbatas (Semua fitur native RDBMS) |
| **Penggunaan Ideal** | Operasi Transaksional Kompleks (Write Model) | Query Agregasi, Reporting, Dashboard (Read Model) |

### Mengapa Mengadopsi Arsitektur Hybrid?
Penggunaan satu jenis data access layer untuk semua kebutuhan sistem enterprise sering kali menimbulkan dilema arsitektur:
* **Hanya Menggunakan EF Core**: Berisiko memicu query SQL sub-optimal pada join multi-tabel kompleks, memori bengkak akibat materialisasi grafik relasi besar, dan overhead `ChangeTracker` yang tidak dibutuhkan pada operasi read-only.
* **Hanya Menggunakan Dapper**: Mengharuskan penulisan SQL manual untuk operasi CRUD rutin, ketiadaan mekanisme Change Tracking bawaan yang andal untuk Domain Entities, serta tingginya duplikasi kode untuk penanganan konkurensi.
* **Solusi Hybrid**: Mengombinasikan kekuatan **EF Core** untuk sisi *Command/Write* (validasi domain, state mutation, invariant enforcement) dan **Dapper** untuk sisi *Query/Read* (proyeksi performa tinggi langsung ke DTO).

---

## 5. How (Workflow Detail)

### 5.1 Alur Kerja Optimistic Concurrency Control (EF Core)
1. Definisikan field *token* konkurensi (misal: `byte[] RowVersion` pada SQL Server atau `uint xmin` pada PostgreSQL).
2. Klien membaca data (Snapshot $T_0$).
3. Klien mengirim permintaan mutasi beserta token konkurensi awal.
4. EF Core menerbitkan SQL `UPDATE ... WHERE Id = @id AND ConcurrencyToken = @originalToken`.
5. RDBMS mengevaluasi affected rows. Jika 0 (karena ada transaksi lain yang mengubah data pada $T_1$), EF Core melempar `DbUpdateConcurrencyException`.
6. Aplikasi menangani resolusi konflik: *Client Wins*, *Store Wins*, atau *Database Merge*.

### 5.2 Alur Kerja Advanced Multi-Mapping (Dapper)
1. Tulis query SQL eksplisit yang melakukan join antartabel.
2. Definisikan pemisah antar-entitas menggunakan parameter `splitOn`.
3. Sediakan fungsi delegasi `Func<T1, T2, T3, T1>` untuk menyusun grafik relasi objek secara in-memory.
4. Gunakan `Dictionary<TKey, TParent>` dalam closure untuk mencegah duplikasi parent saat memproses relasi one-to-many.

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Perakitan vs. Mesin Vending Otomatis
* **EF Core (Pabrik Perakitan Terintegrasi)**: Anda memasukkan komponen mentah, sistem memantau setiap perubahan posisi komponen (*ChangeTracker*), mencatat nomor seri part (*Identity Map*), dan secara hati-hati merakitnya hingga menjadi produk akhir melalui jalur kontrol ketat sebelum dikirim ke gudang (*Unit of Work*). Sangat aman dan terstruktur, tetapi membutuhkan setup jalur perakitan yang besar.
* **Dapper (Mesin Vending Otomatis Berkecepatan Tinggi)**: Anda memasukkan koin (SQL query langsung), mesin menjatuhkan barang pesanan tepat ke tangan Anda tanpa mencatat riwayat pemakaian barang atau memeriksa modifikasi fisik sesudahnya. Cepat, instan, hemat energi, tanpa overhead manajemen stok internal.

### Arsitektur Aliran Hybrid CQRS Data Layer

```
                        ┌───────────────────────────────┐
                        │   API Controller / Endpoint   │
                        └───────────────┬───────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │                                             │
           Write / Command                               Read / Query
                 │                                             │
                 ▼                                             ▼
      ┌─────────────────────┐                       ┌─────────────────────┐
      │  Domain Repository  │                       │    Query Service    │
      │      (EF Core)      │                       │      (Dapper)       │
      └──────────┬──────────┘                       └──────────┬──────────┘
                 │                                             │
                 │ Tracks State                                │ No Tracking
                 │ Validates Invariants                        │ Direct DTO Projection
                 │ Emits SaveChanges                           │ Raw/Optimized SQL
                 ▼                                             ▼
      ┌─────────────────────┐                       ┌─────────────────────┐
      │   AppDbContext      │                       │  ISqlConnection     │
      └──────────┬──────────┘                       └──────────┬──────────┘
                 │                                             │
                 └──────────────────────┬──────────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │    PostgreSQL / SQL Server    │
                        └───────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dapper Multi-Mapping (One-to-One)

Contoh dasar memetakan `User` dan `Profile` menggunakan Dapper `splitOn`.

```csharp
using System.Data;
using Dapper;

public sealed record UserProfileDto(Guid UserId, string Username, string Email, string Bio, string AvatarUrl);

public sealed class UserRepository
{
    private readonly IDbConnection _connection;

    public UserRepository(IDbConnection connection) => _connection = connection;

    public async Task<UserProfileDto?> GetUserProfileAsync(Guid userId, CancellationToken ct)
    {
        const string sql = """
            SELECT 
                u.id AS UserId, u.username AS Username, u.email AS Email,
                p.bio AS Bio, p.avatar_url AS AvatarUrl
            FROM users u
            INNER JOIN profiles p ON p.user_id = u.id
            WHERE u.id = @UserId;
            """;

        var result = await _connection.QueryAsync<UserProfileDto, dynamic, UserProfileDto>(
            new CommandDefinition(
                sql,
                new { UserId = userId },
                cancellationToken: ct
            ),
            map: (user, profile) => new UserProfileDto(
                user.UserId,
                user.Username,
                user.Email,
                profile.Bio,
                profile.AvatarUrl
            ),
            splitOn: "Bio"
        );

        return result.FirstOrDefault();
    }
}
```

### 7.2 Practical Example: Enterprise Hybrid CQRS Implementation

Berikut adalah implementasi skala industri untuk sistem e-commerce checkout yang menggabungkan:
1. **EF Core**: Write model dengan Concurrency Token, Execution Strategy, dan Interceptors.
2. **Dapper**: Read model dengan Multi-Mapping (One-to-Many) dan Streaming.

#### Domain Entities & EF Core Infrastructure (Write Side)

```csharp
// Entities/Order.cs
public sealed class Order
{
    public Guid Id { get; private set; }
    public string CustomerId { get; private set; } = null!;
    public OrderStatus Status { get; private set; }
    public decimal TotalAmount { get; private set; }
    public byte[] Version { get; private set; } = null!; // Concurrency Token
    
    private readonly List<OrderItem> _items = [];
    public IReadOnlyCollection<OrderItem> Items => _items.AsReadOnly();

    private Order() { } // Required for EF Core

    public static Order Create(string customerId)
    {
        return new Order
        {
            Id = Guid.NewGuid(),
            CustomerId = customerId,
            Status = OrderStatus.Draft,
            TotalAmount = 0
        };
    }

    public void AddItem(Guid productId, int quantity, decimal unitPrice)
    {
        if (Status != OrderStatus.Draft)
            throw new InvalidOperationException("Tidak dapat mengubah item pada order yang sudah final.");

        var existingItem = _items.FirstOrDefault(i => i.ProductId == productId);
        if (existingItem != null)
        {
            existingItem.UpdateQuantity(existingItem.Quantity + quantity);
        }
        else
        {
            _items.Add(new OrderItem(Id, productId, quantity, unitPrice));
        }

        TotalAmount = _items.Sum(x => x.Quantity * x.UnitPrice);
    }

    public void Confirm()
    {
        if (!_items.Any())
            throw new InvalidOperationException("Order harus memiliki minimal satu item untuk dikonfirmasi.");
        
        Status = OrderStatus.Confirmed;
    }
}

public sealed class OrderItem
{
    public Guid Id { get; private set; }
    public Guid OrderId { get; private set; }
    public Guid ProductId { get; private set; }
    public int Quantity { get; private set; }
    public decimal UnitPrice { get; private set; }

    internal OrderItem(Guid orderId, Guid productId, int quantity, decimal unitPrice)
    {
        Id = Guid.NewGuid();
        OrderId = orderId;
        ProductId = productId;
        Quantity = quantity;
        UnitPrice = unitPrice;
    }

    internal void UpdateQuantity(int newQuantity)
    {
        if (newQuantity <= 0)
            throw new ArgumentOutOfRangeException(nameof(newQuantity), "Kuantitas harus positif.");
        Quantity = newQuantity;
    }
}

public enum OrderStatus { Draft = 0, Confirmed = 1, Shipped = 2, Cancelled = 3 }
```

```csharp
// Infrastructure/Persistence/Configurations/OrderConfiguration.cs
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

public sealed class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> builder)
    {
        builder.ToTable("orders");
        builder.HasKey(x => x.Id);

        builder.Property(x => x.CustomerId).IsRequired().HasMaxLength(64);
        builder.Property(x => x.TotalAmount).HasPrecision(18, 4);

        // Menentukan token konkurensi (PostgreSQL xmin atau SQL Server RowVersion)
        // Di sini kita gunakan byte[] untuk SQL Server RowVersion/Timestamp:
        builder.Property(x => x.Version)
               .IsRowVersion();

        builder.HasMany(x => x.Items)
               .WithOne()
               .HasForeignKey(x => x.OrderId)
               .OnDelete(DeleteBehavior.Cascade);
    }
}
```

```csharp
// Infrastructure/Persistence/AppDbContext.cs
using Microsoft.EntityFrameworkCore;

public sealed class AppDbContext : DbContext
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OrderItem> OrderItems => Set<OrderItem>();

    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
```

#### Dapper Read Model Service (Read Side)

```csharp
// Application/Orders/Queries/OrderReadModels.cs
public sealed record OrderDetailDto
{
    public Guid OrderId { get; init; }
    public string CustomerId { get; init; } = default!;
    public string Status { get; init; } = default!;
    public decimal TotalAmount { get; init; }
    public List<OrderItemDto> Items { get; init; } = [];
}

public sealed record OrderItemDto(Guid ItemId, Guid ProductId, int Quantity, decimal UnitPrice);
```

```csharp
// Application/Orders/Queries/OrderQueryService.cs
using System.Data;
using Dapper;

public interface IOrderQueryService
{
    Task<OrderDetailDto?> GetOrderByIdAsync(Guid orderId, CancellationToken ct);
    IAsyncEnumerable<OrderDetailDto> StreamConfirmedOrdersAsync(CancellationToken ct);
}

public sealed class OrderQueryService : IOrderQueryService
{
    private readonly IDbConnectionFactory _connectionFactory;

    public OrderQueryService(IDbConnectionFactory connectionFactory)
    {
        _connectionFactory = connectionFactory;
    }

    public async Task<OrderDetailDto?> GetOrderByIdAsync(Guid orderId, CancellationToken ct)
    {
        using var connection = _connectionFactory.CreateConnection();

        const string sql = """
            SELECT 
                o.Id AS OrderId, o.CustomerId, o.Status, o.TotalAmount,
                i.Id AS ItemId, i.ProductId, i.Quantity, i.UnitPrice
            FROM orders o
            LEFT JOIN order_items i ON i.OrderId = o.Id
            WHERE o.Id = @OrderId;
            """;

        var lookup = new Dictionary<Guid, OrderDetailDto>();

        var command = new CommandDefinition(sql, new { OrderId = orderId }, cancellationToken: ct);

        await connection.QueryAsync<OrderDetailDto, OrderItemDto?, OrderDetailDto>(
            command,
            (order, item) =>
            {
                if (!lookup.TryGetValue(order.OrderId, out var currentOrder))
                {
                    currentOrder = order;
                    lookup.Add(currentOrder.OrderId, currentOrder);
                }

                if (item != null)
                {
                    currentOrder.Items.Add(item);
                }

                return currentOrder;
            },
            splitOn: "ItemId"
        );

        return lookup.Values.FirstOrDefault();
    }

    public async IAsyncEnumerable<OrderDetailDto> StreamConfirmedOrdersAsync(
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        using var connection = _connectionFactory.CreateConnection();
        if (connection.State != ConnectionState.Open)
            connection.Open();

        const string sql = """
            SELECT 
                o.Id AS OrderId, o.CustomerId, o.Status, o.TotalAmount
            FROM orders o
            WHERE o.Status = 1;
            """;

        var command = new CommandDefinition(
            sql, 
            flags: CommandFlags.Buffered, // Ganti ke CommandFlags.None jika ingin streaming murni tanpa caching internal Dapper
            cancellationToken: ct
        );

        var reader = await connection.ExecuteReaderAsync(command, CommandBehavior.SingleResult);
        var rowParser = reader.GetRowParser<OrderDetailDto>();

        while (await reader.ReadAsync(ct))
        {
            yield return rowParser(reader);
        }
    }
}

public interface IDbConnectionFactory
{
    IDbConnection CreateConnection();
}
```

---

## 8. Real World Case Study: High-Throughput E-Commerce Flash Sale

### Skenario Masalah
Platform flash sale berskala enterprise memproses 15.000 pesanan per detik (*peak write*) dan melayani 120.000 request status inventory per detik (*peak read*). 
* Terjadi *deadlock* masif pada tabel `Inventory` dan `Orders`.
* Overhead `ChangeTracker` EF Core menyebabkan lonjakan alokasi memori GC Gen2 hingga 8 GB dalam 5 menit pertama, berujung pada *High-Pause Latency*.
* Ditemukan masalah *Lost Updates*: dua transaksi paralel mengurangi kuantitas stok produk yang sama di saat bersamaan, mengakibatkan *overselling* (stok minus).

### Solusi Arsitektur
1. **Write Separation (EF Core + Concurrency Tokens + Execution Strategy)**:
   * Mengisolasi mutasi agregat order menggunakan DbContext yang dikonfigurasi dengan *Resilient Execution Strategy*.
   * Menggunakan token konkurensi pada entitas `InventoryItem` guna mendeteksi tabrakan stok dan menolak transaksi secara atomik tanpa mengunci tabel (*No table locks*).
2. **Read Separation (Dapper + Read-Replica)**:
   * Mengarahkan seluruh query pembacaan ke Dapper melalui Read-Replica connection pool terpisah.
   * Mengeliminasi alokasi pelacakan entity (`AsNoTracking` di EF Core masih memiliki overhead parsing query dan mapping internal; Dapper IL-Emit mengurangi latency pembacaan sebesar 45%).
3. **Penyelesaian Lost Update Menggunakan Optimistic Loop**:

```csharp
public async Task<bool> ReserveStockAsync(Guid productId, int quantity, CancellationToken ct)
{
    const int maxRetries = 3;
    var strategy = _dbContext.Database.CreateExecutionStrategy();

    return await strategy.ExecuteAsync(async () =>
    {
        for (var attempt = 1; attempt <= maxRetries; attempt++)
        {
            try
            {
                var inventory = await _dbContext.Inventories
                    .SingleOrDefaultAsync(x => x.ProductId == productId, ct);

                if (inventory == null || inventory.AvailableStock < quantity)
                    return false;

                inventory.DeductStock(quantity);

                await _dbContext.SaveChangesAsync(ct);
                return true;
            }
            catch (DbUpdateConcurrencyException ex)
            {
                if (attempt == maxRetries)
                {
                    _logger.LogWarning(ex, "Konflik konkurensi maksimum tercapai untuk produk {ProductId}.", productId);
                    throw;
                }

                // Refresh model dari basis data untuk mendapatkan RowVersion terbaru
                foreach (var entry in ex.Entries)
                {
                    await entry.ReloadAsync(ct);
                }
            }
        }
        return false;
    });
}
```

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Hybrid (EF Core Write + Dapper Read)** | Throughput maksimal pada query; Keamanan invariansi domain dan kemudahan transactional UoW pada command. | Membutuhkan dua layer akses data, duplikasi pemetaan skema ke DTO/Entitas, pemeliharaan dependensi ganda. |
| **Compiled Queries (EF Core)** | Memotong waktu kompilasi LINQ Expression Tree; mendekati kecepatan Dapper untuk skenario query berulang. | Sintaks kaku, tidak fleksibel untuk query dinamis dengan filter kondisional, membutuhkan kode boilerplate tambahan. |
| **Optimistic Concurrency** | Tidak ada resource locks di DB (High Throughput untuk sistem read-heavy / low-contention). | Expensive retry logic ketika terjadi benturan tinggi (*high contention*); beban rollback ditanggung aplikasi. |
| **Split Queries (`AsSplitQuery`)** | Menghindari *Cartesian Explosion* pada join multi-koleksi one-to-many. | Eksekusi beberapa SQL terpisah menghasilkan latency jaringan tambahan; rentan terhadap inkonsistensi data jika isolasi snapshot tidak aktif. |
| **Dapper Unbuffered Streaming** | Konsumsi memori mendekati nol saat membaca ratusan ribu baris data. | Menahan koneksi basis data tetap terbuka sepanjang iterasi stream; membatasi koneksi pool jika iterasi lambat. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Cartesian Explosion Akibat Eager Loading Ganda
* **Kesalahan**: Menggunakan banyak `.Include()` pada relasi one-to-many dalam satu query EF Core secara bersamaan.
  ```csharp
  // BAHAYA: Menggabungkan 3 relasi 1:N menghasilkan perkalian kartesian jutaan baris
  var order = await context.Orders
      .Include(o => o.Items)
      .Include(o => o.ShippingHistories)
      .Include(o => o.PaymentLogs)
      .FirstOrDefaultAsync(o => o.Id == id);
  ```
* **Solusi**: Aktifkan split query secara global atau spesifik per-query:
  ```csharp
  var order = await context.Orders
      .Include(o => o.Items)
      .Include(o => o.ShippingHistories)
      .Include(o => o.PaymentLogs)
      .AsSplitQuery() // Memecah menjadi query independen per relasi
      .FirstOrDefaultAsync(o => o.Id == id);
  ```

### 2. Dapper Multi-Mapping N+1 Memory Leak
* **Kesalahan**: Mengabaikan fungsi memoization/kamus saat melakukan mapping relasi parent-child di Dapper, sehingga objek parent diinstansiasi berulang kali untuk setiap baris child.
* **Solusi**: Gunakan `Dictionary<TKey, TParent>` untuk mempertahankan referensi unik objek parent selama iterasi pipeline Dapper.

### 3. Connection Leaks Saat Menggunakan Dapper Manual Connection
* **Kesalahan**: Membuka `SqlConnection` tanpa membuangnya (*dispose*), atau melewatkan penutupan saat terjadi exception sebelum pembacaan selesai.
* **Solusi**: Selalu bungkus instansiasi koneksi dalam blok `using` atau serahkan manajemen siklus hidupnya kepada framework Dependency Injection dengan scope per HTTP request (`Scoped`).

### 4. Menghilangkan Parameter CancellationToken
* **Kesalahan**: Menjalankan query Dapper atau EF Core tanpa `CancellationToken`. Ketika klien API membatalkan request (HTTP Disconnect/Timeout), query di database tetap berjalan sampai selesai, menguras CPU server basis data.
* **Solusi**: Selalu operasikan `ct` ke `CommandDefinition` pada Dapper dan metode async EF Core (`ToListAsync(ct)`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Disable Tracking Secara Default untuk Context Read-Only**: Jika membuat query lewat EF Core, selalu set `.AsNoTracking()` atau konfigurasikan `QueryTrackingBehavior.NoTracking` pada context.
- [ ] **Gunakan TagWith untuk Tracing**: Berikan label query EF Core menggunakan `.TagWith("ModuleName_ActionName")` agar SQL dapat dilacak langsung di database profiler.
- [ ] **Konfigurasi DbContext Connection Resiliency**: Selalu gunakan `EnableRetryOnFailure()` ketika menggunakan cloud-hosted databases (Azure SQL, AWS Aurora).
- [ ] **Standardisasi CommandDefinition di Dapper**: Jangan pernah memanggil ekstensi parameter longgar. Gunakan struktur `CommandDefinition` eksplisit agar mendukung cancellation token dan query timeout.
- [ ] **Tentukan Precision pada Kolom Uang/Desimal**: Selalu tetapkan `.HasPrecision(18, 4)` secara eksplisit untuk semua field moneter/kuantitatif desimal guna menghindari pembulatan diam-diam.
- [ ] **Audit Interceptor**: Gunakan `SaveChangesInterceptor` untuk mencatat metadata audit (`CreatedAt`, `CreatedBy`, `ModifiedAt`) secara otomatis daripada menuliskannya di tiap handler.
- [ ] **Hindari TransactionScope Tanpa Pengaturan Spesifik**: Hindari penggunaan `System.Transactions.TransactionScope` yang dapat mempromosikan koneksi lokal menjadi transaksi terdistribusi (DTC) secara tidak sengaja; prioritaskan `IDbContextTransaction` lokal.

---

## 12. Hands-on Practice

Buka direktori terminal Anda dan bangun lab berikut di dalam folder: `hands-on/m02/`.

### Langkah 1: Inisialisasi Proyek dan Dependensi
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
dotnet new webapi -n AdvancedDataAccess -f net8.0
cd AdvancedDataAccess

dotnet add package Microsoft.EntityFrameworkCore.SqlServer
dotnet add package Microsoft.EntityFrameworkCore.Design
dotnet add package Dapper
```

### Langkah 2: Implementasi Custom Interceptor untuk Soft-Delete dan Auditing
Buat file `Infrastructure/Interceptors/AuditingInterceptor.cs`:

```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;

public interface ISoftDeletable
{
    bool IsDeleted { get; set; }
    DateTimeOffset? DeletedAt { get; set; }
}

public sealed class AuditingInterceptor : SaveChangesInterceptor
{
    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Context is null)
            return base.SavingChangesAsync(eventData, result, cancellationToken);

        foreach (var entry in eventData.Context.ChangeTracker.Entries())
        {
            if (entry is { State: EntityState.Deleted, Entity: ISoftDeletable softDeletable })
            {
                entry.State = EntityState.Modified;
                softDeletable.IsDeleted = true;
                softDeletable.DeletedAt = DateTimeOffset.UtcNow;
            }
        }

        return base.SavingChangesAsync(eventData, result, cancellationToken);
    }
}
```

### Langkah 3: Implementasi Custom Dapper TypeHandler
Buat file `Infrastructure/DapperHandlers/JsonObjectTypeHandler.cs`:

```csharp
using System.Data;
using System.Text.Json;
using Dapper;

public sealed class JsonObjectTypeHandler<T> : SqlMapper.TypeHandler<T> where T : class
{
    public override void SetValue(IDbDataParameter parameter, T? value)
    {
        parameter.Value = value is null ? DBNull.Value : JsonSerializer.Serialize(value);
        parameter.DbType = DbType.String;
    }

    public override T? Parse(object value)
    {
        var stringValue = value as string;
        return string.IsNullOrEmpty(stringValue) 
            ? null 
            : JsonSerializer.Deserialize<T>(stringValue);
    }
}
```

### Langkah 4: Registrasi Servis Dependency Injection
Edit file `Program.cs`:

```csharp
using System.Data;
using Dapper;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("DefaultConnection") 
    ?? "Server=localhost;Database=AdvancedDataAccessDb;Trusted_Connection=True;TrustServerCertificate=True;";

// 1. Registrasi Custom Dapper Type Handlers
SqlMapper.AddTypeHandler(new JsonObjectTypeHandler<Dictionary<string, string>>());

// 2. Registrasi EF Core dengan Execution Strategy & Interceptors
builder.Services.AddSingleton<AuditingInterceptor>();

builder.Services.AddDbContext<AppDbContext>((sp, options) =>
{
    var interceptor = sp.GetRequiredService<AuditingInterceptor>();
    options.UseSqlServer(connectionString, sqlOptions =>
    {
        sqlOptions.EnableRetryOnFailure(
            maxRetryCount: 5,
            maxRetryDelay: TimeSpan.FromSeconds(10),
            errorNumbersToAdd: null);
    })
    .AddInterceptors(interceptor);
});

// 3. Registrasi Factory Dapper
builder.Services.AddScoped<IDbConnection>(sp => new SqlConnection(connectionString));

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddControllers();

var app = builder.Build();

app.MapControllers();
app.Run();
```

---

## 13. Exercise

### Level Easy
Ubah method query Dapper berikut agar menggunakan token pembatalan (`CancellationToken`) dan eksekusi non-buffering:
```csharp
// Current Easy Code:
public async Task<IEnumerable<ProductDto>> GetAllProducts(IDbConnection conn)
{
    return await conn.QueryAsync<ProductDto>("SELECT Id, Name, Price FROM Products");
}
```
*Tugas Anda*: Implementasikan menggunakan `CommandDefinition` dengan cancellation token eksplisit dan kembalikan hasil secara efisien.

### Level Medium
Buatlah kueri menggunakan Dapper `QueryMultipleAsync` untuk mengambil ringkasan dashboard pelanggan yang memuat:
1. Data dasar profil Customer (Single Record).
2. 5 Transaksi terakhir (List of Records).
3. Total pengeluaran sepanjang masa (Single Scalar Decimal).
Eksekusi harus dilakukan dalam satu kali *network round-trip* ke basis data.

### Level Hard
Implementasikan sebuah `SaveChangesInterceptor` kustom di EF Core yang secara otomatis memindai entitas yang mengalami modifikasi dan menuliskan salinan data lama (*Original Values*) dan data baru (*Current Values*) ke dalam tabel `AuditLogs` dalam satu siklus transaksi yang sama tanpa menyebabkan *infinite recursion* pada `SaveChanges`.

---

## 14. Challenge

### Studi Kasus: Reconciler Sistem Pembayaran Transaksional Skala Besar

**Konteks**:
Sistem *Payment Settlement Engine* Anda memproses 500.000 log transaksi per batch dari berbagai payment gateway. File log ini diparsing dan harus dicocokkan (*reconciled*) dengan tabel `PendingTransactions` di database operasional.

**Kebutuhan**:
1. Buat arsitektur pemrosesan data yang mampu mencocokkan batch berisi 50.000 data per iterasi dengan memory overhead sistem tidak melebihi 256 MB.
2. Identifikasi transaksi yang:
   * **Match**: Mutasi status menjadi `Settled`.
   * **Discrepancy (Perbedaan nominal)**: Mutasi status menjadi `Disputed` beserta log deviasi nilai.
   * **Missing In System**: Entri baru yang harus di-insert massal ke tabel `UnmatchedSettlements`.
3. Skenario konkurensi: Saat worker reconciler bekerja, layanan pembayaran lain secara bersamaan dapat mencoba memperbarui status transaksi tersebut menjadi `Cancelled` oleh permintaan konsumen. Tidak boleh ada status yang tertimpa tanpa validasi (*Lost Updates Prevention*).
4. Buat rancangan teknis yang merinci kombinasi EF Core dan Dapper:
   - Di mana Anda memanfaatkan performa batching Dapper?
   - Di mana Anda memanfaatkan locking/optimistic check EF Core?
   - Bagaimana Anda mendesain penanganan rollback ketika 1 transaksi dari 50.000 transaksi mengalami kebuntuan fatal?

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic
1. Apa fungsi dari status entitas `EntityState.Detached` pada EF Core Change Tracker?
2. Bagaimana Dapper memetakan hasil kueri SQL ke tipe data objek C# tanpa memanfaatkan Expression Tree translation?
3. Apa bahaya utama dari tidak memanggil `.AsNoTracking()` pada operasi query pembacaan data dalam jumlah besar di EF Core?
4. Mengapa parameter `splitOn` diperlukan pada fungsi `QueryAsync` Dapper untuk relasi multi-mapping?
5. Apa perbedaan mendasar antara `ExecuteReaderAsync` dengan flags buffered vs unbuffered pada Dapper?

### Bagian 2: Intermediate
6. Bagaimana cara EF Core mendeteksi bahwa data telah dimodifikasi oleh proses lain saat menggunakan atribut `[Timestamp]` atau properti `.IsRowVersion()`?
7. Mengapa penggunaan `TransactionScope` bawaan .NET dapat memicu eskalasi dari transaksi lokal ke Distributed Transaction Coordinator (DTC), dan bagaimana cara menghindarinya pada .NET 8?
8. Kapan sebaiknya kita memilih `.AsSplitQuery()` dibandingkan default `.AsSingleQuery()` pada EF Core?
9. Apa perbedaan mekanika mendasar antara `DbContextFactory` dan pendaftaran langsung `AddDbContext<T>` dengan scope `Scoped` pada aplikasi multi-threaded/worker service?
10. Bagaimana cara Dapper menangani tipe data non-primitif (misal: JSON string di database yang ingin dipetakan langsung ke C# Record) secara transparan?

### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Sistem backend Anda mengalami lonjakan memori drastis (OOM Crash) ketika memproses ekspor data 2 juta baris ke format CSV melalui REST API. Endpoint tersebut menggunakan EF Core dengan query `await context.Transactions.AsNoTracking().ToListAsync()`. Di mana akar permasalahannya dan bagaimana rekonstruksi kodenya?
12. **Skenario B**: Pada sistem reservasi tiket, dua pengguna memilih bangku yang sama pada detik yang identik. Sistem menggunakan EF Core dengan Optimistic Concurrency Control. Ketika request kedua gagal menyimpan data dengan exception `DbUpdateConcurrencyException`, strategi apa yang harus diterapkan pada layer aplikasi agar pengguna kedua mendapatkan feedback yang akurat tanpa merusak data reservasi pengguna pertama?
13. **Skenario C**: Anda memiliki query reporting di Dapper yang berjalan lambat (15 detik) karena melibatkan kalkulasi agregasi pada tabel dengan 40 juta baris data. Analisis menunjukkan database CPU melonjak 100%. Jelaskan langkah diagnostik dan perbaikan arsitektur data layer yang harus dilakukan dari sisi C# dan database!

---

## 16. Summary

* **EF Core** unggul sebagai mesin domain transaksional berkat kapabilitas pelacakan mutasi (*Change Tracking*), abstraksi pemetaan relasional kompleks, dan kemampuan isolasi konsistensi melalui *Unit of Work*.
* **Dapper** memangkas lapisan abstraksi, menyediakan akses performa ultra-tinggi yang ideal untuk skenario proyeksi pembacaan (*Read Model*), pelaporan, serta mutasi massal (*bulk execution*).
* Pola **Hybrid CQRS** menjembatani jurang performa dan integritas domain: gunakan EF Core untuk Command (memvalidasi aturan bisnis dan atomisitas), gunakan Dapper untuk Query (mengeliminasi overhead tracking dan materialisasi berat).
* Skalabilitas produksi menuntut penanganan konkurensi eksplisit (*Optimistic Concurrency*), eliminasi pemborosan I/O via *Split Queries*, penerapan *Connection Resiliency*, dan penggunaan *Streaming Data Pipeline* untuk menjaga stabilitas penggunaan memori server.