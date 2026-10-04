# MODUL PEMBELAJARAN: JAVA CONCURRENCY & MULTITHREADING MENDALAM

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Backend Engineering / Java Enterprise Architecture
* **Kategori:** `02-Programming-Languages`
* **Modul:** `Bab 03 Module 01`
* **Topik:** Java Concurrency & Multithreading Mendalam
* **Level:** Advanced (Tingkat Lanjut)
* **Prasyarat:** Pemahaman mendalam tentang Object-Oriented Programming (OOP) Java, struktur data dasar (Heap, Stack), exception handling, dan eksekusi JVM dasar.
* **Estimasi Waktu Belajar:** 14 - 18 Jam (Termasuk bedah kode dan praktikum mandiri)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memetakan Java Memory Model (JMM):** Mengidentifikasi relasi *happens-before*, mencegah *instruction reordering*, dan memahami interaksi antara CPU Cache (L1/L2/L3), Store Buffers, dan RAM terhadap variabel Java (C4 - Analysis).
2. **Menguasai Primitif Sinkronisasi & Transisi Lock:** Mengimplementasikan dan membedah siklus hidup *intrinsic lock* (`synchronized`, monitor inflation dari *biased* $\rightarrow$ *lightweight* $\rightarrow$ *heavyweight*) serta perbandingannya dengan `ReentrantLock` dan `StampedLock` (C5 - Synthesis).
3. **Mengonstruksi Algoritma Non-Blocking (Lock-Free):** Menerapkan primitif *Compare-And-Swap* (CAS) menggunakan `java.util.concurrent.atomic` dan `VarHandle` untuk struktur data bebas blokir dengan performa tinggi (C6 - Evaluation & Creation).
4. **Merancang Ekosistem Thread Pool Skala Produksi:** Melakukan *tuning* pada `ThreadPoolExecutor`, memilih mekanisme penolakan (*rejection policies*), mencegah kebocoran memori pada `ThreadLocal`, serta mengevaluasi adopsi Java 21+ *Virtual Threads* (Project Loom) untuk beban I/O intensif (C6 - Creation).
5. **Mendiagnosis Liveness Issues dan Anomali Konkurensi:** Melakukan investigasi mendalam terhadap *deadlock*, *livelock*, *thread starvation*, *race conditions*, serta membaca dan menginterpretasikan *thread dumps* untuk sistem terdistribusi skala tinggi (C5 - Evaluation).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman sekuensial, eksekusi kode dipandang seperti resep masakan linier: Baris $N$ selesai seutuhnya sebelum Baris $N+1$ dimulai. Paradigma ini runtuh seketika di lingkungan multi-core modern.

### Pergeseran Paradigma
Konkurensi **bukanlah** tentang menjalankan banyak hal secara bersamaan (itu adalah *paralelisme* hardware); konkurensi adalah tentang **struktur pengelolaan banyak hal yang berjalan secara independen dan berbagi status (*shared mutable state*)**.

```
[ Mental Model Tradisional ]
CPU ---> Menjalankan Instruksi A ---> Menjalankan Instruksi B ---> Menulis Langsung ke RAM

[ Mental Model Concurrency Modern ]
Core 0 [Register / L1 Cache] <---+
                                 |---> Interkoneksi Bus/Mesh ---> [RAM Bersama]
Core 1 [Register / L1 Cache] <---+
```

### 3 Hukum Utama Konkurensi Java
1. **Atomisitas (*Atomicity*):** Apakah operasi terjadi sebagai satu unit diskrit yang tidak dapat diinterupsi? (Contoh: Operasi `count++` terdiri dari 3 instruksi mikro: *read*, *modify*, *write*—ia **tidak** atomik).
2. **Visibilitas (*Visibility*):** Jika Core A mengubah sebuah nilai di RAM, kapan Core B dapat melihat perubahan tersebut tanpa terdistorsi oleh cache lokal CPU Core B?
3. **Pengurutan (*Ordering*):** Compiler, Just-In-Time (JIT) Compiler, dan CPU berhak mengubah urutan eksekusi (*instruction reordering*) selama hasil thread-tunggal tampak ekuivalen (*as-if-serial semantics*). Namun, penataan ulang ini dapat merusak konsistensi pada multi-thread.

Jika kode Anda membaca atau memodifikasi status bersama tanpa regulasi eksplisit, sistem Anda berada dalam status *undefined behavior*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Interaksi Java Memory Model (JMM) dengan Hardware Arsitektur

```
+-----------------------------------------------------------------------+
|                             HARDWARE                                  |
|                                                                       |
|  +--------------------+                     +--------------------+   |
|  |     CPU Core 0     |                     |     CPU Core 1     |   |
|  |  +--------------+  |                     |  +--------------+  |   |
|  |  |  Registers   |  |                     |  |  Registers   |  |   |
|  |  +--------------+  |                     |  +--------------+  |   |
|  |  | L1 D-Cache   |  |                     |  | L1 D-Cache   |  |   |
|  |  +--------------+  |                     |  +--------------+  |   |
|  |  | Store Buffer |  |                     |  | Store Buffer |  |   |
|  |  +--------------+  |                     |  +--------------+  |   |
|  +--------+-----------+                     +--------+-----------+   |
|           |                                          |               |
|           +-------------------+  +-------------------+               |
|                               |  |                                   |
|                     +---------v--v--------+                          |
|                     | L2 / L3 Shared Cache|                          |
|                     +---------+-----------+                          |
|                               |                                      |
+-------------------------------|---------------------------------------+
                                | System Bus
+-------------------------------v---------------------------------------+
|                            MAIN MEMORY                                |
|                                                                       |
|  Java Heap: [ Object Instance | Shared Mutable Fields ]               |
|                                                                       |
|  +---------------------------+     +-------------------------------+  |
|  | Thread 1 Local Work Memory|     | Thread 2 Local Work Memory    |  |
|  | (Stack, Read Frames)      |     | (Stack, Read Frames)          |  |
|  +---------------------------+     +-------------------------------+  |
+-----------------------------------------------------------------------+
```

### 2. Siklus Hidup Thread JVM (Java Thread States)

