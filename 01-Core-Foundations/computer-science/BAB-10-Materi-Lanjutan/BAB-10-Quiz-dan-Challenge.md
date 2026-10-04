# BAB 10: Quiz, Challenge, & Knowledge Check
**Bab 10: Sistem Memori Virtual, Paging, dan Alokasi Tingkat Rendah (Virtual Memory & Memory Management)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Translasi Alamat Multi-Level Page Table**
   Jelaskan secara deterministik bagaimana CPU mentranslasikan sebuah *virtual address* 48-bit (arsitektur x86-64) menjadi *physical address* menggunakan 4-Level Paging (PML4, PDPT, PD, PT). Apa fungsi matematis dari pembagian bit *offset* (12 bit) dan *index* (9 bit per level), serta mengapa arsitektur modern memilih multi-level paging dibanding *flat/single-level page table*?

2. **Siklus Hidup dan Anatomi Page Fault**
   Diferensiasikan secara komprehensif antara **Minor (Soft) Page Fault**, **Major (Hard) Page Fault**, dan **Invalid Page Fault (Segmentation Fault)**. Uraikan langkah-langkah yang dieksekusi oleh CPU, Memory Management Unit (MMU), dan Kernel Page Fault Handler sejak instruksi memory-access dijalankan hingga eksekusi instruksi tersebut diulang kembali (*re-executed*).

3. **Peran Translation Lookaside Buffer (TLB) dan TLB Shootdown**
   Apa peran TLB sebagai hardware cache untuk Page Table Entry (PTE)? Jelaskan fenomena **TLB Shootdown** yang terjadi pada sistem Multi-Core (SMP) ketika kernel memodifikasi PTE (misalnya saat operasi `unmap` atau `page migration`), serta dampak latensinya terhadap throughput sistem akibat *Inter-Processor Interrupts* (IPI).

4. **Hierarki Cache, Cache Lines, dan Prinsip Locality**
   Jelaskan interaksi antara *Temporal Locality* dan *Spatial Locality* dengan *L1/L2/L3 CPU Cache Hierarchy*. Mengapa traversi array 2D secara *row-major* menghasilkan performa yang jauh melampaui *column-major* pada bahasa berbasis baris seperti C/Go, dan bagaimana konsep *Cache Line* (umumnya 64 bytes) serta *prefetcher* memengaruhi fenomena ini?

