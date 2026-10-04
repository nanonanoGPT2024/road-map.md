# Bab 01: Fondasi Sistem Operasi Linux
## Modul 01: Arsitektur Kernel Linux, Ruang Eksekusi, dan Model Proses Shell

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** transisi konteks eksekusi CPU antara *User Space* (Ring 3) dan *Kernel Space* (Ring 0) melalui mekanisme *System Call* (syscall).
- **Menelusuri** siklus hidup proses di Linux melalui implementasi syscall primitif (`clone`, `fork`, `execve`, `wait4`, `exit_group`).
- **Mengonfigurasi** dan mengelola abstraksi aliran I/O standar (*Standard Streams*) serta manipulasi *File Descriptors* (FD) langsung pada *shell*.
- **Mendiagnosis** anomali proses (zombie, orphan, resource exhaustion) menggunakan antarmuka semu `/proc` dan utilitas inspeksi kernel runtime.

---

### 2. Introduction & Concept
Sistem operasi Linux mengadopsi arsitektur *monolithic kernel with dynamic modularity*. Secara konseptual, sistem operasi memisahkan memori dan instruksi perangkat keras menjadi dua domain proteksi utama berdasarkan kapabilitas CPU:
1. **User Space (Ring 3 pada x86-64):** Lingkungan eksekusi unprivileged tempat seluruh aplikasi pengguna, daemon, dan shell beroperasi. Proses di sini tidak memiliki akses langsung ke perangkat keras maupun memori kernel.
2. **Kernel Space (Ring 0 pada x86-64):** Lingkungan eksekusi privileged tempat kode inti kernel, scheduler, memory management, jaringan, dan driver perangkat keras dieksekusi secara native.

Jembatan komunikasi tunggal yang menghubungkan kedua ranah ini adalah **System Call Interface (SCI)**. Setiap interaksi eksternal—seperti alokasi memori, penulisan ke disk, komunikasi soket, atau penciptaan proses—wajib melalui interupsi perangkat lunak atau instruksi CPU khusus (`syscall` pada x86-64) untuk mengalihkan eksekusi ke Kernel Space.

---

### 3. Why It Matters
Dalam arsitektur *production-grade*, ketidaktahuan atas batas *User/Kernel space* dan model proses shell menyebabkan:
- **Latensi Tak Terduga (Context Switching Overhead):** Panggilan sistem yang berlebihan (misal: I/O *unbuffered* baris demi baris) memicu degradasi performa drastis akibat *CPU context switch* dan *cache invalidation*.
- **Eksploitasi Privilese & Container Breakout:** Kontainer Linux (Docker/Kubernetes) bukan VM; mereka berbagi kernel host yang sama. Kesalahan pemahaman batas proteksi ini memicu eksploitasi eskalasi privilese via modul kernel cacat atau celah unprivileged namespaces.
- **Incident Outage Skala Besar:** Ketidakmampuan shell script menangani sinyal kernel (`SIGTERM`, `SIGCHLD`) memicu penumpukan proses zombie, kebocoran file descriptor (`EMFILE`), hingga kehabisan PID (*PID exhaustion*) yang menumbangkan seluruh node server.

---

### 4. What: Definisi dan Komponen Inti

#### 4.1 CPU Ring Protection
Arsitektur prosesor modern menyediakan cincin proteksi hierarkis:
- **Ring 0 (Supervisor Mode):** Akses penuh ke seluruh instruksi CPU, register kontrol (CR0–CR4), dan pemetaan alamat fisik memori.
- **Ring 3 (User Mode):** Set instruksi terbatas. Instruksi berbahaya seperti manipulasi MMU (*Memory Management Unit*) atau interupsi dinonaktifkan.

#### 4.2 System Call Boundary
Ketika proses di User Space membutuhkan layanan kernel, proses mengeksekusi instruksi assembly `syscall`. CPU menyimpan register proses saat ini, menaikkan tingkat hak akses ke Ring 0, dan memindahkan eksekusi ke tabel vektor interupsi kernel (`sys_call_table`).

