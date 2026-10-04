# Kurikulum Rekayasa Sistem Berkelanjutan: Linux Enterprise Foundation
**Kategori:** 01-Core-Foundations  
**Bab 08:** BAB-08-Materi-Lanjutan  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis dan Memanipulasi Linux Kernel Subsystems**: Menganalisis alur eksekusi internal kernel Linux (I/O scheduler, Virtual Memory Subsystem, Network Stack) untuk mengidentifikasi bottleneck performa pada level instruksi dan interrupt handling.
2. **Mengimplementasikan Observabilitas Rendah-Overhead Menggunakan eBPF**: Menulis, mengompilasi, dan memvalidasi program eBPF (Extended Berkeley Packet Filter) untuk memantau tracing kernel, network filtering, dan latency profiling tanpa mengorbankan stabilitas sistem produksi.
3. **Mengonfigurasi Isolasi Sumber Daya Lanjutan Menggunakan cgroups v2 & PSI**: Membangun topologi alokasi sumber daya berbasis `cgroups v2` terpadu dengan integrasi *Pressure Stall Information* (PSI) untuk mencegah degradasi performa akibat *noisy neighbor* dan *memory thrashing*.
4. **Mendesain Arsitektur High-Throughput I/O dengan `io_uring`**: Mengimplementasikan paradigma asynchronous I/O modern guna mengeliminasi syscall overhead dan context-switch thrashing pada pemrosesan I/O skala petabyte.
5. **Menyelaraskan Parameter Kernel (Sysctl Tuning)**: Mengonfigurasi parameter sistem tingkat lanjut untuk server produksi berdensitas tinggi (edge proxy, database engine, microservice host) dengan toleransi zero-packet-drop pada interface multi-100GbE.

---

## 2. Prerequisite

Sebelum menempuh materi ini, peserta wajib menguasai:

- Konsep dasar virtual memory (Paging, Page Tables, TLB, Swap space mechanics).
- Model konkurensi Linux (Processes, Threads, Context Switching, Inter-Process Communication).
- Dasar-dasar pemrograman C tingkat sistem (Memory pointers, structs, file descriptors, POSIX syscalls).
- Pemahaman stack jaringan TCP/IP layer 2 hingga layer 7 (Socket buffer rings, TCP handshake, MTU, Congestion Control).
- Akses terminal dengan hak akses `root`/`sudo` pada Linux Kernel $\ge$ 5.15 (disarankan 6.x) berbasis Ubuntu 22.04 LTS atau RHEL 9.

---

## 3. Concept & Internal Architecture

Arsitektur produksi enterprise modern menggeser paradigma komputasi dari eksekusi POSIX standar ke model non-blocking yang terikat langsung pada kapabilitas kernel modern:

```
+-----------------------------------------------------------------------+
|                           USER SPACE                                  |
|  +--------------------+  +--------------------+  +-----------------+  |
|  | Application (Rust) |  | Web Engine (Go/C)  |  | Observability   |  |
|  |   [io_uring SQ/CQ] |  |   [Worker Tasks]   |  |   Agent (eBPF)  |  |
+--+--------|-----------+--+---------|----------+--+--------|--------+--+
            |                        |                      |
════════════|════════════════════════|══════════════════════|════════════ System Call Boundary
            v                        v                      v
+-----------------------------------------------------------------------+
|                           KERNEL SPACE                                |
|  +-----------------------------------------------------------------+  |
|  |                          eBPF Subsystem                         |  |
|  |  +-------------+     +----------------+     +----------------+  |  |
|  |  | BPF Verifier| --> |  BPF JIT Comp  | --> | Maps (RingBuf) |  |  |
|  |  +-------------+     +----------------+     +----------------+  |  |
|  +-----------------------------------------------------------------+  |
|                                    ^                      ^           |
|                                    | (Trace/Filter)       |           |
|  +-----------------------+---------+--------+-------------+--------+  |
|  |   cgroups v2 Core     |  io_uring Engine | Network Subsystem    |  |
|  |  +-----------------+  |  +-------------+ | +------------------+ |  |
|  |  | Controllers:    |  |  | SQ Ring     | | | XDP (Driver)     | |  |
|  |  | cpu, memory, io |  |  | CQ Ring     | | | TC (Traffic Ctrl)| |  |
|  |  | PSI Monitors    |  |  | Kernel Thrd | | | Socket Buffers   | |  |
|  |  +-----------------+  |  +-------------+ | +------------------+ |  |
|  +-----------------------+------------------+----------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                     Virtual Memory (VMM)                        |  |
|  |     [SLUB Allocator]  [Transparent Hugepages]  [ZRAM/ZSWAP]     |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
|                            HARDWARE                                   |
|   [NVMe Storage Arrays]     [Multi-Queue NICs]      [NUMA Nodes]      |
+-----------------------------------------------------------------------+
```

### 3.1. Unified Hierarchy cgroups v2 dan Pressure Stall Information (PSI)

cgroups v1 memecah kontrol sumber daya ke dalam hierarki independen yang tidak saling mengetahui (uncoordinated hierarchies), menyebabkan deadlock akuntansi antara memory controller dan blkio controller (misalnya: *dirty memory writeback* tidak dapat ditagihkan ke I/O cgroup yang benar).

cgroups v2 menyelesaikan masalah ini melalui *Single Unified Hierarchy*:
- Sebuah proses berada tepat pada satu node grup kontrol.
- Model akuntansi terpadu: Writeback memory secara deterministik dialokasikan ke I/O controller pemilik halaman tersebut.
- **Pressure Stall Information (PSI)**: Metrik diagnostik real-time yang mengkuantifikasi degradasi performa akibat kelangkaan sumber daya. PSI membagi stall menjadi dua metrik:
  - `some`: Persentase waktu ketika *setidaknya satu* task terhenti (*stalled*) menunggu alokasi sumber daya (CPU, Memory, I/O).
  - `full`: Persentase waktu ketika *semua* task non-idle dalam cgroup terhenti secara simultan menunggu sumber daya. Kondisi ini mencerminkan kapasitas sistem yang kolaps total.

### 3.2. eBPF: Programmable Kernel Engine

eBPF mengubah kernel monolitik menjadi kernel yang dapat diprogram secara dinamis dan aman tanpa memuat modul kernel (`.ko`) yang rentan *kernel panic*:
- **Verifier**: Mesin verifikasi formal yang memvalidasi program sebelum dimuat:
  - Memastikan program tidak mengalami dereferensi pointer liar (*dangling pointer*).
  - Menjamin eksekusi terminasi (menolak infinite loop tak terbatas).
  - Membatasi kompleksitas komputasi instruksi (maksimal 1 juta instruksi yang diverifikasi).
