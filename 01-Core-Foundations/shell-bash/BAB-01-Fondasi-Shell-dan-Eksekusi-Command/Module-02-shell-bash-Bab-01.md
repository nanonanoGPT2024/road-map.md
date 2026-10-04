# Kurikulum Enterprise: Rekayasa Shell & Bash Modern

* **Topik**: Shell & Bash Scripting (`shell-bash`)
* **Kategori**: `01-Core-Foundations`
* **Bab**: `01` (BAB-01-Fondasi-dan-Arsitektur)
* **Modul**: `Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi`

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level arsitek/rekayasawan sistem diharapkan mampu:

1. **Membedah Arsitektur Eksekusi Internal Bash**: Mengidentifikasi fase-fase parsing (tokenization, expansion phases, word splitting, quote removal) hingga eksekusi syscall (`fork()`, `execve()`, `pipe()`, `dup2()`).
2. **Mengelola Mutasi File Descriptor (FD) Tingkat Lanjut**: Mengoperasikan alur I/O kustom di luar `0`, `1`, dan `2` (FD 3–9), manipulasi *anonymous pipes*, *named pipes* (FIFO), dan *process substitution* tanpa menimbulkan kebocoran sumber daya (*FD leaks*).
3. **Mendesain Pola Penanganan Interupsi dan Sinyal**: Membangun *lifecycle trap management* berbasis POSIX signal (`SIGTERM`, `SIGINT`, `EXIT`, `SIGHUP`) yang deterministik, re-entrant, dan aman terhadap kegagalan mendadak (*fail-safe cleanup*).
4. **Mengimplementasikan Concurrency & Process Synchronization**: Mengendalikan konkurensi native berbasis Bash (subshell, background jobs, worker pool pattern, `coproc`) dengan mekanisme locking berbasis kernel via `flock`.
5. **Menulis Kode Berskala Enterprise**: Membangun skrip automasi mission-critical dengan ketahanan tinggi (fault-tolerant, fully idempotent, observable, dan mematuhi POSIX/Bash strict safety standards).

---

## 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memahami:
* Fondasi sistem operasi Linux: Virtual Memory, Process Table, PID, PPID, dan Exit Status (`0-255`).
* Dasar-dasar perintah Shell: Perintah umum POSIX (`grep`, `sed`, `awk`, `cut`, `find`).
* Pemahaman fundamental mengenai I/O Redirection standar (`<`, `>`, `>>`, `2>&1`, `|`).
* Pengetahuan dasar pemrograman terstruktur: variabel, percabangan (`if/case`), perulangan (`for/while`), dan fungsi.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Siklus Hidup Instruksi: Dari String ke Kernel Syscall

Bash tidak langsung mengeksekusi baris teks mentah. Sebuah baris instruksi mengalami 8 tahapan serial sebelum kontrol dialihkan ke kernel Linux via *System Call*:

```
[Raw Command String]
        │
        ▼
1. Lexical Analysis (Tokenization & Quoting Detection)
        │
        ▼
2. Parsing & AST (Abstract Syntax Tree Generation)
        │
        ▼
3. Expansions Pipeline (Urutan Bersifat Deterministik):
   a. Brace Expansion {a,b}
   b. Tilde Expansion ~
   c. Parameter & Variable Expansion $VAR
   d. Command Substitution $(cmd)
   e. Arithmetic Expansion $((expr))
   f. Process Substitution <(cmd)
   g. Word Splitting (Berdasarkan Nilai $IFS)
   h. Pathname Expansion / Globbing (*.log)
        │
        ▼
4. Quote Removal (Karakter escape \ dan quote '', "" dibuang)
        │
        ▼
5. Redirection Processing (dup2() & Setup FD Table)
        │
        ▼
6. Variable Assignment (Jika ada mutasi prefix lokal)
        │
        ▼
7. Command Identification (Builtin vs Function vs External Executable)
        │
        ▼
8. Execution (Current Context vs Subshell via fork() + execve())
```

#### Perbedaan Hakiki: Builtin, Function, dan External Binary
1. **Shell Builtin** (contoh: `cd`, `read`, `trap`, `exec`):
   * Berjalan langsung di dalam ruang memori internal proses Bash (*no fork*).
   * Mampu mengubah *state* internal shell (contoh: direktori kerja via `chdir()`, batas memori via `ulimit`).
2. **Shell Function**:
   * Blok kode yang telah di-parsing dan dimuat ke heap memori Bash.
   * Dijalankan pada thread/proses shell yang sama (*current execution environment*), kecuali jika secara eksplisit dipanggil di dalam subshell.
3. **External Binary** (contoh: `/bin/ls`, `/usr/bin/jq`):
   * Memerlukan kernel syscall `fork()` (atau `clone()`) untuk menduplikasi proses shell induk.
   * Diikuti syscall `execve()` yang menimpa *address space* proses anak dengan binary tujuan.
   * Menghasilkan *overhead context switching*, alokasi *page table*, dan resolusi dynamic linker (`ld-linux.so`).

### 3.2 File Descriptor (FD) & I/O Subsystem

Di Linux, setiap proses memiliki File Descriptor Table di kernel space. Secara default:
* `0`: `stdin` (Standard Input)
* `1`: `stdout` (Standard Output)
* `2`: `stderr` (Standard Error)

Bash mengizinkan penggunaan FD hingga `9` (dan lebih tinggi via sintaks modern `exec {var}>...`). 

