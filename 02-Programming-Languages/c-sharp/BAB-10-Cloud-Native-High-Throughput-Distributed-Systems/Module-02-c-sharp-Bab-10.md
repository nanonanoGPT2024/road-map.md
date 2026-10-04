# BAB 10: Cloud-Native High-Throughput Distributed Systems
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *Virtual Actor* menggunakan Microsoft Orleans 8.x pada lingkungan Kubernetes untuk mengelola *stateful distributed compute* dengan *turn-based concurrency*.
- Membangun *data pipeline* berkecepatan tinggi (*sub-millisecond latency*) memanfaatkan `System.IO.Pipelines` dan `System.Threading.Channels` guna meniadakan alokasi memori (*zero-allocation*) dan *Gen-2 GC pressure*.
- Mengimplementasikan pola *Transactional Outbox* dan *Idempotent Consumer* berbasis Change Data Capture (CDC) dan MassTransit untuk menjamin konsistensi data *eventual consistency* (*Guaranteed At-Least-Once Delivery*).
- Mengonfigurasi mitigasi *tail latency* (P99/P99.9), strategi *partition handling*, dan *backpressure propagation* pada sistem terdistribusi berskala ratusan ribu transaksi per detik (TPS).

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, Anda wajib menguasai:
- **C# 12 & .NET 8 Runtime Internals**: Eksekusi `ValueTask`, `Span<T>`, `Memory<T>`, `Unsafe`, serta siklus hidup *Garbage Collection* (Server GC, Non-Concurrent vs Concurrent GC, Dynamic Adaptation to Application Sizes / DATAS).
- **Asynchronous Plumbing**: Cara kerja `SynchronizationContext`, `TaskScheduler`, dan bahaya *thread pool starvation* akibat *sync-over-async*.
- **Distributed Systems Core**: CAP & PACELC Theorem, *Vector Clocks*, *Consensus Protocol* (Raft/Paxos), *Distributed Locking*, dan *Split-Brain Syndrome*.
- **Tools & Infrastruktur**: Docker, Kubernetes, PostgreSQL/CockroachDB, Apache Kafka, dan OpenTelemetry.

---

### 3. Concept & Internal Architecture (Mendalam)

Membangun sistem terdistribusi *cloud-native* berkinerja tinggi menuntut perubahan paradigma dari pendekatan monolitik *stateless-service-with-shared-database* ke arah *partitioned stateful computing* dan *reactive asynchronous streaming*.

```
+-----------------------------------------------------------------------------------+
|                              ORLEANS SILO HOST (NODE)                             |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                           GRAIN DIRECTORY (DHT)                             |  |
|  |  Memetakan GrainId -> Silo Address (Consistent Hashing / Distributed Table) |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  |                             GRAIN ACTIVATION CACHE                          |  |
|  |  +---------------------------------+   +---------------------------------+  |  |
|  |  |      OrderGrain (Activation A)  |   |     WalletGrain (Activation B)  |  |  |
|  |  |  - Single-Threaded Execution    |   |  - Single-Threaded Execution    |  |  |
|  |  |  - Turn-Based Concurrency Queue |   |  - Turn-Based Concurrency Queue |  |  |
|  |  |  - In-Memory Grain State        |   |  - In-Memory Grain State        |  |  |
|  |  +---------------------------------+   +---------------------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v (Async Write Behind / Outbox)           |
|  +-----------------------------------------------------------------------------+  |
|  |                      STORAGE ADAPTER / TRANSACTION LOG                      |  |
|  |          PostgreSQL State Table & Outbox Messages (CDC Log Engine)          |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### A. Internal Runtime Virtual Actor (Microsoft Orleans 8)
Pada sistem *actor* tradisional (seperti Akka.NET atau Erlang), aktor harus dibuat, dialokasikan, dan dihancurkan secara eksplisit. Jika node tempat aktor berjalan mati, sistem harus menangani *supervision strategy* secara manual.

Microsoft Orleans mengabstraksi aktor menjadi **Virtual Actor (Grain)**:
1. **Grain Identity & Activation**: Grain diidentifikasi oleh kunci deterministik (`Guid`, `long`, atau `string`). Grain tidak dibuat secara manual; Grain selalu "ada" secara virtual. Ketika sebuah pesan ditujukan ke Grain ID tertentu, Orleans memeriksa **Grain Directory**. Jika aktivasi belum ada di memori Silo manapun, Silo akan memicu aktivasi: memuat *state* dari database persistensi dan menempatkannya di Silo dengan beban terendah (*Placement Strategy: Random, PreferLocal, atau ActivationCountBased*).
2. **Turn-Based Concurrency**: Setiap aktivasi Grain bersifat *single-threaded* secara logis. Orleans menjamin bahwa hanya satu *turn* (metode/pemanggilan pesan) yang dieksekusi pada satu waktu di dalam satu Grain. Ini mengeliminasi kebutuhan penggunaan primitif sinkronisasi seperti `lock`, `Monitor`, atau `Mutex` di dalam kode bisnis Anda.
3. **Deactivation & Garbage Collection**: Jika sebuah Grain tidak menerima panggilan dalam jangka waktu tertentu (default: 1 jam), runtime Orleans akan menonaktifkannya (*deactivate*) dan menghapus instansnya dari RAM untuk membebaskan memori Silo.

#### B. Zero-Allocation Ingestion Engine (`System.IO.Pipelines`)
Pendekatan tradisional `Stream.ReadAsync(byte[] buffer)` menghasilkan alokasi array berulang yang memaksa Garbage Collector bekerja keras di Gen 0/Gen 1, bahkan Gen 2 jika array berukuran lebih dari 85.000 byte (Large Object Heap). 

`System.IO.Pipelines` memisahkan alokasi memori dari logika konsumsi melalui `PipeReader` dan `PipeWriter`. Runtime mengelola ring buffer terkelola (`MemoryPool<byte>`), memungkinkan parser membaca data streaming (seperti HTTP/2 frame atau raw TCP packet) secara langsung di memory pointer tanpa alokasi buffer baru:
- `PipeWriter` menyewakan segmen memori dari pool terpusat.
- Parsing biner dilakukan langsung menggunakan `ReadOnlySequence<byte>` dan `SequenceReader<byte>`.
- `PipeReader.AdvanceTo(consumed, examined)` memberi tahu runtime segmen memori mana yang telah selesai diproses dan siap dikembalikan ke *pool*, menghilangkan *allocations overhead* secara total.

---

### 4. Why & What

| Dimensi | Paradigma Klasik (CRUD Stateless + Cache) | Paradigma Modern (Cloud-Native Actor + Outbox) |
| :--- | :--- | :--- |
| **Concurrency Model** | Pesimistik / Optimistik Locking langsung di Database Relasional. Rawan *deadlock*. | *Single-threaded turn-based execution* pada memori Grain. Nol *lock contention*. |
| **State Management** | State ditarik dari DB/Redis di setiap request, lalu disimpan kembali (High I/O Overhead). | In-Memory Working Set pada Silo. State ditulis secara asinkron atau terjadwal. |
| **Data Consistency** | Dual-write problem: Update DB dan kirim pesan ke Kafka secara manual (rawan desinkronisasi). | *Transactional Outbox Pattern* terikat satu transaksi atomik lokal di tingkat database engine. |
| **Memory Footprint** | Banyak alokasi `byte[]`, parsing JSON/XML via string intermediate (GC Spikes). | Zero-allocation streams (`System.IO.Pipelines`, `ReadOnlySpan<byte>`), minim alokasi heap. |
| **Throughput Scaling** | Horizontal stateless scaling terbatas oleh *connection pooling* dan lock database terpusat. | Sharding terdistribusi otomatis di memori puluhan Silo (*Dynamic Grain Partitioning*). |

---

### 5. How (Workflow Detail)

Alur kerja pemrosesan transaksi berkecepatan tinggi dengan jaminan konsistensi data mutlak:

```
[Client / API Gateway]
         │
         │ 1. gRPC / Fast Ingestion (Pipelines)
         ▼
