# BAB 05: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Runtime Bash:** Memahami interaksi tingkat rendah antara Bash, kernel Linux, Virtual File System (VFS), Process Table, dan alokasi File Descriptor (FD).
2. **Mengimplementasikan Concurrency & Synchronization Tingkat Lanjut:** Membangun *worker pool* paralel terkontrol menggunakan semafor berbasis Named Pipe (FIFO) dan *mutual exclusion lock* menggunakan syscall `flock(2)`.
3. **Mendesain Deterministic Error Handling & Diagnostics:** Mengimplementasikan *stack trace* otomatis saat runtime crash dengan memanfaatkan array `BASH_SOURCE`, `FUNCNAME`, dan `BASH_LINENO` serta trapping signal terpadu (`EXIT`, `ERR`, `SIGINT`, `SIGTERM`).
4. **Mengelola Alokasi File Descriptor Kustom:** Mengalokasikan, mengarahkan, dan menutup File Descriptor non-standar (FD 3 hingga 9) untuk isolasi aliran logging, telemetri, dan I/O *inter-process communication* (IPC).
5. **Membangun Daemon/Worker Shell Standar Enterprise:** Memproduksi skrip otomasi yang *idempotent*, *fault-tolerant*, dan siap dideploy pada infrastruktur Mission-Critical (CI/CD runner, container bootstrap, bare-metal orchestrator).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Fundamental POSIX shell: conditional logic, perulangan, fungsi dasar, array satu dimensi.
* Konsep dasar sistem operasi Linux: PID, PPID, process state (`R`, `S`, `Z`), environment variables, dan permission file POSIX.
* I/O redirection standar: stdin (`0`), stdout (`1`), stderr (`2`), pipes (`|`).
* Pengetahuan dasar tentang POSIX signals (`SIGINT`, `SIGTERM`, `SIGKILL`, `SIGHUP`).

---

### 3. Concept & Internal Architecture

Bash bukan sekadar interpreter string perintah berurutan; ia adalah runtime eksekusi proses yang berinteraksi langsung dengan antarmuka syscall kernel Linux (`clone`, `fork`, `execve`, `pipe`, `dup2`, `flock`, `kill`).

```
                    +---------------------------------------------------+
                    |                Bash Parent Process                |
                    |                   (PID: 10001)                    |
                    +---------------------------------------------------+
                    | File Descriptor Table:                            |
                    | 0: stdin, 1: stdout, 2: stderr                    |
                    | 3: Custom Read (Config)                           |
                    | 4: Custom Write (Metrics Stream)                  |
                    | 9: flock mutex handle (/var/lock/app.lock)        |
                    +---------------------------------------------------+
                               |                      |
            fork() / clone()   |                      |  pipe() / mkfifo
                               v                      v
        +----------------------------+      +---------------------------+
        |  Subshell / Child Process  |      |   Worker Pool Semaphore   |
        |        (PID: 10002)        |      |       (Named Pipe)        |
        +----------------------------+      +---------------------------+
        | Isolated Memory Segment    |      | Token Buffer (Fixed size) |
        | Copy-on-Write (COW)        |      | Byte read == Slot Claimed |
        | Inherited FDs (0..4, 9)    |      | Byte written == Released  |
        +----------------------------+      +---------------------------+
```

#### A. File Descriptor Architecture dan `dup2`
Linux mengekspos setiap stream I/O sebagai representasi integer dalam File Descriptor Table per proses yang merujuk pada `struct file` di kernel memory.
* Secara default: `0` (stdin), `1` (stdout), `2` (stderr).
* Bash mengizinkan alokasi manual FD `3` sampai `9` melalui sintaks `exec {fd}>file` atau `exec 3>file`.
* Syscall `dup2(oldfd, newfd)` digunakan oleh Bash saat melakukan redirection `2>&1` atau `exec 3>&1`. Ketika FD diarahkan, tabel proses mengalihkan pointer target VFS tanpa menghentikan eksekusi thread parser shell.

#### B. Subshell, Memory Isolation, dan Fork-Exec Cost
Setiap kali kurung `( ... )`, pipeline `cmd1 | cmd2`, atau background execution `&` dipanggil:
1. Kernel melakukan syscall `fork()` (atau `clone()` dengan flag tertentu).
2. Terbentuk proses anak (*child process*) dengan memory space yang terisolasi dari parent process.
3. Modifikasi variabel, array, atau state shell di dalam subshell **tidak akan pernah** terpropagasi kembali ke parent process karena sifat memori *Copy-on-Write* (COW).
4. Overhead `fork()` + `execve()` berulang dalam loop ribuan iterasi dapat membebani CPU kernel scheduling. Skrip kelas enterprise meminimalkan pemanggilan subshell eksternal dan memanfaatkan *Bash builtins* semaksimal mungkin.

