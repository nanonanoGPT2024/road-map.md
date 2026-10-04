# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI LINUX

**Kategori:** 01-Core-Foundations  
**Bab:** BAB-02-Materi-Lanjutan  
**Topik:** Linux Kernel Subsystems, Resource Management (cgroups v2), Storage/VFS Internals, High-Performance Networking Stack, dan Observabilitas Sistem Skala Enterprise.

---

## 1. LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Memanipulasi Linux Virtual Memory System:** Menjelaskan siklus alokasi kernel (*Buddy System*, *SLUB Allocator*), *Page Cache mechanics*, *Dirty Page Writeback Engine*, serta konfigurasi *Out-Of-Memory* (OOM) *killer* berbasis prioritas heuristik (`oom_score_adj`).
2. **Mengonfigurasi dan Mengisolasi Resource Multi-Tenant melalui cgroups v2:** Mengimplementasikan hierarki cgroups terpadu (*unified hierarchy*) untuk kontrol presisi terhadap alokasi CPU (*CFS Bandwidth Control*), limit memori (*hard/soft limits*, swap isolation), serta I/O throttling berbasis *blkio/io.weight*.
3. **Mengoptimalkan Linux Network Subsystem:** Menganalisis *packet traversal path* dari NIC Driver (Ring Buffer, NAPI, SoftIRQ) ke Socket Buffer, serta melakukan *low-latency tuning* pada Linux TCP/IP stack (TCP window scale, *syn-backlog*, TIME_WAIT reuse, epoll architecture).
4. **Mendiagnosis Kernel-Level Bottlenecks:** Menggunakan instrumentasi modern berbasis eBPF (`bpftrace`, `bcc-tools`), perf events, and `/proc` debugging untuk melacak *off-CPU latency*, *lock contention*, dan VFS *micro-stalls*.
5. **Menerapkan Hardening dan Tuning Produksi Enterprise:** Merancang konfigurasi kernel berstandar PCI-DSS dan SOC2, tuning baseline sysctl untuk platform komputasi intensif (misal: Kubernetes Node, Database Engine berskala besar), serta otomatisasi systemd slices.

---

## 2. PREREQUISITES

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar Linux I/O: File descriptors, streams (`stdin`, `stdout`, `stderr`), pipes, redirection, serta permissions POSIX standard.
* Pengetahuan umum arsitektur OS: Pemisahan ruang alamat User-Space vs Kernel-Space, System Calls (`open`, `read`, `write`, `fork`, `execve`), interrupt handling.
* Pengalaman operasional baris perintah: Administrasi paket OS, navigasi direktori `/proc` dan `/sys`, monitoring dasar (`top`, `ps`, `netstat`/`ss`, `iostat`).
* Dasar jaringan TCP/IP: Three-way handshake, state flags (SYN, ACK, FIN, RST), MTU, subnetting, dan port socketing.

---

## 3. CONCEPT & INTERNAL ARCHITECTURE

Arsitektur internal Linux Kernel dibangun di atas abstraksi modular yang sangat berkinerja tinggi, mengelola interaksi antara hardware dan user-space application processes.

```
+-----------------------------------------------------------------------------------+
| USER SPACE                                                                        |
| Applications / Daemons / Containers (JVM, PostgreSQL, Nginx, Go Runtimes)          |
| Standard C Library (glibc / musl) | Native System Call Invocation (syscall instruction) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                    [CPU Ring 3 -> Ring 0 Transition via SYSENTER/SYSCALL]
                                          v
+-----------------------------------------------------------------------------------+
| KERNEL SPACE (Linux Core Architecture)                                            |
|                                                                                   |
|  +------------------------+  +-------------------------+  +--------------------+  |
|  | Process Scheduler      |  | Virtual Memory (VMM)    |  | Virtual Filesystem |  |
|  | - CFS (Fair Scheduler) |  | - Buddy Allocator (4KB) |  | (VFS Layer)        |  |
|  | - Realtime (FIFO/RR)   |  | - SLUB (Objects)        |  | - Dentry Cache     |  |
|  | - cgroups v2 control   |  | - Page Cache / Swappiness| | - Inode Table      |  |
|  +------------------------+  +-------------------------+  +--------------------+  |
|                                                                     |             |
|  +--------------------------------------------------+               |             |
|  | Network Subsystem (Netfilter / eBPF Engine)      |               v             |
|  | - NIC Ring Buffer -> SoftIRQ/NAPI -> sk_buff     |     +--------------------+  |
|  | - TCP/IP Protocol Stack -> Socket Layers         |     | Block Layer (I/O)  |  |
|  | - eBPF Bytecode Verifier & JIT Compiler          |     | - mq-deadline/kyber|  |
|  +--------------------------------------------------+     +--------------------+  |
|                                                                     |             |
+---------------------------------------------------------------------|-------------+
| HARDWARE INTERACTION (Drivers & Architecture HAL)                   v             |
| CPU (x86_64/ARM64) | MMU (TLB/Paging) | NVMe/SSD Storage | Physical NICs (PCIe)   |
+-----------------------------------------------------------------------------------+
```

### 3.1. Virtual Memory Management (VMM) Internals
Linux menggunakan skema alamat berbasis virtual memory dengan arsitektur *paging* 4 tingkat (P4D) atau 5 tingkat (P5D) pada x86_64, yang diterjemahkan ke memori fisik melalui *Translation Lookaside Buffer* (TLB) di level CPU hardware:

