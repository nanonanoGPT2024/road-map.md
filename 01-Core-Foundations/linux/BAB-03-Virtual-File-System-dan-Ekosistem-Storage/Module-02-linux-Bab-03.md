# Kurikulum Rekayasa Sistem Berkelanjutan: Linux Enterprise Infrastructure
## Bab 03: Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis Subsistem Kernel Tingkat Rendah:** Membedah alur eksekusi internal Linux Kernel, mencakup Virtual File System (VFS), *Memory Management* (Buddy Allocator, SLUB, Page Cache reclaim), Process Scheduler (CFS/EEVDF), serta arsitektur I/O modern berbasis `io_uring`.
2. **Merancang Isolasi Resource Berperforma Tinggi:** Mengonfigurasi dan mengoperasikan *Control Groups v2 (cgroups v2)*, *Linux Namespaces*, serta NUMA (*Non-Uniform Memory Access*) *topology affinity* untuk arsitektur multi-tenant dengan *zero-jitter* and *deterministic latency*.
3. **Mengimplementasikan Observabilitas Rendah-Overhead via eBPF:** Menulis, mengompilasi, dan memvalidasi program eBPF (*Extended Berkeley Packet Filter*) untuk *profiling* latensi I/O disk, *off-CPU time*, dan inspeksi paket jaringan tanpa membebani sistem secara destruktif (*zero-context-switch cost*).
4. **Melakukan Kernel Tuning Skala Produksi:** Memetakan dan merekayasa parameter subsistem `sysctl`, TCP memory allocation, epoll scalability, *dirty page flushing*, serta *interrupt request* (IRQ) *affinity* untuk beban kerja *high-throughput/low-latency*.
5. **Mendiagnosis Masalah Kompleks Sistem Operasi:** Melacak *uninterruptible sleep states* (D-state), memory fragmentation, kswapd thrashing, *softirq saturation*, dan *lock contention* menggunakan instrumen telemetri kernel mutakhir.

---

### 2. Prerequisite

Peserta didik wajib memiliki pemahaman mendalam dan pengalaman praktis terkait:
- **Foundational Linux Systems:** Administrasi CLI Linux, arsitektur POSIX, *file permissions*, sinyal POSIX (*signals*), *process states* (R, S, D, Z, T), serta CLI dasar (`ps`, `top`, `grep`, `awk`).
- **Arsitektur Komputer & OS:** Model memori virtual (*virtual-to-physical address translation*, MMU, TLB), hierarki CPU cache (L1/L2/L3), *paging*, instruksi CPU, interupsi (*hardware/software interrupts*), dan arsitektur *bus* PCIe/NVMe.
- **Networking Foundations:** Model OSI & TCP/IP, struktur paket layer 2–4, konsep *socket programming* (stream/datagram, blocking/non-blocking, synchronous/asynchronous), *handshake mechanics*, dan *state machine* TCP.
- **Bahasa Tingkat Rendah Dasar:** Kemampuan membaca sintaksis C standar dan *shell scripting* (Bash/POSIX) tingkat lanjut.

---

### 3. Concept & Internal Architecture

Arsitektur Linux tingkat lanjut memisahkan *User Space* dan *Kernel Space* secara rigid melalui *hardware execution rings* (Ring 0 untuk Kernel, Ring 3 untuk User Space). Interaksi antara kedua ruang ini dijembatani oleh *System Call (syscall) Interface*. 

```
+-------------------------------------------------------------------------+
|                              USER SPACE                                 |
|  [ Applications ]     [ C Libraries: glibc/musl ]     [ System Daemons ] |
+------------------------------------+------------------------------------+
                                     | System Call Interface (Ring 3 -> 0)
+------------------------------------v------------------------------------+
|                             KERNEL SPACE                                |
|  +-------------------+  +-------------------+  +---------------------+  |
|  | Process Scheduler |  | Memory Management |  | Virtual File System |  |
|  |  (CFS / EEVDF)    |  | (Buddy / SLUB)    |  | (VFS / Page Cache)  |  |
|  +-------------------+  +-------------------+  +---------------------+  |
|  +-------------------+  +-------------------+  +---------------------+  |
|  |   Network Stack   |  |   Block Layer     |  |   Infrastructure    |  |
|  | (Socket/TCP/XDP)  |  | (io_uring/NVMe)   |  | (cgroups v2, eBPF)  |  |
|  +-------------------+  +-------------------+  +---------------------+  |
+------------------------------------+------------------------------------+
                                     | Drivers & Architecture Layer
+------------------------------------v------------------------------------+
|                               HARDWARE                                  |
|         [ CPU ]         [ Memory (NUMA) ]         [ Disks / NICs ]      |
+-------------------------------------------------------------------------+
```

