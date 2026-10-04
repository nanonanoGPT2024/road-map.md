## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul**: BASH-01-03
*   **Judul Modul**: Variabel, Parameter Expansion & Tipe Data
*   **Kategori**: 01-Core-Foundations
*   **Prasyarat**: 
    *   BASH-01-01 (Arsitektur Shell & POSIX Standards)
    *   BASH-01-02 (Proses Eksekusi Shell, Fork-Exec Model & Subshell)
*   **Target Audiens**: Systems Engineers, DevOps/SRE Platform Engineers, Shell Script Tool Developers
*   **Tingkat Kesulitan**: Intermediate
*   **Estimasi Waktu Selesai**: 120 Menit
*   **Target Rilis Engine**: GNU Bash 4.x / 5.x (dengan catatan kompatibilitas POSIX Shell)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis dan Membedakan** model tipe data internal Bash (*stringly-typed system*) dan bagaimana atribut variabel dikontrol melalui built-in `declare` / `typeset`.
2.  **Mengoptimalkan Performa Skrip Shell** secara radikal dengan mengganti pemanggilan sub-proses eksternal (*fork-exec overhead* dari binary seperti `sed`, `awk`, `cut`, `basename`, `dirname`, `tr`) menggunakan *Native Parameter Expansion*.
3.  **Mengimplementasikan Mekanisme Parameter Expansion Lanjutan**, mencakup *fallback values*, *substring slicing*, *pattern stripping* (prefix/suffix), *search and replace*, *case modification*, dan *indirect variable expansion*.
4.  **Mendiagnosis dan Memitigasi Bug Kritis** terkait isu keamanan dan integritas data, seperti *Word Splitting*, *Pathname Expansion (Globbing)* pada ekspansi variabel yang tidak diapit tanda kutip (*unquoted expansion*), serta status pembeda antara *unset* vs *null/empty variable*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    ┌────────────────────────────────────────────────────────┐
                    │            BASH PARAMETER EVALUATION                   │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
  ┌──────────────────────────────┐                              ┌──────────────────────────────┐
  │   STORAGE & ATTRIBUTES       │                              │     EXPANSION MECHANISMS     │
  ├──────────────────────────────┤                              ├──────────────────────────────┤
  │ • Stringly-typed (Default)   │                              │ 1. Defensive Defaults:       │
  │ • declare -i (Integer)       │                              │    ${v:-d}, ${v:=d}, ${v:?e} │
  │ • declare -r (Read-Only)     │                              │ 2. Substring & Length:       │
  │ • declare -l/-u (Lowercase/  │                              │    ${#v}, ${v:offset:len}    │
  │   Uppercase transform)       │                              │ 3. Pattern Trimming:         │
  │ • declare -a/-A (Indexed /   │                              │    ${v#p}, ${v##p} (Prefix)  │
  │   Associative Array)         │                              │    ${v%p}, ${v%%p} (Suffix)  │
  │ • Positional Parameters      │                              │ 4. Search & Replace:         │
  │    ($1, $2, $@, $*)          │                              │    ${v/pattern/replacement}  │
  │ • Special Shell Parameters   │                              │ 5. Case Modification:        │
  │    ($?, $$, $!, $#)          │                              │    ${v^^}, ${v,,}            │
  └──────────────────────────────┘                              │ 6. Indirect Expansion:       │
                                                                │    ${!ref}                   │
                                                                └──────────────┬───────────────┘
                                                                               │
                                                                               ▼
                                                                ┌──────────────────────────────┐
                                                                │       SHELL WORD AUDIT       │
                                                                ├──────────────────────────────┤
                                                                │ • Quote Preservation: "$v"   │
                                                                │ • Word Splitting: IFS        │
                                                                │ • Glob Prevention: set -f    │
                                                                └──────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1.  **Eliminasi Overhead Fork-Exec (Performance Engineering)**:
    Di sistem operasi berbasis Unix/Linux, membuat proses baru via *syscall* `clone()` / `fork()` dan `execve()` membutuhkan biaya komputasi yang mahal (alokasi *page table*, *kernel context switching*, duplikasi file descriptor). Menggunakan `echo "$FILE" | cut -d'.' -f1` atau `basename "$FILE"` di dalam sebuah loop berisi 10.000 iterasi akan membuat 10.000 hingga 20.000 sub-proses baru. Menggantinya dengan Native Parameter Expansion (`${FILE%.*}`) memproses manipulasi string secara in-process di dalam alokasi memori Bash langsung, mengubah waktu eksekusi dari beberapa detik menjadi hitungan milidetik.

2.  **Pencegahan Remote Code Injection & Path Traversal (Robustness & Security)**:
    Manipulasi string yang tidak tepat sering menjadi pintu masuk serangan injeksi shell. Pemahaman mendalam tentang penanganan variabel *empty/unset* via ekspansi `${VAR:?Error message}` mencegah skrip melanjutkan eksekusi ke tahap berbahaya (misalnya insiden klasik eksekusi `rm -rf /${VAR}` ketika `$VAR` belum didefinisikan).

3.  **Portabilitas dan Kemandirian Lingkungan (Zero-dependency Scripting)**:
    Skrip operasional tingkat rendah (*bootstrapping*, *initrd*, *container entrypoints*) sering kali dieksekusi di *minimalist environment* di mana utilitas GNU coreutils atau binary `sed`/`awk` mungkin memiliki versi yang tidak kompatibel (misalnya perbedaan GNU `sed` vs BSD `sed` di macOS) atau bahkan tidak tersedia sama sekali. Menguasai ekspansi parameter menjamin kode berjalan deterministik murni menggunakan fasilitas internal shell binary.

---

## SEKSI 05 — APA ITU (WHAT)

Secara arsitektural, Bash tidak memiliki sistem tipe data formal seperti bahasa C atau Go. Semua variabel di Bash pada level internal diimplementasikan sebagai untaian karakter (C-style *null-terminated string*). Namun, Bash menyediakan sistem atribut internal melalui perintah bawaan `declare` atau `typeset` yang memodifikasi cara shell membaca dan memperlakukan representasi string tersebut.

### 1. Klasifikasi Tipe dan Atribut Variabel
*   **Standard String**: Tipe bawaan tak bertipe (*untyped*). Penjumlahan aritmatika pada string biasa akan menghasilkan operasi teks atau error penugasan.
*   **Integer Attribute (`declare -i`)**: Memberitahu evaluator Bash bahwa nilai variabel harus selalu dihitung sebagai ekspresi aritmatika ketika diberi nilai (*assignment*).
*   **Read-Only Attribute (`declare -r`)**: Mengunci entri memori variabel pada *hash table* internal Bash sehingga nilainya tidak dapat diubah (*immutable*) atau dihapus via `unset` selama *lifetime* proses shell tersebut.
*   **Array Attribute (`declare -a` & `declare -A`)**: Mengalokasikan array terindeks (integer index) atau asosiatif (key-value hashmap).

### 2. Parameter Expansion
Ekspansi Parameter (*Parameter Expansion*) adalah operasi pemrosesan yang dipicu oleh karakter sigil dolar (`$`) yang diapit kurung kurawal (`${...}`) di mana Bash melakukan subtitusi, inspeksi, pemotongan, atau modifikasi nilai parameter sebelum baris instruksi dipecah menjadi argumen perintah akhir.

Syntax dasarnya adalah:
`${PARAMETER_EXPRESSION}`

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Evaluasi ekspansi parameter terjadi dalam fase evaluasi ekspansi shell (*Shell Expansions Phase*). Urutan parsing Bash diproses dalam pipeline berikut:

1.  **Brace Expansion** (`{a,b}`)
2.  **Tilde Expansion** (`~`)
3.  **Parameter and Variable Expansion** (`$VAR`, `${VAR}`)
4.  **Arithmetic Expansion** (`$((...))`)
5.  **Command Substitution** (`$(...)`)
6.  **Word Splitting** (Hanya terjadi pada ekspansi yang **tidak** diapit *double quote*, berdasarkan nilai variabel `IFS`)
7.  **Pathname Expansion / Globbing** (`*.log`)
8.  **Quote Removal**

### Taksonomi Mekanisme Parameter Expansion

#### A. Default Values & Defensive Fallbacks
Operator titik dua (`:`) menentukan apakah pengujian mencakup kondisi *null/empty string* selain *unset*.
*   `${VAR:-word}`: Jika `VAR` tidak diset atau kosong (*null*), kembalikan `word`. Nilai `VAR` tidak berubah.
*   `${VAR:=word}`: Jika `VAR` tidak diset atau kosong (*null*), berikan nilai `word` ke `VAR`, lalu kembalikan hasilnya (*assignment on read*). Tidak dapat diterapkan pada positional parameter.
*   `${VAR:+word}`: Jika `VAR` terdefinisi dan tidak kosong, kembalikan `word`; sebaliknya kembalikan string kosong.
*   `${VAR:?error_message}`: Jika `VAR` tidak diset atau kosong, cetak `error_message` ke *standard error* (stderr) dan terminasi skrip non-interaktif dengan exit status non-zero (1).

#### B. Substring & Length Evaluation
*   `${#VAR}`: Menghitung panjang karakter dari string variabel.
*   `${VAR:offset}`: Mengambil substring mulai dari indeks `offset` (indeks berbasis 0) hingga akhir string.
*   `${VAR:offset:length}`: Mengambil substring sepanjang `length` dimulai dari posisi `offset`.
    *   *Peringatan Indeks Negatif*: Menulis `${VAR:-3}` akan terbaca sebagai operator default value. Sintaks substring negatif wajib menyertakan spasi atau kurung: `${VAR: -3}` atau `${VAR:(-3)}`.

#### C. Pattern Trimming (Removal of Substrings)
Mekanisme ini menggunakan *glob pattern* (bukan Regular Expression).
*   `${VAR#pattern}`: Hapus kecocokan *terpendek* (non-greedy) dari pola `pattern` yang berada di bagian **awal** (prefix) string.
*   `${VAR##pattern}`: Hapus kecocokan *terpanjang* (greedy) dari pola `pattern` yang berada di bagian **awal** (prefix) string.
*   `${VAR%pattern}`: Hapus kecocokan *terpendek* (non-greedy) dari pola `pattern` yang berada di bagian **akhir** (suffix) string.
*   `${VAR%%pattern}`: Hapus kecocokan *terpanjang* (greedy) dari pola `pattern` yang berada di bagian **akhir** (suffix) string.

#### D. Pattern Substitution (Search and Replace)
*   `${VAR/pattern/replacement}`: Mengganti kecocokan **pertama** dari `pattern` dengan `replacement`.
*   `${VAR//pattern/replacement}`: Mengganti **seluruh** kecocokan dari `pattern` dengan `replacement` (*global replacement*).
*   `${VAR/#pattern/replacement}`: Mengganti jika `pattern` cocok di **awal** string.
*   `${VAR/%pattern/replacement}`: Mengganti jika `pattern` cocok di **akhir** string.

#### E. Case Modification (Bash 4.0+)
*   `${VAR^}`: Mengubah karakter pertama menjadi huruf besar (*uppercase*).
*   `${VAR^^}`: Mengubah seluruh karakter menjadi huruf besar.
*   `${VAR,}`: Mengubah karakter pertama menjadi huruf kecil (*lowercase*).
*   `${VAR,,}`: Mengubah seluruh karakter menjadi huruf kecil.

#### F. Indirect Expansion
*   `${!VAR}`: Mengakses nilai dari variabel yang namanya disimpan dalam variabel `VAR` (*pointer-like dereference*).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perilaku Prefix Trimming (`#` vs `##`) dan Suffix Trimming (`%` vs `%%`)

Misalkan variabel `TARGET_PATH="/var/log/audit/audit_system.log.old"`

```
                                TARGET_PATH
  ┌────────────────────────────────────────────────────────────────────────┐
  │ /   v   a   r   /   l   o   g   /   a   u   d   i   t   /   ...  . o l d│
  └────────────────────────────────────────────────────────────────────────┘

  1. Prefix Stripping: Mencocokkan dari awal (kiri ke kanan) dengan pattern "*/"
     
     ${TARGET_PATH#*/}  (Non-greedy: berhenti pada slash pertama)
     [ / ] dihapus
     Hasil -> "var/log/audit/audit_system.log.old"
     
     ${TARGET_PATH##*/} (Greedy: mencari slash terakhir yang valid)
     [ /var/log/audit/ ] dihapus
     Hasil -> "audit_system.log.old"  <-- Mirip implementasi built-in "basename"


  2. Suffix Stripping: Mencocokkan dari akhir (kanan ke kiri) dengan pattern ".*"
     
     ${TARGET_PATH%.*}  (Non-greedy: berhenti pada titik paling kanan)
     [ .old ] dihapus
     Hasil -> "/var/log/audit/audit_system.log"
     
     ${TARGET_PATH%%.*} (Greedy: terus mencari titik paling awal yang valid)
     [ .log.old ] dihapus
     Hasil -> "/var/log/audit/audit_system"
```

### 2. Matriks Keputusan: Operator Pengujian Nilai Variabel

```
                     ┌───────────────────────────────┐
                     │ Kondisi Variabel:             │
                     │  - UNSET (Belum dibuat)       │
                     │  - NULL (VAR="")              │
                     │  - SET & BERISI (VAR="prod")  │
                     └───────────────┬───────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
      [ UNSET ]                   [ NULL ]                 [ BERISI ]
  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
  │ ${V:-DEFAULT}   │       │ ${V:-DEFAULT}   │       │ ${V:-DEFAULT}   │
  │   -> "DEFAULT"  │       │   -> "DEFAULT"  │       │   -> "prod"     │
  ├─────────────────┤       ├─────────────────┤       ├─────────────────┤
  │ ${V-DEFAULT}    │       │ ${V-DEFAULT}    │       │ ${V-DEFAULT}    │
  │   -> "DEFAULT"  │       │   -> ""         │       │   -> "prod"     │
  ├─────────────────┤       ├─────────────────┤       ├─────────────────┤
  │ ${V:=DEFAULT}   │       │ ${V:=DEFAULT}   │       │ ${V:=DEFAULT}   │
  │   -> V="DEFAULT"│       │   -> V="DEFAULT"│       │   -> V="prod"   │
  ├─────────────────┤       ├─────────────────┤       ├─────────────────┤
  │ ${V:?ERROR}     │       │ ${V:?ERROR}     │       │ ${V:?ERROR}     │
  │   -> Abort(Err) │       │   -> Abort(Err) │       │   -> "prod"     │
  └─────────────────┘       └─────────────────┘       └─────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Skrip berikut mendemonstrasikan manipulasi parameter dasar tanpa memanggil binary eksternal:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Deklarasi integer dan read-only
declare -i MAX_RETRIES=5
declare -r APP_ENV="production"

# Mencoba mereassign variabel integer dengan string akan dievaluasi secara aritmatika
declare -i COUNTER=0
COUNTER="COUNTER + 1" # Valid di Bash integer mode: COUNTER dievaluasi menjadi 1
echo "Counter value: ${COUNTER}"

# 2. Defensive Parameter Checking
# Mengambil PORT dari environment, fallback ke 8080 jika unset atau empty
HTTP_PORT="${PORT:-8080}"
echo "Server binding to port: ${HTTP_PORT}"

# 3. Path parsing murni Parameter Expansion
FULL_FILE_PATH="/opt/application/releases/v2.4.1/app.tar.gz"

# Mengambil directory path (mirip dirname)
DIR_PATH="${FULL_FILE_PATH%/*}"
echo "Directory : ${DIR_PATH}"

# Mengambil base filename (mirip basename)
FILE_NAME="${FULL_FILE_PATH##*/}"
echo "File Name : ${FILE_NAME}"

# Mengambil ekstensi penuh vs ekstensi akhir
FINAL_EXT="${FILE_NAME##*.}"
FULL_EXT="${FILE_NAME#*.}"
echo "Final Ext : ${FINAL_EXT}"
echo "Full Ext  : ${FULL_EXT}"

# 4. Search and Replace String
CANONICAL_NAME="${FILE_NAME//./_}"
echo "Sanitized : ${CANONICAL_NAME}"
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah skrip audit log parsial kelas produksi untuk pipeline penguraian log NGINX/Envoy secara efisien. Skrip ini memproses string log berulang-ulang tanpa *forking subprocess*, menggunakan *pure native string slicing* dan *parameter expansion*.

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: parse_ingress_log.sh
# Deskripsi: Mengurai format log raw tanpa utilitas eksternal (sed/awk/cut)
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail

# Verifikasi parameter input skrip wajib ada
declare RAW_LOG_ENTRY="${1:?FATAL: Input log entry harus diberikan sebagai argumen pertama.}"

# Format log simulasi:
# [TIMESTAMP] | IP:CLIENT_IP | STATUS:CODE | ROUTE:/path/to/resource | EXEC:TIME_MS
# Contoh:
# [2026-03-30T10:15:20Z] | IP:192.168.1.104 | STATUS:500 | ROUTE:/api/v1/checkout | EXEC:142ms

# Function pemroses murni internal memory
process_log_entry() {
    local entry="$1"
    
    # 1. Ekstrak Timestamp: Hapus prefix '[', buang suffix ']*'
    local ts_stage="${entry#\[}"
    local timestamp="${ts_stage%%\]*}"
    
    # 2. Potong log string untuk mengekstrak Status Code
    # Cari pola "*STATUS:" lalu ambil nilainya hingga delimiter ' |'
    local status_stage="${entry##*STATUS:}"
    local http_status="${status_stage%% |*}"
    
    # 3. Ekstrak Client IP
    local ip_stage="${entry##*IP:}"
    local client_ip="${ip_stage%% |*}"
    
    # 4. Ekstrak Route
    local route_stage="${entry##*ROUTE:}"
    local request_route="${route_stage%% |*}"

    # 5. Ekstrak Execution Time (hilangkan unit 'ms' di akhir via Pattern Stripping)
    local exec_stage="${entry##*EXEC:}"
    local exec_time_raw="${exec_stage%% *}"
    local exec_time_ms="${exec_time_raw%ms}"
    
    # 6. Transformasi data internal (Case Modification)
    local alert_level="normal"
    if [[ "${http_status}" -ge 500 ]]; then
        alert_level="critical"
    fi
    local alert_indicator="${alert_level^^}" # Ubah ke UPPERCASE

    # Output audit dalam format terstruktur
    cat <<EOF
--- INGRESS EVENT REPORT [${alert_indicator}] ---
Event Time  : ${timestamp}
Source Host : ${client_ip}
Route Target: ${request_route}
HTTP Code   : ${http_status}
Latency     : ${exec_time_ms} millisecond(s)
EOF
}

# Eksekusi fungsi utama
process_log_entry "${RAW_LOG_ENTRY}"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Kelebihan | Kekurangan / Batasan | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Native Bash Parameter Expansion** | **Performa Ekstrem**: Berjalan di memori proses utama (*zero fork*). Sangat cepat untuk loop.<br>**Portabilitas Tinggi**: Tidak terpengaruh varian OS (GNU vs BSD). | Pola pencocokan hanya mendukung **Glob Pattern** standar (`*`, `?`, `[...]`), bukan Regex ekspresif (PCRE). Kurang fleksibel untuk ekstraksi data multiline kompleks. | Manipulasi path file, sanitasi string pendek, manipulasi parsing berulang dalam loop besar, inisialisasi env. |
| **External Coreutils (`sed`, `awk`, `cut`)** | Kemampuan **Regular Expressions penuh**, manipulasi multiline canggih, pemrosesan file berukuran gigabyte via buffer streaming tanpa menghabiskan RAM Bash. | **Fork Overhead**: Menghidupkan binary baru membebani CPU bila dipanggil berulang di dalam iterasi loop shell.<br>**Inkonsistensi Sintaks**: Beda opsi CLI antara Linux (GNU) dan BSD/macOS. | Pengolahan stream teks berskala besar dari disk secara pipeline, file transformation terpusat. |
| **Bash Regex Matching (`=~` Operator)** | Native di dalam shell tanpa sub-proses eksternal. Mendukung POSIX Extended Regular Expressions (ERE) via grup tangkap (*capture group* `BASH_REMATCH`). | Kompatibilitas terbatas pada Bash 3+. Evaluasi kompleksitas regex rentan *backtracking* yang dapat membekukan interpreter Bash. Sintaks parsing kadang sensitif terhadap *quoting*. | Validasi format data (misalnya format UUID, validasi alamat IP, email) secara langsung di kondisi blok `if [[ ... ]]`. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Selalu Gunakan Double Quotes pada Ekspansi Variabel**:
    Gunakan `"${MY_VAR}"`, bukan `$MY_VAR`. Mengabaikan tanda kutip akan memaksa shell melakukan fase *Word Splitting* berdasarkan whitespace dan mengevaluasi *Pathname Expansion (Globbing)*, yang berpotensi merusak string dengan spasi atau memicu kerentanan eksekusi saat memuat karakter wildcard (`*`).
    
2.  **Gunakan Format Kurung Kurawal Eksplisit**:
    Gunakan `${VAR}_suffix`, bukan `$VAR_suffix`. Tanpa kurung kurawal, Bash parser akan menganggap `VAR_suffix` sebagai satu nama variabel tunggal yang utuh.

3.  **Terapkan Fail-Fast dengan Defensive Fallbacks**:
    Gunakan `${CONFIG_DIR:?CONFIG_DIR belum diset!}` pada variabel krusial skrip produksi. Jangan biarkan variabel kosong memicu operasi sistem yang destruktif.

4.  **Deklarasikan Variabel dengan Atribut Tepat**:
    *   Gunakan `local -r` di dalam fungsi untuk variabel yang nilainya konstan (*read-only*) demi mencegah polusi state global (*global scope poisoning*).
    *   Gunakan `declare -i` bila variabel tersebut secara eksklusif hanya menyimpan bilangan bulat.

5.  **Batasi Modifikasi Nilai Melalui Indirect Expansion**:
    Sintaks `${!var}` membuat skrip sulit dibaca dan dianalisis secara statis (*static analysis tools* seperti ShellCheck). Batasi penggunaannya atau gunakan *Associative Arrays* (`declare -A`) sebagai alternatif yang jauh lebih bersih dan terstruktur.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Spasi pada Variabel Assignment
```bash
# SALAH (Bash mengira 'MY_KEY' adalah perintah dan '=' adalah argumennya):
MY_KEY = "value"
MY_KEY= "value"

# BENAR:
MY_KEY="value"
```

### 2. Word Splitting pada Parameter Tak Dikutip (*Unquoted Expansion*)
```bash
FILE="my document.pdf"

# SALAH: Diekspansi menjadi: rm my document.pdf (Menghapus 2 file berbeda!)
rm $FILE

# BENAR: Menjaga string utuh sebagai satu argumen
rm "$FILE"
```

### 3. Mengacaukan `${VAR:-DEFAULT}` dengan `${VAR:=DEFAULT}`
```bash
# KESALAHAN LOGIKA:
# Menggunakan := pada variabel yang bersifat positional parameter ($1, $2, dsb)
# akan melempar fatal error: "cannot assign in this way"
set -- ""
echo "${1:=fallback}" # ERROR!

# BENAR: Gunakan :- untuk positional parameter
echo "${1:-fallback}" # Output: fallback
```

### 4. Perangkap Operator Substring Negatif
```bash
STR="PRODUCTION_BUILD"

# SALAH: Terbaca sebagai ekspansi default value "${VAR:-3}", bukan substring!
echo "${STR:-3}" # Output: "PRODUCTION_BUILD"

# BENAR: Berikan spasi pemisah atau tanda kurung
echo "${STR: -3}" # Output: "ILD"
echo "${STR:(-3)}" # Output: "ILD"
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Ekstraktor Struktur URL Database (Tingkat: Sederhana)
*   **Skenario**: Anda menerima format URL koneksi database yang tersimpan di environment variable:
    `DB_URL="postgres://db_user:s3cr3tP@ssw0rd@10.0.4.15:5432/analytics_db"`
*   **Tugas**:
    Tulis skrip tanpa memanggil binary `sed`, `awk`, atau `cut` untuk mengekstrak komponen berikut menggunakan pure Parameter Expansion:
    1.  Protokol (`postgres`)
    2.  Host dan Port (`10.0.4.15:5432`)
    3.  Nama Database (`analytics_db`)

### Latihan 2: Pembersih Ekstensi Ganda dan Normalisasi Path (Tingkat: Menengah)
*   **Skenario**: Sistem backup menghasilkan file dengan format bervariasi:
    `BACKUP_FILES=("/data/backup_2026.01.tar.gz" "/var/backup_2026.02.tgz" "/home/archive.zip")`
*   **Tugas**:
    Iterasi seluruh elemen di atas menggunakan loop, kemudian dengan parameter expansion murni:
    1.  Ambil nama file utuh tanpa direktori.
    2.  Buang seluruh ekstensi arsip (misalnya `.tar.gz`, `.tgz`, `.zip`) sehingga hanya tersisa nama mentahnya saja (contoh output: `backup_2026.01`).
    3.  Ganti karakter titik `.` pada nama mentah tersebut menjadi tanda garis bawah `_` (contoh: `backup_2026_01`).

### Latihan 3: Parser Header HTTP (Tingkat: Menantang)
*   **Skenario**: Anda memiliki raw line HTTP header:
    `RAW_HEADER="Content-Type: application/json; charset=UTF-8; boundary=something"`
*   **Tugas**:
    1.  Validasi bahwa header tersebut diawali dengan `Content-Type:` (jika tidak, skrip harus melempar error dan exit).
    2.  Ambil nilai MIME type utuh (`application/json`).
    3.  Ekstrak nilai spesifikasi `charset` (`UTF-8`). Pastikan output charset selalu dikonversi menjadi lowercase (`utf-8`) secara otomatis menggunakan operator native parameter expansion.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawab pertanyaan berikut secara mandiri sebelum memeriksa kunci analisis:

1.  Diberikan deklarasi: `TARGET="apps/service/payment/handlers.go"`. Parameter expansion manakah yang akan menghasilkan output `"payment/handlers.go"`?
    *   A. `${TARGET#*/}`
    *   B. `${TARGET##*/}`
    *   C. `${TARGET#*service/}`
    *   D. `${TARGET%/*}`

2.  Apa perbedaan mendasar antara ekspansi `${FOO-bar}` dan `${FOO:-bar}` jika variabel didefinisikan sebagai `FOO=""` (empty string)?
    *   A. Tidak ada perbedaan, keduanya menghasilkan string kosong `""`.
    *   B. `${FOO-bar}` menghasilkan `""`, sedangkan `${FOO:-bar}` menghasilkan `"bar"`.
    *   C. Keduanya melempar syntax error.
    *   D. `${FOO-bar}` menghasilkan `"bar"`, sedangkan `${FOO:-bar}` menghasilkan `""`.

3.  Mengapa skrip `declare -i VAL=10; VAL="20 + 5"; echo "$VAL"` menghasilkan `25` bukannya string `"20 + 5"`?
    *   A. Bash mendeteksi tanda kutip dua dan mengeksekusi perintah aritmatika secara implisit.
    *   B. Karena flag `-i` pada `declare` mengaktifkan atribut evaluasi aritmatika pada setiap operasi penugasan nilai ke variabel tersebut.
    *   C. Nilai mengalami parsing otomatis oleh compiler sistem.
    *   D. Terjadi bug pada Bash string evaluator.

4.  Apa efek keamanan jika kita mengeksekusi instruksi: `rm -rf "${CACHE_DIR:?Variable must be set}/data"` jika `CACHE_DIR` belum pernah dideklarasikan sebelumnya?
    *   A. Skrip akan mengeksekusi `rm -rf /data` yang berpotensi merusak sistem.
    *   B. Skrip mencetak string pesan error ke stderr dan langsung menghentikan proses eksekusi (*abort*) dengan exit status 1, sehingga perintah `rm -rf` tidak dijalankan.
    *   C. Skrip secara otomatis membuat direktori sementara lalu menghapusnya.
    *   D. Perintah dilewati secara hening (*silent fail*) tanpa pesan error.

5.  Diberikan instruksi `VAR="alpha_beta_gamma"`. Ekspansi `${VAR//[a-z]/X}` akan menghasilkan:
    *   A. `X_beta_gamma`
    *   B. `XXXXX_XXXX_XXXXX`
    *   C. `alpha_beta_gamma`
    *   D. `X_X_X`

---

### Kunci Jawaban & Penjelasan Kuis

1.  **Jawaban C**:
    *Penjelasan*: `${TARGET#*service/}` mencocokkan pattern `*service/` dari awal string dan menghapusnya secara non-greedy, menyisakan string `payment/handlers.go`. Opsi A menghasilkan `service/payment/handlers.go`, sedangkan Opsi B memotong seluruh path menyisakan `handlers.go`.
2.  **Jawaban B**:
    *Penjelasan*: Tanda titik dua (`:`) pada ekspansi default value menambahkan pengecekan *null/empty string*. Tanpa titik dua (`${FOO-bar}`), shell hanya mengecek apakah variabel dalam status *unset*. Karena `FOO` sudah diset (meskipun kosong), `${FOO-bar}` mengembalikan nilai asli `FOO` yaitu `""`. Sebaliknya, `${FOO:-bar}` melihat bahwa nilainya kosong lalu mengembalikan default value `"bar"`.
3.  **Jawaban B**:
    *Penjelasan*: Atribut `declare -i` memberi instruksi kepada interpreter Bash bahwa setiap string literal yang di-assign ke variabel tersebut harus diparsing menggunakan internal arithmetic evaluator (`$((...))`).
4.  **Jawaban B**:
    *Penjelasan*: Ekspansi `${VAR:?message}` bertindak sebagai fail-safe assertion. Skrip non-interaktif akan langsung *terminate* seketika jika kondisi unset/null terpenuhi sebelum baris perintah dieksekusi.
5.  **Jawaban B**:
    *Penjelasan*: Sintaks `${VAR//pattern/replacement}` menggunakan double slash `//` yang menandakan substitusi global. Pattern `[a-z]` mencocokkan setiap karakter huruf kecil, sehingga semua karakter alfabet diganti dengan `X`, sedangkan karakter garis bawah `_` tetap dipertahankan.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **GNU Bash Reference Manual**:
    *   *Section 3.5.3: Shell Parameter Expansion*
    *   Link: `https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html`
2.  **POSIX.1-2017 Standard (IEEE Std 1003.1-2017)**:
    *   *Section 2.6.2: Parameter Expansion*
    *   Link: `https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_06_02`
3.  **Bash Hackers Wiki**:
    *   *Comprehensive Parameter Expansion Guide & Pattern Matching Nuances*
    *   Link: `https://wiki.bash-hackers.org/syntax/pe`
4.  **Advanced Bash-Scripting Guide (Mendel Cooper)**:
    *   *Chapter 10: Manipulating Variables*
5.  **Google Shell Style Guide**:
    *   Pedoman resmi penggunaan konvensi penamaan variabel dan aturan quoting.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  Bash mengelola tipe data secara internal sebagai string (*stringly-typed*). Atribut pengubah seperti `-i` (integer) atau `-r` (readonly) dapat diatur via built-in `declare` untuk memodifikasi bagaimana Bash mengevaluasi penugasan nilai.
2.  Ekspansi parameter native Bash (`${...}`) adalah teknik pemrosesan string paling efisien karena dieksekusi langsung di *user memory space* interpreter shell tanpa menimbulkan *syscall overhead* pembuatan sub-proses baru (*zero fork-exec overhead*).
3.  Operator default (`:-`, `:=`, `:?`, `:+`) memberikan pertahanan berlapis untuk menjamin keberadaan data sebelum operasi sensitif dijalankan.
4.  Pemotongan pola string mengandalkan simbol `#` / `##` untuk menghapus prefix dari sisi kiri dan `%` / `%%` untuk menghapus suffix dari sisi kanan. Karakter tunggal berarti pencocokan terpendek (*non-greedy*), sedangkan karakter ganda berarti pencocokan terpanjang (*greedy*).
5.  Substitusi string native `${VAR/pola/pengganti}` dan kontrol kapitalisasi `${VAR^^}` / `${VAR,,}` menggantikan kebutuhan dasar pemanggilan binary `sed` atau `tr` untuk kebutuhan manipulasi string per baris.

---

## SEKSI 17 — GLOSARIUM

*   **Parameter Expansion**: Mekanisme internal shell untuk mengambil, mengubah, atau memvalidasi nilai yang diasosiasikan dengan parameter yang diawali tanda sigil `$`.
*   **Word Splitting**: Proses di mana shell membagi hasil ekspansi parameter unquoted menjadi beberapa *token/words* berdasarkan karakter pemisah yang didefinisikan pada variabel `IFS`.
*   **Pathname Expansion (Globbing)**: Pola pencocokan nama file shell menggunakan karakter wildcard (`*`, `?`, `[]`) yang diurai menjadi daftar path file di filesystem.
*   **Fork-Exec Model**: Mekanisme kernel Unix dalam menduplikasi proses saat ini (`fork`) dan menimpa memori proses baru tersebut dengan program executable lain (`execve`).
*   **Sigil**: Simbol grafis (seperti `$`) yang ditempelkan pada identifier variabel untuk menginstruksikan shell agar mengevaluasi nilainya.
*   **Greedy vs Non-Greedy Matching**: Sifat ekspansi pola di mana *greedy* (`##`, `%%`) mencari kecocokan karakter terpanjang yang mungkin, sedangkan *non-greedy* (`#`, `%`) berhenti pada batas kecocokan pertama terpendek yang ditemukan.
*   **Indirect Expansion**: Fitur dereferensiasi tingkat lanjut di mana isi dari sebuah variabel diinterpretasikan kembali sebagai nama variabel target yang nilainya ingin diekstrak (`${!VAR}`).
*   **Null vs Unset**: Keadaan di mana *unset* berarti variabel belum pernah dideklarasikan di memori shell, sedangkan *null* berarti variabel telah dideklarasikan namun berisi string dengan panjang nol (`""`).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Materi:
*   Banyak peserta didik pemula yang secara tidak sadar memanggil `echo "$VAR" | cut -d: -f2` di dalam looping ribuan baris log. Tunjukkan secara langsung kepada mereka perbedaan waktu eksekusi (*execution benchmark*) antara loop 5.000 iterasi menggunakan sub-proses eksternal versus pure parameter expansion (`time` command). Perbedaan performanya bisa mencapai rasio 100:1.
*   Tekankan secara keras bahaya melepas *double quote* (`"$VAR"`). Demonstrasikan bagaimana sebuah file dengan nama `foo * bar.txt` akan memicu kehancuran logika jika diproses tanpa quoting saat shell membaca wildcard `*`.

### Benchmark Demonstrasi Kelas:
Jalankan snippet ini di terminal proyektor untuk memperlihatkan dampak *forking overhead*:
```bash
# Skenario 1: Fork 2000 subproses (LAMBAT)
time for i in {1..2000}; do x=$(basename "/long/path/to/target/file.txt"); done

# Skenario 2: Pure Parameter Expansion (SANGAT CEPAT)
time for i in {1..2000}; do x="${x##*/}"; done
```

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2026)**:
    *   Rilis awal materi Bab 03 Module 01.
    *   Penyelarasan dengan standar Bash 5.2 engine.
    *   Penambahan diagram visual parsing greediness `#` vs `%`.
    *   Penyusunan modul hands-on dan kuis pemahaman teknis mendalam.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya**:
    *   [BASH-01-02: Proses Eksekusi Shell, Fork-Exec Model & Subshell](../02-shell-execution-engine)
*   **Modul Berikutnya**:
    *   [BASH-01-04: Arrays & Associative Arrays (Struktur Data Shell Lanjutan)](../04-arrays-and-data-structures)
*   **Akses Repositori Materi**:
    *   Direktori Kurikulum: `core-foundations/03-variables-and-parameter-expansion/`