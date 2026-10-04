# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**BAB 04: I/O, NETWORKING & LOW-LATENCY DATA PROCESSING**
**Kategori: 02-Programming-Languages (Java Enterprise Platform)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menguasai interaksi internal antara Java Virtual Machine (JVM), System Calls Linux (`epoll`, `splice`, `sendfile`), dan subsistem I/O kernel.
- Merancang dan mengimplementasikan sistem komunikasi jaringan asinkronus berbasis Netty dan Java NIO native dengan alokasi memori *zero-copy* dan *off-heap* (`DirectByteBuffer`, Netty `ByteBuf`).
- Mengeliminasi *Garbage Collection pause* pada jalur kritis transmisi data dengan menerapkan teknik *object pooling*, *custom binary protocol framing*, dan *mechanical sympathy*.
- Melakukan diagnosa mendalam terhadap masalah performa level rendah seperti *Direct Memory Leak*, *TCP buffer starvation*, *epoll CPU spinning*, dan fragmentasi *native arena*.
- Mengoperasikan arsitektur *high-throughput*, *sub-millisecond latency ingestion gateway* yang siap di-*deploy* di lingkungan multi-core bare-metal maupun cloud enterprise.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman solid pada:
- **Core Java**: Concurrency dasar (`ExecutorService`, `CompletableFuture`, Memory Model `volatile`/`synchronized`).
- **NIO Basics**: Siklus hidup `ByteBuffer`, `Channel`, dan `Selector` dasar.
- **Operating Systems Concepts**: Arsitektur Linux Kernel (User Space vs Kernel Space, Page Cache, Socket Buffer `SO_RCVBUF`/`SO_SNDBUF`).
- **Networking Foundations**: TCP/IP 3-Way Handshake, TCP Windowing, Nagle's Algorithm (`TCP_NODELAY`), Edge-triggered vs Level-triggered I/O multiplexing.

---

## 3. Concept & Internal Architecture

Pemrosesan data berkecepatan tinggi (*low-latency*) pada enterprise Java memerlukan pemahaman mendalam tentang bagaimana abstraksi JVM dipetakan ke *hardware* dan *kernel space*.

### 3.1. Kernel Space, User Space, dan Mekanisme Zero-Copy
Pada I/O klasik (`java.io.*`), membaca file dan mengirimkannya ke socket membutuhkan 4 *context switch* dan 4 kali *copy data*:
1. Data dibaca dari storage controller via DMA (Direct Memory Access) ke **Page Cache (Kernel Space)**.
2. CPU menyalin data dari Page Cache ke **JVM Process Buffer (User Space)**.
3. Aplikasi menulis data ke target socket; CPU menyalin data dari User Space ke **Socket Buffer (Kernel Space)**.
4. DMA menyalin data dari Socket Buffer ke **NIC Engine (Network Interface Card)**.

```
TRADITIONAL I/O (4 Context Switches, 4 Data Copies):
[Disk] --DMA Copy--> [Kernel: Page Cache] --CPU Copy--> [User: JVM Buffer]
                                                             |
                                                          CPU Copy
                                                             v
[NIC]  <--DMA Copy-- [Kernel: Socket Buffer] <---------------'

ZERO-COPY via FileChannel.transferTo() / sendfile (2 Context Switches, 0 CPU Copies):
[Disk] --DMA Copy--> [Kernel: Page Cache] ----------------------------------.
                            |                                               |
                     Socket Descriptor (File handle & length, no payload)   | DMA Gather
                            v                                               |
                     [Kernel: Socket Buffer]                                |
                                                                            v
[NIC Engine] <--------------------------------------------------------------'
```

Java NIO `FileChannel.transferTo()` memetakan operasi langsung ke system call `sendfile(2)` atau `splice(2)` di Linux. Data dikirimkan langsung dari Page Cache ke NIC DMA ring buffer melalui teknik *scatter-gather*, melewati JVM User Space sepenuhnya.

