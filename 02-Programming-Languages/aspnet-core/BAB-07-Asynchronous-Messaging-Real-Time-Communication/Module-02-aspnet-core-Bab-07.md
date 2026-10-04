# BAB 07: Asynchronous Messaging & Real-Time Communication
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengatasi** *dual-write problem* pada sistem terdistribusi menggunakan *Transactional Outbox Pattern* berbasis Entity Framework Core dan MassTransit.
- **Mengarsitekturkan** infrastruktur *real-time communication* berskala enterprise menggunakan ASP.NET Core SignalR yang terdistribusi (*scaled-out*) melalui Redis Backplane dan Azure SignalR Service.
- **Mengoptimalkan** *throughput* dan *resource utilization* pada *message consumer* menggunakan teknik konparasi konkurensi, *prefetch count tuning*, dan non-blocking streaming (`IAsyncEnumerable<T>`).
- **Mengimplementasikan** mekanisme resiliensi pesan tingkat lanjut: *Dead-Letter Queues* (DLQ), *Exponential Backoff with Jitter Retry*, dan *Idempotent Consumer Pattern* dengan deduplikasi terdistribusi.
- **Memantau & Mengaudit** alur pesan asinkronus secara *end-to-end* menggunakan W3C Trace Context, OpenTelemetry, dan korelasi *distributed tracing*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **C# 12 & .NET 8**: *Task Parallel Library* (TPL), `ValueTask`, `CancellationToken`, `IAsyncEnumerable<T>`, dan *Memory Management* (`Span<T>`, `Memory<T>`).
- **ASP.NET Core Architecture**: *Dependency Injection lifetime scopes*, *Middleware pipeline*, dan *Background Services* (`IHostedService`/`BackgroundService`).
- **Dasar Messaging & Database**: Konsep dasar AMQP (RabbitMQ), relational database transactions (ACID, isolation levels), serta Redis fundamental (Pub/Sub, Key-Value caching).

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Runtime SignalR & Pipeline `System.IO.Pipelines`
SignalR modern di ASP.NET Core dibangun di atas abstraksi `System.IO.Pipelines` untuk mengeliminasi alokasi memori berlebih dan *Gen2 garbage collection pressure* yang lazim terjadi pada parsing socket konvensional.

```
Client Socket
     │
     ▼
[Transport Layer] ──> (WebSockets / Server-Sent Events / Long Polling)
     │
     ▼
[PipeReader] ───────> Alokasi Memory Pool (ArrayPool<byte>.Shared)
     │
     ▼
[HubConnectionHandler]
     │
     ▼
[HubProtocol] ──────> (MessagePack Hub Protocol / JSON Hub Protocol)
     │
     ▼
[Hub Dispatcher] ───> Eksekusi Method Hub via ThreadPool Worker
```

- **Transport Negotiation**: Klien mengirimkan *negotiate request* HTTP untuk menentukan kapabilitas transport terbaik. Urutan prioritas *fallback*: **WebSockets** (full-duplex, transport biner/teks via TCP) $\rightarrow$ **Server-Sent Events (SSE)** (half-duplex, server-to-client streaming via HTTP) $\rightarrow$ **Long Polling** (request/response fallback dengan latensi tinggi).
- **Socket Multiplexing & Framing**: Pesan dipecah menjadi *frames* yang dibatasi oleh karakter terminator `0x1E` (Record Separator) pada JSON, atau *length-prefixed binary frames* pada MessagePack.
- **Scale-Out Problem & Redis Backplane**: Secara *default*, *instance* SignalR menyimpan memori koneksi (`HubConnectionContext`) secara lokal dalam RAM server. Ketika beban di-*load-balance* ke beberapa server ($Server_A$, $Server_B$), klien yang tersambung ke $Server_A$ tidak dapat menerima pesan yang di-*broadcast* oleh $Server_B$. Redis Backplane menyelesaikan ini menggunakan Redis Pub/Sub: setiap server mendengarkan ke *channel* global; mutasi pesan dikirim ke Redis lalu disebarkan ke semua *node* server secara serentak.

#### 3.2. Asynchronous Messaging Internals & The Dual-Write Problem
Ketika aplikasi perlu memperbarui basis data dan mengirim pesan ke *broker* (seperti RabbitMQ), eksekusi dua operasi I/O terpisah ini menimbulkan risiko inkonsistensi:
1. Database *commit* berhasil, namun broker *down* $\rightarrow$ Pesan hilang (data tidak sinkron).
2. Pesan terkirim ke broker, namun database transaksi *rollback* $\rightarrow$ Muncul pesan *phantom/ghost* (konsumen memproses data yang tidak valid).

