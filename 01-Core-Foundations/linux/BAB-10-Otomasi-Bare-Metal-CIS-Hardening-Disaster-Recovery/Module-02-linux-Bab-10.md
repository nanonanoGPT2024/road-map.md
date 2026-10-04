# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Linux Enterprise

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Arsitektur Kernel Tingkat Rendah:** Membedah interaksi antara Virtual File System (VFS), memory management subsystem (SLUB/Buddy Allocator), scheduler (EEVDF/CFS), dan networking stack berbasis interrupt/softirq.
2. **Merancang Sistem Isolasi Berbasis cgroups v2 & Namespaces:** Mengonfigurasi kontrol resource terpadu (Unified Hierarchy) untuk CPU, Memory, I/O, dan PIDs tanpa runtime container pihak ketiga.
3. **Mengimplementasikan High-Performance I/O & Networking:** Mengoptimalkan throughput dan meminimalisir tail-latency menggunakan arsitektur non-blocking asynchronous `io_uring` serta programmable packet processing berbasis eBPF/XDP.
4. **Melakukan Kernel Tuning Berbasis Profiling Telemetri:** Mengeliminasi bottle-neck latensi subsistem memori (kswapd, dirty page writeback, NUMA page migration) dan network ring buffer berbasis metrik dari `perf`, `bpftrace`, dan `/proc/`.
5. **Mitigasi Masalah Skala Enterprise:** Mendiagnosis dan menyelesaikan masalah degradasi performa akut, seperti CFS quota throttling, lock contention, memory fragmentation, dan softirq starvation pada server bare-metal multi-terabyte dan high-core count.

---

## 2. Prerequisite

Peserta diasumsikan telah memiliki pemahaman operasional berikut:
* **Penguasaan Linux System Administration:** Pengelolaan systemd, manipulasi sinyal POSIX, dan troubleshooting utilitas core OS (`strace`, `lsof`, `ip`, `ps`).
* **Pemahaman Model Eksekusi C/OS:** Memahami konsep User-Space vs Kernel-Space, Privilege Rings (Ring 0 vs Ring 3), system call boundary, stack vs heap allocation, pointer arithmetic, dan thread concurrency.
* **Jaringan Komputer Lanjutan:** Memahami siklus TCP 3-way handshake, TCP state machine, skema interrupt hardware NIC, ARP, MTU, packet queuing disciplines (qdisc), dan OSI Model L2–L4.
* **Storage Internals:** Pemahaman dasar terkait blok storage, partition schemes, direct I/O vs buffered I/O, dan storage controllers (NVMe vs SATA/SAS).

---

## 3. Concept & Internal Architecture (Mendalam)

Arsitektur Linux Enterprise berakar pada abstraksi monolitik modular di mana kernel mengontrol alokasi resource hardware terhadap instruksi perangkat lunak.

```
+-------------------------------------------------------------------------------+
|                                  USER SPACE                                   |
|   +---------------------+   +---------------------+   +-------------------+   |
|   | Enterprise Database |   | High-Throughput App |   | Production Daemon |   |
|   +---------------------+   +---------------------+   +-------------------+   |
|              |                         |                        |             |
|       (Direct IO / POSIX)         (io_uring)               (AF_XDP)           |
+--------------+-------------------------+------------------------+-------------+
|              | System Call Interface   |                        |             |
|              v                         v                        v             |
| +---------------------------------------------------------------------------+ |
| |                                KERNEL SPACE                               | |
| |                                                                           | |
| | +-------------------+  +--------------------+  +------------------------+ | |
| | |        VFS        |  |  Network Subsystem |  | Process Scheduler      | | |
| | | (Dentry, Inode,   |  | (Socket, TCP/IP,   |  | (EEVDF/CFS, Runqueues, | | |
| | |  Page Cache)      |  |  Netfilter, XDP)   |  |  Context Switch)       | | |
| | +---------+---------+  +---------+----------+  +-----------+------------+ | |
| |           |                      |                         |              | |
| | +---------v----------------------v-------------------------v------------+ | |
| | |                     Unified Memory Subsystem                          | | |
| | |  (Buddy System, SLUB Allocator, Page Tables, Active/Inactive LRU)     | | |
| | +--------------------------------+--------------------------------------+ | |
| |                                  |                                        | |
| | +--------------------------------v--------------------------------------+ | |
| | |                     Hardware Abstraction Layer                        | | |
| | |  (Block Drivers / NVMe, NIC Drivers / NAPI, Hardware Interrupts/IRQs) | | |
| | +--------------------------------+--------------------------------------+ | |
+------------------------------------+------------------------------------------+
|                                    v                                          |
| +---------------------------------------------------------------------------+ |
| |                                 HARDWARE                                  | |
| |         [ CPU Cores ]       [ NUMA RAM Nodes ]       [ NVMe / NICs ]      | |
| +---------------------------------------------------------------------------+ |
```

