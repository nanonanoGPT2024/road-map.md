# MODUL 01: Arsitektur Sistem Operasi Linux, Filesystem Hierarchy Standard, dan Manajemen Proses

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CORE-FND-0201`
* **Nama Modul**: Arsitektur Sistem Operasi Linux, Filesystem Hierarchy Standard (FHS), dan Manajemen Proses Tingkat Lanjut
* **Kategori**: `01-Core-Foundations`
* **Jalur Pembelajaran**: `devops-beginner`
* **Prasyarat**: Pemahaman dasar tentang cara kerja komputer, CLI dasar (Command Line Interface), dan konsep dasar komputasi jaringan.
* **Alokasi Waktu**: 8 Jam Pembelajaran Mandiri / Praktik Laboratorium (Hands-on Lab)
* **Tingkat Kesulitan**: Intermediate (Tingkat Dasar Lanjutan untuk Rekayasa DevOps)
* **Penulis / Peninjau**: Senior Technical Curriculum Architect

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Arsitektur Kernel & User Space**: Membedakan interaksi antara *Hardware*, *Linux Kernel*, *System Calls* (`syscalls`), dan aplikasi *User Space* dengan akurasi 100% pada konteks alokasi sumber daya komputasi.
2. **Menavigasi dan Mengelola Filesystem Hierarchy Standard (FHS)**: Mengidentifikasi tujuan fungsional dari direktori root (`/etc`, `/var`, `/proc`, `/sys`, `/dev`, `/opt`) dan menerapkan isolasi path yang tepat saat merancang lingkungan runtime aplikasi.
3. **Mengeksekusi Manajemen Izin Akses dan Kepemilikan Lanjutan**: Mengonfigurasi hak akses POSIX (Read, Write, Execute), Sticky Bit, SUID, SGID, serta File Access Control Lists (FACL) untuk memitigasi risiko eskalasi hak istimewa (privilege escalation).
4. **Mengontrol Siklus Hidup Proses Linux**: Mengoperasikan *process state transitions*, memanfaatkan *signals* (`SIGTERM`, `SIGKILL`, `SIGHUP`), mengidentifikasi *zombie* dan *orphan processes*, serta membedakan mekanisme *fork-exec*.
5. **Mengabstraksi Pengelolaan Service Menggunakan Systemd**: Menulis, mengonfigurasi, dan men-debug berkas *Systemd Service Unit* yang *resilient* dengan deklarasi batasan resource limit (cgroups) dan restart policy yang tepat.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Linux Operating System]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
   [Kernel Space]                                    [User Space]
   ├── Process Scheduler                             ├── GNU Core Utilities
   ├── Memory Management                             ├── Shells (Bash, Zsh)
   ├── Virtual Filesystem (VFS)                      └── Applications / Daemons
   └── Device Drivers                                      │
         │ (System Calls: open, read, fork, clone)         │
         └────────────────────────┬────────────────────────┘
                                  ▼
                 [Filesystem Hierarchy Standard]
                 ├── /etc  (Konfigurasi Statis Host)
                 ├── /var  (Data Variabel: Log, Cache)
                 ├── /proc (Virtual Pseudo-FS: State Proses)
                 └── /sys  (Virtual Pseudo-FS: Objek Kernel)
                                  │
                                  ▼
               [Process Lifecycle & Orchestration]
                 ├── PID 1 (Init System: Systemd)
                 ├── Forks, Execs, Child Lifecycle
                 ├── POSIX Signals (SIGTERM, SIGKILL)
                 └── Security Context (UID, GID, POSIX/ACLs)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam paradigma modern seperti *Containers* (Docker, Podman) dan *Container Orchestration* (Kubernetes), kontainer **bukanlah virtual machine**. Kontainer hanyalah proses Linux biasa yang diisolasi menggunakan fitur kernel: *Namespaces* (isolasi pandangan) dan *Control Groups* / *cgroups* (pembatasan alokasi sumber daya). 

Seorang DevOps Engineer yang tidak memahami cara kerja fundamental Linux akan menghadapi kegagalan fatal ketika:
* **Debugging OOM (Out Of Memory) Killer**: Memahami mengapa kernel membunuh proses aplikasi di Kubernetes pod.
* **Graceful Shutdown**: Mengapa kontainer lambat berhenti atau tiba-tiba menghasilkan transaksi data korup (kegagalan menangani sinyal `SIGTERM` sebelum kernel mengirimkan `SIGKILL`).
* **Broken Permissions**: Masalah klasik `Permission Denied` di pipeline CI/CD atau saat mounting *Persistent Volume* tanpa pemahaman `UID/GID mapping`.
* **Zombie Process Leakage**: Akumulasi proses zombie di dalam *container execution environment* yang mengakibatkan *process table exhaustion*.

Linux adalah pondasi tak tergantikan dari 90%+ infrastruktur cloud, runtime kontainer, pipeline orkestrasi, dan platform otomasi modern.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Kernel Space vs. User Space
Sistem operasi Linux membagi memori menjadi dua arsitektur proteksi virtual memory (disebut Rings, berbasis x86 Privilege Rings):
* **Kernel Space (Ring 0)**: Memiliki akses langsung tanpa batasan ke CPU, physical memory, dan hardware I/O. Kernel mengeksekusi thread inti, network stack, dan penjadwalan proses.
* **User Space (Ring 3)**: Tempat seluruh proses pengguna berjalan (web server, database, shell). User space tidak dapat mengakses hardware secara langsung; setiap interaksi harus melalui **System Call** (`syscall`) yang diatur oleh C Standard Library (`glibc`).

### 2. Virtual Filesystem (VFS) & FHS
Linux memperlakukan hampir semua abstraksi sebagai file ("*Everything is a file*"). VFS adalah lapisan abstraksi kernel yang menyajikan sistem berkas seragam terlepas dari tipe storage fisik underlying (ext4, XFS, Btrfs, NFS).
* **FHS (Filesystem Hierarchy Standard)** mendefinisikan struktur direktori yang konsisten:
  * `/`: Root direktori utama.
  * `/etc`: Konfigurasi konfigurasi sistem host yang dapat diedit secara teks.
  * `/var`: Data variabel yang terus berubah selama runtime (`/var/log`, `/var/run`).
  * `/proc` & `/sys`: File system semu (*pseudo-filesystems* berbasis RAM) yang mengekspos internal kernel state, resource limits, dan hardware profiling langsung ke user space.

### 3. Proses, Thread, dan Systemd
Proses adalah instance program yang sedang dieksekusi, dialokasikan blok memori independen (*virtual address space*), context state, dan *file descriptors* (0: stdin, 1: stdout, 2: stderr).
* **PID (Process ID)**: Pengenal numerik unik untuk setiap proses.
* **PID 1**: Proses *init* pertama yang di-spawn oleh Kernel saat booting. Pada sistem operasi Linux modern, PID 1 dijalankan oleh **Systemd**, yang bertanggung jawab memanajemen daemons, service lifecycles, target dependencies, dan log sentral (*journald*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Alur Eksekusi: Dari Binary ke Running Process (`fork` & `execve`)

1. **Invocation**: Pengguna atau program induk (*parent process*) memanggil system call `fork()` untuk menduplikasi dirinya sendiri.
2. **Duplikasi Konteks**: Kernel membuat salinan struktur proses (Task Struct), memberikan PID baru untuk *child process*, dan menerapkan mekanisme *Copy-On-Write* (COW) pada memory space.
3. **Substitusi Program**: Child process memanggil system call `execve()`. Kernel menimpa text segment, heap, stack, dan memory space lama dengan binary image program baru yang dieksekusi.
4. **Execution & Termination**: Program dieksekusi hingga mengembalikan exit status code (`0` untuk sukses, `non-zero` untuk error) melalui system call `exit()`.
5. **Reaping**: Parent process harus menangkap exit code tersebut via `wait()` atau `waitpid()`. Jika parent gagal menangkapnya, child menjadi **Zombie Process (`<defunct>`)**. Jika parent mati lebih dulu, child menjadi **Orphan Process** yang otomatis diadopsi oleh PID 1 (`systemd`).

### Mekanisme Pengiriman POSIX Signals
Sinyal adalah interupsi asinkron tingkat kernel yang dikirimkan ke suatu proses untuk memberi notifikasi kejadian tertentu:

| Sinyal | Angka | Default Action | Dapat Ditangkap/Diabaikan (Catchable)? | Penggunaan DevOps Kontekstual |
| :--- | :--- | :--- | :--- | :--- |
| `SIGHUP` | 1 | Terminate | **Ya** | Reload configuration daemon tanpa restart |
| `SIGINT` | 2 | Terminate | **Ya** | Interupsi terminal keyboard (`Ctrl + C`) |
| `SIGQUIT` | 3 | Core Dump | **Ya** | Dump proses memori ke disk untuk debugging |
| `SIGKILL` | 9 | Force Kill | **TIDAK** | Terminasi paksa tingkat kernel (Anti-hang) |
| `SIGTERM` | 15 | Terminate | **Ya** | Permintaan terminasi sopan (*Graceful Shutdown*) |
| `SIGCHLD` | 17 | Ignore | **Ya** | Notifikasi child process selesai/berhenti |

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Transisi Status Proses Linux (Process States)

```
               [ Binary Disk ]
                      │ (fork + execve)
                      ▼
               ┌──────────────┐
               │   TASK_NEW   │
               └──────┬───────┘
                      │ Kernel Scheduler mendaftarkan task
                      ▼
               ┌──────────────┐
         ┌────►│ TASK_RUNNING │◄────┐
         │     │ (Ready/Exec) │     │
         │     └──────┬───────┘     │
  I/O Selesai /       │             │ CPU Preemption
  Event Terjadi       │ Meminta I/O │ Time-slice habis
         │            ▼             │
         │     ┌──────────────┐     │
         └─────┤TASK_WAITING  ├─────┘
               │(Interruptible│
               │ /Uninterrupt)│
               └──────┬───────┘
                      │ Eksekusi selesai / exit() terpanggil
                      ▼
               ┌──────────────┐
               │ TASK_ZOMBIE  │ (Menunggu parent memanggil wait())
               └──────┬───────┘
                      │ Parent mengeksekusi wait()
                      ▼
               ┌──────────────┐
               │  TERMINATED  │ (Memory & Task Struct dibebaskan)
               └──────────────┘