#### A. Memory Management: Buddy Allocator, SLUB, & Page Cache
Memori fisik dialokasikan dalam unit halaman (default 4KB). 
- **Buddy Allocator:** Bertanggung jawab atas alokasi blok memori berurutan (*contiguous memory pages*) dengan menggunakan teknik *power-of-two*. Setiap ordo alokasi berkisar dari $2^0$ hingga $2^{11}$ (biasanya hingga 4MB per alokasi). Masalah utama dari Buddy Allocator adalah *external fragmentation*.
- **SLUB Allocator:** Menangani alokasi struktur data kecil kernel (objek yang jauh lebih kecil dari 4KB, seperti `struct task_struct`, `struct inode`). Menggantikan SLAB lawas dengan mengurangi jejak metadata (*tracking overhead*) pada setiap halaman, mengorganisir objek dalam *kmem_caches*.
- **Page Cache & Dirty Memory:** Linux mengalokasikan RAM yang tidak digunakan untuk meng-cache data disk. Operasi penulisan I/O bersifat *asynchronous* secara default: data ditulis ke Page Cache dan ditandai sebagai *dirty*. *Flusher threads* (`kworker/flush`) menulis blok *dirty* tersebut ke media fisik ketika melampaui batasan `vm.dirty_background_ratio` atau `vm.dirty_ratio`.

#### B. Process Scheduling: CFS hingga EEVDF
Dimulai dari Kernel 6.6, Linux menggantikan Completely Fair Scheduler (CFS) dengan **Earliest Eligible Virtual Deadline First (EEVDF)**.
- **CFS:** Menghitung `vruntime` (virtual runtime) untuk setiap *task* menggunakan pohon *red-black* (*rb-tree*). Task dengan `vruntime` terendah dipilih untuk dieksekusi berikutnya.
- **EEVDF:** Memperkenalkan konsep *eligibility* dan *virtual deadline*. EEVDF memisahkan alokasi sumber daya jangka panjang (*fair share*) dari kebutuhan latensi jangka pendek. Proses tidak hanya dievaluasi berdasarkan penggunaan historisnya (`vruntime`), tetapi juga diberikan batas waktu virtual (*deadline*) kapan komputasi harus diselesaikan, meminimalkan latensi untuk proses interaktif tanpa merusak keadilan throughput (*fairness*).

#### C. Control Groups v2 (Unified Hierarchy)
Cgroups v2 memusatkan kontrol resource (CPU, Memory, I/O, PID, RDMA) dalam satu pohon hirarki terpadu (berbeda dengan model v1 yang memisahkan sub-sistem ke direktori berbeda). 
- Menghilangkan *split-brain* antar-pengontrol (misal: Memory Controller dan Block I/O Controller kini bekerja sama menangani write-back caching).
- Memperkenalkan skema isolasi memori mutakhir: `memory.min` (hard protection), `memory.low` (soft protection), `memory.high` (throttling boundary), dan `memory.max` (hard ceiling yang memicu OOM killer jika reclaim gagal).
- Melacak *Pressure Stall Information (PSI)*: Metrik absolut yang mengukur degradasi performa akibat kekurangan CPU, Memory, dan I/O pada tingkat task atau group (`some` vs `full`).

#### D. Modern High-Performance I/O: io_uring
`io_uring` mengatasi masalah syscall overhead yang inheren pada `epoll`, `read`, dan `write`. Menggunakan dua buah *ring buffer* berbasis lockless *circular array* yang dipetakan (*shared memory via mmap*) antara User Space dan Kernel Space:
1. **Submission Queue (SQ):** Aplikasi memasukkan permintaan I/O (Submission Queue Entry / SQE) langsung ke buffer tanpa syscall (atau dengan satu syscall `io_uring_enter`).
2. **Completion Queue (CQ):** Kernel memproses SQE secara asynchronous dan menulis hasilnya ke Completion Queue Entry (CQE), yang dapat dibaca langsung oleh aplikasi tanpa context switch.
Mode opsional `IORING_SETUP_SQPOLL` mendedikasikan satu kernel thread untuk memantau submission queue secara aktif (*polling*), menghilangkan kebutuhan *system call* secara penuh untuk penanganan I/O.

---

### 4. Why & What

| Subsistem / Konsep | Problem Space (Masalah yang Dihadapi) | Solusi Enterprise (What & Why) |
| :--- | :--- | :--- |
| **cgroups v2 & PSI** | Fenomena *Noisy Neighbor* pada multi-tenant infrastructure di mana lonjakan I/O atau memori pada satu kontainer mendegradasi kontainer lain secara tak terprediksi. | Mengganti model *reactive-OOM* dengan throttling proaktif berbasis metrik PSI (`some`/`full` stall) dan proteksi deterministik via `memory.low` dan `io.weight`. |
| **eBPF vs Profiling Lawas** | Tool observabilitas tradisional (`strace`, `lsof`) memiliki overhead masif (strace menghentikan eksekusi thread via `ptrace`), mendegradasi performa hingga 100x lipat di produksi. | eBPF menyuntikkan bytecode terverifikasi ke dalam kernel context (*kprobes*, *tracepoints*, *perf_events*) dengan overhead CPU < 1%, memungkinkan observabilitas instan secara non-destruktif. |
| **io_uring vs epoll/AIO** | POSIX AIO terbatas pada `O_DIRECT`, sementara `epoll` membutuhkan syscall tambahan untuk pembacaan payload I/O sebenarnya, memicu *syscall storm* pada load jutaan IOPS. | `io_uring` mengkonsolidasi disk I/O, network I/O, dan IPC dalam satu antarmuka berbasis memory-mapped lockless ring buffer dengan dukungan *zero-copy* penuh. |
| **EEVDF Scheduler** | CFS sering menyebabkan *latency spikes* (tail latency p99/p999) pada aplikasi yang sensitif terhadap waktu akibat keterlambatan penjadwalan saat antrian penuh. | EEVDF memungkinkan sistem menjadwalkan task berdasarkan *latency-sensitivity deadlines*, mengisolasi alokasi throughput dari target responsivitas. |