[Ingestion Pipeline Controller]
         │
         │ 2. Route via GrainFactory.GetGrain<IOrderGrain>(orderId)
         ▼
[Orleans Silo Cluster]
  ┌────────────────────────────────────────────────────────┐
  │ IOrderGrain Activation (In-Memory)                     │
  │                                                        │
  │ 3. Eksekusi Validasi State & Mutasi Logika Bisnis       │
  │ 4. Siapkan Domain Event & Outbox Record               │
  │ 5. Tulis Atomic Transaction (Grain State + Outbox Msg) │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
              [PostgreSQL Database Storage]
                 - Table: "GrainState"
                 - Table: "OutboxMessages"
                             │
                             │ 6. Polling Relayer / CDC Worker (Debezium/OutboxProcessor)
                             ▼
                  [Apache Kafka Cluster]
                             │
                             │ 7. Idempotent Consumer
                             ▼
                [Downstream Microservices]
```

1. **Ingestion Layer**: Permintaan eksternal diterima melalui soket TCP performa tinggi menggunakan `PipeReader`. Payload dibaca langsung ke `ReadOnlySpan<byte>` tanpa alokasi string intermediat.
2. **Grain Routing**: Runtime memetakan identitas transaksi ke Silo target menggunakan DHT (Distributed Hash Table) tanpa membebani basis data terpusat.
3. **Turn Execution**: Transaksi dieksekusi secara terisolasi di memori Silo. Karena berjalan dalam *single-turn*, tidak ada thread lain yang dapat memodifikasi state Grain tersebut secara simultan.
4. **Atomic Local Commit**: Grain menyimpan perubahan state dan event keluaran ke dalam tabel *Outbox* dalam **satu transaksi database lokal tunggal** (`NpgsqlTransaction`).
5. **Event Dispatching**: Background worker memproses *Outbox* dan mendistribusikan pesan ke message broker (Kafka/RabbitMQ) dengan jaminan *At-Least-Once*.
6. **Consumer Idempotency**: Layanan penerima mengecek deduplikasi record menggunakan *message deduplication key* sebelum mengeksekusi logika bisnis turunan.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi: Meja Kasir Eksklusif (Virtual Actor) vs Antrean Perebutan Buku Besar (Stateless + DB Lock)
- **Stateless + DB Locking**: Bayangkan 1.000 akuntan mencoba mencatat pengeluaran dari 1 rekening yang sama. Setiap kali ingin mencatat, akuntan harus berebut fisik buku besar, mengunci buku tersebut, menulis angka, membuka kunci, lalu kembali ke meja. Jika 100 akuntan berebut sekaligus, sistem macet karena antrean kunci (*database contention*).
- **Virtual Actor**: Rekening tersebut memiliki seorang sekretaris pribadi (Grain). Sekretaris tersebut duduk di mejanya sendiri dan memegang buku rekening tersebut di tangannya. Kapan pun ada 1.000 akuntan yang ingin mencatat transaksi, mereka hanya mengirimkan secarik kertas nota ke kotak masuk sekretaris. Sekretaris memproses nota tersebut satu demi satu secara berurutan (*turn-based concurrency*). Cepat, tanpa perebutan, dan tidak ada data yang bertabrakan.

#### B. Diagram: Pipelines Memory Pooling vs Stream Biasa

```
Alur Stream Klasik (Banyak Alokasi & GC Heavy):
[Socket] ──> new byte[4096] ──> GC Gen 0 ──> new byte[8192] ──> GC Gen 1 ──> Memory Leak!

