# Bab 07 Module 01: Asynchronous Messaging & Real-Time Communication

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** `aspnet-core`
* **Kategori:** `02-Programming-Languages`
* **Kode Modul:** `ASP-NET-07-01`
* **Topik:** Asynchronous Messaging & Real-Time Communication
* **Target Audiens:** Senior Software Engineer, Backend Engineer, Distributed Systems Architect
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang C# Asynchronous Programming (`Task`, `ValueTask`, `async`/`await`, `CancellationToken`).
  * Arsitektur ASP.NET Core Middleware Pipeline dan Dependency Injection Service Lifetimes.
  * Protokol jaringan transport layer (TCP, HTTP/1.1, HTTP/2, WebSocket).
  * Mekanisme sinkronisasi memori multi-threading (`Monitor`, `SemaphoreSlim`, ThreadPool).
* **Estimasi Waktu Belajar:** 180 Menit (Teori & Arsitektur: 60 Menit, Bedah Kode & Praktikum: 120 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis Mekanisme Transport:** Membedah siklus hidup koneksi duplex real-time pada Kestrel Engine, memilih secara deterministik antara WebSockets, Server-Sent Events (SSE), dan Long Polling berdasarkan kapabilitas infrastruktur jaringan.
2. **Mengimplementasikan SignalR Berkinerja Tinggi:** Merancang Strongly-Typed SignalR Hubs dengan serialisasi binary MessagePack untuk throughput tinggi dan alokasi memori minimal.
3. **Mengelola Backpressure dengan High-Performance Channels:** Membangun asynchronous producer-consumer pipeline in-process menggunakan `System.Threading.Channels` (`BoundedChannelOptions`) untuk mencegah memory exhaustion.
4. **Mendesain Arsitektur Scale-Out (Distributed Backplane):** Mengintegrasikan Redis Backplane guna menjamin perutean pesan antar-node cluster web farm tanpa kehilangan konsistensi broadcast state.
5. **Mengamankan Koneksi Persisten:** Mengonfigurasi mekanisme otentikasi JWT Bearer melalui token negotiation (Query String vs Headers) yang resistan terhadap eksploitasi Cross-Site WebSocket Hijacking (CSWSH).
6. **Menerapkan Instrumentasi Observabilitas:** Mengekspos metrik real-time, trace context propagation (`ActivitySource`), dan structured logging sepanjang pipeline asynchronous messaging.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma Request-Response tradisional (HTTP/1.1 atau HTTP/2 un-streamed), klien memegang kendali penuh atas inisiasi komunikasi (*Pull Model*). Server bersifat reaktif murni; ia tidak memiliki kemampuan langsung untuk memicu pengiriman data ke klien tanpa adanya request aktif. Model ini tidak efisien untuk domain dengan latensi ketat seperti live trading, monitoring IoT, atau kolaborasi multipengguna.

```
Request-Response (Pull):
Client  --- [HTTP GET Request]  ---> Server (State Evaluation)
Client  <-- [HTTP 200 Response] --- Server (Socket Closed/Recycled)

Duplex Persistent Connection (Push):
Client  === [Persistent WebSocket Pipe] === Server
Client  <-- [Push Message (Unsolicited)] -- Server (Event Triggered)
Client  --- [Bidirectional Stream] ------> Server
```

Pergeseran paradigma ke *Real-Time Communication* menuntut adopsi konsep **Persistent Duplex Streaming** (*Push Model*). Di sini, koneksi TCP/TLS dijaga tetap terbuka (*long-lived*). Kestrel tidak lagi mendestruksi HTTP context per transaksi, melainkan mempertahankan referensi socket transport di memory. 

Untuk menghubungkan dunia luar (klien WebSocket) dengan beban kerja komputasi internal, diterapkan prinsip **Decoupled Asynchronous Pipelining**:
* Klien tidak boleh memblokir thread eksekusi server.
* Komputasi berat tidak boleh memblokir pipeline I/O jaringan socket.
* Antrean memori (*in-process buffer*) menggunakan bounded channels bertindak sebagai "peredam kejut" (*shock absorber*) untuk menangani lonjakan beban (*burst traffic*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data end-to-end yang menggabungkan Ingestion, In-Memory Bounded Channels, Background Worker, Distributed Redis Backplane, dan Strongly-Typed SignalR Hub:

```
[External Ingestion API] / [Sensor Stream]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ ASP.NET Core Web API Controller                        │
│ - Validasi payload                                    │
│ - WriteAsync() ke Channel Writer                       │
└────────────────────────┬───────────────────────────────┘
                         │ (In-Process Non-Blocking)
                         ▼
┌────────────────────────────────────────────────────────┐
│ System.Threading.Channels.Channel<TelemetryData>       │
│ - BoundedCapacity = 10,000                             │
│ - BoundedChannelFullMode.Wait (Backpressure)           │
└────────────────────────┬───────────────────────────────┘
                         │ (ReadAsync Stream)
                         ▼
┌────────────────────────────────────────────────────────┐
│ TelemetryBackgroundProcessor (IHostedService)          │
│ - Batch processing & transform                        │
│ - Publish ke IHubContext<ITelemetryClient>             │
└────────────────────────┬───────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
┌───────────────────────┐       ┌───────────────────────┐
│ SignalR Node A        │       │ SignalR Node B        │
│ Local Memory Sub      │       │ Local Memory Sub      │
└──────────┬────────────┘       └──────────┬────────────┘
           │                               │
           └───────► [ Redis Backplane ] ◄─┘
                     (Pub/Sub Channel)
                            │
          ┌─────────────────┴─────────────────┐
          │ Broadcast via WebSocket Transport │
          ▼                                   ▼
┌──────────────────┐                 ┌──────────────────┐
│ Web Client (JS)  │                 │ Mobile App (MAUI)│
└──────────────────┘                 └──────────────────┘
```

### Diagram Transisi Protokol SignalR (Negotiation & Fallback)

```
Client                        Reverse Proxy/Kestrel               Server Hub
  │                                    │                              │
  ├── 1. POST /hub/negotiate ─────────►│                              │
  │   (Checks supported transports)    │                              │
  │◄── 2. Response: {ConnectionToken, ─┤                              │
  │       AvailableTransports:         │                              │
  │       [WebSockets, SSE, LP]}───────┘                              │
  │                                                                   │
  │─── 3. GET /hub?id={Token} ───────────────────────────────────────►│
  │       Headers: Upgrade: websocket                                 │
  │       Connection: Upgrade                                         │
  │◄── 4. HTTP 101 Switching Protocols ───────────────────────────────┤
  │                                                                   │
  │================= Persistent Duplex WebSocket Frame ==============│
  │─── 5. Handshake Protocol (JSON/MessagePack) ─────────────────────►│
  │◄── 6. Handshake Ack {} ───────────────────────────────────────────┤
  │                                                                   │
  │◄── 7. Invocation: ClientMethodName(payload) (Server Push) ────────┤
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Kestrel Socket Engine & Transport Layer
Di bawah SignalR terdapat abstraksi `Microsoft.AspNetCore.Connections.ConnectionHandler`. Kestrel membaca paket TCP langsung menggunakan `System.IO.Pipelines` (`PipeReader` dan `PipeWriter`). 
* Alih-alih mengalokasikan buffer `byte[]` baru setiap membaca frame data jaringan, Kestrel meminjam memori dari `MemoryPool<byte>.Shared`.
* `PipeReader` memproses slice memori tanpa alokasi heap berlebih (zero-copy memory slicing via `ReadOnlySequence<byte>`).

### 2. SignalR Hub Lifecycle
Hub bersifat **transient per invokasi**. Setiap kali metode RPC (*Remote Procedure Call*) dikirim dari klien:
1. DI Container membuat instance kelas Hub baru.
2. Inisialisasi properti konteks (`Context`, `Clients`, `Groups`).
3. Metode Hub dieksekusi secara asinkron.
4. Instance Hub didisposisi oleh framework, mengembalikan resource ke GC/Pool.
State koneksi jangka panjang tidak disimpan di dalam instance field kelas Hub, melainkan dipertahankan oleh `HubConnectionContext` yang hidup selama transport socket aktif.

### 3. Protocol Serialization & Frame Framing
SignalR memisahkan layer transport (WebSockets/SSE) dari layer representasi data (*Hub Protocol*). Secara default, protocol yang digunakan adalah Textual JSON, di mana setiap pesan ditutup oleh delimiter ASCII `0x1E` (*Record Separator*). 

Ketika beralih ke protokol binary MessagePack:
* Panjang frame ditentukan oleh format framing VarInt.
* Memory footprint terpangkas hingga 60-70% karena encoding representasi biner.
* CPU overhead berkurang signifikan karena eliminasi escaping string teks dan parsing token JSON.

### 4. Heartbeat dan Keep-Alive
* `ClientTimeoutInterval`: Waktu maksimum Kestrel menunggu pesan dari klien sebelum memutus koneksi secara paksa (default 30 detik).
* `KeepAliveInterval`: Interval di mana server mengirimkan frame ping kosong (0x01 Ping frame) untuk menjaga status koneksi tetap aktif di balik L4/L7 load balancer atau NAT gateway (default 15 detik).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Perbandingan Karakteristik Transport
1. **WebSockets:** 
   * Protokol murni full-duplex melalui RFC 6455.
   * Menggunakan satu socket TCP persisten untuk komunikasi dua arah secara simultan.
   * Overhead header framing minimal (2 hingga 14 byte per frame).
2. **Server-Sent Events (SSE):** 
   * Protokol half-duplex (server-to-client push saja) via HTTP/1.1 atau multiplexed HTTP/2.
   * Menggunakan content-type `text/event-stream`. 
   * Klien tidak dapat mengirim data melalui pipeline yang sama; klien harus membuka HTTP POST terpisah untuk mengirim data ke server.
3. **Long Polling:** 
   * Mekanisme fallback paling mahal.
   * Klien membuka HTTP request dan server menahan response sampai ada data baru (atau timeout). Setelah response diterima, klien *harus* membuka koneksi request baru.
   * Menghasilkan alokasi TCP handshake, TLS negotiation, dan HTTP header berulang-ulang.

### Backpressure Mechanics Menggunakan `System.Threading.Channels`
Ketika consumer (misal: prosesor broadcast SignalR) lebih lambat dari producer (misal: ingestion webhook burst 50.000 req/sec), sistem tanpa batas buffer akan mengalami `OutOfMemoryException`.
`System.Threading.Channels` menyediakan mekanisme bounded channel dengan algoritma mitigasi backpressure terkalibrasi:
* `BoundedChannelFullMode.Wait`: Thread producer menangguhkan eksekusi secara asinkron (`await writer.WriteAsync()`) sampai ada ruang kosong di buffer. Ini mempropagasi backpressure ke hulu, memperlambat ingress API secara elegan.
* `BoundedChannelFullMode.DropOldest`: Elemen terlama di buffer dibuang untuk menampung data baru (cocok untuk telemetry sensor di mana data terbaru lebih bernilai dari data historis).
* `BoundedChannelFullMode.DropNewest`: Elemen baru dibuang sampai slot tersedia.

### Scale-Out Architecture via Redis Backplane
SignalR di node tunggal menyimpan ID koneksi secara in-memory. Jika terdapat Load Balancer di depan Node A dan Node B:
* Klien X terhubung ke Node A.
* Klien Y terhubung ke Node B.
* Jika Node A ingin memanggil `Clients.All.SendAsync()`, Klien Y pada Node B secara natural tidak akan menerima pesan tersebut.

Redis Backplane mengabstraksi problem ini melalui Redis Pub/Sub:
1. Node A mempublikasikan payload RPC biner ke channel Redis internal SignalR.
2. Semua server node yang terdaftar sebagai subscriber menerima payload tersebut.
3. Masing-masing node mendistribusikan payload ke koneksi lokal yang mereka kelola.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah fondasi strongly-typed SignalR Hub dengan channel-backed producer-consumer pipeline.

### 1. Deklarasi Interface Client & Model Data

```csharp
// Contracts/ITelemetryHubClient.cs
namespace AdvancedRealTime.Contracts;

public record TelemetryPayload(
    string DeviceId, 
    double MetricValue, 
    DateTimeOffset TimestampUtc
);

public interface ITelemetryHubClient
{
    Task ReceiveTelemetry(TelemetryPayload payload);
    Task AcknowledgeRegistration(string connectionId, string status);
}
```

### 2. Implementasi Strongly-Typed Hub

```csharp
// Hubs/TelemetryHub.cs
using AdvancedRealTime.Contracts;
using Microsoft.AspNetCore.SignalR;

namespace AdvancedRealTime.Hubs;

public sealed class TelemetryHub : Hub<ITelemetryHubClient>
{
    private readonly ILogger<TelemetryHub> _logger;

    public TelemetryHub(ILogger<TelemetryHub> logger)
    {
        _logger = logger;
    }

    public override async Task OnConnectedAsync()
    {
        var connectionId = Context.ConnectionId;
        _logger.LogInformation("Klien terhubung: {ConnectionId}", connectionId);

        // Mengirim notifikasi selamat datang khusus ke pemanggil
        await Clients.Caller.AcknowledgeRegistration(connectionId, "Koneksi Berhasil Diinisialisasi");
        await base.OnConnectedAsync();
    }

    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        _logger.LogWarning(exception, "Klien terputus: {ConnectionId}", Context.ConnectionId);
        await base.OnDisconnectedAsync(exception);
    }

    public async Task JoinDeviceGroup(string deviceId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(deviceId);
        await Groups.AddToGroupAsync(Context.ConnectionId, $"device_{deviceId}");
        _logger.LogInformation("Koneksi {ConnectionId} bergabung ke grup device_{DeviceId}", Context.ConnectionId, deviceId);
    }

    public async Task LeaveDeviceGroup(string deviceId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(deviceId);
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"device_{deviceId}");
        _logger.LogInformation("Koneksi {ConnectionId} keluar dari grup device_{DeviceId}", Context.ConnectionId, deviceId);
    }
}
```

### 3. Pipeline In-Process Buffer (Channels) & Background Broadcaster

```csharp
// Services/TelemetryQueue.cs
using System.Threading.Channels;
using AdvancedRealTime.Contracts;

