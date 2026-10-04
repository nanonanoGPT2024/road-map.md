## SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum**: Shell & Bash Systems Automation
*   **Kategori**: 01-Core-Foundations
*   **Bab**: 04 — Logika Kontrol, Arithmetic & Exit Codes
*   **Modul**: 01 — Eksekusi Kondisional, Evaluasi Aritmetika, dan Arsitektur Exit Status
*   **Kode Modul**: BSH-01-04-01
*   **Tingkat Kesulitan**: Intermediate
*   **Prasyarat**:
    *   BSH-01-02-01: Anatomi Perintah Linux & Shell Expansion Mechanics
    *   BSH-01-03-01: Variabel, Parameter Expansion, dan Shell Environment
*   **Target Audience**: Systems Engineers, Site Reliability Engineers (SRE), Platform Engineers, dan DevOps Developers yang membutuhkan determinisme absolut dalam automasi infrastruktur Linux.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:

1.  **Mendiagnosis dan Mengontrol Eksekusi Program Berdasarkan Exit Status ($?)**: Mengonseptualisasikan rentang kode status keluar (0–255), memanfaatkan logika terminasi proses POSIX, dan mengelola sinyal abnormal proses (status 128+N).
2.  **Memilih dan Mengimplementasikan Conditional Constructs Secara Tepat**: Membedakan secara mekanis perbedaan pemrosesan antara *POSIX Test Command* (`test` atau `[`), *Bash Keyword Compound Command* (`[[`), dan *Arithmetic Evaluation* (`((` atau `$((`)).
3.  **Mencegah Kerentanan Parsing dan Word Splitting pada Pengujian Logika**: Membangun pengkondisian defensif yang kebal terhadap *pathname expansion*, variabel kosong/tak terdefinisi, dan injeksi parameter.
4.  **Mengeksekusi Operasi Matematika Deterministik 64-bit**: Memanfaatkan Arithmetic Expansion `$(( ... ))` untuk kalkulasi integer performa tinggi tanpa spawning subshell atau dependensi binary eksternal.
5.  **Membangun Pola Alur Kontrol Kompleks**: Mengembangkan blok percabangan `if/elif/else` dan `case` berbasis *Pattern Matching (Globbing/Extended Globbing)* yang aman, terisolasi, dan mudah di-maintain.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       ┌────────────────────────────────────────┐
                       │     KONTROL ALUR & EVALUASI BASH       │
                       └───────────────────┬────────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌──────────────────┐             ┌──────────────────┐             ┌──────────────────┐
│   EXIT STATUS    │             │   TEST RUNTIMES  │             │    ARITHMETIC    │
│    Code: 0..255  │             │   Syntax & Logic │             │   64-bit Int     │
└────────┬─────────┘             └────────┬─────────┘             └────────┬─────────┘
         │                                │                                │
    ┌────┴────┐                      ┌────┴────┐                      ┌────┴────┐
    │         │                      │         │                      │         │
    ▼         ▼                      ▼         ▼                      ▼         ▼
  0=TRUE   1..255=ERR            `[` / `test`  `[[ ... ]]`        `$(( ... ))`  `(( ... ))`
 (Success) (Failure)             (POSIX Word)  (Bash Keyword)     (Value Subs)  (Exit Status)
    │         │                      │         │                      │         │
    └────┬────┘                      └────┬────┘                      └────┬────┘
         │                                │                                │
         └────────────────────────────────┼────────────────────────────────┘
                                          │
                                          ▼
                       ┌────────────────────────────────────────┐
                       │          CONTROL STRUCTURES            │
                       │  - if / elif / else (Branching)        │
                       │  - case ... in (Jump/Pattern Matching) │
                       │  - && / || (Short-circuit Pipelines)   │
                       └────────────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam bahasa pemrograman tingkat tinggi (seperti Python, Go, atau Rust), evaluasi logika berkisar pada tipe data *Boolean* murni (`true` dan `false`), sedangkan exceptions atau error handling ditangani via kontrol khusus (*try/catch*, `Result<T, E>`).

Dalam sistem Unix/Linux dan Bash Shell, **fondasi logika dibangun sepenuhnya di atas Exit Status proses**. 