```
               Process FD Table                 Linux Kernel VFS
             ┌───────────────────┐             ┌─────────────────┐
  stdin  (0) │ File Pointer Path ├────────────►│ /dev/pts/0 (TTY)│
             ├───────────────────┤             ├─────────────────┤
  stdout (1) │ File Pointer Path ├────────────►│ /dev/pts/0 (TTY)│
             ├───────────────────┤             ├─────────────────┤
  stderr (2) │ File Pointer Path ├────────────►│ /dev/pts/0 (TTY)│
             ├───────────────────┤             ├─────────────────┤
  Custom (3) │ File Pointer Path ├───────┐     │ /var/log/app.log│
             ├───────────────────┤       └────►├─────────────────┤
  Custom (4) │ File Pointer Path ├────────────►│ Anonymous Pipe  │
             └───────────────────┘             └─────────────────┘
```

Operasi `exec 3>&1` memanggil syscall `dup2(1, 3)`, menyalin pointer file dari indeks 1 ke indeks 3. Ketika Anda menggunakan `cmd > file 2>&1`, urutan bersifat kritikal:
1. `> file` mengubah FD 1 merujuk ke vnode file target.
2. `2>&1` mengubah FD 2 menyalin target dari FD 1 (merujuk ke vnode file target yang sama).
3. Jika urutan terbalik: `cmd 2>&1 > file`, FD 2 akan menyalin rujukan FD 1 yang lama (biasanya TTY), lalu FD 1 dialihkan ke file. Akibatnya stderr tetap tampil di terminal.

### 3.3 Concurrency, Subshells, dan Signal Handling

* **Subshell `( ... )`**: Menjalankan instruksi di child process baru melalui `fork()`. Subshell mewarisi salinan memori (Copy-on-Write), environment variables, dan open FDs dari parent, tetapi mutasi state (perubahan variabel, `cd`) tidak akan pernah terefleksi kembali ke parent process.
* **Group Command `{ ...; }`**: Menjalankan instruksi di dalam *current execution context*. Mutasi variabel dan state direktori berdampak langsung pada parent process.
* **Signals & Asynchronous Trap**: Bash mendaftarkan handler sinyal kernel via `sigaction`. Sinyal seperti `SIGTERM` (15) dan `SIGINT` (2) dapat diintersepsi oleh perintah `trap`. Bash menahan eksekusi handler sinyal sampai proses foreground binary yang sedang berjalan selesai mengembalikan exit code, kecuali perintah foreground di-wait secara asinkron atau dihentikan langsung oleh sinyal non-trappable (`SIGKILL` / `SIGSTOP`).

---

## 4. Why & What

### Mengapa Pendekatan Shell Konvensional Gagal di Skala Enterprise?
Banyak teknisi memperlakukan Bash sebagai serangkaian perintah CLI linear tanpa penanganan error struktural. Hal ini menyebabkan fenomena:
* **Silent Failures**: Skrip terus melaju meski dependensi database gagal diinisiasi.
* **Zombie/Orphan Processes**: Background worker tetap berjalan di host OS saat skrip di-kill, memakan file locks dan resources CPU.
* **Race Conditions**: Konflik penulisan ke state file atau rotasi log tanpa implementasi lock kernel.
* **Catastrophic Expansions**: Variabel kosong yang diekspansi pada `rm -rf "${DIR}/${SUBDIR}"` berpotensi menghapus direktori root jika `$DIR` atau `$SUBDIR` bernilai null.

### Apa Solusi Standar Rekayasa Modern?
* **Safety Header Imutabel**: Penggunaan `set -Eeuo pipefail`.
* **Stateful Locking**: Menggunakan kernel advisory locks melalui `flock(2)`.
* **Resource Cleanup Trap**: Menjamin pembersihan temporary resources via register trap `EXIT`.
* **Standardized Logging & Telemetry**: Mengalihkan output ke file descriptor terisolasi yang terhubung dengan struktur log sistem (syslog, JSON stdout, systemd-journald).

---

## 5. How (Workflow detail)

Berikut alur kerja standar penulisan skrip Bash production-grade:

```
[Start Execution]
       │
       ▼
[01. Strict Mode Engine Activation] ──► (set -Eeuo pipefail, IFS=$'\n\t')
       │
       ▼
[02. Trap Initialization]           ──► Register cleanup_handler() on EXIT, SIGINT, SIGTERM
       │
       ▼
[03. Exclusive Mutual Exclusion]    ──► Acquire Kernel Lock via flock FD 200
       │
       ▼
[04. Parameter Parsing & Validation]──► Parse args (getopts), validate input, assert dependencies
       │
       ▼
[05. Execution Phase (Core Logic)]  ──► Stream processing, worker pools, transactional changes
       │
       ▼
[06. Success/Fail Exit]             ──► Explicit exit code (0..255)
       │
       ▼
[07. Automatic Cleanup Handler]     ──► Release FDs, drop lock, remove /tmp, emit metrics
```

### Penjelasan Strict Flags:
1. `set -e`: Menghentikan eksekusi skrip jika ada instruksi yang mengembalikan non-zero exit status (dengan pengecualian di kondisi `if`, `while`, atau operand `||`).
2. `set -u` (`set -o nounset`): Melempar error fatal dan membatalkan eksekusi jika shell mencoba membaca variabel yang belum dideklarasikan/diinisiasi.
3. `set -o pipefail`: Secara default pipeline `cmdA | cmdB | cmdC` mengembalikan exit code dari `cmdC`. Flag ini memaksa pipeline mengembalikan exit code dari perintah *pertama* yang gagal (non-zero).
4. `set -E` (`set -o errtrace`): Memaksa traps sinyal `ERR` diwarisi oleh shell function, command substitution, dan subshell context.