```
[HTTP Request]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│               DATABASE TRANSACTION SCOPE               │
│                                                        │
│  1. INSERT INTO Orders (...)                           │
│  2. INSERT INTO OutboxMessages (Payload, Status, ...)   │
│                                                        │
└────────────────────────────────────────────────────────┘
       │ COMMIT (Atomik via DB Engine)
       ▼
┌────────────────────────────────────────────────────────┐
│             OUTBOX PUBLISHER (BackgroundService)       │
│                                                        │
│  3. Polling / CDC OutboxMessages (Unprocessed)         │
│  4. Publish ke RabbitMQ Exchange                       │
│  5. UPDATE OutboxMessages SET ProcessedAtUtc = NOW()   │
└────────────────────────────────────────────────────────┘
       │
       ▼
 [RabbitMQ Broker]
```

Solusi standar industri untuk masalah ini adalah **Transactional Outbox Pattern**: mutasi entitas bisnis dan pembuatan rekaman pesan ditulis ke dalam transaksi basis data relasional yang sama (ACID). Sebuah *worker service* terpisah secara asinkron membaca tabel *outbox*, mengirimkannya ke broker, dan menandai pesan sebagai *processed*.

---

### 4. Why & What

| Dimensi | Synchronous RPC (REST / HTTP) | Asynchronous Messaging (AMQP / RabbitMQ) | Real-Time Push (SignalR) |
| :--- | :--- | :--- | :--- |
| **Pola Komunikasi** | Request - Response (Point-to-Point) | Publish - Subscribe / Competing Consumers | Full-Duplex / Server-Sent Push |
| **Kopling Temporal** | Sangat Tinggi (Kedua sistem harus aktif) | Sangat Rendah (Penerima bisa *offline*) | Tinggi (Koneksi klien harus aktif) |
| **Karakteristik Beban**| Rawan *cascading failures* & *thread exhaustion* | *Load leveling* / *Buffering* via antrean | Sangat hemat *bandwidth* dibanding *polling* |
| **Penggunaan Ideal** | Operasi baca CRUD, kueri data instan | Pemrosesan pesanan, integrasi multi-servis | Notifikasi dashboard, chat, *live telemetry* |

#### Mengapa Tidak Cukup Polling HTTP Biasa?
*Short-polling* dan *long-polling* HTTP membebani TCP stack dan CPU secara eksponensial karena *overhead* HTTP header (berkisar antara 500 byte hingga beberapa kilobyte per request) yang dikirim berulang-ulang tanpa membawa payload perubahan data. SignalR dengan WebSockets hanya membutuhkan 2-6 byte framing per pesan setelah *handshake* awal selesai, memangkas latensi dari hitungan detik ke hitungan sub-milidetik.

---

### 5. How: Alur Kerja & Siklus Hidup Eksekusi

#### Alur Eksekusi SignalR dengan Redis Backplane:
1. **Client Handshake**: Klien mengirim *WebSocket Upgrade Request* melalui Reverse Proxy (misal: YARP/NGINX) yang telah dikonfigurasi untuk mempertahankan header `Upgrade` dan `Connection`.
2. **Connection Registration**: ASP.NET Core menetapkan `ConnectionId` unik, menginisialisasi `PipeReader` dan `PipeWriter`, lalu memicu *lifecycle hook* `OnConnectedAsync`.
3. **Dispatch to Groups**: Server memanggil `Clients.Group("orders-emea").SendAsync(...)`.
4. **Redis Inter-Node Fanout**: SignalR Redis Backplane mem-paket pesan bersama nama *group target* ke payload Redis binary, lalu memicu command `PUBLISH SignalR_Orders`.
5. **Local Socket Emission**: Semua node server yang mendengarkan channel tersebut mendekode payload dan mengirimkan frame WebSockets ke soket lokal masing-masing klien yang tergabung dalam grup.

#### Alur Pengiriman Pesan Resisten Kegagalan (Consumer):
1. **Prefetch**: Consumer mengambil $N$ batch pesan dari RabbitMQ (`Basic.Qos`).
2. **Deduplication Check**: Consumer mengecek status `InboxMessage` menggunakan ID pesan unik dalam transaksi database lokal.
3. **Business Processing**: Eksekusi domain logic.
4. **Ack/Nack**: Jika berhasil, kirim `Basic.Ack` ke broker. Jika terjadi kegagalan sementara (*transient error*), kirim `Basic.Nack` dengan flag *requeue*, atau delegasikan ke *Exponential Backoff Queue* / DLQ jika batas *retry* telah terlampaui.

---

### 6. Analogy & Architectural Diagram

