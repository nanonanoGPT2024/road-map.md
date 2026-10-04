# BAB 04: Quiz, Challenge, & Knowledge Check
**Manajemen Proses, Penjadwalan (Scheduling), dan Threading**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Unifikasi Proses dan Thread pada Linux Kernel**  
   Di tingkat kernel Linux, tidak ada perbedaan struktur data fundamental antara *process* konvensional dan *thread* (keduanya direpresentasikan oleh `struct task_struct`). Jelaskan bagaimana *system call* `clone()` mengabstraksikan pembuatan proses versus *thread* melalui flag emulasi POSIX Threads (pthreads) seperti `CLONE_VM`, `CLONE_FS`, `CLONE_FILES`, dan `CLONE_SIGHAND`. Apa implikasi arsitektural dari konsep *Lightweight Process* (LWP) ini terhadap alokasi memori virtual dan tabel deskriptor berkas (*file descriptor table*)?

2. **Dinamika State Proses dan Analisis State `D` (TASK_UNINTERRUPTIBLE)**  
   Uraikan siklus hidup proses di Linux dan transisi state-nya (`TASK_RUNNING`, `TASK_INTERRUPTIBLE`, `TASK_UNINTERRUPTIBLE`, `TASK_STOPPED`, `EXIT_ZOMBIE`, `EXIT_DEAD`). Mengapa proses yang berada dalam status `D` (*Uninterruptible Sleep*) kebal terhadap sinyal pembunuhan paksa (`SIGKILL` / `kill -9`)? Operasi kernel sub-sistem apa yang umumnya menahan proses pada state tersebut, dan apa risikonya terhadap perhitungan *System Load Average*?

3. **Mekanisme Copy-on-Write (COW) pada Forking**  
   Ketika proses memanggil `fork()`, kernel Linux tidak langsung menduplikasi seluruh *physical memory frame* milik *parent* ke *child*. Jelaskan secara detail bagaimana kernel memanfaatkan *Memory Management Unit* (MMU) dan *Page Table Entries* (PTE) untuk mengimplementasikan *Copy-on-Write* (COW). Kondisi apa yang memicu *Page Fault* (spesifiknya, *write fault*), dan langkah apa yang diambil kernel sebelum mengizinkan penulisan data oleh salah satu proses?

4. **Struktur Hirarki Pengelompokan: PID, TGID, PGID, dan SID**  
   Sebuah *application runtime* multi-threaded (misal: Java Virtual Machine atau Go runtime) menghasilkan puluhan unit eksekusi. Jelaskan perbedaan struktural antara Process ID (`PID`), Thread Group ID (`TGID`), Process Group ID (`PGID`), dan Session ID (`SID`) di dalam kernel Linux. Mengapa perintah `ps` standar menampilkan ID yang identik untuk seluruh thread dalam satu proses, sedangkan direktori `/proc/[pid]/task/` menampilkan ID yang berbeda?

5. **Siklus Hidup Terminasi: Zombie vs Orphan Process dan Peran Subreaper**  
   Jelaskan perbedaan mendasar antara *Zombie Process* (`EXIT_ZOMBIE`) dan *Orphan Process*. Sumber daya sistem apa yang masih tertahan oleh sebuah proses *zombie* di kernel, dan mengapa penumpukan proses *zombie* dapat melumpuhkan sistem operasi meskipun CPU dan RAM berstatus idle? Bagaimana mekanisme *adoption* oleh PID 1 (`systemd`/`init`) atau *Process Subreaper* (`PR_SET_CHILD_SUBREAPER`) bekerja untuk menyelesaikan masalah ini?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Algoritma Penjadwalan: Dari CFS ke EEVDF**  
   Completely Fair Scheduler (CFS) menggunakan metrik `vruntime` (virtual runtime) yang dilacak menggunakan *Red-Black Tree*, sedangkan Linux Kernel modern beralih ke EEVDF (*Earliest Eligible Virtual Deadline First*). Jelaskan bagaimana `vruntime` dihitung secara matematis berdasarkan *Nice Value* (faktor bobot latensi), dan bagaimana algoritma EEVDF mengatasi kelemahan CFS dalam menangani proses *latency-sensitive* tanpa mengorbankan *throughput-oriented processes*.

