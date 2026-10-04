# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab:** 02 (BAB-02-Materi-Lanjutan) | **Topik:** devops-beginner

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal Linux OS (Kernel vs User Space, VFS, Process Lifecycle, dan Signals) untuk kebutuhan otomasi tingkat lanjut.
- Membangun skrip otomasi Bash *production-ready* yang mengimplementasikan *strict error handling*, *POSIX traps*, *idempotency*, dan *defensive programming*.
- Mengonfigurasi, mengamankan, dan mengelola *systemd unit services* dengan batasan sumber daya (*cgroups v2*) dan parameter isolasi keamanan kernel (*sandboxing*).
- Merancang fondasi pipeline CI/CD lokal yang memvalidasi integritas kode infrastruktur melalui *linting*, *automated testing*, dan *deterministic artifact generation*.
- Menginvestigasi dan menyelesaikan kegagalan sistem produksi menggunakan observabilitas berbasis *system calls* (`strace`), *network sockets* (`ss`), dan analisis *system log journal*.

---

## 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memiliki:
- Pemahaman dasar terminal Linux (perintah navigasi file, I/O redirection `|`, `>`, `<`).
- Pemahaman konsep dasar Git (commit, branch, merge, push/pull).
- Akses ke sistem operasi berbasis Linux (disarankan Ubuntu 22.04 LTS / Debian 12 / RHEL 9) dengan hak akses `sudo`.
- Perangkat dengan spesifikasi minimal 2 vCPU, RAM 4 GB, dan media penyimpanan kosong 20 GB.

---

## 3. Concept & Internal Architecture

Dalam konteks rekayasa keandalan sistem (SRE) dan DevOps, otomasi tanpa pemahaman arsitektur sistem operasi dasar akan menciptakan sistem yang rapuh (*brittle*).

### 3.1 Kernel Space vs. User Space & Interupsi System Call

Sistem operasi modern memisahkan memori menjadi dua ring proteksi hardware:
1. **User Space (Ring 3):** Lingkungan eksekusi aplikasi pengguna (web server, skrip otomasi, database). Ruang ini memiliki akses terbatas terhadap hardware.
2. **Kernel Space (Ring 0):** Inti sistem operasi yang memiliki akses langsung tak terbatas ke CPU, RAM, disk controller, dan kartu jaringan.

Ketika aplikasi di User Space perlu menulis file konfigurasi atau membuka *socket* jaringan, aplikasi tersebut tidak dapat mengeksekusinya secara langsung. Aplikasi wajib memicu **Software Interrupt** melalui antarmuka **System Call (syscall)** seperti `open()`, `read()`, `write()`, `fork()`, `execve()`, dan `epoll_create()`.

```
+-------------------------------------------------------------+
|                        USER SPACE                           |
|  [ Custom Daemon / Go App ]      [ Production Bash Script ] |
|            |                                  |             |
|            +---------------+------------------+             |
|                            | (Standard C Library - glibc)   |
|                            v                                |
|                     System Call Interface                   |
+----------------------------|--------------------------------+
|                            v (Context Switch via Syscall)   |
|                        KERNEL SPACE                         |
|  +-------------------------------------------------------+  |
|  | Process Scheduler | Memory Manager | VFS (Filesystem) |  |
|  +-------------------------------------------------------+  |
|  | Device Drivers    | Network Stack  | cgroups & Seccomp|  |
|  +-------------------------------------------------------+  |
+----------------------------|--------------------------------+
                             v
                        [ HARDWARE ]
             (CPU / RAM / NVMe Storage / NIC)
```

DevOps engineer harus memahami bahwa setiap baris skrip shell yang berinteraksi dengan disk atau jaringan memicu ratusan *context switch* antara User Space dan Kernel Space. Kegagalan memahami biaya *syscall* ini dapat memicu degradasi performa I/O (*I/O wait spike*).

### 3.2 Linux Process Lifecycle & Signal Dispatching

Setiap proses di Linux diidentifikasi oleh PID (*Process ID*). Proses baru dibuat melalui dua tahap:
1. `fork()`: Kernel menduplikasi proses induk (*parent*). Ruang memori disalin menggunakan mekanisme *Copy-On-Write* (COW).
2. `execve()`: Kernel mengganti image proses hasil duplikasi dengan biner baru yang akan dieksekusi.

```
[Parent Process] (PID: 1000)
       |
       |-- fork() --> Menduplikasi memori parent (COW)
       |              Child PID: 1001
       |
       \-- execve() -> Memuat biner baru ke PID 1001
```

Manajemen siklus hidup aplikasi membutuhkan pemahaman terhadap **POSIX Signals**:
- **SIGTERM (Signal 15):** Permintaan terminasi halus (*graceful shutdown*). Aplikasi menangkap sinyal ini, menyelesaikan transaksi yang berjalan, menutup koneksi database, lalu keluar.
- **SIGKILL (Signal 9):** Terminasi paksa oleh kernel. Sinyal ini **tidak dapat ditangkap atau diabaikan** oleh aplikasi. Jika aplikasi tidak merespons SIGTERM dalam waktu tertentu, orkestrator akan mengirimkan SIGKILL, yang berisiko merusak status data (*data corruption*).
- **SIGHUP (Signal 1):** Memberi tahu proses untuk memuat ulang konfigurasi tanpa menghentikan *execution state*.
- **SIGCHLD (Signal 17):** Dikirimkan ke parent saat child process berakhir. Jika parent gagal mengeksekusi `wait()` atau `waitpid()`, child process berubah menjadi **Zombie Process** (`[defunct]`), yang mengonsumsi alokasi PID kernel.

