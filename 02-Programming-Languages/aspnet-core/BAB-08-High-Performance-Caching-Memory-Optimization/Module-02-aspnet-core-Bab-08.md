# BAB 08: High-Performance Caching & Memory Optimization
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (Analyze):** Mengidentifikasi *bottleneck* alokasi memori runtime .NET, memahami alokasi Gen0/Gen1/Gen2/LOH/POH, serta mendiagnosis fenomena *Cache Stampede* dan *Thundering Herd Problem* pada sistem berskala jutaan *Request per Second* (RPS).
- **Mengevaluasi (Evaluate):** Mengukur *trade-off* latensi dan konsistensi antara *In-Process Cache (L1)*, *Distributed Cache (L2)*, dan pola sinkronisasi *Cache-Aside* versus *Read-Through/Write-Behind*.
- **Merancang & Mengimplementasikan (Create):** Membangun arsitektur *Hybrid Multi-Tiered Cache* berbasis zero-allocation serialization, memanfaatkan `ArrayPool<T>`, `Memory<T>`, algoritma mitigasi *stampede* probabilistik (*XFetch*), dan sinkronisasi backplane event-driven via Redis Pub/Sub pada .NET 8/9.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **C# Tingkat Lanjut:** `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, `IAsyncEnumerable<T>`, ref structs, dan unsafe code contexts.
- **CLR Internals:** Siklus hidup Garbage Collection (GC Server vs Workstation), alokasi tumpukan memori (*Heap* vs *Stack*), dan mekanisme *Thread Pool Starvation*.
- **Distributed Systems & Networking:** Protokol RESP (Redis Serialization Protocol), TCP socket lifecycle, serta konsistensi data eventual consistency.
- **Tooling:** Penggunaan `dotnet-trace`, `dotnet-dump`, `BenchmarkDotNet`, dan visualisasi dump via JetBrains dotMemory atau Visual Studio Diagnostic Tools.

---

### 3. Concept & Internal Architecture

#### 3.1 CLR Memory Footprint & Garbage Collection Internals
Pada throughput tinggi, pembunuh performa utama di ASP.NET Core bukanlah CPU bound computation, melainkan *Allocation Rate* yang memicu GC pause (khususnya Gen 2 Non-Concurrent Collections / Full GC).

```
+-----------------------------------------------------------------------------------+
|                                  Managed Heap                                     |
+------------------------------------+-----------------------+----------------------+
| Ephemeral Segment                  | Large Object Heap     | Pinned Object Heap   |
|  [Gen 0] -> [Gen 1] -> [Gen 2]     | (LOH: >= 85,000 bytes)| (POH: Blittable/PIN) |
| (Alloc)    (Survive)   (Long-lived)| (No Compaction by Def)| (Fixed Virtual Addr) |
+------------------------------------+-----------------------+----------------------+
```

- **Gen 0 & Gen 1 (Ephemeral):** Menampung objek berumur pendek (misal: konteks HTTP request sementara). Pembersihan sangat cepat (<1ms).
- **Gen 2:** Objek yang bertahan dari beberapa siklus GC (misal: *In-memory cache entries*, database connection pools). GC di Gen 2 memeriksa seluruh heap (*Full GC*), membekukan *managed threads* (*Stop-the-World* phase) dan mendegradasi throughput.
- **Large Object Heap (LOH):** Objek berukuran $\ge 85.000$ bytes langsung dialokasikan ke LOH. LOH tidak melakukan pemadatan (*compaction*) secara *default*, yang berujung pada fragmentasi virtual address space dan `OutOfMemoryException` meski memori fisik masih tersedia.
- **Pinned Object Heap (POH):** Disediakan sejak .NET 5 untuk buffer I/O yang dipin agar tidak mengacaukan GC compaction di heap standar.

#### 3.2 Cache Stampede & Algoritma XFetch
Ketika data cache berukuran besar dengan akses frekuensi tinggi kadaluwarsa (*TTL expiration*), ratusan *concurrent worker threads* akan mendapati *cache miss* secara bersamaan. Fenomena ini disebut **Cache Stampede** atau **Thundering Herd**.

```
Redis/L1 Cache Expiration Hit
         |
         +--> Worker Thread 1 (Cache Miss) ---------\
         +--> Worker Thread 2 (Cache Miss) ----------> [Database Overload]
         +--> Worker Thread N (Cache Miss) ---------/  (CPU 100%, Pool Exhausted)
```

Mitigasi konvensional menggunakan *Distributed Locking* (misal: Redlock) membatasi database hit ke 1 worker, tetapi memperkenalkan latensi sinkronisasi distributed lock overhead dan risiko deadlock.

Solusi tingkat produksi menggunakan pendekatan probabilistik **Optimal Probabilistic Early Expiration (XFetch)**:
Nilai dihitung ulang di background *sebelum* kedaluwarsa secara acak proporsional terhadap waktu komputasi data:

$$\Delta - \beta \cdot \ln(rand()) \cdot \delta > \text{TTL}$$

Di mana:
- $\Delta$: Waktu komputasi yang dibutuhkan untuk menghitung nilai (*read from database + serialize*).
- $\beta$: Parameter agresivitas ($\beta > 0$, default = $1.0$).
- $rand()$: Nilai floating-point seragam antara $(0, 1]$.
- $\delta$: Waktu eksekusi asinkron saat ini.

