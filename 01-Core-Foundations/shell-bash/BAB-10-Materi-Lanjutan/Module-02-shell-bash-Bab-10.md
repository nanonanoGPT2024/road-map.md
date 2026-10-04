# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:

- Mengabstraksi dan mengendalikan siklus hidup proses POSIX/Linux (`fork(2)`, `execve(2)`, `clone(2)`) langsung dari konteks shell Bash.
- Mendesain pipeline manipulasi I/O multi-aliran menggunakan File Descriptor (FD) kustom, non-blocking I/O, Named Pipes (FIFO), dan Process Substitution dengan mitigasi *deadlock*.
- Mengimplementasikan sistem sinkronisasi concurrency dan *distributed locking* lokal berskala enterprise menggunakan *atomic lockfiles* via kernel (`flock(2)` / `noclobber`).
- Menguasai penanganan sinyal asinkronus (`POSIX Signals`), terminasi deterministik (graceful shutdown), serta propagasi sinyal lintas Process Group ID (PGID).
- Mengaudit, memprofil, dan mengoptimalkan performa eksekusi skrip Bash untuk meminimalkan alokasi memori *subshell* dan latensi *context switching* level kernel.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:

- Fundamental UNIX Shell Scripting: parameter expansion lanjutan (`${var//pattern/replace}`), arrays (indexed & associative), dan exit status (`$?`).
- Pemahaman sistem operasi Linux: Virtual Memory, Copy-On-Write (COW), tabel File Descriptor per proses, Process Table, VFS (*Virtual File System*), dan *inode*.
- Konsep dasar concurrency: Race condition, Atomic operation, Semaphore, Mutex, dan Buffer saturation.
- Tools diagnostik POSIX: `strace`, `lsof`, `procfs` (`/proc/$PID/*`), dan `valgrind` (opsional untuk profiling wrapper C).

---

## 3. Concept & Internal Architecture

Eksekusi Bash di tingkat sistem operasi bukanlah sekadar interpretasi baris teks secara linier, melainkan orkestrasi *system calls* kompleks yang berinteraksi langsung dengan kernel Linux.

```
+-------------------------------------------------------------------------------+
|                             Bash Execution Engine                             |
|                                                                               |
|  +-------------------+      +------------------+      +--------------------+  |
|  | Parser & Lexer    | ---> | AST Generation   | ---> | Word Expansion     |  |
|  +-------------------+      +------------------+      +--------------------+  |
+------------------------------------------------------------------|------------+
                                                                   v
                                                        +--------------------+
                                                        | Syscall Dispatcher |
                                                        +--------------------+
                                                                   |
            +------------------------------------------------------+------------------------------------------------------+
            |                                                      |                                                      |
            v                                                      v                                                      v
  [ Process Lifecycle ]                                     [ I/O Subsystem ]                                     [ IPC & Signals ]
  - fork(2) / clone(2)                                      - openat(2) / close(2)                                - sigaction(2) / kill(2)
  - execve(2)                                               - dup2(2) / fcntl(2)                                  - pipe2(2) / mkfifo(3)
  - wait4(2) / WIFEXITED                                    - Atomic file locks (flock)                           - Signal Masking (SIG_BLOCK)
```

### 3.1. Anatomi Fork-Exec dan Copy-On-Write (COW)

Ketika Bash mengeksekusi perintah eksternal atau membuat *subshell*:

1. **`fork(2)` / `clone(2)`**: Kernel menduplikasi proses *parent* (Bash). Page table diduplikasi, namun *physical memory frames* ditandai sebagai *read-only* (Copy-On-Write).
2. **State Cloning**: Subshell mewarisi seluruh environment variables, file descriptor yang terbuka (kecuali flag `FD_CLOEXEC` aktif), umask, dan batasan resource (`setrlimit`). Subshell **tidak** mengekspor kembali modifikasi memori ke *parent*.
3. **`execve(2)`**: Jika perintah adalah binary eksternal, *address space* proses anak ditimpa seluruhnya dengan program baru. Built-in command (`cd`, `read`, `echo`) dieksekusi langsung di dalam memory space interpreter tanpa memanggil `fork-exec`, sehingga jauh lebih efisien.

### 3.2. Manipulasi File Descriptor Table

Setiap proses Linux memiliki tabel File Descriptor di dalam struktur kernel `struct files_struct`. Secara default:
- `0`: Standard Input (`stdin`)
- `1`: Standard Output (`stdout`)
- `2`: Standard Error (`stderr`)

Bash memungkinkan manipulasi FD 3 hingga 9 (atau FD arbitrary $\ge 10$ menggunakan sintaks `{var}>&1`). Manipulasi ini memanfaatkan *system call* `dup2(oldfd, newfd)` dan `fcntl(F_SETFD)`.

Ketika redirection majemuk terjadi, misalnya `2>&1 >file.log`:
- Evaluasi dilakukan strictly dari **kiri ke kanan**.
- `2>&1`: FD 2 diarahkan ke target FD 1 saat ini (terminal console).
- `>file.log`: FD 1 diarahkan ke *file descriptor* hasil `openat()` ke `file.log`.
- Hasil: `stderr` tetap keluar ke console, `stdout` masuk ke file. (Bandingkan dengan `>file.log 2>&1`).

