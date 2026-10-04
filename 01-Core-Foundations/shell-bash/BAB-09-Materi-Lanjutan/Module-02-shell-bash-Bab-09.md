# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis** arsitektur internal runtime Bash, termasuk interaksi Virtual File System (VFS), File Descriptor (FD) table, dan siklus hidup proses subshell/fork-exec.
*   **Merancang dan Mengimplementasikan** mekanisme *concurrency control*, *inter-process communication* (IPC), dan *synchronization primitives* menggunakan Bash murni (FIFO/Named Pipes, `coproc`, dan kernel-level locking via `flock`).
*   **Membangun** sistem penanganan sinyal (*signal trapping & propagation*) yang tangguh untuk menjamin *graceful shutdown* dan pembersihan state pada orkestrasi container/bare-metal.
*   **Mengembangkan** arsitektur automasi berskala enterprise yang mengintegrasikan *structured logging* (JSON), *distributed-ready idempotency*, serta observabilitas runtime tanpa dependensi eksternal yang masif.

---

## 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
*   Sintaks lanjutan Bash: Ekspansi parameter (`${var:-}`, `${var//}`), array asosiatif, dan regex matching (`=~`).
*   Konsep sistem operasi POSIX: Process Tree, Process Group ID (PGID), Signals (`SIGTERM`, `SIGINT`, `SIGHUP`, `SIGCHLD`), dan Virtual Memory (Copy-On-Write).
*   Dasar I/O Redirection: Pemahaman standar stream (`stdin[0]`, `stdout[1]`, `stderr[2]`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 VFS, File Descriptors, dan Tabel Berkas Terbuka
Pada sistem operasi berbasis Linux/POSIX, setiap proses Bash yang berjalan memiliki representasi internal di kernel-space. Kernel mengelola berkas melalui tiga struktur data utama:
1.  **File Descriptor Table (Per-Process):** Berisi array pointer indeks integer (FD 0..N) yang menunjuk ke Open File Table.
2.  **Open File Table (System-Wide):** Menyimpan status flag berkas (read, write, append, non-blocking), current file offset, dan pointer ke V-node/In-node table.
3.  **Inode Table (System-Wide):** Menyimpan metadata fisik berkas, hak akses, dan blok data disk.

```
Process: bash (PID 1042)
+-----------------------+
|  FD Table (Per-Proc)  |
|  0: stdin  --------+  |
|  1: stdout -------+|  |
|  2: stderr ------+||  |
|  3: custom FD --+|||  |
+-----------------||||--+
                  ||||
                  vvvv
+-----------------------------------------------------+
|         Open File Table (Kernel System-Wide)         |
|  - File Status Flags (O_RDWR, O_CREAT, O_NONBLOCK)  |
|  - Offset Position                                  |
|  - Reference Count                                  |
+-----------------------------------------------------+
                          |
                          v
+-----------------------------------------------------+
|          Inode Table / VFS Node Layer                |
|  - Physical disk blocks / Pipe buffers / Sockets    |
+-----------------------------------------------------+
```

Ketika Bash membuka stream baru menggunakan `exec 3<> /path/to/fifo`, Bash meminta system call `open(2)` ke kernel. Kernel mengalokasikan entry terkecil yang tersedia pada FD Table proses Bash tersebut.

### 3.2 Subshell vs Execution Context (`()` vs `{}`)
Eksekusi blok kode memiliki perbedaan arsitektural yang fundamental:
*   **Brace Grouping `{ list; }`:** Dieksekusi di dalam *execution context* shell yang sama. Tidak ada system call `fork(2)` yang dipicu. Mutasi variabel lingkungan dan modifikasi state FD bertahan setelah blok selesai.
*   **Subshell `( list )`:** Memicu system call `fork(2)`. Kernel menduplikasi page table proses Bash menggunakan *Copy-On-Write* (COW). Subshell mewarisi FD dan variabel yang ada, namun setiap mutasi memori (variabel, direktori kerja/`cd`, trap) sepenuhnya terisolasi dan langsung dihancurkan saat subshell melakukan `exit(2)`.

### 3.3 Pipe Internals dan `PIPE_BUF` Atomicity
Pipeline (`cmd1 | cmd2`) menghubungkan stdout `cmd1` ke stdin `cmd2` via anonymous pipe kernel buffer (default: 64KB pada Linux modern). 
*   Penulisan ke pipe dengan ukuran di bawah konstanta `PIPE_BUF` (4096 bytes pada Linux) dijamin **atomic**. Jika beberapa proses menulis data secara bersamaan ke pipe yang sama, data tidak akan terfragmentasi (*interleaved*) selama ukuran payload $\le 4096$ bytes.
*   Jika kapasitas buffer kernel penuh, proses penulis (`write(2)`) akan diblokir (*blocking I/O*) hingga proses pembaca (`read(2)`) mengonsumsi data, mencegah *memory exhaustion*.

### 3.4 Signal Handling Lifecycle & Reentrancy
Ketika sinyal OS (misal: `SIGTERM`) dikirimkan ke Bash:
1.  Kernel menginterupsi eksekusi Bash dan menandai bit sinyal pada *pending signal mask*.
2.  Bash tidak langsung mengeksekusi trap handler di sembarang instruksi. Bash menunda eksekusi trap handler hingga perintah foreground yang sedang berjalan selesai, kecuali perintah tersebut adalah built-in atau Bash sedang berada dalam status `wait`.
3.  Trap handler Bash dijalankan di context utama, mengeksekusi rutinitas sanitasi sebelum mengembalikan kontrol atau keluar via exit code $128 + N$.

---

## 4. Why & What

### Mengapa Bash Lanjutan Relevan di Era Cloud-Native?
Meskipun bahasa pemrograman tingkat tinggi (Go, Rust, Python) mendominasi pengembangan aplikasi modern, Bash tetap menjadi fondasi kritis pada:
*   **Kubernetes Init-Containers & Entrypoint Daemons:** Orkestrasi inisialisasi pod, secret hydration, dan lifecycle pre-stop hooks.
*   **High-Performance CI/CD Engine:** Task runner yang mengeksekusi step build tanpa runtime overhead virtual environment.
*   **System Recovery Tools:** Lingkungan darurat (*minimal shell*) di mana runtime Go/Python tidak tersedia atau rusak.

### Apa yang Membedakan Skrip Enterprise dengan Skrip Amatir?
Skrip Bash enterprise menerapkan standar:
1.  **Deterministik:** Memanfaatkan `set -Eeuo pipefail`.
2.  **Atomic & Concurrency-Safe:** Mencegah *race condition* antar worker menggunakan POSIX file locks (`flock`).
3.  **Graceful & Self-Cleaning:** Menjamin pembersihan resource sementara menggunakan dynamic trap registration.
4.  **Auditable:** Format output terstruktur (JSON lines) yang kompatibel dengan log shipper (Fluentbit, Vector, Datadog).

---

## 5. How (Workflow Detail)

Alur kerja arsitektur eksekusi skrip produksi yang andal dirancang mengikuti pipeline siklus hidup berikut:

```
[ Inisialisasi Environment ]
           │
           ▼
[ Trap Registration: EXIT, ERR, SIGTERM, SIGINT ]
           │
           ▼
[ Acquire Kernel-Level Exclusive Lock via flock (FD 200) ]
           │
           ├─► (Gagal: Exit 1, Instance lain sedang berjalan)
           │
           ▼ (Sukses)
[ Alokasi Dedicated FIFO / Worker Pool FDs ]
           │
           ▼
[ Main Workload Engine (Parallel Jobs / Stream Processing) ]
           │
           ▼
[ Trap Triggered (Normal EXIT atau Unexpected ERR) ]
           │
           ▼
[ Cleanup: Remove Lock, Release FDs, Flush Buffers ]
           │
           ▼
[ Process Exit (Standardized POSIX Return Code) ]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem File Descriptor Bash seperti **Papan Sakelar Telepon Manual (Switchboard)**:
*   Kabel default: Slot 0 (Mikrofon masuk), Slot 1 (Speaker keluar), Slot 2 (Alarm error).
*   Enterprise Bash memungkinkan Anda menancapkan sakelar baru: Slot 3 (Jalur khusus ke database audit), Slot 4 (Pipa transmisi khusus ke departemen analitik).
*   Jika terjadi kebakaran (*Signal SIGTERM*), operator tidak langsung melarikan diri, melainkan menjalankan protokol evakuasi terstruktur (*Trap handler*), memutus semua sambungan dengan aman (*FD close*), baru kemudian mengosongkan gedung.

```
       BASH PROCESS RUNTIME SWITCHBOARD
      +--------------------------------+
0 <---| [IN]  Standard Input (Keyboard)|
1 --->| [OUT] Standard Output (Monitor)|
2 --->| [ERR] Standard Error (Log File)|
      |                                |
3 ===>| [FD3] Duplicated Output Log    |---> /var/log/audit.log
4 <==>| [FD4] Bidirectional Named Pipe |---> /tmp/worker.fifo
      +--------------------------------+
                      |
           Kernel Lock Control
                      |
200 ->| [LOCK] Mutex Lock File         |---> /var/lock/app.lock
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mutex Lock Menggunakan `flock` dan Dedicated FD
Contoh implementasi lock level-kernel untuk mencegah eksekusi ganda (*overlapping execution*).

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

LOCK_FILE="/tmp/batch_job.lock"
# Buka File Descriptor 200 untuk menunjuk ke lock file
exec 200>"${LOCK_FILE}"

# Ambil exclusive non-blocking lock (-n)
if ! flock -n 200; then
    echo "[CRITICAL] Instance lain sedang berjalan. Abort mission." >&2
    exit 1
fi

echo "[INFO] Lock berhasil didapatkan. Menjalankan critical section..."
sleep 5
echo "[INFO] Critical section selesai."

# Lock otomatis dilepas saat FD ditutup atau proses exit
exec 200>&-
```

### 7.2 Practical Example: Enterprise Structured Worker Pool dengan Graceful Shutdown
Implementasi job-queue concurrency control murni menggunakan Named Pipe (FIFO) sebagai token bucket rate-limiter, lengkap dengan telemetry JSON dan trap handling.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name : parallel_engine.sh
# Description : Enterprise-grade parallel processing engine with token bucket IPC
# Standard    : POSIX compliant with Bash 4.4+
# ==============================================================================
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Global Configuration
readonly MAX_CONCURRENCY=4
readonly WORK_DIR="/tmp/engine_${$}"
readonly FIFO_PATH="${WORK_DIR}/token_pipe"
readonly LOG_FILE="/tmp/engine_telemetry.log"
declare -a CHILD_PIDS=()

# Structured JSON Logger
log_event() {
    local level="${1}"
    local message="${2}"
    local trace="${3:-null}"
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    printf '{"timestamp":"%s","level":"%s","pid":%d,"message":"%s","trace":%s}\n' \
        "${timestamp}" "${level}" "$$" "${message}" "${trace}" | tee -a "${LOG_FILE}" >&2
}

# Cleanup Routine
cleanup() {
    local exit_code=$?
    log_event "INFO" "Initiating cleanup sequence..." "{\"exit_code\":${exit_code}}"

    # Terminate child processes if any
    for pid in "${CHILD_PIDS[@]:-}"; do
        if kill -0 "${pid}" 2>/dev/null; then
            log_event "WARN" "Terminating stray child process" "{\"target_pid\":${pid}}"
            kill -SIGTERM "${pid}" 2>/dev/null || true
        fi
    done

    # Close custom file descriptors
    exec 3>&- 2>/dev/null || true
    exec 3<&- 2>/dev/null || true

    # Remove temporary IPC artifacts
    if [[ -d "${WORK_DIR}" ]]; then
        rm -rf "${WORK_DIR}"
    fi

    log_event "INFO" "Engine shutdown successfully completed" "{\"final_status\":${exit_code}}"
    exit "${exit_code}"
}

# Trap Signals for Atomic Recovery
trap cleanup EXIT
trap 'log_event "CRITICAL" "Received SIGTERM/SIGINT. Interrupting..."; exit 143' SIGTERM SIGINT
trap 'log_event "ERROR" "Unhandled error detected in command" "{\"line\":${LINENO},\"command\":\"${BASH_COMMAND}\"}"; exit 1' ERR

# IPC Initialization (Token Bucket)
mkdir -p -m 0700 "${WORK_DIR}"
mkfifo "${FIFO_PATH}"

# Open FD 3 for bidirectional read-write on FIFO to prevent EOF
exec 3<>"${FIFO_PATH}"

# Preload tokens into the FIFO buffer
for ((i = 0; i < MAX_CONCURRENCY; i++)); do
    echo "TOKEN_${i}" >&3
done

# Simulated Worker Payload
execute_payload() {
    local task_id="${1}"
    local token="${2}"
    
    # Internal execution logic
    local duration=$(( (RANDOM % 3) + 1 ))
    sleep "${duration}"
    
    log_event "INFO" "Task completed successfully" "{\"task_id\":${task_id},\"worker_slot\":\"${token}\",\"duration\":${duration}}"
}

# Main Orchestration Loop
main() {
    log_event "INFO" "Bootstrapping parallel engine" "{\"concurrency\":${MAX_CONCURRENCY}}"

    local TOTAL_TASKS=10
    for ((task = 1; task <= TOTAL_TASKS; task++)); do
        # Non-blocking read from token pipe (blocking until token available)
        read -r -u 3 token

        (
            # Subshell Worker
            trap 'exit 2' ERR
            execute_payload "${task}" "${token}"
            # Return token back to pool upon completion
            echo "${token}" >&3
        ) &
        
        CHILD_PIDS+=($!)
    done

    # Synchronize all running children
    log_event "INFO" "All tasks dispatched, waiting for pipeline completion..." "null"
    wait
    log_event "INFO" "All workloads processed successfully." "null"
}

main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Skenario
Sebuah institusi fintech multinasional menjalankan deployment aplikasi perbankan mikro (*core transaction processing*) langsung ke 500+ node server bare-metal. Deployment dilakukan menggunakan skrip shell via SSH runner tanpa ketersediaan container engine (kondisi isolated PCI-DSS compliant enclave).

### 8.2 Masalah
Deployment sering mengalami *split-brain execution* dan proses *zombie*:
1.  Skrip deployment baru dieksekusi sebelum deployment lama selesai, merusak state database migration.
2.  Saat runner CI/CD membatalkan build (`SIGTERM`), skrip utama mati, namun sub-proses child (download binary & apply database migration) tetap berjalan di background sebagai proses yatim (*orphan*) di bawah PID 1 (`systemd`).
3.  Error log berserak dalam format unparsed text, menyulitkan parsing Splunk.

### 8.3 Solusi Arsitektur
Dibuat skrip arsitektur tunggal yang mengimplementasikan:
1.  **Distributed Lock Simulator via `flock`:** Mengunci file mutex pada mount disk terpusat berbasis NFS/EFS.
2.  **Process Group Isolation:** Menggunakan `set -m` dan penembakan sinyal ke Process Group (`kill -- -$$`) pada trap exit untuk membunuh seluruh turunan pohon proses secara deterministik.
3.  **JSON Standard Telemetry:** Output terpusat ke `stdout` yang diarahkan langsung ke systemd-journald dengan metadata structured context.

```bash
# Snapshot Implementasi Solusi: Signal Forwarding ke Seluruh Process Group
kill_process_group() {
    local sig="${1:-SIGTERM}"
    trap '' "${sig}" # Abaikan sinyal pada diri sendiri saat proses broadcast
    log_event "WARN" "Broadcasting ${sig} to process group" "{\"pgid\":$$}"
    kill -"${sig}" -- -$$ 2>/dev/null || true
}
trap 'kill_process_group SIGTERM; exit 143' SIGTERM
```

---

## 9. Trade-offs

| Parameter | Pure Bash (Advanced) | Python 3 Engine | Compiled Binary (Go/Rust) |
| :--- | :--- | :--- | :--- |
| **Startup Latency** | **Ultralow (< 2ms)** | Medium (~30-50ms) | **Ultralow (< 5ms)** |
| **Memory Footprint** | **Sangat Rendah (~2-4MB)** | Tinggi (~20-40MB) | Rendah (~10-15MB) |
| **Portability** | **Native pada seluruh OS Unix** | Tergantung runtime & deps | Multiplatform binary tunggal |
| **Concurrency Model**| Fork-based IPC / FIFOs | OS Threads / AsyncIO | Go Routines / Native Threading|
| **Data Structure Complexity**| Rendah (String, Array, Key-Val) | Tinggi (Objects, Trees, Graphs)| Ekstrem (Type-Safe Complex Data)|
| **Debugging Maintenance** | Sulit jika LOC > 1000 lines | Sangat Baik (Stack trace) | Sangat Baik (Compiler-guaranteed)|

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Failure Pipeline (`PIPEFAIL` Omission)
*   **Kesalahan:** Menggunakan pipa sederhana tanpa `pipefail`.
    ```bash
    cat missing_file.txt | grep "error" # Selalu menghasilkan exit code 0!
    ```
*   **Penyebab:** Shell secara default hanya mengevaluasi exit status dari perintah *terakhir* pada rantai pipa.
*   **Solusi:**
    ```bash
    set -o pipefail
    ```

### 10.2 Variable Scope Poisoning dalam Loop via Pipeline
*   **Kesalahan:** Mengubah state variabel di dalam pipeline loop.
    ```bash
    count=0
    cat list.txt | while read -r line; do
        ((count++))
    done
    echo "Total: ${count}" # Total tetap bernilai 0!
    ```
*   **Penyebab:** Karakter `|` memaksa sisi kanan loop berjalan di dalam **subshell terpisah**. Perubahan pada `count` hilang saat subshell selesai.
*   **Solusi:** Gunakan *Process Substitution* atau *Here-String*:
    ```bash
    count=0
    while read -r line; do
        ((count++))
    done < <(cat list.txt)
    echo "Total: ${count}" # Total terupdate secara presisi
    ```

### 10.3 Deadlock pada Process Substitution
*   **Gejala:** Skrip menggantung secara permanen (*hung process*) saat membaca multiple streams.
*   **Penyebab:** Membuka process substitution `<(command)` di mana output buffer melebihi kapasitas kernel buffer sementara pembaca belum mulai mengonsumsinya.
*   **Troubleshooting:** Periksa state FD proses menggunakan utilitas Linux:
    ```bash
    ls -la /proc/$$/fd
    lsof -p $$
    ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Strict Execution Flags:** Deklarasikan `set -Eeuo pipefail` di baris pertama di bawah shebang.
- [ ] **Dynamic Array Cleanliness:** Gunakan `local -a` atau `local -A` untuk mencegah variable leakage dari fungsi ke global space.
- [ ] **Namerefs over `eval`:** Hindari eksekusi runtime parsing via `eval` yang rawan script injection. Gunakan indirect reference `declare -n target_ref="${1}"`.
- [ ] **Defensive Path Resolution:** Jangan percaya pada relative path. Resolusikan direktori absolut skrip:
  ```bash
  readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  ```
- [ ] **Atomic File Updates:** Jangan me-redirect langsung ke file konfigurasi operasional (`> /etc/app.conf`). Tulis ke temporary file di partisi yang sama lalu gunakan `mv` (atomic operation pada POSIX filesystem).
- [ ] **Dedicated Lock Protection:** Terapkan `flock` pada proses batch yang berpotensi bentrok atau berjalan di cron.
- [ ] **Trap Error Tracing:** Simpan stack frame execution saat terjadi `ERR`:
  ```bash
  trap 'echo "Crash at ${BASH_SOURCE[0]}:${LINENO} on command: ${BASH_COMMAND}" >&2' ERR
  ```

---

## 12. Hands-on Practice

Buat dan eksekusi skrip berikut pada direktori kerja: `hands-on/m02/`

### Langkah 1: Siapkan Struktur Workspace
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat Skrip IPC Multiplexer
Buat file `fd_multiplexer.sh`:
```bash
#!/usr/bin/env bash
set -Eeuo pipefail

LOG_FD_STREAM="execution_trace.log"
exec 3> "${LOG_FD_STREAM}"

log_custom() {
    local msg="${1}"
    # Tulis bersamaan ke FD 1 (stdout) dan FD 3 (file descriptor kustom)
    echo "[DEBUG $(date +%T)] ${msg}" | tee /dev/fd/3
}

log_custom "Menginisialisasi stream custom FD..."
log_custom "Memverifikasi integritas alokasi VFS kernel..."

# Tutup FD 3
exec 3>&-

echo "Isi Berkas Output Hasil Tangkapan FD 3:"
cat "${LOG_FD_STREAM}"
```

### Langkah 3: Eksekusi dan Verifikasi
```bash
chmod +x fd_multiplexer.sh
./fd_multiplexer.sh
```

---

## 13. Exercise

### 13.1 Level Easy
Modifikasi skrip satu-baris (*one-liner*) ini agar aman dari status kegagalan dan tidak membocorkan stdout ke layar, tetapi hanya menyimpan data error ke log:
```bash
# Target perbaikan:
ls /root /tmp > output.log 2>&1
```
*Syarat:* FD stdout harus tetap dialihkan ke file, tetapi pesan error harus dialihkan secara eksklusif ke file log terpisah tanpa menggunakan subshell.

### 13.2 Level Medium
Buat skrip `atomic_counter.sh` yang menjalankan 10 subshell asynchronous secara simultan. Setiap subshell bertugas menambahkan angka 1 ke dalam file teks `counter.txt` sebanyak 50 kali. Skrip harus menggunakan `flock` untuk menjamin tidak ada operasi *race condition* (Hasil akhir harus tepat 500).

### 13.3 Level Hard
Implementasikan sebuah custom bidirectional message loop antara proses induk (Parent Process) dan anak (Child Process) menggunakan dua Named Pipe (`parent_to_child.fifo` dan `child_to_parent.fifo`).
*   Parent mengirim string `"PING <nomor>"`.
*   Child merespons dengan `"PONG <nomor>"`.
*   Harus ada mekanisme timeout: Jika child tidak merespons dalam 3 detik, parent melakukan kill pada child dan melakukan self-termination dengan exit code 124.

---

## 14. Challenge

### Arsitektur Micro-Agent Telemetri Non-Blocking
**Latar Belakang:** Anda sedang merancang agen observabilitas minimalis yang berjalan di ribuan server edge dengan sumber daya memori sangat ketat (<128MB RAM total). Penggunaan Golang/Python dilarang.

**Persyaratan Tantangan:**
1.  Buat program daemon Bash tunggal bernama `edge_watchdog.sh`.
2.  Daemon harus memonitor metric utilisasi memori dan disk setiap 5 detik.
3.  Implementasikan Bash `coproc` untuk memproses agregasi data di latar belakang tanpa memblokir thread loop utama penjemput data.
4.  Jika pemakaian memori melampaui threshold 90%, watchdog harus menembakkan sinyal `SIGUSR1` ke service target (dapat disimulasikan dengan sleep process) dan mencatat histori insiden dalam bentuk payload JSON array ke file `/tmp/incident_dump.json`.
5.  **Zero Resource Leaks:** Skrip harus mampu bertahan dari uji coba stress kill (`kill -SIGINT`, `kill -SIGTERM`, `kill -SIGHUP`) dan memastikan seluruh named pipes, temporary sockets, dan child processes benar-benar bersih dari tabel proses kernel dalam waktu $\le 500$ milidetik.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. **System call apa yang dipicu di kernel Linux saat Bash mengeksekusi sintaks kurung biasa `( umask 077; touch file )`?**
   * A. `clone(2)` atau `fork(2)`
   * B. `execve(2)`
   * C. `pthread_create(3)`
   * D. Tidak ada system call, hanya memory pointer context switch.

2. **Apa fungsi dari perintah `exec 5>&-` dalam Bash?**
   * A. Mengalihkan FD 5 ke standard input.
   * B. Menghubungkan FD 5 dengan FD standard error.
   * C. Menutup File Descriptor 5 secara permanen untuk shell session saat ini.
   * D. Menulis karakter `-` ke stream 5.

3. **Berapa batas kapasitas penulisan atomik (`PIPE_BUF`) yang dijamin oleh kernel Linux pada sebuah pipe/FIFO?**
   * A. 512 Bytes
   * B. 1024 Bytes
   * C. 4096 Bytes
   * D. 65536 Bytes

4. **Kapan sebuah trap handler yang didaftarkan dengan `trap 'handler' ERR` akan dieksekusi?**
   * A. Setiap kali program menghasilkan keluaran ke `stderr`.
   * B. Setiap kali sebuah command menghasilkan return code selain 0, tunduk pada aturan evaluasi `set -e`.
   * C. Hanya saat script menerima sinyal `SIGSEGV`.
   * D. Saat kernel mendeteksi syntax error pada script.

5. **Apa efek dari baris instruksi `shopt -s inherit_errexit`?**
   * A. Mengabaikan seluruh error yang terjadi pada subshell.
   * B. Memaksa command substitution dan subshell mewarisi setting status flag `-e` (`errexit`) dari shell induk.
   * C. Menghentikan program seketika jika ada variabel uninitialized yang dipanggil.
   * D. Meneruskan error code ke proses init systemd.

---

### Bagian 2: Intermediate (Analisis Singkat)
1. Jelaskan mengapa konstruksi `flock -x /var/lock/app.lock -c "command"` lebih aman dibandingkan dengan teknik locking manual berbasis pembuatan file `if [ ! -f /var/lock/file ]; then touch /var/lock/file; fi`!
2. Mengapa membuka named pipe (FIFO) untuk mode baca saja (`exec 3< my.fifo`) dapat membekukan script eksekusi jika tidak ada proses lain yang membuka pipe tersebut untuk mode tulis?
3. Sebutkan perbedaan perilaku antara `kill $PID` dengan `kill -- -$PGID` dalam konteks penanganan sinyal graceful shutdown pada deployment script!
4. Jelaskan bahaya keamanan dari implementasi baris berikut: `eval $(cat user_input.txt)` dan berikan alternatif modern POSIX/Bash untuk assignment dinamis!
5. Apa peran file descriptor `/dev/null` ketika digunakan pada sintaks penutupan stream: `exec 1>&- 2>&-` versus pengalihan stream: `exec >/dev/null 2>&1`?

---

### Bagian 3: Skenario Kasus Produksi
1. **Skenario Deadlock Container Engine:**
   Sebuah skrip entrypoint container Docker memonitor log aplikasi via named pipe: `tail -f /app/log.pipe | jq .`. Saat container distop via `docker stop` (yang mengirimkan `SIGTERM`), container tidak langsung mati melainkan menunggu selama 10 detik penuh (*grace period*) sebelum dimatikan paksa dengan `SIGKILL` oleh Docker daemon. Identifikasi penyebab internal shell mengapa `tail` memblokir penerimaan sinyal dan tuliskan perbaikan implementasi trap handler-nya!

2. **Skenario High-Contention Race Condition:**
   Sebanyak 50 runner batch processing mengeksekusi skrip deployment yang mengakses artefak bersama di NFS mount. Beberapa node melaporkan parsing error: `syntax error: unexpected end of file` saat membaca file konfigurasi sementara yang sedang diperbarui oleh runner master. Rancang arsitektur penulisan file yang aman (*atomic swap pattern*) menggunakan primitive command coreutils untuk menyelesaikan masalah ini!

3. **Skenario Zombie Process Accumulation:**
   Sebuah daemon Bash yang mengorkestrasi parallel background worker menggunakan loop `while true; do worker & done` menyebabkan server kehabisan alokasi Process Table ID (PID Exhaustion) dalam 48 jam, meskipun seluruh worker sudah selesai dieksekusi (*defunct/zombie state*). Jelaskan akar masalah kernel terkait penanganan sinyal `SIGCHLD` pada proses Bash induk dan berikan solusinya!

---

## 16. Summary

1.  **Arsitektur VFS & I/O:** File Descriptors adalah antarmuka langsung ke Open File Table milik kernel Linux. Penguasaan custom FDs (3-9) dan named pipes (FIFOs) memungkinkan pembuatan sistem komunikasi antarmuka data yang terisolasi dan berkinerja tinggi.
2.  **Siklus Hidup Subshell:** Menjalankan eksekusi dalam tanda kurung `()` memicu `fork(2)` yang menduplikasi memory footprint via Copy-on-Write (COW). Komunikasi antar-proses harus dirancang via IPC atau file descriptor terarah, bukan variabel memori global.
3.  **Concurrency & Synchronization:** Menulis ke pipe secara atomik dijamin di bawah batas `PIPE_BUF` (4KB). Mutex mutlak pada level proses sistem operasi wajib menggunakan POSIX kernel locks via `flock` untuk menghindari race condition.
4.  **Signal & Process Group Management:** Skrip enterprise wajib bertanggung jawab penuh atas pohon proses yang dibuatnya. Penanganan sinyal (`SIGTERM`/`SIGINT`) harus mencakup terminasi PGID (`-- -$$`) guna mencegah timbulnya proses orphan dan zombie di layer runtime host atau container.