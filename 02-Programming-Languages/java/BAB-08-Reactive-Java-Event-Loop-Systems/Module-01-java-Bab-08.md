# SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kategori** | `02-Programming-Languages` |
| **Jalur Pembelajaran** | Advanced Java Engineering |
| **Modul** | `Bab 08 Module 01: Reactive Java & Event-Loop Systems` |
| **Tingkat Kesulitan** | Advanced / Production-Grade |
| **Prasyarat** | Java Core Concurrency (Thread, ExecutorService, CompletableFuture), Java NIO (Selectors, Channels, Buffers), Basic Networking (TCP/IP, HTTP) |
| **Target Ekosistem** | JDK 21+, Project Reactor 3.6+, Netty 4.1+, Spring WebFlux |
| **Estimasi Waktu Belajar** | 8 - 10 Jam Pembelajaran Intensif |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan** model konkurensi Thread-per-Request (imperatif) versus Asynchronous Non-blocking Event-Loop (reaktif) berdasarkan utilisasi memori kernel, context switching overhead, dan skalabilitas I/O.
2. **Menguasai Spesifikasi Reactive Streams** (`Publisher`, `Subscriber`, `Subscription`, `Processor`) serta mekanisme *pull-push backpressure* untuk mencegah degradasi sistem akibat producer-consumer mismatch.
3. **Mengonstruksi Pipeline Reaktif Kompleks** menggunakan Project Reactor (`Mono` dan `Flux`), menerapkan operator transformasi, filtering, error handling, serta orkestrasi paralel.
4. **Mengisolasi dan Mengontrol Thread Execution Context** secara presisi menggunakan `publishOn()` dan `subscribeOn()` dengan konfigurasi `Scheduler` yang tepat (Parallel vs BoundedElastic).
5. **Mendeteksi dan Memitigasi Masalah Event-Loop Blocking** menggunakan tooling diagnostik otomatis (*BlockHound*) dan mematuhi aturan strict zero-blocking pada Netty I/O threads.
6. **Merancang dan Mengimplementasikan Layanan Reaktif End-to-End** yang resilient dengan pola retry exponential backoff, rate limiting, circuit breaker, dan integrasi context propagation yang aman.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Imperatif ke Reaktif

Dalam model pemrograman imperatif tradisional (Thread-per-Request), thread sistem operasi bertindak seperti seorang pelayan restoran yang berdiri diam di depan meja pelanggan menunggu pelanggan membaca menu, memilih, dan memutuskan makanan. Selama pelanggan berpikir (merepresentasikan *I/O latency*, seperti query database atau panggilan API eksternal), pelayan (Thread) tersebut diblokir (*blocked*), tidak dapat melayani meja lain, namun tetap mengonsumsi memori stack (standar 1MB per thread di JVM) dan membebani OS scheduler dengan context switching.

```
Model Tradisional (Thread-per-Request):
[Request 1] ───> [OS Thread 1] ───> [Block on DB] (Idle, memori tertahan) ───> [Response 1]
[Request 2] ───> [OS Thread 2] ───> [Block on API] (Idle, memori tertahan) ──> [Response 2]
Keterbatasan: Jumlah koneksi konkuren dibatasi oleh jumlah OS Thread maksimum.
```

Dalam paradigma **Reactive Event-Loop Systems**, mental model berubah menjadi arsitektur berbasis event sinkronous/asinkronous dengan thread minimal yang konstan:

1. **Pelayan Non-Blocking (Event-Loop Thread):** Pelayan mencatat pesanan segera setelah siap, menyerahkannya ke dapur (I/O multiplexer / OS Kernel via `epoll` atau `kqueue`), lalu seketika berpindah melayani meja lain.
2. **Koleksi Callback & State Machine:** Ketika dapur menyelesaikan makanan (I/O event selesai: data socket siap dibaca/ditulis), OS memberi notifikasi ke event-loop. Event-loop mengeksekusi pipeline komputasi lanjutan tanpa memblokir thread.
3. **Backpressure sebagai Kontrak:** Konsumen memiliki hak penuh untuk menentukan seberapa banyak data yang sanggup diproses (`request(n)`). Produser dilarang membanjiri konsumen di luar kapasitas penyimpanannya.

```
Model Reaktif Event-Loop (Non-Blocking):
[Req 1] ┐
[Req 2] ┼─> [Event Loop (1 CPU Core = 1 Thread)] ──> [Daftarkan I/O ke Kernel epoll]
[Req 3] ┘        │                                                │
                 ├── Melayani ribuan event secara instan ─────────┘ (Data Ready)
                 └── Menjalankan callback komputasi lanjutan
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur reactive system bertumpu pada interaksi antara **Netty EventLoopGroup**, **Reactive Streams Engine (Project Reactor)**, dan **Operating System Multiplexing (epoll/kqueue/select)**.

```
+---------------------------------------------------------------------------------------+
|                                OPERATING SYSTEM KERNEL                                |
|             [Socket Channels]  <--->  [Multiplexer: epoll / kqueue]                   |
+------------------------------------------▲--------------------------------------------+
                                           │ Readiness Events (EPOLLIN, EPOLLOUT)
+------------------------------------------▼--------------------------------------------+
|                                  NETTY EVENT LOOP LAYER                               |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                          EventLoopGroup (Worker Pool)                         |   |
|   |                                                                               |   |
|   |   +-------------------------+            +-------------------------+          |   |
|   |   |       EventLoop 1       |            |       EventLoop N       |          |   |
|   |   |  [Task Queue] [Selector]|            |  [Task Queue] [Selector]|          |   |
|   |   +------------┬------------+            +-------------------------+          |   |
+---|----------------│------------------------------------------------------------------|---+
    │                ▼ Pipeline Data Processing                                         │