- **JIT Compiler**: Mentranslasikan instruksi eBPF bytecode secara native ke instruksi arsitektur mesin (`x86_64`, `arm64`) untuk performa setara *in-kernel code*.
- **Maps**: Struktur data bersama (Shared Memory) berbasis key-value, hash, array, atau ring-buffer yang memungkinkan transmisi data deterministik antara kernel space dan user space tanpa serialization overhead.

### 3.3. Asynchronous High-Performance I/O: `io_uring`

Mekanisme POSIX konvensional (`read`, `write`, `epoll`) memerlukan minimal satu kali *context-switch* per syscall. Model `epoll` bersifat *readiness-based* (memberi tahu kapan descriptor siap dibaca, namun operasi baca aktual tetap memicu syscall blocking/interupsi buffer user space).

`io_uring` menggunakan arsitektur *completion-based* berbasis dua sirkular buffer (lockless ring-buffers) yang dipetakan ke memori bersama (*shared memory*) antara kernel dan user space:
- **Submission Queue (SQ)**: User space menulis I/O request descriptor ke SQ ring buffer.
- **Completion Queue (CQ)**: Kernel menulis hasil operasi I/O yang telah selesai ke CQ ring buffer.
- Fitur **SQPOLL** (Submission Queue Polling): Kernel mengalokasikan kernel thread khusus untuk memantau submission queue. User space dapat mengirim jutaan operasi I/O tanpa memicu satu kali pun instruksi CPU `syscall`, mengeliminasi biaya degradasi CPU akibat mitigasi Spectre/Meltdown.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Modern Enterprise |
| :--- | :--- | :--- |
| **Kernel Tracing** | Melalui kernel patch, `ftrace`, atau module `.ko` yang berisiko menumbangkan sistem (*kernel panic*). | **eBPF**: Instrumentasi aman, diverifikasi statis, dan dapat diinjeksikan secara hot-patching. |
| **I/O Multiplexing** | `epoll` + POSIX sync reads; buffer copying bertingkat dari kernel ke user space. | **io_uring**: Lockless zero-copy ring buffer dengan kernel thread polling (SQPOLL). |
| **Isolasi Beban** | cgroups v1; struktur direktori terpisah, akuntansi dirty-page writeback rusak. | **cgroups v2**: Unified tree, akuntansi I/O-Memory atomik, deteksi stall otomatis via PSI. |
| **Network Path** | Netfilter/IPTables traversal; alokasi dan deallokasi `sk_buff` per paket berkecepatan tinggi. | **XDP (eXpress Data Path)**: Pemrosesan paket langsung di DMA layer NIC via eBPF sebelum alokasi `sk_buff`. |
| **Diagnostik Latensi** | Polling metrik OS periodik (`/proc/stat`, `top`), averaging artifacts (1-5-15 min load avg). | **PSI Event Triggers**: Notifikasi kernel interrup-driven mikrodetik saat latency envelope terlampaui. |

---

## 5. How (Workflow Detail)

### 5.1. Alur Transmisi Paket XDP / eBPF vs Jaringan Standar

```
[ NIC Hardware Layer ]
         │ (Packet arrives over PCIe via DMA)
         ▼
[ Driver Ring Buffer ] ───▶ [ XDP Hook (eBPF Execution) ]
                                   │
                   ┌───────────────┴───────────────┐
                   ▼ (XDP_DROP)                    ▼ (XDP_PASS)
             [ Instantly Dropped ]        [ Allocate sk_buff ]
             (Zero Allocation)                     │
                                                   ▼
                                          [ TC Ingress (eBPF) ]
                                                   │
                                                   ▼
                                          [ Linux IP Routing ]
                                                   │
                                                   ▼
                                          [ Socket Buffer Layer ]
                                                   │
                                                   ▼
                                          [ User Application ]
```

1. **Paket Tiba**: NIC menyalin data paket ke *Ring Buffer* memori host menggunakan DMA (Direct Memory Access).
2. **Eksekusi XDP**: Kernel mengeksekusi program eBPF yang terikat langsung pada driver NIC (*native mode*). Keputusan routing (`XDP_TX`), penolakan (`XDP_DROP`), bypass soket (`XDP_REDIRECT`), atau penerusan normal (`XDP_PASS`) dilakukan dalam hitungan *nanodetik*.
3. **Alokasi `sk_buff`**: Jika dioperasikan dengan `XDP_PASS`, kernel mengalokasikan struktur `sk_buff` dan meneruskan pemrosesan ke Traffic Control (TC) Subsystem.
4. **Eksekusi TC**: Program eBPF pada level TC melakukan manipulasi header IP, dynamic QoS, atau tunneling L3/L4.
5. **Stack Transmisi Socket**: Data didekapsulasi melalui TCP/IP stack hingga mencapai buffer socket target aplikasi di ruang pengguna.

---

## 6. Analogy & Diagram ASCII

### 6.1. Analogi: Restoran Tradisional vs Modern Drive-Thru Automasi

- **Model Tradisional (`epoll`)**: Pelayan (aplikasi) bertanya ke dapur secara konstan: *"Apakah pesanan meja 5 sudah selesai?"* Dapur menjawab: *"Sudah, ambil sendiri."* Pelayan berjalan ke dapur, mengambil piring, lalu mengantarkannya. Banyak waktu habis untuk berjalan bolak-balik (Context Switch Latency).
- **Model `io_uring`**: Pelayan meletakkan daftar pesanan di nampan conveyor masuk (Submission Queue). Dapur mengambil pesanan secara otomatis, memasaknya, dan meletakkan makanan yang sudah jadi di nampan conveyor keluar (Completion Queue). Pelayan hanya perlu mengambil makanan dari nampan tanpa harus melangkah ke dapur sama sekali.
- **eBPF**: Inspektur kesehatan terbang yang dapat berteleportasi langsung ke dalam otak koki dapur (Kernel), memeriksa standar higienitas secara real-time tanpa menghentikan proses memasak, dan menghancurkan bahan makanan beracun sebelum menyentuh kompor (XDP Drop).

### 6.2. Diagram Topologi Ring Buffer `io_uring`