1. **The Buddy System:** Pengelola alokasi memori fisik level rendah yang mengelompokkan halaman memori (standar 4KB) menjadi blok-blok orde $2^n$ (misal: 4KB, 8KB, 16KB ... hingga orde 10/11 = 4MB). Tugasnya meminimalkan fragmentasi eksternal.
2. **SLUB Allocator:** Mengalokasikan struktur internal kernel berukuran kecil (kurang dari satu page), seperti *task_struct*, *mm_struct*, atau *inode* cache. SLUB menggantikan SLAB lama dengan mengurangi overhead metadata.
3. **Page Cache & Dirty Writeback Engine:** Seluruh disk I/O dialirkan melalui Page Cache. Saat operasi `write()` dipanggil tanpa flag `O_DIRECT`, data ditulis langsung ke Page Cache RAM dan ditandai sebagai *dirty page*. Kernel *flusher threads* (`kworker/flush`) bertugas menyinkronkan blok dirty ini ke disk fisik berdasarkan rasio batas:
   * `vm.dirty_background_ratio`: Ambang batas persentase memori di mana kernel mulai menulis *dirty pages* ke disk secara asinkron di background.
   * `vm.dirty_ratio`: Ambang batas persentase di mana proses yang mencoba melakukan write akan **diblokir** (synchronous writeback) sampai dirty pages berkurang.
4. **OOM Killer Subsystem:** Ketika memori fisik dan swap habis terpakai (*allocation failure*), kernel memicu Out-of-Memory Killer. Heuristik kalkulasi skor OOM:
   $$\text{oom\_score} = \frac{\text{RSS pages} + \text{swap pages}}{\text{Total Available Pages}} \times 1000 + \text{oom\_score\_adj}$$
   Nilai `oom_score_adj` (-1000 sampai +1000) memungkinkan admin melindungi critical process dari terminasi paksa.

### 3.2. CFS (Completely Fair Scheduler) & cgroups v2
* Linux CFS tidak menggunakan time-slice statis, melainkan melacak $vruntime$ (*virtual runtime*), yaitu jumlah waktu CPU yang telah dikonsumsi oleh sebuah thread, dinormalisasi berdasarkan bobot *niceness* (-20 s/d 19).
* CFS menggunakan struktur data **Red-Black Tree** (rbtree). Thread dengan $vruntime$ terkecil selalu berada di node paling kiri (`rb_leftmost`) dan menjadi kandidat berikutnya untuk dieksekusi oleh core CPU.
* **cgroups v2 (Unified Hierarchy):** Menyederhanakan cgroups v1 yang terfragmentasi. Mengimplementasikan aturan *No Internal Process*, di mana sebuah cgroup hanya boleh memiliki child cgroups ATAU kumpulan proses langsung, tidak boleh keduanya sekaligus. Controllers terintegrasi mencakup:
  * `cpu.max`: Mengatur alokasi CPU CFS Bandwidth dalam format `<quota> <period>` (misal: `50000 100000` = 0.5 CPU core).
  * `memory.max`: Hard limit alokasi memori fisik. Jika terlampaui, OOM killer di-trigger lokal di cgroup tersebut.
  * `memory.high`: Throttling/reclaim limit (soft limit) yang memicu *asynchronous page reclaim* tanpa memicu OOM killer secara agresif.
  * `io.max`: Mengatur batasan pembacaan/penulisan blok I/O per block device (IOPS dan Byte/s limit).

### 3.3. Linux Network Ingress Path
1. Paket ethernet diterima oleh Physical NIC, masuk ke **RX Ring Buffer**.
2. NIC mengirimkan **Hard IRQ (Hardware Interrupt)** ke CPU core.
3. Kernel menjalankan ISR (*Interrupt Service Routine*), mendisposisi Hard IRQ, menjadwalkan `NET_RX_SOFTIRQ`, dan mengaktifkan **NAPI (New API)** loop.
4. CPU mengalokasikan struct `sk_buff` (SKB), lalu *polling* paket dari ring buffer menggunakan mekanisme NAPI tanpa interrupt berulang (mencegah *interrupt storm*).
5. Paket dilewatkan ke layer eBPF/XDP (jika terpasang), dievaluasi oleh iptables/nftables (*Netfilter hooks*), dialihkan ke TCP/UDP stack, divalidasi checksum, lalu ditransfer ke Socket Receive Buffer (`SO_RCVBUF`).
6. Aplikasi user-space menerima notifikasi ketersediaan data melalui pemanggilan IO multiplexer non-blocking `epoll_wait()`.

---

## 4. WHY & WHAT

### Mengapa Perlu Memahami Linux Internals?
Dalam skala enterprise, infrastruktur tidak pernah berjalan dalam isolasi teoretis. Menjalankan *workload* latensi rendah (seperti Redis clusters, Apache Kafka, atau distributed databases seperti Cassandra/ScyllaDB) di atas setelan default OS Linux sering kali menyebabkan:
* **Latency Spikes Tak Terprediksi:** Diakibatkan oleh kswapd *direct reclaim stalls* saat dirty pages melonjak.
* **Network Degradation:** *Dropped packets* pada layer socket buffer (`listen backlog drops`), port exhaustion, serta TCP TIME_WAIT accumulation.
* **Noisy Neighbors:** Kegagalan isolasi resource antar container akibat konfigurasi cgroups yang keliru, menyebabkan starvation CPU dan page eviction pada critical workloads.

### Apa yang Dipelajari di Level Produksi?
* **Bukan Sekadar CLI:** Memahami parameter kernel (`/proc/sys/vm/*`, `/proc/sys/net/*`) dari sudut pandang alokasi struktur data kernel.
* **Deterministic Control:** Mengonfigurasi isolasi NUMA (*Non-Uniform Memory Access*), core affinity, and scheduling classes untuk menghapus jitter pada high-frequency transactions.
* **Observabilitas Tingkat Dalam Tanpa Overhead:** Menggunakan eBPF untuk inspeksi sistem tanpa overhead tinggi seperti pada `ptrace` atau `strace`.

---

## 5. HOW: PRODUCTION IMPLEMENTATION WORKFLOW

Berikut adalah workflow sistematis dalam melakukan tuning, isolasi, dan validasi kinerja kernel di lingkungan produksi:

```
[1. Baseline Profiling]
   └── Mengambil snapshot performa: /proc/interrupts, vmstat 1, sar, mpstat -P ALL 1
        │
        v
[2. Architectural Tuning: Memory Subsystem]
   ├── Set vm.dirty_ratio & vm.dirty_background_ratio untuk mencegah I/O freeze.
   ├── Set vm.swappiness (1-10) untuk menghindari unnecessary swapping pada low latency.
   └── Konfigurasi Transparent HugePages (THP) sesuai target (madvise untuk DBs).
        │
        v
[3. Architectural Tuning: Network & Sockets]
   ├── Memperbesar SOMAXCONN dan netdev_max_backlog.
   ├── Tuning TCP Buffer Sizes: net.ipv4.tcp_rmem / tcp_wmem.
   └── Optimasi Conntrack tables jika menggunakan NAT/Firewalling padat.
        │
        v
[4. Workload Isolation: Unified cgroups v2]
   ├── Membangun custom slice di systemd: /etc/systemd/system/workload.slice.
   ├── Mendefinisikan limits: MemoryMin, MemoryLow, MemoryMax, CPUWeight, CPUQuota.
        │
        v
[5. Real-time Verification]
   ├── Verifikasi cgroups via `/sys/fs/cgroup/`.
   └── Observasi context switching & queue depth via eBPF/bpftrace.
```

---

## 6. ANALOGY & DIAGRAM ASCII

### Analogi Page Cache, Dirty Pages, dan Writeback Engine
Bayangkan kernel sebagai sebuah **Pabrik Manufaktur Dokumen**:
* **Aplikasi User-Space:** Klien yang memesan dokumen untuk dituliskan stempel dan disimpan ke gudang arsip permanen (**Disk/NVMe**).
* **Page Cache (RAM):** Meja kerja utama berukuran besar tempat dokumen ditumpuk sebelum disimpan ke gudang.
* **Aplikasi Menulis Dokumen (`write` syscall):** Klien menaruh dokumen langsung ke atas meja kerja (sangat cepat, dalam hitungan nanodetik). Dokumen ini sekarang bertatus "Belum Diarsipkan" (**Dirty Page**).
* **`vm.dirty_background_ratio` (Pembersih Santai):** Ketika tumpukan dokumen di atas meja mencapai persentase tertentu (misal: 10%), petugas kebersihan (*kworker/flush*) mulai membawa dokumen-dokumen ini ke gudang secara santai tanpa menghentikan klien menulis.
* **`vm.dirty_ratio` (Pemberhentian Darurat):** Jika dokumen di meja menumpuk tak terkendali hingga mencapai batas kritis (misal: 20%), manajer pabrik memerintahkan seluruh klien berhenti menulis! Setiap klien dipaksa menghentikan pekerjaannya dan secara fisik membawa sendiri tumpukannya ke gudang arsip (**Synchronous I/O Stall**).

```
RAM (Page Cache)
+---------------------------------------------------------------+
| Clean Pages (Unmodified Cache) | Dirty Pages (Pending Flush)  |
+--------------------------------+------------------------------+
                                 |
           vm.dirty_background_ratio (e.g., 10%)
                                 |  ==> Background writeback (kworker)
                                 v
+---------------------------------------------------------------+
| Critical Threshold: vm.dirty_ratio reached (e.g., 20%)        |
| APPLICATION THREAD BLOCKED (Synchronous Flush to Disk)        |
+---------------------------------------------------------------+
                                 |
                                 v
                 PHYSICAL STORAGE LAYER (Disk I/O)
```

---

## 7. CODE EXAMPLES: IMPLEMENTASI PRAKTIS

### 7.1. Simple Example: Investigasi VFS, File Descriptor, dan Memory Leak Kernel
Skrip Bash diagnosa status konsumsi dentry/inode cache dan pemetaan file descriptor yang terbuka pada sistem:

```bash
#!/usr/bin/env bash
# Script name: vfs_mem_inspect.sh
set -euo pipefail

echo "=== System File Descriptor Utilization ==="
ALLOCATED_FD=$(cut -f1 /proc/sys/fs/file-nr)
UNUSED_FD=$(cut -f2 /proc/sys/fs/file-nr)
MAX_FD=$(cut -f3 /proc/sys/fs/file-nr)
printf "Allocated FDs : %d\n" "$ALLOCATED_FD"
printf "Max Allowable : %d\n" "$MAX_FD"
printf "Usage Percentage: %.2f%%\n\n" "$((ALLOCATED_FD * 100 / MAX_FD))"

echo "=== Top 5 Memory Slab Allocations (Kernel Internal Objects) ==="
# Membaca informasi slab memory dari /proc/slabinfo melalui slabtop batch
if command -v slabtop &> /dev/null; then
    slabtop -o -s c | head -n 12 | tail -n 6
else
    head -n 10 /proc/slabinfo
fi

echo -e "\n=== VFS Inode / Dentry Cache Footprint ==="
grep -E 'dentry|inode' /proc/slabinfo | awk '{print $1, "Instances: " $2, "Size: " ($2 * $4)/1024/1024 " MB"}'
```

### 7.2. Practical Example: Production Systemctl Tuning & cgroups v2 Setup
Konfigurasi enterprise untuk database server (PostgreSQL/ScyllaDB) berkinerja tinggi, mengombinasikan optimasi kernel sysctl dan pembatasan isolasi cgroups v2 melalui native systemd.

#### A. Konfigurasi Kernel Baseline (`/etc/sysctl.d/99-enterprise-production.conf`)
```ini
# --- VIRTUAL MEMORY TUNING ---
# Mencegah memory starvation dan memory stall ekstrem
vm.swappiness = 1
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
vm.vfs_cache_pressure = 50
# Mencegah kernel memory allocation deadlocks
vm.min_free_kbytes = 1048576

# --- NETWORK TCP/IP & SOCKET ENGINE ---
# Antrian koneksi maksimum sistem
fs.file-max = 2097152
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 16384
net.ipv4.tcp_max_syn_backlog = 16384

# Window scaling & memory allocation untuk TCP (min, default, max dalam bytes)
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Port range & connection reuse
net.ipv4.ip_local_port_range = 10240 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# Proteksi SYN Flooding
net.ipv4.tcp_syncookies = 1
```

