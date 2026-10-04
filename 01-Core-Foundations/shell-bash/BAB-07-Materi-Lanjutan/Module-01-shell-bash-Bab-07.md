## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Core Foundations
*   **Mata Pelajaran:** Advanced Linux & Bash Systems Programming
*   **Bab:** 07 — Job Control, Process Lifecycle & Signals
*   **Modul:** 01 — Job Control, Process Lifecycle & POSIX Signal Interception
*   **Kode Modul:** `BASH-CORE-07-01`
*   **Tingkat Kesulitan:** Intermediate to Advanced
*   **Estimasi Waktu Penyelesaian:** 120 Menit
*   **Prasyarat:** Pemahaman mendalam tentang eksekusi shell, Exit Codes (`$?`), Pipes (`|`), Redirection (`<`, `>`, `2>&1`), serta manipulasi File Descriptors (Bab 06).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan memiliki kompetensi teknis untuk:

1. **Membedakan dan Mengelola State Proses:** Menganalisis siklus hidup proses POSIX (`fork`, `execve`, `waitpid`, `exit`) dan mendiagnosis status abnormal seperti *Zombie* (`defunct`) dan *Orphan*.
2. **Menguasai Mekanisme Bash Job Control:** Mengontrol eksekusi foreground dan background process groups menggunakan `&`, `jobs`, `fg`, `bg`, `disown`, serta suspensi eksekusi via kontrol sinyal TTY.
3. **Mengimplementasikan POSIX Signal Handling:** Mengonfigurasi penanganan sinyal asinkron (`SIGINT`, `SIGTERM`, `SIGHUP`, `SIGQUIT`, `SIGCHLD`, `SIGUSR1`/`2`) menggunakan shell built-in `trap` untuk menjamin ketahanan runtime.
4. **Membangun Arsitektur Script Graceful Shutdown:** Menulis automation scripts level produksi yang mampu membersihkan temporary resources, melepaskan dynamic lock files, dan menghentikan child processes secara deterministik tanpa meninggalkan *resource leak*.
5. **Mengisolasi dan Memahami Relasi Process Tree:** Menavigasi keterkaitan antara Process ID (PID), Parent Process ID (PPID), Process Group ID (PGID), dan Session ID (SID) dalam interaksi kontrol terminal (TTY).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Linux Kernel / POSIX Subsystem]
       │
       ├── Syscalls: fork() ──> execve() ──> wait() / waitpid() ──> exit()
       │
[Bash Shell Environment]
       │
       ├── Process Hierarchy Management
       │     ├── PID (Process ID)
       │     ├── PPID (Parent PID)
       │     ├── PGID (Process Group ID)
       │     └── SID (Session ID)
       │
       ├── Job Control Engine (Terminal Control / TTY)
       │     ├── Foreground Group (Receives stdin/stdout & keyboard signals)
       │     ├── Background Group (&, stopped, running)
       │     └── State Shifting: Ctrl+Z (SIGTSTP) -> bg -> fg -> Ctrl+C (SIGINT)
       │
       └── POSIX Signals & Trap Subsystem
             ├── Non-Catchable Signals: SIGKILL (9), SIGSTOP (19)
             ├── Catchable Signals: SIGTERM (15), SIGINT (2), SIGHUP (1), SIGUSR1/2
             ├── IPC Notification: SIGCHLD (Child termination/reaping)
             └── Graceful Termination Handling: trap 'cleanup_routine' SIGTERM SIGINT
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Di lingkungan produksi Linux, proses shell jarang berjalan dalam isolasi sempurna. Script otomasi, pipeline CI/CD, batch processing, dan background daemons beroperasi dalam ekosistem dinamis yang rentan terhadap interupsi eksternal: scheduler cloud me-reboot VM, orchestrator seperti Kubernetes mengirim `SIGTERM` untuk scaling down, atau user menekan `Ctrl+C` saat script berada di tengah-tengah transaksi file krusial.