```
 USER SPACE                                           KERNEL SPACE
+------------------------------------+               +-----------------------------------+
| Application Memory                 |               | Kernel Memory                     |
|                                    |               |                                   |
|   +----------------------------+   |               |   +---------------------------+   |
|   | Submission Queue Entry     |   |               |   | Processing Worker Thread  |   |
|   | [Op: Read | Fd: 4 | Buf]   |   |               |   | (SQPOLL Kernel Thread)    |   |
|   +--------------│-------------+   |               |   +-------------│-------------+   |
|                  │                 |               |                 │                 |
|                  ▼                 |  Shared Mem   |                 ▼                 |
|       +═════════════════════+      | (mmap-based)  |      +═════════════════════+      |
|       ║ SQ Ring Buffer      ║<─────┼───────────────┼─────>║ SQ Ring Buffer      ║      |
|       +═════════════════════+      |               |      +═════════════════════+      |
|                                    |               |                 │                 |
|                                    |               |                 ▼                 |
|                                    |               |      [ Asynchronous I/O Engine ]  |
|                                    |               |      [  NVMe Driver Execution  ]  |
|                                    |               |                 │                 |
|                  ▲                 |               |                 ▼                 |
|       +══════════╪══════════+      |               |      +══════════╪══════════+      |
|       ║ CQ Ring Buffer      ║<─────┼───────────────┼─────>║ CQ Ring Buffer      ║      |
|       +═════════════════════+      |               |      +═════════════════════+      |
|                  │                 |               |                                   |
|   +--------------┴-------------+   |               |                                   |
|   | Completion Queue Entry     |   |               |                                   |
|   | [Res: 4096 bytes | Fd: 4]  |   |               |                                   |
|   +----------------------------+   |               |                                   |
+------------------------------------+               +-----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Tracing Real-Time Syscall Latency Menggunakan Python-BCC eBPF

Program berikut memantau latency eksekusi syscall `sys_enter_vfs_read` dan mendeteksi operasi baca yang lambat secara langsung di level kernel:

```python
#!/usr/bin/env python3
# File: trace_read_latency.py
from bcc import BPF
import time

bpf_source = """
#include <uapi/linux/ptrace.h>

BPF_HASH(start_time, u32, u64);

int trace_vfs_read_entry(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    start_time.update(&pid, &ts);
    return 0;
}

int trace_vfs_read_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 *tsp = start_time.lookup(&pid);
    if (tsp != 0) {
        u64 delta = bpf_ktime_get_ns() - *tsp;
        if (delta > 5000000) { // Catat latency > 5ms (5,000,000 ns)
            bpf_trace_printk("Slow read: PID %d, Latency: %llu ms\\n", pid, delta / 1000000);
        }
        start_time.delete(&pid);
    }
    return 0;
}
"""

b = BPF(text=bpf_source)
b.attach_kprobe(event="vfs_read", fn_name="trace_vfs_read_entry")
b.attach_kretprobe(event="vfs_read", fn_name="trace_vfs_read_return")

print("Tracing slow VFS reads (>5ms)... Tekan Ctrl+C untuk berhenti.")

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
        print(f"[{ts}] {task.decode()}: {msg.decode()}")
    except KeyboardInterrupt:
        break
```

### 7.2. Practical Example: Konfigurasi cgroups v2 Enterprise untuk Workload Latency-Critical

Konfigurasi systemd slice untuk database in-memory kencang dengan isolasi memory, CPU weight allocation, limitasi hard-kill, dan limitasi pressure stall:

```ini
# /etc/systemd/system/workload-critical.slice
[Unit]
Description=Slice untuk Workload Latency-Critical dengan PSI & cgroups v2
Before=slices.target

[Slice]
# 1. Konfigurasi CPU: Berikan alokasi weight prioritas tinggi
CPUAccounting=yes
CPUWeight=800

# 2. Memory Isolation: Hard limits dan Soft watermarks
MemoryAccounting=yes
# Batas memori maksimum absolut (OOM killer terpicu jika dilewati)
MemoryMax=32G
# Batas proteksi (Kernel menjamin memori ini tidak akan pernah di-swap out atau direclaim)
MemoryMin=16G
# Batas throttling: Kernel mulai menekan alokasi memory secara agresif jika melampaui limit ini
MemoryHigh=28G

# 3. I/O Throttling & Protection
IOAccounting=yes
# Alokasi bobot akses blok penyimpanan I/O (1-10000)
IOWeight=800
# Batas transfer maksimum pada disk penyimpanan NVMe (Device node /dev/nvme0n1 major/minor 259:0)
IODeviceWeight=/dev/nvme0n1 1000
IOReadIOPSMax=/dev/nvme0n1 150000
IOWriteIOPSMax=/dev/nvme0n1 75000

# 4. Process limits: Cegah fork-bomb eksploitasi
TasksAccounting=yes
TasksMax=16384
```

Aktifkan konfigurasi slice pada kernel:
```bash
sudo systemctl daemon-reload
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: P99 Tail Latency Degradation pada Core Payment Gateway Ultra-High-Throughput

#### 1. Arsitektur & Topologi
- **Infrastruktur**: 64-node Bare-Metal Cluster (AMD EPYC 7763, 128 vCPU, 512GB RAM, Dual 100GbE Mellanox ConnectX-6).
- **Beban Kerja**: Distribusi Go-based Financial Transaction Processor menangani 250.000 req/sec via HTTP/2 TLS.
- **Problem Statement**: Terjadi lonjakan latency P99 dari rata-rata $1.8\text{ ms}$ melonjak hingga $450\text{ ms}$ secara periodik setiap 15-20 menit.

```
+-------------------------------------------------------------------------+
|                  DIAGNOSTIK BOTTLENECK P99 LATENCY                      |
+-------------------------------------------------------------------------+
  Kondisi Awal (Degradasi Transaksi)
  Network Packets ──▶ Multi-Queue (IRQ) ──▶ ksoftirqd CPU Saturation (CPU0-7)
                                                    │
                                           kswapd0 direct reclaim
                                           (Memory Allocation Stall)
                                                    │
                                                    ▼
                                           P99 Latency: 450ms

  Solusi Rekayasa (Optimized State)
  Network Packets ──▶ IRQ Affinity Balanced ──▶ XDP eBPF Pre-Filter
                                                    │
                                           cgroups v2 PSI Triggers
                                           (MemoryMin=384G, Protect)
                                                    │
                                                    ▼
                                           P99 Latency: 1.2ms (Zero Dropped)
+-------------------------------------------------------------------------+
```

