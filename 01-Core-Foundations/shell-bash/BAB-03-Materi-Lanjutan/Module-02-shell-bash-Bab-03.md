# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** Shell-Bash | **Bab:** 03 (BAB-03-Materi-Lanjutan)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup proses kernel Linux (`fork`, `execve`, `clone`, `waitpid`) dan pemetaan *File Descriptor* (FD) di dalam engine eksekusi Bash.
- **Mengarsiteksi** sistem *Inter-Process Communication* (IPC) asinkron dan konkuren berbasis Bash menggunakan *Named Pipes* (FIFO), *Process Substitution*, dan *Coprocesses*.
- **Mengimplementasikan** mekanisme penanganan sinyal sistem (*POSIX Signals*) dan *Graceful Termination* yang tahan terhadap kondisi *race condition* dan *cascading failures*.
- **Mendesain** *high-throughput stream processor* modular untuk lingkungan produksi berskala *enterprise* tanpa menimbulkan *memory leak*, *zombie process*, atau *unhandled file descriptor leak*.

---

## 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib memahami:
- Pengetahuan fundamental administrasi sistem Linux/UNIX dan permission model.
- Penguasaan konsep manipulasi stream dasar (`stdin`, `stdout`, `stderr`, redirection `>` dan `>>`).
- Pemahaman dasar arsitektur CPU, *virtual memory paging*, dan *system calls* kernel Linux.
- Familiaritas dengan utilitas sistem: `strace`, `lsof`, `procfs` (`/proc`), `flock`, dan `kill`.

---

## 3. Concept & Internal Architecture (Mendalam)

Bash bukan sekadar bahasa interpretasi sekuensial sederhana; ia bertindak sebagai orkestrator sistem operasi tingkat tinggi yang berinteraksi langsung dengan antarmuka *POSIX system call*.

