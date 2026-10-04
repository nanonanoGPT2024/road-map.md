# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis dan Membedah Internal Kernel-Bash:** Memahami secara mendalam interaksi *system call* (`fork`, `execve`, `clone`, `pipe`, `dup2`) dan mutasi tabel File Descriptor (FD) saat Bash mengeksekusi subshell, pipeline, dan redireksi.
*   **Merancang Arsitektur Concurrency & IPC:** Membangun sistem pemrosesan paralel asinkron berbasis *worker pool* murni di Bash dengan kontrol konkurensi terikat (*bounded concurrency*) menggunakan FIFO (*named pipes*), POSIX semaphores simulasian, dan Coprocesses (`coproc`).
*   **Mengimplementasikan Robust Fault Tolerance & Telemetri:** Menguasai propagasi *signal handling* (`SIGTERM`, `SIGINT`, `SIGHUP`, `SIGCHLD`), trapping terisolasi, eliminasi *zombie processes*, serta pelaporan metrik terstruktur (JSON/NDJSON) ke *standard streams*.
*   **Menerapkan Rekayasa Script Skala Enterprise:** Menulis kode Bash modular, *testable*, dan *defensive* menggunakan fitur lanjutan (Bash 4.4+ namerefs, array asosiatif multidimensi emulasian, dynamic file descriptors) dengan standar *zero-defect* untuk sistem misi kritis.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Sintaks Dasar & Kontrol Alur:** Percabangan (`if`, `case`), perulangan (`for`, `while`), dan manipulasi string dasar.
*   **POSIX Tooling Essentials:** Pemahaman praktis utilitas inti POSIX/GNU (`grep`, `sed`, `awk`, `find`, `xargs`, `cut`, `sort`).
*   **Dasar Sistem Operasi Linux:** Konsep *Process ID* (PID), *Process Group* (PGID), *Parent-Child relationship*, serta manipulasi I/O stream standar (`stdin` [0], `stdout` [1], `stderr` [2]).
*   **Perintah Diagnostik:** Terbiasa menggunakan `strace`, `lsof`, `ps`, `kill`, dan `trap`.

---

## 3. Concept & Internal Architecture

Bash bukan sekadar penerjemah perintah interaktif (*command interpreter*); Bash adalah *runtime environment* lengkap yang berjalan di *user space* dan berinteraksi langsung dengan Linux Kernel API melalui *system calls*.

### A. Lifecycle Eksekusi: Fork-Exec Pattern & Subshell Overhead
Saat script mengeksekusi perintah non-builtin atau subshell, kernel mengeksekusi urutan operasi berikut:

```
[Parent Bash Process (PID: 1000)]
      |
      +---> syscall: clone()/fork() 
      |        |
      |        v
      |   [Child Process (PID: 1001)] 
      |   (Duplikasi Page Table, COW: Copy-On-Write)
      |        |
      |        +---> syscall: dup2() & close() [Jika ada redirection/piping]
      |        |
      |        +---> syscall: execve("/bin/app", argv, envp)
      |                 |
      |                 v
      |            [Image Replaced: /bin/app]
      |                 |
      +--- syscall: wait4() (Jika Foreground)
```

1.  **Fork Phase:** Kernel mengalokasikan task struct baru via `clone(2)`. Di Linux, ini menggunakan *Copy-On-Write* (COW). Memori virtual parent di-*share* secara read-only sampai salah satu proses menulis data.
2.  **File Descriptor Plumb Phase:** Sebelum memanggil biner tujuan, proses anak memodifikasi *file descriptor table*-nya sendiri menggunakan `dup2(2)`. Misalnya, dalam `cmd > file.txt`, child mengeksekusi `open("file.txt", O_WRONLY|O_CREAT|O_TRUNC)` yang menghasilkan FD baru (misal FD 3), lalu memanggil `dup2(3, 1)` dan `close(3)`. FD 1 (`stdout`) kini mengarah ke `file.txt`.
3.  **Exec Phase:** Proses anak memanggil `execve(2)`. Kernel melepaskan ruang memori lama milik Bash, memuat format biner (ELF), memetakan segmen memori baru, dan memulai eksekusi pada `entry point` aplikasi target. Seluruh variabel Bash di proses anak musnah, kecuali yang diekspor (`export`) ke environment block.

### B. Subshell vs Subshell Environment
Subshell terjadi dalam dua konteks:
*   **Explicit Subshell `( ... )`:** Melakukan `fork()` tanpa `execve()`. Proses anak adalah klon penuh dari runtime Bash (termasuk variabel lokal, fungsi, dan opsi shell). Namun, modifikasi memori pada subshell tidak akan pernah terefleksi ke parent shell karena isolasi memori virtual kernel.
*   **Command Substitution `$( ... )`:** Mirip dengan explicit subshell, namun Bash kernel menghubungkan `stdout` anak ke pipe baca internal parent. Parent membaca output via pipe hingga mendeteksi `EOF`, lalu mengeksekusi `wait4()` untuk mengambil exit status.

### C. Pipeline Plumbing & Architectural Trap
Pada pipeline POSIX standard:
```bash
cat large_dataset.log | grep "ERROR" | wc -l
```
Bash mengalokasikan dua anonim pipe via syscall `pipe(2)`. Ketiga proses (`cat`, `grep`, `wc`) dijalankan secara **konkuren** dalam proses anak masing-masing.

```
+-----------+            +------------+            +----------+
| cat (PID) | --(pipe)--> | grep (PID) | --(pipe)--> | wc (PID) |
+-----------+            +------------+            +----------+
     FD 1 -------------------> FD 0 | FD 1 ---------------> FD 0
```

> **Implikasi Arsitektur:** Perubahan variabel dalam loop pipeline seperti `cat list.txt | while read line; do count=$((count+1)); done` akan hilang setelah pipeline selesai, karena blok `while` dieksekusi di dalam subshell. Untuk menghindari ini di Bash 4.2+, gunakan `shopt -s lastpipe` bersamaan dengan deaktivasi *job control* (`set +m`), atau gunakan *process substitution*.