#### Analogi Konseptual
Bayangkan **Kantor Pos Sentral Terpadu**:
- **REST**: Anda menelepon resepsionis dan menunggunya memeriksa berkas di gudang sebelum menutup telepon. Jika gudang terbakar, Anda terjebak menunggu sambungan telepon tanpa kepastian.
- **Outbox Pattern & Messaging**: Anda menulis instruksi kerja dan memasukkannya ke dalam laci arsip fisik Anda (**Outbox**) bersamaan dengan dokumen resmi yang Anda tandatangani (**Database Transaction**). Seorang kurir internal (**Outbox Daemon**) secara rutin mengumpulkan instruksi di laci tersebut untuk dibawa ke **Hub Logistik** (RabbitMQ), yang menjamin paket tetap terkirim meskipun penerima sedang tutup toko.
- **SignalR**: Sambungan interkom langsung dua arah yang terpasang di meja kerja Anda. Setiap kali kurir mencatat penerimaan paket di gudang, bel interkom Anda langsung berbunyi instan tanpa Anda perlu bolak-balik memeriksa laci pos.

#### Diagram Arsitektur Produksi Terpadu

```
                      ┌────────────────────────────────────────┐
                      │            API Gateway / LB            │
                      └──────────────────┬─────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
        ┌───────────────────────┐                 ┌───────────────────────┐
        │  ASP.NET Core Node A  │                 │  ASP.NET Core Node B  │
        │  ┌─────────────────┐  │                 │  ┌─────────────────┐  │
        │  │   SignalR Hub   │  │                 │  │   SignalR Hub   │  │
        │  └────────┬────────┘  │                 │  └────────┬────────┘  │
        │           │           │                 │           │           │
        │  ┌────────▼────────┐  │                 │  ┌────────▼────────┐  │
        │  │ MassTransit Outbox │  │                 │  │ MassTransit Outbox │  │
        └─────┬───────────┬─────┘                 └─────┬───────────┬─────┘
              │           │                             │           │
    Pub/Sub   │           │ Write             Pub/Sub   │           │ Write
    Sync      │           ▼                   Sync      │           ▼
  ┌───────────┼─────────────────────────────────────────┘           │
  │           │     ┌──────────────────────────────────┐            │
  ▼           ▼     ▼                                  ▼            ▼
┌───────────────┐ ┌───────────────────────────────────────────────────────┐
│     REDIS     │ │             POSTGRESQL / SQL SERVER                   │
│   BACKPLANE   │ │  - Orders Table (Domain Data)                         │
└───────────────┘ │  - Outbox Table (Transactional Message Store)         │
                  └──────────────────────────┬────────────────────────────┘
                                             │ Polling / CDC Daemon
                                             ▼
                                  ┌────────────────────┐
                                  │ RabbitMQ Broker    │
                                  │ (Topic / Exchange) │
                                  └──────────┬─────────┘
                                             │ Consume via Competing Consumer
                                             ▼
                                  ┌────────────────────┐
                                  │ Background Worker  │
                                  │ (Process Payment)  │
                                  └────────────────────┘
```

---

### 7. Implementation Code Examples

#### 7.1. Simple Example: Server-to-Client Real-Time Streaming via `IAsyncEnumerable<T>`
Pola ini mengirimkan metrik server langsung ke klien secara *streaming* tanpa buffering seluruh *array* di memori.

```csharp
// MetricsHub.cs
using System.Runtime.CompilerServices;
using Microsoft.AspNetCore.SignalR;

namespace Enterprise.RealTime.Hubs;

public record SystemMetric(double CpuUsage, long MemoryAllocatedBytes, DateTime Timestamp);

public sealed class MetricsHub : Hub
{
    public async IAsyncEnumerable<SystemMetric> StreamSystemMetrics(
        int durationSeconds,
        [EnumeratorCancellation] CancellationToken cancellationToken)
    {
        for (var i = 0; i < durationSeconds; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var metric = new SystemMetric(
                CpuUsage: Random.Shared.NextDouble() * 100.0,
                MemoryAllocatedBytes: GC.GetTotalMemory(forceFullCollection: false),
                Timestamp: DateTime.UtcNow
            );

            yield return metric;

            // Non-blocking interval delay
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
        }
    }
}
```

#### 7.2. Practical Enterprise Example: MassTransit Outbox Pattern & Resilient Consumer

##### a. Domain Entities & DbContext Configuration
```csharp
// Infrastructure/Data/AppDbContext.cs
using MassTransit;
using Microsoft.EntityFrameworkCore;

namespace Enterprise.Messaging.Infrastructure;

public sealed class Order
{
    public Guid Id { get; private set; }
    public string CustomerId { get; private set; } = default!;
    public decimal TotalAmount { get; private set; }
    public string Status { get; private set; } = "Pending";
    public DateTime CreatedAtUtc { get; private set; }

    private Order() { } // EF Core requirement

    public Order(Guid id, string customerId, decimal totalAmount)
    {
        Id = id;
        CustomerId = customerId;
        TotalAmount = totalAmount;
        CreatedAtUtc = DateTime.UtcNow;
    }

    public void MarkCompleted() => Status = "Completed";
}

public sealed class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<Order> Orders => Set<Order>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<Order>(b =>
        {
            b.HasKey(o => o.Id);
            b.Property(o => o.CustomerId).IsRequired().HasMaxLength(64);
            b.Property(o => o.TotalAmount).HasPrecision(18, 4);
        });

        // Konfigurasi tabel Outbox MassTransit ke dalam schema database yang sama
        modelBuilder.AddOutboxMessageEntity();
        modelBuilder.AddOutboxStateEntity();
    }
}
```

