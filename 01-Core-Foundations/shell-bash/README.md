Berikut adalah draf lengkap berkas `README.md` kurikulum silabus enterprise **Shell Bash** yang disusun dengan standar arsitektur kurikulum teknis tingkat lanjut.

---

# Enterprise Shell Scripting & Bash Systems Engineering

Selamat datang di kurikulum komprehensif **Shell Bash**. Kursus ini dirancang bukan sekadar untuk mengajarkan automasi skrip baris-per-baris sederhana, melainkan untuk mengubah paradigma rekayasa perangkat lunak Anda dalam memandang GNU Bash sebagai antarmuka deterministik berkinerja tinggi antara kernel sistem operasi Unix/Linux, arsitektur berkas POSIX, dan orkestrasi infrastruktur modern.

---

## 1. Course Overview & Mindset

### Mindset Rekayasa (Engineering Mindset)
Banyak praktisi memperlakukan skrip Shell sebagai perekat (*glue code*) kasual tanpa menerapkan prinsip rekayasa perangkat lunak yang ketat. Di lingkungan produksi berskala enterprise, kegagalan skrip Bash dapat memicu *data corruption*, *downtime* tak terduga, degradasi performa I/O, hingga pelanggaran keamanan (*vulnerability execution*). 

Dalam kurikulum ini, Anda dituntut untuk mengadopsi prinsip:
* **Deterministik & Defensive**: Skrip harus gagal secara terprediksi (*fail-fast*) menggunakan konfigurasi eksekusi yang ketat (`set -euo pipefail`), penanganan *exit code*, serta sanitasi input total.
* **POSIX & Bash Standards**: Memahami batasan portabilitas antara standar IEEE Std 1003.1 (POSIX) dan kapabilitas eksklusif GNU Bash (*Bashisms*).
* **Efisiensi Sumber Daya**: Memahami implikasi *fork-exec*, *subshell overhead*, alokasi *file descriptor*, serta manipulasi *stream* secara native tanpa ketergantungan berlebih pada *external binaries*.
* **Idempoten**: Setiap skrip automasi sistem yang dijalankan berkali-kali harus menghasilkan *state* akhir yang konsisten tanpa efek samping koruptif.

---

## 2. Learning Roadmap

