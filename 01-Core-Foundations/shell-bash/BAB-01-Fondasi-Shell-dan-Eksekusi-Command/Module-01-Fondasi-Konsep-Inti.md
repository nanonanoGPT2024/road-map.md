# Bab 01 Module 01: Arsitektur Shell Bash, Lingkungan Eksekusi, dan Interaksi Kernel

---

## 1. Title Header & Metadata

* **Topik**: Arsitektur Shell Bash, Siklus Hidup Eksekusi Perintah, dan Batas Sistem (Kernel Boundary)
* **Jalur Kurikulum**: Shell Scripting & Systems Automation
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
* **Estimasi Waktu Membaca**: 45 menit
* **Prasyarat**: Pemahaman dasar command-line Linux, arsitektur OS (Virtual Memory, Process Table), dan fundamental POSIX File Descriptors.

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis** siklus parsing Bash (Tokenization, Expansions, Redirection) sebelum instruksi diserahkan ke kernel Linux.
2. **Mengidentifikasi** perbedaan mendasar antara *Builtin Commands*, *Shell Functions*, *Aliases*, dan *External Executables* berdasarkan alokasi memori dan jejak *system calls*.
3. **Mendiagnosis** mekanisme isolasi proses melalui penelusuran *syscall* (`fork`, `execve`, `clone`, `pipe`, `dup2`, `waitpid`).
4. **Mengisolasi** state lingkungan eksekusi antara parent shell, subshell, dan child process untuk mencegah *environment variable leakage*.
5. **Menulis** skrip deterministik yang aman dari jebakan evaluasi Bash menggunakan konfigurasi *Defensive Execution Flags*.

---

## 3. Target Audience & Prerequisites

Modul ini dirancang untuk:
* **Systems Engineer & DevOps Specialist** yang mengelola pipeline otomatisasi dan runtime infrastruktur berbasis Linux.
* **Backend Developer & Site Reliability Engineer (SRE)** yang ingin memahami implikasi performa dan keamanan dari instruksi Bash skala produksi.

### Prasyarat Teknis
* Akses terminal Linux dengan Bash v4.4+ atau v5.x.
* Utilitas sistem: `strace`, `lsof`, `procps` (`ps`), dan `gcc` (opsional untuk bedah syscall).
* Kemampuan membaca representasi memori proses Linux (`/proc/$PID/`).

---

## 4. Concept Overview

GNU Bash (*Bourne-Again SHell*) bukan sekadar penyedia prompt perintah interaktif, melainkan sebuah **Command Language Interpreter** yang mengimplementasikan spesifikasi IEEE Std 1003.1 (POSIX.1-2017) dengan ekstensi bahasa fungsional dan prosedural. 

Ketika perintah dimasukkan ke dalam Bash:
1. Bash memproses teks input melalui serangkaian tahapan parser statis dan dinamis.
2. Bash menentukan apakah operasi dapat dipenuhi langsung di dalam ruang memorinya sendiri (*in-process*) atau memerlukan pembuatan proses baru (*forking*).
3. Jika eksternal, Bash bertindak sebagai *process orchestrator* yang berinteraksi langsung dengan kernel melalui antarmuka *System Call* (syscall) C-API/POSIX.

Menguasai arsitektur internal Bash berarti menghilangkan paradigma *black-box scripting*. Anda tidak lagi memandang baris perintah sebagai teks ajaib yang dieksekusi begitu saja, melainkan sebagai untaian instruksi yang memanipulasi Process Table, File Descriptor Table, Signal Masks, dan Virtual Address Space.

---

## 5. Why Does This Matter?

Dalam automasi skala industri, kesalahan pemahaman arsitektur shell berujung pada konsekuensi katastropik:

* **Involusi Performa (Fork Overhead)**: Mengabaikan perbedaan *builtin* vs *external binary* dalam perulangan jutaan baris menghasilkan jutaan operasi `fork()/clone()` dan `execve()`. Konteks switching ini membebani CPU Scheduler dan menghabiskan entropy thread PID.
* **Kebocoran State & Variabel Tak Terduga**: Modifikasi variabel di dalam pipeline (misal: `cat file | while read line; do ... done`) hilang begitu perulangan selesai, karena eksekusi pipeline secara default dialokasikan ke dalam *subshell* terpisah.
* **Security Exploit (Injection)**: Ketidaktahuan atas urutan *Shell Expansions* (terutama Word Splitting dan Pathname Expansion) merupakan celah utama lahirnya kerentanan eksekusi arbitrer (*Command Injection* dan *Globbing Arbitrary Argument Injection*).
* **Zombie & Orphaned Processes**: Kegagalan mengelola sinyal dan *file descriptors* pada subshell memicu kebocoran memori kernel dan proses zombie yang memblokir resource sistem.

---

