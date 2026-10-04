# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Pemrograman Backend & Rekayasa Sistem Skala Tinggi
*   **Kategori:** 02-Programming-Languages
*   **Topik Utama:** Java
*   **Bab:** 04 — Sistem I/O Tingkat Lanjut, Jaringan, dan Konkurensi Sistem
*   **Modul:** 01 — I/O, Networking & Low-Latency Data Processing
*   **Prasyarat:** Konsep Memori JVM (Heap/Stack), Dasar Threading & Concurrency Primitives (`java.util.concurrent`), Socket Dasar (`java.net`), Pemahaman Pointer/Alamat Memori OS tingkat dasar.
*   **Target Audiens:** Senior Software Engineer, Systems Engineer, Backend Infrastructure Specialist, Performance Tuning Architect.
*   **Waktu Penyelesaian:** 12 - 16 Jam (Membaca, Menguji Coba, dan Mengimplementasikan Mini-Project).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1.  **Mendekomposisi (Analyze)** arsitektur I/O Java dari Blocking I/O (BIO) stream-based hingga Non-Blocking I/O (NIO) multiplexing dan Asynchronous I/O (AIO), serta interaksinya dengan Kernel OS (`epoll`, `kqueue`, `io_uring`).
2.  **Mengimplementasikan (Apply)** manipulasi memori off-heap menggunakan `ByteBuffer.allocateDirect()` dan Memory-Mapped Files (`MappedByteBuffer`) untuk menghilangkan *Garbage Collection (GC) overhead* pada jalur data kritis (*hot-path*).
3.  **Mengkonstruksi (Create)** sistem transmisi data *Zero-Copy* berkecepatan tinggi menggunakan `FileChannel.transferTo()` / `transferFrom()` yang mengeliminasi perpindahan konteks (*context switching*) antara *User Space* dan *Kernel Space*.
4.  **Mendiagnosis dan Mengeliminasi (Evaluate)** latensi ekstrim (*tail latency/jitter*) yang disebabkan oleh *false sharing*, alokasi memori heap berlebihan, dan kegagalan multiplexer I/O (`epoll CPU 100% bug`).
5.  **Merancang (Create)** sebuah *network ingestion engine* berbasis Java NIO non-blocking murni yang mampu memproses ratusan ribu operasi per detik dengan determinisme latensi pada tingkat sub-milidetik.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Stream Abstraction" ke "Mechanical Sympathy"

Dalam rekayasa perangkat lunak konvensional, I/O sering kali diabstraksikan sebagai "aliran data" (`InputStream` / `OutputStream`) yang dibaca byte demi byte atau array demi array. Pendekatan ini nyaman secara konseptual, namun menyembunyikan realitas perangkat keras di bawahnya:

```
[ Mental Model Tradisional: Stream Abstraction ]
Aplikasi (Thread) <---- InputStream.read() ---- [ OS Kernel ] <---- Device (Disk/NIC)
* Paradigma: 1 Thread per 1 Koneksi. Thread diblokir sampai data tersedia. 
* Konsekuensi: Alokasi ribuan thread, overhead context switching masif, alokasi memori heap tinggi.
```

Untuk sistem *low-latency* dan *high-throughput*, Anda harus mengadopsi mental model **Mechanical Sympathy**—memahami bagaimana CPU, RAM, Network Interface Card (NIC), dan Kernel saling berkomunikasi:

```
[ Mental Model Low-Latency: Zero-Copy & Event Multiplexing ]
NIC Buffer (Ring Buffer) 
       │ (DMA Engine - Direct Memory Access)
       ▼
Kernel Page Cache / Socket Buffer
       │ (Zero-Copy Transfer / Direct Memory Mapping)
       ▼
Off-Heap Buffer (DirectByteBuffer / Mmap) <──> User Space (No GC, No User-Kernel Copies)
       ▲
Multiplexer (epoll/kqueue) memicu Event Ready ke Event Loop Thread
```

### Prinsip Inti Low-Latency I/O:
1. **Hindari Salinan Data (Zero-Copy):** Salinan data memori dari kernel space ke user space membuang siklus bus memori CPU.
2. **Hindari Konkurensi Berlebih (Thread Contention & Context Switches):** 1.000 thread aktif yang saling berebut CPU core menciptakan degradasi performa drastis akibat *cache invalidation* (L1/L2/L3 cache misses). Model *single-writer* atau *event-loop multiplexing* jauh lebih deterministik.
3. **Bebaskan GC dari Hot-Path (Zero Allocation):** Garbage Collector adalah musuh utama latensi deterministik. Jangan mengalokasikan objek baru di heap dalam loop pemrosesan data jaringan atau disk.
4. **Hormati Cache Lines:** Mengakses data secara sekuensial pada blok 64-byte (*Cache Line*) dan mencegah *False Sharing* antar-core CPU.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Perbandingan Alur Data: Standard I/O vs. Zero-Copy I/O

Diagram berikut mengilustrasikan perbedaan fundamental perpindahan data dari Disk/Jaringan ke Socket Jaringan antara Standard I/O (`FileInputStream` + `SocketOutputStream`) dan Zero-Copy I/O (`FileChannel.transferTo`).

#### Alur Standard I/O (4 Context Switches, 4 Data Copies):
```
+-----------------------------------------------------------------------------+
|                                 USER SPACE                                  |
|                                                                             |
|      +---------------------------------------------------------------+      |
|      |               Java Application Heap (byte[] buffer)           |      |
|      +---------------------------------------------------------------+      |
|                     ▲ (Copy 2: CPU)                 │ (Copy 3: CPU)         |
+---------------------┼───────────────────────────────┼-----------------------+
|                     ▼                               ▼                       |
|   +-----------------------------------+   +-----------------------------+   |
|   |    OS Kernel Page Cache (Disk)    |   |      OS Socket Buffer       |   |
|   +-----------------------------------+   +-----------------------------+   |
|                     ▲                               │                       |
|                     │ (Copy 1: DMA)                 │ (Copy 4: DMA)         |
|                     │                               ▼                       |
|              +--------------+               +---------------+               |
|              |     DISK     |               |   NIC BUFFER  |               |
|              +--------------+               +---------------+               |
|                                KERNEL SPACE                                 |
+-----------------------------------------------------------------------------+
```

