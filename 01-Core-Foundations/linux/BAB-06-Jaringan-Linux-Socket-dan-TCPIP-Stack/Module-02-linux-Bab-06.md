# Kurikulum Rekayasa Sistem Berkelanjutan: Linux Kernel Internals, Performance Engineering & Production Architecture
**Kategori:** 01-Core-Foundations  
**Bab 06:** BAB-06-Materi-Lanjutan  
**Modul 02:** Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  
**Target Tingkat Kemahiran:** Senior Systems Engineer, Principal Platform Architect, SRE/Performance Engineer  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis Internal Subsistem Linux Kernel:** Menguraikan alur eksekusi subsistem manajemen memori (Page Cache, SLUB Allocator, NUMA), I/O subsystem (`io_uring`, VFS, block layer), dan CPU scheduler (EEVDF/CFS) hingga level struktur data kernel.
- **Mengembangkan Probing Telemetri Berbasis eBPF/BCC:** Menulis dan mengeksekusi program trace kustom menggunakan `bpftrace` dan kernel tracepoints untuk menganalisis latensi I/O dan jaringan pada granularitas sub-mikrodetik.
- **Merekayasa Konfigurasi Kernel Tingkat Lanjut:** Mengoptimasi parameter subsistem virtual memory (`vm.*`), stack TCP/IP (`net.core.*`, `net.ipv4.*`), serta resource accounting via Cgroups v2 untuk beban kerja berskala jutaan *requests per second* (RPS).
- **Mendiagnosis dan Mengeliminasi Kernel Bottlenecks:** Mengisolasi degradasi performa ekstrem (*tail latency*, jitter p99/p99.9) yang diakibatkan oleh *softirq saturation*, lock contention, kswapd thrashing, dan NUMA remote memory access.
- **Mendesain Arsitektur Sistem Produksi High-Throughput/Low-Latency:** Menerapkan strategi isolasi CPU (CPU pinning, thread isolation), bypass kernel selektif, dan optimalisasi pipeline I/O modern.

---

## 2. Prerequisites

Sebelum memasuki modul tingkat lanjut ini, peserta diasumsikan telah menguasai:
- **Foundations of Operating Systems:** Pemahaman mendalam terkait proses, thread, virtual memory, interrupt handling, dan POSIX system calls.
- **Pemrograman Sistem Tingkat Rendah:** Kemampuan membaca dan menulis bahasa C (pointers, memory management, low-level data structures) serta dasar-dasar assembly x86_64.
- **Administrasi Jaringan & Linux:** Pengalaman praktis dengan CLI Linux, CLI debugging standar (`gdb`, `strace`, `ltrace`), dan stack protokol TCP/IP (three-way handshake, congestion control).
- **Tooling Kompilasi:** Penguasaan `gcc`/`clang`, `make`, serta dependensi kernel headers (`linux-headers-$(uname -r)`).

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi produksi modern menuntut pemahaman deterministik terhadap bagaimana Linux Kernel berinteraksi langsung dengan silikon hardware.

```
+-----------------------------------------------------------------------------------+
|                                  USER SPACE                                       |
|  [ User Application ]       [ Libc / Runtime ]          [ io_uring Ring Buffers ]  |
+---------+----------------------------+-----------------------------+--------------+
          | System Calls               | Page Faults                 | Submission/  |
          | (sys_read, sys_epoll, dll) | (Virtual -> Physical alloc) | Completion   |
+---------v----------------------------v-----------------------------v--------------+
|                                  KERNEL SPACE                                     |
|                                                                                   |
|  [ Virtual File System (VFS) ] <--> [ Page Cache (Radix/XArray) ]                 |
|            |                                    |                                 |
|            v                                    v                                 |
|  [ Block Layer / Block MQ ] --------> [ Storage Driver (NVMe/SCSI) ]              |
|                                                                                   |
|  [ Network Stack: NAPI -> Gro -> dev_queue_xmit -> TCP/IP -> Ring Buffers ]       |
|                                                                                   |
|  [ Memory Management Subsystem ]                                                  |
|    - Per-Node Allocator (NUMA-aware Buddy System)                                 |
|    - Slab Allocator (SLUB): Task, mm_struct, sk_buff caches                       |
|    - Kernel Reclamation: kswapd, direct reclaim, Transparent Hugepages (THP)      |
|                                                                                   |
|  [ Scheduler Subsystem: EEVDF (Earliest Eligible Virtual Deadline First) / CFS ]  |
|    - Runqueues per CPU (rq), Context Switching, sched_slice balancing             |
|                                                                                   |
|  [ Observability Core: eBPF Engine, Kprobes, Tracepoints, Perf Events ]           |
+-----------------------------------------------------------------------------------+
|                                HARDWARE LAYER                                     |
|  [ CPU Cores / L1-L2-L3 Cache ]  [ Memory Controller / NUMA Nodes ]  [ PCIe / NIC ]
+-----------------------------------------------------------------------------------+
```

### 3.1 Memory Management: NUMA, Buddy Allocator, dan SLUB
Pada sistem multi-socket modern, arsitektur memori bersifat **Non-Uniform Memory Access (NUMA)**. Tiap socket CPU memiliki local memory bus sendiri. Pengaksesan memori pada remote node melalui interkoneksi (misal: Intel UPI atau AMD Infinity Fabric) menambahkan penalti latensi hingga 30–50%.

1. **Buddy System:** Kernel mengalokasikan halaman memori fisik berukuran eksponensial $2^n \times 4\text{ KiB}$ (order-0 hingga order-10). Masalah utama pada level ini adalah fragmentasi eksternal.
2. **SLUB Allocator:** Karena alokasi berukuran kecil (seperti struktur kernel `task_struct`, `sk_buff`, `file`) tidak efisien menggunakan satu frame halaman utuh, kernel menggunakan SLUB Allocator yang membungkus frame Buddy System menjadi *slab cache* objek tunggal tanpa internal metadata overhead yang kompleks.
3. **Zone Reclaim & Page Reclaim:** Saat local memory menipis, kernel harus memilih: melakukan *local direct reclaim* (mengorbankan CPU cycles aplikasi lokal untuk membebaskan cache) atau mengambil memori dari remote NUMA node (*remote allocation*). Parameter `vm.zone_reclaim_mode` mengontrol trade-off ini.

