# Kurikulum Rekayasa Perangkat Lunak Enterprise: Java
## Kategori: 02-Programming-Languages
### BAB-03: Java Concurrency & Multithreading Mendalam
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memitigasi Anomali Java Memory Model (JMM):** Mengidentifikasi relasi *happens-before*, efek *hardware memory reordering*, *cache coherence protocol (MESI)*, serta mengeliminasi masalah *false sharing* menggunakan memory layout optimization.
2. **Merancang Custom Synchronization Primitives:** Mengimplementasikan sinkronisasi non-blocking dan blocking tingkat lanjut memanfaatkan `AbstractQueuedSynchronizer` (AQS), `VarHandle`, dan instruksi CPU Atomic (*Compare-And-Swap* / CAS).
3. **Mengoptimalkan Concurrency Read-Intensive & Parallel Workload:** Menerapkan `StampedLock` dengan *optimistic read validation*, serta mendesain algoritma komputasi berbasis `ForkJoinPool` dengan eksploitasi penuh teknik *work-stealing*.
4. **Membangun Arsitektur Asinkron Skala Enterprise:** Mengorkestrasi distributed non-blocking workflows menggunakan `CompletableFuture` dengan isolasi `ExecutorService` kustom yang terukur (bounded, backpressure-aware).
5. **Mengintegrasikan Concurrency Modern (Java 21+ Virtual Threads):** Menentukan batas arsitektural antara platform thread, thread pooling konvensional, dan Virtual Threads (Project Loom), serta menghindari *carrier thread pinning* dan *thread starvation*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Java Fundamentals & Core Concurrency (Bab 03 - Modul 01):** Siklus hidup `Thread`, *intrinsic locking* (`synchronized`), `volatile` dasar, serta `java.util.concurrent.Executors`.
*   **Arsitektur Komputer & CPU Caching:** Pemahaman hierarki memori (L1, L2, L3 cache, main memory), register CPU, dan instruksi mesin tingkat rendah.
*   **Struktur Data Lanjutan:** Antrean berbobot (*priority queue*), *doubly linked list*, operasi *bitwise*, dan *state-machine*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Java Memory Model (JMM), Hardware Reality, dan Cache Coherence

Di level perangkat keras modern, multi-core CPU tidak mengakses memori utama secara langsung untuk setiap instruksi karena latensi RAM (50–100 ns) jauh lebih lambat dibanding siklus CPU (< 1 ns). Tiap *core* memiliki cache lokal (L1i/L1d, L2) dan berbagi L3 cache.

```
+-------------------------------------------------------------------+
|                        Main Memory (DRAM)                         |
+-------------------------------------------------------------------+
                                  ^
                                  | Interconnect Bus (MESI Snooping)
                                  v
+---------------------------------+---------------------------------+
|            Core 0               |             Core 1              |
|  +---------------------------+  |  +---------------------------+  |
|  |         L3 Cache          |  |  |         L3 Cache          |  |
|  +---------------------------+  |  +---------------------------+  |
|  |         L2 Cache          |  |  |         L2 Cache          |  |
|  +---------------------------+  |  +---------------------------+  |
|  |  L1 Data   |  L1 Inst     |  |  |  L1 Data   |  L1 Inst     |  |
|  +---------------------------+  |  +---------------------------+  |
|  | Store Buffer / Registers  |  |  | Store Buffer / Registers  |  |
+---------------------------------+---------------------------------+
```

##### Protokol MESI & Memory Barriers
Setiap *cache line* (biasanya 64 bytes) berada dalam salah satu status protokol MESI:
*   **Modified (M):** Hanya ada di cache core lokal, bernilai kotor (*dirty*), belum ditulis ke RAM.
*   **Exclusive (E):** Hanya ada di cache core lokal, bersih (*clean*), sama dengan RAM.
*   **Shared (S):** Tersedia di beberapa cache core, bersih, siap dibaca.
*   **Invalid (I):** Data tidak lagi valid akibat core lain melakukan mutasi.

Untuk memaksimalkan *throughput*, CPU menggunakan **Store Buffers** dan **Invalidation Queues**. Operasi *write* tidak langsung disiarkan ke *bus*, melainkan masuk ke *store buffer*. Hal ini memicu fenomena **Memory Reordering** (Store-Load, Store-Store, Load-Load, Load-Store reordering).

JMM menjembatani arsitektur CPU yang berbeda (x86 TSO vs ARM/PowerPC weakly ordered) dengan mendefinisikan relasi formal **Happens-Before (HB)**:
*   *Program Order Rule:* Setiap aksi dalam satu thread terjadi sebelum aksi berikutnya berdasarkan urutan program.
*   *Monitor Lock Rule:* Pelepasan kunci (*unlock*) pada monitor terjadi sebelum penguncian (*lock*) berikutnya pada monitor yang sama.
*   *Volatile Variable Rule:* Operasi *write* pada field `volatile` terjadi sebelum operasi *read* berikutnya pada field yang sama. Di balik layar, JVM mengeluarkan instruksi CPU barrier (misal: `mfence` atau `lock addl` pada x86; `dmb` pada ARM) untuk menguras (*flush*) *store buffer* dan menginvalidasi cache core lain.
*   *Transitivity:* Jika $HB(A, B)$ dan $HB(B, C)$, maka $HB(A, C)$.

##### False Sharing & `@Contended`
Karena granularity sinkronisasi hardware berbasis *cache line* (64 bytes), dua variabel independen yang dimutasi oleh dua thread berbeda pada dua core terpisah dapat berada dalam satu *cache line* yang sama. Mutasi variabel A di Core 0 akan memicu invalidasi seluruh *cache line* di Core 1 yang sedang memproses variabel B. Efek ini disebut **False Sharing**, yang dapat menurunkan performa hingga 90%. JVM memitigasi ini secara eksplisit dengan padding memori atau anotasi `-XX:-RestrictContended` dan `@jdk.internal.vm.annotation.Contended`.

#### 3.2 Lock-Free Engineering: CAS, VarHandle, & Algoritma Non-Blocking

Operasi locking konvensional berbasis kernel context switch memicu latensi tinggi (1.000–10.000 siklus CPU). Pendekatan *lock-free* mengandalkan instruksi atomik hardware: **Compare-And-Swap (CAS)**.

