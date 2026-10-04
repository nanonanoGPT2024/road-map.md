# BAB 04: Quiz, Challenge, & Knowledge Check
**I/O, Networking & Low-Latency Data Processing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Abstraksi OS Syscall: BIO vs. NIO**  
   Jelaskan secara mendalam perbedaan transisi eksekusi thread dan context switch pada level Kernel OS saat sebuah thread Java mengeksekusi operasi baca data melalui blocking I/O (`InputStream.read()`) dibandingkan dengan non-blocking NIO (`SocketChannel.read()` yang terdaftar pada `Selector` berbasis `epoll`/`kqueue`). Mengapa arsitektur blocking I/O thread-per-connection gagal melakukan scaling linear ketika menangani ratusan ribu koneksi konkuren (*C10k/C1000k problem*)?

2. **Invarian Buffer dan Mekanisme Mutasi State**  
   Pada Java NIO `Buffer`, jelaskan relasi matematis ketat antara `mark`, `position`, `limit`, dan `capacity`. Jelaskan mutasi state yang terjadi pada pointer-pointer tersebut ketika berturut-turut dieksekusi pemanggilan method: `allocate()`, `put()`, `flip()`, `get()`, `compact()`, dan `clear()`. Mengapa kegagalan memanggil `flip()` sebelum membaca data dari buffer menghasilkan bug pembacaan data corrupt atau `BufferUnderflowException`?

3. **Direct Buffer vs. Heap Buffer & Buffer Pinning**  
   Bandingkan alokasi memori internal antara `ByteBuffer.allocate()` (Non-Direct/Heap) dan `ByteBuffer.allocateDirect()` (Direct/Off-Heap). Jelaskan mengapa JVM terpaksa membuat salinan memori sementara (*temporary direct buffer*) di belakang layar saat melakukan I/O operasi via Heap Buffer, dan bagaimana Direct Buffer mengeliminasi penalti ini serta dampaknya terhadap Garbage Collection pressure.

4. **Arsitektur Zero-Copy via DMA Engine**  
   Analisis alur data dan context switch CPU dari pemanggilan `FileChannel.transferTo()` yang memanfaatkan syscall `sendfile()`. Bandingkan diagram jalur data tersebut dengan transfer data konvensional (menggunakan loop `read()` ke byte array lalu `write()` ke socket), tinjau peran *Direct Memory Access* (DMA) engine, CPU copy, serta eliminasi duplikasi data pada Kernel Buffer dan Socket Buffer.

5. **Trade-Off Protokol Serialisasi pada Low-Latency Critical Path**  
   Mengapa implementasi `java.io.Serializable` standar dianggap sebagai anti-pattern mutlak pada sistem finansial berlatensi rendah (*low-latency trading*)? Jelaskan komparasi arsitektural antara mekanisme Java Native Reflection Serialization dengan framework zero-copy/flat binary seperti SBE (*Simple Binary Encoding*) atau FlatBuffers dari sudut pandang alokasi memori, traversal pointer (*cache locality*), dan decoding footprint.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi Java NIO Epoll Spin Bug**  
   Pada Linux OS, jelaskan bagaimana Java NIO `Selector` berinteraksi dengan kernel syscall `epoll_create`, `epoll_ctl`, dan `epoll_wait`. Bedah akar masalah dari bug legendaris *JDK-6670302 (epoll CPU 100% spin)*: kondisi kernel apa yang menyebabkannya, bagaimana loop event-polling terjebak dalam busy-waiting tanpa event I/O nyata, dan bagaimana framework seperti Netty memitigasi bug ini secara programatis sebelum JVM merilis fix?

2. **Diagnostik OutOfMemoryError: Direct Buffer Memory**  
   Sebuah aplikasi microservice mengalami crash fatal dengan pesan:  
   `java.lang.OutOfMemoryError: Direct buffer memory`, namun metrik monitoring menunjukkan JVM Old Gen heap usage hanya terisi 25%.  
   * Bongkar lifecycle dari `DirectByteBuffer`, peran `sun.misc.Cleaner` (atau `java.lang.ref.Cleaner`), serta ketergantungannya pada GC untuk mendealokasi native memory.
   * Mengapa opsi JVM `-XX:+DisableExplicitGC` dapat secara ironis memicu crash OOM ini lebih cepat?
   * Perintah diagnostics profiling apa (native memory tracking/async-profiler) yang harus Anda jalankan untuk memetakan alokasi off-heap yang tidak ter-free?

