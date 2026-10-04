# MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Linux

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup eksekusi instruksi antara User Space (Ring 3) dan Kernel Space (Ring 0), mencakup mekanika switching context, interupsi hardware, dan *system call dispatcher*.
- **Membedah** arsitektur *Virtual Memory System* Linux: translasi Multi-Level Page Tables, *Translation Lookaside Buffer* (TLB), penanganan *Page Faults* (*Major* vs *Minor*), Page Cache, serta mitigasi degradasi performa akibat *Out-Of-Memory* (OOM) Killer.
- **Mengonfigurasi dan Menyesuaikan** penjadwalan CPU (*Completely Fair Scheduler* / *EEVDF*) dan isolasi sumber daya modern berbasis **cgroups v2** serta Linux *Namespaces* untuk beban kerja kontainer skala enterprise.
- **Mengoptimalkan** subsistem Virtual Filesystem (VFS) dan Block I/O Layer untuk aplikasi *high-throughput* dan *low-latency* menggunakan kombinasi *Direct I/O*, *Page Cache dirty writeback tuning*, dan pemilihan I/O Scheduler yang presisi.
- **Mendiagnosis** anomali performa subsistem kernel (*I/O stalls*, *memory fragmentation*, *CFS throttling*, *NUMA imbalance*) menggunakan utilitas observabilitas mutakhir seperti `perf`, `bpftrace`, dan analisis langsung pada antarmuka `/proc` dan `/sys`.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Konsep dasar administrasi sistem Linux: manajemen berkas, proses, sinyal POSIX (`SIGTERM`, `SIGKILL`, `SIGSEGV`), dan hak akses berkas UNIX.
- Dasar arsitektur komputer: Register prosesor (RIP, RSP, RAX), struktur memori (Stack, Heap), Cache Hirarki CPU (L1/L2/L3), dan konsep *Interrupt Request* (IRQ).
- Kemampuan membaca dan menulis sintaks dasar C atau bahasa sistem modern (Go/Rust), serta kemampuan eksekusi shell script Bash tingkat menengah.

---

## 3. Concept & Internal Architecture

Arsitektur Linux modern dirancang di atas prinsip *monolithic kernel* termodulasi dengan proteksi perangkat keras berbasis arsitektur prosesor x86_64 atau ARM64. 

```
+-----------------------------------------------------------------------+
| USER SPACE (Ring 3)                                                   |
| +-------------------------+       +---------------------------------+ |
| | User Applications       |       | Standard C Library (glibc/musl) | |
| | (Go, Java, Rust, Nginx) | ----> | syscall wrappers (read, write)  | |
| +-------------------------+       +---------------------------------+ |
+------------------------------------|----------------------------------+
                                     | SYSCALL Instruction (MSR 0xC0000082)
                                     v
+-----------------------------------------------------------------------+
| KERNEL SPACE (Ring 0)                                                 |
| +-------------------------------------------------------------------+ |
| | System Call Dispatcher (entry_SYSCALL_64 / sys_call_table)        | |
| +-------------------------------------------------------------------+ |
|         |                     |                     |                 |
|         v                     v                     v                 |
| +-----------------+ +-------------------+ +-------------------------+ |
| | Process & Task  | | Memory Management | | Virtual File System     | |
| | Scheduler       | | Subsystem (MM)    | | (VFS)                   | |
| | - EEVDF / CFS   | | - Paging & TLB    | | - dentry, inode, file   | |
| | - task_struct   | | - Page Cache      | | - Page Writeback Engine | |
| | - cgroups v2    | | - Buddy Alloc/SLUB| | - Block Layer / I/O Sch | |
| +-----------------+ +-------------------+ +-------------------------+ |
|         |                     |                     |                 |
|         +---------------------+---------------------+                 |
|                               v                                       |
|                    Hardware Device Drivers                            |
+-----------------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------------+
| HARDWARE (CPU Core, MMU, TLB, DRAM, NVMe SSD, NIC)                    |
+-----------------------------------------------------------------------+
```

### 3.1. Ring 0 vs Ring 3 & Mekanika System Call
Pada arsitektur CPU x86_64, proteksi memori dipisahkan oleh *Privilege Rings*:
- **Ring 3 (User Mode):** Area eksekusi proses aplikasi. Akses langsung ke register kontrol CPU (CR0, CR3, CR4) dan port I/O dilarang oleh CPU. Jika dilanggar, CPU melempar *General Protection Fault* (`#GP`).
- **Ring 0 (Kernel Mode):** Area eksekusi kernel Linux yang memiliki otoritas mutlak terhadap instruksi hardware, manajemen tabel memori, dan register kontrol.

Transisi dari Ring 3 ke Ring 0 tidak lagi menggunakan interrupt lambat `int 0x80`, melainkan instruksi CPU modern berkecepatan tinggi: **`SYSCALL`** (dan **`SYSRET`** untuk kembali). Alur transisi mencakup:
1. Pengisian nomor *syscall* ke dalam register `RAX`, argumen ke `RDI`, `RSI`, `RDX`, `R10`, `R8`, `R9`.
2. Eksekusi `SYSCALL`: CPU secara otomatis menyimpan `RIP` ke `RCX`, `RFLAGS` ke `R11`, dan memuat alamat eksekusi kernel dari *Model-Specific Register* (MSR `0xC0000082`, `IA32_LSTAR`) langsung ke `RIP`.
3. CPU beralih ke *Privilege Level 0*, menukar pointer stack User Space (`RSP`) dengan Kernel Stack milik proses yang sedang berjalan melalui instruksi `SWAPGS`.
4. Kernel mengeksekusi handler via `sys_call_table[RAX]`.

### 3.2. Process Scheduling & Representasi Kernel: `task_struct`
Di dalam kernel Linux, tidak ada perbedaan mendasar antara *thread* dan *process*. Keduanya direpresentasikan oleh struktur data yang sama: **`struct task_struct`** (didefinisikan di `<linux/sched.h>`). Sebuah thread hanyalah *task* yang membagikan ruang alamat memori (`mm_struct`), tabel deskriptor berkas (`files_struct`), dan *signal handlers* dengan *task* induk melalui flag sistem pemanggilan `clone()` (seperti `CLONE_VM`, `CLONE_FILES`, `CLONE_SIGHAND`).