#### C. Signal Trapping Engine
Ketika sinyal OS diterima (misal `SIGTERM` saat shutdown pod Kubernetes), kernel menginterupsi eksekusi thread interpreter Bash. Bash menyimpan antrean sinyal (*signal queue*) dan menunda eksekusi *signal handler* hingga instruksi internal yang sedang berjalan selesai, kecuali sinyal tersebut didaftarkan melalui command `trap`. 
Penggunaan trap `ERR` dan `EXIT` memungkinkan eksekusi deterministik:
* Trap `EXIT` dieksekusi saat skrip berhenti secara normal ataupun abnormal.
* Trap `ERR` dieksekusi secara instan ketika ada perintah yang mengembalikan exit code non-zero (apabila `set -e` atau `set -E` aktif).

#### D. Mutual Exclusion via `flock(2)`
Bash runtime rentan terhadap *race condition* jika beberapa skrip berjalan bersamaan mengakses resource yang sama (misal state disk atau file log). Syscall `flock(2)` mengunci *inode open file table entry* di level kernel, menjamin sinkronisasi proses yang aman bahkan jika proses shell crash secara tiba-tiba (kernel otomatis melepas *advisory lock* saat FD ditutup atau proses mati).

---

### 4. Why & What

| Dimensi | Skrip Bash Konvensional (Ad-hoc) | Skrip Bash Kelas Produksi (Enterprise-grade) |
| :--- | :--- | :--- |
| **Error Handling** | Mengabaikan exit code, rentan *silent failure*. | `set -Eeuo pipefail`, custom stack trace dump saat crash. |
| **Eksekusi Paralel** | Eksekusi satu per satu atau `cmd &` massal tanpa batas, berisiko *OOM kill*. | Concurrency terkontrol via Semaphore (FIFO) dengan batas kapasitas *worker*. |
| **Pembersihan Resource** | File sementara sering tertinggal jika skrip di-kill (`SIGTERM`). | *Exit traps* deterministik membersihkan PID, socket, FIFO, dan lock. |
| **Locking Mechanism** | Memeriksa eksistensi file (`if [ -f /tmp/lock ]`), memicu *race condition*. | Atomic locking via `flock` terikat pada File Descriptor dedicated. |
| **Logging & Telemetri**| `echo "message"` campur aduk antara stdout & stderr. | Structured logging terisolasi via File Descriptor kustom (misal FD 3 & 4). |

**Kapan Harus Menggunakan Bash Tingkat Lanjut?**
* **Deployment & Container Entrypoints:** Menyiapkan initialization hook Kubernetes, runtime bootstrapping, dan service mesh agent di mana runtime Python/Node/Go tidak tersedia pada distroless/minimal image.
* **Low-Footprint Systems Orchestrator:** Sistem automasi bare-metal, edge devices, atau instalasi OS awal (PXE boot, preseed) yang memiliki dependensi nol.

---

### 5. How (Workflow Detail)

Alur kerja arsitektur runtime skrip enterprise:

```
[ Inisialisasi Environment & Strict Mode ]
                   |
                   v
[ Akuisisi Mutex Lock via flock (FD 9) ] ---- (Gagal) ---> [ Abort / Wait Queue ]
                   | (Berhasil)
                   v
[ Registrasi Trap Handlers (EXIT, ERR, SIGTERM, SIGINT) ]
                   |
                   v
[ Inisialisasi Custom FD (FD 3: Metrics, FD 4: Audit) ]
                   |
                   v
[ Alokasi IPC FIFO Semaphore (Worker Pool Limit: N) ]
                   |
                   v
[ Iterasi Task Queue: Fork Worker Background Process ]
                   |
                   v
[ Wait All Workers & Capture Exit Codes ]
                   |
                   v
[ Deterministik Cleanup Trap (Unlink FIFO, Release Locks, Close FDs) ]
                   |
                   v
[ Safe Exit Status ]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan terminal bandara internasional dengan banyak jalur lepas landas:
* **Subshell:** Landasan pacu terpisah. Jika sebuah pesawat di Runway A mengalami masalah mesin, pesawat di Runway B tidak langsung meledak, namun keduanya bergantung pada menara pengawas yang sama.
* **File Descriptors (FD):** Saluran radio komunikasi terdedikasi. Saluran 1 untuk koordinasi publik (stdout), Saluran 2 untuk alarm marabahaya (stderr), Saluran 3 untuk telemetri bahan bakar (Metrics).
* **Semaphore (FIFO):** Pintu gerbang *boarding pass*. Hanya ada 4 petugas (token). Penumpang (tugas) berikutnya tidak boleh masuk ke landasan pacu sebelum salah satu penumpang yang sedang diproses mengembalikan stempel ke meja petugas.

```
                   +---------------------------------------+
                   |         SEMAPHORE QUEUE (FIFO)        |
                   | Tokens: [x] [x] [x] [x]  (Max: 4 Job) |
                   +---------------------------------------+
                                  ^         |
               read (consume slot)|         | write (release slot)
                                  |         v
             +--------------------+-------------------------+
             |                                              |
      +---------------+                              +---------------+
      | Child Job #1  |                              | Child Job #2  |
      |   (Running)   |                              |   (Running)   |
      +---------------+                              +---------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Dynamic File Descriptor Allocation & Diagnostics
