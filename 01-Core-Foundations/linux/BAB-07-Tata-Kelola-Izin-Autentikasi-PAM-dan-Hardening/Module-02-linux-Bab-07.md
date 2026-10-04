# BAB 07: MATERI LANJUTAN
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal Linux Kernel pada subsistem kritis: Memory Subsystem (VFS, Page Cache, SLAB/SLUB, OOM Killer), CPU Scheduling (`sched_ext`, CFS, cgroups v2), dan Network Stack (eBPF, XDP, TCP/IP ring buffers).
- Mengimplementasikan isolasi beban kerja heterogen tingkat lanjut (*multi-tenant noisy-neighbor isolation*) menggunakan systemd slice dan native Linux cgroups v2 controllers (`memory.high`, `memory.max`, `io.weight`, `cpu.weight`).
- Melakukan profil performa sistem secara non-invasif menggunakan eBPF (`bpftrace`, `bcc-tools`) untuk melacak latensi I/O, network drops, dan context-switch overhead langsung di level kernel.
- Merancang dan mengeksekusi parameterisasi *sysctl* tingkat produksi untuk infrastruktur *ultra-low-latency* dan *high-throughput* (menangani lebih dari 100.000 RPS).
- Memecahkan anomali performa subsistem Linux seperti *tail latency spikes*, *page cache thrashing*, *soft lockups*, dan *TCP buffer bloat* menggunakan metodologi sistematis (*USE Method*, *Off-CPU Analysis*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur dasar Linux Kernel: perbedaan User Space vs Kernel Space, System Calls (`sys_enter_*`), Process Life Cycle (fork/exec, process states).
- Pengoperasian sistem Linux tingkat menengah: manipulasi file permissions, systemd service management, administrasi storage via LVM/ext4/XFS.
- Dasar-dasar networking: layer OSI/TCP-IP, socket programming primitives (`listen`, `accept`, `epoll`), routing, dan packet flow dasar (iptables/nftables).
- Dasar debugging: familiarity dengan utilitas standar seperti `strace`, `lsof`, `vmstat`, `iostat`, dan `top`/`htop`.

---

### 3. Concept & Internal Architecture

Arsitektur produksi Linux modern bergantung pada interaksi deterministik antara subsistem Kernel berikut:

```
+-----------------------------------------------------------------------------------+
|                                   USER SPACE                                      |
|   +-----------------------+   +-----------------------+   +-------------------+   |
|   | Enterprise App (Go)   |   | High-RPS Proxy (NGINX)|   | System Telemetry  |   |
|   +-----------+-----------+   +-----------+-----------+   +---------+---------+   |
+---------------|---------------------------|-------------------------|-------------+
| System Calls  | (read/write/epoll)        | (sendmsg/recvmsg)       | bpf()       |
+---------------v---------------------------v-------------------------v-------------+
|                                  KERNEL SPACE                                     |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | eBPF Virtual Machine (Tracing, Profiling, TC, XDP Hooks)                     |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +---------------------+   +-------------------------+   +---------------------+  |
|  | Memory Subsystem    |   | CPU Scheduler (CFS)     |   | Network Subsystem   |  |
|  | - Page Cache        |   | - Completely Fair Sched |   | - NAPI Polling      |  |
|  | - Anonymous Memory  |   | - cgroups v2 hierarchy  |   | - Socket Queues     |  |
|  | - SLUB Allocator    |   | - Runqueues / NUMA node |   | - TCP/IP Stack      |  |
|  | - Page Reclamation |   | - Latency Sensitive RT  |   | - Ring Buffers (RX) |  |
|  | - OOM Invoker       |   +-------------------------+   +---------------------+  |
|  +---------------------+                                                          |
|            |                                                        |             |
|            v                                                        v             |
|  +---------------------+                                 +---------------------+  |
|  | Virtual File System |                                 | Network Device Core |  |
|  | - ext4 / XFS Layer  |                                 | - DMA Ring Buffers  |  |
|  | - Block Layer / BIO |                                 | - Hardware Queues   |  |
|  +---------------------+                                 +---------------------+  |
|            |                                                        |             |
+------------|--------------------------------------------------------|-------------+
|            v                                                        v             |
|   +------------------+                                     +------------------+   |
|   | NVMe / Block Dev |                                     | Physical NIC/PHY |   |
|   +------------------+                                     +------------------+   |
|                                 HARDWARE                                          |
+-----------------------------------------------------------------------------------+
```

#### A. Virtual Memory Subsystem & Page Reclamation
Linux menggunakan arsitektur Virtual Memory berkonsep *demand paging*. Memori dialokasikan melalui:
1. **Anonymous Pages**: Heap proses, stack, anonymous mmap. Tidak terhubung langsung ke file disk. Ketika terjadi memory pressure, dialokasikan ke Swap jika aktif.
2. **Page Cache**: Caching pembacaan/penulisan file sistem (VFS). Operasi tulis mula-mula disimpan di Page Cache sebagai *dirty pages* sebelum proses kswapd atau flusher threads (`pdflush`, `wb_*`) melakukan sinkronisasi ke blok penyimpanan fisik.
3. **SLUB Allocator**: Kernel object memory allocation (inodes, dentries, socket buffers/sk_buff).

Mekanisme reklamasi memori dikendalikan oleh ambang batas *watermark* (`low`, `min`, `high`) per NUMA memory zone. Ketika pemakaian memori bebas menyentuh `min`, kernel beralih dari asynchronous background reclamation (`kswapd`) ke synchronous direct reclamation, mengakibatkan latensi aplikasi melonjak drastis (*application stall*).

#### B. cgroups v2 Unified Hierarchy
Tidak seperti cgroups v1 yang memisahkan tiap controller (cpu, blkio, memory) ke dalam tree independen, cgroups v2 mengadopsi model *single unified hierarchy*. Model ini mengeliminasi *cross-controller deadlocks* dan mengintegrasikan manajemen alokasi resource:
- Buffer writeback I/O kini dihitung langsung ke pemilik cgroup memory yang memicu penulisan file tersebut, mencegah memory leak yang sebelumnya sering lolos pada cgroups v1.
- *Out-of-Memory (OOM)* handling dapat diisolasi ke seluruh cgroup tree melalui `memory.oom.group`.

#### C. Network Path & eBPF Engine
Paket jaringan masuk melalui NIC menuju Ring Buffer via DMA, memicu *Hard IRQ*. Kernel melayani IRQ tersebut via NAPI softirq context (`ksoftirqd`), memaketkan frame ke dalam struktur `sk_buff`.
- **eBPF (Extended Berkeley Packet Filter)**: Mesin eksekusi in-kernel bertipe RISC-register-based. eBPF memvalidasi kode via In-Kernel Verifier (mencegah memory corruption dan loop tak terhingga) sebelum dieksekusi secara Just-In-Time (JIT) compile. Hook eBPF mencakup kprobe/kretprobe (kernel functions), uprobe (user space functions), tracepoints, socket filters, dan XDP (eXpress Data Path, dieksekusi langsung pada layer driver NIC sebelum memori `sk_buff` dibentuk).

---

### 4. Why & What

| Dimensi | Mengapa Relevan (Why) | Apa yang Dikelola (What) |
| :--- | :--- | :--- |
| **Determinisme Latensi** | *Garbage collection* kernel (dirty writebacks, direct reclaim) memicu jitter >500ms pada *tail latency* (p99.9). | Parameter `vm.dirty_ratio`, `vm.dirty_background_ratio`, cgroups `memory.high`. |
| **Resilience & Fault Isolation** | Satu proses *rogue* (misal: memory leak) dapat memicu global kernel OOM-killer yang mematikan database atau critical proxy. | Isolasi memory via cgroups v2 (`memory.max`), `oom_score_adj`, systemd slices. |
| **Throughput & Network Efficiency** | Driver jaringan default dan TCP settings standar tidak dioptimasi untuk bandwidth >10Gbps atau jutaan koneksi konkuren. | TCP receive/transmit buffer memory (`net.ipv4.tcp_rmem`, `wmem`), `epoll`, NIC ring buffers via `ethtool`. |
| **Observabilitas Real-Time** | Telemetri tradisional (`top`, `iostat`) berbasis sampling periodik (1-5 detik) dan kehilangan insiden *micro-bursts*. | eBPF Dynamic Tracing, Tracepoints, Performance Monitoring Counters (PMCs). |

---

### 5. How (Workflow Detail)

Alur manajemen sistem tingkat produksi mencakup implementasi berurutan:

```
[1. Hardware/OS Baseline] 
       │
       ▼
[2. Kernel Memory Tuning via sysctl] ────► vm.dirty_*, vm.swappiness, vm.zone_reclaim_mode
       │
       ▼
[3. CPU/Memory Isolation via cgroups v2] ─► systemd-cgls, *.slice configuration, oom_score
       │
       ▼
[4. High-Performance Network Stack] ─────► backlog, epoll, TCP BBR, dynamic buffer allocations
       │
       ▼
[5. Real-Time Telemetry with eBPF] ──────► Runtime profile, IO stall detection, tracepoint hooks
```

#### Langkah Implementasi:
1. **Analisis Topologi Hardware**: Verifikasi NUMA nodes menggunakan `numactl --hardware` untuk memetakan core CPU terhadap memory controller fisiknya.
2. **Setup cgroups v2 Unified Mode**: Pastikan kernel boot parameter menggunakan `systemd.unified_cgroup_hierarchy=1`.
3. **Tuning Kernel Runtime**: Modifikasi parameter runtime subsistem via `/etc/sysctl.d/99-enterprise-production.conf`.
4. **Isolasi Service**: Masukkan unit daemon ke dalam `systemd` Slices dengan pembatasan komputasi eksplisit.
5. **Observasi dan Verifikasi**: Pasang probe eBPF untuk menguji apakah degradasi throughput atau *contention lock* terjadi pada boundary kernel space.

---

### 6. Analogy & Diagram ASCII

#### Analogi Page Cache & Dirty Writeback: Tim Pengarsipan Dokumen
Bayangkan sebuah kantor pengarsipan dokumen:
- **Anonymous Memory**: Kertas coretan kerja meja analis yang terus berubah.
- **Page Cache**: Lemari baca cepat. Setiap dokumen dari gudang pusat (SSD) dibuka di sini.
- **Dirty Pages**: Dokumen yang baru direvisi analis tetapi belum dikembalikan ke gudang fisik.
- **`vm.dirty_background_ratio`**: Batas santai. Jika dokumen revisi mencapai 10% meja, staf pembersih (`kswapd`/`flush`) perlahan membawa dokumen ke gudang tanpa menghentikan analis.
- **`vm.dirty_ratio`**: Batas darurat. Jika dokumen revisi mencapai 20% meja kerja, analis dilarang menulis sama sekali (*I/O block*) dan dipaksa ikut mengantar berkas ke gudang (*direct writeback*).

#### Diagram Transisi Lifecycle Memori dan OOM Threshold

```
Physical RAM Limits:
[0% Memory Used]                                                [100% Memory Used]
├──────────────────────┼───────────────────────┼────────────────────────┼───────┤
│ Active Applications  │ Page Cache (Clean)    │ Page Cache (Dirty)     │ SLUB  │
└──────────────────────┴───────────────────────┴────────────────────────┴───────┘
                                                ▲                        ▲
                                                │                        │
                                     dirty_background_ratio          dirty_ratio
                                   (Kernel async flush starts)    (I/O processes BLOCK)

cgroups v2 Enforcement Flow:
[ cgroup2: /production.slice ]
   │
   ├── memory.current
   │
   ├── memory.high ──► [Exceeded: Kernel melakukan throttling latensi & background reclaim]
   │
   ├── memory.max  ──► [Exceeded: Direct synchronous reclaim; jika gagal -> trigger OOM]
   │
   └── memory.oom.group = 1 ──► [Trigger: Bunuh SELURUH proses di dalam slice tanpa residu]
```

---

### 7. Simple Example & Practical Example

#### A. Practical Configuration: Unified Kernel Tuning (`/etc/sysctl.d/99-enterprise-production.conf`)

Konfigurasi kernel sysctl kelas produksi untuk high-throughput microservices:

```ini
# ==============================================================================
# Linux Kernel Advanced Tuning for High-Concurrency / Low-Latency Systems
# ==============================================================================

# 1. Virtual Memory Subsystem
# Kurangi kecenderungan kernel melakukan swapping dari anonymous memory
vm.swappiness = 10

# Mulai background writeback saat dirty memory menyentuh 5% dari total memory
vm.dirty_background_ratio = 5

# Blokir synchronous I/O bila dirty memory menyentuh 15% dari total memory
vm.dirty_ratio = 15

# Jangan alokasi overcommit secara ugal-ugalan; tolak alokasi berlebih di atas formula
vm.overcommit_memory = 0
vm.overcommit_ratio = 50

# Cegah latency spike akibat NUMA zone reclaim (alokasikan node lain sebelum reclaim)
vm.zone_reclaim_mode = 0

# Tingkatkan threshold memory map descriptors untuk high-concurrency app/DB
vm.max_map_count = 262144

# 2. Network Core & TCP Subsystem
# Naikkan batas antrean paket kernel yang menunggu diproses socket layer
net.core.netdev_max_backlog = 16384

# Tingkatkan batas antrean koneksi pending (SYN backlog)
net.core.somaxconn = 32768

# Auto-tuning batas dynamic TCP buffer: min, default, max (dalam bytes)
# Max buffer dinaikkan ke ~16MB untuk throughput jaringan 10Gbps+
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Aktifkan congestion control TCP BBR (Bottleneck Bandwidth and RTT)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Aktifkan reuse port TIME_WAIT untuk incoming connection outbound proxies
net.ipv4.tcp_tw_reuse = 1

# Disable TCP slow start after idle untuk menjaga responsiveness keepalive connections
net.ipv4.tcp_slow_start_after_idle = 0

# 3. File System & File Descriptors
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
```

#### B. cgroups v2 Systemd Slice Resource Enforcement

File: `/etc/systemd/system/production-workload.slice`

```ini
[Unit]
Description=Enterprise Production Workload Slicing
Before=slices.target

[Slice]
# CPU Share Isolation (weight 1-10000)
CPUAccounting=true
CPUWeight=800

# Memory Protection: Beri jaminan 4GB reserved memory dari reclaim
MemoryAccounting=true
MemoryLow=4G

# Throttling point: Reclaim aktif jika menyentuh 28GB
MemoryHigh=28G

# Absolute Hard Limit: Max 32GB
MemoryMax=32G

# OOM Policy: Bunuh semua proses dalam slice jika satu proses meledak
ManagedOOMMemoryPressure=kill
ManagedOOMMemoryPressureLimit=80%
```

File: `/etc/systemd/system/highload-service.service`

```ini
[Unit]
Description=Production API Microservice
After=network.target
PartOf=production-workload.slice

[Service]
Type=simple
Slice=production-workload.slice
User=appuser
Group=appuser
ExecStart=/opt/bin/microservice-api --port=8080
Restart=always
RestartSec=5s

# File descriptor tuning untuk proses ini
LimitNOFILE=1048576

# Prioritas OOM: Rendahkan peluang service ini dibunuh jika sistem global panic
# Nilai berkisar antara -1000 (never kill) hingga 1000 (kill first)
OOMScoreAdjust=-500

[Install]
WantedBy=multi-user.target
```

#### C. eBPF Dynamic Latency Profiling Script

Script `bpftrace` untuk mengukur latensi I/O layer VFS (`vfs_read`) secara real-time:

```bpftrace
#!/usr/bin/env bpftrace
/*
 * File: vfs_latency_profile.bt
 * Mengukur distribusi latensi eksekusi VFS Read dalam satuan mikrodetik
 */

kprobe:vfs_read
{
    @start[tid] = nsecs;
}

kretprobe:vfs_read
/@start[tid]/
{
    $duration_us = (nsecs - @start[tid]) / 1000;
    @vfs_read_lat_us = hist($duration_us);
    delete(@start[tid]);
}

interval:s:5
{
    print(@vfs_read_lat_us);
    clear(@vfs_read_lat_us);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Insiden:
Sebuah gateway sistem perbankan (*Fintech Payment Gateway*) memproses rata-rata 35.000 transaksi per detik. Setiap 15 menit terjadi fenomena *Latency Spike* p99.9 dari 12ms melompat ke 4.500ms (4,5 detik), yang menyebabkan *timeout cascade* pada platform klien.

#### Analisis Akar Masalah (Root Cause Analysis):
1. **Analisis Metrik Tradisional**: Utilitas `top` dan `iostat -x 1` tidak menunjukkan utilisasi CPU 100%, tetapi metrik `%iowait` melonjak berkala ke angka 40%.
2. **Off-CPU Analysis via eBPF**:
   ```bash
   # Melacak thread state yang sleep di kernel space
   sudo offcputime-bpfcc -K -p $(pgrep gateway-service) 5
   ```
   *Stack trace* menunjukkan pemanggil utama tertahan di fungsi kernel: `sync_inodes_sb` -> `ext4_writepages` -> `wait_on_page_writeback`.
3. **Identifikasi Sub-Sistem**:
   - `vm.dirty_ratio` disetel default (20%), sementara memori server berkapasitas 256GB.
   - 20% dari 256GB = ~51GB *dirty pages*.
   - Setiap kali log transaksi yang belum tersinkronisasi mencapai 51GB, kernel menghentikan eksekusi thread aplikasi (*direct reclamation*) dan memblokir thread `write()` hingga flush IO tuntas ke SAN Storage via Fibre Channel.

#### Resolusi & Remediasi:
1. Menerapkan skema *proactive incremental background flushing* via `sysctl`:
   ```bash
   sysctl -w vm.dirty_background_bytes=268435456 # 256MB
   sysctl -w vm.dirty_bytes=1073741824           # 1GB
   ```
2. Mengalihkan partisi log aplikasi ke volume NVMe tersendiri dengan opsi mount `noatime,data=writeback`.
3. Menurunkan nilai `vm.swappiness` dari 60 ke 10 untuk mencegah degradasi cold-memory swapping.

**Hasil**: Latensi p99.9 turun dari 4.500ms ke nilai konstan di 8-11ms tanpa lonjakan berkala.

---

### 9. Trade-offs

| Parameter / Konfigurasi | Keuntungan (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Rekomendasi Deployment |
| :--- | :--- | :--- | :--- |
| **`vm.dirty_bytes` (Kecil: misal 512MB)** | Latensi I/O prediktif, tidak ada *stall* besar saat writeback. | Throughput I/O mentah menurun karena operasi tulis disk dilakukan lebih sering secara granular. | Sistem Online Transaction Processing (OLTP), Low-Latency APIs. |
| **TCP BBR (`bbr`) vs Cubic** | Throughput maksimal pada network dengan packet loss tinggi, minimal buffer bloat. | Agresif terhadap aliran traffic TCP lain (Cubic); starvation berpotensi timbul pada router legacy. | Internet-facing gateways, Global Content Distribution. |
| **cgroups `memory.oom.group=1`** | Integritas konsistensi sistem: mematikan keseluruhan cluster proses yang rusak daripada meninggalkan state setengah jalan (*zombie state*). | Dampak kegagalan lebih besar; service yang berada di satu slice mati total sekaligus. | Database replica sets, microservice container pods. |
| **High `somaxconn` & Backlogs** | Mengurangi `SYN flood rejection` saat lonjakan traffic mendadak (*burst traffic*). | Mengonsumsi *kernel non-paged memory* (SLAB); response timeout klien tetap terjadi jika worker lambat. | Reverse Proxies (Envoy, NGINX, HAProxy). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi:
1. **Mengabaikan SoftIRQ Overload**: Satu core CPU terkunci 100% pada penanganan network interrupt (`si` pada `top`). 
   *Penyebab*: NIC Ring Buffer diarahkan hanya ke CPU core 0 (tidak ada RSS - Receive Side Scaling).
2. **Mematikan Swap Secara Total (`swapoff -a`) Tanpa Perhitungan**:
   *Penyebab*: Kesalahpahaman bahwa swap memperlambat sistem. Mematikan swap secara absolut justru menghilangkan kemampuan kernel untuk mereklamasi *idle/dead anonymous pages*, mempersempit ruang Page Cache yang produktif, dan memicu OOM killer lebih dini.
3. **Mengabaikan File Descriptor Exhaustion**: Nilai limit proses (`LimitNOFILE`) tidak diselaraskan dengan kernel table limit (`fs.file-max`).

#### Panduan Troubleshooting Sistematis:

```
Masalah: Aplikasi Web Timeout / Latency Spike Terdeteksi
  │
  ├─── 1. Cek Drop Paket pada Jaringan:
  │         $ netstat -s | grep -i "buffer errors"
  │         $ tc -s qdisc show dev eth0
  │         -> Solusi: Tingkatkan netdev_max_backlog & driver ring buffer via ethtool
  │
  ├─── 2. Cek Hardware & Soft Interrupt Distribution:
  │         $ mpstat -P ALL 1
  │         -> Jika %soft tinggi pada CPU0 saja: Konfigurasi /proc/irq/<IRQ_NUM>/smp_affinity
  │
  ├─── 3. Cek Kernel Memory Reclaim Contention:
  │         $ sar -B 1 (amati metrik pgscand, pgsteal)
  │         -> Jika pgscand tinggi tapi pgsteal rendah: Terjadi Direct Reclaim Thrashing!
  │
  └─── 4. Cek D-State Threads (Uninterruptible Sleep):
            $ ps -eo state,pid,cmd | grep "^D"
            -> Inspect stack via: cat /proc/<PID>/stack
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Kernel Parameter Baseline**:
  - [ ] `vm.swappiness` diatur di kisaran `1` hingga `10` (jangan dinolkan total kecuali pada database tertentu).
  - [ ] `vm.dirty_background_ratio` diatur antara `5-10%` atau gunakan `vm.dirty_background_bytes`.
  - [ ] `net.core.somaxconn` dinaikkan minimal ke `4096` atau `16384` untuk web ingress.
  - [ ] `fs.file-max` dinaikkan sesuai kalkulasi concurrent open sockets + block access.
- [ ] **Resource Partitioning**:
  - [ ] Memisahkan Workload ke cgroups v2/systemd slices: `system.slice`, `production.slice`, `infra-monitoring.slice`.
  - [ ] Pasang `MemoryHigh` sebagai *canary threshold* sebelum eksekusi hard ceiling `MemoryMax`.
- [ ] **File System & Storage**:
  - [ ] Pasang flag mount `noatime` pada partisi transaksi database dan storage logs.
  - [ ] Gunakan scheduler I/O modern (`none` atau `mq-deadline` untuk NVMe; `bfq` untuk multi-tenant spinning disks).
- [ ] **Network Interface Cards (NIC)**:
  - [ ] Pastikan driver NIC mengaktifkan multi-queue dan didistribusikan via `irqbalance` atau pinned CPU affinity.
  - [ ] Verifikasi Ring Buffer NIC berada pada nilai maksimum hardware: `ethtool -G eth0 rx <MAX> tx <MAX>`.
- [ ] **Observability**:
  - [ ] Sediakan package `bpftrace` dan `perf` di node produksi tanpa dependensi kompilasi kernel dinamis (gunakan BTF - BPF Type Format).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum pada folder: `hands-on/m02/`

#### Lab 1: Mengaktifkan cgroups v2 Memory Isolation dengan Leak Simulation

1. Buat direktori praktikum:
   ```bash
   mkdir -p hands-on/m02/lab1 && cd hands-on/m02/lab1
   ```

2. Tulis simulator program memory leak (`leak_simulator.c`):
   ```c
   #include <stdio.h>
   #include <stdlib.h>
   #include <string.h>
   #include <unistd.h>

   int main() {
       size_t chunk_size = 10 * 1024 * 1024; // 10MB
       int steps = 0;
       printf("PID: %d started allocating memory...\n", getpid());

       while(1) {
           char *p = malloc(chunk_size);
           if (!p) {
               perror("malloc failed");
               return 1;
           }
           memset(p, 0xAA, chunk_size); // Force physical page allocation
           steps++;
           printf("Allocated: %d MB\n", steps * 10);
           usleep(100000); // 100ms
       }
       return 0;
   }
   ```

3. Kompilasi program:
   ```bash
   gcc -O2 leak_simulator.c -o leak_simulator
   ```

4. Buat native cgroups v2 tree manual:
   ```bash
   sudo mkdir -p /sys/fs/cgroup/sandbox
   # Beri batasan maksimum 100MB
   echo "100M" | sudo tee /sys/fs/cgroup/sandbox/memory.max
   echo "max" | sudo tee /sys/fs/cgroup/sandbox/memory.swap.max
   ```

5. Jalankan simulator di dalam cgroup tersebut:
   ```bash
   echo $$ | sudo tee /sys/fs/cgroup/sandbox/cgroup.procs
   ./leak_simulator
   ```

6. Evaluasi output kernel dmesg:
   ```bash
   dmesg -T | grep -E -i "oom|killed process"
   ```
   *Amati bagaimana kernel menghentikan proses hanya di dalam `/sandbox` tanpa mengganggu desktop/server utama.*

#### Lab 2: Observabilitas Latensi Socket Menggunakan eBPF

1. Buat direktori:
   ```bash
   mkdir -p hands-on/m02/lab2 && cd hands-on/m02/lab2
   ```

2. Tulis skrip deteksi koneksi masuk (`tcp_connection_latency.bt`):
   ```bpftrace
   #!/usr/bin/env bpftrace

   BEGIN
   {
       printf("Tracking TCP inbound latency (accept() path). Press Ctrl-C to stop.\n");
   }

   kprobe:sys_enter_accept4
   {
       @start_accept[tid] = nsecs;
   }

   kretprobe:sys_enter_accept4
   /@start_accept[tid]/
   {
       $lat_us = (nsecs - @start_accept[tid]) / 1000;
       @accept_latency_us = hist($lat_us);
       delete(@start_accept[tid]);
   }

   END
   {
       clear(@start_accept);
   }
   ```

3. Jalankan script eBPF:
   ```bash
   sudo bpftrace tcp_connection_latency.bt
   ```

4. Di terminal terpisah, tembak koneksi dengan traffic load (misal: Apache Benchmark):
   ```bash
   ab -n 10000 -c 100 http://localhost/
   ```

---

### 13. Exercise

#### Level: Easy
1. Ubah parameter sysctl `vm.swappiness` menjadi `15` tanpa perlu me-reboot mesin Linux Anda. Pastikan konfigurasi tersebut bersifat persisten setelah reboot.
2. Identifikasi core CPU manakah yang menangani network interrupts untuk device `eth0` menggunakan file virtual `/proc/interrupts`.

#### Level: Medium
1. Konfigurasikan sebuah systemd service bernama `worker-batch.service`. Batasi service ini agar tidak boleh menggunakan lebih dari 150% CPU capacity (1.5 Cores) dan tidak boleh melampaui RAM 2GB. Apabila batas memori tercapai, service harus otomatis dihentikan seluruh prosesnya, bukan hanya single child process.
2. Tulis skrip Bash untuk memonitor rasio *dirty pages* terhadap total memori terpakai dari `/proc/meminfo` secara realtime setiap 1 detik. Kirim sinyal alert jika dirty pages melampaui 10% dari total RAM.

#### Level: Hard
1. Buat program `bpftrace` yang melacak panggilan *system call* `write` yang memakan waktu eksekusi lebih dari 100ms. Cetak Nama Proses (`comm`), Process ID (`pid`), ukuran file descriptor, dan durasi eksekusinya dalam microsecond ke stdout secara streaming.

---

### 14. Challenge

**Studi Kasus: The High-Frequency Trading Noisy-Neighbor Mystery**

Anda bertindak sebagai Principal Infrastructure Engineer pada platform Micro-Trading. Terdapat 2 cluster proses yang ditempatkan pada server bare-metal berspesifikasi ganda: AMD EPYC 64-Core, 512GB RAM, 2x 100GbE NICs.
- **Node A (Execution Engine)**: Service C++ ultra-low latency; wajib mempertahankan response time socket-to-socket sub-millisecond (< 500µs).
- **Node B (Reporting Batch)**: Service Java Analytics yang setiap 30 menit menarik dump transaksi memori untuk agregasi lalu menulis laporan audit terenkripsi sebesar ~50GB ke SSD NVMe lokal.

**Problem:**
Meskipun proses Execution Engine telah di-*pinning* menggunakan `taskset` (CPU pinning) ke Core 0-15, dan Java Reporting dipasang di Core 16-63, latensi transaksi Execution Engine selalu melompat dari 350µs ke 85.000µs (85ms) setiap kali Java Reporting Batch melakukan penulisan berkas laporan ke NVMe.

**Tugas Anda:**
1. Desain investigasi arsitektural: Mengapa CPU pinning gagal mengisolasi latensi? Subsistem kernel mana saja yang menjadi titik temu perdebatan resource (*contention point*) di antara kedua proses tersebut?
2. Berikan solusi arsitektural lengkap tanpa menambah server fisik baru, mencakup:
   - Isolasi VFS / Block I/O Layer.
   - Manajemen Memory Reclamation & Writeback throttling.
   - Konfigurasi Kernel Command Line / sysctl.
   - Systemd / cgroups v2 profile.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)