#### 2. Root Cause Analysis (RCA) Menggunakan Kernel Tracing
1. **Memory Reclaim Thrashing**: Sistem metrik OS (`free -m`) melaporkan penggunaan memori normal (65%), namun kernel mengalami kondisi *direct memory reclaim* yang dipicu oleh alokasi Page Cache dari penulisan log transaksi yang besar. Thread transaksi dialihkan oleh kernel untuk membersihkan dirty memory pages sebelum alokasi buffer baru diberikan.
2. **SoftIRQ CPU Imbalance**: Semua interupsi PCIe jaringan diarahkan secara default oleh firmware ke CPU Core node NUMA 0 (CPU 0-7), menyebabkan saturasi total thread `ksoftirqd/0` hingga `ksoftirqd/7` ($100\%$ CPU usage), sementara CPU Core 8-127 idle.

#### 3. Resolusi Rekayasa Sistem
1. **Affinity & RPS Re-balancing**:
   Mengonfigurasi distribusi interupsi jaringan NIC multi-queue merata ke seluruh core prosesor:
   ```bash
   sudo systemctl stop irqbalance
   # Distibusikan IRQ 100GbE interface ke core CPU sesuai kedekatan node NUMA
   for i in $(ls -d /sys/class/net/eth0/queues/rx-*); do
       q_num=$(echo $i | cut -d'-' -f2)
       printf "%x" $((1 << (q_num % 64))) | sudo tee /proc/irq/$(cat $i/rps_cpus)/smp_affinity
   done
   ```

2. **Isolasi Alokasi Memori Melalui cgroups v2**:
   Membuat file konfigurasi cgroup untuk mengunci memori transaksi agar kebal dari reclaim:
   ```bash
   sudo mkdir -p /sys/fs/cgroup/payment-engine
   echo "+memory +io +cpu" | sudo tee /sys/fs/cgroup/cgroup.subtree_control
   echo "384G" | sudo tee /sys/fs/cgroup/payment-engine/memory.min
   echo "450G" | sudo tee /sys/fs/cgroup/payment-engine/memory.high
   echo "480G" | sudo tee /sys/fs/cgroup/payment-engine/memory.max
   ```

3. **Sysctl Kernel Memory Tuning**:
   Mengatur kernel dirty memory ratio agar flush berjalan di background tanpa menghentikan thread aplikasi:
   ```ini
   # /etc/sysctl.d/99-latency-tuning.conf
   vm.dirty_background_ratio = 3
   vm.dirty_ratio = 10
   vm.vfs_cache_pressure = 50
   vm.swappiness = 0
   net.core.busy_poll = 50
   net.core.busy_read = 50
   ```

#### 4. Hasil Verifikasi
- Latency P99 turun secara permanen dari $450\text{ ms}$ ke level stabil $1.2\text{ ms}$.
- Throughput cluster meningkat sebesar $38\%$ pada penggunaan kapasitas CPU yang sama.
- *Zero packet drops* pada level driver ring buffer.

---

## 9. Trade-offs

| Pendekatan / Komponen | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Dampak Latensi | Dampak Skalabilitas |
| :--- | :--- | :--- | :--- | :--- |
| **`io_uring` vs `epoll`** | Mengeliminasi syscall overhead; performa I/O sebanding kernel driver native. | Permukaan serangan keamanan (*attack surface*) meningkat; debugging kompleksitas kode tinggi. | Menurun drastis (P99 turun $\sim 60\%$). | Skala I/O linier hingga batas kecepatan hardware storage/NIC. |
| **XDP Driver Hook vs Standard Socket** | Memproses paket sebelum kernel networking stack; dropping serangan DDoS tanpa alokasi memori. | Driver NIC harus mendukung native XDP (*Intel ixgbe, Mellanox mlx5*); kehilangan fitur netfilter konvensional. | Ultra-low (sub-mikrodetik per paket). | Skalabilitas packet-per-second mencapai 10x-50x socket POSIX. |
| **`memory.min` Protection** | Mencegah OS mematikan/mereclaim memori database saat load tinggi. | Jika terjadi memori overcommit sistemik, kernel langsung men-trigger Panic atau OOM pada service pendukung lain. | Eliminasi jitter latensi alokasi memori (*zero reclaim stalls*). | Mengharuskan kapasitas RAM hardware terukur secara presisi tanpa overprovisioning. |
| **Network Busy Polling (`busy_poll`)** | Menghilangkan CPU IRQ context-switch overhead; respon socket instan. | Mengorbankan utilitas CPU (satu core CPU dipaksa berjalan pada 100% clock cycles melakukan polling terus-menerus). | Terendah absolut (sub-10 mikrodetik). | Skalabilitas throughput CPU core menurun drastis; boros konsumsi daya. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes

1. **Mengabaikan Pointer Bounding saat Menulis eBPF Verifier-Friendly Code**:
   *Gejala*: Error `Permission denied` atau `Invalid access to packet, memptr at offset X`.
   *Penyebab*: Programmer gagal membuktikan ke Verifier bahwa pointer tidak melampaui panjang paket (`data + offset > data_end`).
   *Koreksi*: Wajib menyisipkan explicit memory bounds checking sebelum dereferensi pointer:
   ```c
   void *data = (void *)(long)ctx->data;
   void *data_end = (void *)(long)ctx->data_end;
   struct ethhdr *eth = data;
   if ((void *)(eth + 1) > data_end)
       return XDP_DROP;
   ```

2. **Konfigurasi `tcp_rmem` & `tcp_wmem` Terlalu Agresif Tanpa Menghitung Batas RAM**:
   *Gejala*: Server crash dengan pesan `Out of Memory: Kill process` padahal metrik heap aplikasi normal.
   *Penyebab*: Nilai maksimal `tcp_rmem` (misal 64MB) dikalikan ratusan ribu koneksi konkuren menyedot memori fisik kernel (`sk_buff` slab cache) di luar jangkauan cgroup tracker aplikasi.
   *Koreksi*: Hitung memory footprint network kernel: $\text{Koneksi Maksimum} \times \text{Buffer Size} < \text{RAM Khusus Jaringan}$.

3. **Mencampur Hirarki cgroups v1 dan cgroups v2 (Hybrid Mode)**:
   *Gejala*: Kontroler cgroups v2 tidak muncul di `cgroup.subtree_control`, resource limits tidak diterapkan oleh systemd.
   *Penyebab*: Parameter kernel masih memuat konfigurasi legacy cgroups v1.
   *Koreksi*: Pastikan bootloader Linux memuat parameter `systemd.unified_cgroup_hierarchy=1`.