#### Alur Zero-Copy I/O via Kernel `sendfile` (2 Context Switches, 2 Data Copies, 0 CPU Copies):
```
+-----------------------------------------------------------------------------+
|                                 USER SPACE                                  |
|   Java App memicu: fileChannel.transferTo(position, count, targetSocket);   |
+-----------------------------------------------------------------------------+
|                                KERNEL SPACE                                 |
|                                                                             |
|   +-----------------------------------+   Descriptors   +---------------+   |
|   |    OS Kernel Page Cache (Disk)    |───────────────>│ Socket Buffer |   |
|   +-----------------------------------+   (Len, Offset) +---------------+   |
|                     ▲                                           │           |
|                     │                                           │           |
|                     │ (Copy 1: DMA Engine)                      │           |
|                     │                                           │           |
|              +--------------+                                   │           |
|              |     DISK     |                                   │           |
|              +--------------+                                   │           |
|                                                                 │           |
|                     NIC DMA Engine membaca langsung             │           |
|                     dari Page Cache via Descriptors             ▼           |
|              +------------------------------------------------------+       |
|              |                  NIC BUFFER / CHIP                   |       |
|              +------------------------------------------------------+       |
+-----------------------------------------------------------------------------+
```

### 2. Arsitektur Java NIO Multiplexing (Reactor Pattern)

```
                       [ Incoming TCP Connections ]
                                     │
                                     ▼
                      +-----------------------------+
                      |   ServerSocketChannel       |
                      |   (Non-Blocking Mode)       |
                      +-----------------------------+
                                     │
                                     ▼
                +─────────────────────────────────────────+
                │        java.nio.channels.Selector       │
                │        (Backing: OS epoll/kqueue)       │
                +─────────────────────────────────────────+
                                     │
             ┌───────────────────────┼───────────────────────┐
             │ Event: OP_ACCEPT      │ Event: OP_READ        │ Event: OP_WRITE
             ▼                       ▼                       ▼
   +-------------------+   +-------------------+   +-------------------+
   |  Acceptor Handler |   | Read Worker /     |   | Flush Handler /   |
   |  Registers new    |   | RingBuffer Engine |   | Socket Writer     |
   |  SocketChannel    |   | (Direct Memory)   |   |                   |
   +-------------------+   +-------------------+   +-------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `ByteBuffer`: Heap vs. Direct Memory

Di dalam Java NIO, `java.nio.ByteBuffer` adalah abstraksi struktural data primitif. Terdapat dua jenis internal:

*   **`HeapByteBuffer`**: Dialokasikan di dalam memori JVM Heap standar.
    *   *Mekanisme I/O:* Saat I/O native dipanggil, JVM **tidak dapat** langsung meneruskan alamat array heap ke Kernel OS via *system call*. Mengapa? Karena Garbage Collector dapat memindahkan objek di heap sewaktu-waktu (*compaction*). Oleh karena itu, JVM runtime harus menyalin data secara implisit dari `HeapByteBuffer` ke sebuah *temporary direct buffer* di C-heap, baru mengeksekusi system call.
    *   *Penalti:* Terjadi duplikasi memori dan lonjakan alokasi sementara (*temporary object garbage*).
*   **`DirectByteBuffer`**: Dialokasikan di luar JVM Heap menggunakan fungsi native `malloc()` (C-runtime) melalui `sun.misc.Unsafe` atau C-heap allocations internal.
    *   *Mekanisme I/O:* Alamat memori bersifat konstan (*pinned memory*). Kernel dapat langsung membaca dari atau menulis ke pointer alamat fisik Direct Buffer menggunakan *Direct Memory Access* (DMA).
    *   *Lifecycle:* Tidak dikelola langsung oleh algoritma penandaan GC standar. Pembersihannya bergantung pada `java.lang.ref.Cleaner` (atau `PhantomReference`). Jika alokasi berlebih tanpa pelepasan yang teratur, dapat memicu `java.lang.OutOfMemoryError: Direct buffer memory`.

#### Struktur Indeks Penunjuk Buffer:
Sebuah `Buffer` dikendalikan oleh 4 nilai invarian:
$$\text{mark} \le \text{position} \le \text{limit} \le \text{capacity}$$

*   **`capacity`**: Kapasitas total elemen memori yang dialokasikan.
*   **`position`**: Indeks berikutnya yang akan dibaca atau ditulis.
*   **`limit`**: Batas akhir elemen yang diizinkan untuk dibaca atau ditulis.
*   **`mark`**: Penanda indeks sementara yang dapat dipulihkan melalui `reset()`.

Operasi Krusial:
*   `flip()`: Mempersiapkan buffer untuk pembacaan setelah proses penulisan selesai. Mengatur `limit = position; position = 0; mark = -1;`.
*   `clear()`: Mengosongkan buffer untuk penulisan ulang. Mengatur `position = 0; limit = capacity; mark = -1;` (Data fisik **tidak** dihapus, hanya penunjuk indeks yang direset).
*   `compact()`: Menyalin elemen yang belum terbaca (antara `position` dan `limit`) ke awal buffer (`index 0`), mengatur `position = limit - position`, dan `limit = capacity`. Berguna saat pembacaan soket tidak tuntas.

### 2. Mekanisme I/O Multiplexing: `Selector` dan Syscall `epoll`

Pada sistem Linux, Java NIO `Selector` mengabstraksikan antarmuka *polling* berbasis kernel:
*   **Lama (`select` / `poll`):** $O(N)$ kompleksitas waktu. Setiap pengecekan membutuhkan pengiriman seluruh array file descriptor (*FD*) dari user-space ke kernel-space.
*   **Modern (`epoll` di Linux / `kqueue` di BSD/macOS):** $O(1)$ kompleksitas terhadap total koneksi aktif. Menggunakan struktur Red-Black Tree di kernel untuk melacak registrasi FD dan sebuah *Ready List* (Double Linked List) yang diisi secara asinkron oleh OS saat ada interupsi perangkat keras.
    *   `epoll_create()`: Mempersiapkan konteks kernel epoll.
    *   `epoll_ctl()`: Mendaftarkan file descriptor soket dengan event ketertarikan (`EPOLLIN`, `EPOLLOUT`).
    *   `epoll_wait()`: Memblokir eksekusi thread sampai interupsi I/O terjadi, mengembalikan *hanya* FD yang memiliki event siap (*ready list*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. BIO vs. NIO vs. AIO

| Dimensi | BIO (Blocking I/O) | NIO (Non-Blocking / Multiplexed) | AIO (Asynchronous I/O) |
| :--- | :--- | :--- | :--- |
| **Arsitektur Model** | 1 Koneksi = 1 Thread | N Koneksi = M Thread (Event Loop) | Proactor Pattern (OS Callback) |
| **Syscall Utama** | `read()`, `write()` (Blocking) | `epoll_wait()`, `read()` (EAGAIN) | `io_uring` (Linux baru), IOCP (Win) |
| **Beban Kernel** | Context Switching masif | Rendah, sangat efisien | Sangat rendah di Windows; di Linux lama simulasi pool thread |
| **Throughput** | Rendah di konkurensi tinggi | Sangat Tinggi (Tens of thousands+) | Sangat Tinggi |
| **Kompleksitas Kode** | Sederhana & Prosedural | Menengah hingga Kompleks | Sangat Kompleks |

### 2. Edge-Triggered (ET) vs. Level-Triggered (LT) pada Multiplexing

Java NIO secara default beroperasi pada mode **Level-Triggered (LT)** untuk portabilitas lintas OS:
*   **Level-Triggered (LT):** Kernel akan terus-menerus memberitahu bahwa FD siap dibaca/ditulis selama buffer kernel masih memiliki sisa data. Jika aplikasi membaca 1024 byte padahal kernel memiliki 2048 byte, pemanggilan `selector.select()` berikutnya akan **segera** terbangun kembali.
*   **Edge-Triggered (ET):** Kernel **hanya satu kali** memicu event saat ada transisi kondisi (misalnya dari data kosong menjadi ada data masuk). Jika aplikasi tidak membaca seluruh byte hingga habis (menguras kernel buffer sampai `EAGAIN` atau `EWOULDBLOCK`), kernel tidak akan memicu event baru untuk data sisa tersebut, berisiko mengunci data (*hang*). Frameork performa ekstrim (seperti Netty native transport) menggunakan mode ET untuk menghemat overhead syscall kernel.

### 3. Memory-Mapped Files (`mmap`) & Page Faults

`FileChannel.map(MapMode mode, long position, long size)` menggunakan system call `mmap()`. 
*   Alih-alih memindahkan data disk ke JVM heap melalui `read()`, `mmap` memetakan langsung blok file di disk ke *Virtual Address Space* dari proses aplikasi.
*   Data tidak langsung dimuat ke RAM fisik seluruhnya. Ketika pointer memori diakses, MMU (Memory Management Unit) CPU menghasilkan **Major Page Fault** jika data belum ada di OS Page Cache, meminta OS membaca blok tersebut dari disk langsung ke halaman memori fisik.
*   **Keuntungan:** Akses I/O file dapat diperlakukan seringkas membaca memori mentah (`MappedByteBuffer.get()`), memangkas overhead read/write syscall sepenuhnya untuk operasi berikutnya.

### 4. Cache Lines, False Sharing, dan Alignment

Dalam CPU modern, data dari memori utama dimuat ke CPU Cache (L1, L2, L3) dalam unit berukuran tetap, yaitu **64 bytes** (*Cache Line*).

```
Core 1 Cache                                  Core 2 Cache
+-------------------------------+             +-------------------------------+
| Variable A  |  Variable B     |             | Variable A  |  Variable B     |
+-------------------------------+             +-------------------------------+
       ▲               ▲                             ▲               ▲
       │               │                             │               │
  Core 1 Writes   Core 2 Reads                 Core 1 Writes   Core 2 Reads