Mekanika Penjadwalan:
- **CFS (Completely Fair Scheduler) / EEVDF (Earliest Eligible Virtual Deadline First - Linux 6.6+):** Mengatur alokasi waktu CPU berbasis *virtual runtime* (`vruntime`).
- Task dengan `vruntime` terkecil dieksekusi terlebih dahulu menggunakan struktur pohon merah-hitam (*red-black tree* / `rb_node`) atau *augmented deadline-ordered tree*.
- Nilai *nice* memetakan bobot pengali pertambahan `vruntime`: proses dengan prioritas rendah (*nice* tinggi) mengakumulasi `vruntime` lebih cepat, sehingga mendapat jatah eksekusi yang lebih singkat.

### 3.3. Arsitektur Virtual Memory Subsystem
Memori fisik tidak pernah diakses secara langsung oleh aplikasi User Space. Setiap proses memiliki ruang alamat virtual (biasanya 48-bit atau 57-bit) yang dipetakan oleh **MMU (Memory Management Unit)** melalui **4-Level Paging System** (atau 5-level jika Paging57 aktif):
- `PGD` (Page Global Directory) $\to$ `P4D` $\to$ `PUD` (Page Upper Directory) $\to$ `PMD` (Page Middle Directory) $\to$ `PTE` (Page Table Entry).
- Setiap halaman standar berukuran $4\,\text{KiB}$. Satu entri PTE menyimpan bit proteksi (Read/Write, User/Supervisor, Execute-Disable / NX bit) dan alamat fisik frame memori.
- **TLB (Translation Lookaside Buffer):** Cache perangkat keras pada CPU untuk menyimpan hasil translasi *Virtual Address* $\to$ *Physical Address*. *Context switch* antarproses berbeda ruang alamat memicu pembongkaran (invalidation) isi TLB, kecuali entri ditandai dengan flag PCID (*Process Context Identifiers*).

```
Virtual Address [48-bit Canonical]
+---------+---------+---------+---------+---------------+
| PGD Ind | PUD Ind | PMD Ind | PTE Ind | Physical Off  |
| 9 bits  | 9 bits  | 9 bits  | 9 bits  |    12 bits    |
+---------+---------+---------+---------+---------------+
     |         |         |         |            |
     v         v         v         v            |
  [CR3]      [PUD]     [PMD]     [PTE]          |
    |          |         |         |            |
    +--->PGD---+         |         |            |
          +---->PUD------+         |            |
                 +----->PMD--------+            |
                         +----->PTE Entry       |
                                   |            |
                                   v            v
                           [Physical Page Frame] + Offset ==> Real Physical RAM
```

- **Page Fault Mechanics:**
  - **Minor Page Fault:** Alamat virtual valid terdaftar di `vm_area_struct` proses, namun PTE belum diisi oleh frame fisik, atau frame sudah ada di Page Cache namun belum dipetakan. Diselesaikan murni di dalam RAM tanpa operasi disk.
  - **Major Page Fault:** Data yang dipetakan oleh memori virtual tidak berada di RAM (berada di swap partition atau file pada storage). Kernel memblokir proses (*uninterruptible sleep* / State `D`), mengeluarkan request I/O ke subsistem block storage, memuat frame ke RAM, memperbarui PTE, dan menjalankan kembali instruksi.

### 3.4. VFS (Virtual Filesystem) & Subsystem Block I/O
VFS mengabstraksikan implementasi sistem berkas heterogen (ext4, XFS, Btrfs, NFS) melalui 4 objek inti:
1. **`struct super_block`:** Merepresentasikan filesystem yang dimount (metadata global, ukuran block).
2. **`struct inode`:** Merepresentasikan objek berkas fisik unik pada disk (metadata ukuran, izin, pointer ke block data, ctime/mtime). Inode tidak menyimpan nama file.
3. **`struct dentry` (Directory Entry):** Menghubungkan nama file dalam struktur hierarki direktori ke nomor `inode` spesifik. Memiliki cache tersendiri (*dcache*).
4. **`struct file`:** Merepresentasikan berkas yang dibuka oleh suatu proses. Dibuat ketika `open()` dipanggil, menyimpan posisi *read/write offset* saat ini (`f_pos`), flag status berkas (`O_RDONLY`, `O_NONBLOCK`), dan pointer ke dentry.

Alur data berkas:
- **Buffered I/O (Default):** Penulisan (`write()`) menyalin data dari buffer aplikasi ke **Page Cache** di kernel space. Penulisan ke storage ditunda (*dirty page*). Kernel background daemon (`kworker/flush`) menulis dirty pages ke disk secara asinkron berdasarkan ambang batas `vm.dirty_background_ratio` dan `vm.dirty_ratio`.
- **Direct I/O (`O_DIRECT`):** Melewati Page Cache sepenuhnya. Data ditransfer langsung antara buffer user-space (harus sejajar dengan block/sector boundary) dan controller hardware storage via DMA (*Direct Memory Access*). Menghilangkan overhead CPU copy memory, sangat krusial untuk database enterprise (DBMS) seperti PostgreSQL dan Oracle.

---

## 4. Why & What

| Komponen / Konsep | Mengapa Dibutuhkan (Why) | Apa Sebenarnya Itu (What) |
| :--- | :--- | :--- |
| **Pemisahan Ring 0 & Ring 3** | Mencegah aplikasi user-space secara sengaja atau tidak sengaja merusak memori sistem operasi, memanipulasi hardware secara acak, atau membajak seluruh sistem. | Mekanisme isolasi berbasis privilege level prosesor yang membatasi eksekusi instruksi CPU sensitif. |
| **Virtual Memory & MMU** | Mencegah fragmentasi fisik RAM, mengisolasi memori antar proses, dan memungkinkan alokasi memori yang lebih besar dari RAM fisik (*overcommit*). | Lapisan abstraksi alamat memori buatan yang dipetakan secara dinamis ke alamat fisik oleh hardware MMU menggunakan tabel bertingkat (*Page Tables*). |
| **Page Cache & Dirty Writeback** | Disk I/O mekanik maupun solid-state jutaan kali lebih lambat dibanding RAM bus. Pembacaan berulang harus dilayani dari memori berkecepatan tinggi. | Pool alokasi memori RAM dinamis kernel untuk menyimpan salinan blok data disk, yang dikelola secara otomatis dan di-flush berkala oleh flush thread. |
| **cgroups v2** | Menghindari kondisi *Noisy Neighbor* pada server multi-tenant/kontainerisasi; mencegah satu proses menghabiskan CPU, I/O, atau RAM seluruh mesin. | Subsistem kernel terpadu (*single-hierarchy*) untuk menetapkan limitasi kuota, prioritas, dan isolasi komputasi (CPU, memory, io, pids). |

