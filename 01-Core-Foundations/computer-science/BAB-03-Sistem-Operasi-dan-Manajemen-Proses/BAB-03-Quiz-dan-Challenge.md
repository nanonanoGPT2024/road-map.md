# BAB 03: Quiz, Challenge, & Knowledge Check
**Arsitektur Sistem Operasi: Manajemen Proses, Konkurensi, dan Memori Virtual**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Context Switch & Cache Invalidation
Jelaskan secara mendalam siklus hidup eksekusi instruksi ketika sistem operasi melakukan *context switch* dari **Proses A** ke **Proses B** (antar-proses yang berbeda) dibandingkan dari **Thread 1** ke **Thread 2** (dalam proses yang sama).
* **Fokus Analisis:** Apa yang terjadi pada *Program Counter* (PC), *Stack Pointer* (SP), register CPU (GPR), *Process Control Block* (PCB/TCB), *Translation Lookaside Buffer* (TLB), serta *L1/L2/L3 hardware caches*? Jelaskan mengapa alih-proses antar-ruang alamat menghasilkan penalti performa laten yang jauh lebih tinggi daripada alih-utas.

### Soal 1.2: Mekanisme Multi-Level Paging pada Arsitektur 64-bit
Pada arsitektur x86-64 dengan skema paging 4-level (PML4, PDPT, PD, PT) dan ukuran *page* standar 4 KiB:
* Mengapa penggunaan *flat page table* linear tunggal mustahil diterapkan secara fisik untuk ruang alamat virtual 48-bit?
* Bagaimana struktur pohon hierarkis multi-level menghemat alokasi memori fisik untuk proses yang memiliki pola alokasi memori renggang (*sparse address space*)? Tunjukkan skenario di mana *overhead* memori dari multi-level paging justru menjadi lebih besar dibandingkan *flat paging*.

### Soal 1.3: Taksonomi Interupsi: Trap, Interrupt, Fault, dan Abort
Bedakan secara teknis keempat mekanisme transfer kendali hardware-ke-kernel berikut:
1. *Software Interrupt / Trap* (contoh: eksekusi instruksi `syscall` / `int 0x80`)
2. *Hardware Interrupt* (contoh: sinyal IRQ dari NIC atau disk controller)
3. *Fault* (contoh: Page Fault `#PF`)
4. *Abort* (contoh: Machine Check Exception `#MC`)
* **Fokus Analisis:** Bagaimana CPU membedakan *synchronous* vs *asynchronous events*, bagaimana instruksi yang sedang dieksekusi ditangani (diulang, dilewati, atau dimatikan secara instan), dan bagaimana mekanisme perpindahan *privilege level* (Ring 3 ke Ring 0) terjadi di tingkat *Interrupt Descriptor Table* (IDT)?

### Soal 1.4: CPU Reordering, Memory Barriers, dan Cache Coherency
Mengapa proteksi variabel bersama (*shared variable*) menggunakan *flag* boolean sederhana tanpa primitif sinkronisasi kernel/hardware gagal total pada CPU modern multi-core?
* Jelaskan interaksi antara *Out-of-Order Execution* (OoO), *Store Buffers*, *Invalidate Queues*, dan protokol koherensi *cache* (seperti MESI).
* Kapan rekayasawan sistem wajib menyisipkan *Memory Barrier/Fence* (Read/Write/Full Fence), dan apa implikasinya terhadap *pipeline flush* prosesor?

