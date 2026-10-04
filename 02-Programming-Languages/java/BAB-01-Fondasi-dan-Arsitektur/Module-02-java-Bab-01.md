# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive JVM, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Eksekusi JVM**: Mengidentifikasi fase kompilasi *Tiered Compilation* (Interpreter, C1, C2), deoptimasi, serta mekanisme *On-Stack Replacement* (OSR) secara langsung dari *assembly* dan *JIT log*.
2. **Menguasai Java Memory Model (JMM) Lanjutan**: Menjelaskan semantik formal *JSR-133*, aturan *Happens-Before*, *CPU Cache Coherence* (protokol MESI), *Memory Barriers/Fences*, dan eliminasi *False Sharing* menggunakan padding/`@Contended`.
3. **Mengoptimalkan Manajemen Memori Tingkat Lanjut**: Membandingkan algoritma *Garbage Collection* kontemporer (G1, ZGC, Shenandoah), mengimplementasikan alokasi memori *Off-Heap* melalui *Foreign Function & Memory API* (Project Panama), dan meniadakan degradasi performa akibat *GC Pause*.
4. **Menerapkan Runtime Concurrency Modern**: Mengintegrasikan *Virtual Threads* (Project Loom), memetakan perilaku *Carrier Threads* (`ForkJoinPool`), menghindari *thread pinning*, dan memanfaatkan `VarHandle` untuk operasi atomik non-blocking tanpa overhead `Unsafe`.
5. **Melakukan Profiling dan Diagnostik Sistem Produksi**: Melacak masalah latensi ekstrim, *Metaspace leak*, dan saturasi memori menggunakan *JDK Flight Recorder* (JFR), *Async-Profiler*, dan analisis *core dump*.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib memiliki pemahaman solid mengenai:
* Konsep dasar OOP, thread dasar (`java.lang.Thread`, `Runnable`), dan eksekusi Java standar (JDK, JRE, JVM).
* Struktur dasar sistem operasi: *Virtual Memory*, *Paging*, *Kernel vs User Space Context Switch*, dan arsitektur CPU x86_64/ARM64 (L1/L2/L3 Caches).
* Telah menguasai Modul 01: Setup JDK 21 LTS, sintaks dasar Java modern, dan kompilasi manual menggunakan CLI (`javac`, `jar`, `java`).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur runtime Java modern didesain untuk menjembatani kode berorientasi objek tingkat tinggi dengan instruksi mikroprosesor native secara adaptif. HotSpot JVM mengorkestrasi tiga komponen inti: **Execution Engine**, **Memory Subsystem**, dan **Thread Scheduler**.

