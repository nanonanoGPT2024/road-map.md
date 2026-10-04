# Bab 10: Arsitektur Kernel, System Calls, dan Interface Virtual File System (`/proc` & `/sys`)

---

### 1. Learning Objective
Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- Membedakan batas eksekusi antara *User Space* (Ring 3) dan *Kernel Space* (Ring 0) pada arsitektur x86_64 secara deterministik.
- Menganalisis, menelusuri, dan mengukur latensi transisi eksekusi instruksi dari pustaka C standard (`glibc`) ke kernel menggunakan *System Calls* (`syscall`) via utility *tracing* seperti `strace` dan kernel probe.
- Memanipulasi parameter runtime kernel Linux secara dinamis melalui interface *Virtual File System* (`/proc` dan `/sys`) tanpa *reboot*.
- Mengidentifikasi sumber *bottleneck* performa sistem (I/O, memory, thread exhaustion) langsung dari telemetri file virtual di tingkat sistem operasi produksi.

---

### 2. Prerequisite
Sebelum mempelajari bab ini, Anda harus memahami:
- Hirarki direktori dasar Linux (FHS - Filesystem Hierarchy Standard).
- Konsep dasar proses (*Process ID*, *Threads*, alokasi memori heap/stack).
- Penggunaan dasar command line (`bash`, redirection, pipes, teks manipulation via `awk`/`grep`).
- Dasar pemrograman C atau pemahaman tentang eksekusi biner POSIX.

---

### 3. Concept
Arsitektur sistem operasi Linux membagi ruang alamat memori virtual menjadi dua domain utama untuk menjaga stabilitas dan integritas hardware:

1. **User Space (Ring 3):** Lingkungan tempat aplikasi pengguna, daemon, dan runtime bahasa pemrograman berjalan. Proses di Ring 3 tidak memiliki akses langsung ke hardware maupun instruksi istimewa (privileged instructions) CPU.
2. **Kernel Space (Ring 0):** Lingkungan terlindungi tempat inti sistem operasi (Linux Kernel) mengeksekusi thread, mengelola driver, mengakses I/O, serta mengatur alokasi memori fisik.

Aplikasi di User Space harus melalui jembatan resmi bernama **System Call (Syscall)** untuk meminta kernel mengeksekusi operasi privileged (seperti membuka file, mengalokasikan memori halaman baru, atau mengirim paket jaringan). 

Untuk memfasilitasi inspeksi dan konfigurasi runtime tanpa membebani komunikasi antar-proses secara kompleks, Linux menyediakan abstraksi berbasis file semu bernama **Virtual File System (VFS)**:
- **/proc (Process Information Pseudo-filesystem):** Representasi keadaan internal kernel dan proses running di memori. Data pada `/proc` tidak disimpan di blok disk fisik; kernel memproduksinya secara *on-the-fly* saat file dibaca.
- **/sys (Sysfs Virtual Filesystem):** Ekspor hierarkis terstruktur dari subsistem kernel, bus perangkat keras, driver, dan topologi hardware yang dikelola oleh `kobject`.

---

### 4. Why
Dalam lingkungan produksi berskala besar (high-throughput microservices, database engine, edge networking):
- **Diagnostik Black-Box:** Ketika sebuah proses *hang* tanpa menghasilkan error log, kemampuan membaca *stack trace* dan status I/O via `/proc/<PID>/` adalah satu-satunya metode non-destruktif untuk mendeteksi *deadlock*.
- **Tuning Tanpa Downtime:** Modifikasi parameter kernel (seperti ukuran TCP socket buffer, swapiness, dirty page ratio) wajib dilakukan secara dinamis melalui `/proc/sys/` atau `/sys/` pada infrastruktur 24/7.
- **Efisiensi Overhead Transisi:** Setiap panggilan *system call* memicu *context switch* mikro (perubahan privilege ring, penyimpanan register CPU, flushes TLB parsial). Mengidentifikasi jumlah syscall yang berlebihan (misalnya I/O yang tidak menggunakan buffer) adalah kunci mengeliminasi bottleneck komputasi.

---

### 5. What
Komponen inti yang menyusun arsitektur batas kernel dan ekosistem virtual file:

- **Syscall Dispatcher & Vector Table:** Tabel internal kernel (`sys_call_table`) yang memetakan nomor ID syscall (misalnya di x86_64: `0 = sys_read`, `1 = sys_write`, `60 = sys_exit`) ke fungsi implementasi kernel yang sesuai.
- **CPU Privilege Transition Register:** Instruksi arsitektur hardware (seperti `SYSCALL`/`SYSRET` pada x86_64) yang memfasilitasi loncatan alamat instruksi dari Ring 3 ke Ring 0 dengan mengubah flag MSR (*Model-Specific Register*).
- **Virtual File System (VFS) Layer:** Abstraksi kernel yang menyamakan seluruh operasi I/O menjadi representasi file standar (`open`, `read`, `write`, `close`), baik file tersebut berada di partisi NVMe (Ext4/XFS) maupun di dalam memori kernel (`procfs`/`sysfs`).
- **kobject & sysfs trees:** Kerangka kerja internal kernel yang merepresentasikan hierarki perangkat, modul kernel, dan atribut hardware menjadi struktur pohon direktori di `/sys`.

---

### 6. How
Alur transisi dari eksekusi aplikasi hingga manipulasi state kernel berjalan sebagai berikut:

```
[User Program: read()] 
       │ 
       ▼
[glibc Wrapper: syscall(SYS_read, fd, buf, count)]
       │
       ▼ (Muat ID syscall ke register RAX, argumen ke RDI, RSI, RDX)
[CPU Instruction: SYSCALL] 
       │ ── Transisi Ring 3 -> Ring 0 ──
       ▼
[Kernel Entry: entry_SYSCALL_64]
       │
       ├─► Simpan context register user-space ke Kernel Stack
       ├─► Validasi pointer memori user-space (mencegah arbitrary write)
       ├─► Akses sys_call_table[RAX] -> Eksekusi ksys_read()
       ├─► Muat nilai return ke register RAX
       └─► Pulihkan context register user-space
       │
       ▼ (CPU Instruction: SYSRET) ── Transisi Ring 0 -> Ring 3 ──
[User Program melanjutkan instruksi berikutnya dengan data dari kernel]
```

Ketika membaca konfigurasi via Virtual File System:
1. Shell memicu syscall `open()` terhadap `/proc/sys/vm/swappiness`.
2. VFS mengidentifikasi bahwa filesystem inode tersebut dimiliki oleh handler `procfs`.
3. Handler kernel mengekstrak nilai variabel internal kernel `vm_swappiness` langsung dari memory space kernel.
4. Data dikonversi menjadi format ASCII string dan dikirimkan kembali melalui return buffer `read()`.

---

### 7. Analogy
Bayangkan **User Space** adalah area nasabah di sebuah bank modern, dan **Kernel Space** adalah brankas utama serta infrastruktur jaringan bank di balik dinding baja lapis baja.

- **Nasabah (User Application):** Tidak diperkenankan masuk langsung ke brankas untuk mengambil uang tunai.
- **Loket Teller (System Call API):** Jalur formal satu-satunya. Nasabah mengisi slip penarikan (argumen syscall) dan menyerahkannya lewat kaca akrilik tebal ke Teller.
- **Satpam & Teller (Syscall Dispatcher & Kernel):** Memvalidasi identitas nasabah, memastikan saldo cukup (validasi pointer & privilege), lalu masuk ke area brankas (Ring 0) untuk mengambil uang.
- **Papan Informasi Suku Bunga Digital (Virtual File System /proc & /sys):** Layar kaca yang dapat dilihat oleh nasabah di lobi. Angka-angka tersebut diambil secara real-time langsung dari sistem database pusat perbankan tanpa nasabah perlu memasuki ruang server.

---

### 8. Diagram

```
+-------------------------------------------------------------------------+
|                              USER SPACE                                 |
|                                                                         |
|  +--------------------+                     +------------------------+  |
|  | User Application   |                     | Monitoring / Sysadmin  |  |
|  | (Nginx, Go, C, etc)|                     | (cat, sysctl, top)     |  |
|  +---------+----------+                     +-----------+------------+  |
|            |                                            |               |
|            | (Function call)                            | (Read/Write)  |
|            v                                            v               |
|  +--------------------+                     +------------------------+  |
|  | GNU C Library      |                     | POSIX Virtual FS APIs  |  |
|  | (glibc POSIX wrap) |                     | open(), read(), write()|  |
|  +---------+----------+                     +-----------+------------+  |
|            |                                            |               |
|            +-----------------------+--------------------+               |
|                                    | (SYSCALL Instruction: Ring 3 -> 0)  |
+------------------------------------|------------------------------------+
| TRAP / INTERRUPT GATEWAY           v                                    |
+-------------------------------------------------------------------------+
|                             KERNEL SPACE                                |
|                                                                         |
|                 +--------------------------------------+                |
|                 | System Call Handler (sys_call_table) |                |
|                 +------------------+-------------------+                |
|                                    |                                    |
|         +--------------------------+--------------------------+         |
|         |                          |                          |         |
|         v                          v                          v         |
|  +--------------+          +---------------+          +--------------+  |
|  | Core Subsys  |          | VFS Layer     |          | Device/Net   |  |
|  | (Sched, IPC, |          | (/proc, /sys) |          | Drivers      |  |
|  | Virtual Mem) |          +-------+-------+          +-------+------+  |
|  +-------+------+                  |                          |         |
|          |                         |                          |         |
+----------|-------------------------|--------------------------|---------+
|          v                         v                          v         |
|                             HARDWARE LAYER                              |
|                 [CPU, MMU, Physical RAM, Disks, NICs]                   |
+-------------------------------------------------------------------------+
```

