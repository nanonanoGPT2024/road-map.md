# BAB 05: Quiz, Challenge, & Knowledge Check
**Bab 05: Hierarki Memori, Cache Subsystem, dan Virtual Memory**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dualitas Prinsip Locality dan Mekanisme Prefetching
Jelaskan perbedaan mendasar antara *Temporal Locality* dan *Spatial Locality*. Bagaimana unit *Hardware Prefetcher* pada CPU modern memanfaatkan kedua prinsip ini saat memuat data dari DRAM ke dalam *Cache Line* (umumnya berukuran 64 byte), dan mengapa perulangan traversal array berbasis baris (*row-major*) menghasilkan performa yang secara signifikan lebih superior dibandingkan traversal berbasis kolom (*column-major*) pada bahasa seperti C/C++?

### Soal 1.2: Anatomi dan Komparasi Organisasi Cache
Bandingkan arsitektur *Direct-Mapped Cache*, *N-Way Set-Associative Cache*, dan *Fully-Associative Cache*. Uraikan bagaimana sebuah alamat memori fisik dipecah menjadi bit *Tag*, *Index*, dan *Offset*. Dalam kondisi beban kerja seperti apa fenomena *Cache Thrashing* terjadi pada *Direct-Mapped Cache*, dan bagaimana peningkatan *associativity* memitigasi masalah tersebut dengan mengorbankan latensi sirkuit komparator?

### Soal 1.3: Mekanisme Resolusi Alamat pada Multi-Level Paging
Jelaskan siklus hidup translasi alamat virtual ke alamat fisik (*Virtual-to-Physical Address Translation*) pada arsitektur x86-64 (4-level paging: PML4 $\rightarrow$ PDPT $\rightarrow$ PD $\rightarrow$ PT). Uraikan peran register kontrol `CR3`, struktur *Page Table Entry* (PTE), serta jelaskan konsekuensi performa jika setiap akses memori harus melakukan 4 kali *memory dereference* tanpa keberadaan *hardware accelerator*.

### Soal 1.4: Kebijakan Propagasi Modifikasi Memori: Write-Through vs. Write-Back
Analisislah trade-off antara arsitektur *Write-Through* (dikombinasikan dengan *Write-Buffer*) dan *Write-Back* (memanfaatkan *Dirty Bit*). Dalam konteks alokasi tulis (*Write-Allocate* vs. *No-Write-Allocate*), jelaskan urutan operasi yang dieksekusi CPU ketika terjadi *Write Miss* pada sistem yang menerapkan kombinasi *Write-Back + Write-Allocate*.

### Soal 1.5: Translation Lookaside Buffer (TLB) dan TLB Shootdown
Apa fungsi spesifik dari *Translation Lookaside Buffer* (TLB) baik untuk instruksi (iTLB) maupun data (dTLB)? Jelaskan secara mendalam proses terjadinya *TLB Shootdown* pada sistem multi-core Symmetric Multiprocessing (SMP) saat suatu proses memanggil *system call* `munmap()` atau memodifikasi proteksi halaman memori via `mprotect()`, serta dampaknya terhadap *Inter-Processor Interrupt* (IPI).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Dekomposisi 4C Cache Misses dan Fenomena False Sharing
Model *4C Cache Misses* mengkategorikan *miss* ke dalam: *Compulsory*, *Capacity*, *Conflict*, dan *Coherence*. 
1. Bagaimana Anda mengisolasi perbedaan antara *Capacity Miss* dan *Conflict Miss* menggunakan profil perangkat keras (*hardware performance counters*)?
2. Jelaskan bagaimana *Coherence Miss* memicu fenomena **False Sharing** pada aplikasi multi-threaded ketika dua thread pada core berbeda memodifikasi variabel independen yang berada pada baris cache (*cache line*) yang sama. Bagaimana cara mendeteksinya menggunakan tooling tingkat lanjut?