```
+-----------------------------------------------------------------------------------+
| HotSpot JVM Runtime                                                               |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Execution Engine                                                            |  |
|  |  +------------------+    +-------------------+    +----------------------+  |  |
|  |  |   Interpreter    |--->|   C1 (Client)     |--->|     C2 (Server)      |  |  |
|  |  |  (Bytecode -> ASM) |    |  Tier 1, 2, 3 JIT |    |  Tier 4 (Heavy Opt)  |  |  |
|  |  +------------------+    +-------------------+    +----------------------+  |  |
|  |           ^                        | (Deopt Trap)            |              |  |
|  |           +------------------------+-------------------------+              |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Java Memory Model (JMM) & Subsystem Memori                                  |  |
|  |  +---------------------------+  +----------------------------------------+  |  |
|  |  | Heap Space                |  | Non-Heap / Off-Heap                    |  |  |
|  |  | - Young Gen (Eden, S0, S1)|  | - Metaspace (Klass Metaspaces)         |  |  |
|  |  | - Old Gen (Tenured)       |  | - CodeCache (JIT native code)          |  |  |
|  |  | - ZGC / G1 Regions        |  | - Arena / Off-Heap (Panama FFM)        |  |  |
|  |  +---------------------------+  +----------------------------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Thread Subsystem (Project Loom & OS Threading)                              |  |
|  |  [Virtual Thread] [Virtual Thread] [Virtual Thread]  (Unmounted/Mounted)    |  |
|  |           \              |              /                                   |  |
|  |   +-----------------------------------------------+                         |  |
|  |   | Carrier Threads Pool (ForkJoinPool - OS-Bound)|                         |  |
|  |   +-----------------------------------------------+                         |  |
|  |             |                       |                                       |  |
|  |      [Kernel Thread]         [Kernel Thread]                                |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### A. HotSpot Tiered Compilation
HotSpot menggunakan pendekatan kompilasi bertingkat (*Tiered Compilation*) untuk menyeimbangkan kecepatan startup dan throughput jangka panjang:
1. **Tier 0 (Interpreted Code)**: Bytecode dieksekusi langsung oleh interpreter. JVM menghitung *invocation counter* dan *backedge counter* untuk mendeteksi *hot methods* atau loop.
2. **Tier 1 (Simple C1)**: Kompilasi JIT tanpa *profiling*. Digunakan jika C2 overload atau kode sangat sepele.
3. **Tier 2 (Limited C1 Profiling)**: Kompilasi native dengan instrumentasi profil dasar.
4. **Tier 3 (Full C1 Profiling)**: Kompilasi native dengan *full profiling* (tipe kelas aktual dari *polymorphic calls*, percabangan branch yang sering diambil).
5. **Tier 4 (C2 Server Compiler)**: Membaca data profil dari Tier 3 untuk melakukan optimasi radikal:
   * **Inlining**: Mengganti *method invocation* dengan isi method itu sendiri, menghilangkan overhead *call stack* dan membuka peluang optimasi lain.
   * **Escape Analysis**: Memeriksa apakah *lifetime* sebuah objek melampaui stack lokal atau thread saat ini. Jika tidak (*NoEscape*), JVM melakukan **Scalar Replacement** (mengurai objek menjadi variabel primitif di CPU register/stack) dan mengeliminasi alokasi di heap (*Lock Elision* & *Elimination of Allocations*).
   * **Loop Unrolling & Vectorization**: Memperluas loop dan memanfaatkan instruksi SIMD (Single Instruction, Multiple Data seperti AVX-512) pada CPU.
   * **Deoptimization**: Jika asumsi profil terlanggar (misalnya, kelas baru dimuat dan mematahkan optimasi *monomorphic call*), JVM melakukan *Uncommon Trap*, membatalkan kode native C2, dan kembali ke Tier 0 / Interpreter.

#### B. Java Memory Model (JMM) & CPU Architecture
JMM mereduksi ketidakpastian perangkat keras multi-core modern. CPU mengeksekusi instruksi secara *out-of-order* dan menggunakan *store buffers* serta hirarki cache lokal (L1, L2) yang tidak langsung tersinkronisasi ke memori utama (RAM).
* **Happens-Before Relationship**: Menjamin bahwa aksi tulis oleh suatu thread pada memori terlihat (*visible*) oleh aksi baca thread lain tanpa instruksi kompilator yang mengubah urutan alur data secara keliru.
* **Mekanisme Volatile**:
  * Operasi baca variabel `volatile` bertindak sebagai *Acquire Barrier*: instruksi pembacaan memori setelahnya tidak dapat dipindahkan ke sebelum instruksi ini.
  * Operasi tulis variabel `volatile` bertindak sebagai *Release Barrier*: instruksi penulisan memori sebelumnya tidak dapat dipindahkan ke setelah instruksi ini.
  * Pada level x86_64, ini diimplementasikan menggunakan instruksi berbiaya tinggi seperti `lock addl` atau instruksi *memory fence* (`mfence`) yang memaksa CPU *drain store buffer*.

#### C. Garbage Collection: G1 vs ZGC
1. **Garbage-First (G1 GC)**:
   * Membagi heap menjadi ribuan Region berukuran tetap (1 MB - 32 MB).
   * Generational: Membedakan Eden, Survivor, dan Old regions.
   * Menggunakan algoritma *Snapshot-At-The-Beginning* (SATB) via *write barriers*. Menghentikan aplikasi (*Stop-The-World*) selama penandaan awal (*Initial Mark*) dan evakuasi region (*Mixed GC*). Pause time berkisar antara puluhan milidetik hingga ratusan milidetik.
2. **Z Garbage Collector (ZGC)**:
   * Bersifat *Concurrent, Low-Latency GC* dengan pause time terjamin di bawah 1 milidetik (< 1ms), tidak terpengaruh oleh ukuran heap (teruji hingga 16 TB).
   * **Colored Pointers**: Metadata referensi (Marked0, Marked1, Remapped) disimpan langsung pada bit referensi pointer itu sendiri (memanfaatkan 46-bit pointer addressing pada arsitektur 64-bit).
   * **Load Barriers**: Ketika aplikasi membaca referensi objek dari heap, *load barrier* mencegat referensi tersebut. Jika objek sedang dipindahkan (*relocating*), thread aplikasi secara transparan mengarahkan pointer ke lokasi baru (*self-healing*) tanpa menunggu fase GC selesai.

#### D. Virtual Threads (Project Loom) Internals
Virtual Threads adalah thread ringan (*lightweight threads*) yang dikelola langsung oleh JVM, bukan 1:1 terhadap OS Kernel Thread.
* Virtual Thread dieksekusi di atas *Carrier Thread* (standarnya adalah `ForkJoinPool` berukuran jumlah CPU core).
* Ketika kode pada Virtual Thread menemui operasi I/O pemblokir (misal: `Socket.read()`, `Thread.sleep()`), JVM memanfaatkan mekanisme internal `Continuation.yield()`. Virtual thread melakukan *unmount* dari Carrier Thread.
* Stack frame dari Virtual Thread dipindahkan dari Carrier Thread stack ke dalam JVM Heap. Carrier Thread bebas mengeksekusi Virtual Thread lain. Ketika I/O selesai via OS *kqueue/epoll*, thread dijadwalkan ulang dan melakukan *mount* kembali ke Carrier Thread yang tersedia.
* **Thread Pinning**: Terjadi jika Virtual Thread diblokir di dalam blok `synchronized` atau memanggil native call (JNI). Stack frame tidak bisa di-*unmount* ke heap, memblokir Carrier Thread yang mendasarinya dan memicu degradasi kapasitas sistem secara masif. Solusi: Gunakan `ReentrantLock`.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise / Lanjutan |
| :--- | :--- | :--- |
| **Model Eksekusi Thread** | 1 Platform Thread = 1 OS Kernel Thread (~1MB stack, overhead context switch kernel tinggi, batas ~5.000 thread). | Virtual Threads (Lightweight, ~1KB footprint, jutaan konkurensi I/O-bound secara simultan). |
| **Alokasi Memori** | Mengandalkan Heap murni. Objek besar memicu frekuensi GC tinggi dan fragmentasi memori. | Hibrida: Heap untuk domain logic, Off-Heap (`Foreign Function & Memory API`) untuk caching besar dan transfer buffer berkecepatan tinggi. |
| **Sinkronisasi Data** | `synchronized` masif dan `AtomicReference` berbiaya wrapping objek tinggi. | `VarHandle` atau alokasi bebas lock (Lock-Free CAS), eliminasi *False Sharing* via padding cache line (64-byte boundary). |
| **Garbage Collection** | Konfigurasi GC default (Parallel/Serial) yang menyebabkan STW (*Stop-the-world*) ratusan milidetik. | ZGC Generational terkonfigurasi dengan limit latensi sub-milidetik untuk P99/P99.9 SLA kencang. |
| **Interoperabilitas Native** | JNI (*Java Native Interface*) dengan boilerplate C/C++ rapuh dan overhead marshalling tinggi. | FFM API (Project Panama: `Arena`, `MemorySegment`, `Linker`) dengan keamanan tipe dan performa setara C. |

---

### 5. How (Workflow detail)

Berikut alur eksekusi memori dan lifecycle eksekusi instruksi Java dari kode sumber ke native CPU:

```
[Java Source (.java)]
        |
        v (javac compiler)