### A. Sub-sistem Manajemen Memori (Memory Management Subsystem)
Kernel mengalokasikan memori fisik melalui dual-layer architecture:
1. **Buddy Allocator (Page-Level Allocation):** Menangani frame memori fisik dalam kelipatan $2^n$ halaman (umumnya basis 4KB). Masalah utama di level ini adalah *external fragmentation*, yang dimitigasi melalui subsistem *memory compaction*.
2. **SLUB Allocator (Byte-Level Allocation):** Mengatur alokasi objek kecil kernel (seperti struct `task_struct`, `mm_struct`, atau socket buffer `sk_buff`). SLUB adalah evolusi dari SLAB yang meminimalisir overhead metadata dengan mengelompokkan cache ke dalam halaman fisik continuous tanpa antrean lock lokal yang redundant.
3. **Reclaim Logic & Virtual Memory Flush:** Saat free memory jatuh di bawah tanda batas `watermark[WMARK_LOW]`, kernel mendelegasikan pembersihan ke thread `kswapd`. Jika konsumsi memory melebihi `watermark[WMARK_MIN]`, aplikasi pengeksekusi akan dipaksa melakukan *direct reclaim*, menyebabkan lonjakan tail latency secara ekstrem.

### B. VFS & Dirty Page Lifecycle
Data yang ditulis melalui POSIX `write()` disimpan pada *Page Cache* sebelum dialirkan ke physical non-volatile media:
* Halaman memori diubah statusnya menjadi **Dirty**.
* Kernel worker (`kworker/flush`) mengeksekusi flush berkala berdasarkan threshold persentase memori (`dirty_background_ratio` dan `dirty_ratio`).
* Read I/O menggunakan mekanisme *readahead*, mendeteksi pola akses sequential dan memuat page ke cache sebelum diminta oleh user space.

### C. Scheduler: CFS ke EEVDF (Earliest Eligible Virtual Deadline First)
* **CFS (Completely Fair Scheduler):** Menyeimbangkan waktu runtime menggunakan virtual runtime (`vruntime`) berbasis Red-Black Tree. Kelemahannya adalah trade-off antara latensi komputasi dan throughput, serta latency tail yang tidak deterministik bagi load transaksional.
* **EEVDF (Linux Kernel >= 6.6):** Mengganti CFS murni dengan membagi alokasi waktu eksekusi berdasarkan konsep *eligibility* (apakah proses telah mengambil porsi fairness-nya) dan *deadline* (waktu toleransi keterlambatan tugas), mengeliminasi ketergantungan empiris `sched_latency_ns`.

### D. Network Subsystem: NAPI, Softirq, dan eBPF/XDP
1. **Hardware Interrupt (Hard IRQ):** NIC menerima frame ethernet, memindahkannya via DMA ke Ring Buffer Host, kemudian memicu interupsi hardware ke core CPU tertentu.
2. **NAPI Polling Loop:** Hard IRQ handler mendisposisi pemrosesan ke *Softirq* (`NET_RX_SOFTIRQ`) dan menonaktifkan interupsi hardware untuk mencegah *interrupt storm*.
3. **eBPF/XDP (eXpress Data Path):** Mengizinkan eksekusi bytecode tersertifikasi (via in-kernel verifier) langsung pada level driver NIC sebelum kernel mengalokasikan struct metadata `sk_buff`, memberikan kemampuan packet filtering berkecepatan kawat (*line-rate*).

---

## 4. Why & What

### Mengapa Konfigurasi Standar Gagal di Skala Enterprise?
Distribusi Linux enterprise (RHEL, Ubuntu Server, Debian) dikonfigurasi secara umum (*general-purpose baseline*). Konfigurasi ini:
* Memprioritaskan throughput rata-rata di atas determinisme tail-latency (P99 / P99.9).
* Mengizinkan *dirty memory* membengkak secara masif, memicu fenomena I/O freeze saat kernel terpaksa melakukan synchronous flush.
* Menggunakan dynamic CPU frequency scaling governors (seperti `powersave` atau `ondemand`) yang memperkenalkan latensi transisi voltase CPU (p-states).
* Menerapkan overcommit memory secara agresif, rentan terhadap OOM Killer yang memutus koneksi stateful database secara acak.

### Apa yang Harus Dilakukan?
Mentransformasikan host Linux menjadi deterministic engine dengan cara:
* Mengisolasi jalur I/O dan jaringan melalui bypass parsial (XDP, `io_uring`).
* Menerapkan strict NUMA alignment dan CPU core affinity pinning.
* Mengunci dirty page ratio pada batas aman untuk mengeliminasi disk-choke events.
* Memigrasikan arsitektur cgroups v1 yang terfragmentasi ke cgroups v2 Unified Tree untuk kontrol multi-resource terkoordinasi.

---

## 5. How (Workflow Detail)

Alur kerja berikut mendefinisikan implementasi sistem optimasi OS bare-metal kelas enterprise:

```
[NIC / Storage Event]
         |
         v
+------------------+     Bypass Jalur Lambat?
| Hard IRQ Trigger | ----------------------------+
+------------------+                             |
         |                                       |
         v                                       v
+------------------+                    +-------------------+
|  SoftIRQ (NAPI)  |                    | eBPF / XDP Hook   |
+------------------+                    +-------------------+
         |                                       |
         v                                       | Packet Dropped / 
+------------------+                             | Redirected via DMA
| sk_buff Allocate |                             v
+------------------+                    +-------------------+
         |                              | Zero-Copy RingBuf |
         v                              +-------------------+
+------------------+
|  TCP/IP Parsing  |
+------------------+
         |
         v
+------------------+
| Socket Buffers   |
+------------------+
         |
         v
+------------------+
| App Context Wait |
+------------------+
```

