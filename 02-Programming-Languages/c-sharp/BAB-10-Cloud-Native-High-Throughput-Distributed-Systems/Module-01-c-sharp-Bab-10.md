# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Modul:** c-sharp
*   **Bab:** 10 — Enterprise & High-Performance Computing
*   **Modul 01:** Cloud-Native, High-Throughput & Distributed Systems
*   **Tingkat Kesulitan:** Advanced / Expert
*   **Prasyarat:** Pemahaman mendalam tentang C# Asynchronous Programming (`async`/`await`, `TaskCompletionSource`, `ValueTask`), Memory Management (`Span<T>`, `Memory<T>`, `ArrayPool<T>`), Networking Fundamentals (TCP/IP, HTTP/2, gRPC), dan dasar-dasar arsitektur microservices.
*   **Target Tech Stack:** .NET 8/9, C# 12/13, ASP.NET Core Minimal APIs, `System.Threading.Channels`, Polly v8, OpenTelemetry, Redis, RabbitMQ/Kafka, Docker/Kubernetes.

---

# SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, Anda diharapkan mampu:

1.  **Mendiagnosis dan Mengatasi** bottleneck konkurensi serta *ThreadPool starvation* dalam runtime .NET di bawah beban *throughput* ekstrem (100.000+ rps).
2.  **Merancang dan Mengimplementasikan** *non-blocking, bounded in-memory processing pipelines* menggunakan `System.Threading.Channels` dengan kontrol *backpressure* deterministik.
3.  **Membangun Arsitektur Terdistribusi Berdaya Tahan Tinggi (Resilient)** menggunakan pola *Transactional Outbox*, *Idempotent Consumer*, dan *Polly v8 Resilience Pipelines* (Circuit Breaker, Rate Limiting, Hedging).
4.  **Mengoptimalkan Penggunaan Sumber Daya** hingga *near-zero allocation* memanfaatkan `ArrayPool<T>`, `PipeReader`/`PipeWriter`, dan konfigurasi Garbage Collector tingkat lanjut (*Dynamic Adaptation to Application Sizes / DATAS*).
5.  **Menerapkan Observabilitas Cloud-Native Menyeluruh** berbasis OpenTelemetry (Metrics, Traces, Logs) dengan W3C Trace Context propagation melintasi batasan proses terdistribusi.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Membangun sistem *cloud-native* berkinerja tinggi membutuhkan pergeseran paradigma fundamental dari pemikiran monolitik sinkron menuju sistem terdistribusi reaktif:

```
[ Mental Model Monolitik Tradisional ]
Request Masuk ---> Thread Dialokasikan ---> I/O Database Sinkron ---> Return Response
(Kelemahan: Thread blocking, cascading failure, scaling berbasis vertikal tak terbatas)

[ Mental Model Distributed High-Throughput Cloud-Native ]
Request Masuk ---> Fast Ingestion (Zero-Alloc, Non-blocking) ---> Bounded Buffer (Backpressure)
                         |
                         +---> Asynchronous Batch Processing ---> Event Broker / Outbox Pattern
                         |
                         +---> Immediate Acknowledgment / Polling Token / SSE Streaming
(Keunggulan: Elastic scaling, fault-isolation, mechanical sympathy, graceful degradation)
```

### 1. Fallacies of Distributed Computing
Anda harus selalu mengasumsikan:
*   Jaringan **tidak pernah** andal (paket hilang, partisi jaringan/split-brain adalah keniscayaan).
*   Latensi **tidak pernah** nol (desain sistem wajib memperhitungkan jitter dan tail-latency).
*   Bandwidth memiliki batasan fisik; serialisasi payload menentukan efisiensi agregat.
*   Topologi jaringan berubah secara dinamis di lingkungan Kubernetes.

### 2. Mechanical Sympathy dalam Runtime .NET
Runtime C# tidak berjalan di ruang hampa. Kinerja optimal menuntut Anda memahami bagaimana instruksi C# diterjemahkan ke assembly oleh RyuJIT, bagaimana memori ditata dalam L1/L2/L3 CPU cache lines, dan bagaimana .NET ThreadPool mendistribusikan *work items* ke *OS threads* melalui algoritma *Hill Climbing* dan *Work-Stealing Queues*.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur *Ingestion Pipeline* berkecepatan tinggi dengan *Backpressure*, *Circuit Breaker*, dan *Transactional Outbox Pattern*:

```
+---------------------------------------------------------------------------------------------------+
|                                 EDGE TIER (KUBERNETES INGRESS)                                    |
+---------------------------------------------------------------------------------------------------+
                                                  │
                                                  │ HTTPS / gRPC Traffic (100k+ req/sec)
                                                  ▼
+---------------------------------------------------------------------------------------------------+
| INGESTION NODE: ASP.NET Core Kestrel (.NET 8/9 Engine)                                            |
|                                                                                                   |
|  [ Minimal API Endpoint ]                                                                         |
|            │  (Validasi Payload Cepat & Idempotency Check via Redis Mem-Cache)                    |
|            ▼                                                                                      |
|  [ System.Threading.Channels (BoundedChannel<T>) ]  <--- Backpressure Policy: DropOldest / Wait   |
|            │                                                                                      |
|            ├─── Worker Task 1 (Consumer) ──────┐                                                  |
|            ├─── Worker Task 2 (Consumer) ──────┼───► Batching Engine (ArrayPool Buffer)           |
|            └─── Worker Task N (Consumer) ──────┘                    │                             |
+---------------------------------------------------------------------┼-----------------------------+
                                                                      │
                                        ┌─────────────────────────────┴────────────────────────────┐
                                        ▼                                                          ▼
+------------------------------------------------+       +-------------------------------------------------+
| DATA PERSISTENCE: Transactional Outbox Pattern |       | RESILIENCE TIER: Polly v8 Resilience Pipeline   |
|                                                |       |                                                 |
|  [ PostgreSQL / YugabyteDB ]                   |       |  [ Rate Limiter ] -> [ Circuit Breaker ]        |
|  - Table: BusinessEntity                       |       |                       │                         |
|  - Table: OutboxMessages (Uncommitted Events)  |       |                       ▼                         |
+------------------------------------------------+       |  [ Distributed Message Broker ]                 |
                        │                                |  - Apache Kafka / RabbitMQ Streams              |
                        ▼                                +-------------------------------------------------+
          [ Outbox Publisher Service ]                                            │
                        │                                                         ▼
                        └────────────────────────────────────────────► [ Downstream Consumers ]
```