### 10.2. Troubleshooting Runbook: Analisis Masalah CPU SoftIRQ Thrashing

```
Gejala: Packet drops tinggi pada RX Ring Buffer, ksoftirqd memakan 100% CPU.
```

1. **Langkah 1: Cek distribusi interupsi jaringan pada CPU Core**:
   ```bash
   cat /proc/interrupts | grep -E "eth|mlx|ens"
   ```
   *Jika hanya satu core CPU yang nilai count-nya bertambah cepat secara signifikan, terjadi IRQ misbalance.*

2. **Langkah 2: Monitor dropped packets pada level interface physical driver**:
   ```bash
   ethtool -S eth0 | grep -E "drop|miss|error"
   ```
   *Jika `rx_missed_errors` atau `rx_dropped` bernilai tinggi, hardware buffer ring telah meluap.*

3. **Langkah 3: Perbesar Ring Buffer hardware menggunakan `ethtool`**:
   ```bash
   # Cek batas ring maximum
   ethtool -g eth0
   # Terapkan batas maksimum (misal: 4096 descriptors)
   sudo ethtool -G eth0 rx 4096 tx 4096
   ```

4. **Langkah 4: Analisis lokasi bottleneck kernel menggunakan `perf`**:
   ```bash
   sudo perf top --filter ksoftirqd
   ```
   *Lacak fungsi internal stack kernel (misal: `fib_table_lookup`, `ipt_do_table`, atau `__netif_receive_skb_core`) yang memakan siklus komputasi CPU paling lama.*

---

## 11. Best Practices (Production Checklist)

### 11.1. Kernel Sysctl Hardening & Tuning Checklist (`/etc/sysctl.d/60-production.conf`)
- [ ] Nonaktifkan packet routing forwarding jika mesin bertindak sebagai pure host: `net.ipv4.ip_forward = 0`
- [ ] Proteksi kernel terhadap SYN Flood Attack: `net.ipv4.tcp_syncookies = 1`
- [ ] Perbesar backlog listen queue koneksi: `net.core.somaxconn = 65535`
- [ ] Tingkatkan alokasi deskriptor socket: `fs.file-max = 2097152`
- [ ] Perbesar depth backlog input jaringan OS: `net.core.netdev_max_backlog = 250000`
- [ ] Aktifkan TCP BBR Congestion Control (Kernel $\ge$ 4.9):
  ```ini
  net.core.default_qdisc = fq
  net.ipv4.tcp_congestion_control = bbr
  ```
- [ ] Optimalkan dirty-memory flushing interval untuk mencegah disk write freezes:
  ```ini
  vm.dirty_background_bytes = 67108864 # 64MB
  vm.dirty_bytes = 268435456           # 256MB
  ```

### 11.2. Monitoring & Diagnostic Baseline
- [ ] Pasang exporter eBPF berbasis tracepoints (misal: Cilium Hubble, Tetragon, atau custom bcc exporter).
- [ ] Aktifkan alert automasi jika nilai file `/proc/pressure/memory` atau `/proc/pressure/io` metrik `some avg10` melampaui $15\%$.
- [ ] Pastikan systemd menggunakan slice hierarkis terpisah untuk *Infra Services* (`system.slice`), *Production Apps* (`workload.slice`), dan *SSH Admin Sessions* (`user.slice`).

---

## 12. Hands-on Practice

Target Praktikum: Membangun lab diagnostik observabilitas kernel, implementasi cgroups v2 terisolasi, dan konfigurasi kernel ring parameter.

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 1: Script Automasi Isolasi cgroups v2 & Pressure Stall Monitor

Buat file `hands-on/m02/setup_cgroup_psi.sh`:

```bash
#!/usr/bin/env bash
# File: hands-on/m02/setup_cgroup_psi.sh
set -euo pipefail

CGROUP_PATH="/sys/fs/cgroup/m02_lab"

echo "[1/4] Mengaktifkan kontroler terpadu pada parent cgroup..."
echo "+cpu +memory +io" | sudo tee /sys/fs/cgroup/cgroup.subtree_control > /dev/null

echo "[2/4] Membuat cgroup isolated: ${CGROUP_PATH}..."
sudo mkdir -p "${CGROUP_PATH}"

echo "[3/4] Menetapkan batas memori dan CPU..."
# Batasi memori hingga 512MB
echo "536870912" | sudo tee "${CGROUP_PATH}/memory.max" > /dev/null
# Batasi CPU hingga 50% dari 1 core (50000 mikrosekon per 100000 mikrosekon period)
echo "50000 100000" | sudo tee "${CGROUP_PATH}/cpu.max" > /dev/null

echo "[4/4] Memeriksa status konfigurasi PSI dan resource limits:"
cat "${CGROUP_PATH}/memory.max" | awk '{print "Memory Max Limit: " $1 / 1024 / 1024 " MB"}'
cat "${CGROUP_PATH}/cpu.max" | awk '{print "CPU Quota: " $1 " / Period: " $2}'
echo "Selesai. Setup cgroups v2 berhasil."
```

### Langkah 2: Monitoring Kernel Pressure Stall Information Engine

Buat file diagnostik Python: `hands-on/m02/psi_monitor.py`:

```python
#!/usr/bin/env python3
# File: hands-on/m02/psi_monitor.py
import time
import sys

PSI_FILE = "/sys/fs/cgroup/m02_lab/memory.pressure"

def parse_psi_line(line):
    # Format line: some avg10=0.00 avg60=0.00 avg300=0.00 total=0
    parts = line.strip().split()
    metric_type = parts[0]
    data = {}
    for item in parts[1:]:
        k, v = item.split('=')
        data[k] = float(v) if '.' in v else int(v)
    return metric_type, data

def main():
    print(f"Memonitoring PSI pada {PSI_FILE}. Tekan Ctrl+C untuk keluar.")
    try:
        while True:
            with open(PSI_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    metric, metrics_data = parse_psi_line(line)
                    if metric == "some":
                        print(f"[PSI ALERT CHECK] Memory Some Stall: Avg10={metrics_data['avg10']}% | Total={metrics_data['total']}us")
                        if metrics_data['avg10'] > 5.0:
                            print("  >> PERINGATAN: Alokasi memory mengalami degradasi latency tinggi! <<")
            time.sleep(2)
    except FileNotFoundError:
        print(f"Error: Path {PSI_FILE} tidak ditemukan. Jalankan setup_cgroup_psi.sh terlebih dahulu.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nMonitoring selesai.")

if __name__ == '__main__':
    main()
```

