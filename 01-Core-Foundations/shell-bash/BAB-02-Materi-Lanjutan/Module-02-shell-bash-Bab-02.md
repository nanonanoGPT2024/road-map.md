# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis & Mengontrol Eksekusi Proses Internal**: Membedakan semantik *subshell fork-exec*, *in-process execution*, dan *process substitution* pada kernel Linux untuk mengeliminasi *variable masking* dan *memory leak*.
2. **Mengonfigurasi Manipulasi File Descriptor Lanjutan**: Mengimplementasikan multiplexing I/O menggunakan File Descriptor (FD 3–9) kustom untuk pemisahan *stream logging*, *telemetry*, dan *data payload*.
3. **Membangun Sistem Konkurensi & Semaphore**: Mengembangkan *worker pool* asinkron murni Bash dengan kontrol konkurensi berbasis *POSIX FIFO (named pipes)* dan *atomic locking* (`flock`).
4. **Menerapkan Mekanisme Resiliensi & Signal Handling Produksi**: Mengabstraksi *fault-tolerance engine* berbasis sinyal POSIX (`SIGTERM`, `SIGINT`, `SIGCHLD`, `ERR`, `EXIT`) dengan *call stack tracing* deterministik.
5. **Mendesain Enterprise Deployment Orchestrator**: Menyusun skrip otomasi *zero-downtime* dengan prinsip idempotensi, atomisitas, dan verifikasi integritas data state.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:

*   Sintaks dasar Bash: pengkondisian `[[ ... ]]`, iterasi, fungsi, dan manipulasi parameter `${var:-default}`.
*   Konsep sistem operasi Linux: Struktur memori proses, File Descriptors (0: STDIN, 1: STDOUT, 2: STDERR), virtual filesystem `/proc`, dan POSIX Signals.
*   Utilitas standar POSIX: `grep`, `sed`, `awk`, `find`, `xargs`, `cut`, `sort`, `tr`.
*   Akses ke lingkungan Linux (Ubuntu 22.04 LTS / RHEL 9) dengan Bash versi minimum 5.0 (`bash --version`).

---

## 3. Concept & Internal Architecture

### 3.1. Linux Process Model & Bash Execution Engine

Ketika Bash menjalankan perintah, engine shell menentukan jalur eksekusi berdasarkan kategori instruksi: *builtin*, *function*, atau *external binary*. 

```
                                    +----------------------+
                                    |    Bash Parser       |
                                    +----------+-----------+
                                               |
                     +-------------------------+-------------------------+
                     |                                                   |
             [ Builtin / Function ]                              [ External Binary ]
                     |                                                   |
          +----------v----------+                             +----------v----------+
          | Same Memory Space   |                             | sys_clone / fork()  |
          | (No Process Spawn)  |                             +----------+----------+
          +---------------------+                                        |
                                                              +----------v----------+
                                                              | COW Memory Page     |
                                                              +----------+----------+
                                                              |      execve()       |
                                                              +---------------------+
```

1. **Fork-Exec Lifecycle**:
   * Bash memanggil *syscall* `clone()` atau `fork()` untuk membuat *child process*.
   * Kernel mengalokasikan Process Control Block (PCB) baru dan menduplikasi *page table* parent via *Copy-on-Write* (COW).
   * Child process mengeksekusi `execve()`, menggantikan segmen memori (text, data, bss, stack, heap) dengan biner target.
2. **Subshell Spawning Mechanism**:
   * Dieksekusi melalui tanda kurung `( ... )`, *pipeline* `cmd1 | cmd2`, ekspresi *command substitution* `$( ... )`, atau *asynchronous execution* `cmd &`.
   * Subshell menduplikasi seluruh *environment*, variabel, dan status shell saat itu, **tetapi mutasi variabel di dalam subshell tidak dapat dipropagasi kembali ke parent process**.
3. **In-Process Sourcing**:
   * Dieksekusi melalui `source script.sh` atau `. script.sh`.
   * Shell mengevaluasi *Abstract Syntax Tree* (AST) dari file target secara langsung di dalam ruang memori dan konteks proses shell yang aktif.

---

### 3.2. File Descriptor Table & Process Substitution

Setiap proses di Linux memiliki tabel File Descriptor di `/proc/$$/fd/`. Bash secara *default* membuka tiga FD:

* `0`: `stdin`
* `1`: `stdout`
* `2`: `stderr`

Bash mendukung alokasi FD kustom dari index `3` sampai `9` (dan dinamis hingga batas `ulimit -n`).

```
Process Table Entry ($$)
+------------------------------------------+
| File Descriptor Table                    |
| Index | Pointer ke File Description (VFS)|
|-------|----------------------------------|
| 0     | -> /dev/pts/1 (Keyboard input)   |
| 1     | -> /dev/pts/1 (Terminal output)  |
| 2     | -> /var/log/app.err              |
| 3     | -> /var/log/app.audit (Custom FD)|
| 4     | -> /tmp/pipe.fifo   (FIFO Read)  |
+------------------------------------------+
```

