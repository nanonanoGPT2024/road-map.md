# MODUL 01: Arsitektur Eksekusi Java Runtime Environment, JVM Internals, dan Memory Model Dasar

---

### 1. Title / Metadata
- **Track**: Rekayasa Perangkat Lunak Berbasis Java Enterprise
- **Module ID**: `JAVA-CORE-01`
- **Tingkat Kesulitan**: Fundamental to Deep Core Architecture
- **Prasyarat**: Pemahaman dasar pemrograman prosedural (variabel, fungsi, branching)
- **Target Platform**: OpenJDK 21 LTS (Temurin/HotSpot VM)

---

### 2. Learning Objectives
Setelah menyelesaikan modul ini, peserta program diharapkan mampu:
1. **Menganalisis** siklus hidup kode sumber Java dari fase kompilasi (`javac`) hingga eksekusi mesin runtime (`java`).
2. **Mendekomposisi** arsitektur Java Virtual Machine (JVM) mencakup ClassLoader Subsystem, Execution Engine (Interpreter, JIT Compiler, Garbage Collector), dan Runtime Data Areas.
3. **Mengevaluasi** alokasi memori runtime antara Stack Memory (Thread-confined) dan Heap Memory (Shared-resource) melalui dekompilasi bytecode (`javap`).
4. **Mendiagnosis** anomali memori tingkat rendah seperti `StackOverflowError` dan `OutOfMemoryError` secara deterministik menggunakan tool CLI JDK.

---

### 3. Conceptual Foundation
Java dibangun di atas paradigma *Write Once, Run Anywhere* (WORA). Paradigma ini bukan sekadar abstraksi perangkat lunak, melainkan pemisahan tegas antara fase penerjemahan kode sumber ke representasi semantik perantara (*Intermediate Representation*) yang disebut **Bytecode**, dan fase penerjemahan Bytecode ke instruksi spesifik CPU target (*Native Machine Code*).

Mesin virtual Java (HotSpot JVM) bertindak sebagai proses sistem operasi terisolasi yang mengabstraksi arsitektur *Instruction Set Architecture* (ISA) perangkat keras. JVM mengadopsi model *Stack-based Virtual Machine* (berbeda dari arsitektur fisik modern berbasis register seperti x86-64 atau ARM), di mana setiap operasi instruksi memanipulasi operan langsung di atas *Operand Stack*.

---

### 4. Why This Matters
Dalam rekayasa sistem enterprise berskala tinggi, ketidaktahuan tentang eksekusi JVM menyebabkan:
- **Latensi Tinggi**: Kegagalan memahami Tiered Compilation (C1/C2 JIT) menyebabkan fase *cold start* yang merusak Service Level Objective (SLO).
- **Kebocoran Memori (Memory Leaks)**: Alokasi referensi objek yang tidak terpantau pada Heap menyebabkan degradasi Garbage Collection (Stop-The-World pauses).
- **Masalah Konkurensi**: Ketidakpahaman atas batas isolasi Stack (Thread-safe) vs Heap (Shared, Rentan Race Condition) mengakibatkan data corruption pada transaksi multi-threading.

Menguasai arsitektur JVM adalah pembeda mutlak antara seorang pemrogram sintaksis dasar dan seorang arsitek sistem berkinerja tinggi.

---

### 5. What Is It?
Arsitektur runtime Java terdiri dari tiga komponen hierarkis utama:

1. **Java Development Kit (JDK)**: Lingkungan pengembangan lengkap yang berisi compiler (`javac`), archiver (`jar`), dokumentasi (`javadoc`), dan alat diagnostik ekstensif (`jcmd`, `jstack`, `jmap`, `javap`).
2. **Java Runtime Environment (JRE)**: Subset JDK yang menyediakan pustaka standar (*Java Class Library/rt.jar/modules*) serta runtime untuk mengeksekusi aplikasi. (Catatan: Sejak Java 11, JRE tidak lagi didistribusikan sebagai installer terpisah, melainkan di-bundle via modular runtime image `jlink`).
3. **Java Virtual Machine (JVM)**: Spesifikasi abstrak dan implementasi perangkat lunak aktif (misal: Oracle HotSpot, Eclipse OpenJ9) yang memuat, memverifikasi, mengoptimalkan, dan mengeksekusi bytecode.

---

### 6. How Does It Work?
Siklus eksekusi kode Java berlangsung dalam langkah deterministik berikut:

```
[Source Code: .java] 
       │
       ▼ (Fase Kompilasi Statis via javac)
[Bytecode: .class]
       │
       ▼ (Fase Runtime: Host Process)
┌──────────────────────────────────────────────────────────────┐
│ JVM (Java Virtual Machine)                                   │
│  1. ClassLoader (Loading -> Linking -> Initialization)       │
│  2. Memory Layout Allocation (Heap, Stack, Metaspace)        │
│  3. Execution Engine:                                        │
│     - Interpreter (Membaca Bytecode baris demi baris)         │
│     - Tiered JIT Compiler (C1 Client -> C2 Server Profiling) │
│     - Native Code Generator (Instruksi Mesin x86/ARM)         │
└──────────────────────────────────────────────────────────────┘
```

1. **Compilation**: `javac` mentranslasikan file teks `.java` menjadi instruksi biner platform-agnostik (`.class`). Kode tidak dioptimalkan untuk mikroprosesor tertentu pada tahap ini.
2. **Class Loading**: `ClassLoader` memuat file `.class` ke memori runtime melalui delegasi hierarki (*Bootstrap*, *Platform/Extension*, *Application ClassLoader*).
3. **Linking**: 
   - *Verification*: Memastikan file mematuhi format spesifikasi JVM, tidak melanggar batasan tipe data, atau memanipulasi pointer berbahaya.
   - *Preparation*: Mengalokasikan memori untuk variabel statis dan menginisialisasinya dengan nilai default tipe.
   - *Resolution*: Mengubah referensi simbolik di dalam *Constant Pool* menjadi referensi memori langsung.
4. **Initialization**: Mengeksekusi blok kode statis (`static {}`) dan menginisialisasi variabel statis ke nilai sebenarnya.
5. **Execution & JIT Tiering**: Interpreter langsung mengeksekusi bytecode. Metode yang sering dipanggil (*hot spots*) diidentifikasi via *Invocation Counters* dan dikompilasi oleh JIT (Just-In-Time) compiler ke instruksi mesin asli melalui C1 (kompilasi cepat tanpa optimasi mendalam) dan C2 (kompilasi lambat dengan optimasi agresif seperti *inlining* dan *escape analysis*).

---

### 7. Architecture / Flow Diagram

```
+-----------------------------------------------------------------------------------+
|                            HOTSPOT JVM RUNTIME DATA AREAS                         |
+-----------------------------------------------------------------------------------+
|  THREAD-SHARED AREAS                              THREAD-ISOLATED (PER-THREAD)    |
|                                                                                   |
|  +------------------------------------+          +-----------------------------+  |
|  |             HEAP MEMORY            |          |         JVM STACK           |  |
|  |  +---------------+--------------+  |          |  +-----------------------+  |  |
|  |  |  Young Gen    |  Old Gen     |  |          |  | Frame: compute()      |  |  |
|  |  |  (Eden, S0,S1)|  (Tenured)   |  |          |  | - Local Variable Array|  |  |
|  |  +---------------+--------------+  |          |  | - Operand Stack       |  |  |
|  |  Semua Alokasi 'new' (Objects)     |          |  | - Frame Data          |  |  |
|  +------------------------------------+          |  +-----------------------+  |  |
|                                                  |  | Frame: main()         |  |  |
|  +------------------------------------+          |  +-----------------------+  |  |
|  |         METASPACE (Native)         |          +-----------------------------+  |
|  |  - Class Metadata                  |                                           |
|  |  - Method Bytecode                 |          +-----------------------------+  |
|  |  - Constant Pool                   |          |       PC REGISTERS          |  |
|  +------------------------------------+          +-----------------------------+  |
|                                                                                   |
|                                                  +-----------------------------+  |
|                                                  |     NATIVE METHOD STACK     |  |
|                                                  +-----------------------------+  |
+-----------------------------------------------------------------------------------+
|                                 EXECUTION ENGINE                                  |
|  +-------------+  +---------------------------------------+  +-----------------+  |
|  | INTERPRETER |  | JIT COMPILER (C1 Profiling / C2 Opt)  |  | GARBAGE COLL.   |  |
|  +-------------+  +---------------------------------------+  | (G1, ZGC, Shen) |  |
|                            | Native Machine Code             +-----------------+  |
|                            v                                                      |
+-----------------------------------------------------------------------------------+
|                          OPERATING SYSTEM & HARDWARE (CPU/RAM)                    |
+-----------------------------------------------------------------------------------+
```