#### 3.3 Hybrid Tiered Caching Architecture
Arsitektur hybrid menggabungkan:
1. **L1 (In-Process):** Sangat cepat (sub-mikrodetik, tanpa serialisasi), terlokalisasi di memori RAM setiap node ASP.NET Core via `IMemoryCache`.
2. **L2 (Distributed):** Terpusat (latensi 1-5 milidetik via Redis/KeyDB cluster), menjaga *state persistence* lintas pod/node.
3. **Backplane Invalidation Bus:** Memanfaatkan Redis Pub/Sub untuk mengirim sinyal *Eviction Notification* ke L1 cache seluruh node ketika salah satu node melakukan *Write/Update/Delete*.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (`IDistributedCache` Default) | Pendekatan Enterprise (Hybrid Zero-Allocation) |
| :--- | :--- | :--- |
| **Pola Serialisasi** | JSON String (`System.Text.Json` / `Newtonsoft`) mengalokasikan byte array & string berulang kali | Binary zero-alloc (`MemoryPack` / `MessagePack`) atau streaming via `IBufferWriter<byte>` langsung ke pooled memory |
| **Mitigasi Stampede**| Tidak ada. Query mentah dihantamkan langsung ke DB saat TTL habis | Single-Flight (*SemaphoreSlim* lokal) digabung dengan algoritma early refresh probabilistik |
| **Lokalisasi Akses** | Setiap request melakukan round-trip jaringan via TCP socket ke Redis | 95%+ request ditangani langsung di L1 (RAM mesin lokal), 5% sisanya ke L2/Database |
| **Garbage Collector**| LOH fragmentation parah akibat payload JSON/byte berukuran besar | LOH bebas dari alokasi besar berkat penggunaan `ArrayPool<byte>.Shared` |
| **Konsistensi L1**   | Risiko *Stale Data* tinggi antar pod yang berbeda | Terjamin konsisten secara eventual (<10ms) via backplane invalidation channel |

---

### 5. How (Workflow Detail)

Alur eksekusi request pencarian data pada implementasi Hybrid Tiered Cache:

```
[HTTP Request] 
      │
      ▼
[L1 Cache Check (In-Process)] ──(HIT)──> [Return Object Reference directly (0 alloc)]
      │ (MISS)
      ▼
[Local Mutex / Single-Flight Token (per Key)]
      │
      ├───[Thread Terpilih (Leader)]
      │          │
      │          ▼
      │   [L2 Cache Check (Redis)] ──(HIT)──> [Deserialize via ArrayPool] 
      │          │                                   │
      │          │ (MISS)                            ├─> [Populate L1 Cache]
      │          ▼                                   └─> [Return Data]
      │   [Execute Database Query (Source of Truth)]
      │          │
      │          ├─> [Async Write to L2 with Tag/TTL]
      │          ├─> [Async Publish Invalidation to Bus]
      │          ├─> [Populate L1 Cache]
      │          └─> [Return Data]
      │
      └───[Thread Menunggu (Followers)]
                 │
                 ▼
          [Tunggu Leader selesai] ──> [Ambil dari L1 Cache yang sudah terisi]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Perpustakaan Modern Multi-Tier
- **L1 Cache (In-Process):** Buku catatan kecil di saku kemeja peneliti. Mengaksesnya instan tanpa perlu berdiri dari meja (latensi: nanodetik).
- **L2 Cache (Redis Cluster):** Rak buku referensi utama di lobi gedung. Perlu berjalan 1 menit untuk mengambilnya (latensi: milidetik).
- **Database (PostgreSQL/SQL Server):** Gudang arsip nasional di luar kota. Butuh pemesanan formal dan pengiriman 3 hari kerja (latensi: ratusan milidetik / detik).
- **Backplane Invalidation:** Pengeras suara lobi perpustakaan. Jika arsip diperbarui, staf mengumumkan via pelantang: *"Halaman 40 pada buku catatan Anda sudah usang, segera coret!"*

#### Diagram Arsitektur Hybrid Cache & Invalidation Backplane

```
                       +---------------------------------------+
                       |           Load Balancer               |
                       +---------------------------------------+
                                   │               │
                     Request A     │               │ Request B
                                   ▼               ▼
         +----------------------------------+     +----------------------------------+
         | ASP.NET Core Instance #1         |     | ASP.NET Core Instance #2         |
         |  +----------------------------+  |     |  +----------------------------+  |
         |  | L1 Cache (IMemoryCache)    |  |     |  | L1 Cache (IMemoryCache)    |  |
         |  +----------------------------+  |     |  +----------------------------+  |
         |  | MemoryPool / ArrayPool     |  |     |  | MemoryPool / ArrayPool     |  |
         |  +----------------------------+  |     |  +----------------------------+  |
         |  | Backplane Subscriber Node  |  |     |  | Backplane Subscriber Node  |  |
         +----------------------------------+     +----------------------------------+
                        │       ▲                             │       ▲
          Redis Read/   │       │ Pub/Sub Invalidation        │       │ Pub/Sub Invalidation
          Write Pipeline│       │ Event Channel               │       │ Event Channel
                        ▼       │                             ▼       │
         +---------------------------------------------------------------------------+
         |                           Redis Enterprise Cluster                        |
         |  +-------------------------------------+-------------------------------+  |
         |  | L2 Distributed Data Store (RESP3)   | Pub/Sub Backplane Channel     |  |
         |  +-------------------------------------+-------------------------------+  |
         +---------------------------------------------------------------------------+
                                          │ (Cache Miss Total)
                                          ▼
                         +---------------------------------+
                         | Database (SQL Server / Postgres)|
                         +---------------------------------+