### 3.3 Systemd Architecture & Resource Isolation (cgroups v2)

`systemd` adalah *init system* (PID 1) modern pada mayoritas distribusi Linux. `systemd` menggantikan SysV init dengan memperkenalkan eksekusi paralel layanan, dependensi soket, dan manajemen resource melalui **Control Groups (cgroups)**.

Pada Linux kernel modern (cgroups v2), `systemd` mengelompokkan proses ke dalam pohon hirarki yang seragam (*single unified hierarchy*). Tiga unit utama pengelompokan proses adalah:
- **Slice (`.slice`):** Node konseptual untuk isolasi resource (contoh: `system.slice`, `user.slice`).
- **Scope (`.scope`):** Proses yang dibuat secara eksternal tetapi dimonitor oleh systemd.
- **Service (`.service`):** Daemon yang dikontrol dan dikonfigurasi melalui systemd unit file.

Fitur keamanan kernel yang diekspos oleh systemd:
- `ProtectSystem=strict`: Menjadikan direktori `/usr`, `/boot`, dan `/etc` bersifat *read-only* bagi service.
- `NoNewPrivileges=yes`: Mencegah proses anak mendapatkan hak akses tambahan via binary SUID.
- `PrivateTmp=yes`: Mengisolasi direktori `/tmp` ke dalam *mount namespace* privat, mencegah kebocoran file antar proses.

---

## 4. Why & What

### Mengapa Shell Scripting Sederhana Tidak Cukup di Enterprise?
Banyak skrip otomasi yang ditulis secara naif tanpa penanganan *return code*, validasi dependensi, atau *idempotency*. 
- **Script Naif:** Gagal saat berjalan di tengah-tengah proses, meninggalkan infrastruktur dalam kondisi *half-configured* (*state drifting*).
- **Production-grade Script:** Menerapkan *defensive programming*, menangani sinyal interupsi, menjamin sifat *idempotent* (dieksekusi 1 kali atau 100 kali menghasilkan status akhir yang persis sama), dan memancarkan *structured logging* ke syslog/journald.

### Mengapa Systemd Wajib Dikuasai vs "Run in Background via nohup/screen"?
Menjalankan aplikasi *enterprise* menggunakan `nohup java -jar app.jar &` memiliki kelemahan fatal:
1. Tidak ada jaminan restart otomatis saat proses *crash* (*OOM-Killed* atau *unhandled exception*).
2. Sulit membatasi konsumsi memori dan CPU; satu proses yang *leak* dapat menghabiskan RAM host dan memicu kernel *kernel panic*.
3. Kehilangan kontrol hierarki proses anak; ketika proses induk mati, child process tertinggal dan menjadi *orphan*.

---

## 5. How (Workflow Detail)

Berikut adalah alur otomasi rilis layanan dari kode sumber lokal hingga deployment berbasis systemd dengan validasi resource:

```
[Local Workstation / Runner]
       |
       | 1. Static Analysis & Linting (shellcheck, shfmt, yamllint)
       v
[Artifact Packaging Engine]
       |
       | 2. Build tarball, checksum hash (SHA-256), embed metadata
       v
[Target Node (Production Host)]
       |
       | 3. Transport & Verify Checksum
       | 4. Unpack to immutable path (/opt/app-releases/vX.Y.Z)
       | 5. Atomic Symlink Switch (/opt/app-current -> /opt/app-releases/vX.Y.Z)
       | 6. Validate Systemd Service & Reload Daemon (systemctl daemon-reload)
       | 7. Restart Service gracefully (SIGTERM -> Grace Period -> Verify)
       v
[Observability & Health Check]
       |
       | 8. Verify Socket Listener (ss -tulpn)
       | 9. Assert Health Check Endpoint (curl -f http://127.0.0.1:8080/health)
       +---> [SUCCESS]: Terminasikan release lama
       +---> [FAILURE]: Rollback symlink ke versi sebelumnya (Atomic Rollback)
```

---

## 6. Analogy & Diagram ASCII

### Analogi Kernel vs User Space
Bayangkan sistem operasi sebagai sebuah **Bank Sentral**:
- **Kernel Space** adalah **Brankas Utama dan Ruang Kontrol Keamanan**. Hanya petugas berotoritas tinggi dengan seragam khusus yang boleh berada di dalamnya.
- **User Space** adalah **Lobi Publik**. Nasabah (aplikasi) dapat berkumpul, berbicara, dan mengisi formulir di sini.
- **System Call** adalah **Loket Teller**. Nasabah tidak boleh masuk ke brankas untuk mengambil uang tunai secara langsung. Mereka harus menyerahkan slip penarikan (syscall `read`/`write`) kepada teller (kernel). Teller memeriksa hak akses (permission), memverifikasi saldo, masuk ke brankas, mengambil uang, dan menyerahkannya kembali ke nasabah di lobi.

### Diagram Arsitektur Cgroups v2 & Systemd