Contoh ini mendemonstrasikan bagaimana mengalokasikan File Descriptor kustom untuk memisahkan log audit dari log output standar aplikasi.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Alokasikan file descriptor kustom (FD 3) yang merujuk ke file audit
AUDIT_LOG="/tmp/audit_event.log"
exec 3>"${AUDIT_LOG}"

# Mengirim output langsung ke FD 3 tanpa mencemari stdout
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] SYSTEM_INIT User=${USER}" >&3

# Output standar aplikasi
echo "Aplikasi berjalan normal..."

# Mengirim event penting lainnya ke FD 3
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] TASK_COMPLETED Status=OK" >&3

# Tutup FD 3 secara eksplisit
exec 3>&-

echo "Audit log tersimpan di ${AUDIT_LOG}:"
cat "${AUDIT_LOG}"
```

---

#### B. Practical Example: Production-Grade Parallel Worker Pool & Trap Engine
Skrip berikut mengimplementasikan paralelisme terkontrol via Named Pipe Semaphore, isolasi mutex via `flock`, penanganan sinyal deterministik, dan stack trace dumper komprehensif saat runtime crash.

Simpan skrip berikut dengan nama `parallel_worker_engine.sh`:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name : parallel_worker_engine.sh
# Description : Robust parallel task execution engine with concurrency limits,
#               atomic locking, isolated logging FDs, and deep stack tracing.
# ==============================================================================

# 1. ENFORCE STRICT RUNTIME EXECUTION
set -Eeuo pipefail
IFS=$'\n\t'

# 2. GLOBAL CONSTANTS & MUTEX PATHS
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOCK_FILE="/var/lock/${SCRIPT_NAME%.*}.lock"
readonly SEMAPHORE_FIFO="/tmp/${SCRIPT_NAME%.*}.fifo.$$"
readonly MAX_CONCURRENCY=4

# 3. ADVANCED STACK TRACE & ERROR HANDLER
trace_back() {
    local exit_code=$?
    local last_command="${BASH_COMMAND}"
    local frame_count="${#BASH_LINENO[@]}"

    # Alihkan langsung ke FD 2 (stderr)
    exec 1>&2

    echo "=================================================================="
    echo "CRITICAL FAILURE: Command '${last_command}' failed with exit code ${exit_code}."
    echo "Timestamp       : $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "Call Stack Trace:"

    for ((i=1; i<frame_count; i++)); do
        local source_file="${BASH_SOURCE[$i]}"
        local line_number="${BASH_LINENO[$((i-1))]}"
        local function_name="${FUNCNAME[$i]}"
        echo "  at ${source_file}:${line_number} in function '${function_name}'"
    done
    echo "=================================================================="
    exit "${exit_code}"
}

# 4. DETERMINISTIC CLEANUP TRAP HANDLER
cleanup() {
    local exit_code=$?
    echo "[Engine] Membersihkan resource (PID: $$)..."
    
    # Tutup dan hapus Named Pipe Semaphore
    if [[ -p "${SEMAPHORE_FIFO}" ]]; then
        exec 7<&- 2>/dev/null || true
        exec 7>&- 2>/dev/null || true
        rm -f "${SEMAPHORE_FIFO}"
    fi

    # Lepaskan flock file descriptor jika masih terpasang
    exec 9>&- 2>/dev/null || true
    
    # Bunuh seluruh child process subshell yang tersisa dalam process group
    trap - SIGTERM SIGINT
    kill -- -$$ 2>/dev/null || true

    echo "[Engine] Selesai dengan status kode: ${exit_code}"
    exit "${exit_code}"
}

# Daftarkan trap
trap 'trace_back' ERR
trap 'cleanup' EXIT
trap 'exit 130' SIGINT
trap 'exit 143' SIGTERM

# 5. ATOMIC MUTEX VIA FLOCK (FD 9)
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    echo "[Fatal] Skrip sedang berjalan pada PID $(cat "${LOCK_FILE}" 2>/dev/null || echo 'Unknown'). Aborting." >&2
    exit 1
fi
echo "$$" >&9

# 6. SEMAPHORE FIFO INITIALIZATION (FD 7)
mkfifo "${SEMAPHORE_FIFO}"
exec 7<>"${SEMAPHORE_FIFO}"
rm -f "${SEMAPHORE_FIFO}" # Unlink file system path; inode tetap aktif via FD 7

# Isi semaphore token sejumlah MAX_CONCURRENCY
for ((i=0; i<MAX_CONCURRENCY; i++)); do
    echo >&7
done

# 7. BUSINESS LOGIC - WORKER PAYLOAD
process_payload() {
    local task_id="$1"
    local execution_time="$2"
    
    echo "[Worker ${task_id}] Mulai eksekusi pada PID $$, estimasi: ${execution_time}s"
    
    # Simulasi I/O operation
    sleep "${execution_time}"
    
    # Contoh simulasi error handling (jika task ID = 999 akan panic)
    if [[ "${task_id}" == "999" ]]; then
        echo "[Worker ${task_id}] Memicu simulated error!" >&2
        false
    fi

    echo "[Worker ${task_id}] SELESAI sukses."
}

# 8. WORKER POOL ORCHESTRATION LOOP
main() {
    echo "[Engine] Memulai orkestrasi dengan Max Concurrency: ${MAX_CONCURRENCY}..."
    
    # Dummy workload array: task_id:sleep_time
    local tasks=(
        "101:2"
        "102:4"
        "103:1"
        "104:3"
        "105:2"
        "106:1"
        "107:2"
    )

    for task_info in "${tasks[@]}"; do
        # Tunggu ketersediaan slot token dari semaphore (Blocking Read)
        read -r -u 7

        IFS=':' read -r tid duration <<< "${task_info}"

        # Fork worker ke dalam subshell background
        (
            # Pastikan subshell tidak mewarisi trap ERR yang membingungkan parent
            trap 'exit 1' ERR
            
            process_payload "${tid}" "${duration}"
            
            # Kembalikan token ke semaphore setelah selesai
            echo >&7
        ) &
    done

    # Tunggu seluruh child background process rampung
    wait

    echo "[Engine] Seluruh tugas berhasil diproses secara konkuren."
}

main "$@"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sebuah perusahaan logistik skala enterprise memiliki armada 5.000 worker node Linux di berbagai edge datacenter. Setiap node menjalankan daemon Bash yang bertugas membaca *high-frequency sensor streaming records* dari VFS mount, melakukan enkripsi payload, dan mengirimkannya ke central object storage API.

#### Permasalahan:
1. **Zombification & Preemption:** Jika worker node terkena *preemption* (misal Spot Instance di-shutdown oleh cloud provider), script seringkali terputus di tengah pengiriman data, menghasilkan state log korup dan lock file basi (*stale lockfile*).
2. **Buffer Overflow IPC:** Penggunaan standard pipe buffer tanpa flow control mengakibatkan memori Bash meluap (*OOM Killed*) saat sensor mengirim 50.000 log records/detik.
3. **Deadlock:** Script generasi lama menggunakan locking berbasis polling file `[ -f /tmp/lock ]` yang menyebabkan dua worker berbeda menulis ke blok partisi disk yang sama secara konkuren (*data race corruption*).

#### Solusi Arsitektural:
1. **Flock Descriptor Hijacking Protection:** Penguncian kernel-level memanfaatkan FD 9 yang otomatis invalid saat proses diterminasi oleh `SIGKILL` ataupun preemption.
2. **Backpressure FIFO Streaming:** Implementasi Named Pipe terisolasi dengan chunking processing data berukuran 64KB (kapasitas default pipe buffer Linux) sehingga parent process menahan aliran data (*backpressure*) ke worker jika worker lambat memproses.
3. **State Rollback pada ERR Trap:** Setiap chunk data yang gagal diverifikasi langsung dipindahkan ke directory dead-letter-queue via rollback function terintegrasi.

---

### 9. Trade-offs

| Pendekatan / Teknik | Keuntungan | Biaya / Trade-off | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Named Pipe Semaphore** | Mengontrol batas pemakaian CPU/RAM secara ketat tanpa library eksternal. | Kompleksitas debugging tracing FD; potensi deadlock jika read/write tidak seimbang. | Paralelisme batch processing pada lingkungan Linux minimal. | Beban tugas sangat pendek (<10ms per job) karena overhead `fork()` dominan. |
| **`flock` FD Mutex** | Atomic, bebas *race condition*, otomatis dilepas oleh kernel jika script crash. | Memerlukan filesystem yang mendukung POSIX locking (tidak selalu andal di beberapa implementasi NFS kuno). | Mencegah duplicate cron run atau overlap daemon process. | Jika script harus lock resource lintas multi-server secara terdistribusi (gunakan Redis/Consul). |
| **Deep Stack Trace via ERR Trap** | Root-cause analysis langsung diketahui seketika saat crash di production. | Sedikit overhead eksekusi Bash introspection array; kode skrip menjadi lebih panjang. | Skrip CI/CD pipeline, installer enterprise, skrip migrasi database. | Skrip mikro satu baris (*one-liner utility*) atau command wrapper sederhana. |
| **Custom FD Redirection (FD 3-9)** | Isolasi output murni (stdout) dari output internal diagnosa & audit data. | Pengembang pemula sulit membaca sintaks `exec 3>&1` atau `>&3`. | Skrip interaktif yang mengembalikan payload JSON/data murni ke stdout. | Script shell sederhana yang tidak membutuhkan parsing machine-to-machine. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Fork Bomb akibat Unbounded Backgrounding
* **Gejala:** Server hang, out of memory, SSH tidak dapat diakses, dmesg menampilkan `kernel: fork: Cannot allocate memory`.
* **Penyebab:** Memanggil `do_work &` di dalam loop tanpa throttling/semaphore.
* **Solusi:** Wajib gunakan implementasi semaphore berbasis FIFO token loop seperti yang dicontohkan pada bagian 7.B.

#### 2. Subshell Variable Leakage (Anti-Pattern)
* **Gejala:** Nilai counter atau status array tetap kosong setelah loop berakhir.
  ```bash
  # KESALAHAN UMUM
  SUCCESS_COUNT=0
  cat task_list.txt | while read -r line; do
      ((SUCCESS_COUNT++))
  done
  echo "Total: ${SUCCESS_COUNT}" # Output selalu 0!
  ```
* **Penyebab:** Penggunaan pipeline `| while` memaksa loop dieksekusi di dalam subshell terisolasi (child process memory).
* **Solusi:** Gunakan Process Substitution atau redirect loop stdin:
  ```bash
  SUCCESS_COUNT=0
  while read -r line; do
      ((SUCCESS_COUNT++))
  done < task_list.txt
  echo "Total: ${SUCCESS_COUNT}" # Output benar
  ```

#### 3. Deadlock pada Named Pipe (FIFO)
* **Gejala:** Skrip berhenti tanpa error (*freeze* permanen) pada line `read` atau `echo > fifo`.
* **Penyebab:** Named Pipe di Linux bersifat blocking secara default; `write` akan memblokir proses sampai ada pihak lain yang melakukan `read`, dan sebaliknya.
* **Solusi:** Buka FIFO menggunakan mode dua arah (read-write) pada dedicated FD:
  ```bash
  exec 7<>"${SEMAPHORE_FIFO}" # Mode read-write (<>) mencegah blocking saat inisialisasi
  ```

#### 4. File Descriptor Leakage
* **Gejala:** `/proc/$$/fd/` terus bertambah hingga mencapai batas `ulimit -n`.
* **Penyebab:** Membuka custom FD di dalam loop fungsi berulang kali tanpa menutupnya (`exec {fd}>&-`).
* **Solusi:** Pastikan setiap `exec {fd}>path` ditutup secara deterministik di blok cleanup atau segera setelah stream selesai dikonsumsi.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis skrip Bash ke lingkungan produksi:

- [ ] **Strict Execution Flags:** Menggunakan `set -Eeuo pipefail` di baris teratas setelah shebang.
- [ ] **Deterministic Shebang:** Menggunakan `#!/usr/bin/env bash` daripada `#!/bin/bash` yang hardcoded demi portabilitas antar distro Linux.
- [ ] **Deterministic Clean Trap:** Mendaftarkan handler `EXIT`, `ERR`, `SIGINT`, `SIGTERM` secara eksplisit.
- [ ] **Static Code Analysis Passed:** Skrip telah divalidasi dengan `shellcheck --severity=style` tanpa warning.
- [ ] **Atomic Concurrency Guard:** Melindungi proses batch/cron dengan `flock(2)` berbasis dedicated FD.
- [ ] **Explicit FD Cleanups:** Semua alokasi FD kustom (FD 3-9) ditutup eksplisit menggunakan format `exec N>&-`.
- [ ] **Non-Polluting Subshell Loops:** Tidak ada pemanggilan pipeline yang mengisolasi variabel krusial ke memory child process yang tidak bisa dibaca kembali.
- [ ] **Process Group Signal Propagation:** Handler trap signal mengandung pembersihan grup proses (`kill -- -$$ 2>/dev/null || true`) untuk membunuh lingering child subshells.
- [ ] **No Hardcoded Paths:** Path binary sistem menggunakan evaluasi dinamis atau variabel yang dapat di-override (misal `CURL="${CURL_BIN:-/usr/bin/curl}"`).

