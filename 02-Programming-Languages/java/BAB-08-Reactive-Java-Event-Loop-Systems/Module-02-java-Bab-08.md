# Kurikulum Rekayasa Perangkat Lunak Enterprise: Java
## Kategori: 02-Programming-Languages
### BAB-08: Reactive Java & Event Loop Systems
#### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Internal Runtime Reactive**: Memahami secara mekanistik siklus hidup execution pipeline Project Reactor (*Assembly Time*, *Subscription Time*, *Runtime/Execution Time*) serta optimasi *Operator Fusion* (Scalar, Synchronous, Asynchronous).
2. **Menguasai Threading Model & Memory Management Netty**: Mengoperasikan Netty `EventLoopGroup`, mengelola pooling memori off-heap via `PooledByteBufAllocator` berbasis algoritma jemalloc, serta mencegah dan melacak *memory leak* melalui Netty `ResourceLeakDetector`.
3. **Mengimplementasikan Pola Konkurensi Reaktif Tingkat Lanjut**: Mengembangkan microservices berbasis non-blocking I/O yang mengimplementasikan *dynamic backpressure strategies*, *custom schedulers*, serta context propagation lintas batas thread (*Tracing & Security*).
4. **Mendiagnosis dan Mengoptimalkan Bottleneck Produksi**: Mendeteksi thread starvation, blocking calls pada Event Loop menggunakan Reactor BlockHound, serta mengonfigurasi tuning low-level kernel Linux (epoll, socket flags) untuk beban I/O masif berkemampuan throughput tinggi dengan latensi deterministik sub-milidetik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus memiliki pemahaman mendalam tentang:

*   **Spesifikasi Reactive Streams (JVM)**: Kontrak `Publisher<T>`, `Subscriber<T>`, `Subscription`, dan `Processor<T, R>` beserta aturan transisi state-nya.
*   **Java NIO Core**: Penggunaan `ByteBuffer`, `Channel`, `Selector`, dan transisi I/O multiplexing tingkat kernel (`select`, `poll`, `epoll`/`kqueue`).
*   **Java Concurrency & Memory Model (JMM)**: Visibilitas cache CPU, instruksi atomik (CAS), barrier memori, dan struktur antrean non-blocking (`ConcurrentLinkedQueue`, `MpscArrayQueue`).
*   **Dasar Project Reactor**: Penggunaan operator dasar `map`, `flatMap`, `filter`, `publishOn`, dan `subscribeOn`.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur reactive modern di ekosistem Java bertumpu pada simbiosis antara **Netty** (sebagai fondasi non-blocking I/O multiplexing) dan **Project Reactor** (sebagai *functional reactive programming abstraction layer*).

```
+-------------------------------------------------------------------------+
|                        Project Reactor API Layer                        |
|   Flux<T> / Mono<T> -> Operators (Assembly, Subscription, Execution)   |
|   Operator Fusion (ScalarCallable, Sync, Async) & ContextView           |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Backpressure Signaling (request(n))
                                   ▼
+-------------------------------------------------------------------------+
|                     Netty ChannelPipeline & Handlers                    |
|   Inbound Handlers  [ByteToMessageDecoder -> ReactiveBridgeHandler]     |
|   Outbound Handlers [MessageToByteEncoder <- FlowControlHandler]        |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Raw Bytes / ByteBuf
                                   ▼
+-------------------------------------------------------------------------+
|                  Netty EventLoop (Single Thread per Loop)               |
|   Task Queue (MpscQueue) | Scheduled Tasks | Epoll/KQueue Selector     |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Syscalls (epoll_wait, read, writev)
                                   ▼
+-------------------------------------------------------------------------+
|                           Linux Kernel Space                            |
|        TCP Ring Buffers (sk_buff) | epoll instance | NIC Driver        |
+-------------------------------------------------------------------------+
```

#### A. Anatomi Eksekusi Project Reactor: Tiga Fase Kritis

Banyak kegagalan arsitektur reaktif terjadi karena ketidakmampuan membedakan tiga fase eksekusi:

1.  **Assembly Time**: Terjadi saat rantai operator dideklarasikan.
    ```java
    Flux<String> pipeline = Flux.just("data")
        .map(String::toUpperCase)
        .filter(s -> s.startsWith("D"));
    ```
    Pada fase ini, **tidak ada data yang mengalir** dan **tidak ada thread eksekusi**. Yang terbentuk hanyalah pohon referensi objek deklaratif: `FluxFilter` membungkus `FluxMap`, yang membungkus `FluxJust`.
2.  **Subscription Time**: Terjadi saat metode `.subscribe(...)` dipanggil.
    *   Sinyal langganan berjalan **dari bawah ke atas** (upstream): `Subscriber` memanggil `Publisher.subscribe(Subscriber)`.
    *   Setiap operator membungkus subscriber downstream dengan subscriber internal miliknya sendiri (`MapSubscriber`, `FilterSubscriber`).
    *   Pada titik paling atas (sumber data), objek `Subscription` diinisiasi dan dioperasikan kembali **dari atas ke bawah** via `Subscriber.onSubscribe(Subscription)`.
3.  **Runtime / Execution Time**: Dimulai saat subscriber memanggil `Subscription.request(n)`.
    *   Sinyal data (`onNext`) mengalir **dari atas ke bawah** (downstream).
    *   Sinyal kontrol kapasitas (`request(n)`) mengalir **dari bawah ke atas** (upstream).
    *   Terminasi dikirimkan melalui sinyal `onComplete` atau `onError`.

#### B. Operator Fusion

Untuk meniadakan overhead alokasi antrean perantara dan thread context switching, Reactor menerapkan *Operator Fusion*:

*   **Macro-fusion**: Terjadi pada Assembly Time. Publisher diganti dengan publisher lain yang lebih optimal (contoh: `Flux.just(A).filter(...)` dapat langsung dievaluasi jika input konstan via optimasi compile-time/instansiasi).
*   **Micro-fusion**: Terjadi pada Subscription Time, terbagi dua:
    *   *Conditional Fusion*: Menghilangkan overhead pemanggilan `request(1)` berulang kali pada pipeline filtering. Subscriber upstream mengimplementasikan `ConditionalSubscriber`, sehingga jika suatu elemen didrop oleh filter, upstream langsung mengirim elemen berikutnya tanpa roundtrip `request(n)`.
    *   *Synchronous/Asynchronous Fusion*: Mengizinkan antrean internal dari operator upstream digunakan langsung oleh operator downstream jika mengimplementasikan interface `QueueSubscription<T>`, menghindari alokasi intermediate queue tambahan.

#### C. Thread Modeling: Netty EventLoop & Reactor Schedulers

*   **EventLoop Binding**: Setiap `Channel` (koneksi soket TCP) didaftarkan ke tepat **satu** `EventLoop` selama masa hidupnya.
*   **Run-to-Completion**: EventLoop memproses I/O dan mengeksekusi task dalam antrean internal (`io.netty.util.internal.shaded.org.jctools.queues.MpscArrayQueue`) menggunakan single OS thread, menjamin *thread-safety* mutlak tanpa locking primitif pada state koneksi tersebut.
*   **Scheduler Boundary**:
    *   `Schedulers.immediate()`: Menjalankan eksekusi pada thread aktif pemanggil.
    *   `Schedulers.parallel()`: Mengalokasikan thread pool berukuran tetap (default: `Runtime.getRuntime().availableProcessors()`) untuk tugas *CPU-bound compute intensive*.
    *   `Schedulers.boundedElastic()`: Pool dinamis berbasis *worker thread backing queue* untuk tugas I/O blocking tak terhindarkan (legacy database, file read/write). Thread akan dimusnahkan saat idle, dibatasi oleh `maxThreads` (default 10x CPU core) dan `maxTaskQueueSize` (default 100,000) untuk mencegah *Out-of-Memory*.

#### D. Manajemen Memori Netty: Jemalloc Architecture & Zero-Copy

