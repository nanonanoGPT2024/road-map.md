## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `BASH-CORE-09-01`
*   **Kategori:** `01-Core-Foundations`
*   **Bab:** `09 — Defensive Scripting, Testing & Audit`
*   **Nama Modul:** `Defensive Scripting, Automated Testing (BATS), and Static Audit`
*   **Tingkat Kesulitan:** `Advanced`
*   **Prasyarat:**
    *   Pemahaman mendalam tentang I/O Redirection, Pipes, dan Exit Codes (`$?`).
    *   Kemahiran dalam Bash Parameter Expansion dan Subshell Semantics.
    *   Pengalaman mengelola Signal Handling (`kill`, POSIX signals).
*   **Estimasi Waktu Belajar:** 180 Menit (Teori: 60 Menit, Praktik Lab: 120 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis & Mengimplementasikan** paradigma *strict mode* Bash (`set -euo pipefail`, `IFS`, `inherit_errexit`) untuk mengeliminasi *silent failures* dan *unintended side-effects*.
2.  **Merancang** mekanisme penanganan kesalahan (Error Handling) tingkat lanjut menggunakan `trap` untuk sinyal `ERR`, `EXIT`, `SIGINT`, dan `SIGTERM` guna menjamin pembersihan resource (*cleanup*) yang deterministik.
3.  **Menerapkan** teknik validasi input defensif, parameter sanitization, dan safe variable expansion untuk memitigasi celah keamanan seperti command injection dan path traversal.
4.  **Membangun** test suite unit/integrasi otomatis menggunakan kerangka kerja BATS (*Bash Automated Testing System*) dengan arsitektur *setup/teardown* yang terisolasi.
5.  **Mengintegrasikan** static analysis tools (ShellCheck) dan format auditing (shfmt) ke dalam workflow validasi kode lokal dan CI/CD pipeline.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [DEFENSIVE BASH ARCHITECTURE]
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         ▼                                ▼                                ▼
  [RUNTIME HARDENING]            [FAULT TOLERANCE]               [QUALITY ASSURANCE]
  ├── set -euo pipefail          ├── Deterministic Cleanup       ├── Static Analysis
  ├── shopt -s inherit_errexit   │   └── trap ... EXIT/ERR       │   └── ShellCheck (AST)
  ├── IFS=$'\n\t'                ├── Idempotent Actions          ├── Automated Testing
  └── Safe Variable Guard        └── Atomic File Ops             │   └── BATS Framework
      └── ${var:?err}                └── mktemp & symlinks       └── Code Formatting
                                                                     └── shfmt
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Secara default, Bash dirancang sebagai interactive shell yang permisif, bukan sebagai runtime eksekusi aplikasi yang strik. Ketika sebuah perintah gagal di tengah script standar, Bash secara default akan mengabaikan kegagalan tersebut dan melanjutkan eksekusi baris berikutnya seolah-olah tidak terjadi anomali (*silent error propagation*).

Pertimbangkan skenario malapetaka klasik berikut:
```bash
# Naive script tanpa validasi defensif
TARGET_DIR="/opt/app/temp_build"
# ... terjadi proses komputasi yang gagal mengalokasikan TARGET_DIR ...
TARGET_DIR="" # Variabel menjadi kosong akibat unbound error

rm -rf "${TARGET_DIR}/*" # Bash mengeksekusi: rm -rf /* -> Bencana filesystem root
```

Di lingkungan produksi berskala enterprise:
*   **Downtime & Korupsi Data:** Script deployment yang gagal di langkah migrasi database namun tetap melanjutkan perintah restart service akan mengakibatkan inkonsistensi data.
*   **Security Vulnerabilities:** Parameter yang tidak divalidasi membuka celah *Argument Injection* atau *Arbitrary Command Execution*.
*   **Resource Leaks:** Script worker yang dihentikan paksa via sinyal `SIGTERM` tanpa cleanup trap akan meninggalkan dangling process, file locks (`.pid`), dan alokasi memori sementara di `/tmp`.

Defensive scripting, testing berbasis BATS, dan audit statis mengubah Bash dari sekadar "alat otomatisasi rapuh" menjadi bahasa pemrogram runtime infrastruktur yang tangguh, deterministik, dan dapat diverifikasi secara formal.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. The Defensive Header (Unofficial Strict Mode)
Sekumpulan direktif interpreter shell yang mengubah perilaku parser dan engine eksekusi Bash:
*   `set -e` (`errexit`): Menghentikan eksekusi script seketika jika ada perintah yang menghasilkan exit status non-zero (`!= 0`), kecuali perintah tersebut merupakan bagian dari conditional testing (`if`, `while`, `until`, `||`).
*   `set -u` (`nounset`): Memperlakukan variabel yang belum dideklarasikan (*unbound/uninitialized*) sebagai error fatal dan langsung menghentikan proses.
*   `set -o pipefail`: Memaksa pipeline (`cmd1 | cmd2 | cmd3`) mengembalikan exit code dari perintah *terakhir* yang bernilai non-zero. Tanpa flag ini, status keberhasilan pipeline hanya ditentukan oleh perintah paling kanan (`cmd3`).
*   `shopt -s inherit_errexit`: (Bash 4.4+) Memastikan efek `set -e` diwariskan ke dalam subshell `$(command)`. Secara default, Bash menonaktifkan `set -e` di dalam command substitution.
*   `IFS=$'\n\t'`: Mengatur *Internal Field Separator* default hanya pada *newline* dan *tab*, mengeliminasi *space* sebagai pemisah token kata untuk mencegah *word-splitting bugs* saat memproses nama file yang mengandung spasi.

### 2. Signal Trapping & Atomic Cleanup
Konsep intercepting sinyal kernel dan internal shell events (`EXIT`, `ERR`, `SIGINT`, `SIGTERM`) untuk menjalankan fungsi penyelamat (*handler/cleanup routines*), menjamin prinsip otomasi *idempotent* dan zero residual files.

### 3. BATS (Bash Automated Testing System)
Kerangka kerja pengujian perangkat lunak berbasis format TAP (*Test Anything Protocol*) yang memungkinkan unit testing dan integration testing terhadap executable shell script, command-line interfaces, dan modul fungsi.

### 4. AST-based Static Analysis (ShellCheck)
Alat audit kode statis yang mem-parsing source code shell ke dalam bentuk *Abstract Syntax Tree* (AST) untuk mendeteksi bugs logis, celah keamanan, dan kelemahan sintaks sebelum script dieksekusi di runtime.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Internal `pipefail`

Secara default, array status pipeline internal Bash (`PIPESTATUS`) mencatat exit code setiap elemen, namun nilai kembalian skalar `$?` dari pipeline hanya merefleksikan elemen terakhir.

```
DEFAULT BEHAVIOR (set +o pipefail):
[false] (status: 1) ──► [grep "foo"] (status: 1) ──► [wc -l] (status: 0)
Hasil $? = 0 (SUCCESS) ──► Bash menganggap pipeline BERHASIL. Bahaya!

STRICT MODE (set -o pipefail):
[false] (status: 1) ──► [grep "foo"] (status: 1) ──► [wc -l] (status: 0)
Bash membaca PIPESTATUS[@] = (1, 1, 0)
Hasil $? = 1 (FAILURE) ──► Bash memicu mekanisme errexit.
```

### Mekanisme `trap` Lifecycle

Sinyal kernel yang dikirim ke proses Bash disalurkan melalui signal handler tabel POSIX:
1.  **Sinyal `EXIT`:** Pseudo-signal internal Bash. Dieksekusi kapan pun script berakhir—baik karena selesai secara natural, tersandung `set -e`, atau memanggil `exit`.
2.  **Sinyal `ERR`:** Pseudo-signal internal yang dipicu hanya jika sebuah perintah mengembalikan status non-zero di luar struktur kontrol kondisi.
3.  **Sinyal OS (`INT`, `TERM`):** Hardware interrupt (Ctrl+C) atau termination request dari supervisor (seperti `systemd` atau Docker runtime).

```
Kernel Signal (SIGTERM) ──┐
                          ├──► [Bash Process Signal Trap] ──► Eksekusi cleanup() ──► Hard Exit
Script Logic Exit (set -e)┘
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Eksekusi: Naive Script vs. Defensive Script

```
                       NAIVE SCRIPT LIFECYCLE
──────────────────────────────────────────────────────────────────
Start ──► Step 1: OK ──► Step 2: FAIL ──► Step 3: Run with invalid state
                             │                     │
                        (Exit code 1        (Korupsi Sistem /
                         diabaikan)          Silent Mutation)
──────────────────────────────────────────────────────────────────

                     DEFENSIVE SCRIPT LIFECYCLE
──────────────────────────────────────────────────────────────────
Start
  │
  ├──► [Init: set -euo pipefail; shopt -s inherit_errexit]
  │
  ├──► [Register Trap Handler: trap cleanup EXIT INT TERM]
  │
  ├──► Step 1: Resource Allocation (e.g., mktemp -d)
  │
  ├──► Step 2: Critical Execution (FAIL: Non-Zero Exit)
  │       │
  │       ▼ [Interception by errexit]
  │    Trigger Pseudo-signal EXIT
  │       │
  │       ▼
  ├──► [Invoke cleanup()]
  │       ├── Hapus file temp atomic
  │       ├── Rilis lockfile / PID
  │       └── Log stack trace & Line Number via ${BASH_SOURCE}, ${LINENO}
  │
  ▼
Script Terminates with Exact Exit Status Code (FAIL FAST)
──────────────────────────────────────────────────────────────────
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah skeleton paling fundamental dari Bash Defensive Script:

```bash
#!/usr/bin/env bash

# 1. Aktifkan Strict Mode
set -euo pipefail
IFS=$'\n\t'

# 2. Deklarasi Resource Global
WORK_DIR=""

# 3. Cleanup Routine
cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM # Mencegah rekursi sinyal
    
    if [[ -d "${WORK_DIR}" ]]; then
        echo "[INFO] Membersihkan temporary directory: ${WORK_DIR}" >&2
        rm -rf "${WORK_DIR}"
    fi
    
    echo "[INFO] Script berakhir dengan exit code: ${exit_code}" >&2
    exit "${exit_code}"
}

# 4. Registrasi Trap
trap cleanup EXIT INT TERM

# 5. Eksekusi Program Terisolasi
WORK_DIR="$(mktemp -d -t myapp-XXXXXX)"
echo "[INFO] Bekerja di: ${WORK_DIR}"

# Demonstrasi nounset guard:
# echo "${UNDEFINED_VARIABLE}" # Jika di-uncomment, script langsung crash di sini

# Demonstrasi pipefail guard:
echo "Menguji pipefail..."
cat "/file/yang/pasti/tidak/ada" 2>/dev/null | sort

echo "Baris ini TIDAK AKAN PERNAH dieksekusi karena pipeline di atas gagal."
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus dunia nyata: Sebuah script pemrosesan data produksi yang harus melakukan validasi argumen secara ketat, mengunci instance agar tidak berjalan ganda (*file-lock mutex*), atomic staging, integrasi static analysis, dan test suite BATS.

### 1. Implementation Script: `data_sync.sh`

```bash
#!/usr/bin/env bash

# ==============================================================================
# SCRIPT NAME: data_sync.sh
# DESCRIPTION: Sinkronisasi file defensif dengan validasi hash dan lock mechanism.
# ==============================================================================

set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true
IFS=$'\n\t'

# Kontrol Verbosity & Dry-Run
DRY_RUN="${DRY_RUN:-false}"
LOCK_FILE="/tmp/data_sync.lock"
TEMP_DIR=""

# --- LOGGING UTILITY ---
log_info()  { printf "[%s] [INFO]  %s\n" "$(date +'%Y-%m-%dT%H:%M:%S%z')" "$*" >&2; }
log_error() { printf "[%s] [ERROR] (Line: %s) %s\n" "$(date +'%Y-%m-%dT%H:%M:%S%z')" "${1}" "${*:2}" >&2; }

# --- CLEANUP & TRAP ENGINE ---
cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM ERR
    
    if [[ -f "${LOCK_FILE}" ]]; then
        rm -f "${LOCK_FILE}"
        log_info "Lockfile ${LOCK_FILE} dirilis."
    fi
    
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
        log_info "Staging dir ${TEMP_DIR} dihapus."
    fi
    
    if (( exit_code != 0 )); then
        log_error "${LINENO}" "Script terhenti dengan kegagalan fatal (Exit Status: ${exit_code})."
    fi
    exit "${exit_code}"
}