---

### 12. Hands-on Practice

Berikut adalah panduan latihan lab bertahap untuk membangun orkestrator batch engine.

#### Persiapan Lab
Buat struktur direktori hands-on:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Membangun Crash Dump Simulator (`hands-on/m02/01_crash_engine.sh`)
Buat file untuk memvalidasi bagaimana stack trace merekonstruksi crash call tree secara deterministik.

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Inisialisasi Trap
trap 'echo "[CRASH] Gagal pada baris ${BASH_LINENO[0]} saat menjalankan: ${BASH_COMMAND}" >&2' ERR

level_three() {
    echo "Masuk level 3: memicu error eksekusi..."
    # Perintah tidak valid yang memicu exit non-zero
    ls /direktori/yang/pasti/tidak/pernah/ada/12345
}

level_two() {
    echo "Masuk level 2..."
    level_three
}

level_one() {
    echo "Masuk level 1..."
    level_two
}

level_one
```
*Jalankan skrip:* `chmod +x 01_crash_engine.sh && ./01_crash_engine.sh`  
*Amati output:* Identifikasi bagaimana ERR trap menangkap perintah yang gagal beserta baris kodenya.

#### Langkah 2: Membangun Mutex Locker (`hands-on/m02/02_mutex_flock.sh`)
Buat file simulasi anti-overlap job:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/service_updater.lock"
exec 9>"${LOCK_FILE}"

echo "Mencoba memperoleh mutex lock..."
if ! flock -n 9; then
    echo "ERROR: Proses lain sedang berjalan. Exit secara aman." >&2
    exit 1
fi
echo "$$" >&9

echo "Lock diperoleh! Memulai pekerjaan kritikal selama 10 detik (PID: $$)..."
sleep 10
echo "Pekerjaan selesai. Lock dilepas."
```
*Uji:* Jalankan `./02_mutex_flock.sh &` lalu segera jalankan `./02_mutex_flock.sh` di terminal yang sama dalam jeda kurang dari 10 detik. Amati bagaimana instance kedua membatalkan eksekusi secara aman (*graceful abort*).