Tanpa pemahaman mendalam tentang siklus hidup proses dan penanganan sinyal:
* Script Bash akan mati secara mendadak (*abrupt termination*), meninggalkan state yang inkonsisten, temporary file yang memenuhi partisi `/tmp`, atau lockfile basi (*stale lockfiles*) yang memblokir cron job berikutnya.
* Sub-proses yang dijalankan di background dapat terputus dari parent-nya, berubah menjadi *zombie* yang memadati tabel proses kernel (`PID exhaustion`) atau menjadi *orphan* yang mengonsumsi CPU/RAM di luar kendali manajemen monitoring.
* Administrator tidak dapat melakukan orkestrasi task secara paralel dan asinkron di dalam single terminal session secara aman tanpa memanfaatkan fasilitas Job Control bawaan Unix secara presisi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Proses dan Atributnya
Proses adalah instance program yang sedang dieksekusi oleh sistem operasi, memiliki ruang memori privat (*virtual address space*), file descriptor table, serta metadata kernel:
* **PID (Process ID):** Identifier unik proses di dalam kernel namespace.
* **PPID (Parent Process ID):** PID dari proses pembuat. Jika parent mati lebih dulu, proses diadopsi oleh init system (PID 1 / `systemd`) atau subreaper lokal.
* **PGID (Process Group ID):** Kumpulan proses terkait yang dapat menerima sinyal identik secara bersamaan (misal: semua perintah dalam single pipe `cat access.log | grep 500 | awk ...`).
* **SID (Session ID):** Kumpulan dari satu atau lebih process group yang terikat pada satu controlling terminal (TTY).

### 2. Job Control
Job control adalah fitur shell yang memungkinkan satu terminal mengontrol beberapa proses konkuren secara interaktif. Job adalah abstraksi tingkat shell di atas process group:
* **Foreground Job:** Proses yang terhubung langsung ke terminal TTY, memiliki akses baca ke stdin dan menerima sinyal langsung dari keyboard (`Ctrl+C`, `Ctrl+Z`). Shell ditahan (*blocked*) sampai job ini selesai atau disuspensi.
* **Background Job:** Proses yang dieksekusi tanpa memblokir terminal prompt shell (ditandai dengan operator `&`). Background job tidak dapat membaca dari stdin (akan menerima `SIGTTIN` jika mencoba), namun secara default masih dapat menulis ke stdout/stderr kecuali di-redirect.

### 3. POSIX Signals
Sinyal adalah bentuk Inter-Process Communication (IPC) asinkron paling primitif dan esensial di Unix-like OS. Sinyal dikirimkan oleh kernel, proses lain, atau terminal driver ke suatu proses untuk mengabarkan suatu event. Bash menangkap dan merespons sinyal ini menggunakan internal command `trap`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Fork-Exec-Wait-Exit
Saat Bash mengeksekusi program eksternal (bukan shell built-in):
1. **`fork()`:** Shell menduplikasi dirinya sendiri. Menghasilkan *child process* yang memiliki salinan memori, environment variables, dan file descriptors dari *parent process*.
2. **`execve()`:** Di dalam child process, binary yang dituju dieksekusi, menimpa teks program dan memori child process tersebut dengan executable baru, namun mewarisi file descriptors yang terbuka (kecuali flag `FD_CLOEXEC` aktif).
3. **`waitpid()`:** Parent process (Bash) memasuki status blocked, menunggu status terminasi dari child process untuk membaca *exit status code* ($?).
4. **`exit()`:** Child melepaskan seluruh resources (RAM, descriptor) dan mengirimkan sinyal `SIGCHLD` ke parent. Jika parent tidak memanggil `waitpid()`, child process masuk ke state **Zombie** (`Z` / `<defunct>`).

```
Parent (Bash) ──fork()──> Child (Forked Bash) ──execve()──> Child (App Execution)
      │                                                              │
  waitpid() (Blocked)                                              exit()
      │                                                              │
      └──<─────────────── Reads Exit Code ───────────────────────────┘
```

### 2. Job Table Bash dan TTY Signals
Terminal line discipline mengonversi input keyboard menjadi sinyal kernel:
* `Ctrl+C` mengirimkan **`SIGINT`** (Signal 2) ke seluruh foreground process group.
* `Ctrl+Z` mengirimkan **`SIGTSTP`** (Terminal Stop, Signal 20) yang menunda eksekusi proses ke background dalam state *Stopped*.
* Command `bg %n` mengirimkan **`SIGCONT`** (Signal 18) ke job ke-*n*, melanjutkan eksekusi di latar belakang tanpa mengembalikan akses stdin TTY.
* Command `fg %n` mengalihkan kontrol TTY ke job ke-*n* melalui `tcsetpgrp()`, mengirimkan `SIGCONT` bila proses sedang stopped, dan memblokir shell utama.

### 3. Sinyal POSIX Fundamental