### 3.3. Process Substitution & Anonymous Pipes

Sintaks `<(command)` dan `>(command)` tidak menciptakan temporary file pada disk:
1. Kernel mengalokasikan anonymous pipe via `pipe2(2)` atau FIFO.
2. Pipe dihubungkan ke file descriptor baru di `/dev/fd/<n>`.
3. Bash meneruskan string jalur file `/dev/fd/<n>` sebagai argumen CLI ke program pemanggil.
4. Data dikirimkan secara streaming via buffer kernel (biasanya berukuran default 64 KB). Jika buffer penuh, proses penulis diblokir oleh kernel scheduler melalui status `TASK_INTERRUPTIBLE` hingga pembaca mengosongkan data.

---

## 4. Why & What

| Dimensi | Pendekatan Skrip Naif (Ad-hoc) | Pendekatan Arsitektur Produksi (Enterprise-grade) |
| :--- | :--- | :--- |
| **Error Handling** | Mengandalkan nilai default, mengabaikan status parsial pipeline. | `set -Eeuo pipefail`, explicit traps, signal cascading. |
| **Concurrency Control**| Menggunakan `ps | grep` atau file indikator flag (`touch running.flag`). Rentan *race condition*. | Mutex tingkat kernel via `flock(2)` yang terikat pada *lifecycle* FD. Otomatis *release* jika crash. |
| **Memory Isolation** | Modifikasi variabel di dalam perulangan pipa (`cat file \| while read...`) yang hilang di luar *loop*. | Menggunakan redirection input murni (`while read ...; done < file`) atau Process Substitution untuk mencegah *subshell fork*. |
| **Telemetry & Audit** | Logging teks polos tidak terstruktur tanpa timestamp ISO-8601, PID, dan tracing context. | Output terstruktur (JSON/NDJSON) ke FD kustom, terintegrasi tracing environment, aman terhadap *log injection*. |

### Mengapa Bash Masih Dominan di Sistem Produksi?
Meskipun bahasa tingkat tinggi (Go, Python, Rust) mendominasi microservices, Bash adalah *lingua franca* untuk:
- Entry point container (`ENTRYPOINT` / `init container` Kubernetes).
- Bootstrapping node, os-hardening, dan image building (Packer, cloud-init).
- Glue-code tingkat rendah yang berinteraksi dengan kernel sysctl, cgroups, dan block storage.

Menguasai Bash pada tingkat sistem berarti menjamin kestabilan infrastruktur pada lapisan paling mendasar sebelum runtime aplikasi Anda berjalan.

---

## 5. How (Workflow Detail)

Untuk membangun eksekusi skrip deterministik kelas industri, implementasikan workflow siklus hidup berikut:

```
+-----------------------------------------------------------------------------------+
| 1. INITIALIZATION: set -Eeuo pipefail; shopt -s inherit_errexit                   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. PROCESS MUTEX: Alokasi dedicated FD & peroleh kernel lock (flock -nx)          |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. SIGNAL TRAPPING: Binding trap cleanup handler ke SIGINT, SIGTERM, EXIT, ERR     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. TELEMETRY INIT: Duplikasi FD 3 (Log Bus) & inisialisasi audit stream           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 5. TASK DISPATCH: Eksekusi core workflow dengan worker pools, FIFOs & safe reads  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 6. DETERMINISTIC CLEANUP: Tutup FD, rilis lock, reap child processes, exit code   |
+-----------------------------------------------------------------------------------+
```

1. **Safety Flags Activation**: Aktifkan flag mitigasi kesalahan fatal interpretasi Bash.
2. **Atomic Single-Instance Enforcement**: Gunakan *kernel lock* terisolasi pada FD custom untuk mencegah overlapping runs.
3. **Trap Handler Configuration**: Pastikan interceptor sinyal terpasang sebelum resource dialokasikan.
4. **Structured I/O Redirection**: Pisahkan telemetry, human-readable stdout, dan diagnostic logging ke alur channel terpisah.
5. **Execution & Child Reaping**: Jalankan tugas paralel menggunakan token-bucket atau dynamic worker pooling; pastikan *child process* tidak menjadi *zombie*.
6. **Graceful Exit**: Jamin penghapusan IPC resources (named pipes, lock file descriptor closure) melalui handler `EXIT`.

---

## 6. Analogy & Diagram ASCII

Bayangkan Bash sebagai **Sistem Rel Kereta Barang Otomatis**:

- **Subshell `(...)`**: Pembuatan jalur rel cabang sementara. Apapun modifikasi jalur yang terjadi di cabang tersebut, tidak akan mengubah jalur utama saat cabang ditutup.
- **File Descriptors (FD)**: Jalur peron stasiun. 
  - Peron 0: Pintu masuk barang (stdin).
  - Peron 1: Pintu keluar barang resmi (stdout).
  - Peron 2: Pintu pembuangan barang rusak (stderr).
  - Peron 3-9: Pintu logistik kustom khusus enterprise.
- **Pipes `|`**: Konveyor belt berjalan antar stasiun. Jika stasiun penerima berhenti mengambil barang, konveyor otomatis berhenti (backpressure) karena sensor kapasitas penuh (buffer kernel 64KB).