namespace AdvancedRealTime.Services;

public interface ITelemetryQueue
{
    ValueTask EnqueueAsync(TelemetryPayload payload, CancellationToken cancellationToken = default);
    IAsyncEnumerable<TelemetryPayload> ReadAllAsync(CancellationToken cancellationToken = default);
}

public sealed class TelemetryQueue : ITelemetryQueue
{
    private readonly Channel<TelemetryPayload> _channel;

    public TelemetryQueue(int capacity = 5000)
    {
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleWriter = false,
            SingleReader = true
        };
        _channel = Channel.CreateBounded<TelemetryPayload>(options);
    }

    public async ValueTask EnqueueAsync(TelemetryPayload payload, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(payload);
        await _channel.Writer.WriteAsync(payload, cancellationToken);
    }

    public IAsyncEnumerable<TelemetryPayload> ReadAllAsync(CancellationToken cancellationToken = default)
    {
        return _channel.Reader.ReadAllAsync(cancellationToken);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Bedah Komponen Hub (`TelemetryHub.cs`)
* `public sealed class TelemetryHub : Hub<ITelemetryHubClient>`: Pewarisan dari `Hub<T>` mengaktifkan compile-time safety. String literals metod seperti `"ReceiveTelemetry"` digantikan oleh pemanggilan method interface C# yang valid.
* `public override async Task OnConnectedAsync()`: Titik intersepsi siklus hidup koneksi. Kestrel memicu kode ini tepat setelah negotiation dan handshake protocol berhasil divalidasi.
* `Clients.Caller.AcknowledgeRegistration(...)`: Mengirim frame RPC hanya ke socket yang memicu request koneksi, meminimalkan bandwidth network.
* `await Groups.AddToGroupAsync(...)`: Menghubungkan ID koneksi unik ke virtual bucket (*Group*). Berguna untuk skenario multicast berbasis topik (misal: hanya listening ke device tertentu).

### Bedah Komponen Buffer Queue (`TelemetryQueue.cs`)
* `new BoundedChannelOptions(capacity)`: Mengalokasikan array-backed buffer di memori dengan ukuran tetap. Menghindari pembengkakan heap yang tidak terkendali di bawah serangan throughput tinggi.
* `FullMode = BoundedChannelFullMode.Wait`: Apabila kapasitas 5.000 slot penuh, pemanggilan `WriteAsync` pada baris downstream akan menunda eksekusi (menahan Task) tanpa memblokir thread OS fisik via async state machine.
* `SingleWriter = false, SingleReader = true`: Menginstruksikan runtime untuk menggunakan algoritma lock-free ring-buffer yang dioptimalkan khusus untuk multi-producer (banyak HTTP endpoints) dan single-consumer (satu hosted service worker).
* `return _channel.Reader.ReadAllAsync(cancellationToken)`: Mengembalikan `IAsyncEnumerable<T>`, memungkinkan konsumsi data secara non-allocating streaming via konstruksi `await foreach`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Ultra-Low-Latency Financial Trading & Telemetry Engine
Sebuah platform pertukaran aset keuangan memproses rata-rata 25.000 fluktuasi harga (order book updates) per detik dari berbagai bursa global. 

**Kebutuhan Sistem:**
1. Ingestion payload harga via internal microservices melalui gRPC/HTTP batching.
2. Broadcast pembaruan harga secara instan ke ribuan klien web browser dengan latensi di bawah 50 milidetik.
3. Klien web menggunakan load-balancer multiserver tanpa jaminan sticky-session layer 4 murni.
4. Serialisasi default JSON membebani bandwidth jaringan server dan memory allocations, sehingga menimbulkan fluktuasi garbage collection (GC Gen 2 pauses).

**Solusi Arsitektural:**
1. Mengimplementasikan bounded channel pipeline untuk menampung lonjakan event tanpa alokasi memori dinamis.
2. Konfigurasi SignalR menggunakan protokol biner **MessagePack** untuk mengurangi ukuran pesan hingga 70%.
3. Implementasi Redis Backplane (`Microsoft.AspNetCore.SignalR.StackExchangeRedis`) untuk koordinasi state pub/sub lintas cluster.
4. Worker service yang membaca dari Bounded Channel dan melakukan multicast ke grup spesifik berdasarkan instrumen keuangan (`Group("EUR_USD")`).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi menyeluruh berstandar industri dengan dukungan Redis scale-out, MessagePack, background channel processing, dan controller ingestion.

### 1. Instalasi Paket NuGet Dependensi

```bash
dotnet add package Microsoft.AspNetCore.SignalR.Protocols.MessagePack --version 8.0.0
dotnet add package Microsoft.AspNetCore.SignalR.StackExchangeRedis --version 8.0.0
```

### 2. Definisi Model dan Interface

```csharp
// Models/MarketTicker.cs
using MessagePack;

namespace RealTimeEngine.Models;

[MessagePackObject]
public sealed record MarketTicker(
    [Key(0)] string Symbol,
    [Key(1)] decimal BidPrice,
    [Key(2)] decimal AskPrice,
    [Key(3)] long UnixSequenceNumber
);

public interface IMarketClient
{
    Task ReceiveTickerUpdate(MarketTicker ticker);
}
```

### 3. Implementasi Hub

```csharp
// Hubs/MarketHub.cs
using Microsoft.AspNetCore.SignalR;
using RealTimeEngine.Models;

namespace RealTimeEngine.Hubs;

public sealed class MarketHub : Hub<IMarketClient>
{
    private readonly ILogger<MarketHub> _logger;

    public MarketHub(ILogger<MarketHub> logger)
    {
        _logger = logger;
    }

    public async Task SubscribeToSymbol(string symbol)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(symbol);
        var normalizedSymbol = symbol.ToUpperInvariant();
        
        await Groups.AddToGroupAsync(Context.ConnectionId, normalizedSymbol);
        _logger.LogInformation("Koneksi {ConnectionId} subscribe ke {Symbol}", 
            Context.ConnectionId, normalizedSymbol);
    }

    public async Task UnsubscribeFromSymbol(string symbol)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(symbol);
        var normalizedSymbol = symbol.ToUpperInvariant();

        await Groups.RemoveFromGroupAsync(Context.ConnectionId, normalizedSymbol);
        _logger.LogInformation("Koneksi {ConnectionId} unsubscribe dari {Symbol}", 
            Context.ConnectionId, normalizedSymbol);
    }
}
```

### 4. Bounded Processing Pipeline

```csharp
// Services/MarketFeedChannel.cs
using System.Threading.Channels;
using RealTimeEngine.Models;

namespace RealTimeEngine.Services;

public sealed class MarketFeedChannel
{
    private readonly Channel<MarketTicker> _channel;

    public MarketFeedChannel(IConfiguration configuration)
    {
        var capacity = configuration.GetValue<int>("ChannelCapacity", 20000);
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleWriter = false,
            SingleReader = true
        };
        _channel = Channel.CreateBounded<MarketTicker>(options);
    }

    public ChannelWriter<MarketTicker> Writer => _channel.Writer;
    public ChannelReader<MarketTicker> Reader => _channel.Reader;
}
```

### 5. Background Streaming Worker Engine

```csharp
// Workers/MarketBroadcastWorker.cs
using Microsoft.AspNetCore.SignalR;
using RealTimeEngine.Hubs;
using RealTimeEngine.Models;
using RealTimeEngine.Services;

namespace RealTimeEngine.Workers;

public sealed class MarketBroadcastWorker : BackgroundService
{
    private readonly MarketFeedChannel _feedChannel;
    private readonly IHubContext<MarketHub, IMarketClient> _hubContext;
    private readonly ILogger<MarketBroadcastWorker> _logger;

    public MarketBroadcastWorker(
        MarketFeedChannel feedChannel,
        IHubContext<MarketHub, IMarketClient> hubContext,
        ILogger<MarketBroadcastWorker> logger)
    {
        _feedChannel = feedChannel;
        _hubContext = hubContext;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Market Broadcast Worker berjalan.");

        try
        {
            await foreach (var ticker in _feedChannel.Reader.ReadAllAsync(stoppingToken))
            {
                // Multicast hanya ke subscriber simbol yang bersangkutan
                await _hubContext.Clients
                    .Group(ticker.Symbol)
                    .ReceiveTickerUpdate(ticker);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            _logger.LogInformation("Market Broadcast Worker menerima sinyal shutdown graceful.");
        }
        catch (Exception ex)
        {
            _logger.LogCritical(ex, "Fatal failure pada pipeline broadcasting market.");
            throw;
        }
    }
}
```

### 6. Ingestion Web Controller

```csharp
// Controllers/IngestionController.cs
using Microsoft.AspNetCore.Mvc;
using RealTimeEngine.Models;
using RealTimeEngine.Services;

namespace RealTimeEngine.Controllers;

[ApiController]
[Route("api/v1/[controller]")]
public sealed class IngestionController : ControllerBase
{
    private readonly MarketFeedChannel _feedChannel;

    public IngestionController(MarketFeedChannel feedChannel)
    {
        _feedChannel = feedChannel;
    }

    [HttpPost("ticker")]
    [ProducesResponseType(StatusCodes.Status202Accepted)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> PublishTicker(
        [FromBody] MarketTicker ticker, 
        CancellationToken cancellationToken)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        try
        {
            // Backpressure diterapkan di sini jika channel penuh
            await _feedChannel.Writer.WriteAsync(ticker, cancellationToken);
            return Accepted();
        }
        catch (ChannelClosedException)
        {
            return StatusCode(StatusCodes.Status503ServiceUnavailable, "Ingestion Pipeline sedang shutdown.");
        }
    }
}
```

### 7. Komposisi Dependensi & Konfigurasi Host (`Program.cs`)

```csharp
// Program.cs
using MessagePack;
using MessagePack.Resolvers;
using RealTimeEngine.Hubs;
using RealTimeEngine.Services;
using RealTimeEngine.Workers;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// Registrasi In-Memory Channel Pipeline
builder.Services.AddSingleton<MarketFeedChannel>();
builder.Services.AddHostedService<MarketBroadcastWorker>();

// Registrasi & Optimasi SignalR dengan MessagePack dan Redis
var signalRBuilder = builder.Services.AddSignalR(options =>
{
    options.EnableDetailedErrors = builder.Environment.IsDevelopment();
    options.KeepAliveInterval = TimeSpan.FromSeconds(15);
    options.ClientTimeoutInterval = TimeSpan.FromSeconds(30);
    options.MaximumReceiveMessageSize = 32 * 1024; // 32 KB per frame
})
.AddMessagePackProtocol(options =>
{
    options.SerializerOptions = MessagePackSerializerOptions.Standard
        .WithResolver(ContractlessStandardResolver.Instance)
        .WithSecurity(MessagePackSecurity.UntrustedData);
});

// Konfigurasi Redis Scale-Out jika Connection String tersedia
var redisConnectionString = builder.Configuration.GetConnectionString("RedisSignalR");
if (!string.IsNullOrWhiteSpace(redisConnectionString))
{
    signalRBuilder.AddStackExchangeRedis(redisConnectionString, options =>
    {
        options.Configuration.ChannelPrefix = "MarketCluster";
    });
}

builder.Services.AddCors(options =>
{
    options.AddPolicy("SignalRPolicy", policy =>
    {
        policy.WithOrigins("https://trading.internal.domain")
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials(); // WAJIB untuk SignalR transport credentials
    });
});

var app = builder.Build();

app.UseCors("SignalRPolicy");
app.UseRouting();

app.MapControllers();
app.MapHub<MarketHub>("/hubs/market");

app.Run();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektur | WebSockets Native | SignalR (Abstraction) | Server-Sent Events (SSE) | gRPC Server Streaming |
| :--- | :--- | :--- | :--- | :--- |
| **Duplex Capability** | Full Duplex murni | Full Duplex murni | Half Duplex (Server-to-Client) | Full / Half Duplex |
| **Fallback Transports** | Tidak ada | Ada (SSE, Long Polling) | Tidak ada | Tidak ada (Wajib HTTP/2) |
| **Browser Support** | Universal | Universal (via polyfill/fallback) | Universal (Kecuali IE lawas) | Terbatas (Perlu gRPC-Web) |
| **Kinerja / Throughput** | Maksimal (Tanpa layer) | Sangat Tinggi (Minimal overhead) | Tinggi untuk teks | Maksimal (Protobuf zero-copy) |
| **Kompleksitas RPC** | Manual (Handling frame) | Otomatis (Built-in Invocation) | Manual | Otomatis (Contract `.proto`) |
| **Distributed Scaling** | Perlu kustomisasi | Didukung (Redis / Azure Service) | Perlu kustomisasi | Perlu custom proxy/mesh |

### Analisis Format Serialisasi: JSON vs MessagePack
* **JSON:** Ramah debugging manusia, didukung secara universal oleh peramban tanpa parser eksternal. Namun, menghasilkan beban garbage collection yang masif karena parsing string dan ukuran payload besar.
* **MessagePack:** Format biner terkompresi. Menghilangkan alokasi string repetitif di LOH (Large Object Heap), menurunkan bandwidth transmisi hingga 70%, dan memangkas waktu komputasi serialisasi/deserialisasi di server hingga 50%. Kelemahannya: klien browser memerlukan library encoder/decoder MessagePack client-side.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. WebSocket Starvation di Bawah HTTP/1.1 Limits
Jika peramban menggunakan HTTP/1.1, terdapat batas ketat konkurensi koneksi per domain (biasanya 6 koneksi simultan). Membuka tab multipel dapat membuat koneksi SignalR antre tanpa batas jika koneksi fallback digunakan.
*Mitigasi:* Terapkan HTTP/2 di reverse proxy atau gunakan subdomain terpisah (*connection domain partitioning*).

### 2. Ephemeral Port Exhaustion pada Redis Backplane
Saat cluster memproses ribuan pesan per detik, pembukaan soket koneksi TCP baru yang tidak terkontrol ke Redis dapat menghabiskan *ephemeral ports* pada host OS server.
*Mitigasi:* Pastikan instance `ConnectionMultiplexer` dikelola sebagai strictly **Singleton** (default pada `AddStackExchangeRedis`) dan atur `ThreadPool.SetMinThreads` untuk menghindari delay agregasi TCP thread starvation.

### 3. Broken Stickiness pada Multi-Node SignalR tanpa Redis
Jika load balancer tidak memiliki konfigurasi **Sticky Sessions** (Cookie/Affinity IP) saat SignalR melakukan negosiasi:
* Request `POST /negotiate` masuk ke Node A.
* Request upgrade `GET /hub (WebSocket)` masuk ke Node B.
* *Dampak:* Node B menolak koneksi dengan HTTP 404/400 karena ID koneksi tidak terdaftar secara lokal.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Blokir Thread Melalui Sync-over-Async di Hub Method
```csharp
// ANTI-PATTERN: Menyebabkan ThreadPool Starvation instan
public void FetchMarketData()
{
    var data = _repository.GetDataAsync().Result; // DEADLOCK / THREAD EXHAUSTION
    Clients.Caller.SendAsync("Data", data).Wait();
}

// SOLUSI: Murni Asinkron end-to-end
public async Task FetchMarketData(CancellationToken cancellationToken)
{
    var data = await _repository.GetDataAsync(cancellationToken);
    await Clients.Caller.ReceiveTelemetry(data);
}
```

### Kesalahan Fatal 2: Menyimpan State Klien di Field Instance Hub
```csharp
// ANTI-PATTERN: Hub dibuat dan dihancurkan per RPC call
public class BadHub : Hub
{
    private List<string> _activeUsers = new(); // AKAN SELALU KOSONG/RESET

    public void RegisterUser(string name)
    {
        _activeUsers.Add(name); 
    }
}

// SOLUSI: Simpan state pada Singleton Store thread-safe terpisah
public class GoodHub : Hub
{
    private readonly IActiveUserManager _userManager;
    public GoodHub(IActiveUserManager userManager) => _userManager = userManager;

    public async Task RegisterUser(string name) => 
        await _userManager.AddAsync(Context.ConnectionId, name);
}
```

### Kesalahan Fatal 3: Mengabaikan Backpressure pada Background Service
```csharp
// ANTI-PATTERN: Unbounded buffer dapat meledakkan RAM
var channel = Channel.CreateUnbounded<Payload>();

// SOLUSI: Selalu gunakan Bounded Channel dengan strategi FullMode terdefinisi
var channel = Channel.CreateBounded<Payload>(new BoundedChannelOptions(10_000)
{
    FullMode = BoundedChannelFullMode.Wait
});
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Selalu Gunakan Strongly-Typed Hubs (`Hub<T>`):** Eliminasi penggunaan string mentah dalam `SendAsync("MethodName", ...)`. Perubahan nama method pada interface `T` akan dideteksi saat proses kompilasi kode.
2. **Kendalikan Ukuran Frame Payload Jaringan:** Konfigurasi batas eksplisit pada `HubOptions.MaximumReceiveMessageSize`. Nilai default adalah 32 KB. Jangan pernah menaikkannya tanpa batasan untuk mencegah eksploitasi Denial of Service (DoS) melalui alokasi memori berukuran gigantik.
3. **Propagasi `CancellationToken`:** Alirkan token pembatalan dari method Hub atau worker hingga ke layer I/O terendah (`Database`, `Redis`, `Channels`).
4. **Desain Hub Sebagai Thin-Controller Layer:** Jangan letakkan kalkulasi bisnis kompleks di dalam Hub. Delegasikan ke service layer atau masukkan ke in-process queue untuk dikerjakan worker.
5. **Autentikasi di Jalur Handshake:** Lakukan autentikasi dan otorisasi hanya pada tahap inisiasi koneksi/negotiate. Mengenkripsi dan mendekode token otentikasi di setiap frame kecil transmisi membuang siklus CPU yang signifikan.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Serialisasi Zero-Copy via MessagePack
Dalam pengujian throughput tinggi, serialisasi MessagePack menghasilkan throughput hingga 3x lipat lebih tinggi dibanding System.Text.Json dengan pemakaian alokasi memori GC Gen 0 yang turun drastis:

```csharp
builder.Services.AddSignalR()
    .AddMessagePackProtocol(options =>
    {
        options.SerializerOptions = MessagePackSerializerOptions.Standard
            .WithResolver(CompositeResolver.Create(
                StandardResolver.Instance,
                ContractlessStandardResolver.Instance
            ));
    });
```

### 2. Tuning Kestrel Transport Socket Limits
Ubah konfigurasi soket Kestrel untuk menangani beban konkurensi masif di lingkungan Linux:

```csharp
builder.WebHost.ConfigureKestrel(serverOptions =>
{
    serverOptions.Limits.MaxConcurrentConnections = 100_000;
    serverOptions.Limits.MaxConcurrentUpgradedConnections = 100_000;
    serverOptions.Limits.Http2.MaxStreamsPerConnection = 1000;
});
```

### 3. Mengurangi Overhead Context Switching ThreadPool
Secara default, ThreadPool .NET bertambah secara bertahap saat terjadi starvation. Pada aplikasi real-time yang memproses lonjakan lalu lintas ekstrem, konfigurasikan thread minimum lebih awal:

```csharp
ThreadPool.SetMinThreads(workerThreads: 256, completionPortThreads: 256);
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mengamankan Otentikasi WebSocket (Token Negotiation)
Protokol WebSocket standar pada browser JavaScript API (`new WebSocket()`) tidak mendukung penambahan custom HTTP Header (seperti `Authorization: Bearer <TOKEN>`). SignalR mengatasi ini dengan mengirimkan access token melalui URL query string saat negotiation.

**Pipeline Konfigurasi JWT Bearer Authentication:**

```csharp
// Program.cs
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = "https://identity.enterprise.internal";
        options.TokenValidationParameters = new()
        {
            ValidateAudience = true,
            ValidAudience = "realtime-cluster"
        };

        options.Events = new JwtBearerEvents
        {
            OnMessageReceived = context =>
            {
                // Ambil token dari query string khusus endpoint SignalR Hub
                var accessToken = context.Request.Query["access_token"];
                var path = context.HttpContext.Request.Path;
                
                if (!string.IsNullOrEmpty(accessToken) && 
                    path.StartsWithSegments("/hubs"))
                {
                    context.Token = accessToken;
                }
                return Task.CompletedTask;
            }
        };
    });