Netty memisahkan memori menjadi dua domain: Heap Buffer (dikelola oleh GC) dan Direct Buffer (dialokasikan di luar JVM Garbage Collector via JNI `malloc`).

*   **PooledByteBufAllocator**: Mengadopsi arsitektur *jemalloc*.
    *   **Arena**: Memecah memori ke dalam beberapa `PoolArena` untuk meminimalkan lock contention antar thread.
    *   **Chunk**: Blok memori kontigu berukuran besar (default: 16 MB).
    *   **Subpage**: Pembagian dari Chunk untuk alokasi berukuran kecil (misal: 16 byte - 28 KB).
*   **Reference Counting (`ReferenceCounted`)**:
    *   Setiap `ByteBuf` pooled dimulai dengan `refCnt = 1`.
    *   Ketika diteruskan ke handler berikutnya, kepemilikan buffer harus didefinisikan secara tegas: apakah dipertahankan (`retain()`) atau dilepaskan (`release()`).
    *   Kelalaian memanggil `release()` saat buffer dikonsumsi penuh menyebabkan kebocoran memori native (Off-Heap Leak), yang **tidak dapat** dideteksi atau dibersihkan oleh Java Virtual Machine Garbage Collector.
*   **True Zero-Copy**:
    *   Level OS: `FileRegion` memanfaatkan syscall `sendfile(2)` untuk mentransfer data dari filesystem pagecache langsung ke network card interface (NIC) ring buffer tanpa transisi ke user space.
    *   Level Framework: `CompositeByteBuf` membungkus beberapa pointer buffer fisik menjadi satu struktur logis tanpa proses `System.arraycopy` (memori-ke-memori).

---

### 4. Why & What

| Dimensi Arsitektur | Thread-per-Request Tradisional (Tomcat/Sync) | Virtual Threads (Java 21 Project Loom) | Reactive Event Loop (Netty + Reactor) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | 1 OS Thread = 1 Request/Connection | 1 Virtual Thread = 1 Task (Carrier Thread M:N) | Single-threaded Event Loop per CPU core multiplexing ribuan koneksi |
| **Batas Konkurensi** | Terbatas (biasanya 200 - 1.000 thread per node karena limit memori stack OS). | Sangat tinggi (jutaan concurrent blocking tasks). | Sangat tinggi (jutaan concurrent persistent connections/websockets). |
| **Backpressure** | Implisit via TCP Windowing dan Thread Blocking. | Implisit via carrier thread unmounting saat blocking I/O. | **Eksplisit di level aplikasi**. Kontrol granular `request(n)`, dynamic dropping, buffering, swapping. |
| **Streaming / Duplex** | Sangat tidak efisien (menghabiskan thread pool untuk koneksi idle/streaming). | Cukup baik, namun kontrol window buffer internal terbatas pada TCP stream. | **Optimal**. Aliran data dua arah native, multiplexing channel, frame slicing. |
| **Memory Footprint** | Besar (~1MB memory stack OS per thread). | Rendah (~beberapa KB metadata kontinuation di Heap). | **Paling Rendah & Deterministik** (Pooled Direct Memory, pre-allocated zero-copy buffers). |
| **Debuggability** | Sangat mudah (Stack trace linear, synchronous profiling). | Mudah (Stack trace mirip model sinkron tradisional). | Kompleks (Asynchronous stack traces terpecah melintasi scheduling boundaries). |

#### Mengapa Event Loop & Reactive Tetap Vital di Era Virtual Threads?
Meskipun Java 21 memperkenalkan Virtual Threads yang mengeliminasi kerumitan reaktif untuk aplikasi CRUD standar (blocking I/O database), arsitektur Reactive Event Loop tetap menjadi standar emas tak tergantikan untuk:
1.  **API Gateway & Reverse Proxy**: Membutuhkan throughput ekstrem, header manipulation tanpa parsing body penuh, dan manipulasi socket tingkat rendah.
2.  **Edge Streaming & IoT**: Menangani jutaan koneksi persistent (WebSocket, SSE, MQTT) yang sebagian besar waktu berada dalam kondisi idle, di mana alokasi stack bahkan sebesar beberapa kilobyte per Virtual Thread akan mengakibatkan konsumsi gigabyte memori.
3.  **Explicit Flow Control**: Skenario di mana produsen downstream dapat menghancurkan node upstream jika transmisi data tidak diregulasi secara matematis pada level aplikasi (`onBackpressureBuffer`, `onBackpressureDrop`).

---

### 5. How (Workflow Detail)

Berikut adalah workflow siklus hidup pemrosesan data end-to-end dari level network socket kernel hingga level Project Reactor:

```
[Network Inbound: NIC Socket]
           │
           ▼ (epoll edge-triggered notification)
[Netty Nio/EpollEventLoop: Selector wake-up]
           │
           ▼
[Allocate PooledDirectByteBuf via Jemalloc Arena]
           │
           ▼ (ChannelPipeline Inbound Traversal)
[Inbound Handler 1: ByteToMessageDecoder (Framing)]
           │
           ▼ (fireChannelRead)
[Inbound Handler 2: ReactiveBridgeHandler]
           │
           ├── Context Insertion (TraceId, Reactor Context)
           ├── Operator Fusion Hook
           ▼
[Project Reactor: FluxCreate / FluxPush]
           │
           ▼ (Subscription backpressure check: demand > 0)
[Operators: filter -> flatMap (Async non-blocking I/O) -> publishOn(Schedulers.parallel())]
           │
           ▼ (Downstream emission)
[Subscriber Terminal: Write response back to Netty]
           │
           ▼ (ChannelPipeline Outbound Traversal)
[Outbound Handler: MessageToByteEncoder]
           │
           ▼
[Netty Channel.writeAndFlush()]
           │
           ▼ (Socket write / Zero-copy flush)
[Linux Kernel TCP Send Buffer]
```

#### Langkah-langkah Pemrosesan Detail:
1.  **I/O Multiplexing Loop**: Netty `EpollEventLoop` memanggil `epoll_wait`. Ketika data tiba di NIC, kernel mengisi socket buffer dan event loop terbangun.
2.  **Pooled Memory Allocation**: Netty mengalokasikan slice memori off-heap melalui `PooledByteBufAllocator.DEFAULT.directBuffer(size)` untuk membaca bitstream mentah dari native socket channel.
3.  **Pipeline Inbound Routing**: Frame dibaca oleh handler decoding di `ChannelPipeline`. Setelah membentuk logical frame lengkap, objek diteruskan ke `ReactiveBridgeHandler`.
4.  **Reactive Upstream Bridge**: Event loop menginjeksi frame ke pipeline Project Reactor via `EmitterProcessor` atau sink terarah (`FluxSink`).
5.  **Dynamic Demand Verification**: Frame hanya dialirkan jika downstream subscriber telah mengirimkan sinyal `request(n)` yang mencukupi. Jika downstream mengalami saturasi, `FlowControlHandler` menunda pembacaan dari socket Netty (`channel.config().setAutoRead(false)`), secara efektif menyebarkan backpressure ke TCP receive window pengirim (Zero Window Probe).
6.  **Outbound Channel Flush**: Respon diproses oleh operator Reactor, dikirim kembali ke `ChannelHandlerContext.writeAndFlush(msg)`. Buffer dituliskan langsung ke socket file descriptor menggunakan native system calls (`writev(2)`).
7.  **Deterministic Deallocation**: Segera setelah penulisan soket selesai dan OS memberikan acknowledgment (`ChannelFuture.addListener(...)`), bit counter referensi `ByteBuf` dikurangi via `ReferenceCountUtil.release(msg)`.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi: Event Loop vs Thread-per-Request
Bayangkan sebuah restoran:
*   **Thread-per-Request**: Restoran mempekerjakan 1 pelayan untuk 1 meja. Jika tamu sedang membaca menu selama 30 menit (blocking read I/O), pelayan tersebut berdiri diam mematung di samping meja, tidak dapat melayani meja lain. Kapasitas restoran dibatasi oleh jumlah pelayan fisik yang mampu digaji.
*   **Event Loop**: Restoran hanya mempekerjakan 1 atau 2 pelayan super-gesit dengan *rolling skates* (Event Loop thread). Pelayan mencatat pesanan dari Meja 1, membawanya ke dapur (Socket read register), lalu langsung meluncur ke Meja 2 untuk menuangkan air, tanpa pernah menunggu koki selesai memasak. Saat lonceng dapur berbunyi (*epoll wake-up notification*), pelayan mengambil piring dan mengantarkannya ke Meja 1.

