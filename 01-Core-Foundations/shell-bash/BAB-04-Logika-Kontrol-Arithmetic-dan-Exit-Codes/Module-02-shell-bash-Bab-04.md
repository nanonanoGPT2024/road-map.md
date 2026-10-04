# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Shell-Bash)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal eksekusi Bash pada level kernel (*process lifecycle*, *file descriptor table*, *subshell spawning*, dan *inter-process communication* via pipes/FIFOs).
- Merancang dan mengimplementasikan arsitektur otomasi Bash modular tingkat enterprise yang aman (*resilient*), terisolasi (*idempotent*), dan memiliki visibilitas sistem mendalam.
- Menguasai manajemen konkurensi, sinkronisasi proses non-blocking menggunakan *atomic locking primitives* (`flock`), dan kontrol sinyal asinkron (`trap`, `SIGTERM`, `SIGINT`, `EXIT`).
- Mendiagnosis dan mengeliminasi *performance bottlenecks* pada pipeline Bash dengan meminimalkan *system call overhead* dan *context switching*.
- Mengonstruksi *framework* penanganan kesalahan komprehensif (*stack tracing*, audit logging terstruktur berbasis JSON, dan *cleanup guarantees*).

---

## 2. Prerequisite

Peserta wajib memahami konsep dasar berikut sebelum mempelajari materi ini:
- Operasi dasar Linux/POSIX CLI (manipulasi file, permissions, pipes, dan redireksi I/O standar `stdin`, `stdout`, `stderr`).
- Sintaks dasar Bash: percabangan (`if/case`), perulangan (`for/while`), serta deklarasi variabel dan array.
- Konsep dasar OS: Threading, Process ID (PID), User Space vs Kernel Space, dan Virtual File System (VFS).
- Konfigurasi environment shell dasar (`PATH`, export variabel, dan eksekusi non-interaktif).

---

## 3. Concept & Internal Architecture

Eksekusi skrip Bash di lingkungan produksi menuntut pemahaman terhadap interaksi antara shell interpreter dan kernel Linux. Shell bukan sekadar *command runner*, melainkan sebuah proses tingkat pengguna (*user-space program*) yang bertindak sebagai antarmuka sistem operasi berbasis *system calls* (syscalls).

### 3.1 Siklus Proses: `fork()`, `execve()`, dan Subshell
Saat Bash mengeksekusi perintah eksternal (misal: `/usr/bin/jq` atau `/usr/bin/curl`):
1. **Fork Phase**: Bash memanggil syscall `fork()` (atau `clone()` di Linux modern) untuk menduplikasi dirinya sendiri. Proses baru ini memiliki Process ID (PID) baru, mewarisi *environment variables*, batas sumber daya (*limits*), dan *file descriptor table* dari *parent process*.
2. **Exec Phase**: Sub-proses tersebut segera memanggil syscall `execve()`. Syscall ini menimpa *address space* proses anak dengan program biner yang baru dipanggil, menginisialisasi stack, heap, dan segmen data baru.
3. **Wait Phase**: *Parent process* (Bash utama) memanggil `wait4()` untuk memblokir eksekusi hingga *child process* mengirimkan sinyal `SIGCHLD` dan mengembalikan nilai *exit status code* (0–255).

```
Parent Bash (PID: 1000)
    │
    ├─► fork() ──────────► Child Process (PID: 1001, Clone dari Bash)
    │                         │
    │                         ├─► execve("/usr/bin/curl", ...)
    │                         │   (Memory space diganti curl)
    │                         │
    │   wait4(1001)           ▼
    │   (Menunggu)         [curl mengeksekusi network request]
    │                         │
    │◄─ SIGCHLD (Exit 0) ─────┘
    ▼
Parent Bash berlanjut
```

Sebaliknya, **Subshell** (diinisiasi via kurung `( ... )`, substitusi perintah `$( ... )`, atau *piped command* pada POSIX default) melakukan `fork()` **tanpa** `execve()`. Subshell menduplikasi kondisi memori Bash secara *Copy-on-Write* (CoW). Modifikasi variabel, direktori aktif (`cd`), atau deskriptor file di dalam subshell **tidak akan pernah** mencemari proses induk (*parent shell memory isolation*).

### 3.2 File Descriptor Table & Virtual File System (VFS)
Setiap proses Linux memiliki tabel file descriptor (FD). Secara default:
- `0`: Standard Input (`stdin`)
- `1`: Standard Output (`stdout`)
- `2`: Standard Error (`stderr`)

Bash memungkinkan manipulasi FD tingkat lanjut (3 hingga 9+ untuk POSIX aman) melalui syscall `dup2()`.
- Redireksi `2>&1` menginstruksikan kernel: "Salin pointer file descriptor 1 ke file descriptor 2".
- Perintah eksekusi seperti `exec 3>&1 1>output.log` membuka kanal baru: FD 3 menyimpan target asli dari FD 1, sementara FD 1 dialihkan ke file `output.log`. Teknik ini fundamental dalam pembuatan engine logging ganda (*dual-stream output*).

