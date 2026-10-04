# BAB 07: Quiz, Challenge, & Knowledge Check
**Asynchronous Messaging & Real-Time Communication**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Pertanyaan 1: Paradigma Komunikasi Distribusi & Boundary Protocols
Jelaskan perbedaan mendasar secara arsitektural antara Request-Response (REST/gRPC), Event-Driven Messaging (AMQP/Kafka), dan Real-Time Push (WebSockets/SignalR). Kapan sebuah sistem harus beralih dari model *synchronous RPC* ke *asynchronous message broker*, dan kapan data harus di-*push* menggunakan persistent bidirectional connection alih-alih polling?

### Pertanyaan 2: SignalR Transport Negotiation Lifecycle
Bagaimana mekanisme *transport fallback negotiation* bekerja pada ASP.NET Core SignalR? Uraikan urutan evaluasi dari WebSockets, Server-Sent Events (SSE), hingga Long Polling. Apa implikasi performa dan alokasi resource pada web server jika reverse proxy (seperti NGINX atau AWS ALB) gagal mengonfigurasi header `Upgrade: websocket` dan memaksa koneksi jatuh ke Long Polling?

### Pertanyaan 3: Delivery Semantics & Idempotency
Dalam asynchronous messaging, jelaskan perbedaan matematis dan praktis antara *At-Most-Once*, *At-Least-Once*, dan *Exactly-Once* delivery semantics. Mengapa di tingkat infrastruktur terdistribusi (seperti RabbitMQ atau Apache Kafka), *Exactly-Once* secara murni hampir mustahil dijamin tanpa koordinasi tingkat aplikasi? Bagaimana *Idempotency Key* diimplementasikan pada consumer ASP.NET Core untuk memitigasi duplikasi pesan?

### Pertanyaan 4: Message Topology: Queues vs. Partitioned Logs
Bandingkan model konsumsi pesan berbasis *Queue* (AMQP/RabbitMQ) dengan *Partitioned Commit Log* (Apache Kafka/Azure Event Hubs). Bagaimana ASP.NET Core `BackgroundService` (`IHostedService`) memperlakukan horizontal scaling, pemrosesan konkurensi, dan urutan pesan (*message ordering*) di bawah kedua model topologi tersebut?

### Pertanyaan 5: Backpressure & Flow Control
Apa yang dimaksud dengan *Backpressure* dalam konteks real-time streaming dan message consumption di ASP.NET Core? Apa yang akan terjadi pada alokasi memory (RAM) proses .NET jika sebuah `Channel<T>` atau WebSocket pipeline menerima data masuk dengan laju 50.000 pesan/detik sementara consumer downstream hanya mampu mengeksekusi I/O database pada laju 2.000 pesan/detik tanpa unbounded buffer mitigation?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Pertanyaan 1: SignalR Scale-Out Mechanics & Redis Backplane
Pada deployment multi-instance ASP.NET Core di balik Load Balancer, jelaskan siklus hidup pesan saat Server A mengirim pesan ke spesifik `ConnectionId` atau `Group` yang terhubung secara fisik pada Server B. Bagaimana Redis Backplane memfasilitasi koordinasi ini, apa overhead serialization yang terjadi, dan mengapa Redis Backplane dapat menjadi bottleneck bandwidth throughput tinggi dibandingkan Azure SignalR Service?

### Pertanyaan 2: Transactional Outbox Pattern & 2PC Alternative
Jelaskan kegagalan sistemik (misal: *Dual-Write Problem*) yang diselesaikan oleh Transactional Outbox Pattern ketika ASP.NET Core memutasi state database melalui Entity Framework Core sekaligus mem-publish event ke Message Broker. Bagaimana implementasi Outbox Publisher bekerja menggunakan `DbContextTransaction`, dan bagaimana menangani konkurensi publisher agar urutan pesan per aggregate root tidak teracak?

### Pertanyaan 3: Dead-Letter Exchange (DLX) & Exponential Backoff Resilience
Bagaimana siklus hidup *poison message* diisolasi pada message bus enterprise (seperti MassTransit atau Wolverine)? Jelaskan mekanisme teknis konfigurasi *retry policy* dengan *exponential backoff and jitter*, transisi pesan ke Dead-Letter Queue (DLQ), serta strategi perancangan alerting diagnostik sebelum pesan tersebut dibuang atau di-*redrive*.

