# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Linux Core Foundations)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis dan Membedah Subsistem Kernel**: Memahami interaksi internal antara Virtual Memory System, Scheduler (CFS/EEVDF), Virtual File System (VFS), dan Network Stack pada Linux Kernel versi modern (5.x/6.x).
- **Mengimplementasikan Programmable Kernel Tracing**: Merancang dan mengeksekusi program eBPF (*extended Berkeley Packet Filter*) untuk observability, security audit, dan performance profiling tingkat rendah tanpa menimbulkan overhead runtime yang destruktif.
- **Mengonfigurasi Isolasi Sumber Daya Tingkat Lanjut**: Mengimplementasikan arsitektur Cgroups v2 secara terpadu (*unified hierarchy*), konfigurasi *Pressure Stall Information* (PSI), serta orkestrasi resource slices menggunakan systemd.
- **Melakukan Tuning Kernel Produksi Skala Enterprise**: Melakukan optimasi performa *low-latency* dan *high-throughput* pada subsistem memori (NUMA, HugePages, SLUB Allocator), I/O (I/O Schedulers, `io_uring`), dan Networking (`epoll`, TCP buffer autotuning, XDP).
- **Mendiagnosis Masalah Sistem Tingkat Rendah**: Menganalisis *memory leaks*, kswapd thrashing, lock contention, dan packet drops pada driver ring buffer menggunakan ftrace, bpftrace, dan perf.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:

1. **Pemrograman Sistem Dasar**: Pemahaman bahasa C (pointer, alokasi memori, struct) dan syscalls standar POSIX (`fork`, `execve`, `clone`, `mmap`, `epoll_wait`).
2. **Administrasi Linux Tingkat Menengah**: Pengoperasian CLI, systemd service management, konfigurasi jaringan (`iproute2`), manipulasi file descriptor, dan partisi disk.
3. **Konsep Arsitektur Komputer**: CPU ring privilege levels (Ring 0 vs. Ring 3), konteks switching, interrupt handling (IRQ/SoftIRQ), arsitektur cache (L1/L2/L3), dan NUMA (*Non-Uniform Memory Access*).

---

## 3. Concept & Internal Architecture

Arsitektur produksi Linux modern bergantung pada interaksi deterministik antara ruang pengguna (*User Space*) dan ruang kernel (*Kernel Space*).

```
+-------------------------------------------------------------------------------+
|                                  USER SPACE                                   |
|  [ Microservices / Database ]   [ systemd slices ]   [ Observability Agents ] |
+-------------------------------------------------------------------------------+
         | Syscalls (`read`, `write`, `epoll_ctl`, `bpf`, `clone3`)
         v
+-------------------------------------------------------------------------------+
|                                 KERNEL SPACE                                  |
|  +-------------------------------------------------------------------------+  |
|  |                           System Call Interface                         |  |
|  +-------------------------------------------------------------------------+  |
|         |                     |                      |                |       |
|         v                     v                      v                v       |
|  +--------------+    +-------------------+    +--------------+  +-----------+ |
|  | Process &    |    | Memory Management |    | Virtual File |  | Network   | |
|  | Scheduler    |    | (NUMA, Page Cache,|    | System (VFS) |  | Subsystem | |
|  | (CFS/EEVDF)  |    |  SLUB, HugePages) |    |              |  | (TCP/IP)  | |
|  +--------------+    +-------------------+    +--------------+  +-----------+ |
|         |                     |                      |                |       |
|  +-------------------------------------------------------------------------+  |
|  |                     cgroups v2 & Security Subsystem                     |  |
|  |             (Memory, CPU, IO, PIDs Controllers, LSM/SELinux)            |  |
|  +-------------------------------------------------------------------------+  |
|         |                                                             |       |
|  +-------------------------------------------------------------------------+  |
|  |                     eBPF Virtual Machine & JIT Engine                   |  |
|  |              [kprobes]  [tracepoints]  [uprobes]  [XDP]                 |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------------------------+
|                                   HARDWARE                                    |
|       [ CPUs / NUMA Nodes ]     [ Physical RAM ]     [ NVMe / 100GbE NIC ]    |
+-------------------------------------------------------------------------------+
```

### A. Extended Berkeley Packet Filter (eBPF) Engine

eBPF mengubah kernel Linux dari sistem monolitik statis menjadi subsistem dinamis yang dapat diprogram secara aman (*programmable kernel*).
- **BPF In-Kernel Verifier**: Menganalisis *Abstract Syntax Tree* (AST) dari bytecode BPF sebelum dieksekusi. Verifier memastikan bahwa program:
  - Tidak memiliki loop tak terbatas (*infinite loops*).
  - Tidak membaca memori di luar batas yang diizinkan (*out-of-bounds memory access*).
  - Tidak dereference pointer null.
  - Memiliki ukuran instruksi di bawah batas kernel (maksimal 1 juta instruksi yang diverifikasi).
- **JIT (Just-In-Time) Compiler**: Mengonversi eBPF bytecode instruksi generik ke instruksi native mesin (x86_64, ARM64) untuk eksekusi mendekati kecepatan hardware (*zero-overhead boundary*).
- **eBPF Maps**: Struktur data kernel-space thread-safe (Hash map, Array, Ring Buffer, LRU) yang berfungsi sebagai jembatan komunikasi sinkron/asinkron antara User Space dan Kernel Space.
- **Hook Attachment**: Dapat dipasang pada Tracepoints (statik), Kprobes/Kretprobes (dinamik di kernel), Uprobes (dinamik di userspace), serta XDP (*eXpress Data Path* — langsung pada driver ring buffer kartu jaringan).

### B. Memory Management Subsystem: NUMA & HugePages

