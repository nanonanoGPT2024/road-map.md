# MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengonfigurasi Kernel Subsystems**: Menguasai arsitektur internal Linux Virtual File System (VFS), Page Cache, Memory Reclaim, CFS (Completely Fair Scheduler), dan Linux Network Stack (NAPI, SoftIRQ, Ring Buffers).
- **Menerapkan Advanced I/O & Storage Optimization**: Mengonfigurasi dan membandingkan synchronous I/O, asynchronous I/O (`io_uring`), direct I/O, serta multi-queue block layer scheduling (`mq-deadline`, `none`, `kyber`) pada storage berlatensi ultra-rendah (NVMe/PCIe Gen4/5).
- **Mengoptimalkan NUMA (Non-Uniform Memory Access)**: Mendesain strategi alokasi memori dan task pinning lintas CPU node guna meminimalkan latency overhead inter-connect (UPI/Infinity Fabric).
- **Mengeksekusi Kernel Tracing & Observability**: Menggunakan eBPF (`bpftrace`, BCC tools) dan `perf` untuk mengidentifikasi lock contention, CPU throttling, off-CPU wait time, serta degradasi performa I/O secara deterministik.
- **Membangun Baseline Arsitektur Linux Enterprise**: Merancang file konfigurasi kernel (`sysctl`), systemd slicing berbasis cgroups v2, serta network stack hardening untuk beban kerja berskala jutaan *requests per second* (RPS).

---

## 2. Prerequisites

Sebelum mempelajari materi ini, Anda harus memahami:
- Konsep dasar Linux Architecture (User Space vs. Kernel Space, System Calls, Process Life Cycle).
- Manipulasi dasar file descriptor, process signals, standard POSIX threads.
- Penggunaan dasar utilitas monitoring: `top`/`htop`, `vmstat`, `iostat`, `netstat`/`ss`.
- Pengetahuan fundamental arsitektur komputer: Register, CPU Cache Hierarchy (L1/L2/L3), RAM, Interrupts, dan Bus interface.

---

## 3. Concept & Internal Architecture

Implementasi Linux skala produksi menuntut pemahaman interaksi antara subsistem inti kernel:

```
+-----------------------------------------------------------------------------------+
|                                  USER SPACE                                       |
|  [Enterprise Application: Nginx / Envoy / Java JVM / Go Engine / PostgreSQL]      |
+-----------------------------------------------------------------------------------+
       | (System Calls: epoll_wait, io_uring_enter, clone3, mmap, futex)
       v
+-----------------------------------------------------------------------------------+
|                                  KERNEL SPACE                                     |
|                                                                                   |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  |  PROCESS/CPU CORE  |  |   VIRTUAL MEMORY     |  |       VFS & STORAGE       |  |
|  |  - CFS Scheduler   |  |   - NUMA Nodes (0,1) |  |   - VFS Inodes/Dentries   |  |
|  |  - cgroups v2      |  |   - Page Allocator   |  |   - Page Cache (Dirty/Cln)|  |
|  |  - Runqueues       |  |   - Slab/Slub (dentry|  |   - Block Layer (mq-sched)|  |
|  |  - Context Switch  |  |   - Direct vs Kswapd |  |   - NVMe Driver           |  |
|  +--------------------+  +----------------------+  +---------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                           NETWORKING CORE (TCP/IP)                          |  |
|  |  - NIC Driver (Ring Buffers: RX/TX) -> Hard IRQ                             |  |
|  |  - NAPI Polling Loop -> SoftIRQ (ksoftirqd)                                 |  |
|  |  - eBPF / XDP Hook Layer                                                    |  |
|  |  - TCP Stack (IP Route -> Conntrack -> TCP Recv Queue -> Socket Buffer)     |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
       |                                      |                               |
       v                                      v                               v
+-------------------+              +----------------------+       +-----------------+
|  Hardware: CPUs   |              | Hardware: NUMA RAM   |       | Hardware: NICs  |
|  (Cores, Caches)  |<------------>| (DDR4/5 per Socket)  |<----->| & NVMe Storage  |
+-------------------+   QPI/UPI    +----------------------+  PCIe +-----------------+
```

### 3.1. CPU Scheduling: Completely Fair Scheduler (CFS) & cgroups v2
Linux CFS mengalokasikan CPU menggunakan *red-black tree* berbasis `vruntime` (virtual runtime):

$$\text{vruntime} += \Delta\text{exec\_time} \times \frac{\text{NICE\_0\_LOAD}}{\text{se->load.weight}}$$

Pada arsitektur multi-tenant berbasis container (Docker/K8s), cgroups v2 mengontrol alokasi CPU melalui dua interface utama:
- `cpu.weight`: Alokasi proporsional (analog dengan *shares*).
- `cpu.max`: Kuota absolut (`quota` dan `period`). Jika proses menghabiskan jatah waktu CPU dalam satu periode sebelum siklus berakhir, kernel memicu *CFS throttling* yang mengakibatkan lonjakan tail latency ($p99$/$p99.9$).

### 3.2. Memory Management: NUMA, Page Cache, dan Reclaim Engine
Sistem multi-socket modern menerapkan NUMA. Setiap socket memiliki local memory controller:
- **Local Access**: Core mengakses RAM di socket yang sama (~60-80 ns).
- **Remote Access**: Core mengakses RAM di socket lain via Interconnect (Intel UPI / AMD Infinity Fabric), menimbulkan penalti latensi hingga 150-300%.