### 3.3 Named Pipes (FIFO) vs Anonymous Pipes
- **Anonymous Pipes (`|`)**: Kernel mengalokasikan *buffer* memori sirkular (biasanya 64 KB di Linux). Komunikasi berlangsung satu arah (*unidirectional*). Pipeline otomatis memicu `fork()` untuk setiap segmen perintah pada shell default, memicu eksekusi konkuren.
- **Named Pipes (FIFO via `mkfifo`)**: Entri direktori khusus pada VFS yang bertindak sebagai pipe tetapi memiliki nama pada filesystem. FIFO memblokir operasi `open()` untuk write hingga ada proses yang membuka untuk read, memungkinkan orkestrasi *producer-consumer* decoupled lintas script independen tanpa menggunakan disk storage.

### 3.4 Mekanisme Interupsi & Kernel Signals
Kernel berkomunikasi dengan proses via *asynchronous signals*. Bash menangani sinyal melalui syscall `sigaction`:
- `SIGINT` (2): Interupsi dari terminal (Ctrl+C).
- `SIGTERM` (15): Permintaan terminasi gracefully dari supervisor (misal: Kubernetes, systemd).
- `SIGKILL` (9): Terminasi paksa oleh kernel (tidak dapat di-trap atau di-ignore).
- `EXIT` (Pseudo-signal internal Bash 0): Dijalankan saat script berhenti secara normal atau abnormal via `exit`.

---

## 4. Why & What

### Mengapa Bash Tetap Esensial di Era Modern?
Meskipun Python, Go, dan Rust mendominasi sistem backend modern, Bash memegang peran kritikal pada level orkestrasi infrastruktur:
1. **Zero Runtime Dependency**: Tersedia secara *native* pada hampir setiap distribusi Linux, container minimalis (Alpine/Debian/RHEL), dan init system.
2. **Glue Language Superiority**: Menghubungkan berbagai biner sistem (Coreutils, AWS CLI, Kubectl, Docker, jq) tanpa overhead deserialisasi memori runtime level tinggi.
3. **Container Entrypoints**: Digunakan sebagai PID 1 wrapper di container untuk menangani propagasi sinyal (*signal forwarding*) dan konfigurasi dinamis sebelum aplikasi utama dieksekusi.

### Kapan Menggunakan Bash vs Bahasa Lain?
| Karakteristik | Shell (Bash 5.x) | Python / Go |
| :--- | :--- | :--- |
| **Kekuatan Utama** | Orkestrasi CLI biner, modifikasi I/O OS, container boot | Logika bisnis kompleks, parsing data berat, multithreading memori |
| **Footprint Memori** | Sangat Rendah (~2-4 MB) | Sedang hingga Tinggi (Python: ~30MB+, Go: runtime static) |
| **Kelemahan** | Manipulasi tipe data heterogen, kalkulasi floating point | Membutuhkan eksternal dependencies/runtime engine |
| **Ideal Use-Case** | Script deploy, CI/CD pipelines, system bootstrap, healthcheck | API backend, distributed worker, database heavy tasks |

---

## 5. How (Workflow Detail Arsitektur)

Untuk mencapai reliabilitas setara production-grade software, alur eksekusi script harus mengikuti arsitektur berstandar berikut:

```
+-------------------------------------------------------+
|  1. BOOTSTRAP: Strict Mode Settings (set -Eeuo pipefail)|
+-------------------------------------------------------+
                           │
                           ▼
+-------------------------------------------------------+
|  2. INITIALIZATION: Setup Signal Handlers & Traps     |
|     (Trap SIGTERM, SIGINT, and EXIT for cleanup)      |
+-------------------------------------------------------+
                           │
                           ▼
+-------------------------------------------------------+
|  3. CONCURRENCY CONTROL: Acquire Atomic Lock (flock)  |
|     (Prevent duplicate runs via File Descriptor)      |
+-------------------------------------------------------+
                           │
                           ▼
+-------------------------------------------------------+
|  4. RUNTIME EXECUTION: Modular & Structured Logging    |
|     (JSON Output, In-memory pipes, subshell safety)   |
+-------------------------------------------------------+
                           │
                           ▼
+-------------------------------------------------------+
|  5. TERMINATION: Cleanup Handlers Run Automatically   |
|     (Release lock, purge temporary FIFO, report exit) |
+-------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konduktor Orkestra vs Pabrik Manufaktur
Bash berperan seperti **Konduktor Orkestra**. Konduktor tidak memainkan biola atau meniup terompet secara langsung; ia memberikan instruksi kepada musisi spesialis (biner eksternal: `grep`, `awk`, `sed`, `curl`) kapan harus bersuara dan mengatur jalur suaranya. Menggunakan Bash untuk memproses manipulasi string jutaan baris per karakter sama seperti menyuruh konduktor memainkan semua alat musik sekaligus—sangat lambat dan tidak efisien. Bash harus mendelegasikan pemrosesan data masif ke biner eksternal atau memanipulasi *stream pointer*.

### Arsitektur Kernel Memory & FD Routing
```
+---------------------------------------------------------------+
|                       USER SPACE                              |
|                                                               |
|  [ Parent Bash Process ]                                      |
|  ├─ PID: 40120                                                |
|  ├─ Memory Heap/Stack: Variables, Functions, Call Stack       |
|  └─ File Descriptor (FD) Table:                               |
|        FD 0 ──► Keyboard /dev/pts/1                           |
|        FD 1 ──► [pipe:12034] ──────────┐                      |
|        FD 2 ──► /var/log/err.log       │                      |
|        FD 3 ──► Lockfile (/var/run/..) │                      |
|                                        │                      |
+----------------------------------------┼----------------------+
|                       KERNEL SPACE     │                      |
|                                        ▼                      |
|  [ VFS / Pipe Buffer: 64KB Circular Buffer in RAM ]           |
|                                        │                      |
+----------------------------------------┼----------------------+
|                       USER SPACE       ▼                      |
|                                                               |
|  [ Child Process: jq / awk ] ◄─────────┘                      |
|  ├─ PID: 40121 (Forked & Execve'd)                            |
|  └─ FD 0 ──► Consumes from [pipe:12034]                       |
|     FD 1 ──► Standard Output                                  |
+---------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Defensive Boilerplate Engine
Skrip ini mendemonstrasikan implementasi `Strict Mode`, *Signal Interception*, dan *Dual Logger*.

```bash
#!/usr/bin/env bash

# STRICT MODE:
# -e: Berhenti jika ada perintah non-zero exit code
# -u: Berhenti jika ada variabel yang belum didefinisikan
# -o pipefail: Pipeline gagal jika salah satu perintah di dalamnya gagal
# -E: ERR trap diwariskan ke shell function dan subshell
set -Eeuo pipefail

# Inisialisasi Environment
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOG_FILE="/tmp/${SCRIPT_NAME%.*}.log"

# Setup Dual Output (Terminal & File) tanpa subshell logging tool
exec 3>&1 4>&2
exec 1>>"${LOG_FILE}" 2>&1

log() {
    local level="$1"
    shift
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    # Menulis ke file log (FD 1 saat ini) dan ke terminal asli (FD 3)
    printf '{"timestamp":"%s","level":"%s","message":"%s"}\n' \
        "${timestamp}" "${level}" "$*" | tee /dev/fd/3
}

cleanup() {
    local exit_code=$?
    log "INFO" "Proses pembersihan (cleanup) dijalankan dengan exit code: ${exit_code}"
    # Mengembalikan standard file descriptor
    exec 1>&3 2>&4
    exec 3>&- 4>&-
    exit "${exit_code}"
}

# Trap menangani sinyal sistem
trap cleanup EXIT
trap 'log "FATAL" "Interupsi SIGINT diterima"; exit 130' SIGINT
trap 'log "FATAL" "Terminasi SIGTERM diterima"; exit 143' SIGTERM

log "INFO" "Sistem berhasil diinisialisasi."
# Simulasi pekerjaan
log "INFO" "Memproses pipeline data..."
```

---

### 7.2 Practical Example: Enterprise Modular Ingestion Engine
Contoh skrip arsitektur produksi untuk memproses ingest data file batch dengan *atomic non-blocking lock*, *stack tracing*, dan isolasi proses.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Batch Ingestion Engine
# Memenuhi Standar: POSIX Compliant subset, High Resiliency, Bash 4.4+
# ==============================================================================
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Global Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly LOCK_FILE="/var/lock/data_ingestor.lock"
readonly LOCK_FD=200
readonly WORK_DIR="/tmp/ingestor_worker_$$"

# Trap handler untuk stack trace saat runtime error terjadi
error_stack_tracer() {
    local exit_code=$?
    local failed_command="${BASH_COMMAND}"
    local line_no="${BASH_LINENO[0]}"
    
    printf '{"event":"CRITICAL","file":"%s","line":%s,"command":"%s","exit_code":%d}\n' \
        "${BASH_SOURCE[0]}" "${line_no}" "${failed_command}" "${exit_code}" >&2
        
    local frame=0
    while caller_info=($(caller $frame)); do
        printf '{"event":"STACK_TRACE","frame":%d,"line":%s,"function":"%s","file":"%s"}\n' \
            "${frame}" "${caller_info[0]}" "${caller_info[1]}" "${caller_info[2]}" >&2
        ((frame++))
    done
    exit "${exit_code}"
}
trap error_stack_tracer ERR

# Clean-up routine
terminate_pipeline() {
    local exit_code=$?
    # Hapus scratch directory jika ada
    [[ -d "${WORK_DIR}" ]] && rm -rf "${WORK_DIR}"
    
    # Lepas kernel lock
    flock -u "${LOCK_FD}" 2>/dev/null || true
    eval "exec ${LOCK_FD}>&-"
    
    printf '{"event":"SYSTEM_SHUTDOWN","exit_code":%d}\n' "${exit_code}"
    exit "${exit_code}"
}
trap terminate_pipeline EXIT SIGINT SIGTERM

acquire_exclusive_lock() {
    # Membuka FD 200 ke file lock
    eval "exec ${LOCK_FD}>\"${LOCK_FILE}\""
    
    # Non-blocking exclusive lock (flock -n)
    if ! flock -x -n "${LOCK_FD}"; then
        printf '{"event":"LOCK_FAILED","error":"Instansiasi lain sedang berjalan. Abort."}\n' >&2
        exit 11
    fi
}

process_dataset() {
    local input_payload="$1"
    local staging_target="${WORK_DIR}/payload.tmp"
    
    printf '{"event":"PROCESSING_START","payload":"%s"}\n' "${input_payload}"
    
    # Simulasi safe parsing via pipe stream tanpa intermediate storage yang rentan race condition
    mkdir -p "${WORK_DIR}"
    echo "${input_payload}" > "${staging_target}"
    
    # Data transformation menggunakan in-memory pipeline
    awk '{ print toupper($0) }' "${staging_target}" > "${WORK_DIR}/result.dat"
    
    printf '{"event":"PROCESSING_SUCCESS","output_file":"%s/result.dat"}\n' "${WORK_DIR}"
}

main() {
    acquire_exclusive_lock
    
    local sample_data="batch_record_id:9981 status:valid"
    process_dataset "${sample_data}"
}

main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Telemetry Processing Daemon pada Klaster 5.000 Node
**Problem Statement**: 
Sebuah perusahaan logistik skala global menjalankan agent telemetry di 5.000 bare-metal Linux edge router. Agent ini bertugas mengekstrak status jaringan, memvalidasi integritas metrik, dan mengirimkannya ke streaming ingestion endpoint via HTTP POST. 

**Kegagalan Sistem Sebelumnya**:
1. *Subshell Explosion*: Script versi lama menggunakan ekspresi `output=$(grep ... | awk ... | sed ...)` di dalam perulangan `while true` tiap 1 detik. Setiap siklus memicu lebih dari 15 kali `fork()` dan `execve()`. Pada ribuan edge routers berkemampuan komputasi terbatas, load average melonjak (*high CPU Context Switches*) hingga script dibunuh oleh Linux OOM Killer.
2. *Zombified Processes & Signal Drop*: Ketika systemd mengirim sinyal `SIGTERM` untuk upgrade, child sub-process tidak meneruskan sinyal. Daemon mati seketika, meninggalkan *uncommitted state* dan transfer log yang korup (*zero data loss guarantee breached*).

### Solusi Desain Arsitektur Baru
1. Menghilangkan external forks dengan mengutamakan **Bash 5.x Built-in Operations** (`${var//search/replace}`, pattern matching arrays) daripada pemanggilan binary `sed`/`awk` eksternal.
2. Menggunakan **Named Pipes (FIFO)** untuk membaca log stream secara kontinu tanpa looping polling disk.
3. Menggunakan **PID 1 Signal Trap Relay Structure** untuk menangkap sinyal `SIGTERM`, menyelesaikan batch saat ini (drain cycle), dan *exit* secara elegan.

### Diagram Alur Solusi:
```
[Kernel Event / Driver System]
            │
            ▼ (Raw Log Streams)
+---------------------------------------+
| System FIFO: /run/telemetry.pipe     |
+---------------------------------------+
            │ (Continuous Streaming I/O)
            ▼
+---------------------------------------+
| Optimized Bash Engine (PID 1204)      |
| ├─ In-memory string manipulation      |
| ├─ Zero external forks in hot-path   |
| ├─ Batch Accumulator (Buffer 500ms)   |
+---------------------------------------+
            │
            ▼ (Atomic HTTP POST payload)
[Upstream Log Platform / API Gateway]
```

### Hasil Optimasi:
- CPU utilization turun dari **34% menjadi 1.2%** pada CPU core router single-core.
- Context switches terpangkas dari **~8.000 switches/sec menjadi kurang dari 40 switches/sec**.
- Zero crash / zero unhandled data corruption saat auto-scaling deployments.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Pure Built-ins** (Bash internal parameter expansion) | Performa sangat tinggi (0 `fork()` overhead), latensi eksekusi mikrodetik. | Kapabilitas ekspresi regex terbatas, keterbacaan kode (*readability*) menurun bagi pemula. |
| **External Binaries** (`jq`, `awk`, `sed`, `grep`) | Kaya fitur, efisien untuk parsing file berukuran Gigabyte. | Biaya `fork()` dan `execve()` tinggi jika dipanggil di dalam loop (*hot-path* anti-pattern). |
| **Atomic File Locking** (`flock`) | Mencegah *race condition* dan eksekusi skrip ganda (*safe single-instance guarantee*). | Berpotensi menyebabkan *deadlock* jika tidak didesain dengan trap cleanup yang ketat. |
| **Named Pipes (FIFO)** | Streaming I/O murni tanpa latensi disk atau pemakaian RAM/SSD berlebih. | Blocking behavior secara default; jika reader gagal bangun, writer akan macet selamanya (*hang*). |
| **Subshell Encapsulation** `( ... )` | Isolasi variabel dan state sistem secara absolut. | *Memory duplicate via CoW*, data dari dalam subshell tidak bisa dikembalikan ke parent secara langsung. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Broken Pipeline Masking via `pipefail` Unset
```bash
# SALAH: Eksekusi berlanjut meski curl gagal total (Network Error 404/500)
curl -sSf https://api.internal/data.json | jq '.records'

# HASIL: Exit code bernilai 0 (karena jq membaca input kosong dan keluar dengan aman).
# Data corruption terjadi di downstream!

# PERBAIKAN:
set -eo pipefail
curl -sSf https://api.internal/data.json | jq '.records'
# Skrip langsung abort karena curl gagal, memicu failure pipeline.
```

### Mistake 2: Reading File Line-by-Line using Subshell Fork Anti-pattern
```bash
# SALAH: Subshell memory loss
cat dataset.txt | while read -r line; do
    total_records=$((total_records + 1))
done
echo "Total: ${total_records}" 
# HASIL: Total tetap 0 atau kosong! Karena 'while' berada di dalam subshell akibat anonymous pipe (|).

# PERBAIKAN: Process Substitution (Parent shell preserves state)
while read -r line; do
    total_records=$((total_records + 1))
done < <(grep "SUCCESS" dataset.txt)
echo "Total: ${total_records}" # Mengembalikan nilai akurat!
```

### Mistake 3: Unquoted Variables in Expansion Leading to Word Splitting & Globbing
```bash
# SALAH: Rentan path injection atau error whitespace
target_dir=/opt/data store/backup
rm -rf $target_dir # Akan mengeksekusi 'rm -rf /opt/data' dan 'store/backup'!! BENCANA SISTEM.

# PERBAIKAN: Selalu gunakan quotes eksplisit
rm -rf -- "${target_dir}"
```

### Panduan Troubleshooting Debugging:
1. Jalankan mode trace eksekusi: `bash -x ./script.sh`.
2. Lacak system call yang memicu perlambatan menggunakan `strace`:
   ```bash
   strace -f -e trace=clone,fork,execve,openat,read,write -s 256 ./script.sh
   ```
3. Identifikasi kebocoran File Descriptor:
   ```bash
   ls -l /proc/$$/fd
   ```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebelum mempromosikan skrip Bash ke lingkungan produksi:

- [ ] **Defensive Directives**: Baris awal script mendefinisikan `set -Eeuo pipefail`.
- [ ] **Signal Handling**: Memiliki konfigurasi `trap` minimum untuk sinyal `EXIT`, `SIGINT`, dan `SIGTERM`.
- [ ] **Locking Mechanism**: Menggunakan `flock` berbasis kernel file descriptor, bukan folder `mkdir` manual atau file `.pid` biasa yang rentan *stale locks*.
- [ ] **Safe Path Resolution**: Seluruh resolusi path menggunakan path absolut yang bersumber dari `${BASH_SOURCE[0]}`.
- [ ] **Command Checking**: Memvalidasi keberadaan *external tool* dependensi di awal eksekusi:
  ```bash
  command -v jq >/dev/null 2>&1 || { echo "Fatal: jq is required" >&2; exit 1; }
  ```
- [ ] **Avoid Hot-path Subshells**: Mengeliminasi penggunaan command substitution `$( ... )` di dalam perulangan berskala ribuan iterasi.
- [ ] **Quoting Consistency**: Semua variabel yang diekspansikan dibungkus dalam tanda kutip ganda `"${my_var}"`.
- [ ] **Structured Logging**: Logging diarahkan ke `stderr` (`>&2`) dengan format parsing-friendly (JSON / Key-Value) dan menyertakan timestamp UTC.
- [ ] **Temporary File Handling**: Seluruh temporary file dibuat via `mktemp` dan dihapus melalui trap handler `EXIT`.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum pada folder: `hands-on/m02/`.

### Langkah 1: Setup Lingkungan Praktikum
Buka terminal dan jalankan:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat Modul Reusable Stack Tracer (`tracer.sh`)
Buat file `hands-on/m02/tracer.sh`:
```bash
#!/usr/bin/env bash
# tracer.sh - Production crash inspection module
init_tracer() {
    set -Eeuo pipefail
    trap 'catch_error $? $LINENO "$BASH_COMMAND"' ERR
}

catch_error() {
    local exit_code="$1"
    local line_no="$2"
    local command="$3"
    
    printf "\n=== FATAL EXCEPTION DETECTED ===\n" >&2
    printf "Time: %s\n" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >&2
    printf "Command: '%s'\n" "${command}" >&2
    printf "Line Number: %s\n" "${line_no}" >&2
    printf "Exit Code: %d\n" "${exit_code}" >&2
    printf "Call Trace:\n" >&2
    
    local i=0
    while caller_line=($(caller $i)); do
        printf "  [%d] File: %s | Line: %s | Func: %s\n" \
            "$i" "${caller_line[2]}" "${caller_line[0]}" "${caller_line[1]}" >&2
        ((i++))
    done
    printf "================================\n" >&2
    exit "${exit_code}"
}
```

### Langkah 3: Buat Producer-Consumer Process via FIFO (`ipc_pipeline.sh`)
Buat file `hands-on/m02/ipc_pipeline.sh`:
```bash
#!/usr/bin/env bash
set -Eeuo pipefail
source ./tracer.sh
init_tracer

readonly FIFO_PATH="/tmp/worker_stream_$$.fifo"

# Buat FIFO pipe
mkfifo "${FIFO_PATH}"

# Pastikan FIFO dihapus saat selesai
cleanup() {
    rm -f "${FIFO_PATH}"
    printf '{"status":"FIFO_CLEANED"}\n'
}
trap cleanup EXIT

# Background Consumer
consumer_process() {
    printf '{"consumer":"STARTED"}\n'
    while read -r data_line; do
        if [[ "${data_line}" == "TERMINATE" ]]; then
            break
        fi
        printf '{"consumer_received":"%s"}\n' "${data_line}"
    done < "${FIFO_PATH}"
}

# Jalankan consumer di background
consumer_process &
CONSUMER_PID=$!

# Writer / Producer
printf 'RECORD_ALPHA\n' > "${FIFO_PATH}"
printf 'RECORD_BETA\n' > "${FIFO_PATH}"
printf 'TERMINATE\n' > "${FIFO_PATH}"

# Tunggu background worker selesai
wait "${CONSUMER_PID}"
printf '{"pipeline":"SUCCESS"}\n'
```

### Langkah 4: Uji dan Eksekusi
```bash
chmod +x tracer.sh ipc_pipeline.sh
./ipc_pipeline.sh
```

---

## 13. Exercise

### Level Easy
Modifikasi skrip `hands-on/m02/ipc_pipeline.sh` agar mencatat timestamp (milidetik) saat consumer menerima data menggunakan built-in Bash variables (`${EPOCHREALTIME}` pada Bash 5.0+).

### Level Medium
Buat sebuah script bernama `hands-on/m02/concurrency_pool.sh` yang mengeksekusi 10 tugas simulasi (`sleep $((RANDOM % 3 + 1))`) secara paralel, namun membatasi eksekusi maksimum hanya **3 proses secara simultan** (Worker Pool pattern) murni menggunakan Bash primitives dan built-in process tracking (`jobs -r` atau PID array).

### Level Hard
Rancang engine distributed task runner bernama `hands-on/m02/batch_executor.sh` yang menerima input file CSV berisi 100 URL endpoint. Script harus:
1. Membaca CSV tanpa memicu subshell fork loop.
2. Menggunakan pool worker (max 5 parallel processes).
3. Menyimpan hasil response HTTP status ke dalam satu file shared output secara *thread-safe* (menggunakan locking mechanism `flock` pada file target).
4. Menangani graceful shutdown saat menerima `SIGTERM`: segera selesaikan task yang sedang aktif, jangan ambil task baru dari CSV, lalu exit dengan kode status 143.

---

## 14. Challenge (Tantangan Studi Kasus Nyata)

### Skenario: Resilient Zero-Downtime Agent Updater Daemon

Anda diminta merancang *Core Architecture Script* untuk agen daemon yang terpasang pada 20.000 server bare-metal edge. 

**Objektif:**
Rancang sebuah file script tunggal `enterprise_agent.sh` yang bertindak sebagai runner monitoring dengan batasan arsitektur sebagai berikut:

1. **Self-Healing & Auto-Update In-Place**:
   Agent harus dapat melakukan pembaruan biner script-nya sendiri tanpa mematikan proses monitoring utama yang sedang memegang lock I/O.
2. **Deterministic Mutex Protocol**:
   Jika administrator secara tidak sengaja menjalankan 2 instance script secara manual melalui remote SSH, instance kedua harus mendeteksi keberadaan instance pertama, mengambil PID-nya, memverifikasi apakah instance tersebut hidup melalui sinyal `/proc/${PID}/status`, dan jika tidak merespons (deadlock), mengambil alih secara paksa (*lock acquisition takeover*) secara aman (*zero race-condition*).
3. **Backpressure Stream**:
   Script menerima data telemetri acak dari file `/dev/urandom`, mengubahnya menjadi representasi hexadesimal, dan mengirimkannya ke remote endpoint. Script harus mampu mendeteksi jika throughput I/O lokal mengalami degradasi, lalu mengaktifkan mekanisme *backoff retry* otomatis tanpa menumpuk *buffer cache* pada memori kernel.
4. **Signal Forwarding Contract**:
   Script harus mengonversi dan mempropagasi sinyal Docker/Container (`SIGQUIT`, `SIGTERM`, `SIGHUP`) ke seluruh sub-proses yang ia lahirkan tanpa meninggalkan *orphan* atau *zombie process*.

*Kirimkan rancangan arsitektur lengkap beserta script implementasi yang telah diuji stress-testing-nya.*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)