```
+-----------------------------------------------------------------------+
|                             USER SPACE                                |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                           Bash Parser                           |  |
|  |   [Lexer] -> [AST Generator] -> [Expansion Engine] -> [Exec]    |  |
|  +-----------------------------------------------------------------+  |
|           |                 |                     |                   |
|       fork()           clone() (threads)      pipe() / dup2()         |
|           v                 v                     v                   |
|  +-----------------+  +-----------------+  +-----------------------+  |
|  | Subshell Child  |  | Coprocess Engine|  | FD Table (0, 1, 2...) |  |
|  +-----------------+  +-----------------+  +-----------------------+  |
|           |                 |                     |                   |
+-----------|-----------------|---------------------|-------------------+
|           v                 v                     v       KERNEL SPACE|
|  +-----------------------------------------------------------------+  |
|  |                   Linux Virtual Memory (VMA)                    |  |
|  |        - Copy-On-Write (COW) Pages                              |  |
|  |        - Anonymous Pipes & Circular Buffers (default 64KB)      |  |
|  |        - Signal Handling Table (struct k_sigaction)             |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

### 3.1. Kernel Syscall Abstraction: Fork-and-Exec Model
Setiap kali shell menjalankan perintah non-builtin atau subshell, kernel mengeksekusi transisi status proses melalui dua syscall utama:
1. `fork()`: Kernel menduplikasi proses induk (Bash parent). Ruang alamat memori (*virtual address space*) tidak disalin secara fisik langsung, melainkan ditandai sebagai **Copy-On-Write (COW)**.
2. `execve()`: Kernel memuat binary baru ke dalam ruang alamat proses child, mengganti *text segment*, *data segment*, *heap*, dan *stack*, namun tetap mewarisi *file descriptors* tertentu kecuali flag `FD_CLOEXEC` aktif.

Jika Bash menjalankan *builtin command* (seperti `cd`, `read`, `export`), Bash tidak memanggil `fork()` maupun `execve()`, melainkan memutasi *state* internal di dalam *heap/stack* proses Bash itu sendiri.

### 3.2. File Descriptor Table & Redirection Mechanics
Linux kernel mengasosiasikan setiap proses dengan tabel *file descriptor* yang mengarah ke *virtual file table entry*.
- Redirection `2>&1` dieksekusi melalui syscall `dup2(1, 2)`. Syscall ini menduplikasi entri tabel file descriptor indeks 1 ke indeks 2. Urutan penulisan redirection bersifat *strictly left-to-right*:
  - `>file 2>&1`: FD 1 diarahkan ke `file`, kemudian FD 2 disalin dari FD 1 (FD 2 mengarah ke `file`).
  - `2>&1 >file`: FD 2 disalin dari FD 1 (mengarah ke terminal/stdout awal), kemudian FD 1 diarahkan ke `file`. Akibatnya, stderr tetap keluar ke terminal.

### 3.3. Inter-Process Communication (IPC) Internals
- **Anonymous Pipes (`|`)**: Mengalokasikan *circular buffer* di kernel memory (biasanya 64 KB pada Linux kernel 2.6.11+). Jika buffer penuh, proses penulis (*producer*) akan di-*block* oleh kernel via *scheduler wait-queue* hingga proses pembaca (*consumer*) mengonsumsi data, dan sebaliknya (*backpressure control*).
- **Process Substitution (`<()` dan `>()`)**: Bash menggunakan anonymous pipe via path `/dev/fd/<n>` atau membuat *Named Pipe* temporer jika sistem tidak memiliki `/dev/fd`. File descriptor dibuka dan dipetakan secara asinkron sebelum target command dieksekusi.
- **Named Pipes (FIFO)**: Menggunakan filesystem inode (`S_IFIFO`), tetapi payload data tetap berada di memori kernel tanpa menyentuh *disk storage block*. FIFO menyediakan titik temu terdefinisi (*rendezvous point*) untuk proses yang tidak memiliki hubungan parent-child.
- **Coprocesses (`coproc`)**: Membuat proses child konkuren yang terhubung secara bidirectional dengan shell induk via dua file descriptor baru: satu untuk *write pipeline* dan satu untuk *read pipeline*.

### 3.4. Signal Handling & Trap Engine
Sinyal adalah interupsi asinkron tingkat OS. Ketika kernel mengirim sinyal (misalnya `SIGTERM` [15], `SIGINT` [2], `SIGCHLD` [17]):
1. Eksekusi proses dihentikan sementara (*interrupted*).
2. Konteks register CPU disimpan, dan eksekusi dialihkan ke *registered signal handler*.
3. Dalam Bash, perintah `trap` mendaftarkan instruksi ke struktur internal. Bash menunda eksekusi trap handler hingga perintah foreground yang sedang berjalan menyelesaikan *syscall cycle*-nya, kecuali sinyal tersebut menyebabkan penghentian langsung (*fatal signal*) atau shell berada dalam status `wait`.

---

## 4. Why & What

| Dimensi | Native Shell-Bash (Enterprise Architecture) | Bahasa Tingkat Tinggi (Python/Go) |
| :--- | :--- | :--- |
| **Startup Overhead** | Sangat rendah (orde mikrodetik untuk builtin, ~1-2ms per fork) | Menengah ke Tinggi (runtime bootstrap, garbage collector initialization) |
| **Integrasi OS** | *Native*; manipulasi stream, FD, dan signal terikat langsung ke POSIX API | Membutuhkan library pembungkus (`os`, `subprocess`, `syscall`) |
| **Resource Footprint** | Minimal (~2-4 MB RAM footprint) | 15 MB - 50+ MB (runtime overhead) |
| **Kesesuaian Penggunaan** | Orkestrator container init, stream routing, pipeline deployment, glue logic OS | Business logic kompleks, komputasi floating point, rest API server |

### Mengapa Perlu Pendekatan Arsitektur Lanjutan pada Bash?
Di lingkungan produksi (k8s entrypoint, systemd units, bare-metal telemetry daemons), script Bash sering menjadi titik kegagalan pertama (*single point of failure*). Kegagalan menangani `SIGTERM` di container menyebabkan pod di-`SIGKILL` paksa setelah *grace period*, mengakibatkan data corruption. Tanpa manajemen File Descriptor yang disiplin, proses dapat mengalami *FD starvation* atau *deadlock* saat pipeline memblokir stream input.

---

## 5. How (Workflow Detail)

### 5.1. Siklus Hidup Eksekusi Pipeline Multi-Proses
```
[Parent Process (PID 1000)]
         |
         |-- pipe() syscall -> Mengembalikan FDs: [read_fd, write_fd]
         |
         |-- fork() ----------------------------------------+
         |   (Child 1 - Producer: PID 1001)                 |-- fork()
         |   dup2(write_fd, STDOUT_FILENO)                  |   (Child 2 - Consumer: PID 1002)
         |   close(read_fd)                                 |   dup2(read_fd, STDIN_FILENO)
         |   execve("generator")                            |   close(write_fd)
         |                                                  |   execve("processor")
         |                                                  |
         +------------- waitpid(1001) & waitpid(1002) <-----+
