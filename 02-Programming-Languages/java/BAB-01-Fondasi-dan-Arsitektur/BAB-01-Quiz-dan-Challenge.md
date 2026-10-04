# BAB 01: Quiz, Challenge, & Knowledge Check
**JVM Deep Dive & Fondasi Java Modern**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi JVM Runtime Data Areas & Memory Layout**  
   Jelaskan secara mendalam perbedaan struktural, siklus hidup, dan manajemen memori antara *JVM Stack*, *Heap*, *Metaspace*, dan *Native/Off-Heap Memory*. Mengapa sejak Java 8 `PermGen` dihapus dan digantikan oleh `Metaspace`, serta bagaimana JVM menangani metadata class jika batas kapasitas native memory tercapai?

2. **Parent-Delegation Model & Mekanisme Class Loading**  
   Uraikan tiga fase siklus hidup class loading (*Loading*, *Linking* [Verification, Preparation, Resolution], dan *Initialization*). Jelaskan bagaimana prinsip *Parent-Delegation Model* bekerja via `Bootstrap`, `Platform`, dan `Application ClassLoader`. Sebutkan dua skenario arsitektural enterprise di mana delegasi ini sengaja dilanggar (*bypassed/inverted*), serta jelaskan mekanismenya!

3. **Eksekusi Bytecode, JIT Tiered Compilation, & Deoptimasi**  
   Bagaimana alur kerja eksekusi kode dari bytecode via *Interpreter*, *Tier 1-3 C1 Compiler (Client)*, hingga *Tier 4 C2 Compiler (Server)*? Apa yang dimaksud dengan *Profiling Counters* (Method Entry Counter & Backedge Counter), serta kondisi apa yang memaksa HotSpot JVM melakukan *On-Stack Replacement* (OSR) dan *Deoptimization* (mengembalikan compiled machine code ke interpreted mode)?

4. **Modern Java Data Modeling: Bytecode Representation of Records & Pattern Matching**  
   Secara semantik dan representasi bytecode, jelaskan perbedaan mendasar antara class konvensional, class immutable manual (final class + final fields), dan Java `record` (JEP 395). Bagaimana JVM mengoptimalkan eksekusi pattern matching (`instanceof` dan `switch` pattern) di level instruksi bytecode dibandingkan konstruksi `if-else` bertingkat tradisional?

5. **Java Memory Model (JMM), Cache Coherence, & `volatile` Semantics**  
   Jelaskan konsep relasi *Happens-Before* dalam JMM. Mengapa deklarasi `volatile` menjamin *visibility* dan *ordering* (mencegah *instruction reordering* melalui CPU Memory Barrier / Fence: `LoadLoad`, `StoreStore`, `LoadStore`, `StoreLoad`), tetapi tidak menjamin *atomicity* pada operasi compound seperti `count++`? Hubungkan jawaban Anda dengan arsitektur CPU multicore dan cache protocol (MESI/MOESI).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Safepoint Mechanism & Latency Inversion**  
   Jelaskan secara teknis bagaimana HotSpot menghentikan semua Java threads untuk operasi *Stop-The-World* (STW) seperti GC phase, biased lock revocation, atau code deoptimization via *Safepoint Polling*. Mengapa *counted loops* (misal: `for (int i=0; i < Integer.MAX_VALUE; i++)`) tanpa safepoint poll dapat menyebabkan latency spike global yang parah (*Time-To-Safepoint / TTSP issue*), dan bagaimana compiler flag modern (`-XX:+UseCountedLoopSafepoints` / Loop Strip Mining) mengatasinya?

2. **Escape Analysis & Scalar Replacement**  
   Jelaskan bagaimana C2 JIT Compiler menentukan apakah suatu object *escapes* dari method scope melalui *Escape Analysis* (*NoEscape*, *ArgEscape*, *GlobalEscape*). Jika suatu object terbukti *NoEscape*, bagaimana teknik *Scalar Replacement* dan *Lock Elimination* bekerja? Mengapa alokasi object pada kasus tersebut secara teknis tidak pernah masuk ke Eden Space pada Heap?

