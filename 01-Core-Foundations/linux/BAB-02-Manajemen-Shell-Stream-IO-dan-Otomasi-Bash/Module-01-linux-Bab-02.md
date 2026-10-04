## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** LIN-COR-02-01
* **Nama Modul:** Manajemen Shell, Stream I/O, dan Otomasi Bash Lanjutan
* **Kategori:** 01-Core-Foundations
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Estimasi Waktu:** 8 Jam (Teori: 3 Jam, Hands-on Lab: 5 Jam)
* **Prasyarat:** Pemahaman dasar navigasi Linux CLI (Bab 01), manipulasi file/direktori, permission dasar (`chmod`, `chown`), dan konsep dasar proses Linux (`ps`, `kill`).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memanipulasi File Descriptor (FD):** Mengimplementasikan manipulasi stream tingkat rendah di luar FD standar (0, 1, 2) menggunakan sistem custom file descriptor (FD 3 hingga 9) untuk *multiplexing* logging dan pemisahan data stream.
2. **Menguasai Mekanisme Redirection & Pipeline:** Membedakan dan mengonfigurasi inter-process communication (IPC) melalui anonymous pipes, named pipes (FIFO), process substitution, dan redirection operator (`>`, `>>`, `&>`, `<&`, `|&`).
3. **Menerapkan Defensive Shell Scripting Standar Enterprise:** Membangun skrip Bash yang tahan terhadap kegagalan runtime (*fault-tolerant*) menggunakan *safety flags* (`set -euo pipefail`), traps (`SIGINT`, `SIGTERM`, `EXIT`, `ERR`), serta scoping variabel yang ketat.
4. **Mengoptimalkan Eksekusi Subshell dan Background Processing:** Mengidentifikasi overhead proses yang ditimbulkan oleh subshell vs grouping command (`( ... )` vs `{ ...; }`), serta mengontrol konkurensi proses latar belakang menggunakan *coproc*, *job control*, dan *semaphore* sederhana berbasis FIFO.
5. **Menghindari Perangkap Performa dan Keamanan Shell:** Mendiagnosis dan memitigasi kerentanan umum seperti *word splitting*, *globbing injection*, pembacaan file berbahaya via loop, serta *race condition* pada file temporer.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                [Linux Kernel VFS]
                                        │
                      ┌─────────────────┴─────────────────┐
                      ▼                                   ▼
             [File Descriptor Table]             [Inter-Process IPC]
             ├── 0: stdin                        ├── Anonymous Pipes (|)
             ├── 1: stdout                       ├── Named Pipes (FIFO)
             ├── 2: stderr                       └── Process Substitution (<())
             └── 3-9: Custom User FDs
                      │
                      ▼
          [Stream Redirection Engine]
          ├── Overwrite (>) / Append (>>)
          ├── Duplication (M>&N)
          ├── Merging (2>&1, |&)
          └── Here-Documents / Here-Strings (<<, <<<)
                      │
                      ▼
         [Defensive Bash Architecture]
         ├── Strict Execution Modes (set -euo pipefail)
         ├── Signal Trapping (trap ... EXIT/ERR/SIGTERM)
         ├── Subshell Lifecycle Management ((), {}, coproc)
         └── Variable & Parameter Expansion Safety
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam lingkungan produksi berbasis Linux modern—mulai dari node komputasi bare-metal, virtual machine cloud, hingga base image container micro-utilities—Bash tetap menjadi perekat (*glue code*) operasional yang paling fundamental. Kegagalan memahami perilaku internal shell sering kali memicu insiden berskala enterprise yang fatal. 

Contoh nyata kegagalan kritis meliputi:
* **Silent Failure pada CI/CD Pipeline:** Kegagalan salah satu perintah di tengah pipeline `curl ... | bash` yang tidak dideteksi karena flag `pipefail` tidak aktif, menyebabkan tahapan deployment terus berjalan dengan artifak yang korup.
* **Kehabisan Inode/Disk Space akibat Unbuffered Output:** Kegagalan memisahkan log aplikasi verbose dari log error standar, atau script loop yang membuka *unclosed file descriptor leak*.
* **Data Corruption akibat Subshell Variable Isolation:** Perubahan state penting yang dideklarasikan di dalam loop yang ter-pipe (`cat file | while read...`) hilang seketika saat subshell ditutup, menghasilkan variabel kosong pada payload eksekusi berikutnya.