```

### 2. VFS, Inodes, dan File Descriptor Table

```
User Space: Process (e.g., NGINX / PID 1042)
┌───────────────────────────────────────────────┐
│ File Descriptor (FD) Table:                   │
│   FD 0  ──> Standard Input (Keyboard/Socket)  │
│   FD 1  ──> Standard Output (/var/log/stdout) │
│   FD 2  ──> Standard Error (/var/log/stderr)  │
│   FD 3  ──> Open File Pointer                 │
└───────────────────────┬───────────────────────┘
                        │ System Call Read/Write
Kernel Space:           ▼
┌───────────────────────────────────────────────┐
│ Virtual Filesystem (VFS) Layer                │
│ ┌───────────────────────────────────────────┐ │
│ │ Open File Table (Offset, Access Modes)    │ │
│ └─────────────────────┬─────────────────────┘ │
│                       ▼                       │
│ ┌───────────────────────────────────────────┐ │
│ │ Inode Table (Metadata: Perms, UID, Size)  │ │
│ └─────────────────────┬─────────────────────┘ │
└───────────────────────┼───────────────────────┘
                        ▼
Physical Storage: Ext4 Block Device [Blocks on Disk: Data blocks]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi fundamental inspeksi sistem operasi Linux melalui pseudo-filesystem `/proc` tanpa menggunakan monitoring tools eksternal.