---

## 5. How: Workflow Detail

### 5.1. Alur Lengkap Eksekusi `read()` Syscall (Buffered I/O)
1. **Aplikasi User Space:** Memanggil fungsi POSIX `read(fd, buf, count)`.
2. **Pustaka Runtime (libc):** Memuat register `RAX = __NR_read`, argumen fd/buf/count ke register x86_64, mengeksekusi `SYSCALL`.
3. **Kernel Mode Transition:** CPU beralih ke Ring 0 via instruksi MSR `LSTAR`. Context user space disimpan pada kernel stack proses.
4. **VFS Layer Lookup:** Kernel membaca `current->files->fd_array[fd]` untuk mendapatkan `struct file`.
5. **Page Cache Check:** Kernel memeriksa *radix tree* / *XArray* dari `file->f_mapping` untuk melihat apakah blok data yang diminta sudah ada di Page Cache.
   - **Cache Hit:** Data disalin langsung dari kernel Page Cache ke buffer user-space (`copy_to_user()`). Kernel beralih kembali ke Ring 3 via `SYSRET`.
   - **Cache Miss:** Kernel mengalokasikan struct page kosong, menyusun `struct bio` (Block I/O Request), dan melemparkannya ke Generic Block Layer.
6. **I/O Scheduler & Device Driver:** Request digabungkan (*merged*) dan diurutkan oleh I/O Scheduler (`none`, `mq-deadline`, atau `bfq`), dikirim ke controller NVMe/SATA melalui antrean DMA.
7. **Task State Sleep:** Task diubah statusnya menjadi `TASK_UNINTERRUPTIBLE` (`D` state). Scheduler memindahkan task keluar dari CPU Runqueue; CPU menjalankan proses lain.
8. **Hardware Interrupt Handler:** Perangkat storage menyelesaikan transfer DMA ke RAM kernel, lalu memicu hardware interrupt (IRQ) ke CPU Core.
9. **Top-Half & Bottom-Half Processing:** CPU menangani hard-IRQ kilat, lalu menjadwalkan Softirq/Tasklet untuk memproses parsing bio.
10. **Task Wakeup:** Task ditandai kembali sebagai `TASK_RUNNING`, dimasukkan ke CPU Runqueue scheduler. Saat gilirannya tiba, kernel mengeksekusi `copy_to_user()`, memperbarui `file->f_pos`, dan mengeksekusi `SYSRET` kembali ke User Space.

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi Sistem Operasi
Bayangkan Linux Kernel sebagai **Manajemen Menara Perkantoran Eksekutif Tertutup**:
- **User Application (Ring 3):** Karyawan tenant di meja kerja masing-masing. Mereka tidak punya kunci ke ruang brankas, generator, atau ruang server.
- **Syscall (`SYSCALL`):** Telepon interkom resmi tenant ke resepsionis untuk meminta dokumen. Karyawan tidak boleh jalan sendiri mengambil dokumen.
- **Page Table & MMU:** Peta ilusi denah kantor. Setiap tenant merasa memiliki seluruh lantai berukuran raksasa, padahal sekat partisi fisiknya (RAM Frame) diacak dan dibagi-bagi di belakang layar.
- **Page Cache:** Meja drop-box dokumen di lobby. Dokumen yang sering dibaca ditinggalkan di meja lobby agar tidak perlu bolak-balik mengambil dari brankas bawah tanah (SSD/Disk).
- **OOM Killer:** Satpam bersenjata yang bertindak ketika gedung kehabisan oksigen (RAM habis). Satpam mengevaluasi siapa yang paling rakus memakai ruangan dan paling tidak kritis (`oom_score`), lalu mengusirnya paksa (`SIGKILL`).

### 6.2. Diagram Ekosistem Subsistem Kernel Lengkap
```
+---------------------------------------------------------------------------------+
|                                USER SPACE                                       |
|  [App Process 1]        [App Process 2]          [Container Cgroup v2]          |
|      |                        |                        |                        |
|  malloc() / read()        mmap() / write()       CPU/MEM Throttle Bounds        |
+------|------------------------|------------------------|------------------------+
       | sys_enter              | sys_enter              |
-------v------------------------v------------------------v-------------------------
|                                KERNEL SPACE                                     |
|  +---------------------------------------------------------------------------+  |
|  |                           VFS (Virtual File System)                       |  |
|  |     dentry cache (dcache)   <--->   inode table   <--->   file struct     |  |
|  +---------------------------------------------------------------------------+  |
|               |                                                |                |
|               v                                                v                |
|  +---------------------------+              +--------------------------------+  |
|  |        PAGE CACHE         |              |        ANONYMOUS MEMORY        |  |
|  |  (Dirty Page Writeback)   |              |       (Heap, Stack, BSS)       |  |
|  +---------------------------+              +--------------------------------+  |
|               |                                                |                |
|               | (I/O Flush)                                    | (Page Fault)   |
|               v                                                v                |
|  +---------------------------+              +--------------------------------+  |
|  |    BLOCK LAYER (bio)      |              |   MMU Multi-Level Page Walk    |  |
|  | - Sched: mq-deadline/none |              |   Buddy System -> SLUB Alloc   |  |
|  +---------------------------+              +--------------------------------+  |
|               |                                                |                |
+---------------|------------------------------------------------|----------------+
                v                                                v
      +--------------------+                           +-------------------+
      | NVMe / SAS Storage |                           | Physical RAM DIMM |
      +--------------------+                           +-------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Bypass libc System Call Execution (C x86_64)
Mengakses system call kernel secara manual menggunakan register tanpa wrapper standar C library untuk membuktikan transisi Ring 3 $\to$ Ring 0.

```c
/* direct_syscall.c */
#include <unistd.h>
#include <sys/syscall.h>