---

### 9. Simple Example
Menjalankan inspeksi direct system call dan manipulasi file sistem virtual kernel.

#### Memeriksa ID Kernel dan Hostname via `/proc`
```bash
# Membaca informasi arsitektur kernel langsung dari memori
cat /proc/version

# Mengamati informasi pemetaan core CPU
grep -m 1 'model name' /proc/cpuinfo
```

#### Menelusuri System Call Sederhana menggunakan `strace`
```bash
# Menjalankan binary 'uptime' dan memfilter hanya syscall write()
strace -e trace=write uptime
```
*Output Representatif:*
```text
write(1, " 14:20:00 up 10 days,  2:15,  "..., 45) = 45
+++ exited with 0 +++
```

---

### 10. Practical Example

Program C produksi berikut mendemonstrasikan dua hal:
1. Memanggil kernel syscall secara eksplisit menggunakan interface `syscall()` bypass fungsi wrapper glibc standar.
2. Membuka dan mengekstrak metrik alokasi memori runtime internal dari direktori virtual `/proc/self/status`.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <fcntl.h>
#include <string.h>

void read_vfs_proc_metrics(void) {
    int fd = open("/proc/self/status", O_RDONLY);
    if (fd == -1) {
        perror("ERR: Gagal membuka /proc/self/status");
        return;
    }

    char buffer[2048];
    ssize_t bytes_read = read(fd, buffer, sizeof(buffer) - 1);
    if (bytes_read > 0) {
        buffer[bytes_read] = '\0';
        
        // Cari status memori VmRSS (Virtual Memory Resident Set Size)
        char *line = strtok(buffer, "\n");
        while (line != NULL) {
            if (strncmp(line, "VmRSS:", 6) == 0 || strncmp(line, "Threads:", 8) == 0) {
                printf("[VFS Metric] %s\n", line);
            }
            line = strtok(NULL, "\n");
        }
    }
    close(fd);
}