---

### 5. How (Workflow Detail)

Alur eksekusi internal saat aplikasi melakukan I/O jaringan performa tinggi menggunakan kernel modern:

```
[User Application]
       |
  1. Tulis SQE ke Ring Buffer Submission (mmap)
       |
  2. Panggil io_uring_enter() (opsional jika SQPOLL aktif)
       |
[Kernel Space: io_uring engine]
       |
  3. Dequeue SQE -> Eksekusi I/O Non-blocking / Asynchronous
       |
  4. Periksa Socket Buffer / Routing Subsystem
       |
  5. Kirim via TCP Engine (kalkulasi BBR congestion window)
       |
  6. Tulis descriptor ke Ring Buffer Network Card (NIC TX Ring)
       |
[Hardware: NIC Device]
       |
  7. Transmisi frame via DMA (Direct Memory Access) ke physical layer
       |
  8. Kirim Hardware Interrupt (MSI-X) ke CPU Core yang terikat (IRQ Affinity)
       |
[Kernel Space: SoftIRQ / NAPI Context]
       |
  9. Driver membersihkan TX Ring via SoftIRQ (NET_TX_SOFTIRQ)
       |
 10. io_uring menulis CQE (Completion Queue Entry) ke CQ Ring Buffer
       |
[User Application]
       |
 11. Baca hasil CQE langsung dari memory tanpa syscall
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Skala Industri

- **Legacy I/O (Syscall Tradisional / epoll):** Seperti pelayan (Aplikasi) yang harus berjalan bolak-balik ke dapur (Kernel) setiap kali ada satu piring pesanan baru. Setiap kali melintasi pintu dapur (Syscall/Context Switch), ia harus diperiksa kartu identitasnya oleh sekuriti, menaruh pesanan, menunggu, lalu kembali membawa makanan.
- **Modern I/O (`io_uring`):** Seperti memasang ban berjalan (*conveyor belt*) dua arah antara ruang makan dan dapur. Pelayan meletakkan pesanan di ban berjalan Submission (SQ), dan juru masak meletakkan makanan jadi di ban berjalan Completion (CQ). Tidak ada yang perlu melewati pintu bolak-balik; efisiensi mencapai batas maksimal.
- **eBPF:** Seperti memasang kamera inspeksi berbasis AI di langit-langit dapur. Kamera menganalisis kecepatan koki memotong bahan dan mencatat titik hambatan tanpa menyentuh juru masak atau menghentikan alur kerja mereka.

```
       USER SPACE                       KERNEL SPACE
+-----------------------+         +-----------------------+
|  Application Memory   |         |   Kernel Subsystems   |
|                       |         |                       |
|   [ SQ Ring Buffer ]========mmap======>[ Submission ]   |
|   (App writes SQEs)   |         |      (Kernel reads)   |
|                       |         |             |         |
|                       |         |             v         |
|                       |         |      [ Execution ]    |
|                       |         |       (VFS / NET)     |
|                       |         |             |         |
|                       |         |             v         |
|   [ CQ Ring Buffer ]<=======mmap=======[ Completion ]   |
|   (App reads CQEs)    |         |      (Kernel writes)  |
+-----------------------+         +-----------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengonfigurasi Cgroups v2 secara Manual via pseudo-fs
Berikut adalah langkah murni tanpa dependensi systemd untuk mengisolasi proses ke dalam cgroup terdedikasi:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Pastikan cgroup v2 telah terpasang
CGROUP_PATH="/sys/fs/cgroup/production_worker"
sudo mkdir -p "${CGROUP_PATH}"

# 2. Batasi memori: Max 512MB, Throttling boundary di 400MB, Proteksi 128MB
echo "134217728" | sudo tee "${CGROUP_PATH}/memory.min"   # 128MB
echo "419430400" | sudo tee "${CGROUP_PATH}/memory.high"  # 400MB
echo "536870912" | sudo tee "${CGROUP_PATH}/memory.max"   # 512MB

# 3. Batasi CPU: Maksimal 1.5 core (150000 us dari 100000 us periode)
echo "150000 100000" | sudo tee "${CGROUP_PATH}/cpu.max"

# 4. Tambahkan shell saat ini ke dalam cgroup tersebut
echo $$ | sudo tee "${CGROUP_PATH}/cgroup.procs"