+---|-----------------------------------------------------------------------------------|---+
|   │                       PROJECT REACTOR EXECUTION PIPELINE                          │
|   │                                                                                   |
|   │   Publisher (Flux/Mono)                                                           |
|   │       │                                                                           |
|   │       ├─► .map()               [Dijalankan di Netty EventLoop Thread]             |
|   │       ├─► .filter()            [Dijalankan di Netty EventLoop Thread]             |
|   │       │                                                                           |
|   │       ├─► .publishOn(Schedulers.boundedElastic())                                 |
|   │       │         │                                                                 |
|   │       │         ▼                                                                 |
|   │       ├─► .flatMap(blockingIOWorker) [Dikerjakan Worker Thread Terpisah]          |
|   │       │         │                                                                 |
|   │       ▼         ▼                                                                 |
|   │   Subscriber (Custom / Netty Outbound Writer)                                     |
|   │       │                                                                           |
|   │       └── request(n) (Mekanisme Backpressure Pull-Push)                           |
|   |                                                                                   |
+---+-----------------------------------------------------------------------------------+
```

### Siklus Hidup Aliran Data & Backpressure

```
Subscriber                    Subscription                     Publisher
    │                              │                               │
    ├────────── subscribe() ───────┼──────────────────────────────>│
    │                              ├──── onSubscribe(sub) ────────>│
    │<── onSubscribe(Subscription)─┤                               │
    │                              │                               │
    ├─────── request(2) ──────────>│                               │
    │                              ├────── read demand (n=2) ─────>│
    │                              │<───── onNext(item 1) ─────────┤
    │<────── onNext(item 1) ───────┤                               │
    │                              │<───── onNext(item 2) ─────────┤
    │<────── onNext(item 2) ───────┤                               │
    │                              │                               │
    ├─────── request(1) ──────────>│                               │
    │                              │<───── onNext(item 3) ─────────┤
    │<────── onNext(item 3) ───────┤                               │
    │                              │<───── onComplete() ───────────┤
    │<────── onComplete() ─────────┤                               │
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur 4 Interface Inti Reactive Streams (Specification v1.0.4)

Semua engine reaktif berbasis JVM (Project Reactor, RxJava, Akka/Pekko Streams) mengimplementasikan 4 kontrak dasar yang didefinisikan dalam paket `org.reactivestreams`:

```java
public interface Publisher<T> {
    void subscribe(Subscriber<? super T> s);
}

public interface Subscriber<T> {
    void onSubscribe(Subscription s);
    void onNext(T t);
    void onError(Throwable t);
    void onComplete();
}

public interface Subscription {
    void request(long n);
    void cancel();
}

public interface Processor<T, R> extends Subscriber<T>, Publisher<R> {
}
```

### 2. Mekanisme Internal Dynamic Demand (Backpressure Math)
Secara internal, `Subscription` mengelola counter demand asinkronus (biasanya menggunakan bit-field atomik atau `AtomicLongFieldUpdater`). 
* Ketika konsumen memanggil `request(n)`, variabel atomic demand ditambahkan: $\text{demand} = \text{demand} + n$.
* Setiap kali produser mengeksekusi `onNext(data)`, demand didekrementasi: $\text{demand} = \text{demand} - 1$.
* Jika $\text{demand} == 0$, produser wajib menahan laju emisi data (*suspend* emisi atau simpan ke buffer internal).
* Jika produser memanggil `onNext` ketika $\text{demand} == 0$, sistem akan melempar `IllegalStateException` ("Queue is full" / "Spec violation: Can't emit without demand") atau memicu strategi `OverflowException`.

### 3. Netty Event-Loop Anatomy
* **Single-Thread Execution Model per Loop:** Satu instance `NioEventLoop` memiliki satu thread OS yang didedikasikan sepenuhnya. Thread ini berjalan dalam infinite loop:
  $$\text{select()} \rightarrow \text{processSelectedKeys()} \rightarrow \text{runAllTasks()}$$
* **Channel Registration:** Puluhan ribu socket connection (Channel) didaftarkan ke satu `Selector` yang sama di dalam satu `NioEventLoop`.
* **Zero Thread-Contention:** Komputasi yang terikat pada channel tertentu selalu dieksekusi oleh EventLoop yang sama. Tidak ada *synchronization locks* antar thread untuk channel yang sama.
* **Golden Rule of Event Loop:** **DILARANG KERAS** memblokir thread Event-Loop. Pemanggilan method seperti `Thread.sleep()`, JDBC standar (blocking), parsing berkas disk secara sinkron, atau algoritma komputasi CPU intensif akan langsung membekukan penanganan puluhan ribu koneksi lain yang terikat pada loop tersebut.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Project Reactor: `Mono` vs `Flux`
Project Reactor adalah implementasi reaktif generasi ke-4 yang dibangun di atas Reactive Streams dan dioptimalkan secara mendalam untuk arsitektur JVM modern:
* **`Mono<T>`:** Merepresentasikan stream asinkronus yang menghasilkan **0 atau 1 elemen**, kemudian selesai via `onComplete()` atau gagal via `onError()`. Setara konseptual dengan non-blocking `Optional<CompletableFuture<T>>`.
* **`Flux<T>`:** Merepresentasikan stream asinkronus yang menghasilkan **0 hingga N elemen** (bisa berhingga atau tak terhingga), diakhiri oleh sinyal penyelesaian atau kegagalan.

### Thread Switching: `publishOn` vs `subscribeOn`
Memahami perbedaan titik eksekusi adalah aspek paling kritis dalam arsitektur reaktif:

```
Assembly Time: Saat deklarasi operator chain dibuat (Mono.just().map()...) -> Dilakukan sekali di main/setup thread.
Subscription Time: Saat .subscribe() dipanggil -> Sinyal mengalir UPSTREAM (bawah ke atas).
Execution Time: Saat data dialirkan via onNext() -> Sinyal mengalir DOWNSTREAM (atas ke bawah).
```

* **`subscribeOn(Scheduler s)`:**
  * Mempengaruhi thread yang digunakan untuk memproses seluruh siklus hidup subscription, bergerak **ke hulu (upstream)** hingga ke titik publisher pertama.
  * Hanya pemanggilan `subscribeOn` pertama (paling dekat dengan Publisher) yang memiliki pengaruh dominan terhadap sumber stream data.