int main(void) {
    const char msg[] = "Executing direct Ring 0 transition via SYSCALL instruction\n";
    long bytes_written;

    /*
     * x86_64 Calling Convention for Syscalls:
     * RAX: Syscall Number (__NR_write = 1)
     * RDI: File Descriptor (1 = stdout)
     * RSI: Buffer Address (msg)
     * RDX: Length of Buffer
     */
    __asm__ volatile (
        "movq $1, %%rax\n\t"     /* __NR_write */
        "movq $1, %%rdi\n\t"     /* fd = STDOUT_FILENO */
        "movq %1, %%rsi\n\t"     /* char* buf */
        "movq %2, %%rdx\n\t"     /* size_t count */
        "syscall\n\t"            /* Invoke Ring 0 transition */
        "movq %%rax, %0\n\t"     /* Store return value */
        : "=r" (bytes_written)
        : "r" (msg), "r" ((long)sizeof(msg) - 1)
        : "%rax", "%rdi", "%rsi", "%rdx", "%rcx", "%r11", "memory"
    );

    return (bytes_written > 0) ? 0 : 1;
}
```
Kompilasi dan jalankan dengan inspeksi register kernel:
```bash
gcc -O2 direct_syscall.c -o direct_syscall
strace ./direct_syscall
```

### 7.2. Practical Example: Mengisolasi Resource Task Menggunakan Cgroups v2 Langsung via VFS
Skrip berikut mengonfigurasi batas eksekusi memori dan CPU untuk proses worker produksi secara murni menggunakan interface VFS `/sys/fs/cgroup`.

```bash
#!/usr/bin/env bash
# cgroup_v2_provision.sh
set -euo pipefail

CGROUP_PATH="/sys/fs/cgroup/prod-workload"

# Pastikan Cgroup v2 sudah terpasang
if [[ ! -f /sys/fs/cgroup/cgroup.controllers ]]; then
    echo "ERROR: Cgroup v2 tidak aktif pada host ini!" >&2
    exit 1
fi

echo "[1/4] Membuat cgroup direktori..."
sudo mkdir -p "${CGROUP_PATH}"

echo "[2/4] Mengaktifkan controller cpu dan memory..."
echo "+cpu +memory" | sudo tee /sys/fs/cgroup/cgroup.subtree_control > /dev/null

echo "[3/4] Menetapkan batas memori dan CPU limit..."
# Batas memori maksimal 512MB, swap dilarang
echo "536870912" | sudo tee "${CGROUP_PATH}/memory.max" > /dev/null
echo "0"         | sudo tee "${CGROUP_PATH}/memory.swap.max" > /dev/null

# Batasi CPU menjadi tepat 1.5 Core (150000 microsecond per 100000 microsecond periode)
echo "150000 100000" | sudo tee "${CGROUP_PATH}/cpu.max" > /dev/null

echo "[4/4] Memasukkan proses background stressor ke dalam cgroup..."
# Jalankan command uji di background
sleep 1000 &
TARGET_PID=$!

echo "${TARGET_PID}" | sudo tee "${CGROUP_PATH}/cgroup.procs" > /dev/null

echo "Proses ${TARGET_PID} berhasil diikat ke ${CGROUP_PATH}"
echo "Current CPU stats:"
cat "${CGROUP_PATH}/cpu.stat"
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1. Kasus: "The Silent 30-Second Stall" pada Node Cluster Kafka & PostgreSQL High-Throughput
- **Latar Belakang:** Kluster broker event streaming enterprise memproses $\pm 400.000$ pesan/detik pada node bertaraf bare-metal (256 GB RAM, 2x AMD EPYC 64-Core, Dual NVMe RAID-0).
- **Insiden:** Setiap interval 10 hingga 15 menit, kluster mengalami latency spike ekstrem (P99 melesat dari 3 ms menjadi 32.000 ms). Klien producer melempar error timeout socket, dan heartbeat node drop dari Apache ZooKeeper / Raft ensemble.
- **Investigasi Awal:** CPU utilization hanya 35%, RAM consumption 85%, disk health (SMART) berstatus 100% normal. Tidak ada error OOM Killer di dmesg.

### 8.2. Root Cause Analysis (RCA) via Kernel Diagnostics
Pemeriksaan metrik kernel tingkat lanjut menggunakan `sar`, `vmstat`, dan tracing bpftrace:

```bash
# 1. Mengecek indikator thread flush kernel dan vmstat
vmstat 1 30
# Hasil: Kolom 'b' (uninterruptible sleep processes) melompat dari 0 menjadi 180!
# Kolom 'wa' (I/O Wait) mencapai 70%.

# 2. Memeriksa status dirty memory di /proc/meminfo
grep -E "Dirty|Writeback" /proc/meminfo
# Hasil saat kejadian:
# Dirty:           42949672 kB (~40 GB data belum ter-flush!)
# Writeback:       12582912 kB
```

Analisis Parameter Default Linux:
- `vm.dirty_ratio = 20` (pada RAM 256GB, proses akan **diblokir total secara sinkron** jika dirty pages menyentuh $20\% \approx 51.2\,\text{GB}$).
- `vm.dirty_background_ratio = 10` (kernel baru mulai melakukan background writeback di $10\% \approx 25.6\,\text{GB}$).
- **Mekanisme Kegagalan:** Karena producer Kafka menulis dengan bandwidth gigabit secara terus-menerus ke Page Cache, dirty memory melesat cepat dari 25GB ke 51GB. Begitu angka 51GB tersentuh, kernel Linux memaksa **semua proses yang memanggil `write()` untuk berhenti dan ikut melakukan penulisan sinkron ke disk** (*throttling forced synchronous writeback*). Controller NVMe tercekik oleh antrean antrean I/O masif, menyebabkan proses Kafka membeku total selama puluhan detik.