### 3.2 File I/O Architecture: Synchrous vs. Asynchronous (`io_uring`)
Pendekatan POSIX klasik `epoll(7)` + non-blocking socket memiliki keterbatasan mendasar: *system call overhead* yang berulang (dua context switch per panggilan I/O) dan ketidakmampuan menangani direct file I/O secara benar-benar asinkron tanpa thread-pool blocking.

`io_uring` mengeliminasi hambatan tersebut melalui dua lock-free single-producer single-consumer ring buffer yang dipetakan (*memory-mapped*) langsung antara user-space dan kernel-space:
- **Submission Queue (SQ):** User-space menulis perintah I/O ke dalam `SQRingEntry` dan memicu update pada submission head/tail pointer.
- **Completion Queue (CQ):** Kernel memproses operasi I/O dan menulis hasilnya ke dalam `CQRingEntry`.

Pada mode tingkat tinggi (`IORING_SETUP_SQPOLL`), kernel thread (`io_uring-sq`) secara kontinu melakukan polling pada SQ, memungkinkan eksekusi I/O dengan **nol system call** setelah setup awal.

### 3.3 Network Stack & Softirq Pipeline
Ketika paket tiba pada physical Network Interface Card (NIC):
1. NIC menggunakan Direct Memory Access (DMA) untuk menulis payload paket ke dalam kernel memory ring buffer (RX Ring).
2. NIC mengirimkan Hardware Interrupt (HardIRQ) ke CPU.
3. HardIRQ handler memicu mekanisme **NAPI (New API)** dan menjadwalkan Software Interrupt (`NET_RX_SOFTIRQ`), lalu segera mengembalikan context ke hardware.
4. `ksoftirqd/x` atau proses interrupt handler mengeksekusi `napi_poll()`, mengonsumsi paket secara batch dari ring buffer tanpa interupsi hardware berulang.
5. Paket dibungkus dalam struktur data `sk_buff`, melewati filtering (Netfilter/iptables), lapisan TCP state machine, hingga ditempatkan pada socket receive buffer (`sk_rcvbuf`).

---

## 4. Why & What

### Mengapa Pendekatan Linux Default Gagal di Skala Enterprise?
Secara default, distribusi Linux (Ubuntu, Debian, RHEL) dikonfigurasi untuk **kompatibilitas workstation umum**, bukan untuk *extreme throughput* atau *ultra-low tail-latency*:
- **Default TCP Window Size & Buffer Bounds** dibatasi secara konservatif untuk menghemat RAM (misal, `tcp_rmem` default sering membatasi window scaling pada link 100GbE, mengakibatkan bandwidth bottleneck via BDP—*Bandwidth-Delay Product*).
- **CPU Scheduling Dynamic Migrations** menyebabkan instruksi cache L1/L2 sering terbuang (*cache thrashing*) karena proses dipindah-pindah antar core/NUMA nodes oleh load balancer kernel.
- **Paging & Allocation Stalls:** Penggunaan `Transparent Hugepages (THP)` mode `always` dapat menyebabkan alokasi memori acak mengalami *freeze* puluhan milidetik ketika thread kernel `khugepaged` melakukan defragmentasi dan zeroing halaman 2MiB di critical path.

### Apa yang Dilakukan oleh Arsitektur Lanjutan?
Arsitektur tingkat lanjut merekayasa sistem Linux menjadi platform deterministik:
- Mendefinisikan afinitas perangkat keras terhadap jalur data software (NUMA pinning, IRQ steering via `smp_affinity`).
- Menghilangkan context switch overhead menggunakan antarmuka modern zero-copy / zero-syscall (`io_uring`, XDP - eXpress Data Path).
- Memanfaatkan observabilitas deterministik berbasis in-kernel verification (eBPF) yang tidak menghentikan runtime proses.

---

## 5. How (Workflow Detail)

Berikut adalah alur perjalanan pengolahan I/O asinkron performa tinggi berbasis `io_uring` dan integrasi jaringan berkecepatan tinggi:

```
[ User Application Space ]
       |
       | 1. Siapkan SQE (Submission Queue Entry) pada mapped ring
       v
+------------------+
| Submission Queue |  <--- User menulis tail pointer secara atomic
+------------------+
       |
       | 2. io_uring_enter() syscall (Dieliminasi jika IORING_SETUP_SQPOLL aktif)
       v
[ Kernel Space Engine ]
       |
       +---> Dispatcher memvalidasi operation code (READV, WRITEV, ACCEPT, SPLICE)
       |
       +---> [ VFS Layer ]
       |        |
       |        +--> Cek Page Cache (XArray)
       |        +--> Cache Miss: Block Layer Submission (blk-mq)
       |        +--> Request disatukan (I/O scheduler: none/mq-deadline)
       |        +--> NVMe driver mentransfer data via DMA
       |
       +---> Operasi Selesai (IRQ callback memicu kernel menulis CQE)
       v
+------------------+
| Completion Queue |  <--- Kernel menulis tail pointer secara atomic
+------------------+
       |
       | 3. User membaca CQE (Completion Queue Entry) secara lock-free
       v
[ User Application Space ]
```

Workflow Pengelolaan Interrupt Jaringan (Hardware-to-Application Path):
1. **Paket Masuk:** Paket ethernet diterima NIC PHY layer, disimpan di FIFO buffer internal adapter.
2. **DMA Transfer:** NIC menginisiasi DMA bus transaction untuk menyalin frame ke kernel memory buffer (`struct sk_buff` array).
3. **HardIRQ Delivery:** NIC mengirim sinyal MSI-X interrupt ke CPU core tertentu (berdasarkan konfigurasi `/proc/irq/<num>/smp_affinity_list`).
4. **Softirq Activation:** CPU melumpuhkan interupsi hardware untuk perangkat tersebut dan membangkitkan `NET_RX_SOFTIRQ`.
5. **NAPI Polling Loop:** Di dalam konteks softirq, driver kernel mengeksekusi function `poll()` dalam kuota tertentu (biasanya 64 paket per loop per core, dikontrol oleh `net.core.netdev_budget`).
6. **Protocol Ingress:** Paket didereferensikan melewati firewall stack (eBPF TC sub-engine atau Netfilter), didekapsulasi oleh `tcp_v4_rcv()`, dan diparkir di Socket Receive Queue.
7. **Wakeup:** Aplikasi yang menunggu via `epoll_wait` atau `io_uring` diubah statusnya menjadi `TASK_RUNNING` oleh CPU scheduler.

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Terautomasi vs. Kurir Tradisional

