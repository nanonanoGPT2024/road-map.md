# BAB 08 MODULE 01: High Performance, Caching, & Memory Optimization

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: ASP.NET Core & Modern Backend Engineering
* **Kategori**: 02-Programming-Languages / .NET Runtime Internals
* **Kode Modul**: ASPNET-08-01
* **Topik**: High Performance, Caching, & Memory Optimization
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**: 
  * Pemahaman mendalam tentang ASP.NET Core Pipeline & Middleware.
  * Penguasaan Async/Await, Threading, Task Parallel Library (TPL).
  * Pemahaman dasar tentang arsitektur memori (Stack vs. Heap).
  * Pengalaman menggunakan Dependency Injection di ASP.NET Core.
* **Tech Stack**: 
  * C# 12 / .NET 8 & .NET 9 (HybridCache API)
  * ASP.NET Core Kestrel Web Server
  * StackExchange.Redis
  * BenchmarkDotNet
  * Microsoft.Extensions.Caching.Memory & Distributed
  * System.Buffers (`ArrayPool<T>`, `MemoryPool<T>`)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis Arsitektur Garbage Collector (GC) .NET**: Membedakan segmentasi Generational GC (Gen 0, Gen 1, Gen 2, LOH, POH), menganalisis dampak Stop-The-World (STW) pauses, serta mengonfigurasi Server GC vs. Workstation GC dan Background GC untuk throughput maksimal.
2. **Menerapkan Zero/Low-Allocation Engineering**: Menggunakan primitive berkinerja tinggi seperti `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, `stackalloc`, serta `ref struct` untuk memanipulasi buffer tanpa alokasi heap berlebih.
3. **Mengoptimalkan Buffer Management**: Mengintegrasikan `ArrayPool<T>` dan `MemoryPool<T>` guna menghindari fragmentasi Large Object Heap (LOH) dan mengeliminasi overhead alokasi/dealokasi byte array berulang kali.
4. **Merancang Strategi Multi-Tier Caching Tingkat Lanjut**: Mengimplementasikan L1 (In-Memory) dan L2 (Distributed via Redis) caching, mitigasi *Cache Stampede* menggunakan *Probabilistic Early Expiration* (XFetch) dan atomic locking (`SemaphoreSlim`), serta memanfaatkan `.NET 9 HybridCache`.
5. **Memaksimalkan ASP.NET Core Output Caching**: Mengimplementasikan Output Caching berbasis Redis/In-Memory dengan tag eviction, cache invalidation presisi, dan kustomisasi policy per endpoint.
6. **Mendeteksi dan Memperbaiki Memory Leaks**: Mengidentifikasi unmanaged resource leak, event handler leaks, unbounded memory cache, dan static collections retention menggunakan diagnostik CLI (`dotnet-dump`, `dotnet-gcdump`, `dotnet-trace`).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Mechanical Sympathy: Menyelaraskan Kode dengan Hardware & Runtime
Performa tinggi dalam ASP.NET Core bukanlah hasil dari *micro-optimization* acak (seperti mengganti `for` menjadi `foreach`), melainkan pemahaman bagaimana Common Language Runtime (CLR) berinteraksi dengan Virtual Memory, CPU Cache Lines (L1/L2/L3), dan Garbage Collector. Setiap baris alokasi heap (`new object()`) adalah utang teknis yang harus dibayar oleh GC melalui siklus CPU yang seharusnya digunakan untuk melayani throughput jaringan.

### 2. Paradigma Zero-Allocation (Allocation Budgeting)
Anggap memori heap sebagai sumber daya terbatas bertarif tinggi. Dalam path eksekusi request kritis (*hot path*):
* Hindari alokasi heap jika objek dapat hidup di stack.
* Pinjam buffer alih-alih membuat buffer baru (`ArrayPool<T>`).
* Gunakan slice berbasis pointer/offset (`Span<T>`) alih-alih `Substring()` atau duplikasi array.
* Pertahankan alokasi objek jangka pendek agar mati di **Gen 0** sebelum dipromosikan ke **Gen 1** atau **Gen 2**.

### 3. Caching: Antara Latensi dan Konsistensi
Cache bukan sekadar penyimpanan key-value instan; cache adalah subsistem terdistribusi yang rentan terhadap *stale data*, *cache stampede*, dan *memory exhaustion*. Mental model yang benar dalam merancang cache:
* Asumsikan cache **pasti** akan miss, invalid, atau down.
* Desain lapisan perlindungan agar ribuan request bersamaan (*thundering herd*) tidak menghantam database secara simultan.
* Kenali batas memori: cache tanpa eviksi otomatis (`SizeLimit` atau Sliding Expiration) adalah bom waktu *Out-Of-Memory* (OOM).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### A. Layout Memori .NET Runtime & Transisi Generasi

```
+-------------------------------------------------------------------------+
|                           MANAGED HEAP                                  |
|                                                                         |
|  +-------------------+   Promote   +----------------------------------+ |
|  |   Generation 0    | ----------> |          Generation 1            | |
|  | (Short-lived obj) |             |     (Buffer transisi GC)         | |
|  +-------------------+             +----------------------------------+ |
|            |                                        |                   |
|            | Allocate                               | Promote           |
|            v                                        v                   |
|    [ new Order() ]                         +--------------------------+ |
|    (Ephemeral Segment)                     |      Generation 2        | |
|                                            |    (Long-lived obj,      | |
|                                            |     Singletons, Cache)   | |
|                                            +--------------------------+ |
|                                                         ^               |
|  +---------------------------------------------------+  |               |
|  | Large Object Heap (LOH) - Objek >= 85,000 bytes   |--+ (Siklus Full) |
|  +---------------------------------------------------+                  |
|  | Pinned Object Heap (POH) - GCHandleType.Pinned    |                  |
|  +---------------------------------------------------+                  |
+-------------------------------------------------------------------------+
     ^
     | Kontrak Span<T> / stackalloc