```bash
#!/usr/bin/env bash
# Inspeksi identitas proses shell saat ini

# Mengetahui Process ID shell saat ini
CURRENT_PID=$$
echo "Current Shell PID: ${CURRENT_PID}"

# Membaca environment variables langsung dari Kernel Pseudo-FS
echo "=== Command Line Invocation ==="
tr '\0' '\n' < /proc/"${CURRENT_PID}"/cmdline
echo ""

# Membaca alokasi memori Virtual vs Resident (RAM aktual)
echo "=== Memory Consumption (Status) ==="
grep -E 'VmSize|VmRSS' /proc/"${CURRENT_PID}"/status

# Mengamati File Descriptors yang sedang terbuka
echo "=== Active File Descriptors ==="
ls -l /proc/"${CURRENT_PID}"/fd
```

**Penjelasan Alur:**
* `$$` menyimpan representasi PID shell interaktif yang sedang berjalan.
* Data di `/proc/[PID]/` tidak disimpan di hard disk, melainkan diproduksi secara *real-time* oleh kernel Linux saat dibaca.
* `tr '\0' '\n'` diperlukan karena parameter baris perintah di `/proc/[PID]/cmdline` dipisahkan menggunakan *null byte* (`\0`), bukan newline.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Menulis dan men-deploy sebuah *Daemon Application* khusus yang berjalan di background menggunakan **Systemd Service Unit**, menerapkan batasan resource (*cgroups*), dan menangani rotasi izin berkas secara aman.