### Soal 2.2: Alur Penanganan Page Fault oleh Linux Kernel
Uraikan langkah demi langkah transisi state dari tingkat sirkuit (*hardware exception*) hingga eksekusi kode kernel ketika CPU membangkitkan interrupt `#PF` (*Page Fault Exception* Vector 14). Bedakan skenario penanganan antara:
* **Minor/Soft Page Fault** (misalnya: alokasi memori pertama via *Demand Paging* atau mekanisme *Copy-On-Write* pasca `fork()`).
* **Major/Hard Page Fault** (misalnya: memuat data dari *backing store* swap atau *file-backed memory mapped* via `mmap()`).
* **Invalid Page Fault** yang berujung pada pengiriman sinyal `SIGSEGV` ke thread eksekusi.

### Soal 2.3: Implikasi Transparent Huge Pages (THP) terhadap Latensi Sistem
Arsitektur modern mendukung ukuran halaman 2MB dan 1GB di samping ukuran standar 4KB. Analisislah mengapa fitur *Transparent Huge Pages* (THP) pada Linux dapat mereduksi beban TLB miss secara dramatis pada aplikasi dengan footprint memori masif, namun secara bersamaan dapat menyebabkan lonjakan latensi ekstrim (*tail latency spike/jitter*) pada sistem database in-memory seperti Redis atau embedded RocksDB akibat mekanisme alokasi sinkron dan proses *memory compaction* di latar belakang (`khugepaged`).

### Soal 2.4: Protokol Cache Coherency (MESI / MOESI) Under the Hood
Diberikan arsitektur multi-core yang menggunakan protokol koherensi MESI (*Modified, Exclusive, Shared, Invalid*):
Asumsikan Core 0 dan Core 1 sama-sama memegang alamat memori `0x00A0` dalam status `Shared (S)`. 
1. Uraikan sinyal bus (*bus snooping transactions*) yang harus diemisikan Core 0 jika ia mengeksekusi instruksi assembly `ADD [0x00A0], 1`.
2. Jelaskan transisi status state-machine pada Core 0 dan Core 1.
3. Kapan protokol MOESI lebih unggul dibandingkan MESI murni dalam konteks sharing data yang telah termodifikasi (*Owner (O) state*) tanpa melibatkan akses tulis kembali ke L3 cache/RAM?

### Soal 2.5: Weak Memory Ordering dan Hardware Memory Barriers
Pada arsitektur modern (seperti x86 dengan model *Total Store Order* / TSO versus ARM64 dengan model *Weakly-Ordered*):
1. Mengapa compiler barrier (seperti `asm volatile("" ::: "memory")`) tidak cukup untuk menjamin visibilitas urutan operasi memori antar core fisik, sehingga membutuhkan instruksi perangkat keras seperti `mfence`, `dmb ish`, atau load-acquire/store-release semantics?
2. Analisislah skenario eksekusi *Out-of-Order Execution Unit* (Store Buffer dan Invalidation Queue) yang menyebabkan algoritma penguncian tanpa kunci (*lock-free*) berbasis Dekker atau Peterson gagal jika hardware memory barrier diabaikan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Degradasi Throughput pada Real-time Inference Pipeline
* **Konteks:** Sebuah microservice komputasi numerik real-time memproses tensor data masif. Setelah migrasi ke arsitektur data baru, throughput drop hingga 78%, sementara pemanfaatan CPU (*CPU Utilization*) tercatat 100% pada semua core.
* **Metrik & Diagnostik:**
  * Profiling via Linux `perf stat` menghasilkan data berikut:
    ```text
    12,450,210,500   cycles                    #   3.412 GHz
     2,490,042,100   instructions              #   0.20  insn per cycle (IPC)
       820,110,400   L1-dcache-load-misses     #  18.42% of all L1-dcache hits
       310,500,200   LLC-load-misses           #  45.10% of all LL-cache hits
    ```
  * Kode sumber utama menunjukkan penggunaan struktur:
    ```c
    struct DataPoint {
        double features[64];
        uint64_t id;
        char label[32];
        bool is_valid;
    };
    struct DataPoint dataset[1000000];
    // Loop pemrosesan hanya membaca field `features[0]` dan `is_valid`
    ```