- **Model Klasik (POSIX System Calls - `read`/`write`/`epoll`):**  
  Seperti petugas gudang (User Space) yang setiap membutuhkan barang harus berjalan menghampiri gerbang utama pabrik (Kernel Boundary), menyerahkan formulir permintaan, menunggu satpam memeriksa identitasnya (Context Switch & Privileged Transition), menunggu barang diambil dari rak, lalu berjalan kembali ke ruangannya. Jika ada 10.000 barang, proses buka-tutup gerbang ini terjadi puluhan ribu kali per detik.
- **Model Modern (`io_uring` SQPOLL & Shared Rings):**  
  Pabrik memasang dua *conveyor belt* melingkar (Shared Ring Buffers) antara ruang gudang dan dalam pabrik. Petugas cukup menaruh nota kerja di belt pertama (Submission Queue), dan lengan robot internal pabrik (Kernel SQ Poller Thread) langsung mengerjakannya secara paralel tanpa satpam perlu memeriksa ulang identitas di gerbang. Barang yang selesai otomatis dikembalikan lewat belt kedua (Completion Queue). Tidak ada satu pun langkah kaki terbuang untuk melewati gerbang.

```
Arsitektur Aliran Kontrol: POSIX Call vs. io_uring

A. POSIX MODEL (Epoll + Read)
User App                      Kernel Space                     Hardware
   |                               |                              |
   |--- 1. epoll_wait() ---------->| (Context Switch ke Ring 0)   |
   |<-- Return Events -------------|                              |
   |                               |                              |
   |--- 2. read(fd, buf) --------->| (Context Switch ke Ring 0)   |
   |                               |--- 3. Direct Memory Access ->|
   |                               |<-- Data Returned ------------|
   |<-- Return Bytes/Error --------|                              |
  (2x Syscalls, 4x Context Switches per I/O event)

B. io_uring MODEL (dengan SQPOLL)
User App                 Shared Ring Memory            Kernel Thread (SQPOLL)
   |                             |                               |
   |-- Tulis SQE ke Ring Memory ->|                               |
   |   (No Syscall!)             |-- Kernel Thread Poll Ring --->|
   |                             |   (Memproses I/O langsung)    |
   |                             |<-- Tulis CQE ke Ring Memory --|
   |<-- Baca CQE dari Ring Memory-|
  (0x Syscall per I/O event pada kondisi tunak)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic In-Kernel Tracing dengan `bpftrace`
Skrip berikut mengukur distribusi durasi *block I/O latency* secara real-time pada level block driver, memetakan dalam bentuk histogram logaritmik:

Simpan sebagai: `biolatency.bt`
```bpftrace
#!/usr/bin/env bpftrace

BEGIN
{
    printf("Tracing block layer I/O latency... Tekan Ctrl-C untuk berhenti.\n");
}

/* Tangkap timestamp saat request dimasukkan ke block device queue */
tracepoint:block:block_bio_queue
{
    @start[args->dev, args->sector] = nsecs;
}

/* Tangkap waktu ketika request selesai dieksekusi oleh driver storage */
tracepoint:block:block_bio_complete
/@start[args->dev, args->sector]/
{
    $duration_us = (nsecs - @start[args->dev, args->sector]) / 1000;
    @usecs = hist($duration_us);
    delete(@start[args->dev, args->sector]);
}

END
{
    printf("\nDistribusi Latensi I/O (dalam Mikrodetik):\n");
}
```

Jalankan dengan:
```bash
sudo bpftrace biolatency.bt
```

### 7.2 Practical Example: Asynchronous File Submitter Menggunakan `liburing`
Contoh program C tingkat enterprise yang membaca metadata blok file secara asinkron tanpa memblokir thread eksekusi utama, mematuhi prinsip zero-copy.

Simpan sebagai: `iouring_reader.c`
```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <liburing.h>

#define QUEUE_DEPTH 32
#define BLOCK_SIZE  4096

struct io_request {
    int fd;
    struct iovec iov;
};

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Penggunaan: %s <path-to-file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    struct io_uring ring;
    int ret = io_uring_queue_init(QUEUE_DEPTH, &ring, 0);
    if (ret < 0) {
        perror("Gagal menginisialisasi io_uring");
        return EXIT_FAILURE;
    }

    int fd = open(argv[1], O_RDONLY | O_DIRECT);
    if (fd < 0) {
        perror("Gagal membuka file (O_DIRECT membutuhkan alignment 4KB)");
        io_uring_queue_exit(&ring);
        return EXIT_FAILURE;
    }

    // Alokasikan memory buffer yang ter-align pada boundary 4KB untuk Direct I/O
    void *buffer;
    if (posix_memalign(&buffer, BLOCK_SIZE, BLOCK_SIZE)) {
        perror("Alokasi memory aligned gagal");
        close(fd);
        io_uring_queue_exit(&ring);
        return EXIT_FAILURE;
    }

    struct io_request req;
    req.fd = fd;
    req.iov.iov_base = buffer;
    req.iov.len = BLOCK_SIZE;

    // Ambil slot Submission Queue Entry (SQE)
    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    if (!sqe) {
        fprintf(stderr, "SQE ring buffer penuh!\n");
        return EXIT_FAILURE;
    }

    // Siapkan operasi baca I/O (vectored read)
    io_uring_prep_readv(sqe, fd, &req.iov, 1, 0);
    io_uring_sqe_set_data(sqe, &req);

    // Submit request ke kernel
    io_uring_submit(&ring);

    // Tunggu Completion Queue Entry (CQE)
    struct io_uring_cqe *cqe;
    ret = io_uring_wait_cqe(&ring, &cqe);
    if (ret < 0) {
        perror("Error menunggu CQE");
        return EXIT_FAILURE;
    }

    if (cqe->res < 0) {
        fprintf(stderr, "Operasi I/O async gagal: %s\n", strerror(-cqe->res));
    } else {
        printf("I/O Berhasil Dieksekusi. Ukuran data dibaca: %d bytes\n", cqe->res);
    }

    // Mark completion queue entry sebagai diproses
    io_uring_cqe_seen(&ring, cqe);

    // Cleanup resources
    free(buffer);
    close(fd);
    io_uring_queue_exit(&ring);

    return EXIT_SUCCESS;
}
```

Kompilasi dengan:
```bash
gcc -O2 -Wall -D_GNU_SOURCE iouring_reader.c -o iouring_reader -luring
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Degenerasi Tail Latency (p99.99) pada Sistem Distributed Payment Gateway
- **Latar Belakang Perusahaan:** Gateway pembayaran finansial Tier-1 memproses rata-rata 1.500.000 HTTP API RPS yang didistribusikan ke cluster multi-socket server (Dual Socket AMD EPYC 7763, 128 Cores/256 Threads, 1TB RAM, dual 100GbE NICs).
- **Insiden:** Terjadi *intermittent spike* p99.9 latensi dari kisaran stabil 1.2 milidetik melonjak hingga 450 milidetik selama lonjakan volume transaksi, memicu pemutusan massal oleh upstream bank (*HTTP 504 Gateway Timeout*).