## 6. What Is It? (Deep-Dive Mechanism)

### 6.1 Fase Parsing dan Translasi Instruksi Bash
Sebelum sebuah perintah dieksekusi oleh kernel, Bash membedah stream karakter melalui algoritma 12 tahap deterministik:

1. **Tokenization (Lexical Analysis)**: Memisahkan karakter stream menjadi *words* dan *operators* berdasarkan `$IFS` (*Internal Field Separator*) dan metakarakter (`|`, `&`, `;`, `(`, `)`, `<`, `>`).
2. **Quote Removal (Parsing awal)**: Mengidentifikasi bagian string yang dilindungi oleh single quotes (`'...'`), double quotes (`"..."`), atau backslashes (`\`).
3. **Alias Expansion**: Mengevaluasi kata pertama terhadap tabel alias (jika bukan non-interactive script atau jika `expand_aliases` diaktifkan).
4. **Brace Expansion**: Mengembangkan pola seperti `a{b,c}d` menjadi `abd acd`. Operasi ini terjadi murni pada level string sebelum ekspansi variabel.
5. **Tilde Expansion**: Mengubah `~` menjadi direktori target (`$HOME` atau target `passwd`).
6. **Parameter and Variable Expansion**: Mengganti ekspresi `$VAR` atau `${VAR}` dengan nilai aktualnya.
7. **Command Substitution**: Menjalankan sub-perintah `$(command)` atau `` `command` `` dan menempatkan output teks standar ke posisi token tersebut.
8. **Arithmetic Expansion**: Menghitung ekspresi numerik `$(( expression ))`.
9. **Process Substitution**: Mengonfigurasi named pipes atau file virtual `/dev/fd/N` melalui `<(command)` atau `>(command)`.
10. **Word Splitting**: Hasil dari ekspansi parameter, substitusi perintah, dan substitusi aritmatika (yang **tidak** berada dalam double quotes) dipecah kembali berdasarkan karakter `$IFS`.
11. **Pathname Expansion (Globbing)**: Memindai filesystem untuk mencocokkan pattern wildcard (`*`, `?`, `[...]`).
12. **Quote Removal (Final)**: Menghapus karakter quote yang digunakan sebagai pelindung pada tahap-tahap sebelumnya.

```
Input Line ──> Tokenization ──> Brace Exp. ──> Tilde Exp. ──> Parameter & Cmd Sub. 
               ──> Arithmetic ──> Word Splitting ──> Pathname Exp. ──> Quote Removal 
               ──> Redirection Setup ──> Command Execution
```

### 6.2 Hirarki Tipe Eksekusi Perintah
Bash mengategorikan instruksi ke dalam 4 tingkatan sebelum melakukan pencarian path sistem:

| Tipe Eksekusi | Alokasi Memori | Keterlibatan Kernel Syscall | Contoh |
| :--- | :--- | :--- | :--- |
| **Special Builtin** | Heap/Stack Bash Parent | Tidak ada `fork()` / `execve()` | `exit`, `set`, `export`, `trap` |
| **Shell Function** | Heap Bash Parent | Tidak ada `fork()` / `execve()` | `my_func() { ... }` |
| **Regular Builtin** | Heap/Stack Bash Parent | Tidak ada `fork()` / `execve()` | `cd`, `echo`, `read`, `kill` |
| **External Binary** | Alokasi VMA Proses Baru | Memerlukan `fork()` / `clone()` & `execve()` | `/bin/ls`, `grep`, `awk`, `python3` |

### 6.3 Interaksi Kernel: The Fork-Exec Pattern
Ketika perintah eksternal diidentifikasi, Bash bertindak sebagai jembatan langsung ke subsistem kernel:

1. **`clone()` / `fork()`**: Bash mereplikasi dirinya sendiri. Kernel membuat struktur `task_struct` baru, menduplikasi tabel *Page Table Entries* (Copy-On-Write), dan membagikan representasi state lingkungan.
2. **`dup2()` / File Descriptor Plumbing**: Jika terdapat redirection (`>`, `<`, `2>&1`), subshell memodifikasi tabel *File Descriptor* lokal miliknya sebelum program baru dimuat.
3. **`execve()`**: Ruang memori proses anak ditimpa (*overlay*) sepenuhnya oleh binary executable target (ELF binary). Register CPU di-reset, dan execution flow dialihkan ke titik masuk (ELF entry point) biner baru.
4. **`wait4()` / `waitpid()`**: Parent shell memasuki mode *blocked* (kecuali diinstruksikan berjalan di latar belakang via `&`) hingga menerima notifikasi sinyal `SIGCHLD` dari kernel yang mengindikasikan proses anak telah selesai beserta *exit code*-nya.

---

## 7. How Does It Work? (Step-by-Step Architecture)

Berikut adalah algoritma state internal saat parent Bash mengeksekusi pipeline kompleks: `cat /etc/passwd | grep -v 'nologin'`

1. **Lexer/Parser mendeteksi Pipe Operator (`|`)**: Bash memahami bahwa kedua instruksi harus dieksekusi secara asinkron dalam subshell terpisah.
2. **Kernel Syscall `pipe()`**:
   * Bash meminta kernel membuat pipa komunikasi antar-proses (IPC).
   * Kernel mengembalikan dua File Descriptor baru: misalnya `fd[3]` (Read End) dan `fd[4]` (Write End).
3. **Forking Subshell Kiri (`cat`)**:
   * Parent Bash memanggil `fork()`.
   * Pada proses anak 1:
     * Menjalankan `dup2(4, 1)`: File descriptor standar output (`stdout` = 1) diarahkan ke `fd[4]`.
     * Menutup `fd[3]` dan `fd[4]`.
     * Memanggil `execve("/bin/cat", ["cat", "/etc/passwd"], environ)`.
4. **Forking Subshell Kanan (`grep`)**:
   * Parent Bash memanggil `fork()`.
   * Pada proses anak 2:
     * Menjalankan `dup2(3, 0)`: File descriptor standar input (`stdin` = 0) diarahkan ke `fd[3]`.
     * Menutup `fd[3]` dan `fd[4]`.
     * Memanggil `execve("/bin/grep", ["grep", "-v", "nologin"], environ)`.
5. **Parent Cleanup & Wait**:
   * Parent shell menutup salinan `fd[3]` dan `fd[4]` miliknya.
   * Parent memanggil `waitpid()` untuk kedua child PID.
   * Sesuai standar POSIX, nilai return status dari pipeline ini adalah exit code dari perintah *terakhir* (`grep`), kecuali jika flag `pipefail` diaktifkan.

---

## 8. Conceptual Architecture (ASCII Diagram)

Berikut peta interaksi proses Bash dengan Virtual Address Space dan Kernel Boundary:

```
+-----------------------------------------------------------------------------------+
| USER SPACE                                                                        |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Parent Bash Process (PID: 1000)                                             |  |
|  |   - Variable Table: [ PATH, USER, CUSTOM_VAR ]                              |  |
|  |   - FD Table: [ 0: stdin, 1: stdout, 2: stderr ]                            |  |
|  |   - Execution State: Interactive / Script Runtime                           |  |
|  +-----------------------------------------------------------------------------+  |
|         |                                 |                                       |
|         | 1. fork()                       | 1. fork()                             |
|         v                                 v                                       |
|  +----------------------------+    +----------------------------+                 |
|  | Subshell 1 (PID: 1001)     |    | Subshell 2 (PID: 1002)     |                 |
|  | - Copy of FD Table         |    | - Copy of FD Table         |                 |
|  | - dup2(pipe_write, stdout) |    | - dup2(pipe_read, stdin)   |                 |
|  +----------------------------+    +----------------------------+                 |
|         |                                 |                                       |
|         | 2. execve("/bin/cat")           | 2. execve("/bin/grep")                |
|         v                                 v                                       |
|  +----------------------------+    +----------------------------+                 |
|  | Replaced Memory Space:     |    | Replaced Memory Space:     |                 |
|  | Process: 'cat'             |    | Process: 'grep'            |                 |
|  | stdout ────+               |    |                +──── stdin |                 |
|  +------------|---------------+    +----------------|-----------+                 |
+---------------|-------------------------------------|-----------------------------+
| KERNEL SPACE  |                                     |                             |
|               v                                     |                             |
|         +-------------------------------------------+                             |
|         |           Kernel FIFO Ring Buffer         |                             |
|         |           (Created via pipe())            |                             |
|         +-------------------------------------------+                             |
+-----------------------------------------------------------------------------------+
```

---

## 9. Real-World Analogy

Bayangkan Bash sebagai **Kepala Proyek Konstruksi (General Contractor)**:
* **Special Builtins (`cd`, `export`)**: Tugas administratif pribadi yang ia lakukan sendiri di buku catatannya tanpa mempekerjakan orang lain. Memindahkan buku ke meja lain (`cd`) tidak memerlukan tenaga outsource.
* **Shell Functions**: Instruksi khusus yang telah ia hapal luar kepala. Ia mengeksekusinya sendiri secara langsung di tempat kerja.
* **External Executables (`grep`, `curl`, `sed`)**: Subkontraktor eksternal bersertifikat. 
  1. Mandor tidak melakukan pekerjaan tersebut.
  2. Mandor menelepon agensi untuk mendatangkan pekerja baru (*`fork`*).
  3. Pekerja datang membawa tas peralatannya sendiri, mengambil alih meja kerja yang disiapkan (*`execve`*).
  4. Mandor menyambungkan selang kompresor dari pekerja A ke pekerja B (*`pipe` & `dup2`*).
  5. Mandor duduk diam menunggu hingga pekerja menyelesaikan tugasnya (*`waitpid`*), lalu mencatat status penyelesaian di laporannya.

---

## 10. Minimal Viable Example (MVE)

Mari buktikan disparitas alokasi kernel antara *builtin* dan *external binary* menggunakan `strace`:

### Kode Uji
Jalankan satu baris ini di terminal Linux:

```bash
# 1. Observasi Bash Builtin
strace -f -e trace=clone,fork,vfork,execve bash -c 'echo "Executing Builtin"'

# 2. Observasi External Executable
strace -f -e trace=clone,fork,vfork,execve bash -c '/bin/echo "Executing External"'
```

### Hasil & Analisis Output
Pada perintah pertama (`echo` builtin):
```text
Executing Builtin
+++ exited with 0 +++
```
*Analisis*: Nol (0) pemanggilan `clone/execve`. Bash mencetak string langsung ke File Descriptor 1 (`stdout`) yang berada di dalam address space-nya sendiri.

Pada perintah kedua (`/bin/echo` eksternal):
```text
clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|CLONE_CHILD_SETTID|SIGCHLD, ...) = 104232
[pid 104232] execve("/bin/echo", ["/bin/echo", "Executing External"], 0x55d14e...) = 0
Executing External
[pid 104232] +++ exited with 0 +++
--- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_EXITED, si_pid=104232, si_status=0, ...} ---
+++ exited with 0 +++
```
*Analisis*: Kernel dipaksa mengalokasikan proses baru via `clone`, mengeksekusi biner via `execve`, memetakan dependensi dynamic linker (glibc), dan menangani sinyal pembersihan `SIGCHLD`.

---

## 11. Production-Grade Implementation

Berikut adalah script framework deterministik tingkat produksi yang menerapkan penanganan *strict mode*, abstraksi subshell, penanganan sinyal kernel (*signals*), dan manajemen file descriptor terisolasi.

Simpan file ini sebagai `runtime_engine_demo.sh`:

```bash
#!/usr/bin/env bash