```
       start()
 [NEW] -------> [RUNNABLE] <-----------------------+
                   |   ^                           |
   I/O / Yield /   |   | OS Scheduler              |
   Quantum Expire  v   | Dispatched                |
              [RUNNING (di OS)]                    |
                   |                               |
       +-----------+-----------+                   |
       |                       |                   |
Lock Contended           wait() / join() /         | Lock Didapat /
(synchronized)           LockSupport.park()        | Notify / Time Habis
       |                       |                   |
       v                       v                   |
  [BLOCKED]            [WAITING / TIMED_WAITING]---+
       |                                           |
       +-------------------------------------------+
                   |
             run() selesai /
             Unhandled Exception
                   v
              [TERMINATED]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Objek Header JVM & Monitor Lock
Setiap objek Java di HotSpot JVM memiliki *Object Header* yang terdiri dari:
1. **Mark Word (32-bit atau 64-bit):** Menyimpan metadata runtime: HashCode, GC Age, Biased Lock Flag, dan Lock State.
2. **Klass Word:** Penunjuk ke metadata kelas di Metaspace.

#### Evolusi Penguncian (*Lock Inflation Path*):
* **Biased Locking:** (Dimatikan secara default di Java 15+) Mengasumsikan objek hanya pernah diakses oleh satu thread. Mengikat *Thread ID* langsung ke dalam Mark Word tanpa instruksi CAS berulang.
* **Lightweight Locking (Thin Lock):** Terjadi jika thread lain mencoba mengakses objek tanpa kontensi parah. JVM mengalokasikan *BasicObjectLock* pada stack eksekusi thread dan menggunakan CAS untuk mengarahkan Mark Word ke *Displaced Mark Word* di stack frame.
* **Heavyweight Locking (Inflated Monitor):** Jika terjadi kontensi tinggi (dua atau lebih thread bersaing memperebutkan lock pada waktu yang sama), lightweight lock akan di-*inflate* menjadi monitor sistem operasi (`ObjectMonitor`). Objek dialokasikan struktur C++ tingkat OS yang memiliki list:
  * `_cxq` (Contention Queue): Thread penantang baru ditempatkan di sini via CAS.
  * `_EntryList`: Thread yang bersiap di-*unpark* untuk mendapatkan giliran berikutnya.
  * `_WaitSet`: Thread yang memanggil `wait()`.

### 2. Memory Barriers (Fences) & JMM Happens-Before
CPU mengeksekusi instruksi secara *out-of-order* untuk memaksimalkan penggunaan *pipeline*. Untuk menegakkan batas konsistensi memori, JVM menyuntikkan instruksi perangkat keras khusus yang disebut **Memory Barrier**:

* **LoadLoad:** Menjamin semua operasi pembacaan sebelum barrier selesai sebelum pembacaan setelah barrier dieksekusi.
* **StoreStore:** Menjamin data hasil penulisan sebelum barrier telah di-*flush* ke cache sebelum penulisan berikutnya diizinkan.
* **LoadStore:** Menjamin pembacaan sebelum barrier tereksekusi sebelum instruksi penulisan berikutnya.
* **StoreLoad:** Barrier termahal. Memaksa semua instruksi penulisan sebelum barrier tersinkronisasi penuh sebelum pembacaan apa pun setelah barrier dieksekusi.

#### Aturan Formal *Happens-Before* dalam JMM:
Jika Operasi $A$ *happens-before* Operasi $B$ ($A \prec B$), maka hasil dari $A$ dijamin dapat dilihat oleh $B$.
1. **Program Order Rule:** Tiap aksi dalam satu thread terjadi sebelum aksi berikutnya sesuai urutan program tertulis.
2. **Monitor Lock Rule:** Pelepasan lock (`unlock`) pada monitor *happens-before* penguncian monitor yang sama berikutnya (`lock`).
3. **Volatile Variable Rule:** Operasi penulisan ke field `volatile` *happens-before* operasi pembacaan berikutnya dari field `volatile` tersebut.
4. **Thread Start Rule:** Pemanggilan `Thread.start()` *happens-before* aksi apa pun di dalam thread yang dimulai.
5. **Thread Termination Rule:** Aksi apa pun dalam suatu thread *happens-before* thread lain mendeteksi bahwa thread tersebut telah selesai (via `Thread.join()` atau return `Thread.isAlive() == false`).
6. **Transitivity Rule:** Jika $A \prec B$ dan $B \prec C$, maka $A \prec C$.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. `volatile` vs Primitif CAS (`Atomic*`)
Variabel `volatile` hanya menjamin **Visibilitas** dan **Pengurutan**, bukan **Atomisitas**. Penulisan ke variabel `volatile` menghasilkan semantik hardware *StoreLoad barrier*, memaksa *cache line* CPU terdekat untuk diekspos dan menolak pembacaan data basi (*stale data*).

```
// Operasi non-atomik:
volatile int counter = 0;
counter++; // Melibatkan READ (volatile), MODIFY (+1), WRITE (volatile)
           // Jika dua thread mengeksekusi ini serentak, salah satu update akan hilang!