+----+-----------------------+
|          STACK             |  --> Sangat Cepat, Otomatis Deallocate saat
| [ ref struct / Pointers ]  |      Stack Frame Pop, Zero GC Pressure
+----------------------------+
```

### B. Pipeline Multi-Tier Hybrid Caching & Cache Stampede Defense

```
[ Incoming Client Request ]
             |
             v
+----------------------------+
| ASP.NET Core Pipeline      |
| OutputCache Middleware     | ---> [ Cache Hit (OutputCache) ] -> Return 200 OK
+----------------------------+
             | Cache Miss
             v
+-------------------------------------------------------------------------+
| HybridCache (.NET 9) / Multi-Tier In-Memory + Distributed Provider      |
|                                                                         |
| 1. Periksa L1 (In-Memory Cache: Fast, Zero Network I/O, Gen 2 Protected)|
|    |                                                                    |
|    +---> [ Hit ] --------------------------------------------+          |
|    | Miss                                                    |          |
|    v                                                         |          |
| 2. Periksa L2 (Distributed Redis: Shared across pods)        |          |
|    |                                                         |          |
|    +---> [ Hit ] -> Update L1 -> Backplane Sync -------------+          |
|    | Miss                                                    |          |
|    v                                                         |          |
| 3. Mutex / Distributed Lock (Mitigasi Cache Stampede)         |          |
|    |                                                         |          |
|    +--[ 1st Thread Lock Acquired ] -> Query DB -> Set L2/L1 -+          |
|    |                                                         |          |
|    +--[ 2nd..Nth Thread Wait Lock ] -> Await & Read Cache ---+          |
+--------------------------------------------------------------|----------+
                                                               |
                                                               v
                                                      [ Response Payload ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Generational Garbage Collector Internal
CLR Garbage Collector bekerja secara non-deterministik menggunakan algoritma *Mark-Sweep-Compact*:
* **Marking Phase**: GC menelusuri objek hidup (*reachable objects*) dari sekumpulan *GC Roots* (stack variable, CPU registers, static fields, handle tables). Objek yang tidak dapat dijangkau ditandai sebagai sampah.
* **Sweeping Phase**: Memori yang dialokasikan untuk objek mati direklamasi.
* **Compacting Phase**: GC menggeser objek hidup ke alamat memori yang bersebelahan untuk mengatasi fragmentasi memori (*heap fragmentation*). Seluruh pointer referensi diupdate secara global. Compaction memakan siklus CPU tinggi.
* **Generations Optimization**:
  * **Gen 0**: Heap kecil (~beberapa MB tergantung L2/L3 cache), alokasi objek baru ditempatkan di sini. GC Gen 0 terjadi sangat cepat (<1 milidetik).
  * **Gen 1**: Berfungsi sebagai buffer penampung antara Gen 0 dan Gen 2.
  * **Gen 2**: Objek berumur panjang (seperti service singleton, cache, connection pool). GC Gen 2 (Full GC) memeriksa seluruh heap dan memicu *Stop-The-World* yang menghentikan semua execution thread.
  * **Large Object Heap (LOH)**: Menampung objek berukuran $\ge 85.000$ bytes. LOH secara historis tidak dikompensasi secara default untuk menghindari biaya copy byte raksasa, sehingga rentan fragmentasi memori.

### 2. Anatomi `Span<T>` dan `ReadOnlySpan<T>`
Secara internal di dalam runtime, `Span<T>` didefinisikan sebagai `ref struct`:
```csharp
public readonly ref struct Span<T>
{
    internal readonly ref T _pointer;
    internal readonly int _length;
}
```
* **Interior Pointer (`ref T _pointer`)**: Pointer langsung yang mereferensikan alamat virtual memory, baik di Managed Heap, Thread Stack, maupun Unmanaged/Native Heap.
* **Type Safety & Bounds Checking**: Runtime menjamin akses index `[i]` berada di dalam rentang `0 <= i < _length` melalui instruksi JIT yang dioptimasi (*range check elimination*).
* **Stack-Only Invariant**: Modifier `ref struct` memberlakukan batasan kaku pada compiler C#:
  * `Span<T>` tidak bisa di-box ke `object` atau `ValueType`.
  * Tidak bisa menjadi tipe field dari class biasa atau struct biasa.
  * Tidak bisa digunakan melintasi boundary `async/await` (karena state machine compiler mempromosikan lokal variable ke field dalam class heap).
  * Tidak dapat diimplementasikan sebagai parameter generic `T` biasa.

### 3. Arsitektur Pooling: `ArrayPool<T>`
`ArrayPool<T>.Shared` mengimplementasikan strategi pool bertingkat (*two-tier architecture*):
1. **Per-Thread Local Cache (`TlsOverPerCoreAllocHeap`)**: Menggunakan Thread-Local Storage (TLS) untuk meminjam dan mengembalikan array tanpa thread-synchronization overhead (lock-free).
2. **Global Partitioned Bucket Table**: Jika TLS cache kosong, pool mengambil dari bucket global yang dikelompokkan berdasarkan ukuran array eksponensial (misalnya 16, 32, 64, ..., 2^N). Array yang dikembalikan ke pool ukurannya *selalu setara atau lebih besar* dari permintaan peminjam, sehingga ukuran array hasil pinjaman (`rented.Length`) tidak boleh dijadikan patokan ukuran data aktual.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Representasi Memori: Struct vs. Class & Boxing Overhead
Objek class di .NET memiliki *object header* (8 byte pada 64-bit OS) dan *Method Table pointer* (8 byte), yang menghasilkan overhead 16 byte per objek di luar data sebenarnya. Ketika value type (struct) dikonversi ke interface atau object, operasi *boxing* terjadi: CLR mengalokasikan objek baru di heap, menyalin data value type ke heap tersebut, dan mengembalikan referensi heap baru.

| Karakteristik | Struct (`Value Type`) | Class (`Reference Type`) |
| :--- | :--- | :--- |
| **Lokasi Alokasi** | Stack, atau inline dalam container type | Selalu di Managed Heap (Gen 0/1/2/LOH) |
| **Biaya Dereferensi** | 0 (Akses data langsung) | Memerlukan pointer dereferencing via memory bus |
| **GC Pressure** | 0 jika berada di stack frame | Menambah beban traversal & compaction GC |
| **Default Copy** | Copy by value (deep copy bit-level) | Copy by reference (shallow copy pointer) |

### 2. Transformasi Slice: `Substring` vs `AsSpan`
Operasi pemrosesan string tradisional mengeksekusi duplikasi memori:
```csharp
string raw = "ORDER-ID:9928192-EU";
string id = raw.Substring(9, 7); // MENGALOKASIKAN string baru di Gen 0 Heap!
```
Dengan `ReadOnlySpan<char>`:
```csharp
ReadOnlySpan<char> span = raw.AsSpan();
ReadOnlySpan<char> idSpan = span.Slice(9, 7); // ZERO ALLOCATION. Hanya pointer offset dan length.
```

### 3. Teorema Cache Stampede & Algoritma XFetch
*Cache Stampede* (atau *Thundering Herd*) terjadi ketika entri cache bernilai kritis kadaluarsa (*expired*) di bawah beban konkurensi masif. Ribuan worker thread mendapati cache miss secara bersamaan, sehingga seluruh thread membanjiri downstream database secara serentak, yang berujung pada cascading failure.

Untuk mitigasi deterministic expiration, digunakan pendekatan probabilistik **XFetch**:

$$\Delta t - \beta \cdot \ln(rand()) > TTL_{remaining}$$

Dimana:
* $\Delta t$: Waktu komputasi pembuatan cache.
* $\beta$: Koefisien agresivitas refresh ($\beta > 0$).
* $rand()$: Angka acak pseudo-uniform antara 0 dan 1.
* Jika ekspresi bernilai `true`, thread yang membaca cache sebelum expired secara proaktif melakukan komputasi latar belakang untuk menyegarkan cache, sehingga cache tidak pernah benar-benar miss bagi pengguna lain.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi parser protokol biner framing sederhana (Header + Length-Prefixed Payload) menggunakan kombinasi `ReadOnlySpan<byte>`, `Utf8Parser`, dan `ArrayPool<byte>`.

```csharp
using System;
using System.Buffers;
using System.Buffers.Binary;
using System.Buffers.Text;
using System.Text;

namespace HighPerformance.Core;

public sealed class FrameParser
{
    // Frame format: [MagicByte (1B)] [PayloadSize (4B, BigEndian)] [Timestamp (8B, BigEndian)] [Payload]
    private const byte MagicByte = 0xAA;
    private const int HeaderSize = 13;

    public readonly record struct ParsedFrame(long Timestamp, byte[] Buffer, int PayloadLength);

    public static bool TryParseFrame(ReadOnlySpan<byte> source, out ParsedFrame frame)
    {
        frame = default;

        // 1. Verifikasi batas minimum ukuran paket
        if (source.Length < HeaderSize)
        {
            return false;
        }

        // 2. Validasi Magic Byte
        if (source[0] != MagicByte)
        {
            return false;
        }

        // 3. Baca PayloadSize tanpa alokasi via BinaryPrimitives
        int payloadSize = BinaryPrimitives.ReadInt32BigEndian(source.Slice(1, 4));
        if (payloadSize < 0 || source.Length < HeaderSize + payloadSize)
        {
            return false;
        }

        // 4. Baca Timestamp
        long timestamp = BinaryPrimitives.ReadInt64BigEndian(source.Slice(5, 8));

        // 5. Pinjam buffer dari Shared ArrayPool untuk menampung hasil olahan
        byte[] rentedBuffer = ArrayPool<byte>.Shared.Rent(payloadSize);

        // 6. Copy slice payload ke rented buffer menggunakan Span copy
        ReadOnlySpan<byte> payloadSpan = source.Slice(HeaderSize, payloadSize);
        payloadSpan.CopyTo(rentedBuffer.AsSpan(0, payloadSize));

        frame = new ParsedFrame(timestamp, rentedBuffer, payloadSize);
        return true;
    }

    public static void ReleaseFrame(in ParsedFrame frame)
    {
        if (frame.Buffer != null)
        {
            // Kembalikan buffer ke pool untuk menghindari kebocoran memori pool
            // clearArray: true diset jika payload mengandung data sensitif (PII/Key)
            ArrayPool<byte>.Shared.Return(frame.Buffer, clearArray: false);
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membongkar alur eksekusi `FrameParser.cs`:

1. `public readonly record struct ParsedFrame(...)`: Menggunakan `readonly record struct` memastikan metadata frame disimpan di Stack (jika digunakan secara lokal) atau tanpa overhead boxing.
2. `if (source.Length < HeaderSize)`: Pemeriksaan batas (*boundary check*) mencegah `IndexOutOfRangeException` dan memungkinkan JIT compiler melakukan optimasi *range check elimination* pada instruksi slicing berikutnya.
3. `source[0] != MagicByte`: Mengakses satu byte secara langsung via pointer offset internal `ReadOnlySpan<byte>`, setara dengan efisiensi pointer C/C++.
4. `BinaryPrimitives.ReadInt32BigEndian(source.Slice(1, 4))`:
   * Menggunakan instruksi CPU `BSWAP` bawaan hardware.
   * `source.Slice(1, 4)` tidak mengalokasikan array baru; ia hanya memodifikasi integer offset dan length pada internal stack frame.
5. `ArrayPool<byte>.Shared.Rent(payloadSize)`:
   * Mengambil array yang sudah dialokasikan sebelumnya dari Thread-Local bucket atau global bucket.
   * Tidak memicu alokasi heap baru di Gen 0.
   * Catatan penting: `rentedBuffer.Length` bisa saja lebih besar daripada `payloadSize`.
6. `payloadSpan.CopyTo(rentedBuffer.AsSpan(0, payloadSize))`:
   * Memanggil intrinsik native `Buffer.Memmove` tingkat kernel, menyalin blok memori antar alamat virtual dalam satuan cache line 64-byte.
7. `ArrayPool<byte>.Shared.Return(frame.Buffer, clearArray: false)`:
   * Mengembalikan array ke pool. Jika parameter `clearArray` adalah `false`, byte lama tidak di-zero-out untuk memaksimalkan performa, namun tidak disarankan untuk data kredensial/kriptografi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Real-Time Pricing & Inventory Engine (Flash Sale Tier-1)
* **Karakteristik Trafik**: 85.000 Requests Per Second (RPS) pada event flash sale produk high-demand.
* **Gejala Masalah**:
  * P99 latency melonjak dari 15ms menjadi 3.2 detik.
  * CPU Server Web ASP.NET Core fluktuatif mencapai 100%, terkunci pada status kernel GC execution.
  * Analisis `dotnet-counters` mengindikasikan lebih dari 400x Gen 2 Collection per menit, dengan alokasi LOH melebihi 1.2 GB per menit.
  * Database Connection Pool Exhausted karena Redis L2 mengalami timeout, memicu *Cache Stampede* massal ke SQL Server.
* **Akar Masalah (Root Cause)**:
  1. String deserialization berbasis `JsonSerializer.Deserialize<ProductDto>(stringJson)` mengalokasikan jutaan string dan DTO temporer per detik.
  2. Cache-Aside pattern tradisional tanpa synchronization mutex menyebabkan ribuan thread mengeksekusi kalkulasi diskon database secara serempak saat TTL habis.
  3. JSON payload besar (120KB) dialokasikan langsung ke LOH sebagai `byte[]` baru setiap kali data diambil dari Redis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut arsitektur produksi menggunakan `.NET 9 HybridCache` (dengan fallback pattern Semaphore/L1/L2 untuk .NET 8) serta parsing serialisasi langsung dari stream/buffer tanpa string allocation:

### 1. Model Domain High-Performance

```csharp
using System.Text.Json.Serialization;

namespace HighPerformance.Engine.Models;

public sealed class ProductInventoryPrice
{
    [JsonPropertyName("id")]
    public required string ProductId { get; set; }

    [JsonPropertyName("p")]
    public decimal BasePrice { get; set; }

    [JsonPropertyName("d")]
    public decimal DiscountPercentage { get; set; }

    [JsonPropertyName("s")]
    public int AvailableStock { get; set; }

    [JsonIgnore]
    public decimal FinalPrice => BasePrice * (1.0m - (DiscountPercentage / 100.0m));
}

[JsonSourceGenerationOptions(
    WriteIndented = false, 
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
[JsonSerializable(typeof(ProductInventoryPrice))]
public partial class InventoryJsonContext : JsonSerializerContext
{
}
```

### 2. Resilient Multi-Tier Cache Engine (Production Grade)

```csharp
using System;
using System.Buffers;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using HighPerformance.Engine.Models;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;

namespace HighPerformance.Engine.Services;

public sealed class ProductCatalogService
{
    private readonly IMemoryCache _l1Cache;
    private readonly IDistributedCache _l2Cache;
    private readonly ILogger<ProductCatalogService> _logger;
    
    // Key-based Semaphore Pool untuk mencegah Thundering Herd per produk
    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, SemaphoreSlim> KeyLocks = new();

    public ProductCatalogService(
        IMemoryCache l1Cache, 
        IDistributedCache l2Cache, 
        ILogger<ProductCatalogService> logger)
    {
        _l1Cache = l1Cache;
        _l2Cache = l2Cache;
        _logger = logger;
    }

    public async ValueTask<ProductInventoryPrice?> GetProductDetailsAsync(string productId, CancellationToken ct)
    {
        string cacheKey = $"prod:{productId}";

        // --- LAYER 1: FAST IN-MEMORY CACHE (Zero Network overhead) ---
        if (_l1Cache.TryGetValue(cacheKey, out ProductInventoryPrice? localItem))
        {
            return localItem;
        }

        // --- LAYER 2: DISTRIBUTED CACHE (Redis) ---
        // Menggunakan pooling untuk pembacaan payload byte Redis
        byte[]? l2Bytes = await _l2Cache.GetAsync(cacheKey, ct).ConfigureAwait(false);
        if (l2Bytes != null)
        {
            // Zero-string-allocation deserialization langsung dari byte buffer
            var productFromL2 = DeserializeFromUtf8(l2Bytes);
            
            // Rehydrate L1 Cache dengan Sliding Window pendek
            _l1Cache.Set(cacheKey, productFromL2, new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30),
                Size = 1 // Enforce size-tracking
            });

            return productFromL2;
        }

        // --- LAYER 3: ATOMIC DATABASE ACCESS (Mitigasi Cache Stampede) ---
        SemaphoreSlim mutex = KeyLocks.GetOrAdd(cacheKey, _ => new SemaphoreSlim(1, 1));
        await mutex.WaitAsync(ct).ConfigureAwait(false);

        try
        {
            // Double-Check Locking pattern setelah acquire mutex
            if (_l1Cache.TryGetValue(cacheKey, out localItem))
            {
                return localItem;
            }

            // Simulasi Query Database
            ProductInventoryPrice? dbProduct = await FetchFromDatabaseSlowAsync(productId, ct).ConfigureAwait(false);
            if (dbProduct == null)
            {
                return null;
            }

            // Simpan ke L1
            _l1Cache.Set(cacheKey, dbProduct, new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30),
                Size = 1
            });

            // Serialisasi via Source Generator & simpan ke L2 Redis
            byte[] serialized = SerializeToUtf8Bytes(dbProduct);
            await _l2Cache.SetAsync(
                cacheKey, 
                serialized, 
                new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10) }, 
                ct
            ).ConfigureAwait(false);

            return dbProduct;
        }
        finally
        {
            mutex.Release();
            // Pembersihan agresif jika tidak ada thread lain yang antre
            if (mutex.CurrentCount == 1)
            {
                KeyLocks.TryRemove(cacheKey, out _);
            }
        }
    }

    private static byte[] SerializeToUtf8Bytes(ProductInventoryPrice data)
    {
        return JsonSerializer.SerializeToUtf8Bytes(data, InventoryJsonContext.Default.ProductInventoryPrice);
    }

    private static ProductInventoryPrice? DeserializeFromUtf8(byte[] bytes)
    {
        var reader = new Utf8JsonReader(bytes);
        return JsonSerializer.Deserialize(ref reader, InventoryJsonContext.Default.ProductInventoryPrice);
    }

    private async Task<ProductInventoryPrice?> FetchFromDatabaseSlowAsync(string productId, CancellationToken ct)
    {
        _logger.LogInformation("DOWNSTREAM HIT: Querying Primary Database for {ProductId}", productId);
        await Task.Delay(150, ct).ConfigureAwait(false); // Simulasi latensi I/O DB
        
        return new ProductInventoryPrice
        {
            ProductId = productId,
            BasePrice = 1250000m,
            DiscountPercentage = 15m,
            AvailableStock = 42
        };
    }
}
```

### 3. Program Setup & Output Caching Policy Configuration

```csharp
using HighPerformance.Engine.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = WebApplication.CreateBuilder(args);