### 1. Buat Script Worker (`/usr/local/bin/dummy-worker.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Handler fungsi untuk menangani POSIX SIGTERM (Graceful Shutdown)
cleanup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] SIGTERM diterima. Membersihkan resource..."
    # Simulasi pelepasan koneksi database / commit transaksi
    sleep 2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Shutdown selesai secara graceful. Keluar."
    exit 0
}

# Trap sinyal SIGTERM dan SIGINT
trap cleanup SIGTERM SIGINT

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Service dummy-worker berhasil diinisialisasi (PID: $$)..."

# Main loop simulasi pemrosesan beban kerja
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Worker beroperasi pada status sehat (Healthy)..."
    sleep 5
done
```

Pastikan eksekusi permission diaktifkan:
```bash
sudo chmod 755 /usr/local/bin/dummy-worker.sh
```

### 2. Buat Systemd Service Unit (`/etc/systemd/system/dummy-worker.service`)

```ini
[Unit]
Description=Dummy Enterprise Background Worker Engine
Documentation=https://internal-docs.enterprise.com/apps/worker
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/dummy-worker.sh
Restart=on-failure
RestartSec=5s

# Hardening & Security Context Isolation
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log

# Cgroups v2 Resource Limiting
MemoryMax=128M
CPUQuota=20%

# Timeout handling untuk Graceful Shutdown (Kirim SIGKILL jika SIGTERM diabaikan)
TimeoutStopSec=10s

[Install]
WantedBy=multi-user.target
```

### 3. Registrasi, Aktivasi, dan Verifikasi Siklus Hidup Service

```bash
# 1. Reload systemd manager configuration untuk membaca unit baru
sudo systemctl daemon-reload

# 2. Start dan enable service saat boot time
sudo systemctl enable --now dummy-worker.service

# 3. Cek status lifecycle dan cgroup attachment
sudo systemctl status dummy-worker.service

# 4. Observasi output log terstruktur secara streaming (journald)
sudo journalctl -u dummy-worker.service -f
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memahami arsitektur Linux melibatkan pemilihan konfigurasi yang memiliki konsekuensi teknis langsung:

### 1. `SIGTERM` vs `SIGKILL` pada Otomasi Deploy
* **SIGTERM (Graceful)**:
  * *Kelebihan*: Menjamin integritas data, menutup koneksi database, menghapus temporary socket files (`.sock`).
  * *Kekurangan*: Membutuhkan waktu tunggu (`TimeoutStopSec`). Jika proses *hung*, pipeline CI/CD atau orkestrator kontainer akan tertahan hingga batas waktu timeout.