| Nama Sinyal | Nomor (x86_64) | Aksi Default | Catchable/Trappable? | Deskripsi Semantik |
| :--- | :--- | :--- | :--- | :--- |
| **`SIGHUP`** | 1 | Terminate | **Ya** | Hangup; terminal controlling ditutup atau koneksi SSH putus. Sering digunakan daemon untuk reload config. |
| **`SIGINT`** | 2 | Terminate | **Ya** | Interrupt; dikirim via keyboard `Ctrl+C`. Permintaan interupsi graceful secara interaktif. |
| **`SIGQUIT`** | 3 | Core Dump | **Ya** | Quit; dikirim via keyboard `Ctrl+\`. Menghentikan proses dan memicu core dump debugging. |
| **`SIGKILL`** | 9 | Force Terminate| **TIDAK** | Unconditional abort; diproses langsung oleh kernel tanpa notifikasi ke proses. Tidak bisa di-block atau di-handle. |
| **`SIGUSR1`** | 10 | Terminate | **Ya** | User-defined signal 1; dialokasikan untuk logika kustom aplikasi/script. |
| **`SIGUSR2`** | 12 | Terminate | **Ya** | User-defined signal 2; dialokasikan untuk logika kustom aplikasi/script. |
| **`SIGTERM`** | 15 | Terminate | **Ya** | Termination request; sinyal default perintah `kill`. Meminta proses shutdown secara teratur. |
| **`SIGSTOP`** | 19 | Pause Execution| **TIDAK** | Stop process execution; kernel menghentikan penjadwalan proses. Tidak bisa di-intercept. |
| **`SIGTSTP`** | 20 | Pause Execution| **Ya** | Terminal Stop; dikirim via `Ctrl+Z`. Dapat di-trap untuk membersihkan layar sebelum suspend. |
| **`SIGCHLD`** | 17 | Ignore | **Ya** | Child status changed; dikirim ke parent ketika child berhenti, lanjut, atau terminated. |

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Lifecycle State Machine & Job Transitioning

```
               [ INITIATION ]
                      │
                      │ fork() & execve()
                      ▼
             ┌─────────────────┐
             │  RUNNING / TTY  │ <────────────── fg %1 ─────────────────┐
             │  (Foreground)   │                                        │
             └────────┬────────┘                                        │
                      │                                                 │
          Ctrl+Z      │                  kill -TERM                     │
        (SIGTSTP)     │                  or SIGINT                      │
                      ▼                                                 │
             ┌─────────────────┐                                        │
             │     STOPPED     │                                        │
             │   (Suspended)   │                                        │
             └────────┬────────┘                                        │
                      │                                                 │
                      │ bg %1 (SIGCONT)                                 │
                      ▼                                                 │
             ┌─────────────────┐                                        │
             │  RUNNING / BG   │ ───────────────────────────────────────┘
             │  (Background)   │
             └────────┬────────┘
                      │
                      │ Process finishes exit(n) OR SIGKILL (9)
                      ▼
             ┌─────────────────┐
             │     ZOMBIE      │ (Waiting for parent waitpid() reap)
             │   (<defunct>)   │
             └────────┬────────┘
                      │
                      │ Parent calls wait() / Parent terminates (PID 1 reaps)
                      ▼
             [ PURGED FROM PROCESS TABLE ]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh dasar demonstrasi navigasi status job: inisiasi background job, inspeksi antrean, perpindahan context, dan terminasi terkontrol.