```text
========================================================================================
                      BASH SYSTEMS ARCHITECTURE ROADMAP
========================================================================================
[Bab 01: Fondasi Shell & Eksekusi]
       │
       ├──> [Bab 02: Navigasi, I/O Streams & File Descriptors]
       │           │
       │           └──> [Bab 03: Variabel, Parameter Expansion & Tipe Data]
       │                       │
       │                       └──> [Bab 04: Logika Kontrol, Arithmetic & Exit Codes]
       │                                   │
       │                                   └──> [Bab 05: Fungsi, Subshell & Environment]
       │                                               │
┌──────────────────────────────────────────────────────┘
│
└──> [Bab 06: Advanced Text Processing (Grep, Sed, Awk)]
       │
       ├──> [Bab 07: Job Control, Process Lifecycle & Signals]
       │           │
       │           └──> [Bab 08: Interaktivitas, Argument Parsing & CLI Design]
       │                       │
       │                       └──> [Bab 09: Defensive Scripting, Testing & Audit]
       │                                   │
       │                                   └──> [Bab 10: Automasi Enterprise, Daemon & CI/CD]
       │                                               │
       └───────────────────────────────────────────────┴───> [CAPSTONE PROJECT]
========================================================================================
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Shell, Terminal, & Arsitektur Eksekusi Bash](01-fondasi-shell/README.md)
*Membedah interaksi antara Kernel, TTY/PTY, glibc, dan proses inisialisasi lingkungan Bash.*
* [Modul 01.1: Arsitektur Kernel, TTY, dan Proses Fork-Exec Bash](01-fondasi-shell/01-arsitektur-kernel-dan-fork-exec.md)
* [Modul 01.2: POSIX vs Bashisms: Kompatibilitas dan Ekosistem Lingkungan](01-fondasi-shell/02-posix-vs-bashisms.md)
* [Modul 01.3: Startup Scripts Lifecycle: `/etc/profile`, `~/.bashrc`, Login vs Non-Login Shell](01-fondasi-shell/03-startup-scripts-lifecycle.md)

### [Bab 02: Navigasi, I/O Streams, & File Descriptors](02-io-dan-file-descriptors/README.md)
*Manipulasi aliran data tingkat rendah, virtual filesystem, serta pengalihan standard streams.*
* [Modul 02.1: Virtual Filesystem (procfs, sysfs) & Deep Inode Operations](02-io-dan-file-descriptors/01-vfs-dan-inodes.md)
* [Modul 02.2: Standard Streams & File Descriptors (0, 1, 2, 3+) Deep-Dive](02-io-dan-file-descriptors/02-file-descriptors-deep-dive.md)
* [Modul 02.3: Redirection, Piping Chaining, dan Heredoc/Herestring Semantics](02-io-dan-file-descriptors/03-redirection-dan-heredoc.md)

### [Bab 03: Variabel, Parameter Expansion, & Struktur Data](03-variabel-dan-struktur-data/README.md)
*Optimalisasi alokasi memori internal shell dan manipulasi teks native tanpa external binary.*
* [Modul 03.1: Scoping, Environment Variables, & Atribut Deklarasi (`declare`, `typeset`)](03-variabel-dan-struktur-data/01-scoping-dan-declare.md)
* [Modul 03.2: Native Parameter Expansion Pattern Matching & Replacement](03-variabel-dan-struktur-data/02-parameter-expansion.md)
* [Modul 03.3: Indexed Arrays dan Associative Arrays Tingkat Lanjut](03-variabel-dan-struktur-data/03-arrays-dan-associative-arrays.md)

### [Bab 04: Logika Kontrol, Arithmetic, & Evaluasi Kondisi](04-logika-dan-arithmetic/README.md)
*Mekanisme branching deterministik, evaluasi biner, dan aritmetika internal Bash.*
* [Modul 04.1: Evaluasi Kondisi: Perbedaan Kritis `test`, `[ ]`, dan `[[ ]]`](04-logika-dan-arithmetic/01-evaluasi-kondisi.md)
* [Modul 04.2: Arithmetic Evaluation: `(( ))` vs `expr` vs Arbitrary Precision `bc`](04-logika-dan-arithmetic/02-arithmetic-evaluation.md)
* [Modul 04.3: Exit Status Patterns, Short-Circuit Evaluation, dan Case Switch Parsing](04-logika-dan-arithmetic/03-loops-dan-branching.md)

### [Bab 05: Modularitas Fungsi, Subshell, & Environment Management](05-fungsi-dan-subshell/README.md)
*Abstraksi kode berulang, pengelolaan lingkungan eksekusi, serta optimasi memory footprint.*
* [Modul 05.1: Functional Programming Pattern, Variable Locality, & Return Handling](05-fungsi-dan-subshell/01-functions-dan-locality.md)
* [Modul 05.2: Subshell Isolation Overhead: `()` vs `{}` Execution Block](05-fungsi-dan-subshell/02-subshell-vs-code-blocks.md)
* [Modul 05.3: Command Substitution (`$()` vs backticks) & Process Substitution (`<()`, `>()`)](05-fungsi-dan-subshell/03-process-substitution.md)

### [Bab 06: Advanced Text Processing: Regex, Sed, & Awk Engine](06-text-processing/README.md)
*Rekayasa parsing teks berskala besar menggunakan perkakas POSIX streams klasik.*
* [Modul 06.1: POSIX Basic vs Extended Regular Expressions via `grep` Engine](06-text-processing/01-regex-dan-grep.md)
* [Modul 06.2: Stream Transformation & In-place Multi-Pass Editing dengan `sed`](06-text-processing/02-stream-editing-sed.md)
* [Modul 06.3: Complex Tabular Data Parsing & Report Generation Menggunakan `awk`](06-text-processing/03-awk-programming-language.md)

### [Bab 07: Job Control, Process Lifecycle, & Asynchronous Concurrency](07-proses-dan-sinyal/README.md)
*Manajemen siklus hidup thread/proses sistem operasi, signal handling, dan race prevention.*
* [Modul 07.1: Job Control, IPC, Background Execution, & Paralelisasi Multiprocess](07-proses-dan-sinyal/01-job-control-dan-concurrency.md)
* [Modul 07.2: Signal Trapping (`trap`), Graceful Shutdown, dan Intercept Termination](07-proses-dan-sinyal/02-signal-trapping.md)
* [Modul 07.3: File Locking Mutex via `flock` untuk Mencegah Race Conditions](07-proses-dan-sinyal/03-mutex-flock-locking.md)

### [Bab 08: Interaktivitas, Argument Parsing, & CLI Interface Design](08-cli-design-dan-interaktivitas/README.md)
*Membangun utilitas command-line yang mematuhi standar UNIX Philosophy dan interaktif.*
* [Modul 08.1: Advanced CLI Flags Parsing Menggunakan `getopts` Native](08-cli-design-dan-interaktivitas/01-cli-getopts-parsing.md)
* [Modul 08.2: User Input Stream, Timers, dan Password Masking via `read`](08-cli-design-dan-interaktivitas/02-input-handling-read.md)
* [Modul 08.3: Desain Standar POSIX CLI Output: Formatted Printing, ANSI, dan STDOUT/STDERR Rules](08-cli-design-dan-interaktivitas/03-posix-cli-formatting.md)

### [Bab 09: Defensive Scripting, Testing, & Static Code Analysis](09-defensive-scripting/README.md)
*Mekanisme pertahanan skrip tingkat enterprise, audit keamanan, dan static linting.*
* [Modul 09.1: Strict Execution Mode: `set -euo pipefail` dan Penanganan Unset Triggers](09-defensive-scripting/01-strict-execution-mode.md)
* [Modul 09.2: Static Code Analysis dengan ShellCheck dan Format Code Architecture](09-defensive-scripting/02-shellcheck-dan-auditing.md)
* [Modul 09.3: Unit Testing Bash Scripts Menggunakan BATS (Bash Automated Testing System)](09-defensive-scripting/03-unit-testing-bats.md)

### [Bab 10: Automasi Enterprise, System Administration, & CI/CD Pipelines](10-automasi-dan-cicd/README.md)
*Integrasi Bash ke orkestrasi cloud, runtime systemd, cron schedules, dan runner CI/CD.*
* [Modul 10.1: Systemd Service Units vs Cron Jobs: Scheduled Execution & Logging Management](10-automasi-dan-cicd/01-systemd-dan-cron.md)
* [Modul 10.2: Remote Automation Menggunakan SSH Multiplexing dan Parallel Keys](10-automasi-dan-cicd/02-ssh-multiplexing-automation.md)
* [Modul 10.3: Bash Infrastructure-as-Code pada CI/CD Runners (GitHub Actions & GitLab CI)](10-automasi-dan-cicd/03-cicd-runner-orchestration.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**"Enterprise Edge Node Observability, Automated Remediation Daemon, & Disaster Recovery Agent"**

### Gambaran Umum
Sebagai syarat kelulusan kurikulum, peserta wajib merancang dan mengimplementasikan agen *monitoring*, audit, dan pemulihan bencana (*self-healing*) berbasis skrip Bash tanpa dependensi eksternal pihak ketiga (hanya mengandalkan GNU Coreutils standar dan Bash v4.4+). Skrip ini didesain untuk berjalan sebagai *background daemon* di server Linux produksi.

### Arsitektur & Kriteria Wajib Proyek:
1. **Defensive Runtime & Portabilitas**:
   * Seluruh pustaka skrip wajib lolos validasi `shellcheck --severity=style` tanpa peringatan (*zero warnings*).
   * Menerapkan konfigurasi `set -euo pipefail` di seluruh modul, dilengkapi dengan penanganan error terperinci menggunakan `trap` untuk mengumpulkan baris kesalahan, status exit, dan *stack trace* fungsi.
2. **File Locking & Concurrency Management**:
   * Menggunakan `flock` berbasis berkas deskriptor untuk memastikan instans tunggal (*single instance daemon*), mencegah *split-brain* proses.
   * Mengimplementasikan *multiprocessing worker pool* non-blocking menggunakan FIFO / UNIX Named Pipe untuk menjalankan *health check* jaringan secara paralel.
3. **Core Monitoring & Parsing Engine**:
   * Membaca dan mem-parsing data kernel langsung dari `/proc` (`/proc/stat`, `/proc/meminfo`, `/proc/loadavg`, `/proc/net/dev`) tanpa memanggil *command overhead* seperti `top` atau `htop`.
   * Melakukan rotasi berkas log secara atomik (`atomic rename`) ketika ukuran berkas melewati ambang batas tertentu, serta membersihkan arsip lama (*pruning*).
4. **CLI Controller & Flags Interface**:
   * Menyediakan antarmuka Command Line Interface terstandarisasi POSIX menggunakan `getopts`:
     * `--daemon` (berjalan di *background* via systemd wrapper)
     * `--dry-run` (melakukan simulasi *remediation* tanpa eksekusi langsung)
     * `--config <path>` (parsing berkas konfigurasi *key-value* secara aman tanpa memakai `eval`)
     * `--report` (menghasilkan *health report* berformat JSON terstruktur yang dihasilkan secara native/pure Bash).
5. **Self-Healing & Remediation Engine**:
   * Mendeteksi anomali (misalnya layanan tertentu *down* atau kapasitas *disk* melewati 90%).
   * Melakukan tindakan mitigasi bertahap (*staged remediation*), merekam proses perbaikan ke syslog via `logger`, dan mengirim payload ringkasan ke webhook HTTPS eksternal via `curl` non-blocking.
6. **Automated Testing**:
   * Dilengkapi minimal 15 berkas pengujian otomatis menggunakan **BATS (Bash Automated Testing System)** yang memvalidasi parsing konfigurasi, *edge-case parameter expansion*, *mock failure handling*, dan integritas format keluaran JSON.

---
*Kurikulum ini disusun berdasarkan standar resmi kompetensi roadmap.sh/shell-bash dan praktik terbaik industri Linux Foundation.*