Menguasai shell bukan sekadar mengetahui perintah `grep` atau `awk`, melainkan memahami secara presisi bagaimana Linux Kernel mengelola file descriptor, bagaimana system call `fork()` dan `execve()` berinteraksi dengan stream I/O, serta bagaimana mengkonstruksi otomasi yang deterministik, idempotensial, dan aman secara kriptografis maupun integritas data.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. File Descriptors dan Stream I/O
Di Linux, semua objek I/O direpresentasikan sebagai stream byte melalui abstraksi file descriptor (FD). Secara default, setiap proses yang dilahirkan oleh shell mewarisi tiga stream standar:
* **`0` (Standard Input / `stdin`):** Stream data masuk (default: keyboard/PTY).
* **`1` (Standard Output / `stdout`):** Stream data keluar normal (default: terminal display).
* **`2` (Standard Error / `stderr`):** Stream diagnostik dan pesan kegagalan (default: terminal display, unbuffered).

Bash menyediakan kemampuan untuk membuka, menutup, dan menduplikasi FD tambahan (3 hingga 9) menggunakan operator `exec`.

### 2. Redirection Operators dan Stream Duplication
Redirection adalah mekanisme modifikasi tujuan atau sumber file descriptor sebelum instruksi command dieksekusi:
* `N> file`: Menuliskan output FD `N` ke `file` (truncate).
* `N>> file`: Menuliskan output FD `N` ke `file` (append).
* `M>&N`: Mengarahkan file descriptor `M` ke lokasi yang ditunjuk oleh FD `N` (duplikasi pointer file description di level kernel).
* `&> file` atau `>& file`: Redirection gabungan `stdout` dan `stderr` ke `file`.

### 3. Pipelines dan Process Substitution
* **Pipeline (`|`):** Menghubungkan FD 1 (`stdout`) dari proses kiri ke FD 0 (`stdin`) dari proses kanan melalui kernel buffer terisolasi (*pipe buffer*, umumnya 64KB di Linux).
* **Process Substitution (`<(command)` atau `>(command)`):** Memungkinkan stream output sebuah proses diperlakukan sebagai argumen path file (diabstraksikan melalui `/dev/fd/N` atau named pipes). Ini memecahkan limitasi pipeline standar yang memaksa eksekusi dalam subshell terisolasi.

### 4. Subshell Lifecycle vs Group Command
* **Subshell `( ... )`:** Melakukan `fork()` penuh atas parent shell. Modifikasi variabel, direktori kerja (`cd`), dan environment di dalamnya tidak berdampak pada parent shell.
* **Group Command `{ ...; }`:** Menjalankan kumpulan perintah dalam context parent shell saat ini tanpa melakukan `fork()` proses shell baru. State variabel tetap bertahan.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Anatomi System Call pada Pipeline dan Redirection
Saat shell mengeksekusi pipeline kompleks seperti `cat /var/log/syslog | grep -E "ERROR" > error.log`, kernel Linux mengeksekusi serangkaian system call:

1. **`pipe(pipefd)`:** Shell memanggil system call `pipe()` untuk membuat anonymous pipe di kernel memory. Return value berupa dua FD: `pipefd[0]` (read-end) dan `pipefd[1]` (write-end).
2. **`fork()`:** Shell membuat dua child process terpisah (satu untuk `cat`, satu untuk `grep`).
3. **`dup2(oldfd, newfd)`:**
   * Pada child process 1 (`cat`): kernel memanggil `dup2(pipefd[1], STDOUT_FILENO)`. Kini stdout `cat` tersambung ke write-end dari pipe. File descriptor pipe aslinya ditutup via `close()`.
   * Pada child process 2 (`grep`): kernel memanggil `dup2(pipefd[0], STDIN_FILENO)`. Kini stdin `grep` membaca dari read-end pipe.
   * Untuk redirection `> error.log`, child process 2 membuka file target via `open("error.log", O_WRONLY|O_CREAT|O_TRUNC, 0644)` yang mengembalikan file descriptor sementara, lalu memanggil `dup2(file_fd, STDOUT_FILENO)`.
4. **`execve()`:** Parent memanggil `execve()` untuk me-replace memory image child process dengan binary executable `/bin/cat` dan `/bin/grep`.
5. **Synchronization:** Parent shell memanggil `wait4()` atau `waitpid()` untuk menunggu hingga proses dalam pipeline selesai, serta mengumpulkan *exit status code*.