Kernel mengelola caching disk melalui **Page Cache**:
- **Dirty Pages**: Halaman memori yang termodifikasi di RAM tetapi belum ditulis ke non-volatile storage.
- **Memory Reclaim Pipeline**:
  - `kswapd`: Daemon background asinkron yang berjalan ketika konsumsi memori mencapai watermark low (`WMARK_LOW`).
  - `Direct Reclaim`: Sinkronisasi pembersihan memori secara blocking yang dipicu ketika level memori mencapai `WMARK_MIN`. Ketika aplikasi memasuki fase direct reclaim, thread eksekusi akan tertahan (*stalling*), menyebabkan penurunan performa kritis pada basis data atau message broker.

### 3.3. Advanced I/O Subsystem: POSIX AIO vs. `io_uring`
Secara historis, Linux menggunakan model I/O berbasis synchronous blocking/non-blocking (`epoll`). Walaupun `epoll` efisien untuk network descriptors, antarmuka ini tidak kompatibel dengan disk storage reguler (yang selalu berstatus *ready* bagi `epoll`).
- `io_uring` menyelesaikan limitasi ini melalui dua *lockless circular ring buffers* yang dibagikan (*shared memory*) antara kernel dan user-space:
  1. **Submission Queue (SQ)**: Aplikasi menaruh request I/O tanpa context switch.
  2. **Completion Queue (CQ)**: Kernel menuliskan hasil operasi I/O setelah selesai.
- Model ini meminimalisir `syscall overhead` ke angka mendekati nol melalui opsi `IORING_SETUP_SQPOLL`.

### 3.4. High-Performance Networking: Ring Buffers, SoftIRQ, dan NAPI
Alur penerimaan paket berkecepatan tinggi (10G/40G/100G+) beroperasi sebagai berikut:
1. Frame tiba di Network Interface Card (NIC) $\rightarrow$ disimpan di DMA RX Ring Buffer.
2. NIC memicu **Hard IRQ** ke CPU core.
3. CPU menghentikan instruksi aktif, menjalankan IRQ handler, menonaktifkan interrupt NIC, dan menjadwalkan **SoftIRQ** (`NET_RX_SOFTIRQ`).
4. **NAPI (New API)** polling loop mengambil alokasi sk_buff (`skb`) secara batch dari ring buffer tanpa interupsi hardware berulang.
5. SoftIRQ menyerahkan paket ke subsistem TCP/IP: routing, conntrack filtering, TCP state machine, hingga disalin ke socket buffer (`SO_RCVBUF`).
6. Jika SoftIRQ mendominasi siklus CPU core tertentu, thread `ksoftirqd/X` akan mengalami saturasi 100%, memicu *packet drop* pada level ring buffer (`rx_dropped`).

---

## 4. Why & What

| Dimensi | Konfigurasi Default Linux (Out-of-the-Box) | Konfigurasi Enterprise Hardened |
| :--- | :--- | :--- |
| **Target Workload** | Komputasi umum desktop/laptop, server serbaguna dengan beban rendah. | Database throughput tinggi, FinTech core, API Gateway (100k+ RPS). |
| **TCP Conntrack** | Tabel kecil (~65.536 entri). Cepat saturasi dan *drop packets* saat terjadi lonjakan trafik. | Skala besar (1-2M+ entri), hash sizing proporsional, timeout TCP agresif. |
| **Memory Allocation** | Aggressive overcommit (`vm.overcommit_memory=0`), kswapd konservatif. | Controlled allocation, explicit swap tuning, proteksi dari blocking direct-reclaim. |
| **I/O Scheduling** | Generic multi-queue (`mq-deadline` atau `bfq`). | Low-latency scheduler (`none` untuk hardware NVMe modern, passthrough mode). |
| **CPU Affinity** | Default CFS floating scheduling, rentan cache-miss & NUMA cross-traffic. | Pinning thread kritis (NUMA aware), isolating cores via `isolcpus` / `cgroups`. |
| **Observability** | Log teks statis (`/var/log/messages`, `dmesg`), metrics aggregat (`top`). | eBPF in-kernel programmable instrumentation, profiling CPU/off-CPU via tracepoints. |

---

## 5. How (Workflow Detail)

Siklus diagnosa dan optimasi sistem Linux produksi mengikuti pipeline standar berikut:

```
[1. DETEKSI METRIK MASALAH]
      │  Contoh: p99 Latency Spikes terdeteksi di Datadog/Prometheus
      ▼
[2. ISOLASI LAYER (Kernel vs User-space)]
      │  Jalankan: vmstat 1, mpstat -P ALL 1, sar -n DEV 1
      ├─► SoftIRQ tinggi (%soft)? ──► [3A. Profiling Network IRQ / Core Binding]
      ├─► Wait I/O tinggi (%iowait)? ─► [3B. Analisis Block I/O & Dirty Throttling]
      └─► System time (%sys) tinggi? ─► [3C. Analisis Lock Contention / Syscalls]
      ▼
[3. DEEP DIVE DENGAN eBPF & PERF]
      │  bpftrace / perf record -F 99 -g -p <PID> -- sleep 10
      │  Identifikasi off-cpu latency, runqueue latency, slab allocator latency
      ▼
[4. IMPLEMENTASI TUNING KERNEL DETERMINISTIK]
      │  Penyesuaian konfigurasi via sysctl, cgroups v2, dan ethtool
      ▼
[5. AUDIT & VALIDASI REGRESI]
      │  Stress testing terisolasi (k6, wrk2, fio)
      ▼
[6. STANDARDISASI INFRASTRUCTURE AS CODE]
         Persistensi ke /etc/sysctl.d/, systemd slices, kernel boot params (GRUB)
```

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi NUMA vs SMP
Bayangkan sebuah kantor dengan dua departemen (Socket 0 dan Socket 1):
- **NUMA Local Access**: Anda mengambil berkas dari laci meja sendiri. Cepat, instan, tanpa hambatan (~60 ns).
- **NUMA Remote Access**: Anda harus berjalan melewati jembatan koridor sempit antar-gedung (UPI Bus) untuk mengambil berkas di laci meja rekan kerja di departemen lain. Ini memakan waktu 3x lebih lama dan menciptakan antrean di jembatan koridor tersebut jika semua orang melakukannya secara bersamaan.

### 6.2. Diagram Packet Processing & Bottleneck Vulnerability

```
Hardware Layer         Kernel Layer                           User Space
+-------------+        +----------------------------------+   +-------------------+
|  100GbE NIC |        |  CPU Core (SoftIRQ Context)      |   |  Application      |
|             |        |                                  |   |                   |
|  +-------+  |  DMA   |  +------------+   +-----------+  |   |  +-------------+  |
|  |RX Ring|──┼───────┼─►|sk_buff Alloc|──►|TCP Stack  |──┼──►|  |Read Socket  |  |
|  |Buffer |  |        |  +------------+   |Processing |  |   |  |Buffer Queue |  |
|  +-------+  |        |        │          +-----------+  |   |  +-------------+  |
+-------------+        +────────┼─────────────────────────+   +-------------------+
       ▲                        │
       │                        ▼
[CRITICAL BOTTLENECK 1]  [CRITICAL BOTTLENECK 2]
Ring Buffer Overflow     SoftIRQ Saturation / Core 0 Throttling
Tanda:                   Tanda:
ethtool -S rx_dropped    mpstat: %soft = 100% pada CPU0
Solusi:                  Solusi:
Perbesar ring buffer,    RPS/RFS, Receive Side Scaling (RSS),
irqbalance pinning.      ethtool -L eth0 combined <N>
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: eBPF One-Liner Trace Profiling
Mendeteksi apakah sistem mengalami disk block I/O latency tinggi secara instan menggunakan `bpftrace`:

```bash
# Menampilkan histogram distribusi waktu eksekusi I/O pada block layer (dalam microsecond)
sudo bpftrace -e 'kprobe:blk_account_io_done { @[kstack] = count(); }'
```

Histogram latensi I/O disk real-time:
```bash
sudo bpftrace -e '
tracepoint:block:block_rq_issue {
    @start[args->dev, args->sector] = nsecs;
}
tracepoint:block:block_rq_complete {
    $start = @start[args->dev, args->sector];
    if ($start) {
        @usecs = hist((nsecs - $start) / 1000);
        delete(@start[args->dev, args->sector]);
    }
}'
```

### 7.2. Practical Example: Enterprise Linux Hardening & Tuning Configuration
File implementasi produksi baseline untuk server enterprise (Node: 128 Core, 512GB RAM, Dual 25GbE Bonded NIC, High Load NVMe).

Simpan sebagai `/etc/sysctl.d/99-enterprise-production.conf`:

```ini
# ==============================================================================
# ENTERPRISE LINUX KERNEL OPTIMIZATION PROFILE
# Target: High-Concurrency Low-Latency Microservices & Database Tier
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. VIRTUAL MEMORY & DIRTY PAGE CONTROL
# ------------------------------------------------------------------------------
# Persentase total RAM sistem di mana dirty pages mulai ditulis ke storage
# oleh background thread (kswapd/flusher). Diset rendah agar I/O write konsisten.
vm.dirty_background_ratio = 5

# Persentase RAM sistem di mana write process diblokir (direct flushing) hingga data tertulis.
# Mencegah memory flooding oleh dirty pages masif.
vm.dirty_ratio = 10

# Waktu interval flush dirty pages (dalam 1/100 detik). 500 = 5 detik.
vm.dirty_writeback_centisecs = 500
vm.dirty_expire_centisecs = 3000

# Minimalisasi kecenderungan kernel melakukan swapping anonymous memory jika page cache masih tersedia.
vm.swappiness = 10

# Tingkatkan watermark scale factor untuk mencegah direct reclaim mendadak saat microburst memory allocation.
# 200 = 2% dari total memory dijadikan gap buffer.
vm.watermark_scale_factor = 200

# Jangan overcommit memory sembarangan pada server database (PostgreSQL/Redis)
vm.overcommit_memory = 0
vm.overcommit_ratio = 50

# Tingkatkan batas memory mapping limit untuk thread execution JVM / distributed engines
vm.max_map_count = 1048576

