# Kurikulum Linux: 01-Core-Foundations
## Bab 05 Module 01: Arsitektur Proses, Siklus Hidup `task_struct`, dan Mekanisme Eksekusi Kernel (`fork`, `execve`, `wait`)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
* Menganalisis representasi internal proses Linux di level kernel melalui struktur data `task_struct` dan sistem berkas virtual `/proc`.
* Membedakan siklus hidup proses, status transisi (`TASK_RUNNING`, `TASK_INTERRUPTIBLE`, `TASK_UNINTERRUPTIBLE`, `TASK_ZOMBIE`, `TASK_STOPPED`), dan implikasinya terhadap performa CPU/IO.
* Menguraikan alur eksekusi system call primitif (`clone`, `fork`, `vfork`, `execve`, `waitpid`) secara mendalam pada level low-level POSIX.
* Mendiagnosis dan mengeliminasi anomali proses di lingkungan produksi (zombie processes, orphan processes, dan state `D` / *uninterruptible sleep*).
* Mengonfigurasi batasan alokasi proses sistem untuk mencegah serangan *fork bomb* dan saturasi PID exhaustion menggunakan `cgroups` dan `sysctl`.

---

### 2. Prerequisite
* Pemahaman fundamental arsitektur sistem operasi (ruang memori virtual, *registers*, stack vs heap).
* Kemahiran menggunakan antarmuka baris perintah (CLI) Linux standar.
* Pengetahuan sintaks dasar bahasa C (pointer, manipulasi memori, struktur data, dan eksekusi file header POSIX).
* Pemahaman dasar tentang interupsi hardware dan transisi mode CPU (*User Space* ke *Kernel Space* via *System Call*).

---

### 3. Concept
Proses di dalam sistem operasi Linux bukan sekadar berkas biner yang sedang berjalan, melainkan sebuah entitas abstrak dinamis yang merepresentasikan alokasi sumber daya sistem secara terisolasi. 

Di dalam kernel Linux, setiap proses diabstraksikan oleh sebuah struktur data C berukuran besar yang disebut **Process Control Block (PCB)**, yang diimplementasikan sebagai `struct task_struct` (didefinisikan di `<linux/sched.h>`). Struktur ini mengelola seluruh atribut proses:
1. **Identifier**: PID (*Process ID*), TGID (*Thread Group ID*), UID, GID.
2. **State**: Status eksekusi saat ini diatur oleh bitmask kernel.
3. **Memory Descriptors**: Struktur `mm_struct` yang memetakan *Virtual Memory Areas* (VMA), page tables, text segment, data segment, dan stack.
4. **File Descriptors Table**: Struktur `files_struct` yang melacak array pointer ke file terbuka, socket, dan pipe.
5. **Signal Handling**: Struktur `signal_struct` yang menyimpan aksi registrasi dan pending mask untuk sinyal asynchronous.
6. **Context Switching Information**: Data arsitektur spesifik CPU (`thread_struct`) yang menyimpan pointer stack kernel, program counter, dan registers ketika proses di-preempt oleh scheduler (*Completely Fair Scheduler* / EEVDF).

Linux mengimplementasikan paradigma hierarki proses yang ketat: setiap proses baru diturunkan dari proses induk (*parent*) menggunakan mekanisme penyalinan ruang keadaan, kecuali `swapper`/`idle` (PID 0) dan proses *init* pengguna sistem (`systemd` pada sistem modern, PID 1).

---