```bash
#!/usr/bin/env bash
# Demonstrasi Dasar Job Control

# 1. Jalankan proses dummy yang sleep panjang di background
echo "Mengeksekusi proses background 1 & 2..."
sleep 100 &
JOB1_PID=$! # Menangkap PID dari background job terakhir

sleep 200 &
JOB2_PID=$!

echo "Job 1 PID: ${JOB1_PID}"
echo "Job 2 PID: ${JOB2_PID}"

# 2. Melihat job table di memory shell saat ini
echo "Daftar Job Aktif:"
jobs -l

# 3. Mengirimkan sinyal stop (SIGSTOP) secara manual ke Job 1
echo "Mengirim sinyal SIGSTOP ke Job 1..."
kill -STOP "${JOB1_PID}"

# Periksa status job (harus bertuliskan 'Stopped')
jobs -l

# 4. Melanjutkan eksekusi Job 1 di background (SIGCONT)
echo "Mengaktifkan kembali Job 1 di background..."
bg %1

# 5. Membersihkan job secara paksa sebelum script exit
echo "Menghentikan semua job dummy..."
kill -TERM "${JOB1_PID}" "${JOB2_PID}"
wait "${JOB1_PID}" "${JOB2_PID}" 2>/dev/null

echo "Semua job berhasil dibersihkan."
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Script worker level produksi: Mengimplementasikan pattern *Robust Worker Daemon* yang menangani sinyal POSIX (`SIGINT`, `SIGTERM`, `SIGHUP`), mengelola dynamic lockfile, menjamin *graceful drain*, dan membersihkan child process secara deterministik.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Nama File: robust_worker.sh
# Deskripsi: Template production-grade worker dengan Signal Trapping & Graceful Cleanup
# ==============================================================================
set -euo pipefail

# Konfigurasi State & Path
readonly SCRIPT_NAME="$(basename "$0")"
readonly WORK_DIR="/tmp/worker_service_${UID}"
readonly PID_FILE="${WORK_DIR}/service.pid"
readonly LOG_FILE="${WORK_DIR}/service.log"

CURRENT_CHILD_PID=0
SHUTDOWN_REQUESTED=0

# Logger utility
log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] [$$] - $*" | tee -a "${LOG_FILE}" >&2
}

# Cleanup Routine: Dipanggil selalu saat script exit normal maupun abnormal
cleanup() {
    local exit_code=$?
    log "INFO" "Memulai cleanup routine (Exit code: ${exit_code})..."

    # 1. Hentikan child process yang masih berjalan
    if [[ ${CURRENT_CHILD_PID} -ne 0 ]] && kill -0 "${CURRENT_CHILD_PID}" 2>/dev/null; then
        log "WARN" "Menghentikan in-flight child process (PID: ${CURRENT_CHILD_PID})..."
        kill -TERM "${CURRENT_CHILD_PID}" 2>/dev/null || true
        wait "${CURRENT_CHILD_PID}" 2>/dev/null || true
    fi

    # 2. Hapus file lock dan state runtime
    if [[ -f "${PID_FILE}" ]]; then
        log "INFO" "Menghapus PID lock file: ${PID_FILE}"
        rm -f "${PID_FILE}"
    fi

    log "INFO" "Cleanup selesai. Shutdown tuntas."
    exit "${exit_code}"
}

# Signal Handler: Intercept SIGINT, SIGTERM, SIGHUP
handle_signal() {
    local sig="$1"
    log "WARN" "Sinyal ${sig} tertangkap! Memulai alur graceful shutdown..."
    SHUTDOWN_REQUESTED=1
    
    # Jangan exit langsung di sini jika sedang menunggu child process;
    # Trigger terminasi child agar loop utama segera selesai.
    if [[ ${CURRENT_CHILD_PID} -ne 0 ]] && kill -0 "${CURRENT_CHILD_PID}" 2>/dev/null; then
        kill -TERM "${CURRENT_CHILD_PID}" 2>/dev/null || true
    fi
}

# Reload Configuration: Implementasi handling SIGHUP
handle_reload() {
    log "INFO" "Sinyal SIGHUP diterima: Reloading konfigurasi runtime..."
    # Logika reload konfigurasi diletakkan di sini (tanpa mematikan proses)
}

# Pendaftaran Trap
# EXIT: Terpicu saat proses selesai (baik via exit code normal atau error)
# Sinyal spesifik diarahkan ke handler fungsinya
trap cleanup EXIT
trap 'handle_signal SIGTERM' SIGTERM
trap 'handle_signal SIGINT' SIGINT
trap 'handle_reload' SIGHUP

# Inisialisasi Lingkungan & Mutex Lock via PID
mkdir -p "${WORK_DIR}"
touch "${LOG_FILE}"

if [[ -f "${PID_FILE}" ]]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        log "ERROR" "Instance lain sudah berjalan dengan PID ${OLD_PID}. Abort."
        exit 1
    else
        log "WARN" "Ditemukan stale PID file (${OLD_PID}). Me-overwrite..."
    fi
fi
echo "$$" > "${PID_FILE}"

log "INFO" "Worker service aktif. Menunggu incoming tasks..."

# Simulasi Task Queue Consumer Loop
TASK_ID=1
while [[ ${SHUTDOWN_REQUESTED} -eq 0 ]]; do
    log "INFO" "Memproses Batch Task #${TASK_ID}..."
    
    # Jalankan workload eksternal secara asinkron (background) agar shell tetap
    # dapat menerima sinyal trap secara instan tanpa terblokir kernel sleep
    sleep 5 &
    CURRENT_CHILD_PID=$!

    # wait built-in Bash akan langsung mengembalikan kontrol jika ada signal trap yang tertangkap
    if wait "${CURRENT_CHILD_PID}"; then
        log "INFO" "Task #${TASK_ID} selesai dengan sukses."
    else
        log "WARN" "Task #${TASK_ID} terinterupsi atau mengalami error."
    fi
    CURRENT_CHILD_PID=0

    ((TASK_ID++))
    
    # Throttle interval antar batch
    if [[ ${SHUTDOWN_REQUESTED} -eq 0 ]]; then
        sleep 1 &
        CURRENT_CHILD_PID=$!
        wait "${CURRENT_CHILD_PID}" || true
        CURRENT_CHILD_PID=0
    fi
done

log "INFO" "Semua batch tasks selesai di-drain. Melanjutkan ke exit sequence."
exit 0
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Keputusan | Keuntungan | Kerugian / Risiko | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **`kill -9` (`SIGKILL`) vs `kill -15` (`SIGTERM`)** | `SIGKILL` menghentikan proses secara absolut dan instan dari tabel kernel. | Tidak ada kesempatan melepaskan memory locks, shared memory, menutup file descriptors, atau menghapus socket; berisiko korupsi data. | Gunakan `SIGTERM` sebagai default lini pertama. Gunakan `SIGKILL` hanya sebagai mekanisme fallback terakhir jika timeout graceful drain terlampaui. |
| **`trap ... EXIT` vs Trapping Individual Signals** | Trap `EXIT` bersifat universal, mencakup terminasi normal (`exit 0`), runtime failures (`exit 1`), dan sinyal fatal yang di-handle shell. | Logika cleanup harus idempotent karena akan dipanggil di semua skenario terminasi tanpa membedakan konteks error. | Wajib digunakan untuk alokasi resource berbasis filesystem (lockfile, scratch disk directory `/tmp`). |
| **Job Control Aktif (`set -m`) dalam Script** | Setiap background job berjalan di Process Group terpisah, mencegah sinyal keyboard menginterupsi background tasks. | Mengabaikan sinyal keyboard dapat menyebabkan orphaned tasks tak terkontrol bila script crashed; overhead manajemen TTY. | Script otomasi interaktif atau script orkestrasi yang menjalankan multi-service daemon secara lokal. |
| **Foreground Block (`cmd`) vs Background Wait (`cmd & wait $!`)** | Foreground block sangat sederhana ditulis dan tidak membutuhkan tracking manual terhadap PID. | Shell terblokir sepenuhnya di level kernel syscall; handling terhadap `trap` tertunda sampai child binary selesai beroperasi. | Gunakan `cmd & wait $!` pada loop daemon agar penanganan sinyal eksternal bersifat reaktif dan instan. |

---

## SEKSI 11 — BEST PRACTICES

1. **Jadikan Fungsi Cleanup Selalu Idempotent:**
   Fungsi cleanup yang didaftarkan ke trap harus aman dijalankan berkali-kali tanpa menghasilkan error tambahan (`rm -f` alih-alih `rm`, validasi keberadaan proses via `kill -0` sebelum mengirim sinyal).
2. **Hindari Blocking Command Langsung pada Trap Loop:**
   Ketika Bash menjalankan binary sinkron di foreground (misal `sleep 60`), shell menunda evaluasi trap sampai binary tersebut mengembalikan kendali. Pola aman untuk script interruptible:
   ```bash
   # RECOMMENDED: Trap responsif secara instan
   long_running_binary &
   CHILD_PID=$!
   wait "${CHILD_PID}"
   ```
3. **Propagasi Sinyal ke Child Processes:**
   Secara default, membunuh parent script tidak otomatis membunuh proses anaknya jika child dijalankan di background group berbeda. Parent wajib menyimpan PID (`$!`) dan mengirimkan terminasi eksplisit ke child saat sinyal shutdown diterima.
4. **Verifikasi Status Proses Menggunakan Sinyal 0:**
   Jangan parsing output teks `ps aux | grep ...` untuk mengecek ketersediaan proses. Gunakan syscall sinyal nul:
   ```bash
   if kill -0 "${TARGET_PID}" 2>/dev/null; then
       # Proses masih hidup dan user memiliki izin pengiriman sinyal
   fi
   ```
5. **Gunakan Notasi Symbolic Signal:**
   Gunakan nama sinyal eksplisit (`SIGTERM`, `SIGINT`, `SIGHUP`) alih-alih representasi numerik (`15`, `2`, `1`) untuk memastikan portabilitas lintas arsitektur sistem operasi (misal: Linux x86 vs SPARC/MIPS/macOS yang bisa memiliki pemetaan angka berbeda).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menggunakan `SIGKILL` (`kill -9`) secara Prematur
```bash
# SALAH: Membiasakan shutdown paksa
kill -9 $(cat /var/run/app.pid)
# Mengakibatkan file descriptor korup, lock file tertinggal, socket hanging.

