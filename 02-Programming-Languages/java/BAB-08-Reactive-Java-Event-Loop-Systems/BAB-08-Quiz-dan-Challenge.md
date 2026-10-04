# BAB 08: Quiz, Challenge, & Knowledge Check
**Reactive Java & Event-Loop Systems**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dualitas Push-Pull Model dalam Reactive Streams Specification**
   Jelaskan secara arsitektural bagaimana Reactive Streams (Flow API di Java 9+) menggabungkan paradigma *push-based* (data-driven) dan *pull-based* (demand-driven) untuk mencapai mekanisme *backpressure* non-blocking. Mengapa model *pure push* (seperti Observer pattern konvensional) berpotensi fatal terhadap stabilitas memori aplikasi pada beban I/O tinggi?

2. **Perbedaan Fundamental Cold vs Hot Publisher**
   Bedakan semantik eksekusi antara *Cold Publisher* dan *Hot Publisher* pada Project Reactor (`Flux`/`Mono`). Bagaimana siklus hidup *subscription*, alokasi *upstream resource*, dan distribusi data terpengaruh ketika terdapat multi-subscriber pada masing-masing tipe publisher tersebut?

3. **Mekanika `publishOn` vs `subscribeOn`**
   Jelaskan secara mendalam perbedaan transmisi sinyal eksekusi saat menggunakan operator `subscribeOn(Scheduler)` dibandingkan `publishOn(Scheduler)`. Scheduler mana yang mengontrol thread eksekusi pada fase *assembly time*, *subscription time*, dan *runtime execution* (mulai dari source hingga subscriber terminal)?

4. **Anatomi dan Kontrak `Subscription.request(long n)`**
   Berdasarkan spesifikasi Reactive Streams Rule 3.x, bagaimana kontrak konkurensi diatur pada method `request(long n)`? Apa implikasinya terhadap *state management* internal publisher jika subscriber memanggil `request(Long.MAX_VALUE)` dibandingkan pemanggilan inkremental berbasis *batching* (`request(1)`)?

5. **Assembly Phase vs Execution Phase**
   Mengapa pembuatan rantai reaktif (pipeline chaining seperti `.map().filter().flatMap()`) tidak mengeksekusi komputasi apa pun sampai method `.subscribe()` dipanggil? Jelaskan implikasi performa dan memori dari pemisahan tegas antara *Assembly Time* dan *Execution Time* ini.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Event-Loop Exhaustion & Netty Worker Thread Poisoning**
   Pada framework berbasis Netty (misalnya Spring WebFlux / Reactor Netty), mengapa eksekusi satu pemanggilan *blocking I/O* (seperti `Thread.sleep()` atau JDBC query konvensional) di dalam operator reaktif dapat melumpuhkan throughput ratusan koneksi concurrent lainnya secara simultan? Jelaskan mekanismenya di level arsitektur thread pool Netty (`NioEventLoopGroup`).

2. **Dinamika Strategi Backpressure Drop, Buffer, dan Latest**
   Analisis skenario internal berikut: Publisher memproduksi 10.000 elemen/detik, sedangkan Downstream Subscriber hanya mampu mengonsumsi 50 elemen/detik. Bandingkan perilaku konsumsi memori (heap), latensi data, dan *loss tolerance* jika diterapkan strategi:
   - `onBackpressureBuffer(int maxSize, BufferOverflowStrategy.DROP_OLDEST)`
   - `onBackpressureDrop()`
   - `onBackpressureLatest()`

3. **Context Propagation vs ThreadLocal Dilemma**
   Mengapa pola desain `ThreadLocal` (yang umum digunakan pada Spring MVC/Security untuk menyimpan trace ID atau user context) mengalami *context loss* pada sistem reaktif? Bagaimana `reactor.util.context.Context` menyelesaikan masalah ini secara immutable, dan mengapa konteks tersebut harus dibaca dari *downstream* ke *upstream*?