1. **Apa fungsi dari opsi `set -o pipefail` di Bash?**
   - A. Membuat proses piping berjalan multi-threading di core CPU berbeda.
   - B. Memastikan pipeline mengembalikan nilai status exit non-zero dari perintah terakhir yang gagal, bukan status perintah terakhir.
   - C. Mencegah kernel menggunakan buffer disk saat I/O pipeline penuh.
   - D. Mengubah anonymous pipe menjadi POSIX Named Pipe secara otomatis.

2. **Kapan Kernel Linux memanggil syscall `execve()` pada Bash script?**
   - A. Setiap kali ada deklarasi fungsi baru.
   - B. Saat script mengeksekusi subshell `( cd /tmp && ls )`.
   - C. Saat sebuah binary eksternal dipanggil setelah pemanggilan `fork()`.
   - D. Setiap kali variabel lokal shell di-assign nilainya.

3. **Mengapa penulisan konstruksi `while read line; do ... done < file.txt` lebih disukai dibandingkan `cat file.txt | while read line; do ... done`?**
   - A. Karena `cat` dibatasi oleh ukuran RAM.
   - B. Karena konstruksi pipa memicu eksekusi loop di dalam subshell, sehingga mutasi variabel di dalam loop hilang setelah loop selesai.
   - C. Karena `read` tidak bisa membaca data dari stdout `cat`.
   - D. Karena `cat` selalu mengubah format encoding file menjadi ASCII.