* **Pertanyaan Diagnostik:**
  1. Analisislah akar masalah teknis mengapa nilai IPC (*Instructions Per Cycle*) jatuh ke level kritis 0.20 meskipun CPU 100% tersaturasi.
  2. Identifikasi patologi memori yang terjadi pada layout data `struct DataPoint` (*Array-of-Structures* / AoS).
  3. Rancang restrukturisasi layout memori (transformasi ke *Structure-of-Arrays* / SoA atau *hybrid/tiled layout*) untuk mengoptimalkan penggunaan baris cache L1/L2 dan memaksimalkan *hardware prefetching throughput*.

---

### Skenario B: Latency Spikes Ekstrim pada Multi-Threaded Matching Engine
* **Konteks:** Engine pencocokan order transaksi finansial dengan arsitektur multi-thread mengalami lonjakan latensi p99.99 dari $45\,\mu\text{s}$ menjadi $14.2\,\text{ms}$ setiap kali volume transaksi harian melonjak 200%.
* **Gejala Sistem:**
  * Tidak ada korelasi dengan *Garbage Collection* atau OS context switching.
  * Analisis `perf c2c` (*Cache-to-Cache*) menunjukkan *HitM* (*Hit on Modified Cache Line*) yang masif pada satu segmen alamat memori tertentu.
  * Kode metrik internal mengimplementasikan monitoring counter sederhana:
    ```cpp
    struct EngineMetrics {
        std::atomic<uint64_t> order_processed_core0;
        std::atomic<uint64_t> order_processed_core1;
        std::atomic<uint64_t> order_processed_core2;
        std::atomic<uint64_t> order_processed_core3;
    };
    ```
* **Pertanyaan Diagnostik:**
  1. Buktikan secara arsitektural mengapa struktur data `EngineMetrics` di atas memicu *Cache Line Bouncing* (invalidation storm) antar-core.
  2. Jelaskan interaksi protokol MESI pada interkoneksi cincin/mesh CPU saat core-core tersebut mengeksekusi operasi `fetch_add` secara konkuren.
  3. Tuliskan perbaikan kode C++ definitif dengan memanfaatkan alignment specifier yang tepat untuk mengeliminasi false sharing secara permanen tanpa merusak portabilitas memory footprint.

---

### Skenario C: Dilema Arsitektur Memory Virtualisasi pada Database In-Memory 500GB
* **Konteks:** Anda memimpin arsitektur sistem penyimpanan *in-memory* terdistribusi sebesar 500GB RAM per node. Arsitek tim mengusulkan untuk mengaktifkan Linux *Explicit HugePages* 1GB (via `hugetlbfs`) untuk menghapus overhead page-table traversal, sedangkan tim infrastruktur menolak karena takut akan fragmentasi memori dan waktu *provisioning* OS yang kaku.
* **Kondisi Eksisting:**
  * Memori fisik: 512GB DDR4 ECC.
  * Pola akses: Random read/write seragam pada miliaran objek kecil ($64-256$ byte).
  * Sistem sering melakukan alokasi dan dealokasi chunk dinamis.
* **Pertanyaan Diagnostik:**
  1. Hitung penghematan konsumsi memori untuk struktur page table itu sendiri (asumsikan page table entry = 8 byte) jika memori 500GB dialokasikan menggunakan 4KB pages vs 2MB pages vs 1GB pages.
  2. Evaluasi dampak performa pengurangan ukuran Page Table terhadap *TLB Coverage*. Berapa banyak entri TLB yang dibutuhkan untuk memetakan keseluruhan 500GB dataset pada masing-masing ukuran halaman?
  3. Berikan rekomendasi teknis yang komprehensif: Apakah sistem harus menggunakan 4KB default, Transparent Huge Pages (THP), Explicit 2MB HugePages, atau 1GB HugePages? Jelaskan justifikasi arsitektural Anda dengan mempertimbangkan risiko fragmentasi eksternal, OS allocation stalls, dan performa random memory walk.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Cache-Oblivious Matrix Engine & Lock-Free SPSC Ring Buffer