##### b. Contracts & Message Definition
```csharp
// Contracts/OrderCreatedEvent.cs
namespace Enterprise.Messaging.Contracts;

public record OrderCreatedEvent(
    Guid OrderId,
    string CustomerId,
    decimal TotalAmount,
    DateTime OccurredOnUtc
);
```

##### c. API Endpoint Menggunakan Transactional Outbox
```csharp
// Endpoints/OrderEndpoints.cs
using Enterprise.Messaging.Contracts;
using Enterprise.Messaging.Infrastructure;
using MassTransit;
using Microsoft.AspNetCore.Mvc;

namespace Enterprise.Messaging.Endpoints;

public static class OrderEndpoints
{
    public static void MapOrderEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/orders", async (
            [FromBody] CreateOrderRequest request,
            AppDbContext dbContext,
            IPublishEndpoint publishEndpoint,
            CancellationToken ct) =>
        {
            var orderId = Guid.NewGuid();
            var order = new Order(orderId, request.CustomerId, request.TotalAmount);

            await dbContext.Orders.AddAsync(order, ct);

            // Publish dipetakan ke DbContext Outbox Message Table (Belum masuk RabbitMQ)
            await publishEndpoint.Publish(new OrderCreatedEvent(
                order.Id,
                order.CustomerId,
                order.TotalAmount,
                DateTime.UtcNow
            ), ct);

            // Eksekusi atomik: Data Order dan Event Outbox disimpan dalam 1 transaksi
            await dbContext.SaveChangesAsync(ct);

            return Results.Accepted($"/api/orders/{orderId}", new { OrderId = orderId });
        });
    }
}

public record CreateOrderRequest(string CustomerId, decimal TotalAmount);
```

##### d. Idempotent Consumer dengan Error Handling & DLQ
```csharp
// Consumers/OrderCreatedConsumer.cs
using Enterprise.Messaging.Contracts;
using MassTransit;
using Microsoft.Extensions.Logging;

namespace Enterprise.Messaging.Consumers;

public sealed class OrderCreatedConsumer : IConsumer<OrderCreatedEvent>
{
    private readonly ILogger<OrderCreatedConsumer> _logger;

    public OrderCreatedConsumer(ILogger<OrderCreatedConsumer> logger)
    {
        _logger = logger;
    }

    public async Task Consume(ConsumeContext<OrderCreatedEvent> context)
    {
        var message = context.Message;
        _logger.LogInformation("Processing OrderCreatedEvent for OrderId: {OrderId}", message.OrderId);

        // Simulasi validasi bisnis dan resiliensi
        if (message.TotalAmount <= 0)
        {
            _logger.LogError("Invalid order amount {Amount} for OrderId {OrderId}. Rejecting.", 
                message.TotalAmount, message.OrderId);
            
            // Melemparkan exception spesifik agar diarahkan ke Fault / Dead-Letter Queue
            throw new ArgumentOutOfRangeException(nameof(message.TotalAmount), "Order amount must be positive.");
        }

        // Domain processing simulasi
        await Task.Delay(100, context.CancellationToken);

        _logger.LogInformation("Successfully processed OrderCreatedEvent: {OrderId}", message.OrderId);
    }
}

// Consumer Definition untuk mengatur policy individual
public sealed class OrderCreatedConsumerDefinition : ConsumerDefinition<OrderCreatedConsumer>
{
    protected override void ConfigureConsumer(
        IReceiveEndpointConfigurator endpointConfigurator,
        IConsumerConfigurator<OrderCreatedConsumer> consumerConfigurator,
        IRegistrationContext context)
    {
        // Concurrency Limit per instance consumer
        endpointConfigurator.ConcurrentMessageLimit = 16;
        endpointConfigurator.PrefetchCount = 32;

        // Exponential Backoff with Jitter
        endpointConfigurator.UseMessageRetry(r => 
            r.Exponential(5, TimeSpan.FromMilliseconds(200), TimeSpan.FromSeconds(5), TimeSpan.FromMilliseconds(100)));

        // In-memory Outbox filter per consumer context (menghindari duplicate publish dari consumer)
        endpointConfigurator.UseInMemoryOutbox(context);
    }
}
```

