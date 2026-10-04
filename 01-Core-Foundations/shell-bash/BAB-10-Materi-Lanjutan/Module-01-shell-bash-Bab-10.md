## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul**: `MOD-BASH-10-01`
*   **Jalur Kurikulum**: `01-Core-Foundations`
*   **Mata Pelajaran**: `shell-bash`
*   **Bab**: 10 — Automasi Enterprise, Daemon & CI/CD
*   **Modul**: 01 — Rekayasa Daemon, Integrasi Systemd, dan Pipeline CI/CD Berbasis Bash
*   **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
*   **Prasyarat**: 
    *   Pemahaman mendalam tentang POSIX File Descriptors & I/O Redirection.
    *   Penguasaan sinyal UNIX/POSIX (`SIGTERM`, `SIGHUP`, `SIGINT`, `SIGCHLD`, `SIGKILL`).
    *   Manajemen proses Linux (`fork`, `exec`, PID namespaces, cgroups).
    *   Konstruksi skrip Bash modular (`set -Eeuo pipefail`, functions, scope variabel).
*   **Estimasi Waktu Penyelesaian**: 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis dan Mengimplementasikan Siklus Hidup Proses Daemon**: Merancang skrip Bash yang berjalan secara asinkron sebagai background service yang terisolasi dari controlling terminal (TTY), menangani sinyal sistemik secara elegan (*graceful shutdown*), dan mencegah terjadinya proses *zombie* atau *orphan*.
2.  **Mengintegrasikan Skrip Bash dengan Systemd Supervisor**: Menyusun unit file `systemd` (`.service`) tingkat produksi yang mengendalikan eksekusi skrip Bash, mencakup manajemen dependensi, restart policies, resource limits via cgroups v2, dan integrasi logging langsung ke `journald`.
3.  **Membangun Mekanisme Konkurensi Aman (Concurrency Locking)**: Mengimplementasikan mutual exclusion berbasis kernel menggunakan utilitas `flock` dan atomic file descriptor manipulation guna mencegah kondisi *race condition* pada eksekusi berskala enterprise.
4.  **Mengotomatisasi Eksekusi Pipeline CI/CD Non-Interaktif**: Mengembangkan skrip Bash yang beroperasi secara deterministik pada lingkungan headless (GitHub Actions, GitLab CI, Jenkins Runner), dengan penanganan variabel *environment*, *exit codes* terstandarisasi, dan pelaporan *failure context* secara atomik.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Enterprise Automation Architecture]
                                       |
        +------------------------------+------------------------------+
        |                                                             |
   [Daemonization & Systemd]                                [CI/CD Execution Plane]
        |                                                             |
        +--> Process Lifecycle (PID 1 vs Subshell)                    +--> Non-Interactive / Non-Login Shells
        +--> POSIX Signals (SIGTERM, SIGHUP, SIGCHLD)                 +--> Pipeline Determinism (set -Eeuo pipefail)
        +--> File Descriptor Detachment (/dev/null)                   +--> Secret Masking & Sensitive Leaks
        +--> Systemd Unit Contracts (Type=exec/simple)                +--> Idempotent Deployment Routines
        |                                                             |
        +------------------------------+------------------------------+
                                       |
                       [Kernel-Level Concurrency: flock]
                                       |
                          (Atomic Locking via FDs)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada skala enterprise, automasi tidak lagi sekadar mengeksekusi sekumpulan perintah secara sekuensial. Masalah mendasar muncul ketika skrip otomasi berhadapan dengan lingkungan produksi:

1.  **Kegagalan Penanganan State dan Sinyal**: Skrip yang dihentikan secara paksa oleh orkestrator (seperti Kubernetes atau systemd saat node drain) tanpa penanganan sinyal `SIGTERM` akan meninggalkan data korup, file lock yatim piatu (*orphaned locks*), atau koneksi database menggantung.
2.  **Kerapuhan Eksekusi CI/CD**: Sebagian besar skrip yang berjalan mulus di terminal lokal *developer* (karena ketersediaan TTY interaktif dan file konfigurasi login seperti `.bashrc`) gagal total saat dieksekusi di dalam runner CI/CD. Hal ini disebabkan oleh perbedaan mendasar lingkungan non-interactive, non-login shell, serta ketidakmampuan skrip mengembalikan *exit code* yang representatif terhadap kegagalan parsial (*subshell failures*).
3.  **Race Conditions pada Tugas Paralel**: Automasi yang dijalankan via cron atau webhook tanpa mekanisme *mutual exclusion* yang terverifikasi di level kernel berpotensi memicu tabrakan eksekusi multiproses terhadap resource yang sama.
4.  **Kurangnya Visibilitas Operasional**: Skrip yang tidak terintegrasi dengan subsistem logging Linux (`syslog`/`journald`) menyulitkan proses audit, tracing, dan telemetri kegagalan sistem.

Menguasai pola perancangan *daemon-ready* dan integrasi CI/CD menjadikan skrip Bash setara dengan komponen infrastruktur kelas enterprise: deterministik, terisolasi, resilien, dan mudah diawasi.

---

## SEKSI 05 — APA ITU (WHAT)