### Alur Eksekusi Data:
1.  **Ingestion:** Request masuk melalui Kestrel, dialokasikan pada memory pool menggunakan `PipeReader`.
2.  **Throttling:** Redis mendeteksi duplicate request melalui distributed lock/token bucket.
3.  **Buffering Internal:** Data dipush ke dalam `BoundedChannel<T>`. Jika downstream jenuh, channel menahan eksekusi produsen (backpressure) atau mendegradasi request sesuai policy.
4.  **Dispatched Batching:** Kumpulan worker menarik data secara batch guna meminimalkan I/O round-trip ke persistensi.
5.  **Reliable Publishing:** Pola Outbox menjamin atomisitas data; Polly v8 memitigasi kegagalan transmisi ke broker eksternal tanpa memblokir thread eksekusi utama.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. ThreadPool Architecture: Hill Climbing vs Starvation
.NET ThreadPool mengelola dua antrean:
*   **Global Queue:** Antrean berbasis FIFO tempat *work items* pertama kali masuk (misal, via `ThreadPool.QueueUserWorkItem`).
*   **Local Work-Stealing Queues:** Setiap thread worker memiliki antrean LIFO lokal. Ketika sebuah thread mengeksekusi item dan memicu task baru, task tersebut didorong ke antrean lokal thread tersebut untuk memaksimalkan *cache locality*.
*   **Hill Climbing Algorithm:** ThreadPool memantau throughput (penyelesaian task) secara berkala. Jika throughput naik saat thread ditambah, pool menambah thread. Jika throughput turun atau stagnan, pool mengurangi thread. 
*   *Bahaya Sinkron-over-Asinkron:* Memanggil `.Result` atau `.Wait()` memblokir thread worker. Algoritma Hill Climbing lambat merespons lonjakan pemblokiran (hanya menyuntikkan ~1-2 thread per detik), menyebabkan *ThreadPool Starvation* dan latensi melonjak drastis.

### 2. Kestrel Transport Architecture
Kestrel tidak lagi menggunakan thread per koneksi socket tradisional. Kestrel mengimplementasikan abstraksi `System.IO.Pipelines`:
*   Driver Socket I/O (`SocketAsyncEventArgs` atau `io_uring` di Linux) membaca byte stream dari network buffer kernel.
*   Data ditulis langsung ke buffer memori yang disewakan dari `MemoryPool<byte>`.
*   Aplikasi membaca dari `PipeReader` tanpa perlu menyalin data (*zero-copy allocation*), mengurangi kerja Garbage Collector secara signifikan.

### 3. System.Threading.Channels Internal
`System.Threading.Channels` lebih unggul dibanding `BlockingCollection<T>` karena bersifat asinkron murni:
*   Menggunakan operasi *lock-free* atau *lightweight synchronization primitives* internal berbasis ring-buffer.
*   `BoundedChannel<T>` menerapkan backpressure melalui `ValueTask`: jika kapasitas tercapai, `WriteAsync` menunda task (menghasilkan *state machine* tanpa memblokir OS thread) hingga ada slot kosong dari `ReadAsync`.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. CAP & PACELC Theorem dalam Sistem Berbasis C#
Teorema CAP menyatakan dalam kondisi network partition ($P$), Anda harus memilih Konsistensi ($C$) atau Ketersediaan ($A$). Teorema PACELC melengkapinya: Jika ada Partisi ($P$), pilih Ketersediaan ($A$) atau Konsistensi ($C$); Namun Else ($E$), pilih Latensi ($L$) atau Konsistensi ($C$).

```
                PACELC
               /      \
        If Partition   Else (Normal Operation)
          /       \          /        \
       (A)         (C)     (L)         (C)
    Available  Consistent Latency  Consistent
```

Dalam implementasi C#:
*   **PC/EC (e.g., Akuntansi Finansial):** Menggunakan transaksi terdistribusi ACID, distributed lock Redis, mengorbankan latensi.
*   **PA/EL (e.g., Real-time Ingestion / IoT Telemetry):** Data masuk ke buffer lokal (`BoundedChannel`), ACK diberikan segera, replikasi ke distributed store bersifat eventual consistent.

### 2. The Transactional Outbox Pattern
Mengirim event langsung ke message broker di tengah-tengah transaksi database adalah anti-pattern terdistribusi (Dual-Write Problem). Jika broker gagal menerima event setelah DB commit, sistem menjadi tidak konsisten.

*Solusi Outbox Pattern:*
1.  Buka transaksi DB lokal.
2.  Tulis status entitas bisnis.
3.  Tulis event yang akan dikirim ke tabel `OutboxMessages` dalam transaksi yang sama.
4.  Commit transaksi database (Atomic).
5.  Proses terpisah (asinkron) membaca `OutboxMessages`, mempublikasikannya ke broker dengan jaminan *At-Least-Once Delivery*, lalu menandai event sebagai *Processed*.

### 3. Backpressure Mechanics
Jika produsen memproduksi data pada 200.000 rps, sedangkan konsumen hanya mampu memproses 80.000 rps, kelebihan 120.000 rps akan masuk ke antrean memori.
*   **Unbounded Queue:** Menyebabkan konsumsi RAM naik eksponensial $\to$ Penekanan GC Gen 2 $\to$ GC Pause meluas $\to$ Out of Memory (OOM) Crash.
*   **Bounded Queue:** Menentukan batas rigid antrean. Ketika penuh, sistem memilih:
    *   *Wait:* Menahan produsen (TCP zero-window propagation / HTTP 429 Too Many Requests).
    *   *DropNewest/DropOldest:* Menghapus elemen lama/baru jika data bersifat *loss-tolerant* (seperti streaming telemetri audio/sensor).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi In-Memory Resilient Ingestion Pipeline menggunakan `System.Threading.Channels` dengan batas kapasitas, backpressure bertipe non-blocking, dan penghentian terkoordinasi (*Graceful Shutdown*).