```
                         [ cgroup root: /sys/fs/cgroup ]
                                       |
                +----------------------+----------------------+
                |                                             |
        [ system.slice ]                                [ user.slice ]
         (System Daemons)                             (Interactive Users)
                |
        +-------+-------------------------+
        |                                 |
[ payment-api.service ]           [ log-forwarder.service ]
  - MemoryMax: 512M                 - MemoryMax: 128M
  - CPUWeight: 200                  - CPUWeight: 50
  - TasksMax: 64                    - TasksMax: 16
        |                                 |
  +-----+-----+                     +-----+-----+
  |           |                     |           |
[Worker 1]  [Worker 2]            [Tailer]    [Compressor]
(PID 4011)  (PID 4012)            (PID 5011)  (PID 5012)
```

Jika `payment-api.service` mengalami *memory leak*, subsistem cgroup akan langsung mengeksekusi OOM killer khusus di dalam slice tersebut tanpa mengorbankan database atau proses kritis lainnya pada host.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Skrip Otomasi dengan POSIX Trap & Strict Mode

Simpan skrip ini untuk memahami mekanisme *Strict Mode* dan *Signal Trapping*.

```bash
#!/usr/bin/env bash
# Strict Mode:
# -e: Berhenti jika ada command yang menghasilkan exit status non-zero
# -u: Berhenti jika menemukan variabel yang belum didefinisikan (unbound variable)
# -o pipefail: Pipeline mengembalikan error jika ada salah satu command di pipeline yang gagal
set -euo pipefail

# Inisialisasi variabel temporer
TMP_DIR="$(mktemp -d -t deploy-infra-XXXXXX)"

# Cleanup function (Idempotent cleanup)
cleanup() {
    local exit_code=$?
    echo "[INFO] Membersihkan resource temporer di: ${TMP_DIR}"
    rm -rf "${TMP_DIR}"
    if [ ${exit_code} -ne 0 ]; then
        echo "[ERROR] Skrip gagal dieksekusi! Exit code: ${exit_code}" >&2
    else
        echo "[SUCCESS] Eksekusi selesai secara normal."
    fi
    exit ${exit_code}
}

# Trap menangani sinyal EXIT, SIGINT (Ctrl+C), dan SIGTERM
trap cleanup EXIT SIGINT SIGTERM

echo "[INFO] Menjalankan proses build payload..."
echo "Payload Engine v1.0.0" > "${TMP_DIR}/payload.txt"

# Simulasi operasi
cat "${TMP_DIR}/payload.txt"
```

### 7.2 Practical Example: Enterprise Deployment Engine & Hardened Systemd Service

Berikut adalah implementasi sistem rilis atomik (*Atomic Symlink Deployment Engine*) yang siap digunakan di lingkungan produksi enterprise.

#### A. The Deployment Automation Script (`deploy-engine.sh`)

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Application Deployment Engine
# Features: Atomic deployment, rollback mechanism, strict verification
# ==============================================================================
set -euo pipefail
IFS=$'\n\t'

# --- Configuration Variables ---
readonly APP_NAME="telemetry-collector"
readonly BASE_DIR="/opt/${APP_NAME}"
readonly RELEASES_DIR="${BASE_DIR}/releases"
readonly CURRENT_LINK="${BASE_DIR}/current"
readonly LOG_DIR="/var/log/${APP_NAME}"
readonly SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