```

### 5.2. Protokol Graceful Shutdown Berjenjang
1. **Pendaftaran Trap**: Script mendaftarkan handler untuk `SIGTERM`, `SIGINT`, dan `EXIT`.
2. **Signal Interception**: OS mengirim `SIGTERM` ke process group.
3. **Cascading Propagation**: Parent shell menerima sinyal, menahan penghentian mendadak, mengirim sinyal ke semua *child processes* yang terdaftar (`jobs -p`).
4. **Drain Phase**: Memberikan batas waktu tertentu (*drain timeout*) bagi proses anak untuk mengosongkan buffer IO.
5. **Atomic Cleanup**: Menghapus FIFO, lockfile, dan membebaskan custom file descriptor.
6. **Clean Exit**: Mengembalikan status terminasi yang valid ke kernel (`128 + signal_number`).

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem File Descriptor dan Pipe: Sistem Plumbing Industri
Bayangkan proses Bash Anda sebagai ruang kontrol pabrik.
- **File Descriptor (0, 1, 2)**: Tiga keran standar pabrik (0 = Pipa Masukan Bahan Baku, 1 = Pipa Pengeluaran Produk, 2 = Pipa Pembuangan Limbah).
- **Custom FD (3-9)**: Katup tambahan yang dipasang teknisi untuk kebutuhan khusus.
- **Anonymous Pipe (`|`)**: Selang fleksibel sementara yang langsung menghubungkan pipa pengeluaran Mesin A ke pipa masukan Mesin B.
- **Named Pipe (FIFO)**: Tangki perantara tetap di lantai pabrik. Mesin A dapat menuangkan material ke sana kapan saja; material tidak bergerak sampai Mesin B memasang pipa dan menyedotnya keluar.
- **Deadlock**: Mesin A menolak beroperasi sebelum tangki terisi penuh, sementara Mesin B menolak menyedot sebelum Mesin A selesai bekerja. Keduanya saling tunggu sampai sistem mati.

```
       PRODUCER PROCESS                     CONSUMER PROCESS
  +-----------------------+              +-----------------------+
  |  FD 1 (STDOUT)        |              |  FD 0 (STDIN)         |
  +-----------+-----------+              +-----------^-----------+
              |                                      |
              |       KERNEL CIRCULAR BUFFER         |
              +-----> [ [Payload] [Data] [...] ] ----+
                      ^                        ^
                      |                        |
                 write_pointer            read_pointer
            (Block jika buffer penuh)  (Block jika buffer kosong)
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Alokasi Dynamic Custom File Descriptor
Bash v4.1+ memungkinkan alokasi file descriptor otomatis tanpa *hardcode* nomor FD.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Buat temporary file untuk demonstrasi
TEMP_METRIC=$(mktemp /tmp/metric_buffer.XXXXXX)

# Alokasikan file descriptor dinamis berikutnya yang tersedia (> 9) ke variabel 'FD_METRIC'
exec {FD_METRIC}>"${TEMP_METRIC}"

echo "Dialokasikan FD nomor: ${FD_METRIC}"

# Menulis ke file descriptor kustom via redirection
echo "timestamp=$(date +%s) cpu_load=0.12" >&"${FD_METRIC}"
echo "timestamp=$(date +%s) cpu_load=0.25" >&"${FD_METRIC}"

# Tutup FD untuk penulisan
exec {FD_METRIC}>&-

# Buka kembali untuk pembacaan secara dinamis
exec {FD_METRIC_IN}<"${TEMP_METRIC}"

while IFS= read -r line <&"${FD_METRIC_IN}"; do
    echo "Processing telemetry entry: ${line}"
done