[JVM Bytecode (.class)]
        |
        v (Class Loader Subsystem: Loading -> Linking -> Initialization)
[HotSpot Runtime Execution Engine]
        |
        +---> Interpreted Execution (Tier 0: Update Call/Loop Counters)
        |           |
        |           v (Threshold Exceeded: Method Profiling)
        +---> C1 Compiler (Tier 1-3: Quick native compilation + inline caches)
        |           |
        |           v (High Traffic / Complex Paths detected)
        +---> C2 Compiler (Tier 4: Escape Analysis -> Vectorization -> Loop Peeling)
                    |
                    v (CPU executes optimized machine instructions)
              [L1/L2/L3 Hardware Cache]
                    | (Cache Coherence - MESI Protocol)
              [Main Memory (RAM)]
```

Langkah kerja diagnostik performa tingkat rendah:
1. **Analisis Hot Spot**: Gunakan *Async-Profiler* untuk mengekstrak *FlameGraph* kompilasi CPU dan alokasi memori tanpa bias *SafePoint*.
2. **Inspeksi Assembly**: Tambahkan flag `-XX:+PrintAssembly` menggunakan HSDIS (*HotSpot Disassembler*) untuk mengonfirmasi apakah loop mengalami vektorisasi SIMD dan eliminasi boundary checking.
3. **Audit SafePoint**: Evaluasi waktu jeda aplikasi akibat thread menunggu mencapai status SafePoint via flag `-Xlog:safepoint=debug`.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi JMM: Kantor Pos Lokal vs Arsip Pusat
Bayangkan CPU Core sebagai manajer regional independen, dan Cache L1/L2 adalah meja kerja pribadinya, sedangkan RAM adalah Lemari Arsip Pusat.
* Jika Manajer A mengubah isi dokumen di mejanya tanpa mengabari orang lain, Manajer B di ruangan lain yang memeriksa mejanya sendiri akan melihat data usang (*stale data*).
* Penandaan dokumen dengan cap **`volatile`** mewajibkan manajer:
  1. Segera menyalin dokumen dari mejanya ke Lemari Arsip Pusat begitu ada perubahan (*Flush* / *Write-Release*).
  2. Membuang salinan di mejanya dan selalu berjalan ke Lemari Arsip Pusat setiap kali ingin membaca (*Invalidate* / *Read-Acquire*).

#### B. Cache Line & False Sharing
CPU membaca memori bukan byte demi byte, melainkan dalam blok berukuran 64 byte (*Cache Line*).

```
Arsitektur Cache Line (64 Bytes):
+---------------------------------------------------------------+
|                      Cache Line (64 Bytes)                    |
|  +-----------------------------+---------------------------+  |
|  |       Variabel X (8B)       |      Variabel Y (8B)      |  |
|  +-----------------------------+---------------------------+  |
+---------------------------------------------------------------+
               ^                               ^
               |                               |
          Core 1 Menulis                  Core 2 Menulis
```
Jika Core 1 memodifikasi `Variabel X` dan Core 2 memodifikasi `Variabel Y` yang berada dalam satu *Cache Line* 64-byte yang sama, protokol cache CPU (MESI) akan terus-menerus membatalkan (*invalidate*) seluruh baris cache tersebut antar core. Akibatnya terjadi lonjakan latensi memori secara drastis meskipun kedua thread tidak mengakses variabel yang sama (*False Sharing*).

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengendalikan JMM dan Visibilitas dengan `VarHandle`
Kode ini mendemonstrasikan manipulasi atomik dan memori tingkat rendah tanpa overhead `synchronized`, menggunakan semantic *Acquire-Release* via `VarHandle` (standar modern pengganti `sun.misc.Unsafe`).

```java
package com.enterprise.memory;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

public final class ModernVolatileState {
    private int state = 0;

    // Inisialisasi VarHandle untuk akses atomik langsung ke field 'state'
    private static final VarHandle STATE_HANDLE;