### Investigasi Metodologis
1. **Analisis CPU Bottleneck:** Total utilitas CPU hanya mencapai 45%. Namun, metrik `mpstat -P ALL 1` menunjukkan CPU 0-3 berjalan pada status 100% utilitas di dalam kolom `%soft` (SoftIRQ starvation).
2. **IRQ Imbalance Profiling:** Pengecekan `/proc/interrupts` membuktikan bahwa seluruh multi-queue receive queues (RX ring) dari kartu jaringan 100GbE dialokasikan secara eksklusif ke Socket 0, khususnya core 0 hingga 7, menyebabkan thread `ksoftirqd` mengalami antrean backlog tinggi (`netdev_max_backlog`).
3. **Analisis Alokasi Memori (NUMA Throttling):**
   ```bash
   numastat -c payment_gateway_service
   ```
   Ditemukan metrik *Node 1 numa_miss* dan *foreign_alloc* bernilai jutaan. Aplikasi dialokasikan pada Node 1, tetapi buffer NIC mengalokasikan memori paket pada Node 0 via DMA engine. Hal ini membebani AMD Infinity Fabric link (*Inter-Socket Bus Contention*).
4. **Transparent Hugepages Stall:**
   ```bash
   bpftrace -e 'kprobe:alloc_pages_vma { @start[tid] = nsecs; } kretprobe:alloc_pages_vma /@start[tid]/ { @dist = hist(nsecs - @start[tid]); delete(@start[tid]); }'
   ```
   Ditemukan alokasi memori terkunci selama 100ms+ di dalam `compact_zone()` akibat defragmentasi memori fisik Transparent Hugepages (THP) yang berupaya menyatukan fragmen halaman 4KiB menjadi kontigu 2MiB.

### Solusi & Remediasi Arsitektur
1. **Penerapan Afinitas NUMA & Interrupt Steering:**
   - Jaringan NIC diikat langsung ke socket lokalnya menggunakan skrip konfigurasi `set_irq_affinity` bawaan driver jaringan.
   - Proses backend diisolasi ke dalam node NUMA yang sama dengan NIC controller via `numactl --cpunodebind=0 --membind=0`.
2. **Deaktivasi Aggressive Memory Compaction:**
   ```bash
   echo madvise > /sys/kernel/mm/transparent_hugepage/enabled
   echo madvise > /sys/kernel/mm/transparent_hugepage/defrag
   ```
3. **Penyelarasan Network Core Budget:**
   Menaikkan kuota pemrosesan frame paket NAPI per softirq cycle guna mencegah luapan ring buffer:
   ```sysctl
   net.core.netdev_budget = 600
   net.core.netdev_budget_usecs = 4000
   ```
4. **Hasil:** Latensi tail p99.9 turun secara drastis dari 450 milidetik menjadi **1.8 milidetik** secara konsisten, mengeliminasi connection drops secara permanen.

---

## 9. Trade-offs

Setiap intervensi tuning di level sistem operasi membawa konsekuensi langsung (*trade-off*). Tidak ada konfigurasi universal:

| Dimensi Rekayasa | Opsi Implementasi | Keuntungan (Pros) | Biaya & Konsekuensi (Cons/Trade-offs) |
| :--- | :--- | :--- | :--- |
| **I/O Engine** | POSIX `epoll` | Sederhana, kompatibel secara universal, aman dari kebocoran memori kernel. | Overhead syscall signifikan pada RPS masif; limited support untuk file system I/O paralel. |
| | Linux `io_uring` | Zero syscall (pada mode SQPOLL), latensi sub-mikrodetik, asinkron native untuk network dan disk. | Kompleksitas debugging tinggi; rentan eksploitasi keamanan jika kernel lama (< 5.10); memakan thread CPU dedicated untuk pooling SQ. |
| **Memory Allocation** | Transparent Hugepages (`always`) | Peningkatan hit rate TLB (Translation Lookaside Buffer) untuk komputasi memori besar (misal Database OLAP). | Menyebabkan latency spike (stall puluhan milidetik) saat alokasi real-time akibat proses `direct compaction`. |
| | THP (`madvise` / `never`) | Latensi alokasi memori sangat konsisten dan deterministik; eliminasi defragmentation stalls. | Beban TLB miss lebih tinggi; penggunaan metadata page tables naik hingga 4x lipat pada beban in-memory besar. |
| **Network Processing** | Default IRQ Balance (`irqbalance`) | Distribusi otomatis beban interrupt ke seluruh core CPU; mudah dikelola. | Cache L1/L2 invalidate berkelanjutan; cross-NUMA access yang merusak jitter deterministik aplikasi low-latency. |
| | Static IRQ Affinity & CPU Pinning | Cache locality terjaga 100%; latensi sub-milidetik tercapai; isolasi resource mutlak. | Konfigurasi sangat kaku; jika load pada satu RX queue meledak, CPU yang dialokasikan akan jenuh sementara core lain idle. |
| **Storage Scheduling** | I/O Scheduler `none` (No-op) | Latensi minimum absolut untuk NVMe flash storage berkecepatan ultra tinggi; bypass overhead antrean kernel. | Tiada prioritas fairness; starvation bisa menimpa proses kecil saat ada thread lain membanjiri bus I/O dengan write batch besar. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum dalam Arsitektur Linux Produksi
1. **Blind Copy-Paste Sysctl Configurations:** Mengambil parameter tuning dari forum internet (misal: menaikkan `net.ipv4.tcp_rmem` ke 64MB per socket tanpa menghitung total socket capacity, berujung pada pemicuan `Out-Of-Memory (OOM) Killer` saat terjadi connection spike).
2. **Mengabaikan SoftIRQ Saturation:** Hanya mengamati CPU utilization via `top` (melihat nilai *idle* agregat) tanpa memperhatikan kolom `si` (SoftIRQ). Satu core yang tercekik 100% `si` dapat melumpuhkan seluruh antrean ingress paket jaringan.
3. **Mengabaikan TCP Time-Wait Recycling Pitfall:** Mengaktifkan flag legacy `net.ipv4.tcp_tw_recycle = 1` (sudah dihapus di kernel 4.12+ namun sering dipaksa via konfigurasi usang). Ini menyebabkan paket TCP drop secara acak dari klien di balik NAT komersial karena timestamp validation checks gagal.