3. **G1 GC Memory Abstraction: Card Table & Remembered Sets (RSet)**  
   Pada Garbage Collector modern berbasis region seperti G1 GC, bagaimana sistem melacak referensi antar-region (*cross-region references*) tanpa harus melakukan *full heap scanning*? Jelaskan fungsi teknis dari *Card Table*, *Write Barriers*, dan *Remembered Sets (RSet)*, serta apa yang dimaksud dengan fenomena *Floating Garbage* saat concurrent marking berlangsung!

4. **Off-Heap Memory Leaks & DirectBuffer Deallocation Lifecycle**  
   Ketika mengalokasikan memori via `ByteBuffer.allocateDirect(size)`, data disimpan di luar heap JVM. Jelaskan bagaimana HotSpot mengelola siklus hidup memori native ini melalui `java.lang.ref.Cleaner` (atau `sun.misc.Cleaner`). Mengapa pemanggilan `System.gc()` terkadang menjadi satu-satunya pemicu pembersihan direct memory pada implementasi lama, dan mengapa penggunaan unsafe pointer/Foreign Function & Memory API (Panama) jauh lebih deterministik?

5. **JVM Class Transformation & Instrumentation Limits**  
   Dalam konteks Java Instrumentation API (`java.lang.instrument`), jelaskan perbedaan mendasar antara `redefineClasses` dan `retransformClasses`. Apa batasan struktural yang ditetapkan JVM terhadap modifikasi bytecode saat runtime (misal: penambahan instance field, perubahan hirarki inheritance, atau penghapusan method), dan apa konsekuensi crash/error di level Native OS jika batasan tersebut dilanggar melalui manipulasi pointer level rendah?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden TTSP (Time-To-Safepoint) Latency Spike di Sistem Kliring Finansial
* **Konteks:** Sebuah microservice order-matching engine berbasis Java 21 berjalan dengan 64GB Heap dan G1 GC. Metric APM menunjukkan bahwa durasi *GC Pause Time* tercatat hanya 20ms, namun p99.99 end-to-end response time melonjak hingga 4500ms secara berkala.
* **Analisis Log:** Flag `-XX:+PrintSafepointStatistics` (atau via JFR event `jdk.SafepointBegin` / `jdk.ExecuteVMOperation`) menunjukkan:
  ```text
  Safepoint "G1CollectForAllocation", Total time for which application threads were stopped: 4.5230120 seconds, Target handling: 0.0210000 seconds
  Spinning: 4.5010000 seconds, Block: 0.0005000 seconds
  ```
* **Pertanyaan Diagnostik:**
  1. Apa perbedaan mendasar antara durasi eksekusi operasi STW aktual dengan total *Safepoint Application Stopped Time* berdasarkan log di atas?
  2. Identifikasi potensi baris kode di domain bisnis pemrosesan koleksi data/matematis yang menyebabkan fenomena *Thread Spinning / TTSP bottleneck* ini.
  3. Langkah profiling apa yang harus Anda lakukan menggunakan `async-profiler` atau JDK Flight Recorder (JFR) untuk mengisolasi thread nakal (*rogue thread*) yang menunda safepoint tersebut?