### D. File Descriptor Deep Dive (FD 0-9 vs Arbitrary Dynamic FDs)
Secara konvensional, UNIX mengalokasikan:
*   `0`: `stdin`
*   `1`: `stdout`
*   `2`: `stderr`

Bash mendukung FD `3` sampai `9` secara eksplisit, dan pada Bash 4.1+, FD dinamis dialokasikan menggunakan sintaks variabel:
```bash
exec {my_fd}>"/path/to/fifo"
echo "data" >&"${my_fd}"
exec {my_fd}>&- # Menutup file descriptor secara atomik
```
Kernel mengalokasikan integer FD bebas terkecil (biasanya $> 9$) dan menyimpannya di variabel `my_fd`.

### E. Linux Signals & Trap Invariance
Sinyal Linux dikirimkan secara asinkron ke Process Group ID (PGID). Bash mengekspos handler via bawaan `trap`. Aturan kritis:
1.  **Trapping Foreground Processes:** Jika sebuah proses anak biner (misal `sleep 100`) sedang berjalan di foreground, menekan `Ctrl+C` mengirim `SIGINT` ke seluruh PGID. Bash parent menunda eksekusi trap sampai proses anak selesai (atau mati akibat sinyal).
2.  **Trap Inheritance:** Trap diwariskan ke subshell `( ... )`, namun trap reset ke default saat child memanggil `execve()`.
3.  **The `SIGCHLD` Reaper:** Ketika anak mati, kernel mengubah statusnya menjadi *Zombie* (`[defunct]`) sampai parent memanggil `wait(2)` atau `waitpid(2)` untuk membaca exit code-nya. Mengabaikan penanganan ini pada proses asinkron (`&`) skala ribuan akan menyebabkan *process table exhaustion* di level kernel Linux.

---

## 4. Why & What

### Mengapa Bash Tetap Relevan di Era Go/Python?
1.  **Zero-Dependency Execution:** Bash tersedia langsung pada hampir semua distribusi Linux (Alpine, RHEL, Ubuntu, Debian), kontainer distroless base, dan sistem tertanam (*embedded system*).
2.  **Direct System Call Integration for I/O:** Membuka pipe, memanipulasi network socket via `/dev/tcp/host/port`, serta mengatur multiplexing stream I/O dapat dilakukan dengan 1 baris sintaks native Bash tanpa abstraksi runtime atau GC (Garbage Collection) pause.
3.  **Process Orchestration Glue:** Mengorkestrasi 10 biner kompilasi terpisah (misal: `ffmpeg`, `tar`, `curl`, `jq`) jauh lebih hemat baris dan ekspresif di Bash dibanding menggunakan library `subprocess` (Python) atau `os/exec` (Go).

### Kapan Bash TIDAK Boleh Digunakan (Boundary Conditions)?
*   Kalkulasi floating-point intensif atau pemrosesan array jutaan record (Bash hanya mendukung operasi 64-bit integer native).
*   Sistem dengan kebutuhan struktur data kompleks (Graph, Tree, Struct pointer murni).
*   Skenario yang membutuhkan multithreading dalam satu alamat memori (Bash hanya mendukung multi-processing murni dengan isolasi memori total).

---

## 5. How (Workflow Detail)

### Protokol Eksekusi Pipeline Produksi Tingkat Lanjut
Berikut alur baku eksekusi sistem pipeline produksi dengan *bounded parallelization* dan mitigasi race condition:

```
[Start Script]
      |
      v
[Inisialisasi Environment: Strict Mode + Signal Traps]
      |
      v
[Alokasi IPC: Non-blocking FIFO (Named Pipe) Backed Semaphore]
      |
      v
[Enqueue Token ke Semaphore (Sejumlah Maksimum Worker Concurrency)]
      |
      +<------------------------------------+
      |                                     |
      v                                     |
[Ambil Token dari FIFO]                     |
      |                                     |
      v                                     |
[Spawn Worker via Subshell Asinkron (&)]   |
      |                                     |
      |---> (Eksekusi Job Independen)       |
      |     (Return Token ke FIFO) ---------+
      v
[Evaluasi Status Worker via wait -n]
      |
      v
[Seluruh Worker Selesai?] -- (No) -> Loop
      |
     (Yes)
      v
[Cleanup Semaphore & Dynamic FDs]
      |
      v
[Termination Script (Exit Code 0)]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konkurensi Bash vs Restoran Cepat Saji

*   **Parent Shell:** Manajer restoran. Ia tidak memasak sendiri, melainkan menerima pesanan dan mendelegasikan tugas.
*   **Subshell Asinkron (`&`):** Koki lepasan yang dipanggil untuk satu pesanan spesifik. Membawa salinan resep, bekerja di dapur terpisah (ruang memori COW), dan tidak memengaruhi buku resep manajer.
*   **File Descriptor (FD):** Pipa corong kabel pesanan. Manajer mengarahkan mikrofon (FD 1 - standard out) langsung ke telinga koki (FD 0 - standard in).
*   **Semaphore FIFO:** Gantungan tiket pesanan fisik. Jumlah pasak tiket terbatas. Jika 4 koki sedang bekerja dan pasak tiket kosong, koki berikutnya harus menunggu pasak tiket dikembalikan sebelum mulai memasak.

```
       [KERNEL VFS & DESCRIPTOR LAYER]
     
       +------------------------------------+
       |         Parent Process             |
       |  FD 0: stdin   -> /dev/pts/0       |
       |  FD 1: stdout  -> /dev/pts/0       |
       |  FD 2: stderr  -> /dev/pts/0       |
       |  FD 3: FIFO RD <- [/tmp/sem.pipe]  |
       |  FD 4: FIFO WR -> [/tmp/sem.pipe]  |
       +-----------------+------------------+
                         |
      +------------------+------------------+
      | fork()                              | fork()
      v                                     v
