# Bab 02: Arsitektur Sistem Operasi Tingkat Rendah & Linux Internals

## 1. Learning Objective
Setelah menyelesaikan modul ini, Site Reliability Engineer (SRE) dan Systems Engineer diharapkan mampu:
- Mengurai alur eksekusi instruksi dari User Space ke Kernel Space melalui *System Call interface* (`sysenter`/`syscall`) dan mekanisme *context switching*.
- Menganalisis operasi internal *System Calls* krusial pada workload modern berperforma tinggi: `epoll` (I/O multiplexing event-driven), `clone` (primitif thread/container namespacing), dan `futex` (sinkronisasi user-space fast-path).
- Menjelaskan arsitektur *Virtual File System* (VFS), interaksi *Page Cache*, siklus flush *Dirty Pages*, serta dampaknya terhadap latensi I/O disk (I/O stall).
- Mendiagnosis manajemen memori tingkat rendah: translasi *Virtual Memory*, struktur *Page Table Walk*, algoritma *Page Reclaim*, *Swapping behavior*, dan determinisme eksekusi *Out-Of-Memory* (OOM) Killer.
- Mengonfigurasi dan mengisolasi resource komputasi menggunakan antarmuka terpadu **cgroups v2** (`cpu`, `memory`, `io`).
- Memahami fondasi kerja **extended Berkeley Packet Filter (eBPF)** (bytecode execution, in-kernel verifier, BPF maps) untuk observabilitas performa kernel tanpa recompile/kernel module injection.

---

## 2. Prerequisite
Untuk menyerap materi ini secara optimal, pembaca wajib memiliki pemahaman dasar mengenai:
- Arsitektur komputer dasar: Register CPU, Cache CPU (L1/L2/L3), TLB (*Translation Lookaside Buffer*), Interupsi hardware vs software.
- Dasar sistem operasi Linux: Perintah shell CLI, struktur direktori `/proc` dan `/sys`, konsep PID, thread, file descriptor (FD).
- Dasar pemrograman C atau Go: Pointer, alokasi memori heap/stack, dan representasi biner.

---

## 3. Concept
Sistem operasi Linux modern bertindak sebagai mediator terabstraksi dengan performa tinggi antara aplikasi user-space dan perangkat keras fisik. Kernel Linux beroperasi dalam mode privilese CPU tertinggi (Ring 0 / Supervisor Mode pada x86_64, EL1 pada ARM64), sementara aplikasi pengguna berjalan pada Ring 3 / User Mode (EL0).

```
+-------------------------------------------------------------------+
|                     User Space (Ring 3 / EL0)                    |
|  [ Nginx / Go App / JVM ]   [ C Standard Library (glibc / musl) ]  |
+---------------------------------+---------------------------------+
                                  | System Call (syscall instruction)
+---------------------------------v---------------------------------+
|                    Kernel Space (Ring 0 / EL1)                    |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |                   System Call Dispatcher                  |   |
|   +---------+--------------------+--------------------+-------+   |
|             |                    |                    |           |
|   +---------v-------+    +-------v-------+    +-------v-------+   |
|   | Process Mgmt    |    | Memory Mgmt   |    | VFS & Storage |   |
|   | - CFS Scheduler |    | - Page Tables |    | - Page Cache  |   |
|   | - clone / futex |    | - Reclamation |    | - Block Layer |   |
|   | - cgroups v2    |    | - OOM Killer  |    | - Drivers     |   |
|   +-----------------+    +---------------+    +---------------+   |
|             |                    |                    |           |
|   +---------v--------------------v--------------------v-------+   |
|   |                  eBPF Runtime Engine & Tracing            |   |
|   +-----------------------------------------------------------+   |
+---------------------------------+---------------------------------+
                                  | Hardware Control
+---------------------------------v---------------------------------+
|          Hardware (CPU Cores, MMU, RAM, NVMe/SSD, NIC)            |
+-------------------------------------------------------------------+
```

Pemisahan ini menjamin isolasi memori dan proteksi perangkat keras: kode aplikasi pengguna tidak diizinkan mengeksekusi instruksi privileged secara langsung. Setiap interaksi eksternal—mulai dari membaca socket jaringan, mengalokasikan physical frame memori, hingga menulis data ke disk—wajib dieksekusi melalui **System Calls (Syscalls)**.

---