#### Process Substitution (`<(cmd)` dan `>(cmd)`)
Process substitution menghubungkan output atau input perintah lain menggunakan *anonymous pipe* atau *named stream* di `/dev/fd/<n>`. 

* `<(command)`: Kernel membuat pipe, menjalankan `command` dengan stdout diarahkan ke pipe, lalu menggantikan `<(...)` dengan nama path `/dev/fd/<n>`. Skrip membaca path tersebut layaknya file biasa.
* Perbedaan esensial dengan pipeline biasa:
  ```bash
  # ANTI-PATTERN: Subshell memutus transmisi variabel ke parent
  TOTAL_COUNT=0
  cat data.csv | while read -r line; do
      ((TOTAL_COUNT++))
  done
  echo "$TOTAL_COUNT" # Tetap 0 karena loop berjalan di subshell pipeline!

  # PRODUCTION-PATTERN: Process Substitution mengeksekusi loop di parent context
  TOTAL_COUNT=0
  while read -r line; do
      ((TOTAL_COUNT++))
  done < <(cat data.csv)
  echo "$TOTAL_COUNT" # Nilai terakumulasi dengan benar
  ```

---

### 3.3. Signal Propagation Engine & Trap Interrupt Handling

Sinyal POSIX adalah mekanisme interupsi asinkron tingkat kernel. Ketika kernel mengirimkan sinyal ke proses:

1. Kernel menandai bitmask *pending signal* pada PCB proses.
2. Saat shell berpindah dari *kernel-space* ke *user-space*, shell memeriksa bitmask sinyal.
3. Jika shell mendefinisikan `trap 'action' SIGNAL`, eksekusi alur utama ditunda sementara handler dieksekusi.

```
Incoming Signal (SIGTERM)
        |
        v
+------------------+     Trap Defined?
| Kernel POSIX Bus +-----------------------+
+------------------+                       |
                                           |
                   +-----------------------v-----------------------+
                   | YES                                        NO |
                   v                                               v
        +----------------------+                        +----------------------+
        | Execute Trap Handler |                        | Run Default Action   |
        | - Cleanup IPC/FIFO   |                        | (Terminate Process   |
        | - Release flock      |                        |  Immediately)        |
        | - Exit with 128+N    |                        +----------------------+
        +----------------------+
```

Bash mematuhi standar exit code: **Exit Code = 128 + Signal Number**.
* `SIGINT` (Signal 2)  -> Exit code `130`
* `SIGTERM` (Signal 15) -> Exit code `143`

---

## 4. Why & What

| Kebutuhan Enterprise | Pendekatan Konvensional (Naif) | Pendekatan Enterprise (Bash Arsitektural) |
| :--- | :--- | :--- |
| **Error Propagation** | Mengharapkan skrip berhenti sendiri tanpa validasi per step. | Strict execution flags: `set -Eeuo pipefail` ditambah trap global `ERR`. |
| **Synchronization** | File flag manual: `touch /tmp/app.lock` (Rentan *race condition*). | Atomic file lock kernel-level via `flock(2)` terikat ke File Descriptor. |
| **Process Control** | Menjalankan *background job* tanpa batas (`&`) yang memicu OOM Killer. | Strict concurrency semaphore pool berbasis *POSIX FIFOs*. |
| **Pemisahan Log Stream** | Menggabungkan *payload data* dan log operasional ke `stdout`. | Dedicated File Descriptors (FD 3 untuk audit, FD 4 untuk metrics, FD 1/2 untuk data standard). |
| **Cleanup Garansi** | Menaruh logika cleanup di baris paling bawah skrip. | Trap registration deterministik pada pseudo-signal `EXIT`. |

---

## 5. How (Workflow Detail)

### 5.1. Alur Eksekusi Skrip Resilien

