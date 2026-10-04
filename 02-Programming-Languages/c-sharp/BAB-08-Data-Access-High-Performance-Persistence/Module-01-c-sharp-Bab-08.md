# Bab 08 Module 01: Data Access & High-Performance Persistence

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori**: `02-Programming-Languages`
* **Jalur Pembelajaran**: `c-sharp`
* **Bab**: `08 - Data Access & Persistence`
* **Modul**: `01 - Data Access & High-Performance Persistence`
* **Target Tingkat Kemahiran**: `Advanced / Staff Software Engineer`
* **Prasyarat Pengetahuan**:
  * Pemahaman mendalam tentang C# Asynchronous Programming Model (`Task`, `ValueTask`, `IAsyncEnumerable<T>`).
  * Pengetahuan arsitektur Common Language Runtime (CLR), Garbage Collection (Gen 0/1/2, LOH/POH), dan alokasi memori (`Span<T>`, `Memory<T>`).
  * Konsep dasar SQL, Transaction Isolation Levels (ACID), dan indexing pada Relational Database Management Systems (RDBMS).
  * Pengalaman menggunakan Entity Framework Core dan ADO.NET dasar.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1. **Mendiagnosis dan Menghilangkan Overhead Abstraksi ORM**: Membedah trade-off antara Entity Framework Core, Dapper (Micro-ORM), dan Native ADO.NET untuk arsitektur *low-latency/high-throughput*.
2. **Menguasai Mekanisme Internal ADO.NET & Connection Pooling**: Menganalisis *lifecycle* socket, physical connection vs logical connection, serta mitigasi *pool exhaustion*.
3. **Menerapkan Pola Zero/Low-Allocation Data Streaming**: Menggunakan `DbDataReader`, `IAsyncEnumerable<T>`, dan `ValueTask` untuk streaming dataset jutaan baris tanpa memicu *high-frequency GC pauses*.
4. **Mengeksekusi High-Performance Bulk Operations**: Mengimplementasikan ingestion data masif menggunakan protokol native seperti `SqlBulkCopy` (SQL Server) atau `NpgsqlBinaryImporter` (PostgreSQL).
5. **Mengoptimalkan Query Pipeline EF Core**: Mengonfigurasi compiled queries, no-tracking split queries, interceptors, dan batch execution guna mendekati performa raw SQL.
6. **Membangun Resilient Persistence Layer**: Mengintegrasikan transactional outbox pattern, distributed lock awareness, dan mitigasi *transient faults* dengan deterministic state tracking.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak modern, pengembang sering kali terjebak dalam dikotomi palsu: *Developer Productivity* (Entity Framework Core) versus *Pure Performance* (ADO.NET/Raw SQL). 

```
[ Abstraction Level ]
        ▲
   High │  EF Core (Change Tracking, Identity Map, LINQ Provider)
        │  ────────────────────────────────────────────────────────
        │  Dapper (Dynamic/IL Generation Object Mapper)
        │  ────────────────────────────────────────────────────────
   Low  │  ADO.NET (Manual Reader, Binary Protocols, TDS/Frontend-Backend)
        ▼
        └────────────────────────────────────────────────────────►
         Low                  Execution Throughput                High
```

Mental model seorang Staff Engineer memandang persistence layer sebagai **Data Streaming & Transformation Pipeline**, bukan sekadar abstraksi *Object-Relational Mapping*. Database engine berbicara dalam protokol biner (misal: TDS untuk SQL Server, PostgreSQL Frontend/Backend Protocol). ADO.NET mengonversi stream biner socket jaringan menjadi managed runtime data structures. 

Ketika Anda memilih tool:
* **EF Core** adalah Transaction Management & Complex Domain Model Engine. Efisiensinya bergantung pada seberapa presisi Anda mengontrol *Change Tracker* dan ekspresi LINQ.
* **Dapper** adalah High-Performance Hydration Engine yang menggunakan Dynamic Method generation (IL Emit) untuk memetakan tabular stream ke dynamic/strongly typed models.
* **ADO.NET** adalah Absolute Control Layer. Digunakan ketika Anda tidak boleh mentoleransi alokasi *boxing/unboxing*, membutuhkan bulk binary streaming langsung ke memory engine, atau memerlukan kontrol streaming per-kolom melalui `GetTextReader()` / `GetStream()`.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran eksekusi request data persistence tingkat tinggi, membandingkan tiga tier akses data dan siklus interaksinya dengan Connection Pool dan Socket Network.

