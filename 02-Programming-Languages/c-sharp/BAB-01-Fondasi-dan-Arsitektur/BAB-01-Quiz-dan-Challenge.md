# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Arsitektur .NET & CLR Internals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Eksekusi Kode: Dari Roslyn hingga Dynamic PGO**  
   Jelaskan siklus hidup instruksi C# dari saat dikompilasi oleh Roslyn menjadi Intermediate Language (IL), hingga dieksekusi sebagai instruksi mesin native oleh RyuJIT. Fokuskan penjelasan Anda pada mekanisme **Tiered Compilation** (Tier 0, Tier 1, dan OSR - *On-Stack Replacement*) serta bagaimana **Dynamic PGO** (*Profile-Guided Optimization*) memanfaatkan data telemetri runtime untuk membalikkan (*devirtualize*) virtual call dan mengoptimalkan register allocation.

2. **Anatomi Objek di Managed Heap (x64)**  
   Bedah struktur fisik sebuah instance reference type di managed heap pada arsitektur 64-bit. Jelaskan peran, ukuran, dan offset dari **Object Header (SyncBlockIndex)**, **MethodTable Pointer (Type Handle)**, serta bagaimana CLR mengatur urutan field (*field layout packing/padding*) untuk memenuhi aturan *memory alignment* 8-byte.

3. **Mekanisme Generational Garbage Collection & Card Table**  
   Mengapa managed heap dibagi menjadi Generasi (0, 1, 2, LOH, dan POH)? Jelaskan konsep *Weak Generational Hypothesis*. Secara teknis internal, bagaimana GC melakukan scanning objek Gen 0 yang masih hidup tanpa harus memindai seluruh objek di Gen 2, dan apa fungsi dari struktur data **Card Table / Card Bundles** serta *write barrier* dalam proses tersebut?

4. **Batas Eksekusi Managed vs Unmanaged (P/Invoke & Marshalling)**  
   Ketika kode managed memanggil fungsi native via C# P/Invoke, apa yang sebenarnya terjadi di balik layar? Jelaskan transisi eksekusi thread managed ke unmanaged, tugas dari **IL Stub**, overhead transisi konteks CPU/GC mode (Cooperative vs Preemptive), serta perbedaan penanganan antara tipe data **blittable** dan **non-blittable**.

5. **Isolasi Runtime: AssemblyLoadContext (ALC)**  
   Bagaimana CLR mengelola resolusi dependensi dan isolasi tipe data menggunakan `AssemblyLoadContext`? Jelaskan mengapa dua assembly yang identik secara biner dapat menghasilkan runtime type yang dianggap berbeda (*TypeIdentity mismatch*) jika dimuat di ALC yang terpisah, dan apa syarat mutlak agar sebuah `Collectible AssemblyLoadContext` dapat di-*unload* sepenuhnya dari memori tanpa mengalami memory leak?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Multi-Fungsi SyncBlock: Sinkronisasi, HashCode, dan COM Interop**  
   Bitwise layout dari `SyncBlockIndex` (4 byte sebelum MethodTable pada x64) bersifat polymorphic. Jelaskan bagaimana bit-bit dalam header ini bertransisi ketika suatu objek mengalami:
   * Pemanggilan `lock(obj)` tanpa kontensi (thin lock/spinlock semantics).
   * Terjadinya kontensi berat yang memaksa alokasi full `SyncBlock` dari SyncBlock Table.
   * Pemanggilan default `GetHashCode()` (apakah hash disimpan di header atau di SyncBlock?).
   * Apa yang terjadi jika objek dikunci sekaligus dihitung hash-nya?

2. **Dinamika Boxing, Unboxing, dan `ref struct` Restrictions**  
   Secara instruksi IL (`box` vs `unbox` vs `unbox.any`), apa perbedaan mendasar antara mem-box sebuah struct dengan mengekstrak nilainya kembali? Bedah bagaimana runtime mengalokasikan memori untuk box value type di heap. Selanjutnya, jelaskan batasan arsitektural mengapa runtime melarang `ref struct` (seperti `Span<T>`) untuk di-box, disimpan di heap, atau dijadikan generic type argument standard!

3. **Stop-The-World (STW), GC Safepoints, dan Engine Hijacking**  
   Untuk memulai GC fase marking, runtime harus membawa seluruh managed thread ke status *Safepoint*. Jelaskan bagaimana RyuJIT menanamkan instruksi safepoint poll (teknik polling page trap) dalam loop dan epilog method. Apa yang dimaksud dengan **Thread Hijacking** (modifikasi return address pada stack thread oleh GC), dan kondisi apa yang menyebabkan thread masuk ke status *unhijackable* sehingga menyebabkan *GC starvation*?

