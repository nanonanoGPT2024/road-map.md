# BAB 02: Arsitektur Sistem Operasi & Linux Internals
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah siklus hidup eksekusi instruksi dari *user space* (Ring 3) ke *kernel space* (Ring 0) melalui System Call interface dan interupsi perangkat keras.
- Menganalisis dan mengoptimasi penjadwalan proses pada Linux Completely Fair Scheduler (CFS) serta interaksinya dengan mekanisme isolasi cgroups v2 di lingkungan kontainer orkestrasi skala besar.
- Menjelaskan arsitektur subsistem memori Linux secara granular, mencakup *page allocation*, *virtual memory management*, *page reclaim*, *kswapd*, hingga mitigasi deterministik *Out-Of-Memory* (OOM) Killer.
- Melacak *network packet path* end-to-end di dalam kernel (Driver -> Ring Buffer -> NAPI -> SoftIRQ -> Network Stack -> Socket Buffer) untuk mengeliminasi latensi ekor (*tail latency*) pada microservices.
- Mengoperasikan *tooling observability* modern berbasis eBPF (*Extended Berkeley Packet Filter*) dan `perf` untuk mendiagnosis degradasi performa I/O dan CPU pada tingkat kernel secara non-invasif di lingkungan produksi.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda harus memahami:
- Arsitektur komputer dasar: Register CPU, Cache (L1/L2/L3), TLB (*Translation Lookaside Buffer*), dan topologi NUMA (*Non-Uniform Memory Access*).
- Konsep dasar sistem operasi: Thread vs Process, Virtual Memory, File Descriptors, dan TCP/IP stack.
- Kemahiran baris perintah Linux tingkat lanjut (`awk`, `sed`, `ip`, `ss`, `strace`, `sysctl`).
- Pengalaman dasar dalam deployment kontainer (Docker/Kubernetes) dan pemahaman isolasi Linux Namespaces.

---

### 3. Concept & Internal Architecture

Kernel Linux adalah kernel monolitik modular yang bertanggung jawab mengelola abstraksi perangkat keras dan menyediakan antarmuka terpadu bagi aplikasi *user space*. 

```
+-----------------------------------------------------------------------+
| USER SPACE (Ring 3)                                                   |
|  [ Applications / Microservices ]       [ System Daemons: systemd ]   |
|  [ POSIX API / Glibc / Musl     ]       [ Runtimes: Go, JVM, Node ]   |
+-----------------------------------v-----------------------------------+
| HARDWARE/KERNEL BOUNDARY (Syscall: sysenter/syscall instruction)      |
+-----------------------------------v-----------------------------------+
| KERNEL SPACE (Ring 0)                                                 |
|  +--------------------+  +-------------------+  +-------------------+ |
|  | Process Scheduler  |  | Memory Management |  | Virtual FS (VFS)  | |
|  | (CFS / EEVDF, RT)  |  | (Buddy, Slab/Slub)|  | (ext4, XFS, btrfs)| |
|  +---------+----------+  +---------+---------+  +---------+---------+ |
|            |                       |                      |           |
|  +---------v-----------------------v----------------------v---------+ |
|  | Networking Stack (Netfilter, TCP/IP, qdisc, NAPI, SoftIRQ)       | |
|  +---------------------------------+--------------------------------+ |
|                                    |                                  |
|  +---------------------------------v--------------------------------+ |
|  | Device Drivers, eBPF Engine, Security Subsystems (SELinux, LSM)  | |
|  +---------------------------------+--------------------------------+ |
+-----------------------------------v-----------------------------------+
| HARDWARE                                                              |
|  [ CPU Core / APIC ]    [ RAM / MMU ]    [ NIC Controller ]   [ NVMe ]|
+-----------------------------------------------------------------------+
```

#### A. Kernel Space vs. User Space & Trap Mechanisms
CPU modern memberlakukan pemisahan hak akses menggunakan level proteksi piranti keras (*rings*). Linux mengeksploitasi dua tingkat:
- **Ring 3 (User Space):** Tempat aplikasi berjalan dengan akses instruksi CPU dan memori terbatas. Eksekusi instruksi khusus (*privileged instructions*) seperti manipulasi tabel halaman memori atau akses langsung ke perangkat keras dilarang oleh CPU.
- **Ring 0 (Kernel Space):** Kode kernel memiliki akses tak terbatas ke seluruh instruksi CPU dan register fisik sistem.

Ketika aplikasi *user space* membutuhkan layanan kernel (misalnya membaca file melalui `read()`), alur eksekusi berpindah melalui instruksi `syscall` (pada x86_64). Hal ini memicu transisi hak istimewa (*privilege transition*):
1. Arsitektur CPU menyimpan register konteks *user space* (`RIP`, `RSP`, `RFLAGS`) ke stack kernel proses bersangkutan.
2. CPU beralih ke Mode Ring 0 dan melompat ke alamat yang telah ditentukan dalam register MSR (*Model-Specific Register*) `IA32_LSTAR`.
3. Dispatcher kernel (`entry_SYSCALL_64`) mencari nomor *system call* di tabel sistem `sys_call_table` dan mengeksekusi fungsi kernel terkait (misal: `sys_read`).
4. Setelah selesai, instruksi `sysretq` memulihkan konteks register dan menurunkan hak akses CPU kembali ke Ring 3.

#### B. Linux Process Scheduler: Completely Fair Scheduler (CFS) & EEVDF
Unit eksekusi dasar di Linux diwakili oleh struktur data `task_struct`. Tidak ada perbedaan struktural fundamental antara *thread* dan *process*; sebuah thread hanyalah `task_struct` yang berbagi ruang alamat memori virtual (`mm_struct`) dan tabel *file descriptor* (`files_struct`) dengan proses induknya (`CLONE_VM | CLONE_FILES`).