### Daemon
Secara tradisional di Linux, **daemon** adalah proses yang berjalan di latar belakang (*background*), tidak terikat secara langsung dengan sesi interaktif pengguna (*detached from controlling terminal*), dan terus hidup untuk melayani request atau memantau status sistem. 

Di era modern yang didominasi oleh `systemd` (PID 1), definisi dan tata cara pembuatan daemon telah berevolusi. Paradigma klasik yang memerlukan teknik *double-forking* dan manual detaching (via `nohup` atau `disown`) telah digantikan oleh pendekatan **supervised process**, di mana `systemd` bertindak sebagai *init system* yang mengelola lifecycle, cgroups, dan file descriptors dari proses tersebut secara transparan.

### Bash dalam Ekosistem CI/CD
Dalam konteks **CI/CD (Continuous Integration/Continuous Delivery)**, Bash bertindak sebagai *lingua franca* untuk mengeksekusi pipeline jobs. Eksekusi ini dilakukan oleh *Runner Agent* (seperti GitLab Runner atau GitHub Actions Runner) yang menjalankan shell dalam mode:
*   **Non-Interactive**: Tidak ada stdin TTY (`[ -t 0 ]` bernilai false), prompt `PS1` tidak dimuat, dan program tidak boleh menunggu interaksi pengguna.
*   **Non-Login**: File inisialisasi profil (`/etc/profile`, `~/.bash_profile`, `~/.bash_login`) dilewati, menyisakan lingkungan yang steril dengan variabel `$PATH` minimal.

Bash tingkat enterprise dalam konteks ini wajib bersifat **idempoten** (dapat dieksekusi berkali-kali dengan output state akhir yang konsisten) dan **deterministik** (memiliki aturan terminasi error yang ketat tanpa mengabaikan kegagalan implisit).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Supervisi Systemd vs. Skrip Bash
Alih-alih membiarkan skrip melepaskan diri sendiri ke background menggunakan `&` dan `disown`, skrip Bash modern dirancang untuk berjalan di *foreground* dari perspektif proses anak langsung, sementara `systemd` menangani pengawasannya:

```
systemd (PID 1)
   └── ExecStart=/usr/local/bin/enterprise-worker.sh (PID 1024)
          ├── Subshell Worker 1 (PID 1025)
          └── Subshell Worker 2 (PID 1026)
```

Jika `Type=simple` atau `Type=exec` digunakan pada unit file systemd:
*   `systemd` menganggap service aktif segera setelah perintah `ExecStart` di-fork (`simple`) atau setelah binary dieksekusi secara sukses (`exec`).
*   Standard Output (stdout) dan Standard Error (stderr) skrip dialihkan langsung ke soket UNIX domain milik `systemd-journald` (File Descriptors 1 dan 2 terhubung ke journal socket).
*   Semua proses anak yang dihasilkan skrip dimasukkan ke dalam satu *cgroup* (control group) yang sama. Jika service dihentikan, systemd mengirimkan sinyal (`SIGTERM`, disusul `SIGKILL` jika timeout) ke **seluruh** proses dalam cgroup tersebut, mencegah terjadinya proses yatim (*leaked processes*).

### 2. Penanganan Sinyal POSIX (Graceful Shutdown)
Bash menyediakan instruksi bawaan (built-in) `trap` yang mendaftarkan handler untuk sinyal-sinyal kernel. Alur eksekusinya adalah:
1.  Kernel mendeteksi perintah terminasi (`systemctl stop`, sinyal dari Docker/Kubernetes) dan mengirimkan `SIGTERM` (sinyal 15) ke PID skrip.
2.  Bash menunda penanganan sinyal sampai perintah foreground yang sedang berjalan selesai, **kecuali** perintah tersebut adalah built-in atau skrip menunggu proses background via `wait`.
3.  Fungsi yang terdaftar pada `trap` dieksekusi. Di sini, operasi cleanup (seperti menghapus lockfile, menyelesaikan transaksi file atomik, menutup koneksi) dijalankan.
4.  Skrip keluar secara eksplisit menggunakan `exit 0` atau mematikan dirinya sendiri dengan sinyal default menggunakan `trap - SIGTERM; kill -s SIGTERM $$`.

### 3. File Locking Berbasis Kernel (`flock`)
Untuk mencegah *overlapping executions* di sistem multi-tasking atau environment CI/CD dengan webhook repetitif, Bash memanfaatkan system call Linux `flock(2)`. 

Mekanisme ini tidak mengandalkan keberadaan file lock sederhana (seperti `test -f /tmp/lock && exit 1`), karena metode file test rentan terhadap **race condition** (Time-of-Check to Time-of-Use / TOCTOU). Sebaliknya, `flock` mengasosiasikan lock dengan sebuah **File Descriptor (FD)** yang terbuka. Kernel menjamin bahwa operasi penguncian bersifat atomik pada tingkat Virtual File System (VFS).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Penanganan Sinyal dan Lifecycle Worker Skrip