### 8.3. Solusi Arsitektural dan Remedi Kernel Sysctl
Konfigurasi parameter kernel diubah dari persentase menjadi angka byte absolut yang kecil dan agresif, sehingga kernel mem-flush data secara konstan tanpa menunggu tumpukan blob memori raksasa:

```ini
# /etc/sysctl.d/99-high-throughput-storage.conf

# Mulai background flush segera saat dirty memory mencapai 256MB
vm.dirty_background_bytes = 268435456

# Paksa throttle synchronous writeback jika dirty memory tembus 1GB (jangan biarkan capai puluhan GB)
vm.dirty_bytes = 1073741824

# Interval bangun kernel flusher thread (dalam 1/100 detik: 100 = 1 detik)
vm.dirty_writeback_centisecs = 100

# Umur maksimal dirty data sebelum harus ditulis ke disk (500 = 5 detik)
vm.dirty_expire_centisecs = 500

# Hindari zone reclaim agresif pada multi-socket NUMA
vm.zone_reclaim_mode = 0

# Mitigasi latency alloc memory: jangan biarkan kswapd tidur terlalu lelap
vm.extra_free_kbytes = 2097152
```

Terapkan parameter:
```bash
sudo sysctl --system
```
**Hasil:** Setelah parameter di atas diaktifkan, P99 latency Kafka stabil pada angka 4.2 ms secara konsisten tanpa ada lonjakan I/O stall maupun thread lockup.

---

## 9. Trade-offs Architecture Analysis

| Parameter / Fitur Kernel | Nilai / Strategi | Keuntungan (Pros) | Kerugian & Dampak (Cons/Trade-offs) | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- | :--- |
| **I/O Subsystem** | `Buffered I/O` | Kecepatan baca/tulis awal setara memory RAM (sub-microsecond), read-ahead otomatis oleh kernel. | Konsumsi RAM besar untuk Page Cache, overhead CPU copy, rentan spike writeback. | Web server static, file processor batch, log shipper. |
| | `Direct I/O (O_DIRECT)` | Menghilangkan CPU context-switch copy, memori tidak terduplikasi di Page Cache, latency deterministik. | Aplikasi wajib mengelola caching layer sendiri di User Space; transfer wajib sejajar sector boundary. | Enterprise Relational DBMS (PostgreSQL, MySQL InnoDB), Time-series DB. |
| **HugePages** | `Transparent HugePages (THP) = always` | Mengurangi miss rate TLB secara otomatis untuk blok memori 2MB tanpa modifikasi kode program. | Memicu *memory compaction stalls*; alokasi memory sewaktu-waktu mengalami freeze tinggi (latency spike). | Komputasi numerik batch, Machine Learning training pipeline. |
| | `Explicit HugePages (hugetlbfs)` | Alokasi memori fisik terkunci sejak boot, nol fragmentasi, nol compaction latency overhead. | Memori ter-reservasi kaku; tidak bisa digunakan oleh proses non-HugePage walau menganggur. | Database Redis in-memory masif, Network Function Virtualization (DPDK). |
| **CPU Isolation** | CFS `cpu.cfs_quota_us` (Hard Limit) | Mencegah CPU starvation pada environment multi-tenant; menjamin SLA pembagian resource. | Risiko tinggi *CFS Throttling*: proses tidur paksa saat jatah habis di awal window, menaikkan P99 latency. | Multi-tenant Kubernetes cluster, SaaS shared computing. |
| | Core Pinning (`cpuset.cpus`) | Akses eksklusif L1/L2 Cache CPU core, nol inter-core context-switching, latency ultra-rendah. | Penggunaan CPU core menjadi tidak fleksibel; resource terfragmentasi jika task sedang idle. | High-Frequency Trading (HFT), Gateway Jaringan Telco, Core DBMS. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes
1. **Mengabaikan Dampak CFS Throttling pada Microservices:** Menyetel CPU limit yang terlalu ketat pada kontainer seringkali memicu throttling tersembunyi, meskipun utilitas CPU rata-rata yang tampak di monitoring APM baru 30%. Penyebabnya adalah *burst period* yang menghabiskan kuota dalam 20ms pertama dari 100ms jendela penjadwalan.
2. **Kekeliruan Membaca Output Metrik `free -m`:** Panik melihat kolom `free` tersisa puluhan megabyte, tanpa menyadari bahwa memori sedang dipinjam oleh `buff/cache` yang dapat sewaktu-waktu direbut kembali secara instan oleh aplikasi saat dibutuhkan.
3. **Mengaktifkan Swap Besar pada Disk Lambat untuk Node Produksi Latency-Sensitive:** Penggunaan swap pada hard drive spindle/SATA lambat saat sistem mengalami *memory pressure* memicu rantai *Major Page Faults* masif yang melumpuhkan performa aplikasi secara eksponensial (*disk thrashing*).

### 10.2. Troubleshooting Guide: Mendiagnosis CFS Throttling
Jika API service di container mengalami lonjakan latency acak, periksa indikator cgroup v2 berikut:

```bash
# Periksa statistik throttling pada cgroup pod/container target
cat /sys/fs/cgroup/system.slice/docker-<CONTAINER_ID>.scope/cpu.stat

# Output yang harus diperhatikan:
# nr_periods 120530
# nr_throttled 34102   <--- Jika persentase > 5%, aplikasi Anda tercekik CFS!
# throttled_usec 4810291402
```
*Solusi:* Naikkan nilai `cpu.max` atau gunakan mekanisme *CPU burst* (Linux 5.14+) dengan parameter:
```bash
echo "max 100000" > cpu.max
echo "50000" > cpu.max.burst
```

### 10.3. Troubleshooting Guide: Melacak Syscall Latency Menggunakan `bpftrace`
Identifikasi syscall lambat yang memblokir worker thread:

```bash
# Tracing syscall write() yang berjalan lebih dari 10 milidetik (10,000,000 ns)
sudo bpftrace -e '
kprobe:ksys_write {
    @start[tid] = nsecs;
}
kretprobe:ksys_write /@start[tid]/ {
    $duration = nsecs - @start[tid];
    if ($duration > 10000000) {
        printf("PID %d (%s) stuck in write() for %d ms\n", 
               pid, comm, $duration / 1000000);
    }
    delete(@start[tid]);
}'
```

---

## 11. Best Practices (Production Checklist)

### 11.1. Kernel Sysctl Hardening & Tuning Baseline
Terapkan nilai-nilai ini di `/etc/sysctl.d/60-production-engine.conf`:

- [ ] **Networking:** `net.core.somaxconn = 65535` (Cegah penolakan TCP listen backlog).
- [ ] **Networking:** `net.ipv4.tcp_max_syn_backlog = 3240000` (Mitigasi SYN Flood).
- [ ] **Virtual Memory:** `vm.swappiness = 1` (Pertahankan swap hanya untuk kondisi darurat OOM tanpa swapping agresif).
- [ ] **Virtual Memory:** `vm.overcommit_memory = 1` (Standar untuk workload database in-memory seperti Redis).
- [ ] **Virtual Memory:** `vm.max_map_count = 1048576` (Wajib untuk database search-engine Elastic/OpenSearch).
- [ ] **File Descriptors:** `fs.file-max = 2097152` (Ambang batas total deskriptor berkas global kernel).

### 11.2. Storage I/O Scheduler Configuration
Periksa dan atur scheduler media penyimpanan berdasarkan teknologi hardware:
```bash
# Cek scheduler aktif pada NVMe (wajib 'none' untuk bypass overhead scheduler layer)
cat /sys/block/nvme0n1/queue/scheduler
# [none] mq-deadline

# Untuk disk SSD SATA/SAS gunakan mq-deadline atau kyber
echo "mq-deadline" | sudo tee /sys/block/sda/queue/scheduler
```

### 11.3. Service Unit Hardening (`systemd`)
Tambahkan proteksi kernel pada definisi file unit `/etc/systemd/system/app-backend.service`:
```ini
[Service]
# Batas alokasi deskriptor berkas
LimitNOFILE=1048576
LimitNPROC=524288

# Isolasi kernel primitives
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryDenyWriteExecute=true
```

---

## 12. Hands-on Practice

Buat direktori kerja untuk menyimpan seluruh artefak praktikum:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Praktikum 1: Monitoring Alokasi Anonymous Memory vs Minor Page Faults
Kita akan membuktikan alokasi memori Linux bersifat *lazy* (demand paging) melalui C program.

1. Buat berkas `lazy_alloc.c`:
```c
/* hands-on/m02/lazy_alloc.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ALLOC_SIZE (100 * 1024 * 1024) // 100 Megabytes

int main(void) {
    printf("[PID %d] 1. Mengalokasikan 100MB memori virtual via malloc()...\n", getpid());
    char *ptr = (char *)malloc(ALLOC_SIZE);
    if (!ptr) {
        perror("malloc");
        return 1;
    }

    printf("[PID %d] Selesai malloc. Memori BELUM disentuh. Tidur 10 detik.\n", getpid());
    sleep(10);

    printf("[PID %d] 2. Menyentuh memori (menulis data). Memulai Page Faults...\n", getpid());
    // Menulis ke setiap page 4096 bytes untuk memicu Minor Page Fault
    for (size_t i = 0; i < ALLOC_SIZE; i += 4096) {
        ptr[i] = 'A';
    }

    printf("[PID %d] Selesai menulis. Semua Page Frame fisik teralokasi. Tidur 10 detik.\n", getpid());
    sleep(10);

    free(ptr);
    return 0;
}
```

2. Jalankan kompilasi dan ukur menggunakan `perf`:
```bash
gcc -O0 lazy_alloc.c -o lazy_alloc

# Jalankan dengan tracking page faults
perf stat -e minor-faults,major-faults ./lazy_alloc
```

3. **Verifikasi Observasi:**
Perhatikan bahwa saat program berada di fase tidur pertama (setelah `malloc`), konsumsi Resident Set Size (RSS) proses masih 0 KB. Begitu iterasi penulisan berjalan, metrik `minor-faults` melonjak sebanyak $\approx 25.600$ kali ($100\,\text{MB} / 4\,\text{KB} = 25.600$), membuktikan bahwa alokasi fisik frame RAM hanya diproses oleh kernel saat instruksi penulisan memicu trap fault ke MMU.

---

## 13. Exercises

### Level: Easy
1. Gunakan perintah `sysctl` untuk membaca batas maksimal memory dirty expire time pada host lokal Anda.
2. Identifikasi PID dari proses dengan penggunaan Resident Set Size (RSS) tertinggi pada sistem, lalu cari tahu berapa banyak file deskriptor yang sedang terbuka oleh proses tersebut di direktori `/proc/<PID>/fd/`.

### Level: Medium
Tulis sebuah skrip shell yang mengekstrak nilai `oom_score` dan `oom_score_adj` dari semua proses yang berjalan, lalu urutkan secara descending untuk menampilkan 5 proses yang paling rentan dieksekusi mati oleh OOM Killer jika host kehabisan memori.

### Level: Hard
Kompilasi program C yang membuka sebuah berkas berukuran 1GB dengan flag `O_DIRECT`. Pastikan buffer yang digunakan dialokasikan menggunakan `posix_memalign()` agar memenuhi alignment memori blok $4\,\text{KiB}$. Bandingkan statistik dirty memory kernel di `/proc/vmstat` sebelum dan sesudah penulisan data berlangsung.

---

## 14. Challenges

### Deskripsi Kasus
Anda adalah Principal Infrastructure Architect pada platform e-Commerce. Sebuah microservice pembayaran yang dideploy di dalam kontainer mengalami lonjakan error HTTP 504 (*Gateway Timeout*) secara berkala setiap 5 menit selama 20 detik. Karakteristik anomali:
- Monitoring Prometheus menunjukkan metrik penggunaan CPU kontainer berada di angka $75\%$ (limit adalah 2 Core).
- Rata-rata memory footprint tidak pernah melampaui $60\%$ dari `memory.max`.
- Disk latency pada host node tetap berada di bawah 1ms.
- Tim aplikasi bersikeras tidak ada bug pada kode logic pembayaran mereka.