```

---

### 7. Implementation: Simple & Practical Example

#### 7.1 Simple Example: High-Performance Pooled Buffer Memory Stream
Menghindari LOH saat memproses serialisasi stream berukuran besar menggunakan `ArrayPool<byte>`.

```csharp
using System.Buffers;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

public sealed class PooledPayloadSerializer
{
    private const int MinimumBufferSize = 65_536; // 64 KB

    public static async ValueTask<byte[]> SerializeZeroAllocAsync<T>(T data, CancellationToken ct = default)
    {
        // Menyewa array dari pool alih-alih mengalokasikan byte array baru di Managed Heap
        byte[] rentedBuffer = ArrayPool<byte>.Shared.Rent(MinimumBufferSize);

        try
        {
            using var memoryStream = new MemoryStream(rentedBuffer);
            await JsonSerializer.SerializeAsync(memoryStream, data, cancellationToken: ct);
            
            // Potong data persis sesuai panjang payload
            int payloadLength = (int)memoryStream.Position;
            byte[] exactPayload = new byte[payloadLength];
            System.Buffer.BlockCopy(rentedBuffer, 0, exactPayload, 0, payloadLength);

            return exactPayload;
        }
        finally
        {
            // WAJIB mengembalikan buffer ke pool untuk menghindari pool leak
            ArrayPool<byte>.Shared.Return(rentedBuffer, clearArray: true);
        }
    }
}
```

#### 7.2 Practical Production Example: Hybrid Cache Engine with Stampede Shield & Backplane Invalidation

Simulasi komponen komprehensif tingkat industri.

##### Kontrak & Interface
```csharp
using System;
using System.Threading;
using System.Threading.Tasks;

namespace Enterprise.Caching.Core;

public interface IHybridCacheService
{
    ValueTask<T?> GetOrSetAsync<T>(
        string key, 
        Func<CancellationToken, ValueTask<T>> factory, 
        TimeSpan? l1Expiration = null, 
        TimeSpan? l2Expiration = null, 
        CancellationToken ct = default);

    Task InvalidateAsync(string key, CancellationToken ct = default);
}
```

##### Implementasi Engine
```csharp
using System;
using System.Buffers;
using System.Collections.Concurrent;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace Enterprise.Caching.Core;

public sealed class EnterpriseHybridCacheService : IHybridCacheService, IDisposable
{
    private readonly IMemoryCache _l1Cache;
    private readonly IConnectionMultiplexer _redis;
    private readonly IDatabase _l2Db;
    private readonly ISubscriber _subscriber;
    private readonly ILogger<EnterpriseHybridCacheService> _logger;
    private const string ChannelName = "cache:invalidation:channel";

    // Single-Flight synchronization per key
    private static readonly ConcurrentDictionary<string, SemaphoreSlim> KeyLocks = new();

    public EnterpriseHybridCacheService(
        IMemoryCache l1Cache,
        IConnectionMultiplexer redis,
        ILogger<EnterpriseHybridCacheService> logger)
    {
        _l1Cache = l1Cache ?? throw new ArgumentNullException(nameof(l1Cache));
        _redis = redis ?? throw new ArgumentNullException(nameof(redis));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _l2Db = _redis.GetDatabase();
        _subscriber = _redis.GetSubscriber();

        // Subscribe to backplane invalidation bus
        _subscriber.Subscribe(RedisChannel.Literal(ChannelName), (channel, message) =>
        {
            if (message.HasValue)
            {
                string evictedKey = message.ToString();
                _l1Cache.Remove(evictedKey);
                _logger.LogDebug("Evicted L1 cache for key: {Key} via backplane", evictedKey);
            }
        });
    }

    public async ValueTask<T?> GetOrSetAsync<T>(
        string key,
        Func<CancellationToken, ValueTask<T>> factory,
        TimeSpan? l1Expiration = null,
        TimeSpan? l2Expiration = null,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(key);

        // 1. Coba ambil dari L1 Memory Cache (0 allocation, synchronous lookup)
        if (_l1Cache.TryGetValue(key, out T? l1Value))
        {
            _logger.LogTrace("L1 Cache Hit for key: {Key}", key);
            return l1Value;
        }

        // 2. Terapkan Single-Flight Locking (Mencegah Stampede ke L2 dan Database)
        SemaphoreSlim keyLock = KeyLocks.GetOrAdd(key, _ => new SemaphoreSlim(1, 1));
        await keyLock.WaitAsync(ct).ConfigureAwait(false);

        try
        {
            // Double-checked locking pada L1
            if (_l1Cache.TryGetValue(key, out l1Value))
            {
                return l1Value;
            }

            // 3. Coba ambil dari L2 Distributed Cache (Redis)
            RedisValue l2Value = await _l2Db.StringGetAsync(key).ConfigureAwait(false);
            if (!l2Value.IsNullOrEmpty)
            {
                _logger.LogTrace("L2 Cache Hit for key: {Key}", key);
                T deserializedFromL2 = DeserializeFromRedis<T>(l2Value);
                
                SetL1(key, deserializedFromL2, l1Expiration);
                return deserializedFromL2;
            }

            // 4. Cache Miss total: Eksekusi factory (Source of Truth: Database/External API)
            _logger.LogInformation("L1 & L2 Cache Miss for key: {Key}. Fetching from Source...", key);
            T factoryValue = await factory(ct).ConfigureAwait(false);

            if (factoryValue is not null)
            {
                // Set L2 asynchronously
                await SetL2Async(key, factoryValue, l2Expiration).ConfigureAwait(false);
                
                // Set L1
                SetL1(key, factoryValue, l1Expiration);
            }

            return factoryValue;
        }
        finally
        {
            keyLock.Release();
            // Cleanup lock jika tidak ada thread lain yang menunggu untuk menghemat memori
            if (keyLock.CurrentCount == 1 && KeyLocks.TryRemove(key, out var removedLock))
            {
                // Lock berhasil diremove, tidak perlu dispose karena semaphore masih safe
            }
        }
    }