4. **File descriptor integer standar untuk `stderr` pada sistem POSIX adalah:**
   - A. 0
   - B. 1
   - C. 2
   - D. 3

5. **Apa fungsi utama dari utilitas kernel-level `flock` dalam skrip Bash?**
   - A. Mengompresi file log secara otomatis saat runtime.
   - B. Mengunci file descriptor menggunakan fungsi `flock(2)` pada kernel untuk mencegah eksekusi paralel ganda (*race condition*).
   - C. Melakukan enkripsi berkas secara asimetris.
   - D. Membatasi memory heap yang boleh digunakan oleh subshell.

---

### 15.2 Pertanyaan Intermediate (Pilihan Ganda)

6. **Diberikan baris kode berikut:**
   ```bash
   exec 3>&1 1>>/var/log/app.log
   ```
   **Apa status konfigurasi File Descriptor tabel pada proses shell saat ini?**
   - A. FD 3 dinonaktifkan, FD 1 menduplikasi input dari keyboard.
   - B. FD 3 menduplikasi target asli dari stdout (misal: terminal), dan FD 1 dialihkan untuk append ke file `/var/log/app.log`.
   - C. FD 1 dan FD 3 bertukar alamat memori pada level VFS.
   - D. Kernel mengunci file `/var/log/app.log` dari proses penulisan proses lain.