```
                      PROSES UTAMA (Main Process)
                  +----------------------------------+
                  | Memory Variables ($WORKER_STATE) |
                  |                                  |
                  | FD 0: stdin                      |
                  | FD 1: stdout                     |
                  | FD 2: stderr                     |
                  | FD 3: JSON Audit Log             |
                  +-----------------+----------------+
                                    |
            +-----------------------+-----------------------+
            | fork()                                        | fork()
            v                                               v
    SUBSHELL TRAP (Subshell A)                      ANONYMOUS PIPE (|)
+-----------------------------------+        +-----------------------------+
| Memory snapshot (COW)             |        | Buffer Kernel (Max 64KB)    |
| Perubahan $WORKER_STATE HILANG    |        | Menahan Writer jika reader  |
| saat subshell terminate           |        | lambat (Backpressure)       |
+-----------------------------------+        +-----------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Demonstrasi Subshell Variable Loss vs. Process Redirection

```bash
#!/usr/bin/env bash
set -euo pipefail

counter=0

# ANTI-PATTERN: Pipeline menciptakan subshell pada sisi kanan (bash default)
echo -e "satu\ndua\ntiga" | while read -r line; do
    ((counter++)) || true
done
echo "Counter via Pipeline: ${counter}" # Output: 0 (State hilang karena fork subshell)

# PATTERN: Redirection murni / Process Substitution mempertahankan memory space parent
while read -r line; do
    ((counter++)) || true
done < <(echo -e "satu\ndua\ntiga")
echo "Counter via Process Substitution: ${counter}" # Output: 3 (State dipertahankan)
```

### 7.2. Practical Enterprise Example: Robust Mutex-Locked Transaction Processor

Skrip standar industri dengan logging terstruktur, atomisitas kernel, penanganan sinyal, dan alokasi File Descriptor dinamis.

```bash
#!/usr/bin/env bash
#
# Module: transaction_processor.sh
# Description: Production-grade transaction processor with non-blocking kernel lock,
#              dedicated telemetry FD, and deterministic signal handling.
# Strict POSIX compatibility flags
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Global Constants
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOCK_DIR="/var/lock/subsys"
readonly LOCK_FILE="${LOCK_DIR}/${SCRIPT_NAME}.lock"
readonly AUDIT_LOG="/var/log/${SCRIPT_NAME}.audit.json"

# Inisialisasi dedicated File Descriptor untuk Telemetry
exec {FD_AUDIT}>>"${AUDIT_LOG}"
exec {FD_LOCK}>"${LOCK_FILE}"

log_audit() {
    local -r severity="$1"
    local -r message="$2"
    local -r timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    
    # Menulis JSON atomic ke File Descriptor kustom (FD_AUDIT)
    printf '{"timestamp":"%s","severity":"%s","script":"%s","pid":%d,"message":"%s"}\n' \
        "${timestamp}" "${severity}" "${SCRIPT_NAME}" "$$" "${message}" >&"${FD_AUDIT}"
}

cleanup() {
    local -r exit_code=$?
    log_audit "INFO" "Executing cleanup sequence. Exit code: ${exit_code}"
    
    # Release kernel lock via flock(2) operation explicitly
    flock -u "${FD_LOCK}" 2>/dev/null || true
    
    # Close custom file descriptors
    exec {FD_LOCK}>&-
    exec {FD_AUDIT}>&-
    
    exit "${exit_code}"
}

handle_signal() {
    local -r sig="$1"
    log_audit "WARN" "Interception of OS signal: ${sig}. Terminating child processes."
    # Trap SIGTERM to process group
    trap - "${sig}"
    kill -- -$$ 2>/dev/null || true
    exit 128
}

# Trap configurations
trap cleanup EXIT
trap 'handle_signal SIGINT' SIGINT
trap 'handle_signal SIGTERM' SIGTERM

acquire_lock() {
    # Non-blocking exclusive lock (LOCK_EX | LOCK_NB)
    if ! flock -n "${FD_LOCK}"; then
        log_audit "ERROR" "Failed to acquire lock on ${LOCK_FILE}. Process collision detected."
        echo "CRITICAL: Instance of ${SCRIPT_NAME} is already running." >&2
        exit 1
    fi
    log_audit "INFO" "Successfully acquired exclusive kernel lock."
}

process_workloads() {
    local -a batch=("TX_1001" "TX_1002" "TX_1003")
    
    for tx in "${batch[@]}"; do
        log_audit "INFO" "Processing record: ${tx}"
        # Simulasi operasi I/O
        sleep 0.5
    done
}

main() {
    acquire_lock
    log_audit "INFO" "Starting main processing engine pipeline."
    process_workloads
    log_audit "INFO" "Pipeline executed successfully with zero faults."
}

main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: High-Throughput Log Ingestion Engine dengan Backpressure & Deadlock Mitigation

**Latar Belakang Masalah:**  
Sebuah platform e-commerce multi-region menghasilkan puluhan juta transaksi per jam. Log raw dari aplikasi web dituliskan ke temporary ingress volume. Script ingestion Bash konvensional mengalami masalah kritis:
1. `Out of Memory (OOM)` akibat subshell pipeline yang tidak terkontrol (`cat file | while read line; do curl ... & done`).
2. Proses tertahan (*hung*) tanpa status jelas akibat silent deadlocks pada pipe buffer yang penuh.
3. Kematian pod mendadak di Kubernetes mengakibatkan *orphan lockfiles* yang membuat pipeline macet selamanya.