CAS menerima tiga argumen: alamat memori ($V$), nilai ekspektasi lama ($A$), dan nilai baru ($B$). Instruksi mesin (seperti `CMPXCHG` di arsitektur x86) akan secara atomik memeriksa apakah $V == A$. Jika benar, $V$ diubah menjadi $B$ dan mengembalikan status *success*; jika salah, operasi dibatalkan (*failure*) tanpa memblokir thread.

##### Dari `sun.misc.Unsafe` ke `java.lang.invoke.VarHandle`
Di Java 9+, manipulasi memori tingkat rendah dialihkan secara resmi dari `Unsafe` ke `VarHandle`. `VarHandle` menyediakan akses terstandarisasi dengan kontrol mode akses memori yang granular:
*   *Plain:* Akses normal tanpa memory barrier (mirip field non-volatile).
*   *Opaque:* Menjamin keutuhan bit (tidak terbelah pada 64-bit value) dan program order per-thread, tanpa cross-thread ordering.
*   *Acquire/Release:* Menjamin ordering satu arah (Acquire mencegah load reordering setelahnya; Release mencegah store reordering sebelumnya).
*   *Volatile:* Full barrier ordering dua arah (sequential consistency).

#### 3.3 AbstractQueuedSynchronizer (AQS) Internals

`AbstractQueuedSynchronizer` adalah fondasi di balik `ReentrantLock`, `CountDownLatch`, `Semaphore`, dan `ReentrantReadWriteLock`. 

AQS mengelola sinkronisasi menggunakan:
1.  **Status Sinkronisasi Atomik (`state`):** Bilangan integer 32-bit `volatile` yang dimutasi via CAS. Maknanya bervariasi: pada `ReentrantLock`, state merepresentasikan kedalaman reentrancy; pada `Semaphore`, state merepresentasikan jumlah *permit* yang tersisa.
2.  **Antrean FIFO CLH Variant:** Antrean doubly-linked list yang terdiri dari instance `Node`. Node merepresentasikan thread yang terblokir dan menunggu giliran (*parked* menggunakan `LockSupport.park()`).
3.  **Condition Queue:** S單 linked list tambahan di dalam `ConditionObject` untuk mendukung semantik *wait/notify*.

```
           AQS Architecture (CLH Lock Queue Variant)
           
         +---------------------------------------+
         | volatile int state (State Variable)   |
         +---------------------------------------+
                            |
                            v
       +------+  prev   +------+  prev   +------+
Head ->| Node |<--------| Node |<--------| Node | <- Tail
       |      |-------->|      |-------->|      |
       +------+  next   +------+  next   +------+
       (Dummy/Acquired)  (Thread A)       (Thread B)
                         WaitStatus:      WaitStatus:
                         SIGNAL (-1)      SIGNAL (-1)
```

Alur Akuisisi Kunci Eksklusif pada AQS:
1.  Thread mencoba mutasi atomik `compareAndSetState(0, 1)`.
2.  Jika gagal, metode `acquire(1)` memanggil implementasi `tryAcquire(int)`.
3.  Bila `tryAcquire` bernilai `false`, thread dibungkus ke dalam `Node.EXCLUSIVE`, lalu disisipkan ke ekor (*tail*) antrean via loop CAS (`enq()`).
4.  Thread masuk ke loop antrean: jika node-nya berada tepat di belakang `head`, thread mencoba `tryAcquire` kembali. Jika kembali gagal, status node pendahulu diset ke `Node.SIGNAL` (-1), dan thread di-suspend menggunakan `LockSupport.park(this)`.
5.  Saat pemegang kunci memanggil `release(1)` -> `tryRelease()`, status dikembalikan ke 0, dan unpark dilakukan pada node penerus langsung (`head.next`).

#### 3.4 ForkJoinPool & Work-Stealing Algorithm

Tidak seperti `ThreadPoolExecutor` konvensional yang membagi satu antrean tunggal (`BlockingQueue`) ke semua worker thread—sehingga rawan konkurensi tinggi pada ekor antrean—`ForkJoinPool` menerapkan pendekatan terdesentralisasi:
*   Tiap worker thread memiliki antrean lokal ganda: **Double-Ended Queue (Deque)**.
*   **Push & Pop (LIFO):** Thread pemilik memasukkan sub-task hasil `fork()` dan mengeksekusinya dari bagian ujung bawah (*bottom*) antrean. Pendekatan LIFO mempertahankan data tetap panas di L1/L2 cache (data locality).
*   **Steal (FIFO):** Ketika thread kehabisan task lokal, ia bertindak sebagai pencuri (*thief*) dan mengambil task dari ujung atas (*top*) deque milik thread worker lain secara FIFO. Strategi FIFO memastikan task yang dicuri adalah unit kerja terbesar yang belum terbagi.

```
       ForkJoinPool: Work-Stealing Internals
       
       Worker Thread 1                    Worker Thread 2
      +-----------------+                +-----------------+
      | Push/Pop (LIFO) |                | Push/Pop (LIFO) |
      +-----------------+                +-----------------+
              |                                  |
              v                                  v
       +-------------+                    +-------------+
Top -> | SubTask 1.1 | (Stolen via FIFO)  | SubTask 2.1 | <- Top
       +-------------+   ^                +-------------+
       | SubTask 1.2 |   |                | SubTask 2.2 |
       +-------------+   |                +-------------+
Btm -> | SubTask 1.3 |   | Steal Action   |             | <- Btm
       +-------------+   |                +-------------+
              ^          |                       |
              |          +-----------------------+
      Local execution
```

#### 3.5 Modern Concurrency: Platform Threads vs Virtual Threads (Project Loom)

*   **Platform Thread:** Pembungkus langsung 1:1 dari OS thread. Memakan memori statis besar (~1MB stack reservation), overhead context switch masuk ke kernel space (~1-2 microseconds), dan terbatas pada batas kapasitas sistem operasi (ribuan thread per node).
*   **Virtual Thread (Java 21+):** Thread ringan yang dikelola langsung oleh JVM (*M:N scheduling*). Jutaan virtual thread dipetakan ke sekumpulan kecil OS worker thread yang disebut **Carrier Threads** (berbasis `ForkJoinPool`).
    *   Ketika kode Virtual Thread melakukan operasi I/O pemblokiran (misal: socket read, database call non-blocking driver), JVM mengintersepsi panggilan via *continuation yielding*.
    *   Virtual Thread di-*unmount* dari Carrier Thread; stack frame-nya dipindahkan dari thread stack hardware ke Java Heap.
    *   Carrier Thread bebas mengeksekusi Virtual Thread lain.
    *   Setelah I/O selesai, OS event loop (epoll/kqueue) memicu notifikasi; Virtual Thread di-*mount* kembali ke Carrier Thread yang tersedia untuk melanjutkan eksekusi.