```
  +------------------------------------------------------------+
  |                   1. Runtime Initialization                |
  |  - set -Eeuo pipefail                                      |
  |  - Bind TRAP signals: EXIT, ERR, SIGINT, SIGTERM           |
  +-----------------------------+------------------------------+
                                |
                                v
  +------------------------------------------------------------+
  |              2. Mutual Exclusion Enforcement               |
  |  - Open FD 200 ke /var/run/lockfile.lock                   |
  |  - flock -xn 200 (Non-blocking check)                      |
  |  - Reject concurrency jika lock sudah dipegang             |
  +-----------------------------+------------------------------+
                                |
                                v
  +------------------------------------------------------------+
  |             3. Resource & Pipeline Allocation              |
  |  - Init anonymous/named pipes untuk concurrency control     |
  |  - Setup custom descriptor (FD 3: Structured Logging)       |
  +-----------------------------+------------------------------+
                                |
                                v
  +------------------------------------------------------------+
  |                 4. Bounded Parallel Processing             |
  |  - Token consumption via FIFO read                         |
  |  - Fork worker ke background (&)                           |
  |  - Return token ke FIFO on worker completion               |
  +-----------------------------+------------------------------+
                                |
                                v
  +------------------------------------------------------------+
  |                    5. Atomic Teardown                      |
  |  - Trap EXIT terpanggil secara deterministik               |
  |  - Release FD 200 flock, flush buffer, purge temp files    |
  +------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konveyor Pabrik Multijalur dengan Emergency Breaker

Bayangkan sebuah pabrik manufaktur modern:
* **Proses Standar**: Ban berjalan tunggal. Jika satu paket jatuh di tengah, operator tidak tahu dan mesin di ujung tetap berjalan memproses kotak kosong (**Bash tanpa `pipefail`**).
* **Enterprise Bash**: Setiap stasiun memiliki sensor optik.
  * **File Descriptors**: Jalur konveyor utama (FD 1) membawa produk jadi. Konveyor samping (FD 2) membuang sisa scrap material. Konveyor khusus (FD 3) membawa log audit ke ruang kontrol supervisor.
  * **Flock**: Kunci fisik pintu utama; hanya satu tim operator yang boleh berada di area mesin dalam satu waktu.
  * **Trap**: Sakelar pemutus darurat (*emergency circuit breaker*). Kapan pun sensor mendeteksi anomali, sistem sentral membunyikan alarm, menyapu seluruh scrap, dan mematikan daya mesin secara bertahap tanpa merusak komponen.

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Manipulasi File Descriptor Kustom

Contoh ini menunjukkan cara membuka, menulis, dan menutup FD tanpa merusak STDOUT/STDERR sistem.

```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET_LOG="/tmp/audit_stream.log"

# Buka FD 3 terhubung ke file target dalam mode append
exec 3>>"${TARGET_LOG}"

# Output standar terminal
echo "Status: Memulai operasi sistem."

# Menulis secara eksklusif ke File Descriptor 3
echo "AUDIT: [$(date --iso-8601=seconds)] Aksi dilakukan oleh UID: ${EUID}" >&3

# Output standar terminal tetap bersih
echo "Status: Operasi selesai tanpa polusi output audit."