Alur System.IO.Pipelines (Zero-Allocation Memory Leased Ring):
[Socket]
   │
   ▼ Write Memory Block (Leased from MemoryPool)
┌────────────────────────────────────────────────────────┐
│ Buffer Segment 1 │ Buffer Segment 2 │ Buffer Segment 3 │ (Koleksi Memory<byte>)
└────────────────────────────────────────────────────────┘
   │
   ▼ AdvanceTo(consumed, examined)
[Parser Engine] ──> Membaca ReadOnlySequence<byte> ──> Mengembalikan Blok ke Pool
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory High-Throughput Pipeline dengan `System.Threading.Channels`
Contoh berikut mengimplementasikan pipeline pemrosesan *in-memory* dengan *backpressure handling* menggunakan `BoundedChannel` untuk mencegah ledakan penggunaan memori (*Out Of Memory*).

```csharp
using System.Threading.Channels;

namespace DistributedCore.Channels;

public sealed class IngestionEngine
{
    private readonly Channel<TransactionEvent> _channel;

    public IngestionEngine(int capacity = 100_000)
    {
        // Pola Bounded Channel krusial untuk mencegah OOM jika worker mengalami bottleneck
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait, // Backpressure: Tahan producer jika buffer penuh
            SingleReader = false,
            SingleWriter = false
        };
        _channel = Channel.CreateBounded<TransactionEvent>(options);
    }

    public async ValueTask PublishAsync(TransactionEvent ev, CancellationToken ct = default)
    {
        // Menulis langsung ke channel secara asinkron tanpa locking primitif
        await _channel.Writer.WriteAsync(ev, ct);
    }

    public async Task StartConsumerAsync(Func<TransactionEvent, ValueTask> processHandler, CancellationToken ct)
    {
        // Konsumsi paralel dengan streaming IAsyncEnumerable
        await foreach (var item in _channel.Reader.ReadAllAsync(ct))
        {
            try
            {
                await processHandler(item);
            }
            catch (Exception ex)
            {
                // Error boundary per item untuk mengisolasi kegagalan
                Console.Error.WriteLine($"[Error Worker] ID: {item.TransactionId}, Ex: {ex.Message}");
            }
        }
    }
}

public readonly record struct TransactionEvent(Guid TransactionId, decimal Amount, long Timestamp);
```

#### B. Practical Example: Production-Grade Orleans Grain dengan Transactional Outbox Pattern

Implementasi industri untuk sistem reservasi saldo dompet digital (*Wallet Ledger*) dengan Orleans 8 dan Entity Framework Core Outbox.

**1. Definisi Kontrak dan State Grain**

```csharp
using Orleans;

namespace DistributedLedger.Grains;

[GenerateSerializer]
public sealed class WalletState
{
    [Id(0)] public decimal CurrentBalance { get; set; }
    [Id(1)] public long Version { get; set; }
}

public interface IWalletGrain : IGrainWithGuidKey
{
    Task<bool> ReserveBalanceAsync(Guid reservationId, decimal amount);
    Task<decimal> GetBalanceAsync();
}
```

**2. Implementasi Grain dengan Turn-Based Concurrency**

```csharp
using Microsoft.Extensions.Logging;
using Orleans.Providers;

namespace DistributedLedger.Grains;

[StorageProvider(ProviderName = "PostgreSqlStorage")]
public sealed class WalletGrain : Grain, IWalletGrain
{
    private readonly IPersistentState<WalletState> _state;
    private readonly ILogger<WalletGrain> _logger;

    public WalletGrain(
        [PersistentState("walletState", "PostgreSqlStorage")] IPersistentState<WalletState> state,
        ILogger<WalletGrain> logger)
    {
        _state = state;
        _logger = logger;
    }

    public override Task OnActivateAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Aktivasi Wallet Grain: {GrainId}", this.GetPrimaryKey());
        return base.OnActivateAsync(cancellationToken);
    }

    public async Task<bool> ReserveBalanceAsync(Guid reservationId, decimal amount)
    {
        // Eksekusi ini dijamin thread-safe oleh Orleans Runtime (Single Turn Execution)
        if (amount <= 0)
            throw new ArgumentOutOfRangeException(nameof(amount), "Nilai reservasi harus positif.");

        if (_state.State.CurrentBalance < amount)
        {
            _logger.LogWarning("Saldo tidak mencukupi untuk Wallet {GrainId}. Permintaan: {Amount}, Tersedia: {Balance}",
                this.GetPrimaryKey(), amount, _state.State.CurrentBalance);
            return false;
        }

        // Mutasi state in-memory
        _state.State.CurrentBalance -= amount;
        _state.State.Version++;

        // Menulis state ke persistensi database (Snapshot)
        await _state.WriteStateAsync();

        _logger.LogInformation("Reservasi berhasil. Wallet: {GrainId}, ResId: {ReservationId}, Sisa: {Balance}",
            this.GetPrimaryKey(), reservationId, _state.State.CurrentBalance);

        return true;
    }

    public Task<decimal> GetBalanceAsync() => Task.FromResult(_state.State.CurrentBalance);
}
```