    public async Task InvalidateAsync(string key, CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(key);

        // 1. Evict L1 lokal
        _l1Cache.Remove(key);

        // 2. Evict L2 (Redis)
        await _l2Db.KeyDeleteAsync(key).ConfigureAwait(false);

        // 3. Broadcast ke seluruh instans aplikasi via Redis Pub/Sub backplane
        await _subscriber.PublishAsync(RedisChannel.Literal(ChannelName), key).ConfigureAwait(false);

        _logger.LogInformation("Invalidated cache key: {Key} across all clusters", key);
    }

    private void SetL1<T>(string key, T value, TimeSpan? expiration)
    {
        var options = new MemoryCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = expiration ?? TimeSpan.FromMinutes(2),
            Size = 1 // Basic sizing metric untuk proteksi memory pressure
        };
        _l1Cache.Set(key, value, options);
    }

    private async Task SetL2Async<T>(string key, T value, TimeSpan? expiration)
    {
        byte[] rentBuffer = ArrayPool<byte>.Shared.Rent(32_768);
        try
        {
            using var ms = new MemoryStream(rentBuffer);
            JsonSerializer.Serialize(ms, value);
            var payload = new ReadOnlyMemory<byte>(rentBuffer, 0, (int)ms.Position);

            TimeSpan ttl = expiration ?? TimeSpan.FromMinutes(10);
            await _l2Db.StringSetAsync(key, payload, ttl).ConfigureAwait(false);
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(rentBuffer);
        }
    }

    private static T DeserializeFromRedis<T>(RedisValue redisValue)
    {
        ReadOnlySpan<byte> span = (byte[])redisValue!;
        return JsonSerializer.Deserialize<T>(span)!;
    }

    public void Dispose()
    {
        _subscriber.Unsubscribe(RedisChannel.Literal(ChannelName));
    }
}
```

---

### 8. Real World Case Study: E-Commerce Flash Sale Architecture

#### 8.1 Latar Belakang & Beban Sistem
Sebuah platform E-Commerce berskala nasional mengadakan program *Flash Sale*.
- **Metrik Trafik:** 150.000 RPS terdistribusi ke 20 pod ASP.NET Core di Azure Kubernetes Service (AKS).
- **Target Entitas:** Data `FlashSaleProductCatalog` (Stok, Diskon, Metadata Produk).
- **Masalah Sebelum Optimasi:** Redis cluster terhambat oleh bandwidth saturated (10 Gbps network pipe terisi penuh oleh payload JSON serialisasi katalog), database PostgreSQL mengalami *connection exhaustion* (5000+ pooled connections hang), response time P99 melonjak dari 15ms menjadi 12.000ms.

#### 8.2 Intervensi Arsitektur Produksi
1. **Adopsi Hybrid Multi-Tier:** Mengimplementasikan modul hybrid di atas. Akses katalog dilayani oleh L1 (`IMemoryCache`) sebesar 98% (Local node access). Network I/O ke Redis turun 94%.
2. **Mitigasi Stampede probabilistik:** Implementasi background early refresh via XFetch. Database PostgreSQL hanya menerima 1 query per 30 detik untuk pembaharuan snapshot data.
3. **Format Serialisasi Binary:** Migrasi dari JSON menjadi binary protobuf/MemoryPack, mengompres ukuran payload Redis dari 120 KB menjadi 14 KB. Menghilangkan alokasi LOH secara permanen.

#### 8.3 Hasil Benchmark Produksi

| Metrik Produksi | Sebelum Optimasi | Pasca Arsitektur Hybrid | Delta |
| :--- | :--- | :--- | :--- |
| **P99 Latency** | 12.450 ms | 3,8 ms | **-99.96%** |
| **Database CPU Core Load** | 98% (32 Cores) | 4% (32 Cores) | **-95.9%** |
| **GC Gen 2 Pause per Menit**| 48 pause (Avg 120ms) | 0 pause | **Eliminasi Total** |
| **Bandwidth Redis** | 9,8 Gbps | 240 Mbps | **-97.5%** |

---

### 9. Trade-offs: Architectural Matrix

```
                             CONSISTENCY
                                 ▲
                                 │       [Strong Consistency]
                                 │       DB Direct / Pessimistic Lock
                                 │
                                 │
                                 │             [Event-Driven Hybrid]
                                 │             (Current Design)
                                 │
                                 │
  [Pure L1 No-Backplane]         │
  (Ultra-Low Latency,            │
   Eventual Inconsistent)        │
                                 │
  ───────────────────────────────┴──────────────────────────────► PERFORMANCE &
  LOW                                                     HIGH     LOW-LATENCY