Pada sistem multi-socket modern, arsitektur memori bersifat *Non-Uniform Memory Access* (NUMA):
- **NUMA Nodes**: Setiap socket CPU memiliki kontroler memori lokal. Akses CPU ke memori lokal (*local node*) membutuhkan latensi sekitar 50-80ns, sedangkan akses memori lintas soket via interconnect bus (seperti Intel UPI atau AMD Infinity Fabric) menghasilkan latensi tambahan 30-50% (*remote node access*).
- **Zone Reclaim & Page Allocator**: Subsistem kernel mengelola alokasi memori melalui *Buddy Allocator* (untuk alokasi halaman berbasis eksponensial $2^n$) dan *SLUB Allocator* (untuk objek-objek kecil kernel seperti *task_struct*, *inode*).
- **Transparent HugePages (THP) vs Explicit HugePages**: 
  - Standar halaman memori Linux adalah 4 KiB.
  - THP mengalokasikan halaman 2 MiB atau 1 GiB secara otomatis, tetapi dapat menyebabkan latensi tinggi saat proses defragmentasi memori (*direct compaction stalls*).
  - Explicit HugePages (HugeTLB) memesan pool memori 2 MiB / 1 GiB sejak boot, kebal terhadap alokasi runtime, dan meminimalkan TLB (*Translation Lookaside Buffer*) misses secara signifikan pada aplikasi *high-memory* (seperti PostgreSQL, Redis, ScyllaDB).

### C. Cgroups v2 & Pressure Stall Information (PSI)

Cgroups v2 menerapkan model hierarki terpadu tunggal (*single unified hierarchy*), menghilangkan konflik alokasi sumber daya antar pengontrol (*controllers*) yang sering terjadi pada Cgroups v1.
- **No Internal Process Constraint**: Proses pengguna hanya boleh berada di *leaf nodes*, mencegah *parent cgroup* bersaing alokasi langsung dengan *child cgroup*.
- **Pressure Stall Information (PSI)**: Metrik diagnostik presisi tinggi yang melacak waktu degradasi performa akibat kelangkaan sumber daya (*CPU, Memory, I/O*). PSI membagi metrik menjadi dua kategori:
  - `some`: Persentase waktu ketika beberapa proses terhambat (*stalled*) menunggu alokasi sumber daya.
  - `full`: Persentase waktu ketika seluruh proses dalam cgroup terhenti total karena menunggu alokasi sumber daya (misalnya: *thrashing* swap atau synchronous disk sync).

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Sysstat, Cgroups v1, Top) | Pendekatan Modern Enterprise (eBPF, Cgroups v2, PSI) |
| :--- | :--- | :--- |
| **Metode Observabilitas** | Polling metrik via `/proc` dan `/sys` secara berkala (interval detik). | Event-driven kernel instrumentation via eBPF kprobes & tracepoints (resolusi nanodetik). |
| **Overhead Monitoring** | Tinggi jika frekuensi polling ditingkatkan; sampling `ptrace` menghentikan thread aplikasi (*stop-the-world*). | Mendekati 0% runtime penalty; JIT execution di kernel space; data disalurkan via BPF Ring Buffer. |
| **Resource Isolation** | Fragmentasi kontroler; alokasi memori dan I/O terpisah sehingga OOM killer mematikan proses acak. | Single Unified Tree; integrasi cgroup-aware OOMD; PSI mendeteksi degradasi sebelum OOM terjadi. |
| **Network Latency** | Paket melintasi seluruh Linux Network Stack (SKB allocation, netfilter, socket buffers). | XDP (*eXpress Data Path*) memfilter atau me-route paket langsung di NIC driver level sebelum memakan siklus CPU kernel. |
| **Storage Throughput** | Block layer I/O terikat syscall blocking atau posix-AIO yang terbatas. | Asynchronous I/O via `io_uring` memotong *syscall context switches* menggunakan antrean cincin (*ring buffer*) bersama. |

---

## 5. How: Workflow Detail

### Workflow 1: Lifecycle Eksekusi eBPF Observability di Kernel

```
+-------------------+      +--------------------+      +----------------------+
| 1. BPF C Code     | ---> | 2. Clang / LLVM    | ---> | 3. Bytecode (ELF)    |
| (Kprobe / Tracep) |      | Target: bpf        |      | (.o file)            |
+-------------------+      +--------------------+      +----------------------+
                                                                  |
                                                                  v
+-------------------+      +--------------------+      +----------------------+
| 6. Attach to Hook | <--- | 5. BPF JIT Compiler| <--- | 4. sys_bpf(LOAD)     |
| (kprobe/XDP/perf) |      | Machine Code       |      | Kernel Verifier Scan |
+-------------------+      +--------------------+      +----------------------+
         |
         v
+-----------------------------------------------------------------------------+
| 7. Execution: Event fires -> BPF program runs -> Writes to BPF Ring Buffer  |
| 8. Userspace Reader consumes data without blocking kernel thread            |
+-----------------------------------------------------------------------------+
```

1. **Source Compilation**: Pengembang menulis kode pelacak dalam bahasa C terikat pustaka `vmlinux.h` (BTF - BPF Type Format) dan mengompilasinya via Clang/LLVM ke arsitektur instruksi BPF.
2. **Loading via `sys_bpf()`**: Userspace loader memanggil syscall `bpf(BPF_PROG_LOAD, ...)` untuk mengunggah bytecode ke kernel.
3. **Static Verification**: In-kernel Verifier mengecek seluruh alur branch instruction, inisialisasi register, pembatasan akses memory-bounds, dan menjamin bahwa program tidak akan membuat kernel mengalami *crash* atau *deadlock*.
4. **JIT Compilation**: Bytecode yang lolos verifikasi langsung dikonversi menjadi instruksi native mesin (contoh: x86 assembly).
5. **Hook Attachment**: Program ditautkan ke *event point* (misal: `tcp_v4_connect` atau `sys_enter_write`).
6. **Data Streaming**: Saat event terpicu, program mengeksekusi logika di kernel dan menulis data terstruktur ke *BPF Perf/Ring Buffer*, yang kemudian dibaca oleh Userspace daemon secara asinkron.