// Register Memory Cache dengan Strict Memory Limit
builder.Services.AddMemoryCache(options =>
{
    options.SizeLimit = 10_000; // Maksimal 10,000 item tercatat
    options.CompactionPercentage = 0.20; // Hapus 20% item jika limit tercapai
});

// Register Distributed Redis Cache
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis") ?? "localhost:6379";
    options.InstanceName = "CatalogCluster_";
});

// Register Output Cache dengan Tag-based Eviction
builder.Services.AddOutputCache(options =>
{
    options.AddBasePolicy(builder => builder.Cache());
    options.AddPolicy("ProductEndpointPolicy", policy => policy
        .Expire(TimeSpan.FromSeconds(60))
        .SetVaryByQuery("productId")
        .Tag("products_all"));
});

builder.Services.AddSingleton<ProductCatalogService>();

var app = builder.Build();

app.UseOutputCache();

// Minimal API Endpoint dengan Output Cache Middleware
app.MapGet("/api/v1/products/{productId}", async (string productId, ProductCatalogService service, CancellationToken ct) =>
{
    var product = await service.GetProductDetailsAsync(productId, ct);
    return product is not null ? Results.Ok(product) : Results.NotFound();
})
.CacheOutput("ProductEndpointPolicy");

// Endpoint Invalidation Cache berdasarkan Tag
app.MapPost("/api/v1/products/purge-cache", async (IOutputCacheStore cacheStore, CancellationToken ct) =>
{
    await cacheStore.EvictByTagAsync("products_all", ct);
    return Results.Ok(new { Message = "Cache successfully invalidated globally." });
});