```
[ User Program ] ---> Pustaka C (glibc) ---> syscall instruction
                                                    |
                                      [ Ring Boundary: Trap/Interrupt ]
                                                    v
[ Kernel Space ] ---> sys_call_table ---> VFS / Memory / Scheduler
```

#### 4.3 Virtual File System (VFS) dan File Descriptors (FD)
Di Linux, prinsip fundamental Unix berlaku: *"Everything is a file"*. VFS adalah lapisan abstraksi yang memungkinkan sistem file yang berbeda (ext4, XFS, NFS, Btrfs) diakses melalui antarmuka panggilan sistem seragam (`open`, `read`, `write`, `close`).

Setiap proses memegang tabel penunjuk independen yang disebut **File Descriptor Table**:
- `0`: Standard Input (`stdin`)
- `1`: Standard Output (`stdout`)
- `2`: Standard Error (`stderr`)
- `3+`: Alokasi dinamis untuk file reguler, socket jaringan, pipe, dan device node.

#### 4.4 Model Eksekusi Shell (POSIX Process Lifecycle)
Ketika perintah dieksekusi di shell (misalnya `ls`):
1. **`fork()` / `clone()`:** Shell menduplikasi dirinya sendiri. Proses baru dibuat sebagai *child process* dengan PID baru, mewarisi memori dan file descriptors dari *parent process*.
2. **`execve()`:** Pada ruang memori anak, sistem mengganti *address space*, kode, stack, dan heap dengan binary baru (`/bin/ls`).
3. **`wait4()`:** Shell (induk) menangguhkan eksekusi dirinya sampai proses anak selesai mengembalikan status keluar (*exit code*).

---

### 5. How: Prosedur Analisis Runtime Kernel & Shell

#### Langkah 1: Menginspeksi Kernel Runtime & Versi Arsitektur
Jalankan perintah berikut untuk memeriksa build kernel dan arsitektur CPU:
```bash
uname -a
cat /proc/version
```

#### Langkah 2: Memverifikasi Alokasi File Descriptor Proses
Identifikasi PID proses shell Anda saat ini, lalu lacak tabel FD-nya:
```bash
echo $$
# Misalkan PID adalah 14502
ls -la /proc/$$/fd
```
*Output memvalidasi asosiasi FD 0, 1, dan 2 ke pseudo-terminal (`/dev/pts/X`).*

#### Langkah 3: Menelusuri System Call Eksekusi Perintah
Gunakan `strace` untuk merekam transisi Ring 3 ke Ring 0:
```bash
strace -f -e trace=clone,execve,write,exit_group /bin/echo "Production Test"
```

---

### 6. Architecture Diagram: Linux Execution & Shell Process Spawning

Berikut adalah peta alur pemanggilan proses shell dan pergeseran konteks hak akses hardware:

```
+-------------------------------------------------------------------------------+
| USER SPACE (Ring 3 - Unprivileged)                                           |
|                                                                               |
|  +----------------+    fork()/clone()    +------------------+                 |
|  |  Bash Shell    | -------------------> |  Child Process   |                 |
|  |  (PID: 1000)   |                      |  (PID: 1001)     |                 |
|  +----------------+                      +------------------+                 |
|         ^                                         |                           |
|         | wait4()                                 | execve("/bin/grep")       |
|         |                                         v                           |
|         |                                +------------------+                 |
|         |                                | Active Binary    |                 |
|         |                                | (grep logic)     |                 |
|         |                                +------------------+                 |
|         |                                         |                           |
|         |                                         | write(fd: 1, buf, len)    |
+---------|-----------------------------------------|---------------------------+
| HARDWARE INTERRUPT / SYSCALL TRAP BOUNDARY        |                           |
+---------|-----------------------------------------|---------------------------+
| KERNEL SPACE (Ring 0 - Privileged)                v                           |
|                                          +------------------+                 |
|                                          | System Call Table|                 |
|                                          | (sys_write)      |                 |
|                                          +------------------+                 |
|                                                   |                           |
|         +--------------------+                    v                           |
|         | Process Scheduler  |           +------------------+                 |
|         | (EEVDF / CFS)      |           | VFS & TTY Driver |                 |
|         +--------------------+           +------------------+                 |
|                   |                               |                           |
+-------------------|-------------------------------|---------------------------+
| HARDWARE LAYER    v                               v                           |
|  +-------------------------------------------------------------------------+  |
|  |                   CPU Registers, MMU, Physical RAM, Terminal            |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

---

### 7. Simple Example: Analisis Redirection & File Descriptors

Memahami I/O redirection tingkat rendah menggunakan bash shell:

```bash
# 1. Alihkan Standard Output (FD 1) ke file data.log
echo "Log Entry 1" 1> data.log