**Peringatan Kritis: Carrier Thread Pinning**
Jika Virtual Thread mengeksekusi kode I/O di dalam blok `synchronized` atau memanggil Foreign Function/JNI, virtual thread mengalami *pinning* (terpasak) ke Carrier Thread. Carrier Thread terblokir di level OS, merusak skalabilitas platform. Solusinya: migrasi blok `synchronized` ke `ReentrantLock`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Rekayasa Lanjutan (Advanced) | Justifikasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **State Synchronization** | `synchronized`, `ReentrantLock` | Lock-Free CAS, `VarHandle`, `LongAdder` | Mengeliminasi biaya thread suspension, context switching kernel, serta prioritas inversi pada skenario throughput ekstrim. |
| **Read Contention** | `ReentrantReadWriteLock` | `StampedLock` (Optimistic Reads) | Menghilangkan write-starvation dan mutasi state atomic internal pada read lock konvensional yang menyebabkan *cache invalidation storm*. |
| **Compute Partitioning** | `FixedThreadPool` + `Callable` | `ForkJoinPool` (Divide and Conquer) | Mengoptimalkan CPU pipelining melalui work-stealing, meminimalkan contention antar thread worker, menjaga L1 cache locality. |
| **I/O Scaling** | Reactive (WebFlux/RxJava) atau Platform Threads | Virtual Threads (Java 21+) | Mengembalikan gaya pemrograman imperatif sekuensial yang mudah di-debug tanpa mengorbankan skalabilitas concurrency masif. |

---

### 5. How (Workflow Detail)

Alur perancangan modul konkurensi berperforma tinggi di level enterprise mengikuti tahapan berikut:

```
[Kebutuhan State/I/O]
        |
        v
 Apakah Mutasi I/O-Bound?
    |               |
   (Ya)           (Tidak: CPU-Bound)
    |               |
    v               v
Gunakan Virtual   Apakah Komputasi Divide-and-Conquer?
Threads (JEP 444)   |               |
(Hindari Pinning)  (Ya)           (Tidak: State Mutation Sederhana)
                    |               |
                    v               v
              ForkJoinPool    Apakah Read Dominan (>90%)?
              (Work Steal)     |               |
                              (Ya)           (Tidak)
                               |               |
                               v               v
                          StampedLock     Apakah Mutasi Numerik Counter?
                         (Optimistic)      |               |
                                          (Ya)           (Tidak: Arbitrary State)
                                           |               |
                                           v               v
                                      LongAdder       Lock-Free Loop via
                                      (Cell array)   VarHandle / CAS / AQS
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Optimistic Read pada `StampedLock` vs `ReadWriteLock`
*   **`ReadWriteLock` (Pessimistic):** Seperti perpustakaan dengan penjaga pintu ketat. Setiap pengunjung yang ingin membaca harus melapor, menandatangani buku tamu (menulis ke status memori bersama), dan mengunci pintu agar penulis tidak masuk sama sekali. Menandatangani buku tamu terus-menerus menyebabkan antrean panjang di pintu masuk.
*   **`StampedLock` Optimistic Read:** Pengunjung langsung masuk tanpa tanda tangan; mereka hanya melirik stempel tanggal di papan pengumuman (*get stamp*). Mereka membaca buku. Sebelum keluar, mereka melirik kembali stempel tanggal tersebut (*validate stamp*). Jika tanggal tidak berubah, bacaan valid. Jika tanggal berubah (ada penulis yang masuk dan merombak rak buku), pembaca membuang salinan bacaannya dan beralih ke mode antrean resmi (*fallback to pessimistic read lock*).

```
   Pessimistic (ReadWriteLock)               Optimistic (StampedLock)
   
[Reader] -> Write shared state -> Lock    [Reader] -> Ambil Stamp (Memory Read)
   |                                         |
   v                                         v
Baca Data                                 Baca Data secara lokal
   |                                         |
   v                                         v
[Reader] -> Write shared state -> Unlock  Validasi Stamp == Original Stamp?
                                          /                         \
                                      (Valid)                     (Invalid)
                                         |                            |
                                      Selesai           Fallback: Ambil Pessimistic Lock
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Optimasi Counter Read-Heavy via `StampedLock`

```java
package com.enterprise.concurrency.basic;

import java.util.concurrent.locks.StampedLock;

public class OptimisticPointRegistry {
    private double x, y;
    private final StampedLock sl = new StampedLock();

    public void move(double deltaX, double deltaY) {
        long stamp = sl.writeLock();
        try {
            x += deltaX;
            y += deltaY;
        } finally {
            sl.unlockWrite(stamp);
        }
    }

    // Optimistic Read: Zero synchronization memory bus overhead
    public double distanceFromOrigin() {
        long stamp = sl.tryOptimisticRead();
        double currentX = x;
        double currentY = y;
        
        // Memeriksa apakah terjadi write lock contention selama assignment lokal
        if (!sl.validate(stamp)) {
            // Fallback ke Pessimistic Read Lock jika optimisme gagal
            stamp = sl.readLock();
            try {
                currentX = x;
                currentY = y;
            } finally {
                sl.unlockRead(stamp);
            }
        }
        return Math.hypot(currentX, currentY);
    }
}
```

#### 7.2 Practical Example: Custom Non-Blocking Circuit Breaker via `VarHandle`

Implementasi sirkuit proteksi transaksi enterprise menggunakan state-machine atomik non-blocking tanpa intrinsic locking (`synchronized`).