### Langkah 1: Isolasi Hardware dan Bindings (NUMA & Irqbalance)
1. Matikan daemon `irqbalance` dinamis jika server ditujukan untuk latensi deterministik tinggi.
2. Identifikasi topologi NUMA menggunakan `lstopo` atau `numactl --hardware`.
3. Ikat interrupt vector dari network interface PCIe card langsung ke NUMA node lokal yang bersesuaian menggunakan `/proc/irq/{IRQ_NUM}/smp_affinity_list`.

### Langkah 2: Konfigurasi Memory Watermarks & Dirty Pages
1. Batasi akumulasi dirty memory agar background flushing berlangsung kontinu tanpa lonjakan I/O:
   * Turunkan `vm.dirty_background_ratio` ke angka konservatif (3-5%).
   * Kunci `vm.dirty_ratio` maksimal di angka 10% atau gunakan representasi absolut bytes (`vm.dirty_background_bytes`).
2. Naikkan `vm.min_free_kbytes` untuk memberi ruang operasi alokasi memory atomik pada network driver buffer saat kondisi traffic burst.

### Langkah 3: Modernisasi IO Engine melalui io_uring
1. Gantikan paradigma asynchronous I/O tradisional (`libaio` atau epoll-based synchronous worker pools) dengan `io_uring`.
2. Gunakan sepasang ring-buffer lockless berbasis shared memory (Submission Queue / SQ dan Completion Queue / CQ) antara kernel dan user space untuk mereduksi syscall boundary context switch ke angka nol (melalui kernel polling flag `IORING_SETUP_SQPOLL`).

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Logistik Gudang
* **User-Space vs Kernel-Space:** Seperti Pembeli (User) yang dilarang masuk ke Gudang Utama (Kernel). Setiap permintaan barang harus melalui Loket Pelayanan (*System Call Interface*).
* **Direct Reclaim vs kswapd:**
  * *kswapd* adalah petugas kebersihan malam hari yang membuang kotak sampah secara bertahap saat gudang mulai terisi 70%. Operasi gudang tetap berjalan lancar.
  * *Direct Reclaim* adalah kondisi ketika gudang terisi 99%. Truk barang dilarang membongkar muatan; supir truk dipaksa turun dari kendaraan dan menyapu gudang terlebih dahulu sebelum dapat menurunkan muatannya (*tail latency spike*).
* **eBPF/XDP:** Satpam di gerbang pagar terluar gudang yang langsung memeriksa plat nomor dan menolak truk palsu di pinggir jalan tol, tanpa perlu membiarkan truk tersebut masuk ke antrean pos penimbangan (*Socket Buffer / sk_buff creation*).

### Ring Buffer & Memory Interaction Model

```
 USER SPACE                   KERNEL SPACE                       HARDWARE
+------------+       Ring Buffer Submission (SQ)              +------------+
|            |===============================================>|            |
| App Worker |               (Shared Memory)                  | NVMe / NIC |
|            |<===============================================| Controller |
+------------+       Ring Buffer Completion (CQ)              +------------+
      ^                                                             |
      |                                                             |
      +------- Direct Memory Mapping (Zero Copy via DMA) <----------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Kontrol cgroups v2 Unified Hierarchy Manual
Menyiapkan cgroup resource-limiting murni tanpa abstraksi container runtime melalui interaksi file direct interface.

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Konfigurasi hierarchy cgroups v2
CGROUP_PATH="/sys/fs/cgroup/production_workload"
sudo mkdir -p "${CGROUP_PATH}"

# 2. Aktifkan memory and cpu controller di root tree jika belum aktif
echo "+cpu +memory +io" | sudo tee /sys/fs/cgroup/cgroup.subtree_control

# 3. Tetapkan Hard Limits pada target group
# Limit memory 4GB, swap disable
echo "4294967296" | sudo tee "${CGROUP_PATH}/memory.max"
echo "0"          | sudo tee "${CGROUP_PATH}/memory.swap.max"

# Set CPU CFS quota: 2 core penuh (200000us per period 100000us)
echo "200000 100000" | sudo tee "${CGROUP_PATH}/cpu.max"

# 4. Attach session shell saat ini ke dalam cgroup
echo $$ | sudo tee "${CGROUP_PATH}/cgroup.procs"

echo "Proses $$ berjalan dalam isolasi cgroups v2:"
cat "${CGROUP_PATH}/cgroup.procs"
```

### Practical Example: Engine Tuning Produksi Linux Low-Latency & High-Throughput
Konfigurasi terpadu untuk host bare-metal database/broker kelas enterprise (e.g., Kafka / PostgreSQL / ScyllaDB) pada `/etc/sysctl.d/99-enterprise-core.conf`:

```ini
# ====================================================================
# ENTERPRISE LINUX KERNEL HARDENING & PERFORMANCE PROFILE
# target: 128 Cores, 512GB RAM, Dual 100GbE NICs, NVMe Storage
# ====================================================================

# 1. Virtual Memory & Reclaim Tuning
vm.swappiness = 1
vm.dirty_background_ratio = 3
vm.dirty_ratio = 8
vm.dirty_expire_centisecs = 1500
vm.dirty_writeback_centisecs = 300
vm.vfs_cache_pressure = 50
vm.min_free_kbytes = 4194304
vm.zone_reclaim_mode = 0
vm.max_map_count = 1048576

# 2. Network Core & Socket Buffers (BDP Tuning for 100GbE)
net.core.netdev_max_backlog = 100000
net.core.somaxconn = 65535
net.core.rmem_default = 33554432
net.core.wmem_default = 33554432
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.core.optmem_max = 2048576

# 3. TCP/IP Dynamic Auto-tuning Allocations
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_max_syn_backlog = 3240000

# 4. File Handlers & PIDs
fs.file-max = 20971520
fs.aio-max-nr = 1048576
fs.inotify.max_user_watches = 1048576
kernel.pid_max = 4194304

# 5. Core Scheduler Settings
kernel.sched_migration_cost_ns = 5000000
kernel.sched_autogroup_enabled = 0
```