### Workflow 2: Cgroups v2 Memory Pressure Mitigation via PSI

```
Kernel Memory Saturation Detected
             |
             v
+-----------------------------+
| Memori Bebas Menipis        |
| (Hit Watermark Low)         |
+-----------------------------+
             |
             v
+-----------------------------+       PSI Threshold Terlampaui
| kswapd Mengaktifkan Reclaim | ------------------------------------+
+-----------------------------+                                     |
             |                                                      |
             v                                                      v
+-----------------------------+                        +-------------------------+
| Direct Compaction Terjadi   |                        | systemd-oomd / Daemon   |
| (Stall / Latensi Melonjak)  |                        | Mendeteksi via PSI API  |
+-----------------------------+                        | (/proc/pressure/memory) |
             |                                         +-------------------------+
             v                                                      |
+-----------------------------+                                     v
| OOM Killer Tradisional      |                        +-------------------------+
| Mematikan Proses Secara     |                        | Graceful Mitigation:    |
| Tidak Terprediksi           |                        | Evict Cache, Drain Node,|
+-----------------------------+                        | Restart Worker Terisolir|
                                                       +-------------------------+
```

---

## 6. Analogi & Diagram ASCII

### Analogi NUMA Architecture: Dapur Restoran Bintang Lima

Bayangkan sebuah dapur restoran komersial dengan dua *Chef Station* (CPU Sockets):
- Setiap station memiliki kulkas bumbu pribadi (*Local Memory Node*).
- Jika Chef di Station 1 mengambil bahan dari kulkasnya sendiri, waktu yang dibutuhkan hanya 5 detik.
- Namun, jika bahan habis dan Chef 1 harus berjalan mengambil bahan di kulkas Station 2 (*Remote Memory Node*), ia harus melintasi lorong dapur sempit (*Interconnect Bus*), memakan waktu 20 detik serta menghalangi Chef 2.
- Jika kedua Chef terus-menerus mengambil bahan dari kulkas satu sama lain (*NUMA Thrashing*), seluruh throughput dapur akan anjlok drastis meskipun kapasitas kedua Chef sangat tinggi.

```
========================= ARSITEKTUR MEMORI SISTEM DUAL-SOCKET =========================

        +-----------------------+                       +-----------------------+
        |     CPU SOCKET 0      |                       |     CPU SOCKET 1      |
        | [Core 0]    [Core 1]  |                       | [Core 2]    [Core 3]  |
        | [Core 4]    [Core 5]  |                       | [Core 6]    [Core 7]  |
        +-----------------------+                       +-----------------------+
                    |                                               |
         Local Access: ~60ns                             Local Access: ~60ns
                    |                                               |
                    v                                               v
        +-----------------------+                       +-----------------------+
        |   NUMA NODE 0 (RAM)   | <===================> |   NUMA NODE 1 (RAM)   |
        |    Local to Socket 0  |      UPI / Infinity   |    Local to Socket 1  |
        +-----------------------+      Fabric Link      +-----------------------+
                                    Cross-Node: ~100ns
```

---

## 7. Simple Example & Practical Example

### Simple Example: Menangkap Latensi Disk I/O Berlebih Menggunakan `bpftrace`

Program *one-liner* ini menggunakan `bpftrace` untuk mengukur latensi I/O blok level kernel (`blk_account_io_done`) dan menghasilkan histogram distribusi latensi dalam mikrodetik ($\mu s$).

```bash
# Jalankan tracing latensi blok IO dengan resolusi distribusi logaritmik
sudo bpftrace -e '
kprobe:blk_account_io_start { 
    @start[arg0] = nsecs; 
} 
kprobe:blk_account_io_done /@start[arg0]/ { 
    @lat_us = hist((nsecs - @start[arg0]) / 1000); 
    delete(@start[arg0]); 
}'
```

Output:
```text
Attaching 2 probes...
^C
@lat_us: 
[16, 32)              24 |@@                                                 |
[32, 64)             189 |@@@@@@@@@@@@@@@@                                   |
[64, 128)            512 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@       |
[128, 256)           601 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ |
[256, 512)            82 |@@@@@@@                                            |
[512, 1K)             11 |@                                                  |
[1K, 2K)               2 |                                                   |
```

---

### Practical Example: Production-Grade eBPF Program untuk Mendeteksi TCP Drop di Kernel

Implementasi kode berikut menggunakan framework eBPF modern (CO-RE: *Compile Once – Run Everywhere*) dalam C untuk mendeteksi *packet drops* pada network stack kernel Linux secara real-time.

Simpan file berikut sebagai `tcp_drop_trace.bpf.c`:

```c
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>

// Definisi event data struct yang dikirim ke userspace
struct drop_event_t {
    u32 saddr;
    u32 daddr;
    u16 sport;
    u16 dport;
    u32 reason;
    u32 pid;
    char comm[16];
};

// Buat BPF Ring Buffer untuk streaming event
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256 KB buffer
} events SEC(".maps");

// Tracepoint kfree_skb menangkap sk_buff saat dibebaskan/dibuang kernel
SEC("tracepoint/skb/kfree_skb")
int trace_kfree_skb(struct trace_event_raw_kfree_skb *ctx) {
    struct sk_buff *skb = (struct sk_buff *)ctx->skbaddr;
    struct sock *sk = (struct sock *)ctx->rx_sk;
    
    // Alokasi memori di ring buffer
    struct drop_event_t *event;
    event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        return 0; // Buffer penuh, drop event tracing
    }

    // Ekstraksi PID dan Process Name
    u64 id = bpf_get_current_pid_tgid();
    event->pid = id >> 32;
    bpf_get_current_comm(&event->comm, sizeof(event->comm));
    
    // Baca alasan drop dari konteks tracepoint
    event->reason = ctx->reason;

    // Ambil detail network tuple jika socket valid
    if (sk) {
        BPF_CORE_READ_INTO(&event->saddr, sk, __sk_common.skc_rcv_saddr);
        BPF_CORE_READ_INTO(&event->daddr, sk, __sk_common.skc_daddr);
        BPF_CORE_READ_INTO(&event->sport, sk, __sk_common.skc_num);
        BPF_CORE_READ_INTO(&event->dport, sk, __sk_common.skc_dport);
        event->dport = __builtin_bswap16(event->dport);
    } else {
        event->saddr = 0;
        event->daddr = 0;
        event->sport = 0;
        event->dport = 0;
    }

    // Submit ke user space
    bpf_ringbuf_submit(event, 0);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
```

Simpan file Makefile pendukung sebagai `Makefile`:

```makefile
CLANG ?= clang
CFLAGS ?= -O2 -g -target bpf -D__TARGET_ARCH_x86

all: tcp_drop_trace.bpf.o

tcp_drop_trace.bpf.o: tcp_drop_trace.bpf.c
	$(CLANG) $(CFLAGS) -I/usr/include/$(shell uname -m)-linux-gnu -c $< -o $@

clean:
	rm -f *.o
```

---

### Practical Example: Konfigurasi systemd Slice & Cgroups v2 Terisolasi

Konfigurasi ini membuat cgroup dedicated untuk backend service dengan limitasi memori ketat, I/O throttle, dan integrasi perlindungan PSI OOM.

Simpan sebagai `/etc/systemd/system/production-backend.slice`:

```ini
[Unit]
Description=Slice Alokasi Terisolasi Enterprise Backend
DefaultDependencies=no
Before=slices.target

[Slice]
# Pembatasan Sumber Daya Cgroups v2
MemoryAccounting=true
# Alokasi memori maksimum absolut (Hard Limit)
MemoryMax=16G
# Ambang batas proteksi (Soft Limit) - kernel memprioritaskan mempertahankan memori ini
MemoryLow=8G
# Kernel memicu reclaim agresif sebelum mencapai hard limit
MemoryHigh=14G

# Proteksi OOM Score: -1000 s/d 1000 (Semakin rendah, semakin aman dari OOM Killer)
OOMScoreAdjust=-500

# CPU Quota & Weight
CPUAccounting=true
# 800% setara dengan maksimal 8 Core CPU penuh
CPUQuota=800%
# Weight CFS scheduler: 1 - 10000 (Standar: 100)
CPUWeight=500

# I/O Throttling per Blok Device (contoh major:minor 259:0 = NVMe)
IOAccounting=true
IODeviceWeight=/dev/disk/by-id/nvme-eui.002538b111b01234 1000
IOReadBandwidthMax=/dev/disk/by-id/nvme-eui.002538b111b01234 500M
IOWriteBandwidthMax=/dev/disk/by-id/nvme-eui.002538b111b01234 300M

# Isolasi Task Limits (Mencegah fork-bomb)
TasksAccounting=true
TasksMax=4096
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: P99.99 Latency Spikes pada Core Payment Gateway Platform

#### Konteks & Skala Arsitektur
Sebuah Payment Service Provider memproses 45.000 transaksi pembayaran per detik (*TPS*) di atas cluster bare-metal dual-socket (2x AMD EPYC 7763 64-Core, 512GB RAM, Dual 100GbE Mellanox ConnectX-6). Aplikasi berbasis JVM (Java 21, Shenandoah Low-Pause GC) berjalan langsung di atas sistem operasi tanpa container abstraction untuk meminimalkan *virtualization penalty*.

#### Gejala Masalah
Secara periodik setiap 15 menit, terjadi anomali di mana *latency tail* ($p99.99$) melonjak dari baseline normal 3.2 ms menjadi 420 ms selama interval 5–10 detik. Hal ini menyebabkan cascading timeout pada payment aggregator mitra bank. GC Logs menunjukkan tidak ada *Long GC Pauses* (Shenandoah GC pause tetap di bawah 5 ms).

#### Analisis Akar Masalah (Root Cause Analysis)
1. **Pengecekan Metrik OS Konvensional**: Penggunaan CPU total rata-rata berada pada 45%, sisa memori fisik 180 GB, tidak terdeteksi *paging out* ke swap.
2. **Observasi Menggunakan eBPF (`compactsnoop`)**:
   Dengan menjalankan tracing eBPF terhadap kernel function `compact_zone`, tim engineer mendeteksi lonjakan tajam waktu tunggu eksekusi memori kernel:
   ```text
   COMM: java, PID: 40129, DELAY_MS: 387.41, LATENCY: Direct Compaction Stall
   ```
3. **Investigasi Memori Subsystem**:
   Ditemukan bahwa Linux Kernel **Transparent HugePages (THP)** diset ke konfigurasi bawaan `[always]`. JVM meminta alokasi memori besar, menyebabkan fragmentasi internal pada physical page frames.
   Saat aplikasi membutuhkan halaman 2 MiB kontigu dan memori fisik terfragmentasi, kernel mengalihkan thread aplikasi yang sedang berjalan dari *user mode* ke *synchronous direct compaction* di kernel space, memblokir thread pemroses pembayaran hingga defragmentasi selesai.
4. **NUMA Interconnect Saturation**:
   Perintah `numastat -c java` mengonfirmasi tingginya *numa_miss* dan *other_node* (38% dari total alokasi memori berada di Node 1, sedangkan worker threads aktif berjalan pada Node 0), menyebabkan saturasi bandwith antarsoket Infinity Fabric.

#### Solusi & Remediasi Terstruktur
1. **Nonaktifkan Runtime Direct Compaction pada THP**:
   Ubah policy THP menjadi `madvise` agar kernel hanya mengalokasikan hugepages jika aplikasi memintanya secara eksplisit via `madvise(MADV_HUGEPAGE)`.
   ```bash
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   echo defer+madvise | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
   ```
2. **Penerapan Explicit HugePages (1 GiB Pool)**:
   Alokasikan pool explicit hugepages pada kedua soket saat sistem melakukan booting:
   ```ini
   # /etc/sysctl.d/99-hugepages.conf
   vm.nr_hugepages_mempolicy = 256
   ```
3. **Pinning Thread dan Binding NUMA Memory Node**:
   Konfigurasikan isolation wrapper pada systemd unit menggunakan utilitas `numactl`:
   ```ini
   ExecStart=/usr/bin/numactl --cpunodebind=0 --membind=0 /usr/bin/java -XX:+UseLargePages -Xms128G -Xmx128G -jar payment-core.jar
   ```
4. **Hasil Implementasi**:
   Latensi $p99.99$ turun secara permanen dari 420 ms ke stabil di 2.8 ms di bawah beban 50.000 TPS konstan. Alokasi memori *remote node* turun ke level 0.01%.

---

## 9. Trade-offs

| Aspek Arsitektur | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Paging Memory** | **4 KiB Standard Pages** | **2 MiB / 1 GiB HugePages** | Standar 4 KiB fleksibel dan hemat RAM untuk banyak proses kecil, tetapi menimbulkan TLB misses tinggi pada *in-memory database*. HugePages memangkas TLB misses hingga 90%, namun mengunci (*pin*) physical memory secara statis dan tidak dapat di-swap. |
| **NUMA Node Allocation** | **Interleave Policy (`numactl --interleave=all`)** | **Node Affinity (`--cpunodebind=X --membind=X`)** | Interleave meratakan konsumsi memori ke semua soket, mencegah saturasi satu node tapi membayar latensi konstan lintas soket. Node Affinity memberikan latensi ultra-rendah untuk single-socket instance, namun dapat memicu OOM lokal jika satu node penuh meskipun node lain kosong. |
| **Network Processing** | **Standard Linux Socket Stack** | **XDP (eXpress Data Path)** | Standard stack menyediakan abstraksi keamanan lengkap (iptables, conntrack, routing table). XDP memproses jutaan pps langsung di NIC driver, memotong 90% latency path, namun bypass seluruh fitur Netfilter/Stateful Firewall OS. |
| **Kernel Profiling** | **Core Dumps / Dynamic Ptrace (GDB)** | **eBPF-based Low Overhead Tracing** | Core dump dan Ptrace memberikan inspeksi status variabel userspace terdalam, tetapi membekukan proses target (*high production risk*). eBPF non-intrusif dan aman dijalankan pada *live traffic*, namun dibatasi kompleksitas verifier. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Masalah: Mengabaikan Zone Reclaim Mode pada Sistem Skala Besar
- **Gejala**: Server dengan memori kosong puluhan gigabyte tiba-tiba mengalami *I/O freezing* parah dan thread kswapd memakan 100% CPU.
- **Penyebab**: Nilai `vm.zone_reclaim_mode` bernilai aktif (`1` atau `2`). Kernel mencoba mendaur ulang page cache secara agresif di dalam NUMA node lokal alih-alih mengambil memori kosong yang melimpah dari NUMA node tetangga.
- **Solusi**:
  ```bash
  # Set zona memori ke mode global allocation (reclaim dimatikan)
  sudo sysctl -w vm.zone_reclaim_mode=0
  ```

### 2. Masalah: Verifier Rejection pada Program eBPF Modern
- **Gejala**: Saat menjalankan deployment eBPF tracer kustom, loader gagal dengan pesan error:
  `R1 invalid mem access 'inv' ... processed 1000001 insns, stack depth 512 ... permission denied`.
- **Penyebab**: Kode program eBPF Anda memiliki loop variabel yang batas maksimalnya tidak dapat dihitung oleh in-kernel static verifier, atau Anda mengakses pointer dari pointer tanpa melakukan validasi null-check atau pembacaan menggunakan macro `BPF_CORE_READ()`.
- **Solusi**:
  Pastikan setiap dereferensi pointer diverifikasi secara eksplisit dan batas loop di-*unroll* menggunakan direktif kompilator:
  ```c
  #pragma unroll
  for (int i = 0; i < 8; i++) {
      // bounded operations
  }
  ```

### 3. Masalah: Packet Drops Tersembunyi pada RX Ring Buffer Kartu Jaringan
- **Gejala**: Aplikasi mencatat hilangnya konektivitas TCP secara intermiten (*connection timeout*), namun `top` menunjukkan utilisasi CPU masih di bawah 60%.
- **Penyebab**: RX Ring Buffer pada Network Interface Controller (NIC) terisi penuh karena SoftIRQ (ksoftirqd) tidak sempat mengosongkan paket dari buffer ke socket queue aplikasi.
- **Troubleshooting & Remediasi**:
  Periksa statistik drop hardware:
  ```bash
  ethtool -S eth0 | grep -E "drop|over_errors|missed"
  ```
  Perbesar ukuran ring buffer NIC ke batas hardware maksimum:
  ```bash
  # Cek batas maksimal hardware
  ethtool -g eth0
  # Set RX dan TX ring buffer ke batas maksimal (contoh: 4096)
  sudo ethtool -G eth0 rx 4096 tx 4096
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis Linux Bare-Metal/Hypervisor Node ke cluster produksi Tier-1:

### Operating System & Kernel Core Tuning (`/etc/sysctl.d/99-enterprise-core.conf`)
- [ ] Nonaktifkan swapiness agresif: `vm.swappiness = 1` atau `0` (untuk dedicated latency-critical).
- [ ] Atur dirty page background writeback agar tidak terjadi buffer-flushing pause:
  ```ini
  vm.dirty_background_ratio = 5
  vm.dirty_ratio = 10
  ```
- [ ] Perbesar file descriptors limit sistem:
  ```ini
  fs.file-max = 2097152
  ```
- [ ] Optimalkan batas IPC dan PID ceiling:
  ```ini
  kernel.pid_max = 4194304
  ```

### High-Performance Networking Tuning (`/etc/sysctl.d/99-enterprise-network.conf`)
- [ ] Tingkatkan ukuran backlog koneksi baru:
  ```ini
  net.core.somaxconn = 65535
  net.core.netdev_max_backlog = 65535
  ```
- [ ] Konfigurasi TCP Dynamic Buffer Window (Min, Default, Max):
  ```ini
  net.ipv4.tcp_rmem = 4096 87380 16777216
  net.ipv4.tcp_wmem = 4096 65536 16777216
  ```
- [ ] Gunakan algoritma TCP BBR Congestion Control:
  ```ini
  net.core.default_qdisc = fq
  net.ipv4.tcp_congestion_control = bbr
  ```
- [ ] Aktifkan TCP Fast Open:
  ```ini
  net.ipv4.tcp_fastopen = 3
  ```

### Resource Slicing & Monitoring
- [ ] Pastikan Cgroups v2 aktif sebagai *default hierarchy* (tambahkan flag kernel boot: `systemd.unified_cgroup_hierarchy=1`).
- [ ] Pasang `systemd-oomd` yang terkonfigurasi memonitor metrik `/proc/pressure/memory`.
- [ ] Atur CPU affinity dan IRQ balancing (hindari IRQ network terkonsentrasi hanya di CPU0):
  ```bash
  systemctl enable --now irqbalance
  ```

---

## 12. Hands-on Practice

Langkah praktikum terstruktur ini dirancang untuk dieksekusi pada lingkungan lab Linux (Ubuntu 22.04/24.04 atau RHEL 9) dengan hak akses root. Seluruh file akan disimpan di subdirektori `hands-on/m02/`.

### Persiapan Workspace
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 1: Eksplorasi Cgroups v2 Unified Tree dan Pressure Metrics
1. Verifikasi tipe filesystem cgroup pada sistem operasi Anda:
   ```bash
   mount | grep cgroup2
   # Output harus: cgroup2 on /sys/fs/cgroup type cgroup2
   ```
2. Buat grup sumber daya pengujian secara manual:
   ```bash
   sudo mkdir -p /sys/fs/cgroup/perf-test-group
   ```
3. Konfigurasikan pembatasan memori maksimum sebesar 256 MiB:
   ```bash
   echo "268435456" | sudo tee /sys/fs/cgroup/perf-test-group/memory.max
   echo "0" | sudo tee /sys/fs/cgroup/perf-test-group/memory.swap.max
   ```
4. Pantau Pressure Stall Information (PSI) grup tersebut secara streaming:
   ```bash
   cat /sys/fs/cgroup/perf-test-group/memory.pressure
   ```

### Langkah 2: Simulasi Memory Stress & Observasi PSI
1. Buat script pembuat beban memori menggunakan Python (`memory_allocator.py`):
   ```python
   # hands-on/m02/memory_allocator.py
   import time
   import sys

   print("Allocating memory in chunk...")
   data = []
   try:
       for i in range(400): # Mencoba alokasi ~400MB
           data.append(b'x' * (1024 * 1024))
           time.sleep(0.01)
   except MemoryError:
       print("Caught MemoryError inside userspace!")
       sys.exit(1)
   print("Allocation complete without OOM.")
   ```
2. Jalankan script tersebut di bawah naungan cgroup yang telah dibuat:
   ```bash
   # Attach terminal ini ke cgroup target
   echo $$ | sudo tee /sys/fs/cgroup/perf-test-group/cgroup.procs
   
   # Eksekusi proses dan lihat reaksi kernel
   python3 memory_allocator.py
   ```
3. Periksa kernel dmesg untuk melihat apakah mekanisme Linux cgroup-aware OOM Killer terpicu secara terisolasi:
   ```bash
   dmesg -T | grep -E -i "oom[-_]killer|killed process" | tail -n 15
   ```

### Langkah 3: Observasi Kernel Scheduling Runtime Menggunakan `perf`
1. Tangkap profil performa thread kernel selama 10 detik saat sistem bekerja:
   ```bash
   sudo perf record -F 99 -a -g -- sleep 10
   ```
2. Tampilkan laporan pemanggilan fungsi kernel yang paling membebani CPU:
   ```bash
   sudo perf report --stdio -n --percent-limit 2.0
   ```

---

## 13. Exercises

### Level: Easy
1. Gunakan perintah `sysctl` untuk membaca nilai buffer jaringan saat ini (`net.ipv4.tcp_wmem`). Hitung berapa megabyte alokasi maksimum yang diizinkan untuk single stream write TCP.
2. Identifikasi apakah NUMA aktif di mesin pengujian Anda menggunakan perintah `numactl --hardware` atau isi dari direktori `/sys/devices/system/node/`. Catat jumlah soket dan persebaran alokasi CPU core.

### Level: Medium
1. Buat systemd service file bernama `heavy-worker.service` yang menjalankan infinite loop bash script. Batasi proses tersebut dalam Cgroups v2 agar:
   - Menggunakan maksimal 25% dari satu core CPU (`CPUQuota=25%`).
   - Tidak boleh mengonsumsi RAM lebih dari 128 MiB.
   Verifikasi batas tersebut bekerja dengan memantau `systemd-cgtop`.