---

### 8. Minimal Working Example
Program berikut memperlihatkan pemisahan antara referensi stack, alokasi objek heap, dan pemanggilan instruksi level bytecode.

```java
// ExecutionEngineDemo.java
package com.architect.core;

public class ExecutionEngineDemo {
    public static void main(String[] args) {
        int primitiveVar = 42; 
        Transaction localTx = new Transaction(primitiveVar, "TX-INIT-001");
        
        long result = processTransaction(localTx);
        System.out.println("Result: " + result);
    }

    private static long processTransaction(Transaction tx) {
        int multiplier = 2;
        return (long) tx.id() * multiplier;
    }
}

record Transaction(int id, String code) {}
```

---

### 9. Step-by-Step Code Walkthrough
1. **`int primitiveVar = 42;`**:
   - Dialokasikan langsung di dalam *Local Variable Array* (LVA) pada *Stack Frame* milik method `main`.
   - Mengisi slot index ke-1 (slot 0 diisi oleh `args`).
   - Tidak menghasilkan alokasi memori pada Heap.
2. **`new Transaction(primitiveVar, "TX-INIT-001");`**:
   - `new`: Mengalokasikan blok memori mentah pada Heap untuk menampung instans record `Transaction` (termasuk *object header* 12/16-byte).
   - `dup`: Menggandakan referensi di atas Operand Stack untuk konsumsi konstruktor `<init>`.
   - `invokespecial`: Mengeksekusi konstruktor kanonikal record.
   - Variabel referensi `localTx` disimpan pada *Stack Frame* `main`, menunjuk langsung ke alamat fisik objek pada Heap.
3. **`processTransaction(localTx);`**:
   - JVM mendorong *Stack Frame* baru ke dalam JVM Stack thread saat ini.
   - Referensi `localTx` disalin (*passed-by-value*) ke slot lokal milik frame `processTransaction`.
4. **Frame Pop**:
   - Setelah `processTransaction` menyelesaikan kalkulasi via instruksi `lmul` dan `lreturn`, frame miliknya dihancurkan (*popped*).
   - Nilai balik didorong kembali ke *Operand Stack* milik method `main`.

---

### 10. Compilation & Execution Guide
Jalankan perintah ini melalui terminal untuk menginspeksi struktur bytecode dan status JVM:

```bash
# 1. Kompilasi kode sumber
javac -d target/classes src/com/architect/core/ExecutionEngineDemo.java

# 2. Dekompilasi Bytecode ke format human-readable
javap -c -v -p target/classes/com/architect/core/ExecutionEngineDemo.class

# 3. Jalankan aplikasi dengan diagnostic flag JVM
java -cp target/classes \
     -XX:+PrintCompilation \
     -Xlog:gc* \
     com.architect.core.ExecutionEngineDemo
```

**Output Dekompilasi Bytecode (Fragmen Kunci Method `processTransaction`):**
```text
private static long processTransaction(com.architect.core.Transaction);
  descriptor: (Lcom/architect/core/Transaction;)J
  flags: (0x000a) ACC_PRIVATE, ACC_STATIC
  Code:
    stack=4, locals=2, args_size=1
       0: iconst_2              // Dorong integer literal 2 ke Operand Stack
       1: istore_1              // Simpan ke local variable index 1 (multiplier)
       2: aload_0               // Dorong reference Transaction (tx) ke stack
       3: invokevirtual #13     // Method com/architect/core/Transaction.id:()I
       6: i2l                   // Konversi int ke long
       7: iload_1               // Dorong multiplier ke stack
       8: i2l                   // Konversi int ke long
       9: lmul                  // Eksekusi perkalian long primitive
      10: lreturn               // Kembalikan long primitive ke pemanggil
```

---

### 11. Real-World Practical Example
Implementasi penanganan beban transfer data berlatensi rendah yang membedakan memori Heap vs Off-Heap / Stack untuk mencegah overhead Garbage Collector secara agresif.