```

Jika Thread A pada Core 1 memodifikasi `Variable A`, dan Thread B pada Core 2 membaca/menulis `Variable B`, tetapi kedua variabel tersebut terletak bersebelahan dalam cache line 64-byte yang sama, maka modifikasi oleh Core 1 akan membatalkan (*invalidate*) seluruh cache line pada Core 2 via cache coherency protocol (MESI). Ini disebut **False Sharing**.
*   **Dampak pada Low Latency:** Penurunan performa hingga puluhan kali lipat pada alur antrean konkuren (*Concurrent Ring Buffers*).
*   **Solusi:** Membatasi variabel kritis dengan padding bytes (atau anotasi `@jdk.internal.vm.annotation.Contended` di lingkungan internal) untuk memastikan variabel penting menempati cache line-nya sendiri.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi **High-Performance Non-Blocking TCP Echo & Processing Server** menggunakan Java NIO murni tanpa library eksternal. Kode ini menangani I/O non-blocking, multiplexing via `Selector`, dan manajemen memori direct buffer.

```java
package com.architect.lowlatency.nio;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.StandardSocketOptions;
import java.nio.ByteBuffer;
import java.nio.channels.ClosedChannelException;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.util.Iterator;
import java.util.Set;

public final class UltraFastNioServer implements Runnable {

    private final int port;
    private final Selector selector;
    private final ServerSocketChannel serverChannel;
    private final ByteBuffer sharedDirectBuffer;
    private volatile boolean running = true;

    public UltraFastNioServer(int port) throws IOException {
        this.port = port;
        // 1. Membuka selector epoll/kqueue internal
        this.selector = Selector.open();

        // 2. Membuka server socket channel
        this.serverChannel = ServerSocketChannel.open();
        this.serverChannel.configureBlocking(false);

        // 3. Konfigurasi Level Soket untuk Latensi Rendah
        this.serverChannel.setOption(StandardSocketOptions.SO_REUSEADDR, true);
        this.serverChannel.setOption(StandardSocketOptions.SO_RCVBUF, 64 * 1024);

        // 4. Bind ke port lokal
        this.serverChannel.bind(new InetSocketAddress(this.port), 1024);

        // 5. Daftarkan event accept ke selector
        this.serverChannel.register(this.selector, SelectionKey.OP_ACCEPT);

        // 6. Alokasi buffer memori native (Off-Heap) 4KB
        this.sharedDirectBuffer = ByteBuffer.allocateDirect(4096);
    }

    @Override
    public void run() {
        System.out.println("[INFO] NIO Server berjalan pada port: " + port);
        try {
            while (running) {
                // Blokir thread sampai ada I/O events yang siap pada OS level
                int readyChannels = selector.select();
                if (readyChannels == 0) {
                    continue;
                }

                Set<SelectionKey> selectedKeys = selector.selectedKeys();
                Iterator<SelectionKey> keyIterator = selectedKeys.iterator();

                while (keyIterator.hasNext()) {
                    SelectionKey key = keyIterator.next();
                    // Sangat krusial: Hapus key dari set segera untuk menghindari pemrosesan ganda
                    keyIterator.remove();

                    if (!key.isValid()) {
                        continue;
                    }

                    try {
                        if (key.isAcceptable()) {
                            handleAccept(key);
                        } else if (key.isReadable()) {
                            handleRead(key);
                        } else if (key.isWritable()) {
                            handleWrite(key);
                        }
                    } catch (IOException e) {
                        System.err.println("[WARN] Client I/O Error: " + e.getMessage());
                        closeChannelQuietly(key);
                    }
                }
            }
        } catch (IOException e) {
            System.err.println("[ERROR] Server Loop Exception: " + e.getMessage());
        } finally {
            cleanup();
        }
    }