2. **Preemption Models dan Dampak Latensi Eksekusi**  
   Linux Kernel mendukung beberapa tingkatan *kernel preemption* yang dapat dikompilasi (`CONFIG_PREEMPT_NONE`, `CONFIG_PREEMPT_VOLUNTARY`, `CONFIG_PREEMPT`, dan `CONFIG_PREEMPT_RT`). Jelaskan apa yang terjadi saat *timer interrupt* terpicu ketika sebuah *thread* pengguna sedang menjalankan fungsi di dalam *kernel space* (misalnya sedang mengeksekusi *system call* yang lambat) pada masing-masing model tersebut. Apa trade-off antara *context-switching overhead* dan *worst-case scheduling latency*?

3. **Processor Affinity, NUMA Topology, dan Cache Thrashing**  
   Pada arsitektur Non-Uniform Memory Access (NUMA) modern, pemindahan (*migration*) *thread* dari satu CPU core ke core lain dapat menimbulkan degradasi performa yang masif. Jelaskan bagaimana fungsi `sched_setaffinity()` dan parameter isolasi kernel (`isolcpus`, *cgroup cpuset*) dapat mencegah masalah *Cache Invalidation* (L1/L2/L3 cache misses) dan *Remote Memory Access latency*. Bagaimana *scheduler domains* di Linux bekerja dalam menyeimbangkan beban antar-NUMA node?

4. **Sinkronisasi Antar-Proses: Futex (Fast Userspace Mutex)**  
   Mekanisme penguncian (*locking*) berbasis *system call* murni (seperti manipulasi semaphore via kernel space) sangat lambat karena *overhead context switch*. Jelaskan mekanisme arsitektur `futex` (*Fast Userspace Mutex*) yang digunakan oleh glibc/Linux. Bagaimana `futex` mengeksekusi operasi penguncian saat *uncontended state* (tanpa campur tangan kernel) versus saat *contended state* (mengalihkan eksekusi ke antrean tidur di kernel space via `sys_futex`)?

5. **Analisis Throttling pada cgroups v2 (CPU Controller)**  
   Dalam containerization (misal: Docker, Kubernetes), alokasi CPU diatur melalui `cgroups v2` menggunakan file konfigurasi `cpu.max` (terdiri dari nilai *quota* dan *period*, misal: `200000 100000` untuk 2 CPU). Jelaskan bagaimana CFS memberlakukan *hard enforcement* terhadap kuota ini. Jika sebuah *multithreaded process* melampaui kuotanya di awal *period window*, apa yang terjadi pada *threads* tersebut di sisa durasi *period*? Bagaimana cara mendeteksi metrik *throttling* ini melalui `/sys/fs/cgroup/` atau `/proc/[pid]/schedstat`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Lonjakan Load Average Ekstrem dengan CPU Utilization Rendah
* **Konteks:**  
  Sebuah cluster server database Linux 64-core mengalami anomali performa kritis. Metrik monitoring menunjukkan *System Load Average* melonjak hingga **320.00**, namun utilisasi total CPU (`%usr` + `%sys`) berada di bawah **15%**. Ratusan proses aplikasi berada dalam status `D`. I/O throughput lokal NVMe terdeteksi normal, tetapi aplikasi mengalami *high latency* hingga *connection timeout*.
* **Pertanyaan Diagnostik:**  
  1. Langkah inspeksi sistem apa yang harus diambil untuk mengidentifikasi fungsi kernel spesifik di mana proses-proses tersebut tertahan (sebutkan file/alat di `/proc` atau *tracing tools* yang relevan)?
  2. Jika anomali ini disebabkan oleh kebuntuan akses storage terdistribusi (misalnya NFS mount hang) atau kegagalan *kernel lock acquisition* (misalnya *inode mutex lock contention*), bagaimana cara membuktikannya secara kausatif tanpa me-reboot mesin?
  3. Mengapa eksekusi `kill -9` pada PID-PID tersebut tidak berhasil mengurangi angka *load average*?