error_handler() {
    local parent_lineno="$1"
    local message="$2"
    local code="${3:-1}"
    log_error "${parent_lineno}" "${message}"
    exit "${code}"
}

trap 'cleanup' EXIT INT TERM
trap 'error_handler ${LINENO} "Unhandled command failure occurred."' ERR

# --- IDEMPOTENCY / LOCK MUTEX ---
acquire_lock() {
    if ! ( set -o noclobber; echo "$$" > "${LOCK_FILE}" ) 2>/dev/null; then
        local holder_pid
        holder_pid="$(cat "${LOCK_FILE}" 2>/dev/null || echo "UNKNOWN")"
        log_error "${LINENO}" "Gagal mengakuisisi lock! Proses lain sedang berjalan (PID: ${holder_pid})."
        exit 75 # EX_TEMPFAIL
    fi
}

# --- VALIDASI INPUT ---
validate_inputs() {
    local source_dir="${1:-}"
    local target_dir="${2:-}"

    if [[ -z "${source_dir}" || -z "${target_dir}" ]]; then
        log_error "${LINENO}" "Argumen tidak lengkap! Usage: $0 <source_dir> <target_dir>"
        exit 64 # EX_USAGE
    fi

    if [[ ! -d "${source_dir}" ]]; then
        log_error "${LINENO}" "Source direktori [${source_dir}] tidak ditemukan!"
        exit 66 # EX_NOINPUT
    fi

    if [[ ! -r "${source_dir}" ]]; then
        log_error "${LINENO}" "Source direktori [${source_dir}] tidak dapat dibaca (permission denied)!"
        exit 77 # EX_NOPERM
    fi
}