```

| Tipe Pendekatan | Latensi Rata-Rata | Skalabilitas | Kompleksitas Kode | Estimasi Biaya Infrastruktur | Tingkat Konsistensi |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Database Direct** | Tinggi (15-150ms) | Rendah (Database Bottleneck)| Sangat Rendah | Sangat Mahal (Scaling DB vertical) | Kuat (ACID) |
| **Pure Redis (L2)** | Sedang (2-6ms) | Tinggi | Rendah | Sedang (Network & Memory Redis) | Tinggi |
| **Pure MemoryCache (L1)**| Sangat Rendah (<0.1ms)| Sangat Tinggi | Sangat Rendah | Paling Murah | Sangat Rendah (State Divergence) |
| **Enterprise Hybrid Multi-Tier**| Ultra-Rendah (<0.2ms)| Maksimal (>1M RPS) | Tinggi | Efisien (Menghemat Redis tier) | Eventual (<10ms via Backplane) |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: String Concatenation & Allocation pada Cache Key
*Bad:*
```csharp
string key = "tenant:" + tenantId + ":user:" + userId + ":date:" + DateTime.UtcNow.ToString();
```
*Mengapa fatal:* String format/concatenation di hot path menghasilkan alokasi string baru di Gen 0 secara masif (jutaan string dialokasikan per menit).
*Solusi:* Manfaatkan zero-alloc string interpolation atau format struct:
```csharp
Span<char> buffer = stackalloc char[128];
bool success = buffer.TryWrite($"tenant:{tenantId}:user:{userId}", out int charsWritten);
string key = string.Create(charsWritten, (tenantId, userId), static (span, state) => 
{
    span.TryWrite($"tenant:{state.tenantId}:user:{state.userId}", out _);
});
```

#### Kesalahan 2: Mengabaikan Sizing Limit pada `IMemoryCache`
*Bad:* Menginstansiasi `new MemoryCache(new MemoryCacheOptions())` tanpa mengatur batas `SizeLimit`.
*Gejala Produksi:* Saat lonjakan traffic, jumlah entitas tak terkontrol hingga memicu OS membunuh proses (`OOMKilled` di Kubernetes Container).
*Solusi:* Wajib konfigurasikan `SizeLimit` dan tentukan `Size` pada setiap entri cache.

#### Kesalahan 3: Sync-Over-Async pada Redis Client (`.Result` / `.Wait()`)
*Bad:*
```csharp
var data = _redisDatabase.StringGetAsync(key).Result;
```
*Gejala Produksi:* **Thread Pool Starvation**. Redis client memproses callback socket melalui I/O Completion Ports (IOCP). Pemanggilan `.Result` memblokir worker thread CLR, sehingga tidak ada thread tersisa untuk menangani I/O responses lain, menyebabkan cascade timeout.

---

### 11. Best Practices & Production Checklist

- [ ] **L1 Entry Size Constraints:** Pastikan `IMemoryCacheOptions.SizeLimit` ditentukan secara eksplisit pada container environment.
- [ ] **GC Server Mode:** Pastikan runtime `.csproj` diatur ke Server GC: `<ServerGarbageCollection>true</ServerGarbageCollection>`.
- [ ] **Redis Connection Optimization:** Gunakan instans `ConnectionMultiplexer` singleton. Jangan pernah membuat instans per-request!
- [ ] **Zero LOH Allocations:** Terapkan parsing payload yang melebihi 85.000 bytes menggunakan streaming parser (`IAsyncEnumerable<T>`, `PipeReader`, atau `ReadOnlySequence<byte>`).
- [ ] **Jittered Expiration:** Selalu tambahkan durasi acak (*jitter*) pada TTL cache (+/- 10-20%) untuk mencegah kedaluwarsa massal pada detik yang sama:
  ```csharp
  var jitter = TimeSpan.FromSeconds(Random.Shared.Next(5, 30));
  var expiration = baseTtl + jitter;
  ```
- [ ] **Observability:** Emit counter OpenTelemetry untuk memonitor metrik:
  - `cache.hits` (label: l1, l2)
  - `cache.misses`
  - `cache.evictions`
  - `cache.serialization.duration`

---

### 12. Hands-on Practice: Membangun Hybrid Cache Engine

Simpan seluruh kode berikut di direktori: `hands-on/m02/`

#### Langkah 1: Buat Struktur Project
```bash
mkdir -p hands-on/m02/HybridCacheLab
cd hands-on/m02/HybridCacheLab
dotnet new webapi -minimal -f net8.0
dotnet add package StackExchange.Redis
dotnet add package Microsoft.Extensions.Caching.Memory
```

#### Langkah 2: Buat File `Engine.cs`
Salin kode berikut ke `hands-on/m02/HybridCacheLab/Engine.cs`:
```csharp
using System.Buffers;
using System.Collections.Concurrent;
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;
using StackExchange.Redis;

namespace HybridCacheLab;

public interface ICacheEngine
{
    ValueTask<T> GetAsync<T>(string key, Func<CancellationToken, ValueTask<T>> factory, CancellationToken ct);
    Task EvictAsync(string key);
}

public class FastCacheEngine : ICacheEngine
{
    private readonly IMemoryCache _l1;
    private readonly IDatabase _l2;
    private readonly ISubscriber _bus;
    private static readonly ConcurrentDictionary<string, SemaphoreSlim> Locks = new();
    private const string BusChannel = "cache:sync";