4. **Fragmentasi Large Object Heap (LOH) vs Non-Compacting Pinned Object Heap (POH)**  
   Berdasarkan CLR internals, objek berukuran $\ge 85.000$ byte dialokasikan di LOH yang secara historis menggunakan algoritma *free-list* tanpa defragmentasi rutin. Mengapa defragmentasi LOH (sweep & compact) sangat mahal dari perspektif CPU cache dan memory copy? Bagaimana alokasi buffer I/O pada **POH (Pinned Object Heap)** menyelesaikan masalah *GC heap fragmentation* yang diakibatkan oleh pinning pointer (`fixed` keyword)?

5. **ReadyToRun (R2R) vs Native AOT: Perbandingan Arsitektur dan Kompromi Runtime**  
   Bandingkan binary format dan lifecycle eksekusi antara kompilasi ReadyToRun (R2R) dan Native AOT (Ahead-of-Time). Analisis trade-off keduanya dalam aspek:
   * Ketersediaan JIT compiler di target mesin.
   * Dukungan terhadap `Reflection.Emit` dan runtime generic instantiation.
   * Ukuran file biner final dan waktu start-up (*cold start*).
   * Kemampuan sistem melakukan *Maximum Peak Throughput Optimization* via PGO.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes (p99.99) Akibat GC Pause dan Finalization Queue Starvation
* **Konteks:** Sebuah microservice pemrosesan transaksi keuangan berbasis .NET 8 menangani throughput 30.000 RPS. Monitoring APM menunjukkan bahwa rata-rata latensi transaksi adalah 4ms, tetapi metrik p99.99 melonjak hingga 1.800ms secara acak setiap 10-15 menit. Analisis metrik runtime menunjukkan bahwa Server GC STW (*Stop-the-World*) pause time melonjak drastis pada Gen 2 collection.
* **Gejala Teknis:** Dump memori menunjukkan puluhan juta instance class wrapper native connection `SecureChannelSession` berada di *Finalization Queue* dan *F-Reachable Queue*. Gen 2 heap terus bertambah besar sebelum akhirnya GC berjalan sangat lambat.
* **Pertanyaan Diagnostik:**
  1. Bagaimana siklus hidup objek yang memiliki finalizer (`~MyClass()`) menyebabkan objek tersebut secara paksa dipromosikan (*promoted*) minimal satu generasi lebih tinggi (dari Gen 0 ke Gen 1, atau Gen 1 ke Gen 2), meskipun objek tersebut sudah tidak lagi direferensikan oleh root aktif?
  2. Bagaimana arsitektur *single-threaded* dari Finalizer Thread di CLR dapat menjadi bottleneck sistem, dan bagaimana mekanisme ini memicu kaskade retensi memori di Gen 2?
  3. Desain pattern apa yang harus diimplementasikan pada class tersebut untuk memotong siklus finalisasi secara deterministik, dan bagaimana cara memvalidasi perbaikannya via dotnet-dump / PerfView?