#### B. cgroups v2 Systemd Slice (`/etc/systemd/system/workload-database.slice`)
```ini
[Unit]
Description=Isolasi Dedicated Database Workload Slice (cgroups v2)
Before=slices.target

[Slice]
# CPU Control: Batasi total penggunaan hingga 16 Cores (1600%)
CPUAccounting=true
CPUQuota=1600%

# Memory Hard/Soft Limits
MemoryAccounting=true
MemoryHigh=60G
MemoryMax=64G
MemorySwapMax=0G

# I/O Protection: Memberikan bobot I/O lebih tinggi daripada default (100)
IOAccounting=true
IOWeight=800

# Task Limits untuk mencegah resource exhaustion (fork bomb)
TasksMax=16384
```

#### C. Custom Systemd Unit Service Menggunakan Slice Tersebut (`/etc/systemd/system/db-engine.service`)
```ini
[Unit]
Description=Mission Critical Engine Service
After=network.target
Requires=workload-database.slice

[Service]
Type=notify
Slice=workload-database.slice
ExecStart=/usr/local/bin/engine-daemon --config=/etc/engine/engine.conf
Restart=always
RestartSec=5s

# Hardening & Security Isolation Directives
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_SYS_NICE

# Atur OOM Score agar kebal dari killing acak
OOMScoreAdjust=-900

# Set CPU Core Affinity (NUMA Node 0: Cores 0-7)
CPUAffinity=0 1 2 3 4 5 6 7

[Install]
WantedBy=multi-user.target
```

---

## 8. REAL WORLD CASE STUDY (ENTERPRISE SCALE)

### Skenario: PostgreSQL Query Stalls & eBPF Root-Cause Analysis
* **Konteks:** Sebuah platform payment gateway memproses 35.000 transaksi database per detik (TPS) pada server bare-metal multi-socket x86_64 dengan RAM 512GB dan NVMe RAID-10 arrays.
* **Permasalahan:** Setiap 15-20 menit, sistem mengalami *micro-stalls* di mana query latensi melonjak dari $0.8\text{ ms}$ menjadi $12.000\text{ ms}$ selama rentang 3 hingga 5 detik. Akibatnya, API Gateway mengalami cascade timeout (HTTP 504). Monitoring standar (`top`, `htop`) tidak menunjukkan lonjakan pemakaian CPU yang mencurigakan.

### Analisis & Investigasi:
1. **Pemeriksaan `/proc/vmstat`:**
   Ditemukan metrik `nr_dirty` melonjak hingga ~60GB, diikuti kenaikan dramatis pada metrik `allocstall` dan `pgsteal_direct`. Ini menandakan bahwa proses aplikasi terjebak dalam *direct memory reclamation* (harus membuang cache secara instan sebelum bisa mengalokasikan RAM baru).
2. **Pengecekan System Tuning:**
   Ditemukan default settings Linux OS:
   * `vm.dirty_ratio = 20` (20% dari 512GB = ~102GB)
   * `vm.dirty_background_ratio = 10` (~51GB)
   * `vm.zone_reclaim_mode = 1`
   Ketika proses penulisan log transaksi intensif mengisi dirty pages hingga 102GB, disk subsystem NVMe mengalami antrian penulisan massal (*flusher storm*). Kernel memblokir system call `write()` milik PostgreSQL demi mendorong data ke disk.
3. **Penyelidikan Latensi VFS dengan bpftrace:**
   Engineers menginjeksi bpftrace script untuk mengukur latensi fungsi kernel `vfs_write`:
   ```bash
   bpftrace -e 'kprobe:vfs_write { @start[tid] = nsecs; } 
                kretprobe:vfs_write /@start[tid]/ { 
                    @duration_us = hist((nsecs - @start[tid]) / 1000); 
                    delete(@start[tid]); 
                }'
   ```
   **Hasil Trace:** Ditemukan histogram outlier ekstrim di mana beberapa panggilan `vfs_write` memakan waktu lebih dari 4.000.000 microsecond (4 detik) tepat saat *dirty page threshold* tersentuh.

### Solusi & Mitigasi:
1. **Ubah Dirty Engine limits dari rasio persentase ke batas absolut byte:**
   ```bash
   sysctl -w vm.dirty_background_bytes=268435456  # 256MB
   sysctl -w vm.dirty_bytes=1073741824            # 1GB
   ```
   *Efek:* Kernel tidak lagi menunggu data kotor bertumpuk hingga puluhan gigabyte. Kernel melakukan *trickle write* kecil secara kontinyu ke storage array tanpa memblokir thread eksekusi database.
2. **NUMA Balancing Tuning:**
   Non-Uniform Memory Access (NUMA) balancing dinonaktifkan (`kernel.numa_balancing = 0`) dan PostgreSQL diikat (*pinned*) menggunakan `numactl --interleave=all` untuk menghilangkan latensi *cross-node memory access*.
3. **Hasil Akhir:** Latensi query $p99.9$ stabil di angka $\le 1.8\text{ ms}$, dan lonjakan latensi micro-stalls tereduksi hingga 0%.

---

## 9. TRADE-OFFS & ARCHITECTURAL DECISIONS

Dalam arsitektur sistem Linux level lanjut, setiap penyesuaian parameter selalu membawa konsekuensi arsitektural:

| Komponen Tuning | Pilihan / Konfigurasi | Keuntungan (Pros) | Biaya / Trade-off (Cons) |
| :--- | :--- | :--- | :--- |
| **I/O Engine (Page Cache)** | `O_DIRECT` (Bypass Page Cache) | Menghilangkan CPU memory copy overhead; mencegah double buffering pada database cache internal. | Tidak ada read-ahead otomatis; aplikasi harus mengelola buffer alignment dan block sizing sendiri secara ketat. |
| **Dirty Memory Limits** | Absolute bytes rendah (misal: 256MB) vs Percentage tinggi (misal: 20%) | **Bytes rendah:** Latensi deterministik, tidak ada I/O stalls massal.<br>**Percent tinggi:** Throughput agregat maksimum untuk batch writes. | Throughput I/O sequential disk menurun jika limit bytes terlalu rendah karena disk tidak dapat melakukan coalescing I/O blocks optimal. |
| **Network Processing** | Polling Berkelanjutan (Busy Polling / DPDK / XDP) | Latensi sub-mikrodetik; bypass interrupt kernel dan network stack traversal. | CPU core akan terkunci pada 100% load terus menerus (idle spinning); konsumsi daya dan panas server melonjak tajam. |
| **Kernel Page Allocator** | Transparent HugePages (THP) = `always` vs `madvise` | **Always:** Meningkatkan hit-rate TLB untuk proses memori besar bertipe sekuensial (HPC, scientific computing). | Mengakibatkan alokasi memori acak (random small-writes) lambat, page-splitting overhead tinggi, dan memory bloat pada DB. |
| **cgroups v2 Quota** | Hard Quota (`cpu.max`) vs Soft Shares (`cpu.weight`) | **Hard Quota:** Isolasi mutlak, proteksi total terhadap CPU starvation bagi penyewa lain. | CPU throttling dapat terjadi meskipun sistem secara keseluruhan memiliki banyak idle CPU capacity. |

---

## 10. COMMON MISTAKES & TROUBLESHOOTING

### 10.1. Common Mistakes
1. **Mengaktifkan `net.ipv4.tcp_tw_recycle`:**
   Parameter usang ini melanggar standar RFC 1323 dan menyebabkan penolakan koneksi acak jika klien berada di balik NAT publik (Load Balancer, Corporate Gateways), karena dependensi pada TCP timestamps. *(Catatan: opsi ini telah dihapus permanen sejak Linux 4.12, namun script warisan sering kali masih mencoba mengaktifkannya).*
2. **Salah Memahami cgroups v1 vs v2:**
   Mencampur controllers cgroups v1 dan v2 secara bersamaan (*hybrid mode*) pada Linux distributions modern (Ubuntu 22.04+, RHEL 9+) yang mengakibatkan Docker atau systemd gagal membaca accounting limits secara presisi.
3. **Mengabaikan Interrupt CPU Core Affinity (IRQ Balancing):**
   Membiarkan seluruh Hardware Interrupt NIC ditangani oleh `CPU0`. Hal ini menyebabkan `CPU0` tersedak dalam status `100% softirq` (*si* pada top), sementara puluhan CPU core lainnya berstatus idle (*unbalanced packet processing*).

### 10.2. Troubleshooting Guide

#### Kasus A: "Packet Dropped at Ring Buffer"
* **Indikator:** Perintah `netstat -s` atau `ethtool -S <eth_interface>` mencatat kenaikan nilai counter `rx_dropped` atau `rx_fifo_errors`.
* **Solusi Diagnostik:**
  1. Periksa ukuran ring buffer saat ini:
     ```bash
     ethtool -g eth0
     ```
  2. Perbesar ukuran RX Ring Buffer hingga nilai maksimum hardware:
     ```bash
     ethtool -G eth0 rx 4096 tx 4096
     ```

#### Kasus B: "Kernel OOM Killer Membunuh Proses yang Salah"
* **Indikator:** Log sistem `/var/log/messages` atau `dmesg -T` menampilkan output:
  `Out of memory: Kill process 1234 (mysqld) score 850 or sacrifice child`.
* **Solusi Diagnostik:**
  1. Cek skor kalkulasi OOM saat ini:
     ```bash
     cat /proc/$(pgrep mysqld)/oom_score
     ```
  2. Terapkan koreksi proteksi deterministik pada service:
     ```bash
     echo -800 > /proc/$(pgrep mysqld)/oom_score_adj
     ```

---

## 11. BEST PRACTICES & PRODUCTION CHECKLIST

### System Deployment Checklist:
- [ ] **Filesystem Options:** Partisi ext4/xfs dimount dengan opsi `noatime` pada disk data untuk menghapus overhead penulisan metadata timestamp akses file.
- [ ] **I/O Scheduler:** Gunakan `none` (pada NVMe/PCIe SSD) atau `mq-deadline` (pada SATA SSD). Hindari scheduler kompleks lama seperti `cfq`.
  ```bash
  echo none > /sys/block/nvme0n1/queue/scheduler
  ```
- [ ] **Entropy Pool Stability:** Pastikan random generator tidak terblokir dengan memvalidasi ketersediaan `haveged` atau verifikasi kernel driver modern `virtio-rng`.
- [ ] **Core Dumps Limit:** Batasi ukuran core dump produksi untuk mencegah disk partition exhaustion saat terjadi fatal crash:
  ```bash
  # /etc/security/limits.conf
  * hard core 0
  ```
- [ ] **HugePages Configuration:** Nonaktifkan THP secara global jika menjalankan Database/In-Memory Cache (Redis/Mongo/Postgres):
  ```bash
  echo madvise > /sys/kernel/mm/transparent_hugepage/enabled
  echo madvise > /sys/kernel/mm/transparent_hugepage/defrag
  ```

---

## 12. HANDS-ON PRACTICE

Langkah-langkah berikut dirancang untuk dijalankan pada virtual machine terisolasi atau development server Linux (disimpan pada path: `hands-on/m02/`).

### Skenario: Simulasi dan Investigasi Latensi I/O & cgroups Throttling
Tujuan: Membangun kontrol cgroup v2, menguji throttling disk I/O buatan, dan menganalisis dampaknya terhadap kernel buffer.

#### Langkah 1: Persiapan Environment
```bash
# Buat direktori kerja praktikum
mkdir -p hands-on/m02/ && cd hands-on/m02/

# Pastikan hierarki cgroups v2 telah terpasang
mount -t cgroup2
```