### 2. Mekanika Strict Execution Mode (`set -euo pipefail`)
* **`-e` (`errexit`):** Shell segera menghentikan eksekusi skrip jika ada command yang mengembalikan status non-zero, kecuali jika command tersebut merupakan bagian dari conditional testing (`if`, `while`, `until`, atau diikuti `||`).
* **`-u` (`nounset`):** Menolak referensi ke variabel yang belum diinisialisasi dan segera melemparkan error fatal ke `stderr`, mencegah skrip mengeksekusi command destruktif seperti `rm -rf "$TARGET_DIR/"` saat variabel `$TARGET_DIR` tidak sengaja terlewat.
* **`-o pipefail`:** Secara default, pipeline hanya mengembalikan exit code dari command *terakhir*. Jika diaktifkan, pipeline akan mengembalikan exit code dari command terakhir yang bernilai non-zero, memastikan error di awal pipeline terdeteksi.
* **`IFS=$'\n\t'`:** Mengatur *Internal Field Separator* default menjadi newline dan tab saja (menghilangkan spasi), meminimalkan risiko kecelakaan eksekusi saat memproses nama file yang mengandung karakter spasi.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Manajemen Stream I/O, File Descriptor Redirection, dan Subshell Isolation

```text
                  PROCESS BOUNDARY: PARENT SHELL
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  [File Descriptor Table]                                        │
│  FD 0 (stdin)  ───────> Keyboard Device Driver (/dev/pts/0)     │
│  FD 1 (stdout) ───────> Pseudo-Terminal Display (/dev/pts/0)    │
│  FD 2 (stderr) ───────> Pseudo-Terminal Display (/dev/pts/0)    │
│  FD 3 (custom) ───┐                                             │
│                   │                                             │
└───────────────────┼─────────────────────────────────────────────┘
                    │ exec 3> /var/log/audit.log
                    ▼
          ┌─────────────────────┐
          │  /var/log/audit.log │
          └─────────────────────┘

===================================================================
                   PIPELINE & PROCESS SUBSTITUTION
===================================================================

Command:  grep "WARN" <(journalctl -u nginx) | tee nginx_warn.log

                        Parent Bash Process
                                 │
           ┌─────────────────────┴─────────────────────┐
           │ (Process Substitution: fork)              │ (Pipeline: fork)
           ▼                                           ▼
┌──────────────────────┐                     ┌────────────────────┐
│ Child 1: journalctl  │                     │ Child 2: Pipeline  │
│                      │                     │                    │
│ stdout (FD 1)        │                     │                    │
└──────────┬───────────┘                     └─────────┬──────────┘
           │ dup2()                                    │
           ▼                                           ▼
  ┌─────────────────┐                        ┌───────────────────┐
  │ /dev/fd/63      │                        │ Child 2a: grep    │
  │ (Named Pipe/    │ ─── read argument ───> │ stdin (FD 0) <────┘
  │ Kernel Buffer)  │                        │ stdout (FD 1) ────┐
  └─────────────────┘                        └───────────────────┤
                                                                 │
                                                    kernel pipe  │ (64 KB)
                                                                 │
                                             ┌───────────────────┘
                                             ▼
                                     ┌───────────────────┐
                                     │ Child 2b: tee     │
                                     │ stdin (FD 0)      │
                                     │   ├── FD 1 ───────┼─> /dev/pts/0
                                     │   └── FD 3 ───────┼─> nginx_warn.log
                                     └───────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut demonstrasi manipulasi Stream I/O dan Custom File Descriptor secara langsung di Bash shell:

### 1. Membuat dan Menggunakan Custom FD

```bash
# Buka File Descriptor 3 untuk penulisan log
exec 3> /tmp/custom_stream.log

# Tulis pesan langsung ke FD 3 tanpa mengubah stdout terminal
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Custom stream initialized." >&3

# Periksa apakah FD 3 aktif di sistem
ls -l /proc/$$/fd/3
# Output: l-wx------ 1 user user 64 Feb 24 10:00 /proc/$$/fd/3 -> /tmp/custom_stream.log

# Tulis command reguler ke terminal dan ke FD 3 secara manual
echo "Pesan ini tampil di terminal"
echo "Pesan ini diam-diam masuk ke custom stream" >&3

# Tutup File Descriptor 3
exec 3>&-