### Skenario B: Race Condition Sporadis dan Thread Starvation pada Layanan Finansial
* **Konteks:**  
  Sebuah microservice trading multi-threaded yang dibangun dengan C++ menggunakan *POSIX threads* (pthreads) dan *thread-pool* manual mengalami insiden *memory corruption* dan ketidaksesuaian saldo pada akun secara acak hanya ketika beban transaksi mencapai *peak* (> 50.000 req/sec). Pada beban normal, sistem lolos uji regresi otomatis. Profiling awal mendeteksi adanya penggunaan primitive mutex yang tidak merata yang menyebabkan beberapa thread penting mengalami kondisi *starvation*.
* **Pertanyaan Diagnostik:**  
  1. Bagaimana Anda membuktikan terjadinya *race condition* atau *data race* di tingkat thread dengan memanfaatkan *compiler instrumentation* (misal: ThreadSanitizer) dan dynamic kernel tracing (`perf` atau `bpftrace`)?
  2. Jelaskan fenomena *Priority Inversion* yang mungkin terjadi jika thread dengan prioritas normal menahan *mutex* yang dibutuhkan oleh thread berprioritas tinggi (*real-time FIFO/RR scheduling*). Mekanisme kernel/POSIX apa yang harus diaktifkan pada atribut mutex (`pthread_mutexattr_setprotocol`) untuk mengatasi masalah ini?
  3. Bagaimana arsitektur *lock-free* berbasis atomic CAS (*Compare-And-Swap*) atau CPU core pinning mengurangi kemungkinan bottleneck sinkronisasi tersebut?

### Skenario C: Arsitektur Multi-Process vs Multi-Threaded pada Edge Proxy Berkecepatan Tinggi
* **Konteks:**  
  Tim infrastruktur Anda sedang mendesain arsitektur *L7 Reverse Proxy* internal generasi terbaru yang harus memproses ratusan ribu koneksi TCP konkuren dengan kebutuhan latensi P99 di bawah 2 milidetik. Tim terbagi menjadi dua kubu:
  * *Kubu A:* Mengusulkan model **Multi-Process Event-Driven** (mirip arsitektur Master-Worker Nginx/PostgreSQL) untuk isolasi kegagalan dan eksploitasi memori yang aman.
  * *Kubu B:* Mengusulkan model **Multi-Threaded Shared-Memory** (mirip arsitektur Envoy/Java Netty) untuk efisiensi *memory footprint* dan kemudahan pertukaran data antar-koneksi.
* **Pertanyaan Diagnostik:**  
  1. Bedah trade-off arsitektural kedua pendekatan ini ditinjau dari:
     - Beban *context-switching* (TLB flushing / *Translation Lookaside Buffer invalidation*).
     - *Blast radius* jika terjadi *segmentation fault* (`SIGSEGV`).
     - Kompleksitas *Inter-Process Communication* (IPC) versus sinkronisasi akses memori *in-process*.
  2. Jika model Multi-Process dipilih, bagaimana Anda mengatasi masalah *Thundering Herd Problem* saat ratusan proses worker mendengarkan (*listen*) pada port jaringan yang sama sebelum dan sesudah adanya flag socket kernel `SO_REUSEPORT` dan flag `EPOLLEXCLUSIVE`?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Process Sentinel & Dynamic CPU Throttler CLI (`task-sentinel`)

#### Problem Statement
Di lingkungan produksi berbasis micro-instance, proses komputasi latar belakang (*worker processes*) sering kali mengalami kebocoran *thread* (*thread leak*) atau berubah menjadi *runaway process* yang memonopoli CPU, sehingga mengganggu proses kritis lainnya (*noisy neighbor syndrome*). Anda diminta membangun utilitas CLI bare-metal tingkat rendah bernama `task-sentinel` (menggunakan C, Rust, Go, atau Bash murni + Linux Virtual File Systems) yang bertindak sebagai supervisor proses eksternal tanpa bergantung pada dependensi orkestrator seperti Docker atau systemd.