### Soal 1.5: Overhead Sistem Panggilan (System Call) vs Pemanggilan Fungsi Biasa
Bandingkan secara komparatif eksekusi fungsi pengguna `my_function()` dengan panggilan sistem `read(fd, buf, count)`.
* Uraikan langkah-langkah yang dieksekusi prosesor: manipulasi *call stack*, penyimpanan register pengguna, modifikasi *Model-Specific Registers* (MSR seperti `IA32_SYSENTER_CS` atau `IA32_LSTAR`), transisi *page table* kernel (*Kernel Page Table Isolation* / KPTI), hingga *return-from-system-call* (`sysret` / `sysexit`). Mengapa mitigasi kerentanan spekulatif (Meltdown/Spectre) memperbesar penalti latensi ini secara drastis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Copy-on-Write (CoW) Degradation dan Redis BGSAVE OOM
Sebuah instans Redis dengan konsumsi memori 48 GiB berjalan pada server dengan total RAM 64 GiB tanpa *swap*. Ketika Redis mengeksekusi perintah `BGSAVE`, proses induk memanggil `fork()` untuk membuat proses anak (*child process*) yang menulis *dump* RDB ke disk.
* Jelaskan bagaimana kernel Linux memanipulasi *Page Table Entries* (PTE) untuk memetakan halaman memori yang sama ke proses induk dan anak dengan atribut *read-only*.
* Jika aplikasi klien melakukan mutasi data (*write*) intensif sebesar 35% dari total kunci selama proses `BGSAVE` berlangsung, mengapa sistem memicu Linux OOM (*Out-of-Memory*) Killer dan mematikan proses induk, meskipun ruang alamat virtual kedua proses terlihat identik saat `fork()` pertama kali terjadi?

### Soal 2.2: Mekanisme Futex (Fast Userspace Mutex) dan Analisis Spurious Wakeups
Primitif konkurensi modern seperti `pthread_mutex` tidak langsung memanggil *syscall* ke kernel saat akuisisi *lock*.
* Jelaskan alur eksekusi *hybrid* dari Linux `futex`: kondisi apa yang memungkinkan penguncian selesai 100% di *user space* via instruksi atomik (misalnya `CMPXCHG`), dan pada kondisi apa *thread* harus memanggil `sys_futex(FUTEX_WAIT)`?
* Apa penyebab utama terjadinya *spurious wakeup* pada *condition variable*, dan mengapa kode produksi diwajibkan memeriksa status predikat dalam *loop* (`while (!condition)`) alih-alih percabangan tunggal (`if (!condition)`) di tingkat instruksi kernel?

### Soal 2.3: Completely Fair Scheduler (CFS) dan Fenomena CPU Throttling pada Container
Pada subsistem kernel Linux CFS:
* Bagaimana variabel `vruntime` (virtual runtime) dihitung berdasarkan prioritas `nice` proses, dan bagaimana CFS menggunakan struktur data Red-Black Tree (`rb_node`) untuk memilih *thread* berikutnya yang akan dieksekusi?
* Dalam lingkungan kontainer (Docker/Kubernetes) dengan alokasi `cpu.cfs_quota_us = 20000` dan `cpu.cfs_period_us = 100000` (ekivalen dengan 0.2 CPU Core), jelaskan bagaimana *multi-threaded application* (misal: 8 threads aktif) dapat mengalami *CPU throttling* parah di 15 milidetik pertama dari suatu periode, mengakibatkan latensi tinggi tak terduga (*tail latency spike*), padahal utilisasi CPU rata-rata per detik berada di bawah 20%.

### Soal 2.4: TLB Shootdown Storm pada Sistem Multi-Socket NUMA
Pada server multi-socket (misal: 4 socket NUMA, 128 core total), sebuah aplikasi *database in-memory* multi-threaded sering kali melakukan dealokasi memori besar secara paralel (`free()` / `munmap()`).
* Jelaskan fenomena *TLB Shootdown*. Bagaimana inisiasi pembatalan validitas *page* di satu core memaksa pengiriman *Inter-Processor Interrupts* (IPI) ke 127 core lainnya?
* Mengapa lonjakan IPI ini menyebabkan degradasi sistemik (*spinning* pada *lock* kernel, penurunan dramatis pada *Instructions Per Cycle* / IPC), dan langkah arsitektural apa yang dapat diambil untuk meminimalkannya (misal: *huge pages*, alokasi memori berbasis *thread-local arena*)?