**3. Implementasi Transactional Outbox Relayer Service (Background Processing)**

```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System.Text.Json;

namespace DistributedLedger.Outbox;

public sealed class OutboxMessage
{
    public Guid Id { get; init; }
    public string EventType { get; init; } = default!;
    public string Payload { get; init; } = default!;
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? ProcessedAtUtc { get; set; }
    public string? ErrorTrace { get; set; }
}

public sealed class LedgerDbContext : DbContext
{
    public LedgerDbContext(DbContextOptions<LedgerDbContext> options) : base(options) { }
    public DbSet<OutboxMessage> OutboxMessages => Set<OutboxMessage>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<OutboxMessage>(b =>
        {
            b.HasKey(x => x.Id);
            b.HasIndex(x => x.ProcessedAtUtc)
             .HasFilter("\"ProcessedAtUtc\" IS NULL"); // Partial index performa tinggi
        });
    }
}

public sealed class OutboxRelayWorker : BackgroundService
{
    private readonly IDbContextFactory<LedgerDbContext> _contextFactory;
    private readonly ILogger<OutboxRelayWorker> _logger;

    public OutboxRelayWorker(
        IDbContextFactory<LedgerDbContext> contextFactory,
        ILogger<OutboxRelayWorker> logger)
    {
        _contextFactory = contextFactory;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Outbox Relay Worker Engine berjalan.");

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await using var context = await _contextFactory.CreateDbContextAsync(stoppingToken);

                // Polling berbasis batch dengan locking baris (SKIP LOCKED) untuk konkurensi antar relayer
                var pendingMessages = await context.OutboxMessages
                    .FromSqlRaw(
                        """
                        SELECT * FROM "OutboxMessages"
                        WHERE "ProcessedAtUtc" IS NULL
                        ORDER BY "CreatedAtUtc" ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 100
                        """)
                    .ToListAsync(stoppingToken);

                if (pendingMessages.Count == 0)
                {
                    await Task.Delay(250, stoppingToken); // Hindari CPU spinning saat antrean kosong
                    continue;
                }

                foreach (var message in pendingMessages)
                {
                    // Simulasi dispatch ke Apache Kafka
                    await RelayToBrokerAsync(message, stoppingToken);
                    message.ProcessedAtUtc = DateTime.UtcNow;
                }

                await context.SaveChangesAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Gagal memproses batch pada Outbox Relay Engine.");
                await Task.Delay(1000, stoppingToken);
            }
        }
    }

    private Task RelayToBrokerAsync(OutboxMessage message, CancellationToken ct)
    {
        // Contoh stub integrasi Kafka producer
        _logger.LogInformation("Dispatched ke Event Hub/Kafka: {Id} - {Type}", message.Id, message.EventType);
        return Task.CompletedTask;
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Pembayaran Skala Ultra (Flash Sale & Core Banking)
- **Konteks**: Layanan e-commerce terkemuka mengalami lonjakan 250.000 permintaan reservasi saldo per detik saat kampanye diskon kilat tahunan. Arsitektur sebelumnya (ASP.NET Core Stateless API + PostgreSQL Transaction Locking) mengalami *thread starvation*, lonjakan *connection pool exhaustion*, dan kegagalan transaksi berantai akibat *lock contention* pada baris akun *merchant* utama.
- **Solusi Arsitektur**:
  1. **Migrasi ke Microsoft Orleans 8 Cluster**: Setiap *Merchant* dan *User Balance* diubah menjadi satu *Virtual Grain*. Permintaan transaksi dialirkan ke Grain spesifik.
  2. **In-Memory Balancing**: Grain melakukan reservasi kredit secara instan di memori, mencatat perubahan ke PostgreSQL melalui pola *Write-Behind Storage* dengan interval per 100 milidetik, menggantikan *pessimistic DB lock*.
  3. **Zero-Copy Serialization**: Mengganti protokol JSON over HTTP/1.1 dengan gRPC over HTTP/2, memanfaatkan deserializer biner tergenerasi otomatis dari Orleans (`[GenerateSerializer]`).
- **Hasil Terverifikasi**:
  - P99.9 Latency terpangkas dari **4.200 ms** menjadi **11 ms**.
  - Beban komputasi basis data berkurang sebesar **85%** karena penghapusan *deadlock resolution cycles*.
  - Menghilangkan *double-spending* sebesar 100% berkat garansi *single-threaded turn-based concurrency* pada setiap Grain.

---

### 9. Trade-offs

Setiap keputusan arsitektur memiliki konsekuensi struktural:

```
                  KONSISTENSI KUAT (ACID)
                         /\
                        /  \
                       /    \
                      /      \  Pola: Stateless API + RDBMS Locking
                     /   B    \  - Latensi P99 Tinggi
                    /          \ - Bottleneck Skalabilitas
                   /            \
                  /      A       \
                 /                \
                /                  \