### Pertanyaan 4: Zombie Connections & Application-Level Heartbeats
Mengapa *TCP Keep-Alive* tingkat OS sering kali tidak memadai untuk mendeteksi *silent connection drops* (misalnya: kabel jaringan terputus mendadak atau firewall state table timeout) pada WebSocket/SignalR? Bagaimana internal ASP.NET Core SignalR mengimplementasikan *Ping Interval* dan *Client Timeout*, serta apa konsekuensi setting timeout yang terlalu agresif di lingkungan high-latency mobile networks?

### Pertanyaan 5: High-Performance Memory Pipeline (System.IO.Pipelines)
Mengapa ASP.NET Core WebSockets dan Kestrel beralih dari `System.IO.Stream` dan `byte[]` buffers tradisional ke `System.IO.Pipelines` (`PipeReader`/`PipeWriter`)? Analisis bagaimana alokasi memory pada *Large Object Heap* (LOH) dan frekuensi *Garbage Collection Gen 2* dapat ditekan secara dramatis menggunakan `MemoryPool<byte>` dan zero-copy slicing saat mem-parsing frame WebSocket biner bervolume tinggi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Thundering Herd & Redis Backplane Saturation
Sebuah platform live streaming olahraga berskala besar menggunakan ASP.NET Core SignalR untuk membagikan skor pertandingan dan live chat. Sistem di-deploy pada 20 node cluster Kubernetes di balik NGINX Ingress Controller dengan konfigurasi Redis Backplane. 

Saat penalti penentu terjadi, 250.000 pengguna menerima update event secara serentak (`Clients.All.SendAsync(...)`). Seketika:
- CPU Redis menyentuh 100%.
- Latensi broadcast membengkak dari 40ms menjadi 18 detik.
- Node ASP.NET Core mulai melempar `RedisTimeoutException`.
- Kubernetes liveness probe gagal karena thread starvation, memicu cascade restarts pada seluruh Pod Kestrel.

```
[250,000 Clients] <--- WebSocket ---> [20 Pods ASP.NET Core]
                                            |
                                  (All Pub/Sub Traffic)
                                            v
                                  [Single Redis Instance] (CPU 100% - Bottleneck)
```

**Pertanyaan Diagnostik:**
1. Mengapa memanggil `Clients.All.SendAsync()` pada topologi Redis Backplane standar menghasilkan amplifikasi traffic sebesar $O(N \times M)$ (di mana $N$ adalah jumlah node server dan $M$ adalah total koneksi)?
2. Bagaimana Anda mendesain ulang arsitektur real-time ini untuk mengeliminasi bottleneck Redis? Uraikan trade-off antara MessagePack protocol serialization, local caching, client-side packet coalescing, Redis sharding/clustering, dan offloading connection management ke edge layer (misalnya Azure SignalR Service atau custom gateway).

---

### Skenario B: Out-of-Order Execution in Distributed Financial Ledger
Sebuah sistem core banking microservices menggunakan MassTransit dan RabbitMQ. Terdapat dua event yang dipublish oleh `AccountService`:
1. `DepositInitiatedEvent` ($10,000)
2. `AccountFrozenEvent` (Perintah pembekuan rekening oleh tim fraud)

Karena fluktuasi beban jaringan dan multithreaded consumers di `LedgerService` (konkurensi worker disetel ke 16 thread per instance), `AccountFrozenEvent` diproses lebih lambat daripada rentetan `DepositCompletedEvent` berikutnya. Akibatnya, dana sebesar $10,000 berhasil ditarik oleh user beberapa milidetik sebelum status pembekuan rekening berhasil di-*commit* ke database Ledger.

**Pertanyaan Diagnostik:**
1. Identifikasi *flaw* arsitektural pada konfigurasi antrean RabbitMQ standar yang menyebabkan hilangnya jaminan urutan (*ordering guarantee*) saat concurrency scale-out ditingkatkan.
2. Rancang solusi end-to-end untuk memastikan transaksi finansial pada rekening yang sama diproses secara strictly-sequential tanpa mengorbankan throughput sistem secara global! Jelaskan peran *Partition Keys*, *Consistent Hash Exchange*, *Saga State Machines*, atau *Single Active Consumer* pattern dalam penyelesaian ini.