### 3.2. I/O Multiplexing: Dari `select`/`poll` ke `epoll`
Java NIO `Selector` mengabstraksi mekanisme multiplexing I/O sistem operasi:
- **`select(2)` / `poll(2)`**: $O(N)$ complexity. Kernel memeriksa seluruh file descriptor yang didaftarkan untuk mengetahui descriptor mana yang *ready*.
- **`epoll(7)` (Linux)**: $O(1)$ complexity event-driven notification.
  - `epoll_create1(2)`: Mengalokasikan struktur kernel berbasis Red-Black Tree untuk tracking FD dan Ready List (doubly linked list).
  - `epoll_ctl(2)`: Menambahkan/mengubah FD pada Red-Black Tree beserta *event mask* (`EPOLLIN`, `EPOLLOUT`, `EPOLLET`).
  - `epoll_wait(2)`: Thread tertidur (*blocks*) sampai hardware interrupt membangunkan kernel dan mengisi Ready List. Tidak ada iterasi terhadap non-active descriptors.

### 3.3. Netty Memory Architecture & Jemalloc Arena
Netty mengabaikan `java.nio.ByteBuffer` standar untuk jalur kritis (*critical path*) demi menghindari biaya alokasi dan garbage collection:
- **`ByteBuf`**: Memisahkan `readerIndex` dan `writerIndex`, mengeliminasi perlunya pemanggilan `.flip()` yang rentan human error.
- **PooledByteBufAllocator**: Diadaptasi dari arsitektur *jemalloc*. Mengalokasikan memori dalam chunks (seringkali 16MB) yang dipotong menjadi pages (biasanya 8KB) dan sub-pages, dikelompokkan ke dalam struktur data *Arenas* (`Tiny`, `Small`, `Normal`, `Huge`).
- **ThreadLocal Cache**: Setiap *EventLoop thread* memiliki cache arena sendiri untuk mengurangi kontensi lock antar thread (`ThreadLocalCache`).
- **Reference Counting**: Menggunakan `ReferenceCounted` (`retain()` dan `release()`). Memori native off-heap dikembalikan ke pool seketika ref count mencapai 0, tanpa menunggu siklus GC.

---

## 4. Why & What

| Dimensi | Pendekatan Klasik (`java.io.*` + Thread-per-Client) | Pendekatan Modern (Java NIO / Netty + Off-Heap) |
| :--- | :--- | :--- |
| **Model Konkurensi** | 1 Thread per Socket Connection. 10.000 klien = 10.000 OS Threads. | Reactor Pattern / Event Loop. Beberapa thread melayani jutaan koneksi. |
| **Beban Memori Thread** | Memory footprint tinggi (~1MB stack trace per thread). | Memory footprint stabil; 1-2 worker thread per physical core. |
| **Garbage Collection** | Tekanan tinggi pada Young Generation (banyak byte array pendek). | Memori data stream dialokasikan di *Off-Heap* (Pooled Direct Buffer), zero GC overhead. |
| **Penanganan Backpressure**| Thread terblokir secara otomatis pada level OS kernel socket buffer. | Perlu implementasi *Reactive Stream Backpressure* eksplisit via watermarks. |
| **Overhead Context Switch**| Masif, CPU menghabiskan waktu pada penjadwalan OS scheduler. | Minimal, worker threads beroperasi dengan afinitas CPU yang konsisten. |

---

## 5. How (Workflow Detail)

Alur penanganan frame data binary masuk pada arsitektur Reactor Netty:

```
[Inbound Network Packet]
       │
       ▼
[OS NIC Driver -> Ring Buffer]
       │
       ▼
[Linux Kernel Socket Recv Buffer]
       │
       ▼
[epoll_wait triggers EventLoop Thread wake up]
       │
       ▼
[NioSocketChannel reads into PooledUnsafeDirectByteBuf]
       │
       ▼
[ChannelPipeline Execution Path]
  ├── ChannelInboundHandler 1: LengthFieldBasedFrameDecoder (Framing)
  ├── ChannelInboundHandler 2: CustomBinaryProtocolDecoder (Zero-copy Slice)
  └── ChannelInboundHandler 3: BusinessLogicHandler (Off-loads to ring buffer/Disruptor)
```