4. **Troubleshooting Silent Pipeline Failure & Mono Cancellation**
   Diberikan sebuah pipeline:
   ```java
   Mono.fromCallable(() -> performExternalHttpCall())
       .timeout(Duration.ofMillis(500))
       .flatMap(response -> persistToDatabase(response))
       .doOnError(e -> log.error("Pipeline failed", e));
   ```
   Jika downstream memicu pembatalan (`cancel()`) atau terjadi timeout saat `performExternalHttpCall()` sedang berjalan, mengapa `persistToDatabase()` tidak pernah dieksekusi dan resource database pool connection bisa mengalami kebocoran jika tidak di-handle dengan benar? Bagaimana cara mengatasinya menggunakan operator `doOnCancel` atau `usingWhen`?

5. **`flatMap` Concurrency Prefetch & Ordering Anomalies**
   Secara *default*, operator `flatMap` pada Project Reactor memiliki parameter `concurrency` (32) dan `prefetch`. Jelaskan bagaimana operator ini menangani sub-stream `Publisher` yang di-*flatten*. Apa konsekuensi urutan emisi data (*ordering guarantee*) dibandingkan dengan `concatMap` dan `flatMapSequential`, serta bagaimana dampaknya terhadap footprint memori?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Failure Akibat Event-Loop Starvation pada Gateway Microservices
Sebuah API Gateway berbasis Spring Cloud Gateway (Reactor Netty) mengalami lonjakan drastis pada P99 latency dari 15ms menjadi 28.000ms. CPU usage server hanya berkisar 12%, namun koneksi incoming HTTP mengalami lonjakan timeout (HTTP 504) secara masif. Thread dump menunjukkan stack trace berikut pada seluruh thread `reactor-http-epoll-*`:
```
"reactor-http-epoll-4" #34 daemon prio=5 os_prio=0 cpu=12.45ms ...
   java.lang.Thread.State: WAITING (parking)
   at jdk.internal.misc.Unsafe.park(java.base@17.0.8/Native Method)
   at java.util.concurrent.locks.LockSupport.park(java.base@17.0.8/LockSupport.java:211)
   at java.util.concurrent.CompletableFuture$Signaller.block(java.base@17.0.8/CompletableFuture.java:1864)
   at java.util.concurrent.ForkJoinPool.unmanagedBlock(java.base@17.0.8/ForkJoinPool.java:3465)
   at java.util.concurrent.CompletableFuture.waitingGet(java.base@17.0.8/CompletableFuture.java:1898)
   at java.util.concurrent.CompletableFuture.get(java.base@17.0.8/CompletableFuture.java:2072)
   at com.bank.gateway.filter.AuthFilter.validateJwt(AuthFilter.java:45)
```
- **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah (*root cause*) dari insiden di atas berdasarkan stack trace tersebut! Mengapa utilisasi CPU tetap rendah padahal sistem mengalami kelumpuhan total?
  2. Bagaimana solusi refactoring arsitektural yang tepat tanpa merusak sifat non-blocking dari Netty EventLoop? 
  3. Mekanisme deteksi otomatis apa (misalnya BlockHound) yang harus dipasang pada CI/CD pipeline untuk mencegah regresi ini terulang?

### Skenario B: Race Condition dan State Corruption pada Shared Mutable State dalam Stream
Sebuah sistem agregasi transaksi finansial memproses event transaksi real-time menggunakan `Flux`:
```java
public class BalanceAggregator {
    private BigDecimal runningBalance = BigDecimal.ZERO; // Shared mutable state

    public Flux<BigDecimal> calculateBalances(Flux<Transaction> transactionFlux) {
        return transactionFlux
            .publishOn(Schedulers.boundedElastic())
            .map(tx -> {
                runningBalance = runningBalance.add(tx.getAmount());
                return runningBalance;
            });
    }
}
```
Ketika sistem diuji dengan 10.000 transaksi concurrent, total akhir saldo tidak deterministik dan selalu tidak sesuai dengan verifikasi database (inkonsistensi data).
- **Pertanyaan Diagnostik:**
  1. Mengapa thread safety terlanggar pada kode di atas, meskipun pipeline reaktif sering diasumsikan "thread-confined"?
  2. Bagaimana Anda mendesain ulang kalkulasi saldo tersebut secara murni fungsional (*functional pure*) menggunakan operator stateful seperti `scan()` atau `reduce()`, sehingga eliminasi mutabilitas dapat menjamin kebenaran matematis tanpa locking?