#### Langkah 2: Membangun Unified cgroup Terisolasi
```bash
# Masuk sebagai superuser
sudo su

# Buat grup kontrol baru langsung di hierarki sysfs
mkdir -p /sys/fs/cgroup/perf-test

# Aktifkan controller CPU, Memory, dan IO untuk sub-tree
echo "+cpu +memory +io" > /sys/fs/cgroup/cgroup.subtree_control
```

#### Langkah 3: Menetapkan Limitasi I/O Ketat
```bash
# Dapatkan major:minor number dari root disk device
ROOT_DEV=$(lsblk -no MAJ:MIN $(df / | tail -1 | awk '{print $1}'))
echo "Target Block Device: $ROOT_DEV"

# Terapkan read limit maksimum 2MB/s (2097152 bytes/s) pada device tersebut
echo "$ROOT_DEV rbps=2097152" > /sys/fs/cgroup/perf-test/io.max
```

#### Langkah 4: Eksekusi Workload & Validasi Throttling
```bash
# Jalankan container atau subshell di dalam cgroup tersebut
# Masukkan PID subshell ke dalam file cgroup.procs
sh -c 'echo $$ > /sys/fs/cgroup/perf-test/cgroup.procs && \
       dd if=/dev/sda of=/dev/null bs=1M count=20 iflag=direct'
```

#### Langkah 5: Analisis Hasil via I/O Counter cgroups
```bash
# Cek data statistik pemblokiran / throttling pada cgroup
cat /sys/fs/cgroup/perf-test/io.stat
```
*Catatan:* Amati bagaimana throughput rate tertahan tepat di ~2.0 MB/s, membuktikan bahwa kernel IO scheduler langsung mencekik throughput proses tanpa crash.

---

## 13. EXERCISES

### Level: Easy
1. Tuliskan satu perintah command line berbasis pipeline untuk mencari 10 proses yang mengonsumsi **Resident Set Size (RSS)** tertinggi di sistem Anda, menampilkan PID, nama proses, dan ukuran konsumsi memori dalam Megabytes (MB).
2. Tentukan perbedaan konseptual antara status thread **Interruptible Sleep (`S`)** dan **Uninterruptible Sleep (`D`)**. Kondisi hardware/sistem apa yang biasanya membuat sebuah proses tertahan pada state `D`?

### Level: Medium
1. Sebuah server web Nginx mengalami galat `502 Bad Gateway` saat menerima lonjakan traffic mendadak (*flash crowd*). Pada log `dmesg`, ditemukan pesan:
   `TCP: request_sock_TCP: Possible SYN flooding on port 80. Dropping request.`
   Padahal verifikasi membuktikan ini bukan serangan denial-of-service, melainkan lalu lintas autentik. Sebutkan dan jelaskan fungsi dari 3 parameter sysctl yang harus Anda naikkan untuk menanggulangi issue ini.
2. Jelaskan apa yang terjadi pada *Page Table* ketika sebuah child process dibuat melalui system call `fork()` menggunakan mekanisme **Copy-On-Write (COW)**. Kapan alokasi memori fisik baru benar-benar terjadi?

### Level: Hard
1. Buatlah script otomasi Bash (atau skrip bpftrace) yang memonitor metrik `/proc/net/dev_mcast` dan `/proc/interrupts` untuk mendeteksi apakah salah satu CPU core menangani porsi hardware interrupt NIC 5x lebih tinggi daripada core lainnya (kondisi Core Imbalance). Jika terdeteksi, script harus mampu menuliskan konfigurasi CPU mask baru ke `/proc/irq/<IRQ_NUM>/smp_affinity`.

---

## 14. CHALLENGE

### Studi Kasus: "The Phantom Micro-Freeze di Financial Matching Engine"

**Latar Belakang:**
Sebuah perusahaan broker ekuitas menjalankan matching engine berlatensi ultra-rendah (dikembangkan dengan C++) pada mesin Ubuntu 22.04 LTS bare-metal dengan arsitektur Dual Socket AMD EPYC (total 128 cores, 512GB RAM). 

**Masalah:**
Aplikasi mencatat terjadinya *outlier latency*: 99.99% transaksi selesai di bawah $40\text{ }\mu\text{s}$, namun setiap interval 10-15 menit sekali, terdapat sekelompok transaksi yang membutuhkan waktu hingga $45.000\text{ }\mu\text{s}$ (45 ms). Kejadian ini membuat matching engine kehilangan prioritas quote di bursa.

**Kondisi Sistem yang Diamati:**
* CPU Utilization total tidak pernah melebihi 35%.
* Server terhubung via 100GbE NIC (Mellanox ConnectX-6).
* Swap space diposisikan nonaktif (`swapoff -a`).
* Monitoring database dan network edge tidak mencatat adanya packet drop di switch fisik.

**Tugas Anda:**
Rancang sebuah dokumen arsitektural investigasi dan implementasi yang mencakup:
1. **Daftar Hipotesis Kernel:** Sebutkan minimal 3 subsistem kernel yang berpotensi menyebabkan micro-freeze tak terlihat ini (Petunjuk: Pikirkan tentang TLB shooting down, Memory Compaction / THP Defrag, atau CPU C-States / Frequency Governor switching).
2. **Observability Strategy:** Tentukan instruksi eBPF/tracepoints kernel spesifik yang harus diinjeksi untuk mengonfirmasi hipotesis tanpa mematikan proses produksi (termasuk deteksi lock acquisition time pada `mm_struct`).
3. **Hardened Architecture Blueprint:** Tuliskan konfigurasi final kernel command line (`/etc/default/grub`), tuning scheduler isolcpus, isolasi cgroups v2, dan power management parameters untuk menjamin determinisme latensi total bagi thread matching engine tersebut.

---

## 15. EVALUASI PEMAHAMAN (QUIZ)