1. **Kernel Event Notification**: Data tiba di NIC, memicu hardware interrupt. Driver NIC menaruh paket ke OS buffer. `epoll_wait` kembali (*returns*), menandai `SelectionKey.OP_READ`.
2. **Buffer Allocation**: `EventLoop` mengambil instance `ByteBuf` langsung dari `PooledByteBufAllocator` menggunakan native memory memory arena.
3. **Pipelining & Framing**: Frame decoder memecah stream bytes menjadi logical frames menggunakan pemisah panjang (*length-field*), menghindari alokasi `byte[]` baru dengan memanfaatkan method `.slice()`.
4. **Reference Management**: Decoder men-decode payload, memanggil `.retain()` jika data diteruskan keluar dari pipeline Netty (misal: ke Worker ThreadPool atau LMAX Disruptor ring buffer), lalu memanggil `.release()` pada buffer induk.

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Cepat Saji (Reactor Pattern vs Thread-per-Client)
- **Thread-per-Client (Tradisional)**: Setiap pelanggan yang datang dikawal oleh satu pelayan khusus dari pintu masuk, duduk, menunggu koki memasak, makan, hingga bayar. Jika ada 1.000 pelanggan, restoran butuh 1.000 pelayan yang sebagian besar hanya berdiri bengong menunggu makanan dimasak.
- **Reactor Pattern (Event-Driven NIO)**: Satu kasir/resepsionis berdiri di depan. Pelanggan datang, memesan, diberi nomor tiket (Event Registration), lalu duduk. Koki memberi sinyal saat pesanan siap (Event Trigger). Satu pelayan membagikan pesanan ke pelanggan yang nomornya dipanggil. Sedikit pelayan dapat melayani ribuan pelanggan secara bergantian tanpa henti.

### Diagram Arsitektur Netty ChannelPipeline & Memory
```
+-----------------------------------------------------------------------------------------+
|                                    EVENT LOOP THREAD                                    |
|                                                                                         |
|  +------------------+      read()      +----------------------------------------------+ |
|  | NioEventLoop     | ---------------> | PooledUnsafeDirectByteBuf (Off-Heap Arena)   | |
|  +------------------+                  +----------------------------------------------+ |
|           |                                                    |                        |
|           | executes                                           | passes reference       |
|           v                                                    v                        |
|  +-----------------------------------------------------------------------------------+  |
|  |                                  CHANNEL PIPELINE                                 |  |
|  |                                                                                   |  |
|  |  +--------------------+     +---------------------+     +----------------------+  |  |
|  |  | FrameDecoder       | --> | BinaryProtoDecoder  | --> | ExecutionHandler     |  |  |
|  |  | (Reassembles TCP)  |     | (ByteBuf -> POJO)   |     | (Dispatches to Ring) |  |  |
|  |  +--------------------+     +---------------------+     +----------------------+  |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
                                                                     |
                                                                     v
                                                     +-------------------------------+
                                                     | Worker Engine / LMAX RingBuf  |
                                                     +-------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Zero-Copy File Transfer via NIO
Contoh minimal mentransfer file berukuran gigabyte langsung ke socket jaringan tanpa menyalin byte ke JVM heap.

```java
package com.enterprise.io.simple;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.channels.FileChannel;
import java.nio.channels.SocketChannel;

public final class ZeroCopyFileSender {

    public static void sendLargeFile(String filePath, String host, int port) throws IOException {
        File file = new File(filePath);
        long fileSize = file.length();

        try (FileInputStream fis = new FileInputStream(file);
             FileChannel sourceChannel = fis.getChannel();
             SocketChannel socketChannel = SocketChannel.open()) {

            socketChannel.connect(new InetSocketAddress(host, port));
            socketChannel.configureBlocking(true);

            long position = 0;
            // Loop mutlak diperlukan karena transferTo tergantung batas maksimum buffer kernel
            while (position < fileSize) {
                long transferred = sourceChannel.transferTo(position, fileSize - position, socketChannel);
                if (transferred <= 0) {
                    break;
                }
                position += transferred;
            }
        }
    }
}
```

### 7.2. Practical Example: Industrial-Grade Low-Latency Binary Gateway Server
Server Netty yang memproses protokol biner khusus: `[Magic: 2B][Length: 4B][Type: 2B][Sequence: 8B][Payload: NB]`. Dilengkapi proteksi backpressure, unpooled allocation prevention, dan proper reference counting.

```java
package com.enterprise.io.practical;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.buffer.ByteBuf;
import io.netty.channel.*;
import io.netty.channel.epoll.Epoll;
import io.netty.channel.epoll.EpollEventLoopGroup;
import io.netty.channel.epoll.EpollServerSocketChannel;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.ByteToMessageDecoder;
import io.netty.handler.codec.LengthFieldBasedFrameDecoder;
import io.netty.util.ReferenceCountUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

public final class EnterpriseBinaryServer {

    private static final Logger log = LoggerFactory.getLogger(EnterpriseBinaryServer.class);
    private final int port;

    public EnterpriseBinaryServer(int port) {
        this.port = port;
    }