Kegagalan memahami paradigma ini menyebabkan:
1.  **Inversi Logika Bencana**: Di Bash, angka `0` merepresentasikan **SUCCESS (True)**, sedangkan angka integer bukan-nol (1-255) merepresentasikan **FAILURE (False)**. Salah menafsirkan angka 0 sebagai *falsy* dapat merusak pipeline deployment secara fatal.
2.  **Kerentanan Ekspansi Eksekusi (Vulnerabilities)**: Penggunaan `[ $var = "target" ]` tanpa double quotes akan melempar error sintaks `unary operator expected` atau mengeksekusi ekspansi yang tidak diinginkan bila `$var` bernilai kosong atau memuat spasi.
3.  **Degradasi Performa Fatal (Fork Bombing)**: Melakukan kalkulasi matematika sederhana menggunakan eksternal tool seperti `echo "$a + $b" | bc` atau `expr` di dalam loop berskala jutaan iterasi akan membebani kernel Linux dengan pemanggilan *fork-exec-exit cycle* jutaan kali, yang seharusnya dapat dieksekusi dalam fraksi milidetik via internal shell built-in `$(( ... ))`.

Otomasi infrastruktur level produksi menuntut skrip shell yang deterministik. Memahami cara kerja evaluasi logika shell secara mekanikal adalah satu-satunya metode untuk menjamin stabilitas runtime.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Exit Status ($?)
Setiap kali sebuah perintah, subshell, fungsi, atau pipeline Bash menyelesaikan eksekusi, kernel mengembalikan nilai integer sebesar 8-bit unsigned (rentang nilai 0 hingga 255) kepada proses induk (parent process). Bash menyimpan nilai ini ke dalam parameter khusus `$?`.
*   `0`: Berhasil (Operasi sukses, pengujian kondisi benar).
*   `1 - 125`: Kode error generik yang dikembalikan program (aplikasi mendefinisikan artinya secara bebas).
*   `126`: Perintah ditemukan tetapi tidak memiliki izin eksekusi (*Permission denied*).
*   `127`: Perintah tidak ditemukan dalam direktori `$PATH` (*Command not found*).
*   `128`: Argument fatal terhadap `exit`.
*   `128+N`: Proses dihentikan paksa oleh sinyal fatal Linux nomor `N` (Contoh: `130` = terminated by Ctrl+C / SIGINT [128 + 2]; `137` = killed by OOM Killer / SIGKILL [128 + 9]).

### 2. POSIX `[` vs Bash `[[`
*   `[` (dikenal juga sebagai `test`): Merupakan program standar POSIX. Meskipun saat ini sudah menjadi shell built-in di hampir semua distro, ia tetap diparsing mengikuti aturan command execution standar: seluruh argumen di dalamnya diproses melalui word splitting dan pathname expansion sebelum evaluasi dilakukan.
*   `[[ ... ]]`: Merupakan *compound command* / Bash keyword khusus. Bash mem-parsing konten di dalam `[[` secara mandiri. Ini menonaktifkan word splitting dan globbing tak disengaja, sekaligus membuka fitur modern seperti perbandingan regex (`=~`) dan pattern matching (`==`).

### 3. Evaluasi Aritmetika
*   `$(( EXPR ))`: *Arithmetic Expansion*. Mengevaluasi ekspresi matematika dan menggantinya dengan nilai hasil (string representasi dari integer).
*   `(( EXPR ))`: *Arithmetic Command*. Mengevaluasi ekspresi dan mengembalikan **Exit Status**: jika hasil akhir kalkulasi bukan-nol, exit status adalah `0` (Success); jika kalkulasi menghasilkan angka `0`, exit status bernilai `1` (Failure).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Pengambilan Exit Status

Saat sebuah proses anak diterminasi via system call `exit_group(status)` atau `exit(status)`, Linux kernel memperbarui status pada Process Control Block (PCB). Parent process memanggil sistem call `wait()` atau `waitpid()` untuk mengumpulkan metadata status ini. Bash mengekstrak 8-bit terendah:

$$\text{Exit Status} = \text{Raw Status} \ \& \ \text{0xFF}$$

Ini membatasi rentang nilai keluar strictly antara 0 hingga 255. Pengembalian nilai 256 akan menjadi `0`, dan -1 akan dikonversi menjadi `255`.

### Alur Parsing: `[` (Builtin) vs `[[` (Keyword)