---

### Skenario C: Architectural Trade-Off: High-Density Live Telemetry Dashboard
Perusahaan logistik global memantau 50.000 armada truk secara real-time. Setiap truk mengirimkan telemetri GPS dan sensor suhu setiap 500 milidetik via MQTT/AMQP ke ingestion service internal. 

Terdapat 1.200 web dashboard milik operator operasional yang memantau pergerakan armada tersebut. Tim engineering berdebat mengenai protokol komunikasi data dari backend ASP.NET Core ke client browser:
- **Opsi 1:** WebSockets (Full Duplex persistent socket via SignalR).
- **Opsi 2:** Server-Sent Events (SSE) (HTTP/2 persistent mono-directional stream).
- **Opsi 3:** HTTP/2 atau HTTP/3 gRPC Web Streaming.
- **Opsi 4:** Polling via REST API dengan short-interval caching (HTTP GET setiap 1 detik).

**Pertanyaan Diagnostik:**
1. Bedah kelebihan, kelemahan, overhead memory per-koneksi, serta limitasi protokol browser untuk masing-masing opsi di atas berdasarkan profil traffic tersebut (server-to-client continuous unidirectional push)!
2. Protokol mana yang secara arsitektural paling optimal dan *resilient* jika operator sering mengalami gangguan jaringan mobile (packet loss tinggi)? Justifikasi pilihan Anda dengan parameter throughput, CPU utilization, dan kemudahan traversing proxy/firewall enterprise.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Real-Time Flash Auction & Settlement Engine

#### 1. Problem Statement
Bangun microservice prototype lelang online real-time (*Flash Auction Engine*) menggunakan **ASP.NET Core Web API**, **SignalR**, **MassTransit**, dan database engine pilihan Anda (PostgreSQL/SQL Server via EF Core). Sistem harus mampu menangani ribuan penawaran harga (*bids*) per detik secara konkuren, menyiarkan penawaran tertinggi secara real-time ke semua peserta, menjamin konsistensi data finansial tanpa race condition, serta memproses settlement pemenang secara asinkron ketika waktu lelang berakhir.

#### 2. Functional & Technical Requirements
1. **SignalR Bidding Hub:**
   - Client dapat bergabung ke Auction Room berbasis ID (`JoinAuctionGroup(string auctionId)`).
   - Menggunakan strongly-typed Hub (`IHubContext<AuctionHub, IAuctionClient>`).
   - Implementasikan *Rate Limiting* berbasis sliding window pada endpoint hub (maksimal 5 bids per detik per koneksi).
2. **Core Ingestion & Concurrency Guard:**
   - Endpoint/Method penawaran: `PlaceBid(Guid auctionId, decimal amount)`.
   - Bid hanya valid jika bernilai lebih tinggi dari `CurrentHighestBid`.
   - Tangani konkurensi ekstrem: Gunakan database concurrency control (Optimistic Concurrency via row versioning atau Pessimistic Row Locking via `SELECT FOR UPDATE`) untuk mencegah race condition dua bid bernilai sama diterima bersamaan.
3. **Transactional Outbox & Event Publishing:**
   - Setelah penawaran baru sukses di-*commit* ke database, sebuah `BidPlacedEvent` harus disimpan via **Transactional Outbox Pattern** sebelum dipublish ke broker (RabbitMQ/In-Memory Test Bus).
   - Event ini memicu consumer latar belakang yang bertugas menyiarkan update harga ke SignalR Hub (`Clients.Group(auctionId).ReceiveHighestBid(...)`).
4. **Auction Expiration & Asynchronous Settlement:**
   - Simulasikan expiry lelang (misal: durasi lelang 60 detik).
   - Saat lelang berakhir, sistem mem-publish `AuctionClosedEvent`.
   - Consumer settlement memproses event tersebut, menandai pemenang lelang, dan mengeksekusi mock payment gateway call dengan *retry policy* (3 kali retry, backoff 2 detik) dan Dead-Letter Queue jika transaksi gagal.