+------------------------+            +------------------------+
|  Worker Process 1      |            |  Worker Process 2      |
|  PID: 20451            |            |  PID: 20452            |
|  FD 0: /dev/null       |            |  FD 0: /dev/null       |
|  FD 1: Pipe WR [42] ---+            |  FD 1: Logfile.out     |
+------------------------+            +------------------------+
             |
             +---> Reads from Pipe [42] ---> Aggregator Daemon
```

---

## 7. Simple Example & Practical Example

### Simple Example: Non-Blocking Atomic Lock Menggunakan File Descriptor
Contoh mekanisme locking level kernel untuk mencegah proses dijalankan dua kali secara bersamaan (*double-run prevention*).

```bash
#!/usr/bin/env bash
# file: hands-on/m02/simple_lock.sh
set -Eeuo pipefail

LOCK_FILE="/var/lock/my_engine.lock"
mkdir -p "$(dirname "${LOCK_FILE}")"

# Buka file descriptor 200 untuk penulisan
exec 200>"${LOCK_FILE}"

# Lakukan eksklusif non-blocking lock via flock syscall
if ! flock -n 200; then
    echo "[-] [$(date '+%Y-%m-%dT%H:%M:%S%z')] Instance lain sedang berjalan. Abort!" >&2
    exit 1
fi

echo "[+] [$(date '+%Y-%m-%dT%H:%M:%S%z')] Lock berhasil didapatkan. Eksekusi tugas penting..."
sleep 5
echo "[+] Tugas selesai."
# FD 200 tertutup secara otomatis saat script selesai, melepaskan lock
```

### Practical Example: Production-Grade Parallel Job Engine
Script di bawah menerapkan: dynamic signal isolation, parallel worker pool menggunakan token FIFO, dynamic FD allocation, dan error collection agregat.

```bash
#!/usr/bin/env bash
# file: hands-on/m02/parallel_orchestrator.sh
# Enterprise Bounded Concurrency Orchestrator Engine

set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Config
readonly CONCURRENCY_LIMIT=4
readonly WORK_ITEMS=(
    "cluster-alpha:us-east-1"
    "cluster-bravo:eu-central-1"
    "cluster-charlie:ap-southeast-1"
    "cluster-delta:us-west-2"
    "cluster-echo:sa-east-1"
    "cluster-foxtrot:me-central-1"
    "cluster-golf:af-south-1"
    "cluster-hotel:eu-west-1"
)

# Runtime state
declare -a PIDS=()
SEMAPHORE_FIFO=""
SEM_READ_FD=0
SEM_WRITE_FD=0

# Logger terstruktur
log_info()  { echo "{\"level\":\"INFO\",\"timestamp\":\"$(date -u +%FT%TZ)\",\"msg\":\"$*\"}"; }
log_error() { echo "{\"level\":\"ERROR\",\"timestamp\":\"$(date -u +%FT%TZ)\",\"msg\":\"$*\"}" >&2; }