### Instruksi Misi
1. Susun hipotesis komprehensif mengenai kemungkinan anomali pada lapisan penjadwalan kernel (CFS) dan konfigurasi kernel Page Cache / swap.
2. Rancang rangkaian perintah profiling sistem (*one-liner* atau tool tracing) yang harus dijalankan saat insiden berlangsung untuk membedah akar permasalahan secara empiris tanpa me-restart server.
3. Rancang formula perbaikan arsitektural menyeluruh pada tingkat cgroups configuration, kernel tunables, dan runtime arguments.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Apa perbedaan mendasar antara eksekusi CPU di **Ring 0** dan **Ring 3** pada platform arsitektur x86_64?
2. Mengapa kernel Linux menggunakan instruksi prosesor `SYSCALL` modern alih-alih software interrupt `INT 0x80` untuk pemanggilan sistem?
3. Sebutkan 4 objek utama yang mengabstraksikan struktur sistem berkas pada lapisan Virtual Filesystem (VFS) Linux!
4. Apa yang membedakan **Minor Page Fault** dengan **Major Page Fault** dalam subsistem manajemen memori virtual?
5. Mengapa sebuah thread POSIX di Linux pada dasarnya dianggap sebagai sebuah task biasa oleh kernel scheduler?

### 15.2. Pertanyaan Intermediate
6. Jelaskan bagaimana algoritma penjadwalan CFS/EEVDF menggunakan variabel `vruntime` untuk menegakkan asas keadilan alokasi komputasi CPU!
7. Apa risiko operasional terbesar menyetel parameter `vm.dirty_ratio` ke angka yang sangat tinggi (misalnya 60%) pada server yang memiliki kapasitas RAM sangat besar (misal 512GB)?
8. Bagaimana isolasi hierarki tunggal (*single hierarchy*) pada **cgroups v2** menyelesaikan masalah inkonsistensi controller yang terjadi pada cgroups v1?
9. Apa fungsi dari flag `O_DIRECT` saat membuka file descriptor dan mengapa teknologi mesin basis data relasional modern sangat bergantung pada fitur ini?
10. Bagaimana cara kerja perhitungan `oom_badness()` oleh kernel Linux sebelum memilih proses mana yang akan dimatikan secara paksa menggunakan sinyal `SIGKILL`?

### 15.3. Skenario Kasus Produksi

#### Skenario 1
Sebuah container microservice Java/JVM dengan limit RAM cgroup 4GB tiba-tiba mati mendadak dengan Exit Code 137, padahal parameter konfigurasi Java Heap `-Xmx` disetel ke 3GB. Saat dicek, tidak ada satupun pesan `java.lang.OutOfMemoryError` di log aplikasi.
- **Pertanyaan:** Apa penyebab pasti kematian proses tersebut di level kernel Linux, dan metrik sistem apa yang harus Anda verifikasi untuk membuktikannya?

#### Skenario 2
Host server database PostgreSQL bare-metal dengan arsitektur 2 socket CPU (NUMA architecture: Node 0 dan Node 1) mengalami degradasi transaksi per detik (TPS) hingga $50\%$. Analisis `top` menunjukkan salah satu socket CPU memiliki idle time tinggi, namun terjadi lonjakan drastis pada konsumsi CPU `sys` (kernel space) dan metrik `kswapd0` berjalan aktif membakar resource, meskipun total RAM bebas secara global masih tersedia 60GB.
- **Pertanyaan:** Anomali kernel memory management apa yang sedang terjadi, dan bagaimana strategi tuning yang harus diterapkan untuk memitigasinya?

#### Skenario 3
Sebuah aplikasi web high-traffic melempar exception error `socket: too many open files in system` kepada ribuan pengguna aktif secara bersamaan, padahal konfigurasi `ulimit -n` untuk user pengeksekusi aplikasi sudah dinaikkan menjadi `1048576`.
- **Pertanyaan:** Mengapa error tersebut masih terjadi di tingkat kernel, file konfigurasi kernel global apa yang membatasi parameter ini, dan bagaimana perintah untuk memperbaikinya secara runtime?

---

### Kunci Jawaban & Pembahasan Kasus Kuis

#### Jawaban Basic
1. Ring 0 berjalan dengan privilege absolut, memiliki akses penuh ke instruksi CPU sensitif dan pemetaan memori fisik. Ring 3 dibatasi oleh proteksi hardware; dilarang mengakses hardware atau memori secara langsung demi stabilitas dan keamanan sistem.
2. `INT 0x80` adalah interrupt berbasis software yang lambat karena memicu lookup pada Interrupt Descriptor Table (IDT), verifikasi permission segment, dan overhead context switch yang tinggi. `SYSCALL` langsung melompat ke alamat kernel yang disimpan di MSR CPU (`LSTAR`) secara instan.
3. `struct super_block`, `struct inode`, `struct dentry`, dan `struct file`.
4. Minor Page Fault memetakan frame memori yang sudah ada di RAM (tanpa pembacaan disk). Major Page Fault memicu disk I/O untuk memuat blok berkas dari media penyimpanan fisik ke RAM karena data belum tersedia di memori.
5. Karena kernel Linux merepresentasikan keduanya menggunakan struktur data yang sama (`struct task_struct`). Perbedaannya hanya terletak pada apakah *task* tersebut membagi ruang alamat (`mm_struct`) dan deskriptor tabel berkas dengan task lain melalui flag saat pemanggilan fungsi `clone()`.