* **SIGKILL (Abrupt)**:
  * *Kelebihan*: Membunuh proses secara instan dari level kernel.
  * *Kekurangan*: Berisiko tinggi menyebabkan korupsi database, file lock tertinggal, transaksi gantung (*dangling transactions*).

### 2. POSIX Permissions Standar vs. ACL (Access Control Lists)
* **Standard POSIX (Chmod/Chown)**:
  * *Kelebihan*: Kompatibilitas universal di semua platform UNIX, ringan, mudah dikelola untuk deployment sederhana.
  * *Kekurangan*: Sangat kaku. Tidak mampu memberikan izin ke multiple user atau multiple group yang berbeda di satu resource yang sama tanpa membuat group OS baru.
* **POSIX ACLs (`setfacl`, `getfacl`)**:
  * *Kelebihan*: Granularitas tinggi. Anda dapat memberikan hak `rwx` spesifik untuk User A, User B, dan Group C pada satu direktori tanpa mengubah pemilik utama.
  * *Kekurangan*: Kompleksitas audit keamanan meningkat. Rentan terlewat saat proses backup jika tool backup tidak mendukung flag preservation ACL (`tar -p --acls`).

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip Least Privilege**: Jangan pernah menjalankan application runtime daemon sebagai `root`. Selalu gunakan dedicated system user tanpa shell login (`useradd -r -s /sbin/nologin <appname>`).
2. **Standardisasi Path FHS**:
   * Jangan meletakkan aplikasi di `/root` atau subdirektori `/home`.
   * Gunakan `/opt/<vendor>/<app>` untuk static standalone enterprise binaries.
   * Gunakan `/var/log/<app>` untuk output application logs jika tidak menggunakan stdout.
3. **Konfigurasi Systemd Timeout**: Selalu tetapkan nilai `TimeoutStopSec` yang masuk akal (misal: 10–30 detik). Tanpa ini, systemd secara default dapat menunggu hingga 90 detik saat server shutdown jika suatu service macet.
4. **Hindari Zombie Accumulation pada Container Initialization**: Jika mengemas aplikasi kompleks (multiple processes) di dalam kontainer tanpa systemd, gunakan micro-init system seperti `tini` atau `dumb-init` sebagai PID 1 untuk melakukan process reaping.
5. **Defensive Shell Scripting**: Selalu sertakan deklarasi `set -euo pipefail` di setiap awal script otomatisasi:
   * `-e`: Langsung keluar jika ada perintah yang gagal (non-zero exit).
   * `-u`: Perlakukan variabel yang belum didefinisikan sebagai error.
   * `-o pipefail`: Gagalkan pipeline jika salah satu perintah di rantai pipe (`|`) gagal, bukan hanya perintah terakhir.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Penggunaan `chmod 777` untuk Menyelesaikan "Permission Denied"
* **Salah**: Mengeksekusi `chmod -R 777 /var/www/data` saat service web server gagal membaca direktori.
* **Dampak**: Membuka celah keamanan katastropik. Setiap user lokal atau proses yang terkompromi dapat mengubah, menyisipkan shell injection, atau menghapus file sistem tersebut.
* **Solusi**: Analisis kepemilikan user context (`ps aux | grep nginx`) lalu sesuaikan ownership ke user yang benar (`chown -R www-data:www-data /var/www/data`) dengan izin minimal yang aman (`find . -type d -exec chmod 755 {} \;` dan `find . -type f -exec chmod 644 {} \;`).

### 2. Mengabaikan Exit Code Pipeline
* **Salah**: 
  ```bash
  cat application.log | grep "CRITICAL ERROR" | awk '{print $2}'
  # Script menganggap langkah di atas sukses karena awk mengembalikan exit code 0, 
  # padahal perintah grep gagal (menghasilkan exit code 1)!
  ```
* **Solusi**: Aktifkan flag `set -o pipefail` agar sub-shell mengenali kegagalan pada komponen awal pipeline.