---

### 13. Exercise

#### Level: Easy
Modifikasi file `hands-on/m02/01_crash_engine.sh` sehingga stack trace menampilkan nama fungsi yang bersarang (*nested functions*) secara lengkap menggunakan iterasi array `${FUNCNAME[@]}`.

#### Level: Medium
Buat skrip `hands-on/m02/medium_fd_splitter.sh` yang:
1. Membuka FD 3 untuk file `success.log` dan FD 4 untuk file `error.log`.
2. Menerima input stream berupa teks berisikan 20 baris acak (berisi string `SUCCESS: ...` atau `ERROR: ...`).
3. Mengarahkan parsing record tersebut ke FD yang sesuai tanpa menggunakan disk file sementara (*intermediate temporary files*).
4. Menutup kedua FD di akhir eksekusi secara deterministik.

#### Level: Hard
Buat skrip `hands-on/m02/hard_batch_throttle.sh` yang:
1. Mengimplementasikan worker pool semaphore dinamis yang kapasitas worker-nya dapat diubah saat runtime via sinyal OS (Kirim `SIGUSR1` untuk menambah 1 slot worker, kirim `SIGUSR2` untuk mengurangi 1 slot worker tanpa mematikan batch engine yang sedang berjalan).
2. Memastikan tidak terjadi deadlock saat penambahan atau pengurangan slot token Named Pipe.