```csharp
using System.Threading.Channels;

namespace HighThroughput.Channels;

public sealed class TelemetryBatchProcessor
{
    private readonly Channel<TelemetryRecord> _channel;
    private readonly ILogger _logger;
    private readonly int _batchSize;
    private readonly TimeSpan _flushInterval;
    private Task? _consumerLoopTask;
    private readonly CancellationTokenSource _cts = new();

    public record TelemetryRecord(Guid DeviceId, double MetricValue, long TimestampUnixMs);

    public TelemetryBatchProcessor(int capacity, int batchSize, TimeSpan flushInterval, ILogger logger)
    {
        _batchSize = batchSize;
        _flushInterval = flushInterval;
        _logger = logger;

        // Inisialisasi Bounded Channel dengan strategi Backpressure "Wait"
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleWriter = false, // Banyak endpoint bisa menulis serentak
            SingleReader = true   // Satu background consumer loop
        };

        _channel = Channel.CreateBounded<TelemetryRecord>(options);
    }

    public void Start()
    {
        _consumerLoopTask = Task.Run(() => ConsumerEngineLoopAsync(_cts.Token));
    }

    public async ValueTask<bool> IngestAsync(TelemetryRecord record, CancellationToken ct)
    {
        // Non-blocking wait jika antrean penuh, mengalirkan backpressure ke caller
        while (await _channel.Writer.WaitToWriteAsync(ct).ConfigureAwait(false))
        {
            if (_channel.Writer.TryWrite(record))
            {
                return true;
            }
        }
        return false;
    }

    private async Task ConsumerEngineLoopAsync(CancellationToken ct)
    {
        var batch = new List<TelemetryRecord>(_batchSize);
        var periodicTimer = new PeriodicTimer(_flushInterval);

        try
        {
            while (!ct.IsCancellationRequested)
            {
                // Strategi dual: Trigger pemrosesan jika batch penuh ATAU timer tercapai
                while (_channel.Reader.TryRead(out var item))
                {
                    batch.Add(item);
                    if (batch.Count >= _batchSize)
                    {
                        await FlushBatchAsync(batch, ct).ConfigureAwait(false);
                        batch.Clear();
                    }
                }

                // Tunggu item berikutnya atau timeout periodic timer untuk flush data sisa
                var readTask = _channel.Reader.WaitToReadAsync(ct).AsTask();
                var timerTask = periodicTimer.WaitForNextTickAsync(ct).AsTask();

                var completedTask = await Task.WhenAny(readTask, timerTask).ConfigureAwait(false);

                if (completedTask == readTask)
                {
                    if (!await readTask.ConfigureAwait(false))
                    {
                        // Channel telah ditutup secara permanen
                        break;
                    }
                }
                else
                {
                    // Timer terpicu, lakukan flush data yang tertahan meskipun batch belum penuh
                    if (batch.Count > 0)
                    {
                        await FlushBatchAsync(batch, ct).ConfigureAwait(false);
                        batch.Clear();
                    }
                }
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            _logger.LogInformation("Consumer engine loop menerima sinyal shutdown.");
        }
        finally
        {
            periodicTimer.Dispose();
            // Kuras sisa antrean sebelum benar-benar berhenti
            while (_channel.Reader.TryRead(out var item))
            {
                batch.Add(item);
            }
            if (batch.Count > 0)
            {
                await FlushBatchAsync(batch, CancellationToken.None).ConfigureAwait(false);
                batch.Clear();
            }
            _logger.LogInformation("Draining selesai. Consumer engine dihentikan aman.");
        }
    }

    private async Task FlushBatchAsync(List<TelemetryRecord> items, CancellationToken ct)
    {
        // Simulasi penulisan I/O batch berkecepatan tinggi
        _logger.LogInformation("Flushing batch sebanyak {Count} entri ke storage/broker.", items.Count);
        await Task.Delay(10, ct).ConfigureAwait(false); 
    }

    public async Task StopAsync()
    {
        _channel.Writer.Complete(); // Tutup akses penulisan baru
        _cts.Cancel();               // Sinyalkan pembatalan ke loop utama

        if (_consumerLoopTask != null)
        {
            await _consumerLoopTask.ConfigureAwait(false);
        }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari implementasi kode di Seksi 07:

1.  **Baris 20–25:**
    ```csharp
    var options = new BoundedChannelOptions(capacity)
    {
        FullMode = BoundedChannelFullMode.Wait,
        SingleWriter = false,
        SingleReader = true
    };
    ```
    *Analisis:* `BoundedChannelFullMode.Wait` adalah fondasi *Backpressure*. Ketika kapasitas tercapai, produsen tidak melempar eksepsi dan tidak membuat memori bengkak; melainkan ditangguhkan (*yield*) secara asinkron. `SingleReader = true` menginstruksikan runtime untuk menggunakan algoritma sinkronisasi antrean teroptimasi yang memotong beban *interlocked/CAS CPU instructions* karena hanya ada satu thread konsumen aktif.

2.  **Baris 38–46:**
    ```csharp
    while (await _channel.Writer.WaitToWriteAsync(ct).ConfigureAwait(false))
    {
        if (_channel.Writer.TryWrite(record))
        {
            return true;
        }
    }
    ```
    *Analisis:* Pola `WaitToWriteAsync` dipadukan dengan `TryWrite`. Pola ini menghindari alokasi `Task<bool>` di dalam hot path. Jika antrean penuh, *continuation* didaftarkan ke status channel internal tanpa memblokir thread eksekusi Kestrel.

3.  **Baris 50:**
    ```csharp
    var batch = new List<TelemetryRecord>(_batchSize);
    ```
    *Analisis:* Mengalokasikan kapasitas list di awal (*pre-sizing*) mencegah alokasi berulang dan operasi penyalinan array internal (*array resizing overhead*) saat elemen ditambahkan.

4.  **Baris 68–71:**
    ```csharp
    var readTask = _channel.Reader.WaitToReadAsync(ct).AsTask();
    var timerTask = periodicTimer.WaitForNextTickAsync(ct).AsTask();
    var completedTask = await Task.WhenAny(readTask, timerTask).ConfigureAwait(false);
    ```
    *Analisis:* Penggabungan *Threshold-based batching* dan *Time-based batching*. Data dikirim segera jika kuota batch tercapai. Namun, jika aliran data melambat, `PeriodicTimer` menjamin latensi penyelesaian data tidak membusuk (*stale*) di memori lokal.

5.  **Baris 97–109:**
    ```csharp
    finally
    {
        periodicTimer.Dispose();
        while (_channel.Reader.TryRead(out var item))
        {
            batch.Add(item);
        }
        ...
    }
    ```
    *Analisis:* Mekanisme *Draining* pada Graceful Shutdown. Kegagalan mengeksekusi draining akan memicu hilangnya paket data yang sudah diterima di memori saat Kubernetes mengirim sinyal `SIGTERM`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Sistem Ingestion Transaksi Kilat (Flash Sale / Order Gateway)
Sebuah platform e-commerce menghadapi lonjakan transaksi Black Friday dengan karakteristik:
*   Beban puncak: **120.000 pesanan per detik** secara serentak.
*   Database relasional (PostgreSQL) downstream hanya mampu menangani maksimum **8.000 transaksi penulisan per detik** sebelum *connection pool* jenuh dan I/O latency kolaps.
*   Syarat kaku: **Zero Data Loss**, **Idempotency** (tidak boleh ada pemotongan saldo ganda akibat network retry dari mobile apps), dan **Tail Latency p99 < 50ms** pada ingestion gateway.

### Solusi Desain Arsitektur:
1.  **Fast Edge Rejection & Validation:** Minimal API menggunakan zero-allocation validation, memverifikasi JWT dan ID idempotensi via Redis Sentinel cluster.
2.  **In-Memory Bounded Channels & Partitioning:** Memecah pesanan ke dalam 16 memory channel terisolasi berbasis hashing `CustomerId` untuk mempertahankan urutan modifikasi status per pelanggan (*causal ordering*).
3.  **Resilience via Polly v8:** Menerapkan pipelines:
    *   *Rate Limiting Pipeline:* Menolak transaksi melebihi kapasitas gateway dengan header HTTP `Retry-After`.
    *   *Circuit Breaker:* Mengisolasi kegagalan penyimpanan lokal Outbox jika disk I/O bottleneck, mendegradasi sistem untuk mengarahkan order ke backup secondary cold-storage.
4.  **Transactional Outbox Engine:** Background worker mengelompokkan pesanan menjadi multi-row INSERT statement ke PostgreSQL, lalu worker lain streaming data via Debezium/Kafka CDC atau direct channel polling.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi menyeluruh (production-grade) dari sistem Ingestion Gateway yang menggabungkan ASP.NET Core Minimal API, Redis Idempotency, Polly v8 Resilience Pipeline, dan Channel Outbox Dispatcher.

```csharp
using System.Text.Json;
using System.Threading.Channels;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Mvc;
using Polly;
using Polly.CircuitBreaker;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