## 4. Why
Mengapa seorang SRE level lanjut harus mendalami Linux Internals hingga ke struktur kernel?
1. **Misteri "Unexplained Latency Spikes"**: Metrik tingkat tinggi (seperti CPU Usage 40%) sering menyembunyikan masalah sebenarnya, misalnya *uninterruptible sleep state* (D-state) akibat I/O lock, perebutan *futex lock*, atau page cache writeback stall.
2. **Kerapuhan Abstraksi Container**: Container bukan virtual machine; container hanyalah proses biasa yang dibatasi oleh kernel namespace dan cgroups. Kegagalan memori container Kubernetes sering kali dipicu oleh ketidaktahuan tentang relasi Page Cache vs Anonymous Memory pada batas cgroup v2.
3. **Observabilitas Berbiaya Rendah**: Menjalankan profiler tradisional seperti `strace` pada sistem produksi dengan ribuan request per detik menghentikan eksekusi proses via `ptrace`, menyebabkan degradasi latensi ratusan persen. Memahami arsitektur kernel dan eBPF memungkinkan instrumentasi sistem secara *zero-overhead* langsung di kernel space.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Arsitektur Kernel & System Call Execution Flow
Ketika aplikasi memanggil fungsi I/O seperti `read()`:
1. **Transisi Hak Akses**: CPU memuat nomor syscall ke register register `%rax`, argumen ke `%rdi`, `%rsi`, `%rdx`, `%r10`, `%r8`, `%r9`, lalu mengeksekusi instruksi assembly `syscall`.
2. **Trap Handler**: CPU berpindah dari Ring 3 ke Ring 0. CPU menyimpan register stack pointer pengguna (`%rsp`) dan register status (`%rflags`) ke dalam struktur data internal *kernel stack* milik thread tersebut (`struct pt_regs`).
3. **Syscall Table Lookup**: Kernel membaca tabel `sys_call_table` pada index yang diberikan oleh `%rax` dan menjalankan fungsi kernel terkait (misal: `ksys_read()`).
4. **Return ke User Space**: Hasil kembalian diletakkan di `%rax`. Kernel memulihkan register pengguna dan mengeksekusi `sysretq`, mengembalikan CPU ke Ring 3.

```
User Program                     Kernel (Ring 0)
  read(fd, buf, len)
      |
      v
  [glibc wrapper]
  mov $0, %rax (sys_read)
  syscall  -------------------> Trap: Switch Ring 3 -> Ring 0
                                Save %rsp, %rip to struct pt_regs
                                sys_call_table[%rax]() -> ksys_read()
                                Execute VFS read logic
                                Put return code into %rax
  Syscall returns <------------ sysretq: Switch Ring 0 -> Ring 3
  Process resumed
```

### 5.2 System Calls Esensial
#### `epoll` (Event Multiplexing Skala Besar)
Berbeda dengan `select()` dan `poll()` yang memiliki kompleksitas waktu $\mathcal{O}(N)$ karena menyalin array file descriptor bolak-balik antara user dan kernel space pada setiap iterasi:
- **`epoll_create1(int flags)`**: Mengalokasikan struct `eventpoll` di kernel space yang menggunakan struktur data **Red-Black Tree (RB-Tree)** untuk menyimpan FD yang dimonitor dan sebuah **Doubly Linked List** untuk menyimpan FD yang berstatus *ready*.
- **`epoll_ctl(int epfd, int op, int fd, struct epoll_event *event)`**: Menambahkan, mengubah, atau menghapus FD dari RB-Tree dengan kompleksitas $\mathcal{O}(\log N)$. Di sini, kernel mendaftarkan callback ke antrian *wait queue* internal socket.
- **`epoll_wait(int epfd, struct epoll_event *events, int maxevents, int timeout)`**: Thread tidur secara efisien hingga callback driver (misal: paket jaringan masuk pada NIC) memindahkan node dari RB-tree ke *Ready List*. Kernel hanya menyalin FD yang aktif ke buffer user space dengan kompleksitas $\mathcal{O}(K)$, di mana $K$ adalah jumlah event aktif.

#### `clone` (Fondasi Threading & Kontainerisasi)
Syscall `clone(int (*fn)(void *), void *stack, int flags, void *arg, ...)` adalah superset dari `fork()`. Flag yang dilewatkan menentukan derajat isolasi:
- **`CLONE_VM`**: Berbagi ruang alamat memori yang sama (primitif POSIX Threads / pthread).
- **`CLONE_FS`, `CLONE_FILES`**: Berbagi informasi filesystem dan tabel file descriptor.
- **Namespace Flags**: `CLONE_NEWPID`, `CLONE_NEWNET`, `CLONE_NEWNS`, `CLONE_NEWIPC`, `CLONE_NEWUTS`, `CLONE_NEWUSER`. Jika flag ini disetel, kernel membuat struktur namespace baru untuk proses anak. Inilah fondasi primitif isolasi container di Linux (seperti Docker/containerd).

#### `futex` (Fast Userspace Mutex)
Operasi penguncian tradisional mengharuskan syscall masuk ke kernel space bahkan saat tidak ada perebutan kunci (*uncontended*). `futex()` membagi fase penguncian:
1. **Fast-path (User-space)**: Thread mencoba mengakuisisi lock via instruksi atomik CPU (seperti `CMPXCHG`). Jika berhasil (tidak ada kontensi), operasi selesai tanpa berpindah ke kernel space sama sekali (nol context switch overhead).
2. **Slow-path (Kernel-space)**: Jika terjadi kontensi (kunci sudah dipegang thread lain), thread memanggil `syscall(SYS_futex, uaddr, FUTEX_WAIT, val, ...)`. Kernel menidurkan thread tersebut ke dalam *hash bucket wait queue* kernel hingga thread pemilik melepaskan kunci dan memanggil `FUTEX_WAKE`.