---

### 14. Challenge

**Studi Kasus Arsitektur:** "Resilient Zero-Downtime Blue/Green Micro-Deployment Engine"

Rancang sebuah skrip Bash production-grade tunggal bernama `deploy_orchestrator.sh` dengan spesifikasi berikut:
1. **Zero External Dependency:** Hanya mengandalkan core Linux utilities (`bash`, `coreutils`, `curl`, `flock`).
2. **State Management:** Menerima input file manifes yang mendefinisikan 10 target microservice endpoint health checks.
3. **Execution Constraints:**
   - Maksimum pemanggilan proses konkuren dibatasi 3 worker secara simultan.
   - Timeout polling per service adalah 5 detik.
4. **Resiliency & Rollback:**
   - Jika satu service mengembalikan HTTP non-200 sebanyak 3 kali berturut-turut, picu prosedur `rollback_all` yang mengirimkan sinyal pembatalan ke seluruh child worker yang sedang berjalan secara instan (`SIGTERM`).
   - Eksekusi stack trace dump yang komprehensif ke audit file descriptor (FD 5) yang tersimpan di disk.
5. **Security & Signal Isolation:** Skrip harus tahan terhadap interupsi terminal (`SIGHUP`). Jika terminal ditutup paksa, engine tetap melanjutkan rollback hingga tuntas sebelum melepaskan kernel lock file.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa ekspresi `set -e` saja tidak cukup untuk menangani kegagalan pada pipeline seperti `cat non_existent_file | grep "foo"`?
2. Mengapa modifikasi variabel di dalam perulangan `cat file | while read line; do VAR="new"; done` tidak berpengaruh di luar loop?
3. Apa perbedaan fundamental antara file descriptor `1` dan file descriptor `2` pada sistem operasi POSIX?
4. Apa yang terjadi pada kernel open file table lock yang dibuat via syscall `flock(2)` apabila proses pemilik lock mati terkena `SIGKILL` (`kill -9`)?
5. Mengapa sintaks `exec 3>&-` harus dipanggil dalam skrip yang membuka file descriptor kustom?