2. Gunakan `bpftrace` untuk mengukur durasi waktu eksekusi syscall `sys_enter_openat` dan identifikasi 3 proses executable userspace teratas yang paling sering membuka file di sistem Anda.

### Level: Hard
1. Buat skrip audit performa yang memantau metrik file `/proc/pressure/io`. Jika metrik stall rata-rata (`avg10`) melampaui angka ambang batas 15.00 selama lebih dari 3 detik berturut-turut, script secara otomatis:
   - Mencatat output status proses top I/O melalui `iotop -b -n 1`.
   - Mengambil trace stack trace block layer menggunakan `bpftrace` selama 5 detik.
   - Menghasilkan alert diagnostik terstruktur ke file `/var/log/io-pressure-incident.json`.

---

## 14. Challenge: Latency Triage Mystery

### Skenario Lapangan
Anda ditugaskan sebagai Lead Site Reliability Engineer pada bank multinasional. Sebuah cluster Apache Kafka yang memproses transaksi perbankan tiba-tiba mengalami *cluster degradation*. Tiga broker utama mengalami *OutOfMemoryError* non-JVM (kernel mematikan broker secara acak), dan latensi komunikasi antar broker melonjak 10x lipat.

### Kondisi Awal Sistem
- OS: RHEL 9 (Kernel 5.14+).
- Hardware: 128 vCPU, 512 GB RAM, 4x 3.84TB NVMe SSD U.2 RAID 10.
- Swap: Dimatikan total (`swapoff -a`).
- File `/proc/meminfo` menunjukkan:
  - `MemTotal`: 527834212 kB
  - `MemFree`: 12431200 kB
  - `Buffers`: 23100 kB
  - `Cached`: 475829100 kB
  - `Active(file)`: 400120300 kB
  - `Inactive(file)`: 75708800 kB
  - `Slab`: 32890000 kB
  - `SUnreclaim`: 28400100 kB

### Instruksi Misi Anda:
1. **Analisis Anomali**: Bedah parameter `/proc/meminfo` di atas. Mengapa JVM broker Kafka terbunuh OOM padahal `Cached` memori mencapai 475 GB (di mana secara teori Linux Page Cache dapat dibebaskan kapan saja)?
2. **Kambing Hitam Kernel**: Apa yang menyebabkan tingginya nilai `SUnreclaim` (Slab Unreclaimable) hingga mencapai puluhan gigabyte? Tools diagnosis tingkat rendah apa yang Anda gunakan untuk menginspeksi isi objek internal Slab allocator tersebut?
3. **Formulasi Solusi Permanen**: Rancang skema arsitektur tuning parameter kernel (`sysctl`), filesystem mounts, serta orkestrasi memory management untuk mencegah masalah ini berulang secara permanen tanpa perlu melakukan reboot berkala pada broker Kafka.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa fungsi utama dari BPF In-Kernel Verifier?**
   - *Jawaban*: Memastikan kode instruksi eBPF yang diunggah dari user space bersifat aman untuk dijalankan di ruang kernel, tidak memiliki loop tak terbatas, tidak mengakses memori sembarangan (*out-of-bounds*), dan tidak mengakibatkan kernel panic.
2. **Apa perbedaan mendasar antara Hard Limit (`memory.max`) dan Soft Limit (`memory.high`) pada Cgroups v2?**
   - *Jawaban*: `memory.high` memicu proses background reclaim dan memperlambat (throttling) proses pengguna saat terlampaui tanpa mematikannya, sedangkan `memory.max` adalah ambang batas kaku di mana kernel akan langsung memicu Out-Of-Memory (OOM) Killer jika memori tidak dapat direclaim lagi.
3. **Mengapa Explicit HugePages tidak dapat di-swap out ke disk oleh Linux Kernel?**
   - *Jawaban*: Karena Explicit HugePages dipin (*pinned*) secara permanen di physical memory pool sejak dialokasikan untuk menjamin persistensi latensi rendah dan memotong overhead TLB lookup.
4. **Apa implikasi performa dari context switch syscall yang sering?**
   - *Jawaban*: Menyebabkan pemborosan siklus clock CPU akibat penyimpanan/pemulihan register CPU, flushing instruksi pipeline, dan degradasi CPU L1/L2 cache locality.
5. **Perintah apa yang digunakan untuk melihat pemetaan alokasi soket NUMA fisik dari suatu proses yang sedang berjalan?**
   - *Jawaban*: `numastat -p <PID>` atau memeriksa isi `/proc/<PID>/numa_maps`.

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Pada sistem operasi Linux modern, apa perbedaan mekanisme pelacakan ftrace, kprobes, dan tracepoints?**
   - *Jawaban*: Tracepoints adalah penanda statis yang disematkan langsung oleh developer kernel di source code (*stable ABI*). Kprobes adalah instrumen dinamis yang memodifikasi instruksi kernel assembly saat runtime (*unstable ABI*). Ftrace adalah framework tracing bawaan kernel untuk melacak alur eksekusi pemanggilan fungsi (*function graph*).
2. **Mengapa arsitektur I/O modern beralih dari model `epoll` ke antarmuka `io_uring`?**
   - *Jawaban*: `epoll` bersifat *readiness-based* dan tetap membutuhkan syscall terpisah untuk membaca/menulis data setelah socket siap (menyebabkan context switch). `io_uring` bersifat *completion-based* dan menggunakan dua *ring buffer lockless* bersama di shared-memory, memungkinkan I/O dieksekusi secara asinkron murni tanpa transisi syscall berulang kali.