# Tutup FD 3
exec 3>&-
```

---

### 7.2. Practical Example: Enterprise Graceful Worker Daemon

Skrip produksi di bawah mengimplementasikan *PID locking*, pembatasan konkurensi (semaphore) menggunakan FIFO, penanganan sinyal (`SIGTERM`/`SIGINT`), logging berbasis JSON, dan pelacakan error call stack via trap `ERR`.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Task Dispatcher Engine
# Architecture: Asynchronous Non-blocking Worker Pool with FIFO Concurrency Control
# ==============================================================================

# Defensive Execution Preamble
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Global Constants
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOCK_FILE="/tmp/${SCRIPT_NAME}.lock"
readonly MAX_CONCURRENCY=4
readonly LOG_FD=3

# State tracking
declare -a WORKER_PIDS=()
FIFO_PATH=""

# ------------------------------------------------------------------------------
# Logging Subsystem (Direct writes to LOG_FD)
# ------------------------------------------------------------------------------
init_logging() {
    exec 3>&1
}

log_json() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    
    # Escape quotes in message
    local clean_msg="${message//\"/\\\"}"
    
    printf '{"timestamp":"%s","level":"%s","script":"%s","pid":%d,"message":"%s"}\n' \
        "${timestamp}" "${level}" "${SCRIPT_NAME}" "$$" "${clean_msg}" >&"${LOG_FD}"
}

# ------------------------------------------------------------------------------
# Error Tracing Subsystem
# ------------------------------------------------------------------------------
error_handler() {
    local line_no="$1"
    local error_code="$2"
    local command="$3"
    
    log_json "FATAL" "Command '${command}' failed at line ${line_no} with exit code ${error_code}"
    
    # Stack Trace Unrolling
    local frame=0
    while caller_info=($(caller "$frame")); do
        log_json "TRACE" " -> Source: ${caller_info[2]}:${caller_info[0]} in function '${caller_info[1]}'"
        ((frame++))
    done
}

# ------------------------------------------------------------------------------
# Cleanup & Signal Traps
# ------------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    trap - EXIT ERR SIGINT SIGTERM
    
    log_json "INFO" "Executing termination cleanup sequence (Current Exit Code: ${exit_code})..."
    
    # Terminate active background workers
    if [[ ${#WORKER_PIDS[@]} -gt 0 ]]; then
        for pid in "${WORKER_PIDS[@]}"; do
            if kill -0 "${pid}" 2>/dev/null; then
                log_json "WARN" "Terminating orphan worker PID: ${pid}"
                kill -TERM "${pid}" 2>/dev/null || true
            fi
        done
        # Tunggu pelepasan resource child process
        wait "${WORKER_PIDS[@]}" 2>/dev/null || true
    fi

    # Cleanup Named Pipe / Semaphore
    if [[ -n "${FIFO_PATH}" && -p "${FIFO_PATH}" ]]; then
        exec 7<&- || true
        exec 7>&- || true
        rm -f "${FIFO_PATH}"
    fi

    # Release FD 200 (Flock)
    exec 200>&- || true
    rm -f "${LOCK_FILE}"

    log_json "INFO" "Execution context safely closed."
    exit "${exit_code}"
}

# ------------------------------------------------------------------------------
# Mutual Exclusion (Flock)
# ------------------------------------------------------------------------------
acquire_lock() {
    exec 200>"${LOCK_FILE}"
    if ! flock -n 200; then
        log_json "ERROR" "Proses instance lain terdeteksi sedang berjalan. Lock ${LOCK_FILE} aktif."
        exit 11
    fi
}

# ------------------------------------------------------------------------------
# Concurrency Semaphore Initialization
# ------------------------------------------------------------------------------
init_semaphore() {
    local slots="$1"
    FIFO_PATH="$(mktemp -u /tmp/worker_semaphore.XXXXXX)"
    mkfifo "${FIFO_PATH}"
    
    # Buka stream Read/Write pada FD 7
    exec 7<>"${FIFO_PATH}"
    # Unlink segera: file tetap terbuka selama FD 7 aktif, hilang otomatis saat shutdown
    rm -f "${FIFO_PATH}"

    # Isi semaphore token sejumlah concurrency slots
    for ((i = 0; i < slots; i++)); do
        printf '\n' >&7
    done
}

# ------------------------------------------------------------------------------
# Worker Payload (Isolated Task)
# ------------------------------------------------------------------------------
execute_task() {
    local task_id="$1"
    local duration="$2"
    
    log_json "INFO" "Worker [${task_id}] execution started. Processing duration: ${duration}s"
    sleep "${duration}"
    
    if [[ "${task_id}" == "CRASH_TRIGGER" ]]; then
        # Simulasi kegagalan kritis tak terduga
        return 42
    fi
    
    log_json "INFO" "Worker [${task_id}] processing complete."
}

# ------------------------------------------------------------------------------
# Core Orchestration Flow
# ------------------------------------------------------------------------------
main() {
    init_logging
    
    # Bind Traps
    trap 'error_handler ${LINENO} $? "${BASH_COMMAND}"' ERR
    trap cleanup EXIT SIGINT SIGTERM
    
    acquire_lock
    log_json "INFO" "Lock acquired. Initializing worker pool with concurrency limit: ${MAX_CONCURRENCY}"
    
    init_semaphore "${MAX_CONCURRENCY}"
    
    # Dummy workload: TaskID:Duration
    local tasks=("T1:2" "T2:3" "T3:1" "T4:4" "T5:2" "T6:1")
    
    for task_def in "${tasks[@]}"; do
        IFS=":" read -r task_id duration <<< "${task_def}"
        
        # Ambil token dari semaphore (Block sampai ada slot)
        read -r -u 7
        
        # Eksekusi worker di background
        (
            local worker_exit=0
            execute_task "${task_id}" "${duration}" || worker_exit=$?
            
            # Kembalikan token ke FD 7
            printf '\n' >&7
            exit "${worker_exit}"
        ) &
        
        local child_pid=$!
        WORKER_PIDS+=("${child_pid}")
        log_json "DEBUG" "Dispatched task ${task_id} on PID ${child_pid}"
    done
    
    # Tunggu seluruh child processes menyelesaikan task
    for pid in "${WORKER_PIDS[@]}"; do
        wait "${pid}"
    done
    
    log_json "INFO" "Seluruh background batch job berhasil diproses."
}

main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Zero-Downtime Rolling Asset Deployment & Canary Sync Engine

* **Konteks**: Sistem delivery frontend berskala besar dengan ribuan static assets yang harus disinkronkan ke 40 server edge CDN lokal melalui rsync parallel, dengan batasan ketat: kegagalan di satu node tidak boleh merusak metadata deployment, dan update rsync harus *atomic* melalui *symlink swap*.
* **Tantangan**: Skrip deployment lama mengalami kegagalan proses di tengah jalan (*network timeout*), meninggalkan file locks basi, dan zombie workers menghabiskan pool koneksi SSH.

### Solusi Bash Architecture:

```
[Release Manifest] 
       |
       v
+------------------+
| Deploy Controller|
+--------+---------+
         |
         +--- FD 200: flock (/var/run/deploy.lock)
         +--- FD 7  : Semaphore Concurrency Queue (Default: 8 Workers)
         |
         +=======================================+
         | Process Pool (Process Substitution)   |
         | Target parsing stream < <(read_hosts) |
         +=======================================+
                         |
         +---------------+---------------+
         | (Worker 1)    | (Worker 2)    | (Worker N)
         v               v               v
   [Edge Node 01]  [Edge Node 02]  [Edge Node 40]
   - Atomic Rsync  - Atomic Rsync  - Atomic Rsync
   - Remote Test   - Remote Test   - Remote Test
   - Symlink Swap  - Symlink Swap  - Symlink Swap
         |               |               |
         +---------------+---------------+
                         |
                         v
                [Trap Evaluator]
          - Success: Update Canary Hash
          - Failure: Call Remote Rollback Hook
