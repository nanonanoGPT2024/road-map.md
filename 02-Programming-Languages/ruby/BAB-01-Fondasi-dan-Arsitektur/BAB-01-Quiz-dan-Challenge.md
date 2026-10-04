# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Runtime & Arsitektur Ruby Core (MRI/YARV)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Eksekusi YARV vs. AST-Walking Interpreter**  
   Jelaskan transformasi arsitektur runtime Ruby dari MRI 1.8 (*AST-walking interpreter*) ke YARV pada Ruby 1.9+ (*stack-based virtual machine*). Mengapa representasi *bytecode* berbasis instruksi *virtual stack* secara signifikan memangkas *overhead dispatch loop* CPU dan konsumsi memori dibandingkan evaluasi *node* pohon AST secara langsung?

2. **Pointer Tagging dan Representasi `VALUE` pada CRuby**  
   Pada arsitektur 64-bit CRuby, sebuah objek direpresentasikan dengan tipe data C `VALUE`. Jelaskan mekanisme *pointer tagging* (`FIXNUM_FLAG`, `FLONUM_MASK`, `SYMBOL_FLAG`, dll.) yang memungkinkan penyimpanan *immediate values* (seperti `Integer`, `Float`, `Symbol`, `true`, `false`, `nil`) langsung di dalam *register* CPU tanpa mengalokasikan struktur `RVALUE` di heap Ruby. Apa implikasi dari bit alignment 64-bit yang memungkinkan teknik ini bekerja?

3. **Global VM Lock (GVL) dan Thread Execution Model**  
   Meskipun Ruby MRI menggunakan native OS threads (`pthreads`), eksekusi kode Ruby paralel dibatasi oleh Global VM Lock (GVL). Jelaskan pada titik mana GVL dilepaskan (*released*) dan diambil kembali (*acquired*) selama eksekusi program. Mengapa operasi I/O-bound mendapatkan keuntungan konkurensi dari *threading* di MRI, sementara CPU-bound task mengalami perlambatan (*thrashing*)?

4. **Generational Garbage Collection (RGenGC) & The Write Barrier**  
   Ruby 2.1 memperkenalkan *Restricted Generational Garbage Collection* (RGenGC) untuk mempertahankan kompatibilitas ke belakang dengan C-extensions lama. Jelaskan konsep *old object* vs *young object*, peran *write barrier* (`RB_OBJ_WRITE`), dan bagaimana *unprotected objects* (objek dari C-extension tanpa *write barrier*) ditangani oleh *remembered set* (*shady/gray list*) tanpa memicu *full heap scan* secara konstan.

5. **Heap Layout: Pages, Slots, dan Compacting GC**  
   Jelaskan struktur internal memori Ruby heap yang terdiri dari `heap_page`, `page_header`, dan array `RVALUE` *slots*. Apa penyebab utama fragmentasi memori pada Ruby sebelum versi 2.7, dan bagaimana algoritma *Two-Finger / Pinning Compactor* pada `GC.compact` memindahkan objek di memori tanpa merusak referensi pointer mentah pada C-extensions?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Dekompilasi Bytecode & Specialized Instructions**  
   Diberikan potongan kode berikut:
   ```ruby
   def calculate(a, b)
     a + b
   end
   ```
   Ketika didekompilasi menggunakan `RubyVM::InstructionSequence.disasm(method(:calculate))`, instruksi yang dihasilkan memuat `opt_plus`. Jelaskan mekanisme *inline caching* dan *instruction specialization* pada YARV tersebut. Apa kondisi runtime yang memaksa YARV melakukan *fallback* dari instruksi cepat `opt_plus` ke pemanggilan metode dinamis penuh (`send` / `vm_call_method`)?

2. **Mekanisme C-Extension: Melepaskan GVL secara Aman**  
   Seorang insinyur menulis C-extension untuk pemrosesan citra komputasi berat. Jika mereka menggunakan API:
   ```c
   rb_thread_call_without_gvl(heavy_computation_func, data, ubf_func, NULL);
   ```
   Jelaskan bahaya teknis apa yang terjadi jika fungsi `heavy_computation_func` secara tidak sengaja memanggil API Ruby internal seperti `rb_str_new` atau `rb_hash_aset` saat GVL dilepaskan. Apa peran dari fungsi UBF (*Unblocking Function*) ketika thread tersebut menerima sinyal OS atau interupsi *Ruby thread kill*?