#### Deskripsi Masalah
Dalam rekayasa sistem performa tinggi, pemahaman hierarki memori membedakan kode yang lambat akibat *memory-bound stalls* dengan kode yang mencapai batas throughput saturasi bus memori fisik (*line rate*). Anda diminta untuk mengimplementasikan dan membuktikan dua subsistem kritis yang mengoptimalkan hierarki memori dari level L1 hingga RAM fisik.

#### Persyaratan Teknis (Requirements)
1. **Cache-Oblivious Matrix Transposition Engine (C/C++ atau Rust):**
   * Implementasikan algoritma transposisi matriks rekursif berbasis strategi *Divide-and-Conquer* yang bekerja secara optimal pada sembarang ukuran hierarki cache tanpa memerlukan parameterisasi ukuran cache secara manual (*cache-oblivious*).
   * Bandingkan performanya secara kuantitatif dengan algoritma transposisi matriks standar (*naive nested loop*) pada matriks kuadrat presisi ganda (`double`) dengan ukuran $N = 4096 \times 4096$ dan $N = 8192 \times 8192$.
   * Ukur dan tampilkan metrik L1 Data Cache Miss, LLC (Last Level Cache) Miss, dan IPC menggunakan integrasi programatik `libperf` / Linux `perf_event_open` atau profiler bawaan sistem.

2. **Zero-Copy Cache-Aligned SPSC (Single Producer Single Consumer) Ring Buffer:**
   * Bangun implementasi antrean melingkar (*circular ring buffer*) berbasis memori bersama tanpa kunci (*lock-free*).
   * Implementasikan pencegahan *False Sharing* secara eksplisit dengan memastikan struktur producer dan consumer terisolasi pada *cache line* yang berbeda (`alignas(64)` atau kelipatannya).
   * Gunakan operasi *atomic* dengan model memori eksplisit (`std::memory_order_acquire` dan `std::memory_order_release`) untuk menjamin koordinasi data antar-core tanpa overhead instruksi *heavyweight bus lock* (`mfence`).
   * Terapkan teknik *Virtual Memory Wrapping Trick* (menggunakan dua kali pemetaan *virtual address space* berturut-turut yang menunjuk ke *physical memory frame* yang sama via `mmap`) untuk mengeliminasi operasi pengecekan modulo/boundary wrap-around pada pointer buffer.

#### Batasan Implementasi (Constraints)
* **Zero Dynamic Allocation in Hot Path:** Alokasi heap hanya diizinkan saat tahap inisialisasi; hot-path processing loop wajib $0$ heap allocation (`malloc`/`free` atau `new`/`delete` dilarang keras).
* **Hardware Portability:** Harus dapat dikompilasi dengan optimasi `-O3` pada arsitektur x86_64 atau ARM64 tanpa menimbulkan *undefined behavior*.
* **Memory Safety:** Tidak boleh ada *data race* (diverifikasi via ThreadSanitizer: `-fsanitize=thread`).

#### Output yang Diharapkan (Expected Deliverables)
1. **Source Code Lengkap:** Program mandiri yang mengimplementasikan matriks engine dan ring-buffer.
2. **Laporan Kuantitatif (Benchmark Table):**
   * Eksekusi transposisi matriks:
     * Ukuran $N$
     * Waktu eksekusi Naive vs Cache-Oblivious (milidetik)
     * L1 Miss Rate (%) dan LLC Misses
     * Memory Throughput (GB/s)
   * Eksekusi SPSC Ring Buffer:
     * Throughput operasi (juta pesan per detik)
     * Latensi p50, p99, dan p99.9 dalam skala nanodetik.