# 5. Verifikasi keanggotaan proses
cat /proc/$$/cgroup
```

#### Practical Example: eBPF Program untuk Tracking Disk I/O Latency
Program BCC (BPF Compiler Collection) tingkat produksi menggunakan Python/C untuk mengidentifikasi lonjakan latensi blok I/O yang tersembunyi dari utilitas biasa.

Simpan file berikut sebagai `io_latency_tracker.py`:

```python
#!/usr/bin/env python3
from bcc import BPF
from time import sleep

# Program C eBPF yang disuntikkan ke dalam Kernel Space
bpf_source = """
#include <uapi/linux/ptrace.h>
#include <linux/blk-mq.h>

BPF_HASH(start_time, struct request *, u64);
BPF_HISTOGRAM(dist);

// Kprobe pada saat request blok diajukan ke driver device
int trace_req_start(struct pt_regs *ctx, struct request *rq) {
    u64 ts = bpf_ktime_get_ns();
    start_time.update(&rq, &ts);
    return 0;
}

// Kprobe pada saat request selesai dieksekusi oleh hardware
int trace_req_done(struct pt_regs *ctx, struct request *rq) {
    u64 *tsp = start_time.lookup(&rq);
    if (tsp != 0) {
        u64 delta = bpf_ktime_get_ns() - *tsp;
        // Konversi ke microsecond dan simpan dalam log2 histogram
        dist.increment(bpf_log2l(delta / 1000));
        start_time.delete(&rq);
    }
    return 0;
}
"""

def main():
    print("[*] Mengompilasi dan memuat bytecode eBPF ke kernel...")
    b = BPF(text=bpf_source)
    
    # Attach probe ke fungsi block execution kernel
    b.attach_kprobe(event="blk_account_io_start", fn_name="trace_req_start")
    b.attach_kprobe(event="blk_account_io_done", fn_name="trace_req_done")

    print("[*] Tracking block I/O latency... Tekan Ctrl+C untuk berhenti.")
    try:
        while True:
            sleep(5)
            print("\n--- Latensi Blok I/O (Microseconds) ---")
            b["dist"].print_log2_hist("usecs")
            b["dist"].clear()
    except KeyboardInterrupt:
        print("\n[*] Menghapus instrumentation hook. Selesai.")

if __name__ == "__main__":
    main()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Degradasi Latensi P99.9 pada Klaster Basis Data Finansial Terdistribusi
- **Konteks:** Sebuah bank investasi tier-1 menjalankan klaster basis data terdistribusi (Cassandra & Kafka) di atas bare-metal Linux (Ubuntu 22.04 LTS, Dual AMD EPYC 64-core, 1TB RAM, NVMe U.2 arrays). Sistem menangani 450.000 transaksi per detik.
- **Gejala Masalah:** Setiap beberapa jam, node acak mengalami lonjakan latensi p99.9 dari ~2ms menjadi >1.200ms. Fenomena ini menyebabkan *heartbeat timeout* pada konsensus Raft, memicu *failover cluster* yang destruktif dan data re-balancing berulang.
- **Root Cause Analysis (RCA):**
  1. **Investigasi CPU:** Metrik CPU global menunjukkan penggunaan stabil pada 45%. Namun, telemetri eBPF `runqlat` mengungkap antrian *scheduler* membengkak secara mendadak.
  2. **Investigasi Memori:** Server memiliki `vm.zone_reclaim_mode = 1` dan alokasi NUMA yang tidak seimbang. Ketika Node NUMA 0 kehabisan memori lokal, alih-alih mengalokasikan memori dari Node NUMA 1, kernel memicu *direct synchronous compaction* dan pembersihan halaman lokal (`kswapd`), menyebabkan *CPU stall* di thread database.
  3. **Investigasi I/O Subsystem:** Aplikasi menggunakan penulisan non-direct I/O. Parameter `vm.dirty_ratio = 20` (200GB) dan `vm.dirty_background_ratio = 10` (100GB). Ketika Kafka menulis log dalam skala besar, kernel menahan hingga 100GB *dirty pages* sebelum mulai memicu `kworker/flush`. Saat ambang batas terlampaui, kernel beralih ke *synchronous dirty write-back* (`throttle_vm_writeout`), memblokir thread operasi I/O database ke dalam status `D-state`.
- **Mitigasi & Solusi Arsitektural:**
  1. Menonaktifkan NUMA zone reclaim:
     ```bash
     sysctl -w vm.zone_reclaim_mode=0
     ```
  2. Mengikat proses database secara afinitas ke node NUMA spesifik via `numactl --interleave=all` atau alokasi CPU-set di systemd.
  3. Mengubah dirty ratio dari persentase menjadi batasan ukuran byte absolut yang ketat:
     ```bash
     sysctl -w vm.dirty_background_bytes=268435456  # 256MB
     sysctl -w vm.dirty_bytes=1073741824            # 1GB
     ```
  4. Hasil: Latensi P99.9 turun secara stabil ke kisaran sub-3ms tanpa ada thread yang terblokir ke dalam *uninterruptible sleep* (`D-state`).