### 5.3 Virtual File System (VFS), Page Cache, & Dirty Pages
VFS menyediakan antarmuka polimorfik universal berorientasi objek untuk berbagai filesystem (ext4, XFS, NFS, procfs).
- **Struktur VFS**:
  - `struct inode`: Menyimpan metadata file (ukuran file, izin akses, pointer ke blok fisik data).
  - `struct dentry` (Directory Entry): Memetakan path string direktori ke inode terkait; di-cache di RAM dalam struktur *dcache* untuk mempercepat *path resolution*.
  - `struct file`: Mewakili file yang sedang dibuka oleh suatu proses (menyimpan offset pointer baca/tulis saat ini).
  - `struct address_space`: Struktur krusial yang mengaitkan penyimpanan blok file ke halaman memori fisik (**Page Cache**).

```
VFS Hierarchy:
Path: "/var/log/syslog"
  dentry ("/") ----> dentry ("var") ----> dentry ("log") ----> dentry ("syslog")
                                                                      |
                                                                      v
                                                                 struct inode
                                                                      |
                                                                      v
                                                             struct address_space
                                                                      |
                                                          +-----------+-----------+
                                                          | Page Cache (Radix/XArray)
                                                          v                       v
                                                    [Page Frame 1]          [Page Frame 2]
```

- **Page Cache & Dirty Pages Workflow**:
  1. Operasi `write()` dari user-space secara default menyalin data dari buffer aplikasi ke Page Cache kernel (RAM).
  2. Data tersebut ditandai sebagai **Dirty Page** (`PG_dirty`). Syscall `write()` langsung mengembalikan status sukses ke aplikasi tanpa menunggu data ditulis ke disk fisik (asinkron).
  3. Kernel thread khusus (`kswapd` dan `kworker/flush`) melakukan periodik writeback ke disk fisik.
  4. **Pencegatan I/O (Throttling)**: Jika volume dirty pages melampaui ambang batas `vm.dirty_ratio` (misal 20% dari total memori) atau `vm.dirty_bytes`, proses yang memanggil `write()` akan dipaksa beralih fungsi menjadi flusher sinkron. Proses ini akan diblokir ke status *Uninterruptible Sleep* (`D-state`) sampai dirty pages turun di bawah ambang batas aman.

### 5.4 Manajemen Memori: Virtual Memory, Swapping, & OOM Killer
Kernel Linux memetakan ruang alamat virtual aplikasi ke dalam frame memori fisik menggunakan **Multi-Level Page Tables** (4-level atau 5-level paging pada arsitektur x86_64: PGD $\rightarrow$ P4D $\rightarrow$ PUD $\rightarrow$ PMD $\rightarrow$ PTE).

```
Virtual Address (64-bit canonical):
+--------+--------+--------+--------+--------+--------------+
| Unused | PGD    | P4D    | PUD    | PMD    | PTE   | Offset |
| 16 bit | 9 bit  | 9 bit  | 9 bit  | 9 bit  | 9 bit | 12 bit |
+--------+--------+--------+--------+--------+-------+--------+
            |        |        |        |        |        |
            v        v        v        v        v        +--> [ Physical Byte ]
           CR3 -> Page Tables Walk via Hardware MMU            Page Frame (4KB)
```

- **Alokasi Memori Optimistik (Demand Paging & Overcommit)**:
  Fungsi `malloc()` memanggil `brk()` atau `mmap()`. Kernel **tidak** langsung mengalokasikan RAM fisik, melainkan hanya memesan rentang alamat virtual (`struct vm_area_struct`). Ketika CPU pertama kali mencoba mengakses alamat memori tersebut, MMU memicu **Page Fault Exception** (Hardware Trap). Kernel menanganinya via `handle_mm_fault()`:
  - Mengambil frame fisik kosong dari *Buddy Allocator*.
  - Menuliskan pemetaan ke PTE (*Page Table Entry*).
  - Mengulang eksekusi instruksi CPU secara transparan.

- **Kategori Halaman Memori**:
  - **File-backed pages**: Halaman memori yang memiliki representasi di disk (Page Cache). Dapat direclaim tanpa swap space dengan cara menimpa atau mem-flush-nya ke disk.
  - **Anonymous pages**: Memori heap, stack, dan shared memory non-file dari aplikasi. Tidak memiliki file cadangan di disk. Memori ini **hanya** bisa direclaim dengan cara di-swap out ke swap device/file.

- **Algoritma Swapping & `vm.swappiness`**:
  Kernel menghitung rasio penyeimbangan antara reclaiming File-backed vs Anonymous memory:
  $$\text{Ratio} = \frac{\text{scan(anon)}}{\text{scan(file)}} \propto \frac{\text{vm.swappiness} \times \text{anon\_cost}}{(200 - \text{vm.swappiness}) \times \text{file\_cost}}$$
  Jika `vm.swappiness=0`, kernel mematikan swapping anonymous page secara proaktif, dan hanya mengizinkan swap jika terjadi kondisi OOM mutlak.

- **Out-Of-Memory (OOM) Killer Determinism**:
  Ketika seluruh physical frame habis dan mekanisme reclaim gagal membebaskan halaman memori yang cukup:
  1. Fungsi `out_of_memory()` dieksekusi di kernel.
  2. Kernel menghitung skor kerentanan setiap proses melalui formula:
     $$\text{oom\_score} = \left( \frac{\text{total\_pages\_used}}{\text{total\_system\_pages}} \times 1000 \right) + \text{oom\_score\_adj}$$
  3. Nilai `oom_score_adj` berkisar dari $-1000$ (kebal OOM kill, contoh: SSHD/systemd) hingga $+1000$ (kandidat utama eliminasi).
  4. Kernel mengirimkan sinyal `SIGKILL` (signal 9) ke proses dengan skor tertinggi untuk mencegah kepanikan kernel (*Kernel Panic*).