```
+---------------------------------------------------------------------------------------+
|                                    MANAGED RUNTIME                                    |
|                                                                                       |
|  +------------------+      +-------------------+      +----------------------------+  |
|  |     EF Core      |      |      Dapper       |      |      Native ADO.NET        |  |
|  | - LINQ Provider  |      | - IL Emit Mapper  |      | - DbDataReader             |  |
|  | - State Manager  |      | - Query Cache     |      | - DbParameter / Commands   |  |
|  +--------+---------+      +---------+---------+      +--------------+-------------+  |
|           |                          |                               |                |
|           +--------------------+     |     +-------------------------+                |
|                                |     |     |                                          |
|                                v     v     v                                          |
|  +---------------------------------------------------------------------------------+  |
|  |                              ADO.NET Provider Core                              |  |
|  |                 (Microsoft.Data.SqlClient / Npgsql / Pomelo)                    |  |
|  +-----------------------------------------+---------------------------------------+  |
|                                            |                                          |
|                                            v                                          |
|  +---------------------------------------------------------------------------------+  |
|  |                           DbConnection Internal Pool                            |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  |  | [Pool Available: Conn A, Conn B]  <--->  [Pool In-Use: Conn C, Conn D]   |  |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  +-----------------------------------------+---------------------------------------+  |
+--------------------------------------------|------------------------------------------+
                                             | TCP Socket Stream (TDS / PG-Wire)
                                             v
+---------------------------------------------------------------------------------------+
|                                    DATABASE ENGINE                                    |
|                                                                                       |
|  +------------------------+  +-------------------------+  +------------------------+  |
|  |     Parser / Lexer     |  | Query Optimizer & Plan  |  | Storage Engine (Rows/  |  |
|  |                        |->| Cache (Sargable Pred.)  |->| Pages, WAL / LSN)      |  |
|  +------------------------+  +-------------------------+  +------------------------+  |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Connection Pool Engine
Koneksi fisik database (`Socket` berbasis TCP/IP) memerlukan *handshake* tiga arah (3-way handshake), TLS negotiation, dan database authentication context initialization. Biaya ini berkisar antara 10ms hingga 100ms+. Connection Pool mengeliminasi latensi ini dengan mempertahankan sekumpulan koneksi fisik aktif dalam managed structure:
* **`DbConnection.Open()`**: Tidak selalu membuka soket. Pool manager memeriksa queue koneksi *idle*. Jika ada, koneksi di-*reset* state-nya (misal via `sp_reset_connection` di SQL Server) dan diserahkan ke managed thread.
* **`DbConnection.Close() / Dispose()`**: Tidak menutup soket TCP. Koneksi dikembalikan ke antrean pool *idle*. Soket hanya diputus jika pool melebihi batas waktu *lifetime* atau koneksi rusak (*broken/zombie state*).

### 2. DbDataReader Hydration Internals
Saat mengeksekusi `ExecuteReaderAsync()`, engine menerima response packet stream dari server:
* **TDS/Wire deserialization**: Byte stream dibaca ke dalam internal network buffer.
* **Boxing avoidance**: Memanggil `reader.GetValue(i)` akan mengalokasikan memori karena mengembalikan `object`. Menggunakan metode strongly-typed seperti `reader.GetInt64(i)` atau `reader.GetFieldValue<T>(i)` membaca langsung primitive byte dari buffer jaringan ke CPU register atau stack, menghilangkan overhead boxing dan GC pressure.

### 3. EF Core Change Tracking Machine
`ChangeTracker` EF Core mengelola relasi objek dan mutasi status via:
* **Snapshot Tracking**: Saat entity dimuat, EF menduplikasi nilai properti ke array internal (*snapshot*). Saat `SaveChangesAsync()` dipanggil, EF memindai seluruh properti objek untuk mendeteksi perbedaan (*diffing*). Operasi ini berbiaya $O(N \times M)$ di mana $N$ adalah jumlah entity dan $M$ adalah jumlah properti.
* **Identity Map**: Menjamin satu baris tabel diwakili oleh tepat satu instance object reference dalam memori context, mencegah duplikasi referensi dan menjaga referential integrity.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Memory Footprint & GC Pressure pada Data Hydration

Dalam aplikasi web dengan skala puluhan ribu request per detik (RPS), alokasi memori saat deserialisasi data query menjadi penyebab utama degradasi performa akibat Garbage Collection (Gen 0/Gen 1 Collections).

```
Dapper / Reflection Mapper:
Network Stream ──► TDS Buffer ──► Object Instantiation (Heap) ──► Field Copy (Gen 0 GC)

Zero-Allocation Streaming ADO.NET:
Network Stream ──► TDS Buffer ──► Span<byte> Parsing ──► Direct Stack Value / Buffer Pool
```

### Sargability dan Database Optimizer Execution Plan
Sebuah query disebut **Sargable** (*Search Argument Able*) jika database engine dapat memanfaatkan index scan/seek secara efisien:
* **Non-Sargable**: `WHERE UPPER(Email) = 'USER@EXAMPLE.COM'` atau `WHERE CreateDate >= DATEADD(day, -7, GETDATE())` (pada parameter index). Ini memaksa database engine melakukan **Full Table Scan / Index Scan** karena transformasi fungsi dieksekusi per baris data.
* **Sargable**: `WHERE Email = 'user@example.com'` dengan collation case-insensitive, atau mengirimkan calculated parameter dari managed code: `WHERE CreateDate >= @CalculatedThreshold`.

### Isolation Levels, Deadlocks, dan Latching
Mekanisme penguncian data RDBMS mempengaruhi skalabilitas konkurensi:
* **Read Committed Snapshot Isolation (RCSI)**: Menghilangkan locking untuk operasi pembacaan menggunakan row-versioning di `tempdb` (SQL Server). Pembaca tidak memblokir penulis, dan penulis tidak memblokir pembaca.
* **Deadlock Detection**: Siklus saling tunggu lock (misal Transaction A mengunci Row 1 dan meminta Row 2; Transaction B mengunci Row 2 dan meminta Row 1). Database engine akan memilih satu transaksi sebagai *deadlock victim* dan memutus koneksinya.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertingkat dari *Raw ADO.NET*, *High-Performance Dapper*, hingga *Optimized EF Core* untuk membaca skenario transaksi finansial berkapasitas besar.

```csharp
// Program.cs
using System;
using System.Collections.Generic;
using System.Data;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Dapper;

namespace HighPerformancePersistence.Fundamental;

public readonly record struct FinancialLedgerRecord(
    long Id,
    Guid TransactionReference,
    decimal Amount,
    string Currency,
    DateTime CreatedAtUtc
);

// -------------------------------------------------------------
// 1. ADO.NET: Zero-Allocation Streaming Pattern
// -------------------------------------------------------------
public sealed class AdoNetHighPerformanceReader
{
    private readonly string _connectionString;

    public AdoNetHighPerformanceReader(string connectionString)
    {
        _connectionString = connectionString;
    }

    public async IAsyncEnumerable<FinancialLedgerRecord> StreamLedgerAsync(
        string currency,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        // CommandBehavior.SequentialAccess meminimalkan memory buffering internal DbDataReader
        const CommandBehavior behavior = CommandBehavior.SequentialAccess | CommandBehavior.CloseConnection;

        var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken).ConfigureAwait(false);