# 2. Alihkan Standard Error (FD 2) ke file terpisah
ls /jalur/tidak/ada 2> error.log

# 3. Alokasi Custom File Descriptor (FD 3) untuk read-write
exec 3<> custom_stream.tmp

# 4. Tulis langsung ke FD 3
echo "Data dialirkan via FD 3" >&3

# 5. Baca data dari FD 3
cat <&3

# 6. Tutup FD 3
exec 3>&-
```

**Penjelasan:**
Sintaks `exec 3<>` mengubah struktur `task_struct` internal proses bash saat ini, mengalokasikan slot indeks `3` pada FD Table yang menunjuk langsung ke *inode* file `custom_stream.tmp`. Operasi `exec 3>&-` mengirimkan syscall `close(3)` ke kernel.

---

### 8. Practical Example: Tracing Degradasi I/O Proses Produksi

Skenario: Sebuah daemon background mengalami lonjakan penggunaan CPU tanpa utilisasi memori yang signifikan. Kita akan mendiagnosis apakah proses terhenti di *User Space* atau *Kernel Space* via pelacakan syscall.

```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET_PROC="node"
PID=$(pgrep -f "${TARGET_PROC}" | head -n 1)

if [[ -z "${PID}" ]]; then
    echo "ERROR: Proses ${TARGET_PROC} tidak terdeteksi." >&2
    exit 1
fi

echo "=== Memulai Analisis Profiling Syscall untuk PID: ${PID} ==="

# 1. Agregasi statistik syscall selama 10 detik
strace -p "${PID}" -c -w -S time sleep 10

# 2. Audit distribusi waktu eksekusi (User vs System CPU time)
ps -p "${PID}" -o pid,user,%cpu,%mem,time,cputime,etime

# 3. Periksa status context switches non-voluntary (indikasi thread contention)
grep -E 'voluntary_ctxt_switches|nonvoluntary_ctxt_switches' "/proc/${PID}/status"

# 4. Periksa batas limit file descriptors
cat "/proc/${PID}/limits" | grep -E 'Max open files|Max processes'
```

**Interpretasi Data:**
- Jika `%sys` pada output CPU tinggi dan `strace -c` didominasi oleh syscall `futex` atau `epoll_wait`, *bottleneck* terjadi akibat lock contention di dalam kernel, bukan komputasi internal program di User Space.

---

### 9. Implementation Strategy: Standardisasi Kernel Param & Process Limits

Penerapan konfigurasi kernel dasar untuk sistem Linux berkapasitas beban tinggi (high-throughput production).

#### Fase 1: Pra-syarat
- Akses root (`sudo`).
- Utilitas terinstal: `sysctl`, `procps`.

#### Fase 2: Rollout Konfigurasi Kernel Param (`/etc/sysctl.d/99-production-core.conf`)
```ini
# Perbesar kapasitas pelacakan thread & proses
kernel.pid_max = 4194304

# Batasi penggunaan swapping agresif untuk menjaga stabilitas memori
vm.swappiness = 10

# Perbesar kapasitas tabel alokasi global File Descriptors
fs.file-max = 2097152