### Langkah 3: Eksekusi Workload Testing dan Validasi

Eksekusi skenario beban kerja dalam kontrol cgroup untuk memvalidasi isolasi:

```bash
# Berikan hak akses eksekusi script
chmod +x hands-on/m02/setup_cgroup_psi.sh
chmod +x hands-on/m02/psi_monitor.py

# Inisialisasi cgroup
./hands-on/m02/setup_cgroup_psi.sh

# Terminal 1: Jalankan monitoring PSI
python3 hands-on/m02/psi_monitor.py &
MONITOR_PID=$!

# Terminal 2 / Background: Inject proses ke dalam cgroup yang mengonsumsi memori
echo "Menjalankan stress test di dalam cgroup..."
# Masukkan shell worker ke dalam cgroup m02_lab
sudo sh -c 'echo $$ > /sys/fs/cgroup/m02_lab/cgroup.procs && stress-ng --vm 1 --vm-bytes 450M --timeout 10s'

# Cleanup
kill -9 $MONITOR_PID 2>/dev/null || true
echo "Praktikum selesai secara deterministik."
```

---

## 13. Exercise

### Tingkat Easy
Gunakan perintah `ethtool` dan `tc` untuk:
1. Mengidentifikasi ukuran ring buffer transmit (TX) dan receive (RX) dari interface jaringan utama mesin Anda.
2. Acceptance Criteria: Dokumentasikan limit maksimum yang didukung perangkat keras kartu jaringan vs alokasi saat ini.

### Tingkat Medium
Buat sebuah program Python berbasis BCC (eBPF) yang melakukan attach ke kprobe `do_sys_openat2`:
1. Mampu membaca nama file (path string) yang sedang dibuka oleh sistem operasi.
2. Menghitung jumlah frekuensi file yang dibuka per proses (PID) dan mengeluarkannya ke layar setiap 5 detik.
3. Acceptance Criteria: Program berhasil berjalan tanpa kompilasi module kernel, dan verifier menyetujui program eBPF tanpa error penolakan memori pointer.

### Tingkat Hard
Konfigurasi skenario pencegahan *Out-Of-Memory Cascade* pada host produksi:
1. Buat hierarki cgroups v2 dengan nested groups: `/sys/fs/cgroup/prod.slice/db.service` dan `/sys/fs/cgroup/prod.slice/worker.service`.
2. Alokasikan `memory.low` dan `memory.min` sebesar 80% RAM fisik ke `db.service`.
3. Simulasikan skenario alokasi beban berlebih pada `worker.service` hingga mencapai `memory.max`.
4. Acceptance Criteria: Kernel OOM killer harus mengeksekusi proses dalam `worker.service` secara deterministik tanpa mengganggu satu pun alokasi memori atau menaikkan metrik PSI pada `db.service`.

---

## 14. Challenge

### Arsitektur Kasus: Rekayasa Engine Trading FinTech Skala 100GbE Ultra-Low Latency

#### Deskripsi Skenario:
Sebuah exchange kripto/fintech enterprise menuntut *Packet-to-Response Processing Time* di bawah $5\text{ mikrodetik}$ untuk alur pesanan (Limit Orders). Sistem beroperasi di atas sepasang interface jaringan 100GbE per server bare-metal. Pada jam puncak volume perdagangan, arsitektur Linux standar mengalami bottleneck berikut:

1. Latensi context-switching memicu jitter hingga $80\text{ mikrodetik}$.
2. Pemrosesan alur network stack POSIX standar (`sk_buff`, TCP reassembly, netfilter check) mengonsumsi $70\%$ siklus CPU.
3. Operasi persistensi audit log transaksi ke drive NVMe memicu I/O delay yang memblokir engine utama.

#### Tugas Arsitektural (Deliverables Tanpa Solusi Instan):
Rancang dokumen arsitektur dan spesifikasi konfigurasi Linux menyeluruh yang mencakup:

1. **Kernel Bypass / Acceleration Topology**: Tentukan strategi implementasi antara XDP (eXpress Data Path) Native Mode, AF_XDP (*Address Family XDP*), atau DPDK. Berikan rasionalisasi teknis mengapa pilihan tersebut dipilih berdasarkan pertimbangan pemeliharaan kode vs efisiensi instruksi CPU.
2. **Asynchronous Audit Logging**: Desain arsitektur logging zero-syscall menggunakan `io_uring` terikat pada direct NVMe block I/O (`O_DIRECT`).
3. **CPU Core Pinning & NUMA Strategy**: Rancang skema partisi CPU:
   - Isolasi core menggunakan `isolcpus`, `nohz_full`, dan `rcu_nocbs`.
   - Konfigurasi alokasi RAM per Node NUMA (`numactl`, `mbind`) untuk mengeliminasi latensi transmisi antar-socket melalui interconnect bus (AMD Infinity Fabric atau Intel UPI).
4. **Failure Modes & Edge-Cases**: Rancang failover mitigasi apabila program XDP mengalami panic atau kehabisan slot ring-buffer saat market flash crash terjadi.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic

1. Mengapa kernel verifier pada arsitektur eBPF menolak program yang memiliki instruksi loop tanpa batas (*unbounded loop*)?
   - A. Karena loop menghabiskan memori RAM stack frame kernel.
   - B. Untuk menjamin eksekusi program terminasi deterministik dan mencegah kernel mengalami deadlock/hang.
   - C. Karena compiler JIT tidak mampu menerjemahkan loop ke arsitektur x86_64.
   - D. Loop hanya diizinkan jika dieksekusi di user space.

2. Parameter sysctl mana yang digunakan untuk mengaktifkan algoritma TCP Congestion Control BBR?
   - A. `net.ipv4.tcp_bbr_enabled = 1`
   - B. `net.ipv4.tcp_congestion_control = bbr` dan `net.core.default_qdisc = fq`
   - C. `net.core.tcp_window_scaling = 1`
   - D. `vm.tcp_congestion_control = bbr`