7. **Bagaimana sifat perilaku subshell `( VAR="NEW" )` terhadap environment parent shell?**
   - A. Nilai `VAR` berubah di parent shell jika menggunakan deklarasi `export`.
   - B. Subshell mewarisi salinan copy-on-write dari parent, modifikasi nilai `VAR` tidak berdampak pada parent shell.
   - C. Terjadi panic error jika subshell memodifikasi variabel bertipe `readonly`.
   - D. Parent shell menerima nilai baru setelah proses subshell mengirimkan sinyal `SIGCHLD`.

8. **Apa perbedaan teknis mendasar antara `trap '...' EXIT` dan `trap '...' SIGTERM`?**
   - A. `SIGTERM` dieksekusi saat script selesai secara normal, `EXIT` hanya saat ada error.
   - B. `EXIT` adalah pseudo-signal Bash internal yang pasti dipicu saat proses shell berakhir (normal maupun abnormal), sedangkan `SIGTERM` adalah sinyal interupsi OS yang harus dikirim eksplisit oleh entitas luar.
   - C. `EXIT` tidak bisa memanggil external function.
   - D. `SIGTERM` mengeksekusi cleanup function di background subshell.

9. **Jika pada script terdapat baris `set -e` dan sebuah command menghasilkan exit code non-zero di dalam blok evaluasi `if`, apa yang terjadi?**
   ```bash
   set -e
   if grep -q "pattern" missing_file.txt; then
       echo "Found"
   fi
   ```
   - A. Skrip langsung crash/berhenti pada pemanggilan `grep`.
   - B. Skrip melanjutkan eksekusi karena perintah yang diuji di dalam kontrol alur `if` atau `while` dikecualikan dari pemutusan `set -e`.
   - C. Bash melakukan rollback pada isi file `missing_file.txt`.
   - D. Kernel memancarkan sinyal `SIGKILL` ke parent shell.