### 5.5 Isolasi Resource: cgroups v2 (Unified Control Group Hierarchy)
Pada Linux terdahulu (cgroups v1), setiap controller (CPU, Memory, BlkIO) memiliki pohon direktori terpisah yang tidak tersinkronisasi. Hal ini memicu *cross-controller deadlock* (misal: proses yang dibatasi memori tidak bisa mengontrol throttling I/O writeback-nya).

cgroups v2 memadukan seluruh isolasi resource ke dalam satu pohon tunggal:
- Struktur hirarki berbasis path `/sys/fs/cgroup/`.
- File konfigurasi antarmuka deklaratif:
  - `cgroup.controllers`: Daftar controller yang tersedia (`cpu memory io pids`).
  - `cgroup.subtree_control`: Controller yang diaktifkan untuk child cgroup.
  - `memory.max`: Hard limit alokasi memori (melewati nilai ini memicu OOM Killer spesifik pada cgroup tersebut).
  - `memory.high`: Throttle limit (melewati nilai ini memperlambat proses secara bertahap dan memicu *aggressive background reclaim* tanpa langsung membunuh proses).
  - `memory.oom.group`: Jika disetel ke `1`, seluruh proses dalam cgroup akan di-kill secara serentak bila OOM terjadi, menjaga integritas multi-process container.
  - `cpu.max`: Kuota CPU periodik dalam format `$QUOTA $PERIOD` (misal: `200000 100000` setara dengan 2 CPU cores).

### 5.6 Pengantar eBPF (extended Berkeley Packet Filter)
eBPF mengubah kernel Linux menjadi sistem operasi yang dapat diprogram secara dinamis (*programmable kernel*):
1. **Safety First (In-Kernel Verifier)**: Program eBPF yang ditulis dalam C dibatasi dan diperiksa sebelum dijalankan: tidak boleh ada loop tak terhingga yang tidak terikat, tidak ada akses memori di luar batas *sandbox*, dan kompleksitas instruksi maksimal diverifikasi secara formal.
2. **JIT Compilation**: Bytecode eBPF dikompilasi secara real-time ke instruksi mesin native CPU (x86/ARM) untuk meminimalkan degradasi performa ke level sub-mikrodetik.
3. **BPF Hooks**: eBPF dapat ditempelkan (*attached*) ke berbagai event kernel:
   - **Kprobes / Kretprobes**: Menangkap entry dan return dari fungsi kernel internal mana pun.
   - **Tracepoints**: Titik instrumentasi statis yang stabil di dalam kode sumber kernel.
   - **Uprobes**: Tracing fungsi tingkat user-space (misal: panggilan SSL write pada OpenSSL/Go runtime).
   - **Perf Events / Raw Tracepoints**: Instrumentasi berkecepatan tinggi untuk profiling CPU hardware & page faults.
4. **BPF Maps**: Struktur data kernel berkecepatan tinggi (Hash Map, Array, Ring Buffer) yang digunakan untuk menyimpan metrik agregasi dan bertukar data antara kernel space dan user space secara efisien.

---

## 6. How
Implementasi inspeksi dan manipulasi low-level Linux internals dilakukan melalui utility bawaan kernel, file system `/proc`, `/sys`, dan interface CLI terstandar:

1. **Inspeksi Virtual Memory & Page Tables**:
   Periksa pemetaan memori proses spesifik melalui `/proc/$PID/smaps` atau tool `pmap -XX $PID`.
2. **Observasi VFS & Page Cache**:
   Gunakan `/proc/meminfo` untuk memonitor `Active(file)`, `Inactive(file)`, `Dirty`, dan `Writeback`.
3. **Membatasi Resource dengan cgroups v2**:
   Buat folder baru di bawah `/sys/fs/cgroup/`, lalu atur limitasi melalui instruksi `echo`.
4. **Instrumentasi Kernel Zero-Overhead dengan eBPF**:
   Gunakan BCC (*BPF Compiler Collection*) atau `bpftrace` untuk menulis program pelacak syscall dan page fault secara ad-hoc tanpa mematikan proses target.

---

