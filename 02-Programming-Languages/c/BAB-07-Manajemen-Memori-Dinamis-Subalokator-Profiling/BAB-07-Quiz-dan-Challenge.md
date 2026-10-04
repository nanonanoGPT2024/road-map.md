# BAB 07: Quiz, Challenge, & Knowledge Check
**Manajemen Memori Dinamis: Subalokator & Profiling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Fragmentasi Internal vs. Eksternal pada Custom Allocator**  
   Jelaskan perbedaan mendasar antara fragmentasi internal dan fragmentasi eksternal dalam konteks manajemen memori dinamis. Pada desain *Fixed-Size Block Pool Allocator* dan *Buddy Allocator*, jenis fragmentasi mana yang menjadi trade-off dominan pada masing-masing allocator tersebut? Sertakan analisis matematis sederhana terkait pemborosan memori (memory overhead) untuk mengilustrasikan jawaban Anda.

2. **Mekanisme Alignment Memori dan Cache-Line Awareness**  
   Mengapa alignment memori (misalnya *power-of-two alignment* seperti 8, 16, atau 64 byte) sangat penting saat mengimplementasikan *Arena (Linear) Allocator* pada arsitektur modern (x86_64 / AArch64)? Apa konsekuensi performa pada level CPU cycle dan bus transaksi memori jika pointer yang dihasilkan oleh subalokator mengalami *unaligned access* atau melintasi batas *cache line*?

3. **Trade-off Arena Allocator vs. General-Purpose `malloc`/`free`**  
   *Arena Allocator* (atau *Bump/Linear Allocator*) meniadakan overhead pemanggilan individual `free()` dengan menerapkan strategi reset memori secara menyeluruh (*bulk deallocation*). Kapan pola alokasi ini optimal digunakan, dan apa bahaya struktural terbesar (spesifik terhadap *object lifetime* dan destruksi resource non-memori seperti file descriptor) jika arsitektur sistem dipaksa mengadopsi pola ini secara naif?

4. **Deteksi Sanitizer: AddressSanitizer (ASan) vs. Valgrind Memcheck**  
   Jelaskan perbedaan mendasar antara mekanisme instrumentasi waktu-kompilasi (*compiler-based instrumentation*) milik AddressSanitizer (khususnya konsep *Shadow Memory* dan *Redzones*) dengan emulasi biner *just-in-time* (JIT) milik Valgrind Memcheck. Mengapa ASan mampu mendeteksi *stack-buffer-overflow* dan memiliki runtime overhead yang jauh lebih rendah (~2x) dibandingkan Valgrind (~20x-50x), namun Valgrind tetap relevan untuk skenario tertentu?

5. **Anatomi dan Overhead Metadata Alokator Standar**  
   Saat program memanggil `malloc(24)` pada implementasi alokator standar (seperti `ptmalloc` milik glibc), alokasi aktual pada heap kernel hampir selalu lebih besar dari 24 byte. Komponen metadata apa saja yang disisipkan oleh alokator di sekitar atau sebelum chunk memori yang dikembalikan ke user, dan bagaimana metadata ini rentan terhadap eksploitasi *heap corruption* (seperti *heap-overflow* yang menimpa chunk header)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Intrusive Free-List Integrity & Pointer Tagging**  
   Dalam implementasi *Slab/Pool Allocator*, teknik *Intrusive Singly Linked List* sering digunakan di mana payload blok yang belum dialokasikan dipinjam untuk menyimpan pointer `next`. Apa yang terjadi jika terjadi *double-free* atau *use-after-free* pada blok tersebut? Bagaimana teknik defensif seperti *pointer poisoning* (misalnya menimpa payload dengan `0xDEADBEEF`) atau *safe-linking/pointer XORing* (seperti yang digunakan glibc modern) memitigasi eksploitasi perusakan freelist ini?

2. **Coalescing Strategy pada Buddy Allocator**  
   Pada *Buddy Allocator*, jelaskan algoritma pencarian indeks *buddy* dari suatu blok memori berukuran $2^k$ pada offset $P$ menggunakan operasi bitwise. Masalah apa yang muncul jika proses *coalescing* (penggabungan blok bebas) dilakukan secara eager/agresif versus deferred/lazy pada beban kerja alokasi-dealokasi berfrekuensi tinggi di sekitar ambang batas ukuran partisi?

