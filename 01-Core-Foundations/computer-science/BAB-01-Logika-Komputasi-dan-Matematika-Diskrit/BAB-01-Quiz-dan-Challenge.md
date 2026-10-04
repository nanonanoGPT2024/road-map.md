# BAB 01: Quiz, Challenge, & Knowledge Check
**Bab 01: Fondasi Arsitektur Komputer, Eksekusi Instruksi, dan Abstraksi Memori**

---
## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Von Neumann Bottleneck & L1 Harvard Split**  
   Jelaskan secara mendalam konsep *Von Neumann Bottleneck* pada pemrosesan throughput data modern. Mengapa prosesor performa tinggi modern mengadopsi arsitektur *Modified Harvard* (pemisahan L1 Instruction Cache dan L1 Data Cache) alih-alih mempertahankan unified memory bus secara murni hingga ke register CPU?
2. **IEEE 754 Floating-Point Precision & Subnormal Numbers**  
   Analisis bagaimana representasi floating-point IEEE 754 single-precision (32-bit) menangani limitasi presisi matematis. Apa yang dimaksud dengan *subnormal (denormalized) numbers*, bagaimana *gradual underflow* bekerja, dan mengapa operasi floating-point yang melibatkan angka subnormal dapat memicu penurunan performa CPU hingga puluhan cycle (*performance penalty*)?
3. **Mekanisme Paging & Multi-Level Page Tables**  
   Bagaimana sistem operasi dan hardware MMU (*Memory Management Unit*) mentranslasikan alamat virtual 64-bit menjadi alamat fisik melalui *Multi-Level Page Table* (misal: 4-level paging x86-64)? Jelaskan dampak dari kedalaman level translasi terhadap latensi akses memori dan bagaimana *Translation Lookaside Buffer* (TLB) memitigasi *overhead* tersebut.
4. **Pipeline Hazards & Branch Prediction**  
   Identifikasi tiga kategori utama *pipeline hazards* (*Structural, Data, Control*). Jelaskan bagaimana algoritma *Dynamic Branch Prediction* modern (seperti TAGE branch predictor) memprediksi alur eksekusi, serta apa dampak instruksional dan temporal dari *pipeline flush* akibat kondisi *branch misprediction* pada arsitektur superscalar.
5. **Memory Hierarchy & Locality of Reference**  
   Diferensiasikan *Spatial Locality* dan *Temporal Locality* dalam konteks hardware cache lines (biasanya 64 byte). Bagaimana perbedaan representasi memori *Row-Major* versus *Column-Major* pada array multi-dimensi secara langsung memengaruhi rasio *Cache Miss* (L1/L2) saat dieksekusi oleh loop bertingkat (*nested loop*)?

---
## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **False Sharing & Protokol Cache Coherency (MESI/MOESI)**  
   Dua buah thread yang berjalan secara konkuren pada dua core CPU berbeda memperbarui dua variabel integer independen yang kebetulan berada di dalam baris cache yang sama (*same 64-byte cache line*). Bedah rantai status transisi pada protokol *MESI* yang terjadi, serta jelaskan bagaimana fenomena *False Sharing* ini dapat mendegradasi skalabilitas performa multithreading secara drastis meskipun tidak ada lock yang digunakan.
2. **Data Alignment, Padding, & Unaligned Memory Access Penalty**  
   Mengapa kompilator menyisipkan padding byte ke dalam representasi `struct` bahasa C/Rust? Apa yang terjadi di tingkat mikroarsitektur bus memori ketika CPU mencoba membaca variabel 64-bit yang berada di alamat yang tidak terkelipatan 8 (*unaligned access*) pada arsitektur x86 vs arsitektur RISC (misal: ARM/MIPS)?
3. **Speculative Execution Side-Channel Vulnerability**  
   Jelaskan mekanisme internal eksekusi spekulatif (*Speculative Execution*) dan *Out-of-Order Execution* yang memungkinkan terjadinya serangan *Spectre* (Variant 1: Bounds Check Bypass). Bagaimana CPU membocorkan informasi rahasia melalui status mikroarsitektural cache meskipun instruksi ilegal pada akhirnya di-*rollback* oleh *Reorder Buffer* (ROB)?
4. **Anatomi Biaya Konteks Switching (Context Switch Overhead)**  
   Ketika scheduler sistem operasi melakukan *preempt* terhadap sebuah thread kernel untuk menjalankan thread lain, rincikan seluruh pekerjaan mikroarsitektural yang terjadi. Mengapa latensi dari context switch tidak hanya mencakup *direct cost* (penyimpanan register, switching stack pointer, page table switch via CR3 register), melainkan juga *indirect cost* yang signifikan?