# ------------------------------------------------------------------------------
# 2. NETWORK SUBSYSTEM: CONCURRENCY & CONNECTION TRACKING
# ------------------------------------------------------------------------------
# Batas antrean connection requests yang belum diaksep (SYN queue listen socket backlog)
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# Maksimum sk_buff yang diantrekan pada input NIC sebelum diserahkan ke CPU
net.core.netdev_max_backlog = 100000

# Skala memori TCP Buffer (min, default, max) dalam satuan bytes
# Max: 16MB untuk throughput tinggi pada bandwidth delay product (BDP) besar
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Port range alokasi ephemeral sockets
net.ipv4.ip_local_port_range = 10240 65535

# TCP Socket Behavior
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2

# Aktifkan algoritma congestion control modern (BBR)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# TCP Keepalive Tuning
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 5

# ------------------------------------------------------------------------------
# 3. FILE SYSTEM & SYSTEM CAPACITY
# ------------------------------------------------------------------------------
# Global system-wide file descriptor limit
fs.file-max = 20971520

# Maksimum asynchronous concurrent I/O operations (AIO)
fs.aio-max-nr = 1048576

# Event tracing limits
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 8192
```

Terapkan langsung tanpa reboot:
```bash
sudo sysctl --system
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1. Masalah: Latency Spikes $p99.9$ pada Payment Clearing Engine (500.000 RPS)
* **Konteks**: Layanan payment gateway mengalami timeout acak ($> 1500\text{ ms}$) setiap beberapa menit pada kluster Kubernetes.
* **Metrik Awal**:
  * Rata-rata utilisasi CPU seluruh server hanya $35\%$.
  * Rata-rata alokasi RAM $45\%$.
  * Network bandwidth normal ($2\text{ Gbps}$ dari link $25\text{ Gbps}$).

### 8.2. Root Cause Analysis (RCA) via Tracing
1. **Analisis CPU Throttling**:
   Melalui cgroups v2 metrik di `/sys/fs/cgroup/system.slice/.../cpu.stat`, ditemukan nilai `nr_throttled` bertambah secara konsisten jutaan siklus meskipun CPU node tidak penuh.
   * *Diagnosa*: Konfigurasi `cpu.max` (CFS bandwidth control) pada container terlalu ketat dengan period $100\text{ ms}$. Thread burst mengeksekusi quota dalam $10\text{ ms}$ awal, kemudian di-freeze oleh kernel selama $90\text{ ms}$ berikutnya.
2. **Analisis SoftIRQ Core Saturation**:
   Eksekusi `mpstat -P ALL 1` mengungkap bahwa `CPU 0` mengalami $100\%$ `%soft`, sedangkan 127 CPU core lainnya idle dari SoftIRQ.
   * *Diagnosa*: Interrupt NIC physical eth0 dialokasikan secara eksklusif ke CPU 0 tanpa Receive Side Scaling (RSS) dan tanpa multiqueue balancing.
3. **Analisis Memory Direct Reclaim Latency**:
   Menggunakan `bpftrace`:
   ```bash
   sudo bpftrace -e 'kprobe:__alloc_pages_direct_compact { @start[tid] = nsecs; }
   kretprobe:__alloc_pages_direct_compact /@start[tid]/ {
       @latency_us = hist((nsecs - @start[tid]) / 1000);
       delete(@start[tid]);
   }'
   ```
   Ditemukan tail latency di atas $800\text{ ms}$ akibat *Direct Memory Compaction* dan *Reclaim* karena alokasi HugePages tanpa background buffer yang cukup.

### 8.3. Solusi Arsitektural & Hasil Eksekusi
1. **Penerapan Multi-Queue NIC & IRQ Affinity**:
   ```bash
   # Aktifkan 16 channels queue pada NIC
   sudo ethtool -L eth0 combined 16
   # Distribusikan IRQ secara merata via script atau irqbalance
   sudo systemctl restart irqbalance
   ```
2. **Eliminasi CFS Quota Throttling**:
   Menghapus hard quota pada pod berlatensi kritis (`limits.cpu` dihapus, hanya menggunakan `requests.cpu` dengan isolasi static CPU manager pool Kubernetes).
3. **Penyelarasan NUMA Node Memory Allocation**:
   Aplikasi diikat (*pinned*) menggunakan `numactl` ke socket lokal terdekat dengan interface NVMe controller dan PCIe NIC:
   ```bash
   numactl --cpunodebind=0 --membind=0 /opt/engine/payment-service
   ```
4. **Hasil**:
   - $p99$ Latency turun dari $1500\text{ ms}$ menjadi $2.4\text{ ms}$.
   - Packet drops pada NIC (`rx_dropped`) turun ke $0$.
   - CPU throttling rate mencapai $0\%$.

---

## 9. Trade-offs