* **`publishOn(Scheduler s)`:**
  * Mempengaruhi thread yang digunakan untuk mengeksekusi semua operator **ke hilir (downstream)** setelah titik deklarasi `publishOn`.
  * Dapat dideklarasikan berulang kali dalam satu rantai untuk memindahkan alur komputasi antar pool thread yang berbeda.

### Tipologi Schedulers
1. `Schedulers.immediate()`: Menjalankan eksekusi pada thread aktif saat itu juga (no-op context switch).
2. `Schedulers.single()`: Satu reusable single-thread pool. Bagus untuk komputasi berurutan berbobot rendah.
3. `Schedulers.parallel()`: Kumpulan thread berukuran tetap sejumlah CPU Core ($N$). Dikhususkan untuk **komputasi CPU-bound murni** (misal kalkulasi kriptografi, pemrosesan citra/JSON dalam memori).
4. `Schedulers.boundedElastic()`: Dynamic thread pool yang otomatis meluas (default: $10 \times \text{CPU Core}$, antrian task hingga 100.000). Didesain eksplisit untuk **isolasi I/O blocking legacy** (misal JDBC, legacy REST API clients, blocking file system).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fondasi Reactive Streams murni menggunakan Project Reactor. Kode ini mendemonstrasikan pembuatan pipeline, pengendalian backpressure kustom, thread scheduling, dan error recovery.