#### B. Diagram Jemalloc ByteBuf Allocation vs Leaks

```
[PooledByteBufAllocator]
       │
       ├── PoolArena (Thread-affinity Arena)
       │        ├── Chunk (16 MB Contiguous Memory)
       │        │     ├── Subpage (8 KB Slices)
       │        │     └── Subpage (8 KB Slices)
       │        └── Chunk (16 MB)
       │
       ▼
[Allocation of ByteBuf Instance]
       │
       ├── refCnt = 1  (Active allocated memory in Off-Heap)
       │
       ├── .retain()   ---> refCnt = 2
       │
       ├── .release()  ---> refCnt = 1
       │
       ├── .release()  ---> refCnt = 0 (Deallocated, returned to Subpage pool)
       │
       └── LUPA .release()?
               │
               ▼
         [LEAK DETECTED!]
         Heap Garbage Collector membersihkan pointer Java 'ByteBuf',
         namun Physical Native Memory di Off-Heap TIDAK PERNAH terbebas.
         => Native Process Memory Ballooning => Linux OOM Killer terminated!
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Dynamic Demand Custom Subscriber

Implementasi subscriber kustom yang memanipulasi *backpressure demand* secara dinamis berdasarkan kalkulasi kapasitas lokal untuk mencegah saturasi thread.

```java
package com.enterprise.reactive.basic;

import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.atomic.AtomicInteger;

public class DynamicBackpressureSubscriber<T> implements Subscriber<T> {

    private static final Logger log = LoggerFactory.getLogger(DynamicBackpressureSubscriber.class);

    private final int highWatermark;
    private final int lowWatermark;
    private final AtomicInteger unconsumedDemand;
    private Subscription subscription;

    public DynamicBackpressureSubscriber(int highWatermark, int lowWatermark) {
        if (lowWatermark >= highWatermark) {
            throw new IllegalArgumentException("Low watermark must be strictly lower than high watermark");
        }
        this.highWatermark = highWatermark;
        this.lowWatermark = lowWatermark;
        this.unconsumedDemand = new AtomicInteger(0);
    }

    @Override
    public void onSubscribe(Subscription s) {
        this.subscription = s;
        log.info("Subscription initialized. Requesting initial high-watermark: {}", highWatermark);
        this.unconsumedDemand.set(highWatermark);
        s.request(highWatermark);
    }

    @Override
    public void onNext(T item) {
        log.info("Processing element: {}", item);
        
        // Simulasikan pengerjaan CPU singkat tanpa blocking I/O
        int remaining = unconsumedDemand.decrementAndGet();
        
        // Dynamic Refill: Ketika kapasitas pemrosesan mencapai batas low-watermark,
        // minta batch baru sejumlah delta untuk menstabilkan buffer stream
        if (remaining <= lowWatermark) {
            int demandToRequest = highWatermark - remaining;
            unconsumedDemand.addAndGet(demandToRequest);
            log.debug("Low-watermark hit ({}). Replenishing demand by {}", remaining, demandToRequest);
            subscription.request(demandToRequest);
        }
    }

    @Override
    public void onError(Throwable t) {
        log.error("Terminal state: Error received", t);
    }

    @Override
    public void onComplete() {
        log.info("Terminal state: Stream processed completely");
    }
}
```

#### B. Practical Example: Production-Grade Non-Blocking API Gateway Component

Contoh berikut mengimplementasikan Edge Pipeline lengkap: Filter Gateway berbasis Netty/Reactor, manajemen off-heap buffer yang aman (*leak-free*), tracing propagation, context injection, dan circuit breaking via timeout & backpressure protection.

```java
package com.enterprise.reactive.gateway;

import io.netty.buffer.ByteBuf;
import io.netty.buffer.PooledByteBufAllocator;
import io.netty.util.ReferenceCountUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.util.context.Context;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.UUID;

public class ProductionGatewayFilter {

    private static final Logger log = LoggerFactory.getLogger(ProductionGatewayFilter.class);
    private static final String TRACE_KEY = "X-Trace-Context";

    /**
     * Memproses payload masuk, melakukan transformasi, validasi, dan rute data
     * secara fully non-blocking tanpa membocorkan Pooled ByteBuf.
     */
    public Flux<ByteBuf> executeProxyPipeline(Flux<ByteBuf> inboundStream, String routeEndpoint) {
        String traceId = UUID.randomUUID().toString();

        return inboundStream
            // Pasang distributed context tracing
            .contextWrite(Context.of(TRACE_KEY, traceId))
            // Cegah downstream producer membanjiri memory: buffer max 256 elemen, drop oldest jika penuh
            .onBackpressureBuffer(
                256,
                droppedBuffer -> {
                    log.warn("Backpressure capacity exceeded. Dropping oldest frame to protect system!");
                    ReferenceCountUtil.safeRelease(droppedBuffer);
                }
            )
            // Transformasi payload secara thread-safe
            .flatMap(buf -> transformPayloadSafely(buf)
                .subscribeOn(Schedulers.parallel()), 16 // Concurrency hint: 16 parallel tasks
            )
            // Timeout fail-safe per chunk jika rute hilir mengalami hanging
            .timeout(Duration.ofMillis(800))
            .onErrorResume(error -> {
                log.error("Upstream routing failure for Trace [{}]: {}", traceId, error.getMessage());
                return fallbackHandler(traceId, error);
            });
    }

    private Mono<ByteBuf> transformPayloadSafely(ByteBuf rawInput) {
        return Mono.deferContextual(ctx -> {
            String traceId = ctx.getOrDefault(TRACE_KEY, "UNKNOWN");
            try {
                // Membaca isi ByteBuf tanpa memindahkan data ke Heap secara agresif
                int readableBytes = rawInput.readableBytes();
                byte[] bytes = new byte[readableBytes];
                rawInput.readBytes(bytes);
                
                String originalBody = new String(bytes, StandardCharsets.UTF_8);
                log.debug("Trace [{}]: Incoming Payload transformed -> {}", traceId, originalBody);

                // Alokasikan buffer keluaran secara off-heap dari Arena
                String responsePayload = "{\"trace\":\"" + traceId + "\", \"payload\":\"" + originalBody + "\"}";
                byte[] responseBytes = responsePayload.getBytes(StandardCharsets.UTF_8);

                ByteBuf allocatedOutbound = PooledByteBufAllocator.DEFAULT.directBuffer(responseBytes.length);
                allocatedOutbound.writeBytes(responseBytes);

                return Mono.just(allocatedOutbound);
            } finally {
                // WAJIB: Release input ByteBuf untuk mencegah native memory leak
                ReferenceCountUtil.safeRelease(rawInput);
            }
        });
    }