#### B. Pertanyaan Intermediate
6. Mengapa mode file descriptor `exec 7<>"${FIFO_FILE}"` (read-write mode) lebih disukai daripada pembukaan terpisah (`exec 7<` dan `exec 7>`) saat mengimplementasikan semaphore di Bash?
7. Bagaimana variabel internal Bash `BASH_SOURCE`, `FUNCNAME`, dan `BASH_LINENO` saling berkorelasi saat runtime stack tracing dibangkitkan?
8. Bagaimana implementasi sintaks `kill -- -$$` bekerja untuk membunuh seluruh proses anak (*child subshells*), dan apa arti tanda minus (`-`) sebelum PID?
9. Apa perbedaan dampak performa antara memanggil command external berkali-kali di dalam loop (misal `date` atau `sed`) dibandingkan dengan Bash internal Parameter Expansion?
10. Pada kondisi apa flag `set -u` (*nounset*) memicu false-positive error pada parameter expansion default `${1:-default}`?

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sebuah cronjob Bash berjalan setiap menit untuk mengeksekusi pipeline database ETL. Pada hari tertentu, database mengalami lonjakan beban sehingga skrip butuh 3 menit untuk selesai. Terjadi penumpukan ratusan proses cronjob yang sama hingga server mengalami crash karena exhaust process table. Solusi teknis apa yang harus disematkan langsung di level skrip Bash?
12. **Skenario 2:** Anda memiliki skrip runner CI/CD yang menjalankan background parallel subshells dengan loop token semaphore FIFO. Saat skrip runner di-cancel dari dashboard Gitlab Runner (mengirim `SIGTERM`), subshell background terus berjalan di latar belakang sebagai *orphaned processes* dan mengunci port testing. Bagaimana memperbaiki handling sinyal tersebut?
13. **Skenario 3:** Skrip deployment aplikasi menggunakan perulangan array konfigurasi untuk mengganti baris file via inline stream manipulation. Terjadi disk out-of-space di tengah eksekusi loop sehingga file konfigurasi terpotong menjadi 0 byte (*file truncation failure*). Bagaimana merancang arsitektur penulisan file yang aman (*atomic file writes*) murni menggunakan Bash?

---

#### Kunci Jawaban & Evaluasi

##### Jawaban Basic
1. `set -e` hanya memeriksa status kode keluar (*exit status*) dari **perintah terakhir** pada pipeline. Jika perintah pertama gagal namun `grep` mengembalikan kode 0 (atau sebaliknya tergantung posisi), `set -e` menganggap pipeline berhasil. Harus dikombinasikan dengan `set -o pipefail` agar pipeline gagal jika salah satu perintah mengembalikan non-zero.
2. Operator pipeline (`|`) mengeksekusi sisi kanan di dalam subshell memory space baru (`clone`/`fork`). Perubahan variabel terjadi di memori child process dan dimusnahkan seketika subshell tersebut keluar, sehingga parent process tetap menyimpan nilai lama.
3. FD 1 (`stdout`) didesain untuk stream data utama program (payload yang dapat di-pipe ke program lain), sedangkan FD 2 (`stderr`) didesain khusus untuk diagnostik, error, dan log yang tidak boleh bercampur dengan data payload.
4. Kernel Linux mengasosiasikan lock `flock(2)` dengan *file table entry* yang diikat ke Process ID. Jika proses mati secara mendadak (termasuk via `SIGKILL`), kernel secara otomatis menutup seluruh open file descriptors proses tersebut dan membersihkan advisory lock, sehingga tidak akan memicu *permanent lockfile deadlock*.
5. `exec 3>&-` menutup file descriptor 3. Jika tidak ditutup, descriptor tetap terbuka di process table hingga skrip berhenti, yang dapat menyebabkan *file handle exhaustion* atau file tidak dapat di-unmount pada level OS.