KETERSEDIAAN TINGGI (AP) ──────────── LATENSI RENDAH & THROUGHPUT MAKSIMAL
Pola: Event-Driven Kafka             Pola: Orleans In-Memory Virtual Actors
- Konsistensi Lemah                  - Single Point of Serialization
- Kompleksitas Rekonsiliasi          - Memori Node Besar (RAM Heavy)
```

| Pendekatan | Keuntungan Utama | Biaya / Kerugian |
| :--- | :--- | :--- |
| **Virtual Actors (Orleans)** | - Tidak ada lock contention.<br>- Latensi pemrosesan memori ultra-rendah.<br>- Skalabilitas elastis otomatis. | - State memory footprint tinggi pada Silo.<br>- Split-brain hazard jika konfigurasi konsensus cluster gagal.<br>- Sulit melakukan ad-hoc complex cross-grain queries. |
| **Transactional Outbox (RDBMS)** | - Jaminan At-Least-Once Delivery mutlak.<br>- Tidak ada dual-write inconsistency.<br>- Mendukung audit trail otomatis. | - Overhead disk I/O konstan.<br>- Polling delay / CDC engine latency overhead.<br>- Tabel outbox membengkak jika relayer tersendat. |
| **Zero-Allocation Pipelines** | - Menghilangkan 90%+ GC pressure Gen 0/1/2.<br>- Latensi socket P99.9 sangat stabil. | - Kompleksitas kode tinggi.<br>- Wajib tracking lifecycle pointer/memory leasing secara manual (rawan *use-after-free*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Sinkronisasi Blokir di dalam Grain (*Sync-over-Async*)
- **Kesalahan Fatal**: Memanggil `.Result`, `.Wait()`, atau `Thread.Sleep()` di dalam Grain method.
- **Dampak**: Orleans Runtime Context terikat secara kooperatif. Pemanggilan sinkron akan memblokir thread Silo, menghentikan eksekusi ratusan Grain lain yang dijadwalkan pada thread pekerja yang sama, memicu kaskade *Silo Deadlock Timeout*.
- **Solusi**: Selalu gunakan `await`, return `ValueTask` atau `Task`, dan gunakan `Task.Delay()` alih-alih `Thread.Sleep()`.

#### 2. Re-entrancy Bugs & State Corruption
- **Kesalahan Fatal**: Menandai grain dengan atribut `[Reentrant]` tanpa proteksi, kemudian melakukan mutasi state lokal setelah statement `await` eksternal.
```csharp
// BAHAYA BESAR
[Reentrant]
public async Task MutateStateUnsafe()
{
    var current = this.State.Balance;
    await ExternalServiceCallAsync(); // Panggilan asinkron melepaskan lock turn!
    this.State.Balance = current + 10; // State.Balance asli mungkin sudah diubah turn lain!
}
```
- **Solusi**: Hindari `[Reentrant]` jika memungkinkan. Jika terpaksa digunakan untuk *read-only methods*, pisahkan mutasi state ke metode non-reentrant terpisah.

#### 3. Diagnostic Commands untuk Troubleshooting Produksi
Deteksi *memory leak* dan *thread starvation* pada Silo .NET:

```bash
# 1. Analisis alokasi memory heap secara real-time
dotnet-counters monitor --process-id <PID> --counters System.Runtime,Microsoft.Orleans

# 2. Ambil dump memori Silo yang hang untuk memeriksa deadlock turn Orleans
dotnet-dump collect --process-id <PID> --type Full

# 3. Analisis SOS thread pool queues
dotnet-dump analyze dump_core.dmp
> clrstack -all
> dumpasync -stacks
```

---

### 11. Best Practices (Production Checklist)

#### Runtime Engine & Host Configuration
- [ ] Aktifkan `ServerGarbageCollection` dan `GarbageCollectionAdaptationMode` (DATAS) di `runtimeconfig.json` untuk adaptasi memori dinamis di container Kubernetes.
- [ ] Konfigurasi Orleans Silo Clustering menggunakan provider konsisten tinggi (misal: AWS DynamoDB, Azure Table, atau PostgreSQL/Kubernetes API), **jangan pernah** gunakan membership berbasis multicast di produksi.
- [ ] Atur batas `ResponseTimeout` pada Orleans Messaging (default: 30 detik, disarankan: 5–8 detik untuk deteksi cepat kegagalan downstream).

#### Storage & Outbox Reliability
- [ ] Pasang partial index pada kolom status/waktu di tabel Outbox (misal: `WHERE "ProcessedAtUtc" IS NULL`).
- [ ] Terapkan `FOR UPDATE SKIP LOCKED` pada relayer worker untuk mencegah perebutan *row-level locks* jika memiliki banyak instans background reader.
- [ ] Implementasikan strategi pembersihan data historis (*data pruning/retention policy*) untuk pesan outbox yang telah terkirim guna menjaga ukuran indeks DB tetap kecil di memory cache.

---

### 12. Hands-on Practice

Implementasikan sistem *Distributed Counter & Rate Limiter Engine* berkinerja tinggi menggunakan template hands-on berikut.

#### Langkah 1: Inisialisasi Project Cluster
Jalankan perintah berikut di direktori `hands-on/m02/`:

```bash
mkdir -p hands-on/m02/src
cd hands-on/m02/src

# Buat Project Orleans Host
dotnet new console -n DistributedCounter.Host
cd DistributedCounter.Host
dotnet add package Microsoft.Orleans.Server --version 8.2.0
dotnet add package Microsoft.Extensions.Hosting --version 8.0.0
dotnet add package OpenTelemetry.Extensions.Hosting --version 1.8.1
```

#### Langkah 2: Buat Grain Implementation
Tambahkan file `CounterGrain.cs`:

```csharp
using Orleans;