### Skenario C: Arsitektur & Trade-off: Project Reactor vs Spring MVC + Virtual Threads (Project Loom)
Sebuah bank digital sedang merancang arsitektur baru untuk sistem transfer antarbank berkapasitas 50.000 request/detik. Sistem ini murni I/O-bound (memanggil database via SQL, memanggil 3 microservices external via REST, dan mempublikasikan event ke Kafka).
Tim Engineering terbagi menjadi dua kubu:
- Kubu A: Mengusung arsitektur Full Reactive Stack (Spring WebFlux + R2DBC + Project Reactor).
- Kubu B: Mengusung arsitektur Tradisional Blokir diperbarui (Spring Boot 3 MVC + Virtual Threads Loom + HikariCP).
- **Pertanyaan Diagnostik:**
  1. Analisis perbandingan kedua pendekatan tersebut ditinjau dari:
     - Kompleksitas kognitif / *maintainability* kode (debugging, stack traces, testing).
     - Overhead memori per koneksi concurrent.
     - *Backpressure management* dari client hingga layer database.
  2. Dalam skenario spesifik apa Project Reactor **tetap mutlak lebih unggul** dibandingkan Virtual Threads, dan dalam kondisi apa Virtual Threads membuat penggunaan Project Reactor menjadi *over-engineering* yang tidak perlu?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Resilient Event Gateway dengan Dynamic Backpressure & Context Tracing

#### Deskripsi Masalah:
Anda diminta membangun komponen core routing untuk sebuah API Gateway pembayaran. Gateway ini harus menerima stream transaksi berkecepatan tinggi, memvalidasi token keamanan, menerapkan rate-limiting berbasis windowing, mengalirkan downstream ke backend banking legacy yang lambat, serta mendukung context tracing (Distributed Trace ID) tanpa kehilangan konteks di sepanjang asynchronous hop.

#### Persyaratan Fungsional & Teknis:
1. **Source Stream Simulation**: Buat producer yang memancarkan `PaymentEvent` secara dinamis (hingga 2.000 req/sec) yang disimulasikan via `Flux.generate()` atau `Flux.create()`.
2. **Dynamic Context Injection**: Setiap transaksi yang masuk harus diberi `traceId` (UUID) yang diinjeksikan ke dalam `Mono/Flux` Reactor Context. Trace ID ini harus dapat diakses pada operator logging downstream tanpa di-passing sebagai argumen method.
3. **Resilient Rate-Limiting & Backpressure Handling**:
   - Backend target legacy hanya mampu memproses maksimal **100 req/sec**.
   - Jika downstream backend mulai kewalahan (terdeteksi dari *latency spike* > 200ms), pipeline gateway harus secara otomatis beralih menampung maksimal 500 antrean di memory buffer (`onBackpressureBuffer`). Jika buffer penuh, transaksi yang berlebih harus di-drop dengan fallback audit record khusus (`onBackpressureDrop`).
4. **Non-Blocking Concurrency Throttling**:
   - Eksekusi transmisi ke backend legacy menggunakan `flatMap` dengan konkurensi terkontrol (maksimal 10 concurrent requests).
   - Jangan gunakan `Thread.sleep()` atau synchronous network mock; gunakan delay non-blocking (`Mono.delay()`).