```

Skrip menggunakan *process substitution* untuk *streaming parsing host list*, memvalidasi integritas sha256 paket rsync di memory buffer, dan melakukan atomically dynamic switch menggunakan `ln -sfn` via remote shell execution.

---

## 9. Trade-offs

Menggunakan Bash tingkat lanjut untuk sistem otomatisasi produksi memiliki konsekuensi rekayasa yang harus dipertimbangkan secara objektif:

| Aspek | Advanced Pure Bash | Python / Go Binary |
| :--- | :--- | :--- |
| **Performance & Parsing Overhead** | Forking subshell (`$(...)`, pipelines) mengeksekusi *heavy syscalls* (`clone`, `execve`). Lambat untuk manipulasi string per-karakter jutaan kali. | Jauh lebih cepat. Go terkompilasi murni, Python mengeksekusi operasi string di level VM C tanpa fork berulang. |
| **Footprint & Dependencies** | **Nol Dependency**. Berjalan di initramfs, container minimalis (Alpine/Debian Slim), atau recovery environment tanpa runtime eksternal. | Membutuhkan runtime Python (50MB+) atau dynamic libraries (kecuali Go static binary). |
| **State & Concurrency Control** | Primitive. Mengandalkan kernel abstractions (Signals, IPC FIFOs, File Descriptors). Sulit mengelola kompleksitas shared memory. | First-class citizen (Goroutines, Channels, Threads, Mutexes, AsyncIO). |
| **Fault Recovery & Debugging** | Memerlukan instrumentasi manual (`trap`, `caller`, `BASH_SOURCE`). Parsing *dynamic variable evaluation* bisa memunculkan *edge cases*. | Terstruktur dengan *structured exceptions*, typed compiler checks, dan pprof profiling. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Subshell Variable Masking dalam Pipeline

* **Penyebab**: Operator pipe `|` mengeksekusi kedua sisinya di dalam *subshell context* yang terisolasi.
* **Gejala**: Variabel yang diperbarui di dalam perulangan kembali ke nilai awal setelah perulangan selesai.
* **Diagnosa & Solusi**: Gunakan *Process Substitution* atau *Here-String*.

```bash
# SALAH
COUNT=0
cat endpoints.txt | while read -r url; do
    ((COUNT++))
done
echo "Processed: $COUNT" # Output selalu 0

# BENAR
COUNT=0
while read -r url; do
    ((COUNT++))
done < <(cat endpoints.txt)
echo "Processed: $COUNT" # Nilai akurat
```

### 10.2. Penggunaan Flag `set -e` yang Tidak Konsisten (Subshell Amnesia)

* **Penyebab**: Pada spesifikasi POSIX lama, kondisi dalam `if`, `while`, atau pipeline `||` menonaktifkan pewarisan flag `-e` ke subshell fungsi di dalamnya.
* **Gejala**: Command gagal di dalam fungsi, tetapi skrip terus mengeksekusi instruksi destruktif berikutnya.
* **Solusi**: Pastikan selalu menyertakan `shopt -s inherit_errexit` (tersedia mulai Bash 4.4+) bersama dengan `set -E`.

### 10.3. File Descriptor Leaks

* **Penyebab**: Membuka custom FD (`exec 4>file.txt`) tanpa menutupnya sebelum skrip melepaskan konteks atau dalam fungsi berulang.
* **Diagnosa**:
  ```bash
  # Periksa descriptor yang terbuka dari proses shell aktif
  ls -la /proc/$$/fd/
  ```
* **Solusi**: Selalu pasangkan pembukaan FD dengan deklarasi penutupan eksplisit di block cleanup: `exec 4>&-`.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebagai gate review skrip Bash sebelum merge ke production:

- [ ] **Shebang Standar**: Gunakan `#!/usr/bin/env bash` untuk portabilitas path binary bash di berbagai distro Linux.
- [ ] **Preamble Wajib**: Letakkan `set -Eeuo pipefail` di baris pertama setelah shebang.
- [ ] **Trap Global Handlers**: Definisikan handler untuk sinyal `ERR`, `EXIT`, `SIGINT`, dan `SIGTERM`.
- [ ] **Semua Variabel Ter-quote**: Gunakan quote ganda `"$VAR"` untuk mencegah *word splitting* dan *glob expansion*.
- [ ] **Penggunaan Array**: Hindari menyimpan kumpulan string atau daftar file dalam string yang dipisahkan spasi; gunakan `declare -a`.
- [ ] **Eksekusi Pengujian Kondisi**: Gunakan `[[ ... ]]` alih-alih `[ ... ]` atau utility eksternal `test`.
- [ ] **Variabel Terproteksi**: Deklarasikan konstanta sistem menggunakan `readonly` atau `declare -r`.
- [ ] **Atomic File Locking**: Gunakan `flock` untuk skrip yang berjalan di cron atau daemon scheduler agar tidak terjadi double-run.
- [ ] **Proses Substitusi**: Ganti pola `cat file | while` dengan `while ... done < <(command)`.
- [ ] **Linting & Validasi**: Skrip wajib lulus analisis statis `shellcheck --severity=style` tanpa peringatan.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan pada folder direktori: `hands-on/m02/`

### Setup Persiapan Lingkungan