1. Apa perbedaan mendasar antara anonymous memory dan page cache di dalam sistem Linux?
2. Apa yang terjadi jika kernel Linux mencapai parameter batas `vm.dirty_ratio`?
3. Mengapa parameter `vm.swappiness = 0` pada kernel modern tidak sepenuhnya mematikan swap?
4. Apa fungsi dari flag `SO_REUSEPORT` pada layer socket Linux?
5. Di filesystem virtual manakah cgroups v2 secara standar dipasang (*mount*) pada distro Linux modern?

#### B. Intermediate (5 Pertanyaan)
1. Jelaskan bagaimana mekanisme cgroups v2 `memory.high` berbeda cara kerjanya dengan `memory.max`!
2. Mengapa NAPI (New API) polling pada Linux Network Subsystem lebih efisien dibanding model interrupt-driven biasa saat menghadapi incoming packet rate jutaan paket per detik?
3. Jelaskan risiko mengaktifkan `vm.overcommit_memory = 2` pada sistem yang menjalankan aplikasi dengan footprint memori dinamis seperti JVM!
4. Bagaimana eBPF verifier memastikan keselamatan eksekusi kode di dalam kernel space tanpa mengakibatkan kernel panic?
5. Mengapa opsi filesystem mount `noatime` secara dramatis dapat mengurangi penulisan disk pada high-traffic file server?