# --- CORE LOGIC ---
process_sync() {
    local src="$1"
    local dst="$2"

    TEMP_DIR="$(mktemp -d -t sync_stage.XXXXXXXXXX)"
    log_info "Alokasi staging area di: ${TEMP_DIR}"

    # Eksekusi Staging
    log_info "Menyalin file dari ${src} ke staging area..."
    cp -r "${src}/." "${TEMP_DIR}/"

    # Verifikasi Integritas
    local count
    count="$(find "${TEMP_DIR}" -type f | wc -l | tr -d ' ')"
    log_info "Total file berhasil diproses di staging: ${count}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] Melewati transfer atomik ke direktori tujuan: ${dst}."
        return 0
    fi

    mkdir -p "${dst}"
    # Atomic Move/Sync menggunakan rsync
    rsync -a --delete "${TEMP_DIR}/" "${dst}/"
    log_info "Sinkronisasi atomik ke ${dst} sukses diselesaikan."
}

# --- ENTRY POINT ---
main() {
    local src="${1:-}"
    local dst="${2:-}"

    validate_inputs "${src}" "${dst}"
    acquire_lock
    process_sync "${src}" "${dst}"
}

main "$@"
```

### 2. Automated Test Suite: `test_data_sync.bats`

Simpan file berikut di folder yang sama untuk diuji menggunakan BATS framework (`bats test_data_sync.bats`).

```bash
#!/usr/bin/env bats