cleanup() {
    local exit_code=$?
    log_info "Membersihkan resource sistem..."
    
    # Kill worker yang masih tersisa dalam Process Group
    trap '' SIGTERM
    if [[ ${#PIDS[@]} -gt 0 ]]; then
        for pid in "${PIDS[@]}"; do
            if kill -0 "${pid}" 2>/dev/null; then
                log_info "Menghentikan worker aktif (PID: ${pid})..."
                kill -TERM "${pid}" 2>/dev/null || true
            fi
        done
        wait 2>/dev/null || true
    fi

    # Cleanup File Descriptors & FIFO
    if [[ -n "${SEM_READ_FD:-}" && "${SEM_READ_FD}" -gt 0 ]]; then
        exec {SEM_READ_FD}<&- || true
    fi
    if [[ -n "${SEM_WRITE_FD:-}" && "${SEM_WRITE_FD}" -gt 0 ]]; then
        exec {SEM_WRITE_FD}>&- || true
    fi
    if [[ -n "${SEMAPHORE_FIFO:-}" && -p "${SEMAPHORE_FIFO}" ]]; then
        rm -f "${SEMAPHORE_FIFO}"
    fi

    log_info "Engine dihentikan dengan status code: ${exit_code}"
    exit "${exit_code}"
}

trap cleanup EXIT
trap 'log_error "Menerima SIGINT! Membatalkan seluruh operasi..."; exit 130' SIGINT
trap 'log_error "Menerima SIGTERM! Membatalkan seluruh operasi..."; exit 143' SIGTERM

# Inisialisasi FIFO-based POSIX Semaphore
setup_semaphore() {
    local slots="$1"
    SEMAPHORE_FIFO="$(mktemp -u /tmp/orchestrator_sem.XXXXXX)"
    mkfifo -m 0600 "${SEMAPHORE_FIFO}"
    
    # Buka Read and Write terpisah via dynamic FD allocation
    exec {SEM_READ_FD}<"${SEMAPHORE_FIFO}"
    exec {SEM_WRITE_FD}>"${SEMAPHORE_FIFO}"
    
    # Hapus file dari filesystem namespace, FD tetap valid (VFS unlinked handle)
    rm -f "${SEMAPHORE_FIFO}"

    # Isi semaphore pool dengan token
    for ((i = 0; i < slots; i++)); do
        echo >&"${SEM_WRITE_FD}"
    done
}

# Worker implementation
execute_work_item() {
    local target="$1"
    local id="$2"
    local delay
    delay=$(( (RANDOM % 3) + 1 ))

    # Simulasi failure acak untuk stress-testing resilience
    if [[ "${target}" == "cluster-delta:us-west-2" ]]; then
        log_error "[Worker-${id}] Simulasi kegagalan transmisi pada target ${target}"
        return 2
    fi

    log_info "[Worker-${id}] Sinkronisasi node ${target} (Est: ${delay}s)..."
    sleep "${delay}"
    log_info "[Worker-${id}] Berhasil sinkronisasi node ${target}"
    return 0
}

# Main Execution Flow
main() {
    log_info "Memulai Orchestration Engine dengan limit paralel: ${CONCURRENCY_LIMIT}"
    setup_semaphore "${CONCURRENCY_LIMIT}"

    local worker_id=0
    local failure_detected=0

    for item in "${WORK_ITEMS[@]}"; do
        worker_id=$((worker_id + 1))
        
        # Ambil token dari FIFO (blocking jika antrean penuh)
        read -u "${SEM_READ_FD}"

        # Spawn child worker asinkron
        (
            set -Eeuo pipefail
            local worker_exit=0
            execute_work_item "${item}" "${worker_id}" || worker_exit=$?
            
            # Kembalikan token ke FIFO
            echo >&"${SEM_WRITE_FD}"
            exit "${worker_exit}"
        ) &

        local current_pid=$!
        PIDS+=("${current_pid}")
        log_info "Worker-${worker_id} di-spawn dengan PID: ${current_pid}"
    done

    # Tunggu seluruh worker selesai dan kumpulkan exit codes
    log_info "Seluruh tugas terdistribusi. Menunggu pipeline selesai..."
    for pid in "${PIDS[@]}"; do
        if ! wait "${pid}"; then
            log_error "Worker PID ${pid} exit dengan status failure!"
            failure_detected=1
        fi
    done

    if [[ ${failure_detected} -ne 0 ]]; then
        log_error "Eksekusi engine selesai dengan satu atau lebih task gagal."
        return 1
    fi

    log_info "Seluruh orchestrator tasks sukses 100%!"
    return 0
}

main "$@"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Zero-Downtime Blue/Green Load Balancer Switcher & Telemetry Reaper

*   **Environment:** Sebuah bank digital skala besar mengoperasikan gateway pembayaran dengan 32 node backend bare-metal. Deployment versi baru dilakukan dengan memutar rute NGINX *upstream targets* secara atomik.
*   **Masalah:** Deployment sebelumnya menggunakan script Bash konvensional yang mengeksekusi iterasi loop sekuensial via SSH. Jika satu server mengalami network timeout, script macet (*hanging indefinitely*), menyebabkan inkonsistensi versi (*split-brain state*). Sinyal pembatalan (Ctrl+C oleh operator) meninggalkan subshell orphan yang terus menjalankan deploy sebagian di remote node.
*   **Solusi Rekayasa:** Dibangun deployment orchestrator berbasis Bash 5 dengan karakteristik:
    1.  **Strict Global Connection Timeouts:** Menggunakan subshell terisolasi dengan alarm interrupt kernel via dynamic FDs.
    2.  **Atomic Dynamic Symlink Rollback:** Swap target socket secara atomik via `ln -sfn` dan `mv -T` yang dipicu via SSH multiplexed sockets (`ControlMaster`).
    3.  **Real-Time Subshell Health-check Aggregation:** Menggunakan FIFO dedicated untuk *event stream* real-time yang langsung diurai (*parsed*) oleh background monitoring loop.

```
                  [DEPLOYMENT ORCHESTRATOR]
                              |
       +----------------------+----------------------+
       |                      |                      |
[Fork: SSH Worker-01]  [Fork: SSH Worker-02]  [Fork: Event Aggregator]
 (ControlSocket Pool)   (ControlSocket Pool)         |
       |                      |                      |
  [Remote Node 1]        [Remote Node 2]             |
  (ln -sfn atomic)       (ln -sfn atomic)            |
       |                      |                      |
       +----------(Status Event Stream)------------->+
                              |                      |
                     [Evaluasi Status] <-------------+
                              |
               +--------------+--------------+
               | (Semua OK)                  | (Satu Gagal)
               v                             v
       [Commit NGINX Reload]         [Broadcast SIGTERM]
                                     [Atomic Rollback Trigger]
```

---

## 9. Trade-offs (Architectural Decisions)

| Dimensi | Native Bash Subshell Concurrency | Biner Terkompilasi (Go / Rust) | Eksternal Tools (`xargs -P` / GNU Parallel) |
| :--- | :--- | :--- | :--- |
| **Footprint / Dependency** | **Nol:** Langsung jalan di base OS terkecil tanpa kompilasi atau install runtime. | **Tinggi:** Perlu kompilasi biner untuk arch spesifik target (cross-compilation). | **Sedang:** Membutuhkan instalasi package GNU Parallel atau coreutils modern. |
| **Performance Overhead** | **Tinggi:** Setiap worker melakukan `fork()` penuh (duplikasi page table OS & setup runtime Bash). | **Sangat Rendah:** Menggunakan micro-threads / green-threads (*goroutine*) dalam satu memory space. | **Tinggi:** Setiap item memicu `fork()` + `execve()` biner baru secara berulang. |
| **Memory Isolation** | **Mutlak:** Kernel mengisolasi memory space antar worker secara terpisah via virtual memory COW. | **Terkontrol:** Memory dishare, rentan memory race condition jika locking primitif salah. | **Mutlak:** Proses terpisah total tanpa memory sharing. |
| **IPC Complexity** | **Tinggi:** Terbatas pada Stream FDs, Named Pipes (FIFO), Signal, atau Unix Domain Sockets. | **Sangat Rendah:** Channel native memory, shared sync primitive, mutexes. | **Sangat Terbatas:** Hanya menangkap exit code, stdout, dan stderr. |
| **Failure Blast Radius** | **Rendah:** Crash pada satu worker tidak mematikan parent jika trap diisolasi. | **Kritis:** Panic yang tidak di-*recover* dapat merobohkan seluruh instance application. | **Rendah:** Kegagalan child otomatis dilaporkan kembali via exit code. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Zombie Ingestion Explosion
*   **Kesalahan:** Mengabaikan child process dalam background loop terus menerus (`while true; do worker & done`) tanpa `wait`.
*   **Dampak:** Process table kernel (dibatasi oleh `/proc/sys/kernel/pid_max`) penuh dengan entri zombie (`defunct`). Sistem menolak alokasi proses baru (`fork: Resource temporarily unavailable`).
*   **Troubleshooting:** Periksa kolom `STAT` pada `ps aux | grep Z`. Selesaikan dengan menambahkan loop `wait -n` untuk membersihkan return code anak saat mereka mati.

### 2. Silent Pipeline Masking (`pipefail` Failure)
*   **Kesalahan:** Menjalankan `set -e` tanpa `set -o pipefail`.
    ```bash
    set -e
    curl -f https://internal.repo/package.tar.gz | tar -xzf -
    ```
*   **Dampak:** Jika `curl` gagal (misal 404 Not Found), pipeline secara keseluruhan tetap menghasilkan exit code `0` karena proses terakhir (`tar`) berhasil menangani EOF kosong atau crash tanpa menghentikan script, menyamarkan kegagalan build.
*   **Troubleshooting:** Selalu deklarasikan `set -Eeuo pipefail` di baris pertama seluruh script produksi.

### 3. Circular Dependency pada Bash 4.4 Namerefs
*   **Kesalahan:** Mendeklarasikan nameref (`declare -n`) yang mereferensikan variabel dengan nama yang sama di scope lokal.
    ```bash
    mutate_data() {
        declare -n ref="$1"
        ref="modified_${ref}" # Error jika parameter $1 adalah "ref"
    }
    mutate_data "ref" # Memicu: bash: warning: ref: circular name reference
    ```
*   **Dampak:** Shell crash atau infinite variable resolution loop.
*   **Troubleshooting:** Gunakan konvensi penamaan nameref dengan prefix unik: `declare -n __mutate_target_ref="$1"`.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa (*checklist*) berikut sebelum merilis script Bash ke production:

* [ ] **The Holy Trinity Initialization:** Mengaktifkan strict mode di baris paling atas:
  ```bash
  set -Eeuo pipefail
  IFS=$'\n\t'
  ```
* [ ] **Signal Trap Cleanup:** Memastikan trap `EXIT`, `SIGINT`, dan `SIGTERM` terdaftar untuk menghapus temp files, directory, dan child background jobs.
* [ ] **Deterministic Paths:** Hindari path relatif. Inisialisasi root path absolut menggunakan:
  ```bash
  readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  ```
* [ ] **Explicit Variable Scoping:** Semua variabel dalam fungsi wajib dideklarasikan menggunakan `local` atau `local -r` (read-only). Variabel global wajib menggunakan `declare -r` atau `readonly`.
* [ ] **Avoid Useless `cat` and Forks:** Gunakan *parameter expansion* internal Bash daripada memanggil utility eksternal seperti `sed`, `awk`, atau `cut` untuk manipulasi string sederhana.
* [ ] **Subshell Isolation Audit:** Pastikan operasi yang memodifikasi state direktori (`cd`) selalu dijalankan dalam subshell `( cd /path && make )` agar tidak mencemari runtime parent directory.
* [ ] **Dynamic File Descriptor Sanitization:** Tutup seluruh file descriptor non-standar yang dibuka via `exec {fd}>...` sebelum memanggil script/biner eksternal agar FD tidak bocor (*leaked descriptors*).
* [ ] **Static Analysis Validation:** Script harus lolos validasi `shellcheck -s bash -S error` tanpa peringatan.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

### Skenario Praktikum:
Bangun sistem ingestion log terdistribusi yang memproses stream log mentah secara paralel, mengompresinya secara asinkron, dan melaporkan ringkasan ukuran secara atomik tanpa *race condition*.

#### Langkah 1: Persiapan Direktori Kerja
```bash
mkdir -p hands-on/m02/{input,output,processed}
cd hands-on/m02/
```

#### Langkah 2: Buat Data Mock Dummy
```bash
for i in {1..20}; do
    head -c "$(( (RANDOM % 500 + 100) * 1024 ))" /dev/urandom > "input/access_log_${i}.log"
done
```

#### Langkah 3: Implementasi Script Compressor Paralel
Buat file `hands-on/m02/stream_compressor.sh` dengan isi berikut:

```bash
#!/usr/bin/env bash
# file: hands-on/m02/stream_compressor.sh
set -Eeuo pipefail

readonly MAX_WORKERS=3
readonly INPUT_DIR="./input"
readonly OUTPUT_DIR="./output"

# Trap handling
cleanup() {
    local code=$?
    echo "[!] Membersihkan worker background..."
    jobs -p | xargs -r kill 2>/dev/null || true
    rm -rf "${FIFO_NAME:-}"
    exit "${code}"
}
trap cleanup EXIT INT TERM

# Buat FIFO untuk antrean
FIFO_NAME="$(mktemp -u)"
mkfifo "${FIFO_NAME}"
exec 9<>"${FIFO_NAME}"
rm -f "${FIFO_NAME}"

# Isi token
for ((i=0; i<MAX_WORKERS; i++)); do
    echo "token" >&9
done

echo "[*] Memulai kompresi paralel stream..."

for file in "${INPUT_DIR}"/*.log; do
    [[ -f "${file}" ]] || continue
    
    # Tunggu giliran slot token
    read -u 9 _

    (
        set -euo pipefail
        base_name="$(basename "${file}")"
        echo "[+] [PID: $BASHPID] Mulai memproses: ${base_name}"
        
        # Simulasi kompresi dengan verifikasi integritas
        gzip -c "${file}" > "${OUTPUT_DIR}/${base_name}.gz"
        
        # Kembalikan token
        echo "token" >&9
        echo "[-] [PID: $BASHPID] Selesai: ${base_name}.gz"
    ) &
done

# Tunggu seluruh proses selesai
wait
echo "[SUCCESS] Seluruh file log berhasil dikompresi."
```

#### Langkah 4: Eksekusi dan Verifikasi
```bash
chmod +x hands-on/m02/stream_compressor.sh
./hands-on/m02/stream_compressor.sh
ls -lh hands-on/m02/output/
```

---

## 13. Exercises

### Level: Easy
Modifikasi script `hands-on/m02/stream_compressor.sh` untuk menghasilkan output status ringkasan:
1. Hitung total bytes sebelum kompresi dan sesudah kompresi.
2. Hitung persentase kompresi keseluruhan.
*Batasan:* Eksekusi perhitungan tanpa menggunakan utilitas eksternal seperti `python` atau `perl` (Gunakan manipulasi integer Bash dan utilitas POSIX bawaan).

### Level: Medium
Buat script Bash `hands-on/m02/circuit_breaker.sh` yang menjalankan monitoring terhadap HTTP endpoint (bisa dimock dengan `nc -l`).
1. Jalankan worker di background setiap 1 detik.
2. Jika endpoint gagal merespons selama 3 kali beruntun, ubah state menjadi `OPEN` dan hentikan pengiriman request selama 10 detik.
3. Setelah 10 detik, ubah ke state `HALF-OPEN` dan kirim 1 probe request.
4. Tangani sinyal `SIGHUP` untuk me-reload file konfigurasi tanpa menghentikan status circuit breaker saat ini.

### Level: Hard
Rancang script engine antrean terdistribusi lokal: `hands-on/m02/distributed_queue.sh`.
1. Gunakan Unix Domain Socket murni yang diekspos melalui `nc -l -U /tmp/queue.sock`.
2. Script harus memiliki proses *Master* yang membuka socket tersebut dan menerima payload JSON event dari berbagai script client Bash independen.
3. Master mem-parsing JSON payload secara native dan mendistribusikan task ke worker pool dengan batasan memori maksimum (monitor via `/proc/$PID/statm`).
4. Jika worker menggunakan memori melebihi ambang batas (*threshold*) yang ditentukan, Master mengirimkan `SIGTERM` secara tertib, menunggu data disimpan, dan me-restart worker baru.

---

## 14. Challenge

### Arsitektur Zero-Loss Transactional Event Buffer Engine
Sebuah sistem telemetri IoT edge gateway menghasilkan puluhan ribu string metriks per menit via stdout. Anda diminta merancang arsitektur Bash berkinerja tinggi tanpa menggunakan perantara middleware seperti Redis atau RabbitMQ.

#### Persyaratan Arsitektur:
1.  **High Throughput & Low Latency:** Bash script harus menerima continuous stdin stream, mengelompokkannya (*batching*) per 1000 record atau interval 500ms (mana yang tercapai lebih dulu).
2.  **Backpressure & Resilience:** Jika disk write I/O tersedak (*choked*), buffer memory-resident di Bash harus membatasi diri maksimal 100MB agar OOM-Killer Linux tidak mematikan sistem gateway. Jika limit tercapai, aktifkan mekanisme *drop-oldest* dengan mencatat total drop counter.
3.  **Crash Recovery:** Jika script menerima sinyal `SIGKILL` mendadak dari power failure, pada saat *cold boot* pertama kali, engine harus melakukan deteksi parsing recovery pada temporary state files untuk memastikan data tidak terkorupsi (*atomic rename swapping*).
4.  **No High-Level Runtimes:** Dilarang menggunakan runtime non-shell (Python, Ruby, Node, Java, Go). Hanya Bash v4/v5, kernel interfaces (`/dev/`, `/proc/`, `/sys/`), dan biner POSIX low-level.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pemahaman Konsep Dasar (5 Pertanyaan)

1. **Apa perbedaan mendasar antara eksekusi perintah via `( cmd )` vs `{ cmd; }` di Bash?**
   * A. `{ cmd; }` mengeksekusi perintah di subshell baru; `( cmd )` mengeksekusinya di current shell process.
   * B. `( cmd )` melakukan syscall `clone()/fork()` untuk membuat subshell environment; `{ cmd; }` dieksekusi di context current shell tanpa subshell spawn.
   * C. `( cmd )` memisahkan alokasi stdin/stdout; `{ cmd; }` tidak dapat dialihkan I/O-nya.
   * D. Tidak ada perbedaan sama sekali, keduanya hanyalah preferensi sintaks penulisan blok.

2. **Kapan kondisi di mana opsi `set -e` GAGAL menghentikan script Bash saat sebuah perintah menghasilkan exit code non-zero?**
   * A. Saat perintah tersebut dieksekusi di root user (`UID 0`).
   * B. Saat perintah dijalankan sebagai bagian dari kondisi pengujian percabangan (seperti klausa `if`, `while`, atau operand kiri operator `||`).
   * C. Saat perintah diarahkan ke `/dev/null`.
   * D. Saat panjang karakter perintah melebihi 256 karakter.

3. **Mengapa penulisan syntax pipeline `cmdA | cmdB` berpotensi menyebabkan race condition pada variabel global?**
   * A. Karena kernel Linux mengacak prioritas alokasi thread antara dua biner.
   * B. Karena secara default Bash mengeksekusi kedua perintah dalam subshell terpisah secara konkuren, sehingga mutasi variabel di `cmdB` tidak pernah mencapai parent environment.
   * C. Karena `pipe(2)` membersihkan (*clears*) entire environmental namespace sebelum pembacaan data.
   * D. Karena Bash menunda eksekusi `cmdA` sampai `cmdB` melepaskan memory lock.

4. **Apa fungsi dari system call `dup2(oldfd, newfd)` yang dipanggil Bash pada proses redireksi file descriptor?**
   * A. Menghapus tabel alokasi file descriptor lama dan menggantinya dengan disk buffer baru.
   * B. Mengalokasikan memori pointer baru untuk proses anak.
   * C. Menggandakan descriptor `oldfd` ke `newfd`, menutup `newfd` terlebih dahulu jika sebelumnya sedang terbuka, sehingga stream terhubung atomik.
   * D. Mengirimkan sinyal asinkron `SIGCHLD` ke kernel.

5. **Apa yang terjadi ketika sinyal `SIGINT` dikirimkan ke parent shell saat biner foreground non-builtin sedang dieksekusi?**
   * A. Parent shell langsung terminate seketika dan meninggalkan biner anak berjalan di background tanpa kontrol.
   * B. Parent menunda eksekusi trap handler hingga biner foreground selesai atau mati akibat menerima sinyal yang sama dalam process group-nya.
   * C. Kernel menghentikan swap memory parent process secara permanen.
   * D. Bash parent mengabaikan seluruh sinyal secara otomatis kecuali `SIGKILL`.

---

### Bagian B: Pemahaman Tingkat Lanjut (5 Pertanyaan)

6. **Bagaimana mekanisme `shopt -s lastpipe` memengaruhi arsitektur eksekusi pipeline di Bash, dan apa persyaratannya?**
   * A. Mengeksekusi pipeline dari kanan ke kiri; Job Control harus selalu aktif (`set -m`).
   * B. Memaksa elemen terakhir dari pipeline dijalankan dalam current shell process (bukan subshell), asalkan Job Control dalam keadaan nonaktif (`set +m`).
   * C. Menyimpan output pipeline terakhir ke dalam circular memory cache Linux kernel.
   * D. Mengabaikan return error pada pipeline terakhir secara absolut.

7. **Pada Bash 4.3+, apa risiko arsitektural penggunaan dynamic namerefs (`declare -n var=$target`) dalam fungsi rekursif?**
   * A. Nameref dapat memicu memory leak permanen yang tidak dapat di-reclaim oleh Linux kernel.
   * B. Jika nama variabel lokal nameref sama dengan nilai string yang dirujuk dari scope pemanggil, Bash mendeteksi circular reference dan melempar *fatal name resolution warning/error*.
   * C. Variabel nameref selalu mengubah atribut variabel menjadi read-only secara otomatis.
   * D. Nameref mematikan inheritance option `set -e` di dalam scope fungsi lokal.

8. **Mengapa konstruksi semaphore berbasis Anonymous FIFO (`mkfifo` lalu `rm`) tetap valid digunakan antar worker process yang di-fork?**
   * A. Karena file FIFO tetap tersimpan di disk cache OS meskipun inode metadata telah dihapus dari VFS namespace.
   * B. Karena file descriptor terbuka yang merujuk pada pipe file table di Linux kernel tetap valid selama proses yang memegang open handle belum menutupnya via `close()`.
   * C. Karena Bash menyalin byte FIFO langsung ke segmen `data` proses anak saat `fork()`.
   * D. Karena memory virtual Bash mengemulasi FIFO menggunakan shared memory segment POSIX (`shm_open`).

9. **Jika background process diluncurkan dengan `&` dan parent shell dihentikan via `SIGTERM`, mengapa child process sering kali tetap hidup sebagai orphan process?**
   * A. Karena `SIGTERM` secara default tidak dipropagasikan oleh shell parent ke asynchronous child processes yang memiliki detach status kecuali ditangani secara eksplisit via custom trap.
   * B. Karena kernel Linux menolak mengirim sinyal ke background tasks.
   * C. Karena child background tasks otomatis dipindahkan PGID-nya ke PID 0.
   * D. Karena background process memegang unlinked descriptor yang mencegah sinyal OS masuk.

10. **Apa implikasi performa dari penggantian utilisasi external subshell `VAR=$(echo $STR | cut -d: -f1)` dengan Bash Parameter Expansion `${STR%%:*}` dalam loop 100.000 iterasi?**
    * A. Performa identik karena kernel Linux mengoptimasi command substitution secara native.
    * B. Parameter Expansion ratusan kali lebih cepat karena tidak melakukan syscall `clone()`, `fork()`, `execve()`, setup memory COW, dan context switching CPU.
    * C. Parameter Expansion lebih lambat karena diimplementasikan di layer user space tanpa GCC vectorization.
    * D. Command substitution lebih hemat memori karena subshell membersihkan cache RAM seketika saat exit.

---

### Bagian C: Pemecahan Masalah Kasus Produksi (3 Skenario)

11. **Skenario 1:** Sebuah script deployment pipeline menjalankan pengujian integrasi database dengan template berikut:
    ```bash
    set -e
    find ./tests -name "*.sh" | while read test_script; do
        bash "${test_script}"
        TOTAL_RUN=$((TOTAL_RUN + 1))
    done
    echo "Total tests run: ${TOTAL_RUN}"
    ```
    Di log sistem, script selalu mencetak: `Total tests run: 0`, meskipun 50 test script berhasil dieksekusi. Selain itu, jika satu test gagal (exit code 1), script deployment tetap sukses melaju ke tahap berikutnya. Analisis akar penyebab sistemik dari kedua bug ini dan bagaimana Anda memperbaikinya secara definitif!

12. **Skenario 2:** Anda memiliki script daemon pemroses antrean yang menggunakan `flock` pada file descriptor 9. Sistem berjalan mulus selama berbulan-bulan sampai suatu hari tim developer menambahkan pemanggilan utility backup database eksternal:
    ```bash
    exec 9>"/var/lock/worker.lock"
    flock -n 9 || exit 1
    # ... logic internal ...
    /opt/vendor/backup-agent &
    # ...
    ```
    Setelah itu, ketika script worker daemon di-restart secara terjadwal oleh systemd, script selalu gagal dengan error locking (`Instance already running`), meskipun process daemon utama jelas sudah mati. Mengapa lock file tersebut masih tertahan (*locked*), dan modifikasi arsitektur apa yang wajib dilakukan?

13. **Skenario 3:** Sebuah batch orchestrator memproses 500 file secara paralel menggunakan subshell background `process_file &`. Untuk mencegah kehabisan kapasitas server, digunakan logika penjagaan jumlah proses aktif:
    ```bash
    while [ $(jobs -r | wc -l) -ge 16 ]; do
        sleep 0.1
    done
    ```
    Ketika beban load data tinggi, sistem mendadak mengalami *freezing* total, CPU usage 100%, dan script berhenti memproses file baru. Analisis kelemahan desain dari arsitektur loop monitor ini dan jelaskan pola arsitektur pengganti yang *kernel-friendly*!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A & B
1. **B** — Explicit parenthesis `( )` mengeksekusi subshell baru via `clone()/fork()`, sedangkan curly braces `{ }` adalah grouping syntax pada current process context.
2. **B** — Desain POSIX menetapkan `set -e` diabaikan jika command dieksekusi sebagai bagian dari part of test context (`if`, `while`, `until`, `&&`, `||`).
3. **B** — Elemen pipeline dijalankan secara konkuren dalam subshell isolated process; mutasi variabel di dalam child tidak mengubah parent environment.
4. **C** — `dup2` mengalihkan slot descriptor target secara atomik dan menutup file stream yang telah ada sebelumnya jika terpasang.
5. **B** — Desain internal POSIX signal handling pada shell: parent memblok/menunda pemanggilan trap signal-nya hingga child proses foreground selesai dieksekusi.
6. **B** — `shopt -s lastpipe` menjalankan child pipeline terakhir di current process shell hanya jika job control dinonaktifkan (`set +m`).
7. **B** — Resolusi nameref yang mengarah ke variabel bernama serupa di scope lokal fungsi memicu fatal circular reference.
8. **B** — Struktur VFS kernel Linux memelihara inode open file description selama reference count descriptor table $> 0$, meski nama file di directory dihapus via unlinking.
9. **A** — Job background yang diasumsikan asynchronous tidak otomatis menerima termination cascade dari parent shell kecuali sinyal ditangkap dan disebarkan manual via process group/PID trap tracking.
10. **B** — Parameter expansion murni internal Bash string evaluator; tidak memicu context switch CPU, `fork`, `execve`, maupun alokasi page memory baru.

#### Bagian C (Kasus Produksi)
11. **Analisis Akar Masalah:**
    *   *Bug 1 (Variabel Hilang):* Pipeline `find ... | while` memaksa loop `while` berjalan di subshell anak terpisah. Modifikasi terhadap `TOTAL_RUN` hanya mengubah virtual memory child process tersebut dan lenyap ketika subshell terminasi.
    *   *Bug 2 (Masking Error):* Kegagalan pada biner `test_script` di dalam `while` tidak menggugurkan eksekusi keseluruhan karena status exit code pipeline ditentukan oleh statement `find`, dan opsi `pipefail` tidak aktif.
    *   *Solusi Komprehensif:*
        Gunakan Process Substitution agar loop berjalan di current environment dan pasang strict mode:
        ```bash
        set -Eeuo pipefail
        TOTAL_RUN=0
        while IFS= read -r -d '' test_script; do
            bash "${test_script}"
            TOTAL_RUN=$((TOTAL_RUN + 1))
        done < <(find ./tests -name "*.sh" -print0)
        echo "Total tests run: ${TOTAL_RUN}"
        ```

12. **Analisis Akar Masalah:**
    *   File descriptor yang dibuka di shell parent (`exec 9>...`) secara default mewariskan status descriptor handle ke child processes yang di-spawn tanpa flag `FD_CLOEXEC`.
    *   Saat `/opt/vendor/backup-agent &` dieksekusi di background, ia melakukan *inherit* terhadap FD 9 milik parent. Ketika process daemon utama dimatikan oleh systemd, child process backup agent tersebut masih aktif dan masih memegang FD 9 terbuka. Kernel Linux menganggap lock `flock` masih aktif hingga seluruh proses yang memegang handle FD 9 mati.
    *   *Solusi Arsitektur:*
        Tutup akses file descriptor secara eksplisit sebelum melempar job ke background:
        ```bash
        /opt/vendor/backup-agent 9>&- &
        ```
        Atau alokasikan flag close-on-exec pada FD jika didukung tooling lokal.

13. **Analisis Akar Masalah:**
    *   Pola `while [ $(jobs -r | wc -l) -ge 16 ]; do sleep 0.1; done` adalah polling loop aktif yang sangat mahal. Setiap 100ms, Bash memicu 2 kali syscall `clone()/fork()` (`jobs` subshell dan `wc`), setup pipe, serta context switch CPU.
    *   Pada load tinggi, system mengalami *process starvation* dan IO thrashing hanya untuk memeriksa jumlah worker. Jika worker mati di antara evaluasi subshell, monitoring parsing strings berpotensi meleset.
    *   *Solusi Arsitektur:*
        Gantikan *busy-wait polling loop* tersebut dengan *event-driven architecture*:
        1. Gunakan Anonymous FIFO POSIX Token Semaphore (seperti di Practical Example Bagian 7), di mana script memblok secara native di level system call kernel `read()` tanpa looping konsumsi CPU, ATAU
        2. Gunakan Bash built-in `wait -n` (menunggu sembarang satu child process selesai dan melepaskan slot secara instan tanpa subshell overhead).

---

## 16. Summary

Pengembangan sistem Bash tingkat enterprise menuntut pergeseran paradigma dari sekadar menyusun baris perintah (*shell scripting*) menjadi pemahaman arsitektur rekayasa sistem (*systems engineering*). Dengan menguasai mekanisme internal Linux Kernel—seperti siklus `fork-exec`, mitigasi Copy-On-Write, isolasi memori virtual subshell, plumbing File Descriptors, dan propagasi sinyal proses—seorang perekayasa perangkat lunak dapat membangun pipeline orkestrasi yang efisien, tangguh (*fault-tolerant*), dan berkinerja tinggi.

Kunci keandalan Bash pada sistem produksi skala besar terletak pada penerapan konvensi defensif yang disiplin:
1. Menjaga integritas eksekusi melalui **Strict Modes** (`-Eeuo pipefail`).
2. Menghilangkan ketergantungan *busy-polling* dengan beralih ke sinkronisasi berbasis *kernel-blocking* (FIFO Semaphores, `wait -n`).
3. Mengamankan alokasi resource via **Dynamic File Descriptors** dan **Deterministic Cleanups Trap**.

Ketika batasan komputasi algoritma dan struktur data kompleks Bash tercapai, integrator sistem harus membatasi peran Bash secara presisi: bukan sebagai engine komputasi data masif, melainkan sebagai orkestrator proses (*glue technology*) kelas wahid yang memanfaatkan keandalan sistem operasi secara maksimal.