    public FastCacheEngine(IMemoryCache l1, IConnectionMultiplexer redis)
    {
        _l1 = l1;
        _l2 = redis.GetDatabase();
        _bus = redis.GetSubscriber();

        _bus.Subscribe(RedisChannel.Literal(BusChannel), (_, key) =>
        {
            _l1.Remove(key.ToString());
        });
    }

    public async ValueTask<T> GetAsync<T>(string key, Func<CancellationToken, ValueTask<T>> factory, CancellationToken ct)
    {
        if (_l1.TryGetValue(key, out T? val) && val is not null)
            return val;

        var lockObj = Locks.GetOrAdd(key, _ => new SemaphoreSlim(1, 1));
        await lockObj.WaitAsync(ct);
        try
        {
            if (_l1.TryGetValue(key, out val) && val is not null)
                return val;

            var l2Val = await _l2.StringGetAsync(key);
            if (l2Val.HasValue)
            {
                var deserialized = JsonSerializer.Deserialize<T>((byte[])l2Val!)!;
                _l1.Set(key, deserialized, TimeSpan.FromSeconds(30));
                return deserialized;
            }

            var fresh = await factory(ct);
            var serialized = JsonSerializer.SerializeToUtf8Bytes(fresh);
            await _l2.StringSetAsync(key, serialized, TimeSpan.FromMinutes(2));
            _l1.Set(key, fresh, TimeSpan.FromSeconds(30));
            return fresh;
        }
        finally
        {
            lockObj.Release();
        }
    }

    public async Task EvictAsync(string key)
    {
        _l1.Remove(key);
        await _l2.KeyDeleteAsync(key);
        await _bus.PublishAsync(RedisChannel.Literal(BusChannel), key);
    }
}
```

#### Langkah 3: Modifikasi `Program.cs`
Ganti seluruh isi `Program.cs` dengan implementasi endpoint verifikasi:
```csharp
using HybridCacheLab;
using Microsoft.Extensions.Caching.Memory;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddMemoryCache(opt => opt.SizeLimit = 10_000);
builder.Services.AddSingleton<IConnectionMultiplexer>(sp => 
    ConnectionMultiplexer.Connect("localhost:6379,abortConnect=false"));
builder.Services.AddSingleton<ICacheEngine, FastCacheEngine>();

var app = builder.Build();

app.MapGet("/products/{id:int}", async (int id, ICacheEngine cache, CancellationToken ct) =>
{
    var product = await cache.GetAsync($"product:{id}", async token =>
    {
        // Simulasi akses database I/O delay
        await Task.Delay(200, token);
        return new Product(id, $"Product-{id}", 150_000, DateTime.UtcNow);
    }, ct);

    return Results.Ok(product);
});

app.MapPost("/products/{id:int}/evict", async (int id, ICacheEngine cache) =>
{
    await cache.EvictAsync($"product:{id}");
    return Results.NoContent();
});

app.Run();

public record Product(int Id, string Name, decimal Price, DateTime LastRetrieved);
```

#### Langkah 4: Uji Coba Multi-Node
1. Jalankan Redis lokal:
   ```bash
   docker run -d --name test-redis -p 6379:6379 redis:alpine
   ```
2. Jalankan dua instans aplikasi pada port berbeda:
   ```bash
   # Terminal 1
   dotnet run --urls="http://localhost:5001"
   
   # Terminal 2
   dotnet run --urls="http://localhost:5002"
   ```
3. Lakukan request ke `http://localhost:5001/products/1` (Latency ~200ms - Database hit).
4. Lakukan request ke `http://localhost:5002/products/1` (Latency ~2ms - Redis hit).
5. Lakukan request ulang ke `http://localhost:5001/products/1` (Latency <1ms - L1 Cache hit).
6. Kirim request invalidasi:
   ```bash
   curl -X POST http://localhost:5001/products/1/evict
   ```
7. Periksa bahwa L1 Cache di `http://localhost:5002/products/1` secara otomatis ter-evict melalui message bus.

---

### 13. Exercises

#### Level Easy
Ubah implementasi `EnterpriseHybridCacheService.SetL2Async` agar mengimplementasikan jittering acak antara 5 hingga 15 detik pada nilai TTL untuk mencegah cache expiration serentak.

#### Level Medium
Gantilah alur serialisasi default `System.Text.Json` dengan mekanisme streaming menggunakan `Utf8JsonWriter` yang menulis langsung ke objek `IBufferWriter<byte>` yang memanfaatkan buffer dari `ArrayPool<byte>.Shared`.

#### Level Hard
Rancang dan implementasikan algoritma *XFetch* murni di dalam method `GetOrSetAsync`. Jika kalkulasi XFetch menyatakan bahwa cache harus dihitung ulang (early expiration hit), trigger sebuah background worker thread (`Task.Run` atau `UnsafeQueueUserWorkItem`) untuk mengeksekusi factory dan memperbarui L1/L2, sementara request saat ini tetap langsung menerima data lama (*stale data*) dengan nol latensi.

---

### 14. Real-World Architectural Challenge