# Proteksi crash: batasi alokasi ruang memori berlebih
vm.overcommit_memory = 1
```

Aktivasi konfigurasi runtime:
```bash
sudo sysctl --system
```

#### Fase 3: Rencana Rollback
Jika terjadi instabilitas sistem, kembalikan parameter ke default bawaan distro:
```bash
sudo rm -f /etc/sysctl.d/99-production-core.conf
sudo sysctl --system
```

---

### 10. Verification Steps

Jalankan perintah pengujian deterministik berikut untuk memverifikasi kepatuhan arsitektural:

```bash
# Validasi bahwa limit process descriptors aktif
CURRENT_PID_MAX=$(sysctl -n kernel.pid_max)
if [[ "${CURRENT_PID_MAX}" -eq 4194304 ]]; then
    echo "PASS: kernel.pid_max telah tervalidasi (${CURRENT_PID_MAX})."
else
    echo "FAIL: kernel.pid_max tidak sesuai target." >&2
    exit 1
fi

# Validasi penanganan Signal pada Bash
trap 'echo "PASS: SIGINT dicegat."' SIGINT
kill -SIGINT $$
trap - SIGINT
```

---

### 11. Trade-offs: Monolithic Kernel vs Microkernel & Subshell Execution

| Parameter | Monolithic Kernel (Linux) | Microkernel (seL4, Mach, QNX) |
| :--- | :--- | :--- |
| **Kinerja Syscall** | **Tinggi:** Drivers & FS berada di Ring 0; minimal context switch overhead. | **Rendah:** Driver berjalan di Ring 3; membutuhkan IPC intensif melintasi boundary. |
| **Blast Radius** | **Tinggi:** Kernel panic pada modul/driver merusak seluruh OS. | **Rendah:** Crash pada driver hanya mematikan sub-komponen proses bersangkutan. |
| **Kompleksitas Desain** | **Tinggi:** Jutaan baris kode berjalan di tingkat privilese tertinggi. | **Rendah:** Kode inti kernel minimalis dan terverifikasi secara matematis. |

| Model Shell Execution | Fork & Exec (Subshell: `(...)` ) | In-Process Execution (Source / Function) |
| :--- | :--- | :--- |
| **Resource Overhead** | Tinggi (Membuat page table baru, duplikasi state via Copy-on-Write). | Minimal (Berjalan di stack frame memori shell yang sama). |
| **Isolasi State** | Sempurna (Variabel lingkungan tidak mencemari parent). | Tidak ada isolasi (State parent shell rentan ter-overwrite). |

---

### 12. Best Practices

#### Hal yang WAJIB Dilakukan (DOs)
- **Gunakan `exec` untuk eksekusi container entrypoint:** Gunakan `exec binary` pada akhir script entrypoint Docker/OCI agar aplikasi langsung menduduki PID 1, menjamin propagasi sinyal `SIGTERM` kernel langsung diterima aplikasi.
- **Pembersihan Resource FD:** Selalu tutup *custom file descriptors* segera setelah aliran data selesai (`exec 3>&-`).
- **Verifikasi Exit Code:** Selalu evaluasi variabel `$?` atau aktifkan `set -e` guna mencegah propagasi eksekusi saat child process mengalami kegagalan fatal.

#### Hal yang DILARANG (DON'Ts)
- **Dilarang memicu Subshell dalam Loop Intensif:** Hindari parsing teks jutaan baris menggunakan `while read line; do echo $(echo $line | awk ...); done`. Pola ini memicu ribuan syscall `fork()` dan `execve()` per detik yang membebani CPU scheduler.
- **Dilarang Mengabaikan `SIGCHLD`:** Membiarkan child process mati tanpa pembacaan status oleh parent via `wait()` memicu kebocoran memori tabel proses (*Zombie explosion*).

---

### 13. Common Failure Modes & Debugging

#### Kasus A: Zombie Process Accumulation
- **Gejala:** Muncul status `Z` atau `defunct` pada perintah `ps aux`.
- **Mekanisme Akar Masalah:** Child process telah selesai mengeksekusi instruksi dan memanggil `exit_group()`. Kernel mempertahankan struktur `task_struct` miliknya agar parent dapat membaca *exit code*. Jika parent menolak mengeksekusi `wait4()`, entri PID tersebut tidak dapat dibebaskan dari memori kernel.
- **Solusi:** Kirim sinyal `SIGCHLD` ke parent process untuk memaksanya membaca tabel anak, atau hentikan parent process secara langsung (`SIGTERM`/`SIGKILL`) sehingga anak-anak zombie diadopsi oleh init system (PID 1) yang secara otomatis akan membersihkannya (*reaping*).

```bash
# Identifikasi Parent PID (PPID) dari proses zombie
ps -ef | grep defunct
# Berikan sinyal SIGCHLD ke Parent PID
kill -s SIGCHLD <PPID>
```

#### Kasus B: File Descriptor Exhaustion (`EMFILE` / `ENFILE`)
- **Gejala:** Aplikasi memunculkan log error `Too many open files`.
- **Mekanisme Akar Masalah:** Proses mencapai batas per-proses (`ulimit -n`) atau sistem melampaui batas kernel (`fs.file-max`).
- **Solusi:** Deteksi proses yang menahan FD terbanyak:
```bash
lsof -n | awk '{print $1, $2}' | sort | uniq -c | sort -nr | head -n 10
```

---

### 14. Performance Considerations

1. **Cost of Context Switch:** Transisi dari User Space (Ring 3) ke Kernel Space (Ring 0) dan sebaliknya memerlukan pemuatan ulang register CPU, manipulasi stack pointer, dan pembersihan register TLB (*Translation Lookaside Buffer*). Minimalisir frekuensi syscall via I/O Buffering di User Space.
2. **vDSO (Virtual Dynamic Shared Object):** Untuk syscall yang sangat sering dipanggil tetapi tidak mengubah state hardware (contoh: `gettimeofday`, `clock_gettime`), kernel Linux memetakan halaman memori kernel langsung ke User Space secara read-only. Eksekusi ini berjalan sepenuhnya di Ring 3 tanpa penalti context switch. Pastikan pustaka aplikasi menggunakan vDSO secara optimal.

---

### 15. Security Considerations

- **SUID/SGID Binaries Privilege Escalation:** File dengan bit SUID (`chmod u+s`) dieksekusi dengan privilese pemilik file (umumnya root), terlepas dari siapa pengguna yang menjalankannya di Ring 3. Batasi file SUID dan audit secara periodik:
  ```bash
  find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -exec ls -la {} \;
  ```
- **Seccomp (Secure Computing Mode):** Manfaatkan Seccomp BPF untuk memblokir syscall berbahaya pada level kernel bagi aplikasi publik (misal: memblokir syscall `ptrace` atau `reboot` pada aplikasi berbasis web).

---

### 16. Scalability Characteristics

- **PID Scale Constraints:** Nilai default `kernel.pid_max` historis (32,768) membatasi jumlah total proses/thread yang dapat hidup bersamaan pada sistem multi-core skala besar. Untuk node komputasi dengan ribuan thread, nilai ini wajib ditingkatkan hingga `4194304` guna mencegah kegagalan alokasi proses (`fork: Resource temporarily unavailable`).
- **Scheduler Scalability:** Kernel Linux modern mengimplementasikan scheduler **EEVDF** (*Earliest Eligible Virtual Deadline First*, menggantikan CFS sejak kernel 6.6) dengan kompleksitas waktu $O(\log N)$ berbasis *Red-Black Tree*, menjamin performa distribusi waktu CPU tetap konstan meskipun menangani jutaan thread.

---

### 17. Real-world Scenario: Post-Mortem Node Hang akibat Orphan Pod

#### 1. Ringkasan Insiden
Node worker Kubernetes tiba-tiba berhenti merespons perintah scheduling (`NodeNotReady`). Perintah SSH ke node membutuhkan waktu 30 detik untuk sekadar memunculkan prompt shell.

#### 2. Root Cause Analysis (RCA)
- Sebuah container microservice menjalankan aplikasi via wrapper script bash:
  `ENTRYPOINT ["/bin/sh", "-c", "python app.py"]`
- Bash berjalan sebagai PID 1 di dalam namespace kontainer. Ketika pod dihentikan, kernel mengirimkan sinyal `SIGTERM` hanya ke bash. Bash tidak mempropagasi sinyal tersebut ke proses anak (`python`).
- Python terus berjalan, dan saat bash mati paksa via `SIGKILL` dari Kubernetes, Python menjadi orphan dan terus memproduksi thread tanpa kendali hingga menghabiskan alokasi PID kernel pada host node (`kernel.pid_max` tercapai).
- Kernel host tidak lagi mampu mengeksekusi syscall `clone()` untuk proses baru, memblokir kubelet dan antarmuka otentikasi SSH.

#### 3. Tindakan Remediasi
- Mengubah spesifikasi Dockerfile menggunakan eksekusi langsung tanpa subshell intermediary:
  `ENTRYPOINT ["python", "app.py"]`
  atau menyematkan init system minimalis seperti `tini` / `dumb-init`:
  `ENTRYPOINT ["/usr/bin/tini", "--", "python", "app.py"]`
- Mengonfigurasi `PID limits` pada level cgroup container runtime untuk mencegah satu container menghabiskan resource pool seluruh OS.

---

### 18. Knowledge Check

**1. Apa implikasi mendasar pada CPU register ketika sebuah program mengeksekusi instruksi `syscall`?**
*A.* Program beralih mengeksekusi memori swap.
*B.* CPU beralih dari Ring 3 ke Ring 0, menyimpan Program Counter (PC), dan memuat pointer instruksi kernel dari tabel interupsi.
*C.* Proses shell langsung dimatikan dan digantikan oleh PID 1.
*D.* CPU secara otomatis mengosongkan seluruh isi RAM fisik untuk proteksi isolasi.
*E.* Status file descriptor langsung ditutup seketika.

*Rasional Jawaban:* B benar. `syscall` mengeksekusi transisi level privilese hardware (Privilege Escalation Terkontrol), menyimpan konteks eksekusi User Space (Instruction Pointer, General Purpose Registers), dan melompat ke entry point penangan syscall kernel.

---

**2. Mengapa eksekusi loop bash berikut menyebabkan degradasi performa I/O yang masif?**
```bash
while IFS= read -r line; do
  echo "$line" | grep "ERROR" >> filtered.log