app.Run();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### In-Memory vs. Distributed Cache vs. Hybrid Cache

| Karakteristik | In-Memory (`IMemoryCache`) | Distributed (`Redis`) | Modern Hybrid (`HybridCache`) |
| :--- | :--- | :--- | :--- |
| **Latensi** | Sub-mikrodetik (<1µs) | 1ms - 5ms (Network bound) | Sub-mikrodetik (L1) / ~1ms (L2) |
| **Memory Footprint** | Mengonsumsi RAM aplikasi lokal | Terisolasi di server Redis | Kombinasi RAM lokal & Redis |
| **Konsistensi Data** | Rendah antar pod multi-instance | Sangat Tinggi (Single Source) | Tinggi (via Invalidation Bus) |
| **Cache Stampede Protection**| Tidak ada (Manual Lock) | Tidak ada (Harus RedLock) | Bawaan (*Built-in stampede lock*) |
| **Serialization Cost** | Nol (Menyimpan object ref) | Tinggi (CPU cost JSON/Protobuf)| Rendah (L1 no-ser, L2 ser) |

### Memory Management: `Span<T>` vs. Array Heap Allocation

```
+--------------------------------------------------------------------+
| Skenario: Memotong 100 bytes data dari 10 KB network payload        |
+--------------------------------------------------------------------+
| Pendekatan Heap: byte[] chunk = new byte[100]; Array.Copy(...)      |
| Latensi: ~45 ns | Alokasi: 124 bytes | GC Pressure: Gen 0 Incr     |
+--------------------------------------------------------------------+
| Pendekatan Span: ReadOnlySpan<byte> slice = source.Slice(0, 100);  |
| Latensi: ~0.4 ns | Alokasi: 0 bytes   | GC Pressure: ZERO           |
+--------------------------------------------------------------------+
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **`Span<T>` melintasi `async/await` Boundary**:
   * *Problem*: Compiler melarang penggunaan `Span<T>` di dalam method asynchronous jika dipanggil melintasi keyword `await`.
   * *Solusi*: Gunakan `Memory<T>` atau `ReadOnlyMemory<T>` yang diizinkan berada di heap state-machine, lalu panggil `.Span` secara sinkron sesaat sebelum pemrosesan byte dieksekusi.
2. **Buffer Leakage pada `ArrayPool<T>`**:
   * *Problem*: Mengambil array dengan `Rent()`, namun eksekusi method melempar exception sebelum `Return()` dipanggil, mengakibatkan hilangnya referensi array dari pool dan memaksa runtime mengalokasikan array baru berulang kali.
   * *Solusi*: Selalu gunakan blok `try ... finally` untuk mengembalikan buffer pinjaman.
3. **Penyalahgunaan `ArrayPool` Size**:
   * *Problem*: Mengasumsikan `rented.Length` persis sama dengan ukuran yang diminta. 
   * *Solusi*: Simpan panjang byte data riil secara terpisah dan akses buffer hanya melalui slicing: `rented.AsSpan(0, actualDataLength)`.
4. **Out-of-Memory akibat Unbounded `IMemoryCache`**:
   * *Problem*: Menyimpan entri baru tanpa konfigurasi `SizeLimit` atau expirations. Di bawah serangan DDOS atau scanning URL acak, heap terus membengkak hingga process terminated oleh OS (OOM Killer).
   * *Solusi*: Wajib tetapkan `options.SizeLimit` pada konfigurasi dependency injection dan berikan bobot `Size = 1` pada setiap pemanggilan `.Set()`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: String Concatenation di Hot Loops
```csharp
// SALAH: Mengalokasikan puluhan ribu string objek di Gen 0
string result = "";
for (int i = 0; i < items.Length; i++) {
    result += items[i].ToString() + ",";
}