# ==============================================================================
# SECURE BASH ENGINE HARNESS
# Architecture-aware initialization complying with POSIX.1-2017 & Bash 5+
# ==============================================================================

# Enable strict execution boundaries:
# -e: Exit immediately if a pipeline returns non-zero status.
# -u: Treat unset variables as an error when performing parameter expansion.
# -o pipefail: Return value of a pipeline is the status of the last command to exit
#              with a non-zero status, or zero if all successfully exit.
set -euo pipefail

# Ensure internal field separator is strictly configured to avoid malicious word splitting
IFS=$'\n\t'

# Module Metadata
readonly SCRIPT_NAME="${0##*/}"
readonly PROCESS_ID="$$"
readonly RUNTIME_TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Allocate dedicated custom File Descriptor (FD 3) for isolated audit logging
readonly AUDIT_LOG="/tmp/engine_audit_${PROCESS_ID}.log"
exec 3> "${AUDIT_LOG}"

# Intercept termination and cleanup signals
trap 'system_cleanup $?' EXIT
trap 'handle_signal SIGINT' INT
trap 'handle_signal SIGTERM' TERM

# ------------------------------------------------------------------------------
# Signal & Cleanup Handlers
# ------------------------------------------------------------------------------
system_cleanup() {
    local exit_code="$1"
    # Close custom File Descriptor 3
    exec 3>&- 2>/dev/null || true
    
    if [[ "${exit_code}" -ne 0 ]]; then
        printf "[FATAL] [%s] Script failed with exit code: %d\n" \
            "${RUNTIME_TIMESTAMP}" "${exit_code}" >&2
    fi
}