        await using var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT Id, TransactionReference, Amount, Currency, CreatedAtUtc
            FROM dbo.FinancialLedgers WITH (NOLOCK)
            WHERE Currency = @Currency";
        
        var param = command.CreateParameter();
        param.ParameterName = "@Currency";
        param.SqlDbType = SqlDbType.VarChar;
        param.Size = 3;
        param.Value = currency;
        command.Parameters.Add(param);

        await using var reader = await command.ExecuteReaderAsync(behavior, cancellationToken).ConfigureAwait(false);

        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
        {
            // Strongly typed accessors membaca primitive byte langsung dari TDS stream tanpa boxing
            yield return new FinancialLedgerRecord(
                Id: reader.GetInt64(0),
                TransactionReference: reader.GetGuid(1),
                Amount: reader.GetDecimal(2),
                Currency: reader.GetString(3),
                CreatedAtUtc: reader.GetDateTime(4)
            );
        }
    }
}

// -------------------------------------------------------------
// 2. EF Core: Compiled Query & No-Tracking Implementation
// -------------------------------------------------------------
public sealed class LedgerDbContext : DbContext
{
    public LedgerDbContext(DbContextOptions<LedgerDbContext> options) : base(options) { }

    public DbSet<FinancialLedgerEntity> Ledgers => Set<FinancialLedgerEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<FinancialLedgerEntity>(b =>
        {
            b.ToTable("FinancialLedgers");
            b.HasKey(x => x.Id);
            b.Property(x => x.Amount).HasPrecision(18, 4);
            b.Property(x => x.Currency).HasMaxLength(3).IsUnicode(false);
            b.HasIndex(x => x.Currency);
        });
    }
}

public class FinancialLedgerEntity
{
    public long Id { get; set; }
    public Guid TransactionReference { get; set; }
    public decimal Amount { get; set; }
    public string Currency { get; set; } = null!;
    public DateTime CreatedAtUtc { get; set; }
}

public sealed class EfCoreHighPerformanceReader
{
    // Meng-compile query ke delegasi statis, melewati parsing Expression Tree pada runtime pemanggilan
    private static readonly Func<LedgerDbContext, string, IAsyncEnumerable<FinancialLedgerRecord>> CompiledLedgerQuery =
        EF.CompileAsyncQuery((LedgerDbContext context, string currency) =>
            context.Ledgers
                .AsNoTracking() // Mengabaikan Change Tracker (Zero Allocation Identity Map)
                .Where(x => x.Currency == currency)
                .Select(x => new FinancialLedgerRecord(
                    x.Id,
                    x.TransactionReference,
                    x.Amount,
                    x.Currency,
                    x.CreatedAtUtc
                ))
        );

    private readonly IDbContextFactory<LedgerDbContext> _contextFactory;

    public EfCoreHighPerformanceReader(IDbContextFactory<LedgerDbContext> contextFactory)
    {
        _contextFactory = contextFactory;
    }