### 4. Why
Memahami manajemen proses hingga level internal kernel sangat krusial bagi arsitek infrastruktur dan insinyur keandalan sistem (*Site Reliability Engineers* / *Systems Engineers*) karena:
* **Mencegah PID Exhaustion**: Sistem Linux memiliki batasan jumlah PID (`/proc/sys/kernel/pid_max`). Kegagalan me-reap child process akan mengakibatkan *zombie processes* yang menghabiskan slot tabel proses, menyebabkan kernel menolak pembuatan proses baru (`EAGAIN: Resource temporarily unavailable`).
* **Optimasi Performa Kontainer**: Runtime kontainer (Docker, containerd, CRI-O) hanyalah pemanfaatan Linux Namespaces (termasuk PID namespace) dan Control Groups (cgroups) terhadap `task_struct`. Pemahaman ini membedakan teknisi yang hanya bisa menjalankan kontainer dari teknisi yang mampu men-debug *crash loop* atau kebocoran memori kernel.
* **Diagnostik Sistem Macet (*System Hangs*)**: Proses yang terkunci dalam status `D` (*Uninterruptible Sleep*) biasanya diakibatkan oleh kebuntuan I/O pada perangkat storage/NFS. Status ini tidak dapat dihentikan bahkan menggunakan `SIGKILL` (`kill -9`), menuntut kemampuan tracing kernel berbasis `strace`, `perf`, atau pembacaan `/proc/[pid]/stack`.

---

### 5. What
Komponen utama yang menyusun manajemen proses di Linux:
* **`task_struct`**: Struktur sentral kernel pengelola siklus hidup proses.
* **Copy-On-Write (COW)**: Optimasi manajemen memori kernel saat menduplikasi ruang memori via `fork()`. Halaman memori fisik tidak disalin sampai salah satu proses menulis ke halaman tersebut.
* **Virtual Filesystem `/proc`**: Antarmuka berbasis RAM yang mengekspos status internal `task_struct` ke *user space* dalam bentuk file teks (contoh: `/proc/[pid]/status`, `/proc/[pid]/maps`, `/proc/[pid]/fd/`).
* **System Calls Inti**:
  * `fork()`: Menduplikasi proses pemanggil, menghasilkan child process dengan PID unik.
  * `execve()`: Mengganti total citra memori proses pemanggil dengan program baru (ELF binary/script).
  * `waitpid()`: Menghentikan eksekusi parent hingga status child berubah dan membaca status terminasinya (mencegah zombie).
  * `clone()`: System call dasar yang lebih fleksibel di mana `fork()`, `vfork()`, dan `pthread_create()` diimplementasikan dengan membagikan flag namespace/memori tertentu.

---

### 6. How
Alur kerja pembuatan, eksekusi, dan terminasi proses berlangsung dalam langkah-langkah presisi berikut:

```
[Parent Process]
       │
       ▼
   fork() / clone() ───(Kernel Space)───► Alokasi task_struct baru
       │                                  Duplikasi Page Tables (Tandai Copy-On-Write)
       │                                  Salin File Descriptors & Signal Handlers
       │                                  Tetapkan PID Baru
       ├─────────────────────────────────────────┐
       ▼ (Mengembalikan PID Anak)                ▼ (Mengembalikan 0)
[Parent Process]                          [Child Process]
       │                                         │
  waitpid() (Block/Wait)                         ▼
       │                                      execve() ───► Kernel memvalidasi ELF
       │                                         │          Bebaskan memory space lama
       │                                         │          Setup Stack, Heap, Text segment baru
       │                                         │          Reset Signal Handlers default
       │                                         ▼
       │                                  Eksekusi Program Baru (main())
       │                                         │
       │                                         ▼
       │                                       exit()
       │                                         │
       ▼                                         ▼
Menerima SIGCHLD ◄───────────────────── [ZOMBIE STATE]
Baca exit code child                   (Menunggu status dibaca,
Hapus task_struct child                task_struct masih tertahan)
Resume eksekusi parent
```