#### C. Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario 1**:
   Sebuah server database MySQL mengalami *freeze* selama 3-5 detik secara berkala. Saat diperiksa, nilai metrik `pgscand` pada `sar -B` bernilai sangat tinggi, tetapi `kswapd` CPU utilization mendekati nol.
   *Pertanyaan*: Anomali apa yang sedang terjadi di memory subsystem, dan parameter sysctl apa yang harus dianalisis untuk mengatasi masalah ini?

2. **Skenario 2**:
   Koneksi HTTP dari aplikasi web sering terputus dengan error `Connection reset by peer` di jam sibuk. Nilai CPU utilization dan RAM masih tersisa 40%. Log `dmesg` menunjukkan pesan: `TCP: request_sock_TCP: Possible SYN flooding on port 80. Dropping request.`
   *Pertanyaan*: Jika dipastikan ini bukan serangan DDoS melainkan traffic legitimate, parameter kernel dan network stack layer apa saja yang harus ditingkatkan kapasitasnya?

3. **Skenario 3**:
   Aplikasi backend Anda tiba-tiba mati mendadak tanpa meninggalkan jejak stack trace pada Application Error Log. Perintah `systemctl status` menunjukkan exit code `SIGKILL` (Code 137).
   *Pertanyaan*: Tuliskan langkah investigasi menggunakan log sistem untuk memverifikasi apakah Linux OOM-Killer yang mengeksekusi proses tersebut, dan bagaimana cara melindungi proses penting dari eksekusi OOM killer tanpa merusak stabilitas kernel!