    public async IAsyncEnumerable<FinancialLedgerRecord> StreamLedgersAsync(
        string currency, 
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        await using var context = await _contextFactory.CreateDbContextAsync(cancellationToken);
        
        await foreach (var item in CompiledLedgerQuery(context, currency).WithCancellation(cancellationToken))
        {
            yield return item;
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Kode AdoNetHighPerformanceReader:
1. `CommandBehavior.SequentialAccess`: Menginstruksikan `DbDataReader` untuk membaca kolom data secara berurutan (*as a stream*). Fitur ini mematikan perilaku default ADO.NET yang memuat seluruh baris ke memory buffer lokal sebelum diekspos, mereduksi footprint RAM secara dramatis saat membaca data berskala besar.
2. `await connection.OpenAsync(cancellationToken).ConfigureAwait(false)`: Mengambil pooled connection secara asinkron tanpa memblokir thread caller, dan `ConfigureAwait(false)` mengabaikan sinkronisasi konteks GUI/ASP.NET synchronization context untuk mengurangi overhead switching.
3. `command.Parameters.Add(param)` dengan type explisit: Mencegah inferensi tipe otomatis yang sering menyebabkan type mismatch (misalnya `NVARCHAR` vs `VARCHAR`) yang memicu pembatalan index scan pada engine SQL Server.
4. `reader.GetInt64(0)`, `reader.GetDecimal(2)`: Akses langsung ke TDS reader memory buffer internal berbasis offset kolom, menghasilkan alokasi heap 0-byte (zero heap allocation) untuk tipe nilai (*value types*).
5. `yield return new FinancialLedgerRecord(...)`: Menghasilkan streaming record via `IAsyncEnumerable<T>`, memungkinkan consumer memproses record segera setelah paket jaringan pertama tiba tanpa menunggu seluruh set data termuat.

### Kode EfCoreHighPerformanceReader:
1. `EF.CompileAsyncQuery(...)`: Mengonversi LINQ Expression tree menjadi delegate native execution plan sekali saja pada inisialisasi statis. Mengeliminasi overhead runtime parsing LINQ provider pada setiap invocation loop.
2. `AsNoTracking()`: Memerintahkan EF Core untuk tidak mengalokasikan snapshot entity dalam instance `ChangeTracker`. Memangkas alokasi memori hingga ~70% dan meningkatkan throughput query execution secara signifikan.
3. `IDbContextFactory<LedgerDbContext>`: Menghindari scope instantiation yang kaku dan thread-safety issue, memungkinkan dynamic creation context yang dapat di-dispose secara instan dalam pipeline asinkron.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Skenario: Arsitektur Pembayaran Skala Global (Financial Clearing Engine)
Sebuah perusahaan pembayaran memproses transaksi kartu kredit global dengan target pemrosesan *end-of-day clearing* sebesar **100.000.000 mutasi transaksi per batch window**. 

### Bottleneck yang Terdeteksi
* Implementasi awal menggunakan standard Entity Framework Core `context.Ledgers.AddRange(entities)` dan `SaveChangesAsync()`.
* **Dampak**: 
  1. Konsumsi memori aplikasi meledak hingga >16 GB RAM dalam 5 menit pertama, memicu intensitas GC Paged Memory Exception (OOM).
  2. Throughput berada pada angka rata-rata **~1.200 records/detik**.
  3. Batch processing yang ditargetkan selesai dalam 30 menit diproyeksikan memakan waktu lebih dari 23 jam.

### Solusi Arsitektural
1. Membagi pipeline menjadi dua model: Read/Write Splitting Transactional Processing.
2. Mengganti ORM insert path dengan **Bulk Ingestion via Streaming Binary Protocol**: Menggunakan implementasi direct memory buffer streaming via ADO.NET `SqlBulkCopy` / `NpgsqlBinaryImporter`.
3. Memanfaatkan `IAsyncEnumerable<T>` yang di-pipe langsung dari source reader ke database target bulk writer melalui memory-bounded queue (`System.Threading.Channels.Channel<T>`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah engine ingestion performa tinggi menggunakan implementasi native `SqlBulkCopy` dengan streaming `IDataReader` adapter khusus untuk meminimalisasi alokasi memori ke tingkat terendah.

```csharp
// HighPerformanceBulkWriter.cs
using System;
using System.Collections.Generic;
using System.Data;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;

namespace HighPerformancePersistence.RealWorld;

public sealed class LedgerBulkPayload
{
    public long Id { get; init; }
    public Guid TransactionReference { get; init; }
    public decimal Amount { get; init; }
    public string Currency { get; init; } = "USD";
    public DateTime CreatedAtUtc { get; init; }
}

/// <summary>
/// Custom In-Memory DataReader Adapter.
/// Mengalirkan enumerable objek secara langsung ke SqlBulkCopy tanpa memuat DataTable ke RAM.
/// </summary>
public sealed class ObjectDataReaderAdapter<T> : IDataReader
{
    private readonly IEnumerator<T> _enumerator;
    private readonly IReadOnlyList<Func<T, object>> _propertyAccessors;
    private readonly IReadOnlyList<string> _propertyNames;

    public ObjectDataReaderAdapter(
        IEnumerable<T> data,
        IReadOnlyList<string> propertyNames,
        IReadOnlyList<Func<T, object>> propertyAccessors)
    {
        _enumerator = data.GetEnumerator();
        _propertyNames = propertyNames;
        _propertyAccessors = propertyAccessors;
    }

    public bool Read() => _enumerator.MoveNext();
    public object GetValue(int i) => _propertyAccessors[i](_enumerator.Current);
    public int FieldCount => _propertyAccessors.Count;
    public string GetName(int i) => _propertyNames[i];

    // Implementasi interface minimum yang disyaratkan SqlBulkCopy
    public void Dispose() => _enumerator.Dispose();
    public void Close() => Dispose();
    public bool IsClosed => false;
    public int Depth => 0;
    public DataTable GetSchemaTable() => throw new NotSupportedException();
    public bool NextResult() => false;
    public int RecordsAffected => -1;

    // Primitives accessors
    public int GetOrdinal(string name)
    {
        for (int i = 0; i < _propertyNames.Count; i++)
        {
            if (string.Equals(_propertyNames[i], name, StringComparison.OrdinalIgnoreCase))
                return i;
        }
        return -1;
    }

    public object this[int i] => GetValue(i);
    public object this[string name] => GetValue(GetOrdinal(name));
    public bool GetBoolean(int i) => (bool)GetValue(i);
    public byte GetByte(int i) => (byte)GetValue(i);
    public long GetBytes(int i, long fieldOffset, byte[]? buffer, int bufferoffset, int length) => 0;
    public char GetChar(int i) => (char)GetValue(i);
    public long GetChars(int i, long fieldoffset, char[]? buffer, int bufferoffset, int length) => 0;
    public IDataReader GetData(int i) => throw new NotSupportedException();
    public string GetDataTypeName(int i) => GetFieldType(i).Name;
    public DateTime GetDateTime(int i) => (DateTime)GetValue(i);
    public decimal GetDecimal(int i) => (decimal)GetValue(i);
    public double GetDouble(int i) => (double)GetValue(i);
    public Type GetFieldType(int i) => _propertyAccessors[i](_enumerator.Current).GetType();
    public float GetFloat(int i) => (float)GetValue(i);
    public Guid GetGuid(int i) => (Guid)GetValue(i);
    public short GetInt16(int i) => (short)GetValue(i);
    public int GetInt32(int i) => (int)GetValue(i);
    public long GetInt64(int i) => (long)GetValue(i);
    public string GetString(int i) => (string)GetValue(i);
    public int GetValues(object[] values)
    {
        int count = Math.Min(values.Length, FieldCount);
        for (int i = 0; i < count; i++) values[i] = GetValue(i);
        return count;
    }
    public bool IsDBNull(int i) => GetValue(i) == null;
}

public sealed class BulkPersistenceEngine
{
    private readonly string _connectionString;

    public BulkPersistenceEngine(string connectionString)
    {
        _connectionString = connectionString;
    }

    public async Task<long> BulkInsertLedgersAsync(
        IEnumerable<LedgerBulkPayload> transactions,
        int batchSize = 10_000,
        CancellationToken cancellationToken = default)
    {
        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken).ConfigureAwait(false);

        // SqlBulkCopyOptions.TableLock: Mengurangi transaction-log overhead secara signifikan
        // SqlBulkCopyOptions.CheckConstraints: Tetap menjaga integritas data model relasional
        var copyOptions = SqlBulkCopyOptions.TableLock | 
                          SqlBulkCopyOptions.CheckConstraints | 
                          SqlBulkCopyOptions.KeepIdentity;

        using var bulkCopy = new SqlBulkCopy(connection, copyOptions, externalTransaction: null)
        {
            DestinationTableName = "dbo.FinancialLedgers",
            BatchSize = batchSize,
            BulkCopyTimeout = 300 // 5 Menit
        };

        // Explicit Column Mapping untuk menghindari mismatch schema metadata database
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Id), "Id");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.TransactionReference), "TransactionReference");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Amount), "Amount");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Currency), "Currency");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.CreatedAtUtc), "CreatedAtUtc");

        var columnNames = new[] { "Id", "TransactionReference", "Amount", "Currency", "CreatedAtUtc" };
        var columnAccessors = new Func<LedgerBulkPayload, object>[]
        {
            x => x.Id,
            x => x.TransactionReference,
            x => x.Amount,
            x => x.Currency,
            x => x.CreatedAtUtc
        };

        using var readerAdapter = new ObjectDataReaderAdapter<LedgerBulkPayload>(
            transactions,
            columnNames,
            columnAccessors
        );

        var stopwatch = Stopwatch.StartNew();
        
        // Eksekusi streaming langsung melalui Tabular Data Stream protocol
        await bulkCopy.WriteToServerAsync(readerAdapter, cancellationToken).ConfigureAwait(false);
        
        stopwatch.Stop();
        return stopwatch.ElapsedMilliseconds;
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Berikut perbandingan komprehensif antara tiga paradigma data access C#:

| Metrik / Dimensi | Entity Framework Core 8/9 | Dapper (Micro-ORM) | Native ADO.NET (`DbDataReader`) |
| :--- | :--- | :--- | :--- |
| **Throughput (Ops/sec)** | Moderate to High (~25K ops/sec) | High (~70K ops/sec) | Maximum (~95K+ ops/sec) |
| **Heap Memory Allocation** | Tinggi (~1.5 KB - 8 KB per entity) | Rendah (~150 - 500 B per entity) | Sangat Rendah (~0 - 80 B per read) |
| **Change Tracking** | Otomatis (Full Snapshot / Proxy) | Manual / Tidak Tersedia | Manual / Tidak Tersedia |
| **Complex Relational Modeling** | Native via Fluent API / Navigation | Manual JOIN split mapping | Manual Parsing via nested loops |
| **Developer Productivity** | Sangat Tinggi (LINQ, Migrations) | Menengah (Raw SQL + Micro-mapper) | Rendah (Boilerplate tinggi) |
| **Batch Processing Optimization** | Built-in Batching sejak v7+ | Bergantung pada SQL command concat | Bulk Copy Protocols (Native TDS/PG) |
| **LINQ to SQL Overhead** | Parsing Expression Trees (~µs cost) | N/A (Menggunakan plain SQL) | N/A (Menggunakan plain SQL) |

### Kapan Menggunakan Tool yang Tepat:
* **EF Core**: Digunakan untuk **Write-heavy transactional aggregates**, Transaction Management dengan boundary kompleks (Domain-Driven Design / bounded context), dan sistem di mana schema agility dan migration safety sangat diutamakan.
* **Dapper**: Digunakan untuk **High-performance API Query Endpoints** (CQRS Read-Path), dashboard queries kompleks dengan multiple joined views, di mana performa mendekati raw SQL dibutuhkan tanpa menulis reader boilerplate berulang.
* **Native ADO.NET / Bulk Protocols**: Wajib digunakan untuk **High-volume ingestion pipelines (ETL/Clearing engines)**, batch processing di atas puluhan ribu transaksi per detik, dan sistem stream telemetri real-time yang mensyaratkan toleransi nol terhadap latency spike akibat alokasi memori.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Connection Pool Starvation (Exhaustion)
* **Kasus**: Kode asinkron yang salah membuka koneksi namun menunggu pemrosesan internal CPU yang lama atau pemanggilan eksternal HTTP sebelum menutup koneksi.
* **Manifestasi**: Exception `System.InvalidOperationException: Timeout expired. The timeout elapsed prior to obtaining a connection from the pool.`
* **Solusi**: Minimalkan masa aktif `DbConnection`. Buka koneksi tepat sebelum eksekusi SQL dan lepaskan/tutup segera menggunakan block `await using`. Jangan pernah menahan instance database connection melintasi I/O calls non-database (misal: HTTP API calls).

### 2. Parameter Sniffing
* **Kasus**: Database engine membuat execution plan berdasarkan nilai parameter pertama kali query dikompilasi. Jika parameter pertama memiliki kardinalitas data yang ekstrem (misal parameter `TenantId = 1` hanya memiliki 10 baris, sedangkan `TenantId = 2` memiliki 10.000.000 baris).
* **Solusi**: Gunakan query hints (`OPTIMIZE FOR UNKNOWN` pada SQL Server) atau dynamic query generation untuk skenario filter dengan variasi selectivity yang ekstrem.

### 3. Cartography Explosions pada Complex EF Core Queries
* **Kasus**: Memuat entity relasional One-to-Many berganda secara eager loading (`.Include(x => x.Orders).ThenInclude(o => o.Items)`).
* **Manifestasi**: Database mengeksekusi cross join eksplosif yang menghasilkan duplikasi baris jutaan kali di network wire, membebani database engine memory dan bandwidth jaringan.
* **Solusi**: Wajib menggunakan `.AsSplitQuery()` di EF Core untuk memecah SQL join query menjadi beberapa query terpisah yang lebih efisien bagi relasi 1:N dan N:M.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Implicit Client-Side Evaluation
```csharp
// SALAH: Method kustom 'ComputeTax' tidak dapat diterjemahkan ke SQL
// EF Core akan mengunduh seluruh baris tabel ke memori aplikasi
var data = context.Orders
    .Where(o => ComputeTax(o.SubTotal) > 100)
    .ToList();

// BENAR: Evaluasi dilakukan murni di SQL level
var data = context.Orders
    .Where(o => (o.SubTotal * 0.11m) > 100)
    .ToList();
```

### Mistake 2: Missing Async Cancellation Handling
```csharp
// SALAH: Token dibiarkan default, koneksi tertahan di server jika HTTP client disconnect
public async Task<List<Customer>> GetCustomersAsync() =>
    await _context.Customers.ToListAsync();

// BENAR: Teruskan CancellationToken ke database driver untuk membatalkan query di level RDBMS
public async Task<List<Customer>> GetCustomersAsync(CancellationToken ct) =>
    await _context.Customers.ToListAsync(ct);
```

### Mistake 3: Unbounded In-Memory Data Loading
```csharp
// SALAH: Memuat seluruh data log ke memori aplikasi sekaligus (OOM Disaster)
var logs = await _context.AuditLogs.ToListAsync(ct);
foreach (var log in logs) { Process(log); }

// BENAR: Stream data per baris secara asinkron dengan memory buffer flat
await foreach (var log in _context.AuditLogs.AsNoTracking().AsAsyncEnumerable().WithCancellation(ct))
{
    Process(log);
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Async API Secara Eksklusif**: Hindari `.Result` atau `.Wait()` pada panggilan database. Operasi database adalah I/O bound murni; memblokir thread thread-pool akan menyebabkan thread starvation dalam hitungan milidetik saat traffic melonjak.
2. **Deterministic Disposal Pattern**: Selalu gunakan `await using` untuk seluruh implementasi `DbConnection`, `DbCommand`, `DbDataReader`, dan `DbContext`. Ini menjamin pembersihan resource soket dan pengembalian koneksi ke connection pool segera setelah blok keluar, bahkan saat terjadi *unhandled exception*.
3. **Index Coverage Awareness**: Pastikan query mengeksekusi kolom-kolom yang masuk ke dalam *Covering Index* (memuat semua target `SELECT` via statement `INCLUDE` di RDBMS) untuk menghindari operasi tambahan *Key Lookup* / *Clustered Index Seek*.
4. **Isolate Long Transactions**: Transaksi database harus seringkas mungkin. Persiapkan data, validasi payload, dan panggil third-party API *sebelum* memanggil `BeginTransactionAsync()`. Komit atau rollback sesegera mungkin guna meminimalisasi durasi row/page locking di engine database.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Connection String Hardening untuk High Throughput
Tuning connection string untuk mengontrol pool secara tepat:
```text
Server=tcp:sql-cluster.production.net,1433;
Initial Catalog=LedgerDb;
User Id=sa_app;
Password=YourStrongPasswordHere;
Max Pool Size=200;
Min Pool Size=20;
Pooling=true;
Connect Timeout=15;
Application Intent=ReadOnly;
MultiSubnetFailover=True;
```

### 2. Mengurangi Alokasi Memori dengan Tagged String Interning
Saat membaca data kategori berulang (misal: ISO Currency Codes `"USD"`, `"EUR"`, `"IDR"`):
```csharp
// Menghindari alokasi ribuan object string yang sama di heap Gen 0
public static class CurrencyCache
{
    private static readonly Dictionary<string, string> Cache = new()
    {
        { "USD", "USD" }, { "EUR", "EUR" }, { "IDR", "IDR" }
    };

    public static string Intern(string currency) =>
        Cache.TryGetValue(currency, out var existing) ? existing : currency;
}
```

### 3. EF Core Context Pooling
Gunakan `AddDbContextPool<TContext>` di ASP.NET Core:
```csharp
builder.Services.AddDbContextPool<LedgerDbContext>(options =>
    options.UseSqlServer(connectionString), 
    poolSize: 1024
);
```
Mekanisme ini mendaur ulang instance `DbContext` yang telah di-dispose, mereduksi overhead alokasi memory heap objek per request sebesar 30-50%.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. SQL Injection Prevention Internals
SQL Injection terjadi ketika untrusted input dievaluasi sebagai interpreter code alih-alih data literal. Parameterized Query ADO.NET mengirimkan statement query dan data input secara terpisah di tingkat protokol database engine.

```csharp
// VULNERABLE: Direct SQL Concatenation (DO NOT USE)
string query = "SELECT * FROM Users WHERE UserName = '" + inputUser + "' AND Password = '" + inputPassword + "'";

// SECURE: Protocol-Level Parameterization
using var cmd = connection.CreateCommand();
cmd.CommandText = "SELECT Id, PasswordHash FROM Users WHERE UserName = @UserName";
cmd.Parameters.Add(new SqlParameter("@UserName", SqlDbType.VarChar, 50) { Value = inputUser });
```

### 2. Principle of Least Privilege pada Database Level
Kredensial yang digunakan oleh persistence layer aplikasi tidak boleh memiliki akses *DDL operations* (`ALTER`, `DROP`, `CREATE TABLE`). Pisahkan hak akses untuk operational runtime user (DML murni: `SELECT`, `INSERT`, `UPDATE`, `DELETE`) dan database migration pipeline user.

### 3. Row-Level Security (RLS) & Parameter Validation
Pastikan database multi-tenant mengisolasi data via Tenant ID validation. Jangan berasumsi tenant data aman hanya dengan filter di frontend; paksa tenancy filter menggunakan **EF Core Global Query Filters**:
```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<FinancialLedgerEntity>()
        .HasQueryFilter(e => e.TenantId == _currentTenantProvider.GetTenantId());
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Pengujian dan pemantauan performa persistensi memerlukan observabilitas terperinci di level transport data.

### 1. OpenTelemetry & Diagnostic Source Instrumentation
ADO.NET dan EF Core secara otomatis mengekspos activity tracing melalui `System.Diagnostics.DiagnosticSource`:

```csharp
// Program.cs - Setup OpenTelemetry Instrumentation
builder.Services.AddOpenTelemetry()
    .WithTracing(tracerProvider => tracerProvider
        .AddSource("Microsoft.Data.SqlClient")
        .AddEntityFrameworkCoreInstrumentation(options =>
        {
            options.SetDbStatementForText = true; // Log SQL query text
            options.IncludeConnectionParameters = false; // Sanitasi credentials
        })
        .AddOtlpExporter()
    );
```

### 2. Custom EF Core DbCommandInterceptor untuk Profiling Latensi
Gunakan Interceptor untuk menangkap query dengan durasi eksekusi tinggi (*Slow Queries*):

```csharp
public sealed class HighLatencyCommandInterceptor : DbCommandInterceptor
{
    private const long ThresholdMilliseconds = 200;

    public override async ValueTask<DbDataReader> ReaderExecutedAsync(
        DbCommand command,
        CommandExecutedEventData eventData,
        DbDataReader result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Duration.TotalMilliseconds > ThresholdMilliseconds)
        {
            // Log Slow Query ke APM / Logging platform
            Console.Error.WriteLine(
                $"[SLOW QUERY DETECTED] Duration: {eventData.Duration.TotalMilliseconds}ms " +
                $"| SQL: {command.CommandText}");
        }

        return await base.ReaderExecutedAsync(command, eventData, result, cancellationToken);
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Gunakan Connection Pooling dengan Benar**: Buka koneksi selambat mungkin, tutup secepat mungkin. Gunakan `await using` pada connection dan commands.
* **Optimasi EF Core Read Path**:
  * Selalu gunakan `.AsNoTracking()` untuk operasi read-only.
  * Gunakan `.AsSplitQuery()` untuk relasi One-to-Many berlapis.
  * Manfaatkan `EF.CompileAsyncQuery()` untuk query intensif yang dipanggil berulang kali per detik.
  * Hindari Client-side Evaluation dengan memeriksa *log warning* `QueryClientEvaluationWarning`.
* **Streaming Dataset Besar**:
  * Gunakan `IAsyncEnumerable<T>` yang dipasangkan dengan `CommandBehavior.SequentialAccess`.
  * Gunakan method type spesifik (`reader.GetInt64(i)`, `reader.GetString(i)`) alih-alih `reader.GetValue(i)` untuk menghindari *boxing* value-type.
* **Bulk Processing Rules**:
  * Jangan gunakan EF Core `AddRange` untuk ingestion di atas 5.000 records.
  * Gunakan protocol-native bulk engine (`SqlBulkCopy` / `NpgsqlBinaryImporter`) dengan table lock options untuk bypass overhead transaction logging individual.
* **Parameterize Semuanya**: Hindari konkatenasi string SQL untuk mengamankan sistem dari SQL Injection dan memungkinkan reuse execution plan di level database optimizer.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Apa fungsi utama dari `CommandBehavior.SequentialAccess` pada `DbDataReader`?**
   * A. Mengurutkan hasil query berdasarkan Clustered Index secara otomatis.
   * B. Mengalirkan data kolom demi kolom dari network socket tanpa memuat seluruh baris data ke buffer memori managed runtime.
   * C. Menjalankan query secara synchronous berurutan tanpa multi-threading.
   * D. Mencegah race condition antar concurrent transactions.

2. **Mengapa pemanggilan `.AsNoTracking()` pada EF Core meningkatkan performa read-only query?**
   * A. Karena menginstruksikan database engine untuk mematikan ACID transaction.
   * B. Karena EF Core melewati tahap pembuatan snapshot entity dan pendaftaran objek ke `ChangeTracker`.
   * C. Karena query langsung dialihkan ke cache memory internal OS.
   * D. Karena SQL query otomatis diubah menjadi binary storage protocol.

3. **Kapan kondisi sebuah database connection dikembalikan ke Connection Pool?**
   * A. Saat method `GC.Collect()` dipanggil oleh runtime engine.
   * B. Segera setelah method `Close()` atau `DisposeAsync()` dipanggil pada instance `DbConnection`.
   * C. Saat proses OS dimatikan (*graceful shutdown*).
   * D. Ketika server database mengirim sinyal TCP FIN.

4. **Metode ADO.NET manakah yang menghasilkan memory allocation terendah saat membaca nilai kolom berjenis `BIGINT`?**
   * A. `(long)reader.GetValue(0)`
   * B. `Convert.ToInt64(reader[0])`
   * C. `reader.GetInt64(0)`
   * D. `reader.GetFieldValue<object>(0)`

5. **Apa dampak langsung dari eksekusi SQL query Non-Sargable pada RDBMS?**
   * A. Query otomatis dibatalkan oleh timeout execution.
   * B. Database engine terpaksa melakukan Table Scan / Index Scan penuh karena tidak dapat mengeksekusi Index Seek.
   * C. Connection pool langsung mencapai limit maksimum (*exhausted*).
   * D. EF Core melemparkan `InvalidOperationException`.

### Soal Tingkat Lanjut (Intermediate)
6. **Apa yang menyebabkan terjadinya fenomena "Cartesian Explosion" pada query EF Core dan bagaimana mitigasinya?**
   * A. Query dengan banyak operator `.GroupBy()`; mitigasi via `.AsNoTracking()`.
   * B. Multiple `.Include()` pada relasi 1:N yang menghasilkan perkalian silang baris data; mitigasi via `.AsSplitQuery()`.
   * C. Deadlock akibat transaction isolation level serializable; mitigasi via RCSI.
   * D. Parameter sniffing pada compiled query; mitigasi via query tags.

7. **Bagaimana mekanisme internal `EF.CompileAsyncQuery` mengoptimalkan latency eksekusi query?**
   * A. Menulis stored procedure langsung ke schema database server.
   * B. Mengonversi LINQ Expression tree menjadi compiled IL delegate statis sehingga engine mengabaikan dynamic parsing tree pada setiap request.
   * C. Mengaktifkan zero-allocation protocol dengan bypass managed ADO.NET provider.
   * D. Menyimpan hasil query database secara permanen di local memory cache.

8. **Mengapa method `SqlBulkCopy` dengan opsi `TableLock` mengeksekusi ingestion data jauh lebih cepat dibandingkan individual/batched `INSERT` statements?**
   * A. Menghapus foreign key validation dan primary key constraint secara permanen.
   * B. Mengurangi logging detail transaksi di Transaction Log (Write-Ahead Log) dan menghilangkan lock contention per row.
   * C. Mengonversi data managed menjadi format XML sebelum transmisi soket.
   * D. Mengeksekusi kompresi ZIP otomatis pada protokol jaringan TDS.

9. **Kondisi manakah yang paling berpotensi menyebabkan Connection Pool Starvation di bawah beban traffic tinggi?**
   * A. Membuka `DbConnection` di dalam scoped service tanpa memanggil `GC.WaitForPendingFinalizers()`.
   * B. Membuka `DbConnection`, lalu melakukan pemanggilan eksternal microservice عبر HTTP yang lambat sebelum mengeksekusi query database.
   * C. Menjalankan query dengan opsi `.AsSplitQuery()`.
   * D. Memakai `AddDbContextPool` dengan kapasitas pool terlalu tinggi.

10. **Bagaimana implementasi `ObjectDataReaderAdapter<T>` pada kode Seksi 10 mengeliminasi alokasi Large Object Heap (LOH)?**
    * A. Mengonversi objek menjadi unmanaged memory pointer via `Marshal.AllocHGlobal`.
    * B. Mengalirkan satu demi satu instance data melalui traversal enumerator in-memory tanpa perlu memuat seluruh kumpulan data ke dalam objek `System.Data.DataTable`.
    * C. Menggunakan SIMD instructions untuk membaca array properti.
    * D. Menyimpan dataset langsung ke disk lokal menggunakan mapping file.

---

### Kunci Jawaban Kuis

1. **B** — `CommandBehavior.SequentialAccess` mengalirkan data byte secara sekuensial dari network buffer, mengabaikan loading keseluruhan baris ke memori.
2. **B** — EF Core tidak perlu mengalokasikan memori snapshot untuk tracking perubahan di `ChangeTracker`, menghemat memori heap dan CPU processing.
3. **B** — Pemanggilan `Dispose()` / `Close()` melepaskan logical connection kembali ke managed pool untuk didaur ulang, tanpa memutus physical socket connection.
4. **C** — `reader.GetInt64(0)` membaca primitif numerik langsung ke stack/register tanpa boxing ke `System.Object`.
5. **B** — Transformasi fungsi pada predicate kolom mencegah optimizer menggunakan struktur B-Tree Index untuk melakukan Index Seek efisien.
6. **B** — Eager loading relasi berganda menghasilkan perkalian relasional Cartesian; `.AsSplitQuery()` mengeksekusi SQL terpisah per relasi untuk memutus ledakan data duplikat.
7. **B** — Expression tree LINQ dievaluasi dan dikompilasi sekali ke managed executable delegate, menghilangkan overhead evaluasi tree berulang pada hot-path.
8. **B** — Minimal logging pada storage engine dan eliminasi akumulasi row locks menjadi table-level lock mempercepat throughput batch write secara drastis.
9. **B** — Menahan pool connection saat menunggu operasi latency tinggi non-database (I/O HTTP) memonopoli resource pool, menyebabkan antrean thread lain timeout.
10. **B** — Menghindari pemakaian `DataTable` yang mengalokasikan array 2D masif di heap memory; adapter mengalirkan elemen sekuensial per baris via pattern reader.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek: High-Throughput Financial Outbox Processor
Bangun sebuah console application C# (.NET 8/9) fungsional yang mensimulasikan sistem pemrosesan mutasi transaksi finansial berkapasitas tinggi dengan kriteria ketat berikut:

### Persyaratan Fungsional & Teknis:
1. **Database Setup**: Buat skrip SQL yang menyiapkan tabel:
   ```sql
   CREATE TABLE TransactionOutbox (
       Id BIGINT IDENTITY(1,1) PRIMARY KEY,
       TransactionReference UNIQUEIDENTIFIER NOT NULL,
       Payload NVARCHAR(MAX) NOT NULL,
       Status VARCHAR(20) NOT NULL, -- 'Pending', 'Processed'
       CreatedAtUtc DATETIME2 NOT NULL,
       ProcessedAtUtc DATETIME2 NULL
   );
   CREATE INDEX IX_TransactionOutbox_Status ON TransactionOutbox(Status) INCLUDE (Id, TransactionReference);
   ```
2. **Phase 1 (Bulk Producer)**:
   * Buat generator sintetis yang memproduksi **500.000 record data transaksi**.
   * Masukkan seluruh 500.000 data tersebut ke database menggunakan teknik **High-Performance Bulk Copy (Zero LOH Allocation)** dengan adapter custom. Target durasi: `< 3 detik`.
3. **Phase 2 (High-Performance Streaming Consumer)**:
   * Implementasikan consumer pipeline menggunakan `IAsyncEnumerable<T>` dengan ADO.NET `CommandBehavior.SequentialAccess`.
   * Lakukan batch update status record dari `Pending` menjadi `Processed` menggunakan parameterized batching SQL query (per chunk 1.000 record) atau table-valued parameters.
4. **Metrik & Validasi**:
   * Ukur performa menggunakan `System.Diagnostics.Stopwatch`.
   * Cetak metrik memori sebelum dan sesudah proses menggunakan:
     ```csharp
     long allocatedBytes = GC.GetAllocatedBytesForCurrentThread();
     int gen0 = GC.CollectionCount(0);
     int gen1 = GC.CollectionCount(1);
     int gen2 = GC.CollectionCount(2);
     ```
   * Verifikasi bahwa tidak ada garbage collection berlebih pada Generation 2 (Gen 2 collections harus mendekati 0).

### Kriteria Kelulusan:
* Seluruh 500.000 data berhasil dibuat, dimasukkan, dibaca, dan diperbarui statusnya tanpa terjadi exception (bebas dari error *timeout* maupun *connection exhaustion*).
* Total alokasi memory heap selama streaming batch consumer tetap stabil (*flat memory profile*, tidak mengalami linear memory growth seiring bertambahnya jumlah record).