## 7. Analogy
Bayangkan Linux Kernel sebagai **Otoritas Pelabuhan Logistik Internasional**:
- **System Call** adalah loket imigrasi dan bea cukai resmi. Truk kargo (aplikasi user-space) dilarang menerobos dermaga secara mandiri. Sopir harus menyerahkan manifest dokumen (register CPU) ke petugas loket untuk diverifikasi.
- **Page Cache & Dirty Pages** adalah terminal kontainer transit sementara di pelabuhan. Kargo dari kapal diturunkan cepat ke dermaga transit (RAM), dan kapal langsung diizinkan berlayar pergi (`write()` return). Petugas lapangan (kswapd/kworker) perlahan-lahan memindahkan kontainer dari dermaga transit ke gudang semen permanen (Disk/SSD). Jika dermaga transit sudah kepenuhan kontainer belum terangkut (*dirty pages* menumpuk), gerbang pelabuhan akan ditutup total; truk pengantar dipaksa berhenti di depan pintu masuk (*uninterruptible sleep D-state*).
- **Virtual Memory & Page Faults** adalah sistem pemesanan tiket penerbangan *overbooked*. Maskapai (Kernel) menjanjikan kursi penerbangan ke 150 penumpang pada pesawat berkapasitas 100 kursi fisik. Selama penumpang hanya memegang reservasi di aplikasi (*virtual address space*), semua aman. Ketika penumpang tiba-tiba benar-benar melangkah masuk ke pintu pesawat (*dereferensi pointer / page fault*), kru kabin baru kelabakan mencarikan kursi fisik nyata di dalam pesawat.
- **cgroups v2** adalah sekat partisi kompartemen kedap air pada kapal kargo: jika satu ruangan mengalami kebocoran air (kebocoran memori/OOM), pintu hidrolik menutup dan menenggelamkan ruangan tersebut saja, tanpa menenggelamkan seluruh kapal.
- **eBPF** adalah kamera CCTV pintar dan drone mikro tanpa awak yang dapat disuntikkan secara aman ke lorong mana pun di pelabuhan untuk mencatat setiap pergerakan kontainer secara real-time tanpa memperlambat operasional truk barang sedikit pun.

---

## 8. Diagram (ASCII)

### Siklus Hidup Alokasi Memori, Page Fault, dan OOM Killer
```
Aplikasi User Space               Kernel Subsystem                    Hardware MMU
       |                                 |                                 |
1. malloc(100MB)                         |                                 |
   brk() / mmap() ---------------------> |                                 |
                                  Buat vm_area_struct                      |
                                  (Alokasi Virtual VMA)                    |
   Alamat virtual kembali <--------------+                                 |
       |                                                                   |
2. *ptr = 'A' (Akses Memori Pertama Kali)                                  |
       +-----------------------------------------------------------------> | Cek TLB/PTE
                                                                           | -> Entry PTE MISSING!
                                         | <-------------------------------+ Memicu Hardware Exception:
                                         |                                   Page Fault (#PF)
                                 handle_mm_fault()                         |
                                         |                                 |
                         +---------------+---------------+                 |
                         | Cari Physical Frame Kosong    |                 |
                         | (Buddy Allocator)             |                 |
                         +---------------+---------------+                 |
                                         |                                 |
                      [Ada Frame Kosong]   [Frame Penuh / Low Memory]      |
                               |                       |                   |
                               |               Reclaim Page Cache          |
                               |               & Swap Out Anon Pages       |
                               |                       |                   |
                               |         [Memori Tetap Tidak Cukup]        |
                               |                       |                   |
                               |               Trigger OOM Killer          |
                               |               Hitung oom_score            |
                               |               Kirim SIGKILL ke target     |
                               |                                           |
                               v                                           |
                       Update Page Table Entry (PTE) --------------------> | Update Hardware Page Table
                               |                                           |
3. Kernel melanjutkan instruksi pengguna <---------------------------------+ Instruksi CPU selesai
```

---

## 9. Simple Example
Menghitung alokasi Virtual Memory vs Residen (Physical) Memory menggunakan bahasa C sederhana untuk membuktikan konsep Demand Paging:

```c
// demand_paging.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main() {
    size_t size = 256 * 1024 * 1024; // 256 MB
    printf("PID: %d\n", getpid());
    printf("1. Mengalokasikan 256 MB virtual memory via malloc()...\n");
    char *buffer = (char *)malloc(size);

    printf("   Alokasi selesai. Periksa VIRT vs RES di top/ps. Tekan Enter...");
    getchar();

    printf("2. Menulis data ke 128 MB pertama (memicu Page Faults)...\n");
    for (size_t i = 0; i < size / 2; i += 4096) {
        buffer[i] = 'X'; // Menulis 1 byte per page 4KB
    }

    printf("   Penulisan 128 MB selesai. Periksa kembali VIRT vs RES. Tekan Enter...");
    getchar();

    free(buffer);
    return 0;
}
```
**Observasi:**
Pada langkah 1, `top` akan menunjukkan `VIRT=256M`, namun `RES=0M`. Pada langkah 2, `VIRT=256M`, dan `RES` melonjak persis ke `~128M`. Ini membuktikan kernel menunda alokasi memori fisik hingga terjadi instruksi dereferensi langsung.

---

## 10. Practical Example (Konfigurasi CLI & Production Scripting)

### Penerapan Isolasi cgroups v2 secara Manual di Linux
Berikut langkah konfigurasi batas resource hierarkis pada server berbasis systemd/cgroups v2 native:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Pastikan sistem menggunakan unified cgroup hierarchy (cgroups v2)
if [ ! -f /sys/fs/cgroup/cgroup.controllers ]; then
    echo "ERROR: Sistem belum mengaktifkan cgroups v2!"
    exit 1
fi

CGROUP_PATH="/sys/fs/cgroup/production_worker"

# 2. Buat sub-cgroup
echo "Membuat cgroup di $CGROUP_PATH"
sudo mkdir -p "$CGROUP_PATH"

# 3. Aktifkan memory controller pada subtree
echo "+memory +io +cpu" | sudo tee /sys/fs/cgroup/cgroup.subtree_control > /dev/null