### Soal 2.5: Zombie vs Orphan Process, File Descriptor Leak, dan Init/Systemd Reaping
Jelaskan patologi status siklus hidup proses berikut:
* Apa perbedaan struktural di dalam kernel Linux antara *Zombie Process* (status `Z` di `ps`) dan *Orphan Process*? Mengapa *zombie process* tidak mengonsumsi RAM atau CPU, namun jika jumlahnya tidak terkendali dapat melumpuhkan sistem secara fatal?
* Jika sebuah *parent process* mati mendadak sebelum membaca *exit status* dari *child process* melalui `waitpid()`, jelaskan proses *re-parenting* yang dilakukan oleh kernel ke PID 1 (`systemd`/`init`). Apa yang terjadi jika implementasi PID 1 kustom di dalam Docker container tidak mengimplementasikan penanganan sinyal `SIGCHLD`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Context Switching Storm & Thread Starvation
Sebuah layanan microservice berbasis Java (Spring Boot) yang menangani transaksi pembayaran mengalami degradasi total saat *flash sale*. Utilisasi CPU melonjak hingga 100%, namun *throughput* turun dari 12.000 RPS menjadi 150 RPS, dengan *p99 latency* melonjak dari 15ms ke 12.000ms. 

Inspeksi telemetri tingkat rendah menunjukkan data berikut:
* CPU US (User): 12%
* CPU SY (System/Kernel): 86%
* Context Switches per second: > 2.800.000 / detik (Normal: ~25.000 / detik)
* Active OS Threads: 4.500 threads (Thread pool tomcat dikonfigurasi `max-threads=5000`)
* Downstream Dependency: Database PostgreSQL mengalami perlambatan *query*, menaikkan waktu respons DB dari 2ms ke 400ms.

#### Pertanyaan Diagnostik:
1. Analisis hubungan kausalitas teknis antara latensi downstream database dengan lonjakan persentase `CPU SY` dan laju *context switch*. Apa yang sedang dilakukan oleh kernel Linux pada 86% siklus CPU tersebut?
2. Bagaimana fenomena *thread-per-request model* memicu *cache thrashing* pada level CPU L1 Data/Instruction Cache dalam kondisi ini?
3. Rancang rencana mitigasi arsitektur jangka pendek (*hotfix config*) dan jangka panjang (*re-architecture*) untuk mengisolasi sistem dari kegagalan berantai ini tanpa menambah kapasitas mesin.

---

### Skenario B: Priority Inversion & Deadlock pada Thread Pool Paralel
Sistem kendali industri embedded berbasis Linux Real-Time (PREEMPT_RT) mengelola sistem telemetri sensor dengan tiga tingkatan *thread*:
* **Thread High (H):** Membaca aktuator kritis tiap 5ms (Prioritas Real-Time FIFO 90).
* **Thread Medium (M):** Melakukan komputasi kompresi log ke penyimpanan lokal (Prioritas Normal / SCHED_OTHER, nice 0).
* **Thread Low (L):** Mengambil data telemetri suhu via I2C bus (Prioritas Real-Time FIFO 20).

Thread **H** dan Thread **L** berbagi struktur data *in-memory buffer* yang diproteksi oleh *POSIX Mutex* non-robust konvensional (`pthread_mutex_t`). 
Pada kondisi beban tinggi, Thread **H** mengalami *deadline miss* selama 300ms, memicu sistem *fail-safe shutdown*. Investigasi menunjukkan Thread **L** sempat mengakuisisi *mutex*, namun sebelum selesai melepaskannya, Thread **M** dieksekusi secara masif oleh *scheduler*.

```
Thread H:        [Menunggu Mutex...]-----------------------------> [Deadline Miss!]
Thread M:                [Mengeksekusi Loop Kompresi CPU-Bound.....]
Thread L:  [Lock Mutex]--[Tergusur oleh M...]
```

