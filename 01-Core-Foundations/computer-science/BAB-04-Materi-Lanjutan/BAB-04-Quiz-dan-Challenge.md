# BAB 04: Quiz, Challenge, & Knowledge Check
**Bab 04: Proses, Thread, dan Konkurensi Tingkat Rendah (Process Management, Threads, & Low-Level Concurrency)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Process vs Thread pada Level Kernel**
   Jelaskan secara mendalam perbedaan struktural di tingkat kernel antara *process* dan *thread* (khususnya pada model 1:1 seperti POSIX Threads via Linux NPTL). Bagaimana struktur data `task_struct`, alokasi Virtual Memory (Memory Descriptor/`mm_struct`), serta *File Descriptor Table* dimanipulasi ketika sebuah thread baru di-instansiasi melalui `clone()` dibandingkan dengan `fork()`?

2. **Mekanisme dan Overhead Context Switching**
   Uraikan urutan eksekusi step-by-step yang terjadi pada CPU ketika terjadi *preemptive context switch* antar dua thread dari proses yang berbeda. Jelaskan komponen overhead deterministik (*direct overhead*: penyelamatan register, kernel mode transition, scheduler execution) dan non-deterministik (*indirect overhead*: TLB invalidation/flushing, cache pollution, pipeline stall).

3. **Prinsip Formal Mutual Exclusion dan Algoritma Dasar**
   Sebutkan empat kondisi formal yang wajib dipenuhi oleh setiap solusi *Mutual Exclusion* (Dijkstra Criteria). Mengapa algoritma berbasis perangkat lunak murni seperti *Peterson’s Algorithm* tidak lagi menjamin konsistensi pada prosesor multi-core modern yang menggunakan arsitektur memori *Out-of-Order (OoO) execution* dan *Store Buffers*?

4. **Karakteristik Primitif Sinkronisasi: Mutex vs Spinlock vs Futex**
   Bandingkan karakteristik operasional dari `Spinlock`, `Kernel Mutex`, dan `Futex` (Fast Userspace Mutex). Kapan dan dalam kondisi metrik beban kerja seperti apa sebuah *Spinlock* secara drastis mengungguli *Mutex*, dan kapan *Spinlock* justru menyebabkan degradasi performa sistem secara katastropik (*priority inversion* / *CPU starvation*)?

5. **Kondisi Formal Deadlock (Coffman Conditions)**
   Analisis keempat kondisi Coffman (*Mutual Exclusion*, *Hold and Wait*, *No Preemption*, *Circular Wait*). Jelaskan bagaimana strategi alokasi sumber daya berbasis *Total Resource Ordering* (Hierarchical Resource Allocation) membuktikan secara matematis eliminasi salah satu dari kondisi Coffman tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Fenomena False Sharing pada Arsitektur Cache L1/L2**
   Dua thread independen berjalan pada dua Core fisik yang berbeda. Thread A secara berulang memperbarui variabel `uint64_t counter_a`, sementara Thread B memperbarui `uint64_t counter_b`. Kedua variabel dialokasikan secara bersebelahan di heap memory. Jelaskan interaksi protokol koherensi cache (misal: MESI/MOESI) yang memicu fenomena *False Sharing*, dampaknya terhadap bus memori, serta bagaimana teknik *cacheline alignment/padding* mengatasi masalah ini.

2. **Memory Ordering, Reordering, dan Hardware Memory Barriers**
   Diberikan pseudo-code berikut yang dieksekusi secara paralel:
   ```c
   // Thread 1
   data = 42;
   ready = 1;

   // Thread 2
   while (!ready);
   assert(data == 42);
   ```
   Mengapa pada arsitektur CPU dengan model memori santai (seperti ARM64 atau DEC Alpha) `assert(data == 42)` bisa gagal (assertion violation)? Jelaskan peran instruksi *Acquire-Release Semantics* dan *Memory Barrier* (Fences) dalam mencegah *compiler/hardware reordering*.

3. **Mekanisme Futex Under-the-Hood**
   Jelaskan alur eksekusi `sys_futex()` pada Linux ketika terjadi *uncontended lock* versus *contended lock*. Bagaimana integrasi antara atomic CAS (`Compare-And-Swap`) di userspace dan antrean tidur (*wait queue*) berbasis hash table di kernel space meminimalkan context switch overhead?

4. **Deadlock Detection via Lock-Dep & Static Analysis**
   Ketika menganalisis sebuah crash dump dari aplikasi C++ multithreaded yang mengalami *hang*, Anda melihat Thread 1 menunggu `Mutex B` saat memegang `Mutex A`, sementara Thread 2 menunggu `Mutex C` saat memegang `Mutex B`, dan Thread 3 menunggu `Mutex A` saat memegang `Mutex C`. Jelaskan bagaimana *Wait-For-Graph (WFG)* dibangun secara algoritmik untuk mendeteksi *cycle*, dan bagaimana runtime locking validator (seperti Linux Kernel `lockdep`) mendeteksi potensi deadlock sebelum deadlock tersebut benar-benar terjadi secara fisik.