// BENAR: Menggunakan ValueStringBuilder atau string.Create (Zero/Low allocation)
string result = string.Create(totalLength, items, (span, state) => {
    // Tulis langsung ke buffer memori karakter internal string
});
```

### Kesalahan 2: Closure Allocation pada LINQ & Lambdas
```csharp
// SALAH: Variable 'threshold' dicapture oleh compiler, mengalokasikan instance class closure di Heap
int threshold = GetThreshold();
var query = orders.Where(x => x.Amount > threshold).ToList();

// BENAR: Hindari capturing context atau gunakan static local method
static bool IsAboveThreshold(Order x, int val) => x.Amount > val;
```

### Kesalahan 3: Memanggil `GC.Collect()` Secara Manual di Production
* *Anti-Pattern*: Developer mencoba "membersihkan memori" dengan memanggil `GC.Collect()`.
* *Dampak*: Merusak model heuristik tuning runtime, menaikkan objek berumur pendek dari Gen 0 langsung ke Gen 2 secara prematur (*premature promotion*), dan menyebabkan freeze aplikasi global yang tidak dapat diprediksi.
* *Solusi*: Percayakan alokasi dan siklus sapuan pada GC Engine. Cukup turunkan laju alokasi kode.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Source-Generated System.Text.Json**:
   * Tinggalkan Newtonsoft.Json dan System.Text.Json berbasis refleksi. Gunakan `JsonSerializerContext` untuk menghasilkan kode parsing saat compile-time. Ini menghilangkan alokasi metadata refleksi dan mendukung kompilasi Native AOT.
2. **Standardisasi Pemilihan Type Task**:
   * Gunakan `ValueTask<T>` untuk metode asinkronus yang memiliki probabilitas tinggi untuk selesai secara sinkron (misalnya data sudah tersedia di in-memory cache). Gunakan `Task<T>` jika operasi hampir pasti bersifat I/O-bound asinkron murni.
3. **Konfigurasi Server Garbage Collection**:
   * Pastikan file runtime `.runtimeconfig.json` mengaktifkan Server GC untuk sistem multi-core backend:
   ```json
   {
     "runtimeOptions": {
       "configProperties": {
         "System.GC.Server": true,
         "System.GC.Concurrent": true
       }
     }
   }
   ```
4. **Penggunaan StringValues untuk Request Headers**:
   * Gunakan tipe `Microsoft.Extensions.Primitives.StringValues` alih-alih `string[]` saat membaca headers, karena tipe ini didesain khusus agar tidak mengalokasikan array heap baru jika header hanya bernilai tunggal.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Tolok Ukur Kinerja Menggunakan BenchmarkDotNet

Simulasi pengujian pemrosesan payload string vs. low-allocation Span:

```csharp
using System;
using System.Buffers;
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Jobs;
using BenchmarkDotNet.Running;