#### Jawaban Intermediate
6. `vruntime` merepresentasikan jumlah eksekusi CPU virtual yang telah dinikmati oleh sebuah task. Semakin sering suatu task berjalan, semakin besar `vruntime`-nya. Scheduler selalu memilih task dengan `vruntime` terendah untuk dieksekusi berikutnya. Nilai *nice* memperlambat/mempercepat laju pertumbuhan `vruntime` ini.
7. Risiko terjadi I/O stall/freeze masif. Saat dirty page mencapai 60% dari 512GB ($\approx 307\,\text{GB}$ data kotor), kernel akan memaksa penulisan secara sinkron. Proses akan terblokir total (*state D*) selama bermenit-menit hingga tumpukan ratusan gigabyte data selesai dikosongkan ke storage.
8. Pada cgroups v1, setiap controller (cpu, memory, blkio) memiliki hierarki pohon terpisah yang sering menyebabkan *deadlock* dan inkonsistensi tracking resource (misalnya melacak proses mana yang memicu dirty page I/O). Cgroups v2 menyatukan seluruh controller ke dalam satu pohon tunggal terpadu (*unified hierarchy*).
9. `O_DIRECT` menginstruksikan kernel untuk membypass Page Cache sepenuhnya; data langsung ditransfer via DMA antara buffer user-space dan controller storage. Database menggunakannya karena database memiliki *Buffer Pool Manager* sendiri yang jauh lebih pintar dalam mengatur strategi caching dibanding Page Cache Linux.
10. Skor OOM ditentukan dari persentase RAM yang dikonsumsi proses terhadap total memori sistem, ditambah penyesuaian nilai `/proc/<PID>/oom_score_adj`. Task dengan skor kalkulasi tertinggi akan dipilih oleh kernel untuk dikirimi sinyal `SIGKILL` guna menyelamatkan host dari kondisi *panic*.

#### Pembahasan Skenario Kasus Produksi
- **Solusi Skenario 1:**
  Proses JVM dibunuh oleh **Kernel cgroup OOM Killer** (bukan JVM runtime memory leak). Keluarannya adalah Exit Code 137 ($128 + 9$ alias `SIGKILL`). Penyebabnya: total alokasi memori proses JVM bukan hanya Heap (`-Xmx`), melainkan mencakup *Metaspace*, *Thread Stacks* ($1\,\text{MB} \times \text{jumlah thread}$), *Direct ByteBuffers*, dan garbage collection overhead. Ketika akumulasi ini menembus 4GB, cgroup memory watcher mengeksekusi proses secara paksa. Buktinya dapat diverifikasi melalui perintah `dmesg -T | grep -E -i "killed process|oom-killer"` atau memeriksa `memory.events` pada cgroup v2 container tersebut (`oom` dan `oom_kill` counter bertambah).
  
- **Solusi Skenario 2:**
  Terjadi **NUMA Allocation Imbalance / Remote Node Starvation**. Memori pada salah satu NUMA Node (misal Node 0) telah terisi penuh, sementara parameter `vm.zone_reclaim_mode` aktif atau alokasi proses database terikat (*node-affinity*) secara kaku pada satu socket. Akibatnya, alih-alih mengalokasikan RAM kosong yang melimpah di NUMA Node 1, kernel menjalankan `kswapd0` untuk merebut dan mereklamasi memori lokal Node 0 secara agresif, membakar CPU cycles pada kernel space (`sys`). Mitigasi: Setel `sysctl -w vm.zone_reclaim_mode=0`, dan gunakan utilitas `numactl --interleave=all` untuk menyebarkan alokasi memori ke seluruh NUMA node secara berimbang.

- **Solusi Skenario 3:**
  Batas maksimal berkas yang terlampaui adalah **Ambang Batas Global Seluruh Kernel Sistem Operasi (`fs.file-max`)**, bukan batas per-proses/per-user (`ulimit -n` / `RLIMIT_NOFILE`). Meskipun sebuah proses diizinkan membuka 1 juta berkas, jika total akumulasi seluruh proses pada sistem operasi mencapai nilai ceiling `fs.file-max`, pemanggilan sistem `open()` / `socket()` akan ditolak dengan error `ENFILE`. Solusi Runtime: Naikkan nilai file-max global secara permanen dengan `sysctl -w fs.file-max=2097152` dan pasang konfigurasi tersebut ke `/etc/sysctl.d/99-file-limits.conf`.

---

## 16. Summary

```
===================================================================================
                   LINUX KERNEL SUBSYSTEM SUMMARY ARCHITECTURE
===================================================================================

[ USER SPACE ]
      |
      |  (Syscall: RAX/RDI/RSI/RDX -> MSR LSTAR)
      v
+---------------------------------------------------------------------------------+
| KERNEL PRIVILEGE RING 0                                                         |
|                                                                                 |
|   +--------------------+     +---------------------+     +--------------------+ |
|   | PROCESS SCHEDULER  |     |  MEMORY MANAGEMENT  |     |   VFS / STORAGE    | |
|   |--------------------|     |---------------------|     |--------------------| |
|   | - EEVDF / CFS      |     | - Multi-Level Pages |     | - dentry / inode   | |
|   | - task_struct      |     | - Page Faults Engine|     | - Page Cache       | |
|   | - vruntime balance |     | - kswapd & OOM Kill |     | - Direct I/O       | |
|   | - cgroups v2 tree  |     | - NUMA / Dirty Page |     | - Block Layer (bio)| |
|   +--------------------+     +---------------------+     +--------------------+ |
|             |                           |                           |           |
+-------------|---------------------------|---------------------------|-----------+
              v                           v                           v
     [ Hardware CPU Cores ]        [ Physical RAM ]           [ NVMe Storage ]
===================================================================================
```

Arsitektur produksi Linux menuntut pemahaman menyeluruh terhadap kolaborasi antara abstraksi software dan batasan hardware. Kunci kestabilan sistem performa tinggi tidak terletak pada penambahan resource fisik secara membabi buta, melainkan pada ketepatan eliminasi bottleneck kernel:
1. **Transisi Hak Akses Efisien:** Meminimalisir transisi User Space $\to$ Kernel Space yang tidak perlu melalui batching primitives (`epoll`, `io_uring`).
2. **Manajemen Virtual Memory Deterministik:** Menghindari *latency spikes* dengan mengontrol alokasi *Page Cache writeback*, memahami siklus *Minor* vs *Major Page Faults*, serta mengelola isolasi NUMA.
3. **Isolasi Beban Kerja Modern:** Memanfaatkan kapabilitas **cgroups v2** secara presisi guna mencegah degradasi performa akibat perebutan jatah CPU dan memori, memastikan keandalan sistem berskala enterprise.