1. **Inisiasi (`fork`)**: Parent memanggil `fork()`. Kernel mengeksekusi arsitektur `sys_clone()`. Kernel menyalin data struktural induk ke `task_struct` anak, mengalokasikan PID baru, dan menetapkan memori halaman induk ke status *read-only* dengan penanda Copy-on-Write (COW).
2. **Mutasi Identitas (`execve`)**: Child memanggil `execve(const char *filename, char *const argv[], char *const envp[])`. Kernel memvalidasi format biner (misal ELF magic number), melepaskan ruang alamat virtual lama anak, memetakan segmen biner baru ke dalam memori virtual, menginisialisasi stack baru untuk argumen/environment, dan mengarahkan Program Counter (PC) ke *entry point* biner baru (`_start`).
3. **Pembersihan Sumber Daya (`exit`)**: Saat child memanggil `exit()`, kernel membebaskan sebagian besar sumber dayanya (VMA memori, file descriptors), namun **tetap mempertahankan** `task_struct` anak di kernel process table. Proses masuk ke status `TASK_ZOMBIE` / `EXIT_ZOMBIE`.
4. **Reaping (`waitpid`)**: Kernel mengirimkan sinyal `SIGCHLD` ke parent. Parent mengeksekusi `waitpid()`. Kernel mentransfer return code anak ke parent, kemudian menghapus `task_struct` anak secara permanen dari memori sistem.

---

### 7. Analogy
Bayangkan sebuah **Perusahaan Percetakan Dokumen Resmi (Sistem Operasi)**:
* **`task_struct`**: Berkas rekam jejak karyawan yang berisi identitas, daftar akses ruangan, inventaris meja kerja, dan status pekerjaan.
* **`fork()`**: Seorang manajer mencetak lembar kerja duplikat secara instan. Manajer dan asistennya membaca dari kertas kerja yang sama. Kertas aslinya tidak difotokopi ulang secara fisik hingga asisten mulai menulis coretan baru di kertas tersebut (*Copy-On-Write*).
* **`execve()`**: Asisten merapikan mejanya, membuang semua dokumen lama proyek percetakan, dan mengambil mandat baru sebagai akuntan perusahaan; meja kerjanya tetap sama, orangnya sama, tetapi seluruh fokus dan dokumen yang dikerjakannya berganti total.
* **`Zombie State`**: Asisten telah mengundurkan diri dan berhenti bekerja, tetapi lencana karyawannya belum diserahkan ke bagian personalia. Manajer harus datang ke personalia (`waitpid()`) untuk menandatangani berkas pelepasan agar nama sang asisten resmi dihapus dari daftar karyawan aktif.

---

### 8. Diagram
Diagram transisi status proses di Linux:

```
                    ┌────────────────────────┐
                    │      CREATED           │
                    │   (via fork/clone)     │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
      ┌────────────►│      TASK_RUNNING      │◄────────────┐
      │             │   (Ready / Executing)  │             │
      │             └───────────┬────────────┘             │
      │                         │                          │
Scheduler Preempt /             │ Kernel menunggu          │ Event selesai /
Time slice habis                │ I/O atau Event           │ Interupsi diterima
      │                         ▼                          │
      │             ┌────────────────────────┐             │
      └─────────────┤   TASK_INTERRUPTIBLE   ├─────────────┘
                    └────────────────────────┘
                    ┌────────────────────────┐
                    │  TASK_UNINTERRUPTIBLE  ├─────────────► (Wake up bila hardware
                    │        (State D)       │                I/O tuntas)
                    └───────────┬────────────┘
                                │
                      SIGSTOP / │ SIGCONT
                      ptrace    │
                                ▼
                    ┌────────────────────────┐
                    │      TASK_STOPPED      │
                    └───────────┬────────────┘
                                │
                                │ exit() / terminasi sinyal fatal
                                ▼
                    ┌────────────────────────┐
                    │      EXIT_ZOMBIE       │
                    │   (Menunggu reaping)   │
                    └───────────┬────────────┘
                                │
                                │ wait() / waitpid() dipanggil parent
                                ▼
                    ┌────────────────────────┐
                    │      TERMINATED        │
                    │ task_struct dibebaskan │
                    └────────────────────────┘
```

---

### 9. Simple Example
Mengamati identitas proses dan ruang lingkup lingkungan subshell menggunakan Linux CLI:

```bash
# Cetak PID dan Process Name dari shell yang sedang aktif
echo "PID Shell ini: $$"

# Verifikasi representasi kernel di sistem berkas /proc
cat /proc/$$/status | grep -E '^(Name|Pid|PPid|State|Threads)'

# Jalankan background sleep dan amati transisi status di tabel proses
sleep 60 &
CHILD_PID=$!
echo "Child PID: ${CHILD_PID}"

# Cek status proses child (seharusnya S = Interruptible Sleep)
ps -o pid,ppid,state,cmd -p ${CHILD_PID}

# Hentikan proses child
kill -9 ${CHILD_PID}
```

---

### 10. Practical Example
Berikut adalah implementasi program C standar POSIX produksi yang mendemonstrasikan penanganan `fork()`, mutasi via `execve()`, serta penanganan asynchronous sinyal `SIGCHLD` untuk mencegah pembentukan *zombie process*.

Simpan kode berikut sebagai `process_lifecycle.c`:

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <string.h>

// Signal handler aman untuk mereap semua child yang selesai (Non-blocking)
void sigchld_handler(int signo) {
    (void)signo;
    int saved_errno = errno;
    pid_t pid;
    int status;

    // Loop WNOHANG untuk menangkap banyak child yang keluar bersamaan
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0) {
        if (WIFEXITED(status)) {
            printf("\n[REAPER] Child PID %d exited cleanly with code: %d\n", pid, WEXITSTATUS(status));
        } else if (WIFSIGNALED(status)) {
            printf("\n[REAPER] Child PID %d killed by signal: %d\n", pid, WTERMSIG(status));
        }
    }
    errno = saved_errno;
}