handle_signal() {
    local signal_type="$1"
    printf "[WARN] [%s] Intercepted signal %s. Initiating graceful termination.\n" \
        "${RUNTIME_TIMESTAMP}" "${signal_type}" >&2
    exit 130
}

# ------------------------------------------------------------------------------
# Core Execution Logic
# ------------------------------------------------------------------------------
log_audit() {
    local level="$1"
    local message="$2"
    # Write to FD 3 bypassing stdout/stderr of application
    printf "[%s] [%s] [PID:%s] %s\n" \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "${level}" "$BASHPID" "${message}" >&3
}

execute_subshell_workload() {
    local worker_id="$1"
    local state_tracker="INITIAL"

    # Explaining subshell boundaries:
    # () spawns a subshell process inheriting environment, but variable mutations
    # cannot escape back to parent memory space.
    (
        state_tracker="MUTATED_IN_SUBSHELL"
        log_audit "INFO" "Worker ${worker_id} started in isolated subshell (BASHPID: ${BASHPID})"
        
        # Verify subshell PID divergence from Parent Script PID
        if [[ "${BASHPID}" -eq "${PROCESS_ID}" ]]; then
            log_audit "CRITICAL" "Subshell failure: running on parent process space!"
            exit 1
        fi
        
        # Emulating localized deterministic file handling
        printf "Worker %d payload executed successfully.\n" "${worker_id}"
    )

    # Parent memory check: $state_tracker MUST STILL BE "INITIAL"
    if [[ "${state_tracker}" != "INITIAL" ]]; then
        log_audit "FATAL" "Memory isolation breach detected!"
        return 1
    fi
}