namespace DistributedCounter.Host;

public interface ICounterGrain : IGrainWithStringKey
{
    ValueTask<long> IncrementAsync(long amount);
    ValueTask<long> GetValueAsync();
}

[GenerateSerializer]
public sealed class CounterState
{
    [Id(0)] public long Value { get; set; }
}

public sealed class CounterGrain : Grain, ICounterGrain
{
    private long _cachedValue;

    public override Task OnActivateAsync(CancellationToken cancellationToken)
    {
        _cachedValue = 0;
        return base.OnActivateAsync(cancellationToken);
    }

    public ValueTask<long> IncrementAsync(long amount)
    {
        _cachedValue += amount;
        return ValueTask.FromResult(_cachedValue);
    }

    public ValueTask<long> GetValueAsync()
    {
        return ValueTask.FromResult(_cachedValue);
    }
}
```

#### Langkah 3: Konfigurasi Silo Host & Benchmark Client
Edit file `Program.cs`:

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Orleans.Configuration;
using Orleans.Hosting;
using System.Diagnostics;
using DistributedCounter.Host;

var builder = Host.CreateDefaultBuilder(args)
    .UseOrleans(siloBuilder =>
    {
        siloBuilder.UseLocalhostClustering();
        siloBuilder.Configure<ClusterOptions>(options =>
        {
            options.ClusterId = "prod-cluster-01";
            options.ServiceId = "CounterService";
        });
        siloBuilder.ConfigureLogging(logging => logging.SetMinimumLevel(LogLevel.Warning));
    });

using var host = builder.Build();
await host.StartAsync();

Console.WriteLine("=== Silo Active. Starting High-Throughput Load Benchmark ===");

var client = host.Services.GetRequiredService<IGrainFactory>();
const int totalRequests = 100_000;
const int concurrentTasks = 50;

var stopwatch = Stopwatch.StartNew();

await Parallel.ForEachAsync(
    Enumerable.Range(0, totalRequests),
    new ParallelOptions { MaxDegreeOfParallelism = concurrentTasks },
    async (i, ct) =>
    {
        // Distribusikan ke 100 grain berbeda secara hash
        var grainKey = $"counter_partition_{i % 100}";
        var grain = client.GetGrain<ICounterGrain>(grainKey);
        await grain.IncrementAsync(1);
    });

stopwatch.Stop();

Console.WriteLine($"Eksekusi {totalRequests} request selesai.");
Console.WriteLine($"Total Waktu: {stopwatch.ElapsedMilliseconds} ms");
Console.WriteLine($"Throughput: {(totalRequests / (stopwatch.ElapsedMilliseconds / 1000.0)):F0} Ops/Sec");

var verifyGrain = client.GetGrain<ICounterGrain>("counter_partition_0");
var sampleValue = await verifyGrain.GetValueAsync();
Console.WriteLine($"Verifikasi Nilai Partition 0: {sampleValue}");

await host.StopAsync();
```

Jalankan pengujian menggunakan:
```bash
dotnet run -c Release
```

---

### 13. Exercise

#### Level 1 - Easy: Bounded Channel Event Broadcaster
- **Tugas**: Buat kelas `MemoryBroadcaster<T>` menggunakan `System.Threading.Channels`.
- **Spesifikasi**: 
  - Gunakan `BoundedChannelOptions` dengan kapasitas 500 item dan mode `BoundedChannelFullMode.DropOldest`.
  - Sediakan metode `ValueTask PublishAsync(T item)` dan `IAsyncEnumerable<T> SubscribeAsync(CancellationToken ct)`.
  - Pastikan tidak ada thread blocking yang terjadi saat alur konsumsi lebih lambat dari produksi.

#### Level 2 - Medium: Transactional Outbox Unit of Work Interceptor
- **Tugas**: Buatlah EF Core Interceptor (`SaveChangesInterceptor`) yang secara otomatis menyadap entitas agregat yang mengimplementasikan `IHaveDomainEvents`.
- **Spesifikasi**:
  - Saat `SavingChangesAsync` dipanggil, ekstrak semua event internal domain dari entity tracker.
  - Serialisasikan event tersebut ke format JSON menggunakan zero-allocation UTF-8 bytes writer.
  - Masukkan ke DbSet `OutboxMessages` secara implisit dalam transaksi SQL yang sama sebelum operasi commit database terjadi.

#### Level 3 - Hard: Orleans Distributed Lock Grain with Auto-Renewal Lease & Fencing Token
- **Tugas**: Bangun sistem Distributed Lock berbasis Orleans Grain (`ILockGrain`).
- **Spesifikasi**:
  - Grain mengizinkan satu caller mengklaim kunci kepemilikan (*lease*) selama $N$ detik.
  - Setiap kali lock diberikan, Grain menghasilkan *monotonically increasing number* (**Fencing Token**).
  - Jika pemilik kunci tidak memperbarui *heartbeat* sebelum batas sewa habis, Grain secara sepihak membatalkan kepemilikan dan mengizinkan antrean caller berikutnya untuk mengklaim kunci dengan Fencing Token baru yang lebih tinggi.

---

### 14. Challenge

**Skenario**: Sistem Bursa Aset Kripto Terdesentralisasi (Matching Engine) membutuhkan engine pencocokan order (*Limit Order Book*) dengan throughput 500.000 order per detik dengan persistensi anti-data loss.