3. **Fiber Scheduler dan Non-blocking IO Event Loop (Ruby 3.0+)**  
   Bagaimana implementasi `Fiber::SchedulerInterface` di Ruby 3+ mampu mengubah pemanggilan I/O sinkronus standar (misalnya `TCPSocket#read`) menjadi operasi non-blocking asinkronus tanpa memodifikasi pustaka standar Ruby? Jelaskan interaksi antara *syscall hook* di level runtime YARV dengan *event-loop loop multiplexer* (seperti `epoll` atau `kqueue`).

4. **Diagnostik Memory Bloat: Allocator Fragmentation vs Object Leak**  
   Sebuah worker Ruby menunjukkan penggunaan memori *Resident Set Size* (RSS) sebesar 2 GB pada sistem operasi Linux, namun metrik `GC.stat[:heap_live_slots]` menunjukkan jumlah objek hidup bernilai stabil setara ~300 MB. Jelaskan bagaimana alokator memori `glibc malloc` (terkait *memory arenas* dan batas `M_MMAP_THRESHOLD`) berinteraksi dengan alokasi heap Ruby sehingga menyebabkan *perceived memory bloat*, dan bagaimana teknik mitigasi menggunakan alokator alternatif (jemalloc) bekerja pada level halaman memori OS.

5. **Object Shapes (Shape Trees) pada Ruby 3.2+**  
   Ruby 3.2 memperkenalkan *Object Shapes* untuk menggantikan variasi *inline cache* instance variable berbasis ID counter. Jelaskan bagaimana transisi *shape tree* terjadi saat instance variable diinisialisasi dalam urutan yang berbeda pada dua *instance* dari kelas yang sama:
   ```ruby
   # Objek 1:
   a = Point.new; a.x = 1; a.y = 2
   # Objek 2:
   b = Point.new; b.y = 2; b.x = 1
   ```
   Bagaimana perbedaan urutan tersebut memengaruhi *shape transition*, ukuran memori *shape tree*, dan performa *monomorphic inline cache* pada akses berikutnya?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Investigasi Latency Spike Akibat GC Pause pada High-Throughput API
* **Konteks:** Sebuah microservice Ruby on Rails berbasis Puma melayani 12.000 request per detik untuk platform lelang finansial. Tim SRE mendeteksi lonjakan latensi p99 secara periodik hingga 450 ms setiap 90 detik, sementara p50 tetap di angka 8 ms. Analisis awal menunjukkan CPU usage melonjak 100% pada satu core saat lonjakan latensi terjadi.
* **Gejala:** Metrik New Relic / Datadog menunjukkan lonjakan korelasi langsung antara p99 dan fase *Major Mark-and-Sweep* pada Ruby GC. Nilai `GC.stat[:major_gc_count]` meningkat tepat di saat anomali terjadi.
* **Pertanyaan Diagnostik:**
  1. Parameter lingkungan (*GC environmental variables*) apa yang harus Anda audit pertama kali (`RUBY_GC_HEAP_GROWTH_FACTOR`, `RUBY_GC_MALLOC_LIMIT`, dll.) untuk membatasi frekuensi Major GC tanpa mengorbankan kapasitas memori?
  2. Bagaimana Anda menggunakan `GC::Profiler` dan tracepoint heap allocation untuk mendeteksi alokasi objek transient berukuran besar (*short-lived large strings/arrays*) yang secara prematur memicu *malloc limit threshold*?
  3. Berikan arsitektur solusi mitigasi: apakah teknik *out-of-band garbage collection*, tuning allocator, atau refactoring pipeline streaming objek yang paling tepat diterapkan di sini? Sertakan justifikasi teknisnya.

---

### Skenario B: Race Condition dan Memory Corruption pada Caching Layer Multi-Threaded
* **Konteks:** Sebuah aplikasi multi-threaded Puma (16 threads per process) mengimplementasikan in-memory thread-safe cache sederhana menggunakan Ruby `Hash` dasar:
  ```ruby
  class AppCache
    def initialize
      @storage = {}
    end

    def fetch(key)
      @storage[key] ||= yield
    end
  end
  ```