| Pendekatan/Optimasi | Keuntungan (+ / Pro) | Biaya & Konsekuensi (- / Con) |
| :--- | :--- | :--- |
| **`vm.swappiness = 0`** | Mencegah pembacaan disk swap yang lambat secara paksa. | Mempercepat aktivasi OOM (Out-of-Memory) Killer saat Page Cache habis dan memory spiking mendadak. Direkomendasikan nilai `1` - `10`. |
| **Transparent Huge Pages (THP) = `always`** | Menurunkan Translation Lookaside Buffer (TLB) miss; mempercepat komputasi intensif CPU masif. | Menyebabkan jitter latensi signifikan (*memory compaction pauses*) pada database memory-bound seperti Redis, MongoDB, dan PostgreSQL. Direkomendasikan `madvise`. |
| **TCP BBR Congestion Control** | Memaksimalkan throughput pada high-latency / lossy network link secara dramatis dibanding Reno/Cubic. | Menjadi sangat agresif dalam perebutan alokasi antrean buffer switch terhadap koneksi model Cubic konvensional; memakan overhead CPU sedikit lebih tinggi. |
| **I/O Polling (`IORING_SETUP_SQPOLL`)** | Sub-microsecond latency I/O; nol system call overhead. | Membutuhkan 1 dedicated kernel thread yang mengonsumsi 100% dari 1 CPU core secara konstan hanya untuk polling I/O queues. |
| **Aggressive IRQ Affinity (Core Pinning)** | Menghilangkan cache-line invalidation antar CPU core; performa thread deterministik. | Mengurangi fleksibilitas kernel scheduler untuk menyeimbangkan beban multi-tasking umum; risiko core over-saturation jika beban terkonsentrasi. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Mengabaikan TCP Listen Drop Silent Failures
* **Gejala**: Klien mengalami *connection timeout*, namun server CPU dan memory masih rendah.
* **Akar Masalah**: Nilai `net.core.somaxconn` besar, namun parameter backlog aplikasi di fungsi `listen(fd, backlog)` bernilai default (misal: 128 di Python/Node.js). Jika laju koneksi tinggi, TCP backlog meluap.
* **Deteksi**:
  ```bash
  # Cek overflow socket drops
  netstat -s | grep -i "listen"
  # atau
  ss -lnt '( sport = :8080 )'
  # Perhatikan Send-Q vs Recv-Q. Jika Recv-Q > Send-Q, koneksi sedang di-drop!
  ```
* **Solusi**: Tingkatkan nilai backlog aplikasi runtime dan `net.core.somaxconn` secara paralel.

### Mistake 2: Conntrack Table Exhaustion
* **Gejala**: Server tiba-tiba menolak paket TCP baru (`kernel: nf_conntrack: table full, dropping packet`).
* **Deteksi**:
  ```bash
  cat /proc/sys/net/netfilter/nf_conntrack_count
  cat /proc/sys/net/netfilter/nf_conntrack_max
  ```
* **Solusi**:
  ```bash
  sudo sysctl -w net.netfilter.nf_conntrack_max=2097152
  sudo sysctl -w net.netfilter.nf_conntrack_buckets=524288
  ```

### Mistake 3: Kesalahan Setting `vm.overcommit_memory = 2` Tanpa Swap Cukup
* **Gejala**: `malloc()` gagal dengan error `Cannot allocate memory` padahal memori bebas terlihat masih besar di `free -m`.
* **Akar Masalah**: Mode 2 membatasi total alokasi memori secara ketat:
  $$\text{Commit Limit} = (\text{RAM} \times \text{overcommit\_ratio}) + \text{Swap}$$
  Jika swap dinonaktifkan ($0$), aplikasi tidak dapat mengalokasikan memori melebihi persentase rasio RAM.
* **Solusi**: Gunakan mode `0` (heuristic default) atau berikan ukuran swap space yang memadai sebelum mengaktifkan mode strict overcommit.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Storage Scheduler**: Verifikasi block scheduler untuk disk NVMe diset ke `none` guna memotong layer antrean yang tidak diperlukan:
   ```bash
   echo none | sudo tee /sys/block/nvme0n1/queue/scheduler
   ```
2. [ ] **Transparent Huge Pages (THP)**: Setel ke `madvise` pada host yang menjalankan Database:
   ```bash
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
   ```
3. [ ] **File Descriptor Limits**: Konfigurasikan ulimit pengguna sistem di `/etc/security/limits.d/99-nofile.conf`:
   ```ini
   *       soft    nofile  1048576
   *       hard    nofile  1048576
   root    soft    nofile  1048576
   root    hard    nofile  1048576
   ```
4. [ ] **Ring Buffer NIC Capacity**: Tingkatkan RX/TX ring buffers interface fisik ke batas maksimal:
   ```bash
   sudo ethtool -G eth0 rx 4096 tx 4096
   ```
5. [ ] **CPU Governor**: Ubah power governor dari `powersave` atau `ondemand` menjadi `performance` untuk mematikan frequency scaling latency:
   ```bash
   echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
   ```
6. [ ] **TCP Keepalive**: Pastikan TCP keepalive di-tune untuk mendeteksi *dead peers* lebih awal pada proxy layer (Envoy/HAProxy/Nginx).

---

## 12. Hands-on Practice

Buat direktori dan simpan seluruh skrip latihan pada struktur: `hands-on/m02/`

```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 1: Eksplorasi Topologi NUMA Sistem
Buat skrip `hands-on/m02/01_numa_inspect.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== MEMORY TOPOLOGY AUDIT ==="
numactl --hardware

echo -e "\n=== NUMA HIT/MISS RATIO ==="
numastat -c