---

### 16. Summary

1. Arsitektur produksi Linux menuntut pemahaman lintas-subsistem yang holistik: performa aplikasi tidak semata-mata ditentukan oleh efisiensi kode, melainkan bagaimana kode tersebut berinteraksi dengan Virtual Memory, CPU Scheduler, VFS, dan Network Stack kernel.
2. Pengelolaan memori yang deterministik dicapai dengan mengendalikan ritme *dirty page writeback* secara halus (`vm.dirty_background_bytes`, `vm.dirty_bytes`) untuk mencegah fenomena ekstrim *direct reclamation stall*.
3. cgroups v2 merevolusi tata kelola isolasi sistem Linux dengan menyediakan struktur hierarki terpadu (*unified hierarchy*), mengintegrasikan akuntansi writeback I/O, dan memberikan kontrol berlapis via `memory.high` (throttling preventif) dan `memory.max` (hard cap isolasi).
4. eBPF telah mengubah paradigma observabilitas performa enterprise dari model sampling statis menjadi *programmable, in-kernel, low-overhead dynamic tracing*, memungkinkan analisis latensi hingga skala mikrodetik langsung di akar penyebab masalah.
5. Tuning kernel produksi adalah seni mengelola *trade-offs*: tidak ada konfigurasi magis yang berlaku universal; optimasi throughput sering kali harus dibayar dengan kompromi alokasi memori atau latensi tail yang harus disesuaikan secara presisi terhadap arsitektur beban kerja sistem.