CFS membagi waktu CPU berdasarkan konsep *virtual runtime* (`vruntime`), yang dihitung sebagai:

$$\Delta vruntime = \Delta exec\_time \times \frac{NICE\_0\_LOAD}{task\_weight}$$

- Setiap tugas diposisikan dalam struktur pohon merah-hitam (*Red-Black Tree*). Tugas dengan `vruntime` terendah berada di sisi paling kiri (*leftmost node*).
- Scheduler secara kontinu memilih node paling kiri untuk dieksekusi selanjutnya.
- Pada Kernel 6.6+, Linux mulai mengadopsi EEVDF (*Earliest Eligible Virtual Deadline First*) untuk menggantikan CFS murni, mengoptimalkan penanganan latensi dengan membedakan *lag time* dan alokasi *slice*.
- **CPU Cgroups Throttling:** Pada cgroups v2 (`cpu.max`), bandwidth CPU dibatasi menggunakan kuota waktu dalam satu periode (misal: 100ms). Jika sebuah cgroup menghabiskan kuotanya sebelum periode selesai, timer kernel (`hrtimer`) akan menghapus tugas dari *runqueue* aktif, memicu lonjakan latensi ekor (*tail latency*) drastis tanpa terlihat adanya saturasi CPU 100% pada node.

#### C. Arsitektur Memori Virtual: Paging, Slab Allocator, dan OOM Killer
Subsistem memori memetakan alamat memori virtual proses ke alamat fisik memori (*physical frames*) menggunakan *Multi-Level Page Tables* (4 tingkat atau 5 tingkat dengan Paging57).

1. **Buddy System:** Mengelola halaman memori fisik bebas dalam blok berukuran eksponensial basis 2 ($2^n \times 4\text{ KB}$).
2. **Slab/Slub Allocator:** Menghindari fragmentasi internal untuk struktur objek kernel yang kecil dan sering dialokasikan (`task_struct`, `mm_struct`, `inode`, `dentry`).
3. **Page Cache vs. Anonymous Memory:**
   - **Page Cache:** Memetakan blok file di disk ke memori RAM untuk mempercepat I/O file. Dapat didrop/dikosongkan kapan saja jika halaman dalam status *clean*.
   - **Anonymous Memory:** Memori alokasi dinamis program (Heap, Stack). Memori ini tidak memiliki keterkaitan dengan disk file dan harus dipindahkan ke partisi *Swap* jika kernel mengalami tekanan alokasi (*memory pressure*).
4. **Out-of-Memory (OOM) Killer:**
   Ketika *watermark* alokasi halaman memori mencapai level kritis (`WMARK_MIN`) dan kswapd gagal merebut kembali (*reclaim*) memori yang cukup, kernel memicu OOM Killer. Skor proses dihitung berdasarkan formula:

   $$Points = \text{Total RSS} + \text{Page Tables} + \text{Swap Usage}$$
   
   Nilai ini kemudian dinormalisasi terhadap total memori yang tersedia menjadi nilai `oom_score` (0 - 1000) dan disesuaikan secara linier dengan konfigurasi `oom_score_adj` (-1000 hingga 1000). Tugas dengan skor tertinggi akan dieksekusi dengan sinyal `SIGKILL`.

---

### 4. Why & What

Dalam platform berskala masif, lapisan abstraksi runtime bahasa pemrograman tingkat tinggi (seperti Go runtime, JVM, Node.js) dan runtime kontainer (containerd, CRI-O) sering kali mengaburkan mekanika sistem operasi yang sebenarnya.

```
+-------------------------------------------------------------------------+
| Lapisan Abstraksi                                                      |
|   App Code -> Runtime Engine -> Container Shim -> Syscall -> Kernel OS  |
|                                                               ^         |
| Kegagalan Performa / Latensi Terjadi di Sini -----------------+         |
+-------------------------------------------------------------------------+
```

#### Mengapa SRE Wajib Menguasai Linux Internals?
1. **Kebocoran Abstraksi (*Leaky Abstractions*):** Ketika microservice Anda mengalami *timeout* HTTP secara acak pada p99, log aplikasi sering kali tidak mencatat *error*. Akar masalah biasanya berada di level OS: *CFS scheduling throttle*, antrean TCP *listen backlog* penuh, *SoftIRQ core saturation*, atau interupsi *memory compaction* di kernel.
2. **Optimasi Biaya Komputasi (*Cost Efficiency*):** Menjalankan cluster Kubernetes tanpa memahami bagaimana Linux mengalokasikan CPU core atau memori hanya akan berujung pada strategi *over-provisioning* yang boros anggaran infrastruktur cloud.
3. **Post-Mortem Tingkat Lanjut:** Masalah tingkat kernel seperti *D-state processes* (I/O hang tak terputus), fragmentasi memori, atau kebocoran *socket buffer* tidak dapat diselesaikan hanya dengan *restarting container pod*.

---

### 5. How (Workflow Detail)

Berikut adalah alur lengkap end-to-end penanganan paket jaringan ingress (*ingress network path*) di tingkat kernel hingga diterima oleh aplikasi:

```
[ NIC Hardware ]
       | (Paket fisik tiba dari jaringan)
       v
[ DMA Transfer ] ---> Menyalin data langsung ke Host RAM (Rx Ring Buffer)
       |
       v
[ Hard IRQ (Hardware Interrupt) ] ---> Dikirim NIC ke CPU Core melalui APIC
       |
       v
[ CPU Interrupt Handler ]
       |
       +---> Menonaktifkan interrupt hardware dari NIC (Interrupt Mitigation)
       +---> Menjadwalkan NAPI (New API) poll loop
       +---> Memanggil raise_softirq(NET_RX_SOFTIRQ)
       |
       v
[ ksoftirqd / SoftIRQ Execution Context ]
       |
       v
[ napi_gro_receive() ] ---> Menggabungkan frame TCP (Generic Receive Offload)
       |
       v
[ __netif_receive_skb() ]
       |
       +---> tc (Traffic Control) & Ingress qdisc evaluation
       +---> Netfilter Hook (iptables / nftables PREROUTING)
       |
       v
[ ip_rcv() ] ---> Verifikasi header IP, Checksum, Fragment reassembly
       |
       v
[ ip_local_deliver() ] ---> Transport Layer Dispatch
       |
       v
[ tcp_v4_rcv() ] ---> Verifikasi TCP header, TCP Sequence, State Machine
       |
       v
[ sk->sk_data_ready() ]
       |
       +---> Memasukkan data ke Socket Receive Buffer (sk_receive_queue)
       +---> Membangunkan proses yang tertidur di epoll_wait()
       |
       v
[ User Space Application ]
       |
       +---> Terjaga dari epoll_wait()
       +---> Memanggil syscall read() / recv()
       +---> Data disalin dari Kernel sk_buff ke User Buffer
```

Detail tahapan eksekusi:
1. **DMA Transfer:** NIC menulis data paket langsung ke area RAM host yang ditunjuk oleh *Rx Descriptor Ring Buffer* tanpa keterlibatan CPU.
2. **Hard IRQ:** NIC memicu sinyal interupsi perangkat keras ke CPU. CPU menangguhkan eksekusi thread saat itu, berpindah ke ISR (*Interrupt Service Routine*).
3. **NAPI Poll:** ISR mematikan interupsi NIC untuk mencegah *interrupt storm*, lalu memicu *software interrupt* `NET_RX_SOFTIRQ`.
4. **SoftIRQ Processing:** Thread kernel `ksoftirqd/x` atau penangan interrupt lokal menjalankan polling NAPI (`napi_poll`), mengambil paket dari *Ring Buffer* dan membungkusnya ke dalam struktur data kernel universal: `sk_buff` (*Socket Buffer*).
5. **Protocol Stack Processing:** Paket melewati filter keamanan (*Netfilter/ebpf*), pemrosesan IP routing, verifikasi protokol TCP, hingga payload diletakkan ke *receive queue* milik soket yang terhubung.
6. **Userspace Wakeup:** Kernel membangunkan thread aplikasi yang terblokir di *system call* `epoll_wait()`, mengizinkan aplikasi menyalin data dari kernel space ke memori aplikasi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Skala Industri

Bayangkan sebuah dapur restoran ultra-sibuk untuk memahami interaksi komponen OS:
- **CPU Core** = Koki (*Chef*).
- **User Space** = Pelayan yang mencatat pesanan pelanggan di area depan restoran.
- **Kernel Space** = Area persiapan dapur steril tempat alat tajam dan api berada.
- **System Call** = Jalur pesanan berbentuk loket berputar di mana pelayan menyerahkan tiket ke koki (melewati batas hak akses).
- **CFS Scheduler** = Manajer dapur yang mengalokasikan timer menit untuk setiap koki agar semua pesanan pelanggan diproses secara adil bergiliran.
- **Ring Buffer** = Sabuk berjalan (*conveyor belt*) tempat bahan makanan masuk dari truk logistik luar (NIC).
- **SoftIRQ (ksoftirqd)** = Asisten koki yang mengambil piring kotor/bahan dari ban berjalan ke meja persiapan secara borongan agar sang koki utama tidak terinterupsi setiap satu butir telur datang.

```
       USER SPACE                       KERNEL SPACE
+-----------------------+        +--------------------------+
|  Pelayan (Aplikasi)   |        |   Koki Dapur (Kernel)    |
|                       |        |                          |
|  Order Item Baru      |        |  Eksekusi Aman           |
|          |            |        |  (Raw Disk, Raw Memory)  |
|          v            |        |            ^             |
|   +---------------+   | Syscall|            |             |
|   |  Loket Tiket  |===+========+============+             |
|   +---------------+   |        |                          |
+-----------------------+        +--------------------------+
                                              ^
                                              | Mengambil barang
                                 +------------+-------------+
                                 | Ban Berjalan             |
                                 | (Ring Buffer / NAPI)     |
                                 +--------------------------+
                                              ^
                                              | Truk Pasokan
                                        [ NIC Hardware ]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Tracing Syscall Latency Menggunakan `bpftrace`
Skrip *one-liner* ini mengukur latensi eksekusi *system call* `sys_enter_write` secara real-time pada host Linux tanpa memodifikasi kode biner aplikasi.

```bash
# Tracing distribusi latensi syscall write() dalam microsecond (us)
sudo bpftrace -e '
tracepoint:syscalls:sys_enter_write {
    @start[tid] = nsecs;
}
tracepoint:syscalls:sys_exit_write /@start[tid]/ {
    @lat_us = hist((nsecs - @start[tid]) / 1000);
    delete(@start[tid]);
}
INTERVAL:s:5 {
    print(@lat_us);
    clear(@lat_us);
}'
```

#### B. Practical Example: Production-Grade eBPF Script untuk Mendeteksi Latensi Antrean Penjadwal CPU (Runqueue Latency)
Dalam sistem terdistribusi, lonjakan latensi sering diakibatkan oleh thread yang siap jalan (*runnable*) namun harus menunggu CPU core kosong. Program berbasis Python-BCC di bawah ini memonitor fenomena *Runqueue Latency* (Scheduler Delay):

Simpan berkas berikut sebagai `sched_latency_monitor.py`:

```python
#!/usr/bin/env python3
"""
SRE Production Tool: Monitor Runqueue Latency (Scheduler Wait Time)
Target: Mengidentifikasi thread starving akibat CFS throttling atau CPU saturation.
"""