3. **Diagnostik Memory Leak Non-Trivial: False Negatives pada Profiling**  
   Sebuah daemon backend berkinerja tinggi berjalan selama 3 minggu dan mengalami kenaikan Resident Set Size (RSS) secara monoton hingga memicu Linux Out-Of-Memory (OOM) Killer. Namun, saat diuji menggunakan Valgrind Memcheck dan LeakSanitizer (LSan) di staging environment dengan simulasi beban singkat, kedua tool melaporkan `0 bytes leaked in 0 blocks`. Analisis akar masalah teknis apa saja yang dapat menjelaskan fenomena ini (pertimbangkan konsep *global registry bloat*, *arena leakage*, dan *heap fragmentation / virtual memory allocation behavior* seperti `mmap` vs `brk` threshold).

4. **Desain Free-Chunk Splitting dan Boundary Tagging**  
   Dalam implementasi *explicit free-list allocator*, jelaskan konsep *Knuth's Boundary Tags* (header dan footer yang mereplikasi status ukuran dan flag alokasi). Mengapa boundary tag memungkinkan operasi *coalescing* ke belakang (*coalesce with previous block*) berjalan dalam kompleksitas waktu $O(1)$? Bagaimana cara mengoptimalkan ukuran memori untuk mengeliminasi footer pada blok yang sedang dialokasikan?

5. **Analisis Core Dump Akibat Heap Corruption**  
   Diberikan potongan output GDB berikut dari sebuah crash di production environment:
   ```text
   #0  0x00007ffff7a898b7 in __GI_raise (sig=sig@entry=6) at ../sysdeps/unix/sysv/linux/raise.c:51
   #1  0x00007ffff7a8b23a in __GI_abort () at abort.c:89
   #2  0x00007ffff7acd4c0 in __libc_message (action=action@entry=do_abort, fmt=fmt@entry=0x7ffff7bf7028 "%s\n") at ../sysdeps/posix/libc_fatal.c:181
   #3  0x00007ffff7ad4d9a in malloc_printerr (str=str@entry=0x7ffff7bf4d4d "corrupted double-linked list") at malloc.c:5350
   #4  0x00007ffff7ad7b65 in _int_free (av=0x7ffff7dd1b20 <main_arena>, p=0x555555759a20, have_lock=0) at malloc.c:4298
   #5  0x0000555555555314 in worker_cleanup (ctx=0x555555759a30) at worker.c:142
   ```
   Rekonstruksikan mekanisme internal glibc `_int_free` yang memicu pesan `corrupted double-linked list`. Instruksi integritas apa yang dilanggar oleh pointer `p` sebelum memasuki `malloc_printerr`, dan langkah-langkah praktis apa yang harus Anda lakukan pada GDB untuk menelusuri memori di sekitar `0x555555759a20` guna mengidentifikasi *culprit* penulisan memori liar tersebut?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Alokasi pada Sistem Trading Frekuensi Tinggi (HFT)
Sebuah sistem limit-order-book C11 berjalan pada server Linux multi-core (64-core NUMA node). Pada pengujian throughput tinggi (1.000.000 order/detik), p99.99 latensi melonjak dari 850 nanodetik menjadi 45 milidetik. Hasil profiling thread menggunakan `perf` menunjukkan bottleneck masif pada fungsi glibc `sysmalloc`, mutex lock contention di `_int_malloc`, dan page fault handler kernel (`do_page_fault` -> `clear_page_c_evex`).
*   **Pertanyaan Diagnostik:**
    1. Mengapa alokator default OS gagal memenuhi ekspektasi latensi deterministic pada skenario ini, dan mengapa page fault kernel muncul di tengah pemrosesan order?
    2. Rancang arsitektur subalokator hybrid (misalnya kombinasi *Thread-Local Storage (TLS) Pool Allocator* dan *Pre-allocated Arena*) yang mengeliminasi lock-contention, syscall `mmap`/`brk`, serta page fault saat runtime pemrosesan order aktif.