5. **Error & Timeout Boundary**:
   - Jika backend legacy tidak merespons dalam durasi 300ms, terapkan timeout non-blocking dan kembalikan response fallback `PaymentStatus.GATEWAY_TIMEOUT`.
   - Pipeline tidak boleh berhenti (*terminate*) saat ada error transaksi tunggal; error harus diisolasi di level event.

#### Batasan Implementasi:
- **Zero Imperative Loops**: Dilarang menggunakan loop imperatif (`for`, `while`) atau primitif sinkronisasi manual (`synchronized`, `ReentrantLock`).
- **Zero Thread-Blocking**: Pipeline harus 100% lulus audit non-blocking (simulasikan BlockHound compatibility).
- **Pure Functional Transformations**: Hindari *shared mutable variables* di luar pipeline context.

#### Expected Output:
Kode Java murni yang siap dieksekusi (dapat berupa unit test berbasis `StepVerifier` atau runner class mandiri) yang memvalidasi bahwa:
1. Trace ID konsisten tercetak pada console log dari awal hingga akhir event diproses.
2. Backpressure buffer tidak meledak (`OutOfMemoryError`) saat producer dipacu pada 2.000 req/sec.
3. Transaksi yang timeout atau gagal terisolasi tanpa merusak *stream subscription* transaksi berikutnya.
4. Total execution metrics menunjukkan throughput stabil sesuai batasan downstream downstream throttle.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Kontrak dasar Reactive Streams: 4 interfaces utama (`Publisher`, `Subscriber`, `Subscription`, `Processor`) dan aturan interaksinya.
- [ ] Perbedaan eksekusi semantik antara `Mono` (0 atau 1 elemen) dan `Flux` (0 hingga N elemen tak terbatas).
- [ ] Peran dan cara kerja internal Schedulers: `Schedulers.immediate()`, `Schedulers.single()`, `Schedulers.boundedElastic()`, dan `Schedulers.parallel()`.
- [ ] Alasan mendasar mengapa blocking operations dilarang keras di thread Netty EventLoop (`reactor-http-epoll-*`).
- [ ] Cara kerja Reactor `Context` untuk propagasi state transaksional/tracing lintas thread pool tanpa `ThreadLocal`.
- [ ] Operator handling konkurensi: `flatMap` vs `concatMap` vs `flatMapSequential` vs `switchMap`.
- [ ] Strategi mitigasi overflow data: `BUFFER`, `DROP`, `LATEST`, dan `ERROR`.
- [ ] Trade-off fundamental antara Reactive Streams (Push-Pull Backpressure, Flow Control) dengan Virtual Threads/Project Loom (Blocking-style I/O Concurrency).

### Saya tidak perlu menghafal:
- [ ] Ratusan variasi nama operator transformatif obscure di Project Reactor (cukup pahami katalog operator inti: transform, filter, combine, time-based, error handling).
- [ ] Detail implementasi bit-shift ring buffer pada `RingBuffer` internal LMAX Disruptor/Netty ByteBuf optimizations.
- [ ] Konfigurasi parameter low-level OS native epoll/kqueue transport (kecuali saat melakukan fine-tuning Linux kernel khusus produksi).

### Saya harus bisa melakukan:
- [ ] Menganalisis *thread dump* untuk mendeteksi event-loop starvation dan melacak asal pemanggilan blocking I/O di dalam stack reaktif.
- [ ] Mengonfigurasi dan mengintegrasikan BlockHound ke dalam test suite enterprise untuk mendeteksi blocking call secara otomatis.
- [ ] Melakukan debugging pipeline reaktif menggunakan operator `.checkpoint()`, `.log()`, dan `Hooks.onOperatorDebug()`.
- [ ] Menulis integration test non-blocking end-to-end yang tangguh menggunakan `StepVerifier` dan `TestPublisher` dengan manipulasi virtual time (`StepVerifier.withVirtualTime`).
- [ ] Mentransformasi API berbasis callback atau imperative synchronous legacy menjadi clean non-blocking Publisher menggunakan `Mono.create()`, `Flux.create()`, atau `Mono.fromCallable()`.