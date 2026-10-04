# BAB 02: Quiz, Challenge, & Knowledge Check
**Sistem Operasi Linux & Otomasi Shell Scripting**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Abstraksi File System & Inode Mechanism**  
   Jelaskan bagaimana Linux Virtual File System (VFS) membedakan antara *Hard Link* dan *Symbolic (Soft) Link* pada level struktur data `inode`. Apa implikasi struktural pada pointer blok data di storage ketika file sumber asli (*target*) dihapus (`rm`) pada kedua jenis tautan tersebut?

2. **Siklus Hidup Proses & Kernel Task Struct**  
   Ketika sebuah proses dieksekusi di Linux, kernel membuat representasi berupa `task_struct`. Jelaskan perbedaan mendasar antara status proses `TASK_INTERRUPTIBLE`, `TASK_UNINTERRUPTIBLE`, dan `EXIT_ZOMBIE`. Apa bahaya akumulasi *zombie process* terhadap alokasi kapasitas proses di sistem operasi meskipun proses tersebut tidak lagi mengonsumsi CPU atau memori?

3. **Standar I/O Streams, File Descriptors, & Kernel Pipe Buffer**  
   Setiap proses Linux diinisialisasi dengan tiga standard stream: `stdin (0)`, `stdout (1)`, dan `stderr (2)`. Jelaskan mekanisme kernel ketika perintah `command > output.log 2>&1` dieksekusi vs `command 2>&1 > output.log`. Mengapa urutan pendefinisian file descriptor tersebut menghasilkan output tujuan yang berbeda secara fundamental?

4. **Kalkulasi POSIX Permissions & Bit Khusus (Special Bits)**  
   Selain bit standar (*read*, *write*, *execute* untuk *User*, *Group*, *Others*), Linux memiliki *Special Permission Bits*: SUID (Set Owner User ID), SGID (Set Group ID), dan Sticky Bit. Jelaskan implikasi keamanan dan fungsionalitas dari SGID pada sebuah direktori kolaboratif, serta Sticky Bit pada direktori bersama seperti `/tmp`.

5. **Konteks Eksekusi Subshell vs Current Shell**  
   Jelaskan perbedaan mendasar internal antara menjalankan skrip Bash menggunakan:
   * `bash script.sh`
   * `source script.sh` (atau `. script.sh`)
   * `./script.sh` (dengan *shebang*)  
   Bagaimana dampaknya terhadap pewarisan variabel *environment*, scope variabel lokal, dan Process ID (PID) dari shell pemanggil?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Evaluasi Out-Of-Memory (OOM) Killer & Memory Pressure**  
   Ketika sistem kehabisan memori fisik dan swap, OOM Killer diaktifkan oleh kernel. Jelaskan bagaimana kernel Linux mengkalkulasi `oom_score` sebuah proses dan bagaimana engineer dapat memproteksi daemon kritis (misalnya database engine) dari terminasi mendadak menggunakan nilai `oom_score_adj`.

2. **Defensive Bash Architecture: Analisis `set -euo pipefail`**  
   Dalam standard otomasi enterprise, skrip Bash wajib menggunakan *strict mode*: `set -euo pipefail`. Uraikan secara spesifik skenario kegagalan diam-diam (*silent failure*) apa yang dicegah oleh masing-masing opsi:
   * `-e` (`errexit`)
   * `-u` (`nounset`)
   * `-o pipefail`  
   Berikan contoh kasus di mana `-e` saja gagal mendeteksi error pada pipeline perintah!

3. **Investigasi I/O Saturation via System Calls (`strace` & `/proc`)**  
   Sebuah skrip worker batch processing dilaporkan mengalami status *stuck* dengan persentase CPU rendah, namun metrik `%iowait` sistem mencapai 95%. Bagaimana Anda menggunakan `strace` untuk melihat system call yang tertahan, dan informasi apa yang dapat Anda gali dari virtual filesystem `/proc/[PID]/io` serta `/proc/[PID]/wchan` untuk mengisolasi bottleneck?

4. **Mitigasi Zombie Process & PID Starvation Tanpa Reboot**  
   Sebuah *parent process* yang mengalami *bug* gagal memanggil system call `wait()` atau `waitpid()` untuk mengumpulkan exit status dari child processes yang telah mati, menghasilkan ratusan proses `<defunct>`. Mengapa perintah `kill -9 <PID_ZOMBIE>` gagal membersihkan proses tersebut? Jelaskan alur penanganan yang benar di level sistem operasi untuk membersihkannya tanpa melakukan *restart* server.

5. **Race Condition pada Shell Scripting: TOCTOU & Atomic Locking**  
   Jelaskan kerentanan *Time-of-Check to Time-of-Use* (TOCTOU) yang terjadi jika sebuah skrip Bash melakukan pemeriksaan idempotensi menggunakan pola `if [ ! -f /tmp/app.lock ]; then touch /tmp/app.lock; ... fi`. Bagaimana cara menerapkan *atomic locking* yang aman menggunakan utilitas `flock` atau fitur kernel Linux (*file locks*) untuk mencegah eksekusi konkuren?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kasus Insiden Disk Full Misterius (Ghost Files & Inode Depletion)