Saat skrip mengeksekusi:
```bash
[ "$a" = "$b" ]
```
1. Shell Lexer dan Parser melihat token `[` sebagai nama perintah.
2. Argument expansion dijalankan: `$a` dan `$b` diekspansi. Jika tidak di-quote dan mengandung spasi, word splitting memecahnya menjadi token-token terpisah.
3. Perintah `[` dieksekusi, mencari token penutup `]` sebagai argumen terakhir. Bila token berlebih (akibat unquoted space), `[` memicu error: `too many arguments`.

Saat skrip mengeksekusi:
```bash
[[ $a == $b ]]
```
1. Lexer mengenali keyword `[[`. Shell beralih ke mode parsing khusus *conditional expression*.
2. Variabel `$a` tidak dipecah menjadi beberapa *words* walaupun bernilai `foo bar baz`.
3. Sisi kanan (`$b`) diperlakukan sebagai pattern glob (atau literal jika di-quote).
4. Operator penutup `]]` diverifikasi langsung di level grammar AST (*Abstract Syntax Tree*), bukan dievaluasi sebagai argumen command.

### Logika Short-Circuit (`&&` dan `||`)

Bash mengevaluasi ekspresi dari kiri ke kanan dengan konsep *short-circuit*:
*   `CMD1 && CMD2`: `CMD2` HANYA dieksekusi jika dan hanya jika `CMD1` menghasilkan exit status `0`.
*   `CMD1 || CMD2`: `CMD2` HANYA dieksekusi jika `CMD1` menghasilkan exit status BUKAN `0`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Siklus Evaluasi Exit Status dan Kontrol `if`

```
  Kueri Perintah / Blok Evaluasi
              │
              ▼
   ┌──────────────────────┐
   │ Jalankan: <COMMAND>  │ ──► [Fork/Exec atau Builtin]
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Tangkap Exit Status  │ ──► Disimpan ke parameter `$?`
   │ (Range 0 - 255)      │
   └──────────┬───────────┘
              │
              ▼
       Apakah $? == 0 ?
        /          \
     (YA)          (TIDAK)
      /              \
     ▼                ▼
┌──────────────┐   ┌──────────────┐
│ Blok "then"  │   │ Blok "else"  │
│ dieksekusi   │   │ dieksekusi   │
└──────────────┘   └──────────────┘
```

### Pemrosesan Variabel: `[` (Test) vs `[[` (Conditional Keyword)

```
KASUS: var="alpha beta"

Evaluasi: [ $var = "alpha beta" ]
  │
  ├─ 1. Word Splitting ──► [ "alpha" "beta" = "alpha beta" ]
  ├─ 2. Count Tokens  ──► Ditemukan 5 token argumen!
  └─ 3. Hasil         ──► ERROR: [: too many arguments

Evaluasi: [[ $var == "alpha beta" ]]
  │
  ├─ 1. Keyword bypass ──► Bash mempertahankan boundary string
  ├─ 2. Comparison     ──► Compares string "alpha beta" with "alpha beta"
  └─ 3. Hasil         ──► SUCCESS (Exit status 0)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut demonstrasi sintaks fundamental untuk verifikasi operasi aritmetika, pembandingan string, dan penangkapan exit status secara langsung di bash shell.

```bash
#!/usr/bin/env bash
# File: demo_simple.sh
set -u # Cegah unbound variables

# 1. Menangkap Exit Status Command
ls /tmp >/dev/null 2>&1
status_sukses=$?
echo "Exit code ls sukses: ${status_sukses}" # Output: 0

ls /direktori_yang_pasti_tidak_ada >/dev/null 2>&1
status_gagal=$?
echo "Exit code ls gagal: ${status_gagal}"   # Output: 2 (pada GNU coreutils)

# 2. Arithmetic Context ($(( )) dan (( )))
num1=40
num2=2

# Arithmetic Expansion (mengembalikan nilai)
sum=$(( num1 + num2 ))
echo "Hasil penjumlahan: ${sum}"             # Output: 42

# Arithmetic Command (mengembalikan exit code)
(( sum == 42 ))
echo "Apakah sum == 42? Status: $?"          # Output: 0 (True)

(( sum > 100 ))
echo "Apakah sum > 100? Status: $?"         # Output: 1 (False)

# 3. String & Regex Matching dengan [[ ... ]]
hostname="prod-k8s-worker-01.corp.internal"

if [[ "${hostname}" =~ ^prod-k8s-[a-z]+-[0-9]{2} ]]; then
    echo "Hostname valid untuk cluster production."