```java
// BufferMemoryPipeline.java
package com.architect.performance;

import java.nio.ByteBuffer;
import java.util.Objects;

/**
 * Pipeline pemrosesan biner efisien yang mendemonstrasikan 
 * isolasi alokasi heap vs non-heap.
 */
public final class BufferMemoryPipeline {

    private static final int BUFFER_CAPACITY = 1024;

    public static void main(String[] args) {
        // Direct Buffer: Memori dialokasikan langsung pada OS Native Heap (Off-Heap)
        // Menghindari biaya relokasi memori oleh GC.
        ByteBuffer directBuffer = ByteBuffer.allocateDirect(BUFFER_CAPACITY);
        
        try {
            ingestPayload(directBuffer, 0xCAFEBABE);
            long checksum = processDirectMemory(directBuffer);
            System.out.printf("Pipeline executed successfully. Checksum: %X%n", checksum);
        } finally {
            // Buffer native off-heap tidak dikelola otomatis oleh standard generational GC
            directBuffer.clear();
        }
    }

    private static void ingestPayload(ByteBuffer buffer, int magicHeader) {
        Objects.requireNonNull(buffer, "Target buffer must not be null");
        buffer.clear();
        buffer.putInt(magicHeader);
        buffer.putLong(System.currentTimeMillis());
        buffer.flip(); // Mengubah mode penulisan ke mode pembacaan
    }

    private static long processDirectMemory(ByteBuffer buffer) {
        if (buffer.remaining() < 12) {
            throw new IllegalArgumentException("Payload rusak: Ukuran buffer tidak mencukupi");
        }
        
        int header = buffer.getInt();
        long timestamp = buffer.getLong();

        // Validasi identitas paket data
        if (header != 0xCAFEBABE) {
            throw new IllegalStateException("Corrupted Magic Header: Invalid Frame");
        }

        // Operasi kalkulasi lokal pada thread-stack
        return (long) header ^ timestamp;
    }
}
```

---

### 12. Practical Example Walkthrough
1. **`ByteBuffer.allocateDirect(BUFFER_CAPACITY)`**: Menggunakan JNI (*Java Native Interface*) untuk memanggil `malloc()` sistem operasi. Objek penunjuk tipis (*wrapper*) tetap hidup di Java Heap, namun payload byte data hidup di *Unmanaged Native Memory*.
2. **`buffer.flip()`**: Mengubah batas (*limit*) dan posisi (*position*) pointer buffer internal tanpa menduplikasi array byte. Tidak ada objek baru yang diinstansiasi di Heap.
3. **Pemberian Payload & Eliminasi Mutasi**: Nilai diekstraksi secara sekuensial melalui operasi primitif integer/long, sehingga eksekusi tetap berada dalam register CPU dan Frame Stack tanpa overhead dereferensi pointer object.

---

### 13. Edge Cases, Pitfalls & Failure Modes

| Kondisi / Kasus | Penyebab Internal JVM | Dampak Runtime | Solusi Rekayasa |
| :--- | :--- | :--- | :--- |
| **`StackOverflowError`** | Rekursi tanpa batas atau chain method terlalu dalam yang melampaui alokasi `-Xss`. | Thread dihentikan mendadak; stack frame hancur. | Ubah pola rekursi menjadi iterasi berbasis loop; tingkatkan ukuran stack (`-Xss1m`). |
| **`OutOfMemoryError: Java heap space`** | Tingkat pembuatan objek melebihi kapasitas `-Xmx` dan objek tidak dapat di-reclaim oleh GC. | Crash aplikasi atau kegagalan transaksi massal. | Analisis Heap Dump (`.hprof`); terapkan *object pooling* atau perbaiki *memory leak*. |
| **`OutOfMemoryError: Metaspace`** | Pembuatan class metadata dinamis berlebih (sering akibat library runtime byte-code generation: CGLIB, ByteBuddy). | JVM kehabisan native memory host. | Batasi batas native class metadata via `-XX:MaxMetaspaceSize=256m`. |
| **Silent JIT Deoptimization** | Asumsi tipe polimorfik pecah (misal: antarmuka awalnya hanya memiliki 1 implementasi, lalu memuat implementasi ke-2 di runtime). | C2 melepaskan kode mesin yang dioptimalkan, mundur ke interpreter; latensi naik tajam. | Terapkan *monomorphic call-sites* pada jalur komputasi kritis (*hot paths*). |

---

### 14. Trade-Off Analysis

```
Pendekatan Eksekusi:
[Standard JIT (HotSpot)]  vs  [AOT Native Image (GraalVM)]  vs  [Pure Interpretation]
```

