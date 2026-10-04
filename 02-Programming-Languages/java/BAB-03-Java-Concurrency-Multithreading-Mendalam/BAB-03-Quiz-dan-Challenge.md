# BAB 03: Quiz, Challenge, & Knowledge Check
**Java Concurrency & Multithreading Mendalam**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Java Memory Model (JMM) dan Relasi *Happens-Before*
Jelaskan secara presisi arsitektural bagaimana Java Memory Model (JMM) menjamin visibilitas variabel antar-core CPU. Mengapa deklarasi `volatile` tidak menjamin operasi atomic seperti `count++`, namun mampu mencegah instruksi CPU melakukan *instruction reordering*? Uraikan peran *memory barriers* (*load/store fences*) dalam konteks ini.

### Soal 1.2: State Machine Thread & OS Scheduling Mapping
Gambarkan dan jelaskan transisi state thread di JVM (`NEW`, `RUNNABLE`, `BLOCKED`, `WAITING`, `TIMED_WAITING`, `TERMINATED`). Apa perbedaan mendasar antara state `BLOCKED` dan `WAITING` pada level interaksi dengan OS scheduler dan monitor object JVM? Sertakan referensi ke pemanggilan metode spesifik (`Object.wait()`, `Thread.sleep()`, `LockSupport.park()`, dan akuisisi monitor).

### Soal 1.3: Mekanisme Interupsi Kooperatif
Java tidak lagi mendukung penghentian thread secara paksa (`Thread.stop()` di-deprecate). Jelaskan filosofi desain di balik *cooperative interruption model* di Java. Mengapa membersihkan *interrupted status* secara implisit saat menangkap `InterruptedException` sering menjadi sumber bug kritis, dan bagaimana penanganan yang benar sesuai standar enterprise?

### Soal 1.4: Anatomi Memory Leak pada `ThreadLocal`
Uraikan arsitektur internal kelas `ThreadLocal` dan `ThreadLocalMap`. Mengapa entri pada `ThreadLocalMap` menggunakan `WeakReference` untuk *key*, tetapi menggunakan *strong reference* untuk *value*? Analisis bagaimana topologi ini dapat memicu memory leak yang parah (*perm/heap retention*) pada container server yang menggunakan *reusable worker thread pool* (misal: Apache Tomcat).

### Soal 1.5: Intrinsic Lock (`synchronized`) vs. Explicit Lock (`ReentrantLock`)
Bandingkan mekanisme `synchronized` dengan `java.util.concurrent.locks.ReentrantLock`. Uraikan bagaimana JVM melakukan *lock escalation/biasing* (dari *biased lock*, *lightweight lock/thin lock*, hingga *heavyweight/OS mutex lock*). Kapan seorang *systems engineer* harus memilih `ReentrantLock` daripada *intrinsic lock*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Arsitektur Internal AbstractQueuedSynchronizer (AQS)
Bongkar arsitektur internal `AbstractQueuedSynchronizer` (AQS) yang menjadi fondasi `ReentrantLock`, `Semaphore`, dan `CountDownLatch`. Jelaskan representasi status sinkronisasi (`state`), struktur data antrean internal (varian *CLH queue*), serta bagaimana thread diparkir dan dibangunkan kembali menggunakan primitives `LockSupport.park()` dan `LockSupport.unpark()`.

### Soal 2.2: Hardware Primitives, CAS, dan Mitigasi ABA Problem
Jelaskan bagaimana operasi *Compare-And-Swap* (CAS) dipetakan dari kelas atomik Java (`java.util.concurrent.atomic`) ke instruksi CPU native (seperti `CMPXCHG` pada arsitektur x86). Apa itu fenomena *ABA Problem* dalam struktur data *lock-free*, dalam kondisi apa fenomena ini merusak integritas sistem, dan bagaimana `AtomicStampedReference` menyelesaikannya secara mekanis?

### Soal 2.3: Cache Line Bouncing dan False Sharing
Pada arsitektur multi-core modern, CPU cache diorganisir dalam unit *cache line* (umumnya 64 byte). Jelaskan fenomena *false sharing* ketika dua thread memodifikasi dua variabel `volatile` independen yang kebetulan berada di cache line yang sama. Bagaimana protokol koherensi cache (misal: MESI) memukul degradasi throughput sistem? Bagaimana anotasi `@jdk.internal.vm.annotation.Contended` / JEP 142 memitigasi hal ini?