5. **Anatomi Virtual Address Space Proses & Batas Alokasi**
   Gambarkan dan urutkan segmentasi memori standar dalam *User-Space Virtual Memory Layout* (Text/Code, Initialized Data, BSS, Heap, Memory Mapping Segment, Stack). Jelaskan perbedaan mendasar mekanisme alokasi memori dinamis antara *system call* `brk`/`sbrk` (mengubah batas *program break*) dengan `mmap` (*anonymous memory mapping*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Copy-on-Write (CoW) pada `fork()`**
   Ketika proses melakukan `fork()`, kernel tidak langsung menyalin seluruh physical frame milik *parent process*. Uraikan secara teknis bagaimana flags/permissions pada Page Table Entry (PTE) dimanipulasi (pengubahan bit Read/Write menjadi Read-Only) untuk memfasilitasi CoW. Apa yang terjadi pada level hardware trap saat *child* atau *parent* mencoba menulis ke salah satu page tersebut?

2. **Analisis Thrashing dan Working Set Model**
   Jelaskan parameter yang menyebabkan sebuah sistem masuk ke dalam status **Memory Thrashing**. Mengapa ketika jumlah total *Working Set Size* (WSS) dari seluruh proses aktif melampaui ketersediaan *Physical RAM*, throughput I/O penyimpanan meningkat drastis sementara utilitas CPU anjlok mendekati nol? Bagaimana algoritma *page replacement* (misalnya LRU vs Clock/Second-Chance) merespons kondisi ini?

3. **Internal vs External Fragmentation & Arsitektur Allocator**
   Bandingkan permasalahan *Internal Fragmentation* dan *External Fragmentation*. Bagaimana kernel dan custom memory allocator modern (seperti Linux Buddy System untuk alokasi frame fisik dan Slab/SLUB/SLOB untuk alokasi objek kecil di kernel) memitigasi kedua bentuk fragmentasi tersebut secara efisien?

4. **False Sharing dan Cache Coherency (Protokol MESI)**
   Dua thread yang berjalan di dua CPU core berbeda mengeksekusi penulisan intensif pada dua variabel independen yang secara kebetulan berada di dalam satu *Cache Line* (64-byte) yang sama. Uraikan degradasi performa yang ditimbulkan akibat siklus invalidasi status protokol MESI (Modified, Exclusive, Shared, Invalid) dan bagaimana teknik *padding* diterapkan untuk mengatasinya.

5. **Transparent Huge Pages (THP) vs 4KB Pages: Latency Trade-Off**
   Penggunaan *Huge Pages* (2MB atau 1GB) mereduksi *TLB miss rate* secara signifikan untuk beban kerja dengan jejak memori masif. Namun, mengapa fitur *Transparent Huge Pages* (THP) sering kali diwajibkan untuk dimatikan (*disabled*) pada *database engine* latensi-rendah (seperti Redis, ScyllaDB, atau MongoDB)? Fokuskan jawaban Anda pada proses *memory compaction* dan alokasi sinkron di level kernel.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes dan Swap Thrashing pada Distributed Database
Sebuah node database NoSQL terdistribusi (in-memory caching engine) dengan kapasitas RAM 128 GB mengalami *p99 latency spike* yang melonjak dari 1.2 milidetik menjadi lebih dari 8.500 milidetik secara periodik setiap 15 menit. Metrik CPU menunjukkan *%iowait* naik hingga 85%, sementara beban query eksternal tergolong stabil pada 40.000 QPS.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menggunakan utilitas Linux (seperti `vmstat`, `sar -B`, `perf`, `/proc/vmstat`, dan `/proc/[pid]/smaps`) untuk membuktikan bahwa lonjakan latensi disebabkan oleh swapping/major page faults dan memory compaction oleh kernel thread `kswapd` atau `khugepaged`?
  2. Parameter kernel `vm.swappiness`, `vm.dirty_background_ratio`, dan `vm.zone_reclaim_mode` apa saja yang wajib ditinjau dan dikonfigurasi ulang untuk menstabilkan latensi I/O?

### Skenario B: Race Condition dan Silent Memory Corruption pada High-Frequency Trading (HFT) Pool
Sebuah aplikasi order-matching multi-threaded yang ditulis dalam C++20 mengimplementasikan *lock-free ring buffer* dan *custom memory pool*. Di bawah beban uji stres 100.000 order/detik, sesekali data order ID terkorupsi dengan nilai dari objek transaksi lain, tanpa memicu *Segmentation Fault*. Analisis memory dump menunjukkan terjadinya reuse memori sebelum siklus pembacaan tuntas.
* **Pertanyaan Diagnostik:**
  1. Identifikasi bagaimana fenomena *ABA Problem* atau *Use-After-Free* (UAF) akibat re-allocation siklik dalam custom pool dapat menyebabkan silent corruption tanpa perlindungan *memory safety*.
  2. Bagaimana instruksi sinkronisasi atomik, *memory barriers/fences* (khususnya *acquire-release semantics* vs *sequential consistency*), dan teknik *Hazard Pointers* atau *Epoch-Based Reclamation* (EBR) diterapkan untuk memvalidasi keamanan *reclamation* memori?

### Skenario C: Misteri OOM-Killer pada Microservices di Lingkungan Kubernetes
Sebuah service berbasis JVM dideploy di Kubernetes pod dengan batas resource: `requests: {memory: "4Gi"}`, `limits: {memory: "4Gi"}`. Nilai heap JVM diatur dengan `-Xms2g -Xmx2g`. Setelah berjalan normal selama 6 jam di bawah beban produksi sedang, pod secara mendadak mati dengan exit code `137` (OOMKilled), padahal metrik monitoring JVM Application Performance Monitoring (APM) menunjukkan *Heap Usage* tidak pernah melampaui 1.8 GB dan *Garbage Collection* berjalan sehat.
* **Pertanyaan Diagnostik:**
  1. Uraikan komponen-komponen *off-heap memory* dari JVM (Metaspace, Thread Stacks, Direct Byte Buffers, Native Memory allocations, JIT CodeCache, dynamic C-libraries) yang dapat menyebabkan penggunaan *Resident Set Size* (RSS) proses melampaui limit 4 GiB yang dipaksakan oleh *cgroups* (Control Groups v1/v2).
  2. Langkah diagnostik apa yang harus dijalankan pada level container dan JVM runtime (misalnya *Native Memory Tracking* / NMT, *core dump analysis*, tracing jemalloc/glibc allocator) untuk menemukan akar alokasi memori yang bocor (*leaking memory*)?

---

## 4. Chapter Challenge

**Tantangan Praktis: Implementasi Thread-Safe Slab/Buddy Memory Allocator di User-Space**

### Deskripsi Masalah
Fungsi alokasi standar seperti `malloc()` dan `free()` dari *general-purpose allocator* (glibc `ptmalloc`) memiliki overhead metadata dan potensi contention pada aplikasi dengan frekuensi alokasi/dealokasi sangat tinggi untuk objek berukuran seragam. Anda diminta untuk merancang dan mengimplementasikan *custom, thread-safe memory allocator* di user-space.

### Requirements & Spesifikasi Teknis
1. **Backing Storage:** Ambil blok memori mentah berukuran besar (misalnya 64 MB) langsung dari kernel menggunakan system call `mmap` (`MAP_ANONYMOUS | MAP_PRIVATE`, flag `PROT_READ | PROT_WRITE`). Jangan gunakan `malloc` bawaan runtime.
2. **Dual-Strategy Engine:**
   - **Slab Allocator:** Untuk alokasi objek kecil berukuran tetap (fixed-size classes: 32B, 64B, 128B, 256B, 512B, 1024B). Objek harus dipaketkan ke dalam page-aligned chunks (4096 bytes) menggunakan *freelist* berbasis pointer intrusif.
   - **Buddy Allocator:** Untuk alokasi blok memori dinamis berukuran $2^k$ (antara 2 KB hingga 64 KB) guna melayani permintaan di atas ukuran Slab atau kebutuhan alokasi chunk baru bagi Slab Allocator. Wajib mendukung mekanisme *splitting* dan *coalescing* (penggabungan blok buddy yang bebas kembali menjadi blok induk).
3. **Alignment & Metadata:**
   - Seluruh pointer yang dikembalikan ke pemanggil harus ter-align pada batas 8-byte atau 16-byte (`alignof(max_align_t)`).
   - Metadata alokasi (misalnya chunk size atau pointer ke freelist) tidak boleh merusak payload data dan harus efisien (overhead header $\le 16$ bytes).
4. **Thread-Safety & Scalability:**
   - Terapkan skema *Thread-Local Cache* (arena per thread atau partisi lock) untuk meminimalkan lock contention global antar-core ketika banyak thread mengalokasikan memori secara konkuren.
5. **API Contract:**
   - `void* my_alloc(size_t size)`
   - `void my_free(void* ptr)`
   - `void my_allocator_stats()` (Menampilkan metrik: Total Allocated, Internal Fragmentation, Active Slabs, Free Memory).

### Constraints
- Bahasa implementasi: C99, C++17, atau Rust (menggunakan blok `unsafe` secara eksplisit).
- Dilarang memanggil `stdlib.h` (`malloc`, `calloc`, `realloc`, `free`).
- Harus bebas dari memory leaks pada internal metadata.

### Expected Output
- Kode sumber modular yang dapat dikompilasi dengan `-Wall -Wextra -Werror -pedantic`.
- Test harness yang memverifikasi:
  1. *Correctness test:* Memastikan data yang ditulis ke pointer alokasi tidak corrupt dan aman dari tumpang tindih.
  2. *Fragmentation stress test:* Alokasi dan dealokasi 1.000.000 objek acak dalam urutan pseudorandom; buktikan fitur *coalescing* berhasil mengembalikan blok besar.
  3. *Concurrency benchmark:* Bukti throughput multithreaded (minimal 4 thread) menunjukkan performa stabil tanpa race condition (diverifikasi dengan Valgrind/Memcheck atau AddressSanitizer/LeakSanitizer: `fsanitize=address,undefined`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Struktur translasi alamat berbasis paging multi-level (PML4 $\to$ PDPT $\to$ PD $\to$ PT $\to$ Physical Offset) dan peran register kontrol `CR3`.
- [ ] Perbedaan deterministik antara Virtual Address, Physical Address, dan Bus Address.
- [ ] Alur kerja kernel page fault handler dalam menangani alokasi on-demand, CoW, dan swapping.
- [ ] Peran dan cara kerja TLB, proses flushing saat context switch, serta mitigasi via ASID/PCID (Process-Context Identifiers).
- [ ] Prinsip kerja algoritma penggantian halaman (*Page Replacement Algorithms*): FIFO, Optimal, LRU, Second-Chance/Clock, dan Working Set Algorithm.
- [ ] Fenomena CPU cache line bouncing, false sharing, dan protokol cache coherency hardware (MESI/MOESI).
- [ ] Konsep manajemen fragmentasi: Mekanisme Buddy Allocator (splitting & coalescing) dan Slab/SLUB allocation.
- [ ] Batasan resource memory pada level kernel: Anonymous memory vs File-backed memory, page cache, serta logika pemicu OOM-Killer (*Out-of-Memory Killer* via `oom_score`).

### Saya tidak perlu menghafal:
- [ ] Posisi bit individual eksak dari register arsitektur CPU spesifik yang jarang diakses (misalnya bit reserved non-standar pada MSR platform lama).
- [ ] Implementasi baris-per-baris dari kode sumber kernel Linux `mm/memory.c` atau fungsi `alloc_pages()` internal.
- [ ] Nilai numerik konstan dari syscall numbers untuk `mmap`, `brk`, atau `mprotect` di setiap varian arsitektur OS.

### Saya harus bisa melakukan:
- [ ] Menganalisis jejak virtual dan fisik memori dari proses produksi yang berjalan melalui `/proc/[pid]/maps`, `/proc/[pid]/smaps`, dan `/proc/[pid]/status`.
- [ ] Mendeteksi memory leaks, use-after-free, dan out-of-bounds access menggunakan tooling profiling tingkat industri (`Valgrind Memcheck`, `AddressSanitizer (ASan)`, `Heaptrack`).
- [ ] Mendiagnosis dan mengeliminasi masalah *False Sharing* pada aplikasi multi-threaded menggunakan hardware performance counters (`perf c2c` atau `perf stat -e cache-misses`).
- [ ] Mengonfigurasi parameter memory-tuning pada Linux kernel (`sysctl`: `swappiness`, `overcommit_memory`, `dirty_ratio`, hugepages) sesuai karakteristik beban kerja sistem.
- [ ] Mengalokasikan, melindungi, dan membebaskan anonymous memory regions langsung menggunakan POSIX system calls (`mmap`, `mprotect`, `munmap`, `madvise`).