10. **Apa yang terjadi ketika sebuah proses menulis ke Named Pipe (FIFO) yang belum memiliki proses pembaca (Reader)?**
    - A. Data dibuang langsung ke `/dev/null`.
    - B. Operasi write akan terblokir (*blocked/hang*) pada kernel level sampai ada proses lain yang membuka pipe tersebut untuk membaca.
    - C. Kernel langsung melempar sinyal `SIGPIPE` dan mematikan script seketika.
    - D. FIFO menyimpan data tak terbatas di memori swap disk.

---

### 15.3 Skenario Kasus Produksi (Analisis Mendalam)

#### Kasus 1: Insiden Kebocoran Resource di Kubernetes CronJob
**Skenario**: Sebuah skrip Bash dijalankan sebagai Kubernetes CronJob setiap 5 menit untuk memproses backup database. Muncul alert bahwa node Kubernetes mengalami kondisi `PID Pressure` (PID pool habis, node crash). Hasil inspeksi menunjukkan ribuan proses `backup_script.sh` berstatus *defunct* (zombie).
```bash
#!/usr/bin/env bash
# backup_script.sh
run_backup() {
    tar -czf /backup/db_$(date +%s).tar.gz /data &
}
run_backup
# Script exit langsung tanpa wait
```
**Pertanyaan Kasus 1**:
Jelaskan mengapa akumulasi proses *defunct* terjadi di kernel Linux dan bagaimana arsitektur Bash yang benar untuk menjamin *child process reapings* sebelum parent process terminate!

#### Kasus 2: Deadlock Masif pada Transaksi File Log
**Skenario**: Dua daemon Bash (`worker_A.sh` dan `worker_B.sh`) saling berebut mengakses file mutasi status:
- Worker A: Membuka lock FD 200 pada file `/tmp/state.lock`, lalu mencoba membuka lock FD 201 pada file `/tmp/config.lock`.
- Worker B: Membuka lock FD 201 pada file `/tmp/config.lock`, lalu mencoba membuka lock FD 200 pada file `/tmp/state.lock`.
Kedua worker berhenti total (*hung indefinitely*).
**Pertanyaan Kasus 2**:
Analisis fenomena OS apa yang sedang terjadi di atas, dan rancang strategi pertahanan implementasi shell script locking untuk mencegah kebuntuan tersebut!