### Soal 2.4: Diagnostik Thread Dump: Deadlock, Livelock, dan Starvation
Diberikan laporan insiden di mana CPU server melonjak ke 100% pada sistem e-commerce tanpa ada transaksi yang terselesaikan, sementara pada insiden lain, pemrosesan berhenti total dengan CPU usage 0%. Jelaskan bagaimana Anda membedakan kondisi **Deadlock**, **Livelock**, dan **Thread Starvation** hanya menggunakan output command-line diagnostic tools (`jcmd`, `jstack`) dan Java Flight Recorder (JFR).

### Soal 2.5: Work-Stealing Internals pada `ForkJoinPool`
Bedah algoritma *work-stealing* pada `ForkJoinPool`. Bagaimana struktur *dual-ended queue* (deque) meminimalkan kontensi antar-*worker threads*? Jelaskan risiko performa fatal jika operasi blocking I/O (seperti panggilan REST client atau JDBC) dieksekusi secara naif di dalam `ForkJoinPool.commonPool()`, dan bagaimana mekanika `ForkJoinPool.ManagedBlocker` mengkompensasi hal tersebut.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Latency & Thread Pool Starvation Akibat Unbounded Queue
Sebuah layanan payment gateway berskala tinggi mengalami insiden kritis saat event diskon nasional. Rata-rata latency API melonjak dari 15ms menjadi 45 detik, diakhiri dengan cascading failures ke microservices hulu karena HTTP timeouts.

**Arsitektur Saat Ini:**
```java
// Konfigurasi Executor Service di Spring Boot
@Bean
public ExecutorService transactionExecutor() {
    return Executors.newFixedThreadPool(200); 
    // Menggunakan LinkedBlockingQueue dengan kapasitas Integer.MAX_VALUE
}
```
Downstream database mengalami degradasi latensi sementara (kueri naik dari 5ms ke 3000ms).

#### Pertanyaan Diagnostik & Solusi:
1. Analisis mengapa konfigurasi `Executors.newFixedThreadPool(200)` menyebabkan bahaya fatal (*catastrophic failure*) saat downstream service mengalami penurunan performa. Apa yang terjadi pada Heap Memory dan latensi antrean saat *unbounded queue* jenuh?
2. Redesain konfigurasi `ThreadPoolExecutor` tersebut menggunakan parameter *core pool size*, *maximum pool size*, *bounded queue*, dan implementasikan custom `RejectedExecutionHandler` yang menerapkan *backpressure* tanpa memicu hilangnya data transaksi. Sertakan pertimbangan sizing formula berdasarkan profiling CPU-bound vs I/O-bound.

---

### Skenario B: Race Condition Samar pada High-Throughput Check-Then-Act Cache
Tim trading crypto melaporkan anomali audit: saldo inventaris token pengguna sesekali menjadi bernilai negatif atau *double-allocated* ketika 100+ order masuk dalam milidetik yang sama.

**Potongan Kode Bermasalah:**
```java
public class OrderSettlementService {
    private final Map<String, AccountBalance> balanceCache = new ConcurrentHashMap<>();

    public void processDeduction(String accountId, BigDecimal amount) {
        AccountBalance balance = balanceCache.get(accountId);
        if (balance == null) {
            balance = loadFromDatabase(accountId);
            balanceCache.put(accountId, balance);
        }

        // Check-then-act race condition
        if (balance.getAvailableAmount().compareTo(amount) >= 0) {
            // Simulasi proses settlement eksternal lambat
            executeBankTransfer(accountId, amount);
            balance.deduct(amount); // Internal mutable state update
        } else {
            throw new InsufficientFundException("Saldo tidak mencukupi");
        }
    }
}
```

#### Pertanyaan Diagnostik & Solusi:
1. Bedah secara mendalam setidaknya **tiga titik celah kegagalan konkurensi (*concurrency bugs*)** pada implementasi di atas (tinjau dari aspek atomisitas *check-then-act*, thread-safety dari objek `AccountBalance`, dan semantik pemanggilan `ConcurrentHashMap`).
2. Tulis ulang kode tersebut secara thread-safe menggunakan idiomatik `ConcurrentHashMap` mutakhir (`compute`, `computeIfAbsent`), jadikan `AccountBalance` sebuah *immutable structure* atau koordinasikan mutasi state menggunakan operasi atomik *optimistic locking* (misal CAS).

---