# Tutup FD pembacaan dan bersihkan storage
exec {FD_METRIC_IN}<&-
rm -f "${TEMP_METRIC}"
```

### 7.2. Practical Example: Robust Worker Pool dengan Bidirectional Coprocess & Named Pipe
Implementasi *producer-consumer worker pattern* menggunakan Named Pipe untuk *concurrency throttling* dan isolasi error.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Concurrent Batch Processor with Lock Management & IPC
# ==============================================================================
set -Eeuo pipefail

readonly WORK_DIR="/tmp/batch_engine_${$}"
readonly FIFO_QUEUE="${WORK_DIR}/job.fifo"
readonly MAX_PARALLEL_WORKERS=4
readonly LOCK_FILE="/var/lock/batch_engine.lock"

# Buat workspace
mkdir -p "${WORK_DIR}"
mkfifo "${FIFO_QUEUE}"

# ------------------------------------------------------------------------------
# Cleanup Handler & Resource Deallocation
# ------------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    trap - SIGINT SIGTERM EXIT
    echo "[CLEANUP] Initiating shutdown sequence (Exit Code: ${exit_code})..."

    # Matikan semua child job yang berada dalam process group ini
    if [[ -n "$(jobs -pr)" ]]; then
        echo "[CLEANUP] Terminating active background workers..."
        kill -SIGTERM $(jobs -pr) 2>/dev/null || true
        wait $(jobs -pr) 2>/dev/null || true
    fi

    # Lepaskan custom file descriptor jika masih terbuka
    if { exec {FIFO_READ_FD}<&-; } 2>/dev/null; then :; fi
    if { exec {FIFO_WRITE_FD}>&-; } 2>/dev/null; then :; fi

    # Hapus file sistem temporer
    rm -rf "${WORK_DIR}"
    echo "[CLEANUP] Cleanup completed successfully."
    exit "${exit_code}"
}

trap cleanup SIGINT SIGTERM EXIT

# ------------------------------------------------------------------------------
# Mutex Lock via flock (Mencegah overlapping execution)
# ------------------------------------------------------------------------------
exec {LOCK_FD}>"${LOCK_FILE}"
if ! flock -n "${LOCK_FD}"; then
    echo "[ERROR] Another instance of batch processor is running. Aborting." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# Inisialisasi Non-Blocking Queue (Named Pipe Mechanics)
# ------------------------------------------------------------------------------
# Membuka FIFO untuk pembacaan dan penulisan sekaligus agar tidak memblokir shell
exec {FIFO_READ_FD}<>"${FIFO_QUEUE}"

# Inisialisasi token semaphore untuk membatasi worker konkuren
for ((i = 0; i < MAX_PARALLEL_WORKERS; i++)); do
    echo "TOKEN" >&"${FIFO_READ_FD}"
done

# ------------------------------------------------------------------------------
# Worker Routine Function
# ------------------------------------------------------------------------------
worker_task() {
    local job_id="${1}"
    local payload="${2}"

    echo "[WORKER-$(printf '%02d' "${job_id}")] Processing item: ${payload}"
    
    # Simulasi I/O bound atau CPU bound task
    sleep "$(( (RANDOM % 3) + 1 ))"

    if [[ "${payload}" == "FAIL_TRIGGER" ]]; then
        echo "[WORKER-$(printf '%02d' "${job_id}")] Critical failure encountered!" >&2
        return 2
    fi

    echo "[WORKER-$(printf '%02d' "${job_id}")] Finished item: ${payload}"
    return 0
}

# ------------------------------------------------------------------------------
# Engine Dispatcher Loop
# ------------------------------------------------------------------------------
echo "[ENGINE] Dispatcher running. Processing workloads..."

JOBS_PAYLOAD=("alpha" "beta" "gamma" "delta" "FAIL_TRIGGER" "epsilon" "zeta")

for idx in "${!JOBS_PAYLOAD[@]}"; do
    payload="${JOBS_PAYLOAD[$idx]}"
    job_id=$((idx + 1))

    # Ambil token dari semaphore pool (blocking jika MAX_PARALLEL_WORKERS tercapai)
    read -r -u "${FIFO_READ_FD}" _TOKEN

    # Eksekusi worker secara background
    (
        set +e
        worker_task "${job_id}" "${payload}"
        worker_status=$?

        # Kembalikan token ke semaphore pool terlepas dari status eksekusi
        echo "TOKEN" >&"${FIFO_READ_FD}"
        exit "${worker_status}"
    ) &
done

# Tunggu hingga semua background jobs selesai dieksekusi
wait

echo "[ENGINE] All operations completed. Commencing normal exit."
```

---

## 8. Real World Case Study (Enterprise Scale)

### Masalah: Broken Deployment & Data Corruption pada High-Volume Telemetry Collector
Sebuah institusi perbankan global memiliki daemon lokal di setiap host node (*Node Exporter Log Scraper*) yang ditulis dalam Bash. Script ini membaca stream audit log dari `auditd` kernel socket dan meneruskannya ke Kafka local proxy menggunakan named pipe.

**Insiden Produksi (P1):**
1. Setiap kali instance Kafka lokal di-restart (*rolling update*), stream pengiriman terputus.
2. Script Bash menerima sinyal `SIGPIPE` dari kernel karena menulis ke socket yang tertutup. Karena default trap handling tidak diatur, Bash langsung *crash* seketika.
3. Subshell yang membaca kernel stream menjadi *orphan process* (`PPID=1`), terus mengonsumsi memori tanpa batas (*memory leak* pada buffer `/proc/kmsg`), mengakibatkan *Kernel Out-of-Memory (OOM) Panic* pada server host.

### Solusi Arsitektural: Resilient Circuit Breaker Pipe Engine
Tim SRE merancang ulang *stream processor* tersebut menggunakan arsitektur *self-healing pipe* dengan deteksi `SIGPIPE`, buffer *backpressure handling*, dan penguncian *atomic file descriptor*.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Resilient Stream Forwarder with Self-Healing IPC
# ==============================================================================
set -Eeuo pipefail

readonly BUFFER_DIR="/var/run/telemetry_stream"
readonly STREAM_FIFO="${BUFFER_DIR}/kafka_stream.fifo"
readonly LOG_SOURCE="/var/log/audit/audit.log"
readonly DEAD_LETTER_LOG="/var/log/telemetry_dlq.log"
readonly MAX_RECONNECT_ATTEMPTS=5

mkdir -p "${BUFFER_DIR}"
[[ -p "${STREAM_FIFO}" ]] || mkfifo "${STREAM_FIFO}"

# Tangani SIGPIPE secara eksplisit agar script tidak crash ketika consumer mati
trap '' SIGPIPE

cleanup_orchestrator() {
    echo "[SHUTDOWN] Terminating forwarder daemon..."
    trap - SIGINT SIGTERM EXIT
    kill $(jobs -p) 2>/dev/null || true
    rm -rf "${BUFFER_DIR}"
    exit 0
}
trap cleanup_orchestrator SIGINT SIGTERM EXIT