Deploy program di atas dan enforce ke kernel space:
```bash
sudo sysctl --system
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Tier-1 FinTech Payment Engine (150,000 TPS)
* **Karakteristik Workload:** Stateless microservices terdistribusi terhubung ke clustered in-memory key-value store.
* **Gejala Masalah:** Rata-rata response time berada di angka 1.5ms, namun metrik P99.9 mengalami lonjakan (*spike*) sporadis hingga 800ms - 2 detik tiap 10 menit, memicu cascade timeout ke downstream payment networks.

### Root Cause Analysis (RCA) via Tracing
1. Eksekusi `perf top` dan modul `bpftrace` menunjukkan pemanggilan intensif fungsi internal `compact_zone` dan `alloc_pages_nodemask`.
2. Investigasi terhadap file `/proc/vmstat` menunjukkan pertumbuhan tajam pada counter `compact_stall` dan `pgalloc_direct`.
3. Server menggunakan Transparent Huge Pages (THP) secara `always`. Ketika memory terfragmentasi, alokasi 2MB page contiguous gagal dieksekusi secara instan, memicu proses *synchronous compaction* yang membekukan thread utama aplikasi.
4. Terjadi intervensi softirq `NET_RX` yang terpusat di Core 0 akibat konfigurasi default interrupt affinity, mendegradasi clock execution database threads yang berbagi CPU core yang sama.

### Langkah Remediasi Produksi
1. Matikan de-fragmentasi instan THP ke mode `madvise` dan hilangkan compaction synchronous:
   ```bash
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   echo defer+madvise | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
   ```
2. Dedikasikan core CPU khusus menggunakan parameter bootloader GRUB `isolcpus` dan `nohz_full` untuk worker transaksional:
   ```text
   GRUB_CMDLINE_LINUX_DEFAULT="isolcpus=2-31,34-63 nohz_full=2-31,34-63 rcu_nocbs=2-31,34-63 intel_idle.max_cstate=1 processor.max_cstate=1"
   ```
3. Distribusikan MSI-X interrupt vector NIC 100GbE secara seimbang ke seluruh CPU NUMA lokal:
   ```bash
   # Parsing file IRQ interface eth0 dan bind affinity secara afinitas bitmask
   systemctl stop irqbalance
   INTERFACE="eth0"
   IRQS=$(grep "${INTERFACE}" /proc/interrupts | awk '{print $1}' | tr -d ':')
   CORE=0
   for IRQ in $IRQS; do
       echo $CORE > /proc/irq/$IRQ/smp_affinity_list
       CORE=$(( (CORE + 1) % 16 )) # Distribusikan ke 16 core lokal NUMA-0
   done
   ```
* **Hasil Pasca-Tuning:** Tail-latency P99.9 turun dari 800ms menjadi 3.2ms secara stabil di beban puncak 150k TPS.

---

## 9. Trade-offs

| Pendekatan / Parameter | Keuntungan (Advantage) | Kerugian / Risiko (Trade-off) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **THP: `always` vs `madvise`** | Alokasi TLB (Translation Lookaside Buffer) minim miss; throughput komputasi linear naik. | Alokasi memori terblokir oleh *compaction stall*; tail latency hancur. | Gunakan `madvise` untuk DB dan latensi rendah. Gunakan `always` untuk batch data processing / HPC. |
| **`io_uring` vs Traditional POSIX IO** | Mengeliminasi system call context-switching; zero overhead throughput maksimum. | Kompleksitas debugging meningkat drastis; rentan terhadap security bugs baru di kernel tua. | Workload async intensif (Web server modern, custom storage engines, edge proxy). |
| **Polling Driver (XDP / DPDK)** | Processing jutaan paket per detik pada kawat (*line-rate wire speed*). | Core CPU 100% terserap secara eksklusif (busy-wait loop); konsumsi daya & panas maksimum. | Gateway anti-DDoS, packet capture IDS/IPS, Core Telecom Handoff. |
| **Aggressive Dirty Page Flushing** | Memori terlindungi dari freeze I/O; proses shutdown/sync instan. | Mengurangi umur baca-tulis drive SSD/NVMe (write endurance exhaustion). | Wajib untuk database ACID transaksional. Hindari untuk logging buffer temporal. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum (Anti-Patterns)
1. **Blind Copy-Pasting `sysctl.conf`:** Menyalin konfigurasi web tanpa menghitung arsitektur NUMA node, jumlah core, serta rasio bus speed PCI Express vs DRAM Bandwidth.
2. **Pengabaian CFS Quota Throttling:** Menggunakan Kubernetes CPU limit tanpa menyadari bahwa CFS quota mereset penggunaan dalam period 100ms; proses transaksional terhenti (throttled) meskipun utilisasi rata-rata CPU tampak baru mencapai 40%.
3. **Mengabaikan Softirq Starvation:** Membiarkan interrupt jaringan diurus oleh CPU 0 secara default, menyebabkan Core 0 terkunci 100% pada *si* (softirq) saat core lain berada di status *idle*.

### Troubleshooting Workflow Menggunakan Diagnostic Commands

```
Problem: Sistem Lambat / Latency Spike
  |
  +---> [vmstat 1] -----------> pgscand / allocstall > 0?
  |                                   |
  |                                   v
  |                             Direct Memory Reclaim Detected!
  |                             Solusi: Naikan vm.min_free_kbytes,
  |                                     matikan THP defrag sync.
  |
  +---> [/proc/net/softnet_stat] -> Kolom 2 (dropped) bertambah?
  |                                   |
  |                                   v
  |                             Netdev Backlog Overflown!
  |                             Solusi: Tingkatkan net.core.netdev_max_backlog.
  |
  +---> [perf top] ------------> Spinlock Contention (_raw_spin_lock-like)?
                                      |
                                      v
                                Lock Contention di Kernel.
                                Solusi: Audit NUMA balancing / Multi-queue scale.