#### Pertanyaan Diagnostik:
1. Jelaskan bagaimana Thread **M** yang memiliki prioritas lebih rendah dari Thread **H** dapat secara tidak langsung memblokir eksekusi Thread **H** (*Unbounded Priority Inversion*).
2. Mengapa algoritma penjadwalan bawaan (*default priority scheduler*) gagal mencegah situasi ini?
3. Tunjukkan solusi teknis konkret untuk mengeliminasi masalah ini pada level OS primitive: Jelaskan perbedaan mekanisme kerja antara **Priority Inheritance Protocol** (PIP) dan **Priority Ceiling Protocol** (PCP). Parameter konfigurasi mutex apa yang harus diaktifkan pada implementasi POSIX?

---

### Skenario C: Trade-off Arsitektur I/O: Event-Driven (epoll) vs Zero-Copy (splice/sendfile)
Sebuah tim arsitektur sedang merancang ulang *edge-proxy* streaming video berskala multi-terabit per detik. Server bertugas membaca segmen berkas video dari *NVMe arrays* lokal dan mengirimkannya ke ratusan ribu koneksi klien TCP secara bersamaan.

Dua arsitektur diusulkan:
* **Arsitektur 1 (Worker-Event Loop):** Menggunakan Linux `epoll` non-blocking dengan *user-space ring buffer*. Alur: `pread()` memindahkan data dari *Page Cache* ke *Buffer Pengguna*, lalu `pwrite()` / `send()` memindahkan data dari *Buffer Pengguna* ke *Socket Buffer*.
* **Arsitektur 2 (Kernel Zero-Copy Pipeline):** Menggunakan `epoll` untuk sinyal kesiapan soket, namun transfer data aktual menggunakan panggilan sistem `sendfile()` atau `splice()` yang mengalirkan data langsung antar-*file descriptor* via kernel *pipe buffers*.

```
Arsitektur 1 (Standard):
[Disk] -> (DMA) -> [Page Cache] -> (CPU Copy) -> [User Space Buffer] -> (CPU Copy) -> [Socket Buffer] -> (DMA) -> [NIC]

Arsitektur 2 (Zero-Copy):
[Disk] -> (DMA) -> [Page Cache] ----------------------------------------------------> [Socket Buffer] -> (DMA) -> [NIC]
                                 \--(Kernel Reference Pointer)--/
```

#### Pertanyaan Diagnostik:
1. Hitung dan bandingkan jumlah *Context Switches* dan operasi *Memory Copy* (baik via CPU maupun DMA) per transaksi I/O antara Arsitektur 1 dan Arsitektur 2.
2. Jika sistem membutuhkan enkripsi data dinamis (*TLS/HTTPS* dengan algoritma ChaCha20-Poly1305) sebelum data dikirimkan ke soket, apakah Arsitektur 2 masih dapat digunakan secara murni? Jelaskan batasan fundamental kernel zero-copy ketika transformasi payload data diperlukan di tingkat *user space*.
3. Bagaimana subsistem Linux terbaru, **io_uring**, memadukan keunggulan kedua pendekatan di atas untuk mencapai performa I/O tinggi tanpa *system call context switch overhead*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Engine Task Scheduler Preemptive Berskala Mikro (User-Level Threading / Fiber Engine)

#### Problem Statement
Dalam komputasi performa tinggi, ketergantungan pada *kernel-level threads* (`pthread`) untuk jutaan konkurensi memicu *memory footprint* masif (alokasi *guard page* dan *stack* minimal puluhan KiB hingga MiB per utas) serta *overhead context switch* di Ring 0. Anda ditugaskan membangun sebuah **User-Level Preemptive Task Scheduler (Green Thread / Fiber Library)** minimalis pada lingkungan Linux x86-64 menggunakan bahasa C (atau C++ / Rust tanpa runtime bawaan).