# BENAR: Berikan grace period
PID=$(cat /var/run/app.pid)
kill -TERM "$PID"
TIMEOUT=10
while kill -0 "$PID" 2>/dev/null && [ $TIMEOUT -gt 0 ]; do
    sleep 1
    ((TIMEOUT--))
done
if kill -0 "$PID" 2>/dev/null; then
    kill -KILL "$PID" # Fallback mutlak
fi
```

### 2. Overwrite Sinyal Penting di Subshell
Menetapkan trap di dalam parent script tidak otomatis membuat subshell mengeksekusinya dengan cara yang sama: subshell mewarisi signal trap *reset* ke default actions untuk penanganan sinyal tertentu jika subshell dieksekusi secara asynchronous.

### 3. Mengabaikan Exit Status pada Trap Handler
```bash
# SALAH: Menimpa exit status asli
trap 'cleanup' ERR
cleanup() {
    rm -rf "$TMP_DIR"
    # Tanpa exit eksplisit, script bisa lanjut mengeksekusi baris berikutnya!
}

# BENAR: Preserve exit code
trap 'cleanup' ERR
cleanup() {
    local err_code=$?
    rm -rf "$TMP_DIR"
    exit "${err_code}"
}
```

### 4. Backgrounding Tanpa Manajemen `SIGINT` (Background Leak)
Menjalankan script yang mem-background task via `&`, namun saat terminal di-`Ctrl+C`, hanya parent-nya yang mati; background task tertinggal dan menjadi *orphan* yang diadopsi oleh init.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Job State Toggling Lab
* **Tujuan:** Memahami interaksi TTY, pembekuan proses (*stop*), dan pengalihan background/foreground.
* **Instruksi:**
  1. Jalankan perintah `cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32` di terminal interaktif.
  2. Suspensikan proses tersebut menggunakan keyboard interrupt `Ctrl+Z`.
  3. Periksa status proses melalui perintah `jobs -l`. Catat PID dan nomor job-nya.
  4. Lanjutkan eksekusi proses tersebut di latar belakang menggunakan `bg`.
  5. Amati output yang masih membanjiri stdout terminal.
  6. Tarik kembali proses tersebut ke foreground menggunakan `fg`.
  7. Hentikan total proses menggunakan `Ctrl+C`.

### Latihan 2: Membangun Resilient Temporary Workspace
* **Tujuan:** Mengimplementasikan trap handler yang anti-bocor untuk pengelolaan direktori `/tmp`.
* **Instruksi:**
  1. Buat script Bash bernama `safe_workspace.sh`.
  2. Di awal script, buat direktori acak `/tmp/sandbox.XXXXXX` menggunakan utility `mktemp -d`.
  3. Konfigurasi `trap` sehingga direktori tersebut **dijamin terhapus** saat:
     * Script selesai berjalan sukses.
     * Script diinterupsi oleh user (`Ctrl+C`).
     * Script dihentikan via perintah `kill` dari terminal lain.
     * Script mengalami unhandled error (`set -e`).
  4. Simulasikan loop pemrosesan data selama 30 detik di dalam direktori tersebut.
  5. Uji script Anda dengan mengirimkan `kill -15 <PID>` dari window terminal yang berbeda, dan pastikan direktori di `/tmp/` langsung terhapus bersih.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa yang terjadi pada level kernel terhadap memory space sebuah child process saat fungsi `fork()` dijalankan, dan mekanisme optimasi apa yang digunakan Linux modern?**
   * A. Kernel menyalin 100% isi RAM parent seketika ke physical frame baru secara sinkron.
   * B. Kernel membagikan pointer address space yang sama secara permanen tanpa isolasi data.
   * C. Kernel mengimplementasikan Copy-On-Write (COW); halaman memori ditandai read-only dan diduplikasi secara fisik hanya ketika salah satu proses mencoba menulis data.
   * D. Kernel mengompres memori child process dan menyimpannya di swap space sampai dipanggil `execve()`.

2. **Perintah Bash mana yang digunakan untuk memutuskan hubungan antara running background job dengan kontrol sesi shell saat ini, sehingga job tersebut tidak terbunuh saat shell ditutup (SIGHUP)?**
   * A. `kill -HUP %1`
   * B. `bg --detach`
   * C. `disown -h %1`
   * D. `detach -p %1`

3. **Manakah dari pasangan sinyal berikut yang secara mutlak TIDAK DAPAT di-intercept, di-block, atau di-ignore oleh user-space script menggunakan perintah `trap`?**
   * A. `SIGINT` dan `SIGTERM`
   * B. `SIGKILL` dan `SIGSTOP`
   * C. `SIGHUP` dan `SIGQUIT`
   * D. `SIGUSR1` dan `SIGUSR2`

4. **Kondisi apa yang mendefinisikan sebuah proses berada dalam status Zombie (`defunct`)?**
   * A. Proses yang kehabisan memori dan memasuki infinite loop.
   * B. Proses yang parent-nya telah mati, sehingga proses tersebut diadopsi oleh PID 1.
   * C. Proses yang telah selesai mengeksekusi tugasnya dan memanggil `exit()`, namun parent process belum membaca status terminasinya melalui syscall `wait()`/`waitpid()`.
   * D. Background process yang mencoba membaca input dari STDIN terminal.

5. **Diberikan potongan script berikut:**
   ```bash
   trap 'echo "Terminating"; rm -f /tmp/lock' 2 15
   sleep 100
   ```
   **Apa yang terjadi jika proses tersebut dikirim sinyal `kill -9 <PID>`?**
   * A. String `"Terminating"` tercetak, file `/tmp/lock` dihapus, proses mati.
   * B. Sinyal diabaikan karena tidak ada angka 9 di daftar trap.
   * C. Kernel langsung membunuh proses seketika; pesan tidak tercetak dan file `/tmp/lock` tetap tertinggal di filesystem.
   * D. Script membeku (*deadlock*) sampai komputer direstart.

---

### Kunci Jawaban & Rasional Teknis
1. **Jawaban: C** — Linux menggunakan strategi Copy-on-Write (COW). Halaman memori privat diduplikasi hanya saat terjadi operasi tulis (*write*), membuat pemanggilan `fork()` sangat efisien dan ringan.
2. **Jawaban: C** — Perintah internal `disown` (khususnya dengan flag `-h` untuk keep in job table tapi drop SIGHUP, atau default tanpa flag untuk menghapusnya dari active jobs table) memutus sinyal `SIGHUP` yang dikirimkan controlling terminal saat sesi SSH/TTY terminated.
3. **Jawaban: B** — Arsitektur POSIX menetapkan `SIGKILL` (9) dan `SIGSTOP` (19) sebagai sinyal kontrol absolut kernel. Sinyal ini langsung dieksekusi oleh OS scheduler tanpa dispatching ke user-space signal handling table suatu proses.
4. **Jawaban: C** — Status zombie terjadi ketika data struktur proses di PCB (*Process Control Block*) kernel harus tetap dipertahankan sampai parent-nya mengonsumsi exit status code via `wait()`. Jika parent lalai, proses tetap berada di process table dengan penanda `<defunct>`.
5. **Jawaban: C** — `SIGKILL` (nomor sinyal 9) tidak dapat ditangkap oleh `trap`. Kernel secara deterministik langsung mencabut resources CPU dan memori proses tersebut tanpa menjalankan fungsi handler yang didefinisikan script.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **POSIX Standard:** IEEE Std 1003.1-2017 (Volume System Interfaces - `fork`, `exec`, `sigaction`, `waitpid`).
* **Linux Manual Pages:**
  * `man 7 signal` — Tinjauan komprehensif seluruh POSIX signal architecture di Linux.
  * `man 2 waitpid` — Penjelasan mekanisme reaping dan zombie processes.
  * `man 1 bash` — Bagian *"SIGNALS"* dan *"JOB CONTROL"*.
* **Buku Referensi:**
  * *"Advanced Programming in the UNIX Environment"* (APUE) oleh W. Richard Stevens & Stephen A. Rago — Chapter 9: Process Relationships, Chapter 10: Signals.
  * *"The Linux Programming Interface"* oleh Michael Kerrisk — Bab 20-22 (Signals Concepts & Handlers).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Struktur Identitas Proses:** Ekosistem Unix mengelompokkan eksekusi berdasarkan hierarki hierarki PID, PPID, PGID (Process Group), dan SID (Session). Job Control Bash bekerja memanipulasi Process Group ID di atas controlling terminal.
2. **Siklus Hidup Proses:** Dimulai dari `fork()` untuk penggandaan, `execve()` untuk pergantian instruksi program, dan diakhiri dengan `exit()`. Parent bertanggung jawab melakukan *reaping* exit code melalui `wait()` agar proses tidak menggantung sebagai Zombie.
3. **Job Control Primitives:** Shell mengizinkan pemindahan eksekusi antara Foreground dan Background via operator `&`, `jobs`, `fg`, `bg`, serta pengiriman sinyal suspensi TTY via `Ctrl+Z` (`SIGTSTP`) dan terminasi via `Ctrl+C` (`SIGINT`).
4. **Resiliensi Script Berbasis Sinyal:** Penggunaan instruksi `trap` merupakan standar wajib arsitektur production Bash untuk menangkap sinyal interupsi (`SIGINT`, `SIGTERM`, `SIGHUP`) dan menjamin pembersihan resource (PID locks, scratch directories) via trap semantik `EXIT`.
5. **Determinisme Terminasi:** Utamakan pengiriman sinyal kooperatif `SIGTERM` (15) untuk memberikan waktu drain bagi child processes. Hindari penggunaan mutlak `SIGKILL` (9) secara serampangan guna memitigasi risiko data corruption dan dangling resource locks.

---

## SEKSI 17 — GLOSARIUM

* **Controlling Terminal (TTY):** Perangkat terminal karakter yang mengontrol input/output dari session group dan memancarkan sinyal keyboard ke foreground process group.
* **Idempotent:** Karakteristik operasi di mana eksekusi berulang kali dengan input yang sama akan memberikan hasil akhir yang identik tanpa memicu error atau side effect yang tidak diinginkan.
* **Orphan Process:** Kondisi di mana child process tetap hidup setelah parent process-nya telah mati terlebih dahulu. Orphan otomatis diadopsi oleh init system (PID 1).
* **Reaping:** Tindakan parent process memanggil fungsi syscall `wait()` atau `waitpid()` untuk membaca exit code child process yang sudah selesai, sehingga kernel dapat menghapus child tersebut sepenuhnya dari process table.
* **Signal Mask:** Kumpulan sinyal yang untuk sementara waktu diblokir oleh kernel agar tidak dikirimkan ke eksekusi thread/proses saat ini.
* **Subreaper:** Proses dalam hierarki Linux (selain PID 1) yang secara eksplisit mendaftarkan diri via `prctl(PR_SET_CHILD_SUBREAPER)` untuk mengadopsi orphan processes dari keturunan process tree-nya.
* **Zombie Process (`<defunct>`):** Proses yang sudah mati (`exit`), namun strukturnya masih tersimpan di kernel process table karena exit code-nya belum dibaca oleh parent process.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Setup Demonstrasi Langsung:** Saat mengajar, jalankan perintah visual monitoring di split tmux pane terpisah:
  ```bash
  watch -n 0.5 'ps -o pid,ppid,pgid,sid,stat,cmd -g $$'
  ```
  Ini memberi visualisasi langsung kepada peserta bagaimana PGID dan status proses (`S`, `R`, `T`, `Z`) berubah dinamis saat instruksi `Ctrl+Z`, `bg`, dan `fg` dieksekusi di pane utama.
* **Penekanan Edge Cases:**
  * Tunjukkan bahwa trap string kosong `trap '' SIGINT` berfungsi untuk **mengabaikan sinyal** secara permanen oleh shell dan child processes yang dieksekusi setelahnya.
  * Tunjukkan bahwa `trap '-' SIGINT` berfungsi untuk me-reset handling ke default kernel behavior.
* **Peringatan macOS vs Linux:** macOS menggunakan implementasi BSD Unix di mana sinyal numerik internal untuk beberapa sinyal real-time berbeda dengan Linux POSIX (meski nama sinyal fundamental tetap konsisten). Tekankan ke peserta didik untuk selalu menggunakan notasi penamaan alfabetik (`SIGINT`) daripada angka (`2`).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026):**
  * Rilis inisial materi Bab 07 Modul 01.
  * Penambahan arsitektur worker script production-ready dengan idempotency trap handling.
  * Standarisasi diagram ASCII alur state-machine proses dan TTY signal.
  * Pemutakhiran quiz dan hands-on exercises berbasis skenario real-world Linux system administration.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `BASH-CORE-06-03` — Advanced I/O Redirection, File Descriptors & Named Pipes (FIFOs)
* **Modul Berikutnya:** `BASH-CORE-07-02` — Inter-Process Communication (IPC), Bash Coprocesses (`coproc`) & Concurrency Parallelism Pattern
* **Indeks Jalur Belajar:** `BASH-CORE-FOUNDATIONS-TRACK` (Tingkat Pemahiran Lanjutan)