    private void handleAccept(SelectionKey key) throws IOException {
        ServerSocketChannel ssc = (ServerSocketChannel) key.channel();
        SocketChannel clientChannel = ssc.accept();
        if (clientChannel != null) {
            clientChannel.configureBlocking(false);

            // TCP_NODELAY menonaktifkan algoritma Nagle (menghilangkan latensi buffering TCP)
            clientChannel.setOption(StandardSocketOptions.TCP_NODELAY, true);
            clientChannel.setOption(StandardSocketOptions.SO_KEEPALIVE, true);

            // Daftarkan channel untuk event Read
            clientChannel.register(selector, SelectionKey.OP_READ);
        }
    }

    private void handleRead(SelectionKey key) throws IOException {
        SocketChannel clientChannel = (SocketChannel) key.channel();
        sharedDirectBuffer.clear(); // Reset pointer: position=0, limit=capacity

        int bytesRead = clientChannel.read(sharedDirectBuffer);

        if (bytesRead == -1) {
            // Client mengirim sinyal FIN (koneksi ditutup secara tertib)
            closeChannelQuietly(key);
            return;
        }

        if (bytesRead > 0) {
            // Balik buffer dari mode tulis ke mode baca
            sharedDirectBuffer.flip();

            // Pemrosesan payload (Contoh: Echo langsung ke client)
            while (sharedDirectBuffer.hasRemaining()) {
                clientChannel.write(sharedDirectBuffer);
            }

            // Jika socket write buffer penuh, alihkan ke OP_WRITE (Dipotong untuk efisiensi contoh)
        }
    }

    private void handleWrite(SelectionKey key) throws IOException {
        // Implementasi flush buffer sisa jika pengiriman parsial terjadi
    }

    private void closeChannelQuietly(SelectionKey key) {
        try {
            key.cancel();
            key.channel().close();
        } catch (IOException ignored) {
        }
    }

    public void stop() {
        this.running = false;
        this.selector.wakeup();
    }

    private void cleanup() {
        try {
            selector.close();
            serverChannel.close();
        } catch (IOException ignored) {
        }
    }