done < access.log
```
*A.* Variabel IFS merusak struktur direktori `/proc`.
*B.* Akses read-only pada `access.log` dilarang oleh kernel.
*C.* Shell mengeksekusi syscall `fork()`, `clone()`, dan `execve()` baru pada setiap baris file untuk memanggil utilitas `grep`.
*D.* File `filtered.log` otomatis beralih menjadi device node di Ring 0.
*E.* Nilai context switch dipaksa turun hingga 0 secara hardware.

*Rasional Jawaban:* C benar. Memanggil utilitas binary eksternal seperti `grep` di dalam perulangan mengeksekusi penciptaan proses baru secara berulang untuk setiap baris input, yang memicu ribuan context switch dan pembebanan siklus CPU secara masif.

---

**3. Sebuah proses anak menyelesaikan tugasnya sebelum proses induk mengeksekusi `wait4()`. Dalam kondisi ini, status proses anak di mata kernel adalah:**
*A.* Orphan process yang langsung diadopsi oleh init.
*B.* Daemon process yang dialihkan ke background execution.
*C.* Melakukan dump memory ke `/var/log/core`.
*D.* Zombie process yang mempertahankan alokasi di tabel proses kernel (`task_struct`).
*E.* Terhapus permanen dari memori tanpa sisa meta-data.

*Rasional Jawaban:* D benar. Kernel mempertahankan struktur metadata proses (PID, status keluar, statistik penggunaan resource) di dalam `task_struct` hingga proses parent memanggil syscall `wait()` untuk mengambil data tersebut.

---

### 19. Reference Implementation: Enterprise Process Wrapper Script

Script produksi di bawah ini mengimplementasikan manipulasi file descriptor tingkat rendah, penanganan sinyal kernel yang tepat, serta eksekusi yang ramah terhadap PID namespace (POSIX compliant).

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name   : process_supervisor.sh
# Description   : Enterprise execution wrapper dengan signal traps dan custom FDs
# Standard      : POSIX / Shellcheck compliant
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail

# Deklarasi direktori kerja dan file log
readonly WORK_DIR="/tmp/process_supervisor"
readonly LOG_FILE="${WORK_DIR}/engine.log"
readonly ERR_FILE="${WORK_DIR}/engine.err"

mkdir -p "${WORK_DIR}"

# Alokasikan Custom File Descriptor 3 & 4 untuk logging terisolasi
exec 3>> "${LOG_FILE}"
exec 4>> "${ERR_FILE}"

log_info() {
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    printf "[%s] [INFO] [PID:%d]: %s\n" "${timestamp}" "$$" "$1" >&3
}

log_error() {
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    printf "[%s] [ERROR] [PID:%d]: %s\n" "${timestamp}" "$$" "$1" >&4
}

# Cleanup Handler untuk menjamin pelepasan Resource Kernel
cleanup() {
    local exit_code=$?
    log_info "Menerima sinyal terminasi/exit. Memulai pembersihan resource..."

    # Tutup custom file descriptors
    exec 3>&- || true
    exec 4>&- || true

    log_info "Proses pembersihan selesai. Status keluar: ${exit_code}"
    exit "${exit_code}"
}

# Trap sinyal kernel kritis untuk mengantisipasi Zombie/Orphanage
trap cleanup EXIT
trap 'log_error "Menerima SIGINT/SIGTERM. Menghentikan subproses..."; exit 143' SIGINT SIGTERM

log_info "Sistem supervisor aktif. Memeriksa limitasi sistem operasi..."

# Audit batasan FD sistem saat ini
MAX_FD=$(ulimit -n)
log_info "Konfigurasi alokasi FD maksimum untuk proses ini: ${MAX_FD}"

# Payload Operasional: Menjalankan eksekusi terisolasi
log_info "Menjalankan payload instruksi terisolasi..."

# Simulasi eksekusi background child process
(
    # Subshell mewarisi FD 3 dan FD 4
    printf "Subshell PID: %d aktif di bawah Parent PID: %d\n" "$$" "$PPID" >&3
    # Simulasi kerja
    sleep 2
) &

CHILD_PID=$!
log_info "Child process berhasil didaftarkan dengan PID: ${CHILD_PID}. Menunggu status..."

# Explicit wait untuk mencegah terciptanya zombie process
wait "${CHILD_PID}"
CHILD_STATUS=$?

if [[ "${CHILD_STATUS}" -eq 0 ]]; then
    log_info "Child process PID ${CHILD_PID} berhasil diselesaikan dengan sukses."
else
    log_error "Child process PID ${CHILD_PID} gagal dengan exit code: ${CHILD_STATUS}"
    exit "${CHILD_STATUS}"
fi

log_info "Semua tugas runtime selesai. Keluar secara normal."
exit 0
```

---

### 20. Summary & Next Steps

Modul ini telah membedah batas eksekusi antara User Space dan Kernel Space, siklus hidup proses melalui System Call primitif, manipulasi File Descriptors tingkat lanjut, serta pertimbangan performa dan keamanan pada tingkat kernel Linux.

Pondasi mekanistik ini menjadi prasyarat mutlak untuk modul berikutnya. Pada **Modul 02: Filesystem Hierarchy Standard (FHS), Manipulasi Inode, dan Alokasi Storage Tingkat Rendah**, kita akan menelusuri bagaimana kernel mengorganisasi struktur penyimpanan secara fisik, cara kerja hardlink/symlink pada layer metadata VFS, serta analisis *block-level storage*.