```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Panduan Implementasi: Structured Multiprocess Health Auditor

Buat file `health_auditor.sh` dengan instruksi berikut:
1. Skrip menerima argumen path file daftar server target.
2. Skrip membuka FD 3 yang dialirkan ke file `audit.log`.
3. Skrip membatasi konkurensi pengecekan maksimal 3 target secara bersamaan menggunakan FIFO semaphore.
4. Setiap worker mengecek status server via pseudo-network check atau `ping -c 1`.
5. Skrip harus merespons `SIGINT` (Ctrl+C) secara bersih tanpa meninggalkan proses background atau file FIFO yang menggantung.

```bash
#!/usr/bin/env bash
# File: hands-on/m02/health_auditor.sh
set -Eeuo pipefail

TARGETS_FILE="${1:-targets.txt}"
if [[ ! -f "${TARGETS_FILE}" ]]; then
    echo "Usage: $0 <targets_file>" >&2
    exit 1
fi

LOG_FILE="hands-on/m02/audit.log"
exec 3>>"${LOG_FILE}"

FIFO_PIPE="$(mktemp -u)"
mkfifo "${FIFO_PIPE}"
exec 4<>"${FIFO_PIPE}"
rm -f "${FIFO_PIPE}"

# Concurrency limit = 3
for ((i=0; i<3; i++)); do echo "" >&4; done

cleanup() {
    echo "[!] Interrupted or Exited. Cleaning up..." >&2
    exec 4<&- || true
    exec 4>&- || true
    exec 3>&- || true
}
trap cleanup EXIT

while read -r target; do
    [[ -z "${target}" ]] && continue
    read -r -u 4 # Wait slot
    (
        timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        if ping -c 1 -W 1 "${target}" &>/dev/null; then
            echo "${timestamp} [HEALTHY] Host: ${target}" >&3
        else
            echo "${timestamp} [UNHEALTHY] Host: ${target}" >&3
        fi
        echo "" >&4 # Release slot
    ) &
done < "${TARGETS_FILE}"