3. **Jelaskan peran metrik Pressure Stall Information (PSI) kategori `full` vs `some`!**
   - *Jawaban*: `some` mengindikasikan bahwa sebagian thread/task mengalami delay akibat kelangkaan resource (sementara thread non-blocking lain tetap berjalan). `full` mengindikasikan seluruh thread yang dapat dieksekusi dalam sistem/cgroup terhenti total karena menunggu sumber daya dilepaskan.
4. **Apa yang terjadi secara mekanis ketika kernel parameter `vm.swappiness` diatur ke nilai `0`?**
   - *Jawaban*: Kernel tidak akan men-swap memori anonim (*anonymous memory*) sama sekali sampai kapasitas page cache memori bebas dan file-backed pages habis mencapai ambang batas absolut *high-watermark*.
5. **Bagaimana cara kerja teknologi XDP (*eXpress Data Path*) sehingga mampu memproses 20+ juta paket per detik pada interface 100GbE?**
   - *Jawaban*: XDP mengeksekusi program eBPF tepat di driver network interface card sebelum buffer sistem operasi (`sk_buff`) dialokasikan dan sebelum paket memasuki stack IP routing atau sub-layer firewall Linux.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: Diagnosa Packet Loss
Sebuah aplikasi web berbasis Go melaporkan latensi tinggi. Metrik server menunjukkan utilisasi CPU 20% dan RAM 30%. Namun, log kernel `dmesg` menunjukkan peringatan:
`TCP: Possible SYN flooding on port 443. Sending cookies. Check SNMP counters.`
Aplikasi tidak sedang terkena serangan siber DDOS.
- **Analisis & Tindakan Perbaikan**:
  - *Akar Masalah*: Listen backlog socket aplikasi terisi penuh (*overflow*). Aplikasi pengguna memproses koneksi baru lebih lambat daripada laju koneksi SYN masuk, sehingga parameter `net.core.somaxconn` sistem atau parameter `backlog` pemanggilan `listen()` pada kode Go terlampaui.
  - *Solusi*: Tingkatkan nilai `net.core.somaxconn` dan `net.ipv4.tcp_max_syn_backlog` pada `sysctl`, serta sesuaikan konfigurasi internal HTTP server parameter backlog pada aplikasi.

#### Skenario 2: Filesystem Lock Contention
Database Postgres mengalami lonjakan latensi commit transaksi secara tiba-tiba pada drive NVMe berkecepatan tinggi. Perintah `vmstat 1` menunjukkan kolom `b` (blocked processes) bernilai ratusan, dan kolom `wa` (I/O wait) mencapai 40%, meskipun utilisasi throughput NVMe masih jauh di bawah batas IOPS maksimum disk.
- **Analisis & Tindakan Perbaikan**:
  - *Akar Masalah*: Terjadi antrean penulisan sinkron (*fsync / synchronous write barrier*) yang menumpuk akibat *dirty pages* yang terlalu lama ditahan di page cache sistem operasi sebelum akhirnya di-*flush* secara masif sekaligus oleh daemon `pdflush`/`flush`.
  - *Solusi*: Turunkan ambang batas dirty memory pada sysctl: ubah `vm.dirty_background_ratio` menjadi `3` dan `vm.dirty_ratio` menjadi `6` agar flushing I/O ke storage dilakukan secara bertahap dan berkelanjutan, mencegah fenomena *I/O freezing spike*.

#### Skenario 3: Cross-NUMA Degradation pada AI Inference Engine
Model deep learning yang dideploy menggunakan TensorRT pada bare-metal server (dual-socket GPU server) menghasilkan latency throughput 50% lebih lambat dibandingkan saat dites pada workstation single-socket developer, meskipun GPU dan CPU yang digunakan identik.
- **Analisis & Tindakan Perbaikan**:
  - *Akar Masalah*: Instance aplikasi berjalan pada Socket 0, namun PCIe bus tempat GPU fisik tertancap terhubung langsung ke memory controller internal Socket 1. Seluruh operasi DMA (*Direct Memory Access*) dan transfer frame harus melintasi interconnect fabric antar CPU, memangkas bandwidth PCIe hingga separuhnya (*NUMA unbalance*).
  - *Solusi*: Identifikasi letak PCIe GPU menggunakan `lspci -vvv` untuk melihat `NUMA node: 1`. Jalankan proses inferensi menggunakan perintah isolasi: `numactl --cpunodebind=1 --membind=1 <command>` agar seluruh instruksi CPU, alokasi memori RAM, dan komunikasi bus PCIe GPU berada pada satu domain node fisik yang identik.

---

## 16. Summary

1. **Kernel Linux Adalah Sistem Deterministik yang Dapat Diprogram**: Melalui eBPF, administrator dan software engineer tidak lagi memperlakukan kernel sebagai *black box*. Observabilitas, tracing, dan rekayasa routing jaringan dapat disuntikkan secara dinamis langsung pada kernel space dengan garansi keamanan in-kernel verifier.
2. **Hierarki Sumber Daya Modern Bersandar pada Cgroups v2 & PSI**: Pengelolaan multi-tenant dan isolasi microservices tingkat enterprise memerlukan arsitektur *unified hierarchy*. Penggunaan metrik Pressure Stall Information (PSI) menyediakan deteksi dini saturasi CPU, Memory, dan Storage sebelum degradasi sistem mencapai status kegagalan fatal OOM.
3. **Efisiensi Hardware Skala Besar Bergantung pada Cache & NUMA Locality**: Di era komputasi multi-socket modern, alokasi memori lokal vs remote menentukan p99 latency aplikasi. Mengabaikan NUMA topology, Transparent HugePages fragmentation, dan alokasi ring buffer kartu jaringan akan membatalkan performa arsitektur secanggih apa pun yang dibangun di atas layer aplikasi.