| Matriks Komparasi | Standard JIT (HotSpot JVM) | GraalVM AOT Native Image | Pure Interpretation (`-Xint`) |
| :--- | :--- | :--- | :--- |
| **Peak Throughput** | **Tertinggi** (Optimasi runtime berbasis data profil aktual/PGO). | Tinggi hingga Menengah (Sulit memprediksi profile cabang runtime dinamis). | Sangat Rendah (Tidak ada translasi instruksi mesin). |
| **Startup Latency** | Lambat (Perlu proses *warm-up* kompilasi bertingkat). | **Instan** (Hitungan milidetik; instruksi mesin langsung dimuat). | Instan (Tidak ada overhead kompilasi). |
| **Memory Footprint** | Besar (Memerlukan JVM runtime, Metaspace, JIT compiler cache). | **Minimal** (Hanya binary native dan SubstrateVM minimalis). | Menengah. |
| **Dynamic Capabilities**| Penuh (Mendukung Dynamic Class Loading, Reflection runtime fleksibel). | Terbatas (Semua metadata reflektif harus didaftarkan saat build time). | Penuh. |

---

### 15. Performance & Resource Considerations
- **Kompleksitas Alokasi Memori**: Alokasi memori pada JVM Stack beroperasi pada kompleksitas waktu $\mathcal{O}(1)$ melalui pergeseran pointer *top-of-stack*. Alokasi memori pada Heap membutuhkan algoritma alokasi thread-local yang kompleks (*Thread Local Allocation Buffers* / TLAB) dengan kompleksitas amortisasi $\mathcal{O}(1)$, namun pembersihannya via GC berpotensi $\mathcal{O}(N)$ terhadap total objek aktif.
- **Escape Analysis**: Kompiler JIT C2 secara otomatis menganalisis apakah siklus hidup sebuah objek melampaui scope pemanggilannya. Jika tidak (*does not escape*), JVM melakukan optimasi **Scalar Replacement**, memecah field objek menjadi variabel lokal dan menempatkannya langsung di *Stack Registers*, mengeliminasi tekanan pada Garbage Collector secara total.

---

### 16. Production Readiness & Best Practices
1. **Explicit Memory Sizing**: Jangan biarkan JVM menentukan heap secara implisit di lingkungan container Docker/Kubernetes. Gunakan opsi rasio container:
   ```bash
   -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:InitialRAMPercentage=50.0
   ```
2. **Diagnostic Pre-configurations**: Selalu aktifkan otomatisasi pembuatan dump memori saat crash:
   ```bash
   -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/jvm/crash-dump.hprof
   ```
3. **Avoid Premature Boxing**: Hindari penggunaan wrapper types (`java.lang.Integer`, `java.lang.Long`) pada pemrosesan throughput tinggi; gunakan primitif untuk mempertahankan kontinuitas cache L1/L2 CPU dan mengurangi jejak memori akibat *Object Headers*.

---

### 17. Troubleshooting & Debugging Guide

Jika aplikasi mengalami degradasi latensi tinggi secara anomali di server produksi, ikuti alur diagnosis ini:

```
[Degradasi Sistem Terdeteksi]
              │
              ▼
   Ambil PID Proses Java  ──>  $ jps -lv
              │
              ▼
    Cek Pemanfaatan Thread CPU  ──>  $ top -H -p <PID>
              │
              ▼
   Konversi TID Thread ke Hexadecimal  ──>  $ printf "%x\n" <TID>
              │
              ▼
   Cari Thread di Stack Trace  ──>  $ jstack <PID> | grep -A 30 0x<HEX_TID>
              │
              ├──> [Status: BLOCKED] ──> Masalah Kontensi Lock
              └──> [Status: RUNNABLE di GC] ──> Cek Heap: $ jcmd <PID> GC.heap_info
```

**Perintah Diagnostik Penting:**
- `jcmd <PID> VM.native_memory baseline` & `jcmd <PID> VM.native_memory detail.diff`: Mendeteksi Native Memory Leak (Metaspace, JIT Cache, C-Heap).
- `jstat -gcutil <PID> 1000`: Memonitor utilisasi persentase ruang Eden, Old, dan waktu jeda GC secara real-time per detik.

---

### 18. Enterprise Scenario / Case Study
**Konteks**: Sebuah microservice sistem *Core Banking Settlement* mengalami insiden Out of Memory (OOM) setiap penutupan buku harian (EOD), menyebabkan thread worker berhenti memproses antrean transaksi.