    private Flux<ByteBuf> fallbackHandler(String traceId, Throwable cause) {
        return Flux.defer(() -> {
            String errorMsg = "{\"trace\":\"" + traceId + "\", \"error\":\"Service Unavailable\", \"reason\":\"" 
                              + cause.getClass().getSimpleName() + "\"}";
            byte[] bytes = errorMsg.getBytes(StandardCharsets.UTF_8);
            
            ByteBuf errorBuffer = PooledByteBufAllocator.DEFAULT.directBuffer(bytes.length);
            errorBuffer.writeBytes(bytes);
            return Flux.just(errorBuffer);
        });
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*   **Domain**: Real-Time L2/L3 Order Book Financial Market Data Gateway.
*   **Skala Beban**: 500.000 price tick events/detik yang di-broadcast ke lebih dari 50.000 subscriber instrumen derivatif global.
*   **SLA**: P99.99 Latency < 1.2 milidetik; Zero Garbage Collector Pauses (> 2ms).

#### Permasalahan Arsitektur Lama (Legacy System)
Implementasi awal menggunakan framework MVC standar berbasis Thread-per-request via WebSocket.
1.  **Thread Pool Starvation**: Terjadi lonjakan volatilitas pasar (misal: rilis data suku bunga The Fed). Volume pesan melompat 8x lipat. Downstream client yang memiliki jaringan lambat (*slow consumer*) membuat thread write pemancar terhenti (*blocked*). Akibatnya, 2.000 worker threads habis total dalam 3 detik.
2.  **GC Trashing**: Jutaan instansiasi payload JSON per detik menghasilkan *churn* memori yang sangat masif di Heap JVM (mengalokasikan 8 GB/detik). Garbage collector melakukan STW (*Stop-the-World*) pause sebesar 80-150 milidetik, mendistorsi harga pasar dan melanggar SLA.

#### Solusi Transformasi Arsitektur Reaktif
Arsitektur dirombak total menggunakan model **Netty Native Transport (Epoll) + Project Reactor + Pooled Binary Direct Allocator**:

```
[Bursa Efek Feed (UDP Multicast / Aeron)]
                     │
                     ▼
[Direct Off-Heap Kernel Ring Buffer]
                     │
                     ▼
[EpollEventLoopGroup (Pinned Core 0-3)]
                     │
                     ▼ (Zero-Copy Frame Slice)
[Single Publisher Flux<MarketTick>]
                     │
                     ├── .publish().autoConnect(50000) (Multicast Hot Stream)
                     │
     ┌───────────────┴────────────────────────┐
     ▼                                        ▼
[Fast Consumer (Co-located HFT)]   [Slow Consumer (Web Mobile Client)]
  -> direct request(unbounded)       -> .onBackpressureDrop(tick -> metrics.incDrop())
  -> Sub-millisecond direct socket   -> Conflation Buffer (Hold latest tick only)
```

1.  **Zero-Allocation Pipeline**: Data biner didekodekan langsung menggunakan `ByteBuf.slice()`. Payload WebSocket dikirim menggunakan binary framing tanpa translasi ke Java `String` atau objek JSON.
2.  **Conflation / Dynamic Drop Strategy**: Untuk slow consumer, pipeline menerapkan operator conflation kustom:
    ```java
    tickFlux.onBackpressureDrop(slowTick -> {
        slowConsumerDropCounter.increment();
        // Logika Drop: Hanya harga kadaluarsa yang dibuang, snapshot terbaru dipertahankan
    });
    ```
3.  **Kernel Level Socket Tuning**: Penyetelan flag TCP level rendah pada Netty Bootstrap:
    *   `SO_REUSEPORT` diaktifkan: Memungkinkan beberapa process/thread mengikat port yang sama untuk mendistribusikan interupsi CPU secara seimbang.
    *   `TCP_NODELAY` diaktifkan: Mematikan algoritma Nagle untuk memaksa paket langsung dikirimkan tanpa menunggu buffer terisi penuh.

#### Hasil Produksi
*   **P99 Latency**: Berkurang dari 120ms menjadi **0.45ms**.
*   **Alokasi Heap JVM**: Berkurang drastis sebesar **94%** karena 98% operasi I/O berlangsung di Off-Heap direct buffer.
*   **Ketahanan Beban**: Ketika slow consumer mengalami hang, node server sama sekali tidak mengalami lonjakan memori karena mekanisme backpressure langsung membatalkan transmisi paket individual tanpa mengorbankan subscriber lain.

---

### 9. Trade-offs

```
                       LATENCY & THROUGHPUT DETERMINISM
                                     ▲
                                    / \
                                   /   \
                                  /  ★  \  <-- Event Loop + Zero-Copy Netty
                                 /       \
                                /         \
  DEBUGGABILITY & SIMPLE       /___________\  MASSIVE CONCURRENCY
  DEVELOPMENT MODEL                           WITH DYNAMIC BACKPRESSURE
  (Virtual Threads / Loom)                    (Project Reactor / Flow)
```

| Karakteristik Arsitektur | Reactive Event Loop (Netty + Reactor) | Platform Threads (Standard Synchronous) | Virtual Threads (Java 21 Project Loom) |
| :--- | :--- | :--- | :--- |
| **Throughput (Peak Max)** | **Tertinggi**: Tanpa context switch cost, minimal overhead framing. | Rendah: Tercekik batas OS thread limit. | **Tinggi**: Mendekati Event Loop untuk standard network RPC. |
| **Predictable P99.9 Latency** | **Unggul**: Zero-alloc dan thread affinity mencegah interupsi jitter kernel. | Sangat Buruk: Variansi tinggi akibat thread scheduling dan GC pause. | Moderat: Masih mengalokasikan continuation object di heap saat unmount. |
| **Kompleksitas Kode & Debugging** | **Sangat Tinggi**: Stack trace non-lokal, kurva belajar functional reactive curam. | **Sangat Rendah**: Model imperatif sekuensial, standard try-catch debugging. | **Sangat Rendah**: Gaya pemrograman imperatif dengan efisiensi tinggi. |
| **Resiko Memory Leak** | **Tinggi (Off-Heap Leak)**: Butuh kedisiplinan eksplisit reference count buffer. | Hampir Nol: Diatur sepenuhnya oleh Garbage Collector. | Hampir Nol: Diatur sepenuhnya oleh Garbage Collector. |
| **Biaya Infrastruktur (Cost)** | **Paling Murah**: Dapat melayani jutaan koneksi pada CPU dan RAM footprint kecil. | Paling Mahal: Memerlukan scaling horizontal agresif (RAM besar). | Murah: Utilisasi CPU efisien tanpa perlu horizontal scaling ekstrem. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Blocking Call Terjadi di Dalam Event Loop Thread
*   **Gejala**: Latensi memuncak di semua koneksi secara global; sistem tampak *freeze* secara acak; throughput turun drastis ke hitungan puluhan TPS.
*   **Akar Masalah**: Memanggil JDBC driver sinkron, `Thread.sleep()`, pemanggilan RPC blocking, atau operasi parsing kriptografi/CPU intensif di dalam thread `nioEventLoopGroup` atau `Schedulers.parallel()`.
*   **Deteksi**: Integrasikan **BlockHound** saat aplikasi startup.
    ```java
    // Tambahkan di awal metode main/static init
    BlockHound.install();
    ```
    Jika terjadi pemanggilan blocking pada thread non-blocking, exception fatal akan segera dilemparkan sebelum kode menyentuh produksi:
    ```text
    reactor.blockhound.BlockingOperationError: Blocking call! java.io.FileInputStream#readBytes
        at java.base/java.io.FileInputStream.read(FileInputStream.java)
        at com.enterprise.service.AuthService.loadKey(AuthService.java:45)
        at com.enterprise.gateway.ProductionGatewayFilter.lambda$0(ProductionGatewayFilter.java:32)
    ```
*   **Solusi**: Alihkan eksekusi yang tak terhindarkan memiliki sifat blocking ke scheduler terpisah:
    ```java
    Mono.fromCallable(() -> legacyBlockingIoService.execute())
        .subscribeOn(Schedulers.boundedElastic());
    ```

#### 2. Native Off-Heap Memory Leak (Netty ByteBuf Leak)
*   **Gejala**: Memori Heap stabil di profiling, namun `RES/RSS` process di sistem operasi terus membengkak hingga process dimatikan paksa oleh OS via `Out of memory: Kill process (java) score ...`.
*   **Akar Masalah**: Mengonsumsi `ByteBuf` tanpa memanggil `.release()` atau membuat split stream Reactor yang kehilangan terminasi pembersihan.
*   **Solusi**:
    1.  Aktifkan *Paranoid Leak Detection* pada environment staging/testing:
        ```bash
        -Dio.netty.leakDetection.level=PARANOID
        ```
    2.  Analisis log yang dihasilkan Netty:
        ```text
        LEAK: ByteBuf.release() was not called before it's garbage-collected. 
        Recent access records: 
        Created at:
           io.netty.buffer.PooledByteBufAllocator.directBuffer(PooledByteBufAllocator.java:400)
           com.enterprise.gateway.ProductionGatewayFilter.transformPayloadSafely(ProductionGatewayFilter.java:62)
        ```
    3.  Terapkan release idiomatik dengan `ReferenceCountUtil.safeRelease(msg)` di dalam blok `finally`.

#### 3. Kehilangan Operator Subscription Context (ThreadLocal Misuse)
*   **Gejala**: Security Context kosong, user session hilang, atau Distributed Tracing ID (`traceId`) mendadak berganti menjadi `null` di tengah jalan eksekusi rantai operator.
*   **Akar Masalah**: Menggunakan `ThreadLocal` biasa (seperti yang digunakan standar SLF4J MDC atau Spring Security context konvensional) pada arsitektur reaktif di mana eksekusi dapat berpindah thread secara acak antar scheduling boundary.
*   **Solusi**: Gunakan context reaktif native via Reactor `ContextView` atau manfaatkan fitur otomatis **Micrometer Context Propagation** yang diperkenalkan pada Reactor 3.5+:
    ```java
    Hooks.enableAutomaticContextPropagation();
    ```

---

### 11. Best Practices (Production Checklist)

#### OS & Kernel Configuration (`/etc/sysctl.conf`)
* [ ] Tingkatkan ukuran maximum open file descriptors: `fs.file-max = 2097152`.
* [ ] Atur limits session di `/etc/security/limits.conf`: `appuser soft nofile 1048576`, `appuser hard nofile 1048576`.
* [ ] Optimasi memory allocation untuk TCP ring buffer:
  ```ini
  net.ipv4.tcp_rmem = 4096 87380 16777216
  net.ipv4.tcp_wmem = 4096 65536 16777216
  net.core.somaxconn = 32768
  net.ipv4.tcp_max_syn_backlog = 16384
  ```
* [ ] Aktifkan Epoll Low Latency Flag: `net.ipv4.tcp_low_latency = 1`.

#### Netty & JVM Initialization
* [ ] Gunakan native transport Linux secara langsung jika beroperasi pada arsitektur Linux (hindari Java NIO default):
  ```java
  Epoll.isAvailable() ? new EpollEventLoopGroup(threads) : new NioEventLoopGroup(threads);
  ```
* [ ] Set Netty allocator explicit:
  ```bash
  -Dio.netty.allocator.type=pooled
  -Dio.netty.allocator.numDirectArenas=(jumlah_core_cpu)
  ```
* [ ] Nonaktifkan deteksi leak di produksi untuk throughput maksimal setelah fase pengujian selesai:
  ```bash
  -Dio.netty.leakDetection.level=DISABLED
  ```
* [ ] Pasang JVM flag untuk memastikan native memory limit tidak menabrak batas container:
  ```bash
  -XX:MaxDirectMemorySize=4g -XX:+ExitOnOutOfMemoryError
  ```

#### Reactive Code Quality
* [ ] **No Naked Subscriptions**: Hindari memanggil `.subscribe()` di dalam service logic internal; teruskan `Flux`/`Mono` ke web framework engine atau top-level boundary.
* [ ] Jangan gunakan operator `.block()` atau `.toIterable()` di jalur kritis manapun.
* [ ] Pasang operator defensive timeout `.timeout(Duration)` pada seluruh operasi I/O eksternal untuk menjamin pembebasan resource.
* [ ] Pastikan seluruh error terminal terpasang handler fallback `.onErrorResume()` atau logging kontekstual `.doOnError()`.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah **High-Performance Non-Blocking Reverse Proxy Core** yang mampu menangani routing payload biner mentah secara efisien, aman dari memory leak, dan memiliki isolasi thread-pool yang ketat.

Simpan seluruh file ke dalam direktori: `hands-on/m02/`

#### Struktur Proyek
```text
hands-on/m02/
├── pom.xml
└── src/
    └── main/
        └── java/
            └── com/
                └── enterprise/
                    └── proxy/
                        ├── ProxyServerApp.java
                        ├── HttpReverseProxyHandler.java
                        └── pipeline/
                            └── SafeRoutingFilter.java
```

#### Step 1: Konfigurasi Dependencies (`hands-on/m02/pom.xml`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.enterprise.reactive</groupId>
    <artifactId>high-perf-reactive-proxy</artifactId>
    <version>1.0.0</version>

    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <reactor.version>3.6.4</reactor.version>
        <netty.version>4.1.108.Final</netty.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>io.projectreactor</groupId>
            <artifactId>reactor-core</artifactId>
            <version>${reactor.version}</version>
        </dependency>
        <dependency>
            <groupId>io.netty</groupId>
            <artifactId>netty-all</artifactId>
            <version>${netty.version}</version>
        </dependency>
        <dependency>
            <groupId>io.projectreactor.tools</groupId>
            <artifactId>blockhound</artifactId>
            <version>1.0.8.RELEASE</version>
        </dependency>
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>2.0.12</version>
        </dependency>
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-classic</artifactId>
            <version>1.5.3</version>
        </dependency>
    </dependencies>
</project>
```

#### Step 2: Safe Routing Filter (`hands-on/m02/src/main/java/com/enterprise/proxy/pipeline/SafeRoutingFilter.java`)

```java
package com.enterprise.proxy.pipeline;

import io.netty.buffer.ByteBuf;
import io.netty.buffer.PooledByteBufAllocator;
import io.netty.util.ReferenceCountUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

public class SafeRoutingFilter {

    private static final Logger log = LoggerFactory.getLogger(SafeRoutingFilter.class);

    public Mono<ByteBuf> routeAndTransform(ByteBuf payload, String routeId) {
        return Mono.fromSupplier(() -> {
            try {
                int bytesLength = payload.readableBytes();
                byte[] rawContent = new byte[bytesLength];
                payload.readBytes(rawContent);

                String body = new String(rawContent, StandardCharsets.UTF_8);
                log.info("Processing frame for route [{}], size: {} bytes", routeId, bytesLength);

                // Buat paket respon baru (Non-blocking manipulation)
                String enrichedResponse = "HTTP/1.1 200 OK\r\n" +
                                         "Content-Type: application/json\r\n" +
                                         "X-Route-Id: " + routeId + "\r\n" +
                                         "Content-Length: " + (body.length() + 25) + "\r\n\r\n" +
                                         "{\"status\":\"PROCESSED\",\"data\":\"" + body + "\"}";

                byte[] outBytes = enrichedResponse.getBytes(StandardCharsets.UTF_8);
                ByteBuf outBuffer = PooledByteBufAllocator.DEFAULT.directBuffer(outBytes.length);
                outBuffer.writeBytes(outBytes);

                return outBuffer;
            } finally {
                // HINDARI OFF-HEAP LEAK: Rilis buffer payload masuk
                ReferenceCountUtil.safeRelease(payload);
            }
        });
    }
}
```

#### Step 3: Inbound Netty-Reactor Channel Adapter (`hands-on/m02/src/main/java/com/enterprise/proxy/HttpReverseProxyHandler.java`)

```java
package com.enterprise.proxy;

import com.enterprise.proxy.pipeline.SafeRoutingFilter;
import io.netty.buffer.ByteBuf;
import io.netty.channel.ChannelFutureListener;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInboundHandlerAdapter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.scheduler.Schedulers;

import java.util.UUID;

public class HttpReverseProxyHandler extends ChannelInboundHandlerAdapter {

    private static final Logger log = LoggerFactory.getLogger(HttpReverseProxyHandler.class);
    private final SafeRoutingFilter routingFilter = new SafeRoutingFilter();

    @Override
    public void channelRead(ChannelHandlerContext ctx, Object msg) {
        if (msg instanceof ByteBuf byteBuf) {
            String routeId = UUID.randomUUID().toString().substring(0, 8);

            // Sambungkan pemrosesan Netty ke Reactor pipeline
            routingFilter.routeAndTransform(byteBuf, routeId)
                .publishOn(Schedulers.parallel())
                .subscribe(
                    transformedBuffer -> {
                        // Tulis kembali ke client soket secara fully asynchronous
                        ctx.writeAndFlush(transformedBuffer)
                           .addListener(ChannelFutureListener.CLOSE); // Tutup soket HTTP/1.1 connection sederhana
                    },
                    error -> {
                        log.error("Pipeline failure for route {}", routeId, error);
                        ctx.close();
                    }
                );
        } else {
            // Forward objek tak dikenal atau release jika tidak diproses
            ctx.fireChannelRead(msg);
        }
    }

    @Override
    public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) {
        log.error("Uncaught channel pipeline exception", cause);
        ctx.close();
    }
}
```

#### Step 4: Server Main Application Engine (`hands-on/m02/src/main/java/com/enterprise/proxy/ProxyServerApp.java`)

```java
package com.enterprise.proxy;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.ChannelFuture;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelOption;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.epoll.Epoll;
import io.netty.channel.epoll.EpollEventLoopGroup;
import io.netty.channel.epoll.EpollServerSocketChannel;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.blockhound.BlockHound;

public class ProxyServerApp {