# Background Receiver/Consumer Simulator (Mock Kafka ingestion agent)
mock_kafka_consumer() {
    while true; do
        if [[ -p "${STREAM_FIFO}" ]]; then
            # Konsumsi stream secara streaming
            while IFS= read -r line; do
                # Simulasi downtime acak untuk menguji daya tahan pipe
                if (( RANDOM % 100 < 5 )); then
                    echo "[KAFKA] Network blip! Consumer disconnecting..." >&2
                    return 1
                fi
                # Simulasi ingestion
            done < "${STREAM_FIFO}"
        fi
        sleep 1
    done
}

# Main Forwarder Loop dengan Circuit Breaker Logic
run_stream_engine() {
    local retry_count=0

    # Menjaga open file descriptor agar FIFO tidak mengirim EOF secara konstan
    exec {FIFO_DUMMY_WRITE}>"${STREAM_FIFO}"

    # Eksekusi consumer dalam background process loop
    mock_kafka_consumer &
    local consumer_pid=$!

    echo "[ENGINE] Monitoring and tailing: ${LOG_SOURCE}"

    # Baca file stream (simulasi via loop pembacaan aktif)
    while true; do
        if ! kill -0 "${consumer_pid}" 2>/dev/null; then
            echo "[CIRCUIT-BREAKER] Consumer dead. Route stream to Dead-Letter Queue..."
            ((retry_count++))

            if (( retry_count > MAX_RECONNECT_ATTEMPTS )); then
                echo "[FATAL] Kafka unreachable after max retries. Escalating incident." >&2
                exit 2
            fi

            # Re-spawn Consumer
            sleep 2
            mock_kafka_consumer &
            consumer_pid=$!
            continue
        fi

        # Kirim data ke FIFO; jika gagal (SIGPIPE tertangkap), arahkan ke DLQ
        local timestamp
        timestamp=$(date --iso-8601=ns)
        local telemetry_payload="{\"node_time\": \"${timestamp}\", \"metric\": \"heartbeat\"}"

        if ! echo "${telemetry_payload}" > "${STREAM_FIFO}" 2>/dev/null; then
            echo "${telemetry_payload}" >> "${DEAD_LETTER_LOG}"
            echo "[WARNING] Write to FIFO failed. Diverted to DLQ."
        else
            retry_count=0
        fi

        sleep 0.2
    done
}