```

### 2. Proteksi Cross-Site WebSocket Hijacking (CSWSH)
Penyerang dari situs jahat dapat mengarahkan browser korban yang terotentikasi untuk membuka koneksi WebSocket ke server Anda. 
* Mitigasi: Validasi origin secara ketat melalui ASP.NET Core CORS middleware.
* Larang origin wildcard `*` bila `AllowCredentials()` diaktifkan.

```csharp
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins("https://dashboard.production.internal") // KETAT: No Wildcards!
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials();
    });
});
```

### 3. Otorisasi Tingkat Hub dan Method
Terapkan atribut otorisasi secara deklaratif menggunakan RBAC atau Claims-based policies:

```csharp
[Authorize(Roles = "Trader,Broker")]
public sealed class SecureTradingHub : Hub<ITradingClient>
{
    [Authorize(Policy = "ExecuteOrdersOnly")]
    public async Task PlaceBid(OrderOrderDto order)
    {
        // Hub invocation context dijamin memiliki ClaimsPrincipal yang sah
        var traderId = Context.UserIdentifier;
        // ...
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendiagnosis latensi dan degradasi sistem pada komunikasi real-time, kita mengintegrasikan `System.Diagnostics.Activity` (OpenTelemetry Tracing) dan metrik bawaan.

### Trace Context Propagation Melalui Hub

```csharp
// Diagnostics/DiagnosticsConfig.cs
using System.Diagnostics;

namespace RealTimeEngine.Diagnostics;

public static class DiagnosticsConfig
{
    public const string SourceName = "RealTimeEngine.Telemetry";
    public static readonly ActivitySource ActivitySource = new(SourceName, "1.0.0");
}
```

```csharp
// Hubs/ObservableHub.cs
using System.Diagnostics;
using Microsoft.AspNetCore.SignalR;
using RealTimeEngine.Diagnostics;

public class ObservableHub : Hub
{
    public async Task BroadcastMessage(string message)
    {
        using Activity? activity = DiagnosticsConfig.ActivitySource.StartActivity(
            "Hub:BroadcastMessage", 
            ActivityKind.Server);

        activity?.SetTag("signalr.connection_id", Context.ConnectionId);
        activity?.SetTag("signalr.user_id", Context.UserIdentifier);

        // Eksekusi logic downstream
        await Task.Yield(); 
    }
}
```

### Monitoring Metrik Internal Kestrel & SignalR
ASP.NET Core mengekspos EventCounters dan System.Diagnostics.Metrics yang dapat di-scrape oleh Prometheus:
* `microsoft.aspnetcore.connections.active_connections`: Jumlah koneksi transport soket yang saat ini terbuka.
* `microsoft.aspnetcore.connections.connection_duration`: Distribusi durasi bertahannya soket di Kestrel.
* `signalr.server.active_connections`: Metrik spesifik jumlah koneksi SignalR Hub yang aktif.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### CLI & Setup Commands
```bash
# Tambah paket esensial SignalR & Optimasi
dotnet add package Microsoft.AspNetCore.SignalR.StackExchangeRedis
dotnet add package Microsoft.AspNetCore.SignalR.Protocols.MessagePack

# Menjalankan Redis lokal via Docker untuk Backplane development
docker run -d --name signalr-redis -p 6379:6379 redis:alpine
```

### Cheat Sheet Konfigurasi C#

```csharp
// 1. Strongly-Typed Hub Declaration
public class AppHub : Hub<IClientContract> {}

// 2. Multicast Target Rules
Clients.All.Send();                           // Ke seluruh node & koneksi
Clients.Caller.Send();                        // Ke pengirim RPC ini saja
Clients.Group("group_name").Send();           // Ke seluruh anggota group tertentu
Clients.User("user_guid").Send();             // Ke seluruh koneksi milik User spesifik (via ClaimTypes.NameIdentifier)
Clients.Client("connection_id").Send();       // Ke satu soket koneksi tunggal

// 3. High-Performance Bounded Channel
var ch = Channel.CreateBounded<T>(new BoundedChannelOptions(10_000) {
    FullMode = BoundedChannelFullMode.Wait,
    SingleReader = true
});

// 4. Client WebSocket Auth (JavaScript client)
const connection = new signalR.HubConnectionBuilder()
    .withUrl("/hubs/chat", {
        accessTokenFactory: () => this.myJwtToken
    })
    .withAutomaticReconnect([0, 2000, 5000, 10000, null])
    .build();
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Basic (Pilihan Ganda)

#### Soal 1
Mengapa objek instance kelas SignalR Hub didestruksi (disposed) setelah pemanggilan sebuah RPC selesai, bukan dipertahankan selama masa hidup koneksi TCP?
* A. Untuk menghemat alokasi memori GC dengan menerapkan pola transient lifecycle dan mencegah state concurrency leak antar-RPC invocation.
* B. Karena Kestrel tidak mendukung koneksi TCP persisten.
* C. Karena protokol WebSocket secara berkala menutup koneksi setiap data selesai ditransmisikan.
* D. Supaya instance Hub dapat di-serialize langsung ke file swap sistem operasi.

#### Soal 2
Jika klien web berjalan di balik reverse proxy yang melarang implementasi WebSockets, transport fallback apa yang selanjutnya dicoba oleh protokol negosiasi bawaan SignalR?
* A. HTTP/3 QUIC Datagrams.
* B. Server-Sent Events (SSE).
* C. Raw TCP Streaming Socket.
* D. gRPC Bi-directional Channel.

#### Soal 3
Bagaimana cara JavaScript SignalR Client mengirimkan JSON Web Token (JWT) pada koneksi browser murni saat membuka koneksi transport WebSockets?
* A. Melalui Header `Authorization: Bearer` bawaan pada objek constructor `new WebSocket()`.
* B. Melalui TLS Client Certificate handshake saja.
* C. Melalui Query String parameter `access_token` yang dinegosiasi pada endpoint.
* D. Browser secara otomatis menyisipkan token ke dalam binary payload frame data.

#### Soal 4
Apa tujuan konfigurasi `SingleReader = true` saat mendeklarasikan `BoundedChannelOptions` pada `System.Threading.Channels`?
* A. Melarang kelas selain BackgroundService untuk membaca file.
* B. Memungkinkan channel runtime mengeliminasi mutual exclusion locks sinkronisasi saat de-queue, meningkatkan throughput pembacaan.
* C. Memastikan hanya ada 1 klien SignalR yang menerima pesan broadcast.
* D. Mengunci alur kerja pembaca agar berjalan secara synchronous blocking.

#### Soal 5
Pada scale-out SignalR multi-server farm, apa fungsi mendasar dari **Redis Backplane**?
* A. Menyimpan riwayat seluruh percakapan klien ke database disk secara permanen.
* B. Meneruskan pesan broadcast yang dipicu dari satu node server ke node server lainnya melalui mekanisme Pub/Sub.
* C. Menggantikan peran Kestrel engine sebagai penerima frame koneksi WebSockets.
* D. Menangani enkripsi TLS/SSL sebelum paket masuk ke jaringan internal.

---

### Bagian B: Intermediate (Studi Kasus & Analisis)

#### Soal 6
Jelaskan apa yang terjadi jika aplikasi high-throughput mengonfigurasi `Channel.CreateBounded<T>` dengan kapasitas 100 item dan `BoundedChannelFullMode.Wait`, sementara worker consumer mengalami crash atau terhambat (stalled) dalam memproses item tersebut! Apa dampaknya terhadap thread pool dan memory server?

#### Soal 7
Analisis skenario kegagalan: Sebuah sistem monitoring arsitektur multi-node SignalR menggunakan Redis Backplane. Namun, developer mengabaikan konfigurasi **Sticky Sessions** (Session Affinity) pada L7 Load Balancer. Jelaskan secara teknis kegagalan negosiasi yang akan dialami oleh klien web baru!

#### Soal 8
Sebutkan dua keuntungan utama dan satu trade-off penggunaan protokol **MessagePack** dibandingkan protokol **JSON** default pada SignalR!

#### Soal 9
Mengapa method Hub SignalR berikut sangat dilarang digunakan di lingkungan produksi enterprise?
```csharp
public async Task SendNotification(string payload)
{
    Task.Run(() => {
        var enriched = _service.Process(payload);
        Clients.All.SendAsync("Notify", enriched);
    });
}
```

#### Soal 10
Ketika koneksi klien terputus secara mendadak akibat kehilangan sinyal jaringan seluler (tanpa pengiriman graceful disconnect frame TCP FIN/RST), komponen internal mana pada ASP.NET Core SignalR yang mendeteksi putusnya koneksi tersebut, dan berdasarkan mekanisme apa?

---

### KUNCI JAWABAN & PEMBAHASAN EVALUASI

#### Jawaban Bagian A
1. **A** — SignalR Hub didesain transient per pemanggilan RPC untuk mencegah state collision concurrent, membersihkan resource scoped dependencies (DI), dan menjaga memory footprint server tetap dapat diprediksi.
2. **B** — Urutan fallback otomatis SignalR adalah: WebSockets -> Server-Sent Events (SSE) -> Long Polling.
3. **C** — Karena keterbatasan API WebSocket standar W3C di browser yang tidak mengizinkan kustomisasi HTTP Header saat handshake, SignalR mengalirkan token melalui query string `access_token` pada fase negotiate dan handshake.
4. **B** — Memberi tahu runtime bahwa hanya ada satu pembaca tunggal mengaktifkan optimasi jalur lock-free memory ring buffer, menghilangkan instruksi sinkronisasi CAS (*Compare-And-Swap*) antar consumer.
5. **B** — Redis Backplane bertindak sebagai message dispatcher antar-instance ASP.NET Core. Setiap instance mendengarkan topic internal Redis dan meneruskan pesan tersebut ke koneksi lokal yang dikelolanya.

#### Jawaban Bagian B
6. **Analisis Bounded Channel:**
   * Ketika kapasitas 100 terisi penuh dan consumer stalled, pemanggilan downstream `writer.WriteAsync(item)` akan menunda eksekusi asinkron (mengembalikan Task yang belum completed).
   * Producer threads (misal: HTTP Request API Controllers) tidak memblokir ThreadPool OS thread secara sinkron, melainkan state machine asinkron ditangguhkan.
   * Memory server aman dari `OutOfMemoryException` karena batas buffer 100 item dipertahankan (*Backpressure dipertahankan*).
   * Request API baru pada hulu pada akhirnya akan mengalami timeout atau mengembalikan response `503 Service Unavailable` saat HTTP request timeout terlampaui.

7. **Analisis Kegagalan Negosiasi Sticky Sessions:**
   * Inisiasi koneksi SignalR diawali dengan HTTP `POST /hub/negotiate` yang ditangani oleh Node A, menghasilkan `ConnectionToken` yang terdaftar di memori lokal Node A.
   * Saat klien browser meng-upgrade transport dan mengirimkan request lanjutan `GET /hub?id={ConnectionToken}` via WebSocket, load balancer tanpa sticky session dapat mengarahkan koneksi tersebut ke Node B.
   * Karena Node B tidak mengenali token koneksi lokal tersebut (token negotiation inisial tidak disimpan di Redis, hanya disimpan lokal), Node B merespons dengan `HTTP 404 Not Found` atau `HTTP 400 Bad Request`. Proses handshake gagal total.

8. **MessagePack Trade-Offs:**
   * *Keuntungan 1:* Payload berukuran biner jauh lebih padat (30% - 70% lebih kecil dibanding JSON stringified), menurunkan konsumsi network I/O.
   * *Keuntungan 2:* Serialisasi CPU zero-copy dan reduksi alokasi string heap, menurunkan frekuensi Garbage Collection Gen 0/1/2.
   * *Trade-off:* Payload tidak human-readable (sulit di-debug menggunakan network sniffer standar browser) dan menuntut klien memiliki runtime parser/serializer MessagePack eksternal.

9. **Masalah Anti-Pattern Thread Unbounded Fire-and-Forget:**
   * `Task.Run` di dalam method Hub memisahkan eksekusi dari dependency injection scope dan HubContext siklus hidup koneksi.
   * Instance Hub mungkin sudah terdisposisi saat `Clients.All` diakses, mengakibatkan `ObjectDisposedException`.
   * Pengecualian (*unhandled exceptions*) di dalam `Task.Run` tersebut tidak tertangkap oleh pipeline global exception handler, memicu risiko silent failure atau unobserved task exceptions.

10. **Deteksi Disconnect Tak Terduga (Keep-Alive Heartbeat):**
    * Dideteksi oleh mekanisme **SignalR Heartbeat / Keep-Alive Monitoring** di layer Kestrel.
    * Server mengirim Ping frame setiap interval waktu tertentu (default 15 detik via `KeepAliveInterval`).
    * Jika dalam rentang waktu tertentu (default 30 detik via `ClientTimeoutInterval`) server sama sekali tidak menerima frame respons (baik data, pong frame, maupun activity frame) dari socket klien, server berasumsi bahwa koneksi telah terputus (zombie connection), membatalkan socket descriptor, dan memicu callback `OnDisconnectedAsync(exception)` di Hub.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: Real-Time Distributed Server Fleet Metrics Aggregator

### Deskripsi Skenario
Rancang dan bangun sistem telemetry metrics aggregator untuk memantau performa 500 node server secara real-time. Setiap node server mengirimkan metriks CPU, RAM, dan I/O setiap 500 milidetik via REST API ingestion. Dashboard engineer web browser harus memvisualisasikan data ini dengan interval update stabil tanpa latensi visual dan konsumsi CPU server yang minimal.

### Kriteria & Batasan Teknis:
1. **Strongly-Typed Hub:** Buat SignalR Hub dengan nama `FleetMetricsHub` yang mengimplementasikan interface `IFleetMetricsClient` yang strongly-typed.
2. **In-Process Bounded Pipeline:** 
   * REST Controller mem-push metriks masuk ke dalam `Channel<ServerMetricsRecord>`.
   * Kapasitas maksimum channel dibatasi sebesar **50.000 items**.
   * Jika buffer penuh, sistem harus menerapkan mode `DropOldest` (karena dalam real-time monitoring, metriks usang tidak relevan dibandingkan kondisi terkini).
3. **Batch Aggregation Worker:**
   * Buat `BackgroundService` (`FleetBroadcasterWorker`) yang membaca dari channel.
   * Lakukan batching: Kumpulkan metrik selama 100ms atau per 50 item (mana yang tercapai lebih dulu) sebelum mengirim multicast ke SignalR Hub untuk menghemat context switching I/O jaringan.
4. **Protokol Biner:** Daftarkan dan konfigurasikan serialisasi binary **MessagePack** pada pipeline SignalR.
5. **Simulasi Fault Tolerance & Client Testing:**
   * Tulis sebuah console app sederhana menggunakan `Microsoft.AspNetCore.SignalR.Client` yang mensimulasikan pemutusan koneksi (network drop) dan pastikan implementasi `.WithAutomaticReconnect()` bekerja tanpa crash.
6. **Observabilitas:** Tambahkan log kustom terstruktur yang mencatat jumlah pesan yang di-drop jika throughput melampaui kemampuan broadcasting.

### Verifikasi Keberhasilan Praktikum:
* Eksekusi stress-test menggunakan tools seperti ApacheBench atau `k6` ke REST endpoint ingestion dengan load 5.000 request/detik.
* Pastikan alokasi memori process (`Working Set Private`) pada Task Manager atau `dotnet-counters` tetap stabil (datar) tanpa mengalami kenaikan linier (*memory leak free*).
* Periksa apakah console app client menerima data metriks batch yang dikirim oleh `FleetBroadcasterWorker` secara konsisten.