```

#### Komando Diagnostik Kritis:
```bash
# Pantau softnet packet drop secara real-time
watch -d -n 1 'cat /proc/net/softnet_stat'

# Periksa CFS Throttling pada proses di cgroup tertentu
cat /sys/fs/cgroup/production_workload/cpu.stat

# Trace context switch latency menggunakan bpftrace
sudo bpftrace -e '
tracepoint:sched:sched_switch {
    @switch_lat[args->prev_comm] = stats(curtask->on_cpu);
}'
```

---

## 11. Best Practices (Production Checklist)

### OS & Hardware Level
- [ ] Nonaktifkan C-States dan P-States transisional pada BIOS untuk server ultra low-latency (`governor=performance`).
- [ ] Atur HugePages secara statically allocated (`hugepagesz=1G hugepages=64`) saat bootloader GRUB, alih-alih dynamic compaction.
- [ ] Sinkronisasikan Interrupt Affinity ke NUMA Node yang secara fisik memegang bus PCIe peripheral controller interface.

### Memory & Storage
- [ ] Set `vm.swappiness = 1` (tetap aktifkan swap kecil berbasis file terenkripsi untuk mencegah direct kernel allocation deadlock).
- [ ] Alokasikan `vm.min_free_kbytes` sebesar minimal 1% - 2% dari total DRAM sistem untuk memory shock absorber.
- [ ] Gunakan scheduler storage `none` atau `kyber` untuk storage drive NVMe ultra-cepat, dan tinggalkan scheduler `mq-deadline` atau `bfq` untuk media latency-sensitive.

### Network Subsystem
- [ ] Terapkan active queue discipline TCP modern: `default_qdisc = fq` dengan congestion control `tcp_congestion_control = bbr`.
- [ ] Tingkatkan ring buffer NIC ke batas maximum hardware:
  ```bash
  sudo ethtool -G eth0 rx 4096 tx 4096
  ```

---

## 12. Hands-on Practice

Target eksekusi: Implementasikan pengujian langsung dan simpan seluruh artefak konfigurasi dan script verifikasi pada direktori `hands-on/m02/`.

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### File 1: `hands-on/m02/01_cgroup_stress_isolation.sh`
Script orkestrasi isolasi proses langsung pada level sistem operasi:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/sys/fs/cgroup/perf_lab"
sudo mkdir -p "${BASE_DIR}"

# Konfigurasi isolasi memory ketat: 512MB RAM, NO Swap
echo "536870912" | sudo tee "${BASE_DIR}/memory.max"
echo "0"         | sudo tee "${BASE_DIR}/memory.swap.max"

# Konfigurasi CPU Throttling ketat: Alokasi 0.5 CPU Core (50ms per 100ms)
echo "50000 100000" | sudo tee "${BASE_DIR}/cpu.max"

echo "[INFO] cgroups v2 configured successfully at ${BASE_DIR}."
echo "[INFO] Running test workload in isolated boundary..."

# Jalankan benchmark stress di background cgroup
sudo systemd-run --slice=perf_lab.slice --scope \
  stress-ng --vm 1 --vm-bytes 400M --timeout 10s --metrics-brief

echo "[INFO] Inspecting CPU Throttling metrics post-execution:"
cat "${BASE_DIR}/cpu.stat" || true
```

### File 2: `hands-on/m02/02_io_engine_benchmark.sh`
Komparasi arsitektur I/O Asynchronous: `libaio` vs modern `io_uring`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BENCH_FILE="test_io.img"
fio --version >/dev/null 2>&1 || { echo "fio is not installed. Aborting."; exit 1; }

echo "[1/2] Benchmarking Legacy libaio Engine..."
fio --name=aio_test --filename=${BENCH_FILE} --size=1G --rw=randread \
    --ioengine=libaio --direct=1 --bs=4k --iodepth=64 --runtime=10 \
    --time_based --group_reporting --output=libaio_result.log

echo "[2/2] Benchmarking Modern io_uring Engine..."
fio --name=uring_test --filename=${BENCH_FILE} --size=1G --rw=randread \
    --ioengine=io_uring --direct=1 --bs=4k --iodepth=64 --runtime=10 \
    --time_based --group_reporting --output=io_uring_result.log

# Cleanup media
rm -f ${BENCH_FILE}