# 4. Terapkan Limitasi Memori Ketat & Throttling
# - memory.max: Batas mutlak (melewati ini memicu OOM Killer cgroup)
# - memory.high: Batas peringatan kernel (memicu throttling & background reclaim)
echo "$((512 * 1024 * 1024))" | sudo tee "$CGROUP_PATH/memory.max" > /dev/null   # 512 MB
echo "$((400 * 1024 * 1024))" | sudo tee "$CGROUP_PATH/memory.high" > /dev/null  # 400 MB

# 5. Pasang kuota CPU: 1.5 core (150000 microsecond per 100000 microsecond cycle)
echo "150000 100000" | sudo tee "$CGROUP_PATH/cpu.max" > /dev/null

# 6. Jalankan proses di dalam isolasi cgroup tersebut
echo "Menjalankan worker bash di dalam cgroup..."
echo $$ | sudo tee "$CGROUP_PATH/cgroup.procs"

# 7. Verifikasi penempatan proses
cat "$CGROUP_PATH/cgroup.procs"
grep -E '(oom|fail)' "$CGROUP_PATH/memory.events"
```

---

## 11. Real World Example
### Kasus Industri: Tragedi I/O Freeze 30 Detik pada Database Kafka Akibat "Dirty Pages Flush Spike"
- **Insiden**: Kluster Apache Kafka dengan throughput penulisan 500 MB/s mengalami lonjakan latensi produksi (*producer latency spike*) dari 2ms melonjak drastis hingga 35.000ms secara berkala setiap 5 menit. Producer client menerima `TimeoutException`.
- **Investigasi Masalah**:
  1. Perintah `vmstat 1` menunjukkan metrik `wa` (iowait) melonjak hingga 80% dan proses Kafka masuk ke state `D` (*Uninterruptible Sleep*).
  2. Saat diperiksa via `cat /proc/vmstat | grep nr_dirty`, dirty pages menumpuk hingga 40 GB pada RAM sistem (total RAM node: 128 GB).
  3. Konfigurasi bawaan OS Linux server:
     `vm.dirty_ratio = 20` (20% dari 128 GB = ~25.6 GB)
     `vm.dirty_background_ratio = 10` (10% dari 128 GB = ~12.8 GB)
  4. Penyebab: Ketika Kafka menulis batch log raksasa secara konstan ke Page Cache, background flusher (`kworker`) tertinggal dari laju ingress. Saat dirty pages menyentuh limit 25.6 GB (`vm.dirty_ratio`), Linux kernel secara agresif **memblokir seluruh syscall `write()`** proses Kafka. Kernel memaksa thread Kafka berhenti menulis dan harus ikut serta mem-flush data kotor ke NVMe array hingga antrian berkurang. Selama waktu flush masif tersebut, I/O disk saturated dan proses freeze selama puluhan detik.
- **Solusi Rekayasa SRE**:
  Ubah konfigurasi rasio berbasis persentase menjadi berbasis ukuran byte statis absolut yang kecil di `/etc/sysctl.d/99-kafka-pagecache.conf`:
  ```ini
  # Mulai background flusher sangat dini (saat dirty data menyentuh 256MB)
  vm.dirty_background_bytes = 268435456

  # Jangan biarkan dirty data melampaui 1GB sebelum memblokir aplikasi
  vm.dirty_bytes = 1073741824

  # Kurangi interval pengecekan flusher kernel ke 100 milidetik (100 centisecs)
  vm.dirty_writeback_centisecs = 100
  vm.dirty_expire_centisecs = 500
  ```
  **Hasil**: Penulisan I/O ke storage disk terdistribusi halus secara konstan (*smooth streaming*), latensi spike 30 detik tereliminasi sepenuhnya, stabil di $< 5\text{ms}$.

---

## 12. Trade-offs

| Pendekatan / Parameter | Keuntungan | Kerugian / Risiko | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **`vm.swappiness = 0`** | Menghindari latensi disk akibat swapping anonymous memory secara mendadak. | Risiko OOM Killer langsung aktif mematikan aplikasi jika Page Cache tidak dapat direclaim lagi. | Workload latensi sangat sensitif (misal: Redis in-memory cache). |
| **`vm.swappiness = 60` (Default)** | Memaksimalkan efisiensi pemanfaatan RAM dengan memindahkan memori pasif ke swap demi memperbesar Page Cache. | Terjadi disk I/O churn dan lonjakan latensi (*latency jitter*) bila memori pasif tiba-tiba diakses kembali. | General-purpose computing, non-latency critical microservices. |
| **I/O Multiplexing via `epoll`** | Mampu menangani $100.000+$ koneksi simultan (C10K/C1000K problem) dengan alokasi thread yang minimal. | Kompleksitas arsitektur asynchronous / event-driven tinggi; rentan starvation jika callback memblokir event loop. | Reverse Proxy (Nginx/HAProxy), Event-driven web servers, API Gateway. |
| **eBPF Tracing vs `strace`** | Overhead performa mendekati nol ($< 1\%$), aman dijalankan langsung pada sistem *high-traffic production*. | Membutuhkan kernel Linux modern ($\ge 5.4$), pemahaman C/assembly kernel, hak akses privilese root/CAP_BPF. | Tracing performa sistem riil, observability real-time, runtime security enforcement (Falco/Tetragon). |

---

## 13. When To Use
Gunakan optimasi dan teknik analisis tingkat rendah ini saat:
- Merancang atau mengoperasikan sistem terdistribusi dengan throughput tinggi (Kafka, Cassandra, PostgreSQL, ScyllaDB).
- Mengonfigurasi node Kubernetes (*kubelet configuration*) untuk mengelola alokasi resource pods secara presisi (`systemReserved`, `kubeReserved`, `cgroupDriver=systemd`).
- Menginvestigasi insiden performa di mana CPU usage terlihat rendah tetapi waktu respons aplikasi melambat secara ekstrem (mengecek kontensi lock futex atau antrian D-state).
- Mengaudit keamanan atau mendeteksi *anomalous system calls* pada container runtime menggunakan tooling eBPF.

---

## 14. When NOT To Use
Jangan gunakan teknik atau intervensi langsung level kernel jika:
- Aplikasi Anda berjalan di atas PaaS / Serverless platform (AWS Lambda, Google Cloud Run) di mana kernel diabstraksikan sepenuhnya oleh cloud provider.
- Masalah performa berada jelas pada layer aplikasi tingkat tinggi (misal: algoritma query database $N+1$, kesalahan indeks SQL relasional, atau infinite loop logic aplikasi).
- Tim belum memiliki standar monitoring kestabilan kernel: mengubah parameter `sysctl` memori secara sporadis di produksi tanpa pengujian beban (*load test*) dapat memicu *Kernel Panic* seketika.

---

## 15. Common Mistakes
1. **Menonaktifkan Swap Total (`swapoff -a`) Tanpa Perhitungan**:
   Banyak engineer menonaktifkan swap dengan asumsi "swap membuat lambat". Kenyataannya, tanpa swap sama sekali, kernel kehilangan kemampuan membuang anonymous pages yang tidak pernah digunakan. Hal ini menyempitkan ruang Page Cache dan memperbesar kemungkinan proses terbunuh seketika oleh OOM Killer saat terjadi lonjakan memori sementara.
2. **Menggunakan `strace` pada Node Produksi Sibuk**:
   `strace` memanfaatkan mekanisme `ptrace` yang menghentikan eksekusi thread target (menyetop register execution) pada setiap syscall *entry* dan *exit*. Menjalankan `strace -p $PID` pada database produksi dengan 20.000 TPS dapat menurunkan throughput hingga 90% dan menyebabkan *cascading outage*.
3. **Mengabaikan Karakteristik Epoll Starvation**:
   Menggunakan *Edge-Triggered* (`EPOLLET`) epoll tanpa mengonsumsi seluruh data buffer socket hingga mendapatkan status `EAGAIN` atau `EWOULDBLOCK`, yang menyebabkan koneksi macet permanen karena kernel tidak akan mengirimkan notifikasi ulang.
4. **Salah Membaca Indikator Memori Linux**:
   Mengira sistem "kehabisan memori" karena perintah `free -m` menunjukkan kolom `free` hanya bernilai beberapa megabyte. Pada Linux, memori yang bebas adalah pemborosan; kernel selalu memanfaatkan sisa memori sebagai **Buff/Cache** (Page Cache). Indikator ketersediaan memori yang valid adalah kolom **available**.

---

## 16. Best Practices

### Production Rule of Thumb
- **Gunakan cgroups v2 Sepenuhnya**: Tinggalkan cgroups v1 hybrid mode. Pastikan flag kernel `systemd.unified_cgroup_hierarchy=1` aktif.
- **Tentukan Limit Memori Berjenjang**:
  Selalu atur `memory.high` di bawah `memory.max` (misal: `memory.high = 85%` dari `memory.max`). Ini memberi kesempatan kernel untuk memperlambat alokasi secara bertahap dan menjalankan reclaim agresif sebelum OOM Killer membunuh container secara mendadak.
- **Kalibrasi Page Cache Flush Parameters**:
  Pada sistem dengan RAM besar ($\ge 64\text{ GB}$), selalu gunakan konfigurasi berbasis byte (`vm.dirty_background_bytes`, `vm.dirty_bytes`), bukan persentase rasio default (`dirty_ratio`).

### Production Checklist
- [ ] Swappiness dikonfigurasi rasional (`vm.swappiness = 1` hingga `10` untuk server latensi sensitif; hindari nilai 0 mutlak jika swap file tersedia).
- [ ] Antarmuka cgroup driver container runtime (`dockerd` / `containerd`) sinkron dengan `systemd` (`"exec-opts": ["native.cgroupdriver=systemd"]`).
- [ ] Monitoring metrik kernel aktif: monitoring metrik `node_vmstat_pgfault`, `node_memory_Dirty_bytes`, dan counter cgroup `memory.events` (khususnya field `oom_kill` dan `high`).
- [ ] Tooling tracing berbasis eBPF (`bcc-tools`, `bpftrace`) telah terinstal di bastion/admin host node untuk kebutuhan debug insiden tanpa downtime.

---

## 17. Troubleshooting

| Gejala / Simtom | Kemungkinan Penyebab Utama | Langkah Investigasi Diagnostik | Solusi Remedi |
| :--- | :--- | :--- | :--- |
| Proses aplikasi mendadak hilang (hilang seketika dari `ps`) tanpa jejak di log aplikasi. | Dibunuh oleh **OOM Killer** akibat penggunaan RAM melampaui alokasi OS atau batas container. | Jalankan `dmesg -T \| grep -i -E '(oom-killer\|killed process)'` atau periksa `/var/log/messages`. | Tingkatkan limit `memory.max` cgroup atau atur `oom_score_adj` untuk memproteksi proses penting. |
| CPU usage tinggi pada metrik **`%sys`** (System Time), `%usr` rendah. | Aplikasi terlalu sering memicu context-switch via syscall pendek, thread thrashing, atau futex contention masif. | Jalankan `perf top` untuk melihat fungsi kernel teratas, atau tracing via `bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'`. | Optimalkan pooling koneksi, ganti I/O model ke batching / epoll, minimalkan lock contention di kode aplikasi. |
| Banyak proses berada dalam status **`D` (Uninterruptible Sleep)**. | I/O disk stall parah; proses terblokir di kernel space saat menunggu sinkronisasi dirty pages atau kegagalan storage hardware. | Jalankan `cat /proc/$PID/stack` untuk melihat fungsi kernel tempat proses tersangkut (misal: `sync_inodes_sb`, `wait_on_page_writeback`). | Periksa status kesehatan storage NVMe/SAN, turunkan nilai `vm.dirty_bytes`, kurangi I/O queue pressure. |
| Latensi request jaringan melonjak drastis, socket queue menumpuk. | Listen backlog socket penuh atau worker thread terkunci pada event loop syscall blocking. | Jalankan `ss -lnt` dan amati kolom `Send-Q` vs `Recv-Q`. Jalankan `tcptop` (eBPF). | Naikkan `net.core.somaxconn` pada kernel dan naikkan parameter backlog pada `listen()` socket aplikasi. |