### Skenario B: Race Condition dan Memory Corruption pada Multithreaded Job Queue
Sebuah engine simulasi fisik 3D menggunakan custom lock-free memory allocator berbasis *Single-Producer Single-Consumer (SPSC) Ring Buffer* untuk mentransfer data paket kalkulasi antar worker thread. Di bawah stress testing berat, terjadi crash intermiten dengan indikasi pointer payload menunjuk ke alamat memori yang sudah di-overwrite oleh task generasi berikutnya sebelum thread konsumen selesai membaca datanya.
*   **Pertanyaan Diagnostik:**
    1. Analisis bagaimana fenomena *instruction reordering* oleh compiler atau *weak memory ordering* (out-of-order execution oleh CPU) dapat merusak sinkronisasi antara alokasi ring buffer dan status ketersediaan data payload jika memory fence / atomic release-acquire semantics tidak diterapkan secara presisi.
    2. Tuliskan pseudocode/implementasi C11 atomics (`stdatomic.h`) yang mendemonstrasikan pola penulisan payload, sinkronisasi pointer head/tail menggunakan `memory_order_release` dan `memory_order_acquire`, untuk memastikan konsumen tidak pernah membaca payload yang belum selesai diinisialisasi atau telah di-reclaim.

### Skenario C: Lonjakan Virtual Memory Footprint (VIRT vs. RSS) pada Embedded Gateway
Sebuah router IoT dengan RAM fisik terbatas (128 MB) menggunakan subalokator custom untuk menangani routing paket data jaringan. Meskipun monitoring `valgrind` menyatakan aplikasi tidak memiliki direct memory leak, monitoring sistem via `/proc/<pid>/status` menunjukkan bahwa `VmSize` (Virtual Memory) membengkak mendekati batas arsitektur 32-bit (hampir 3 GB) sementara `VmRSS` (Resident Set) hanya sekitar 40 MB. Tiba-tiba, thread baru gagal dibuat (`pthread_create` mengembalikan `EAGAIN` atau `ENOMEM`).
*   **Pertanyaan Diagnostik:**
    1. Apa akar penyebab struktural yang membuat Virtual Memory membengkak drastis tanpa diiringi lonjakan Resident Memory pada implementasi custom allocator berbasis *chunking* atau `mmap`?
    2. Evaluasi trade-off arsitektur antara pemesanan ruang alamat virtual (*address space reservation via PROT_NONE*) versus komitmen memori fisik (*PROT_READ | PROT_WRITE*). Bagaimana Anda menata ulang strategi alokasi agar sistem embedded 32-bit ini terhindar dari *virtual address space exhaustion*?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Cache-Aligned Thread-Safe Slab Allocator dengan Leak Tracking

#### Deskripsi Masalah:
Sistem pemrosesan jaringan membutuhkan alokator blok berukuran tetap (*Slab Allocator*) untuk mengalokasikan struct `NetworkPacket` (ukuran 256 byte) secara masif tanpa memicu overhead general-purpose allocator dan tanpa fragmentasi eksternal. Anda ditugaskan untuk mengimplementasikan subalokator dari scratch dengan performa microsecond, terisolasi dalam satu file implementasi yang robust.

#### Requirements Teknis:
1. **Inisialisasi Memori:**
   - Alokasikan memori utama (*Backing Store*) menggunakan `mmap` (bukan `malloc`) dengan ukuran kelipatan System Page Size (biasanya 4096 byte).
   - Pastikan setiap blok memori yang dikembalikan ke user memiliki data alignment 64-byte (setara CPU cache-line size) untuk mencegah *false sharing* antar core.
2. **Metadata & Intrusive Free-List:**
   - Gunakan teknik *Intrusive Linked List* di mana pointer `next` disimpan langsung di dalam blok yang belum terpakai. Tidak boleh ada alokasi memori terpisah untuk melacak linked list.
3. **Thread-Safety Minimal Overhead:**
   - Lindungi operasi `slab_alloc()` dan `slab_free()` menggunakan POSIX Mutex yang dioptimalkan (`pthread_mutex_t`), atau implementasikan thread-caching sederhana jika memungkinkan.