Sebuah server web reverse-proxy (Nginx) memicu peringatan kritis: *“No space left on device (Error 28)”*. Namun, saat On-Call Engineer mengeksekusi perintah `df -h`, partisi root `/` baru terpakai 55%. Logging traffic terhenti dan service mulai melempar HTTP 500.

**Pertanyaan Diagnostik:**
1. Apa dua kemungkinan penyebab teknis utama di level Linux filesystem yang menjelaskan anomali di mana `df -h` menunjukkan sisa kapasitas tetapi sistem melaporkan *disk full*?
2. Tuliskan urutan perintah diagnostik berbasis CLI untuk memvalidasi status penggunaan Inode vs Block Storage.
3. Jika masalah disebabkan oleh file log raksasa yang telah di-*delete* (`rm /var/log/nginx/access.log`) namun ruangannya tidak dibebaskan oleh kernel karena file descriptor masih dipegang oleh proses yang aktif, bagaimana cara Anda mengidentifikasi PID proses tersebut menggunakan `lsof` dan membebaskan disk space secara *live* tanpa menghentikan atau me-*restart* proses Nginx?

---

### Skenario B: Race Condition & Data Corruption pada Automated Sync Cron Job
Sebuah cron job shell script dijalankan setiap 5 menit untuk mengekstrak data dari API eksternal, memproses file CSV sementara di `/tmp/process/`, dan mengunggahnya ke bucket storage. Suatu hari, API eksternal mengalami latensi tinggi, menyebabkan satu siklus eksekusi memakan waktu 12 menit. Akibatnya, beberapa proses cron job yang sama berjalan bersamaan (*overlapping*), membaca dan menimpa file sementara yang sama secara bersamaan, sehingga menghasilkan data korup pada storage tujuan.

**Pertanyaan Diagnostik:**
1. Desain ulang mekanisme inisialisasi skrip tersebut menggunakan `flock` berbasis file descriptor (bukan file lock berbasis `touch`) agar jika instance skrip sebelumnya masih berjalan, eksekusi cron job yang baru langsung berhenti (*fail-fast*) secara aman dengan exit code tertentu.
2. Tunjukkan implementasi sinyal penanganan (*trap cleanup*) di Bash yang menjamin bahwa jika proses tersebut dihentikan secara paksa oleh sistem menggunakan sinyal `SIGTERM` atau `SIGINT`, seluruh temporary resources tetap terhapus sempurna.

---

### Skenario C: OS Resource Throttling & Tuning Kernel untuk High-Throughput Service
Sebuah microservice baru yang ditulis dengan Go dideploy langsung di atas Ubuntu VM. Ketika tim QA melakukan *load testing* dengan 50.000 concurrent connection, service mulai menolak koneksi baru dengan pesan error sistem: *"accept: too many open files"* dan *“connection reset by peer”*, padahal penggunaan CPU VM baru mencapai 30% dan RAM 40%.

**Pertanyaan Diagnostik:**
1. Jelaskan batasan resource di level kernel dan user-space apa saja yang sedang dilanggar oleh aplikasi tersebut (hubungkan dengan `limits.conf`, `nofile`, dan *socket backlog*).
2. Tentukan parameter kernel (`sysctl`) mana yang harus di-*tuning* secara presisi untuk menangani koneksi TCP berskala tinggi terkait *file descriptors exhaustion* dan *SYN queue backlog* (`fs.file-max`, `net.core.somaxconn`, `net.ipv4.tcp_max_syn_backlog`).
3. Tuliskan langkah konfigurasi persisten agar perubahan batas `ulimit` untuk user service tersebut tidak ter-reset saat sistem melakukan reboot.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Production Log Rotator & Health Auto-Remediation Daemon

#### Problem Statement
Sebuah sistem legacy menghasilkan file log transaksi bervolume tinggi di direktori `/var/log/legacy-app/*.log`. Aplikasi ini tidak mendukung native log rotation dan tidak dapat di-restart tanpa *downtime*. Jika ukuran direktori melampaui ambang batas tertentu, disk latency melonjak dan memicu cascaded failure pada OS. Anda ditugaskan membangun skrip otomasi Bash mandiri yang bertindak sebagai *maintenance daemon* yang robust, aman, dan siap produksi.

#### Requirements
1. **Strict Defensive Standards:**
   * Wajib menggunakan `set -euo pipefail`.
   * Seluruh variabel harus menggunakan *strict variable scoping* (`local` dalam fungsi) dan *double quoting* untuk mencegah word splitting/globbing.
2. **Atomic Locking & Non-Overlapping:**
   * Skrip harus menggunakan mekanisme locking non-blocking via `flock` menggunakan dedicated file descriptor. Jika skrip mendeteksi proses dirinya sendiri sedang berjalan, skrip harus menghentikan eksekusi dengan log status peringatan.