* **Gejala:** Developer berasumsi bahwa karena GVL aktif, operasi mutasi hash primitif di Ruby bersifat *thread-safe*. Namun, di bawah beban tinggi (500 konkurensi), aplikasi terkadang melemparkan exception anomali `IndexError`, referensi nilai `nil` tak terduga, atau dalam kasus ekstrem, proses *crash* dengan sinyal `SIGSEGV` (Segmentation Fault) pada level runtime `hash.c`.
* **Pertanyaan Diagnostik:**
  1. Mengapa GVL **tidak menjamin** atomisitas kode Ruby tingkat tinggi seperti memoization (`@storage[key] ||= yield`), dan bagaimana *thread switching* (100 Hz / time-slice 10 ms YARV) dapat mengeksekusi *interleaved instructions* di tengah-tengah operasi tersebut?
  2. Pada kondisi internal C-struct apa mutasi konkuren terhadap `st_table` (struktur C pendukung `Hash` di CRuby) memicu akses pointer liar (*dangling pointer*) yang berujung pada `SIGSEGV` ketika tabel melakukan *rehashing*?
  3. Rancang perbaikan implementasi kelas `AppCache` di atas menggunakan primitif konkurensi Ruby yang benar (*Mutex*, *Concurrent::Map*, atau *Read-Write Lock*) dan buktikan secara teoritis mengapa solusi Anda menghilangkan race condition pada tingkat Ruby VM dan struktur memori C.

---

### Skenario C: Dilema Arsitektur High-Concurrency Workload: Forking vs Fiber Reactor vs Threading
* **Konteks:** Perusahaan Anda sedang merancang ulang fondasi gateway API yang menerima data telemetri IoT (HTTP POST payload 2 KB per koneksi, rata-rata 30.000 persistent HTTP connections yang mengirimkan data tiap 5 detik). Beban kerja adalah: 90% non-blocking socket waiting, 10% validasi skema JSON & dekompresi data.
* **Pilihan Arsitektur:**
  1. *Architecture 1:* Puma Clustered (Forking model + 16 threads per worker process).
  2. *Architecture 2:* Falcon / Async Ruby (Single-process per core berbasis Fiber Scheduler + IO Reactor).
  3. *Architecture 3:* Migrasi ke runtime alternatif (TruffleRuby atau JRuby) untuk menghilangkan GVL sepenuhnya menggunakan *parallel OS threads*.
* **Pertanyaan Diagnostik:**
  1. Evaluasi konsumsi memori (Memory Footprint) dari ketiga arsitektur tersebut untuk menangani 30.000 koneksi persisten. Jelaskan keterbatasan model Puma Clustered terkait konsumsi file descriptor dan *stack memory per thread*.
  2. Bagaimana GVL membatasi performa Arsitektur 1 dan 2 ketika menangani 10% beban CPU-bound (JSON parsing)? Mengapa JRuby/TruffleRuby memiliki keunggulan kompetitif di sini, namun memiliki trade-off pada *startup time* dan *warm-up latency*?
  3. Sebagai Principal Architect, tentukan keputusan arsitektur mana yang paling optimal untuk spesifikasi sistem di atas. Sertakan analisis *operational cost*, *complexity*, dan *failure modes*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Custom Heap & Bytecode Memory Profiler Berbasis Internal API

#### Problem Statement
Tim teknik Anda dilarang menggunakan monitoring agent pihak ketiga yang bersifat closed-source (seperti New Relic / Datadog APM native gem) di lingkungan produksi berkeamanan tinggi (air-gapped banking network). Anda ditugaskan membangun library diagnostik internal berukuran ringkas bernama `CoreProfiler` yang dapat di-inject ke dalam runtime Ruby produksi untuk menganalisis fragmentasi heap, mendeteksi kebocoran slot objek, dan memeriksa efisiensi instruksi YARV.

#### Requirements
1. **Bytecode Inspector (`CoreProfiler::Bytecode`):**
   * Mengambil referensi sebuah kelas dan method, kemudian mengekstrak seluruh deret instruksi YARV ke dalam format structured hash.
   * Mendeteksi keberadaan instruksi yang tidak efisien atau *de-optimized instruction path* (misal: keberadaan instruksi `opt_send_without_block` berulang yang seharusnya dapat dioptimasi, atau dynamic method invocation).
2. **Heap Page Analyzer (`CoreProfiler::Heap`):**
   * Membaca langsung status internal alokasi Ruby VM menggunakan `GC.stat` dan `ObjectSpace.dump_all` (atau `ObjectSpace.count_objects`).
   * Menghitung rasio fragmentasi: menghitung rasio antara *live slots* vs *free slots* per heap page.
   * Menghasilkan metrik detail mengenai jumlah objek yang *pinned* (`GC.stat[:pinned_objects]` jika tersedia, atau identifikasi objek yang ditandai tidak dapat dipindahkan oleh Compactor).