4. **Debug & Canary Verification:**
   - Sisipkan *Canary byte* (misalnya nilai hex `0xCAFEBABE`) di batas payload saat mode debug aktif (`#ifdef DEBUG`) untuk memverifikasi *out-of-bounds write*.
   - Implementasikan fungsi diagnosa `slab_dump_stats()` yang mencetak: total kapasitas, jumlah blok aktif, jumlah blok bebas, rasio fragmentasi internal, dan alamat blok yang masih mengalami leak saat penghancuran slab (`slab_destroy()`).

#### Constraints:
* Bahasa: Pure C (C99 atau C11).
* Dilarang keras menggunakan `malloc()`, `calloc()`, `realloc()`, atau `free()` dari `<stdlib.h>` di seluruh implementasi. Semua interaksi memori level OS harus melalui `mmap()` dan `munmap()` (`<sys/mman.h>`).
* Performa alokasi dan dealokasi harus berkisar dalam kompleksitas waktu konstan $O(1)$.
* Harus bersih dari peringatan compiler: `-Wall -Wextra -Werror -pedantic`.

#### Expected Output:
Program harus menyertakan fungsi `main()` untuk stress-test:
1. Melakukan 100.000 iterasi alokasi dan dealokasi secara multithreaded (minimal 4 thread pekerja).
2. Simulasi kasus deteksi *double-free*: alokator harus menangkap error dan menghentikan eksekusi dengan pesan assert yang terstruktur.
3. Mencetak laporan profil memori di akhir pengujian yang mengonfirmasi $0$ byte leak saat program ditutup secara normal, lolos verifikasi AddressSanitizer (`-fsanitize=address,undefined`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme pemetaan memori sistem operasi (`mmap`, `brk`/`sbrk`, Virtual Memory subsystem, Page Tables, dan Page Faults).
- [ ] Perbedaan fundamental arsitektur dan trade-off kompleksitas waktu/ruang dari 4 subalokator klasik: *Arena/Linear*, *Pool/Slab*, *Buddy*, dan *Free-List (First-fit/Best-fit)*.
- [ ] Konsep CPU Cache-line, False Sharing, Data Alignment, serta implikasinya terhadap performa pointer subalokator pada arsitektur SIMD/multicore.
- [ ] Cara kerja internal AddressSanitizer (Shadow Bytes, Poisoning, Redzones) dan perbandingannya dengan dynamic binary translation (Valgrind).
- [ ] Mengapa general-purpose allocator (`ptmalloc`, `jemalloc`, `mimalloc`) menggunakan arena multithreaded dan segregasi ukuran kelas (*size classes*) untuk mereduksi lock-contention.

### Saya tidak perlu menghafal:
- [ ] Struktur data internal spesifik baris-per-baris dari `malloc.c` milik glibc (seperti layout bit field internal `mchunkptr`).
- [ ] Syscall opcode spesifik arsitektur untuk alokasi memori pada assembly level.
- [ ] Flag bitmask numerik dari `mmap` di luar yang standar (`MAP_PRIVATE`, `MAP_ANONYMOUS`, `PROT_READ`, `PROT_WRITE`).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *Arena Allocator* dan *Pool Allocator* yang thread-safe dan cache-aligned dari scratch menggunakan standard C.
- [ ] Menggunakan Valgrind (`memcheck`, `massif`) untuk mendeteksi memory leak, uninitialized reads, dan membuat grafik timeline heap usage.
- [ ] Mengompilasi, mengeksekusi, dan menginterpretasikan laporan crash dari AddressSanitizer (ASan), MemorySanitizer (MSan), dan UndefinedBehaviorSanitizer (UBSan).
- [ ] Mendiagnosis heap corruption dan menginspeksi memori rusak menggunakan GDB melalui dump memory (`x/<n>xb`), backtrace, dan analisis core file.
- [ ] Mendesain isolasi alokasi memori untuk sistem mission-critical di mana fragmentasi eksternal bernilai nol mutlak (zero-fragmentation guarantee).