    public static void main(String[] args) throws IOException {
        UltraFastNioServer server = new UltraFastNioServer(8080);
        Thread serverThread = new Thread(server, "NIO-Engine-Thread");
        serverThread.start();
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 24:** `this.selector = Selector.open();`  
    Menginisialisasi multiplexer OS. Pada Linux modern, ini memicu system call native `epoll_create1(EPOLL_CLOEXEC)`. Objek ini menjadi jantung pengelolaan ribuan koneksi.
*   **Baris 28:** `this.serverChannel.configureBlocking(false);`  
    Mengalihkan Server Socket Channel ke mode non-blocking. Panggilan `accept()` setelah operasi ini tidak akan memblokir thread eksekusi jika tidak ada koneksi baru yang antre, melainkan langsung mengembalikan `null`.
*   **Baris 31:** `this.serverChannel.setOption(StandardSocketOptions.SO_REUSEADDR, true);`  
    Memperbolehkan socket mengikat alamat lokal yang masih dalam status `TIME_WAIT` dari koneksi sebelumnya, mempercepat waktu restart server dalam pipeline CI/CD atau failover.
*   **Baris 38:** `this.serverChannel.register(this.selector, SelectionKey.OP_ACCEPT);`  
    Mendaftarkan `ServerSocketChannel` ke `Selector` dengan bitmask ketertarikan `SelectionKey.OP_ACCEPT`. Sistem kernel akan memantau kedatangan paket TCP SYN baru.
*   **Baris 41:** `this.sharedDirectBuffer = ByteBuffer.allocateDirect(4096);`  
    Mengalokasikan memori sebesar 4KB langsung pada Virtual Memory OS di luar Java Heap. Alokasi ini kebal terhadap GC Pause dan mendukung direct memory transfer oleh NIC DMA.
*   **Baris 49:** `int readyChannels = selector.select();`  
    Memanggil `epoll_wait()`. Thread utama akan masuk ke state blocked level-OS tanpa menghabiskan siklus CPU hingga setidaknya satu channel memiliki event I/O yang relevan.
*   **Baris 57:** `keyIterator.remove();`  
    **Instruksi Sangat Kritis.** Selector mengisi `selectedKeys` set, namun **tidak pernah** menghapusnya secara otomatis. Jika tidak dihapus via iterator, key yang sama akan diproses ulang di iterasi loop berikutnya, menyebabkan komputasi sia-sia dan `NullPointerException` atau `ClosedChannelException`.
*   **Baris 82:** `clientChannel.setOption(StandardSocketOptions.TCP_NODELAY, true);`  
    Mematikan Algoritma Nagle. Nagle berusaha mengumpulkan paket-paket kecil untuk dikirim bersamaan demi efisiensi bandwidth. Mematikannya adalah hukum wajib untuk transmisi berlatensi rendah agar paket sekecil apa pun langsung terkirim seketika ke jaringan.
*   **Baris 92:** `sharedDirectBuffer.clear();`  
    Mengatur kembali pointer buffer: `position = 0` dan `limit = capacity`. Data lama tidak ditimpa dengan nilai nol (efisiensi siklus instruksi), penulisan data baru nantinya akan langsung meng-overwrite byte secara bertahap.
*   **Baris 94:** `int bytesRead = clientChannel.read(sharedDirectBuffer);`  
    Melakukan eksekusi native non-blocking read. Jika menghasilkan `-1`, client telah memutus koneksi via TCP FIN, sehingga channel harus ditutup dan dibatalkan pendaftarannya (`key.cancel()`).
*   **Baris 103:** `sharedDirectBuffer.flip();`  
    Mengubah status buffer dari *write-mode* ke *read-mode*. Menetapkan nilai `limit` ke posisi `position` terakhir (jumlah data valid yang baru saja dibaca), dan menyetel `position = 0`.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Market Data Binary Feed Ingestion Engine (High-Frequency Ingestion)

#### Masalah Produksi:
Sebuah bursa komoditas dan kripto mengirimkan miliaran pembaruan harga (*Order Book L2 Tick Updates*) setiap hari menggunakan paket UDP/TCP biner berkecepatan tinggi. 
* Arsitektur awal berbasis Spring MVC / IO Stream konvensional mengalami:
  * Latensi P99 melambung hingga **180 ms** akibat GC Stop-the-World (STW) pauses.
  * *Heap bloat* karena deserialisasi jutaan objek JSON/String per detik.
  * CPU tersedot untuk operasi alokasi memory copy antara OS socket buffer dan Java Heap.

#### Solusi Rekayasa Sistem:
Membangun sebuah ultra-low-latency Ingestion Engine:
1. Membaca paket biner mentah menggunakan `SocketChannel` non-blocking ke dalam off-heap `DirectByteBuffer` yang telah di-pool (*Zero Allocation*).
2. Membaca data byte secara *flyweight* (langsung membaca offset byte array via pointer tanpa memicu alokasi objek model Java).
3. Melakukan persisting streaming tick ke dalam disk menggunakan `MappedByteBuffer` (Memory-Mapped File) yang di-flush secara asinkron.
4. Latensi P99 dipangkas dari **180 ms** menjadi **< 15 mikrodetik (µs)** dengan **0 byte alokasi heap** pada hot-path.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah kode produksi *Flyweight Binary Protocol Parser* dan *Zero-GC Ingestion Buffer* untuk parsing data tick biner secara instan dari direct memory.

Format Binary Packet (16 Bytes Total per Tick):
* `int32` (4 bytes): Instrument ID
* `int64` (8 bytes): Epoch Timestamp in Nanoseconds
* `int32` (4 bytes): Price scaled to $10^{-4}$

```java
package com.architect.lowlatency.engine;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;

public final class MarketDataEngine {

    // Ukuran satu paket tick biner
    public static final int TICK_RECORD_SIZE = 16;
    private static final int BUFFER_POOL_CAPACITY = 1024 * TICK_RECORD_SIZE; // 16 KB

    // Memory-Mapped File Persister
    private final MappedByteBuffer mmapPersister;

    public MarketDataEngine(File storageFile, long preallocatedSize) throws Exception {
        // Pre-alokasi file di disk agar OS tidak fragmented saat penulisan run-time
        try (RandomAccessFile raf = new RandomAccessFile(storageFile, "rw")) {
            raf.setLength(preallocatedSize);
            this.mmapPersister = raf.getChannel().map(
                    FileChannel.MapMode.READ_WRITE, 0, preallocatedSize
            );
        }
    }

    /**
     * Memproses batch tick yang masuk pada DirectByteBuffer secara Zero-Allocation.
     * Menggunakan konsep Flyweight Pattern (tanpa instansiasi objek OrderTick).
     */
    public void processIncomingBatch(ByteBuffer networkDirectBuffer) {
        // Asumsi: networkDirectBuffer sudah di-flip dan siap dibaca
        while (networkDirectBuffer.remaining() >= TICK_RECORD_SIZE) {
            
            // Baca data primitif langsung dari memori via offset absolut untuk performa maksimal
            int currentPos = networkDirectBuffer.position();
            
            int instrumentId = networkDirectBuffer.getInt(currentPos);
            long timestampNs  = networkDirectBuffer.getLong(currentPos + 4);
            int scaledPrice  = networkDirectBuffer.getInt(currentPos + 12);

            // Geser posisi buffer maju 16 bytes
            networkDirectBuffer.position(currentPos + TICK_RECORD_SIZE);

            // 1. Eksekusi Rule Mesin Cepat (Inline Evaluation)
            evaluateTradingRule(instrumentId, timestampNs, scaledPrice);

            // 2. Tulis langsung ke MMAP Buffer (Zero-Copy Persistence)
            persistTick(instrumentId, timestampNs, scaledPrice);
        }

        // Jika tersisa byte ganjil akibat segmentasi paket TCP, lakukan compact
        networkDirectBuffer.compact();
    }

    private void evaluateTradingRule(int instrumentId, long timestampNs, int scaledPrice) {
        // Hot path: Menghindari pembuatan String, Boxing/Unboxing, atau Logging di sini.
        if (scaledPrice <= 0) {
            // Drop anomaly tanpa alokasi exception di hot-path
            return;
        }
        // Logika eksekusi trading low latency deterministik ditempatkan di sini...
    }

    private void persistTick(int instrumentId, long timestampNs, int scaledPrice) {
        if (mmapPersister.remaining() >= TICK_RECORD_SIZE) {
            mmapPersister.putInt(instrumentId);
            mmapPersister.putLong(timestampNs);
            mmapPersister.putInt(scaledPrice);
        } else {
            // Buffer MMAP Penuh - Roll-over file secara asinkron
            handleMmapRollOver();
        }
    }

    private void handleMmapRollOver() {
        // Mekanisme roll over disk terpisah
    }

    public static void main(String[] args) throws Exception {
        File dataFile = new File("market_data.bin");
        long fileSize = 64 * 1024 * 1024; // 64 MB Preallocated memory-mapped file
        
        MarketDataEngine engine = new MarketDataEngine(dataFile, fileSize);

        // Simulasi pembacaan paket jaringan menggunakan DirectByteBuffer
        ByteBuffer networkBuffer = ByteBuffer.allocateDirect(BUFFER_POOL_CAPACITY);

        // Simulasi inject data biner mentah (3 Tick dimasukkan sekaligus)
        for (int i = 1; i <= 3; i++) {
            networkBuffer.putInt(1001);                 // Instrument: AAPL
            networkBuffer.putLong(System.nanoTime());   // Timestamp
            networkBuffer.putInt(1502500);              // Price: 150.2500
        }

        // Siapkan buffer untuk pembacaan parsing
        networkBuffer.flip();

        long startNs = System.nanoTime();
        engine.processIncomingBatch(networkBuffer);
        long elapsedNs = System.nanoTime() - startNs;

        System.out.println("[PERF] 3 Binary Ticks diparsing dan dipersist ke mmap dalam: " 
                            + elapsedNs + " ns (" + (elapsedNs / 3.0) + " ns/tick)");

        // Bersihkan file uji coba saat aplikasi selesai
        dataFile.deleteOnExit();
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Matrix Pendekatan Alokasi Memori Java

| Metode | Latensi Akses (CPU) | Biaya Alokasi | Dampak GC | Throughput I/O Jaringan |
| :--- | :--- | :--- | :--- | :--- |
| **Heap Buffer (`byte[]`)** | Sangat Rendah (Optimal L1/L2) | Rendah (Pointer bump) | **Tinggi** (Penyebab utama GC Spikes) | Rendah (Membutuhkan internal copying) |
| **Direct Buffer (`allocateDirect`)** | Rendah | Tinggi (Memanggil system `malloc`) | **Nol** (Di luar JVM Heap) | Maksimal (Direct Memory Access / DMA) |
| **Memory Mapped (`mmap`)** | Sangat Rendah (Pointers langsung) | Sangat Tinggi (Kernel Page Mapping) | **Nol** | Maksimal untuk I/O Disk |

### 2. Network I/O Paradigm Trade-offs

```
Latensi (Rendah lebih baik)
  ▲
  │                                    [BIO: 1 Thread per Connection]
  │                                    - Latensi hancur saat ribuan koneksi
  │                                    - Penggunaan RAM masif (Stack Thread)
  │
  │                  [Java NIO Selector (Multiplexing)]
  │                  - Keseimbangan ideal latensi & konkurensi masif
  │                  - Kompleksitas kode menengah
  │
  │    [Kernel Bypass / Agrona / Aeron (JNI + DPDK/eBPF)]
  │    - Latensi sub-mikrodetik absolut
  │    - Kompleksitas rekayasa ekstrem, portabilitas OS hilang
  └─────────────────────────────────────────────────────────────► Skala Konkurensi
```

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Linux `epoll()` 100% CPU Utilization Bug
*   **Mekanisme:** Sebuah bug terkenal pada Java NIO di Linux di mana `Selector.select()` terbangun secara terus menerus (*busy loop*) meskipun tidak ada file descriptor yang siap I/O. Hal ini terjadi saat client melakukan terminasi abnormal (misalnya via `TCP RST`), menyebabkan OS membangkitkan event polling yang tidak dipahami oleh JVM runtime lama, mengakibatkan loop tak hingga yang mengonsumsi 100% 1 Core CPU.
*   **Penanganan:** Implementasikan strategi deteksi counter. Jika `selector.select()` kembali dengan return `0` secara beruntun sebanyak $N$ kali (misal 512 kali berturut-turut) tanpa event nyata, rebuild selector: buat instance `Selector` baru, daftarkan ulang channel lama, dan tutup selector lama. (Pustaka seperti Netty memiliki mekanisme ini secara built-in).

### 2. Direct Memory Leaks & Out of Memory
*   Memori yang dialokasikan via `ByteBuffer.allocateDirect()` tidak tunduk pada `-Xmx` JVM heap limit, melainkan dibatasi oleh `-XX:MaxDirectMemorySize`.
*   Direct buffer hanya dibebaskan ketika objek Java pembungkusnya (*wrapper object*) di-garbage collect. Jika wrapper dipromosikan ke *Old Generation* dan GC mayor jarang terjadi, sistem operasi dapat kehabisan memori native (*OS OOM Killer* membunuh proses Java).

### 3. Partial Socket Writes
*   Ketika memanggil `SocketChannel.write(buffer)`, tidak ada jaminan seluruh buffer terkirim ke socket. Jika buffer transmisi TCP milik kernel sudah penuh, method akan mengembalikan jumlah byte yang tertulis (bisa kurang dari sisa buffer, bahkan `0`).
*   Mengabaikan nilai kembalian `write()` dapat mengakibatkan data payload terpotong (*data corruption* pada protokol stream).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Lupa Memanggil `flip()` Sebelum Membaca Buffer

```java
// SALAH: Buffer baru diisi, tetapi dibaca tanpa flip()
ByteBuffer buf = ByteBuffer.allocateDirect(1024);
socketChannel.read(buf); // position bertambah ke N
// Mencoba menulis ke socket lain langsung
targetChannel.write(buf); // AKAN MENULIS 0 BYTE! Karena limit masih di 1024 dan position di N

// BENAR: Selalu balik mode penulisan ke pembacaan
ByteBuffer buf = ByteBuffer.allocateDirect(1024);
socketChannel.read(buf);
buf.flip(); // limit = position; position = 0
targetChannel.write(buf);
```

### Kesalahan 2: Menggunakan `allocateDirect()` di Dalam Loop Transaksi

```java
// SALAH: Membuat native buffer berulang kali per transaksi
while (running) {
    // Alokasi memori native (malloc syscall) sangat lambat dan mahal!
    ByteBuffer buffer = ByteBuffer.allocateDirect(1024);
    clientChannel.read(buffer);
    process(buffer);
}

// BENAR: Alokasikan satu kali dan gunakan kembali (Buffer Pooling / Ring Buffer)
ByteBuffer pooledBuffer = ByteBuffer.allocateDirect(1024);
while (running) {
    pooledBuffer.clear(); // Sangat murah! Hanya memindahkan pointer index
    clientChannel.read(pooledBuffer);
    pooledBuffer.flip();
    process(pooledBuffer);
}
```

### Kesalahan 3: Iterasi `selectedKeys()` Tanpa Menghapus Elemen

```java
// SALAH: Tidak memanggil iterator.remove()
Set<SelectionKey> keys = selector.selectedKeys();
for (SelectionKey key : keys) {
    if (key.isReadable()) {
        readData(key); // Di iterasi select() berikutnya, key ini MASIH ADA di set!
    }
}

// BENAR: Selalu gunakan Iterator dan panggil it.remove()
Iterator<SelectionKey> it = selector.selectedKeys().iterator();
while (it.hasNext()) {
    SelectionKey key = it.next();
    it.remove(); // Hapus dari ready set
    if (key.isReadable()) {
        readData(key);
    }
}
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Ring Buffer Pattern (LMAX Disruptor Architecture):** Untuk memisahkan I/O Network Reader Thread dari Business Logic Worker Thread tanpa memicu lock contention.
2.  **Sematkan Buffer Pooling:** Gunakan pooling framework (misal `PooledByteBufAllocator` milik Netty atau custom array stack pool) untuk mendaur ulang off-heap chunk.
3.  **Terapkan Explicit Zero-Copy:** Gunakan `FileChannel.transferTo()` / `transferFrom()` bila mentransfer file langsung ke soket. Ini menggunakan instruksi kernel `sendfile` yang mengeksploitasi DMA.
4.  **Matikan Nagle's Algorithm secara Eksplisit:** Selalu gunakan `socketChannel.setOption(StandardSocketOptions.TCP_NODELAY, true)` pada aplikasi bertipe RPC atau pemrosesan pesan cepat.
5.  **Pinning Thread ke CPU Cores (Thread Affinity):** Di sistem sub-mikrodetik, sematkan I/O multiplexer thread ke CPU core khusus menggunakan library seperti Java-Thread-Affinity (OpenHFT) guna mencegah OS context switching antar core.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Parameter Tuning Kernel OS (Linux `/etc/sysctl.conf`)
Konfigurasi kernel penting untuk I/O berkapasitas tinggi:
```ini
# Memperbesar buffer socket maksimum (membaca dan menulis)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216

# Auto-tuning TCP Buffer (min, default, max bytes)
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Memperbesar backlog connection queue
net.core.somaxconn = 32768

# Efisiensi epoll dalam menangani file descriptors masif
fs.file-max = 2097152
```

### 2. Flag JVM Mandatori untuk Low-Latency I/O
```bash
java -XX:+UseNUMA \
     -XX:+UseZGC \
     -XX:MaxDirectMemorySize=8G \
     -XX:+UnlockDiagnosticVMOptions \
     -XX:GuaranteedSafepointInterval=0 \
     -Djava.net.preferIPv4Stack=true \
     -jar ultra-latency-service.jar
```
*   `-XX:+UseNUMA`: Mengoptimalkan penempatan memori JVM berdasarkan kedekatan fisik dengan socket CPU yang mengeksekusi thread.
*   `-XX:MaxDirectMemorySize=8G`: Mencegah crash native memory dengan memberikan batasan pasti alokasi off-heap.
*   `-Djava.net.preferIPv4Stack=true`: Menghindari overhead parsing dual-stack IPv6 di level kernel networking C-library jika jaringan internal murni IPv4.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Slowloris & Slow Read Attacks
*   **Vektor Serangan:** Penyerang membuka ribuan koneksi TCP dan mengirimkan byte dengan kecepatan sangat lambat (misal 1 byte per 10 detik) atau membaca respons sangat lambat untuk menahan buffer kernel terbuka.
*   **Hardening (Java NIO):** Implementasikan *Idle Timeout Watchdog*. Setiap `SocketChannel` wajib memiliki atribut waktu interaksi terakhir (`lastActivityTimestamp`). Jika selisih `currentTime - lastActivityTimestamp > TIMEOUT_THRESHOLD`, putuskan soket secara paksa (`channel.close()`).

### 2. Direct Memory Exhaustion DoS
*   **Vektor Serangan:** Penyerang mengirimkan header frame yang memuat field *payload length* palsu yang sangat besar (misal 2GB), memicu server mengalokasikan direct buffer masif yang menguras RAM server seketika (*OOM Crash*).
*   **Mitigasi:** 
    1. Validasi batas maksimum frame size di awal sebelum parsing (`if (frameSize > MAX_ALLOWED_PACKET) disconnectClient();`).
    2. Alokasikan buffer tetap (*fixed-size*) dan tolak payload yang melampaui kapasitas tanpa alokasi dinamis.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Memantau Penggunaan Direct Memory via JMX

Java menyediakan MXBean internal untuk memantau konsumsi memori off-heap yang tidak terlihat oleh heap profiler biasa:

```java
import java.lang.management.ManagementFactory;
import java.lang.management.BufferPoolMXBean;
import java.util.List;

public class DirectMemoryMonitor {
    public static void printDirectMemoryUsage() {
        List<BufferPoolMXBean> pools = ManagementFactory.getPlatformMXBeans(BufferPoolMXBean.class);
        for (BufferPoolMXBean pool : pools) {
            System.out.printf("Pool Name: %s | Count: %d | Total Capacity: %.2f MB | Memory Used: %.2f MB%n",
                pool.getName(),
                pool.getCount(),
                pool.getTotalCapacity() / (1024.0 * 1024.0),
                pool.getMemoryUsed() / (1024.0 * 1024.0)
            );
        }
    }
}
```

### 2. Diagnosis Latensi via OS Tools (`perf`, `strace`, `eBPF`)
*   **Mendeteksi Syscall Blocking:**
    Gunakan `strace` untuk melihat apakah epoll thread mengalami blocking yang tidak diharapkan:
    ```bash
    strace -cp <PID_JAVA>
    ```
    Melihat distribusi waktu sistem: jika waktu terbesar ada di `futex`, berarti terjadi persaingan thread lock; jika di `epoll_wait`, sistem berada dalam status I/O bound menunggu input jaringan.
*   **eBPF Profiling (BCC Tools):**
    Menggunakan `tcprtt` untuk mengukur Round-Trip Time (RTT) soket TCP secara real-time langsung dari kernel probe tanpa menambahkan overhead komputasi pada kode Java.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Intisari Status Buffer
```
                    limit (setelah flip)      capacity
                              ▼                  ▼
[ B | Y | T | E | S |   |   |   |   |   |   |   ]
                      ▲
                   position (setelah flip, siap dibaca dari 0 s.d limit)
```

### 2. Operasi Buffer Cepat
*   `buffer.flip()` $\rightarrow$ Pindah dari mode **menulis** ke mode **membaca**. (`limit = position; position = 0;`)
*   `buffer.clear()` $\rightarrow$ Reset pointer untuk **menulis ulang**. (`position = 0; limit = capacity;`)
*   `buffer.compact()` $\rightarrow$ Salin sisa unread bytes ke depan, lanjutkan **menulis**.
*   `buffer.rewind()` $\rightarrow$ Baca ulang buffer dari awal. (`position = 0;`)

### 3. Pemilihan I/O Strategy Matrix
*   **Gunakan BIO** jika: Koneksi sedikit ($<100$), throughput rendah, sistem scripting sederhana.
*   **Gunakan Java NIO Direct Buffer** jika: Perlu performa I/O tinggi, koneksi masif concurrent ($>10,000$), beban GC harus minim.
*   **Gunakan FileChannel Zero-Copy (`transferTo`)** jika: Mengirim file utuh dari disk langsung ke antarmuka jaringan.
*   **Gunakan `MappedByteBuffer`** jika: Sequential logging kecepatan tinggi, binary database persistence, file cache super cepat.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa perbedaan fundamental antara `ByteBuffer.allocate()` dan `ByteBuffer.allocateDirect()`?**
   * *Jawaban:* `allocate()` membuat buffer di Java Virtual Machine Heap yang dikelola oleh Garbage Collector dan memerlukan internal copy saat operasi I/O native. `allocateDirect()` mengalokasikan memori native di luar heap (C-heap) yang memungkinkan kernel mengaksesnya langsung via DMA tanpa salinan tambahan dan kebal dari GC.

2. **Apa yang terjadi secara internal ketika kita memanggil `buffer.flip()`?**
   * *Jawaban:* Method mengatur nilai `limit` ke nilai `position` saat ini, kemudian mengatur nilai `position` kembali ke indeks `0`, serta membatalkan nilai `mark` yang aktif. Ini mempersiapkan buffer dari tahap penulisan ke tahap pembacaan.

3. **Mengapa pemanggilan `iterator.remove()` wajib dilakukan saat mengiterasi `selector.selectedKeys()`?**
   * *Jawaban:* Karena Selector tidak menghapus key yang sudah siap secara otomatis dari *selected-key set*. Jika tidak dihapus manual, key tersebut akan tetap berada di set pada pemanggilan `select()` berikutnya, menyebabkan aplikasi memproses event usang atau menangani objek yang statusnya sudah berubah/tertutup.

4. **Bagaimana fungsi flag `TCP_NODELAY` dalam meningkatkan performa transmisi socket?**
   * *Jawaban:* Flag ini mematikan Algoritma Nagle. Algoritma Nagle secara default menahan paket-paket kecil sampai buffer penuh atau acknowledgment paket sebelumnya diterima untuk menghemat utilisasi segmen jaringan. Mematikannya membuat seluruh frame data terkirim langsung seketika, menurunkan latensi jaringan.

5. **Apa fungsi utama dari system call `epoll` dibandingkan `select` lama di Linux?**
   * *Jawaban:* `epoll` memiliki kompleksitas algoritma $O(1)$ terhadap total koneksi aktif untuk mengembalikan deskriptor yang siap, sedangkan `select` beroperasi pada $O(N)$ karena harus memindai seluruh set file deskriptor dari user space ke kernel space setiap kali dipanggil.

---

### Soal Tingkat Menengah (Intermediate)

6. **Jelaskan fenomena *epoll CPU 100% bug* pada Java NIO dan bagaimana arsitektur modern mengatasinya!**
   * *Jawaban:* Bug ini terjadi ketika koneksi TCP terputus secara tidak wajar (`RST`), menyebabkan OS memicu loop event polling epoll yang tidak dapat ditangani Selector Java runtime secara benar, membuat `Selector.select()` terbangun terus-menerus tanpa memblokir thread (return 0). Solusinya adalah memantau frekuensi loop nol berturut-turut, dan jika melampaui batas tertentu, membuat instance Selector baru secara runtime dan memindahkan seluruh registrasi channel ke Selector baru tersebut.

7. **Mengapa *Memory-Mapped Files* (`mmap`) dapat menimbulkan degradasi latensi yang tak terduga (*latency spikes*) jika tidak ditangani dengan benar?**
   * *Jawaban:* Karena `mmap` mengandalkan Virtual Memory OS dan *Page Faults*. Ketika pointer diarahkan ke segmen virtual memory yang belum termuat di RAM fisik atau telah di-*flush* ke disk swap oleh kernel, MMU akan men-suspend thread hingga Major Page Fault selesai mengambil data dari disk mekanis/SSD, yang menyebabkan terhentinya eksekusi deterministik secara tiba-tiba.

8. **Bagaimana mekanisme *Zero-Copy* `FileChannel.transferTo()` menghemat siklus CPU dibandingkan stream read/write konvensional?**
   * *Jawaban:* Pendekatan stream membutuhkan 4 context switches dan 4 kali salinan data (Disk $\rightarrow$ Kernel Cache $\rightarrow$ User Heap $\rightarrow$ Socket Buffer $\rightarrow$ NIC). `transferTo()` memicu system call `sendfile` di mana kernel mentransfer data langsung dari Page Cache ke NIC Buffer menggunakan DMA engine, mereduksi context switch menjadi 2 kali dan CPU data copies menjadi 0.

9. **Apa yang dimaksud dengan *False Sharing* dalam pemrosesan data konkuren tingkat rendah dan bagaimana mencegahnya di Java?**
   * *Jawaban:* False sharing terjadi ketika dua variabel independen yang dimodifikasi oleh thread di core CPU yang berbeda berada di dalam satu *Cache Line* (64-byte) yang sama. Modifikasi satu variabel memaksa seluruh cache line di core lain dibatalkan (*invalidated*). Cara mencegahnya adalah menambahkan *padding bytes* manual atau menggunakan anotasi `@Contended` agar variabel kritis ditempatkan pada cache line terpisah.

10. **Kapan alokasi `DirectByteBuffer` dapat menyebabkan fatal OutOfMemoryError meskipun memori JVM Heap masih sangat lapang?**
    * *Jawaban:* Ketika memori native fisik mencapai limit yang dialokasikan OS atau batas parameter `-XX:MaxDirectMemorySize`, sementara objek wrapper Java di heap belum di-reclaim oleh GC (misal tertahan di Old Generation tanpa ada GC mayor). Akibatnya, pemanggilan native `malloc` gagal dan JVM melempar `OutOfMemoryError: Direct buffer memory`.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang & Bangun: Ultra-Low-Latency Financial Tick Replay Engine

#### Deskripsi Spesifikasi Proyek:
Buatlah sebuah aplikasi server standalone Java NIO murni (tanpa dependencies eksternal seperti Netty, Spring, atau Apache Commons) yang mengemulasi sebuah Gateway Pertukaran Finansial:

1.  **Binary Data Reader:**
    *   Membuka file binary log berukuran 100MB berisi jutaan data tick (format sama seperti SEKSI 10: 16-byte record: `int32 ID`, `int64 timestamp`, `int32 price`).
    *   Gunakan `FileChannel.map` untuk memetakan seluruh data file ke memori secara instan.
2.  **TCP Broadcast Server:**
    *   Gunakan non-blocking `ServerSocketChannel` dan `Selector` yang berjalan pada thread dedicated.
    *   Server harus mampu menerima koneksi simultan dari minimal 10 client TCP eksternal (misalnya dijalankan via utility command line `nc localhost 9999`).
3.  **Low-Latency Broadcasting Pipeline:**
    *   Server harus membaca tick dari Memory-Mapped File dan mengirimkannya ke seluruh client yang terhubung secara non-blocking.
    *   **Aturan Desain Zero-Allocation:** Dilarang mengalokasikan objek baru di Java Heap dalam loop pembacaan dan pengiriman data ke socket.
    *   Gunakan pooling direct buffer tunggal atau model circular ring buffer.
4.  **Metrik Performa:**
    *   Ukur dan cetak latensi rata-rata serta latensi P99 (dalam satuan microsecond/nanosecond) untuk memproses 1.000.000 data tick ke seluruh connected client.
    *   Pastikan alokasi memori heap JVM tetap datar (*flat memory line*, 0 byte per tick) selama proses transmisi berlangsung (dapat divalidasi via *VisualVM* atau *JConsole*).