3. **Optimasi TCP Socket: Nagle’s Algorithm vs. Delayed ACK**  
   Jelaskan interaksi buruk yang terjadi antara Nagle's Algorithm (aktif secara default pada socket OS) dan mekanisme TCP *Delayed ACK* pada arsitektur komunikasi data request-response berbasis paket kecil. Opsi socket apa (`StandardSocketOptions`) yang harus diaktifkan pada `SocketChannel` Java untuk menghentikan latensi buatan ini, dan apa trade-off jaringan (bandwidth vs packet headers overhead) yang harus Anda bayar?

4. **Memory-Mapped Files (`MappedByteBuffer`) dan Eliminasi Page Faults**  
   Pada arsitektur persistence log berkecepatan tinggi, pemanggilan `FileChannel.map()` memetakan file disk langsung ke address space proses virtual memory.  
   * Jelaskan perbedaan antara *Minor Page Fault* dan *Major Page Fault* saat mengakses byte pertama dari halaman memori yang belum termuat di RAM.
   * Teknik pre-touching atau native call apa (`madvise(MADV_WILLNEED)`, `mlock`) yang dapat Anda panggil dari Java untuk mencegah engine terkena latency spikes pada hot path transaksi?

5. **False Sharing dan Cache Line Padding pada I/O Ring Buffer**  
   Dalam implementasi antrean I/O berbasis shared-memory multithreaded (seperti LMAX Disruptor ring buffer), jelaskan fenomena *False Sharing* pada level arsitektur hardware L1/L2/L3 cache line (standar 64-byte). Tunjukkan bagaimana compiler Java mengoptimasi layout objek, dan bagaimana anotasi `@jdk.internal.vm.annotation.Contended` atau explicit variable padding manual memecahkan race invalidasi cache line antar inti CPU.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes P99 pada High-Throughput API Gateway
* **Konteks:** Sistem API Gateway berbasis Java mengarahkan traffic sebesar 120.000 RPS. Saat traffic melonjak, latensi P50 tetap normal di 1.5ms, tetapi latensi P99 dan P99.9 meledak hingga 1.800ms. CPU utilization server melonjak ke 98%, tetapi bukan karena komputasi payload, melainkan metric OS mencatat **voluntary context switches** menembus angka jutaan per detik.
* **Gejala:** Thread dump menunjukkan 1.500 thread berstatus `TIMED_WAITING` dan `WAITING` pada thread pool executor internal, serta ratusan thread `BLOCKED` saat mencoba menulis telemetry logging ke socket menggunakan logging framework sinkron tradisional.
* **Pertanyaan Diagnostik:**
  1. Identifikasi kegagalan arsitektur konkurensi I/O yang menyebabkan ledakan context switches tersebut.
  2. Rancang ulang arsitektur I/O gateway tersebut menggunakan model non-blocking event-loop (Reactor pattern). Komponen NIO apa yang harus Anda terapkan untuk membatasi jumlah worker thread agar sama dengan jumlah core CPU fisik?
  3. Bagaimana strategi backpressure yang harus Anda implementasikan pada TCP level (`channel.isWritable()`) untuk mencegah Out of Memory ketika upstream client mengirim request lebih cepat daripada kemampuan downstream service memprosesnya?