#### Kasus 3: Kegagalan Ingestion Pipeline Tersembunyi pada Docker CI/CD
**Skenario**: Script deployment pipeline CI/CD memiliki baris perintah berikut:
```bash
set -e
docker build -t my-app . | tee build.log
deploy_app
```
Suatu hari, `docker build` gagal total karena error sintaks pada Dockerfile. Namun, langkah `deploy_app` tetap dieksekusi di runner dan men-deploy container versi lama yang rusak ke cluster staging.
**Pertanyaan Kasus 3**:
Mengapa `set -e` gagal menghentikan script pada kegagalan `docker build` di pipeline tersebut, dan bagaimana implementasi perbaikan standarnya?

---

### Kunci Jawaban Evaluasi

#### Jawaban 15.1 (Basic)
1. **B** — `pipefail` memastikan pipeline mewarisi status error dari command paling kanan yang gagal.
2. **C** — `execve()` dipanggil saat binary eksternal dieksekusi untuk menimpa space memori anak fork.
3. **B** — Redireksi via pipe (`|`) mengisolasi variabel di dalam subshell; proses substitusi atau direct redirection menjaga memori context pada parent.
4. **C** — Standar POSIX menetapkan deskriptor integer 2 sebagai standard error (`stderr`).
5. **B** — `flock` memanggil fungsi kernel C `flock(2)` untuk sinkronisasi mutex akses via file descriptor.

#### Jawaban 15.2 (Intermediate)
6. **B** — Operator `3>&1` menyalin stdout ke FD 3, kemudian operator `1>>` mengalihkan stdout ke file log.
7. **B** — Subshell memiliki sifat *memory isolation* melalui arsitektur CoW (*Copy-on-Write*).
8. **B** — `EXIT` adalah pseudo-signal Bash komprehensif, sementara `SIGTERM` adalah sinyal OS spesifik.
9. **B** — Sesuai spesifikasi POSIX, perintah yang dievaluasi langsung oleh conditional construct (`if`, `while`, `until`) tidak terpengaruh abort `set -e`.
10. **B** — FIFO bersifat *synchronous rendezvous*: proses penulisan diblokir sampai ada sisi pembaca yang aktif.

#### Jawaban 15.3 (Solusi Skenario Produksi)
* **Solusi Kasus 1**:
  - **Penyebab**: Script menjalankan proses kompresi di background (`&`) lalu langsung keluar. Saat child process selesai setelah parent-nya mati, child mencari parent baru (di-adopt oleh PID 1/systemd). Jika init system di dalam container bukan init sejati (misal Docker tanpa flag `--init`), proses yang selesai tersebut tidak pernah di-`wait()` (*reaped*), sehingga entri PID-nya tetap tersangkut di Process Table kernel sebagai proses *defunct* (Zombie).
  - **Perbaikan**: Tambahkan perintah built-in `wait` sebelum exit, atau bind trap sinyal `CHLD`:
    ```bash
    wait "${!}" # Menunggu PID terakhir selesai
    ```
* **Solusi Kasus 2**:
  - **Penyebab**: Terjadi *Circular Deadlock* (Coffman Condition) akibat *inconsistent lock acquisition order*.
  - **Perbaikan**:
    1. Standarisasi urutan lock acquisition: semua worker wajib meminta `state.lock` terlebih dahulu, baru kemudian `config.lock`.
    2. Hindari blocking locking: gunakan flags non-blocking `flock -n` atau terapkan timeout menggunakan `flock -w 5` (timeout 5 detik). Jika gagal mendapatkan lock sekunder, lepaskan lock primer, lakukan random sleep (jitter), lalu ulangi (*exponential backoff*).
* **Solusi Kasus 3**:
  - **Penyebab**: Karena perintah `docker build` berada di sisi kiri dari pipeline yang terhubung ke `tee`, exit code yang diperiksa oleh `set -e` secara default hanyalah exit code dari perintah **terakhir** dalam pipeline (yaitu `tee`). Karena `tee` berhasil menulis error stream ke disk, `tee` keluar dengan status code 0. Akibatnya, `set -e` menganggap pipeline sukses.
  - **Perbaikan**: Tambahkan `set -o pipefail` di header script. Ini memaksa pipeline mengembalikan status failure milik `docker build`.

---

## 16. Summary

Pengembangan skrip Bash tingkat enterprise membutuhkan pergeseran paradigma dari sekadar menyusun urutan perintah ad-hoc menjadi rekayasa perangkat lunak sistem yang kokoh. Kualitas script produksi ditentukan oleh ketahanannya dalam menghadapi kondisi tak terduga (*fault-tolerance*), pengelolaan konkurensi data yang aman, penggunaan resource kernel yang efisien, dan transparansi proses melalui *stack trace* dan logging yang terstruktur.

Dengan menguasai manipulasi *File Descriptor*, memahami mekanisme siklus proses kernel (`fork`/`exec`), menggunakan *defensive setting* (`-Eeuo pipefail`), serta mengunci akses file secara atomik melalui `flock`, insinyur sistem dapat membangun fondasi otomasi yang stabil, aman, dan siap beroperasi di skala ribuan server enterprise modern.