    public void start() throws InterruptedException {
        boolean useEpoll = Epoll.isAvailable();
        EventLoopGroup bossGroup = useEpoll ? new EpollEventLoopGroup(1) : new NioEventLoopGroup(1);
        EventLoopGroup workerGroup = useEpoll ? new EpollEventLoopGroup() : new NioEventLoopGroup();

        try {
            ServerBootstrap bootstrap = new ServerBootstrap();
            bootstrap.group(bossGroup, workerGroup)
                     .channel(useEpoll ? EpollServerSocketChannel.class : NioServerSocketChannel.class)
                     .option(ChannelOption.SO_BACKLOG, 8192)
                     .option(ChannelOption.SO_REUSEADDR, true)
                     .childOption(ChannelOption.SO_KEEPALIVE, true)
                     .childOption(ChannelOption.TCP_NODELAY, true)
                     .childOption(ChannelOption.WRITE_BUFFER_WATER_MARK, new WriteBufferWaterMark(32 * 1024, 64 * 1024))
                     .childOption(ChannelOption.ALLOCATOR, io.netty.buffer.PooledByteBufAllocator.DEFAULT)
                     .childHandler(new ChannelInitializer<SocketChannel>() {
                         @Override
                         protected void initChannel(SocketChannel ch) {
                             ChannelPipeline pipeline = ch.pipeline();
                             // Max Frame Length 8MB; Offset to length field is 2; Length field is 4 bytes.
                             pipeline.addLast("frameDecoder", new LengthFieldBasedFrameDecoder(8 * 1024 * 1024, 2, 4, 0, 0));
                             pipeline.addLast("protocolDecoder", new CustomBinaryProtocolDecoder());
                             pipeline.addLast("businessHandler", new IngestionBusinessHandler());
                         }
                     });

            ChannelFuture future = bootstrap.bind(port).sync();
            log.info("Server started successfully on port {} using {}", port, useEpoll ? "epoll (Native Linux)" : "NIO");
            future.channel().closeFuture().sync();
        } finally {
            bossGroup.shutdownGracefully();
            workerGroup.shutdownGracefully();
        }
    }

    // Protocol DTO
    public record BinaryPacket(short magic, int length, short type, long sequence, byte[] payload) {}

    // Protocol Decoder: Mengambil frame biner tanpa mengalokasi memori berlebih
    public static final class CustomBinaryProtocolDecoder extends ByteToMessageDecoder {
        private static final short EXPECTED_MAGIC = 0x5A43; // 'ZC'

        @Override
        protected void decode(ChannelHandlerContext ctx, ByteBuf in, List<Object> out) {
            if (in.readableBytes() < 16) { // Header minimal: 2 + 4 + 2 + 8 = 16 bytes
                return;
            }

            short magic = in.readShort();
            if (magic != EXPECTED_MAGIC) {
                in.skipBytes(in.readableBytes());
                ctx.close();
                return;
            }

            int length = in.readInt();
            short type = in.readShort();
            long sequence = in.readLong();

            int payloadLength = length - 16;
            byte[] payload = new byte[payloadLength];
            in.readBytes(payload);

            out.add(new BinaryPacket(magic, length, type, sequence, payload));
        }
    }

    // Business Handler: Memproses packet dan menjaga lifecycle ByteBuf
    public static final class IngestionBusinessHandler extends SimpleChannelInboundHandler<BinaryPacket> {
        @Override
        protected void channelRead0(ChannelHandlerContext ctx, BinaryPacket packet) {
            // Evaluasi Channel Writable State untuk Backpressure
            if (!ctx.channel().isWritable()) {
                log.warn("Channel write buffer full! Applying upstream backpressure for sequence: {}", packet.sequence());
            }

            // Jalur Cepat Eksekusi Data
            if (packet.type() == 0x01) { // Ping/Heartbeat
                ByteBuf response = ctx.alloc().directBuffer(8);
                response.writeLong(packet.sequence());
                ctx.writeAndFlush(response);
            } else {
                // Proses data payload di worker pipeline eksternal
                processTelemetryPayload(packet);
            }
        }

        private void processTelemetryPayload(BinaryPacket packet) {
            // Simulasi pemrosesan tanpa overhead alokasi objek heap yang masif
            if (packet.sequence() % 100_000 == 0) {
                log.info("Ingested sequence: {} payload size: {} bytes", packet.sequence(), packet.payload().length);
            }
        }