### Skenario B: Torn Reads & Data Corruption pada Shared-Memory Trading Engine
* **Konteks:** Sebuah matching engine mengekspos market data ke analytical engine di node yang sama menggunakan IPC via off-heap memory buffer (`DirectByteBuffer` / Shared Memory). Writer thread menulis snapshot orderbook (berisi `orderId: long`, `price: double`, `quantity: long`), sementara beberapa concurrent Reader threads membaca data tersebut secara terus-menerus tanpa menggunakan explicit lock mutex (`synchronized` atau `ReentrantLock`) demi mengejar target latensi eksekusi sub-mikrodetik.
* **Gejala:** Secara berkala, analytics engine menangkap nilai `price` yang valid tetapi berpasangan dengan `quantity` dari order yang berbeda atau data setengah tertulis (*torn reads*), yang menyebabkan kesalahan fatal pada kalkulasi algorithmic trading.
* **Pertanyaan Diagnostik:**
  1. Secara mekanika Java Memory Model (JMM) dan arsitektur hardware CPU memory reordering, jelaskan mengapa pembacaan tanpa lock pada field-field berukuran 64-bit dapat menghasilkan *torn reads* atau pembacaan instruksi yang out-of-order.
  2. Tanpa menggunakan locking mutual exclusion yang memblokir thread, desain skema sinkronisasi *lock-free* menggunakan `VarHandle` (atau `sun.misc.Unsafe`) dengan implementasi semantic *Acquire-Release* atau *Sequence Lock (SeqLock)* pattern. Tunjukkan bagaimana Reader mendeteksi bahwa data sedang ditulis oleh Writer sehingga Reader dapat membatalkan pembacaan kotor tersebut.

### Skenario C: Dilema Zero Data Loss (RPO=0) vs. Microsecond Latency pada Write-Ahead-Log
* **Konteks:** Anda adalah Principal Architect yang merancang Write-Ahead-Log (WAL) untuk engine pembayaran terdesentralisasi. Regulasi mengharuskan sistem menjamin *Zero Data Loss* (RPO=0) jika terjadi hardware failure (mesin mati mendadak atau power-loss). Beban sistem adalah 200.000 mutasi ledger per detik, dengan SLA latensi per transaksi maksimal 200 mikrodetik.
* **Gejala:** Tim engineering mencoba mengimplementasikan `FileChannel.force(true)` (syscall `fsync`) pada setiap transaksi penulisan. Akibatnya, throughput hancur ke level 1.200 transaksi per detik dengan latensi per transaksi melonjak ke 8-15 milidetik karena keterbatasan fisik I/O disk NVMe flush cycle.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa pemanggilan `FileChannel.force(true)` sinkron per request secara fundamental merusak latensi sistem pada level storage controller dan volatile page cache.
  2. Rancang arsitektur I/O hybrid yang memadukan teknik *Group Commit*, off-heap ring buffer, dan non-volatile memory (Direct I/O atau PMEM via Project Panama Foreign Function & Memory API) yang memungkinkan pencapaian throughput 200k ops/sec dengan jaminan persistensi data tanpa mengeksekusi `fsync` per-request secara naif.
  3. Jelaskan trade-off antara parameter `force(true)` (flush data + metadata) versus `force(false)` (flush data only) dari sisi integritas partisi sistem file OS saat terjadi hard power cut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Ultra-Low-Latency Ring Buffer IPC (Inter-Process Communication)
* **Problem:** Anda diminta membangun library Java I/O internal untuk pertukaran pesan antar dua proses Java yang berjalan pada mesin bare-metal Linux yang sama. Mekanisme komunikasi TCP Loopback (`localhost:8080`) ditolak oleh komite arsitektur karena menelan latensi rata-rata 12–25 mikrodetik dengan jitter P99 di atas 100 mikrodetik akibat TCP stack overhead. Anda harus menciptakan IPC berbasis **Off-Heap Shared Memory-Mapped File** yang memiliki karakteristik sub-microsecond latency (< 1 µs) dan Zero Garbage Allocation pada critical path.
* **Requirements:**
  1. **Lock-Free Circular Ring Buffer:** Bangun implementasi Single-Producer Single-Consumer (SPSC) Ring Buffer di atas `MappedByteBuffer` (atau via Project Panama `MemorySegment`).
  2. **Zero Allocation Data Path:** Serialisasi dan deserialisasi payload menggunakan pendekatan *Flyweight Pattern* (membaca dan menulis langsung dari/ke memory offset tanpa membuat object `byte[]`, `String`, atau wrapper object lainnya). Alokasi memori pada hot loop harus **0 byte/op**.
  3. **Memory Visibility & Ordering:** Implementasikan synchronization protocol tanpa lock menggunakan `VarHandle` (atau `sun.misc.Unsafe`) dengan semantik `getAcquire()` dan `setRelease()` untuk mengontrol tail dan head pointer agar tidak terjadi race condition dan instruksi tidak di-reorder oleh compiler/CPU.
  4. **Micro-Benchmarking:** Buat harness benchmark komprehensif menggunakan **JMH (Java Microbenchmark Harness)** yang mengukur *throughput* dan *single-shot round-trip latency*.