### Skenario B: Silent Memory Corruption & Race Condition pada High-Throughput In-Memory Cache
* **Konteks:** Tim backend membangun custom in-memory cache menggunakan *Ring Buffer* kustom tanpa dependensi eksternal. Struktur data memanfaatkan direct memory access menggunakan class internal atau FFM API untuk bypass GC overhead. Saat beban traffic mencapai 250.000 ops/detik di server bare-metal multi-socket (NUMA architecture), terjadi korupsi data acak dan pembacaan data basi (*stale data*) antar-CPU socket.
* **Kode Sampel:**
  ```java
  public class FastCacheEntry {
      private long sequenceId; // Write cursor
      private byte[] payload;  // Serialized data
      
      public void write(long seq, byte[] data) {
          this.payload = data;
          this.sequenceId = seq; // Marker bahwa write selesai
      }
      
      public byte[] read(long expectedSeq) {
          if (this.sequenceId == expectedSeq) {
              return this.payload; // Read operation
          }
          return null;
      }
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Dari perspektif Java Memory Model dan arsitektur CPU hardware (Store Buffer, Out-of-Order Execution, Invalidation Queues), mengapa pembacaan `this.payload` pada thread consumer dapat mengembalikan data `null` atau referensi object setengah jadi (*partially initialized*) meskipun `this.sequenceId == expectedSeq` bernilai `true`?
  2. Mengapa anomali ini lebih sering tereskalasi pada server Multi-Socket NUMA dibanding laptop development lokal developer?
  3. Bagaimana Anda merefaktor struktur tersebut menggunakan *VarHandle* (dengan memory access modes: *Release/Acquire* atau *Volatile*) atau Java 21 Memory Segment untuk menjamin zero-corruption dengan latency serendah mungkin tanpa menggunakan `synchronized`?

### Skenario C: Krisis Thread Exhaustion vs Virtual Thread Pinning di Arsitektur Cloud-Native
* **Konteks:** Sistem gateway pembayaran berbasis Spring Boot 3 & Java 21 dimigrasikan dari Classic Platform Threads (Tomcat Thread Pool) ke *Virtual Threads* (Project Loom) untuk meningkatkan throughput IO. Pasca rilis produksi, throughput justru anjlok drastis ke 100 req/detik, CPU utilization 100%, dan terjadi cascading failure (*Read Timeout* masif).
* **Temuan Diagnostik:** JFR trace menunjukkan ratusan Virtual Threads berada dalam kondisi terblokir, dan log diagnostic memperingatkan adanya *Pinned Virtual Threads*.
* **Pertanyaan Diagnostik:**
  1. Jelaskan secara mekanis bagaimana Virtual Thread dipetakan ke Carrier Thread (OS Thread/ForkJoinPool). Apa perbedaan perilaku runtime ketika Virtual Thread memblokir pada *blocking IO operation* normal vs saat ia berada dalam status *Pinned*?
  2. Jelaskan dua skenario struktural kode yang menyebabkan Virtual Thread menjadi *Pinned* (hubungkan dengan blok `synchronized`, Object monitor methods, dan JNI / Native Call invocation).
  3. Rekonstruksi arsitektur penanganan konkurensi: Jika sistem harus mengakses database RDBMS legacy melalui JDBC driver yang sarat dengan blok `synchronized`, bagaimana strategi mitigasi teknis Anda tanpa harus membatalkan migrasi ke Java 21 Virtual Threads?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Off-Heap Circular Ring Buffer dengan False Sharing Mitigation & Custom Isolation

#### Problem Statement
Anda ditugaskan merancang modul transmisi event finansial ultra-rendah latensi (*Zero-Garbage Messaging Core*) yang harus mentransmisikan data mentah per detik tanpa memicu alokasi memori di HotSpot Eden Space, kebal terhadap degradasi cache akibat *False Sharing*, serta mendukung isolasi dynamic plugin class loader yang dapat dimuat (*load*) dan dibuang (*unload*) tanpa kebocoran Metaspace.

#### Requirements
1. **Zero-Garbage Data Path:**  
   Implementasikan Ring Buffer dengan kapasitas tetap ($2^n$ slots) menggunakan Java 21 `java.lang.foreign.MemorySegment` / Foreign Function & Memory (FFM) API untuk alokasi native memory. Seluruh operasi penulisan (*push*) dan pembacaan (*poll*) pada hot path dilarang mengalokasikan object baru ke Java Heap ($0\text{ bytes/op}$).
2. **False Sharing Prevention:**  
   Pastikan write pointer (head) dan read pointer (tail) berada pada CPU Cache Line yang terisolasi secara terpisah (menggunakan manual padding 128 bytes atau `@jdk.internal.vm.annotation.Contended` yang aktif via JVM flags).
3. **Thread Safety via VarHandle:**  
   Gunakan `VarHandle` dengan semantik memory ordering yang paling efisien (*Acquire-Release semantics*) untuk sinkronisasi head dan tail cursor antar thread producer dan consumer tunggal (Single-Producer Single-Consumer / SPSC). Dilarang keras menggunakan keyword `synchronized` atau class `ReentrantLock`.
4. **Isolasi Plugin via Custom ClassLoader:**  
   Buat `HotSwapPluginClassLoader` kustom yang membaca plugin enkripsi payload secara dinamis dari file bytecode mentah (.class). Implementasikan mekanisme eksplisit untuk memastikan plugin ClassLoader dapat di-*garbage collect* sepenuhnya oleh JVM saat modul di-unload (verifikasi pembebasan Metaspace).

#### Constraints
* **Runtime:** JDK 21+.
* **Dependencies:** Murni Java Standard Library (`java.base`). Tidak diperbolehkan menggunakan dependensi pihak ketiga (LMAX Disruptor, Netty, Guava, dll).
* **JVM Flags Wajib Uji:** 
  `-XX:+UnlockExperimentalVMOptions -XX:+EnableValhalla` (opsional), `-XX:+UseZGC -XX:+ZGenerational` atau G1GC dengan flag visualisasi tracking memory: `-Xlog:gc*,gc+safepoint=info:stdout`.

#### Expected Output & Verification
* **JMH Benchmark:** Sertakan benchmark harness berbasis *Java Microbenchmark Harness* (JMH) yang menguji *throughput* dan *allocation rate* (`org.openjdk.jmh.annotations.CompilerControl`, `@AuxCounters`, profiler GC `org.openjdk.jmh.profile.GCProfiler`). Target: $0 \text{ B/op}$ allocation pada hot path.
* **Metaspace Leak Test:** Program eksekutor yang memuat 1.000 iterasi modifikasi class plugin secara berulang, mengeksekusinya, membuang referensinya, dan membuktikan melalui `ManagementFactory.getMemoryMXBean().getNonHeapMemoryUsage()` bahwa ukuran Metaspace stabil dan tidak mengalami `java.lang.OutOfMemoryError: Metaspace`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi memori HotSpot JVM: Struktur Object Header (Mark Word, Klass Pointer, Padding, Payload) pada arsitektur 64-bit (Compressed OOPs on vs off).
- [ ] Alur transisi dari Bytecode execution ke C1/C2 JIT compilation, On-Stack Replacement (OSR), dan kriteria deoptimasi code cache.
- [ ] Prinsip JMM (Java Memory Model): Aksi inter-thread, urutan program (*Program Order*), urutan sinkronisasi (*Synchronization Order*), serta relasi *Happens-Before*.
- [ ] Semantik dan trade-off Garbage Collector modern: Generational G1 GC, ZGC (Generational ZGC), dan Shenandoah GC (khususnya *colored pointers*, *load barriers*, dan *concurrent compaction*).
- [ ] Perilaku Virtual Threads (Project Loom): Perbedaan mendasar antara unmounting/mounting continuations pada I/O blocking vs kondisi *thread pinning* (monitors & native calls).
- [ ] Arsitektur CPU hardware modern: False Sharing, Cache Line (64 bytes), L1/L2/L3 cache latency hierarchy, dan Store Buffer.

### Saya tidak perlu menghafal:
- [ ] Hexadecimal opcodes spesifik dari ratusan instruksi JVM Bytecode (misal: nilai hex opcode `invokevirtual` vs `invokestatic`). Cukup gunakan `javap -c -v` untuk inspeksi.
- [ ] Detail implementasi source code C++ internal HotSpot JVM (`hotspot/src/share/vm/*`), kecuali abstraksi arsitektur dasarnya.
- [ ] Offset byte eksak dari platform-dependent mark word fields (cukup pahami fungsi bit-level locking tags, biased lock bits, age bits, dan identity hashcode).

### Saya harus bisa melakukan:
- [ ] Melakukan dekonstruksi dan analisis file `.class` menggunakan command line `javap -v -p` untuk membaca instruksi bytecode, constant pool, dan stack map frames.
- [ ] Mengonfigurasi dan menganalisis profiling performa aplikasi runtime menggunakan **JDK Flight Recorder (JFR)** dan **JDK Mission Control (JMC)** untuk mendiagnosa safepoint issues, memory allocation spikes, dan lock contention.
- [ ] Menggunakan tools diagnosa CLI bawaan JDK: `jcmd`, `jstack`, `jmap`, `jstat`, dan membaca output log GC terpadu modern (`-Xlog:gc*`).
- [ ] Membangun program konkurensi bebas race-condition tanpa locking konvensional menggunakan Java `VarHandle` dengan *Acquire/Release* ordering.
- [ ] Mengalokasikan, memanipulasi, dan membebaskan native memory secara aman menggunakan **Foreign Function & Memory API (FFM - Java 21+)** tanpa risiko crash fatal segmentation fault pada OS.
- [ ] Mengisolasi ClassLoader leak pada server container melalui analisis Heap Dump (.hprof) di Eclipse Memory Analyzer (MAT) dengan fokus penelusuran *ClassLoader GC Roots*.