```

Solusi untuk operasi mutasi atomik berkinerja tinggi adalah **Compare-And-Swap (CAS)**:
Instruksi level CPU (seperti `CMPXCHG` pada arsitektur x86) yang mengeksekusi logika berikut secara hardware-atomic:
$$\text{CAS}(V, E, N)$$
* $V$: Alamat memori yang akan diubah.
* $E$: Nilai yang diharapkan (*Expected*).
* $N$: Nilai baru yang akan ditulis (*New*).
Jika nilai saat ini pada $V == E$, ubah nilai pada $V$ menjadi $N$ dan kembalikan `true`. Jika tidak, operasi gagal tanpa mutasi, dan thread dapat mengulang kembali loop kalkulasinya (*optimistic loop*).

### 2. Lock Primitives: `synchronized` vs `ReentrantLock` vs `StampedLock`
* **`synchronized` (Intrinsic Lock):** Terkelola otomatis oleh JVM di level bytecode (`monitorenter`/`monitorexit`). Mendukung reentrancy (thread yang memegang lock dapat memasuki blok tersinkronisasi lain pada objek yang sama tanpa deadlock). Kekurangan: Tidak dapat di-interrupt saat menunggu lock, tidak ada polling waktu tunggu, dan bersifat eksklusif penuh.
* **`ReentrantLock`:** Mengimplementasikan interface `Lock`. Menggunakan *AbstractQueuedSynchronizer* (AQS). Memungkinkan:
  * Polling lock via `tryLock()`.
  * Penguncian yang dapat diinterupsi (`lockInterruptibly()`).
  * Fairness policy (FIFO queue vs non-fair performa tinggi).
* **`StampedLock` (Java 8+):** Menggunakan token (*stamp*) berjenis `long`. Menyediakan mode pembacaan optimis (*Optimistic Reading*) yang tidak menggunakan locking sama sekali kecuali jika terjadi mutasi di tengah pembacaan, secara drastis mengurangi kontensi pembacaan data.

### 3. Thread Pools & Queue Dynamics
Arsitektur `ThreadPoolExecutor` diatur oleh relasi matematis parameter:
* `corePoolSize`: Jumlah thread minimum yang dipertahankan tetap hidup.
* `maximumPoolSize`: Batas absolut thread fisik yang dialokasikan.
* `workQueue`: Antrean tugas pemblokir (`BlockingQueue`).

**Algoritma Penjadwalan Tugas:**
1. Jika jumlah thread saat ini $< \text{corePoolSize}$, thread worker baru dibuat untuk memproses tugas baru.
2. Jika jumlah thread $\ge \text{corePoolSize}$, tugas **wajib** dicoba dimasukkan ke dalam `workQueue`.
3. Jika antrean penuh dan thread saat ini $< \text{maximumPoolSize}$, thread baru dialokasikan hingga batas maksimum.
4. Jika antrean penuh dan thread saat ini $== \text{maximumPoolSize}$, `RejectedExecutionHandler` dipicu.

### 4. Virtual Threads (Project Loom - Java 21+)
Java tradisional memetakan 1 Java Thread langsung ke 1 Operating System (OS) Kernel Thread (*1:1 model*). Beban memori thread OS tinggi (~1MB stack), dan *context switching* di level OS membutuhkan transisi kernel mode.

Virtual Threads memperkenalkan model *M:N multiplexing*. Jutaan Virtual Threads berjalan di atas sejumlah kecil *Carrier Threads* (OS Platform Threads). Saat Virtual Thread melakukan operasi I/O pemblokir (misal: JDBC call, Socket read), JVM secara otomatis melepaskan (*unmount*) stack Virtual Thread dari Carrier Thread via primitive `Continuation`, dan mengembalikan Carrier Thread ke pool untuk mengeksekusi Virtual Thread lain. Begitu I/O selesai, Virtual Thread di-*mount* kembali.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan perbandingan antara manipulasi nilai non-thread-safe, sinkronisasi berbasis `ReentrantLock`, dan implementasi Lock-Free menggunakan `AtomicLong` dan CAS loop eksplisit.

```java
package com.architect.concurrency.fundamental;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.ReentrantLock;

public final class CounterBenchmarkDemo {

    private static final int THREAD_COUNT = 8;
    private static final int INCREMENTS_PER_THREAD = 100_000;

    // 1. Primitive Unsafe State (Menghasilkan Race Condition)
    private static long unsafeCounter = 0;

    // 2. Lock-Based State
    private static long lockedCounter = 0;
    private static final ReentrantLock lock = new ReentrantLock();

    // 3. VarHandle CAS-Based State (Lock-Free)
    private static volatile long casCounter = 0;
    private static final VarHandle CAS_COUNTER_HANDLE;