##### Jawaban Intermediate
6. Membuka FIFO hanya untuk membaca (`<`) akan memblokir (*blocking pause*) hingga ada writer yang membuka pipe tersebut. Membuka FIFO hanya untuk menulis (`>`) juga akan memblokir hingga ada reader. Membuka dengan mode dua arah (`<>`) memastikan descriptor langsung terbuka tanpa blocking, mencegah *startup deadlock*.
7. Ketiganya adalah array paralel terindeks: `BASH_SOURCE[i]` menyimpan nama file tempat pemanggilan, `FUNCNAME[i]` menyimpan nama fungsi yang sedang aktif, dan `BASH_LINENO[i-1]` menyimpan nomor baris pasti di mana fungsi/perintah tersebut dipanggil dari layer stack sebelumnya.
8. Tanda minus (`-`) sebelum ID proses menginstruksikan kernel bahwa target sinyal bukanlah single PID, melainkan seluruh **Process Group ID (PGID)**. `kill -- -$$` mengirimkan sinyal ke seluruh proses anak yang berbagi grup ID yang sama dengan parent Bash script, mencegah *orphaned subshells*.
9. Pemanggilan command eksternal memaksa kernel mengeksekusi syscall `fork()`, alokasi memori halaman baru, resolving binary path via `$PATH`, dan syscall `execve()`. Dalam 10.000 iterasi, ini memakan waktu orde beberapa detik hingga menit. Bash Parameter Expansion dieksekusi langsung di CPU thread memory Bash runtime secara native tanpa fork overhead (orde milidetik).
10. `set -u` **tidak** memicu false positive pada sintaks `${1:-default}` atau `${var:+alternate}` karena Bash mengenali fallback operator sebagai penanganan ekspresi uninitialized variable yang aman. False positive terjadi jika parameter dievaluasi langsung via `${1}` atau `$var` tanpa operator ekspansi parameter pelindung.

##### Jawaban Skenario Produksi
11. Pasang non-blocking mutual exclusion lock via `flock` pada file descriptor terisolasi di awal script:
    ```bash
    exec 9>"/var/lock/db_etl.lock"
    flock -n 9 || exit 0
    ```
    Jika instance sebelumnya masih berjalan, cronjob berikutnya akan langsung exit seketika (status 0 atau error handling terukur) tanpa membebani sistem.
12. Tangkap sinyal `SIGTERM` dan `SIGINT` menggunakan trap handler yang mengarahkan pembunuhan grup proses (*process group killing*):
    ```bash
    trap 'trap - SIGTERM; kill -- -$$ 2>/dev/null; exit 143' SIGTERM
    ```
    Ini menjamin sinyal terminasi diteruskan ke seluruh subshell worker yang sedang berjalan sebelum parent process keluar.
13. Terapkan pola **Atomic File Write with Rollback**:
    Jangan pernah memodifikasi file target secara *in-place* langsung. Tulis konfigurasi baru ke file sementara pada partisi/filesystem yang sama (`${TARGET_FILE}.tmp.$$`), validasi integritas sintaks file menggunakan parser/checksum, lalu lakukan atomic swap menggunakan syscall `mv` (`rename(2)` atomic operation):
    ```bash
    generate_config > "${TARGET_FILE}.tmp.$$"
    validate_syntax "${TARGET_FILE}.tmp.$$" && mv -f "${TARGET_FILE}.tmp.$$" "${TARGET_FILE}"
    ```
    Jika script crash atau disk penuh di tengah penulisan, file asli tidak pernah terkorupsi.

---

### 16. Summary

1. **Kernel-Aware Scripting:** Bash tingkat enterprise berinteraksi erat dengan arsitektur Linux Kernel; pemahaman atas syscalls (`fork`, `dup2`, `flock`, `pipe`) memisahkan skrip rapuh dengan automation engine berkinerja tinggi.
2. **Defensive Primitives:** Penggunaan kombinasi `set -Eeuo pipefail` dan trap handler terpadu (`EXIT`, `ERR`, signals) adalah pondasi dasar penulisan skrip yang deterministik.
3. **Controlled Concurrency:** Paralelisme di Bash tidak boleh dibiarkan tanpa batas (*unbounded*). Pemanfaatan FIFO Named Pipe sebagai *Token-Bucket Semaphore* menghindarkan host dari kehabisan memori (*OOM*) dan *Process Table Exhaustion*.
4. **Isolated I/O Streaming:** Memisahkan data output operasional, audit tracking, dan pesan kesalahan fatal melalui alokasi File Descriptor kustom (FD 3 hingga 9) menjamin integritas data dalam pipeline otomatisasi modern.