### 3. Menggunakan `kill -9` (`SIGKILL`) Sebagai Solusi Pertama
* **Salah**: Langsung menjalankan `kill -9 <PID>` ketika sebuah daemon terlihat lambat atau unresponsive.
* **Dampak**: Kernel langsung mencabut memori proses tanpa memberi kesempatan proses untuk flush buffers ke disk atau menutup active socket.
* **Solusi**: Selalu mulai dengan `kill -15 <PID>` (`SIGTERM`). Berikan waktu transisi, lalu periksa apakah proses sudah terminasi. Jika dan hanya jika proses tidak merespons dalam jangka waktu toleransi, lakukan eskalasi ke `kill -9`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Lab
Anda bertugas sebagai System Administrator & DevOps Engineer di sebuah perusahaan e-commerce. Anda diberikan mesin server Ubuntu Linux 22.04 LTS yang mengalami anomali resource and permission misconfigurations.

### Tugas 1: Investigasi dan Mitigasi Proses Menggantung (Easy)
1. Jalankan proses sleep panjang di background: `sleep 10000 &`.
2. Dapatkan PID dari proses tersebut menggunakan utility `pgrep` atau kombinasi `ps aux | grep sleep`.
3. Kirimkan sinyal terminasi standar yang anggun (`SIGTERM`). Pastikan proses telah dibersihkan sepenuhnya dari process table menggunakan `ps`.

### Tugas 2: Pemulihan File Permission & Ownership (Medium)
1. Buat hierarki direktori simulasi:
   ```bash
   sudo mkdir -p /opt/finance-app/secure_data
   sudo touch /opt/finance-app/secure_data/transactions.db
   ```
2. Buat dedicated system user dan group bernama `finops`:
   ```bash
   sudo useradd -r -s /usr/sbin/nologin finops
   ```
3. Konfigurasikan permission sehingga:
   * Direktori `/opt/finance-app` hanya dapat dibaca, ditulisi, dan dieksekusi oleh user `finops` dan group `finops`.
   * User lain selain `root` tidak memiliki izin sama sekali (`0700` atau `0770`).
   * Verifikasi menggunakan testing impersonation:
     ```bash
     sudo -u finops test -r /opt/finance-app/secure_data/transactions.db && echo "Akses Diberikan"
     ```

### Tugas 3: Menangani Zombie Process Melalui Systemd (Hard)
1. Tulis sebuah script Python `/usr/local/bin/zombie_maker.py` yang memanggil `os.fork()`, di mana child process langsung exit tetapi parent process melakukan `time.sleep(60)` tanpa memanggil `os.wait()`.
2. Buat Systemd service unit `/etc/systemd/system/zombie-monitor.service` untuk menjalankan script tersebut.
3. Amati status proses menggunakan command `ps aux | grep -E 'Z|defunct'`.
4. Implementasikan konfigurasi Systemd yang tepat atau update script untuk menjamin child process segera dibersihkan saat terminasi tanpa meninggalkan zombie state.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan berikut secara mandiri untuk menguji pemahaman Anda:

1. **Apa perbedaan mendasar antara kernel space dan user space dalam arsitektur x86_64 OS?**
   * A. User space mengeksekusi hardware instructions langsung, Kernel space memanipulasi network socket.
   * B. Kernel space berjalan di Ring 0 dengan akses langsung ke hardware dan memori fisik; User space di Ring 3 dengan akses terbatas melalui System Calls.
   * C. Kernel space adalah ruang untuk virtual memory, User space untuk physical memory.
   * D. Tidak ada perbedaan, pembagian ini hanya konvensi penamaan folder di Linux.

2. **File descriptor berapakah yang dialokasikan Linux secara default untuk Standard Error (`stderr`)?**
   * A. 0
   * B. 1
   * C. 2
   * D. 3

3. **Mengapa kernel Linux tidak mengizinkan sinyal `SIGKILL` (9) untuk ditangkap (*intercept*) atau diabaikan oleh kode aplikasi?**
   * A. Karena SIGKILL ditangani oleh Network Layer.
   * B. Agar sistem administrator selalu memiliki kontrol absolut untuk menghentikan proses yang rusak/malicious tanpa blokade program.
   * C. Sinyal SIGKILL selalu ditransformasikan menjadi SIGTERM secara otomatis.
   * D. Karena kode sumber Linux membatasi ukuran bit payload sinyal 9.