#### Requirements
1. **Process Supervision & Lifecycle Tracking:**  
   Program harus mengeksekusi sub-proses target (misal: stress test CPU), bertindak sebagai *subreaper*, melacak PID dan seluruh TGID/TID (threads) yang dihasilkan oleh proses anak melalui pembacaan `/proc/[pid]/task/`. Program harus menangani sinyal POSIX (`SIGCHLD`, `SIGTERM`, `SIGINT`) secara anggun (*graceful teardown*) dan memanen seluruh anak untuk memastikan tidak ada *zombie process* yang tersisa.
2. **Automated Dynamic CPU Quota Enforcement via cgroups v2:**  
   - Skrip/program harus mendeteksi mount point `cgroups v2` (`/sys/fs/cgroup`).
   - Program membuat sub-cgroup khusus untuk proses target: `/sys/fs/cgroup/task_sentinel_<PID>`.
   - Program memindahkan target PID ke dalam cgroup tersebut (`cgroup.procs`).
   - Menerapkan batasan kuota CPU dinamis melalui `cpu.max` (misalnya membatasi proses maksimal hanya boleh menggunakan 50% dari 1 CPU Core: `50000 100000`).
3. **Telemetry & Real-Time Kernel Stat Metrics:**  
   Setiap interval 2 detik, program harus membaca dan menampilkan metrik performa kernel dari `/proc/[pid]/stat`, `/proc/[pid]/schedstat`, dan `/sys/fs/cgroup/task_sentinel_<PID>/cpu.stat`:
   - Jumlah thread aktif (`num_threads`).
   - Metrik CPU Throttling (`nr_throttled`, `throttled_usec`).
   - *Voluntary* vs *Involuntary Context Switches* dari `/proc/[pid]/status`.
4. **Runaway Mitigation Trigger:**  
   Jika *involuntary context switch* melonjak melampaui ambang batas tertentu atau metrik *throttled_usec* bertambah secara agresif selama 3 interval berturut-turut, utilitas harus mengirimkan sinyal `SIGSTOP` untuk membekukan proses sementara, mencatat diagnostik jejak stack kernel (`/proc/[pid]/stack`), lalu mengirimkan sinyal `SIGCONT` untuk melanjutkannya, atau `SIGKILL` jika proses tidak merespons perintah terminasi dalam 10 detik.

#### Constraints
- Dilarang keras menggunakan *wrapper runtime* container (Docker, Podman, Containerd).
- Manipulasi proses dan cgroups harus dilakukan secara direct interaction terhadap Linux Virtual Filesystem (`/proc` dan `/sys/fs/cgroup`) serta *POSIX System Calls*.
- Harus kompatibel dengan sistem Linux berarsitektur x86_64 atau ARM64 dengan cgroups v2 terpasang.