5. **Direct Memory Access (DMA) vs Programmed I/O & Cache Invalidation**  
   Jelaskan siklus hidup transmisi data berkecepatan tinggi menggunakan *Direct Memory Access* (DMA) dari Network Interface Card (NIC) langsung ke RAM. Masalah koherensi apa yang muncul antara memori fisik yang baru saja ditulis DMA dengan cache L2/L3 CPU, dan bagaimana driver kernel serta hardware menyinkronkan konsistensi data tersebut (*cache snooping* vs *explicit cache invalidation*)?

---
## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike p99 pada Core In-Memory Engine akibat TLB Thrashing & Page Faults
Sebuah sistem High-Frequency Trading (HFT) mengeksekusi in-memory matching engine yang dialokasikan sebesar 64 GB heap memory di Linux server. Pada saat volume transaksi pasar melonjak tajam, tercatat lonjakan p99 latency yang ekstrem (dari 4 mikrosekon melesat hingga 85 milisekon). Metrik profiling sistem menggunakan `perf` menunjukkan metrik `dTLB-load-misses` yang luar biasa tinggi dan lonjakan `minor page faults`. Sistem berjalan dengan konfigurasi default page size 4 KB.
* **Pertanyaan Diagnostik:**
  1. Analisis korelasi matematis antara alokasi 64 GB heap dengan konfigurasi standard 4 KB page terhadap kapasitas TLB CPU modern (misal: 1024-entry L2 TLB). Mengapa konfigurasi ini menyebabkan *TLB Thrashing*?
  2. Mengapa *minor page faults* terjadi secara masif saat runtime padahal memori telah dipesan via `malloc()` di awal inisialisasi aplikasi?
  3. Rancang strategi rekayasa arsitektural (di level OS configuration dan level system programming) untuk mengeliminasi bottleneck TLB dan page allocation latency ini secara permanen.

### Skenario B: Silent Data Corruption & Race Condition pada Lock-Free Ring Buffer
Tim platform backend mengimplementasikan lock-free *Single Producer Single Consumer* (SPSC) ring buffer berkecepatan tinggi untuk streaming event transaksi keuangan. Selama uji beban di arsitektur x86-64, pengujian berjalan 100% deterministik dan valid. Namun, saat service yang sama dikompilasi dan di-deploy ke server berbasis ARM64 (Graviton), terjadi fenomena *silent data corruption* di mana data yang dibaca oleh Consumer sesekali berisi data usang (*stale data*) atau pointer yang menunjuk memori sampah.
* **Pertanyaan Diagnostik:**
  1. Dari perspektif *Memory Consistency Model*, jelaskan perbedaan fundamental antara model *Total Store Order* (TSO) pada x86-64 dan model *Weakly Ordered* (Relaxed) pada ARM64.
  2. Identifikasi potensi instruksi reordering yang dilakukan hardware ARM64 antara operasi penulisan payload data dengan operasi pembaruan indeks pointer `head`/`tail`.
  3. Bagaimana koreksi kode level rendah harus diterapkan menggunakan *Memory Barriers* (atau C++11 `std::atomic` memory ordering semantics seperti `acquire-release`) untuk menjamin integritas data di arsitektur ARM64?

### Skenario C: Architectural Trade-off: Memory-Mapped Files (mmap) vs Explicit Direct I/O (O_DIRECT)
Sebuah tim data infrastructure sedang merancang storage engine database NoSQL berbasis disk bertipe NVMe SSD untuk throughput penulisan 100.000 IOPS. Dua arsitek berdebat: Arsitek 1 mengusulkan penggunaan `mmap` untuk mengeksploitasi Linux Page Cache secara otomatis demi kesederhanaan kode. Arsitek 2 menolak dan mendesak penggunaan `O_DIRECT` dengan *custom userspace buffer pool* dan asynchronous I/O (`io_uring`).
* **Pertanyaan Diagnostik:**
  1. Apa trade-off arsitektural terberat dari `mmap` dalam menangani workload write-heavy dengan dataset yang melampaui kapasitas RAM fisik (terkait lock contention pada kernel virtual memory `mmap_lock` dan interupsi I/O)?
  2. Jelaskan kompleksitas teknis yang harus ditanggung oleh aplikasi userspace ketika mengadopsi `O_DIRECT` (termasuk alignment constraints, buffer management, dan pengabaian page cache).
  3. Pada kondisi karakteristik workload seperti apa `mmap` tetap unggul, dan pada ambang batas metrik beban apa migrasi ke `io_uring` + `O_DIRECT` menjadi sebuah keharusan teknis?

---
## 4. Chapter Challenge
**Tantangan Praktis: Implementasi Custom Slab & Arena Allocator dengan Cache-Line Awareness**

### Problem Statement
Penggunaan system default allocator (`malloc`/`free` atau standard runtime allocators) pada eksekusi multithreaded performa tinggi memicu problem *external memory fragmentation*, thread contention pada global heap locks, dan ketidakmampuan menjamin *cache-line boundary alignment*. Tugas Anda adalah merancang dan mengimplementasikan *low-level custom memory allocator* dari nol (*zero external dependencies*) menggunakan C atau Rust.