**Investigasi**:
1. Analisis Heap Dump `.hprof` menggunakan CLI `jhat` dan Eclipse Memory Analyzer Tool (MAT).
2. Ditemukan bahwa 85% ruang Tenured Heap didominasi oleh objek `java.util.HashMap$Node` yang dipertahankan oleh sebuah *In-Memory Audit Cache*.
3. Kelas cache tersebut mengimplementasikan map statis (`private static final Map<String, TransactionAudit>`) tanpa kebijakan penggusuran (*eviction policy*) berbasis batas kapasitas atau TTL (*Time-To-Live*).

**Resolusi Arsitektur**:
- Menghapus referensi statis global tak berbatas.
- Mengganti struktur in-memory dengan cache berbasis LRU (*Least Recently Used*) yang dibatasi kapasitasnya melalui Guava/Caffeine Cache dengan konfigurasi referensi lunak (*Soft References*):
  ```java
  Caffeine.newBuilder()
      .maximumSize(50_000)
      .expireAfterWrite(Duration.ofMinutes(30))
      .recordStats()
      .build();
  ```
- Hasil: Penggunaan Heap stabil di bawah 45% kapasitas maksimum saat beban puncak EOD tanpa ada *Stop-the-World GC pause* melebihi 100ms.

---

### 19. Hands-On Exercises & Mini-Projects

#### Level 1: Analisis Stack & Heap (Dasar)
- **Instruksi**: Tulis program Java yang secara sengaja memicu:
  1. `java.lang.StackOverflowError` menggunakan pemanggilan rekursif tanpa kondisi terminasi.
  2. `java.lang.OutOfMemoryError: Java heap space` menggunakan loop tak terbatas yang mengalokasikan array `byte[]` ke dalam `List`.
- **Ekspektasi**: Catat perbedaan perilakunya di console, dan identifikasi jenis resource memori yang kehabisan ruang melalui stack trace yang dihasilkan.

#### Level 2: Eksplorasi Instruksi Bytecode (Menengah)
- **Instruksi**:
  1. Buat program sederhana yang memiliki dua implementasi penggabungan string: satu menggunakan operator konkatenasi `+` di dalam loop, dan satu lagi menggunakan `StringBuilder`.
  2. Kompilasi kedua kelas tersebut dan gunakan alat `javap -c` untuk mendekompilasi bytecode.
- **Ekspektasi**: Buat laporan tertulis singkat yang menunjukkan mengapa loop dengan konkatenasi `+` pada versi Java lama mengalokasikan banyak objek per iterasi, dan bagaimana compiler Java 21 mengoptimalkannya menggunakan metode `invokedynamic` (`StringConcatFactory`).

#### Level 3: Off-Heap Cache Minimalis (Lanjutan)
- **Instruksi**: Bangun engine *Off-Heap Key-Value Store* sederhana dengan spesifikasi berikut:
  1. Menerima data payload biner (maksimum 4KB per record).
  2. Simpan payload di luar Java Heap menggunakan `java.nio.ByteBuffer.allocateDirect`.
  3. Kelola tabel indeks penunjuk lokasi memori (offset dan panjang data) di dalam Java Heap.
  4. Implementasikan metode pembacaan `get(key)` dan penulisan `put(key, data)` yang *thread-safe*.
- **Ekspektasi**: Aplikasi dapat memproses alokasi dan pembacaan 1.000.000 entitas tanpa memicu fase Garbage Collection pada Heap di ruang Old Generation (`jstat -gcutil` menunjukkan 0% pertambahan Old Gen).

---

### 20. Summary & Next Steps
- **Rangkuman Kunci**:
  1. Eksekusi Java bergantung pada pemisahan antara translasi bytecode `.class` (statis via `javac`) dan interpretasi/kompilasi adaptif native (dinamis via HotSpot JVM).
  2. **Stack Memory** terisolasi per thread dan memiliki siklus hidup deterministik yang terikat pada eksekusi frame method.
  3. **Heap Memory** adalah area penyimpanan global bersama untuk semua instansiasi objek, yang dikelola secara otomatis oleh siklus GC bertingkat.
  4. Kompiler JIT HotSpot mentransformasikan bytecode yang sering dieksekusi menjadi instruksi mesin asli melalui analisis profil bertingkat (Tiered Compilation C1/C2).

- **Langkah Berikutnya (Modul 02)**:
  Kita akan melangkah lebih dalam ke struktur sistem tipe Java: **"Type System Internals: Primitives, Reference Types, Memory Layout (Object Headers, Compressed OOPs), and Value-Based Semantics"**. Siapkan pemahaman instruksi level-rendah ini untuk membedah bagaimana objek dikemas secara presisi di level byte CPU.