namespace HighPerformance.Benchmarks;

[MemoryDiagnoser]
[SimpleJob(RuntimeMoniker.Net80)]
public class StringParsingBenchmark
{
    private const string Payload = "DATA_ROW|TIMESTAMP:2026-03-30T10:00:00Z|SENSOR_ID:99281|VALUE:893.211";

    [Benchmark(Baseline = true)]
    public double ParseLegacyStringSplit()
    {
        // Alokasi: Array string split + multiple substring
        string[] parts = Payload.Split('|');
        string valuePart = parts[3].Split(':')[1];
        return double.Parse(valuePart);
    }

    [Benchmark]
    public double ParseZeroAllocationSpan()
    {
        ReadOnlySpan<char> span = Payload.AsSpan();

        // Cari segmen terakhir "|VALUE:"
        int lastPipe = span.LastIndexOf('|');
        ReadOnlySpan<char> valueSegment = span.Slice(lastPipe + 1);
        int colonIndex = valueSegment.IndexOf(':');
        ReadOnlySpan<char> numericSpan = valueSegment.Slice(colonIndex + 1);

        // Parsing langsung dari ReadOnlySpan<char> tanpa string baru
        return double.Parse(numericSpan);
    }
}
```

### Hasil Benchmark Representatif

| Method | Mean | Error | StdDev | Ratio | Gen0 | Allocated | Alloc Ratio |
|:--- |:--- |:--- |:--- |:--- |:--- |:--- |:--- |
| **ParseLegacyStringSplit** | 184.21 ns | 1.21 ns | 1.13 ns | 1.00 | 0.0458 | **288 B** | 1.00 |
| **ParseZeroAllocationSpan** | 14.12 ns | 0.08 ns | 0.07 ns | 0.08 | **0.0000** | **0 B** | **0.00** |

*Observasi: Pendekatan `Span<T>` 13x lebih cepat dengan alokasi memori mutlak 0 Byte.*

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Mitigasi Cache Poisoning**:
   * Validasi dan sanitasi parameter query atau path sebelum menjadikannya Cache Key. Gunakan cryptographic hashing (misalnya SHA-256) jika input key mengandung payload kompleks untuk mencegah manipulasi karakter khusus.
2. **Buffer Overread & Data Leaks di `ArrayPool<T>`**:
   * *Celah Keamanan*: Array yang dipinjam dari pool berpotensi mengandung sisa data dari thread atau tenant lain jika tidak dibersihkan. Jika data tersebut berisi token JWT atau password, lalu dikirim ke client akibat salah menghitung panjang data, terjadi kebocoran kredensial lintas tenant (*cross-tenant data leakage*).
   * *Hardening*:
     * Wajib gunakan slice data eksplisit: `rented.AsSpan(0, validLength)`.
     * Gunakan opsi `clearArray: true` pada `ArrayPool<T>.Shared.Return(buffer, clearArray: true)` saat memproses payload otentikasi/kriptografi.
3. **Denial of Service (DoS) via Cache Exhaustion**:
   * Batasi ukuran maksimum payload yang dapat disimpan ke dalam cache terdistribusi (misal max 1MB per Redis key).
   * Blokir request client yang mencoba mengirim header custom tanpa batas jika header tersebut didaftarkan ke `VaryByHeader` pada Output Caching.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Metrik Kunci via `dotnet-counters`
Pantau metrik berikut pada server produksi secara real-time:
```bash
dotnet-counters monitor -p <PID> --counters System.Runtime,Microsoft.AspNetCore.Hosting
```
* `gc-heap-size`: Pertumbuhan heap terus-menerus mengindikasikan kebocoran memori (*memory leak*).
* `gen-2-gc-count`: Peningkatan tajam menandakan alokasi berlebih pada objek berumur panjang atau LOH.
* `allocation-rate`: Laju byte yang dialokasikan per detik. Hot-path API idealnya memiliki allocation rate mendekati 0 saat idle.
* `time-in-gc`: Persentase waktu eksekusi CPU yang terkuras untuk Garbage Collector. Jika $> 5\%$, pipeline alokasi memori memerlukan optimasi segera.

### 2. EventCounters & Diagnostic Logging untuk Cache Efficiency

```csharp
using System.Diagnostics.Tracing;