setup() {
    # Environment isolated setup sebelum setiap tes
    TEST_DIR="$(mktemp -d -t bats_test_env.XXXXXX)"
    SRC_DIR="${TEST_DIR}/source"
    DST_DIR="${TEST_DIR}/destination"
    
    mkdir -p "${SRC_DIR}" "${DST_DIR}"
    echo "Payload A" > "${SRC_DIR}/file_a.txt"
    echo "Payload B" > "${SRC_DIR}/file_b.txt"
    
    # Path executable script yang diuji
    SCRIPT_UNDER_TEST="./data_sync.sh"
}

teardown() {
    # Cleanup seluruh artefak tes
    if [[ -d "${TEST_DIR}" ]]; then
        rm -rf "${TEST_DIR}"
    fi
    rm -f /tmp/data_sync.lock
}

@test "Gagal jika argumen tidak diberikan (Exit Code 64)" {
    run "${SCRIPT_UNDER_TEST}"
    [ "$status" -eq 64 ]
    [[ "$output" =~ "Argumen tidak lengkap" ]]
}

@test "Gagal jika direktori sumber tidak eksis (Exit Code 66)" {
    run "${SCRIPT_UNDER_TEST}" "${TEST_DIR}/non_existent" "${DST_DIR}"
    [ "$status" -eq 66 ]
    [[ "$output" =~ "tidak ditemukan" ]]
}

@test "Berhasil menyinkronkan direktori secara normal" {
    run "${SCRIPT_UNDER_TEST}" "${SRC_DIR}" "${DST_DIR}"
    [ "$status" -eq 0 ]
    [ -f "${DST_DIR}/file_a.txt" ]
    [ -f "${DST_DIR}/file_b.txt" ]
    [ "$(cat "${DST_DIR}/file_a.txt")" = "Payload A" ]
}

@test "Menolak eksekusi ganda jika Lockfile masih aktif" {
    touch /tmp/data_sync.lock
    run "${SCRIPT_UNDER_TEST}" "${SRC_DIR}" "${DST_DIR}"
    [ "$status" -eq 75 ]
    [[ "$output" =~ "Gagal mengakuisisi lock" ]]
}

