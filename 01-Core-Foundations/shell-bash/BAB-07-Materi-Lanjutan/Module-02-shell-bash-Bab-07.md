# Kurikulum Enterprise: Shell-Bash
## Kategori: 01-Core-Foundations | Bab: 07 - Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Senior Engineer / SRE diharapkan mampu:
- **Menganalisis** arsitektur internal Bash runtime: sistem pemanggilan `fork-exec`, alokasi memori Copy-on-Write (CoW), tabel *file descriptor* VFS, dan penanganan sinyal asinkron tingkat kernel.
- **Merancang dan mengimplementasikan** pola orkestrasi konkurensi tingkat lanjut menggunakan *named pipes* (FIFO), *process substitution*, *coprocesses*, dan *worker pools* berbasis primitif sistem operasi.
- **Mengembangkan** skrip otomasi berstandar industri dengan ketahanan tinggi (*zero unhandled signals*), atomic file-locking (`flock`), isolasi subshell, dan pelaporan observabilitas terstruktur (*structured JSON logging*).
- **Mendiagnosis dan memecahkan masalah** *race conditions*, *deadlocks*, *masked return codes*, dan *memory leaks* (subshell footprint) pada eksekusi skala besar di lingkungan kontainer (Kubernetes/Docker).

---

## 2. Prerequisite