### Skenario C: Dilema Arsitektural: Migrasi Virtual Threads (Java 21) vs. Thread Carrier Pinning
Sistem API gateway perusahaan perbankan memproses 50.000 concurrent HTTP requests. Manajemen mendorong migrasi penuh dari model Thread Pool konvensional (`Platform Threads`) ke **Virtual Threads (Project Loom)** untuk menghemat memori footprint sistem.

Namun, pengujian performa tahap staging menunjukkan penurunan drastis pada throughput, di mana thread carrier OS mengalami *exhaustion* dan latensi melonjak drastis, jauh lebih lambat daripada model `ThreadPoolExecutor` awal.

Setelah ditelusuri melalui Java Flight Recorder (JFR), ditemukan event:
`jdk.VirtualThreadPinned`.

**Kode Gateway Eksisting:**
```java
public class TokenValidator {
    public synchronized Claims validateAndEnrich(String token) {
        // Melakukan dekripsi lokal
        byte[] key = readKeyFromHSM(); // Synchronous Socket Call ke Hardware Security Module
        return parseJwt(token, key);
    }
}
```

#### Pertanyaan Diagnostik & Solusi:
1. Jelaskan fenomena *Virtual Thread Pinning* ke *Carrier Thread*. Mengapa penggunaan blok `synchronized` yang membungkus pemanggilan I/O blocking (`readKeyFromHSM()`) melumpuhkan mekanisme *cooperative scheduling* dari Project Loom?
2. Apa perbedaan mendasar antara *state saving* virtual thread di Java Heap Memory vs Platform Thread di OS Stack?
3. Formulasikan rencana refaktorisasi arsitektur untuk mengeleminasi pinning tersebut tanpa merusak invariansi thread-safety, dan evaluasi kapan sistem harus tetap memilih Reactive Core (seperti Netty) daripada Virtual Threads.

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Resilient Lock-Free Bounded Ring Buffer dengan Backpressure & Zero-Allocation Semantics

#### Problem Statement
Dalam arsitektur pipeline pemrosesan data real-time berbasis streaming, dependensi pada antrean bawaan Java seperti `ArrayBlockingQueue` menimbulkan degradasi performa drastis akibat kontensi *heavyweight lock* (menggunakan satu atau dua instance `ReentrantLock`), dan `LinkedBlockingQueue` menghasilkan alokasi memori berlebih (`Node` objects) yang memicu siklus GC Stop-The-World (STW).

Anda ditugaskan oleh Chief Architect untuk membangun modul antrean throughput ultra-tinggi: **`LockFreeRingBuffer<E>`**. Modul ini harus mampu memfasilitasi komunikasi transfer pesan dari banyak thread produsen (*Multi-Producer*) ke satu atau banyak thread konsumen (*Multi-Consumer* atau MPMC).

#### Spesifikasi dan Requirements
1. **Ring Buffer Structure**:
   - Struktur data harus berbasis array dengan ukuran tetap (*fixed-capacity*), berukuran *power-of-two* (misal: 1024, 2048, 65536) agar operasi modulo dapat digantikan oleh operasi bitwise masking (`sequence & (capacity - 1)`).
2. **Lock-Free Concurrency Mechanism**:
   - Tidak boleh menggunakan kata kunci `synchronized` atau kelas eksplisit dari paket `java.util.concurrent.locks.*`.
   - Mutasi pointer/indeks harus sepenuhnya mengandalkan manipulasi memori atomik berbasis CAS menggunakan `VarHandle` atau kelas atomik dari `java.util.concurrent.atomic`.
3. **Penyelarasan Cache Line (Mitigasi False Sharing)**:
   - Head sequence, Tail sequence, dan status pendukung kritis lainnya harus dipisahkan dengan padding cache line (baik manual padding array bytes maupun memanfaatkan `@Contended`) untuk mencegah degradasi performa L1/L2/L3 cache bouncing.
4. **Metode Utama yang Wajib Diimplementasikan**:
   - `boolean offer(E element)`: Non-blocking write. Menghasilkan `false` jika ring buffer penuh (menerapkan immediate backpressure signal).
   - `E poll()`: Non-blocking read. Menghasilkan `null` jika ring buffer kosong.
   - `int size()`: Mengembalikan estimasi elemen aktif secara akurat dan atomik.
   - `boolean isFull()` dan `boolean isEmpty()`.
5. **Zero-Allocation Execution Path**:
   - Setelah inisialisasi awal, operasi `offer()` dan `poll()` dilarang keras mengalokasikan objek baru di Java Heap (Zero heap-allocation during steady-state). Hindari penggunaan primitive auto-boxing.