echo -e "\n=== LATENCY MATRIX ==="
cat /sys/devices/system/node/node0/distance || true
```
Jalankan:
```bash
chmod +x 01_numa_inspect.sh
./01_numa_inspect.sh
```

### Langkah 2: Observasi Latensi Scheduling Runqueue dengan eBPF
Buat skrip `hands-on/m02/02_runqlat.bt`:

```bpftrace
#!/usr/bin/env bpftrace
/*
 * 02_runqlat.bt - Mengukur latency antrean CPU CFS Scheduler
 * Satuan: Microseconds (us)
 */

BEGIN {
    printf("Tracing CPU scheduler runqueue latency... Hit Ctrl-C to end.\n");
}

tracepoint:sched:sched_wakeup,
tracepoint:sched:sched_wakeup_new {
    @qtime[args->pid] = nsecs;
}

tracepoint:sched:sched_switch {
    if (@qtime[args->next_pid]) {
        $latency = (nsecs - @qtime[args->next_pid]) / 1000;
        @usecs = hist($latency);
        delete(@qtime[args->next_pid]);
    }
}

END {
    clear(@qtime);
}
```
Jalankan skrip selama 10 detik di bawah load:
```bash
sudo chmod +x 02_runqlat.bt
sudo ./02_runqlat.bt
```

### Langkah 3: Setup cgroups v2 Isolasi Sumber Daya Eksplisit
Buat skrip `hands-on/m02/03_cgroup_isolation.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

CGROUP_PATH="/sys/fs/cgroup/prod-workload.slice"

echo "1. Membuat control group v2 slice..."
sudo mkdir -p "${CGROUP_PATH}"

echo "2. Membatasi memory limit maksimal (4GB) dan swap (0)..."
echo "4294967296" | sudo tee "${CGROUP_PATH}/memory.max"
echo "0" | sudo tee "${CGROUP_PATH}/memory.swap.max"

echo "3. Membatasi CPU Quota (2 CPU Core Maksimum = 200000us per 100000us period)..."
echo "200000 100000" | sudo tee "${CGROUP_PATH}/cpu.max"