##### e. Program.cs & Service Registration
```csharp
// Program.cs
using Enterprise.Messaging.Consumers;
using Enterprise.Messaging.Endpoints;
using Enterprise.Messaging.Infrastructure;
using Enterprise.RealTime.Hubs;
using MassTransit;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// Database Registration
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Database")));

// SignalR Configuration with Redis Backplane
builder.Services.AddSignalR(hubOptions =>
{
    hubOptions.EnableDetailedErrors = builder.Environment.IsDevelopment();
    hubOptions.KeepAliveInterval = TimeSpan.FromSeconds(15);
    hubOptions.ClientTimeoutInterval = TimeSpan.FromSeconds(30);
})
.AddStackExchangeRedis(builder.Configuration.GetConnectionString("Redis")!, options =>
{
    options.Configuration.ChannelPrefix = "Enterprise_SignalR";
});

// MassTransit with Outbox & RabbitMQ Registration
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderCreatedConsumer, OrderCreatedConsumerDefinition>();

    x.AddEntityFrameworkOutbox<AppDbContext>(o =>
    {
        o.UsePostgres();
        o.UseBusOutbox();
        o.DuplicateDetectionWindow = TimeSpan.FromMinutes(30);
        o.DisableInboxCleanupService(); // Jika pembersihan inbox didelegasikan ke worker khusus
    });

    x.UsingRabbitMq((context, cfg) =>
    {
        cfg.Host(builder.Configuration.GetConnectionString("RabbitMQ"));

        // Mengonfigurasi endpoints otomatis berdasarkan consumer definitions
        cfg.ConfigureEndpoints(context);
    });
});

var app = builder.Build();

app.MapOrderEndpoints();
app.MapHub<MetricsHub>("/hubs/metrics");

app.Run();
```

---

### 8. Real-World Case Study: FinTech Real-Time Dynamic Settlement Engine
Sebuah platform pertukaran aset keuangan skala enterprise menangani $25.000$ order per detik (*peak load*). Sistem lama menggunakan HTTP synchronous call ke settlement engine, yang mengakibatkan:
1. Lonjakan *Thread Pool Starvation* pada ASP.NET Core Kestrel sewaktu settlement engine mengalami *latency spike*.
2. Munculnya inkonsistensi saldo (*phantom balances*) akibat kegagalan jaringan acak di tengah-tengah transaksi HTTP ganda.

#### Arsitektur Solusi Baru:
- **Write Path**: HTTP POST order diterima oleh Minimal API, divalidasi, lalu dimasukkan ke dalam basis data PostgreSQL bersamaan dengan entri *Outbox* dalam waktu $< 8\text{ ms}$. Request HTTP langsung mengembalikan respons `202 Accepted`.
- **Decoupled Pipeline**: Service daemon membaca tabel outbox dan mempublikasikan event ke cluster RabbitMQ (menggunakan *Quorum Queues* untuk jaminan replikasi tinggi).
- **Processing Engine**: Konsumen asinkron memproses kliring saldo dengan kontrol konkurensi terisolasi via *Idempotent Consumers*.
- **Real-Time Delivery**: Begitu kliring rampung, hasil mutasi di-*broadcast* ke SignalR Hub. Karena terdapat 12 node aplikasi di belakang AWS ALB, **SignalR Redis Backplane** mendistribusikan notifikasi penyelesaian secara instan ke browser/aplikasi mobile pengguna dalam waktu $< 45\text{ ms}$ secara *end-to-end*.

---

### 9. Trade-Off Analysis

| Aspek | In-Memory Channels / TPL | Broker Eksternal (RabbitMQ / Kafka) | REST Polling Terjadwal | SignalR + WebSockets |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput** | Sangat Tinggi ($> 500\text{k}$ msg/s per node) | Tinggi ($20\text{k} - 100\text{k}$ msg/s) | Sangat Rendah | Sangat Tinggi |
| **Latency** | Sub-mikrodetik | Rendah ($2 - 10\text{ ms}$) | Sangat Tinggi (Interval polling) | Sangat Rendah ($1 - 10\text{ ms}$) |
| **Scalability** | Single-Node (Vertikal) | Terdistribusi Horizontal | Horizontal (Membebani DB) | Horizontal (dengan Backplane) |
| **Reliability** | Rentan hilang bila node *crash* | Sangat Tinggi (*Durable Storage*) | Bergantung DB | Sementara (*Connection state loss*) |
| **Operational Cost**| $0 (Nol dependensi infrastruktur) | Membutuhkan Cluster Management | Biaya komputasi & I/O DB tinggi | Memerlukan Redis / Backplane instance |

---

### 10. Common Mistakes & Troubleshooting