```java
package com.architect.reactive.fundamental;

import reactor.core.publisher.Flux;
import reactor.core.publisher.BaseSubscriber;
import reactor.core.publisher.SignalType;
import reactor.core.scheduler.Schedulers;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ThreadLocalRandom;

public class ReactiveFundamentalDemo {

    public static void main(String[] args) throws InterruptedException {
        CountDownLatch completionLatch = new CountDownLatch(1);

        System.out.println("[MAIN] Thread entry: " + Thread.currentThread().getName());

        Flux<Integer> telemetryStream = Flux.range(1, 20)
                .map(id -> {
                    // Mensimulasikan data telemetry
                    System.out.println("[GENERATE] Item: " + id + " | Thread: " + Thread.currentThread().getName());
                    return id;
                })
                .subscribeOn(Schedulers.single()) // Upstream dieksekusi pada scheduler single
                .filter(id -> id % 2 == 0)        // Mengambil hanya angka genap
                .publishOn(Schedulers.parallel()) // Downstream dipindahkan ke parallel scheduler
                .map(id -> {
                    // Simulasi pemrosesan CPU-bound
                    System.out.println("[PROCESS] Item: " + id + " | Thread: " + Thread.currentThread().getName());
                    return id * 10;
                })
                .publishOn(Schedulers.boundedElastic()) // Beralih ke pool I/O
                .flatMap(id -> simulateExternalIoCall(id)); // FlatMap untuk operasi asinkronus berikutnya

        // Mengonsumsi stream dengan Custom Subscriber untuk mengontrol Backpressure secara granular
        telemetryStream.subscribe(new BaseSubscriber<String>() {
            private int consumedElements = 0;
            private static final int BATCH_SIZE = 2;

            @Override
            protected void hookOnSubscribe(org.reactivestreams.Subscription subscription) {
                System.out.println("[SUBSCRIBER] Subscribed. Requesting initial batch: " + BATCH_SIZE);
                request(BATCH_SIZE); // Permintaan demand awal
            }

            @Override
            protected void hookOnNext(String value) {
                consumedElements++;
                System.out.println("[SUBSCRIBER] Received: " + value + " | Thread: " + Thread.currentThread().getName());

                // Strategi Backpressure: Tarik data berikutnya saat batch terpenuhi
                if (consumedElements % BATCH_SIZE == 0) {
                    System.out.println("[SUBSCRIBER] Batch processed. Requesting next batch: " + BATCH_SIZE);
                    request(BATCH_SIZE);
                }
            }

            @Override
            protected void hookOnError(Throwable throwable) {
                System.err.println("[SUBSCRIBER] Error encountered: " + throwable.getMessage());
                completionLatch.countDown();
            }

            @Override
            protected void hookOnFinally(SignalType type) {
                System.out.println("[SUBSCRIBER] Pipeline terminated with signal: " + type);
                completionLatch.countDown();
            }
        });

        // Menunggu seluruh proses asinkronus selesai sebelum main thread mati
        completionLatch.await();
    }

    private static Flux<String> simulateExternalIoCall(Integer input) {
        return Flux.defer(() -> {
            int latency = ThreadLocalRandom.current().nextInt(50, 150);
            try {
                // Simulasi blocking latency yang diisolasi di boundedElastic
                Thread.sleep(latency);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return Flux.error(e);
            }
            return Flux.just("PAYLOAD_TRANS_ID-" + input + "_ACK");
        });
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis kritis terhadap kode implementasi Seksi 07:

1. **`Flux.range(1, 20)`**: Operator factory pembuat Publisher dingin (*cold publisher*) yang akan menghasilkan stream integer berurutan dari 1 sampai 20 saat ada demand.
2. **`.subscribeOn(Schedulers.single())`**: Memerintahkan pipeline dari hulu (`range` dan `map` pertama) untuk berjalan pada satu thread khusus terdedikasi (`single-*`). Walaupun di-*subscribe* dari `main`, emisi data dimulai dari context thread ini.
3. **`.publishOn(Schedulers.parallel())`**: Memotong context thread downstream. Segala operator yang berada persis di bawah baris ini (`filter` evaluasi, `map` komputasi) akan dieksekusi oleh pool thread `parallel-*` yang cocok untuk manipulasi CPU.
4. **`.publishOn(Schedulers.boundedElastic())`**: Pemotongan context kedua. Mengalihkan alur eksekusi berikutnya ke thread pool elastis yang dirancang khusus mentoleransi latency pemanggilan blocking.
5. **`.flatMap(id -> simulateExternalIoCall(id))`**: Mengubah elemen `Integer` menjadi `Publisher` baru secara dinamis, lalu menggabungkan (*merge*) kembali emisi Publisher tersebut ke dalam satu stream utama tanpa blocking.
6. **`extends BaseSubscriber<String>`**: Menggunakan kelas abstraksi bawaan Reactor untuk kontrol presisi terhadap sinyal `Reactive Streams`. Menghindari penggunaan default `subscribe()` tanpa demand boundary.
7. **`hookOnSubscribe(...)`**: Dieksekusi seketika saat publisher menerima subscription. Di sini kita tidak memanggil `requestUnbounded()`, melainkan secara sengaja mengirim sinyal demand terkontrol `request(2)`.
8. **`hookOnNext(...)`**: Titik tangkap item data yang diterima downstream. Terdapat dynamic batching: setelah memproses 2 item, subscriber meminta 2 item tambahan (`request(BATCH_SIZE)`).
9. **`Flux.defer(...)`**: Memastikan bahwa pemanggilan `Thread.sleep` (atau kode I/O blocking) dievaluasi secara dinamis secara per-subscription, bukan saat pembuatan rantai operator (assembly-time).

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Payment Gateway Webhook Ingestion Engine
Perusahaan Fintech Skala Besar memproses hingga **50.000 requests/detik** pada endpoint webhook notifikasi transaksi dari bank dan payment partners. 

#### Tantangan Lapangan:
1. **Spike Traffic Ekstrem:** Trafik datang secara *bursty* selama event promosi (*flash sale*).
2. **Downstream Bottleneck:** Bank Partner A lambat dalam merespons konfirmasi tanda terima (waktu respons 300ms - 2000ms).
3. **Sistem Imperatif Mengalami Collapse:** Arsitektur lama berbasis Spring MVC + Tomcat (Thread-per-request) mengalami thread exhaustion seketika: pool sebesar 200 thread habis terpakai dalam hitungan 200ms saat ada lonjakan 1000 request masuk, menyebabkan error `HTTP 503 Service Unavailable` dan connection drop massal.
4. **Kebutuhan:** Sistem harus menerima payload dengan latensi masuk $<10\text{ms}$, menerapkan *in-flight queueing* dengan kendali backpressure, memvalidasi HMAC secara non-blocking di CPU-core, menulis log audit secara asinkronus ke persistent layer, dan membatasi koneksi ke bank mitra agar tidak mengalami rate-limit.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem ingestion transaksi berskala produksi menggunakan arsitektur Reactive Java dengan Project Reactor. Sistem ini mencakup *buffer throttling*, *rate-limiting*, fallback mechanism, dan context propagation.

```java
package com.architect.reactive.production;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.util.context.Context;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public class ProductionPaymentIngestionEngine {

    // Monitoring metrics internal
    private static final AtomicLong PROCESSED_COUNTER = new AtomicLong(0);
    private static final AtomicLong DROPPED_COUNTER = new AtomicLong(0);

    public record PaymentWebhookPayload(
            String transactionId,
            String merchantId,
            double amount,
            String signature,
            long timestamp
    ) {}

    public record ProcessingResult(
            String transactionId,
            String status,
            String executionThread,
            Instant processedAt
    ) {}

    public static void main(String[] args) throws InterruptedException {
        ProductionPaymentIngestionEngine engine = new ProductionPaymentIngestionEngine();

        // 1. Mensimulasikan sumber banjir data webhook (Burst 10.000 incoming requests)
        Flux<PaymentWebhookPayload> highThroughputStream = Flux.range(1, 10_000)
                .map(i -> new PaymentWebhookPayload(
                        UUID.randomUUID().toString(),
                        "MERCHANT_" + (i % 50),
                        150.00 + i,
                        "HMAC_SIGNATURE_MOCK_" + i,
                        System.currentTimeMillis()
                ));

        // 2. Mendaftarkan stream transaksi ke Ingestion Engine
        engine.processTransactionStream(highThroughputStream)
                .contextWrite(Context.of("TRACE_ID", UUID.randomUUID().toString()))
                .doOnNext(res -> {
                    long count = PROCESSED_COUNTER.incrementAndGet();
                    if (count % 1000 == 0) {
                        System.out.printf("[METRICS] Processed: %d events | Dropped: %d%n",
                                count, DROPPED_COUNTER.get());
                    }
                })
                .blockLast(); // Block hanya untuk demo runner lifecycle

        System.out.println("Processing Terminated. Final Processed: " + PROCESSED_COUNTER.get());
    }

    public Flux<ProcessingResult> processTransactionStream(Flux<PaymentWebhookPayload> inboundFlux) {
        return inboundFlux
                // Mitigasi Overpressure: Gunakan Backpressure Drop Strategy jika downstream tidak mampu
                .onBackpressureBuffer(
                        500, // Kapasitas buffer maksimal
                        droppedItem -> {
                            DROPPED_COUNTER.incrementAndGet();
                            System.err.println("[BACKPRESSURE DROP] Dropping transaction: " + droppedItem.transactionId());
                        }
                )
                // Isolasi validasi kriptografi ke pool parallel (CPU-Bound)
                .publishOn(Schedulers.parallel(), 128) // Prefetch 128 items
                .flatMap(payload -> validateCryptographicSignature(payload)
                        .filter(Boolean::booleanValue)
                        .map(valid -> payload)
                        .switchIfEmpty(Mono.error(new SecurityException("Invalid HMAC signature"))),
                        64 // Concurrency level untuk flatMap
                )
                // Isolasi persistensi database dan legacy bank API ke pool boundedElastic (I/O Bound)
                .publishOn(Schedulers.boundedElastic(), 128)
                .flatMap(validPayload -> executeDownstreamSettlement(validPayload)
                        // Ketahanan: Retry dengan Exponential Backoff + Jitter
                        .retryWhen(reactor.util.retry.Retry.backoff(3, Duration.ofMillis(50))
                                .maxBackoff(Duration.ofMillis(500))
                                .filter(ex -> !(ex instanceof SecurityException))
                        )
                        // Fallback jika bank downstream down total
                        .onErrorResume(ex -> fallbackDeadLetterQueue(validPayload, ex)),
                        32 // Konkurensi panggilan keluar dibatasi 32 untuk mencegah exhaust socket
                );
    }

    private Mono<Boolean> validateCryptographicSignature(PaymentWebhookPayload payload) {
        return Mono.deferContextual(ctxView -> {
            String traceId = ctxView.getOrDefault("TRACE_ID", "UNKNOWN");
            // Simulasi komputasi HMAC hash non-blocking
            boolean isValid = payload.signature() != null && payload.signature().startsWith("HMAC_");
            return Mono.just(isValid);
        });
    }

    private Mono<ProcessingResult> executeDownstreamSettlement(PaymentWebhookPayload payload) {
        return Mono.deferContextual(ctxView -> {
            String traceId = ctxView.getOrDefault("TRACE_ID", "UNKNOWN");
            
            // Mensimulasikan latensi jaringan I/O yang fluktuatif ke bank
            long simulatedLatency = 10 + (long)(Math.random() * 40);
            
            return Mono.delay(Duration.ofMillis(simulatedLatency))
                    .thenReturn(new ProcessingResult(
                            payload.transactionId(),
                            "SETTLED",
                            Thread.currentThread().getName(),
                            Instant.now()
                    ));
        });
    }

    private Mono<ProcessingResult> fallbackDeadLetterQueue(PaymentWebhookPayload payload, Throwable cause) {
        return Mono.fromCallable(() -> {
            // Simulasi penyimpanan lokal ke fail-safe disk queue / Kafka DLQ
            return new ProcessingResult(
                    payload.transactionId(),
                    "FAILED_QUEUED_DLQ: " + cause.getMessage(),
                    Thread.currentThread().getName(),
                    Instant.now()
            );
        }).subscribeOn(Schedulers.boundedElastic());
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Arsitektur sistem memiliki kompromi desain yang mendasar. Pemilihan paradigma harus disesuaikan dengan profil beban kerja (*workload profile*).

| Parameter Evaluasi | Imperatif Tradisional (Spring MVC + Tomcat) | Reaktif Asinkron (Project Reactor + Netty) | Virtual Threads (Java 21+ Project Loom) |
| :--- | :--- | :--- | :--- |
| **Model Threading** | 1 OS Thread = 1 Request | Few Event-Loops ($N$ Cores) melayani $M$ Request | Jutaan Virtual Thread dipetakan ke Carrier Thread |
| **Memory Footprint** | Sangat Tinggi (~1MB per Thread Stack) | Minimum (~beberapa KB per koneksi/state) | Rendah (~beberapa ratus byte per Virtual Thread) |
| **Throughput (I/O Bound)** | Terbatas oleh OS Thread Limit (~2k-5k threads) | Sangat Tinggi ($100k+$ concurrent connections) | Sangat Tinggi ($100k+$ concurrent connections) |
| **CPU Bound Performance** | Bagus, mudah didistribusikan per core | Membutuhkan dispatch eksplisit ke thread pool terpisah | Rentan *Carrier Thread Pinning* jika ada native/sync lock |
| **Kompleksitas Koding** | Rendah (Gaya sekuensial, blocking intuitif) | **Sangat Tinggi** (Monadic thinking, callback chain, non-blocking mindset) | Rendah (Menjaga gaya imperatif prosedural) |
| **Kemudahan Debugging** | Sangat Mudah (Stacktrace linear, local state jelas) | **Sangat Sulit** (Stacktrace terfragmentasi antar tick event loop) | Mudah (Stacktrace linear utuh preserved) |
| **Ecosystem Maturity** | Matang Sepenuhnya (Semua library Java kompatibel) | Parsial (Hanya untuk library dengan driver non-blocking R2DBC, WebClient) | Matang untuk sebagian besar library, terus beradaptasi |

### Kapan Menggunakan Reaktif (Project Reactor / Netty)?
1. Membutuhkan penanganan ratusan ribu koneksi konkuren berdaya tahan lama (e.g., Streaming Gateway, WebSocket Server, IoT Ingestion Hub).
2. Memerlukan kendali **Backpressure yang nyata dan matematis** antarkomponen terdistribusi.
3. Seluruh dependensi eksternal (driver database, HTTP client, message broker) sudah memiliki driver asinkron/non-blocking native.

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **The Phantom Infinite Flow (Hung Pipeline):**
   * *Gejala:* Pipeline terhenti total, data tidak terkirim, tidak ada exception yang muncul di log.
   * *Akar Masalah:* Subscriber tidak memanggil sinyal demand (`request(n)`), atau lupa men-subscribe (`Mono`/`Flux` bersifat dingin (*cold*) secara default—jika tidak ada `.subscribe()`, **tidak ada kode yang dijalankan**).
2. **Event-Loop Thread Pinning:**
   * *Akar Masalah:* Menjalankan method sinkronous/blocking di dalam pipeline tanpa `publishOn()`.
   ```java
   // PETAKA BESAR: Mematikan seluruh throughput Netty
   flux.map(data -> restTemplate.getForObject(...)) // Blocking HTTP client
   ```
   * *Dampak:* Karena worker thread Netty biasanya sama dengan jumlah core CPU ($N$), $N$ pemanggilan serentak akan membekukan seluruh server untuk seluruh user.
3. **Out of Memory (OOM) via Unbounded Buffering:**
   * *Akar Masalah:* Menggunakan strategi backpressure buffer tanpa batas maksimum:
   ```java
   flux.onBackpressureBuffer() // Default parameter tanpa parameter limit!
   ```
   * Jika producer 10x lebih cepat daripada subscriber dalam durasi lama, JVM Heap akan meledak dalam hitungan menit.
4. **Context Loss Across Thread Boundaries:**
   * `ThreadLocal` **TIDAK BEKERJA** secara default di sistem reaktif karena satu stream berpindah-pindah thread selama eksekusinya. Penggunaan `SecurityContextHolder` atau SLF4J MDC bawaan akan menghasilkan `null` atau data tercampur antar user (*cross-contamination*).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. The Block-Inside-Reactive Mistake
```java
// SALAH (ANTI-PATTERN): Menghancurkan performa reaktif
public Mono<UserResponse> getUser(String id) {
    User user = databaseRepository.findById(id).block(); // JANGAN PERNAH MEMANGGIL .block()!
    return Mono.just(mapToResponse(user));
}

// BENAR: Pertahankan rantai asinkron
public Mono<UserResponse> getUser(String id) {
    return databaseRepository.findById(id)
            .map(this::mapToResponse);
}
```

### 2. Side-Effects dalam Operator Fungsional
```java
// SALAH: Mutasi state luar dari operator map/filter yang murni (pure)
List<String> results = new ArrayList<>();
flux.map(item -> {
    results.add(item); // Race condition! Bahaya konkurensi fatal
    return item;
}).subscribe();

// BENAR: Gunakan operator pengumpul fungsional
Mono<List<String>> results = flux.collectList();
```

### 3. Mengabaikan Sinyal Error (Silent Failures)
```java
// SALAH: Mengonsumsi data tanpa penanganan error
flux.subscribe(data -> process(data)); // Jika terjadi exception, pipeline mati diam-diam!

// BENAR: Selalu pasang handler error eksplisit
flux.subscribe(
    data -> process(data),
    error -> log.error("Pipeline failure: ", error),
    () -> log.info("Completed successfully")
);
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip "Hot vs Cold" Publisher:**
   * Pahami bahwa stream bersifat *Cold* (dimulai dari awal setiap ada subscriber baru) kecuali diubah secara eksplisit menjadi *Hot* (memancarkan data tanpa menunggu subscriber, e.g., via `.publish().refCount()` atau `.share()`).
2. **Defensive Scheduling:**
   * Selalu isolasi kode warisan (legacy JDBC, blocking SDKs) secara eksplisit menggunakan thread pool khusus:
   ```java
   Mono.fromCallable(() -> legacyBlockingCall())
       .subscribeOn(Schedulers.boundedElastic());
   ```
3. **Fail-Fast Backpressure Policy:**
   * Di layer arsitektur gerbang (edge/API gateway), gunakan strategi `onBackpressureDrop` atau batasi queue secara eksplisit (`onBackpressureBuffer(maxSize, BufferOverflowStrategy.DROP_OLDEST)`) untuk menjaga integritas memori server dari serangan DoS/spike.
4. **Context Propagation yang Benar:**
   * Gunakan Reactor Context API (`subscriberContext()` atau `ContextView`) untuk tracing/security, bukan `ThreadLocal`. Integrasikan `reactor-core-micrometer` untuk propagasi tracing transparan.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Prefetch Tuning
Operator seperti `publishOn`, `flatMap`, dan `concatMap` memiliki buffer prefetch internal (standar: 256 atau 32 item):
```java
// TUNE: Perkecil prefetch jika data payload berupa byte array besar untuk menghemat memori
flux.publishOn(Schedulers.parallel(), 16);
```

### 2. Hindari Over-allocation dengan FlatMap Concurrency
Secara default, `flatMap` mengonsumsi 256 publisher anak secara konkuren. Pada beban I/O tinggi, ini dapat membombardir downstream database hingga connection pool habis.
```java
// Batasi konkurensi flatMap ke angka proporsional
flux.flatMap(this::callExternalHttp, 16); // Maksimal 16 koneksi outbound bersamaan
```

### 3. Optimasi Zero-Copy ByteBuf Netty
Di sistem berbasis Netty/WebFlux, manfaatkan pembacaan langsung dari buffer network tanpa alokasi memori heap tambahan:
* Hindari konversi ke `String` atau `byte[]` jika tujuannya hanya mem-forward data ke socket/file lain. Gunakan `DataBufferUtils.retain()` dan `DataBufferUtils.release()`.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Backpressure Deny-of-Service Mitigation:**
   * Client berbahaya dapat sengaja mengirim payload besar secara perlahan (*Slowloris attack*) atau memicu eksekusi tanpa menarik downstream (*Zero-demand attack*).
   * **Mitigasi:** Pasang timeout global yang ketat di setiap langkah operator:
   ```java
   inboundFlux.timeout(Duration.ofSeconds(5))
              .onErrorResume(TimeoutException.class, e -> Mono.error(new CustomSecurityTimeoutException()));
   ```
2. **Information Disclosure in Reactive Stacktraces:**
   * Karena pipeline reaktif melintasi banyak thread, stacktrace dapat menjadi sangat panjang dan menampilkan detail internal framework secara masif ke output publik.
   * **Mitigasi:** Selalu sanitasi exception sebelum diteruskan ke HTTP response via `.onErrorMap()`.
3. **Thread Context Isolation Leak:**
   * Jangan menyimpan credential rahasia di mutable container statis di dalam pipeline. Konteks reaktif (`Context`) bersifat *immutable*, gunakan properti ini untuk mengamankan auth token secara terisolasi per subscriber execution chain.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Diagnostik Thread Blocking dengan BlockHound
BlockHound adalah Java agent yang memodifikasi bytecode JVM runtime untuk mendeteksi apakah ada pemanggilan blocking pada thread yang ditandai sebagai non-blocking (seperti worker thread Netty).

```java
// Inisialisasi pada bootstrap aplikasi (e.g., main method)
BlockHound.install();

// Uji coba: Ini akan seketika melempar BlockingOperationError saat runtime
Mono.delay(Duration.ofMillis(1))
    .doOnNext(it -> {
        try {
            Thread.sleep(10); // BlockHound langsung mendeteksi dan menghentikan eksekusi!
        } catch (InterruptedException e) {}
    }).subscribe();
```

### 2. Reactor Hooks Assembly Tracing
Stacktrace pada error reaktif seringkali tidak menunjukkan di mana rantai operator dideklarasikan dalam kode Anda.
```java
// Aktifkan hanya di environment DEVELOPMENT / DEBUG (overhead tinggi pada performa):
Hooks.onOperatorDebug();
```
Untuk production yang aman tanpa runtime overhead, gunakan bytecode injection tool: `io.projectreactor:reactor-tools`.

### 3. Logging Terstruktur dengan Operator `.tap()` dan `.doOnSignal()`
Hindari penggunaan `.doOnNext(System.out::println)` untuk logging. Gunakan logging non-blocking terstruktur:
```java
flux.doOnNext(item -> log.debug("Processing item ID: {}", item.getId()))
    .doOnError(err -> log.error("Pipeline crashed: ", err))
    .doOnCancel(() -> log.warn("Client canceled downstream connection"));
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Sinyal Inti Reactive Streams
* `onSubscribe(Subscription s)`: Panggilan pertama saat inisialisasi koneksi antara publisher dan subscriber.
* `onNext(T t)`: Pengiriman 1 unit data dari publisher ke subscriber.
* `onError(Throwable t)`: Sinyal terminal yang menyatakan pipeline gagal secara permanen.
* `onComplete()`: Sinyal terminal yang menyatakan seluruh data berhasil dikirim secara sukses.

### Schedulers Quick Reference

| Scheduler Method | Pool Size | Target Workload |
| :--- | :--- | :--- |
| `Schedulers.parallel()` | Fixed ($N$ = CPU Cores) | CPU-bound computation murni, hashing, parsing. |
| `Schedulers.boundedElastic()`| Dynamic (Max $10 \times \text{Core}$) | Blocking I/O legacy (JDBC, File system sinkron, HTTP SDK kuno). |
| `Schedulers.single()` | 1 Thread Reusable | Urutan sekuensial ringan, low-overhead scheduling. |
| `Schedulers.immediate()` | 0 (Current Thread) | Langsung dieksekusi tanpa thread jump. |

### Cheatsheet Operator Utama

```
Mono.just(val)              -> Emisi nilai tunggal seketika.
Mono.defer(() -> ...)       -> Lazy evaluation pembuat Mono per-subscriber.
Flux.fromIterable(list)     -> Stream dari Collection standar.
.map(fn)                    -> Transformasi 1-to-1 sinkronous.
.flatMap(fn)                -> Transformasi 1-to-N asinkronous (merging non-deterministic).
.concatMap(fn)              -> Transformasi 1-to-N asinkronous berurutan (deterministic order).
.publishOn(sched)           -> Mengubah execution context downstream ke scheduler baru.
.subscribeOn(sched)         -> Menentukan execution context hulu (upstream source).
.onErrorResume(fallback)    -> Tangkap exception dan alihkan ke publisher alternatif.
.retryWhen(Retry.backoff()) -> Retry cerdas dengan interval dinamis.
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian 1: Basic (Pilihan Ganda)

1. **Apa yang terjadi secara internal jika sebuah `Publisher` memanggil `.subscribe()` namun subscriber tidak pernah memanggil `Subscription.request(n)`?**
   * A. Publisher langsung mengalirkan data tanpa batas.
   * B. Terjadi `OutOfMemoryError` seketika.
   * C. Data tidak akan dialirkan sama sekali karena subscriber belum menyatakan demand-nya.
   * D. Publisher secara otomatis membatalkan (*cancel*) subscription setelah 5 detik.

2. **Perbedaan fundamental antara `Mono` dan `Flux` dalam Project Reactor adalah:**
   * A. Mono hanya berjalan pada satu thread, sedangkan Flux berjalan paralel.
   * B. Mono merepresentasikan stream 0..1 elemen, sedangkan Flux merepresentasikan 0..N elemen.
   * C. Mono digunakan khusus I/O blocking, sedangkan Flux non-blocking.
   * D. Flux tidak mendukung backpressure, sedangkan Mono mendukungnya.

3. **Scheduler mana yang secara arsitektural dirancang untuk mengisolasi pemanggilan legacy database JDBC yang masih bersifat blocking?**
   * A. `Schedulers.parallel()`
   * B. `Schedulers.immediate()`
   * C. `Schedulers.boundedElastic()`
   * D. `Schedulers.single()`

4. **Kapan sebenarnya perakitan operator pipeline (`.map()`, `.filter()`) dieksekusi oleh runtime?**
   * A. Saat Assembly-Time (seketika baris kode deklarasi dibaca oleh thread pemanggil).
   * B. Hanya saat `onComplete()` dipanggil.
   * C. Saat data pertama kali masuk ke network card.
   * D. Secara berkala via Garbage Collector background cycle.

5. **Apa efek negatif langsung jika developer memanggil `Thread.sleep(2000)` di dalam operator `.map()` yang dieksekusi pada Netty Event-Loop thread?**
   * A. Hanya request milik user tersebut yang tertunda selama 2 detik.
   * B. Seluruh ratusan hingga ribuan koneksi client lain yang terikat pada event loop tersebut ikut terhenti total selama 2 detik.
   * C. Netty akan secara otomatis membunuh thread tersebut dan membuat thread baru.
   * D. Sistem operasi akan mengabaikan thread sleep tersebut secara otomatis.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus)

6. **Diberikan rantai kode berikut:**
   ```java
   Flux.range(1, 10)
       .subscribeOn(Schedulers.single())   // Baris 2
       .subscribeOn(Schedulers.parallel()) // Baris 3
       .map(i -> i * 2)
       .subscribe();
   ```
   **Thread pool manakah yang akan mengeksekusi operasi `Flux.range` di atas?**
   * A. `Schedulers.parallel()` karena dideklarasikan terakhir.
   * B. `Schedulers.single()` karena pemanggilan `subscribeOn` pertama yang paling dekat ke arah Publisher yang mengendalikan titik subscription awal.
   * C. Thread `main` tempat kode dideklarasikan.
   * D. Terjadi runtime collision dan melemparkan `IllegalStateException`.

7. **Operator manakah yang HARUS dipilih jika urutan emisi data downstream wajib sama persis dengan urutan request upstream pada transformasi publisher asinkron?**
   * A. `.flatMap()`
   * B. `.concatMap()`
   * C. `.parallelMap()`
   * D. `.mergeMap()`

8. **Mengapa tool logging MDC (Mapped Diagnostic Context) SLF4J standar gagal menampilkan ID korelasi (e.g., `traceId`) secara konsisten pada arsitektur Spring WebFlux murni?**
   * A. Karena library SLF4J tidak mendukung Java versi baru.
   * B. Karena MDC bertumpu pada `ThreadLocal`, sementara eksekusi pipeline reaktif melintasi batas thread yang berbeda-beda (*thread hopping*).
   * C. Karena Event-Loop menonaktifkan fitur output I/O konsol.
   * D. Karena WebFlux menghapus memori stack secara otomatis setiap 100ms.

9. **Strategi mitigasi backpressure `onBackpressureDrop()` paling tepat diimplementasikan pada skenario:**
   * A. Transaksi finansial penarikan saldo rekening bank.
   * B. Aliran telemetry GPS sensor IoT frekuensi tinggi, di mana kehilangan satu titik sampel lebih dapat diterima daripada server mengalami Crash/OOM.
   * C. Penyimpanan log audit kepatuhan regulasi legal.
   * D. Parsing berkas konfigurasi XML aplikasi saat booting.

10. **Apa fungsi utama dari library BlockHound dalam ekosistem Reactive Java?**
    * A. Menghitung penggunaan memori heap subscriber secara real-time.
    * B. Mengonversi query SQL blocking menjadi non-blocking otomatis via AI.
    * C. Mendeteksi pemanggilan method blocking pada thread non-blocking saat runtime dan memicu error diagnostik.
    * D. Mengamankan endpoint HTTP dari serangan distributed brute force.

---

### Kunci Jawaban Kuis

1. **C** — Sesuai spesifikasi Reactive Streams, produser tidak boleh memancarkan data sebelum subscriber menyatakan demand via `request(n)`.
2. **B** — Mono dibatasi untuk emisi 0 atau 1 nilai terminal, Flux untuk urutan arbitrary 0 sampai N nilai.
3. **C** — `Schedulers.boundedElastic()` diciptakan eksplisit untuk menampung pemblokiran thread dengan pool dinamis yang terikat batas aman.
4. **A** — Rantai deklarasi dibangun di Assembly-time; eksekusi data yang sebenarnya baru terjadi setelah titik Subscription-time.
5. **B** — Event Loop bersifat single-thread multiplexed; jika satu thread loop diblokir, semua channel yang terdaftar pada selector loop tersebut membeku.
6. **B** — Sinyal `subscribeOn` bergerak ke hulu (*upstream*), sehingga deklarasi `subscribeOn` paling atas/awal yang memenangkan context kontrol publisher.
7. **B** — `.concatMap()` menunggu publisher asinkronus sebelumnya selesai (`onComplete`) sebelum men-subscribe yang berikutnya, menjamin preservation urutan.
8. **B** — Mekanisme `ThreadLocal` tidak kompatibel dengan paradigma switching thread reaktif; solusinya menggunakan Reactive Streams Context.
9. **B** — Data metrik/telemetry realtime bersifat loss-tolerant demi mempertahankan stabilitas sistem utama.
10. **C** — BlockHound menggunakan instrumentasi bytecode untuk memonitor thread blocking (seperti sleep, socket read sinkron) pada thread bertanda non-blocking.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "High-Frequency Crypto Order-Book Aggregator & Matching Gateway"

#### Deskripsi Sistem:
Rancang dan bangun sebuah komponen backend mikro berbasis Java 21 dan Project Reactor yang mengonsumsi aliran order transaksi perdagangan dari 3 bursa simulasi yang berbeda, memproses verifikasi batas risiko, dan mengalirkannya ke Matching Engine internal.

#### Persyaratan Fungsional & Teknis:
1. **Multi-Source Ingestion:**
   * Buat minimal 3 Publisher `Flux<OrderEvent>` yang memancarkan order beli/jual secara independen dengan delay fluktuatif (10 - 100ms).
   * Gabungkan ketiga stream tersebut menjadi satu stream terpadu menggunakan operator `Flux.merge()` atau `Flux.combineLatest()`.
2. **Backpressure Enforced Consumer:**
   * Buat `Custom Subscriber` yang menerapkan **Dynamic Demand Batching**:
     * Minta 50 order di awal.
     * Evaluasi latency pemrosesan lokal. Jika processing time di bawah ambang batas (e.g., $<5\text{ms}$), tingkatkan demand batch berikutnya menjadi 100 (adaptive scaling).
     * Jika terjadi lonjakan antrian, terapkan `onBackpressureBuffer(1000, BufferOverflowStrategy.DROP_OLDEST)`.
3. **Thread Context Isolation Strict Rule:**
   * Aliran masuk simulasi bursa berjalan di `Schedulers.parallel()`.
   * Eksekusi "Risk Assessment Analysis" (CPU-bound) dieksekusi pada `Schedulers.parallel()`.
   * Eksekusi "Database Audit Order Log" yang disimulasikan sebagai operasi blocking lambat ($100\text{ms}$) **WAJIB** diisolasi pada `Schedulers.boundedElastic()`.
4. **Resiliency & Diagnostics:**
   * Pasang integrasi **BlockHound** di unit test untuk memvalidasi bahwa tidak ada thread Netty/Parallel yang tersentuh oleh method blocking buatan Anda.
   * Pasang timeout 5 detik pada tiap partition batching, dan retry otomatis maksimal 3 kali jika salah satu bursa simulasi menghasilkan sinyal network drop.
5. **Kriteria Kelulusan Proyek:**
   * Menjalankan stress test pemrosesan 100.000 order tanpa melemparkan `OutOfMemoryError`.
   * BlockHound tidak melempar `BlockingOperationError`.
   * Semua order yang berhasil diproses tercatat dengan identifier transaksi dan identifier nama thread eksekusi yang sesuai dengan layer schedulernya masing-masing.