echo "=== SUMMARY RESULT ==="
echo -n "libaio IOPS: "
grep -E "IOPS=" libaio_result.log | head -n 1
echo -n "io_uring IOPS: "
grep -E "IOPS=" io_uring_result.log | head -n 1
```

### File 3: `hands-on/m02/03_trace_sched_switch.bt`
Script `bpftrace` untuk mengukur durasi sleep-to-run delay (latency runqueue scheduling):

```bpftrace
#!/usr/bin/env bpftrace

BEGIN
{
    printf("Tracing Scheduler Runqueue Latency... Hit Ctrl-C to summarize.\n");
}

tracepoint:sched:sched_wakeup
{
    @enqueue_time[args->pid] = nsecs;
}

tracepoint:sched:sched_switch
{
    $prev = args->prev_pid;
    $next = args->next_pid;

    if (@enqueue_time[$next] != 0) {
        $latency_us = (nsecs - @enqueue_time[$next]) / 1000;
        @sched_latency_us = hist($latency_us);
        delete(@enqueue_time[$next]);
    }
}

END
{
    clear(@enqueue_time);
    printf("\nExecution distribution captured (in microseconds):\n");
}
```

Jalankan hak akses eksekusi:
```bash
chmod +x hands-on/m02/*.sh hands-on/m02/*.bt
```

---

## 13. Exercise

### Level Easy
Tuliskan single bash script berlatar belakang `ethtool` untuk mengidentifikasi channel count, coalesce timer, dan memodifikasi adaptive network interrupt moderation (rx-usecs) dari network card ethernet utama server produksi Anda.

### Level Medium
Konfigurasikan unit service `systemd` bernama `secure-critical.service` yang mengalokasikan database binary ke CPU NUMA Node 1 secara utuh, memasang limit memori di 16GB dengan memory protection reserve sebesar 2GB, dan membatasi IOPS baca drive `/dev/nvme0n1` maksimum 50,000 IOPS tanpa menggunakan docker/container framework.

### Level Hard
Buat script automasi tuning berbasis shell yang membaca layout topologi hardware `/sys/devices/system/node/` kemudian secara programatis:
1. Membagi total core CPU menjadi dua kelompok: **Control Plane Cores** dan **Isolated Fast-Path Cores**.
2. Memprogram ulang `smp_affinity` seluruh interupsi PCIe NVMe dan Network ke kelompok Control Plane Cores.
3. Mengonfigurasi `cpuset.cpus` root container untuk menjamin thread komputasi payload latency-critical berjalan eksklusif pada Isolated Fast-Path Cores tanpa terinterupsi softirq dan time-slice timer kernel ticks.

---

## 14. Challenge

**Skenario Sistem:**
Anda adalah Principal Infrastructure Architect pada bursa High-Frequency Trading (HFT). Perusahaan men-deploy server bare-metal berspesifikasi:
* Dual-Socket AMD EPYC 9654 (192 Cores total, 384 Threads).
* 1.5 TB ECC DDR5 RAM.
* Dual 100Gbps Mellanox ConnectX-6 NIC.
* Workload: Message ingestion UDP Multicast non-stop 80 Juta Paket per Detik.

**Kondisi Kritis:**
Setiap kali terjadi burst likuiditas pasar, terdeteksi packet loss rata-rata 0.04% pada buffer kernel. Di ranah finansial ini, kehilangan 1 paket berarti kegagalan arbitrase order jutaan dolar. Analisis hardware membuktikan utilisasi kapasitas interface kabel optik baru menyentuh 45%. 

**Tugas Anda:**
Rancang strategi re-arsitektur bare-metal OS dari level boot parameter hingga user space. Anda dilarang mengganti hardware. Buat blue-print arsitektur komprehensif yang memuat:
1. Skema Kernel Bypass Selection (analisis AF_XDP vs RoCE vs Kernel socket bypass).
2. Cetak biru alokasi isolasi CPU Core (termasuk mitigasi RCU callback, IRQ threading, Page Allocator lock).
3. Parameter memory subsistem spesifik (huge pages, zonelist, NUMA interleaving profile).
4. Mekanisme verifikasi deterministik: Metrik apa yang Anda ukur untuk membuktikan packet loss turun menjadi 0% mutlak pada throughput puncak.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara alokasi memori fisik level Buddy Allocator dengan SLUB Allocator?**
   * *Jawaban:* Buddy Allocator mengelola alokasi memori pada granularitas halaman fisik (*page frame*, umumnya basis 4KB atau pangkat dua dari itu) untuk memitigasi eksternal fragmentasi. SLUB Allocator dibangun di atas alokasi Buddy System untuk mengelola objek-objek data kecil berukuran arbitrary di dalam kernel (seperti struct metadata `inode`, `task_struct`, atau socket) guna mengeliminasi internal fragmentasi.

2. **Mengapa nilai `vm.swappiness = 0` tidak disarankan secara absolut pada server Linux modern?**
   * *Jawaban:* Nilai 0 secara agresif melarang kernel memindahkan anonymous memory ke swap space hingga memory benar-benar mencapai threshold out-of-memory kritis. Ini dapat membatasi kemampuan kernel mereclaim memory page cache yang tidak aktif secara seimbang, berpotensi memicu sudden OOM killing padahal sistem memiliki buffer swap yang mampu menyerap lonjakan sesaat.

3. **Apa fungsi dari sistem `cgroups v2` Unified Hierarchy dibandingkan multi-hierarchy pada `cgroups v1`?**
   * *Jawaban:* cgroups v2 mengintegrasikan seluruh resource controller (CPU, Memory, I/O, RDMA) ke dalam satu pohon hirarki proses terpadu (*single unified tree*). Hal ini mengeliminasi masalah sinkronisasi lintas controller yang sering terjadi di cgroups v1 (misalnya: I/O throttling yang gagal berfungsi jika writeback memory ditangani oleh cgroup memory yang jalurnya berbeda dengan cgroup blkio).

4. **Kapan kondisi Direct Reclaim terjadi pada Linux Kernel?**
   * *Jawaban:* Direct reclaim terjadi saat alokasi memori diminta oleh sebuah proses, namun ketersediaan halaman memori bebas sistem anjlok hingga berada di bawah ambang batas kritis minimum `watermark[WMARK_MIN]`. Proses pemanggil dialihkan dari komputasi utama untuk mengeksekusi pembersihan page cache secara synchronous.

5. **Apa fungsi flag `O_DIRECT` saat membuka file descriptor storage?**
   * *Jawaban:* Flag `O_DIRECT` menginstruksikan VFS untuk mem-bypass Linux Page Cache secara langsung. Operasi transfer I/O dilakukan secara direct via DMA antara buffer user space memory dan controller block device, mengeliminasi duplikasi memory copy dan overhead dirty page cache.

---

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Mengapa implementasi `io_uring` menghasilkan throughput I/O yang signifikan lebih tinggi dibanding `epoll` + POSIX AIO?**
   * *Jawaban:* `io_uring` mengimplementasikan dua lockless ring buffer (Submission Queue dan Completion Queue) di shared memory space antara kernel dan user space. Pola ini memangkas overhead context switch instruksi system call secara repetitif. Melalui kernel side polling (`IORING_SETUP_SQPOLL`), read/write dapat diproses tanpa eksekusi syscall tambahan.

2. **Jelaskan siklus hidup Network Packet mulai dari frame tiba di NIC hingga siap dibaca aplikasi di POSIX socket.**
   * *Jawaban:* (1) NIC menerima sinyal fisik, menulis packet via DMA ke Rx Ring Buffer memory host. (2) NIC membunyikan Hardware IRQ ke CPU. (3) CPU mengeksekusi Top-Half handler, menjadwalkan Softirq `NET_RX`, dan mematikan IRQ hardware interface (NAPI mode). (4) Polling loop NAPI memanen packet dari Ring Buffer, mengalokasikan struct `sk_buff`. (5) Paket diparsing melalui stack layer network (IP, Netfilter/Iptables, TCP/UDP logic). (6) Payload diletakkan ke antrean Socket Receive Buffer. (7) Proses user space dibangunkan (*wake up*) via event socket (`epoll`/select).

3. **Bagaimana parameter kernel `vm.zone_reclaim_mode` memengaruhi server dengan arsitektur multi-socket NUMA?**
   * *Jawaban:* Jika diaktifkan (nilai > 0), kernel dipaksa mereclaim memory cache lokal pada NUMA node yang sama sebelum meminta alokasi dari NUMA node tetangga. Hal ini menjaga dependensi latensi bus UPI/QPI, namun dapat memicu direct reclaim berat dan latency stalls lokal jika zone lokal penuh meskipun memori pada node NUMA lain masih kosong melimpah. Nilai 0 (default modern) mengizinkan alokasi node tetangga.

4. **Apa indikasi teknis jika metrik `/proc/net/softnet_stat` pada kolom kedua terus mengalami inkrementasi?**
   * *Jawaban:* Kolom kedua merepresentasikan dropped frame akibat parameter `netdev_max_backlog` terlampaui. Ini terjadi ketika ring buffer NIC driver memproses frame lebih cepat daripada kemampuan sub-sistem softirq kernel mengambil dan memasukkannya ke antrean stack networking.

5. **Jelaskan mekanisme kerja algoritma CFS Quota Throttling pada container/cgroups!**
   * *Jawaban:* CFS mendefinisikan batasan CPU berdasarkan jendela waktu periode (`cpu.cfs_period_us`, default 100ms) dan batas alokasi waktu pemakaian (`cpu.cfs_quota_us`). Jika sebuah proses multi-thread menghabiskan jatah waktu kuota dalam 20ms pertama dari jendela 100ms tersebut, kernel akan memarkir (*throttle*) dan menolak penjadwalan proses tersebut selama 80ms sisanya, menghasilkan latensi P99 yang ekstrem.

---

### Bagian 3: Skenario Kasus Produksi (3 Skenario)

#### Skenario 1: The Mysterious High System CPU Load
* **Kondisi:** Server API Gateway (64 Core) menunjukkan utilisasi CPU total 90%, namun utilisasi CPU User space (`%usr`) hanya 15%, sedangkan CPU System space (`%sys`) mendominasi di angka 75%. Profiling beban I/O drive berada di level nol.
* **Pertanyaan:** Apa penyebab paling potensial dari tingginya CPU system space tersebut, alat apa yang Anda gunakan untuk mengonfirmasi, dan apa solusinya?
* **Jawaban Komprehensif:** 
  Penyebab paling potensial adalah adanya **Spinlock Contention** masif di level kernel atau alokasi resource yang memicu lock serialization (misalnya mmap contention atau file descriptor table lock). 
  * Konfirmasi: Jalankan `perf top -g` untuk melihat fungsi kernel mana yang mendominasi instruksi CPU. Jika ditemukan simbol seperti `_raw_spin_lock`, `native_queued_spin_lock_slowpath`, atau `down_read`, contention terkunci di level lock internal.
  * Solusi: Evaluasi apakah aplikasi melakukan thread spawning berlebih (thundering herd problem). Gunakan worker model berbasis event loop atau kurangi contention pada resource shared memory; isolasi jalur memori per-core atau alihkan pooling koneksi lokal.

#### Skenario 2: Asymmetric Core Exhaustion
* **Kondisi:** Sebuah cluster database distributed NoSQL berjalan pada host bare-metal. Pengawas infrastruktur mendapati Core 0 selalu berada pada 100% kapasitas secara persisten, sementara 127 core lainnya berada pada utilisasi di bawah 10%. Performa aplikasi hancur drastis.
* **Pertanyaan:** Menganalisis fenomena ini dari sudut pandang subsistem Interrupt handling Linux, apa yang terjadi dan bagaimana langkah operasional untuk menyelesaikannya secara permanen?
* **Jawaban Komprehensif:**
  Fenomena ini terjadi akibat konfigurasi default routing hardware interrupt driver peripheral (NIC atau storage HBA) yang secara eksklusif mengalirkan interupsi vector ke core CPU pertama (Core 0), mengakibatkan **SoftIRQ Starvation** (`ksoftirqd/0` atau `NET_RX` monopolizing Core 0).
  * Solusi Operasional:
    1. Pastikan interface mendukung multi-queue (`ethtool -l <ethX>`).
    2. Tingkatkan channel queues ke jumlah core fisik yang relevan: `ethtool -L <ethX> combined 16`.
    3. Nonaktifkan service `irqbalance` jika tidak deterministic.
    4. Tulis mapping mask baru secara manual pada `/proc/irq/<irq_number>/smp_affinity` atau `smp_affinity_list` agar interrupt terdistribusi seimbang di seluruh CPU core pada socket NUMA yang sama.

#### Skenario 3: Database Crash "Silent Killer"
* **Kondisi:** Database server PostgreSQL Enterprise dengan 256GB RAM mengalami terminasi proses secara tiba-tiba tanpa mencatatkan stack trace error apa pun di log internal PostgreSQL (`postgresql.log`). Kejadian berlangsung saat beban baca-tulis query analitik batch dieksekusi bersamaan dengan transaksi harian.
* **Pertanyaan:** Apa subsistem Linux yang melakukan terminasi ini, bagaimana cara menganalisis bukti forensiknya, dan bagaimana rekayasa parameter kernel untuk mencegah recurrence?
* **Jawaban Komprehensif:**
  PostgreSQL dimatikan secara paksa oleh **Kernel Out-Of-Memory (OOM) Killer** via sinyal `SIGKILL` (yang tidak dapat ditangkap oleh software logging user space).
  * Bukti Forensik: Eksekusi `dmesg -T | grep -E -i "oom|killed process"` atau periksa `/var/log/messages` / `journalctl -k`. Di sana akan tercatat tabel memory dump, skor badness proses, dan baris pemanggilan: `Killed process <pid> (postgres) total-vm:... anon-rss:...`.
  * Rekayasa Solusi:
    1. Konfigurasi virtual memory overcommit ke mode strict pada `/etc/sysctl.conf`:
       ```ini
       vm.overcommit_memory = 2
       vm.overcommit_ratio = 80
       ```
    2. Kurangi parameter `oom_score_adj` khusus untuk master PID PostgreSQL menjadi `-1000` (agar OOM Killer memprioritaskan proses ad-hoc lain untuk dimatikan terlebih dahulu):
       ```bash
       echo -1000 | sudo tee /proc/$(head -n 1 /var/run/postgresql.pid)/oom_score_adj
       ```
    3. Set reserve headroom swap file dan sesuaikan setting alokasi PostgreSQL `shared_buffers` + `work_mem * max_connections` agar tidak melampaui RAM fisik.

---

## 16. Summary

Optimalisasi Linux kelas enterprise menuntut peralihan dari konfigurasi reaktif generic ke perancangan arsitektur sistem yang deterministik:
1. **Pahami Batasan Abstraksi Kernel:** Lapisan VFS, Page Cache, dan POSIX Syscall mengorbankan latensi deterministik demi simplisitas pemrograman. Untuk performa absolut, gunakan bypass modern seperti `io_uring` untuk I/O storage dan eBPF/XDP untuk network stack.
2. **Kendalikan Lifecycle Virtual Memory:** Memory fragmentation dan direct reclaim adalah musuh utama dari P99.9 tail latency. Isolasi alokasi melalui kontrol absolut dirty pages (`dirty_background_ratio`), alokasi static HugePages, dan setting watermarks (`min_free_kbytes`) terukur.
3. **Harmonisasi Topologi Hardware (NUMA & IRQ):** Kecepatan CPU modern dibatasi oleh latensi interconnect memory bus. Bind thread pemrosesan, interupsi I/O card PCIe, dan resource memory ke dalam satu domain NUMA lokal yang sama untuk menghindari cross-socket bus penalty.
4. **Isolasi Terpadu Melalui cgroups v2:** Hindari fragmentasi kontrol resource. Terapkan Unified Hierarchy cgroups v2 untuk CPU, memory, dan I/O limits guna meniadakan starvation antar tenant dalam multi-workload enterprise ecosystem.