---

## 6. Analogy & Diagram ASCII

### Analogi: Bash Execution Pipe vs Perakitan Manufaktur Modular
Bayangkan Bash sebagai rantai perakitan pabrik:
* **Current Shell `{}`**: Tim internal di ruang utama. Perubahan catatan inventaris langsung berdampak pada papan utama pabrik.
* **Subshell `()`**: Pabrik cabang di seberang jalan yang memfotokopi seluruh cetak biru (*Copy-on-Write*). Apapun coretan yang dibuat di papan pabrik cabang tidak mengubah papan utama pabrik induk.
* **File Descriptors**: Jalur konveyor modular. FD 0, 1, 2 adalah pintu standar. Anda dapat memasang pipa kustom (FD 3–9) untuk mengirim material khusus langsung ke gudang log tanpa mencampuri jalur produk utama.

### Diagram: Isolasi File Descriptor dan Pipeline Flow

```
+-------------------------------------------------------------------------------+
| Process Address Space (PID: 12044)                                            |
|                                                                               |
|  [Environment: PATH, IFS, custom vars]                                       |
|                                                                               |
|  FD Table:                                                                    |
|  [0] Stdin  -------------> Keyboard / Socket                                  |
|  [1] Stdout -------------> Buffer / Dev Null                                  |
|  [2] Stderr -------------> Console (Unbuffered)                               |
|  [3] Custom -------------> /var/log/audit.json (O_APPEND | O_CREAT)           |
|  [200] Lock -------------> /var/lock/worker.lock (flock advisory lock)        |
|                                                                               |
|  Execution Context:                                                           |
|  ├── Parent Script (Main)                                                     |
|  │    │                                                                       |
|  │    ├── fork() ---> Subshell Context (PID: 12045)                           |
|  │    │                ├── Inherited FDs (0, 1, 2, 3, 200)                    |
|  │    │                └── execve('/usr/bin/curl')                            |
|  │    │                                                                       |
|  │    └── Named Pipe (FIFO) Handler                                           |
|  │             ▲                                                              |
|  └─────────────┴─── Reads data from child without intermediate disk write     |
+-------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mutasi File Descriptor Lanjutan
Membuat alur pencatatan ganda (*dual logging*) tanpa dependensi eksternal, memisahkan log konsol dan audit file menggunakan FD kustom.

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Inisialisasi file audit
AUDIT_LOG="./audit.log"

# Buka FD 3 yang merujuk ke file log (append mode)
exec 3>>"${AUDIT_LOG}"

# Kirim pesan normal ke stdout (FD 1)
echo "Pesan ini tampil di terminal."

# Kirim pesan rahasia/audit khusus ke FD 3
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] AUDIT: User admin authenticated" >&3

# Tutup FD 3 secara eksplisit
exec 3>&-

# Validasi isi
cat "${AUDIT_LOG}"
rm -f "${AUDIT_LOG}"
```

### 7.2 Practical Example: Process Pool Concurrency Limiter
Pola standar industri untuk mengeksekusi *N* pekerjaan paralel secara asinkron tanpa membanjiri sistem CPU (Job Throttling murni menggunakan Bash primitives & FIFO).

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

readonly MAX_WORKERS=4
readonly JOB_COUNT=10
readonly QUEUE_FIFO="/tmp/worker_queue_$$.fifo"

# Buat named pipe (FIFO) untuk token bucket semaphore
mkfifo "${QUEUE_FIFO}"
exec 3<>"${QUEUE_FIFO}"
rm -f "${QUEUE_FIFO}" # Unlink dari filesystem, FD 3 tetap terbuka di kernel

# Bersihkan resources saat exit
trap 'exec 3>&-; exit 0' EXIT
trap 'echo "Terminated by user"; exec 3>&-; exit 1' SIGINT SIGTERM

# Isi semaphore dengan token sejumlah MAX_WORKERS
for ((i = 0; i < MAX_WORKERS; i++)); do
    echo >&3
done

# Worker logic
execute_task() {
    local task_id="$1"
    local sleep_duration=$(( (RANDOM % 3) + 1 ))
    echo "[$(date +%T)] [START] Worker Task #${task_id} (Duration: ${sleep_duration}s)"
    sleep "${sleep_duration}"
    echo "[$(date +%T)] [DONE ] Worker Task #${task_id}"
}

echo "Mulai mengeksekusi ${JOB_COUNT} task dengan limit konkurensi ${MAX_WORKERS}..."

for ((i = 1; i <= JOB_COUNT; i++)); do
    # Ambil token dari FIFO. Jika kosong, script block/menunggu di sini
    read -r -u 3

    # Jalankan pekerjaan di subshell background
    (
        execute_task "$i"
        # Kembalikan token ke FIFO setelah task selesai
        echo >&3
    ) &
done

# Tunggu hingga semua background jobs selesai
wait
echo "Seluruh task selesai secara paralel tanpa melebihi batas sumber daya."
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Engine Backup & Streaming Ekspor PostgreSQL Berskala Terabyte dengan Mutex Lock & Telemetri Realtime