### Bagian 1: 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara memori **VIRT (Virtual)**, **RES (Resident)**, dan **SHR (Shared)** yang ditampilkan pada utility `top`?
2. Apakah file descriptor yang telah dibuka oleh proses otomatis ditutup ketika proses tersebut mengalami crash/SIGSEGV? Mengapa?
3. File konfigurasi apa di Linux yang menentukan hak akses pembatasan resource POSIX (seperti max open files, stack size, max user processes) secara statis?
4. Apa fungsi dari flag `TCP_NODELAY` ketika dipasang pada network socket pemrograman aplikasi?
5. Mengapa swap space tetap disarankan untuk dialokasikan dalam kapasitas kecil (misal: 1-2GB) pada sebagian besar server produksi, meskipun RAM server berukuran sangat besar?

### Bagian 2: 5 Pertanyaan Intermediate
1. Bagaimana cara Linux kernel membedakan perlakuan antara I/O read miss (data tidak ada di Page Cache) dengan penanganan Page Fault saat aplikasi mengakses pointer memori baru?
2. Pada struktur cgroups v2, jelaskan mengapa fitur *Multiple Hierarchies* yang ada pada cgroups v1 dihilangkan dan diganti dengan *Unified Hierarchy* tunggal?
3. Jelaskan hubungan fungsional antara `epoll_create`, `epoll_ctl`, dan `epoll_wait`. Mengapa `epoll` jauh lebih scalable dibanding `select` dan `poll` dalam menangani 100.000 concurrent sockets?
4. Apa dampak negatif dari parameter sysctl `vm.overcommit_memory = 2` (No Overcommit) terhadap aplikasi yang menggunakan pola runtime `fork()` seperti Redis?
5. Bagaimana cara kerja mekanisme **NAPI (New API)** pada Linux network driver dalam mencegah fenomena **Receive Livelock** pada sistem penerima lalu lintas jaringan skala tinggi?

### Bagian 3: 3 Skenario Kasus Produksi
1. **Skenario Kasus 1:**
   Sebuah distributed storage cluster mengeluhkan penulisan data yang tercekik secara acak. Parameter kernel menunjukkan `vm.vfs_cache_pressure = 1000`. Bagaimana nilai konfigurasi ini mempengaruhi dentry/inode cache, Page Cache, dan kinerja operasi filesystem `stat()` dan `open()`?
2. **Skenario Kasus 2:**
   Sebuah container microservice Java/JVM dengan batas alokasi cgroups memory sebesar 4GB sering mengalami `Exit Code 137` (Killed), namun tidak ada log Java `java.lang.OutOfMemoryError` yang tertulis pada file log aplikasi. Jelaskan subsistem apa yang membunuh container ini dan bagaimana langkah analisanya.
3. **Skenario Kasus 3:**
   Sebuah server database membaca throughput disk sangat lambat meskipun menggunakan hardware NVMe mutakhir. Saat dicek via `cat /sys/block/nvme0n1/queue/rotational`, hasilnya adalah `0`. Namun latency read sangat tinggi. Anda menemukan bahwa queue depth diset terlalu rendah dan CPU Core yang melayani IO Interrupt terisolasi secara keliru. Langkah apa saja yang perlu diambil?

---

### Kunci Jawaban Evaluasi Pemahaman

#### Jawaban Bagian 1: Basic
1. **VIRT:** Total alamat memori virtual yang diminta proses (termasuk file di disk, memory mapped, library shared, dan memory yang belum dialokasikan ke RAM fisik). **RES:** Alokasi memori fisik (RAM) aktual yang sedang ditempati oleh proses saat ini. **SHR:** Porsi memori Resident (RES) yang dapat dipakai bersama dengan proses lain (contoh: dynamic shared library C standard, shared memory segments).
2. **Ya, ditutup otomatis.** Ketika proses mati, kernel Linux mengeksekusi fungsi pembersihan internal `do_exit()`. Kernel menelusuri struct `files_struct` milik proses dan menurunkan *reference count* dari semua file descriptor yang terbuka. Jika *reference count* mencapai nol, struktur file VFS terkait ditutup dan dikembalikan ke pool kernel.
3. `/etc/security/limits.conf` (dan direktori `/etc/security/limits.d/`).
4. Menonaktifkan **Nagle's Algorithm**. Flag ini memaksa socket untuk langsung mengirimkan paket-paket kecil ke network tanpa menunggu terkumpulnya data seukuran MSS (*Maximum Segment Size*), esensial untuk memangkas latensi pada interaksi request-response cepat.
5. Swap kecil memungkinkan kernel secara aman memindahkan halaman memori yang hampir tidak pernah diakses (*cold anonymous pages*, seperti kode inisialisasi daemon) ke disk secara lambat, sehingga membebaskan memori fisik berharga untuk dialokasikan sebagai **Page Cache** aktif yang mempercepat performa I/O.

#### Jawaban Bagian 2: Intermediate
1. **Page Fault** adalah interupsi hardware CPU saat mencoba mengakses alamat virtual yang belum terpetakan ke *Physical Frame* di MMU. Kernel mengevaluasi penyebabnya: jika alamat valid namun merujuk ke data file storage yang belum masuk RAM, kernel membangkitkan disk request untuk membaca file tersebut ke dalam **Page Cache** (ini adalah read miss), kemudian memetakan frame fisik tersebut ke page table proses dan menginstruksikan CPU untuk melanjutkan eksekusi instruksi.
2. Pada cgroups v1, setiap controller (cpu, memory, blkio) memiliki hierarki pohon terpisah yang tidak saling berkomunikasi. Hal ini menyebabkan inkonsistensi pelacakan resource: misalnya, controller blkio tidak bisa melacak page cache writeback yang dibangkitkan oleh proses yang dibatasi di controller memory. Pada cgroups v2, *Unified Hierarchy* memastikan sebuah proses berada pada satu path pohon yang sama untuk seluruh resource, memungkinkan akuntansi terintegrasi antar-subsistem (contoh: *cross-resource cost accounting* antara memory writeback dan I/O throttling).
3. `select` dan `poll` memiliki kompleksitas algoritma $\mathcal{O}(n)$, di mana pada setiap loop pemanggilan, seluruh list socket descriptor harus disalin dari user-space ke kernel-space dan di-scan satu per satu. Sebaliknya, `epoll` beroperasi pada skala $\mathcal{O}(1)$:
   - `epoll_create` mengalokasikan struktur rbtree dan ready-list di kernel space.
   - `epoll_ctl` mendaftarkan event callback socket ke device hardware driver.
   - `epoll_wait` hanya mengembalikan socket yang berstatus aktif dari *ready list* internal kernel, tanpa melakukan looping pada socket yang sedang idle.