### Prosedur Troubleshooting Sistematis

```
                  [ Gejala: Tingginya Latensi / Penurunan Throughput ]
                                         |
                                         v
                         Jalankan `vmstat -w 1` & `mpstat -P ALL 1`
                                         |
               +-------------------------+-------------------------+
               |                                                   |
      %si (SoftIRQ) Tinggi?                               %wa (I/O Wait) Tinggi?
               |                                                   |
               v                                                   v
   Periksa: `/proc/interrupts`                         Periksa: `iostat -xz 1`
   Identifikasi RX/TX queue binding                   Cari await, %util disk
               |                                                   |
               +--> Solusi: Set static IRQ                         +--> Solusi: Ganti I/O Scheduler,
                    smp_affinity ke core lokal                          evaluasi Direct I/O via io_uring
               |
               v
      %sys (System Time) Tinggi?
               |
               v
   Jalankan: `perf top` atau `perf record -a -g -- sleep 5`
   Deteksi lock contention: spinlock, mutex, atau page fault storm
               |
               +--> Solusi: Evaluasi NUMA locality (`numastat`), mitigasi THP
```

#### Diagnostic Commands Cheat-Sheet:
```bash
# 1. Menganalisis CPU core mana yang menangani Software Interrupt secara tidak seimbang
watch -n 1 -d "cat /proc/interrupts | egrep '(CPU|eth|nvme)'"

# 2. Mengukur Lock Contention pada Kernel Space secara real-time
sudo perf top -F 99 --sort comm,dso,symbol

# 3. Mendeteksi alokasi memori yang jatuh ke remote NUMA node
numastat -m

# 4. Mendeteksi dropped packets pada layer kernel ring buffer
netstat -s | grep -i "buffer errors"
ethtool -S <interface_name> | grep -E "(drop|error|miss)"
```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar parameter deterministik ini sebagai *baseline* pada server platform berperforma tinggi (Kernel 5.15+ / 6.x):

### A. Subsystem Virtual Memory (Sysctl Baseline)
```ini
# hands-on/m02/sysctl-production.conf

# Kurangi agresivitas kernel untuk swapping data anonymous ke disk
vm.swappiness = 10

# Naikkan threshold dirty pages sebelum background flush kernel (pdflush/flush) diaktifkan
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10

# Cegah sistem kehabisan memori secara mendadak dengan alokasi ketat
vm.overcommit_memory = 0
vm.overcommit_ratio = 50

# Tingkatkan batas jumlah virtual memory mapping areas (Wajib untuk database & runtime JVM)
vm.max_map_count = 1048576

# Nonaktifkan zone reclaim agar memory dialokasikan dari node lain jika lokal habis, bukan menghentikan I/O
vm.zone_reclaim_mode = 0
```

### B. Subsystem Jaringan & TCP Core (High Throughput, Low Latency)
```ini
# Maksimalkan ukuran antrean socket connection backlog
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65536

# Alokasi buffer memori TCP (Min, Default, Max dalam satuan bytes)
# Tuning untuk network link 10GbE / 40GbE / 100GbE
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432

# Aktifkan BBR Congestion Control (Membutuhkan modul tcp_bbr aktif)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Aktifkan TCP Fast Open (Client & Server)
net.ipv4.tcp_fastopen = 3

# Nonaktifkan slow start restart untuk menjaga performa koneksi yang sempat idle
net.ipv4.tcp_slow_start_after_idle = 0

# Mitigasi SYN Flood attacks dan lindungi connection table
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
```

### C. File & Resource Limits (`/etc/security/limits.conf`)
```text
*               soft    nofile          1048576
*               hard    nofile          1048576
*               soft    memlock         unlimited
*               hard    memlock         unlimited
```

### D. Production Deployment Architecture Checklist
- [ ] Nonaktifkan C-states dalam BIOS / UEFI untuk sistem latensi ultra-rendah (`intel_idle.max_cstate=0` atau `processor.max_cstate=0` di kernel parameters).
- [ ] Isolasi CPU cores untuk engine komputasi utama menggunakan parameter bootloader `isolcpus=24-63 nohz_full=24-63 rcu_nocbs=24-63`.
- [ ] Atur I/O scheduler storage NVMe ke `none`: `echo none > /sys/block/nvme0n1/queue/scheduler`.
- [ ] Bind NIC HardIRQ langsung ke core socket CPU lokal melalui script isolasi IRQ.
- [ ] Ganti Cgroups v1 dengan Cgroups v2 secara universal untuk akuntansi resource memory buffer I/O yang akurat.

---

## 12. Hands-on Practice

Target Workspace: `hands-on/m02/`

### Skenario: Mendiagnosis dan Mengoptimasi Bottleneck High-Concurrency Server
Latihan ini memandu pembuatan lingkungan benchmark lokal untuk mendemonstrasikan saturasi interrupt kernel, visualisasi antrean paket, dan mitigasi latensi.