main() {
    log_audit "INFO" "Starting engine runtime. Master PID: ${PROCESS_ID}"

    # Demonstrate process array iteration without subshell variable loss
    local completed_tasks=0
    local raw_data="alpha:beta:charlie"

    # Deterministic parsing using pure bash parameter expansion instead of spawning cut/awk
    local original_ifs="${IFS}"
    IFS=':'
    read -r -a data_nodes <<< "${raw_data}"
    IFS="${original_ifs}"

    for node in "${data_nodes[@]}"; do
        log_audit "DEBUG" "Processing node: ${node}"
        execute_subshell_workload "${node}"
        # Increment counter in parent space safely
        completed_tasks=$((completed_tasks + 1))
    done

    printf "[SUCCESS] Processed %d architectural tasks. Audit written to %s\n" \
        "${completed_tasks}" "${AUDIT_LOG}"
}

main "$@"
```

### Eksekusi dan Verifikasi
Jalankan script untuk menguji validitas arsitektur:
```bash
chmod +x runtime_engine_demo.sh
./runtime_engine_demo.sh
cat /tmp/engine_audit_*.log
```

---

## 12. Edge Cases, Failure Modes & Pitfalls

### Pitfall 1: Hilangnya Modifikasi Variabel pada Subshell Pipeline
Pola umum berikut merupakan jebakan paling fatal:
```bash
total=0
cat /etc/hosts | while read -r line; do
    total=$((total + 1))
done
echo "Total lines: ${total}" # OUTPUT: 0!
```
**Mengapa?** Karena `while read` ditempatkan setelah operator pipa `|`, Bash menjalankan loop tersebut di dalam proses anak (*subshell*). Nilai variabel `$total` memang bertambah, tetapi hanya di dalam VMA (Virtual Memory Area) milik proses anak. Saat loop selesai, proses anak mati, dan address space-nya dihancurkan kernel. Variabel `$total` pada parent tetap bernilai `0`.

**Solusi POSIX/Bash (Process Substitution)**:
```bash
total=0
while read -r line; do
    total=$((total + 1))