Peserta didik harus memiliki pemahaman mendalam tentang:
1. Pemrograman Bash fundamental (variabel, percabangan, fungsi, array asosiatif).
2. Konsep dasar sistem operasi POSIX: proses, PID, PPID, alokasi memori pengguna vs kernel space.
3. Aliran Standar I/O (`stdin`, `stdout`, `stderr`) dan kode keluar POSIX (`exit status`).
4. Dasar administrasi sistem Linux: utilitas *coreutils* (`awk`, `sed`, `grep`, `xargs`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Model Eksekusi Proses: Fork-Exec dan Subshell Overhead
Bash adalah *command language interpreter* yang beroperasi di atas abstraksi kernel POSIX. Saat Bash mengeksekusi perintah non-builtin, runtime tidak langsung mengeksekusi binary target di memori saat ini. Runtime memanggil *system call* `fork()`, menduplikasi proses Bash saat ini menjadi proses *child*, diikuti oleh `execve()` untuk menimpa *address space child* dengan binary yang dipanggil.

```
+-------------------------------------------------------------+
|                     Bash Parent (PID: 1000)                 |
|  - Environment Variables    - Open File Descriptors (0,1,2) |
|  - Trap Vectors Table       - Shell Variables               |
+-------------------------------------------------------------+
                               |
                        fork() | (Kernel CoW page duplication)
                               v
+-------------------------------------------------------------+
|                     Bash Child (PID: 1001)                  |
|  - Cloned Context           - Temporary File Descriptors    |
+-------------------------------------------------------------+
                               |
                      execve() | (Overwrites memory segment)
                               v
+-------------------------------------------------------------+
|                    Target Binary (/bin/ls)                  |
+-------------------------------------------------------------+
```

Jika perintah dijalankan di dalam tanda kurung `( ... )`, pipeline `|`, atau *command substitution* `$( ... )`, Bash hanya memanggil `fork()` tanpa `execve()`. Ini menciptakan **subshell**:
- Subshell mewarisi *environment variables*, batasan sumber daya (`ulimit`), dan *file descriptor*.
- Modifikasi variabel internal shell, perubahan direktori kerja (`cd`), atau perubahan status trap di dalam subshell **tidak akan pernah** merambat kembali ke proses *parent*.
- *Overhead*: Pemanggilan `fork()` berulang di dalam *loop* besar memicu degradasi performa drastis akibat *context switching* dan alokasi *kernel task struct*.

### 3.2. Arsitektur File Descriptors (FD) dan Virtual File System (VFS)
Dalam kernel Linux, setiap proses memiliki *File Descriptor Table* yang merujuk ke *Open File Table* global, yang selanjutnya memetakan ke *i-node table* di VFS.
Bash mengalokasikan:
- `0`: Standard Input (`stdin`)
- `1`: Standard Output (`stdout`)
- `2`: Standard Error (`stderr`)
- `3-9`: Tersedia untuk pemesanan kustom non-eksklusif pengguna melalui deklarasi `exec`.
- `10+`: Sering digunakan secara internal oleh Bash (misal: penanganan *heredocs*, *process substitution*).

Manipulasi FD dilakukan melalui `dup2()` system call:
- `exec 3>&1`: Menduplikasi entri tabel FD 1 ke entri FD 3 (FD 3 mengarah ke target yang sama dengan FD 1 saat itu).
- `exec 1>file.log`: Mengarahkan entri FD 1 ke file baru di VFS.
- `exec 3>&-`: Menutup FD 3 (*cleanup syscall close()*).

### 3.3. Penanganan Sinyal Asinkron dan Tabel Trap
Kernel mengirimkan sinyal (`SIGTERM`, `SIGINT`, `SIGHUP`, `SIGCHLD`) ke proses dengan memodifikasi bitmask sinyal pada struktur proses di kernel.
Bash menunda eksekusi penanganan trap:
- Jika proses Bash sedang menunggu *foreground command* (proses eksternal) selesai via `waitpid()`, sinyal yang diterima Bash tidak langsung memicu fungsi trap Bash. Bash mencatat sinyal tersebut dan baru mengeksekusi handler **setelah** *foreground command* melepaskan kendali atau dihentikan oleh sinyal yang sama.
- Pengecualian: Perintah bawaan `wait` tanpa argumen akan segera diinterupsi oleh penanganan trap jika sinyal masuk. Pola ini kritikal untuk implementasi *graceful shutdown* di kontainer (PID 1).

---

## 4. Why & What

### Mengapa Bash Tingkat Lanjut Dibutuhkan di Era Cloud-Native?
Di era orkestrasi kontainer dan infrastruktur modern, muncul anggapan bahwa bahasa seperti Go atau Python sepenuhnya menggantikan Shell script. Namun secara arsitektur:
1. **Zero-Dependency Footprint**: Skrip Bash berjalan di hampir semua base image Linux tanpa kompilasi binary atau dependensi runtime eksternal (seperti Node.js atau Python runtime yang menambah puluhan/ratusan megabyte attack surface).
2. **First-Class Process Orchestration**: Menghubungkan streams I/O proses yang berbeda di Go/Python memerlukan puluhan baris *boilerplate* kode (`os/exec`, Goroutine/Thread management, channel sync). Di Bash, primitif ini adalah fitur bawaan kernel yang diekspresikan secara deklaratif dalam 1 baris pipa (`|`, `<(...)`, `> >(...)`).
3. **Container Lifecycle Hooks**: Siklus hidup Pod (`preStop`, `postStart`, *readiness probes*) di Kubernetes dieksekusi langsung oleh shell kernel instance. Kegagalan memahami interaksi subshell, `flock`, dan signal forwarding pada Bash menyebabkan proses mati secara *abrupt* (*ungraceful termination*), memicu data corruption pada cache disk atau koneksi database yang putus sepihak.

---

## 5. How (Workflow Detail)

Untuk membangun eksekusi Bash kelas enterprise yang tangguh, alur kerja di bawah wajib diikuti:

```
[Start Engine] 
       │
       ▼
[Set Strict Options] ────► set -euo pipefail, IFS=$'\n\t'
       │
       ▼
[Allocate Resources] ───► Inisialisasi Mutex (flock) & Custom FD (FD 3..9)
       │
       ▼
[Register Traps] ───────► Hubungkan EXIT, SIGINT, SIGTERM ke Cleanup Handler
       │
       ▼
[Execution Logic] ──────► Worker Pools via Named Pipe (FIFO) / Coprocess
       │
       ▼
[Collect & Join] ───────► Sinkronisasi Child Processes via 'wait'
       │
       ▼
[Exit Routine] ─────────► Evaluasi Status, Hapus Temp File/Pipes, Lepas FD
```

1. **Strict Initialization**: Pengaturan interpreter flags deterministik untuk mencegah eksekusi state cacat.
2. **Resource Locking**: Eksekusi atomic lock via file descriptor untuk menjamin skrip berstatus *singleton* jika dibutuhkan.
3. **Signal & Trap Registration**: Menjamin sumber daya sistem (file sementara, soket, background jobs) selalu dibersihkan bahkan jika skrip mengalami panik runtime atau dihentikan paksa via SIGTERM.
4. **Isolated Task Processing**: Distribusi kerja ke background jobs dengan *throttling* menggunakan token bucket berbasis FIFO.
5. **Deterministic Cleanup**: Dekonstruksi proses secara teratur, menutup seluruh FD custom, dan mengembalikan exit code yang benar.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pemipaan Air (Pipes & File Descriptors)
Bayangkan File Descriptor sebagai stopkontak atau katup bernomor di dinding:
- Stopkontak `0` membawa input air (data masuk).
- Stopkontak `1` adalah pipa pembuangan air bersih utama (output data).
- Stopkontak `2` adalah pipa pembuangan darurat (error data).
- Stopkontak `3-9` adalah katup bypass yang bisa Anda pasang sendiri untuk membelokkan aliran air ke tangki filter cadangan tanpa mengganggu pipa utama.

Jika Anda menyambungkan dua pipa secara tergesa-gesa tanpa pengatur tekanan (proses sinkronisasi), air akan meluap (*pipe buffer overflow*, default Linux: 64KB).

### Diagram Alur Token Bucket Concurrency (Worker Pool via FIFO)

```
                       +-------------------+
                       | Token Bucket      |
                       | (FIFO: /tmp/pipe) |
                       +---------+---------+
                                 |
              +------------------+------------------+
              | (Read 1 byte)    | (Read 1 byte)    | (Read 1 byte)
              v                  v                  v
       +--------------+   +--------------+   +--------------+
       |   Worker 1   |   |   Worker 2   |   |   Worker 3   |
       |  (Subshell)  |   |  (Subshell)  |   |  (Subshell)  |
       +-------+------+   +-------+------+   +-------+------+
               |                  |                  |
               | (Job Finished)   | (Job Finished)   | (Job Finished)
               +------------------+------------------+
                                  |
                                  v
                        [Write Token back to FIFO]
                                  │
                                  ▼
                         (Slot Siap Digunakan)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Mutex via Custom File Descriptor & `flock`
Menjamin sebuah skrip Bash tidak berjalan lebih dari satu instance secara bersamaan (Singleton Engine) tanpa *race condition* (menghindari antipola file `.pid`).

```bash
#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/var/lock/my_engine.lock"

# Alokasikan FD 200 dan arahkan ke lock file
exec 200>"${LOCK_FILE}"

# Lakukan eksklusif non-blocking lock pada FD 200
if ! flock -n 200; then
    echo "[CRITICAL] Instance lain sedang berjalan. Abort mission." >&2
    exit 1
fi

echo "[INFO] Lock berhasil didapatkan. Menjalankan proses inti..."
sleep 5
echo "[INFO] Selesai. FD otomatis dilepas saat proses exit."
```

### 7.2. Practical Example: Enterprise Concurrent Worker Pool & Structured Logger
Implementasi antrean kerja paralel dengan *concurrency limit*, structured logging JSON, isolasi sinyal, dan pelepasan sumber daya atomik.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Concurrent Task Processor (Worker Pool Pattern)
# Standar: Bash 4.4+ (POSIX-compliant core conventions)
# ==============================================================================

set -euo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOG_LEVEL_INFO="INFO"
readonly LOG_LEVEL_ERROR="ERROR"
readonly LOG_LEVEL_DEBUG="DEBUG"
readonly MAX_CONCURRENCY=4

# Direktori kerja aman sementara
TMP_DIR="$(mktemp -d -t "${SCRIPT_NAME}.XXXXXXXXXX")"
readonly TMP_DIR
readonly FIFO_PATH="${TMP_DIR}/worker_token.fifo"

# Custom FD 3 untuk JSON Logging Engine
exec 3>&1

# ------------------------------------------------------------------------------
# Structured Logging Function (JSON Output via FD 3)
# ------------------------------------------------------------------------------
log_json() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    
    # Escape quotes
    local escaped_msg="${message//\"/\\\"}"

    # Tulis langsung ke FD 3 tanpa mengotori FD 1 atau FD 2
    printf '{"time":"%s","level":"%s","script":"%s","pid":%d,"message":"%s"}\n' \
        "${timestamp}" "${level}" "${SCRIPT_NAME}" "$$" "${escaped_msg}" >&3
}

# ------------------------------------------------------------------------------
# Cleanup Routine
# ------------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    log_json "${LOG_LEVEL_INFO}" "Menjalankan pembersihan sumber daya internal..."
    
    # Tutup token bucket FIFO jika masih terbuka
    if [[ -e "${FIFO_PATH}" ]]; then
        exec 9>&- 2>/dev/null || true
        exec 9<&- 2>/dev/null || true
        rm -f "${FIFO_PATH}"
    fi

    # Hapus subshell temporary directory
    if [[ -d "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi

    # Hentikan semua child processes yang masih lingering
    local children
    children="$(jobs -p)"
    if [[ -n "${children}" ]]; then
        log_json "${LOG_LEVEL_DEBUG}" "Menghentikan background child jobs: ${children}"
        # Matikan sinyal bertahap: SIGTERM -> SIGKILL
        kill -s TERM ${children} 2>/dev/null || true
        wait ${children} 2>/dev/null || true
    fi

    log_json "${LOG_LEVEL_INFO}" "Proses dihentikan dengan status: ${exit_code}"
    exit "${exit_code}"
}

# Tangkap sinyal terminasi sistem untuk graceful shutdown
trap cleanup EXIT
trap 'log_json "${LOG_LEVEL_ERROR}" "Menerima SIGINT/SIGTERM!"; exit 143' INT TERM

# ------------------------------------------------------------------------------
# Initialize Concurrency Mechanism (Token Bucket via Named Pipe)
# ------------------------------------------------------------------------------
mkfifo "${FIFO_PATH}"
# Hubungkan custom FD 9 secara bidirectional read-write ke FIFO
exec 9<>"${FIFO_PATH}"

# Masukkan token awal sebanyak limit konkurensi ke dalam FIFO
for ((i = 0; i < MAX_CONCURRENCY; i++)); do
    echo >&9
done

# ------------------------------------------------------------------------------
# Task Execution Function
# ------------------------------------------------------------------------------
execute_task() {
    local task_id="$1"
    local simulated_time="$2"

    log_json "${LOG_LEVEL_INFO}" "Memulai Task-${task_id} (estimasi durasi: ${simulated_time}s)"
    
    # Simulasi eksekusi beban I/O atau Compute
    sleep "${simulated_time}"
    
    if [[ "${task_id}" == "CRASH_CASE" ]]; then
        log_json "${LOG_LEVEL_ERROR}" "Task-${task_id} mengalami kegagalan proses tak terduga!"
        return 1
    fi

    log_json "${LOG_LEVEL_INFO}" "Sukses menyelesaikan Task-${task_id}"
    return 0
}

# ------------------------------------------------------------------------------
# Main Dispatcher Engine
# ------------------------------------------------------------------------------
main() {
    log_json "${LOG_LEVEL_INFO}" "Menginisialisasi Worker Pool (Max Workers: ${MAX_CONCURRENCY})"

    # Kumpulan payload data dummy (id:duration)
    local tasks=(
        "T001:2"
        "T002:3"
        "T003:1"
        "T004:4"
        "T005:2"
        "T006:1"
        "T007:2"
    )

    for item in "${tasks[@]}"; do
        IFS=":" read -r tid duration <<< "${item}"

        # Blokir eksekusi hingga ada token tersedia di FD 9 (Named Pipe)
        read -r -u 9

        # Eksekusi task di dalam background subshell
        (
            local task_status=0
            execute_task "${tid}" "${duration}" || task_status=$?
            
            # Kembalikan token ke FD 9 setelah tugas selesai
            echo >&9
            exit "${task_status}"
        ) &
    done

    log_json "${LOG_LEVEL_INFO}" "Seluruh task telah didistribusikan. Menunggu sisa proses (synchronization barrier)..."
    
    # Tunggu seluruh background jobs rampung
    wait

    log_json "${LOG_LEVEL_INFO}" "Seluruh worker telah menyelesaikan operasi dengan sukses."
}

# Jalankan entry point utama
main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: *Graceful Termination & Drain Agent* pada Kubernetes Sidecar
**Latar Belakang**: Sebuah platform e-commerce finansial menjalankan kontainer sidecar untuk sinkronisasi token audit log lokal ke remote S3.
**Insiden Produksi**: Ketika deployment Kubernetes melakukan *Rolling Update*, Pod menerima sinyal `SIGTERM`. Skrip sidecar Bash sebelumnya langsung mati sebelum memproses buffer log yang tersisa di disk memory buffer (`/dev/shm`), menyebabkan hilangnya catatan transaksi senilai ratusan juta rupiah (audit compliance violation).

### Solusi Arsitektural:
Skrip Bash dirancang ulang untuk mengadopsi pola **Signal Interception & Buffer Drain Engine**:
1. Skrip dieksekusi sebagai PID 1 di dalam sidecar container.
2. Mencegah *immediate termination* dengan menangkap sinyal `SIGTERM`.
3. Menjalankan *flush loop* untuk memproses sisa antrean file buffer lokal sampai ukuran file 0 byte.
4. Menerapkan *timeout threshold* agar kontainer tidak terbunuh secara agresif oleh `SIGKILL` dari Kubelet (default 30 detik).

```bash
#!/usr/bin/env bash
# ==============================================================================
# Production Drain Agent: Kubernetes PreStop & Graceful Sidecar Shutdown
# ==============================================================================
set -euo pipefail

SHUTDOWN_REQUESTED=0
BUFFER_DIR="/dev/shm/audit_buffer"

handle_sigterm() {
    echo "[SYSTEM] SIGTERM diterima dari Kubelet. Memulai fase drain..."
    SHUTDOWN_REQUESTED=1
}

# Tangkap SIGTERM langsung ke Bash PID 1
trap handle_sigterm SIGTERM

drain_remaining_buffers() {
    echo "[DRAIN] Memeriksa file buffer tersisa di ${BUFFER_DIR}..."
    local remaining_files
    remaining_files="$(find "${BUFFER_DIR}" -type f -name "*.log" | wc -l)"
    
    while [[ "${remaining_files}" -gt 0 ]]; do
        echo "[DRAIN] Mentransfer ${remaining_files} file ke storage persisten..."
        # Simulasi flush batch ke cloud storage
        for file in "${BUFFER_DIR}"/*.log; do
            [[ -e "$file" ]] || break
            # Proses sinkronisasi atomik
            # aws s3 cp "$file" s3://audit-vault/ && rm -f "$file"
            rm -f "$file" # Dikosongkan sebagai simulasi
        done
        remaining_files="$(find "${BUFFER_DIR}" -type f -name "*.log" | wc -l)"
        sleep 0.5
    done
    echo "[DRAIN] Drain selesai. Seluruh buffer telah diamankan."
}

# Main Application Loop
echo "[SYSTEM] Audit Sidecar Agent aktif (PID: $$)..."
mkdir -p "${BUFFER_DIR}"

while [[ "${SHUTDOWN_REQUESTED}" -eq 0 ]]; do
    # Buat dummy log entries secara periodik
    touch "${BUFFER_DIR}/audit_$(date +%s%N).log" 2>/dev/null || true

    # CATATAN ARSITEKTURAL: Perintah 'sleep' eksternal akan memblokir trap
    # jika tidak dijalankan di background dan ditunggu dengan builtin 'wait'.
    sleep 2 &
    wait $! || true
done

# Masuk ke fase termination cleanup
drain_remaining_buffers
echo "[SYSTEM] Agent berhenti secara terkontrol. Keluar dengan kode 0."
exit 0
```

---

## 9. Trade-offs

| Dimensi | Native Shell Scripting (Bash 5.x) | Bahasa Tingkat Tinggi (Go / Rust) | Interpretasi Trade-off |
| :--- | :--- | :--- | :--- |
| **Startup Latency** | Instan (~1-3ms) | Sangat cepat (~1-5ms binary) | Bash unggul tanpa inisialisasi runtime masif, ideal untuk CLI singkat. |
| **Memory Footprint**| ~2-4MB (Per instance) | ~10-15MB (Go Runtime overhead) | Sangat ringan, namun jika ribuan subshell dibuat, CoW memory akan melonjak. |
| **Scalability & Concurrency** | Terbatas (OS processes & pipes) | Sangat tinggi (Lightweight Goroutines/Async tasks) | Bash mengalokasikan process OS nyata untuk konkurensi; Go mengalokasikan green threads. |
| **Error Handling Strictness** | Rapuh jika tanpa `set -euo pipefail` | Kuat (Type system & explicit error interface) | Bash membutuhkan disiplin tingkat tinggi untuk mencegah eksekusi berlanjut saat error. |
| **Dependency Portability** | Sangat portabel di Unix-like environment | Static single binary (Self-contained) | Go/Rust tidak memedulikan versi Bash di target machine, tapi butuh pipeline kompilasi. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Masking Exit Codes dengan Kata Kunci `local`
**Pola Cacat**:
```bash
my_func() {
    # Perintah di bawah SELALU mengembalikan status 0 karena 'local' adalah builtin yang sukses,
    # mengaburkan exit code aktual dari command substitution di dalamnya!
    local payload="$(curl -s -f https://api.internal/crash)"
}
```
**Perbaikan**:
```bash
my_func() {
    local payload
    payload="$(curl -s -f https://api.internal/crash)"
}
```

### 10.2. Penggunaan Pipeline Tanpa `pipefail`
**Pola Cacat**:
```bash
set -e
# Jika grep gagal menghasilkan match (status 1), perintah sed tetap mengembalikan 0.
# Skrip tidak akan berhenti dan terus berjalan membawa status palsu.
cat critical_data.txt | grep "SECURITY_TOKEN" | sed 's/ //g'
```
**Perbaikan**:
```bash
set -euo pipefail
cat critical_data.txt | grep "SECURITY_TOKEN" | sed 's/ //g'
```

### 10.3. Masalah Zombie Process dan Docker PID 1
Saat Bash berjalan sebagai PID 1 di dalam kontainer Docker, secara default Bash tidak memiliki *automatic child reaping mechanism*. Subshell yang menjadi *orphaned* tidak akan di-`wait` secara otomatis, menyebabkan tabel proses Linux penuh dengan proses `<defunct>` (Zombies).
**Solusi**:
Gunakan init process mikro seperti `tini` atau `dumb-init` sebagai *entrypoint*, atau gunakan `set -m` (job control) dan tangkap sinyal `SIGCHLD` dengan `wait -n`.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini saat melakukan *Code Review* pada Bash script produksi:

- [ ] **Shebang Eksplisit**: Menggunakan `#!/usr/bin/env bash` bukan `#!/bin/sh` (menghindari ketidakcocokan POSIX vs Bashisms).
- [ ] **Strict Safety Mode**: Wajib mencantumkan `set -euo pipefail` di baris teratas setelah shebang.
- [ ] **Field Separator Aman**: Tetapkan `IFS=$'\n\t'` untuk mencegah *word-splitting* liar pada spasi.
- [ ] **Quoting Disiplin**: Seluruh ekspansi variabel harus diapit tanda kutip: `"${my_var}"` (kecuali secara sadar membutuhkan ekspansi glob/array).
- [ ] **Cleanup via Traps**: Bersihkan direktori sementara (`mktemp`) dan *Named Pipes* pada event `EXIT`, `INT`, `TERM`.
- [ ] **Static Analysis**: Skrip lolos verifikasi `shellcheck -s bash --severity=style` tanpa warning.
- [ ] **Locking Mechanism**: Gunakan `flock` berbasis File Descriptor jika skrip merupakan background daemon atau berkala dieksekusi via Cron.
- [ ] **Subshell Minimization**: Hindari memanggil `cat`, `awk`, atau `sed` di dalam loop jutaan iterasi; optimalkan dengan Bash builtin parameter expansion seperti `${var##*/}` atau associative arrays.

---

## 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada sistem Linux Anda untuk disimpan di direktori `hands-on/m02/`.

### Langkah 1: Persiapan Struktur Direktori
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 2: Membuat File Implementasi IPC Buffer
Buat file `hands-on/m02/ipc_coprocess.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Luncurkan Coprocess sebagai Worker Asinkron
# Coprocess mengeksekusi stream processor di background dengan pipe dua arah
coproc HASH_ENGINE {
    while read -r line; do
        if [[ "${line}" == "QUIT" ]]; then
            break
        fi
        # Hitung sha256 checksum secara instan di memori
        sha256sum <<< "${line}" | awk '{print $1}'
    done
}

echo "[ORCHESTRATOR] Coprocess aktif dengan PID: ${HASH_ENGINE_PID}"

# FD HASH_ENGINE[1] adalah STDIN dari coprocess
# FD HASH_ENGINE[0] adalah STDOUT dari coprocess

# 2. Kirim Pesan ke Coprocess
echo "PayloadDataAlpha" >&"${HASH_ENGINE[1]}"
read -r response_alpha <&"${HASH_ENGINE[0]}"
echo "[RESULT-1] Hash Alpha: ${response_alpha}"

echo "PayloadDataBeta" >&"${HASH_ENGINE[1]}"
read -r response_beta <&"${HASH_ENGINE[0]}"
echo "[RESULT-2] Hash Beta: ${response_beta}"

# 3. Hentikan Coprocess secara Teratur
echo "QUIT" >&"${HASH_ENGINE[1]}"
wait "${HASH_ENGINE_PID}"

echo "[ORCHESTRATOR] Coprocess sukses dinonaktifkan."
```

### Langkah 3: Eksekusi dan Verifikasi
```bash
chmod +x hands-on/m02/ipc_coprocess.sh
./hands-on/m02/ipc_coprocess.sh
```

---

## 13. Exercise

### Level Easy: Safe Redirection Isolation
Tulis skrip `safe_log_fd.sh`. Buka File Descriptor kustom `4` yang merujuk ke file `/tmp/audit_stream.log`. Buat fungsi logging yang menulis pesan secara terisolasi ke FD 4, tanpa mencemari stdout maupun stderr. Tutup FD 4 di akhir skrip menggunakan mekanisme pelepasan ekspresi bash `exec 4>&-`.

### Level Medium: Parallel Rate-Limited Downloader
Rancang skrip `parallel_fetcher.sh` yang menerima daftar 10 URL (gunakan endpoint mock HTTP). Terapkan worker pool berbasis FIFO untuk membatasi proses unduhan maksimum 3 proses bersamaan. Tampilkan metrik durasi waktu eksekusi total menggunakan variabel bawaan `${SECONDS}`.

### Level Hard: Dynamic IPC Multi-Worker with Health Checks
Bangun skrip `supervised_workers.sh`. Skrip memelihara 2 coprocess pekerja konstan. Orchestrator membagikan job stream secara round-robin. Jika salah satu coprocess mati secara tak terduga (simulasikan dengan mengirimkan perintah fatal atau terminasi PID pekerja dari luar), orchestrator harus mendeteksi sinyal `SIGCHLD`, me-restart pekerja tersebut secara otomatis, dan mendistribusikan ulang antrean tanpa kehilangan pesan yang sedang diproses.

---

## 14. Challenge

### Tantangan Arsitektur: Pure Bash Write-Ahead-Log (WAL) State Machine
**Konteks**: Anda diinstruksikan membangun sistem cache *key-value in-memory* menggunakan Bash 5.x tanpa dependensi binary pihak ketiga apa pun (dilarang menggunakan SQLite, Redis, Python, dsb.).
**Spesifikasi Persyaratan**:
1. Menggunakan **Associative Array** internal sebagai *in-memory datastore*.
2. Membuka **Coprocess** atau **FIFO IPC Interface** yang menerima perintah:
   - `SET <key> <val>`
   - `GET <key>`
   - `DEL <key>`
   - `SNAPSHOT`
3. Seluruh mutasi state (`SET`, `DEL`) harus dicatat secara sinkron ke dalam berkas **WAL (Write-Ahead-Log)** menggunakan append-only File Descriptor sebelum associative array diupdate.
4. Skrip harus mampu bertahan dari interupsi paksa (`SIGKILL` yang disimulasikan). Pada saat start-up, skrip harus melakukan fase **Crash Recovery**: membaca berkas WAL dari awal untuk merekonstruksi seluruh data state ke associative array sebelum membuka interface untuk menerima request baru.
5. Menjamin konkurensi multi-client yang aman menggunakan *non-blocking atomic file lock* (`flock`).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi dari opsi `set -o pipefail` di Bash?
   - A. Membuat pipeline berjalan paralel di multi-core CPU.
   - B. Mengembalikan status error (non-zero) dari perintah terakhir dalam pipeline yang gagal.
   - C. Mencegah error syntax menghentikan skrip.
   - D. Menghubungkan stderr ke pipeline berikutnya secara default.
   *Jawaban: B. Tanpa pipefail, exit code pipeline adalah exit code perintah terakhir, meskipun perintah di awal atau tengah pipeline gagal.*

2. File descriptor default berapakah yang digunakan untuk `stderr`?
   - A. 0
   - B. 1
   - C. 2
   - D. 3
   *Jawaban: C. Standar POSIX memetakan 0=stdin, 1=stdout, 2=stderr.*

3. Apa efek samping dari mengeksekusi subshell dengan tanda kurung `( cd /tmp && rm -f test.log )`?
   - A. Direktori kerja dari skrip shell utama berubah menjadi `/tmp`.
   - B. Direktori kerja dari skrip shell utama TIDAK berubah setelah blok subshell selesai.
   - C. Variabel lingkungan di luar subshell akan otomatis terhapus.
   - D. Subshell akan langsung berjalan di background secara asinkron.
   *Jawaban: B. Subshell menduplikasi process space; pemanggilan `cd` hanya mengubah environment child process.*

4. Perintah manakah yang digunakan untuk menutup File Descriptor kustom `3`?
   - A. `close 3`
   - B. `exec 3>&-`
   - C. `exit 3`
   - D. `rm /dev/fd/3`
   *Jawaban: B. Sintaks POSIX Bash untuk menutup file descriptor adalah `exec <FD>&-`.*

5. Apa fungsi variabel internal `$!` dalam Bash?
   - A. Menampilkan exit status dari proses terakhir.
   - B. Menampilkan PID dari proses background (asinkron) terakhir.
   - C. Menampilkan pesan error terakhir dari sistem.
   - D. Menampilkan argumen terakhir dari baris perintah.
   *Jawaban: B. `$!` menyimpan PID dari background job terbaru.*

### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. **Kasus**: Diberikan baris kode: `result=$(cat file.txt | grep "user")`. Jika `file.txt` tidak ada dan `set -e` aktif tanpa `pipefail`, apakah skrip akan langsung berhenti? Jelaskan.
   *Jawaban: Tidak. Karena `cat` mengembalikan exit code 1, tetapi `grep` menerima input kosong dan mengembalikan exit code 1. Namun jika perintah terakhir pada pipeline berhasil (misal: piping lanjut ke perintah yang sukses), skrip tetap berjalan. Lebih penting lagi, jika tanpa `pipefail`, status akhir hanya ditentukan perintah terakhir dari pipeline.*

7. **Kasus**: Mengapa pola `while read line; do ((count++)); done < <(grep pattern file.txt)` mempertahankan nilai `$count`, sedangkan `grep pattern file.txt | while read line; do ((count++)); done` membuat `$count` tetap 0 di luar loop?
   *Jawaban: Pada pola pipeline (`|`), Bash mengeksekusi sisi kanan pipa di dalam subshell terpisah (pada kebanyakan konfigurasi Bash default), sehingga mutasi `$count` hilang saat subshell selesai. Pola Process Substitution (`< <(...)`) menjalankan loop `while` di dalam shell utama.*

8. **Kasus**: Apa perbedaan fundamental penanganan concurrency antara background tasks biasa `cmd &` dengan `coproc cmd`?
   *Jawaban: `cmd &` melepaskan proses ke background dengan komunikasi satu arah via file/pipe standar tanpa pemetaan FD otomatis. `coproc` mendirikan komunikasi IPC bidirectional terotomatisasi, menghasilkan pasangan File Descriptor (`${NAME[0]}` untuk membaca, `${NAME[1]}` untuk menulis).*

9. **Kasus**: Mengapa menggunakan file `.pid` (menyimpan PID di file teks) untuk locking proses sering memicu *race condition* dibandingkan `flock`?
   *Jawaban: Operasi baca-periksa-tulis pada file teks biasa bukan operasi atomik di tingkat kernel. Dua proses dapat membaca ketiadaan file di saat bersamaan dan keduanya mengklaim lock. `flock` mengandalkan system call kernel (`flock()` / `fcntl()`) yang dieksekusi secara atomik di File Table VFS.*

10. **Kasus**: Apa yang terjadi jika sebuah trap didaftarkan pada sinyal `SIGKILL` (`trap cleanup SIGKILL`)?
    *Jawaban: Trap tidak akan pernah terpanggil. Berdasarkan spesifikasi kernel POSIX, sinyal `SIGKILL` (sinyal 9) dan `SIGSTOP` tidak dapat ditangkap, diblokir, atau diabaikan oleh proses pengguna apa pun.*

### Bagian 3: Evaluasi Kasus Produksi Riil
11. **Skenario 1**: Sebuah cron job bash pembersih data berjalan setiap 5 menit:
    ```bash
    #!/bin/bash
    set -e
    flock -x -w 10 /tmp/cleaner.lock -c "python3 /opt/cleaner.py"
    ```
    Tiba-tiba sistem mengalami lonjakan *zombie process* ratusan thread dan beban sistem melonjak tajam setelah Python script hang pada I/O network database. Apa kelemahan arsitektur ini dan perbaikannya?
    *Solusi Arsitektural*: Perintah `flock` menunggu 10 detik (`-w 10`), namun jika Python hang setelah lock didapatkan, tidak ada *timeout ceiling* pada eksekusi perintah Python itu sendiri. Instance berikutnya akan menumpuk di antrean memori. Solusi: Gunakan utilitas `timeout` di dalam subshell lock: `flock -x -w 10 /tmp/cleaner.lock timeout 60s python3 /opt/cleaner.py`.*

12. **Skenario 2**: Anda menjalankan skrip orkestrasi di Kubernetes. Saat Pod diterminasi, Kubelet mengirim `SIGTERM`. Log aplikasi menunjukkan bahwa proses child yang dijalankan oleh skrip Anda langsung terputus secara kotor (*dirty abort*), bukan menyelesaikan tugasnya.
    ```bash
    #!/usr/bin/env bash
    set -e
    ./run_worker_node.bin
    ```
    Jelaskan mengapa skrip di atas tidak meneruskan sinyal dan bagaimana solusinya.
    *Solusi Arsitektural*: Script Bash bertindak sebagai *parent process*. Ketika menerima `SIGTERM`, ia tidak otomatis meneruskannya ke child process (`run_worker_node.bin`) jika tidak dikonfigurasi dengan trap aktif, atau lebih buruk lagi, binary tersebut dijalankan secara blocking di foreground. Solusi: Gunakan `exec ./run_worker_node.bin` sehingga proses binary menimpa proses shell secara langsung (mengambil alih PID 1), memungkinkannya menerima `SIGTERM` langsung dari Kubelet.*

13. **Skenario 3**: Sebuah batch worker shell script memproses ribuan file gambar menggunakan ImageMagick:
    ```bash
    for img in /mnt/images/*.jpg; do
        convert "$img" -resize 50% "/mnt/thumbnails/$(basename "$img")" &
    done
    wait
    ```
    Saat dieksekusi dengan 50.000 gambar, server mengalami Kernel Panic: *Out of Memory (OOM)* atau `fork: Resource temporarily unavailable`. Identifikasi akar masalah internal Linux dan berikan pola arsitektur Bash yang tepat.
    *Solusi Arsitektural*: Akar masalahnya adalah pembentukan 50.000 proses secara instan di background (`&`). Ini memicu fork bomb yang melampaui batas kernel `max user processes` (`ulimit -u`) dan menghabiskan memori RAM/Paging table. Solusinya adalah mengubah skrip menjadi pola *Throttled Worker Pool* (seperti pada bab 7.2) dengan membatasi proses aktif maksimum sesuai jumlah vCPU sistem (misal: 4 atau 8 worker concurrently).*

---

## 16. Summary

Implementasi Bash pada arsitektur perangkat lunak modern menuntut standar rekayasa yang setara dengan bahasa pemrograman sistem lainnya. Melalui penguasaan:
1. **Model Eksekusi Kernel**: Pemahaman batas pemisah antara kernel space dan user space, duplikasi tabel proses lewat `fork-exec`, dan isolasi status subshell.
2. **Manipulasi File Descriptor (I/O Multiplexing)**: Memanfaatkan saluran komunikasi di luar standar 0, 1, dan 2 untuk mengalirkan metrik atau log terstruktur secara independen.
3. **Konkurensi Terkontrol**: Menggantikan *uncontrolled background jobs* dengan *Token Bucket Pattern* berbasis FIFO atau coprocess terisolasi.
4. **Resiliensi dan Determinisme**: Menerapkan `set -euo pipefail` serta interceptor sinyal trap sistemik (`SIGTERM`, `EXIT`) guna menjamin *graceful shutdown* dan pembersihan sumber daya secara atomik di ekosistem kontainer enterprise.