@test "Dry-run mode tidak menyentuh direktori tujuan" {
    export DRY_RUN="true"
    run "${SCRIPT_UNDER_TEST}" "${SRC_DIR}" "${DST_DIR}"
    [ "$status" -eq 0 ]
    # File tidak boleh tersalin di DST_DIR
    [ ! -f "${DST_DIR}/file_a.txt" ]
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan | Kerugian / Risiko Tersembunyi | Mitigasi yang Direkomendasikan |
| :--- | :--- | :--- | :--- |
| **`set -e` (errexit)** | Menolak silent failure; langsung menghentikan eksekusi script saat terjadi non-zero exit code. | Memiliki edge case ambigu saat digunakan dalam subshell, conditional commands (`grep`, `[[ ]]`), atau pipes. | Jangan mengandalkan `set -e` untuk commands yang return non-zero secara alami. Gunakan syntax eksplisit: `command \|\| true` atau tangani via conditional. |
| **`set -u` (nounset)** | Mencegah bug destructive akibat variabel kosong (`rm -rf "${FOO}/*"`). | Menghentikan eksekusi saat membaca array asosiatif kosong atau opsi opsional CLI. | Gunakan ekspansi default: `${VARIABLE:-default}` atau `${VARIABLE-}` untuk mengevaluasi variabel opsional secara legal. |
| **Pembersihan dengan `trap ... EXIT`** | Menjamin clean-up berjalan deterministik pada skenario error, interupsi sinyal, atau script exit normal. | Jika fungsi cleanup mengandung kode yang mengembalikan error non-zero di bawah `set -e`, dapat terjadi infinite trap loop atau premature abort. | Selalu gunakan `trap - EXIT INT TERM` di awal fungsi cleanup dan periksa keberadaan target path sebelum `rm -rf`. |
| **Testing Menggunakan BATS** | Verifikasi black-box dan unit behavior secara headless dan mudah diintegrasikan ke CI/CD. | Memerlukan runtime instalasi tambahan (`npm` / native package); pengujian operasi root/sistem nyata memerlukan mock engine yang kompleks. | Gunakan Docker container terisolasi untuk suite testing BATS agar tidak merusak lingkungan host. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Standard Header Konsisten:**
    ```bash
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s inherit_errexit 2>/dev/null || true
    IFS=$'\n\t'
    ```
2.  **Quote Semua Ekspansi Variabel:**
    Selalu bungkus variabel dalam tanda kutip ganda (`"${var}"`) kecuali secara eksplisit memerlukan *word-splitting*. Gunakan `"${array[@]}"` untuk mempertahankan integritas boundaries elemen array.
3.  **Gunakan Format Sanitasi Standar POSIX Exit Codes:**
    Gunakan exit code semantik yang terdefinisi pada `/usr/include/sysexits.h`:
    *   `0`: Sukses
    *   `64`: Command line usage error (`EX_USAGE`)
    *   `66`: Cannot open input (`EX_NOINPUT`)
    *   `70`: Internal software error (`EX_SOFTWARE`)
    *   `75`: Temporary failure / Lock exists (`EX_TEMPFAIL`)
    *   `77`: Permission denied (`EX_NOPERM`)
4.  **Static Audit Mandatori:**
    Jalankan ShellCheck sebelum eksekusi script:
    ```bash
    shellcheck -S error -e SC1090,SC1091 script.sh
    ```
5.  **Batasi Scope Variabel dengan `local`:**
    Di dalam fungsi, selalu deklarasikan variabel menggunakan kata kunci `local` (atau `local -r` untuk read-only). Ini mencegah polusi variabel global yang tidak terduga.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Ilusi Keamanan `set -e` dalam Subshell
*Salah:*
```bash
set -e
output=$(cat non_existent_file.txt) # Bash < 4.4 TIDAK menghentikan script di sini!
echo "Script terus berjalan!"
```
*Benar:*
Aktifkan `shopt -s inherit_errexit` (Bash 4.4+) atau lakukan checking status eksplisit:
```bash
shopt -s inherit_errexit
output=$(cat non_existent_file.txt)
```

### 2. Mengabaikan Exit Code `grep`
*Salah:*
```bash
set -e
# Jika grep tidak menemukan data, return status adalah 1 -> SCRIPT CRASH
has_root=$(grep "superuser" /etc/passwd)
```
*Benar:*
```bash
# Explicit fallback menggunakan OR operator
has_root=$(grep "superuser" /etc/passwd || true)
# Atau gunakan conditional test secara benar:
if grep -q "superuser" /etc/passwd; then
    # logic
fi
```

### 3. Masalah Word Splitting pada Dynamic Trapping
*Salah:*
```bash
temp_file="/tmp/test file with space.txt"
trap "rm -f $temp_file" EXIT # Spasi akan memecah argumen rm menjadi 5 file berbeda!
```
*Benar:*
```bash
temp_file="/tmp/test file with space.txt"
# Definisikan fungsi terisolasi
cleanup() {
    rm -f "${temp_file}"
}
trap cleanup EXIT
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Tingkat Dasar): Memperbaiki Unsafe Script
Refactor script berikut agar mematuhi strict mode, menangani unbound variable, dan menggunakan cleanup trap:

```bash
#!/bin/bash
# STARTER CODE (UNSAFE)
TMP="/tmp/app_log_dump"
mkdir $TMP
curl -s "https://api.github.com/zen" > $TMP/zen.txt
cat $TMP/zen.txt
rm -rf $TMP
```

<details>
<summary>Lihat Solusi Latihan 1</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

TMP_DIR=""

cleanup() {
    if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT INT TERM

TMP_DIR="$(mktemp -d -t app_log_dump.XXXXXX)"
curl -fsSL "https://api.github.com/zen" > "${TMP_DIR}/zen.txt"
cat "${TMP_DIR}/zen.txt"
```
</details>

---

### Latihan 2 (Tingkat Menengah): Atomic Transaction Pattern
Buat skrip yang mendownload payload, memverifikasi sha256 checksum-nya, dan melakukan replacement direktori atomik menggunakan symbolic link (`ln -sfn`). Jika download atau verifikasi sha256 gagal, state direktori aktif sebelumnya tidak boleh terpengaruh sedikit pun.

<details>
<summary>Lihat Solusi Latihan 2</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

DEPLOY_ROOT="/opt/myapp"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
CURRENT_SYMLINK="${DEPLOY_ROOT}/current"
NEW_RELEASE_ID="$(date +%Y%m%d%H%M%S)"
TARGET_RELEASE="${RELEASES_DIR}/${NEW_RELEASE_ID}"

cleanup() {
    local status=$?
    if (( status != 0 )) && [[ -d "${TARGET_RELEASE}" ]]; then
        echo "[ROLLBACK] Membersihkan release yang gagal dibuat: ${TARGET_RELEASE}" >&2
        rm -rf "${TARGET_RELEASE}"
    fi
    exit "${status}"
}
trap cleanup EXIT INT TERM

mkdir -p "${RELEASES_DIR}"
mkdir -p "${TARGET_RELEASE}"

echo "Simulated App Data" > "${TARGET_RELEASE}/app.bin"
echo "Validating payload..."

# Simulasi kegagalan jika payload kosong
if [[ ! -s "${TARGET_RELEASE}/app.bin" ]]; then
    echo "Payload kosong!" >&2
    exit 1
fi

# Atomic Switch via symlink (-s symbolic, -f force, -n treat symlink to directory as file)
ln -sfn "${TARGET_RELEASE}" "${CURRENT_SYMLINK}"
echo "Deployment berhasil dialihkan ke: ${NEW_RELEASE_ID}"
```
</details>

---

### Latihan 3 (Tingkat Lanjut): Menulis Full BATS Test Harness
Tulis sebuah test suite BATS untuk memverifikasi program CLI hipotetis `db_backup.sh` yang menerima argumen `-d <database>` dan flag `--compress`. Uji minimal 3 skenario:
1. Error jika `-d` tidak diberikan.
2. Sukses membuat dump file saat argumen valid.
3. Sukses menghasilkan format file `.gz` jika `--compress` disematkan.

<details>
<summary>Lihat Solusi Latihan 3</summary>

```bash
#!/usr/bin/env bats

setup() {
    TEST_DIR="$(mktemp -d)"
    # Mocking binary db_backup.sh untuk pengujian mandiri
    MOCK_SCRIPT="${TEST_DIR}/db_backup.sh"
    cat << 'EOF' > "${MOCK_SCRIPT}"
#!/usr/bin/env bash
set -euo pipefail
DB=""
COMPRESS=false

while [[ $# -gt 0 ]]; do
  case $1 in
    -d) DB="$2"; shift 2 ;;
    --compress) COMPRESS=true; shift ;;
    *) exit 64 ;;
  esac
done

[[ -z "${DB}" ]] && { echo "Error: Database wajib diisi" >&2; exit 64; }

TARGET_FILE="dump_${DB}.sql"
[[ "${COMPRESS}" == "true" ]] && TARGET_FILE="${TARGET_FILE}.gz"

touch "${TARGET_FILE}"
echo "SUCCESS:${TARGET_FILE}"
EOF
    chmod +x "${MOCK_SCRIPT}"
    cd "${TEST_DIR}"
}