**Konteks Tantangan:**
Sebuah platform perbankan digital memiliki service otentikasi sentral. Service ini membaca profil permissions pengguna yang berukuran 4 KB setiap kali token JWT divalidasi.
- Throughput sistem: 250.000 RPS.
- Kapasitas memori server instans ASP.NET Core: 4 GB RAM.
- Profil permission berubah sangat jarang (maksimal 1 kali sehari per user), namun jika berubah, akses user harus terupdate di seluruh cluster dalam kurun waktu kurang dari 500 milidetik demi alasan audit keamanan (*Security Compliance*).

**Tugas Anda:**
Rancang arsitektur implementasi cache lengkap (Tulis dokumen desain teknis dan class C# inti) yang memenuhi kriteria berikut tanpa menggunakan library pihak ketiga tambahan (hanya `Microsoft.Extensions.Caching.Memory` dan `StackExchange.Redis`):
1. Penggunaan RAM di setiap node tidak boleh bertumbuh secara linier jika terjadi serangan *random username scanning* (mencegah DoS pada L1).
2. Jika sambungan Redis ke cluster terputus (*Connection Failure / Network Partition*), pod tidak boleh mengalami *crash* atau *cascade hanging*, melainkan harus secara otomatis mengalami degradasi ke *safe fallback* lokal dengan circuit breaker pattern.
3. Alokasi heap per request validasi harus strictly **0 bytes** pada status L1 cache hit.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Objek di .NET yang berukuran $\ge 85.000$ bytes akan dialokasikan oleh Garbage Collector ke dalam:
   - A. Gen 0
   - B. Gen 1
   - C. Large Object Heap (LOH)
   - D. Stack Frame

2. Apa tujuan utama memanggil `ArrayPool<byte>.Shared.Return(buffer, clearArray: true)`?
   - A. Menghapus referensi memori dari Virtual Address OS
   - B. Mengembalikan memori ke OS segera tanpa melewati GC
   - C. Mengembalikan buffer ke pool dan membersihkan data sensitif dari array agar tidak dibaca penyewa berikutnya
   - D. Memaksa GC Gen 2 berjalan seketika

3. Fenomena *Cache Stampede* terjadi pada kondisi:
   - A. Database mengalami deadlock akibat distributed locking
   - B. Ribuan request concurrent mendapati cache key yang sama telah kedaluwarsa secara bersamaan
   - C. Ukuran data di Redis melebihi memori fisik server
   - D. Redis client kehabisan port TCP socket

4. Mengapa mengakses data dari L1 Cache (`IMemoryCache`) lebih efisien daripada L2 Cache (`Redis`)?
   - A. L1 cache menggunakan hard disk NVMe
   - B. L1 cache tidak membutuhkan serialisasi/deserialisasi byte dan terhindar dari round-trip latensi socket jaringan
   - C. L1 cache mendukung ACID transaction
   - D. L1 cache secara otomatis terkompresi dengan format gzip

5. Dampak dari penulisan kode `var val = redisDatabase.StringGetAsync(key).Result;` di lingkungan ASP.NET Core adalah:
   - A. Penurunan penggunaan memori Gen 0
   - B. Potensi terjadinya Thread Pool Starvation dan request timeout massal
   - C. Data tersimpan permanen di LOH
   - D. Pembersihan memory heap secara otomatis

#### Bagian 2: Intermediate (Benar/Salah & Analisis Singkat)

6. **(Benar / Salah)** Mengatur absolute expiration tanpa sliding expiration pada cache menjamin sistem bebas dari serangan Cache Stampede.
7. **(Benar / Salah)** `Span<T>` dan `ReadOnlySpan<T>` dapat digunakan sebagai generic type parameter pada asynchronous method (`async Task`).
8. **(Benar / Salah)** Server Garbage Collector (`ServerGC`) menginstansiasi managed heap dan GC thread khusus untuk setiap logical CPU core yang tersedia di sistem.
9. Jelaskan mengapa *Double-Checked Locking* penting digunakan di dalam implementasi hybrid caching saat mengambil data setelah melewati `SemaphoreSlim.WaitAsync()`!
10. Sebutkan risiko teknis utama dari penggunaan Redis Pub/Sub sebagai invalidation backplane, dan bagaimana strategi fallback mitigasinya!

#### Bagian 3: Production Case Scenarios

11. **Skenario Kasus 1:**
    Sebuah aplikasi ASP.NET Core 8 di-deploy pada container Docker dengan memori limit 1 GB. Metrik APM menunjukkan bahwa penggunaan memori terus meningkat perlahan selama 3 hari hingga container dimatikan paksa oleh Linux kernel (*OOMKilled*). Dump file menunjukkan bahwa objek `Byte[]` menempati 75% heap di LOH. Identifikasi 2 kemungkinan sumber masalah arsitektural dan jelaskan langkah perbaikannya!

12. **Skenario Kasus 2:**
    Perusahaan Anda mengalami insiden data leakage internal: Pegawai A melihat informasi profil Pegawai B setelah dilakukan update profil pada sistem human resource yang menggunakan hybrid caching. Analisis kemungkinan bug pada lapisan sinkronisasi memory cache lokal dan bagaimana Anda memvalidasi perbaikannya.

13. **Skenario Kasus 3:**
    Dalam sebuah cluster Redis dengan latensi normal <1ms, tiba-tiba metrik `ThreadPool.QueueUserWorkItem` ASP.NET Core melonjak drastis, latensi aplikasi naik ke 5.000ms, sementara utilisasi CPU Redis server tercatat hanya 15%. Log error dipenuhi pesan `Timeout awaiting response (outbound=0KiB, inbound=0KiB)`. Diagnosis apa yang terjadi di layer runtime web server dan bagaimana menyelesaikannya!

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **C** - Objek $\ge 85.000$ bytes dialokasikan langsung ke LOH untuk menghindari biaya pemindahan objek besar di segmen ephemeral.
2. **C** - Menghindari *memory data leak* ke penyewa buffer berikutnya dan mengembalikan buffer agar dapat didaur ulang tanpa membebani GC.
3. **B** - Kedaluwarsanya key penting yang diakses secara serentak sehingga seluruh request membanjiri sumber data utama (Database).
4. **B** - L1 menyimpan *object reference* langsung di CLR Managed Heap, menghilangkan penalti serialisasi/deserialisasi dan I/O jaringan.
5. **B** - Memblokir managed thread pada I/O completion callback memicu kehabisan worker thread (*Thread Pool Starvation*).

#### Bagian 2: Intermediate
6. **Salah** - Absolute expiration justru dapat menjadi pemicu utama stampede ketika TTL habis pada jam sibuk.
7. **Salah** - `Span<T>` adalah `ref struct` yang dialokasikan khusus di stack dan tidak dapat diangkat (*boxed*) ke dalam state machine compiler async/await.
8. **Benar** - Server GC mendistribusikan dedicated heap per core untuk memaksimalkan throughput pada sistem multi-core server.
9. **Analisis Singkat:** Karena saat beberapa thread menunggu antrean semaphore di key yang sama, thread pemenang pertama (*leader*) telah selesai mempopulasikan L1. Tanpa pengecekan ulang kedua setelah thread berikutnya masuk, thread-thread selanjutnya akan mengeksekusi I/O redundan ke L2/Database.
10. **Analisis Singkat:** Sifat Redis Pub/Sub adalah *fire-and-forget* (at-most-once delivery). Jika terjadi disconnect sesaat pada network link pod, pesan invalidasi akan hilang dan L1 pod tersebut berpotensi menyimpan data usang (*stale*). Mitigasi: Tetapkan batas maksimum TTL L1 yang sangat pendek (misal: 1-2 menit) sebagai safe fallback window.

#### Bagian 3: Production Case Scenarios
11. **Analisis Masalah 1:**
    - Serialisasi payload cache L2 menggunakan method yang mengalokasikan array byte baru $>85.000$ bytes tanpa pooling, menyebabkan fragmentasi LOH kronis.
    - `IMemoryCache` tidak menetapkan `SizeLimit` dan entry size, sehingga objek berukuran besar di L1 tidak pernah dieviasi secara efektif saat memory pressure naik.
    - *Solusi:* Terapkan `ArrayPool<byte>.Shared` untuk serialisasi buffer, aktifkan `SizeLimit` pada `MemoryCacheOptions`, dan atur runtime flag `GCLargeObjectHeapCompactionMode` ke *CompactOnce* jika diperlukan.
12. **Analisis Masalah 2:**
    - Terjadi *reference leaking* di mana instance object hasil L1 cache dikembalikan langsung ke caller context, kemudian caller context memutasi (*mutate*) state internal object tersebut (misal: `userProfile.Username = "New"`), sehingga seluruh thread lain yang membaca L1 mendapatkan object mutasi yang salah.
    - *Solusi:* Simpan object immutable (record/readonly struct) atau buat salinan (*defensive copy*) sebelum mengembalikan data dari L1 cache.
13. **Analisis Masalah 3:**
    - Terjadi *Sync-Over-Async* di kode aplikasi atau Thread Pool starvation akibat operasi CPU-bound intensif yang berjalan di thread pool yang sama dengan IOCP callback worker. Saat worker thread terblokir, threadpool butuh waktu lambat (*ramp-up rate* 1-2 thread per detik) untuk membuat thread baru, menyebabkan timeout pada driver StackExchange.Redis meski engine Redis itu sendiri menganggur.
    - *Solusi:* Audit kode dari seluruh pemanggilan `.Result` / `.Wait()`, pisahkan komputasi berat ke worker background task khusus, dan konfigurasikan `ThreadPool.SetMinThreads()` ke angka yang lebih tinggi (sesuai baseline traffic) pada saat bootstrap aplikasi.

---

### 16. Summary

Optimalisasi memori dan caching tingkat enterprise pada ASP.NET Core menuntut pemahaman menyeluruh terhadap ekosistem CLR dan arsitektur sistem terdistribusi:
1. **Memory Discipline:** Menghindari alokasi Gen 2 dan fragmentasi LOH adalah pondasi performa tinggi. Pemanfaatan `ArrayPool<T>`, `Memory<T>`, dan teknik pooling secara signifikan memangkas latensi alokasi.
2. **Multi-Tiered Topology:** Pola Hybrid Cache (L1 MemoryCache + L2 Redis) memberikan trade-off terbaik: menghadirkan latensi instan sub-mikrodetik dari L1 dan konsistensi lintas node berkat L2 dan invalidation backplane.
3. **Thundering Herd Resilience:** Skalabilitas sejati dicapai saat sistem terlindung dari *Cache Stampede*. Kombinasi Single-Flight concurrency lock dan algoritma early refresh probabilistik (XFetch) menjamin beban layer database tetap konsisten dan stabil bahkan pada lonjakan trafik ekstrem.