# Validasi penutupan: mencoba menulis ke FD 3 akan menghasilkan error
echo "Tes error" >&3
# Output: bash: 3: Bad file descriptor
```

### 2. Mengatasi Jebakan Subshell dengan Process Substitution

```bash
#!/usr/bin/env bash

# Skenario: Menghitung total baris dan mengakumulasikan nilai
counter=0

# PENDEKATAN SALAH (Pipeline standar menciptakan subshell):
printf "baris1\nbaris2\nbaris3\n" | while read -r line; do
    ((counter++))
done
echo "Counter via Pipeline: $counter"
# Output Counter: 0 (Variabel di parent tidak terpengaruh subshell!)

# PENDEKATAN BENAR (Process Substitution mengeksekusi while di parent shell):
while read -r line; do
    ((counter++))
done < <(printf "baris1\nbaris2\nbaris3\n")

echo "Counter via Process Substitution: $counter"
# Output Counter: 3 (Nilai state berhasil dipertahankan)
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Di bawah ini adalah skrip operasional kelas produksi: Skrip pencadangan sistem transaksional yang mengimplementasikan defensive scripting (`set -euo pipefail`), signal handling (`trap`), process substitution, redirection FD multi-channel, serta pencegahan race-condition.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script Name : secure_backup_engine.sh
# Description : Melakukan snapshot direktori, enkripsi gpg, dan verifikasi hash
#               dengan isolated error routing dan structured stream logging.
# ==============================================================================

# Aktifkan strict mode
set -euo pipefail
IFS=$'\n\t'

# ------------------------------------------------------------------------------
# KONSTANTA DAN VARIABEL GLOBAL
# ------------------------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "${0}")"
readonly RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
readonly BACKUP_SRC="/etc"
readonly DEST_DIR="/tmp/backups"
readonly ARCHIVE_OUT="${DEST_DIR}/backup_${RUN_ID}.tar.gz"
readonly LOG_FILE="/tmp/backup_engine_${RUN_ID}.log"
readonly ERR_FILE="/tmp/backup_engine_${RUN_ID}.err"

# Flag debugging (0: false, 1: true)
readonly DEBUG=1

# ------------------------------------------------------------------------------
# INISIALISASI CUSTOM FILE DESCRIPTOR
# ------------------------------------------------------------------------------
# FD 3 -> Standard Audit Log (Append)
# FD 4 -> Standard Error Diagnostics (Append)
mkdir -p "${DEST_DIR}"
exec 3>> "${LOG_FILE}"
exec 4>> "${ERR_FILE}"

# ------------------------------------------------------------------------------
# CLEANUP DAN TRAP HANDLERS
# ------------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    # Nonaktifkan trap untuk mencegah looping error handling
    trap - EXIT ERR SIGINT SIGTERM

    if [[ ${exit_code} -ne 0 ]]; then
        log_error "Proses abnormal terhenti dengan status exit code: ${exit_code}"
        # Bersihkan artifak parsial jika ada
        [[ -f "${ARCHIVE_OUT}" ]] && rm -f "${ARCHIVE_OUT}"
    else
        log_info "Proses pembersihan selesai. Pipeline sukses tanpa error."
    fi

    # Tutup File Descriptor custom
    exec 3>&- 2>/dev/null || true
    exec 4>&- 2>/dev/null || true

    exit "${exit_code}"
}

# Trap menangkap EXIT (normal/abnormal), ERR, SIGINT, dan SIGTERM
trap cleanup EXIT
trap 'log_error "Interupsi sinyal terdeteksi (SIGINT/SIGTERM)!"; exit 130' SIGINT SIGTERM
trap 'log_error "Error fatal terjadi pada baris ${BASH_LINENO[0]} pada command: ${BASH_COMMAND}"' ERR

# ------------------------------------------------------------------------------
# HELPER LOGGING
# ------------------------------------------------------------------------------
log_info() {
    local msg="[INFO] [$(date '+%Y-%m-%dT%H:%M:%S%z')] [${SCRIPT_NAME}] : $*"
    echo "${msg}" >&3
    echo "${msg}" >&1
}

log_error() {
    local msg="[ERROR] [$(date '+%Y-%m-%dT%H:%M:%S%z')] [${SCRIPT_NAME}] (LINE ${BASH_LINENO[0]}) : $*"
    echo "${msg}" >&4
    echo "${msg}" >&2
}