int main(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigchld_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART | SA_NOCLDSTOP;

    if (sigaction(SIGCHLD, &sa, NULL) == -1) {
        perror("Gagal registrasi sigaction");
        exit(EXIT_FAILURE);
    }

    printf("[PARENT] PID: %d, bersiap melakukan fork...\n", getpid());

    pid_t child_pid = fork();

    if (child_pid < 0) {
        perror("Fork gagal dieksekusi");
        exit(EXIT_FAILURE);
    }

    if (child_pid == 0) {
        // --- CHILD PROCESS CONTEXT ---
        printf("[CHILD] PID: %d, PPID: %d. Mengganti memori via execve...\n", getpid(), getppid());

        // Menyiapkan argumen untuk execve (/bin/ls -l -h /proc/self)
        char *binary_path = "/bin/ls";
        char *args[] = { "ls", "-lh", "/proc/self", NULL };
        char *env[] = { "PATH=/bin:/usr/bin", NULL };

        // Eksekusi mutasi proses
        execve(binary_path, args, env);

        // Baris di bawah HANYA tercapai jika execve gagal
        perror("[CHILD] execve gagal dieksekusi");
        _exit(127);
    } else {
        // --- PARENT PROCESS CONTEXT ---
        printf("[PARENT] Berhasil membuat child PID: %d. Menunggu child selesai...\n", child_pid);

        // Simulasi pekerjaan Parent, menunggu sinyal SIGCHLD bekerja
        for (int i = 0; i < 3; i++) {
            printf("[PARENT] Bekerja memproses transaksi %d...\n", i + 1);
            sleep(1);
        }
        printf("[PARENT] Selesai. Keluar dari program utama.\n");
    }

    return EXIT_SUCCESS;
}
```

Kompilasi dan jalankan:
```bash
gcc -Wall -Wextra -O2 process_lifecycle.c -o process_lifecycle
./process_lifecycle
```

---

### 11. Real World Example
**Insiden Produksi**: Kegagalan Skalabilitas Microservice Node.js di Kluster Kubernetes.

* **Kondisi**: Sebuah layanan pemrosesan gambar berbasis Node.js dijalankan di Kubernetes Pod tanpa init manager kustom. Node.js menggunakan fungsi `child_process.spawn()` untuk memanggil utilitas `imagemagick` / `ffmpeg` guna mengubah resolusi aset secara intensif.
* **Masalah**: Node.js berjalan sebagai PID 1 di dalam Pod container. Ketika sub-proses ImageMagick selesai, statusnya tidak di-*reap* secara konsisten karena asynchronous garbage collection loop Node.js terkadang terlambat menangani event `exit` atau child mati secara abnormal. Ribuan child process masuk ke status `TASK_ZOMBIE`.
* **Dampak**: Meskipun utilisasi RAM dan CPU Pod terlihat rendah di Prometheus, pembuatan proses baru tiba-tiba gagal dengan error fatal `fork: Resource temporarily unavailable`. Node Linux host menolak membuat thread atau proses baru karena container mencapai batas `pids.max` (cgroups limit). Node lain mengalami isolasi parsial.
* **Solusi Arsitektural**:
  1. Menambahkan biner init minimalis seperti `tini` atau `dumb-init` sebagai *entrypoint* Pod, yang secara eksplisit bertindak sebagai PID 1 untuk mengadopsi dan me-reap proses yatim (*orphan processes*).
  2. Mengaktifkan opsi `shareProcessNamespace: true` pada spesifikasi Pod Kubernetes untuk memungkinkan inspeksi tabel proses secara transparan antar kontainer.

---

### 12. Trade-offs

| Kategori | Model Multi-Process (`fork`) | Model Multi-Threading (`clone` + `CLONE_VM`) |
| :--- | :--- | :--- |
| **Advantages** | Isolasi memori penuh. Jika 1 child crash (Segmentation Fault), parent & child lain tetap berjalan aman. Tidak butuh locking kompleks pada global memory. | Penggunaan sumber daya memori sangat efisien. IPC (*Inter-Process Communication*) instan melalui heap bersama tanpa serialization. |
| **Disadvantages** | Konsumsi memori lebih besar. Komunikasi antar proses (IPC) harus lewat pipes, shared memory (`shmget`), atau sockets yang menambah overhead arsitektur. | Kerentanan *data race* tinggi; kegagalan memori di satu thread (contoh: *bad pointer write*) akan meruntuhkan seluruh proses aplikasi. |
| **Complexity** | Menengah: Pengelolaan sinyal (`SIGCHLD`), pelepasan descriptor, dan penanganan status zombie memerlukan akurasi tinggi. | Sangat Tinggi: Membutuhkan sinkronisasi mutex, spinlock, semaphore, serta pencegahan deadlock yang rumit. |
| **Performance** | Context switch antar proses memakan CPU cycle lebih tinggi karena harus melakukan flush Translation Lookaside Buffer (TLB). | Context switch lebih cepat karena thread berbagi ruang alamat memori dan page table yang sama. |
| **Cost** | Footprint kernel lebih besar untuk setiap instance (`task_struct`, VMA tables, descriptor tables). | Footprint kernel lebih ringan untuk alokasi per unit komputasi. |

---

### 13. When To Use
* **Aplikasi dengan Arsitektur Multi-tenant**: Eksekusi kode yang tidak dipercaya (*untrusted code execution*) atau script pihak ketiga yang membutuhkan jaminan isolasi memori mutlak.
* **Worker Process Architecture**: Pola arsitektur seperti Nginx, PostgreSQL, atau Gunicorn di mana *master process* bertindak sebagai supervisor andal dan mendistribusikan beban ke *worker processes*.
* **Aplikasi Berorientasi Ketahanan Ekstrim**: Service yang tidak boleh mati secara sistemik hanya karena salah satu transaksi komputasi memicu memori korup atau abort.

---

### 14. When NOT To Use
* **Operasi I/O Frekuensi Ultra-Tinggi (Micro-tasks)**: Misalnya sistem API gateway dengan jutaan websocket concurrent; hindari spawning proses baru untuk tiap koneksi (gunakan event-loop non-blocking seperti `epoll` atau `io_uring`).
* **Sistem dengan Akses Data Matriks Terdistribusi Bersama**: Komputasi grafika/AI/HPC di mana ribuan worker membutuhkan throughput pembacaan dan penulisan memori yang sama secara langsung pada latensi sub-mikrodetik.

---

### 15. Common Mistakes
* **Mengabaikan Loop Reaping pada `SIGCHLD`**: Hanya memanggil `waitpid()` sekali saat menerima `SIGCHLD`. Sinyal Linux bersifat non-queueable; jika 5 proses anak mati dalam jendela waktu yang hampir bersamaan, hanya 1 sinyal yang terkirim ke parent, meninggalkan 4 anak lainnya dalam status Zombie abadi. Solusi: Gunakan `while(waitpid(-1, &status, WNOHANG) > 0)`.
* **Menggunakan `fork()` pada Aplikasi Multi-threaded**: Jika proses multi-thread memanggil `fork()`, hanya thread pemanggil yang disalin ke child. Mutex yang di-lock oleh thread lain di parent akan tetap terkunci selamanya di child, memicu kondisi *instant deadlock*.
* **Tidak Memeriksa Error Return dari `fork()`**: Mengasumsikan `fork()` selalu berhasil. Pada kondisi memori habis (*OOM*) atau batas `ulimit -u` tercapai, `fork()` mengembalikan nilai `-1`, yang jika tidak dicek akan menyebabkan logika downstream berjalan di konteks yang salah.

---

### 16. Best Practices (Production Checklist)
- [ ] **Pasang Init System Minimal di Kontainer**: Selalu gunakan `tini` (`ENTRYPOINT ["/tini", "--", "/entrypoint.sh"]`) pada base image Docker stripped down.
- [ ] **Batasi Kapasitas Eksekusi Proses Maksimal**: Konfigurasi parameter batas proses per user melalui `/etc/security/limits.conf` (contoh: `appuser hard nproc 4096`).
- [ ] **Terapkan Cgroups v2 `pids.max`**: Isolasi container pod dengan limit PID ketat untuk mencegah eskalasi fork-bomb melumpuhkan Linux Node host:
  ```bash
  echo 500 > /sys/fs/cgroup/system.slice/my_service.service/pids.max
  ```
- [ ] **Gunakan Flag `O_CLOEXEC` pada File Descriptors**: Pastikan semua file descriptor dibuka dengan `FD_CLOEXEC` agar tidak bocor (*descriptor leaking*) ke child process saat eksekusi `execve`.
- [ ] **Terapkan Non-blocking Signal Handler**: Pastikan signal handler sesingkat mungkin dan hanya memanggil fungsi-fungsi *async-signal-safe* (seperti `write()`, `waitpid()`).

---

### 17. Troubleshooting

#### Masalah 1: Mengidentifikasi dan Memusnahkan Zombie Process
Gejala: Perintah `top` melaporkan peningkatan jumlah status `zombie`, PID terus bertambah.
1. Cari proses dengan status `Z` dan identifikasi Parent PID-nya (PPID):
   ```bash
   ps -eo pid,ppid,stat,cmd | awk '$3 ~ /Z/ {print $0}'
   ```
2. **Diagnosa**: Anda **tidak bisa** membunuh zombie dengan `kill -9 <PID_ZOMBIE>` karena proses tersebut sudah mati. Anda harus memaksa parent untuk me-reap child tersebut:
   ```bash
   # Kirim sinyal SIGCHLD ke Parent agar menjalankan handler wait()
   kill -s SIGCHLD <PPID>
   ```
3. Jika parent menolak me-reap child (karena bug software/deadlock):
   ```bash
   # Bunuh Parent Process. Child yang menjadi yatim (orphan) akan diadopsi oleh init (PID 1)
   # yang akan langsung me-reap zombie secara otomatis.
   kill -15 <PPID> # fallback: kill -9 <PPID>
   ```

#### Masalah 2: Proses Terjebak di State `D` (*Uninterruptible Sleep*)
Gejala: Muncul proses berstatus `D` di output `ps` yang mengabaikan sinyal `kill -9`.
1. Dapatkan jejak kernel thread proses yang macet:
   ```bash
   cat /proc/<PID>/stack
   ```
2. Analisis output kernel call stack. Jika terlihat pemanggilan subsistem storage seperti `nfs_wait_bit_uninterruptible` atau `ext4_write_inode`, masalah berakar pada storage bottleneck atau RPC timeout pada mounted share.
3. Ambil tindakan: Jangan reboot paksa server sebelum melepaskan kuncian I/O; lakukan recover pada service NFS target atau eksekusi `umount -l` (lazy unmount) pada mount point yang bermasalah.

---

### 18. Exercise
Selesaikan skenario praktis ini menggunakan workstation/VM Linux Anda:

1. **Investigasi Struktur `/proc`**:
   Buka terminal, jalankan `sleep 300 &`. Temukan direktori `/proc` milik proses tersebut. Tuliskan dalam catatan Anda:
   * Berapa nilai alamat memori virtual pada stack di `/proc/<PID>/maps`?
   * Buka `/proc/<PID>/status` dan periksa berapa banyak context switches (`voluntary_ctxt_switches` vs `nonvoluntary_ctxt_switches`) yang dialami proses tersebut.
2. **Simulasi Manual Zombie Generation**:
   Tulis script shell kecil atau biner C sederhana yang melakukan `fork()`, kemudian membuat child langsung keluar (`exit(0)`), sementara parent dibiarkan melakukan `sleep(60)` tanpa memanggil `wait()`. Verifikasi status zombie di terminal lain menggunakan utilitas `ps`.
3. **Analisis System Call dengan `strace`**:
   Jalankan tracing pada perintah `sh -c "ls /var"` menggunakan command:
   ```bash
   strace -f -e trace=clone,fork,execve,wait4,exit_group sh -c "ls /var"
   ```
   Petakan alur return value dari `clone` hingga pemanggilan `execve`.

---

### 19. Challenge
**Rancang Mini Daemon Supervisor ("Process-Watchdog")**

Buat sebuah program C mandiri atau script Bash setingkat produksi yang bertindak sebagai init-supervisor untuk biner target tertentu:
* **Requirement 1**: Supervisor harus menerima path biner target sebagai argumen pertama (misal: `./watchdog /usr/bin/python3 -m http.server 8080`).
* **Requirement 2**: Supervisor mengeksekusi target sebagai child process via `fork()` dan `execve()`.
* **Requirement 3**: Supervisor harus menangani sinyal sistem (`SIGTERM`, `SIGINT`) dan meneruskannya (*signal propagation*) ke child process secara bertanggung jawab.
* **Requirement 4**: Jika child process crash secara tiba-tiba (exit code != 0 atau mati karena sinyal tak terduga), watchdog harus mendeteksi alasan kematian secara tepat, mencatat timestamp ke file `/tmp/watchdog.log`, dan secara otomatis me-restart child process dengan jeda back-off 2 detik.
* **Requirement 5**: Pastikan tidak ada satupun proses zombie yang tersisa pada tabel proses selama siklus crash-restart berjalan.

---

### 20. Summary
* **Pusat Kendali Kernel**: Struktur `task_struct` adalah representasi absolut dari eksekusi di Linux; memahami data ini memungkinkan kontrol penuh terhadap manajemen sistem operasi.
* **Pola Pembuatan Proses**: Linux memisahkan pembuatan ruang eksekusi baru dari pemuatan program melalui dua langkah terpisah: `fork()` untuk kloning keadaan (dengan optimasi *Copy-On-Write*), dan `execve()` untuk penggantian ruang alamat dengan citra biner baru.
* **Siklus Hidup & Kematian**: Kematian proses membutuhkan koordinasi parent-child. Selama proses parent belum mengeksekusi `waitpid()`, metadata child tetap tertahan di kernel sebagai `TASK_ZOMBIE`.
* **Reliabilitas Produksi**: Manajemen proses yang matang menuntut penanganan sinyal yang deterministik, isolasi sumber daya via cgroups, dan mitigasi PID exhaustion melalui pengawasan lifecycle yang bersih.