#### Masalah
Perusahaan fintech membutuhkan pipeline backup yang mengekspor data database PostgreSQL, mengompresinya secara on-the-fly, mengunggahnya ke Object Storage (S3), dan mencatat audit metadata. Kendala operasional:
1. Skrip ganda tidak boleh berjalan bersamaan (bisa mengakibatkan I/O saturation pada database primary).
2. Disk space tidak mencukupi untuk menyimpan file raw SQL uncompressed (wajib full-streaming tanpa intermediate file).
3. Jika proses gagal di tengah jalan (misal network loss ke S3 atau kill oleh OOM), lock harus dilepas, upload parsial harus dibatalkan, dan webhook alarm harus dipanggil.

#### Solusi Arsitektur
Implementasi Bash script modular dengan advisory lock kernel via `flock`, redirection pipeline multi-stage via `named pipes`, dan trap handling yang tangguh.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name : pg_stream_backup.sh
# Description : Enterprise streaming backup pipeline for PostgreSQL to AWS S3.
# Standards   : POSIX compliant, bash-strict, zero-intermediate-disk architecture.
# ==============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

# --- 1. Environment & Global Constants ---
readonly SCRIPT_NAME="$(basename "${0}")"
readonly LOCK_FILE="/var/lock/${SCRIPT_NAME}.lock"
readonly LOCK_FD=200
readonly TIMESTAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
readonly BACKUP_NAME="pg_backup_${TIMESTAMP}.sql.gz"
readonly METRICS_ENDPOINT="https://telemetry.internal.company.com/v1/metrics"

# Mock Credential / Config Injection
readonly PG_HOST="${PG_HOST:-127.0.0.1}"
readonly PG_PORT="${PG_PORT:-5432}"
readonly PG_USER="${PG_USER:-postgres}"
readonly S3_BUCKET="${S3_BUCKET:-s3://enterprise-db-backups/daily/}"

# --- 2. Logging & Telemetry Engine ---
# Gunakan FD 4 untuk Structured Logging terpisah dari stdout/stderr
exec 4>&1