3. **Storage Health Threshold Validation:**
   * Skrip harus memeriksa utilisasi disk partisi target. Jika utilisasi disk `>= 85%`, skrip masuk ke mode darurat (*Aggressive Compression & Truncation*).
4. **Zero Data-Loss Log Rotation:**
   * Karena aplikasi terus menulis ke file tanpa me-release file descriptor, skrip **tidak boleh** memindahkan atau menghapus file log aktif menggunakan `mv` atau `rm` secara naif.
   * Gunakan teknik copy/compress kemudian truncate secara atomik (`truncate -s 0` atau `: > file.log`) agar file descriptor aplikasi tetap valid tanpa kehilangan pointer penulisan data baru.
5. **Retention Management:**
   * Kompresi file log hasil rotasi menggunakan format `.tar.gz` atau `.gz` dengan timestamp ISO-8601 (`YYYY-MM-DD_HHmmss`).
   * Hapus file log terkompresi yang memiliki usia lebih dari $N$ hari (didefinisikan via environment variable `RETENTION_DAYS`, default: 7 hari).
6. **Error Trapping & Structured Logging:**
   * Terapkan `trap` untuk menangkap sinyal `EXIT`, `SIGINT`, dan `SIGTERM` guna membersihkan temporary state secara bersih.
   * Skrip harus mencetak *structured standard log* dengan format:
     `[YYYY-MM-DDTHH:MM:SSZ] [LEVEL] [PID] message` ke `stdout` (untuk severity INFO) dan `stderr` (untuk severity WARN/ERROR).

#### Constraints
* **Pure POSIX/Bash Builtins & Core Utilities:** Skrip tidak boleh bergantung pada instalasi binary pihak ketiga (dilarang menggunakan tools eksternal seperti `logrotate` package, Python, atau Go). Hanya gunakan `bash`, `awk`, `sed`, `grep`, `find`, `flock`, `gzip`, `truncate`, `df`, dan `stat`.
* **Idempotent:** Skrip dapat dijalankan berulang kali tanpa memicu duplikasi data, file corrupt, atau failure loop.

#### Expected Output
1. File skrip `log_remediator.sh` lengkap dengan dokumentasi header dan arsitektur fungsi modular.
2. Contoh eksekusi perintah manual via terminal yang mendemonstrasikan skenario:
   * Eksekusi normal (*dry-run* / successful run).
   * Percobaan eksekusi bersamaan yang tertahan oleh locking mechanism.
3. Log output yang merefleksikan proses rotasi, pengosongan file log aktif, dan pembersihan file kadaluarsa.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi struktur Linux Filesystem Hierarchy Standard (FHS), peran Virtual File System (VFS), dan interaksi metadata pada Inode vs Data Blocks.
- [ ] State machine proses Linux (Running, Interruptible, Uninterruptible, Zombie, Orphan) dan bagaimana kernel mengelola alokasi PID via `task_struct`.
- [ ] Mekanisme I/O Stream Redirection, File Descriptor table (0, 1, 2, n), duplikasi descriptor via `dup2()`, dan blocking nature pada Unix Pipes (`|`).
- [ ] Model perizinan file POSIX (Read, Write, Execute, Octal Notation) serta efek dari bit khusus (SUID, SGID, Sticky Bit) dan `umask`.
- [ ] Ekosistem sinyal kernel Linux (`SIGTERM`, `SIGKILL`, `SIGINT`, `SIGHUP`, `SIGCHLD`) dan implikasi arsitektural penanganan sinyal tersebut pada shell execution.
- [ ] Perbedaan internal antara child shell, subshell `( )`, code block `{ }`, dan sourcing environment file.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap seluruh system call table number di arsitektur x86_64 (gunakan `man syscalls` atau `/usr/include/asm/unistd_64.h`).
- [ ] Setiap varian flag/opsi langka pada utilitas CLI `awk`, `sed`, atau `find` (pahami konsep filter stream dan gunakan `man` atau `--help`).
- [ ] Konversi nilai hex dari raw filesystem superblock parameters.

### Saya harus bisa melakukan:
- [ ] Melacak system call proses yang mengalami bottleneck atau hang menggunakan `strace -p <PID> -T -tt -f`.
- [ ] Menemukan dan membebaskan disk capacity yang terkunci oleh *deleted-but-open files* menggunakan kombinasi `lsof +L1` dan file descriptor truncation via `/proc/[PID]/fd/`.
- [ ] Mengonfigurasi batasan file descriptor dan process threads secara persisten pada sistem melalui `/etc/security/limits.conf` dan parameter kernel `sysctl`.
- [ ] Menulis skrip automasi Bash enterprise dengan *strict mode* (`set -euo pipefail`), modular functions, trap-based cleanup handling, dan POSIX-compliant syntax.
- [ ] Menerapkan mekanisme race-condition-free file locking menggunakan utilitas `flock` untuk menjamin eksekusi skrip background yang aman.