#### Requirements
1. **Context Switching Engine:**
   * Implementasikan fungsi alih-konteks manual dalam bahasa Assembly x86-64 (`fiber_switch(from_context, to_context)`).
   * Fungsi wajib menyimpan dan memulihkan secara presisi:
     * Register *Callee-Saved*: `%rbx`, `%rsp`, `%rbp`, `%r12`, `%r13`, `%r14`, `%r15`.
     * Register kontrol floating-point / SIMD (*MXCSR* dan *x87 control word* via instruksi `fnstcw`/`stmxcsr`).
2. **Stack Allocation & Guard Page:**
   * Setiap *fiber* dialokasikan memori dinamis sebesar 64 KiB via `mmap()` dengan flag `MAP_ANONYMOUS | MAP_PRIVATE`.
   * Halaman terbawah (*bottom page* 4 KiB) dari setiap *stack* fiber harus diproteksi dengan `mprotect(..., PROT_NONE)` sebagai *Guard Page* untuk mendeteksi *Stack Overflow* seketika (menghasilkan sinyal `SIGSEGV` terkendali).
3. **Preemption Mechanism (Preemptive Time-Slicing):**
   * Manfaatkan POSIX Interval Timer (`setitimer` dengan interval 10ms) yang mengirimkan sinyal `SIGALRM` ke proses.
   * Daftarkan *signal handler* kustom (`sigaction` dengan flag `SA_SIGINFO`) yang memanipulasi *signal context* (`ucontext_t` / `mcontext_t`) untuk memaksa *fiber* yang sedang berjalan melepaskan CPU (*yield*) dan kembali ke penjadwal utama (*Scheduler loop*).
4. **Scheduler Data Structure:**
   * Implementasikan antrean tugas berbasis *Round-Robin Queue* yang menyimpan *Task Control Block* (TCB).
   * Status Fiber: `READY`, `RUNNING`, `TERMINATED`.
   * Penanganan terminasi: Jika sebuah fiber menyelesaikan eksekusi fungsi utamanya, alokasi memori stack-nya harus dibersihkan secara aman tanpa memicu *segmentation fault* pada eksekusi fiber berikutnya.

#### Constraints
* Dilarang menggunakan pustaka `ucontext.h` bawaan POSIX (`getcontext`, `makecontext`, `swapcontext`) untuk proses *switching* utama, Anda wajib menulis logika *assembly* sendiri.
* Dilarang menggunakan alokasi memori berbasis heap standar (`malloc`/`free`) di dalam *signal handler* (wajib mematuhi kaidah *Async-Signal-Safe*).
* Sistem harus dapat mengeksekusi minimal **10.000 concurrent fibers** secara bergantian dan mencetak eksekusi log tanpa mengalami *stack corruption* atau *memory leak*.

#### Expected Output
Program demonstrasi yang membuktikan bahwa dua atau lebih fiber yang memuat *infinite loop* CPU-bound (`while(1)`) dapat saling berbagi CPU secara bergantian (*interleaved execution*) karena adanya interupsi *timer preemption*, dengan jejak konsol terverifikasi:

```text
[INIT] Scheduler initialized with quantum = 10ms
[SPAWN] Fiber 1 created (Stack: 0x7f9a1000, Guard: 0x7f9a0000)
[SPAWN] Fiber 2 created (Stack: 0x7f9a3000, Guard: 0x7f9a2000)
[SCHED] Starting execution...
[FIBER 1] Counter: 1000000
[KERNEL] SIGALRM Triggered! Preempting Fiber 1...
[SCHED] Switching context: Fiber 1 -> Fiber 2
[FIBER 2] Counter: 1000000
[KERNEL] SIGALRM Triggered! Preempting Fiber 2...
[SCHED] Switching context: Fiber 2 -> Fiber 1
...
[TEST PASSED] Preemption and isolation confirmed without segmentation fault.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup lengkap proses: Transisi status `TASK_RUNNING`, `TASK_INTERRUPTIBLE`, `TASK_UNINTERRUPTIBLE`, `TASK_STOPPED`, dan `EXIT_ZOMBIE`.
- [ ] Perbedaan fundamental antara *Hardware Exception* (synchronous) dan *External Hardware Interrupt* (asynchronous).
- [ ] Mekanisme translasi alamat: *Virtual Address* $\rightarrow$ CR3 Register $\rightarrow$ PML4E $\rightarrow$ PDPTE $\rightarrow$ PDE $\rightarrow$ PTE $\rightarrow$ *Physical Address*.
- [ ] Peran dan biaya operasional dari *Translation Lookaside Buffer* (TLB), *TLB Hit/Miss*, serta mekanisme *TLB Invalidation* via instruksi `INVLPG`.
- [ ] Arsitektur proteksi memori CPU: Ring 0 vs Ring 3, pemisahan ruang alamat kernel/pengguna, dan mekanisme KPTI (*Kernel Page Table Isolation*).
- [ ] Semantik instruksi atomik CPU (e.g., `LOCK CMPXCHG`, `XCHG`, *Load-Linked/Store-Conditional*) dan kaitannya dengan bus locking vs cache-line locking.
- [ ] Kondisi Coffman untuk terjadinya *Deadlock* (Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait) dan metode pembatalannya.
- [ ] Model konsistensi memori (Sequential Consistency, Total Store Order/TSO, Weak Ordering) dan kebutuhan eksplisit memory fence.
- [ ] Arsitektur I/O non-blocking: Keterbatasan skalabilitas $O(N)$ dari `select`/`poll` dibandingkan skalabilitas $O(1)$ dari `epoll` (Edge-Triggered vs Level-Triggered).
- [ ] Paradigma alokasi memori Linux: Mekanisme *Overcommit*, heuristik *OOM Killer*, *Badness Score*, dan manajemen *Page Cache* vs *Anonymous Memory*.

### Saya tidak perlu menghafal:
- [ ] Struktur bitwise spesifik dari tabel deskriptor x86 (seperti format bit mentah dari *Global Descriptor Table* / GDT atau *Task State Segment* / TSS).
- [ ] Nomor pemetaan numerik (*Syscall Numbers*) unik pada tabel unistd x86_64 (misal: `sys_read` = 0, `sys_write` = 1, `sys_open` = 2). Cukup pahami mekanisme pemanggilannya via register `%rax`.
- [ ] Rumus matematika mendalam penghitungan penalti peluruhan *dynamic decay weight* internal pada kernel CFS Linux kuno.
- [ ] Sintaks mikro-spesifik API konfigurasi driver perangkat keras vendor tertentu di luar standar antarmuka POSIX.

### Saya harus bisa melakukan:
- [ ] Menggunakan utilitas diagnostik sistem tingkat rendah: `strace` untuk melacak interaksi *syscall*, `perf` untuk merekam *CPU hardware performance counters*, dan `vmstat` / `pidstat` untuk mengukur *voluntary/involuntary context switching*.
- [ ] Menganalisis *memory dump* dan *core dump* menggunakan `gdb` untuk merekonstruksi jejak panggilan (*stack trace*) multi-threaded yang mengalami *deadlock*.
- [ ] Menghitung kebutuhan ruang tabel halaman (*page table footprint*) teoritis untuk konfigurasi ukuran memori fisik dan ukuran halaman tertentu (4 KiB vs 2 MiB vs 1 GiB Huge Pages).
- [ ] Mengidentifikasi dan memperbaiki *concurrency bugs* (race conditions, data races, deadlocks, live-locks) menggunakan ThreadSanitizer (TSan) dan Valgrind (Helgrind).
- [ ] Membaca serta mengekstrak metrik kesehatan kernel secara langsung dari sistem berkas virtual `/proc` (misalnya: `/proc/[pid]/status`, `/proc/[pid]/maps`, `/proc/interrupts`, dan `/proc/meminfo`).