#### Expected Output
Terminal log terstruktur (stdout/JSON) yang menampilkan siklus hidup proses secara detail:
```text
[INIT] Subreaper active. Spawning target process: ./cpu_burner --threads=4
[CGROUP] Created /sys/fs/cgroup/task_sentinel_18492
[CGROUP] Assigned PID 18492 to cgroup.procs
[CGROUP] Enforcing cpu.max = 50000 100000 (Limit: 50% single-core)
--------------------------------------------------------------------------
TIMESTAMP            THREADS   VOL_CS    INVOL_CS   THROTTLED_TIME(us)   STATE
2026-03-30T10:00:02  4         120       1450       45021                R (Running)
2026-03-30T10:00:04  4         135       3200       98340                R (Running)
--------------------------------------------------------------------------
[ALERT] Heavy CPU throttling detected on PID 18492! Dumping kernel call stack:
[STACK] [<0>] cfs_rq_throttle+0x14a/0x210
[STACK] [<0>] put_prev_task_fair+0x1e/0x40
[STACK] [<0>] __schedule+0x312/0xa60
[SIGNAL] Gracefully terminating target PID 18492 (SIGTERM sent)...
[REAP] Child process 18492 exited with code 0. Zombie prevention successful.
[CLEANUP] Removed /sys/fs/cgroup/task_sentinel_18492. Sentinel exiting cleanly.
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis dan kedalaman pemahaman Anda sebelum melangkah ke topik sistem operasi dan arsitektur kernel berikutnya.

### Saya harus memahami:
- [ ] Anatomi `struct task_struct` dan representasi proses serta thread di Linux kernel.
- [ ] Peran dan cara kerja system call famili `clone()`, `fork()`, `vfork()`, dan `execve()`.
- [ ] Mekanisme Copy-on-Write (COW) pada level MMU, Page Table, dan Kernel Page Fault Handler.
- [ ] Enam status dasar siklus hidup proses di Linux, dengan perhatian mendalam pada `TASK_UNINTERRUPTIBLE` (`D`) dan `EXIT_ZOMBIE` (`Z`).
- [ ] Perbedaan fundamental antara Process ID (`PID`), Thread Group ID (`TGID`), Process Group (`PGRP`), dan Session (`SID`).
- [ ] Cara kerja penjadwal Completely Fair Scheduler (CFS) dan EEVDF, termasuk konsep `vruntime`, bobot latensi (*nice levels*), dan pemilihan tugas berbasis *Red-Black Tree*.
- [ ] Konsep *Preemption* pada kernel Linux (`PREEMPT_NONE`, `PREEMPT_VOLUNTARY`, `PREEMPT_FULL`) dan dampaknya pada *throughput* vs *scheduling jitter*.
- [ ] Arsitektur sinkronisasi *userspace-to-kernel*: primitives mutex, spinlock, read-write lock, dan implementasi internal `sys_futex`.
- [ ] Dampak hierarki memori NUMA terhadap eksekusi multi-threading, CPU affinity, dan penanganan *false sharing* pada *CPU cache line*.
- [ ] Arsitektur pengontrol sumber daya `cgroups v2` (khususnya subsistem `cpu.max`, `cpu.weight`, dan `cpu.stat`).

### Saya tidak perlu menghafal:
- [ ] Kode numerik heksadesimal atau konstanta biner internal kernel flag dari `clone()` (cukup memahami fungsi spesifiknya seperti `CLONE_VM`, `CLONE_FILES`, dsb.).
- [ ] Tabel lookup konversi matematis 40-level *nice value* ke bobot CFS scheduler (`sched_prio_to_weight[]`) secara presisi angka per angka.
- [ ] Seluruh nomor syscall arsitektur x86_64/ARM64 untuk operasi proses (cukup mengetahui fungsi abstraksinya di glibc/kernel documentation).
- [ ] Implementasi internal kode C assembly low-level dari instruksi context switch (`__switch_to`).

### Saya harus bisa melakukan:
- [ ] Menemukan dan mendiagnosis proses dalam status `D` (Uninterruptible Sleep) menggunakan `cat /proc/[pid]/stack`, `wchan`, atau `sysrq-trigger`.
- [ ] Mengidentifikasi, melacak silsilah proses (*process tree*), dan mengeliminasi akar penyebab proses *zombie* tanpa me-reboot mesin produksi.
- [ ] Mengonfigurasi dan mengunci proses atau thread pada CPU core tertentu menggunakan CLI `taskset`, `numactl`, atau memanggil C API `sched_setaffinity()`.
- [ ] Membaca, menganalisis, dan mengekstrak metrik *scheduling latency* serta *context switch* dari `/proc/[pid]/status` dan `/proc/[pid]/schedstat`.
- [ ] Menggunakan `strace` untuk melacak sinyal, IPC, dan lifecycle system call proses secara mendalam (`-f` untuk mengikuti child threads/processes).
- [ ] Mengonfigurasi batasan kuota CPU hard-limit dan soft-weight secara manual via direct filesystem manipulation di `/sys/fs/cgroup/` (cgroups v2).
- [ ] Memanfaatkan dynamic tracing tools (`perf top`, `perf record`, atau skrip `bpftrace`/`eBPF`) untuk menemukan bottleneck contention lock kernel dan preemptive stalls.