#### Batasan Teknis (Constraints)
- Java 17+ atau Java 21+.
- Tidak boleh menggunakan library eksternal (Dilarang menggunakan LMAX Disruptor, Agrona, JCTools, Guava, atau Netty). Kode harus 100% Core Java.
- Harus tahan terhadap ancaman instruction reordering pada arsitektur non-TLO (seperti ARM64) dengan menyertakan semantik akses memori yang benar (Acquire/Release atau Volatile semantics via `VarHandle`).

#### Expected Delivery
1. Kode lengkap kelas `LockFreeRingBuffer<T>` yang bersih, terdokumentasi, dan lolos uji kompilasi.
2. Kelas pengujian konkurensi komprehensif (`LockFreeRingBufferStressTest`) yang mengeksekusi 10 produsen dan 10 konsumen secara konkuren menggunakan `CountDownLatch` untuk start bersamaan, memverifikasi tidak ada data yang hilang (*lost updates*), tidak terjadi double processing, dan tidak terjadi *deadlock/livelock*.
3. Analisis kompleksitas waktu dan memori, serta penjelasan tertulis bagaimana *memory ordering semantics* (`VarHandle.setRelease`, `VarHandle.getAcquire`, dll.) ditegakkan di dalam kode Anda.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk menguji kesiapan arsitektural dan teknis Anda sebelum melangkah ke bab implementasi sistem terdistribusi.

### Saya harus memahami:
- [ ] Aturan spesifik Java Memory Model (JMM) yang mendefinisikan batas relasi *Happens-Before* (transitivitas, program order rule, volatile variable rule, monitor lock rule).
- [ ] Perbedaan internal antara model memori CPU (store buffers, invalidation queues) dengan JMM abstraction.
- [ ] Cara kerja state tracking pada `AbstractQueuedSynchronizer` (AQS) dalam mengelola sinkronisasi mode `Exclusive` vs `Shared`.
- [ ] Alasan mengapa `Thread.sleep()` tidak melepaskan monitor lock yang sedang dipegang, sedangkan `Object.wait()` melepaskannya.
- [ ] Detail siklus hidup dan strategi sizing *carrier threads* pada arsitektur Java 21 Virtual Threads (Project Loom).
- [ ] Dampak kontensi memori pada struktur data *concurrent* (misal: Segment-stripping pada `LongAdder` vs CAS loop terpusat pada `AtomicLong`).
- [ ] Konsekuensi operasional dari berbagai kebijakan penolakan task (`AbortPolicy`, `CallerRunsPolicy`, `DiscardPolicy`, `DiscardOldestPolicy`) pada `ThreadPoolExecutor`.

### Saya tidak perlu menghafal:
- [ ] Nilai exact konstanta flag biner/hexadecimal bitmask internal di dalam kode sumber kelas AQS atau `ThreadPoolExecutor`.
- [ ] Opcodes mesin native CPU (seperti assembly mnemonic x86/ARM) untuk setiap instruksi memory fence (`MFENCE`, `SFENCE`, `DMB`).
- [ ] Kode sumber mentah native C++ implementasi HotSpot JVM untuk Object Monitor (`objectMonitor.cpp`).
- [ ] Nomor JEP (Java Extension Proposal) historis secara spesifik, cukup pahami mekanisme kapabilitas fiturnya.

### Saya harus bisa melakukan:
- [ ] Menganalisis file Java Thread Dump mentah (dari `jcmd <pid> Thread.dump_to_file` atau `jstack`) untuk mengisolasi root-cause deadlock atau monitor contention dalam waktu kurang dari 15 menit.
- [ ] Menggunakan tools telemetri dan profiling lanjutan (Java Flight Recorder / JDK Mission Control) untuk mendeteksi event *thread allocation rate*, *lock contention duration*, dan *virtual thread pinning*.
- [ ] Mendesain dan mengimplementasikan *resilient custom thread pool* dengan bounded queue, reject handler, thread factory dengan nama terstandarisasi, dan shutdown hook gracefully (`awaitTermination` lifecycle).
- [ ] Menulis algoritma struktur data *non-blocking* atau *lock-free* sederhana menggunakan primitif CAS (`VarHandle` atau `Atomic*FieldUpdater`) dengan semantic ordering yang tepat (*opaque*, *acquire/release*, *volatile*).
- [ ] Mendeteksi bug konkurensi tersembunyi (*race conditions*, *visibility issues*, *stale cache*, *thread starvation*) melalui review kode statis arsitektural.