---

### 9. Trade-offs

| Parameter Rekayasa | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **I/O Access Strategy** | `O_DIRECT` (Bypass Page Cache) | Buffered I/O (Memanfaatkan Page Cache) | `O_DIRECT` menghilangkan *copy overhead* dan degradasi akibat `kswapd`, namun menuntut aplikasi mengelola alokasi buffer aligned dan caching mandiri di memori. |
| **Network Polling** | Hardware Interrupt (IRQ based) | Busy Polling (`epoll` busy poll / DPDK) | Busy Polling memotong tail-latency hingga sub-mikrodetik, namun mengonsumsi 100% kapasitas inti CPU bahkan saat tidak ada beban transaksi (*idle burning*). |
| **Hugepages Architecture** | Transparent Huge Pages (THP = `always`) | Explicit Huge Pages (`hugetlbfs`) / `madvise` | THP menyederhanakan alokasi 2MB pages namun memicu *unpredictable latency spikes* saat *memory defragmentation* (`khugepaged`). Explicit hugepages menjamin stabilitas tanpa jitter dengan biaya kompleksitas konfigurasi statis. |
| **eBPF Tracing vs Metrics Exporters** | eBPF Dynamic Probes (`kprobes`) | Static Metrics Exporters (`/proc`, `sysfs`) | Exporter standar aman tetapi lambat dan agregatif (resolusi kasar per detik). `kprobe` eBPF beresolusi nanodetik namun berisiko menambah *instruction overhead* bila di-attach pada jalur eksekusi berfrekuensi ekstrem (misal: scheduler context switch per detik). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi:
1. **Mengabaikan Interrupt Handling Affinity:** Membiarkan semua core CPU melayani IRQ dari Network Card berkecepatan 40GbE/100GbE, sehingga Core 0 tersaturasi oleh `ksoftirqd/0` sementara core lainnya idle.
2. **Ketergantungan Berlebih pada Swappiness = 0:** Menyetel `vm.swappiness = 0` dengan asumsi sistem tidak akan pernah swapping. Hal ini membatasi elastisitas file page reclaim, yang dapat memicu `Out-Of-Memory (OOM) Killer` prematur padahal memori cache anonim masih bisa dialihkan.
3. **Mengabaikan Epoll Starvation:** Aplikasi multithread menggunakan model `EPOLLEXCLUSIVE` atau thundering herd handling yang salah, sehingga thread worker tertentu mengalami starvasi koneksi sementara thread lain kelebihan beban.

#### Alur Diagnostik D-State Process (Uninterruptible Sleep):
Proses dalam status `D` tidak dapat dimatikan bahkan dengan `kill -9` karena sedang menunggu pengembalian I/O atau hardware locks.

```bash
# 1. Temukan proses yang berada dalam status 'D'
ps -eo pid,user,state,time,comm | awk '$3=="D" {print $0}'

# 2. Periksa kernel stack trace langsung dari thread yang bermasalah
# (Ganti <PID> dengan target pid)
cat /proc/<PID>/stack

# 3. Analisis apakah terjadi starvation pada subsistem I/O menggunakan PSI
cat /proc/pressure/io
# Output:
# some avg10=15.20 avg60=8.45 avg300=2.12 total=4567890
# full avg10=10.11 avg60=5.12 avg300=1.05 total=2345678

# 4. Lacak subsistem pemblokir via perf (sampling kernel trace)
sudo perf record -e sched:sched_blocked_reason -a -- sleep 10
sudo perf report --stdio
```

---

### 11. Best Practices (Production Checklist)

#### Kernel Tuning Checklist (`/etc/sysctl.d/99-enterprise-production.conf`):

- [ ] **Virtual Memory Subsystem:**
  ```ini
  vm.swappiness = 10
  vm.dirty_background_bytes = 268435456
  vm.dirty_bytes = 1073741824
  vm.max_map_count = 1048576
  vm.vfs_cache_pressure = 50
  vm.overcommit_memory = 1
  ```
- [ ] **Network Stack (Low Latency / High Throughput):**
  ```ini
  net.core.somaxconn = 65535
  net.core.netdev_max_backlog = 100000
  net.core.rmem_max = 16777216
  net.core.wmem_max = 16777216
  net.ipv4.tcp_rmem = 4096 87380 16777216
  net.ipv4.tcp_wmem = 4096 65536 16777216
  net.ipv4.tcp_congestion_control = bbr
  net.core.default_qdisc = fq
  net.ipv4.tcp_tw_reuse = 1
  net.ipv4.tcp_fin_timeout = 15
  ```
- [ ] **File Descriptors & Resource Limits:**
  ```ini
  fs.file-max = 2097152
  fs.inotify.max_user_watches = 524288
  fs.inotify.max_user_instances = 8192
  ```
- [ ] **IRQ Balancing & CPU Isolation:**
  - [ ] Memetakan antrean IRQ kartu jaringan secara eksplisit menggunakan skrip affinity atau mengonfigurasi `irqbalance` dengan *banned CPUs*.
  - [ ] Memisahkan core penanganan aplikasi dengan core penanganan interupsi via parameter bootloader kernel: `isolcpus=2-15 nohz_full=2-15 rcu_nocbs=2-15`.