```
[Systemd / CI Runner Engine]
            |
            | 1. Memanggil Skrip (ExecStart)
            v
+--------------------------------------------------------------------+
| Bash Master Process (PID: 1042)                                    |
|                                                                    |
|  [ Inisialisasi Environment & Trap Handler ]                       |
|  trap 'cleanup_handler SIGTERM' SIGTERM                            |
|  trap 'reload_handler SIGHUP'   SIGHUP                             |
|                                                                    |
|  [ Alokasi File Descriptor & Atomic Lock ]                         |
|  exec 200>/var/lock/enterprise-worker.lock                         |
|  flock -n 200 || exit 1                                            |
|                                                                    |
|  [ Worker Loop ]                                                   |
|  +--------------------------------------------------------------+  |
|  | loop:                                                        |  |
|  |   do_work() &            <-- Menjalankan child process       |  |
|  |   WORKER_PID=$!                                              |  |
|  |   wait $WORKER_PID       <-- Interruptible wait state        |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
            |
            | 2. Event: SIGTERM Terkirim (misal: 'systemctl stop')
            v
+--------------------------------------------------------------------+
| Eksekusi Trap Handler (PID: 1042)                                  |
|                                                                    |
|  1. logger "Menerima SIGTERM, memulai graceful shutdown..."        |
|  2. kill -SIGTERM $WORKER_PID (Propagasi sinyal ke proses anak)    |
|  3. wait $WORKER_PID                                               |
|  4. rm -f /var/run/enterprise-worker.state                         |
|  5. flock -u 200 (Opsional: Otomatis dilepas kernel saat close)   |
|  6. exit 0                                                         |
+--------------------------------------------------------------------+
            |
            | 3. Exit Code 0 dikembalikan ke Supervisor
            v
[Systemd / CI Runner Engine] -> Status: INACTIVE (Clean Exit)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh berikut menunjukkan struktur fundamental penanganan sinyal dan eksekusi non-blocking interruptible loop:

```bash
#!/usr/bin/env bash

# Pastikan strict mode diaktifkan
set -Eeuo pipefail

# Variabel status lifecycle
RUNNING=1
CHILD_PID=0