#### 1. SignalR Connection Leak & Memory Bloat
- **Gejala**: RAM server membengkak secara linier seiring waktu hingga terjadi `OutOfMemoryException`.
- **Akar Masalah**: Memasukkan objek besar ke dalam SignalR `HubContext` atau menambahkan *event listener* C# yang mereferensikan objek Hub tanpa melakukan *unsubscribe* saat koneksi terputus (`OnDisconnectedAsync`).
- **Solusi**: Jangan pernah menyimpan state klien di memori statis Hub. Gunakan *ClaimsPrincipal* dari token JWT dan batasi ukuran payload *buffer* di `HubOptions.MaximumReceiveMessageSize`.

#### 2. Dual-Write via Direct Bus Publish
- **Gejala**: Data tersimpan di basis data, tetapi pelanggan tidak menerima event; atau sebaliknya, konsumen memproses pesan sementara transaksi database di-rollback karena *constraint violation*.
- **Akar Masalah**: Memanggil `await _bus.Publish(...)` secara langsung berdampingan dengan `await _dbContext.SaveChangesAsync()`.
- **Solusi**: Terapkan *Transactional Outbox Pattern* secara konsisten. Validasi bahwa tabel outbox berada dalam database engine yang sama dengan entitas bisnis.

#### 3. Poison Message Infinite Retry Loop
- **Gejala**: CPU consumer mencapai 100%, log dibanjiri oleh error yang identik, dan antrean tertimbun tidak bergerak (*head-of-line blocking*).
- **Akar Masalah**: Kesalahan deserialisasi JSON atau validasi bisnis yang dilempar berulang kali tanpa batas *retry* maksimum atau pengalihan ke Dead-Letter Queue.
- **Solusi**: Terapkan konfigurasi *Retry Filter*: bedakan *transient exceptions* (misal: `TimeoutException`, `SocketException`) dari *fatal exceptions* (misal: `InvalidOperationException`, `ArgumentNullException`, `JsonException`). Fatal exceptions harus langsung di-*reject* ke Error/Dead-Letter Queue.

---

### 11. Best Practices (Production Checklist)

- [ ] **Enforce Idempotency**: Setiap consumer wajib memvalidasi Message ID atau Business Correlation Key sebelum menjalankan mutasi domain.
- [ ] **Configure QOS (Prefetch Count)**: Jangan gunakan prefetch *unlimited* pada consumer. Tetapkan nilai rasional (misal: $2 \times \text{ConcurrentMessageLimit}$) untuk mencegah penimbunan pesan di RAM consumer yang lambat.
- [ ] **Keep-Alive & Heartbeats**: Set `ClientTimeoutInterval` dua kali lebih besar dari `KeepAliveInterval` pada konfigurasi SignalR.
- [ ] **Use MessagePack for High-Throughput Hubs**: Gantikan JSON Hub Protocol dengan MessagePack untuk memangkas *network bandwidth* dan *deserialization CPU cycles* hingga 60%.
- [ ] **Graceful Consumer Shutdown**: Selalu teruskan `CancellationToken` dari `ConsumeContext` ke method asynchronous database untuk memastikan transaksi dibatalkan dengan aman saat instance menerima sinyal `SIGTERM`.
- [ ] **Distributed Tracing Propagation**: Pastikan `ActivitySource` diaktifkan agar W3C `traceparent` secara otomatis diteruskan dari HTTP Header $\rightarrow$ Outbox Table $\rightarrow$ RabbitMQ Metadata $\rightarrow$ Consumer Context $\rightarrow$ SignalR Push.

---

### 12. Hands-on Practice: Membangun Resilient Notification Pipeline
Simpan kode berikut dalam struktur folder: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
dotnet new web -n EnterpriseMessagingLab
cd EnterpriseMessagingLab
dotnet add package MassTransit.RabbitMQ
dotnet add package MassTransit.EntityFrameworkCore
dotnet add package Microsoft.EntityFrameworkCore.InMemory
dotnet add package Microsoft.AspNetCore.SignalR.StackExchangeRedis
```

#### Langkah 2: Buat Pipeline Notifikasi End-to-End
Ganti isi `Program.cs` dengan implementasi fungsional mandiri yang menghubungkan In-Memory Outbox, Message Publishing, Consumer, dan SignalR Hub:

```csharp
// hands-on/m02/EnterpriseMessagingLab/Program.cs
using MassTransit;
using Microsoft.AspNetCore.SignalR;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSignalR();

// Inisialisasi MassTransit menggunakan mediator lokal untuk simulasi lab
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<PaymentNotificationConsumer>();

    x.UsingInMemory((context, cfg) =>
    {
        cfg.ConfigureEndpoints(context);
    });
});

var app = builder.Build();

app.MapHub<NotificationHub>("/hubs/notifications");