from bcc import BPF
import time
import sys

bpf_source = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

BPF_HASH(start_time, u32, u64);
BPF_HISTOGRAM(runqueue_lat);

// Trace saat thread ditambahkan ke runqueue
TRACEPOINT_PROBE(sched, sched_wakeup) {
    u32 pid = args->pid;
    u64 ts = bpf_ktime_get_ns();
    start_time.update(&pid, &ts);
    return 0;
}

// Trace saat thread yang baru dibuat masuk ke runqueue
TRACEPOINT_PROBE(sched, sched_wakeup_new) {
    u32 pid = args->pid;
    u64 ts = bpf_ktime_get_ns();
    start_time.update(&pid, &ts);
    return 0;
}

// Trace saat konteks beralih: thread mulai dieksekusi di core CPU
TRACEPOINT_PROBE(sched, sched_switch) {
    u32 next_pid = args->next_pid;
    u64 *tsp, delta_us;

    tsp = start_time.lookup(&next_pid);
    if (tsp != 0) {
        delta_us = (bpf_ktime_get_ns() - *tsp) / 1000;
        runqueue_lat.increment(bpf_log2l(delta_us));
        start_time.delete(&next_pid);
    }
    return 0;
}
"""

def main():
    print("[INFO] Mengompilasi dan menginjeksi program eBPF ke kernel...")
    b = BPF(text=bpf_source)
    print("[INFO] Monitoring aktif. Tekan Ctrl+C untuk keluar.")

    try:
        while True:
            time.sleep(5)
            print("\n" + "=" * 60)
            print(f"Distribusi Runqueue Latency (us) - Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            b["runqueue_lat"].print_log2_hist("Latency (microseconds)")
            b["runqueue_lat"].clear()
    except KeyboardInterrupt:
        print("\n[INFO] Menghapus probe dan menghentikan pengawasan.")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Degradasi p99.9 Latensi pada Klaster Kubernetes Fintech Multi-Tenant
- **Konteks:** Sebuah microservice pembayaran berbasis Go memproses 45.000 RPS. SRE mendapati peningkatan tajam pada latensi p99.9 dari 8ms melonjak ke 1.800ms secara sporadis, yang memicu *gateway timeout*.
- **Observasi Awal:** Metrik standar Node Exporter menunjukkan utilisasi rata-rata CPU node hanya 42%, penggunaan memori pada 60%, dan metrik jaringan berada jauh di bawah limit fisik kartu NIC 25Gbps.

```
Metrik Rata-rata Node:
  CPU: 42% (Terlihat normal)
  Memory: 60% (Terlihat normal)
Tetapi:
  Pod p99.9 Latency: 1.800 ms (Kritis!)
```

#### Investigasi Mendalam (*Deep Dive Analysis*):
1. **Analisis CFS Throttling:**
   Tim SRE memeriksa berkas status cgroups pods yang bermasalah:
   ```bash
   cat /sys/fs/cgroup/cpu,cpuacct/kubepods/burstable/pod<uid>/cpu.stat
   # Output:
   # nr_periods 120542
   # nr_throttled 43210  <-- 35.8% DITHROTTLE!
   # throttled_time 8754129845124
   ```
   Meskipun CPU *usage* rata-rata rendah, arsitektur *multithreading* Go runtime menciptakan lonjakan komputasi paralel (*burst*) singkat yang menghabiskan alokasi kuota CPU 100ms dalam tempo 15ms pertama. Akibatnya, goroutine dibekukan (*throttled*) oleh CFS selama 85ms berikutnya dalam setiap siklus.

2. **Analisis Network Ring Buffer & SoftIRQ:**
   Saat lonjakan beban terjadi, terjadi penumpukan *dropped packets* di antarmuka jaringan kernel:
   ```bash
   ethtool -S eth0 | grep -E "rx_dropped|rx_missed_errors"
   # Output:
   # rx_dropped: 184512
   ```
   Intensitas interupsi jaringan terkonsentrasi hanya pada CPU Core 0, membebani kapasitas ksoftirqd/0 hingga 100% (*Single Core SoftIRQ bottleneck*), sementara core lainnya *idle*.

#### Solusi & Remediasi:
1. **CFS Tuning:** Menghapus parameter `cpu.limits` pada deployment Kubernetes dan beralih ke model alokasi berbasis `cpu.requests` eksklusif dengan *Guaranteed QoS Class* untuk pod berlatensi kritis.
2. **RSS & RPS Activation:** Mengaktifkan *Receive Side Scaling* (RSS) dan *Receive Packet Steering* (RPS) pada tingkat kernel untuk mendistribusikan beban penanganan interupsi paket jaringan ke seluruh 32 CPU core:
   ```bash
   # Distribusikan pemrosesan interrupt ke CPU Core 0-31
   echo "ffffffff" > /sys/class/net/eth0/queues/rx-0/rps_cpus
   ```
3. **Hasil:** CFS throttling turun ke angka 0%, antrean *dropped packets* berhenti, dan p99.9 latensi langsung stabil kembali di angka 4.2ms pada kapasitas beban puncak (*peak load*).

---

### 9. Trade-offs

| Pendekatan / Parameter | Opsi A | Opsi B | Trade-off Analisis |
| :--- | :--- | :--- | :--- |
| **CFS Quota vs No CPU Limit** | Memasang `cpu.limits` kaku | Hanya menetapkan `cpu.requests` | Opsi A mencegah pod memonopoli resource (*noisy neighbor*), namun memicu *unintended CFS throttling* mikro. Opsi B memberikan performa latensi terbaik tapi meningkatkan risiko destabilisasi node jika terjadi loop tak terbatas (*runaway code*). |
| **NIC Ring Buffer Size** | Ukuran Kecil (e.g., 512 Descriptors) | Ukuran Besar (e.g., 4096 Descriptors) | Ukuran besar mencegah *packet drop* saat ada lonjakan lalu lintas (*traffic burst*), namun dapat memicu *Bufferbloat* yang meningkatkan latensi transit paket. Ukuran kecil meminimalkan latensi antrean, namun rentan *drop*. |
| **Memory Overcommit** | `vm.overcommit_memory = 0` (Heuristik) | `vm.overcommit_memory = 2` (Strict) | Opsi 0 memaksimalkan utilisasi kapasitas RAM fisik sistem, tetapi berisiko memicu OOM Killer acak. Opsi 2 mencegah OOM Killer sepenuhnya, namun alokasi memori aplikasi besar sering ditolak (*failed malloc*) meskipun RAM fisik masih tersisa. |
| **Swappiness Strategy** | `vm.swappiness = 0` | `vm.swappiness = 10` | Menyetel nilai 0 menghindari I/O disk akibat paging anonim, namun meningkatkan risiko OOM killer mendadak karena kernel kehilangan fleksibilitas untuk merebut kembali memori anonim saat terjadi lonjakan Page Cache. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengira `vm.swappiness = 0` Mematikan Swap Sepenuhnya
- **Dampak:** Pada kernel Linux modern, menyetel nilai `0` tidak sepenuhnya menonaktifkan swap. Pengaturan ini hanya menginstruksikan kernel untuk tidak merebut halaman memori anonim sampai alokasi mencapai ambang batas kritis tertentu.
- **Troubleshooting:**
  ```bash
  # Verifikasi penggunaan swap aktual
  free -m
  cat /proc/zoneinfo | grep -E "min|low|high|nr_free_pages"
  # Matikan swap absolut jika arsitektur menghendaki (contoh: node Kubelet)
  swapoff -a
  ```

#### Kesalahan 2: Mengabaikan Titik Saturasi Tabel Conntrack (*Connection Tracking*)
- **Dampak:** Saat diserang lonjakan koneksi HTTP berskala masif, kernel membuang paket baru tanpa jejak (*silent packet drop*) dengan pesan log kernel: `nf_conntrack: table full, dropping packet`.
- **Troubleshooting:**
  ```bash
  # Cek kapasitas dan penggunaan conntrack saat ini
  cat /proc/sys/net/netfilter/nf_conntrack_count
  cat /proc/sys/net/netfilter/nf_conntrack_max

  # Remediasi instan di level runtime kernel
  sudo sysctl -w net.netfilter.nf_conntrack_max=1048576
  ```

#### Kesalahan 3: Tidak Mampu Mendiagnosis Proses dalam Status `D` (Uninterruptible Sleep)
- **Dampak:** Proses tidak merespons sinyal `kill -9` (`SIGKILL`) dan menyebabkan beban sistem (*load average*) meroket tanpa adanya konsumsi CPU riil.
- **Troubleshooting:**
  ```bash
  # Cari proses berstatus 'D'
  ps aux | awk '$8 ~ /D/'
  
  # Periksa kernel call stack dari proses yang hang (misal PID 4312)
  cat /proc/4312/stack
  # Jika jejak stack berhenti di nfs_wait_bituninterruptible atau get_request,
  # akar masalahnya berada pada latensi subsistem blok/NFS storage yang degraded.
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist konfigurasi `/etc/sysctl.d/99-sre-production.conf` berikut untuk node Linux dengan throughput tinggi:

```ini
# ====================================================================
# SRE PRODUCTION KERNEL HARDENING & OPTIMIZATION CONFIGURATION
# ====================================================================

# [VIRTUAL MEMORY SUBSYSTEM]
# Minimalkan kecenderungan swap tanpa mematikan fitur sepenuhnya
vm.swappiness = 1
# Hindari memory page starvation pada level alokasi rendah
vm.min_free_kbytes = 1048576
# Kendalikan rasio dirty memory cache agar I/O disk flush tidak memblokir kernel
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
# Pertahankan zone reclaim tetap non-aktif untuk mencegah latensi NUMA yang tidak terduga
vm.zone_reclaim_mode = 0

# [NETWORK CORE & TCP SUBSYSTEM]
# Tingkatkan ukuran antrean backlog soket masuk maksimum
net.core.somaxconn = 65535
# Tingkatkan batas paket jaringan yang diantrekan sebelum diproses stack protokol
net.core.netdev_max_backlog = 65535
# Alokasi buffer maksimum untuk TCP Read dan Write (16MB)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
# TCP Autotuning: min, default, max buffer (4KB, 87KB, 16MB)
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
# Aktifkan BBR Congestion Control (Membutuhkan Kernel 4.9+)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
# Matikan TCP Slow Start setelah idle untuk mempertahankan kecepatan koneksi
net.ipv4.tcp_slow_start_after_idle = 0
# Daur ulang status soket FIN-WAIT-2 lebih agresif (detik)
net.ipv4.tcp_fin_timeout = 15

# [FILE DESCRIPTORS & SYSTEM LIMITS]
# Kapasitas maksimum total file descriptor sistem operasi
fs.file-max = 2097152
# Batas monitoring inotify untuk sistem dengan ribuan pod/kontainer
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 8192
```

Terapkan langsung konfigurasi di atas dengan:
```bash
sudo sysctl --system
```

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan memproduksi kondisi **CFS CPU Quota Throttling** secara sengaja di dalam cgroup v2, mengukurnya dengan metric kernel, dan melacak anomali penundaannya menggunakan eBPF.

#### Langkah 1: Persiapan Lingkungan Kerja
Siapkan direktori praktikum dan pastikan sistem Anda telah mengaktifkan cgroups v2:
```bash
mkdir -p ~/hands-on/m02 && cd ~/hands-on/m02
# Verifikasi cgroups v2 (harus menghasilkan output: cgroup2fs)
stat -fc %T /sys/fs/cgroup
```

#### Langkah 2: Buat Skrip Beban Kerja CPU
Simpan kode Go sederhana berikut sebagai `burner.go`:
```go
package main

import (
	"runtime"
	"time"
)

func main() {
	// Jalankan loop pembakaran CPU paralel pada seluruh logical core yang tersedia
	for i := 0; i < runtime.NumCPU(); i++ {
		go func() {
			for {
				// Loop ketat untuk mengonsumsi cycle CPU
			}
		}()
	}
	time.Sleep(10 * time.Minute)
}
```
Kompilasi kode tersebut:
```bash
go build -o burner burner.go
```

#### Langkah 3: Setup Cgroup v2 dengan Limitasi Ketat
Buat grup kontrol baru dan batasi kuota CPU ke 20% dari 1 core (20000 mikrosekon per periode 100000 mikrosekon):
```bash
sudo mkdir -p /sys/fs/cgroup/sre_experiment
# Format: $MAX $PERIOD
echo "20000 100000" | sudo tee /sys/fs/cgroup/sre_experiment/cpu.max
```

#### Langkah 4: Jalankan Program di Bawah Cgroup Terisolasi
Jalankan program dan masukkan PID-nya ke cgroup eksperimen:
```bash
./burner &
BURNER_PID=$!
echo $BURNER_PID | sudo tee /sys/fs/cgroup/sre_experiment/cgroup.procs
```

#### Langkah 5: Analisis dan Verifikasi Metrik Throttling
Amati status penjadwalan kernel secara real-time:
```bash
watch -n 1 "cat /sys/fs/cgroup/sre_experiment/cpu.stat"
```
*Perhatikan bagaimana nilai `nr_throttled` dan `throttled_usec` meroket secara konsisten.*

#### Langkah 6: Pembersihan (Cleanup)
Hentikan eksperimen dengan aman:
```bash
kill -9 $BURNER_PID
sudo rmdir /sys/fs/cgroup/sre_experiment
```

---

### 13. Exercise

#### Level: Easy
Gunakan perintah CLI standar Linux untuk mengekstrak informasi detail berikut dari server target:
1. Hitung total frekuensi konteks switch CPU (*voluntary* vs *involuntary*) pada server Anda per detik menggunakan `vmstat`.
2. Tentukan PID proses yang saat ini memiliki alokasi memori fisik terkunci (*pinned/locked memory*) terbesar melalui `/proc/[pid]/status`.

#### Level: Medium
Tulis skrip Bash otomatis untuk mendeteksi *Socket Memory Pressure*. Skrip harus membaca status alokasi buffer TCP dari `/proc/net/sockstat`, mengekstrak metrik `sockets: used` dan `TCP: inuse mem`, lalu memicu peringatan terminal jika memori TCP melampaui ambang batas aman.

#### Level: Hard
Buat skrip `bpftrace` yang melacak eksekusi fungsi kernel `vfs_read`. Skrip harus mengidentifikasi dan mencetak:
- Nama proses (`comm`).
- Path file atau ID inode yang dibaca.
- Eksekusi pembacaan yang memakan waktu lebih lama dari 20 milidetik (indikasi I/O stall pada media penyimpanan).

---

### 14. Challenge

#### Skenario Kasus Kompleks: "The Phantom Latency Spike of Database Node-03"

Anda mengelola klaster database terdistribusi performa tinggi yang menangani operasi I/O intensif (Campuran 70% Write, 30% Read). Pada Node-03, Anda menghadapi anomali sistemik yang tidak lazim:
- Setiap tepat pukul 03.15 dini hari, latensi baca p99.9 melonjak dari 1.2ms menjadi 4.500ms selama rentang waktu 3 menit.
- Metrik CPU host pada rentang waktu tersebut berada di bawah 25%.
- Metrik I/O disk fisik (`await` pada `iostat`) tidak menunjukkan saturasi antrean perangkat penyimpanan (NVMe SSD).
- Analisis *log* aplikasi database tidak mencatat eksekusi query besar atau proses backup yang berjalan di jam tersebut.
- Node memiliki konfigurasi RAM 512GB, dan memori bebas dilaporkan hanya bersisa 4GB karena 480GB dialokasikan oleh kernel sebagai **Page Cache**.

#### Tugas Investigasi & Desain Arsitektur Anda:
1. Formulasikan hipotesis teknis mendalam mengenai mekanisme internal kernel apa yang terpicu pada pukul 03.15 tersebut (kaitkan dengan *Direct Memory Reclamation*, *Memory Compaction*, dan *Transparent Huge Pages / THP*).
2. Tuliskan rencana runut penelusuran masalah (*troubleshooting playbook*) langkah demi langkah menggunakan `perf` atau `bpftrace` untuk membuktikan apakah kernel mengalami degradasi pada siklus alokasi halaman memori (`alloc_pages_slowpath`).
3. Rancang perbaikan konfigurasi permanen pada tingkat parameter *sysctl* memori dan manajemen alokasi sistem operasi untuk mengeliminasi lonjakan latensi ekor tersebut secara permanen tanpa perlu me-reboot mesin database.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara instruksi CPU Ring 3 dan Ring 0 dalam arsitektur proteksi perangkat keras x86_64?
2. Mengapa *thread* dan *proses* diperlakukan secara identik oleh Linux Process Scheduler di level kernel?
3. Parameter konfigurasi apa pada subsistem cgroup v2 yang merepresentasikan batas pemakaian CPU maksimum dalam sebuah siklus waktu?
4. Apa yang membedakan *Minor Page Fault* dan *Major Page Fault* dalam subsistem manajemen memori virtual?
5. Mengapa penggunaan utilitas pemantauan warisan seperti `top` atau `netstat` tidak lagi memadai untuk menganalisis anomali *tail latency* mikrodetik di server produksi modern?

#### B. Pertanyaan Intermediate
6. Bagaimana cara Linux Completely Fair Scheduler (CFS) menghitung nilai `vruntime` suatu tugas, dan apa dampaknya jika sebuah tugas memiliki nilai `nice` positif yang tinggi?
7. Jelaskan fenomena *SoftIRQ core starvation* dan bagaimana fitur RPS (*Receive Packet Steering*) membantu memitigasinya pada NIC performa tinggi!
8. Apa yang terjadi secara mekanis di dalam kernel ketika memori sistem mencapai batas `vm.dirty_ratio` dibandingkan dengan `vm.dirty_background_ratio`?
9. Jelaskan peran instruksi CPU MSR `IA32_LSTAR` dalam proses penanganan *System Call* modern!
10. Mengapa aktivasi fitur *Transparent Huge Pages* (THP) sering kali disarankan untuk dimatikan pada server basis data seperti PostgreSQL atau Redis?

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sebuah pod microservice berbasis Java di Kubernetes tiba-tiba mati dengan *exit code* 137, namun log aplikasi Spring Boot tidak mencatat exception apa pun. Pada dmesg node host, Anda menemukan baris log: `Memory cgroup out of memory: Killed process 8421 (java)`. Bagaimana langkah investigasi Anda untuk menentukan apakah akar masalahnya adalah kebocoran memori pada *JVM Heap*, alokasi *Native Memory/Off-Heap*, atau *Kernel Page Cache* pod tersebut?
12. **Skenario 2:** Setelah melakukan migrasi klaster cloud dari cgroup v1 ke cgroup v2, Anda mendapati bahwa sejumlah pod mengalami degradasi I/O performa secara drastis saat menulis log file. Subsistem kernel apa yang baru diatur secara terintegrasi pada cgroup v2 yang sebelumnya terpisah pada cgroup v1 yang dapat menyebabkan fenomena ini?
13. **Skenario 3:** Tim pengembang melaporkan koneksi TCP HTTP antarservice sering mengalami *connection reset* (`ECONNRESET`) secara acak saat throughput mencapai 80.000 RPS. Tidak ada packet drop pada NIC hardware. Analisis kernel parameter manakah yang wajib Anda audit pertama kali untuk memastikan soket tidak dibuang diam-diam pada tahap *three-way handshake*?

---

#### Kunci Jawaban & Rationale Teknis Evaluasi

1. **Ring 3 vs Ring 0:** Ring 3 adalah mode non-istimewa untuk eksekusi aplikasi biasa dengan restriksi memori dan instruksi perangkat keras. Ring 0 adalah mode dengan hak penuh di mana kode kernel dapat mengeksekusi instruksi CPU istimewa (misal manipulasi bit CR0/CR3/CR4, deskriptor interupsi IDT) dan memetakan langsung memori fisik.
2. **Task di Mata Scheduler:** Linux mengabstraksikan keduanya ke dalam satu struktur seragam `task_struct`. Perbedaannya hanya terletak pada apakah struktur tersebut berbagi referensi pointer ruang alamat (`mm_struct`) dan tabel file descriptor yang sama dengan parent (`CLONE_VM`, `CLONE_FILES`) atau mengalokasikan salinan independen saat pemanggilan *syscall* `clone()`.
3. **Parameter Cgroup v2:** `cpu.max` (berisi dua kuantitas angka: kuota waktu maksimal per satu periode waktu siklus, misal `50000 100000` untuk 50% CPU).
4. **Minor vs Major Page Fault:** *Minor page fault* terjadi ketika frame halaman fisik sebenarnya sudah ada di memori RAM tetapi belum dipetakan ke tabel halaman MMU proses bersangkutan (tidak melibatkan pembacaan disk). *Major page fault* terjadi saat halaman data yang diminta belum berada di RAM dan kernel terpaksa membaca blok dari media disk atau area swap ke RAM (memicu latensi I/O tinggi).
5. **Keterbatasan Tooling Tradisional:** Tooling lama (`top`, `netstat`) bekerja dengan metode polling berbasis interval kasar (misalnya per 1 hingga 3 detik) dengan membaca berkas teks `/proc`. Hal ini mengaburkan lonjakan anomali mikro (*microbursts*) dan latensi ekor yang terjadi dalam skala mikrodetik atau milidetik.
6. **Perhitungan `vruntime`:** $vruntime += \Delta exec\_time \times (NICE\_0\_LOAD / task\_weight)$. Tugas dengan nilai nice positif tinggi memiliki bobot (`task_weight`) yang jauh lebih kecil. Akibatnya, setiap fraksi waktu eksekusi riil akan melambungkan `vruntime`-nya secara eksponensial lebih cepat, mendorongnya ke sisi kanan RB-Tree dan secara masif mengurangi jatah eksekusinya.
7. **SoftIRQ Starvation & RPS:** Terjadi ketika penanganan interupsi paket jaringan dari NIC hanya dilayani oleh satu core CPU CPU0 melalui hard IRQ routing default, menyebabkan antrean thread `ksoftirqd/0` saturasi 100% dan membuang paket baru. RPS (*Receive Packet Steering*) memecahkan masalah ini dengan membagikan pemrosesan protokol jaringan perangkat lunak (*SoftIRQ*) ke seluruh core CPU lain melalui algoritma hash perangkat lunak.
8. **Dirty Ratio Thresholds:** Saat mencapai `vm.dirty_background_ratio`, thread kernel `kswapd` / `flusher` mulai menulis halaman kotor (*dirty pages*) ke disk secara asynchronous di latar belakang tanpa menangguhkan thread aplikasi. Namun, jika laju penulisan aplikasi melampaui kapasitas disk hingga menyentuh `vm.dirty_ratio`, kernel akan secara sinkron memblokir (*synchronous throttling*) aplikasi yang mencoba melakukan *syscall write()* sampai jumlah halaman kotor turun kembali di bawah batas tersebut.
9. **MSR `IA32_LSTAR`:** Register ini menyimpan alamat instruksi entry-point 64-bit kernel (`entry_SYSCALL_64`). Saat instruksi CPU `syscall` dieksekusi oleh aplikasi di Ring 3, perangkat keras CPU secara atomik menyalin pointer program dari register register ini ke Instruction Pointer (`RIP`), memungkinkan transisi instan ke handler sistem kernel tanpa overhead *interrupt gate* lama.
10. **Dampak Negatif THP pada Database:** Basis data umumnya melakukan alokasi dan mutasi memori dalam chunk kecil acak (misal 8KB atau 16KB). THP memaksa alokasi dalam blok raksasa 2MB contiguous. Ketika terjadi fragmentasi memori, kernel memicu daemon *khugepaged* atau *direct memory compaction* sinkron yang membekukan pemrosesan CPU untuk menata ulang blok fisik 2MB, menghasilkan *I/O stall* parah pada thread database.
11. **Skenario 1 - Analisis OOM:** Ekstrak metrik alokasi terakhir pada berkas `/sys/fs/cgroup/memory/kubepods/.../memory.stat`. Bandingkan nilai `rss` (Resident Set Size) terhadap `cache` dan `mapped_file`. Masuk ke konfigurasi heap JVM (opsi `-Xmx`). Jika metrik RSS host jauh melampaui alokasi parameter `-Xmx`, kebocoran terjadi pada *Native Memory* (misal penggunaan direct byte buffers oleh framework Netty atau kebocoran library C-binding JNI), bukan pada Java Heap.
12. **Skenario 2 - Cgroup v2 I/O Regression:** Cgroup v2 mengimplementasikan fitur *Unified Hierarchy* yang mengintegrasikan pengawasan CPU, Memory, dan I/O secara bersamaan. Di cgroup v1, alokasi *writeback Page Cache* anonim tidak dapat dihubungkan ke limit I/O blok pemilik pod. Pada cgroup v2, kernel membebankan penulisan I/O *dirty page cache* langsung ke cgroup pembuat data; pembatasan memori otomatis memicu pembatasan *I/O writeback throttling* secara agresif.
13. **Skenario 3 - TCP Drops Handshake:** Audit nilai parameter antrean soket kernel: `net.core.somaxconn` dan antrean backlog lokal aplikasi (parameter `backlog` pada pemanggilan syscall `listen()`). Jika antrean *Listen Backlog* penuh karena aplikasi lambat memanggil `accept()`, kernel akan membuang paket SYN/ACK atau mengirim sinyal RST secara diam-diam berdasarkan nilai sysctl `net.ipv4.tcp_abort_on_overflow`.

---

### 16. Summary

Menguasai arsitektur sistem operasi dan internal kernel Linux mengubah paradigma seorang Software Development Engineer in Test (SDET) dan Site Reliability Engineer (SRE) dari sekadar **konsumen infrastruktur** menjadi seorang **system diagnostician**. 

Latensi ekor (*tail latency*) dan degradasi tak kasat mata pada platform komputasi modern hampir selalu berakar pada benturan antara asumsi perangkat lunak tingkat tinggi dengan kenyataan fisik manajemen sistem operasi:
- **Penjadwalan (Scheduling):** Batas cgroups yang salah konfigurasi memicu interupsi CFS throttling masif tanpa menimbulkan saturasi utilisasi CPU global.
- **Memori (Memory):** Tekanan pada alokasi halaman fisik memicu *direct memory compaction* dan OOM Killer yang mematikan proses tanpa jejak error di log aplikasi.
- **Jaringan (Networking):** Jalur kritis paket data dari NIC *Ring Buffer* hingga soket aplikasi rentan mengalami bottleneck penanganan interupsi pada level *SoftIRQ* jika tidak didistribusikan secara merata.

Alat observabilitas modern berbasis **eBPF** adalah instrumen wajib bagi SRE masa kini untuk menembus dinding pembatas antara ruang aplikasi (*user space*) dan kernel secara langsung di lingkungan produksi tanpa mengorbankan stabilitas sistem. Memahami mekanika internal ini adalah fondasi paling esensial dalam membangun sistem berskala masif yang tangguh, deterministik, dan efisien secara biaya.