**Spesifikasi Teknis**:
1. Rancang pasangan *Symbol* (misal: `BTC_USDT`) sebagai Grain Orleans tunggal atau terpartisi (Sharded Partition).
2. Setiap transaksi pencocokan buku order tidak boleh menggunakan *locks* sinkron primitif. Seluruh order matching dieksekusi murni di RAM.
3. Seluruh order yang cocok (*trades executed*) harus dialirkan ke downstream ledger tanpa memperlambat matching engine utama. Gunakan teknik *In-Memory Disruptor Pattern / Ring Buffer Channel* yang menjamin P99.9 latency di bawah 2 ms.
4. Implementasikan pemulihan state instan jika node Silo mati mendadak (*Crash Recovery*) menggunakan *Event Sourcing snapshotting* yang mampu membaca 1.000.000 snapshot records dalam waktu kurang dari 1,5 detik saat aktivasi Grain.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa Virtual Actor pada Microsoft Orleans tidak membutuhkan siklus instansiasi dan penghancuran eksplisit oleh developer?
2. Apa dampak teknis penggunaan `BoundedChannelFullMode.Wait` dibandingkan `BoundedChannelFullMode.DropWrite` ketika buffer channel telah penuh?
3. Sebutkan kelemahan utama penggunaan `Stream.ReadAsync(byte[] buffer)` dibandingkan parsing memori terkelola via `System.IO.Pipelines`!
4. Apa fungsi dari klausa `FOR UPDATE SKIP LOCKED` pada kueri basis data relasional saat membaca tabel Transactional Outbox?
5. Mengapa pemanggilan `Task.Result` atau `.Wait()` di dalam metode Grain Orleans dapat mengakibatkan *cluster-wide freeze*?

#### B. Pertanyaan Intermediate
6. Bagaimana cara runtime Orleans menjamin *thread-safety* dari state internal sebuah Grain tanpa memerlukan kata kunci `lock` di dalam kode aplikasi?
7. Dalam kondisi jaringan apa sebuah kluster Orleans dapat mengalami *split-brain*, dan mekanisme internal apa yang digunakan untuk mitigasi hal tersebut?
8. Bagaimana struktur data `ReadOnlySequence<byte>` pada `System.IO.Pipelines` menangani frame data jaringan yang terfragmentasi di beberapa blok memori non-kontigu?
9. Apa perbedaan esensial dari garansi konsistensi pengiriman data antara *At-Least-Once Delivery* via Outbox Pattern versus *Exactly-Once Processing*?
10. Mengapa pembaruan *state* in-memory Grain yang dieksekusi setelah pemanggilan metode asinkron lain pada Grain beranotasi `[Reentrant]` berpotensi menghasilkan data corrupt (*race condition*)?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah Silo Orleans di lingkungan Kubernetes tiba-tiba dihentikan (*OOMKilled*) oleh kernel Linux karena penggunaan memori melebihi 4 GB, padahal transaksi bisnis per detik sedang normal. Hasil dump menunjukkan penumpukan jutaan objek di Gen 2 GC. Analisis apa akar masalahnya di level alokasi C# dan langkah apa yang harus diambil untuk mengatasinya?
12. **Skenario 2**: Sistem *payment processing* Anda menggunakan Transactional Outbox Pattern dengan polling SQL setiap 100 ms. Namun downstream broker mendeteksi terjadinya lonjakan pesan duplikat sebesar 12% ketika transaksi mencapai 50.000 TPS, yang memicu masalah pada downstream service. Identifikasi titik kegagalan (*failure point*) dan rancang solusinya!
13. **Skenario 3**: Dua Silo Orleans berada dalam zona jaringan berbeda (Multi-AZ). Terjadi degradasi jaringan berkala di mana latensi komunikasi antar Silo melonjak dari 1 ms ke 850 ms. Grain Client mulai memunculkan `TimeoutException` masif. Bagaimana arsitektur Silo Placement Strategy dan Grain Messaging Configuration harus disesuaikan agar cluster tidak kolaps?

---

### Kunci Jawaban & Solusi Quiz

##### Pertanyaan Basic
1. Karena Orleans mengadopsi abstraksi *Virtual Actor*. Grain memiliki identitas deterministik yang eksis secara konseptual secara permanen. Runtime mengelola aktivasinya secara otomatis ke memori Silo manapun saat ada pesan masuk, dan mendonaktifkannya (*garbage collect*) saat idle.
2. `Wait` menerapkan mekanisme *backpressure* dengan menahan eksekusi producer asinkron hingga buffer memiliki slot kosong. Sebaliknya, `DropWrite` menolak/membuang event yang baru masuk seketika tanpa menahan eksekusi thread producer.
3. Pendekatan `Stream.ReadAsync` mengalokasikan array byte secara berulang pada heap yang meningkatkan frekuensi GC Gen 0/1 dan berisiko mencemari Large Object Heap (LOH). `System.IO.Pipelines` menggunakan memory pooling terkelola tanpa alokasi baru (*zero-allocation*).
4. Klausa tersebut mengunci baris data yang sedang dibaca oleh transaksi relayer saat ini dan secara otomatis melompati (*skip*) baris-baris yang telah dikunci oleh relayer lain yang berjalan paralel, mencegah *blocking/lock-wait* antar proses worker.
5. Orleans mengeksekusi grain turns menggunakan *custom cooperative TaskScheduler* pada thread pool terbatas. Pemanggilan `.Result` atau `.Wait()` memblokir thread yang sedang aktif, mencegah scheduler menjalankan task turn berikutnya, yang akhirnya memicu *thread starvation* kaskade.