#### Langkah 1: Persiapan Environment dan Dependencies
```bash
mkdir -p hands-on/m02/scripts
cd hands-on/m02/

# Pasang dependency kernel tools dan compiler
sudo apt-get update
sudo apt-get install -y build-essential liburing-dev bpftrace linux-tools-common \
    linux-tools-generic linux-tools-$(uname -r) numactl wrk fio
```

#### Langkah 2: Script Profiling eBPF untuk Latensi Syscall Read/Write
Tulis skrip tracing untuk mengidentifikasi proses mana yang menahan CPU context paling lama pada lapisan Virtual File System (VFS).

Simpan skrip berikut ke `hands-on/m02/scripts/vfs_latency.bt`:
```bpftrace
#!/usr/bin/env bpftrace

kprobe:vfs_read,
kprobe:vfs_write
{
    @start[tid] = nsecs;
}

kretprobe:vfs_read,
kretprobe:vfs_write
/@start[tid]/
{
    $lat = (nsecs - @start[tid]) / 1000;
    @vfs_lat_us[comm] = hist($lat);
    delete(@start[tid]);
}

interval:s:5
{
    printf("\n--- Latensi Operasi VFS (5 Detik Terakhir) ---\n");
    print(@vfs_lat_us);
    clear(@vfs_lat_us);
}
```

Jalankan tracing di terminal terpisah:
```bash
sudo bpftrace hands-on/m02/scripts/vfs_latency.bt
```

#### Langkah 3: Benchmark Storage I/O Baseline: Non-Direct vs Direct `io_uring`
Bandingkan throughput dan tail-latency disk antara I/O konvensional synchronous dan `io_uring` terdistribusi.

1. **Test Run A (Synchronous POSIX I/O via Page Cache):**
   ```bash
   fio --name=sync-read-test \
       --filename=test_io.bin \
       --size=2G \
       --readwrite=randread \
       --bs=4k \
       --ioengine=sync \
       --direct=0 \
       --numjobs=8 \
       --time_based --runtime=15 \
       --group_reporting
   ```

2. **Test Run B (High-Performance Engine `io_uring` Direct I/O):**
   ```bash
   fio --name=iouring-read-test \
       --filename=test_io.bin \
       --size=2G \
       --readwrite=randread \
       --bs=4k \
       --ioengine=io_uring \
       --direct=1 \
       --iodepth=64 \
       --numjobs=8 \
       --time_based --runtime=15 \
       --group_reporting
   ```
*Evaluasi perbandingan metrik IOPS, p99.9 latency, dan CPU overhead antara kedua engine.*

#### Langkah 4: Membersihkan Environment
```bash
rm -f test_io.bin
```

---

## 13. Exercises

### Tingkat: Easy
1. Gunakan perintah `sysctl` untuk membaca dan mengubah konfigurasi `net.core.somaxconn` secara runtime, lalu pastikan nilainya persisten setelah proses reboot melalui file konfigurasi modular di `/etc/sysctl.d/99-custom.conf`.
2. Identifikasi jumlah node NUMA pada sistem pengujian Anda dan temukan CPU core mana yang terikat pada masing-masing node menggunakan tool CLI bawaan Linux.
   - **Kriteria Keberhasilan:** Ekstraksi output valid dari utilitas `numactl -H` dan `lscpu`.

### Tingkat: Medium
1. Tulis sebuah program C sederhana yang mengimplementasikan `posix_memalign()` untuk mengalokasikan page buffer 4KiB, membuka sebuah file dengan flag `O_DIRECT`, dan menuliskan data string ke dalamnya. 
   - **Kriteria Keberhasilan:** Program berhasil melakukan flush write ke disk tanpa return code error `-EINVAL`.
2. Buat skrip automasi shell (`set_affinity.sh`) yang mendeteksi seluruh network IRQ pada sistem dari `/proc/interrupts` dan menetapkan afinitas proses interrupt tersebut secara merata (*round-robin*) pada CPU core socket 0 saja.
   - **Kriteria Keberhasilan:** Pengecekan `/proc/irq/<irq_num>/smp_affinity_list` menunjukkan mapping core yang tepat.

### Tingkat: Hard
1. Buat program `bpftrace` yang melakukan observasi terhadap lifecycle eksekusi fungsi CPU scheduler kernel: `pick_next_task_fair` (untuk CFS) atau `pick_next_task_eevdf` (pada Kernel 6.6+). Tangkap dan hitung durasi waktu yang dihabiskan oleh kernel murni untuk memilih task berikutnya yang akan dieksekusi per core CPU.
   - **Kriteria Keberhasilan:** Skrip mampu mencetak ringkasan latensi context scheduling dalam histogram mikrodetik tanpa mengalami dropped events pada sistem yang sedang mengalami stress test `stress-ng --cpu 8`.

---

## 14. Challenges

### Skenario Kasus Kompleks: "The Million-Connection Phantom Out-of-Memory Incident"

#### Deskripsi Lingkungan
Sebuah platform broker WebSocket terdistribusi dirancang untuk menampung 1.000.000 concurrent connection dalam satu server tunggal (Bare-Metal, RAM 128GB, 64-Core CPU, Ubuntu 22.04 LTS, Kernel 5.15).

#### Permasalahan
Saat traffic ramp-up mencapai angka 600.000 koneksi aktif (dengan traffic rata-rata yang sangat rendah per koneksi, hanya heartbeat keep-alive setiap 30 detik):
1. Penggunaan memori fisik melalui perintah `free -m` mendadak melonjak hingga 98% terpakai.
2. Kernel OOM Killer aktif dan mematikan proses utama WebSocket.
3. Namun, metrik RSS memory (`Resident Set Size`) dari proses WebSocket tersebut di laporan `/proc/<pid>/status` tercatat hanya menggunakan memori total sebesar **22GB RAM**. Terdapat selisih misterius lebih dari **90GB RAM** yang tidak terlacak oleh profiling user-space standar.