else
    echo "Pola hostname tidak valid!"
fi
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skrip operasional level produksi untuk memvalidasi penggunaan ruang disk, ketersediaan port jaringan, alokasi memori swap, dan mengembalikan exit code terstandarisasi untuk monitoring agent (misal: Nagios, Zabbix, Datadog).

```bash
#!/usr/bin/env bash
#
# ==============================================================================
# SCRIPT: host_health_probe.sh
# DESKRIPSI: Diagnostic probe untuk kesehatan resource server.
#             Mengimplementasikan evaluasi aritmetika, case matching,
#             dan exit status berstandar Nagios/Monitoring (0, 1, 2, 3).
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail

# Konvensi Exit Code Monitoring
readonly STATUS_OK=0
readonly STATUS_WARNING=1
readonly STATUS_CRITICAL=2
readonly STATUS_UNKNOWN=3

# Threshold
readonly DISK_WARN_THRESHOLD=80
readonly DISK_CRIT_THRESHOLD=90

probe_disk_usage() {
    local partition="${1}"
    
    # Verifikasi keberadaan partisi
    if ! df -P "${partition}" >/dev/null 2>&1; then
        echo "UNKNOWN: Partisi ${partition} tidak ditemukan pada filesystem."
        return "${STATUS_UNKNOWN}"
    fi

    # Ambil persentase (integer) tanpa dependensi eksternal selain awk
    local usage_pct
    usage_pct=$(df -P "${partition}" | awk 'NR==2 {gsub("%",""); print $5}')

    # Validasi bahwa usage_pct adalah integer murni menggunakan Bash Regex
    if [[ ! "${usage_pct}" =~ ^[0-9]+$ ]]; then
        echo "UNKNOWN: Gagal membaca metrik disk secara valid (Output: ${usage_pct})."
        return "${STATUS_UNKNOWN}"
    fi

    # Evaluasi Aritmetika menggunakan compound command (( ... ))
    if (( usage_pct >= DISK_CRIT_THRESHOLD )); then
        echo "CRITICAL: Penggunaan disk ${partition} mencapai ${usage_pct}% (>= ${DISK_CRIT_THRESHOLD}%)"
        return "${STATUS_CRITICAL}"
    elif (( usage_pct >= DISK_WARN_THRESHOLD )); then
        echo "WARNING: Penggunaan disk ${partition} mencapai ${usage_pct}% (>= ${DISK_WARN_THRESHOLD}%)"
        return "${STATUS_WARNING}"
    else
        echo "OK: Penggunaan disk ${partition} normal pada ${usage_pct}%"
        return "${STATUS_OK}"
    fi
}

probe_network_port() {
    local host="${1}"
    local port="${2}"

    # Validasi port number adalah integer 1-65535
    if (( port < 1 || port > 65535 )); then
        echo "UNKNOWN: Nomor port ${port} berada di luar batas valid (1-65535)."
        return "${STATUS_UNKNOWN}"
    fi

    # Menggunakan pseudo-device network Bash /dev/tcp
    # Timeout diset menggunakan subshell timeout jika tersedia, atau command timeout
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null; then
        echo "OK: Terhubung ke ${host}:${port}"
        return "${STATUS_OK}"
    else
        echo "CRITICAL: Koneksi ke ${host}:${port} gagal atau timeout."
        return "${STATUS_CRITICAL}"
    fi
}

main() {
    local check_type="${1:-}"
    
    # Pola seleksi eksekusi menggunakan case .. in (Pattern Matching)
    case "${check_type}" in
        disk)
            local target_partition="${2:-/}"
            probe_disk_usage "${target_partition}"
            exit $?
            ;;
        port)
            local target_host="${2:-127.0.0.1}"
            local target_port="${3:-}"
            
            if [[ -z "${target_port}" ]]; then
                echo "UNKNOWN: Argumen port wajib disediakan."
                exit "${STATUS_UNKNOWN}"
            fi
            
            probe_network_port "${target_host}" "${target_port}"
            exit $?
            ;;
        *)
            echo "Usage: $0 {disk <mount_point> | port <host> <port>}"
            exit "${STATUS_UNKNOWN}"
            ;;
    esac
}

main "$@"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Kelebihan | Kekurangan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **POSIX `[` (`test`)** | Portabilitas absolut antar berbagai shell (`dash`, `ash`, `sh`, `zsh`, `ksh`). | Rawan terhadap *word splitting* dan pathname expansion; tidak mendukung regex bawaan; sintaks kaku. | Skrip init ringan (Alpine/BusyBox), skrip dasar instalasi POSIX murni. |
| **Bash `[[ ... ]]`** | Penanganan variabel aman dari whitespace; mendukung pattern matching wildcard & Regex (`=~`); operator logika `&&` / `\|\|` natural. | Non-portabel di luar bash/zsh/ksh; sintaks invalid di `dash` (Debian/Ubuntu `/bin/sh`). | Standar de-facto untuk skrip Bash tingkat produksi, automasi CI/CD modern. |
| **Aritmetika `$(( ))`** | Sangat cepat; built-in di dalam shell runtime; tidak memerlukan subprocess fork; mendukung integer signed 64-bit. | **Hanya mendukung integer**. Tidak bisa menghitung floating-point (desimal) seperti `3.14 * 2`. | Loop counter, kalkulasi metrik byte/persentase, indexing array. |
| **Eksternal `bc` / `awk`** | Mendukung kalkulasi presisi tinggi dan operasi desimal/floating-point floating-point yang kompleks. | Mahal secara CPU context-switching karena memanggil child process baru (`fork-exec`). | Diperlukan kalkulasi rata-rata beban sistem (load average) atau matematika presisi. |
| **`if ... elif` vs `case`** | `if` fleksibel untuk evaluasi kondisi majemuk dengan berbagai operator. | `case` jauh lebih efisien dan bersih jika membandingkan satu variabel against multiple glob patterns. | Gunakan `case` saat mem-parsing opsi CLI atau status string terstruktur. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan `[[ ... ]]` Secara Default pada Bash Scripting**: Singkirkan penggunaan `[` kecuali ditargetkan secara eksplisit untuk skrip portabel `/bin/sh`.
2.  **Hindari Membandingkan String dengan Operator Numerik**:
    *   SALAH: `[[ "${counter}" -eq "admin" ]]` (Bash memaksa konversi string `"admin"` menjadi integer `0`, menghasilkan bug logika fatal).
    *   BENAR: `[[ "${counter}" == "admin" ]]` untuk string, dan `(( counter == 0 ))` untuk integer.
3.  **Gunakan Format Evaluasi Numerik Khusus `(( ... ))`**: Alih-alih `[[ $val -gt 10 ]]`, format `(( val > 10 ))` lebih mudah dibaca, native secara semantik, dan tidak memerlukan resolusi variabel manual (`$`).
4.  **Terapkan Explicit Variable Quoting di Sisi Kanan `[[` Jika Membutuhkan Kesetaraan Literal**:
    ```bash
    pattern="*.txt"
    [[ "notes.txt" == $pattern ]]   # TRUE (Regex/Glob expansion: cocok dengan .txt)
    [[ "notes.txt" == "$pattern" ]] # FALSE (Literal comparison: mencari string *.txt)
    ```
5.  **Jaga Konsistensi Exit Codes**: Gunakan `exit 0` untuk terminasi sukses, dan tentukan angka exit status non-zero yang unik untuk mengisolasi akar kegagalan skrip.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Inversi Konseptual Boolean
*Kesalahan fatal bagi programmer pemula:*
```bash
# SALAH: Menganggap 0 adalah False dan 1 adalah True
if 0; then # Syntax error: Bash mencoba menjalankan command bernama '0'
    echo "Zero is True?"
fi
```
**Koreksi**: Evaluasi logika Bash melihat exit code eksekusi program.
```bash
if true; then  # Command 'true' selalu exit dengan status 0
    echo "Sukses!"
fi
```

### 2. Spasi yang Hilang pada Operator `[` dan `[[`
```bash
# SALAH: Mengabaikan whitespace boundary
if [[$foo == "bar"]]; then  # bash: [[foo: command not found
if [ "$foo"="$bar" ]; then  # Dievaluasi sebagai single argument non-empty (selalu bernilai True!)
```
**Koreksi**: Karena `[` adalah command dan `[[` adalah token penanda, spasi pemisah wajib disertakan:
```bash
if [[ "$foo" == "$bar" ]]; then
if [ "$foo" = "$bar" ]; then
```

### 3. Menggunakan Pembanding String untuk Angka dengan Zero-Padding
```bash
val1="08"
val2="8"
if [ "$val1" = "$val2" ]; then
    echo "Sama"
else
    echo "Beda!" # Output: Beda! (Karena evaluasi string '08' != '8')
fi
```
**Koreksi**: Gunakan arithmetic evaluation, tetapi waspadai leading-zero yang diinterpretasikan sebagai **oktal**:
```bash
# Operasi (( 10#$val1 == 10#$val2 )) memaksa pemrosesan menggunakan basis desimal (base-10)
if (( 10#${val1} == 10#${val2} )); then
    echo "Sama secara numerik"
fi
```

### 4. Overwriting Parameter `$?` Sebelum Digunakan
```bash
rm -rf /opt/critical_service/data
echo "Mencoba menghapus folder..."
if [[ $? -eq 0 ]]; then # BUG: $? sekarang memuat exit code dari perintah 'echo', bukan 'rm'!
    echo "Pembersihan selesai"
fi
```
**Koreksi**: Simpan `$?` segera setelah eksekusi target, atau tempatkan perintah langsung dalam blok `if`:
```bash
if rm -rf /opt/critical_service/data; then
    echo "Pembersihan selesai"
fi
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Safe Number Parsing & Arithmetic Engine
*   **Target**: Buat fungsi bernama `safe_calculate` yang menerima 3 argumen: `OPERAND_A`, `OPERATOR`, `OPERAND_B`.
*   **Ketentuan**:
    1. Validasi `OPERAND_A` dan `OPERAND_B` harus berupa integer (positif atau negatif).
    2. `OPERATOR` hanya boleh salah satu dari: `+`, `-`, `*`, `/`, `%`.
    3. Cegah skenario *division by zero* (pembagian dengan nol) dan kembalikan exit code `101`.
    4. Kembalikan hasil perhitungan ke stdout jika valid, serta exit code `0`.

### Lab 2: Network Health Status Evaluator
*   **Target**: Tulis skrip yang memindai array berisikan 3 domain/IP (misal: `127.0.0.1`, `8.8.8.8`, `192.0.2.1`).
*   **Ketentuan**:
    1. Eksekusi ping 1 paket dengan deadline timeout 2 detik untuk setiap target.
    2. Gunakan operator short-circuit `&&` dan `||` untuk mencetak log status: `"[IP] ONLINE"` atau `"[IP] OFFLINE"`.
    3. Simpan jumlah kegagalan menggunakan ekspansi aritmetika `$(( failures++ ))`.
    4. Jika seluruh host tidak dapat dihubungi, skrip keluar dengan status exit `2`; jika ada setidaknya satu yang offline, keluar dengan status `1`; jika seluruhnya sukses, keluar dengan `0`.

### Lab 3: Log Parser Berbasis `case` dan Pattern Matching
*   **Target**: Buat pipeline sederhana yang membaca file log baris demi baris.
*   **Ketentuan**:
    1. Klasifikasikan setiap baris:
        *   Jika memuat pola `*[ERROR]*` atau `*[FATAL]*`, tambahkan counter `$errors`.
        *   Jika memuat pola `*[WARN]*`, tambahkan counter `$warnings`.
        *   Jika memuat pola `*[INFO]*`, abaikan.
        *   Kondisi default (format anomali), tulis ke stderr.
    2. Outputkan ringkasan metrik akhir dalam format JSON menggunakan integer evaluation.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Jika sebuah command Bash diakhiri paksa oleh sinyal `SIGTERM` (Sinyal nomor 15), berapakah nilai Exit Status ($?) yang dikembalikan ke shell?**
    *   A. 15
    *   B. 1
    *   C. 143
    *   D. 255
    *   *Kunci Jawaban*: C. *Penjelasan*: Sinyal fatal Linux yang menterminasi proses menyebabkan shell menghitung exit status dengan formula $128 + N$. Untuk SIGTERM ($N=15$), exit code adalah $128 + 15 = 143$.

2.  **Manakah ekspresi aritmetika berikut yang mengembalikan Exit Status `0` (Success)?**
    *   A. `(( 5 - 5 ))`
    *   B. `(( 10 * 0 ))`
    *   C. `(( 42 > 10 ))`
    *   D. `(( 0 ))`
    *   *Kunci Jawaban*: C. *Penjelasan*: Pada *Arithmetic Command* `(( ... ))`, exit status dihitung dari evaluasi matematika: jika hasil evaluasi adalah non-zero (dalam logika C, angka bukan-nol adalah True), Bash menghasilkan exit code `0`. Operasi `42 > 10` bernilai logika `1` (True/Non-zero), sehingga exit codenya adalah `0`. Sebaliknya, opsi A, B, dan D menghasilkan nilai numerik `0`, yang pada arithmetic context dikonversi menjadi exit status `1` (Failure).

3.  **Diberikan cuplikan skrip berikut:**
    ```bash
    var=""
    [ -n $var ] && echo "Ada" || echo "Kosong"
    ```
    **Apakah output dari skrip tersebut, dan mengapa?**
    *   A. "Kosong", karena variabel bernilai empty string.
    *   B. "Ada", karena ketiadaan tanda kutip pada `$var` menyebabkan perintah dievaluasi sebagai `[ -n ]`, yang secara inheren mengembalikan sukses jika hanya ada 1 argumen.
    *   C. Error: syntax error unexpected token.
    *   D. "Kosong", karena `-n` memvalidasi null value.
    *   *Kunci Jawaban*: B. *Penjelasan*: Ini adalah jebakan klasik POSIX `[`: Ketika unquoted `$var` diekspansi menjadi string kosong, parser mereduksi ekspresi menjadi `[ -n ]`. Menurut spesifikasi POSIX test, jika `[` dipanggil dengan hanya satu argumen string (dalam hal ini string `-n`), ia akan mengembalikan status `0` (True) selama argumen tersebut bukan null, mengabaikan fakta bahwa `-n` semestinya adalah operator unary. Inilah alasan fundamental mengapa `[[ -n $var ]]` jauh lebih aman digunakan.

4.  **Apa perbedaan mendasar antara `[[ $str == "v*" ]]` dan `[[ $str == v* ]]`?**
    *   A. Keduanya sama persis, tanda kutip diabaikan.
    *   B. Yang pertama mencocokkan string literal `v*`, yang kedua memperlakukan `v*` sebagai glob pattern yang cocok dengan string apa pun yang diawali huruf 'v'.
    *   C. Yang pertama adalah regular expression, yang kedua adalah wildcard glob.
    *   D. Yang pertama menghasilkan error sintaks.
    *   *Kunci Jawaban*: B. *Penjelasan*: Dalam keyword `[[`, string sisi kanan yang tidak di-quote akan dianggap sebagai pattern (globbing), sedangkan yang diapit tanda kutip diperlakukan sebagai literal value identik.

5.  **Perhatikan kode berikut:**
    ```bash
    false || true && false
    echo $?
    ```
    **Berapakah angka yang dicetak?**
    *   A. 0
    *   B. 1
    *   C. 127
    *   D. False
    *   *Kunci Jawaban*: B. *Penjelasan*: Di Bash, operator `&&` dan `||` memiliki prioritas presedensi yang sama dan dievaluasi secara asosiatif dari kiri ke kanan. 
        1. `false || true`: `false` (status 1) gagal, maka cabang `||` dieksekusi -> `true` (status 0).
        2. Status saat ini adalah 0 (sukses).
        3. `... && false`: Karena step sebelumnya bernilai 0, cabang `&&` dieksekusi -> `false` (status 1).
        4. Exit status akhir adalah `1`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Manual Bash Resmi (GNU Project)**:
    *   Bagian 3.2.4.2: *Conditional Constructs* (`man bash` atau `info bash`)
    *   Bagian 6.5: *Shell Arithmetic*
*   **Standar POSIX IEEE 1003.1-2017**:
    *   Spesifikasi Utility: `test` ([The Open Group Base Specifications Issue 7](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/test.html))
*   **Buku & Repositori Rujukan**:
    *   *Pure Bash Bible* oleh Dylan Araps (Kompilasi algoritma aritmetika dan logika kontrol tanpa dependensi eksternal).
    *   *Classic Shell Scripting* oleh Arnold Robbins & Nelson H.F. Beebe (O'Reilly Media).
*   **Bash Hackers Wiki**:
    *   Dokumentasi mendalam mengenai *Compound Commands* dan arsitektur token parser Bash.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Paradigma Boolean**: Exit code `0` berarti Sukses (True), kode bukan-nol (`1-255`) berarti Gagal (False). Ini adalah fondasi dari seluruh branching `if`, `while`, dan chaining `&&` / `||`.
2.  **`[[ ... ]]` vs `[ ... ]`**: Gunakan `[[ ... ]]` untuk script Bash modern karena kebal terhadap *word splitting*, mendukung Regex via operator `=~`, dan pola globbing tingkat lanjut. Pertahankan `[` hanya jika Anda menulis script cross-shell yang harus compliant terhadap standar POSIX murni.
3.  **Aritmetika Native**: Bash menyediakan mesin hitung signed integer 64-bit native melalui `$(( ... ))` untuk ekspansi nilai dan `(( ... ))` untuk pengujian kondisi. Jangan gunakan `expr` atau pipe ke `bc` untuk kalkulasi integer rutin.
4.  **Signal Propagation**: Nilai `$?` di atas 128 umumnya merepresentasikan terminasi mendadak akibat sinyal sistem (`128 + Sinyal`). Selalu evaluasi `$?` seawal mungkin sebelum tertimpa oleh pemanggilan perintah baru.

---

## SEKSI 17 — GLOSARIUM

*   **Exit Status / Exit Code**: Nilai numerik 8-bit (0-255) yang dikirimkan oleh proses anak kepada proses induk saat proses berhenti, merepresentasikan status akhir eksekusinya.
*   **Short-Circuit Evaluation**: Mekanisme peninjauan ekspresi logika di mana operan kedua hanya dievaluasi jika hasil operan pertama belum cukup untuk menentukan output akhir (misal: `&&` dan `||`).
*   **Word Splitting**: Proses pemisahan string menjadi beberapa token/kata terpisah oleh shell berdasarkan karakter pembatas internal (*Internal Field Separator* / `$IFS`), seringkali memicu bug jika variabel tidak di-quote dengan benar pada `[` atau perintah Linux biasa.
*   **Compound Command**: Konstruksi sintaksis shell tingkat tinggi yang diperlakukan sebagai satu kesatuan unit perintah, seperti `[[ ... ]]`, `(( ... ))`, atau `{ ...; }`.
*   **Arithmetic Expansion**: Mekanisme shell yang mengevaluasi ekspresi matematika di dalam blok `$(( ... ))` dan menimpa konstruksi tersebut dengan hasil numeriknya.
*   **Pattern Matching**: Mekanisme Bash untuk mencocokkan string menggunakan metakarakter wildcard (seperti `*`, `?`, `[...]`, dan Extended Globbing).

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Titik Rawan Pemahaman Siswa**:
    *   Mayoritas siswa dengan latar belakang bahasa seperti Python/JavaScript akan terus menerus tertukar menganggap `0 == false`. Tekankan berulang-ulang: *“In Shell, Zero means Zero Errors (Success)”*. Buat demonstrasi langsung di terminal dengan mengetik `ls; echo $?`.
    *   Jelaskan secara visual mengapa `[ $a = $b ]` meledak saat `$a` bernilai string kosong. Perlihatkan output eksekusi dengan `set -x` (*xtrace*) agar token parsing terlihat dengan jelas di layar.
*   **Tips Pedagogis**:
    *   Tunjukkan disassembler/trace level sistem dengan `strace -e trace=process,wait4 <script>` agar siswa melihat pemanggilan *syscall* kernel Linux saat mengembalikan return value proses.
    *   Saat mengajarkan ekspresi numerik, pastikan siswa memahami bahwa Bash **TIDAK MENDUKUNG FLOATING POINT**. Tunjukkan apa yang terjadi saat mengeksekusi `echo $(( 10 / 3 ))` (hasilnya `3`, bukan `3.333`).

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0** (2024-03-24):
    *   Rilis awal materi kurikulum sesuai standar kurikulum GEMINI.md.
    *   Mencakup arsitektur 8-bit Exit Status, perbandingan mendalam POSIX `[` vs Bash `[[`, ekspansi aritmetika internal, dan pola pertahanan defensive programming.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**:
    *   `BSH-01-03-01`: Variabel, Parameter Expansion, dan Shell Environment
*   **Modul Saat Ini**:
    *   `BSH-01-04-01`: Eksekusi Kondisional, Evaluasi Aritmetika, dan Arsitektur Exit Status
*   **Modul Berikutnya**:
    *   `BSH-01-04-02`: Loop Control, File Iteration, dan I/O Redirection Mechanics