##### Pertanyaan Intermediate
6. Orleans mengimplementasikan *Turn-Based Concurrency*. Setiap aktivasi Grain memiliki antrean pesan tunggal (*mailbox* internal). Pesan-pesan diproses satu per satu secara berurutan (*single-threaded turn*), sehingga tidak ada dua thread yang mengakses atau memutasi memory state Grain yang sama secara bersamaan.
7. Terjadi saat partisi jaringan (*network partition*) memutus komunikasi antar Silo. Orleans memitigasi hal ini menggunakan provider clustering berbasis konsensus eksternal terpusat (seperti Zookeeper, Consul, DynamoDB, atau Postgres Lease Table) di mana Silo yang kehilangan kontak quorum voting akan mematikan dirinya sendiri (*I am dead protocol*) untuk menghindari dual master state.
8. `ReadOnlySequence<byte>` diimplementasikan sebagai senarai berantai (*linked list*) dari segmen-segmen memori terkelola (`ReadOnlyMemory<byte>`). Parser dapat mengiterasi lintas batas fisik segmen menggunakan `SequenceReader<byte>` seolah-olah data tersebut berada pada satu contiguous array linier.
9. *At-Least-Once Delivery* menjamin pesan tidak pernah hilang dan dapat dikirim lebih dari satu kali jika terjadi kegagalan jaringan saat konfirmasi; *Exactly-Once Processing* menuntut idempotensi pada layer consumer (misalnya dedup key table) untuk memastikan efek samping dari mutasi bisnis hanya dieksekusi tepat satu kali terlepas dari duplikasi pesan yang diterima.
10. Saat Grain ditandai `[Reentrant]`, statement `await` melepaskan giliran eksekusi (*yield execution*), memungkinkan request lain untuk masuk dan mengeksekusi metode mutasi state sebelum await pertama selesai. Variabel lokal yang disimpan sebelum titik `await` menjadi basi (*stale state*), menghasilkan race condition.

##### Skenario Kasus Produksi
11. **Analisis**: Akumulasi Gen 2 GC masif tanpa adanya traffic spike umumnya dipicu oleh: (a) Alokasi objek biner berukuran > 85.000 byte langsung ke LOH akibat penggunaan memory buffer streams primitif, atau (b) Aktivasi Grain tidak terdeaktivasi karena timer atau background unmanaged event subscription yang menahan referensi Grain di memori.
    **Solusi**: Ganti parsing IO menggunakan `System.IO.Pipelines` dan `ArrayPool<byte>.Shared`. Pastikan semua unmanaged subscriptions dilepas di method `OnDeactivateAsync`, dan atur `CollectionAgeLimit` pada konfigurasi grain runtime ke nilai yang lebih agresif (misal 15 menit). Aktifkan Server GC DATAS.
12. **Analisis**: Terjadi *race condition* atau latensi tinggi saat pemrosesan batch outbox. Relayer membaca batch data, mengirim pesan ke Kafka, tetapi proses pembaruan kolom `ProcessedAtUtc` memakan waktu terlalu lama atau gagal karena konkurensi database, sehingga worker lain atau siklus berikutnya menganggap pesan tersebut belum diproses dan mengirimkannya kembali.
    **Solusi**: Turunkan ukuran batch outbox. Pasang idempotency deduplication key deterministik pada header pesan Kafka (kombinasi `MessageId` + `AggregateVersion`). Pada sisi Downstream Consumer, wajib implementasikan *Idempotent Consumer Table* yang melakukan atomik insert checking (`ON CONFLICT DO NOTHING`) sebelum memproses payload bisnis.
13. **Analisis**: Cross-silo network call latency spike menyebabkan turn queues di masing-masing Grain menumpuk pesat, menghabiskan batas default `ResponseTimeout` (30 detik).
    **Solusi**: Ubah konfigurasi `PlacementStrategy` pada grain-grain kritikal menjadi `PreferLocal` atau implementasikan `StatelessWorker` untuk komputasi read-only. Turunkan `ResponseTimeout` menjadi 4–6 detik untuk *fast-fail* sirkuit pemanggil. Aktifkan *Client Gateway routing sharding* agar traffic dari AZ tertentu selalu diarahkan ke Silo yang berada pada AZ fisik yang sama.

---

### 16. Summary
1. Microsoft Orleans merevolusi arsitektur terdistribusi dengan menyediakan abstraksi **Virtual Actor**: komputasi stateful in-memory yang diskalakan secara independen, dengan garansi eksekusi *turn-based* yang mematikan kemungkinan race-condition lokal.
2. Pemrosesan data throughput ultra-tinggi menuntut penghentian alokasi memori berlebih; penggabungan `System.IO.Pipelines`, `ReadOnlySequence<byte>`, dan `BoundedChannel` menyediakan alur ingestion bebas beban GC (*zero-allocation*) dengan perlindungan *backpressure*.
3. Dalam sistem terdistribusi, *dual-write* adalah anti-pattern. Pola **Transactional Outbox** yang dipadukan dengan **Idempotent Consumer** menjamin konsistensi data absolut (*At-Least-Once*) tanpa mengorbankan integritas transaksional basis data lokal.
4. Performa skala enterprise (P99/P99.9 sub-millisecond) hanya dapat dicapai melalui perancangan holistik: pemilihan Garbage Collection mode yang tepat (Server GC DATAS), eliminasi total *sync-over-async*, serta kesiapan arsitektur terhadap kegagalan partisi jaringan.