---

### 12. Hands-on Practice

Simpan seluruh skrip latihan ini ke direktori: `hands-on/m02/`.

#### Langkah 1: Eksplorasi Cgroups v2 & Implementasi Throttling Memory
Buat skrip `hands-on/m02/cgroup_lab.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/sys/fs/cgroup/lab_isolated"
echo "[+] Menyiapkan Cgroup v2 di ${BASE_DIR}..."
sudo mkdir -p "${BASE_DIR}"

# Batasi alokasi memory maksimal ke 100MB
echo "104857600" | sudo tee "${BASE_DIR}/memory.max"
echo "0" | sudo tee "${BASE_DIR}/memory.swap.max"

echo "[+] Menjalankan alokator memori 150MB di dalam namespace cgroup..."
# Jalankan Python yang mencoba mengalokasikan 150MB; sistem harus memicu OOM Killer
sudo cgexec -g memory:lab_isolated python3 -c '
import time
print("Mengalokasikan 150MB...")
try:
    bytearray(150 * 1024 * 1024)
    print("Sukses mengalokasikan!")
except Exception as e:
    print(f"Alokasi gagal: {e}")
time.sleep(2)
' || echo "[!] Proses sukses dihentikan oleh OOM Killer (Perilaku yang Diharapkan)."

echo "[+] Analisis Memory Events Cgroup:"
cat "${BASE_DIR}/memory.events"

# Bersihkan
sudo rmdir "${BASE_DIR}"
```

#### Langkah 2: Audit Tracing Context Switch Menggunakan `perf`
Buat skrip `hands-on/m02/perf_scheduler_audit.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[+] Memulai tracing context-switch selama 5 detik..."
sudo perf record -e sched:sched_switch -a -g -- sleep 5

echo "[+] Menganalisis 10 thread dengan context-switch terbanyak:"
sudo perf report --stdio --no-children --sort comm | head -n 30

echo "[+] Membersihkan artifacts..."
rm -f perf.data
```

#### Langkah 3: Konfigurasi Optimalisasi TCP BBR & Buffer Sizes
Buat skrip `hands-on/m02/network_tuning.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[+] Memvalidasi modul kernel BBR..."
sudo modprobe tcp_bbr

echo "[+] Memeriksa ketersediaan modul..."
sysctl net.ipv4.tcp_available_congestion_control

echo "[+] Menerapkan algoritma antrean Fair Queueing dan TCP BBR..."
sudo sysctl -w net.core.default_qdisc=fq
sudo sysctl -w net.ipv4.tcp_congestion_control=bbr

echo "[+] Status Konfigurasi:"
sysctl net.ipv4.tcp_congestion_control
```

Eksekusi seluruh file tersebut:
```bash
chmod +x hands-on/m02/*.sh
./hands-on/m02/cgroup_lab.sh
./hands-on/m02/perf_scheduler_audit.sh
./hands-on/m02/network_tuning.sh
```

---

### 13. Exercise

#### Level Easy
Tulis skrip bash yang membaca `/proc/net/dev` setiap detik dan menghitung laju drop paket (RX/TX drops) per antarmuka jaringan secara real-time. Jika paket drop > 0, cetak peringatan berwarna merah.

#### Level Medium
Buat sebuah systemd service unit bernama `secure-worker.service` yang menjalankan web server dummy (misal `python3 -m http.server 8080`). Konfigurasi service tersebut agar mengimplementasikan:
1. `MemoryMax=256M`
2. `CPUQuota=50%`
3. `ProtectSystem=strict`
4. `PrivateTmp=true`
5. `CapabilityBoundingSet=CAP_NET_BIND_SERVICE` (hapus privilege root lainnya).

#### Level Hard
Kembangkan program Python berbasis BCC (eBPF) yang melakukan monitor secara dinamis terhadap pemanggilan sistem *sys_enter_openat*. Program harus mencetak nama proses, nama file yang dibuka, status return code, dan menghitung durasi file descriptor tersebut terbuka hingga ditutup kembali (*sys_enter_close*).

---

### 14. Challenge

**Skenario Tantangan Produksi:**
Anda ditugaskan merestrukturisasi infrastruktur komputasi edge multi-tenant. Pada server ini, terdapat dua beban kerja kritis yang berjalan berdampingan:
1. **Engine Transaksi Kriptografi Real-Time:** Membutuhkan latensi p99.99 di bawah 500 mikrodetik, beban memori rendah (500MB), CPU 4-core.
2. **Batch Processing Log Aggregator:** Menghabiskan hingga 64GB RAM, membaca dan menulis puluhan gigabyte file log per menit ke local storage NVMe, sangat rentan menciptakan *dirty page storm*.