3. **Analisis Teknis (Post-Mortem Engine):** Uraian penjelasan analitis mengapa optimasi layout cache-aligned dan memory-mapping trick berhasil mereduksi pipeline stalls pada level mikroarsitektur CPU.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Prinsip matematis dan fisika di balik *Memory Hierarchy Wall* (mengapa DRAM jauh lebih lambat daripada kecepatan siklus CPU register/L1).
- [ ] Representasi matematis pembagian alamat memori menjadi Tag, Index, dan Offset pada berbagai arsitektur cache associativity.
- [ ] Mengapa baris cache standar CPU modern disetel pada ukuran 64 byte, beserta trade-off spasial dan latensi transfer bus.
- [ ] Siklus resolusi alamat virtual-ke-fisik, struktur Page Table (Level 1 hingga Level 4 pada x86-64), dan format entri PTE (Present bit, R/W bit, Dirty bit, Accessed bit).
- [ ] Mekanisme kerja TLB, implikasi TLB Miss, dan biaya komputasi dari proses *TLB Shootdown* pada multi-socket/multi-core server.
- [ ] Protokol koherensi memori bus-snooping (MESI/MOESI) dan transisi antar state (*Modified*, *Owner*, *Exclusive*, *Shared*, *Invalid*).
- [ ] Perbedaan fundamental antara *Minor Page Fault*, *Major Page Fault*, dan *Segmentation Fault* (`SEGV`).
- [ ] Implikasi hardware memory ordering (Store Buffers, Invalidation Queues, Weak vs. Strong Memory Models) terhadap pemrograman konkurensi.
- [ ] Cara kerja teknik virtual memory mirroring menggunakan `mmap` untuk membuat contiguous circular ring buffers.

### Saya tidak perlu menghafal:
- [ ] Nilai eksak hex opcode instruksi assembly untuk TLB flushing (`invlpg`) atau bus locking (`lock cmpxchg`).
- [ ] Letak bit absolut dari setiap register kontrol CPU (`CR0`, `CR3`, `CR4`) di level bitfield silikon.
- [ ] Angka latensi nanodetik absolut dari vendor tertentu (misal: siklus akses DDR4 vs DDR5), melainkan urutan magnitudo relatifnya (L1 $\sim 1\text{ns}$, L2 $\sim 3-4\text{ns}$, L3 $\sim 10-15\text{ns}$, RAM $\sim 50-80\text{ns}$, SSD $\sim 10-100\mu\text{s}$).
- [ ] Implementasi algoritma internal kernel Linux scheduler saat menentukan penempatan thread NUMA node secara spesifik.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengukur L1/L2/LLC cache miss serta IPC pada aplikasi menggunakan tools analisis perangkat keras tingkat rendah (seperti `perf stat`, `perf record`, atau hardware performance counter APIs).
- [ ] Mengidentifikasi masalah *False Sharing* pada aplikasi multi-threaded menggunakan `perf c2c` dan memperbaikinya menggunakan data alignment directives (`alignas(64)` / compile-time attributes).
- [ ] Mengonfigurasi, mengaktifkan, dan mengevaluasi status HugePages / Transparent Huge Pages (THP) pada lingkungan Linux enterprise serta mengukur dampaknya pada TLB miss rate via `/proc/meminfo` dan `/sys/kernel/mm/transparent_hugepage/`.
- [ ] Melakukan restrukturisasi arsitektur data dari *Array-of-Structures* (AoS) ke *Structure-of-Arrays* (SoA) untuk meningkatkan efisiensi SIMD vectorization dan spatial locality.
- [ ] Menulis kode sistem bebas data race yang mengimplementasikan operasi atomik dengan memory ordering yang tepat (`acquire-release semantics`) tanpa bergantung pada mutual exclusion locks (`mutex`).