log_debug() {
    if [[ "${DEBUG}" -eq 1 ]]; then
        local msg="[DEBUG] [$(date '+%Y-%m-%dT%H:%M:%S%z')] : $*"
        echo "${msg}" >&3
    fi
}

# ------------------------------------------------------------------------------
# BUSINESS LOGIC PIPELINE
# ------------------------------------------------------------------------------
main() {
    log_info "Memulai backup pipeline untuk: ${BACKUP_SRC}"

    # Validasi dependensi
    local required_bins=("tar" "gzip" "sha256sum")
    for bin in "${required_bins[@]}"; do
        if ! command -v "${bin}" >/dev/null 2>&1; then
            log_error "Dependency binari tidak ditemukan: ${bin}"
            exit 127
        fi
    done

    # Validasi direktori target
    if [[ ! -d "${BACKUP_SRC}" ]]; then
        log_error "Source direktori tidak ditemukan: ${BACKUP_SRC}"
        exit 2
    fi

    log_debug "Membuat arsip terkompresi menggunakan tar stream..."

    # Menjalankan tar dengan redirection stderr ke FD 4, sambil mengekstrak sha256 checksum secara parallel
    # Menggunakan Process Substitution dan 'tee' tanpa menciptakan race condition file temporer
    local checksum=""
    {
        tar --exclude='/etc/shadow*' -czf - "${BACKUP_SRC}" 2>&4 \
            | tee "${ARCHIVE_OUT}" \
            | sha256sum > >(read -r sum _ && echo "${sum}" > "${ARCHIVE_OUT}.sha256")
    }

    # Beri jeda kernel sinkronisasi pipe completion
    wait

    if [[ ! -s "${ARCHIVE_OUT}" ]]; then
        log_error "Hasil arsip kosong atau tidak terbentuk: ${ARCHIVE_OUT}"
        exit 3
    fi

    checksum=$(awk '{print $1}' "${ARCHIVE_OUT}.sha256")
    log_info "Arsip berhasil dibuat: ${ARCHIVE_OUT}"
    log_info "SHA256 Checksum: ${checksum}"

    # Verifikasi integritas menggunakan Process Substitution
    log_info "Memverifikasi integritas checksum..."
    if ! sha256sum --check --status <(echo "${checksum}  ${ARCHIVE_OUT}"); then
        log_error "Integritas checksum gagal divalidasi!"
        exit 4
    fi

    log_info "Verifikasi sukses. Ukuran file: $(stat -c%s "${ARCHIVE_OUT}") bytes."
}

# Jalankan skrip
main "$@"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Metrik | Bash Advanced Scripting | Python / Golang CLI Utility | Trade-Off Decision Point |
| :--- | :--- | :--- | :--- |
| **Overhead Execution** | Sangat rendah untuk glue logic sederhana; overhead tinggi jika memanggil ribuan proses external (`fork/exec`). | Overhead runtime startup lebih tinggi, namun sangat cepat untuk iterasi data besar di memori. | Gunakan Bash jika >80% tugas murni memanggil binary Linux bawaan. Beralih ke Python/Go jika butuh manipulasi objek JSON kompleks atau multithreading murni. |
| **Portabilitas & Dependencies** | Bergantung pada versi Bash (`v3` di macOS legacy vs `v4/v5` di modern Linux) dan ketersediaan Coreutils. | Bergantung pada runtime environment (Python runtime / binary statically linked Go). | Gunakan POSIX shell (`/bin/sh`) jika harus kompatibel lintas sistem POSIX murni; gunakan Bash 4+ jika infrastruktur terstandarisasi di Linux. |
| **Subshell Memory Isolation** | Variabel dalam subshell tidak bocor ke parent (aman), namun komunikasi antar subshell memerlukan IPC (pipe/file). | Shared memory atau concurrency primitives (threads, channels) mudah dikontrol dalam satu proses. | Bash memaksa *fail-safe isolation* secara natural, tetapi IPC rumit jika data yang dibagi memiliki struktur kompleks. |
| **I/O Buffering Control** | Bash bergantung penuh pada *libc unbuffered/block buffered mechanism* bawaan command yang dipanggil. | Kontrol presisi atas I/O buffer di application level (`flush()`, sync I/O). | Skrip Bash rentan terhadap pipe buffering delay (`stdbuf` sering kali dibutuhkan untuk manipulasi realtime stream). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Header Standar Enterprise:**
   Selalu awali skrip Bash dengan:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   IFS=$'\n\t'
   ```
2. **Karantina Variabel dengan Defensive Quoting:**
   Selalu bungkus variabel dan substitusi perintah dengan tanda kutip ganda (`"$var"`, `"$(cmd)"`). Jangan biarkan variabel terbuka tanpa kutip kecuali memang sengaja mengeksploitasi word splitting.
3. **Validasi Ketersediaan Variabel Terlebih Dahulu:**
   Jika variabel mungkin tidak terisi, sediakan nilai fallback bawaan daripada memicu kegagalan fatal:
   ```bash
   TARGET_DIR="${1:-/tmp/fallback}"
   ```
4. **Pisahkan Standard Output dan Error Stream:**
   Data yang menjadi output utama skrip harus dikirim ke `stdout` (FD 1), sedangkan pesan status, warning, atau log diagnostik harus selalu diarahkan ke `stderr` (`>&2`) atau custom FD. Ini memungkinkan downstream tool mengonsumsi output via pipe tanpa polusi string log.
5. **Gunakan Trap untuk Penanganan Sumber Daya:**
   Jangan pernah meninggalkan file temporer tak terhapus di `/tmp`. Alokasikan file sementara via `mktemp` dan daftarkan penghapusannya di fungsi `cleanup` yang diikat ke trap `EXIT`.
6. **Hindari `cat` yang Tidak Perlu (*Useless Use of Cat - UUOC*):**
   Gunakan redirection langsung ke binary (`grep "foo" < file.txt` daripada `cat file.txt | grep "foo"`). Ini menghemat satu system call `fork()` dan alokasi pipe kernel.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Kehilangan Scope Variabel Akibat Pipeline Subshell
```bash
# SALAH
found_records=0
journalctl -u my_service | while read -r line; do
    ((found_records++))