// 1. Registrasi StackExchange.Redis
builder.Services.AddSingleton<IConnectionMultiplexer>(_ => 
    ConnectionMultiplexer.Connect("localhost:6379,abortConnect=false"));

// 2. Registrasi Channel In-Memory Bounded Buffer
builder.Services.AddSingleton(Channel.CreateBounded<OrderCreatedEvent>(new BoundedChannelOptions(50_000)
{
    FullMode = BoundedChannelFullMode.Wait,
    SingleReader = false,
    SingleWriter = false
}));

// 3. Registrasi Polly v8 Resilience Pipeline
builder.Services.AddSingleton<ResiliencePipeline>(sp =>
{
    return new ResiliencePipelineBuilder()
        .AddRateLimiter(new SlidingWindowRateLimiter(new SlidingWindowRateLimiterOptions
        {
            PermitLimit = 100_000,
            Window = TimeSpan.FromSeconds(1),
            SegmentsPerWindow = 4,
            QueueLimit = 5_000
        }))
        .AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 100,
            BreakDuration = TimeSpan.FromSeconds(15)
        })
        .AddTimeout(TimeSpan.FromMilliseconds(500))
        .Build();
});

// 4. Registrasi Background Outbox Dispatcher
builder.Services.AddHostedService<OutboxDispatcherWorker>();

var app = builder.Build();

// Endpoint Ingestion dengan Idempotensi & Resilience Pipeline
app.MapPost("/api/v1/orders", async (
    [FromBody] CreateOrderRequest request,
    [FromHeader(Name = "X-Idempotency-Key")] string? idempotencyKey,
    [FromServices] IConnectionMultiplexer redis,
    [FromServices] Channel<OrderCreatedEvent> channel,
    [FromServices] ResiliencePipeline resiliencePipeline,
    CancellationToken ct) =>
{
    if (string.IsNullOrWhiteSpace(idempotencyKey))
    {
        return Results.BadRequest(new { Error = "Header 'X-Idempotency-Key' wajib disertakan." });
    }

    var db = redis.GetDatabase();
    var redisKey = $"idempotency:order:{idempotencyKey}";

    // Eksekusi pipeline resilience untuk rate limiting & fail-fast
    try
    {
        return await resiliencePipeline.ExecuteAsync(async state =>
        {
            // Cek idempotensi atomik via Redis (SET NX dengan expiry 1 jam)
            bool acquired = await db.StringSetAsync(redisKey, "PENDING", TimeSpan.FromHours(1), When.NotExists);
            if (!acquired)
            {
                return Results.Conflict(new { Error = "Permintaan duplikat terdeteksi. Transaksi sedang atau telah diproses." });
            }

            var orderEvent = new OrderCreatedEvent(
                OrderId: Guid.NewGuid(),
                CustomerId: request.CustomerId,
                Amount: request.Amount,
                IdempotencyKey: idempotencyKey,
                CreatedAtUtc: DateTime.UtcNow
            );

            // Tulis ke bounded channel pipeline (menerapkan backpressure non-blocking)
            await channel.Writer.WriteAsync(orderEvent, state);

            return Results.Accepted($"/api/v1/orders/{orderEvent.OrderId}", new { orderEvent.OrderId, Status = "Enqueued" });
        }, ct);
    }
    catch (RateLimiterRejectedException)
    {
        return Results.StatusCode(StatusCodes.Status429TooManyRequests);
    }
    catch (BrokenCircuitException)
    {
        return Results.StatusCode(StatusCodes.Status503ServiceUnavailable);
    }
});

app.Run();

// ==========================================
// KONTRAK DATA & MODELS
// ==========================================
public sealed record CreateOrderRequest(Guid CustomerId, decimal Amount);

public sealed record OrderCreatedEvent(
    Guid OrderId,
    Guid CustomerId,
    decimal Amount,
    string IdempotencyKey,
    DateTime CreatedAtUtc
);

// ==========================================
// WORKER OUTBOX DENGAN BATCH BULK INSERT
// ==========================================
public sealed class OutboxDispatcherWorker : BackgroundService
{
    private readonly Channel<OrderCreatedEvent> _channel;
    private readonly ILogger<OutboxDispatcherWorker> _logger;
    private const int BatchSize = 1000;
    private readonly TimeSpan _drainTimeout = TimeSpan.FromMilliseconds(50);