#### 3. Constraints & Non-Functional Requirements
- **Zero In-Memory State for Data Integrity:** State lelang tidak boleh disimpan murni di memori aplikasi (static dictionary) untuk menghindari data loss saat crash, tetapi caching layer (misal: Redis Cache) diperbolehkan untuk percepatan validasi *read*.
- **Backpressure Handling:** Gunakan `System.Threading.Channels.Channel<T>` bounded buffer jika ada internal queuing pipeline.
- **Serialization:** Implementasikan MessagePack protocol pada SignalR Hub atau optimalkan JSON Serializer options (mengabaikan null values dan menggunakan camelCase).
- **Target Metrics:** Pipeline penawaran harus lolos uji beban lokal minimal 500 requests/second dengan p99 latency < 100ms.

#### 4. Expected Output
1. **Source Code Implementation:**
   - File Hub: `AuctionHub.cs` & `IAuctionClient.cs`.
   - File Entity & DB Context configuration: Konfigurasi Outbox dan Concurrency Token.
   - File Consumer: `BidPlacedEventConsumer.cs` dan `AuctionClosedConsumer.cs`.
   - Setup konfigurasi di `Program.cs` (DI registration, MassTransit setup, SignalR protocol setup).
2. **Architectural Rationale Document (Markdown):**
   - Penjelasan teknis penanganan race condition saat 100 user menawar di milidetik yang sama.
   - Diagram alir data dari penawaran masuk -> database commit -> outbox dispatch -> mass transit -> signalr broadcast.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan layer arsitektural OSI & transport level antara HTTP/1.1, HTTP/2, HTTP/3, WebSockets, dan raw TCP sockets.
- [ ] Siklus hidup negosiasi transport SignalR (`Negotiate`, WebSocket upgrade handshake, SSE, Long Polling fallback).
- [ ] Trade-off fundamental antara Message Broker Queue (RabbitMQ) vs Distributed Append-Only Log (Apache Kafka).
- [ ] Mengapa *Dual-Write* (menulis ke database dan mem-publish event secara berurutan tanpa koordinasi) adalah anti-pattern terdistribusi, dan bagaimana Transactional Outbox Pattern menyelesaikannya.
- [ ] Mekanisme kerja Idempotent Consumer menggunakan composite keys atau transaction receipts.
- [ ] Konsep Competing Consumers Pattern vs Exclusive/Single Active Consumer.
- [ ] Dampak alokasi memori Large Object Heap (LOH) akibat buffer data stream yang tidak dikelola dengan `ArrayPool<T>` atau `System.IO.Pipelines`.
- [ ] Batasan arsitektur Redis Pub/Sub untuk SignalR Scale-Out di lingkungan massive broadcast throughput.

### Saya tidak perlu menghafal:
- [ ] Detail byte-by-byte masking key header WebSocket RFC 6455 (engine Kestrel menanganinya secara native).
- [ ] Konfigurasi internal Erlang pada broker RabbitMQ secara mendalam.
- [ ] Seluruh overload sintaks fluent API MassTransit atau Wolverine configuration (cukup pahami prinsip registration bus, consumer, dan outbox).
- [ ] Urutan raw frame binary format MessagePack (cukup pahami cara meregistrasikan serializer contract resolver).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi ASP.NET Core SignalR strongly-typed hub dengan autentikasi berbasis JWT token via query string fallback.
- [ ] Mengimplementasikan Redis Backplane atau Azure SignalR Service pada ASP.NET Core cluster dengan benar.
- [ ] Mengimplementasikan Transactional Outbox Pattern menggunakan MassTransit / Entity Framework Core integration.
- [ ] Mengonfigurasi Retry Policy, Circuit Breaker, dan Dead-Letter Queue (DLQ) pada consumer message bus.
- [ ] Menggunakan `System.Threading.Channels` untuk mengelola backpressure in-memory secara asynchronous.
- [ ] Menangani race condition dan concurrent update pada database menggunakan EF Core concurrency tokens (`[Timestamp]` / `.IsRowVersion()`).
- [ ] Melakukan troubleshooting koneksi WebSocket yang sering putus (*dropped/aborted*) menggunakan diagnostic logging dan network tracing tool (Wireshark/Fiddler).