done < <(cat /etc/hosts)
echo "Total lines: ${total}" # OUTPUT: Benar (e.g., 10)
```

### Pitfall 2: `$$` vs `$BASHPID`
* `$$` selalu mengembalikan PID dari *parent/top-level shell process*, bahkan ketika dipanggil dari dalam subshell.
* `$BASHPID` mencerminkan Process ID aktual yang diberikan oleh kernel kepada konteks eksekusi saat itu. Menggunakan `$$` untuk membuat lock file atau unique temporary path di dalam subshell akan memicu *race condition* karena seluruh subshell akan menghasilkan nilai ID yang identik.

---

## 13. Trade-off & Decision Matrix

| Kategori Strategi | Kelebihan (Pros) | Kekurangan (Cons) | Dampak Kernel Syscall | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Bash Builtin / Expansions** (`${var//foo/bar}`, `((i++))`) | Latensi nanodetik, nol alokasi process table, zero context-switch. | Kemampuan manipulasi regex terbatas dibanding tools biner murni. | **Zero Syscall** (hanya alokasi heap lokal). | Perulangan ketat (*hot paths*), parsing string sederhana, aritmatika dasar. |
| **Shell Functions** | Modularitas kode tinggi, mempertahankan state environment. | Rentan menimpa variable name-space jika tidak di-scope `local`. | **Zero Syscall** overhead penciptaan proses. | Standarisasi internal pipeline logic di dalam script yang sama. |
| **Subshell `( ... )`** | State sandboxing mutlak; perubahan direktori/variabel tidak bocor. | Overhead `fork()` (duplikasi metadata page table). | **High**: Memerlukan `clone()` / `fork()`. | Isolasi konfigurasi lokal, operasi direktori temporer (`cd /tmp && ...`). |
| **External Binary** (`awk`, `sed`, `jq`) | Performa tinggi untuk data streaming masif (megabytes/gigabytes). | Biaya inisialisasi proses besar untuk eksekusi single-item. | **Extreme**: Memerlukan `clone()`, `execve()`, dan dynamic linking. | Manipulasi array kompleks, parsing payload besar, agregasi data IO berskala tinggi. |

---

## 14. Security & Hardening Considerations

1. **Unquoted Variable Expansion (Word Splitting Exploit)**:
   Jangan pernah menulis `rm -rf $DIR_PATH/*`. Jika `$DIR_PATH` kosong atau mengandung spasi (misal: `DIR_PATH=" /"`), Bash akan memecah argumen menjadi `rm -rf / *`, yang memicu penghapusan root filesystem.
   * *Mitigasi*: Selalu proteksi ekspansi variabel: `rm -rf "${DIR_PATH:?Error}/"*`.

2. **Manipulasi `$IFS` (Field Separator Hijacking)**:
   Jika script berjalan di lingkungan multi-user atau menerima external input, attacker dapat mengubah `$IFS` agar pemisahan token mengeksekusi biner yang salah.
   * *Mitigasi*: Reset `$IFS` secara deterministik pada awal script menggunakan `IFS=$'\n\t'`.

3. **Injeksi Eksekusi Aritmatika**:
   Ekspresi `(( ... ))` dan `$(( ... ))` mengevaluasi variabel secara rekursif.
   ```bash
   # VULNERABLE CODE:
   read -r user_input
   val=$(( user_input ))
   ```
   Jika penyerang memasukkan `a[$(reboot)]`, Bash akan mengeksekusi perintah `reboot` melalui tahap ekspansi aritmatika.
   * *Mitigasi*: Validasi input bahwa data murni numerik menggunakan pattern regex `[[ "$user_input" =~ ^[0-9]+$ ]]` sebelum evaluasi aritmatika.

---

## 15. Verification & Testing

Untuk memvalidasi bahwa skrip Anda mematuhi batasan lingkungan eksekusi dan tidak memicu kebocoran state, jalankan rangkaian pengujian otomatis menggunakan script pengetesan mandiri berikut:

Simpan sebagai `test_engine_specs.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail

TESTS_PASSED=0
TESTS_FAILED=0

assert_equals() {
    local expected="$1"
    local actual="$2"
    local test_name="$3"

    if [[ "${expected}" == "${actual}" ]]; then
        printf "[PASS] %s\n" "${test_name}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        printf "[FAIL] %s | Expected: '%s', Got: '%s'\n" "${test_name}" "${expected}" "${actual}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# TEST 1: Memverifikasi State Isolation pada Subshell
run_isolation_test() {
    local target_var="PARENT_STATE"
    (
        target_var="SUBSHELL_STATE"
    )
    assert_equals "PARENT_STATE" "${target_var}" "Subshell State Isolation Test"
}

# TEST 2: Memverifikasi Perilaku Pipefail
run_pipefail_test() {
    set -o pipefail
    local pipeline_status=0
    # Command 'false' produces return code 1, piped into 'true' (0)
    false | true || pipeline_status=$?
    assert_equals "1" "${pipeline_status}" "Pipefail Propagation Test"
}

# TEST 3: Memverifikasi Perbedaan PID pada Subshell
run_pid_divergence_test() {
    local parent_pid=$$
    local subshell_pid
    subshell_pid=$(echo "$BASHPID")
    
    if [[ "${parent_pid}" -ne "${subshell_pid}" ]]; then
        local result="DIVERGED"
    else
        local result="IDENTICAL"
    fi
    assert_equals "DIVERGED" "${result}" "BASHPID Subshell Divergence Test"
}

# Menjalankan Test Suite
run_isolation_test
run_pipefail_test
run_pid_divergence_test

printf "\nExecution Summary: %d Passed, %d Failed\n" "${TESTS_PASSED}" "${TESTS_FAILED}"
[[ "${TESTS_FAILED}" -eq 0 ]] || exit 1
```

---

## 16. Anti-Patterns & Code Smells

### 1. The Useless Use of Cat (UUOC)
* *Smell*: `cat /var/log/syslog | grep "ERROR"`
* *Architectural Cost*: Menciptakan dua proses anak (`cat` dan `grep`), satu channel pipe kernel, dan pembacaan memori ganda.
* *Correction*: `grep "ERROR" /var/log/syslog` (Hanya 1 proses, pembacaan file descriptor langsung via `openat()`).

### 2. Iterasi Array/Stream via `ls`
* *Smell*: `for file in $(ls *.txt); do ... done`
* *Architectural Cost*:
  1. `ls` memanggil binary eksternal (`fork/execve`).
  2. Spasi atau karakter newline pada nama file akan merusak Word Splitting, mengeksekusi loop dengan nama file terpotong.
* *Correction*: Gunakan Pathname Expansion native:
  ```bash
  for file in ./*.txt; do
      [[ -e "${file}" ]] || continue # Guard against empty glob
      process_file "${file}"
  done
  ```

### 3. Parsing Baris Per Baris dengan External Command
* *Smell*:
  ```bash
  while read -r line; do
      user=$(echo "$line" | cut -d: -f1) # FORK BOMB IN DISGUISE
  done < /etc/passwd
  ```
* *Architectural Cost*: Jika `/etc/passwd` memiliki 10.000 baris, script melakukan `fork` dan `execve` biner `cut` sebanyak 10.000 kali!
* *Correction*: Gunakan kemampuan manipulasi string internal Bash:
  ```bash
  while read -r line; do
      user="${line%%:*}" # Zero Syscalls! Executed in-process memory.
  done < /etc/passwd
  ```

---

## 17. Best Practices & Operational Playbook

### Strict Initialization Checklist (The Production Boilerplate)
Setiap skrip Bash production wajib memiliki pola deklarasi awal berikut:

```bash
#!/usr/bin/env bash
# Gunakan env binary untuk portabilitas lokasi interpreter di berbagai distro POSIX

# 1. Strict Mode
set -euo pipefail

# 2. Sanitasi Field Separator
IFS=$'\n\t'

# 3. Defensive Umaks
umask 0077

# 4. Standardized Signals Interception
trap 'exit 1' SIGHUP SIGINT SIGTERM
```

### Operational Deployment Checklist
* [ ] **Audit Forking Frequencies**: Pastikan tidak ada external binary (`awk`, `cut`, `sed`, `grep`) yang dieksekusi di dalam perulangan berbasis baris (*line-by-line loops*).
* [ ] **Scope Enforcements**: Pastikan semua variabel di dalam fungsi dideklarasikan menggunakan kata kunci `local`.
* [ ] **Subshell Leak Prevention**: Hindari penggunaan pipa (`|`) jika state variabel pada loop dibutuhkan kembali oleh proses utama; alihkan menggunakan *process substitution* `< <(...)`.
* [ ] **Quoting Strategy**: Setiap ekspansi parameter (`"${my_var}"`) wajib dilindungi *double-quotes*, kecuali jika perilaku *word splitting* eksplisit dibutuhkan.

---

## 18. Troubleshooting Guide (Runbook)

### Kasus: Pipeline Macet / Berjalan Tanpa Henti (Stalled Process Execution)

#### 1. Symptom Diagnosis
Proses script automasi berhenti merespons, memori terus terkunci, dan sistem pemantauan mendeteksi eksekusi berstatus `UNINTERRUPTIBLE SLEEP` (D) atau `INTERRUPTIBLE SLEEP` (S).

#### 2. Investigasi File Descriptor via `/proc`
Cari PID script yang sedang berjalan, kemudian bedah pemetaan File Descriptor-nya:
```bash
# Temukan PID script
pgrep -f runtime_engine_demo.sh

# Inspeksi seluruh file descriptor yang terbuka pada proses tersebut
ls -l /proc/<PID>/fd/
```
Jika terlihat File Descriptor mengarah ke pipe yang tidak memiliki pembaca (*dead reader*) atau file kunci (*stale lock*), terjadi *Deadlock Pipe Buffer*.

#### 3. Penelusuran Syscall Real-time dengan `strace`
Pasang monitor syscall pada proses yang menggantung:
```bash
strace -p <PID> -f -s 1024 -e trace=read,write,wait4,pipe,dup2
```
* Pola `wait4(-1, ...)` menandakan parent sedang memblokir eksekusi menunggu child process yang tidak kunjung mati.
* Ambil PID child dari log `wait4`, lalu lakukan `strace` spesifik pada child tersebut untuk melihat apakah terjadi *blocking network socket* atau *deadlock input stream*.

#### 4. Remediasi
Jika anak proses menggantung akibat *unbuffered write* yang melampaui batas Linux Pipe Buffer (default: 65.536 bytes):
1. Ubah logika pipeline agar tidak menumpuk buffer di memori.
2. Gunakan named pipe eksplisit (`mkfifo`) dengan multiplexer atau pecah pipeline menjadi file perantara jika data melampaui puluhan megabytes.

---

## 19. Key Takeaways

1. **Bash adalah Parsing Engine sebelum menjadi Process Launcher**: Bash memproses baris teks melalui 12 langkah ekspansi terurut sebelum kernel menerima panggilan eksekusi biner.
2. **Builtins Menghemat Konteks Kernel**: Memanfaatkan *special builtins* dan manipulasi parameter Bash internal mengeliminasi overhead syscall `clone()` dan `execve()`.
3. **Subshells Mengisolasi State secara Asimetris**: Subshell menduplikasi state memori dari parent process (Copy-On-Write), namun modifikasi di dalam subshell **tidak pernah** terefleksi kembali ke parent.
4. **Pipa (`|`) Menciptakan Subshells**: Seluruh segmen pipeline dieksekusi dalam subshell tersendiri. Gunakan *Process Substitution* `< <(...)` jika ingin mempertahankan modifikasi variabel pasca perulangan.
5. **Konfigurasi `set -euo pipefail` adalah Harga Mati**: Ini merupakan benteng pertahanan utama untuk mencegah eksekusi berlanjut ketika terjadi kegagalan instruksi di tengah jalan.

---

## 20. Self-Assessment Exercises

Selesaikan tugas berikut untuk menguji pemahaman arsitektur Anda terhadap sistem eksekusi Bash:

### Soal 1: Subshell Variable Isolation Analysis (Analytical)
Diberikan script berikut:
```bash
#!/usr/bin/env bash
set -euo pipefail
counter=10
(
    counter=$((counter + 5))
    export counter
)
counter=$((counter + 1))
echo "$counter"
```
**Pertanyaan**: 
1. Berapakah output angka dari skrip di atas? 
2. Jelaskan langkah demi langkah apa yang dilakukan kernel terhadap tabel memori proses parent dan subshell pada baris `export counter`!

### Soal 2: Syscall Reduction Challenge (Practical Coding)
Ubah potongan kode skrip yang tidak efisien ini sehingga menghasilkan output string yang sama persis, **tanpa memanggil satupun external binary** (`basename`, `cut`, `tr`, `sed`, `awk`):

```bash
# Kode Asal (Sangat lambat, banyak fork/execve overhead):
input_path="/var/log/nginx/access-production.backup.log"
filename=$(basename "$input_path")
raw_name=$(echo "$filename" | cut -d'.' -f1)
uppercased=$(echo "$raw_name" | tr '[:lower:]' '[:upper:]')
echo "$uppercased" # Output: ACCESS-PRODUCTION
```

### Soal 3: Deterministic Pipeline Design (System Design)
Rancang sebuah fungsi Bash bernama `secure_stream_processor` yang:
1. Membaca stream input dari `stdin`.
2. Memfilter baris yang hanya mengandung format JSON valid (secara sintaksis sederhana diawali `{` dan diakhiri `}`).
3. Menghitung jumlah baris yang berhasil divalidasi ke dalam variabel `VALID_LINES_COUNT` yang **dapat diakses dan dicetak oleh parent process** setelah pipeline selesai, tanpa menulis temporary file ke disk.

---

## Solusi Penilaian Mandiri

### Solusi Soal 1
1. **Output**: `11`
2. **Analisis Memori Kernel**:
   * Saat parent mencapai tanda `(`, fungsi `clone()/fork()` dijalankan. Subshell mendapatkan salinan Virtual Memory Area (VMA) milik parent.
   * `counter=$((counter + 5))` mengubah nilai variabel lokal di memori subshell menjadi `15`.
   * Perintah `export counter` hanya menambahkan atribut `export` ke environment table **proses anak**. Subshell tidak memiliki akses baca-tulis (*write-access*) langsung ke segment memori parent process.
   * Saat subshell mencapai `)`, proses anak memanggil `exit()`. Kernel membersihkan memory space milik anak.
   * Parent shell, yang memorinya tidak tersentuh sama sekali sejak pemanggilan fork, melanjutkan eksekusinya di mana nilai `$counter` masih `10`. Baris berikutnya menambahkan `1`, menghasilkan output `11`.

### Solusi Soal 2
Implementasi murni in-memory Bash parameter expansion:
```bash
input_path="/var/log/nginx/access-production.backup.log"

# 1. Ekstrak nama file (pengganti basename)
filename="${input_path##*/}"

# 2. Buang ekstensi setelah titik pertama (pengganti cut)
raw_name="${filename%%.*}"

# 3. Ubah ke huruf besar menggunakan Bash 4+ parameter expansion (pengganti tr)
uppercased="${raw_name^^}"

echo "$uppercased"
```
*Total fork/execve calls berkurang dari 3 menjadi 0.*

### Solusi Soal 3
Implementasi memanfaatkan *Process Substitution* untuk menghindari isolasi subshell pada loop counter:
```bash
secure_stream_processor() {
    VALID_LINES_COUNT=0
    local line

    # Process substitution <(...) mencegah loop dieksekusi dalam subshell
    while read -r line || [[ -n "${line}" ]]; do
        # Pattern matching native in-process
        if [[ "${line}" =~ ^\{.*\}$ ]]; then
            VALID_LINES_COUNT=$((VALID_LINES_COUNT + 1))
            printf "%s\n" "${line}"
        fi
    done < <(cat) # Mengalirkan stdin tanpa memecah context variable

    # VALID_LINES_COUNT tetap persisten di parent context
    printf "[METRIC] Total processed valid lines: %d\n" "${VALID_LINES_COUNT}" >&2
}
```