**Solusi Arsitektural:**  
Membangun high-throughput ingestion processor berbasis Bash menggunakan pola:
- Token-bucket semaphore concurrency control murni melalui File Descriptor FIFO.
- Backpressure detection: membatasi proses anak maksimal $N$ *workers*.
- Signal-resilient lock orchestration terikat PID aktif.

```bash
#!/usr/bin/env bash
#
# Module: high_throughput_ingestor.sh
# Production Pipeline with Controlled Worker Pools and IPC Sync
set -Eeuo pipefail

readonly CONCURRENCY_LIMIT=4
readonly WORK_DIR="/tmp/pipeline_runtime_$$"
readonly FIFO_PATH="${WORK_DIR}/worker_tokens.fifo"

mkdir -m 0700 -p "${WORK_DIR}"

# 1. Cleanup Lifecycle Management
cleanup() {
    local -r exit_code=$?
    # Hindari rekursi
    trap - EXIT INT TERM
    
    # Bunuh seluruh Process Group
    kill -- -$$ 2>/dev/null || true
    
    # Bersihkan artifacts
    rm -rf "${WORK_DIR}"
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM

# 2. Concurrency Controller via FIFO Semaphore
mkfifo "${FIFO_PATH}"
# Hubungkan FIFO ke FD 7 untuk read-write (mencegah blocking open)
exec 7<>"${FIFO_PATH}"

# Inisialisasi token semaphore ke dalam buffer FIFO
for ((i = 0; i < CONCURRENCY_LIMIT; i++)); do
    echo "TOKEN" >&7
done

# 3. Payload Processor Function
worker_task() {
    local -r payload="$1"
    local -r worker_pid=$$
    
    # Simulasi beban komputasi/network request
    echo "[Worker ${worker_pid}] Processing payload: ${payload}"
    sleep "$((RANDOM % 2 + 1))"
    
    # Kembalikan token ke FD 7 saat selesai
    echo "TOKEN" >&7
}

# 4. Ingestion Stream Processor
main_stream() {
    local items=(
        "BATCH_A_CHUNKS_01" "BATCH_A_CHUNKS_02" "BATCH_A_CHUNKS_03"
        "BATCH_B_CHUNKS_01" "BATCH_B_CHUNKS_02" "BATCH_B_CHUNKS_03"
        "BATCH_C_CHUNKS_01" "BATCH_C_CHUNKS_02"
    )

    for item in "${items[@]}"; do
        # Konsumsi token (blokir eksekusi jika tidak ada token yang tersedia)
        read -r -u 7 _

        # Fork background worker
        (
            worker_task "${item}"
        ) &
    done

    # Barrier Synchronization: tunggu semua child processes dalam grup selesai
    wait
    echo "Seluruh batch pemrosesan berhasil dieksekusi secara asinkron."
}

main_stream
```

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Bash Subshells `( ... )`** | Isolasi modifikasi state environment lengkap. Aman dari *side-effects*. | Overheads `fork(2)` yang tinggi jika dipanggil secara intensif di loop besar. | Gunakan hanya untuk isolasi state lingkungan atau delegasi concurrency. |
| **Process Substitution `<(...)`** | Menghindari pembuatan temporary file fisik di disk, memory streaming murni. | Tidak portabel ke shell strictly POSIX (sh/dash). Membutuhkan `/dev/fd` kernel support. | Gunakan pada Bash modern (Linux/k8s environment). Hindari di embedded ash/dash. |
| **Anonymous Pipes `\|`** | Sederhana, mengimplementasikan *backpressure* kernel secara otomatis. | Memecah pipeline menjadi subshell terisolasi. Error parsing kompleks (`PIPESTATUS`). | Eksekusi stream data linear sederhana. Wajib aktivasi `set -o pipefail`. |
| **Named Pipes (FIFO)** | Memungkinkan IPC antar-proses acak tanpa hierarki *parent-child*. | Potensi deadlocks jika operasi *open-for-read* atau *open-for-write* tidak dilakukan secara seimbang. | Sinkronisasi concurrency worker pool (Semaphore token). |
| **Bash vs. Go/Python** | Zero external dependencies, footprint container minimalis (<15MB base OS). | Keterbatasan manipulasi struktur data biner kompleks; debugging thread asinkronus sulit. | Orchestration container init, sysadmin automation, and bare-metal bootstrapping. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Mengabaikan Flag PIPESTATUS

```bash
# SALAH: Hanya menangkap status exit dari perintah terakhir ('grep')
cat massive_archive.tar.gz | tar -xzf - | grep "CRITICAL_ERROR"
echo $? # Jika tar gagal corrupt, tapi grep exit 0 (karena string ada/tidak), kegagalan tar diabaikan!

# BENAR: Menggunakan pipefail dan array PIPESTATUS
set -o pipefail
tar -xzf massive_archive.tar.gz | grep "CRITICAL_ERROR" || {
    pipeline_status=("${PIPESTATUS[@]}")
    if [[ "${pipeline_status[0]}" -ne 0 ]]; then
        echo "Error: tar extraction failed with exit code: ${pipeline_status[0]}" >&2
    fi
    if [[ "${pipeline_status[1]}" -ne 0 ]]; then
        echo "Notice: grep found no patterns or hit error: ${pipeline_status[1]}" >&2
    fi
}
```