echo "4. Cgroup terkonfigurasi pada: ${CGROUP_PATH}"
ls -la "${CGROUP_PATH}"
```
Jalankan skrip:
```bash
chmod +x 03_cgroup_isolation.sh
./03_cgroup_isolation.sh
```

---

## 13. Exercise

### Level: Easy
1. Tulis sebuah command bash satu baris menggunakan `ss` untuk menampilkan semua socket TCP berstatus `CLOSE-WAIT` beserta process ID (PID) yang menahannya.
2. Identifikasi scheduler I/O disk aktif pada sistem Anda untuk block device root (`/dev/sda` atau `/dev/nvme0n1`).

### Level: Medium
1. Sebuah server web mengalami lonjakan load `ksoftirqd/X` pada Core 0 hingga 100%, sementara Core 1-7 idle. Tuliskan langkah perbaikan deterministik menggunakan `ethtool` dan interface driver balancing untuk mendistribusikan SoftIRQ load ke seluruh Core yang tersedia.
2. Buat skrip Bash yang memonitor pertumbuhan `/proc/net/dev` dan memicu alert jika nilai metrik `rx_fifo_errors` atau `rx_dropped` mengalami peningkatan lebih dari 100 frame per 5 detik.

### Level: Hard
1. Buat program tracing berbasis `bpftrace` yang melacak latency pemanggilan system call `futex` (wait/wake) per thread ID (`tid`) dan tampilkan histogram distribusi latensinya untuk proses dengan nama binary `mysqld` atau `postgres`.
2. Konfigurasikan systemd service override untuk sebuah aplikasi intensif I/O agar berjalan di dalam dedicated CPU core isolasi (Core 2-3 saja) dan terikat secara memory-binding pada NUMA Node 0.

---

## 14. Challenge

### Skenario Kasus: The Multi-Tier NVMe & TCP Starvation Mystery
Anda ditugaskan mengaudit instance bare-metal production dengan spesifikasi:
- 2x AMD EPYC 9654 (192 Cores, 384 Threads total)
- 1.5 TB DDR5 ECC RAM (Terbagi ke dalam 2 NUMA Node)
- 4x 3.84TB NVMe SSD U.2 RAID 0 (Hardware stripe)
- 2x 100 GbE Mellanox ConnectX-6 NIC (Bonding LACP 802.3ad)

**Permasalahan Teramati**:
Database key-value in-memory terdistribusi mengeksekusi operasi baca-tulis disk asinkron berkecepatan tinggi. Ketika throughput mencapai $3.200.000$ IOPS dan network ingress menyentuh $45\text{ Gbps}$:
1. **Masalah A**: Latensi write disk melonjak dari normal $80\,\mu\text{s}$ menjadi $450\text{ ms}$ secara periodik setiap 30 detik.
2. **Masalah B**: Network stack mulai mencatat ribuan `TCP: drop open request from...` pada `dmesg`.
3. **Masalah C**: Load average sistem melompat ke angka $> 400$, padahal CPU utilization riil (`%usr + %sys`) berada di bawah $20\%$. Nilai `%iowait` mendekati nol, namun `%sys` menunjukkan fluktuasi tajam.

**Tugas Anda**:
Rancang dokumen arsitektur dan investigasi sistem (Format RFC Engineering) yang mengidentifikasi:
1. Kemungkinan benturan antara alokasi dirty pages kernel (`dirty_ratio`), flush pipeline, dan saturation memory cross-NUMA interconnect.
2. Analisis korelasi status Load Average tinggi tanpa CPU/IOWait tinggi (Petunjuk: *Uninterruptible Sleep Task Contention* pada kernel lock / futex / page lock).
3. Parameter konfigurasi lengkap kernel (`sysctl`), driver (`mlx5_core`, NVMe options), cgroups v2 resource controller, dan affinity balancing untuk memulihkan performa sistem ke status sub-millisecond deterministik.

*(Tantangan ini membutuhkan riset mendalam mengenai Kernel Memory Locking, Lockless Networking, dan Ring Buffer tuning tingkat lanjut).*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Apa perbedaan fungsional utama antara `SoftIRQ` (`ksoftirqd`) dan `Hard IRQ` pada arsitektur pemrosesan paket jaringan Linux?
2. Mengapa nilai metrik Load Average Linux dapat bernilai tinggi padahal utilisasi CPU (CPU usage) terhitung rendah?
3. Parameter `sysctl` manakah yang mengatur ambang batas ukuran buffer TCP Receive Window maksimal pada Linux Network Stack?
4. Apa fungsi utama algoritma `mq-deadline` pada subsystem Block Layer Linux?
5. Mengapa Transparent Huge Pages (THP) sering disarankan untuk dimatikan atau diset ke status `madvise` pada server basis data seperti PostgreSQL atau Redis?

### 15.2. Pertanyaan Intermediate
6. Jelaskan bagaimana mekanisme *Direct Reclaim* bekerja saat konsumsi memori mencapai batas `WMARK_MIN`, dan apa dampaknya secara langsung terhadap performa aplikasi user-space?
7. Bagaimana `io_uring` mengeliminasi overhead context switch antara kernel space dan user space secara struktural jika dibandingkan dengan POSIX `read()`/`write()` atau `epoll()`?
8. Bagaimana pengaruh pembatasan CPU quota pada cgroups v2 (`cpu.max`) terhadap fenomena CFS Throttling pada pod container microservices?
9. Mengapa arsitektur NUMA Node traversal (mengakses remote memory melalui inter-socket link) menyebabkan degradasi performa komputasi berlatensi rendah?
10. Pada network stack Linux, apa peran dari NAPI (New API) polling loop dan dalam kondisi apa NAPI beralih dari interrupt mode ke polling mode?

### 15.3. Skenario Kasus Produksi
11. **Skenario Kasus 1**:
    Sebuah web server Nginx melaporkan error log `1024: Too many open files` padahal Anda telah menetapkan `fs.file-max = 2097152` di `/etc/sysctl.conf`. Jelaskan di mana letak akar permasalahan layer konfigurasi ini dan sebutkan 2 tempat lain yang harus diperbaiki.
12. **Skenario Kasus 2**:
    Aplikasi basis data memproses write transaction yang sangat cepat ke disk NVMe. Setiap 10-15 detik, aplikasi berhenti merespons selama 2-3 detik. Metrik monitoring menunjukkan `Dirty Memory` merangkak naik sampai menyentuh batas tertentu, lalu drop tajam bersamaan dengan berhentinya respons sistem. Konfigurasi `sysctl` apa yang salah dan bagaimana cara memulihkannya?
13. **Skenario Kasus 3**:
    Koneksi jaringan masuk ke server API ditolak secara massal pada saat peak traffic. Saat diperiksa, utilisasi memori dan CPU masih sangat longgar. Output `dmesg` menampilkan: `nf_conntrack: table full, dropping packet`. Jika sistem ini tidak boleh di-restart dan tidak boleh mematikan firewall (`iptables`/`nftables`), tuliskan langkah perbaikan mitigasi langsung di runtime shell Linux!

---

### Kunci Jawaban Evaluasi

#### Jawaban Basic
1. **Hard IRQ** dieksekusi secara instan oleh CPU saat menerima sinyal hardware, menonaktifkan interrupt lain sementara untuk menyimpan status paket ke RAM/DMA, dan sifatnya sangat singkat. **SoftIRQ** adalah kelanjutan asinkron di kernel context untuk memproses logika berat (TCP/IP checksum, protocol validation) tanpa menahan interrupt hardware CPU.
2. Linux Load Average tidak hanya menghitung task dalam status Running/Runnable (`R`), tetapi juga task dalam status **Uninterruptible Sleep (`D`)**, seperti proses yang tertahan menunggu I/O disk, network wait, atau perolehan lock kernel (`down_read`/mutex).
3. `net.ipv4.tcp_rmem` (khususnya nilai ketiga/maksimum) dan `net.core.rmem_max`.
4. Mencegah starvation antrean I/O dengan mengelompokkan request write dan read, menerapkan batas deadline toleransi eksekusi sebelum starvation terjadi, sambil tetap memanfaatkan parallel submit queues hardware SSD.
5. Karena THP membagi memori ke dalam block 2MB secara dinamis. Jika alokasi memory tersebar (sparse) dan fragmented, kernel akan memicu *compaction worker* sinkron yang mengunci thread memory, menimbulkan lonjakan latensi jutaan microsecond (*latency spikes*).

#### Jawaban Intermediate
6. Direct Reclaim dipicu ketika `kswapd` gagal mengimbangi laju alokasi memori dan kapasitas bebas anjlok menembus `WMARK_MIN`. Alih-alih background flush, proses user-space yang sedang meminta alokasi memori akan dibekukan (*stalled*) dan dipaksa oleh kernel untuk membersihkan/menulis dirty memory ke storage sebelum alokasi baru diizinkan.
7. `io_uring` mengimplementasikan dua ring buffer (Submission Queue dan Completion Queue) di dalam *shared memory* antara kernel dan aplikasi user-space. Aplikasi menulis request ke antrean tanpa system call; kernel memprosesnya dan menulis response langsung ke completion ring. Jika mode `SQPOLL` aktif, context switch turun ke nol.
8. CFS Quota membagi alokasi CPU ke dalam siklus periodik (default: 100ms). Jika kuota waktu CPU sebuah container habis sebelum period berakhir (misal habis dalam 15ms awal akibat microburst concurrency), kernel menunda (*throttle*) seluruh thread container tersebut hingga siklus periodik 100ms berikutnya dimulai.
9. Remote NUMA traversal dibatasi oleh kapasitas throughput dan latensi bus penghubung (Intel UPI / AMD Infinity Fabric). Mengakses RAM di socket lain menambah latensi bus (bisa mencapai 2x-3x lipat dibanding local access) serta menciptakan antrean (*bus contention*) jika kedua socket saling bertukar data cache-line secara simultan.
10. NAPI mematikan Hard IRQ setelah paket pertama tiba di ring buffer, lalu kernel beralih ke mode *polling* teratur melalui SoftIRQ untuk menyerap paket secara batch. Ini mencegah *interrupt storm* (jutaan interrupt per detik yang dapat melumpuhkan CPU core).

#### Jawaban Skenario Kasus Produksi
11. **Akar Masalah**: `fs.file-max` adalah batas global kernel secara sistemik, bukan batas per-proses.
    **Dua Layer yang Harus Diperbaiki**:
    - Limits SystemD Service: Tambahkan `LimitNOFILE=1048576` pada unit file service Nginx (`/etc/systemd/system/nginx.service.d/override.conf`).
    - User PAM Limits: Konfigurasikan batas soft dan hard `nofile` di `/etc/security/limits.conf` untuk user `nginx`/`www-data`.
12. **Akar Masalah**: Nilai `vm.dirty_ratio` terpasang terlalu tinggi atau default (misal 20-30% dari RAM 256GB = ~50-75GB dirty data tertimbun). Ketika batas tercapai, sistem mematangkan seluruh operasi tulis dan masuk ke mode *direct writeback freeze*.
    **Solusi**:
    Turunkan batas agresif menggunakan rasio rendah atau absolute bytes:
    ```bash
    sudo sysctl -w vm.dirty_background_ratio=3
    sudo sysctl -w vm.dirty_ratio=6
    ```
    Atau tetapkan batas absolut: `vm.dirty_bytes = 1073741824` (1GB) dan `vm.dirty_background_bytes = 536870912` (512MB).
13. **Mitigasi Langsung di Runtime**:
    Perbesar kapasitas tabel conntrack dan ukuran bucket hash langsung ke kernel virtual filesystem tanpa restart:
    ```bash
    # 1. Gandakan ukuran hash table bucket (misal ke 524288)
    echo 524288 | sudo tee /sys/module/nf_conntrack/parameters/hashsize
    # 2. Gandakan max tracking capacity
    sudo sysctl -w net.netfilter.nf_conntrack_max=2097152
    # 3. Turunkan TCP timeout connection agar tracking entries cepat dibersihkan
    sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600
    sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_close_wait=10
    ```

---

## 16. Summary

1. **Kernel Subsystems Interdependence**: Performa sistem enterprise ditentukan oleh keselarasan antara CPU scheduling (CFS), Virtual Memory management, Block I/O, dan Network processing. Kegagalan optimasi di satu layer (misal: TCP buffer bloat) akan berdampak pada layer lain (peningkatan memory direct-reclaim).
2. **Deterministic Latency**: Menghilangkan jitter latensi tingkat tinggi ($p99.9$) membutuhkan konfigurasi eksplisit: menonaktifkan CFS Quota hard-throttling pada workload sensitif, menyelaraskan alokasi thread dan memori dengan NUMA boundaries, serta menghindari alokasi dirty memory yang terlalu longgar.
3. **Observability Modern**: Monitoring tradisional (`top`, `iostat`) menyamarkan degradasi performa dalam angka agregat rata-rata. Pemecahan masalah kernel modern membutuhkan instrumentasi tracing dinamis berbasis **eBPF** (`bpftrace`, `perf`) untuk menganalisis waktu tunggu runqueue, lock contention, dan off-CPU execution stack secara real-time.
4. **Architectural Hardening**: Konfigurasi default distribusi Linux ditujukan untuk skenario kompatibilitas umum. Lingkungan produksi berkecepatan tinggi menuntut standarisasi via kernel boot parameters, persistensi tuning `/etc/sysctl.d/`, cgroups v2, dan network stack multiqueue distribution.