### Requirements
1. **Dua Komponen Utama:**
   * **Arena (Bump) Allocator:** Digunakan untuk siklus hidup objek berumur pendek (*ephemeral*). Mengalokasikan memori secara linear dengan incrementing pointer dan mendukung *bulk deallocation* (reset) dalam $O(1)$.
   * **Slab Allocator:** Digunakan untuk objek berukuran tetap (*fixed-size*) dengan *caching objects* (misal: slab 32-byte, 64-byte, 128-byte) untuk mencegah fragmentasi eksternal, dengan waktu alokasi dan dealokasi strictly $O(1)$.
2. **Cache-Line Boundary Alignment:** Seluruh blok memori yang dialokasikan wajib ter-*align* pada batas kelipatan 64-byte (*L1 data cache line boundary*) untuk mengeliminasi penyeberangan cache line (*cache line splits*).
3. **Internal Accounting & Zero Overhead:** Header metadata tidak boleh disisipkan secara naif di depan setiap alokasi kecil yang dapat merusak alignment atau menyebabkan bloat memory. Gunakan bitmask atau embedded freelist.

### Constraints
* Dilarang menggunakan library alokasi eksternal (`jemalloc`, `mimalloc`) maupun method pembungkus tingkat tinggi.
* Permintaan blok memori primer dari kernel wajib menggunakan system call langsung (`mmap` pada POSIX atau `VirtualAlloc` pada Windows).
* Implementasi harus thread-safe minimal pada level arena partitioning (misal: Thread-Local Arena instance atau lock-free freelist untuk Slab).

### Expected Output
1. Source code implementasi lengkap dalam satu file atau modul terstruktur yang bersih.
2. Unit test benchmarking mikroarsitektur:
   * Menunjukkan verifikasi alignment: `(uintptr_t)ptr % 64 == 0` untuk setiap pointer hasil alokasi.
   * Benchmark perbandingan throughput alokasi/dealokasi $1.000.000$ objek ukuran 64-byte antara implementasi Custom Allocator Anda vs Standard System `malloc`.
3. Analisis empiris profil fragmentasi dan estimasi konsumsi cycle CPU menggunakan tooling profiler (`perf`, Valgrind/Massif, atau cycle counter hardware `RDTSC`).

---
## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus instruksi CPU (*Fetch, Decode, Execute, Memory Access, Write-Back*) dan bagaimana *Instruction Pipelining* dioptimalkan.
- [ ] Representasi data biner: format *Two's Complement* untuk signed integer dan struktur bit IEEE 754 (Sign, Exponent, Mantissa) untuk floating-point.
- [ ] Konsep Virtual Memory, struktur page tables, MMU, TLB, serta pemisahan ruang User Space dan Kernel Space.
- [ ] Hirarki memori fisik: Register, Cache L1i/L1d, L2, L3, RAM, dan NVMe SSD dari segi latensi akses (*nanoseconds scale*).
- [ ] Mekanisme konsistensi cache (*Cache Coherency*) dan dampak dari *False Sharing* pada pemrosesan konkuren.
- [ ] Model konsistensi memori hardware (*Strong/TSO* vs *Weakly-Ordered Architecture*).
- [ ] Perbedaan interupsi CPU: *Hardware Interrupts*, *Software Traps/Exceptions*, dan mekanisme *System Calls*.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel opcode instruksi arsitektur x86-64 atau ARM64 secara harfiah.
- [ ] Angka eksak kapasitas cache atau latency latency spesifik dari setiap vendor/generasi prosesor (cukup memahami orde magnitudonya).
- [ ] Implementasi manual assembly dari instruksi bootstrap sistem operasi BIOS/UEFI.
- [ ] Konstanta heksadesimal spesifik untuk bitfield control register prosesor (seperti bitmask flag register CR0/CR3/CR4).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan menghitung padding serta memory layout dari struktur data kompleks untuk meminimalkan jejak memori (*data structure packing*).
- [ ] Menggunakan utility profiling performa sistem (seperti `perf`, `valgrind`, atau hardware PMU counters) untuk mengidentifikasi *cache misses*, *branch mispredictions*, dan *page faults*.
- [ ] Menulis kode yang berorientasi *Cache-Friendly (Data-Oriented Design)* dengan memaksimalkan pola akses sequential (*Spatial Locality*).
- [ ] Mengelola memori tingkat rendah secara manual menggunakan panggilan sistem `mmap`/`munmap` dengan proteksi memori yang tepat.
- [ ] Mengidentifikasi dan memecahkan bug *memory corruption* tingkat rendah (seperti *buffer overflow*, *use-after-free*, dan *unaligned access faults*) menggunakan debugger (misal: GDB/LLDB dan AddressSanitizer).