#### Tugas Rekayasa Anda
- Lakukan isolasi teknis: Ke mana perginya sisa memory 90GB tersebut di level kernel?
- Struktur data kernel internal apa yang mengonsumsi memori ini? (*Petunjuk: Pelajari alokasi SLUB kernel, socket tracking structure, sk_buff read/write buffers, conntrack table overhead, dan buffer TCP accounting*).
- Rancang strategi konfigurasi sysctl kernel, tuning struktur data network stack, serta arsitektur socket yang memungkinkan 1.000.000 koneksi ini bertahan dengan alokasi total memori hardware kurang dari 64GB RAM tanpa memicu OOM Killer.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Apa perbedaan mendasar antara alokasi memori melalui Buddy System vs. SLUB Allocator di dalam Linux Kernel?**  
   *Kunci Jawaban:* Buddy System mengelola alokasi frame halaman fisik berukuran besar berbasis eksponensial $2^n \times 4\text{ KiB}$ untuk memitigasi fragmentasi eksternal. SLUB Allocator dibangun di atas Buddy System untuk mengalokasikan objek kernel kecil (seperti `struct task_struct`, file descriptors, inodes) guna mencegah fragmentasi internal.

2. **Mengapa Direct I/O (`O_DIRECT`) menuntut data memory buffer harus aligned secara spesifik (misal kelipatan 512 bytes atau 4KiB)?**  
   *Kunci Jawaban:* Karena Direct I/O melewati (bypass) Page Cache Linux Kernel secara langsung mentransfer block ke/dari storage controller via Direct Memory Access (DMA). Storage hardware controller dan DMA engine mensyaratkan addressing memory berbasis physical alignment boundary.

3. **Apa fungsi utama dari ring buffer completion queue (CQ) pada arsitektur `io_uring`?**  
   *Kunci Jawaban:* Sebagai media komunikasi lock-free satu arah tempat kernel menuliskan hasil status/return code dari operasi I/O asinkron yang telah selesai dieksekusi, sehingga user-space application dapat mengonsumsinya tanpa memicu context switch.

4. **Apa yang diindikasikan oleh nilai kolom `%si` pada output monitoring `top` atau `mpstat`?**  
   *Kunci Jawaban:* Persentase waktu CPU yang dihabiskan untuk melayani Software Interrupts (`SoftIRQ`), seperti pemrosesan paket jaringan ingress via NAPI atau callback timer disk.

5. **Apa risiko menyalakan `vm.overcommit_memory = 2` pada sistem Linux?**  
   *Kunci Jawaban:* Kernel akan menerapkan pembatasan ketat bahwa alokasi memori total tidak boleh melebihi formula `Swap + (RAM * overcommit_ratio)`. Hal ini dapat menyebabkan system call `malloc()` gagal (*out of memory error*) bahkan ketika sistem masih memiliki sisa physical RAM bebas yang cukup banyak.

---

### Bagian 2: Intermediate (5 Pertanyaan)

1. **Jelaskan siklus hidup penanganan paket jaringan dari saat NIC mendeteksi sinyal listrik/cahaya hingga data masuk ke socket buffer aplikasi!**  
   *Kunci Jawaban:* (1) NIC menulis paket ke memory host via DMA RX ring buffer; (2) NIC membangkitkan HardIRQ; (3) HardIRQ handler kernel menjadwalkan `NET_RX_SOFTIRQ` lalu mematikan interupsi NIC (NAPI); (4) Polling loop `ksoftirqd` mengambil frame paket dari ring buffer; (5) Kernel membungkus data dalam `sk_buff`, mengeksekusi routing, Netfilter/eBPF; (6) Paket dimasukkan ke antrean socket buffer aplikasi; (7) Thread aplikasi di-wakeup oleh scheduler.

2. **Bagaimana mekanisme Transparent Hugepages (THP) memicu lonjakan latensi (latency spikes) pada aplikasi dengan footprint memory intensif dan acak?**  
   *Kunci Jawaban:* Ketika memory fisik terfragmentasi dan mode THP `always` aktif, thread kernel `khugepaged` atau alokasi lokal memicu *Direct Memory Compaction*. Pada fase ini, kernel mengunci (*lock*) memory zones, menyalin halaman-halaman 4KiB yang terpencar menjadi 2MiB kontigu, menghentikan alokasi proses aplikasi selama puluhan hingga ratusan milidetik.

3. **Mengapa alokasi memori lintas node NUMA (NUMA Remote Access) dapat menurunkan performa sistem database in-memory?**  
   *Kunci Jawaban:* Karena instruksi pembacaan/penulisan memori harus melintasi bus interkoneksi antar CPU socket (seperti QPI/UPI atau Infinity Fabric) yang memiliki bandwidth lebih sempit dan latensi propagasi jauh lebih tinggi dibanding mengakses local memory bus pada socket yang sama.

4. **Dalam kondisi apa I/O Scheduler Linux sebaiknya diatur ke `none` (No-Op Scheduler)?**  
   *Kunci Jawaban:* Saat sistem menggunakan media penyimpanan non-rotasional modern bertaraf tinggi seperti NVMe SSD. Drive NVMe memiliki puluhan ribu hardware queue internal sendiri (`blk-mq`), sehingga penjadwalan/merging di software layer kernel hanya akan menambah latensi CPU dan overhead lock contention.

5. **Jelaskan peran teknologi eBPF (Extended Berkeley Packet Filter) dalam observabilitas performa Linux dibandingkan `strace`!**  
   *Kunci Jawaban:* `strace` menggunakan mekanisme `ptrace` yang menghentikan (*pause/context switch*) proses target pada setiap entry dan exit system call, menyebabkan perlambatan kinerja ekstrem (hingga puluhan kali lipat). eBPF menginjeksi program bytecode yang diverifikasi langsung ke dalam kernel space untuk mengumpulkan metrik secara in-situ dengan overhead mendekati nol tanpa memblokir runtime target.

---

### Bagian 3: Production Case Scenarios (3 Skenario)