### Skenario B: Broken Concurrency di Arsitektur ARM64 Akibat Memory Model & Instruction Reordering
* **Konteks:** Sistem in-memory caching kustom dengan performa ultra-tinggi berjalan sempurna tanpa error selama 3 tahun di cluster server Linux berbasis prosesor x86-64 (Intel Xeon). Namun, ketika cluster dimigrasikan ke server berbasis ARM64 (AWS Graviton3) untuk efisiensi biaya, sistem mulai mengalami error intermiten: thread pembaca mendapati properti objek bernilai *null* atau *partially initialized data*, yang menyebabkan crash berantai `NullReferenceException`.
* **Kode Sumber Terduga:**
  ```csharp
  public class CacheManager
  {
      private static CacheManager _instance;
      private Dictionary<string, byte[]> _storage;

      private CacheManager()
      {
          _storage = new Dictionary<string, byte[]>();
          _storage.Add("INIT", new byte[] { 1 });
      }

      public static CacheManager GetInstance()
      {
          if (_instance == null) // Read 1
          {
              _instance = new CacheManager(); // Write & Init
          }
          return _instance;
      }

      public byte[] GetData(string key) => _storage[key];
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Mengapa kode di atas (yang jelas memiliki race condition) hampir tidak pernah crash di arsitektur x86-64 (Strong Memory Model: TSO - *Total Store Order*), namun secara konsisten gagal di ARM64 (Weak Memory Model)?
  2. Jelaskan bagaimana RyuJIT dan CPU ARM64 dapat melakukan *out-of-order execution* (reordering instruksi alokasi memori heap, inisialisasi field `_storage`, dan assignment referensi pointer ke `_instance`) sehingga thread lain dapat membaca pointer `_instance` yang tidak null, namun field `_storage` di dalamnya masih bernilai null!
  3. Berikan solusi refactoring kode tersebut tanpa menggunakan global lock berat (`Monitor`), manfaatkan primitif konkurensi CLR (`Volatile`, `Interlocked`, atau `Lazy<T>`), dan jelaskan efek instruksi memory barrier/fence hardware yang di-generate pada arsitektur ARM64!

### Skenario C: Krisis Cold-Start pada Kubernetes: Trade-Off Migrasi ke Native AOT
* **Konteks:** Tim arsitektur memutuskan untuk memigrasikan API Gateway internal dari ASP.NET Core standar (JIT) ke **Native AOT** guna mengejar target cold-start di bawah 50ms pada cluster Kubernetes dengan auto-scaling ekstrem (KEDA). Setelah biner berhasil di-build dan di-deploy, aplikasi mengalami serangkaian crash saat runtime (`TypeLoadException`, `MissingMetadataException`, dan silent failure pada deserialisasi JSON).
* **Temuan Investigasi:**
  * Komponen logging internal menggunakan library lama yang melakukan runtime reflection: `assembly.GetTypes()` dan memanggil method melalui `MethodInfo.Invoke`.
  * Serialisasi HTTP payload menggunakan `Newtonsoft.Json` (Json.NET).
  * Dependency Injection (DI) framework mendaftarkan service menggunakan *open generic types* berbasis runtime discovery: `services.AddTransient(typeof(IRepository<>), ...)`
* **Pertanyaan Diagnostik:**
  1. Mengapa compiler Native AOT (ILC - *IL Compiler*) melakukan stripping (*tree shaking*) terhadap metadata dan kode yang dipanggil via reflection, dan mengapa dynamic generic instantiation (`MakeGenericType`) tidak dapat dieksekusi pada runtime Native AOT tanpa deklarasi awal?
  2. Analisis kompromi teknis: Jika gateway tersebut membutuhkan throughput puncak yang sangat tinggi (p99 latency stabil di beban tinggi), apakah Native AOT pasti lebih unggul daripada RyuJIT dengan Dynamic PGO? Jelaskan alasannya dari perspektif optimasi runtime adaptif!
  3. Rancang rencana remediasi arsitektur: Komponen mana yang harus diganti (misal: Source Generators), atribut apa yang harus disematkan (`[DynamicallyAccessedMembers]`), dan bagaimana fallback strategy jika library pihak ketiga mutlak tidak mendukung trim-safety?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Allocation Type & Memory Layout Inspector

#### Problem Statement
Dalam rekayasa software performa tinggi (HFT, game engine, database internals), memahami alignment memori dan menghindari alokasi GC sekunder akibat boxing/type-inspection adalah kebutuhan mutlak. Anda diminta membangun sebuah engine diagnostics mandiri bernama **`ClrMemoryProfiler`**. Library/alat ini harus mampu menginspeksi struktur in-memory dari instance managed class dan struct secara raw (langsung dari pointer memori) tanpa menggunakan library eksternal (seperti ClrMD) dan **tanpa memicu alokasi heap baru (Zero GC Allocation)** pada jalur inspeksi.

#### Requirements
1. **Raw Metadata Extractor via Unsafe Pointer:**
   * Buat method generic `void InspectLayout<T>(T target)` di mana `T` bisa berupa class (`reference type`) maupun struct (`value type`).
   * Menggunakan pointer manipulation (`Unsafe`, `MemoryMarshal`), ekstrak dan cetak:
     * Alamat memori aktual dari objek/value.
     * Nilai **SyncBlockIndex** (hanya jika target adalah reference type).
     * Nilai **MethodTable Pointer** (TypeHandle).
     * Ukuran total instance di memori (Base Instance Size untuk class, `Unsafe.SizeOf<T>()` untuk struct).
     * Offset relatif dari setiap field primitif di dalam objek terhadap titik awal payload data.
2. **Generational Detection:**
   * Tentukan di Generasi GC mana objek class target berada saat ini (Gen 0, Gen 1, Gen 2, LOH, atau POH) dengan membaca metadata runtime internal atau boundary heap, tanpa memanggil `GC.GetGeneration(object)` standar (karena pemanggilan ini menyebabkan overhead konversi parameter dan batas safepoint).
3. **Bit-Level SyncBlock Mutator & Lock Detector:**
   * Implementasikan detector status thread lock: Baca langsung 4-byte `SyncBlockIndex` dari memory address `(address - 4)` pada instance class.
   * Cetak apakah objek tersebut sedang di-*lock* (Thin Lock vs Fat Lock) dan apakah default `GetHashCode()` telah dieksekusi pada objek tersebut, murni dengan membaca bit-flags di SyncBlockIndex.

#### Constraints
* Dilarang menggunakan alokasi heap di dalam method inspeksi: dilarang melakukan string concatenation (gunakan `Span<char>`, `ValueStringBuilder`, atau unmanaged console writer), dilarang melakukan boxing (`object obj = target` dilarang keras).
* Program harus dikompilasi dengan konfigurasi `AllowUnsafeBlocks = true` pada .NET 8 / .NET 9.
* Kode harus tahan uji (*crash-safe*) terhadap thread-pinning: pastikan objek yang diinspeksi dipin (`GCHandle` atau keyword `fixed`) selama inspeksi pointer berlangsung agar pointer tidak bergeser akibat GC Compaction.

#### Expected Output
Aplikasi konsol menampilkan output diagnostik tabular:
```text
========================================================================
CLR TYPE & MEMORY LAYOUT INSPECTOR (Architecture: x64)
========================================================================
Target Type            : MyNamespace.OrderTransaction (Class / Reference Type)
Object Memory Address  : 0x000001FA8042B318
SyncBlock Address      : 0x000001FA8042B314 [Value: 0x20000001]
 -> Lock Status        : Thin-Lock Active (Thread ID: 14)
 -> HashCode Generated : False