### 10.2. Kesalahan Fatal: Subshell Masking Variable di Read Loop

```bash
# SALAH
TOTAL_SIZE=0
find /data -name "*.bin" -printf "%s\n" | while read -r size; do
    TOTAL_SIZE=$((TOTAL_SIZE + size)) # Berjalan di child process!
done
echo "Total: ${TOTAL_SIZE}" # Output selalu 0!

# BENAR: Process substitution mengembalikan proses utama ke parent
TOTAL_SIZE=0
while read -r size; do
    TOTAL_SIZE=$((TOTAL_SIZE + size))
done < <(find /data -name "*.bin" -printf "%s\n")
echo "Total: ${TOTAL_SIZE}" # Output akurat
```

### 10.3. Panduan Diagnostik & Debugging Produksi

1. **Investigasi Stuck Process (Deadlock Analysis):**
   ```bash
   # Melacak proses yang menggantung pada syscall I/O
   strace -p <PID> -f -e trace=openat,read,write,pipe2,flock
   ```
2. **Inspeksi File Descriptors yang Terbuka:**
   ```bash
   ls -la /proc/<PID>/fd/
   lsof -p <PID>
   ```
3. **Mendeteksi Memory Leaks dan Mutex Contention:**
   Periksa status `/proc/<PID>/status` pada key `VmPeak`, `VmSize`, dan `/proc/locks` untuk melihat status antrean `flock(2)`.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis skrip Bash ke lingkungan produksi:

- [ ] **Strict Mode Initialization**: Script dimulai dengan deklarasi wajib:
  ```bash
  set -Eeuo pipefail
  ```
- [ ] **Signal Handlers Attached**: Trap untuk sinyal terminasi telah diisolasi:
  ```bash
  trap 'cleanup' EXIT
  trap 'handle_signal SIGTERM' SIGTERM
  trap 'handle_signal SIGINT' SIGINT
  ```
- [ ] **Locking Mechanism**: Skrip yang tidak boleh berjalan simultan wajib menggunakan locking berbasis file descriptor kernel (`flock`), bukan file teks ad-hoc.
- [ ] **Explicit Variable Scoping**: Hindari variabel global tidak terkendali; selalu gunakan `local` pada fungsi dan `readonly` untuk konstanta konfigurasional.
- [ ] **Explicit I/O Channeling**:
  - `stdout` (FD 1): Hanya untuk output data fungsional yang siap diparsing program lain.
  - `stderr` (FD 2): Khusus log pesan error, warning, dan status human-readable.
- [ ] **Sanitized Dynamic Variables**: Semua ekspansi variabel dibungkus tanda kutip ganda (contoh: `"${my_path}"`) untuk mencegah *word splitting* dan *globbing attack*.
- [ ] **Zero Orphaned Child Policy**: Subshell yang dipanggil di background wajib di-track PID-nya atau dimasukkan ke dalam Process Group yang di-reap serentak saat induk mati (`kill -- -$PID`).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori proyek: `hands-on/m02/`

### File Setup: `hands-on/m02/setup.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p hands-on/m02/data
echo "Preparing test data..."
for i in {1..100}; do
    echo "LOG_RECORD_${i}_PAYLOAD_OK" > "hands-on/m02/data/file_${i}.log"
done
echo "Setup complete."
```

### Script Implementasi: `hands-on/m02/worker_pipeline.sh`
```bash
#!/usr/bin/env bash
set -Eeuo pipefail

readonly DATA_DIR="hands-on/m02/data"
readonly METRICS_FILE="hands-on/m02/metrics.log"
exec {METRICS_FD}>>"${METRICS_FILE}"

cleanup() {
    exec {METRICS_FD}>&-
    echo "[Cleaned up FDs]"
}
trap cleanup EXIT

process_file() {
    local file_path="$1"
    local content
    content=$(<"${file_path}")
    
    # Simulasi mutasi state & output metrik
    printf '%s | Processed: %s | Size: %d\n' \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
        "${file_path}" \
        "${#content}" >&"${METRICS_FD}"
}

echo "Memproses data via non-subshell pipe..."
while IFS= read -r -d '' file; do
    process_file "${file}"
done < <(find "${DATA_DIR}" -type f -name "*.log" -print0)