5. **ABA Problem pada Lock-Free Data Structures**
   Jelaskan bagaimana *ABA Problem* terjadi pada implementasi *Lock-Free Concurrent Stack* berbasis linked list yang menggunakan primitif `Atomic CAS`. Mengapa pengecekan nilai pointer identik tidak menjamin integritas referensi memori, dan bagaimana teknik *Tagged Pointers* (Version Counters) atau *Hazard Pointers* memitigasi risiko *use-after-free* dalam skenario ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike Ekstrem dan Livelock pada High-Frequency Trading Core
Sebuah subsistem *order-matching engine* berkecepatan mikrodetik dijalankan pada server NUMA multi-socket dengan 64 core CPU. Tim merekayasa komunikasi antar thread menggunakan *busy-waiting spinlock* agresif untuk menghindari *latency context switch* kernel. 
Namun, saat volume order melonjak:
- Penggunaan CPU melonjak ke 100% pada semua core.
- *Throughput* pemrosesan order anjlok sebesar 92%.
- Metrik hardware counter via `perf` menunjukkan metrik `cycle_activity.stalls_total` dan *L3 Cache Invalidation Misses* meroket tajam.

**Pertanyaan Diagnostik:**
1. Apa akar penyebab degradasi performa ini ditinjau dari saturasi *inter-connect bus* (QPI/UPI) dan *cache coherence traffic storm* akibat fenomena *cache-line ping-pong*?
2. Bagaimana Anda meredesain primitif sinkronisasi ini (misalnya mengombinasikan `PAUSE` instruction, exponential back-off, atau lock-free ring-buffer SPSC terisolasi) agar throughput tetap stabil tanpa mengorbankan latensi p99 secara liar?

---

### Skenario B: Misteri Silent Data Corruption pada Multi-Threaded In-Memory Index
Sebuah database internal high-concurrency menggunakan custom *Concurrent Hash Map* berbasis bucket-level locking. Dalam pengetesan beban (load testing) selama 48 jam, sistem mendeteksi kerusakan pointer (*segmentation fault*) yang terjadi secara sporadis (hanya 1 dari 10 juta operasi write paralel). 
Pemeriksaan awal menunjukkan:
- Semua mutasi node bucket dilindungi oleh `pthread_mutex_t`.
- Operasi traversal pembacaan (*read path*) dioptimasi menggunakan mekanisme *Lock-Free Read* berbasis atomic pointer load tanpa akuisisi mutex, dengan asumsi bahwa mutasi pointer adalah atomik secara hardware pada arsitektur x86_64.

**Pertanyaan Diagnostik:**
1. Mengapa asumsi "pointer write atomik pada x86_64 menjamin lock-free read yang aman" fatal jika node yang dihapus langsung di-*free* ke memory pool menggunakan `free()` standar (*Dangling Pointer / Read-While-Reclaim Race Condition*)?
2. Bagaimana mekanisme *Epoch-Based Reclamation* (EBR) atau *Read-Copy-Update* (RCU) memecahkan masalah ini dengan menjamin bahwa memori hanya dideallokasi setelah semua thread pembaca yang aktif melewati fase *quiescent state*?

---

### Skenario C: Prioritas Terbalik (Priority Inversion) dan Watchdog Timeout pada Embedded Gateway
Sebuah sistem telemetri IoT industrial menjalankan RTOS (Real-Time Operating System) dengan tiga thread prioritas tetap:
- **Thread High (H):** Menangani interupsi sensor keselamatan kritis setiap 10ms.
- **Thread Medium (M):** Melakukan kompresi data jaringan berbasis CPU-bound secara berkala.
- **Thread Low (L):** Mengirim log diagnostik lambat ke flash storage.

Sistem mengalami insiden: Hardware Watchdog me-reboot mesin karena Thread H tidak merespons tepat waktu. Investigasi telemetri mengungkap bahwa Thread L sedang memegang Mutex I/O bersama, Thread H terbangun dan mencoba mengakuisisi Mutex I/O yang sama (sehingga terblokir), dan tepat pada saat itu Thread M terbangun dan mempreempt Thread L karena Thread M memiliki prioritas lebih tinggi dari L.

**Pertanyaan Diagnostik:**
1. Jelaskan bagaimana dinamika di atas menciptakan kondisi *Unbounded Priority Inversion*, di mana Thread prioritas menengah (M) secara tidak langsung memblokir Thread prioritas tinggi (H) tanpa batas waktu yang jelas.
2. Analisis solusi arsitektural untuk problem ini: Bandingkan efektivitas implementasi protokol *Priority Inheritance* (PIP) versus *Priority Ceiling Protocol* (PCP) pada kernel RTOS tersebut.

---

## 4. Chapter Challenge
**Tantangan Praktis: High-Performance Lock-Free SPSC/MPMC Ring Buffer Implementation**

### Problem Statement
Dalam arsitektur sistem konkurensi modern, antrean pesan (*message passing queue*) antar-thread yang menggunakan kernel mutex sering kali menjadi bottleneck utama akibat overhead context switch dan *lock contention*. Anda ditantang untuk merancang dan mengimplementasikan modul antrean data biner tingkat rendah (*circular ring buffer*) berbasis memori bersama tanpa menggunakan mutex maupun spinlock di jalur kritis.