MethodTable (TypeDesc) : 0x00007FFB349210B0
GC Heap Location       : Generation 0 (Ephemeral Segment)
Total Allocated Size   : 40 bytes (Payload: 24 bytes, Overhead: 16 bytes)
------------------------------------------------------------------------
FIELD OFFSET TABLE:
------------------------------------------------------------------------
Offset | Field Name       | Type    | Size    | Value (Hex/Raw)
+0000  | _transactionId   | Int64   | 8 bytes | 0x000000000001E3FA
+0008  | _amount          | Double  | 8 bytes | 408F400000000000 (1000.0)
+0016  | _flags           | Byte    | 1 byte  | 0x01
+0017  | [PADDING]        | N/A     | 7 bytes | ALIGNMENT FILL
========================================================================
Allocated Memory during Inspection: 0 bytes.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup biner: C# source code $\rightarrow$ Roslyn $\rightarrow$ IL $\rightarrow$ Tier 0 JIT $\rightarrow$ Dynamic PGO Profiling $\rightarrow$ Tier 1 JIT / OSR Native Machine Code.
- [ ] Layout memori objek reference type di x64: Object Header (4 byte padding/SyncBlockIndex) + MethodTable Pointer (8 byte) + Instance Fields + Alignment Padding.
- [ ] Perbedaan representasi memori antara Value Type (unboxed di stack/embedded di heap) dan Reference Type (heap pointer indirection).
- [ ] Cara kerja Generational Garbage Collector: Mark, Sweep, Compact, Card Table, dan Write Barrier.
- [ ] Mekanisme pemisahan heap: Ephemeral (Gen 0 & 1), Gen 2, Large Object Heap (LOH), dan Pinned Object Heap (POH).
- [ ] Aturan sinkronisasi thread CLR: Thin Lock, Fat Lock, Wait-Sleep-Join state, dan alokasi `SyncBlock`.
- [ ] Dampak perbedaan arsitektur CPU: x86/x64 Strong Memory Model vs ARM64 Weak Memory Model terhadap eksekusi konkurensi di .NET.
- [ ] Perbedaan fundamental antara kompilasi JIT, ReadyToRun (R2R), dan Native AOT (Ahead-of-Time).

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap kode opcode IL byte (misal: `0xFE 0x01` untuk `ceq`). Tool seperti `ildasm` atau decompilers (ILSpy/dnSpy) selalu tersedia untuk membacanya.
- [ ] Lokasi offset heksadesimal spesifik dari bit-flag internal runtime CLR yang tidak didokumentasikan resmi dan dapat berubah di setiap versi minor .NET.
- [ ] Angka pasti ambang batas kuantitatif pemanggilan method untuk promosi Tiered JIT (misal: tepat 30 kali invoke untuk Tier 0 ke Tier 1); konfigurasi ini dikontrol dinamis oleh runtime engine.

### Saya harus bisa melakukan:
- [ ] Menangkap dan menganalisis dump memori managed process menggunakan CLI diagnostic tools (`dotnet-dump`, `dotnet-gcdump`, `dotnet-trace`).
- [ ] Memeriksa TypeHandle, MethodTable, dan dump object menggunakan debugger LLDB/WinDbg dengan ekstensi SOS (`sos.dll`).
- [ ] Menggunakan namespace `System.Runtime.CompilerServices.Unsafe` dan `System.Runtime.InteropServices.MemoryMarshal` untuk manipulasi memori performa tinggi tanpa alokasi.
- [ ] Mendiagnosis dan mengeliminasi kasus memory leak akibat retensi GC root tak disengaja (*event subscription leaks*, *static reference accumulation*, dan *ALC uncollectibility*).
- [ ] Mengonfigurasi dan mengoptimalkan runtime .NET melalui environment variable (misal: `DOTNET_TieredPGO`, `DOTNET_gcServer`, `DOTNET_GCHeapCount`).