* **Constraints:**
  * Heap profiling menggunakan async-profiler atau `-XX:+PrintGCDetails` harus membuktikan tidak ada satupun aktivitas Garbage Collection (Minor/Major GC) selama proses transfer 10.000.000 pesan berjalan.
  * Ukuran cache line alignment: Header dan pointer head/tail harus dipisahkan dengan padding 64 byte untuk mencegah false sharing.
  * Target latensi: P99 Round-Trip Time (RTT) IPC < 2.0 mikrodetik pada hardware modern.
* **Expected Output:**
  * Modul kode fungsional: `SharedMemoryRingBufferWriter.java`, `SharedMemoryRingBufferReader.java`, dan `FlyweightMessageAccessor.java`.
  * Laporan eksekusi JMH yang mencakup tabel distribusi latensi persentil: P50, P90, P99, P99.9, dan throughput (ops/sec).
  * Log eksekusi GC yang memvalidasi `0 allocations` selama running test loop.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan internal mekanisme Kernel I/O Multiplexing (`select` vs `poll` vs `epoll`/`kqueue`) dan bagaimana Java NIO `Selector` merepresentasikan abstraksi ini.
- [ ] Alur lifecycle `ByteBuffer` (Heap vs Direct) serta formula transisi pointer: `position`, `limit`, `capacity`, dan `mark`.
- [ ] Mekanisme Kernel Zero-Copy (`sendfile`, `splice`, DMA transfer) dan bagaimana `FileChannel.transferTo()` bekerja melewati memory user space.
- [ ] Memory-Mapped I/O (`MappedByteBuffer`, Virtual Memory Pages, Page Faults, dan Dirty Page Flushes).
- [ ] Karakteristik Latency vs Throughput pada tuning TCP Socket Options (`TCP_NODELAY`, `SO_RCVBUF`, `SO_SNDBUF`, `SO_REUSEADDR`, `SO_LINGER`).
- [ ] Dampak arsitektur hardware CPU (Cache Lines, False Sharing, Store Buffers, Memory Barriers) terhadap desain I/O concurrency berlatensi rendah.
- [ ] Kelemahan Java Native Serialization dan keunggulan skema Zero-Copy Binary Encoding (SBE, Agrona DirectBuffer, FlatBuffers).
- [ ] Batasan garbage collection pada high-throughput networking dan strategi mitigasi zero-allocation (Buffer Pooling, Object Recycling, Off-Heap storage).

### Saya tidak perlu menghafal:
- [ ] Nomor byte spesifik atau opcode internal binary framing protokol Java Serialization standar.
- [ ] Nilai konstanta numerik integer dari file descriptor Linux syscall (misal nilai hex untuk flag `O_DIRECT`, `O_SYNC`, `epoll_ctl` constants).
- [ ] Implementasi internal kode C native JDK (JNI) untuk setiap platform operating system secara detail baris per baris.
- [ ] Urutan parameter lengkap dari native function call POSIX (`mmap`, `madvise`, `sysconf`) selama memahami abstraksi API-nya di Java.

### Saya harus bisa melakukan:
- [ ] Membangun echo/messaging server non-blocking murni menggunakan Java NIO Core (`ServerSocketChannel`, `SocketChannel`, `Selector`, `SelectionKey`) tanpa framework eksternal.
- [ ] Mendeteksi dan mendiagnosis memory leak pada Direct Memory (`sun.misc.Cleaner`, off-heap native memory tracking via NMT / `jcmd VM.native_memory baseline`).
- [ ] Memetakan file disk berukuran multi-gigabyte menggunakan `FileChannel.map()` dan memanipulasi isinya secara acak dengan proteksi zero-allocation.
- [ ] Menulis harness JMH yang tepat untuk mengukur latensi I/O dalam orde nanodetik/mikrodetik tanpa terkena bias JVM JIT optimization (*dead code elimination*, *constant folding*).
- [ ] Melakukan tuning TCP socket connection pool untuk mengeliminasi tail-latency spikes pada downstream integration API.
- [ ] Mengimplementasikan flyweight pattern data access menggunakan `VarHandle` atau Project Panama Foreign Function & Memory API untuk membaca binary struct off-heap tanpa alokasi object.