    private static final Logger log = LoggerFactory.getLogger(ProxyServerApp.class);
    private static final int PORT = 8080;

    public static void main(String[] args) throws InterruptedException {
        // 1. Pasang proteksi anti-blocking
        BlockHound.install();
        log.info("BlockHound successfully installed to guard EventLoop threads.");

        // 2. Evaluasi Linux Epoll availability
        boolean useEpoll = Epoll.isAvailable();
        log.info("System native transport strategy: {}", useEpoll ? "EPOLL (Linux High-Performance)" : "NIO (Generic)");

        EventLoopGroup bossGroup = useEpoll ? new EpollEventLoopGroup(1) : new NioEventLoopGroup(1);
        EventLoopGroup workerGroup = useEpoll ? new EpollEventLoopGroup() : new NioEventLoopGroup();

        try {
            ServerBootstrap b = new ServerBootstrap();
            b.group(bossGroup, workerGroup)
             .channel(useEpoll ? EpollServerSocketChannel.class : NioServerSocketChannel.class)
             .childOption(ChannelOption.TCP_NODELAY, true)
             .childOption(ChannelOption.SO_KEEPALIVE, true)
             .childOption(ChannelOption.SO_RCVBUF, 32 * 1024)
             .childOption(ChannelOption.SO_SNDBUF, 32 * 1024)
             .childHandler(new ChannelInitializer<SocketChannel>() {
                 @Override
                 protected void initChannel(SocketChannel ch) {
                     ch.pipeline().addLast(new HttpReverseProxyHandler());
                 }
             });

            ChannelFuture f = b.bind(PORT).sync();
            log.info("Enterprise Reactive Proxy started deterministically on port: {}", PORT);
            f.channel().closeFuture().sync();
        } finally {
            bossGroup.shutdownGracefully();
            workerGroup.shutdownGracefully();
        }
    }
}
```

#### Step 5: Eksekusi dan Verifikasi
1.  Buka terminal, masuk ke folder `hands-on/m02/` dan jalankan build:
    ```bash
    mvn clean compile exec:java -Dexec.mainClass="com.enterprise.proxy.ProxyServerApp"
    ```
2.  Buka terminal kedua, tembakkan payload benchmark HTTP:
    ```bash
    curl -X POST http://localhost:8080/api/v1/stream -d '{"event":"ORDER_CREATED","account":"ID-9941"}'
    ```
3.  Periksa bahwa respon diterima seketika dan server log menampilkan bahwa eksekusi berlangsung di dalam pipeline non-blocking tanpa terpicu deteksi kebocoran memori.

---

### 13. Exercise

#### Level: Easy
*   **Pertanyaan**: Diberikan sebuah pipeline `Flux.range(1, 100).publishOn(Schedulers.single()).map(i -> i * 2)`. Pada thread manakah method eksekusi penghasil data `Flux.range` dijalankan, dan pada thread manakah logic lambda `map` dijalankan? Mengapa?
*   **Kriteria Penilaian**: Peserta mampu membedakan dengan tepat efek posisi pemanggilan `publishOn` terhadap thread upstream versus thread downstream.

#### Level: Medium
*   **Kasus**: Sebuah microservice gateway mengimplementasikan `flatMap` untuk memanggil 3 downstream service:
    ```java
    Flux.fromIterable(requestList)
        .flatMap(req -> client.callService(req)) // Total requestList size = 10.000
        .collectList();
    ```
    Sistem seketika mengalami memory saturation dan timeout massal saat traffic spike. 
*   **Tugas**: Modifikasi kode di atas dan sertakan penanganan *concurrency control* dan *backpressure buffering* agar gateway hanya mengeksekusi maksimal 64 request concurrently ke downstream, dengan sisanya diantrekan secara teratur.
*   **Kriteria Penilaian**: Penggunaan parameter overload `concurrency` pada operator `flatMap`, penambahan error isolation, dan penanganan timeout.

#### Level: Hard
*   **Kasus**: Buat implementasi custom Netty `ChannelInboundHandler` yang bertindak sebagai *Adaptive Dynamic Rate Limiter*. 
*   **Persyaratan**: 
    1. Handler memantau bandwidth masuk per client channel.
    2. Jika client mengirim data melebihi 10MB/detik, handler memanggil `ctx.channel().config().setAutoRead(false)` untuk berhenti membaca frame dari TCP Kernel.
    3. Setelah 1 detik berlalu dan window kecepatan reset, aktifkan kembali auto-read via `ctx.channel().config().setAutoRead(true)` serta pastikan tidak ada `ByteBuf` yang teralokasi mengambang tanpa di-release pada saat pemblokiran stream.
*   **Kriteria Penilaian**: Penggunaan Netty Task Scheduling (`ctx.executor().schedule(...)`), kontrol TCP window flow control tanpa alokasi memori heap berlebih, dan manipulasi autoRead yang thread-safe.

---

### 14. Challenge

**Skenario Kasus Kompleks: "The Zero-Allocation High-Frequency Telemetry Ingestion Hub"**

Sebuah perusahaan IoT kendaraan otonom membutuhkan telemetry hub yang menerima transmisi data biner via koneksi TCP murni dengan spesifikasi:

1.  **Arsitektur Target**:
    *   Menerima 200.000 paket/detik ukuran tetap (128 bytes per telemetry frame).
    *   Memproses validasi CRC-32 checksum secara fully off-heap tanpa mengonversi byte ke objek Java model (Zero-Allocation).
    *   Menerapkan *Backpressure Priority Dropping*: Data telemetry terbagi menjadi dua jenis berdasarkan byte header pertama: `CRITICAL (0x01)` dan `DIAGNOSTIC (0x02)`.
    *   Ketika subscriber analitik hilir mengalami kelambatan konsumsi data, pipeline **hanya boleh mendrop** frame bertipe `DIAGNOSTIC`. Frame bertipe `CRITICAL` tidak boleh dibuang dalam kondisi apapun dan wajib dibuffer hingga batas kapasitas maksimal 50.000 record sebelum memicu error terminal.
2.  **Tantangan Implementasi**:
    *   Tulis arsitektur pipeline lengkap menggunakan `EpollServerSocketChannel`, kustom Reactor Subscriber / Processor, dan `PooledByteBufAllocator`.
    *   Wajib lolos integrasi **BlockHound** (tanpa satupun blocking invocation di thread worker).
    *   Wajib lolos pengujian profiling memori: Menjalankan eksekusi 10 juta event dengan heap usage delta tidak boleh bertambah lebih dari 15 MB setelah proses selesai (membuktikan integrasi off-heap zero allocation berjalan sempurna).

*Instruksi Pengerjaan: Selesaikan arsitektur sistem ini tanpa menggunakan library external tambahan di luar Project Reactor Core dan Netty Core.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Soal)
1. **Kapan tepatnya eksekusi I/O atau komputasi pada rantai Project Reactor mulai dijalankan?**
   * A. Saat method factory seperti `Flux.create(...)` atau `Mono.just(...)` dideklarasikan.
   * B. Saat method operator transformasi data seperti `.map(...)` atau `.filter(...)` dipasang.
   * C. Saat method `.subscribe(...)` dipanggil pada pipeline tersebut (Subscription Time/Execution Time).
   * D. Saat garbage collector memindai rantai eksekusi objek.
   * *Kunci: C. Tanpa ada pemanggilan `.subscribe(...)`, pipeline reaktif hanyalah objek blueprint deklaratif di Assembly time.*

2. **Apa yang terjadi jika Anda lupa memanggil `ReferenceCountUtil.release(byteBuf)` pada pooled ByteBuf yang telah selesai dikonsumsi di Netty handler?**
   * A. Garbage Collector Java akan membebaskannya secara otomatis tanpa penundaan.
   * B. Terjadi Off-Heap Native Memory Leak yang lambat laun dapat menyebabkan proses dimatikan oleh sistem operasi (OOM Killer).
   * C. Netty melempar checked exception seketika saat method berakhir.
   * D. Koneksi TCP secara otomatis me-reset koneksi (mengirim paket RST).
   * *Kunci: B. Buffer yang dialokasikan di direct memory native tidak berada di bawah kendali Garbage Collection heap JVM standar.*

3. **Manakah perbedaan mendasar antara `publishOn` dan `subscribeOn` di Project Reactor?**
   * A. `publishOn` mempengaruhi thread eksekusi downstream (setelah operator dipanggil), sedangkan `subscribeOn` mempengaruhi thread emisi upstream terlepas dari posisi deklarasinya.
   * B. `publishOn` hanya bekerja untuk operasi sinkron, sedangkan `subscribeOn` khusus untuk socket I/O.
   * C. `publishOn` mengatur koneksi socket, `subscribeOn` mengatur query database.
   * D. Tidak ada perbedaan, keduanya adalah alias yang interchangeable.
   * *Kunci: A. `subscribeOn` merubah execution context pada fase langganan dari bawah ke atas, sementara `publishOn` memindahkan sinyal eksekusi downstream ke scheduler yang ditentukan.*

4. **Berapa ukuran default thread pool yang dialokasikan oleh `Schedulers.parallel()`?**
   * A. Selalu 200 thread mirip Tomcat servlet container.
   * B. Jumlahnya dinamis tanpa batas (*unbounded*).
   * C. Tepat sebanyak jumlah logical core processor yang terdeteksi oleh JVM (`Runtime.getRuntime().availableProcessors()`).
   * D. 1 thread saja untuk menjaga konsistensi state.
   * *Kunci: C. Schedulers.parallel didesain khusus untuk pekerjaan komputasi murni (CPU-bound) sehingga ukurannya diikat ke jumlah logical core.*

5. **Apa fungsi utama dari tool BlockHound pada pengembangan aplikasi reaktif berbasis Java?**
   * A. Mengonversi blocking driver JDBC menjadi non-blocking driver secara otomatis.
   * B. Memverifikasi bytecode di JVM secara runtime untuk mendeteksi pemanggilan method blocking di dalam thread yang seharusnya non-blocking (seperti Event Loop).
   * C. Mempercepat serialisasi JSON pada controller layer.
   * D. Mengatur load balancing koneksi masuk pada socket Netty.
   * *Kunci: B. BlockHound menginstrumentasi bytecode Java untuk melempar exception jika thread EventLoop mengeksekusi operasi blocking.*

#### B. Intermediate (5 Soal)
6. **Dalam mekanisme Project Reactor, apa yang dimaksud dengan optimasi "Micro-fusion"?**
   * A. Menggabungkan dua file JAR microservice menjadi satu deployment unit.
   * B. Penggunaan interface antrean internal bersama (`QueueSubscription`) antar dua operator berurutan untuk menghindari alokasi array antrean perantara tambahan dan context switch.
   * C. Kompilasi runtime kode Java ke native assembly via GraalVM.
   * D. Menjalankan dua JVM process di dalam satu thread OS yang sama.
   * *Kunci: B. Micro-fusion mengizinkan downstream operator menggunakan struktur internal antrean upstream secara langsung jika memenuhi kontrak antrean kompatibel.*

7. **Mengapa penggunaan `ThreadLocal` konvensional bermasalah saat digunakan di dalam pipeline Project Reactor?**
   * A. Karena `ThreadLocal` memicu thread deadlock di level kernel Linux.
   * B. Karena eksekusi pipeline reaktif dapat berpindah antar thread worker yang berbeda di scheduling boundary, sehingga context yang terikat pada thread lama tidak terbaca di thread baru.
   * C. Karena JVM mematikan fitur `ThreadLocal` pada versi Java 17 ke atas.
   * D. Karena `ThreadLocal` hanya dapat menyimpan tipe data primitif.
   * *Kunci: B. Eksekusi asynchronous reactive berpindah-pindah thread; konteks harus diikat pada level stream metadata (`ContextView`), bukan thread memory.*

8. **Apa perbedaan struktural mendasar antara arsitektur allocator Netty `UnpooledByteBufAllocator` versus `PooledByteBufAllocator`?**
   * A. `Unpooled` mengalokasikan dan mendealokasikan physical memory baru via system call setiap kali diminta, sedangkan `Pooled` mengelola memory slab besar (Arena/Chunk) dan meminjamkan slice tanpa pemanggilan kernel berulang.
   * B. `Unpooled` hanya berjalan di heap, sedangkan `Pooled` hanya berjalan di stack memory.
   * C. `Pooled` berjalan lebih lambat namun lebih hemat kode.
   * D. `Unpooled` ditujukan khusus untuk protokol UDP, `Pooled` khusus TCP.
   * *Kunci: A. Pooled memory mengadopsi prinsip jemalloc untuk menghindari biaya mahal syscall kernel `malloc`/`free` serta mengurangi fragmentasi memori.*

9. **Apa konsekuensi sistemik dari penerapan operator `.onBackpressureDrop()` tanpa konfigurasi drop metrics penampung yang tepat?**
   * A. Event loop thread langsung di-terminate oleh framework.
   * B. Data payload client di-drop secara diam-diam (*silent data loss*) tanpa memberikan notifikasi upstream maupun visibilitas monitoring pada engineer bahwa sistem berada di ambang saturasi.
   * C. Memory server langsung mengalami crash seketika.
   * D. Koneksi internet server langsung terputus secara fisik.
   * *Kunci: B. Operator drop secara sepihak membuang elemen data berlebih; jika tidak dipasangkan dengan metrik observabilitas atau downstream acknowledgement, data hilang tanpa jejak audit.*

10. **Kapan seorang Software Architect harus memilih arsitektur Netty Event Loop dibandingkan model Java 21 Virtual Threads?**
    * A. Untuk aplikasi CRUD enterprise standar yang didominasi oleh akses database relasional via JPA/Hibernate.
    * B. Untuk aplikasi batch processing data statis yang berjalan offline.
    * C. Untuk komponen edge gateway, reverse proxy, socket multiplexer, atau aplikasi bursa/streaming yang membutuhkan kontrol direct off-heap zero-copy, pooling memory, dan granular backpressure regulation.
    * D. Event Loop Netty sudah usang dan harus selalu digantikan oleh Virtual Threads untuk seluruh use-case.
    * *Kunci: C. Virtual threads sangat bagus untuk I/O imperative CRUD, tetapi tidak menyediakan kapabilitas zero-copy buffers, off-heap memory management, dan flow control TCP fine-grained yang menjadi kekuatan Netty.*

#### C. Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Tim engineering Anda meluncurkan API Gateway reaktif berbasis Netty dan Spring WebFlux. Di staging environment, throughput mencapai 80.000 TPS tanpa masalah. Namun, begitu masuk ke Production, utilisasi CPU tiba-tiba menyentuh 100% pada traffic yang hanya 5.000 TPS, dan seluruh connection socket mulai mengalami timeout. Saat thread dump dianalisis via `jstack`, ditemukan pola berikut berulang pada puluhan thread:
    ```text
    "epollEventLoopGroup-3-2" #42 prio=5 os_prio=0 cpu=19420.21ms
       java.lang.Thread.State: RUNNABLE
       at com.enterprise.security.JwtValidator.verifySignature(JwtValidator.java:88)
       at com.enterprise.gateway.AuthFilter.filter(AuthFilter.java:34)
    ```
    *   **Pertanyaan**: Apa diagnosis root cause masalah ini dan apa perbaikan arsitektural yang paling presisi untuk memulihkan throughput sistem tanpa merusak integritas keamanan?
    *   *Analisis Solusi*: 
        *Diagnosis*: Operasi verifikasi tanda tangan kriptografi JWT (yang bersifat compute/CPU-intensive blocking) dieksekusi langsung di dalam `epollEventLoopGroup` thread. Karena Event Loop thread jumlahnya terbatas (sesuai core CPU) dan bertugas melayani ribuan multiplexed socket, eksekusi komputasi berat ini menahan (starve) event loop dari membaca dan memproses paket jaringan client lain.
        *Solusi Arsitektur*: Ekstrak tahapan validasi signature kriptografi tersebut ke thread pool komputasi khusus via operator reaktif:
        ```java
        Mono.fromCallable(() -> jwtValidator.verifySignature(token))
            .subscribeOn(Schedulers.parallel());
        ```
        Hal ini membebaskan Epoll Event Loop thread agar dapat segera kembali memproses socket I/O multiplexing di level kernel.

12. **Skenario Kasus 2**:
    Aplikasi trading biner Anda mendadak crash di produksi dengan pesan dari Linux Kernel: `Out of Memory: Kill process 12401 (java) score 950`. Anda memeriksa heap monitoring via Prometheus, dan melihat heap memory usage hanya berkisar di angka 30% dari total `-Xmx` yang dialokasikan (4 GB dari total 12 GB yang diizinkan). JVM sama sekali tidak melempar `java.lang.OutOfMemoryError: Java heap space`.
    *   **Pertanyaan**: Apa jenis memory issue yang terjadi, di mana area alokasi memory tersebut berada, dan bagaimana langkah mitigasi serta perbaikan source code yang harus diambil?
    *   *Analisis Solusi*:
        *Diagnosis*: Terjadi **Native Off-Heap Memory Leak**. Penggunaan Netty `ByteBuf` yang dialokasikan via `PooledByteBufAllocator` (Direct Buffer) tidak di-release kembali ke pool via `.release()`, sehingga memori fisik native server terus bertambah melampaui limit RAM container/OS hingga memicu Linux kernel OOM Killer.
        *Langkah Mitigasi & Investigasi*:
        1. Aktifkan leak detector level pada staging: `-Dio.netty.leakDetection.level=ADVANCED` atau `PARANOID`.
        2. Periksa setiap custom `ChannelInboundHandler` atau filter Reactor: pastikan setiap `ByteBuf` masuk selalu dipagari dalam konstruksi blok `try ... finally { ReferenceCountUtil.safeRelease(buffer); }`.
        3. Pasang batasan direktori memori JVM yang eksplisit: `-XX:MaxDirectMemorySize=X` agar JVM melempar error sebelum dimatikan paksa oleh kernel OS, sehingga heap dump native/diagnostik dapat diekstrak.

13. **Skenario Kasus 3**:
    Sebuah downstream service analytical database pihak ketiga yang lambat dihubungi oleh pipeline reaktif Anda. Pipeline tersebut menggunakan buffer konvensional:
    ```java
    upstreamFlux
        .publishOn(Schedulers.boundedElastic())
        .map(this::callSlowExternalService)
        .subscribe();
    ```
    Saat upstream traffic melonjak tajam, memori server langsung kolaps dalam 15 menit. Anda diminta merancang arsitektur perlindungan downstream dengan pola *Fail-Safe Graceful Degradation*.
    *   **Pertanyaan**: Bagaimana modifikasi rantai reaktif untuk melindungi server dari saturasi antrean tak terbatas tanpa membuang transaksi finansial yang penting?
    *   *Analisis Solusi*:
        Penggunaan `publishOn` standar mengalokasikan buffer default internal (biasanya 256 elemen) yang jika tersumbat pada downstream yang sangat lambat akan menimbun beban atau memicu thread starvation. Arsitektur harus diubah dengan menambahkan isolasi konkurensi, eksplisit bounded buffer, strategi degradasi, serta timeout perlindungan:
        ```java
        upstreamFlux
            .onBackpressureBuffer(
                5000, // Batasi buffer antrean maksimal
                droppedItem -> deadLetterQueueService.persist(droppedItem), // Alihkan ke persistence storage saat limit lewat
                BufferOverflowStrategy.DROP_OLDEST // Lindungi stabilitas memori aplikasi
            )
            .flatMap(item -> 
                Mono.fromCallable(() -> slowExternalService.call(item))
                    .subscribeOn(Schedulers.boundedElastic())
                    .timeout(Duration.ofMillis(1200)) // Putus downstream call jika latency outlier
                    .onErrorResume(e -> fallbackLocalCacheService.record(item, e)),
                32 // Batasi concurrency factor maksimal 32 parallel in-flight call ke downstream
            )
            .subscribe();
        ```

---

### 16. Summary

1.  **Arsitektur Simbiotik Netty & Reactor**: Netty menyediakan engine non-blocking I/O multiplexing berbasis kernel event notification (`epoll`/`kqueue`) dengan pengelolaan memori pooled off-heap (jemalloc), sementara Project Reactor menyediakan functional programming abstraction layer yang mengimplementasikan spesifikasi Reactive Streams secara matematis.
2.  **Siklus Rantai Reaktif**: Sangat penting memisahkan antara **Assembly Time** (konstruksi pohon operator), **Subscription Time** (propagasi upstream sinyal subscriber), dan **Execution Time** (aliran data downstream dan sinyal backpressure upstream).
3.  **Hukum Kekekalan Event Loop**: **Jangan pernah memblokir Event Loop**. Segala bentuk operasi sleep, pemanggilan database JDBC sinkron, enkripsi intensif, atau disk file writing blocking harus didelegasikan keluar dari Event Loop via `publishOn` ke scheduler yang sesuai (`boundedElastic` untuk blocking I/O, `parallel` untuk CPU bound).
4.  **Disiplin Off-Heap**: Pooled Direct ByteBuf menawarkan throughput tanpa interupsi Garbage Collector, namun menuntut disiplin mutlak reference counting (`retain()` / `release()`). Kegagalan pelepasan buffer berujung pada crash fatal native memory leak oleh OS OOM Killer.
5.  **Relevansi Arsitektural**: Walaupun era modern menghadirkan Java Virtual Threads (Loom), arsitektur Reactive Event Loop tetap menjadi pilihan superior yang tak tergantikan untuk sistem edge network, proxy gateway, dynamic flow-control streaming, dan sistem berlatensi deterministik sub-milidetik.