```java
package com.enterprise.concurrency.advanced;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

public class AtomicCircuitBreaker {

    public enum State {
        CLOSED, OPEN, HALF_OPEN
    }

    private static final int FAILURE_THRESHOLD = 5;
    private static final long RESET_TIMEOUT_NANOS = 10_000_000_000L; // 10 Detik

    private volatile State state = State.CLOSED;
    private volatile int consecutiveFailures = 0;
    private volatile long lastStateChangedTimestamp = System.nanoTime();

    private static final VarHandle STATE_HANDLE;
    private static final VarHandle FAILURES_HANDLE;

    static {
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup();
            STATE_HANDLE = lookup.findVarHandle(AtomicCircuitBreaker.class, "state", State.class);
            FAILURES_HANDLE = lookup.findVarHandle(AtomicCircuitBreaker.class, "consecutiveFailures", int.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public boolean allowExecution() {
        State current = (State) STATE_HANDLE.getVolatile(this);
        if (current == State.CLOSED) {
            return true;
        }

        if (current == State.OPEN) {
            long openDuration = System.nanoTime() - lastStateChangedTimestamp;
            if (openDuration > RESET_TIMEOUT_NANOS) {
                // Berusaha transisi atomic dari OPEN ke HALF_OPEN
                if (STATE_HANDLE.compareAndSet(this, State.OPEN, State.HALF_OPEN)) {
                    lastStateChangedTimestamp = System.nanoTime();
                    return true;
                }
            }
            return false;
        }

        // HALF_OPEN: Izinkan single probe execution
        return true;
    }

    public void recordSuccess() {
        State current = (State) STATE_HANDLE.getVolatile(this);
        if (current == State.HALF_OPEN) {
            if (STATE_HANDLE.compareAndSet(this, State.HALF_OPEN, State.CLOSED)) {
                FAILURES_HANDLE.setVolatile(this, 0);
            }
        } else if (current == State.CLOSED) {
            FAILURES_HANDLE.setVolatile(this, 0);
        }
    }

    public void recordFailure() {
        int failures;
        do {
            failures = (int) FAILURES_HANDLE.getVolatile(this);
        } while (!FAILURES_HANDLE.compareAndSet(this, failures, failures + 1));

        if (failures + 1 >= FAILURE_THRESHOLD) {
            if (STATE_HANDLE.compareAndSet(this, State.CLOSED, State.OPEN)) {
                this.lastStateChangedTimestamp = System.nanoTime();
            } else if (STATE_HANDLE.compareAndSet(this, State.HALF_OPEN, State.OPEN)) {
                this.lastStateChangedTimestamp = System.nanoTime();
            }
        }
    }

    public State getState() {
        return (State) STATE_HANDLE.getVolatile(this);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Perusahaan Financial Technology memproses transaksi otorisasi pembayaran kartu kredit dengan SLA latensi P99 < 15ms pada beban puncak 80.000 Request Per Second (RPS). 

Arsitektur lama menggunakan thread pool klasik berbasis OS (`ThreadPoolExecutor` dengan 1.000 thread) dan orkestrasi blocking database + fraud check RPC.

#### Anomali yang Muncul
1.  **Thread Starvation & Context Switching Thrashing:** Penggunaan ribuan OS thread menyebabkan CPU menghabiskan 40% kapasitas compute hanya untuk swapping register/stack CPU (*kernel context switch overhead*).
2.  **Cascading Latency Spike:** Ketika service scoring fraud eksternal mengalami penurunan performa (latensi naik dari 5ms ke 500ms), 1.000 thread habis terblokir menunggu I/O. Tomcat menolak incoming request baru (HTTP 503).
3.  **Memory Footprint:** 1.000 platform thread $\times$ 1 MB stack memakan 1 GB RAM hanya untuk idle thread stacks, di luar heap memory.

#### Solusi Rekayasa
1.  Migrasi orkestrasi transaksi ke **Virtual Threads (Java 21+)** untuk I/O offloading tak terbatas secara elastis.
2.  Menerapkan **Dedicated Bounded Custom ForkJoinPool** untuk pemrosesan validasi enkripsi token kartu (CPU-bound) agar tidak mengganggu thread lain.
3.  Implementasi isolasi dependensi eksternal menggunakan non-blocking pipeline `CompletableFuture` dengan timeout deterministik.

#### Implementasi Kode: Enterprise Payment Orchestration Engine

```java
package com.enterprise.concurrency.production;

import java.time.Duration;
import java.util.concurrent.*;

public class PaymentOrchestrationEngine implements AutoCloseable {

    private final ExecutorService virtualThreadExecutor;
    private final ForkJoinPool cpuBoundCryptoPool;
    private final ScheduledExecutorService timeoutScheduler;