int main(void) {
    // 1. Eksekusi Syscall gettid (SYS_gettid = 186 pada x86_64) langsung via Kernel Dispatcher
    pid_t tid = (pid_t)syscall(SYS_gettid);
    
    // 2. Syscall write (SYS_write = 1 pada x86_64) langsung ke File Descriptor 1 (STDOUT)
    const char msg[] = "[Kernel Syscall] Direct write execution bypass printf buffer\n";
    syscall(SYS_write, 1, msg, sizeof(msg) - 1);

    printf("[Kernel Info] Thread ID aktif via syscall: %d\n", tid);

    // 3. Mengambil status proses dari procfs
    read_vfs_proc_metrics();

    return 0;
}
```

#### Kompilasi dan Eksekusi:
```bash
gcc -Wall -O2 inspect_kernel.c -o inspect_kernel
./inspect_kernel
```

---

### 11. Real World Example
**Kasus: Diagnostik Database Latency Spike di E-Commerce Global**

Pada platform e-commerce berskala 100,000 req/detik, node database PostgreSQL mendadak mengalami lonjakan latensi p99 dari 2ms ke 1200ms. Log aplikasi tidak mencatat error query; CPU dan Memory fisik masih tersisa 40%.

**Langkah Penyelidikan Kernel Engineers:**
1. **Analisis `/proc/sys/vm`:**
   Engineers memeriksa parameter `/proc/sys/vm/dirty_ratio` (default 20%) dan `/proc/sys/vm/dirty_background_ratio` (default 10%). Server memiliki 256GB RAM, yang berarti kernel mengizinkan akumulasi "dirty pages" hingga ~50GB sebelum memaksa I/O flush disk.
2. **Inspeksi `/proc/vmstat`:**
   Ditemukan metrik `nr_dirty` melompat tinggi, diikuti oleh proses postgres terblokir pada state `D` (Uninterruptible Sleep/Disk Sleep) yang terdeteksi via `/proc/<PID>/status` pada field `State: D (disk sleep)`.
3. **Penyebab:**
   Ketika batas 50GB tercapai, kernel membekukan operasi I/O write aplikasi user space guna mem-flush dirty pages secara masif ke disk NVMe array (terjadi I/O saturation).
4. **Solusi Runtime (Tanpa Reboot):**
   Parameter dituning langsung via interface Sysfs/Procfs:
   ```bash
   # Batasi dirty memory absolut menjadi 2GB (background) dan 4GB (hard throttle)
   echo 2147483648 > /proc/sys/vm/dirty_background_bytes
   echo 4294967296 > /proc/sys/vm/dirty_bytes
   ```
   Latensi p99 langsung stabil kembali ke 2.4ms karena flush disk terjadi secara konstan, gradual, dan prediktif.

---

### 12. Trade-offs

| Aspek | Direct Syscall / Kernel Direct Access | glibc / High-Level User Space Wrapper |
|---|---|---|
| **Portabilitas** | Rendah. Nomor syscall terikat ke arsitektur CPU spesifik (x86_64 vs ARM64 berbeda tabel). | Tinggi. POSIX compliance menjamin kode berjalan lintas OS dan arsitektur hardware. |
| **Overhead Komputasi** | Rendah untuk eksekusi minimalis, namun frekuensi tinggi tanpa buffering menyebabkan flushes pipeline CPU. | Ada overhead abstraksi tipis, namun diimbangi dengan User-space Buffering (misal: `fwrite` vs `write`). |
| **Safety & Memory Access** | Sangat ketat. Kernel menolak invalid pointer (mengembalikan `EFAULT`), tapi memanipulasi low-level memory rawan segmentation fault. | Exception handling dan sanitasi tipe data ditangani sebelum mencapai batas kernel. |
| **Observabilitas via VFS** | Sangat detail. State kernel `/proc` membeberkan realita hardware sebenarnya. | Metrik internal runtime terbatas pada apa yang dialokasikan oleh memory management bahasa tersebut. |

---

### 13. When To Use
- Saat melakukan debugging mendalam pada aplikasi yang mengalami *deadlock*, *stuck I/O*, atau *ghost resource consumption*.
- Membangun tool telemetri dan observability (seperti agent Prometheus, Datadog, atau custom APM agent).
- Mengonfigurasi parameter sistem tingkat lanjut di orchestrator kontainer (misalnya fine-tuning sysctl di Kubernetes Pod security context).
- Mengembangkan aplikasi sistem berkinerja tinggi yang membutuhkan manipulasi network socket khusus (`SO_REUSEPORT`, epoll, io_uring).

---

### 14. When NOT To Use
- Menggunakan raw system call langsung (`syscall(SYS_...)`) pada aplikasi bisnis reguler; selalu gunakan API standar bahasa Anda kecuali ada pembenaran performa ekstrem.
- Membaca `/proc` secara agresif dalam frekuensi tinggi (polling tiap millisecond); parsing file ASCII di `/proc` menghasilkan overhead alokasi string dan context switches yang membebani CPU.
- Mengubah parameter `/proc/sys/` di lingkungan produksi tanpa validasi empiris di lingkungan staging; salah mengonfigurasi parameter seperti `vm.panic_on_oom` dapat memicu *Kernel Panic* instan.

---

### 15. Common Mistakes
- **Menganggap isi `/proc` dan `/sys` ada di storage disk:** Banyak sysadmin pemula panik melihat ukuran file `/proc/kcore` yang menyamai ukuran RAM fisik, lalu berusaha menghapusnya atau menyalinnya via rsync, menyebabkan disk space analyzer salah kalkulasi.
- **Lupa persistensi perubahan runtime:** Mengubah nilai via `echo 1 > /proc/sys/net/ipv4/ip_forward` akan hilang total saat mesin di-reboot. Konfigurasi permanen wajib ditulis di `/etc/sysctl.conf` atau `/etc/sysctl.d/`.
- **Salah mengidentifikasi status "D" (Disk Sleep):** Mencoba mengirim sinyal `kill -9 <PID>` ke proses yang berada dalam state `D` di `/proc/<PID>/status`. Proses di Ring 0 yang sedang menunggu hardware I/O **tidak dapat dihentikan** oleh sinyal apa pun sampai instruksi I/O perangkat keras selesai atau timeout.

---

### 16. Best Practices (Production Checklist)
- [ ] Validasi nilai parameter sebelum dan sesudah runtime update:
  ```bash
  sysctl -a | grep <parameter_name>
  ```
- [ ] Terapkan konfigurasi kernel secara deklaratif menggunakan file terstruktur:
  ```bash
  echo "vm.max_map_count = 262144" > /etc/sysctl.d/99-elasticsearch.conf
  sysctl --system
  ```
- [ ] Batasi hak akses penulisan `/proc` dan `/sys` di level kontainer (selalu gunakan opsi *Read-Only Root Filesystem* pada Docker/Kubernetes runtime).
- [ ] Manfaatkan `perf` atau `eBPF` daripada menjalankan `strace` pada proses produksi berbeban tinggi (high-traffic), karena `strace` menghentikan sementara thread via ptrace hook yang dapat menurunkan throughput aplikasi hingga 80%.

---

### 17. Troubleshooting

#### Masalah: "Permission denied" saat menulis ke file `/proc/sys/` meskipun menggunakan `sudo`
```bash
$ sudo echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse
bash: /proc/sys/net/ipv4/tcp_tw_reuse: Permission denied
```
- **Akar Masalah:** Operator redirection (`>`) dieksekusi oleh shell User biasa sebelum perintah `sudo` dijalankan.
- **Solusi:**
  ```bash
  echo 1 | sudo tee /proc/sys/net/ipv4/tcp_tw_reuse > /dev/null
  # ATAU
  sudo sysctl -w net.ipv4.tcp_tw_reuse=1
  ```

#### Masalah: Mutasi nilai pada `/sys/` ditolak dengan error "Invalid argument"
```bash
$ sudo sysctl -w vm.overcommit_memory=5
sysctl: setting key "vm.overcommit_memory": Invalid argument
```
- **Akar Masalah:** Kernel memvalidasi rentang nilai input. Parameter `vm.overcommit_memory` hanya menerima flag integer: `0` (heuristic), `1` (always overcommit), atau `2` (strict don't overcommit).
- **Solusi:** Periksa dokumentasi resmi Kernel via `kernel-doc` atau dokumentasi `Documentation/sysctl/vm.rst` sebelum mengubah variabel sysctl.

---

### 18. Exercise
1. Tuliskan satu perintah bash berbasis pipeline untuk menemukan 5 proses di sistem Anda yang saat ini membuka jumlah *file descriptors* terbanyak dengan menganalisis `/proc/<PID>/fd/`.
2. Gunakan utility `strace` terhadap perintah `ls -l /` untuk menghitung:
   - Berapa total panggilan system call yang terjadi?
   - System call apa yang paling mendominasi alokasi waktu eksekusi?
   *(Gunakan flag agregasi ringkasan pada strace)*.

---

### 19. Challenge
Buat script Bash mandiri atau binary C monitoring performa bernama `kernel_pressure_check.sh` yang mengekstrak informasi Pressure Stall Information (PSI) dari direktori `/proc/pressure/` (CPU, Memory, dan I/O). 

**Spesifikasi Kebutuhan:**
1. Script harus membedakan metrik `some` (setidaknya satu thread terhambat) dan `full` (seluruh thread terhenti total menunggu resource).
2. Jika rata-rata ambang batas `full` memory stall selama 10 detik terakhir (`avg10`) melampaui `0.00`, cetak pesan peringatan berwarna merah ke STDOUT dan simpan entri darurat ke log file lokal dengan format:
   `[TIMESTAMP] HIGH MEMORY PRESSURE DETECTED: <nilai avg10>`.
3. Skrip harus mengekstrak data langsung dari file `/proc/pressure/memory` tanpa menggunakan software monitoring pihak ketiga.

---

### 20. Summary
- **Pemisahan Ring CPU:** User Space (Ring 3) mengeksekusi kode aplikasi terisolasi; Kernel Space (Ring 0) mengeksekusi kendali hardware, memori fisik, dan manajemen thread.
- **System Call:** Pintu gerbang resmi penyeberangan privilege dari Ring 3 ke Ring 0, dimediasi oleh instruksi CPU hardware (`SYSCALL`) dan tabel dispatcher kernel (`sys_call_table`).
- **`/proc`:** Virtual filesystem berbasis RAM yang merefleksikan proses eksekusi (`/proc/<PID>`) dan state internal kernel (`/proc/sys/`).
- **`/sys`:** Hierarki berbasis obyek (`kobject`) yang mengekspos topologi hardware, driver, bus, dan block devices.
- **Operasional Produksi:** Menguasai VFS dan batas Syscall memungkinkan diagnostik sistem tingkat rendah secara non-destruktif dan penyetelan performa runtime kernel secara real-time tanpa restart sistem.