4. **Direktori FHS manakah yang merupakan pseudo-filesystem yang merefleksikan internal state kernel langsung dari RAM dan berukuran 0 byte di hard disk?**
   * A. `/var`
   * B. `/opt`
   * C. `/etc`
   * D. `/proc`

5. **Apa fungsi dari directive `NoNewPrivileges=true` pada file unit Systemd?**
   * A. Mencegah child process mendapatkan hak akses lebih tinggi daripada induknya (misalnya melalui binary berstatus SUID).
   * B. Menonaktifkan user login SSH.
   * C. Menghapus hak akses group wheel/sudo secara temporer.
   * D. Menginstruksikan kernel untuk me-restart service jika penggunaan memori melebihi batas.

---

### Kunci Jawaban & Rubrik Penilaian

* **Kunci Jawaban**:
  1. **B** — Kernel space beroperasi pada privilege level paling tinggi (Ring 0) dengan kontrol total ke perangkat keras.
  2. **C** — Default file descriptors: 0 = Stdin, 1 = Stdout, 2 = Stderr.
  3. **B** — SIGKILL dan SIGSTOP sengaja didesain kebal dari penangkapan program (`uncatchable`) untuk menjamin OS operator dapat mematikan proses apa pun.
  4. **D** — `/proc` (bersama `/sys`) adalah virtual memory filesystem yang di-generate langsung oleh kernel secara dinamis.
  5. **A** — `NoNewPrivileges=true` memastikan proses dan turunannya tidak dapat melakukan privilege escalation via tools seperti `sudo` atau bit SUID (`chmod +s`).

* **Rubrik Penilaian Mandiri**:
  * **5/5 Benar**: *Mastery*. Pemahaman teoritis arsitektur sistem operasi Anda telah solid. Anda siap melangkah ke manipulasi Shell Scripting tingkat lanjut.
  * **3–4 Benar**: *Proficient*. Anda memahami konsep umum, namun perlu meninjau kembali abstraksi tingkat rendah seperti syscalls dan security context.
  * **< 3 Benar**: *Needs Review*. Buka kembali Seksi 05 dan Seksi 06. Disarankan untuk mempraktikkan langsung interaksi CLI di terminal Linux.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku & Manual Standar Industri**:
   * *The Linux Programming Interface* oleh Michael Kerrisk (No Starch Press) — Referensi komprehensif arsitektur Linux API dan System Calls.
   * *UNIX and Linux System Administration Handbook (5th Edition)* oleh Evi Nemeth, et al.