    public PaymentOrchestrationEngine(int cryptoParallelism) {
        // Virtual Thread Executor: Unlimited concurrency for blocking I/O calls
        this.virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();

        // CPU-bound pool sizing based on hardware concurrency
        this.cpuBoundCryptoPool = new ForkJoinPool(
                cryptoParallelism,
                ForkJoinPool.defaultForkJoinWorkerThreadFactory,
                (t, e) -> System.err.printf("Uncaught exception in pool: %s, %s%n", t.getName(), e.getMessage()),
                false // LIFO mode for locality
        );

        // Deterministic cancellation scheduler
        this.timeoutScheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "timeout-watchdog");
            t.setDaemon(true);
            return t;
        });
    }

    public record PaymentRequest(String transactionId, String pan, double amount) {}
    public record PaymentResult(String transactionId, boolean approved, String reason) {}

    public CompletableFuture<PaymentResult> processPayment(PaymentRequest request) {
        // Step 1: Enkripsi & Hashing Payload (CPU-Bound Task diarahkan ke ForkJoinPool)
        CompletableFuture<String> tokenizationFuture = CompletableFuture.supplyAsync(() -> {
            return cpuBoundTokenize(request.pan());
        }, cpuBoundCryptoPool);

        // Step 2 & 3: I/O Calls dieksekusi paralel menggunakan Virtual Threads
        return tokenizationFuture.thenCompose(token -> {
            CompletableFuture<Boolean> fraudCheck = CompletableFuture.supplyAsync(
                    () -> callFraudDetectionService(token, request.amount()), 
                    virtualThreadExecutor
            );

            CompletableFuture<Boolean> ledgerCheck = CompletableFuture.supplyAsync(
                    () -> callLedgerService(request.transactionId(), request.amount()), 
                    virtualThreadExecutor
            );

            // Step 4: Aggregation / Barrier synchronization
            return fraudCheck.thenCombine(ledgerCheck, (fraudPass, ledgerPass) -> {
                if (fraudPass && ledgerPass) {
                    return new PaymentResult(request.transactionId(), true, "AUTHORIZED");
                }
                return new PaymentResult(request.transactionId(), false, "DECLINED_RISK_OR_FUNDS");
            });
        }).orTimeout(12, TimeUnit.MILLISECONDS) // Strict Enterprise SLA Boundary
          .exceptionally(ex -> {
              if (ex instanceof TimeoutException) {
                  return new PaymentResult(request.transactionId(), false, "GATEWAY_TIMEOUT");
              }
              return new PaymentResult(request.transactionId(), false, "INTERNAL_FAILURE: " + ex.getMessage());
          });
    }

    private String cpuBoundTokenize(String rawPan) {
        // Simulasi kalkulasi kriptografi intensif (AES/Argon2 hashing)
        long hash = 1125899906842624L;
        for (int i = 0; i < rawPan.length(); i++) {
            hash = 31 * hash + rawPan.charAt(i);
        }
        return "TKN-" + Long.toHexString(hash);
    }

    private boolean callFraudDetectionService(String token, double amount) {
        // Simulasi blocking REST/gRPC client call
        try {
            Thread.sleep(Duration.ofMillis(4)); // Virtual thread yields carrier thread here
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
        return amount < 10_000.0;
    }

    private boolean callLedgerService(String txId, double amount) {
        // Simulasi blocking database query via JDBC driver
        try {
            Thread.sleep(Duration.ofMillis(3)); // Virtual thread yields
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
        return true;
    }

    @Override
    public void close() {
        virtualThreadExecutor.close();
        cpuBoundCryptoPool.close();
        timeoutScheduler.shutdown();
    }
}
```

---

### 9. Trade-offs

```
                  PILIHAN STRATEGI ARSITEKTUR KONKURENSI
                                     |
    +--------------------------------+--------------------------------+
    |                                                                 |
    v                                                                 v
[Lock-Free / CAS Architecture]                       [Pessimistic / Virtual Threads]
- Latensi per-operasi sub-mikrodetik                 - Pengurangan throughput CPU akibat polling
- Kompleksitas kode tinggi (VarHandle, ABA problem)  - Kode imperatif sederhana & mudah di-debug
- Skalabilitas write-contention tinggi menurun       - Skalabilitas horizontal I/O masif
```

| Pendekatan / Teknologi | Latency Profil | Throughput Scale | Penggunaan Memori | Kompleksitas Rekayasa |
| :--- | :--- | :--- | :--- | :--- |
| **Pessimistic Locking (`ReentrantLock`)** | Moderate (~1-5 $\mu s$ saat contention) | Rendah–Sedang | Rendah (hanya instance node) | Rendah (Safe, well-understood) |
| **Lock-Free CAS Loop (`VarHandle`)** | Ultra-Low (<100 $ns$ uncontended) | Ekstrim (bila contention moderat) | Minimal (In-place mutation) | Sangat Tinggi (Rawan livelock, ABA risk) |
| **`StampedLock` (Optimistic Reads)** | Ultra-Low (Read path zero bus write) | Sangat Tinggi pada Read-heavy | Rendah | Tinggi (Harus disiplin tanpa reentrancy) |
| **Virtual Threads (Project Loom)** | Rendah (Menghilangkan context switch kernel) | Jutaan Concurrency (I/O) | ~Few KB per-thread pada Heap | Rendah–Menengah (Perlu mitigasi pinning) |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Carrier Thread Pinning pada Virtual Threads

*   **Penyebab:** Memanggil operasi I/O pemblokiran (misal HTTP call, Database I/O) di dalam blok `synchronized(lock)`. JVM tidak dapat melepaskan stack frame dari OS thread underlying (Carrier Thread).
*   **Gejala:** Throttling kapasitas sistem, *exhaustion* pada pool carrier thread default, performa anjlok drastis setara atau lebih buruk dari thread model konvensional.
*   **Deteksi:** Aktifkan VM flag pada runtime:
    ```bash
    -Djdk.tracePinnedThreads=full
    ```
*   **Troubleshooting:** Ganti semua `synchronized` yang membungkus I/O dengan `java.util.concurrent.locks.ReentrantLock`.

#### 10.2 False Sharing pada Multithreaded Processing Hot-Paths

*   **Penyebab:** Core 0 dan Core 1 memperbarui dua variabel yang berbeda tetapi variabel tersebut terletak bersebelahan dalam rentang 64-byte yang sama di memori utama.
*   **Gejala:** Utilisasi CPU tinggi, namun throughput skala agregat tidak naik saat jumlah core/thread ditambah.
*   **Troubleshooting:**
    *   Terapkan explicit class padding:
        ```java
        public class ContendedData {
            public volatile long value1;
            public long p1, p2, p3, p4, p5, p6, p7; // 56 bytes manual cache line padding
            public volatile long value2;
        }
        ```
    *   Atau gunakan JVM argument `-XX:-RestrictContended` dan tambahkan anotasi `@jdk.internal.vm.annotation.Contended` pada field target.

#### 10.3 Deadlock pada `StampedLock` Reentrancy Bug

*   **Penyebab:** `StampedLock` secara desain **TIDAK bersifat reentrant**. Thread yang memegang `sl.writeLock()` lalu memanggil metode internal yang kembali meminta `sl.writeLock()` atau `sl.readLock()` akan mengalami self-deadlock.
*   **Troubleshooting:** Pastikan unit logika yang memerlukan lock bersifat self-contained, atau gunakan `ReentrantLock` jika desain arsitektur modular Anda menuntut pemanggilan bertingkat (reentrant calls).

---

### 11. Best Practices (Production Checklist)

1.  [ ] **Ukuran Thread Pool Matematis Terverifikasi:**
    $$N_{\text{threads}} = N_{\text{CPU}} \times U_{\text{CPU}} \times \left(1 + \frac{W}{C}\right)$$
    Di mana $U_{\text{CPU}}$ adalah target utilisasi CPU, $W$ adalah *wait time* (I/O), dan $C$ adalah *compute time* (CPU). Jangan pernah menebak ukuran thread pool.
2.  [ ] **Bounded Task Queues Wajib Digunakan:** Hindari `Executors.newFixedThreadPool(n)` tanpa argumen antrean eksplisit karena menggunakan `LinkedBlockingQueue` tak berbatas (*unbounded* / `Integer.MAX_VALUE`), yang berisiko memicu `OutOfMemoryError: Java heap space`. Gunakan `ArrayBlockingQueue` dengan `RejectedExecutionHandler` kustom (misal: caller-runs atau dead-letter metrics).
3.  [ ] **Thread Naming Factory:** Seluruh thread pool wajib menggunakan `ThreadFactory` khusus yang memberikan nama terstruktur (contoh: `payment-processor-worker-%d`) untuk kemudahan diagnostik via *thread dump*.
4.  [ ] **Disiplin Try-Finally:** Setiap pemanggilan `lock.lock()`, `sl.writeLock()`, atau AQS primitives harus langsung diikuti blok `try { ... } finally { lock.unlock(); }` tanpa kode intervensi di antara perolehan lock dan awal blok `try`.
5.  [ ] **Hindari ThreadLocal Berlebihan pada Virtual Threads:** Karena Virtual Threads dapat dibuat dalam jumlah jutaan, alokasi memori objek berat pada `ThreadLocal` akan melipatgandakan konsumsi heap secara eksplosif. Gunakan `ScopedValue` (Java 21+) sebagai alternatif modern yang *immutable* dan hemat memori.

---

### 12. Hands-on Practice

Buatlah proyek berbasis Maven/Gradle dan simpan seluruh kode berikut di dalam folder: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Struktur File
```bash
mkdir -p hands-on/m02/src/main/java/com/enterprise/concurrency/
mkdir -p hands-on/m02/src/test/java/com/enterprise/concurrency/
```

#### Langkah 2: Buat Implementasi Ring-Buffer Lock-Free Single-Producer Single-Consumer (SPSC)
File: `hands-on/m02/src/main/java/com/enterprise/concurrency/SpscLockFreeRingBuffer.java`

```java
package com.enterprise.concurrency;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

public class SpscLockFreeRingBuffer<E> {

    private final Object[] buffer;
    private final int mask;

    private volatile long head = 0;
    private volatile long tail = 0;

    private static final VarHandle HEAD;
    private static final VarHandle TAIL;
    private static final VarHandle BUFFER_ELEMENT;

    static {
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup();
            HEAD = lookup.findVarHandle(SpscLockFreeRingBuffer.class, "head", long.class);
            TAIL = lookup.findVarHandle(SpscLockFreeRingBuffer.class, "tail", long.class);
            BUFFER_ELEMENT = MethodHandles.arrayElementVarHandle(Object[].class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public SpscLockFreeRingBuffer(int capacity) {
        int adjustedCapacity = findNextPositivePowerOfTwo(capacity);
        this.buffer = new Object[adjustedCapacity];
        this.mask = adjustedCapacity - 1;
    }

    private static int findNextPositivePowerOfTwo(int value) {
        return 1 << (32 - Integer.numberOfLeadingZeros(value - 1));
    }

    public boolean offer(E item) {
        if (item == null) throw new NullPointerException("Null elements prohibited");

        final long currentTail = (long) TAIL.getOpaque(this);
        final long currentHead = (long) HEAD.getAcquire(this);

        if (currentTail - currentHead >= buffer.length) {
            return false; // Buffer penuh
        }

        int index = (int) (currentTail & mask);
        BUFFER_ELEMENT.setRelease(buffer, index, item);
        TAIL.setRelease(this, currentTail + 1);
        return true;
    }

    @SuppressWarnings("unchecked")
    public E poll() {
        final long currentHead = (long) HEAD.getOpaque(this);
        final long currentTail = (long) TAIL.getAcquire(this);

        if (currentHead >= currentTail) {
            return null; // Buffer kosong
        }

        int index = (int) (currentHead & mask);
        E item = (E) BUFFER_ELEMENT.getAcquire(buffer, index);
        BUFFER_ELEMENT.setRelease(buffer, index, null); // GC hygiene
        HEAD.setRelease(this, currentHead + 1);
        return item;
    }
}
```

#### Langkah 3: Buat Unit Test Verifikasi Concurrency & Correctness
File: `hands-on/m02/src/test/java/com/enterprise/concurrency/SpscLockFreeRingBufferTest.java`

```java
package com.enterprise.concurrency;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

public class SpscLockFreeRingBufferTest {

    @Test
    public void testHighThroughputSpscIntegrity() throws InterruptedException {
        final int iterations = 10_000_000;
        final SpscLockFreeRingBuffer<Integer> ringBuffer = new SpscLockFreeRingBuffer<>(1024);
        final CountDownLatch latch = new CountDownLatch(2);
        final AtomicInteger checksumConsumer = new AtomicInteger(0);

        long start = System.nanoTime();

        // Single Producer Thread
        Thread producer = Thread.ofPlatform().name("producer-worker").start(() -> {
            latch.countDown();
            try {
                latch.await();
            } catch (InterruptedException ignored) {}

            for (int i = 1; i <= iterations; i++) {
                while (!ringBuffer.offer(i)) {
                    Thread.onSpinWait(); // JVM instruction hint to CPU
                }
            }
        });

        // Single Consumer Thread
        Thread consumer = Thread.ofPlatform().name("consumer-worker").start(() -> {
            latch.countDown();
            try {
                latch.await();
            } catch (InterruptedException ignored) {}

            int received = 0;
            int sum = 0;
            while (received < iterations) {
                Integer val = ringBuffer.poll();
                if (val != null) {
                    sum += (val % 2 == 0) ? 1 : 0;
                    received++;
                } else {
                    Thread.onSpinWait();
                }
            }
            checksumConsumer.set(sum);
        });

        producer.join();
        consumer.join();

        long durationMs = (System.nanoTime() - start) / 1_000_000;
        System.out.printf("Processed %d events in %d ms (Operations/sec: %,d)%n",
                iterations, durationMs, (long) (iterations / (durationMs / 1000.0)));

        Assertions.assertEquals(iterations / 2, checksumConsumer.get());
    }
}
```

---

### 13. Exercise

#### Level: Easy
Implementasikan thread-safe caching sederhana berbasis `StampedLock` yang memetakan `String key` ke `String value`. Pastikan pembacaan data cache didominasi oleh `tryOptimisticRead()`, dan hanya jatuh ke mode `readLock()` atau `writeLock()` jika terjadi pembaharuan cache (*cache miss*).

#### Level: Medium
Rancang sebuah custom synchronization primitive bernama `ResourceGate` menggunakan `AbstractQueuedSynchronizer` (AQS). Primitive ini memiliki aturan:
*   Maksimal memperbolehkan $N$ thread masuk secara serentak.
*   Jika mode darurat diaktifkan (`gate.closeAll()`), seluruh thread yang sedang menunggu atau akan masuk harus langsung diblokir dan menerima pengecualian `ResourceSuspendedException`.

#### Level: Hard
Kembangkan implementasi struktur data **Non-Blocking Lock-Free Stack** berbasis algoritma Treiber Stack (`VarHandle` CAS pada node pointer `head`), yang mampu menangani mitigasi bahaya memory reclamation dan terhindar secara matematis dari problem kontensi *False Sharing* pada referensi head node. Lakukan benchmark komparatif melawan `java.util.concurrent.ConcurrentLinkedDeque` pada 16 thread aktif.

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Principal Architect pada bursa pertukaran kripto terdesentralisasi (*order-matching engine*). Engine memproses 200.000 order pembatalan dan pencocokan per detik pada satu instans memori. Terdapat 3 kriteria kritis:
1.  Latensi match round-trip wajib deterministik di bawah 500 mikrodetik pada P99.9.
2.  Garbage Collection pauses apa pun di atas 1 milidetik tidak dapat ditoleransi.
3.  Virtual threads digunakan untuk menerima koneksi websocket luar, tetapi eksekusi pencocokan order (*matching algorithm*) berjalan pada fixed OS thread dedicated dengan pinning ke CPU Core tertentu (Affinity).

**Tantangan Eksekusi:**
*   Rancang arsitektur bridging antara ingress traffic Virtual Threads (non-pinned) dengan Core Matching Thread (pinned thread) tanpa menggunakan library pihak ketiga (hanya menggunakan Java Standard API).
*   Gunakan zero-allocation memory structures pada jalur kritis (hot-path).
*   Buktikan bahwa struktur data antrean komunikasi internal Anda bebas dari resiko *blocking*, aman terhadap *reordering*, dan tahan dari degradasi akibat *cache-coherence thrashing*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1.  Apa konsekuensi performa terhadap CPU Cache saat suatu thread melakukan penulisan ke variabel `volatile`?
2.  Mengapa `Thread.onSpinWait()` lebih disukai di dalam busy-wait loop dibandingkan loop kosong murni `while(!condition) {}`?
3.  Apa perbedaan mendasar antara memori stack yang dialokasikan untuk Platform Thread versus Virtual Thread?
4.  Mengapa `StampedLock` tidak dapat digunakan secara rekursif (non-reentrant)?
5.  Apa implikasi instruksi CAS (*Compare-And-Swap*) gagal pada kondisi beban write-contention sangat tinggi?

#### Bagian 2: Intermediate (5 Pertanyaan)
6.  Bagaimana cara kerja status `SIGNAL (-1)` pada node AQS dalam mengoptimalkan efisiensi bangun/tidurnya (*park/unpark*) sebuah thread?
7.  Jelaskan konsep *Carrier Thread Pinning* pada Project Loom dan sebutkan dua penyebab utama terjadinya kondisi tersebut!
8.  Bagaimana varian `LongAdder` dapat menghasilkan throughput penambahan angka yang jauh lebih tinggi daripada `AtomicLong` pada sistem multi-core masif?
9.  Dalam ForkJoinPool, mengapa pencurian tugas (*work-stealing*) dilakukan dari ujung atas (*top*) deque secara FIFO, sedangkan thread pemilik mengambil dari ujung bawah (*bottom*) secara LIFO?
10. Pada arsitektur hardware x86, mengapa memory reordering tipe *Store-Load* dapat terjadi meskipun compiler Java tidak mengubah urutan instruksi kode?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Analitis)
11. **Skenario A:** Tim Anda melaporkan bahwa setelah migrasi ke Java 21 Virtual Threads, sistem backend mengalami degradasi throughput parah dan metrik OS menampilkan jumlah platform thread melonjak hingga 8.000 thread. Saat dilakukan analisa thread dump, ditemukan ribuan `ForkJoinPool-1-worker-*` berstatus `BLOCKED` di dalam panggilan database legacy. Apa akar masalah arsitektur ini dan bagaimana resolusinya?
12. **Skenario B:** Sebuah sistem real-time analytics mengimplementasikan *in-memory aggregations* menggunakan array paralel berukuran kecil yang diakses oleh 8 thread pekerja. Meskipun komputasi murni CPU (tanpa I/O) dan thread pool berukuran pas dengan jumlah physical core, utilisasi CPU per-core hanya mencapai 40% dan latensi pemrosesan melonjak tinggi. Profiling hardware performance counter mencatat tingkat *L1 cache miss* mencapai 78%. Anomali apa yang terjadi dan bagaimana perbaikan strukturnya?
13. **Skenario C:** Sebuah microservice orkestrasi pemesanan tiket menggunakan `CompletableFuture.allOf(...)` untuk menggabungkan 20 panggilan dependensi I/O eksternal. Di lingkungan produksi dengan beban puncak, thread pool default `ForkJoinPool.commonPool()` kehabisan thread, melumpuhkan fitur-fitur background lain di dalam aplikasi JVM yang sama. Identifikasi cacat arsitektur integrasi ini dan berikan rekomendasi rekayasa perbaikannya!

---

#### Kunci Jawaban & Panduan Evaluasi

##### Jawaban Basic
1.  Penulisan ke variabel `volatile` menghasilkan instruksi CPU memory barrier (misal `mfence` atau `lock` prefix pada x86). Ini memaksa data di *store buffer* ditulis segera ke cache, menginvalidasi salinan cache line pada seluruh core CPU lain (lewat protokol MESI), dan menghentikan pipeline reordering CPU melintasi batas barrier tersebut.
2.  `Thread.onSpinWait()` memetakan ke instruksi native CPU (seperti instruksi `PAUSE` pada arsitektur x86). Ini memberi sinyal pada hardware bahwa core sedang dalam loop spin-wait, sehingga CPU dapat menonaktifkan sementara spekulasi eksekusi memori (menghindari memory order violation penalty saat keluar loop) dan menurunkan konsumsi daya panas prosesor.
3.  Platform Thread memiliki alokasi memori stack statis yang besar (default 1 MB per thread di OS) yang direservasi langsung sejak inisialisasi. Stack Virtual Thread bersifat dinamis, dimulai hanya dari beberapa ratus byte di Java Heap, dan ukurannya bertambah/berkurang sesuai kedalaman call frame eksekusi.
4.  `StampedLock` mengembalikan nilai representasi numerik (*stamp*) long 64-bit pada setiap perolehan kunci. Logika internal validasinya tidak mencatat identitas thread ID kepemilikan. Upaya reentrant lock pada stamp yang sama akan mengevaluasi status sebagai konkurensi liar atau benturan mutasi, yang mengarah ke self-deadlock.
5.  Saat contention sangat tinggi, instruksi CAS berulang kali mengevaluasi nilai lama yang sudah berubah, memicu *retry-loop* tanpa henti. Ini menghabiskan siklus CPU (100% core load) tanpa menyelesaikan unit kerja nyata (*livelock-like degradation*).

##### Jawaban Intermediate
6.  Pada AQS, status `SIGNAL (-1)` pada sebuah node adalah kontrak bahwa thread pemilik node tersebut berkewajiban membangunkan (*unpark*) node berikutnya (successor) saat ia melepas kuncinya kelak. Dengan menyetel pendahulunya ke status `SIGNAL`, thread yang hendak tidur memastikan ia tidak akan tertidur selamanya tanpa ada yang membangunkan, sehingga aman memanggil `LockSupport.park()`.
7.  *Carrier Thread Pinning* adalah kegagalan JVM melepaskan Virtual Thread dari OS carrier thread underlying saat eksekusi terblokir. Dua penyebab utama: (1) Eksekusi operasi blocking I/O di dalam blok/metode `synchronized`, dan (2) Eksekusi native method via JNI atau Foreign Function Interface (Project Panama).
8.  `AtomicLong` mengandalkan satu memory address terpusat yang diperebutkan via CAS loop; kegagalan CAS meningkat eksponensial seiring bertambahnya core. `LongAdder` memecah counter ke dalam array internal `Cell[]`. Berbagai thread memutasi cell yang terdistribusi secara independen (berdasarkan hash thread ID). Akumulasi total baru dilakukan saat metode `sum()` dipanggil.
9.  Thread lokal mengambil tugas dari *bottom* secara LIFO karena sub-tugas yang paling baru dimasukkan memiliki kemungkinan terbesar datanya masih bersarang (*warm*) di cache CPU L1/L2. Thread lain mencuri tugas dari *top* secara FIFO karena tugas tertua adalah unit dekomposisi terbesar (pohon teratas) yang jika dicuri akan menyediakan beban kerja mandiri paling banyak, sehingga meminimalkan frekuensi aksi pencurian berikutnya.
10. Arsitektur x86 menggunakan model konsistensi memori TSO (Total Store Order). Hardware memiliki *store buffer* internal. Saat core melakukan *Store*, data masuk ke buffer lokal terlebih dahulu sementara eksekusi *Load* berikutnya dapat langsung dieksekusi dari cache sebelum isi buffer sempat dialirkan ke L1 cache. Dari sudut pandang core lain, urutan operasi terlihat tertukar (*reordered*).

##### Jawaban Kasus Produksi
11. **Akar Masalah:** Driver database yang digunakan menggunakan blok `synchronized` internal untuk memproteksi socket connection stream, memicu *Carrier Thread Pinning*. Virtual thread memblokir OS thread; runtime Virtual Thread mendeteksi saturasi ini dan secara otomatis memicu kompensasi dengan melahirkan OS carrier thread baru hingga menyentuh batas sistem (8.000 thread), menyebabkan kehabisan native memory.
    **Resolusi:** (1) Perbarui driver database ke versi yang telah mengadopsi Java 21 primitives (menggunakan `ReentrantLock`), (2) Sementara waktu batasi concurrency Virtual Threads ke database menggunakan `Semaphore` bounded eksplisit alih-alih melepaskan pembuatan thread tak terkontrol, (3) Jalankan profiling `-Djdk.tracePinnedThreads=full` untuk memastikan zero-pinning.
12. **Akar Masalah:** Terjadi fenomena **False Sharing**. Array berukuran kecil menempatkan variabel-variabel counter per-thread saling bersebelahan di dalam baris memori yang sama (satu *cache line* 64-byte). Ketika Thread 0 memutasi indeks 0, core menginvalidasi L1 cache milik Thread 1 yang mengolah indeks 1, menyebabkan *cache invalidation storm* terus menerus antar core.
    **Resolusi:** Terapkan memory padding antar variabel pemrosesan menggunakan class pembungkus bernotasi `@Contended` atau padding array dummy 64 bytes (`long p1, p2, p3, p4, p5, p6, p7`), atau konversi pemrosesan menjadi agregasi lokal pada stack thread sebelum digabungkan ke array utama secara batch.
13. **Akar Masalah:** `CompletableFuture` tanpa passing argumen `Executor` eksplisit secara default akan menggunakan `ForkJoinPool.commonPool()`. Pool ini didesain secara global untuk komputasi internal JVM berkarakteristik CPU-bound non-blocking. Menggunakan pool ini untuk puluhan blocking I/O panggilan eksternal menyebabkan *pool exhaustion*, memblokir task sistem JVM lain seperti parallel streams.
    **Resolusi:** Buat dedicated custom thread pool terisolasi untuk downstream I/O tersebut, baik menggunakan `Executors.newVirtualThreadPerTaskExecutor()` (jika I/O compliant) atau `ThreadPoolExecutor` bounded yang disetel dengan *CallerRunsPolicy* serta batasan antrean yang terukur.

---

### 16. Summary

*   **JMM bukan abstraksi fiktif**, melainkan spesifikasi formal yang menjembatani perilaku instruction reordering CPU modern, store buffers, dan protokol cache coherence (MESI) dengan semantik bahasa pemrograman.
*   **Lock-Free Programming via `VarHandle` & CAS** menghadirkan latensi pemrosesan sub-mikrodetik yang krusial untuk ultra-low latency computing, namun menuntut disiplin tinggi terhadap memory access modes (Acquire/Release/Volatile) dan potensi livelock.
*   **`StampedLock`** menjadi arsitektur pengganti definitif untuk `ReadWriteLock` pada workload yang didominasi read, berkat kemampuan *optimistic read validation* yang tidak melakukan mutasi status memori pada jalur baca.
*   **Virtual Threads merevolusi I/O Bound Workloads** dengan memisahkan abstraksi logical execution dari kernel threads, namun mewajibkan eliminasi mutlak terhadap *Carrier Thread Pinning* (`synchronized` over I/O) dan kehati-hatian pada memori `ThreadLocal`.
*   **Stabilitas Enterprise Concurrency** bertumpu pada isolasi kapasitas (*bulkheading*): memisahkan thread pool komputasi CPU murni (`ForkJoinPool`) dari thread pool pemanggilan I/O jaringan secara deterministik dan terlindungi oleh timeout SLA yang ketat.