wait
echo "Audit complete. Output written to ${LOG_FILE}"
```

---

## 13. Exercise

### Level Easy: Safe File Descriptor Multiplexer
* **Instruksi**: Tulis skrip `fd_routing.sh` yang menerima input stream STDIN.
  * Baris yang mengandung kata `"DEBUG"` harus dibuang ke `/dev/null`.
  * Baris yang mengandung kata `"ERROR"` harus diarahkan ke FD 2 (STDERR).
  * Baris lainnya harus diarahkan ke FD 1 (STDOUT) dengan prefix `[PROD]`.
* **Kriteria Validasi**: Uji dengan `printf "INFO OK\nDEBUG Trace\nERROR Crash\n" | ./fd_routing.sh`.

### Level Medium: Dynamic Variable Callstack Tracer
* **Instruksi**: Buat skrip `callstack_tracer.sh`. Implementasikan fungsi bertingkat (`func_a` memanggil `func_b`, `func_b` memanggil `func_c`). Di dalam `func_c`, picu error secara sengaja (misal: pembagian nol atau eksekusi variabel tak terdefinisi). Bangun trap `ERR` kustom yang membaca array `${FUNCNAME[@]}`, `${BASH_SOURCE[@]}`, dan `${BASH_LINENO[@]}` untuk mencetak visual call stack tree vertikal.
* **Kriteria Validasi**: Log trace harus memunculkan path file lengkap, nama fungsi dari daun hingga akar, dan nomor baris terkait secara presisi.

### Level Hard: Dynamic Token-Bucket Rate Limiter
* **Instruksi**: Bangun engine pemroses data bernama `stream_processor.sh` yang membaca jutaan entri JSON dari pipe stream input. Terapkan algoritma *token bucket* murni di Bash (menggunakan sinyal timer POSIX atau loop interupsi sub-detik) yang membatasi pemrosesan tepat 10 transaksi per detik tanpa mendrop pesan, dan memprosesnya secara non-blocking ke downstream handler.
* **Kriteria Validasi**: Jika input stream diberikan kecepatan 100 baris/detik, eksekusi pemrosesan harus stabil menghasilkan 10 baris per interval detik secara deterministik.

---

## 14. Challenge

### High-Availability Distributed State Synchronizer

Rancang skrip shell enterprise architecture tanpa dependensi binary pihak ketiga (hanya utilitas POSIX standar dan Bash 5.x) bernama `cluster_mesh_sync.sh` dengan ketentuan:

1. **State Engine**: Mampu membaca konfigurasi node cluster dari file JSON sederhana/flat text file.
2. **Leader Election via Kernel Lock**: Menggunakan file descriptor locking pada network shared filesystem (NFS/EFS path) untuk menentukan master controller instance secara atomic.
3. **Heartbeat Daemon**: Master instance memancarkan update berkala ke slave nodes via File Descriptor asynchronous stream pipes.
4. **Self-Healing Traps**: Jika master instance dimatikan secara mendadak (`kill -9` atau `kill -15`), *failover sequence* harus dieksekusi oleh salah satu node standby dalam waktu kurang dari 2 detik tanpa menghasilkan file state corrupt atau deadlock.
5. **No Blind Wait**: Dilarang menggunakan polling pasif berulang dengan latency tinggi (`sleep 5`). Gunakan interupsi sinyal UNIX untuk event propagation antar proses.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic

1. Mengapa perintah `export MY_VAR="value"` di dalam subshell `( export MY_VAR="value" )` tidak dapat diakses oleh parent script setelah subshell selesai dieksekusi?
2. Apa konsekuensi teknis mengaktifkan opsi shell `set -o pipefail` pada command chain seperti `grep "pattern" data.txt | wc -l` jika `grep` tidak menemukan pola?
3. Sebutkan File Descriptor default pada sistem Linux beserta peruntukannya!
4. Apa fungsi dari pemanggilan pseudo-sinyal `EXIT` pada instruksi `trap 'cleanup' EXIT`?
5. Mengapa perintah `[ -f /tmp/lock.pid ] || touch /tmp/lock.pid` dianggap anti-pattern untuk mekanisme concurency locking pada sistem enterprise?

### 15.2. Pertanyaan Intermediate

6. Jelaskan perbedaan mendalam antara anonymous pipe `command1 | command2` dan process substitution `command2 < <(command1)` dari perspektif alokasi subshell dan persistensi variabel!
7. Bagaimana mekanisme kerja `exec 3<>/tmp/custom.sock` dalam memanipulasi stream I/O pada Bash?
8. Mengapa signal `SIGKILL` (Signal 9) dan `SIGSTOP` tidak dapat ditangkap oleh utility `trap`?
9. Apa perbedaan semantik antara sintaks `$$` dan `$!` dalam konteks pelacakan status background process?
10. Pada skenario apa flag `set -e` gagal menghentikan eksekusi skrip meskipun terjadi error non-zero exit code pada sebuah instruksi?

### 15.3. Skenario Kasus Produksi

11. **Skenario A**: Sebuah script backup database harian berjalan via cronjob:
    ```bash
    #!/bin/bash
    set -e
    mysqldump -u root production | gzip > /mnt/storage/prod_backup.sql.gz
    echo "Backup Sukses" | mail -s "Status" devops@company.com
    ```
    Suatu malam, disk `/mnt/storage` penuh sehingga proses `gzip` crash dengan exit code 1. Namun, notifikasi email "Backup Sukses" tetap terkirim ke tim DevOps, menyembunyikan terjadinya insiden data loss. Jelaskan secara teknis di mana letak akar masalah arsitektur skrip tersebut dan tuliskan perbaikannya!

12. **Skenario B**: Anda memiliki script audit `process_logs.sh` yang membaca log berukuran 50GB:
    ```bash
    declare -A ERROR_MAP
    cat /var/log/huge_app.log | while read -r line; do
        if [[ "$line" =~ ERROR_([0-9]+) ]]; then
            code="${BASH_REMATCH[1]}"
            ((ERROR_MAP[$code]++))
        fi
    done
    echo "Total categories: ${#ERROR_MAP[@]}"
    ```
    Setelah selesai, output `Total categories` selalu bernilai `0`. Tim Anda menduga regex rusak. Apakah analisis tersebut benar? Jika salah, identifikasi kegagalan arsitekturnya dan perbaiki tanpa menurunkan performa!

13. **Skenario C**: Pada pipeline CI/CD, ada skrip Bash panjang yang kerap berhenti secara misterius tanpa pesan error sama sekali, hanya menampilkan exit code general `1` pada runner agent. Uraikan arsitektur *debugging & tracing frame engine* berbasis environment bash internal yang bisa diinjeksi ke baris awal skrip tersebut untuk mendeteksi baris spesifik, command yang gagal, dan riwayat stack pemanggilannya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Basic
1. Karena subshell berjalan di child process baru melalui syscall `fork()`. Ruang memori dialokasikan terpisah via Copy-on-Write, sehingga mutasi environment table di child process terisolasi dan musnah saat child process exit.
2. Skrip akan menerima exit code non-zero dari `grep` (exit code 1 jika tidak ada string yang match), sehingga memicu shell berhenti seketika (jika `set -e` aktif), berbeda dengan default behavior pipeline yang hanya mengambil exit code dari instruksi terakhir (`wc -l`).
3. FD 0: Standard Input (`stdin`), FD 1: Standard Output (`stdout`), FD 2: Standard Error (`stderr`).
4. `EXIT` adalah pseudo-signal Bash yang dieksekusi saat shell keluar dalam kondisi apapun (normal termination, exit eksplisit, atau fatal error). Menjamin eksekusi housekeeping cleanup secara deterministik.
5. Operasi pengecekan `[ -f ... ]` dan pembuatan file `touch ...` bukanlah operasi *atomic*. Terjadi window of vulnerability (Time-of-Check to Time-of-Use / TOCTOU) di mana proses lain dapat berjalan di antara kedua perintah tersebut, menyebabkan *race condition*.

#### Intermediate
6. Anonymous pipe `A | B` mengeksekusi kedua segmen `A` dan `B` dalam child subshell. Pada process substitution `B < <(A)`, segmen `B` tetap berjalan pada konteks parent shell utama, sedangkan hanya `A` yang berjalan di child process asinkron yang outpunya dialirkan melalui descriptor path `/dev/fd/`. Hal ini mempertahankan mutasi variabel di dalam `B`.
7. Perintah tersebut mengalokasikan File Descriptor 3 untuk membaca dan menulis (`<>`) ke file atau FIFO target secara bidirectional, memungkinkan I/O streaming persistent tanpa berulang kali membuka-tutup handler file.
8. Standar kernel POSIX mendesain sinyal `SIGKILL` dan `SIGSTOP` secara absolut untuk dihandle langsung oleh kernel scheduler; hak kontrol proses dicabut dari user-space sehingga proses target tidak diberi alokasi instruksi untuk memblokir, mengabaikan, atau menangkapnya.
9. `$$` mengembalikan PID dari proses shell yang sedang aktif saat ini (*self process*), sedangkan `$!` menyimpan PID dari *job background* yang paling terakhir dieksekusi di asynchronous context.
10. `set -e` dinonaktifkan secara otomatis saat perintah yang gagal berada dalam evaluasi kondisi statement `if`, perulangan `while`/`until`, bagian dari pipeline non-final sebelum `||`, atau perintah yang di-negasi menggunakan operator `!`.

#### Skenario Kasus Produksi
11. **Akar Masalah**: Preamble `set -e` tanpa `set -o pipefail` hanya mendeteksi exit code dari command terakhir dalam pipeline. Command `mysqldump` gagal atau `gzip` crash diabaikan jika command penutup mengembalikan 0 (atau jika shell parsing pipe buffer menutupi error di sisi upstream).
    **Solusi**:
    ```bash
    #!/usr/bin/env bash
    set -Eeuo pipefail
    
    BACKUP_FILE="/mnt/storage/prod_backup_$(date +%F).sql.gz"
    
    # Eksekusi dengan strict check
    mysqldump -u root production | gzip > "${BACKUP_FILE}"
    
    # Validasi size integritas
    if [[ ! -s "${BACKUP_FILE}" ]]; then
        echo "ERROR: Backup file kosong atau corrupt!" >&2
        exit 1
    fi
    
    echo "Backup Sukses" | mail -s "Status" devops@company.com
    ```

12. **Akar Masalah**: Analisis regex salah. Masalah utama terletak pada `cat ... | while read ...`, yang menyebabkan seluruh loop `while` beserta array associative `ERROR_MAP` hidup dan mati di dalam sebuah *subshell pipe*.
    **Solusi**:
    ```bash
    declare -A ERROR_MAP
    # Alihkan stream langsung via Process Substitution
    while read -r line; do
        if [[ "$line" =~ ERROR_([0-9]+) ]]; then
            code="${BASH_REMATCH[1]}"
            ((ERROR_MAP[$code]++))
        fi
    done < <(cat /var/log/huge_app.log)
    
    echo "Total categories: ${#ERROR_MAP[@]}"
    ```

13. **Solusi Tracing Engine**: Tambahkan Trap `ERR` dengan Stack Unrolling di awal skrip:
    ```bash
    set -Eeuo pipefail
    
    trace_error() {
        local exit_code=$?
        local failed_line=$1
        local failed_cmd=$2
        
        echo "[CRITICAL ERROR] Komando: '${failed_cmd}' gagal pada baris ${failed_line} (Exit Code: ${exit_code})" >&2
        echo "=== STACK TRACE ===" >&2
        local i=0
        while caller_info=($(caller $i)); do
            echo "  [$i] File: ${caller_info[2]} | Baris: ${caller_info[0]} | Fungsi: ${caller_info[1]}" >&2
            ((i++))
        done
        echo "===================" >&2
        exit "${exit_code}"
    }
    
    trap 'trace_error ${LINENO} "${BASH_COMMAND}"' ERR
    ```

---

## 16. Summary

* **Eksekusi Subshell vs In-Process**: Memahami boundaries isolasi proses kernel membedakan engineer pemula dengan enterprise system architect. Hindari kebocoran subshell pada pipelines menggunakan *Process Substitution* `<(...)`.
* **Defensive Preamble**: Shell script produksi wajib menerapkan baseline environment: `set -Eeuo pipefail` untuk menghentikan degradasi eksekusi parsial secara dini.
* **Manipulasi File Descriptor (FD)**: I/O Redirection tingkat lanjut memungkinkan isolasi multiplexing antara stream data utama (FD 1), standard error (FD 2), dan specialized telemetry/audit logging logs (FD 3-9).
* **Konkurensi Deterministik**: Hindari pola sleep looping atau backgrounding tak terbatas. Bangun throttling token berbasis *Named Pipes (FIFOs)* dan amankan integritas *single-execution* menggunakan kernel locking `flock`.
* **Resiliensi via Signals**: Seluruh lifecycle resource harus terlindungi oleh `trap` handler, menjamin *graceful shutdown* dan sanitasi file temporer saat sistem menerima gangguan sinyal operasional.