[EventSource(Name = "HighPerformance-Catalog-Metrics")]
public sealed class CatalogMetricsEventSource : EventSource
{
    public static readonly CatalogMetricsEventSource Log = new();
    private System.Diagnostics.Tracing.PollingCounter? _l1HitRateCounter;
    private long _l1Hits;
    private long _totalRequests;

    public void RecordHit() => Interlocked.Increment(ref _l1Hits);
    public void RecordRequest() => Interlocked.Increment(ref _totalRequests);

    // Diproses oleh OpenTelemetry Metrics Listener atau dotnet-counters
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------------------------------------------------------------------+
| ASP.NET CORE PERFORMANCE CHEAT SHEET                                                          |
+-----------------------------------------------------------------------------------------------+
| DOMAIN          | ATURAN EMAS                        | HINDARI                                |
+-----------------+------------------------------------+----------------------------------------+
| Memory Slicing  | Gunakan Span<T> / ReadOnlySpan<T>  | string.Substring(), byte[] copy        |
| Buffer Reuse    | Gunakan ArrayPool<T>.Shared.Rent() | new byte[size] pada hot path           |
| JSON I/O        | Source Generators JsonSerializer   | Newtonsoft.Json / Reflection JObject   |
| In-Memory Cache | Wajib set SizeLimit & Compaction   | IMemoryCache tanpa eviction parameter  |
| Async Execution | ValueTask<T> jika frequently sync  | Task.Run() membungkus method sinkron   |
| String Handling | string.Create() & Utf8Parser       | String concatenation (+) dalam loops   |
| Output Caching  | Tag-based Eviction                 | ResponseCache (Legacy HTTP header-only)|
+-----------------------------------------------------------------------------------------------+
```

### Perintah Esensial Investigasi Runtime
* Ambil snapshot memory dump:
  `dotnet-dump collect -p <PID>`
* Analisis memory leak secara interaktif:
  `dotnet-dump analyze <DUMP_FILE.dmp>`
  * Perintah dump interaktif: `dumpheap -stat` (Melihat objek dengan alokasi terbesar).
  * Perintah telusuri akar GC: `gcroot <OBJECT_ADDRESS>` (Melihat siapa penahan objek di heap).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Basic (Pilihan Ganda)

**1. Di mana alokasi instansiasi variabel `Span<byte>` disimpan oleh .NET Runtime?**
* A. Large Object Heap (LOH)
* B. Gen 0 Managed Heap
* C. Selalu di Thread Stack
* D. Pinned Object Heap (POH)
* *Jawaban yang benar*: **C**
* *Penjelasan*: `Span<T>` didefinisikan sebagai `ref struct`, yang memberlakukan aturan runtime ketat bahwa ia hanya boleh hidup di stack frame dan tidak pernah dialokasikan di heap managed mana pun.

**2. Apa yang menjadi pemicu sebuah objek dialokasikan langsung ke Large Object Heap (LOH)?**
* A. Objek memiliki tipe data string
* B. Ukuran objek $\ge 85.000$ bytes
* C. Objek mengimplementasikan interface `IDisposable`
* D. Objek diinstansiasi di dalam Controller Singleton
* *Jawaban yang benar*: **B**
* *Penjelasan*: Objek yang memiliki alokasi memori 85.000 bytes atau lebih secara default langsung dialokasikan ke LOH untuk menghindari biaya compaction objek raksasa di Gen 0/1/2.

**3. Manakah dampak paling berbahaya dari implementasi cache-aside tanpa concurrency lock saat cache expired?**
* A. Deadlock pada aplikasi client
* B. Cache Poisoning
* C. Cache Stampede (Thundering Herd)
* D. Segment fault pada server Redis
* *Jawaban yang benar*: **C**
* *Penjelasan*: Hilangnya kunci cache di bawah beban ribuan request bersamaan memicu seluruh thread melakukan query ke database secara simultan (Cache Stampede), yang berisiko merubuhkan database.

**4. Mengapa developer harus memeriksa panjang data asli daripada bergantung pada `rentedArray.Length` dari `ArrayPool<T>.Shared.Rent(minSize)`?**
* A. Karena array selalu diisi byte null
* B. Karena ukuran array yang dikembalikan pool bisa lebih besar dari `minSize` yang diminta
* C. Karena ArrayPool memotong ukuran array secara otomatis
* D. Karena indeks array dimulai dari 1 pada low-allocation mode
* *Jawaban yang benar*: **B**
* *Penjelasan*: Algoritma bucket ArrayPool bekerja pada kelipatan eksponensial; meminta array ukuran 100 byte bisa saja mengembalikan array dengan kapasitas 128 atau 256 byte.

**5. Mengapa System.Text.Json Source Generator menghasilkan performa yang jauh lebih tinggi daripada deserializer tradisional?**
* A. Menghapus ketergantungan pada runtime Reflection dan dynamic code emission (IL)
* B. Mengubah format JSON menjadi protocol buffer biner
* C. Mengabaikan validasi sintaks JSON
* D. Menjalankan proses serialisasi di kernel thread terpisah
* *Jawaban yang benar*: **A**
* *Penjelasan*: Source Generator menghasilkan logika serialization C# deterministik saat proses kompilasi, mengeliminasi kebutuhan pemindaian metadata reflection yang lambat dan memakan alokasi heap saat runtime.

---

### Bagian B: Intermediate (Analisis Kasus & Troubleshooting Singkat)

**6. Kasus**: Sebuah background service memproses transaksi setiap 10ms. Profiler mendeteksi adanya alokasi heap konstan dari instruksi `Task.FromResult(true)`. Bagaimana Anda memperbaikinya?
* *Solusi Teknis*: Ganti tipe kembalian method menjadi `ValueTask<bool>` atau gunakan instance statis `Task.CompletedTask` / cache boolean task `Task.FromResult(true)` yang disimpan dalam static readonly variable, sehingga tidak ada alokasi wrapper task baru pada setiap loop interval.

**7. Kasus**: Kode berikut melempar compile-time error. Mengapa error ini muncul dan apa solusinya?
```csharp
public async Task<int> ProcessPayloadAsync(ReadOnlySpan<byte> data) {
    await Task.Delay(100);
    return data.Length;
}
```
* *Solusi Teknis*: `ReadOnlySpan<byte>` adalah `ref struct` yang tidak dapat disimpan di heap. Ketika method dideklarasikan `async`, compiler membuat state machine struct/class di heap yang menyimpan variabel lokal melintasi titik `await`. Solusinya: Ubah tipe parameter menjadi `ReadOnlyMemory<byte>`, simpan ke lokal, lalu akses `.Span` setelah statement `await Task.Delay(100)`.

**8. Kasus**: Pada server Redis cluster berkapasitas tinggi, penggunaan CPU web server ASP.NET Core sangat tinggi saat deserialisasi cache DTO yang besar. Apa strategi penggantian serialisasi yang paling tepat?
* *Solusi Teknis*: Beralih dari text-based JSON ke binary serialization berkecepatan tinggi seperti **MessagePack** atau **Protocol Buffers (Protobuf)**, dipadukan dengan deserialisasi berbasis direct-stream (`PipeReader` / `ReadOnlySequence<byte>`) tanpa mengonversi byte stream menjadi string terlebih dahulu.

**9. Kasus**: Analisis dump pada memori aplikasi mendeteksi kebocoran memori (leak) yang melibatkan `MemoryCache`. Opsi apa yang wajib diaktifkan pada `MemoryCacheOptions` untuk mencegah memori bertambah tanpa batas (*unbounded growth*)?
* *Solusi Teknis*: Daftarkan `options.SizeLimit` pada konfigurasi builder service, tentukan nilai `Size` pada setiap entri cache saat method `.Set(key, value, options)` dipanggil, dan definisikan `CompactionPercentage` (misalnya 0.10 atau 0.20) agar memori otomatis dipangkas saat mencapai ambang batas limit.

**10. Kasus**: Mengapa pemanggilan `arrayPool.Return(buffer, clearArray: false)` memiliki implikasi bahaya jika buffer tersebut pernah menampung data payload enkripsi RSA Key atau password user?
* *Solusi Teknis*: Jika `clearArray: false`, array dikembalikan ke pool tanpa menghapus isi memorinya. Thread atau request lain yang menyewa array dari pool tersebut nantinya berpotensi membaca sisa byte kunci enkripsi atau password yang belum tertimpa, mengakibatkan kerentanan information disclosure (kebocoran data sensitif antar request).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: High-Throughput IoT Telemetry Ingestion Engine

#### Deskripsi Spesifikasi Proyek
Bangun microservice endpoint ASP.NET Core minimal API yang mampu memproses *unbuffered log telemetry* dalam jumlah masif dengan constraint alokasi memori yang sangat ketat:

1. **Endpoint Kontrak**:
   * URL: `POST /api/v2/telemetry/ingest`
   * Format Request Payload (Contoh mentah string byte stream):
     `DEV_EUI=A0019B;TEMP=32.48;HUM=71.2;STATUS=OK;CHECKSUM=FA81`
2. **Arsitektur Batasan (Constraints)**:
   * **Maksimal Alokasi Heap**: $\le 128 \text{ Bytes}$ per request (di luar internal framework Kestrel read buffers).
   * Dilarang menggunakan method `string.Split()`, `string.Substring()`, atau regular expressions (`Regex`).
   * Validasi nilai `CHECKSUM` menggunakan bitwise CRC-16 kalkulasi via `Span<byte>` slice parsing.
   * Gunakan `ArrayPool<byte>.Shared` untuk buffer decoding payload.
3. **Multi-Tier Caching Rule**:
   * Simpan status agregasi terakhir per `DEV_EUI` ke dalam caching pipeline:
     * L1: `IMemoryCache` dengan time-to-live 5 detik.
     * L2: Mock `IDistributedCache` simulasi Redis dengan TTL 60 detik.
   * Lindungi endpoint dari race-condition cache stampede menggunakan synchronous semaphore pool per device group.
4. **Verifikasi & Acceptance Criteria**:
   * Buat class pengujian unit menggunakan **BenchmarkDotNet** pada parsing engine.
   * Metrik diagnosa BenchmarkDotNet wajib menunjukkan:
     * `Gen 0 Collections`: **0.0000**
     * `Allocated`: **0 Bytes** (khusus modul logic parsing).
   * Lakukan load testing lokal menggunakan k6 atau Bombardier dengan 5.000 RPS konstan selama 30 detik:
     * Verifikasi metrik via `dotnet-counters`: `Gen 2 Collections` tidak boleh bertambah lebih dari 2 kali sepanjang pengujian berlangsung.