    public OutboxDispatcherWorker(Channel<OrderCreatedEvent> channel, ILogger<OutboxDispatcherWorker> logger)
    {
        _channel = channel;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Outbox Dispatcher Engine aktif.");
        var buffer = new List<OrderCreatedEvent>(BatchSize);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Tarik pesan pertama dengan await untuk efisiensi CPU
                if (await _channel.Reader.WaitToReadAsync(stoppingToken))
                {
                    var timeoutCts = new CancellationTokenSource(_drainTimeout);
                    using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, timeoutCts.Token);

                    try
                    {
                        while (buffer.Count < BatchSize && _channel.Reader.TryRead(out var orderEvent))
                        {
                            buffer.Add(orderEvent);
                        }
                    }
                    catch (OperationCanceledException) when (timeoutCts.IsCancellationRequested)
                    {
                        // Batas waktu drain interval tercapai, lanjutkan flush
                    }

                    if (buffer.Count > 0)
                    {
                        await PersistBatchToOutboxStorageAsync(buffer, stoppingToken);
                        buffer.Clear();
                    }
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Kesalahan fatal pada pipeline pemrosesan batch outbox.");
                await Task.Delay(1000, stoppingToken); // Backoff jika ada failure storage
            }
        }

        // Tangani sisa data saat gracefully stopping
        while (_channel.Reader.TryRead(out var residual))
        {
            buffer.Add(residual);
        }
        if (buffer.Count > 0)
        {
            await PersistBatchToOutboxStorageAsync(buffer, CancellationToken.None);
        }
    }

    private async Task PersistBatchToOutboxStorageAsync(List<OrderCreatedEvent> events, CancellationToken ct)
    {
        // Di lingkungan nyata: Gunakan PostgreSQL NpgsqlBatch atau EF Core BulkExtensions
        // Contoh ini mensimulasikan persistensi bulk batch yang atomik
        _logger.LogInformation("Berhasil melakukan bulk write {Count} orders ke DB Outbox.", events.Count);
        await Task.Delay(5, ct); // Simulasi high-speed disk I/O
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur Pemrosesan Asinkron Internal

| Fitur / Parameter | `System.Threading.Channels` | `BlockingCollection<T>` | Actor Model (Proto.Actor / Akka) | External Broker (Kafka / RabbitMQ) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Asinkron murni (`ValueTask`) | Sinkron (`WaitHandle` / Blocking) | Message Passing Asinkron | Jaringan Asinkron Eksternal |
| **Throughput** | Ekstrem (> 10 Juta ops/detik) | Sedang (< 500k ops/detik) | Sangat Tinggi (> 2 Juta ops/detik)| Tinggi (50k - 500k ops/detik) |
| **Alokasi Memori** | Mendekati Nol (Zero-allocation) | Alokasi Wrapper Node Objek | Sangat Rendah | Bergantung Serialisasi Jaringan |
| **Distribusi State** | Proses Tunggal (In-Memory) | Proses Tunggal (In-Memory) | Multi-Node Clustering | Multi-Node Persistent Storage |
| **Kompleksitas** | Rendah | Rendah | Tinggi (Perlu desain state actor) | Tinggi (Operasi infrastruktur) |
| **Use Case Terbaik** | In-process queue, backpressure | Legacy multi-threading code | Sistem State Stateful & Konkuren | Integrasi Sistem Lintas Service |

### Dual Write Solution: 2PC vs Transactional Outbox

| Dimensi Evaluasi | Two-Phase Commit (2PC / XA Transactions) | Transactional Outbox Pattern |
| :--- | :--- | :--- |
| **Kinerja & Latensi** | Sangat Buruk (Holding locks lintas sistem/jaringan) | Sangat Cepat (Hanya lock DB lokal sementara) |
| **Ketersediaan (CAP)** | Rendah (Blokade penuh jika koordinator mati) | Tinggi (Penerbitan asinkron terpisah) |
| **Dukungan Cloud Modern** | Hampir tidak didukung oleh cloud DB dan broker | Didukung secara native di semua platform |
| **Kompleksitas Konsumen** | Rendah (Konsisten secara instan) | Memerlukan penanganan **Idempotency** di konsumen |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1.  **Thread Pool Starvation akibat Sync-over-Async:**
    *   *Gejala:* CPU usage rendah (10–20%), tetapi Response Time HTTP melonjak dari 5ms menjadi 30 detik.
    *   *Penyebab:* Pemanggilan `.Result`, `.Wait()`, atau `GetAwaiter().GetResult()` pada code path. Thread pool kehabisan thread worker yang sedang menunggu task I/O lain selesai.
    *   *Edge Case:* Terjadi secara masif saat library pihak ketiga memanggil synchronous blocking I/O di dalam ASP.NET pipeline.

2.  **Split-Brain pada Distributed Lock (Redis Redlock):**
    *   *Penyebab:* GC Pause (Stop-the-world) yang panjang pada node aplikasi C#.
    *   *Skenario:* Node A mengambil lock Redis dengan TTL 5 detik. Node A mengalami Full GC Pause selama 7 detik. Lock di Redis expired. Node B mengambil lock yang sama. GC Node A selesai, Node A melanjutkan eksekusi mengira ia masih memegang lock. Terjadilah inkonsistensi ganda (*race condition*).
    *   *Solusi:* Gunakan *Optimistic Concurrency Control* via *Fencing Tokens* (monotonically increasing integer) yang divalidasi oleh database downstream.

3.  **Out-of-Order Execution pada Parallel Consumers:**
    *   *Masalah:* Membaca dari `Channel<T>` secara konkuren dengan banyak worker (`SingleReader = false`) menyebabkan event urutan kedua dieksekusi mendahului event urutan pertama.
    *   *Solusi:* Partisi antrean! Buat array channel internal:
        ```csharp
        int partitionIndex = (uint)customerId.GetHashCode() % PartitionCount;
        await _partitionedChannels[partitionIndex].Writer.WriteAsync(item);
        ```
        Setiap partisi memiliki **tepat satu** dedicated background loop (`SingleReader = true`).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan Fatal: Mengabaikan CancellationToken pada Network I/O
```csharp
// SALAH: Jika user membatalkan request (browser ditutup), I/O tetap berjalan sia-sia
[HttpGet("data")]
public async Task<IActionResult> GetData()
{
    var result = await _httpClient.GetStringAsync("https://api.internal/slow");
    return Ok(result);
}

// BENAR: Salurkan CancellationToken sampai ke transport layer terbawah
[HttpGet("data")]
public async Task<IActionResult> GetData(CancellationToken ct)
{
    var response = await _httpClient.GetAsync("https://api.internal/slow", ct);
    response.EnsureSuccessStatusCode();
    var result = await response.Content.ReadAsStringAsync(ct);
    return Ok(result);
}
```

### 2. Kesalahan Fatal: Naive Retry Storms tanpa Jitter
```csharp
// SALAH: 10.000 request gagal serentak, lalu mencoba kembali pada detik yang sama persis
// Mengakibatkan database downstream tumbang total (Thundering Herd Problem).
services.AddHttpClient("Downstream")
    .AddTransientHttpErrorPolicy(p => p.WaitAndRetryAsync(3, _ => TimeSpan.FromSeconds(2)));

// BENAR: Terapkan Exponential Backoff dengan Jitter acak via Polly v8
var resiliencePipeline = new ResiliencePipelineBuilder()
    .AddRetry(new RetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true, // Jitter mendistribusikan spike load secara acak
        BaseDelay = TimeSpan.FromMilliseconds(200)
    })
    .Build();
```

### 3. Kesalahan Fatal: Penggunaan `Channel<T>` secara Unbounded tanpa Proteksi
```csharp
// SALAH: Memori akan meledak jika terjadi kemacetan downstream
var channel = Channel.CreateUnbounded<T>();

// BENAR: Selalu tentukan batas rigidly untuk memicu backpressure
var channel = Channel.CreateBounded<T>(new BoundedChannelOptions(10_000)
{
    FullMode = BoundedChannelFullMode.Wait
});
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Twelve-Factor Concurrency & Statelessness:**
    *   Simpan state hanya di database atau distributed cache. Node komputasi C# harus bisa dimatikan atau di-*kill* kapan saja oleh Kubernetes tanpa merusak integritas sistem.

2.  **Graceful Termination Flow (SIGTERM Handling):**
    *   Tangani `IHostApplicationLifetime.ApplicationStopping`.
    *   Tutup semua listener HTTP terlebih dahulu (Kubernetes service controller akan menghapus pod dari routing table).
    *   Beri jeda *readiness probe fail* (misal 5 detik).
    *   Lakukan *flush* dan *draining* terhadap semua in-memory channels ke database/broker sebelum waktu terminasi habis (`terminationGracePeriodSeconds`).

3.  **High-Performance Logging:**
    *   Dilarang keras menggunakan string interpolation pada hot path: `_logger.LogInformation($"Order {id} created");` mengalokasikan string baru di heap.
    *   Gunakan source-generated logging:
        ```csharp
        public static partial class LogExtensions
        {
            [LoggerMessage(EventId = 101, Level = LogLevel.Information, Message = "Order {OrderId} berhasil diproses untuk Pelanggan {CustomerId}")]
            public static partial void LogOrderCreated(this ILogger logger, Guid orderId, Guid customerId);
        }
        ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Zero-Allocation Deserialization dengan Span<T> & ArrayPool<T>
Mengurangi tekanan pada Garbage Collector dengan menyewa buffer alih-alih mengalokasikan array baru:

```csharp
using System.Buffers;
using System.Text.Json;

public async ValueTask ProcessPayloadAsync(Stream networkStream, int payloadLength)
{
    // Sewa buffer dari pool memori bersama
    byte[] rentedBuffer = ArrayPool<byte>.Shared.Rent(payloadLength);
    try
    {
        int bytesRead = await networkStream.ReadAtLeastAsync(rentedBuffer, payloadLength, throwOnEndOfStream: true);
        
        // Buat slice memori tanpa alokasi baru
        ReadOnlySpan<byte> span = rentedBuffer.AsSpan(0, bytesRead);

        // Deserialisasi langsung dari read-only span
        var data = JsonSerializer.Deserialize<TelemetryPayload>(span);
        // Lakukan pemrosesan terhadap data...
    }
    finally
    {
        // Wajib mengembalikan buffer ke pool agar tidak terjadi memory leak
        ArrayPool<byte>.Shared.Return(rentedBuffer);
    }
}

public record TelemetryPayload(int SensorId, double Temperature);
```

### 2. .NET 8/9 Garbage Collector Tuning untuk High-Throughput
Konfigurasikan file `runtimeconfig.json` atau csproj untuk mengaktifkan **Server GC** dan **DATAS** (*Dynamic Adaptation to Application Sizes*):

```xml
<PropertyGroup>
  <ServerGarbageCollection>true</ServerGarbageCollection>
  <!-- Menyesuaikan ukuran heap secara elastis dengan beban kerja aktual -->
  <GCDynamicAdaptationMode>1</GCDynamicAdaptationMode>
  <!-- Nonaktifkan alokasi thread pool lambat jika aplikasi beroperasi di container CPU ketat -->
  <ThreadPoolMinThreads>100</ThreadPoolMinThreads>
</PropertyGroup>
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **mTLS (Mutual TLS) Service-to-Service:**
    Konfigurasikan Kestrel untuk memvalidasi sertifikat X.509 klien internal mesh:
    ```csharp
    builder.WebHost.ConfigureKestrel(options =>
    {
        options.ConfigureHttpsDefaults(httpsOptions =>
        {
            httpsOptions.ClientCertificateMode = ClientCertificateMode.RequireCertificate;
            httpsOptions.ClientCertificateValidation = (certificate, chain, errors) =>
            {
                // Validasi Thumbprint atau Custom CA Policy internal
                return certificate.Thumbprint.Equals("EXPECTED_INTERNAL_CA_THUMBPRINT", StringComparison.OrdinalIgnoreCase);
            };
        });
    });
    ```

2.  **Per-Client Rate Limiting Middleware Terdistribusi:**
    Cegah serangan Distributed Denial of Service (DDoS) dan noisy neighbors menggunakan token bucket per IP / API-Key yang diatur oleh `System.Threading.RateLimiting`:
    ```csharp
    builder.Services.AddRateLimiter(options =>
    {
        options.AddPolicy("PerUserPolicy", context =>
        {
            var identity = context.User.Identity?.Name ?? context.Connection.RemoteIpAddress?.ToString() ?? "anonymous";
            return RateLimitPartition.GetTokenBucketLimiter(identity, _ => new TokenBucketRateLimiterOptions
            {
                TokenLimit = 500,
                TokensPerPeriod = 100,
                ReplenishmentPeriod = TimeSpan.FromSeconds(1),
                QueueLimit = 0 // Langsung tolak jika kehabisan kuota
            });
        });
    });
    ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Kumpulkan telemetri standar OpenTelemetry untuk *Distributed Tracing* melintasi batasan jaringan menggunakan `ActivitySource`:

```csharp
using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

// 1. Definisikan ActivitySource untuk instrumentasi domain
public static class DiagnosticsConfig
{
    public const string SourceName = "Enterprise.OrderGateway";
    public static readonly ActivitySource Source = new(SourceName, "1.0.0");
}

// 2. Registrasi TracerProvider
builder.Services.AddOpenTelemetry()
    .WithTracing(tracerProviderBuilder =>
    {
        tracerProviderBuilder
            .AddSource(DiagnosticsConfig.SourceName)
            .SetResourceBuilder(ResourceBuilder.CreateDefault().AddService("OrderIngestionService"))
            .AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddOtlpExporter(opt => opt.Endpoint = new Uri("http://otel-collector:4317"));
    });

// 3. Penggunaan Tracing Manual di Hot Path
app.MapPost("/process", async (CancellationToken ct) =>
{
    using Activity? activity = DiagnosticsConfig.Source.StartActivity("IngestOrderActivity", ActivityKind.Internal);
    activity?.SetTag("custom.tier", "critical-path");

    try
    {
        // Simulasi kerja
        await Task.Delay(5, ct);
        activity?.SetStatus(ActivityStatusCode.Ok);
        return Results.Ok();
    }
    catch (Exception ex)
    {
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        activity?.RecordException(ex);
        throw;
    }
});
```

### CLI Diagnostic Commands
Gunakan tools diagnostik .NET CLI langsung pada container production yang bermasalah:

```bash
# Pantau throughput, GC pressure, dan ThreadPool saturation secara real-time
dotnet-counters monitor System.Runtime --process-id <PID>

# Lacak task deadlock atau thread pool starvation dengan dump thread stacks
dotnet-stack report --process-id <PID>

# Rekam trace alokasi CPU untuk dianalisis di Speedscope / PerfView
dotnet-trace collect --process-id <PID> --providers Microsoft-DotNETCore-SampleProfiler
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Aturan Emas Skalabilitas C#
*   **Asynchronous End-to-End:** Jangan pernah mencampur synchronous blocking (`.Result`, `.Wait()`) dengan async code.
*   **Bound Everything:** Setiap queue atau buffer dalam memori **wajib** memiliki batasan rigid (`BoundedChannel`).
*   **Zero-Alloc Hot Path:** Hindari alokasi objek heap dalam loop data tingkat tinggi menggunakan `Span<T>`, `ValueTask`, dan `ArrayPool<T>`.
*   **Propagate Tokens:** Jangan pernah membuat async API tanpa menerima `CancellationToken`.

### 2. Panduan Singkat API `System.Threading.Channels`

| Operasi | Non-Allocating / Async API | Keterangan |
| :--- | :--- | :--- |
| **Write** | `ValueTask WriteAsync(T item, CancellationToken ct)` | Suspends caller jika channel penuh (*backpressure*). |
| **Try Write** | `bool TryWrite(T item)` | Langsung kembali `false` jika channel penuh tanpa alokasi. |
| **Wait Write** | `ValueTask<bool> WaitToWriteAsync(CancellationToken ct)` | Menunggu ketersediaan slot antrean secara asinkron. |
| **Read** | `ValueTask<T> ReadAsync(CancellationToken ct)` | Menunggu data jika kosong. |
| **Try Read** | `bool TryRead(out T item)` | Membaca data seketika; ideal untuk pemrosesan bulk batch. |
| **Close** | `void Complete(Exception? error = null)` | Menutup channel; mencegah data baru masuk, data sisa tetap bisa dibaca. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Basic - Intermediate)

#### Basic
1. Apa akar penyebab terjadinya *ThreadPool Starvation* ketika Anda memanggil `.Result` pada `Task` yang belum selesai di ASP.NET Core?
   * A. Garbage Collector Gen 2 mematikan semua background worker.
   * B. Thread worker tertahan menunggu hasil kalkulasi, sementara algoritma Hill Climbing lambat mengalokasikan thread baru untuk mengurai antrean kerja.
   * C. Kestrel secara otomatis memutuskan koneksi socket jika sebuah thread dialokasikan lebih dari 10ms.
   * D. Memory leak terjadi di Large Object Heap (LOH).

2. Fitur `BoundedChannelOptions.SingleReader = true` memberikan keuntungan apa pada runtime?
   * A. Memastikan hanya ada satu proses OS yang dapat mengakses aplikasi.
   * B. Menghilangkan kebutuhan alokasi memori untuk entri antrean.
   * C. Mengoptimalkan operasi sinkronisasi antrean internal dengan mengeliminasi atomic CAS overhead yang biasanya dibutuhkan untuk multi-threading reader.
   * D. Mengunci thread caller sehingga tidak dapat menerima request HTTP lain.

3. Konfigurasi `BoundedChannelFullMode.Wait` bertujuan untuk:
   * A. Melempar eksepsi `ChannelClosedException` jika buffer penuh.
   * B. Menghapus item terlama secara otomatis dari antrean.
   * C. Menerapkan backpressure secara aman dengan menahan produsen secara asinkron sampai tersedia kapasitas di antrean.
   * D. Mengalokasikan array baru secara otomatis untuk memperbesar kapasitas buffer.

4. Manakah tipe pengembalian yang paling efisien untuk metode async hot-path yang sering kali selesai secara sinkron tanpa alokasi heap?
   * A. `Task<T>`
   * B. `void`
   * C. `ValueTask<T>`
   * D. `TaskCompletionSource<T>`

5. Dalam arsitektur Transactional Outbox, kapan event pesan dikirim ke message broker (misal Kafka/RabbitMQ)?
   * A. Sebelum transaksi database lokal dimulai.
   * B. Tepat di dalam blok transaksi database lokal sebelum `COMMIT`.
   * C. Secara asinkron oleh proses terpisah setelah transaksi database lokal berhasil di-`COMMIT`.
   * D. Menggunakan RPC call langsung di dalam controller.

---

#### Intermediate
6. Pada sistem skala besar dengan ribuan node mikroservis, mengapa pola retry *Exponential Backoff* **wajib** dipadukan dengan *Jitter*?
   * A. Untuk menghemat alokasi memori string di Garbage Collector.
   * B. Menghindari "Thundering Herd Problem", di mana ribuan instance melakukan retry serentak pada interval waktu yang sama sehingga kembali melumpuhkan downstream service.
   * C. Jitter mempercepat koneksi socket TCP dengan merangkum paket secara paralel.
   * D. Karena C# Compiler mewajibkan jitter pada setiap implementasi Polly v8.

7. Anda mendeteksi bahwa aplikasi .NET 8 di Kubernetes sering mengalami Restart akibat *OOMKilled* (Out Of Memory), meskipun throughput transaksi stabil. Pemeriksaan memory dump menunjukkan dominasi array byte berukuran 90KB. Mengapa ini terjadi?
   * A. Array tersebut masuk ke Small Object Heap (SOH) dan tidak pernah di-compact.
   * B. Array $\ge$ 85.000 byte dialokasikan di Large Object Heap (LOH), yang jarang dikompaksi oleh GC, menyebabkan fragmentasi memori virtual masif hingga container melebihi memory limit cgroup.
   * C. ThreadPool membuat thread melebihi kapasitas memori stack.
   * D. Channel in-memory bocor karena tidak menggunakan `ValueTask`.

8. Dalam implementasi Idempotent Consumer menggunakan Redis, mengapa operasi pemeriksaan dan penyimpanan kunci status transaksi harus bersifat atomik (misal: `StringSetAsync(..., When.NotExists)`)?
   * A. Mencegah alokasi heap di runtime ASP.NET Core.
   * B. Mencegah Race Condition di mana dua request identik yang datang bersamaan lolos dari pengecekan dan memicu eksekusi ganda sebelum kunci pertama sempat ditulis.
   * C. Menghindari koneksi Redis ditutup oleh timeout operating system.
   * D. Memaksa Kestrel menggunakan HTTP/3 alih-alih HTTP/2.

9. Apa perbedaan mendasar antara implementasi `ArrayPool<byte>.Shared.Rent(size)` dibanding inisialisasi biasa `new byte[size]`?
   * A. `ArrayPool` menyewa array dari pool memori yang dapat digunakan kembali untuk menghindari alokasi baru di GC Heap, dan ukuran array yang dikembalikan bisa jadi lebih besar dari ukuran yang diminta.
   * B. `ArrayPool` menjamin array yang dikembalikan tepat sesuai ukuran dan memorinya selalu diisi angka nol secara otomatis.
   * C. `ArrayPool` menyimpan memori secara eksklusif di CPU L1 Cache.
   * D. `ArrayPool` hanya dapat digunakan di thread utama (UI thread).

10. Ketika mengonfigurasi Polly v8 `CircuitBreakerStrategyOptions`, apa arti parameter `FailureRatio` sebesar 0.5 dengan `MinimumThroughput` sebesar 100?
    * A. Circuit breaker akan langsung putus jika 50 request pertama gagal berturut-turut.
    * B. Dalam sampling duration, sirkuit hanya akan mengevaluasi kondisi jika setidaknya ada 100 request, dan akan putus jika 50% atau lebih dari total request tersebut gagal.
    * C. Sirkuit membatasi throughput maksimal aplikasi menjadi 50 request per detik.
    * D. 50% thread di dalam ThreadPool akan dialihkan untuk menangani fallback logic.

---

### Kunci Jawaban & Pembahasan

1.  **Jawaban: B**
    *Pembahasan:* Memanggil `.Result` memblokir thread pemanggil secara sinkron. Jika beban tinggi, thread yang diblokir menumpuk. Algoritma Hill Climbing .NET sengaja membatasi injeksi thread baru (hanya 1-2 per detik) untuk menghindari *context switching overhead*, sehingga request antre hingga timeout massal.
2.  **Jawaban: C**
    *Pembahasan:* Pengetahuan bahwa konsumen bersifat tunggal mengizinkan internal channel menggunakan struktur data ring buffer lock-free yang lebih sederhana tanpa operasi atomik Interlocked multi-reader, yang memangkas latensi eksekusi CPU.
3.  **Jawaban: C**
    *Pembahasan:* `BoundedChannelFullMode.Wait` menunda execution context produsen melalui `ValueTask` asinkron ketika kapasitas penuh. Ini memaksa produsen menyesuaikan kecepatan dengan konsumen (backpressure).
4.  **Jawaban: C**
    *Pembahasan:* `ValueTask<T>` adalah `readonly struct`. Jika metode selesai secara sinkron (misal, hasil sudah ada di cache), tidak ada alokasi objek heap sama sekali di GC, berbeda dengan `Task<T>` yang selalu mengalokasikan objek Task di heap.
5.  **Jawaban: C**
    *Pembahasan:* Pola Transactional Outbox memisahkan persistensi data lokal dan transmisi broker. Pesan disimpan dalam tabel database yang sama dengan entitas bisnis, lalu proses worker asinkron membacanya dan mempublikasikan ke broker untuk menjamin konsistensi mutlak.
6.  **Jawaban: B**
    *Pembahasan:* Tanpa Jitter, semua klien yang mengalami kegagalan pada waktu $T$ akan serempak mengirim retry pada $T + \Delta t$, menyebabkan spike traffic periodik yang kembali merobohkan sistem downstream. Jitter menambahkan variasi acak untuk meratakan kurva distribusi beban retry.
7.  **Jawaban: B**
    *Pembahasan:* Objek berukuran $\ge 85.000$ byte dialokasikan langsung di Large Object Heap (LOH). GC default tidak melakukan pemadatan (compaction) pada LOH karena biayanya yang mahal, menyebabkan fragmentasi ruang alamat virtual memori yang memicu pembengkakan Private Bytes hingga pod dihentikan oleh OOMKilled Kubernetes.
8.  **Jawaban: B**
    *Pembahasan:* Operasi non-atomik (Cek dulu -> lalu Set) rentan terhadap *time-of-check to time-of-use* (TOCTOU) race condition. Dua thread paralel dapat membaca bahwa kunci belum ada secara simultan, lalu keduanya sama-sama menjalankan proses bisnis yang seharusnya tidak boleh terduplikasi.
9.  **Jawaban: A**
    *Pembahasan:* `ArrayPool<T>` menyewakan buffer array yang sudah ada dari bucket memori internal. Array ini sering kali lebih besar dari requested size dan dapat berisi data sisa (dirty bytes) dari pemakaian sebelumnya, sehingga pengembang wajib membersihkannya secara manual jika diperlukan dan hanya membaca sejumlah panjang data aktual yang diproses.
10. **Jawaban: B**
    *Pembahasan:* `MinimumThroughput` bertindak sebagai guard rail agar sirkuit tidak putus prematurely karena sampel data yang terlalu sedikit (misal: hanya 2 request masuk dan 1 gagal). Sirkuit baru aktif mengevaluasi jika kuota minimum request tercapai dalam satu jendela sampling.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul: High-Throughput Financial Ticketing Ingestion Gateway

#### Deskripsi Skenario:
Anda adalah Principal Systems Architect di bursa valuta terdesentralisasi. Anda diminta membangun subsistem *Order Ingestion Gateway* yang tahan banting untuk menerima jutaan pesanan transaksi mata uang dengan spesifikasi beban tinggi.

#### Kriteria Keberhasilan (Acceptance Criteria):
1.  **Endpoint API Ingestion:**
    *   Buat endpoint `POST /api/v1/orders/ingest` menggunakan ASP.NET Core Minimal API.
    *   Menerapkan zero-allocation JSON streaming deserialization menggunakan `System.IO.Pipelines` atau `ArrayPool<byte>`.
2.  **Backpressure & Buffering:**
    *   Integrasikan `System.Threading.Channels` dengan kapasitas rigid **20.000 elemen**.
    *   Konfigurasikan backpressure berjenis `Wait` untuk memastikan gateway tidak memuntahkan *OutOfMemoryException*.
3.  **Resilience Architecture (Polly v8):**
    *   Terapkan composite resilience pipeline:
        *   Concurrency Limiter: Maksimal 2.000 pemrosesan simultan.
        *   Circuit Breaker: Putus koneksi jika terjadi failure rate > 30% ke persistensi outbox.
        *   Timeout: Maksimum 300ms per operasi ingestion.
4.  **Idempotency Protection:**
    *   Cegah duplicate ingestion menggunakan Redis distributed caching (SET NX pattern).
5.  **Multi-Partitioned Outbox Consumer:**
    *   Bikin background service yang memproses antrean pesanan menggunakan **4 dedicated worker threads**.
    *   Setiap customer harus selalu diproses oleh worker yang sama berdasarkan hash dari `CustomerId` (*Deterministic In-Order Processing*).
6.  **Observabilitas:**
    *   Instrumentasikan gateway dengan OpenTelemetry `ActivitySource`. Catat tags: `customer.id`, `order.partition`, `batch.size`.

#### Verifikasi Pengujian (Load Testing):
Gunakan alat uji beban seperti `k6` atau `wrk` untuk menyimulasikan:
*   Beban: 50.000 request per detik selama 60 detik.
*   Uji ketahanan: Matikan downstream storage selama 5 detik, sirkuit harus terbuka (HTTP 503) seketika tanpa menumbangkan node ASP.NET Core, lalu pulih secara otomatis (*self-healing*) saat storage aktif kembali.