### Requirements & Functionality
1. **Dua Mode Operasi:**
   - **Mode SPSC (Single Producer, Single Consumer):** Implementasi murni berbasis lock-free menggunakan atomic operations dengan model memori yang paling ketat (*Strict Acquire-Release semantics*, bukan sequential consistency penuh).
   - **Mode MPMC (Multi Producer, Multi Consumer):** Implementasi berbasis atomic CAS untuk head dan tail pointers dengan penanganan *wrap-around* dan *ABA Problem*.
2. **Anti-False Sharing:**
   - Struktur data harus secara eksplisit mendistribusikan read index dan write index ke *cache line* yang berbeda menggunakan compiler directives (`alignas(64)` pada arsitektur x86_64).
3. **Zero Dynamic Allocation di Jalur Kritis:**
   - Seluruh alokasi kapasitas ring buffer harus dilakukan secara *pre-allocated* di inisialisasi awal. Operasi `push()` dan `pop()` tidak boleh memanggil `malloc()`/`free()`.
4. **Metrik & Diagnostic Hook:**
   - Sistem harus mengekspos metrik: *drop counter* (ketika buffer penuh), *empty counter* (ketika buffer kosong), dan *CAS retry loop counter*.

### Constraints
- Bahasa: **C11 / C++17** atau **Rust**.
- Tidak boleh menggunakan library concurrency eksternal (hanya `stdatomic.h`, `<atomic>`, atau `std::sync::atomic`).
- Wajib menyertakan unit test multi-threaded yang memverifikasi bahwa:
  - Tidak ada data loss atau korupsi urutan data (*in-order delivery* pada mode SPSC).
  - Tidak terjadi memory leak saat jutaan entri dialirkan secara konruen.
- Verifikasi keamanan memori: Program harus bersih dari *data race* saat diverifikasi menggunakan **ThreadSanitizer (TSan)**:
  `gcc -fsanitize=thread -O2 ...`

### Expected Output
- Kode sumber modular: `ring_buffer.h` dan `ring_buffer.c` (atau ekuivalen Rust).
- Harness benchmark multi-thread yang menampilkan:
  - Operasi per detik (Ops/sec throughput).
  - Latensi transfer per item (skala nanodetik).
  - Log eksekusi ThreadSanitizer yang membuktikan `0 data races detected`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan internal siklus hidup antara *kernel-level thread* dan *user-level thread* (green threads/goroutines) serta biaya context switch masing-masing.
- [ ] Representasi kernel atas sebuah thread via `task_struct`, pembagian ruang alamat memori, dan dampaknya terhadap TLB (*Translation Lookaside Buffer*).
- [ ] Teori formal sinkronisasi: 4 Kondisi Dijkstra untuk Mutual Exclusion dan 4 Kondisi Coffman untuk Deadlock.
- [ ] Mekanisme kerja instruksi atomik CPU: `CAS (Compare-And-Swap)`, `LL/SC (Load-Link/Store-Conditional)`, dan `Fetch-And-Add`.
- [ ] Hierarki memori hardware, protokol koherensi cache (MESI/MOESI), dan fenomena *False Sharing*.
- [ ] Arsitektur *Memory Models* (Sequential Consistency, Acquire-Release, Relaxed Ordering) dan fungsi *Instruction/Memory Barriers*.
- [ ] Mekanisme internal primitives OS: *Spinlock*, *Semaphore*, *Futex*, dan integrasi userspace-kernel transition.
- [ ] Problem konkurensi lanjut: *Priority Inversion*, *ABA Problem*, *Starvation*, dan teknik *Safe Memory Reclamation* (EBR/RCU).

### Saya tidak perlu menghafal:
- [ ] Nomor syscall spesifik untuk `sys_futex` atau `sys_clone` pada setiap arsitektur CPU (cukup pahami semantiknya via POSIX/glibc wrappers).
- [ ] Rincian bitmask register spesifik arsitektur hardware saat context switch (misal: format pasti register floating-point AVX-512 state saving).
- [ ] Sintaks mikro-assembler untuk hardware memory fence pada arsitektur prosesor usang (fokus pada abstraksi C11/C++ `std::memory_order` modern).

### Saya harus bisa melakukan:
- [ ] Menulis dan mendebug program multithreaded menggunakan ThreadSanitizer (`-fsanitize=thread`) dan membedah race condition tersembunyi.
- [ ] Mengukur overhead thread context switch secara kuantitatif menggunakan perkakas benchmarking sistem (`perf`, `ftrace`, atau POSIX timers).
- [ ] Mencegah dan mendeteksi deadlock dengan pemodelan *Wait-For-Graph* dan implementasi *lock ordering protocol* yang ketat.
- [ ] Menggunakan data alignment attributes (`alignas(64)`) untuk memitigasi bottleneck *False Sharing* pada profiling hardware performance counter.
- [ ] Mengimplementasikan algoritma konkuren lock-free dasar (misal: SPSC Ring Buffer atau Treiber Stack) secara benar menggunakan *Acquire-Release memory ordering*.