    static {
        try {
            CAS_COUNTER_HANDLE = MethodHandles.lookup()
                .findStaticVarHandle(CounterBenchmarkDemo.class, "casCounter", long.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== MEMULAI BENCHMARK EKSEKUSI KONKURENSI ===");

        runExperiment("UNSAFE COUNTER", () -> {
            for (int i = 0; i < INCREMENTS_PER_THREAD; i++) {
                unsafeCounter++; // Non-atomic read-modify-write
            }
        });
        System.out.printf("Hasil Akhir Unsafe Counter : %d (Expected: %d)%n%n", 
                unsafeCounter, THREAD_COUNT * INCREMENTS_PER_THREAD);

        runExperiment("REENTRANT LOCK COUNTER", () -> {
            for (int i = 0; i < INCREMENTS_PER_THREAD; i++) {
                lock.lock();
                try {
                    lockedCounter++;
                } finally {
                    lock.unlock();
                }
            }
        });
        System.out.printf("Hasil Akhir Locked Counter : %d (Expected: %d)%n%n", 
                lockedCounter, THREAD_COUNT * INCREMENTS_PER_THREAD);

        runExperiment("VARHANDLE CAS COUNTER", () -> {
            for (int i = 0; i < INCREMENTS_PER_THREAD; i++) {
                incrementCasOptimistic();
            }
        });
        System.out.printf("Hasil Akhir CAS Counter    : %d (Expected: %d)%n%n", 
                casCounter, THREAD_COUNT * INCREMENTS_PER_THREAD);
    }

    private static void incrementCasOptimistic() {
        long current;
        long next;
        do {
            current = (long) CAS_COUNTER_HANDLE.getVolatile();
            next = current + 1;
            // Native Compare-And-Swap Loop
        } while (!CAS_COUNTER_HANDLE.compareAndSet(current, next));
    }

    private static void runExperiment(String testName, Runnable task) throws InterruptedException {
        ExecutorService executor = Executors.newFixedThreadPool(THREAD_COUNT);
        CountDownLatch startSignal = new CountDownLatch(1);
        CountDownLatch doneSignal = new CountDownLatch(THREAD_COUNT);

        for (int i = 0; i < THREAD_COUNT; i++) {
            executor.execute(() -> {
                try {
                    startSignal.await(); // Memaksa seluruh thread mulai bersamaan
                    task.run();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    doneSignal.countDown();
                }
            });
        }

        long startNanos = System.nanoTime();
        startSignal.countDown(); // Memicu race condition maksimum
        doneSignal.await();      // Menunggu seluruh thread selesai
        long duration = System.nanoTime() - startNanos;

        executor.shutdown();
        System.out.printf("[%s] Waktu Eksekusi: %,d ns%n", testName, duration);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari contoh kode di atas:

* **Baris 19:** `private static long unsafeCounter = 0;`
  Bidang ini tidak memiliki instruksi memory fence dan tidak berada di dalam blok sinkronisasi. Jika dua thread memuat register CPU mereka dengan nilai yang sama secara paralel, salah satu operasi penambahan akan menimpa yang lain tanpa terdeteksi (*lost update*).
* **Baris 23:** `private static final ReentrantLock lock = new ReentrantLock();`
  Inisialisasi lock mutual-exclusion. Menggunakan `AbstractQueuedSynchronizer` di balik layar untuk memarkir thread yang gagal memperoleh kepemilikan lock ke dalam antrean tunggu OS (*wait queue*).
* **Baris 26–35:** Registrasi `VarHandle CAS_COUNTER_HANDLE`
  `VarHandle` (diperkenalkan pada Java 9) menggantikan dependensi lama terhadap `sun.misc.Unsafe`. Mengakses pemetaan memori langsung ke field `casCounter` dengan jaminan performa setara intrinsik bahasa C.
* **Baris 46–50:** Penggunaan Blok `try-finally` pada `ReentrantLock`
  **Kaidah Wajib:** `lock.lock()` harus dipanggil **tepat sebelum** blok `try`, dan `lock.unlock()` harus diletakkan pada baris pertama di dalam blok `finally`. Ini menjamin pembebasan lock tetap terjadi meskipun terjadi `Error` atau `RuntimeException`.
* **Baris 67–75:** Implementasi Optimistic Loop pada `incrementCasOptimistic()`
  Metode ini membaca nilai mutakhir via `getVolatile()`, menyiapkan nilai inkremen, dan mengeksekusi `compareAndSet()`. Jika saat instruksi CPU CAS dieksekusi nilainya telah diubah oleh thread lain, loop akan mengulang (*retry*) pembacaan dan perhitungan tanpa melibatkan pemblokiran thread di tingkat OS (*zero context switch*).
* **Baris 79–80:** Penggunaan `CountDownLatch(1)` dan `CountDownLatch(THREAD_COUNT)`
  Pola *Gate Synchronizer*. `startSignal` mencegah thread mengeksekusi loop sebelum seluruh alokasi 8 thread worker benar-benar siap dan berada di kondisi `WAITING`, memaksa kontensi maksimum terjadi secara serentak.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Sistem: *High-Throughput In-Memory Rate Limiter* (Sliding Window Log Pattern)
* **Konteks Masalah:** Pada arsitektur Payment Gateway, sistem harus mampu membatasi maksimum $X$ permintaan per $Y$ milidetik per Merchant API Key secara *real-time*.
* **Beban Beban Kerja (*Workload*):**
  * Rata-rata $100.000$ transaksi/detik terdistribusi ke beberapa core server.
  * Pembacaan data status transaksi merchant berlangsung sangat sering, sementara mutasi penambahan log hanya terjadi jika kuota belum terlampaui.
* **Kebutuhan Teknis:**
  * Tidak boleh terjadi *false positive* yang meloloskan transaksi melampaui limit akibat race condition.
  * Mutasi status harus terisolasi per merchant tanpa menggunakan *global coarse-grained locking* yang membunuh skalabilitas multithreading.
  * Memori harus terbebas dari *leakage* log kadaluarsa.

### Pilihan Desain Arsitektur:
1. Menghindari `synchronized` pada level method service untuk mencegah bottleneck global.
2. Menggunakan `ConcurrentHashMap` dengan `compute()` untuk mencapai atomisitas pembaruan bucket spesifik.
3. Memanfaatkan `StampedLock` di dalam struktur data bucket internal untuk mengoptimalkan rasio pembacaan yang jauh lebih dominan dibanding penulisan.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem rate limiter tingkat produksi dengan algoritma *Sliding Window Counter* yang memanfaatkan `StampedLock` untuk meminimalkan beban latensi.

```java
package com.architect.concurrency.ratelimiter;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.StampedLock;

public final class DistributedScaleRateLimiter {

    private final int maxRequestsPerWindow;
    private final long windowSizeNanos;
    private final ConcurrentHashMap<String, SlidingWindowBucket> merchantBuckets;
    private final ScheduledExecutorService cleanupScheduler;

    public DistributedScaleRateLimiter(int maxRequestsPerWindow, long windowSize, TimeUnit timeUnit) {
        if (maxRequestsPerWindow <= 0) {
            throw new IllegalArgumentException("Max requests harus lebih besar dari 0");
        }
        this.maxRequestsPerWindow = maxRequestsPerWindow;
        this.windowSizeNanos = timeUnit.toNanos(windowSize);
        this.merchantBuckets = new ConcurrentHashMap<>();
        
        // Background thread pembersih untuk mencegah memori membengkak tak terbatas
        this.cleanupScheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "RateLimiter-Cleaner");
            t.setDaemon(true);
            return t;
        });
        this.cleanupScheduler.scheduleAtFixedRate(this::evictStaleBuckets, 1, 1, TimeUnit.MINUTES);
    }

    public boolean tryAcquire(String merchantApiKey) {
        Objects.requireNonNull(merchantApiKey, "merchantApiKey tidak boleh bernilai null");
        long currentNanos = System.nanoTime();

        SlidingWindowBucket bucket = merchantBuckets.computeIfAbsent(
                merchantApiKey, 
                k -> new SlidingWindowBucket()
        );

        return bucket.tryConsume(currentNanos, windowSizeNanos, maxRequestsPerWindow);
    }

    private void evictStaleBuckets() {
        long currentNanos = System.nanoTime();
        merchantBuckets.forEach((key, bucket) -> {
            if (bucket.isInactive(currentNanos, windowSizeNanos)) {
                merchantBuckets.remove(key, bucket);
            }
        });
    }

    public void shutdown() {
        cleanupScheduler.shutdown();
    }

    /**
     * Bucket internal berkinerja tinggi yang diamankan via StampedLock
     */
    private static final class SlidingWindowBucket {
        private final Deque<Long> timestampDeque = new ArrayDeque<>();
        private final StampedLock lock = new StampedLock();
        private long lastAccessNanos = System.nanoTime();

        public boolean tryConsume(long currentNanos, long windowSizeNanos, int maxAllowed) {
            long boundaryNanos = currentNanos - windowSizeNanos;

            // 1. Optimistic Reading Phase (Non-blocking check)
            long stamp = lock.tryOptimisticRead();
            boolean needExclusiveLock = false;

            if (stamp != 0L) {
                // Membaca status snapshot
                int currentSize = timestampDeque.size();
                long oldestTimestamp = currentSize > 0 ? timestampDeque.peekFirst() : 0L;

                if (lock.validate(stamp)) {
                    // Validasi berhasil: tidak ada penulisan konkuren selama pembacaan di atas
                    if (currentSize >= maxAllowed && oldestTimestamp > boundaryNanos) {
                        // Kuota penuh secara optimis terbukti valid, tolak request seketika
                        return false;
                    }
                }
            }

            // 2. Fallback ke Pessimistic Write Lock
            long writeStamp = lock.writeLock();
            try {
                this.lastAccessNanos = currentNanos;

                // Eviksi timestamp kadaluarsa dari sliding window
                while (!timestampDeque.isEmpty() && timestampDeque.peekFirst() <= boundaryNanos) {
                    timestampDeque.pollFirst();
                }

                if (timestampDeque.size() < maxAllowed) {
                    timestampDeque.addLast(currentNanos);
                    return true;
                } else {
                    return false;
                }
            } finally {
                lock.unlockWrite(writeStamp);
            }
        }

        public boolean isInactive(long currentNanos, long windowSizeNanos) {
            long stamp = lock.readLock();
            try {
                return (currentNanos - lastAccessNanos) > (windowSizeNanos * 2);
            } finally {
                lock.unlockRead(stamp);
            }
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Perbandingan Karakteristik Primitif Sinkronisasi

| Fitur / Karakteristik | `synchronized` | `ReentrantLock` | `StampedLock` | `Atomic*` (CAS) |
| :--- | :--- | :--- | :--- | :--- |
| **Tingkat Abstraksi** | Bytecode JVM | API Java Library | API Java Library | CPU Instruction (`CMPXCHG`) |
| **Optimistic Read** | Tidak Didukung | Tidak Didukung | Didukung via Stamp | Alami (Retry Loop) |
| **Reentrancy** | Penuh (Alami) | Penuh (Explicit) | **TIDAK REENTRANT** | Tidak Relevan |
| **Interruption Safe** | Tidak | Ya (`lockInterruptibly`) | Sebagian (Tergantung mode) | Ya (Tidak memblokir OS thread) |
| **Overhead Memori** | Nol (Mark Word Objek) | Sedang (Object AQS Node)| Sedang (Object Node) | Minimum (Object wrapper) |
| **Performa (Read-Heavy)**| Terbatas | Cukup | **Sangat Tinggi** | Luar Biasa |
| **Performa (High-Contention Writes)** | Cukup Baik (Adaptive spin) | Stabil | Menurun tajam | Menurun (Kelelahan CPU akibat loop) |

### 2. Evaluasi Thread Platform vs Virtual Thread (Project Loom)

```
+---------------------------------------------------------------------------------------+
| Skenario Kerja           | Pilihan Terbaik       | Alasan Arsitektural                       |
+--------------------------+-----------------------+-------------------------------------------+
| I/O Bound (Microservices,| Virtual Threads       | Triliunan task dapat di-suspend tanpa     |
| REST API, Database JDBC) | (Executors.newVirtual | membebani memori kernel OS thread. Stack  |
|                          | ThreadPerTaskExecutor)| dinamis di heap Java.                     |
+--------------------------+-----------------------+-------------------------------------------+
| CPU Bound (Kriptografi,  | Platform Thread Pool  | Virtual Thread tidak menambah core fisik. |
| Kompresi File, Encoding) | (ForkJoin / FixedPool)| Overhead unmount/mount justru membuang    |
|                          |                       | siklus CPU tanpa operasi I/O tunggu.      |
+--------------------------+-----------------------+-------------------------------------------+
| Legacy Codes dengan      | Platform Thread Pool  | Virtual thread akan terkena kondisi       |
| native JNI call /        | (Khusus & Terukur)    | "Pinned" (tidak dapat di-unmount) saat    |
| `synchronized` lama      |                       | eksekusi blok native/monitorenter.        |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Spurious Wakeups (Pembangkitan Semu)
Saat thread memanggil `wait()` atau `Condition.await()`, thread tersebut dapat terbangun secara spontan dari status suspended tanpa ada operasi `notify()` atau `signal()` yang dikirimkan.
* **Bahaya Arsitektural:** Memeriksa kondisi menggunakan `if` dapat meloloskan state yang belum valid ke baris eksekusi berikutnya.

```java
// BUG KRITIS:
if (!hasResource()) {
    condition.await(); // Bahaya: Saat terbangun semu, loop dilewati meski hasResource() == false
}
consumeResource();

// PERBAIKAN ARSITEKTURAL:
while (!hasResource()) {
    condition.await(); // Thread dipaksa re-evaluasi kondisi setiap kali terbangun
}
consumeResource();
```

### 2. ThreadLocal Leak pada Lingkungan Managed Thread Pool
Thread pool tidak menghancurkan thread yang telah selesai melayani request. Nilai `ThreadLocal` yang terikat pada thread worker akan terus bertahan hidup di Heap selamanya jika tidak dibersihkan secara manual.
* **Dampak:** OutOfMemoryError (`java.lang.OutOfMemoryError: Metaspace / Java heap space`) pada container server seperti Tomcat atau Kubernetes Pods.
* **Mitigasi:** Selalu bungkus manipulasi `ThreadLocal` dalam blok `try-finally` dengan `threadLocal.remove()` pada blok `finally`.

### 3. False Sharing pada Arsitektur Multi-Core
CPU modern mentransfer data antara RAM dan Cache dalam unit diskrit berukuran 64 byte bernama **Cache Lines**. Jika Thread A pada Core 0 mengubah variabel $X$, dan Thread B pada Core 1 membaca variabel $Y$, tetapi $X$ dan $Y$ terletak bersebelahan dalam cache line 64 byte yang sama:
* Inti CPU terpaksa membatalkan (*invalidate*) seluruh cache line tersebut secara terus menerus melalui cache coherency protocol (MESI).
* **Solusi:** Gunakan isolasi padding atau anotasi internal `@jdk.internal.ValueBased` / `@jdk.internal.vm.annotation.Contended` (membutuhkan JVM flag `-XX:-RestrictContended`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Double-Checked Locking Tanpa `volatile`
```java
// KODE SALAH:
public class SingletonRegistry {
    private static SingletonRegistry INSTANCE; // Tidak ada volatile!

    public static SingletonRegistry getInstance() {
        if (INSTANCE == null) {
            synchronized (SingletonRegistry.class) {
                if (INSTANCE == null) {
                    INSTANCE = new SingletonRegistry(); // RAWAN INSTRUCTION REORDERING
                }
            }
        }
        return INSTANCE;
    }
}
```
**Mengapa ini fatal?**
Inisialisasi objek `new SingletonRegistry()` dieksekusi oleh bytecode JVM dalam 3 tahap:
1. Alokasi memori kosong untuk objek.
2. Eksekusi konstruktor objek.
3. Menunjuk referensi `INSTANCE` ke alamat memori yang dialokasikan.

CPU diizinkan mengurutkan instruksi menjadi `1 -> 3 -> 2`. Jika Thread A berada pada tahap 3 dan belum menjalankan konstruktor, Thread B dapat masuk ke pengecekan pertama `INSTANCE == null` (bernilai `false`), lalu mengambil objek setengah jadi yang status variabel di dalamnya belum terinisialisasi seutuhnya (*partially initialized object crash*).
**Solusi:** Tambahkan penanda modifier `private static volatile SingletonRegistry INSTANCE;`.

### Mistake 2: Menelan Mentah-mentah `InterruptedException`
```java
// KODE SALAH:
try {
    Thread.sleep(5000);
} catch (InterruptedException e) {
    // Kosong / Hanya printStackTrace
}
```
**Mengapa ini fatal?**
Ketika JVM melempar `InterruptedException`, JVM **mereset status interupsi thread menjadi false**. Menelan exception ini menghilangkan sinyal shutdown sistem dari thread pool upstream, menyebabkan thread menjadi zombie dan memblokir *graceful shutdown* aplikasi.
**Solusi:** Kembalikan status interupsi dengan benar.
```java
// PERBAIKAN:
try {
    Thread.sleep(5000);
} catch (InterruptedException e) {
    Thread.currentThread().interrupt(); // Restore status interrupt
    logger.warn("Thread diinterupsi saat operasi tunggu. Membatalkan tugas...", e);
    return; // Keluar dari alur eksekusi
}
```

### Mistake 3: Mengeksekusi `.run()` Bukan `.start()`
Memanggil langsung `run()` pada instance class `Thread` tidak akan meluncurkan thread baru di tingkat sistem operasi. Kode tersebut hanya mengeksekusi instruksi method biasa di dalam thread pemanggil (*current caller thread*). Selalu gunakan `.start()` untuk memicu alokasi thread native oleh JVM.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prioritaskan Immutability (Objek Tanpa Mutasi):** Objek yang seluruh state-nya bernilai `final` secara otomatis aman dari masalah konkurensi (Thread-Safe) dan dapat dibagikan bebas tanpa membutuhkan mekanisme locking apa pun sesuai aturan safe publication JMM.
2. **Karantina Ruang Lingkup Critical Section:** Minimalkan baris kode di dalam blok lock. Jangan pernah mengeksekusi panggilan I/O jaringan, pemrosesan disk lambat, atau operasi kompleks di dalam blok sinkronisasi.
3. **Standarisasi Penamaan Custom Thread Pool:** Jangan pernah membiarkan thread anonim (`pool-1-thread-1`) berada di production runtime. Buat custom `ThreadFactory` untuk mempermudah identifikasi saat terjadi bottleneck log atau thread dump analysis.
4. **Penerapan Graceful Shutdown Pola 2-Fase:**
```java
public static void shutdownExecutorGracefully(ExecutorService executor, long timeoutSeconds) {
    executor.shutdown(); // 1. Berhenti menerima tugas baru
    try {
        // 2. Tunggu eksekusi tugas berjalan selesai
        if (!executor.awaitTermination(timeoutSeconds, TimeUnit.SECONDS)) {
            executor.shutdownNow(); // Batalkan paksa tugas yang masih tertahan
            if (!executor.awaitTermination(timeoutSeconds, TimeUnit.SECONDS)) {
                System.err.println("Thread pool menolak mati sepenuhnya.");
            }
        }
    } catch (InterruptedException ie) {
        executor.shutdownNow();
        Thread.currentThread().interrupt();
    }
}
```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Lock Striping Architecture
Daripada mengunci seluruh struktur koleksi data menggunakan satu global lock, pecah struktur data tersebut ke dalam beberapa segmen independen (stripe). Masing-masing segmen dilindungi oleh lock yang berbeda. Konsep ini adalah dasar performa tinggi di balik arsitektur internal `ConcurrentHashMap`.

### 2. Mengurangi Kontensi Menggunakan `LongAdder`
Saat puluhan core CPU berlomba-lomba memutasi satu variabel via `AtomicLong.incrementAndGet()`, instruksi hardware CAS akan mengalami *bus contention* yang parah akibat kegagalan berulang.
* Java 8 menghadirkan `java.util.concurrent.atomic.LongAdder`.
* `LongAdder` mempertahankan array sel internal (`Cell[]`) yang dialokasikan terpisah per thread untuk mendistribusikan beban penambahan.
* Saat nilai akhir diminta via `.sum()`, seluruh akumulasi nilai sel akan digabungkan. Operasi penulisan dapat diskalakan secara linear mengikuti jumlah core CPU.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Denial of Service via Unbounded Queue:**
   Penggunaan method factory instan seperti `Executors.newFixedThreadPool(n)` atau `Executors.newCachedThreadPool()` menggunakan `LinkedBlockingQueue` tanpa batas kapasitas maksimal (`Integer.MAX_VALUE`). Lonjakan permintaan eksternal secara drastis akan menimbun objek tasks di Heap memori hingga JVM runtuh terkena `OutOfMemoryError`.
   * **Mitigasi:** Selalu inisialisasi `ThreadPoolExecutor` secara eksplisit dengan `ArrayBlockingQueue` berkapasitas terikat (*bounded queue*) dan tetapkan `RejectedExecutionHandler` secara cermat (misal: `CallerRunsPolicy` atau custom metrics logging).
2. **Safe Publication via Final Fields:**
   Saat mengekspos objek baru ke thread lain, pastikan konstruktor telah selesai seutuhnya sebelum referensi objek diteruskan (*jangan biarkan `this` lolos/escaped dari dalam konstruktor*). Inisialisasi field bertipe `final` menjamin bahwa pembacaan field tersebut oleh thread mana pun akan selalu melihat nilai yang valid tanpa fenomena *memory race*.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Diagnostik Thread Dump Menggunakan `jcmd`
Untuk mengidentifikasi thread yang terkunci atau deadlock pada runtime production:
```bash
# Temukan Process ID (PID)
jcmd

# Ekstrak snapshot kondisi seluruh thread
jcmd <PID> Thread.print > threaddump.txt

# Menampilkan analisis Deadlock otomatis via JVM
jcmd <PID> Thread.dump_to_file -format=json thread_dump.json
```

### 2. Membaca Struktur Thread Dump Deadlock
```text
Found one Java-level deadlock:
=============================
"OrderProcessing-Thread-1":
  waiting to lock monitor 0x00007f9c8400a800 (object 0x0000000713002aa0, a java.lang.Object),
  which is held by "OrderProcessing-Thread-2"

"OrderProcessing-Thread-2":
  waiting to lock monitor 0x00007f9c8400b100 (object 0x0000000713002ab0, a java.lang.Object),
  which is held by "OrderProcessing-Thread-1"
```
**Analisis:**
Thread 1 memegang resource `A` dan menunggu resource `B`. Sementara Thread 2 memegang resource `B` dan menunggu resource `A`. Sistem mengalami kebuntuan fatal (*circular wait condition*).

### 3. Penyebaran Metadata Trace Context pada Thread Asinkron (MDC Propagation)
Log framework modern (Logback / Log4j2) mengandalkan `MDC` yang berbasiskan `ThreadLocal`. Saat eksekusi dilemparkan ke thread pool via `executor.submit()`, metadata korelasi log (`traceId`) akan terputus.
* **Solusi Produksi:** Bungkus seluruh submit task menggunakan custom decorator runnable yang menyalin dan membersihkan context map MDC ke dalam thread worker target.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------------------------------------------------------------+
| MASALAH KONKURENSI     | ALAT / SOLUSI UTAMA              | CATATAN PENTING                     |
+------------------------+----------------------------------+-------------------------------------+
| Race Conditions        | AtomicInteger, LongAdder, Lock   | Hindari counter primitif            |
| Visibility Basi        | volatile                         | Tidak menjamin operasi atomik       |
| Read Dominan (90%+)    | StampedLock, ReadWriteLock       | Waspadai stamp zero invalidation    |
| Mutual Exclusion       | ReentrantLock                    | Selalu tempatkan unlock() di finally|
| I/O Bound Workload     | Virtual Threads (Java 21+)       | Jangan gunakan thread pool kaku     |
| CPU Heavy Workload     | ForkJoinPool / FixedThreadPool   | Sesuaikan ukuran pool dengan Core   |
| Safe Wait-Notify       | Condition (await / signal)       | Selalu bungkus dalam while loop     |
| Singleton / Init       | Initialization-on-demand Holder  | Manfaatkan Classloader thread-safety|
+-----------------------------------------------------------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic Level)

1. **Apa yang secara spesifik dijamin oleh penandaan keyword `volatile` pada sebuah variabel field di Java?**
   * A. Menjamin atomisitas seluruh instruksi aritmatika pada variabel tersebut.
   * B. Menjamin bahwa thread yang membaca variabel tersebut akan selalu membaca nilai termutakhir dari memori utama dan mencegah penataan ulang instruksi tertentu.
   * C. Mencegah pemanggilan method secara konkuren oleh dua thread secara bersamaan.
   * D. Mengunci variabel tersebut secara permanen ke dalam cache L1 CPU.
   * *Jawaban:* **B**. `volatile` menjamin visibilitas dan pengurutan (*happens-before ordering*), namun **tidak** menjamin atomisitas operasi kompon (seperti penambahan atau pengurangan).

2. **Dua thread mengeksekusi kode `counter++` secara simultan tanpa sinkronisasi sebanyak 1.000 kali dari nilai awal 0. Berapakah rentang nilai akhir yang valid di Java?**
   * A. Pasti tepat bernilai 2.000.
   * B. Pasti bernilai 1.000.
   * C. Nilai apa pun antara 2 hingga 2.000.
   * D. Akan memicu lemparan `ConcurrentModificationException` di runtime.
   * *Jawaban:* **C**. Karena `counter++` adalah 3 langkah mikro (Read-Modify-Write), interleaving instruksi terburuk secara teoritis dapat menimpa hasil perhitungan hingga bernilai minimum 2, atau bekerja mulus hingga bernilai maksimum 2.000.

3. **Status thread mana yang menunjukkan bahwa thread Java sedang terblokir menunggu perolehan monitor lock intrinsic (`synchronized`)?**
   * A. `WAITING`
   * B. `TIMED_WAITING`
   * C. `BLOCKED`
   * D. `SUSPENDED`
   * *Jawaban:* **C**. Status `BLOCKED` dialokasikan secara spesifik hanya saat thread menunggu untuk memasuki blok/method tersinkronisasi `synchronized`. Menunggu lock bertipe `ReentrantLock` menghasilkan status `WAITING` atau `TIMED_WAITING` via `LockSupport.park()`.

4. **Kapan kondisi Deadlock terjadi pada arsitektur perangkat lunak multithreading?**
   * A. Saat thread kehabisan alokasi memori heap JVM.
   * B. Saat satu thread memonopoli CPU secara berkelanjutan tanpa memberi kesempatan bagi thread lain.
   * C. Saat dua atau lebih thread saling menunggu pelepasan resource/lock yang dipegang oleh thread lainnya secara melingkar.
   * D. Saat sebuah thread dimatikan secara paksa menggunakan `Thread.stop()`.
   * *Jawaban:* **C**. Sesuai syarat Coffman, deadlock mensyaratkan adanya kondisi mutual exclusion, hold and wait, no preemption, dan circular wait.

5. **Apa fungsi utama dari method `Thread.join()`?**
   * A. Menggabungkan dua pool thread yang berjalan terpisah.
   * B. Memaksa thread pemanggil untuk berhenti sejenak (*pause*) hingga thread target menyelesaikan eksekusinya.
   * C. Menginterupsi thread yang sedang mengalami loop tanpa henti.
   * D. Memaksa compiler JVM mengabaikan instruction reordering.
   * *Jawaban:* **B**. Pemanggilan `t.join()` menyebabkan thread saat ini menghentikan eksekusinya sampai thread `t` mencapai status `TERMINATED`.

---

### Soal Tingkat Menengah (Intermediate Level)

6. **Mengapa algoritma implementasi Double-Checked Locking membutuhkan keyword `volatile` pada deklarasi instance objeknya?**
   * A. Tanpa `volatile`, referensi objek dapat dipublikasikan ke thread lain sebelum proses konstruksi internal variabel objek selesai dieksekusi akibat *instruction reordering*.
   * B. `volatile` bertugas mencegah blok `synchronized` dimasuki lebih dari satu kali oleh thread yang sama.
   * C. Supaya instance objek dialokasikan di thread stack dan bukan di JVM heap memori.
   * D. Menjamin instance objek dibersihkan secara instan oleh Garbage Collector saat method selesai.
   * *Jawaban:* **A**. Reordering instruksi oleh hardware/JIT compiler dapat membuat penunjukan alamat memori terjadi sebelum konstruktor selesai dijalankan, memicu pembacaan status objek parsial (*half-baked object*) oleh thread lain.

7. **Pada `ThreadPoolExecutor`, apa yang terjadi secara internal jika antrean `workQueue` berkapasitas penuh dan parameter `maximumPoolSize` belum tercapai?**
   * A. Thread pool melempar `RejectedExecutionException`.
   * B. Tugas baru ditolak dan thread pemanggil dipaksa berhenti (*hung*).
   * C. Thread pool akan membuat worker thread baru di atas `corePoolSize` untuk mengeksekusi tugas tersebut hingga menyentuh batas `maximumPoolSize`.
   * D. Tugas baru akan menimpa tugas tertua yang tersimpan di dalam queue.
   * *Jawaban:* **C**. Sesuai aturan orkestrasi `ThreadPoolExecutor`, thread baru melebihi `corePoolSize` hanya akan dialokasikan jika dan hanya jika `workQueue` telah mencapai kapasitas maksimalnya.

8. **Apa kerugian terbesar menggunakan `StampedLock` dibandingkan `ReentrantLock` standar?**
   * A. `StampedLock` tidak dapat digunakan pada mesin multi-core.
   * B. `StampedLock` tidak bersifat Reentrant; pemanggilan lock berulang oleh thread yang sama akan memicu self-deadlock.
   * C. `StampedLock` memerlukan overhead alokasi memori yang jauh lebih besar dibanding heavyweight lock.
   * D. Operasi tulis pada `StampedLock` tidak memiliki jaminan mutual exclusion.
   * *Jawaban:* **B**. `StampedLock` sama sekali tidak mendukung *reentrancy*. Jika thread yang memegang write lock mencoba mengambil lock itu lagi, thread tersebut akan memblokir dirinya sendiri secara permanen (*self-deadlock*).

9. **Apa yang dimaksud dengan fenomena "Spurious Wakeup" pada sinkronisasi thread?**
   * A. Thread worker mati secara mendadak karena operating system kehabisan native memory.
   * B. Thread terbangun dari status `wait()` atau `await()` tanpa adanya sinyal eksplisit (`notify`/`signal`) atau habisnya periode waktu tunggu.
   * C. Thread mengabaikan instruksi interrupt yang dikirimkan oleh pool manager.
   * D. Garbage Collector memindahkan referensi lock saat sedang diakses oleh CPU.
   * *Jawaban:* **B**. Di level OS, thread yang diparkir dapat diaktifkan kembali oleh interupsi perangkat keras tingkat rendah atau context switch OS secara acak. Oleh sebab itu, kondisi tunggu **harus selalu** dievaluasi di dalam loop `while (condition)`.

10. **Kapan implementasi Virtual Threads (Project Loom) memberikan keunggulan performa paling signifikan dibandingkan Platform Threads konvensional?**
    * A. Pada sistem rendering video 3D dan kalkulasi machine learning yang memanfaatkan instruksi CPU murni.
    * B. Pada sistem enkripsi data dalam memori berskala gigabyte tanpa pemanggilan thread I/O.
    * C. Pada aplikasi layanan microservices yang menangani volume request sangat tinggi dengan pola pemblokiran I/O (akses database, REST call eksternal).
    * D. Pada sistem yang secara dominan mengeksekusi operasi native method via C library (JNI).
    * *Jawaban:* **C**. Virtual Threads unggul saat thread sering diblokir oleh operasi I/O, memungkinkan JVM melepaskan Carrier Thread untuk melayani komputasi lain. Pada tugas murni CPU-bound, Virtual Threads tidak memberikan peningkatan throughput dan justru menambah sedikit overhead penjadwalan.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: *Ultra-High Performance Concurrent Batching Pipeline (Backpressure Queue)*

#### Deskripsi Permasalahan
Anda ditugaskan oleh Lead Architect untuk membangun modul ingestion data analitik transaksi keuangan. Modul ini menerima ratusan ribu data transaksi per detik dari ribuan worker paralel, namun hanya diizinkan menuliskan data tersebut ke penyimpanan basis data dalam bentuk **Batch** (kelompok transaksi) guna menjaga stabilitas I/O database.

#### Kebutuhan Fungsional & Spesifikasi Sistem:
1. **Producer-Consumer Architecture:**
   * Banyak thread produser dapat memanggil method `submit(Transaction tx)` secara konkuren tanpa mengalami blocking yang berlebihan.
2. **Kriteria Pembentukan Batch:**
   * Batch harus dikirimkan ke storage jika:
     * Jumlah data di dalam antrean telah mencapai batas ukuran tertentu (misal: `BATCH_SIZE = 500` item), **ATAU**
     * Telah melewati batas waktu tunggu tertentu (misal: `MAX_DELAY_MS = 50` ms) meskipun jumlah data belum mencapai 500 item (*Flushing Timer Window*).
3. **Mekanisme Backpressure:**
   * Jika database mengalami latensi tinggi dan buffer antrean internal mencapai batas absolut (`MAX_BUFFER_CAPACITY = 50.000` transaksi), produser baru harus diperlambat atau diblokir secara terkendali tanpa menyebabkan crash memori heap (`OutOfMemoryError`).
4. **Zero Data Loss saat Shutdown:**
   * Implementasikan method `shutdownAndFlush()` yang aman. Ketika sistem menerima instruksi terminasi, sistem harus menolak transaksi baru yang masuk, menguras sisa transaksi yang tersimpan di dalam buffer, mengeksekusi batch terakhir ke database, lalu menutup seluruh thread pool secara bersih.

#### Batasan Teknis & Larangan:
* **DILARANG** menggunakan framework eksternal (hanya diperbolehkan menggunakan murni pustaka `java.base`: `java.util.concurrent.*`).
* **DILARANG** menggunakan sinkronisasi global tunggal `synchronized(this)` yang membungkus seluruh method ingestion.
* Evaluasi penggunaan `ArrayBlockingQueue`, `ReentrantLock` dengan `Condition`, atau primitif atomic yang tepat untuk mengatur koordinasi batching worker.
* Tuliskan *Integration Test* sederhana di dalam method `main()` yang memvalidasi bahwa jika 100.000 transaksi dimasukkan secara simultan oleh 20 thread, seluruh 100.000 data tersebut tercatat lengkap dan masuk ke dalam simulasi batch database tanpa kebocoran transaksi satupun (*zero missing items*).