4. Nilai `vm.overcommit_memory = 2` membatasi alokasi alokasi virtual memori total tidak boleh melebihi formula: $\text{Swap} + (\text{RAM} \times \text{overcommit\_ratio})$. Ketika Redis melakukan snapshotting data ke disk, Redis memanggil system call `fork()` untuk menduplikasi dirinya. Meskipun `fork()` menggunakan Copy-On-Write dan membutuhkan memori fisik aktual yang sangat sedikit, kernel akan mengkalkulasi seolah-olah Redis menduplikasi seluruh virtual memory-nya. Akibatnya, `fork()` akan gagal (*Out of Memory error*) meskipun kapasitas RAM fisik masih melimpah.
5. Pada traffic tinggi, interrupt-driven model murni membuat CPU menghabiskan 100% kapasitasnya hanya untuk memproses hardware interrupt (*interrupt storm*), sehingga tidak ada siklus tersisa untuk memproses paket itu sendiri (**Receive Livelock**). NAPI mengatasi ini dengan teknik hybrid: paket pertama memicu interrupt, namun driver kemudian mendisposisi interrupt selanjutnya dan berpindah ke mode **polling berkelanjutan** (menguras paket dari RX Ring buffer) hingga buffer kosong, baru kemudian mengaktifkan kembali hardware interrupt.

#### Jawaban Bagian 3: Skenario Kasus Produksi
1. **Analisis Nilai `vm.vfs_cache_pressure = 1000`:**
   Nilai default parameter ini adalah 100. Angka ekstrim 1000 memaksa kernel untuk mereclaim (membuang) metadata filesystem (Dentry dan Inode caches) dari RAM secara sangat agresif dibandingkan Page Cache biasa. Akibatnya, server mengalami *directory cache thrashing*. Setiap pemanggilan system call `stat()`, `open()`, atau pengecekan izin direktori akan berujung pada disk seek fisik langsung ke storage metadata block alih-alih dilayani instan dari memory cache. Kinerja storage cluster terpuruk drastis pada direktori hierarki padat. Solusinya adalah mengembalikan nilai ke default `100` atau `50`.
2. **Analisis Container Exit Code 137:**
   *Exit code 137* mengindikasikan proses dihentikan oleh sinyal `SIGKILL` (128 + 9). Ketiadaan jejak pada log internal JVM membuktikan bahwa JVM tidak pernah menyadari kekurangan memori heap Java. Ini adalah indikasi pemutusan sepihak oleh **cgroups v2 Memory Controller OOM Killer**. Ketika total konsumsi memori container (JVM Heap + Metaspace + Off-Heap direct buffers + overhead glibc thread stack) melebihi `memory.max` cgroups, kernel langsung menghentikan proses tanpa intervensi runtime.
   *Diagnosa:* Jalankan `dmesg -T | grep -E -i 'oom[-_]killer|killed process'` atau inspeksi counter throttling pada `/sys/fs/cgroup/<container_slice>/memory.events` (perhatikan field `oom` dan `oom_kill`).
3. **Analisis Kasus Bottleneck NVMe:**
   - **Queue Depth:** Default queue depth perangkat block mungkin terkonfigurasi terlalu dangkal untuk karakteristik NVMe parallelism. Cek dan naikkan parameter `/sys/block/nvme0n1/queue/nr_requests` (misal dari 128 ke 1024/2048) agar controller NVMe dapat memanfaatkan arsitektur antrian internal paralelnya secara optimal.
   - **SMP Affinity:** Hardware interrupt NVMe queues kemungkinan besar hanya dilayani oleh CPU Core tertentu (misal Core 0) sehingga core tersebut saturated. Verifikasi dengan `cat /proc/interrupts | grep nvme`. Aktifkan daemon `irqbalance` atau konfigurasi afinitas mask `/proc/irq/<nvme_irq_number>/smp_affinity` agar antrian I/O didistribusikan secara simetris ke seluruh core CPU yang berada pada NUMA node lokal yang sama dengan slot PCIe disk tersebut.

---

## 16. SUMMARY

Modul ini telah mengupas tuntas arsitektur operasional dan mekanika internal Linux Kernel untuk lingkungan enterprise:
* **Memory Management:** Alokasi kernel dikendalikan oleh Buddy System dan SLUB allocator. Penanganan Page Cache diatur oleh Dirty Writeback Engine, di mana pemahaman batas mutlak byte (`dirty_bytes`) lebih esensial dibanding rasio persentase dinamis untuk mencegah synchronous micro-stalls pada platform IOPS tinggi.
* **CPU Scheduling & cgroups v2:** CFS mendistribusikan waktu komputasi secara deterministic menggunakan Red-Black tree berbasis $vruntime$. Unified hierarchy cgroups v2 menyediakan kontrol resource isolation terpusat (CPU, Memori, dan I/O) tanpa friksi antar-controller.
* **Network & Storage Data Paths:** Mengoptimalkan packet traversal melalui ring-buffer tuning, mitigasi interrupts berlebih via NAPI, dan konfigurasi kernel VFS/socket queues menghilangkan bottleneck tersembunyi yang tidak dapat diselesaikan hanya dengan penskalaan hardware.
* **Production Engineering Mindset:** Pemecahan masalah di level enterprise memerlukan observabilitas presisi tinggi tanpa instrumen yang menginterupsi eksekusi (seperti penggunaan modern eBPF hooks) serta pemahaman menyeluruh atas trade-off di setiap modifikasi parameter sistem.