teardown() {
    rm -rf "${TEST_DIR}"
}

@test "Gagal dengan code 64 saat flag -d diabaikan" {
    run ./db_backup.sh --compress
    [ "$status" -eq 64 ]
    [[ "$output" =~ "Database wajib diisi" ]]
}

@test "Berhasil membuat database dump standar" {
    run ./db_backup.sh -d "production"
    [ "$status" -eq 0 ]
    [ -f "dump_production.sql" ]
    [[ "$output" =~ "SUCCESS:dump_production.sql" ]]
}

@test "Berhasil membuat file terkompresi saat flag --compress aktif" {
    run ./db_backup.sh -d "production" --compress
    [ "$status" -eq 0 ]
    [ -f "dump_production.sql.gz" ]
    [[ "$output" =~ "SUCCESS:dump_production.sql.gz" ]]
}
```
</details>

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Diberikan cuplikan skrip berikut:**
    ```bash
    set -e
    false | true
    echo "Done"
    ```
    **Apakah kata `"Done"` akan dicetak ke console stdout?**
    *   A. Tidak, karena perintah `false` mengembalikan status 1 dan `set -e` langsung mematikan skrip.
    *   B. Ya, karena exit status pipeline ditentukan hanya oleh perintah terakhir (`true`), kecuali `set -o pipefail` diaktifkan.
    *   C. Tidak, Bash selalu memeriksa seluruh status dalam ekspresi pipeline.
    *   D. Tergantung versi POSIX operating system.
    *   *Jawaban yang Benar:* **B**
    *   *Penjelasan:* Secara default, Bash hanya melihat exit code command paling kanan dalam pipeline. Untuk mendeteksi kegagalan `false`, dibutuhkan `set -o pipefail`.

2.  **Apa yang terjadi jika variabel yang tidak dideklarasikan dipanggil di bawah instruksi `set -u`?**
    *   A. Variabel secara otomatis diinisialisasi menjadi string kosong `""`.
    *   B. Script memunculkan warning tetapi melanjutkan eksekusi ke baris berikutnya.
    *   C. Shell mencetak error `unbound variable` ke stderr dan langsung menghentikan proses dengan status non-zero.
    *   D. Nilai variabel diambil dari environment root global.
    *   *Jawaban yang Benar:* **C**
    *   *Penjelasan:* Flag `set -u` (`nounset`) menginstruksikan parser shell untuk memperlakukan ekspansi variabel yang belum didefinisikan sebagai invalid state fatal.

3.  **Mengapa `shopt -s inherit_errexit` sangat krusial di Bash 4.4+ saat menggunakan `set -e`?**
    *   A. Karena tanpa flag ini, eksekusi dalam background job (`&`) tidak dapat membaca environment variable.
    *   B. Karena secara default, Bash menonaktifkan mekanisme `set -e` di dalam command substitution subshell `$(...)`.
    *   C. Agar fungsi recursion dapat berjalan tanpa batasan stack depth limit.
    *   D. Untuk mengizinkan variable inheritance lintas proses `sudo`.
    *   *Jawaban yang Benar:* **B**
    *   *Penjelasan:* Historis POSIX menetapkan subshell tidak mewarisi `errexit`. Bash 4.4 memperkenalkan `inherit_errexit` agar command substitution `var=$(failing_command)` memicu error abort sebagaimana mestinya.

4.  **Apa tujuan perintah `trap - EXIT` di baris pertama dalam fungsi cleanup?**
    *   A. Menghapus memory swap proses Bash.
    *   B. Mematikan sinyal interrupt keyboard OS secara permanen.
    *   C. Melakukan deregistrasi signal handler untuk mencegah loop eksekusi rekursif jika ada failure di dalam fungsi cleanup itu sendiri.
    *   D. Mempercepat eksekusi proses termination.
    *   *Jawaban yang Benar:* **C**
    *   *Penjelasan:* Jika cleanup handler gagal dan memicu exit status non-zero di bawah `set -e`, handler bisa memanggil dirinya sendiri secara rekursif tak berujung jika trap tidak dinetralkan terlebih dahulu.

5.  **Audit static analysis ShellCheck mengeluarkan peringatan SC2086: `Double quote to prevent globbing and word splitting`. Manakah baris kode yang memicu error ini?**
    *   A. `rm -f "${TARGET_FILE}"`
    *   B. `rm -f $TARGET_FILE`
    *   C. `readonly TARGET_FILE="/tmp/out"`
    *   D. `if [[ -f "$TARGET_FILE" ]]; then`
    *   *Jawaban yang Benar:* **B**
    *   *Penjelasan:* Baris `$TARGET_FILE` tanpa double-quotes rentan terhadap pemecahan kata (word splitting) jika string mengandung spasi, serta rentan terhadap pathname expansion (globbing) jika string mengandung karakter wildcard seperti `*` atau `?`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **POSIX Standard:** IEEE Std 1003.1-2017 (Shell & Utilities - Section 2: Shell Command Language).
*   **GNU Bash Reference Manual:** Section 4.3.1 *The Set Builtin* & Section 3.2.5 *Pipelines*.
*   **Google Shell Style Guide:** Standar format dan coding convention shell script industri: `https://google.github.io/styleguide/shellguide.html`
*   **ShellCheck Wiki & AST Engine:** Dokumentasi komprehensif bug pattern shell script: `https://www.shellcheck.net/wiki/`
*   **BATS-core Project Repository:** Dokumentasi resmi Bash Automated Testing System: `https://github.com/bats-core/bats-core`

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Paradigma Fail-Fast:** Skrip Bash produksi harus selalu dimulai dengan konfigurasi `set -euo pipefail`, `IFS=$'\n\t'`, dan `shopt -s inherit_errexit` untuk menghentikan asumsi permisif default shell.
*   **Deterministic State Clean-Up:** Sinyal operasi sistem dan pseudo-signal shell (`EXIT`, `ERR`, `INT`, `TERM`) wajib diikat ke routing handler trap yang bertugas mengembalikan state OS, membuang data temporer, dan melepaskan resource locks.
*   **Verifikasi Perilaku Formal:** Keandalan logika script tidak boleh hanya diuji secara manual, melainkan harus diisolasi dan diuji menggunakan test framework terstruktur seperti **BATS**.
*   **Audit Statis Pre-deployment:** Mengintegrasikan **ShellCheck** pada proses development lokal dan CI pipeline adalah lini pertahanan pertama untuk menangkap celah keamanan variabel, escaping, dan portabilitas subshell.