done
echo "Total: $found_records" # Output selalu 0!

# BENAR (Proses dieksekusi di context parent shell)
found_records=0
while read -r line; do
    ((found_records++))
done < <(journalctl -u my_service)
echo "Total: $found_records"
```

### 2. Parsing Output `ls` untuk Operasi File
```bash
# SALAH: Hancur jika nama file memiliki karakter spasi, glob wildcard, atau newline
for file in $(ls *.log); do
    rm "$file"
done

# BENAR: Gunakan globbing native Bash
for file in ./*.log; do
    [[ -e "$file" ]] || continue # Tangani skenario jika tidak ada file yang cocok
    rm -- "$file"
done
```

### 3. Redirection Order yang Keliru
```bash
# SALAH: FD 2 diarahkan ke FD 1 lama (terminal), baru kemudian FD 1 diarahkan ke file.
# Hasil: stderr tetap muncul di layar, tidak tersimpan di file!
cmd > output.log 2>&1  # <-- INI YANG BENAR
cmd 2>&1 > output.log  # <-- INI SALAH! (Order of redirection matters)
```

### 4. Mengabaikan Exit Code pada Pipeline tanpa `pipefail`
```bash
# Tanpa set -o pipefail
non_existent_command | echo "Data"
echo $? # Output: 0 (Padahal non_existent_command mengembalikan status 127)
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Exercise 1: Pipeline Diagnostics dan FD Multiplexing
* **Tujuan:** Membuat wrapper skrip yang memisahkan error stream ke file terpisah dan menduplikat output normal ke layar sekaligus file audit tanpa menggunakan utility `tee`.

1. Buat direktori kerja baru: `mkdir -p ~/bash-advanced-lab && cd ~/bash-advanced-lab`.
2. Buat skrip bernama `fd_multiplex.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   
   exec 3> audit_stdout.log
   exec 4> audit_stderr.log
   
   # Simulasikan multi-channel writing
   echo "Pesan sistem normal 1" | tee /dev/fd/3
   echo "Pesan error terdeteksi!" >&4
   echo "Pesan sistem normal 2" | tee /dev/fd/3
   
   exec 3>&-
   exec 4>&-
   ```
3. Eksekusi skrip: `chmod +x fd_multiplex.sh && ./fd_multiplex.sh`.
4. **Verifikasi:** Periksa isi `audit_stdout.log` dan `audit_stderr.log`. Pastikan pesan error terisolasi secara sempurna dan tidak tercampur di stdout.

### Exercise 2: Real-time Concurrency Control Menggunakan Named Pipe (FIFO)
* **Tujuan:** Mengimplementasikan pola Concurrency Semaphore menggunakan FIFO untuk membatasi eksekusi paralel maksimal 3 job sekaligus di Bash murni.

1. Buat skrip bernama `fifo_semaphore.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   
   MAX_WORKERS=3
   SEMAPHORE="/tmp/bash_sem.$$"
   mkfifo "${SEMAPHORE}"
   exec 9<>"${SEMAPHORE}"
   rm -f "${SEMAPHORE}"
   
   # Isi semaphore dengan token
   for ((i=1; i<=MAX_WORKERS; i++)); do
       echo >&9
   done
   
   # Jalankan 10 job paralel, dibatasi 3 proses konkurensi
   for j in {1..10}; do
       read -u 9 # Ambil slot token (blocking jika buffer kosong)
       {
           echo "[$(date +%T)] Memulai Worker $j..."
           sleep 2
           echo "[$(date +%T)] Selesai Worker $j"
           echo >&9 # Kembalikan slot token
       } &
   done
   
   wait
   exec 9>&- # Tutup FD
   echo "Seluruh batch job selesai."
   ```
2. Eksekusi skrip: `chmod +x fifo_semaphore.sh && ./fifo_semaphore.sh`.
3. **Verifikasi:** Amati timestamp output. Pastikan worker dieksekusi tepat maksimal 3 job dalam jendela waktu 2 detik yang sama.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Pilihan Ganda

#### 1. Perhatikan potongan kode berikut:
```bash
set -eo pipefail
false | true
echo "SUCCESS"
```
Apa output yang dihasilkan dari potongan kode di atas ketika dieksekusi di Bash?
* A. `SUCCESS`
* B. Tidak mencetak apapun dan exit dengan status code 1.
* C. Muncul syntax error pada tanda pipe.
* D. Program mengalami infinite loop.

#### 2. Apa perbedaan fungsional mendasar antara operator `>` dan `<&` di Bash?
* A. `>` digunakan untuk membaca file, sedangkan `<&` digunakan untuk menulis.
* B. `>` mengalihkan output stream ke target file, sedangkan `<&` menduplikasi input file descriptor.
* C. `>` membuat anonymous pipe, sedangkan `<&` membuat named pipe FIFO.
* D. Tidak ada perbedaan, keduanya operator redirection standar POSIX.

#### 3. Mengapa script berikut tidak mengupdate variabel `COUNT` di layar terminal parent?
```bash
COUNT=0
cat data.txt | while read -r line; do
    ((COUNT++))
done
echo "Total: $COUNT"
```
* A. Karena `COUNT` adalah reserved keyword di Bash.
* B. Karena `while` loop tidak mendukung operasi aritmatika internal.
* C. Karena pipeline (`|`) memaksa child loop dieksekusi di dalam `subshell` hasil kernel `fork()`.
* D. Karena instruksi `cat` menghapus buffer stdin milik parent process.

---

### Jawaban dan Rasionalisasi

* **Soal 1:** **B (Tidak mencetak apapun dan exit dengan status 1).**
  * *Rasional:* Flag `-o pipefail` memaksa status exit dari pipeline diambil dari command paling kanan yang gagal (di sini `false` bernilai 1). Karena flag `-e` aktif, kegagalan non-zero pada pipeline tersebut langsung memutus eksekusi skrip secara mendadak sebelum mencapai perintah `echo "SUCCESS"`.
* **Soal 2:** **B (`>` mengalihkan output stream ke file, sedangkan `<&` menduplikasi input file descriptor).**
  * *Rasional:* Operator `>` memanggil `open()` dan `dup2()` untuk mengaitkan stdout ke vnode file, sementara `<&` menggunakan system call `dup2()` untuk menduplikasi reference file descriptor input (misal `0<&3`).
* **Soal 3:** **C (Pipeline memaksa child loop dieksekusi di subshell hasil fork).**
  * *Rasional:* Di Bash, setiap command dalam segmen pipeline dijalankan di dalam subshell terisolasi. Variabel `COUNT` yang bertambah nilainya berada pada memori child process yang di-destruct oleh kernel begitu pipeline berakhir. Parent Bash tetap mempertahankan nilai `COUNT=0` miliknya.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **POSIX Standard IEEE Std 1003.1-2017:** Shell Command Language Reference (Section 2: Shell Architecture & Redirection).
* **GNU Bash Reference Manual (v5.2):** *Redirection, Builtin Commands, and Execution Environment*. Tersedia di: `https://www.gnu.org/software/bash/manual/`.
* **Linux Programmer's Manual:** System Call References:
  * `man 2 pipe`
  * `man 2 dup2`
  * `man 2 fork`
  * `man 2 execve`
* **Buku:** Arnold Robbins & Nelson H.F. Beebe, *Classic Shell Scripting: Hidden Commands that Unlock the Power of Unix*, O'Reilly Media.
* **Buku:** Chet Ramey & Brian Fox, *The GNU Bash Reference Manual*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Modul ini telah mengupas tuntas arsitektur stream I/O dan otomasi Bash tingkat lanjut:
1. **Linux VFS File Descriptor Abstraction:** Stream 0, 1, dan 2 adalah pondasi, namun ketersediaan FD 3 hingga 9 memberikan kapabilitas pemisahan logging dan multiplexing stream secara native di tingkat kernel tanpa software pihak ketiga.
2. **Kernel IPC via Streams:** Anonymous pipe (`|`) dan process substitution (`<()`) memanfaatkan system call `pipe()` dan `dup2()`, di mana pemahaman akan alokasi subshell sangat penting untuk mencegah bug isolasi variabel.
3. **Defensive Shell Engineering:** Penggunaan `set -euo pipefail` bersamaan dengan `trap` adalah standar non-negotiable dalam rekayasa sistem produksi untuk menjamin skrip berperilaku deterministik dan mampu memulihkan diri (*self-cleanup*) saat kegagalan sistem terjadi.

---

## SEKSI 17 — GLOSARIUM

* **File Descriptor (FD):** Angka integer non-negatif yang dialokasikan oleh kernel sebagai handle penunjuk sumber data I/O terbuka (file, soket jaringan, terminal PTY, pipe) di level VFS.
* **Subshell:** Child instance dari shell process yang dibuat via system call `fork()`. Subshell mewarisi environment variabel parent, namun isolasi memori kernel mencegah modifikasi balik ke parent.
* **Process Substitution:** Mekanisme Bash yang mengekspos output suatu proses sebagai nama file sementara di sistem VFS (`/dev/fd/XX`), memungkinkan command yang hanya menerima input argumen file dapat membaca data pipe secara direct.
* **Trap:** Shell builtin command yang menginstruksikan shell untuk mengeksekusi instruksi khusus bila menerima sinyal asynchronous OS tertentu (`SIGINT`, `SIGTERM`, atau pseudo-signal seperti `EXIT`, `ERR`).
* **FIFO (Named Pipe):** Entri file khusus pada filesystem yang bekerja dengan filosofi First-In, First-Out, bertindak sebagai mekanisme Inter-Process Communication (IPC) antar proses independen tanpa shared memory.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Hambat Umum Peserta:** Peserta biasanya kesulitan membedakan antara `2>&1 > file` dengan `> file 2>&1`. Tekankan bahwa redirection dievaluasi oleh shell dari **kiri ke kanan** sebelum instruksi program dijalankan. Gambarkan layout pointer file descriptor secara visual di papan tulis/slide.
* **Pemberian Materi Lab:** Pastikan peserta tidak menguji skrip loop `set -e` di sesi terminal login interaktif utama mereka, karena skrip yang exit dapat langsung menutup sesi shell/SSH. Sarankan untuk selalu membungkus latihan dalam skrip file terpisah (`.sh`) atau subshell manual `bash -c '...'`.
* **Fokus Audit Keamanan:** Beri penekanan ekstra pada bahaya word splitting ketika tidak menyertakan quote pada variabel path file (`"$TARGET"` vs `$TARGET`), terutama di lingkungan produksi di mana user eksternal bisa meng-upload file dengan spasi atau karakter newline.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Februari 2025):**
  * Rilis modul perdana kurikulum Core Linux.
  * Penyusunan modul komprehensif 20 seksi standar GEMINI.md.
  * Penambahan skrip enterprise snapshot backup engine dengan dynamic trap dan process substitution.
  * Penambahan latihan hands-on token semaphore berbasis FIFO.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** [LIN-COR-01-02: Manajemen Sistem Berkas, Perizinan Lanjutan, dan Kontrol Akses ACL](../01-Core-Foundations/LIN-COR-01-02.md)
* **Modul Berikutnya:** [LIN-COR-02-02: Anatomi Proses Linux, Signal Handling, dan Manajemen Daemon Systemd](../01-Core-Foundations/LIN-COR-02-02.md)