run_stream_engine
```

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Named Pipes (FIFO)** | Mengeliminasi I/O disk bottleneck secara absolut; memori buffer dikelola langsung oleh Linux kernel. | Terjadinya *Blocking Lock*: pembacaan atau penulisan pertama akan tertahan selamanya jika ujung pipa (*pipe ends*) tidak dibuka secara simetris. |
| **Coprocess (`coproc`)** | Komunikasi dua arah (*two-way messaging*) yang elegan ke satu proses latar belakang dari shell utama. | Rentan terhadap *deadlock* jika buffer internal (64KB) penuh dan proses induk memanggil `read` saat child menunggu `write`. Tidak kompatibel dengan POSIX standar (Bash-only). |
| **Subshell `(...)`** | Menjaga isolasi variabel dan modifikasi *environment*; tidak mencemari memori parent shell. | Overhead eksekusi kernel `fork()`. Modifikasi status (variabel, direktori aktif) hilang saat subshell selesai dieksekusi. |
| **Process Substitution `<()`** | Memungkinkan perlakuan output stream dari multiple program seolah-olah sebagai file reguler. | Pemetaan `/dev/fd/*` tidak selalu tersedia di semua sistem kontainer mikro (misalnya lingkungan minimal chroot atau alpine tanpa `/dev` mounting yang tepat). |
| **Atomic Locking via `flock`** | Mencegah *race condition* secara reliabel pada level file descriptor kernel. | Ketergantungan pada *filesystem type*; `flock` tidak aman jika digunakan di atas distributed network storage (NFS/CIFS) tanpa dukungan lock daemon. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Subshell Variable Scope Loss
*Kasus:* Mengubah nilai variabel di dalam *while loop* yang dihubungkan dengan pipe.

```bash
# SALAH: while loop berjalan di dalam subshell child process
counter=0
cat /etc/hosts | while read -r line; do
    ((counter++))
done
echo "Total lines: ${counter}" # Output: 0! Variabel counter di parent tidak berubah.

# PERBAIKAN: Gunakan Process Substitution atau Redirection ke loop utama
counter=0
while read -r line; do
    ((counter++))
done < <(cat /etc/hosts)
echo "Total lines: ${counter}" # Output: Akurat (berjalan di parent shell)
```

### 10.2. Zombie Process Accumulation
*Kasus:* Menjalankan background tasks (`&`) tanpa mengimplementasikan `wait` atau trap handling untuk `SIGCHLD`.

*Gejala:* Perintah `ps aux | grep 'Z'` menampilkan ratusan proses berstatus `<defunct>`.

*Solusi:*
```bash
# Tangani terminasi child process secara asinkron
reap_zombies() {
    local dead_pid
    # WNOHANG memastikan waitpid tidak memblokir eksekusi jika tidak ada zombie
    while dead_pid=$(wait -n -p _ 2>/dev/null); do
        : # Child process berhasil dibersihkan dari process table kernel
    done
}
trap reap_zombies SIGCHLD
```

### 10.3. FIFO Deadlock saat Initial Open
*Kasus:* Membuka Named Pipe untuk dibaca di proses yang sama tanpa redirection non-blocking.

```bash
mkfifo /tmp/my.fifo
# DEADLOCK: Shell akan hang di baris ini selamanya
read -r line < /tmp/my.fifo

# PERBAIKAN: Buka FIFO dalam mode Read-Write menggunakan custom file descriptor
exec 3<>/tmp/my.fifo
# Shell tidak akan hang karena ada descriptor penulisan yang terpasang
read -r -u 3 -t 1 line || echo "Timeout: Tidak ada data di pipe"
exec 3>&-
```

### Panduan Troubleshooting dengan `strace` & `lsof`
1. **Lacak Eksekusi Syscall Shell:**
   ```bash
   strace -f -e trace=clone,fork,execve,pipe,dup2,close -p <PID_BASH>
   ```
2. **Identifikasi File Descriptor Leak:**
   ```bash
   ls -la /proc/<PID_BASH>/fd/
   lsof -p <PID_BASH>
   ```
   *Jika nomor FD terus bertambah tanpa pernah tertutup (terutama FD > 3), sistem mengalami resource leak.*

---

## 11. Best Practices (Production Checklist)

- [ ] **Strict Execution Flags:** Selalu deklarasikan `set -Eeuo pipefail` di header script.
  - `-E`: Trap handler mewarisi fungsi shell and subshells.
  - `-e`: Berhenti seketika jika ada statement yang mengembalikan status non-nol.
  - `-u`: Lempar error fatal jika variabel belum didefinisikan (*unbound variable*).
  - `-o pipefail`: Gagalkan seluruh pipeline jika salah satu segment perintah gagal (bukan hanya perintah terakhir).
- [ ] **Explicit Signal Propagation:** Tangkap `SIGINT` dan `SIGTERM` secara eksplisit, lalu teruskan sinyal ke sub-process group:
  ```bash
  trap 'kill -TERM 0' SIGINT SIGTERM
  ```
- [ ] **Resource Isolation:** Gunakan `mktemp -d` untuk membuat *isolated runtime directory* dan pastikan terhapus via `trap ... EXIT`.
- [ ] **Atomic Operation:** Jangan gunakan pengecekan manual keberadaan file (`[[ ! -f /tmp/lock ]] && touch /tmp/lock`) untuk locking karena rentan *race condition*. Selalu gunakan `flock(1)` atau `mkdir` direktori atomik.
- [ ] **Dynamic FD Allocation:** Hindari *hardcode* nomor FD manual (`exec 3>file`). Gunakan sintaks dinamis `exec {MY_FD}>file`.
- [ ] **Safe Processing of Delimiters:** Selalu panggil `read` dengan flag `-r` (menonaktifkan *backslash escaping*) dan set `IFS=` kosong untuk mencegah *unintended whitespace trimming*.

---

## 12. Hands-on Practice

Buat seluruh file praktikum berikut pada direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 1: Eksperimen Pipe Buffering & Throttling
Buat file `01_pipe_buffer_test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

FIFO_TEST="/tmp/buffer_exp.fifo"
rm -f "${FIFO_TEST}"
mkfifo "${FIFO_TEST}"

echo "[Step 1] Named Pipe dibuat di: ${FIFO_TEST}"

# Jalankan consumer yang lambat (membaca setiap 1 detik)
(
    exec 3<"${FIFO_TEST}"
    echo "[Consumer] Siap membaca..."
    while IFS= read -r -u 3 line; do
        echo "[Consumer received] ${line}"
        sleep 1
    done
) &
CONSUMER_PID=$!

# Jalankan producer yang cepat
exec 4>"${FIFO_TEST}"
echo "[Step 2] Mengirim data cepat ke buffer..."
for i in {1..5}; do
    echo "Message payload ID: ${i}" >&4
    echo "[Producer sent] ID: ${i}"
done

echo "[Step 3] Semua data terkirim. Menunggu consumer mengosongkan antrian..."
# Tutup write descriptor agar consumer menerima EOF setelah item terakhir dibaca
exec 4>&-

wait "${CONSUMER_PID}"
rm -f "${FIFO_TEST}"
echo "[Step 4] Eksekusi selesai."
```

Jalankan dan amati:
```bash
chmod +x 01_pipe_buffer_test.sh
./01_pipe_buffer_test.sh
```

### Langkah 2: Audit File Descriptor Menggunakan `/proc`
Buat file `02_fd_leak_investigation.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Investigasi PID: $$"
echo "--- File Descriptors Awal ---"
ls -l /proc/$$/fd/

# Alokasikan 3 Custom File Descriptors
exec {FD_DATA}< /etc/resolv.conf
exec {FD_DUMMY}> /tmp/dummy_out.tmp
exec {FD_PIPE_READ}<> <(:)

echo -e "\n--- File Descriptors Setelah Alokasi Dinamis ---"
ls -l /proc/$$/fd/

# Tutup semua descriptor yang dibuat
exec {FD_DATA}<&-
exec {FD_DUMMY}>&-
exec {FD_PIPE_READ}>&-
rm -f /tmp/dummy_out.tmp

echo -e "\n--- File Descriptors Setelah Dideallokasi (Clean) ---"
ls -l /proc/$$/fd/
```

Jalankan:
```bash
chmod +x 02_fd_leak_investigation.sh
./02_fd_leak_investigation.sh
```

---

## 13. Exercise

### Level Easy: Safe File Descriptor Redirection Sanitizer
- **File path:** `hands-on/m02/exercise_easy.sh`
- **Objektif:** Buat script yang mengeksekusi pipeline: mengambil isi `/etc/passwd`, melakukan filtering baris yang memuat `/bin/bash`, memodifikasi separator `:` menjadi format tab, dan menuliskannya ke stdout tanpa membuat *temporary file* di disk.
- **Kriteria Keberhasilan:** Script wajib berjalan dengan `set -euo pipefail`, menggunakan *process substitution* `<(...)`, dan tidak meninggalkan sisa process/file.

### Level Medium: Mutex Lock File Processor
- **File path:** `hands-on/m02/exercise_medium.sh`
- **Objektif:** Implementasikan skrip yang melakukan kalkulasi *critical section* (menambah angka integer dalam sebuah file teks sebanyak 100 kali iterasi). Buat agar skrip ini dapat dijalankan secara bersamaan (*concurrently*) oleh 5 instance script yang berbeda.
- **Kriteria Keberhasilan:** Menggunakan `flock` pada specific File Descriptor untuk menjamin tidak terjadi *lost update* (jika nilai awal 0, setelah 5 instance skrip selesai, nilai final harus tepat 500).

### Level Hard: Asynchronous Task Dispatcher with Dynamic Throttling
- **File path:** `hands-on/m02/exercise_hard.sh`
- **Objektif:** Bangun *standalone queue engine* di Bash yang menerima daftar 50 string URL dari sebuah file input. Script harus mendownload header URL tersebut (`curl -I`) secara konkuren dengan batas maksimal concurrent running job sebanyak `N` (misal 5 worker).
- **Kriteria Keberhasilan:** 
  1. Concurrency dikontrol via FIFO token semaphore atau dynamic job table tracking.
  2. Menangkap sinyal `SIGINT` (Ctrl+C) secara bersih: saat dihentikan di tengah jalan, seluruh child workers harus segera di-`SIGTERM`, lock dan FIFO dibersihkan, dan mencetak laporan berapa URL yang telah berhasil diproses sebelum interrupt.

---

## 14. Challenge

### Arsitektur "Resilient Bash Micro-Daemon"
**Deskripsi Skenario Sistem:**
Anda adalah Principal Infrastructure Engineer pada platform bare-metal compute. Anda diminta membuat sebuah daemon independen berbasis Bash murni bernama `agent-sentinel.sh` yang bertugas memantau status CPU & disk load, lalu mempublikasikannya ke HTTP metric endpoint lokal via `curl` setiap 2 detik.

**Spesifikasi Persyaratan Teknis:**
1. **Self-Daemonization & Singleton:** Daemon harus memvalidasi bahwa hanya ada 1 instance dirinya yang berjalan di seluruh sistem menggunakan kernel *file locks*. Jika instance lama stale/dead, lock harus terbebas secara otomatis tanpa intervensi manual.
2. **Zero In-Flight Loss Pipe:** Script harus membaca data beban sistem menggunakan *Named Pipe* yang dialokasikan khusus, dipasok oleh background subshell.
3. **Signal Orchestration:**
   - Menerima sinyal `SIGHUP`: Membaca ulang file konfigurasi `/etc/sentinel.conf` secara dinamis tanpa restart process PID.
   - Menerima sinyal `SIGUSR1`: Mencetak statistik internal (waktu aktif, jumlah cycle metric terkirim, jumlah I/O failures) ke stderr secara asinkron.
   - Menerima sinyal `SIGTERM`: Melakukan drain operasi pengiriman metric yang sedang berlangsung (timeout 5 detik) sebelum keluar dengan exit code 0.
4. **Resilience Boundary:** Jika endpoint HTTP lokal down (kegagalan koneksi), script tidak boleh *crash*. Daemon harus beralih ke *fallback buffer circular array* dalam memori (maksimal 100 metrik terakhir) dan memuntahkan data tersebut secara otomatis begitu endpoint HTTP kembali online.
5. **No External Tools Dependency:** Tidak boleh menggunakan daemon tools eksternal seperti `supervisord`, `systemd-notify`, atau utility pihak ketiga di luar core utils standar Linux.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara eksekusi perintah via *Builtin command* dengan *External binary* dalam konteks pembuatan proses di kernel?
2. Mengapa urutan redirection `>output.log 2>&1` menghasilkan luaran yang berbeda dibandingkan `2>&1 >output.log`?
3. Apa fungsi flag `-u` pada parameter `set -euo pipefail` di Bash?
4. Mengapa modifikasi variabel di dalam baris perintah `cat file.txt | while read line; do VAR="xyz"; done` tidak dapat diakses di luar loop tersebut?
5. Mengapa perintah `kill -9` (`SIGKILL`) tidak dapat ditangkap (*trapped*) menggunakan perintah `trap` di Bash?

### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja internal *Circular Buffer* pada implementasi kernel Linux Anonymous Pipe (`|`), dan apa yang terjadi pada *Producer process* jika buffer tersebut terisi penuh?
7. Terangkan mekanisme `flock` pada file descriptor dan jelaskan mengapa teknik ini lebih aman dibandingkan membuat file penanda berbasis `touch /var/lock/app.pid`!
8. Apa yang dimaksud dengan *Zombie Process*, apa penyebab kemunculannya dari script Bash, dan *system call* apa yang gagal dieksekusi oleh parent process?
9. Jelaskan perbedaan operasional dan interaksi sistem berkas antara *Anonymous Pipe* dengan *Named Pipe (FIFO)* di bawah VFS Linux!
10. Bagaimana sintaks `exec {VAR_FD}>file.txt` mengelola alokasi File Descriptor secara dinamis di Bash v4.1+, dan bagaimana cara menutup kembali file descriptor tersebut dengan benar?

### 3 Skenario Kasus Produksi
11. **Skenario A:** Sebuah script pemrosesan file log harian berjalan lancar di staging, namun ketika dijalankan di server produksi dengan volume log 50 GB, script tersebut mengalami *hang/freeze* permanen di baris `output=$(app_engine | filter_engine)`. Setelah diperiksa dengan `top`, CPU usage menunjukkan 0%. Gunakan analisis *system call* dan *I/O buffering* untuk mengidentifikasi penyebab *deadlock* tersebut dan berikan solusi arsitekturalnya!
12. **Skenario B:** Container Kubernetes yang menjalankan aplikasi berbasis worker Bash selalu membutuhkan waktu tepat 30 detik untuk berhenti setelah perintah deployment rollout baru dijalankan (*pod termination*). Log menunjukkan pod dihentikan paksa oleh sinyal `SIGKILL`. Lakukan audit arsitektural pada script entrypoint container tersebut: mengapa sinyal `SIGTERM` dari Kubernetes tidak memicu *graceful shutdown*?
13. **Skenario C:** Anda memiliki pipeline Bash multi-tahap yang dijalankan di background: `producer | transformer | loader &`. Terjadi kegagalan fatal pada tahap `transformer` (segfault / exit code 139), namun seluruh rangkaian skrip induk tetap melanjutkan eksekusi ke baris berikutnya seolah pipeline sukses karena return code yang dibaca adalah milik `loader`. Bagaimana Anda mendesain arsitektur handling error pipeline tersebut agar error di tengah tahapan terdeteksi secara akurat?

---

## 16. Summary

- **Architecture Boundary:** Bash adalah antarmuka kontrol langsung ke *POSIX primitives*. Kehandalan script skala enterprise bergantung pada pemahaman model eksekusi proses kernel (`fork-and-exec`), mekanisme isolasi memori (*Copy-On-Write*), dan manajemen lifecycle tabel *File Descriptor*.
- **Stream & IPC Orchestration:** Redirection bukan sekadar sintaks teks, melainkan manipulasi penunjuk entri array file descriptor via `dup2()`. Named Pipes (FIFO) dan Process Substitution menyediakan jalur IPC berkecepatan tinggi tanpa disk I/O, namun membutuhkan penanganan *blocking mechanics* dan *backpressure* yang teliti guna menghindari kondisi *deadlock*.
- **Signal Safety & Concurrency:** Arsitektur skrip produksi wajib mengimplementasikan isolasi sinyal (`SIGTERM`, `SIGINT`, `SIGPIPE`, `SIGCHLD`). Penggunaan `set -Eeuo pipefail`, penguncian berbasis kernel `flock`, dan manajemen cleanup via `trap ... EXIT` adalah standar baku rekayasa perangkat lunak modern untuk menjamin sistem terbebas dari *leakage*, *race condition*, dan kegagalan beruntun (*cascading failure*).