---

## SEKSI 17 — GLOSARIUM

*   **Idempotence:** Karakteristik operasi di mana script dapat dieksekusi berkali-kali dengan parameter yang sama tanpa menghasilkan efek samping baru atau korupsi state sistem di luar eksekusi pertama.
*   **Unbound Variable:** Kondisi di mana variabel dipanggil dalam ekspresi shell sebelum nilainya diinisialisasi atau didefinisikan.
*   **Trap:** Fasilitas built-in Bash untuk mendaftarkan fungsi penanganan yang akan dipanggil saat proses menerima sinyal tertentu dari kernel atau runtime shell.
*   **Command Injection:** Kerentanan keamanan di mana input pengguna yang tidak disanitasi digabungkan langsung ke dalam shell interpreter, menyebabkan perintah arbitrer dieksekusi.
*   **Pipefail:** Opsi shell yang mengevaluasi exit code seluruh komponen pipeline; jika salah satu perintah gagal, exit status pipeline secara agregat akan bernilai kegagalan tersebut.
*   **BATS (Bash Automated Testing System):** Testing framework berbasis Test Anything Protocol (TAP) untuk Bash scripts.
*   **Subshell:** Proses shell turunan (child process) yang di-fork oleh shell utama untuk mengeksekusi grup perintah tertentu secara terisolasi.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:** Pastikan peserta didik memahami dengan jelas bahwa `set -e` **bukanlah solusi mutlak**. Perilaku `set -e` sering kali mengejutkan pada operasi kondisional: jika sebuah command gagal di dalam blok `if command; then`, `set -e` sengaja di-bypass oleh spesifikasi POSIX.
*   **Praktik Lab Interaktif:** Instruksikan peserta didik untuk sengaja mematikan script (`kill -SIGINT <pid>`) saat proses staging sedang berlangsung, lalu verifikasi apakah trap script berhasil membersihkan `/tmp` dan file lock atau meninggalkannya dalam status *dangling*.
*   **Debugging Mindset:** Tekankan pemakaian `bash -x` (xtrace mode) atau injection runtime environment `PS4='+ $(date "+%H:%M:%S") [${BASH_SOURCE}:${LINENO}] ' bash -x script.sh` saat mendiagnosis script defensif yang abort tanpa pesan error yang jelas.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis | Perubahan Utama |
| :--- | :--- | :--- | :--- |
| `1.0.0` | 2024-03-30 | Senior Core Systems Architect | Inisialisasi materi Defensive Scripting, Testing BATS, dan Static Analysis AST. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `← Bab 08: Process Management, Signals & Job Control`
*   **Modul Saat Ini:** `Bab 09 Module 01: Defensive Scripting, Testing & Audit`
*   **Modul Berikutnya:** `Bab 10: Production Operations, Automation & Enterprise Deployment Patterns →`