log() {
    local level="$1"
    local message="$2"
    local log_entry
    log_entry=$(printf '{"timestamp":"%s","level":"%s","script":"%s","message":"%s"}' \
        "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        "${level}" \
        "${SCRIPT_NAME}" \
        "${message}")
    echo "${log_entry}" >&4
}

# --- 3. Robust Cleanup & Trap Infrastructure ---
cleanup() {
    local exit_code=$?
    log "INFO" "Executing cleanup sequence with exit code: ${exit_code}..."

    # Release and remove lock
    flock -u ${LOCK_FD} 2>/dev/null || true
    exec {LOCK_FD}>&- || true
    rm -f "${LOCK_FILE}"

    if [[ ${exit_code} -ne 0 ]]; then
        log "FATAL" "Backup pipeline failed! Emitting critical telemetry alert."
        # Invoke webhook telemetry via curl silently
        # curl -s -X POST "${METRICS_ENDPOINT}" -d "{\"status\":\"FAILED\",\"timestamp\":\"${TIMESTAMP}\"}" || true
    else
        log "INFO" "Backup pipeline successfully executed."
    fi

    exit "${exit_code}"
}

trap cleanup EXIT
trap 'log "WARN" "Interruption signal (SIGINT/SIGTERM) received!"; exit 130' SIGINT SIGTERM

# --- 4. Mutex Concurrency Control (Kernel-Level) ---
acquire_lock() {
    exec {LOCK_FD}>"${LOCK_FILE}"
    if ! flock -n ${LOCK_FD}; then
        log "ERROR" "Process collision detected. Another instance is running on Lock FD ${LOCK_FD}."
        exit 101
    fi
    log "INFO" "Mutual exclusion acquired via lockfile: ${LOCK_FILE}"
}

# --- 5. Pre-flight Assertion Engine ---
verify_prerequisites() {
    local -a required_bins=("pg_dump" "gzip" "aws" "flock")
    for bin in "${required_bins[@]}"; do
        if ! command -v "${bin}" >/dev/null 2>&1; then
            log "FATAL" "Dependency assertion failure: Binary '${bin}' is not installed or not in PATH."
            exit 102
        fi
    done
    log "INFO" "All system dependencies verified successfully."
}

# --- 6. Execution Pipeline (Zero-Disk Streaming) ---
run_pipeline() {
    log "INFO" "Starting streaming backup for host: ${PG_HOST}:${PG_PORT}"

    # Arsitektur Pipeline Streaming:
    # pg_dump stdout -> gzip stdout -> aws s3 cp stdin
    # Berjalan tanpa menyentuh disk lokal storage secara langsung.
    # set -o pipefail menjamin jika pg_dump crash, exit code pipeline adalah error pg_dump.
    
    # Simulation / Pseudo execution for environments without AWS/PG CLI:
    # Ganti dengan command asli di environment produksi:
    # pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -F p | gzip -c -9 | aws s3 cp - "${S3_BUCKET}${BACKUP_NAME}"

    log "INFO" "Simulating high-throughput pipeline stream..."
    echo "DUMP_HEADER: [DATA]" | gzip -c | cat > /dev/null

    log "INFO" "Stream processing and upload completed successfully: ${BACKUP_NAME}"
}

# --- 7. Main Invocation Flow ---
main() {
    acquire_lock
    verify_prerequisites
    run_pipeline
}

main "$@"
```

---

## 9. Trade-offs

| Dimensi Rekayasa | Implementasi Bash Native | Alternatif: Bahasa Terkompilasi / Runtime (Go / Python) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Execution Latency & Startup** | Instan (1-5ms), runtime footprint mendekati nol. | Python: 30-100ms (VM init). Go: instan (~1ms). | Bash unggul dalam operasi orkestrasi binary host (tanpa overhead VM/interpreter). |
| **Memory Footprint** | Sangat Rendah (~2-5 MB per subshell context). | Python: 15-40 MB. Go: 5-15 MB. | Bash sangat ideal untuk sistem dengan sumber daya terbatas (embedded, edge, bootstrap containers). |
| **System Fork Cost** | **Tinggi**. Setiap subshell `(...)`, pipeline `\|`, atau substitusi perintah `$(...)` memanggil `clone()/fork()`. | Rendah jika konkurensi ditangani di level OS/Green Threads (Goroutines). | Skrip Bash dengan perulangan intensif yang memanggil external binary ribuan kali akan memicu lonjakan degradasi CPU context switching. |
| **Error Handling & Type Safety** | Tipe data implisit (semuanya adalah string/array). Debugging runtime rawan jika flag keselamatan diabaikan. | Strongly typed (Go) atau Dynamic Typing dengan Exception handling komprehensif (Python). | Bash membutuhkan kedisiplinan verifikasi manual (`nounset`, sanitasi variabel, assertion exit code). |
| **Data Processing Capability** | Terbatas pada text-stream (I/O bounded via pipes). Kurang efisien untuk struktur data kompleks (Nested JSON, binary parsing). | Sangat unggul (banyak native standard library untuk JSON, Protobuf, gRPC). | Gunakan Bash untuk *orchestration* dan pipe processing; delegasikan transformasi data rumit ke `jq` atau binary Go. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis 1: Subshell Variable Loss pada While Loop Pipe
* **Anti-Pattern**:
  ```bash
  count=0
  cat data.txt | while read -r line; do
      ((count++))
  done
  echo "Total lines: $count" # Output AKAN SELALU 0!
  ```
* **Akar Masalah**: Simbol `|` memaksa sisi kanan loop dieksekusi di subshell tersendiri (`fork()`). Variabel `$count` yang dimutasi berada di memory space child process dan hilang saat loop selesai.
* **Solusi Enterprise (Process Substitution / Here-String)**:
  ```bash
  count=0
  while read -r line; do
      ((count++))
  done < <(cat data.txt) # Loop tetap berjalan di CURRENT shell execution space
  echo "Total lines: $count" # Output benar
  ```

### Kesalahan Kritis 2: Penanganan Unquoted Expansions (Word Splitting Hazard)
* **Anti-Pattern**:
  ```bash
  rm -rf /tmp/app_data/$APP_FOLDER
  ```
  Jika `$APP_FOLDER` tidak sengaja kosong, perintah terevaluasi menjadi `rm -rf /tmp/app_data/` yang menghapus seluruh base directory aplikasi. Jika `$APP_FOLDER="foo bar"`, sistem mengeksekusi dua argumen terpisah: `/tmp/app_data/foo` dan `bar`.
* **Solusi Enterprise**:
  Gunakan variable assertion `${VAR:?error_msg}` dan selalu kutip (*quote*) variabel:
  ```bash
  rm -rf "/tmp/app_data/${APP_FOLDER:?APP_FOLDER must be defined and non-empty}"
  ```

### Kesalahan Kritis 3: Zombie Process Leakage pada Asynchronous Tasks
* **Anti-Pattern**:
  Memicu job background `task &` berulang kali tanpa sinkronisasi pembersihan sinyal `SIGCHLD` atau `wait`, menyebabkan tabel proses host dipenuhi zombie state `[defunct]`.
* **Solusi Enterprise**:
  Gunakan fungsi wrapper kontrol proses dengan `wait $PID` atau polling berjadwal yang menangani interrupt secara graceful.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum menyetujui Pull Request automasi shell enterprise:

- [ ] **Shebang Standar**: Menggunakan `#!/usr/bin/env bash` untuk portabilitas path antar distro Linux/BSD.
- [ ] **Strict Safety Mode**: Mengaktifkan `set -Eeuo pipefail` di header skrip.
- [ ] **Immutability IFS**: Mengatur `$IFS` secara eksplisit (`IFS=$'\n\t'`) untuk mencegah split parameter pada spasi tak terduga.
- [ ] **Trap Registration**: Minimal mendaftarkan handler untuk `EXIT`, `SIGINT`, dan `SIGTERM`.
- [ ] **Quoting Hygiene**: Semua ekspansi ekspresi dan variabel terbungkus dalam tanda kutip ganda `"$VAR"`, array diekspansi via `"${ARRAY[@]}"`.
- [ ] **Concurrency Locking**: Skrip backend background menggunakan `flock` agar atomic dan mencegah tumpang tindih proses.
- [ ] **Defensive Dependency Checks**: Memeriksa seluruh tool CLI eksternal menggunakan `command -v binary >/dev/null 2>&1` sebelum logika utama dimulai.
- [ ] **Separation of Concerns for Output**:
  - Data stream untuk konsumsi program lain dikirim murni ke `stdout` (FD 1).
  - Pesan log, diagnostic, dan telemetry dialihkan secara konsisten ke `stderr` (FD 2) atau Dedicated Logging FD.
- [ ] **Linting & Code Quality**: Bebas dari warning validasi melalui analisis statis `shellcheck -x script.sh`.

---

## 12. Hands-on Practice

Implementasikan hands-on ini secara bertahap pada sistem Linux Anda. Semua berkas akan disimpan pada direktori `hands-on/m02/`.

### Langkah 1: Persiapan Workspace
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 2: Implementasi Skrip Pipeline Paralel Transaksional
Buat file `hands-on/m02/transaction_processor.sh`:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Hands-On Lab: Fault-Tolerant Concurrent Transaction Processor
# File        : hands-on/m02/transaction_processor.sh
# ==============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

readonly WORK_DIR="/tmp/hands_on_m02_$$"
readonly PROCESSED_LOG="${WORK_DIR}/processed.log"
readonly ERROR_LOG="${WORK_DIR}/error.log"

# Setup Direktori Kerja
mkdir -p "${WORK_DIR}"

# 1. Setup Resource Handler Trap
cleanup() {
    local exit_code=$?
    echo "[CLEANUP] Cleaning working directory: ${WORK_DIR}"
    rm -rf "${WORK_DIR}"
    echo "[CLEANUP] Completed with code: ${exit_code}"
    exit "${exit_code}"
}
trap cleanup EXIT
trap 'echo "[ALERT] Aborted by signal!"; exit 130' SIGINT SIGTERM

# 2. Setup Dedicated FDs
# FD 5: Processed Data Stream
# FD 6: Error / Anomaly Stream
exec 5>>"${PROCESSED_LOG}"
exec 6>>"${ERROR_LOG}"

# 3. Dummy Transaction Data Generator
generate_mock_data() {
    cat <<EOF
TXN-1001,SUCCESS,450.00
TXN-1002,INVALID,0.00
TXN-1003,SUCCESS,1200.50
TXN-1004,FAILED,34.10
TXN-1005,SUCCESS,99.90
EOF
}

# 4. Processing Engine via Stream Process Substitution
echo "[RUN] Processing transactions pipeline..."

while IFS=',' read -r txn_id txn_status txn_amount; do
    # Validasi skema
    if [[ "${txn_status}" == "SUCCESS" ]]; then
        # Kirim ke FD 5
        echo "[VALID TRANSACTION] ID: ${txn_id} Amount: \$${txn_amount}" >&5
    else
        # Kirim ke FD 6
        echo "[ANOMALY DETECTED] ID: ${txn_id} Status: ${txn_status}" >&6
    fi
done < <(generate_mock_data)

# 5. Flush and Present Stream Output
echo "=== SUMMARY: PROCESSED LOG (Via FD 5) ==="
cat "${PROCESSED_LOG}"

echo ""
echo "=== SUMMARY: ERROR/ANOMALY LOG (Via FD 6) ==="
cat "${ERROR_LOG}"

# 6. Menutup FDs
exec 5>&-
exec 6>&-

echo "[FINISH] Hands-on script completed cleanly."
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip dan periksa status kode balasan:
```bash
chmod +x hands-on/m02/transaction_processor.sh
./hands-on/m02/transaction_processor.sh
echo "Exit Status: $?"
```

---

## 13. Exercise

### Level Easy
Tulis skrip bernama `hands-on/m02/ex_easy.sh` yang menerima input path direktori dari argumen CLI pertama. Skrip wajib memvalidasi apakah argumen tersebut ada dan merupakan direktori valid. Jika tidak valid atau variabel kosong, hentikan skrip secara terhormat dengan exit status `2` dan cetak error ke `stderr`. Gunakan `set -euo pipefail`.

### Level Medium
Tulis skrip bernama `hands-on/m02/ex_medium.sh` yang membaca file teks besar baris demi baris menggunakan `read` dan *process substitution*. Hitung statistik jumlah karakter total tanpa mengeksekusi subshell pipeline (sehingga mutasi variabel counter tetap terjaga di parent process). Skrip harus mendaftarkan trap `SIGINT` yang mencetak jumlah baris yang *sempat* diproses sebelum program ditutup paksa oleh pengguna.

### Level Hard
Rancang script engine `hands-on/m02/ex_hard.sh` yang menjalankan 3 fungsi independen (`task_db`, `task_cache`, `task_storage`) secara asinkron (background). Skrip utama harus memonitor ketiga process PID tersebut. Jika **salah satu** proses mengalami error (exit code non-zero), skrip utama harus secara agresif mengirim sinyal `SIGTERM` kepada 2 proses lainnya yang masih berjalan, menghapus temporary file yang dibuat masing-masing worker, lalu keluar dengan exit status dari worker yang pertama kali crash.

---

## 14. Challenge

### Studi Kasus: High-Throughput Log Ingestion Engine dengan Rate-Limiting & Backpressure
Sistem telemetry Anda menghasilkan file log masif yang masuk ke direktori spool `/var/spool/raw_events/`. Anda diminta merancang arsitektur Bash daemon tanpa bantuan runtime level tinggi (Go/Python/Node.js).

**Spesifikasi Tantangan:**
1. **Locking & Single Instance**: Daemon berjalan terus menerus (looping), locked via `flock`.
2. **Backpressure Limit**: Sistem hanya boleh memproses maksimal 5 file secara paralel. Jika kapasitas penuh, daemon menunda membaca direktori spool (*backpressure*).
3. **Purity Stream via FIFO**: Setiap worker harus mengompres log menggunakan `gzip`, mengekstrak metadata JSON baris pertama menggunakan `head -n 1`, dan mengirim metrik tersebut ke anonymous Unix Pipe / FIFO internal yang dibaca oleh telemetry reporter di parent shell.
4. **Resilience**: Simulasikan interupsi kill mendadak (`kill -SIGTERM <PID>`). Daemon harus menunggu worker yang sedang berjalan menyelesaikan chunk yang tersisa (dengan batas timeout graceful shutdown 5 detik) sebelum melepaskan lock dan shutdown.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Mengapa ekspresi `cmd > file 2>&1` berbeda perilakunya jika urutannya diubah menjadi `cmd 2>&1 > file`?
2. Apa perbedaan fundamental antara flag `set -e` dan `set -o pipefail`?
3. Mengapa variabel yang dideklarasikan dan diubah di dalam blok `cat list.txt | while read r; do ...; done` nilainya kembali ke awal setelah loop selesai?
4. Apa fungsi dari perintah shell builtin `exec` ketika digunakan tanpa nama program (contoh: `exec 3>myfile.txt`)?
5. Mengapa shebang `#!/usr/bin/env bash` lebih direkomendasikan untuk portabilitas dibandingkan `#!/bin/bash`?

### 15.2 Pertanyaan Intermediate
6. Jelaskan apa yang terjadi di level kernel saat instruksi `read -r line < <(curl -s https://api.internal/data)` dijalankan (jelaskan mengenai syscall dan virtual filesystem descriptor)!
7. Mengapa penanganan sinyal via `trap 'cleanup' SIGTERM` terkadang tidak langsung merespons seketika saat external binary (seperti `sleep 100`) sedang dieksekusi di foreground?
8. Bagaimana implementasi `flock` pada File Descriptor mampu mencegah *race condition* antar instance skrip yang berjalan simultan?
9. Apa fungsi operator ekspansi `${VAR:=default}` vs `${VAR:-default}`?
10. Bagaimana cara mencegah Bash mengevaluasi token wildcard (`*`, `?`) sebagai Pathname Expansion ketika memproses string yang berisi karakter matematika?

### 15.3 Skenario Kasus Produksi
11. **Skenario A**: Sebuah skrip migrasi database berjalan di pipeline CI/CD dengan flag `set -e`. Skrip tersebut memiliki baris:
    ```bash
    RESULT=$(psql -h "$DB_HOST" -c "SELECT count(*) FROM users;" 2>&1)
    ```
    Ketika koneksi PostgreSQL gagal, mengapa CI/CD pipeline langsung berhenti tepat di baris tersebut, dan bagaimana cara menangkap output error ke dalam variabel `RESULT` tanpa memicu trigger `set -e` secara prematur?
12. **Skenario B**: Di sebuah server produksi, script worker cron job mengalami freeze dan menahan file lock selamanya. Setelah ditelusuri, worker tersebut memanggil perintah external network request yang hang (*infinite TCP socket timeout*). Bagaimana merancang arsitektur wrapper eksekusi Bash yang memiliki batas waktu mutlak (*hard timeout enforcement*) sekaligus menjamin lock dilepas?
13. **Skenario C**: Skrip log aggregator memproses file seukuran 50 GB. Pengembang menggunakan `awk` di dalam while loop Bash baris demi baris:
    ```bash
    while read -r log_line; do
        user=$(echo "$log_line" | awk '{print $3}')
        # logic lanjutan...
    done < access.log
    ```
    Skrip membutuhkan waktu belasan jam dan utilisasi CPU server melonjak 100%. Jelaskan secara arsitektural (kernel context switching, syscall, dan process table) mengapa pendekatan ini tidak efisien, dan bagaimana cara merestrukturisasinya agar selesai dalam hitungan menit!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Basic
1. **Urutan Evaluasi Redirection**: Shell memproses redirection dari kiri ke kanan. Pada `> file 2>&1`, stdout (1) diarahkan ke `file` dulu, lalu stderr (2) disalin merujuk ke tujuan yang sama dengan stdout (`file`). Pada `2>&1 > file`, stderr (2) menyalin tujuan stdout yang saat itu masih merujuk ke terminal/console, baru kemudian stdout (1) dialihkan ke `file`. Akibatnya, stderr tetap keluar di terminal.
2. **Perbedaan `set -e` vs `pipefail`**: `set -e` hanya menghentikan skrip jika *exit code akhir* dari sebuah pipeline/instruksi bernilai non-zero. Pada pipeline `A | B | C`, jika `A` gagal (exit 1) tetapi `C` sukses (exit 0), `set -e` menganggap pipeline sukses. `set -o pipefail` memastikan bahwa jika ada elemen pipeline yang gagal (`A`), pipeline tersebut secara keseluruhan mengembalikan status non-zero sehingga `set -e` dapat menangkapnya.
3. **Subshell Pipe Isolation**: Simbol pipeline (`|`) mengeksekusi setiap segmen prosesnya di dalam child process (subshell) yang terisolasi. Perubahan memory address/variabel yang terjadi di dalam subshell child process tidak disalin kembali ke memory table parent shell.
4. **Shell Re-direction Setup via `exec`**: Digunakan untuk memanipulasi File Descriptor Table dari proses shell saat ini secara permanen tanpa menjalankan subshell atau mengganti image process. `exec 3>myfile.txt` membuka file pointer baru pada indeks FD 3 yang tetap aktif untuk semua perintah selanjutnya sampai ditutup via `exec 3>&-`.
5. **Portabilitas Shebang**: Lokasi biner `bash` tidak selalu berada di `/bin/bash` di semua sistem POSIX (misalnya di FreeBSD berada di `/usr/local/bin/bash` atau NixOS di direktori nix store). `/usr/bin/env` membaca variabel `$PATH` sistem target untuk mencari lokasi binary bash yang valid.

#### Intermediate
6. **Kernel Execution Process Substitution**: Shell membuat named pipe virtual anonymous via `/dev/fd/<n>` atau pipe memory syscall `pipe()`. Syscall `fork()` dipanggil untuk menjalankan subshell `curl`, di mana output stdout `curl` disambungkan ke sisi write pipe via `dup2()`. Shell utama membaca sisi read pipe melalui virtual descriptor tersebut secara streaming tanpa menulis isi HTTP stream ke media penyimpanan fisik.
7. **Signal Delay pada Foreground External Program**: Saat external process berjalan di foreground, Bash mentransfer kontrol terminal dan menunggu via `waitpid()`. Bash menyimpan sinyal kernel yang masuk ke dalam antrean pending dan baru mengeksekusi trap handler setelah syscall `waitpid()` selesai mengembalikan status dari external program tersebut.
8. **Mekanisme Locking via `flock`**: `flock` bekerja di level Open File Table VFS Linux Kernel (advisory locks via syscall `flock(fd, LOCK_EX)`). Kernel mengasosiasikan lock dengan struktur inode file referensi FD tersebut. Ketika instance kedua mencoba meminta lock eksklusif non-blocking (`flock -n`), kernel memeriksa struktur file lock table dan langsung menolak request dengan status non-zero jika lock sedang dipegang FD proses lain.
9. **Ekspansi `${VAR:=default}` vs `${VAR:-default}`**: `${VAR:-default}` mengevaluasi nilai string ke `default` jika `$VAR` unset/null, tetapi *tidak mengubah* nilai `$VAR` aslinya. `${VAR:=default}` mengevaluasi nilai string ke `default` dan sekaligus *mengisi/memutasi* variabel `$VAR` dengan nilai `default` tersebut jika sebelumnya unset/null.
10. **Mencegah Pathname Globbing**: Nonaktifkan pathname expansion pada parsing engine Bash menggunakan opsi `set -f` (atau `set -o noglob`).

#### Kasus Produksi
11. **Solusi Skenario A**: Masalah terjadi karena command substitution `$(...)` mengembalikan exit status command di dalamnya. Jika `psql` gagal, seluruh baris penugasan mengembalikan non-zero yang memicu `set -e`. Solusinya adalah menonaktifkan terminasi instan untuk baris penugasan tersebut menggunakan fallback logical OR `||`:
    ```bash
    RESULT=$(psql -h "$DB_HOST" -c "SELECT count(*) FROM users;" 2>&1) || {
        exit_code=$?
        echo "Database query error caught [Code: ${exit_code}]: ${RESULT}"
        # Lakukan mitigasi atau exit terkontrol
    }
    ```
12. **Solusi Skenario B**: Pisahkan lock handling dan eksekusi command dengan pembatasan durasi timeout native kernel. Bungkus network call dengan binary `timeout --kill-after=5s 30s <command>` di dalam script. Pastikan handler trap `EXIT` terkonfigurasi untuk melepaskan `flock` kapanpun proses dihentikan secara paksa oleh sistem.
13. **Solusi Skenario C**: Skrip lambat karena pengembang memanggil `echo` dan `awk` di dalam while loop. Jika terdapat 500.000 baris log, Bash akan melakukan `fork()` dan `execve()` sebanyak 1.000.000 kali. Overhead kernel context switching, alokasi page table, dan inisialisasi binary berulang kali ini membebani CPU. Solusi yang benar:
    * Singkirkan perulangan baris demi baris pada Bash.
    * Delegasikan seluruh proses parsing secara streaming langsung ke satu proses `awk` native:
    ```bash
    awk '{print $3}' access.log > extracted_users.txt
    ```
    Metode streaming tunggal ini hanya memanggil `fork()` dan `execve()` **satu kali**, memanfaatkan buffer I/O internal C runtime, dan selesai dalam hitungan detik untuk file puluhan gigabyte.

---

## 16. Summary

* Bash adalah lingkungan eksekusi perintah berbasis tokenisasi bertingkat yang berinteraksi langsung dengan antarmuka syscall kernel Linux (`fork`, `execve`, `dup2`, `flock`).
* Keandalan skrip otomasi skala enterprise bergantung pada penerapan strict header (`set -Eeuo pipefail`), pengaturan `$IFS` yang tepat, pengutipan (*quoting*) ekspresi variabel defensif, serta pembersihan resource terstruktur via `trap ... EXIT`.
* File descriptor kustom (FD 3–9) dan Named Pipes (FIFO) memungkinkan pemisahan jalur data stream dan telemetry logging tanpa bergantung pada intermediate disk storage yang lambat dan rentan bocor.
* Memahami kapan harus memanfaatkan Bash (sebagai pengendali orkestrasi binary host yang ringkas dan bebas dependency) dan kapan harus mendelegasikannya ke alat khusus stream-processing (`awk`, `sed`, `jq`) adalah pembeda fundamental antara skrip rapuh dengan arsitektur otomatisasi sistem kelas enterprise.