app.MapPost("/api/payments/pay", async (IPublishEndpoint bus) =>
{
    var transactionId = Guid.NewGuid();
    await bus.Publish(new PaymentSuccessEvent(transactionId, 250_000, DateTime.UtcNow));
    return Results.Ok(new { Status = "Dispatched", TransactionId = transactionId });
});

app.Run();

// Definisi Kontrak, Hub, dan Consumer
public record PaymentSuccessEvent(Guid TransactionId, decimal Amount, DateTime Timestamp);

public sealed class NotificationHub : Hub
{
    public Task JoinGroup(string groupName) => Groups.AddToGroupAsync(Context.ConnectionId, groupName);
}

public sealed class PaymentNotificationConsumer : IConsumer<PaymentSuccessEvent>
{
    private readonly IHubContext<NotificationHub> _hubContext;
    private readonly ILogger<PaymentNotificationConsumer> _logger;

    public PaymentNotificationConsumer(IHubContext<NotificationHub> hubContext, ILogger<PaymentNotificationConsumer> logger)
    {
        _hubContext = hubContext;
        _logger = logger;
    }

    public async Task Consume(ConsumeContext<PaymentSuccessEvent> context)
    {
        var msg = context.Message;
        _logger.LogInformation("Processing payment event for TX: {TxId}", msg.TransactionId);

        // Broadcast langsung ke semua klien yang terhubung via SignalR
        await _hubContext.Clients.All.SendAsync("ReceiveNotification", 
            $"Payment of IDR {msg.Amount:N0} successfully verified at {msg.Timestamp:HH:mm:ss} UTC");
    }
}
```

#### Langkah 3: Eksekusi dan Verifikasi
1. Jalankan aplikasi: `dotnet run`
2. Buka terminal baru dan picu endpoint pembayaran:
   ```bash
   curl -X POST http://localhost:5000/api/payments/pay
   ```
3. Periksa konsol aplikasi: Verifikasi log bahwa pesan di-*publish* secara asinkron, diterima oleh consumer, dan diteruskan ke konteks SignalR Hub.

---

### 13. Exercises

#### Level Easy
Ubah konfigurasi SignalR pada contoh `MetricsHub` agar membatasi pengiriman stream metrics maksimal hanya untuk durasi 60 detik. Jika klien meminta lebih dari 60 detik, lemparkan `HubException` sebelum stream dimulai.

#### Level Medium
Buat sebuah MassTransit Consumer Definition untuk `PaymentSuccessEvent` yang menerapkan:
- Konkurensi pesan maksimal: 5.
- Retry policy: 3 kali percobaan dengan interval tetap 2 detik.
- Mengabaikan (tidak me-retry) exception berjenis `InvalidOperationException`.

#### Level Hard
Rancang dan implementasikan kustom EF Core SaveChanges Interceptor (`SaveChangesInterceptor`) yang mendeteksi setiap entitas bertipe `IAuditableEntity` yang dihapus (*soft-deleted*), lalu secara atomik menginisialisasi rekaman event audit ke dalam tabel `AuditLogs` dalam konteks transaksi yang sama tanpa menggunakan library pihak ketiga.

---

### 14. Challenge: Mission-Critical Telemetry Hub
Sebuah perusahaan logistik memiliki 50.000 armada truk yang mengirimkan metrik GPS setiap 2 detik ke sistem ASP.NET Core. 

**Persyaratan Tantangan:**
1. Desain arsitektur di mana klien pengirim (truk) menggunakan koneksi MQTT atau WebSocket persisten ke sistem ingestion.
2. Ingestion layer tidak boleh menulis langsung ke database relasional utama untuk menghindari *lock contention*.
3. Pesan harus di-*buffer* secara terdistribusi dan di-konsumsi secara *micro-batch* (misal per 500 pesan atau interval 1 detik) sebelum ditulis ke basis data *time-series* / PostgreSQL.
4. Dashboard web operator armada harus menampilkan posisi truk secara *real-time* dengan latensi $< 500\text{ ms}$. Jika operator melakukan *filter* wilayah geografis tertentu, operator tersebut hanya boleh menerima stream pembaruan untuk truk yang berada dalam batas koordinat (*bounding box*) tersebut.
5. Buat ringkasan spesifikasi arsitektur teknis lengkap (pilihan teknologi, struktur pesan, desain partisi broker, dan konfigurasi SignalR Grouping/Streaming).

---

### 15. Evaluasi Pemahaman

#### Basic (Pilihan Ganda)
1. Apa peran utama dari Record Separator `0x1E` dalam SignalR JSON Hub Protocol?
   - A. Menandakan enkripsi payload telah selesai.
   - B. Berfungsi sebagai pembatas (*delimiter/framing*) antar pesan dalam stream socket TCP berkelanjutan.
   - C. Merupakan token otentikasi koneksi WebSockets.
   - D. Menandakan koneksi soket harus ditutup secara graceful.

2. Masalah apa yang dipecahkan oleh *Transactional Outbox Pattern*?
   - A. Keterbatasan bandwidth internet pada protokol HTTP/1.1.
   - B. Masalah *Dual-Write* antara database relasional dan message broker.
   - C. Kegagalan serialisasi format data MessagePack.
   - D. Kebutuhan load balancing pada cluster Kubernetes.

3. Komponen apa yang digunakan SignalR untuk mendistribusikan pesan ke beberapa server aplikasi yang berbeda?
   - A. HTTP Reverse Proxy.
   - B. Entity Framework Change Tracker.
   - C. Redis Backplane / Azure SignalR Service.
   - D. RabbitMQ Dead-Letter Exchange secara langsung tanpa adapter.

4. Manakah tipe transport SignalR yang mendukung komunikasi dua arah secara penuh (*full-duplex*) melalui koneksi TCP tunggal?
   - A. Server-Sent Events.
   - B. Long Polling.
   - C. WebSockets.
   - D. HTTP POST Streams.

5. Apa efek dari konfigurasi `PrefetchCount` yang bernilai terlalu tinggi pada consumer RabbitMQ?
   - A. Antrean broker langsung terhapus otomatis.
   - B. Consumer berisiko kehabisan memori (*out of memory*) dan pesan tertahan pada satu worker lambat.
   - C. Database secara otomatis meningkatkan batas koneksi pool.
   - D. Latensi jaringan berkurang menjadi 0.

#### Intermediate (Analisis Singkat)
1. Jelaskan mengapa pemanggilan `Clients.All.SendAsync(...)` di dalam SignalR Hub saat melayani 100.000 klien yang tersambung dapat menurunkan performa server secara drastis jika menggunakan JSON dibandingkan MessagePack!
2. Mengapa penggunaan `TransactionScope` terdistribusi konvensional (Two-Phase Commit / 2PC) tidak disarankan pada arsitektur cloud microservices modern, sehingga kita lebih memilih *Outbox Pattern*?
3. Apa perbedaan mendasar antara *At-Least-Once Delivery* dan *Exactly-Once Processing*, serta bagaimana peran *Idempotent Consumer* menjembatani keduanya?
4. Bagaimana cara kerja pembatalan (*cancellation*) pada SignalR Streaming via `IAsyncEnumerable<T>` ketika browser pengguna tiba-tiba ditutup (*force close*)?
5. Mengapa tabel outbox MassTransit memerlukan pembersihan berkala (*cleanup daemon*), dan apa dampak performa pada basis data jika tabel tersebut dibiarkan membengkak hingga puluhan juta baris?

#### Skenario Kasus Produksi
1. **Kasus 1**: Sistem Anda menggunakan MassTransit dengan RabbitMQ. Tiba-tiba antrean pesan pembayaran menumpuk (*lag*) hingga $100.000$ pesan. CPU database mencapai 90%, sementara CPU consumer hanya 10%. Langkah profiling dan modifikasi arsitektur apa yang harus Anda lakukan segera?
2. **Kasus 2**: Pengguna melaporkan bahwa saat server aplikasi melakukan *rolling deployment* (pemberhentian bertahap node container untuk update versi), beberapa koneksi SignalR mereka terputus dan tidak menerima notifikasi selama lebih dari 2 menit. Konfigurasi apa di level Kestrel, Reverse Proxy, dan Client SDK yang wajib Anda perbaiki?
3. **Kasus 3**: Terjadi insiden di mana sebuah event `OrderCancelled` diproses oleh consumer sebelum event `OrderCreated` selesai diproses pada thread consumer yang berbeda karena pengiriman yang tidak berurutan (*out-of-order delivery*). Bagaimana Anda mendesain ulang skema messaging untuk menjamin konsistensi status domain tanpa mematikan konkurensi throughput?

---

### 16. Summary
- **SignalR** mengabstraksi komunikasi real-time tingkat tinggi dengan fondasi pipeline performa tinggi (`System.IO.Pipelines`). Untuk arsitektur multi-node, integrasi **Redis Backplane** atau **Azure SignalR Service** mutlak diperlukan guna mengatasi isolasi state memori lokal antar-server.
- Penggunaan **Transactional Outbox Pattern** memitigasi *dual-write problem* dengan menggabungkan persistensi domain state dan message payload ke dalam satu batas transaksi basis data lokal yang atomik.
- Resiliensi pada *consumer* membutuhkan pendekatan berlapis: pengaturan **Concurrency Limit** dan **Prefetch Count** yang seimbang, pemisahan error sementara dengan **Exponential Backoff**, isolasi *poison messages* ke **Dead-Letter Queues**, serta penerapan **Idempotency Key** untuk menjamin kestabilan sistem dari ancaman duplikasi transmisi data.