#### Skenario 1: The Mystery of the Locked Engine
- **Kasus:** Setelah mengaktifkan multi-threading berskala tinggi pada aplikasi transaksi finansial C++, Anda mendapati CPU utilization mencapai 100% pada semua core, namun *Throughput Transaksi* merosot 80%. Profiling menggunakan `perf top` menampilkan simbol `native_queued_spin_lock_slowpath` mendominasi 70% siklus CPU.
- **Pertanyaan:** Apa yang sebenarnya terjadi di level kernel, dan tindakan rekayasa apa yang harus Anda ambil untuk menyelesaikannya?
- **Kunci Jawaban & Analisis:**
  - *Diagnosa:* Terjadi **Spinlock Contention** parah di dalam kernel space. Banyak thread yang berjalan paralel mencoba mengakses struktur data kernel global yang sama (misal: lock socket table, mutex memory allocator, atau lock pada file descriptor table bersama). CPU menghabiskan seluruh siklusnya hanya untuk *busy-waiting* (berputar di loop spinlock) menunggu giliran lock dilepas.
  - *Mitigasi Arsitektur:*
    1. Hindari contention file descriptor tunggal: Terapkan soket independen per-thread via flag `SO_REUSEPORT` sehingga setiap thread memiliki antrean socket terpisah di kernel.
    2. Hindari alokasi memori berulang pada critical path: Ganti user-space dynamic allocator standar (`glibc ptmalloc`) dengan memory allocator teroptimasi multi-thread (`jemalloc` atau `tcmalloc`) yang menggunakan thread-local caching arena.
    3. Pisahkan CPU task pinning menggunakan `taskset` agar thread tidak berebut context yang sama.

#### Skenario 2: Drop Paket Siluman pada 100GbE Network Ingress
- **Kasus:** Server CDN menerima lonjakan traffic video streaming. Metrik `ifconfig` atau `ip -s link` menunjukkan angka `RX dropped` yang bertambah dengan cepat, namun CPU utilization rata-rata sistem masih sangat rendah (sekitar 15%). Aplikasi Web Server tidak mencatat log crash atau error memori.
- **Pertanyaan:** Di lapisan subsistem manakah paket tersebut di-drop sebelum mencapai aplikasi, dan bagaimana Anda mengonfigurasi kernel untuk mengatasinya?
- **Kunci Jawaban & Analisis:**
  - *Diagnosa:* Paket di-drop di level kernel ring buffer atau antrean socket backlog sebelum sempat diproses oleh kernel TCP stack. Penyebab utamanya adalah NIC hardware buffer (`RX ring buffer`) atau kernel ingress processing queue (`netdev_max_backlog`) terlalu kecil untuk menampung burst packet traffic, sementara core CPU yang menangani IRQ interface tersebut jenuh sesaat.
  - *Mitigasi Arsitektur:*
    1. Naikkan kapasitas ring buffer hardware adapter via ethtool:  
       `ethtool -G <eth_name> rx 4096 tx 4096`
    2. Naikkan antrean ingress backlog kernel:  
       `sysctl -w net.core.netdev_max_backlog=100000`
    3. Naikkan batas kuota pemrosesan paket NAPI per softirq execution:  
       `sysctl -w net.core.netdev_budget=600`
    4. Aktifkan Receive Side Scaling (RSS) atau pastikan irq distribution disebar ke beberapa core lokal:  
       `systemctl start irqbalance` atau set manual `smp_affinity`.

#### Skenario 3: Stall I/O Berkala pada Database Write-Heavy
- **Kasus:** Database PostgreSQL yang menangani operasi penulisan data masif (bulk-insert ratusan ribu record) mengalami *freeze* total selama 2–4 detik setiap beberapa menit sekali. Selama periode freeze, metrik I/O Wait `%wa` melonjak drastis, lalu kembali ke nol secara mendadak.
- **Pertanyaan:** Fenomena kernel virtual memory apa yang melatarbelakangi freeze berkala ini, dan konfigurasi sysctl apa yang dapat merekayasa aliran I/O menjadi rata (*smooth*)?
- **Kunci Jawaban & Analisis:**
  - *Diagnosa:* Fenomena ini disebut **Dirty Page Flusher Stall**. Aplikasi menulis data ke dalam Page Cache sistem operasi jauh lebih cepat daripada kemampuan physical disk (SSD/NVMe) melakukan flush write. Ketika persentase dirty pages di memori melampaui batas ambang batas `vm.dirty_ratio`, kernel memaksa seluruh aplikasi yang sedang menulis untuk berhenti (*blocking direct write*) dan membantu proses flush ke disk secara sinkron.
  - *Mitigasi Arsitektur:*
    Ubah parameter dirty page throttling kernel agar proses sinkronisasi ke disk berlangsung lebih dini secara background tanpa memblokir thread database:
    ```bash
    # Turunkan rasio trigger background flusher agar proses flush berjalan kontinu sejak dini
    sysctl -w vm.dirty_background_ratio=3
    
    # Atau gunakan absolute bytes alih-alih ratio (sangat efektif untuk RAM server besar > 128GB)
    sysctl -w vm.dirty_background_bytes=268435456  # 256MB
    
    # Batasi batas absolut blocking direct flush agar tidak pernah mencapai titik freeze
    sysctl -w vm.dirty_ratio=10
    sysctl -w vm.dirty_bytes=1073741824            # 1GB
    ```

---

## 16. Summary

1. **Kernel Bukan Black-Box:** Dalam skala jutaan operasi per detik, sistem operasi Linux tidak boleh diperlakukan sebagai perantara abstrak yang transparan. Kinerja puncak bergantung langsung pada efisiensi jalur data hardware-to-software (CPU caches, bus interkoneksi NUMA, dan offload NIC).
2. **Evolusi I/O Modern:** Arsitektur lama berbasis sinkron/blocking system calls dan model `epoll` POSIX standar kini dilengkapi dengan teknologi performa tinggi seperti `io_uring` yang mengeliminasi context switch overhead melalui shared ring buffer memory.
3. **Observabilitas Berbiaya Nol:** Diagnosis deterministik pada level produksi modern tidak lagi mengandalkan logging invasif atau tooling debugger blocking. Penggunaan **eBPF dan Tracepoints** memungkinkan eksekusi telemetri mikrodetik secara aman dan minim interferensi pada kernel space runtime.
4. **Prinsip Tuning Deterministik:** Peningkatan keandalan sistem Linux produksi bukan tentang membesarkan seluruh parameter konfigurasi secara membabi buta, melainkan menyeimbangkan *trade-off* latensi vs *throughput*, mengeliminasi *contention lock*, serta memastikan data diproses pada domain silikon CPU/NUMA node yang tepat.