        @Override
        public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) {
            log.error("Channel pipeline exception", cause);
            ctx.close();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        new EnterpriseBinaryServer(9876).start();
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ultra-Low-Latency Order Routing Gateway (FinTech/Bursa Saham)
- **Konteks**: Sebuah bursa berjangka menangani *peak traffic* sebesar 1.500.000 order/detik melalui protokol biner FIX (Financial Information eXchange) yang dikompresi.
- **Masalah Awal**:
  1. Latensi P99.99 berada pada angka 85ms karena Java Garbage Collection *Stop-The-World* (STW) pauses.
  2. Terjadi lonjakan thread context switching (OS load average > 80 pada server 32-core) akibat arsitektur berbasis *thread pool executor* konvensional.
  3. Terjadi *Out Of Memory: Direct buffer memory* secara acak di tengah jam transaksi aktif.
- **Investigasi Mendalam**:
  1. *GC Profiling* via async-profiler mengidentifikasi pembuatan puluhan juta instans `byte[]` dan POJO transaksi per detik di Eden Space.
  2. *Netty Leak Detection* di level `PARANOID` mengonfirmasi bahwa custom handler pipeline tidak me-release `ByteBuf` yang dibuang akibat validasi checksum yang gagal.
  3. Thread starvation terjadi karena logging sinkronus I/O di dalam handler pipeline Netty.
- **Solusi Rekayasa**:
  1. **Transport Layer**: Beralih ke Linux Native Epoll Transport (`EpollEventLoopGroup`) dengan Kernel SO_BUSY_POLL diaktifkan.
  2. **Pipeline Architecture**: 
     - Pipeline Netty hanya bertugas membaca frame biner langsung ke Direct ByteBuf.
     - Frame diteruskan ke **LMAX Disruptor RingBuffer** berbasis shared off-heap array (Zero Allocation).
  3. **Affinity Tuning**: Mengunci Core CPU (*CPU Pinning*) menggunakan native utility `taskset` / JNA Affinity untuk menghindari context switching antar CPU socket.
  4. **Strict Memory Protocol**: Penggunaan `ReferenceCountUtil.touch()` saat debugging dan automasi via custom testing suite untuk memastikan zero memory leak.
- **Hasil**:
  - P99.99 Latensi turun dari **85ms** ke **340 mikrodetik (0.34ms)**.
  - Beban GC berkurang hingga **99.2%** (zero-allocation transient data).
  - Throughput stabil pada 2.200.000 pesan/detik dengan utilisasi CPU terkontrol (rata-rata 35%).

---

## 9. Trade-offs

```
                       PERFORMANCE / LATENCY
                             /\
                            /  \
                           /    \
                          /  *   \  (Off-Heap / Zero-Copy Netty)
                         /        \
   (Thread-per-client)  /          \
                       /____________\
DEVELOPMENT SIMPLICITY                OPERATIONAL COST & MEMORY SAFETY
```

### Analisis Parameter

1. **Direct Memory vs Heap Memory**:
   - *Direct Memory*: Bebas biaya GC, performa transfer I/O maksimal (DMA ready). Namun biaya alokasi/de-alokasi sangat lambat (memerlukan `malloc`/`free` OS call), rentan fatal *OS Crash (SIGSEGV)* jika terjadi *buffer overrun*, dan sulit di-*profile* dibanding Java Heap biasa.
   - *Heap Memory*: Sangat cepat dialokasi (pointer bumping di TLAB), otomatis dikelola GC. Namun memperlambat GC lifecycle dan menyalin data dua kali saat dikirim ke socket.

2. **Epoll Level-Triggered (LT) vs Edge-Triggered (ET)**:
   - *Level-Triggered*: Lebih aman; jika ada data tersisa yang belum dibaca, `epoll_wait` akan terus memberitahu thread.
   - *Edge-Triggered*: Performa lebih tinggi karena mengurangi event wakeups kernel, tetapi jika kode aplikasi gagal membaca habis seluruh byte pada satu siklus I/O (`EAGAIN`/`EWOULDBLOCK`), socket akan *hang* secara permanen (*deadlock state*).

3. **Kompleksitas Arsitektur vs Skalabilitas**:
   - Memilih arsitektur Reactor non-blocking meningkatkan kompleksitas *debugging*, hilangnya konteks *stack trace*, dan risiko terblokirnya pipeline secara fatal jika ada developer yang memanggil operasi *blocking* (misal: JDBC call atau I/O synchronous) di dalam *EventLoop thread*.

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal yang Sering Terjadi di Produksi
1. **Memblokir EventLoop Thread**:
   ```java
   // ANTI-PATTERN FATAL! Menghancurkan throughput seluruh server
   public void channelRead(ChannelHandlerContext ctx, Object msg) {
       String result = databaseClient.blockingQuery(); // EventLoop membeku!
       ctx.writeAndFlush(result);
   }
   ```
   *Solusi*: Lempar eksekusi blocking ke thread pool terpisah (`EventExecutorGroup`) atau gunakan reactive non-blocking client driver.

2. **Memory Leak pada Netty `ByteBuf`**:
   Lupa memanggil `.release()` saat pesan tidak diteruskan ke handler berikutnya.
   ```java
   public void channelRead(ChannelHandlerContext ctx, Object msg) {
       ByteBuf buf = (ByteBuf) msg;
       if (isCorrupted(buf)) {
           // Lupa memanggil buf.release(); -> DIRECT MEMORY LEAK!
           ctx.close();
           return;
       }
       ctx.fireChannelRead(msg); // Ini aman, diteruskan ke handler berikutnya
   }
   ```

3. **Membaca `ByteBuffer` NIO Tanpa Memeriksa Sisa Data (`remaining()`)**:
   Mengasumsikan `channel.read(byteBuffer)` membaca seluruh frame dalam satu tarikan. TCP adalah stream-based protocol, bukan message-based protocol. Frame dapat terpotong secara arbitrer.

### 10.2. Troubleshooting Guide
- **Diagnosa Direct Memory Leak**:
  Jalankan JVM dengan parameter:
  `-Dio.netty.leakDetection.level=PARANOID -XX:NativeMemoryTracking=detail`
  Gunakan tool `jcmd <PID> VM.native_memory baseline` lalu bandingkan beberapa jam kemudian via `jcmd <PID> VM.native_memory detail.diff`. Periksa pertumbuhan arena `DirectBuffer` atau alokasi native libc `malloc`.
- **Epoll 100% CPU Bug**:
  Jika utilisasi core CPU menyentuh 100% tanpa adanya traffic masuk, JVM kemungkinan terkena *NIO epoll loop bug* (di mana selector wake up tanpa ada FD ready). Update versi Netty ke branch LTS terbaru atau JVM runtime terbaru, di mana Netty memiliki mekanisme deteksi *selector rebuild*.

---

## 11. Best Practices (Production Checklist)

### Checklist Konfigurasi Produksi

- [ ] **Transport Layer**: Gunakan Native Transport (`io.netty.channel.epoll.Epoll` untuk Linux, `io.netty.channel.kqueue.KQueue` untuk macOS/BSD) alih-alih standard Java NIO.
- [ ] **TCP Opts**: Set `TCP_NODELAY = true` untuk menonaktifkan Nagle's Algorithm (krusial untuk low latency).
- [ ] **Backpressure Control**: Definisikan `WriteBufferWaterMark` secara eksplisit. Verifikasi method `channel.isWritable()` sebelum melakukan operasi *burst write*.
- [ ] **Resource Safety**: Pastikan setiap custom inbound handler yang meng-absorb (tidak memanggil `fireChannelRead`) mengimplementasikan `SimpleChannelInboundHandler` atau memanggil `ReferenceCountUtil.release(msg)` di dalam blok `finally`.
- [ ] **Memory Allocator**: Gunakan default `PooledByteBufAllocator.DEFAULT` dengan `-Dio.netty.allocator.type=pooled`.
- [ ] **Heap Boundaries**: Alokasikan space Direct Memory yang cukup via `-XX:MaxDirectMemorySize` (contoh: samakan dengan kapasitas memory Heap jika bekerja intensif dengan network I/O).
- [ ] **Thread Sizing**: Konfigurasikan worker group sizing tepat: $N = \text{Runtime.getRuntime().availableProcessors()} \times 2$ (kecuali server terisolasi pada CPU pinning, di mana $N = \text{Core Count}$).

---

## 12. Hands-on Practice

Buatlah direktori praktikum berikut: `hands-on/m02/`

### File: `hands-on/m02/pom.xml`
```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.enterprise.io</groupId>
    <artifactId>low-latency-io</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <netty.version>4.1.107.Final</netty.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>io.netty</groupId>
            <artifactId>netty-all</artifactId>
            <version>${netty.version}</version>
        </dependency>
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-simple</artifactId>
            <version>2.0.9</version>
        </dependency>
    </dependencies>
</project>
```

### File: `hands-on/m02/src/main/java/com/enterprise/io/DirectVsHeapBenchmark.java`
Eksperimen komparasi langsung overhead throughput dan alokasi memori antara Heap ByteBuffer dan Direct ByteBuffer.

```java
package com.enterprise.io;

import java.nio.ByteBuffer;

public class DirectVsHeapBenchmark {
    private static final int ITERATIONS = 10_000_000;
    private static final int BUFFER_SIZE = 1024; // 1 KB

    public static void main(String[] args) {
        System.out.println("Starting Benchmark: Heap vs Direct Allocation & Access...");

        // Warmup
        benchmarkHeap(10_000);
        benchmarkDirect(10_000);

        long startHeap = System.nanoTime();
        benchmarkHeap(ITERATIONS);
        long endHeap = System.nanoTime();

        long startDirect = System.nanoTime();
        benchmarkDirect(ITERATIONS);
        long endDirect = System.nanoTime();

        System.out.printf("Heap Execution Time:   %,d ms%n", (endHeap - startHeap) / 1_000_000);
        System.out.printf("Direct Execution Time: %,d ms%n", (endDirect - startDirect) / 1_000_000);
    }

    private static void benchmarkHeap(int iters) {
        for (int i = 0; i < iters; i++) {
            ByteBuffer buffer = ByteBuffer.allocate(BUFFER_SIZE);
            buffer.putLong(0, 123456789L);
            long val = buffer.getLong(0);
        }
    }

    private static void benchmarkDirect(int iters) {
        for (int i = 0; i < iters; i++) {
            ByteBuffer buffer = ByteBuffer.allocateDirect(BUFFER_SIZE);
            buffer.putLong(0, 123456789L);
            long val = buffer.getLong(0);
        }
    }
}
```

### Instruksi Praktikum:
1. Compile dan jalankan benchmark di atas:
   ```bash
   mvn clean compile
   java -XX:+PrintGC -cp target/classes com.enterprise.io.DirectVsHeapBenchmark
   ```
2. Analisis output log GC. Amati bahwa `ByteBuffer.allocate(1024)` memicu siklus GC berkali-kali karena membanjiri Young Generation, sedangkan `allocateDirect` memicu native system call `malloc` yang secara drastis menggeser overhead dari CPU GC ke Kernel OS context switching jika tidak di-*pool*.

---

## 13. Exercise

### Level Easy
Tuliskan sebuah Java NIO server berbasis `Selector` native yang membaca string dari klien, mencetak teks dalam format uppercase, dan mengirimkannya kembali tanpa menggunakan framework Netty. Tangani `OP_ACCEPT` dan `OP_READ` secara terpisah.

### Level Medium
Buat sebuah Netty Inbound Handler kustom yang memvalidasi header frame. Jika header valid, teruskan payload ke pipeline berikutnya menggunakan `.retain()`. Jika invalid, buang frame dengan aman menggunakan `.release()`, kirim pesan error kembali ke klien dengan `writeAndFlush`, lalu putus koneksi socket.

### Level Hard
Implementasikan sebuah streaming ring buffer custom menggunakan `sun.misc.Unsafe` atau Java 21 Foreign Function & Memory (FFM) API (`Arena.ofShared()`). Program harus mampu menerima raw byte blocks dari socket secara konkuren dan menyimpannya langsung pada continuous off-heap memory dengan cache-line padding (64 bytes) untuk mencegah *false sharing* antar worker threads.

---

## 14. Challenge

### Studi Kasus Kompleks: High-Throughput FIX Protocol Fast-Drop Engine
Anda diminta merancang subsistem gateway ingestion bursa saham dengan spesifikasi berikut:
- **Throughput Target**: Minimal 3.000.000 pesanan per detik per node.
- **Latency SLA**: P99.9 < 500 mikrodetik.
- **Constraint**: 
  - Alokasi memori heap di jalur data kritis harus bernilai **0 bytes per request** (Zero Allocation Policy).
  - Jika klien mengirim data lebih cepat daripada kapasitas engine pencocokan (*backpressure state*), sistem tidak boleh mengalami OutOfMemory (OOM) dan tidak boleh menjatuhkan koneksi secara serampangan, melainkan harus menerapkan degradasi graceful (menghentikan pembacaan socket sementara melalui `ChannelOption.AUTO_READ = false`).
- **Tugas Arsitektur**:
  1. Tentukan layout framing binary protocol untuk membungkus data order.
  2. Susun konfigurasi Netty Pipeline, EventLoop thread allocation, dan *custom pooled bytebuf slice parsing logic*.
  3. Buktikan secara matematis dan arsitektural bahwa tidak ada kebocoran memori direct (`ReferenceCounted`) pada kondisi di mana klien memutuskan koneksi TCP secara sepihak di tengah transmisi paket besar.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara `ByteBuffer.allocate()` dan `ByteBuffer.allocateDirect()` pada Java NIO?
2. Mengapa metode `channel.read(byteBuffer)` dapat mengembalikan nilai lebih kecil dari kapasitas buffer yang kita sediakan?
3. Apa fungsi dari pemanggilan method `buffer.flip()` pada operasi Java NIO standard?
4. Apa yang dimaksud dengan *context switch* dalam kaitannya dengan I/O data read/write?
5. Mengapa Netty memperkenalkan abstraksi `ByteBuf` baru alih-alih memakai `java.nio.ByteBuffer` standar bawaan JDK?

### 5 Pertanyaan Intermediate
1. Bagaimana Linux `epoll` menyelesaikan bottleneck performa $O(N)$ yang dialami oleh system call pendahulunya seperti `select` dan `poll`?
2. Jelaskan bahaya memanggil blocking call (seperti `Thread.sleep()` atau JDBC query) di dalam method `channelRead` pada Netty `ChannelInboundHandler`!
3. Apa perbedaan antara *Level-Triggered* dan *Edge-Triggered* pada I/O multiplexing, dan apa dampaknya jika aplikasi tidak membaca seluruh buffer socket pada model Edge-Triggered?
4. Bagaimana arsitektur jemalloc pada Netty `PooledByteBufAllocator` mengurangi lock contention antar thread?
5. Apa konsekuensinya jika aplikasi Java secara terus menerus memanggil `ByteBuf.retain()` tanpa memanggil pasangan `ByteBuf.release()`-nya? Parameter JVM apa yang mendeteksi insiden ini?

### 3 Skenario Kasus Produksi
1. **Skenario 1**: Sebuah microservice gateway Netty mengalami lonjakan memori Resident Set Size (RSS) pada level OS hingga di-kill oleh Linux *OOM Killer*, padahal metrics Java Heap (Xmx) baru terpakai 20%. Tidak ada log Exception pada JVM. Apa penyebab potensialnya dan langkah profiling apa yang harus dijalankan?
2. **Skenario 2**: Aplikasi Java NIO network ingestion Anda mendadak mengalami 100% CPU utilization pada thread selector tanpa ada klien yang terhubung atau traffic data yang lewat. Fenomena OS apa ini dan bagaimana mitigasi arsitekturalnya?
3. **Skenario 3**: Sebuah upstream client mengirimkan payload ukuran besar (100MB) secara simultan melalui 500 koneksi bersamaan ke server Netty Anda. Server tiba-tiba melempar `OutOfMemoryError: Direct buffer memory`. Mengingat Anda menggunakan Netty dengan pooling, langkah konseptual dan setting watermark apa yang harus Anda sesuaikan untuk menangani skenario burst ini tanpa crashing?

---

## 16. Summary

- **Mekanisme Zero-Copy**: Memotong latensi dan CPU overhead secara drastis dengan mengeliminasi penyalinan data antara Kernel Space dan User Space (JVM Heap) melalui system call seperti `sendfile(2)` dan native DMA channel mapping.
- **I/O Multiplexing Modern**: Penggunaan `epoll` pada platform Linux memungkinkan JVM memantau ratusan ribu koneksi socket secara efisien dengan performa $O(1)$, tanpa polling array file descriptor yang memboroskan siklus komputasi CPU.
- **Netty Low-Latency Engine**: Menggabungkan EventLoop non-blocking, *jemalloc-inspired pooled direct buffers*, dan per-thread arena cache untuk mencapai transmisi jutaan paket per detik dengan *zero-allocation footprint* pada Java Heap.
- **Kesiapan Operasional**: Merancang sistem low-latency menuntut penguasaan *off-heap lifecycle management*, kewaspadaan absolut terhadap operasi blocking pada EventLoop, serta penerapan backpressure adaptif demi ketahanan sistem tingkat enterprise.