echo "Pemrosesan selesai. Data metrik tersimpan di ${METRICS_FILE}."
```

### Instruksi Eksekusi
```bash
chmod +x hands-on/m02/setup.sh hands-on/m02/worker_pipeline.sh
./hands-on/m02/setup.sh
./hands-on/m02/worker_pipeline.sh
cat hands-on/m02/metrics.log | head -n 5
```

---

## 13. Exercise

### Level Easy
Modifikasi pipeline command berikut agar tidak mengabaikan error code proses hulu dan variabel tetap terikat di lingkungan *parent*:
```bash
# Code awal (buggy)
cat /etc/hosts | while read line; do HOST_COUNT=$((HOST_COUNT+1)); done; echo $HOST_COUNT
```
*Goal:* Gunakan sintaks redirection murni, aktifkan `pipefail`, dan inisialisasi default variable.

### Level Medium
Buat script Bash yang membuka File Descriptor kustom nomor 8 untuk membaca file konfigurasi `/etc/resolv.conf`, dan File Descriptor 9 untuk menulis report audit. 
- Iterasi baris per baris FD 8.
- Tuliskan hanya baris yang mengandung keyword `nameserver` ke FD 9 dengan prefix `[DNS_RESOLVER]`.
- Tutup kedua FD secara manual di akhir skrip.

### Level Hard
Buat custom Semaphore Concurrency Controller menggunakan Bash dan Named Pipe (FIFO):
- Batasi proses paralel hingga tepat 3 worker bersamaan.
- Proses kumpulan 10 antrean *dummy task* (masing-masing task sleep antara 1-3 detik).
- Jika ada worker yang crash (disimulasikan dengan sinyal `kill -9` acak), semaphore tidak boleh mengalami *deadlock* dan sisa antrean harus tetap diproses hingga selesai.

---

## 14. Challenge (Enterprise Reliability Scenario)

**Konteks Sistem:**  
Anda adalah Staff SRE di penyedia Financial-Technology global. Terdapat skrip Bash legasi yang berjalan setiap jam via crontab untuk melakukan rekonsiliasi data perbankan (`reconcile_wallets.sh`). 

**Masalah di Produksi:**
1. Jika eksekusi batch berjalan lebih dari 1 jam (karena network latency database), cron berikutnya jalan secara tumpang-tindih (*overlapping*), merusak integritas balance ledger dan memicu race condition.
2. Saat administrator mengirimkan perintah rolling reboot mesin (`SIGTERM`), script langsung mati seketika meninggalkan transaksi dalam kondisi setengah terupdate (*inconsistent state*).
3. Tim logging mengeluh bahwa stdout script mencampuradukkan payload response JSON dari API dan crash log internal secara berantakan, membingungkan parsing Elastic/Logstash.

**Misi Arsitektur:**  
Rancang ulang struktur skrip Bash `reconcile_wallets.sh` tersebut dengan kriteria produksi mutlak:
- **Zero Double-Execution**: Menggunakan Mutex via Linux Kernel (`flock`) non-blocking. Jika skrip mendeteksi proses lama masih berjalan, skrip baru harus mencatat audit `ALERT` ke stderr dan segera keluar dengan status 0 (tidak boleh gagal agar cron tidak memicu email alert palsu).
- **Graceful Shutdown Interceptor**: Menangkap `SIGTERM` dan `SIGINT`. Jika sinyal diterima saat pemrosesan batch sedang berlangsung, skrip harus menyelesaikan transaksi yang sedang diproses saat itu (in-flight transaction limit: max 10 detik timeout), membatalkan antrean berikutnya, merilis mutex, dan keluar dengan exit code 143.
- **Strict Isolated Dual-FD Logging**:
  - Saluran FD 3: Mengalirkan data operasional (JSON structured event).
  - Saluran FD 4: Mengalirkan data trace diagnostik mentah.
  - Console `stdout`/`stderr` hanya boleh menerima ringkasan eksekusi final.
- Tuliskan arsitektur skrip tersebut secara lengkap, deterministik, aman, dan berikan penjelasan pada setiap layer mitigasinya.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic

1. Mengapa ekspresi `echo "test" | read result; echo "$result"` mencetak string kosong pada layar?
   - A. Karena utility `read` tidak mendukung standard input dari operator pipe.
   - B. Karena pipe mengeksekusi sisi kanan (`read result`) di dalam lingkungan *subshell* terpisah (`fork(2)`), sehingga alokasi variabel lokal hilang saat proses anak terminasi.
   - C. Karena string "test" otomatis di-flush oleh kernel sebelum `read` sempat menangkap buffer.
   - D. Karena flag `-r` tidak dideklarasikan pada fungsi `read`.

2. Apa fungsi parameter flag `set -E` (atau `set -o errtrace`) pada shell Bash?
   - A. Memaksa Bash keluar seketika jika ada variabel yang belum didefinisikan.
   - B. Memastikan trap `ERR` diwariskan ke dalam subshell, fungsi, dan command substitutions.
   - C. Mengabaikan seluruh error syntax yang ditemukan pada script runtime.
   - D. Menyalakan echo command trace sebelum instruksi dieksekusi.

3. System call Linux manakah yang dipanggil secara internal oleh perintah `flock` di Bash untuk menjamin isolasi single-instance process?
   - A. `chmod(2)`
   - B. `mknod(2)`
   - C. `flock(2)` / `fcntl(2)`
   - D. `ptrace(2)`

4. Sintaks Bash manakah yang secara valid membuka file descriptor 3 dalam mode write-append pada file `/tmp/audit.log`?
   - A. `exec 3< /tmp/audit.log`
   - B. `exec 3>> /tmp/audit.log`
   - C. `open --fd 3 --append /tmp/audit.log`
   - D. `3>&1 >> /tmp/audit.log`

5. Manakah pernyataan yang benar terkait Process Substitution `<(command)`?
   - A. Perintah tersebut selalu membuat temporary file fisik di direktori `/tmp`.
   - B. Perintah tersebut mengeksekusi program di parent shell tanpa melakukan fork.
   - C. Perintah tersebut menghubungkan output program ke file descriptor `/dev/fd/<n>` menggunakan anonymous pipe kernel.
   - D. Perintah tersebut tidak dapat digunakan sebagai input untuk perulangan `while read`.

---

### 15.2. Pertanyaan Intermediate

6. Pada pipeline: `cmdA | cmdB | cmdC`, flag `set -o pipefail` diaktifkan. Jika `cmdA` exit dengan status 0, `cmdB` exit dengan status 137 (OOM killed), dan `cmdC` exit dengan status 0. Berapakah nilai `$?` setelah seluruh pipeline selesai?
   - A. 0
   - B. 1
   - C. 137
   - D. 255

7. Mengapa penguncian proses (*process locking*) menggunakan `mkdir /tmp/lock.dir` dianggap atomic oleh POSIX standard, sementara `[ -f /tmp/lock ] || touch /tmp/lock` tidak aman (*unsafe*)?
   - A. Karena `mkdir` berjalan di thread kernel yang berbeda dengan shell script.
   - B. Karena `mkdir` memanggil system call `mkdir(2)` yang dijamin atomic di level VFS/filesystem, sedangkan pola `[ -f ] || touch` memiliki celah waktu (*Time-of-Check to Time-of-Use / TOCTOU*) antar kedua syscall tersebut.
   - C. Karena perintah `touch` tidak mampu membuat file jika direktori memiliki izin *read-only*.
   - D. Karena `mkdir` otomatis mendeteksi PID dari proses yang sedang aktif.

8. Perhatikan potongan kode berikut:
   ```bash
   trap 'echo "Crash Detected!"' ERR
   value=$(ls /path/yang/pasti/tidak/ada)
   echo "Selesai"
   ```
   Jika `set -e` aktif, mengapa teks `"Crash Detected!"` TIDAK dipicu saat assignment variabel `value` gagal?
   - A. Karena `ls` bukan merupakan program bawaan (built-in) Bash.
   - B. Karena command substitution yang gagal pada baris assignment memerlukan deklarasi eksplisit `inherit_errexit` atau assignment terpisah dari keyword lokal.
   - C. Karena sinyal `ERR` hanya bisa diinterupsi oleh kernel level sinyal seperti `SIGSEGV`.
   - D. Karena error langsung di-redirect ke `stderr` terminal console.

9. Apa implikasi dari mengeksekusi `kill -TERM -$$` di dalam signal handler skrip Bash?
   - A. Hanya mematikan parent process dan membiarkan child process menjadi orphan (diadopsi init).
   - B. Mengirimkan sinyal `SIGTERM` ke seluruh proses di dalam Process Group ID (PGID) yang sama dengan skrip saat ini.
   - C. Mengirimkan sinyal reboot ke sistem operasi Linux.
   - D. Mengosongkan memory page subshell secara paksa.

10. Ketika membuat named pipe dengan `mkfifo /tmp/my_fifo`, apa yang terjadi secara default jika proses script mengeksekusi `echo "data" > /tmp/my_fifo` tanpa ada proses lain yang membuka file tersebut untuk membaca (*read*)?
    - A. Perintah echo langsung return 0 dan membuang datanya ke `/dev/null`.
    - B. Perintah echo mengalami error `Broken pipe` (SIGPIPE).
    - C. Kernel memblokir proses eksekusi `echo` (*blocking open/write*) sampai ada proses lain yang membuka FIFO tersebut untuk membaca.
    - D. File FIFO otomatis terhapus oleh sistem VFS.

---

### 15.3. Skenario Kasus Produksi

11. **Skenario:** Anda memiliki skrip daemon pengirim metrik yang berjalan terus-menerus. Pada skrip tersebut, Anda memasang trap sinyal `trap 'cleanup' EXIT`. Namun, ketika container platform (Docker/Kubernetes) mematikan Pod melalui perintah `docker stop` (yang mengirimkan `SIGTERM` lalu `SIGKILL` setelah grace period 30 detik habis), fungsi `cleanup` Anda tidak pernah tereksekusi sama sekali, mengakibatkan data korup. Mengapa ini terjadi dan bagaimana perbaikan arsitekturnya?
    - *Analisis Akar Masalah & Solusi:*
      - **Akar Masalah:** Secara default pada Bash, event pseudo-signal `EXIT` hanya dieksekusi secara otomatis saat skrip keluar secara normal, atau saat menerima sinyal yang diintersep eksplisit. Jika skrip menerima `SIGTERM`, dan `SIGTERM` **tidak** didaftarkan di `trap`, Bash langsung terminasi seketika tanpa memicu event `EXIT`.
      - **Solusi:** Daftarkan trap sinyal `SIGTERM` (dan `SIGINT`) secara eksplisit untuk memanggil fungsi cleanup atau exit: `trap 'cleanup' EXIT SIGTERM SIGINT`.

12. **Skenario:** Skrip backup database memproses pipeline besar:
    ```bash
    mysqldump -u root production_db | gzip > /mnt/nfs/prod.sql.gz
    ```
    Suatu hari, ruang disk penyimpanan NFS habis di tengah jalan. Proses `gzip` gagal dan exit code bernilai 1. Namun, orchestrator Jenkins menyatakan langkah backup tersebut "SUCCESS" (Exit Code 0), sehingga data cadangan yang korup tidak terdeteksi selama berminggu-minggu. Bagian apa yang hilang dari konfigurasi skrip Bash Anda?
    - *Analisis Akar Masalah & Solusi:*
      - **Akar Masalah:** Bash secara default mengembalikan nilai `$?` dari proses **paling kanan (terakhir)** dalam pipeline jika `pipefail` tidak aktif. Jika `mysqldump` sukses (0) dan `gzip` gagal (1), exit status pipeline adalah 1. Namun jika skrip tersebut dibungkus subshell tanpa `set -o pipefail`, atau jika parsing pipa dilakukan tanpa pengecekan array `PIPESTATUS`, kegagalan sistem penyimpanan sering terabaikan.
      - **Solusi:** Wajib menyertakan `set -eo pipefail` pada awal skrip, sehingga jika salah satu komponen di pipeline gagal (seperti `gzip` yang kehabisan disk space), seluruh rantai langsung menghentikan skrip dan mengembalikan status non-zero ke orchestrator.

13. **Skenario:** Skrip worker memproses jutaan baris data log menggunakan konstruksi perulangan:
    ```bash
    exec 3< /var/log/huge_traffic.log
    while read -u 3 -r line; do
        process_line "$line" &
    done
    ```
    Setelah berjalan 2 menit, server mengalami *kernel panic* / *fork: Cannot allocate memory*, dan sistem monitoring crash. Apa kesalahan fatal arsitektur konkurensi skrip ini?
    - *Analisis Akar Masalah & Solusi:*
      - **Akar Masalah:** Perulangan di atas melakukan `fork(2)` proses anak ke background (`&`) pada **setiap baris log** tanpa ada batasan konkurensi (semaphore/worker pool). Jutaan proses tercipta secara simultan, menghabiskan alokasi Process Table kernel (`pid_max`) dan memicu kehabisan Virtual Memory (OOM).
      - **Solusi:** Implementasikan token-bucket concurrency limit (misalnya menggunakan Named Pipe FIFO atau `xargs -P <N>` / `parallel`) untuk membatasi jumlah background worker yang aktif secara paralel, dan gunakan perintah `wait -n` untuk menunggu slot worker kosong sebelum mem-fork proses berikutnya.

---

### Kunci Jawaban Quiz

| No | Jawaban | Penjelasan Teknis Singkat |
| :--- | :--- | :--- |
| 1 | **B** | Sisi kanan pipe pada Bash standar dieksekusi di dalam subshell. Seluruh mutasi state memori di subshell tidak dikembalikan ke parent shell. |
| 2 | **B** | Flag `-E` memastikan trap signal `ERR` tetap diwariskan ke context fungsi internal dan shell executions anak. |
| 3 | **C** | Utilitas `flock` pada Linux mengekspos system call `flock(2)` / `fcntl(2)` secara langsung melalui File Descriptor target. |
| 4 | **B** | Sintaks `exec 3>> file` membuka FD 3 dalam mode penulisan append (`O_APPEND \| O_WRONLY`). |
| 5 | **C** | Process Substitution dialokasikan kernel sebagai anonymous pipe streaming via descriptor `/dev/fd/<n>`. |
| 6 | **C** | Dengan `pipefail`, exit status pipeline diambil dari proses paling kanan yang bernilai non-zero (dalam hal ini `cmdB` dengan status 137). |
| 7 | **B** | `mkdir(2)` adalah *single atomic system call* di level filesystem kernel Linux, mencegah kerentanan TOCTOU *race conditions*. |
| 8 | **B** | Command substitution di dalam deklarasi assignment variabel tidak memicu sinyal `ERR` tanpa konfigurasi shell option `inherit_errexit`. |
| 9 | **B** | Tanda minus di depan PID (`-$$`) menginstruksikan kernel untuk mengirim sinyal ke seluruh proses dalam Process Group ID (PGID) tersebut. |
| 10 | **C** | Named pipe (FIFO) bersifat blocking di level kernel sampai kedua belah pihak (reader dan writer) terhubung ke buffer yang sama. |

---

## 16. Summary

Implementasi Bash tingkat enterprise menuntut pergeseran paradigma: dari sekadar merangkai perintah shell sederhana menjadi disiplin rekayasa sistem yang deterministik.

1. **Kernel Lifecycle Alignment**: Memahami operasi `fork-exec`, alokasi Virtual Memory (Copy-On-Write), dan Process Group ID adalah landasan untuk membangun sistem yang aman dari memory leak dan zombie process.
2. **Deterministic I/O Streams**: Memanfaatkan File Descriptor kustom (3-9+) dan Process Substitution memungkinkan manipulasi data stream berperforma tinggi tanpa menghasilkan artifact file temporary disk yang tidak perlu.
3. **Resilient Concurrency & Mutex**: Menghindari pendekatan penguncian ad-hoc. Manfaatkan penguncian kernel via `flock(2)` dan pola semaphore token-bucket menggunakan Named Pipe (FIFO) untuk melindungi sistem dari *race conditions* dan *deadlocks*.
4. **Fail-Safe Operation**: Menegakkan *Strict Mode* (`set -Eeuo pipefail`) dan signal handling yang rapi pada setiap level proses menjamin sistem beroperasi secara deterministik dan siap diintegrasikan pada arsitektur cloud-native modern.