# --- Logging Facilities ---
log_info()  { echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [INFO]  $*"; }
log_warn()  { echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [WARN]  $*" >&2; }
log_error() { echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [ERROR] $*" >&2; }

# --- Security Checks ---
if [[ "${EUID}" -ne 0 ]]; then
    log_error "Skrip ini wajib dijalankan dengan hak akses root (sudo)."
    exit 1
fi

# Argument Handling
VERSION="${1:-}"
if [[ -z "${VERSION}" ]]; then
    log_error "Argumen versi wajib disertakan! Penggunaan: $0 <version-string>"
    exit 1
fi

readonly TARGET_RELEASE_DIR="${RELEASES_DIR}/${VERSION}"
TMP_WORKSPACE="$(mktemp -d -t "${APP_NAME}-deploy-XXXXXX")"

# --- Defensive Cleanup Trap ---
cleanup() {
    local exit_code=$?
    if [[ -d "${TMP_WORKSPACE}" ]]; then
        rm -rf "${TMP_WORKSPACE}"
    fi
    if [[ ${exit_code} -ne 0 ]]; then
        log_error "Deployment GAGAL. Menjaga release aktif tetap berjalan."
    fi
    exit "${exit_code}"
}
trap cleanup EXIT SIGINT SIGTERM

# --- Step 1: Pre-flight Verification & Directory Tree Setup ---
log_info "Memulai deployment untuk ${APP_NAME} versi: ${VERSION}"

mkdir -p "${RELEASES_DIR}" "${LOG_DIR}"
id -u "${APP_NAME}" &>/dev/null || useradd -r -s /usr/sbin/nologin -d "${BASE_DIR}" "${APP_NAME}"

# --- Step 2: Download & Extract Artifact to Staging Workspace ---
log_info "Menyiapkan biner payload..."
cat << 'EOF' > "${TMP_WORKSPACE}/collector.sh"
#!/usr/bin/env bash
# Mock internal microservice
set -euo pipefail
trap 'echo "Menerima SIGTERM, menutup koneksi database..."; exit 0' SIGTERM
echo "Telemetry Collector berjalan pada PID $$..."
while true; do
    echo "$(date -u) - Jantung sistem normal: Memory usage nominal" >> /dev/stdout
    sleep 5
done
EOF
chmod 755 "${TMP_WORKSPACE}/collector.sh"

# --- Step 3: Atomic Release Placement ---
if [[ -d "${TARGET_RELEASE_DIR}" ]]; then
    log_warn "Versi ${VERSION} sudah ada. Mengganti isi rilis..."
    rm -rf "${TARGET_RELEASE_DIR}"
fi

mkdir -p "${TARGET_RELEASE_DIR}"
cp -a "${TMP_WORKSPACE}/collector.sh" "${TARGET_RELEASE_DIR}/collector"
chown -R "${APP_NAME}:${APP_NAME}" "${BASE_DIR}" "${LOG_DIR}"

# --- Step 4: Atomic Symlink Switchover ---
log_info "Melakukan pergantian symlink secara atomik..."
ln -sfn "${TARGET_RELEASE_DIR}" "${CURRENT_LINK}.tmp"
mv -Tf "${CURRENT_LINK}.tmp" "${CURRENT_LINK}"

# --- Step 5: Systemd Unit Provisioning ---
log_info "Mengonfigurasi systemd hardening service..."
cat << EOF > "${SERVICE_FILE}"
[Unit]
Description=Enterprise Telemetry Collector Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_NAME}
Group=${APP_NAME}
WorkingDirectory=${CURRENT_LINK}
ExecStart=${CURRENT_LINK}/collector
Restart=always
RestartSec=5s

# Process Lifecycle Handling
KillMode=mixed
TimeoutStopSec=20s

# Sandboxing & Security Controls
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ReadWritePaths=${LOG_DIR}

# Resource Control (cgroups v2)
MemoryMax=256M
CPUQuota=50%
TasksMax=32

[Install]
WantedBy=multi-user.target
EOF

# --- Step 6: Activation & Health Validation ---
log_info "Menerapkan konfigurasi ke systemd..."
systemctl daemon-reload
systemctl enable "${APP_NAME}.service"
systemctl restart "${APP_NAME}.service"

# Health check
log_info "Melakukan validasi status daemon..."
sleep 2
if systemctl is-active --quiet "${APP_NAME}.service"; then
    log_info "Layanan ${APP_NAME} (v${VERSION}) BERHASIL di-deploy dan aktif!"
else
    log_error "Layanan gagal berjalan! Mengambil log terakhir:"
    journalctl -u "${APP_NAME}.service" -n 20 --no-pager
    exit 1
fi
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden OOM Killer Cascade pada Payment Gateway
- **Konteks:** Sebuah sistem microservice payment processing memproses rata-rata 4.500 transaksi per detik. Komponen *worker* ditulis menggunakan runtime Python yang dijalankan manual via skrip shell menggunakan operator *background* `&`.
- **Insiden:** Terjadi *memory leak* pada library enkripsi payload. Tanpa batas memori (*unbounded memory*), proses *worker* mengonsumsi 98% kapasitas RAM host fisik (64 GB). Kernel Linux memicu mekanisma **Out-Of-Memory (OOM) Killer**.
- **Dampak Fatal:** Algoritma heuristik OOM Killer kernel (`/proc/[pid]/oom_score`) memilih proses yang paling banyak mengonsumsi memori tetapi memiliki dependensi vital. Akibatnya, instance database PostgreSQL lokal dan SSH daemon (`sshd`) dimatikan paksa oleh kernel. Seluruh akses remote terputus, dan transaksi pembayaran terhenti selama 42 menit (Estimasi kerugian: \$180.000).

### Resolusi Teknis Arsitektural:
1. **Adopsi cgroups v2 via systemd:** Setiap worker ditempatkan di bawah unit tersendiri dengan direktif `MemoryMax=2G` dan `MemoryHigh=1.6G`.
2. **OOM Score Adjustment:** Memberikan proteksi pada komponen inti dengan mengatur `OOMScoreAdjust=-1000` pada unit kritis (seperti database dan SSH), sehingga kernel dilarang mematikan komponen tersebut.
3. **Mekanisme Graceful Throttle:** Begitu konsumsi memori mencapai `MemoryHigh`, kernel memperlambat alokasi I/O proses tersebut secara terukur, memberikan waktu bagi sistem pemantauan untuk mengirimkan sinyal peringatan sebelum proses dimatikan paksa.

---

## 9. Trade-offs

Dalam merancang fondasi sistem otomasi infrastruktur, engineer harus memilih pendekatan arsitektural berdasarkan pertimbangan sistemik berikut:

| Pendekatan / Teknologi | Keuntungan (Pros) | Kerugian / Biaya (Cons) | Metrik Terdampak |
| :--- | :--- | :--- | :--- |
| **Systemd Native vs. Docker/Container** (Pada Single Host) | Overhead latensi mendekati 0. Akses syscall langsung tanpa abstraksi network bridge/overlay. | Tidak ada isolasi file system biner secara utuh (*chroot/rootfs layer*). Mengotori package host OS. | **Latency:** Sangat rendah.<br>**Maintenance Cost:** Tinggi saat dependencies bentrok. |
| **Atomic Symlink Deployment vs In-place Overwrite** | *Downtime* mendekati 0. Rollback dapat dilakukan secara instan cukup dengan memindahkan pointer symlink. | Memerlukan ruang disk dua kali lipat untuk menyimpan versi rilis yang lama. | **Storage Cost:** Meningkat.<br>**Recovery Time (MTTR):** Turun drastis (sub-detik). |
| **Aggressive Systemd Sandboxing** (`ProtectSystem=strict`) | Serangan RCE (*Remote Code Execution*) tidak dapat memodifikasi file biner sistem atau menginjeksi SSH keys. | Skrip/aplikasi pihak ketiga yang mencoba menulis ke direktori terproteksi (seperti `/var` atau `/tmp`) akan *crash*. | **Security Posture:** Maksimal.<br>**Engineering Latency:** Waktu debug permission meningkat. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum 1: Mengabaikan Penanganan POSIX Signals (Zombie & Orphan Procs)
- **Gejala:** Skrip deployment dijalankan ulang, tetapi port jaringan masih terkunci (`EADDRINUSE: address already in use`).
- **Akar Masalah:** Aplikasi child mengabaikan `SIGTERM` dan terus berjalan di background karena parent process mati mendadak tanpa mengeksekusi sub-process reaper.
- **Solusi:** Konfigurasikan `KillMode=mixed` pada unit systemd, atau pasang trap handler POSIX eksplisit di skrip bash:
  ```bash
  trap 'kill -TERM "$child_pid" 2>/dev/null; wait "$child_pid"' SIGTERM SIGINT
  ```

### Kesalahan Umum 2: Symlink Race Condition
- **Gejala:** Klien menerima error `404 Not Found` atau `File Not Found` saat deployment sedang berlangsung.
- **Akar Masalah:** Perintah `ln -sf /new /current` menghapus symlink lama sesaat sebelum link baru dibuat. Terdapat jeda beberapa milidetik di mana `/current` tidak eksis di Virtual File System (VFS).
- **Solusi:** Gunakan teknik pertukaran atomik dengan opsi `-T` pada Linux:
  ```bash
  ln -sfn /path/to/release-v2 /path/to/symlink.tmp
  mv -Tf /path/to/symlink.tmp /path/to/symlink
  ```

### Panduan Troubleshooting: Diagnosa Proses Menggunakan `strace`
Jika sebuah proses tiba-tiba menggantung (*hang*) tanpa mengeluarkan log:
```bash
# 1. Temukan PID dari layanan
PID=$(pgrep -f "collector")

# 2. Attach strace ke syscall yang sedang dieksekusi secara real-time
sudo strace -p "${PID}" -f -e trace=network,file,desc -s 256

# 3. Analisis:
# - Jika tertahan di futex(): Aplikasi mengalami deadlock pada level threading.
# - Jika tertahan di read(3, ...): Aplikasi menunggu I/O dari socket jaringan yang hang (lupa menyetel timeout).
```

---

## 11. Best Practices (Production Checklist)

Gunakan tabel checklist ini sebelum mempromosikan skrip atau unit konfigurasi ke cluster produksi.

| Kategori | Item Pemeriksaan | Target Standar | Status Verifikasi |
| :--- | :--- | :--- | :--- |
| **Shell Security** | Strict flags terpasang | Wajib memuat `set -euo pipefail` di awal skrip | [ ] |
| **Shell Hygiene** | Static Analysis | Lulus uji `shellcheck -S error` tanpa peringatan | [ ] |
| **Process Control** | Unprivileged Execution | Service berjalan di bawah user non-root (`User=app-user`) | [ ] |
| **Process Control** | Sandboxing Flags | `ProtectSystem=strict`, `NoNewPrivileges=yes` aktif | [ ] |
| **Resource Limits**| cgroups Throttling | Parameter `MemoryMax` dan `CPUQuota` terkonfigurasi | [ ] |
| **Lifecycle** | Graceful Shutdown | Mendukung `SIGTERM` dengan batas waktu `TimeoutStopSec` | [ ] |
| **Storage** | Atomic Switchover | Perubahan pointer direktori rilis menggunakan `mv -Tf` | [ ] |

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sistem monitoring mandiri (*Production Sentinel*) yang bertugas mengawasi performa CPU/Memori, mencatat log ke sistem secara periodik, dan diamankan di bawah kontrol ketat `systemd`.

Struktur direktori kerja:
```
hands-on/m02/
├── bin/
│   └── sentinel.sh
├── config/
│   └── sentinel.conf
├── systemd/
│   └── sentinel.service
└── Makefile
```

### Langkah 1: Buat Ruang Kerja
```bash
mkdir -p hands-on/m02/{bin,config,systemd}
cd hands-on/m02/
```

### Langkah 2: Buat Skrip Utama (`bin/sentinel.sh`)
```bash
cat << 'EOF' > bin/sentinel.sh
#!/usr/bin/env bash
set -euo pipefail

# Baca file konfigurasi
CONFIG_PATH="${SENTINEL_CONFIG:-/etc/sentinel/sentinel.conf}"
if [[ -f "${CONFIG_PATH}" ]]; then
    # shellcheck source=/dev/null
    source "${CONFIG_PATH}"
else
    INTERVAL_SECONDS=5
    METRIC_TAG="DEFAULT"
fi

shutdown_node() {
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Menghentikan Sentinel Agent secara aman..."
    exit 0
}

trap shutdown_node SIGTERM SIGINT

echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Sentinel Agent aktif. Tag: ${METRIC_TAG}, Interval: ${INTERVAL_SECONDS}s"

while true; do
    LOAD=$(awk '{print $1}' /proc/loadavg)
    MEM_FREE=$(awk '/MemAvailable/ {printf "%.2f", $2/1024}' /proc/meminfo)
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] [${METRIC_TAG}] LoadAvg: ${LOAD} | MemAvailable: ${MEM_FREE} MB"
    sleep "${INTERVAL_SECONDS}"
done
EOF
chmod +x bin/sentinel.sh
```

### Langkah 3: Buat Konfigurasi Default (`config/sentinel.conf`)
```bash
cat << 'EOF' > config/sentinel.conf
INTERVAL_SECONDS=3
METRIC_TAG="PRODUCTION-NODE-01"
EOF
```

### Langkah 4: Buat Unit File Systemd (`systemd/sentinel.service`)
```bash
cat << 'EOF' > systemd/sentinel.service
[Unit]
Description=Sentinel System Resource Watcher
After=network.target

[Service]
Type=simple
User=sentinel-svc
Group=sentinel-svc
Environment="SENTINEL_CONFIG=/etc/sentinel/sentinel.conf"
ExecStart=/usr/local/bin/sentinel.sh
Restart=on-failure
RestartSec=3s

# Security Hardening
ProtectSystem=strict
ProtectHome=yes
NoNewPrivileges=yes
PrivateTmp=yes

# Resource Limits
MemoryMax=64M
CPUQuota=20%

[Install]
WantedBy=multi-user.target
EOF
```

### Langkah 5: Buat Makefile Otomasi Instalasi (`Makefile`)
```bash
cat << 'EOF' > Makefile
SHELL := /bin/bash
.PHONY: install test verify uninstall

test:
	@echo "Menjalankan static analysis..."
	@shellcheck bin/sentinel.sh || echo "Peringatan: Install shellcheck untuk hasil optimal."

install: test
	@echo "Memulai instalasi sistem..."
	sudo id -u sentinel-svc &>/dev/null || sudo useradd -r -s /usr/sbin/nologin sentinel-svc
	sudo mkdir -p /etc/sentinel
	sudo cp config/sentinel.conf /etc/sentinel/sentinel.conf
	sudo cp bin/sentinel.sh /usr/local/bin/sentinel.sh
	sudo cp systemd/sentinel.service /etc/systemd/system/sentinel.service
	sudo chown -R sentinel-svc:sentinel-svc /etc/sentinel
	sudo chmod 644 /etc/sentinel/sentinel.conf
	sudo chmod 755 /usr/local/bin/sentinel.sh
	sudo systemctl daemon-reload
	sudo systemctl enable --now sentinel.service

verify:
	@echo "Memverifikasi integritas proses..."
	sudo systemctl status sentinel.service --no-pager
	@echo "--- Output Log Terbaru ---"
	sudo journalctl -u sentinel.service -n 5 --no-pager

uninstall:
	@echo "Mencabut instalasi layanan..."
	-sudo systemctl disable --now sentinel.service
	-sudo rm -f /etc/systemd/system/sentinel.service
	-sudo rm -f /usr/local/bin/sentinel.sh
	-sudo rm -rf /etc/sentinel
	-sudo userdel sentinel-svc
	sudo systemctl daemon-reload
EOF
```

### Langkah 6: Eksekusi dan Pengujian
Jalankan target instalasi dan lakukan verifikasi:
```bash
make install
make verify
```

---

## 13. Exercise

### Level Easy
Modifikasi skrip `bin/sentinel.sh` agar membaca metrics tambahan: persentase penggunaan storage pada direktori root (`/`). Gunakan perintah `df` atau parsing kernel info melalui `/proc/mounts`. Output log wajib menyertakan nilai `DiskRootUsed: XX%`.

### Level Medium
Tambahkan mekanisme *Log Rotation* internal sederhana: Jika output diarahkan ke file `/var/log/sentinel/agent.log`, tambahkan kontrol dalam skrip untuk memeriksa ukuran file tersebut secara periodik. Jika ukuran file melewati 5 MB, lakukan rotasi file menjadi `agent.log.1` sebelum menulis log baru. Batasi jumlah retensi maksimal hanya 3 file backup.

### Level Hard
Ubah arsitektur integrasi `sentinel.service` menjadi layanan bertipe `Type=notify`. 
- Ubah skrip shell (atau gunakan tool wrapper `systemd-notify`) untuk mengirimkan sinyal kesiapan `systemd-notify --ready` ke PID 1 hanya setelah file konfigurasi divalidasi dan iterasi pengumpulan metrik pertama berhasil dieksekusi.
- Konfigurasi parameter `WatchdogSec=10s` pada unit file `sentinel.service`. Skrip harus mengirimkan detak jantung (*keep-alive notification*) `systemd-notify --watchdog` setiap 5 detik. Jika daemon mengalami hanging/deadlock lebih dari 10 detik, pastikan systemd merestart daemon secara otomatis.

---

## 14. Challenge

### Studi Kasus: Multi-Tier Failover Daemon Tanpa Orkestrator Container

**Deskripsi Tantangan:**
Perusahaan Anda memiliki server *edge computing* di lokasi remote yang tidak memiliki kapasitas hardware yang memadai untuk menjalankan Kubernetes maupun Docker engine. Anda diminta membuat framework *self-healing* multi-proses menggunakan kapabilitas native Linux OS.

**Spesifikasi Persyaratan:**
1. **Dua Daemon Berpasangan:** Buat dua daemon independen:
   - `ingress-proxy`: Bertugas menerima request traffic.
   - `core-engine`: Bertugas memproses data.
2. **Ketergantungan Kuat (*Tight Coupling*):** Jika `core-engine` crash atau mengalami restart, `ingress-proxy` harus mendeteksi down-state tersebut dan mengembalikan status code maintenance (`503 Service Unavailable`) ke incoming traffic, alih-alih ikut crash (*graceful degradation*).
3. **Resilience & Watchdog:** Buat skrip *health-checker* independen yang berjalan via `systemd.timer` setiap 10 detik. Jika mendeteksi bahwa salah satu daemon mengonsumsi memori lebih dari 80% dari batas `MemoryMax` cgroups-nya, watchdog harus memicu *graceful restart* via `systemctl restart` secara berurutan tanpa menimbulkan *dropped connections*.
4. **Audit Trail Immutability:** Semua pergantian state dan eksekusi restart wajib dicatat ke fasilitas lokal `syslog` (`/dev/log`) menggunakan utility `logger` dengan format compliant RFC 5424.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. Apa fungsi dari opsi `set -e` dalam skrip Bash, dan kapan opsi ini gagal menghentikan eksekusi skrip?
2. Jelaskan perbedaan mendasar antara sinyal POSIX `SIGTERM` (15) dan `SIGKILL` (9)!
3. Mengapa eksekusi `mv -Tf link.tmp link` menghasilkan pergantian symlink yang bersifat *atomic* dibandingkan `ln -sf`?
4. Apa yang dimaksud dengan Ring 0 dan Ring 3 pada arsitektur prosesor x86-64 modern?
5. Direktif systemd apa yang digunakan untuk memastikan sebuah service otomatis berjalan kembali ketika mengalami crash non-zero exit code?

### Bagian 2: Intermediate (5 Soal)
6. Bagaimana cara kernel Linux menangani memory allocation ketika sebuah proses melebihi parameter `MemoryMax` pada cgroups v2?
7. Apa bahaya membiarkan proses berstatus *Zombie Process* (`<defunct>`) menumpuk di sistem, meskipun proses tersebut tidak mengonsumsi memori atau CPU?
8. Bagaimana implementasi parameter `ProtectSystem=strict` memengaruhi izin akses direktori `/etc` dan `/usr` pada runtime proses daemon?
9. Mengapa penggunaan pipe pada shell (contoh: `cmd1 | cmd2`) membutuhkan `set -o pipefail` untuk keamanan automasi pipeline CI/CD?
10. Jelaskan alur eksekusi syscall yang terjadi ketika perintah shell `cat file.txt` dijalankan dari perspektif sistem operasi!

### Bagian 3: Skenario Kasus Produksi (3 Soal)

#### Skenario Kasus A
Sebuah microservice yang dikelola oleh systemd tiba-tiba berhenti merespons traffic. Ketika Anda menjalankan `systemctl status service-api`, tercatat status: `Active: failed (Result: signal) ... Main PID: 21304 (code=killed, signal=KILL)`. Pada log aplikasi tidak ditemukan error trace apapun.
*Pertanyaan Analisis:* Langkah diagnosa apa yang harus Anda lakukan di tingkat kernel untuk membuktikan apakah proses tersebut dibunuh oleh Linux OOM Killer? Perintah kernel log apa yang spesifik untuk melacak kejadian tersebut?

#### Skenario Kasus B
Skrip deployment CI/CD Anda mengeksekusi instruksi:
```bash
systemctl restart my-worker.service
```
Namun skrip pipeline pipeline CI/CD menggantung (*timeout*) selama 90 detik sebelum akhirnya gagal. Saat diperiksa, proses worker lama masih berjalan dengan PID yang sama.
*Pertanyaan Analisis:* Parameter systemd apa pada unit service yang mengatur durasi tunggu sinyal terminasi, dan mengapa service Anda menolak untuk berhenti setelah menerima instruksi restart?

#### Skenario Kasus C
Anda memiliki script automation yang menulis log langsung ke disk lokal pada path `/var/log/app.log`. Tiba-tiba seluruh command Linux menghasilkan error `No space left on device`. Namun, saat Anda menjalankan `df -h`, kapasitas disk masih menunjukkan sisa 40% kosong.
*Pertanyaan Analisis:* Kondisi teknis apa pada filesystem Linux yang menyebabkan kegagalan ini, dan bagaimana cara mendiagnosa serta memperbaikinya?

---

## Kunci Jawaban & Panduan Evaluasi Quiz

### Bagian 1: Basic
1. `set -e` menghentikan skrip jika ada command yang menghasilkan exit code non-zero. Fitur ini gagal menghentikan eksekusi jika command yang gagal tersebut berada di dalam struktur pengkondisian (seperti blok `if`, `while`, `until`), atau berada di sisi kiri dari operator boolean `||` atau `&&`.
2. `SIGTERM` adalah sinyal software interrupt yang meminta proses mati secara sopan; proses dapat menangkap sinyal ini untuk melakukan operasi pembersihan (*cleanup*). `SIGKILL` adalah instruksi mutlak langsung ke kernel untuk menghapus tabel alokasi memori proses tersebut; aplikasi tidak dapat menangkap (*intercept*), menunda, atau mengabaikan sinyal `SIGKILL`.
3. `ln -sf` bukan operasi atomik; perintah ini menghapus pointer lama sebelum membuat pointer baru, meninggalkan celah waktu mikro di mana symlink tidak ada. Sebaliknya, `mv -Tf` memanfaatkan syscall `renameat()` atau `rename()` yang dijamin atomik oleh standar POSIX kernel Linux: direktori tujuan ditukar secara instan dalam metadata VFS.
4. Ring 0 adalah Kernel Space dengan hak istimewa penuh (kontrol instruksi hardware, alokasi memori fisik, interrupts). Ring 3 adalah User Space dengan hak terbatas, di mana aplikasi dijalankan secara terisolasi dan wajib memicu *system call* untuk meminta resource hardware.
5. `Restart=on-failure`.

### Bagian 2: Intermediate
6. Pada cgroups v2, ketika memori proses menembus batas `MemoryMax`, kernel pertama-tama akan mencoba mereklamasi memori (seperti membuang *page cache* yang tidak aktif). Jika alokasi memori anonim tetap melewati batas tersebut dan tidak ada swap yang dapat digunakan, kernel akan memicu OOM Killer internal yang hanya membunuh proses di dalam cgroup bersangkutan, bukan proses global.
7. Zombie process tidak lagi menggunakan memori aplikasi atau siklus CPU, tetapi Zombie process mempertahankan baris datanya pada Kernel Process Table. Karena sistem operasi memiliki batas maksimal PID fisik (`/proc/sys/kernel/pid_max`), tumpukan zombie process dapat memicu **PID Exhaustion**, yang mengakibatkan host tidak dapat lagi membuat proses baru apapun.
8. `ProtectSystem=strict` me-mount seluruh hirarki `/usr`, `/boot`, dan `/etc` secara *read-only* bagi proses tersebut menggunakan file system *mount namespaces*. Jika daemon mencoba memodifikasi file di direktori tersebut, kernel akan langsung mengembalikan error `EPERM` (Operation not permitted).
9. Secara default, shell hanya membaca exit code dari perintah **terakhir** pada sebuah pipeline. Jika `cmd1` crash (exit 1) tetapi `cmd2` berhasil membaca output kosong (exit 0), exit status pipeline bernilai 0 (dianggap sukses). Mengaktifkan `set -o pipefail` memaksa shell mengembalikan exit code non-zero jika salah satu perintah di dalam rantai pipeline gagal.
10. Alur syscall: Skrip shell memicu `fork()` untuk menduplikasi proses shell -> memicu `execve("/bin/cat", ...)` -> loader kernel memetakan dynamic libraries via `openat()`, `read()`, `mmap()` -> binary memanggil syscall `openat()` ke path `file.txt` -> memanggil syscall `read()` untuk memindahkan byte data dari buffer kernel ke buffer user space -> memanggil syscall `write(1, buffer)` untuk melempar byte data ke stdout file descriptor -> memanggil `exit_group()`.

### Bagian 3: Skenario Kasus Produksi
- **Kasus A:** Jalankan `dmesg -T | grep -i oom` atau periksa log kernel via `journalctl -k --grep="Out of memory"`. Analisis baris log untuk memeriksa status `oom_score`, nama proses yang dimatikan (`Killed process 21304`), dan jumlah anon-rss/page-tables yang dikonsumsi sebelum crash terjadi.
- **Kasus B:** Permasalahan terletak pada penanganan sinyal di mana service worker mengabaikan `SIGTERM`, atau thread internal aplikasi mengalami deadlock saat proses cleanup. Parameter yang mengatur batas waktu tunggu default adalah `TimeoutStopSec` (default 90 detik pada systemd). Systemd menunggu hingga timer 90 detik berakhir sebelum mengeksekusi `SIGKILL`. Solusi: Perbaiki aplikasi agar merespons `SIGTERM` dengan benar, atau perkecil nilai `TimeoutStopSec=15s` serta konfigurasikan `KillMode=mixed`.
- **Kasus C:** Sistem kehabisan **Inodes** (Metadata Storage Allocation), bukan kapasitas blok penyimpanan. Jika sebuah sistem menyimpan jutaan file berukuran 0 byte atau sangat kecil, alokasi tabel inode filesystem akan habis terpakai (100%). Diagnosa: Jalankan perintah `df -i` untuk memeriksa kolom `IUse%`. Perbaikan: Temukan direktori yang memuat tumpukan jutaan file kecil (biasanya direktori spooling/sesi PHP/cache sementara) menggunakan `find /var/ -xdev -printf '%h\n' | sort | uniq -c | sort -k 1 -n` lalu bersihkan file-file usang tersebut.

---

## 16. Summary

Fondasi rekayasa DevOps berakar pada pemahaman interaksi antara kode otomasi dan sistem operasi Linux:
1. **Arsitektur Internal:** Pahami batasan tegas antara User Space dan Kernel Space. System call adalah jembatan komunikasi, dan sinyal POSIX adalah kontrol transmisi status aplikasi.
2. **Defensive Automation:** Skrip otomasi di lingkungan enterprise wajib mematuhi standar *idempotency*, *strict execution flags* (`set -euo pipefail`), dan pembersihan resource berbasis interrupt trap handler.
3. **Enterprise Service Management:** Gantikan eksekusi aplikasi background yang rapuh dengan unit service `systemd` modern yang memanfaatkan keamanan sandboxing kernel dan isolasi resource presisi berbasis `cgroups v2`.
4. **Resilience & Observability:** Kemampuan melacak alur *syscall* melalui `strace`, mengidentifikasi batas alokasi Inode, serta menganalisis intervensi kernel OOM Killer merupakan kompetensi krusial untuk menjamin stabilitas sistem skala enterprise.