**Objektif Tantangan:**
Rancang konfigurasi arsitektur sistem operasi lengkap tanpa mengubah source code kedua aplikasi tersebut:
- Buat arsitektur isolasi cgroups v2 lengkap dengan konfigurasi I/O weight, Memory boundaries, dan CPU isolation.
- Petakan afinitas CPU dan pemisahan Core execution antara IRQ, Transaction Engine, dan Batch Aggregator.
- Konfigurasi parameter `sysctl` untuk memitigasi page cache starvation.
- Sediakan skrip verifikasi otomatis berbasis eBPF/perf untuk memvalidasi bahwa *Batch Processing Log Aggregator* tidak mendegradasi Transaction Engine saat siklus I/O puncak berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi dari modul *SLUB Allocator* di dalam kernel Linux, dan apa perbedaannya dengan *Buddy Allocator*?
   * *Jawaban:* Buddy Allocator mengalokasikan halaman memori berurutan (*contiguous pages*) dalam ukuran kelipatan $2^n$ (minimal 4KB), sedangkan SLUB Allocator bertugas mengalokasikan memori untuk objek kernel berukuran kecil (seperti file descriptors, task_struct) di dalam page tersebut untuk menghindari *internal fragmentation*.

2. Mengapa proses yang berstatus `D` (*Uninterruptible Sleep*) tidak dapat dihentikan menggunakan sinyal `SIGKILL` (`kill -9`)?
   * *Jawaban:* Karena thread tersebut sedang menunggu pemenuhan resource perangkat keras (biasanya I/O disk atau semaphore kernel). Kernel dirancang untuk tidak menginterupsi eksekusi pada status ini demi menjaga konsistensi state driver dan perangkat keras.

3. Apa keunggulan arsitektural utama Cgroups v2 dibandingkan dengan Cgroups v1?
   * *Jawaban:* Cgroups v2 mengimplementasikan hirarki tunggal terpadu (*unified hierarchy*), menghilangkan konflik antar-kontroler independen, mendukung manajemen I/O write-back yang terintegrasi dengan alokasi memori, serta memperkenalkan Pressure Stall Information (PSI).

4. Mengapa algoritma TCP BBR lebih unggul daripada TCP Cubic pada jaringan modern dengan tingkat paket drop acak?
   * *Jawaban:* TCP Cubic mengasumsikan paket drop sebagai indikator kongesti jaringan dan langsung memotong ukuran *congestion window*. Sebaliknya, TCP BBR memodelkan kapasitas aktual pipa jaringan berdasarkan *Bottleneck Bandwidth* dan *Round-Trip Time* (RTT), sehingga tidak terpengaruh oleh *loss* non-kongestif.

5. Dalam konteks arsitektur `io_uring`, apa peran dari Submission Queue (SQ) dan Completion Queue (CQ)?
   * *Jawaban:* SQ adalah *ring buffer* tempat aplikasi menaruh permintaan I/O (SQE) yang akan dieksekusi kernel, sedangkan CQ adalah *ring buffer* tempat kernel menulis status penyelesaian I/O (CQE) untuk dikonsumsi aplikasi secara lockless dan tanpa syscall.

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja mekanisme *Direct Reclaim* pada Linux Memory Management, dan apa dampaknya pada aplikasi yang sensitif terhadap latensi?
   * *Jawaban:* Direct Reclaim terjadi saat alokasi halaman memori gagal dipenuhi dari daftar bebas (*free list*) dan `kswapd` tertinggal. Thread aplikasi itu sendiri dipaksa kernel untuk membersihkan, menulis *dirty pages* ke disk, atau menukar halaman anonim ke swap sebelum alokasi dapat selesai. Hal ini menyebabkan thread aplikasi terhenti (*stall*) dan memicu lonjakan latensi (*latency spike*).

7. Jelaskan fenomena *Thundering Herd Problem* pada pemanggilan `epoll_wait` di arsitektur multi-process dan bagaimana flag `EPOLLEXCLUSIVE` mengatasinya!
   * *Jawaban:* Fenomena ini terjadi ketika beberapa thread/proses memantau satu listening socket yang sama. Saat ada satu koneksi masuk, semua proses terbangun serentak, namun hanya satu yang berhasil melakukan `accept()`, sementara sisanya kembali sleep. Ini membuang siklus CPU dan memicu lock contention. Flag `EPOLLEXCLUSIVE` memastikan kernel hanya membangunkan tepat satu thread/proses penunggu.

8. Apa perbedaan struktural antara metrik PSI `some` dan `full` pada analisis kehabisan sumber daya?
   * *Jawaban:* `some` mengukur persentase waktu di mana setidaknya ada *sebagian* non-idle task yang terhenti (*stalled*) menunggu resource tersebut (masih ada task lain yang bisa jalan). `full` mengukur persentase waktu di mana *seluruh* non-idle task di dalam cgroup terhenti secara total, merepresentasikan hilangnya kapasitas komputasi secara mutlak.