3. Apa keuntungan arsitektural utama unified hierarchy pada cgroups v2 dibandingkan cgroups v1?
   - A. Mengizinkan sebuah proses berada di 10 grup berbeda secara paralel.
   - B. Koordinasi atomik antara subsystem (seperti alokasi I/O dirty page writeback yang terikat langsung ke memory controller cgroup yang tepat).
   - C. Menghapus ketergantungan pada systemd.
   - D. Mengurangi alokasi memory kernel hingga 90%.

4. Di layer manakah instruksi program eBPF berbasis XDP (eXpress Data Path) dieksekusi?
   - A. Di dalam layer socket user space setelah fungsi `accept()`.
   - B. Di layer driver kartu jaringan (NIC) tepat saat paket disalin ke DMA ring buffer sebelum struktur `sk_buff` dialokasikan.
   - C. Di dalam Traffic Control Ingress setelah filtering IPTables.
   - D. Di layer sistem file VFS.

5. Apa representasi dari metrik `full` pada Linux Pressure Stall Information (PSI)?
   - A. Persentase kapasitas storage disk yang telah terisi penuh.
   - B. Persentase waktu ketika seluruh proses non-idle dalam cgroup terhenti (*stalled*) menunggu ketersediaan hardware resource.
   - C. Tingkat saturasi bandwidth jaringan 100GbE.
   - D. Jumlah swap space yang tersisa sebelum OOM killer berjalan.

---

### 15.2. Pertanyaan Intermediate

6. Bagaimana cara kerja submission queue polling (**SQPOLL**) pada arsitektur `io_uring` mengeliminasi CPU context switch?
   - A. Dengan menjalankan aplikasi user space langsung di level privilege Ring 0.
   - B. Dengan membuat thread khusus di kernel space yang terus menerus memantau Submission Queue di shared memory tanpa membutuhkan pemanggilan syscall `enter` oleh user space.
   - C. Dengan mengubah seluruh I/O synchronous menjadi thread pool pthread di user space.
   - D. Menghapus instruksi CPU memory barrier.

7. Perhatikan konfigurasi cgroups v2: `memory.min = 10G`, `memory.high = 15G`, `memory.max = 20G`. Apa yang terjadi jika penggunaan memori proses mencapai $16\text{ GB}$?
   - A. Kernel langsung memicu OOM Killer dan mematikan proses utama.
   - B. Kernel mematikan host server secara instan untuk proteksi hardware.
   - C. Kernel tidak mematikan proses, tetapi mulai menekan alokasi (*throttling*) dan mengaktifkan reclaim secara agresif terhadap proses tersebut.
   - D. Memori dialihkan secara paksa ke hard disk swap tanpa degradasi I/O.

8. Dalam kondisi traffic load UDP/TCP tinggi, tool `ethtool -S` menunjukkan peningkatan pesat pada kolom counter `rx_missed_errors`. Tindakan resolusi sistem pertama yang paling tepat adalah:
   - A. Menaikkan nilai `vm.swappiness` ke 100.
   - B. Memperbesar ukuran RX Ring Buffer hardware interface menggunakan `ethtool -G <iface> rx <max_val>`.
   - C. Me-restart networking systemd slice.
   - D. Menurunkan batas ukuran Maximum Transmission Unit (MTU).

9. Apa perbedaan mendasar antara implementasi tracing kernel berbasis **Kprobe** vs **Tracepoints** pada eBPF?
   - A. Tracepoints tidak memerlukan verifier, sedangkan Kprobe memerlukan verifier.
   - B. Kprobe bersifat dinamis dengan memodifikasi instruksi memori kernel run-time (berisiko berubah antar versi kernel), sedangkan Tracepoints adalah titik instrumen statis yang stabil yang didefinisikan secara resmi di source code kernel.
   - C. Kprobe dieksekusi di user space, Tracepoints di hardware.
   - D. Kprobe hanya dapat membaca register CPU, tidak dapat mengakses isi struct memory.

10. Mengapa nilai `vm.dirty_ratio` yang terlalu besar (misal: 60% pada RAM 512GB) membahayakan persistensi database berlatensi rendah?
    - A. Menyebabkan memori swap tidak dapat dialokasikan.
    - B. Saat batas tercapai, kernel memblokir seluruh syscall `write()` aplikasi untuk mem-flush kotoran memori ratusan gigabyte ke storage secara sinkron (*I/O freeze stall*).
    - C. Menghapus isi database saat daya listrik mati.
    - D. Menurunkan clock speed prosesor CPU host.

---

### 15.3. Skenario Kasus Produksi

11. **Skenario Kasus 1**:  
    Sebuah host Kubernetes enterprise berbasis Ubuntu 22.04 LTS mengalami *node freezing* sporadis selama 3-5 detik setiap kali backup cluster berjalan di malam hari. Monitoring standar menunjukkan utilisasi CPU total hanya $25\%$, utilisasi RAM $50\%$, namun metrik transaksi HTTP pod aplikasi di node tersebut mencatatkan ribuan timeout.  
    *Pertanyaan Kasus*: Apa investigasi teknis pertama yang harus Anda buktikan melalui subsistem kernel Linux, file apa di direktori `/proc` yang membuktikannya, dan parameter kernel apa yang menjadi akar masalahnya?

12. **Skenario Kasus 2**:  
    Sebuah platform edge-routing mengimplementasikan program XDP eBPF untuk mitigasi serangan DDoS. Ketika diuji dengan trafik simulasi SYN Flood sebesar 40 juta packet per detik (Mpps), program XDP di mode `native driver` mampu men-drop trafik berbahaya secara mulus. Namun, ketika program tersebut dipindahkan ke interface tunnel virtual (GRE/VXLAN) atau interface yang drivernya tidak memiliki native XDP hook, utilisasi CPU host langsung melompat menjadi $100\%$ dan server berhenti merespons.  
    *Pertanyaan Kasus*: Jelaskan mengapa terjadi perbedaan performa katastropik tersebut dan bagaimana alur eksekusi internal kernel memproses XDP pada interface yang tidak memiliki native driver support.

13. **Skenario Kasus 3**:  
    Aplikasi database FinTech Anda menggunakan file descriptor I/O langsung (`O_DIRECT`). Administrator sistem mengubah konfigurasi I/O scheduler dari `none` (atau `kyber`) menjadi `bfq` (Budget Fair Queueing) pada drive SSD NVMe PCIe Gen4 berkecepatan tinggi. Pasca perubahan, metrik IOPS database turun drastis dari 800.000 IOPS menjadi 95.000 IOPS, disertai kenaikan drastis pada P99 latensi.  
    *Pertanyaan Kasus*: Jelaskan inkompatibilitas mekanis antara algoritma penjadwalan `bfq` dengan karakteristik perangkat keras modern NVMe Multi-Queue, dan mengapa scheduler `none` adalah opsi standar mutlak untuk arsitektur I/O modern enterprise.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Kunci Pilihan Ganda:
1. **B** — eBPF verifier wajib menjamin safety. Unbounded loops berpotensi memicu kernel lock-up permanen, sehingga ditolak secara ketat.
2. **B** — Algoritma BBR memerlukan queue discipline Fair Queuing (`fq`) agar pacing emisi paket TCP berjalan presisi di level kernel stack.
3. **B** — cgroups v2 menyelesaikan problem akuntansi cross-resource (khususnya sinkronisasi alokasi antara blok I/O dan memory cache dirty pages).
4. **B** — XDP bekerja sebelum alokasi struktur `sk_buff` terjadi, tepat di lapisan driver network ring DMA, menghasilkan throughput ultra-tinggi.
5. **B** — Metrik `full` pada PSI mengindikasikan seluruh task non-idle dalam cgroup terhenti menunggu giliran ketersediaan hardware (kelangkaan kritis).
6. **B** — SQPOLL mengalokasikan kernel thread yang secara aktif memantau ring buffer di memori terpetakan (mmap), mengeliminasi kebutuhan instruksi syscall dari user space.
7. **C** — `memory.high` bertindak sebagai soft limit dinamis yang memicu throttling proses secara proporsional sebelum menyentuh hard limit `memory.max` yang memicu eksekusi OOM killer.
8. **B** — `rx_missed_errors` menandakan hardware queue terisi penuh karena CPU/driver terlambat mengosongkan paket dari buffer kartu jaringan. Solusi awal adalah memperbesar ring descriptor.
9. **B** — Tracepoints stabil secara ABI kernel, sedangkan Kprobe mengaitkan instruksi dynamic breakpoint pada arbitrary function kernel yang dapat berubah tanpa peringatan antar versi kernel.
10. **B** — Dirty pages yang menumpuk hingga batas rasio absolut memaksa kernel menghentikan proses user space untuk membersihkan memori secara serentak (*sync flush bottleneck*).

#### Panduan Jawaban Skenario Kasus:
11. **Pembahasan Kasus 1**:
    - *Investigasi*: Periksa Pressure Stall Information (PSI) I/O dan memory: `cat /proc/pressure/io` dan `cat /proc/pressure/memory`. Anda akan menemukan metrik `some` dan `full` I/O melonjak hingga $>60\%$ selama proses backup.
    - *Akar Masalah*: Proses backup membanjiri buffer cache memory dengan dirty pages. Kernel default menggunakan `vm.dirty_ratio` berbasis persentase RAM (yang setara dengan puluhan gigabyte pada server besar). Ketika flush sinkron terpicu, seluruh sistem I/O freeze.
    - *Solusi*: Terapkan batas byte absolut: `vm.dirty_background_bytes = 67108864` (64MB) dan `vm.dirty_bytes = 268435456` (256MB).
12. **Pembahasan Kasus 2**:
    - *Penyebab*: Jika driver NIC tidak mendukung XDP native mode, kernel secara otomatis melakukan fallback ke **Generic XDP** (`XDP_GENERIC`).
    - *Mekanisme Internal*: Pada mode generic, XDP dieksekusi *setelah* alokasi `sk_buff` penuh dan setelah alokasi memori paket di stack networking standar selesai dilakukan. Akibatnya, jutaan alokasi dan deallokasi struktur paket kompleks tetap terjadi di core CPU, menghilangkan manfaat bypass zero-allocation, sehingga 40 Mpps membanjiri CPU host secara instan.
13. **Pembahasan Kasus 3**:
    - *Penyebab*: `bfq` dirancang untuk disk mekanis putar (HDD) atau single-queue SSD legacy untuk memprioritaskan keadilan akses (*fair sharing*) via komputasi algoritma overhead tinggi di CPU.
    - *Mekanisme NVMe*: NVMe storage beroperasi secara paralel dengan mendukung hingga 64.000 queue independen secara hardware, di mana masing-masing queue dapat menampung 64.000 submission entries. Memasang scheduler kompleks seperti `bfq` memaksa transaksi multi-queue NVMe disatukan ke antrean algoritma software terpusat yang memicu penguncian CPU core (*lock contention*).
    - *Solusi*: Gunakan scheduler `none`, yang membiarkan hardware internal controller NVMe mengeksekusi antrean multi-queue paralelnya secara langsung tanpa campur tangan software layer I/O kernel.

---

## 16. Summary

```
+───────────────────────────────────────────────────────────────────────────+
|                  RINGKASAN ARSITEKTUR LINUX KERNEL MODERN                 |
+───────────────────────────────────────────────────────────────────────────+
  cgroups v2        Unified Hierarchy    Eliminasi isolasi broken-accounting,
                    + PSI Engine         monitoring latency degradation dini.
  ─────────────────────────────────────────────────────────────────────────
  eBPF Subsystem    In-Kernel Virtual    Observabilitas deterministik, dynamic
                    Machine + Verifier   patching, security & network offloading.
  ─────────────────────────────────────────────────────────────────────────
  io_uring Engine   Zero-Syscall Ring    Menggantikan epoll readiness model
                    Buffers (SQ/CQ)      dengan async completion & SQPOLL.
  ─────────────────────────────────────────────────────────────────────────
  Network Tuning    XDP + Driver Ring    Bypass sk_buff traversal alokasi buffer,
                    + TCP BBR Pacing     mengantarkan multi-million pps scale.
+───────────────────────────────────────────────────────────────────────────+
```

Penguasaan Linux tingkat enterprise pada era cloud-native dan komputasi performa tinggi tidak lagi berpusat pada perintah administrasi sistem operasional sederhana. Arsitektur produksi modern membutuhkan pemahaman presisi mengenai bagaimana instruksi dieksekusi di batas antarmuka kernel-user space, bagaimana alokasi halaman memori direclaim di bawah tekanan beban puncak, dan bagaimana meminimalkan friksi *context-switch* serta alokasi buffer melalui pemanfaatan kapabilitas subsistem modern seperti **eBPF**, **io_uring**, dan **cgroups v2**. Pengetahuan ini adalah pondasi fundamental yang membedakan administrator infrastruktur biasa dengan Senior Platform/System Engineer kelas enterprise.