---

## 18. Exercise
Selesaikan latihan investigasi mandiri berikut:

1. **Eksplorasi Kernel Stack**:
   Jalankan proses `sleep 300` di latar belakang (`sleep 300 &`). Dapatkan PID-nya, lalu lakukan inspeksi isi kernel call stack thread tersebut secara langsung dari `/proc`.
   *Pertanyaan*: Fungsi kernel internal apa yang sedang menahan eksekusi proses tersebut?

2. **Deteksi Page Fault Rate**:
   Tulis perintah satu baris (*one-liner*) menggunakan `sar -B 1 5` atau `vmstat 1 5` untuk memonitor laju *Minor Page Faults* (`fault/s` atau `flt/s`) dan *Major Page Faults* (`majflt/s`).
   *Pertanyaan*: Jelaskan secara teknis perbedaan mekanisme kernel antara Minor Page Fault dan Major Page Fault!

---

## 19. Challenge
**Skenario**: Anda diberikan sebuah node compute produksi berkapasitas RAM 8 GB yang menjalankan database microservice. Tiba-tiba container database tersebut di-kill setiap kali ada batch processing file sebesar 4 GB yang dieksekusi secara asinkron.

**Tugas Arsitektur**:
1. Rancang konfigurasi cgroups v2 terisolasi untuk proses batch tersebut di mana memori maksimal dibatasi hingga 2 GB, namun eksekusi batch tidak boleh dihentikan secara fatal (tidak boleh OOM-killed).
2. Terapkan strategi I/O write throttling agar background flush dari file log batch tersebut tidak mendegradasi throughput latensi baca database utama.
3. Buat implementasi rule konfigurasi deklaratif (bisa via systemd service drop-in configuration atau shell provisioning script).