2. **Dokumentasi Resmi & Kernel Tree**:
   * [Linux Filesystem Hierarchy Standard (FHS) 3.0 Documentation](https://refspecs.linuxfoundation.org/FHS_3.0/fhs-3.0.html)
   * [Systemd System and Service Manager Manuals (systemd.service)](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
   * Linux Manual Pages: `man 2 syscalls`, `man 7 signal`, `man 5 proc`.
3. **Repository Otentik & Lab Guide**:
   * [Linux Kernel Source Tree (GitHub Mirror)](https://github.com/torvalds/linux)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Linux terbagi secara rigid antara **Kernel Space** (kontrol hardware, Ring 0) dan **User Space** (aplikasi, Ring 3) yang dihubungkan melalui jembatan **System Calls**.
* Filosofi "*Everything is a file*" direalisasikan melalui abstraksi **Virtual Filesystem (VFS)**, di mana resource hardware, socket jaringan, dan status kernel dapat dibaca melalui file system semu (`/proc` dan `/sys`).
* Hirarki sistem file Linux distandarisasi lewat **FHS**: `/etc` untuk file konfigurasi, `/var` untuk dynamic state/log, dan `/opt` untuk third-party packages.
* Seluruh proses diturunkan dari **PID 1** (`systemd`) melalui mekanisme **`fork()`** (duplikasi) dan **`execve()`** (substitusi program).
* Sinyal POSIX mengatur alur komunikasi asinkron proses. DevOps engineer wajib memprioritaskan `SIGTERM` (15) untuk memberikan waktu aplikasi membersihkan resource sebelum melakukan intervensi keras dengan `SIGKILL` (9).
* Modern background service harus dibungkus menggunakan file **Systemd Unit** yang menerapkan prinsip keamanan *Least Privilege* serta pembatasan kapasitas komputasi (*cgroups*).

---

## SEKSI 17 — GLOSARIUM

* **Cgroups (Control Groups)**: Fitur kernel Linux yang membatasi, mencatat, dan mengisolasi penggunaan resource (CPU, memory, disk I/O, network) dari sekumpulan proses.
* **File Descriptor (FD)**: Indeks integer abstrak yang digunakan kernel untuk melacak file, socket, atau pipa (pipe) yang dibuka oleh proses tertentu.
* **FHS (Filesystem Hierarchy Standard)**: Spesifikasi formal yang mendefinisikan lokasi direktori utama beserta fungsinya pada sistem operasi mirip Unix.
* **Inodes (Index Nodes)**: Struktur data pada filesystem Unix yang menyimpan metadata tentang suatu file (ukuran, permission, lokasi block disk) kecuali nama file dan datanya langsung.
* **Orphan Process**: Child process yang parent process-nya telah mati terlebih dahulu; child ini secara otomatis di-adopt oleh init system (PID 1).
* **System Call (Syscall)**: Permintaan terprogram oleh user-space program kepada kernel Linux untuk layanan privileged (e.g., membaca disk, membuat network socket).
* **Zombie Process**: Proses yang telah menghentikan eksekusinya (`exit()`), namun metadata task struct-nya masih tercatat di RAM karena parent process belum memanggil `wait()` untuk membaca return status-nya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan**:
  * Banyak peserta pemula bingung membedakan antara file binary aplikasi dan sebuah running process. Tunjukkan secara visual proses transisi dari disk image menjadi process allocation di `/proc`.
  * Saat sesi lab, tekankan bahwa troubleshooting kontainer (seperti Docker) menggunakan 100% prinsip modul ini. Ingatkan peserta: "Jika Anda memahami Linux OS, tidak ada sihir hitam di balik Docker/Kubernetes."
* **Mitigasi Kesulitan Peserta**:
  * Konsep `fork()` dan `exec()` sering membingungkan peserta yang tidak berlatar belakang Computer Science. Gunakan analogi: `fork()` adalah memfotokopi blueprint kerja, `exec()` adalah melempar lembaran fotokopi tersebut dan menggantinya dengan buku tugas yang benar-benar baru.
* **Setup Lab Lingkungan**:
  * Pastikan peserta tidak menggunakan akun `root` langsung saat mengerjakan hands-on. Sediakan environment virtual machine berbasis Ubuntu 22.04 LTS atau Rocky Linux 9 dengan user biasa yang memiliki hak akses `sudo`.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: `1.0.0`
* **Tanggal Rilis**: 2026-03-30
* **Perubahan**:
  * Rilis inisial materi Arsitektur Linux, FHS, dan Manajemen Proses Tingkat Lanjut.
  * Penambahan skema diagram ASCII untuk transisi state proses dan relasi VFS.
  * Standardisasi penulisan systemd hardening unit file berbasis Cgroups v2.
* **Maintainer**: DevOps Core Technical Curriculum Council

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CORE-FND-0102: Konsep Dasar Jaringan Komputer, Topologi, dan Model OSI/TCP-IP`
* **Modul Saat Ini**: `CORE-FND-0201: Arsitektur Sistem Operasi Linux, Filesystem Hierarchy Standard, dan Manajemen Proses`
* **Modul Berikutnya**: `CORE-FND-0202: Otomasi Shell Scripting Tingkat Lanjut, I/O Redirection, dan Defensive Bash Programming`