# Trap handler untuk SIGTERM dan SIGINT
cleanup() {
    local exit_signal="$1"
    echo "[$(date -Iseconds)] Tangkapan sinyal: ${exit_signal}. Memulai terminasi bersih..."
    RUNNING=0
    
    # Periksa apakah child process masih aktif, jika ya, hentikan
    if [[ "${CHILD_PID}" -ne 0 ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
        echo "[$(date -Iseconds)] Mengirim SIGTERM ke proses anak (PID: ${CHILD_PID})..."
        kill -TERM "${CHILD_PID}"
        wait "${CHILD_PID}" 2>/dev/null || true
    fi
    
    echo "[$(date -Iseconds)] Sumber daya dibersihkan. Daemon berhenti secara normal."
    exit 0
}

# Registrasikan fungsi penanganan sinyal
trap 'cleanup SIGTERM' SIGTERM
trap 'cleanup SIGINT' SIGINT

echo "[$(date -Iseconds)] Service daemon dimulai dengan PID: $$"

# Loop utama
while [[ "${RUNNING}" -eq 1 ]]; do
    # Jalankan beban kerja secara asynchronous di background subshell
    # agar instruksi 'wait' dapat segera diputus oleh penerimaan sinyal
    sleep 3600 &
    CHILD_PID=$!
    
    # Tunggu proses anak selesai; 'wait' akan terinterupsi secara instan saat sinyal diterima
    wait "${CHILD_PID}" 2>/dev/null || true
    CHILD_PID=0
done
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi sistem pemantau direktori artefak CI/CD enterprise (`artifact-collector.sh`) yang dirancang untuk beroperasi di bawah supervisi `systemd` dengan jaminan konkurensi kernel-level, pelaporan terstruktur ke `journald`, dan proteksi lingkungan non-interaktif.

### 1. Skrip Shell Produksi: `/usr/local/bin/artifact-collector.sh`

```bash
#!/usr/bin/env bash
#
# ==============================================================================
# Enterprise Artifact Collector Daemon
# File: /usr/local/bin/artifact-collector.sh
# Standard: POSIX.1-2017 / Bash 4.4+ Strict Execution Model
# ==============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

# Deklarasi Konstanta Konfigurasi
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOCK_FD=200
readonly LOCK_FILE="/var/lock/artifact-collector.lock"
readonly SPOOL_DIR="/var/spool/ci-artifacts"
readonly DEST_DIR="/var/opt/ci-storage"
readonly LOG_TAG="ArtifactCollector"

# Global Mutable State
CURRENT_CHILD_PID=0
IS_SHUTTING_DOWN=0

# Utilitas Logging Terstruktur ke Syslog / Journald
log_info() {
    logger -t "${LOG_TAG}" -p user.info -- "level=info pid=$$ msg=\"$*\""
}

log_error() {
    logger -t "${LOG_TAG}" -p user.err -- "level=error pid=$$ msg=\"$*\""
}

log_warn() {
    logger -t "${LOG_TAG}" -p user.warning -- "level=warn pid=$$ msg=\"$*\""
}

# Verifikasi dependensi eksternal yang esensial
verify_prerequisites() {
    local -a deps=("flock" "logger" "rsync" "find")
    for cmd in "${deps[@]}"; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log_error "Ketergantungan kritis tidak ditemukan: ${cmd}"
            exit 127
        fi
    done

    # Buat direktori kerja jika belum tersedia
    [[ -d "${SPOOL_DIR}" ]] || mkdir -p "${SPOOL_DIR}"
    [[ -d "${DEST_DIR}" ]] || mkdir -p "${DEST_DIR}"
}

# Mekanisme Mutual Exclusion Menggunakan Kernel Locks
acquire_lock() {
    # Buka File Descriptor untuk lock file
    eval "exec ${LOCK_FD}>\"${LOCK_FILE}\""
    
    # Gunakan non-blocking exclusive lock
    if ! flock -n "${LOCK_FD}"; then
        log_error "Instance lain dari ${SCRIPT_NAME} telah berjalan. Eksekusi dibatalkan."
        exit 1
    fi
    log_info "Lock file berhasil diperoleh pada FD ${LOCK_FD} (${LOCK_FILE})"
}

# Pemrosesan Artefak CI/CD (Beban Kerja Inti)
process_artifacts() {
    local artifact_batch
    # Cari berkas .tar.gz yang telah selesai ditulis (tidak diakses proses lain dalam 1 menit terakhir)
    artifact_batch=$(find "${SPOOL_DIR}" -type f -name "*.tar.gz" -cmin +1 2>/dev/null || true)

    if [[ -n "${artifact_batch}" ]]; then
        log_info "Menemukan artefak baru, memulai sinkronisasi atomik..."
        
        # Pindahkan via rsync dengan skema proteksi atomik
        rsync -a --remove-source-files "${SPOOL_DIR}/" "${DEST_DIR}/"
        log_info "Sinkronisasi artefak selesai."
    fi
}

# Graceful Shutdown Handler
terminate_daemon() {
    local signal_source="$1"
    
    if [[ "${IS_SHUTTING_DOWN}" -eq 1 ]]; then
        return
    fi
    IS_SHUTTING_DOWN=1
    
    log_warn "Menerima sinyal ${signal_source}. Memulai proses pelepasan sumber daya (graceful shutdown)..."
    
    # Propagasikan terminasi ke proses anak aktif jika ada
    if [[ "${CURRENT_CHILD_PID}" -ne 0 ]] && kill -0 "${CURRENT_CHILD_PID}" 2>/dev/null; then
        log_info "Menghentikan sub-proses pekerja (PID: ${CURRENT_CHILD_PID})..."
        kill -SIGTERM "${CURRENT_CHILD_PID}"
        wait "${CURRENT_CHILD_PID}" 2>/dev/null || true
    fi
    
    # Menutup dan melepaskan File Descriptor lock
    eval "exec ${LOCK_FD}>&-"
    rm -f "${LOCK_FILE}"
    
    log_info "Semua proses telah dibersihkan. Daemon berhenti."
    exit 0
}

# Konfigurasi Sinyal
setup_signal_traps() {
    trap 'terminate_daemon SIGTERM' SIGTERM
    trap 'terminate_daemon SIGINT'  SIGINT
    trap 'log_info "SIGHUP diterima: Reload konfigurasi tidak diimplementasikan.";' SIGHUP
}

# Main Execution Loop
main() {
    log_info "Memulai inisialisasi daemon ${SCRIPT_NAME}..."
    verify_prerequisites
    acquire_lock
    setup_signal_traps
    
    log_info "Inisialisasi selesai. Memasuki main monitoring loop."

    while [[ "${IS_SHUTTING_DOWN}" -eq 0 ]]; do
        # Jalankan eksekusi batch di background
        process_artifacts &
        CURRENT_CHILD_PID=$!
        
        # Wait interuptibel
        wait "${CURRENT_CHILD_PID}" 2>/dev/null || true
        CURRENT_CHILD_PID=0
        
        # Polling delay terinterupsi (sleep di background untuk mempertahankan respons sinyal)
        sleep 10 &
        CURRENT_CHILD_PID=$!
        wait "${CURRENT_CHILD_PID}" 2>/dev/null || true
        CURRENT_CHILD_PID=0
    done
}

# Jalankan entrypoint program
main "$@"
```

### 2. Unit File Systemd: `/etc/systemd/system/artifact-collector.service`

```ini
[Unit]
Description=Enterprise CI/CD Artifact Collector Daemon
Documentation=man:artifact-collector(8)
After=network.target local-fs.target
Wants=network.target

[Service]
Type=exec
User=cicd-svc
Group=cicd-svc
ExecStart=/usr/local/bin/artifact-collector.sh
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=45
Restart=on-failure
RestartSec=10s

# Sandboxing & Security Hardening Limits
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/spool/ci-artifacts /var/opt/ci-storage /var/lock
PrivateTmp=true
NoNewPrivileges=true
CapabilityBoundingSet=

# Resource Controls (cgroups v2)
MemoryMax=512M
CPUQuota=50%
TasksMax=64

# Standard Logging via Journald
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ArtifactCollector

[Install]
WantedBy=multi-user.target
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Kriteria | Shell Script (Bash) murni | Systemd Unit + Bash Wrapper | Bahasa Kompilasi (Go / Rust) |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | Rendah (~3-5 MB per proses subshell) | Rendah + Terbatas via cgroups | Sangat Rendah (~5-10 MB statik binary) |
| **Portabilitas** | Bergantung pada path interpreter dan utilitas bawaan OS (`rsync`, `flock`) | Spesifik pada sistem operasi berbasis Linux systemd | Sangat Tinggi (Single self-contained binary) |
| **Penanganan Concurrency** | Terbatas pada IPC sederhana (FD locks, signals, named pipes) | Dimediasi oleh init system dan event loops skrip | Sangat Lanjut (Pthreads, Goroutines, Channels natively) |
| **Maintenance & Readability** | Rentan rapuh (*brittle*) jika mencapai kompleksitas > 1000 LOC | Sangat baik untuk automasi infrastruktur; konfigurasi deklaratif | Terstruktur via strictly typed interfaces |
| **Crash Recovery** | Harus diimplementasikan manual jika tanpa external supervisor | Otomatis diatur via `Restart=` directive oleh PID 1 | Dapat memantau diri sendiri atau via supervisor luar |
| **Eksekusi CI/CD** | Standar universal (dapat dieksekusi instan di sembarang runner agent) | Tidak berlaku langsung di dalam container unprivileged runner | Memerlukan proses kompilasi sebelum dijalankan |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Standard Prelude yang Ketat**: Selalu sematkan `set -Eeuo pipefail` di baris pertama skrip executable. Opsi `-E` memastikan trap ERR diwariskan ke fungsi shell dan subshell command substitution.
2.  **Hindari "Double-Forking" Shell Tradisional**: Jangan menggunakan sintaksis usang `nohup ./script.sh > /dev/null 2>&1 &` di sistem modern. Delegasikan isolasi proses, redirection, dan pemantauan PID sepenuhnya kepada `systemd`.
3.  **Gunakan File Descriptors Tingkat Tinggi untuk `flock`**: Gunakan FD bernilai 100 hingga 254 (misal: `exec 200>/var/lock/app.lock`) untuk menghindari konflik dengan standard stream (0, 1, 2) atau alokasi dinamis utilitas POSIX.
4.  **Desain Skrip Idempoten untuk Pipeline CI/CD**: Pastikan skrip tidak menghasilkan error jika resource tujuan sudah ada. Gunakan perintah atomik seperti `mkdir -p`, `ln -sfn`, dan `rsync -a` daripada `cp -r`.
5.  **Masking Variabel Rahasia (*Secrets*)**: Pada script CI/CD, hindari perintah `set -x` secara global karena flags ini mencetak evaluasi variabel lingkungan yang berisiko mengekspos API keys atau token ke build logs runner. Jika debugging diperlukan, isolasi:
    ```bash
    set +x
    export SENSITIVE_TOKEN="secret"
    set -x
    ```
6.  **Gunakan Pola `wait` Interuptibel**: Saat menunggu di dalam loop daemon, hindari `sleep <durasi_panjang>` langsung di thread utama. Eksekusi `sleep` di background dan panggil `wait $!`. Hal ini memastikan sinyal `SIGTERM` segera dievaluasi oleh shell tanpa harus menunggu timer sleep selesai.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Mengabaikan Perilaku Non-Interactive Shell di CI/CD**:
    *   *Gejala*: Perintah berjalan normal di terminal SSH developer, tetapi gagal dengan pesan `command not found` di pipeline runner.
    *   *Penyebab*: Utilitas dependensi dipasang pada path lokal seperti `$HOME/.nvm/bin` atau `/usr/local/bin` yang hanya dimuat melalui file `~/.bashrc` (interactive non-login mode).
    *   *Solusi*: Definisikan variabel `$PATH` secara eksplisit dan absolut di awal skrip otomasi.
2.  **Kondisi Race Condition pada Lock File Primitif**:
    *   *Anti-pattern*:
        ```bash
        # BERBAHAYA: TOCTOU Race Condition
        if [ -f /tmp/lock ]; then exit 1; fi
        touch /tmp/lock
        ```
    *   *Solusi*: Gunakan locking berbasis kernel via `flock(1)` yang mengeksekusi pemeriksaan dan penguncian dalam satu instruksi atomik kernel:
        ```bash
        exec 200>/tmp/lock
        flock -n 200 || exit 1
        ```
3.  **Zombie Accumulation**:
    *   *Gejala*: Timbul puluhan hingga ratusan proses dengan status `[defunct]` saat daemon berjalan berhari-hari.
    *   *Penyebab*: Daemon melepaskan proses anak menggunakan `&` tanpa pernah memanggil `wait` untuk mengonsumsi exit status dari proses anak tersebut.
    *   *Solusi*: Implementasikan fungsi penampung sinyal `SIGCHLD` (`trap 'wait' SIGCHLD`) atau tangkap secara eksplisit seluruh sub-PID yang di-spawn.
4.  **Membuat File State Sementara Tanpa Pembersihan Mutlak**:
    *   *Gejala*: Runner CI/CD atau daemon menolak berjalan pada run kedua karena direktori atau lock file sisa (*stale lock*) run sebelumnya masih tertinggal saat skrip abort.
    *   *Solusi*: Buat registrasi `trap ... EXIT` di awal program. Trap `EXIT` dijamin dieksekusi saat skrip berhenti dalam skenario apa pun, termasuk error fatal atau interupsi sinyal.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Dasar): Membuat Robust Non-Interactive CI Runner Task
*   **Objektif**: Buat skrip `build-task.sh` yang menjalankan serangkaian kompilasi tiruan dengan verifikasi strict mode, deterministic exit codes, dan logging execution time.
*   **Spesifikasi**:
    *   Aktifkan `set -Eeuo pipefail`.
    *   Bungkus tugas build ke dalam fungsi yang mengembalikan waktu eksekusi total (dalam detik).
    *   Tangkap kegagalan dan keluarkan ringkasan error ke `stderr` tanpa meninggalkan file sementara yang dibuat di `/tmp/build-XXXXXX`.
*   **Kode Solusi Terverifikasi**:
    ```bash
    #!/usr/bin/env bash
    set -Eeuo pipefail

    TMP_DIR=$(mktemp -d /tmp/build-XXXXXX)

    cleanup() {
        echo "Membersihkan workspace sementara: ${TMP_DIR}" >&2
        rm -rf "${TMP_DIR}"
    }
    trap cleanup EXIT

    execute_task() {
        local start_time end_time duration
        start_time=$(date +%s)
        
        echo "Menjalankan kompilasi pada workspace..."
        touch "${TMP_DIR}/artifact.bin"
        sleep 2
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        echo "Tugas selesai dalam ${duration} detik."
    }

    execute_task
    ```

### Latihan 2 (Menengah): Daemon Watchdog dengan Self-Contained Lock
*   **Objektif**: Buat skrip daemon `health-watchdog.sh` yang memantau utilitas disk (`/`) setiap 5 detik. Jika utilitas disk di atas 90%, tulis peringatan ke syslog.
*   **Spesifikasi**:
    *   Gunakan File Descriptor 205 untuk locking pada `/tmp/watchdog.lock`.
    *   Gunakan interruptible wait.
    *   Keluar secara bersih saat menerima sinyal `SIGTERM` atau `SIGINT`.
*   **Kode Solusi Terverifikasi**:
    ```bash
    #!/usr/bin/env bash
    set -Eeuo pipefail

    LOCK_FILE="/tmp/watchdog.lock"
    exec 205>"${LOCK_FILE}"
    flock -n 205 || { echo "Daemon sudah aktif." >&2; exit 1; }

    RUNNING=1
    CHILD_PID=0

    cleanup() {
        RUNNING=0
        if [[ "${CHILD_PID}" -ne 0 ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
            kill -TERM "${CHILD_PID}"
            wait "${CHILD_PID}" 2>/dev/null || true
        fi
        exec 205>&-
        rm -f "${LOCK_FILE}"
        logger -t "Watchdog" "Watchdog dihentikan secara normal."
        exit 0
    }
    trap cleanup SIGTERM SIGINT

    logger -t "Watchdog" "Watchdog aktif."

    while [[ "${RUNNING}" -eq 1 ]]; do
        CURRENT_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
        if [[ "${CURRENT_USAGE}" -gt 90 ]]; then
            logger -p user.warning -t "Watchdog" "Peringatan: Penggunaan disk / mencapai ${CURRENT_USAGE}%"
        fi
        
        sleep 5 &
        CHILD_PID=$!
        wait "${CHILD_PID}" 2>/dev/null || true
        CHILD_PID=0
    done
    ```

### Latihan 3 (Lanjut): Atomic Blue/Green Deployer Engine
*   **Objektif**: Buat skrip deployment production `deploy-release.sh` yang menerima input path source release dan melakukan swap symlink secara atomik ke `/var/www/live`.
*   **Spesifikasi**:
    *   Skrip harus menerima satu argumen: direktori path rilis (misal: `/releases/v1.0.2`).
    *   Validasi bahwa direktori rilis valid dan berisi file manifest `VERSION`.
    *   Lakukan pergantian symlink live menggunakan teknik atomic POSIX rename via `ln -sfn` atau manipulasi rename temporary symlink (`ln -s ... temp && mv -T temp /var/www/live`).
    *   Jika proses gagal di tengah jalan, symlink `/var/www/live` tidak boleh berada dalam kondisi rusak (*broken*).
*   **Kode Solusi Terverifikasi**:
    ```bash
    #!/usr/bin/env bash
    set -Eeuo pipefail

    readonly LIVE_LINK="/var/www/live"
    readonly TARGET_RELEASE="${1:-}"

    if [[ -z "${TARGET_RELEASE}" ]]; then
        echo "Penggunaan: $0 <path-direktori-rilis>" >&2
        exit 1
    fi

    if [[ ! -d "${TARGET_RELEASE}" ]]; then
        echo "Error: Direktori rilis '${TARGET_RELEASE}' tidak ditemukan." >&2
        exit 2
    fi

    if [[ ! -f "${TARGET_RELEASE}/VERSION" ]]; then
        echo "Error: File manifest '${TARGET_RELEASE}/VERSION' tidak ada. Rilis tidak valid." >&2
        exit 3
    fi

    echo "Mempersiapkan atomic swap menuju: ${TARGET_RELEASE}..."

    # Buat symlink sementara di direktori yang sama dengan live target
    TEMP_LINK="$(mktemp -u "${LIVE_LINK}.tmp.XXXXXX")"

    # Arahkan symlink temporary ke target
    ln -s "${TARGET_RELEASE}" "${TEMP_LINK}"

    # Atomic Rename: Menggantikan symlink lama tanpa downtime
    # Parameter -T memaksa mv memperlakukan target sebagai berkas symlink, bukan folder
    if mv -Tf "${TEMP_LINK}" "${LIVE_LINK}"; then
        echo "Deployment Berhasil: ${LIVE_LINK} -> ${TARGET_RELEASE}"
        exit 0
    else
        echo "Error: Gagal melakukan swap atomik." >&2
        rm -f "${TEMP_LINK}"
        exit 4
    fi
    ```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Mengapa konstruksi `kill -9` (`SIGKILL`) dilarang keras digunakan sebagai mekanisme default shutdown pada daemon skrip Bash?**
    *   A. Sinyal `SIGKILL` membutuhkan akses root penuh untuk dialirkan ke sub-proses.
    *   B. Sinyal `SIGKILL` tidak dapat dicegat (*intercepted*) atau ditangani oleh `trap`, sehingga proses langsung dihentikan oleh kernel tanpa mengeksekusi rutin pembersihan file lock atau buffer I/O.
    *   C. `SIGKILL` menyebabkan memory leak permanen pada hardware RAM server.
    *   D. `SIGKILL` otomatis mengubah status exit code Bash menjadi `0`.
    *   *Jawaban*: **B**. Kernel menangani `SIGKILL` secara instan pada process table tanpa memberikan kesempatan bagi proses target untuk mengeksekusi instruksi trap cleanup.

2.  **Pada systemd unit, apakah perbedaan fungsional mendasar antara `Type=simple` dan `Type=exec` ketika mengeksekusi skrip Bash?**
    *   A. `Type=simple` menolak pembacaan file script Bash.
    *   B. `Type=simple` menganggap unit telah aktif segera setelah `fork()` dilakukan oleh systemd, sedangkan `Type=exec` menunggu hingga interpreter Bash selesai di-load dan dieksekusi.
    *   C. `Type=exec` secara otomatis menduplikasi stdout skrip ke `/dev/null`.
    *   D. `Type=simple` tidak mendukung penghentian proses melalui sinyal `SIGTERM`.
    *   *Jawaban*: **B**. `Type=exec` memastikan unit dependensi lain yang bergantung pada service ini tidak dijalankan sebelum eksekusi binary/skrip benar-benar dimulai oleh kernel.

3.  **Mengapa pendekatan polling `sleep 60` di dalam main loop daemon skrip Bash dianggap sebagai anti-pattern jika penanganan sinyal dibutuhkan secara instan?**
    *   A. Perintah `sleep` menggunakan resource CPU sebesar 100%.
    *   B. Eksekusi `sleep` secara foreground memblokir eksekusi Bash trap handler hingga interval 60 detik selesai, menunda respon terhadap `SIGTERM`.
    *   C. `sleep` otomatis melepaskan lock descriptor yang diperoleh via `flock`.
    *   D. `sleep` mengembalikan exit code non-zero jika dijalankan di environment CI/CD.
    *   *Jawaban*: **B**. Ketika Bash menjalankan perintah eksternal di foreground, trap handler sinyal baru akan diproses *setelah* perintah eksternal tersebut selesai, kecuali perintah tersebut dijalankan di background dan ditunggu dengan `wait`.

4.  **Apa fungsi opsi `-n` pada perintah `flock -n 200`?**
    *   A. Mengunci file descriptor dalam mode read-only (shared lock).
    *   B. Non-blocking mode: Menginstruksikan `flock` untuk langsung gagal (*fail-fast*) dengan exit code 1 jika file descriptor sedang dikunci oleh proses lain, alih-alih menunggu lock dilepas.
    *   C. Menghapus (*nullify*) file lock secara otomatis saat proses anak mati.
    *   D. Mencegah logging systemd mencatat aktivitas penguncian.
    *   *Jawaban*: **B**. Non-blocking execution sangat esensial untuk mencegah antrean eksekusi instance otomatis yang berjalan serentak.

5.  **Perilaku shell manakah yang paling tepat mendeskripsikan runner pada platform CI/CD (seperti GitHub Actions atau GitLab CI)?**
    *   A. Interactive Login Shell
    *   B. Non-Interactive Login Shell
    *   C. Non-Interactive Non-Login Shell
    *   D. Interactive Non-Login Shell
    *   *Jawaban*: **C**. CI runner menjalankan job langsung melalui batch execution string (misal: `bash -c ...`) tanpa mengalokasikan terminal interaktif (TTY) dan tanpa membaca script inisialisasi login seperti `/etc/profile`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Manual Pages (Linux Standard Documentation)**:
    *   `man 1 bash` — Bagian *SIGNALS*, *INVOCATION*, dan *REDIRECTION*.
    *   `man 2 flock` — Spesifikasi Linux kernel advisory file locks.
    *   `man 5 systemd.service` — Spesifikasi konfigurasi unit file systemd.
    *   `man 7 signal` — Tinjauan komprehensif seluruh sinyal POSIX Linux.
2.  **Standar & Spesifikasi Industri**:
    *   The Open Group Base Specifications Issue 7 (IEEE Std 1003.1-2017) — *POSIX.1 Shell Command Language*.
    *   The Twelve-Factor App: *Processes & Concurrency* (https://12factor.net/processes).
    *   Systemd Process Hardening Guide: Freedesktop.org systemd security directives.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

| Topik Utama | Mekanisme Inti | Implikasi Teknis |
| :--- | :--- | :--- |
| **Daemon Modern** | Supervisi Systemd (`Type=exec`) | Lifecycle, cgroups v2 resource limits, dan logging dikelola oleh PID 1; skrip berjalan di foreground. |
| **Signal Handling** | `trap <handler> <SIGNALS>` | Memungkinkan graceful termination, propagasi sinyal ke worker subshell, dan mitigasi data corruption. |
| **Concurrency Control** | `flock` via Dedicated File Descriptor | Penguncian atomik berbasis kernel VFS; mencegah race conditions dan eksekusi duplikat tanpa risiko TOCTOU. |
| **Lingkungan CI/CD** | Non-Interactive, Non-Login Execution | Mewajibkan path deterministik, eliminasi asumsi terminal interaktif, dan isolasi file konfigurasi shell manual. |
| **Atomic Updates** | In-place symlink swapping (`mv -Tf`) | Menjamin zero-downtime deployment tanpa mengekspos broken states kepada service konsumen. |

---

## SEKSI 17 — GLOSARIUM

*   **Atomic Operation**: Operasi komputasi yang dieksekusi secara keseluruhan atau tidak sama sekali; tidak dapat diinterupsi atau ditinggalkan dalam kondisi setengah selesai oleh proses lain.
*   **cgroups (Control Groups) v2**: Mekanisme kernel Linux untuk membatasi, mencatat, dan mengisolasi alokasi penggunaan sumber daya (CPU, Memori, I/O) bagi sekumpulan proses.
*   **File Descriptor (FD)**: Indikator abstrak berformat integer yang dialokasikan oleh kernel Linux untuk mengakses berkas, soket, atau pipa I/O.
*   **Idempoten**: Karakteristik sebuah operasi di mana eksekusi berulang kali terhadap operasi tersebut menghasilkan state akhir yang sama tanpa efek samping baru.
*   **Non-Interactive Shell**: Kondisi di mana interpreter shell dijalankan tanpa terhubung ke input terminal pengguna (`stdin` tidak terikat pada TTY).
*   **Orphan Process**: Proses anak yang terus berjalan saat proses induknya (*parent*) telah mati, yang kemudian diadopsi oleh init system (PID 1).
*   **Race Condition**: Situasi anomali di mana output dari program bergantung pada urutan atau durasi relatif dari thread/proses lain yang tidak tersinkronisasi.
*   **TOCTOU (Time-of-Check to Time-of-Use)**: Kategori kerentanan perangkat lunak yang disebabkan oleh perubahan kondisi sistem di antara waktu pengecekan status sumber daya dan waktu pemanfaatan sumber daya tersebut.
*   **Zombie Process (Defunct)**: Proses yang telah selesai dieksekusi, tetapi entri prosesnya masih tersisa di process table kernel Linux karena proses induknya belum membaca exit status-nya via syscall `wait()`.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Penyampaian Materi Teori**:
    *   Bongkar pemikiran usang mahasiswa/peserta yang menganggap daemon di Linux harus dibuat dengan perintah `nohup ... & disown`. Jelaskan mengapa paradigma tersebut menjadi sumber masalah besar pada era orkestrasi modern (karena `nohup` melepaskan kaitan dari process supervision tree, menyulitkan monitoring, dan sering kali meninggalkan memory leaks).
    *   Tunjukkan visualisasi interaktif proses tree menggunakan perintah `ps -ef f` atau `pstree -ap` untuk memperlihatkan hierarki kontrol antara systemd, skrip Bash, dan child processes.
*   **Setup Lab & Praktik**:
    *   Pastikan lingkungan lab memiliki akses `sudo` untuk membuat systemd service unit di `/etc/systemd/system/`.
    *   Uji responsivitas trap dengan mengirimkan sinyal menggunakan utilitas `kill`:
        ```bash
        systemctl start artifact-collector
        journalctl -u artifact-collector -f &
        systemctl stop artifact-collector
        ```
    *   Verifikasi bahwa pesan `Menerima sinyal SIGTERM` muncul di `journalctl` sebelum service beralih ke state `inactive (dead)`.
*   **Fokus Debugging**:
    *   Jika skrip peserta menghasilkan error `Permission denied` saat mengalokasikan lock, tinjau permissions direktori `/var/lock` atau `/run/lock`. Arahkan pengujian sementara ke direktori `/tmp/` jika isolasi user non-root diterapkan secara ketat.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (2025-02-15)**:
    *   Inisialisasi penyusunan materi komprehensif Bab 10 Modul 01.
    *   Integrasi standar POSIX signals, modern systemd service architecture, dan pattern CI/CD non-interactive headless runner.
    *   Penambahan implementasi locking berbasis kernel `flock` via File Descriptor 200.
    *   Pengayaan latihan implementasi Blue/Green atomic symlink swapping.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**: `MOD-BASH-09-03` — Advanced Signal Handling, Process Groups & Job Control
*   **Modul Saat Ini**: `MOD-BASH-10-01` — Automasi Enterprise, Daemon & CI/CD
*   **Modul Berikutnya**: `MOD-BASH-10-02` — Secure Infrastructure Automation: Auditability, Compliance & Defensive Hardening