---

## 20. Summary
- **Arsitektur Pemisahan Privilese**: Kernel Linux membatasi eksekusi hardware melalui isolasi Ring 3 (User) dan Ring 0 (Kernel). Interaksi keduanya dijembatani oleh *System Call* yang memicu transisi context register yang aman.
- **Syscall Generasi Modern**: Operasi konkurensi masif bertumpu pada efisiensi kernel data structures: `epoll` menggunakan RB-tree dan wait-list terhubung untuk I/O tak-terblokir; `clone` menyederhanakan konstruksi thread dan namespaces; `futex` mengeksekusi sinkronisasi lock pada user space tanpa overhead syscall selama tidak terjadi perebutan.
- **VFS dan Page Cache Buffer**: File read/write dioperasikan melewati layer caching kernel. Penulisan terjadi ke memori terlebih dahulu (Dirty Pages). Menjaga konfigurasi dirty memory flusher adalah kunci menghindari problem I/O stall pada storage berperforma tinggi.
- **Hierarki Virtual Memory**: Melalui *demand paging*, kernel hanya meregangkan pemetaan virtual saat malloc dipanggil, dan menunda komitmen RAM fisik hingga hardware MMU membangkitkan *Page Fault Exception*.
- **Kontrol Isolasi Mutakhir**: **cgroups v2** menyediakan kontrol tunggal terpadu yang memecahkan masalah integrasi antar-controller pada cgroups v1, mengamankan node dari insiden kegagalan resource.
- **Era Observabilitas eBPF**: Melalui eBPF, SRE modern tidak lagi bergantung pada teknik invasif; kode pengawasan internal dapat diverifikasi dan dieksekusi langsung di dalam kernel space dengan tingkat presisi tinggi dan overhead performa yang sangat minimal.

---