    static {
        try {
            STATE_HANDLE = MethodHandles.lookup()
                .findVarHandle(ModernVolatileState.class, "state", int.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public void updateRelease(int newValue) {
        // Menjamin seluruh mutasi memori sebelum baris ini selesai dieksekusi 
        // sebelum nilai state ditulis (Release Fence semantics)
        STATE_HANDLE.setRelease(this, newValue);
    }

    public int readAcquire() {
        // Menjamin pembacaan memori setelah baris ini tidak mendahului 
        // pembacaan nilai state (Acquire Fence semantics)
        return (int) STATE_HANDLE.getAcquire(this);
    }

    public boolean compareAndSetState(int expected, int target) {
        // Instruksi komparasi atomik (CAS) native level CPU
        return STATE_HANDLE.compareAndSet(this, expected, target);
    }
}
```

#### Practical Example: High-Throughput Ring Buffer Menggunakan Project Panama (Off-Heap) dan Cache Padding
Implementasi Ring Buffer *zero-GC off-heap* berkinerja tinggi, aman dari *False Sharing*, memanfaatkan Java 21 `Foreign Function & Memory API`.

```java
package com.enterprise.lowlatency;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

/**
 * Ring Buffer Lock-Free Off-Heap berperforma tinggi.
 * Mengalokasikan data di luar garbage-collected heap menggunakan FFM API (Project Panama).
 */
public final class OffHeapRingBuffer implements AutoCloseable {

    private static final int CAPACITY = 1024; // Harus kelipatan 2 (power-of-two)
    private static final int MASK = CAPACITY - 1;
    private static final long ELEMENT_SIZE = ValueLayout.JAVA_LONG.byteSize();
    private static final long BUFFER_SIZE = CAPACITY * ELEMENT_SIZE;

    private final Arena arena;
    private final MemorySegment nativeMemory;

    // Cache line padding untuk mencegah False Sharing antara Head dan Tail (64 bytes)
    @SuppressWarnings("unused")
    private long p0, p1, p2, p3, p4, p5, p6; // 56 bytes padding
    private volatile long head = 0L;         // 8 bytes -> Total 64 bytes
    
    @SuppressWarnings("unused")
    private long p7, p8, p9, p10, p11, p12, p13; // 56 bytes padding
    private volatile long tail = 0L;             // 8 bytes -> Total 64 bytes

    private static final VarHandle HEAD_HANDLE;
    private static final VarHandle TAIL_HANDLE;

    static {
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup();
            HEAD_HANDLE = lookup.findVarHandle(OffHeapRingBuffer.class, "head", long.class);
            TAIL_HANDLE = lookup.findVarHandle(OffHeapRingBuffer.class, "tail", long.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public OffHeapRingBuffer() {
        // Mengalokasikan arena memori native eksplisit di luar GC Heap
        this.arena = Arena.ofShared();
        this.nativeMemory = arena.allocate(BUFFER_SIZE, 64); // Aligned 64-byte untuk cacheline
    }

    public boolean offer(long value) {
        long currentTail = (long) TAIL_HANDLE.getOpaque(this);
        long currentHead = (long) HEAD_HANDLE.getAcquire(this);

        if ((currentTail - currentHead) >= CAPACITY) {
            return false; // Buffer penuh
        }

        long offset = (currentTail & MASK) * ELEMENT_SIZE;
        // Tulis langsung ke native memory tanpa alokasi objek
        nativeMemory.set(ValueLayout.JAVA_LONG, offset, value);

        // Terbitkan pointer baru ke pembaca (Release semantics)
        TAIL_HANDLE.setRelease(this, currentTail + 1);
        return true;
    }

    public long poll(long emptySentinel) {
        long currentHead = (long) HEAD_HANDLE.getOpaque(this);
        long currentTail = (long) TAIL_HANDLE.getAcquire(this);

        if (currentHead >= currentTail) {
            return emptySentinel; // Buffer kosong
        }

        long offset = (currentHead & MASK) * ELEMENT_SIZE;
        // Baca data dari native memory
        long value = nativeMemory.get(ValueLayout.JAVA_LONG, offset);

        // Majukan pointer head (Release semantics)
        HEAD_HANDLE.setRelease(this, currentHead + 1);
        return value;
    }

    @Override
    public void close() {
        // Dealokasi langsung seluruh memori off-heap deterministik tanpa menunggu GC
        if (arena.scope().isAlive()) {
            arena.close();
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Transaksi Pembayaran Skala FinTech memproses 120.000 TPS (*Transactions Per Second*) pada arsitektur microservices berbasis Java 21 dan Spring Boot. 

#### Masalah Produksi
Setiap periode transaksi puncak (*flash sale*), sistem mengalami fluktuasi latensi:
* Latensi Rata-rata: 2.1 ms.
* Latensi P99: 15 ms.
* Latensi P99.99: **Mencapai 1.850 ms (1.85 detik)**.
* Dampak: Pemutusan koneksi (*read timeout*) dari upstream API Gateway dan sistem pembayaran bank mitra, menyebabkan transaksi duplikat dan kegagalan verifikasi saldo.

#### Root Cause Analysis (Investigasi Teknis)
1. **Analisis GC Log (`-Xlog:gc*,safepoint=info:file=gc.log`)**:
   GC default yang aktif adalah G1 dengan heap 32GB (`-Xms32g -Xmx32g`). Log menunjukkan *Mixed GC* memicu pause berulang selama 300 ms - 700 ms akibat *Humongous Allocations* (banyak payload transaksi JSON berukuran > 16 MB dialokasikan langsung ke Old Generation, memicu fragmentasi region).
2. **Analisis Thread Dump via `jcmd <pid> Thread.dump_to_file`**:
   Dari 4.000 Platform Threads yang berjalan, lebih dari 3.200 thread berada dalam status `BLOCKED` atau `WAITING` di thread pool Apache Tomcat, kehabisan thread worker saat upstream database lambat.
3. **Analisis Profiling (Async-Profiler CPU & Allocation)**:
   * 40% alokasi memori dihasilkan oleh serialisasi JSON sementara yang lolos dari *Escape Analysis* C2 Compiler karena ukuran method melebihi ambang batas inlining default (`-XX:FreqInlineSize=325`).

#### Solusi Arsitektural & Hasil Pengujian
1. **Migrasi Engine Concurrency ke Virtual Threads**:
   Mengubah konfigurasi embedded server untuk menggunakan `Executors.newVirtualThreadPerTaskExecutor()`. Beban OS context switch berkurang 85%, penggunaan memory thread stack turun dari 4 GB menjadi 150 MB.
2. **Ganti Garbage Collector ke Generational ZGC**:
   Mengaktifkan ZGC modern dengan konfigurasi JVM:
   ```bash
   -XX:+UseZGC -XX:+ZGenerational -Xms32g -Xmx32g -XX:+AlwaysPreTouch
   ```
3. **Optimasi Ambang Batas Inlining JIT C2**:
   Menyesuaikan profil HotSpot untuk method krusial:
   ```bash
   -XX:MaxInlineLevel=15 -XX:FreqInlineSize=600
   ```

#### Hasil Pasca-Implementasi
* Latensi Rata-rata: 1.2 ms (-42%).
* Latensi P99: 2.4 ms (-84%).
* **Latensi P99.99: Stabil di 4.8 ms (Turun dari 1.850 ms -> Reliabilitas 99.999% tercapai)**.
* Pause GC terpanjang yang tercatat dalam log ZGC turun drastis ke **0.32 ms**.

---

### 9. Trade-offs

| Pendekatan / Komponen | Keuntungan (Pros) | Konsekuensi & Keterbatasan (Cons) | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Generational ZGC** | Latensi *pause* deterministik (<1 ms), tidak terpengaruh besarnya heap. Skalabilitas tinggi. | Throughput throughput mentah turun sekitar 2-8% akibat *load barriers*, konsumsi CPU tambahan untuk GC background worker. | Layanan perbankan, sistem perdagangan frekuensi tinggi (HFT), payment processing dengan SLA ketat. |
| **G1 GC** | Throughput keseluruhan lebih tinggi dibanding ZGC pada skenario komputasi berat, penggunaan memori tambahan lebih rendah. | Latensi *Stop-The-World* tidak dapat dihindari (berkisar antara 10 ms hingga ratusan ms). Sulit dikontrol pada heap masif. | Batch processing, ETL pipeline, pelaporan data non-real-time di mana throughput > latensi. |
| **Virtual Threads (Loom)** | Pemrograman konkurensi gaya sekuensial yang bersih, alokasi thread tak terbatas untuk tugas I/O bound. | Tidak memberikan manfaat pada beban kerja CPU-bound (hashing, enkripsi). Risiko *carrier thread starvation* jika terjadi *pinning*. | REST APIs, GraphQL engines, gateway perantara microservices yang didominasi integrasi HTTP/DB/I/O. |
| **Off-Heap Memory (FFM API)** | Membebaskan JVM Heap dari GC overhead, transfer data zero-copy ke native OS interface atau GPU. | Wajib manajemen siklus hidup memori secara manual (`Arena.close()`). Bug dapat mengakibatkan kebocoran memori OS (*native leak*) yang tidak terlacak oleh `jmap`. | In-memory cache berukuran besar (>50GB), network buffers (Netty alternatives), pengolahan array multi-dimensi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Virtual Thread Pinning via `synchronized`
* **Gejala**: Throughput sistem anjlok ketika Virtual Threads diaktifkan; Carrier Threads macet di 100% atau thread pool starvation.
* **Akar Masalah**: Blok `synchronized` yang membungkus pemanggilan I/O memblokir pelepasan Virtual Thread dari Carrier Thread (*pinning*).
* **Solusi**: Ganti struktur `synchronized` dengan `java.util.concurrent.locks.ReentrantLock`.
* **Deteksi JVM**: Jalankan aplikasi dengan flag diagnostik:
  `-Djdk.tracePinnedThreads=full`

#### 2. Metaspace OutOfMemoryError (`java.lang.OutOfMemoryError: Metaspace`)
* **Gejala**: Aplikasi crash setelah berjalan beberapa hari di lingkungan produksi, terutama pasca redeploy dinamis atau pembuatan proxy class massal.
* **Akar Masalah**: ClassLoader leak. Framework seperti reflection, CGLIB, atau serialization dinamis membuat *dynamic proxies* tanpa batasan, sedangkan ClassLoader lama tetap terikat di heap oleh static reference, sehingga metadatanya di Metaspace tidak dapat dibersihkan.
* **Investigasi**:
  ```bash
  jcmd <PID> VM.metaspace
  jcmd <PID> GC.class_histogram
  ```

#### 3. Premature Promotion ke Old Generation
* **Gejala**: Frekuensi Major/Old GC meningkat secara anomali padahal beban kerja normal.
* **Akar Masalah**: Ukuran Survivor Space terlalu kecil atau `-XX:MaxTenuringThreshold` diset terlalu rendah. Objek berumur pendek meluap langsung dari Eden ke Tenured space (*premature promotion*).
* **Solusi**: Analisis via `-Xlog:gc+age=trace`. Perbesar Survivor Ratio (`-XX:SurvivorRatio=6`) atau naikkan ukuran New Generation (`-XX:NewRatio`).

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis aplikasi Java 21+ ke lingkungan produksi:

- [ ] **Alokasi Heap Simetris**: Set `-Xms` sama persis dengan `-Xmx` untuk mencegah latensi JVM meminta ekspansi memori dinamis ke OS saat beban melonjak.
- [ ] **Pre-Touch Memory Allocation**: Gunakan `-XX:+AlwaysPreTouch` agar JVM langsung menginisialisasi seluruh halaman memori fisik saat *startup*, memitigasi latensi *Page Fault* saat traffic puncak.
- [ ] **Modern GC Selection**: Gunakan `-XX:+UseZGC -XX:+ZGenerational` jika beban kerja menuntut SLA P99 di bawah 10ms.
- [ ] **Crash Dump Diagnostik Otomatis**: Pastikan flag diagnostik fatal diaktifkan:
  ```bash
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/var/log/dumps/java_oom.hprof \
  -XX:+ExitOnOutOfMemoryError
  ```
- [ ] **Audit Thread Safety & False Sharing**: Beri padding manual atau gunakan `-XX:-RestrictContended` dan tambahkan anotasi `jdk.internal.vm.annotation.Contended` pada variabel atomic yang diakses bersamaan secara masif.
- [ ] **Validasi Virtual Thread Pinned**: Pastikan parameter `-Djdk.tracePinnedThreads=short` aktif di environment staging/stress-test.
- [ ] **Explicit Headless Mode**: Tambahkan `-Djava.awt.headless=true` untuk server yang tidak memerlukan subsistem grafis GUI guna menghemat native memory footprint.

---

### 12. Hands-on Practice

Simpan seluruh hasil latihan di folder workspace: `hands-on/m02/`

#### Skenario Latihan
Mengidentifikasi degradasi performa akibat *Thread Pinning* pada Virtual Thread, mengukurnya dengan JDK Flight Recorder (JFR), lalu memperbaikinya menggunakan `ReentrantLock`.

#### Langkah 1: Tulis Kode Terkontaminasi (`hands-on/m02/PinningVulnerable.java`)
```java
package hands_on.m02;

import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.ReentrantLock;

public class PinningVulnerable {

    private static final Object MONITOR = new Object();
    private static final ReentrantLock MODERN_LOCK = new ReentrantLock();

    public static void executeWithPinning() {
        // Anti-pattern: Operasi I/O / blocking sleep di dalam synchronized block
        synchronized (MONITOR) {
            try {
                Thread.sleep(Duration.ofMillis(100));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    public static void executeWithoutPinning() {
        // Pattern Benar: ReentrantLock mengizinkan unmounting virtual thread
        MODERN_LOCK.lock();
        try {
            Thread.sleep(Duration.ofMillis(100));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            MODERN_LOCK.unlock();
        }
    }

    public static void main(String[] args) throws Exception {
        boolean fixActive = args.length > 0 && args[0].equals("--fixed");
        System.out.println("Memulai stress test, mode fixed: " + fixActive);

        long startTime = System.currentTimeMillis();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 200; i++) {
                executor.submit(() -> {
                    if (fixActive) {
                        executeWithoutPinning();
                    } else {
                        executeWithPinning();
                    }
                });
            }
        }
        long duration = System.currentTimeMillis() - startTime;
        System.out.printf("Total Waktu Eksekusi: %d ms%n", duration);
    }
}
```

#### Langkah 2: Kompilasi dan Jalankan Profiling dengan JFR
1. Kompilasi:
   ```bash
   javac -d . PinningVulnerable.java
   ```
2. Jalankan versi yang rentan (*pinning*) dengan merekam profiling JFR:
   ```bash
   java -XX:StartFlightRecording=filename=pinned.jfr,settings=profile \
        -Djdk.tracePinnedThreads=full \
        hands_on.m02.PinningVulnerable
   ```
   *Amati terminal*: JVM akan mencetak *stack trace pinning event* yang menunjukkan thread tidak dapat di-*unmount*.

3. Jalankan versi yang diperbaiki (*fixed*):
   ```bash
   java -XX:StartFlightRecording=filename=fixed.jfr,settings=profile \
        -Djdk.tracePinnedThreads=full \
        hands_on.m02.PinningVulnerable --fixed
   ```

#### Langkah 3: Verifikasi dengan `jcmd`
Buka metadata JFR menggunakan tools bawaan JDK:
```bash
jfr print --events jdk.VirtualThreadPinned pinned.jfr
```
*Hasil*: Anda akan melihat log komprehensif mengenai *Carrier Thread* yang terblokir pada eksekusi pertama, dan nol event pinning pada eksekusi kedua.

---

### 13. Exercise

#### Level Easy
Tulis sebuah kelas Java `CacheLineValidator` yang mengukur waktu eksekusi penulisan berulang (1.000.000.000 kali) ke dua variabel `long` yang ditempatkan berdampingan dalam satu array (`long[2]`), dibandingkan dengan dua variabel `long` yang dipisahkan oleh padding 7 elemen long kosong di antaranya (`long[16]`).
* *Kriteria Penilaian*: Buktikan bahwa versi berpading memiliki performa eksekusi minimal 2x lebih cepat pada multi-threaded benchmark (2 thread berjalan serentak).

#### Level Medium
Buat implementasi *custom classloader* bernama `HotSwapClassLoader` yang mampu memuat ulang bytecode file `.class` dari direktori runtime tanpa perlu me-restart proses JVM.
* *Kriteria Penilaian*: Validasi bahwa instance baru menggunakan tipe class dari loader yang baru, dan pastikan referensi classloader lama berhasil dibersihkan dari GC roots (uji Metaspace stability).

#### Level Hard
Rancang struktur data **Lock-Free Single-Producer Single-Consumer (SPSC) Queue** murni off-heap menggunakan Project Panama (`java.lang.foreign.*`).
* *Kriteria Penilaian*:
  1. Tidak ada alokasi objek heap sama sekali pada method `enqueue()` dan `dequeue()` (verifikasi alokasi 0 bytes via Async-Profiler).
  2. Implementasikan semantic *Acquire/Release memory order* secara presisi.
  3. Mengimplementasikan antarmuka `AutoCloseable` untuk pembersihan memori deterministik.

---

### 14. Challenge

#### Deskripsi Tantangan: "Ultra-Low Latency Order Matching Gateway Engine"
Anda bertindak sebagai Principal Systems Architect di sebuah bursa perdagangan aset digital. Anda diminta membangun sebuah core gateway ingestion order perdagangan dengan kriteria:

1. **Throughput Target**: Mampu menerima dan memproses 500.000 order per detik secara streaming.
2. **Latensi Maksimal**: Latensi P99.99 tidak boleh melebihi 2 milidetik di bawah beban penuh.
3. **Kendala Heap**: Heap JVM dialokasikan maksimal hanya 512 MB, tetapi sistem harus menampung status sementara dari 5.000.000 transaksi aktif di memori.

#### Batasan Arsitektural
* Dilarang menggunakan library pihak ketiga (hanya JDK 21 murni).
* Dilarang menggunakan `sun.misc.Unsafe` (wajib menggunakan `java.lang.foreign.*` dan `VarHandle`).
* Tidak boleh terjadi *Stop-The-World* GC pause lebih dari 1 ms (pilih dan tune GC secara argumentatif).
* Implementasikan mekanisme backpressure non-blocking ketika buffer transit mendekati kapasitas maksimal.

#### deliverables
1. File implementasi core engine Java.
2. File konfigurasi bash startup script berisi seluruh JVM Tuning Flags (`-XX`, `-Xm`, modul JVM options).
3. Dokumen arsitektur teknis mini (maksimal 500 kata) yang menjelaskan layout memori off-heap dan strategi sinkronisasi antar thread tanpa lock.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi dari *On-Stack Replacement* (OSR) pada C2 Compiler HotSpot?
2. Mengapa instruksi `volatile` pada arsitektur x86_64 membutuhkan memori barrier, padahal arsitektur x86_64 secara hardware sudah berkarakteristik *strongly ordered memory*?
3. Sebutkan perbedaan struktural penyimpanan metadata antara *PermGen* (versi Java lawas) dan *Metaspace* (Java modern)!
4. Kapan HotSpot memutuskan untuk membatalkan kompilasi JIT C2 (*Deoptimization*) dan mengembalikan eksekusi kode ke Interpreter?
5. Mengapa method `Continuation.yield()` menjadi primitif inti dalam implementasi Virtual Thread?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja algoritma *Colored Pointers* dan *Load Barriers* pada ZGC sehingga mampu menjaga pause time di bawah 1 milidetik pada heap berukuran terabyte?
7. Apa dampak dari fenomena *False Sharing* terhadap hardware cache L1/L2, dan bagaimana cara memitigasinya pada Java 21?
8. Bandingkan semantik akses memori `getVolatile()`, `getAcquire()`, dan `getOpaque()` pada class `VarHandle`!
9. Jelaskan skenario di mana penggunaan Virtual Threads justru memperburuk performa aplikasi dibandingkan menggunakan Platform Threads konvensional!
10. Mengapa alokasi objek bertipe *Humongous Object* pada G1 GC dapat memicu penurunan performa sistem secara drastis?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice mengalami lonjakan CPU 100% secara mendadak. Hasil `jcmd Thread.print` menunjukkan banyak thread berada pada state `RUNNABLE` di dalam method kompilasi C2 Compiler, dan sistem merespons lambat. Bagaimana Anda mendiagnosis dan memitigasi anomali ini di runtime tanpa reboot jika memungkinkan?
12. **Skenario 2**: Aplikasi keuangan Anda mencatat log exception `java.lang.OutOfMemoryError: Direct buffer memory`. Analisis heap dump via Eclipse Memory Analyzer (MAT) menunjukkan JVM Heap hanya terpakai 20% dari total `-Xmx`. Di mana letak kebocoran memori ini dan bagaimana cara melacak objek yang menjadi biang keladinya?
13. **Skenario 3**: Anda melakukan migrasi arsitektur dari Java 11 ke Java 21. Setelah mengaktifkan Virtual Threads, metrik P99.9 latensi database call melonjak dari 5ms menjadi 4000ms secara sporadis. Log JVM mengindikasikan ratusan log peringatan *Pinned Thread*. Apa langkah remediasi arsitektur software yang harus segera diambil?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### A. Basic
1. **OSR (On-Stack Replacement)** memungkinkan JVM mengganti implementasi method yang sedang berjalan di stack (misalnya loop panjang yang ditafsirkan oleh interpreter) langsung dengan kode native yang dikompilasi JIT di tengah-tengah eksekusi tanpa menunggu pemanggilan method berikutnya.
2. Meskipun x86_64 tidak mengubah urutan Read-Read, Read-Write, atau Write-Write, ia tetap mengizinkan operasi *Store-Load reordering* (operasi tulis dapat ditunda di *store buffer* sementara operasi baca mendahuluinya). `volatile` mencegah hal ini dengan memaksakan barrier (seperti `lock prefix` atau `mfence`).
3. PermGen berada di dalam contiguous Java Heap dan dibatasi oleh `-XX:MaxPermSize`. Metaspace dialokasikan pada *Native Memory* OS di luar heap, dibatasi oleh memori fisik yang tersedia atau parameter `-XX:MaxMetaspaceSize`.
4. Deoptimasi terjadi ketika asumsi optimasi spekulatif C2 tidak valid lagi. Contoh: JVM melakukan inline sebuah method karena hanya ada satu implementasi kelas (*monomorphic*), tetapi kemudian classloader memuat kelas turunan baru yang meng-override method tersebut (*class hierarchy invalidation*).
5. `Continuation.yield()` bertugas membekukan eksekusi call stack virtual thread saat ini, menyalin stack frame ke heap, dan mengembalikan kontrol eksekusi ke Carrier Thread tanpa memblokir thread OS yang mendasarinya.

#### B. Intermediate
6. ZGC memanfaatkan bit referensi 42-45 pada pointer 64-bit untuk menyimpan state (*Marked0*, *Marked1*, *Remapped*). Jika sebuah objek sedang dipindahkan, *Load Barrier* (sepotong kode mikro yang dieksekusi saat pointer dibaca) mendeteksi warna pointer yang usang, mencari alamat baru via *Forwarding Table*, memperbarui nilai pointer tersebut di tempat (*self-healing*), dan melanjutkan eksekusi secara transparan tanpa menghentikan thread aplikasi.
7. *False Sharing* menyebabkan Cache Invalidation Storm di antara inti CPU yang berbeda melalui protokol MESI. Solusinya: Pisahkan variabel yang saling bersaing dengan memberikan padding memori (minimal 64 byte, ukuran satu cache line) atau menggunakan `@Contended`.
8. * `getVolatile()`: Menjamin urutan eksekusi memori penuh (*Sequential Consistency*).
   * `getAcquire()`: Menjamin instruksi memori setelah pemanggilan ini tidak diurutkan ulang mendahuluinya (*One-way barrier*).
   * `getOpaque()`: Menjamin operasi atomik terhadap nilai data tanpa memberikan aturan urutan memori (*ordering semantics*) terhadap variabel lain di sekitarnya.
9. Virtual Threads memperburuk performa pada beban kerja **CPU-Bound** (komputasi murni tanpa I/O seperti rendering grafis, kalkulasi machine learning, kriptografi) karena overhead penjadwalan dan *swapping* stack virtual thread ke heap justru menambah CPU penalty tanpa ada waktu tunggu I/O yang bisa dimanfaatkan.
10. Objek Humongous (> 50% dari ukuran G1 Region) dialokasikan langsung ke Old Generation secara berurutan (*contiguous regions*). Alokasi ini tidak memanfaatkan Eden/Survivor, memicu fragmentasi region, dan jika G1 kehabisan contiguous free regions, ia akan memaksa dilakukannya *Full GC* yang berjalan secara single-threaded dan memakan waktu sangat lama (STW).

#### C. Skenario Kasus Produksi
11. **Diagnosa & Solusi**: Terjadi *JIT Compilation Storm / Deoptimization Loop*. Identifikasi method penyebab menggunakan `-XX:+PrintCompilation`. Mitigasi runtime: Gunakan `jcmd <PID> Compiler.directives_add` dengan file JSON direktif untuk mengecualikan method tersebut dari kompilasi C2 sementara waktu (`c2: false`), memaksa method tetap diinterpretasikan atau di-compile C1 tanpa membakar CPU 100%.
12. **Diagnosa & Solusi**: Masalah terjadi pada alokasi `ByteBuffer.allocateDirect()` atau *Direct Memory JNI/FFM*. Heap dump standar tidak menyertakan payload native. Solusi: Gunakan Native Memory Tracking (NMT) dengan menambahkan flag `-XX:NativeMemoryTracking=detail`, lalu jalankan `jcmd <PID> VM.native_memory baseline` dan `jcmd <PID> VM.native_memory detail.diff` untuk melacak call-site native allocator.
13. **Diagnosa & Solusi**: Driver database JDBC atau framework connection pooling menggunakan blok `synchronized` di jalur eksekusi I/O query database, yang menyebabkan *Virtual Thread Pinning* dan melumpuhkan seluruh thread pool Carrier. Solusi: Update driver JDBC ke versi modern yang sudah loom-compliant (telah mengganti `synchronized` dengan `ReentrantLock`), atau sementara waktu isolasi pemanggilan database client tersebut ke dalam dedicated bounded Platform Thread Pool (`Executors.newFixedThreadPool()`).

---

### 16. Summary

1. **HotSpot Engine**: HotSpot JVM bukanlah sekadar interpreter melainkan sistem adaptif berkinerja tinggi yang mengombinasikan interpretasi instan dengan kompilasi multitier (C1 & C2) yang mampu melakukan *Escape Analysis*, *Inlining*, dan *Vectorization*.
2. **Java Memory Model**: Pemahaman mendalam mengenai JMM, *Happens-Before*, protokol MESI, dan *Cache Lines* merupakan fondasi mutlak untuk merancang arsitektur konkurensi modern yang aman, bebas lock, dan bebas dari jebakan *False Sharing*.
3. **Garbage Collection Modern**: Pilihan GC menentukan profil latensi sistem. ZGC modern (Generational ZGC) memecahkan kompromi antara latensi dan kapasitas memori dengan menawarkan jeda pause sub-milidetik secara deterministik via *Load Barriers* dan *Colored Pointers*.
4. **Konkurensi Generasi Baru**: Project Loom (Virtual Threads) dan Project Panama (Foreign Function & Memory API) memposisikan Java 21+ sebagai runtime tingkat enterprise yang efisien: menangani jutaan konkurensi I/O sekaligus mengeksekusi komputasi memori native *zero-copy* tanpa terbebani limitasi historis JVM.