3. **Execution Profiler (`CoreProfiler.profile_block`):**
   * Menerima sebuah block kode, mengeksekusinya, dan mengeluarkan metrik delta alokasi memory:
     * Alokasi slot muda (*young objects allocated*).
     * Promosi slot ke generasi tua (*promoted objects*).
     * Total malloc memory delta yang dialokasikan di luar Ruby heap (`malloc_increase_bytes`).
4. **Zero External Dependency:**
   * Wajib hanya menggunakan standard library Ruby dan Core API (`ObjectSpace`, `GC`, `RubyVM::InstructionSequence`).

#### Constraints
* **Memory Overhead:** Profiler itu sendiri tidak boleh mengalokasikan objek baru secara liar saat sedang mengukur; instansiasi objek diagnostik harus diminimalisasi (*zero-allocation profiling path* sebisa mungkin).
* **Production Safety:** Profiler tidak boleh menjalankan *full stop-the-world GC* secara paksa (`GC.start` dilarang dipanggil di dalam tracer execution).

#### Expected Output
Sebuah script Ruby mandiri (`core_profiler.rb`) yang ketika dieksekusi menghasilkan output diagnostik terstruktur ke STDOUT:

```text
================================================================================
COREPROFILER RUNTIME DIAGNOSTIC REPORT
================================================================================
[1] BYTECODE AUDIT: OrderService#process_payment
    Instruction Count : 42
    Optimized Ops     : opt_plus, opt_aref, opt_eq (12)
    Dynamic Dispatches: send, opt_send_without_block (4) [WARNING: Potential polymorphic IC deopt]

[2] HEAP FRAGMENTATION METRICS
    Total Heap Pages  : 48
    Live Slots        : 18,240
    Free Slots        : 1,320
    Slot Density      : 93.25% (Healthy)
    Pinned Objects    : 412 (Cannot be compacted)

[3] BLOCK ALLOCATION DELTA
    Duration          : 0.0042s
    Young Allocated   : 1,250 slots
    Old Promoted      : 45 slots
    Malloc Delta      : +14.2 KB
================================================================================
```

---

## 5. Knowledge Check & Checklist

Beri tanda centang pada item yang telah Anda kuasai secara mendalam sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Representasi biner dan bitmasking tipe `VALUE` pada CRuby (Pointer Tagging untuk `Fixnum`, `Flonum`, `TrueClass`, `FalseClass`, `NilClass`, dan `Symbol`).
- [ ] Siklus hidup kompilasi kode Ruby: Source Code $\to$ Tokenization (Ripper) $\to$ Abstract Syntax Tree (AST) $\to$ Bytecode Generation (`RubyVM::InstructionSequence`).
- [ ] Mekanisme eksekusi mesin virtual YARV berbasis stack (manipulasi stack pointer, frame pointers, dan instruction table dispatch).
- [ ] Algoritma Garbage Collector Ruby: RGenGC (Generational GC), Three-Color Marking, Write Barriers, dan Compaction.
- [ ] Arsitektur thread MRI: Hubungan native pthread, VM-level lock (GVL), perlakuan terhadap I/O blocking syscall, dan unblocking functions (UBF).
- [ ] Konsep *Object Shapes* pada Ruby 3.2+ dan perbedaannya dengan inline caching konvensional.

### Saya tidak perlu menghafal:
- [ ] Seluruh opcode instruksi YARV (misal: opcode ID numerik dari `opt_lt`, `putspecialobject`, dll.).
- [ ] Implementasi baris-per-baris C macro alokasi memori internal (`ALLOC`, `REALLOC_N`, `ZALLOC`).
- [ ] Spesifikasi formal parser grammar Bison Yacc pada `parse.y`.

### Saya harus bisa melakukan:
- [ ] Mendekompilasi method Ruby menggunakan `RubyVM::InstructionSequence.disasm` dan menganalisis aliran stack evaluation-nya.
- [ ] Mengidentifikasi masalah memory leak nyata versus memori terfragmentasi (memory bloat) menggunakan metrik `GC.stat` dan dump heap `ObjectSpace`.
- [ ] Melakukan tuning konfigurasi Ruby VM menggunakan environment variables (`RUBY_GC_*`, `RUBY_PAGE_SIZE`, `MALLOC_ARENA_MAX`) untuk beban kerja spesifik.
- [ ] Menganalisis *thread safety* pada kode Ruby dan menentukan dengan presisi kapan GVL melindungi state dan kapan race condition dapat terjadi.
- [ ] Menggunakan dan mengonfigurasi `GC.compact` secara aman di aplikasi produksi tanpa merusak native C-extension.