9. Mengapa *Transparent Huge Pages* (THP) sering direkomendasikan untuk dinonaktifkan (`madvise` atau `never`) pada basis data relasional seperti PostgreSQL atau database latensi rendah?
   * *Jawaban:* Kompaktifikasi memori dinamis (`khugepaged`) untuk membentuk halaman 2MB dapat mengunci region memori secara sinkron, menciptakan latensi ekstrem. Selain itu, mutasi kecil (misal 4KB) pada halaman 2MB memaksa sistem melakukan flush atau copy seluruh blok 2MB tersebut (*amplification overhead*).

10. Bagaimana pemisahan IRQ affinity dari core penanganan aplikasi dapat meningkatkan performa komputasi deterministik?
    * *Jawaban:* Pemisahan ini mencegah alur eksekusi aplikasi terputus secara acak oleh *Hardware Interrupt* dan *Software Interrupt* (`ksoftirqd`), menjaga agar L1/L2 data cache aplikasi tidak terinfiltrasi oleh buffer paket jaringan, dan meniadakan *jitter* penjadwalan.

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sebuah web service melaporkan ribuan connection timeout saat jam sibuk. Saat dicek via `netstat -s`, metrik `times the listen queue of a socket overflowed` terus bertambah, padahal utilisasi CPU baru mencapai 20%. Di mana letak masalahnya dan bagaimana memperbaikinya?
    * *Analisis & Solusi:* Masalah ada pada antrian *listen backlog* socket aplikasi yang penuh. Kernel membuang paket TCP SYN/ACK yang masuk. Solusi: Tingkatkan batas backlog aplikasi (misal backlog pada `listen(fd, backlog)`), naikkan batas kernel `net.core.somaxconn` (default sering kali hanya 128 atau 4096 menjadi 65535), dan tingkatkan `net.ipv4.tcp_max_syn_backlog`.

12. **Skenario 2:** Server Kafka mengalami I/O freeze berkala setiap 30 detik selama 3 hingga 5 detik. File log ditulis secara teratur tanpa buffering aplikasi. Selama freeze, utilisasi disk mencapai 100% dan throughput turun ke 0. Apa diagnosa subsistem memori Anda?
    * *Analisis & Solusi:* Server mengalami penumpukan *dirty pages* berlebih di Page Cache karena batas flusher terlalu longgar. Saat batas absolut `vm.dirty_ratio` terlampaui, kernel beralih ke mode sinkron (`throttle_vm_writeout`), memaksa seluruh thread Kafka untuk berhenti menulis dan mengosongkan buffer ke NVMe. Solusi: Turunkan `vm.dirty_background_bytes` ke 256MB dan `vm.dirty_bytes` ke 1GB agar flusher kernel mencicil I/O secara konstan tanpa menimbulkan akumulasi burst.

13. **Skenario 3:** Setelah deployment microservice baru di dalam klaster Kubernetes, node mengalami pembengkakan penggunaan memori sistem secara perlahan tanpa ada pod yang melebihi batas request/limit. Output `free -m` menunjukkan memori `used` tinggi, tetapi tidak ada di Page Cache (`buff/cache`). `slabtop` menunjukkan alokasi `dentry` dan `inode_cache` memakan 85% RAM. Apa akar permasalahannya?
    * *Analisis & Solusi:* Terjadi *Slab Memory Leak* di tingkat kernel. Kemungkinan besar microservice tersebut secara berulang melakukan scanning direktori yang sangat luas atau membuka jutaan file unik yang tidak pernah dibuka kembali tanpa menutupnya dengan benar, menyebabkan struktur data metadata VFS (`dentry` dan `inode`) memenuhi SLUB allocator. Solusi: Analisis aplikasi untuk menutup path traversal leak, atau atur `sysctl vm.vfs_cache_pressure = 100` (atau lebih tinggi, misal 150) agar kernel mereclaim dentry/inode cache secara lebih agresif.

---

### 16. Summary

Penguasaan Linux pada level arsitektur produksi tingkat lanjut menuntut transisi pemahaman dari sekadar operator perintah CLI menuju pemahaman rekayasa subsistem internal kernel. Performa sistem skala enterprise tidak hanya dibatasi oleh ketersediaan hardware, melainkan oleh efisiensi interaksi antara *User Space* dan *Kernel Space*:
1. **Memori dan I/O Terikat Erat:** Pengelolaan buffer I/O (`io_uring`, `Page Cache`) dan memori (`Buddy Allocator`, `SLUB`, `cgroups v2`) beroperasi secara simbiotik. Kesalahan kalkulasi dirty page write-back dapat menghentikan seluruh operasi I/O dan memicu latensi destruktif.
2. **Observabilitas Non-Invasif:** Standar pemantauan modern telah beralih ke eBPF. Instrumen lama yang melakukan sampling via context-switch tidak lagi memadai untuk menelusuri fenomena micro-burst atau tail-latency (P99.9+).
3. **Isolasi Deterministik:** Arsitektur multi-tenant modern bergantung pada integritas cgroups v2, evaluasi Pressure Stall Information (PSI), pembagian domain NUMA, serta IRQ/CPU pinning untuk menjamin aplikasi berperforma tinggi dapat berjalan berdampingan tanpa saling mendegradasi (*zero noisy-neighbor impact*).